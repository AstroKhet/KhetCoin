import time

from blockchain.block import *
from crypto.hashing import HASH256


def mine_block_with_nonce(block: Block) -> Block:
    start_time = time.time()
    static_block = block.header_without_nonce()

    # Print some statistics about mining this block
    e_no_hashes = round(pow(2, 256) / block.target)
    print(f"Block Target: {block.target:064x}")
    print(f"Estimated number of hashes required: {e_no_hashes}")

    for nonce in range(block.nonce, 0xFFFFFFFF):

        h = HASH256(static_block + int_to_bytes(nonce))
        if bytes_to_int(h) < block.target:
            print(h.hex())
            block.nonce = nonce
            print("NONCE FOUND")
            print(block.nonce)
            break
    else:
        print("All possible nonces exhausted. Please mine with coinbase instead.")

    print()
    duration = time.time() - start_time
    print(f"Time taken: {duration:.2f}s")
    # print(f"Avg. hash rate: {round(nonce/duration)}")
    return block
