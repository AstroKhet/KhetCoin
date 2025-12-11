from copy import copy, deepcopy
import time
from blockchain.block import Block
from blockchain.merkle_tree import MerkleTree
from blockchain.script import P2PKH_script_pubkey, Script
from blockchain.transaction import TransactionOutput
from crypto.hashing import HASH160, HASH256
from crypto.key import get_public_key
from ktc_constants import GENESIS_HASH, KTC, MAX_BITS
from mining.miner import Miner, build_coinbase_tx
from utils.helper import int_to_bytes

pk_hash = HASH160(get_public_key("Khet", raw=True))

output = TransactionOutput(
    value=50 * KTC,
    script_pubkey=P2PKH_script_pubkey(pk_hash)
)


unmined_block = Block(
    version=1,
    prev_block=GENESIS_HASH,
    timestamp=int(time.time()),
    bits=bytes.fromhex("003fff1e"),  
    nonce=0,
    txs=[build_coinbase_tx(0, [output])],
)

# print(unmined_block)

if __name__ == "__main__":
    miner = Miner()
    mined_block = miner.start_mining(unmined_block, outputs=[output])
    # print(mined_block)