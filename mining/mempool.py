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
        self._valid_txns: dict[bytes, Transaction] = dict()

        # 2. Orphan transactions & utility variables
        self._orphan_txns:         dict[bytes, Transaction]            = dict()
        self._orphan_missing_utxo: dict[bytes, set[tuple[bytes, int]]] = dict()
        self._orphan_registry:     dict[tuple[bytes, int], bytes]      = dict()

        # 3. Time where transaction was added to mempool / orphan pool
        self._time_log: dict[bytes, int] = dict()

        # 3. Stores UTXOs spent in current mempool
        self._spent_mempool_utxos: set[tuple[bytes, int]] = set()
        
        # 4. Transient variables for efficient GUI updating
        self._updated_valids = False
        self._updated_orphans = False

    def add_tx(self, tx: Transaction) -> bool:
        match self.get_mempool_eligibility(tx):
            case "orphan":
                if tx.verify(allow_orphan=True):
                    tx_hash = tx.hash()
                    self._orphan_txns[tx_hash] = tx
                    self._time_log[tx_hash] = int(time.time())
                    
                    self._updated_orphans = True
                    log.info("Successfully saved to orphan pool")
                else:
                    log.warning("Failed to verify orphan tx")
                    return False
                
            case "valid":
                if tx.verify():
                    if tx.fee() < MIN_RELAY_TX_FEE:
                        log.warning(f"Tx fee ({tx.fee()} khets) is too low (Min: {MIN_RELAY_TX_FEE} khets)")
                        return False
                    tx_hash = tx.hash()
                    self._valid_txns[tx_hash] = tx
                    self._time_log[tx_hash] = int(time.time())
                    
                    self._updated_valids = True
                    log.info("Successfully saved to valid mempool")
                else:
                    log.warning("Failed to verify tx")
                    return False
            case _:
                return False
 
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

    def get_mempool_eligibility(self, tx: Transaction) -> str:
        """
        Returns the mempool status of a new transaction,
        which is either "valid" | "orphan" | "invalid"
        """
        
        tx_hash = tx.hash()
        status = "valid"
        log.info(f"Checking mempool eligibility for TX<{tx_hash.hex()}>")
        
        
        # Check if new transaction double spends UTXOs
        #   a) If tx does not exist, store as orphan
        #   b) If tx exists but output id is out of bounds, reject.
        #   c) If tx exists but is not part of UTXO set, reject (double spend)
        #   d) If tx exists but is is self._spent_mempool_utxos, reject (double spend)
        #   e) If tx exists and is part of UTXO set, accept
        if tx.is_coinbase():
            log.warning("Coinbase transactions should not be relayed. Rejected from mempool.")
            return "invalid"

        for i, input in enumerate(tx.inputs):
            prev_tx_hash = input.prev_tx_hash
            prev_id = input.prev_index
            outpoint = (prev_tx_hash, prev_id)
            
            if outpoint in self._spent_mempool_utxos:
                log.warning(f"Input[{i}] double-spends mempool tx output: {(prev_tx_hash.hex(), prev_id)}")
                return "invalid"

            if utxo_raw := get_txn(prev_tx_hash):
                utxo = Transaction.parse_static(utxo_raw).outputs[prev_id]
                if not tx.verify_input(i, utxo.script_pubkey):
                    log.warning(f"Input[{i}] failed to verify.")
                    return "invalid"

            else: 
                log.info(f"No valid UTXO found for Input[{i}]. Checking through mempool...")
                mempool_tx = self._valid_txns.get(prev_tx_hash)
                if mempool_tx is None:  # Add into orphan pool
                    log.info(f"No UTXO found for Input[{i}]. Saved to orphan pool")
                    self._orphan_registry[outpoint] = tx_hash

                    if not self._orphan_missing_utxo.get(tx_hash):
                        self._orphan_missing_utxo[tx_hash] = set()
                    self._orphan_missing_utxo[tx_hash].add(outpoint)
                    status = "orphan"

                else:
                    try:
                        tx_out = mempool_tx.outputs[prev_id]
                    except KeyError:
                        log.warning(f"Mempool UTXO index referenced by Input[{i}] is out of bounds.")
                        return "invalid"
                    
                    if not tx.verify_input(i, tx_out.script_pubkey):
                        log.warning(f"Unlocking script for Input[{i}] failed")
                        return "invalid"
                    self._spent_mempool_utxos.add(outpoint)

        return status

    def get_valid_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._valid_txns.get(tx_hash, None)
    
    def get_orphan_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._orphan_txns.get(tx_hash, None)
    
    def get_tx(self, tx_hash: bytes) -> Transaction | None:
        # Get txn regardless as long as its in mempool
        return self.get_valid_tx(tx_hash) or self.get_orphan_tx(tx_hash)
    
    def get_tx_exists(self, tx_hash: bytes) -> bool:
        return tx_hash in self._valid_txns

    def get_all_valid_tx(self) -> list[Transaction]:
        return list(self._valid_txns.values())

    def get_all_orphan_tx(self) -> list[Transaction]:
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
            if self._valid_txns.get(tx_hash):
                # Blocks sent over may contain txns in the mempool not seen by you yet
                del self._valid_txns[tx_hash]

    # Modifiers for transient GUI variables
    
    def check_update_valids(self):
        """
        Checks if any transactions were added or removd from self._mempool 
        from the last time this function was called
        """
        updated = self._updated_valids
        self._updated_valids = False
        return updated

    def check_update_orphans(self):
        """
        Checks if any transactions were added or removd from self._orphan_txns
        from the last time this function was called
        """
        updated = self._updated_orphans
        self._updated_orphans = False
        return updated