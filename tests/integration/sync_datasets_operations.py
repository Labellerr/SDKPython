"""

This module contains integration tests that make actual API calls to test
sync_datasets operations in real-world scenarios.

Usage:
    python sync_datasets_operations.py
"""

import os
import sys

# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

import time

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


def test_sync_datasets(
    api_key,
    api_secret,
    client_id,
    project_id,
    dataset_id,
    path,
    data_type,
    email_id,
    connection_id,
):
    """
    Test syncing datasets.

    Business scenario: Synchronize dataset files with the backend to ensure
    the project has the latest data available for annotation.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID
        dataset_id: Dataset ID to sync
        path: Path to the data
        data_type: Type of data (image, video, audio, document, text)
        email_id: Email ID of the user
        connection_id: Connection ID
    """

    print("\n" + "=" * 60)
    print("TEST: Sync Datasets")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        print(f"\n1. Syncing dataset: {dataset_id}")
        print(f"Project ID: {project_id}")
        print(f"Data Type: {data_type}")
        print(f"Path: {path}")
        print(f"Connection ID: {connection_id}")

        result = client.datasets.sync_datasets(
            client_id=client_id,
            project_id=project_id,
            dataset_id=dataset_id,
            path=path,
            data_type=data_type,
            email_id=email_id,
            connection_id=connection_id,
        )

        print("Dataset sync successful")
        print(f"Response: {result}")

        return result

    except LabellerrError as e:
        print(f"Error: {str(e)}")
        return None
    finally:
        client.close()


def test_sync_datasets_with_different_data_types(
    api_key,
    api_secret,
    client_id,
    project_id,
    dataset_id,
    path,
    email_id,
    connection_id,
):
    """
    Test syncing datasets with different data types.

    Business scenario: Test syncing various data types (image, video, audio, etc.)
    to ensure the API handles different file types correctly.
    """

    print("\n" + "=" * 60)
    print("TEST: Sync Datasets with Different Data Types")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)
    results = {}

    data_types = ["image", "video", "audio", "document", "text"]

    for data_type in data_types:
        try:
            print(f"\n{data_type.upper()} - Syncing dataset...")
            result = client.datasets.sync_datasets(
                client_id=client_id,
                project_id=project_id,
                dataset_id=dataset_id,
                path=path,
                data_type=data_type,
                email_id=email_id,
                connection_id=connection_id,
            )

            print(f"{data_type.upper()} sync successful")
            results[data_type] = {"success": True, "result": result}

            # Add delay between requests
            time.sleep(1)

        except LabellerrError as e:
            print(f"{data_type.upper()} sync failed: {str(e)}")
            results[data_type] = {"success": False, "error": str(e)}

    client.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results.values() if r["success"])
    print(f"Successful syncs: {successful}/{len(data_types)}")

    return results


def test_sync_datasets_validation(api_key, api_secret):
    """
    Test parameter validation for sync datasets.

    Business scenario: Ensure the SDK properly validates input parameters
    before making API calls to prevent invalid requests.
    """
    print("\n" + "=" * 60)
    print("TEST: Sync Datasets Parameter Validation")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    # Test 1: Invalid data_type
    print("\n1. Testing invalid data_type...")
    try:
        client.datasets.sync_datasets(
            client_id="test_client",
            project_id="test_project",
            dataset_id="test_dataset",
            path="/test/path",
            data_type="invalid_type",  # Invalid
            email_id="test@example.com",
            connection_id="test_connection",
        )
        print("   Should have raised validation error")
    except Exception as e:
        print(f"Validation error caught: {str(e)[:80]}...")

    # Test 2: Empty required field
    print("\n2. Testing empty required fields...")
    try:
        client.datasets.sync_datasets(
            client_id="",  # Empty
            project_id="test_project",
            dataset_id="test_dataset",
            path="/test/path",
            data_type="image",
            email_id="test@example.com",
            connection_id="test_connection",
        )
        print("   Should have raised validation error")
    except Exception as e:
        print(f"Validation error caught: {str(e)[:80]}...")

    # Test 3: Missing email format
    print("\n3. Testing valid parameters...")
    try:
        # This will fail at API level but should pass validation
        client.datasets.sync_datasets(
            client_id="test_client",
            project_id="test_project",
            dataset_id="test_dataset",
            path="/test/path",
            data_type="image",
            email_id="valid@example.com",
            connection_id="test_connection",
        )
        print("   Validation passed (API call may fail)")
    except LabellerrError as e:
        print(f"API error (validation passed): {str(e)[:80]}...")
    except Exception as e:
        print(f"Validation passed, error at API level: {str(e)[:80]}...")

    client.close()
    print("\n   Validation tests completed")


def run_all_tests(
    api_key,
    api_secret,
    client_id,
    project_id,
    dataset_id,
    path,
    data_type,
    email_id,
    connection_id,
):
    """
    Run all integration tests for sync datasets operations.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID
        dataset_id: Dataset ID to sync
        path: Path to the data
        data_type: Type of data (image, video, audio, document, text)
        email_id: Email ID of the user
        connection_id: Connection ID
    """
    print("\n" + "=" * 80)
    print(" SYNC DATASETS OPERATIONS - INTEGRATION TESTS")
    print("=" * 80)
    print(f"\nClient ID: {client_id}")
    print(f"Project ID: {project_id}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Data Type: {data_type}")
    print("\n" + "=" * 80)

    # Test 1: Basic sync
    print("\n\n Running Test Suite: BASIC SYNC")
    test_sync_datasets(
        api_key,
        api_secret,
        client_id,
        project_id,
        dataset_id,
        path,
        data_type,
        email_id,
        connection_id,
    )

    # Test 2: Validation tests
    print("\n\n Running Test Suite: PARAMETER VALIDATION")
    test_sync_datasets_validation(api_key, api_secret)

    print("\n" + "=" * 80)
    print(" INTEGRATION TESTS COMPLETED")
    print("=" * 80)
    print("\n")


if __name__ == "__main__":
    # Import credentials
    try:
        import cred

        API_KEY = cred.API_KEY
        API_SECRET = cred.API_SECRET
        CLIENT_ID = cred.CLIENT_ID
        PROJECT_ID = cred.PROJECT_ID

        # Additional parameters for sync_datasets
        DATASET_ID = getattr(cred, "DATASET_ID", "")
        PATH = getattr(cred, "PATH", "/data")
        DATA_TYPE = getattr(cred, "DATA_TYPE", "image")
        EMAIL_ID = getattr(cred, "EMAIL_ID", "")
        CONNECTION_ID = getattr(cred, "CONNECTION_ID", "")

    except (ImportError, AttributeError):
        # Fall back to environment variables
        API_KEY = os.environ.get("LABELLERR_API_KEY", "")
        API_SECRET = os.environ.get("LABELLERR_API_SECRET", "")
        CLIENT_ID = os.environ.get("LABELLERR_CLIENT_ID", "")
        PROJECT_ID = os.environ.get("LABELLERR_PROJECT_ID", "")
        DATASET_ID = os.environ.get("LABELLERR_DATASET_ID", "")
        PATH = os.environ.get("LABELLERR_PATH", "/data")
        DATA_TYPE = os.environ.get("LABELLERR_DATA_TYPE", "image")
        EMAIL_ID = os.environ.get("LABELLERR_EMAIL_ID", "")
        CONNECTION_ID = os.environ.get("LABELLERR_CONNECTION_ID", "")

    # Check if credentials are available
    if not all([API_KEY, API_SECRET, CLIENT_ID, PROJECT_ID]):
        print("\n" + "=" * 80)
        print(" ERROR: Missing Credentials")
        print("=" * 80)
        print("\nPlease provide credentials either by:")
        print("1. Setting them in tests/integration/cred.py:")
        print("   API_KEY = 'your_api_key'")
        print("   API_SECRET = 'your_api_secret'")
        print("   CLIENT_ID = 'your_client_id'")
        print("   PROJECT_ID = 'your_project_id'")
        print("   DATASET_ID = 'your_dataset_id'")
        print("   EMAIL_ID = 'user@example.com'")
        print("   CONNECTION_ID = 'your_connection_id'")
        print("   PATH = '/path/to/data'")
        print("   DATA_TYPE = 'image'")
        print("\n2. Or setting environment variables:")
        print("   export LABELLERR_API_KEY='your_api_key'")
        print("   export LABELLERR_API_SECRET='your_api_secret'")
        print("   export LABELLERR_CLIENT_ID='your_client_id'")
        print("   export LABELLERR_PROJECT_ID='your_project_id'")
        print("   export LABELLERR_DATASET_ID='your_dataset_id'")
        print("   export LABELLERR_EMAIL_ID='user@example.com'")
        print("   export LABELLERR_CONNECTION_ID='your_connection_id'")
        print("\n" + "=" * 80)
        sys.exit(1)

    # Check if additional sync_datasets parameters are available
    if not all([DATASET_ID, EMAIL_ID, CONNECTION_ID]):
        print("\n" + "=" * 80)
        print(" WARNING: Missing Sync Datasets Parameters")
        print("=" * 80)
        print("\nRunning validation tests only.")
        print("To run full sync tests, provide:")
        print("   DATASET_ID, EMAIL_ID, CONNECTION_ID")
        print("\n" + "=" * 80)

        # Run only validation tests
        print("\n\n Running Test Suite: PARAMETER VALIDATION")
        test_sync_datasets_validation(API_KEY, API_SECRET)
        sys.exit(0)

    # Run all tests
    run_all_tests(
        API_KEY,
        API_SECRET,
        CLIENT_ID,
        PROJECT_ID,
        DATASET_ID,
        PATH,
        DATA_TYPE,
        EMAIL_ID,
        CONNECTION_ID,
    )
