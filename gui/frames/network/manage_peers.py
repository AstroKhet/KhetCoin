import logging
import tkinter as tk
from tkinter import ttk

from datetime import timedelta
from gui.bindings import bind_hierarchical, mousewheel_cb

from gui.helper import display_error_window
from networking.node import Node
from networking.peer import Peer

from utils.fmt import format_bytes

log = logging.getLogger(__name__)
# TODO Save peers into peers.json
# TODO Open separate windows with GUI to modify peers.json, allow setting of names/initial connect etc

class ManagePeersFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        self.selected_peer_id = None
        self.selected_peer = None
        self.labels_peer_details = {}

        # 0. Main layout: Left panel and (initially hidden) Right details panel
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)  # Left panel takes more space initially
        self.grid_columnconfigure(1, weight=0)  # Right panel

        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.grid_rowconfigure(0, weight=0)  # Top-left info area
        self.frame_main.grid_rowconfigure(1, weight=1)  # Bottom-left peer list area
        self.frame_main.grid_columnconfigure(0, weight=1)

        # 1.1 Top-Left: Basic Info Area
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

        # 1.2 Bottom-Left: Scrollable Peer List Area
        peer_list_cols = {
            "id": ("Peer ID", 30),
            "name": ("Name", 100),
            "address": ("Address", 150),
            "user_agent": ("User Agent", 150),
            "direction": ("Direction", 80),
            "ping": ("Ping (ms)", 80),
        }

        self.lf_peers = ttk.LabelFrame(self.frame_main, text="Connected Peers", padding="5")
        self.lf_peers.grid(row=1, column=0, sticky="nsew")
        self.lf_peers.grid_rowconfigure(0, weight=1)
        self.lf_peers.grid_columnconfigure(0, weight=1)

        self.tree_peers = ttk.Treeview(
            self.lf_peers,
            columns=list(peer_list_cols.keys()),
            show="headings",
            selectmode="browse",
        )

        for col_id, (text, width) in peer_list_cols.items():
            self.tree_peers.heading(col_id, text=text)
            self.tree_peers.column(col_id, width=width, minwidth=50, stretch=True)

        vsb_peers = ttk.Scrollbar(self.lf_peers, orient="vertical", command=self.tree_peers.yview)
        hsb_peers = ttk.Scrollbar(self.lf_peers, orient="horizontal", command=self.tree_peers.xview)
        self.tree_peers.configure(yscrollcommand=vsb_peers.set, xscrollcommand=hsb_peers.set)

        self.tree_peers.grid(row=0, column=0, sticky="nsew")
        vsb_peers.grid(row=0, column=1, sticky="ns")
        hsb_peers.grid(row=1, column=0, sticky="ew")

        self.tree_peers.bind("<<TreeviewSelect>>", self._on_peer_select)

        # 2. RIGHT panel (peer details, hidden initially)
        self.frame_details = ttk.LabelFrame(self, text="Peer Info")
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
        self.cnv_peer_details.create_window((0, 0), window=self.lf_peer_details, anchor="nw")

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
            "Ping Time", "Min Ping", "Time Offset"
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

        # 3. Initital setup
        bind_hierarchical("<MouseWheel>", self.frame_details, lambda e: mousewheel_cb(e, self.cnv_peer_details))
        self._generate_peer_list_treeview()
        self._hide_peer_details()
        self._update()

    def _generate_peer_list_treeview(self):
        latest_peers = list(self.node.peers)
        tree_peers_iids = set(self.tree_peers.get_children())

        # 1. Add or update peers
        for peer in latest_peers:
            values = (
                peer.session_id,
                peer.name or "N/A",
                peer.str_ip,
                peer.user_agent.decode(),
                peer.direction.title(),
                peer.latest_ping_time or "N/A",
            )
            
            if str(peer.session_id) in tree_peers_iids:
                self.tree_peers.item(peer.session_id, values=values)
                tree_peers_iids.remove(str(peer.session_id))
            else:
                self.tree_peers.insert("", "end", iid=peer.session_id, values=values)
        
        for iid in tree_peers_iids:
            self.tree_peers.delete(iid)
            
        # 2. Misc updates
        self.label_connected_peers.config(text=f"Connected Peers: {len(latest_peers)}")
    
    def _on_peer_select(self, _):
        selection = self.tree_peers.selection() #
        if not selection:  # Ignore deselction
            return

        self.selected_peer_id = int(selection[0])
        peer = self.node.get_peer_by_id(self.selected_peer_id)
        if peer:
            self.selected_peer = peer
            self._show_peer_details(peer)
        else:
            display_error_window(self, title="Something went wrong", err="Error retrieving peer info")

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
            "Time Offset": "version msg",
        }

        for field_name, label_widget in self.labels_peer_details.items():
            label_widget.config(text=details_map.get(field_name, "N/A"))

    def _hide_peer_details(self):
        self.frame_details.grid_remove()
        self.selected_peer_id = None
        self.selected_peer = None

    def _update(self):
        # Time updating
        
        # Peer list updating
        if self.node.check_updated_peers():
            self._generate_peer_list_treeview()
            
        # Peer details updating
        if self.frame_details.winfo_ismapped():
            self._config_peer_details(self.selected_peer)

        self.after(500, self._update)
