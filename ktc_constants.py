# Genesis Block
GENESIS_HEADER = bytes.fromhex(
    ""
)
GENESIS_HASH = bytes.fromhex(
    "0000074d9ce1bc6fa2c396897578693ac89d2de2b5f3c217ea9dd2fbd12b6961"
)

# 1 KTC = 10,000,000 khets (analogous to 1 satoshi)
KTC = 100_000_000

# 10,000 blocks before each halving
INITIAL_BLOCK_REWARD = 50 * KTC
MAX_KTC = 1_000_000  # Max KTC in circulation
MAX_KHETS = MAX_KTC * KTC
HALVING_INTERVAL = MAX_KHETS // (2 * INITIAL_BLOCK_REWARD)

# No. of confirmations before a coinbase output can be spent
COINBASE_MATURITY = 10

# Max size (in bytes) for each block
MAX_BLOCK_SIZE = 1 << 20  # 1 MB

# Mining difficulty and readjustment
MIN_DIFFICULTY = 0xFFFF * pow(256, 0x1F - 3)  # 
MIN_BITS = bytes.fromhex("00ffff1F")

# Peers (shift over to db.constants, networking.constants)
PEERS_SQL = ".local/peers.db"
PEER_INACTIVE_TIMEOUT = 3600 * 3  # 3 hours
MAX_PEERS = 8 
