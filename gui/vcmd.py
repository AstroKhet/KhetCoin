"""Validator commands for GUI text input"""
import re

from ktc_constants import KTC
from math import isclose

def register_VCMD_INT(parent):
    VCMD_INT = (parent.register(lambda P: P.isdigit() or P==""), "%P")
    return VCMD_INT


def register_VMCD_KTC(parent):
    VCMD_KTC = (parent.register(_validate_KTC), "%P")
    return VCMD_KTC
    
    
# Auxillary functions

_real_re = re.compile(r'^\d*\.?\d*$')
def _validate_KTC(new):
    if new == "" or new == ".":
        return True
    if not _real_re.match(new):
        return False

    try:
        val = float(new)
    except ValueError:
        return False
    
    val_khets = val * KTC
    return isclose(val_khets, round(val_khets), rel_tol=0.0, abs_tol=1e-3)  # To deal with floating point precision error
