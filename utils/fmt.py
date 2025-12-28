# Formatting / pretty print functions
from datetime import datetime
import math

from networking.constants import _SVC_FULL, _SVC_BETA


def print_compare_bytes(stuff1: bytes, stuff2: bytes) -> None:
    RESET = "\033[0m"
    BLUE = "\033[94m"  # Top row
    GREEN = "\033[92m"  # Matching byte
    RED = "\033[91m"  # Different byte

    max_len = max(len(stuff1), len(stuff2))

    for i in range(0, max_len, 16):
        row1 = stuff1[i : i + 16]
        row2 = stuff2[i : i + 16]

        # Print top row in blue
        row1_str = " ".join(f"{BLUE}{b:02x}{RESET}" for b in row1)
        print(row1_str)

        # Print bottom row in green (if matching), red (if different), or white (if no counterpart)
        row2_str = []
        for j, b in enumerate(row2):
            if j < len(row1) and b == row1[j]:  # If it exists in row1 and matches
                row2_str.append(f"{GREEN}{b:02x}{RESET}")
            else:  # If it exists but differs
                row2_str.append(f"{RED}{b:02x}{RESET}")

        # Print bottom row (or just a blank line if row2 is empty)
        print(" ".join(row2_str))


def print_bytes(data: bytes):
    """Prints bytes in a properly aligned hex dump format."""
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]  # Slice 16-byte chunk

        # Hex representation
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        hex_part = (
            hex_part[:23] + " " + hex_part[23:] if len(chunk) > 8 else hex_part
        )  # Extra space after 8th byte

        # ASCII representation (printable characters or '.')
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        # Adjust spacing for the last row (if < 16 bytes)
        padding = "   " * (16 - len(chunk))  # Add spaces for missing hex values
        print(f"{i:08X}   {hex_part}{padding}  {ascii_part}")


def format_bytes(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


def format_age(seconds: int | float) -> str:
    seconds = int(seconds)
    minutes, s = divmod(seconds, 60)
    hours, m = divmod(minutes, 60)
    days, h = divmod(hours, 24)
    months, d = divmod(days, 30)
    years, mo = divmod(months, 12)

    # List of all units in order
    units = [("Y", years), ("M", mo), ("D", d), ("h", h), ("m", m), ("s", s)]

    # Find first non-zero unit
    for i, (_, value) in enumerate(units):
        if value > 0:
            start = i
            break
    else:
        start = len(units) - 1

    return " ".join(f"{value}{name}" for name, value in units[start:])

def format_epoch(epoch: int | float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%d %b %Y, %H:%M:%S")

def format_number(num) -> str:
    if abs(num) >= 1_000_000_000_000_000:
        return f"{num / 1_000_000_000_000_000:.1f}Q".rstrip("0").rstrip(".")
    elif abs(num) >= 1_000_000_000_000:
        return f"{num / 1_000_000_000_000:.1f}T".rstrip("0").rstrip(".")
    elif abs(num) >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    elif abs(num) >= 1_000_000:
        return f"{num / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    elif abs(num) >= 1_000:
        return f"{num / 1_000:.1f}K".rstrip("0").rstrip(".")
    else:
        return str(num)

def format_hashrate(x):
    HASH_UNITS = [
        (1e3,  "KH/s"),
        (1e6,  "MH/s"),
        (1e9,  "GH/s"),
        (1e12, "TH/s"),
        (1e15, "PH/s"),
        (1e18, "EH/s")
    ]
    for threshold, name in reversed(HASH_UNITS):
        if x >= threshold:
            return f"{x/threshold:.2f} {name}"
    return f"{x:.2f} H/s"


def truncate_bytes(h: bytes | str, ends=2) -> str:
    if isinstance(h, bytes):
        h = h.hex()
    
    if len(h) < ends * 4:
        return h #type: ignore
    return h[:ends*2] + "...." + h[-ends*2:]  #type: ignore


def format_snake_case(text, all_words=True):
    """
    Repalces underscores with spaces and capitalizes each word is `all_words` is set.
    
    Example: oh_hell_naw -> Oh Hell Naw
    """
    words = text.split("_")
    if all_words:
        return " ".join(w[0].upper() + w[1:] for w in words)
    else:
        return " ".join(words).capitalize()
    

def services_to_str(services: bytes):
    svcs = []
    if services & _SVC_BETA:
        svcs.append("NODE_BETA")
    
    if services & _SVC_FULL:
        svcs.append("NODE_FULL")
        
    return ", ".join(svcs)