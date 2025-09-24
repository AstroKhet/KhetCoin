import tkinter as tk

from datetime import datetime, timedelta
from tkinter import ttk

from blockchain.block import get_relevant_tx
from blockchain.transaction import get_utxo_addr_value
from crypto.key import wif_encode
from db.block import get_block_metadata_at_height, get_blockchain_height
from db.utxo import get_utxo_count
from gui.fonts import HexFont
from gui.helper import attach_tooltip, copy_to_clipboard
from ktc_constants import KTC
from networking.node import Node
from utils.fmt import truncate_bytes


class YourWalletFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        # Left side
        LEFT = tk.Frame(self)
        LEFT.place(relx=0, rely=0, relwidth=0.5, relheight=1.0)

        label_wallet = tk.Label(LEFT, text=f"{self.node.name}'s Wallet", font=("Segoe UI", 16, "bold"), )
        label_wallet.pack(anchor="w", padx=20, pady=(20, 15))

        label_addr = tk.Label(LEFT, text="ADDRESS", font=("Segoe UI", 10), fg="gray")
        label_addr.pack(anchor="w", padx=20, pady=(0, 5))

        frame_pk_wif = tk.Frame(LEFT)
        frame_pk_wif.pack(anchor="w", padx=20, pady=(0, 30))  # padding applied here

        label_pk_wif = tk.Label(frame_pk_wif,  text=wif_encode(self.node.pk_hash),  font=("Courier", 10))
        label_pk_wif.pack(side="left")

        btn_pk_wif_copy = ttk.Button(frame_pk_wif, text="Copy", command=lambda: copy_to_clipboard(self, wif_encode(self.node.pk_hash)))
        btn_pk_wif_copy.pack(side="left", padx=(10, 0))

        label_balance = tk.Label(LEFT, text="BALANCE", font=("Segoe UI", 10), fg="gray")
        label_balance.pack(anchor="w", padx=20, pady=(0, 5))

        label_amount = tk.Label(LEFT,  text=f"{get_utxo_addr_value(self.node.pk_hash)/KTC} KTC",  font=("Segoe UI", 20, "bold"))
        label_amount.pack(anchor="w", padx=20)

        frame_utxo = tk.Frame(LEFT)
        frame_utxo.pack(anchor="w", padx=20, pady=(0, 30)) 

        label_utxo = tk.Label(frame_utxo, text=f"From {get_utxo_count(self.node.pk_hash)} UTXO(s)", font=("Segoe UI", 10))
        label_utxo.pack(side="left")

        btn_goto_utxo = ttk.Button(frame_utxo, text="See all", command=lambda: self.controller.switch_to_frame("UTXO"))
        btn_goto_utxo.pack(side="left", padx=(10, 0))

        # Right side
        RIGHT = tk.Frame(self)
        RIGHT.place(relx=0.5, rely=0, relwidth=0.5, relheight=1.0)

        lf_recent_tx = tk.LabelFrame(RIGHT, text="Recent Transactions")
        lf_recent_tx.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        label_recent_tx = tk.Label(
            lf_recent_tx,
            text="Transactions over the past 30 days.",
            font=("Arial", 10, "italic"),
        )
        label_recent_tx.grid(row=0, column=0, sticky="w")

        btn_full_history = ttk.Button(lf_recent_tx, text="Full History", command=lambda: self.controller.switch_to_frame("transaction_history"))
        btn_full_history.grid(row=0, column=1, sticky="e",)

        # Recent Txns
        canvas_txn_records = tk.Canvas(lf_recent_tx, borderwidth=0, highlightthickness=0)
        scrollbar_txn_records = ttk.Scrollbar(
            lf_recent_tx, orient="vertical", command=canvas_txn_records.yview
        )
        self.scroll_frame = tk.Frame(canvas_txn_records)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas_txn_records.configure(
                scrollregion=canvas_txn_records.bbox("all")
            ),
        )

        window_id = canvas_txn_records.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )

        # Sync frame width with canvas width
        canvas_txn_records.bind(
            "<Configure>",
            lambda e: canvas_txn_records.itemconfig(window_id, width=e.width),
        )

        canvas_txn_records.configure(yscrollcommand=scrollbar_txn_records.set)

        canvas_txn_records.grid(row=1, column=0, columnspan=2, sticky="nsew")
        scrollbar_txn_records.grid(row=1, column=2, sticky="ns")

        lf_recent_tx.grid_rowconfigure(1, weight=1)
        lf_recent_tx.grid_columnconfigure(0, weight=1)

        self._display_recent_txns()

    def _get_recent_transactions(self) -> dict[datetime, list]:
        """
        Returns a list containing transaction in the past 30 days
        grouped together in a dict

        Each record is a dict
        - type: "COINBASE" | "INPUT" | "OUTPUT"
        - value: Integer value in khets
        - txn: Transaction hash
        - timestamp: Timestamp
        """
        recent_txns = dict()

        height = get_blockchain_height()
        now = datetime.now()

        while True:
            meta = get_block_metadata_at_height(height)
            if not meta:
                break

            blk_time = datetime.fromtimestamp(meta.timestamp)
            if now.date() - blk_time.date() > timedelta(days=30):
                break

            records = get_relevant_tx(self.node.pk_hash, height)
            for record in records:
                recent_txns.setdefault(blk_time.date(), []).append(record)

            height -= 1
            if height < 0:
                break

        return recent_txns

    def _display_recent_txns(self):
        recent_txns = self._get_recent_transactions()

        if not recent_txns:
            tk.Label(
                self.scroll_frame,
                text="No recent transactions",
                font=("Arial", 14),
                fg="gray",
                anchor="center",
            ).pack(fill="x", pady=20)
            return

        for date, records in recent_txns.items():
            date_str = date.strftime("%d %b %Y")

            lf_day = tk.LabelFrame(self.scroll_frame, text=date_str)
            lf_day.pack(fill="x", padx=10, pady=10, expand=True)

            lf_day.grid_columnconfigure(0, weight=2)
            lf_day.grid_columnconfigure(1, weight=4)
            lf_day.grid_columnconfigure(2, weight=4)

            for i, rec in enumerate(records):
                # Type
                txn_type = rec["type"]
                txn_hash = rec["txn"]
                txn_value = rec["value"]
                label_txn_type = tk.Label(lf_day, text=txn_type, anchor="w")
                label_txn_type.grid(row=i, column=0, sticky="ew")

                # Value
                sign, value_color = ("-", "#bf1029") if txn_type == "OUTPUT" else ("+", "#3f8f29")
                label_value = tk.Label(lf_day, text=f"{sign}{txn_value/KTC}KTC", anchor="w", fg=value_color)
                label_value.grid(row=i, column=1, sticky="ew")

                # Txn Hash
                btn_txn = tk.Button(
                    lf_day, 
                    text=truncate_bytes(txn_hash, 4), font=HexFont(8), bg="#f0f8ff", 
                    command=lambda q=txn_hash: self.controller.switch_to_frame(
                        "view_blockchain", 
                        init_query=q,
                        init_from="your_wallet"
                    )
                )
                btn_txn.grid(row=i, column=2, sticky="ew")
                attach_tooltip(btn_txn, txn_hash.hex())
                