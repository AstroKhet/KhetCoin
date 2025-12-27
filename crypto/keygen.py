
from multiprocessing import Process, Queue, Value, cpu_count
from ctypes import c_ubyte
import os
import threading
import time

from crypto.key import private_key_to_wif


class KeyGenerator:
    
    def __init__(self, processes=None):
        self.cpu_count = cpu_count()
        if processes is None:
            self.no_processes = self.cpu_count
        else:
            self.no_processes = processes
            
            
        self.v_private_key = Value(c_ubyte * 32)
        
        self._gen_thread = None
        self._gen_processes = []
        self.stop_flag = Value('B', 1)
        
        self.private_key = None
        
    def generate(self, prefix=""):
        with self.stop_flag.get_lock():
            self.stop_flag.value = 0
            
        self.private_key = None
        
        self._gen_thread = threading.Thread(
            target=self._initiate_generators,
            args=(prefix,),
            daemon=True
        )
        self._gen_thread.start()
        
    def _initiate_generators(self, prefix):
        result_queue = Queue() 
        
        with self.v_private_key.get_lock():
            for i in range(32): self.v_private_key[i] = 0

        for _ in range(self.no_processes):
            proc = Process(
                target=key_generator,
                args=(prefix, result_queue, self.stop_flag) # Pass the queue
            )
            proc.start()
            self._gen_processes.append(proc)

        # Blocks until a key is found OR shutdown is called
        status, key_found = result_queue.get() 
    
        if status == 0:
            return    
        elif status == 1: # Key found
            self.private_key = key_found
            self.shutdown()
            
    def shutdown(self):
        with self.stop_flag.get_lock():
            self.stop_flag.value = 1
        
        for proc in self._gen_processes:
            proc.join()
        self._gen_processes = []


def key_generator(prefix, queue, v_stop_flag):
    while not v_stop_flag.value:
        priv_key_bytes = os.urandom(32)
        wif = private_key_to_wif(priv_key_bytes)

        if wif[1:].startswith(prefix):
            try:
                queue.put_nowait((1, priv_key_bytes))
            except:
                pass
            return
    
    queue.put_nowait((0, None))
        
                
        
    
    

            
        