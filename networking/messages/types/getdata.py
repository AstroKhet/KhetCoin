from typing import BinaryIO, List

from crypto.hashing import HASH256
from utils.helper import itole, letoi


class GetDataMessage:
    command = b"getdata"

    def __init__(self, inventory: List[tuple]):
        self.inventory = inventory

        self.payload = itole(len(inventory), 1)
        for inv_type, inv_hash in inventory:
            self.payload += itole(inv_type, 4) + inv_hash

        self.length = len(self.payload)
        self.checksum = HASH256(self.payload)[:4]

    def __str__(self):
        lines = [f"[getdata]"]
        for i, (inv_type, inv_hash) in enumerate(self.inventory):
            inv_type_name = "Txn" if inv_type == 1 else "Blk"
            lines.append(f"  Item {i} ({inv_type_name}): {inv_hash.hex()}")

        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO):
        count = letoi(stream.read(1))
        inventory = []
        for _ in range(count):
            inv_type = letoi(stream.read(4))
            inv_hash = stream.read(32)
            inventory.append((inv_type, inv_hash))
        return cls(inventory)
