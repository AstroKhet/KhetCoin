import os
import re

import base58
from coincurve import PrivateKey, PublicKey

from crypto.hashing import HASH160, HASH256
from utils.config import APP_CONFIG

KEYS_DIR = APP_CONFIG.get("path", "keys")


def create_private_key(prefix="") -> bytes:
    while True:
        private_key_bytes = os.urandom(32)
        priv_key = PrivateKey(private_key_bytes)

        addr = HASH160(priv_key.public_key.format(compressed=True))
        wif = wif_encode(addr)

        # Skip the leading '1'
        if wif[1:].startswith(prefix):
            return private_key_bytes
        

def save_private_key(priv_key: bytes | PrivateKey, name: str = "") -> None:
    if isinstance(priv_key, PrivateKey):
        priv_key_bytes = priv_key.secret
    else:
        priv_key_bytes = priv_key

    if len(priv_key_bytes) != 32:
        raise ValueError("Private Key must be 32 bytes long")

    if name == "":
        raise ValueError("Name cannot be empty!")

    # Check if name contains only letters and numbers
    if not re.match(r"^[\w\s]+$", name):
        raise ValueError("Name must contain only letters and numbers.")

    # Check if the name already exists
    priv_key_path = KEYS_DIR / f"{name}.dat"
    if priv_key_path.exists():
        raise ValueError(f"{name} already exists. Please choose a different name.")

    with open(priv_key_path, "wb") as private_key_dat:
        private_key_dat.write(priv_key_bytes)
    print(f"Private Key \"{name}\" saved at {priv_key_path}")


def get_private_key(name: str, raw: bool=True) -> bytes | PrivateKey:
    priv_key_path = KEYS_DIR / f"{name}.dat"

    if not priv_key_path.exists():
        raise ValueError(f"No private key found with the name: \"{name}\"")

    with open(priv_key_path, "rb") as file:
        priv_key_bytes = file.read()

    if raw:
        return priv_key_bytes
    return PrivateKey(priv_key_bytes)


def get_public_key(name: str, raw: bool=True) -> bytes | PublicKey:
    """
    Returns the 33B compressed SEC format of the public key
    1B Y-parity + 32B X-coordinate
    """
    priv_key: PrivateKey = get_private_key(name, raw=False) # type: ignore
    publ_key = priv_key.public_key
    if raw:
        return publ_key.format(compressed=True)
    return publ_key


def wif_encode(addr: bytes | str, version=b"\x00") -> str:
    if isinstance(addr, str):
        try:
            addr = bytes.fromhex(addr)
        except ValueError:
            return addr
        
    pre = version + addr
    checksum = HASH256(pre)[:4]
    code = pre + checksum
    
    return base58.b58encode(code).decode()

def wif_decode(wif: str) -> bytes | None:
    try:
        decode = base58.b58decode(wif)
    except ValueError:
        return None
    version = decode[:1]
    addr = decode[1:-4]
    checksum = decode[-4:]
    if HASH256(version + addr)[:4] != checksum:
        return None
    
    return addr


def private_key_to_wif(private_key_raw):
    addr = HASH160(PrivateKey(private_key_raw).public_key.format(compressed=True))
    wif = wif_encode(addr)
    return wif