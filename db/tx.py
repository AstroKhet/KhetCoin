import os

from io import BytesIO

from attr import dataclass
from db.block import get_block_hash_at_height, get_block_metadata, get_block_timestamp
from db.constants import BLOCKCHAIN_DIR, LMDB_ENV, TX_DB
from utils.helper import bytes_to_int, read_varint

@dataclass
class TransactionMetadata:
    txn_hash: bytes
    dat_no: int
    offset: int
    size: int
    pos: int
    height: int
    
    
    
def get_txn(tx_hash: bytes) -> bytes |  None:
    # 32B LE tx hash
    with LMDB_ENV.begin(db=TX_DB) as db:
        value = db.get(tx_hash)

        if value is None:
            return None

        dat_file_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])
        tx_size = bytes_to_int(value[8:12])

        dat_file = os.path.join(BLOCKCHAIN_DIR, f"blk{dat_file_no:08}.dat")
        stream = open(dat_file, 'rb')
        stream.seek(offset)
    
        return stream.read(tx_size)

def get_txn_metadata(tx_hash: bytes) -> TransactionMetadata | None:
    with LMDB_ENV.begin(db=TX_DB) as db:
        value = db.get(tx_hash)
        if value is None:
            return None
        dat_no = bytes_to_int(value[:4])
        offset = bytes_to_int(value[4:8])
        tx_size = bytes_to_int(value[8:12])
        pos = bytes_to_int(value[12:16])
        height = read_varint(BytesIO(value[16:]))
        
        return TransactionMetadata(
            txn_hash=tx_hash,
            dat_no=dat_no,
            offset=offset,
            size=tx_size,
            pos=pos,
            height=height
        )
        
def get_txn_height(tx_hash: bytes) -> int | None:
    meta = get_txn_metadata(tx_hash)
    if meta is not None:
        return meta.height
    return None


def get_txn_timestamp(tx_hash: bytes) -> int | None:
    meta = get_txn_metadata(tx_hash)
    if meta is not None:
        if blk_hash := get_block_hash_at_height(meta.height):
            if blk_meta := get_block_metadata(blk_hash):
                return blk_meta.timestamp
    return None


# Why isn't there a 'save_transaction' function? Because transactions must be saved
# together as a block on the blockchain (save_block), otherwise it stays in the mempool.

def get_tx_exists(tx_hash: bytes) -> bool:
    with LMDB_ENV.open(db=TX_DB) as db:
        return db.get(tx_hash) is not None

