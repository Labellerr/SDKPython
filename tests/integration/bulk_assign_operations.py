"""
Real integration tests for bulk assign and list file operations.

This module contains integration tests that make actual API calls to test
bulk_assign_files and list_file operations in real-world scenarios.

Usage:
    python Bulk_Assign_Operations.py
"""

import os
import sys

from labellerr import LabellerrError

# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

import time

from labellerr.client import LabellerrClient


def test_list_files_by_status(api_key, api_secret, client_id, project_id):
    """
    Test listing files by status.

    Business scenario: Project manager wants to see all files in a specific status
    to track progress and plan resource allocation.
    """
    print("\n" + "=" * 60)
    print("TEST: List Files by Status")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        # List all files without specific status filter
        print("\n1. Listing files (first page)...")
        result = client.projects.list_file(
            client_id=client_id, project_id=project_id, search_queries={}, size=10
        )

        print("Successfully retrieved files")
        if "files" in result:
            print("Found {len(result.get('files', []))} files")
        else:
            print("Response: {result}")

        return result

    except LabellerrError as e:
        print(f"Error: {str(e)}")
        return None


def test_list_files_with_pagination(api_key, api_secret, client_id, project_id):
    """
    Test listing files with pagination.

    Business scenario: Large projects need to paginate through files
    for performance and to process files in batches.
    """
    print("\n" + "=" * 60)
    print("TEST: List Files with Pagination")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        # Get first page
        print("\n1. Fetching first page (5 items)...")
        result_page1 = client.projects.list_file(
            client_id=client_id, project_id=project_id, search_queries={}, size=5
        )

        print("Page 1 retrieved successfully")
        if "files" in result_page1:
            print("Page 1 contains {len(result_page1.get('files', []))} files")

        # Check if there's a next page cursor
        next_cursor = result_page1.get("next_search_after")
        if next_cursor:
            print("\n2. Next page cursor found, fetching second page...")
            result_page2 = client.projects.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries={},
                size=5,
                next_search_after=next_cursor,
            )
            print("Page 2 retrieved successfully")
            if "files" in result_page2:
                print("Page 2 contains {len(result_page2.get('files', []))} files")
        else:
            print("   ℹ No more pages available")

        return result_page1

    except LabellerrError as e:
        print(f"Error: {str(e)}")
        return None


def test_bulk_assign_files(
    api_key, api_secret, client_id, project_id, file_ids, new_status
):
    """
    Test bulk assigning files to a new status.

    Business scenario: Project manager needs to move multiple files to a new stage
    in the annotation pipeline efficiently.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID
        file_ids: List of file IDs to assign
        new_status: New status to assign to files
    """
    print("\n" + "=" * 60)
    print("TEST: Bulk Assign Files")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        print(f"\n1. Bulk assigning {len(file_ids)} files to status: {new_status}")
        print("File IDs: {file_ids[:3]}{'...' if len(file_ids) > 3 else ''}")

        result = client.projects.bulk_assign_files(
            client_id=client_id,
            project_id=project_id,
            file_ids=file_ids,
            new_status=new_status,
        )

        print("Bulk assign successful")
        print("Response: {result}")

        return result

    except LabellerrError as e:
        print(f"Error: {str(e)}")
        return None


def test_list_then_bulk_assign_workflow(
    api_key, api_secret, client_id, project_id, target_status, new_status
):
    """
    Test complete workflow: List files with specific status, then bulk assign them to new status.

    Business scenario: Project manager identifies files in one stage and moves them
    to the next stage in the annotation pipeline.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID
        target_status: Status to search for
        new_status: New status to assign files to
    """
    print("\n" + "=" * 60)
    print("TEST: List Then Bulk Assign Workflow")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        # Step 1: List files with target status
        print(f"\n1. Listing files with status: {target_status}")
        list_result = client.projects.list_file(
            client_id=client_id,
            project_id=project_id,
            search_queries={"status": target_status},
            size=5,  # Limit to 5 for testing
        )

        print("Files listed successfully")

        # Extract file IDs from result
        files = list_result.get("files", [])
        if not files:
            print("ℹ No files found with status: {target_status}")
            return None

        file_ids = [f["id"] for f in files if "id" in f]
        if not file_ids:
            print("ℹ No file IDs found in response")
            return None

        print("Found {len(file_ids)} files to process")

        # Step 2: Bulk assign to new status
        print(f"\n2. Bulk assigning {len(file_ids)} files to status: {new_status}")
        assign_result = client.projects.bulk_assign_files(
            client_id=client_id,
            project_id=project_id,
            file_ids=file_ids,
            new_status=new_status,
        )

        print("Bulk assign successful")
        print("Workflow completed successfully!")

        # Step 3: Verify the change (optional)
        print(f"\n3. Verifying files now have status: {new_status}")
        time.sleep(1)  # Brief pause to allow status update
        verify_result = client.projects.list_file(
            client_id=client_id,
            project_id=project_id,
            search_queries={"status": new_status},
            size=len(file_ids) + 5,
        )

        print("Verification query successful")

        return {
            "list_result": list_result,
            "assign_result": assign_result,
            "verify_result": verify_result,
        }

    except LabellerrError as e:
        print(f" Error: {str(e)}")
        return None


def test_bulk_assign_single_file(
    api_key, api_secret, client_id, project_id, file_id, new_status
):
    """
    Test bulk assigning a single file.

    Business scenario: Sometimes need to change status of just one file using bulk API.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID
        file_id: Single file ID to assign
        new_status: New status to assign
    """
    print("\n" + "=" * 60)
    print("TEST: Bulk Assign Single File")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        print(f"\n1. Bulk assigning single file: {file_id}")
        print("New status: {new_status}")

        result = client.projects.bulk_assign_files(
            client_id=client_id,
            project_id=project_id,
            file_ids=[file_id],
            new_status=new_status,
        )

        print("Single file bulk assign successful")
        print("Response: {result}")

        return result

    except LabellerrError as e:
        print(f"Error: {str(e)}")
        return None


def test_search_with_filters(api_key, api_secret, client_id, project_id):
    """
    Test searching files with complex filter criteria.

    Business scenario: Quality manager needs to find files matching specific criteria
    for audit or review purposes.
    """
    print("\n" + "=" * 60)
    print("TEST: Search Files with Filters")
    print("=" * 60)

    client = LabellerrClient(api_key, api_secret)

    try:
        # Test 1: Simple status filter
        print("\n1. Searching with simple filters...")
        result1 = client.projects.list_file(
            client_id=client_id,
            project_id=project_id,
            search_queries={"status": "pending"},
            size=10,
        )
        print("Simple filter search successful")

        # Test 2: Multiple filters (if supported)
        print("\n2. Searching with multiple filters...")
        result2 = client.projects.list_file(
            client_id=client_id,
            project_id=project_id,
            search_queries={
                "status": "completed",
                # Add more filters based on your API's capabilities
            },
            size=10,
        )
        print("Multiple filter search successful")

        return {"simple_filter": result1, "multiple_filters": result2}

    except LabellerrError as e:
        print(f" Error: {str(e)}")
        return None


def run_all_tests(api_key, api_secret, client_id, project_id):
    """
    Run all integration tests for bulk assign operations.

    Args:
        api_key: API key for authentication
        api_secret: API secret for authentication
        client_id: Client ID
        project_id: Project ID containing files to test with
    """
    print("\n" + "=" * 80)
    print(" BULK ASSIGN AND LIST FILE OPERATIONS - INTEGRATION TESTS")
    print("=" * 80)
    print(f"\nClient ID: {client_id}")
    print(f"Project ID: {project_id}")
    print("\n" + "=" * 80)

    # Test 1: List files
    print("\n\n Running Test Suite: LIST FILES")
    test_list_files_by_status(api_key, api_secret, client_id, project_id)

    # Test 2: Pagination
    print("\n\n Running Test Suite: PAGINATION")
    test_list_files_with_pagination(api_key, api_secret, client_id, project_id)

    # Test 3: Search with filters
    print("\n\n Running Test Suite: SEARCH FILTERS")
    test_search_with_filters(api_key, api_secret, client_id, project_id)


if __name__ == "__main__":
    # Import credentials
    try:
        import cred

        API_KEY = cred.API_KEY
        API_SECRET = cred.API_SECRET
        CLIENT_ID = cred.CLIENT_ID
        PROJECT_ID = cred.PROJECT_ID
    except (ImportError, AttributeError):
        # Fall back to environment variables
        API_KEY = os.environ.get("LABELLERR_API_KEY", "")
        API_SECRET = os.environ.get("LABELLERR_API_SECRET", "")
        CLIENT_ID = os.environ.get("LABELLERR_CLIENT_ID", "")
        PROJECT_ID = os.environ.get("LABELLERR_PROJECT_ID", "")

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
        print("\n2. Or setting environment variables:")
        print("   export LABELLERR_API_KEY='your_api_key'")
        print("   export LABELLERR_API_SECRET='your_api_secret'")
        print("   export LABELLERR_CLIENT_ID='your_client_id'")
        print("   export LABELLERR_PROJECT_ID='your_project_id'")
        print("\n" + "=" * 80)
        sys.exit(1)

    # Run all tests
    run_all_tests(API_KEY, API_SECRET, CLIENT_ID, PROJECT_ID)

    # Example of running specific tests with file IDs
    # Uncomment and modify these lines to test with actual file IDs
    """
    # Example: Test bulk assign with specific file IDs
    file_ids = ["file_id_1", "file_id_2", "file_id_3"]
    test_bulk_assign_files(API_KEY, API_SECRET, CLIENT_ID, PROJECT_ID,
                           file_ids, "annotation")

    # Example: Test complete workflow
    test_list_then_bulk_assign_workflow(API_KEY, API_SECRET, CLIENT_ID, PROJECT_ID,
                                        target_status="pending",
                                        new_status="annotation")

    # Example: Test single file
    test_bulk_assign_single_file(API_KEY, API_SECRET, CLIENT_ID, PROJECT_ID,
                                 "single_file_id", "review")
    """
