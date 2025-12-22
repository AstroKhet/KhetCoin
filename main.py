import logging

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
    """
    Main entry point.
    """
    logger = configure_logging()

    try:
        run_initial_setup(logger)
    except Exception:
        logger.error("Aborting due to setup failure")
        return

    launch_app()


if __name__ == "__main__":
    main()