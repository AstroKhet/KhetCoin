from typing import BinaryIO, List

from networking.constants import PROTOCOL_VERSION
from utils.helper import itole, letoi


class GetBlocksMessage:
    command = b"getblocks"
    def __init__(self, version: int = PROTOCOL_VERSION, locator_hashes: List[bytes] = [], hash_stop: bytes = None):
        self.version = version
        self.locator_hashes = locator_hashes
        self.hash_stop = hash_stop
        self.payload = itole(PROTOCOL_VERSION, 4)
        self.payload += itole(len(locator_hashes), 1)
        for hash in locator_hashes:
            self.payload += hash
        self.payload += hash_stop
        
    def __str__(self):
        lines = ["getblocks"]
        
        for i, hash in enumerate(self.locator_hashes):
            lines.append(f"  Locator hash {i}: {hash.hex()}")
            
        lines.append(f"  Hash stop: {self.hash_stop.hex() or 'Next 2000 blocks'}")
        
        return "\n".join(lines)
    
    @classmethod
    def parse(cls, stream: BinaryIO) -> "GetBlocksMessage":
        version = letoi(stream.read(4))
        count = letoi(stream.read(1))
        locator_hashes = [stream.read(32) for _ in range(count)]
        hash_stop = stream.read(32)
        return cls(version, locator_hashes, hash_stop)
    