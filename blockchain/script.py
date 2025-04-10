from typing import List, BinaryIO

from blockchain.op_codes import *
from utils.helper import letoi, itole, read_varint, encode_varint


class Script:
    def __init__(self, commands: List[bytes | int]=[]):
        self.commands: List[bytes | int] = commands

    def __str__(self) -> str:
        result = ""
        for command in self.commands:
            if isinstance(command, bytes):
                result += f"<{command.hex()}> "
            else:
                result += f"{OP_CODE_NAMES[command]} "

        return result

    @classmethod
    def parse(cls, stream: BinaryIO) -> 'Script':
        script_len = read_varint(stream)
        commands= []
        i = 0

        while i < script_len:
            cmd = stream.read(1)
            cmd_numeric = letoi(cmd)
            i += 1
            if 0 < cmd_numeric < 76:  # Push next cmd bytes into stack
                commands.append(stream.read(cmd_numeric))
                i += cmd_numeric
            elif cmd_numeric <= 78:  # 76 OP_PUSHDATA1, 77 OP_PUSHDATA2, 78 OP_PUSHDATA4
                num_bytes = int(pow(2, cmd_numeric - 76))
                length = letoi(stream.read(num_bytes))
                commands.append(stream.read(length))
                i += cmd_numeric + length
            else:  # op code
                commands.append(cmd_numeric)

        return cls(commands)

    def serialize(self) -> bytes:
        result: bytes = b""

        for command in self.commands:
            if isinstance(command, bytes):
                length = len(command)
                if length < 76:
                    result += bytes([length])
                elif length < 0x100:
                    result += b"\x4c" + bytes([length])
                elif length < 0x10000:
                    result += b"\x4d" + length.to_bytes(2, "little")
                else:
                    result += b"\x4e" + length.to_bytes(4, "little")

                result += command
            else:
                result += itole(command, 1)

        num_bytes = len(result)
        return encode_varint(num_bytes) + result

    def evaluate(self, msg_hash: bytes = b'') -> bool:
        stack = []

        for command in self.commands:
            if isinstance(command, bytes):
                stack.append(command)
            else: # int which is a command op_code
                if command in (0xAC, 0xAE):  # OP_CHECKSIG, OP_CHECKMULTISIG
                    if OP_CODE_FUNCTIONS[command](stack, msg_hash):
                        pass  # No errors in Script
                elif OP_CODE_FUNCTIONS[command](stack):  # Other op_codes
                    pass # No errors in Script
                else:
                    return False

        return True

    def __add__(self, other: 'Script') -> 'Script':
        return Script(self.commands + other.commands)
