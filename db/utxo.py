import logging


from io import BytesIO
from dataclasses import dataclass

from blockchain.script import Script
from blockchain.transaction import TransactionOutput
from db.block import get_block_timestamp
from db.constants import ADDR_DB, LMDB_ENV, UTXO_DB
from db.tx import get_txn_timestamp
from utils.helper import bytes_to_int

@dataclass
class UTXO:
    owner: bytes
    value: int
    txn_hash: bytes
    index: int
    timestamp: int
    script_pubkey: Script


def get_utxo(outpoint: bytes) -> TransactionOutput | None:
    """
    outpoint (bytes): Txn Hash (32B) + Output Index (4B)
    """
    with LMDB_ENV.begin(db=UTXO_DB) as db:
        if tx_out := db.get(outpoint):
            return TransactionOutput.parse(BytesIO(tx_out))
        return None


def get_utxo_set(addr: bytes) -> list[UTXO]:
    # TODO: UTXO set caching
    utxo_set = []
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cur = db.cursor()
        if cur.set_key(addr):   # position at key
            for op in cur.iternext_dup():
                if tx_out := get_utxo(op):
                    txn_hash = op[:32]
                    idx = bytes_to_int(op[32:36])
                    utxo_set.append(
                        UTXO(
                            owner=addr,
                            value=tx_out.value,
                            txn_hash=txn_hash,
                            index=idx,    
                            timestamp=get_txn_timestamp(txn_hash) or 0,
                            script_pubkey=tx_out.script_pubkey
                        )
                    )
                else:
                    print(op.hex())
        
        return utxo_set
    
def get_utxo_count(addr: bytes) -> int:
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cursor = db.cursor()
        if cursor.set_key(addr):
            return cursor.count()
        else:
            return 0
