from typing import List, BinaryIO, Optional
from coincurve import PrivateKey
from numpy import isin

from blockchain.script import *
from utils.helper import *
from utils.database import *
from crypto.hashing import *

SIGHASH_ALL = 0x01
SIGHASH_ONE = 0x02

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
        self.prev_hash = prev_hash    
        self.prev_index = prev_index 
        self.script_sig = script_sig    
        self.sequence = sequence            

    def __str__(self):
        result =  f"\tPrev Tx Hash: {self.prev_hash.hex()}\n"
        result += f"\tPrev Tx Index: {self.prev_index}\n"
        result += f"\tScript Sig: {self.script_sig}\n"
        result += f"\tSequence: {self.sequence}\n"
        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> 'TransactionInput':
        prev_hash = stream.read(32)[::-1]  ## Convert to Big Endian
        prev_index = letoi(stream.read(4))

        script_sig = Script.parse(stream) 
        sequence = letoi(stream.read(4))
        return cls(prev_hash, prev_index, script_sig, sequence)

    def serialize(self, custom_script: Optional[Script]=None) -> bytes:
        """Serializes the transaction input. Uses custom_script if provided."""
        result: bytes = self.prev_hash[::-1] ## Convert to Little Endian
        result += itole(self.prev_index)

        if custom_script:
            result += custom_script.serialize()
        else:
            result += self.script_sig.serialize()

        result += itole(self.sequence)
        return result

    ## UNTESTED
    def fetch_tx(self) -> 'Transaction':
        tx_io = get_tx_io(self.prev_hash)
        tx = Transaction.parse(tx_io)
        return tx

    def value(self) -> int:
        source_tx = self.fetch_tx()
        source_val = source_tx.outputs[self.prev_index].value
        return source_val

    def script_pubkey(self) -> Script:
        source_tx = self.fetch_tx()
        source_script_pk = source_tx.outputs[self.prev_index].script_pubkey
        return source_script_pk


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
        value = letoi(stream.read(8))
        script_pubkey = Script.parse(stream)
        return cls(value, script_pubkey)
    
    def serialize(self) -> bytes:
        result: bytes = itole(self.value, 8)
        result += self.script_pubkey.serialize()
        return result


class Transaction:
    """
    Represents a transaction.

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
        version = letoi(stream.read(4))

        no_inputs = read_varint(stream)
        inputs = [TransactionInput.parse(stream) for _ in range(no_inputs)]

        no_outputs = read_varint(stream)
        outputs = [TransactionOutput.parse(stream) for _ in range(no_outputs)]

        locktime = letoi(stream.read(4))

        return cls(version, inputs, outputs, locktime)

    def serialize(self) -> bytes:
        result: bytes = itole(self.version)

        result += encode_varint(len(self.inputs))
        result += b''.join([input.serialize() for input in self.inputs])

        result += encode_varint(len(self.outputs))
        result += b''.join([output.serialize() for output in self.outputs])

        result += itole(self.locktime)

        return result

    def sig_hash(self, index: int, NO_HASH: bool = False) -> bytes:
        result: bytes = itole(self.version)
        result += encode_varint(len(self.inputs))
        for i, input in enumerate(self.inputs):
            if i == index:
                result += input.serialize(input.script_pubkey())
            else:
                result += input.serialize(Script())  # Empty script_pubkey

        result += encode_varint(len(self.outputs))
        result += b''.join([output.serialize() for output in self.outputs])

        result += itole(self.locktime, 4) 
        result += itole(SIGHASH_ALL, 4)
        
        if NO_HASH:
            return result
        
        return HASH256(result)

    def sign_input(self, index: int, privkey: PrivateKey) -> bool:
        """Returns True if the input was signed successfully."""
        
        msg_hash = self.sig_hash(index)
        
        signature = privkey.sign(msg_hash, hasher=None) + bytes([SIGHASH_ALL])
        pubkey = privkey.public_key.format(compressed=True)
        
        self.inputs[index].script_sig = Script([signature, pubkey])
        
        return self.verify_input(index)

    def verify_input(self, index: int) -> bool:
        unverified_input = self.inputs[index]
        script_pubkey = unverified_input.script_pubkey()

        script_to_evaluate = unverified_input.script_sig + script_pubkey
        msg_hash = self.sig_hash(index)

        return script_to_evaluate.evaluate(msg_hash)

    def verify(self) -> bool:
        if self.fee() < 0:
            return False

        for i in range(len(self.inputs)):
            if not self.verify_input(i):
                return False

        return True

    def is_coinbase(self) -> bool:
        if len(self.inputs) != 1:
            return False

        coinbase_input = self.inputs[0]
        if coinbase_input.prev_hash != bytes.fromhex("00" * 32):
            return False
        
        if coinbase_input.prev_index != 0xffffffff:
            return False
        
        return True

    def coinbase_height(self) -> int:
        if not self.is_coinbase():
            raise ValueError("Invalid coinbase transaction.")
        
        if isinstance(self.inputs[0].script_sig.commands[0], int):
            raise ValueError("No op_codes should be in coinbase script_sig.")
        height = letoi(self.inputs[0].script_sig.commands[0])
        return height       

    def hash(self) -> bytes:
        tx_hash = HASH256(self.serialize())[::-1]  # Convert TO LE
        return tx_hash

    ######################################################
    def fee(self) -> int:
        if self.is_coinbase():
            return 0
        
        value_in = sum(tx_in.value() for tx_in in self.inputs)
        value_out = sum(tx_out.value for tx_out in self.outputs)
        
        return value_in - value_out  # should be >0


def create_coinbase_tx(height: int, pubkey: bytes, custom_message=None) -> Transaction:
    """Creates a coinbase transaction with the given height and public key."""
    if custom_message:
        script_sig = Script([itole(height), pubkey, custom_message])
    else:
        script_sig = Script([itole(height), pubkey])
        
    tx_in = TransactionInput(
        prev_hash=bytes.fromhex("00" * 32),
        prev_index=0xffffffff,
        script_sig=script_sig,
        sequence=0xffffffff,
    )
    
    tx_out = TransactionOutput(value=50, script_pubkey=Script([pubkey]))
    return Transaction(version=1, inputs=[tx_in], outputs=[tx_out], locktime=0)