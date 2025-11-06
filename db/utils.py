from io import BytesIO
import os

from db.constants import LMDB_ENV, BLOCKS_DB, HEIGHT_DB, TX_DB, WALLET_DB, UTXO_DB
from utils.fmt import print_bytes, truncate_bytes
from utils.helper import bytes_to_int, read_varint  # assuming your helpers are here too
from utils.config import APP_CONFIG

## DELETE IN PRODUCTION

def clear_all_dbs():
    with LMDB_ENV.begin(write=True) as txn:
        txn.drop(BLOCKS_DB, delete=False)
        txn.drop(HEIGHT_DB, delete=False)
        txn.drop(TX_DB, delete=False)
        txn.drop(WALLET_DB, delete=False)
        txn.drop(UTXO_DB, delete=False)
    print("All LMDB databases cleared.")


def print_lmdb():
    dbs = {
        "BLOCKS_DB": BLOCKS_DB,
        "HEIGHT_DB": HEIGHT_DB,
        "TX_DB": TX_DB,
        "UTXO_DB": UTXO_DB,
        "ADDR_DB": WALLET_DB
    }

    for name, db in dbs.items():
        print(f"\n{name}")
        w = 100
        print("╔" + "═" * w + "╤" + "═" * w + "╗")
        print("║ {:<98} │ {:<98} ║".format("Key", "Value"))
        print("╟" + "─" * w + "┼" + "─" * w + "╢")

        with LMDB_ENV.begin(db=db, write=False) as txn:
            cursor = txn.cursor()

            if name == "ADDR_DB":
                # Group multiple values per key
                for key in cursor.iternext(keys=True, values=False):
                    for value in cursor.iternext_dup():
                        out = value[:32]
                        idx = bytes_to_int(value[32:])
                        print(
                            "║ {:<98} │ {:<98} ║".format(
                                f"to={key.hex()}", f"tx={out.hex()}, id={idx}"
                            )
                        )

            else:
                # Normal DBs, print as before
                for key, value in cursor:
                    if name == "BLOCKS_DB":
                        dat_no = bytes_to_int(value[0:4])
                        offset = bytes_to_int(value[4:8])
                        size = bytes_to_int(value[8:12])
                        ts = bytes_to_int(value[12:16])
                        no_txns = bytes_to_int(value[16:20])
                        total_sent = bytes_to_int(value[20:28])
                        fee = bytes_to_int(value[28:36])
                        height = read_varint(BytesIO(value[36:]))

                        value_str = f"dat={dat_no}, off={offset}, size={size}, ts={ts}, #tx={no_txns}, sent={total_sent}, fee={fee}, height={height}"

                        print(
                            "║ {:<98} │ {:<98} ║".format(f"blk={key.hex()}", value_str)
                        )
                    elif name == "HEIGHT_DB":
                        print(
                            "║ {:<98} │ {:<98} ║".format(
                                f"height={read_varint(key)}", f"blk={value.hex()}"
                            )
                        )
                    elif name == "TX_DB":
                        dat_no = bytes_to_int(value[0:4])
                        offset = bytes_to_int(value[4:8])
                        size = bytes_to_int(value[8:12])
                        pos = bytes_to_int(value[12:16])
                        height = read_varint(value[16:])
                        value_str = (
                            f"dat={dat_no}, off={offset}, size={size}, pos={pos}, height={height}"
                        )
                        print(
                            "║ {:<98} │ {:<98} ║".format(f"tx={key.hex()}", value_str)
                        )

                    elif name == "UTXO_DB":
                        txn = key[:32].hex()
                        idx = bytes_to_int(key[32:])
                        print(
                            "║ {:<98} │ {:<98} ║".format(f"tx={txn}, idx={idx}", f"{truncate_bytes(value, ends=4)}")
                        )

        print("╚" + "═" * w + "╧" + "═" * w + "╝")


def print_dat(n, start, end=-1):
    dat_file = os.path.join(APP_CONFIG.get("path", "blockchain"), f"blk{n:08}.dat")

    with open(dat_file, "rb") as dat:
        dat.seek(start)
        if end == -1:
            raw = dat.read()
        else:
            raw = dat.read(end - start)

        print(f"Opening {dat_file} Bytes {start} to {end}:")
        print_bytes(raw)
