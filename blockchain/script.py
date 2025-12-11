from typing import List, BinaryIO
from coincurve import GLOBAL_CONTEXT
from coincurve._libsecp256k1 import ffi, lib


from blockchain.op_codes import *
from utils.helper import int_to_bytes, bytes_to_int, read_varint, encode_varint


class Script:
    def __init__(self, commands: List[bytes | int]=[]):
        self.commands: List[bytes | int] = commands

    def __str__(self) -> str:
        result = ""
        for command in self.commands:
            if isinstance(command, int):
                result += f"{OP_CODE_NAMES[command]}"
            else:
                result += f"{command.hex()}"
            result += "\n"

        return result[:-1]

    @classmethod
    def parse(cls, stream: BinaryIO) -> 'Script':
        script_len = read_varint(stream)
        commands= []
        i = 0

        while i < script_len:
            cmd = stream.read(1)
            cmd_numeric = bytes_to_int(cmd)
            i += 1
            if 0 < cmd_numeric < 76:  # Push next cmd bytes into stack
                commands.append(stream.read(cmd_numeric))
                i += cmd_numeric
            elif cmd_numeric <= 78:  # 76 OP_PUSHDATA1, 77 OP_PUSHDATA2, 78 OP_PUSHDATA4
                num_bytes = 1 << (cmd_numeric - 76)
                length = bytes_to_int(stream.read(num_bytes))
                commands.append(stream.read(length))
                i += cmd_numeric + length
            else:  # op code
                commands.append(cmd_numeric)

        return cls(commands)
    
    def serialize(self) -> bytes:
        result: bytes = b""

        for command in self.commands:
            if isinstance(command, int):
                result += int_to_bytes(command, 1)
            else:
                length = len(command)
                if length < 76:
                    result += bytes([length]) 
                elif length < 0x100:     # OP_PUSHDATA1
                    result += b"\x4c" + bytes([length])
                elif length < 0x10000:   # OP_PUSHDATA2
                    result += b"\x4d" + int_to_bytes(length, 2)
                else:                    # OP_PUSHDATA4
                    result += b"\x4e" + int_to_bytes(length, 4)

                result += command

        num_bytes = len(result)
        return encode_varint(num_bytes) + result

    def evaluate(self, msg_hash: bytes = b'') -> bool:
        stack = []
        for command in self.commands: 
            if isinstance(command, int):  # int which is a command op_code
                if command in (0xAC, 0xAE):  # OP_CHECKSIG, OP_CHECKMULTISIG
                    if OP_CODE_FUNCTIONS[command](stack, msg_hash):
                        pass  # No errors in Script
                elif OP_CODE_FUNCTIONS[command](stack):  # Other op_codes
                    pass # No errors in Script
                else:
                    return False
            else: 
                stack.append(command)

        return True

    def is_standard_script_sig(self):
        """
        Checks if Script has the following structure
        - DER Signature
        - EC Compressed Pubkey
        """
        if len(self.commands) != 2:
            return False

        first_cmd = self.commands[0][:-1]  # Remove sighash byte
        if not isinstance(first_cmd, bytes): 
            return False

        sig = ffi.new('secp256k1_ecdsa_signature *')
        if not lib.secp256k1_ecdsa_signature_parse_der(GLOBAL_CONTEXT.ctx, sig, first_cmd, len(first_cmd)):
            return False

        second_cmd = self.commands[1]
        if not isinstance(second_cmd, bytes):
            return False

        pubkey = ffi.new('secp256k1_pubkey *')
        if not lib.secp256k1_ec_pubkey_parse(GLOBAL_CONTEXT.ctx, pubkey, second_cmd, len(second_cmd)):
            return False

        return True
                    
    def is_p2pkh(self):
        """
        Checks if Script has the following structure
        - 0x76 OP_DUP
        - 0xA9 OP_HASH160
        - 20B Pubkey Hash
        - 0x88 OP_EQUALVERIFY
        - 0xAC OP_CHECKSIG
        """
        if len(self.commands) != 5:
            return False
        
        if self.commands[0] != OP_DUP:
            return False

        if self.commands[1] != OP_HASH160:
            return False
        
        if isinstance(self.commands[2], bytes):  # <PubkeyHash>
            if len(self.commands[2]) != 20:
                return False
        else:
            return False
        
        if self.commands[3] != OP_EQUALVERIFY: 
            return False
        
        if self.commands[4] != OP_CHECKSIG:
            return False
        
        return True 
    
    def get_script_pubkey_receiver(self) -> bytes | None:
        """
        The receiver address of a transaction is contained within
        the ScriptPubkey of its outputs

        Returns a 20B PubkeyHash
        """
        if not self.is_p2pkh():
            return None
        
        return self.commands[2]  # type: ignore
    
    def get_script_sig_sender(self) -> bytes | None:
        """
        The sender of a transaction is contained within the ScriptSigof its inputs

        Returns a 20B PubkeyHash
        """
        if not self.is_standard_script_sig():
            return None
        return HASH160(self.commands[1])  # type: ignore
    
    @property
    def sigops(self):
        return sum(isinstance(cmd, int) for cmd in self.commands)
    
    def __add__(self, other: 'Script') -> 'Script':
        return Script(self.commands + other.commands)


def P2PKH_script_pubkey(pk_hash: bytes) -> Script:
    return Script(
        [
            OP_DUP,
            OP_HASH160,
            pk_hash, 
            OP_EQUALVERIFY,
            OP_CHECKSIG
        ]
    )
