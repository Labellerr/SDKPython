from labellerr.client import LabellerrClient
from labellerr.core.datasets import create_dataset_from_local
from labellerr.core.annotation_templates import create_template
from labellerr.core.projects import create_project

# from labellerr.core.schemas import *  remove this code
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    QuestionType,
    CreateTemplateParams,
)
from labellerr.core.schemas.datasets import DatasetConfig
from labellerr.core.schemas import DatasetDataType
from labellerr.core.schemas.projects import CreateProjectParams, RotationConfig

import uuid
import pytest
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
IMAGES_DATASET_UPLOAD_PATH = os.getenv("IMAGES_DATASET_UPLOAD_PATH")


client = LabellerrClient(api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID)


@pytest.fixture
def create_dataset_fixture():
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    dataset = create_dataset_from_local(
        client=client,
        dataset_config=DatasetConfig(dataset_name="My Dataset", data_type="image"),
        folder_to_upload=IMAGES_DATASET_UPLOAD_PATH,
    )

    return dataset


@pytest.fixture
def create_annotation_template_fixture():
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    template = create_template(
        client=client,
        params=CreateTemplateParams(
            template_name="My Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Object",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                )
            ],
        ),
    )

    return template


@pytest.fixture
def create_project_fixture(create_dataset_fixture, create_annotation_template_fixture):
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )
    dataset = create_dataset_fixture
    template = create_annotation_template_fixture

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


def test_create_dataset(create_dataset_fixture):
    dataset = create_dataset_fixture

    assert dataset.dataset_id is not None

    result = dataset.status()

    assert result["status_code"] == 300
    assert result["files_count"] > 0


def test_create_annotation_template(create_annotation_template_fixture):
    template = create_annotation_template_fixture

    assert template.annotation_template_id is not None
    assert isinstance(template.annotation_template_id, str)


def test_create_project(create_project_fixture):
    project = create_project_fixture

    assert project.project_id is not None
    assert isinstance(project.project_id, str)
