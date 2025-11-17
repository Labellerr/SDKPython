"""
Unit tests for Labellerr client functionality.

This module contains unit tests that test individual components
in isolation using mocks and fixtures.
"""

import pytest
from pydantic import ValidationError

from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project
from labellerr.core.projects.image_project import ImageProject
from labellerr.core.users.base import LabellerrUsers
from labellerr.core.schemas.projects import CreateProjectParams, RotationConfig
from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core.datasets import LabellerrDataset
from unittest.mock import Mock, patch


@pytest.fixture
def project(client):
    """Create a test project instance without making API calls"""
    # Create a mock ImageProject instance directly, bypassing the metaclass factory
    project_data = {
        "project_id": "test_project_id",
        "data_type": "image",
        "attached_datasets": [],
    }
    # Use __new__ to create instance without calling __init__ through metaclass
    proj = ImageProject.__new__(ImageProject)
    proj.client = client
    proj._LabellerrProject__project_id_input = "test_project_id"
    proj._LabellerrProject__project_data = project_data
    return proj


@pytest.fixture
def users(client):
    """Create a test users instance with client reference"""
    users_instance = LabellerrUsers(client)
    return users_instance


@pytest.fixture
def sample_valid_params():
    """Create a sample valid CreateProjectParams for create_project"""
    return CreateProjectParams(
        project_name="Test Project",
        data_type="image",
        rotations=RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        ),
        use_ai=False,
        created_by="test_user@example.com",
    )


@pytest.fixture
def mock_dataset():
    """Create a mock dataset for testing"""
    dataset = Mock(spec=LabellerrDataset)
    dataset.dataset_id = "test-dataset-id"
    dataset.files_count = 10
    return dataset


@pytest.fixture
def mock_annotation_template():
    """Create a mock annotation template for testing"""
    template = Mock(spec=LabellerrAnnotationTemplate)
    template.annotation_template_id = "test-template-id"
    return template


@pytest.mark.unit
class TestInitiateCreateProject:

    def test_missing_required_parameters(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test error handling for missing required parameters"""
        # Test missing project_name
        with pytest.raises(ValidationError):
            CreateProjectParams(
                data_type="image",
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test_user@example.com",
                # Missing project_name
            )

        # Test missing data_type
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test Project",
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test_user@example.com",
                # Missing data_type
            )

        # Test missing rotations
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test Project",
                data_type="image",
                use_ai=False,
                created_by="test_user@example.com",
                # Missing rotations
            )

    def test_invalid_created_by_email(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test error handling for invalid created_by email format"""
        # Test invalid email format - should raise ValidationError during CreateProjectParams creation
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test Project",
                data_type="image",
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="not_an_email",  # Invalid email format
            )

        # Test invalid email without domain extension
        with pytest.raises(ValidationError):
            CreateProjectParams(
                project_name="Test Project",
                data_type="image",
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by="test@example",  # Invalid email format
            )

    def test_invalid_annotation_guide(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test error handling for invalid annotation guide"""
        # Since annotation templates are now separate objects,
        # we test that empty datasets raise an error
        valid_params = CreateProjectParams(
            project_name="Test Project",
            data_type="image",
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test_user@example.com",
        )

        # Test with empty datasets list
        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, valid_params, [], mock_annotation_template)

        assert "At least one dataset is required" in str(exc_info.value)

    def test_both_upload_methods_specified(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test error when dataset has no files"""
        valid_params = CreateProjectParams(
            project_name="Test Project",
            data_type="image",
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test_user@example.com",
        )

        # Create a dataset with no files
        empty_dataset = Mock(spec=LabellerrDataset)
        empty_dataset.dataset_id = "empty-dataset-id"
        empty_dataset.files_count = 0

        with pytest.raises(LabellerrError) as exc_info:
            create_project(
                client, valid_params, [empty_dataset], mock_annotation_template
            )

        assert "Dataset empty-dataset-id has no files" in str(exc_info.value)

    def test_no_upload_method_specified(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test successful project creation with valid parameters"""
        valid_params = CreateProjectParams(
            project_name="Test Project",
            data_type="image",
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test_user@example.com",
        )

        # Mock the API response
        mock_response = {"response": {"project_id": "test-project-id"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={"project_id": "test-project-id", "data_type": "image"},
            ):
                result = create_project(
                    client, valid_params, [mock_dataset], mock_annotation_template
                )
                assert result is not None

    def test_empty_files_to_upload(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test project creation with multiple datasets"""
        valid_params = CreateProjectParams(
            project_name="Test Project",
            data_type="image",
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by="test_user@example.com",
        )

        # Create multiple datasets
        dataset1 = Mock(spec=LabellerrDataset)
        dataset1.dataset_id = "dataset-1"
        dataset1.files_count = 5

        dataset2 = Mock(spec=LabellerrDataset)
        dataset2.dataset_id = "dataset-2"
        dataset2.files_count = 10

        # Mock the API response
        mock_response = {"response": {"project_id": "test-project-id"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={"project_id": "test-project-id", "data_type": "image"},
            ):
                result = create_project(
                    client, valid_params, [dataset1, dataset2], mock_annotation_template
                )
                assert result is not None

    def test_invalid_folder_to_upload(
        self, client, mock_dataset, mock_annotation_template
    ):
        """Test project creation with AI enabled"""
        valid_params = CreateProjectParams(
            project_name="Test Project",
            data_type="image",
            rotations=RotationConfig(
                annotation_rotation_count=2,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
            use_ai=True,  # Enable AI
            created_by="test_user@example.com",
        )

        # Mock the API response
        mock_response = {"response": {"project_id": "test-project-id"}}

        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.projects.base.LabellerrProject.get_project",
                return_value={"project_id": "test-project-id", "data_type": "image"},
            ):
                result = create_project(
                    client, valid_params, [mock_dataset], mock_annotation_template
                )
                assert result is not None


@pytest.mark.unit
class TestCreateUser:
    """Test cases for create_user method"""

    def test_create_user_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.core.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                # Missing email_id, projects, roles
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_create_user_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.core.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id=12345,  # Not a string
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_create_user_empty_projects(self, users):
        """Test error handling for empty projects list"""
        from labellerr.core.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=[],  # Empty list
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "projects" in str(exc_info.value).lower()

    def test_create_user_empty_roles(self, users):
        """Test error handling for empty roles list"""
        from labellerr.core.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


@pytest.mark.unit
class TestUpdateUserRole:
    """Test cases for update_user_role method"""

    def test_update_user_role_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.core.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, roles
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_update_user_role_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.core.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_update_user_role_empty_roles(self, users):
        """Test error handling for empty roles list"""
        from labellerr.core.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


@pytest.mark.unit
class TestDeleteUser:
    """Test cases for delete_user method"""

    def test_delete_user_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.core.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, user_id
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_delete_user_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.core.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_project_id(self, users):
        """Test error handling for invalid project_id"""
        from labellerr.core.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id=12345,  # Not a string
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "project_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_email_id(self, users):
        """Test error handling for invalid email_id"""
        from labellerr.core.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                email_id=12345,  # Not a string
                user_id="user_123",
            )

        assert "email_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_user_id(self, users):
        """Test error handling for invalid user_id"""
        from labellerr.core.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                user_id=12345,  # Not a string
            )

        assert "user_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestAddUserToProject:
    """Test cases for add_user_to_project method"""

    def test_add_user_to_project_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.add_user_to_project(
                project_id="project_123",
                # Missing email_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_add_user_to_project_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.core.schemas import AddUserToProjectParams

        with pytest.raises(ValidationError) as exc_info:
            AddUserToProjectParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestRemoveUserFromProject:
    """Test cases for remove_user_from_project method"""

    def test_remove_user_from_project_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.remove_user_from_project(
                project_id="project_123",
                # Missing email_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_remove_user_from_project_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.core.schemas import RemoveUserFromProjectParams

        with pytest.raises(ValidationError) as exc_info:
            RemoveUserFromProjectParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestChangeUserRole:
    """Test cases for change_user_role method"""

    def test_change_user_role_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.change_user_role(
                project_id="project_123",
                email_id="john@example.com",
                # Missing new_role_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_change_user_role_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.core.schemas import ChangeUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            ChangeUserRoleParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                new_role_id="7",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestListAndBulkAssignFiles:
    """Tests for list_files and bulk_assign_files methods"""

    def test_list_files_missing_required(self, project):
        """Test list_files with missing required parameters"""
        with pytest.raises(TypeError):
            project.list_files()

    def test_bulk_assign_files_missing_required(self, project):
        """Test bulk_assign_files with missing required parameters"""
        with pytest.raises(TypeError):
            project.bulk_assign_files(new_status="None")


@pytest.mark.unit
class TestBulkAssignFiles:
    """Comprehensive tests for bulk_assign_files method"""

    def test_bulk_assign_files_invalid_client_id_type(self, project):
        """Test error handling for invalid client_id type - validation happens inside method"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_client_id(self, project):
        """Test error handling for empty client_id"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_project_id_type(self, project):
        """Test error handling for invalid project_id type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id=12345,  # Not a string
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_project_id(self, project):
        """Test error handling for empty project_id"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_file_ids_list(self, project):
        """Test error handling for empty file_ids list"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=[],  # Empty list
                new_status="completed",
            )
        assert "file_ids" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_file_ids_type(self, project):
        """Test error handling for invalid file_ids type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids="file1,file2",  # Not a list
                new_status="completed",
            )
        assert "file_ids" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_new_status_type(self, project):
        """Test error handling for invalid new_status type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status=123,  # Not a string
            )
        assert "new_status" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_new_status(self, project):
        """Test error handling for empty new_status"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="",
            )
        assert "new_status" in str(exc_info.value).lower()

    def test_bulk_assign_files_single_file(self, project):
        """Test bulk assign with a single file - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1"],
                new_status="completed",
            )
            assert params.file_ids == ["file1"]
        except ValidationError:
            pytest.fail("Validation should pass for single file")

    def test_bulk_assign_files_multiple_files(self, project):
        """Test bulk assign with multiple files - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2", "file3", "file4", "file5"],
                new_status="in_progress",
            )
            assert len(params.file_ids) == 5
        except ValidationError:
            pytest.fail("Validation should pass for multiple files")

    def test_bulk_assign_files_special_characters_in_ids(self, project):
        """Test bulk assign with special characters in IDs - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="client-123_test",
                project_id="project-456_test",
                file_ids=["file-1_test", "file-2_test"],
                new_status="pending",
            )
            assert params.client_id == "client-123_test"
        except ValidationError:
            pytest.fail("Validation should pass for IDs with special characters")


@pytest.mark.unit
class TestListFiles:
    """Comprehensive tests for list_files method"""

    def test_list_files_invalid_client_id_type(self, project):
        """Test error handling for invalid client_id type - validation happens inside method"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                search_queries={"status": "completed"},
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_list_files_empty_client_id(self, project):
        """Test error handling for empty client_id"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="",
                project_id="project_123",
                search_queries={"status": "completed"},
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_list_files_invalid_project_id_type(self, project):
        """Test error handling for invalid project_id type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id=12345,  # Not a string
                search_queries={"status": "completed"},
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_list_files_empty_project_id(self, project):
        """Test error handling for empty project_id"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="",
                search_queries={"status": "completed"},
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_list_files_invalid_search_queries_type(self, project):
        """Test error handling for invalid search_queries type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries="status:completed",  # Not a dict
            )
        assert "search_queries" in str(exc_info.value).lower()

    def test_list_files_invalid_size_type(self, project):
        """Test error handling for invalid size type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size="invalid",  # Non-numeric string
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_negative_size(self, project):
        """Test error handling for negative size"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=-1,
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_zero_size(self, project):
        """Test error handling for zero size"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=0,
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_with_default_size(self, project):
        """Test list_files with default size parameter - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
            )
            assert params.size == 10  # Default value
        except ValidationError:
            pytest.fail("Validation should pass with default size")

    def test_list_files_with_custom_size(self, project):
        """Test list_files with custom size parameter - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=50,
            )
            assert params.size == 50
        except ValidationError:
            pytest.fail("Validation should pass with custom size")

    def test_list_files_with_next_search_after(self, project):
        """Test list_files with next_search_after for pagination - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=10,
                next_search_after="some_cursor_value",
            )
            assert params.next_search_after == "some_cursor_value"
        except ValidationError:
            pytest.fail("Validation should pass with next_search_after")

    def test_list_files_complex_search_queries(self, project):
        """Test list_files with complex search queries - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={
                    "status": "completed",
                    "created_at": {"gte": "2024-01-01"},
                    "tags": ["tag1", "tag2"],
                },
            )
            assert "status" in params.search_queries
        except ValidationError:
            pytest.fail("Validation should pass with complex search queries")

    def test_list_files_empty_search_queries(self, project):
        """Test list_files with empty search queries dict - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={},  # Empty dict
            )
            assert params.search_queries == {}
        except ValidationError:
            pytest.fail("Validation should pass with empty search queries")


if __name__ == "__main__":
    pytest.main()
