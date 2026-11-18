"""
This module will contain all utils which will be common across modules in the core module only.
"""

import logging
import math
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast

import requests

from ..exceptions import (
    APIConnectionError,
    JobTimeoutError,
    LabellerrError,
    RateLimitError,
    ServerError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default polling settings for the status() methods of datasets, projects and exports.
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_POLL_TIMEOUT = 3600.0
# Smallest polling interval accepted (interval=0 would flood the API).
MIN_POLL_INTERVAL = 0.5

# Errors that may go away on a later attempt. Polling retries these until its
# deadline; every other error is raised at once. The requests errors cover functions
# that call requests directly (make_request already wraps them in APIConnectionError).
TRANSIENT_ERRORS = (
    ServerError,
    RateLimitError,
    APIConnectionError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


def _validate_polling(timeout: Optional[float], interval: float) -> None:
    """
    Check polling arguments before any request is sent.

    :raises LabellerrError: If ``interval`` is not a number of at least
        ``MIN_POLL_INTERVAL`` seconds, or ``timeout`` is neither None nor a finite
        number >= 0
    """

    def is_number(value) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )

    if not is_number(interval) or interval < MIN_POLL_INTERVAL:
        raise LabellerrError(
            f"interval must be a number of at least "
            f"{MIN_POLL_INTERVAL} seconds, got {interval!r}"
        )
    if timeout is not None and (not is_number(timeout) or timeout < 0):
        raise LabellerrError(
            f"timeout must be None or a number >= 0 seconds, got {timeout!r}"
        )


def poll(
    function: Callable[..., T],
    condition: Callable[[T], bool],
    interval: float = DEFAULT_POLL_INTERVAL,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    on_success: Optional[Callable[[T], Any]] = None,
    on_timeout: Optional[Callable[[int, Optional[T]], Any]] = None,
    on_exception: Optional[Callable[[Exception], Any]] = None,
) -> T:
    """
    Poll a function at specified intervals until a condition is met.

    Transient errors raised by ``function`` (``TRANSIENT_ERRORS``: 5xx, 429 and
    connection problems) are retried until the timeout or ``max_retries``. Any other
    error (authentication, permission, not found, ...) is raised at once.

    Args:
        function: The function to call
        condition: Function that takes the return value of `function` and returns True when polling should stop
        interval: Time in seconds between calls
        timeout: Maximum time in seconds to poll before giving up (None: no limit)
        max_retries: Maximum number of attempts before giving up (None: no limit)
        args: Positional arguments to pass to `function`
        kwargs: Keyword arguments to pass to `function`
        on_success: Callback function to call with the successful result
        on_timeout: Callback function to call on timeout with the number of attempts and last result
        on_exception: Callback function to call when an exception occurs in `function`

    Returns:
        The return value that met ``condition``; on timeout or ``max_retries``, the
        last return value

    Raises:
        JobTimeoutError: If the timeout or ``max_retries`` is reached before
            ``function`` returned any value (every attempt failed with a transient
            error, which is chained as the cause)
        LabellerrError: Any non-transient error raised by ``function``

    Examples:
        ```python
        # Poll until a job is complete
        result = poll(
            function=check_job_status,
            condition=lambda status: status == "completed",
            interval=5.0,
            timeout=300,
            args=(job_id,)
        )

        # Poll with a custom breaking condition
        result = poll(
            function=get_task_result,
            condition=lambda r: r["status"] != "in_progress",
            interval=2.0,
            max_retries=10
        )
        ```
    """
    if kwargs is None:
        kwargs = {}

    start_time = time.time()
    attempts = 0
    has_result = False
    last_result: Optional[T] = None
    last_error: Optional[BaseException] = None

    while True:
        attempts += 1
        try:
            last_result = function(*args, **kwargs)
        except TRANSIENT_ERRORS as e:
            last_error = e
            if on_exception:
                on_exception(e)
            logger.warning("Transient error in poll function: %s", e)
        except Exception as e:
            if on_exception:
                on_exception(e)
            raise
        else:
            has_result = True
            last_error = None
            # Check if condition is satisfied
            if condition(last_result):
                if on_success:
                    on_success(last_result)
                return last_result

        if timeout is not None and time.time() - start_time > timeout:
            reason = f"Polling timed out after {timeout} seconds ({attempts} attempts)"
        elif max_retries is not None and attempts >= max_retries:
            reason = f"Polling reached max retries: {max_retries}"
        else:
            # Wait before next attempt
            time.sleep(interval)
            continue

        if on_timeout:
            on_timeout(attempts, last_result)
        logger.warning("%s", reason)
        if not has_result:
            raise JobTimeoutError(reason) from last_error
        return cast(T, last_result)


def validate_params(**validations):
    """
    Decorator to validate method parameters based on type specifications.

    Usage:
    @validate_params(project_id=str, file_id=str, keyFrames=list)
    def some_method(self, project_id, file_id, keyFrames):
        ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each parameter
            for param_name, expected_type in validations.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not isinstance(value, expected_type):
                        from ..exceptions import LabellerrError

                        type_name = (
                            " or ".join(t.__name__ for t in expected_type)
                            if isinstance(expected_type, tuple)
                            else expected_type.__name__
                        )
                        raise LabellerrError(f"{param_name} must be a {type_name}")

            return func(*args, **kwargs)

        return wrapper

    return decorator
