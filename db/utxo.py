
# UTXO
# Key: Tx Hash (32L) + Index (4L)
# Value: Full Transaction Output

from io import BytesIO
import logging

from blockchain.transaction import Transaction, TransactionOutput
from db.constants import LMDB_ENV, UTXO_DB
from utils.helper import int_to_bytes

log = logging.getLogger(__name__)


def update_UTXO_set(txs: list[Transaction]):
    for tx in txs:
        for tx_in in tx.inputs:
            outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
            delete_utxo(outpoint)
            
        tx_hash = tx.hash()
        for i, tx_out in enumerate(tx.outputs):
            outpoint = tx_hash + int_to_bytes(i, 4)
            save_utxo(outpoint, tx_out)
            
    
def backtrack_UTXO_set(txs: list[Transaction]):
    for tx in txs:
        for tx_in in tx.inputs:
            if source_tx_out := tx_in.fetch_tx_output():
                outpoint = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_index)
                save_utxo(outpoint, source_tx_out)
            
        tx_hash = tx.hash()
        for i, tx_out in enumerate(tx.outputs):
            outpoint = tx_hash + int_to_bytes(i, 4)
            delete_utxo(outpoint, tx_out)


def save_utxo(outpoint: bytes, tx_out: TransactionOutput):
    with LMDB_ENV.begin(db=UTXO_DB) as db:
        db.put(outpoint, tx_out.serialize())


def delete_utxo(outpoint: bytes):
    with LMDB_ENV.begin(db=UTXO_DB) as db:
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
    