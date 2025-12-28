import math
import logging
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from blockchain.block import Block, calculate_block_subsidy
from blockchain.script import P2PKH_script_pubkey
from blockchain.transaction import Transaction, TransactionOutput
from db.block import calculate_block_target, get_block_height_at_hash
from db.functions import connect_block, save_block_data
from db.height import get_blockchain_height
from gui.colours import BTN_NEUTRAL_BLUE, BTN_STOP_RED
from gui.fonts import MonoFont, SansFont
from gui.common.columns import MEMPOOL_TX_COLS
from gui.common.scrollable import create_scrollable_treeview
from gui.common.transaction import tx_popup
from gui.vcmd import register_VMCD_KTC
from ktc_constants import KTC, MAX_KTC
from networking.constants import BLOCK_TYPE
from networking.messages.types.inv import InvMessage
from networking.node import Node
from utils.config import APP_CONFIG
from utils.fmt import format_age, format_bytes, format_hashrate, truncate_bytes
from utils.helper import target_to_bits

log = logging.getLogger(__name__)



_frame_id = 23

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
        
        self.label_hash_rate = tk.Label(self.frame_hash_rate, text=format_hashrate(0), font=SansFont(16, weight="bold"))
        self.label_hash_rate.grid(row=1, column=0, sticky="nsew")
        
        self.label_mining_status = tk.Label(self.frame_hash_rate, text="(Miner inactive)")
        self.label_mining_status.grid(row=2, column=0, sticky="nsew", pady=5)
        
        # 1.1.2 Frame for controlling no. of miner cores
        self.frame_mining_config = ttk.Frame(self.frame_hash_rate)
        self.frame_mining_config.grid(row=3, column=0, sticky="nsew")
        self.frame_mining_config.columnconfigure(1, weight=1)
        
        self.label_mining_power = ttk.Label(self.frame_mining_config, text=f"No. mining processes: {APP_CONFIG.get('mining', 'mining_processes')}") 
        self.label_mining_power.grid(row=0, column=1, pady=(25, 3))
        
        self.scale_mining_power = ttk.Scale(self.frame_mining_config, from_=1, to=self.node.miner.cpu_count, orient=tk.HORIZONTAL, command=self._scale_cpu_cores)
        self.scale_mining_power.set(APP_CONFIG.get("mining", "mining_processes"))
        self.scale_mining_power.grid(row=1, column=1, sticky="ew", padx=20, pady=10)
        
        ttk.Label(self.frame_mining_config, text="1").grid(row=1, column=0, padx=(10, 3))
        ttk.Label(self.frame_mining_config, text=f"{self.node.miner.cpu_count} cores").grid(row=1, column=2, padx=(3, 10))
        
        self.frame_miner_tag = ttk.Frame(self.frame_mining_config)
        self.frame_miner_tag.grid(row=2, column=1)
        
        ttk.Label(self.frame_miner_tag, text="Miner tag: ").grid(row=0, column=0)
        self.label_miner_tag = tk.Label(self.frame_miner_tag, text=APP_CONFIG.get("mining", "tag"), font=MonoFont())
        self.label_miner_tag.grid(row=0, column=1)
        
        # 1.2 Bottom section for mining options
        self.frame_mining_options = ttk.Frame(self.frame_left)
        self.frame_mining_options.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame_mining_options.rowconfigure(3, weight=1)
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
        
        # 1.2.2 Mining notifications
        
        ttk.Label(frame_mining_conditions, text="Notify when mined: ").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.var_notification = tk.BooleanVar(value=True)
        self.chk_notification = ttk.Checkbutton(frame_mining_conditions, variable=self.var_notification)
        self.chk_notification.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        
        # 1.2.2 Main mining btns
        self.btn_mining = tk.Button(
            self.frame_mining_options,
            text="Start Mining",
            bg=BTN_NEUTRAL_BLUE,
            height=2,
            width=15,
            font=("Segue UI", 15, "bold"),
            command=self._toggle_mining_switch
        )
        self.btn_mining.grid(row=2, column=0, padx=5, pady=12)
        
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
        
        self.label_mining_reward = tk.Label(self.lf_mempool_details, anchor="w", padx=10)
        self.label_mining_reward.pack(fill="x", pady=2)     
        
        
        # 2.2 Bottom section for (valid) mempool txs
        self.lf_mempool = ttk.LabelFrame(self.frame_right, text="Mempool")
        self.lf_mempool.grid(row=1, column=0, sticky="nsew")
        self.lf_mempool.rowconfigure(0, weight=1)
        self.lf_mempool.columnconfigure(0, weight=1)

        self.tree_mempool = create_scrollable_treeview(self.lf_mempool, MEMPOOL_TX_COLS, (0, 0))
        self.tree_mempool.bind("<<TreeviewSelect>>", lambda _: self._on_tx_select("valid"))
        self.tree_mempool.tag_configure("highlight", background="#ffd6e0")       
        
        # 3. Initial setup
        self._selected_tx: Transaction | None = None
        self._last_mined_block_hash: bytes = self.node.block_tip_index.hash
        
        # This is different from Miner.is_mining; self._mining just means the button was pressed and will mine whenever mining conditions are reached.
        self._mining = False  
        self._mining_start_t = None
        self._generate_mempool_treeview()
        
        self._is_active = True
        self._update()

    def on_hide(self):
        self._is_active = False
        
    def on_show(self):
        self._is_active = True
        self.label_miner_tag.config(text=APP_CONFIG.get("mining", "tag"))
        
        
    def _generate_mempool_treeview(self):
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
                f"{format_age(time.time() - self.node.mempool.get_tx_time(tx_hash))} ago"
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
        if self._mining:  # Turn OFFF
            log.info("Stop Miner clicked.")
            if self.node.miner.stop_flag.value == 0:
                self.node.miner.shutdown()
            
            self.scale_mining_power.config(state="normal")
            self.sb_min_total_fee.config(state="normal")
            
            self.label_mining_status.config(text="(Miner inactive)")
            self.btn_mining.config(text="Start Mining", bg="#9dbcd4")
            self._remove_highlights()
        else:  # Turn ON
            log.info("Start Miner clicked.")
            self.label_mining_status.config(text="(Waiting for mempool to hit min fee...)")
            self.scale_mining_power.config(state="disabled")
            self.sb_min_total_fee.config(state="disabled")
            self.btn_mining.config(text="Stop Mining", bg=BTN_STOP_RED)
            
            # Poll miner first 
            # This prevents re-mining with the same mempool in the rare event where, within 1 update/polling cycle,
            # poll (nothing) -> block mined -> stop miner -> start miner (uses old mempool) -> poll (block, mempool updated)
            self._poll_miner()
    
        self._mining = not self._mining
        
        
    def _poll_miner(self):
        # 1. Process any mined block
        if (mined_block := self.node.miner.mined_block) is not None:
            self._process_mined_block(mined_block)
            self._mining_start_t = None
        
        # 2. If miner is stopped, start miner
        if self.node.miner.stop_flag.value:
            min_total_fee = self.var_min_total_fee.get()
            if self.node.mempool.get_total_fee() >= min_total_fee:
                self._start_miner()
                self._mining_start_t = time.monotonic()
                self.label_mining_status.config(text=f"Mining... ({format_age(0)})")
        
        # 3. If miner is active, update GUI for mining duration
        else:
            t_mining = round(time.monotonic() - self._mining_start_t)
            self.label_mining_status.config(text=f"Mining... ({format_age(t_mining)})")

    def _start_miner(self):
        """Creates coinbase transactions and activates miner"""
        if self.node.miner.stop_flag.value == 0:   # already mining
            return
        
        if block := self._generate_candidate_block():
            # Default: Coinbase transaction to miner only.
            total_fee = self.node.mempool.get_total_fee()
            reward = calculate_block_subsidy(get_blockchain_height() + 1) + total_fee
            cb_outputs = [
                TransactionOutput(reward, P2PKH_script_pubkey(self.node.pk_hash))
            ]
            self.node.miner.mine(block, cb_outputs)
            
            self._highlight_mempool([tx.hash() for tx in block.get_transactions()])
        else:
            messagebox.showerror("Error", "Something went wrong when generating a candidate block for mining :(")
        
    def _generate_candidate_block(self) -> Block | None:
        tip_index = self.node.block_tip_index
        txs = self.node.mempool.get_all_valid_tx(explicit_sort=True)
        height = get_block_height_at_hash(tip_index.hash) + 1
        try:
            block = Block(
                version=1,
                prev_block=tip_index.hash,
                timestamp=int(time.time()),
                bits=target_to_bits(calculate_block_target(height, tip_index.prev_hash)),
                nonce=0,
                txs=txs
            )
        except Exception as e:
            log.error(f"Failed to create candidate block: {e}")
            return None
        
        return block
        
    def _process_mined_block(self, block: Block):
        self._remove_highlights()
        
        # 0. Verify block guard
        if not block.verify():
            messagebox.showerror("Miner Error", "Something wrong happened with the miner")
            return
        
        # 1. Save block
        save_block_data(block)
        connect_block(block, self.node)
        
        self._last_mined_block_hash = block.hash()
 
        # 2. Broadcast block
        inventory = [(BLOCK_TYPE, block.hash())]
        inv_msg = InvMessage(inventory)
        self.node.broadcast(inv_msg)
        if self.var_notification.get():
            messagebox.showinfo("Block mined", f"Your have mined block no. {block.get_height()}")
        
        
    def _scale_cpu_cores(self, *_):
        val = round(self.scale_mining_power.get())
        if val == self.node.miner.no_processes:
            return
        
        self.node.miner.set_processes(val)
        self.label_mining_power.config(text=f"No. mining processes: {val}")
        APP_CONFIG.set("mining", "mining_processes", val)  
        
    def _highlight_mempool(self, tx_hashes):
        for iid in self.tree_mempool.get_children():
            tx_hash = bytes.fromhex(iid)
            if tx_hash in tx_hashes:
                self.tree_mempool.item(iid, tags=("highlight",))
    
    def _remove_highlights(self):
        for iid in self.tree_mempool.get_children():
            self.tree_mempool.item(iid, tags=())
    
    def _update(self):
        if self._is_active:
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
            reward = calculate_block_subsidy(get_blockchain_height() + 1) + total_fee
            self.label_mining_reward.config(text=f"Mining Reward: {reward/KTC:.8f}KTC")
            
            # 2. Age updates
            for iid in self.tree_mempool.get_children():
                tx_hash = bytes.fromhex(iid)     
                tx_time = self.node.mempool.get_tx_time(tx_hash)
                self.tree_mempool.set(iid, "received", format_age(time.time() - tx_time))
            
            # 3. Check mempool for any updates
            if self.node.mempool.check_update_valids(_frame_id):
                self._generate_mempool_treeview()
                self._generate_metadata()
            
            # 4. Mining updates
            self.label_hash_rate.config(text=format_hashrate(self.node.miner.get_hashrate()))
        
        # Allow mining in background
        if self._mining:
            if self.node.check_updated_blockchain(_frame_id):  # Restart mining if someone else propagates a new valid block that extends the active chain
                if self.node.block_tip_index.hash != self._last_mined_block_hash:
                    log.info(f"Miner restarted as new block {self.node.block_tip_index.hash} set as block tip.")
                    log.info("miner shutdown called from mining frame _update")
                    self.node.miner.shutdown()
                    self._start_miner()
                
            self._poll_miner()
            
        self.after(500, self._update)
    
    def _show_more_info(self):
        info_msg = """Mining in Khetcoin is the process of varying the candidate block's nonce and its coinbase transaction's script_sig until the block's 32-byte hash falls below the target value.
        \nYou will receive the full coinbase reward for any block you successfully mine.
        \nThe number of mining processes determines how many workers run concurrently. You should try to find the ideal number of processes on your PC. While more processes increase CPU usage, the total hashrate may not scale linearly (and may even fall off if your CPU's logical processes > CPU cores)
        \nThe minimum fee before mining is the total fee of all transactions in your mempool when mining begins. After pressing "Start Mining", your node continuously monitors the mempool for new transactions or ones already mined by others.
        \nSetting the minimum fee to 0 KTC is valid; the miner will still mine a block that contain a coinbase transaction paying the current block reward to you. You are advised to do this when the mempool is empty.
        \nThe transactions your node is currently mining will be highlighted in the mempool.
        """
        messagebox.showinfo("Mining in Khetcoin App", info_msg)
        
        
