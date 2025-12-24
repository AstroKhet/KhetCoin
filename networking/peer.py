import asyncio
import logging
from random import randint
import time
from typing import List

from db.block import get_block_locator_hashes
from db.height import get_blockchain_height
from db.peers import set_last_seen
from networking.constants import PING_TIMEOUT, USER_AGENT
from networking.constants import PROTOCOL_VERSION, SERVICES
from networking.messages.envelope import MessageEnvelope
from networking.messages.types import *
from networking.messages.types import CORE_MESSAGES


log = logging.getLogger(__name__)

class Peer:
    def __init__(
        self,
        node,
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter,
        name: str = "",
        session_id = 0,
        direction = ""
    ):
        """
        An interface to communicate with a connected peer.
        
        Args:
            node: The node which this peer is connected to.
            reader: The asyncio.streamreader object for this peer.
            writer: The asyncio.streamwriter object for this peer.
            name: An optional, private name given to this peer by the node
            session_id: Internal number used to index peers in a session
            direction: Either "inbound" or "outbound" exactly.
        """
        self.node = node
        self.reader = reader
        self.writer = writer
        self.name = name
        
        self.addr = writer.get_extra_info("peername")
        self.ip: str = self.addr[0]
        self.port: int = self.addr[1]
        self.str_ip = f"{self.addr[0]}:{self.addr[1]}"

        # Session specific variables
        self.session_id: int = session_id
        self.direction = direction
        self.time_created: int = int(time.time())

        # Tracking
        self.last_block_timestamp: int = 0
        self.last_tx_timestamp: int = 0
        self.last_send_timestamp: int = 0
        self.last_recv_timestamp: int = 0

        self.bytes_recv: int = 0
        self.bytes_sent: int = 0

        # Ping / Latency tests
        self.time_offset = 0
        self.pong_future = asyncio.Future()
        self.latest_ping_time_ms = None
        self.ping_times: List[float] = []
        self.last_ping = 0
        self.ping()

        # Variables derived after handshake
        self.version: int = 0
        self.services: int = 0
        self.user_agent: bytes = b""
        self.height: int = 0
        self.relay: bool = False

        # asyncio variables
        self.established = asyncio.Future()
        self.listen_task: asyncio.Task | None = None
        log.debug(f"[{self.str_ip}] Peer object created.")

    async def read_message(self) -> MessageEnvelope | None:
        try:
            envelope = await MessageEnvelope.parse_async(self.reader)

            # accounting
            self.bytes_recv += envelope.payload_size
            self.node.bytes_recv += envelope.payload_size
            self.last_recv_timestamp = int(time.time())

            if isinstance(envelope.message, BlockMessage):
                self.last_block_timestamp = self.last_recv_timestamp
            elif isinstance(envelope.message, TxMessage):
                self.last_tx_timestamp = self.last_recv_timestamp

            log.debug(
                f"[{self.str_ip}] Received {type(envelope.message).__name__}"
            )
            return envelope

        except (
            asyncio.IncompleteReadError,
            ConnectionResetError,
            ConnectionAbortedError,
            EOFError,
        ) as e:
            log.info(f"[{self.str_ip}] Peer disconnected ({type(e).__name__})")
            return None

        except asyncio.CancelledError:
            log.debug(f"[{self.str_ip}] read_message cancelled")
            return None

        except ValueError as e:
            log.warning(f"[{self.str_ip}] Protocol error: {e}. Dropping peer.")
            return None

        except Exception:
            log.exception(f"[{self.str_ip}] Unexpected error in read_message")
            return None


    async def send_message(self, msg):
        """Sends `msg` to this peer"""
        if isinstance(msg, CORE_MESSAGES):
            envelope = MessageEnvelope(msg)
        else:
            envelope = msg
   
        
        cmd = envelope.command.decode("ascii", errors="replace")
        serialized_envelope = envelope.serialize()
        log.info(f"[{self.str_ip}] Sending message: {cmd} ({len(serialized_envelope)} bytes)")

        try:
            print("SEND", type(envelope.message))
            self.writer.write(serialized_envelope)
            await self.writer.drain()

            # Tracking
            self.bytes_sent += len(serialized_envelope)
            self.node.bytes_sent += len(serialized_envelope)
            self.last_send_timestamp = int(time.time())

            log.info(f"[{self.str_ip}] Sent message: {cmd} ({len(serialized_envelope)} bytes)\n{envelope}")
        except Exception as e:
            log.exception(f"[{self.str_ip}] {type(e).__name__}: Error sending message '{cmd}': {e}")
            await self.close()

    async def send_version(self):
        log.debug(f"[{self.str_ip}] Preparing to send version message...")

        version_message = VersionMessage(
            version=PROTOCOL_VERSION,
            services=SERVICES,
            recver_ip=self.addr[0],
            recver_port=self.addr[1],
            sender_ip=self.node.external_ip,
            sender_port=self.node.port,
            nonce=randint(0, (1 << 64) - 1),
            start_height=get_blockchain_height(),
            user_agent=USER_AGENT
        )

        await self.send_message(version_message)
    
    async def send_getblocks(self):
        await self.send_message(
            GetBlocksMessage(
                PROTOCOL_VERSION,
                locator_hashes=get_block_locator_hashes(),
                hash_stop=bytes(32)                             
            )
        )
        
    async def listen(self) -> None:
        while True:
            if self.reader.at_eof():
                log.warning(f"[{self.str_ip}] Reader at EOF. Stopping listener.")
                break
            
            envelope = await self.read_message()
            if envelope is None:
                self.close()

            try:
                await self.node.msg_processor_queue.put((self, envelope))
            except Exception as e:
                log.error(f"[{self.str_ip}] Error putting message onto queue: {e}. Stopping listener.")
                break

        log.info(f"[{self.str_ip}] Listener task stopped.")
        await self.close()

    async def close(self):
        log.info(f"[{self.str_ip}] Closing connection")

        try:
            if self.last_recv_timestamp:
                await set_last_seen(self.ip, self.port, self.last_recv_timestamp)

            self.writer.close()
            await self.writer.wait_closed()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.debug(f"[{self.str_ip}] Error during close (ignored): {e}")
        finally:
            self.node.remove_peer(self)

        
    def ping(self):
        self.node.spawn(self._ping_task())

    async def _ping_task(self) -> None:  # Creates a ping task
        # Reset pong_future
        if self.pong_future.done():
            self.pong_future = asyncio.Future()

        time_ping_sent = time.time() 
        self.last_ping = int(time.time())
        await self.send_message(PingMessage())
        
        try:
            time_pong_received = await asyncio.wait_for(self.pong_future, timeout=PING_TIMEOUT)
        except asyncio.TimeoutError:
            log.info(f"[{self.str_ip}] No pong message received within {PING_TIMEOUT}s after pinging. Disconnecting peer...")
            await self.close()
            return
        self.latest_ping_time_ms = int((time_pong_received - time_ping_sent) * 1000)
        self.ping_times.append(self.latest_ping_time_ms)

    @property
    def connection_time(self) -> int:
        return int(time.time()) - self.time_created

    @property
    def last_block_ago(self) -> int | None:
        "Returns how long ago this node sent a block"
        return int(time.time()) - self.last_block_timestamp

    @property
    def last_tx_ago(self) -> int | None:
        """Returns how long ago this node sent a tx"""
        return int(time.time()) - self.last_tx_timestamp

    @property
    def last_send_ago(self) -> int | None:  # Last time YOU sent to PEER
        """Returns how long ago you sent a message from this peer"""
        return int(time.time()) - self.last_send_timestamp

    @property
    def last_recv_ago(self) -> int | None:  # Last time PEER sent to YOU
        """Returns how long ago you received a message from this peer"""
        return int(time.time()) - self.last_recv_timestamp

    def __hash__(self):
        return self.session_id

    def __eq__(self, other: 'Peer'):
        return hash(self) == hash(other)
