import time
import tkinter as tk

from datetime import datetime
from tkinter import ttk
from math import ceil

from blockchain.block import Block, calculate_block_subsidy
from blockchain.script import Script
from blockchain.transaction import Transaction
from crypto.key import wif_encode
from db.block import get_block, get_block_at_height, get_block_hash_at_height, get_block_height_at_hash, get_block_metadata, get_block_metadata_at_height, get_blockchain_height
from db.tx import get_txn, get_txn_metadata
from gui.bindings import bind_entry_prompt, bind_hierarchical, mousewheel_cb
from gui.helper import reset_widget, attach_tooltip, copy_to_clipboard
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import format_age, format_bytes, format_epoch, format_number, truncate_bytes

# TODO: Implement sort by ascending/descending for each column in block view
# Blocks are sorted by height in descending order

class ViewBlockchainFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node, **kwargs):
        """
        **kwargs (optional):
        - init_query (bytes | str): Uused when page switching with an intended query to search
        - init_from (str):  Frame name where the initial query came from
        """

        super().__init__(parent)
        self.controller = controller
        self.node = node

        self.labels_block_details = dict()
        self.cache_block_metadata = dict()

        # 0. Main Layout
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        # Main Panel
        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.rowconfigure(0, weight=0)  # Top Search Bar
        self.frame_main.rowconfigure(1, weight=1)  # Bottom-left Blockchain View
        self.frame_main.columnconfigure(0, weight=1)

        # Search Bar
        self.lf_search = ttk.LabelFrame(self.frame_main, text="Blockhain Viewer", padding="5")
        self.lf_search.grid(row=0, column=0, sticky="new", pady=(0, 5))
        self.lf_search.columnconfigure(0, weight=1)

        self.var_search = tk.StringVar()
        self.entry_search = tk.Entry(self.lf_search, textvariable=self.var_search)
        self._entry_prompt = "Enter block hash/height or transaction hash"
        bind_entry_prompt(self.entry_search, self._entry_prompt)

        self.entry_search.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.btn_search = ttk.Button(self.lf_search, text="Search", command=self._search)
        self.btn_search.grid(row=0, column=1, padx=5, pady=5)

        # 1. Recent Blocks (block list)
        self.rows_per_page = 50
        self.lf_block_list = ttk.LabelFrame(self.frame_main, text="Blocks", padding="5")
        self.lf_block_list.grid(row=1, column=0, sticky="nsew")
        self.lf_block_list.rowconfigure(0, weight=1)
        self.lf_block_list.columnconfigure(0, weight=1)

        self.block_page = tk.StringVar(value="1")
        self.block_page.trace_add("write", self._page_select_block)
        self.no_block_rows = get_blockchain_height() + 1
        self.no_block_pages = ceil(self.no_block_rows / self.rows_per_page)   # Block 0 Genesis

        self.tree_block_list = None

        # 2. Block Details (block_details)
        self._selected_block: Block | None = None
        self.lf_block_details = ttk.LabelFrame(self.frame_main, text="Block Details", padding="5")
        self.lf_block_details.grid(row=1, column=0, sticky="nsew")
        self.lf_block_details.rowconfigure(0, weight=1)
        self.lf_block_details.columnconfigure(0, weight=1)
        self.lf_block_details.columnconfigure(1, weight=0)

        self.txn_page = tk.StringVar(value="1")
        self.txn_page.trace_add("write", self._page_select_txn)

        self.tree_txn_list = None

        # 3. Txn Details
        self._selected_tx: Transaction | None = None
        self.lf_tx_details = ttk.LabelFrame(self.frame_main, text="Transaction Details", padding="5")
        self.lf_tx_details.grid(row=1, column=0, sticky="nsew")
        self.lf_tx_details.rowconfigure(0, weight=1)
        self.lf_tx_details.columnconfigure(0, weight=1)
        self.lf_tx_details.columnconfigure(1, weight=0)
        
        # 4. Not Found
        self.lf_notfound = ttk.Labelframe(self.frame_main, text="Not Found!")
        self.lf_notfound.grid(row=1, column=0, sticky="nsew")
        self.lf_notfound.rowconfigure(0, weight=1)
        self.lf_notfound.columnconfigure(0, weight=1)

        # 5. Periodic update helper vars
        # Current page: block_list | block_details | tx_details
        self._current_page = "block_list"

        # Age field: (label, created)
        self._block_age_field = None
        self._tx_age_field = None

        # 6. Page initialization
        self._init_from = kwargs.get("init_from", None)
        if init_query := kwargs.get("init_query", None):
            self._search(init_query)
        else:
            self._switch_to_block_list()

        self._update()

    def _switch_to_block_list(self):
        self._current_page = "block_list"
        self._generate_block_list()
        self._page_select_block()
        self.lf_block_list.tkraise()

    def _switch_to_block_details(self, spec_block: Block | None = None):
        # Shows the details of self.selected_block or a specified block
        self._current_page = "block_details"
        block = spec_block if spec_block is not None else self._selected_block
        if block is not None:
            self._generate_block_details(block)
            self.lf_block_details.tkraise()
        else:
            self._switch_to_notfound("No Block Selected!")

    def _switch_to_tx_details(self, spec_tx: Transaction | None = None):
        self._current_page = "tx_details"
        tx = spec_tx if spec_tx is not None else self._selected_tx

        if tx is not None:
            self._generate_txn_details(tx)
            self.lf_tx_details.tkraise()
        else:
            self._switch_to_notfound("No Transaction Selected!")

    def _switch_to_notfound(self, msg):
        self._current_page = "notfound"
        self._generate_notfound(msg)
        self.lf_notfound.tkraise()

    def _search(self, query=None):
        if query is None:
            query = self.var_search.get()

        if query == self._entry_prompt:  # Searching nothing brings you to default view page
            self.block_page.set("1")
            self._switch_to_block_list()
            return

        def hash_search(hash_):
            if block := get_block(hash_, full=True):
                self._switch_to_block_details(
                    Block.parse_static(block, full_block=True)
                )
                return True
            elif txn := get_txn(hash_):
                self._switch_to_tx_details(Transaction.parse_static(txn))
                return True
            return False

        def height_search(height):
            if block := get_block_at_height(height, full=True):
                self._switch_to_block_details(
                    Block.parse_static(block, full_block=True)
                )
                return True
            return False

        search_success = False
        if isinstance(query, bytes):
            search_success = hash_search(query)

        elif isinstance(query, int):
            search_success = height_search(query)

        elif isinstance(query, str):
            if len(query) == 64:
                try:
                    hash_ = bytes.fromhex(query)
                    search_success = hash_search(hash_)
                except ValueError:
                    pass
            else:
                try:
                    height = int(query)
                    search_success = height_search(height)
                except ValueError:
                    pass

        if not search_success:
            self._switch_to_notfound(
                f'Your search "{str(query)}" did not yield any results :('
            )

    def _page_select_block(self, *_):
        page = int(self.block_page.get())
        start_row = self.rows_per_page * (page - 1)
        end_row = min(self.rows_per_page * page, self.no_block_rows)

        # Refresh the block list first
        if self.tree_block_list:
            self.tree_block_list.delete(*self.tree_block_list.get_children())
        
        for depth in range(start_row, end_row):
            height = self.no_block_rows - depth - 1
            meta = get_block_metadata_at_height(height)
            if not meta:
                continue

            block_hash = meta.block_hash.hex()
            values = (
                height,
                truncate_bytes(block_hash),
                format_age(time.time() - meta.timestamp),
                meta.no_txns,
                format_bytes(meta.full_block_size),
                f"{meta.total_sent/KTC:.2f} KTC",
                f"{meta.fee/KTC:.2f} KTC",
                format_epoch(meta.timestamp)
            )

            self.tree_block_list.insert("", "end", iid=height, values=values)

    def _page_select_txn(self, *_):
        page = int(self.txn_page.get())
        start_row = self.rows_per_page * (page - 1)
        end_row = min(self.rows_per_page * page, self.no_txn_rows)

        if not self._selected_block:
            return

        transactions = self._selected_block.transactions
        for txiid in range(start_row, end_row):
            txn = transactions[txiid]

            from_ = txn.from_()
            to = txn.to()
            values = (
                txiid, 
                truncate_bytes(txn.hash()),
                from_ if isinstance(from_, str) else truncate_bytes(from_, ends=4),
                to if isinstance(to, str) else truncate_bytes(to, ends=4),
                f"{sum(tx_out.value for tx_out in txn.outputs)/KTC} KTC",
                f"{txn.fee()/KTC} KTC"
            )

            self.tree_txn_list.insert("", "end", iid=txiid, values=values)

    def _on_block_select(self, _):
        selection = self.tree_block_list.selection()
        if not selection:
            return

        height = int(selection[0])
        block_raw = get_block_at_height(height, full=True)
        if not block_raw:
            return

        self._selected_block = Block.parse_static(block_raw, full_block=True)
        self._switch_to_block_details()
        return

    def _on_txn_select(self, parent_block: Block | None):
        selection = self.tree_txn_list.selection()
        if not selection or parent_block is None:
            return
        print(selection)
        txn_pos = int(selection[0])
        self._selected_tx = parent_block.transactions[txn_pos]
        self._switch_to_tx_details()

    def _generate_block_list(self):
        reset_widget(self.lf_block_list)
        block_list_cols = {
            "height": ("Height", 12),
            "hash": ("Block Hash", 20),
            "age": ("Age", 40),
            "no_txns": ("No. Txns", 12),
            "size": ("Size", 12),
            "sent": ("Total Sent", 12),
            "fees": ("Total Fees", 12)
        }

        self.tree_block_list = ttk.Treeview(
            self.lf_block_list,
            columns=list(block_list_cols.keys()),
            show="headings",
            selectmode="browse",
        )

        for col_id, (text, width) in block_list_cols.items():
            self.tree_block_list.heading(col_id, text=text)
            self.tree_block_list.column(col_id, width=width, minwidth=50, stretch=tk.YES)

        vsb_block_list = ttk.Scrollbar(self.lf_block_list, orient="vertical", command=self.tree_block_list.yview)
        hsb_block_list = ttk.Scrollbar(self.lf_block_list, orient="horizontal", command=self.tree_block_list.xview)
        self.tree_block_list.configure(yscrollcommand=vsb_block_list.set, xscrollcommand=hsb_block_list.set)

        self.tree_block_list.grid(row=0, column=0, sticky="nsew")
        vsb_block_list.grid(row=0, column=1, sticky="ns")
        hsb_block_list.grid(row=1, column=0, sticky="ew")

        self.tree_block_list.bind("<<TreeviewSelect>>", self._on_block_select)

        frame_block_list_footer = tk.Frame(self.lf_block_list)
        frame_block_list_footer.grid(row=1, column=0, pady=5)

        spinbox_block = tk.Spinbox(
            frame_block_list_footer, 
            from_=1, 
            to=self.no_block_pages, 
            increment=1, 
            width=5,
            textvariable=self.block_page
        )
        spinbox_block.pack(side="left", padx=5, pady=5)

        label_max_block_page = tk.Label(frame_block_list_footer, text=f"of {self.no_block_pages}")
        label_max_block_page.pack(side="left", padx=2, pady=5)

        frame_nav = tk.Frame(self.lf_block_list)
        frame_nav.grid(row=1, column=0, columnspan=2, sticky="e")

        btn_refresh = ttk.Button(frame_nav, text="Refresh", command=self._switch_to_block_list)
        btn_refresh.pack(side="right", padx=5, pady=5)

    def _generate_block_details(self, block: Block):
        reset_widget(self.lf_block_details)

        block_hash = block.hash()
        self.lf_block_details.config(text=f"Block Details for <{block_hash.hex()}>")
        # Scroll region
        cnv_block_details = tk.Canvas(self.lf_block_details, highlightthickness=0)
        cnv_block_details.grid(row=0, column=0, sticky="nsew")

        vsb_block_details = ttk.Scrollbar(self.lf_block_details, orient="vertical", command=cnv_block_details.yview)
        vsb_block_details.grid(row=0, column=1, sticky="ns")
        cnv_block_details.configure(yscrollcommand=vsb_block_details.set)

        frame_block_details = tk.Frame(cnv_block_details)
        frame_block_details.columnconfigure(0, weight=1)
        win_id_block_details = cnv_block_details.create_window((0, 0), window=frame_block_details, anchor="nw")
        cnv_block_details.bind(
            "<Configure>",
            lambda e: cnv_block_details.itemconfig(win_id_block_details, width=e.width),
        )
        frame_block_details.bind(
            "<Configure>",
            lambda _: cnv_block_details.configure(scrollregion=cnv_block_details.bbox("all")),
        )

        # 1. Block metadata
        frame_block_meta = tk.Frame(frame_block_details)
        frame_block_meta.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame_block_meta.columnconfigure(0, weight=1, uniform="block_cols")
        frame_block_meta.columnconfigure(1, weight=1, uniform="block_cols")

        meta = get_block_metadata(block_hash)
        if not meta: # ur cooked idk
            return

        height = meta.height
        coinbase_tx = block.transactions[0]
        reward = sum(tx_out.value for tx_out in coinbase_tx.outputs)

        details = {
            "Height": height,
            "Age": format_age(time.time() - block.timestamp),
            "Block Hash": block_hash,
            "Size": format_bytes(meta.full_block_size),
            "Previous Block": block.prev_block,
            "Version": block.version,
            "Merkle Root": block.merkle_root,
            "Mined on": format_epoch(block.timestamp),
            "Difficulty": format_number(block.difficulty()),
            "Nonce": block.nonce,
            "No. Txns": meta.no_txns,
            "Total Sent": f"{meta.total_sent / KTC:.2f} KTC",
            "Fee": f"{meta.fee/KTC} KTC",
            "Fee/KB": f"{(meta.fee/KTC) / meta.full_block_size * 1024:.2f} KTC/KB",
            "Confirmations": get_blockchain_height() - height,
            "Minted": f"{calculate_block_subsidy(height)/KTC} KTC",
            "Block Reward": f"{reward / KTC} KTC",
        }

        frame_block_meta.columnconfigure(0, weight=1)
        frame_block_meta.columnconfigure(1, weight=1)

        for i, (key, val) in enumerate(details.items()):
            cell = ttk.Frame(frame_block_meta)
            cell.grid(row=i//2, column=i%2, sticky="ew", padx=4, pady=2)
            cell.columnconfigure(0, weight=1, uniform="col")
            cell.columnconfigure(1, weight=1, uniform="col")

            label_name = tk.Label(cell, text=f"{key}:", anchor="w")
            label_name.grid(row=0, column=0, sticky="ew", padx=5)

            # Truncated hash with 'Copy' button
            if isinstance(val, bytes) and len(val) == 32:
                full_hex = val.hex()
                truncated = truncate_bytes(full_hex, 4)

                widget_val = tk.Frame(cell)
                widget_val.columnconfigure(0, weight=5)
                widget_val.columnconfigure(1, weight=2)

                label_val = tk.Label(widget_val, text=truncated, anchor="w", bg="light blue")
                label_val.grid(row=0, column=0, sticky="w") 
                attach_tooltip(label_val, full_hex)

                btn_copy = ttk.Button(
                    widget_val, text="Copy", width=6,
                    command=lambda text=full_hex: copy_to_clipboard(self, text)
                )
                btn_copy.grid(row=0, column=1, padx=5, sticky="e")

            # Normal text label
            else:
                widget_val = tk.Label(cell, text=str(val), anchor="w")
                if key == "Age":  # For constant refreshing
                    self._block_age_field = (widget_val, block.timestamp)

            widget_val.grid(row=0, column=1, sticky="ew", padx=5)


        # 2. Transactions in block
        txn_list_cols = {
            "index": ("Index", 8),
            "hash": ("Transaction Hash", 16),
            "from": ("From", 16),
            "to": ("To", 16),
            "amount": ("Amount", 12),
            "fees": ("Fee", 12),
        }

        frame_txn_list = tk.Frame(frame_block_details)
        frame_txn_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_txn_list.rowconfigure(0, weight=1)
        frame_txn_list.columnconfigure(0, weight=1)

        # Treeview
        self.tree_txn_list = ttk.Treeview(
            frame_txn_list,
            columns=list(txn_list_cols.keys()),
            show="headings",
            selectmode="browse",
        )
        self.tree_txn_list.grid(row=0, column=0, sticky="nsew")

        vsb_tree_txn_list = ttk.Scrollbar(frame_txn_list, orient="vertical", command=self.tree_txn_list.yview)
        vsb_tree_txn_list.grid(row=0, column=1, sticky="ns")

        self.tree_txn_list.configure(yscrollcommand=vsb_tree_txn_list.set)
        self.tree_txn_list.grid(row=0, column=0, sticky="nsew")

        for col_key, (col_title, col_w_chars) in txn_list_cols.items():
            self.tree_txn_list.heading(col_key, text=col_title)
            self.tree_txn_list.column(col_key, width=col_w_chars * 8, anchor="w")

        self.tree_txn_list.bind("<<TreeviewSelect>>", lambda _: self._on_txn_select(self._selected_block))

        # Footer
        frame_txn_list_list_footer = tk.Frame(frame_txn_list)
        frame_txn_list_list_footer.grid(row=1, column=0, pady=(6, 0))

        self.no_txn_rows = len(block.transactions)
        self.no_txn_pages = ceil(self.no_txn_rows / self.rows_per_page)

        spinbox_txn = tk.Spinbox(
            frame_txn_list_list_footer,
            from_=1,
            to=max(1, self.no_txn_pages),
            increment=1,
            width=5,
            textvariable=self.txn_page,
        )
        spinbox_txn.pack(side="left", padx=5, pady=5)
        label_max_txn_pages = tk.Label(frame_txn_list_list_footer, text=f"of {self.no_txn_pages}")
        label_max_txn_pages.pack(side="left", padx=2, pady=5)

        frame_nav = tk.Frame(self.lf_block_details)
        frame_nav.grid(row=1, column=0, columnspan=2, sticky="e")

        btn_return = ttk.Button(frame_nav, text="Return", command=self._switch_to_block_list)
        btn_return.pack(side="right", padx=5, pady=5)

        btn_refresh = ttk.Button(frame_nav, text="Refresh", command=self._switch_to_block_details)
        btn_refresh.pack(side="right", padx=5, pady=5)

        bind_hierarchical("<MouseWheel>", self.lf_block_details, lambda e: mousewheel_cb(e, cnv_block_details))
        
        self._selected_block = block
        self._page_select_txn()


    def _generate_txn_details(self, tx: Transaction):
        reset_widget(self.lf_tx_details)

        tx_hash = tx.hash()
        self.lf_tx_details.config(text=f"Transaction Details for <{tx_hash.hex()}>")

        cnv_txn_details = tk.Canvas(self.lf_tx_details, highlightthickness=0)
        cnv_txn_details.grid(row=0, column=0, sticky="nsew")
        
        vsb_txn_details = ttk.Scrollbar(self.lf_block_details, orient="vertical", command=cnv_txn_details.yview)
        vsb_txn_details.grid(row=0, column=1, sticky="ns")
        cnv_txn_details.configure(yscrollcommand=vsb_txn_details.set)

        frame_tx_details = tk.Frame(cnv_txn_details)
        frame_tx_details.columnconfigure(0, weight=1)
        win_id_txn_details = cnv_txn_details.create_window((0, 0), window=frame_tx_details, anchor="nw")
        cnv_txn_details.bind(
            "<Configure>",
            lambda e: cnv_txn_details.itemconfig(win_id_txn_details, width=e.width)
        )
        frame_tx_details.bind(
            "<Configure>",
            lambda _: cnv_txn_details.configure(scrollregion=cnv_txn_details.bbox("all"))
        )
        
        # 1. Txn Metadata
        frame_tx_meta = tk.Frame(frame_tx_details)
        frame_tx_meta.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame_tx_meta.columnconfigure(0, weight=1, uniform="txn_cols")
        frame_tx_meta.columnconfigure(1, weight=1, uniform="txn_cols")
        
        tx_meta = get_txn_metadata(tx_hash)
        if tx_meta is None:
            self._switch_to_notfound(f"Transaction metadata <{tx_hash.hex()}> not found in db")
            return

        block_hash = get_block_hash_at_height(tx_meta.height) 
        if block_hash is None:
            self._switch_to_notfound(f"Block at height {tx_meta.height} not found in db")
            return

        block_meta = get_block_metadata(block_hash)
        if block_meta is None:
            self._switch_to_notfound(f"Block metadata <{block_hash}> not found in db")
            return

        fee = tx.fee()
        size = len(tx.serialize())
        details = {
            "Hash": tx_hash,
            "Block Height": tx_meta.height,
            "Position": tx_meta.pos,
            "Time": datetime.fromtimestamp(block_meta.timestamp).strftime("%d %b %Y, %H:%M:%S"),
            "Age": format_age(time.time() - block_meta.timestamp),
            "Version": tx.version,
            "Inputs": len(tx.inputs),
            "Outputs": len(tx.outputs),
            "Input Value": "N/A"if tx.is_coinbase()else f"{sum(tx_in.value() or 0 for tx_in in tx.inputs)/KTC} KTC",
            "Output Value": f"{sum(tx_out.value for tx_out in tx.outputs)/KTC} KTC",
            "Size": format_bytes(len(tx.serialize())),
            "Fee": f"{fee} khets",
            "Fee/B": f"{fee/size:.2f} khets/B",
            "Coinbase": "Yes" if tx.is_coinbase() else "No",
            "Locktime": tx.locktime,
        }

        frame_tx_meta.columnconfigure(0, weight=1)
        frame_tx_meta.columnconfigure(1, weight=1)

        for i, (key, val) in enumerate(details.items()):
            cell = ttk.Frame(frame_tx_meta)
            cell.grid(row=i//2, column=i%2, sticky="ew", padx=4, pady=2)
            cell.columnconfigure(0, weight=1, uniform="col")
            cell.columnconfigure(1, weight=1, uniform="col")

            label_name = tk.Label(cell, text=f"{key}:", anchor="w")
            label_name.grid(row=0, column=0, sticky="ew", padx=5)

            if isinstance(val, bytes) and len(val) == 32:
                full_hex = val.hex()
                truncated = truncate_bytes(full_hex, 4)

                widget_val = tk.Frame(cell)
                widget_val.columnconfigure(0, weight=5)
                widget_val.columnconfigure(1, weight=2)

                label_val = tk.Label(widget_val, text=truncated, anchor="w", bg="light blue")
                label_val.grid(row=0, column=0, sticky="w") 
                attach_tooltip(label_val, full_hex)

                btn_copy = ttk.Button(
                    widget_val, text="Copy", width=6,
                    command=lambda text=full_hex: copy_to_clipboard(self, text)
                )
                btn_copy.grid(row=0, column=1, padx=5, sticky="e")
            else:
                widget_val = tk.Label(cell, text=str(val), anchor="w")
                if key == "Age":
                    self._tx_age_field = (widget_val, block_meta.timestamp)

            widget_val.grid(row=0, column=1, sticky="ew", padx=5)

        # 2. Input/Output of Transaction
        frame_txn_io = tk.Frame(frame_tx_details)
        frame_txn_io.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_txn_io.columnconfigure(0, weight=1, uniform="txnio_cols")
        frame_txn_io.columnconfigure(1, weight=1, uniform="txnio_cols")

        # Headers
        tk.Label(frame_txn_io, text="From", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=0, sticky="w")
        tk.Label(frame_txn_io, text="To", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=1, sticky="w")

        # Inputs
        for i, tx_in in enumerate(tx.inputs, start=1):
            script_sig = tx_in.script_sig
            script_pk = tx_in.script_pubkey()
            if tx.is_coinbase():
                addr = "Coinbase"
            else:
                addr = script_sig.get_script_sig_sender() or "N/A"
            value = tx_in.value() or 0

            frame_input = tk.Frame(frame_txn_io)
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

            tk.Label(frame_input, text=f"{value/KTC:.8f}KTC", fg="gray").grid(row=1, column=0, sticky="w")

        # Outputs
        for i, tx_out in enumerate(tx.outputs, start=1):
            script_pk = tx_out.script_pubkey
            value = tx_out.value
            addr = script_pk.get_script_pubkey_receiver() or "N/A"

            frame_output = tk.Frame(frame_txn_io)
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

        # Footer
        frame_footer_block = tk.Frame(self.lf_tx_details)
        frame_footer_block.grid(row=2, column=0, columnspan=2, sticky="w")

        label_txn_block = tk.Label(frame_footer_block, text=f"This transaction belongs to Block #{block_meta.height}")
        label_txn_block.pack(side="left", padx=5, pady=5)

        btn_goto_txn_block = ttk.Button(
            frame_footer_block, text="Go", width=4,
            command=lambda q=block_meta.block_hash: self._search(q)
        )
        btn_goto_txn_block.pack(side="left", padx=5, pady=5)

        frame_footer = tk.Frame(self.lf_tx_details)
        frame_footer.grid(row=2, column=0, columnspan=2, sticky="e")

        frame_nav = tk.Frame(self.lf_tx_details)
        frame_nav.grid(row=2, column=0, columnspan=2, sticky="e")

        if self._init_from is not None:
            btn_return_to_from = ttk.Button(
                frame_nav, text="Back to Wallet", 
                command=lambda ifr=self._init_from: self.controller.switch_to_frame(ifr)
            )
            btn_return_to_from.pack(side="right", padx=5, pady=5)
            self._init_from = None

        if self._selected_block is not None and tx_meta.height == get_block_height_at_hash(self._selected_block.hash()):
            btn_return = ttk.Button(frame_nav, text="Return", command=self._switch_to_block_details)
        else:
            btn_return = ttk.Button(frame_nav, text="Return", command=self._switch_to_block_list)
        btn_return.pack(side="right", padx=5, pady=5)

        btn_refresh = ttk.Button(frame_nav, text="Refresh", command=self._switch_to_tx_details)
        btn_refresh.pack(side="right", padx=5, pady=5)

        self._selected_tx = tx
            
    def _generate_notfound(self, msg: str):
        label_msg = tk.Label(self.lf_notfound, text=msg)
        label_msg.pack(expand=True)

        btn_return = ttk.Button(self.lf_notfound, text="Return", command=self._switch_to_block_list)
        btn_return.pack(anchor="se", padx=5, pady=5)

    
    def _show_script_window(self, script_sig: Script | None=None, script_pubkey: Script | None=None):
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
        no_blocks = get_blockchain_height() + 1
        if no_blocks != self.no_block_rows:
            self.no_block_rows = no_blocks
            self.no_block_pages = ceil(self.no_block_rows / self.rows_per_page)

            # Auto refresh block list view when a new block is added
            if self._current_page == "block_list":
                self._page_select_block()

        match self._current_page:
            case "block_list":
                if self.tree_block_list:
                    for iid in self.tree_block_list.get_children():
                        height = int(self.tree_block_list.set(iid, "height"))
                        meta = get_block_metadata_at_height(height)
                        if meta is None:
                            continue

                        self.tree_block_list.set(iid, "age", format_age(time.time() - meta.timestamp))
                        
            case "block_details":
                label, created = self._block_age_field
                label.config(text=format_age(time.time() - created))

            case "tx_details":
                label, created = self._tx_age_field
                label.config(text=format_age(time.time() - created))

            case _:
                pass

        self.after(500, self._update)