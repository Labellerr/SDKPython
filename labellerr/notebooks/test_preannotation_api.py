import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.projects.video_project import LabellerrProject

load_dotenv()

API_KEY = os.getenv("QA_API_KEY")
API_SECRET = os.getenv("QA_API_SECRET")
CLIENT_ID = os.getenv("QA_CLIENT_ID")

PROJECT_ID = "jeanna_mixed_aphid_93841"
VIDEO_JSON_FILE_PATH = r"C:\Users\yashs\Downloads\dumy_anotation.json"


def main():

    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    project = LabellerrProject(client=client, project_id=PROJECT_ID)

    response = project.upload_keyframe_preannotations(
        video_json_file_path=VIDEO_JSON_FILE_PATH
    )

    print(response)


if __name__ == "__main__":
    main()
