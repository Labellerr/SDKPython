"""
Integration tests for annotation template creation functionality.

These tests make real API calls and verify actual template creation, listing,
and management operations.
"""

import os
import uuid
import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.annotation_templates import create_template, list_templates
from labellerr.core.schemas import DatasetDataType
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    CreateTemplateParams,
    Option,
    QuestionType,
)
from labellerr.core.exceptions import LabellerrError

# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def cleanup_templates():
    """
    Fixture for automatic template cleanup after each test.

    Note: Template deletion is not yet implemented in SDK,
    so this fixture tracks templates but cannot delete them.

    Usage in tests:
        template = create_template(...)
        cleanup_templates(template.annotation_template_id)
    """
    templates_to_cleanup = []

    def _register(template_id: str):
        """Register a template_id for cleanup"""
        if template_id and template_id not in templates_to_cleanup:
            templates_to_cleanup.append(template_id)

    yield _register

    # Note: Cleanup not possible yet - template deletion API not implemented
    if templates_to_cleanup:
        print(f"\n⚠ Template deletion not yet implemented - {len(templates_to_cleanup)} template(s) remain in system")


@pytest.fixture(scope="session", autouse=True)
def verify_api_credentials_before_tests():
    """
    Verify API credentials are valid before running any integration tests.
    Fails fast if credentials are missing or invalid.
    """
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id_val = os.getenv("CLIENT_ID")

    if not all([api_key, api_secret, client_id_val]):
        pytest.skip(
            "API credentials not configured. Set API_KEY, "
            "API_SECRET, and CLIENT_ID environment variables."
        )

    try:
        client = LabellerrClient(api_key, api_secret, client_id_val)
        # Make a simple API call to verify credentials work
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


class TestTemplateCreationIntegration:
    """Integration tests for template creation with real API calls"""

    def test_create_template_single_bbox_question(self, integration_client, cleanup_templates):
        """
        Test creating a template with a single bounding box question.
        Verifies template creation with geometric annotation type.
        """
        params = CreateTemplateParams(
            template_name=f"SDK_Test_BBox_Template_{uuid.uuid4().hex[:8]}",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw bounding box around objects",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    color="#FF0000",
                )
            ],
        )

        template = create_template(integration_client, params)
        cleanup_templates(template.annotation_template_id)

        # Validate template was created
        assert template is not None
        assert template.annotation_template_id is not None
        assert isinstance(template.annotation_template_id, str)
        assert len(template.annotation_template_id) > 0

        print(f"\n✓ Created template: {template.annotation_template_id}")

    def test_create_template_multiple_questions(self, integration_client, cleanup_templates):
        """
        Test creating a template with multiple questions of different types.
        Verifies:
        - Geometric type (bounding box with color)
        - Choice type (dropdown with options)
        - Boolean type (yes/no question)
        """
        params = CreateTemplateParams(
            template_name=f"SDK_Test_Multi_Template_{uuid.uuid4().hex[:8]}",
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
                    question="Select object category",
                    question_type=QuestionType.dropdown,
                    required=True,
                    options=[
                        Option(option_name="person"),
                        Option(option_name="vehicle"),
                        Option(option_name="animal"),
                        Option(option_name="other"),
                    ],
                ),
                AnnotationQuestion(
                    question_number=3,
                    question="Is object visible?",
                    question_type=QuestionType.boolean,
                    required=False,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                ),
            ],
        )

        template = create_template(integration_client, params)
        cleanup_templates(template.annotation_template_id)

        assert template is not None
        assert template.annotation_template_id is not None
        print(f"\n✓ Created multi-question template: {template.annotation_template_id}")

    def test_create_template_all_geometric_types(self, integration_client, cleanup_templates):
        """
        Test creating a template with ALL geometric question types in one template.
        Tests: bounding_box, polygon, polyline, dot
        """
        params = CreateTemplateParams(
            template_name=f"SDK_Test_AllGeometric_Template_{uuid.uuid4().hex[:8]}",
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
                    question="Draw polygon",
                    question_type=QuestionType.polygon,
                    required=True,
                    color="#00FF00",
                ),
                AnnotationQuestion(
                    question_number=3,
                    question="Draw line",
                    question_type=QuestionType.polyline,
                    required=True,
                    color="#0000FF",
                ),
                AnnotationQuestion(
                    question_number=4,
                    question="Mark point",
                    question_type=QuestionType.dot,
                    required=True,
                    color="#FFFF00",
                ),
            ],
        )

        template = create_template(integration_client, params)
        cleanup_templates(template.annotation_template_id)

        assert template is not None
        assert template.annotation_template_id is not None
        print(
            f"\n✓ Created template with all geometric types: {template.annotation_template_id}"
        )

    def test_create_template_all_choice_and_input_types(self, integration_client, cleanup_templates):
        """
        Test creating a template with ALL choice and input question types.
        Tests: radio, boolean, select, dropdown, input
        """
        params = CreateTemplateParams(
            template_name=f"SDK_Test_AllChoice_Template_{uuid.uuid4().hex[:8]}",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Choose one option",
                    question_type=QuestionType.radio,
                    required=True,
                    options=[Option(option_name="A"), Option(option_name="B")],
                ),
                AnnotationQuestion(
                    question_number=2,
                    question="Is valid?",
                    question_type=QuestionType.boolean,
                    required=True,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                ),
                AnnotationQuestion(
                    question_number=3,
                    question="Select multiple",
                    question_type=QuestionType.select,
                    required=True,
                    options=[
                        Option(option_name="Tag1"),
                        Option(option_name="Tag2"),
                        Option(option_name="Tag3"),
                    ],
                ),
                AnnotationQuestion(
                    question_number=4,
                    question="Select from dropdown",
                    question_type=QuestionType.dropdown,
                    required=True,
                    options=[
                        Option(option_name="Option1"),
                        Option(option_name="Option2"),
                        Option(option_name="Option3"),
                    ],
                ),
                AnnotationQuestion(
                    question_number=5,
                    question="Enter description",
                    question_type=QuestionType.input,
                    required=False,
                ),
            ],
        )

        template = create_template(integration_client, params)
        cleanup_templates(template.annotation_template_id)

        assert template is not None
        assert template.annotation_template_id is not None
        print(
            f"\n✓ Created template with all choice and input types: {template.annotation_template_id}"
        )

    def test_list_templates_and_all_data_types(self, integration_client, cleanup_templates):
        """
        Test listing templates for all data types and verify list functionality.
        Creates one template for video data type, then lists all data types.
        Tests: image, video, audio, document, text
        """
        # Create one template for video to test a different data type
        params = CreateTemplateParams(
            template_name=f"SDK_Test_Video_Template_{uuid.uuid4().hex[:8]}",
            data_type=DatasetDataType.video,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Is valid video?",
                    question_type=QuestionType.boolean,
                    required=True,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                )
            ],
        )

        created_template = create_template(integration_client, params)
        cleanup_templates(created_template.annotation_template_id)

        print(f"\n✓ Created video template: {created_template.annotation_template_id}")

        # Now list templates for all data types
        data_types = [
            DatasetDataType.image,
            DatasetDataType.video,
            DatasetDataType.audio,
            DatasetDataType.document,
            DatasetDataType.text,
        ]

        for data_type in data_types:
            templates = list_templates(integration_client, data_type)

            assert templates is not None
            assert isinstance(templates, list)
            print(
                f"✓ Listed {len(templates)} templates for {data_type.value} data type"
            )

            # Verify our created video template is in the list
            if data_type == DatasetDataType.video and len(templates) > 0:
                template_ids = [t.annotation_template_id for t in templates]
                assert (
                    created_template.annotation_template_id in template_ids
                ), "Newly created video template should appear in video list"


class TestTemplateValidationIntegration:
    """Integration tests for template validation errors"""

    def test_validation_errors(self, integration_client):
        """
        Test all validation errors in one test.
        Tests: geometric types without color, choice types without options
        """
        # Test 1: Bounding box without color
        params_bbox = CreateTemplateParams(
            template_name="Invalid_BBox_Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Draw box",
                    question_type=QuestionType.bounding_box,
                    required=True,
                    # Missing color - should fail validation
                )
            ],
        )

        with pytest.raises(
            ValueError,
            match="Color is required for bounding box, polygon, polyline, and dot questions",
        ):
            create_template(integration_client, params_bbox)

        print("\n✓ Validation correctly rejected bounding box without color")

        # Test 2: Polygon without color
        params_polygon = CreateTemplateParams(
            template_name="Invalid_Polygon_Template",
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
            create_template(integration_client, params_polygon)

        print("✓ Validation correctly rejected polygon without color")

        # Test 3: Dropdown without options
        params_dropdown = CreateTemplateParams(
            template_name="Invalid_Dropdown_Template",
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Select category",
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
            create_template(integration_client, params_dropdown)

        print("✓ Validation correctly rejected dropdown without options")

        # Test 4: Radio without options
        params_radio = CreateTemplateParams(
            template_name="Invalid_Radio_Template",
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
            create_template(integration_client, params_radio)

        print("✓ Validation correctly rejected radio without options")


class TestTemplatePropertiesIntegration:
    """Integration tests for template properties and operations"""

    @pytest.mark.skip(reason="Template update/delete operations not yet implemented - placeholder for future feature")
    def test_template_update_operations_not_implemented(self):
        """
        Placeholder test for template update operations.

        When update APIs are available, this test should verify:
        - update_name()
        - update_questions()
        - add_question()
        - remove_question()
        - delete_template()

        TODO: Implement when update APIs are available
        """
        pass

    def test_get_template_by_id(self, integration_client, cleanup_templates):
        """
        Test retrieving a template by ID.
        Creates a template and then fetches it by ID to verify retrieval.
        """
        from labellerr.core.annotation_templates.base import LabellerrAnnotationTemplate

        # Create a new template for this test
        template_name = f"SDK_Test_Fetch_Template_{uuid.uuid4().hex[:8]}"
        params = CreateTemplateParams(
            template_name=template_name,
            data_type=DatasetDataType.image,
            questions=[
                AnnotationQuestion(
                    question_number=1,
                    question="Test question for fetch",
                    question_type=QuestionType.boolean,
                    required=True,
                    options=[Option(option_name="Yes"), Option(option_name="No")],
                )
            ],
        )

        created_template = create_template(integration_client, params)
        template_id = created_template.annotation_template_id
        cleanup_templates(template_id)
        print(f"\n→ Created template for fetch test: {template_id}")

        # Fetch raw data from API
        raw_data = LabellerrAnnotationTemplate.get_annotation_template(
            integration_client, template_id
        )
        print(f"\n→ Raw API response keys: {list(raw_data.keys())}")

        # WORKAROUND: Due to a bug in LabellerrAnnotationTemplate.__new__/__init__,
        # we need to use the factory method from_annotation_template_data instead
        # of the direct constructor to properly populate the template properties.
        fetched_template = LabellerrAnnotationTemplate.from_annotation_template_data(
            integration_client, **raw_data
        )

        # Verify the fetched template
        assert fetched_template.annotation_template_id == template_id

        # Check if we successfully fetched the template
        print(
            f"✓ Successfully fetched template by ID: {fetched_template.annotation_template_id}"
        )

        # Verify properties are accessible
        print(f"  - Template name: {fetched_template.template_name}")
        print(f"  - Data type: {fetched_template.data_type}")
        print(f"  - Created by: {fetched_template.created_by}")
        print(f"  - Created at: {fetched_template.created_at}")

        # Verify questions
        if fetched_template.questions:
            print(f"  - Questions count: {len(fetched_template.questions)}")
        else:
            print("  - Questions: None")

        # Add assertions to ensure properties are not None
        assert (
            fetched_template.template_name is not None
        ), "Template name should not be None"
        assert fetched_template.data_type is not None, "Data type should not be None"
        assert fetched_template.questions is not None, "Questions should not be None"

        print(
            "\n✓ Template fetch test completed successfully - verified we can retrieve templates by ID"
        )
