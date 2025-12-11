import hashlib


def _ripemd160(s):
    """ripemd160 hash"""
    return hashlib.new("ripemd160", s).digest()


def _sha256(s):
    """sha256 hash"""
    return hashlib.sha256(s).digest()


def HASH160(s):
    """sha256 followed by ripemd160"""
    return _ripemd160(_sha256(s))


def HASH256(s):
    """two rounds of sha256"""
    return _sha256(_sha256(s))
