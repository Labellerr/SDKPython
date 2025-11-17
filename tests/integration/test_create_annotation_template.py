import os
import uuid

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.annotation_templates import create_template
from labellerr.core.schemas import DatasetDataType
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    CreateTemplateParams,
    QuestionType,
)

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")


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
                    question="TEST QUESTION - Bounding Box",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                ),
                AnnotationQuestion(
                    question_number=2,
                    question="TEST QUESTION - Polygon",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.polygon,
                    required=True,
                    color="#FFC800",
                ),
            ],
        ),
    )

    return template


def test_create_annotation_template(create_annotation_template_fixture):
    template = create_annotation_template_fixture

    assert template.annotation_template_id is not None
    assert isinstance(template.annotation_template_id, str)
