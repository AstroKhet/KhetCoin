import asyncio
import logging
import miniupnpc
import random
import time

from typing import Optional, Set, Tuple

from blockchain.block import Block
from crypto.hashing import HASH160
from crypto.key import get_public_key
from db.index import BlockIndex, get_block_tip_index
from db.peers import load_all_peers
from mining.mempool import Mempool
from mining.miner import Miner
from networking.constants import CONNECTION_TIMEOUT, HANDSHAKE_TIMEOUT
from networking.messages.envelope import MessageEnvelope
from networking.messages.types.getaddr import GetAddrMessage
from networking.messages.types.mempool import MempoolMessage
from networking.peer import Peer
from networking.processor import MessageProcessor
from utils.config import APP_CONFIG


log = logging.getLogger(__name__)


class Node:
    def __init__(self, name: str, port: int = 8666, loop=None):
        self.name = name
        self.port = port
        self.external_ip = self.setup_port_forwarding() or "0.0.0.0"
        
        self.peers: Set[Peer] = set()
        self.pk_hash: bytes = HASH160(get_public_key(name, raw=True))

        # Self (server)
        self.server: asyncio.Server | None = None
        self.server_start_time: int = 0
        self.loop = loop
        self.mempool = Mempool()
        self.miner = Miner()

        # Clients (peers)
        self.next_peer_id: int = 0
        self.peer_id_lookup: dict = dict()
        self.bytes_recv: int = 0
        self.bytes_sent: int = 0

        # Async variables
        self.processor = MessageProcessor(self)
        self.processor_queue: asyncio.Queue[Tuple[Peer, MessageEnvelope]] = asyncio.Queue()  # For db write serialization

        self._shutdown_requested = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        
        self.is_running = False
        # Transient variables for efficient GUI update
        
        # Block consensus 
        self.block_tip_index: BlockIndex = get_block_tip_index()
        self.orphan_blocks: list[Block] = []
        
        self._updated_blockchain = 0
        self._updated_peers = 0
        log.info(f"Node '{self.name}' initialized on {self.external_ip}:{self.port}")

    def setup_port_forwarding(self):
        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            upnp.discover()
            upnp.selectigd()

            external_port = self.port
            internal_port = self.port
            protocol = 'TCP'

            upnp.addportmapping(external_port, protocol, upnp.lanaddr, internal_port, f"MyNode-{self.name}", '')
            log.info(f"Port {external_port} forwarded via UPnP to {upnp.lanaddr}:{internal_port}")
            return upnp.externalipaddress()
        except Exception as e:
            log.warning(f"UPnP port forwarding failed: {e}")
            return None
        
    async def start_server(self):
        try:
            self.server = await asyncio.start_server(
                self._handle_incoming_connection, "0.0.0.0", self.port
            )
            addr = self.server.sockets[0].getsockname()
            self.server_start_time = int(time.time())

            log.info(f"Server listening on {addr}")
        except Exception as e:
            log.exception(f"Error starting server: {e}")
            self.server = None
            self._shutdown_requested.set()

        self.is_running = True
        
    async def close_server(self):
        self.is_running = False
        self.server_start_time = 0
        
        awaitables = []

        if self.server:
            log.debug("Closing server...")
            self.server.close()
            self.server = None

        tasks_to_cancel = list(self._tasks)
        self._tasks.clear()

        peers_to_close = list(self.peers)
        self.peers.clear()
        self._updated_peers = 0

        for peer in peers_to_close:
            awaitables.append(peer.close())

        for task in tasks_to_cancel:
            task.cancel()
            awaitables.append(task)
                
        await asyncio.gather(*awaitables, return_exceptions=True)

        
    async def run(self):
        log.info(f"Node starting...")
        self._shutdown_requested.clear()

        server_task = asyncio.create_task(self.start_server())
        self.add_task(server_task)

        if self._shutdown_requested.is_set():
            log.error(f"Exiting run() because server failed to start.")
            await self.close_server()
            return

        processor_task = asyncio.create_task(self._message_processor_loop())
        self.add_task(processor_task)

        connect_initial_task = asyncio.create_task(self._connect_initial_peers())
        self.add_task(connect_initial_task)

        peer_rotation_task = asyncio.create_task(self._rotate_peers())
        self.add_task(peer_rotation_task)

        log.info(f"Node running. Waiting for shutdown signal...")
        self.is_running = True
        await self._shutdown_requested.wait()

        log.info(f"Shutdown requested. Cleaning up...")
        await self._shutdown_tasks()
        log.info(f"Node finished.")

    async def connect_to_peer(self, addr: tuple, name: str = "", initial=False):
        peer_str_ip = f"{addr[0]}:{addr[1]}"
        if addr == (self.external_ip, self.port):
            log.warning("Attempted to self connect.")
            return
        
        if len(self.peers) >= APP_CONFIG.get("node", "max_peers"):
            return

        log.info(f"Attempting TCP connection to {peer_str_ip}...")
        reader = writer = None
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(addr[0], addr[1]), timeout=CONNECTION_TIMEOUT)
            log.info(f"TCP connection established with {peer_str_ip}. Starting handshake...")
        except ConnectionRefusedError:
            log.info(f"{peer_str_ip} - connection refused.")
            return
        except Exception as e:
            log.exception(f"Unexpected error connecting TCP to {peer_str_ip}: {e}")
            return

        peer = Peer(self, reader, writer, name, session_id=self.next_peer_id, direction="outbound")
        self.peer_id_lookup[self.next_peer_id] = peer
        self.next_peer_id += 1
        listen_task = asyncio.create_task(peer.listen())
        peer.listen_task = listen_task
        self.add_task(listen_task)

        try:
            await peer.send_version()
            established = await asyncio.wait_for(
                peer.established, timeout=HANDSHAKE_TIMEOUT
            )
            if established:
                self.peers.add(peer)
                self._updated_peers = 0
                
                if initial:
                    log.info(f"Mempool message sent")
                    self.add_task(asyncio.create_task(peer.send_message(MempoolMessage())))
            else:
                log.warning(f"Handshake failed with peer {peer.str_ip}.")
        except Exception as e:
            log.exception(f"Error during handshake with peer {peer.str_ip}: {e}")
            await peer.close()

    def broadcast(self, 
        message,
        exclude: Optional[Peer] = None,
        sample: int = APP_CONFIG.get("node", "max_peers"),
        outbound: bool = False
    ):
        """
        Broadcasts a `message` of type `MessageEnvelope` or and of `networking.messages.types.CORE_MESSAGE` to up to `sample` connected peers except `exclude`
        \nRestricts to only outbound peers if `outbound` is True
        """
        target_peers = list(self.peers)

        if exclude: 
            target_peers = [peer for peer in target_peers if peer != exclude]

        if outbound:
            target_peers = [peer for peer in target_peers if peer.direction == "outbound"]

        target_peers = random.sample(
            target_peers,
            max(0, min(sample, len(target_peers)))
        )

        for peer in target_peers:
            asyncio.run_coroutine_threadsafe(peer.send_message(message), self.loop)

    async def _handle_incoming_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        # Get peer address
        addr = writer.get_extra_info("peername", ("Unknown", 0))
        peer_str_ip = f"{addr[0]}:{addr[1]}"
        log.debug(f"Handling incoming connection from {peer_str_ip}")

        # Check if its possible to connect with peer
        if len(self.peers) >= APP_CONFIG.get("node", "max_peers"):
            writer.close()
            await writer.wait_closed()
            return

        if any(p.addr == addr for p in self.peers):
            writer.close()
            await writer.wait_closed()
            return

        # Create peer object
        peer = Peer(self, reader, writer, session_id=self.next_peer_id, direction="inbound")
        self.peer_id_lookup[self.next_peer_id] = peer
        self.next_peer_id += 1

        # Start listening to peer
        log.info(
            f"Connected to peer no. {peer.session_id} from {peer.str_ip}. Starting handshake..."
        )

        listen_task = asyncio.create_task(peer.listen(), name=f"Listen_{peer.str_ip}")
        peer.listen_task = listen_task
        self.add_task(listen_task)

        # Send VersionMessage
        await peer.send_version()

        try:
            log.debug(
                f"Waiting for handshake established future from {peer.str_ip}..."
            )
            established = await asyncio.wait_for(
                peer.established, timeout=HANDSHAKE_TIMEOUT
            )
            if established:
                log.info(f"Handshake successful with incoming peer {peer.str_ip}. Adding to peers.")
                self.peers.add(peer)
                self._updated_peers = 0
                await peer.send_message(GetAddrMessage())
            else:
                log.warning(f"Handshake failed or rejected by incoming peer {peer.str_ip} (established=False).")
        
        except Exception as e:
            log.exception(f"Error during handshake with incoming peer {peer.str_ip}: {e}")
            if not peer.writer.is_closing():
                await peer.close()

    async def _message_processor_loop(self):
        log.info("Message processor loop started.")
        while not self._shutdown_requested.is_set():
            try:
                peer, message_envelope = await self.processor_queue.get()
                # Concurrent message processing
                # processor_task = asyncio.create_task(
                #     self.processor.process_message(peer, message_envelope)
                # )
                # self.add_task(processor_task)

                # Single message processing
                await self.processor.process_message(peer, message_envelope)
                self.processor_queue.task_done()

            except Exception as e:
                log.exception(f"Error in message processor loop: {e}")
                await asyncio.sleep(1)

        log.info("Message processor loop finished.")

    async def _connect_initial_peers(self):
        log.info("Connecting to initial peers...")
        peers_to_connect = await load_all_peers()
        peers_to_connect = peers_to_connect[:APP_CONFIG.get("node", "max_peers")]
        if not peers_to_connect:
            return 

        for peer_id, name, ip, port, added, last_seen, services in peers_to_connect:
            self.add_task(
                asyncio.create_task(
                    self.connect_to_peer((ip, port), name, initial=True)
                )
            )

    async def _rotate_peers(self):
        timeout = APP_CONFIG.get("node", "peer_inactive_timeout")

        while not self._shutdown_requested.is_set():
            now = time.time()
            
            # 1. Clear inactive peers
            for peer in list(self.peers):
                if now - peer.last_recv > timeout:
                    self.remove_peer(peer)
                    log.info(f"Removed inactive peer {peer}")
                    
            await asyncio.sleep(1)
                
            
    def add_task(self, task: asyncio.Task):
        def task_done(task: asyncio.Task):
            try:
                task.result()  # This re-raises if the task had an exception
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.error(f"Task failed: {e}")
            finally:
                self._tasks.discard(task)

        self._tasks.add(task)
        task.add_done_callback(task_done)

    async def shutdown(self):
        log.info(f"External shutdown triggered.")
        self._shutdown_requested.set()

    async def _shutdown_tasks(self):
        await self.close_server()

    def remove_peer(self, peer: Peer):
        peer.close()
        self.peers.discard(peer)
        self.peer_id_lookup.pop(peer.session_id)
        self._updated_peers = 0
        
        log.info(f"Peer No. {peer.session_id} disconnected.")

    def get_peer_by_id(self, peer_id: int) -> Peer | None:
        return self.peer_id_lookup.get(peer_id)
        
    def check_updated_peers(self, i=1):
        """
        Checks if any transactions were added or removd from self.peers from the last time this function was called.
        \n`i` is used as an ID for different frames.
        """
        updated = (self._updated_peers >> i) & 1 == 0
        self._updated_peers |= (1 << i)
        return updated
    
    def check_updated_blockchain(self, i=1):
        updated = (self._updated_blockchain >> i) & 1 == 0
        self._updated_blockchain |= (1 << i)
        return updated
    
    def set_tip(self, block_index):
        self.block_tip_index = block_index
        self._updated_blockchain = 0
    
    @property
    def uptime(self) -> int:
        if self.server_start_time:
            return int(time.time()) - self.server_start_time
        else:
            return 0
