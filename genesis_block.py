from db.constants import *
from db.utils import print_dat, print_lmdb
from utils.helper import *
from utils.fmt import *

from blockchain.block import *
from blockchain.merkle_tree import *
from blockchain.transaction import *
from blockchain.script import *

from crypto.key import *
from crypto.mining import *

from ktc_constants import MIN_BITS

# Create Genesis Block and insert into database
# Genesis Block will use P2PKH, but P2SH will be supported as well

# ScriptSig (Coinbase; can be anything)
# Suggested format: <BlockHeight> <custom data> <additional nonce>
script_sig = Script([
    int_to_bytes(0, 8), 
    b"Khet turns 6 on 01/Feb/2025"
])

# ScriptPubkey
# OP_DUP OP_HASH160 <PubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
script_pubkey = Script([
    0x76,
    0xA9,
    HASH160(get_public_key("EFD", raw=True)), # type: ignore
    0x88,
    0xAC
])

coinbase_tx_input = TransactionInput(
    prev_hash=bytes(32),
    prev_index=0xffffffff,
    script_sig=script_sig,
    sequence=0xffffffff,
)

coinbase_tx_output = TransactionOutput(
    value=50 * KTC,  # 50 KTC
    script_pubkey=script_pubkey,
)

coinbase_tx = Transaction(
    version=1,
    inputs=[coinbase_tx_input],
    outputs=[coinbase_tx_output],
    locktime=0
)

unmined_genesis_block = Block(
    version=1,
    prev_block=bytes.fromhex("00" * 32),
    merkle_root=MerkleTree([coinbase_tx.hash()]).get_merkle_root(),
    timestamp=int(time.time()),
    bits=MIN_BITS,  # LOWEST_BITS,
    nonce=0,
    tx_hashes=[coinbase_tx.hash()],
)

# FOR MINING PURPOSES
if __name__ == "__main__":
    print("Genesis Block: ")

    print("\n" + "-" * 75 + "\n")

    genesis_block = mine_block_with_nonce(unmined_genesis_block)
    print("Genesis Block Hash")
    print(genesis_block.hash().hex())
    
    print("Genesis header")
    print(genesis_block.header().hex())

    print("GENESIS BLOCK FULL DAT")
    print_bytes(
        genesis_block.header() + 
        encode_varint(1) + 
        coinbase_tx.serialize()
    )

    print("Saving Genesis Block...")
    dat_file_no = 0
    dat_file = os.path.join(BLOCKCHAIN_DIR, f"blk{dat_file_no:08}.dat")
    if not os.path.exists(dat_file):
        open(dat_file, "wb").close()

    try:
        with open(dat_file, "ab") as dat:
            header = genesis_block.header()
            full_block = header + encode_varint(1) + coinbase_tx.serialize()

            dat.write(BLOCK_MAGIC)
            dat.write(int_to_bytes(len(full_block)))
            dat.write(full_block)
            dat.flush()
            print(f"Dat {dat_file} saved")
        with LMDB_ENV.begin(write=True) as db:
            block_value = (
                int_to_bytes(dat_file_no)
                + int_to_bytes(0)  # offset
                + int_to_bytes(len(full_block))  # BlockSize
                + header[68:72]  # Timestamp
                + int_to_bytes(1)  # No. Txns
                + int_to_bytes(coinbase_tx_output.value, 8)  # Total sent
                + int_to_bytes(0, 8)  # Fee
                + encode_varint(0) # Height
            )

            db.put(genesis_block.hash(), block_value, db=BLOCKS_DB)
            print("Block DB Saved")

            tx_hash = HASH256(coinbase_tx.serialize())
            tx_value = (
                int_to_bytes(0)
                + int_to_bytes(88 + len(encode_varint(1)))
                + int_to_bytes(len(coinbase_tx.serialize()))
                + int_to_bytes(0)
                + encode_varint(0)
            )

            db.put(tx_hash, tx_value, db=TX_DB)
            print("tx db saved")

            db.put(encode_varint(0), genesis_block.hash(), db=HEIGHT_DB)
            print("Height DB Saved")

            key = HASH160(get_public_key("EFD", raw=True))  # Khet's P2PKH 20B Address
            value = tx_hash + int_to_bytes(0) # Outpoint
            db.put(key, value, db=ADDR_DB)
            print("Addr db saved")
            
            key = coinbase_tx.hash() + int_to_bytes(0)
            value = coinbase_tx.outputs[0].serialize()
            db.put(key, value, db=UTXO_DB)
            print("utxo db saved")
        print("Genesis block saved")
 
    except Exception as e:
        print(f"Error {e}")
    print_lmdb()
    print_dat(0, 0)
    # save_block(genesis.serialize(), [coinbase_tx.serialize()])
