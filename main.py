
from setup.functions import configure_logging, run_initial_setup
from utils.config import APP_CONFIG


def launch_app() -> None:
    """
    Launch the GUI application.
    """
    from gui.app import KhetcoinApp

    node_kwargs = {
        "name": APP_CONFIG.get("app", "name"),
        "port": APP_CONFIG.get("node", "port")
    }

    app = KhetcoinApp(**node_kwargs)
    app.main()


def main():
    if not APP_CONFIG.get("app", "initial_setup"):
        run_initial_setup()
        
    if APP_CONFIG.get("app", "initial_setup"):
        configure_logging()
        launch_app()


if __name__ == "__main__":
    main()