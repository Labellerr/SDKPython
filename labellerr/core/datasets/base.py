"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc."""

import json
import logging
import uuid
from abc import ABCMeta
from typing import Dict, Any, List, TYPE_CHECKING

from .. import constants
from ..exceptions import InvalidDatasetError, LabellerrError
from ..client import LabellerrClient

from ..files import LabellerrFile
from ..connectors import LabellerrConnection

if TYPE_CHECKING:
    from ..projects import LabellerrProject


class LabellerrDatasetMeta(ABCMeta):
    # Class-level registry for dataset types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, data_type, dataset_class):
        """Register a dataset type handler"""
        cls._registry[data_type] = dataset_class

    @staticmethod
    def get_dataset(client: "LabellerrClient", dataset_id: str):
        """Get dataset from Labellerr API"""
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={client.client_id}"
            f"&uuid={unique_id}"
        )

        response = client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)

    """Metaclass that combines ABC functionality with factory pattern"""

    def __call__(cls, client, dataset_id, **kwargs):
        # Only intercept calls to the base LabellerrFile class
        if cls.__name__ != "LabellerrDataset":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, dataset_id, **kwargs)
            return instance
        dataset_data = cls.get_dataset(client, dataset_id)
        if dataset_data is None:
            raise InvalidDatasetError(f"Dataset not found: {dataset_id}")
        data_type = dataset_data.get("data_type")

        dataset_class = cls._registry.get(data_type)
        if dataset_class is None:
            raise InvalidDatasetError(f"Unknown data type: {data_type}")
        kwargs["dataset_data"] = dataset_data
        return dataset_class(client, dataset_id, **kwargs)


class LabellerrDataset(metaclass=LabellerrDatasetMeta):
    """Base class for all Labellerr files with factory behavior"""

    def __init__(self, client: "LabellerrClient", dataset_id: str, **kwargs):
        self.client = client
        self.__dataset_id_input = dataset_id
        self.__dataset_data = kwargs["dataset_data"]

    @property
    def dataset_id(self):
        return self.__dataset_id_input

    @property
    def name(self):
        return self.__dataset_data.get("name")

    @property
    def description(self):
        return self.__dataset_data.get("description")

    @property
    def created_at(self):
        return self.__dataset_data.get("created_at")

    @property
    def created_by(self):
        return self.__dataset_data.get("created_by")

    @property
    def files_count(self):
        return self.__dataset_data.get("files_count", 0)

    @property
    def status_code(self):
        return self.__dataset_data.get("status_code", 501)  # if not found, return 501

    @property
    def data_type(self):
        return self.__dataset_data.get("data_type")

    def status(self) -> Dict[str, Any]:
        """
        Poll dataset status until completion or timeout.

        Args:
            interval: Time in seconds between status checks (default: 2.0)
            timeout: Maximum time in seconds to poll before giving up
            max_retries: Maximum number of retries before giving up

        Returns:
            Final dataset data with status information

        Examples:
            # Poll until dataset processing is complete
            final_status = dataset.status()

            # Poll with custom timeout
            final_status = dataset.status(timeout=300)

            # Poll with custom interval and max retries
            final_status = dataset.status(interval=5.0, max_retries=20)
        """
        from ..utils import poll

        def get_dataset_status():
            unique_id = str(uuid.uuid4())
            url = (
                f"{constants.BASE_URL}/datasets/{self.dataset_id}?client_id={self.client.client_id}"
                f"&uuid={unique_id}"
            )

            response = self.client.make_request(
                "GET",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )
            dataset_data = response.get("response", {})
            if dataset_data:
                self.__dataset_data = dataset_data
            return dataset_data

        def is_completed(dataset_data):
            status_code = dataset_data.get("status_code", 500)
            # Consider dataset complete when status_code is 200 (success) or >= 400 (error/failed)
            return status_code == 300 or status_code >= 400

        def on_success(dataset_data):
            status_code = dataset_data.get("status_code", 500)
            if status_code == 300:
                logging.info(
                    "Dataset %s processing completed successfully!", self.dataset_id
                )
            else:
                logging.warning(
                    "Dataset %s processing finished with status code: %s",
                    self.dataset_id,
                    status_code,
                )
            return dataset_data

        return poll(
            function=get_dataset_status,
            condition=is_completed,
            interval=2.0,
            timeout=None,
            max_retries=None,
            on_success=on_success,
        )

    def fetch_files(self, page_size: int = 1000) -> List[LabellerrFile]:
        """
        Fetch all files in this dataset as LabellerrFile instances.

        :param page_size: Number of files to fetch per API request (default: 10)
        :return: List of file IDs
        """
        print(f"Fetching files for dataset: {self.dataset_id}")
        file_ids = []
        next_search_after = None  # Start with None for first page

        while True:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/search/files/all"
            params = {
                "sort_by": "created_at",
                "sort_order": "desc",
                "size": page_size,
                "uuid": unique_id,
                "dataset_id": self.dataset_id,
                "client_id": self.client.client_id,
            }

            # Add next_search_after only if it exists (don't send on first request)
            if next_search_after:
                url += f"?next_search_after={next_search_after}"

            response = self.client.make_request(
                "GET", url, extra_headers=None, request_id=unique_id, params=params
            )
            print(response)
            # Extract files from the response
            files = response.get("response", {}).get("files", [])

            # Collect file IDs
            for file_info in files:
                file_id = file_info.get("file_id")
                if file_id:
                    file_ids.append(file_id)

            # Get next_search_after for pagination
            next_search_after = response.get("response", {}).get("next_search_after")

            # Break if no more pages or no files returned
            if not next_search_after or not files:
                break

        files = []

        for file_id in file_ids:
            try:
                _file = LabellerrFile(
                    client=self.client,
                    file_id=file_id,
                    dataset_id=self.dataset_id,
                )
                files.append(_file)
            except LabellerrError as e:
                logging.warning(
                    f"Warning: Failed to create file instance for {file_id}: {str(e)}"
                )

        return files

    def sync_with_connection(
        self,
        project: "LabellerrProject",
        path: str,
        data_type: str,
        connection: LabellerrConnection,
    ):
        """
        Syncs datasets with the backend.

        :param project: The project instance
        :param path: The path to sync
        :param data_type: Type of data (image, video, audio, document, text)
        :param connection: The connection instance
        :return: Dictionary containing sync status
        :raises LabellerrError: If the sync fails
        """

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/datasets/sync?uuid={unique_id}&client_id={self.client.client_id}"

        payload = json.dumps(
            {
                "client_id": self.client.client_id,
                "project_id": project.project_id,
                "dataset_id": self.dataset_id,
                "path": path,
                "data_type": data_type,
                "email_id": self.client.api_key,
                "connection_id": connection.connection_id,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def enable_multimodal_indexing(self, is_multimodal=True):
        """
        Enables or disables multimodal indexing for an existing dataset.

        :param is_multimodal: Boolean flag to enable (True) or disable (False) multimodal indexing
        :return: Dictionary containing indexing status
        :raises LabellerrError: If the operation fails
        """
        assert is_multimodal is True, "Disabling multimodal indexing is not supported"

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/multimodal_index?client_id={self.client.client_id}"

        payload = json.dumps(
            {
                "dataset_id": str(self.dataset_id),
                "client_id": self.client.client_id,
                "is_multimodal": is_multimodal,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )
