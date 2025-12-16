"""
Unit tests for Labellerr project functionality.
"""

import pytest
from unittest.mock import patch

from labellerr.core.exceptions import LabellerrError
from labellerr.core.schemas import ExportsListResponse


@pytest.mark.unit
class TestListExports:
    """Test cases for list_exports method"""

    def test_list_exports_returns_completed_and_in_progress_exports(self, project):
        """Test that list_exports correctly returns both completed and in-progress exports"""
        mock_response = {
            "response": {
                "completed": [{"report_id": "export-123"}],
                "inProgress": [{"report_id": "export-456"}],
            }
        }

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert isinstance(result, ExportsListResponse)
            assert len(result.completed) == 1
            assert len(result.in_progress) == 1
            assert result.completed[0]["report_id"] == "export-123"
            assert result.in_progress[0]["report_id"] == "export-456"

    def test_list_exports_handles_empty_exports(self, project):
        """Test that list_exports handles case when no exports exist"""
        mock_response = {"response": {"completed": [], "inProgress": []}}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result.completed == []
            assert result.in_progress == []

    def test_list_exports_raises_error_for_invalid_response(self, project):
        """Test that list_exports raises LabellerrError when API returns invalid response"""
        with patch.object(project.client, "make_request", return_value=None):
            with pytest.raises(LabellerrError) as exc_info:
                project.list_exports()

            assert "Invalid response" in str(exc_info.value)

    def test_list_exports_raises_error_when_response_key_missing(self, project):
        """Test that list_exports raises LabellerrError when 'response' key is missing"""
        mock_response = {"error": "something went wrong"}

        with patch.object(project.client, "make_request", return_value=mock_response):
            with pytest.raises(LabellerrError) as exc_info:
                project.list_exports()

            assert "Invalid response" in str(exc_info.value)

    def test_list_exports_handles_missing_optional_fields(self, project):
        """Test that list_exports handles response with missing optional fields gracefully"""
        mock_response = {"response": {}}

        with patch.object(project.client, "make_request", return_value=mock_response):
            result = project.list_exports()

            assert result.completed == []
            assert result.in_progress == []
