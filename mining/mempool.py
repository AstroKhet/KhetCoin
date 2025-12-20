import logging
import time

from blockchain.transaction import Transaction
from db.tx import get_tx
from db.utxo import get_utxo, get_utxo_exists
from utils.config import APP_CONFIG
from utils.helper import int_to_bytes

log = logging.getLogger(__name__)

class Mempool:
    """
    A Mempool object that stores verified & unconfirmed transactions. 
    Mempool object lifetime lasts as long as the Node's session
    """
    def __init__(self) -> None:
        # 1. Validated transactions are stored in mempool
        self._valid_txs: dict[bytes, Transaction] = dict()

        # 2. Orphan transactions & utility variables
        self._orphan_txs:         dict[bytes, Transaction]            = dict()
        self._orphan_missing_utxo: dict[bytes, set[tuple[bytes, int]]] = dict()
        self._orphan_registry:     dict[tuple[bytes, int], bytes]      = dict()

        # 3. Time where transaction was added to mempool / orphan pool
        self._time_log: dict[bytes, int] = dict()

        # 3. Stores UTXOs spent in current mempool
        self._spent_mempool_utxos: set[tuple[bytes, int]] = set()
        
        # 4. Transient variables for efficient GUI updating
        self._updated_valids = self._updated_orphans = 0

    def add_tx(self, tx: Transaction) -> bool:
        match self.get_mempool_eligibility(tx):
            case "orphan":
                if tx.verify(allow_orphan=True):
                    tx_hash = tx.hash()
                    self._orphan_txs[tx_hash] = tx
                    self._time_log[tx_hash] = int(time.time())
                    
                    for tx_in in tx.inputs:
                        outpoint = (tx_in.prev_tx_hash, tx_in.prev_index)
                        outpoint_bytes = tx_in.prev_tx_hash + int_to_bytes(tx_in.prev_id)
                        if not get_utxo_exists(outpoint_bytes):
                            self._orphan_registry[outpoint] = tx_hash
                            if not self._orphan_missing_utxo.get(tx_hash):
                                self._orphan_missing_utxo[tx_hash] = set()
                            self._orphan_missing_utxo[tx_hash].add(outpoint)
                        else:
                            self._spent_mempool_utxos.add(outpoint)
                            
                    self._updated_orphans = 0
                    log.info("Successfully saved to orphan pool")
                else:
                    log.warning("Failed to verify orphan tx")
                    return False
                
            case "valid":
                if tx.verify():
                    if (fee_rate := tx.fee_rate() * 1024) < APP_CONFIG.get("node", "min_relay_fee_rate"):
                        log.info(f"Valid transaction rejected as fee rate ({fee_rate} khets/KB) is too low. To change this, go to settings.")
                        return False
                    
                    for tx_in in tx.inputs:
                        outpoint = (tx_in.prev_tx_hash, tx_in.prev_index)
                        self._spent_mempool_utxos.add(outpoint)
                        
                    tx_hash = tx.hash()
                    self._valid_txs[tx_hash] = tx
                    self._time_log[tx_hash] = int(time.time())
                    
                    self._updated_valids = 0
                    log.info("Successfully saved to valid mempool")
                else:
                    log.warning("Failed to verify tx")
                    return False
            case _:
                return False
 
        # Check if any outputs satisfy as parents to orphan txs
        for i in range(len(tx.outputs)):
            outpoint = (tx_hash, i)
            if orphan_tx_hash := self._orphan_registry.get(outpoint):
                try:
                    self._orphan_missing_utxo[orphan_tx_hash].remove(outpoint)
                except (AttributeError, ValueError) as e:  # TODO: Should not happen
                    log.warning(f"Mismatch between orphan registry and awaiting orphan UTXO record: {e}")
                    continue

                if len(self._orphan_missing_utxo[orphan_tx_hash]) == 0:
                    adopted_tx = self._orphan_txs[orphan_tx_hash]
                    self.add_tx(adopted_tx)
                    del self._orphan_missing_utxo[orphan_tx_hash]
                    del self._orphan_txs[orphan_tx_hash]

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
        #   a) If prev_tx does not exist, store as orphan
        #   b) If prev_tx exists but output id is out of bounds, reject.
        #   c) If prev_tx exists but is not part of UTXO set, reject (double spend)
        #   d) If prev_tx exists but is is self._spent_mempool_utxos, reject (double spend)
        #   e) If prev_tx exists and is part of UTXO set, accept
        if tx.is_coinbase():
            log.warning("Coinbase transactions should not be relayed. Rejected from mempool.")
            return "invalid"

        for i, tx_in in enumerate(tx.inputs):
            prev_tx_hash = tx_in.prev_tx_hash
            prev_id = tx_in.prev_index
            outpoint = (prev_tx_hash, prev_id)
            outpoint_bytes = prev_tx_hash + int_to_bytes(prev_id)
            
            if outpoint in self._spent_mempool_utxos:
                log.warning(f"Input[{i}] double-spends mempool tx output: {(prev_tx_hash.hex(), prev_id)}")
                return "invalid"

            if utxo := get_utxo(outpoint_bytes):
                if not tx.verify_input(i, utxo.script_pubkey):
                    log.warning(f"Input[{i}] failed to verify.")
                    return "invalid"

            else:   # Not in UTXO set
                # Not in UTXO because the outpoint is i) spent or ii) exists in mempool 
                # i) See if outpoint exists in blockchain
                if tx_raw := get_tx(self.prev_tx_hash):
                    tx = Transaction.parse(tx_raw)
                    try:
                        _ = tx.outputs[self.prev_index]
                        log.warning("Outpoint references a spend UTXO. Rejected.")
                        return "invalid"
                    except IndexError:
                        log.warning("Outpoint references a valid transaction but an invalid index. Rejected.")
                        return "invalid"
                else:
                    log.info(f"Input[{i}] outpoint does not refer to any transaction in the blockchain. Checking mempool now...")

                # ii) See if its outpoint is in the mempool
                mempool_tx = self._valid_txs.get(prev_tx_hash)
                if mempool_tx is None:  # Added into orphan pool in add_tx
                    log.info(f"No UTXO found for Input[{i}].")
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
        return status

    def get_valid_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._valid_txs.get(tx_hash, None)
    
    def get_orphan_tx(self, tx_hash: bytes) -> Transaction | None:
        return self._orphan_txs.get(tx_hash, None)

    def get_all_valid_tx(self, explicit_sort=False) -> list[Transaction]:
        if explicit_sort:  # Used for block mining; transaction order must follow mempool addition order
            return list(sorted(self._valid_txs.values(), key=lambda tx: self._time_log[tx.hash()]))
        else:  # Although addition order is already preserved in self._valid_txs for python versions > 3.7
            return list(self._valid_txs.values())

    def get_all_orphan_tx(self) -> list[Transaction]:
        return list(self._orphan_txs.values())

    def get_tx_time(self, tx_hash: bytes) -> int:
        """Returns the epoch time of when a transaction is added to the mempool, both valid and orphan."""
        return self._time_log.get(tx_hash, 0)

    def get_total_fee(self) -> float:
        return sum(tx.fee() for tx in self._valid_txs.values())
    
    def get_total_size(self) -> float:
        if self._valid_txs:
            return sum(len(tx.serialize()) for tx in self._valid_txs.values())
        return 0
    
    def get_no_tx(self):
        return len(self._valid_txs.values())
        
    def remove_mined_txs(self, txs: list[Transaction]):
        for tx in txs:
            tx_hash = tx.hash()
            if self._valid_txs.pop(tx_hash, None) is None:
                self._orphan_txs.pop(tx_hash, None)
        
    def revalidate_mempool(self):
        """
        Used to completely revalidate every single transaction in the mempool. Used when blocks are added/removed
        \nThis function should ONLY be called after the UTXO set has updated to the latest version.
        """
        all_txs = list(self._valid_txs.values()) + list(self._orphan_txs.values())

        self._valid_txs = dict()
        self._orphan_txs = dict()
        self._orphan_missing_utxo = dict()
        self._orphan_registry = dict()
        
        self._updated_valids = self._updated_orphans = 0
        
        for tx in all_txs:
            self.add_tx(tx)
        
        
    # Modifiers for transient GUI variables
    def check_update_valids(self, i=1):
        """
        Checks if any transactions were added or removd from self._mempool from the last time this function was called.
        \n`i` is used as an ID for different frames.
        """
        updated = (self._updated_valids >> i) & 1 == 0
        self._updated_valids |= (1 << i)
        return updated

    def check_update_orphans(self, i=1):
        """
        Checks if any transactions were added or removd from self._orphan_txs from the last time this function was called.
        \n`i` is used as an ID for different frames.
        """
        updated = (self._updated_orphans >> i) & 1 == 0
        self._updated_orphans |= (1 << i)
        return updated