import time
from typing import BinaryIO

from crypto.hashing import HASH256
from networking.constants import PROTOCOL_VERSION, NETWORK_PORT, SERVICES
from utils.helper import encode_ip_address, format_ip_address, itole, letoi

 
class VersionMessage:
    command = b"version"
    def __init__(
        self, version: int = PROTOCOL_VERSION, services: int = SERVICES, timestamp: int = int(time.time()),
        recver_services: int = 0, recver_ip: bytes | str = "", recver_port: int = NETWORK_PORT,
        sender_services: int = 0, sender_ip: bytes | str = "", sender_port: int = NETWORK_PORT,
        nonce: int = 0,
        user_agent: bytes = b"/Khetcoin:0.1/",  # This is probably never changing lol
        start_height: int = 0,
        relay: bool = False,
    ):
        self.version = version
        self.services = services
        self.timestamp = timestamp

        self.recver_services = recver_services
        self.recver_ip = encode_ip_address(recver_ip)
        self.recver_port = recver_port
        self.recver_addr = itole(recver_services, 8) + self.recver_ip + itole(recver_port, 2)

        self.sender_services = sender_services
        self.sender_ip = encode_ip_address(sender_ip)
        self.sender_port = sender_port
        self.sender_addr = itole(sender_services, 8) + self.sender_ip + itole(sender_port, 2)

        self.nonce = nonce
        self.user_agent = user_agent
        self.start_height = start_height
        self.relay = relay  # ?

        self.payload = (
            itole(self.version, 4) + itole(self.services, 8) + itole(self.timestamp, 8)
            + self.recver_addr
            + self.sender_addr
            + itole(self.nonce, 8)
            + itole(len(self.user_agent), 1) + self.user_agent
            + itole(self.start_height, 4) + itole(self.relay, 1)
        )

        self.length = len(self.payload)
        self.checksum = HASH256(self.payload)[:4]

    def __str__(self):
        timestamp = time.strftime("%d %m %y %H:%M", time.localtime(self.timestamp))
        lines = [
            "[version]",
            f"  Version:    {self.version}",
            f"  Services:   {hex(self.services)}",
            f"  Timestamp:  {self.timestamp} ({timestamp})",
            "",
            "  Receiver:",
            f"    Services: {hex(self.recver_services)}",
            f"    IP:       {format_ip_address(self.recver_ip)}",
            f"    Port:     {self.recver_port}",
            "",
            "  Sender:",
            f"    Services: {hex(self.sender_services)}",
            f"    IP:       {format_ip_address(self.sender_ip)}",
            f"    Port:     {self.sender_port}",
            "",
            f"  Nonce:      {self.nonce}",
            f"  User Agent: {self.user_agent.decode(errors='replace')}",
            f"  Start Height: {self.start_height}",
            f"  Relay:      {self.relay}",
            f"  Length:     {self.length} bytes",
            f"  Checksum:   {self.checksum.hex()}",
        ]
        return "\n".join(lines)

    @classmethod
    def parse(cls, stream: BinaryIO):
        version = letoi(stream.read(4))
        services = letoi(stream.read(8))
        timestamp = letoi(stream.read(8))

        recver_services = letoi(stream.read(8))
        recver_ip = stream.read(16) 
        recver_port = letoi(stream.read(2))

        sender_services = letoi(stream.read(8))
        sender_ip = stream.read(16)
        sender_port = letoi(stream.read(2))
        
        nonce = letoi(stream.read(8))
        user_agent_length = letoi(stream.read(1))
        user_agent = stream.read(user_agent_length)
        start_height = letoi(stream.read(4))
        relay = bool(letoi(stream.read(1)))

        return cls(
            version, services, timestamp,
            recver_services, recver_ip, recver_port,
            sender_services, sender_ip, sender_port,
            nonce,
            user_agent,
            start_height,
            relay,
        )
