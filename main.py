from gui.app import KhetcoinApp
from setup.setup import SetupApp
from networking.node import Node
from setup.functions import INITIAL_SETUP, RUNTIME_SETUP
from utils.config import APP_CONFIG

node_kwargs = {"name": "Khet", "host": "127.0.0.1", "port": 8888}
# node_kwargs = {"name": APP_CONFIG.get("node", "name"), "host": APP_CONFIG.get("node", "name")}

def main():
    if not APP_CONFIG.get("app", "initial_setup"):
        setup_app = SetupApp()
        setup_app.main()
        INITIAL_SETUP()
    
        # Run the initial setup sequence
    RUNTIME_SETUP()
    
    app = KhetcoinApp(**node_kwargs)
    
    print("main")
    app.main()
    print("main finish")


if __name__ == "__main__":
    main()
