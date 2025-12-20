from setup.initializer import init_folders, init_font
from setup.functions import INITIAL_SETUP, RUNTIME_SETUP

def main():
    from utils.config import APP_CONFIG

    if not APP_CONFIG.get("app", "initial_setup"):
        try:
            from setup.setup import SetupApp
            from setup.initializer import init_db
    
            init_folders()
            setup_app = SetupApp()
            setup_app.main()
            print("call init db")
            init_db()
            init_font()

            
            APP_CONFIG.set("app", "initial_setup", True)
        except Exception as e:
            print(f"Initial setup failed: {e}")
            return

    RUNTIME_SETUP()
    from gui.app import KhetcoinApp

    node_kwargs = {
        "name": APP_CONFIG.get("app", "name"),
        "port": APP_CONFIG.get("node", "port")
    }

    app = KhetcoinApp(**node_kwargs)
    app.main()


if __name__ == "__main__":
    main()