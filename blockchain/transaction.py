import logging

from typing import List, BinaryIO, Optional
from coincurve import PrivateKey
from db.constants import LMDB_ENV, ADDR_DB
from ktc_constants import COINBASE_MATURITY, MAX_KHETS, KTC, MAX_KTC, MAX_BLOCK_SIZE

from blockchain.constants import SIGHASH_ALL, SIGOPS_LIMIT
from blockchain.script import *

from crypto.hashing import *

from db.block import get_blockchain_height, median_time_past
from db.tx import get_txn

from utils.helper import *


log = logging.getLogger(__name__)

class TransactionInput:
    """Represents a transaction input.
    
    Attributes:
        prev_tx_hash: 32 bytes, little-endian
        prev_tx_index: 4 bytes, little-endian
        script_sig: variable length
        sequence: 4 bytes, little-endian
    """
    def __init__(
        self,
        prev_hash: bytes,
        prev_index: int,     
        script_sig: Script = Script([]),     
        sequence: int = 0xffffffff,          
    ):
        self.prev_tx_hash = prev_hash    
        self.prev_index = prev_index 
        self.script_sig = script_sig    
        
        # Used for RBF & relative txn locktime, but not implemented here
        self.sequence = sequence            

    def __str__(self):
        result =  f"\tPrev Tx Hash: {self.prev_tx_hash.hex()}\n"
        result += f"\tPrev Tx Index: {self.prev_index}\n"
        result += f"\tScript Sig: {self.script_sig}\n"
        result += f"\tSequence: {self.sequence}\n"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> 'TransactionInput':
        prev_hash = stream.read(32)
        prev_index = bytes_to_int(stream.read(4))
        script_sig = Script.parse(stream) 
        sequence = bytes_to_int(stream.read(4))
        return cls(prev_hash, prev_index, script_sig, sequence)

    def serialize(self, custom_script: Optional[Script]=None) -> bytes:
        """Serializes the transaction input. Uses custom_script if provided."""
        result: bytes = self.prev_tx_hash
        result += int_to_bytes(self.prev_index)

        if custom_script:
            result += custom_script.serialize()
        else:
            result += self.script_sig.serialize()

        result += int_to_bytes(self.sequence)
        return result

    def fetch_tx(self) -> 'Transaction | None':
        # Fetches the full transaction based on prev_hash
        tx_io = get_txn(self.prev_tx_hash)
        if tx_io:
            return Transaction.parse(BytesIO(tx_io))
        else:
            return None

    def value(self) -> int | None:
        source_tx = self.fetch_tx()
        if source_tx:
            source_val = source_tx.outputs[self.prev_index].value
            return source_val
        else:  # No prev tx found?
            return None

    def script_pubkey(self) -> Script | None:
        """
        Retrieves the locking script of this Input
        """
        source_tx = self.fetch_tx()
        if source_tx:    
            source_script_pk = source_tx.outputs[self.prev_index].script_pubkey
            return source_script_pk
        else:
            return None


class TransactionOutput:
    """Represents a transaction output.
    
    Attributes:
        value: 8 bytes, little-endian
        script_pubkey: variable length
    """
    def __init__(self, value: int, script_pubkey: Script):
        self.value = value
        self.script_pubkey = script_pubkey
    
    def __str__(self):
        result = "Output:\n"
        result += f"\tValue: {self.value} \n"
        result += f"\tScript Pubkey: {self.script_pubkey}\n"
        return result
    
    @classmethod
    def parse(cls, stream: BinaryIO) -> 'TransactionOutput':
        value = bytes_to_int(stream.read(8))
        script_pubkey = Script.parse(stream)
        return cls(value, script_pubkey)
    
    def serialize(self) -> bytes:
        result: bytes = int_to_bytes(self.value, 8)
        result += self.script_pubkey.serialize()
        return result


class Transaction:
    """
    Represents a transaction.
    `Transaction` objects should be used as immutable

    Attributes:
        version: 4 bytes, little-endian
        inputs: List[TransactionInput]
        outputs: List[TransactionOutput]
        locktime: 4 bytes, little-endian
    """
    def __init__(
        self,
        version: int,
        inputs: List[TransactionInput],
        outputs: List[TransactionOutput],
        locktime: int,
    ):
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.locktime = locktime

        # For fast calculation of self.size().
        self._serialize_cache = None 

    def __setattr__(self, name, value) -> None:
        if name != "_serialize_cache":
            self._serialize_cache = None
        super().__setattr__(name, value)

    def __str__(self):
        result = f"Version: {self.version}\n"
        result += f"Inputs: \n"
        for input in self.inputs:
            result += str(input)
            result += "\n"
        result += f"Outputs: \n"
        for output in self.outputs:
            result += str(output)
            result += "\n"
        result += f"Locktime: {self.locktime}\n"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> 'Transaction':
        """
        Parses a transaction from a Binary I/O
        """
        version = bytes_to_int(stream.read(4))

        no_inputs = read_varint(stream)
        inputs = [TransactionInput.parse(stream) for _ in range(no_inputs)]

        no_outputs = read_varint(stream)
        outputs = [TransactionOutput.parse(stream) for _ in range(no_outputs)]

        locktime = bytes_to_int(stream.read(4))

        return cls(version, inputs, outputs, locktime)

    @classmethod
    def parse_static(cls, bytes: bytes) -> 'Transaction':
        """
        Parses a transaction from static bytes
        """
        return cls.parse(BytesIO(bytes))

    def serialize(self) -> bytes:
        if self._serialize_cache:
            return self._serialize_cache

        result: bytes = int_to_bytes(self.version)

        result += encode_varint(len(self.inputs))
        result += b''.join([input.serialize() for input in self.inputs])

        result += encode_varint(len(self.outputs))
        result += b''.join([output.serialize() for output in self.outputs])

        result += int_to_bytes(self.locktime)

        self._serialize_cache = result
        return result

    def _sig_hash(self, index: int,  NO_HASH: bool = False) -> bytes:
        """
        Provides 'z', the hash of the transaction to be signed
        Here the message is this transaction without script_sigs for
        inputs with index != `index`
        
        Args:
            index: 
            NO_HASH: 
        """
        result: bytes = int_to_bytes(self.version)
        result += encode_varint(len(self.inputs))
        for i, input in enumerate(self.inputs):
            if i == index:
                result += input.serialize(input.script_pubkey())
            else:
                result += input.serialize(Script())  # Empty script_pubkey

        result += encode_varint(len(self.outputs))
        result += b''.join([output.serialize() for output in self.outputs])

        result += int_to_bytes(self.locktime, 4) 
        result += int_to_bytes(SIGHASH_ALL, 4)

        if NO_HASH:
            return result

        return HASH256(result)

    def sign_input(self, index: int, privkey: PrivateKey) -> bool:
        """Returns True if the input was signed successfully."""

        msg_hash = self._sig_hash(index)

        signature = privkey.sign(msg_hash, hasher=None) + bytes([SIGHASH_ALL])

        # P2PKH
        pk_hash = HASH160(privkey.public_key.format(compressed=True))
        self.inputs[index].script_sig = Script([signature, pk_hash])

        self._serialize_cache = None
        return self.verify_input(index)

    def sign(self, privkey: PrivateKey) -> bool:
        """Returns True if all inputs were signed successfully"""
        for i in range(len(self.inputs)):
            if not self.sign_input(i, privkey):
                return False
        return True
    
    def verify_input(self, index: int, custom_script_pubkey: Script | None = None) -> bool:
        unverified_input = self.inputs[index]
        if custom_script_pubkey:
            script_pubkey = custom_script_pubkey
        else:
            script_pubkey = unverified_input.script_pubkey()
            
        if script_pubkey is None:  # Cannot retrieve script_pubkey
            return False

        script_verify = unverified_input.script_sig + script_pubkey
        if script_verify.sigops > SIGOPS_LIMIT:
            log.warning(f"<TX {self.hash()}> Input[{index}] exceeds SIGOPS LIMIT")
            return False

        msg_hash = self._sig_hash(index)

        return script_verify.evaluate(msg_hash)

    def verify(self, allow_orphan: bool = False) -> bool:
        log.info(f"Verifying Transaction<{self.serialize().hex()}>...")
        if not self.inputs or not self.outputs:
            log.warning(f"<TX {self.hash()}> has empty input and/or output")
            return False

        if self.size() > MAX_BLOCK_SIZE:
            log.warning(f"<TX {self.hash()}> Size is not less than {MAX_BLOCK_SIZE} & >= 100.")
            return False

        if self.fee() < 0:
            log.warning(f"<TX {self.hash()}> Fee <= 0")
            return False

        input_sum = 0
        if not self.is_coinbase():
            # Checking inputs
            for tx_in in self.inputs:
                input_value = tx_in.value()
                # TODO: Orphan TXN
                if input_value is None:
                    if allow_orphan:
                        log.info(f"Input<{tx_in}> is an orphan. Ignoring as allow_orphan=True")
                        continue
                    else:   
                        log.warning(f"Input<{tx_in}>: Invalid UTXO reference. Ignore by setting allow_orphan=True")
                        return False

                if input_value > MAX_KHETS:
                    log.warning(f"<Input<{tx_in}>: Value exceeds KTC limit")
                    return False

                input_sum += input_value
            if input_sum > MAX_KHETS:
                log.warning(f"<TX {self.hash()}> Sum or parts of input exceed {MAX_KTC} KTC")
                return False

        output_sum = 0
        for tx_out in self.outputs:
            output_value = tx_out.value

            if output_value > MAX_KHETS:
                log.warning(f"<Output<{tx_out}>: Value exceeds KTC limit")
                return False

            output_sum += output_value
        if output_sum > MAX_KHETS:
            log.warning(f"<TX {self.hash()}> Sum or parts of input exceed {MAX_KTC} KTC")
            return False

        if self.locktime == 0:  # Txn is immediately spendable
            pass
        elif self.locktime < 500_000_000:  # locktime is the least height requried before tx is spendable
            if self.locktime > get_blockchain_height():
                log.warning(f"<TX {self.hash()}> Blockchain height insufficient. Transaction locked.")
                return False
        else:  # locktime represents an epoch time
            if self.locktime > median_time_past():
                log.warning(f"<TX {self.hash()}> MTP too early. Transaction locked.")
                return False

        # Ensuring that all inputs come from a valid UTXO
        if not self.is_coinbase():
            output_seen: set[tuple[bytes, int]] = set()  # Double spend checking
            for i, input in enumerate(self.inputs):
                prev_tx_hash = input.prev_tx_hash
                prev_id = input.prev_index
                outpoint = (prev_tx_hash, prev_id)

                if outpoint in output_seen:
                    log.warning(f"Double spend detected at Input[{i}]")
                    return False

                else:
                    output_seen.add(outpoint)
                if not self.verify_input(i): 
                    log.warning(f"<TX {self.hash()}> Input[{i}] failed to verify.")
                    return False

                # if prev_tx := input.fetch_tx():
                #     if prev_tx.is_coinbase() and get_blockchain_height() < prev_tx.coinbase_height() + COINBASE_MATURITY:
                #         log.warning(f"<TX {self.hash()}> Input[{i}] uses a coinbase txn that has not matured yet.")
                #         return False

                # else:  # Orphan TXN
                #     log.warning(f"<TX {self.hash()}> Input[{i}] does not reference a valid txn_hash. Discarding.")
                #     # Discarded, but possible to cache in orphan pool
                #     return False

        return True

    def is_coinbase(self) -> bool:
        if len(self.inputs) != 1:
            return False

        coinbase_input = self.inputs[0]
        if coinbase_input.prev_tx_hash != bytes(32):
            return False

        if coinbase_input.prev_index != 0xffffffff:
            return False

        return True

    def coinbase_height(self) -> int:
        if not self.is_coinbase():
            log.exception(f"<TX {self.hash()}> No coinbase height for non coinbase txn")
            return -1

        if self.inputs[0].script_sig.sigops > 0:
            log.exception(f"<TX {self.hash()}> Invalid coinbase txn: scriptSig must have 0 SIGOPS")
            return -1
        else:
            height = bytes_to_int(self.inputs[0].script_sig.commands[0]) # type: ignore
        return height       

    def hash(self) -> bytes:
        tx_hash = HASH256(self.serialize())
        return tx_hash

    def fee(self) -> int:
        if self.is_coinbase():
            return 0

        value_in = 0
        for inp in self.inputs:
            if value := inp.value():
                value_in += value
            else:
                log.warning(f"Input {inp} refering to non-existent UTXO")
                return -1

        value_out = sum(tx_out.value for tx_out in self.outputs)

        return value_in - value_out  # should be >0

    def size(self):
        return len(self.serialize())

    def from_(self):
        """
        Returns where the Transaction inputs came from
        """
        if self.is_coinbase():
            from_ = "Coinbase Reward"
        else:   
            no_inputs = len(self.inputs)
            from_ = self.inputs[0].script_sig.get_script_sig_sender()
            if not from_: 
                from_ = f"{no_inputs} inputs"
            for tx_in in self.inputs[1:]:
                if from_ != tx_in.script_sig.get_script_sig_sender():
                    from_ = f"{no_inputs} inputs"
                    break
        return from_
    
    def to(self):
        """
        Returns where the Transaction outputs are going to
        """
        to = self.outputs[0].script_pubkey.get_script_pubkey_receiver()
        no_outputs = len(self.outputs)
        if not to:
            to = f"{no_outputs} outputs"
        for tx_out in self.outputs[1:]:
            if to != tx_out.script_pubkey.get_script_pubkey_receiver():
                to= f"{no_outputs} outputs"
                break
        return to

    def __hash__(self):
        return self.hash()

    def __eq__(self, other):
        return self.hash() == other.hash()


# Auxillary UTXO functionality for wallet
def save_utxo_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.put(addr, outpoint)


def get_utxo_addr(addr: bytes) -> list[tuple]:
    utxos = []
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        cursor = db.cursor()
        if cursor.set_key(addr):
            for outpoint in cursor.iternext_dup():
                utxos.append((outpoint[:32], bytes_to_int(outpoint[32:36])))
    return utxos


def get_utxo_addr_value(addr: bytes) -> int:
    # TODO: Implement UTXO Caching
    value = 0
    for tx_hash, idx in get_utxo_addr(addr):
        if tx_raw := get_txn(tx_hash):
            tx = Transaction.parse_static(tx_raw)
            tx_out = tx.outputs[idx]
            value += tx_out.value
        # else txn not found
    return value


def delete_utxo_addr(addr: bytes, tx_hash: bytes, index: int):
    with LMDB_ENV.begin(db=ADDR_DB) as db:
        outpoint = tx_hash + int_to_bytes(index)
        db.delete(addr, outpoint)


def count_utxo_addr(addr: bytes | None = None) -> int:
    """
    Counts UTXOs associated with addr if set, otherwise returns size of entire UTXO set
    """
    with LMDB_ENV.begin(db=ADDR_DB) as txn:
        cursor = txn.cursor()
        if addr is None:
            stat = txn.stat()
            return stat["entries"]
        if cursor.set_key(addr):
            return cursor.count()
        else:
            return 0
