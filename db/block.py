import logging

from dataclasses import dataclass
from pathlib import Path

from db.constants import *

from db.height import get_block_hash_at_height, get_blockchain_height
from ktc_constants import GENESIS_HASH, HIGHEST_TARGET, ONE_DAY, RETARGET_INTERVAL
from utils.helper import bits_to_target, bytes_to_int, int_to_bytes
from utils.config import APP_CONFIG

import os

log = logging.getLogger(__name__)
BLOCKCHAIN_DIR = Path(APP_CONFIG.get("path", "blockchain"))

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



# 1. App meta functions



def get_block_dat_no():
    block_files = BLOCKCHAIN_DIR.glob("blk*.dat")
    return max(int(f.stem[3:]) for f in block_files if f.stem[3:].isdigit())


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

        dat_file = BLOCKCHAIN_DIR / f"blk{dat_file_no:08}.dat"
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



# 3. Block metadata
def get_block_metadata(block_hash: bytes) -> BlockMetadata | None:
    with LMDB_ENV.begin(db=BLOCKS_DB) as db:
        value = db.get(block_hash)
        if not value:
            return None
        return BlockMetadata(
            block_hash      = block_hash,
            dat_no          = bytes_to_int(value[0:4]),
            offset          = bytes_to_int(value[4:8]),
            full_block_size = bytes_to_int(value[8:12]),
            timestamp       = bytes_to_int(value[12:16]),
            no_txs          = bytes_to_int(value[16:20]),
            total_sent      = bytes_to_int(value[20:28]),
            fee             = bytes_to_int(value[28:36]),
            height          = bytes_to_int(value[36:44]),
        )

def get_block_metadata_at_height(height: int) -> BlockMetadata | None:
    block_hash = get_block_hash_at_height(height)
    if not block_hash:
        return None
    return get_block_metadata(block_hash)


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
        return HIGHEST_TARGET
    
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


def get_block_locator_hashes():
    locator = []
    height = get_blockchain_height()
    step = 1
    
    while height >= 0:
        locator.append(get_block_hash_at_height(height))
        if len(locator) >= 10:
            step *= 2
        height -= step
        
    if locator[-1] != GENESIS_HASH:
        locator.append(GENESIS_HASH)
    
    return locator
    