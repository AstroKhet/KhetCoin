from typing import BinaryIO, List

from ktc_constants import GENESIS_HASH
from networking.constants import PROTOCOL_VERSION
from utils.helper import encode_varint, int_to_bytes, bytes_to_int, read_varint


class GetHeadersMessage:
    command = b"getheaders"
    def __init__(
        self, version: int = PROTOCOL_VERSION, 
        locator_hashes: List[bytes] = [GENESIS_HASH], 
        hash_stop: bytes = bytes(32)  # Zero by default
    ):
        self.version = version
        self.locator_hashes = locator_hashes
        self.hash_stop = hash_stop
        
        self.payload = int_to_bytes(self.version, 4) + encode_varint(len(locator_hashes))
        for h in locator_hashes:
            self.payload += h
        self.payload += self.hash_stop

    def __str__(self) -> str:
        result =  f"[GetHeaders] -> {self.payload.hex()}\n"
        result += f"\tVersion: {self.version}\n"
        result += f"\tLocator hashes ({len(self.locator_hashes)}x):\n"
        for i, h in enumerate(self.locator_hashes):
            result += f"\t\t{i}: <{h.hex()}>\n"
        result += f"\tHash stop: {self.hash_stop or 'Next 2000 blocks'}"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> "GetHeadersMessage":
        version = bytes_to_int(stream.read(4))
        count = read_varint(stream)
        locator_hashes = []
        for _ in range(count):
            locator_hashes.append(stream.read(32))
        hash_stop = stream.read(32)
        return cls(version, locator_hashes, hash_stop)
