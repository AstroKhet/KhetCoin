import tkinter as tk

from networking.node import Node

print(tk.TkVersion)

class KhetcoinGUI:
    def __init__(self, root: tk.Tk, node: Node):
        self.root = root
        self.node = node
        
        self.root.title(f"{node.name}'s Khetcoin Console")
        
        