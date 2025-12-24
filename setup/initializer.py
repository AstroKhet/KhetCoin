"""
Setup file to create LMDB database and save genesis block
"""
from math import floor
from pathlib import Path
import sqlite3
import time
import tkinter as tk
from tkinter import font

from crypto.hashing import HASH256

from ktc_constants import GENESIS_HASH, GENESIS_BLOCK_BYTES, HIGHEST_TARGET, INITIAL_BLOCK_REWARD
from utils.config import APP_CONFIG
from utils.helper import int_to_bytes

ADDRESSES_SQL = APP_CONFIG.get("path", "addresses")
PEERS_SQL = APP_CONFIG.get("path", "peers")
BLOCKCHAIN_DIR = APP_CONFIG.get("path", "blockchain")


def init_folders():
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    BLOCKCHAIN_DIR = BASE_DIR / ".data" / "blockchain"
    BLOCKCHAIN_DIR.mkdir(parents=True, exist_ok=True)
    
    LMDB_DIR = BASE_DIR / ".data" / "lmdb"
    LMDB_DIR.mkdir(parents=True, exist_ok=True)
    
    KEYS_DIR = BASE_DIR / ".local" / "keys"
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    
def init_db():
    # 1. SQL files (.db)
    # 1.1 Saved Wallet Address SQL
    with sqlite3.connect(ADDRESSES_SQL) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                address TEXT,
                added INTEGER
            );""")
        con.commit()
    
    # 1.2 Saved Peers SQL
    with sqlite3.connect(PEERS_SQL) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                ip TEXT,
                port INTEGER,
                added INTEGER,
                last_seen INTEGER,
                services INTEGER,
                UNIQUE(ip, port)
            );""")
        con.commit()
        
        # Bootstrap peer (Khet himself)
        cur.execute("""
            INSERT INTO peers (name, ip, port, added, last_seen, services) 
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip, port) DO NOTHING;
        """, ("Khet", "128.106.117.21", 8666, int(time.time()), 0, 1)
        )
        con.commit()
        
    # 2. LMDB files (.mdb)
    from db.constants import ADDR_DB, HEIGHT_DB, INDEX_DB, LMDB_ENV, BLOCK_MAGIC, BLOCKS_DB, TX_DB, UTXO_DB
    with LMDB_ENV.begin(write=True) as txn:
        LMDB_ENV.open_db(b"blocks",      txn=txn, create=True)
        LMDB_ENV.open_db(b"index",       txn=txn, create=True)
        LMDB_ENV.open_db(b"height",      txn=txn, create=True)
        LMDB_ENV.open_db(b"transaction", txn=txn, create=True)
        LMDB_ENV.open_db(b"tx_history",  txn=txn, create=True, dupsort=True)
        LMDB_ENV.open_db(b"utxo",        txn=txn, create=True)
        LMDB_ENV.open_db(b"addr",         txn=txn, create=True, dupsort=True)

            
    # 3. Genesis block
    dat_file = BLOCKCHAIN_DIR / f"blk00000000.dat"
    with open(dat_file, "ab") as dat:
        dat.write(BLOCK_MAGIC)
        dat.write(int_to_bytes(len(GENESIS_BLOCK_BYTES)))
        dat.write(GENESIS_BLOCK_BYTES)

    with LMDB_ENV.begin(write=True) as db_tx:
        # 1. Save to BLOCKS_DB
        block_value = (
            int_to_bytes(0)
            + int_to_bytes(0)
            + int_to_bytes(len(GENESIS_BLOCK_BYTES))
            + GENESIS_BLOCK_BYTES[68:72]
            + int_to_bytes(1)
            + int_to_bytes(INITIAL_BLOCK_REWARD, 8)
            + int_to_bytes(0, 8)
            + int_to_bytes(0, 8)
        )
        db_tx.put(GENESIS_HASH, block_value, db=BLOCKS_DB)

        # 2. Save to INDEX_DB
        index_value = (
            GENESIS_HASH
            + bytes(32)
            + int_to_bytes(0, 8)
            + int_to_bytes(floor((1 << 256) / (HIGHEST_TARGET + 1)), 32)
            + bytes(0)
        )
        db_tx.put(GENESIS_HASH, index_value, db=INDEX_DB)
        
        # 3. Save to TX_DB
        CB_TX_BYTES = GENESIS_BLOCK_BYTES[81:]
        CB_TX_HASH = HASH256(CB_TX_BYTES)
        tx_value = (
            int_to_bytes(0)
            + int_to_bytes(89)
            + int_to_bytes(len(CB_TX_BYTES))
            + int_to_bytes(0)
            + int_to_bytes(0, 8)
        )

        db_tx.put(CB_TX_HASH, tx_value, db=TX_DB)
        
        # 4. Save to Height DB (not used in save_block_data)
        db_tx.put(int_to_bytes(0, 8), GENESIS_HASH, db=HEIGHT_DB)
        
        # 5. Save to UTXO (not used in save_block_data)
        outpoint = CB_TX_HASH + int_to_bytes(0, 4)
        CB_TX_OUTPUT = GENESIS_BLOCK_BYTES[-38:-4]
        db_tx.put(outpoint, CB_TX_OUTPUT, db=UTXO_DB)
        
        # 6. Save to ADDR
        db_tx.put(CB_TX_OUTPUT[12:32], outpoint, db=ADDR_DB)
        
def init_font():
    MONO_STACK = ["Courier New", "Courier", "Liberation Mono", "Monospace"]
    SANS_STACK = ["Segoe UI", "Helvetica", "Arial", "Sans"]
    
    _temp_root = tk.Tk()
    _temp_root.withdraw() 
    APP_CONFIG.set("font", "mono", _pick_family(MONO_STACK))
    APP_CONFIG.set("font", "sans", _pick_family(SANS_STACK))
    _temp_root.destroy()

def _pick_family(stack):
    """Return the first available font family from the stack."""
    available = list(font.families())
    for f in stack:
        if f in available:
            return f
    return "TkDefaultFont"