import tkinter as tk

from datetime import datetime, timedelta
from tkinter import ttk

from crypto.key import wif_encode
from db.utxo import get_utxo_count_to_addr, get_utxo_value_to_addr
from db.tx import get_tx_timestamp
from db.tx_history import get_tx_history
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.common.scrollable import create_scrollable_frame
from gui.fonts import MonoFont, SansFont
from gui.helper import add_hover_effect, copy_to_clipboard, reset_widget
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes


class YourWalletFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        # Left side
        frame_left = tk.Frame(self)
        frame_left.place(relx=0, rely=0, relwidth=0.5, relheight=1.0)

        label_wallet = tk.Label(frame_left, text=f"{self.node.name}'s wallet", font=SansFont(16, weight="bold"), )
        label_wallet.pack(anchor="w", padx=20, pady=(20, 15))

        label_addr = tk.Label(frame_left, text="ADDRESS", font=SansFont(10), fg="gray")
        label_addr.pack(anchor="w", padx=20, pady=(0, 5))

        frame_pk_wif = tk.Frame(frame_left)
        frame_pk_wif.pack(anchor="w", padx=20, pady=(0, 30))  # padding applied here

        label_pk_wif = tk.Label(frame_pk_wif,  text=wif_encode(self.node.pk_hash),  font=("Courier", 10))
        label_pk_wif.pack(side="left")

        btn_pk_wif_copy = ttk.Button(frame_pk_wif, text="Copy", command=lambda: copy_to_clipboard(self, wif_encode(self.node.pk_hash)))
        btn_pk_wif_copy.pack(side="left", padx=(10, 0))

        label_balance = tk.Label(frame_left, text="BALANCE", font=SansFont(10), fg="gray")
        label_balance.pack(anchor="w", padx=20, pady=(0, 5))

        self.label_amount = tk.Label(frame_left,  text=f"{get_utxo_value_to_addr(self.node.pk_hash)/KTC} KTC",  font=SansFont(20, weight="bold"))
        self.label_amount.pack(anchor="w", padx=20)

        frame_utxo = tk.Frame(frame_left)
        frame_utxo.pack(anchor="w", padx=20, pady=(0, 30)) 

        self.label_utxo = tk.Label(frame_utxo, text=f"From {get_utxo_count_to_addr(self.node.pk_hash)} UTXO(s)", font=SansFont(10))
        self.label_utxo.pack(side="left")

        btn_goto_utxo = ttk.Button(frame_utxo, text="See all", command=lambda: self.controller.switch_to_frame("UTXO"))
        btn_goto_utxo.pack(side="left", padx=(10, 0))

        # Right side
        frame_right = tk.Frame(self)
        frame_right.place(relx=0.5, rely=0, relwidth=0.5, relheight=1.0)

        lf_recent_tx = tk.LabelFrame(frame_right, text="Recent Transactions")
        lf_recent_tx.pack(fill="both", expand=True, padx=10, pady=10)
        lf_recent_tx.columnconfigure(0, weight=1)
        lf_recent_tx.rowconfigure(1, weight=1)

        # Header
        frame_recent_tx_header = ttk.Frame(lf_recent_tx)
        frame_recent_tx_header.grid(row=0, column=0, sticky="nsew")
        label_recent_tx = tk.Label(
            frame_recent_tx_header,
            text="Transactions over the past 30 days.",
            font=("Arial", 10, "italic"),
        )
        label_recent_tx.pack(side="left", padx=5, pady=5)

        btn_full_history = ttk.Button(frame_recent_tx_header, text="Full History", command=lambda: self.controller.switch_to_frame("transaction_history"))
        btn_full_history.pack(side="right", padx=5, pady=5)

        # Recent txs
        frame_recent_txs_container = tk.Frame(lf_recent_tx, bg="blue")
        frame_recent_txs_container.columnconfigure(0, weight=1)
        frame_recent_txs_container.rowconfigure(0, weight=1)
        frame_recent_txs_container.grid(row=1, column=0, sticky="nsew")
        self.frame_recent_txs, self.cnv_recent_txs = create_scrollable_frame(frame_recent_txs_container, xscroll=False)
        self.frame_recent_txs.columnconfigure(0, weight=1)

        lf_recent_tx.rowconfigure(1, weight=1)
        lf_recent_tx.columnconfigure(0, weight=1)

        self._display_recent_txs()

        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    def _display_recent_txs(self):
        reset_widget(self.frame_recent_txs)
        recent_txs = get_tx_history(up_to=30)

        if not recent_txs:
            tk.Label(self.frame_recent_txs, text="No transaction history.", font=SansFont(14, weight="bold"), fg="gray", anchor="center").grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
            return
        
        date_to_hash = {}
        for tx_hash in recent_txs.keys():
             timestamp = get_tx_timestamp(tx_hash)
             if timestamp is None:
                 timestamp = 0  #should not happen
             
             date = datetime.fromtimestamp(timestamp)
             date_to_hash.setdefault(date.date(), []).append(tx_hash)
             
        for i, (date, tx_hashes) in enumerate(date_to_hash.items()):
            date_str = date.strftime("%d %b %Y")
            lf_day = tk.LabelFrame(self.frame_recent_txs, text=date_str)
            lf_day.grid(row=i, column=0, padx=5, pady=5, ipadx=5, ipady=5, sticky="nsew")

            lf_day.columnconfigure(0, weight=2)
            lf_day.columnconfigure(1, weight=4)
            lf_day.columnconfigure(2, weight=4)

            row = 0
            for tx_hash in tx_hashes:
                cb_value, in_value, out_value = recent_txs[tx_hash]
                
                if cb_value:
                    self._display_tx(lf_day, row, "COINBASE", tx_hash, cb_value)
                    row += 1
                    
                if in_value:
                    self._display_tx(lf_day, row, "INPUT", tx_hash, in_value)
                    row += 1

                if out_value:
                    self._display_tx(lf_day, row, "OUTPUT", tx_hash, out_value)
                    row += 1

        bind_hierarchical("<MouseWheel>", self.frame_recent_txs, lambda e: mousewheel_cb(e, self.cnv_recent_txs))

    
    def _display_tx(self, lf_day, row, type_, tx_hash, value):
        label_tx_type = tk.Label(lf_day, text=type_, anchor="w", font=SansFont(10))
        label_tx_type.grid(row=row, column=0, sticky="ew")
        
        sign, value_color = ("-", "#bf1029") if type_ == "OUTPUT" else ("+", "#3f8f29")
        label_value = tk.Label(lf_day, text=f"{sign}{value/KTC:.8f}KTC", anchor="w", fg=value_color, font=SansFont(10))
        label_value.grid(row=row, column=1, sticky="ew")
        
        # tx Hash
        btn_tx = tk.Button(
            lf_day, 
            text=truncate_bytes(tx_hash), font=MonoFont(8), bg="#f0f8ff", 
            command=lambda q=tx_hash: self.controller.switch_to_frame(
                "view_blockchain", 
                init_query=q,
                init_from="your_wallet"
            ),
            relief="flat"
        )
        btn_tx.grid(row=row, column=2, sticky="ew")

        add_hover_effect(btn_tx, "#f0f8ff", "#E0F0FF")
        
    def _update(self):
        if not self._is_active:
            return
        
        if self.node.check_updated_blockchain(4):
            self.label_amount.config(text=f"{get_utxo_value_to_addr(self.node.pk_hash)/KTC} KTC")
            self.label_utxo.config(text=f"From {get_utxo_count_to_addr(self.node.pk_hash)} UTXO(s)")
            self._display_recent_txs()
        
        self.after(500, self._update)
