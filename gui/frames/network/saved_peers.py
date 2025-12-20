import ipaddress
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import sqlite3

from gui.common.scrollable import create_scrollable_treeview
from gui.helper import center_popup, copy_to_clipboard
from utils.config import APP_CONFIG
from utils.fmt import format_age, format_epoch

PEERS_SQL = APP_CONFIG.get("path", "peers")

class SavedPeersFrame(tk.Frame):
    def __init__(self, parent, controller, node):
        super().__init__(parent)

        self.controller = controller
        self.node = node
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        
        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.rowconfigure(0, weight=0)
        self.frame_main.rowconfigure(1, weight=1)
        self.frame_main.columnconfigure(0, weight=1)

        # 1. Options Menu
        self.frame_sort = tk.Frame(self.frame_main)
        self.frame_sort.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        tk.Label(self.frame_sort, text="Sort By:").pack(side="left", padx=(0, 5))
        
        self.sort_by_var = tk.StringVar(value="Name")
        self.om_sort_by = ttk.OptionMenu(self.frame_sort, self.sort_by_var, "Name", "Name", "Added", command=self._sort_addrs)
        self.om_sort_by.pack(side="left", padx=5)
        
        self.sort_order_var = tk.StringVar(value="Ascending")
        self.om_sort_order = ttk.OptionMenu(self.frame_sort, self.sort_order_var, "Ascending", "Ascending", "Descending", command=self._sort_addrs)
        self.om_sort_order.pack(side="left", padx=5)
        
        self.label_no_peers = tk.Label(self.frame_sort, text="")
        self.label_no_peers.pack(side="left", padx=(0, 5))
        
        # 2. Wallet Addresses Treeview
        peer_cols = {
            "name": ("Name", 100),
            "ip": ("IP Address", 100),
            "port": ("Network Port", 50),
            "added": ("Added", 100)
        }
        
        self.lf_peers = ttk.LabelFrame(self.frame_main, text="Saved Addresses", padding="5")
        self.lf_peers.grid(row=1, column=0, sticky="nsew")
        self.lf_peers.rowconfigure(0, weight=1)
        self.lf_peers.columnconfigure(0, weight=1)
        
        self.tree_peers = create_scrollable_treeview(self.lf_peers, peer_cols, (0, 0))
        self.tree_peers.bind("<<TreeviewSelect>>", self._on_peer_select)
        
        self.btn_add_peer = ttk.Button(self, text="Add", command=self._add_peer)
        self.btn_add_peer.grid(row=1, column=0, sticky="e")
        
        # 3. Peer Edit panel
        self.lf_peer_info = ttk.LabelFrame(self, text="Peer Info")
        self.lf_peer_info.grid(row=0, column=1, sticky="nsew")
        
        ttk.Label(self.lf_peer_info, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.label_name = ttk.Label(self.lf_peer_info)
        self.label_name.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(self.lf_peer_info, text="Edit", width=5, command=lambda: self._edit_var("name")).grid(row=0, column=2, padx=5)

        ttk.Label(self.lf_peer_info, text="IP Address:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.label_ip = ttk.Label(self.lf_peer_info)
        self.label_ip.grid(row=1, column=1, sticky="w", padx=5)
        ttk.Button(self.lf_peer_info, text="Edit", width=5, command=lambda: self._edit_var("ip")).grid(row=1, column=2, padx=5)

        ttk.Label(self.lf_peer_info, text="Network Port:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.label_port = ttk.Label(self.lf_peer_info)
        self.label_port.grid(row=2, column=1, sticky="w", padx=5)
        ttk.Button(self.lf_peer_info, text="Edit", width=5, command=lambda: self._edit_var("port")).grid(row=2, column=2, padx=5)
        
        ttk.Label(self.lf_peer_info, text="Added:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.label_added = ttk.Label(self.lf_peer_info)
        self.label_added.grid(row=3, column=1, sticky="w", padx=5)

        btn_remove = ttk.Button(self.lf_peer_info, text="Remove", command=self._delete_peer)
        btn_remove.grid(row=4, column=0, padx=5, pady=40)

        btn_close = ttk.Button(self.lf_peer_info, text="Close", command=self._hide_peer_info)
        btn_close.grid(row=5, column=2, sticky="e", padx=5, pady=5, columnspan=2)
        
        # 4. Initial Setup
        self._hide_peer_info()
        self.peers = self._load_peers()
        self._selected_peer = None
        self._selected_iid = None
        self._generate_peers_treeview()
        
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()

    def _load_peers(self):
        # Should only run once upon the first time loading this frame.
        with sqlite3.connect(PEERS_SQL) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM peers")
            rows = cur.fetchall()
            return {row[0]: 
                {
                    "name": row[1],
                    "ip": row[2],
                    "port": row[3],
                    "added": row[4]
                } 
            for row in rows}
        
    def _generate_peers_treeview(self):
        for item in self.tree_peers.get_children():
            self.tree_peers.delete(item)
            
        sort_by = self.sort_by_var.get()
        reverse = self.sort_order_var.get() == "Descending"
        if sort_by == "Name":
            sorted_addr = dict(sorted(self.peers.items(), key=lambda item: item[1]["name"], reverse=reverse))
        else:  # Maybe there can be more sorting options in the future
            sorted_addr = self.peers  
            
        for iid, info in sorted_addr.items():
            values = (
                info["name"],
                info["ip"],
                info["port"],
                format_age(int(time.time()) - info["added"]) + " ago"
            )
            
            self.tree_peers.insert("", "end", iid=iid, values=values)
            
        self.label_no_peers.config(text=f"{len(self.peers)} saved peers")
    
    def _on_peer_select(self, _):
        selection = self.tree_peers.selection()
        if not selection:
            return
        
        self._selected_iid = int(selection[0])
        self._selected_peer = self.peers[self._selected_iid]
        
        if not self.lf_peer_info.winfo_ismapped():
            self.lf_peer_info.grid(row=0, column=1, sticky="nsew")
        
        name = self._selected_peer["name"]
        ip_addr = self._selected_peer["ip"]
        port = self._selected_peer["port"]
        self.lf_peer_info.config(text=name)
        
        self.label_name.config(text=name)
        
        self.label_ip.config(text=ip_addr)
        ttk.Button(self.lf_peer_info, text="Copy", width=5, command=lambda ip=ip_addr: copy_to_clipboard(self, ip)).grid(row=1, column=3)
        
        self.label_port.config(text=port)
        
        self.label_added.config(text=format_epoch(self._selected_peer["added"]))
    
    def _hide_peer_info(self):
        self.lf_peer_info.grid_remove()
        self._selected_peer = self._selected_iid = None
    
    def _edit_var(self, field: str):
        win = tk.Toplevel(self)
        win.title(f"Edit {field} for {self._selected_peer['name']}")
        win.geometry("300x180")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text=f"New {field}:").grid(row=0, column=0, padx=10, pady=10, sticky="w")

        entry = ttk.Entry(win)
        entry.insert(0, self._selected_peer[field])
        entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        entry.focus_set()

        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=1, column=0, columnspan=2, pady=15, padx=10, sticky="e")

        ttk.Button(frame_btns, text="Cancel", command=win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(frame_btns, text="Save", command=lambda: (self._save_edit(field, entry), win.destroy())).pack(side="right")
    
    def _save_edit(self, field: str, entry: tk.Entry):
        value = entry.get().strip()
        if field == "name":
            self.label_name.config(text=value)
            self.lf_peer_info.config(text=value)
            cmd = "UPDATE peers SET name = ? WHERE id = ?"
        elif field == "ip":
            try:
                ipaddress.ip_address(value)
            except ValueError:
                messagebox.showwarning("Failed to edit IP address", f"{value} is not a valid IP address.")
                return
            self.label_ip.config(text=value)
            cmd = "UPDATE peers SET ip = ? WHERE id = ?"
        elif field == "port":
            try:
                value = int(value)
                if not 1 <= value <= 65535:
                    messagebox.showwarning("Failed to edit port", "Network port must be between 1 and 65535")
                    return
            except ValueError:
                messagebox.showwarning("Failed to edit port", "Network port must be a number!")
                return
            self.label_port.config(text=value)
            cmd = "UPDATE peers SET port = ? WHERE id = ?"
                        
        self.peers[self._selected_iid][field] = value
        with sqlite3.connect(PEERS_SQL) as con:
            cur = con.cursor()
            cur.execute(cmd, (value, self._selected_iid))
        self.tree_peers.set(self._selected_iid, field, value)
        
    def _sort_addrs(self, *_):
        self._generate_peers_treeview()

    def _add_peer(self):
        win = tk.Toplevel(self)
        win.title("Add peer")
        win.geometry("300x160")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="Name:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        entry_name = ttk.Entry(win)
        entry_name.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ttk.Label(win, text="IP Address:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        entry_ip = ttk.Entry(win)
        entry_ip.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ttk.Label(win, text="Network Port:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        entry_port = ttk.Entry(win)
        entry_port.insert(0, '8666')
        entry_port.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=3, column=0, columnspan=2, pady=15, padx=10, sticky="e")

        ttk.Button(frame_btns, text="Cancel", command=win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(frame_btns, text="Save", command=lambda: self._save_peer(win, entry_name, entry_ip, entry_port)).pack(side="right")

    def _save_peer(self, win, entry_name, entry_ip, entry_port):
        name = entry_name.get()
        ip = entry_ip.get()
        port = int(entry_port.get())
        
        if not name:
            messagebox.showwarning("Failed to save peer", "Name cannot be empty!")
        elif not ip:
            messagebox.showwarning("Failed to save peer", "IP address cannot be empty!")
        elif not port:
            messagebox.showwarning("Failed to save peer", "Network port cannot be empty!")
        else:
            try:
                port = int(port)
                if not 1 <= port <= 65535:
                    messagebox.showwarning("Failed to save peer", "Network port must be between 1 and 65535")
                    return
            except ValueError:
                messagebox.showwarning("Failed to save peer", "Network port must be a number!")
                return
            
            try: 
                ipaddress.ip_address(ip)
            except ValueError:
                messagebox.showwarning("Failed to save peer", "Invalid IP address!")
                return
            
            with sqlite3.connect(PEERS_SQL) as con:
                cur = con.cursor()
                
                cur.execute("SELECT id FROM peers WHERE ip = ? AND port = ?", (ip, port))
                if cur.fetchone():
                    messagebox.showwarning("Duplicate Entry", f"Peer with IP Address {ip}:{port} already saved.")
                    return
                
                added = int(time.time())
                cur.execute("""
                    INSERT INTO peers (name, ip, port, added, last_seen, services)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, ip, port, added, int(time.time()), 0))
            
                con.commit()
                cur.execute("SELECT id FROM peers WHERE ip = ? and port = ?", (ip, port))
                iid = int(cur.fetchone()[0])
                
            self.peers[iid] = {
                "name": name,
                "ip": ip,
                "port": port,
                "added": added
            }
            
            self._generate_peers_treeview()
            win.destroy()
            messagebox.showinfo(title="Peer saved", message=f"Saved \"{name}\" to your peers.")
            
    def _delete_peer(self):
        iid = self._selected_iid
        name = self.peers[iid]['name']
        if messagebox.askokcancel(title="Confirm deletion", message=f"Are you sure you want to remove \"{name}\" from your peers?"):
            with sqlite3.connect(PEERS_SQL) as con:
                cur = con.cursor()
                cur.execute("DELETE FROM peers WHERE id = ?", (iid,))
            self.peers.pop(iid)
            self.tree_peers.delete(iid)
            messagebox.showinfo(title="Peer removed", message=f"\"{name}\" removed from peers.")
            self._hide_peer_info()
            self.label_no_peers.config(text=f"{len(self.peers)} saved peers")

        
    def _update(self):
        if not self._is_active:
            return
        
        for iid in self.tree_peers.get_children():
            age = format_age(int(time.time()) - self.peers[int(iid)]["added"]) + " ago"
            self.tree_peers.set(iid, "added", age)
        
        self.after(500, self._update)
