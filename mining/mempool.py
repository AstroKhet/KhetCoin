import logging
import time

from blockchain.transaction import Transaction
from db.tx import get_txn
from mining.constants import MIN_RELAY_TX_FEE

log = logging.getLogger(__name__)

class Mempool:
    """
    A Mempool object that stores verified & unconfirmed transactions. 
    Mempool object lifetime lasts as long as the Node's session
    """
    def __init__(self) -> None:
        # 1. Validated transactions are stored in mempool
        self._mempool: dict[bytes, Transaction] = dict()

        # 2. Orphan transactions & utility variables
        self._orphan_txns:         dict[bytes, Transaction]            = dict()
        self._orphan_missing_utxo: dict[bytes, set[tuple[bytes, int]]] = dict()
        self._orphan_registry:     dict[tuple[bytes, int], bytes]      = dict()

        # 3. Time where transaction was added to mempool / orphan pool
        self._time_log: dict[bytes, int] = dict()

        # 3. Stores UTXOs spent in current mempool
        self._spent_mempool_utxos: set[tuple[bytes, int]] = set()

    def add_tx(self, tx: Transaction) -> bool:
        if not self.check_mempool_eligibility(tx):
            return False
        
        tx_hash = tx.hash()
        self._mempool[tx_hash] = tx
        self._time_log[tx_hash] = int(time.time())

        # Check if any outputs satisfy as parents to orphan txns
        for i in range(len(tx.outputs)):
            outpoint = (tx_hash, i)
            if orphan_tx_hash := self._orphan_registry.get(outpoint):
                try:
                    self._orphan_missing_utxo[orphan_tx_hash].remove(outpoint)
                except (AttributeError, ValueError) as e:  # TODO: Should not happen
                    log.warning(f"Mismatch between orphan registry and awaiting orphan UTXO record: {e}")
                    continue

                if len(self._orphan_missing_utxo[orphan_tx_hash]) == 0:
                    adopted_tx = self._orphan_txns[orphan_tx_hash]
                    self.add_tx(adopted_tx)
                    del self._orphan_missing_utxo[orphan_tx_hash]
                    del self._orphan_txns[orphan_tx_hash]

                self._spent_mempool_utxos.add(outpoint)
                del self._orphan_registry[outpoint]

        return True

    def check_mempool_eligibility(self, tx: Transaction):
        log.info(f"Checking mempool eligibility for TX<{tx.hash()}>")
        if not tx.verify(allow_orphan=True):  
            return False

        if tx.is_coinbase():
            log.warning("Coinbase transactions should not be relayed. Rejected from mempool.")
            return False

        if tx.fee() < MIN_RELAY_TX_FEE:
            log.warning("Txn fee < MIN_RELAY_FEE. Rejected")
            return False

        # Intra-Txn Double spending checks already handled in tx.verify; don't need to worry about
        # duplicate tx outpoints below
        temp_seen_outputs = set()
        for i, input in enumerate(tx.inputs):
            prev_tx_hash = input.prev_tx_hash
            prev_id = input.prev_index
            outpoint = (prev_tx_hash, prev_id)

            # Trying to spend an output that another txn in the mempool has used
            if outpoint in self._spent_mempool_utxos or \
               outpoint in temp_seen_outputs:
                log.warning(f"Input[{i}] double-spends {(prev_tx_hash.hex(), prev_id)}")
                return False

            # 1. UTXO CHECK
            utxo_raw = get_txn(prev_tx_hash)
            if utxo_raw:
                utxo = Transaction.parse_static(utxo_raw).outputs[prev_id]
                if not tx.verify_input(i, utxo.script_pubkey):
                    log.warning(f"Input[{i}] failed to verify.")
                    return False

            # utxo_raw = get_utxo(*outpoint)
            # if utxo_raw:  # Verify Script
            #     utxo = TransactionOutput.parse(BytesIO(utxo_raw))
            #     if not tx.verify_input(i, utxo.script_pubkey):
            #         log.warning(f"Input[{i}] failed to verify.")
            #         return False

            else:  # 2. MEMPOOL CHECK if no UTXO found
                log.info(f"No valid UTXO found for Input[{i}]. Checking through mempool now...")

                mempool_tx = self._mempool.get(prev_tx_hash)
                if mempool_tx is None:
                    # Add into orphan pool
                    tx_hash = tx.hash()
                    self._orphan_txns[tx_hash] = tx
                    self._time_log[tx_hash] = int(time.time())
                
                    self._orphan_registry[outpoint] = tx_hash

                    if not self._orphan_missing_utxo.get(tx_hash):
                        self._orphan_missing_utxo[tx_hash] = set()
                    self._orphan_missing_utxo[tx_hash].add(outpoint)

                    log.warning(f"No mempool UTXO found for Input[{i}]. Saved to orphan pool")
                    continue

                elif not (0 <= prev_id < len(mempool_tx.outputs)):
                    log.warning(f"Mempool UTXO index referenced by Input[{i}] is out of bounds.")
                    return False

                else:
                    tx_out = mempool_tx.outputs[prev_id]
                    if not tx.verify_input(i, tx_out.script_pubkey):
                        log.warning(f"Unlocking script for Input[{i}] failed")
                        return False
                    self._spent_mempool_utxos.add(outpoint)

            temp_seen_outputs.add(outpoint)

        # Txn is eligible for mempool membership
        self._spent_mempool_utxos.update(temp_seen_outputs)
        return True

    def get_valid_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._mempool.get(tx_hash, None)
    
    def get_orphan_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._orphan_txns.get(tx_hash, None)
    
    def get_tx_exists(self, tx_hash: bytes) -> bool:
        return tx_hash in self._mempool

    def get_valid_txs(self) -> list[Transaction]:
        return list(self._mempool.values())


    def get_orphan_txs(self) -> list[Transaction]:
        return list(self._orphan_txns.values())

    def get_tx_time(self, tx_hash: bytes) -> int:
        """
        Returns the epoch time of when a transaction is added to the mempool, 
        both valid and orphan.
        """
        return self._time_log.get(tx_hash, 0)
    
    def remove_from_mempool(self, txn_hashes: list[bytes]):
        # Used when a new block is mined
        for tx_hash in txn_hashes:
            if self._mempool.get(tx_hash):
                # Blocks sent over may contain txns in the mempool not seen by you yet
                del self._mempool[tx_hash]
