import json
import uuid

import requests
from labellerr import LabellerrClient

from .. import client_utils, constants, schemas
from ..datasets import LabellerrDataset
from ..exceptions import LabellerrError
from .audio_project import AudioProject as LabellerrAudioProject
from .document_project import DocucmentProject as LabellerrDocumentProject
from .image_project import ImageProject as LabellerrImageProject
from .video_project import VideoProject as LabellerrVideoProject
from .text_project import TextProject as LabellerrTextProject
from .base import LabellerrProject
from ..annotation_templates import LabellerrAnnotationTemplate
from typing import List
from concurrent.futures import ThreadPoolExecutor

__all__ = [
    "LabellerrProject",
    "LabellerrAudioProject",
    "LabellerrDocumentProject",
    "LabellerrImageProject",
    "LabellerrVideoProject",
    "LabellerrTextProject",
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

    # Validate response structure before accessing nested keys
    if not isinstance(response, dict):
        raise LabellerrError(
            f"Invalid API response type: expected dict, got {type(response)}"
        )

    if "response" not in response:
        raise LabellerrError(
            f"API response missing 'response' key. Response: {response}"
        )

    response_data = response["response"]
    if not isinstance(response_data, dict):
        raise LabellerrError(
            f"Invalid response data type: expected dict, got {type(response_data)}"
        )

    if "project_id" not in response_data:
        raise LabellerrError(
            f"API response missing 'project_id'. Response data: {response_data}"
        )

    project_id = response_data["project_id"]
    if not project_id:
        raise LabellerrError("API returned empty project_id")

    return LabellerrProject(client, project_id=project_id)


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

    # Validate response structure before accessing nested keys
    if not isinstance(response, dict):
        raise LabellerrError(
            f"Invalid API response type: expected dict, got {type(response)}"
        )

    if "response" not in response:
        raise LabellerrError(
            f"API response missing 'response' key. Response: {response}"
        )

    response_data = response["response"]
    if not isinstance(response_data, list):
        raise LabellerrError(
            f"Invalid response data type: expected list, got {type(response_data)}"
        )

    # Handle different response formats
    if isinstance(response, list):
        # Response is directly a list of projects
        projects = response
    elif isinstance(response, dict) and "response" in response:
        # Response is wrapped in a response object
        inner_response = response["response"]
        if isinstance(inner_response, list):
            # Inner response is directly a list
            projects = inner_response
        elif isinstance(inner_response, dict):
            # Inner response is a dict with projects key
            projects = inner_response.get("projects", [])
        else:
            projects = []
    else:
        # Fallback to empty list
        projects = []

    return [
        LabellerrProject(client, project_id=project["project_id"])
        for project in projects
    ]


    def _instantiate_project(project_data):
        try:
            # Validate project_data structure
            if not isinstance(project_data, dict):
                return None

            if "project_id" not in project_data:
                return None

            project = LabellerrProject(client, project_id=project_data["project_id"])
            return project
        except requests.exceptions.RetryError:  # Handling Dangling projects
            return None
        except LabellerrError:  # Handling Non-migrated projects
            return None
        except (KeyError, TypeError):  # Handle malformed project data
            return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        projects = [
            p
            for p in executor.map(_instantiate_project, response_data)
            if p is not None
        ]

    return projects

def delete_project(client: "LabellerrClient", project: LabellerrProject):
    """
    Deletes a project from the Labellerr API.

    :param client: The client instance.
    :param project: The project instance.
    :return: The response from the API.
    """
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/projects/delete/{project.project_id}?client_id={client.client_id}&uuid={unique_id}"

    return client.make_request(
        "POST",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
    )