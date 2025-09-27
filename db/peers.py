import aiosqlite
import sqlite3

from ktc_constants import PEERS_SQL, PEER_INACTIVE_TIMEOUT, MAX_PEERS
from networking.constants import GETADDR_LIMIT
from utils.ip import format_ip


PEERS_COLS = [
    ("ip", "TEXT PRIMARY KEY"),
    ("port", "INTEGER"),
    ("last_seen", "INTEGER"),
    ("services", "INTEGER"),
    ("name", "TEXT"),
    ("ban_score", "INTEGER DEFAULT 0"),
]

def create_peers_table():
    """Creates the peers table. Should be used ONLY in utils.setup:INITIAL_SETUP"""
    con = sqlite3.connect(PEERS_SQL)
    cur = con.cursor()

    cols = ",\n    ".join(f"{field} {sql_type}" for field, sql_type in PEERS_COLS)
    sql = f"CREATE TABLE IF NOT EXISTS peers (\n    {cols}\n);"
    cur.execute(sql)

    con.commit()
    con.close()


async def check_if_peer_exists(ip: bytes | str) -> bool:
    if isinstance(ip, bytes):
        ip = format_ip(ip)

    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute(
            "SELECT EXISTS(SELECT 1 FROM peers WHERE ip = ?)",
            (ip,)
        ) as cur:
            res = await cur.fetchone()
            if res:
                return bool(res[0])
            return False


async def change_ban_score_by(ip: str | bytes, delta: int = 0) -> None:
    if isinstance(ip, bytes):
        ip = format_ip(ip)

    async with aiosqlite.connect(PEERS_SQL) as db:
        await db.execute(
            """
            UPDATE peers
            SET ban_score = MAX(ban_score + ?, 0)
            WHERE ip = ?
            """,
            (delta, ip),
        )
        await db.commit()


async def save_peer_from_addr(addr: tuple):
    """
    Saves an address from `AddrMessage`
    
    `addr` should be as is from `AddrMessage` with 4 entries:
        timestamp: int
        services: int
        ip: bytes
        port: int
    """
    timestamp, services, ip, port = addr
    ip = format_ip(ip)
    
    # Insert if ip does not exist, otherwise ignore
    async with aiosqlite.connect(PEERS_SQL) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO peers (ip, port, last_seen, services)
            VALUES (?, ?, ?, ?)
            """,
            (ip, port, timestamp, services)
        )
        await db.commit()


async def load_peers():
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute(
            "SELECT * FROM peers ORDER BY RANDOM() LIMIT ?", (MAX_PEERS, )
        ) as cur:
            peers = await cur.fetchall()
    return peers


async def get_active_peers(limit=GETADDR_LIMIT):
    """Randomly chooses peers with last_seen less than `PEER_INACTIVE_TIMEOUS` seconds ago, up to `limit`"""
    
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute(
            "SELECT * FROM peers WHERE last_seen > ? ORDER BY RANDOM() LIMIT ?", (PEER_INACTIVE_TIMEOUT, limit)
        ) as cur:
            peers = await cur.fetchall()
            return peers


# Say you want to add a block_height column later:

# cur.execute("ALTER TABLE peers ADD COLUMN block_height INTEGER")
# conn.commit()
