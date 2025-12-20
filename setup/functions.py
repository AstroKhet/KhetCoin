## Setup tools after installing Khetcoin, such as creating file folders
import logging
import tkinter as tk

from pathlib import Path
from tkinter import font


from utils.config import APP_CONFIG


def INITIAL_SETUP():
    """First and only setup for the entire project"""
    # 1. Directory creation
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    BLOCKCHAIN_DIR = BASE_DIR / ".data" / "blockchain"
    BLOCKCHAIN_DIR.mkdir(parents=True, exist_ok=True)
    
    LMDB_DIR = BASE_DIR / ".data" / "lmdb"
    LMDB_DIR.mkdir(parents=True, exist_ok=True)
    
    KEYS_DIR = BASE_DIR / ".local" / "keys"
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 2. DB files
    from setup.database import init_db
    init_db()

    # 3. Fonts
    MONO_STACK = ["Courier New", "Courier", "Liberation Mono", "Monospace"]
    SANS_STACK = ["Segoe UI", "Helvetica", "Arial", "Sans"]
    
    _temp_root = tk.Tk()
    _temp_root.withdraw() 
    APP_CONFIG.set("font", "mono", _pick_family(MONO_STACK))
    APP_CONFIG.set("font", "sans", _pick_family(SANS_STACK))
    _temp_root.destroy()

    return True


# TODO: param n & filename used for logging 2 nodes on one computer ONLY
def RUNTIME_SETUP():
    """Setup for each time main.py is run"""
    if APP_CONFIG.get("app", "initial_setup"):
        INITIAL_SETUP()
        
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
        # filename=APP_CONFIG.get("path", "log"),
        filename=APP_CONFIG.get("path", "log"),
        filemode="w",
        force=True
    )
    
    
    return 

def _pick_family(stack):
    """Return the first available font family from the stack."""
    available = list(font.families())
    for f in stack:
        if f in available:
            return f
    return "TkDefaultFont"