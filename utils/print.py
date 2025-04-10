import string

# Kinda just asked ChatGPT to write these functions cus im too lazy

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
