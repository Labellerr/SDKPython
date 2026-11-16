"""Regression tests for review findings: typed errors, list_projects, users, headers."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from labellerr import AuthenticationError, LabellerrClient
from labellerr.core import constants
from labellerr.core.datasets.utils import connect_local_files
from labellerr.core.exceptions import InvalidProjectError, NotFoundError, ServerError
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


def _projects(n):
    return {"response": [{"project_id": f"p{i}"} for i in range(n)]}


def test_list_projects_skips_not_found_and_invalid_projects():
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c"
    client.make_request.return_value = _projects(4)

    def build(_client, project_id):
        if project_id == "p0":
            raise NotFoundError("gone")
        if project_id == "p1":
            raise InvalidProjectError("old")
        if project_id == "p2":
            raise ServerError("broken project", status_code=500)
        return project_id

    with patch("labellerr.core.projects.LabellerrProject", side_effect=build):
        assert list_projects(client) == ["p3"]


def test_list_projects_propagates_an_expired_token():
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c"
    client.make_request.return_value = _projects(2)
    with patch(
        "labellerr.core.projects.LabellerrProject",
        side_effect=AuthenticationError("expired"),
    ):
        with pytest.raises(AuthenticationError):
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
