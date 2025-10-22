import os

import pytest
from pydantic import ValidationError

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


@pytest.fixture
def client():
    """Create a test client with mock credentials"""
    return LabellerrClient("test_api_key", "test_api_secret")


@pytest.fixture
def sample_valid_payload():
    """Create a sample valid payload for initiate_create_project"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_image = os.path.join(current_dir, "test_data", "test_image.jpg")

    # Create test directory and file if they don't exist
    os.makedirs(os.path.join(current_dir, "test_data"), exist_ok=True)
    if not os.path.exists(test_image):
        with open(test_image, "w") as f:
            f.write("dummy image content")

    return {
        "client_id": "12345",
        "dataset_name": "Test Dataset",
        "dataset_description": "Dataset for testing",
        "data_type": "image",
        "created_by": "test_user@example.com",
        "project_name": "Test Project",
        "autolabel": False,
        "files_to_upload": [test_image],
        "annotation_guide": [
            {
                "option_type": "radio",
                "question": "Test Question",
                "options": ["Option 1", "Option 2"],
            }
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
    }


class TestInitiateCreateProject:

    def test_missing_required_parameters(self, client, sample_valid_payload):
        """Test error handling for missing required parameters"""
        # Remove required parameters one by one and test
        required_params = [
            "client_id",
            "dataset_name",
            "dataset_description",
            "data_type",
            "created_by",
            "project_name",
            "autolabel",
        ]

        for param in required_params:
            invalid_payload = sample_valid_payload.copy()
            del invalid_payload[param]

            with pytest.raises(LabellerrError) as exc_info:
                client.initiate_create_project(invalid_payload)

            assert f"Required parameter {param} is missing" in str(exc_info.value)

        # Test annotation_guide separately since it has special validation
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["annotation_guide"]

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert (
            "Please provide either annotation guide or annotation template id"
            in str(exc_info.value)
        )

    def test_invalid_client_id(self, client, sample_valid_payload):
        """Test error handling for invalid client_id"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["client_id"] = 123  # Not a string

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "client_id must be a non-empty string" in str(exc_info.value)

        # Test empty string
        invalid_payload["client_id"] = "   "
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        # Whitespace client_id causes HTTP header issues
        assert "Invalid leading whitespace" in str(
            exc_info.value
        ) or "client_id must be a non-empty string" in str(exc_info.value)

    def test_invalid_annotation_guide(self, client, sample_valid_payload):
        """Test error handling for invalid annotation guide"""
        invalid_payload = sample_valid_payload.copy()

        # Missing option_type
        invalid_payload["annotation_guide"] = [{"question": "Test Question"}]
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "option_type is required in annotation_guide" in str(exc_info.value)

        # Invalid option_type
        invalid_payload["annotation_guide"] = [
            {"option_type": "invalid_type", "question": "Test Question"}
        ]
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "option_type must be one of" in str(exc_info.value)

    def test_both_upload_methods_specified(self, client, sample_valid_payload):
        """Test error when both files_to_upload and folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["folder_to_upload"] = "/path/to/folder"

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Cannot provide both files_to_upload and folder_to_upload" in str(
            exc_info.value
        )

    def test_no_upload_method_specified(self, client, sample_valid_payload):
        """Test error when neither files_to_upload nor folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Either files_to_upload or folder_to_upload must be provided" in str(
            exc_info.value
        )

    def test_empty_files_to_upload(self, client, sample_valid_payload):
        """Test error handling for empty files_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["files_to_upload"] = []

        with pytest.raises(LabellerrError):
            client.initiate_create_project(invalid_payload)

    def test_invalid_folder_to_upload(self, client, sample_valid_payload):
        """Test error handling for invalid folder_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]
        invalid_payload["folder_to_upload"] = "   "

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Folder path does not exist" in str(exc_info.value)


class TestCreateUser:
    """Test cases for create_user method"""

    def test_create_user_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                # Missing email_id, projects, roles
            )

        assert "missing" in str(exc_info.value).lower()

    def test_create_user_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.create_user(
                client_id=12345,  # Not a string
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_create_user_empty_projects(self, client):
        """Test error handling for empty projects list"""
        with pytest.raises(ValidationError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=[],  # Empty list
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "projects" in str(exc_info.value).lower()

    def test_create_user_empty_roles(self, client):
        """Test error handling for empty roles list"""
        with pytest.raises(ValidationError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


class TestUpdateUserRole:
    """Test cases for update_user_role method"""

    def test_update_user_role_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.update_user_role(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, roles
            )

        assert "missing" in str(exc_info.value).lower()

    def test_update_user_role_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.update_user_role(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_update_user_role_empty_roles(self, client):
        """Test error handling for empty roles list"""
        with pytest.raises(ValidationError) as exc_info:
            client.update_user_role(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


class TestDeleteUser:
    """Test cases for delete_user method"""

    def test_delete_user_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, user_id
            )

        assert "missing" in str(exc_info.value).lower()

    def test_delete_user_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.delete_user(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_project_id(self, client):
        """Test error handling for invalid project_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id=12345,  # Not a string
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "project_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_email_id(self, client):
        """Test error handling for invalid email_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                email_id=12345,  # Not a string
                user_id="user_123",
            )

        assert "email_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_user_id(self, client):
        """Test error handling for invalid user_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                user_id=12345,  # Not a string
            )

        assert "user_id" in str(exc_info.value).lower()


class TestAddUserToProject:
    """Test cases for add_user_to_project method"""

    def test_add_user_to_project_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.add_user_to_project(
                client_id="12345",
                project_id="project_123",
                # Missing email_id
            )

        assert "missing" in str(exc_info.value).lower()

    def test_add_user_to_project_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.add_user_to_project(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


class TestRemoveUserFromProject:
    """Test cases for remove_user_from_project method"""

    def test_remove_user_from_project_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.remove_user_from_project(
                client_id="12345",
                project_id="project_123",
                # Missing email_id
            )

        assert "missing" in str(exc_info.value).lower()

    def test_remove_user_from_project_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.remove_user_from_project(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


class TestChangeUserRole:
    """Test cases for change_user_role method"""

    def test_change_user_role_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.change_user_role(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                # Missing new_role_id
            )

        assert "missing" in str(exc_info.value).lower()

    def test_change_user_role_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(ValidationError) as exc_info:
            client.change_user_role(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                new_role_id="7",
            )

        assert "client_id" in str(exc_info.value).lower()


class TestListAndBulkAssignFiles:
    """Tests for list_file and bulk_assign_files methods"""

    def test_list_file_missing_required(self, client):
        with pytest.raises(TypeError):
            client.list_file(client_id="12345", project_id="project_123")

    def test_bulk_assign_files_missing_required(self, client):
        with pytest.raises(TypeError):
            client.bulk_assign_files(
                client_id="12345", project_id="project_123", new_status="None"
            )


if __name__ == "__main__":
    pytest.main()
