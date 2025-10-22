# labellerr/client.py

import concurrent.futures
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import client_utils, constants, gcs, schemas
from .core.datasets.datasets import DataSets
from .exceptions import LabellerrError
from .utils import validate_params, poll
from .validators import auto_log_and_handle_errors

create_dataset_parameters: Dict[str, Any] = {}


@auto_log_and_handle_errors(
    include_params=False,
    exclude_methods=[
        "close",
        "validate_rotation_config",
        "get_total_folder_file_count_and_total_size",
        "get_total_file_count_and_total_size",
    ],
)
@dataclass
class KeyFrame:
    """
    Represents a key frame with validation.
    """

    frame_number: int
    is_manual: bool = True
    method: str = "manual"
    source: str = "manual"

    def __post_init__(self):
        # Validate frame_number
        if not isinstance(self.frame_number, int):
            raise ValueError("frame_number must be an integer")
        if self.frame_number < 0:
            raise ValueError("frame_number must be non-negative")

        # Validate is_manual
        if not isinstance(self.is_manual, bool):
            raise ValueError("is_manual must be a boolean")

        # Validate method
        if not isinstance(self.method, str):
            raise ValueError("method must be a string")

        # Validate source
        if not isinstance(self.source, str):
            raise ValueError("source must be a string")


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

        # Initialize DataSets handler for dataset-related operations
        self.datasets = DataSets(api_key, api_secret, self)

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

    def _handle_upload_response(self, response, request_id=None):
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

    def _request(self, method, url, **kwargs):
        """
        Wrapper around client_utils.request for backward compatibility.

        :param method: HTTP method
        :param url: Request URL
        :param kwargs: Additional arguments
        :return: Response data
        """
        return client_utils.request(method, url, **kwargs)

    def _make_request(self, method, url, **kwargs):
        """
        Make an HTTP request using the configured session or requests library.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param kwargs: Additional arguments to pass to requests
        :return: Response object
        """
        if self._session:
            return self._session.request(method, url, **kwargs)
        else:
            return requests.request(method, url, **kwargs)

    def _handle_response(self, response, request_id=None):
        """
        Handle API response and extract data or raise errors.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID
        :return: Response data
        """
        return client_utils.handle_response(response, request_id)

    def get_direct_upload_url(self, file_name, client_id, purpose="pre-annotations"):
        """
        Get the direct upload URL for the given file names.

        :param file_name: The list of file names.
        :param client_id: The ID of the client.
        :param purpose: The purpose of the URL.
        :return: The response from the API.
        """
        url = f"{constants.BASE_URL}/connectors/direct-upload-url?client_id={client_id}&purpose={purpose}&file_name={file_name}"
        headers = client_utils.build_headers(
            client_id=client_id, api_key=self.api_key, api_secret=self.api_secret
        )

        try:
            response_data = client_utils.request(
                "GET", url, headers=headers, success_codes=[200]
            )
            return response_data["response"]
        except Exception as e:
            logging.exception(f"Error getting direct upload url: {e}")
            raise

    def create_aws_connection(
        self,
        client_id: str,
        aws_access_key: str,
        aws_secrets_key: str,
        s3_path: str,
        data_type: str,
        name: str,
        description: str,
        connection_type: str = "import",
    ):
        """
        AWS S3 connector and, if valid, save the connection.
        :param client_id: The ID of the client.
        :param aws_access_key: The AWS access key.
        :param aws_secrets_key: The AWS secrets key.
        :param s3_path: The S3 path.
        :param data_type: The data type.
        :param name: The name of the connection.
        :param description: The description.
        :param connection_type: The connection type.

        """
        # Validate parameters using Pydantic
        params = schemas.AWSConnectionParams(
            client_id=client_id,
            aws_access_key=aws_access_key,
            aws_secrets_key=aws_secrets_key,
            s3_path=s3_path,
            data_type=data_type,
            name=name,
            description=description,
            connection_type=connection_type,
        )

        request_uuid = str(uuid.uuid4())
        test_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"email_id": self.api_key},
        )

        aws_credentials_json = json.dumps(
            {
                "access_key_id": params.aws_access_key,
                "secret_access_key": params.aws_secrets_key,
            }
        )

        test_request = {
            "credentials": aws_credentials_json,
            "connector": "s3",
            "path": params.s3_path,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
        }

        client_utils.request(
            "POST",
            test_connection_url,
            headers=headers,
            data=test_request,
            request_id=request_uuid,
        )

        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={params.client_id}"
        )

        create_request = {
            "client_id": params.client_id,
            "connector": "s3",
            "name": params.name,
            "description": params.description,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
            "credentials": aws_credentials_json,
        }

        return client_utils.request(
            "POST",
            create_url,
            headers=headers,
            data=create_request,
            request_id=request_uuid,
        )

    def create_gcs_connection(
        self,
        client_id: str,
        gcs_cred_file: str,
        gcs_path: str,
        data_type: str,
        name: str,
        description: str,
        connection_type: str = "import",
        credentials: str = "svc_account_json",
    ):
        """
        Create/test a GCS connector connection (multipart/form-data)
        :param client_id: The ID of the client.
        :param gcs_cred_file: Path to the GCS service account JSON file.
        :param gcs_path: GCS path like gs://bucket/path
        :param data_type: Data type, e.g. "image", "video".
        :param name: Name of the connection
        :param description: Description of the connection
        :param connection_type: "import" or "export" (default: import)
        :param credentials: Credential type (default: svc_account_json)
        :return: Parsed JSON response
        """
        # Validate parameters using Pydantic
        params = schemas.GCSConnectionParams(
            client_id=client_id,
            gcs_cred_file=gcs_cred_file,
            gcs_path=gcs_path,
            data_type=data_type,
            name=name,
            description=description,
            connection_type=connection_type,
            credentials=credentials,
        )

        request_uuid = str(uuid.uuid4())
        test_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"email_id": self.api_key},
        )

        test_request = {
            "credentials": params.credentials,
            "connector": "gcs",
            "path": params.gcs_path,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
        }

        with open(params.gcs_cred_file, "rb") as fp:
            test_files = {
                "attachment_files": (
                    os.path.basename(params.gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            client_utils.request(
                "POST",
                test_url,
                headers=headers,
                data=test_request,
                files=test_files,
                request_id=request_uuid,
            )

        # If test passed, create/save the connection
        # use same uuid to track request
        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={params.client_id}"
        )

        create_request = {
            "client_id": params.client_id,
            "connector": "gcs",
            "name": params.name,
            "description": params.description,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
            "credentials": params.credentials,
        }

        with open(params.gcs_cred_file, "rb") as fp:
            create_files = {
                "attachment_files": (
                    os.path.basename(params.gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            return client_utils.request(
                "POST",
                create_url,
                headers=headers,
                data=create_request,
                files=create_files,
                request_id=request_uuid,
            )

    def list_connection(
        self, client_id: str, connection_type: str, connector: str = None
    ):
        request_uuid = str(uuid.uuid4())
        list_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/list"
            f"?client_id={client_id}&uuid={request_uuid}&connection_type={connection_type}"
        )

        if connector:
            list_connection_url += f"&connector={connector}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=client_id,
            extra_headers={"email_id": self.api_key},
        )

        return client_utils.request(
            "GET", list_connection_url, headers=headers, request_id=request_uuid
        )

    def delete_connection(self, client_id: str, connection_id: str):
        """
        Deletes a connector connection by ID.

        :param client_id: The ID of the client.
        :param connection_id: The ID of the connection to delete.
        :return: Parsed JSON response
        """
        # Validate parameters using Pydantic
        params = schemas.DeleteConnectionParams(
            client_id=client_id, connection_id=connection_id
        )
        request_uuid = str(uuid.uuid4())
        delete_url = (
            f"{constants.BASE_URL}/connectors/connections/delete"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "email_id": self.api_key,
            },
        )

        payload = json.dumps({"connection_id": params.connection_id})

        return client_utils.request(
            "POST", delete_url, headers=headers, data=payload, request_id=request_uuid
        )

    def connect_local_files(self, client_id, file_names, connection_id=None):
        """
        Connects local files to the API.

        :param client_id: The ID of the client.
        :param file_names: The list of file names.
        :param connection_id: The ID of the connection.
        :return: The response from the API.
        """
        url = f"{constants.BASE_URL}/connectors/connect/local?client_id={client_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key, api_secret=self.api_secret, client_id=client_id
        )

        body = {"file_names": file_names}
        if connection_id is not None:
            body["temporary_connection_id"] = connection_id

        return client_utils.request("POST", url, headers=headers, json=body)

    @validate_params(client_id=str, files_list=(str, list))
    def upload_files(self, client_id: str, files_list: Union[str, List[str]]):
        """
        Uploads files to the API.

        :param client_id: The ID of the client.
        :param files_list: The list of files to upload or a comma-separated string of file paths.
        :return: The connection ID from the API.
        :raises LabellerrError: If the upload fails.
        """
        # Validate parameters using Pydantic
        params = schemas.UploadFilesParams(client_id=client_id, files_list=files_list)
        try:
            # Use validated files_list from Pydantic
            files_list = params.files_list

            if len(files_list) == 0:
                raise LabellerrError("No files to upload")

            response = self.__process_batch(client_id, files_list)
            connection_id = response["response"]["temporary_connection_id"]
            return connection_id
        except LabellerrError:
            raise
        except Exception as e:
            logging.error(f"Failed to upload files: {str(e)}")
            raise

    def __process_batch(self, client_id, files_list, connection_id=None):
        """
        Processes a batch of files for upload.

        :param client_id: The ID of the client
        :param files_list: List of file paths to process
        :param connection_id: Optional connection ID
        :return: Response from connect_local_files
        """
        # Prepare files for upload
        files = {}
        for file_path in files_list:
            file_name = os.path.basename(file_path)
            files[file_name] = file_path

        response = self.connect_local_files(
            client_id, list(files.keys()), connection_id
        )
        resumable_upload_links = response["response"]["resumable_upload_links"]
        for file_name in resumable_upload_links.keys():
            gcs.upload_to_gcs_resumable(
                resumable_upload_links[file_name], files[file_name]
            )

        return response

    def get_dataset(self, workspace_id, dataset_id):
        """
        Retrieves a dataset from the Labellerr API.

        :param workspace_id: The ID of the workspace.
        :param dataset_id: The ID of the dataset.
        :return: The dataset as JSON.
        """
        url = f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={workspace_id}&uuid={str(uuid.uuid4())}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            extra_headers={"Origin": constants.ALLOWED_ORIGINS},
        )

        return client_utils.request("GET", url, headers=headers)

    def update_rotation_count(self):
        """
        Updates the rotation count for a project.

        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/projects/rotations/add?project_id={self.project_id}&client_id={self.client_id}&uuid={unique_id}"

            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=self.client_id,
                extra_headers={"content-type": "application/json"},
            )

            payload = json.dumps(self.rotation_config)
            logging.info(f"Update Rotation Count Payload: {payload}")

            response = requests.request("POST", url, headers=headers, data=payload)

            logging.info("Rotation configuration updated successfully.")
            client_utils.handle_response(response, unique_id)

            return {"msg": "project rotation configuration updated"}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    def _setup_cloud_connector(
        self, connector_type: str, client_id: str, connector_config: dict
    ):
        """
        Internal method to set up cloud connector (AWS or GCP).

        :param connector_type: Type of connector ('aws' or 'gcp')
        :param client_id: The ID of the client
        :param connector_config: Configuration dictionary for the connector
        :return: connection_id from the created connection
        """
        if connector_type == "s3":
            # AWS connector configuration
            aws_access_key = connector_config.get("aws_access_key")
            aws_secrets_key = connector_config.get("aws_secrets_key")
            s3_path = connector_config.get("s3_path")
            data_type = connector_config.get("data_type")

            if not all([aws_access_key, aws_secrets_key, s3_path, data_type]):
                raise ValueError("Missing required AWS connector configuration")

            result = self.create_aws_connection(
                client_id=client_id,
                aws_access_key=str(aws_access_key),
                aws_secrets_key=str(aws_secrets_key),
                s3_path=str(s3_path),
                data_type=str(data_type),
                name=connector_config.get("name", f"aws_connector_{int(time.time())}"),
                description=connector_config.get(
                    "description", "Auto-created AWS connector"
                ),
                connection_type=connector_config.get("connection_type", "import"),
            )
        elif connector_type == "gcp":
            # GCP connector configuration
            gcs_cred_file = connector_config.get("gcs_cred_file")
            gcs_path = connector_config.get("gcs_path")
            data_type = connector_config.get("data_type")

            if not all([gcs_cred_file, gcs_path, data_type]):
                raise ValueError("Missing required GCS connector configuration")

            result = self.create_gcs_connection(
                client_id=client_id,
                gcs_cred_file=str(gcs_cred_file),
                gcs_path=str(gcs_path),
                data_type=str(data_type),
                name=connector_config.get("name", f"gcs_connector_{int(time.time())}"),
                description=connector_config.get(
                    "description", "Auto-created GCS connector"
                ),
                connection_type=connector_config.get("connection_type", "import"),
            )
        else:
            raise LabellerrError(f"Unsupported cloud connector type: {connector_type}")

        # Extract connection_id from the response
        if isinstance(result, dict) and "response" in result:
            return result["response"].get("connection_id")
        return None

    def enable_multimodal_indexing(self, client_id, dataset_id, is_multimodal=True):
        """
        Enables or disables multimodal indexing for an existing dataset.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset
        :param is_multimodal: Boolean flag to enable (True) or disable (False) multimodal indexing
        :return: Dictionary containing indexing status
        :raises LabellerrError: If the operation fails
        """
        # Validate parameters using Pydantic
        params = schemas.EnableMultimodalIndexingParams(
            client_id=client_id,
            dataset_id=dataset_id,
            is_multimodal=is_multimodal,
        )

        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/search/multimodal_index?client_id={params.client_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "dataset_id": str(params.dataset_id),
                "client_id": params.client_id,
                "is_multimodal": params.is_multimodal,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def get_multimodal_indexing_status(self, client_id, dataset_id):
        """
        Retrieves the current multimodal indexing status for a dataset.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset
        :return: Dictionary containing indexing status and configuration
        :raises LabellerrError: If the operation fails
        """
        # Validate parameters using Pydantic
        params = schemas.GetMultimodalIndexingStatusParams(
            client_id=client_id,
            dataset_id=dataset_id,
        )

        url = (
            f"{constants.BASE_URL}/search/multimodal_index?client_id={params.client_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "dataset_id": str(params.dataset_id),
                "client_id": params.client_id,
                "get_status": True,
            }
        )

        result = client_utils.request("POST", url, headers=headers, data=payload)

        # If the response is null or empty, provide a meaningful default status
        if result.get("response") is None:
            result["response"] = {
                "enabled": False,
                "modalities": [],
                "indexing_type": None,
                "status": "not_configured",
                "message": "Multimodal indexing has not been configured for this dataset",
            }

        return result

    def get_total_folder_file_count_and_total_size(self, folder_path, data_type):
        """
        Retrieves the total count and size of files in a folder using memory-efficient iteration.

        :param folder_path: The path to the folder.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count = 0
        total_file_size = 0
        files_list = []

        # Use os.scandir for better performance and memory efficiency
        def scan_directory(directory):
            nonlocal total_file_count, total_file_size
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_file():
                            file_path = entry.path
                            # Check if the file extension matches based on datatype
                            if not any(
                                file_path.endswith(ext)
                                for ext in constants.DATA_TYPE_FILE_EXT[data_type]
                            ):
                                continue
                            try:
                                file_size = entry.stat().st_size
                                files_list.append(file_path)
                                total_file_count += 1
                                total_file_size += file_size
                            except OSError as e:
                                logging.error(f"Error reading {file_path}: {str(e)}")
                        elif entry.is_dir():
                            # Recursively scan subdirectories
                            scan_directory(entry.path)
            except OSError as e:
                logging.error(f"Error scanning directory {directory}: {str(e)}")

        scan_directory(folder_path)
        return total_file_count, total_file_size, files_list

    def get_total_file_count_and_total_size(self, files_list, data_type):
        """
        Retrieves the total count and size of files in a list.

        :param files_list: The list of file paths.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count = 0
        total_file_size = 0
        # for root, dirs, files in os.walk(folder_path):
        for file_path in files_list:
            if file_path is None:
                continue
            try:
                # check if the file extension matching based on datatype
                if not any(
                    file_path.endswith(ext)
                    for ext in constants.DATA_TYPE_FILE_EXT[data_type]
                ):
                    continue
                file_size = os.path.getsize(file_path)
                total_file_count += 1
                total_file_size += file_size
            except OSError as e:
                logging.error(f"Error reading {file_path}: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error reading {file_path}: {str(e)}")

        return total_file_count, total_file_size, files_list

    def get_all_project_per_client_id(self, client_id):
        """
        Retrieves a list of projects associated with a client ID.

        :param client_id: The ID of the client.
        :return: A dictionary containing the list of projects.
        :raises LabellerrError: If the retrieval fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/project_drafts/projects/detailed_list?client_id={client_id}&uuid={unique_id}"

            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
            )

            response = requests.request("GET", url, headers=headers, data={})
            return client_utils.handle_response(response, unique_id)
        except Exception as e:
            logging.error(f"Failed to retrieve projects: {str(e)}")
            raise

    def _upload_preannotation_sync(
        self, project_id, client_id, annotation_format, annotation_file, conf_bucket=None
    ):
        """
        Synchronous implementation of preannotation upload.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = {
                "project_id": project_id,
                "client_id": client_id,
                "annotation_format": annotation_format,
                "annotation_file": annotation_file,
            }
            client_utils.validate_required_params(
                required_params, list(required_params.keys())
            )
            client_utils.validate_annotation_format(annotation_format, annotation_file)

            request_uuid = str(uuid.uuid4())
            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
            if conf_bucket:
                assert conf_bucket in ["low", "medium", "high"], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                url += f"&conf_bucket={conf_bucket}"
            file_name = client_utils.validate_file_exists(annotation_file)
            # get the direct upload url
            gcs_path = f"{project_id}/{annotation_format}-{file_name}"
            logging.info("Uploading your file to Labellerr. Please wait...")
            direct_upload_url = self.get_direct_upload_url(gcs_path, client_id)
            # Now let's wait for the file to be uploaded to the gcs
            gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
            payload = {}
            url += "&gcs_path=" + gcs_path
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"email_id": self.api_key},
            )
            response = requests.request("POST", url, headers=headers, data=payload)
            response_data = self._handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(project_id, job_id)
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def upload_preannotation_by_project_id_async(
        self, project_id, client_id, annotation_format, annotation_file, conf_bucket=None
    ):
        """
        Asynchronously uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: A Future object that will contain the response from the API.
        :raises LabellerrError: If the upload fails.

        """

        def upload_and_monitor():
            try:
                # validate all the parameters
                required_params = [
                    "project_id",
                    "client_id",
                    "annotation_format",
                    "annotation_file",
                ]
                for param in required_params:
                    if param not in locals():
                        raise LabellerrError(f"Required parameter {param} is missing")

                if annotation_format not in constants.ANNOTATION_FORMAT:
                    raise LabellerrError(
                        f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                    )

                request_uuid = str(uuid.uuid4())
                url = (
                    f"{self.base_url}/actions/upload_answers?"
                    f"project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
                )
                if conf_bucket:
                    assert conf_bucket in ["low", "medium", "high"], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                    url += f"&conf_bucket={conf_bucket}"
                # validate if the file exist then extract file name from the path
                if os.path.exists(annotation_file):
                    file_name = os.path.basename(annotation_file)
                else:
                    raise LabellerrError("File not found")

                # Check if the file extension is .json when annotation_format is coco_json
                if annotation_format == "coco_json":
                    file_extension = os.path.splitext(annotation_file)[1].lower()
                    if file_extension != ".json":
                        raise LabellerrError(
                            "For coco_json annotation format, the file must have a .json extension"
                        )
                # get the direct upload url
                gcs_path = f"{project_id}/{annotation_format}-{file_name}"
                logging.info("Uploading your file to Labellerr. Please wait...")
                direct_upload_url = self.get_direct_upload_url(gcs_path, client_id)
                # Now let's wait for the file to be uploaded to the gcs
                gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
                payload = {}
                url += "&gcs_path=" + gcs_path
                headers = client_utils.build_headers(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    client_id=client_id,
                    extra_headers={"email_id": self.api_key},
                )
                response = requests.request("POST", url, headers=headers, data=payload)
                response_data = self._handle_upload_response(response, request_uuid)

                # read job_id from the response
                job_id = response_data["response"]["job_id"]
                self.client_id = client_id
                self.job_id = job_id
                self.project_id = project_id

                logging.info(f"Pre annotation upload successful. Job ID: {job_id}")

                # Now monitor the status
                headers = client_utils.build_headers(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    client_id=self.client_id,
                    extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                )
                status_url = f"{self.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
                
                def check_job_status():
                    response = requests.request(
                        "GET", status_url, headers=headers, data={}
                    )
                    status_data = response.json()
                    logging.debug(f"Status data: {status_data}")
                    return status_data

                def is_job_completed(status_data):
                    return status_data.get("response", {}).get("status") == "completed"

                def on_success(status_data):
                    logging.info("Pre-annotation job completed.")

                def on_exception(e):
                    logging.error(f"Failed to get preannotation job status: {str(e)}")
                    raise LabellerrError(f"Failed to get preannotation job status: {str(e)}")

                result = poll(
                    function=check_job_status,
                    condition=is_job_completed,
                    interval=5.0,
                    on_success=on_success,
                    on_exception=on_exception
                )
                
                return result

            except Exception as e:
                logging.exception(f"Failed to upload preannotation: {str(e)}")
                raise

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(upload_and_monitor)

    def preannotation_job_status_async(self, project_id, job_id):
        """
        Get the status of a preannotation job asynchronously with timeout protection.

        Args:
            project_id: The project ID
            job_id: The job ID to check status for
            max_retries: Maximum number of retries before timing out (default: 60 retries = 5 minutes)
            retry_interval: Seconds to wait between retries (default: 5 seconds)

        Returns:
            concurrent.futures.Future: A future that will contain the final job status

        Raises:
            LabellerrError: If max retries exceeded or job status check fails
        """

        def check_status():
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=self.client_id,
                extra_headers={"Origin": constants.ALLOWED_ORIGINS},
            )
            url = f"{self.base_url}/actions/upload_answers_status?project_id={project_id}&job_id={job_id}&client_id={self.client_id}"
            payload = {}

            def get_job_status():
                response = requests.request(
                    "GET", url, headers=headers, data=payload
                )
                response_data = response.json()
                
                # Log current status for visibility
                current_status = response_data.get('response', {}).get('status', 'unknown')
                logging.info(f"Pre-annotation job status: {current_status}")
                
                # Check if job failed and raise error immediately
                if current_status == 'failed':
                    raise LabellerrError('Internal server error: ', response_data)
                
                return response_data

            def is_job_completed(response_data):
                return response_data.get("response", {}).get("status") == "completed"

            def on_success(response_data):
                logging.info("Pre-annotation job completed successfully!")

            def on_exception(e):
                logging.error(f"Failed to get preannotation job status: {str(e)}")
                raise LabellerrError(f"Failed to get preannotation job status: {str(e)}")

            return poll(
                function=get_job_status,
                condition=is_job_completed,
                on_success=on_success,
                on_exception=on_exception
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(check_status)

    def upload_preannotation_by_project_id(
        self, project_id, client_id, annotation_format, annotation_file, conf_bucket=None
    ):
        """
        Uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = [
                "project_id",
                "client_id",
                "annotation_format",
                "annotation_file",
            ]
            for param in required_params:
                if param not in locals():
                    raise LabellerrError(f"Required parameter {param} is missing")

            if annotation_format not in constants.ANNOTATION_FORMAT:
                raise LabellerrError(
                    f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                )

            request_uuid = str(uuid.uuid4())
            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
            if conf_bucket:
                assert conf_bucket in ["low", "medium", "high"], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                url += f"&conf_bucket={conf_bucket}"
            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, "rb") as f:
                files = [("file", (file_name, f, "application/octet-stream"))]
                headers = client_utils.build_headers(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    client_id=client_id,
                    extra_headers={"email_id": self.api_key},
                )
                response = requests.request(
                    "POST", url, headers=headers, data=payload, files=files
                )
            response_data = self._handle_upload_response(response, request_uuid)
            logging.debug(f"response_data: {response_data}")

            # read job_id from the response
            job_id = response_data["response"]["job_id"]

            logging.info(f"Preannotation job started successfully. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(project_id, job_id)
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def create_local_export(self, project_id, client_id, export_config):
        """
        Creates a local export with the given configuration.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param export_config: Export configuration dictionary.
        :return: The response from the API.
        :raises LabellerrError: If the export creation fails.
        """
        # Validate parameters using Pydantic
        schemas.CreateLocalExportParams(
            project_id=project_id,
            client_id=client_id,
            export_config=export_config,
        )
        # Validate export config using client_utils
        client_utils.validate_export_config(export_config)

        unique_id = client_utils.generate_request_id()
        export_config.update({"export_destination": "local", "question_ids": ["all"]})

        payload = json.dumps(export_config)
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        return client_utils.request(
            "POST",
            f"{self.base_url}/sdk/export/files?project_id={project_id}&client_id={client_id}",
            headers=headers,
            data=payload,
            request_id=unique_id,
        )

    def fetch_download_url(self, project_id, uuid, export_id, client_id):
        try:
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"Content-Type": "application/json"},
            )

            response = requests.get(
                url=f"{constants.BASE_URL}/exports/download",
                params={
                    "client_id": client_id,
                    "project_id": project_id,
                    "uuid": uuid,
                    "report_id": export_id,
                },
                headers=headers,
            )

            if response.ok:
                return json.dumps(response.json().get("response"), indent=2)
            else:
                raise LabellerrError(
                    f" Download request failed: {response.status_code} - {response.text}"
                )
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download export: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error in download_function: {str(e)}")
            raise

    @validate_params(project_id=str, report_ids=list, client_id=str)
    def check_export_status(
        self, project_id: str, report_ids: List[str], client_id: str
    ):
        request_uuid = client_utils.generate_request_id()
        try:
            if not project_id:
                raise LabellerrError("project_id cannot be null")
            if not report_ids:
                raise LabellerrError("report_ids cannot be empty")

            # Construct URL
            url = f"{constants.BASE_URL}/exports/status?project_id={project_id}&uuid={request_uuid}&client_id={client_id}"

            # Headers
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"Content-Type": "application/json"},
            )

            payload = json.dumps({"report_ids": report_ids})

            response = requests.post(url, headers=headers, data=payload)
            result = client_utils.handle_response(response, request_uuid)

            # Now process each report_id
            for status_item in result.get("status", []):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = (  # noqa E999 todo check use of that
                        self.fetch_download_url(
                            project_id=project_id,
                            uuid=request_uuid,
                            export_id=status_item["report_id"],
                            client_id=client_id,
                        )
                    )

            return json.dumps(result, indent=2)

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to check export status: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error checking export status: {str(e)}")
            raise

    def create_template(self, client_id, data_type, template_name, questions):
        """
        Creates an annotation template with the given configuration.

        :param client_id: The ID of the client.
        :param data_type: The type of data for the template (image, video, etc.).
        :param template_name: The name of the template.
        :param questions: List of questions/annotations for the template.
        :return: The response from the API containing template details.
        :raises LabellerrError: If the creation fails.
        """
        # Validate parameters using Pydantic
        params = schemas.CreateTemplateParams(
            client_id=client_id,
            data_type=data_type,
            template_name=template_name,
            questions=questions,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/create_template?client_id={params.client_id}&data_type={params.data_type}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "templateName": params.template_name,
                "questions": [q.model_dump() for q in params.questions],
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def create_user(
        self,
        client_id,
        first_name,
        last_name,
        email_id,
        projects,
        roles,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
    ):
        """
        Creates a new user in the system.

        :param client_id: The ID of the client
        :param first_name: User's first name
        :param last_name: User's last name
        :param email_id: User's email address
        :param projects: List of project IDs to assign the user to
        :param roles: List of role objects with project_id and role_id
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :return: Dictionary containing user creation response
        :raises LabellerrError: If the creation fails
        """
        # Validate parameters using Pydantic
        params = schemas.CreateUserParams(
            client_id=client_id,
            first_name=first_name,
            last_name=last_name,
            email_id=email_id,
            projects=projects,
            roles=roles,
            work_phone=work_phone,
            job_title=job_title,
            language=language,
            timezone=timezone,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/register?client_id={params.client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        payload = json.dumps(
            {
                "first_name": params.first_name,
                "last_name": params.last_name,
                "work_phone": params.work_phone,
                "job_title": params.job_title,
                "language": params.language,
                "timezone": params.timezone,
                "email_id": params.email_id,
                "projects": params.projects,
                "client_id": params.client_id,
                "roles": params.roles,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def update_user_role(
        self,
        client_id,
        project_id,
        email_id,
        roles,
        first_name=None,
        last_name=None,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
        profile_image="",
    ):
        """
        Updates a user's role and profile information.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param roles: List of role objects with project_id and role_id
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :param profile_image: User's profile image (optional)
        :return: Dictionary containing update response
        :raises LabellerrError: If the update fails
        """
        # Validate parameters using Pydantic
        params = schemas.UpdateUserRoleParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            roles=roles,
            first_name=first_name,
            last_name=last_name,
            work_phone=work_phone,
            job_title=job_title,
            language=language,
            timezone=timezone,
            profile_image=profile_image,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/update?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        # Build the payload with all provided information
        # Extract project_ids from roles for API requirement
        project_ids = [
            role.get("project_id") for role in params.roles if "project_id" in role
        ]

        payload_data = {
            "profile_image": params.profile_image,
            "work_phone": params.work_phone,
            "job_title": params.job_title,
            "language": params.language,
            "timezone": params.timezone,
            "email_id": params.email_id,
            "client_id": params.client_id,
            "roles": params.roles,
            "projects": project_ids,  # API requires projects list extracted from roles (same format as create_user)
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name

        payload = json.dumps(payload_data)

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def delete_user(
        self,
        client_id,
        project_id,
        email_id,
        user_id,
        first_name=None,
        last_name=None,
        is_active=1,
        role="Annotator",
        user_created_at=None,
        max_activity_created_at=None,
        image_url="",
        name=None,
        activity="No Activity",
        creation_date=None,
        status="Activated",
    ):
        """
        Deletes a user from the system.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param user_id: User's unique identifier
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param is_active: User's active status (default: 1)
        :param role: User's role (default: "Annotator")
        :param user_created_at: User creation timestamp (optional)
        :param max_activity_created_at: Max activity timestamp (optional)
        :param image_url: User's profile image URL (optional)
        :param name: User's display name (optional)
        :param activity: User's activity status (default: "No Activity")
        :param creation_date: User creation date (optional)
        :param status: User's status (default: "Activated")
        :return: Dictionary containing deletion response
        :raises LabellerrError: If the deletion fails
        """
        # Validate parameters using Pydantic
        params = schemas.DeleteUserParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            role=role,
            user_created_at=user_created_at,
            max_activity_created_at=max_activity_created_at,
            image_url=image_url,
            name=name,
            activity=activity,
            creation_date=creation_date,
            status=status,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/delete?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        # Build the payload with all provided information
        payload_data = {
            "email_id": params.email_id,
            "is_active": params.is_active,
            "role": params.role,
            "user_id": params.user_id,
            "imageUrl": params.image_url,
            "email": params.email_id,
            "activity": params.activity,
            "status": params.status,
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name
        if params.user_created_at is not None:
            payload_data["user_created_at"] = params.user_created_at
        if params.max_activity_created_at is not None:
            payload_data["max_activity_created_at"] = params.max_activity_created_at
        if params.name is not None:
            payload_data["name"] = params.name
        if params.creation_date is not None:
            payload_data["creationDate"] = params.creation_date

        payload = json.dumps(payload_data)

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def add_user_to_project(self, client_id, project_id, email_id, role_id=None):
        """
        Adds a user to a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param role_id: Optional role ID to assign to the user
        :return: Dictionary containing addition response
        :raises LabellerrError: If the addition fails
        """
        # Validate parameters using Pydantic
        params = schemas.AddUserToProjectParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            role_id=role_id,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/add_user_to_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        if params.role_id is not None:
            payload_data["role_id"] = params.role_id

        payload = json.dumps(payload_data)
        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def remove_user_from_project(self, client_id, project_id, email_id):
        """
        Removes a user from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :return: Dictionary containing removal response
        :raises LabellerrError: If the removal fails
        """
        # Validate parameters using Pydantic
        params = schemas.RemoveUserFromProjectParams(
            client_id=client_id, project_id=project_id, email_id=email_id
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/remove_user_from_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        payload = json.dumps(payload_data)
        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    # TODO: this is not working from UI
    def change_user_role(self, client_id, project_id, email_id, new_role_id):
        """
        Changes a user's role in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param new_role_id: The new role ID to assign to the user
        :return: Dictionary containing role change response
        :raises LabellerrError: If the role change fails
        """
        # Validate parameters using Pydantic
        params = schemas.ChangeUserRoleParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            new_role_id=new_role_id,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/change_user_role?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload_data = {
            "email_id": params.email_id,
            "new_role_id": params.new_role_id,
            "uuid": unique_id,
        }

        payload = json.dumps(payload_data)
        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def list_file(
        self, client_id, project_id, search_queries, size=10, next_search_after=None
    ):
        # Validate parameters using Pydantic
        params = schemas.ListFileParams(
            client_id=client_id,
            project_id=project_id,
            search_queries=search_queries,
            size=size,
            next_search_after=next_search_after,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/project_files?project_id={params.project_id}&client_id={params.client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "search_queries": params.search_queries,
                "size": params.size,
                "next_search_after": params.next_search_after,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def bulk_assign_files(self, client_id, project_id, file_ids, new_status):
        # Validate parameters using Pydantic
        params = schemas.BulkAssignFilesParams(
            client_id=client_id,
            project_id=project_id,
            file_ids=file_ids,
            new_status=new_status,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/files/bulk_assign?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "file_ids": params.file_ids,
                "new_status": params.new_status,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    @validate_params(client_id=str, project_id=str, file_id=str, key_frames=list)
    def link_key_frame(
        self, client_id: str, project_id: str, file_id: str, key_frames: List[KeyFrame]
    ):
        """
        Links key frames to a file in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param file_id: The ID of the file
        :param key_frames: List of KeyFrame objects to link
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/actions/add_update_keyframes?client_id={client_id}&uuid={unique_id}"
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
            )

            body = {
                "project_id": project_id,
                "file_id": file_id,
                "keyframes": [
                    kf.__dict__ if isinstance(kf, KeyFrame) else kf for kf in key_frames
                ],
            }

            response = self._make_request("POST", url, headers=headers, json=body)
            return self._handle_response(response, unique_id)

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to link key frames: {str(e)}")

    @validate_params(client_id=str, project_id=str)
    def delete_key_frames(self, client_id: str, project_id: str):
        """
        Deletes key frames from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/actions/delete_keyframes?project_id={project_id}&uuid={unique_id}&client_id={client_id}"
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
            )

            response = self._make_request("POST", url, headers=headers)
            return self._handle_response(response, unique_id)

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to delete key frames: {str(e)}")

    # ===== Dataset-related methods (delegated to DataSets) =====

    def create_project(
        self,
        project_name,
        data_type,
        client_id,
        attached_datasets,
        annotation_template_id,
        rotations,
        use_ai=False,
        created_by=None,
    ):
        """
        Creates a project with the given configuration.
        Delegates to the DataSets handler.
        """
        return self.datasets.create_project(
            project_name,
            data_type,
            client_id,
            attached_datasets,
            annotation_template_id,
            rotations,
            use_ai,
            created_by,
        )

    def initiate_create_project(self, payload):
        """
        Orchestrates project creation by handling dataset creation, annotation guidelines,
        and final project setup. Delegates to the DataSets handler.
        """
        return self.datasets.initiate_create_project(payload)

    def create_annotation_guideline(
        self, client_id, questions, template_name, data_type
    ):
        """
        Creates an annotation guideline for a project.
        Delegates to the DataSets handler.
        """
        return self.datasets.create_annotation_guideline(
            client_id, questions, template_name, data_type
        )

    def validate_rotation_config(self, rotation_config):
        """
        Validates a rotation configuration.
        Delegates to the DataSets handler.
        """
        return self.datasets.validate_rotation_config(rotation_config)

    def create_dataset(
        self,
        dataset_config,
        files_to_upload=None,
        folder_to_upload=None,
        connector_config=None,
    ):
        """
        Creates a dataset with support for multiple data types and connectors.
        Delegates to the DataSets handler.
        """
        return self.datasets.create_dataset(
            dataset_config, files_to_upload, folder_to_upload, connector_config
        )

    def delete_dataset(self, client_id, dataset_id):
        """
        Deletes a dataset from the system.
        Delegates to the DataSets handler.
        """
        return self.datasets.delete_dataset(client_id, dataset_id)

    def upload_folder_files_to_dataset(self, data_config):
        """
        Uploads local files from a folder to a dataset using parallel processing.
        Delegates to the DataSets handler.
        """
        return self.datasets.upload_folder_files_to_dataset(data_config)

    def initiate_attach_dataset_to_project(self, client_id, project_id, dataset_id):
        """
        Orchestrates attaching a dataset to a project.
        Delegates to the DataSets handler.
        """
        return self.datasets.attach_dataset_to_project(
            client_id, project_id, dataset_id=dataset_id
        )

    def initiate_attach_datasets_to_project(self, client_id, project_id, dataset_ids):
        """
        Orchestrates attaching multiple datasets to a project (batch operation).
        Delegates to the DataSets handler.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param dataset_ids: List of dataset IDs to attach
        :return: Dictionary containing attachment status
        """
        return self.datasets.attach_dataset_to_project(
            client_id, project_id, dataset_ids=dataset_ids
        )

    def initiate_detach_dataset_from_project(self, client_id, project_id, dataset_id):
        """
        Orchestrates detaching a dataset from a project.
        Delegates to the DataSets handler.
        """
        return self.datasets.detach_dataset_from_project(
            client_id, project_id, dataset_id=dataset_id
        )

    def initiate_detach_datasets_from_project(self, client_id, project_id, dataset_ids):
        """
        Orchestrates detaching multiple datasets from a project (batch operation).
        Delegates to the DataSets handler.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param dataset_ids: List of dataset IDs to detach
        :return: Dictionary containing detachment status
        """
        return self.datasets.detach_dataset_from_project(
            client_id, project_id, dataset_ids=dataset_ids
        )
