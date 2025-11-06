from math import floor
import os
import time
from typing import List, BinaryIO

from db.block import get_blk_dat_no, get_block_at_height, get_block_height_at_hash, get_block_timestamp
from db.constants import BLOCK_MAGIC, BLOCKS_DB, DAT_SIZE, HEIGHT_DB, TX_DB, UTXO_DB
from utils.helper import *
from utils.config import APP_CONFIG
from crypto.hashing import *
from blockchain.transaction import *
from blockchain.merkle_tree import *

from ktc_constants import HALVING_INTERVAL, INITIAL_BLOCK_REWARD, MIN_DIFFICULTY

class Block:
    def __init__(
        self,
        version: int,
        prev_block: bytes,
        merkle_root: bytes,
        timestamp: int,
        bits: bytes,
        nonce: int,
        transactions: List[Transaction] = [],
        tx_hashes: List[bytes] = []
    ):
        self.version: int = version
        self.prev_block: bytes = prev_block
        self.merkle_root: bytes = merkle_root
        self.timestamp: int = timestamp
        self.bits: bytes = bits
        self.nonce: int = nonce

        self.tx_hashes: List[bytes] = tx_hashes
        # Do something about this separation
        self.transactions: List[Transaction] = transactions

        coeff = bytes_to_int(bits[:3])
        exponent = bits[-1]
        self.target: int = coeff * pow(256, exponent - 3)

        self._serialize_cache = None

    def __setattr__(self, name, value) -> None:
        if name != "_serialize_cache":
            self._serialize_cache = None
        super().__setattr__(name, value)

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
        version = bytes_to_int(stream.read(4))
        prev_block = stream.read(32)
        merkle_root = stream.read(32)
        timestamp = bytes_to_int(stream.read(4))
        bits = stream.read(4)
        nonce = bytes_to_int(stream.read(4))

        if full_block:
            transactions: List[Transaction] = []
            no_transactions = read_varint(stream)
            for _ in range(no_transactions):
                transactions.append(Transaction.parse(stream))

            tx_hashes = [tx.hash() for tx in transactions]
            
            block = cls(
                version, prev_block, merkle_root, timestamp, bits, nonce, transactions, tx_hashes
            )
            
        
        else:
            block = cls(version, prev_block, merkle_root, timestamp, bits, nonce, tx_hashes=[])
        return block

    @classmethod
    def parse_static(cls, stream: bytes, full_block: bool=False) -> 'Block':
        """
        Parses a block from static bytes
        """
        return cls.parse(BytesIO(stream), full_block)

    def add_transaction_hash(self, tx_hash: bytes) -> None:
        self.tx_hashes.append(tx_hash)
        self._serialize_cache = None

    def header(self) -> bytes:
        """
        Serialized only the 80-byte block header
        """
        if self._serialize_cache:
            return self._serialize_cache

        result: bytes = int_to_bytes(self.version)
        result += self.prev_block
        result += self.merkle_root
        result += int_to_bytes(self.timestamp)
        result += self.bits
        result += int_to_bytes(self.nonce)

        self._serialize_cache = result
        return result

    def header_without_nonce(self) -> bytes:
        """
        Serialization without nonce for mining
        """
        return (int_to_bytes(self.version) +
        self.prev_block +
        self.merkle_root +
        int_to_bytes(self.timestamp) +
        self.bits)
        
    def serialize_full(self) -> bytes:
        result = self.header()
        result += encode_varint(len(self.transactions))
        for txn in self.transactions:
            result += txn.serialize()
        return result

    def hash(self) -> bytes:
        """
        Little-Endian hash of block
        """
        h = HASH256(self.header())
        return h

    def difficulty(self) -> int:
        return MIN_DIFFICULTY / self.target

    def check_proof_of_work(self) -> bool:
        this_hash = self.hash()
        return bytes_to_int(this_hash) < self.target

    def validate_merkle_root(self) -> bool:
        return MerkleTree(self.tx_hashes).get_merkle_root() == self.merkle_root

    def verify(self, full=True) -> bool:
        # Full means verify a block with all its transactions
        # Otherwise we are just validating a header
        log.info(f"Verifying Block<{self.hash()}>...")

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
            mtree = MerkleTree(self.tx_hashes)
            if mtree.get_merkle_root()!= self.merkle_root:  # LE
                log.warning("Calculated merkle root mismatch")
                return False

            # Verify that there exists only 1 coinbase transaction
            coinbase_tx = self.transactions[0]
            if (not coinbase_tx.is_coinbase()):
                log.warning("First transaction is not a coinbase transaction.")
                return False

            if any(tx.is_coinbase() for tx in self.transactions[1:]):
                log.warning("Coinbase transaction should only be in first transaction")
                return False

            # Verify coinbase reward
            height = get_block_height_at_hash(self.prev_block)
            if height is None:
                log.warning("Previous block is not saved locally or does not exist at all.")
                return False
            height += 1

            block_subsidy = calculate_block_subsidy(height)
            fees = sum(tx.fee() for tx in self.transactions)
            block_reward = sum(out.value for out in coinbase_tx.outputs)

            if block_reward > block_subsidy + fees:
                log.warning("block_reward > block_subsidy + fees")
                return False

            if not all(tx.verify() for tx in self.transactions):
                log.warning("Invalid transaction in block")
                return False
        else:
            log.warning("Full block requried for block verification!")
            return False

        return True

    def size(self):
        return len(self.serialize_full())

# Auxillary functions

def calculate_block_subsidy(height: int) -> int:
    return INITIAL_BLOCK_REWARD >> floor(height/HALVING_INTERVAL)


def get_relevant_tx(pk_hash: bytes, height: int):
    # TODO: Implement Caching
    addr = pk_hash
    records = []

    raw_block = get_block_at_height(height, full=True)
    if not raw_block:
        return records

    block = Block.parse_static(raw_block, full_block=True)

    timestamp = get_block_timestamp(block.header())
    for txn in block.transactions:
        tx_hash = txn.hash()
        
        total_in = total_out = 0
        for tx_in in txn.inputs:
            if script_pubkey := tx_in.script_pubkey():
                if addr == script_pubkey.get_script_pubkey_receiver():
                    total_in += tx_in.value() or 0
                    
        for tx_out in txn.outputs:
            if addr == tx_out.script_pubkey.get_script_pubkey_receiver():
                total_out += tx_out.value
                    

        if txn.is_coinbase():
            records.append(
                {
                    "type": "COINBASE",
                    "value": total_out,
                    "txn": tx_hash,
                    "timestamp": timestamp,
                }
            )
            continue

        if total_in > 0:
            records.append(
                {
                    "type": "INPUT",
                    "value": total_in,
                    "txn": tx_hash,
                    "timestamp": timestamp,
                }
            )

        if total_out > 0:
            records.append(
                {
                    "type": "OUTPUT",
                    "value": total_out,
                    "txn": tx_hash,
                    "timestamp": timestamp,
                }
            )

    return records


def save_block(block: Block) -> bool:
    """
    Pure function to save a full block.
    Block validation should be done outside this function
    """
    header = block.header()
    txns_raw = [txn.serialize() for txn in block.transactions]

    block_hash = HASH256(header)
    # with LMDB_ENV.begin(db=BLOCKS_DB) as db:
    #     if db.get(block_hash) is not None:
    #         return False  # block already exists in db

    no_transactions_varint = encode_varint(len(block.transactions))
    block_raw = header + no_transactions_varint + b"".join(txns_raw)
    block_size = len(block_raw)

    # .dat file config
    dat_file_no = get_blk_dat_no()
    dat_file = os.path.join(APP_CONFIG.get("path", "blockchain"), f"blk{dat_file_no:08}.dat")
    if not os.path.exists(dat_file):
        open(dat_file, "wb").close()

    offset = os.path.getsize(dat_file)
    if offset + block_size > DAT_SIZE:
        dat_file_no += 1
        dat_file = os.path.join(APP_CONFIG.get("path", "blockchain"), f"blk{dat_file_no:08}.dat")

    # Saving data
    height = get_blockchain_height() + 1
    timestamp = header[68:72]

    try:
        with open(dat_file, "ab") as dat:
            dat.write(BLOCK_MAGIC)
            dat.write(int_to_bytes(len(block_raw)))
            dat.write(block_raw)

        with LMDB_ENV.begin(write=True) as db:
            total_sent = 0
            total_fees = 0
            for txn_obj in block.transactions:
                total_fees += txn_obj.fee()
                total_sent += sum(tx_out.value for tx_out in txn_obj.outputs)

            block_value = (
                int_to_bytes(dat_file_no)
                + int_to_bytes(offset)
                + int_to_bytes(block_size)
                + timestamp
                + int_to_bytes(len(block.transactions))
                + int_to_bytes(total_sent, 8)
                + int_to_bytes(total_fees, 8)
                + encode_varint(height)
            )
            db.put(block_hash, block_value, db=BLOCKS_DB)

            offset += 88 + len(no_transactions_varint)
            for i, tx in enumerate(txns_raw):
                tx_hash = HASH256(tx)
                tx_value = (
                    int_to_bytes(dat_file_no)
                    + int_to_bytes(offset)
                    + int_to_bytes(len(tx))
                    + int_to_bytes(i)
                    + encode_varint(height)
                )
                db.put(tx_hash, tx_value, db=TX_DB)
                offset += len(tx)

            db.put(encode_varint(height), block_hash, db=HEIGHT_DB)

            for txn_obj in block.transactions:
                if not txn_obj.is_coinbase():
                    for tx_in in txn_obj.inputs:
                        outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
                        db.delete(outpoint, db=UTXO_DB)

                        pk = tx_in.script_sig.get_script_sig_sender()
                        if pk:
                            db.delete(pk, outpoint, db=WALLET_DB)

                for i, tx_out in enumerate(txn_obj.outputs):
                    outpoint = txn_obj.hash() + int_to_bytes(i)
                    db.put(outpoint, tx_out.serialize(), db=UTXO_DB)

                    pk = tx_out.script_pubkey.get_script_pubkey_receiver()
                    if pk:
                        db.put(pk, outpoint, db=WALLET_DB)
        return True
    except Exception as e:
        log.exception(f"Error attempting to save block: {e}")
        return False
