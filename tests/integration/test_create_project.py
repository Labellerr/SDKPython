import os

import pytest

from labellerr.client import LabellerrClient
from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.projects import create_project
from labellerr.core.schemas import CreateProjectParams, DatasetDataType, RotationConfig

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
DATASET_ID = os.getenv("DATASET_ID")
TEMPLATE_ID = os.getenv("TEMPLATE_ID")


@pytest.fixture
def create_project_fixture(client):

    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )
    dataset = LabellerrDataset(client=client, dataset_id=DATASET_ID)
    template = LabellerrAnnotationTemplate(
        client=client, annotation_template_id=TEMPLATE_ID
    )

    project = create_project(
        client=client,
        params=CreateProjectParams(
            project_name="My Project",
            data_type=DatasetDataType.image,
            rotations=RotationConfig(
                annotation_rotation_count=1,
                review_rotation_count=1,
                client_review_rotation_count=1,
            ),
        ),
        datasets=[dataset],
        annotation_template=template,
    )
    return project


def test_create_project(create_project_fixture):
    project = create_project_fixture

    assert project.project_id is not None
    assert isinstance(project.project_id, str)


def test_archive_and_delete_project(create_project_fixture):

    project = create_project_fixture
    assert project.project_id is not None

    # 1. Archive
    print(f"Archiving project {project.project_id}...")
    try:
        project.archive()
    except Exception as e:
        pytest.fail(f"Failed to archive project: {e}")

    # 2. Unarchive (test the alias)
    print(f"Unarchiving project {project.project_id}...")
    try:
        project.unarchive()
    except Exception as e:
        pytest.fail(f"Failed to unarchive project: {e}")

    # 3. Archive again (to test delete on archived project if valid, or just normal delete)
    # Let's delete it while active
    print(f"Deleting project {project.project_id}...")
    try:
        project.delete()
    except Exception as e:
        pytest.fail(f"Failed to delete project: {e}")
