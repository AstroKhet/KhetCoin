import asyncio
import logging
from random import randint
import time
from typing import List

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

        # TODO Status flags
        ## Might need this to flag that I am awaiting for continuous data from this peer
        ## i.e. block with n txs -> tx1 -> tx2 -> ... -> tx
        
        # Tracking
        ## Timestamps in miliseconds
        self._last_block: int | None = None
        self._last_tx: int | None = None
        self._last_send_timestamp: int | None = None
        self._last_recv_timestamp: int | None = None

        self.bytes_recv: int = 0
        self.bytes_sent: int = 0

        # Ping / Latency tests
        self.time_offset = 0
        self.pong_future = asyncio.Future()
        self.latest_ping_time = None
        self.ping_times: List[float] = []
        self.ping()

        # Variables derived after handshake
        self.version: int = 0
        self.services: int = 0
        self.user_agent: bytes = b""
        self.start_height: int = 0
        self.relay: bool = False

        # asyncio variables
        self.established = asyncio.Future()
        self.listen_task: asyncio.Task | None = None
        log.debug(f"[{self.str_ip}] Peer object created.")

    async def read_message(self) -> MessageEnvelope | None:
        try:
            envelope = await MessageEnvelope.parse_async(self.reader)

            log.info(f"[{self.str_ip}] Received message: {envelope.command.decode('ascii', errors='replace')}")
            return envelope
        except ValueError:
            return None
        except (asyncio.IncompleteReadError, ConnectionResetError, EOFError) as e:
            log.warning(f"[{self.str_ip}] Connection closed: {type(e).__name__}")
            await self.close()
            return None
        except Exception as e:
            log.exception(f"[{self.str_ip}] Unexpected error: {e}")
            await self.close()
            return None

    async def send_message(self, msg):
        """Sends `msg` to this peer"""
        if isinstance(msg, MessageEnvelope):
            envelope = msg
        elif isinstance(msg, CORE_MESSAGES):
            envelope = MessageEnvelope(msg.command, msg.payload)
        else:  # Should not happen unless you messed with the source code
            log.exception(f"Attempted to send invalid message type: {type(msg)}")
            return 
        
        cmd = envelope.command.decode("ascii", errors="replace")
        log.info(f"[{self.str_ip}] Sending message: {msg.command}")

        try:
            serialized_envelope = envelope.serialize()
            self.writer.write(serialized_envelope)
            await self.writer.drain()

            # Tracking
            self.bytes_sent += len(serialized_envelope)
            self.node.bytes_sent += len(serialized_envelope)
            self._last_send_timestamp = int(time.time())
            if isinstance(envelope.message, BlockMessage):
                self._last_block = self._last_send_timestamp
            elif isinstance(envelope.message, TxMessage):
                self._last_tx = self._last_send_timestamp

            log.info(f"[{self.str_ip}] Sent message: {cmd} ({len(serialized_envelope)} bytes)")
        except Exception as e:
            log.exception(f"[{self.str_ip}] {type(e).__name__}: Error sending message '{cmd}': {e}")
            await self.close()

    async def send_version(self):
        log.debug(f"[{self.str_ip}] Preparing to send version message...")

        nonce = randint(0, (1 << 64) - 1)
        start_height = get_blockchain_height()

        version_message = VersionMessage(
            version=PROTOCOL_VERSION,
            services=SERVICES,
            recver_ip=self.addr[0],
            recver_port=self.addr[1],
            sender_ip=self.node.external_ip,
            sender_port=self.node.port,
            nonce=nonce,
            start_height=start_height,
            user_agent=USER_AGENT
        )

        version_envelopeelope = MessageEnvelope(
            command=version_message.command,
            payload=version_message.payload,
        )
        await self.send_message(version_envelopeelope)

    async def listen(self) -> None:
        while True:
            if self.reader.at_eof():
                log.warning(f"[{self.str_ip}] Reader at EOF. Stopping listener.")
                break
            
            envelope = await self.read_message()
            if envelope is None:
                continue
                # log.warning(f"[{self.str_ip}] Read None message. Stopping listener.")
                # break

            self.bytes_recv += envelope.payload_size
            self.node.bytes_recv += envelope.payload_size
            self._last_recv_timestamp = int(time.time())
            await set_last_seen(self.ip, self.port, self._last_recv_timestamp)

            if isinstance(envelope.message, BlockMessage):
                self._last_block = self._last_recv_timestamp
            elif isinstance(envelope.message, TxMessage):
                self._last_tx = self._last_recv_timestamp

            try:
                await self.node.processor_queue.put((self, envelope))
            except Exception as e:
                log.error(
                    f"[{self.str_ip}] Error putting message onto queue: {e}. Stopping listener."
                )
                break

        log.info(f"[{self.str_ip}] Listener task stopped.")
        await self.close()

    async def close(self):
        log.info(f"[{self.str_ip}] Closing connection...")
        if self.listen_task and not self.listen_task.done():
            log.debug(f"[{self.str_ip}] Cancelling listen task.")
            self.listen_task.cancel()

        try:
            self.writer.close()
            await self.writer.wait_closed()
            log.debug(f"[{self.str_ip}] Writer closed.")
        except Exception as e:
            log.warning(f"[{self.str_ip}] Error closing writer; peer might have had an ungraceful shutdown.\n{e}")
        finally:
            self.node.remove_peer(self) 
        
    def ping(self):
        task = asyncio.create_task(self._ping_task())
        self.node.add_task(task)

    async def _ping_task(self) -> None:  # Creates a ping task
        # Reset pong_future
        if self.pong_future.done():
            self.pong_future = asyncio.Future()

        ping_msg = PingMessage()
        envelope = MessageEnvelope(command=ping_msg.command, payload=ping_msg.payload)

        time_ping_sent = time.time() 
        await self.send_message(envelope)

        time_pong_received = await asyncio.wait_for(self.pong_future, timeout=PING_TIMEOUT)
        self.latest_ping_time = int((time_pong_received - time_ping_sent) * 1000)
        self.ping_times.append(self.latest_ping_time)

    @property
    def connection_time(self) -> int:
        return int(time.time()) - self.time_created

    @property
    def last_block(self) -> int | None:
        if self._last_block:
            return int(time.time()) - self._last_block
        return None

    @property
    def last_tx(self) -> int | None:
        if self._last_tx:
            return int(time.time()) - self._last_tx
        return None

    @property
    def last_send(self) -> int | None:  # Last time YOU sent to PEER
        if self._last_send_timestamp:
            return int(time.time()) - self._last_send_timestamp
        return None

    @property
    def last_recv(self) -> int | None:  # Last time PEER sent to YOU
        if self._last_recv_timestamp:
            return int(time.time()) - self._last_recv_timestamp
        return None

    def __hash__(self):
        return self.session_id

    def __eq__(self, other: 'Peer'):
        return hash(self) == hash(other)
