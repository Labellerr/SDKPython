"""
Integration tests for export_layout / delivery_format.

Covers the combinations that ExportsCore must reject (EXPORT_CONSTRAINTS in
ExportsCore/models/create_export.py). Before export_layout and delivery_format
were added to CreateExportParams these were silently dropped, so every case
below was accepted by the backend.

Reads credentials from the SDKPython/.env file:
    LABELLERR_API_KEY, LABELLERR_API_SECRET, LABELLERR_CLIENT_ID,
    IMAGE_PROJECT_ID, VIDEO_PROJECT_ID, EXPORT_STATUSES (optional)

Run with:
    python -m pytest tests/integration/test_export_layout_delivery.py -v -s
"""

import os
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects import LabellerrProject
from labellerr.core.schemas import CreateExportParams

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.getenv("LABELLERR_API_KEY")
API_SECRET = os.getenv("LABELLERR_API_SECRET")
CLIENT_ID = os.getenv("LABELLERR_CLIENT_ID")
PROJECT_IDS = {
    "image": os.getenv("IMAGE_PROJECT_ID"),
    "video": os.getenv("VIDEO_PROJECT_ID"),
}
STATUSES = [
    s.strip()
    for s in os.getenv(
        "EXPORT_STATUSES", "review,r_assigned,client_review,cr_assigned,accepted"
    ).split(",")
    if s.strip()
]

# (case_id, data_type, export options) - every one of these must be rejected
INVALID_CASES = [
    # png requires per_file layout
    ("image_png_monolithic", "image", {
        "export_format": "png", "export_layout": "monolithic", "delivery_format": "data_file",
    }),
    # yolov11 requires per_file layout
    ("image_yolov11_monolithic", "image", {
        "export_format": "yolov11", "export_layout": "monolithic", "delivery_format": "data_file",
    }),
    # yolov11 requires archive delivery format
    ("image_yolov11_per_file_manifest", "image", {
        "export_format": "yolov11", "export_layout": "per_file", "delivery_format": "manifest",
    }),
    # monolithic only supports data_file
    ("image_json_monolithic_manifest", "image", {
        "export_format": "json", "export_layout": "monolithic", "delivery_format": "manifest",
    }),
    ("image_json_monolithic_archive", "image", {
        "export_format": "json", "export_layout": "monolithic", "delivery_format": "archive",
    }),
    # per_file only supports manifest / archive
    ("image_json_per_file_data_file", "image", {
        "export_format": "json", "export_layout": "per_file", "delivery_format": "data_file",
    }),
    # not a valid layout value
    ("image_unknown_layout", "image", {
        "export_format": "json", "export_layout": "per_page",
    }),
    # per_file only supports manifest / archive
    ("video_json_per_file_data_file", "video", {
        "export_format": "json", "export_layout": "per_file", "delivery_format": "data_file",
    }),
    # video auto-sets per_file, which does not support data_file
    ("video_json_default_layout_data_file", "video", {
        "export_format": "json", "delivery_format": "data_file",
    }),
    # monolithic only supports data_file
    ("video_json_monolithic_manifest", "video", {
        "export_format": "json", "export_layout": "monolithic", "delivery_format": "manifest",
    }),
]

# Sanity cases: valid combinations must still be accepted after the change
VALID_CASES = [
    ("image_json_monolithic_data_file", "image", {
        "export_format": "json", "export_layout": "monolithic", "delivery_format": "data_file",
    }),
    ("video_json_default_layout", "video", {"export_format": "json"}),
]


def _ids(cases):
    return [case_id for case_id, _, _ in cases]


def _build_params(case_id, options):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return CreateExportParams(
        export_name=f"SDK_Test_Layout_{case_id}_{timestamp}",
        export_description=f"Integration test export - {case_id}",
        statuses=STATUSES,
        **options,
    )


@pytest.fixture(scope="session")
def client():
    if not all([API_KEY, API_SECRET, CLIENT_ID]):
        pytest.skip(
            "Missing LABELLERR_API_KEY, LABELLERR_API_SECRET or LABELLERR_CLIENT_ID in .env"
        )
    return LabellerrClient(api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID)


@pytest.fixture(scope="session")
def projects(client):
    cache = {}

    def get(data_type):
        if not PROJECT_IDS[data_type]:
            pytest.skip(f"Missing {data_type.upper()}_PROJECT_ID in .env")
        if data_type not in cache:
            cache[data_type] = LabellerrProject(
                client=client, project_id=PROJECT_IDS[data_type]
            )
        return cache[data_type]

    return get


@pytest.mark.integration
class TestExportLayoutDeliveryRejected:
    """Each invalid layout/delivery combination must be rejected by the SDK or ExportsCore."""

    @pytest.mark.parametrize("case_id,data_type,options", INVALID_CASES, ids=_ids(INVALID_CASES))
    def test_invalid_combination_is_rejected(self, projects, case_id, data_type, options):
        project = projects(data_type)

        # Building the params is inside the block: unknown enum values fail in the SDK itself
        with pytest.raises(Exception) as exc_info:
            export = project.create_export(_build_params(case_id, options))
            print(f"\n✗ {case_id} was accepted: report_id={export.report_id}")

        print(f"\n✓ {case_id} rejected: {type(exc_info.value).__name__}: {exc_info.value}")


@pytest.mark.integration
class TestExportLayoutDeliveryAccepted:
    """Valid layout/delivery combinations must still create an export."""

    @pytest.mark.parametrize("case_id,data_type,options", VALID_CASES, ids=_ids(VALID_CASES))
    def test_valid_combination_is_accepted(self, projects, case_id, data_type, options):
        project = projects(data_type)

        export = project.create_export(_build_params(case_id, options))

        assert export.report_id, f"{case_id}: export report_id is empty"
        print(f"\n✓ {case_id} created: {export.report_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
