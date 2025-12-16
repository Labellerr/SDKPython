"""
Unit tests for Labellerr project functionality.

This module contains unit tests for project-related methods
including list_exports, create_export, and other project operations.
"""

import json
import pytest
import requests
from unittest.mock import patch

from labellerr.core.projects.image_project import ImageProject
from labellerr.core.exceptions import LabellerrError


@pytest.fixture
def project(client):
    """Create a test project instance without making API calls"""
    project_data = {
        "project_id": "test_project_id",
        "data_type": "image",
        "attached_datasets": [],
    }
    proj = ImageProject.__new__(ImageProject)
    proj.client = client
    proj._LabellerrProject__project_id_input = "test_project_id"
    proj._LabellerrProject__project_data = project_data
    return proj


@pytest.mark.unit
class TestListExports:
    """Test cases for list_exports method"""

    def test_list_exports_success(self, project):
        """Test successful list exports returns JSON string"""
        mock_response = {
            "response": [
                {
                    "report_id": "export-123",
                    "status": "completed",
                    "created_at": "2024-01-01T00:00:00Z",
                },
                {
                    "report_id": "export-456",
                    "status": "pending",
                    "created_at": "2024-01-02T00:00:00Z",
                },
            ]
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            # Verify result is a JSON string
            assert isinstance(result, str)

            # Parse and verify content
            parsed_result = json.loads(result)
            assert "response" in parsed_result
            assert len(parsed_result["response"]) == 2

    def test_list_exports_empty_list(self, project):
        """Test list exports when no exports exist"""
        mock_response = {"response": []}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            parsed_result = json.loads(result)
            assert parsed_result["response"] == []

    def test_list_exports_request_exception(self, project):
        """Test list exports handles RequestException properly"""
        with patch.object(
            project.client,
            "make_request",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            with pytest.raises(requests.exceptions.RequestException):
                project.list_exports()

    def test_list_exports_generic_exception(self, project):
        """Test list exports handles generic exceptions"""
        with patch.object(
            project.client, "make_request", side_effect=Exception("Unexpected error")
        ):
            with pytest.raises(Exception) as exc_info:
                project.list_exports()

            assert "Unexpected error" in str(exc_info.value)

    def test_list_exports_url_construction(self, project):
        """Test that list exports constructs the correct URL"""
        mock_response = {"response": []}

        with patch.object(
            project.client, "make_request", return_value=mock_response
        ) as mock_request:
            project.list_exports()

            # Verify make_request was called
            mock_request.assert_called_once()

            # Get the URL argument
            call_args = mock_request.call_args
            url = call_args[0][1]  # Second positional argument is the URL

            # Verify URL contains expected parameters
            assert "project_id=test_project_id" in url
            assert "client_id=test_client_id" in url
            assert "/exports/list" in url
            assert "uuid=" in url

    def test_list_exports_correct_http_method(self, project):
        """Test that list exports uses GET method"""
        mock_response = {"response": []}

        with patch.object(
            project.client, "make_request", return_value=mock_response
        ) as mock_request:
            project.list_exports()

            call_args = mock_request.call_args
            method = call_args[0][0]  # First positional argument is the method

            assert method == "GET"

    def test_list_exports_correct_headers(self, project):
        """Test that list exports sends correct headers"""
        mock_response = {"response": []}

        with patch.object(
            project.client, "make_request", return_value=mock_response
        ) as mock_request:
            project.list_exports()

            call_args = mock_request.call_args
            extra_headers = call_args[1].get("extra_headers", {})

            assert extra_headers.get("Content-Type") == "application/json"

    def test_list_exports_returns_formatted_json(self, project):
        """Test that list exports returns properly indented JSON"""
        mock_response = {"response": [{"id": "1"}]}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            # Check that it's indented (contains newlines and spaces)
            assert "\n" in result
            assert "  " in result  # 2-space indent

    def test_list_exports_timeout_exception(self, project):
        """Test list exports handles timeout exceptions"""
        with patch.object(
            project.client,
            "make_request",
            side_effect=requests.exceptions.Timeout("Request timed out"),
        ):
            with pytest.raises(requests.exceptions.Timeout):
                project.list_exports()

    def test_list_exports_connection_error(self, project):
        """Test list exports handles connection errors"""
        with patch.object(
            project.client,
            "make_request",
            side_effect=requests.exceptions.ConnectionError("Failed to connect"),
        ):
            with pytest.raises(requests.exceptions.ConnectionError):
                project.list_exports()

    def test_list_exports_with_multiple_exports(self, project):
        """Test list exports with many exports"""
        exports = [
            {"report_id": f"export-{i}", "status": "completed"} for i in range(100)
        ]
        mock_response = {"response": exports}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            parsed_result = json.loads(result)
            assert len(parsed_result["response"]) == 100


@pytest.mark.unit
class TestCheckExportStatus:
    """Test cases for check_export_status method"""

    def test_check_export_status_empty_report_ids(self, project):
        """Test check_export_status raises error for empty report_ids"""
        with pytest.raises(LabellerrError) as exc_info:
            project.check_export_status([])

        assert "report_ids cannot be empty" in str(exc_info.value)

    def test_check_export_status_success(self, project):
        """Test successful export status check"""
        mock_response = {
            "status": [
                {
                    "report_id": "export-123",
                    "is_completed": True,
                    "export_status": "Created",
                }
            ]
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            with patch.object(
                project,
                "_LabellerrProject__fetch_exports_download_url",
                return_value="https://download.url",
            ):
                result = project.check_export_status(["export-123"])

                parsed_result = json.loads(result)
                assert "status" in parsed_result

    def test_check_export_status_multiple_reports(self, project):
        """Test check_export_status with multiple report IDs"""
        mock_response = {
            "status": [
                {
                    "report_id": "export-1",
                    "is_completed": True,
                    "export_status": "Created",
                },
                {
                    "report_id": "export-2",
                    "is_completed": False,
                    "export_status": "Processing",
                },
            ]
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            with patch.object(
                project,
                "_LabellerrProject__fetch_exports_download_url",
                return_value="https://download.url",
            ):
                result = project.check_export_status(["export-1", "export-2"])

                parsed_result = json.loads(result)
                assert len(parsed_result["status"]) == 2

    def test_check_export_status_request_exception(self, project):
        """Test check_export_status handles RequestException"""
        with patch.object(
            project.client,
            "make_request",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            with pytest.raises(requests.exceptions.RequestException):
                project.check_export_status(["export-123"])


@pytest.mark.unit
class TestCreateExport:
    """Test cases for create_export method"""

    def test_create_export_missing_connection_id_for_non_local(self, project):
        """Test create_export raises error when connection_id missing for non-local export"""
        from labellerr.core.schemas import CreateExportParams, ExportDestination

        export_config = CreateExportParams(
            export_name="test_export",
            export_description="Test export description",
            export_format="json",
            statuses=["completed"],
            export_destination=ExportDestination.S3,
            connection_id="",  # Empty connection_id
        )

        with pytest.raises(LabellerrError) as exc_info:
            project.create_export(export_config)

        assert "connection_id is required" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main()
