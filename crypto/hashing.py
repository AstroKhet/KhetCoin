import hashlib


def RIPEMD160(s):
    """ripemd160 hash"""
    return hashlib.new("ripemd160", s).digest()


def SHA256(s):
    """sha256 hash"""
    return hashlib.sha256(s).digest()


def HASH160(s):
    """sha256 followed by ripemd160"""
    return RIPEMD160(SHA256(s))


def HASH256(s):
    """two rounds of sha256"""
    return SHA256(SHA256(s))
