import logging

from rich import get_console
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Variables
_LEVEL: int = logging.DEBUG
_LOGGER_NAME: str = "Menti"
_DEV_MODE: bool = False
_DEV_LOGGER_NAME: str = "Dev"

# Retrieve Rich Console
console: Console = get_console()


class RichHandler(logging.StreamHandler):
    """
    Custom StreamHandler to colorize the logging messages based on the log
    level.

    Args:
        logging (_type_): logging.StreamHandler
    """

    # Mapping of the logging levels to the Rich colors
    FORMATS = {
        logging.DEBUG: "white",
        logging.INFO: "dark_green",
        logging.WARNING: "orange1",
        logging.ERROR: "red",
        logging.CRITICAL: "bold red",
    }

    def __init__(self, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Formats a log message and prints it to the Rich console.

        Args:
            record (logging.LogRecord): Log record to format and print.
        """
        style = self.FORMATS.get(record.levelno, "white")

        # If message is a normal string
        if isinstance(record.msg, str):
            console.print(self.format(record), style=style, highlight=False)

        # If message is of a different type (e.g. Panel)
        elif isinstance(record.msg, Panel | Table):
            console.print(record.msg, style=style)


# Stream handler setup
stream_handler = RichHandler()

# Logger setup
logger = None


def get_logger() -> logging.Logger:
    """
    Returns the default logger for the application.

    Returns:
        logging.Logger: Logger for the main application.
    """
    global logger
    if logger is None:
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(_LEVEL)
        logger.addHandler(stream_handler)
    return logger


# Dev Logger setup
dev_logger = None


def enable_dev_mode():
    """
    Enables the developer mode for the application.
    Adds a new logger used for debugging purposes.
    Adds additional formatting with more details to both loggers.
    """
    global _DEV_MODE, dev_logger
    _DEV_MODE = True
    dev_logger = logging.getLogger(_DEV_LOGGER_NAME)
    dev_logger.setLevel(logging.DEBUG)
    dev_logger.addHandler(stream_handler)

    # Increase log details
    debug_formatter = logging.Formatter(
        fmt=(
            "{asctime}.{msecs:03.0f} - {levelname} - {filename}:{lineno} - "
            "{message}"
        ),
        datefmt="%H:%M:%S",
        style="{",
    )
    stream_handler.setFormatter(debug_formatter)


def get_dev_logger() -> logging.Logger | None:
    """
    Getter function for the dev logging.

    Returns:
        logging.Logger | None: Dev logger if dev mode is enabled, else None.
    """
    return dev_logger
