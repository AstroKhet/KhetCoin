# Genesis Block
GENESIS_HEADER = bytes.fromhex(
    ""
)
GENESIS_HASH = bytes.fromhex(
    "000000a56fc3ed0024b9516ca4f5433bec6c56137ab3dcccabaeb3a4bd60b262"
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
MIN_DIFFICULTY = 0xFFFF * pow(256, 0x1E - 3)  # Roughly 65537 hashes per block 
MIN_BITS = bytes.fromhex("00ffff1e")

# Peers (shift over to db.constants, networking.constants)
PEERS_SQL = ".local/peers.db"
PEER_INACTIVE_TIMEOUT = 3600 * 3  # 3 hours
MAX_PEERS = 8 
