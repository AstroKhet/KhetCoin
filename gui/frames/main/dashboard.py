import tkinter as tk

class DashboardFrame(tk.Frame):

    def __init__(self, parent, controller, node):
        super().__init__(parent)

        label = tk.Label(self, text="Welcome to the Khetcoin", font=("Arial", 16))
        label.pack(padx=20, pady=20, anchor="center")

        
