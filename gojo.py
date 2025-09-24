from gui.main_window import KhetcoinApp
from networking.node import Node


node_kwargs = {
    "name": "Gojo Satoru",
    "host": "127.0.0.1",
    "port": 9999
}

def main():
    node = Node(**node_kwargs)
    app = KhetcoinApp(node)
    
    app.main()
    

if __name__ == "__main__":
    main()

