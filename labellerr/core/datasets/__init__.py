import json
import logging
import uuid

from .. import constants, schemas
from ..exceptions import LabellerrError
from .audio_dataset import AudioDataSet as LabellerrAudioDataset
from .base import LabellerrDataset
from .document_dataset import DocumentDataSet as LabellerrDocumentDataset
from .image_dataset import ImageDataset as LabellerrImageDataset
from .utils import upload_files, upload_folder_files_to_dataset
from .video_dataset import VideoDataset as LabellerrVideoDataset
from ..connectors import LabellerrConnection

from ..client import LabellerrClient

__all__ = [
    "LabellerrImageDataset",
    "LabellerrVideoDataset",
    "LabellerrDataset",
    "LabellerrAudioDataset",
    "LabellerrDocumentDataset",
]


def create_dataset_from_connection(
    client: "LabellerrClient",
    dataset_config: schemas.DatasetConfig,
    connection: LabellerrConnection | str,
    path: str,
) -> LabellerrDataset:
    """
    Creates a dataset via a connection.

    :param client: The client to use for the request.
    :param dataset_config: The configuration for the dataset.
    :param connection_id: The ID of the connection to use for the dataset.
    :param path: The path to the data source.
    :return: The LabellerrDataset instance.
    """
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/datasets/create?client_id={client.client_id}&uuid={unique_id}"

    payload = json.dumps(
        {
            "dataset_name": dataset_config.dataset_name,
            "dataset_description": dataset_config.dataset_description,
            "data_type": dataset_config.data_type,
            "connection_id": (
                connection.connection_id
                if isinstance(connection, LabellerrConnection)
                else connection
            ),
            "path": path,
            "client_id": client.client_id,
            "es_multimodal_index": dataset_config.multimodal_indexing,
        }
    )
    response_data = client.make_request(
        "POST",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
        data=payload,
    )
    dataset_id = response_data["response"]["dataset_id"]
    return LabellerrDataset(client=client, dataset_id=dataset_id)  # type: ignore[abstract]


def create_dataset_from_local(
    client: "LabellerrClient",
    dataset_config: schemas.DatasetConfig,
    files_to_upload=None,
    folder_to_upload=None,
):
    """
    Creates a dataset with support for multiple data types and connectors.

    :param dataset_config: A dictionary containing the configuration for the dataset.
                          Required fields: client_id, dataset_name, data_type
                          Optional fields: dataset_description, connector_type
                          Can also be a DatasetConfig Pydantic model instance.
    :param files_to_upload: List of file paths to upload (for local connector)
    :param folder_to_upload: Path to folder to upload (for local connector)
    :return: The LabellerrDataset instance.
    """
    if files_to_upload is not None:
        connection_id = upload_files(
            client,
            client_id=client.client_id,
            files_list=files_to_upload,
        )
    elif folder_to_upload is not None:
        result = upload_folder_files_to_dataset(
            client,
            {
                "client_id": client.client_id,
                "folder_path": folder_to_upload,
                "data_type": dataset_config.data_type,
            },
        )
        connection_id = result.pop("connection_id")
        logging.info(f"Folder uploaded successfully. {result}")
    else:
        raise LabellerrError("No files or folder to upload provided")

    return create_dataset_from_connection(
        client,
        dataset_config,
        connection_id,
        path="local",
    )


def delete_dataset(client: "LabellerrClient", dataset_id: str):
    """
    Deletes a dataset from the system.

    :param dataset_id: The ID of the dataset to delete
    :return: Dictionary containing deletion status
    :raises LabellerrError: If the deletion fails
    """
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/datasets/{dataset_id}/delete?client_id={client.client_id}&uuid={unique_id}"

    return client.make_request(
        "DELETE",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
    )


def list_datasets(
    client: "LabellerrClient",
    datatype: str,
    scope: schemas.DataSetScope,
    page_size: int = constants.DEFAULT_PAGE_SIZE,
    last_dataset_id: str = None,
):
    """
    Retrieves datasets by parameters with pagination support.
    Always returns a generator that yields individual datasets.

    :param client: The client object.
    :param datatype: The type of data for the dataset.
    :param scope: The permission scope for the dataset.
    :param page_size: Number of datasets to return per page (default: 10)
                        Use -1 to auto-paginate through all pages
                        Use specific number to fetch only that many datasets from first page
    :param last_dataset_id: ID of the last dataset from previous page for pagination
                            (only used when page_size is a specific number, ignored for -1)
    :return: Generator yielding individual datasets

    Examples:
        # Auto-paginate through all datasets
        for dataset in get_all_datasets(client, "image", DataSetScope.client, page_size=-1):
            print(dataset)

        # Get first 20 datasets
        datasets = list(get_all_datasets(client, "image", DataSetScope.client, page_size=20))

        # Manual pagination - first page of 10
        gen = get_all_datasets(client, "image", DataSetScope.client, page_size=10)
        first_10 = list(gen)
    """
    # Auto-pagination mode: yield datasets across all pages
    if page_size == -1:
        actual_page_size = constants.DEFAULT_PAGE_SIZE
        current_last_dataset_id = None
        has_more = True

        while has_more:
            unique_id = str(uuid.uuid4())
            url = (
                f"{constants.BASE_URL}/datasets/list?client_id={client.client_id}&data_type={datatype}&permission_level={scope}"
                f"&page_size={actual_page_size}&uuid={unique_id}"
            )

            if current_last_dataset_id:
                url += f"&last_dataset_id={current_last_dataset_id}"

            response = client.make_request(
                "GET",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )

            datasets = response.get("response", {}).get("datasets", [])
            for dataset in datasets:
                yield dataset

            # Check if there are more pages
            has_more = response.get("response", {}).get("has_more", False)
            current_last_dataset_id = response.get("response", {}).get(
                "last_dataset_id"
            )

    else:
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/list?client_id={client.client_id}&data_type={datatype}&permission_level={scope}"
            f"&page_size={page_size}&uuid={unique_id}"
        )

        # Add last_dataset_id for pagination if provided
        if last_dataset_id:
            url += f"&last_dataset_id={last_dataset_id}"

        response = client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        datasets = response.get("response", {}).get("datasets", [])
        for dataset in datasets:
            yield dataset
