import sys
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from mentai.utils.logger import get_logger

# Types for exception decorator
P = ParamSpec("P")
R = TypeVar("R")


def catch_exceptions(func: Callable[P, R]) -> Callable[P, R]:  # noqa: UP047
    """
    Decorator to catch exceptions and handle them gracefully.

    Args:
        func (Callable): Function to decorate.

    Returns:
        Callable: Wrapper function that handles the exceptions.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            logger = get_logger()
            logger.debug("")
            sys.exit(0)

    return wrapper
