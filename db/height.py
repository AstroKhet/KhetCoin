



from db.constants import HEIGHT_DB, LMDB_ENV
from utils.helper import bytes_to_int, int_to_bytes

def get_blockchain_height():
    # Returns the height of the latest block stored in this node
    with LMDB_ENV.begin(db=HEIGHT_DB) as db:
        with db.cursor() as cur:
            if cur.last():
                return bytes_to_int(cur.key())
            else:
                return -1

def save_height(height: int, block_hash: bytes):
    with LMDB_ENV.begin(db=HEIGHT_DB, write=True) as db:
        db.put(int_to_bytes(height, 8), block_hash)
        
def delete_height(height: int):
    with LMDB_ENV.begin(db=HEIGHT_DB, write=True) as db:
        db.delete(int_to_bytes(height, 8))  
        
def get_block_hash_at_height(height: int | bytes) -> bytes | None:
    """
    Takes in a height as int or bytes and returns the corresponding block hash
    """
    if isinstance(height, int):
        height = int_to_bytes(height, 8)
    with LMDB_ENV.begin(db=HEIGHT_DB) as db:
        return db.get(height)