from io import BytesIO
import os

from db.constants import INDEX_DB, LMDB_ENV, BLOCKS_DB, HEIGHT_DB, MEMPOOL_DB, TX_DB, ADDR_DB, TX_HISTORY_DB, UTXO_DB
from utils.fmt import print_bytes, truncate_bytes
from utils.helper import bytes_to_int
from utils.config import APP_CONFIG

## DELETE IN PRODUCTION

def clear_all_dbs():
    with LMDB_ENV.begin(write=True) as tx:
        tx.drop(BLOCKS_DB, delete=False)
        tx.drop(HEIGHT_DB, delete=False)
        tx.drop(TX_DB, delete=False)
        tx.drop(TX_HISTORY_DB, delete=False)
        tx.drop(ADDR_DB, delete=False)
        tx.drop(UTXO_DB, delete=False)
    print("All LMDB databases cleared.")
    
    BLOCKCHAIN_DIR = APP_CONFIG.get("path", "blockchain")

    # delete all files in the directory
    for p in BLOCKCHAIN_DIR.iterdir():
        if p.is_file():
            p.unlink()

    # create empty blk00000000.dat
    (BLOCKCHAIN_DIR / "blk00000000.dat").touch()
    print("All .dat files cleared")
    
def print_lmdb():
    dbs = {
        "BLOCKS_DB": BLOCKS_DB,
        "INDEX_DB": INDEX_DB,
        "HEIGHT_DB": HEIGHT_DB,
        "TX_DB": TX_DB,
        "TX_HISTORY_DB": TX_HISTORY_DB, 
        "UTXO_DB": UTXO_DB,
        "ADDR_DB": ADDR_DB,
        "MEMPOOL_DB": MEMPOOL_DB
    }

    for name, db in dbs.items():
        print(f"\n{name}")
        w = 100
        print("╔" + "═" * w + "╤" + "═" * w + "╗")
        print("║ {:<98} │ {:<98} ║".format("Key", "Value"))
        print("╟" + "─" * w + "┼" + "─" * w + "╢")

        with LMDB_ENV.begin(db=db, write=False) as tx:
            cursor = tx.cursor()

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
            elif name == "TX_HISTORY_DB":
                for key, value in cursor:
                    tx_hash   = value[:32]
                    cb_value  = bytes_to_int(value[32:40])
                    in_value  = bytes_to_int(value[40:48])
                    out_value = bytes_to_int(value[48:56])

                    print(
                        "║ {:<98} │ {:<98} ║".format(
                            f"height={bytes_to_int(key)}",
                            f"tx_hash={tx_hash.hex()}, {cb_value=}, {in_value=}, {out_value=}"
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
                        no_txs = bytes_to_int(value[16:20])
                        total_sent = bytes_to_int(value[20:28])
                        fee = bytes_to_int(value[28:36])
                        height = bytes_to_int(value[36:44])

                        value_str = f"dat={dat_no}, off={offset}, size={size}, ts={ts}, #tx={no_txs}, sent={total_sent}, fee={fee}, height={height}"

                        print(
                            "║ {:<98} │ {:<98} ║".format(f"blk={key.hex()}", value_str)
                        )
                    elif name == "HEIGHT_DB":
                        print(
                            "║ {:<98} │ {:<98} ║".format(
                                f"height={bytes_to_int(key)}", f"blk={value.hex()}"
                            )
                        )
                    elif name == "TX_DB":
                        dat_no = bytes_to_int(value[0:4])
                        offset = bytes_to_int(value[4:8])
                        size = bytes_to_int(value[8:12])
                        pos = bytes_to_int(value[12:16])
                        height = bytes_to_int(value[16:24])
                        value_str = (
                            f"dat={dat_no}, off={offset}, size={size}, pos={pos}, height={height}"
                        )
                        print(
                            "║ {:<98} │ {:<98} ║".format(f"tx={key.hex()}", value_str)
                        )

                    elif name == "UTXO_DB":
                        tx = key[:32].hex()
                        idx = bytes_to_int(key[32:])
                        print(
                            "║ {:<98} │ {:<98} ║".format(f"tx={tx}, idx={idx}", f"{truncate_bytes(value, ends=4)}")
                        )
                    elif name == "MEMPOOL_DB":
                        tx = key.hex()
                        print(
                            "║ {:<98} │ {:<98} ║".format(f"{tx=}", f"{truncate_bytes(value, ends=8)}")
                        )
        print("╚" + "═" * w + "╧" + "═" * w + "╝")


def print_dat(n, start, end=-1):
    dat_file = APP_CONFIG.get("path", "blockchain") / f"blk{n:08}.dat"

    with open(dat_file, "rb") as dat:
        dat.seek(start)
        if end == -1:
            raw = dat.read()
        else:
            raw = dat.read(end - start)

        print(f"Opening {dat_file} Bytes {start} to {end}:")
        print_bytes(raw)
