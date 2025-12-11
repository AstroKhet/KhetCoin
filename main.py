from gui.main_window import KhetcoinApp
from networking.node import Node
from utils.setup import RUNTIME_SETUP
from utils.config import APP_CONFIG

node_kwargs = {"name": "Khet", "host": "127.0.0.1", "port": 8888}
# node_kwargs = {"name": APP_CONFIG.get("node", "name"), "host": APP_CONFIG.get("node", "name")}

def main():
    RUNTIME_SETUP("khet")
    
    app = KhetcoinApp(**node_kwargs)

    app.main()


if __name__ == "__main__":
    main()
