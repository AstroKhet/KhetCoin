import logging

from typing import BinaryIO
from coincurve import PrivateKey
from db.height import get_blockchain_height
from ktc_constants import MAX_BLOCK_SIZE

from blockchain.constants import SIGHASH_ALL, SIGOPS_LIMIT
from blockchain.script import Script

from crypto.hashing import HASH256

from db.block import median_time_past
from db.tx import get_tx

from utils.fmt import format_bytes
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
        
        # Used for RBF & relative tx locktime, but not implemented here
        self.sequence = sequence            
        
        self._prev_output = None

    def __str__(self):
        return (
            f"      Prev Tx Hash : {self.prev_tx_hash.hex()}\n"
            f"      Prev Index   : {self.prev_index}\n"
            f"      Script Sig   : {self.script_sig}\n"
            f"      Sequence     : {self.sequence}"
        )

    @classmethod
    def parse(cls, stream: BinaryIO | bytes) -> 'TransactionInput':
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
            
        prev_hash = stream.read(32)
        prev_index = bytes_to_int(stream.read(4))
        script_sig = Script.parse(stream) 
        sequence = bytes_to_int(stream.read(4))
        return cls(prev_hash, prev_index, script_sig, sequence)

    def serialize(self, custom_script: Script | None = None) -> bytes:
        """Serializes the transaction input. Uses custom_script if provided."""
        result: bytes = self.prev_tx_hash
        result += int_to_bytes(self.prev_index)

        if custom_script:
            result += custom_script.serialize()
        else:
            result += self.script_sig.serialize()

        result += int_to_bytes(self.sequence)
        return result
        
    def fetch_tx_output(self) -> 'TransactionOutput | None':
        if self._prev_output:
            return self._prev_output
        
        if tx_raw := get_tx(self.prev_tx_hash):
            tx = Transaction.parse(tx_raw)
            try:
                self._prev_output = tx.outputs[self.prev_index]
                return self._prev_output
            except IndexError:
                return None
        return None

    def value(self) -> int | None:
        if tx_out := self.fetch_tx_output():
            return tx_out.value
        return None

    def script_pubkey(self) -> Script | None:
        """Retrieves the locking script of this Input"""
        if tx_out := self.fetch_tx_output():    
            return tx_out.script_pubkey
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

        self._change = False  # Determines if this output is change
    
    def __str__(self):
        return (
            f"      Value        : {self.value}\n"
            f"      ScriptPubKey : {self.script_pubkey}"
        )

    @classmethod
    def parse(cls, stream: BinaryIO | bytes) -> 'TransactionOutput':
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
            
        value = bytes_to_int(stream.read(8))
        script_pubkey = Script.parse(stream)
        return cls(value, script_pubkey)
    
    def serialize(self) -> bytes:
        result: bytes = int_to_bytes(self.value, 8)
        result += self.script_pubkey.serialize()
        return result
    
    def set_change(self) -> None:
        self._change = True

    def is_change(self) -> True:
        return self._change


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
        inputs: list[TransactionInput],
        outputs: list[TransactionOutput],
        locktime: int,
    ):
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.locktime = locktime

    def __str__(self):
        lines = [
            f"Transaction {self.hash().hex()}",
            f"  Version: {self.version}",
            "",
            f"  Inputs ({len(self.inputs)}):",
        ]

        for i, tx_in in enumerate(self.inputs):
            lines.append(f"    [{i}]")
            lines.append(str(tx_in))

        lines.append("")
        lines.append(f"  Outputs ({len(self.outputs)}):")

        for i, tx_out in enumerate(self.outputs):
            lines.append(f"    [{i}]")
            lines.append(str(tx_out))

        lines.append(f"\n  Locktime: {self.locktime}")
        return "\n".join(lines)
    
    @classmethod
    def parse(cls, stream: BinaryIO | bytes) -> 'Transaction':
        """Parses a transaction from a Binary I/O or bytes"""
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
            
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
        result: bytes = int_to_bytes(self.version)

        result += encode_varint(len(self.inputs))
        result += b''.join([tx_in.serialize() for tx_in in self.inputs])

        result += encode_varint(len(self.outputs))
        result += b''.join([tx_out.serialize() for tx_out in self.outputs])

        result += int_to_bytes(self.locktime)

        return result

    def _sig_hash(self, index: int, NO_HASH: bool = False) -> bytes:
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

        signature = privkey.sign(msg_hash, hasher=HASH256) + bytes([SIGHASH_ALL])
        # P2PKH
        pubkey = privkey.public_key.format(compressed=True)
        self.inputs[index].script_sig = Script([signature, pubkey])

        self._serialize_cache = None
        return self.verify_input(index)

    def sign(self, privkey: PrivateKey) -> bool:
        """Returns True if all inputs were signed successfully"""
        for i in range(len(self.inputs)):
            if not self.sign_input(i, privkey):
                log.warning(f"Failed to sign input {i}")
                return False
        return True
    
    def verify_input(self, index: int, custom_script_pubkey: Script | None = None) -> bool:
        unverified_input = self.inputs[index]
        if custom_script_pubkey:
            script_pubkey = custom_script_pubkey
        else:
            script_pubkey = unverified_input.script_pubkey()
            
        if script_pubkey is None:  # Cannot retrieve script_pubkey
            log.warning(f"Unable to retrieve scriptPubkey from input {index}")
            return False

        script_verify = unverified_input.script_sig + script_pubkey
        if script_verify.sigops > SIGOPS_LIMIT:
            log.warning(f"<TX {self.hash()}> Input[{index}] exceeds SIGOPS LIMIT")
            return False

        msg_hash = self._sig_hash(index)

        if not script_verify.evaluate(msg_hash):
            log.warning(f"Script evaluation failed for input {index}")
        return script_verify.evaluate(msg_hash)

    def verify(self, allow_orphan: bool = False) -> bool:
        """
        Verifies that a transaction fits into the Khetcoin protocol
        
        Note: This does not check if the tx uses outputs already spent
        """
        log.info(f"Verifying Transaction<{self.hash().hex()}>...")
        
        # 1. Basic Preliminary checks
        if not self.inputs or not self.outputs:
            log.warning(f"Empty inputs and/or outputs")
            return False

        if size := self.size() > MAX_BLOCK_SIZE:
            log.warning(f"Transaction size too large: {format_bytes(size)} > {format_bytes(MAX_BLOCK_SIZE)}")
            return False

        if self.fee() is None:
            if allow_orphan: 
                pass
            else:
                log.warning(f"Error calculating fee")
                return False
        elif self.fee() < 0:
            log.warning("Fee <= 0")
            return False

        # 2. Checking Inputs of this Transaction
        #   a) For inputs referencing valid outpoints, their combined script should be valid.
        #   b) No double spending within a transaction. That is, we can't have two inputs pointing to the same outpoint
        if not self.is_coinbase():
            output_seen: set[tuple[bytes, int]] = set()
            for i, input in enumerate(self.inputs):
                if input.value() is None:
                    if allow_orphan:
                        log.info(f"Unable to find referenced UTXO for Input[{i}]; Orphan transaction")
                        continue
                    
                elif not self.verify_input(i): 
                    log.warning(f"Input[{i}] failed to verify.")
                    return False
                
                outpoint = (input.prev_tx_hash, input.prev_index)
                if outpoint in output_seen:
                    log.warning(f"Double spend detected at Input[{i}]")
                    return False
 
                output_seen.add(outpoint)

        # 3. Locktime checks 
        if self.locktime == 0:  # Tx is immediately spendable
            pass
        elif self.locktime < 500_000_000:  # locktime is the least height requried before tx is spendable
            if self.locktime > get_blockchain_height():
                log.warning(f"<TX {self.hash()}> Blockchain height insufficient. Transaction locked.")
                return False
        else:  # locktime represents an epoch time
            if self.locktime > median_time_past():
                log.warning(f"<TX {self.hash()}> MTP too early. Transaction locked.")
                return False

        # Transaction Verified
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

    def hash(self) -> bytes:
        tx_hash = HASH256(self.serialize())
        return tx_hash

    def fee(self) -> int | None:
        if self.is_coinbase():
            return 0

        input_value = self.input_value()
        if not input_value:
            return None
        output_value = self.output_value()
        return  input_value - output_value # should be >0
    
    def fee_rate(self):
        if (fee := self.fee()) is not None:
            return fee / len(self.serialize())
        return None
        
    def input_value(self) -> int | None:
        val = 0
        for i, inp in enumerate(self.inputs):
            value = inp.value()
            if value is not None:
                val += value
            else:
                return None
        return val
    
    def output_value(self, exclude_change=False):
        val = sum(tx_out.value for tx_out in self.outputs)
        if exclude_change:
            val -= self.change_value()
        return val
    
    def change_value(self):
        val = sum(tx_out.value for tx_out in self.outputs if tx_out.is_change())
        return val
    
    def size(self):
        return len(self.serialize())

    def from_(self):
        """Returns where the Transaction inputs came from"""
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
        """Returns where the Transaction outputs are going to"""
        to = self.outputs[0].script_pubkey.get_script_pubkey_receiver()
        no_outputs = len(self.outputs)
        if not to:
            to = f"{no_outputs} outputs"
        for tx_out in self.outputs[1:]:
            if to != tx_out.script_pubkey.get_script_pubkey_receiver():
                to= f"{no_outputs} outputs"
                break
        return to

    def copy(self):
        return Transaction(self.version, self.inputs, self.outputs, self.locktime)
    def __hash__(self):
        return self.hash()

    def __eq__(self, other):
        return self.hash() == other.hash()

