"""Regression tests for review findings: typed errors, list_projects, users, headers."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from labellerr import AuthenticationError, LabellerrClient
from labellerr.core import constants
from labellerr.core.datasets.utils import connect_local_files
from labellerr.core.exceptions import InvalidProjectError, ServerError
from labellerr.core.projects import list_projects
from labellerr.core.projects.utils import get_direct_upload_url

pytestmark = pytest.mark.unit


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)
        self.headers = {}

    def json(self):
        return self._body


def _client(response=None):
    session = MagicMock(spec=requests.Session)
    if response is not None:
        session.request.return_value = response
    return LabellerrClient("k", "s", "c", session=session)


def test_legacy_constants_are_lazy_and_unknown_names_raise():
    assert "BASE_URL" not in vars(constants)
    with pytest.raises(AttributeError):
        constants.NOPE


def test_typed_error_survives_get_direct_upload_url():
    client = _client(_Response(401, {"error_code": "TOKEN_INVALID", "message": "x"}))
    with pytest.raises(AuthenticationError):
        get_direct_upload_url(client, "f.json")


def _projects(n, null_status=()):
    return {
        "response": {
            "projects": [
                {
                    "project_id": f"p{i}",
                    "status_code": None if f"p{i}" in null_status else 300,
                }
                for i in range(n)
            ]
        }
    }


def _list_client(response):
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c"
    client.make_request.return_value = response
    return client


def test_list_projects_skips_rows_without_a_document_and_invalid_projects():
    client = _list_client(_projects(4, null_status={"p0"}))

    def build(_client, project_id, **_kw):
        if project_id == "p1":
            raise InvalidProjectError("unknown data type")
        return project_id

    with patch("labellerr.core.projects.LabellerrProject", side_effect=build):
        assert list_projects(client) == ["p2", "p3"]


def test_list_projects_logs_how_many_were_skipped(caplog):
    client = _list_client(_projects(3, null_status={"p0"}))

    with patch(
        "labellerr.core.projects.LabellerrProject",
        side_effect=lambda _client, project_id, **_kw: project_id,
    ):
        with caplog.at_level("WARNING", logger="labellerr.core.projects"):
            list_projects(client)

    assert "skipped 1 of 3 projects" in caplog.text


@pytest.mark.parametrize(
    "error",
    [ServerError("boom", status_code=500), AuthenticationError("expired")],
)
def test_list_projects_raises_errors_from_the_list_request(error):
    # The list is the only request; its errors are raised, not turned into [].
    client = _list_client(None)
    client.make_request.side_effect = error
    with pytest.raises(type(error)):
        list_projects(client)


def test_each_client_has_its_own_users_object():
    a, b = _client(), _client()
    assert a.users.client is a
    assert b.users.client is b


def test_connect_local_files_omits_client_id_header_when_none():
    client = MagicMock()
    client.base_url = "https://x.test"
    connect_local_files(client, None, ["a.jpg"])
    assert client.make_request.call_args.kwargs["extra_headers"] is None
    connect_local_files(client, "c9", ["a.jpg"])
    assert client.make_request.call_args.kwargs["extra_headers"] == {"client_id": "c9"}
