from typing import BinaryIO

from networking.constants import INV_LIMIT
from utils.helper import encode_varint, int_to_bytes, bytes_to_int, read_varint


class InvMessage:
    """
    Allows a node to advertise its knowledge of one or more objects. 
    It can be received unsolicited, or in reply to getblocks.
    """
    command = b"inv"
    def __init__(self, inventory: list[tuple[int, bytes]]):
        """
        inventory | list[tuple[int, bytes]]: A set containing the type and serialization of somedata
        
        Types:
        - 1: Transaction
        - 2: Block
        """
        self.inventory = inventory

        self.payload = encode_varint(len(inventory))
        for inv_type, inv_hash in inventory:
            self.payload += int_to_bytes(inv_type, 4) + inv_hash

    def __str__(self):
        lines = [f"[inv]"]
        for i, (inv_type, inv_hash) in enumerate(self.inventory):
            inv_type_name = "Tx" if inv_type == 1 else "block"
            lines.append(f"  Item {i} ({inv_type_name}): {inv_hash.hex()}")
        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO):
        count = read_varint(stream)
        if count > INV_LIMIT:
            # TODO: BANNNN
            return cls([])

        inventory = []
        # 0 - Error
        # 1 - Msg TX
        # 2 - Msg Block
        # 3 - Msg Merkle Block (SPV not implemented yet)
        for _ in range(count):
            inv_type = bytes_to_int(stream.read(4))
            inv_hash = stream.read(32)
            inventory.append((inv_type, inv_hash))
        return cls(inventory)
