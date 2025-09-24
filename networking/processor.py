import logging
import asyncio
import time

from blockchain.block import Block
from blockchain.transaction import Transaction

from crypto.hashing import HASH256
from db.tx import get_tx_exists, get_txn
from db.block import *
from db.peers import get_active_peers, save_peer_from_addr

from networking.constants import BLOCK_TYPE, GETADDR_LIMIT, GETBLOCKS_LIMIT, GETHEADERS_LIMIT, TX_TYPE
from networking.messages.envelope import MessageEnvelope
from networking.messages.types import *
from networking.messages.types import notfound
from networking.peer import Peer

from utils.helper import encode_ip, int_to_bytes, int_to_bytes
from utils.ip import is_routable


log = logging.getLogger(__name__)


class MessageProcessor:
    """Central processing interface for handling the node's message queue."""

    def __init__(self, node):
        self.node = node

    async def process_message(self, peer: Peer, env: MessageEnvelope):
        command = env.command
        message = env.message # The parsed message object (e.g., VersionMessage instance)

        command_str = command.decode('ascii', errors='replace')

        log.debug(f"Processing command '{command_str}' from {peer.str_ip}")

        # Construct handler method name
        handler_name = f"process_{command_str}"
        handler_method = getattr(self, handler_name, None)

        if handler_method and callable(handler_method):
            if asyncio.iscoroutinefunction(handler_method):
                try:
                    await handler_method(peer, message)
                except Exception as e:
                    log.exception(f"Error executing handler '{handler_name}' for command {command_str} from {peer.str_ip}: {e}")
        else:
            log.warning(f"No handler method named '{handler_name}' found for command: {command_str!r} from {peer.str_ip}")
            # INCREASE BAN SCORE!!!

    async def process_version(self, peer: Peer, msg: VersionMessage):
        # Process version
        peer.version = msg.version
        peer.services = msg.services
        peer.user_agent = msg.user_agent
        peer.start_height = msg.start_height
        peer.relay = msg.relay

        # Basic Validation (Example)
        # TODO: Implement proper version negotiation and validation
        # if msg.version < 70000:  # Example: Reject very old protocol versions
        # await peer.close() # Optionally disconnect

        # 3. Send verack
        verack_envelope = MessageEnvelope(b"verack")
        await peer.send_message(verack_envelope)

    async def process_verack(self, peer: Peer, msg: VerackMessage):
        if not peer.established.done():
            peer.established.set_result(True)  # Signal successful handshake

    async def process_ping(self, peer: Peer, msg: PingMessage):
        # Create pong message with the same nonce
        pong_message = PongMessage(nonce=msg.nonce)
        pong_envelope = MessageEnvelope(
            command=pong_message.command,
            payload=pong_message.payload,
        )
        await peer.send_message(pong_envelope)

    async def process_pong(self, peer: Peer, msg: PongMessage):
        if not peer.pong_future.done():
            peer.pong_future.set_result(time.time())
        # else do nothing; pong should only happen after a ping, which resets peer.pong_future

    async def process_inv(self, peer: Peer, msg: InvMessage):
        # https://en.bitcoin.it/wiki/Protocol_documentation#inv
        # Allows a node to advertise its knowledge of one or more objects. It can be received unsolicited, or in reply to getblocks.
        # Payload (maximum 50,000 entries, which is just over 1.8 megabytes):

        inventory = msg.inventory
        missing_data = {
            TX_TYPE: [],  # TX
            BLOCK_TYPE: []   # Block
        }  # Statically typed because there will ever only be this many inv types

        for item in inventory:
            inv_type, inv_hash = item
            if inv_type == TX_TYPE:  # TX
                if peer.node.mempool.get_tx_exists(inv_hash):
                    continue
                elif get_tx_exists(inv_hash):
                    continue
            elif inv_type == BLOCK_TYPE: # BLOCK
                if get_block_exists(inv_hash):
                    continue
            else: # 0 or some other invalid type - ignore
                continue
            missing_data[inv_type].append(inv_hash)

        for inv_type, inv_hashes in missing_data.items():
            getdata_msg = GetDataMessage(inv_hashes)
            await peer.send_message(getdata_msg)

    async def process_getaddr(self, peer: Peer, msg: GetAddrMessage):
        addresses = set()
        for connected_peer in peer.node.peers:
            if connected_peer.ip == peer.ip:
                continue

            addr = (
                int_to_bytes(connected_peer.last_recv),
                int_to_bytes(connected_peer.services, 8),
                encode_ip(peer.ip),
                int_to_bytes(peer.port, 2)
            )
            addresses.add(addr)

        # default limit = 8, chosen by random
        active_peers = await get_active_peers(limit=GETADDR_LIMIT)
        for ip, port, last_recv, services, *_ in active_peers:
            addr = (
                int_to_bytes(last_recv),
                int_to_bytes(services, 8),
                encode_ip(ip),
                int_to_bytes(port, 2)
            )
            addresses.add(addr)

        addr_msg = AddrMessage(list(addresses))
        await peer.send_message(addr_msg)

    async def process_addr(self, peer: Peer, msg: AddrMessage):
        # Filter addresses
        addresses = [addr for addr in msg.addresses if is_routable(addr[2])]

        # Process incoming addresses
        for addr in addresses:
            # This trusts that other nodes are not sending bad data
            # Possible to implement aggregation to determine bad data
            save_peers_task = asyncio.create_task(save_peer_from_addr(addr))
            self.node.add_task(save_peers_task)

        # Relay addresses to 2 other random peers
        addr_msg = AddrMessage(addresses)

        await self.node.broadcast(
            message=addr_msg,
            exclude=peer,
            sample=2
        )

    async def process_getheaders(self, peer: Peer, msg: GetHeadersMessage):
        locator_hashes = msg.locator_hashes
        stop_hash = msg.hash_stop
        common_hash = None
        for block_hash in locator_hashes:
            if get_block_exists(block_hash):
                common_hash = block_hash

        if common_hash is None: 
            return

        curr_height = get_block_height_at_hash(common_hash)
        if curr_height is None:
            return
        
        headers = []
        # Collecting headers
        while len(headers) < GETHEADERS_LIMIT:
            curr_hash = get_block_hash_at_height(curr_height)
            if curr_hash is None:  # You have reached the tip of the blockchain
                break

            header = get_block_header(curr_hash)
            if header is None:  # Shouldn't happen unless you messed with your blockchain database
                break

            headers.append(header)
            if HASH256(header) == stop_hash: # Stop hash reached
                break

            curr_height += 1

        header_msg = HeadersMessage(headers)

        await peer.send_message(header_msg)

    async def process_headers(self, peer: Peer, msg: HeadersMessage):
        headers = msg.headers
        if len(headers) < 1:
            return

        start_header = headers[0]

        return 

    async def process_getblocks(self, peer: Peer, msg: GetBlocksMessage):
        locator_hashes = msg.locator_hashes
        stop_hash = msg.hash_stop
        common_hash = None
        for block_hash in locator_hashes:
            if get_block_exists(block_hash):
                common_hash = block_hash

        if common_hash is None:
            return
        # Collecting block hashes
        curr_height = get_block_height_at_hash(common_hash)
        if curr_height is None:
            return
        block_hashes = []
        while len(block_hashes) < GETBLOCKS_LIMIT:
            curr_hash = get_block_hash_at_height(curr_height)
            if curr_hash is None:  # You have reached the tip of the blockchain
                break

            if not get_block_exists(curr_hash):
                break

            block_hashes.append(curr_hash)
            if curr_hash == stop_hash:  # Stop hash reached
                break

            curr_height += 1

        block_inv = [(BLOCK_TYPE, block_hash) for block_hash in block_hashes]
        inv_msg = InvMessage(block_inv)

        await peer.send_message(inv_msg)

    async def process_block(self, peer: Peer, msg: BlockMessage):
        block_raw = msg.block
        block = Block.parse(BytesIO(block_raw), full_block=True)

        if get_block_exists(block.hash()):
            return

        if not block.verify():
            return

        return

    async def process_getdata(self, peer: Peer, msg: GetDataMessage):
        inventory = msg.inventory

        notfound_items = []
        for inv_type, inv_hash in inventory:
            if inv_type == TX_TYPE:
                if tx := get_txn(inv_hash):  # TODO: notfound msg
                    tx_msg = TxMessage(tx) # type: ignore
                    await peer.send_message(tx_msg)
                    continue

            elif inv_type == BLOCK_TYPE:
                if block := get_block(inv_hash):
                    block_msg = BlockMessage(block)
                    await peer.send_message(block_msg)
                    continue

            notfound_items.append((inv_type, inv_hash))

        await peer.send_message(NotFoundMessage(notfound_items))

    async def process_tx(self, peer: Peer, msg: TxMessage):
        tx_raw = msg.tx
        tx = Transaction.parse(BytesIO(tx_raw))

        # Mempool usage
        if get_tx_exists(tx.hash()):
            return

        if peer.node.mempool.add_tx(tx):
            log.info(f"Transaction {tx.hash().hex()} successfully added into mempool")
        else:
            log.info(f"Transaction {tx.hash().hex()} rejected from mempool")

        # Other usage if any

        return

    async def process_mempool(self, peer: Peer, msg: MempoolMessage):
        return

    async def process_notfound(self, peer: Peer, msg: NotFoundMessage):
        missing = msg.inventory
        return
