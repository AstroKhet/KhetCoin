"""
Local storage of the transaction history pertaining to your node.
"""

from datetime import datetime, timedelta

from blockchain.block import Block
from db.block import get_block_height_at_hash, get_block_metadata_at_height
from db.constants import LMDB_ENV, TX_HISTORY_DB
from db.index import get_block_index
from utils.helper import bytes_to_int, int_to_bytes


# I was thinking of implementing a cache but the up_to variable totally screwed over this idea
# Anyways this function is so friggin fast it takes << 1ms to load 30k+ entries (0.005ms on my pc)
# Really puts the lightning in LMDB
# Its so frickin fast I dont have to optimize it HOORAY!!

def get_tx_history(up_to=None) -> dict[bytes, tuple[int, int, int]]:
    """
    Returns a dictionary with key=tx_hash and value=tuple(coinbase_value, input_value, output_value)
    
    `up_to` (int | None): Returns history up to this days past if set, else returns full history
    """
    if up_to is None:
        max_detla = timedelta.max
    else:
        max_detla = timedelta(up_to)
    
    history = {}
    with LMDB_ENV.begin(db=TX_HISTORY_DB) as db:
        with db.cursor() as cur:
            if cur.last():
                while True: 
                    height, value = cur.item()

                    meta = get_block_metadata_at_height(bytes_to_int(height))
                    if not meta:
                        break

                    block_time = datetime.fromtimestamp(meta.timestamp)
                    if datetime.now().date() - block_time.date() > max_detla:
                        break
                    
                    tx_hash   = value[:32]
                    cb_value  = bytes_to_int(value[32:40])
                    in_value  = bytes_to_int(value[40:48])
                    out_value = bytes_to_int(value[48:56])
                    
                    history[tx_hash] = (cb_value, in_value, out_value)
                        
                    if not cur.prev():
                        break             
        
    return history



def append_tx_history(block: Block, pk_hash: bytes):
    """Saves all transactions that uses P2PKH and references `pk_hash` in `block` to TX_HISTORY_DB
    \nShould be done only after saving the block itself"""
    block_index = get_block_index(block.hash())

    
    with LMDB_ENV.begin(write=True, db=TX_HISTORY_DB) as db:
        for tx in block.get_transactions():
            tx_hash = tx.hash()
            
            total_in = total_out = 0
            for tx_in in tx.inputs:
                if script_pubkey := tx_in.script_pubkey():
                    if pk_hash == script_pubkey.get_script_pubkey_receiver():
                        total_in += tx_in.value() or 0
                        
            for tx_out in tx.outputs:
                if pk_hash == tx_out.script_pubkey.get_script_pubkey_receiver():
                    total_out += tx_out.value
                    
            if tx.is_coinbase():
                value = tx_hash + int_to_bytes(total_out, 8) + int_to_bytes(0, 8) + int_to_bytes(0, 8)
            else:
                value = tx_hash + int_to_bytes(0, 8) + int_to_bytes(total_in, 8) + int_to_bytes(total_out, 8)

            db.put(int_to_bytes(block_index.height, 8), value)
        
        
def delete_tx_history(height: int):
    with LMDB_ENV.begin(db=TX_HISTORY_DB) as db:
        with db.cursor() as cur:
            if cur.set_key(int_to_bytes(height, 8)):
                cur.delete(dup=True)


