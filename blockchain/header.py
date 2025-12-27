



from io import BytesIO
from typing import BinaryIO

from crypto.hashing import HASH256
from utils.helper import bytes_to_int, int_to_bytes


class Header:
    def __init__(
        self,
        version: int,
        prev_block: bytes,
        merkle_root: bytes,
        timestamp: int,
        bits: bytes,
        nonce: int,
    ):
        self.version: int = version
        self.prev_block: bytes = prev_block
        self.merkle_root: bytes = merkle_root
        self.timestamp: int = timestamp
        self.bits: bytes = bits
        self.nonce: int = nonce
    
    def __str__(self) -> str:
        result = f"Block Hash: {self.hash().hex()}\n"
        result += f"Version {self.version}\n"
        result += f"Previous Block: {self.prev_block.hex()}\n"
        result += f"Merkle Root: {self.merkle_root.hex()}\n"
        result += f"Timestamp: {self.timestamp}\n"
        result += f"Bits: {self.bits.hex()}\n"
        result += f"Nonce: {self.nonce}\n"
        
        return result
    @classmethod
    def parse(cls, stream: BinaryIO | bytes) -> 'Header':
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
            
        version = bytes_to_int(stream.read(4))
        prev_block = stream.read(32)
        merkle_root = stream.read(32) 
        timestamp = bytes_to_int(stream.read(4))
        bits = stream.read(4)
        nonce = bytes_to_int(stream.read(4))

        header = cls(version, prev_block, merkle_root, timestamp, bits, nonce)
        return header
    
    def serialize(self) -> bytes:
        result: bytes = int_to_bytes(self.version)
        result += self.prev_block
        result += self.merkle_root
        result += int_to_bytes(self.timestamp)
        result += self.bits
        result += int_to_bytes(self.nonce)

        return result
    
    def set_merkle_root(self, root):
        self.merkle_root = root

    def hash(self) -> bytes:
        return HASH256(self.serialize())
    
    # Methods specific for mining
    def serialize_without_nonce(self):
        return self.serialize()[:76]
    
    def copy(self):
        return Header(self.version, self.prev_block, self.merkle_root, self.timestamp, self.bits, self.nonce)
    