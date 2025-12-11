"""
Integration tests for the Labellerr MCP Server

These tests verify the complete workflow using the SDK core implementation:
1. Dataset creation with file uploads
2. Annotation template creation
3. Project creation linking dataset and template
4. Listing and querying operations

Run these tests with: python tests/integration/run_mcp_integration_tests.py
"""

import os
import pytest
import uuid
from dotenv import load_dotenv

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Skip entire module if SDK core dependencies are not installed
try:
    from labellerr.core import LabellerrClient
    from labellerr.core import datasets as dataset_ops
    from labellerr.core import projects as project_ops
    from labellerr.core import annotation_templates as template_ops
    from labellerr.core.datasets import LabellerrDataset
    from labellerr.core.datasets.base import LabellerrDatasetMeta
    from labellerr.core.datasets.utils import upload_folder_files_to_dataset
    from labellerr.core.projects import LabellerrProject
    from labellerr.core.projects.base import LabellerrProjectMeta
    from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
    from labellerr.core import schemas
    from labellerr.core.schemas.annotation_templates import (
        CreateTemplateParams,
        AnnotationQuestion,
        QuestionType,
        Option,
    )
    from labellerr.core import constants

    SDK_AVAILABLE = True
except ImportError as e:
    SDK_AVAILABLE = False
    pytest.skip(
        f"SDK core dependencies not installed: {e}. Install with: pip install -e '.[dev]'",
        allow_module_level=True,
    )

# Load environment variables
load_dotenv()


@pytest.fixture(scope="session")
def credentials():
    """Load API credentials from environment"""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id = os.getenv("CLIENT_ID")
    test_data_path = os.getenv("LABELLERR_TEST_DATA_PATH")

    if not all([api_key, api_secret, client_id]):
        pytest.skip(
            "Missing required environment variables (API_KEY, API_SECRET, CLIENT_ID)"
        )

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "client_id": client_id,
        "test_data_path": test_data_path,
    }


@pytest.fixture(scope="session")
def sdk_client(credentials):
    """Create SDK client instance"""
    client = LabellerrClient(
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        client_id=credentials["client_id"],
    )

    yield client

    # Cleanup
    client.close()


@pytest.fixture(scope="session")
def test_dataset_id(sdk_client, credentials):
    """Create a test dataset and return its ID"""
    test_data_path = credentials.get("test_data_path")

    if not test_data_path or not os.path.exists(test_data_path):
        pytest.skip("Test data path not provided or does not exist")

    # Upload files and create dataset
    upload_result = upload_folder_files_to_dataset(
        sdk_client,
        {
            "client_id": credentials["client_id"],
            "folder_path": test_data_path,
            "data_type": "image",
        },
    )
    connection_id = upload_result.get("connection_id")

    dataset_config = schemas.DatasetConfig(
        dataset_name=f"MCP Test Dataset {uuid.uuid4().hex[:8]}",
        data_type="image",
        dataset_description="Created by MCP integration tests",
    )

    dataset = dataset_ops.create_dataset_from_connection(
        sdk_client, dataset_config, connection_id, "local"
    )

    dataset_id = dataset.dataset_id

    yield dataset_id

    # Cleanup - delete dataset after tests
    try:
        dataset_ops.delete_dataset(sdk_client, dataset_id)
    except Exception as e:
        print(f"Warning: Failed to cleanup dataset {dataset_id}: {e}")


@pytest.fixture(scope="session")
def test_template_id(sdk_client):
    """Create a test annotation template and return its ID"""
    template_name = f"MCP Test Template {uuid.uuid4().hex[:8]}"

    questions = [
        AnnotationQuestion(
            question_number=1,
            question="Object",
            question_id=str(uuid.uuid4()),
            question_type=QuestionType.bounding_box,
            required=True,
            options=[Option(option_name="#FF0000")],
            color="#FF0000",
        )
    ]

    params = CreateTemplateParams(
        template_name=template_name, data_type="image", questions=questions
    )

    template = template_ops.create_template(sdk_client, params)
    return template.annotation_template_id


@pytest.fixture(scope="session")
def test_project_id(sdk_client, test_dataset_id, test_template_id):
    """Create a test project and return its ID"""
    project_name = f"MCP Test Project {uuid.uuid4().hex[:8]}"

    rotations = schemas.RotationConfig(
        annotation_rotation_count=1,
        review_rotation_count=1,
        client_review_rotation_count=1,
    )

    params = schemas.CreateProjectParams(
        project_name=project_name,
        data_type="image",
        rotations=rotations,
        use_ai=False,
        created_by=None,
    )

    # Get dataset and template objects
    dataset = LabellerrDataset(sdk_client, test_dataset_id)
    template = LabellerrAnnotationTemplate(sdk_client, test_template_id)

    project = project_ops.create_project(sdk_client, params, [dataset], template)

    return project.project_id


# =============================================================================
# Test Cases
# =============================================================================


class TestSDKClientInitialization:
    """Test SDK client initialization"""

    def test_client_initialization(self, sdk_client):
        """Test that SDK client initializes successfully"""
        assert sdk_client is not None
        assert sdk_client.api_key is not None
        assert sdk_client.api_secret is not None
        assert sdk_client.client_id is not None
        assert sdk_client.base_url == constants.BASE_URL

    def test_client_session(self, sdk_client):
        """Test that session is configured"""
        assert sdk_client._session is not None


class TestDatasetOperations:
    """Test dataset-related SDK operations"""

    def test_create_dataset_with_folder(self, sdk_client, credentials):
        """Test creating a dataset by uploading a folder"""
        test_data_path = credentials.get("test_data_path")

        if not test_data_path or not os.path.exists(test_data_path):
            pytest.skip("Test data path not provided")

        # Upload folder
        upload_result = upload_folder_files_to_dataset(
            sdk_client,
            {
                "client_id": credentials["client_id"],
                "folder_path": test_data_path,
                "data_type": "image",
            },
        )
        connection_id = upload_result.get("connection_id")
        assert connection_id is not None

        # Create dataset
        dataset_config = schemas.DatasetConfig(
            dataset_name=f"Test Dataset {uuid.uuid4().hex[:8]}", data_type="image"
        )

        dataset = dataset_ops.create_dataset_from_connection(
            sdk_client, dataset_config, connection_id, "local"
        )

        assert dataset.dataset_id is not None

        # Cleanup
        dataset_ops.delete_dataset(sdk_client, dataset.dataset_id)

    def test_get_dataset(self, sdk_client, test_dataset_id):
        """Test getting dataset details"""
        dataset_data = LabellerrDatasetMeta.get_dataset(sdk_client, test_dataset_id)

        assert dataset_data is not None
        assert dataset_data.get("dataset_id") == test_dataset_id
        assert "name" in dataset_data
        assert "data_type" in dataset_data

    def test_list_datasets(self, sdk_client):
        """Test listing datasets"""
        datasets = list(
            dataset_ops.list_datasets(
                sdk_client, "image", schemas.DataSetScope.client, page_size=10
            )
        )

        assert isinstance(datasets, list)


class TestAnnotationTemplateOperations:
    """Test annotation template-related SDK operations"""

    def test_create_annotation_template(self, sdk_client):
        """Test creating an annotation template"""
        template_name = f"Test Template {uuid.uuid4().hex[:8]}"

        questions = [
            AnnotationQuestion(
                question_number=1,
                question="Object Detection",
                question_id=str(uuid.uuid4()),
                question_type=QuestionType.bounding_box,
                required=True,
                options=[Option(option_name="#00FF00")],
                color="#00FF00",
            )
        ]

        params = CreateTemplateParams(
            template_name=template_name, data_type="image", questions=questions
        )

        template = template_ops.create_template(sdk_client, params)

        assert template.annotation_template_id is not None

    def test_get_annotation_template(self, sdk_client, test_template_id):
        """Test getting annotation template details"""
        template_data = LabellerrAnnotationTemplate.get_annotation_template(
            sdk_client, test_template_id
        )

        assert template_data is not None


class TestProjectOperations:
    """Test project-related SDK operations"""

    def test_create_project(self, sdk_client, test_dataset_id, test_template_id):
        """Test creating a project"""
        project_name = f"Test Project {uuid.uuid4().hex[:8]}"

        rotations = schemas.RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        )

        params = schemas.CreateProjectParams(
            project_name=project_name, data_type="image", rotations=rotations
        )

        dataset = LabellerrDataset(sdk_client, test_dataset_id)
        template = LabellerrAnnotationTemplate(sdk_client, test_template_id)

        project = project_ops.create_project(sdk_client, params, [dataset], template)

        assert project.project_id is not None

    def test_get_project(self, sdk_client, test_project_id):
        """Test getting project details"""
        project_data = LabellerrProjectMeta.get_project(sdk_client, test_project_id)

        assert project_data is not None
        assert project_data.get("project_id") == test_project_id
        assert "project_name" in project_data
        assert "data_type" in project_data

    def test_list_projects(self, sdk_client):
        """Test listing projects"""
        projects = project_ops.list_projects(sdk_client)

        assert isinstance(projects, list)

    def test_list_projects_contains_test_project(self, sdk_client, test_project_id):
        """Test that our test project appears in the list"""
        projects = project_ops.list_projects(sdk_client)

        project_ids = [p.project_id for p in projects]
        assert test_project_id in project_ids


class TestExportOperations:
    """Test export-related SDK operations"""

    def test_create_export(self, sdk_client, test_project_id):
        """Test creating an export"""
        project = LabellerrProject(sdk_client, test_project_id)

        export_config = schemas.CreateExportParams(
            export_name=f"Test Export {uuid.uuid4().hex[:8]}",
            export_description="Created by integration tests",
            export_format="json",
            statuses=["accepted"],
            export_destination=schemas.ExportDestination.LOCAL,
        )

        export = project.create_export(export_config)

        assert export.report_id is not None

    def test_check_export_status(self, sdk_client, test_project_id):
        """Test checking export status"""
        project = LabellerrProject(sdk_client, test_project_id)

        # First create an export
        export_config = schemas.CreateExportParams(
            export_name=f"Test Export Status {uuid.uuid4().hex[:8]}",
            export_description="Testing status check",
            export_format="json",
            statuses=["accepted"],
            export_destination=schemas.ExportDestination.LOCAL,
        )

        export = project.create_export(export_config)

        if not export.report_id:
            pytest.skip("Export did not return report_id")

        # Check status
        result = project.check_export_status([export.report_id])

        assert result is not None


class TestCompleteWorkflow:
    """Test the complete end-to-end workflow"""

    def test_full_workflow(self, sdk_client, credentials):
        """Test creating dataset -> template -> project"""
        test_data_path = credentials.get("test_data_path")

        if not test_data_path or not os.path.exists(test_data_path):
            pytest.skip("Test data path not provided")

        # Step 1: Create dataset
        upload_result = upload_folder_files_to_dataset(
            sdk_client,
            {
                "client_id": credentials["client_id"],
                "folder_path": test_data_path,
                "data_type": "image",
            },
        )
        connection_id = upload_result.get("connection_id")

        dataset_config = schemas.DatasetConfig(
            dataset_name=f"Workflow Test Dataset {uuid.uuid4().hex[:8]}",
            data_type="image",
        )

        dataset = dataset_ops.create_dataset_from_connection(
            sdk_client, dataset_config, connection_id, "local"
        )
        dataset_id = dataset.dataset_id

        # Step 2: Create template
        questions = [
            AnnotationQuestion(
                question_number=1,
                question="Label",
                question_id=str(uuid.uuid4()),
                question_type=QuestionType.bounding_box,
                required=True,
                options=[Option(option_name="#FF00FF")],
                color="#FF00FF",
            )
        ]

        template_params = CreateTemplateParams(
            template_name=f"Workflow Test Template {uuid.uuid4().hex[:8]}",
            data_type="image",
            questions=questions,
        )

        template = template_ops.create_template(sdk_client, template_params)

        # Step 3: Create project
        rotations = schemas.RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        )

        project_params = schemas.CreateProjectParams(
            project_name=f"Workflow Test Project {uuid.uuid4().hex[:8]}",
            data_type="image",
            rotations=rotations,
        )

        project = project_ops.create_project(
            sdk_client, project_params, [dataset], template
        )
        project_id = project.project_id

        # Step 4: Verify project was created
        project_data = LabellerrProjectMeta.get_project(sdk_client, project_id)
        assert project_data.get("project_id") == project_id

        # Step 5: Verify project appears in list
        projects = project_ops.list_projects(sdk_client)
        project_ids = [p.project_id for p in projects]
        assert project_id in project_ids

        # Cleanup
        try:
            dataset_ops.delete_dataset(sdk_client, dataset_id)
        except Exception as e:
            print(f"Warning: Failed to cleanup dataset: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
