"""
Database functions for addr
Links pubkey_hash addresses to their UTXO set
"""

from io import BytesIO
from dataclasses import dataclass

from blockchain.script import Script
from blockchain.transaction import TransactionOutput
from db.constants import ADDR_DB, LMDB_ENV, UTXO_DB
from db.tx import get_tx_timestamp
from db.utxo import get_utxo
from utils.helper import bytes_to_int, int_to_bytes

@dataclass
class UTXO:
    owner: bytes
    value: int
    tx_hash: bytes
    index: int
    timestamp: int
    script_pubkey: Script


def save_utxo_to_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.put(addr, outpoint)


def delete_utxo_from_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.delete(addr, outpoint)


def get_addr_utxos(addr: bytes) -> list[UTXO]:
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
def get_addr_utxos_value(addr: bytes) -> int:
    if utxo_set :=  get_addr_utxos(addr):
        return sum(utxo.value for utxo in utxo_set)
    
    
def get_utxo_count(addr: bytes) -> int:
    """
    Retrieves no. of UTXOs that pay to `addr`
    """
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cursor = db.cursor()
        if cursor.set_key(addr):
            return cursor.count()
        else:
            return 0
