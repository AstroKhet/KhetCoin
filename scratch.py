from crypto.hashing import HASH160
from crypto.key import get_public_key
from db.block import get_block_header
from db.constants import BLOCK_MAGIC, LMDB_ENV, ADDR_DB
from db.utils import clear_all_dbs, print_lmdb, print_dat
from utils.helper import encode_varint

c = input("Clear all DBs? (y/n)")
if c == "y":
    clear_all_dbs()

print_lmdb()

# print_dat(0, 0)


