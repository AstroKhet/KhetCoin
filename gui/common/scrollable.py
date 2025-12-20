import tkinter as tk
from tkinter import ttk


def create_scrollable_treeview(parent, tree_cols: dict[str, tuple[str, int]], pos: tuple[int, int], xscroll: bool = True):
    """Creates a treeview based on the given `tree_cols` and grid `pos` within the `parent`."""
    treeview = ttk.Treeview(
        parent,
        columns=list(tree_cols.keys()),
        show="headings",
        selectmode="browse",
    )
    
    treeview.grid(row=pos[0], column=pos[1], sticky="nsew")
    for key, (title, width) in tree_cols.items():
        treeview.heading(key, text=title, anchor="w")
        treeview.column(key, width=width, anchor="w")

    vsb = ttk.Scrollbar(parent, orient="vertical", command=treeview.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    treeview.configure(yscrollcommand=vsb.set)

    if xscroll:
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=treeview.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        treeview.configure(xscrollcommand=hsb.set)
        
    return treeview


def create_scrollable_frame(parent, yscroll=True, xscroll=True, return_canvas=True):
    """
    Creates a frame contained within `parent` that has scrolling features. This means its position is the same as `parent`, i.e. there's no need to grid this frame.
    \nUse `return_canvas` for future mousewheel bindings if more widgets are added.
    """
    cnv = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
    cnv.grid(row=0, column=0, sticky="nsew")

    if yscroll:
        vsb = ttk.Scrollbar(parent, orient="vertical", command=cnv.yview)
        vsb.grid(row=0, column=1, sticky="ns") 
        cnv.configure(yscrollcommand=vsb.set)
    
    if xscroll:
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=cnv.xview)
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew")
        cnv.configure(xscrollcommand=vsb.set)

    frame = tk.Frame(cnv)
    frame.bind("<Configure>", lambda _: cnv.configure(scrollregion=cnv.bbox("all")))
    
    win = cnv.create_window((0, 0), window=frame, anchor="nw") 
    cnv.bind("<Configure>", lambda e: cnv.itemconfig(win, width=e.width))
    
    if return_canvas:
        return frame, cnv
    else:
        return frame
