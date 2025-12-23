"""Column data for common Treeview widgets"""

MEMPOOL_TX_COLS = {
    "hash": ("Hash", 9),
    "from": ("From", 9),
    "to": ("To", 9),
    "amount": ("Amount", 15),
    "fees": ("Fee", 15),
    "received": ("Received", 9)
}


TX_LIST_COLS = {
    "index": ("Index", 8),
    "hash": ("Transaction Hash", 16),
    "from": ("From", 16),
    "to": ("To", 16),
    "amount": ("Amount", 12),
    "fees": ("Fee", 12),
}


BLOCK_LIST_COLS = {
    "height": ("Height", 12),
    "hash": ("Block Hash", 20),
    "age": ("Age", 40),
    "no_txs": ("No. txs", 12),
    "size": ("Size", 12),
    "sent": ("Total Sent", 12),
    "fees": ("Total Fees", 12)
}