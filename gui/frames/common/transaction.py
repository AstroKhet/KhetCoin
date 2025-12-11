"""Common GUI functions related to transactions"""
import tkinter as tk
from tkinter import ttk

from blockchain.script import Script
from blockchain.transaction import Transaction
from crypto.key import wif_encode
from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.frames.common.scrollable import create_scrollable_frame
from gui.helper import center_popup, copy_to_clipboard
from ktc_constants import KTC
from utils.fmt import format_bytes, truncate_bytes

def tx_popup(parent, tx: Transaction, type_: str):
        """
        type_ (str) : "orphan" | "valid"
        """
        win = tk.Toplevel(parent)
        win.title(f"{type_.capitalize()} Transaction")
        win.geometry("800x500")

        win.rowconfigure(0, weight=5, uniform="win_row")
        win.rowconfigure(1, weight=2, uniform="win_row")
        win.columnconfigure(0, weight=1)

        frame_main = tk.Frame(win, bg='blue')
        frame_main.grid(row=0, column=0, sticky="nsew")
        frame_main.columnconfigure(0, weight=1)
        frame_main.rowconfigure(0, weight=1)


        # 1. Full list of inputs and outputs
        frame_details, cnv_details = create_scrollable_frame(win, xscroll=False)
        frame_details.columnconfigure(0, weight=1)
        
        frame_tx_io = tk.Frame(frame_details)
        frame_tx_io.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame_tx_io.columnconfigure(0, weight=1, uniform="txio_cols")
        frame_tx_io.columnconfigure(1, weight=1, uniform="txio_cols")

        # Headers
        tk.Label(frame_tx_io, text="From", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=0, sticky="w")
        tk.Label(frame_tx_io, text="To", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=1, sticky="w")

        for i, tx_in in enumerate(tx.inputs, start=1):
            script_sig = tx_in.script_sig
            script_pk = tx_in.script_pubkey()
            if tx.is_coinbase():
                addr = "Coinbase"
            else:
                addr = script_sig.get_script_sig_sender() or "N/A"
            value = f"{tx_in.value()/KTC:.8f}KTC" if tx_in.value() is not None else "N/A"

            frame_input = tk.Frame(frame_tx_io)
            frame_input.grid(row=i, column=0, sticky="we", padx=2, pady=2)
            frame_input.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_input, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_input, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(parent, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_input, text="Script", width=6,
                    command=lambda sig=script_sig, pk=script_pk: script_popup(parent, sig, pk, tx.hash())
            ).grid(row=0, column=2)

            tk.Label(frame_input, text=value, fg="gray").grid(row=1, column=0, sticky="w")

        # Outputs
        for i, tx_out in enumerate(tx.outputs, start=1):
            script_pk = tx_out.script_pubkey
            value = tx_out.value
            addr = script_pk.get_script_pubkey_receiver() or "N/A"

            frame_output = tk.Frame(frame_tx_io)
            frame_output.grid(row=i, column=1, sticky="we", padx=2, pady=2)
            frame_output.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_output, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_output, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(parent, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_output, text="Script", width=6,
                    command=lambda pk=script_pk: script_popup(parent, script_pubkey=pk, tx_hash=tx.hash())
            ).grid(row=0, column=2)

            text = f"{value/KTC:.8f}KTC"
            if tx_out.is_change():
                text += " (change)"
            tk.Label(frame_output, text=text, fg="gray").grid(row=1, column=0, sticky="w")


        
        # 2. Transaction Summary
        lf_meta = ttk.LabelFrame(win, text="Summary")
        lf_meta.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        lf_meta.columnconfigure(0, weight=1)
        lf_meta.columnconfigure(1, weight=1)

        # Left frame (inputs, outputs, size)
        frame_meta_left = tk.Frame(lf_meta)
        frame_meta_left.columnconfigure(0, weight=1)
        frame_meta_left.columnconfigure(1, weight=1)
        frame_meta_left.grid(row=0, column=0, sticky="nsew", padx=10)

        if type_ == "valid":
            tk.Label(frame_meta_left, text="Input value:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_meta_left, text=f"{tx.input_value()/KTC:.8f} KTC").grid(row=0, column=1, sticky="e")
        elif type_ == "orphan":
            tk.Label(frame_meta_left, text="Input value:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_meta_left, text=f"N/A").grid(row=0, column=1, sticky="e")

        tk.Label(frame_meta_left, text="Output value:").grid(row=1, column=0, sticky="w")
        tk.Label(frame_meta_left, text=f"{tx.output_value(exclude_change=True)/KTC:.8f} KTC").grid(row=1, column=1, sticky="e")  
            
        if type_ == "valid":
            tk.Label(frame_meta_left, text="Change value:").grid(row=2, column=0, sticky="w")
            tk.Label(frame_meta_left, text=f"{tx.change_value()/KTC:.8f} KTC").grid(row=2, column=1, sticky="e")
            
        elif type_ == "orphan":
            tk.Label(frame_meta_left, text="Change value:").grid(row=2, column=0, sticky="w")
            tk.Label(frame_meta_left, text=f"N/A").grid(row=2, column=1, sticky="e")

        tx_size = len(tx.serialize())
        tk.Label(frame_meta_left, text="Transaction size:").grid(row=3, column=0, sticky="w")
        tk.Label(frame_meta_left, text=format_bytes(tx_size)).grid(row=3, column=1, sticky="e")
            
        # Right frame (fees)
        frame_meta_right = tk.Frame(lf_meta)
        frame_meta_right.columnconfigure(0, weight=1)
        frame_meta_right.columnconfigure(1, weight=1)
        frame_meta_right.grid(row=0, column=1, sticky="nsew", padx=10)

        total_fee = tx.fee()
        if total_fee is not None:
            tk.Label(frame_meta_right, text="Total fee:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_meta_right, text=f"{total_fee / KTC:.8f} KTC").grid(row=0, column=1, sticky="e")

            fee_rate = total_fee / tx_size if tx_size > 0 else 0
            tk.Label(frame_meta_right, text="Fee rate:").grid(row=1, column=0, sticky="w")
            tk.Label(frame_meta_right, text=f"{fee_rate * 1024:.2f} khets/KB").grid(row=1, column=1, sticky="e")
        else:
            tk.Label(frame_meta_right, text="Total fee:").grid(row=0, column=0, sticky="w")
            tk.Label(frame_meta_right, text=f"N/A").grid(row=0, column=1, sticky="e")

            tk.Label(frame_meta_right, text="Fee rate:").grid(row=1, column=0, sticky="w")
            tk.Label(frame_meta_right, text=f"N/A").grid(row=1, column=1, sticky="e")   
    
        bind_hierarchical("<MouseWheel>", frame_main, lambda e: mousewheel_cb(e, cnv_details))
        return win
    
def script_popup(parent, script_sig: Script | None=None, script_pubkey: Script | None=None, tx_hash: bytes = None):
    # Copied from /gui/frames/blockchain/view_blockchain.py
    win_script = tk.Toplevel(parent)
    if tx_hash:
        win_script.title(f"Script for Transaction {truncate_bytes(tx_hash)}") 
    else:
        win_script.title(f"Script")
        
    win_script.geometry("300x200")
    win_script.transient(parent)
    center_popup(parent, win_script)
    
    frame_script = tk.Frame(win_script, padx=10, pady=10)
    frame_script.pack(fill="both", expand=True)

    if script_sig is not None:
        label_sig = tk.Label(frame_script, text="ScriptSig", font=("Arial", 10, "bold"), anchor="w")
        label_sig.pack(fill="x", pady=(0, 2))

        txt_sig = tk.Text(frame_script, wrap="word", height=6)
        txt_sig.insert("1.0", str(script_sig))
        txt_sig.config(state="disabled")
        txt_sig.pack(fill="both", expand=True, pady=(0, 10))

    if script_pubkey is not None:
        label_pk = tk.Label(frame_script, text="ScriptPubkey", font=("TkDefaultFont", 10, "bold"), anchor="w")
        label_pk.pack(fill="x", pady=(0, 2))

        txt_pk = tk.Text(frame_script, wrap="word", height=6)
        txt_pk.insert("1.0", str(script_pubkey))
        txt_pk.config(state="disabled")
        txt_pk.pack(fill="both", expand=True)
        
    return win_script