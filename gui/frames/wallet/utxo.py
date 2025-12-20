import tkinter as tk
from tkinter import ttk

from datetime import datetime

from db.utxo import get_utxo_set_to_addr, get_utxo_value_to_addr
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.common.scrollable import create_scrollable_frame
from gui.fonts import MonoFont, SansFont
from gui.helper import add_hover_effect, reset_widget
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes


class UTXOFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        # Default is sort by value desc
        self.utxo_set = get_utxo_set_to_addr(self.node.pk_hash)
        self.utxo_set.sort(key=lambda utxo: utxo.value, reverse=True)
        self.balance = get_utxo_value_to_addr(self.node.pk_hash)

        self.frame_balance_container = tk.Frame(self)
        self.frame_balance_container.pack(fill="x", pady=(10, 5))
        
        self.label_balance_title = tk.Label(self.frame_balance_container, text="BALANCE", font=SansFont(9), fg="gray")
        self.label_balance_title.pack()
        
        self.label_balance_value = tk.Label(self.frame_balance_container, text=f"{self.balance/KTC:.8f} KTC", font=SansFont(16, weight="bold"))
        self.label_balance_value.pack()

        self.frame_sort = tk.Frame(self)
        self.frame_sort.pack(fill="x", padx=10, pady=5)
        
        tk.Label(self.frame_sort, text="Sort By:").pack(side="left", padx=(0, 5))

        self.sort_by_var = tk.StringVar(value="Value")
        self.om_sort_by = ttk.OptionMenu(self.frame_sort, self.sort_by_var, "Value", "Value", "Time", command=self._sort_utxo)
        self.om_sort_by.pack(side="left", padx=5)

        self.sort_order_var = tk.StringVar(value="Ascending")
        self.om_sort_order = ttk.OptionMenu(self.frame_sort, self.sort_order_var, "Ascending", "Ascending", "Descending", command=self._sort_utxo)
        self.om_sort_order.pack(side="left", padx=5)
        
        self.label_no_utxo = ttk.Label(self.frame_sort, text=f"({len(self.utxo_set)} UTXOs)")
        self.label_no_utxo.pack(side="left", padx=5)

        self.frame_utxo_container = tk.Frame(self)
        self.frame_utxo_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.frame_utxo_container.columnconfigure(0, weight=1)
        self.frame_utxo_container.rowconfigure(0, weight=1)
        
        self.frame_utxo_grid, self.cnv_utxo_grid = create_scrollable_frame(self.frame_utxo_container, xscroll=False)
        
        self.frame_utxo_grid.columnconfigure(0, weight=1, uniform="utxo_card")
        self.frame_utxo_grid.columnconfigure(1, weight=1, uniform="utxo_card")
        self.frame_utxo_grid.columnconfigure(2, weight=1, uniform="utxo_card")

        self._generate_utxo_set_cards()
        
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    def _generate_utxo_set_cards(self):
        reset_widget(self.frame_utxo_grid)
        
        for i, utxo in enumerate(self.utxo_set):
            row, col = divmod(i, 3)
            
            frame_utxo_cell = tk.Frame(self.frame_utxo_grid, bg="white", borderwidth=1, relief="solid")
            frame_utxo_cell.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            frame_value_line = tk.Frame(frame_utxo_cell, bg="white")
            frame_value_line.pack(anchor="w", fill="x", padx=10, pady=(10, 2))

            label_utxo_value = tk.Label(frame_value_line, text=f"{utxo.value/KTC:.8f} KTC", font=SansFont(14, weight="bold"), bg="white")
            label_utxo_value.pack(side="left")

            label_utxo_currency = tk.Label(frame_value_line, text="KTC", font=SansFont(8), fg="gray", bg="white")
            label_utxo_currency.pack(side="left", padx=(5, 0), anchor="s", pady=(0, 2))

            frame_info_line = tk.Frame(frame_utxo_cell, bg="white")
            frame_info_line.pack(anchor="w", fill="x", padx=10, pady=2)

            label_utxo_from = tk.Label(frame_info_line, text="FROM", font=SansFont(8), fg="gray", bg="white")
            label_utxo_from.pack(side="left")

            
            btn_utxo_from = tk.Button(
                frame_info_line, 
                text=truncate_bytes(utxo.tx_hash), font=MonoFont(), bg="#f0f8ff",
                command=lambda q=utxo.tx_hash: self.controller.switch_to_frame(
                    "view_blockchain",
                    init_query=q,
                    init_from="UTXO"
                ),
                relief="flat"
            )
            btn_utxo_from.pack(side="left", padx=10)
            add_hover_effect(btn_utxo_from, "#f0f8ff", "#E0F0FF")

            label_utxo_id_text = tk.Label(frame_info_line, text=f"ID {utxo.index}", font=SansFont(8), fg="gray", bg="white")
            label_utxo_id_text.pack(side="left")
            
            label_utxo_age = tk.Label(frame_utxo_cell, text=datetime.fromtimestamp(utxo.timestamp).strftime("%d %b %Y, %H:%M:%S"), bg="white")
            label_utxo_age.pack(anchor="w", padx=10, pady=(2, 10))
        
        bind_hierarchical("<MouseWheel>", self.frame_utxo_grid, lambda e: mousewheel_cb(e, self.cnv_utxo_grid))
        
    def _sort_utxo(self, *_):
        var = self.sort_by_var.get()
        order = self.sort_order_var.get()
        if order == "Descending":
            reverse = True
        else:
            reverse = False
            
        if var == "Value":
            self.utxo_set.sort(key=lambda utxo: utxo.value, reverse=reverse)
        elif var == "Time":
            self.utxo_set.sort(key=lambda utxo: utxo.timestamp, reverse=reverse)
            
        self._generate_utxo_set_cards()
        
    def _update(self):
        if not self._is_active:
            return
        
        if self.node.check_updated_blockchain(3):
            self.utxo_set = get_utxo_set_to_addr(self.node.pk_hash)
            self.label_no_utxo.config(text=f"({len(self.utxo_set)} UTXOs)")
            self._generate_utxo_set_cards()
        
        self.after(500, self._update)