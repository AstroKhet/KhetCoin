from math import ceil
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

import logging

from blockchain.constants import TX_VERSION, P2PKH_INPUT_SIZE, P2PKH_OUTPUT_SIZE
from blockchain.script import Script, P2PKH_script_pubkey
from blockchain.transaction import Transaction, TransactionInput, TransactionOutput
from crypto.key import get_private_key, wif_decode
from db.addr import get_addr_utxos, get_addr_utxos_value
from gui.bindings import bind_entry_prompt
from gui.frames.common.scrollable import create_scrollable_frame, create_scrollable_treeview
from gui.frames.common.transaction import tx_popup
from gui.vcmd import register_VCMD_INT, register_VMCD_KTC
from gui.helper import center_popup
from ktc_constants import KTC, MAX_KHETS
from networking.messages.envelope import MessageEnvelope
from networking.messages.types.inv import InvMessage
from networking.node import Node
from utils.config import APP_CONFIG
from utils.helper import encode_varint
from wallet.algorithm import get_recommended_fee_rate, select_utxos
from wallet.constants import MIN_CHANGE

log = logging.getLogger(__name__)


class PayFrame(tk.Frame):
    def __init__(self, parent, controller, node: Node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        
        # 0. Spinbox value input validator commands
        self.vcmd_khets = register_VCMD_INT(self)
        self.vcmd_KTC = register_VMCD_KTC(self)

        # 1. Receipient list
        self.recipient_frames = dict()
        self.lf_recipients = tk.LabelFrame(self, text="Recipients")
        self.lf_recipients.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.frame_recipients, self.cnv_recipients = create_scrollable_frame(self, xscroll=False)
        self.frame_recipients.columnconfigure(0, weight=1)

        # 2. Fee selection menu
        self.frame_fee = tk.LabelFrame(self, text="Transaction Fee")
        self.frame_fee.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.frame_fee.columnconfigure(1, weight=1)
        self.frame_fee.columnconfigure(3, weight=3)

        self.fee_choice_var = tk.StringVar(self, value="recommended")

        self.rb_fee_recommended = tk.Radiobutton(self.frame_fee, text="Recommended", variable=self.fee_choice_var, value="recommended", command=self._toggle_fee_widgets_state)
        self.rb_fee_recommended.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.fee_recommended = get_recommended_fee_rate(node.mempool.get_all_valid_tx(), 6)
        self.label_fee_recommended_value = tk.Label(self.frame_fee, text=f"{self.fee_recommended} khets/KB")
        self.label_fee_recommended_value.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.var_wait_blocks = tk.IntVar(value=6)
        self.var_wait_blocks.trace_add("write", self._update_recommended_fee)
        self.label_wait_blocks = tk.Label(self.frame_fee, text=f"Expected blocks until inclusion:")
        self.label_wait_blocks.grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.spinbox_wait_blocks = tk.Spinbox(self.frame_fee, from_=1, to=1000, increment=1, textvariable=self.var_wait_blocks)
        self.spinbox_wait_blocks.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        
        self.rb_fee_custom = tk.Radiobutton(self.frame_fee, text="Custom", variable=self.fee_choice_var, value="custom", command=self._toggle_fee_widgets_state)
        self.rb_fee_custom.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.var_fee_custom = tk.DoubleVar(value=0.0)
        self.sb_custom_fee = tk.Spinbox(self.frame_fee, from_=0, to=MAX_KHETS, increment=0.01, textvariable=self.var_fee_custom, format="%.8f", validate="key", validatecommand=self.vcmd_KTC)
        self.sb_custom_fee.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.var_fee_unit = tk.StringVar(value="KTC")
        self.var_fee_unit.trace_add("write", lambda *_, val=self.var_fee_custom, unit=self.var_fee_unit, sb=self.sb_custom_fee: self._unit_conversion(val, unit, sb))
        self.om_fee_custom_unit = ttk.OptionMenu(self.frame_fee, self.var_fee_unit, "KTC", "khets", "KTC")
        self.om_fee_custom_unit.grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.label_fee_per_kb = tk.Label(self.frame_fee, text="per KB")
        self.label_fee_per_kb.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # 3. Options footer 
        self.frame_options = tk.Frame(self)
        self.frame_options.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self.btn_send = ttk.Button(self.frame_options, text="Send", command=self._send_tx_window)
        self.btn_send.pack(side="left", padx=2)
        self.btn_add_recipient = ttk.Button(self.frame_options, text="Add Recipient", command=self._add_recipient_block)
        self.btn_add_recipient.pack(side="left", padx=2)
        self.btn_clear_all = ttk.Button(self.frame_options, text="Remove All", command=self._remove_all_blocks)
        self.btn_clear_all.pack(side="left", padx=2)

        balance_val = get_addr_utxos_value(self.node.pk_hash) / KTC
        self.btn_wallet = ttk.Button(self.frame_options, text="Wallet", command=lambda: self.controller.switch_to_frame("your_wallet"))
        self.btn_wallet.pack(side="right", padx=2)
        self.label_balance = tk.Label(self.frame_options, text=f"Balance: {balance_val:.8f} KTC")
        self.label_balance.pack(side="right", padx=2)

        self._selected_tx: Transaction | None = None
        self._add_recipient_block()
        self._toggle_fee_widgets_state()
        
        # For quick address lookup
        self._contacts = None
        
    def on_show(self):
        with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM addresses")
            rows = cur.fetchall()
            self._contacts = {row[0]: (row[1], row[2]) for row in rows}
        
    def _add_recipient_block(self):
        row_index = len(self.recipient_frames)
        frame_recipient = tk.Frame(self.frame_recipients, borderwidth=1, relief="solid")
        frame_recipient.grid(row=row_index, column=0, sticky="ew", pady=5)
        
        frame_recipient.columnconfigure(1, weight=1)
        frame_recipient.columnconfigure(2, weight=1)

        label_pay_to = tk.Label(frame_recipient, text="Pay to")
        label_pay_to.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        entry_address = tk.Entry(frame_recipient)
        entry_address.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="ew")
        bind_entry_prompt(entry_address, "Khetcoin address (e.g. 1Ke23Hje6GoSoDVbgR6kyWRrNhubvGCkw2)")
        btn_contacts = ttk.Button(frame_recipient, text="Contacts", command=lambda e=entry_address: self._show_saved_addresses(e))
        btn_contacts.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        btn_delete = ttk.Button(frame_recipient, text="Delete", command=lambda b=frame_recipient: self._remove_recipient_block(b))
        btn_delete.grid(row=0, column=4, padx=5, pady=2, sticky="w")

        label_value = tk.Label(frame_recipient, text="Amount")
        label_value.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        var_value = tk.DoubleVar(value=0.0)
        sb_amount = ttk.Spinbox(frame_recipient, from_=0, to=MAX_KHETS, increment=0.01, textvariable=var_value, format="%.8f", validate="key", validatecommand=self.vcmd_KTC)
        sb_amount.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        var_unit = tk.StringVar(value="KTC")
        var_unit.trace_add("write", lambda *_, val=var_value, unit=var_unit, sb=sb_amount: self._unit_conversion(val, unit, sb))
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
        self.fee_recommended = get_recommended_fee_rate(self.node.mempool.get_all_valid_tx(), wait_blocks)
        self.label_fee_recommended_value.config(text=f"{self.fee_recommended} khets/KB")
        
    def _toggle_fee_widgets_state(self):
        choice = self.fee_choice_var.get()
        if choice == "recommended":
            self.label_fee_recommended_value.config(fg="black")
            self.sb_custom_fee.config(state="disabled")
            self.om_fee_custom_unit.config(state="disabled")
            self.label_fee_per_kb.config(fg="gray")
            self.label_wait_blocks.config(fg="black")
            self.spinbox_wait_blocks.config(state="normal")
        else:
            self.label_fee_recommended_value.config(fg="gray")
            self.sb_custom_fee.config(state="normal")
            self.om_fee_custom_unit.config(state="normal")
            self.label_fee_per_kb.config(fg="black")
            self.label_wait_blocks.config(fg="gray")
            self.spinbox_wait_blocks.config(state="disabled")
            
    def _unit_conversion(self, var_value, var_unit: tk.StringVar, sb: tk.Spinbox):
        new_unit = var_unit.get()
        if sb.cget('increment') == 0.01:
            old_unit = "KTC"
        else:
            old_unit = "khets"
            
        if new_unit == "KTC": 
            if old_unit == "KTC":
                return
            var_value.set(var_value.get() / KTC)
            sb.config(increment=0.01, format="%.8f", textvariable=var_value, validate="key", validatecommand=self.vcmd_KTC)
        elif new_unit == "khets":  
            if old_unit == "khets":
                return
            var_value.set(var_value.get() * KTC)
            sb.config(increment=1, format="%.0f", textvariable=var_value, validate="key", validatecommand=self.vcmd_khets)
            
    def _get_fee_rate(self):
        """
        Returns fee rate in khet/B for calculation purposes
        `Recommended`: returns based on reference to mempool
        `Custom`: self-explanatory
        """
        choice = self.fee_choice_var.get()
        if choice == "recommended":
            return get_recommended_fee_rate(self.node.mempool.get_all_valid_tx()) / 1024
        else:
            fee = self.var_fee_custom.get()
            if self.var_fee_unit.get() == "KTC":
                fee *= KTC
            return fee / 1024
        
    def _generate_tx(self) -> Transaction | None:
        # 0 Setup for output choices
        
        # 0.1 Get sfv_value and op_value
        # sfv_value: total value of all outputs marked "subtract fee from value"
        # op_value: total value of all outputs (including sfv and non-sfv)
        sfv_value, op_value = 0, 0
        for frame_recipient, output_fields in self.recipient_frames.items():
            value = output_fields["value"].get()
            if value == 0:
                frame_recipient.config(bg="pink")
                messagebox.showerror(title="Error creating transaction", message="Invalid value entry.", detail="You cannot input 0 as payment amount (see red highlight)!")
                frame_recipient.config(bg="white")
                return
            
            unit = output_fields["unit"].get()
            sub = output_fields["sub"].get()
            if unit == "KTC":
                value *= KTC
            sfv_value += int(value) if sub else 0
            op_value += int(value)
        
        # 0.2 Get UTXO set & sanity checks
        utxo_set = get_addr_utxos(self.node.pk_hash)
        utxo_value = sum(utxo.value for utxo in utxo_set)
        if op_value > utxo_value:
            messagebox.showerror(title="Error creating transaction", message="Insufficient funds!", detail=f"You need at least {(op_value - utxo_value)/KTC:.8f} KTC more to complete this transaction")
            return None
        
        # 1. Create Transaction
        # 1.1 Iteratively adjust the target UTXO set value to determine a suitable set that can cover transaction fees + output value
        #     The problem here lies in the fact that the transaction fees depend on what UTXOs are chosen (for tx size),
        #     but to select a suitable UTXO set requires us to know what the fee is (so that it covers total output value + fees)
        #
        #     The solution here is to first assume that the first pass/selection of UTXOs can cover the transaction fees.
        #     However, if we're not so lucky, we increase the target amount for the UTXO selection algorithm by the deficit and try again,
        #     until we land on a suitable UTXO set. 
        #
        #     It is possible that the iteration never converges in the scenario where the next passes keep on adding new UTXOs
        #     that have incredibly small values; the fee required to add these UTXO(s) exceeds the value it brings. This is
        #     highly unlikely unless the user has a lot of dust UTXOs, which are actively avoided by the UTXO selection algorithm.
        #
        #     In such cases, the user can specify a custom, smaller fee rate instead; though it risks their transaction never being relayed or mined.
        
        fee_rate = self._get_fee_rate()
        n_outputs = len(self.recipient_frames.values())
        target = op_value

        for _ in range(10):
            utxo_guess = select_utxos(utxo_set, target)
            if not utxo_guess:
                messagebox.showerror(title="Error creating transaction", message="Error selecting UTXOs. Please double check if you have sufficient funds")
                return None
            
            n_inputs = len(utxo_guess)
            utxo_guess_value = sum(utxo.value for utxo in utxo_guess)
            use_change = not (utxo_guess_value == op_value)
            
            # Note that this only works for P2PKH
            tx_size = 4 \
                      + len(encode_varint(n_inputs) ) + P2PKH_INPUT_SIZE  *  n_inputs \
                      + len(encode_varint(n_outputs + use_change)) + P2PKH_OUTPUT_SIZE * (n_outputs + use_change) \
                      + 4
                      
            fee = fee_rate * tx_size
            payment = op_value if sfv_value else op_value + fee
            change =  utxo_guess_value - payment
            
            if change == 0:
                break
            elif change >= MIN_CHANGE:
                break
            else:  # Insufficient funds, reiterate
                deficit = -change
                target += deficit
                continue
        else:
            messagebox.showerror(title="Error creating transaction", message="Error selecting UTXOs. Try reducing MIN_CHANGE.")
            return None
        
        inputs = []
        for utxo in utxo_guess:
            inputs.append(TransactionInput(
                prev_hash=utxo.tx_hash,
                prev_index=utxo.index,
                script_sig=Script([]),
                sequence=0xffffffff
            ))
            
        outputs = []
        for frame_recipient, output_fields in self.recipient_frames.items():
            pk_hash = wif_decode(output_fields["addr"].get())
            
            if pk_hash is None:
                frame_recipient.config(bg="pink")
                messagebox.showerror(title="Error creating transaction", message="One or more invalid payment address (see red highlight). Ensure it follows valid WIF format.")
                return
            
            frame_recipient.config(bg="white")
            value = output_fields["value"].get()
            unit = output_fields["unit"].get()
            
            if unit == "KTC":
                value *= KTC
            
            if sub:
                value -= ceil(fee * value / sfv_value)
                if value < 0:
                    frame_recipient.config(bg="pink")
                    messagebox.showerror(title="Error creating transaction", message="Invalid value entry.", detail="Insufficient amount to cover fees. Try turning off subtract by fee (see red highlight).")
                    frame_recipient.config(bg="white")
                    return
                
            #P2PKH
            outputs.append(
                TransactionOutput(
                    value=int(value),
                    script_pubkey=P2PKH_script_pubkey(pk_hash)
                )
            )
            
        # 2. SFV output value adjustment & change value
        if change:
            change_output = TransactionOutput(
                value=int(change),
                script_pubkey=P2PKH_script_pubkey(self.node.pk_hash)  # Change addr
            )
            change_output.set_change()
            outputs.append(change_output)
            
        # 3. Create & sign transaction
        tx = Transaction(
            version=TX_VERSION,
            inputs=inputs,
            outputs=outputs,
            locktime=0
        )
        
        # TODO this is kinda sketchy
        if tx.sign(get_private_key(self.node.name, raw=False)): # type: ignore
            self._selected_tx = tx
            return tx
        else:
            messagebox.showerror(title="Error creating transaction", message="Signing failed when creating transaction.")
            return None
    
    def _send_tx(self):
        # 1. InvMessage creation
        inv_msg = InvMessage([(1, self._selected_tx.hash())])
        msg = MessageEnvelope(inv_msg.command, inv_msg.payload)
        if len(self.node.peers) > 0:
            self.node.broadcast(msg)
        else:
            if not messagebox.askokcancel("No Peers", "Your node is not connected to any peers. Continuing will add the transaction only to your mempool. Proceed anyways?"):
                return
                

        # 2. tx broadcasting and storage
        if not self.node.mempool.add_tx(self._selected_tx):
            messagebox.showwarning("Failed to add transaction to mempool", f"See {APP_CONFIG.get('path', 'log')} for more info.")
        else:
            # 3. GUI notification
            messagebox.showinfo(title="Transaction Created!", message="Your transaction has been broadcasted.")
            self._remove_all_blocks()

    def _send_tx_window(self):
        self._selected_tx = self._generate_tx()
        if not self._selected_tx:
            return 

        win_tx = tx_popup(self, self._selected_tx, "valid")
        win_tx.grab_set()
        center_popup(self, win_tx)
        
        fee_disclaimer = tk.Label(win_tx, text="Actual fee rate may be slightly higher than specified fee.", font=("Arial", 8, "italic"))
        fee_disclaimer.grid(row=2, column=0, padx=5, pady=5)
        btn_send = ttk.Button(win_tx, text="Send Transaction", command=lambda: (self._send_tx(), win_tx.destroy()))
        btn_send.grid(row=3, column=0, padx=15, pady=15, sticky="e")
 

    def _show_saved_addresses(self, entry_addr: tk.Entry):
        win = tk.Toplevel(self)
        win.title("Contacts")
        win.geometry("400x300")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
        
        contacts_cols = {
            "name": ("Name", 100),
            "address": ("Address", 200)
        }
        
        tree_contacts = create_scrollable_treeview(win, contacts_cols, (0, 0))
        tree_contacts.bind("<<TreeviewSelect>>", lambda _: (self._fill_address_field_from_selection(entry_addr, tree_contacts), win.destroy()))
        
        for iid, info in self._contacts.items():
            tree_contacts.insert("", "end", iid=iid, values=info)
        
    def _fill_address_field_from_selection(self, entry_addr: tk.Entry, tree_contacts: ttk.Treeview):
        selection = tree_contacts.selection()
        if not selection:
            return
        
        iid = int(selection[0])
        entry_addr.event_generate("<FocusIn>")
        entry_addr.delete(0, tk.END)
        entry_addr.insert(0, self._contacts[iid][1])
            