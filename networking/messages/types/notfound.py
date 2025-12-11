from typing import BinaryIO
from utils.helper import encode_varint, int_to_bytes, bytes_to_int, read_varint


class NotFoundMessage:
    """
    notfound is a response to a getdata, sent if any requested data items could not be relayed, 
    for example, because the requested transaction was not in the memory pool or relay set.
    """
    command = b"notfound"

    def __init__(self, inventory: list[tuple[int, bytes]]):
        self.inventory = inventory

        self.payload = encode_varint(len(inventory))
        for inv_type, inv_hash in inventory:
            # inv_type: 1=Transaction, 2=Block
            self.payload += int_to_bytes(inv_type, 4) + inv_hash

    def __str__(self):
        lines = [f"[notfound]"]
        for i, (inv_type, inv_hash) in enumerate(self.inventory):
            inv_type_name = "Tx" if inv_type == 1 else "Block"
            lines.append(f"  Item {i} ({inv_type_name}): {inv_hash.hex()}")
        return "\n".join(lines)
    
    @classmethod
    def parse(cls, stream: BinaryIO):
        count = read_varint(stream)
            
        inventory = []
        for _ in range(count):
            inv_type = bytes_to_int(stream.read(4))
            inv_hash = stream.read(32)
            inventory.append((inv_type, inv_hash))
        return cls(inventory)
