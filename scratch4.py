import os
import time
from coincurve import PrivateKey
from blockchain.constants import SIGHASH_ALL
from blockchain.transaction import Transaction
from crypto.hashing import HASH160, HASH256
from crypto.key import create_private_key, get_private_key, get_public_key, save_private_key, wif_encode, wif_decode
from db.block import calculate_block_target, get_blockchain_height
from db.constants import LMDB_ENV
from db.tx import get_tx
from ktc_constants import MAX_BITS
from utils.config import APP_CONFIG
from utils.helper import bits_to_target, int_to_bytes, target_to_bits
from wallet.algorithm import get_recommended_fee_rate


from multiprocessing import Event, Value

from coincurve import PrivateKey, GLOBAL_CONTEXT
from coincurve._libsecp256k1 import lib, ffi
from crypto.key import get_private_key

a = get_private_key("Khet", raw=False)

count = {68:0, 69: 0, 70: 0, 71: 0}
for i in range(100):
    msg = int_to_bytes(i + 123987123)
    s = a.sign(msg, hasher=HASH256)
    
    sig = ffi.new('secp256k1_ecdsa_signature *')

    sig_parsed = lib.secp256k1_ecdsa_signature_parse_der(GLOBAL_CONTEXT.ctx, sig, s, len(s))
    print(sig_parsed)
    count[len(s)] += 1
    

print(count)