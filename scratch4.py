from blockchain.transaction import Transaction
from crypto.hashing import HASH160
from crypto.key import create_private_key, get_private_key, get_public_key, save_private_key, wif_encode, wif_decode
from db.constants import LMDB_ENV
from db.tx import get_txn
from wallet.algorithm import get_recommended_fee_rate


# efd = create_private_key()
# save_private_key(efd, "EFD")

# tx = get_txn(bytes.fromhex("314cc4727aedb49c7c0f1272dadcfbc0242256c6d90b84cc4bb959ea62fda162"))
# tx =  Transaction.parse_static(tx)
# print(len(tx.outputs[0].serialize()))


from utils.setup import INITIAL_SETUP
import os
print(os.path.join(".local", "addresses.db"))