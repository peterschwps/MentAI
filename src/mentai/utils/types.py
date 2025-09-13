from collections.abc import Callable
from typing import Any, Literal, TypeAlias, TypedDict


# ----- Menti Types -----
class StaticContentQuestion(TypedDict):
    type: Literal["quiz-choice", "quiz-open"]
    image: Any
    label: Any
    layout: Any
    styledTitle: Any
    textSizeOffset: int


class StaticContentLeaderboard(TypedDict):
    type: Literal["leaderboard"]
    label: Any
    styledTitle: Any
    textSizeOffset: Any
    additionalDetails: Any


class Choice(TypedDict):
    interactive_content_choice_id: str
    title: str
    response_settings: Any
    image: Any
    legacy_choice_id: Any
    legacy_question_metadata_field_id: Any


class InteractiveContent(TypedDict):
    interactive_content_id: str
    response_mode: str
    title: str
    description: str | None
    max_entries: int | None
    countdown: int | None
    scoring: str | None
    choices: list[Choice]
    image: Any
    vote_settings: Any
    response_policy: Any
    response_range: Any
    response_point_quota: Any


class Slide(TypedDict):
    slide_public_key: str
    title: str
    static_content: StaticContentQuestion | StaticContentLeaderboard
    interactive_contents: list[InteractiveContent]  # is empty for leaderboards
    design: Any
    images: Any
    is_migrated: bool


class LegacyThemeSettings(TypedDict):
    bar_color: Any
    background_color: Any
    line_color: Any
    text_color: Any
    accessibility_mode: Any
    font: Any
    pace: Any
    backdrop_alpha: Any
    ui_color_positive: Any
    ui_color_neutral: Any
    ui_color_negative: Any
    config_id: Any
    logo: Any


class ParticipationSettings(TypedDict):
    participation_key: str
    participation_code: int
    participation_mode: str
    participation_policy: str
    participation_identity_mode: str
    participation_identity_visibility: str


class SlideDeck(TypedDict):
    slides: list[Slide]
    name: str
    theme_id: int
    legacy_theme_settings: LegacyThemeSettings
    qa_settings: Any
    live_chat_settings: Any
    reaction_settings: Any
    language_settings: Any
    participation_settings: ParticipationSettings
    ownership_settings: Any
    is_free_owner: Any


class Quiz(TypedDict):
    series: None
    slide_deck: SlideDeck


class Player(TypedDict):
    identifier: str
    name: str | None
    emojiShortname: str
    emojiName: str
    index: int


class PlayerDetails(TypedDict):
    voteKey: str
    questionPublicKey: str
    identifier: str
    player: Player
    latency: str
    ioLatency: str


class VoteChoice(TypedDict):
    interactiveContentChoiceId: str


class VoteOpen(TypedDict):
    interactiveContentChoiceId: str
    value: str


class Vote(TypedDict):
    isMigrated: bool
    interactiveContentId: str
    type: Literal["quiz-choice", "quiz-open"]
    choices: list[VoteChoice | VoteOpen]


class ClientTimestamps(TypedDict):
    startAt: int | None  # to be set when the question countdown starts
    endAt: int | None  # to be set when the question countdown starts


class VotingDataSlide(TypedDict):
    voteKey: str
    questionPublicKey: str
    identifier: str
    player: Player
    voteTimestamp: int | None  # to be set when the question goes live
    vote: Vote
    clientTimestamps: ClientTimestamps
    latency: str
    ioLatency: str


QuestionPublicKey: TypeAlias = str  # noqa: UP040
VotingData: TypeAlias = dict[QuestionPublicKey, VotingDataSlide]  # noqa: UP040

# ----- WebSocket Types -----
# see https://socket.io/docs/v4/engine-io-protocol/
# and https://socket.io/docs/v4/socket-io-protocol/
# Message Components
MessageType: TypeAlias = str  # noqa: UP040
MessageNamespace: TypeAlias = str  # noqa: UP040
MessageAckID: TypeAlias = int  # noqa: UP040
MessageEvent: TypeAlias = str  # noqa: UP040
MessageData: TypeAlias = dict[Any, Any]  # noqa: UP040

# Message Formats
# format: "type/namespace,ack_id[event,data]"
MessageWithAck: TypeAlias = str  # noqa: UP040
# format: "type/namespace[event,data]"
MessageWithoutAck: TypeAlias = str  # noqa: UP040
Message: TypeAlias = MessageWithAck | MessageWithoutAck  # noqa: UP040

# ----- Self-constructed Types -----
# --- src.solver.py ---
Question: TypeAlias = str  # noqa: UP040
Answer: TypeAlias = str  # noqa: UP040
Answers: TypeAlias = dict[Question, Answer]  # noqa: UP040


# --- src.utils.websocket.py ---
QuestionKeyAnswersMapping: TypeAlias = dict[  # noqa: UP040
    QuestionPublicKey, Answers
]


class ShownSlides(TypedDict):
    questions: list[str]
    leaderboards: list[str]


CallbackFunction: TypeAlias = Callable  # noqa: UP040
CallbackArguments: TypeAlias = dict[str, Any]  # noqa: UP040


class Waiter(TypedDict):
    function: CallbackFunction  # callback function
    kwargs: CallbackArguments  # keyword arguments to be passed
    # to the callback function


AckWaiters: TypeAlias = dict[int, Waiter]  # noqa: UP040


# --- src.utils.settings.py ---
class SolverSettings(TypedDict):
    OPEN_AI_API_KEY: str
    OPEN_AI_MODEL: str


class QuizSettings(TypedDict):
    PLAYER_NAME: str
    MINIMUM_DELAY_IN_MS: int
    MAXIMUM_DELAY_IN_MS: int
    CONTEXT: str


class Settings(TypedDict):
    SOLVER: SolverSettings
    QUIZ: QuizSettings
