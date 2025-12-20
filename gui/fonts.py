import tkinter.font as font

from utils.config import APP_CONFIG


_MONO_FAMILY = APP_CONFIG.get("font", "mono")
_SANS_FAMILY = APP_CONFIG.get("font", "sans")

# Font helpers
def MonoFont(size=10, **kwargs):
    """Monospace font for keys, hex, console-like text."""
    return font.Font(family=_MONO_FAMILY, size=size, **kwargs)

def SansFont(size=10, **kwargs):
    """Sans-serif font for general UI text."""
    return font.Font(family=_SANS_FAMILY, size=size, **kwargs)
