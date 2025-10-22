import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "SDKPython"))
)

# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

from SDKPython.labellerr.client import LabellerrClient
from SDKPython.labellerr.exceptions import LabellerrError


def export_project(api_key, api_secret, client_id, project_id):
    """Exports a project using the Labellerr SDK."""

    client = LabellerrClient(api_key, api_secret)
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
    try:
        result = client.create_local_export(project_id, client_id, export_config)

        export_id = result["response"]["report_id"]
        print(f"Local export created successfully. Export ID: {export_id}")
    except LabellerrError as e:
        print(f"Local export creation failed: {str(e)}")
