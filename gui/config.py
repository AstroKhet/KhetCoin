# name: Main title of dropdown menu at the top left menu bar
# options: Dropdown menu options for each menu title. None refers to separator

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
        "options": ["your_wallet", "UTXO", "transaction_history", None, "pay"]
    },
    {
        "name": "network", 
        "options": ["node", "manage_peers"]
    },
]
