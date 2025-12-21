
def main():
    
    from setup.functions import RUNTIME_SETUP, INITIAL_SETUP
    from utils.config import APP_CONFIG

    if not APP_CONFIG.get("app", "initial_setup"):
        try:
            INITIAL_SETUP()
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