"""
Database constants for supporting all blockchain storage and caching functionalities
These should neither be configurable nor seen by the user normally.
"""

import lmdb
import os

from utils.config import APP_CONFIG

# BLOCKCHAIN .DAT STORAGE FORMAT
# BEGINNING of each BLOCK
# - Block Magic 4B (MEOW)
# - Full Block Size 4L
# - Block Header 80B
# - No. TX (varint)
# - Tx1, Tx2, ... Tx

BLOCK_MAGIC = "MEOW".encode() # TODO shift this to a universal constants file
os.makedirs(APP_CONFIG.get("path", "blockchain"), exist_ok=True)

MAP_SIZE = 1 << 30  # 1 GB
DAT_SIZE = 10 * (1 << 20) # 10 MB

LMDB_ENV = lmdb.open(
    APP_CONFIG.get("path", "lmdb"),
    map_size=MAP_SIZE,
    max_dbs=10, 
)

with LMDB_ENV.begin(write=True) as txn:
    BLOCKS_DB = LMDB_ENV.open_db(b"blocks", txn=txn, create=True)
    HEIGHT_DB = LMDB_ENV.open_db(b"height", txn=txn, create=True)
    TX_DB = LMDB_ENV.open_db(b"transaction", txn=txn, create=True)
    UTXO_DB = LMDB_ENV.open_db(b"utxo", txn=txn, create=True)
    ADDR_DB = LMDB_ENV.open_db(b"addr", txn=txn, create=True, dupsort=True)


# BLOCKS
# Key: Block hash (32B)
# Value: dat no: 4B
#        offset: 4B
#        full block size: 4B
#        timestamp: 4B
#        no txs: 4B
#        total sent: 8B
#        fee: 8B
#        height: VI

# HEIGHT
# Key: Height (varint)
# Value: Block Hash (32L)

# TX
# Key: Tx Hash (32L)
# Value: dat no (4L)
#        offset (4L)
#        full tx size (4L)
#        height (varint)

# UTXO
# Key: Tx Hash (32L) + Index (4L)
# Value: Full Transaction Output

# ADDR (Duplicate Keys)
# Key: Pubkey Hash (20B)
# Value: Tx Hash (32L) + Index (4L)
