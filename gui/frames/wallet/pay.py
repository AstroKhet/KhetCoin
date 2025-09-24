from cgitb import text
import select
import tkinter as tk
from tkinter import Spinbox, ttk

import logging

from blockchain.constants import TXN_VERSION
from blockchain.script import Script, P2PKH_script_pubkey
from blockchain.transaction import Transaction, TransactionInput, TransactionOutput, get_utxo_addr_value
from crypto.key import get_private_key, wif_decode, wif_encode
from db.utxo import get_utxo_set
from gui.bindings import bind_entry_prompt
from gui.helper import copy_to_clipboard
from ktc_constants import KTC
from networking.node import Node
from wallet.algorithm import get_recommended_fee_rate, select_utxos

log = logging.getLogger(__name__)


class PayFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node

        # 1. Receipient list
        self.recipient_frames = dict()
        self.lf_recipients = tk.LabelFrame(self, text="Recipients")
        self.lf_recipients.pack(side="top", fill="both", expand=True, padx=10, pady=5)

        self.cnv_recipients = tk.Canvas(self.lf_recipients, highlightthickness=0)
        self.vsb_recipients = ttk.Scrollbar(self.lf_recipients, orient="vertical", command=self.cnv_recipients.yview)
        self.frame_recipients_inner = tk.Frame(self.cnv_recipients)
        self.cnv_recipients.configure(yscrollcommand=self.vsb_recipients.set)
        self.vsb_recipients.pack(side="right", fill="y")
        self.cnv_recipients.pack(side="left", fill="both", expand=True)
        self.cnv_recipients_window = self.cnv_recipients.create_window((0, 0), window=self.frame_recipients_inner, anchor="nw")
        
        self.frame_recipients_inner.bind(
            "<Configure>",
            lambda _: self.cnv_recipients.configure(scrollregion=self.cnv_recipients.bbox("all"))
        )
        self.cnv_recipients.bind(
            "<Configure>", 
            lambda e: self.cnv_recipients.itemconfig(self.cnv_recipients_window, width=e.width)
        )

        # 2. Fee selection menu
        self.frame_fee = tk.LabelFrame(self, text="Transaction Fee")
        self.frame_fee.pack(side="top", fill="x", padx=10, pady=5)
        self.frame_fee.columnconfigure(1, weight=1)
        self.frame_fee.columnconfigure(3, weight=3)

        self.fee_choice_var = tk.StringVar(self, value="recommended")

        self.rb_fee_recommended = tk.Radiobutton(self.frame_fee, text="Recommended", variable=self.fee_choice_var, value="recommended", command=self._update_fee_widgets_state)
        self.rb_fee_recommended.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.fee_recommended = get_recommended_fee_rate(node.mempool.get_mempool(), 6)
        self.label_fee_recommended_value = tk.Label(self.frame_fee, text=f"{self.fee_recommended} khets/KB")
        self.label_fee_recommended_value.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.var_wait_blocks = tk.IntVar(value=6)
        self.var_wait_blocks.trace_add("write", self._update_recommended_fee)
        self.spinbox_wait_blocks = tk.Spinbox(self.frame_fee, from_=1, to=float('inf'), increment=1, textvariable=self.var_wait_blocks)
        self.spinbox_wait_blocks.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        self.rb_fee_custom = tk.Radiobutton(self.frame_fee, text="Custom", variable=self.fee_choice_var, value="custom", command=self._update_fee_widgets_state)
        self.rb_fee_custom.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.var_fee_custom = tk.DoubleVar(value=0.0)
        self.spinbox_custom_fee = tk.Spinbox(self.frame_fee, from_=0, to=float('inf'), increment=0.01, textvariable=self.var_fee_custom, format="%.8f")
        self.spinbox_custom_fee.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.var_fee_unit = tk.StringVar(value="KTC")
        self.var_fee_unit.trace_add("write", lambda *_, val=self.var_fee_custom, unit=self.var_fee_unit, sb=self.spinbox_custom_fee: self._unit_conversion(val, unit, sb))
        self.om_fee_custom_unit = ttk.OptionMenu(self.frame_fee, self.var_fee_unit, "KTC", "khets", "KTC")
        self.om_fee_custom_unit.grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.label_fee_per_kb = tk.Label(self.frame_fee, text="per KB")
        self.label_fee_per_kb.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # 3. Options footer 
        self.frame_options = tk.Frame(self)
        self.frame_options.pack(side="bottom", fill="x", padx=10, pady=(5, 10))

        self.btn_send = ttk.Button(self.frame_options, text="Send", command=self._send_txn_window)
        self.btn_send.pack(side="left", padx=2)
        self.btn_add_recipient = ttk.Button(self.frame_options, text="Add Recipient", command=self._add_recipient_block)
        self.btn_add_recipient.pack(side="left", padx=2)
        self.btn_clear_all = ttk.Button(self.frame_options, text="Remove All", command=self._remove_all_blocks)
        self.btn_clear_all.pack(side="left", padx=2)

        balance_val = get_utxo_addr_value(self.node.pk_hash) / KTC
        self.btn_wallet = ttk.Button(self.frame_options, text="Wallet", command=lambda: self.controller.switch_to_frame("wallet"))
        self.btn_wallet.pack(side="right", padx=2)
        self.label_balance = tk.Label(self.frame_options, text=f"Balance: {balance_val:.8f} KTC")
        self.label_balance.pack(side="right", padx=2)

        self._add_recipient_block()
        self._update_fee_widgets_state()

    def _add_recipient_block(self):
        row_index = len(self.recipient_frames)
        frame_recipient = tk.Frame(self.frame_recipients_inner, borderwidth=1, relief="solid")
        frame_recipient.grid(row=row_index, column=0, sticky="ew", pady=5)
        self.frame_recipients_inner.columnconfigure(0, weight=1)
        frame_recipient.columnconfigure(1, weight=1)
        frame_recipient.columnconfigure(2, weight=1)

        label_pay_to = tk.Label(frame_recipient, text="Pay to")
        label_pay_to.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        entry_address = tk.Entry(frame_recipient)
        entry_address.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="ew")
        bind_entry_prompt(entry_address, "Khetcoin address (e.g. 1Ke23Hje6GoSoDVbgR6kyWRrNhubvGCkw2)")
        btn_contacts = ttk.Button(frame_recipient, text="Contacts")
        btn_contacts.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        btn_delete = ttk.Button(frame_recipient, text="Delete", command=lambda b=frame_recipient: self._remove_recipient_block(b))
        btn_delete.grid(row=0, column=4, padx=5, pady=2, sticky="w")

        label_value = tk.Label(frame_recipient, text="Amount")
        label_value.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        var_value = tk.DoubleVar(value=0.0)
        spinbox_amount = tk.Spinbox(frame_recipient, from_=0, to=float('inf'), increment=0.01, textvariable=var_value, format="%.8f")
        spinbox_amount.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        var_unit = tk.StringVar(value="KTC")
        var_unit.trace_add("write", lambda *_, val=var_value, unit=var_unit, sb=spinbox_amount: self._unit_conversion(val, unit, sb))
        om_unit = ttk.OptionMenu(frame_recipient, var_unit, "KTC", "khets", "KTC")
        om_unit.grid(row=1, column=2, padx=5, pady=2, sticky="w")
        
        frame_subtract_option = tk.Frame(frame_recipient)
        frame_subtract_option.grid(row=1, column=3, columnspan=2, padx=5, pady=2, sticky="w")
        var_subfromvalue = tk.BooleanVar(value=False)
        cb_subtract_fee = tk.Checkbutton(frame_subtract_option, text="Subtract fee from value", variable=var_subfromvalue, onvalue=True, offvalue=False)
        cb_subtract_fee.pack(side="left")
        
        recipient_widgets = {
            "addr": entry_address,
            "value": var_value,
            "unit": var_unit,
            "sub": var_subfromvalue,
        }
        self.recipient_frames[frame_recipient] = recipient_widgets

    def _remove_recipient_block(self, recipient_frame: tk.Frame):
        recipient_frame.destroy()
        self.recipient_frames.pop(recipient_frame, None)
        
        if not self.recipient_frames:
            self._add_recipient_block()  # At least one blank one

    def _remove_all_blocks(self):
        for block in self.recipient_frames:
            block.destroy()
        self.recipient_frames.clear()
        self._add_recipient_block()

    def _update_recommended_fee(self, *_):
        wait_blocks = self.var_wait_blocks.get()
        self.fee_recommended = get_recommended_fee_rate(self.node.mempool.get_mempool(), wait_blocks)
        self.label_fee_recommended_value.config(text=f"{self.fee_recommended} khets/KB")
        
    def _update_fee_widgets_state(self):
        choice = self.fee_choice_var.get()
        if choice == "recommended":
            self.label_fee_recommended_value.config(fg="black")
            self.spinbox_custom_fee.config(state="disabled")
            self.om_fee_custom_unit.config(state="disabled")
            self.label_fee_per_kb.config(fg="gray")
            self.spinbox_wait_blocks.config(state="normal")
        else:
            self.label_fee_recommended_value.config(fg="gray")
            self.spinbox_custom_fee.config(state="normal")
            self.om_fee_custom_unit.config(state="normal")
            self.label_fee_per_kb.config(fg="black")
            self.spinbox_wait_blocks.config(state="disabled")
            
    def _unit_conversion(self, var_value, var_unit: tk.StringVar, sb: tk.Spinbox):
        unit = var_unit.get()
        if unit == "KTC":   # khets -> KTC
            sb.config()
            var_value.set(var_value.get() / KTC)
            sb.config(increment=0.01, format="%.8f", textvariable=var_value)
        elif unit == "khets":  # KTC to khets
            var_value.set(var_value.get() * KTC)
            sb.config(increment=1, format="%.0f", textvariable=var_value)
            
    def _get_fee_rate(self):
        choice = self.fee_choice_var.get()
        if choice == "recommended":
            return get_recommended_fee_rate(self.node.mempool.get_mempool())
        else:
            fee = self.var_fee_custom.get()
            if self.var_fee_unit.get() == "KTC":
                fee *= KTC
            return fee
        
    def _generate_txn(self) -> Transaction | None:
        sfv_value, op_value = 0, 0
        for output_fields in self.recipient_frames.values():
            value = output_fields["value"].get()
            unit = output_fields["unit"].get()
            sub = output_fields["sub"].get()
            if unit == "KTC":
                    value *= KTC
            sfv_value += int(sub * value)
            op_value += int(value)
                
        outputs = []
        for frame_recipient, output_fields in self.recipient_frames.items():
            pk_hash = wif_decode(output_fields["addr"].get())
            value = output_fields["value"].get()
            unit = output_fields["unit"].get()
            sub = output_fields["sub"].get()
            
            if not pk_hash:  
                # Simple feedback for incorrect address. 
                # TODO: Better error feedbacking
                frame_recipient.config(bg="pink")
                return
            
            if unit == "KTC":
                value *= KTC
            
            #P2PKH
            outputs.append(
                TransactionOutput(
                    value=int(value),
                    script_pubkey=P2PKH_script_pubkey(pk_hash)
                )
            )
        
        # UTXO Selection 
        utxo_set = get_utxo_set(self.node.pk_hash)
        utxo_value = sum(utxo.value for utxo in utxo_set)

        if op_value > utxo_value:
            log.warning("You cannot pay more than what you currently have!")
            return None

        n_input_guess, max_iterations = 1, 5
        inputs, utxos = [], []

        for _ in range(max_iterations):
            # Estimate fee based on guessed number of inputs
            fee = self._get_fee_rate() * n_input_guess
            target = op_value + fee

            if target > utxo_value:
                log.warning("Insufficient funds to cover amount + estimated fee!")
                log.info(f"Reduce fee to {fee - (target - utxo_value)} khets to continue")
                return None

            utxos = select_utxos(utxo_set, target)
            if not utxos:
                log.warning("Error in selecting UTXOs.")
                return None

            n_inputs_actual = len(utxos)
            if n_inputs_actual == n_input_guess:
                break
            n_input_guess = n_inputs_actual

        for utxo in utxos:
            inputs.append(TransactionInput(
                prev_hash=utxo.txn_hash,
                prev_index=utxo.index,
                script_sig=Script([]),
                sequence=0xffffffff
            ))
            
        txn = Transaction(
            version=TXN_VERSION,
            inputs=inputs,
            outputs=outputs,
            locktime=0
        )
        
        txn.sign(get_private_key(self.node.name, raw=False)) # type: ignore
        return txn
    
    
    def _send_txn_window(self):
        win_txn_summary = tk.Toplevel(self)
        win_txn_summary.title("Confirm Transaction")
        win_txn_summary.geometry("300x400")
        
        # 1. Scrollable frame for viewing txn summary
        frame_txn_summary = tk.Frame(win_txn_summary)
        frame_txn_summary.grid(row=0, column=0, sticky="nsew")
        frame_txn_summary.columnconfigure(0, weight=1)
        frame_txn_summary.rowconfigure(0, weight=1)

        cnv_txn_summary = tk.Canvas(frame_txn_summary, highlightthickness=0)
        cnv_txn_summary.grid(row=0, column=0, sticky="nsew")
        
        vsb_txn_summary = ttk.Scrollbar(frame_txn_summary, orient="vertical", command=cnv_txn_summary.yview)
        vsb_txn_summary.grid(row=0, column=1, sticky="ns")
        hsb_txn_summary = ttk.Scrollbar(frame_txn_summary, orient="horizontal", command=cnv_txn_summary.xview)
        hsb_txn_summary.grid(row=1, column=0, sticky="ew")

        cnv_txn_summary.configure(yscrollcommand=vsb_txn_summary.set, xscrollcommand=hsb_txn_summary.set)
        
        frame_txn_details = tk.Frame(cnv_txn_summary)
        frame_txn_details.columnconfigure(0, weight=1)

        win_id_txn_details = cnv_txn_summary.create_window((0, 0), window=frame_txn_details, anchor="nw")

        cnv_txn_summary.bind(
            "<Configure>",
            lambda e: cnv_txn_summary.itemconfig(win_id_txn_details, width=e.width)
        )
        frame_txn_details.bind(
            "<Configure>",
            lambda _: cnv_txn_summary.configure(scrollregion=cnv_txn_summary.bbox("all"))
        )
        
        # 2. Content for txn summary window
        txn = self._generate_txn()
        if txn is None:
            label_err = tk.Label(frame_txn_summary, text="Error creating transaction. See console log.")
            label_err.pack()
            return
        
        # Copied from /gui/frames/blockchain/view_blockchain.py
        frame_txn_io = tk.Frame(frame_txn_summary)
        frame_txn_io.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_txn_io.columnconfigure(0, weight=1, uniform="txnio_cols")
        frame_txn_io.columnconfigure(1, weight=1, uniform="txnio_cols")

        # Headers
        tk.Label(frame_txn_io, text="From", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=0, sticky="w")
        tk.Label(frame_txn_io, text="To", font=("Arial", 10, "bold"), padx=5, pady=5).grid(row=0, column=1, sticky="w")

        for i, tx_in in enumerate(txn.inputs, start=1):
            script_sig = tx_in.script_sig
            script_pk = tx_in.script_pubkey()
            if txn.is_coinbase():
                addr = "Coinbase"
            else:
                addr = script_sig.get_script_sig_sender() or "N/A"
            value = tx_in.value() or 0

            frame_input = tk.Frame(frame_txn_io)
            frame_input.grid(row=i, column=0, sticky="we", padx=2, pady=2)
            frame_input.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_input, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_input, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(self, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_input, text="Script", width=6,
                    command=lambda sig=script_sig, pk=script_pk: self._show_script_window(sig, pk)
            ).grid(row=0, column=2)

            tk.Label(frame_input, text=f"{value/KTC:.8f}KTC", fg="gray").grid(row=1, column=0, sticky="w")

        # Outputs
        for i, tx_out in enumerate(txn.outputs, start=1):
            script_pk = tx_out.script_pubkey
            value = tx_out.value
            addr = script_pk.get_script_pubkey_receiver() or "N/A"

            frame_output = tk.Frame(frame_txn_io)
            frame_output.grid(row=i, column=1, sticky="we", padx=2, pady=2)
            frame_output.columnconfigure(0, weight=1)

            wif_addr = wif_encode(addr)
            tk.Label(frame_output, text=f"{i}. {wif_addr}").grid(row=0, column=0, sticky="w")
            ttk.Button(frame_output, text="Copy", width=5,
                    command=lambda a=wif_addr: copy_to_clipboard(self, a)
            ).grid(row=0, column=1)
            ttk.Button(frame_output, text="Script", width=6,
                    command=lambda pk=script_pk: self._show_script_window(script_pubkey=pk)
            ).grid(row=0, column=2)

            tk.Label(frame_output, text=f"{value/KTC:.8f}KTC", fg="gray").grid(row=1, column=0, sticky="w")
        pass

    def _show_script_window(self, script_sig: Script | None=None, script_pubkey: Script | None=None):
        # Copied from /gui/frames/blockchain/view_blockchain.py
        win_script = tk.Toplevel(self)
        win_script.title(f"Script for Transaction {truncate_bytes(self.selected_txn.hash())}") # type: ignore
        win_script.geometry("300x200")
        
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