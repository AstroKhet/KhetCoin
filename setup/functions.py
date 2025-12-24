import logging
from utils.config import APP_CONFIG


def configure_logging() -> logging.Logger:
    """
    Configure the logging system and return a logger for this module.
    """
    log_path = APP_CONFIG.get("path", "log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - "
            "%(funcName)s() - "
            "%(message)s"
        ),
        filename=log_path,
        filemode="w",
        force=True,
    )


def run_initial_setup() -> None:
    """
    Perform initial setup if it has not already been done.
    Sets up folders, database, fonts, and runs SetupApp.
    """
    if APP_CONFIG.get("app", "initial_setup"):
        return

    try:
        from setup.setup import SetupApp
        from setup.initializer import init_db, init_folders, init_font

        init_folders()
        setup_app = SetupApp()
        setup_app.main()
        init_db()
        init_font()

        APP_CONFIG.set("app", "initial_setup", True)

    except Exception as e:
        print(f"Initial setup failed {e}")
        raise

