# Specialized file for coin selection algorithms


from blockchain.transaction import Transaction
from db.utxo import UTXO
from ktc_constants import MAX_BLOCK_SIZE
from mining.constants import MIN_RELAY_TX_FEE
from wallet.constants import MIN_CHANGE


def select_utxos(utxo_set: list[UTXO], target, use_min_change = True) -> list[UTXO] | None:
    """
    Provides a list of UTXO objects where its total value satisfy any of the following:
    
    If `use_min_change` = False
    1. Is >= `target`
    
    If `use_min_change` = True
    1. Is exactly equal to `target`
    2. Is >= to target 
    3. Tries again with `use_min_change` = False if this allows UTXO set value >= target at least.
    """
    min_change = MIN_CHANGE if use_min_change else 0
    total_utxo = sum(utxo.value for utxo in utxo_set)
    
    # 0. Sanity checks
    # 0.1 Check if target is even affordable
    if total_utxo < target:
        return None
    
    # 0.2 Check if total utxo amount exactly equals target (rare; in this case we don't need change at all)
    if total_utxo == target:
        return utxo_set
    
    # 0.3 Otherwise, if we can afford target but not target + min_change, forgo min_change and select again
    if use_min_change and target < total_utxo < target + min_change:
        return select_utxos(utxo_set, target, use_min_change=False)

    # 1 UTXO filtering
    # 1.1 Sort UTXOs based on value in ascending order
    utxo_set.sort(key=lambda utxo: utxo.value)
    total_small = 0
    smaller, larger = [], []
    
    # 1.2 Filter UTXOs based on if their value exceeds target
    for utxo in utxo_set:
        if utxo.value < target:
            smaller.append(utxo)
            total_small += utxo.value
        elif utxo.value > target:
            larger.append(utxo)
        else: # Exact match
            return [utxo]
    
    # 1.3 See if any 'larger' UTXO can fully cover target + min_change by itself
    for l_utxo in larger:
        if l_utxo.value >= target + min_change:
            return [l_utxo]
    
    # 1.4 See if all 'smaller' UTXO can fully cover target + min_change. 
    #     This is a preliminary check to see if we need and 'larger' UTXO in our final UTXO selection
    total, selected = 0, []
    if total_small < target + min_change:
        total, selected = larger[-1].value, [larger[-1]]

    # 1.5 Collect the smaller UTXOs in ascending order, until either condition is met (exact match or >= target + min_change)
    for s_utxo in smaller:
        total += s_utxo.value
        selected.append(s_utxo)
        if total == target:
            return min_change
        elif total >= target + min_change:
            return selected
    
    # 1.6 In the rare case where total_small + largest utxo != target and < target + min_change
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
