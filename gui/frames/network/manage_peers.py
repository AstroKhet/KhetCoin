import logging
import sqlite3
import time
import tkinter as tk
from tkinter import ttk, messagebox

from datetime import timedelta
from gui.bindings import bind_hierarchical, mousewheel_cb

from gui.frames.common.scrollable import create_scrollable_frame, create_scrollable_treeview
from gui.helper import center_popup
from networking.node import Node
from networking.peer import Peer

from utils.config import APP_CONFIG
from utils.fmt import format_age, format_bytes

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
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)  # Left panel takes more space initially
        self.columnconfigure(1, weight=0)  # Right panel

        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.rowconfigure(0, weight=0)  # Top-left info area
        self.frame_main.rowconfigure(1, weight=1)  # Bottom-left peer list area
        self.frame_main.columnconfigure(0, weight=1)

        # 1.1 Top-Left: Basic Info Area
        self.lf_info_area = ttk.LabelFrame(self.frame_main, text="Network Info", padding="5")
        self.lf_info_area.grid(row=0, column=0, sticky="new", pady=(0, 5))
        self.lf_info_area.columnconfigure(1, weight=1)

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
            "user_agent": ("User Agent", 80),
            "direction": ("Direction", 60),
            "connection_time": ("Connection Time", 80),
            "ping": ("Ping (ms)", 50),
        }

        self.lf_peers = ttk.LabelFrame(self.frame_main, text="Connected Peers", padding="5")
        self.lf_peers.grid(row=1, column=0, sticky="nsew")
        self.lf_peers.rowconfigure(0, weight=1)
        self.lf_peers.columnconfigure(0, weight=1)

        self.tree_peers = create_scrollable_treeview(self.lf_peers, peer_list_cols, (0, 0))
        self.tree_peers.bind("<<TreeviewSelect>>", self._on_peer_select)

        # 2. RIGHT panel (peer details, hidden initially)
        self.lf_details = ttk.LabelFrame(self, text="Peer Info")
        self.lf_details.grid(row=0, column=1, sticky="nsew")

        self.lf_details.rowconfigure(0, weight=1)
        self.lf_details.columnconfigure(0, weight=1)

        frame_details, cnv_details = create_scrollable_frame(self.lf_details, xscroll=False)

        frame_details_content = ttk.Frame(frame_details, padding="5")
        frame_details_content.pack(expand=True, fill="both") 

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
            label_title = tk.Label(frame_details_content, text=f"{field_name}:")
            label_title.grid(row=i, column=0, sticky="w", padx=5, pady=2)

            label_value = tk.Label(frame_details_content, text="N/A", anchor="w")
            label_value.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.labels_peer_details[field_name] = label_value

        frame_details_content.columnconfigure(1, weight=1)

        btn_close_details = ttk.Button(frame_details, text="Close", command=self._hide_peer_details)
        btn_close_details.pack(side="bottom", pady=10, anchor="w", padx=10)
        
        btn_save_peer = ttk.Button(frame_details, text="Save", command=self._add_peer)
        btn_save_peer.pack(side="bottom", pady=10, anchor="w", padx=10)
        bind_hierarchical("<MouseWheel>", self.lf_details, lambda e: mousewheel_cb(e, cnv_details))
        
        # 3. Initital setup
        
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
                format_age(int(time.time() )- peer.time_created),
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
            self._show_peer_details()
        else:
            messagebox.showerror(title="Something went wrong", message="Error retrieving peer info")

    def _show_peer_details(self):
        # Only grid the area and set title
        if not self.lf_details.winfo_ismapped():
            self.lf_details.grid(row=0, column=1, sticky="nsew")

        self.lf_details.config(text=f"Peer ID: {self.selected_peer.session_id}")
        self._config_peer_details()

    def _config_peer_details(self):
        peer = self.selected_peer
        if peer is None:
            for field_name, label_widget in self.labels_peer_details.items():
                label_widget.config(fg="gray")
            return
        
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
        self.lf_details.grid_remove()
        self.selected_peer_id = None
        self.selected_peer = None

    def _add_peer(self):
        win = tk.Toplevel(self)
        win.title("Add address")
        win.geometry("300x160")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="Name:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        entry_name = ttk.Entry(win)
        entry_name.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ttk.Label(win, text=f"IP Address: {self.selected_peer.ip}").grid(row=1, column=0, padx=10, pady=5, sticky="w")

        ttk.Label(win, text=f"Network Port: {self.selected_peer.port}").grid(row=2, column=0, padx=10, pady=5, sticky="w")

        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=3, column=0, columnspan=2, pady=15, padx=10, sticky="e")

        ttk.Button(frame_btns, text="Cancel", command=win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(frame_btns, text="Save", command=lambda: self._save_peer(win, entry_name, self.selected_peer.ip, self.selected_peer.port)).pack(side="right")
        

    def _save_peer(self, win, entry_name, ip, port):
        name = entry_name.get()
        if not name:
            messagebox.showwarning("Failed to save peer", "Name cannot be empty!")
        else:
            with sqlite3.connect(APP_CONFIG.get("path", "peers")) as con:
                cur = con.cursor()
                
                cur.execute("SELECT id FROM peers WHERE ip = ? AND port = ?", (ip, port))
                if cur.fetchone():
                    messagebox.showwarning("Duplicate Entry", f"Peer with IP Address {ip}:{port} already saved.")
                    return
                
                added = int(time.time())
                cur.execute("""
                    INSERT INTO peers (name, ip, port, added)
                    VALUES (?, ?, ?, ?)
                """, (name, ip, port, added))
            
                con.commit()
                cur.execute("SELECT id FROM peers WHERE ip = ? and port = ?", (ip, port))

            win.destroy()
            messagebox.showinfo(title="Peer saved", message=f"Saved \"{name}\" to your peers.")
    
    def _update(self):
        # Time updating
        for iid in self.tree_peers.get_children():
            peer = self.node.get_peer_by_id(int(iid))
            if peer:
                self.tree_peers.set(iid, "connection_time", format_age(int(time.time() )- peer.time_created))
                
        # Peer list updating
        if self.node.check_updated_peers():
            print("UPDATE")
            self._generate_peer_list_treeview()
            if self.node.get_peer_by_id(self.selected_peer_id) is None:  # Selected peer disconnected
                self.lf_details.config(text=self.lf_details.cget('text') + " (Disconnected)")
                self.selected_peer = self.selected_peer_id = None
            
        # Peer details updating
        if self.lf_details.winfo_ismapped():
            self._config_peer_details()

        self.after(500, self._update)
