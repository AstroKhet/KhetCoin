import time
import datetime
import struct
import multiprocessing

from regex import D
from blockchain.block import *
from crypto.hashing import HASH256


def mine_block_with_nonce(block: Block) -> Block:
    start_time = start = time.time()
    static_block = block.serialize_static()
    last_nonce = 0

    # Print some statistics about mining this block
    e_no_hashes = round(pow(2, 256) / block.target)
    print(f"Block Target: {block.target:064x}")
    print(f"Estimated number of hashes required: {e_no_hashes}")

    for nonce in range(0, 0xFFFFFFFF):
        # now = time.time()
        # if now - start > 1:
        #     rate = nonce - last_nonce
        #     e_time_left = round(pow(2, 256) / (block.target * rate))

        #     print(f"{rate} hashes/s, estimated time left = {str(datetime.timedelta(seconds=e_time_left))}\r")

        #     start = now
        #     last_nonce = nonce

        h = HASH256(static_block + itole(nonce))
        if betoi(h) < block.target:
            block.nonce = nonce
            break
    else:
        print("All possible nonces exhausted. Please mine with coinbase instead.")

    print()
    duration = time.time() - start_time
    print(f"Time taken: {duration:.2f}s")
    print(f"Avg. hash rate: {round(nonce/duration)}")
    return block
