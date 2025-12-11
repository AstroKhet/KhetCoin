import math
import logging

from crypto.hashing import HASH256

log = logging.getLogger(__name__)


class MerkleTree:
    def __init__(self, leaves: list[bytes]):
        if not leaves:  # Allow temporary stroage of empty merkle trees for convenience
            self.levels = []
            return
            
        cur = leaves[:]  

        self.levels = [cur]  # levels[0] = leaves
        
        # Build all levels
        while len(cur) > 1:
            if len(cur) % 2 == 1:
                cur = cur + [cur[-1]]   # duplicate last element
            
            parent_level = [
                HASH256(cur[i] + cur[i+1])
                for i in range(0, len(cur), 2)
            ]

            self.levels.append(parent_level)
            cur = parent_level


    def root(self) -> bytes | None:
        if not self.levels:
            return bytes(32)
        return self.levels[-1][0]


    def update_leaf(self, index: int, new_hash: bytes):
        """
        Incrementally updates the merkle tree when a leaf changes.
        Only recomputes O(log n) hashes.
        """
        if not self.levels:
            return
        
        # Update leaf
        self.levels[0][index] = new_hash

        cur_index = index

        # Recompute parents up the tree
        for level in range(len(self.levels) - 1):  # from leaf to second last
            parent_index = cur_index // 2

            level_nodes = self.levels[level]
            parent_nodes = self.levels[level + 1]

            # Determine left/right child
            left = level_nodes[cur_index & ~1]
            right = (
                level_nodes[cur_index | 1]
                if (cur_index | 1) < len(level_nodes)
                else left  # duplicate if odd
            )

            parent_nodes[parent_index] = HASH256(left + right)

            cur_index = parent_index  # move up

    def append_leaf(self, leaf_hash: bytes):
        if not self.levels:
            self.levels = [[leaf_hash]]
            return
        
        leaves = self.levels[0]
        leaves.append(leaf_hash)

        # Rebuild the tree top-down incrementally
        cur_index = len(leaves) - 1

        # Ensure each level exists
        while len(self.levels) < (cur_index.bit_length() + 1):
            self.levels.append([])

        for level in range(len(self.levels) - 1):
            nodes = self.levels[level]

            # Pad if needed
            if len(nodes) % 2 == 1:
                nodes.append(nodes[-1])

            parent_index = cur_index // 2
            parents = self.levels[level + 1]

            # Ensure parent array is long enough
            if parent_index >= len(parents):
                parents.extend([None] * (parent_index + 1 - len(parents)))

            left  = nodes[cur_index & ~1]
            right = nodes[cur_index | 1] if (cur_index | 1) < len(nodes) else left

            parents[parent_index] = HASH256(left + right)

            cur_index = parent_index
            
    # Helper: return leaf list
    def get_leaves(self):
        return self.levels[0]

    def copy(self):
        return MerkleTree(self.get_leaves())    
