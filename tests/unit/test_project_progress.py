"""Unit tests for project progress: ProjectProgress, project.progress() and
list_projects_with_progress()."""

import copy
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from labellerr.core.exceptions import NotFoundError, ServerError
from labellerr.core.projects import (
    LabellerrProject,
    ProjectWithProgress,
    list_projects_with_progress,
)
from labellerr.core.schemas import ProjectProgress

pytestmark = pytest.mark.unit

# Shape of GET /projects/workflow and of row["stats"]["workflow"] on dev, plus the
# "finished" field the backend adds.
WORKFLOW = {
    "file_count": 1000,
    "counts": {"None": 50, "assigned": 20, "review": 30, "accepted": 880},
    "unmapped": 2,
    "stages": {
        "annotation": {"queued": 50, "working": 20, "rework": 3},
        "review": {"queued": 30, "working": 5, "rework": 1},
        "client_review": {"queued": 0, "working": 0, "rework": 0},
    },
    "done": 880,
    "blocked": 10,
    "finished": 999,
    "computed_at": 1795710641023,
}


def _workflow(**overrides):
    workflow = copy.deepcopy(WORKFLOW)
    workflow.update(overrides)
    return workflow


def _client(response=None):
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c"
    client.make_request.return_value = response
    return client


def _row(project_id, status_code=300, **extra):
    row = {"project_id": project_id, "data_type": "image", "status_code": status_code}
    row.update(extra)
    return row


def _list(*rows):
    return {"response": {"projects": list(rows)}}


# ProjectProgress


def test_project_progress_parses_the_api_response():
    progress = ProjectProgress.model_validate(WORKFLOW)

    assert progress.file_count == 1000
    assert progress.counts["accepted"] == 880
    assert progress.unmapped == 2
    assert progress.stages.annotation.queued == 50
    assert progress.stages.review.working == 5
    assert progress.stages.client_review.rework == 0
    assert progress.done == 880
    assert progress.blocked == 10
    assert progress.finished == 999
    assert progress.computed_at == 1795710641023


def test_percent_complete_rounds_down():
    # 999 of 1000 is 99.9%: it must not say 100 before every file is finished.
    assert ProjectProgress.model_validate(WORKFLOW).percent_complete == 99


def test_percent_complete_is_zero_without_files():
    progress = ProjectProgress.model_validate(_workflow(file_count=0, finished=0))
    assert progress.percent_complete == 0


@pytest.mark.parametrize(
    "file_count, finished, expected",
    [(1000, 1000, True), (1000, 999, False), (0, 0, False)],
)
def test_is_complete(file_count, finished, expected):
    progress = ProjectProgress.model_validate(
        _workflow(file_count=file_count, finished=finished)
    )
    assert progress.is_complete is expected


def test_unknown_fields_are_ignored():
    progress = ProjectProgress.model_validate(_workflow(new_api_field={"x": 1}))
    assert not hasattr(progress, "new_api_field")


def test_finished_is_required():
    workflow = _workflow()
    del workflow["finished"]
    with pytest.raises(ValidationError):
        ProjectProgress.model_validate(workflow)


# project.progress()


def _project(client):
    return LabellerrProject(
        client,
        "p1",
        project_data={"project_id": "p1", "data_type": "image", "status_code": 300},
    )


def test_progress_calls_the_workflow_endpoint():
    client = _client({"response": WORKFLOW})
    _project(client).progress()

    client.make_request.assert_called_once()
    method, url = client.make_request.call_args[0][:2]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert method == "GET"
    assert parsed.path == "/projects/workflow"
    assert query["project_id"] == ["p1"]
    assert query["client_id"] == ["c"]
    assert query["uuid"] == [client.make_request.call_args[1]["request_id"]]


def test_progress_returns_project_progress():
    progress = _project(_client({"response": WORKFLOW})).progress()

    assert isinstance(progress, ProjectProgress)
    assert progress.finished == 999
    assert progress.percent_complete == 99


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("Project Not Exist"),
        ServerError("counting failed", status_code=503),
    ],
)
def test_progress_raises_api_errors(error):
    client = _client()
    project = _project(client)
    client.make_request.side_effect = error
    with pytest.raises(type(error)):
        project.progress()


# list_projects_with_progress()


def test_list_projects_with_progress_requests_stats_and_archived_projects():
    client = _client(_list())
    list_projects_with_progress(client)

    query = parse_qs(urlparse(client.make_request.call_args[0][1]).query)
    assert query["include_stats"] == ["true"]
    assert query["include_archived"] == ["true"]
    assert query["client_id"] == ["c"]


def test_list_projects_with_progress_pairs_each_project_with_its_progress():
    client = _client(
        _list(
            _row("p0", stats={"workflow": WORKFLOW, "attention": {"tier": "low"}}),
            _row("p1", stats={"workflow": _workflow(finished=1000)}),
        )
    )

    result = list_projects_with_progress(client)

    assert [type(item) for item in result] == [ProjectWithProgress] * 2
    assert [item.project.project_id for item in result] == ["p0", "p1"]
    assert [item.progress.percent_complete for item in result] == [99, 100]
    project, progress = result[0]
    assert isinstance(project, LabellerrProject)
    assert isinstance(progress, ProjectProgress)


def test_list_projects_with_progress_is_none_when_not_counted_yet():
    client = _client(
        _list(
            _row("p0", stats={"workflow": None, "computed_at": None}),
            _row("p1", stats=None),
            _row("p2"),
        )
    )

    result = list_projects_with_progress(client)

    assert [item.project.project_id for item in result] == ["p0", "p1", "p2"]
    assert [item.progress for item in result] == [None, None, None]


def test_list_projects_with_progress_skips_rows_with_null_status_code():
    client = _client(
        _list(
            _row("p0", stats={"workflow": WORKFLOW}),
            _row("p1", status_code=None, stats={"workflow": None}),
        )
    )

    result = list_projects_with_progress(client)

    assert [item.project.project_id for item in result] == ["p0"]


def test_list_projects_with_progress_applies_page_size():
    client = _client(
        _list(*[_row(f"p{i}", stats={"workflow": WORKFLOW}) for i in range(3)])
    )

    result = list_projects_with_progress(client, page_size=2)

    assert [item.project.project_id for item in result] == ["p0", "p1"]


def test_list_projects_with_progress_makes_one_request():
    client = _client(
        _list(*[_row(f"p{i}", stats={"workflow": WORKFLOW}) for i in range(5)])
    )

    list_projects_with_progress(client)

    assert client.make_request.call_count == 1
