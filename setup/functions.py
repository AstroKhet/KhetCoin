## Setup tools after installing Khetcoin, such as creating file folders
import logging
import tkinter as tk

from pathlib import Path
from tkinter import font


from utils.config import APP_CONFIG


def INITIAL_SETUP():
    """First and only setup for the entire project"""
    from setup.setup import SetupApp
    from setup.initializer import init_db, init_folders, init_font

    init_folders()
    setup_app = SetupApp()
    setup_app.main()
    init_db()
    init_font()


# TODO: param n & filename used for logging 2 nodes on one computer ONLY
def RUNTIME_SETUP():
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - "
            "%(funcName)s() - "
            "%(message)s"
        ),
        filename=APP_CONFIG.get("path", "log"),
        filemode="w",
        force=True
    )
    
    
    return 

