from blockchain.transaction import Transaction
from crypto.hashing import HASH256
from db.constants import LMDB_ENV, MEMPOOL_DB



def load_mempool() -> list[bytes]:
    raw_txs = []

    with LMDB_ENV.begin(db=MEMPOOL_DB, write=False) as txn:
        cursor = txn.cursor()
        for tx_hash, raw_tx in cursor:
            raw_txs.append(raw_tx)


    return raw_txs
    
    
def save_mempool(raw_txs: list[bytes]):
    with LMDB_ENV.begin(db=MEMPOOL_DB, write=True) as db:
        db.drop(MEMPOOL_DB, delete=False)  # clear existing entries
        for raw_tx in raw_txs:
            db.put(HASH256(raw_tx), raw_tx)
