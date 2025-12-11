import tkinter as tk

from networking.node import Node



class ProfileFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        tk.Label(self, text=self.node.name).pack()
        
        