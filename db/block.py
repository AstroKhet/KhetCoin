import logging
from io import BytesIO

from dataclasses import dataclass
from crypto.hashing import HASH256
from db.constants import *
from ktc_constants import MAX_TARGET, ONE_DAY, RETARGET_INTERVAL
from utils.helper import bits_to_target, encode_varint, bytes_to_int, int_to_bytes, read_varint
from utils.config import APP_CONFIG

import os

log = logging.getLogger(__name__)


# 0. Block Metadata dataclass
@dataclass
class BlockMetadata:
    block_hash: bytes
    dat_no: int 
    offset: int
    full_block_size: int 
    timestamp: int 
    no_txs: int
    fee: int 
    total_sent: int  
    height: int  

# For fast retrieval of metadata within each session
_metadata_cache: dict[bytes, BlockMetadata | None] = dict()


# 1. App meta functions

def get_block_dat_no():
    # retrieves the current (highest) block*.dat file from BLOCKS_DIR
    # block{8 digit number}.dat
    return max(
        int(filename[3:11])
        for filename in os.listdir(APP_CONFIG.get("path", "blockchain"))
        if filename.endswith(".dat")
    )


def get_blockchain_height():
    # Returns the height of the latest block stored in this node
    with LMDB_ENV.begin(db=HEIGHT_DB) as db:
        with db.cursor() as csr:
            if csr.last():
                return bytes_to_int(csr.key())
            else:
                return 0

# 2. Raw header/block by height/hash
def get_raw_block(block_hash: bytes, _full: bool = True) -> bytes | None:
    """
    Used to return a FULL block in byte form.
    \n`_full` is a legacy variable used for `get_header`. Do not use!
    """
    # block should be a 32B  representation of the block hash
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        value = db.get(block_hash)

        if value is None:
            return None

        dat_file_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])

        dat_file = os.path.join(APP_CONFIG.get("path", "blockchain"), f"blk{dat_file_no:08}.dat")
        stream = open(dat_file, "rb")
        stream.seek(offset)

        magic = stream.read(4)
        if magic != BLOCK_MAGIC:
            log.warning("Block magic not placed correctly in .dat file.")
            return None

        if _full:
            block_size = bytes_to_int(stream.read(4))
            return stream.read(block_size)
        else:  # Return 80B to be parsed by Header ONLY! Block class is designed for FULL blocks!
            return stream.read(80)


def get_raw_block_at_height(height: int, _full: bool = True) -> bytes | None:
    """
    Used to return a FULL block in byte form based on its height.
    `_full` is a legacy variable used for `get_header_at_height`. Do not use!
    """
    if block_hash := get_block_hash_at_height(height):
        if _full:
            if block_raw := get_raw_block(block_hash, True):
                return block_raw
        else:
            if header_raw := get_raw_header(block_hash):
                return header_raw

    log.warning(f"No {['header', 'block'][_full]} found at height {height}!")
    return None


def get_raw_header(block_hash: bytes) -> bytes | None:
    """Returns a block header in byte form"""
    return get_raw_block(block_hash, _full=False)


def get_raw_header_at_height(height: int) -> bytes | None:
    """Returns header in byte form based on its height."""
    return get_raw_block_at_height(height, _full=False)


# 2.1 Support function for converting height to hash
def get_block_hash_at_height(height: int | bytes) -> bytes | None:
    """
    Takes in a height as int or bytes(varint) and returns the corresponding block hash
    """
    if isinstance(height, int):
        height = encode_varint(height)
    with LMDB_ENV.begin(db=HEIGHT_DB) as db:
        return db.get(height)


# 3. Block metadata
def get_block_metadata(block_hash: bytes) -> BlockMetadata | None:
    if block_hash in _metadata_cache:
        return _metadata_cache.get(block_hash)
    
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        value = db.get(block_hash)
        if not value:
            return None
        return BlockMetadata(
            block_hash=block_hash,
            dat_no=bytes_to_int(value[0:4]),
            offset=bytes_to_int(value[4:8]),
            full_block_size=bytes_to_int(value[8:12]),
            timestamp=bytes_to_int(value[12:16]),
            no_txs=bytes_to_int(value[16:20]),
            total_sent=bytes_to_int(value[20:28]),
            fee=bytes_to_int(value[28:36]),
            height=read_varint(BytesIO(value[36:])),
        )

def get_block_metadata_at_height(height: int) -> BlockMetadata | None:
    block_hash = get_block_hash_at_height(height)
    if not block_hash:
        return None
    return get_block_metadata(blk_hash)


# 4. Commonly used metadata fields
# Also I've used this too much before implementing the metadata dataclass so here it stays
def get_block_height_at_hash(block_hash: bytes) -> int | None:
    if meta := get_block_metadata(block_hash):
        return meta.height
    return None


# 5. Misc functions
def get_block_exists(block_hash: bytes) -> bool:
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        return db.get(block_hash) is not None


def median_time_past() -> int:
    height = get_blockchain_height()
    timestamps = []

    for h in range(height, max(0, height - 11), -1):
        if header_raw := get_raw_header_at_height(h):
            timestamps.append(bytes_to_int(header_raw[68:72]))

    timestamps.sort()
    return timestamps[len(timestamps) // 2]


def calculate_block_target(height: int) -> int | None:
    if height < RETARGET_INTERVAL:
        return MAX_TARGET
    
    if (prev_header := get_raw_header_at_height(height - 1)):
        prev_target =  bits_to_target(prev_header[72:76])
    else:
        return None
    
    # Non-retargetting height
    if height % RETARGET_INTERVAL != 0:
        return prev_target
    
    # Retargetting height
    else:
        if (start_header := get_raw_header_at_height(height - RETARGET_INTERVAL)):
            start_time = bytes_to_int(start_header[68:72])
        else:
            return None

        end_time = bytes_to_int(prev_header[68:72])
 
        t_elapsed = end_time - start_time
        new_target = int(prev_target * t_elapsed / ONE_DAY)
        
        return max(prev_target // 4, min(new_target, prev_target * 4))


def save_block(block) -> bool:
    """
    Pure function to save a full block.
    Block validation should be done outside this function
    """
    header = block.header
    txs = block.get_transactions()
    raw_txs = [tx.serialize() for tx in txs]

    block_hash = block.hash()

    no_transactions_varint = encode_varint(len(txs))
    block_raw = header + no_transactions_varint + b"".join(raw_txs)
    block_size = len(block_raw)

    # .dat file config
    dat_file_no = get_block_dat_no()
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
            for tx in txs:
                total_fees += tx.fee()
                total_sent += sum(tx_out.value for tx_out in tx.outputs)

            block_value = (
                int_to_bytes(dat_file_no)
                + int_to_bytes(offset)
                + int_to_bytes(block_size)
                + timestamp
                + int_to_bytes(len(txs))
                + int_to_bytes(total_sent, 8)
                + int_to_bytes(total_fees, 8)
                + encode_varint(height)
            )
            db.put(block_hash, block_value, db=BLOCKS_DB)

            offset += 88 + len(no_transactions_varint)
            for i, tx in enumerate(raw_txs):
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

            for tx in txs:
                if not tx.is_coinbase():
                    for tx_in in tx.inputs:
                        outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
                        db.delete(outpoint, db=UTXO_DB)

                        pk = tx_in.script_sig.get_script_sig_sender()
                        if pk:
                            db.delete(pk, outpoint, db=ADDR_DB)

                for i, tx_out in enumerate(tx.outputs):
                    outpoint = tx.hash() + int_to_bytes(i)
                    db.put(outpoint, tx_out.serialize(), db=UTXO_DB)

                    pk = tx_out.script_pubkey.get_script_pubkey_receiver()
                    if pk:
                        db.put(pk, outpoint, db=ADDR_DB)
        return True
    
    except Exception as e:
        log.exception(f"Error attempting to save block: {e}")
        return False
    