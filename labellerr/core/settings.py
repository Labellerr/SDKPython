"""
Connection settings shared by the sync and async Labellerr clients.
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

from . import constants

try:
    import importlib.metadata as _importlib_metadata
except ImportError:  # Python < 3.8
    import importlib_metadata as _importlib_metadata  # type: ignore[no-redef]

try:
    __version__ = _importlib_metadata.version("labellerr-sdk")
except Exception:
    __version__ = "unknown"

# Sent by both clients: the gateway pins a session to its User-Agent.
DEFAULT_USER_AGENT = f"labellerr-sdk-python/{__version__}"
DEFAULT_SOURCE = "sdk"

ENV_BASE_URL = "LABELLERR_BASE_URL"
ENV_ORIGIN = "LABELLERR_ORIGIN"


@dataclass(frozen=True)
class Settings:
    """
    Where and how a client talks to the Labellerr API.

    A ``Settings`` you construct is used as given. ``Settings.from_env()`` (what a
    client uses when no settings are passed) also reads ``LABELLERR_BASE_URL`` and
    ``LABELLERR_ORIGIN``.

    :param base_url: API base URL (a trailing ``/`` is removed)
    :param origin: ``origin`` header; None picks the default for the credential kind
        (``https://pro.labellerr.com`` for an API key, ``https://sdk.labellerr.com``
        for an access token)
    :param source: ``source`` header
    :param user_agent: ``User-Agent`` header; None uses ``DEFAULT_USER_AGENT``
    """

    base_url: str = constants.DEFAULT_BASE_URL
    origin: Optional[str] = None
    source: str = DEFAULT_SOURCE
    user_agent: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ValueError("base_url must be a non-empty string")
        object.__setattr__(self, "base_url", self.base_url.strip().rstrip("/"))

    @classmethod
    def from_env(cls, **overrides: Any) -> "Settings":
        """
        Build settings from the environment, read now (not at import time).

        Precedence: an override passed here, then the environment, then the default.
        Overrides whose value is None are ignored.

        :param overrides: Any ``Settings`` field
        :return: Settings
        """
        values = {}
        base_url = os.environ.get(ENV_BASE_URL)
        if base_url and base_url.strip():
            values["base_url"] = base_url
        origin = os.environ.get(ENV_ORIGIN)
        if origin and origin.strip():
            values["origin"] = origin.strip()
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)

    def resolve_origin(self, credential_kind: str) -> str:
        """
        The origin to send for a credential kind.

        :param credential_kind: ``"api_key"`` or ``"bearer"``
        :return: ``self.origin`` when set, otherwise the kind's default
        """
        if self.origin:
            return self.origin
        if credential_kind == "bearer":
            return constants.TOKEN_DEFAULT_ORIGIN
        return constants.DEFAULT_ORIGIN

    def resolve_user_agent(self) -> str:
        """The User-Agent to send."""
        return self.user_agent or DEFAULT_USER_AGENT
