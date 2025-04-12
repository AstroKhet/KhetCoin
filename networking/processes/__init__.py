from .process_tx import process_tx



CORE_PROCESSES = [
    process_tx,
]

__all__ = [
    "process_tx",
]

PROCESS_MAP = {proc.__name__: proc for proc in CORE_PROCESSES}