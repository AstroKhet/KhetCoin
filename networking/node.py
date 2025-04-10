import asyncio
import json
from pathlib import Path

from utils.helper import str_ip

from networking.constants import HANDSHAKE_TIMEOUT
from networking.peer import Peer
from networking.processor import MessageProcessor

# Constants
DEFAULT_PEERS_FILE = Path(".local/peers.json")  # Format: {"peers": [["ip", port], ...]}

MAX_PEERS = 8  # Bitcoin Core default


class Node:
    def __init__(self, name: str, host="0.0.0.0", port: int = 9333):
        self.name = name
        self.host = host
        self.port = port
        self.peers = set()
        self.server: asyncio.Server

        self.processor = MessageProcessor(self)
        self.message_queue = asyncio.Queue()

    async def start_server(self):
        self.server = await asyncio.start_server(self.handle_peer, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        print(f"[{self.name}] Listening on {addr}")
        async with self.server:
            await self.server.serve_forever()

    async def handle_peer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        print(f"[{self.name}] Incoming connection from {addr}")
        peer = Peer(self, reader, writer)

        try:
            established = await asyncio.wait_for(peer.respond_handshake(), timeout=HANDSHAKE_TIMEOUT)
        except asyncio.TimeoutError:
            print(f"[{self.name}] Handshake timed out from incoming {str_ip(addr)}")
            await peer.close()
            return

        if established:
            self.peers.add(peer)
            asyncio.create_task(peer.listen())
            print(f"Incoming handshake complete from {str_ip(addr)}")
        else:
            print(f"Handshake failed from incoming {str_ip(addr)}")
            await peer.close()

    async def connect_to_peer(self, addr: tuple, name: str = ""):
        try:
            reader, writer = await asyncio.open_connection(
                addr[0], addr[1], local_addr=(self.host, self.port)
            )
        except (ConnectionRefusedError, OSError) as e:
            print(
                f"Could not connect to {str_ip}: {e}"
            )
            return

        print(f"Connected to peer: {str_ip(addr, name)}")
        peer = Peer(self, reader, writer, name)

        try:
            established = await asyncio.wait_for(
                peer.initiate_handshake(), timeout=HANDSHAKE_TIMEOUT
            )
        except asyncio.TimeoutError:
            print(
                f"Handshake timed out with {str_ip(addr, name)}"
            )
            await peer.close()
            return

        if established:
            self.peers.add(peer)
            asyncio.create_task(peer.listen())
            print(f"Handshake complete with {str_ip(addr)}")
        else:
            print(f"[{self.name}] Handshake failed with {str_ip(addr)}")
            await peer.close()

    def remove_peer(self, peer):
        self.peers.discard(peer)

    def load_peers_from_json(self, file_path: Path = DEFAULT_PEERS_FILE):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Peers file not found: {file_path}. Starting with no peers.")
            return {}

        except json.JSONDecodeError:
            print(f"Error decoding JSON from {file_path}. Starting with no peers.")
            return {}

    async def broadcast(self, message):
        for peer in list(self.peers):  # Copy to avoid modification during iteration
            await peer.send(message)

    async def message_dispatcher(self):
        while True:
            peer, message_envelope = await self.message_queue.get()
            try:
                # Await the async processing of the message
                await self.processor.process_message(peer, message_envelope)
            except Exception as e:
                print(f"Error processing message: {e}")

    async def run(self):
        server_task = asyncio.create_task(self.start_server())
        processor_task = asyncio.create_task(self.message_dispatcher())

        # EXAMPLE CONNECTION TO BOB

        for peer_name, peer_details in self.load_peers_from_json().items():
            peer_ip = peer_details["ip_address"]
            peer_port = peer_details["port"]

            await self.connect_to_peer((peer_ip, peer_port), peer_name)

        
        ## MANUAL INPUT LOOP FOR TESTING PURPOSES ONLY
        try:
            while True:
                msg = await asyncio.to_thread(
                    input, "Enter message (or 'exit' to stop): "
                )
                if msg.lower() == "exit":
                    break
                await self.broadcast(msg)
        finally:
            server_task.cancel()
            processor_task.cancel()


if __name__ == "__main__":
    node = Node(name="Alice", host="127.0.0.1", port=50000)

    asyncio.run(node.run())
