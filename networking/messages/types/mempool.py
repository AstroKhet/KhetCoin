from typing import BinaryIO


class MempoolMessage:
    command = b"mempool"

    def __init__(self):
        self.payload = b""

    def __str__(self):
        return "[mempool]"

    @classmethod
    def parse(cls, _stream: BinaryIO):
        return cls()
