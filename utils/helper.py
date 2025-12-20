from typing import BinaryIO
from io import BytesIO
import ipaddress

def bytes_to_int(be: bytes) -> int:
    """Big-endian bytes to integer."""
    return int.from_bytes(be, 'big')

def int_to_bytes(i: int, num_bytes: int = 4) -> bytes:
    """Integer to big-endian bytes."""
    return i.to_bytes(num_bytes, 'big')


def read_varint(stream: BinaryIO) -> int:
    """Reads a variable integer from the stream."""
    if isinstance(stream, bytes):
        stream = BytesIO(stream)
        
    i = stream.read(1)[0]
    match i:
        case 0xfd:
            return bytes_to_int(stream.read(2))
        case 0xfe:
            return bytes_to_int(stream.read(4))
        case 0xff:
            return bytes_to_int(stream.read(8))
        case _:
            return i

def encode_varint(i: int) -> bytes:
    """Encodes an integer as a Bitcoin-style variable integer."""
    if i < 0xfd:
        return bytes([i])
    elif i <= 0xffff:
        return b'\xfd' + int_to_bytes(i, 2)  # 2 bytes
    elif i <= 0xffffffff:
        return b'\xfe' + int_to_bytes(i, 4)  # 4 bytes
    else:  # i <= 0xffffffffffffffff
        return b'\xff' + int_to_bytes(i, 8)  # 8 bytes


def encode_ip(ip: bytes | str | int) -> bytes:
    """Encode IP (str, bytes, or int) into 16-byte Bitcoin format."""
    ip_obj = ipaddress.ip_address(ip)

    if isinstance(ip_obj, ipaddress.IPv4Address):
        return b"\x00" * 10 + b"\xff" * 2 + ip_obj.packed
    else:
        return ip_obj.packed


def format_ip(ip_bytes: bytes) -> str:
    """Convert 16-byte or 4-byte Bitcoin IP format to string."""
    if len(ip_bytes) == 4:
        return str(ipaddress.IPv4Address(ip_bytes))

    elif len(ip_bytes) == 16:
        if ip_bytes[:12] == b"\x00" * 10 + b"\xff" * 2:  # IPv6 mapped IPv4
            return str(ipaddress.IPv4Address(ip_bytes[12:]))
        else:
            return str(ipaddress.IPv6Address(ip_bytes))

    else:
        return ""


def bits_to_target(bits: bytes):
    return bytes_to_int(bits[:3]) * pow(256, bits[3] - 3)


def target_to_bits(target: int):
    raw = target.to_bytes(32, byteorder="big").lstrip(b"\x00")
    size = len(raw)

    if size <= 3:
        mantissa = int.from_bytes(raw, "big") << (8 * (3 - size))
    else:
        mantissa = int.from_bytes(raw[:3], "big")

    if mantissa & 0x00800000:
        mantissa >>= 8
        size += 1
    
    return int_to_bytes(mantissa, 3) + int_to_bytes(size, 1)
