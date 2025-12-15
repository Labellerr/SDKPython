import pytest
from unittest.mock import patch, Mock
import json
from labellerr.core.projects.image_project import ImageProject
from labellerr.core.users.base import LabellerrUsers

@pytest.fixture
def client():
    """Create a mock client"""
    from labellerr.client import LabellerrClient
    client = Mock(spec=LabellerrClient)
    client.client_id = "test-client-id"
    client.api_key = "test-api-key"
    client.api_secret = "test-api-secret"
    return client

@pytest.fixture
def project(client):
    """Create a test project instance"""
    project_data = {
        "project_id": "test_project_id",
        "data_type": "image", 
        "attached_datasets": [],
    }
    # Use __new__ to avoid initialization logic if needed, or just mock it
    proj = ImageProject.__new__(ImageProject)
    proj.client = client
    proj._LabellerrProject__project_id_input = "test_project_id"
    proj._LabellerrProject__project_data = project_data
    return proj

@pytest.mark.unit
class TestProjectLifecycle:
    """Tests for project lifecycle methods: archive, unarchive, delete"""

    def test_archive_project(self, project, client):
        """Test archiving a project"""
        mock_response = {"status": "success", "msg": "Project archived"}
        
        with patch.object(client, "make_request", return_value=mock_response) as mock_req:
            response = project.archive()
            
            assert response == mock_response
            
            # Verify the request
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            assert args[0] == "POST"
            assert "/projects/archive" in args[1]
            assert kwargs["data"] is not None
            assert '"project_id": "test_project_id"' in kwargs["data"]

    def test_unarchive_project(self, project, client):
        """Test unarchiving a project"""
        mock_response = {"status": "success", "msg": "Project unarchived"}
        
        with patch.object(client, "make_request", return_value=mock_response) as mock_req:
            # Test direct call to archive(unarchive=True)
            response = project.archive(unarchive=True)
            assert response == mock_response
            
            args, kwargs = mock_req.call_args
            assert "/projects/unarchive" in args[1]

            # Test alias unarchive()
            mock_req.reset_mock()
            response = project.unarchive()
            assert response == mock_response
            
            args, kwargs = mock_req.call_args
            assert "/projects/unarchive" in args[1]

    def test_delete_project(self, project, client):
        """Test deleting a project"""
        mock_response = {"status": "success", "msg": "Project deleted"}
        
        with patch.object(client, "make_request", return_value=mock_response) as mock_req:
            response = project.delete()
            
            assert response == mock_response
            
            # Verify the request
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            assert args[0] == "DELETE"
            assert "/projects/project/test_project_id" in args[1]
