from crypto.hashing import HASH256

class MerkleTree:
    def __init__(self, leaves):
        """
        Initialize the MerkleTree with a list of leaf hashes (each as bytes).
        The tree is built immediately.
        """
        self.leaves = leaves
        self.levels = (
            []
        )  # levels[0] is the list of leaves; last level contains the Merkle root
        self.build_tree()

    def build_tree(self):
        """Build the Merkle tree using double SHA256 hashing."""
        current_level = self.leaves
        self.levels.append(current_level)
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # If there's no right node, duplicate the left node
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(HASH256(left + right))
            self.levels.append(next_level)
            current_level = next_level

    def get_merkle_root(self) -> bytes:
        """Return the Merkle root of the tree."""
        return self.levels[-1][0] if self.levels else None

    def generate_merkle_proof(self, indices):
        """
        Generate a Merkle proof for a list of leaf indices.

        Returns:
        - proof (list of hashes)
        - flag bits (list of 0s and 1s indicating provided vs. computed nodes)
        """
        proof = []
        flags = []
        included = set(indices)

        for level in self.levels[:-1]:  # Exclude root level
            new_included = set()
            for index in included:
                sibling_index = index ^ 1  # Toggle last bit
                if sibling_index in included:
                    flags.append(0)  # We will compute this node
                else:
                    if sibling_index < len(level):
                        proof.append(level[sibling_index])
                        flags.append(1)  # This hash is provided
                new_included.add(index // 2)
            included = new_included

        return proof, flags

    @staticmethod
    def validate_merkle_proof(leaves, indices, proof, flags, merkle_root):
        """
        Validate a Merkle proof for multiple leaves.

        Parameters:
          leaves      - The original leaf hashes (list of bytes).
          indices     - The indices of these leaves in the original tree.
          proof       - List of sibling hashes (bytes).
          flags       - List of 0s and 1s indicating provided vs. computed nodes.
          merkle_root - The expected Merkle root (bytes).

        Returns:
          True if the proof is valid, False otherwise.
        """
        computed = dict(zip(indices, leaves))
        proof_index = 0

        for flag in flags:
            new_computed = {}
            for index in computed:
                sibling_index = index ^ 1  # Toggle last bit
                if flag == 1:  # Provided hash
                    sibling = proof[proof_index]
                    proof_index += 1
                else:  # Compute sibling from known nodes
                    sibling = computed.get(sibling_index, computed[index])

                parent_index = index // 2
                if index % 2 == 0:
                    new_computed[parent_index] = HASH256(
                        computed[index] + sibling
                    )
                else:
                    new_computed[parent_index] = HASH256(
                        sibling + computed[index]
                    )

            computed = new_computed

        return computed.get(0, None) == merkle_root  # Check if root matches
