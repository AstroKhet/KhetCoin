from typing import BinaryIO
from blockchain.transaction import Transaction

class TxMessage:
    command = b"tx"

    def __init__(self, tx: Transaction | bytes):
        if isinstance(tx, Transaction):
            self.tx = self.payload = tx.serialize()
        else:
            self.tx = self.payload = tx

    def __str__(self):
        return f"[tx]\n{self.tx.hex()}"

    @classmethod
    def parse(cls, stream: BinaryIO):
        tx = Transaction.parse(stream)
        return cls(tx)
