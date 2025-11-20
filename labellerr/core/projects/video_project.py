import os
import uuid
from typing import Any, Dict, List

from .. import constants
from ..exceptions import LabellerrError
from ..schemas import DatasetDataType, KeyFrame
from .base import LabellerrProject, LabellerrProjectMeta


class VideoProject(LabellerrProject):
    """
    Class for handling video project operations and fething multiple datasets.
    """

    def add_or_update_keyframes(
        self,
        file_id: str,
        keyframes: List[KeyFrame],
    ):
        """
        Links key frames to a file in a project.

        :param file_id: The ID of the file
        :param keyframes: List of KeyFrame objects to link
        :return: Response from the API
        """
        # Parameter validation
        if not isinstance(file_id, str):
            raise LabellerrError("file_id must be a str")

        if not isinstance(keyframes, list):
            raise LabellerrError("keyframes must be a list")

        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/add_update_keyframes?client_id={self.client.client_id}&uuid={unique_id}"

            body = {
                "project_id": self.project_id,
                "file_id": file_id,
                "keyframes": [
                    (kf.model_dump() if hasattr(kf, "model_dump") else kf)
                    for kf in keyframes
                ],
            }

            return self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                json=body,
            )
        except LabellerrError:
            raise
        except Exception as e:
            raise LabellerrError(f"Failed to link key frames: {str(e)}")

    def delete_keyframes(self, file_id: str, keyframes: List[int]):
        """
        Deletes key frames from a project.

        :param file_id: The ID of the file
        :param keyframes: List of key frame numbers to delete
        :return: Response from the API
        """
        # Parameter validation
        if not isinstance(file_id, str):
            raise LabellerrError("file_id must be a str")

        if not isinstance(keyframes, list):
            raise LabellerrError("keyframes must be a list")

        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/delete_keyframes?project_id={self.project_id}&uuid={unique_id}&client_id={self.client.client_id}"

            return self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                json={
                    "project_id": self.project_id,
                    "file_id": file_id,
                    "keyframes": keyframes,
                },
            )
        except LabellerrError:
            raise
        except Exception as e:
            raise LabellerrError(f"Failed to delete key frames: {str(e)}")

    def upload_keyframe_preannotations(self, video_json_file_path: str = None) -> Any:
        """
        Uploads pre-annotations for video project.

        Supports both the parent signature and a video-specific signature for backward compatibility.

        :param annotation_format: (Deprecated) The format of the preannotation data
        :param annotation_file: (Deprecated) The file path of the preannotation data
        :param conf_bucket: (Deprecated) Confidence bucket [low, medium, high]
        :param _async: (Deprecated) Whether to return a future object
        :param video_json_file_path: Path to the video JSON file containing pre-annotations
        :return: Response from the API
        """
        # Support both old and new signatures
        file_path = video_json_file_path

        # Parameter validation
        if not isinstance(file_path, str):
            raise LabellerrError("file_path must be a str")

        try:
            # Validate if the file exists
            if not os.path.exists(file_path):
                raise LabellerrError(f"File not found: {file_path}")

            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/upload_answers?project_id={self.project_id}&answer_format=video_json&client_id={self.client.client_id}&uuid={unique_id}"

            # Get file name from path
            file_name = os.path.basename(file_path)

            # Open file and prepare multipart form data
            with open(file_path, "rb") as f:
                files = [("file", (file_name, f, "application/json"))]
                payload: Dict[Any, Any] = {}

                response = self.client.make_request(
                    "POST",
                    url,
                    request_id=unique_id,
                    handle_response=False,
                    data=payload,
                    files=files,
                )

            return self.client.handle_upload_response(response, unique_id)
        except LabellerrError:
            raise
        except Exception as e:
            raise LabellerrError(f"Failed to upload pre-annotations: {str(e)}")


LabellerrProjectMeta._register(DatasetDataType.video, VideoProject)
