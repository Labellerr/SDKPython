# labellerr/client.py

import random
from itertools import takewhile
from typing import Any, Dict, Mapping, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import MaxRetryError, ResponseError
from urllib3.util.retry import Retry

from . import client_utils
from .credentials import (
    ApiKeyCredentials,
    BearerTokenCredentials,
    Credentials,
    TokenProvider,
    resolve_credentials,
)

# Initialize DataSets handler for dataset-related operations
from .exceptions import LabellerrError
from .settings import Settings

# Status codes retried (for idempotent methods only) before the response is returned.
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
# Methods retried on a retryable status or a read error. POST is not: the server may
# already have acted on it. Connection-establishment errors are retried for every
# method (urllib3 ``connect`` retries do not look at the method).
RETRY_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "OPTIONS"])
DEFAULT_TIMEOUT = 30  # seconds
# Longest server-supplied Retry-After the client sleeps for before retrying. A longer
# one is not retried: the response is returned and RateLimitError.retry_after (or the
# ServerError) carries it to the caller.
RETRY_AFTER_MAX = 10.0  # seconds
# Cap on one exponential-backoff sleep, before jitter.
BACKOFF_MAX = 10.0  # seconds
# Random extra sleep, as a fraction of the backoff, so clients that failed together
# do not retry together.
BACKOFF_JITTER = 0.5


class LabellerrRetry(Retry):
    """
    urllib3 ``Retry`` with the client's backoff rules (works with urllib3 1.26 and 2):

    - the first retry already backs off (``backoff_factor`` seconds; urllib3 retries
      the first time without sleeping), doubling up to ``BACKOFF_MAX``, plus jitter;
    - a ``Retry-After`` of at most ``RETRY_AFTER_MAX`` is slept for; a longer one
      stops the retries and the response is returned.

    Settings live in module constants, not constructor arguments, because
    ``Retry.new()`` rebuilds the object from the standard arguments only.
    """

    def get_backoff_time(self) -> float:
        consecutive_errors = len(
            list(
                takewhile(lambda x: x.redirect_location is None, reversed(self.history))
            )
        )
        if consecutive_errors < 1 or not self.backoff_factor:
            return 0.0
        backoff = min(BACKOFF_MAX, self.backoff_factor * 2 ** (consecutive_errors - 1))
        return backoff + random.uniform(0, backoff * BACKOFF_JITTER)

    def get_retry_after(self, response):
        # urllib3 raises InvalidHeader for a malformed value; treat it as absent so
        # the backoff applies instead.
        try:
            return super().get_retry_after(response)
        except Exception:
            return None

    def increment(self, method=None, url=None, response=None, *args, **kwargs):
        if response is not None and self.respect_retry_after_header:
            retry_after = self.get_retry_after(response)
            if retry_after is not None and retry_after > RETRY_AFTER_MAX:
                raise MaxRetryError(
                    kwargs.get("_pool"),
                    url or "",
                    ResponseError(
                        f"Retry-After {retry_after:g}s exceeds {RETRY_AFTER_MAX:g}s"
                    ),
                )
        return super().increment(method, url, response, *args, **kwargs)


def _require_client_id(client_id: Union[str, int, None]) -> str:
    """
    The client ID as a string; every request carries it (URL and header).

    :raises LabellerrError: If it is missing or blank
    """
    if client_id is None or isinstance(client_id, bool):
        raise LabellerrError(
            "client_id is required (the client ID of the Labellerr workspace)"
        )
    value = str(client_id).strip()
    if not value:
        raise LabellerrError("client_id must not be empty")
    return value


def build_retry(total: int = 3, backoff_factor: float = 1) -> Retry:
    """
    The retry policy mounted on the client's own session.

    ``raise_on_status=False``: when retries run out the last response is returned
    and mapped by ``client_utils.error_from_response`` (``ServerError`` /
    ``RateLimitError``) instead of surfacing as a ``requests`` ``RetryError``.
    """
    return LabellerrRetry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=RETRY_METHODS,
        raise_on_status=False,
        # A Retry-After up to RETRY_AFTER_MAX is honoured; LabellerrRetry returns the
        # response for a longer one.
        respect_retry_after_header=True,
    )


class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        client_id: Union[str, int, None] = None,
        enable_connection_pooling: bool = True,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
        access_token: Union[str, TokenProvider, None] = None,
        email_id: Optional[str] = None,
        *,
        credentials: Optional[Credentials] = None,
        settings: Optional[Settings] = None,
        session: Optional[requests.Session] = None,
    ):
        """
        Initializes the LabellerrClient with API credentials.

        Give exactly one of: ``api_key`` and ``api_secret``; ``access_token`` (see
        ``from_access_token``); or ``credentials``.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        :param client_id: The client ID (workspace) of the Labellerr account.
            Required: it is sent with every request. Pass it by keyword when
            credentials come from ``access_token=`` or ``credentials=``.
        :param enable_connection_pooling: Whether to enable connection pooling
        :param pool_connections: Number of connection pools to cache
        :param pool_maxsize: Maximum number of connections to save in the pool
        :param access_token: A user access token, or a zero-argument function
            returning one. Sent as ``Authorization: Bearer``.
        :param email_id: The signed-in user's email (used with ``access_token``).
        :param credentials: An ``ApiKeyCredentials`` or ``BearerTokenCredentials``.
        :param settings: Base URL, origin, source and User-Agent; defaults to
            ``Settings.from_env()``, read now.
        :param session: A ``requests.Session`` to use as-is (no retry adapters are
            mounted on it, and ``close()`` does not close it).
        :raises AuthenticationError: If no credentials, more than one kind, or an
            empty one is given.
        :raises LabellerrError: If ``client_id`` is missing or blank.
        """
        self.credentials = resolve_credentials(
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            credentials=credentials,
        )
        if settings is None:
            settings = Settings.from_env()
        elif not isinstance(settings, Settings):
            raise TypeError("settings must be a labellerr Settings instance")
        self.settings = settings

        self.client_id: str = _require_client_id(client_id)
        self.email_id = email_id
        # Plain attribute: callers may reassign it at runtime.
        self.base_url = settings.base_url
        self._session: Optional[requests.Session] = None
        self._owns_session = False
        self._enable_pooling = enable_connection_pooling
        self._pool_connections = pool_connections
        self._pool_maxsize = pool_maxsize

        if session is not None:
            self._session = session
        elif enable_connection_pooling:
            self._setup_session()

        # Import here to avoid circular imports
        from .users.base import LabellerrUsers

        # Initialize Users handler for user-related operations
        self.users = LabellerrUsers(self)

    @classmethod
    def from_access_token(
        cls,
        access_token: Union[str, TokenProvider],
        client_id: Union[str, int],
        email_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "LabellerrClient":
        """
        Create a client that authenticates as a signed-in user.

        :param access_token: The user's access token, or a zero-argument function
            returning one.
        :param client_id: The client ID (workspace) to act in. Required.
        :param email_id: The user's email.
        :param kwargs: Any other LabellerrClient keyword argument.
        :raises LabellerrError: If ``client_id`` is missing or blank.
        """
        return cls(
            client_id=client_id,
            access_token=access_token,
            email_id=email_id,
            **kwargs,
        )

    # Read-only views of ``self.credentials``, kept for backward compatibility.
    # Requests are authenticated from ``self.credentials`` only, so these cannot be
    # reassigned (that would silently not change the credentials).

    @property
    def api_key(self) -> Optional[str]:
        """The API key, for an API-key client; otherwise None."""
        if isinstance(self.credentials, ApiKeyCredentials):
            return self.credentials.api_key
        return None

    @property
    def api_secret(self) -> Optional[str]:
        """The API secret, for an API-key client; otherwise None."""
        if isinstance(self.credentials, ApiKeyCredentials):
            return self.credentials.api_secret
        return None

    @property
    def access_token(self) -> Union[str, TokenProvider, None]:
        """The token or token function, for a token client; otherwise None."""
        if isinstance(self.credentials, BearerTokenCredentials):
            return self.credentials.token_source
        return None

    @property
    def caller_identity(self) -> Optional[str]:
        """
        The identity some request bodies carry: the signed-in user's email for a
        token client, otherwise the API key.
        """
        if self.credentials.kind == "bearer":
            return self.email_id
        return self.api_key

    def _setup_session(self):
        """
        Set up requests session with connection pooling for better performance.
        """
        self._session = requests.Session()
        self._owns_session = True
        adapter = HTTPAdapter(
            pool_connections=self._pool_connections,
            pool_maxsize=self._pool_maxsize,
            max_retries=build_retry(),
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def close(self):
        """
        Close the session the client created. An injected session is left open.
        """
        if self._session is not None and self._owns_session:
            self._session.close()
            self._session = None
            self._owns_session = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _build_headers(
        self,
        extra_headers: Optional[Mapping[str, Any]] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        The headers of an API request: authentication, ``source``, ``origin``,
        ``User-Agent`` and ``client_id``.

        :param extra_headers: Optional extra headers to include
        :param client_id: Client ID to send; defaults to the client's own
        :return: Dictionary of headers
        """
        return client_utils.build_headers(
            self.credentials,
            self.settings,
            client_id=self.client_id if client_id is None else client_id,
            extra_headers=extra_headers,
        )

    def handle_upload_response(
        self, response: requests.Response, request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Specialized error handling for upload operations that may have different success patterns.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID; defaults to the
            ``x-correlation-id`` the request was sent with
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
        if request_id is None:
            request_id = client_utils.sent_request_id(response)
        if response.status_code < 400:
            try:
                return response.json()
            except ValueError:
                raise LabellerrError(
                    f"Failed to parse response: {response.text}",
                    status_code=response.status_code,
                    request_id=request_id,
                    response_body=response.text,
                )
        raise client_utils.error_from_response(
            response.status_code,
            client_utils.response_body(response),
            getattr(response, "headers", None),
            request_id,
        )

    def _handle_gcs_response(
        self, response: requests.Response, operation_name: str = "GCS operation"
    ) -> bool:
        """
        Specialized error handling for Google Cloud Storage operations.

        :param response: requests.Response object
        :param operation_name: Name of the operation for error messages
        :return: True for successful operations
        :raises LabellerrError: For non-successful responses
        """
        expected_codes = [200, 201] if operation_name == "upload" else [200]

        if response.status_code in expected_codes:
            return True
        else:
            raise LabellerrError(
                f"{operation_name} failed: {response.status_code} - {response.text}",
                status_code=response.status_code,
            )

    def make_request(
        self,
        method: str,
        url: str,
        extra_headers: Optional[Mapping[str, str]] = None,
        request_id: Optional[str] = None,
        handle_response: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Make an authenticated HTTP request using the configured session or the
        requests library, and parse the response.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param extra_headers: Optional extra headers to include
        :param request_id: Optional request tracking ID, sent as the
            ``x-correlation-id`` header (generated when not given) and reported in
            any error, so it matches the gateway's logs
        :param handle_response: Whether to parse response (default True)
        :param kwargs: Additional arguments to pass to requests (``params``,
            ``json``, ``data``, ``files``, ``timeout`` (default 30 s), ``headers``)
        :return: Parsed response data if handle_response=True, otherwise Response object
        :raises LabellerrError: For non-successful responses when handle_response=True
        """
        if request_id is None:
            request_id = client_utils.generate_request_id()
        headers = client_utils.merge_headers(
            {client_utils.CORRELATION_ID_HEADER: request_id},
            self._build_headers(extra_headers),
        )
        if kwargs.get("headers"):
            headers = client_utils.merge_headers(headers, kwargs["headers"])
        kwargs["headers"] = headers

        if "timeout" not in kwargs:
            kwargs["timeout"] = DEFAULT_TIMEOUT

        if self._session is not None:
            response = self._session.request(method, url, **kwargs)
        else:
            response = requests.request(method, url, **kwargs)

        if handle_response:
            return client_utils.handle_response(response, request_id)
        return response
