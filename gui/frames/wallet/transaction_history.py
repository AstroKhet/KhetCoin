from datetime import datetime
import tkinter as tk
from tkinter import ttk

from db.tx import get_tx_timestamp
from db.tx_history import get_tx_history
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.common.scrollable import create_scrollable_frame
from gui.fonts import MonoFont, SansFont
from gui.helper import add_hover_effect, reset_widget
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes



class TransactionHistoryFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        self.tx_history = get_tx_history()
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        
        frame_main = ttk.Frame(self)
        frame_main.columnconfigure(0, weight=1)
        frame_main.rowconfigure(0, weight=1)
        frame_main.grid(row=1, column=0, sticky="nsew")
        
        tk.Label(frame_main, text="Transaction History", font=SansFont(16, weight="bold")).grid(row=0, column=0)
        
        self.frame_history, self.cnv_history = create_scrollable_frame(frame_main, xscroll=False)
        self.frame_history.columnconfigure(0, weight=1)
        
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    
    def _generate_tx_history(self):
        reset_widget(self.frame_history)
        
        if not self.tx_history:
            tk.Label(self.frame_history, text="No transaction history.", font=SansFont(14, weight="bold"), fg="gray", anchor="center").grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
            return
        
        date_to_hash = {}
        for tx_hash in self.tx_history.keys():
             timestamp = get_tx_timestamp(tx_hash)
             if timestamp is None:
                 timestamp = 0  #should not happen
             
             date = datetime.fromtimestamp(timestamp)
             date_to_hash.setdefault(date.date(), []).append(tx_hash)
             
        for i, (date, tx_hashes) in enumerate(date_to_hash.items()):
            date_str = date.strftime("%d %b %Y")
            lf_day = tk.LabelFrame(self.frame_history, text=date_str)
            lf_day.grid(row=i, column=0, padx=5, pady=5, ipadx=5, ipady=5, sticky="ns")

            lf_day.columnconfigure(0, weight=2)
            lf_day.columnconfigure(1, weight=4)
            lf_day.columnconfigure(2, weight=4)

            row = 0
            for tx_hash in tx_hashes:
                cb_value, in_value, out_value = self.tx_history[tx_hash]
                
                if cb_value:
                    self._display_tx(lf_day, row, "COINBASE", tx_hash, cb_value)
                    row += 1
                    
                if in_value:
                    self._display_tx(lf_day, row, "INPUT", tx_hash, in_value)
                    row += 1

                if out_value:
                    self._display_tx(lf_day, row, "OUTPUT", tx_hash, out_value)
                    row += 1
                    
        bind_hierarchical("<MouseWheel>", self.frame_history, lambda e: mousewheel_cb(e, self.cnv_history))
        
    def _display_tx(self, lf_day, row, type_, tx_hash, value):
        label_tx_type = tk.Label(lf_day, text=type_, anchor="w", font=SansFont(10), width=10)
        label_tx_type.grid(row=row, column=0, sticky="ew")
        
        sign, value_color = ("-", "#bf1029") if type_ == "OUTPUT" else ("+", "#3f8f29")
        label_value = tk.Label(lf_day, text=f"{sign}{value/KTC:.8f}KTC", anchor="w", fg=value_color, font=SansFont(10), width=25)
        label_value.grid(row=row, column=1, sticky="ew")
        
        # tx Hash
        btn_tx = tk.Button(
            lf_day, 
            text=truncate_bytes(tx_hash, 4), font=MonoFont(8), bg="#f0f8ff", 
            command=lambda q=tx_hash: self.controller.switch_to_frame(
                "view_blockchain", 
                init_query=q,
                init_from="transaction_history"
            ),
            relief="flat"
        )
        btn_tx.grid(row=row, column=2, sticky="ew")

        add_hover_effect(btn_tx, "#f0f8ff", "#E0F0FF")
        
        
    def _update(self):
        if not self._is_active:
            return
        
        if self.node.check_updated_blockchain(2):
            self.tx_history = get_tx_history()
            self._generate_tx_history()
            
        self.after(500, self._update)