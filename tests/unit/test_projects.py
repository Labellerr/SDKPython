"""
Unit tests for Labellerr project functionality.
"""

import pytest
from unittest.mock import patch

from labellerr.core.projects.image_project import ImageProject


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

    def test_list_exports_returns_api_response(self, project):
        """Test that list_exports returns the API response directly"""
        mock_response = {
            "response": [
                {"report_id": "export-123", "status": "completed"},
                {"report_id": "export-456", "status": "pending"},
            ]
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result == mock_response
            assert len(result["response"]) == 2

    def test_list_exports_calls_correct_endpoint(self, project):
        """Test that list_exports calls the correct API endpoint with proper parameters"""
        mock_response = {"response": []}

        with patch.object(
            project.client, "make_request", return_value=mock_response
        ) as mock_request:
            project.list_exports()

            mock_request.assert_called_once()
            call_args = mock_request.call_args

            # Verify HTTP method
            assert call_args[0][0] == "GET"

            # Verify URL contains required parameters
            url = call_args[0][1]
            assert "/exports/list" in url
            assert "project_id=test_project_id" in url
            assert "client_id=test_client_id" in url
            assert "uuid=" in url

            # Verify headers
            assert call_args[1]["extra_headers"]["Content-Type"] == "application/json"

    def test_list_exports_empty_response(self, project):
        """Test list_exports handles empty exports list"""
        mock_response = {"response": []}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result["response"] == []


if __name__ == "__main__":
    pytest.main()
