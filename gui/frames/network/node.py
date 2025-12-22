import tkinter as tk
from datetime import timedelta
from tkinter import messagebox
from gui.colours import BTN_CONFIG_GRAY, BTN_START_GREEN, BTN_STOP_RED, colour_pattern_gen
from networking.node import Node
from utils.config import APP_CONFIG
from utils.fmt import format_bytes

# TODO: Add a way to record data sent/recv per session in Node
# TODO: Add a live graph that updates every 0.5s or so for data transmission rate
# TODO: Implement button to go to connected peers next to connected count

_frame_id = 41

class NodeFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1, uniform="node_frame")
        self.columnconfigure(1, weight=1, uniform="node_frame")

        frame_left = tk.Frame(self, bg="white")
        frame_left.grid(row=0, column=0, sticky="nsew")

        label_name = tk.Label(frame_left, text=f"{node.name}'s Node", bg="white", font=("Arial", 16))
        label_name.pack(fill="x", pady=(20, 50), padx=10)

        # BUTTON to start/stop server
        self.btn_server = tk.Button(
            frame_left,
            text="Start Node",
            bg=BTN_START_GREEN,
            fg="white",
            height=2,
            font=("Segue UI", 15, "bold"),
            command=self._toggle_server_switch
        )
        if self.node.is_running:
            self.btn_server.config(text="Shutdown Node", bg=BTN_STOP_RED)
        self.btn_server.pack(fill=tk.BOTH, padx=40, pady=15)

        # BUTTON to go to Network/Manage Peers
        btn_peers = tk.Button(
            frame_left,
            text="Manage Peers",
            bg=BTN_CONFIG_GRAY,
            fg="white",
            height=2,
            font=("Segue UI", 15, "bold"),
            command=lambda: self.controller.switch_to_frame("manage_peers"),
        )
        btn_peers.pack(fill=tk.BOTH, padx=40, pady=15)

        # Right side
        frame_right = tk.Frame(self)
        frame_right.grid(row=0, column=1, sticky="nsew")
        frame_right.columnconfigure(1, weight=1)

        tk.Label(frame_right, text="Your IP Address:", anchor="w").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.label_ip_addr = tk.Label(frame_right, text=f"{self.node.external_ip}:{self.node.port}", anchor="w", padx=5)
        self.label_ip_addr.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # Server uptime
        tk.Label(frame_right, text="Server uptime:", anchor="w").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.label_uptime = tk.Label(frame_right, text=f"{timedelta(seconds=self.node.uptime())}", anchor="w", padx=5)
        self.label_uptime.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Number of peers
        tk.Label(frame_right, text="No. connected peers:", anchor="w").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.label_peers = tk.Label(frame_right, text=f"{len(self.node.peers)}", anchor="w", padx=5)
        self.label_peers.grid(row=2, column=1, sticky="w", padx=5, pady=2)

        # Data sent
        tk.Label(frame_right, text="Data sent:", anchor="w").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.label_data_sent = tk.Label(frame_right, text=f"{format_bytes(self.node.bytes_sent)}", anchor="w", padx=5)
        self.label_data_sent.grid(row=3, column=1, sticky="w", padx=5, pady=2)

        # Data received
        tk.Label(frame_right, text="Data received:", anchor="w").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.label_data_received = tk.Label(frame_right, text=f"{format_bytes(self.node.bytes_recv)}", anchor="w", padx=5)
        self.label_data_received.grid(row=4, column=1, sticky="w", padx=5, pady=2)


        # Start periodic updates
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    def _toggle_server_switch(self):
        if self.btn_server.cget("text") == "Start Node":
            if self.node.external_ip == "0.0.0.0":
                messagebox.showerror("Invalid IP", "Your IP port was not forwarded properly.")
                return
            self.controller.start_node()
            self.btn_server.config(text="Shutdown Node", bg="#dc3545")
        else:
            self.controller.close_node()
            self._update()  # Immediately reset uptime
            self.btn_server.config(text="Start Node", bg="#28a745") 
            
    def _update(self):
        if not self._is_active:
            return
        
        self.label_uptime.configure(text=str(timedelta(seconds=self.node.uptime())))
        self.label_peers.configure(text=str(len(self.node.peers)))
        self.label_data_sent.configure(text=format_bytes(self.node.bytes_sent))
        self.label_data_received.configure(text=format_bytes(self.node.bytes_recv))

        self.after(500, self._update)
