
from gui.frames.blockchain.mempool import MempoolFrame
from gui.frames.blockchain.view_blockchain import ViewBlockchainFrame

from gui.frames.main.dashboard import DashboardFrame

from gui.frames.network.node import NodeFrame
from gui.frames.network.peers import PeersFrame

from gui.frames.wallet.pay import PayFrame
from gui.frames.wallet.transaction_history import TransactionHistoryFrame
from gui.frames.wallet.utxo import UTXOFrame
from gui.frames.wallet.your_wallet import YourWalletFrame

FRAMES_CONFIG = {
    "dashboard": DashboardFrame,
    # "settings": SettingsFrame,
    "view_blockchain": ViewBlockchainFrame,
    "mempool": MempoolFrame, 
    "your_wallet": YourWalletFrame,
    "UTXO": UTXOFrame,
    "transaction_history": TransactionHistoryFrame,
    "pay": PayFrame,
    "node": NodeFrame,
    "manage_peers": PeersFrame,
    # "theme": ThemeFrame,
    # "appearance": AppearanceFrame,
}
