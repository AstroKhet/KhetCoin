"""Validator commands for GUI text input"""
import re
import string

from ktc_constants import KTC
from math import isclose

def register_VCMD_INT(parent):
    VCMD_INT = (parent.register(lambda P: P.isdigit() or P==""), "%P")
    return VCMD_INT


def register_VMCD_KTC(parent):
    VCMD_KTC = (parent.register(_validate_KTC), "%P")
    return VCMD_KTC
    

def register_VCMD_filename(parent):
    VCMD_FILE = (parent.register(filename_vcmd), "%P")
    return VCMD_FILE

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def register_VCMD_wif_prefix(parent):
    VCMD_b58 = (parent.register(lambda P: (len(P) <= 4) and all(c in BASE58_ALPHABET for c in P)), "%P")
    return VCMD_b58

    
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


_filename_chars = f"-_.() {string.ascii_letters}{string.digits}"
def filename_vcmd(new_value: str) -> bool:
    """
    Validate input for a filename entry:
    - Empty string is allowed
    - Only valid filename characters
    - Maximum length 40
    """
    if new_value == "":
        return True

    if len(new_value) > 40:
        return False

    # Check if all characters are valid
    if all(c in _filename_chars for c in new_value):
        return True

    return False