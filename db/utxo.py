
# UTXO
# Key: Tx Hash (32L) + Index (4L)
# Value: Full Transaction Output

from dataclasses import dataclass
from io import BytesIO
import logging

from blockchain.script import Script
from blockchain.transaction import Transaction, TransactionOutput
from db.constants import ADDR_DB, LMDB_ENV, UTXO_DB
from db.tx import get_tx_timestamp
from utils.helper import bytes_to_int, int_to_bytes

log = logging.getLogger(__name__)


@dataclass
class UTXO:
    owner: bytes
    value: int
    tx_hash: bytes
    index: int
    timestamp: int
    script_pubkey: Script
    

def update_UTXO_set(txs: list[Transaction]):
    for tx in txs:
        tx_hash = tx.hash()
        
        if not tx.is_coinbase():
            for tx_in in tx.inputs:
                outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
                delete_utxo(outpoint)
                
                if pk := tx_in.script_sig.get_script_sig_sender():
                    delete_utxo_from_addr(pk, tx_hash, tx_in.prev_index)
            
        
        for i, tx_out in enumerate(tx.outputs):
            outpoint = tx_hash + int_to_bytes(i, 4)
            save_utxo(outpoint, tx_out)
            
            if pk := tx_out.script_pubkey.get_script_pubkey_receiver():
                save_utxo_to_addr(pk, tx_hash, i)
            
    
def backtrack_UTXO_set(txs: list[Transaction]):
    for tx in txs[::-1]:
        tx_hash = tx.hash()
        
        for tx_in in tx.inputs:
            if source_tx_out := tx_in.fetch_tx_output():  # Coinbase inputs have no prev tx
                outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
                save_utxo(outpoint, source_tx_out)
                
                if pk := tx_in.script_sig.get_script_sig_sender():
                    save_utxo_to_addr(pk, tx_hash, tx_in.prev_index)
            
        
        for i, tx_out in enumerate(tx.outputs):
            outpoint = tx_hash + int_to_bytes(i, 4)
            delete_utxo(outpoint, tx_out)
            
            if pk := tx_out.script_pubkey.get_script_pubkey_receiver():
                delete_utxo_from_addr(pk, tx_hash, i)



def save_utxo(outpoint: bytes, tx_out: TransactionOutput):
    with LMDB_ENV.begin(write=True, db=UTXO_DB) as db:
        db.put(outpoint, tx_out.serialize())


def delete_utxo(outpoint: bytes):
    with LMDB_ENV.begin(write=True, db=UTXO_DB) as db:
        db.delete(outpoint)
    

def get_utxo(outpoint: bytes) -> TransactionOutput | None:
    """outpoint (bytes): tx Hash (32B) + Output Index (4B)"""
    with LMDB_ENV.begin(db=UTXO_DB) as db:
        if tx_out := db.get(outpoint):
            return TransactionOutput.parse(BytesIO(tx_out))
        return None


def get_utxo_exists(outpoint: bytes):
    with LMDB_ENV.begin(db=UTXO_DB) as db:
        return db.get(outpoint) is not None
    
    
# ADDR_DB
    
def save_utxo_to_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(write=True, db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.put(addr, outpoint)

def delete_utxo_from_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(write=True, db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.delete(addr, outpoint)
    
    
def get_utxo_set_to_addr(addr: bytes) -> list[UTXO]:
    """
    Retrieves all UTXOs that pay to `addr`
    """
    # TODO: UTXO set caching
    utxo_set = []
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cur = db.cursor()
        if cur.set_key(addr):   # position at key
            for op in cur.iternext_dup():
                if tx_out := get_utxo(op):
                    tx_hash = op[:32]
                    idx = bytes_to_int(op[32:36])
                    utxo_set.append(
                        UTXO(
                            owner=addr,
                            value=tx_out.value,
                            tx_hash=tx_hash,
                            index=idx,    
                            timestamp=get_tx_timestamp(tx_hash) or 0,
                            script_pubkey=tx_out.script_pubkey
                        )
                    )
        
        return utxo_set


# Misc supporting functions used for GUI specific tasks
def get_utxo_value_to_addr(addr: bytes) -> int:
    if utxo_set :=  get_utxo_set_to_addr(addr):
        return sum(utxo.value for utxo in utxo_set)
    return 0
    
    
def get_utxo_count_to_addr(addr: bytes) -> int:
    """
    Retrieves no. of UTXOs that pay to `addr`
    """
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cursor = db.cursor()
        if cursor.set_key(addr):
            return cursor.count()
        else:
            return 0
    

    