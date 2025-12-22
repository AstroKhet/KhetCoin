import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from gui.bindings import bind_hierarchical, mousewheel_cb
from gui.common.scrollable import create_scrollable_frame
from gui.fonts import SansFont
from gui.helper import attach_tooltip
from gui.vcmd import register_VCMD_INT, register_VMCD_KTC
from utils.config import APP_CONFIG
from utils.fmt import format_snake_case

_frame_id = 2


class SettingsFrame(tk.Frame):
    def __init__(self, parent, controller, node):
        super().__init__(parent)
        self.controller = controller
        self.node = node
                
        self.vcmd_int = register_VCMD_INT(self)
        self.vcmd_ktc = register_VMCD_KTC(self)
        self.widgets = {}
        
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)
        
        frame_center_cointainer = ttk.Frame(self)
        frame_center_cointainer.rowconfigure(0, weight=1)
        frame_center_cointainer.grid(row=0, column=1, sticky="nsew")
        
        self.frame_main, cnv_main = create_scrollable_frame(frame_center_cointainer, xscroll=False)

        self._generate_settings_menu()
        bind_hierarchical("<MouseWheel>", self, lambda e: mousewheel_cb(e, cnv_main))
        
        
    def _generate_settings_menu(self):
        tk.Label(self.frame_main, text="Settings", font=SansFont(14, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="ew", padx=5)
        tk.Label(self.frame_main, text="(Hover over variable to see more details)", font=SansFont(8), fg="gray").grid(row=1, column=0, columnspan=3, sticky="ew", padx=5)

        row = 2
        for cat, vars in APP_CONFIG.data.items():
            if any(v["display"] for v in vars.values()) == False:
                continue
            
            label_cat = tk.Label(self.frame_main, text=cat.capitalize(), font=SansFont(10, weight="bold"))
            label_cat.grid(row=row, column=0, sticky="w", padx=5, pady=(15, 0))
            row += 1

            for key, struct_var in vars.items():
                if not struct_var["display"]:
                    continue
                
                # Display config var value
                label_key = tk.Label(self.frame_main, text=format_snake_case(key, all_words=False))
                label_key.grid(row=row, column=0, sticky="w", padx=10)
                if description := struct_var["description"]:
                    attach_tooltip(label_key, description)
                                
                display_val = str(struct_var["value"])
                if unit := struct_var["unit"]:
                    display_val += " " + unit
                    
                label_var = tk.Label(self.frame_main, text=display_val)
                label_var.grid(row=row, column=1, sticky="w", padx=10)
         
                # Create edit button
                
                if struct_var["type"] == "bool":
                    if struct_var["configurable"]:
                        var = tk.BooleanVar(value=struct_var["value"])
                        chk = ttk.Checkbutton(self.frame_main, variable=var,
                            command=lambda c=cat, k=key, v=var, l=label_var: self._set_variable(c, k, v, l))
                        chk.grid(row=row, column=2, padx=15)

                elif struct_var["type"] in ("str", "int", "float"):
                    if cat == "path":
                        btn_goto = ttk.Button(self.frame_main, text="Open Folder", width=12,
                            command=lambda p=struct_var["value"]: self._goto_folder(p))
                        btn_goto.grid(row=row, column=2, sticky="w", padx=15)
                    else:
                        if struct_var["configurable"]:
                            if struct_var["type"] == "str":
                                var = tk.StringVar(value=struct_var["value"])
                            elif struct_var["type"] == "int":
                                var = tk.IntVar(value=struct_var["value"])
                            elif struct_var["type"] == "float":
                                var = tk.DoubleVar(value=struct_var["value"])
                                
                            btn_edit = ttk.Button(self.frame_main, text="Edit", 
                                command=lambda c=cat, k=key, v=var, l=label_var: self._set_variable(c, k, v, l))
                            btn_edit.grid(row=row, column=2, sticky="w", padx=15)
                row += 1


    def _set_variable(self, cat: str, key: str, var, label: tk.Label):
        row = label.grid_info()["row"]
        if isinstance(var, tk.BooleanVar):
            val = var.get()
            APP_CONFIG.set(cat, key, val)
            label.config(text=str(val))
            
        elif isinstance(var, (tk.StringVar, tk.IntVar, tk.DoubleVar)):
            val = var.get()
            entry_edit = tk.Entry(self.frame_main, textvariable=var, width=8)
            
            
            if isinstance(var, tk.IntVar):
                entry_edit.config(validate="key", validatecommand=self.vcmd_int)
            if isinstance(var, tk.DoubleVar):
                entry_edit.config(validate="key", validatecommand=self.vcmd_ktc)  # Will probably only need floats for vars with KTC unit
            entry_edit.grid(row=row, column=1, sticky="ew", padx=5)
            
            # Remove Edit btn
            self._remove_widgets_in_cell(self.frame_main, row=row, col=2)
            
            # Place in Save & Cancel buttons
            btn_save = ttk.Button(self.frame_main, text="Save", 
                command=lambda c=cat, k=key, v=var, l=label: 
                    (self._save_variable(c, k, v, l), entry_edit.grid_remove())
            )
            btn_save.grid(row=row, column=2, sticky="w", padx=15)
            
            btn_cancel = ttk.Button(self.frame_main, text="Cancel", 
                command=lambda c=cat, k=key, v=var, l=label: 
                    (self._cancel_edit(c, k, v, l), entry_edit.grid_remove())
            )
            btn_cancel.grid(row=row, column=3, sticky="w", padx=15)
            

    def _save_variable(self, cat: str, key: str, var, label: tk.Label):
        val = var.get()
        APP_CONFIG.set(cat, key, val)

        unit = APP_CONFIG.get_var_struct(cat, key).get("unit", "")
        if unit:
            label.config(text=f"{val} {unit}")
        else:
            label.config(text=val)
        self._cancel_edit(cat, key, var, label)

    
    def _cancel_edit(self,  cat: str, key: str, var, label: tk.Label):
        row = label.grid_info()["row"]

        # Remove Entry, Save & Cancel buttons
        self._remove_widgets_in_cell(self.frame_main, row, 2)
        self._remove_widgets_in_cell(self.frame_main, row, 3)
        
        # Place value label & Edit button
        label.grid(row=row, column=1)
        btn_edit = ttk.Button(self.frame_main, text="Edit", 
            command=lambda c=cat, k=key, v=var, l=label: self._set_variable(c, k, v, l))
        btn_edit.grid(row=row, column=2, sticky="w", padx=15)
            
    def _remove_widgets_in_cell(self, frame, row, col):
        for widget in frame.grid_slaves(row=row, column=col):
            widget.grid_forget() 
            
    def _goto_folder(self, subpath):
        path = APP_CONFIG.BASE_DIR / subpath
        folder = path.parent

        if folder.exists() and folder.is_dir():
            webbrowser.open(str(folder))
        else:
            messagebox.showwarning("Folder not found", f"Folder does not exist:\n{folder}")
            

        
        
                