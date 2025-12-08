import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects.video_project import LabellerrProject

# Load environment variables from .env file
load_dotenv(r"D:\Professional\Labellerr_SDK\dev.env")

API_KEY = os.getenv("QA_API_KEY")
API_SECRET = os.getenv("QA_API_SECRET")
CLIENT_ID = os.getenv("QA_CLIENT_ID")

# Validate that all required credentials are present
if not API_KEY:
    raise ValueError("QA_API_KEY is not set")
if not API_SECRET:
    raise ValueError("QA_API_SECRET is not set")
if not CLIENT_ID:
    raise ValueError("QA_CLIENT_ID is not set")

PROJECT_ID = "jeanna_mixed_aphid_93841"
VIDEO_JSON_FILE_PATH = r"D:\Professional\Labellerr_SDK\dummy_annotation.json"


def main():

    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    project = LabellerrProject(client=client, project_id=PROJECT_ID)

    print(project.project_id)

    response = project.upload_preannotations(
        annotation_format="video_json", annotation_file=VIDEO_JSON_FILE_PATH
    )
    print(response)


if __name__ == "__main__":
    main()
