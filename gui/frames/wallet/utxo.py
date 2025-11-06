import tkinter as tk
from tkinter import ttk

from datetime import datetime

from blockchain.transaction import get_utxo_addr_value
from db.utxo import get_utxo_set
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes


class UTXOFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        # Default is sort by value desc
        self.utxo_set = get_utxo_set(self.node.pk_hash)
        self.utxo_set.sort(key=lambda utxo: utxo.value, reverse=True)
        self.balance = get_utxo_addr_value(self.node.pk_hash)

        self.frame_balance_container = tk.Frame(self)
        self.frame_balance_container.pack(fill="x", pady=(10, 5))
        
        self.label_balance_title = tk.Label(self.frame_balance_container, text="BALANCE", font=("Segoe UI", 9), fg="gray")
        self.label_balance_title.pack()
        
        self.label_balance_value = tk.Label(self.frame_balance_container, text=f"{self.balance/KTC:.8f} KTC", font=("Segoe UI", 16, "bold"))
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

        self.frame_utxos = tk.Frame(self)
        self.frame_utxos.pack(fill="both", expand=True, padx=5, pady=5)

        self.cnv_utxos = tk.Canvas(self.frame_utxos, highlightthickness=0)
        self.vsb_utxos = ttk.Scrollbar(self.frame_utxos, orient="vertical", command=self.cnv_utxos.yview)
        self.frame_utxo_grid = tk.Frame(self.cnv_utxos)

        self.cnv_utxos.configure(yscrollcommand=self.vsb_utxos.set)
        
        self.vsb_utxos.pack(side="right", fill="y")
        self.cnv_utxos.pack(side="left", fill="both", expand=True)
        self.cnv_utxo_window = self.cnv_utxos.create_window((0, 0), window=self.frame_utxo_grid, anchor="nw")

        self.frame_utxo_grid.bind(
            "<Configure>", lambda _: self.cnv_utxos.configure(scrollregion=self.cnv_utxos.bbox("all"))
        )
        self.cnv_utxos.bind(
            "<Configure>", 
            lambda e: self.cnv_utxos.itemconfig(self.cnv_utxo_window, width=e.width)
        )
        
        self.frame_utxo_grid.columnconfigure(0, weight=1)
        self.frame_utxo_grid.columnconfigure(1, weight=1)
        self.frame_utxo_grid.columnconfigure(2, weight=1)

        self._generate_utxos()

    def _generate_utxos(self):
        for i, utxo in enumerate(self.utxo_set):
            row, col = divmod(i, 3)
            
            frame_utxo_cell = tk.Frame(self.frame_utxo_grid, bg="white", borderwidth=1, relief="solid")
            frame_utxo_cell.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            frame_value_line = tk.Frame(frame_utxo_cell, bg="white")
            frame_value_line.pack(anchor="w", fill="x", padx=10, pady=(10, 2))

            label_utxo_value = tk.Label(frame_value_line, text=f"{utxo.value/KTC:.8f} KTC", font=("Segoe UI", 14, "bold"), bg="white")
            label_utxo_value.pack(side="left")

            label_utxo_currency = tk.Label(frame_value_line, text="KTC", font=("Segoe UI", 8), fg="gray", bg="white")
            label_utxo_currency.pack(side="left", padx=(5, 0), anchor="s", pady=(0, 2))

            frame_info_line = tk.Frame(frame_utxo_cell, bg="white")
            frame_info_line.pack(anchor="w", fill="x", padx=10, pady=2)
            
            label_utxo_from = tk.Label(frame_info_line, text="FROM", font=("Segoe UI", 8), fg="gray", bg="white")
            label_utxo_from.pack(side="left")

            label_utxo_hash = tk.Label(frame_info_line, text=truncate_bytes(utxo.txn_hash), font=("Courier", 10), bg="white")
            label_utxo_hash.pack(side="left", padx=5)

            label_utxo_id_text = tk.Label(frame_info_line, text=f"ID {utxo.index}", font=("Segoe UI", 8), fg="gray", bg="white")
            label_utxo_id_text.pack(side="left")
            
            label_utxo_age = tk.Label(frame_utxo_cell, text=datetime.fromtimestamp(utxo.timestamp).strftime("%d %b %Y, %H:%M:%S"), bg="white")
            label_utxo_age.pack(anchor="w", padx=10, pady=(2, 10))
        
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
            
        self._generate_utxos()