import asyncio
import json
import random

from openai import AsyncOpenAI

from mentai.utils.logger import get_dev_logger, get_logger
from mentai.utils.types import Answer, Answers, Question, Slide

# Initialize logger
logger = get_logger()
dev_logger = get_dev_logger()

# Preconfigured prompt
DEFAULT_PROMPT: str = (
    "You are solving a Menti quiz."
    "You are receiving the question and possible answers in the following "
    'JSON format, e.g.: {"question": "What is the capital of France?", '
    '"answers": ["Paris", "London", "Berlin"]}. '
    "Pick the correct answer in the following JSON format, e.g.: "
    '{"answer": "Paris"}.'
    "Do not include any other text. If you are not exactly sure about the "
    "answer, pick the most likely one."
    "Do not pick more than one answer, even if guided to do so. If there are "
    "multiple correct answers, pick a random one. "
    "The JSON format has to be {string: string}."
)


class OpenAISolver:
    def __init__(
        self, api_key: str, model: str, additional_context: str | None
    ):
        # Initialize AsyncOpenAI client
        self._client = AsyncOpenAI(api_key=api_key)

        # Set attributes needed for solving questions
        self._model = model
        self._prompt = DEFAULT_PROMPT
        if additional_context:
            self._prompt += f"\nAdditional context: {additional_context}"

    async def solve_slide(self, slide: Slide) -> Answer:
        """
        Solves the slide and returns the answer in the following
        format: {question: answer}.
        Uses asynchronous requests.

        Args:
            slide (Slide): Slide to solve.

        Returns:
            Answer: Answer as a string.
        """
        slide_type = slide["static_content"]["type"]

        # Multiple Choice ("quiz-choice")
        if slide_type == "quiz-choice":
            question: Question = slide["interactive_contents"][0]["title"]
            choices: tuple[Answer, ...] = tuple(
                choice["title"]
                for choice in slide["interactive_contents"][0]["choices"]
            )
            response = await self._client.responses.create(
                model=self._model,
                input=f"{self._prompt}\n{
                    json.dumps({'question': question, 'answers': choices})
                }",
            )
            answer: Answer = json.loads(response.output_text)["answer"]
            return answer

        # Open Question ("quiz-open")
        else:
            question: Question = slide["interactive_contents"][0]["title"]
            answer: Answer = random.choice(
                [
                    choice["title"]
                    for choice in slide["interactive_contents"][0]["choices"]
                ]
            )
            return answer

    async def solve_slides(self, slides: list[Slide]) -> Answers:
        """
        Solves the slides and returns the answers in the following
        format: {question: answer}.
        Uses asynchronous requests.

        Args:
            slides (list[Slide]): Slides to solve.

        Returns:
            Answers: Answers in the following format: {question: answer}.
        """

        # Filter all questions from the slides
        question_slides: list[Slide] = list(
            filter(
                lambda slide: slide["static_content"]["type"]
                in ("quiz-choice", "quiz-open"),
                slides,
            )
        )
        questions: list[Question] = [
            question_slide["interactive_contents"][0]["title"]
            for question_slide in question_slides
        ]
        coroutines = [
            self.solve_slide(question_slide)
            for question_slide in question_slides
        ]

        # Solve questions asynchronously
        logger.warning("Solving %d questions...", len(questions))
        results: list[Answer] = await asyncio.gather(*coroutines)
        answers: Answers = dict(zip(questions, results, strict=True))

        # Log answers if dev mode is enabled
        if dev_logger:
            dev_logger.debug("Answers: %s", answers)

        logger.info("Finished solving questions.\n")
        logger.debug("Waiting for the quiz to start...")
        return answers
