# NOTE: Do not modify any constants defined over here!
# These are hard coded to support the consensus mechanism of KhetCoin
# Modifying them WILL exclude you from the blockchain

# Genesis Block
GENESIS_HASH = bytes.fromhex(
    "0000074d9ce1bc6fa2c396897578693ac89d2de2b5f3c217ea9dd2fbd12b6961"
)
"""`bytes` The 32 Bytes Big-Endian hash of the very first block in KhetCoin."""


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


MAX_TARGET = 0xFFFF * pow(256, 0x1F - 3)
"""`int` Highest possible target value for mining. Also used for the first blocks in KhetCoin"""


MAX_BITS = bytes.fromhex("00ffff1f")
"""`bytes` Special byte representation of `MAX_TARGET`."""
