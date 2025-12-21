"""More complex database operations that require items from more than one db file (more to prevent circular imports lol)"""

import logging

from blockchain.block import Block
from crypto.hashing import HASH256
from db.block import get_block_dat_no, get_block_exists, get_block_height_at_hash, get_raw_block
from db.constants import BLOCK_MAGIC, BLOCKS_DB, DAT_SIZE, INDEX_DB, LMDB_ENV, TX_DB
from db.height import delete_height, get_blockchain_height, save_height
from db.index import BlockIndex, generate_block_index, get_block_index, get_fork_index
from db.tx_history import append_tx_history, delete_tx_history
from db.utxo import backtrack_UTXO_set, update_UTXO_set
from utils.config import APP_CONFIG
from utils.helper import encode_varint, int_to_bytes

log = logging.getLogger(__name__)
BLOCKCHAIN_DIR = APP_CONFIG.get("path", "blockchain")


def process_new_block(block, node):
    if not block.verify():
        return
    
    save_block_data(block)
    
    block_index = get_block_index(block.hash())

    # 1.1 Block extends active chain
    if block.prev_block == node.block_tip_index.hash:
        connect_block(block, node)
        
    # 2. Block extends forked chain
    else:
        if block_index.chainwork > node.block_tip_index.chainwork:
            reorg_blockchain(node.block_tip_index, block_index, node)
        else:
            # Nothing happens
            pass
        
    adopted = {o_block for o_block in node.orphan_blocks if get_block_exists(o_block.prev_block)}
    for o_block in adopted:
        process_new_block(o_block, node)
    
    node.orphan_blocks -= adopted

        
def connect_block(block: Block, node):
    """Extends `block` to the active blockchain
    
    This includes
    - Updating the UTXO set
    - Updating Mempool
    - Updating support DBs like HEIGHT_DB & TX_HISTORY_DB
    """
    block_index = get_block_index(block.hash())
    txs = block.get_transactions()
    
    # 1. Save to UTXO_DB (and ADDR_DB)
    update_UTXO_set(txs)
    
    # 2. Refresh mempool
    node.mempool.remove_mined_txs(txs)
    node.mempool.revalidate_mempool()
    
    # 3. Save to HEIGHT_DB
    print("HEIGHT", block_index.height)
    save_height(block_index.height, block.hash())
    
    # 4. Save to TX_HISTORY_DB
    append_tx_history(block, node.pk_hash)
    
    # 5. Set as blockchain tip 
    node.set_tip(block_index)
    
    # 6. Deal with orphans.


def disconnect_block(block: Block, node):
    """
    Backtracks `block` from the active blockchain
    """
    block_index = get_block_index(block.hash())
    txs = block.get_transactions()
    
    # 1. Backtrack UTXO set

    backtrack_UTXO_set(txs)
    
    # 2. Backtrack mempool
    for tx in txs:
        node.mempool.add_tx(tx)
        
    # 3. Remove from HEIGHT_DB
    delete_height(block_index.height)
    
    # 4. Remove from local TX_HISTORY_DB
    delete_tx_history(block_index.height)
    
    # 5. Set as blockchain tip 
    block_index = generate_block_index(block)
    node.set_tip(block_index)
    

def reorg_blockchain(old_tip_index: BlockIndex, new_tip_index: BlockIndex, node):
    fork_index = get_fork_index(old_tip_index, new_tip_index)
    
    # 1. Backtrack all blocks until fork point
    index = old_tip_index
    while index != fork_index:
        block = Block.parse(get_raw_block(index.hash))
        disconnect_block(block, node)
        index = index.get_prev_index()
        
    # 2. Extend all blocks until new tip
    index = new_tip_index
    
    to_connect = []
    while index != fork_index:
        block = Block.parse(get_raw_block(index.hash))
        to_connect.append(block)
        index = index.get_prev_index()
    
    for block in reversed(to_connect):
        connect_block(block, node)
        

        

def save_block_data(block) -> bool:
    """
    Pure function to save a full block.
    Block validation should be done outside this function
    """
    header = block.header
    header_raw = header.serialize()
    txs = block.get_transactions()
    raw_txs = [tx.serialize() for tx in txs]

    block_hash = block.hash()

    no_transactions_varint = encode_varint(len(txs))
    block_raw = header_raw + no_transactions_varint + b"".join(raw_txs)
    block_size = len(block_raw)

    # .dat file config
    dat_file_no = get_block_dat_no()
    dat_file = BLOCKCHAIN_DIR / f"blk{dat_file_no:08}.dat"
    dat_file.touch(exist_ok=True)

    offset = dat_file.stat().st_size
    if offset + block_size > DAT_SIZE:
        dat_file_no += 1
        dat_file = BLOCKCHAIN_DIR / f"blk{dat_file_no:08}.dat"
        dat_file.touch(exist_ok=True)

    # Saving data
    prev_hash = block.prev_block
    prev_index = get_block_index(prev_hash)
    height = prev_index.height + 1
    
    try:
        with open(dat_file, "ab") as dat:
            dat.write(BLOCK_MAGIC)
            dat.write(int_to_bytes(block_size))
            dat.write(block_raw)

        with LMDB_ENV.begin(write=True) as db:
            total_sent = 0
            total_fees = 0
            for tx in txs:
                total_fees += tx.fee()
                total_sent += sum(tx_out.value for tx_out in tx.outputs)

            # 1. Save to BLOCKS_DB
            block_value = (
                int_to_bytes(dat_file_no)
                + int_to_bytes(offset)
                + int_to_bytes(block_size)
                + int_to_bytes(header.timestamp)
                + int_to_bytes(len(txs))
                + int_to_bytes(total_sent, 8)
                + int_to_bytes(total_fees, 8)
                + int_to_bytes(height, 8)
            )
            db.put(block_hash, block_value, db=BLOCKS_DB)

            # 2. Save to INDEX_DB
            block_index = generate_block_index(block)
            db.put(block.hash(), block_index.serialize(), db=INDEX_DB)
            
            # 3. Save to TX_DB
            offset += 88 + len(no_transactions_varint)
            for i, tx in enumerate(raw_txs):
                tx_hash = HASH256(tx)
                tx_value = (
                    int_to_bytes(dat_file_no)
                    + int_to_bytes(offset)
                    + int_to_bytes(len(tx))
                    + int_to_bytes(i)
                    + int_to_bytes(height, 8)
                )
                db.put(tx_hash, tx_value, db=TX_DB)
                offset += len(tx)
                            
        return True
    
    except Exception as e:
        log.exception(f"Error attempting to save block: {e}")
        return False
    