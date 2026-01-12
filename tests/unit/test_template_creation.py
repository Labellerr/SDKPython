"""
Unit tests for annotation template creation functionality.

These tests use mocked API responses to test the template creation logic
without making actual API calls.
"""

from unittest.mock import patch

import pytest

from labellerr.client import LabellerrClient
from labellerr.core.annotation_templates import create_template, list_templates
from labellerr.core.schemas import DatasetDataType
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    CreateTemplateParams,
    Option,
    QuestionType,
)


def mock_template_responses(
    template_id, template_name="Test Template", data_type="image"
):
    """
    Helper function to create mock responses for template creation.
    Returns list of responses: [create_response, get_template_response]
    """
    return [
        {"response": {"template_id": template_id}},  # create_template POST response
        {
            "response": {  # get_template GET response (called by __new__)
                "template_id": template_id,
                "template_name": template_name,
                "data_type": data_type,
                "questions": [],
                "created_at": "2024-01-01",
                "created_by": "test@example.com",
            }
        },
    ]


class TestTemplateCreation:
    """Unit tests for template creation with mocked API calls"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing"""
        return LabellerrClient("test_api_key", "test_api_secret", "test_client_id")

    def test_create_template_single_bbox_question(self, mock_client):
        """Test creating a template with a single bounding box question"""
        params = CreateTemplateParams(
            template_name="Single BBox Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Detect objects",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "test_template_id_123", "Single BBox Template"
            )

            template = create_template(mock_client, params)

            assert template.annotation_template_id == "test_template_id_123"

            # Verify the create request payload
            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["templateName"] == "Single BBox Template"
            assert len(payload["questions"]) == 1
            assert payload["questions"][0]["option_type"] == "BoundingBox"
            assert payload["questions"][0]["color"] == "#FF0000"

    def test_create_template_multiple_questions(self, mock_client):
        """Test creating a template with multiple questions of different types"""
        params = CreateTemplateParams(
            template_name="Multi Question Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw bounding box",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                ),
                AnnotationQuestion(
                    question_number=2,
                    question="Select category",
                    question_type=QuestionType.dropdown,
                    required=True,
                    options=[
                        Option(option_name="cat"),
                        Option(option_name="dog"),
                        Option(option_name="car"),
                    ],
                ),
                AnnotationQuestion(
                    question_number=3,
                    question="Is visible?",
                    question_type=QuestionType.boolean,
                    required=False,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                ),
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "test_template_id_456", "Multi Question Template"
            )

            template = create_template(mock_client, params)

            assert template.annotation_template_id == "test_template_id_456"

            # Verify payload structure
            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert len(payload["questions"]) == 3
            assert payload["questions"][0]["option_type"] == "BoundingBox"
            assert payload["questions"][1]["option_type"] == "dropdown"
            assert payload["questions"][2]["option_type"] == "boolean"

    def test_create_template_polygon_question(self, mock_client):
        """Test creating a template with polygon question"""
        params = CreateTemplateParams(
            template_name="Polygon Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw polygon around object",
                    question_type=QuestionType.polygon,
                    required=True,
                    color="#00FF00",
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "polygon_template_id", "Polygon Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "polygon"
            assert payload["questions"][0]["color"] == "#00FF00"

    def test_create_template_polyline_question(self, mock_client):
        """Test creating a template with polyline question"""
        params = CreateTemplateParams(
            template_name="Polyline Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw line",
                    question_type=QuestionType.polyline,
                    required=True,
                    color="#0000FF",
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "polyline_template_id", "Polyline Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "polyline"
            assert payload["questions"][0]["color"] == "#0000FF"

    def test_create_template_dot_question(self, mock_client):
        """Test creating a template with dot question"""
        params = CreateTemplateParams(
            template_name="Dot Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Mark point",
                    question_type=QuestionType.dot,
                    required=True,
                    color="#FF00FF",
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "dot_template_id", "Dot Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "dot"
            assert payload["questions"][0]["color"] == "#FF00FF"

    def test_create_template_radio_question(self, mock_client):
        """Test creating a template with radio question"""
        params = CreateTemplateParams(
            template_name="Radio Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Choose one",
                    question_type=QuestionType.radio,
                    required=True,
                    options=[
                        Option(option_name="Option A"),
                        Option(option_name="Option B"),
                    ],
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "radio_template_id", "Radio Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "radio"
            assert len(payload["questions"][0]["options"]) == 2

    def test_create_template_select_question(self, mock_client):
        """Test creating a template with select question"""
        params = CreateTemplateParams(
            template_name="Select Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Select multiple",
                    question_type=QuestionType.select,
                    required=True,
                    options=[
                        Option(option_name="Tag1"),
                        Option(option_name="Tag2"),
                        Option(option_name="Tag3"),
                    ],
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "select_template_id", "Select Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "select"
            assert len(payload["questions"][0]["options"]) == 3

    def test_create_template_input_question(self, mock_client):
        """Test creating a template with input (text) question"""
        params = CreateTemplateParams(
            template_name="Input Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Enter description",
                    question_type=QuestionType.input,
                    required=False,
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.side_effect = mock_template_responses(
                "input_template_id", "Input Template"
            )

            create_template(mock_client, params)

            create_call = mock_request.call_args_list[0]
            payload = create_call[1]["json"]
            assert payload["questions"][0]["option_type"] == "input"
            # Input questions don't require options

    def test_create_template_all_data_types(self, mock_client):
        """Test creating templates for all data types"""
        data_types = [
            DatasetDataType.image,
            DatasetDataType.video,
            DatasetDataType.audio,
            DatasetDataType.document,
            DatasetDataType.text,
        ]

        for data_type in data_types:
            params = CreateTemplateParams(
                template_name=f"{data_type.value} Template",
                data_type=data_type,
                questions=[
                    AnnotationQuestion(
                        question_number=1,
                        question="Test question",
                        question_type=QuestionType.boolean,
                        required=True,
                        options=[Option(option_name="Yes"), Option(option_name="No")],
                    )
                ],
            )

            with patch.object(mock_client, "make_request") as mock_request:
                mock_request.side_effect = mock_template_responses(
                    f"{data_type.value}_template_id",
                    f"{data_type.value} Template",
                    data_type.value,
                )

                template = create_template(mock_client, params)

                assert (
                    template.annotation_template_id == f"{data_type.value}_template_id"
                )

                # Verify URL contains correct data_type
                create_call = mock_request.call_args_list[0]
                url = create_call[0][1]
                assert f"data_type={data_type.value}" in url


class TestTemplateValidation:
    """Unit tests for template validation logic"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing"""
        return LabellerrClient("test_api_key", "test_api_secret", "test_client_id")

    def test_bbox_without_color_raises_error(self, mock_client):
        """Test that bounding box question without color raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid BBox Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw box",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    # Missing color
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Color is required for bounding box, polygon, polyline, and dot questions",
        ):
            create_template(mock_client, params)

    def test_polygon_without_color_raises_error(self, mock_client):
        """Test that polygon question without color raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Polygon Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw polygon",
                    question_type=QuestionType.polygon,
                    required=True,
                    # Missing color
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Color is required for bounding box, polygon, polyline, and dot questions",
        ):
            create_template(mock_client, params)

    def test_polyline_without_color_raises_error(self, mock_client):
        """Test that polyline question without color raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Polyline Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw line",
                    question_type=QuestionType.polyline,
                    required=True,
                    # Missing color
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Color is required for bounding box, polygon, polyline, and dot questions",
        ):
            create_template(mock_client, params)

    def test_dot_without_color_raises_error(self, mock_client):
        """Test that dot question without color raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Dot Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Mark point",
                    question_type=QuestionType.dot,
                    required=True,
                    # Missing color
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Color is required for bounding box, polygon, polyline, and dot questions",
        ):
            create_template(mock_client, params)

    def test_radio_without_options_raises_error(self, mock_client):
        """Test that radio question without options raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Radio Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Choose one",
                    question_type=QuestionType.radio,
                    required=True,
                    # Missing options
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Options are required for radio, boolean, select, dropdown, stt, imc questions",
        ):
            create_template(mock_client, params)

    def test_boolean_without_options_raises_error(self, mock_client):
        """Test that boolean question without options raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Boolean Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Is valid?",
                    question_type=QuestionType.boolean,
                    required=True,
                    # Missing options
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Options are required for radio, boolean, select, dropdown, stt, imc questions",
        ):
            create_template(mock_client, params)

    def test_select_without_options_raises_error(self, mock_client):
        """Test that select question without options raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Select Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Select tags",
                    question_type=QuestionType.select,
                    required=True,
                    # Missing options
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Options are required for radio, boolean, select, dropdown, stt, imc questions",
        ):
            create_template(mock_client, params)

    def test_dropdown_without_options_raises_error(self, mock_client):
        """Test that dropdown question without options raises ValueError"""
        params = CreateTemplateParams(
            template_name="Invalid Dropdown Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Choose category",
                    question_type=QuestionType.dropdown,
                    required=True,
                    # Missing options
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Options are required for radio, boolean, select, dropdown, stt, imc questions",
        ):
            create_template(mock_client, params)

    def test_input_without_options_is_valid(self, mock_client):
        """Test that input question without options is valid"""
        params = CreateTemplateParams(
            template_name="Valid Input Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Enter text",
                    question_type=QuestionType.input,
                    required=True,
                    # Input doesn't require options
                )
            ],
        )

        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.return_value = {
                "response": {"template_id": "input_template_id"}
            }

            # Should not raise an error
            template = create_template(mock_client, params)
            assert template.annotation_template_id == "input_template_id"


class TestListTemplates:
    """Unit tests for listing templates"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing"""
        return LabellerrClient("test_api_key", "test_api_secret", "test_client_id")

    def test_list_templates_empty(self, mock_client):
        """Test listing templates when none exist"""
        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.return_value = {"response": []}

            templates = list_templates(mock_client, DatasetDataType.image)

            assert templates == []
            mock_request.assert_called_once()

            # Verify URL contains correct data_type
            call_args = mock_request.call_args
            url = call_args[0][1]
            assert "data_type=image" in url

    def test_list_templates_with_results(self, mock_client):
        """Test listing templates with results"""
        with patch.object(mock_client, "make_request") as mock_request:
            mock_request.return_value = {
                "response": [
                    {
                        "template_id": "template_1",
                        "template_name": "Template 1",
                        "data_type": "image",
                        "questions": [],
                        "created_at": "2024-01-01",
                        "created_by": "test@example.com",
                    },
                    {
                        "template_id": "template_2",
                        "template_name": "Template 2",
                        "data_type": "image",
                        "questions": [],
                        "created_at": "2024-01-01",
                        "created_by": "test@example.com",
                    },
                ]
            }

            templates = list_templates(mock_client, DatasetDataType.image)

            assert len(templates) == 2

    def test_list_templates_all_data_types(self, mock_client):
        """Test listing templates for all data types"""
        data_types = [
            DatasetDataType.image,
            DatasetDataType.video,
            DatasetDataType.audio,
            DatasetDataType.document,
            DatasetDataType.text,
        ]

        for data_type in data_types:
            with patch.object(mock_client, "make_request") as mock_request:
                mock_request.return_value = {"response": []}

                list_templates(mock_client, data_type)

                # Verify URL contains correct data_type
                call_args = mock_request.call_args
                url = call_args[0][1]
                assert f"data_type={data_type.value}" in url
