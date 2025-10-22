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


def pre_annotation_uploading(
    api_key, api_secret, client_id, project_id, annotation_format, annotation_file
):

    client = LabellerrClient(api_key, api_secret)
    try:
        # Upload and wait for processing to complete
        result = client.upload_preannotation_by_project_id(
            project_id, client_id, annotation_format, annotation_file
        )
        # Check the final status
        if result["response"]["status"] == "completed":
            print("Pre-annotations processed successfully")
            # Access additional metadata if needed
            metadata = result["response"].get("metadata", {})
            print("metadata", metadata)
    except LabellerrError as e:
        print(f"Pre-annotation upload failed: {str(e)}")
