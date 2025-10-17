import asyncio
import logging
import random
import time
from typing import Optional, Set, Tuple

from crypto.hashing import HASH160
from crypto.key import get_public_key
from utils.helper import str_ip
from ktc_constants import MAX_PEERS

from networking.constants import CONNECTION_TIMEOUT, HANDSHAKE_TIMEOUT
from networking.messages.envelope import MessageEnvelope
from networking.peer import Peer
from networking.processor import MessageProcessor

from mining.mempool import Mempool
from db.peers import load_peers


log = logging.getLogger(__name__)


class Node:
    def __init__(self, name: str, host: str = "0.0.0.0", port: int = 9333):
        self.name = name
        self.host = host
        self.port = port
        self.peers: Set[Peer] = set()
        self.pk_hash: bytes = HASH160(get_public_key(name, raw=True))

        # Self (server)
        self.server: asyncio.Server | None = None
        self.server_start_time: int = 0
        self.mempool = Mempool()

        # Clients (peers)
        self.peer_id: int = 0
        self.bytes_recv: int = 0
        self.bytes_sent: int = 0

        # Async variables
        self.processor = MessageProcessor(self)
        self.processor_queue: asyncio.Queue[Tuple[Peer, MessageEnvelope]] = asyncio.Queue()  # For db write serialization

        self._shutdown_requested = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()

        log.info(f"Node '{self.name}' initialized on {self.host}:{self.port}")

    async def start_server(self):
        try:
            self.server = await asyncio.start_server(
                self._handle_incoming_connection, self.host, self.port
            )
            addr = self.server.sockets[0].getsockname()
            self.server_start_time = int(time.time())

            log.info(f"[{self.name}] Server listening on {addr}")
        except Exception as e:
            log.exception(f"[{self.name}] Error starting server: {e}")
            self.server = None
            self._shutdown_requested.set()

    async def close_server(self):
        awaitables = []

        if self.server:
            log.debug("Closing server...")
            self.server.close()
            self.server = None

        tasks_to_cancel = list(self._tasks)
        self._tasks.clear()

        peers_to_close = list(self.peers)
        self.peers.clear()

        for peer in peers_to_close:
            awaitables.append(peer.close())

        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
            awaitables.append(task)

        if awaitables:
            await asyncio.gather(*awaitables, return_exceptions=True)

        self.server_start_time = 0

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

        peer_rotation_task = asyncio.create_task(self._peer_rotation())
        self.add_task(peer_rotation_task)

        log.info(f"[{self.name}] Node running. Waiting for shutdown signal...")
        await self._shutdown_requested.wait()

        log.info(f"[{self.name}] Shutdown requested. Cleaning up...")
        await self._shutdown_tasks()
        log.info(f"[{self.name}] Node finished.")

    async def connect_to_peer(self, addr: tuple, name: str = ""):
        peer_str_ip = str_ip(addr, name)
        if len(self.peers) >= MAX_PEERS:
            return

        log.info(f"[{self.name}] Attempting TCP connection to {peer_str_ip}...")
        reader, writer = None, None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(addr[0], addr[1]), timeout=CONNECTION_TIMEOUT
            )
            log.info(f"[{self.name}] TCP connection established with {peer_str_ip}. Starting handshake...")
        except Exception as e:
            log.exception(f"[{self.name}] Unexpected error connecting TCP to {peer_str_ip}: {e}")
            return

        peer = Peer(self, reader, writer, name, session_id=self.peer_id, direction="outbound")
        self.peer_id += 1
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
            else:
                log.warning(f"[{self.name}] Handshake failed with peer {peer.str_ip}.")
        except Exception as e:
            log.exception(f"[{self.name}] Error during handshake with peer {peer.str_ip}: {e}")
            await peer.close()

    def broadcast(self, 
        message: MessageEnvelope, 
        exclude: Optional[Peer] = None,
        sample: int = MAX_PEERS,
        outbound: bool = False
    ):
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
            self.add_task(
                asyncio.create_task(peer.send_message(message))
            )

    async def _handle_incoming_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        # Get peer address
        peer_addr_info = writer.get_extra_info("peername", ("Unknown", 0))
        peer_str_ip = str_ip(peer_addr_info)
        log.debug(f"[{self.name}] Handling incoming connection from {peer_str_ip}")

        # Check if its possible to connect with peer
        if len(self.peers) >= MAX_PEERS:
            writer.close()
            await writer.wait_closed()
            return

        if any(p.addr == peer_addr_info for p in self.peers):
            writer.close()
            await writer.wait_closed()
            return

        # Create peer object
        peer = Peer(self, reader, writer, session_id=self.peer_id, direction="inbound")
        self.peer_id += 1

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
                f"[{self.name}] Waiting for handshake established future from {peer.str_ip}..."
            )
            established = await asyncio.wait_for(
                peer.established, timeout=HANDSHAKE_TIMEOUT
            )
            if established:
                log.info(
                    f"[{self.name}] Handshake successful with incoming peer {peer.str_ip}. Adding to peers."
                )
                self.peers.add(peer)
            else:
                log.warning(
                    f"[{self.name}] Handshake failed or rejected by incoming peer {peer.str_ip} (established=False)."
                )
        except Exception as e:
            log.exception(
                f"[{self.name}] Error during handshake with incoming peer {peer.str_ip}: {e}"
            )
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
        peers_to_connect = await load_peers()
        if not peers_to_connect:
            return 

        for ip, port, name, *_ in peers_to_connect:
            self.add_task(
                asyncio.create_task(
                    self.connect_to_peer((ip, port), name)
                )
            )

    async def _peer_rotation(self):
        log.info("Rotating task started")
        # periodically removes inactive peers and rotates active ones
        return

    def add_task(self, task: asyncio.Task):
        def task_done(task: asyncio.Task):
            try:
                task.result()  # This re-raises if the task had an exception
            except Exception as e:
                log.error(f"Task failed: {e}")
            finally:
                self._tasks.discard(task)

        self._tasks.add(task)
        task.add_done_callback(task_done)

    async def shutdown(self):
        log.info(f"[{self.name}] External shutdown triggered.")
        self._shutdown_requested.set()

    async def _shutdown_tasks(self):
        await self.close_server()

    def remove_peer(self, peer: Peer):
        self.peers.discard(peer)

    def get_peer_by_id(self, peer_id: int) -> Peer | None:
        for peer in self.peers:
            if peer.session_id == peer_id:
                return peer
        else:
            return None

    @property
    def uptime(self) -> int:
        if self.server_start_time:
            return int(time.time()) - self.server_start_time
        else:
            return 0

    @property
    def public_ip_addr(self) -> str:
        from requests import get
        return get("https://api.ipify.org").content.decode("utf8")
