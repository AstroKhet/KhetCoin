import time
import aiosqlite

from utils.ip import ip_bytes_to_str, ip_convert_to_bytes
from utils.config import APP_CONFIG

from dataclasses import dataclass

@dataclass
class PeerMeta:
    _id: int
    name: str
    ip: str
    port: int
    added: int
    last_seen: int
    services: int
    
    @property
    def ip_bytes(self):
        return ip_convert_to_bytes(self.ip)
    



PEERS_SQL = APP_CONFIG.get("path", "peers")
async def save_peer_from_addr(addr_msg_data: tuple):
    """
    Saves an address from `AddrMessage`
    
    `addr` should be as is from `AddrMessage` with 4 entries:
        timestamp: int
        services: int
        ip: bytes
        port: int
    """
    timestamp, services, ip, port = addr_msg_data
    ip = ip_bytes_to_str(ip)
    
    # Insert if ip does not exist, otherwise ignore
    async with aiosqlite.connect(PEERS_SQL) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO peers (name, ip, port, added, last_seen, services)
            VALUES (?, ?, ?, ?)
            """,
            ("Peer", ip, port, int(time.time()), timestamp, services)
        )
        await db.commit()


async def load_all_peers():
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute("SELECT * FROM peers ORDER BY last_seen DESC") as cur:
            peers = await cur.fetchall()
            
    return [PeerMeta(*peer) for peer in peers]


async def load_all_active_peers():
    latest_last_seen = int(time.time()) - APP_CONFIG.get("node", "peer_inactive_timeout")
    async with aiosqlite.connect(PEERS_SQL) as db:
        async with db.execute("SELECT * FROM peers WHERE last_seen > ? ORDER BY RANDOM()", (latest_last_seen, )) as cur:
            peers = await cur.fetchall()
    return [PeerMeta(*peer) for peer in peers]


async def set_last_seen(ip, port, last_seen):
    async with aiosqlite.connect(PEERS_SQL) as db:
        await db.execute("UPDATE peers SET last_seen = ? WHERE ip = ? AND port = ?;", (last_seen, ip, port))
        