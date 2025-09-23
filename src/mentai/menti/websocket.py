import json
import sys
import threading
from random import randint
from time import sleep, time
from typing import Any

from rich.table import Table
from websocket import WebSocketApp

from mentai.utils.logger import get_dev_logger, get_logger
from mentai.utils.types import (
    AckWaiters,
    CallbackArguments,
    CallbackFunction,
    Message,
    MessageData,
    MessageEvent,
    PlayerDetails,
    QuestionKeyAnswersMapping,
    ShownSlides,
    VotingData,
    Waiter,
)

# Add file specific ignores for Pyright
# pyright: reportRedeclaration=false, reportOptionalSubscript=false

# Menti namespace
NAMESPACE = "/quiz2"

# Retrieve loggers
logger = get_logger()
dev_logger = get_dev_logger()


class SocketIOClient:
    def __init__(
        self,
        user_agent: str,
        minimum_delay_in_ms: int,
        maximum_delay_in_ms: int,
    ):
        # Public attributes
        self.ns_connected: bool = False  # to check if namespace is connected

        # to store quiz metadata with player details for request payloads
        self.player_details: PlayerDetails

        # to store solutions for answer submission
        self.voting_data: VotingData

        # to store a mappings for more detailled logging messages
        self.question_keys_answers: QuestionKeyAnswersMapping

        # Private attributes
        self._url = (
            "wss://quiz-api.mentimeter.com/socket.io/"
            "?EIO=4&transport=websocket"
        )
        self._headers = {
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": user_agent,
            "Upgrade": "websocket",
            "Origin": "https://www.menti.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "de-DE,de;q=0.9",
        }
        self._ws: WebSocketApp | None = None  # for WebSocket connection
        self._shown_slides: ShownSlides = {
            "questions": [],
            "leaderboards": [],
        }  # to store previously shown slides and prevent duplicate logging
        # of the same slide
        self._minimum_delay_in_ms = (
            minimum_delay_in_ms  # lowest delay for answer submission
        )
        self._maximum_delay_in_ms = (
            maximum_delay_in_ms  # highest delay for answer submission
        )
        self._next_ack_id: int = 0  # to increment the counter for Ack-IDs
        self._ack_waiters: AckWaiters = {}  # to map Ack-ID to its callback
        # function and arguments

    # ----- Context Manager -----
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ----- Connection Handling -----
    def start(self) -> None:
        """
        Starts the WebSocket connection and waits for the namespace connection
        to be established.
        """
        if not self._ws:
            self._ws = WebSocketApp(
                url=self._url,
                header=self._headers,
                on_message=self._on_message,
                on_open=self._on_open,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            # Start WebSocket connection
            t = threading.Thread(target=self._ws.run_forever, daemon=False)
            t.start()

            # Check for successful connection
            counter = 0
            while not self.ns_connected and counter < 10:
                sleep(0.5)
                counter += 1
            if self.ns_connected:
                if dev_logger:
                    dev_logger.debug("Namespace connection established.")
            else:
                logger.critical(
                    "Connection to Menti server could not be established. "
                    "Quitting..."
                )
                self.stop()
                sys.exit(1)

    def stop(self):
        """
        Closes the WebSocket connection.
        """
        if self._ws:
            self.ns_connected = False
            self._ws.close()

    # ----- Message Handling -----
    def _reserve_ack(
        self,
        ack_cb: CallbackFunction | None,
        cb_args: CallbackArguments | None = None,
    ) -> int:
        """
        Reserves an Ack-ID and increments the counter.
        Maps the Ack-ID to a callback function if needed.

        Args:
            ack_cb (CallbackFunction): Callback function to be called when the
                                       server responds to the Ack-ID.
            cb_args (CallbackArguments, optional): Keyword arguments to pass to
                                                   the callback function.
                                                   Defaults to None.
        Returns:
            int: Reserved Ack-ID.
        """
        ack_id = self._next_ack_id
        self._next_ack_id += 1
        if ack_cb:
            self._ack_waiters[ack_id] = {
                "function": ack_cb,
                "kwargs": cb_args or {},
            }
        return ack_id

    def _send(self, msg: Message):
        """
        Sends a message to the WebSocket if the connection has been
        established.

        Args:
            msg (Message): The message to send.
        """
        if dev_logger:
            dev_logger.debug("Sending message: %s", msg)
        if self._ws:
            self._ws.send(msg)

    def send_payload(
        self,
        event: str,
        data: Any | None = None,
        expect_ack: bool = False,
        ack_cb: CallbackFunction | None = None,
        cb_args: CallbackArguments | None = None,
    ):
        """
        Sends a 42-Event in Namespace of the WebSocketif the connection has
        been established.

        Args:
            event (str): Event to send, e.g. player_vote. This is configured
                         by Menti.
            data (dict, optional): Data to send. Defaults to None.
            expect_ack (bool, optional): Whether to expect an Ack.
                                         Defaults to False.
            ack_cb (CallbackFunction, optional): Callback function to be called
                                                 when the server responds to
                                                 the Ack-ID. Defaults to None.
            cb_args (CallbackArguments, optional): Keyword arguments to pass to
                                                   the callback function.
                                                   Defaults to None.
        """
        payload: (
            list[MessageEvent] | list[tuple[MessageEvent, MessageData]]
        ) = [event] if data is None else [event, data]
        if expect_ack:
            ack_id = self._reserve_ack(ack_cb, cb_args)
            msg: Message = f"42{NAMESPACE},{ack_id}{
                json.dumps(payload, separators=(',', ':'))
            }"
        else:
            msg: Message = (
                f"42{NAMESPACE},{json.dumps(payload, separators=(',', ':'))}"
            )
        self._send(msg)

    # ----- WebSocket-Client Callbacks -----
    def _on_open(self, *_: Any):
        """
        Called when the WebSocket connection is established.
        """
        if dev_logger:
            dev_logger.debug("WebSocket connection established.")

    def _on_error(self, _: Any, error):
        """
        Called when an error occurs in the WebSocket connection.

        Args:
            error (Any): Error that occurred.
        """
        if dev_logger:
            dev_logger.error(
                "WebSocket %s: %s", type(error).__name__, error, exc_info=True
            )

    def _on_close(self, *_: Any):
        """
        Called when the WebSocket connection is closed.
        """
        self.ns_connected = False
        if dev_logger:
            dev_logger.debug("WebSocket connection closed.")

    def _on_message(self, _: Any, msg: Message):
        """
        Called when the WebSocket receives a message. Implements all the
        necessary logic for the Menti quiz flow.
        WebSocket uses the Engine.IO Protocol (Transport Layer):
        https://github.com/socketio/engine.io-protocol.
        Messages are using the Socket.IO Protocol (Application Layer):
        https://socket.io/docs/v4/socket-io-protocol/.

        Args:
            msg (Message): Message received from the WebSocket.
        """
        if dev_logger:
            dev_logger.debug("Received message: %s", msg)

        # Engine.IO Layer
        status_code = msg[0]

        # Initial message after successful connection
        if status_code == "0":
            self._send(f"40{NAMESPACE},")  # join namespace (40/quiz2)
            return

        # Heartbeat mechanism (ping --> pong)
        if status_code == "2":
            self._send("3")
            return

        # Ignore all other codes
        if status_code != "4":
            return

        # Socket.IO Layer (if Code 4, e.g.: 42/quiz2)
        sio_type = msg[1]
        remainder = msg[2:]

        # Namespace connected (40/quiz2)
        if sio_type == "0":
            self.ns_connected = True

        # Namespace disconnected (41/quiz2)
        # Currently not used in recorded requests
        elif sio_type == "1":
            self.ns_connected = False

        # Event (42/quiz2 or 42/quiz2,<Ack-ID>...)
        elif sio_type == "2":
            # Remove namespace prefix
            payload = remainder[(len(NAMESPACE) + 1) :]

            # Fetch Ack-ID if it exists
            ack_id_str = ""
            i = 0
            while payload[i].isdigit():
                ack_id_str += payload[i]
                i += 1

            # Extract JSON part from payload
            json_part = payload[i:]
            data = json.loads(json_part)
            event: MessageEvent = data[0]
            args: MessageData = data[1:] if len(data) > 1 else []

            # Handle response to latency probe
            # Currently not used because the flow works without it,
            # but saved for possible changes in the future.
            # Only the client initiates 'ts:client' pings
            # and the server responds with 'ts:server'.
            #
            # Quiz started is status when next slide is shown.
            if event in ("ts:server", "quiz_started"):
                pass

            # Next question / slide
            elif event == "quiz_created":
                if args[0]["gameState"] in (
                    "lobby",
                    "result",
                    "final_leaderboard",
                ):
                    pass

                # Update quiz metadata and send join request
                current_question_key = args[0]["gameStateData"][
                    "questionPublicKey"
                ]
                self.player_details["questionPublicKey"] = current_question_key
                self.player_details["latency"] = f"{randint(10, 30)}ms"
                self.send_payload(
                    event="player_join",
                    data=self.player_details,
                    expect_ack=True,
                )

            # Countdown for answer submission
            elif event == "quiz_countdown_started":
                current_question_key = args[0]["gameStateData"][
                    "questionPublicKey"
                ]
                start_time: int = args[0]["gameStateData"]["startAt"]
                end_time: int = args[0]["gameStateData"]["endAt"]

                # Console output
                logger.warning(
                    "\nCountdown started! Question (%s/%s): %s",
                    list(self.question_keys_answers.keys()).index(
                        current_question_key
                    )
                    + 1,
                    len(list(self.question_keys_answers.keys())),
                    list(
                        self.question_keys_answers[current_question_key].keys()
                    )[0],
                )

                # Update voting data
                self.voting_data[current_question_key]["clientTimestamps"][
                    "startAt"
                ] = start_time
                self.voting_data[current_question_key]["clientTimestamps"][
                    "endAt"
                ] = end_time

                # Set offset for open questions (otherwise answer will be
                # marked false) and random delay
                offset = (
                    1
                    if self.voting_data[current_question_key]["vote"]["type"]
                    == "quiz-open"
                    else 0
                )
                offset += randint(
                    self._minimum_delay_in_ms, self._maximum_delay_in_ms
                )

                # Check if offset too long
                # If offset greater than or equal to end time, it will be set
                # to end time - 1 (otherwise submission fails as too_late).
                if start_time + offset >= end_time:
                    offset = end_time - start_time - 1

                # Log offset
                if dev_logger:
                    dev_logger.debug(
                        "Configured offset for answer submission: %dms.",
                        offset,
                    )

                # Set voteTimestamp to start time + offset
                self.voting_data[current_question_key]["voteTimestamp"] = (
                    start_time + offset
                )

                # Set additional submission delay in ms (with 500ms buffer)
                # This is to make the voteTimestamp more realistic and prevent
                # a very late submission with a very low offset.
                #
                # Edge case: Lowest "Seconds to answer" by Menti is 5s.
                # If 5s to answer and offset is 4501ms --> submission after 4s.
                #
                # Configured offset is less than or equal to 500ms earlier
                # than end time:
                if (start_time + offset) >= end_time - 500:
                    submission_delay = offset - 500

                # Configured offset is at least 500ms earlier than end time:
                else:
                    submission_delay = offset

                # Log submission time
                if dev_logger:
                    dev_logger.debug(
                        "Calculated submission time: %dms.", submission_delay
                    )

                # Sleep until one second before start time
                sleep((start_time - round(time() * 1000) - 1000) / 1000)

                # Interesting findings (Aug. 30, 2025):
                # 1.: The voteTimestamp is used to determine the time
                #     of the answer submission.
                # 2.: You can submit an answer late, as long as it is still
                #     live. If the voteTimestamp is set accordingly you can
                #     still get a perfect score.
                # 3.: You can submit an answer while the countdown is running,
                #     if the voteTimestamp is set correctly.
                # 4.: Open questions need a voteTimestamp = startAt + 1ms.
                #     Otherwise a correct answer will be marked false.
                #
                # Wait until question starts
                while not round(time() * 1000) >= start_time:
                    pass
                else:
                    # Wait until submission time
                    sleep(submission_delay / 1000)

                    # Submit answer and callback function for error handling
                    # (e.g. resubmitting vote)
                    self.send_payload(
                        event="player_vote",
                        data=self.voting_data[current_question_key],
                        expect_ack=True,
                        ack_cb=self.send_payload,
                        cb_args={
                            "event": "player_vote",
                            "data": self.voting_data[current_question_key],
                            "expect_ack": True,
                        },
                    )
                    logger.warning(
                        "Submitting answer: %s.",
                        list(
                            self.question_keys_answers[
                                current_question_key
                            ].values()
                        )[0],
                    )

            # Question finished
            elif event == "quiz_ended":
                sleep(1)  # to prevent score not being loaded yet
                current_question_key = args[0]["gameStateData"][
                    "questionPublicKey"
                ]
                self.player_details["questionPublicKey"] = current_question_key
                self.player_details["latency"] = f"{randint(10, 30)}ms"
                self.send_payload(
                    event="player_get_result",
                    data=self.player_details,
                    expect_ack=True,
                )

        # ACK for Event (43/quiz2,<Ack-ID>...)
        elif sio_type == "3":
            # Remove namespace prefix
            payload = remainder[(len(NAMESPACE) + 1) :]

            # Fetch Ack-ID
            ack_id_str = ""
            i = 0
            while payload[i].isdigit():
                ack_id_str += payload[i]
                i += 1
            ack_id = int(ack_id_str)

            # Extract JSON part from payload
            json_part = payload[i:]
            args: list[MessageData] = json.loads(json_part)

            if args[0]["gameState"] == "lobby":
                pass

            elif args[0]["gameState"] == "question":
                time_elapsed = args[0]["gameStateData"].get("elapsedTime")
                if time_elapsed and isinstance(time_elapsed, int | float):
                    logger.info(
                        "Submitted answer after %s seconds.",
                        round(time_elapsed, 2),
                    )
                else:
                    logger.info("Submitted answer.")

            elif args[0]["gameState"] == "leaderboard":
                if (
                    args[0]["gameStateData"]["questionPublicKey"]
                    not in self._shown_slides["leaderboards"]
                ) and (score := args[0]["gameStateData"].get("score")):
                    # Only print leaderboard and add it to shown slide
                    # if score > 0
                    # This prevents unneccessary logging if presentator is
                    # skipping through the slides very fast
                    # (e.g. before the quiz starts)
                    if score.get("total", {}).get("totalScore", 0) > 0:
                        table = Table(
                            title="[u]Current Leaderboard[/]",
                            title_style="",
                            title_justify="center",
                            min_width=len("Current Leaderboard") + 4,
                        )
                        table.add_column(
                            "Position", justify="center", no_wrap=True
                        )
                        table.add_column(
                            "Score", justify="center", no_wrap=True
                        )
                        table.add_row(
                            str(score["total"]["position"]),
                            str(score["total"]["totalScore"]),
                        )
                        logger.debug("")
                        logger.debug(table)
                        self._shown_slides["leaderboards"].append(
                            args[0]["gameStateData"]["questionPublicKey"]
                        )
                    else:
                        pass

            elif args[0]["gameState"] == "final_leaderboard":
                # "Issue": The leaderboard slide can be shown at all times.
                # Even during a quiz. The score check cannot prevent the
                # console output from saying "You've won" if the presenter
                # decides to show the final leaderboard slide during the quiz
                # and after the player has already answered at least one
                # question correctly.
                # However, this should be a very rare edge case and even the
                # leaderboard slide shows "And the winner is..." by default.
                if score := args[0]["gameStateData"].get("score"):
                    table = Table(
                        title="[b u]Final Leaderboard[/]",
                        title_style="",
                        title_justify="center",
                        min_width=len("Final Leaderboard") + 4,
                    )
                    table.add_column(
                        "Position", justify="center", no_wrap=True
                    )
                    table.add_column("Score", justify="center", no_wrap=True)
                    table.add_row(
                        str(score["total"]["position"]),
                        str(score["total"]["totalScore"]),
                    )
                    logger.debug("")
                    logger.debug(table)
                    if (
                        args[0]["gameStateData"]["score"]["total"]["position"]
                        == 1
                    ):
                        logger.info("\nCongrats! You've won!")
                    logger.debug("")

            elif args[0]["gameState"] == "result":
                if (
                    args[0]["gameStateData"]["questionPublicKey"]
                    not in self._shown_slides["questions"]
                ):
                    self._shown_slides["questions"].append(
                        args[0]["gameStateData"]["questionPublicKey"]
                    )
                    if score := args[0]["gameStateData"].get("score"):
                        if score["question"].get(
                            "correctAnswer", False
                        ) or score["question"].get("markedCorrect", False):
                            logger.info(
                                "Correct Answer! Score: %s.",
                                score["question"]["score"],
                            )
                        else:
                            logger.error("Wrong answer.")

            elif args[0]["gameState"] == "error":
                error_code = args[0].get("errorCode")

                # Error codes to call callback function (resubmit vote)
                if error_code in (
                    "player_voted_too_fast",
                    "failed_to_post_vote",
                ):
                    callback: Waiter | None = self._ack_waiters.pop(
                        ack_id, None
                    )
                    if callback:
                        callback["function"](**callback["kwargs"])

                # Error codes to ignore
                elif error_code in (
                    "player_has_already_voted",
                    "no_available_quiz",
                ):
                    pass

                # Specific error codes to log
                elif error_code == "player_voted_too_slow":
                    logger.error("Vote was submitted too late.")

                # Unknown error codes
                else:
                    if error_code:
                        logger.error("Unknown error: %s", error_code)
                    else:
                        logger.error("Unknown error: %s", args[0])

        # Connection Error (44/quiz2)
        # Currently not used in recorded requests
        elif sio_type == "4":
            pass
