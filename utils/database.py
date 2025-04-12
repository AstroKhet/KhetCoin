## To handle retrieval and storage of blocks and transactions
from typing import List

from utils.helper import *
from crypto.hashing import HASH256
import lmdb
import glob
import os
import shutil


# blk*.dat files follow "blk" + 8 digit dec file no + ".dat"

## 32 byte hashes are stored in little-endian format

MAGIC = bytes("Khet".encode())

TX_HASH_LMDB = ".data/transaction_index/"
BLK_HASH_LMDB = ".data/block_index/"
HEIGHT_LMDB = ".data/height_index/"
DAT_FILE_DIR = ".data/blocks/"

os.makedirs(DAT_FILE_DIR, exist_ok=True)
os.makedirs(TX_HASH_LMDB, exist_ok=True)
os.makedirs(HEIGHT_LMDB, exist_ok=True)
os.makedirs(BLK_HASH_LMDB, exist_ok=True)

MAP_SIZE = 10**9  # 1 GB
MAX_OFFSET = 10 ** 7  # 10 MB


TXN_ENV = lmdb.open(TX_HASH_LMDB, MAP_SIZE)
BLK_ENV = lmdb.open(BLK_HASH_LMDB, MAP_SIZE)
HEIGHT_ENV = lmdb.open(HEIGHT_LMDB, MAP_SIZE)


def get_latest_dat_file_no() -> int:
    """Finds the highest numbered blk*.dat file using max instead of sorting."""
    blk_files = glob.glob(os.path.join(DAT_FILE_DIR, "blk*.dat"))
    if not blk_files:
        genesis_file = os.path.join(DAT_FILE_DIR, "blk00000000.dat")

        # Create genesis file i.e. file 0
        with open(genesis_file, "wb") as f:
            pass

        return 0

    # Extract file numbers and find the max
    latest_file = max(blk_files, key=lambda f: int(f[-12:-4]))

    return int(latest_file[-12:-4])

def get_highest_block_height() -> int:
    """Returns the highest block height from the block index."""
    with HEIGHT_ENV.begin() as height_db, height_db.cursor() as cursor:
        if cursor.last():
            return letoi(cursor.key())
        else:
            return 0


def save_block(block_header: bytes, raw_txs: List[bytes]):
    """
    Saves a block and its transactions to the blockchain database.

    Args:
        block_header: The 80-byte block header
        raw_txs: List of serialized transactions

    Raises:
        ValueError: If the block header is invalid or block size exceeds limits
    """
    # Validate inputs
    if len(block_header) != 80:
        raise ValueError("Block header must be 80 bytes long")

    block_size = len(block_header) + sum(map(len, raw_txs))
    if block_size > 1_000_000:  # 1MB
        raise ValueError("Block size cannot exceed 1 MB")

    # Calculate block hash early to check if it already exists
    block_hash = HASH256(block_header)[::-1]  # Convert to LE for storage

    # Check if block already exists in database
    with BLK_ENV.begin() as blk_db:
        if blk_db.get(block_hash) is not None:
            raise ValueError(f"Block {block_hash.hex()} already exists in database")

    # Get current state
    dat_file_no = get_latest_dat_file_no()
    height = get_highest_block_height() + 1
    timestamp = block_header[-12:-8]  # Extract timestamp from header

    # Prepare block data without transactions
    block_data_without_tx = (
        MAGIC + itole(block_size, 4) + block_header + encode_varint(len(raw_txs))
    )

    # Get or create appropriate dat file
    dat_file = os.path.join(DAT_FILE_DIR, f"blk{dat_file_no:08}.dat")
    if not os.path.exists(dat_file):
        open(dat_file, "wb").close()

    # Check if we need a new file due to size limit
    if os.path.getsize(dat_file) + len(block_data_without_tx) > MAX_OFFSET:
        dat_file_no += 1
        dat_file = os.path.join(DAT_FILE_DIR, f"blk{dat_file_no:08}.dat")
        open(dat_file, "wb").close()

    # Write block header and prepare transaction hashes
    tx_hashes = []
    block_offset = 0
    tx_offsets = []

    # Use a single file handle for all operations on this file
    with open(dat_file, "ab") as dat:
        # Write block header and get its offset
        block_offset = dat.tell()
        dat.write(block_data_without_tx)

        # Write transactions and collect their offsets
        for raw_tx in raw_txs:
            tx_offset = dat.tell()
            dat.write(raw_tx)
            tx_offsets.append(tx_offset)
            tx_hashes.append(HASH256(raw_tx)[::-1])  # Convert to LE for storage

    # Now update all databases in a single transaction for atomicity
    try:
        # Use a write transaction for each database - if any fails, all are rolled back
        with BLK_ENV.begin(write=True) as blk_db, TXN_ENV.begin(
            write=True
        ) as txn_db, HEIGHT_ENV.begin(write=True) as height_db:

            # Store block metadata
            blk_value = (
                itole(dat_file_no, 4)  # dat file number
                + itole(block_offset, 4)  # offset in file
                + itole(block_size, 4)  # total block size
                + itole(height, 4)  # block height
                + timestamp  # block timestamp
            )
            blk_db.put(block_hash, blk_value)

            # Store transaction locations
            for tx_hash, tx_offset in zip(tx_hashes, tx_offsets):
                tx_value = itole(dat_file_no) + itole(tx_offset)
                txn_db.put(tx_hash, tx_value)

            # Update block height index
            height_db.put(itole(height), block_hash)

    except lmdb.Error as e:
        # Log the error
        print(f"Database error while saving block: {e}")
        # Could potentially attempt to remove the written data from the dat file
        # but that's complex and could cause more issues
        raise

    print(
        f"Block {block_hash.hex()} saved at height {height} in file {dat_file_no:08}.dat"
    )
    return block_hash  # Return the hash for convenience


def get_block_io(block_hash: bytes) -> BinaryIO:
    """Reads a block binary stream from the dat file using its block hash."""
    with BLK_ENV.begin() as blk_db:
        value = blk_db.get(block_hash)
        if value is None:
            raise ValueError(f"Block <{block_hash.hex()}> not found!")

        dat_file_no = letoi(value[:4])
        offset = letoi(value[4:8])
        # block_size = letoi(value[8:12])
        # height = letoi(value[12:16])
        # timestamp = letoi(value[16:20])

    dat_file = os.path.join(DAT_FILE_DIR, f"blk{dat_file_no:08}.dat")
    stream = open(dat_file, "rb")
    stream.seek(offset)
    return stream

def get_tx_io(tx_hash: bytes) -> BinaryIO:
    """Reads a transaction binary stream from the dat file using its transaction hash."""
    with TXN_ENV.begin() as txn_db:
        value = txn_db.get(tx_hash)
        if value is None:
            raise ValueError(f"Transaction <{tx_hash.hex()}> not found!")

        dat_file_no = letoi(value[:4])
        offset = letoi(value[4:8])

    dat_file = os.path.join(DAT_FILE_DIR, f"blk{dat_file_no:08}.dat")
    stream = open(dat_file, "rb")
    stream.seek(offset)
    return stream


def view_blk_lmdb():
    """Print all key-value pairs in BLK_HASH_LMDB."""
    with BLK_ENV.begin() as blk_db:
        for key, value in blk_db.cursor():
            block_hash = key[::-1].hex()  # <block_hash> - 32B - LE
            dat_file_no = letoi(value[:4])  # <dat_file_no> - 4B - LE
            offset = letoi(value[4:8])  # <offset> - 4B - LE
            block_size = letoi(value[8:12])  # <block_size> - 4B - LE
            height = letoi(value[12:16])  # <height> - 4B - LE
            timestamp = letoi(value[16:20])  # <timestamp> - 8B - LE

            print(f"<block_hash>: {block_hash} | "
                  f"<dat_file_no>: {dat_file_no} | "
                  f"<offset>: {offset} | "
                  f"<block_size>: {block_size} | "
                  f"<height>: {height} | "
                  f"<timestamp>: {timestamp}")

def view_txn_lmdb():
    """Print all key-value pairs in TX_HASH_LMDB."""
    with TXN_ENV.begin() as txn_db:
        for key, value in txn_db.cursor():
            tx_hash = key[::-1].hex()  # <tx_hash> - 32B - LE
            dat_file_no = letoi(value[:4])  # <dat_file_no> - 4B - LE
            offset = letoi(value[4:8])  # <offset> - 4B - LE

            print(f"<tx_hash>: {tx_hash} | "
                  f"<dat_file_no>: {dat_file_no} | "
                  f"<offset>: {offset}")


def ERASE_ALL_DATA():
    ### REMOVE IN PRODUCTION !!!!!
    """Deletes all files in .data/block_index, .data/blocks, and .data/transaction_index."""
    for directory in [".data/block_index", ".data/blocks", ".data/transaction_index"]:
        if os.path.exists(directory):
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

    print("All data erased!")
