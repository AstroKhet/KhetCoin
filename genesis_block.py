from utils.helper import *
from utils.print import *
from utils.database import *

from blockchain.block import *
from blockchain.merkle_tree import *
from blockchain.transaction import *
from blockchain.script import *

from crypto.key import *
from crypto.mining import *

from coincurve import verify_signature

genesis_blk_height = 0  # duh

coinbase_tx_input = TransactionInput(
    prev_hash=bytes.fromhex("ff" * 32),
    prev_index=0xffffffff,
    script_sig=Script([itole(genesis_blk_height, 8), b"Khet turns 6 on 01/Feb/2025"]),
    sequence=0xffffffff,
)

coinbase_tx_output = TransactionOutput(
    value=5_000_000_000,  # 50 KTC
    script_pubkey=Script([get_public_key("Khet", raw=True), 0xAC]),  ## OP CHECK SIG
)

coinbase_tx = Transaction(
    version=1,
    inputs=[coinbase_tx_input],
    outputs=[coinbase_tx_output],
    locktime=0
)

genesis = Block(
    version=1,
    prev_block=bytes.fromhex("00" * 32),
    merkle_root=MerkleTree([coinbase_tx.hash()]).get_merkle_root(),
    timestamp=1738339200,  # 01/Feb/2025 00:00
    bits=LOWEST_BITS,  # LOWEST_BITS,
    nonce=30864130,
    tx_hashes=[coinbase_tx.hash()],
)

def mine(blk):
    blk = mine_block_with_nonce(blk)
    print(f"Nonce = {blk.nonce}")

    print("Genesis Block: ")
    print_bytes(blk.serialize())
    print("Block Hash: ")
    print_bytes(blk.hash())
    print("Nonce:", blk.nonce)


# FOR MINING PURPOSES
if __name__ == "__main__":
    print("Genesis Block: ")
    print_bytes(genesis.hash())
    print("\n" + "-" * 75 + "\n")
    # mine(genesis)

    print("GENESIS BLOCK FULL DAT")
    print_bytes(
        genesis.serialize() + 
        encode_varint(1) + 
        coinbase_tx.serialize()
    )

    ERASE_ALL_DATA()
    save_block(genesis.serialize(), [coinbase_tx.serialize()], 0)

    print("-" * 75)
    blk0 = os.path.join(DAT_FILE_DIR, "blk00000000.dat")

    with open(blk0, "rb") as f:
        print("GENESIS BLOCK DATA (SAVED)")
        print_bytes(f.read())

    view_blk_lmdb()
    view_txn_lmdb()