import sys
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from rich.panel import Panel

from mentai.utils.decorators import catch_exceptions
from mentai.utils.logger import enable_dev_mode, get_logger
from mentai.utils.types import Settings

# Retrieve logger
logger = get_logger()


# Entry point
def cli():
    """
    Entry point of the program. Wrapper for the main function.

    CLI Arguments / Options:
        participation_code (str): Participation code of the Menti quiz.
        player_name (Optional[str]): Name of the player. If None, the name of
                                     the settings file will be used.
                                     If both values are None, the randomly
                                     generated Menti name will be used.
        additional_context (Optional[str]): Additional context to use for
                                            solving the questions. If None,
                                            the context from the settings file
                                            will be used.
                                            If both values are None, no
                                            additional context will be used.
        dev_mode (Optional[bool]): If True, additional logging outputs for
                                   debugging will be activated. Defaults to
                                   False.
    """
    typer.run(main)


@catch_exceptions
def main(
    participation_details: Annotated[
        str,
        typer.Argument(
            help="Participation code / link of the Menti quiz.",
            metavar="Participation Details",
        ),
    ],
    player_name: Annotated[
        str | None,
        typer.Option(
            "-n",
            "--name",
            help="Name to use for the player if custom names are allowed.",
            metavar="Name",
        ),
    ] = None,
    additional_context: Annotated[
        Path | None,
        typer.Option(
            "-a",
            "--additional-context",
            help=(
                "Path to a text file containing additional context to add to "
                "the prompt for solving questions."
            ),
            metavar="Addtional Context",
            exists=True,
            file_okay=True,
            readable=True,
            allow_dash=True,
        ),
    ] = None,
    dev_mode: Annotated[
        bool,
        typer.Option(
            "-d",
            "--dev",
            help=("Activate additional logging outputs for debugging."),
            hidden=True,
        ),
    ] = False,
):
    """
    An automated CLI tool using AI to solve Menti quiz questions.
    """  # This message is shown when using the `--help` flag.

    # Set dev mode
    if dev_mode:
        enable_dev_mode()

    # Validate participation code format
    valid_code: bool = False
    participation_details = participation_details.strip().replace(" ", "")
    if participation_details.isdigit() and len(participation_details) == 8:
        valid_code = True

    # Validate participation link format
    else:
        try:
            url = urlparse(participation_details)
            valid_url: bool = all([url.scheme, url.netloc])
        except AttributeError:
            pass

        # Exit with detail console output
        if not valid_url:
            logger.critical("Invalid participation details.")
            logger.debug(
                "Participation code must be an 8-digit number. "
                "Participation link must be a valid URL, e.g.: "
                "https://www.menti.com/abcdefghijkl"
            )
            sys.exit(1)

    # Load settings (import here to load the correct logger and speed up start)
    from mentai.utils.settings import load_settings

    settings: Settings = load_settings()

    # Load delays
    minimum_delay_in_ms = settings["QUIZ"]["MINIMUM_DELAY_IN_MS"]
    maximum_delay_in_ms = settings["QUIZ"]["MAXIMUM_DELAY_IN_MS"]

    # Load player name
    if player_name is None:
        player_name = settings["QUIZ"]["PLAYER_NAME"]

    # Load additional context
    if additional_context is not None:
        with open(additional_context) as file:
            additional_context_string = file.read().strip()
    else:
        if len(settings["QUIZ"]["CONTEXT"]) > 0:
            additional_context = Path(settings["QUIZ"]["CONTEXT"])
            with open(additional_context) as file:
                additional_context_string = file.read().strip()
        else:
            additional_context_string = None

    # Quick info to console
    logger.debug("")
    logger.debug(
        Panel.fit(
            renderable=(
                "Press [bold]Ctrl+C[/] at any time to stop the program."
            ),
            title="Important Note",
            padding=1,
        )
    )
    logger.debug("\nStarting up...")

    # Start flow
    from mentai.menti.menti import MentiSlides

    # Create MentiSlides instance
    menti = MentiSlides(
        open_ai_api_key=settings["SOLVER"]["OPEN_AI_API_KEY"],
        open_ai_model=settings["SOLVER"]["OPEN_AI_MODEL"],
        minimum_delay_in_ms=minimum_delay_in_ms,
        maximum_delay_in_ms=maximum_delay_in_ms,
    )

    # Add participation key from url if not valid code
    if not valid_code:
        menti.participation_key = url.path.split("/")[-1]
        participation_details = ""

    # Load quiz metadata and solve questions
    menti.load_quiz(
        participation_code=participation_details,
        additional_context=additional_context_string,
    )

    # Join quiz and start automated websocket flow
    menti.join_quiz(player_name=player_name)


# Run programm
if __name__ == "__main__":
    cli()
