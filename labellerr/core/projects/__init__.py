import json
import uuid

from labellerr import LabellerrClient

from .. import client_utils, constants, schemas
from ..datasets import LabellerrDataset
from ..exceptions import LabellerrError
from .audio_project import AudioProject as LabellerrAudioProject
from .document_project import DocucmentProject as LabellerrDocumentProject
from .image_project import ImageProject as LabellerrImageProject
from .video_project import VideoProject as LabellerrVideoProject
from .base import LabellerrProject
from ..annotation_templates import LabellerrAnnotationTemplate
from typing import List

__all__ = [
    "LabellerrProject",
    "LabellerrAudioProject",
    "LabellerrDocumentProject",
    "LabellerrImageProject",
    "LabellerrVideoProject",
]


def create_project(
    client: "LabellerrClient",
    params: schemas.CreateProjectParams,
    datasets: List[LabellerrDataset],
    annotation_template: LabellerrAnnotationTemplate,
):
    """
    Orchestrates project creation by handling dataset creation, annotation guidelines,
    and final project setup.
    """

    if len(datasets) == 0:
        raise LabellerrError("At least one dataset is required")

    for dataset in datasets:
        if dataset.files_count == 0:
            raise LabellerrError(f"Dataset {dataset.dataset_id} has no files")

    attached_datasets = [dataset.dataset_id for dataset in datasets]

    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/projects/create?client_id={client.client_id}&uuid={unique_id}"

    payload = json.dumps(
        {
            "project_name": params.project_name,
            "attached_datasets": attached_datasets,
            "data_type": params.data_type,
            "annotation_template_id": annotation_template.annotation_template_id,
            "rotations": params.rotations.model_dump(),
            "use_ai": params.use_ai,
            "created_by": params.created_by,
        }
    )
    headers = client_utils.build_headers(
        api_key=client.api_key,
        api_secret=client.api_secret,
        client_id=client.client_id,
        extra_headers={
            "Content-Type": "application/json",
        },
    )

    response = client.make_request(
        "POST", url, headers=headers, data=payload, request_id=unique_id
    )

    return LabellerrProject(client, project_id=response["response"]["project_id"])


def list_projects(client: "LabellerrClient"):
    """
    Retrieves a list of projects associated with a client ID.

    :param client: The client instance.
    :return: A list of LabellerrProject objects.
    """
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/project_drafts/projects/detailed_list?client_id={client.client_id}&uuid={unique_id}"

    response = client.make_request(
        "GET",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
    )
    return [
        LabellerrProject(client, project_id=project["project_id"])
        for project in response["response"]["projects"]
    ]
