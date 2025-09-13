import asyncio
import sys
from random import randint
from time import sleep

import requests
from fake_useragent import UserAgent

from mentai.menti.solver import OpenAISolver
from mentai.menti.websocket import SocketIOClient
from mentai.utils.logger import get_logger
from mentai.utils.types import (
    Answers,
    PlayerDetails,
    Quiz,
    SlideDeck,
    VotingData,
)

# Retrieve logger
logger = get_logger()


class MentiSlides:
    def __init__(
        self,
        open_ai_api_key: str,
        open_ai_model: str,
        minimum_delay_in_ms: int,
        maximum_delay_in_ms: int,
    ):
        # Initialize requests session
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": UserAgent().random,
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;"
                "q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, zstd",
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )

        # Load homepage to fetch cookies
        self._session.get("https://www.menti.com/")

        # Initialization variables
        self._open_ai_api_key = open_ai_api_key
        self._open_ai_model = open_ai_model
        self._minimum_delay_in_ms = minimum_delay_in_ms
        self._maximum_delay_in_ms = maximum_delay_in_ms

        # Other variables
        self.participation_key: str
        self._identifier: str
        self._quiz_details: Quiz
        self._slide_deck_details: SlideDeck
        self._answers: Answers
        self._player_details: PlayerDetails

    def _set_identifier(self) -> None:
        """
        Fetches the identifier for the player and stores it in the identifier
        attribute.
        """
        self._session.headers.update(
            {
                "Accept": "*/*",
                "Origin": "https://www.menti.com",
                "Referer": "https://www.menti.com/",
            }
        )
        response = self._session.post("https://www.menti.com/core/identifiers")
        self._session.headers.pop("Origin")
        self._identifier = response.json()["identifier"]

    def _set_participation_key(self, participation_code: str) -> None:
        """
        Fetches the participation key for the quiz and stores it in the
        participation_key attribute.
        """
        self._session.headers.update({"Accept": "*/*"})
        response = self._session.get(
            url=(
                f"https://www.menti.com/core/audience/"
                f"slide-deck/{participation_code}/participation-key"
            ),
        )
        try:
            self.participation_key = response.json()["participation_key"]
        except KeyError:
            logger.error("Invalid participation code.")
            logger.debug("Please check the code and try again.")
            sys.exit(1)

    def _set_quiz_details(self) -> None:
        """
        Fetches the quiz details (including all of the questions) and stores
        them in the quiz_details attribute.
        """
        self._session.headers.update({"Accept": "application/json"})
        response = self._session.get(
            url=(
                f"https://www.menti.com/core/audience/slide-deck/"
                f"{self.participation_key}"
            ),
            params={"source": "voteCode"},
        )
        self._quiz_details = response.json()
        self._slide_deck_details = self._quiz_details["slide_deck"]

    def _set_answers(self, additional_context: str | None) -> None:
        """
        Solves the slides and stores them in the answers attribute.

        Args:
            additional_context (Optional[str]): Additional context to use for
                                                solving the questions.
        """
        solver = OpenAISolver(
            api_key=self._open_ai_api_key,
            model=self._open_ai_model,
            additional_context=additional_context,
        )
        self._answers = asyncio.run(
            solver.solve_slides(self._slide_deck_details["slides"])
        )

    def _set_player_details(self) -> None:
        """
        Fetches the player details and stores them in the player_details
        attribute.
        """
        self._session.headers.update(
            {
                "X-Identifier": self._identifier,
                "Origin": "https://www.menti.com",
                "Referer": (
                    f"https://www.menti.com/{self.participation_key}"
                    f"?source=voteCode"
                ),
            }
        )
        response = self._session.post(
            url=(
                f"https://www.menti.com/core/audience/quiz/"
                f"{self.participation_key}/players"
            ),
            params={"tries": 1},
        )
        self._player_details = {
            "voteKey": self.participation_key,
            "questionPublicKey": self._slide_deck_details["slides"][0][
                "slide_public_key"
            ],
            "identifier": self._identifier,
            "player": response.json(),
            "latency": f"{randint(30, 60)}ms",
            "ioLatency": "-1ms",
        }

    def _set_player_name(self, player_name: str | None) -> None:
        """
        Sets the player name.

        Args:
            player_name (Optional[str]): Name of the player.If None, the
                                         randomly generated Menti name will be
                                         used.
        """
        response = self._session.patch(
            url=(
                f"https://www.menti.com/core/audience/quiz"
                f"/{self.participation_key}/players"
            ),
            json={"name": player_name},
        )
        self._player_details["player"] = response.json()

    def load_quiz(
        self, participation_code: str, additional_context: str | None
    ):
        """
        Loads the quiz and all necessary details.

        Args:
            participation_code (str): Code needed to enter the quiz. If it was
                                      provided by a direct link, it should be
                                      set to an empty string.
            additional_context (Optional[str]): Additional context to use for
                                                solving the questions.
        """
        self._set_identifier()
        if participation_code != "":
            self._set_participation_key(participation_code)
        self._set_quiz_details()
        self._set_answers(additional_context)

    def join_quiz(self, player_name: str | None):
        """
        Joins the quiz. Starts the WebSocket connection. Fetches random player
        details and sets the player name.
        Sets the voting data, required for answer submission.

        Args:
            player_name (Optional[str]): Name of the player. If None, the
                                         randomly generated Menti name will be
                                         used.
        """
        with SocketIOClient(
            user_agent=self._session.headers["User-Agent"],  # type: ignore
            minimum_delay_in_ms=self._minimum_delay_in_ms,
            maximum_delay_in_ms=self._maximum_delay_in_ms,
        ) as socket_client:
            # Join quiz
            self._set_player_details()
            socket_client.send_payload(
                event="player_join", data=self._player_details, expect_ack=True
            )

            # Set player name (defaults to the emojiName if None)
            self._set_player_name(
                player_name
                if player_name
                else self._player_details["player"]["emojiName"]
            )
            socket_client.send_payload(
                event="player_join", data=self._player_details, expect_ack=True
            )

            # Set voting data
            voting_data: VotingData = {
                slide["slide_public_key"]: {
                    "voteKey": self.participation_key,
                    "questionPublicKey": slide["slide_public_key"],
                    "identifier": self._identifier,
                    "player": self._player_details["player"],
                    "voteTimestamp": None,
                    "vote": {
                        "isMigrated": slide["is_migrated"],
                        "interactiveContentId": slide["interactive_contents"][
                            0
                        ]["interactive_content_id"],
                        "type": slide["static_content"]["type"],
                        "choices": [
                            {
                                "interactiveContentChoiceId": elem[
                                    "interactive_content_choice_id"
                                ]
                            }
                            for elem in list(
                                filter(
                                    lambda choice: choice["title"]
                                    in self._answers[slide["title"]],
                                    slide["interactive_contents"][0][
                                        "choices"
                                    ],
                                )
                            )
                        ],
                    },
                    "clientTimestamps": {"startAt": None, "endAt": None},
                    "latency": f"{randint(50, 100)}ms",
                    "ioLatency": "-1ms",
                }
                for slide in self._slide_deck_details["slides"]
                if slide["static_content"]["type"]
                in ("quiz-choice", "quiz-open")
            }

            # Add value to open questions
            for slide in self._slide_deck_details["slides"]:
                if slide["static_content"]["type"] == "quiz-open":
                    voting_data[slide["slide_public_key"]]["vote"]["choices"][
                        0
                    ]["value"] = self._answers[slide["title"]]  # type: ignore

            # Set data
            socket_client.player_details = self._player_details
            socket_client.voting_data = voting_data
            socket_client.question_keys_answers = {
                question["questionPublicKey"]: {
                    slide["title"]: self._answers[slide["title"]]
                    for slide in list(
                        filter(
                            lambda slide: slide["slide_public_key"]
                            == question["questionPublicKey"],
                            self._slide_deck_details["slides"],
                        )
                    )
                }
                for question in voting_data.values()
            }  # format: {"slide_public_key": {"question": "answer"}}

            # Wait until WebSocket connection is closed
            while socket_client.ns_connected:
                sleep(1)
