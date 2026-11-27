import json
import logging
import uuid

from labellerr import LabellerrClient

from .. import schemas
from ..datasets import LabellerrDataset
from ..exceptions import (
    InvalidProjectError,
    LabellerrError,
)
from .audio_project import AudioProject as LabellerrAudioProject
from .document_project import DocucmentProject as LabellerrDocumentProject
from .image_project import ImageProject as LabellerrImageProject
from .video_project import VideoProject as LabellerrVideoProject
from .text_project import TextProject as LabellerrTextProject
from .base import LabellerrProject
from ..annotation_templates import LabellerrAnnotationTemplate
from typing import List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "LabellerrProject",
    "LabellerrAudioProject",
    "LabellerrDocumentProject",
    "LabellerrImageProject",
    "LabellerrVideoProject",
    "LabellerrTextProject",
    "ProjectWithProgress",
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
    url = f"{client.base_url}/projects/create?client_id={client.client_id}&uuid={unique_id}"

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

    response = client.make_request(
        "POST",
        url,
        extra_headers={"Content-Type": "application/json"},
        data=payload,
        request_id=unique_id,
    )

    return LabellerrProject(client, project_id=response["response"]["project_id"])


class ProjectWithProgress(NamedTuple):
    """A project and its last counted progress, from ``list_projects_with_progress``."""

    project: LabellerrProject
    progress: Optional[schemas.ProjectProgress]
    """The stored count as of ``progress.computed_at``; None if not counted yet."""


def _list_project_rows(
    client: "LabellerrClient", page_size: Optional[int], include_stats: bool
) -> List[Tuple[dict, LabellerrProject]]:
    """
    Fetch the project list in one request and build a project from each row.

    Returns ``(row, project)`` pairs, in list order. Rows with no project document
    (``status_code`` null) and rows with an unknown data type are skipped.
    """
    unique_id = str(uuid.uuid4())
    # include_archived=true: this list hides archived projects unless asked, and
    # list_projects has always returned them.
    url = (
        f"{client.base_url}/projects/detailed_list?client_id={client.client_id}"
        f"&include_archived=true"
    )
    if include_stats:
        url += "&include_stats=true"
    url += f"&uuid={unique_id}"

    response = client.make_request(
        "GET",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
    )

    # Limit the number of projects if page_size is specified
    projects_data = response["response"]["projects"]
    if page_size is not None and page_size > 0:
        projects_data = projects_data[:page_size]

    # Each row is the same project object GET /projects/project/{id} returns, so the
    # projects are built from the rows without another request.
    pairs = []
    for row in projects_data:
        # No project document: the row comes from SQL only and status_code is null.
        if row.get("status_code") is None:
            continue
        try:
            project = LabellerrProject(
                client, project_id=row["project_id"], project_data=row
            )
        except InvalidProjectError:
            # Unknown data type: skip it.
            continue
        pairs.append((row, project))

    skipped = len(projects_data) - len(pairs)
    if skipped:
        logger.warning(
            "list_projects skipped %d of %d projects "
            "(no project document or unknown data type)",
            skipped,
            len(projects_data),
        )
    return pairs


def list_projects(client: "LabellerrClient", page_size: Optional[int] = None):
    """
    Retrieves a list of projects associated with a client ID, archived projects
    included. The projects are built from the list in one request.

    :param client: The client instance.
    :param page_size: Optional limit on number of projects to return (default: None = all projects).
    :return: A list of LabellerrProject objects.
    """
    return [
        project
        for _row, project in _list_project_rows(client, page_size, include_stats=False)
    ]


def list_projects_with_progress(
    client: "LabellerrClient", page_size: Optional[int] = None
) -> List[ProjectWithProgress]:
    """
    Retrieves every project with its last counted progress, in one request.

    The same projects as ``list_projects``, each paired with its progress::

        for project, progress in list_projects_with_progress(client):
            print(
                project.project_name,
                progress.percent_complete if progress else "not counted yet",
            )

    ``progress`` is the stored count as of ``progress.computed_at``, not a live one.
    It is refreshed when the project's dashboard is opened, when the project is
    created or a dataset is attached or detached, and by the stats job at 08:00 and
    14:00 IST for projects with activity. It is None when the project hasn't been
    counted yet; call ``project.progress()`` for a live count.

    This request is slower than ``list_projects``, so use ``list_projects`` when
    progress isn't needed.

    :param client: The client instance.
    :param page_size: Optional limit on number of projects to return (default: None = all projects).
    :return: A list of ProjectWithProgress(project, progress) tuples.
    """
    results = []
    for row, project in _list_project_rows(client, page_size, include_stats=True):
        workflow = (row.get("stats") or {}).get("workflow")
        progress = (
            schemas.ProjectProgress.model_validate(workflow) if workflow else None
        )
        results.append(ProjectWithProgress(project, progress))
    return results


def delete_project(client: "LabellerrClient", project: LabellerrProject):
    """
    Deletes a project from the Labellerr API.

    :param client: The client instance.
    :param project: The project instance.
    :return: The response from the API.
    """
    unique_id = str(uuid.uuid4())
    url = f"{client.base_url}/projects/delete/{project.project_id}?client_id={client.client_id}&uuid={unique_id}"

    return client.make_request(
        "POST",
        url,
        extra_headers={"content-type": "application/json"},
        request_id=unique_id,
    )
