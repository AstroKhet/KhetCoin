
# Max no. of signature operations in one script
SIGOPS_LIMIT = 20

# SIGHASH bytes
SIGHASH_ALL = 0x01
SIGHASH_ONE = 0x02


TX_VERSION = 1

# The next 2 variables are used when creating transactions with the KhetCoin App with the P2PKH protocol to ensure fee rate stays above the minimum fee rate.

# On a high level, the size of an input = size of(prev_hash + prev_index + scrip_sig + sequence)
#
# Trivially, prev_hash (32B) + prev_index (4B) + sequence (4B) = 40 bytes.
# script_sig can be anything; but the P2PKH protocol restricts it to be [DER signature, pubkey (compressed, NOT hashed)]
# The DER signature can have a theoretical maximum of 72 + 1 (sighash) = 73 bytes, while the compressed pubkey will be fixed at 33 bytes.
# HOWEVER, the ECDSA module being used in KhetCoin (coincurve) uses libsecp256k1's secp256k1_ecdsa_sign, which 
# "will by default create signatures in the lower-S form", meaning the leading bit of s will NEVER be 1, and hence it is unnecessary
# to pad s with a leading 0x00 byte. This means that our maximum script_sig size is 72B
#
# Now, when serializing the script, we have 1B (script length) + 1B (OP_PUSHDATA1) + 72B + 1B (OP_PUSHDATA1) + 33B = 108B
# Which means max P2PKH input size = 40 + 108 = 148B
P2PKH_INPUT_SIZE = 148


# Size of output = size of (value + script_pubkey)
# Size of value = 8B
# Size of script_pubkey = 1B (script length) + 1B (OP_DUP) + 1B (OP_HASH160) + 1B (OP_PUSHDATA1) + 20B (pk hash) + 1B (OP_EQUAL_VERIFY) + 1B (OP_CHECKSIG) = 26B
# Size of output = 8 + 26 = 34B
P2PKH_OUTPUT_SIZE = 34