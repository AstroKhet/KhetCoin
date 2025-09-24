import tkinter as tk
import tkinter.font as font

# For easy binding of widgets that may stack on top of each other
def bind_hierarchical(sequence: str, widget, cb):
    widget.bind(sequence, cb)
    for child in widget.winfo_children():
        bind_hierarchical(sequence, child, cb)


def mousewheel_cb(event, canvas):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# Entry Prompt Text
def bind_entry_prompt(entry, prompt):
    entry.insert(0, prompt)
    entry.config(fg="grey", font=font.Font(family="Arial", size=10, slant="italic"))
    entry.bind("<FocusIn>", lambda e: entry_on_focus_in(e, prompt))
    entry.bind("<FocusOut>", lambda e: entry_on_focus_out(e, prompt))

def entry_on_focus_in(event, prompt):
    entry = event.widget
    if entry.get() == prompt:
        entry.delete(0, tk.END)
        entry.config(fg="black", font=("Aria", 10))

def entry_on_focus_out(event, prompt):
    entry = event.widget
    if not entry.get():
        entry.insert(0, prompt)
        entry.config(fg="grey", font=font.Font(family="Arial", size=10, slant="italic"))
