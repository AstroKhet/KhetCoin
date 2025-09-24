import random
from typing import BinaryIO

from utils.helper import int_to_bytes, bytes_to_int
 

class PongMessage:
    command = b"pong"

    def __init__(self, nonce: int = random.randint(0, 2**64 - 1)):
        self.nonce = nonce
        self.payload = int_to_bytes(nonce, 8)

    def __str__(self):
        return f"[pong] -> Nonce: {self.nonce}"

    @classmethod
    def parse(cls, stream: BinaryIO):
        nonce = bytes_to_int(stream.read(8))
        return cls(nonce)
