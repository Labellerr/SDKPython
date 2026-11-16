"""
Credentials for the Labellerr API: an API key and secret, or a user access token.

Error messages and reprs never contain the key, secret or token.
"""

import inspect
from typing import Any, Callable, Dict, Optional, Union

from .exceptions import AuthenticationError

TokenProvider = Callable[[], str]


def _is_non_blank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_async_callable(value: Any) -> bool:
    return inspect.iscoroutinefunction(value) or inspect.iscoroutinefunction(
        getattr(value, "__call__", None)
    )


def _clean(value: str, label: str) -> str:
    """
    Strip surrounding whitespace, then reject control characters.

    The message never contains the value (``requests`` would echo a bad header value
    into its error, which then gets logged).
    """
    value = value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise AuthenticationError(f"{label} contains a control character")
    return value


class Credentials:
    """
    Base class: something that produces the authentication headers of a request.

    :ivar kind: ``"api_key"`` or ``"bearer"``
    """

    kind: str = ""

    def auth_headers(self) -> Dict[str, str]:
        """
        The authentication headers to send with a request.

        :return: Dictionary of headers
        :raises AuthenticationError: If no valid credential can be produced
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(kind={self.kind!r})"

    __str__ = __repr__


class ApiKeyCredentials(Credentials):
    """
    An API key and secret, sent as the ``api_key`` and ``api_secret`` headers.

    :param api_key: The API key
    :param api_secret: The API secret
    :raises AuthenticationError: If either value is missing or blank
    """

    kind = "api_key"

    def __init__(self, api_key: str, api_secret: str) -> None:
        if not _is_non_blank_string(api_key) or not _is_non_blank_string(api_secret):
            raise AuthenticationError(
                "api_key and api_secret must both be non-empty strings"
            )
        self._api_key = _clean(api_key, "api_key")
        self._api_secret = _clean(api_secret, "api_secret")

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_secret(self) -> str:
        return self._api_secret

    def auth_headers(self) -> Dict[str, str]:
        return {"api_key": self._api_key, "api_secret": self._api_secret}


class BearerTokenCredentials(Credentials):
    """
    A user access token, sent as ``Authorization: Bearer <token>``.

    :param token: The token, or a zero-argument (synchronous) function returning the
        current token. A function is called for every request, so it can refresh.
    :raises AuthenticationError: If the token is empty, or the function is ``async``
    """

    kind = "bearer"

    def __init__(self, token: Union[str, TokenProvider]) -> None:
        self._token: Optional[str] = None
        self._provider: Optional[TokenProvider] = None
        if isinstance(token, str):
            if not token.strip():
                raise AuthenticationError("access_token must be a non-empty string")
            self._token = _clean(token, "access_token")
        elif callable(token):
            if _is_async_callable(token):
                raise AuthenticationError(
                    "access_token provider must be a regular function returning a "
                    "string; async functions are not supported"
                )
            self._provider = token
        else:
            raise AuthenticationError(
                "access_token must be a non-empty string or a zero-argument "
                "function returning one"
            )

    @property
    def token_source(self) -> Union[str, TokenProvider]:
        """The token or provider this was built from."""
        return self._token if self._provider is None else self._provider

    def token(self) -> str:
        """
        The current token (calls the provider when there is one).

        :return: The token
        :raises AuthenticationError: If the provider does not return a non-empty string
        """
        if self._provider is None:
            return self._token  # type: ignore[return-value]
        try:
            value = self._provider()
        except Exception as exc:
            raise AuthenticationError(
                "The access token provider raised an error"
            ) from exc
        if inspect.isawaitable(value):
            close = getattr(value, "close", None)
            if callable(close):
                close()  # avoid a "coroutine was never awaited" warning
            raise AuthenticationError(
                "access_token provider returned an awaitable; it must return a string"
            )
        if not _is_non_blank_string(value):
            raise AuthenticationError(
                "access_token provider returned no token "
                f"(got {type(value).__name__}, expected a non-empty string)"
            )
        return _clean(value, "access_token")

    def auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}


def resolve_credentials(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Union[str, TokenProvider, None] = None,
    credentials: Optional[Credentials] = None,
) -> Credentials:
    """
    Turn a client's constructor arguments into one ``Credentials`` object.

    Exactly one of ``credentials``, ``access_token``, or ``api_key`` + ``api_secret``
    must be given.

    :param api_key: API key
    :param api_secret: API secret
    :param access_token: User access token, or a function returning one
    :param credentials: A ready-made ``Credentials`` object
    :return: Credentials
    :raises AuthenticationError: If none, or more than one, is given, or one is invalid
    """
    given = [
        credentials is not None,
        access_token is not None,
        api_key is not None or api_secret is not None,
    ]
    if sum(given) > 1:
        raise AuthenticationError(
            "Pass one of credentials=, access_token=, or api_key and api_secret, "
            "not more than one"
        )
    if credentials is not None:
        if not isinstance(credentials, Credentials):
            raise AuthenticationError(
                "credentials must be an ApiKeyCredentials or BearerTokenCredentials"
            )
        return credentials
    if access_token is not None:
        return BearerTokenCredentials(access_token)
    if api_key is not None or api_secret is not None:
        return ApiKeyCredentials(api_key, api_secret)  # type: ignore[arg-type]
    raise AuthenticationError(
        "No credentials: pass api_key and api_secret, access_token, or credentials="
    )


__all__ = [
    "Credentials",
    "ApiKeyCredentials",
    "BearerTokenCredentials",
    "resolve_credentials",
]
