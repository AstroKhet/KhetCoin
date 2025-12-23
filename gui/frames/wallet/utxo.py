import tkinter as tk
from tkinter import ttk

from datetime import datetime

from db.utxo import get_utxo_exists, get_utxo_set_to_addr, get_utxo_value_to_addr
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.common.scrollable import create_scrollable_frame
from gui.common.transaction import tx_popup
from gui.fonts import MonoFont, SansFont
from gui.helper import add_hover_effect, reset_widget
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes
from utils.helper import int_to_bytes


_frame_id = 32


class UTXOFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        # Default is sort by value desc
        self.utxos_spent = self.node.mempool.spent_mempool_utxos
        self.utxos_to_node = (get_utxo_set_to_addr(self.node.pk_hash) - self.utxos_spent) | self.node.mempool.new_mempool_utxos_to_node

        self.balance = sum(utxo.value for utxo in self.utxos_to_node)

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
        self.om_sort_by = ttk.OptionMenu(self.frame_sort, self.sort_by_var, "Value", "Value", "Time", command=self._generate_utxo_set_cards)
        self.om_sort_by.pack(side="left", padx=5)

        self.sort_order_var = tk.StringVar(value="Ascending")
        self.om_sort_order = ttk.OptionMenu(self.frame_sort, self.sort_order_var, "Ascending", "Ascending", "Descending", command=self._generate_utxo_set_cards)
        self.om_sort_order.pack(side="left", padx=5)

        self.frame_utxo_container = tk.Frame(self)
        self.frame_utxo_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.frame_utxo_container.columnconfigure(0, weight=1)
        self.frame_utxo_container.rowconfigure(0, weight=1)
        
        self.frame_utxo_grid, self.cnv_utxo_grid = create_scrollable_frame(self.frame_utxo_container, xscroll=False)
        
        self.frame_utxo_grid.columnconfigure(0, weight=1, uniform="utxo_card")
        self.frame_utxo_grid.columnconfigure(1, weight=1, uniform="utxo_card")
        self.frame_utxo_grid.columnconfigure(2, weight=1, uniform="utxo_card")

        # self._generate_utxo_set_cards()
        
        self._is_active = True
    
    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self._update()
        
    def _generate_utxo_set_cards(self, *_):
        reset_widget(self.frame_utxo_grid)
        var = self.sort_by_var.get()
        order = self.sort_order_var.get()
        
        reverse = (order == "Descending")
        
        # This filtering ensures that spent utxos (grayed out) are on those that exists in the actual UTXO set
        unavail_utxo_set_to_node = {
            utxo for utxo in self.utxos_spent
            if get_utxo_exists(utxo.tx_hash + int_to_bytes(utxo.index)) and utxo.owner == self.node.pk_hash
        }

        if var == "Time":
            avail_utxo_set_to_node = sorted(self.utxos_to_node, key=lambda utxo: utxo.timestamp, reverse=reverse)
            unavail_utxo_set_to_node = sorted(unavail_utxo_set_to_node, key=lambda utxo: utxo.timestamp, reverse=reverse)
        else:
            avail_utxo_set_to_node = sorted(self.utxos_to_node, key=lambda utxo: utxo.value, reverse=reverse)
            unavail_utxo_set_to_node = sorted(unavail_utxo_set_to_node, key=lambda utxo: utxo.value, reverse=reverse)
            
        n = 0
        for utxo in avail_utxo_set_to_node:
            row, col = divmod(n, 3)
            self._add_utxo_card(row, col, utxo, True)
            n += 1
            
        for utxo in unavail_utxo_set_to_node:
            row, col = divmod(n, 3)
            self._add_utxo_card(row, col, utxo, False)
            n += 1
            
        bind_hierarchical("<MouseWheel>", self.frame_utxo_grid, lambda e: mousewheel_cb(e, self.cnv_utxo_grid))
        
    def _add_utxo_card(self, row, col, utxo, available=True):
        # Choose colors based on availability
        bg_color = "white" if available else "#d9d9d9"  # light gray
        fg_color = "black" if available else "gray"

        frame_utxo_cell = tk.Frame(self.frame_utxo_grid, bg=bg_color, borderwidth=1, relief="solid")
        frame_utxo_cell.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        frame_value_line = tk.Frame(frame_utxo_cell, bg=bg_color)
        frame_value_line.pack(anchor="w", fill="x", padx=10, pady=(10, 2))

        label_utxo_value = tk.Label(
            frame_value_line,
            text=f"{utxo.value/KTC:.8f} KTC",
            font=SansFont(14, weight="bold"),
            bg=bg_color,
            fg=fg_color
        )
        label_utxo_value.pack(side="left")

        label_utxo_currency = tk.Label(frame_value_line, text="KTC", font=SansFont(8), fg="gray", bg=bg_color)
        label_utxo_currency.pack(side="left", padx=(5, 0), anchor="s", pady=(0, 2))

        frame_info_line = tk.Frame(frame_utxo_cell, bg=bg_color)
        frame_info_line.pack(anchor="w", fill="x", padx=10, pady=2)

        label_utxo_from = tk.Label(frame_info_line, text="FROM", font=SansFont(8), fg="gray", bg=bg_color)
        label_utxo_from.pack(side="left")

        btn_bg = "#f0f8ff" if available else "#b8b8d0"
        if utxo in self.node.mempool.new_mempool_utxos_to_node:
            btn_cmd = lambda: self.controller.switch_to_frame("mempool")
        else:
            btn_cmd = lambda q=utxo.tx_hash: self.controller.switch_to_frame(
                "view_blockchain",
                init_query=q,
                init_from="UTXO"
            )
        btn_utxo_from = tk.Button(
            frame_info_line, 
            text=truncate_bytes(utxo.tx_hash), font=MonoFont(), bg=btn_bg,
            command=btn_cmd,
            relief="flat"
        )
        btn_utxo_from.pack(side="left", padx=10)
        if available:
            add_hover_effect(btn_utxo_from, btn_bg, "#e0f0ff")
        else:
            add_hover_effect(btn_utxo_from, btn_bg, "#b0cfcf")

        label_utxo_id_text = tk.Label(frame_info_line, text=f"ID {utxo.index}", font=SansFont(8), fg="gray", bg=bg_color)
        label_utxo_id_text.pack(side="left")
        
        if utxo.timestamp:
            age = datetime.fromtimestamp(utxo.timestamp).strftime("%d %b %Y, %H:%M:%S")
        else:
            age = "Mempool"
        label_utxo_age = tk.Label(frame_utxo_cell, text=age, bg=bg_color, fg=fg_color)
        label_utxo_age.pack(anchor="w", padx=10, pady=(2, 10))
            
        
    def _update(self):
        if not self._is_active:
            return
        
        if self.node.mempool.check_update_mempool(_frame_id):
            self.utxos_spent = self.node.mempool.spent_mempool_utxos
            self.utxos_to_node = (get_utxo_set_to_addr(self.node.pk_hash) - self.utxos_spent) | self.node.mempool.new_mempool_utxos_to_node

            self.balance = sum(utxo.value for utxo in self.utxos_to_node)
            self.label_balance_value.config(text=f"{self.balance/KTC:.8f}KTC")
            self._generate_utxo_set_cards()
            
        
        self.after(500, self._update)