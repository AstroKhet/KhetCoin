import os
import re
from coincurve import PrivateKey, PublicKey
from pydantic import PrivateAttr

KEY_DATA_ACCESS_FOLDER = ".local/keys/"

def create_private_key() -> bytes:
    private_key_bytes = os.urandom(32)
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
    priv_key_path = os.path.join(KEY_DATA_ACCESS_FOLDER, f"{name}.dat")
    if os.path.exists(priv_key_path):
        raise ValueError(f"{name} already exists. Please choose a different name.")

    with open(priv_key_path, "wb") as private_key_dat:
        private_key_dat.write(priv_key_bytes)
    print(f"Private Key \"{name}\" saved at {priv_key_path}")


def get_private_key(name: str, raw: bool=True) -> bytes | PrivateKey:
    priv_key_path = os.path.join(KEY_DATA_ACCESS_FOLDER, f"{name}.dat")

    if not os.path.exists(priv_key_path):
        raise ValueError(f"No private key found with the name: \"{name}\"")

    with open(priv_key_path, "rb") as file:
        priv_key_bytes = file.read()

    if raw:
        return priv_key_bytes
    return PrivateKey(priv_key_bytes)


def get_public_key(name: str, raw: bool=True) -> bytes | PublicKey:
    priv_key: PrivateKey = get_private_key(name, raw=False)
    publ_key = priv_key.public_key
    if raw:
        return publ_key.format(compressed=True)
    return publ_key
