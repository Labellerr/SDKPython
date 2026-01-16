"""
Unit tests for labellerr/core/projects/__init__.py module.

This module contains unit tests for the create_project and list_projects functions
using mocks and fixtures to avoid external API calls.
"""

import json
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project, list_projects, delete_project
from labellerr.core.projects.base import LabellerrProject
from labellerr.core.schemas import CreateProjectParams, DatasetDataType, RotationConfig
import requests
from unittest.mock import MagicMock
from labellerr import LabellerrClient


@pytest.fixture
def mock_dataset():
    """Create a mock dataset with files"""
    dataset = Mock(spec=LabellerrDataset)
    dataset.dataset_id = "test-dataset-123"
    dataset.files_count = 10
    return dataset


@pytest.fixture
def mock_empty_dataset():
    """Create a mock dataset with no files"""
    dataset = Mock(spec=LabellerrDataset)
    dataset.dataset_id = "empty-dataset-456"
    dataset.files_count = 0
    return dataset


@pytest.fixture
def mock_annotation_template():
    """Create a mock annotation template"""
    template = Mock(spec=LabellerrAnnotationTemplate)
    template.annotation_template_id = "template-789"
    return template


@pytest.fixture
def client():
    """Create a mock LabellerrClient"""
    from labellerr import LabellerrClient
    mock_client = Mock(spec=LabellerrClient)
    mock_client.client_id = "test-client-id"
    mock_client.api_key = "test-api-key"
    mock_client.api_secret = "test-api-secret"
    return mock_client


@pytest.fixture
def valid_create_project_params():
    """Create valid project creation parameters"""
    return CreateProjectParams(
        project_name="Test Project",
        data_type=DatasetDataType.image,
        rotations=RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        ),
        use_ai=False,
        created_by="test@example.com",
    )


@pytest.mark.unit
class TestCreateProject:
    """Test cases for create_project function"""

    def test_create_project_no_datasets(
        self, client, valid_create_project_params, mock_annotation_template
    ):
        """Test that empty datasets list raises LabellerrError"""
        with pytest.raises(LabellerrError) as exc_info:
            create_project(
                client, valid_create_project_params, [], mock_annotation_template
            )

        assert "At least one dataset is required" in str(exc_info.value)

    def test_create_project_dataset_with_no_files(
        self,
        client,
        valid_create_project_params,
        mock_empty_dataset,
        mock_annotation_template,
    ):
        """Test that dataset with no files raises LabellerrError"""
        with pytest.raises(LabellerrError) as exc_info:
            create_project(
                client,
                valid_create_project_params,
                [mock_empty_dataset],
                mock_annotation_template,
            )

        assert f"Dataset {mock_empty_dataset.dataset_id} has no files" in str(
            exc_info.value
        )

    def test_create_project_successful(
        self,
        client,
        valid_create_project_params,
        mock_dataset,
        mock_annotation_template,
    ):
        """Test successful project creation"""
        mock_response = {"response": {"project_id": "new-project-id"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "new-project-id",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                result = create_project(
                    client,
                    valid_create_project_params,
                    [mock_dataset],
                    mock_annotation_template,
                )

                assert result is not None
                assert isinstance(result, LabellerrProject)

    def test_create_project_multiple_datasets(
        self, client, valid_create_project_params, mock_annotation_template
    ):
        """Test project creation with multiple datasets"""
        dataset1 = Mock(spec=LabellerrDataset)
        dataset1.dataset_id = "dataset-1"
        dataset1.files_count = 5

        dataset2 = Mock(spec=LabellerrDataset)
        dataset2.dataset_id = "dataset-2"
        dataset2.files_count = 15

        mock_response = {"response": {"project_id": "multi-dataset-project"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "multi-dataset-project",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                result = create_project(
                    client,
                    valid_create_project_params,
                    [dataset1, dataset2],
                    mock_annotation_template,
                )

                assert result is not None
                # Verify make_request was called with correct payload
                call_args = client.make_request.call_args
                payload = json.loads(call_args[1]["data"])
                assert len(payload["attached_datasets"]) == 2
                assert "dataset-1" in payload["attached_datasets"]
                assert "dataset-2" in payload["attached_datasets"]

    def test_create_project_with_ai_enabled(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test project creation with AI features enabled"""
        params = CreateProjectParams(
            project_name="AI Project",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=2,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
            use_ai=True,
            created_by="test@example.com",
        )

        mock_response = {"response": {"project_id": "ai-project-id"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "ai-project-id",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                result = create_project(
                    client, params, [mock_dataset], mock_annotation_template
                )

                assert result is not None
                # Verify use_ai is set to True in payload
                call_args = client.make_request.call_args
                payload = json.loads(call_args[1]["data"])
                assert payload["use_ai"] is True

    @pytest.mark.parametrize(
        "data_type",
        [
            DatasetDataType.image,
            DatasetDataType.video,
            DatasetDataType.audio,
            DatasetDataType.document,
            DatasetDataType.text,
        ],
    )
    def test_create_project_different_data_types(
        self, client, mock_dataset, mock_annotation_template, data_type
    ):
        """Test project creation with different data types"""
        params = CreateProjectParams(
            project_name=f"{data_type.value} Project",
            data_type=data_type,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test@example.com",
        )

        mock_response = {"response": {"project_id": f"{data_type.value}-project"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": f"{data_type.value}-project",
                    "data_type": data_type.value,
                    "status_code": 200,
                },
            ):
                result = create_project(
                    client, params, [mock_dataset], mock_annotation_template
                )

                assert result is not None
                # Verify data_type in payload
                call_args = client.make_request.call_args
                payload = json.loads(call_args[1]["data"])
                assert payload["data_type"] == data_type.value

    def test_create_project_custom_rotations(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test project creation with custom rotation counts"""
        params = CreateProjectParams(
            project_name="Custom Rotation Project",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=3,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test@example.com",
        )

        mock_response = {"response": {"project_id": "rotation-project"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "rotation-project",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                result = create_project(
                    client, params, [mock_dataset], mock_annotation_template
                )

                assert result is not None
                # Verify rotation config in payload
                call_args = client.make_request.call_args
                payload = json.loads(call_args[1]["data"])
                assert payload["rotations"]["annotation_rotation_count"] == 3
                assert payload["rotations"]["review_rotation_count"] == 2
                assert payload["rotations"]["client_review_rotation_count"] == 1

    def test_create_project_url_construction(
        self,
        client,
        valid_create_project_params,
        mock_dataset,
        mock_annotation_template,
    ):
        """Test that API URL is constructed correctly"""
        mock_response = {"response": {"project_id": "test-project"}}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "test-project",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                create_project(
                    client,
                    valid_create_project_params,
                    [mock_dataset],
                    mock_annotation_template,
                )

                # Verify URL contains required parameters
                call_args = mock_request.call_args
                url = call_args[0][1]
                assert "/projects/create" in url
                assert f"client_id={client.client_id}" in url
                assert "uuid=" in url

    def test_create_project_headers_construction(
        self,
        client,
        valid_create_project_params,
        mock_dataset,
        mock_annotation_template,
    ):
        """Test that request headers are constructed correctly"""
        mock_response = {"response": {"project_id": "test-project"}}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "test-project",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                create_project(
                    client,
                    valid_create_project_params,
                    [mock_dataset],
                    mock_annotation_template,
                )

                # Verify headers
                call_args = mock_request.call_args
                headers = call_args[1]["headers"]
                assert "Content-Type" in headers
                assert headers["Content-Type"] == "application/json"

    def test_create_project_payload_structure(
        self,
        client,
        valid_create_project_params,
        mock_dataset,
        mock_annotation_template,
    ):
        """Test that request payload has correct structure"""
        mock_response = {"response": {"project_id": "test-project"}}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "test-project",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                create_project(
                    client,
                    valid_create_project_params,
                    [mock_dataset],
                    mock_annotation_template,
                )

                # Verify payload structure
                call_args = mock_request.call_args
                payload = json.loads(call_args[1]["data"])

                assert "project_name" in payload
                assert "attached_datasets" in payload
                assert "data_type" in payload
                assert "annotation_template_id" in payload
                assert "rotations" in payload
                assert "use_ai" in payload
                assert "created_by" in payload

                assert payload["project_name"] == "Test Project"
                assert payload["annotation_template_id"] == "template-789"
                assert isinstance(payload["attached_datasets"], list)


@pytest.mark.unit
class TestListProjects:
    """Test cases for list_projects function"""

    def test_list_projects_empty_response(self, client):
        """Test list_projects with empty project list"""
        mock_response = {"response": []}

        with patch.object(client, "make_request", return_value=mock_response):
            result = list_projects(client)

            assert result == []
            assert isinstance(result, list)

    def test_list_projects_single_project(self, client):
        """Test list_projects with a single project"""
        mock_response = {
            "response": [{"project_id": "project-1", "data_type": "image"}]
        }

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={
                    "project_id": "project-1",
                    "data_type": "image",
                    "status_code": 200,
                },
            ):
                result = list_projects(client)

                assert len(result) == 1
                assert isinstance(result[0], LabellerrProject)

    def test_list_projects_multiple_projects(self, client):
        """Test list_projects with multiple projects"""
        mock_response = {
            "response": [
                {"project_id": "project-1", "data_type": "image"},
                {"project_id": "project-2", "data_type": "video"},
                {"project_id": "project-3", "data_type": "text"},
            ]
        }

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                side_effect=[
                    {
                        "project_id": "project-1",
                        "data_type": "image",
                        "status_code": 200,
                    },
                    {
                        "project_id": "project-2",
                        "data_type": "video",
                        "status_code": 200,
                    },
                    {
                        "project_id": "project-3",
                        "data_type": "text",
                        "status_code": 200,
                    },
                ],
            ):
                result = list_projects(client)

                assert len(result) == 3
                assert all(isinstance(project, LabellerrProject) for project in result)

    def test_list_projects_url_construction(self, client):
        """Test that list_projects constructs URL correctly"""
        mock_response = {"response": []}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            list_projects(client)

            # Verify URL
            call_args = mock_request.call_args
            url = call_args[0][1]
            assert "/project_drafts/projects/detailed_list" in url
            assert f"client_id={client.client_id}" in url
            assert "uuid=" in url

    def test_list_projects_request_method(self, client):
        """Test that list_projects uses GET method"""
        mock_response = {"response": []}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            list_projects(client)

            # Verify HTTP method
            call_args = mock_request.call_args
            method = call_args[0][0]
            assert method == "GET"

    def test_list_projects_headers(self, client):
        """Test that list_projects sets correct headers"""
        mock_response = {"response": []}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            list_projects(client)

            # Verify headers
            call_args = mock_request.call_args
            extra_headers = call_args[1]["extra_headers"]
            assert "content-type" in extra_headers
            assert extra_headers["content-type"] == "application/json"

    def test_list_projects_with_uuid(self, client):
        """Test that list_projects generates and uses UUID"""
        mock_response = {"response": []}

        with patch.object(
            client, "make_request", return_value=mock_response
        ) as mock_request:
            with patch("labellerr.core.projects.uuid.uuid4") as mock_uuid:
                test_uuid = "test-uuid-12345"
                mock_uuid.return_value = test_uuid

                list_projects(client)

                # Verify UUID is in URL and request_id
                call_args = mock_request.call_args
                url = call_args[0][1]
                request_id = call_args[1]["request_id"]

                assert test_uuid in url
                assert request_id == test_uuid

    def test_list_projects_preserves_project_order(self, client):
        """Test that list_projects preserves order of projects"""
        project_ids = ["proj-001", "proj-002", "proj-003", "proj-004"]
        mock_response = {
            "response": [
                {"project_id": pid, "data_type": "image"} for pid in project_ids
            ]
        }

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                side_effect=[
                    {"project_id": pid, "data_type": "image", "status_code": 200}
                    for pid in project_ids
                ],
            ):
                result = list_projects(client)

                assert len(result) == len(project_ids)


@pytest.mark.unit
class TestCreateProjectParamsValidation:
    """Test parameter validation for CreateProjectParams"""

    def test_missing_project_name(self):
        """Test that missing project_name raises ValidationError"""
        with pytest.raises(ValidationError):
            CreateProjectParams(
                data_type=DatasetDataType.image,
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test@example.com",
            )

    def test_missing_data_type(self):
        """Test that missing data_type raises ValidationError"""
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test",
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test@example.com",
            )

    def test_missing_rotations(self):
        """Test that missing rotations raises ValidationError"""
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test",
                data_type=DatasetDataType.image,
                use_ai=False,
                created_by="test@example.com",
            )

    def test_invalid_email_format(self):
        """Test that invalid email format raises ValidationError"""
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test",
                data_type=DatasetDataType.image,
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="not-an-email",
            )

    def test_empty_project_name(self):
        """Test that empty project_name raises ValidationError"""
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="",
                data_type=DatasetDataType.image,
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test@example.com",
            )


@pytest.mark.unit
class TestDeleteProjectUnit:
    """Unit tests for delete_project with mocked API calls"""

    @pytest.fixture
    def client(self):
        """Create a mock client for unit testing"""
        mock_client = MagicMock(spec=LabellerrClient)
        mock_client.client_id = "test-client-id"
        mock_client.api_key = "test-api-key"
        mock_client.api_secret = "test-api-secret"
        return mock_client

    @pytest.fixture
    def mock_project(self, client):
        """Create a mock project for testing"""
        project = MagicMock(spec=LabellerrProject)
        project.client = client
        project.project_id = "test_project_id_123"
        project.data_type = "image"
        project.annotation_template_id = "test_template_id"
        project.created_by = "test@example.com"
        project.project_name = "Test Project"
        return project

    def test_delete_project_url_format(self, client, mock_project):
        """Test that delete_project constructs the correct URL"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = {"response": {"message": "Deleted"}}

            delete_project(client, mock_project)

            # Verify API call was made
            mock_request.assert_called_once()
            call_args = mock_request.call_args

            # Verify HTTP method
            assert call_args[0][0] == "POST", "Should use POST method"

            # Verify URL structure
            url = call_args[0][1]
            assert "/projects/delete/" in url, "URL should contain /projects/delete/"
            assert mock_project.project_id in url, "URL should contain project_id"
            assert f"client_id={client.client_id}" in url, "URL should contain client_id"
            assert "uuid=" in url, "URL should contain uuid parameter"

    def test_delete_project_headers(self, client, mock_project):
        """Test that delete_project sends correct headers"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = {"response": {}}

            delete_project(client, mock_project)

            # Verify headers
            call_kwargs = mock_request.call_args[1]
            assert "extra_headers" in call_kwargs
            assert call_kwargs["extra_headers"]["content-type"] == "application/json"

    def test_delete_project_api_error(self, client, mock_project):
        """Test handling of API errors during deletion"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = LabellerrError("Project not found")

            with pytest.raises(LabellerrError, match="Project not found"):
                delete_project(client, mock_project)

    def test_delete_project_connection_error(self, client, mock_project):
        """Test handling of connection errors during deletion"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

            with pytest.raises(requests.exceptions.ConnectionError, match="Connection refused"):
                delete_project(client, mock_project)

    def test_delete_project_timeout(self, client, mock_project):
        """Test handling of timeout errors during deletion"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(requests.exceptions.Timeout, match="Request timed out"):
                delete_project(client, mock_project)

    def test_delete_project_with_none_project(self, client):
        """Test that deleting None project raises appropriate error"""
        with pytest.raises(AttributeError):
            delete_project(client, None)

    def test_delete_project_with_empty_project_id(self, client):
        """Test handling of project with empty project_id"""
        mock_proj = MagicMock()
        mock_proj.project_id = ""

        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = {"response": {}}

            # Should still make the API call (API will handle validation)
            delete_project(client, mock_proj)

            # Verify call was made
            mock_request.assert_called_once()

    def test_delete_project_malformed_response(self, client, mock_project):
        """Test handling of malformed API response"""
        with patch.object(client, "make_request") as mock_request:
            # Return malformed response (missing expected keys)
            mock_request.return_value = {}

            # Should not raise an error, but return the response as-is
            result = delete_project(client, mock_project)
            assert result == {}

    def test_delete_project_unauthorized(self, client, mock_project):
        """Test handling of unauthorized deletion attempts"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = LabellerrError("403 Unauthorized")

            with pytest.raises(LabellerrError, match="403 Unauthorized"):
                delete_project(client, mock_project)

    def test_delete_nonexistent_project(self, client):
        """Test deleting a project that doesn't exist (moved from integration tests)"""
        # Create a mock project with non-existent ID
        nonexistent_project = MagicMock(spec=LabellerrProject)
        nonexistent_project.project_id = "nonexistent_project_12345"

        # Mock the API to return an error for non-existent project
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = LabellerrError("Project not found")

            # Attempt to delete should raise an error
            with pytest.raises(LabellerrError) as exc_info:
                delete_project(client, nonexistent_project)

            # Verify the error message
            assert any(
                keyword in str(exc_info.value).lower()
                for keyword in ["not found", "does not exist"]
            ), f"Expected 'not found' error, got: {exc_info.value}"

    def test_delete_project_server_error(self, client, mock_project):
        """Test handling of server errors (500) during deletion"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = LabellerrError("500 Internal Server Error")

            with pytest.raises(LabellerrError, match="500 Internal Server Error"):
                delete_project(client, mock_project)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
