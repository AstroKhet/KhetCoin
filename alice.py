from gui.main_window import KhetcoinApp
from networking.node import Node

node_kwargs = {
    "name": "Alice",
    "host": "127.0.0.1",
    "port": 8888
}

def main():
    node = Node(**node_kwargs)
    app = KhetcoinApp(node)
    
    app.main()
    

if __name__ == "__main__":
    main()
