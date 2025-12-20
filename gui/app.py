import asyncio
import logging
import threading
import tkinter as tk
import sys

from tkinter import messagebox

from gui.frames import FRAMES_CONFIG, MENU_CONFIG
from networking.node import Node
from utils.config import APP_CONFIG
from utils.fmt import format_snake_case

log = logging.getLogger(__name__)

# TODO logging

class KhetcoinApp:
    """
    Main Interface for Khetcoin
    - Controls both the GUI and Node event loops
    """
    def __init__(self, **node_kwargs):
        self.node_loop = asyncio.new_event_loop()
        self.node_thread = threading.Thread(target=self._run_node_loop, daemon=True)
        self.node_thread.start()
        
        self.node = Node(**node_kwargs, loop=self.node_loop)

        self.root = tk.Tk()
        self.root.title(f"{self.node.name}'s Node")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.view_container = tk.Frame(self.root)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.view_container.rowconfigure(0, weight=1)
        self.view_container.columnconfigure(0, weight=1)

        dashboard = FRAMES_CONFIG["dashboard"](parent=self.view_container, controller=self, node=self.node)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.frames = {"dashboard": dashboard}
        
        if APP_CONFIG.get("app", "run_node_on_startup"):
            self.start_node()

        self._setup_menu()
        self.current_frame = None
        self.current_frame_name = "dashboard"
        self.switch_to_frame(self.current_frame_name)
        log.info("KhetcoinApp successfully started")

    def _run_node_loop(self):
        """Target function for the node thread to run the asyncio loop."""
        asyncio.set_event_loop(self.node_loop)
        self.node_loop.run_forever()
        log.debug("Node asyncio loop stopped.")

    def start_node(self):
        """Starts the node's run method in the node's event loop."""
        if self.node.server is not None:
            log.warning("Node is already running.")
            return

        asyncio.run_coroutine_threadsafe(self.node.run(), self.node_loop)
        log.info("Node start requested.")

    def close_node(self):
        """Signals the node to shut down gracefully."""

        asyncio.run_coroutine_threadsafe(self.node.shutdown(), self.node_loop)
        log.info("Node shutdown signal sent.")

    def _setup_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        for menu_info in MENU_CONFIG:
            menu_name = menu_info["name"].capitalize()
            menu_options = menu_info["options"]

            menu = tk.Menu(menu_bar, tearoff=0)
            menu_bar.add_cascade(label=menu_name, menu=menu)

            for option in menu_options:
                if option is None:
                    menu.add_separator()
                    continue

                label = format_snake_case(option)
                if option == "exit":
                    menu.add_command(label=label, command=self._on_closing)
                else:
                    menu.add_command(
                        label=label,
                        command=lambda frame_name=option: self.switch_to_frame(frame_name),
                    )

    def switch_to_frame(self, frame_name, **kwargs):
        display_frame_name = format_snake_case(frame_name)

        # 1. Get / Create frame
        frame = self.frames.get(frame_name)
        if frame is None or kwargs: 
            frame_class = FRAMES_CONFIG[frame_name]
            frame = frame_class(parent=self.view_container, controller=self, node=self.node, **kwargs)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[frame_name] = frame

        # 2. Config grames with on_hide / on_show
        if hasattr(self.current_frame, "on_hide"):
            self.current_frame.on_hide()
        if hasattr(frame, "on_show"):
            frame.on_show()

        # 3. Config window
        frame.tkraise()
        self.current_frame = frame
        self.current_frame_name = frame_name
        self.root.title(f"{self.node.name}'s Node - {display_frame_name}")

    def main(self):
        if sys.version_info < (3, 8):
            messagebox.showerror("Invalid python version!", "Python 3.8 or newer is required", detail=f"Your current python version is:\n\n {sys.version}")
            log.error(f"Invalid python version: {sys.version_info } < 3.8")
            return
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            log.warning("Keyboard interrupt shutdown.")
            self._shutdown()
            
        log.info("KhetCoin App shutdown complete.")
        
    def _on_closing(self):
        if messagebox.askokcancel("Quit", f"Shut down {self.node.name}'s node and exit?"):
            self._shutdown()

    def _shutdown(self):
        asyncio.run_coroutine_threadsafe(self.node.shutdown(), self.node_loop)
        self.node_loop.call_soon_threadsafe(self.node_loop.stop)
        self.node.miner.shutdown()
        self.root.destroy()
