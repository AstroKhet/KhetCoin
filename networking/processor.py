from networking.messages.types import *
from networking.messages.envelope import MessageEnvelope
from networking.processes import PROCESS_MAP


# … import other message types as you implement them …


class MessageProcessor:
    def __init__(self, node):
        self.node = node

    async def process_message(self, peer, menv: MessageEnvelope):
        command = menv.command
        message = menv.message
        match command:
            # case b"version":
            #     await self.process_version(peer, menv)
            # case b"verack":
            #     await self.process_verack(peer)
            case b"ping":
                await self.process_ping(peer, message)
            # case b"pong":
            #     await self.process_pong(peer, message)
            case b"inv":
                await self.process_inv(peer, message)
            case b"getdata":
                await self.process_getdata(peer, message)
            case b"getblocks":
                await self.process_getblocks(peer, message)
            case b"block":
                await self.process_block(peer, message)
            case b"tx":
                await self.process_tx(peer, message)
            # … add more as needed …
            case _:
                print(f"[{self.node.name}] Unknown command: {command!r}")

    # async def process_version(self, peer, menv: MessageEnvelope):
    #     """
    #     1. Validate peer’s protocol version >= our min.
    #     2. Check timestamp sanity.
    #     3. Check for self‑connection via nonce.
    #     4. Send our verack.
    #     5. Possibly update peer’s advertised start_height in Node state.
    #     """
    #     # … your logic here …

    # async def process_verack(self, peer):
    #     """
    #     1. Mark handshake as fully complete for this peer.
    #     2. Now ready to send/receive other messages.
    #     """
    #     # … your logic here …

    async def process_ping(self, peer, msg: PingMessage):
        """
        1. Extract nonce from payload.
        2. Reply with a pong message containing same nonce.
        """
        nonce = msg.nonce
        pong_message = PongMessage(nonce=nonce)
        
        menv = MessageEnvelope(
            command=pong_message.command,
            payload=pong_message.payload,
        )
        
        await peer.send(menv)


    # async def process_pong(self, peer, menv: MessageEnvelope):
    #     """
    #     1. Match pong nonce to outstanding ping.
    #     2. Measure round‑trip latency or just ignore.
    #     """
    #     # … your logic here …

    async def process_inv(self, peer, menv: MessageEnvelope):
        """
        1. For each inventory vector:
           a. If we don’t have it, add to a getdata request.
        2. Send a single getdata message for missing items.
        """
        # … your logic here …

    async def process_getdata(self, peer, menv: MessageEnvelope):
        """
        1. For each requested hash:
           a. If it’s a block we have, send a block message.
           b. If it’s a tx we have, send a tx message.
        """
        # … your logic here …

    async def process_getblocks(self, peer, menv: MessageEnvelope):
        """
        1. Given locator hashes + stop hash:
           a. Find the highest common block.
           b. Send an inv message with up to N block hashes after that.
        """
        # … your logic here …

    async def process_block(self, peer, menv: MessageEnvelope):
        """
        1. Validate block header + proof‑of‑work.
        2. Insert into blockchain DB.
        3. Broadcast inv for this new block to other peers.
        """
        # … your logic here …

    async def process_tx(self, peer, menv: MessageEnvelope):
        """
        1. Validate transaction (syntax, signatures).
        2. Add to mempool if valid.
        3. Broadcast inv for this tx to other peers.
        """
        # … your logic here …
