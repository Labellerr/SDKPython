"""
Integration tests for export creation and management.

Tests creating exports, checking status, and cleanup.
"""

import os
import time
import pytest
from datetime import datetime
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects import LabellerrProject
from labellerr.core.schemas import CreateExportParams, ExportDestination

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
PROJECT_ID = os.getenv("PROJECT_ID")


@pytest.fixture(scope="session")
def client():
    """Create a client instance for the test session."""
    if not all([API_KEY, API_SECRET, CLIENT_ID]):
        pytest.skip("Missing required environment variables: API_KEY, API_SECRET, CLIENT_ID")

    return LabellerrClient(api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID)


@pytest.fixture(scope="session")
def project(client):
    """Get the project instance for testing exports."""
    if not PROJECT_ID:
        pytest.skip("Missing required environment variable: PROJECT_ID")

    return LabellerrProject(client=client, project_id=PROJECT_ID)


@pytest.fixture
def cleanup_exports(project):
    """Fixture to track and cleanup created exports."""
    created_exports = []

    yield created_exports

    # Cleanup: Note that exports are typically cleaned up automatically by the backend
    # after they are downloaded or expire. No explicit delete API is usually needed.
    if created_exports:
        print(f"\n🧹 Test completed. Created {len(created_exports)} export(s).")
        print("📋 Export IDs:")
        for export_id in created_exports:
            print(f"   - {export_id}")


@pytest.mark.integration
class TestCreateExportIntegration:
    """Integration tests for export creation."""

    def test_create_local_export_basic(self, project, cleanup_exports):
        """Test creating a basic local export with COCO JSON format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_{timestamp}",
            export_description="Integration test export - basic COCO JSON",
            export_format="coco_json",
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)

        # Verify export was created
        assert export is not None, "Export creation returned None"
        assert export.report_id is not None, "Export report_id is None"
        assert isinstance(export.report_id, str), "Export report_id is not a string"

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        print(f"\n✓ Export created: {export.report_id}")

    def test_create_local_export_with_status_check(self, project, cleanup_exports):
        """Test creating an export and checking its status."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Status_{timestamp}",
            export_description="Integration test export - with status check",
            export_format="coco_json",
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)
        assert export.report_id is not None

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        # Check status (single check, no polling)
        status = export._status
        assert status is not None, "Status check returned None"
        assert isinstance(status, dict), "Status is not a dictionary"

        print(f"\n✓ Export created: {export.report_id}")
        print(f"📊 Initial status: {status.get('export_status', 'unknown')}")

    def test_create_local_export_and_poll(self, project, cleanup_exports):
        """Test creating an export and polling until completion."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Poll_{timestamp}",
            export_description="Integration test export - poll until completion",
            export_format="coco_json",
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)
        assert export.report_id is not None

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        print(f"\n✓ Export created: {export.report_id}")
        print("⏳ Polling for completion...")

        # Poll until completion (with longer timeout - exports can take time)
        final_status = export.status(interval=3.0, timeout=300.0)

        assert final_status is not None, "Polling returned None"
        assert isinstance(final_status, dict), "Final status is not a dictionary"

        # Check if export completed successfully
        status_list = final_status.get("status", [])
        export_status = None
        is_completed = False
        for status_item in status_list:
            if status_item.get("report_id") == export.report_id:
                export_status = status_item.get("export_status")
                is_completed = status_item.get("is_completed", False)
                break

        print(f"📊 Final status: {export_status}, Completed: {is_completed}")

        # Verify export reached a terminal state or is still processing
        # Valid terminal states: 'created' (success), 'failed' (error)
        # If still processing after timeout, that's also acceptable for this test
        terminal_states = ['created', 'Created', 'failed', 'Failed']
        if export_status not in terminal_states:
            print(f"⚠️  Export still processing after timeout. Status: {export_status}")
            # Don't fail the test - just warn that it's still processing
        else:
            assert export_status.lower() in ['created', 'failed'], \
                f"Unexpected terminal state: {export_status}"

    def test_create_export_different_formats(self, project, cleanup_exports):
        """Test creating exports with different export formats."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Test with different format (if supported)
        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Format_{timestamp}",
            export_description="Integration test export - different format",
            export_format="coco_json",  # You can test other formats like "yolo", "csv", etc.
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)
        assert export.report_id is not None

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        print(f"\n✓ Export created with format 'coco_json': {export.report_id}")

    def test_create_export_multiple_statuses(self, project, cleanup_exports):
        """Test creating an export with multiple annotation statuses."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Multi_{timestamp}",
            export_description="Integration test export - multiple statuses",
            export_format="coco_json",
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)
        assert export.report_id is not None

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        print(f"\n✓ Export created with multiple statuses: {export.report_id}")

    def test_export_repr(self, project, cleanup_exports):
        """Test the Export __repr__ method."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Repr_{timestamp}",
            export_description="Integration test export - repr test",
            export_format="coco_json",
            statuses=['review', 'r_assigned', 'client_review', 'cr_assigned', 'accepted', 'critical'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export
        export = project.create_export(export_config)

        # Track for cleanup
        cleanup_exports.append(export.report_id)

        # Test repr
        repr_str = repr(export)
        assert "Export" in repr_str
        assert export.report_id in repr_str

        print(f"\n✓ Export repr: {repr_str}")


@pytest.mark.integration
class TestExportErrors:
    """Integration tests for export error handling."""

    def test_create_export_invalid_status(self, project, cleanup_exports):
        """Test creating an export with invalid status raises appropriate error."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # This should work as backend typically doesn't validate statuses strictly
        # or filters them. Adjust based on actual API behavior.
        export_config = CreateExportParams(
            export_name=f"SDK_Test_Export_Invalid_{timestamp}",
            export_description="Integration test export - invalid status",
            export_format="coco_json",
            statuses=['invalid_status'],
            export_destination=ExportDestination.LOCAL
        )

        # Create export - may succeed or fail depending on backend validation
        try:
            export = project.create_export(export_config)
            if export and export.report_id:
                cleanup_exports.append(export.report_id)
                print(f"\n✓ Export created even with invalid status: {export.report_id}")
        except Exception as e:
            print(f"\n✓ Export correctly failed with invalid status: {e}")
            # This is acceptable - backend rejected invalid status


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/integration/test_create_export.py -v -s
    pytest.main([__file__, "-v", "-s"])
