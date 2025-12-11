## Setup tools after installing Khetcoin, such as creating file folders
import logging
import os

import sqlite3

from utils.config import APP_CONFIG

def INITIAL_SETUP():
    """First and only setup for the entire project"""
    # 0. Directory creation
    os.makedirs(".data/blockchain", exist_ok=True)
    os.makedirs(".data/lmdb", exist_ok=True)
    os.makedirs(".local/keys", exist_ok=True)
    
    # 1. DB files
    # 1.1 Saved Wallet Address SQL
    with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
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
    with sqlite3.connect(APP_CONFIG.get("path", "peers")) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                ip TEXT,
                port INTEGER,
                ban_score INTEGER
            );""")
        con.commit()
        
    APP_CONFIG.set("app", "initial_setup", True)
    return 


# TODO: param n & filename used for logging 2 nodes on one computer ONLY
def RUNTIME_SETUP(n=""):
    """Setup for each time main.py is run"""
    if APP_CONFIG.get("app", "initial_setup"):
        INITIAL_SETUP()
        
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
        # filename=APP_CONFIG.get("path", "log"),
        filename=os.path.join(APP_CONFIG.base_dir, f".local/log-{n}.txt"),
        filemode="w",
        force=True
    )
    
    
    return 