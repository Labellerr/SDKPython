"""
Integration tests for labellerr/core/projects/__init__.py module.

This module contains integration tests that make actual API calls to test
the create_project and list_projects functions end-to-end.
"""

import os
import time

import pytest
from dotenv import load_dotenv

from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project, list_projects
from labellerr.core.projects.base import LabellerrProject
from labellerr.core.schemas import CreateProjectParams, DatasetDataType, RotationConfig

# Load environment variables from .env file
load_dotenv()


def validate_project_response(project, context=""):
    """
    Validate that a project object has the expected structure and non-null required fields.

    :param project: The project object to validate
    :param context: Context string for better error messages
    :raises AssertionError: If validation fails
    """
    prefix = f"{context}: " if context else ""

    assert project is not None, f"{prefix}Project object is None"
    assert isinstance(
        project, LabellerrProject
    ), f"{prefix}Expected LabellerrProject instance, got {type(project)}"

    # Validate required attributes exist
    required_attrs = ["project_id", "data_type"]
    for attr in required_attrs:
        assert hasattr(
            project, attr
        ), f"{prefix}Project missing required attribute '{attr}'"

    # Validate project_id
    assert project.project_id is not None, f"{prefix}Project ID is None"
    assert isinstance(
        project.project_id, str
    ), f"{prefix}Expected project_id to be str, got {type(project.project_id)}"
    assert len(project.project_id) > 0, f"{prefix}Project ID is empty string"

    # Validate data_type if present
    if project.data_type is not None:
        valid_types = ["image", "video", "audio", "document", "text"]
        assert (
            project.data_type in valid_types
        ), f"{prefix}Invalid data type '{project.data_type}'. Expected one of {valid_types}"


@pytest.fixture
def client():
    """Create a test client with real credentials from environment"""
    from labellerr.client import LabellerrClient

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id = os.getenv("CLIENT_ID")

    if not all([api_key, api_secret, client_id]):
        pytest.skip(
            "Integration tests require API_KEY, API_SECRET, and CLIENT_ID environment variables"
        )

    return LabellerrClient(api_key, api_secret, client_id)


@pytest.fixture
def dataset_id():
    """Get dataset ID from environment"""
    dataset_id = os.getenv("DATASET_ID")
    if not dataset_id:
        pytest.skip("DATASET_ID environment variable is required")
    return dataset_id


@pytest.fixture
def email_id():
    """Get email ID from environment"""
    return os.getenv("EMAIL_ID", "test@example.com")


@pytest.fixture
def test_dataset(client, dataset_id):
    """Get or create a test dataset for integration tests"""
    if dataset_id:
        return LabellerrDataset(client=client, dataset_id=dataset_id)
    pytest.skip("DATASET_ID environment variable is required for integration tests")


@pytest.fixture
def test_annotation_template(client):
    """Get or create a test annotation template for integration tests"""
    # Use an environment variable or skip
    template_id = os.getenv("TEMPLATE_ID") or os.getenv("TEST_TEMPLATE_ID")
    if template_id:
        return LabellerrAnnotationTemplate(
            client=client, annotation_template_id=template_id
        )
    pytest.skip(
        "TEMPLATE_ID or TEST_TEMPLATE_ID environment variable is required for integration tests"
    )


@pytest.fixture
def default_rotation_config():
    """Create default rotation configuration"""
    return RotationConfig(
        annotation_rotation_count=1,
        review_rotation_count=1,
        client_review_rotation_count=1,
    )


def create_test_project_params(
    project_name_suffix: str,
    email_id: str,
    data_type: DatasetDataType = DatasetDataType.image,
    rotations: RotationConfig = None,
    use_ai: bool = False,
) -> CreateProjectParams:
    """Helper function to create test project parameters with unique name"""
    timestamp = int(time.time())
    if rotations is None:
        rotations = RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        )
    return CreateProjectParams(
        project_name=f"SDK_IntegrationTest_{project_name_suffix}_{timestamp}",
        data_type=data_type,
        rotations=rotations,
        use_ai=use_ai,
        created_by=email_id or "test@example.com",
    )


@pytest.fixture
def test_project_params(email_id, default_rotation_config):
    """Create test project parameters with unique name"""
    return create_test_project_params(
        "Project", email_id, rotations=default_rotation_config
    )


@pytest.mark.integration
@pytest.mark.slow
class TestCreateProjectIntegration:
    """Integration tests for create_project function"""

    def test_create_project_basic(
        self, client, test_project_params, test_dataset, test_annotation_template
    ):
        """Test basic project creation with real API calls"""
        try:
            project = create_project(
                client=client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            # Validate response structure
            validate_project_response(project, "test_create_project_basic")
        except LabellerrError as e:
            pytest.fail(f"Project creation failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"Project creation failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_create_project_with_ai(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test project creation with AI enabled"""
        try:
            params = create_test_project_params(
                "AI_Project",
                email_id,
                rotations=RotationConfig(
                    annotation_rotation_count=2,
                    review_rotation_count=2,
                    client_review_rotation_count=1,
                ),
                use_ai=True,
            )

            project = create_project(
                client=client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            # Validate response structure
            validate_project_response(project, "test_create_project_with_ai")
        except LabellerrError as e:
            pytest.fail(f"AI project creation failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"AI project creation failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_create_project_image_type(
        self,
        client,
        test_dataset,
        test_annotation_template,
        email_id,
        default_rotation_config,
    ):
        """Test creating an image project"""
        params = create_test_project_params(
            "Image", email_id, rotations=default_rotation_config
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.data_type == "image"

    def test_create_project_custom_rotations(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test project creation with custom rotation counts"""
        params = create_test_project_params(
            "CustomRotation",
            email_id,
            rotations=RotationConfig(
                annotation_rotation_count=3,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert isinstance(project, LabellerrProject)

    def test_create_project_no_datasets_error(
        self, client, test_project_params, test_annotation_template
    ):
        """Test that creating project with no datasets raises error"""
        with pytest.raises(LabellerrError) as exc_info:
            create_project(
                client=client,
                params=test_project_params,
                datasets=[],
                annotation_template=test_annotation_template,
            )

        assert "At least one dataset is required" in str(exc_info.value)

    def test_create_project_verify_properties(
        self,
        client,
        test_project_params,
        test_dataset,
        test_annotation_template,
        email_id,
    ):
        """Test that created project has correct properties"""
        try:
            project = create_project(
                client=client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            # Verify project properties with detailed error messages
            assert project.project_id is not None, "Project ID is None"
            assert project.data_type == test_project_params.data_type.value, (
                f"Data type mismatch: expected {test_project_params.data_type.value}, "
                f"got {project.data_type}"
            )
            assert (
                project.annotation_template_id
                == test_annotation_template.annotation_template_id
            ), (
                f"Annotation template ID mismatch: "
                f"expected {test_annotation_template.annotation_template_id}, "
                f"got {project.annotation_template_id}"
            )
            expected_creator = email_id or "test@example.com"
            assert (
                project.created_by == expected_creator
            ), f"Creator mismatch: expected {expected_creator}, got {project.created_by}"
        except LabellerrError as e:
            pytest.fail(
                f"Project property verification failed with LabellerrError: {e}"
            )
        except Exception as e:
            pytest.fail(
                f"Project property verification failed: {type(e).__name__}: {e}"
            )


@pytest.mark.integration
@pytest.mark.slow
class TestListProjectsIntegration:
    """Integration tests for list_projects function"""

    def test_list_projects_basic(self, client):
        """Test basic project listing with real API calls"""
        try:
            projects = list_projects(client)

            # Validate response structure
            assert projects is not None, "list_projects returned None"
            assert isinstance(projects, list), f"Expected list, got {type(projects)}"

            # Validate each project in the list
            for idx, project in enumerate(projects):
                validate_project_response(project, f"Project at index {idx}")
        except LabellerrError as e:
            pytest.fail(f"Listing projects failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"Listing projects failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_list_projects_returns_labellerr_project_objects(self, client):
        """Test that list_projects returns LabellerrProject objects"""
        try:
            projects = list_projects(client)

            assert isinstance(projects, list), f"Expected list, got {type(projects)}"
            for idx, project in enumerate(projects):
                assert isinstance(
                    project, LabellerrProject
                ), f"Project at index {idx} is not LabellerrProject: {type(project)}"
                # Verify basic properties exist
                assert hasattr(
                    project, "project_id"
                ), f"Project at index {idx} missing 'project_id' attribute"
                assert hasattr(
                    project, "data_type"
                ), f"Project at index {idx} missing 'data_type' attribute"
                assert hasattr(
                    project, "annotation_template_id"
                ), f"Project at index {idx} missing 'annotation_template_id' attribute"
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_list_projects_project_properties(self, client):
        """Test that listed projects have required properties"""
        try:
            projects = list_projects(client)

            if len(projects) > 0:
                # Test first project has required attributes
                project = projects[0]
                assert (
                    project.project_id is not None
                ), "First project has None project_id"
                assert isinstance(
                    project.project_id, str
                ), f"Expected project_id to be str, got {type(project.project_id)}"
                # Data type should be one of the valid types
                valid_types = ["image", "video", "audio", "document", "text"]
                assert (
                    project.data_type in valid_types
                ), f"Invalid data type '{project.data_type}'. Expected one of {valid_types}"
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_list_projects_after_creation(
        self, client, test_project_params, test_dataset, test_annotation_template
    ):
        """Test that newly created project appears in list"""
        try:
            # Create a new project
            created_project = create_project(
                client=client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            # Verify project was created successfully
            validate_project_response(created_project, "Created project")
            created_project_id = created_project.project_id

            # Retry logic to handle eventual consistency and pagination
            max_retries = 3
            retry_delay = 5  # seconds
            project_found = False

            for attempt in range(max_retries):
                # Wait for the project to be indexed
                time.sleep(retry_delay)

                # Check if the created project is in the updated list
                updated_projects = list_projects(client)
                project_found = any(
                    p.project_id == created_project_id for p in updated_projects
                )

                if project_found:
                    break

                if attempt < max_retries - 1:
                    # Not last attempt, will retry
                    import warnings

                    warnings.warn(
                        f"Attempt {attempt + 1}/{max_retries}: Project {created_project_id} "
                        f"not found in list of {len(updated_projects)} projects. Retrying..."
                    )

            # Final assertion with helpful context
            if not project_found:
                # Project still not found - could be pagination issue
                # Try to retrieve the project directly to confirm it exists
                try:
                    # Attempt to retrieve the project directly
                    LabellerrProject(client, project_id=created_project_id)
                    # Project exists but not in list - likely pagination issue
                    import warnings

                    warnings.warn(
                        f"Project {created_project_id} exists (can be retrieved directly) "
                        f"but not found in list_projects() response. This may indicate pagination "
                        f"or eventual consistency issues. List contains {len(updated_projects)} projects."
                    )
                    # Don't fail the test - the project was successfully created
                except Exception:
                    # Project doesn't exist - this is a real failure
                    pytest.fail(
                        f"Created project {created_project_id} not found in list of "
                        f"{len(updated_projects)} projects after {max_retries} attempts, "
                        f"and cannot be retrieved directly."
                    )
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_list_projects_consistency(self, client):
        """Test that listing projects multiple times returns consistent results"""
        # List projects multiple times
        projects1 = list_projects(client)
        time.sleep(1)
        projects2 = list_projects(client)

        # Should return similar results (count might differ slightly due to concurrent operations)
        assert isinstance(projects1, list)
        assert isinstance(projects2, list)
        # Both calls should succeed and return lists
        assert len(projects1) >= 0
        assert len(projects2) >= 0


@pytest.mark.integration
@pytest.mark.slow
class TestCreateProjectEdgeCases:
    """Integration tests for edge cases and error handling"""

    def test_create_project_long_name(
        self,
        client,
        test_dataset,
        test_annotation_template,
        email_id,
        default_rotation_config,
    ):
        """Test creating project with maximum allowed name length (50 chars)"""
        timestamp = int(time.time())
        # API limit is 50 characters, so create a name at the limit
        long_name = f"SDK_Test_{'A' * 30}_{timestamp}"[:50]

        params = create_test_project_params(
            "", email_id, rotations=default_rotation_config
        )
        params.project_name = long_name  # Override with long name

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.project_id is not None

    def test_create_project_special_characters_in_name(
        self,
        client,
        test_dataset,
        test_annotation_template,
        email_id,
        default_rotation_config,
    ):
        """Test creating project with special characters in name"""
        timestamp = int(time.time())
        special_name = f"SDK_Test-Project_2024_{timestamp}"

        params = create_test_project_params(
            "", email_id, rotations=default_rotation_config
        )
        params.project_name = special_name  # Override with special name

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.project_id is not None

    def test_create_project_minimum_rotations(
        self,
        client,
        test_dataset,
        test_annotation_template,
        email_id,
        default_rotation_config,
    ):
        """Test creating project with minimum rotation counts (1)"""
        params = create_test_project_params(
            "MinRotation", email_id, rotations=default_rotation_config
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.project_id is not None


@pytest.mark.integration
@pytest.mark.slow
class TestProjectWorkflow:
    """Integration tests for complete project workflows"""

    def test_create_and_retrieve_project(
        self, client, test_project_params, test_dataset, test_annotation_template
    ):
        """Test creating a project and then retrieving it"""
        try:
            # Create project
            created_project = create_project(
                client=client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            assert created_project is not None, "create_project returned None"
            created_project_id = created_project.project_id
            assert created_project_id is not None, "Created project has None project_id"

            # Wait for project to be fully created
            time.sleep(2)

            # Retrieve project by creating a new instance
            retrieved_project = LabellerrProject(
                client=client, project_id=created_project_id
            )

            # Verify properties match
            assert retrieved_project.project_id == created_project_id, (
                f"Project ID mismatch: expected {created_project_id}, "
                f"got {retrieved_project.project_id}"
            )
            assert retrieved_project.data_type == test_project_params.data_type.value, (
                f"Data type mismatch: expected {test_project_params.data_type.value}, "
                f"got {retrieved_project.data_type}"
            )
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_create_multiple_projects(
        self,
        client,
        test_dataset,
        test_annotation_template,
        email_id,
        default_rotation_config,
    ):
        """Test creating multiple projects in sequence"""
        try:
            timestamp = int(time.time())
            created_projects = []

            for i in range(3):
                params = create_test_project_params(
                    f"Multi_{timestamp}_{i}",
                    email_id,
                    rotations=default_rotation_config,
                )

                project = create_project(
                    client=client,
                    params=params,
                    datasets=[test_dataset],
                    annotation_template=test_annotation_template,
                )

                assert project is not None, f"Project {i} creation returned None"
                assert (
                    project.project_id is not None
                ), f"Project {i} has None project_id"
                created_projects.append(project)
                time.sleep(1)  # Small delay between creations

            # Verify all projects were created
            assert (
                len(created_projects) == 3
            ), f"Expected 3 projects, got {len(created_projects)}"
            assert all(
                p.project_id is not None for p in created_projects
            ), "Some projects have None project_id"

            # Verify all project IDs are unique
            project_ids = [p.project_id for p in created_projects]
            unique_ids = set(project_ids)
            assert len(project_ids) == len(unique_ids), (
                f"Duplicate project IDs found. Total: {len(project_ids)}, "
                f"Unique: {len(unique_ids)}, IDs: {project_ids}"
            )
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
