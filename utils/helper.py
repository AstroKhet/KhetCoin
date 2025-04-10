from typing import BinaryIO
import ipaddress

from sphinx import ret


def letoi(le: bytes) -> int:
    """Little-endian bytes to integer."""
    return int.from_bytes(le, 'little')

def itole(i: int, num_bytes: int = 4) -> bytes:
    """Integer to little-endian bytes."""
    return i.to_bytes(num_bytes, 'little')

def betoi(be: bytes) -> int:
    """Big-endian bytes to integer."""
    return int.from_bytes(be, 'big')

def itobe(i: int, num_bytes: int = 4) -> bytes:
    """Integer to big-endian bytes."""
    return i.to_bytes(num_bytes, 'big')


def read_varint(stream: BinaryIO) -> int:
    """Reads a variable integer from the stream."""
    i = stream.read(1)[0]
    match i:
        case 0xfd:
            return letoi(stream.read(2))
        case 0xfe:
            return letoi(stream.read(4))
        case 0xff:
            return letoi(stream.read(8))
        case _:
            return i

def encode_varint(i: int) -> bytes:
    """Encodes an integer as a variable integer."""
    if i < 0xfd:
        return bytes([i])
    elif i <= 0xffff:
        return b'\xfd' + itole(i)
    elif i <= 0xffffffff:
        return b'\xfe' + itole(i)
    else:  # assumes i <= 0xffffffffffffffff
        return b'\xff' + itole(i)

def str_ip(addr: tuple, name="") -> str:
    if name:
        return f"{addr[0]}:{addr[1]} ({name})"
    else:
        return f"{addr[0]}:{addr[1]}"
    
def encode_ip_address(ip: bytes | str) -> bytes:
    """Convert IP to 16-byte Bitcoin format"""
    if ip is None:
        return bytes(16)  # Default empty

    # Handle bytes input
    if isinstance(ip, bytes):
        if len(ip) == 4:
            return ip + bytes(12)  # IPv4 -> IPv6
        if len(ip) == 16:
            return ip  # Already IPv6
        raise ValueError("IP bytes must be 4 or 16 bytes")

    # Handle string input
    if isinstance(ip, str):
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.packed + bytes(12) if ip_obj.version == 4 else ip_obj.packed

    raise TypeError("IP must be str or bytes")


def format_ip_address(ip_bytes: bytes) -> str:
    """Convert 16-byte Bitcoin format to IP string"""
    try:
        if ip_bytes[4:] == bytes(12):  # IPv4
            return str(ipaddress.IPv4Address(ip_bytes[:4]))
        return str(ipaddress.IPv6Address(ip_bytes))
    except:
        return ip_bytes.hex()
