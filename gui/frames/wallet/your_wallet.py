import tkinter as tk

from datetime import datetime, timedelta
from tkinter import ttk

from blockchain.block import Block
from crypto.key import wif_encode
from db.block import get_raw_block_at_height, get_block_metadata_at_height, get_blockchain_height
from db.addr import get_utxo_count, get_addr_utxos_value
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

        label_amount = tk.Label(LEFT,  text=f"{get_addr_utxos_value(self.node.pk_hash)/KTC} KTC",  font=("Segoe UI", 20, "bold"))
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
            text="Transactions over the past 90 days.",
            font=("Arial", 10, "italic"),
        )
        label_recent_tx.grid(row=0, column=0, sticky="w")

        btn_full_history = ttk.Button(lf_recent_tx, text="Full History", command=lambda: self.controller.switch_to_frame("transaction_history"))
        btn_full_history.grid(row=0, column=1, sticky="e",)

        # Recent txs
        canvas_tx_records = tk.Canvas(lf_recent_tx, borderwidth=0, highlightthickness=0)
        scrollbar_tx_records = ttk.Scrollbar(
            lf_recent_tx, orient="vertical", command=canvas_tx_records.yview
        )
        self.scroll_frame = tk.Frame(canvas_tx_records)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas_tx_records.configure(
                scrollregion=canvas_tx_records.bbox("all")
            ),
        )

        window_id = canvas_tx_records.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )

        # Sync frame width with canvas width
        canvas_tx_records.bind(
            "<Configure>",
            lambda e: canvas_tx_records.itemconfig(window_id, width=e.width),
        )

        canvas_tx_records.configure(yscrollcommand=scrollbar_tx_records.set)

        canvas_tx_records.grid(row=1, column=0, columnspan=2, sticky="nsew")
        scrollbar_tx_records.grid(row=1, column=2, sticky="ns")

        lf_recent_tx.rowconfigure(1, weight=1)
        lf_recent_tx.columnconfigure(0, weight=1)

        self._display_recent_txs()

    def _get_recent_transactions(self) -> dict[datetime, list]:
        """
        Returns a list containing transaction in the past 30 days
        grouped together in a dict

        Each record is a dict
        - type: "COINBASE" | "INPUT" | "OUTPUT"
        - value: Integer value in khets
        - tx: Transaction hash
        - timestamp: Timestamp
        """
        recent_txs = dict()

        height = get_blockchain_height()
        now = datetime.now()

        while True:
            meta = get_block_metadata_at_height(height)
            if not meta:
                break

            block_time = datetime.fromtimestamp(meta.timestamp)
            if now.date() - block_time.date() > timedelta(days=90):
                break

            records = self._get_relevant_tx(self.node.pk_hash, height)
            for record in records:
                recent_txs.setdefault(block_time.date(), []).append(record)

            height -= 1
            if height < 0:
                break

        return recent_txs

    def _display_recent_txs(self):
        recent_txs = self._get_recent_transactions()

        if not recent_txs:
            tk.Label(
                self.scroll_frame,
                text="No recent transactions",
                font=("Arial", 14),
                fg="gray",
                anchor="center",
            ).pack(fill="x", pady=20)
            return

        for date, records in recent_txs.items():
            date_str = date.strftime("%d %b %Y")

            lf_day = tk.LabelFrame(self.scroll_frame, text=date_str)
            lf_day.pack(fill="x", padx=10, pady=10, expand=True)

            lf_day.columnconfigure(0, weight=2)
            lf_day.columnconfigure(1, weight=4)
            lf_day.columnconfigure(2, weight=4)

            for i, rec in enumerate(records):
                # Type
                tx_type = rec["type"]
                tx_hash = rec["tx"]
                tx_value = rec["value"]
                label_tx_type = tk.Label(lf_day, text=tx_type, anchor="w")
                label_tx_type.grid(row=i, column=0, sticky="ew")

                # Value
                sign, value_color = ("-", "#bf1029") if tx_type == "OUTPUT" else ("+", "#3f8f29")
                label_value = tk.Label(lf_day, text=f"{sign}{tx_value/KTC}KTC", anchor="w", fg=value_color)
                label_value.grid(row=i, column=1, sticky="ew")

                # tx Hash
                btn_tx = tk.Button(
                    lf_day, 
                    text=truncate_bytes(tx_hash, 4), font=HexFont(8), bg="#f0f8ff", 
                    command=lambda q=tx_hash: self.controller.switch_to_frame(
                        "view_blockchain", 
                        init_query=q,
                        init_from="your_wallet"
                    )
                )
                btn_tx.grid(row=i, column=2, sticky="ew")
                attach_tooltip(btn_tx, tx_hash.hex())
                
                
    def _get_relevant_tx(self, pk_hash: bytes, height: int):
        # TODO: Implement Caching
        addr = pk_hash
        records = []

        raw_block = get_raw_block_at_height(height)
        if not raw_block:
            return records

        block = Block.parse(raw_block)

        timestamp = block.header.timestamp
        for tx in block._transactions:
            tx_hash = tx.hash()
            
            total_in = total_out = 0
            for tx_in in tx.inputs:
                if script_pubkey := tx_in.script_pubkey():
                    if addr == script_pubkey.get_script_pubkey_receiver():
                        total_in += tx_in.value() or 0
                        
            for tx_out in tx.outputs:
                if addr == tx_out.script_pubkey.get_script_pubkey_receiver():
                    total_out += tx_out.value
                        

            if tx.is_coinbase():
                records.append(
                    {
                        "type": "COINBASE",
                        "value": total_out,
                        "tx": tx_hash,
                        "timestamp": timestamp,
                    }
                )
                continue

            if total_in > 0:
                records.append(
                    {
                        "type": "INPUT",
                        "value": total_in,
                        "tx": tx_hash,
                        "timestamp": timestamp,
                    }
                )

            if total_out > 0:
                records.append(
                    {
                        "type": "OUTPUT",
                        "value": total_out,
                        "tx": tx_hash,
                        "timestamp": timestamp,
                    }
                )

        return records
