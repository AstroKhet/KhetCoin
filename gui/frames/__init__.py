
from gui.frames.blockchain.mempool import MempoolFrame
from gui.frames.wallet.saved_addresses import SavedAddressesFrame
from gui.frames.blockchain.view_blockchain import ViewBlockchainFrame
from gui.frames.blockchain.mining import MiningFrame

from gui.frames.main.dashboard import DashboardFrame
from gui.frames.main.settings import SettingsFrame

from gui.frames.network.node import NodeFrame
from gui.frames.network.manage_peers import ManagePeersFrame
from gui.frames.network.saved_peers import SavedPeersFrame

from gui.frames.wallet.pay import PayFrame
from gui.frames.wallet.transaction_history import TransactionHistoryFrame
from gui.frames.wallet.utxo import UTXOFrame
from gui.frames.wallet.your_wallet import YourWalletFrame


FRAMES_CONFIG = {
    "dashboard": DashboardFrame,
    "settings": SettingsFrame,
    
    "view_blockchain": ViewBlockchainFrame,
    "mempool": MempoolFrame, 
    "mining": MiningFrame,
    
    "your_wallet": YourWalletFrame,
    "UTXO": UTXOFrame,
    "transaction_history": TransactionHistoryFrame,
    "pay": PayFrame,
    "saved_addresses": SavedAddressesFrame,
    
    "node": NodeFrame,
    "manage_peers": ManagePeersFrame,
    "saved_peers": SavedPeersFrame,
}


MENU_CONFIG = [
    {
        "name": "main", 
        "options": ["dashboard", None, "settings"]
    },
    {
        "name": "blockchain",
        "options": ["view_blockchain", None, "mempool", "mining"]
    },
    {
        "name": "wallet",
        "options": ["your_wallet", "UTXO", "transaction_history", None, "pay", "saved_addresses"]
    },
    {
        "name": "network", 
        "options": ["node", "manage_peers", None, "saved_peers"]
    },
]
