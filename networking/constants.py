"""
Networking constants for supporting the Khetcoin P2P protocol. 
These should neither be configurable nor seen by the user normally.
"""

####################################
NETWORK_MAGIC = "BITE".encode()  # 42 49 54 45
NETWORK_PORT = 8666

PROTOCOL_VERSION = 201  # Current Khetcoin protocol version
SERVICES = 0  # No additional services

USER_AGENT = b"/Khetcoin:0.1/"
####################################

HANDSHAKE_TIMEOUT = 10  # seconds
CONNECTION_TIMEOUT = 10 
PING_TIMEOUT = 10
MAX_PEERS = 8


MAX_MESSAGE_SIZE = 8 * (1 << 10)  # Maximum allowable payload size (bytes) for messages = 8MB
MAX_TIME_DELTA = 10  # Maximum default allowable time differential (seconds) for messages

ADDR_LIMIT = 100  # Max no. of addresses allowed to be received in ADDR messages
INV_LIMIT = 10_000

GETADDR_LIMIT = 8  # Max no. of active addr to retrieve randomly from peers.db
GETBLOCKS_LIMIT = 500
GETHEADERS_LIMIT = 400

TX_TYPE = 0x01
BLOCK_TYPE = 0x02


