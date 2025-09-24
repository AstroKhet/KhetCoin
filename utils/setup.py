## Setup tools after installing Khetcoin, such as creating file folders
import logging
# .data/
# 


def INITIAL_SETUP():
    """First and only setup for the entire project"""
    return 


def RUNTIME_SETUP():
    """Setup for each time main.py is run"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s"
    )
    return 