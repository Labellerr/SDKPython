"""
Unit tests for dataset creation functions.

This module focuses on testing the create_dataset_from_connection and
create_dataset_from_local functionality.
"""

from unittest.mock import patch

import pytest

from labellerr.core.datasets import (
    create_dataset_from_connection,
    create_dataset_from_local,
)
from labellerr.core.datasets.base import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.schemas import DatasetConfig


@pytest.mark.unit
class TestCreateDatasetFunctions:
    """Test dataset creation functions"""

    def test_create_dataset_from_connection_success(self, client):
        """Test successful dataset creation from connection"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Dataset",
            data_type="image",
            connector_type="aws",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock both the dataset creation and the get_dataset call
        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                # Use string connection_id instead of Mock object
                connection_id = "test-connection-id"

                dataset = create_dataset_from_connection(
                    client=client,
                    dataset_config=dataset_config,
                    connection=connection_id,
                    path="s3://test-bucket/path/to/data",
                )

                # Should succeed
                assert dataset is not None

    def test_create_dataset_from_local_with_files(self, client):
        """Test successful dataset creation from local files"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Local Dataset",
            data_type="image",
            connector_type="local",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock the upload_files function and dataset creation
        with patch(
            "labellerr.core.datasets.upload_files", return_value="test-connection-id"
        ):
            with patch.object(client, "make_request", return_value=mock_response):
                with patch(
                    "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                    return_value={
                        "dataset_id": "test-dataset-id",
                        "data_type": "image",
                    },
                ):
                    # Mock create_dataset_from_connection to avoid the connection object issue
                    with patch(
                        "labellerr.core.datasets.create_dataset_from_connection",
                        return_value=LabellerrDataset(
                            client=client, dataset_id="test-dataset-id"
                        ),
                    ):
                        dataset = create_dataset_from_local(
                            client=client,
                            dataset_config=dataset_config,
                            files_to_upload=["test_file1.jpg", "test_file2.jpg"],
                        )

                    # Should succeed
                    assert dataset is not None

    def test_create_dataset_from_local_with_folder(self, client):
        """Test successful dataset creation from local folder"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Local Dataset",
            data_type="image",
            connector_type="local",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock the upload_folder_files_to_dataset function and dataset creation
        with patch(
            "labellerr.core.datasets.upload_folder_files_to_dataset",
            return_value={"connection_id": "test-connection-id", "status": "success"},
        ):
            with patch.object(client, "make_request", return_value=mock_response):
                with patch(
                    "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                    return_value={
                        "dataset_id": "test-dataset-id",
                        "data_type": "image",
                    },
                ):
                    # Mock create_dataset_from_connection to avoid the connection object issue
                    with patch(
                        "labellerr.core.datasets.create_dataset_from_connection",
                        return_value=LabellerrDataset(
                            client=client, dataset_id="test-dataset-id"
                        ),
                    ):
                        dataset = create_dataset_from_local(
                            client=client,
                            dataset_config=dataset_config,
                            folder_to_upload="/path/to/test/folder",
                        )

                    # Should succeed
                    assert dataset is not None

    def test_create_dataset_from_local_no_files_or_folder(self, client):
        """Test error when neither files nor folder is provided for local dataset"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Local Dataset",
            data_type="image",
            connector_type="local",
        )

        with pytest.raises(LabellerrError) as exc_info:
            create_dataset_from_local(
                client=client,
                dataset_config=dataset_config,
                # Missing both files_to_upload and folder_to_upload
            )

        assert "No files or folder to upload provided" in str(exc_info.value)

    def test_create_dataset_from_connection_with_different_paths(self, client):
        """Test dataset creation with different path formats"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Dataset",
            data_type="image",
            connector_type="gcp",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Test with GCS path
        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                # Use string connection_id instead of Mock object
                connection_id = "test-gcp-connection-id"

                dataset = create_dataset_from_connection(
                    client=client,
                    dataset_config=dataset_config,
                    connection=connection_id,
                    path="gs://test-bucket/path/to/data",
                )

                # Should succeed
                assert dataset is not None
