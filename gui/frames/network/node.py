import tkinter as tk
from datetime import timedelta
from gui.colours import colour_pattern_gen
from networking.node import Node
from utils.config import APP_CONFIG
from utils.fmt import format_bytes

# TODO: Add a way to record data sent/recv per session in Node
# TODO: Add a live graph that updates every 0.5s or so for data transmission rate
# TODO: Implement button to go to connected peers next to connected count
from time import time

class NodeFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        frame_left = tk.Frame(self, bg="white")
        frame_left.place(relx=0, rely=0, relwidth=0.5, relheight=1.0)

        label_name = tk.Label(
            frame_left, text=f"{node.name}'s Node", bg="white", font=("Arial", 16)
        )
        label_name.pack(fill="x", pady=(20, 50), padx=10)

        # BUTTON to start/stop server
        self.btn_server = tk.Button(
            frame_left,
            text="Start Node",
            bg="#28a745",
            fg="white",
            height=2,
            font=("Segue UI", 15, "bold"),
            command=self._toggle_server_switch
        )
        if self.node.is_running:
            self.btn_server.config(text="Shutdown Node", bg="#dc3545")
        self.btn_server.pack(fill=tk.BOTH, padx=40, pady=15)

        # BUTTON to go to Network/Manage Peers
        btn_peers = tk.Button(
            frame_left,
            text="Manage Peers",
            bg="#6e7f80",
            fg="white",
            height=2,
            font=("Segue UI", 15, "bold"),
            command=lambda: self.controller.switch_to_frame("manage_peers"),
        )
        btn_peers.pack(fill=tk.BOTH, padx=40, pady=15)

        # Right side
        frame_right = tk.Frame(self)
        frame_right.place(relx=0.5, rely=0, relwidth=0.5, relheight=1.0)

        # Info labels with alternating background colors
        clr_gen = colour_pattern_gen(["#ffffff", "#f0f0f0"])
        self.label_uptime = tk.Label(frame_right, text=f"Server uptime: {timedelta(seconds=node.uptime)}", anchor="w", bg=next(clr_gen), padx=10)
        self.label_uptime.pack(fill="x", pady=2)

        self.label_peers = tk.Label(frame_right, text=f"No. connected peers: {len(node.peers)}", anchor="w", bg=next(clr_gen), padx=10)
        self.label_peers.pack(fill="x", pady=2)

        self.label_data_sent = tk.Label(frame_right, text=f"Data sent: {format_bytes(self.node.bytes_sent)}", anchor="w", bg=next(clr_gen), padx=10)
        self.label_data_sent.pack(fill="x", pady=2)

        self.label_data_received = tk.Label(frame_right, text=f"Data received: {format_bytes(self.node.bytes_recv)}", anchor="w", bg=next(clr_gen), padx=10)
        self.label_data_received.pack(fill="x", pady=2)


        # Start periodic updates
        self._update()
        
    def _toggle_server_switch(self):
        if self.btn_server.cget("text") == "Start Node":
            self.controller.start_node()
            self.btn_server.config(text="Shutdown Node", bg="#dc3545")
        else:
            self.controller.close_node()
            self._update()  # Immediately reset uptime
            self.btn_server.config(text="Start Node", bg="#28a745") 
            
    def _update(self):
        self.label_uptime.configure(
            text=f"Server uptime: {timedelta(seconds=self.node.uptime)}"
        )

        self.label_peers.configure(
            text=f"No. connected peers: {len(self.node.peers)}"
        )
        
        self.label_data_sent.configure(
            text=f"Data sent: {format_bytes(self.node.bytes_sent)}"
        )
        self.label_data_received.configure(
            text=f"Data received: {format_bytes(self.node.bytes_recv)}"
        )

        self.after(500, self._update)
