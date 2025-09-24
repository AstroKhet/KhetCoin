import tkinter as tk
from tkinter import ttk

from networking.node import Node


class MempoolFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
