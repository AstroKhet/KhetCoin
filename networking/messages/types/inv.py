from typing import BinaryIO, List

from utils.helper import encode_varint, itole, letoi, read_varint


class InvMessage:
    command = b"inv"

    def __init__(self, inventory: List[tuple]):
        """Hashes should all be in Little-Endian"""
        self.inventory = inventory

        self.payload = encode_varint(len(inventory))
        for inv_type, inv_hash in inventory:
            # inv_type: 1=Transaction, 2=Block
            self.payload += itole(inv_type, 4) + inv_hash

    def __str__(self):
        lines = [f"[inv]"]
        for i, (inv_type, inv_hash) in enumerate(self.inventory):
            inv_type_name = "Txn" if inv_type == 1 else "Blk"
            lines.append(f"  Item {i} ({inv_type_name}): {inv_hash.hex()}")
        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO):
        count = read_varint(stream)
        inventory = []
        for _ in range(count):
            inv_type = letoi(stream.read(4))
            inv_hash = stream.read(32)
            inventory.append((inv_type, inv_hash))
        return cls(inventory)
