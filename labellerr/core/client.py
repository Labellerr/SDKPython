# labellerr/client.py

import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import client_utils, constants

# Initialize DataSets handler for dataset-related operations
from .exceptions import LabellerrError


class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """

    def __init__(
        self,
        api_key,
        api_secret,
        client_id,
        enable_connection_pooling=True,
        pool_connections=10,
        pool_maxsize=20,
    ):
        """
        Initializes the LabellerrClient with API credentials.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        :param client_id: The client ID for the Labellerr account.
        :param enable_connection_pooling: Whether to enable connection pooling
        :param pool_connections: Number of connection pools to cache
        :param pool_maxsize: Maximum number of connections to save in the pool
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.client_id = client_id
        self.base_url = constants.BASE_URL
        self._session = None
        self._enable_pooling = enable_connection_pooling
        self._pool_connections = pool_connections
        self._pool_maxsize = pool_maxsize

        if enable_connection_pooling:
            self._setup_session()

        # Import here to avoid circular imports
        from .users.base import LabellerrUsers

        # Initialize Users handler for user-related operations
        self.users = LabellerrUsers(self)

    def _setup_session(self):
        """
        Set up requests session with connection pooling for better performance.
        """
        self._session = requests.Session()

        if HTTPAdapter is not None and Retry is not None:
            # Configure retry strategy
            retry_kwargs = {
                "total": 3,
                "status_forcelist": [429, 500, 502, 503, 504],
                "backoff_factor": 1,
            }

            methods = [
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
            ]

            try:
                # Prefer modern param if available
                retry_strategy = Retry(allowed_methods=methods, **retry_kwargs)
            except TypeError:
                # Fallback for older urllib3
                retry_strategy = Retry(**retry_kwargs)

            # Configure connection pooling
            adapter = HTTPAdapter(
                pool_connections=self._pool_connections,
                pool_maxsize=self._pool_maxsize,
                max_retries=retry_strategy,
            )

            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

    def close(self):
        """
        Close the session and cleanup resources.
        """
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def handle_upload_response(self, response, request_id=None):
        """
        Specialized error handling for upload operations that may have different success patterns.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
        try:
            response_data = response.json()
        except ValueError:
            raise LabellerrError(f"Failed to parse response: {response.text}")

        if response.status_code not in [200, 201]:
            if 400 <= response.status_code < 500:
                raise LabellerrError(
                    {"error": response_data, "code": response.status_code}
                )
            elif response.status_code >= 500:
                raise LabellerrError(
                    {
                        "status": "internal server error",
                        "message": "Please contact support with the request tracking id",
                        "request_id": request_id or str(uuid.uuid4()),
                        "error": response_data,
                    }
                )
        return response_data

    def _handle_gcs_response(self, response, operation_name="GCS operation"):
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
                f"{operation_name} failed: {response.status_code} - {response.text}"
            )

    def make_request(
        self,
        method,
        url,
        extra_headers=None,
        request_id=None,
        handle_response=True,
        **kwargs,
    ):
        """
        Make an HTTP request using the configured session or requests library.
        Automatically builds headers and handles response parsing.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param extra_headers: Optional extra headers to include
        :param request_id: Optional request tracking ID
        :param handle_response: Whether to parse response (default True)
        :param kwargs: Additional arguments to pass to requests
        :return: Parsed response data if handle_response=True, otherwise Response object
        """
        # Build headers if client_id is provided
        if self.client_id is not None:
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=self.client_id,
                extra_headers=extra_headers,
            )
            # Merge with any existing headers in kwargs
            if "headers" in kwargs:
                headers.update(kwargs["headers"])
            kwargs["headers"] = headers

        # Make the request
        if self._session:
            response = self._session.request(method, url, **kwargs)
        else:
            response = requests.request(method, url, **kwargs)

        # Handle response if requested
        if handle_response:
            return client_utils.handle_response(response, request_id)
        else:
            return response
