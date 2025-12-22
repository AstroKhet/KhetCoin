import asyncio
from io import BytesIO
import logging
from typing import BinaryIO
from crypto.hashing import HASH256
from networking.constants import NETWORK_MAGIC
from networking.messages.types import COMMAND_MAP
from utils.helper import int_to_bytes, bytes_to_int

log = logging.getLogger(__name__)

class MessageEnvelope:
    def __init__(self, message):
        self.command = message.command.strip(b"\x00")
        self.payload = message.payload

        message_class = COMMAND_MAP.get(self.command)
        if not message_class:
            log.warning(f"Received message with unknown command!: {self.command.decode('ascii')}")
            raise ValueError

        self.message = message_class.parse(self.payload_stream)

    def __str__(self):
        result = f"{self.message}\n"
        result += f"Length: {len(self.payload)}\n"
        result += f"Checksum: {HASH256(self.payload)[:4].hex()}\n"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> "MessageEnvelope":
        magic = stream.read(4)
        if magic != NETWORK_MAGIC:
            raise RuntimeError("Invalid network magic")

        command = stream.read(12).strip(b"\x00")
        len_payload = bytes_to_int(stream.read(4))
        checksum = stream.read(4)
        payload = stream.read(len_payload)

        if HASH256(payload)[:4] != checksum:
            raise RuntimeError("Checksum mismatch")

        return cls(command, payload)

    @classmethod
    async def parse_async(cls, reader: asyncio.StreamReader) -> "MessageEnvelope":
        magic = await reader.readexactly(4)
        if not magic:
            #TODO: Handle ConnectionResetError
            raise EOFError("Peer disconnected")
        if magic != NETWORK_MAGIC:
            raise RuntimeError("Invalid network magic")

        command = await reader.readexactly(12)
        command = command.strip(b"\x00")
        len_payload = bytes_to_int(await reader.readexactly(4))
        checksum = await reader.readexactly(4)
        payload = await reader.readexactly(len_payload)

        if HASH256(payload)[:4] != checksum:
            raise RuntimeError("Checksum mismatch")

        return cls(command, payload)
    
    def serialize(self) -> bytes:
        result: bytes = NETWORK_MAGIC
        result += self.command.ljust(12, b"\x00")
        result += int_to_bytes(len(self.payload), 4)
        result += HASH256(self.payload)[:4]  # checksum
        result += self.payload
        return result

    @property
    def payload_stream(self):
        return BytesIO(self.payload)
    
    
    @property 
    def payload_size(self) -> int:
        return len(self.serialize())
