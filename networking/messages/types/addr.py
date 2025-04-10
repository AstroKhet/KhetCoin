from typing import BinaryIO, List

from utils.helper import encode_ip_address, format_ip_address, itole, letoi


class AddrMessage:
    command = b"addr"

    def __init__(self, addresses: List[tuple]):
        self.addresses = addresses

        self.payload = itole(len(addresses), 1)
        for timestamp, services, ip, port in addresses:
            self.payload += itole(timestamp, 4)
            self.payload += itole(services, 8)
            self.payload += encode_ip_address(ip)
            self.payload += itole(port, 2)

    def __str__(self):
        lines = [f"[addr]"]
        for i, (timestamp, services, ip, port) in enumerate(self.addresses):
            lines.append(f"  Address {i}:")
            lines.append(f"    Timestamp: {timestamp}")
            lines.append(f"    Services:  {hex(services)}")
            lines.append(f"    IP:        {format_ip_address(ip)}")
            lines.append(f"    Port:      {port}")

    @classmethod
    def parse(cls, stream: BinaryIO):
        count = letoi(stream.read(1))
        addresses = []
        for _ in range(count):
            timestamp = letoi(stream.read(4))
            services = letoi(stream.read(8))
            ip = stream.read(16)
            port = letoi(stream.read(2))
            addresses.append((timestamp, services, ip, port))
        return cls(addresses)
