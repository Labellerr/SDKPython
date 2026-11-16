# labellerr/client.py

from typing import Any, Dict, Mapping, Optional, Union

import requests
from requests.adapters import HTTPAdapter
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


def build_retry(total: int = 3, backoff_factor: float = 1) -> Retry:
    """
    The retry policy mounted on the client's own session.

    ``raise_on_status=False``: when retries run out the last response is returned
    and mapped by ``client_utils.error_from_response`` (``ServerError`` /
    ``RateLimitError``) instead of surfacing as a ``requests`` ``RetryError``.
    """
    return Retry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=RETRY_METHODS,
        raise_on_status=False,
        # Never sleep for a server-supplied Retry-After (it can be hours); the backoff
        # applies, and RateLimitError.retry_after carries the value to the caller.
        respect_retry_after_header=False,
    )


class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        client_id: Optional[str] = None,
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
        :param client_id: The client ID for the Labellerr account.
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

        # Read-only conveniences kept for backward compatibility; requests are
        # authenticated from ``self.credentials`` only.
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self.access_token: Union[str, TokenProvider, None] = None
        if isinstance(self.credentials, ApiKeyCredentials):
            self.api_key = self.credentials.api_key
            self.api_secret = self.credentials.api_secret
        elif isinstance(self.credentials, BearerTokenCredentials):
            self.access_token = self.credentials.token_source

        self.client_id = client_id
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
        client_id: Optional[str],
        email_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "LabellerrClient":
        """
        Create a client that authenticates as a signed-in user.

        :param access_token: The user's access token, or a zero-argument function
            returning one.
        :param client_id: The client ID (workspace) to act in.
        :param email_id: The user's email.
        :param kwargs: Any other LabellerrClient keyword argument.
        """
        return cls(
            client_id=client_id,
            access_token=access_token,
            email_id=email_id,
            **kwargs,
        )

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
        :param request_id: Optional request tracking ID
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
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
        :param request_id: Optional request tracking ID
        :param handle_response: Whether to parse response (default True)
        :param kwargs: Additional arguments to pass to requests (``params``,
            ``json``, ``data``, ``files``, ``timeout`` (default 30 s), ``headers``)
        :return: Parsed response data if handle_response=True, otherwise Response object
        :raises LabellerrError: For non-successful responses when handle_response=True
        """
        headers = self._build_headers(extra_headers)
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
