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
                address TEXT,
                user_agent TEXT,
                ban_score INTEGER
            );""")
        con.commit()
        
    APP_CONFIG.set("app", "initial_setup", True)
    return 


def RUNTIME_SETUP():
    """Setup for each time main.py is run"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s"
    )
    
    
    return 