from typing import Any, Dict

from ..exceptions import LabellerrError
from ..utils import poll

from .. import constants
from ..client import LabellerrClient

__all__ = [
    "poll",
]


def validate_rotation_config(rotation_config: Dict[str, Any]) -> None:
    """
    Validates a rotation configuration.

    :param rotation_config: A dictionary containing the configuration for the rotations.
    :raises LabellerrError: If the configuration is invalid.
    """
    annotation_rotation_count = rotation_config.get("annotation_rotation_count")
    review_rotation_count = rotation_config.get("review_rotation_count")
    client_review_rotation_count = rotation_config.get("client_review_rotation_count")

    # Validate review_rotation_count
    if int(review_rotation_count or 0) != 1:
        raise LabellerrError("review_rotation_count must be 1")

    # Validate client_review_rotation_count based on annotation_rotation_count
    if (
        int(annotation_rotation_count or 0) == 0
        and int(client_review_rotation_count or 0) != 0
    ):
        raise LabellerrError(
            "client_review_rotation_count must be 0 when annotation_rotation_count is 0"
        )
    elif int(annotation_rotation_count or 0) == 1 and int(
        client_review_rotation_count or 0
    ) not in [0, 1]:
        raise LabellerrError(
            "client_review_rotation_count can only be 0 or 1 when annotation_rotation_count is 1"
        )
    elif (
        int(annotation_rotation_count or 0) > 1
        and int(client_review_rotation_count or 0) != 0
    ):
        raise LabellerrError(
            "client_review_rotation_count must be 0 when annotation_rotation_count is greater than 1"
        )


def get_direct_upload_url(
    client: LabellerrClient, file_name: str, purpose: str = "pre-annotations"
) -> str:
    """
    Get a direct upload URL for uploading files to GCS.

    :param file_name: Name of the file to upload
    :param client: LabellerrClient instance
    :param purpose: Purpose of the upload (default: "pre-annotations")
    :return: Direct upload URL
    """
    url = f"{constants.BASE_URL}/connectors/direct-upload-url"
    params = {  # noqa: F841
        "client_id": client.client_id,
        "purpose": purpose,
        "file_name": file_name,
    }

    try:
        response_data = client.make_request(
            "GET",
            url,
            extra_headers={"Origin": constants.ALLOWED_ORIGINS},
        )
        return response_data["response"]
    except Exception as e:
        raise LabellerrError(f"Failed to get direct upload URL: {str(e)}")
