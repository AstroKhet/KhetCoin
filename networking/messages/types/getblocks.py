from typing import BinaryIO, List

from networking.constants import PROTOCOL_VERSION
from utils.helper import encode_varint, int_to_bytes, bytes_to_int


class GetBlocksMessage:
    command = b"getblocks"
    def __init__(self, 
            version: int = PROTOCOL_VERSION,
            locator_hashes: List[bytes] = [],
            hash_stop: bytes = bytes(32)
        ):
        self.version = version
        self.locator_hashes = locator_hashes
        self.hash_stop = hash_stop
        
        self.payload = int_to_bytes(PROTOCOL_VERSION, 4)
        self.payload += encode_varint(len(locator_hashes))
        for hash in locator_hashes:
            self.payload += hash
        self.payload += hash_stop
        
    def __str__(self):
        lines = ["[getblocks]"]
        
        for i, hash in enumerate(self.locator_hashes):
            lines.append(f"  Locator hash {i}: {hash.hex()}")
            
        lines.append(f"  Hash stop: {self.hash_stop.hex()}")
        
        return "\n".join(lines)
    
    @classmethod
    def parse(cls, stream: BinaryIO) -> "GetBlocksMessage":
        version = bytes_to_int(stream.read(4))
        count = bytes_to_int(stream.read(1))
        locator_hashes = [stream.read(32) for _ in range(count)]
        hash_stop = stream.read(32)
        return cls(version, locator_hashes, hash_stop)
    