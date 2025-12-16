"""
Unit tests for Labellerr project functionality.
"""

import pytest
from unittest.mock import patch


@pytest.mark.unit
class TestListExports:
    """Test cases for list_exports method"""

    def test_list_exports_returns_api_response(self, project):
        """Test that list_exports returns the API response correctly"""
        mock_response = {
            "response": {
                "completed": [
                    {"report_id": "export-123", "status": "completed"},
                ],
                "inProgress": [
                    {"report_id": "export-456", "status": "pending"},
                ],
            }
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result["completed"] == mock_response["response"]["completed"]
            assert result["in_progress"] == mock_response["response"]["inProgress"]

    def test_list_exports_calls_correct_endpoint(self, project):
        """Test that list_exports calls the correct API endpoint with proper parameters"""
        mock_response = {"response": {"completed": [], "inProgress": []}}

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
        mock_response = {"response": {"completed": [], "inProgress": []}}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result["completed"] == []
            assert result["in_progress"] == []
