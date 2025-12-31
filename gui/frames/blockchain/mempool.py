import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from blockchain.transaction import Transaction
from gui.common.columns import MEMPOOL_TX_COLS
from gui.common.transaction import tx_popup
from gui.common.scrollable import create_scrollable_treeview
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import format_age, format_bytes, truncate_bytes


_frame_id = 22

class MempoolFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        # Outer weights: left (mempool) : right (metadata) = 5 : 2
        self.columnconfigure(0, weight=5, uniform="mempool")
        self.columnconfigure(1, weight=2, uniform="mempool")
        self.rowconfigure(0, weight=1)

        # 1. Left side: Mempool txs
        self.frame_mempool = tk.Frame(self)
        self.frame_mempool.grid(row=0, column=0, sticky="nsew")
        # Make the frame_mempool actually expand in both directions
        self.frame_mempool.rowconfigure(0, weight=2, uniform="txs")   # valid txs row
        self.frame_mempool.rowconfigure(1, weight=1, uniform="txs")   # orphan txs row
        self.frame_mempool.columnconfigure(0, weight=1)

        # 1.1 Valid txs List
        self.lf_valid_txs = ttk.LabelFrame(self.frame_mempool, text="Validated Transactions")
        self.lf_valid_txs.grid(row=0, column=0, sticky="nsew")
        self.lf_valid_txs.rowconfigure(0, weight=1)
        self.lf_valid_txs.columnconfigure(0, weight=1)

        self.tree_valid_txs = create_scrollable_treeview(self.lf_valid_txs, MEMPOOL_TX_COLS, (0, 0))
        self.tree_valid_txs.bind("<<TreeviewSelect>>", lambda _: self._on_tx_select("valid"))

        # 1.2 Orphan txs List
        self.lf_orphan_txs = ttk.LabelFrame(self.frame_mempool, text="Orphan Transactions")
        self.lf_orphan_txs.grid(row=1, column=0, sticky="nsew")
        self.lf_orphan_txs.rowconfigure(0, weight=1)
        self.lf_orphan_txs.columnconfigure(0, weight=1)

        self.tree_orphan_txs = create_scrollable_treeview(self.lf_orphan_txs, MEMPOOL_TX_COLS, (0, 0))
        self.tree_orphan_txs.bind("<<TreeviewSelect>>", lambda _: self._on_tx_select("orphan"))

        # 2. Right side: Mempool metadata
        self.lf_metadata = ttk.LabelFrame(self, text="Mempool Info")
        
        self.lf_metadata.grid(row=0, column=1, sticky="nsew")
        self.lf_metadata.columnconfigure(0, weight=1, uniform="metadata")
        self.lf_metadata.columnconfigure(1, weight=1, uniform="metadata")

        # 3. Initial setup
        self._selected_tx: Transaction | None = None
        self._generate_valid_txs_treeview()
        self._generate_orphan_txs_treeview()
        
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    def _generate_valid_txs_treeview(self):
        latest_txs = self.node.mempool.get_all_valid_tx()
        tree_valid_tx_iids = list(self.tree_valid_txs.get_children())

        # Update or insert rows
        for tx in latest_txs:
            tx_hash = tx.hash()
            from_ = tx.from_()
            to = tx.to()
            values = (
                truncate_bytes(tx_hash),
                from_ if isinstance(from_, str) else truncate_bytes(from_),
                to if isinstance(to, str) else truncate_bytes(to),
                f"{sum(tx_out.value for tx_out in tx.outputs) / KTC:.8f} KTC",
                f"{tx.fee() / KTC:.8f} KTC",
                format_age(time.time() - self.node.mempool.get_tx_time(tx_hash)) + " ago"
            )

            if tx_hash.hex() in tree_valid_tx_iids:
                self.tree_valid_txs.item(tx_hash.hex(), values=values)
                tree_valid_tx_iids.remove(tx_hash.hex())
            else:
                self.tree_valid_txs.insert("", "end", iid=tx_hash.hex(), values=values)

        # Remove extra old rows if new list is shorter
        for iid in tree_valid_tx_iids:
            self.tree_valid_txs.delete(iid)
            

    def _generate_orphan_txs_treeview(self):
        latest_txs = self.node.mempool.get_all_orphan_tx()
        tree_orphan_tx_iids = set(self.tree_orphan_txs.get_children())

        for tx in latest_txs:
            tx_hash = tx.hash()
            from_ = tx.from_()
            to = tx.to()
            values = (
                truncate_bytes(tx_hash),
                from_ if isinstance(from_, str) else truncate_bytes(from_),
                to if isinstance(to, str) else truncate_bytes(to),
                f"{sum(tx_out.value for tx_out in tx.outputs) / KTC:.8f} KTC",
                "N/A",
                format_age(time.time() - self.node.mempool.get_tx_time(tx_hash)) + " ago"
            )

            if tx_hash.hex() in tree_orphan_tx_iids:
                self.tree_orphan_txs.item(tx_hash.hex(), values=values)
                tree_orphan_tx_iids.remove(tx_hash.hex())
            else:
                self.tree_orphan_txs.insert("", "end", iid=tx_hash.hex(), values=values)

        # Remove items that no longer exist
        for iid in tree_orphan_tx_iids:
            self.tree_orphan_txs.delete(iid)
    
    def _generate_metadata(self):
        valid_txs = self.node.mempool.get_all_valid_tx()
        no_valid_txs = len(valid_txs)
        size_valid_txs = sum(len(tx.serialize()) for tx in valid_txs)

        orphan_txs = self.node.mempool.get_all_orphan_tx()
        no_orphan_txs = len(orphan_txs)
        size_orphan_txs = sum(len(tx.serialize()) for tx in orphan_txs)
        

        details = {
            "No. txs": no_valid_txs + no_orphan_txs,
            "Total txs Size": format_bytes(size_valid_txs + size_orphan_txs),
            "No. Valid txs": no_valid_txs,
            "Valid txs Size": format_bytes(size_valid_txs),
            "No. Orphan txs": no_orphan_txs,
            "Orphan txs Size": format_bytes(size_orphan_txs),
        }

        # Fee, Avg Fee, highest fee, highest fee incl, etc
        for r, (field, value) in enumerate(details.items()):
            label_field = tk.Label(self.lf_metadata, text=field)
            label_field.grid(row=r, column=0, sticky="w", padx=5, pady=5)

            label_value = tk.Label(self.lf_metadata, text=value)
            label_value.grid(row=r, column=1, sticky="w", padx=5, pady=5)
 
    def _on_tx_select(self, type_: str):
        if type_ == "valid":
            selection = self.tree_valid_txs.selection()
            tx_hash = bytes.fromhex(selection[0])
            tx = self.node.mempool.get_valid_tx(tx_hash)
        else:
            selection = self.tree_orphan_txs.selection()
            tx_hash = bytes.fromhex(selection[0])
            tx = self.node.mempool.get_orphan_tx(tx_hash)

        self._selected_tx = tx
        tx_popup(self, tx, type_)

    def _update(self):
        if not self._is_active:
            return
        
        # Time updating
        for iid in self.tree_valid_txs.get_children():
            tx_hash = bytes.fromhex(iid)     
            tx_time = self.node.mempool.get_tx_time(tx_hash)
            self.tree_valid_txs.set(iid, "received", format_age(time.time() - tx_time))

        for iid in self.tree_orphan_txs.get_children():
            tx_hash = bytes.fromhex(iid)    
            tx_time = self.node.mempool.get_tx_time(tx_hash)
            self.tree_orphan_txs.set(iid, "received", format_age(time.time() - tx_time))

        # Valid Transaction listening
        if self.node.mempool.check_update_valids(_frame_id):
            self._generate_valid_txs_treeview()
            self._generate_metadata()
        
        # Orphan Transaction listening
        if self.node.mempool.check_update_orphans(_frame_id):
            self._generate_orphan_txs_treeview()
            self._generate_metadata()

        self.after(500, self._update)