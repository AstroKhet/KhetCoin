
import os
import tkinter as tk
from tkinter import ttk, messagebox

from crypto.key import private_key_to_wif, save_private_key
from crypto.keygen import KeyGenerator
from gui.helper import reset_widget
from gui.vcmd import register_VCMD_filename, register_VCMD_wif_prefix
from setup.initializer import init_db, init_font
from utils.config import APP_CONFIG
    
class SetupApp():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KhetCoin Setup")
        self.root.geometry("600x400")
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        
        self.vcmd_filename = register_VCMD_filename(self.root)
        self.vcmd_wif_prefix = register_VCMD_wif_prefix(self.root)
        
        self.view_container = tk.Frame(self.root)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.view_container.rowconfigure(0, weight=1)
        self.view_container.columnconfigure(0, weight=1)
        
        self.name = None
        self.priv_key = None
        self.keygen = KeyGenerator()
        
        self.show_welcome_frame()

        
    def main(self):
        try:
            self.root.mainloop()
        except Exception as e:
            print(e)
            self._close()
        
    def show_welcome_frame(self):
        reset_widget(self.view_container)
        frame = tk.Frame(self.view_container)
        frame.tkraise()
        frame.place(relx=0.5, rely=0.5, anchor="center")  # center everything
        

        self.var_confirm_name = tk.BooleanVar(value=False)
        name_var = tk.StringVar()

        tk.Label(frame, text="Welcome to KhetCoin!", font=("TkDefaultFont", 20, "bold")).pack(pady=(0, 20))

        tk.Label(frame, text="To get started, please enter your name:",).pack(pady=(0, 10))

        entry = ttk.Entry(frame, textvariable=name_var, width=25, justify="center", validate="key", validatecommand=self.vcmd_filename)
        entry.pack(pady=5)
        entry.focus_set()

        def on_confirm():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Invalid name", "Please enter your name.")
                return

            if messagebox.askyesno(
                "Confirm name",
                f"Is this name correct?\n\n{name}\n\nYou cannot change this later",
            ):
                self.name = name_var.get().strip()
                self.show_addr_frame()

        ttk.Button(frame, text="Confirm", command=on_confirm).pack(pady=10)

        
    def show_addr_frame(self):
        reset_widget(self.view_container)
        frame = tk.Frame(self.view_container)
        frame.tkraise()
        frame.place(relx=0.5, rely=0.5, anchor="center")

        # initial key
        self.priv_key = os.urandom(32)
        wif = private_key_to_wif(self.priv_key)
        self.var_confirm_addr = tk.BooleanVar(value=False)

        tk.Label(frame, text="Generate wallet address", font=("TkDefaultFont", 20, "bold")).pack(pady=(0, 20))
        tk.Label(frame, text="Your Address:").pack(pady=5)
        self.label_addr = tk.Label(frame, text=wif, font=("TkDefaultFont", 12), width=60, anchor="center")
        self.label_addr.pack(padx=10, pady=5)

        # Buttons: Confirm and Regenerate side by side
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=10)

        def on_confirm():
            if messagebox.askyesno(
                "Confirm address",
                f"Is this address correct?\n\n{private_key_to_wif(self.priv_key)}\n\nYou cannot change this later",
            ):
                self.show_done_frame()
                
        self.btn_confirm_addr = ttk.Button(btn_frame, text="Confirm", command=on_confirm)
        self.btn_confirm_addr.pack(side="left", padx=5)
        self.btn_generate_addr = ttk.Button(btn_frame, text="Regenerate", command=self._on_keygen_generate)
        self.btn_generate_addr.pack(side="left", padx=5)

        # Prefix entry with info button
        prefix_frame = tk.Frame(frame)
        prefix_frame.pack(pady=10)

        tk.Label(prefix_frame, text="Prefix (optional):").pack(side="left")

        
        self.prefix_var = tk.StringVar()
        self.entry_prefix = ttk.Entry(prefix_frame, width=5, textvariable=self.prefix_var, validate="key", validatecommand=self.vcmd_wif_prefix)
        self.entry_prefix.pack(side="left", padx=5)

        def show_prefix_info():
            messagebox.showinfo(
                "Prefix Info",
                "Valid prefixes can contain up to 4 alphanumerical charcters except for: \nZero - '0'\nCapital o - 'O'\nSmall L - 'l'\nCapital i -'I'.\n\n"
                "Example: prefix 'Khet' -> 1KhetHcbU3NnLiW7xabtvPUZMSVwYQXhsY"
            )

        ttk.Button(prefix_frame, text="?", width=2, command=show_prefix_info).pack(side="left", padx=5)


    def show_done_frame(self):
        reset_widget(self.view_container)
        frame = tk.Frame(self.view_container)
        frame.tkraise()
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(frame, text="You are all set!", font=("TkDefaultFont", 20, "bold")).pack(pady=(0, 12))
        
        tk.Label(frame, text=f"Your name: {self.name}").pack(pady=2)
        tk.Label(frame, text=f"Your wallet address: {private_key_to_wif(self.priv_key)}").pack(pady=2)
        # Buttons: Confirm and Regenerate side by side
        
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=10)

        def save():
            save_private_key(self.priv_key, self.name)
            APP_CONFIG.set("app", "name", self.name)
            APP_CONFIG.set("mining", "tag", f"/{self.name}/")
            init_db()
            init_font()
            APP_CONFIG.set("app", "initial_setup", True)
            
            self._close()
            
        btn_save = ttk.Button(btn_frame, text="Confirm", command=save)
        btn_save.pack(side="left", padx=5)
        
        def on_redo():
            if messagebox.askyesno(
                "Confirm redo",
                f"Your current name and address will be reset",
            ):
                self.show_welcome_frame()
        btn_redo = ttk.Button(btn_frame, text="Reset", command=on_redo)
        btn_redo.pack(side="left", padx=5)


    def _on_keygen_generate(self):
        prefix = self.prefix_var.get()
        if not prefix:
            self.priv_key = os.urandom(32)
            wif = private_key_to_wif(self.priv_key)
            self.label_addr.config(text=wif)
            return
        
        self.entry_prefix.config(state="disabled")
        self.btn_confirm_addr.config(state="disabled")
        
        self.btn_generate_addr.config(
            text="Stop",
            command=self._on_keygen_stop
        )
        
        self.label_addr.config(text="Generating...")
            
        self.keygen.generate(prefix)
        self._update_show_addr()
        
    def _on_keygen_stop(self):
        self.keygen.shutdown()
        self.label_addr.config(text=private_key_to_wif(self.priv_key))
        self.btn_generate_addr.config(
            text="Regenerate",
            command=self._on_keygen_generate
        )
        self.entry_prefix.config(state="normal")
        self.btn_confirm_addr.config(state="normal")
        
        
    def _update_show_addr(self):
        if private_key := self.keygen.private_key:
            self.priv_key = private_key
            self._on_keygen_stop()
            return
            
        if self.keygen.stop_flag.value:
            self.btn_generate_addr.config(
                text="Regenerate",
                command=self._on_keygen_generate
            )
            return

        self.root.after(500, self._update_show_addr)
    
    def _close(self):
        # Close all waiting variables
        self.root.destroy()
        
        