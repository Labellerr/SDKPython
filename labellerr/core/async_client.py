# labellerr/async_client.py

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import aiofiles
import aiohttp

from labellerr.core import client_utils
from labellerr.core.credentials import (
    ApiKeyCredentials,
    BearerTokenCredentials,
    Credentials,
    TokenProvider,
    resolve_credentials,
)
from labellerr.core.exceptions import (
    APIConnectionError,
    APITimeoutError,
    LabellerrError,
)
from labellerr.core.schemas.base import DatasetDataType
from labellerr.core.settings import DEFAULT_SOURCE, Settings
from labellerr.validators import auto_log_and_handle_errors_async

logger = logging.getLogger(__name__)

ASYNC_SOURCE = "sdk-async"
DATA_TYPES = [data_type.value for data_type in DatasetDataType]


async def _read_body(response: aiohttp.ClientResponse) -> Tuple[Any, bool]:
    """
    Read an aiohttp response body once.

    :return: (parsed JSON, True) when the body is JSON, otherwise (text, False)
    """
    text = await response.text()
    try:
        return json.loads(text), True
    except ValueError:
        return text, False


@auto_log_and_handle_errors_async(
    include_params=False,
    exclude_methods=["close", "_ensure_session", "_build_headers"],
)
class AsyncLabellerrClient:
    """
    Async client for interacting with the Labellerr API using aiohttp for better performance.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        connector_limit: int = 100,
        access_token: Union[str, TokenProvider, None] = None,
        *,
        credentials: Optional[Credentials] = None,
        settings: Optional[Settings] = None,
    ):
        """
        Initializes the AsyncLabellerrClient with API credentials.

        Give exactly one of: ``api_key`` and ``api_secret``; ``access_token`` (see
        ``from_access_token``); or ``credentials``.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        :param connector_limit: Maximum number of connections in the pool
        :param access_token: A user access token, or a zero-argument (synchronous)
            function returning one. Sent as ``Authorization: Bearer``.
        :param credentials: An ``ApiKeyCredentials`` or ``BearerTokenCredentials``.
        :param settings: Base URL, origin, source and User-Agent; defaults to
            ``Settings.from_env()``, read now.
        :raises AuthenticationError: If no credentials, more than one kind, or an
            invalid one (e.g. an ``async def`` token provider) is given.
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

        # Plain attribute: callers may reassign it at runtime.
        self.base_url = settings.base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector_limit = connector_limit

    @classmethod
    def from_access_token(
        cls, access_token: Union[str, TokenProvider], **kwargs: Any
    ) -> "AsyncLabellerrClient":
        """
        Create a client that authenticates as a signed-in user.

        :param access_token: The user's access token, or a zero-argument
            (synchronous) function returning one.
        :param kwargs: Any other AsyncLabellerrClient keyword argument.
        """
        return cls(access_token=access_token, **kwargs)

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
    def _source(self) -> str:
        """``sdk-async``, unless the settings chose a different source."""
        if self.settings.source == DEFAULT_SOURCE:
            return ASYNC_SOURCE
        return self.settings.source

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session is created with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self._connector_limit,
                limit_per_host=20,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": self.settings.resolve_user_agent()},
            )

    async def close(self):
        """Close the aiohttp session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_headers(
        self,
        client_id: Optional[str] = None,
        extra_headers: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Builds standard headers for API requests.

        :param client_id: Optional client ID to include in headers
        :param extra_headers: Optional dictionary of additional headers
        :return: Dictionary of headers
        """
        return client_utils.build_headers(
            self.credentials,
            self.settings,
            client_id=client_id,
            extra_headers=extra_headers,
            source=self._source,
        )

    async def _request(
        self,
        method: str,
        url: str,
        request_id: Optional[str] = None,
        success_codes: Optional[list] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make HTTP request and handle response in a single async method.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param request_id: Optional request tracking ID (auto-generated if not
            provided), sent as the ``x-correlation-id`` header and reported in any
            error, so it matches the gateway's logs
        :param success_codes: Optional list of success status codes (default: [200, 201])
        :param kwargs: Additional arguments to pass to aiohttp
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        :raises APITimeoutError: If the request times out
        :raises APIConnectionError: If the connection fails or drops
        """
        # Generate request_id if not provided
        if request_id is None:
            request_id = client_utils.generate_request_id()
        kwargs["headers"] = client_utils.merge_headers(
            {client_utils.CORRELATION_ID_HEADER: request_id},
            kwargs.get("headers"),
        )

        await self._ensure_session()

        assert (
            self._session is not None
        ), "Session must be initialized before making requests"
        try:
            async with self._session.request(method, url, **kwargs) as response:
                return await self._handle_response(
                    response, request_id, success_codes=success_codes
                )
        # Timeout first: aiohttp's ServerTimeoutError is also a ClientConnectionError.
        except asyncio.TimeoutError as e:
            raise APITimeoutError(
                f"Request timed out: {method} {client_utils.url_without_query(url)}",
                request_id=request_id,
            ) from e
        except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError) as e:
            raise APIConnectionError(
                f"Connection error: {method} {client_utils.url_without_query(url)}",
                request_id=request_id,
            ) from e

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        request_id: Optional[str] = None,
        success_codes: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Return the JSON body of a successful response, or raise the error
        ``client_utils.error_from_response`` maps it to.

        :param response: aiohttp ClientResponse object
        :param request_id: Optional request tracking ID
        :param success_codes: Optional list of success status codes (default: [200, 201])
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
        if success_codes is None:
            success_codes = [200, 201]

        # Read and parse first; raise afterwards, outside any try block, so the
        # parsed JSON body of an error is kept.
        body, is_json = await _read_body(response)
        if response.status in success_codes:
            if not is_json:
                raise LabellerrError(
                    f"Expected JSON response but got: {body}",
                    status_code=response.status,
                    request_id=request_id,
                    response_body=body,
                )
            return body
        raise client_utils.error_from_response(
            response.status,
            body,
            getattr(response, "headers", None),
            request_id,
        )

    async def get_direct_upload_url(
        self, file_name: str, client_id: str, purpose: str = "pre-annotations"
    ) -> str:
        """
        Async version of get_direct_upload_url.
        """
        url = f"{self.base_url}/connectors/direct-upload-url"
        params = {"client_id": client_id, "purpose": purpose, "file_name": file_name}
        headers = self._build_headers(client_id=client_id)

        try:
            response_data = await self._request(
                "GET", url, params=params, headers=headers
            )
            return response_data["response"]
        except Exception as e:
            logger.exception("Error getting direct upload url: %s", e)
            raise

    async def connect_local_files(
        self, client_id: str, file_names: List[str], connection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Async version of connect_local_files.
        """
        url = f"{self.base_url}/connectors/connect/local"
        params = {"client_id": client_id}
        headers = self._build_headers(client_id=client_id)

        body: Dict[str, Any] = {"file_names": file_names}
        if connection_id is not None:
            body["temporary_connection_id"] = connection_id

        return await self._request(
            "POST", url, params=params, headers=headers, json=body
        )

    async def upload_file_stream(
        self, signed_url: str, file_path: str, chunk_size: int = 8192
    ) -> bool:
        """
        Async streaming file upload to minimize memory usage.

        :param signed_url: GCS signed URL for upload
        :param file_path: Local file path to upload
        :param chunk_size: Size of chunks to read
        :return: True on success
        """
        await self._ensure_session()

        file_size = os.path.getsize(file_path)
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(file_size),
        }

        async with aiofiles.open(file_path, "rb") as f:
            assert (
                self._session is not None
            ), "Session must be initialized before uploading files"
            async with self._session.put(
                signed_url, headers=headers, data=f
            ) as response:
                if response.status not in [200, 201]:
                    text = await response.text()
                    raise LabellerrError(f"Upload failed: {response.status} - {text}")
                return True

    async def upload_files_batch(
        self, client_id: str, files_list: Union[List[str], str], batch_size: int = 5
    ) -> str:
        """
        Async batch file upload with concurrency control.

        :param client_id: The ID of the client
        :param files_list: List of file paths to upload
        :param batch_size: Number of concurrent uploads
        :return: Connection ID
        """
        normalized_files_list: List[str]
        if isinstance(files_list, str):
            normalized_files_list = files_list.split(",")
        elif isinstance(files_list, list):
            normalized_files_list = files_list
        else:
            raise LabellerrError(
                "files_list must be either a list or a comma-separated string"
            )

        if len(normalized_files_list) == 0:
            raise LabellerrError("No files to upload")

        # Validate files exist
        for file_path in normalized_files_list:
            if not os.path.exists(file_path):
                raise LabellerrError(f"File does not exist: {file_path}")
            if not os.path.isfile(file_path):
                raise LabellerrError(f"Path is not a file: {file_path}")

        # Get upload URLs and connection ID
        file_names = [os.path.basename(f) for f in normalized_files_list]
        response = await self.connect_local_files(client_id, file_names)

        connection_id = response["response"]["temporary_connection_id"]
        resumable_upload_links = response["response"]["resumable_upload_links"]

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(batch_size)

        async def upload_single_file(file_path: str):
            async with semaphore:
                file_name = os.path.basename(file_path)
                signed_url = resumable_upload_links[file_name]
                return await self.upload_file_stream(signed_url, file_path)

        # Upload files concurrently
        tasks = [upload_single_file(file_path) for file_path in normalized_files_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for errors
        failed_files = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_files.append((normalized_files_list[i], str(result)))

        if failed_files:
            error_msg = (
                f"Failed to upload {len(failed_files)} files: {failed_files[:3]}"
            )
            if len(failed_files) > 3:
                error_msg += f"... and {len(failed_files) - 3} more"
            raise LabellerrError(error_msg)

        return connection_id

    async def get_dataset(self, workspace_id: str, dataset_id: str) -> Dict[str, Any]:
        """
        Async version of get_dataset.
        """
        url = f"{self.base_url}/datasets/{dataset_id}"
        unique_id = str(uuid.uuid4())
        params = {"client_id": workspace_id, "uuid": unique_id}
        headers = self._build_headers(client_id=workspace_id)

        return await self._request(
            "GET", url, params=params, headers=headers, request_id=unique_id
        )

    async def create_dataset(
        self,
        dataset_config: Dict[str, Any],
        files_to_upload: Optional[List[str]] = None,
        path: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Async version of create_dataset.

        :param dataset_config: Configuration for the dataset
        :param files_to_upload: Optional list of files to upload
        :param path: Path to the data source (required for GCS and AWS connectors)
        :param connection_id: Pre-existing connection ID to use for the dataset.
                             If both connection_id and files_to_upload are provided, connection_id takes precedence.
        """
        try:
            # Validate data_type
            if dataset_config.get("data_type") not in DATA_TYPES:
                raise LabellerrError(f"Invalid data_type. Must be one of {DATA_TYPES}")

            # Get connector_type from dataset_config, default to "local"
            connector_type = dataset_config.get("connector_type", "local")

            # Validate path for GCS/AWS connectors
            if connector_type in ["gcp", "aws"] and path is None:
                raise LabellerrError(f"path is required for {connector_type} connector")

            # Use provided connection_id or create one from files_to_upload
            final_connection_id = connection_id
            if final_connection_id is None and files_to_upload is not None:
                final_connection_id = await self.upload_files_batch(
                    client_id=dataset_config["client_id"], files_list=files_to_upload
                )

            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/datasets/create"
            params = {"client_id": dataset_config["client_id"], "uuid": unique_id}
            headers = self._build_headers(
                client_id=dataset_config["client_id"],
                extra_headers={"content-type": "application/json"},
            )

            payload: Dict[str, Any] = {
                "dataset_name": dataset_config["dataset_name"],
                "dataset_description": dataset_config.get("dataset_description", ""),
                "data_type": dataset_config["data_type"],
                "connection_id": final_connection_id,
                "path": path,
                "client_id": dataset_config["client_id"],
                "connector_type": connector_type,
            }

            response_data = await self._request(
                "POST",
                url,
                params=params,
                headers=headers,
                json=payload,
                request_id=unique_id,
            )
            dataset_id = response_data["response"]["dataset_id"]
            return {"response": "success", "dataset_id": dataset_id}

        except LabellerrError as e:
            logger.error("Failed to create dataset: %s", e)
            raise

    # Add more async methods as needed...
