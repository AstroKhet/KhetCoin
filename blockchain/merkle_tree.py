import math
import logging

from crypto.hashing import HASH256

log = logging.getLogger(__name__)

class MerkleTree:

    def __init__(self, leaves: list[bytes]):
        """
        Constructs a merkle tree based on the provided list of hashes
        """
        if not leaves:
            log.exception("Empty list passed into MerkleTree constructor!")
            return 
        
        self._merkle_tree = [leaves]  # Lower index represent leaves of tree
        
        n = len(leaves)
        while n > 1:
            if n % 2:
                leaves.append(leaves[-1])
                
            leaves = [
                HASH256(leaves[i] + leaves[i+1])
                for i in range(0, n, 2)
            ]
                
            n = len(leaves)
            
    
    def get_merkle_root(self):
        return self._merkle_tree[-1][0]
        
        
