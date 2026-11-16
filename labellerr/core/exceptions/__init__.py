# labellerr/exceptions.py

from typing import Any, Optional


class LabellerrError(Exception):
    """
    Base exception for Labellerr SDK errors.

    Constructed exactly like a plain ``Exception`` (``LabellerrError("text")``,
    ``LabellerrError({...})``). Errors built from an API response also carry the
    details below; they are ``None`` for errors raised client-side.

    :ivar status_code: HTTP status of the response
    :ivar error_code: The gateway's machine-readable code, e.g. ``"TOKEN_INVALID"``
    :ivar request_id: Request tracking ID
    :ivar response_body: Parsed JSON body, or the text when the body is not JSON
    """

    def __init__(
        self,
        *args: Any,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(*args)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        self.response_body = response_body


class AuthenticationError(LabellerrError):
    """Credentials are missing or invalid (HTTP 401, or rejected client-side)."""


class PermissionDeniedError(LabellerrError):
    """The caller may not perform this action (HTTP 403)."""


class NotFoundError(LabellerrError):
    """The requested resource does not exist (HTTP 404)."""


class RateLimitError(LabellerrError):
    """
    Too many requests (HTTP 429).

    :ivar retry_after: Seconds to wait before retrying, from ``Retry-After``; or None
    """

    def __init__(self, *args: Any, retry_after: Optional[float] = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class ServerError(LabellerrError):
    """The API failed to handle the request (HTTP 5xx)."""


class JobTimeoutError(LabellerrError):
    """A background job did not finish before the polling deadline passed."""


class InvalidDatasetError(LabellerrError):
    """Custom exception for invalid dataset errors."""

    pass


class InvalidProjectError(LabellerrError):
    """Custom exception for invalid project errors."""

    pass


class InvalidDatasetIDError(LabellerrError):
    pass


class InvalidConnectionError(LabellerrError):
    pass


class InvalidAnnotationTemplateError(LabellerrError):
    """Custom exception for invalid annotation template errors."""

    pass


__all__ = [
    "LabellerrError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "JobTimeoutError",
    "InvalidDatasetError",
    "InvalidProjectError",
    "InvalidDatasetIDError",
    "InvalidConnectionError",
    "InvalidAnnotationTemplateError",
]
