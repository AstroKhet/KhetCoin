from typing import BinaryIO


class GetAddrMessage:
    command = "getaddr"

    def __init__(self):
        self.payload = b""

    def __str__(self) -> str:
        return "[getaddr]"

    @classmethod
    def parse(cls, _stream: BinaryIO) -> "GetAddrMessage":
        return cls()  # no data
