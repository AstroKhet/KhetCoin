from gui.main_window import KhetcoinApp
from networking.node import Node
from utils.setup import RUNTIME_SETUP

node_kwargs = {"name": "Khet", "host": "127.0.0.1", "port": 8888}


def main():
    RUNTIME_SETUP()
    
    node = Node(**node_kwargs)
    app = KhetcoinApp(node)

    app.main()


if __name__ == "__main__":
    main()
