
def main():
    from utils.config import APP_CONFIG

    if not APP_CONFIG.get("app", "initial_setup"):
        from setup.setup import SetupApp
        from setup.functions import INITIAL_SETUP, RUNTIME_SETUP

        setup_app = SetupApp()
        setup_app.main()
        INITIAL_SETUP()

    RUNTIME_SETUP()

    from gui.app import KhetcoinApp

    node_kwargs = {
        "name": APP_CONFIG.get("node", "name"),
        "host": "0.0.0.0",
        "port": APP_CONFIG.get("node", "port")
    }

    app = KhetcoinApp(**node_kwargs)
    app.main()


if __name__ == "__main__":
    main()