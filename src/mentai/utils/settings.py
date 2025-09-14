import contextlib
import os
import sys
import webbrowser
from pathlib import Path

import toml
from platformdirs import user_config_dir

from .logger import get_logger
from .types import Settings

# Initialize logger
logger = get_logger()

# Project name
_PROJECT_NAME = "MentAI"

# Default settings configuration
SETTINGS_DIR = Path(user_config_dir(_PROJECT_NAME))
SETTINGS_FILE = SETTINGS_DIR / "config.toml"
SETTINGS: Settings = {
    "SOLVER": {
        "OPEN_AI_API_KEY": "",
        "OPEN_AI_MODEL": "gpt-5",
    },
    "QUIZ": {
        "PLAYER_NAME": "",
        "MINIMUM_DELAY_IN_MS": 500,
        "MAXIMUM_DELAY_IN_MS": 3000,
        "CONTEXT": "",
    },
}


# ----- Helper Functions -----
def notify_new_settings_file(is_corrupt: bool = False):
    """
    Creates a new settings file. Sends a notification and short explanation
    to the console.
    Exits the programm with exit code 1.

    Args:
        is_corrupt (bool, optional): If a settings file exists but is corrupt.
                                     Defaults to False.
    """
    logger.error(
        "Corrupt settings file." if is_corrupt else "Settings file not found."
    )
    logger.debug(
        'Creating empty template in "%s". Opening it...',
        SETTINGS_FILE,
    )
    SETTINGS_DIR.mkdir(
        parents=True, exist_ok=True
    )  # to create directory if it doesn't exist
    with open(SETTINGS_FILE, mode="w") as f:
        toml.dump(SETTINGS, f)
    with contextlib.suppress(Exception):
        webbrowser.open(f"file://{SETTINGS_FILE.absolute()}")
    logger.debug(
        "Please do not remove any keys and only fill your values in between "
        "the given quotes or as a numeric value."
    )
    logger.debug("Add your OpenAI API key and restart the program.")
    logger.debug(
        "All other values can be left as is. "
        "Refer to the Documentation for more information."
    )
    logger.debug("Exiting...")
    sys.exit(1)


# Create settings file if it doesn't exist
if not os.path.exists(SETTINGS_FILE):
    notify_new_settings_file()


def load_settings() -> Settings:
    """
    Validates and loads the settings from the settings file.
    """
    settings: Settings
    with open(SETTINGS_FILE) as f:
        try:
            settings: Settings = toml.load(f)  # type: ignore
        except (TypeError, toml.TomlDecodeError):
            notify_new_settings_file(is_corrupt=True)

    # Check existence of first level keys
    for category, category_key_value_pairs in SETTINGS.items():
        if category not in settings:
            notify_new_settings_file(is_corrupt=True)

        # Check type of first level keys
        if type(settings[category]) is not type(SETTINGS[category]):
            notify_new_settings_file(is_corrupt=True)

        # Check existence of second level keys
        for key2 in SETTINGS[category]:
            if key2 not in settings[category]:
                notify_new_settings_file(is_corrupt=True)

            # Check type of second level keys
            if type(settings[category][key2]) is not type(
                category_key_value_pairs[key2]  # type: ignore
            ):
                notify_new_settings_file(is_corrupt=True)

    # Specific checks
    exit: bool = False
    error_count: int = 0
    if len(settings["QUIZ"]["CONTEXT"]) > 0 and not os.path.isfile(
        settings["QUIZ"]["CONTEXT"]
    ):
        logger.error("Value of 'CONTEXT' is not a valid file path.")
        exit = True
        error_count += 1

    if settings["SOLVER"]["OPEN_AI_API_KEY"] == "":
        logger.error("OpenAI API key is missing.")
        exit = True
        error_count += 1

    if exit:
        logger.debug(
            "Please fix the error%s and restart the program.",
            "s" if error_count > 1 else "",
        )
        logger.debug(
            'You can find your settings file in: "%s". Opening it...',
            SETTINGS_FILE,
        )
        with contextlib.suppress(Exception):
            webbrowser.open(f"file://{SETTINGS_FILE.absolute()}")
        sys.exit(1)

    return settings
