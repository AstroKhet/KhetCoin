from typing import BinaryIO
from blockchain.block import Block


class BlockMessage:
    command = b"block"

    def __init__(self, block: Block):
        self.block = self.payload = block.serialize()

    def __str__(self):
        return f"[block]\n{self.block}"

    @classmethod
    def parse(cls, stream: BinaryIO):
        block = Block.parse(stream)
        return cls(block)
