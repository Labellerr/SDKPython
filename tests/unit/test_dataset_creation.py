"""
Comprehensive unit tests for dataset creation and management.

This module tests the dataset creation, deletion, and listing functionality
including validation, error handling, and edge cases.
"""

from unittest.mock import Mock, patch
import pytest

from labellerr.core.datasets import (
    create_dataset_from_connection,
    create_dataset_from_local,
    delete_dataset,
    list_datasets,
)
from labellerr.core.datasets.base import LabellerrDataset, LabellerrDatasetMeta
from labellerr.core.exceptions import LabellerrError, InvalidDatasetIDError
from labellerr.core.schemas import DatasetConfig, DataSetScope


@pytest.mark.unit
class TestDatasetCreation:
    """Test dataset creation functions"""

    def test_create_dataset_from_connection_with_string_connection_id(self, client):
        """Test dataset creation with string connection_id"""
        dataset_config = DatasetConfig(
            dataset_name="Test Dataset",
            data_type="image",
        )

        mock_response = {
            "response": {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "data_type": "image",
            }
        }

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
                return_value={
                    "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                    "data_type": "image",
                },
            ):
                dataset = create_dataset_from_connection(
                    client=client,
                    dataset_config=dataset_config,
                    connection="test-connection-id",
                    path="s3://bucket/path",
                )

                assert dataset is not None
                assert dataset.dataset_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_create_dataset_from_connection_with_connection_object(self, client):
        """Test dataset creation with LabellerrConnection object"""
        from labellerr.core.connectors import LabellerrConnection

        dataset_config = DatasetConfig(
            dataset_name="Test Dataset",
            data_type="video",
        )

        # Create a proper mock connection with required attributes
        mock_connection = Mock(spec=LabellerrConnection)
        mock_connection.connection_id = "test-connection-id"

        mock_response = {
            "response": {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440001",
                "data_type": "video",
            }
        }

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
                return_value={
                    "dataset_id": "550e8400-e29b-41d4-a716-446655440001",
                    "data_type": "video",
                },
            ):
                dataset = create_dataset_from_connection(
                    client=client,
                    dataset_config=dataset_config,
                    connection=mock_connection,
                    path="gs://bucket/path",
                )

                assert dataset is not None

    def test_create_dataset_from_local_with_files_list(self, client):
        """Test creating dataset from local files list"""
        dataset_config = DatasetConfig(
            dataset_name="Local Files Dataset",
            data_type="image",
        )

        files_to_upload = ["/path/to/file1.jpg", "/path/to/file2.jpg"]

        with patch(
            "labellerr.core.datasets.upload_files", return_value="local-connection-id"
        ):
            with patch(
                "labellerr.core.datasets.create_dataset_from_connection"
            ) as mock_create:
                mock_dataset = Mock()
                mock_dataset.dataset_id = "test-dataset-id"
                mock_create.return_value = mock_dataset

                dataset = create_dataset_from_local(
                    client=client,
                    dataset_config=dataset_config,
                    files_to_upload=files_to_upload,
                )

                assert dataset is not None
                mock_create.assert_called_once()

    def test_create_dataset_from_local_with_folder(self, client):
        """Test creating dataset from local folder"""
        dataset_config = DatasetConfig(
            dataset_name="Local Folder Dataset",
            data_type="document",
        )

        folder_path = "/path/to/documents"

        with patch(
            "labellerr.core.datasets.upload_folder_files_to_dataset",
            return_value={"connection_id": "folder-connection-id", "status": "success"},
        ):
            with patch(
                "labellerr.core.datasets.create_dataset_from_connection"
            ) as mock_create:
                mock_dataset = Mock()
                mock_dataset.dataset_id = "test-dataset-id"
                mock_create.return_value = mock_dataset

                dataset = create_dataset_from_local(
                    client=client,
                    dataset_config=dataset_config,
                    folder_to_upload=folder_path,
                )

                assert dataset is not None

    def test_create_dataset_from_local_no_source(self, client):
        """Test error when no files or folder provided"""
        dataset_config = DatasetConfig(
            dataset_name="Invalid Dataset",
            data_type="image",
        )

        with pytest.raises(
            LabellerrError, match="No files or folder to upload provided"
        ):
            create_dataset_from_local(
                client=client,
                dataset_config=dataset_config,
            )

    def test_create_dataset_with_multimodal_indexing(self, client):
        """Test creating dataset with multimodal indexing enabled"""
        dataset_config = DatasetConfig(
            dataset_name="Multimodal Dataset",
            data_type="image",
            multimodal_indexing=True,
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            with patch(
                "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                create_dataset_from_connection(
                    client=client,
                    dataset_config=dataset_config,
                    connection="test-connection",
                    path="s3://bucket/path",
                )

                # Verify multimodal_indexing was passed in the request
                call_args = mock_request.call_args
                assert "data" in call_args.kwargs
                import json

                payload = json.loads(call_args.kwargs["data"])
                assert payload["es_multimodal_index"] is True


@pytest.mark.unit
class TestDatasetDeletion:
    """Test dataset deletion functionality"""

    def test_delete_dataset_success(self, client):
        """Test successful dataset deletion"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_response = {"response": {"status": "deleted", "dataset_id": dataset_id}}

        with patch.object(client, "make_request", return_value=mock_response):
            result = delete_dataset(client, dataset_id)

            assert result is not None
            assert result["response"]["status"] == "deleted"

    def test_delete_dataset_invalid_id(self, client):
        """Test deletion with invalid dataset ID"""
        invalid_id = "not-a-valid-uuid"

        # The deletion function doesn't validate UUID format before making request
        # So it will make the API call which should fail
        with patch.object(
            client, "make_request", side_effect=LabellerrError("Invalid dataset ID")
        ):
            with pytest.raises(LabellerrError):
                delete_dataset(client, invalid_id)

    def test_delete_nonexistent_dataset(self, client):
        """Test deletion of non-existent dataset"""
        dataset_id = "00000000-0000-0000-0000-000000000000"

        with patch.object(
            client, "make_request", side_effect=LabellerrError("Dataset not found")
        ):
            with pytest.raises(LabellerrError, match="Dataset not found"):
                delete_dataset(client, dataset_id)


@pytest.mark.unit
class TestDatasetListing:
    """Test dataset listing functionality"""

    def test_list_datasets_single_page(self, client):
        """Test listing datasets with single page"""
        mock_response = {
            "response": {
                "datasets": [
                    {"dataset_id": "id1", "name": "Dataset 1"},
                    {"dataset_id": "id2", "name": "Dataset 2"},
                ],
                "has_more": False,
            }
        }

        with patch.object(client, "make_request", return_value=mock_response):
            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=DataSetScope.client,
                    page_size=10,
                )
            )

            assert len(datasets) == 2
            assert datasets[0]["dataset_id"] == "id1"

    def test_list_datasets_auto_pagination(self, client):
        """Test listing datasets with auto-pagination (page_size=-1)"""
        # Mock multiple pages
        mock_responses = [
            {
                "response": {
                    "datasets": [{"dataset_id": f"id{i}"} for i in range(10)],
                    "has_more": True,
                    "last_dataset_id": "id9",
                }
            },
            {
                "response": {
                    "datasets": [{"dataset_id": f"id{i}"} for i in range(10, 15)],
                    "has_more": False,
                }
            },
        ]

        with patch.object(client, "make_request", side_effect=mock_responses):
            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=DataSetScope.client,
                    page_size=-1,  # Auto-pagination
                )
            )

            assert len(datasets) == 15
            assert datasets[0]["dataset_id"] == "id0"
            assert datasets[-1]["dataset_id"] == "id14"

    def test_list_datasets_empty_result(self, client):
        """Test listing datasets when no datasets exist"""
        mock_response = {
            "response": {
                "datasets": [],
                "has_more": False,
            }
        }

        with patch.object(client, "make_request", return_value=mock_response):
            datasets = list(
                list_datasets(
                    client=client,
                    datatype="video",
                    scope="user",  # Use string instead of enum
                    page_size=10,
                )
            )

            assert len(datasets) == 0

    def test_list_datasets_with_last_dataset_id(self, client):
        """Test manual pagination with last_dataset_id"""
        mock_response = {
            "response": {
                "datasets": [
                    {"dataset_id": "id11", "name": "Dataset 11"},
                    {"dataset_id": "id12", "name": "Dataset 12"},
                ],
                "has_more": True,
                "last_dataset_id": "id12",
            }
        }

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            datasets = list(
                list_datasets(
                    client=client,
                    datatype="document",
                    scope=DataSetScope.client,
                    page_size=10,
                    last_dataset_id="id10",
                )
            )

            assert len(datasets) == 2
            # Verify last_dataset_id was included in URL
            call_args = mock_request.call_args
            assert (
                "last_dataset_id=id10" in call_args[0][1]
            )  # URL is second positional arg


@pytest.mark.unit
class TestDatasetValidation:
    """Test dataset ID validation"""

    def test_empty_dataset_id(self, client):
        """Test that empty dataset_id is rejected"""
        with pytest.raises(
            InvalidDatasetIDError, match="Dataset ID cannot be None or empty"
        ):
            LabellerrDatasetMeta.get_dataset(client, "")

    def test_none_dataset_id(self, client):
        """Test that None dataset_id is rejected"""
        with pytest.raises((InvalidDatasetIDError, TypeError)):
            LabellerrDatasetMeta.get_dataset(client, None)

    def test_non_string_dataset_id(self, client):
        """Test that non-string dataset_id is rejected"""
        with pytest.raises((InvalidDatasetIDError, TypeError, AttributeError)):
            LabellerrDatasetMeta.get_dataset(client, 12345)


@pytest.mark.unit
class TestDatasetErrorHandling:
    """Test error handling in dataset operations"""

    def test_other_exceptions_propagate(self, client):
        """Test that exceptions from API are propagated"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        # Simulate an API error
        api_error = LabellerrError("API error occurred")

        with patch.object(client, "make_request", side_effect=api_error):
            with pytest.raises(LabellerrError, match="API error occurred"):
                LabellerrDatasetMeta.get_dataset(client, dataset_id)

    def test_custom_exceptions_not_converted(self, client):
        """Test that non-API exceptions are not converted"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        # Simulate a different kind of error
        custom_error = ValueError("Custom error")

        with patch.object(client, "make_request", side_effect=custom_error):
            with pytest.raises(ValueError, match="Custom error"):
                LabellerrDatasetMeta.get_dataset(client, dataset_id)


@pytest.mark.unit
class TestDatasetConfig:
    """Test DatasetConfig schema validation"""

    def test_valid_dataset_config(self):
        """Test creating valid dataset config"""
        config = DatasetConfig(
            dataset_name="Test Dataset",
            data_type="image",
        )

        assert config.dataset_name == "Test Dataset"
        assert config.data_type == "image"
        # dataset_description defaults to empty string, not None
        assert config.dataset_description == ""
        assert config.multimodal_indexing is False

    def test_dataset_config_with_all_fields(self):
        """Test dataset config with all fields"""
        config = DatasetConfig(
            dataset_name="Full Dataset",
            data_type="video",
            dataset_description="A test dataset",
            multimodal_indexing=True,
        )

        assert config.dataset_name == "Full Dataset"
        assert config.data_type == "video"
        assert config.dataset_description == "A test dataset"
        assert config.multimodal_indexing is True

    def test_dataset_config_with_different_data_types(self):
        """Test dataset config with various data types"""
        data_types = ["image", "video", "audio", "document", "text"]

        for data_type in data_types:
            config = DatasetConfig(
                dataset_name=f"{data_type.capitalize()} Dataset",
                data_type=data_type,
            )
            assert config.data_type == data_type


@pytest.mark.unit
class TestDatasetProperties:
    """Test dataset property access"""

    def test_dataset_properties_access(self, client):
        """Test accessing dataset properties"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_dataset_data = {
            "dataset_id": dataset_id,
            "name": "Test Dataset",
            "description": "Test Description",
            "data_type": "image",
            "files_count": 42,
            "status_code": 300,
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "test@example.com",
        }

        with patch(
            "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
            return_value=mock_dataset_data,
        ):
            dataset = LabellerrDataset(client, dataset_id)

            # Test all properties
            assert dataset.dataset_id == dataset_id
            assert dataset.name == "Test Dataset"
            assert dataset.description == "Test Description"
            assert dataset.data_type == "image"
            assert dataset.files_count == 42
            assert dataset.status_code == 300
            assert dataset.created_at == "2024-01-01T00:00:00Z"
            assert dataset.created_by == "test@example.com"

    def test_dataset_properties_defaults(self, client):
        """Test dataset property defaults when data is missing"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        # Minimal dataset data
        mock_dataset_data = {
            "dataset_id": dataset_id,
            "data_type": "image",
        }

        with patch(
            "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
            return_value=mock_dataset_data,
        ):
            dataset = LabellerrDataset(client, dataset_id)

            # Test defaults
            assert dataset.dataset_id == dataset_id
            assert dataset.data_type == "image"
            assert dataset.files_count == 0  # Default
            assert dataset.status_code == 501  # Default

    def test_dataset_status_property(self, client):
        """Test dataset status_code property returns default when missing"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_dataset_data = {
            "dataset_id": dataset_id,
            "data_type": "image",
            # status_code not provided
        }

        with patch(
            "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
            return_value=mock_dataset_data,
        ):
            dataset = LabellerrDataset(client, dataset_id)

            # Should return default 501 when not found
            assert dataset.status_code == 501

    def test_dataset_files_count_zero_default(self, client):
        """Test dataset files_count returns 0 when not provided"""
        dataset_id = "550e8400-e29b-41d4-a716-446655440000"

        mock_dataset_data = {
            "dataset_id": dataset_id,
            "data_type": "video",
            # files_count not provided
        }

        with patch(
            "labellerr.core.datasets.base.LabellerrDatasetMeta.get_dataset",
            return_value=mock_dataset_data,
        ):
            dataset = LabellerrDataset(client, dataset_id)

            # Should return 0 when not found
            assert dataset.files_count == 0
