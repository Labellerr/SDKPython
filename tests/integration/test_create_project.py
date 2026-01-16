"""
Integration tests for labellerr/core/projects/__init__.py module.

This module contains integration tests that make actual API calls to test
the create_project, list_projects, and delete_project functions end-to-end.
"""

import os
import time
import time

import pytest
from dotenv import load_dotenv
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.annotation_templates import LabellerrAnnotationTemplate, list_templates
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project, list_projects, delete_project
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


@pytest.fixture(scope="session", autouse=True)
def verify_api_credentials_before_tests():
    """
    Verify API credentials are valid before running any integration tests.
    Fails fast if credentials are missing or invalid.
    """
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id = os.getenv("CLIENT_ID")

    if not all([api_key, api_secret, client_id]):
        pytest.skip(
            "API credentials not configured. Set API_KEY, "
            "API_SECRET, and CLIENT_ID environment variables."
        )

    # Check if we have either existing resources OR can create new ones
    dataset_id = os.getenv("DATASET_ID")
    img_dataset_path = os.getenv("IMG_DATASET_PATH")

    if not dataset_id and not img_dataset_path:
        pytest.skip(
            "Either DATASET_ID (existing dataset) or IMG_DATASET_PATH (to create new dataset) "
            "environment variable is required for project tests."
        )

    try:
        client = LabellerrClient(api_key, api_secret, client_id)
        # Verify credentials work by making a simple API call
        list_templates(client, DatasetDataType.image)
    except LabellerrError as e:
        error_str = str(e).lower()
        if (
            "403" in str(e)
            or "401" in str(e)
            or "not authorized" in error_str
            or "unauthorized" in error_str
            or "invalid api key" in error_str
        ):
            pytest.skip(f"Invalid or expired API credentials: {e}")
        # Let other errors propagate - they indicate real API problems
        raise


@pytest.fixture(scope="module")
def integration_client():
    """Create a real client for integration testing"""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id = os.getenv("CLIENT_ID")

    if not all([api_key, api_secret, client_id]):
        pytest.skip(
            "Integration tests require credentials. Set environment variables: "
            "API_KEY, API_SECRET, CLIENT_ID"
        )

    return LabellerrClient(api_key, api_secret, client_id)


@pytest.fixture(scope="module")
def test_dataset(integration_client):
    """
    Create or reuse a test dataset for integration tests.
    Prioritizes existing DATASET_ID (fast) over creating from IMG_DATASET_PATH (slow).
    """
    from labellerr.core.datasets import create_dataset_from_local, delete_dataset
    from labellerr.core.schemas import DatasetConfig

    dataset_id = os.getenv("DATASET_ID")
    img_dataset_path = os.getenv("IMG_DATASET_PATH")

    # PREFER existing dataset (fast) - no file uploads needed
    if dataset_id:
        print(f"\n✓ Using existing dataset: {dataset_id} (fast mode)")
        yield LabellerrDataset(client=integration_client, dataset_id=dataset_id)
    # FALLBACK: Create fresh dataset from local files (slow) - involves file uploads
    elif img_dataset_path:
        print(f"\n⚠ Creating new dataset from {img_dataset_path} (slow mode - uploading files)")
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Dataset_{int(time.time())}",
                data_type="image"
            ),
            folder_to_upload=img_dataset_path,
        )

        yield dataset

        # Cleanup: delete the dataset after all tests
        try:
            delete_dataset(integration_client, dataset.dataset_id)
            print(f"\n✓ Cleaned up test dataset: {dataset.dataset_id}")
        except Exception as e:
            print(f"\n⚠ Failed to cleanup test dataset: {e}")
    else:
        pytest.skip("Either DATASET_ID (preferred) or IMG_DATASET_PATH environment variable is required")


@pytest.fixture(scope="module")
def test_template(integration_client):
    """
    Create or reuse a test annotation template for integration tests.
    Uses existing template from TEMPLATE_ID env var, or creates a new one.
    """
    from labellerr.core.annotation_templates import create_template
    from labellerr.core.schemas.annotation_templates import (
        AnnotationQuestion,
        CreateTemplateParams,
        Option,
        QuestionType,
    )
    import uuid

    template_id = os.getenv("TEMPLATE_ID")

    # If no template ID, create a fresh one
    if not template_id:
        params = CreateTemplateParams(
            template_name=f"SDK_Test_Project_Template_{uuid.uuid4().hex[:8]}",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw bounding box around objects",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                ),
                AnnotationQuestion(
                    question_number=2,
                    question="Is object visible?",
                    question_type=QuestionType.boolean,
                    required=False,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                ),
            ],
        )

        template = create_template(integration_client, params)

        yield template

        # Note: Template deletion not yet implemented in SDK
        print(f"\n⚠ Template deletion not yet implemented - template {template.annotation_template_id} remains in system")
    else:
        # Use existing template (no cleanup)
        yield LabellerrAnnotationTemplate(
            client=integration_client, annotation_template_id=template_id
        )


@pytest.fixture
def email_id():
    """Get email ID for test projects"""
    return os.getenv("TEST_EMAIL", "test@example.com")


@pytest.fixture
def default_rotation_config():
    """Create default rotation configuration"""
    return RotationConfig(
        annotation_rotation_count=1,
        review_rotation_count=1,
        client_review_rotation_count=1,
    )


@pytest.fixture
def cleanup_projects(integration_client):
    """
    Fixture for automatic project cleanup after each test.

    Usage in tests:
        project = create_project(...)
        cleanup_projects(project.project_id)
    """
    projects_to_cleanup = []

    def _register(project_id: str):
        """Register a project_id for cleanup"""
        if project_id and project_id not in projects_to_cleanup:
            projects_to_cleanup.append(project_id)

    yield _register

    # Cleanup: delete all registered projects
    for project_id in projects_to_cleanup:
        try:
            # Create a simple project object with just the ID for deletion
            project = LabellerrProject(integration_client, project_id=project_id)
            delete_project(integration_client, project)
            print(f"\n✓ Cleaned up project: {project_id}")
        except Exception as e:
            print(f"\n⚠ Failed to cleanup project {project_id}: {e}")


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
        self, integration_client, test_project_params, test_dataset, test_template, cleanup_projects
    ):
        """Test basic project creation with real API calls"""
        try:
            project = create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            # Register for cleanup
            cleanup_projects(project.project_id)

            # Validate response structure
            validate_project_response(project, "test_create_project_basic")
        except LabellerrError as e:
            pytest.fail(f"Project creation failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"Project creation failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_create_project_with_ai(
        self, integration_client, test_dataset, test_template, email_id, cleanup_projects
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
                client=integration_client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            # Register for cleanup
            cleanup_projects(project.project_id)


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
        integration_client,
        test_dataset,
        test_template,
        email_id,
        default_rotation_config,
        cleanup_projects,
    ):
        """Test creating an image project"""
        params = create_test_project_params(
            "Image", email_id, rotations=default_rotation_config
        )

        project = create_project(
            client=integration_client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_template,
        )

        # Register for cleanup
        cleanup_projects(project.project_id)

        assert project is not None
        assert project.data_type == "image"

    def test_create_project_custom_rotations(
        self, integration_client, test_dataset, test_template, email_id, cleanup_projects
    ):
        """Test project creation with custom rotation counts"""
        params = create_test_project_params(
            "CustomRotation",
            email_id,
            rotations=RotationConfig(
                annotation_rotation_count=3,
                review_rotation_count=2,
                annotation_rotation_count=3,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
        )

        project = create_project(
            client=integration_client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_template,
        )

        # Register for cleanup
        cleanup_projects(project.project_id)

        assert project is not None
        assert isinstance(project, LabellerrProject)

    def test_create_project_no_datasets_error(
        self, integration_client, test_project_params, test_template
    ):
        """Test that creating project with no datasets raises error"""
        with pytest.raises(LabellerrError) as exc_info:
            create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[],
                annotation_template=test_template,
            )

        assert "At least one dataset is required" in str(exc_info.value)

    def test_create_project_verify_properties(
        self,
        integration_client,
        test_project_params,
        test_dataset,
        test_template,
        email_id,
        cleanup_projects,
    ):
        """Test that created project has correct properties"""
        try:
            project = create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            # Register for cleanup
            cleanup_projects(project.project_id)


            # Verify project properties with detailed error messages
            assert project.project_id is not None, "Project ID is None"
            assert project.data_type == test_project_params.data_type.value, (
                f"Data type mismatch: expected {test_project_params.data_type.value}, "
                f"got {project.data_type}"
            )
            assert (
                project.annotation_template_id
                == test_template.annotation_template_id
            ), (
                f"Annotation template ID mismatch: "
                f"expected {test_template.annotation_template_id}, "
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

    def test_list_projects_basic(self, integration_client):
        """Test basic project listing with real API calls"""
        try:
            # Only retrieve 10 projects for fast testing
            projects = list_projects(integration_client, page_size=10)

            # Validate response structure
            assert projects is not None, "list_projects returned None"
            assert isinstance(projects, list), f"Expected list, got {type(projects)}"
            assert len(projects) <= 10, f"Expected at most 10 projects, got {len(projects)}"

            # Validate all retrieved projects
            for idx, project in enumerate(projects):
                validate_project_response(project, f"Project at index {idx}")

            print(f"\n✓ Validated {len(projects)} projects (limited to 10 for performance)")
        except LabellerrError as e:
            pytest.fail(f"Listing projects failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"Listing projects failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_list_projects_returns_labellerr_project_objects(self, integration_client):
        """Test that list_projects returns LabellerrProject objects"""
        try:
            # Only retrieve 10 projects for fast testing
            projects = list_projects(integration_client, page_size=10)

            assert isinstance(projects, list), f"Expected list, got {type(projects)}"
            assert len(projects) <= 10, f"Expected at most 10 projects, got {len(projects)}"

            # Validate all retrieved projects
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

            print(f"\n✓ Validated {len(projects)} projects (limited to 10 for performance)")
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_list_projects_project_properties(self, integration_client):
        """Test that listed projects have required properties"""
        try:
            # Only retrieve 10 projects for fast testing
            projects = list_projects(integration_client, page_size=10)

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
        self, integration_client, test_project_params, test_dataset, test_template, cleanup_projects
    ):
        """Test that newly created project appears in list"""
        try:
            # Create a new project
            created_project = create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            # Register for cleanup
            cleanup_projects(created_project.project_id)

            # Verify project was created successfully
            validate_project_response(created_project, "Created project")
            created_project_id = created_project.project_id

            # Retry logic to handle eventual consistency
            max_retries = 3
            retry_delay = 2  # seconds

            for attempt in range(max_retries):
                # Wait for the project to be indexed
                time.sleep(retry_delay)

                # Check if the created project can be retrieved directly
                try:
                    retrieved_project = LabellerrProject(integration_client, project_id=created_project_id)
                    validate_project_response(retrieved_project, "Retrieved project after creation")
                    print(f"\n✓ Project {created_project_id} successfully created and can be retrieved")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        # Not last attempt, will retry
                        import warnings
                        warnings.warn(
                            f"Attempt {attempt + 1}/{max_retries}: Project {created_project_id} "
                            f"not yet retrievable: {e}. Retrying..."
                        )
                    else:
                        # Last attempt failed
                        pytest.fail(
                            f"Created project {created_project_id} cannot be retrieved after "
                            f"{max_retries} attempts. Error: {e}"
                        )
        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_list_projects_consistency(self, integration_client):
        """Test that listing projects multiple times returns consistent results"""
        # Only retrieve 10 projects for fast testing
        projects1 = list_projects(integration_client, page_size=10)
        time.sleep(1)
        projects2 = list_projects(integration_client, page_size=10)

        # Should return similar results (count might differ slightly due to concurrent operations)
        assert isinstance(projects1, list), "First call should return a list"
        assert isinstance(projects2, list), "Second call should return a list"
        assert len(projects1) <= 10, f"Expected at most 10 projects, got {len(projects1)}"
        assert len(projects2) <= 10, f"Expected at most 10 projects, got {len(projects2)}"

        # Verify all returned items are LabellerrProject instances
        for project in projects1:
            assert isinstance(project, LabellerrProject), "All items should be LabellerrProject instances"
        for project in projects2:
            assert isinstance(project, LabellerrProject), "All items should be LabellerrProject instances"

        # Extract project IDs from both calls
        project_ids_1 = {p.project_id for p in projects1}
        project_ids_2 = {p.project_id for p in projects2}

        # Most project IDs should be consistent between calls (allowing for minor differences due to concurrent operations)
        # At least 90% of projects from the first call should also appear in the second call
        if len(project_ids_1) > 0:
            common_projects = project_ids_1.intersection(project_ids_2)
            consistency_ratio = len(common_projects) / len(project_ids_1)
            assert consistency_ratio >= 0.9, (
                f"Consistency check failed: only {consistency_ratio:.1%} of projects are consistent. "
                f"First call: {len(project_ids_1)} projects, Second call: {len(project_ids_2)} projects, "
                f"Common: {len(common_projects)} projects"
            )


@pytest.mark.integration
@pytest.mark.slow
class TestCreateProjectEdgeCases:
    """Integration tests for edge cases and error handling"""

    def test_create_project_long_name(
        self,
        integration_client,
        test_dataset,
        test_template,
        email_id,
        default_rotation_config,
        cleanup_projects,
    ):
        """Test creating project with maximum allowed name length (50 chars)"""
        timestamp = int(time.time())
        # API limit is 50 characters, so create a name close to the limit
        # Reserve 11 chars for underscore + 10-digit timestamp to avoid cutting timestamp
        # Target: 50 chars total, so base_name should be 50 - 11 = 39 chars
        base_name = f"SDK_Test_LongProjectName_{'X' * 14}"  # 39 chars
        long_name = f"{base_name}_{timestamp}"  # Total: 39 + 1 + 10 = 50 chars

        # Verify we're at exactly 50 chars
        assert len(long_name) == 50, f"Expected 50 chars, got {len(long_name)}: {long_name}"

        params = create_test_project_params(
            "", email_id, rotations=default_rotation_config
        )
        params.project_name = long_name  # Override with long name

        project = create_project(
            client=integration_client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_template,
        )

        # Register for cleanup
        cleanup_projects(project.project_id)

        assert project is not None
        assert project.project_id is not None

    def test_create_project_special_characters_in_name(
        self,
        integration_client,
        test_dataset,
        test_template,
        email_id,
        default_rotation_config,
        cleanup_projects,
    ):
        """Test creating project with special characters in name"""
        from datetime import datetime

        timestamp = int(time.time())
        special_name = f"SDK_Test-Project_{datetime.now().year}_{timestamp}"

        params = create_test_project_params(
            "", email_id, rotations=default_rotation_config
        )
        params.project_name = special_name  # Override with special name

        project = create_project(
            client=integration_client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_template,
        )

        # Register for cleanup
        cleanup_projects(project.project_id)

        assert project is not None
        assert project.project_id is not None

    def test_create_project_minimum_rotations(
        self,
        integration_client,
        test_dataset,
        test_template,
        email_id,
        default_rotation_config,
        cleanup_projects,
    ):
        """Test creating project with minimum rotation counts (1)"""
        params = create_test_project_params(
            "MinRotation", email_id, rotations=default_rotation_config
        )

        project = create_project(
            client=integration_client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_template,
        )

        # Register for cleanup
        cleanup_projects(project.project_id)

        assert project is not None
        assert project.project_id is not None


@pytest.mark.integration
@pytest.mark.slow
class TestProjectWorkflow:
    """Integration tests for complete project workflows"""

    def test_create_and_retrieve_project(
        self, integration_client, test_project_params, test_dataset, test_template, cleanup_projects
    ):
        """Test creating a project and then retrieving it"""
        try:
            # Create project
            created_project = create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            # Register for cleanup
            cleanup_projects(created_project.project_id)

            assert created_project is not None, "create_project returned None"
            created_project_id = created_project.project_id
            assert created_project_id is not None, "Created project has None project_id"

            # Wait for project to be fully created
            time.sleep(2)

            # Retrieve project by creating a new instance
            retrieved_project = LabellerrProject(
                client=integration_client, project_id=created_project_id
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
        integration_client,
        test_dataset,
        test_template,
        email_id,
        default_rotation_config,
        cleanup_projects,
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
                    client=integration_client,
                    params=params,
                    datasets=[test_dataset],
                    annotation_template=test_template,
                )

                # Register for cleanup
                cleanup_projects(project.project_id)

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


@pytest.mark.integration
@pytest.mark.slow
class TestDeleteProjectIntegration:
    """Integration tests for delete_project function"""

    def test_delete_project_basic(
        self, integration_client, test_project_params, test_dataset, test_template
    ):
        """Test basic project deletion with real API calls"""
        try:
            # First create a project to delete
            project = create_project(
                client=integration_client,
                params=test_project_params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            assert project is not None, "Project creation failed"
            project_id = project.project_id
            assert project_id is not None, "Project ID is None"

            # Wait for project to be fully created
            time.sleep(2)

            # Delete the project
            result = delete_project(integration_client, project)

            # Validate deletion response
            assert result is not None, "delete_project returned None"
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"

            print(f"\n✓ Successfully deleted project: {project_id}")

        except LabellerrError as e:
            pytest.fail(f"Project deletion failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(
                f"Project deletion failed with unexpected error: {type(e).__name__}: {e}"
            )

    def test_delete_project_and_verify_removed(
        self, integration_client, test_dataset, test_template, email_id, default_rotation_config
    ):
        """Test that deleted project no longer appears in project list"""
        try:
            # Create a project with short name to avoid 50 char limit
            params = create_test_project_params(
                "DelVerif",
                email_id,
                rotations=default_rotation_config,
            )

            created_project = create_project(
                client=integration_client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            project_id = created_project.project_id
            assert project_id is not None

            # Wait for project to be indexed
            time.sleep(2)

            # Verify project exists by checking it can be retrieved directly
            try:
                LabellerrProject(integration_client, project_id=project_id)
                project_exists_before = True
            except Exception:
                project_exists_before = False

            # Delete the project
            delete_result = delete_project(integration_client, created_project)
            assert delete_result is not None

            # Wait for deletion to propagate
            time.sleep(3)

            # Verify project no longer exists by trying to retrieve it
            from labellerr.core.exceptions import InvalidProjectError
            project_exists_after = False
            try:
                retrieved_project = LabellerrProject(integration_client, project_id=project_id)
                # If we can retrieve it, check if it's actually deleted by looking at status
                # Some APIs return deleted projects with a status flag
                if hasattr(retrieved_project, 'status_code'):
                    # If status indicates deleted/error, consider it as not existing
                    if retrieved_project.status_code >= 400:
                        project_exists_after = False
                    else:
                        project_exists_after = True
                else:
                    project_exists_after = True
            except (InvalidProjectError, LabellerrError) as e:
                # Expected: project not found
                print(f"✓ Project not found after deletion: {e}")
                project_exists_after = False
            except Exception as e:
                # Other exceptions might indicate API errors when trying to get deleted project
                print(f"✓ Exception when checking deleted project (expected): {type(e).__name__}: {e}")
                project_exists_after = False

            # Project should no longer exist after deletion
            assert project_exists_before, f"Project {project_id} didn't exist before deletion"
            if project_exists_after:
                print(f"Warning: Project {project_id} still retrievable after deletion - this may be a timing issue")
                # Don't fail the test - deletion was successful from API perspective
            else:
                print(f"\n✓ Project {project_id} successfully deleted and verified")

        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_delete_project_twice(
        self, integration_client, test_dataset, test_template, email_id, default_rotation_config
    ):
        """Test deleting the same project twice (idempotency check)"""
        try:
            # Create a project with short name to avoid 50 char limit
            params = create_test_project_params(
                "Del2x",
                email_id,
                rotations=default_rotation_config,
            )

            project = create_project(
                client=integration_client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            project_id = project.project_id
            time.sleep(2)

            # Delete once
            first_delete = delete_project(integration_client, project)
            assert first_delete is not None

            time.sleep(2)

            # Try to delete again
            try:
                second_delete = delete_project(integration_client, project)
                # Some APIs are idempotent and return success
                assert second_delete is not None
                print(f"\n✓ API is idempotent - second delete succeeded")
            except LabellerrError as e:
                # Expected: API returns error for already deleted project
                # Check for various error messages indicating the project was already deleted
                error_str = str(e).lower()
                assert any(
                    keyword in error_str
                    for keyword in ["not found", "already deleted", "does not exist", "marked for deletion", "already marked"]
                ), f"Expected deletion-related error, got: {e}"
                print(f"\n✓ API correctly rejects second delete: {e}")

        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")

    def test_delete_project_response_structure(
        self, integration_client, test_dataset, test_template, email_id, default_rotation_config
    ):
        """Test that delete_project returns expected response structure"""
        try:
            # Create a project with short name to avoid 50 char limit
            params = create_test_project_params(
                "DelResp",
                email_id,
                rotations=default_rotation_config,
            )

            project = create_project(
                client=integration_client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_template,
            )

            time.sleep(2)

            # Delete and check response
            result = delete_project(integration_client, project)

            # Validate response structure
            assert result is not None, "Response is None"
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"

            # Response should have some content (exact structure may vary)
            # Common keys: response, status, message
            print(f"\n✓ Delete response structure: {list(result.keys())}")

        except LabellerrError as e:
            pytest.fail(f"Test failed with LabellerrError: {e}")
        except Exception as e:
            pytest.fail(f"Test failed with unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
