"""Labellerr SDK - Python client for Labellerr API."""

from .async_client import AsyncLabellerrClient
from .client import LabellerrClient
from .core.credentials import ApiKeyCredentials, BearerTokenCredentials, Credentials
from .core.exceptions import (
    AuthenticationError,
    JobFailedError,
    JobTimeoutError,
    LabellerrError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)

# Version from package metadata (computed once, in labellerr.core.settings, which
# also builds the User-Agent from it).
from .core.settings import DEFAULT_USER_AGENT, Settings, __version__

__all__ = [
    "__version__",
    "LabellerrClient",
    "AsyncLabellerrClient",
    "LabellerrError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "JobTimeoutError",
    "JobFailedError",
    "Credentials",
    "ApiKeyCredentials",
    "BearerTokenCredentials",
    "Settings",
    "DEFAULT_USER_AGENT",
]
