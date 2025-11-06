import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import sqlite3

from crypto.key import wif_decode
from utils.config import APP_CONFIG
from utils.fmt import format_age, format_epoch

class SavedAddressesFrame(tk.Frame):
    def __init__(self, parent, controller, node):
        super().__init__(parent)

        self.controller = controller
        self.node = node
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        
        self.frame_main = ttk.Frame(self, padding="5")
        self.frame_main.grid(row=0, column=0, sticky="nsew")
        self.frame_main.grid_rowconfigure(0, weight=0)
        self.frame_main.grid_rowconfigure(1, weight=1)
        self.frame_main.grid_columnconfigure(0, weight=1)

        # 1. Options Menu
        self.frame_sort = tk.Frame(self.frame_main)
        self.frame_sort.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        tk.Label(self.frame_sort, text="Sort By:").pack(side="left", padx=(0, 5))
        
        self.sort_by_var = tk.StringVar(value="Value")
        self.om_sort_by = ttk.OptionMenu(self.frame_sort, self.sort_by_var, "Name", "Name", "Added", command=self._sort_addrs)
        self.om_sort_by.pack(side="left", padx=5)

        self.sort_order_var = tk.StringVar(value="Ascending")
        self.om_sort_order = ttk.OptionMenu(self.frame_sort, self.sort_order_var, "Ascending", "Ascending", "Descending", command=self._sort_addrs)
        self.om_sort_order.pack(side="left", padx=5)
        
        self.label_no_addrs = tk.Label(self.frame_sort, text="")
        self.label_no_addrs.pack(side="left", padx=(0, 5))
        
        # 2. Wallet Addresses Treeview
        addr_cols = {
            "name": ("Name", 150),
            "addr": ("Wallet Address", 300),
            "added": ("Added", 100)
        }
        
        self.lf_addrs = ttk.LabelFrame(self.frame_main, text="Saved Addresses", padding="5")
        self.lf_addrs.grid(row=1, column=0, sticky="nsew")
        self.lf_addrs.grid_rowconfigure(0, weight=1)
        self.lf_addrs.grid_columnconfigure(0, weight=1)
        
        self.tree_addrs = ttk.Treeview(
            self.lf_addrs,
            columns=list(addr_cols.keys()),
            show="headings",
            selectmode="browse"
        )
        
        for col_id, (text, width) in addr_cols.items():
            self.tree_addrs.heading(col_id, text=text)
            self.tree_addrs.column(col_id, width=width, minwidth=50, stretch=True, anchor="w")
            
        vsb_addrs = ttk.Scrollbar(self.lf_addrs, orient="vertical", command=self.tree_addrs.yview)
        hsb_addrs = ttk.Scrollbar(self.lf_addrs, orient="horizontal", command=self.tree_addrs.xview)
        self.tree_addrs.configure(yscrollcommand=vsb_addrs.set, xscrollcommand=hsb_addrs.set)
        
        self.tree_addrs.grid(row=0, column=0, sticky="nsew")
        vsb_addrs.grid(row=0, column=1, sticky="ns")
        hsb_addrs.grid(row=1, column=0, sticky="ew")
        
        self.tree_addrs.bind("<<TreeviewSelect>>", self._on_addr_select)
        
        self.btn_add_addr = ttk.Button(self, text="Add", command=self._add_addr)
        self.btn_add_addr.grid(row=1, column=0, sticky="e")
        
        # 3. Address Edit panel
        self.lf_addr_info = ttk.LabelFrame(self, text="Address Info")
        self.lf_addr_info.grid(row=0, column=1, sticky="nsew")
        
        ttk.Label(self.lf_addr_info, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.label_name = ttk.Label(self.lf_addr_info)
        self.label_name.grid(row=0, column=1, sticky="w", padx=5)

        self.btn_edit_name = ttk.Button(self.lf_addr_info, text="Edit", command=lambda: self._edit_var("name"))
        self.btn_edit_name.grid(row=0, column=2, padx=5)

        ttk.Label(self.lf_addr_info, text="Address:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.label_addr = ttk.Label(self.lf_addr_info)
        self.label_addr.grid(row=1, column=1, sticky="w", padx=5)

        self.btn_edit_addr = ttk.Button(self.lf_addr_info, text="Edit", command=lambda: self._edit_var("address"))
        self.btn_edit_addr.grid(row=1, column=2, padx=5)

        ttk.Label(self.lf_addr_info, text="Added:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.label_added = ttk.Label(self.lf_addr_info)
        self.label_added.grid(row=2, column=1, sticky="w", padx=5)

        btn_remove = ttk.Button(self.lf_addr_info, text="Remove", command=self._confirm_remove)
        btn_remove.grid(row=3, column=0, padx=5, pady=40)

        btn_close = ttk.Button(self.lf_addr_info, text="Close", command=self._hide_addr_info)
        btn_close.grid(row=4, column=3, sticky="e", padx=5, pady=5)
        
        # 4. Initial Setup
        self._hide_addr_info()
        self.addrs = self._load_addrs()
        self.selected_addr = None
        self.selected_iid = None
        self._generate_addrs_treeview()

    
    def _load_addrs(self):
        # Should only run once upon the first time loading this frame.
        with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM addresses")
            rows = cur.fetchall()
            return {row[0]: 
                {
                    "name": row[1],
                    "address": row[2],
                    "added": row[3]
                } 
            for row in rows}
        
    def _generate_addrs_treeview(self):
        sort_by = self.sort_by_var.get()
        reverse = self.sort_order_var.get() == "Descending"
        if sort_by == "Name":
            sorted_addr = dict(sorted(self.addrs.items(), key=lambda item: item[1]["name"], reverse=reverse))
        elif sort_by == "Added":  # "Added" col in our treeview is the age, so we sort by reverse timestamp
            sorted_addr = dict(sorted(self.addrs.items(), key=lambda item: item[1]["added"], reverse=not reverse))
        else:  # Maybe there can be more sorting options in the future
            sorted_addr = self.addrs  
            
        for iid, info in sorted_addr.items():
            values = (
                info["name"],
                info["address"],
                format_age(info["added"])
            )
            
            self.tree_addrs.insert("", "end", iid=iid, values=values)
            
        self.label_no_addrs.config(text=f"{len(self.addrs)} saved addresses")
        return 
    
    def _on_addr_select(self, _):
        self.selected_iid = self.tree_addrs.selection()
        self.selected_addr = self.addrs[self.selected_iid]
        
        if not self.lf_addr_info.winfo_ismapped():
            self.lf_addr_info.grid(row=0, column=1, sticky="nsew")
        
        self.lf_addr_info.config(text=self.selected_addr["name"])
        self.label_name.config(text=self.selected_addr["name"])
        self.label_addr.config(text=self.selected_addr["addresse"])
        self.label_added.config(text=format_epoch(self.selected_addr["added"]))
    
    def _hide_addr_info(self):
        self.lf_addr_info.grid_remove()
        self.selected_addr = self.selected_iid = None
    
    def _edit_var(self, field: str):
        win = tk.Toplevel(self)
        win.title(f"Edit {field} for {self.selected_addr['name']}")

        win.geometry("300x180")
        win.transient(self)
        win.grab_set()
        
        entry = ttk.Entry(win)
        entry.insert(0, self.selected_addr[field])
        entry.pack(padx=10, pady=5, fill="x")
        entry.focus_set()
        
        frame_save_cancel = ttk.Frame(win)
        frame_save_cancel.pack(padx=10, pady=(10, 10), fill="x")

        ttk.Button(
            frame_save_cancel, text="Cancel", command=win.destroy
        ).pack(side="right", expand=True, fill="x")
        
        ttk.Button(
            frame_save_cancel, text="Save", command=lambda: (self.save_edit(field, entry), win.destroy())
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
    
    
    def _save_edit(self, field: str, entry: tk.Entry):
        value = entry.get().strip()
        if field == "name":
            self.label_name.config(text=value)
            cmd = "UPDATE addresses SET name = ? WHERE id = ?"
        elif field == "address":
            self.label_addr.config(text=value)
            cmd = "UPDATE addresses SET address = ? WHERE id = ?"
                        
        self.addrs[self.selected_iid][field] = value
        with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
            cur = con.cursor()
            cur.execute(cmd, (value, self.selected_iid))

    
    def _sort_addrs(self):
        return
    
    def _confirm_remove(self):
        return 
    
    def _add_addr(self):
        win = tk.Toplevel(self)
        win.title(f"Add address")

        win.geometry("400x300")
        win.transient(self)
        win.grab_set()
        
        entry_name = ttk.Entry(win)
        entry_name.pack(padx=10, pady=5, fill="x")
        
        entry_addr = ttk.Entry(win)
        entry_addr.pack(padx=10, pady=5, fill="x")
        
        frame_save_cancel = ttk.Frame(win)
        frame_save_cancel.pack(padx=10, pady=(10, 10), fill="x")

        ttk.Button(
            frame_save_cancel, text="Cancel", command=win.destroy
        ).pack(side="right", expand=True, fill="x")
        
        ttk.Button(
            frame_save_cancel, text="Save", command=lambda: self._save_addr(win, entry_name, entry_addr)
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
    
    def _save_addr(self, win, entry_name, entry_addr):
        name = entry_name.get()
        addr = entry_addr.get()
        
        if not name:
            messagebox.showwarning("Failed to save address", "Name cannot be empty!")
        elif not addr:
            messagebox.showwarning("Failed to save address", "Address cannot be empty!")
        elif wif_decode(addr) is None:
            messagebox.showwarning("Failed to save address", "Invalid Address!")
        elif addr in [info["addr"] for info in self.addr]:
            messagebox.showwarning("Failed to save address", "Address already saved!")
        else:
            with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
                cur = con.cursor()
                added = int(time.time())
                cur.execute("""
                    INSERT INTO addresses (name, address, added)
                    VALUES (?, ?, ?)
                """, (name, addr, added))
            
                con.commit()
                cur.execute("SELECT id FROM addresses WHERE address = ?", (addr,))
                iid = cur.fetchone()
                
            print(type(iid))
            self.addrs[iid] = {
                "name": name,
                "address": addr,
                "added": added
            }
            
            self._generate_addrs_treeview()
            messagebox.showinfo("Address saved")
            win.destroy()
    
    def _delete_addr(self, iid):
        pass
        
    def _update(self):
        #
        return