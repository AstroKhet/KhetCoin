import threading
import time
import logging

from multiprocessing import Process, Queue, Event, Value, cpu_count

from blockchain.block import Block
from blockchain.header import Header
from blockchain.merkle_tree import MerkleTree
from blockchain.script import Script
from blockchain.transaction import Transaction, TransactionInput, TransactionOutput
from crypto.hashing import HASH256

from utils.fmt import format_hashrate
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
        self.block = None
        self.target = None
        self.outputs = None
        
        self.cpu_count = cpu_count()
        if processes is None:
            self.no_processes = self.cpu_count
        else:
            self.no_processes = processes
            
        self.batch_size = Value('Q', APP_CONFIG.get("mining", "batch_size"))
        self.stop_flag = Value('B', 1)
        
        self.mined = Event()
        self.nonce = Value('I', 0)
        self.sig_nonce = Value('Q', 0)
        
        self.result_queue = Queue()
        self.processes: list[Process] = []
        
        # Mining variables
        self._recent_hash_rates = []  # Moving average for stable hash rate reporting
        self._total_hashes = 0
        self._hash_counter = 0
        self._report_counter = 0
        self._desired_report_rate = 5 # No. of times a miner should report its hashing progress per second
        
        self._mine_start_time = 0
        self._mine_end_time = 0
        
        self._miner_thread = None
        
        self.is_mining = False
        log.info("Miner initiated.")

    def mine(self, block, outputs):
        self.mined.clear()
        
        with self.stop_flag.get_lock():
            self.stop_flag.value = 0
            
        self._miner_thread =  threading.Thread(
            target=self.start_mining,
            args=(block, outputs),
            daemon=True
        )
        
        self._miner_thread.start()
        
    def start_mining(self, block: Block, outputs: list[TransactionOutput]) -> Block | None:
        # 1. Initial spawning of mining worker processes
        print('start mining')
        log.info('Mining process started')
        
        self.block = block
        self.target = block.target
        self.outputs = outputs
        
        header = block.header
        cb_tx = build_coinbase_tx(0, outputs)
        block.add_tx(cb_tx)
        
        for i in range(self.no_processes):
            proc = Process(
                target=miner,
                args=(self.result_queue, 
                      header.copy(),
                      block.merkle_tree.copy(), 
                      cb_tx.copy(), 
                      i, 
                      self.no_processes, 
                      self.target,
                      self.batch_size,
                      self.stop_flag
                      )
            )
            proc.start()
            print('process started!')
            self.processes.append(proc)
        
        self._mine_start_time = time.time()
        self._last_hash_report = time.time()

        self.is_mining = True
        print(self.stop_flag.value)
        while not self.stop_flag.value:
            status, value = self.result_queue.get()
            
            if status == 0:
                # Hash counter
                self._hash_counter += value
                self._total_hashes += value
                self._report_counter += 1
            elif status == 1:
                # Found nonce
                # print(f"Block mined after {self._total_hashes} hashes")
                # t = time.time() - self._mine_start_time
                # print(f"Time taken: {t:.2f}")
                # print(f"Avg hashrate: {format_hashrate(self._total_hashes / t)}")
                self.shutdown()
                
                sig_nonce, nonce = value
                with self.nonce.get_lock():
                    self.nonce.value = nonce
                    
                with self.sig_nonce.get_lock():
                    self.sig_nonce.value = sig_nonce
                    
                self.mined.set()
                
                # 
                # cb_tx = build_coinbase_tx(sig_nonce, self.outputs)
                # self.block.add_tx(cb_tx)
                # self.block.nonce = nonce
                # return self.block
            
            elif status == 2: # No result
                pass
            
            # Moderate batch_size ever 0.5s
            now = time.time()
            # print(now - self._last_hash_report)
            if (t_elapsed := now - self._last_hash_report) >= 0.5:
                print('hc', self._hash_counter)
                print('te', t_elapsed)
                hash_rate = self._hash_counter / t_elapsed
                print('hr', format_hashrate(hash_rate))
                report_rate = self._report_counter / t_elapsed
                print('rr', report_rate)
                self._record_hash_rate(hash_rate)
                self._moderate_reporting_rate(report_rate)
                self._last_hash_report = now
                self._report_counter = self._hash_counter = 0
                print()
        print("STOPPED MINING")
        
        
    def shutdown(self):
        with self.stop_flag.get_lock():
            self.stop_flag.value = 1
        
        APP_CONFIG.set("mining", "batch_size", self.batch_size.value)
        print("shutdown initiated")
        for proc in self.processes:
            proc.terminate()
            
        log.info("All miner processes terminated.")
        print("finish join")
        self.processes = [] 
        self._recent_hash_rates = []
        self._mine_end_time = time.time()
        self.is_mining = False
        
    
    def get_hashrate(self) -> float:
        """Returns a moving average of the 5 latest reported hashrates"""        
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
            
    def _moderate_reporting_rate(self, report_rate):    
        """Moderates Miner.batch size and consequently the hashrate report rate to a self._desired_report_rate"""
        # (1) Batch Size           * Report rate               = Hash rate
        # (2) Moderated Batch Size * self._desired_report_rate = Hash rate
        # (1) = (2), so
        # Moderated Batch Size = Batch Size * Report rate / self._desired_report_rate
 
        with self.batch_size.get_lock():
            self.batch_size.value = int(
                self.batch_size.value * (report_rate / self._desired_report_rate)
            )
            
        
        

def miner(
    queue: Queue, 
    header: Header,
    merkle_tree: MerkleTree, 
    cb_tx: Transaction,
    start_nonce: int, 
    step: int, 
    target: int,
    v_batch,
    v_stop_flag,
    ):
    """Worker function for block mining. Designed for standard coinbase transactions only (see `build_coinbase_tx`)"""
    hash_count = 0
    batch = v_batch.value
    
    try:
        for sig_nonce in range(1 << 64):
            cb_tx.inputs[0].script_sig = Script([int_to_bytes(sig_nonce, 64)])
            merkle_tree.update_leaf(0, cb_tx.hash())
            header.set_merkle_root(merkle_tree.root())
        
            p_head = header.serialize_without_nonce()

            for n in range(start_nonce, 1 << 32, step):
                
                raw_header = p_head + int_to_bytes(n)
                h = HASH256(raw_header)
                v = bytes_to_int(h)
                
                hash_count += 1
                if hash_count >= batch:
                    batch = v_batch.value
                    if v_stop_flag.value:
                        # print("worker stopped")
                        return
                    queue.put((0, hash_count))
                    hash_count = 0
                    
                if v < target:
                    print("nonce found!")
                    if hash_count > 0:
                        queue.put((0, hash_count))
                    queue.put((1, (sig_nonce, n)))
            
        # No success
        if hash_count > 0:
            queue.put((0, hash_count))
            
    except KeyboardInterrupt:  # To prevent KeyboardInterrupt errors from hashlib to flood the terminal
        return
            



def build_coinbase_tx(sig_nonce: int, outputs: list[TransactionOutput]) -> Transaction:
    """Standard Coinbase Transaction constructor, whereby scriptSig is used solely for extra mining space with a 64bit integer."""
    script_sig = Script([int_to_bytes(sig_nonce, 64)])
    
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
