from typing import List, BinaryIO

from blockchain import transaction
from utils.helper import *
from crypto.hashing import *
from blockchain.transaction import *
from blockchain.merkle_tree import *

# GENESIS_BLOCK = bytes.fromhex("not created yet")
LOWEST_BITS = bytes.fromhex("ffff001e")  ## Minimum difficulty for mainnet
LOWEST_DIFFICULTY = 0xffff * pow(0xff, 0x1e - 3)

GENESIS_BLOCK_BYTES = b"TODO: insert genesis block here"
GENESIS_BLOCK_HASH = HASH256(GENESIS_BLOCK_BYTES)

class Block:
    """
    Represents a block.

    Attributes:
        version: 4 bytes-LE
        prev_block: 32 bytes-LE
        merkle_root: 32 bytes-LE
        timestamp = 4 bytes-LE
        bits = 4 bytes-LE
        nonce = Integer (mutable)
    """
    def __init__(
        self,
        version: int,
        prev_block: bytes,
        merkle_root: bytes,  ## 
        timestamp: int,
        bits: bytes,
        nonce: int,
        tx_hashes: List[bytes] = [],
    ):
        self.version: int = version
        self.prev_block: bytes = prev_block
        self.merkle_root: bytes = merkle_root
        self.timestamp: int = timestamp
        self.bits: bytes = bits
        self.nonce: int = nonce

        self.tx_hashes: List[bytes] = tx_hashes

        exponent = self.bits[-1]
        coeff = letoi(self.bits[:-1])
        self.target: int = coeff * pow(256, exponent - 3)

    def __str__(self):
        result = f"Block: {self.hash().hex()}\n"
        result += f"Version {self.version}\n"
        result += f"Previous Block: {self.prev_block.hex()}\n"
        result += f"Merkle Root: {self.merkle_root.hex()}\n"
        result += f"Timestamp: {self.timestamp}\n"
        result += f"Bits: {self.bits.hex()}\n"
        result += f"Nonce: {self.nonce}\n"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO, full_block: bool=False) -> 'Block':
        version = letoi(stream.read(4))
        prev_block = stream.read(32)[::-1]
        merkle_root = stream.read(32)[::-1]
        timestamp = letoi(stream.read(4))
        bits = stream.read(4)
        nonce = letoi(stream.read(4))

        if full_block:
            transactions: List[Transaction] = []
            no_transactions = read_varint(stream)
            for _ in range(no_transactions):
                transactions.append(Transaction.parse(stream))

            tx_hashes = [tx.hash() for tx in transactions]
            
        block = cls(version, prev_block, merkle_root, timestamp, bits, nonce, tx_hashes)
        return block
    
    def add_transaction_hash(self, tx_hash: bytes) -> None:
        self.tx_hashes.append(tx_hash)

    def serialize(self) -> bytes:
        """
        Serialized only the 80-byte block header
        """
        result: bytes = itole(self.version)
        result += self.prev_block
        result += self.merkle_root
        result += itole(self.timestamp)
        result += self.bits
        result += itole(self.nonce, num_bytes=4)
        return result

    def serialize_static(self) -> bytes:
        """
        Serialization without nonce for mining
        """
        return (itole(self.version) +
        self.prev_block +
        self.merkle_root +
        itole(self.timestamp) +
        self.bits)

    def hash(self) -> bytes:
        h = HASH256(self.serialize())[::-1]  # Convert TO LE
        return h

    def difficulty(self) -> int:
        return LOWEST_DIFFICULTY / self.target

    def check_proof_of_work(self) -> bool:
        this_hash = self.hash()
        return letoi(this_hash) < self.target

    def validate_merkle_root(self) -> bool:
        return MerkleTree(self.tx_hashes).get_merkle_root() == self.merkle_root
