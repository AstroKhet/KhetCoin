from typing import BinaryIO


class GetAddrMessage:
    # The 'getaddr' message sends a request to a node asking for information
    # about known active peers. This helps with discovering potential nodes
    # in the network.
    #
    # The typical response to receiving this message is to transmit one or more
    # 'addr' messages, each containing one or more peers from a database of
    # known active peers.
    #
    # A common presumption is that a node is likely to be active if it has sent
    # a message within the last three hours.
    command = b"getaddr"

    def __init__(self):
        self.payload = b""

    def __str__(self) -> str:
        return "[getaddr]"

    @classmethod
    def parse(cls, _stream: BinaryIO) -> "GetAddrMessage":
        return cls()  # no data
