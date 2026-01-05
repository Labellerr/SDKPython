import pytest
import os
from labellerr.core.exceptions import LabellerrError

@pytest.mark.integration
class TestSam2Workflow:
    """Test SAM2 workflow"""

    def test_create_job_from_annotations(self, integration_client):
        """Test creating a SAM2 job from annotations"""
        
        # Use IDs provided by user or from env, with fallbacks
        project_id = os.getenv("TEST_SAM2_PROJECT_ID", "ninnetta_necessary_penguin_93195")
        file_id = os.getenv("TEST_SAM2_FILE_ID", "2a8d96ca-9161-4dee-ad3b-a5faf301bc6c")
        email_id = os.getenv("TEST_SAM2_EMAIL_ID", "dev@labellerr.com")

        try:
            response = integration_client.sam2.create_job_from_annotations(
                project_id=project_id,
                file_id=file_id,
                email_id=email_id
            )
            
            assert isinstance(response, dict)
            assert "job_ids" in response
            assert "message" in response
            assert isinstance(response["job_ids"], list)
            
        except LabellerrError as e:
            # Handle cases where the specific project/file might not exist in the test env
            if any(phrase in str(e).lower() for phrase in ["not found", "permission denied", "404", "403"]):
                 pytest.skip(f"Skipping SAM2 test due to invalid resource or permission: {e}")
            else:
                raise
