import os

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects import LabellerrProject

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
PROJECT_ID = os.getenv("PROJECT_ID")


@pytest.fixture
def export_annotation_fixture():
    # Initialize the client with your API credentials
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    project_id = PROJECT_ID

    export_config = {
        "export_name": "Weekly Export",
        "export_description": "Export of all accepted annotations",
        "export_format": "coco_json",
        "statuses": [
            "review",
            "r_assigned",
            "client_review",
            "cr_assigned",
            "accepted",
        ],
    }

    # Get project instance
    project = LabellerrProject(client=client, project_id=project_id)

    # Create export
    result = project.create_local_export(export_config)
    export_id = result["response"]["report_id"]
    # print(f"Local export created successfully. Export ID: {export_id}")

    return export_id


def test_export_annotation(export_annotation_fixture):
    export_id = export_annotation_fixture

    assert export_id is not None
    assert isinstance(export_id, str)
