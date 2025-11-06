import time
import tkinter as tk
from tkinter import ttk

from blockchain.script import Script
from blockchain.transaction import Transaction
from crypto.key import wif_encode
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.helper import copy_to_clipboard
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import format_age, format_bytes, format_epoch, truncate_bytes


class MempoolFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        # Outer weights: left (mempool) : right (metadata) = 5 : 2
        self.columnconfigure(0, weight=5, uniform="mempool")
        self.columnconfigure(1, weight=2, uniform="mempool")
        self.rowconfigure(0, weight=1)

        # 1. Left side: Mempool TXNs
        self.frame_mempool = tk.Frame(self)
        self.frame_mempool.grid(row=0, column=0, sticky="nsew")
        # Make the frame_mempool actually expand in both directions
        self.frame_mempool.rowconfigure(0, weight=2, uniform="txs")   # valid txs row
        self.frame_mempool.rowconfigure(1, weight=1, uniform="txs")   # orphan txs row
        self.frame_mempool.columnconfigure(0, weight=1)

        tx_cols = {
            "hash": ("Hash", 9),
            "from": ("From", 9),
            "to": ("To", 9),
            "amount": ("Amount", 15),
            "fees": ("Fee", 15),
            "received": ("Received", 9)
        }

        # 1.1 Valid TXNs List
        self.lf_valid_txs = ttk.LabelFrame(self.frame_mempool, text="Validated Transactions")
        # IMPORTANT: sticky so the LabelFrame fills the frame_mempool cell
        self.lf_valid_txs.grid(row=0, column=0, sticky="nsew")
        self.lf_valid_txs.rowconfigure(0, weight=1)
        self.lf_valid_txs.columnconfigure(0, weight=1)

        self.tree_valid_txs = ttk.Treeview(
            self.lf_valid_txs,
            columns=list(tx_cols.keys()),
            show="headings",
            selectmode="browse",
        )
        self.tree_valid_txs.grid(row=0, column=0, sticky="nsew")

        for col_key, (col_title, col_w_chars) in tx_cols.items():
            self.tree_valid_txs.heading(col_key, text=col_title)
            self.tree_valid_txs.column(col_key, width=col_w_chars * 8, anchor="w")

        vsb_valid_tx = ttk.Scrollbar(self.lf_valid_txs, orient="vertical", command=self.tree_valid_txs.yview)
        vsb_valid_tx.grid(row=0, column=1, sticky="ns")

        hsb_valid_tx = ttk.Scrollbar(self.lf_valid_txs, orient="horizontal", command=self.tree_valid_txs.xview)
        hsb_valid_tx.grid(row=1, column=0, sticky="ew")

        self.tree_valid_txs.configure(yscrollcommand=vsb_valid_tx.set, xscrollcommand=hsb_valid_tx.set)
        self.tree_valid_txs.bind("<<TreeviewSelect>>", self._on_valid_tx_select)

        # 1.2 Orphan TXNs List
        self.lf_orphan_txs = ttk.LabelFrame(self.frame_mempool, text="Orphan Transactions")
        self.lf_orphan_txs.grid(row=1, column=0, sticky="nsew")
        self.lf_orphan_txs.rowconfigure(0, weight=1)
        self.lf_orphan_txs.columnconfigure(0, weight=1)

        self.tree_orphan_txs = ttk.Treeview(
            self.lf_orphan_txs,
            columns=list(tx_cols.keys()),
            show="headings",
            selectmode="browse",
        )
        self.tree_orphan_txs.grid(row=0, column=0, sticky="nsew")

        for col_key, (col_title, col_w_chars) in tx_cols.items():
            self.tree_orphan_txs.heading(col_key, text=col_title)
            self.tree_orphan_txs.column(col_key, width=col_w_chars * 8, anchor="w")

        vsb_orphan_tx = ttk.Scrollbar(self.lf_orphan_txs, orient="vertical", command=self.tree_orphan_txs.yview)
        vsb_orphan_tx.grid(row=0, column=1, sticky="ns")

        hsb_orphan_tx = ttk.Scrollbar(self.lf_orphan_txs, orient="horizontal", command=self.tree_orphan_txs.xview)
        hsb_orphan_tx.grid(row=1, column=0, sticky="ew")

        self.tree_orphan_txs.configure(yscrollcommand=vsb_orphan_tx.set, xscrollcommand=hsb_orphan_tx.set)
        self.tree_orphan_txs.bind("<<TreeviewSelect>>", self._on_orphan_tx_select)

        # 2. Right side: Mempool metadata
        self.lf_metadata = ttk.LabelFrame(self, text="Mempool Info")
        
        self.lf_metadata.grid(row=0, column=1, sticky="nsew")
        self.lf_metadata.columnconfigure(0, weight=1, uniform="metadata")
        self.lf_metadata.columnconfigure(1, weight=1, uniform="metadata")

        # 3. Initial setup
        self._selected_tx: Transaction | None = None
        self._generate_valid_txs_treeview()
        self._generate_orphan_txs_treeview()
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
            "No. Txns": no_valid_txs + no_orphan_txs,
            "Total Txns Size": format_bytes(size_valid_txs + size_orphan_txs),
            "No. Valid Txns": no_valid_txs,
            "Valid Txns Size": format_bytes(size_valid_txs),
            "No. Orphan Txns": no_orphan_txs,
            "Orphan Txns Size": format_bytes(size_orphan_txs),
        }

        # Fee, Avg Fee, highest fee, highest fee incl, etc
        for r, (field, value) in enumerate(details.items()):
            label_field = tk.Label(self.lf_metadata, text=field)
            label_field.grid(row=r, column=0, sticky="w", padx=5, pady=5)

            label_value = tk.Label(self.lf_metadata, text=value)
            label_value.grid(row=r, column=1, sticky="w", padx=5, pady=5)
 
    def _on_valid_tx_select(self, _):
        selection = self.tree_valid_txs.selection()
        if not selection:
             return
        
        tx_hash = bytes.fromhex(selection[0])
        tx = self.node.mempool.get_valid_tx(tx_hash)
        if tx:
            self._selected_tx = tx
            self._on_tx_select(tx, "valid")
    
    def _on_orphan_tx_select(self, _):
        selection = self.tree_orphan_txs.selection()
        if not selection:
             return
        
        tx_hash = bytes.fromhex(selection[0])
        tx = self.node.mempool.get_orphan_tx(tx_hash)
        if tx:
            self._selected_tx = tx
            self._on_tx_select(tx, "orphan")

    def _on_tx_select(self, tx, type_):
        # Copied from gui/frames/wallet/pay.py
        """
        type_ (str) : "orphan" | "valid"
        """
        win_tx = tk.Toplevel(self)
        win_tx.title(f"{type_.capitalize()} Transaction")
        win_tx.geometry("600x500")

        win_tx.rowconfigure(0, weight=5, uniform="tx_preview")
        win_tx.rowconfigure(1, weight=2, uniform="tx_preview")
        win_tx.rowconfigure(2, weight=1, uniform="tx_preview")
        win_tx.columnconfigure(0, weight=1)

        # 0. Scrollable frame for viewing tx summary
        frame_tx_scrollable = tk.Frame(win_tx)
        frame_tx_scrollable.grid(row=0, column=0, sticky="nsew")
        frame_tx_scrollable.columnconfigure(0, weight=1)
        frame_tx_scrollable.rowconfigure(0, weight=1)

        cnv_tx_summary = tk.Canvas(frame_tx_scrollable, highlightthickness=0)
        cnv_tx_summary.grid(row=0, column=0, sticky="nsew")
        
        vsb_tx_summary = ttk.Scrollbar(frame_tx_scrollable, orient="vertical", command=cnv_tx_summary.yview)
        vsb_tx_summary.grid(row=0, column=1, sticky="ns")

        cnv_tx_summary.configure(yscrollcommand=vsb_tx_summary.set)
        
        frame_tx_details = tk.Frame(cnv_tx_summary)
        frame_tx_details.columnconfigure(0, weight=1)

        win_id_tx_details = cnv_tx_summary.create_window((0, 0), window=frame_tx_details, anchor="nw")

        cnv_tx_summary.bind(
            "<Configure>",
            lambda e: cnv_tx_summary.itemconfig(win_id_tx_details, width=e.width)
        )
        frame_tx_details.bind(
            "<Configure>",
            lambda _: cnv_tx_summary.configure(scrollregion=cnv_tx_summary.bbox("all"))
        )

        # 1. Transaction Summary
        lf_tx_summary = ttk.LabelFrame(win_tx, text="Summary")
        lf_tx_summary.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Configure equal column weight for even spacing
        lf_tx_summary.columnconfigure(0, weight=1)
        lf_tx_summary.columnconfigure(1, weight=1)

        # Left frame (inputs, outputs, size)
        frame_tx_summary_left = tk.Frame(lf_tx_summary)
        frame_tx_summary_left.columnconfigure(0, weight=1)
        frame_tx_summary_left.columnconfigure(1, weight=1)
        frame_tx_summary_left.grid(row=0, column=0, sticky="nsew", padx=10)

        if type_ == "valid":
            tk.Label(frame_tx_summary_left, text="Input value:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_tx_summary_left, text=f"{tx.input_value()/KTC:.8f} KTC").grid(row=0, column=1, sticky="e")
        elif type_ == "orphan":
            tk.Label(frame_tx_summary_left, text="Input value:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_tx_summary_left, text=f"N/A").grid(row=0, column=1, sticky="e")

        tk.Label(frame_tx_summary_left, text="Output value:").grid(row=1, column=0, sticky="w")
        tk.Label(frame_tx_summary_left, text=f"{tx.output_value(exclude_change=True)/KTC:.8f} KTC").grid(row=1, column=1, sticky="e")  
            
        if type_ == "valid":
            tk.Label(frame_tx_summary_left, text="Change value:").grid(row=2, column=0, sticky="w")
            tk.Label(frame_tx_summary_left, text=f"{tx.change_value()/KTC:.8f} KTC").grid(row=2, column=1, sticky="e")
            
        elif type_ == "orphan":
            tk.Label(frame_tx_summary_left, text="Change value:").grid(row=2, column=0, sticky="w")
            tk.Label(frame_tx_summary_left, text=f"N/A").grid(row=2, column=1, sticky="e")

        tx_size = len(tx.serialize())
        tk.Label(frame_tx_summary_left, text="Transaction size:").grid(row=3, column=0, sticky="w")
        tk.Label(frame_tx_summary_left, text=format_bytes(tx_size)).grid(row=3, column=1, sticky="e")
            
        # Right frame (fees)
        frame_tx_summary_right = tk.Frame(lf_tx_summary)
        frame_tx_summary_right.columnconfigure(0, weight=1)
        frame_tx_summary_right.columnconfigure(1, weight=1)
        frame_tx_summary_right.grid(row=0, column=1, sticky="nsew", padx=10)

        total_fee = tx.fee()
        if total_fee is not None:
            tk.Label(frame_tx_summary_right, text="Total fee:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_tx_summary_right, text=f"{total_fee / KTC:.8f} KTC").grid(row=0, column=1, sticky="e")

            fee_rate = total_fee / tx_size if tx_size > 0 else 0
            tk.Label(frame_tx_summary_right, text="Fee rate:").grid(row=1, column=0, sticky="w")
            tk.Label(frame_tx_summary_right, text=f"{fee_rate:.2f} khets/B").grid(row=1, column=1, sticky="e")
        else:
            tk.Label(frame_tx_summary_right, text="Total fee:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_tx_summary_right, text=f"N/A").grid(row=0, column=1, sticky="e")

            tk.Label(frame_tx_summary_right, text="Fee rate:").grid(row=1, column=0, sticky="w")
            tk.Label(frame_tx_summary_right, text=f"N/A").grid(row=1, column=1, sticky="e")   
    
        # 2. Content for tx summary window
        if tx is None:
            label_err = tk.Label(frame_tx_scrollable, text="Error creating transaction. See console log.")
            label_err.grid(row=0, column=0)
            return
        
        # Copied from /gui/frames/blockchain/view_blockchain.py
        frame_tx_io = tk.Frame(frame_tx_details)
        frame_tx_io.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_tx_io.columnconfigure(0, weight=1, uniform="txio_cols")
        frame_tx_io.columnconfigure(1, weight=1, uniform="txio_cols")

        # Headers
        tk.Label(frame_tx_io, text="From", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=0, sticky="w")
        tk.Label(frame_tx_io, text="To", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=1, sticky="w")

        for i, tx_in in enumerate(tx.inputs, start=1):
            script_sig = tx_in.script_sig
            script_pk = tx_in.script_pubkey()
            if tx.is_coinbase():
                addr = "Coinbase"
            else:
                addr = script_sig.get_script_sig_sender() or "N/A"
            value = f"{tx_in.value()/KTC:.8f}KTC" if tx_in.value() is not None else "N/A"

            frame_input = tk.Frame(frame_tx_io)
            frame_input.grid(row=i, column=0, sticky="we", padx=2, pady=2)
            frame_input.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_input, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_input, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(self, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_input, text="Script", width=6,
                    command=lambda sig=script_sig, pk=script_pk: self._show_script_window(sig, pk)
            ).grid(row=0, column=2)

            tk.Label(frame_input, text=value, fg="gray").grid(row=1, column=0, sticky="w")

        # Outputs
        for i, tx_out in enumerate(tx.outputs, start=1):
            script_pk = tx_out.script_pubkey
            value = tx_out.value
            addr = script_pk.get_script_pubkey_receiver() or "N/A"

            frame_output = tk.Frame(frame_tx_io)
            frame_output.grid(row=i, column=1, sticky="we", padx=2, pady=2)
            frame_output.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_output, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_output, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(self, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_output, text="Script", width=6,
                    command=lambda pk=script_pk: self._show_script_window(script_pubkey=pk)
            ).grid(row=0, column=2)

            tk.Label(frame_output, text=f"{value/KTC:.8f}KTC", fg="gray").grid(row=1, column=0, sticky="w")
        
        bind_hierarchical("<MouseWheel>", frame_tx_scrollable, lambda e: mousewheel_cb(e, cnv_tx_summary))
    
    def _show_script_window(self, script_sig: Script | None=None, script_pubkey: Script | None=None):
        # Copied from /gui/frames/blockchain/view_blockchain.py
        win_script = tk.Toplevel(self)
        win_script.title(f"Script for Transaction {truncate_bytes(self._selected_tx.hash())}") # type: ignore
        win_script.geometry("300x200")
        win_script.transient(self)
        
        frame_script = tk.Frame(win_script, padx=10, pady=10)
        frame_script.pack(fill="both", expand=True)

        if script_sig is not None:
            label_sig = tk.Label(frame_script, text="ScriptSig", font=("Arial", 10, "bold"), anchor="w")
            label_sig.pack(fill="x", pady=(0, 2))

            txt_sig = tk.Text(frame_script, wrap="word", height=6)
            txt_sig.insert("1.0", str(script_sig))
            txt_sig.config(state="disabled")
            txt_sig.pack(fill="both", expand=True, pady=(0, 10))

        if script_pubkey is not None:
            label_pk = tk.Label(frame_script, text="ScriptPubkey", font=("TkDefaultFont", 10, "bold"), anchor="w")
            label_pk.pack(fill="x", pady=(0, 2))

            txt_pk = tk.Text(frame_script, wrap="word", height=6)
            txt_pk.insert("1.0", str(script_pubkey))
            txt_pk.config(state="disabled")
            txt_pk.pack(fill="both", expand=True)
            
    def _update(self):
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
        if self.node.mempool.check_update_valids():
            self._generate_valid_txs_treeview()
            self._generate_metadata()
        
        # Orphan Transaction listening
        if self.node.mempool.check_update_orphans():
            self._generate_orphan_txs_treeview()
            self._generate_metadata()

        self.after(500, self._update)