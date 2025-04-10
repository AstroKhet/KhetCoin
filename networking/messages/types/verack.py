from typing import BinaryIO


class VerackMessage:
    command = b"verack"

    def __init__(self):
        self.payload = b""

    def __str__(self):
        return f"[verack]"

    @classmethod
    def parse(cls, _stream: BinaryIO):
        return cls()
