"""
Integration tests for the Labellerr MCP Server

These tests verify the complete workflow using the pure API implementation:
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

# Load environment variables
load_dotenv()


@pytest.fixture(scope="session")
def credentials():
    """Load API credentials from environment"""
    api_key = os.getenv('LABELLERR_API_KEY')
    api_secret = os.getenv('LABELLERR_API_SECRET')
    client_id = os.getenv('LABELLERR_CLIENT_ID')
    test_data_path = os.getenv('LABELLERR_TEST_DATA_PATH')

    if not all([api_key, api_secret, client_id]):
        pytest.skip("Missing required environment variables (API_KEY, API_SECRET, CLIENT_ID)")

    return {
        'api_key': api_key,
        'api_secret': api_secret,
        'client_id': client_id,
        'test_data_path': test_data_path
    }


@pytest.fixture(scope="session")
def api_client(credentials):
    """Create API client instance"""
    from labellerr.mcp_server.api_client import LabellerrAPIClient

    client = LabellerrAPIClient(
        api_key=credentials['api_key'],
        api_secret=credentials['api_secret'],
        client_id=credentials['client_id']
    )

    yield client

    # Cleanup
    client.close()


@pytest.fixture(scope="session")
def test_dataset_id(api_client, credentials):
    """Create a test dataset and return its ID"""
    test_data_path = credentials.get('test_data_path')

    if not test_data_path or not os.path.exists(test_data_path):
        pytest.skip("Test data path not provided or does not exist")

    # Upload files and create dataset
    connection_id = api_client.upload_folder_to_connector(test_data_path, "image")

    dataset_name = f"MCP Test Dataset {uuid.uuid4().hex[:8]}"
    result = api_client.create_dataset(
        dataset_name=dataset_name,
        data_type="image",
        dataset_description="Created by MCP integration tests",
        connection_id=connection_id
    )

    dataset_id = result["response"]["dataset_id"]

    yield dataset_id

    # Cleanup - delete dataset after tests
    try:
        api_client.delete_dataset(dataset_id)
    except Exception as e:
        print(f"Warning: Failed to cleanup dataset {dataset_id}: {e}")


@pytest.fixture(scope="session")
def test_template_id(api_client):
    """Create a test annotation template and return its ID"""
    template_name = f"MCP Test Template {uuid.uuid4().hex[:8]}"

    questions = [
        {
            "question_number": 1,
            "question": "Object",
            "question_id": str(uuid.uuid4()),
            "option_type": "BoundingBox",
            "required": True,
            "options": [{"option_name": "#FF0000"}],
            "color": "#FF0000"
        }
    ]

    result = api_client.create_annotation_template(
        template_name=template_name,
        data_type="image",
        questions=questions
    )

    template_id = result["response"]["template_id"]
    return template_id


@pytest.fixture(scope="session")
def test_project_id(api_client, test_dataset_id, test_template_id):
    """Create a test project and return its ID"""
    project_name = f"MCP Test Project {uuid.uuid4().hex[:8]}"

    rotations = {
        "annotation_rotation_count": 1,
        "review_rotation_count": 1,
        "client_review_rotation_count": 1
    }

    result = api_client.create_project(
        project_name=project_name,
        data_type="image",
        attached_datasets=[test_dataset_id],
        annotation_template_id=test_template_id,
        rotations=rotations,
        use_ai=False,
        created_by=None
    )

    project_id = result["response"]["project_id"]
    return project_id


# =============================================================================
# Test Cases
# =============================================================================

class TestAPIClientInitialization:
    """Test API client initialization"""

    def test_client_initialization(self, api_client):
        """Test that API client initializes successfully"""
        assert api_client is not None
        assert api_client.api_key is not None
        assert api_client.api_secret is not None
        assert api_client.client_id is not None
        assert api_client.BASE_URL == "https://api.labellerr.com"

    def test_client_session(self, api_client):
        """Test that session is configured"""
        assert api_client.session is not None


class TestDatasetOperations:
    """Test dataset-related API operations"""

    def test_create_dataset_with_folder(self, api_client, credentials):
        """Test creating a dataset by uploading a folder"""
        test_data_path = credentials.get('test_data_path')

        if not test_data_path or not os.path.exists(test_data_path):
            pytest.skip("Test data path not provided")

        # Upload folder
        connection_id = api_client.upload_folder_to_connector(test_data_path, "image")
        assert connection_id is not None

        # Create dataset
        dataset_name = f"Test Dataset {uuid.uuid4().hex[:8]}"
        result = api_client.create_dataset(
            dataset_name=dataset_name,
            data_type="image",
            connection_id=connection_id
        )

        assert "response" in result
        assert "dataset_id" in result["response"]

        dataset_id = result["response"]["dataset_id"]

        # Cleanup
        api_client.delete_dataset(dataset_id)

    def test_get_dataset(self, api_client, test_dataset_id):
        """Test getting dataset details"""
        result = api_client.get_dataset(test_dataset_id)

        assert "response" in result
        assert result["response"]["dataset_id"] == test_dataset_id
        assert "name" in result["response"]
        assert "data_type" in result["response"]

    def test_list_datasets(self, api_client):
        """Test listing datasets"""
        result = api_client.list_datasets(data_type="image", scope="client")

        assert "response" in result
        assert "datasets" in result["response"]
        assert isinstance(result["response"]["datasets"], list)


class TestAnnotationTemplateOperations:
    """Test annotation template-related API operations"""

    def test_create_annotation_template(self, api_client):
        """Test creating an annotation template"""
        template_name = f"Test Template {uuid.uuid4().hex[:8]}"

        questions = [
            {
                "question_number": 1,
                "question": "Object Detection",
                "question_id": str(uuid.uuid4()),
                "option_type": "BoundingBox",
                "required": True,
                "options": [{"option_name": "#00FF00"}],
                "color": "#00FF00"
            }
        ]

        result = api_client.create_annotation_template(
            template_name=template_name,
            data_type="image",
            questions=questions
        )

        assert "response" in result
        assert "template_id" in result["response"]

    def test_get_annotation_template(self, api_client, test_template_id):
        """Test getting annotation template details"""
        result = api_client.get_annotation_template(test_template_id)

        assert "response" in result or "template" in result  # API may return different structure


class TestProjectOperations:
    """Test project-related API operations"""

    def test_create_project(self, api_client, test_dataset_id, test_template_id):
        """Test creating a project"""
        project_name = f"Test Project {uuid.uuid4().hex[:8]}"

        rotations = {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1
        }

        result = api_client.create_project(
            project_name=project_name,
            data_type="image",
            attached_datasets=[test_dataset_id],
            annotation_template_id=test_template_id,
            rotations=rotations
        )

        assert "response" in result
        assert "project_id" in result["response"]

    def test_get_project(self, api_client, test_project_id):
        """Test getting project details"""
        result = api_client.get_project(test_project_id)

        assert "response" in result
        assert result["response"]["project_id"] == test_project_id
        assert "project_name" in result["response"]
        assert "data_type" in result["response"]

    def test_list_projects(self, api_client):
        """Test listing projects"""
        result = api_client.list_projects()

        assert "response" in result
        assert "projects" in result["response"]
        assert isinstance(result["response"]["projects"], list)

    def test_list_projects_contains_test_project(self, api_client, test_project_id):
        """Test that our test project appears in the list"""
        result = api_client.list_projects()

        project_ids = [p["project_id"] for p in result["response"]["projects"]]
        assert test_project_id in project_ids


class TestExportOperations:
    """Test export-related API operations"""

    def test_create_export(self, api_client, test_project_id):
        """Test creating an export"""
        result = api_client.create_export(
            project_id=test_project_id,
            export_name=f"Test Export {uuid.uuid4().hex[:8]}",
            export_description="Created by integration tests",
            export_format="json",
            statuses=["accepted"]
        )

        assert "response" in result
        # Export may return report_id or job_id
        assert "report_id" in result["response"] or "job_id" in result["response"]

    def test_check_export_status(self, api_client, test_project_id):
        """Test checking export status"""
        # First create an export
        export_result = api_client.create_export(
            project_id=test_project_id,
            export_name=f"Test Export Status {uuid.uuid4().hex[:8]}",
            export_description="Testing status check",
            export_format="json",
            statuses=["accepted"]
        )

        report_id = export_result["response"].get("report_id")
        if not report_id:
            pytest.skip("Export did not return report_id")

        # Check status
        result = api_client.check_export_status(
            project_id=test_project_id,
            report_ids=[report_id]
        )

        assert "status" in result or "response" in result


class TestCompleteWorkflow:
    """Test the complete end-to-end workflow"""

    def test_full_workflow(self, api_client, credentials):
        """Test creating dataset -> template -> project"""
        test_data_path = credentials.get('test_data_path')

        if not test_data_path or not os.path.exists(test_data_path):
            pytest.skip("Test data path not provided")

        # Step 1: Create dataset
        connection_id = api_client.upload_folder_to_connector(test_data_path, "image")
        dataset_result = api_client.create_dataset(
            dataset_name=f"Workflow Test Dataset {uuid.uuid4().hex[:8]}",
            data_type="image",
            connection_id=connection_id
        )
        dataset_id = dataset_result["response"]["dataset_id"]

        # Step 2: Create template
        template_result = api_client.create_annotation_template(
            template_name=f"Workflow Test Template {uuid.uuid4().hex[:8]}",
            data_type="image",
            questions=[{
                "question_number": 1,
                "question": "Label",
                "question_id": str(uuid.uuid4()),
                "option_type": "BoundingBox",
                "required": True,
                "options": [{"option_name": "#FF00FF"}],
                "color": "#FF00FF"
            }]
        )
        template_id = template_result["response"]["template_id"]

        # Step 3: Create project
        project_result = api_client.create_project(
            project_name=f"Workflow Test Project {uuid.uuid4().hex[:8]}",
            data_type="image",
            attached_datasets=[dataset_id],
            annotation_template_id=template_id,
            rotations={
                "annotation_rotation_count": 1,
                "review_rotation_count": 1,
                "client_review_rotation_count": 1
            }
        )
        project_id = project_result["response"]["project_id"]

        # Step 4: Verify project was created
        project_details = api_client.get_project(project_id)
        assert project_details["response"]["project_id"] == project_id

        # Step 5: Verify project appears in list
        projects_list = api_client.list_projects()
        project_ids = [p["project_id"] for p in projects_list["response"]["projects"]]
        assert project_id in project_ids

        # Cleanup
        try:
            api_client.delete_dataset(dataset_id)
        except Exception as e:
            print(f"Warning: Failed to cleanup dataset: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
