import asyncio
import logging
import random
import time

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
        self.external_ip = None # Placeholder first, port forwarding is done when node actually startstup
        
        self.peers: set[Peer] = set()
        self.pk_hash: bytes = HASH160(get_public_key(name, raw=True))

        # Self (server)
        self.server: asyncio.Server | None = None
        self.server_start_time: int = 0
        self.loop: asyncio.AbstractEventLoop = loop
        self.mempool = Mempool(self)
        self.miner = Miner()
        
        # Clients (peers)
        self.next_peer_id: int = 0
        self.peer_id_lookup: dict = dict()
        self.bytes_recv: int = 0
        self.bytes_sent: int = 0

        # Async variables
        self.msg_processor = MessageProcessor(self)
        self.msg_processor_queue: asyncio.Queue[tuple[Peer, MessageEnvelope]] = asyncio.Queue()  # For db write serialization

        self._shutdown_requested = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        
        self.is_running = False
        
        # Block consensus 
        self.block_tip_index: BlockIndex = get_block_tip_index()
        self.orphan_blocks: set[Block] = set()
        
        # Transient variables for efficient GUI update
        self._updated_blockchain = 0
        self._updated_peers = 0
        log.info(f"Node '{self.name}' initialized on {self.external_ip}:{self.port}")

 
    async def run(self):
        log.info(f"Node starting...")
        self._shutdown_requested.clear()
        
        log.info(f"Node accessible via {self.external_ip}:{self.port}")
        
        self.mempool.load_mempool()
        log.info(f"Mempool loaded with {len(self.mempool._valid_txs)} transactions.")
        

        log.info("Spawning Node startup tasks...")
        self.spawn(self._start_server())
        self.spawn(self._message_processor_loop())
        self.spawn(self._initial_connection_task())
        self.spawn(self._node_management_task())

        log.info(f"Node running. Waiting for shutdown signal...")
        self.is_running = True
        await self._shutdown_requested.wait()

        log.info(f"Shutdown requested. Cleaning up...")
        await self._close_server()
        log.info(f"Node finished.")
        
    async def shutdown(self):
        log.info(f"External shutdown triggered.")
        self._shutdown_requested.set()

    async def _start_server(self):
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
       
    async def _close_server(self):
        log.info("Shutting down server...")

        self.is_running = False
        self.server_start_time = 0

        self.mempool.save_mempool()
        log.info(f"Mempool saved with {len(self.mempool._valid_txs) + len(self.mempool._orphan_txs)} txs")
        if self.server:
            log.debug("Closing server socket...")
            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception as e:
                log.warning(f"Error while waiting for server to close: {e}")
            self.server = None

        # Cancel all background tasks
        tasks_to_cancel = list(self._tasks)
        self._tasks.clear()
        for task in tasks_to_cancel:
            task.cancel()

        peers_to_close = list(self.peers)
        self.peers.clear()
        self._updated_peers = 0

        awaitables = [peer.close() for peer in peers_to_close]
        awaitables.extend(tasks_to_cancel)

        results = await asyncio.gather(*awaitables, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                log.warning(f"Exception during shutdown: {r}")

        log.info("Server shutdown complete.")
     
    async def _message_processor_loop(self):
        log.info("Message processor loop started.")
        while not self._shutdown_requested.is_set():
            peer, message_envelope = await self.msg_processor_queue.get()
            try:
                await self.msg_processor.process_message(peer, message_envelope)
            except Exception as e:
                log.exception(f"Error in message processor loop: {e}")
            finally:
                # Remove the task regardless (otherwise it STOPS once an exception raises!!! definitely didnt take 2 days to realise this !!!)
                self.msg_processor_queue.task_done()

        log.info("Message processor loop finished.")

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
        log.info(f"[{peer.str_ip}] Connected as peer no. {peer.session_id}; Starting handshake")

        listen_task = self.spawn(peer.listen())
        peer.listen_task = listen_task

        # Send VersionMessage
        await peer.send_version()
        try:
            log.debug(f"[{peer.str_ip}] Waiting for handshake established future")
            established = await asyncio.wait_for(peer.established, timeout=HANDSHAKE_TIMEOUT)
            if established:
                log.info(f"[{peer.str_ip}] Handshake successful. Adding to peers.")
                self.peers.add(peer)
                self._updated_peers = 0
                await peer.send_message(GetAddrMessage())
                if peer.height > self.block_tip_index.height:
                    await peer.send_getblocks()
            else:
                log.warning(f"[{peer.str_ip}] Handshake failed or rejected .")
        
        except Exception as e:
            log.warning(f"[{peer.str_ip}] Error during handshake: {e}")
            if not peer.writer.is_closing():
                await peer.close()

    async def _connect_to_peer(self, addr: tuple, name: str = "", initial=False):
        if len(self.peers) >= APP_CONFIG.get("node", "max_peers"):
            log.info("Cannot connect to peer; max amount reached")
            return

        peer_str_ip = f"{addr[0]}:{addr[1]}"
        log.info(f"[{peer_str_ip}] Attempting to connect...")
        if addr == (self.external_ip, self.port):
            log.warning(f"[{peer_str_ip}] Attempted to self connect.")
            return
        

        reader = writer = None
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(addr[0], addr[1]), timeout=CONNECTION_TIMEOUT)
            log.info(f"[{peer_str_ip}] TCP connection established. Starting handshake...")
        except TimeoutError:
            log.info(f"[{peer_str_ip}] Connection not established for {CONNECTION_TIMEOUT}s. Giving up.")
        except ConnectionRefusedError:
            log.info(f"[{peer_str_ip}] Connection refused.")
            return
        except Exception as e:
            log.exception(f"[{peer_str_ip}] Unexpected error attempting TCP connection: {e}")
            return
        
        if writer is None:
            log.info(f"[{peer_str_ip}] No writer.")
            return
        
        peer = Peer(self, reader, writer, name, session_id=self.next_peer_id, direction="outbound")
        self.peer_id_lookup[self.next_peer_id] = peer
        self.next_peer_id += 1
        peer.listen_task = self.spawn(peer.listen())

        try:
            await peer.send_version()
            established = await asyncio.wait_for(peer.established, timeout=HANDSHAKE_TIMEOUT)
            if established:
                log.info(f"[{peer_str_ip}] Handshake success. Pear established.")
                self.peers.add(peer)
                self._updated_peers = 0
                
                if initial:
                    await peer.send_message(MempoolMessage())
                if peer.height > self.block_tip_index.height:
                    await peer.send_getblocks()
            else:
                log.info(f"[{peer_str_ip}] Handshake failed.")
        except Exception as e:
            log.info(f"[{peer_str_ip}] Error during handshake with peer {peer.str_ip}: {e}")
            await peer.close()

    async def _initial_connection_task(self):
        log.info("Connecting to initial peers...")
        peers_to_connect = await load_all_peers()
        peers_to_connect = peers_to_connect[:APP_CONFIG.get("node", "max_peers")]
        if not peers_to_connect:
            return 

        for peer_meta in peers_to_connect:
            self.spawn(self._connect_to_peer((peer_meta.ip, peer_meta.port), peer_meta.name, initial=True))


    async def _node_management_task(self):
        """
        Running loop to manage expiry for peers and mempool txns
        """
        timeout = APP_CONFIG.get("node", "peer_inactive_timeout")
        while not self._shutdown_requested.is_set():
            now = time.time()
            
            for peer in list(self.peers):
                # Clear inactive peers
                if peer.last_recv_ago > timeout:
                    await peer.close()
                    log.info(f"[{peer.str_ip}] Removed inactive peer.")

                # Regular pinging to keep peer alive
                if (now - peer.last_ping) >= 120:
                    peer.ping()
                    
                # 
                if (peer.height - self.block_tip_index.height >= 5) and (peer.last_block_ago >= 30):
                     await peer.send_getblocks()
                    
            await asyncio.sleep(1)
                
    def spawn(self, coro):
        task = self.loop.create_task(coro)
        self._tasks.add(task)

        def task_done(t: asyncio.Task):
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.exception(f"Task Failed: {e}")
                self._shutdown_requested.set()
            finally:
                self._tasks.discard(t)

        task.add_done_callback(task_done)
        return task

    def broadcast(self, 
        message,
        exclude: Peer | None = None,
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

        for peer in target_peers:  #run coro threadsafe as broadcast is not async
            asyncio.run_coroutine_threadsafe(
                peer.send_message(message),
                self.loop
            )

    def remove_peer(self, peer: Peer):
        task = peer.listen_task
        if task and not task.done():
            task.cancel()
            
        self.peers.discard(peer)
        self.peer_id_lookup.pop(peer.session_id, None)
        self._updated_peers = 0
        
        log.info(f"[{peer.str_ip}] Peer No. {peer.session_id} disconnected.")

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
    
    def uptime(self) -> int:
        if self.server_start_time:
            return int(time.time()) - self.server_start_time
        else:
            return 0
