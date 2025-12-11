from gui.main_window import KhetcoinApp
from utils.setup import RUNTIME_SETUP


node_kwargs = {
    "name": "Gojo Satoru",
    "host": "127.0.0.1",
    "port": 9999
}

def main():
    RUNTIME_SETUP("gojo")
    app = KhetcoinApp(**node_kwargs)
    
    app.main()
    

if __name__ == "__main__":
    main()

