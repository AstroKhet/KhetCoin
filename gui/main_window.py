import asyncio
import logging
import threading
import tkinter as tk

from tkinter import messagebox

from gui.config import MENU_CONFIG
from gui.frames import FRAMES_CONFIG
from networking.node import Node

log = logging.getLogger(__name__)

# TODO logging

class KhetcoinApp:
    """
    Main Interface for Khetcoin
    - Controls both the GUI and Node event loops
    """
    def __init__(self, node: Node):
        self.node = node

        self.node_loop = asyncio.new_event_loop()
        self.node_thread = threading.Thread(target=self._run_node_loop, daemon=True)
        self.node_thread.start()

        self.root = tk.Tk()
        self.root.title(f"{node.name}'s Node")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.view_container = tk.Frame(self.root)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.view_container.grid_rowconfigure(0, weight=1)
        self.view_container.grid_columnconfigure(0, weight=1)

        dashboard = FRAMES_CONFIG["dashboard"](parent=self.view_container, controller=self, node=node)
        dashboard.grid(row=0, column=0, sticky="nsew")
        self.frames = {"dashboard": dashboard}

        self._setup_menu()
        self.current_frame_name = "dashboard"
        self.switch_to_frame(self.current_frame_name)
        log.info("KhetcoinApp successfully started")

    def _run_node_loop(self):
        """Target function for the node thread to run the asyncio loop."""
        asyncio.set_event_loop(self.node_loop)
        self.node_loop.run_forever()
        print("Node asyncio loop stopped.")  # Added for debugging

    def start_node(self):
        """Starts the node's run method in the node's event loop."""
        # Check if the node's run task is already active to prevent multiple starts
        # A simple way is to check if the node's server is running or if there's an active run task
        if self.node.server is not None:
            print("Node is already running.")
            return

        print("Requesting node start...")
        # Submit the node.run() coroutine to the node's event loop
        # This will start the server and other node tasks within the node_loop
        asyncio.run_coroutine_threadsafe(self.node.run(), self.node_loop)
        print("Node start requested.")  # Added for debugging

    def close_node(self):
        """Signals the node to shut down gracefully."""
        # Signal the node to shut down gracefully
        print("Requesting node shutdown...")
        asyncio.run_coroutine_threadsafe(self.node.shutdown(), self.node_loop)
        # IMPORTANT: Do NOT stop the node_loop here. It needs to keep running
        # so that the node can be started again later.
        print("Node shutdown signal sent.")  # Added for debugging

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

                label = self._format_title(option)
                if option == "exit":
                    menu.add_command(label=label, command=self._on_closing)
                else:
                    menu.add_command(
                        label=label,
                        command=lambda frame_name=option: self.switch_to_frame(frame_name),
                    )

    def switch_to_frame(self, frame_name, **kwargs):
        dispaly_frame_name = self._format_title(frame_name)
        
        def switch():
            frame = self.frames[frame_name]
            frame.tkraise()
            self.root.title(f"{self.node.name}'s Node - {dispaly_frame_name}")
        def create():
            frame_class = FRAMES_CONFIG[frame_name]
            frame = frame_class(parent=self.view_container, controller=self, node=self.node, **kwargs)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[frame_name] = frame
            frame.tkraise()
            self.root.title(f"{self.node.name}'s Node - {dispaly_frame_name}")
            
        try:  # Attempt to retrieve already created frame
            if kwargs:  # Forceful recreation of frame
                create()
            else:
                switch()
        except KeyError: # Create frame
                create()

    def main(self):
        self.root.mainloop()
        print("Tkinter mainloop exited.")
        # Ensure the node loop is stopped when the Tkinter app exits
        if self.node_loop.is_running():
            print("Stopping node asyncio loop from main.")
            self.node_loop.call_soon_threadsafe(self.node_loop.stop)
        # Wait for the node thread to finish
        self.node_thread.join(timeout=5)  # Add a timeout for joining
        if self.node_thread.is_alive():
            print("Warning: Node thread did not join gracefully.")
        else:
            print("Node thread joined successfully.")

    def _on_closing(self):
        if messagebox.askokcancel(
            "Quit", f"Shut down {self.node.name}'s node and exit?"
        ):
            print("User confirmed shutdown. Initiating full application exit.")
            asyncio.run_coroutine_threadsafe(self.node.shutdown(), self.node_loop)
            self.node_loop.call_soon_threadsafe(self.node_loop.stop)
            self.root.destroy()
            print("Tkinter root destroyed.")

    def _format_title(self, title):
         return " ".join(w[0].upper() + w[1:] for w in title.split("_"))