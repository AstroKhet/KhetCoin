import math
import logging
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from blockchain.block import Block, calculate_block_subsidy
from blockchain.script import P2PKH_script_pubkey
from blockchain.transaction import Transaction, TransactionOutput
from db.block import calculate_block_target, get_block_hash_at_height, get_blockchain_height
from gui.colours import colour_pattern_gen
from gui.frames.common.columns import TX_COLS
from gui.frames.common.transaction import tx_popup
from gui.frames.common.scrollable import create_scrollable_treeview
from gui.vcmd import register_VMCD_KTC
from ktc_constants import KTC, MAX_KTC
from networking.node import Node
from utils.config import APP_CONFIG
from utils.fmt import format_age, format_bytes, format_hashrate, truncate_bytes
from utils.helper import target_to_bits

log = logging.getLogger(__name__)

class MiningFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        self.vcmd_KTC = register_VMCD_KTC(self)
        
        self.columnconfigure(0, weight=1, uniform="main")
        self.columnconfigure(1, weight=1, uniform="main")
        self.rowconfigure(0, weight=1)
        
        # 1. Left frame for mining options
        self.frame_left = ttk.Frame(self)
        self.frame_left.rowconfigure(0, weight=3)
        self.frame_left.rowconfigure(1, weight=7)
        self.frame_left.columnconfigure(0, weight=1)
        self.frame_left.grid(row=0, column=0, sticky="nsew")
        
        # 1.1 Top section for mining stats (hash rate, duration, etc)
        self.lf_mining_stats = ttk.LabelFrame(self.frame_left, text="Mining Stats")
        self.lf_mining_stats.columnconfigure(0, weight=1)
        self.lf_mining_stats.rowconfigure(1, weight=1)

        self.lf_mining_stats.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 1.1.1 Frame Hash Rate
        self.frame_hash_rate = ttk.Frame(self.lf_mining_stats)
        self.frame_hash_rate.rowconfigure(0, weight=1)
        self.frame_hash_rate.columnconfigure(0, weight=1)
        self.frame_hash_rate.grid(row=0, column=0, sticky="nsew")
        tk.Label(self.frame_hash_rate, text="Hash Rate").grid(row=0, column=0, sticky="nsew")
        
        self.label_hash_rate = tk.Label(self.frame_hash_rate, text=format_hashrate(0), font=("Segoe UI", 15, "bold"))
        self.label_hash_rate.grid(row=1, column=0, sticky="nsew")
        
        self.label_mining_status = tk.Label(self.frame_hash_rate, text="(Miner Inactive)")
        self.label_mining_status.grid(row=2, column=0, sticky="nsew", pady=5)
        
        # 1.1.2 Frame for controlling no. of miner cores
        self.frame_mining_power_config = ttk.Frame(self.frame_hash_rate)
        self.frame_mining_power_config.grid(row=3, column=0, sticky="nsew")
        self.frame_mining_power_config.columnconfigure(1, weight=1)
        
        self.label_mining_power = ttk.Label(self.frame_mining_power_config, text=f"No. mining processes: {APP_CONFIG.get('mining', 'mining_processes')}") 
        self.label_mining_power.grid(row=0, column=1, pady=(25, 3))
        
        self.scale_mining_power = ttk.Scale(self.frame_mining_power_config, from_=0, to=self.node.miner.cpu_count, orient=tk.HORIZONTAL, command=self._scale_cpu_cores)
        self.scale_mining_power.set(APP_CONFIG.get("mining", "mining_processes"))
        self.scale_mining_power.grid(row=1, column=1, sticky="ew", padx=20, pady=10)
        
        ttk.Label(self.frame_mining_power_config, text="0").grid(row=1, column=0, padx=(10, 3))
        ttk.Label(self.frame_mining_power_config, text=f"{self.node.miner.cpu_count} cores").grid(row=1, column=2, padx=(3, 10))
        
        
        # 1.2 Bottom section for mining options
        self.frame_mining_options = ttk.Frame(self.frame_left)
        self.frame_mining_options.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame_mining_options.rowconfigure(2, weight=1)
        self.frame_mining_options.columnconfigure(0, weight=1)
        
        # 1.2.1 Mining conditions
        frame_mining_conditions = ttk.Frame(self.frame_mining_options)
        frame_mining_conditions.grid(row=1, column=0, sticky="nsew")
        frame_mining_conditions.columnconfigure(1, weight=1)
        
        ttk.Label(frame_mining_conditions, text="Minimum fee before mining: ").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        
        self.var_min_total_fee = tk.DoubleVar(value=0.0)
        self.sb_min_total_fee = ttk.Spinbox(frame_mining_conditions, from_=0, to=MAX_KTC, increment=0.00000100, textvariable=self.var_min_total_fee, format="%.8f", validate="key", validatecommand=self.vcmd_KTC)
        self.sb_min_total_fee.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(frame_mining_conditions, text="KTC").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        
        # 1.2.2 Main mining btns
        frame_mining_btns = ttk.Frame(self.frame_mining_options)
        frame_mining_btns.grid(row=2, column=0, sticky="nsew")
        
        self.btn_mining = tk.Button(
            frame_mining_btns,
            text="Start Mining",
            bg="#9dbcd4",
            height=2,
            font=("Segue UI", 15, "bold"),
            command=self._toggle_mining_switch
        )
        self.btn_mining.pack(fill=tk.BOTH, padx=40, pady=15)
        
        btn_more_info = ttk.Button(self.frame_mining_options, text="More Information", command=self._show_more_info)
        btn_more_info.grid(row=3, column=0)
        
        
        # 2. Right frame for transactions included in mining
        self.frame_right = ttk.Frame(self)
        self.frame_right.rowconfigure(1, weight=1)
        self.frame_right.columnconfigure(0, weight=1)
        self.frame_right.grid(row=0, column=1, sticky="nsew")
        
        # 2.1 Top section for mempool stats
        self.lf_mempool_details = ttk.LabelFrame(self.frame_right, text="Mempool Details")
        self.lf_mempool_details.grid(row=0, column=0, sticky="nsew")
        
        # 2.1.1 Empty labels to be filled with self._update
        self.label_no_tx = tk.Label(self.lf_mempool_details, anchor="w", padx=10)
        self.label_no_tx.pack(fill="x", pady=2)
        
        self.label_tx_size = tk.Label(self.lf_mempool_details, anchor="w", padx=10)
        self.label_tx_size.pack(fill="x", pady=2)
        
        self.label_tx_fee = tk.Label(self.lf_mempool_details, anchor="w", padx=10)
        self.label_tx_fee.pack(fill="x", pady=2)        
        
        # 2.2 Bottom section for (valid) mempool txs
        self.lf_mempool = ttk.LabelFrame(self.frame_right, text="Mempool")
        self.lf_mempool.grid(row=1, column=0, sticky="nsew")
        self.lf_mempool.rowconfigure(0, weight=1)
        self.lf_mempool.columnconfigure(0, weight=1)

        self.tree_mempool = create_scrollable_treeview(self.lf_mempool, TX_COLS, (0, 0))
        self.tree_mempool.bind("<<TreeviewSelect>>", lambda _: self._on_tx_select("valid"))
        
        
        # 3. Initial setup
        self._selected_tx: Transaction | None = None
        
        # This is different from Miner.is_mining; self._mining just means the button was pressed and will mine whenever mining conditions are reached.
        self._mining = False  
        self._generate_mempool()
        self._update()
    
    def _generate_mempool(self):
        latest_txs = self.node.mempool.get_all_valid_tx()
        tree_valid_tx_iids = list(self.tree_mempool.get_children())

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
                self.tree_mempool.item(tx_hash.hex(), values=values)
                tree_valid_tx_iids.remove(tx_hash.hex())
            else:
                self.tree_mempool.insert("", "end", iid=tx_hash.hex(), values=values)

        # Remove extra old rows if new list is shorter
        for iid in tree_valid_tx_iids:
            self.tree_mempool.delete(iid)
            
    def _on_tx_select(self, _):
        selection = self.tree_mempool.selection()
        if not selection:
             return
        
        tx_hash = bytes.fromhex(selection[0])
        tx = self.node.mempool.get_valid_tx(tx_hash)
        tx_popup(self, tx, "valid")
            
    def _generate_metadata(self):
        return
    
    def _toggle_mining_switch(self):
        if self.node.miner.is_mining:
            self.node.miner.shutdown()
            self.btn_mining.config(text="Start Mining", bg="#9dbcd4")
            self.scale_mining_power.config(state="normal")
        else:
            # Poll miner first 
            # This prevents re-mining with the same mempool in the rare event where, within 1 update/polling cycle,
            # poll (nothing) -> block mined -> start mining (uses old mempool) -> poll (block, mempool updated)
            self.scale_mining_power.config(state="disabled")
            self.btn_mining.config(text="Stop Mining", bg="#9dbcd4")
            self._poll_miner()

    def _generate_candidate_block(self) -> Block | None:
        txs = self.node.mempool.get_all_valid_tx()
        height = get_blockchain_height() + 1
        block = Block(
            version=1,
            prev_block=get_block_hash_at_height(height - 1),
            timestamp=int(time.time()),
            bits=target_to_bits(calculate_block_target(height)),
            nonce=0,
            txs=txs
        )
        
        return block
    
    def _update(self):
        # 1. Update Mempool Summary
        no_txs = self.node.mempool.get_no_tx()
        total_size = self.node.mempool.get_total_size()
        total_fee = self.node.mempool.get_total_fee()
        if no_txs != 0:
            avg_size = total_size / no_txs
            avg_fee = total_fee / no_txs
        else:
            avg_fee = avg_size = 0
        
        self.label_no_tx.config(text=f"No. Transactions: {no_txs}")
        self.label_tx_size.config(text=f"Total Size: {format_bytes(total_size)} (average {format_bytes(avg_size)})")
        self.label_tx_fee.config(text=f"Total Fee: {total_fee/KTC:.8f}KTC (average {avg_fee/KTC:.8f}KTC)")
        
        # 2. Age updates
        for iid in self.tree_mempool.get_children():
            tx_hash = bytes.fromhex(iid)     
            tx_time = self.node.mempool.get_tx_time(tx_hash)
            self.tree_mempool.set(iid, "received", format_age(time.time() - tx_time))
        
        # 3. Check mempool for any updates
        if self.node.mempool.check_update_valids(i=2):
            self._generate_mempool()
            self._generate_metadata()
        
        # 4. Mining updates
        self.label_hash_rate.config(text=format_hashrate(self.node.miner.get_hashrate()))
        
        self._poll_miner()
            
        self.after(500, self._update)
    
    def _scale_cpu_cores(self, *_):
        val = round(self.scale_mining_power.get())
        if val == self.node.miner.no_processes:
            return
        
        self.node.miner.set_processes(val)
        self.label_mining_power.config(text=f"No. mining processes: {val}")
        APP_CONFIG.set("mining", "mining_processes", val)


        
    def _poll_miner(self):
        """
        Polls the event `Miner.mined`
        \nIf a block is mined, resets `Miner.mined` and then broadcasts the mined block.
        """
        
        if not self.node.miner.mined.is_set():
            return
        
        self.node.miner.mined.clear()
        
        nonce = self.node.miner.nonce.value
        sig_nonce = self.node.miner.sig_nonce.value   
        
        block = self._generate_candidate_block()
        # Default: Coinbase transaction to miner only.
        output = TransactionOutput(
            calculate_block_subsidy(get_blockchain_height() + 1),
            P2PKH_script_pubkey(self.node.pk_hash)
        )
        self.node.miner.mine(block, [output])
        self.btn_mining.config(text="Stop Mining", bg="#fa694f")
        
        
            
        
    def _show_more_info(self):
        info_msg = """Mining in Khetcoin is the process of varying the block's nonce and the coinbase transaction's script_sig until the block's 32-byte hash falls below the target value.
        \nYou will receive the full coinbase reward for any block you successfully mine.
        \nThe number of mining processes determines how many worker miners run concurrently, up to your CPU's core count. More processes raise CPU usage, though hash rate may not scale linearly. 
        \nThe minimum fee before mining is the total fee of all transactions in your mempool when mining begins. After pressing "Start Mining", your node continuously monitors the mempool for new transactions or ones already mined by others.
        \nSetting the minimum fee to 0 KTC is completely valid; the block will simply contain a coinbase transaction that pays the current block reward to you. You are highly advised to do this in the early stages of KhetCoin.
        \nThe transactions your node is currently mining will be highlighted in the mempool.
        """
        messagebox.showinfo("Mining in Khetcoin App", info_msg)
        
        
