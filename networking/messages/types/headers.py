from typing import BinaryIO, List

from jwt import encode

from utils.helper import encode_varint, read_varint


class HeadersMessage:
    command = b"headers"
    def __init__(self, headers: List[bytes]):
        self.headers = headers

        self.payload = encode_varint(len(headers))
        for header in headers:
            self.payload += header
            
    def __str__(self):
        lines = [f"[headers]"]
        for i, header in enumerate(self.headers):
            lines.append(f"  Header {i}: {header.hex()}")
        return "\n".join(lines)
    
    @classmethod
    def parse(cls, stream: BinaryIO):
        count = read_varint(stream)
        headers = []
        for _ in range(count):
            header_bytes = stream.read(80)
            stream.read(1)  # txn count for headers message is always 0
            headers.append(header_bytes)

        return cls(headers)