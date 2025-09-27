import logging
from io import BytesIO

from dataclasses import dataclass
from db.constants import *
from utils.helper import encode_varint, bytes_to_int, read_varint

import os

log = logging.getLogger(__name__)

@dataclass
class BlockMetadata:
    block_hash: bytes
    dat_no: int 
    offset: int
    full_block_size: int 
    timestamp: int 
    no_txns: int
    fee: int 
    total_sent: int  
    height: int  


def get_blk_dat_no():
    # retrieves the current (highest) blk*.dat file from BLOCKS_DIR
    # blk{8 digit number}.dat
    return max(
        int(filename[3:11])
        for filename in os.listdir(BLOCKCHAIN_DIR)
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


def get_block_hash_at_height(height: int | bytes) -> bytes | None:
    """
    Takes in a height as int or bytes(varint) and returns the corresponding block hash
    """
    if isinstance(height, int):
        height = encode_varint(height)
    with LMDB_ENV.begin(db=HEIGHT_DB) as db:
        value = db.get(height)
        if value is None:
            return None

        return value


def get_block_at_height(height: int, full: bool = False) -> bytes | None:
    if block_hash := get_block_hash_at_height(height):
        if block := get_block(block_hash, full):
            return block

    log.warning(f"No block found at height {height}")
    return None


def get_block(block_hash: bytes, full: bool = False) -> bytes | None:
    # block should be a 32B  representation of the block hash
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        value = db.get(block_hash)

        if value is None:
            return None

        dat_file_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])

        dat_file = os.path.join(BLOCKCHAIN_DIR, f"blk{dat_file_no:08}.dat")
        stream = open(dat_file, "rb")
        stream.seek(offset)

        magic = stream.read(4)
        if magic != BLOCK_MAGIC:
            return None

        block_size = bytes_to_int(stream.read(4))
        if full:
            return stream.read(block_size)
        else:  # headers only
            return stream.read(80)


def get_block_header(block_hash: bytes) -> bytes | None:
    return get_block(block_hash, full=False)


def get_block_metadata(block_hash: bytes) -> BlockMetadata | None:
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
            no_txns=bytes_to_int(value[16:20]),
            total_sent=bytes_to_int(value[20:28]),
            fee=bytes_to_int(value[28:36]),
            height=read_varint(BytesIO(value[36:])),
        )

def get_block_metadata_at_height(height: int) -> BlockMetadata | None:
    blk_hash = get_block_hash_at_height(height)
    if not blk_hash:
        return None
    return get_block_metadata(blk_hash)

# Commonly used metadata fields
# Also I've used this too much before implementing the metadata dataclass so here it stays
def get_block_height_at_hash(block_hash: bytes) -> int | None:
    if meta := get_block_metadata(block_hash):
        return meta.height
    return None

def get_block_exists(block_hash: bytes) -> bool:
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        return db.get(block_hash) is not None


def median_time_past() -> int:
    height = get_blockchain_height()
    timestamps = []

    for h in range(height, max(0, height - 11), -1):
        block = get_block_at_height(h)
        if block := get_block_at_height(h):
            timestamps.append(get_block_timestamp(block))
        else:
            timestamps.append(0)

    timestamps.sort()
    return timestamps[len(timestamps) // 2]


def get_block_version(header: bytes) -> int:
    return bytes_to_int(header[0:4])


def get_block_prev_hash(header: bytes) -> bytes:
    return header[4:36]


def get_block_merkle_root(header: bytes) -> bytes:
    return header[36:68]


def get_block_timestamp(header: bytes) -> int:
    return bytes_to_int(header[68:72])


def get_block_bits(header: bytes) -> bytes:
    return header[72:76]


def get_block_nonce(header: bytes) -> int:
    return bytes_to_int(header[76:80])


