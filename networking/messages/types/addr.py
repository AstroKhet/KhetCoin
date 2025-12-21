from typing import BinaryIO, List
from utils.helper import encode_ip, format_ip, int_to_bytes, bytes_to_int, read_varint


class AddrMessage:
    command = b"addr"

    def __init__(self, addresses: List[tuple]):
        self.addresses = addresses

        self.payload = int_to_bytes(len(addresses), 1)

        for timestamp, services, ip, port in addresses:
            self.payload += int_to_bytes(timestamp, 4)
            self.payload += int_to_bytes(services, 8)
            self.payload += encode_ip(ip)
            self.payload += port.to_bytes(2)

    def __str__(self):
        lines = [f"[addr]"]
        for i, (timestamp, services, ip, port) in enumerate(self.addresses):
            lines.append(f"  Address {i}:")
            lines.append(f"    Timestamp: {timestamp}")
            lines.append(f"    Services:  {hex(services)}")
            lines.append(f"    IP:        {format_ip(ip)}")
            lines.append(f"    Port:      {port}")
        return "\n".join(lines)
        
    @classmethod
    def parse(cls, stream: BinaryIO):
        count = read_varint(stream)
        addresses = []
        for _ in range(count):
            timestamp = bytes_to_int(stream.read(4))
            services = bytes_to_int(stream.read(8))
            ip = stream.read(16)
            port = bytes_to_int(stream.read(2))
            addresses.append((timestamp, services, ip, port))
        return cls(addresses)
