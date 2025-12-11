import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import sqlite3

from crypto.key import wif_decode
from gui.frames.common.scrollable import create_scrollable_treeview
from gui.helper import center_popup, copy_to_clipboard
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
        self.frame_main.rowconfigure(0, weight=0)
        self.frame_main.rowconfigure(1, weight=1)
        self.frame_main.columnconfigure(0, weight=1)

        # 1. Options Menu
        self.frame_sort = tk.Frame(self.frame_main)
        self.frame_sort.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        tk.Label(self.frame_sort, text="Sort By:").pack(side="left", padx=(0, 5))
        
        self.sort_by_var = tk.StringVar(value="Name")
        self.om_sort_by = ttk.OptionMenu(self.frame_sort, self.sort_by_var, "Name", "Name", "Added", command=self._sort_addrs)
        self.om_sort_by.pack(side="left", padx=5)

        self.sort_order_var = tk.StringVar(value="Ascending")
        self.om_sort_order = ttk.OptionMenu(self.frame_sort, self.sort_order_var, "Ascending", "Ascending", "Descending", command=self._sort_addrs)
        self.om_sort_order.pack(side="left", padx=5)
        
        self.label_no_addrs = tk.Label(self.frame_sort, text="")
        self.label_no_addrs.pack(side="left", padx=(0, 5))
        
        # 2. Wallet Addresses Treeview
        ADDR_COLS = {
            "name": ("Name", 150),
            "addr": ("Wallet Address", 300),
            "added": ("Added", 100)
        }
        
        self.lf_addrs = ttk.LabelFrame(self.frame_main, text="Saved Addresses", padding="5")
        self.lf_addrs.grid(row=1, column=0, sticky="nsew")
        self.lf_addrs.rowconfigure(0, weight=1)
        self.lf_addrs.columnconfigure(0, weight=1)
        
        self.tree_addrs = create_scrollable_treeview(self.lf_addrs, ADDR_COLS, (0, 0))
        self.tree_addrs.bind("<<TreeviewSelect>>", self._on_addr_select)
        
        self.btn_add_addr = ttk.Button(self, text="Add", command=self._add_addr)
        self.btn_add_addr.grid(row=1, column=0, sticky="e")
        
        # 3. Address Edit panel
        self.lf_addr_info = ttk.LabelFrame(self, text="Address Info")
        self.lf_addr_info.grid(row=0, column=1, sticky="nsew")
        
        ttk.Label(self.lf_addr_info, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.label_name = ttk.Label(self.lf_addr_info)
        self.label_name.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Button(self.lf_addr_info, text="Edit", width=5, command=lambda: self._edit_var("name")).grid(row=0, column=2, padx=5)

        ttk.Label(self.lf_addr_info, text="Address:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.label_addr = ttk.Label(self.lf_addr_info)
        self.label_addr.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Button(self.lf_addr_info, text="Edit", width=5, command=lambda: self._edit_var("address")).grid(row=1, column=2, padx=5)

        ttk.Label(self.lf_addr_info, text="Added:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.label_added = ttk.Label(self.lf_addr_info)
        self.label_added.grid(row=2, column=1, sticky="w", padx=5)

        btn_remove = ttk.Button(self.lf_addr_info, text="Remove", command=self._delete_addr)
        btn_remove.grid(row=3, column=0, padx=5, pady=40)

        btn_close = ttk.Button(self.lf_addr_info, text="Close", command=self._hide_addr_info)
        btn_close.grid(row=4, column=2, sticky="e", padx=5, pady=5, columnspan=2)
        
        # 4. Initial Setup
        self._hide_addr_info()
        self.addrs = self._load_addrs()
        self._selected_addr = None
        self._selected_iid = None
        self._generate_addrs_treeview()
        self._update()
    
    def refocus(self):
        self.addrs = self._load_addrs()
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
        for item in self.tree_addrs.get_children():
            self.tree_addrs.delete(item)
            
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
                format_age(int(time.time()) - info["added"]) + " ago"
            )
            
            self.tree_addrs.insert("", "end", iid=iid, values=values)
            
        self.label_no_addrs.config(text=f"{len(self.addrs)} saved addresses")
        return 
    
    def _on_addr_select(self, _):
        selection = self.tree_addrs.selection()
        if not selection:
            return
        
        self._selected_iid = int(selection[0])
        self._selected_addr = self.addrs[self._selected_iid]
        
        if not self.lf_addr_info.winfo_ismapped():
            self.lf_addr_info.grid(row=0, column=1, sticky="nsew")
        
        name = self._selected_addr["name"]
        addr = self._selected_addr["address"]
        self.lf_addr_info.config(text=name)
        
        self.label_name.config(text=name)
        
        self.label_addr.config(text=addr)
        ttk.Button(self.lf_addr_info, text="Copy", width=5, command=lambda a=addr: copy_to_clipboard(self, a)).grid(row=1, column=3)
        
        self.label_added.config(text=format_epoch(self._selected_addr["added"]))
    
    def _hide_addr_info(self):
        self.lf_addr_info.grid_remove()
        self._selected_addr = self._selected_iid = None
    
    def _edit_var(self, field: str):
        win = tk.Toplevel(self)
        win.title(f"Edit {field} for {self._selected_addr['name']}")
        win.geometry("300x180")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text=f"New {field}:").grid(row=0, column=0, padx=10, pady=10, sticky="w")

        entry = ttk.Entry(win)
        entry.insert(0, self._selected_addr[field])
        entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        entry.focus_set()

        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=1, column=0, columnspan=2, pady=15, padx=10, sticky="e")

        ttk.Button(frame_btns, text="Cancel", command=win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(frame_btns, text="Save", command=lambda: (self._save_edit(field, entry), win.destroy())).pack(side="right")
    
    def _save_edit(self, field: str, entry: tk.Entry):
        value = entry.get().strip()
        if field == "name":
            self.label_name.config(text=value)
            self.lf_addr_info.config(text=value)
            cmd = "UPDATE addresses SET name = ? WHERE id = ?"
        elif field == "address":
            if wif_decode(value) is None:
                messagebox.showwarning("Failed to save address", "Invalid Address! Please check again")
                return
            
            self.label_addr.config(text=value)
            cmd = "UPDATE addresses SET address = ? WHERE id = ?"
                        
        self.addrs[self._selected_iid][field] = value
        with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
            cur = con.cursor()
            # Duplicate check
            if field == "address":
                cur.execute("SELECT id FROM addresses WHERE address = ?", (value,))
                if cur.fetchone():
                    messagebox.showwarning("Duplicate entry", f"Entry with wallet address {value} already saved in contacts.")
                    return

            cur.execute(cmd, (value, self._selected_iid))
        self.tree_addrs.set(self._selected_iid, field, value)
        
    
    def _sort_addrs(self, *_):
        self._generate_addrs_treeview()

    def _add_addr(self):
        win = tk.Toplevel(self)
        win.title("Add address")
        win.geometry("300x120")
        win.transient(self)
        win.grab_set()
        center_popup(self, win)
        
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="Name:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        entry_name = ttk.Entry(win)
        entry_name.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ttk.Label(win, text="Wallet Address:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        entry_addr = ttk.Entry(win)
        entry_addr.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        frame_btns = ttk.Frame(win)
        frame_btns.grid(row=2, column=0, columnspan=2, pady=15, padx=10, sticky="e")

        ttk.Button(frame_btns, text="Cancel", command=win.destroy).pack(side="right", padx=(5, 0))
        ttk.Button(frame_btns, text="Save", command=lambda: self._save_addr(win, entry_name, entry_addr)).pack(side="right")

        
    def _save_addr(self, win, entry_name, entry_addr):
        name = entry_name.get()
        addr = entry_addr.get()
        
        if not name:
            messagebox.showwarning("Failed to save address", "Name cannot be empty!")
        elif not addr:
            messagebox.showwarning("Failed to save address", "Address cannot be empty!")
        elif wif_decode(addr) is None:
            messagebox.showwarning("Failed to save address", "Invalid Address!")
        else:
            with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
                cur = con.cursor()
                
                # Duplicate check
                cur.execute("SELECT id FROM addresses WHERE address = ?", (addr,))
                if cur.fetchone():
                    messagebox.showwarning("Duplicate entry", f"Entry with wallet address {addr} already saved in contacts.")
                    return
                
                added = int(time.time())
                cur.execute("""
                    INSERT INTO addresses (name, address, added)
                    VALUES (?, ?, ?)
                """, (name, addr, added))
            
                con.commit()
                cur.execute("SELECT id FROM addresses WHERE address = ?", (addr,))
                iid = int(cur.fetchone()[0])
                
            self.addrs[iid] = {
                "name": name,
                "address": addr,
                "added": added
            }
            
            self._generate_addrs_treeview()
            win.destroy()
            messagebox.showinfo(title="Address saved", message=f"Saved \"{name}\" to your contacts.")
            
    
    def _delete_addr(self):
        iid = self._selected_iid
        name = self.addrs[iid]['name']
        if messagebox.askokcancel(title="Confirm deletion", message=f"Are you sure you want to remove \"{name}\" from your contacts?"):
            with sqlite3.connect(APP_CONFIG.get("path", "addresses")) as con:
                cur = con.cursor()
                cur.execute("DELETE FROM addresses WHERE id = ?", (iid,))
            self.addrs.pop(iid)
            self.tree_addrs.delete(iid)
            messagebox.showinfo(title="Address removed", message=f"\"{name}\" removed from contacts.")
            self._hide_addr_info()
            self.label_no_addrs.config(text=f"{len(self.addrs)} saved addresses")

        
    def _update(self):
        for iid in self.tree_addrs.get_children():
            age = format_age(int(time.time()) - self.addrs[int(iid)]["added"]) + " ago"
            self.tree_addrs.set(iid, "added", age)
        
        self.after(500, self._update)
    