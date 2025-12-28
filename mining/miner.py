import threading
import time
import logging

from multiprocessing import Process, Queue, Value, cpu_count
from blockchain.block import Block
from blockchain.header import Header
from blockchain.merkle_tree import MerkleTree
from blockchain.script import Script
from blockchain.transaction import Transaction, TransactionInput, TransactionOutput
from crypto.hashing import HASH256

from db.block import get_block_height_at_hash
from db.height import get_blockchain_height
from utils.helper import bytes_to_int, int_to_bytes
from utils.config import APP_CONFIG

log = logging.getLogger(__name__)

class Miner:
    """
    A Miner objects requires a `Block` object to be passed as an argument, 
    and an array of `TransactionOutput` for coinbase transaction creation.
    The `Block` object should **NOT** include the coinbase transaction (i.e. a block with 0 transactions is valid)
    
    
    The scriptSig for the coinbase transaction will be a 64 byte big-endian integer by default, used purely for mining.
    """
    def __init__(self, processes=None):
        self.cpu_count = cpu_count()
        if processes is None:
            self.no_processes = self.cpu_count
        else:
            self.no_processes = processes
            
        # self.batch_size = Value('Q', APP_CONFIG.get("mining", "batch_size"))
        
        
        self.nonce = Value('I', 0)
        self.sig_nonce = Value('Q', 0)
        
        self._mine_processes: list[Process] = []
        
        # Mining variables
        self._recent_hash_rates = []  # Moving average for stable hash rate reporting
        self._total_hashes = 0
        self._hash_counter = 0
        self._report_counter = 0
        self._desired_report_rate = 5 # No. of times a miner should report its hashing progress per second
        
        self._mine_start_time = 0
        self._mine_end_time = 0
        
        self._miner_thread = None
        self.stop_flag = Value('B', 1)
        
        self.mined_block: Block | None = None
        log.info("Miner initiated.")

    def mine(self, candidate_block: Block, cb_outputs: list[TransactionOutput]):
        """Main interface for mining."""
        with self.stop_flag.get_lock():
            self.stop_flag.value = 0
        
        self.mined_block = None
        
        self._miner_thread =  threading.Thread(
            target=self._initiate_miners,
            args=(candidate_block, cb_outputs),
            daemon=True
        )
        self._miner_thread.start()
        
    def _initiate_miners(self, candidate_block: Block, cb_outputs: list[TransactionOutput]) -> Block | None:
        # 1. Initial spawning of mining worker processes
        log.info(f"Initiating {self.no_processes} mining processes...")
        
        height = get_block_height_at_hash(candidate_block.prev_block) + 1
        log.info(f"Attempting to mine at block {height=}")
        
        miner_tag = str(APP_CONFIG.get("mining", "tag")).encode("utf-8")
        cmds = [int_to_bytes(height, 8), int_to_bytes(0, 64)]
        if miner_tag:
            cmds.append(miner_tag)
        script_sig = Script(cmds)
        
        cb_tx = build_coinbase_tx(script_sig, cb_outputs)
        header = candidate_block.header
        candidate_block.set_coinbase_tx(cb_tx)
        result_queue = Queue()  # Dedicated queue for each thread
        
        for i in range(self.no_processes):
            proc = Process(
                target=miner,
                args=(result_queue, 
                      header.copy(),
                      candidate_block.merkle_tree.copy(), 
                      cb_tx.copy(), 
                      i, 
                      self.no_processes, 
                      candidate_block.target,
                      height, 
                      miner_tag,
                      self.stop_flag
                      )
            )
            proc.start()
            self._mine_processes.append(proc)
        
        self._mine_start_time = time.time()
        self._last_hash_report = time.time()

        while not self.stop_flag.value:
            status, value = result_queue.get()
            
            if status == 0:
                # Shutdown
                break
            
            elif status == 1:  # !!! Found nonce !!!
                sig_nonce, nonce = value
                cmds = [int_to_bytes(height, 8), int_to_bytes(sig_nonce, 64)]
                if miner_tag:
                    cmds.append(miner_tag)
                script_sig = Script(cmds)
                cb_tx = build_coinbase_tx(script_sig=script_sig, outputs=cb_outputs)

                candidate_block.set_coinbase_tx(cb_tx)
                candidate_block.set_nonce(nonce)
                self.mined_block = candidate_block
                
                self.shutdown()
                break
            
            elif status == 2: # Hash counter
                self._hash_counter += value
                self._total_hashes += value
                self._report_counter += 1
            
            # Moderate batch_size ever 0.5s
            now = time.time()
            if (t_elapsed := now - self._last_hash_report) >= 0.5:
                hash_rate = self._hash_counter / t_elapsed
                self._hash_counter = 0
                self._last_hash_report = now

                self._record_hash_rate(hash_rate)

        log.info(f"Miner thread for {height=} finished.")
        return
        
        
    def shutdown(self):
        with self.stop_flag.get_lock():
            self.stop_flag.value = 1
        log.info("Miner stop flag set.")

        for proc in self._mine_processes:
            proc.join()
        
        self._mine_processes = [] 
        self._recent_hash_rates = []
        self._mine_end_time = time.time()
        
    
    def get_hashrate(self) -> float:
        """Returns a moving average of the 10 latest reported hashrates"""        
        hash_rates = self._recent_hash_rates[:]
        if hash_rates:
            return sum(hash_rates) / len(hash_rates)
        return 0
    
    def set_processes(self, n):
        self.no_processes = n
        
    def _record_hash_rate(self, hash_rate):
        """Records down the latest hash rate in self._recent_hash_rates, up to 10."""
        self._recent_hash_rates.append(hash_rate)
        if len(self._recent_hash_rates) > 10:
            self._recent_hash_rates.pop(0)
            

def miner(
    queue: Queue, 
    header: Header,
    merkle_tree: MerkleTree, 
    cb_tx: Transaction,
    start_nonce: int, 
    step: int, 
    target: int,
    height: int,
    miner_tag: bytes,
    v_stop_flag
    ):
    """Worker function for block mining. Designed for standard coinbase transactions only (see `build_coinbase_tx`)
    Queue statuses:
    """
    hash_count = 0

    batch = 1000
    last_report = time.perf_counter_ns()
    try:
        for sig_nonce in range(1 << 64):
            # ScriptSig format for coinbase transactions:
            # <Height 8B> <nonce 64B> <tag ?B>
            cmds = [int_to_bytes(height, 8), int_to_bytes(sig_nonce, 64)]
            if miner_tag:
                cmds.append(miner_tag)
            cb_tx.inputs[0].script_sig = Script(cmds)
            
            merkle_tree.update_leaf(0, cb_tx.hash())
            header.set_merkle_root(merkle_tree.root())
            partial_head = header.serialize_without_nonce()

            for nonce in range(start_nonce, 1 << 32, step):
                raw_header = partial_head + int_to_bytes(nonce)
                raw_header_hash = HASH256(raw_header)
                
                hash_count += 1
                if hash_count >= batch:
                    if v_stop_flag.value:
                        try:
                            queue.put_nowait((0, None))  
                        except:
                            pass
                        return
                    
                    now = time.perf_counter_ns()
                    t_elapsed_ns = max(now - last_report, 1)
                    batch = round(batch * (5e8/t_elapsed_ns))  # report every 0.5s
                    
                    queue.put((2, hash_count))
                    hash_count = 0
                    last_report = time.perf_counter_ns()
                    
                if bytes_to_int(raw_header_hash) < target:
                    if hash_count > 0:
                        queue.put((2, hash_count))
                    queue.put((1, (sig_nonce, nonce)))
            
        # No success
        if hash_count > 0:
            queue.put((2, hash_count))
            
    except KeyboardInterrupt:  # To prevent KeyboardInterrupt errors from hashlib to flood the terminal
        return
    except Exception as e:
        log.error(f"Error mining: {e}")
            

def build_coinbase_tx(script_sig: Script, outputs: list[TransactionOutput]) -> Transaction:
    """Standard Coinbase Transaction constructor, whereby scriptSig is <Height 8B> <nonce 64B> <tag ?B>"""
    
    tx_input = TransactionInput(
        prev_hash=bytes(32),
        prev_index=0xFFFFFFFF,
        script_sig=script_sig,
        sequence=0xFFFFFFFF
    )
    
    coinbase_tx = Transaction(
        version=1,
        inputs=[tx_input],
        outputs=outputs,
        locktime=0
    )
    
    return coinbase_tx
