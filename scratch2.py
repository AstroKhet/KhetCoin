from db.constants import *
from utils.helper import *
from utils.fmt import *

from blockchain.block import *
from blockchain.merkle_tree import *
from blockchain.transaction import *
from blockchain.script import *

from crypto.key import *
from crypto.mining import *

from ktc_constants import MIN_BITS, GENESIS_HASH


# ScriptSig (Coinbase; can be anything)
script_sig = Script([int_to_bytes(1, 8)])

# ScriptPubkey
script_pubkey = Script(
    [0x76, 0xA9, HASH160(get_public_key("Khet", raw=True)), 0x88, 0xAC]  # type: ignore
)

coinbase_tx_input = TransactionInput(
    prev_hash=bytes(32),
    prev_index=0xFFFFFFFF,
    script_sig=script_sig,
    sequence=0xFFFFFFFF,
)

coinbase_tx_output = TransactionOutput(
    value=50 * KTC,  # 50 KTC
    script_pubkey=script_pubkey,
)

coinbase_tx = Transaction(
    version=1, inputs=[coinbase_tx_input], outputs=[coinbase_tx_output], locktime=0
)

unmined_block = Block(
    version=1,
    prev_block=GENESIS_HASH,
    merkle_root=MerkleTree([coinbase_tx.hash()]).get_merkle_root(),
    timestamp=int(time.time()),
    bits=MIN_BITS,  # LOWEST_BITS,
    nonce=0,
    tx_hashes=[coinbase_tx.hash()],
    transactions=[coinbase_tx],
)


block = mine_block_with_nonce(unmined_block)
print(f"Time: {block.timestamp}")
print("Block Hash:")
print(block.hash().hex())

print("Full Block:")
print_bytes(block.serialize_full())

if input("Save? (y/n)") == 'y':
    if not block.verify():
        print("Block not verified!")
    else:
        save_block(block)
        print("block saved")
