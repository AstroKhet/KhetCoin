import tkinter as tk

class SavedPeersFrame(tk.Frame):
    def __init__(self, parent, controller, node):
        super().__init__(parent)

        label = tk.Label(self, text="Saved Peers", font=("Arial", 16))
        label.pack(padx=20, pady=20, anchor="center")

        
