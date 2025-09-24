import tkinter as tk
from datetime import timedelta
from networking.node import Node
from utils.fmt import format_bytes

# TODO: Add a way to record data sent/recv per session in Node
# TODO: Add a live graph that updates every 0.5s or so for data transmission rate
# TODO: Implement button to go to connected peers next to connected count


class NodeFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        LEFT = tk.Frame(self, bg="white")
        LEFT.place(relx=0, rely=0, relwidth=0.5, relheight=1.0)

        label_name = tk.Label(
            LEFT, text=f"{node.name}'s Node", bg="white", font=("Arial", 16)
        )
        label_name.pack(fill="x", pady=(20, 50), padx=10)

        def toggle_server_switch():
            if btn_server["text"] == "START":
                btn_server.config(text="Starting...", bg="#a8d5b8")  # Light green
                self.controller.start_node()
                btn_server.config(text="STOP", bg="#dc3545")  # Strong red
            else:
                btn_server.config(text="Closing...", bg="#e69a9a")  # Desaturated red
                self.controller.close_node()
                self._update()  # Immediately reset uptime
                btn_server.config(text="START", bg="#28a745")  # Vibrant green

        # BUTTON to start/stop server
        btn_server = tk.Button(
            LEFT,
            text="START",
            bg="#28a745",
            fg="white",
            height=2,
            font=("Arial", 12),
            command=toggle_server_switch,
        )
        btn_server.pack(fill=tk.BOTH, padx=40, pady=15)

        # BUTTON to go to Network/Manage Peers
        btn_peers = tk.Button(
            LEFT,
            text="Manage Peers",
            bg="#007bff",  # Navigation blue
            fg="white",
            height=2,
            font=("Arial", 10),
            command=lambda: self.controller.switch_to_frame("manage_peers"),
        )
        btn_peers.pack(fill=tk.BOTH, padx=40, pady=15)

        # Right side
        RIGHT = tk.Frame(self)
        RIGHT.place(relx=0.5, rely=0, relwidth=0.5, relheight=1.0)

        # Info labels with alternating background colors
        self.label_ip = tk.Label(
            RIGHT,
            text=f"Public IP address: {node.public_ip_addr}",
            anchor="w",
            bg="white",
            padx=10,
        )
        self.label_uptime = tk.Label(
            RIGHT,
            text=f"Server uptime: {timedelta(seconds=node.uptime)}",
            anchor="w",
            bg="#f0f0f0",
            padx=10,
        )
        self.label_peers = tk.Label(
            RIGHT,
            text=f"No. connected peers: {len(node.peers)}",
            anchor="w",
            bg="white",
            padx=10,
        )
        self.label_data_sent = tk.Label(
            RIGHT,
            text=f"Data sent: {format_bytes(self.node.bytes_sent)}",
            anchor="w",
            bg="#f0f0f0",
            padx=10,
        )
        self.label_data_received = tk.Label(
            RIGHT,
            text=f"Data received: {format_bytes(self.node.bytes_recv)}",
            anchor="w",
            bg="white",
            padx=10,
        )

        # Pack all labels
        self.label_ip.pack(fill="x", pady=2)
        self.label_uptime.pack(fill="x", pady=2)
        self.label_peers.pack(fill="x", pady=2)
        self.label_data_sent.pack(fill="x", pady=2)
        self.label_data_received.pack(fill="x", pady=2)

        # Start periodic updates
        self._update()

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
