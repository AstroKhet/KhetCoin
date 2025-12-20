from multiprocessing import Process, Value, cpu_count
from ctypes import c_ubyte
import os
import threading

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
        for _ in range(self.no_processes):
            proc = Process(
                target=key_generator,
                args=(prefix, self.v_private_key, self.stop_flag)
            )
            proc.start()
            self._gen_processes.append(proc)
    
        
        while not self.stop_flag.value:
            continue
        
        if bytes(self.v_private_key[:]) != bytes(32):
            self.shutdown()
            self.private_key = bytes(self.v_private_key[:])
    
    def shutdown(self):
        self.private_key = None
        with self.stop_flag.get_lock():
            self.stop_flag.value = 1
        
        for proc in self._gen_processes:
            proc.terminate()
            
def key_generator(prefix, v_private_key_raw, v_stop_flag):
    
    while True:
        if v_stop_flag.value:
            return
        
        priv_key_bytes = os.urandom(32)
        wif = private_key_to_wif(priv_key_bytes)

        if wif[1:].startswith(prefix):
            with v_private_key_raw.get_lock():
                v_private_key_raw[:] = priv_key_bytes
            with v_stop_flag.get_lock():
                v_stop_flag.value = 1
                
        
    
    

            
        