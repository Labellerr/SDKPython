"""
Integration tests for annotation template creation.

This module tests the create_template function for all supported data types:
- Image (with bounding box and polygon questions)
- Video (with bounding box questions)
- Audio (with classification questions)
- Document (with selection questions)
- Text (with sentiment questions)

IMPORTANT: Templates cannot be automatically cleaned up as the SDK does not
provide a delete_template() function. Templates will accumulate with each test run.
Manual cleanup may be required periodically via the Labellerr UI.
"""

import time
import uuid
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add tests directory to path to import conftest helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import skip_if_auth_failed

from labellerr.core.annotation_templates import create_template
from labellerr.core.schemas import DatasetDataType
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    CreateTemplateParams,
    Option,
    QuestionType,
)

load_dotenv()


def _create_and_validate_template(client, template_name, data_type, questions):
    """
    Helper function to create and validate a template.
    
    Args:
        client: LabellerrClient instance
        template_name: Name for the template
        data_type: DatasetDataType enum value
        questions: List of AnnotationQuestion objects
        
    Returns:
        Template object with annotation_template_id
    """
    params = CreateTemplateParams(
        template_name=template_name,
        data_type=data_type,
        questions=questions
    )
    
    try:
        template = create_template(client, params)
        assert template is not None
        assert template.annotation_template_id is not None
        assert isinstance(template.annotation_template_id, str)
        return template
    except Exception as e:
        skip_if_auth_failed(e)


@pytest.mark.integration
class TestCreateAnnotationTemplateIntegration:
    """Integration tests for annotation template creation across all data types.

    Note: Templates cannot be automatically cleaned up as the SDK does not provide
    a delete_template() function. Templates will accumulate with each test run.
    """

    def test_create_image_template(self, integration_client):
        """Test creating image template with bounding box and polygon questions."""
        timestamp = int(time.time())
        _create_and_validate_template(
            client=integration_client,
            template_name=f"SDK_Test_Image_Template_{timestamp}",
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
        )

    def test_create_video_template(self, integration_client):
        """Test creating video template with bounding box question."""
        timestamp = int(time.time())
        _create_and_validate_template(
            client=integration_client,
            template_name=f"SDK_Test_Video_Template_{timestamp}",
            data_type=DatasetDataType.video,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="TEST QUESTION - Video Bounding Box",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#0000FF",
                ),
            ],
        )

    def test_create_audio_template(self, integration_client):
        """Test creating audio template with radio button classification question."""
        timestamp = int(time.time())
        _create_and_validate_template(
            client=integration_client,
            template_name=f"SDK_Test_Audio_Template_{timestamp}",
            data_type=DatasetDataType.audio,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="TEST QUESTION - Audio Classification",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.radio,
                    required=True,
                    options=[
                        Option(option_name="Speech"),
                        Option(option_name="Music"),
                        Option(option_name="Noise"),
                        Option(option_name="Silence"),
                    ],
                ),
            ],
        )

    def test_create_document_template(self, integration_client):
        """Test creating document template with select dropdown question."""
        timestamp = int(time.time())
        _create_and_validate_template(
            client=integration_client,
            template_name=f"SDK_Test_Document_Template_{timestamp}",
            data_type=DatasetDataType.document,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="TEST QUESTION - Document Type",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.select,
                    required=True,
                    options=[
                        Option(option_name="Invoice"),
                        Option(option_name="Receipt"),
                        Option(option_name="Contract"),
                        Option(option_name="Other"),
                    ],
                ),
            ],
        )

    def test_create_text_template(self, integration_client):
        """Test creating text template with radio button sentiment question."""
        timestamp = int(time.time())
        _create_and_validate_template(
            client=integration_client,
            template_name=f"SDK_Test_Text_Template_{timestamp}",
            data_type=DatasetDataType.text,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="TEST QUESTION - Sentiment",
                    question_id=str(uuid.uuid4()),
                    question_type=QuestionType.radio,
                    required=True,
                    options=[
                        Option(option_name="Positive"),
                        Option(option_name="Negative"),
                        Option(option_name="Neutral"),
                    ],
                ),
            ],
        )
