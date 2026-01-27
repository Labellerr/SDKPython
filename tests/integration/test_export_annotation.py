"""
Integration tests for annotation export functionality.

This module tests the project.create_local_export() method for exporting
annotations from a project in COCO JSON format.

Requires environment variables:
    - API_KEY: Labellerr API key
    - API_SECRET: Labellerr API secret
    - CLIENT_ID: Labellerr client ID
    - PROJECT_ID: ID of an existing project with annotations to export

Note: This test requires an existing project with annotations. It does not
create or clean up projects/exports.
"""

import os

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects import LabellerrProject
from labellerr.core.schemas import CreateExportParams, ExportDestination

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
PROJECT_ID = os.getenv("PROJECT_ID")


@pytest.fixture
def export_annotation_fixture():
    """
    Fixture that creates a local export and returns the export ID.

    Creates a COCO JSON export with all annotation statuses:
    - review
    - r_assigned
    - client_review
    - cr_assigned
    - accepted

    Returns:
        str: The export ID (report_id) of the created export

    Raises:
        pytest.skip: If required environment variables are not set
    """
    # Initialize the client with your API credentials
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    project_id = PROJECT_ID

    export_config = CreateExportParams(
        export_name="Weekly Export",
        export_description="Export of all accepted annotations",
        export_format="coco_json",
        statuses=[
            "review",
            "r_assigned",
            "client_review",
            "cr_assigned",
            "accepted",
        ],
        export_destination=ExportDestination.LOCAL,
    )

    # Get project instance
    project = LabellerrProject(client=client, project_id=project_id)

    # Create export
    export = project.create_export(export_config)
    export_id = export.report_id
    # print(f"Local export created successfully. Export ID: {export_id}")

    return export_id


@pytest.mark.integration
def test_export_annotation(export_annotation_fixture):
    """
    Test that an export can be created and has a valid export ID.

    This test:
    1. Uses the export_annotation_fixture to create an export
    2. Verifies the export ID is not None
    3. Verifies the export ID is a string

    Note: This test does not verify export completion or download,
    only that the export was successfully initiated.
    """
    export_id = export_annotation_fixture

    assert export_id is not None
    assert isinstance(export_id, str)
