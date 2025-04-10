import asyncio
from random import randint

from networking.messages.types.verack import VerackMessage
from networking.messages.types.version import VersionMessage
from utils.database import get_highest_block_height
from utils.helper import str_ip
from .messages.envelope import MessageEnvelope


class Peer:
    def __init__(
        self,
        node,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        name: str = "",
    ):
        self.name = name
        self.reader = reader
        self.writer = writer
        self.node = node
        self.addr = writer.get_extra_info("peername")

        self.str_ip = str_ip(self.addr[0])
        self.established = False

        # Futures for expected responses
        self._pong_future = None
        self._verack_future = None
        self._version_future = None

    async def initiate_handshake(self):
        nonce = randint(0, 2**64 - 1)
        version_message = VersionMessage(
            recver_ip=self.addr[0],
            recver_port=self.addr[1],
            sender_ip=self.node.host,
            sender_port=self.node.port,
            nonce=nonce,
            start_height=get_highest_block_height(),
        )

        version_envelope = MessageEnvelope(
            command=version_message.command,
            payload=version_message.payload,
        )

        self._verack_future = asyncio.get_event_loop().create_future()
        self._version_future = asyncio.get_event_loop().create_future()

        await self.send(version_envelope)

        try:
            await asyncio.wait_for(self._verack_future, timeout=5)
            print(f"Verack received from {self.str_ip}")
        except asyncio.TimeoutError:
            print(f"Handshake timeout waiting for verack from {self.str_ip}")
            return False

        try:
            version_response = await asyncio.wait_for(self._version_future, timeout=5)
        except asyncio.TimeoutError:
            print(f"Handshake timeout waiting for version from {self.str_ip}")
            return False

        if version_response.message.nonce == nonce:
            print("Likely self-connection, nonce matches.")
            return False

        verack = MessageEnvelope(b"verack", b"")
        await self.send(verack)
        return True

    async def respond_handshake(self):
        self._version_future = asyncio.get_event_loop().create_future()

        try:
            version_incoming = await asyncio.wait_for(self._version_future, timeout=5)
        except asyncio.TimeoutError:
            print(f"[{self.node.name}] Timeout waiting for Version from {self.str_ip}")
            return False
        


        verack = MessageEnvelope(b"verack", b"")
        await self.send(verack)

        self._verack_future = asyncio.get_event_loop().create_future()

        nonce = randint(0, 2**64 - 1)
        version_outgoing = VersionMessage(
            recver_ip=self.addr[0],
            recver_port=self.addr[1],
            sender_ip=self.node.host,
            sender_port=self.node.port,
            nonce=nonce,
            start_height=get_highest_block_height(),
        )
        await self.send(
            MessageEnvelope(version_outgoing.command, version_outgoing.payload)
        )

        try:
            await asyncio.wait_for(self._verack_future, timeout=5)
            return True
        except asyncio.TimeoutError:
            print(f"Handshake timeout waiting for verack from {self.str_ip}")
            return False

    async def ping(self):
        self._pong_future = asyncio.get_event_loop().create_future()
        await self.send(MessageEnvelope(b"ping", b""))

        try:
            await asyncio.wait_for(self._pong_future, timeout=5)
            print(f"Received pong from {self.str_ip}")
            return True
        except asyncio.TimeoutError:
            print(f"Ping timed out for {self.str_ip}")
            return False

    async def listen(self) -> None:
        try:
            while True:
                msg = await self.read_message()
                if msg is None:
                    break
                await self.handle_message(msg)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"Connection lost with {self.addr}")
            self.node.remove_peer(self)
            self.writer.close()
            await self.writer.wait_closed()

    async def handle_message(self, msg: MessageEnvelope):
        if msg.command == b"pong" and self._pong_future and not self._pong_future.done():
            self._pong_future.set_result(msg)
            return
        
        if msg.command == b"verack" and self._verack_future and not self._verack_future.done():
            self._verack_future.set_result(msg)
            return
        
        if msg.command == b"version" and self._version_future and not self._version_future.done():
            self._version_future.set_result(msg)
            return

        await self.node.processor_queue.put((self, msg))
        print(f"Message from {self.addr}: {msg}")

    async def read_message(self) -> MessageEnvelope | None:
        try:
            envelope = await MessageEnvelope.parse_async(self.reader)
            return envelope
        except RuntimeError as e:
            print(f"Error parsing message from {self.str_ip}: {e}")
            return None

    async def send(self, message: MessageEnvelope):
        try:
            self.writer.write(message.serialize())
            await self.writer.drain()
        except Exception as e:
            print(f"Error sending to {self.str_ip}: {e}")

    async def close(self):
        print(f"Closing connection to {self.str_ip}")
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            print(f"Error while closing connection to {self.addr}: {e}")
        finally:
            self.node.remove_peer(self)
