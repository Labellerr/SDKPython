import uuid
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrSam2:
    def __init__(self, client: "LabellerrClient"):
        self.client = client

    def create_job_from_annotations(
        self, project_id: str, file_id: str, email_id: str
    ) -> Dict[str, Any]:
        """
        Create a SAM2 job from annotations.

        :param project_id: The ID of the project.
        :param file_id: The ID of the file.
        :param email_id: The email ID of the user.
        :return: A dictionary containing job_ids and a message.
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.client.base_url}/sam2/create_job_from_annotations"
            f"?client_id={self.client.client_id}&project_id={project_id}&uuid={unique_id}"
        )

        payload = {
            "file_id": file_id,
            "project_id": project_id,
            "email_id": email_id,
        }

        response = self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            json=payload,
        )
        return response.get("response", None)
