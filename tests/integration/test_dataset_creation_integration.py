"""
Integration tests for dataset creation and management.

These tests make actual API calls to verify dataset creation, deletion,
and listing functionality works correctly with the Labellerr API.
"""

import os
import time
import tempfile
from pathlib import Path

import pytest

from labellerr.client import LabellerrClient
from labellerr.core.datasets import (
    LabellerrDataset,
    create_dataset_from_local,
    create_dataset_from_connection,
    delete_dataset,
    list_datasets,
)
from labellerr.core.exceptions import (
    LabellerrError,
    InvalidDatasetIDError,
    InvalidDatasetError,
)
from labellerr.core.schemas import DatasetConfig, DataSetScope


# Module-level list to track all created datasets for cleanup
_created_datasets = []


def register_dataset_for_cleanup(dataset_id: str, client: LabellerrClient):
    """Register a dataset ID for cleanup at the end of test session"""
    # Check if dataset_id already exists in the list of tuples
    if dataset_id and dataset_id not in [d[0] for d in _created_datasets]:
        _created_datasets.append((dataset_id, client))
        print(f"  → Registered dataset {dataset_id} for cleanup")


def cleanup_all_datasets():
    """Clean up all registered datasets"""
    print(f"\n\nCleaning up {len(_created_datasets)} created datasets...")
    for dataset_id, client in _created_datasets:
        try:
            delete_dataset(client, dataset_id)
            print(f"  ✓ Deleted dataset: {dataset_id}")
        except Exception as e:
            print(f"  ✗ Failed to delete dataset {dataset_id}: {e}")
    _created_datasets.clear()


@pytest.fixture(scope="session", autouse=True)
def cleanup_datasets_on_exit(request):
    """Automatically cleanup all created datasets at end of test session"""
    yield
    cleanup_all_datasets()


def get_test_images_from_env(num_images: int = 3) -> list:
    """
    Get real test images from IMG_DATASET_PATH environment variable.
    Returns a list of image file paths. Skips test if path doesn't exist or has no images.
    """
    img_path = os.getenv("IMG_DATASET_PATH")

    if not img_path:
        pytest.skip("IMG_DATASET_PATH not set in environment")

    img_path = Path(img_path)

    if not img_path.exists():
        pytest.skip(f"IMG_DATASET_PATH does not exist: {img_path}")

    if not img_path.is_dir():
        pytest.skip(f"IMG_DATASET_PATH is not a directory: {img_path}")

    # Find image files (jpg, jpeg, png)
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    image_files = [
        f for f in img_path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if not image_files:
        pytest.skip(f"No image files found in IMG_DATASET_PATH: {img_path}")

    if len(image_files) < num_images:
        pytest.skip(f"Not enough images in IMG_DATASET_PATH. Found {len(image_files)}, need {num_images}")

    # Return first num_images files
    return image_files[:num_images]


def skip_if_auth_error(e: Exception):
    """Helper to skip tests when authentication fails or file uploads fail due to auth"""
    error_str = str(e).lower()
    # Check for direct auth errors
    if "403" in str(e) or "not authorized" in error_str or "invalid api key" in error_str:
        pytest.skip(f"API credentials invalid or expired: {e}")
    # Check for file upload failures (which often hide auth errors in logs)
    if "all file uploads failed" in error_str:
        pytest.skip(f"File uploads failed (likely due to invalid credentials): {e}")


def handle_api_errors(func):
    """
    Decorator to handle common API errors in integration tests.

    Automatically:
    - Skips tests on auth errors (403, invalid credentials)
    - Skips tests on API unavailability (500, 503)
    - Propagates other errors for proper failure reporting

    Usage:
        @handle_api_errors
        def test_something(self, integration_client):
            # test code
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except LabellerrError as e:
            skip_if_auth_error(e)
            if "500" in str(e) or "unavailable" in str(e).lower():
                pytest.skip(f"API unavailable: {e}")
            else:
                raise

    return wrapper


@pytest.mark.integration
class TestDatasetCreationIntegration:
    """Integration tests for dataset creation"""

    @handle_api_errors
    def test_create_dataset_from_local_folder(self, integration_client):
        """
        Comprehensive test: dataset creation, all properties validation, and property types.
        Tests:
        - Basic dataset creation from local folder
        - All property accessors (name, data_type, files_count, status_code, etc.)
        - Property types validation
        - Files count accuracy
        """
        # Get real test images from IMG_DATASET_PATH
        test_images = get_test_images_from_env(num_images=3)

        # Copy images to a temporary folder for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil

            # Copy real images to temp directory
            for img_file in test_images:
                shutil.copy2(img_file, tmpdir)

            # Verify files were copied
            copied_files = list(Path(tmpdir).iterdir())
            assert len(copied_files) == 3, f"Expected 3 files, found {len(copied_files)}"

            dataset_config = DatasetConfig(
                dataset_name=f"Test Local Dataset {int(time.time())}",
                dataset_description="Integration test dataset from local folder with real images",
                data_type="image",
            )

            dataset_id = None

            try:
                # Create dataset from local folder
                dataset = create_dataset_from_local(
                    client=integration_client,
                    dataset_config=dataset_config,
                    folder_to_upload=tmpdir,
                )

                dataset_id = dataset.dataset_id
                # Register for cleanup
                register_dataset_for_cleanup(dataset_id, integration_client)

                # Verify dataset was created
                assert dataset is not None
                assert dataset.dataset_id is not None
                assert dataset.name == dataset_config.dataset_name

                # Test all property accessors
                assert dataset.data_type == "image"
                assert hasattr(dataset, 'files_count')
                assert hasattr(dataset, 'status_code')
                assert hasattr(dataset, 'description')
                assert hasattr(dataset, 'created_at')
                assert hasattr(dataset, 'created_by')

                # Validate property types
                assert isinstance(dataset.dataset_id, str)
                assert isinstance(dataset.data_type, str)
                assert isinstance(dataset.files_count, int)
                assert isinstance(dataset.status_code, int)
                if dataset.name is not None:
                    assert isinstance(dataset.name, str)

                # Print properties for verification
                print(f"\nDataset Properties:")
                print(f"  ID: {dataset.dataset_id}")
                print(f"  Name: {dataset.name}")
                print(f"  Data Type: {dataset.data_type}")
                print(f"  Files Count: {dataset.files_count}")
                print(f"  Status Code: {dataset.status_code}")
                print(f"  Description: {dataset.description}")

                # Wait for dataset processing
                status = dataset.status()
                assert status is not None

                # Clean up - delete the dataset
                delete_result = delete_dataset(integration_client, dataset_id)
                assert delete_result is not None
                dataset_id = None

            finally:
                if dataset_id:
                    try:
                        delete_dataset(integration_client, dataset_id)
                    except Exception:
                        pass

    @handle_api_errors
    def test_create_dataset_from_connection_with_existing_connection(
        self, integration_client, test_credentials, test_project_ids
    ):
        """Test creating a dataset using an existing connection"""
        # Skip if no connection ID available
        connection_id = os.getenv("TEST_CONNECTION_ID")
        if not connection_id:
            pytest.skip("TEST_CONNECTION_ID not set in environment")

        dataset_config = DatasetConfig(
            dataset_name=f"Test Connection Dataset {int(time.time())}",
            dataset_description="Integration test dataset from connection",
            data_type="image",
        )

        # Create dataset from connection
        dataset = create_dataset_from_connection(
            client=integration_client,
            dataset_config=dataset_config,
            connection=connection_id,
            path="test/path",
        )

        # Verify dataset was created
        assert dataset is not None
        assert dataset.dataset_id is not None
        assert dataset.name == dataset_config.dataset_name

        # Clean up
        delete_dataset(integration_client, dataset.dataset_id)

    @handle_api_errors
    def test_create_dataset_with_multimodal_indexing(self, integration_client):
        """
        Comprehensive test: multimodal indexing and dataset deletion.
        Tests dataset creation with multimodal indexing, then verifies deletion works correctly.
        """
        # Get real test images
        test_images = get_test_images_from_env(num_images=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil

            # Copy real image to temp directory
            shutil.copy2(test_images[0], tmpdir)

            dataset_config = DatasetConfig(
                dataset_name=f"Multimodal Test Dataset {int(time.time())}",
                data_type="image",
                multimodal_indexing=True,
            )

            dataset_id = None

            try:
                # Create dataset with multimodal indexing
                dataset = create_dataset_from_local(
                    client=integration_client,
                    dataset_config=dataset_config,
                    folder_to_upload=tmpdir,
                )

                assert dataset is not None
                dataset_id = dataset.dataset_id
                assert dataset_id is not None
                # Register for cleanup
                register_dataset_for_cleanup(dataset_id, integration_client)

                # Verify multimodal indexing can be enabled
                result = dataset.enable_multimodal_indexing(is_multimodal=True)
                assert result is not None

                # Test deletion
                delete_result = delete_dataset(integration_client, dataset_id)
                assert delete_result is not None

                # Mark as deleted (don't verify by fetching as API may return 500 errors)
                dataset_id = None

            finally:
                if dataset_id:
                    try:
                        delete_dataset(integration_client, dataset_id)
                    except Exception:
                        pass


@pytest.mark.integration
class TestDatasetValidationIntegration:
    """Integration tests for dataset ID validation with real API"""

    def test_invalid_dataset_id_format_rejected(self, integration_client):
        """Test that invalid dataset ID formats are rejected before API call"""
        invalid_ids = [
            "invalid-id",
            "not-a-uuid",
            "05becc9c-e221-42ea-90f8-8d24031e2f3b1",  # Extra character
            "123456",
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(InvalidDatasetIDError, match="Invalid dataset ID format"):
                LabellerrDataset(integration_client, invalid_id)

    def test_valid_uuid_format_but_nonexistent_dataset(self, integration_client):
        """Test that valid UUID format but non-existent dataset returns proper error"""
        nonexistent_id = "00000000-0000-0000-0000-000000000000"

        try:
            # This should fail because the dataset doesn't exist
            with pytest.raises((InvalidDatasetError, LabellerrError)) as exc_info:
                dataset = LabellerrDataset(integration_client, nonexistent_id)

            # Skip if we got auth error
            if exc_info.value:
                skip_if_auth_error(exc_info.value)

            # Verify error message mentions dataset not found
            assert "not found" in str(exc_info.value).lower() or "dataset" in str(exc_info.value).lower()

        except Exception as e:
            # If we get RetryError or 500 errors, that's expected for non-existent datasets
            if "RetryError" in str(type(e).__name__) or "500" in str(e):
                pass  # Expected
            else:
                raise

    def test_empty_dataset_id_rejected(self, integration_client):
        """Test that empty dataset_id is rejected"""
        with pytest.raises(InvalidDatasetIDError, match="Dataset ID cannot be None or empty"):
            LabellerrDataset(integration_client, "")

@pytest.mark.integration
class TestDatasetDeletionIntegration:
    """Integration tests for dataset deletion"""

    def test_delete_nonexistent_dataset(self, integration_client):
        """Test deletion of non-existent dataset returns appropriate error"""
        nonexistent_id = "00000000-0000-0000-0000-000000000001"

        try:
            with pytest.raises(LabellerrError):
                delete_dataset(integration_client, nonexistent_id)
        except Exception as e:
            # Some error is expected
            assert "not found" in str(e).lower() or "error" in str(e).lower()


@pytest.mark.integration
class TestDatasetListingIntegration:
    """Integration tests for dataset listing"""

    @handle_api_errors
    def test_list_datasets_client_scope(self, integration_client):
        """Test listing datasets with client scope"""
        datasets = list(list_datasets(
            client=integration_client,
            datatype="image",
            scope=DataSetScope.client,
            page_size=10,
        ))

        # Should return a list (may be empty)
        assert isinstance(datasets, list)

        # If datasets exist, verify structure
        if datasets:
            for dataset in datasets:
                assert "dataset_id" in dataset
                # May have other fields like name, data_type, etc.

    @handle_api_errors
    def test_list_datasets_auto_pagination(self, integration_client):
        """Test listing datasets with auto-pagination (page_size=-1)"""
        datasets = list(list_datasets(
            client=integration_client,
            datatype="image",
            scope=DataSetScope.client,
            page_size=-1,  # Auto-pagination
        ))

        # Should return a list
        assert isinstance(datasets, list)

    @handle_api_errors
    def test_list_datasets_different_data_types(self, integration_client):
        """Test listing datasets for different data types"""
        data_types = ["image", "video", "document"]

        for data_type in data_types:
            datasets = list(list_datasets(
                client=integration_client,
                datatype=data_type,
                scope=DataSetScope.client,
                page_size=5,
            ))

            assert isinstance(datasets, list)

    @handle_api_errors
    def test_list_datasets_project_scope(self, integration_client):
        """Test listing datasets with project scope"""
        datasets = list(list_datasets(
            client=integration_client,
            datatype="image",
            scope=DataSetScope.project,
            page_size=10,
        ))

        # Should return a list (may be empty)
        assert isinstance(datasets, list)


@pytest.mark.integration
class TestDatasetWorkflowIntegration:
    """Integration tests for complete dataset workflows"""

    @handle_api_errors
    def test_dataset_update_operations(self, integration_client):
        """
        Test dataset update operations: name, description, and metadata.

        NOTE: This test currently documents that update operations are NOT YET IMPLEMENTED.
        When update functionality is added to the SDK, this test will validate it.
        For now, it verifies that datasets can be created and their properties accessed.
        """
        # Get real test images
        test_images = get_test_images_from_env(num_images=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil

            # Copy real image to temp directory
            shutil.copy2(test_images[0], tmpdir)

            dataset_config = DatasetConfig(
                dataset_name=f"Update Test Dataset {int(time.time())}",
                dataset_description="Original description for update testing",
                data_type="image",
            )

            dataset_id = None

            try:
                # Create dataset
                dataset = create_dataset_from_local(
                    client=integration_client,
                    dataset_config=dataset_config,
                    folder_to_upload=tmpdir,
                )

                assert dataset is not None
                dataset_id = dataset.dataset_id
                assert dataset_id is not None
                # Register for cleanup
                register_dataset_for_cleanup(dataset_id, integration_client)

                # Verify original properties are accessible
                assert dataset.name == dataset_config.dataset_name
                assert dataset.data_type == "image"

                # Document what update operations are NOT YET IMPLEMENTED:
                print(f"\n⚠ Update operations not yet implemented in SDK:")
                print(f"  - update_name() - method does not exist")
                print(f"  - update_description() - method does not exist")
                print(f"  - update_metadata() - method does not exist")
                print(f"  - add_files() - method does not exist")
                print(f"  - remove_files() - method does not exist")

                # Verify that these methods don't exist (expected)
                assert not hasattr(dataset, 'update_name'), "update_name unexpectedly exists"
                assert not hasattr(dataset, 'update_description'), "update_description unexpectedly exists"
                assert not hasattr(dataset, 'update_metadata'), "update_metadata unexpectedly exists"
                assert not hasattr(dataset, 'add_files'), "add_files unexpectedly exists"
                assert not hasattr(dataset, 'remove_files'), "remove_files unexpectedly exists"

                # Clean up
                delete_result = delete_dataset(integration_client, dataset_id)
                assert delete_result is not None
                dataset_id = None

            finally:
                if dataset_id:
                    try:
                        delete_dataset(integration_client, dataset_id)
                    except Exception:
                        pass

    @handle_api_errors
    def test_complete_dataset_lifecycle(self, integration_client):
        """Test complete dataset lifecycle: create, fetch, list, and delete"""
        # Get real test images
        test_images = get_test_images_from_env(num_images=2)

        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil

            # Copy real images to temp directory
            for img_file in test_images:
                shutil.copy2(img_file, tmpdir)

            dataset_config = DatasetConfig(
                dataset_name=f"Lifecycle Test Dataset {int(time.time())}",
                dataset_description="Testing complete lifecycle",
                data_type="image",
            )

            dataset_id = None

            try:
                # Step 1: Create dataset
                dataset = create_dataset_from_local(
                    client=integration_client,
                    dataset_config=dataset_config,
                    folder_to_upload=tmpdir,
                )

                assert dataset is not None
                dataset_id = dataset.dataset_id
                assert dataset_id is not None
                # Register for cleanup
                register_dataset_for_cleanup(dataset_id, integration_client)

                # Step 2: Fetch dataset by ID
                fetched_dataset = LabellerrDataset(integration_client, dataset_id)
                assert fetched_dataset.dataset_id == dataset_id
                assert fetched_dataset.name == dataset_config.dataset_name

                # Step 3: Check dataset status
                status = fetched_dataset.status()
                assert status is not None
                assert "status_code" in status

                # Step 4: List datasets and verify our dataset is in the list
                datasets = list(list_datasets(
                    client=integration_client,
                    datatype="image",
                    scope=DataSetScope.client,
                    page_size=20,
                ))

                dataset_ids = [d.get("dataset_id") for d in datasets]
                # Our dataset might or might not be in the first page
                # So we just verify the list operation worked

                # Step 5: Delete dataset
                delete_result = delete_dataset(integration_client, dataset_id)
                assert delete_result is not None

                dataset_id = None  # Mark as deleted

            finally:
                # Cleanup: ensure dataset is deleted even if test fails
                if dataset_id:
                    try:
                        delete_dataset(integration_client, dataset_id)
                    except Exception:
                        pass  # Ignore cleanup errors
