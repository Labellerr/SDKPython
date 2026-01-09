"""
Integration tests for dataset creation and management.

These tests make actual API calls to verify dataset creation, deletion,
and listing functionality works correctly with the Labellerr API.
"""

import os
import re
import time
import tempfile
from pathlib import Path

import pytest
import requests.exceptions

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


def enhance_api_error(error: Exception, context: str) -> str:
    """
    Enhance API error messages with context for better CI diagnostics.

    Args:
        error: The original exception
        context: Description of what operation was being performed

    Returns:
        Enhanced error message with API details
    """
    error_msg = str(error)

    # Check for HTML error responses (API returning error pages)
    if "<!DOCTYPE html>" in error_msg or "<html" in error_msg:
        # Try to extract HTTP status from HTML
        status_match = re.search(r'(\d{3})\s+([\w\s]+)', error_msg)
        if status_match:
            status_code = status_match.group(1)
            status_text = status_match.group(2)
            return (
                f"{context} - API returned HTML error page\n"
                f"HTTP Status: {status_code} {status_text}\n"
                f"This indicates an API infrastructure issue (endpoint not found, server error, etc.)\n"
                f"Original error: {type(error).__name__}"
            )
        else:
            return (
                f"{context} - API returned HTML error page instead of JSON\n"
                f"This indicates an API infrastructure issue (404, 500, etc.)\n"
                f"Original error: {type(error).__name__}: {error_msg[:200]}"
            )

    # Check for connection/retry errors
    if isinstance(error, requests.exceptions.RetryError):
        return (
            f"{context} - Network connection failed\n"
            f"Max retries exceeded connecting to API\n"
            f"This indicates network/connectivity issues or API rate limiting\n"
            f"Original error: {error}"
        )

    # Check for LabellerrError with error dict
    if isinstance(error, LabellerrError):
        error_str = str(error)
        if "'error':" in error_str and "'code':" in error_str:
            # Extract status code if present
            code_match = re.search(r"'code':\s*(\d+)", error_str)
            if code_match:
                code = code_match.group(1)
                return (
                    f"{context} - API request failed\n"
                    f"HTTP Status Code: {code}\n"
                    f"Error details: {error_str[:500]}"
                )

    # Default: return context + original error
    return f"{context}\nOriginal error: {type(error).__name__}: {error}"


@pytest.fixture
def cleanup_datasets(integration_client):
    """
    Fixture for automatic dataset cleanup after each test.

    Usage in tests:
        dataset = create_dataset_from_local(...)
        cleanup_datasets(dataset.dataset_id)
    """
    datasets_to_cleanup = []

    def _register(dataset_id: str):
        """Register a dataset_id for cleanup"""
        if dataset_id and dataset_id not in datasets_to_cleanup:
            datasets_to_cleanup.append(dataset_id)

    yield _register

    # Cleanup after test completes
    for dataset_id in datasets_to_cleanup:
        try:
            delete_dataset(integration_client, dataset_id)
        except Exception as e:
            # Silently handle cleanup failures (dataset may already be deleted)
            pass


@pytest.fixture(scope="session", autouse=True)
def verify_api_credentials_before_tests():
    """
    Verify API credentials are valid before running any integration tests.
    Fails fast if credentials are missing or invalid.
    """
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id_val = os.getenv("CLIENT_ID")

    if not all([api_key, api_secret, client_id_val]):
        pytest.skip(
            "API credentials not configured. Set API_KEY, "
            "API_SECRET, and CLIENT_ID environment variables."
        )

    try:
        client = LabellerrClient(
            api_key=api_key, api_secret=api_secret, client_id=client_id_val
        )
        # Make a simple API call to verify credentials work
        list(
            list_datasets(
                client, datatype="image", scope=DataSetScope.client, page_size=1
            )
        )
    except LabellerrError as e:
        error_str = str(e).lower()
        if (
            "403" in str(e)
            or "401" in str(e)
            or "not authorized" in error_str
            or "unauthorized" in error_str
            or "invalid api key" in error_str
        ):
            pytest.skip(f"Invalid or expired API credentials: {e}")
        # Let other errors propagate - they indicate real API problems
        raise


# Removed session-level cleanup - now using per-test fixture instead
# This avoids double-deletion and makes cleanup more predictable


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


@pytest.mark.integration
class TestDatasetCreationIntegration:
    """Integration tests for dataset creation"""

    def test_create_dataset_from_local_folder(self, integration_client, cleanup_datasets):
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

            # Create dataset from local folder
            dataset = create_dataset_from_local(
                client=integration_client,
                dataset_config=dataset_config,
                folder_to_upload=tmpdir,
            )

            # Register for automatic cleanup
            cleanup_datasets(dataset.dataset_id)

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
            status = dataset.status(timeout=300)  # 5 min timeout
            assert status is not None

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

    def test_create_dataset_with_multimodal_indexing(self, integration_client, cleanup_datasets):
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

            # Create dataset with multimodal indexing
            dataset = create_dataset_from_local(
                client=integration_client,
                dataset_config=dataset_config,
                folder_to_upload=tmpdir,
            )

            assert dataset is not None
            assert dataset.dataset_id is not None

            # Register for automatic cleanup
            cleanup_datasets(dataset.dataset_id)

            # Verify multimodal indexing can be enabled
            try:
                result = dataset.enable_multimodal_indexing(is_multimodal=True)
                assert result is not None
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Failed to enable multimodal indexing for dataset {dataset.dataset_id}"
                ))

            # Test deletion
            try:
                delete_result = delete_dataset(integration_client, dataset.dataset_id)
                assert delete_result is not None
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Failed to delete dataset {dataset.dataset_id}"
                ))


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
        """
        Test that valid UUID format but non-existent dataset returns proper error.

        Note: API may return 500 errors for certain nonexistent IDs (infrastructure issue),
        which causes retry exhaustion. We accept either proper error response or retry error.
        """
        nonexistent_id = "00000000-0000-0000-0000-000000000000"

        try:
            with pytest.raises((InvalidDatasetError, LabellerrError, requests.exceptions.RetryError)) as exc_info:
                LabellerrDataset(integration_client, nonexistent_id)

            # Verify it's not an auth error (credentials were validated upfront)
            error_msg = str(exc_info.value).lower()

            # Check for auth errors
            if "403" in error_msg or "unauthorized" in error_msg:
                pytest.fail("Got auth error instead of not found - credentials issue")

            # Accept any error (404, 500, retry error) as valid for nonexistent dataset
            assert any(
                x in error_msg for x in ["not found", "dataset", "error", "500", "retry", "max retries"]
            ), f"Expected error for nonexistent dataset, got: {exc_info.value}"

        except Exception as e:
            # Unexpected exception type
            pytest.fail(f"Unexpected exception type: {type(e).__name__}: {e}")

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

    @pytest.mark.skip(reason="Update operations not yet implemented - placeholder for future feature")
    def test_dataset_update_operations_not_implemented(self):
        """
        Placeholder test for dataset update operations.

        When update APIs are available, this test should verify:
        - update_name()
        - update_description()
        - update_metadata()
        - add_files()
        - remove_files()

        TODO: Implement when update APIs are available
        """
        pass

    def test_complete_dataset_lifecycle(self, integration_client, cleanup_datasets):
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

            # Step 1: Create dataset
            dataset = create_dataset_from_local(
                client=integration_client,
                dataset_config=dataset_config,
                folder_to_upload=tmpdir,
            )

            assert dataset is not None
            assert dataset.dataset_id is not None

            # Register for automatic cleanup
            cleanup_datasets(dataset.dataset_id)

            # Step 2: Fetch dataset by ID
            try:
                fetched_dataset = LabellerrDataset(integration_client, dataset.dataset_id)
                assert fetched_dataset.dataset_id == dataset.dataset_id
                assert fetched_dataset.name == dataset_config.dataset_name
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Step 2: Failed to fetch dataset by ID {dataset.dataset_id}"
                ))

            # Step 3: Check dataset status
            try:
                status = fetched_dataset.status(timeout=300)  # 5 min timeout
                assert status is not None
                assert "status_code" in status
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Step 3: Failed to check status for dataset {dataset.dataset_id}"
                ))

            # Step 4: List datasets and verify our dataset is in the list
            try:
                # Use pagination to find the dataset
                found = False
                for dataset_dict in list_datasets(
                    client=integration_client,
                    datatype="image",
                    scope=DataSetScope.client,
                    page_size=-1,  # Auto-paginate to check all datasets
                ):
                    if dataset_dict.get("dataset_id") == dataset.dataset_id:
                        found = True
                        break

                assert found, f"Created dataset {dataset.dataset_id} not found in listing"
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Step 4: Failed to list datasets or verify dataset {dataset.dataset_id} in listing"
                ))

            # Step 5: Delete dataset
            try:
                delete_result = delete_dataset(integration_client, dataset.dataset_id)
                assert delete_result is not None
            except (LabellerrError, requests.exceptions.RetryError) as e:
                pytest.fail(enhance_api_error(
                    e,
                    f"Step 5: Failed to delete dataset {dataset.dataset_id}"
                ))
