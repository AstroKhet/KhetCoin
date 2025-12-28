import logging
import time

from blockchain.transaction import Transaction
from db.mempool import load_mempool, save_mempool
from db.tx import get_tx_exists, get_tx_timestamp
from db.utxo import UTXO, get_utxo
from networking.constants import TX_TYPE
from networking.messages.types.inv import InvMessage
from utils.config import APP_CONFIG
from utils.helper import int_to_bytes

log = logging.getLogger(__name__)

class Mempool:
    """
    A Mempool object that stores verified & unconfirmed transactions. 
    Mempool object lifetime lasts as long as the Node's session
    """
    def __init__(self, node) -> None:
        self.node = node
        
        # 1. Validated transactions are stored in mempool
        self._valid_txs: dict[bytes, Transaction] = dict()

        # 2. Orphan transactions & utility variables
        self._orphan_txs:          dict[bytes, Transaction]            = dict()  # tx_hash to Transaction
        self._orphan_missing_utxo: dict[bytes, set[tuple[bytes, int]]] = dict()  # tx_hash to outpoint
        self._orphan_registry:     dict[tuple[bytes, int], bytes]      = dict()  # outpoint to tx_hash

        # 3. Time where transaction was added to mempool / orphan pool
        self._time_log: dict[bytes, int] = dict()

        # 3. Stores UTXOs spent in current mempool
        self.spent_mempool_utxos: set[UTXO] = set() 
        self.new_mempool_utxos_to_node: set[UTXO] = set()
        
        # 4. Transient variables for efficient GUI updating
        self._updated_valids = 0
        self._updated_orphans = 0

    def add_tx(self, tx: Transaction) -> bool:
        tx_hash = tx.hash()
        log.info(f"Attempting to add tx to mempool: <{tx_hash.hex()}>")
        
        if get_tx_exists(tx_hash) or (tx_hash in self._valid_txs.keys()) or (tx_hash in self._orphan_txs.keys()):
            log.info("Tx already exists.")
            return False
        
        tx_in_statuses = self.get_mempool_eligibility(tx)
        if "invalid" in tx_in_statuses:
            log.info("Invalid Tx.")
            return False
        
        is_orphan = "orphan" in tx_in_statuses
        if not tx.verify(allow_orphan=is_orphan):
            log.warning(f"Failed to verify tx: ({is_orphan=})")
            return False
        
        
        if is_orphan:
            self._orphan_txs[tx_hash] = tx
            self._updated_orphans = 0
            log.info("Successfully saved to orphan pool")
        else:
            # if (fee_rate := tx.fee_rate() * 1024) < APP_CONFIG.get("node", "min_relay_fee_rate"):
            #     log.info(f"Valid transaction <{tx.hash().hex()}> rejected as fee rate ({fee_rate} khets/KB) is too low.")
            #     return False
            
            self._valid_txs[tx_hash] = tx
            self._updated_valids = 0
            log.info("Successfully saved to mempool")
            
            self.node.broadcast(
                InvMessage(
                    [(TX_TYPE, tx_hash)]
                )
            )  # exclude=peer... too lazy to implement...
            
            
        time_added = int(time.time())
        self._time_log[tx_hash] = time_added
        
        for i, tx_in in enumerate(tx.inputs):
            status = tx_in_statuses[i]
            outpoint = (tx_in.prev_tx_hash, tx_in.prev_index)
    
            if status == "orphan":
                self._orphan_registry[outpoint] = tx_hash
                self._orphan_missing_utxo.setdefault(tx_hash, set()).add(outpoint)

            prev_tx_out = tx_in.fetch_tx_output() or self._valid_txs.get(tx_in.prev_tx_hash)[tx_in.prev_index]
            script_pk = prev_tx_out.script_pubkey
            timestamp = get_tx_timestamp(tx_in.prev_tx_hash) or self._time_log.get(tx_in.prev_tx_hash, 0) or 0
            utxo = UTXO(script_pk.get_script_pubkey_receiver(), tx_in.fetch_value(), tx_in.prev_tx_hash, tx_in.prev_index, timestamp, script_pk)
            self.spent_mempool_utxos.add(utxo)
            self.new_mempool_utxos_to_node.discard(utxo)
                    
        for i, tx_out in enumerate(tx.outputs):
            script_pk = tx_out.script_pubkey
            owner = script_pk.get_script_pubkey_receiver()
            if owner == self.node.pk_hash:
                utxo = UTXO(owner, tx_out.value, tx_hash, i, time_added, script_pk)
                self.new_mempool_utxos_to_node.add(utxo)
            
            # Check if any outputs satisfy as parents to orphan txs
            outpoint = (tx_hash, i)
            if orphan_tx_hash := self._orphan_registry.get(outpoint):
                self._orphan_missing_utxo[orphan_tx_hash].remove(outpoint)

                if not self._orphan_missing_utxo[orphan_tx_hash]:
                    adopted_tx = self._orphan_txs[orphan_tx_hash]
                    self.add_tx(adopted_tx)
                    del self._orphan_missing_utxo[orphan_tx_hash]
                    del self._orphan_txs[orphan_tx_hash]

                del self._orphan_registry[outpoint]
        return True

    def get_mempool_eligibility(self, tx: Transaction) -> str:
        """
        Returns the mempool status of a new transaction,
        which is either "valid" | "orphan" | "invalid"
        """
        tx_hash = tx.hash()
        status = "valid"
        tx_in_statuses = []
        log.info(f"Checking mempool eligibility for TX<{tx_hash.hex()}>")
        
        if tx.is_coinbase():
            log.warning("Coinbase transactions should not be relayed. Rejected from mempool.")
            return "invalid"

        for i, tx_in in enumerate(tx.inputs):
            prev_tx_hash = tx_in.prev_tx_hash
            prev_id = tx_in.prev_index
            
            # 1. Does prev_tx exist?
            if get_tx_exists(prev_tx_hash):
                script_pk = tx_in.fetch_script_pubkey()
                timestamp = get_tx_timestamp(tx_hash) or 0
                utxo = UTXO(script_pk.get_script_pubkey_receiver(), tx_in.fetch_value(), prev_tx_hash, prev_id, timestamp, script_pk) 
                # 1.1 YES prev_tx | NO prev_id 
                if tx_in.fetch_tx_output() is None:
                    log.info("Outpoint references a valid transaction but an invalid index. Rejected.")
                    tx_in_statuses.append("invalid")
                    continue
            
                # 1.2 YES prev_tx | YES prev_id 
                outpoint_bytes = prev_tx_hash + int_to_bytes(prev_id)
                if utxo := get_utxo(outpoint_bytes):
                    
                # 1.2.1 YES prev_tx | YES prev_id | YES outpoint in utxo set | NO mempool unspent
                    if utxo in self.spent_mempool_utxos:
                        log.warning(f"Input[{i}] double-spends mempool tx output: {(prev_tx_hash.hex(), prev_id)}")
                        tx_in_statuses.append("invalid")
                        continue
                    
                # 1.2.2 YES prev_tx | YES prev_id | YES outpoint in utxo set | YES mempool unspent | NO verified
                    if not tx.verify_input(i, utxo.script_pubkey):
                        log.warning(f"UTXO found but input[{i}] failed to verify.")
                        tx_in_statuses.append("invalid")
                        continue
                    
                # 1.2.2 YES prev_tx | YES prev_id | YES outpoint in utxo set | YES mempool unspent | YES verified
                    else:
                        tx_in_statuses.append("valid")
                        continue
                    
                # 1.3 YES prev_tx | YES prev_id | NO outpoint in utxo set
                else:
                    log.warning(f"Outpoint references a spent UTXO ({(prev_tx_hash.hex(), prev_id)}). Rejected.")
                    tx_in_statuses.append("valid")
                
            # 2. NO prev_tx
            else: 
                log.info(f"Input[{i}] outpoint does not refer to any transaction in the blockchain. Checking mempool now...")
                
                # 2.1 NO prev_tx | YES prev_tx in mempool
                if mempool_tx := self._valid_txs.get(prev_tx_hash):
                    
                # 2.1.1 NO prev_tx | YES prev_tx in mempool | NO prev_id in mempool
                    try:
                        tx_out = mempool_tx.outputs[prev_id]
                    except KeyError:
                        log.warning(f"Mempool UTXO index referenced by Input[{i}] is out of bounds.")
                        tx_in_statuses.append("invalid")
                        continue
                    
                # 2.1.2 NO prev_tx | YES prev_tx in mempool | YES prev_id in mempool | NO verified
                    if not tx.verify_input(i, tx_out.script_pubkey):
                        tx_in_statuses.append("invalid")
                        continue
                    
                # 2.1.3 NO prev_tx | YES prev_tx in mempool | YES prev_id in mempool | YES verified
                    else:
                        tx_in_statuses.append("valid")
                        continue
                
                # 2.1 NO prev_tx | NO prev_tx in mempool
                else:  # Transaction either references nothing, or a tx in self._orphan txs, both meaning that its an orphan
                    log.info(f"No UTXO found for Input[{i}]. It is an orphan")
                    tx_in_statuses.append("orphan")
                    continue

        return tx_in_statuses

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

        self.spent_mempool_utxos = set()
        self.new_mempool_utxos_to_node = set()
        
        self._valid_txs = dict()
        self._orphan_txs = dict()
        self._orphan_missing_utxo = dict()
        self._orphan_registry = dict()
        
        self._updated_valids = self._updated_orphans = 0
        
        for tx in all_txs:
            self.add_tx(tx)
        

    def load_mempool(self):
        raw_txs = load_mempool()
        for raw_tx in raw_txs:
            try:
                tx = Transaction.parse(raw_tx)
                self.add_tx(tx)
            except:
                pass
        
    def save_mempool(self):
        raw_txs = list(self._valid_txs.values()) + list(self._orphan_txs.values())
        save_mempool(raw_txs)
        
        
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
    
    def check_update_mempool(self, i=1):
        update_valids = self.check_update_valids(i)
        update_orphans = self.check_update_orphans(i)
        return update_valids or update_orphans