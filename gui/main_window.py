import tkinter as tk
import asyncio
import threading

from networking.node import Node
from networking.constants import NETWORK_PORT

print(tk.TkVersion)

class KhetcoinApp:
    def __init__(self, root: tk.Tk, node: Node):
        self.root = root
        self.node = node

        self.root.title(f"{node.name}'s Khetcoin Console")

