import tkinter as tk
from tkinter import ttk

from datetime import timedelta
from gui.bindings import bind_hierarchical, mousewheel_cb

from networking.node import Node
from networking.peer import Peer

from utils.fmt import format_bytes

# TODO Save peers into peers.json
# TODO Open separate windows with GUI to modify peers.json, allow setting of names/initial connect etc

class PeersFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        self.selected_peer_id = None
        self.selected_peer = None
        self.labels_peer_details = {}

        # Main layout: Left panel and (initially hidden) Right details panel
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)  # Left panel takes more space initially
        self.grid_columnconfigure(1, weight=0)  # Right panel

        #####################################################################################################
        # Left Panel
        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.grid_rowconfigure(0, weight=0)  # Top-left info area
        self.frame_main.grid_rowconfigure(1, weight=1)  # Bottom-left peer list area
        self.frame_main.grid_columnconfigure(0, weight=1)

        # Top-Left: Basic Info Area
        self.lf_info_area = ttk.LabelFrame(self.frame_main, text="Network Info", padding="5")
        self.lf_info_area.grid(row=0, column=0, sticky="new", pady=(0, 5))
        self.lf_info_area.grid_columnconfigure(1, weight=1)

        self.label_connected_peers = ttk.Label(self.lf_info_area, text="Connected Peers: 0")
        self.label_connected_peers.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.btn_node = ttk.Button(
            self.lf_info_area,
            text="Your Node",
            command=lambda: self.controller.switch_to_frame("node"),
        )
        self.btn_node.grid(row=0, column=1, sticky="e", padx=5, pady=2)

        # Bottom-Left: Scrollable Peer List Area
        # TODO Implement sorting of peers by some criteria
        # peers.sort(key=lambda p: p.id)  # Sort for consistent display
        self.lf_peers_list = ttk.LabelFrame(self.frame_main, text="Connected Peers", padding="5")
        self.lf_peers_list.grid(row=1, column=0, sticky="nsew")
        self.lf_peers_list.grid_rowconfigure(0, weight=1)
        self.lf_peers_list.grid_columnconfigure(0, weight=1)

        self.peer_list_cols = {
            "id": ("Peer ID", 30),
            "name": ("Name", 100),
            "address": ("Address", 150),
            "user_agent": ("User Agent", 150),
            "direction": ("Direction", 80),
            "ping": ("Ping (ms)", 80),
        }

        self.tree_peers_list = ttk.Treeview(
            self.lf_peers_list,
            columns=list(self.peer_list_cols.keys()),
            show="headings",
            selectmode="browse",
        )

        for col_id, (text, width) in self.peer_list_cols.items():
            self.tree_peers_list.heading(col_id, text=text)
            self.tree_peers_list.column(col_id, width=width, minwidth=50, stretch=tk.YES)

        self.vsb_peer_list = ttk.Scrollbar(self.lf_peers_list, orient="vertical", command=self.tree_peers_list.yview)
        self.hsb_peer_list = ttk.Scrollbar(self.lf_peers_list, orient="horizontal", command=self.tree_peers_list.xview)
        self.tree_peers_list.configure(yscrollcommand=self.vsb_peer_list.set, xscrollcommand=self.hsb_peer_list.set)

        self.tree_peers_list.grid(row=0, column=0, sticky="nsew")
        self.vsb_peer_list.grid(row=0, column=1, sticky="ns")
        self.hsb_peer_list.grid(row=1, column=0, sticky="ew")

        self.tree_peers_list.bind("<<TreeviewSelect>>", self._on_peer_select)

        #####################################################################################################################################
        # RIGHT panel (peer details, hidden initially)
        self.frame_details = ttk.Frame(self)
        self.frame_details.grid(row=0, column=1, sticky="nsew")

        self.frame_details.grid_rowconfigure(0, weight=1)
        self.frame_details.grid_columnconfigure(0, weight=1)

        self.cnv_peer_details = tk.Canvas(self.frame_details, borderwidth=0, highlightthickness=0)
        self.cnv_peer_details.grid(row=0, column=0, sticky="nsew")

        self.vsb_peer_details = ttk.Scrollbar(self.frame_details, orient="vertical", command=self.cnv_peer_details.yview)
        self.hsb_peer_details = ttk.Scrollbar(self.frame_details, orient="horizontal", command=self.cnv_peer_details.xview)

        self.vsb_peer_details.grid(row=0, column=1, sticky="ns") 
        self.hsb_peer_details.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.cnv_peer_details.configure(
            yscrollcommand=self.vsb_peer_details.set,
            xscrollcommand=self.hsb_peer_details.set
        )

        self.lf_peer_details = ttk.LabelFrame(self.cnv_peer_details, text="Peer Details", padding="10")

        self.cnv_window_id = self.cnv_peer_details.create_window((0, 0), window=self.lf_peer_details, anchor="nw")

        self.frame_details_content = ttk.Frame(self.lf_peer_details, padding="5")
        self.frame_details_content.pack(expand=True, fill="both") 

        self.lf_peer_details.bind(
            "<Configure>",
            lambda _: self.cnv_peer_details.configure(scrollregion=self.cnv_peer_details.bbox("all"))
        )

        detail_fields = [
            "Name", "Direction", "Peer ID", "Address", "User Agent",
            "Services", "Version", "Transaction Relay", "Starting Block",
            "Synced Headers", "Synced Blocks",
            "Connection Time",
            "Last Block", "Last Transaction", "Last Send", "Last Receive",
            "Sent", "Received",
            "Ping Time", "Ping Wait", "Min Ping", "Time Offset"
        ]

        for i, field_name in enumerate(detail_fields):
            label_title = ttk.Label(self.frame_details_content, text=f"{field_name}:")
            label_title.grid(row=i, column=0, sticky="w", padx=5, pady=2)

            label_value = ttk.Label(self.frame_details_content, text="N/A", anchor="w")
            label_value.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.labels_peer_details[field_name] = label_value

        self.frame_details_content.grid_columnconfigure(1, weight=1)

        self.btn_close_details = ttk.Button(
            self.lf_peer_details, text="Close Details", command=self._hide_peer_details
        )
        self.btn_close_details.pack(side="bottom", pady=10, anchor="w", padx=10)

        # Bind mousewheel scroll to every widget housed within self.right_frame
        bind_hierarchical("<MouseWheel>", self.frame_details, lambda e: mousewheel_cb(e, self.cnv_peer_details))
        self._update()
        self._hide_peer_details()  # Ensure it's hidden initially

    def _on_peer_select(self, _):
        selection = self.tree_peers_list.selection() #
        if not selection:  # Ignore deselction
            return

        self.selected_peer_id = int(selection[0])
        peer = self.node.get_peer_by_id(self.selected_peer_id)
        if peer:
            self.selected_peer = peer
            self._show_peer_details(peer)
        else:
            # TODO Invalid peer selection
            pass

    def _show_peer_details(self, peer: Peer):
        # Only grid the area and set title
        if not self.frame_details.winfo_ismapped():
            self.frame_details.grid(row=0, column=1, sticky="nsew")

        self.lf_peer_details.config(text=f"Peer no. {peer.session_id}")
        self._config_peer_details(peer)

    def _config_peer_details(self, peer: Peer):
        details_map = {
            "Name": peer.name or "N/A",
            "Direction": peer.direction.title(),
            "Peer ID": peer.session_id,
            "Address": peer.str_ip,
            "User Agent": peer.user_agent.decode(),
            "Services": f"{peer.services} # into text",
            "Version": peer.version,
            "Transaction Relay": "Yes" if peer.relay else "No",
            "Starting Block": peer.start_height,
            "Synced Headers": "# snyced headers",
            "Synced Blocks": "# Synced blocks",
            "Connection Time": f"{timedelta(seconds=peer.connection_time)}",
            "Last Block": f"{peer.last_block}s" if peer.last_block else "Never",
            "Last Transaction": f"{peer.last_tx}s" if peer.last_tx else "Never",
            "Last Send": f"{peer.last_send}s" if peer.last_send else "Never",
            "Last Receive": f"{peer.last_recv}s" if peer.last_recv else "Never",
            "Sent": format_bytes(peer.bytes_sent),
            "Received": format_bytes(peer.bytes_recv),
            "Ping Time": f"{peer.latest_ping_time} ms",
            "Ping Wait": "## if still pending ping else N/A",
            "Min Ping": "N/A" if not peer.ping_times else f"{min(peer.ping_times)} ms",
            "Time Offset": "# calculate from version msg",
        }

        for field_name, label_widget in self.labels_peer_details.items():
            label_widget.config(text=details_map.get(field_name, "N/A"))

    def _hide_peer_details(self):
        self.frame_details.grid_remove()
        self.selected_peer_id = None

    def _update(self):
        peers = list(self.node.peers)  # Convert set to list for iteration
        self.label_connected_peers.config(text=f"Connected Peers: {len(peers)}")

        # Map of current peers keyed by session_id
        current_peers = {peer.session_id: peer for peer in peers}
        existing_ids = set(self.tree_peers_list.get_children())

        # 1️⃣ Add or update peers
        for session_id, peer in current_peers.items():
            values = (
                peer.session_id,
                peer.name or "N/A",
                peer.str_ip,
                peer.user_agent.decode(),
                peer.direction.title(),
                peer.latest_ping_time or "N/A",
            )

            if session_id in existing_ids:
                # Compare existing row values to avoid unnecessary updates
                current_values = self.tree_peers_list.item(session_id, "values")
                if current_values != values:
                    self.tree_peers_list.item(session_id, values=values)
            else:
                # New peer, insert it
                self.tree_peers_list.insert("", "end", iid=session_id, values=values)

        # 2️⃣ Remove disconnected peers
        for iid in existing_ids - current_peers.keys():
            self.tree_peers_list.delete(iid)

        if self.frame_details.winfo_ismapped() and self.selected_peer:
            if self.selected_peer.session_id not in current_peers: # Peer disconnected 
                self.selected_peer = self.selected_peer_id = None
                self._hide_peer_details()
            else:
                self._config_peer_details(self.selected_peer)

        self.after(500, self._update)
