# networking/messages/types/__init__.py
from .version import VersionMessage
from .verack import VerackMessage
from .getaddr import GetAddrMessage
from .addr import AddrMessage
from .inv import InvMessage
from .getdata import GetDataMessage
from .getblocks import GetBlocksMessage
from .getheaders import GetHeadersMessage
from .headers import HeadersMessage
from .block import BlockMessage
from .tx import TxMessage
from .mempool import MempoolMessage
from .ping import PingMessage
from .pong import PongMessage

# Grouped by protocol function for documentation
CORE_MESSAGES = [
    VersionMessage,  # Handshake
    VerackMessage,
    GetAddrMessage,  # Peer discovery
    AddrMessage,
    InvMessage,  # Data propagation
    GetDataMessage,
    GetBlocksMessage,  # Chain sync
    GetHeadersMessage,
    HeadersMessage,
    BlockMessage,
    TxMessage,  # Transactions
    MempoolMessage,
    PingMessage,  # Connection
    PongMessage
]

__all__ = [
    "VersionMessage",
    "VerackMessage",
    "GetAddrMessage",
    "AddrMessage",
    "InvMessage",
    "GetDataMessage",
    "GetBlocksMessage",
    "GetHeadersMessage",
    "HeadersMessage",
    "BlockMessage",
    "TxMessage",
    "MempoolMessage",
    "PingMessage",
    "PongMessage",
]

COMMAND_MAP = {msg.command: msg for msg in CORE_MESSAGES}
