import os
import tkinter as tk
import webbrowser

from gui.colours import KHET_ORANGE_LIGHT
from gui.fonts import SansFont
from gui.helper import add_hover_effect
from ktc_constants import KTC_VERSION
from utils.config import APP_CONFIG
from utils.fmt import format_snake_case

_frame_id = 1

class DashboardFrame(tk.Frame):
    def __init__(self, parent, controller, node):
        super().__init__(parent)
        
        self.node = node
        self.controller = controller
        
        self.icon_path = APP_CONFIG.get("path", "assets") / "icons" / "96px"
        
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # 1. Hello, User!
        label_greeting = tk.Label(self, text=f"Hello, {self.node.name}", font=SansFont(20, weight="bold"))
        label_greeting.grid(row=0, column=0, sticky="n", pady=(8, 0))
        
        # 1.1 Version
        label_version = tk.Label(self, text=f"KhetCoin v{KTC_VERSION}", font=SansFont(9), fg="gray")
        label_version.grid(row=1, column=0, sticky="n", pady=(0, 6))

        # 2. Main dashboard menu
        frame_center_container = tk.Frame(self)
        frame_center_container.grid(row=2, column=0, sticky="nsew")

        # 2.1 Centering the menu in the middle
        frame_center_container.columnconfigure(0, weight=1)  # left expander
        frame_center_container.columnconfigure(1, weight=0)  # middle fixed
        frame_center_container.columnconfigure(2, weight=1)  # right expander
        frame_center_container.rowconfigure(0, weight=1)

        self.frame_menu = tk.Frame(frame_center_container)
        self.frame_menu.grid(row=0, column=1, sticky="n")

        options = [
            "view_blockchain", "node", "mining", "your_wallet", 
            "pay", "saved_addresses", "saved_peers", "settings"
        ]

        self.menu_cols = 4
        self.menu_rows = (len(options) + self.menu_cols - 1) // self.menu_cols

        self.menu_btn_size = 96

        for c in range(self.menu_cols):
            self.frame_menu.columnconfigure(c, minsize=self.menu_btn_size, weight=0)
        for r in range(self.menu_rows):
            self.frame_menu.rowconfigure(r, minsize=self.menu_btn_size, weight=0)

        # 2.2  Create buttons with icons
        self._menu_images = []
        for idx, option in enumerate(options):
            command = lambda opt=option: self.controller.switch_to_frame(opt)
            self._put_button(idx, option, command)

        # 2.3 Extra buttons
        feedback_cmd = lambda: webbrowser.open("https://forms.gle/n9WrY7BvTkek2S1i9")
        self._put_button(idx+1, "feedback", feedback_cmd)
        
        guide_cmd = lambda: webbrowser.open("https://docs.google.com/document/d/1ADRmDofa2dM5rW36-aAL2re6DPIrsnATmU68HgwWk7s/edit?usp=sharing")
        self._put_button(idx+2, "guide", guide_cmd)
        
        github_cmd = lambda: webbrowser.open("https://github.com/AstroKhet/Khetcoin")
        self._put_button(idx+3, "github", github_cmd)
        
    def _put_button(self, idx, option, command):
        r = idx // self.menu_cols
        c = idx % self.menu_cols

        cell = tk.Frame(self.frame_menu, width=self.menu_btn_size, height=self.menu_btn_size)
        cell.grid(row=r, column=c, padx=5, pady=5)
        cell.grid_propagate(False)
        
        icon_path = os.path.join(self.icon_path, f"{option}.png")
        try:
            img = tk.PhotoImage(file=icon_path)
        except Exception:
            img = tk.PhotoImage(width=1, height=1)  # tiny placeholder if missing
        self._menu_images.append(img)
        
        # This is more of a hack to get more concise button names but if it works it works
        if '_' in option:
            name = option[option.index('_')+1:]
        else:
            name = option

        btn = tk.Button(
            cell,
            image=img, text=format_snake_case(name), compound="top",
            command=command,
            bg="white", activebackground="white",
            relief="flat", bd=0, highlightthickness=0, 
            padx=12, pady=9,
            font=SansFont(12, weight="bold")
        )
        
        btn.pack(expand=True, fill="both")
        add_hover_effect(btn, normal_bg="white", hover_bg=KHET_ORANGE_LIGHT)      
        

