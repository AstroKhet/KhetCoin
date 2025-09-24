# Specialized file for coin selection algorithms


from blockchain.transaction import Transaction
from db.utxo import UTXO
from ktc_constants import MAX_BLOCK_SIZE
from mining.constants import MIN_RELAY_TX_FEE
from wallet.constants import MIN_CHANGE


def select_utxos(utxo_set: list[UTXO], target, use_min_change = True) -> list[UTXO] | None:
    min_change = MIN_CHANGE if use_min_change else 0

    total_utxo = sum(utxo.value for utxo in utxo_set)
    if total_utxo < target:
        return None
    
    if total_utxo == target:
        return utxo_set
    
    if use_min_change and target < total_utxo < target + min_change:
        return select_utxos(utxo_set, target, use_min_change=False)

    utxo_set.sort(key=lambda utxo: utxo.value)
    total_small = 0
    smaller, larger = [], []
    
    for utxo in utxo_set:
        if utxo.value < target:
            smaller.append(utxo)
            total_small += utxo.value
        elif utxo.value > target:
            larger.append(utxo)
        else: # Exact match
            return [utxo]
        
    for l_utxo in larger:
        if l_utxo.value >= target + min_change:
            return [l_utxo]
    
    total, selected = 0, []
    if total_small < target + min_change:
        total, selected = larger[-1].value, [larger[-1]]

    for s_utxo in smaller:
        total += s_utxo.value
        selected.append(s_utxo)
        if total >= target + min_change:
            return selected
    
    # In the rare case where total_small + largest utxo != target and < target + min_change
    return select_utxos(utxo_set, target, use_min_change=False)
        

def get_recommended_fee_rate(mempool: list[Transaction], wait_block = 1) -> int:
    mempool.sort(key = lambda txn: txn.fee() / txn.size(), reverse=True)
    
    size = 0
    for txn in mempool:
        size += txn.size()
        if size > wait_block * MAX_BLOCK_SIZE:
            return round(txn.fee() / txn.size())
    else:
        return MIN_RELAY_TX_FEE
