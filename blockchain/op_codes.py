from typing import List
from crypto.hashing import *

from coincurve import PublicKey, verify_signature

def op_dup(stack: List[bytes | int]) -> bool:
    """Duplicates the top stack item."""
    if stack:
        stack.append(stack[-1])
        return True
    return False


def op_hash160(stack: List[bytes | int]) -> bool:
    """Hashes the top stack item using HASH160()."""
    if stack:
        stack.append(HASH160(stack.pop()))
        return True
    return False


def op_hash256(stack: List[bytes | int]) -> bool:
    """Hashes the top stack item using HASH256()."""
    if stack:
        stack.append(HASH256(stack.pop()))
        return True
    return False


def op_equal(stack: List[bytes | int]) -> bool:
    """Checks if the top two stack items are equal."""
    if len(stack) < 2:
        return False
    stack.append(1 if stack.pop() == stack.pop() else 0)
    return True


def op_equalverify(stack: List[bytes | int]) -> bool:
    """Verifies equality of top two items and removes them if equal."""
    if not op_equal(stack):
        return False
    return stack.pop() == 1

def op_checksig(stack: List[bytes | int], msg_hash: bytes) -> bool:
    """Simulates a signature verification check."""
    if len(stack) < 2:
        return False

    pubkey_bytes = stack.pop()
    sig = stack.pop()[:-1]  # Remove the sighash byte

    valid_sig = verify_signature(sig, msg_hash, pubkey_bytes, hasher=None)
    stack.append(int(valid_sig))

    return True

######################################################
def op_checkmultisig(stack: List[bytes | int]) -> bool:
    """Simulates a multi-signature check."""
    if len(stack) < 3:
        return False
    n = stack.pop()  # Number of required signatures
    if len(stack) < n + 1:
        return False
    for _ in range(n):  # Simulated signature verification
        stack.pop()
    stack.pop()  # Number of public keys
    stack.append(1)  # Simulated success
    return True


def op_verify(stack: List[bytes | int]) -> bool:
    """Fails the script if the top stack item is zero."""
    if not stack or stack.pop() == 0:
        return False
    return True


def op_return(stack: List[bytes | int]) -> bool:
    """Marks the transaction as invalid."""
    return False  # Always fails the script


def op_nop(stack: List[bytes | int]) -> bool:
    """Does nothing (used for future soft forks)."""
    return True


OP_CODE_FUNCTIONS = {
    0x76: op_dup,
    0xA9: op_hash160,  
    0xAA: op_hash256, 
    0x87: op_equal,  
    0x88: op_equalverify, 
    0xAC: op_checksig,
    0xAE: op_checkmultisig, 
    0x69: op_verify,
    0x6A: op_return,
    0x61: op_nop,
}

OP_CODE_NAMES = {
    0x76: "OP_DUP",
    0xA9: "OP_HASH160",
    0xAA: "OP_HASH256",
    0x87: "OP_EQUAL",
    0x88: "OP_EQUALVERIFY",
    0xAC: "OP_CHECKSIG",
    0xAE: "OP_CHECKMULTISIG",
    0x69: "OP_VERIFY",
    0x6A: "OP_RETURN",
    0x61: "OP_NOP",
}
