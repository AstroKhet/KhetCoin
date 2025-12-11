from hashlib import sha256
from multiprocessing import Process, Queue, cpu_count, Value
import os
import time

# Example pseudo target
target = 0xFFF * pow(256, 0x1F - 4)

# -----------------------------------------------------------
# Mining worker (one per CPU core)
# -----------------------------------------------------------
def miner(start, step, q):
    """
    Each miner searches a different subset of the [0, 1e12) space:
    nonce = start, start+step, start+2*step, ...
    Uses a local counter to avoid frequent locking
    """
    max_nonce = int(1e12)
    local_count = 0
    BATCH_SIZE = 100000  # adjust for frequency of reporting

    nonce = start
    while nonce < max_nonce:
        # Hash the nonce
        b = nonce.to_bytes(64, "big")
        h = sha256(b).digest()
        v = int.from_bytes(h, "big")

        local_count += 1

        # Update the queue every BATCH_SIZE hashes
        if local_count >= BATCH_SIZE:
            q.put(("HASHED", local_count))
            local_count = 0

        if v < target:
            # Send remaining local count before exiting
            if local_count > 0:
                q.put(("HASHED", local_count))
            q.put(("FOUND", nonce))
            return

        nonce += step

    # If finished without success, send remaining hashes
    if local_count > 0:
        q.put(("HASHED", local_count))
    q.put(("DONE", None))


# -----------------------------------------------------------
# Controller: spawn N miners in parallel
# -----------------------------------------------------------
def mine():
    cores = cpu_count()
    print(f"[Main] Starting mining on {cores} cores")

    result_queue = Queue()
    processes = []

    # Track start time
    start_time = time.time()
    total_hashes = 0

    # Spawn workers
    for i in range(cores):
        p = Process(
            target=miner,
            args=(i, cores, result_queue)
        )
        p.start()
        processes.append(p)

    last_report_time = start_time

    # Main loop: monitor results and calculate hash rate
    while True:
        # Wait for next message
        status, value = result_queue.get()

        if status == "HASHED":
            total_hashes += value

        elif status == "FOUND":
            print(f"\n[Main] Miner found nonce: {value}")
            # Stop all miners
            for p in processes:
                p.terminate()
            break

        elif status == "DONE":
            pass  # One worker finished its range without success

        # Print hash rate every 0.5 seconds
        now = time.time()
        if now - last_report_time >= 0.5:
            elapsed = now - last_report_time
            hr = total_hashes / elapsed
            print(f"[Main] Hashrate: {hr:.2f} H/s")
            total_hashes = 0
            last_report_time = now

    # Print total elapsed time
    end_time = time.time()
    print(f"[Main] Mining stopped. Total time: {end_time - start_time:.2f} seconds")


# -----------------------------------------------------------
if __name__ == "__main__":
    mine()
