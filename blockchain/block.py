from math import floor

import time
import logging
from typing import List, BinaryIO
from io import BytesIO

from db.block import get_block_height_at_hash
from utils.helper import bits_to_target, bytes_to_int, read_varint, encode_varint
from blockchain.header import Header
from blockchain.transaction import Transaction
from blockchain.merkle_tree import MerkleTree

from ktc_constants import HALVING_INTERVAL, INITIAL_BLOCK_REWARD, MAX_BLOCK_SIZE, HIGHEST_TARGET

log = logging.getLogger(__name__)

class Block:
    def __init__(
        self,
        version: int,
        prev_block: bytes,
        timestamp: int,
        bits: bytes,
        nonce: int,
        txs: List[Transaction] = [],
    ):
        self.version: int = version
        self.prev_block: bytes = prev_block
        self.timestamp: int = timestamp
        self.bits: bytes = bits
        self.nonce: int = nonce

        self._transactions: List[Transaction] = txs
        self._tx_hashes: List[bytes] = [tx.hash() for tx in txs]        
        self.merkle_tree = MerkleTree(self._tx_hashes)
        self.target: int = bits_to_target(bits)
        
        self.header = Header(version, prev_block, self.merkle_tree.root(), timestamp, bits, nonce)
        
        
    def __str__(self):
        lines = [
            "========== BLOCK ==========",
            str(self.header),
            "",
            f"Transactions ({len(self._transactions)}):",
        ]

        for i, tx in enumerate(self._transactions):
            lines.append(f"\n--- Transaction {i} ---")
            lines.append(str(tx))

        lines.append("\n===========================")
        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO | bytes) -> 'Block':
        """Parses a full block. Use `Header` class otherwise."""
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
            
        version = bytes_to_int(stream.read(4))
        prev_block = stream.read(32)
        merkle_root = stream.read(32)
        timestamp = bytes_to_int(stream.read(4))
        bits = stream.read(4)
        nonce = bytes_to_int(stream.read(4))
        transactions: List[Transaction] = []
        
        no_transactions = read_varint(stream)
        for _ in range(no_transactions):
            transactions.append(Transaction.parse(stream))
        
        block = cls(version, prev_block, timestamp, bits, nonce, transactions)
        return block

    def add_tx(self, tx: Transaction):
        """Appends a transaction object to the block.
        \nCoinbase transactions will be inserted at index 0.
        """
        tx_hash = tx.hash()
        if tx.is_coinbase():
            log.warning("Use Block.set_coinbase_tx for coinbase transactions instead. Automatically calling set_coinbase_tx...")
            self.set_coinbase_tx(tx)
            return
        else:
            self._transactions.add(tx)
            self._tx_hashes.append(tx_hash)
            self.merkle_tree.append_leaf(tx_hash)
        
        self.header.merkle_root = self.merkle_tree.root()
    
    def set_coinbase_tx(self, cb_tx: Transaction):
        """If the block already has a coinbase transaction, replaces it with `cb_tx`. 
        \nOtherwise, insert a `cb_tx` at position 0 of self._transactions"""
        
        if not cb_tx.is_coinbase():
            log.warning("Non coinbase transaction cannot be used with Block.set_coinbase_tx")
            return
        
        tx_hash = cb_tx.hash()
        
        if self._transactions and self._transactions[0].is_coinbase():
            # Remove existing coinbase transaction
            self._transactions.pop(0)
            self._tx_hashes.pop(0)
        
        self._transactions.insert(0, cb_tx)
        self._tx_hashes.insert(0, tx_hash)
        self.merkle_tree = MerkleTree(self._tx_hashes)  # Recreate merkle tree

        self.header.merkle_root = self.merkle_tree.root()
    
    def set_nonce(self, nonce: int):
        self.nonce = nonce
        self.header.nonce = nonce
         
    def get_transactions(self):
        return self._transactions
    
    def get_tx_hashes(self):
        return self._tx_hashes
    
    def get_header(self):
        return self.header
        
    
    def serialize(self) -> bytes:
        if self._transactions == []:
            log.warning("Attempted to serialized empty block.")
        
        result = self.header.serialize()
        result += encode_varint(len(self._transactions))
        for tx in self._transactions:
            result += tx.serialize()
            
        return result

    def hash(self) -> bytes:
        return self.header.hash()

    def difficulty(self) -> int:
        return HIGHEST_TARGET / self.target

    def work(self) -> int:
        return floor((1 << 256) / (self.target + 1))
    
    def check_proof_of_work(self) -> bool:
        return bytes_to_int(self.hash()) < self.target

    def verify(self, full=True) -> bool:
        # Full means verify a block with all its transactions
        # Otherwise we are just validating a header
        log.info(f"Verifying Block<{self.hash()}>...")

        # TODO enforce block target checks
        if not self.check_proof_of_work():
            log.warning("Invalid proof of work.")
            return False

        # TODO: enforce MTP checks
        if self.timestamp > time.time() + 3600 * 2:
            log.warning("Timestamp invalid: Too far into the future!")
            return False

        if self.size() > MAX_BLOCK_SIZE:
            log.warning(f"Block size exceeds {MAX_BLOCK_SIZE}B")
            return False

        if full:
            log.info("Header validated. Verifying transactions...")
            mtree = MerkleTree(self._tx_hashes)
            if mtree.root()!= self.merkle_tree.root():  # LE
                log.warning("Calculated merkle root mismatch")
                return False

            # Verify that there exists only 1 coinbase transaction
            coinbase_tx = self._transactions[0]
            if (not coinbase_tx.is_coinbase()):
                log.warning("First transaction is not a coinbase transaction.")
                return False

            if any(tx.is_coinbase() for tx in self._transactions[1:]):
                log.warning("Coinbase transaction should only be in first transaction")
                return False

            # Verify coinbase reward
            height = get_block_height_at_hash(self.prev_block)
            if height is None:
                log.warning("Previous block is not saved locally or does not exist at all.")
                return False
            height += 1

            block_subsidy = calculate_block_subsidy(height)
            fees = sum(tx.fee() for tx in self._transactions)
            block_reward = sum(out.value for out in coinbase_tx.outputs)

            if block_reward > block_subsidy + fees:
                log.warning("block_reward > block_subsidy + fees")
                return False

            if not all(tx.verify() for tx in self._transactions):
                log.warning("Invalid transaction in block")
                return False
        else:
            log.warning("Full block requried for block verification!")
            return False

        return True

    def size(self):
        return len(self.serialize())
    
    def get_miner_tag(self) -> str | None:
        # Assume this function is only called for actual blocks i.e. one cb transaction at the start.
        try:
            cb_tx = self._transactions[0]
            cb_script_sig = cb_tx.inputs[0].script_sig
            tag = cb_script_sig.commands[2].decode("utf-8")
            return tag
        except:
            return None
    
    def get_height(self) -> int | None:
        "Determines block height from script sig. May not be accurate."
        try:
            cb_tx = self._transactions[0]
            cb_script_sig = cb_tx.inputs[0].script_sig
            height_bytes = cb_script_sig.commands[0]
            if len(height_bytes) != 8:
                raise
            height = bytes_to_int(height_bytes)
            return height
        except:
            return None
            
    @property
    def merkle_root(self):
        return self.merkle_tree.root()
    
    def __hash__(self):
        return self.hash()
    
    def __eq__(self, other):
        return self.hash() == other.hash()

# Auxillary functions

def calculate_block_subsidy(height: int) -> int:
    return INITIAL_BLOCK_REWARD >> floor(height/HALVING_INTERVAL)





