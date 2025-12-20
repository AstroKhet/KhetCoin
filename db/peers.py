import aiosqlite

from networking.constants import GETADDR_LIMIT
from utils.ip import format_ip
from utils.config import APP_CONFIG

PEERS_SQL = APP_CONFIG.get("path", "peers")
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
    """
	"id"	INTEGER,
	"name"	TEXT,
	"ip"	TEXT,
	"port"	INTEGER,
	"added"	INTEGER,
	"last_seen"	INTEGER,
	"ban_score"	INTEGER DEFAULT 0,
    )"""
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute(
            "SELECT * FROM peers ORDER BY RANDOM() LIMIT ?", (APP_CONFIG.get("node", "max_peers"),)
        ) as cur:
            peers = await cur.fetchall()
    return peers


async def get_active_peers(limit=GETADDR_LIMIT):
    """Randomly chooses peers with last_seen less than `cfg:peer_inactive_timeout` seconds ago, up to `limit`"""
    
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute(
            "SELECT * FROM peers WHERE last_seen > ? ORDER BY RANDOM() LIMIT ?", (APP_CONFIG.get("node", "peer_inactive_timeout"), limit)
        ) as cur:
            peers = await cur.fetchall()
            return peers


# Say you want to add a block_height column later:

# cur.execute("ALTER TABLE peers ADD COLUMN block_height INTEGER")
# conn.commit()
