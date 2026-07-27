import pytest
from unittest.mock import Mock, patch
from labellerr.core.sam2.base import LabellerrSam2
from labellerr.client import LabellerrClient

class TestSam2Unit:
    def test_create_job_from_annotations_payload(self):
        """Test that create_job_from_annotations sends correct payload"""
        mock_client = Mock(spec=LabellerrClient)
        mock_client.base_url = "https://api.labellerr.com"
        mock_client.client_id = "test_client_id"
        mock_client.make_request.return_value = {
            "response": {
                "job_ids": ["job_123"],
                "message": "Created 1 jobs"
            }
        }
        
        sam2 = LabellerrSam2(mock_client)
        
        project_id = "test_project"
        file_id = "test_file"
        email_id = "test@example.com"
        
        result = sam2.create_job_from_annotations(project_id, file_id, email_id)
        
        # Verify the request was made with correct URL and payload
        mock_client.make_request.assert_called_once()
        args, kwargs = mock_client.make_request.call_args
        
        assert args[0] == "POST"
        assert "create_job_from_annotations" in args[1]
        assert "client_id=test_client_id" in args[1]
        
        payload = kwargs["json"]
        assert payload["project_id"] == project_id
        assert payload["file_id"] == file_id
        assert payload["email_id"] == email_id
        
        assert result["job_ids"] == ["job_123"]
