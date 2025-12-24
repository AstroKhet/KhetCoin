
from io import BytesIO
from db.height import get_blockchain_height
from db.constants import INDEX_DB, LMDB_ENV
from db.height import get_block_hash_at_height
from utils.helper import bytes_to_int, int_to_bytes


class BlockIndex:
    def __init__(self, 
            block_hash: bytes, 
            prev_hash: bytes, 
            height: int, 
            chainwork: int, 
            flag=bytes(1)
        ):
        self.hash = block_hash
        self.prev_hash = prev_hash
        self.height = height
        self.chainwork = chainwork
        self.flag = flag
        
    def __str__(self):
        return (
            f"BlockIndex("
            f"height={self.height}, "
            f"hash={self.hash.hex()}, "
            f"prev={self.prev_hash.hex()}, "
            f"chainwork={self.chainwork}"
            f")"
        )
        
    @classmethod
    def parse(cls, stream):
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
        
        block_hash = stream.read(32)
        prev_hash = stream.read(32)
        height = bytes_to_int(stream.read(8))
        chainwork = bytes_to_int(stream.read(32))
        flag = stream.read(1)
        
        return cls(block_hash, prev_hash, height, chainwork, flag)
            
    def get_prev_index(self):
        with LMDB_ENV.begin(db=INDEX_DB) as db:
            prev_index = BlockIndex.parse(db.get(self.prev_hash))
            return prev_index

            
    def serialize(self):
        result =  self.hash
        result += self.prev_hash
        result += int_to_bytes(self.height, 8)
        result += int_to_bytes(self.chainwork, 32)
        result += self.flag
        return result
    
    def __eq__(self, other):
        return self.hash == other.hash


def get_block_index(block_hash: bytes):
    with LMDB_ENV.begin(db=INDEX_DB) as db:
        if raw_block := db.get(block_hash):
            return BlockIndex.parse(raw_block)
    return None
    
    
def generate_block_index(block):
    prev_hash = block.prev_block
    prev_index = get_block_index(prev_hash)
    
    return BlockIndex(
        block.hash(),
        prev_hash,
        prev_index.height + 1,
        prev_index.chainwork + block.work(),
    )
    
    
def get_block_tip_index():
    tip_hash = get_block_hash_at_height(get_blockchain_height())
    return get_block_index(tip_hash)
    

def get_fork_index(A: BlockIndex, B: BlockIndex):
    while A.height > B.height:
        A = A.get_prev_index()
        
    while B.height > A.height:
        B = B.get_prev_index()
        
    while A != B:
        A = A.get_prev_index()
        B = B.get_prev_index()
    
    return A