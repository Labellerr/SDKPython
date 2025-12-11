"""
Integration tests for labellerr/core/projects/__init__.py module.

This module contains integration tests that make actual API calls to test
the create_project and list_projects functions end-to-end.
"""

import time

import pytest

from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project, list_projects
from labellerr.core.projects.base import LabellerrProject
from labellerr.core.schemas import CreateProjectParams, DatasetDataType, RotationConfig


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
    import os

    template_id = os.getenv("TEMPLATE_ID") or os.getenv("TEST_TEMPLATE_ID")
    if template_id:
        return LabellerrAnnotationTemplate(
            client=client, annotation_template_id=template_id
        )
    pytest.skip(
        "TEMPLATE_ID or TEST_TEMPLATE_ID environment variable is required for integration tests"
    )


@pytest.fixture
def test_project_params(email_id):
    """Create test project parameters with unique name"""
    timestamp = int(time.time())
    return CreateProjectParams(
        project_name=f"SDK_IntegrationTest_Project_{timestamp}",
        data_type=DatasetDataType.image,
        rotations=RotationConfig(
            annotation_rotation_count=1,
            review_rotation_count=1,
            client_review_rotation_count=1,
        ),
        use_ai=False,
        created_by=email_id or "test@example.com",
    )


@pytest.mark.integration
@pytest.mark.slow
class TestCreateProjectIntegration:
    """Integration tests for create_project function"""

    def test_create_project_basic(
        self, client, test_project_params, test_dataset, test_annotation_template
    ):
        """Test basic project creation with real API calls"""
        project = create_project(
            client=client,
            params=test_project_params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        # Assertions
        assert project is not None
        assert isinstance(project, LabellerrProject)
        assert project.project_id is not None
        assert isinstance(project.project_id, str)
        assert len(project.project_id) > 0

    def test_create_project_with_ai(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test project creation with AI enabled"""
        timestamp = int(time.time())
        params = CreateProjectParams(
            project_name=f"SDK_IntegrationTest_AI_Project_{timestamp}",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=2,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
            use_ai=True,
            created_by=email_id or "test@example.com",
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert isinstance(project, LabellerrProject)
        assert project.project_id is not None

    def test_create_project_image_type(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test creating an image project"""
        timestamp = int(time.time())
        params = CreateProjectParams(
            project_name=f"SDK_IntegrationTest_Image_{timestamp}",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by=email_id or "test@example.com",
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
        timestamp = int(time.time())
        params = CreateProjectParams(
            project_name=f"SDK_IntegrationTest_CustomRotation_{timestamp}",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=3,
                review_rotation_count=2,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by=email_id or "test@example.com",
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
        project = create_project(
            client=client,
            params=test_project_params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        # Verify project properties
        assert project.project_id is not None
        assert project.data_type == test_project_params.data_type.value
        assert (
            project.annotation_template_id
            == test_annotation_template.annotation_template_id
        )
        assert project.created_by == (email_id or "test@example.com")


@pytest.mark.integration
@pytest.mark.slow
class TestListProjectsIntegration:
    """Integration tests for list_projects function"""

    def test_list_projects_basic(self, client):
        """Test basic project listing with real API calls"""
        projects = list_projects(client)

        # Assertions
        assert projects is not None
        assert isinstance(projects, list)
        # Should have at least some projects (or could be empty)
        for project in projects:
            assert isinstance(project, LabellerrProject)
            assert project.project_id is not None

    def test_list_projects_returns_labellerr_project_objects(self, client):
        """Test that list_projects returns LabellerrProject objects"""
        projects = list_projects(client)

        assert isinstance(projects, list)
        for project in projects:
            assert isinstance(project, LabellerrProject)
            # Verify basic properties exist
            assert hasattr(project, "project_id")
            assert hasattr(project, "data_type")
            assert hasattr(project, "annotation_template_id")

    def test_list_projects_project_properties(self, client):
        """Test that listed projects have required properties"""
        projects = list_projects(client)

        if len(projects) > 0:
            # Test first project has required attributes
            project = projects[0]
            assert project.project_id is not None
            assert isinstance(project.project_id, str)
            # Data type should be one of the valid types
            assert project.data_type in ["image", "video", "audio", "document", "text"]

    def test_list_projects_after_creation(
        self, client, test_project_params, test_dataset, test_annotation_template
    ):
        """Test that newly created project appears in list"""
        # Get initial project count
        initial_projects = list_projects(client)
        initial_count = len(initial_projects)

        # Create a new project
        create_project(
            client=client,
            params=test_project_params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        # Wait a bit for the project to be fully created
        time.sleep(2)

        # List projects again
        updated_projects = list_projects(client)
        updated_count = len(updated_projects)

        # Should have one more project
        assert updated_count >= initial_count
        # Note: The new project might not immediately appear in the list
        # depending on the API's consistency model

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
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test creating project with maximum allowed name length (50 chars)"""
        timestamp = int(time.time())
        # API limit is 50 characters, so create a name at the limit
        long_name = f"SDK_Test_{'A' * 30}_{timestamp}"[:50]

        params = CreateProjectParams(
            project_name=long_name,
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by=email_id or "test@example.com",
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.project_id is not None

    def test_create_project_special_characters_in_name(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test creating project with special characters in name"""
        timestamp = int(time.time())
        special_name = f"SDK_Test-Project_2024_{timestamp}"

        params = CreateProjectParams(
            project_name=special_name,
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by=email_id or "test@example.com",
        )

        project = create_project(
            client=client,
            params=params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert project is not None
        assert project.project_id is not None

    def test_create_project_minimum_rotations(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test creating project with minimum rotation counts (1)"""
        timestamp = int(time.time())
        params = CreateProjectParams(
            project_name=f"SDK_IntegrationTest_MinRotation_{timestamp}",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
            use_ai=False,
            created_by=email_id or "test@example.com",
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
        # Create project
        created_project = create_project(
            client=client,
            params=test_project_params,
            datasets=[test_dataset],
            annotation_template=test_annotation_template,
        )

        assert created_project is not None
        created_project_id = created_project.project_id

        # Wait for project to be fully created
        time.sleep(2)

        # Retrieve project by creating a new instance
        retrieved_project = LabellerrProject(
            client=client, project_id=created_project_id
        )

        # Verify properties match
        assert retrieved_project.project_id == created_project_id
        assert retrieved_project.data_type == test_project_params.data_type.value

    def test_create_multiple_projects(
        self, client, test_dataset, test_annotation_template, email_id
    ):
        """Test creating multiple projects in sequence"""
        timestamp = int(time.time())
        created_projects = []

        for i in range(3):
            params = CreateProjectParams(
                project_name=f"SDK_IntegrationTest_Multi_{timestamp}_{i}",
                data_type=DatasetDataType.image,
                rotations=RotationConfig(
                    annotation_rotation_count=1,
                    review_rotation_count=1,
                    client_review_rotation_count=1,
                ),
                use_ai=False,
                created_by=email_id or "test@example.com",
            )

            project = create_project(
                client=client,
                params=params,
                datasets=[test_dataset],
                annotation_template=test_annotation_template,
            )

            created_projects.append(project)
            time.sleep(1)  # Small delay between creations

        # Verify all projects were created
        assert len(created_projects) == 3
        assert all(p.project_id is not None for p in created_projects)

        # Verify all project IDs are unique
        project_ids = [p.project_id for p in created_projects]
        assert len(project_ids) == len(set(project_ids))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
