"""
Database constants and storage specifications for blockchain persistence.

These definitions support all on-disk blockchain storage and LMDB-backed
indexes/caches. They are internal-only and must not be configurable or
user-visible.
"""

import lmdb
import os

from utils.config import APP_CONFIG


# =============================================================================
# BLOCKCHAIN .DAT STORAGE FORMAT
# =============================================================================
# At the beginning of each block:
#
#   - block_magic        : 4B   (b"MEOW")
#   - full_block_size    : 4B
#   - block_header       : 80B
#   - tx_count           : VarInt
#   - transactions       : Tx1, Tx2, ... TxN
#

BLOCK_MAGIC = b"MEOW" 


# =============================================================================
# FILESYSTEM / STORAGE LIMITS
# =============================================================================

MAP_SIZE = 1 << 30        # LMDB map size: 1 GiB
DAT_SIZE = 10 * (1 << 20) # Max .dat file size: 10 MiB


# =============================================================================
# LMDB ENVIRONMENT
# =============================================================================
LMDB_DIR = APP_CONFIG.get("path", "lmdb")
LMDB_DIR.mkdir(parents=True, exist_ok=True)
LMDB_ENV = lmdb.open(str(LMDB_DIR), map_size=MAP_SIZE, max_dbs=10)


# =============================================================================
# LMDB DATABASE SCHEMAS
# =============================================================================

# ---------------------
# BLOCKS DB
# ---------------------
# Key   : Block Hash (32B)
# Value :
#   - data_file_no      : 4B
#   - data_offset       : 4B
#   - full_block_size   : 4B
#   - timestamp         : 4B
#   - tx_count          : 4B
#   - total_sent        : 8B
#   - fee               : 8B
#   - height            : 8B


# ---------------------
# INDEX DB
# ---------------------
# Key   : Block Hash (32B)
# Value:
#   - block_hash        : 32B
#   - prev_hash         : 32B
#   - height            : 8B
#   - chainwork         : 32B
#   - flags             : 1B


# ---------------------
# HEIGHT DB
# ---------------------
# Key   : Block Height (8B)
# Value : 
#    - Block Hash       : 32B


# ---------------------
# TX DB
# ---------------------
# Key   : Tx Hash (32B)
# Value :
#   - data_file_no      : 4B
#   - data_offset       : 4B
#   - full_tx_size      : 4B
#   - block_height      : 8B


# ---------------------
# TX_HISTORY DB (Duplicate Keys)
# ---------------------
# Key   : Block Height (8B)
# Value :
#   - tx_hash           : 32B
#   - coinbase_value    : 8B
#   - input_value       : 8B
#   - output_value      : 8B


# ---------------------
# UTXO DB
# ---------------------
# Key   : Tx Hash (32B) + Output Index (4B)
# Value : Full Transaction Output


# ---------------------
# ADDR DB (Duplicate Keys)
# ---------------------
# Key   : PubKey Hash (20B)
# Value : Tx Hash (32B) + Output Index (4B)


with LMDB_ENV.begin(write=True) as txn:
    BLOCKS_DB     = LMDB_ENV.open_db(b"blocks", txn=txn, create=True)
    INDEX_DB      = LMDB_ENV.open_db(b"index", txn=txn, create=True)
    HEIGHT_DB     = LMDB_ENV.open_db(b"height", txn=txn, create=True)
    TX_DB         = LMDB_ENV.open_db(b"transaction", txn=txn, create=True)
    TX_HISTORY_DB = LMDB_ENV.open_db(b"tx_history", txn=txn, create=True, dupsort=True)
    UTXO_DB       = LMDB_ENV.open_db(b"utxo", txn=txn, create=True)
    ADDR_DB       = LMDB_ENV.open_db(b"addr", txn=txn, create=True, dupsort=True)
    MEMPOOL_DB    = LMDB_ENV.open_db(b"mempool", txn=txn, create=True)
