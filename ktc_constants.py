# NOTE: Do not modify any constants defined over here!
# These are hard coded to support the consensus mechanism of KhetCoin
# Modifying them WILL exclude you from the blockchain


# KhetCoin App version
KTC_VERSION = "0.2.3"
"""Version of this current KhetCoin repo"""

# Genesis Block
GENESIS_HASH = bytes.fromhex(
    "00000000b660f929deb419fee2be91b4f53fc2bf9f2d2477d813a2701c1a2070"
)
"""`bytes` The 32 Bytes Big-Endian hash of the very first block in KhetCoin."""

GENESIS_BLOCK_BYTES = bytes.fromhex(
    "000000010000000000000000000000000000000000000000000000000000000000000000fc4cc459b5ac88b58c8943156a03b7c9eb440e06494a7ba2731920d2fd91a05a694d4d3900ffff1d3b3fee980100000001010000000000000000000000000000000000000000000000000000000000000000ffffffff510800000000000000004000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000062f4b6865742fffffffff01000000012a05f2001976a914cd228666a327389937cae12328bb1af3021af80588ac00000000"
)
"""`bytes` The byte representation of the genesis block. Using sha256 twice yields `GENESIS_HASH`"""

KTC = 100_000_000
"""`int` 1 KTC = 100_000_000 khets. khet is the lowest indivisible currecny unit in KhetCoin."""


INITIAL_BLOCK_REWARD = 50 * KTC
"""`int` The block reward (khets) for the first block; used to calculated subsequent block rewards after halving."""


MAX_KTC = 1_000_000 
"""`int` The maximum number of Khetcoins (in KTCs) designed to be in circulation."""


MAX_KHETS = MAX_KTC * KTC
"""`int` The maximum number of Khetcoins (in khets) designed to be in circulation. """


HALVING_INTERVAL = MAX_KHETS // (2 * INITIAL_BLOCK_REWARD)
"""`int` The number of blocks between each halving event."""


RETARGET_INTERVAL = 144
"""`int` The number of blocks between each time the block target is recalculated. Each block should take around 10 minutes to mine."""


ONE_DAY = 60 * 60 * 24
"""`int` The number of seconds in a day. Used together with `RETARGET_INTERVAL` to calculate block target."""


MAX_BLOCK_SIZE = 1 << 20  # 1 MB
"""`int` Maximum byte size for each block"""


HIGHEST_TARGET = 0xFFFF * pow(256, 0x1D - 3)
"""`int` Highest possible target value for mining. Also used for the first blocks in KhetCoin"""


HIGHEST_BITS = bytes.fromhex("00ffff1d")
"""`bytes` Special byte representation of `MAX_TARGET`."""
