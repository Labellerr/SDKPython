import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "SDKPython"))
)


# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

import uuid

import pytest

from labellerr import LabellerrClient, LabellerrError
from labellerr.core.projects import create_project


@pytest.fixture
def labellerr_client():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    return LabellerrClient(api_key, api_secret)


def create_project_all_option_type(
    api_key, api_secret, client_id, email, path_to_images
):
    """Creates a project with all option types using the Labellerr SDK."""

    client = LabellerrClient(api_key, api_secret)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "A sample dataset for image classification",
        "data_type": "image",
        "created_by": email,
        "project_name": "Testing_project-7",
        "annotation_guide": [
            {
                "question_number": 1,  # incremental series starting from 1
                "question": "Test",  # question name
                "question_id": "533bb0c8-fb2b-4394-a8e1-5042a944802f",  # random uuid
                "option_type": "polygon",
                "required": True,
                "options": [
                    {
                        "option_name": "#fe1236"
                    },  # give the hex code of some random color
                ],
            },
            {
                "question_number": 2,  # Pixel annotation for bounding box format
                "question": "Test2",
                "question_id": "533bb0c8-fb2b-4394-a8e1-5042a944808d",
                "option_type": "BoundingBox",
                "required": True,
                "options": [{"option_name": "#afe126"}],
            },
            {
                "question_number": 3,  # Classification question for simple input field
                "question": "Test-Input",
                "option_type": "input",
                "question_id": "81bc5c1a-5b95-4df2-8085-aca8d66a93ad",
                "required": True,
                "options": [],  # this will be empty array only
            },
            {
                "question_number": 4,  # Classification question for multi-select dropdown
                "question": "Multi-Test",
                "option_type": "select",
                "question_id": "971c5c1a-5b95-4df2-8085-aca8d66a0351",
                "required": True,
                "options": [
                    {
                        "option_id": "22b7942f-06ef-4293-9d73-d117eda8ec0d",
                        "option_name": "A",
                    },
                    {
                        "option_id": "15e0e903-ed8f-43ff-a841-a0638ff08153",
                        "option_name": "B",
                    },
                    {
                        "option_id": "c2e37dad-5034-4bed-920b-5fc14c4032e0",
                        "option_name": "C",
                    },
                ],
            },
            {
                "question_number": 5,  # Classification question for single-select dropdown
                "question": "Test-Dropdown",
                "option_type": "dropdown",
                "question_id": "456c5c1a-5b95-4df2-8085-aca8d66a03049",
                "required": True,
                "options": [
                    {
                        "option_id": "58k142f-06ef-4293-9d73-d117eda87254",
                        "option_name": "Sample A",
                    },
                    {
                        "option_id": "43t56903-ed8f-43ff-a841-a0638ff08856",
                        "option_name": "Sample B",
                    },
                ],
            },
            {
                "question_number": 6,  # Classification question for radio
                "question": "Radio test",
                "option_type": "radio",
                "question_id": "712v5c1a-5b95-4df2-8085-aca8d66a01048",
                "required": True,
                "options": [
                    {
                        "option_id": "916v24h-06ef-4293-9d73-d117eda81112",
                        "option_name": "1",
                    },
                    {
                        "option_id": "12ak879-ed8f-43ff-a841-a0638ff23115",
                        "option_name": "2",
                    },
                ],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }
    try:
        result = create_project(client, project_payload)
        print(
            f"[ALL OPTION TYPE] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:

        print(f"Project creation failed: {str(e)}")


def create_project_polygon_boundingbox_project(
    api_key, api_secret, client_id, email, path_to_images
):

    client = LabellerrClient(api_key, api_secret, client_id)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Dataset for object detection with polygon and bounding box annotations",
        "data_type": "image",
        "created_by": email,
        "project_name": "polygon_boundingbox_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Vehicle Detection",
                "question_id": str(uuid.uuid4()),
                "option_type": "polygon",
                "required": True,
                "options": [{"option_name": "#ff6b35"}],  # Orange for vehicles
            },
            {
                "question_number": 2,
                "question": "Person Detection",
                "question_id": str(uuid.uuid4()),
                "option_type": "BoundingBox",
                "required": True,
                "options": [{"option_name": "#4ecdc4"}],  # Teal for persons
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = client.projects.create_project(project_payload)
        print(
            f"[polygon_boundingbox] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")


def create_project_select_dropdown_radio(
    api_key, api_secret, client_id, email, path_to_images
):

    client = LabellerrClient(api_key, api_secret)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Dataset for multi-label image classification",
        "data_type": "image",
        "created_by": email,
        "project_name": "select_dropdown_radio_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Object Categories",
                "option_type": "select",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Animals"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Vehicles"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Buildings"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Nature"},
                ],
            },
            {
                "question_number": 2,
                "question": "Image Quality",
                "option_type": "dropdown",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "High Quality"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Medium Quality"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Low Quality"},
                ],
            },
            {
                "question_number": 3,
                "question": "Lighting Condition",
                "option_type": "radio",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Bright"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Dim"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Dark"},
                ],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = client.projects.create_project(project_payload)
        print(
            f"[select_dropdown_radio] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")


def create_project_polygon_input(api_key, api_secret, client_id, email, path_to_images):

    client = LabellerrClient(api_key, api_secret)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Medical images with detailed annotations and metadata",
        "data_type": "image",
        "created_by": email,
        "project_name": "polygon_input_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Anomaly Region",
                "question_id": str(uuid.uuid4()),
                "option_type": "polygon",
                "required": True,
                "options": [{"option_name": "#ff4757"}],  # Red for anomalies
            },
            {
                "question_number": 2,
                "question": "Anomaly Description",
                "option_type": "input",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [],
            },
            {
                "question_number": 3,
                "question": "Additional Notes",
                "option_type": "input",
                "question_id": str(uuid.uuid4()),
                "required": False,
                "options": [],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = client.projects.create_project(project_payload)
        print(
            f"[polygon_input_project] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")


def create_project_input_select_radio(
    api_key, api_secret, client_id, email, path_to_images, projects
):

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Dataset for evaluating and moderating image content",
        "data_type": "image",
        "created_by": email,
        "project_name": "input_select_radio_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Content Summary",
                "option_type": "input",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [],
            },
            {
                "question_number": 2,
                "question": "Content Categories",
                "option_type": "select",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Educational"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Entertainment"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Commercial"},
                    {"option_id": str(uuid.uuid4()), "option_name": "News"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Social"},
                ],
            },
            {
                "question_number": 3,
                "question": "Content Appropriateness",
                "option_type": "radio",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Appropriate"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Needs Review"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Inappropriate"},
                ],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = projects.create_project(project_payload)
        print(
            f"[input_select_radio] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")


def create_project_boundingbox_dropdown_input(
    api_key, api_secret, client_id, email, path_to_images
):

    client = LabellerrClient(api_key, api_secret)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Retail product images with bounding boxes and metadata",
        "data_type": "image",
        "created_by": email,
        "project_name": "boundingbox_dropdown_input_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Product Bounding Box",
                "question_id": str(uuid.uuid4()),
                "option_type": "BoundingBox",
                "required": True,
                "options": [{"option_name": "#2ed573"}],  # Green for products
            },
            {
                "question_number": 2,
                "question": "Product Category",
                "option_type": "dropdown",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Electronics"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Clothing"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Home & Garden"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Sports"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Books"},
                ],
            },
            {
                "question_number": 3,
                "question": "Product Name/Brand",
                "option_type": "input",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [],
            },
            {
                "question_number": 4,
                "question": "Product Condition Notes",
                "option_type": "input",
                "question_id": str(uuid.uuid4()),
                "required": False,
                "options": [],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = client.projects.create_project(project_payload)
        print(
            f"[boundingbox_dropdown_input] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")


def create_project_radio_dropdown(
    api_key, api_secret, client_id, email, path_to_images
):

    client = LabellerrClient(api_key, api_secret)

    project_payload = {
        "client_id": client_id,
        "dataset_name": "Testing_dataset",
        "dataset_description": "Simple dataset for quick image classification",
        "data_type": "image",
        "created_by": email,
        "project_name": "radio_dropdown_project",
        "annotation_guide": [
            {
                "question_number": 1,
                "question": "Image Type",
                "option_type": "radio",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Indoor"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Outdoor"},
                ],
            },
            {
                "question_number": 2,
                "question": "Primary Subject",
                "option_type": "dropdown",
                "question_id": str(uuid.uuid4()),
                "required": True,
                "options": [
                    {"option_id": str(uuid.uuid4()), "option_name": "Person"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Animal"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Object"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Landscape"},
                    {"option_id": str(uuid.uuid4()), "option_name": "Architecture"},
                ],
            },
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "autolabel": False,
        "folder_to_upload": path_to_images,
    }

    try:
        result = client.projects.create_project(project_payload)
        print(
            f"[radio_dropdown] Project ID: {result['project_id']['response']['project_id']}"
        )
    except LabellerrError as e:
        print(f"Project creation failed: {str(e)}")
