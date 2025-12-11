from typing import BinaryIO, List

from crypto.hashing import HASH256
from utils.helper import encode_varint, int_to_bytes, bytes_to_int


class GetDataMessage:
    command = b"getdata"

    def __init__(self, inventory: List[tuple]):
        self.inventory = inventory

        self.payload = encode_varint(len(self.inventory))
        for inv_type, inv_hash in inventory:
            self.payload += int_to_bytes(inv_type, 4) + inv_hash

    def __str__(self):
        lines = [f"[getdata]"]
        for i, (inv_type, inv_hash) in enumerate(self.inventory):
            inv_type_name = "Tx" if inv_type == 1 else "Block"
            lines.append(f"  Item {i} ({inv_type_name}): {inv_hash.hex()}")

        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO):
        count = bytes_to_int(stream.read(1))
        inventory = []
        for _ in range(count):
            inv_type = bytes_to_int(stream.read(4))
            inv_hash = stream.read(32)
            inventory.append((inv_type, inv_hash))
        return cls(inventory)
