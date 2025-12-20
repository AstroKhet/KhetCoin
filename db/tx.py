

from dataclasses import dataclass
from db.block import get_block_metadata
from db.constants import LMDB_ENV, TX_DB
from db.height import get_block_hash_at_height
from utils.helper import bytes_to_int
from utils.config import APP_CONFIG

BLOCKCHAIN_DIR = APP_CONFIG.get("path", "blockchain")

@dataclass
class TransactionMetadata:
    tx_hash: bytes
    dat_no: int
    offset: int
    size: int
    pos: int
    height: int
    
    
    
def get_tx(tx_hash: bytes) -> bytes |  None:
    """
    Returns the full serialized transaction corresponding to `tx_hash`
    """
    with LMDB_ENV.begin(db=TX_DB) as db:
        value = db.get(tx_hash)

        if value is None:
            return None

        dat_file_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])
        tx_size = bytes_to_int(value[8:12])

        dat_file = BLOCKCHAIN_DIR / f"blk{dat_file_no:08}.dat"
        stream = open(dat_file, 'rb')
        stream.seek(offset)
    
        return stream.read(tx_size)

def get_tx_metadata(tx_hash: bytes) -> TransactionMetadata | None:
    with LMDB_ENV.begin(db=TX_DB) as db:
        value = db.get(tx_hash)
        if value is None:
            return None
        dat_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])
        tx_size = bytes_to_int(value[8:12])
        pos = bytes_to_int(value[12:16])
        height = bytes_to_int(value[16:24])
        
        return TransactionMetadata(
            tx_hash=tx_hash,
            dat_no=dat_no,
            offset=offset,
            size=tx_size,
            pos=pos,
            height=height
        )
        
def get_tx_height(tx_hash: bytes) -> int | None:
    meta = get_tx_metadata(tx_hash)
    if meta is not None:
        return meta.height
    return None


def get_tx_timestamp(tx_hash: bytes) -> int | None:
    meta = get_tx_metadata(tx_hash)
    if meta is not None:
        if block_hash := get_block_hash_at_height(meta.height):
            if block_meta := get_block_metadata(block_hash):
                return block_meta.timestamp
    return None


# Why isn't there a 'save_transaction' function? Because transactions must be saved
# together as a block on the blockchain (save_block), otherwise it stays in the mempool.

def get_tx_exists(tx_hash: bytes) -> bool:
    with LMDB_ENV.begin(db=TX_DB) as db:
        return db.get(tx_hash) is not None

