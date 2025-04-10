from typing import BinaryIO
from sqlalchemy import Transaction


class TxMessage:
    command = b"tx"

    def __init__(self, tx: Transaction):
        self.tx = tx = tx
        self.payload = tx.serialize()

    def __str__(self):
        return f"[tx]\n{self.tx}"

    @classmethod
    def parse(cls, stream: BinaryIO):
        tx = Transaction.parse(stream)
        return cls(tx)
