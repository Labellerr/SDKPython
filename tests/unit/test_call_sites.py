"""
Unit tests that every request call site goes out through ``client.make_request``:
the client's own auth headers, no ``email_id``/``clientid`` header, and a URL built
from ``client.base_url``. A mocked session stands in for the network.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from labellerr import LabellerrClient, Settings
from labellerr.core.annotation_templates import list_templates
from labellerr.core.connectors import (
    LabellerrConnection,
    LabellerrGCSConnection,
    LabellerrS3Connection,
    delete_connection,
    list_connections,
)
from labellerr.core.datasets import LabellerrDataset, list_datasets
from labellerr.core.datasets.utils import connect_local_files
from labellerr.core.projects import create_project
from labellerr.core.projects.utils import get_direct_upload_url
from labellerr.core.schemas import (
    AWSConnectionParams,
    AWSConnectionTestParams,
    ConnectionType,
    ConnectorType,
    DatasetDataType,
    GCSConnectionParams,
    GCSConnectionTestParams,
)

pytestmark = pytest.mark.unit

BASE = "https://sdk.example.test"
TOKEN = "tok-DO-NOT-LEAK-1234567890"


CONNECTION_BODY = {"response": {"connection_id": "conn-1", "connector": "s3"}}


class _Response:
    def __init__(self, body=None, status_code=200):
        self.status_code = status_code
        self._body = CONNECTION_BODY if body is None else body
        self.text = json.dumps(self._body)
        self.headers = {}

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _no_env_overrides(monkeypatch):
    monkeypatch.delenv("LABELLERR_BASE_URL", raising=False)
    monkeypatch.delenv("LABELLERR_ORIGIN", raising=False)


@pytest.fixture(params=["api_key", "bearer"])
def client(request):
    session = MagicMock()
    session.request.return_value = _Response()
    settings = Settings(base_url=BASE)
    if request.param == "api_key":
        built = LabellerrClient(
            "the-key", "the-secret", "client-7", settings=settings, session=session
        )
    else:
        built = LabellerrClient.from_access_token(
            TOKEN,
            "client-7",
            email_id="user@example.test",
            settings=settings,
            session=session,
        )
    built.kind = request.param
    built.fake_session = session
    return built


def _calls(client):
    return client.fake_session.request.call_args_list


def _check(client, call, path_prefix):
    """The request carries this client's auth, no banned headers, and our base URL."""
    method, url = call.args[0], call.args[1]
    headers = call.kwargs["headers"]
    lowered = {name.lower() for name in headers}

    assert url.startswith(f"{BASE}{path_prefix}"), url
    if client.kind == "api_key":
        assert headers["api_key"] == "the-key"
        assert headers["api_secret"] == "the-secret"
        assert "authorization" not in lowered
    else:
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert "api_key" not in lowered
        assert "api_secret" not in lowered
    assert "email_id" not in lowered
    assert "clientid" not in lowered
    assert headers["client_id"] == "client-7"
    assert "origin" in lowered
    assert "user-agent" in lowered
    return method, url, headers


def _lower(headers):
    return {name.lower(): value for name, value in headers.items()}


# --- connections -----------------------------------------------------------------


def test_connection_test_goes_through_the_client(client):
    connection = LabellerrConnection(
        client, "conn-1", connection_data={"connector": "s3", "name": "n"}
    )
    result = connection.test(
        "s3://bucket/x", ConnectionType._IMPORT, DatasetDataType.image
    )
    assert result == CONNECTION_BODY["response"]

    (call,) = _calls(client)
    method, url, headers = _check(client, call, "/connectors/connections/test")
    assert method == "POST"
    assert "client_id=client-7" in url
    assert call.kwargs["timeout"] == (30, 300)
    assert call.kwargs["files"]["connection_id"] == (None, "conn-1")
    assert "content-type" not in _lower(headers)


def test_s3_test_connection_goes_through_the_client(client):
    params = AWSConnectionTestParams(
        aws_access_key="AK",
        aws_secrets_key="SK",
        path="s3://bucket/x",
        data_type=DatasetDataType.image,
    )
    result = LabellerrS3Connection.test_connection(client, params)
    assert result == CONNECTION_BODY["response"]

    (call,) = _calls(client)
    _, _, headers = _check(client, call, "/connectors/connections/test")
    assert call.kwargs["timeout"] == (30, 300)
    assert call.kwargs["files"]["connector"] == (None, "s3")
    assert "content-type" not in _lower(headers)


def test_s3_create_connection_goes_through_the_client(client):
    params = AWSConnectionParams(
        aws_access_key="AK",
        aws_secrets_key="SK",
        path="s3://bucket/x",
        data_type=DatasetDataType.image,
        name="conn",
        description="d",
    )
    created = LabellerrS3Connection.create_connection(client, params)
    assert created is not None

    test_call, create_call = _calls(client)[:2]
    _check(client, test_call, "/connectors/connections/test")
    _, url, headers = _check(client, create_call, "/connectors/connections/create")
    assert "client_id=client-7" in url
    assert create_call.kwargs["files"]["name"] == (None, "conn")
    assert create_call.kwargs["timeout"] == (30, 300)
    assert "content-type" not in _lower(headers)


@pytest.fixture
def svc_account_file(tmp_path):
    path = tmp_path / "svc.json"
    path.write_text("{}")
    return str(path)


def test_gcs_test_connection_goes_through_the_client(client, svc_account_file):
    params = GCSConnectionTestParams(
        svc_account_json=svc_account_file,
        path="gs://bucket/x",
        data_type=DatasetDataType.image,
    )
    result = LabellerrGCSConnection.test_connection(client, params)
    assert result == CONNECTION_BODY["response"]

    (call,) = _calls(client)
    _, _, headers = _check(client, call, "/connectors/connections/test")
    assert call.kwargs["data"]["connector"] == "gcs"
    assert call.kwargs["files"][0][0] == "attachment_files"
    assert call.kwargs["timeout"] == (30, 300)
    assert "content-type" not in _lower(headers)


def test_gcs_create_connection_goes_through_the_client(client, svc_account_file):
    client.fake_session.request.return_value = _Response(
        {"response": {"connection_id": "conn-1", "connector": "gcs"}}
    )
    params = GCSConnectionParams(
        svc_account_json=svc_account_file,
        path="gs://bucket/x",
        data_type=DatasetDataType.image,
        name="conn",
        description="d",
    )
    created = LabellerrGCSConnection.create_connection(client, params)
    assert created is not None

    test_call, create_call = _calls(client)[:2]
    _check(client, test_call, "/connectors/connections/test")
    _, _, headers = _check(client, create_call, "/connectors/connections/create")
    assert create_call.kwargs["data"]["name"] == "conn"
    assert create_call.kwargs["data"]["client_id"] == "client-7"
    assert create_call.kwargs["timeout"] == (30, 300)
    assert "content-type" not in _lower(headers)


def test_get_connection_uses_the_client_base_url(client):
    LabellerrConnection(client, "conn-1")
    (call,) = _calls(client)
    _check(client, call, "/connectors/connections/conn-1/details")


def test_list_connections_sends_no_email_header(client):
    client.fake_session.request.return_value = _Response({"response": []})
    assert list_connections(client, ConnectorType._S3) == []
    (call,) = _calls(client)
    _check(client, call, "/connectors/connections/list")


def test_delete_connection_sends_no_email_header(client):
    client.fake_session.request.return_value = _Response({"response": "deleted"})
    assert delete_connection(client, "conn-1") == "deleted"
    (call,) = _calls(client)
    method, _, _ = _check(client, call, "/connectors/connections/delete")
    assert method == "POST"
    assert call.kwargs["json"] == {"connection_id": "conn-1"}


# --- datasets --------------------------------------------------------------------


def test_connect_local_files_goes_through_the_client(client):
    client.fake_session.request.return_value = _Response({"response": "ok"})
    result = connect_local_files(client, "client-7", ["a.png"], connection_id="tmp-1")
    assert result == {"response": "ok"}

    (call,) = _calls(client)
    method, url, _ = _check(client, call, "/connectors/connect/local")
    assert method == "POST"
    assert url.endswith("client_id=client-7")
    assert call.kwargs["json"] == {
        "file_names": ["a.png"],
        "temporary_connection_id": "tmp-1",
    }
    assert call.kwargs["timeout"] == (30, 300)


def test_connect_local_files_keeps_the_client_id_argument(client):
    client.fake_session.request.return_value = _Response({"response": "ok"})
    connect_local_files(client, "other-client", ["a.png"])
    (call,) = _calls(client)
    assert call.kwargs["headers"]["client_id"] == "other-client"
    assert "temporary_connection_id" not in call.kwargs["json"]


def _dataset(client):
    dataset = LabellerrDataset.__new__(LabellerrDataset)
    dataset.__init__(client, "ds-1", dataset_data={"data_type": "image"})
    return dataset


def test_dataset_sync_body_carries_the_caller_identity(client):
    client.fake_session.request.return_value = _Response({"response": "synced"})
    connection = LabellerrConnection(
        client, "conn-1", connection_data={"connector": "s3"}
    )
    client.fake_session.request.reset_mock()

    _dataset(client).sync_with_connection(
        SimpleNamespace(project_id="p-1"), "s3://b/x", "image", connection
    )

    (call,) = _calls(client)
    _, _, headers = _check(client, call, "/connectors/datasets/sync")
    body = json.loads(call.kwargs["data"])
    expected = "the-key" if client.kind == "api_key" else "user@example.test"
    assert body["email_id"] == expected
    assert _lower(headers)["content-type"] == "application/json"


def test_list_datasets_uses_the_client_base_url(client):
    client.fake_session.request.return_value = _Response(
        {"response": {"datasets": [], "last_dataset_id": None}}
    )
    list(list_datasets(client, DatasetDataType.image, "project", page_size=1))
    call = _calls(client)[0]
    _check(client, call, "/datasets/list")


# --- projects --------------------------------------------------------------------


def test_create_project_goes_through_the_client(client):
    client.fake_session.request.return_value = _Response(
        {"response": {"project_id": "proj-1"}}
    )
    params = SimpleNamespace(
        project_name="p",
        data_type="image",
        rotations=SimpleNamespace(model_dump=lambda: {"annotation_rotation_count": 1}),
        use_ai=False,
        created_by=None,
    )
    dataset = SimpleNamespace(files_count=3, dataset_id="ds-1")
    template = SimpleNamespace(annotation_template_id="tpl-1")

    with patch("labellerr.core.projects.LabellerrProject") as project_class:
        create_project(client, params, [dataset], template)

    project_class.assert_called_once_with(client, project_id="proj-1")
    (call,) = _calls(client)
    method, url, headers = _check(client, call, "/projects/create")
    assert method == "POST"
    assert "client_id=client-7" in url
    assert _lower(headers)["content-type"] == "application/json"
    assert json.loads(call.kwargs["data"])["attached_datasets"] == ["ds-1"]


def test_get_direct_upload_url_sets_no_second_origin(client):
    client.fake_session.request.return_value = _Response({"response": "https://up"})
    assert get_direct_upload_url(client, "f.json") == "https://up"

    (call,) = _calls(client)
    method, _, headers = _check(client, call, "/connectors/direct-upload-url")
    assert method == "GET"
    origins = [name for name in headers if name.lower() == "origin"]
    assert origins == ["origin"]
    assert headers["origin"] == client.settings.resolve_origin(client.credentials.kind)


# --- the other URL builders ------------------------------------------------------


def test_annotation_template_list_uses_the_client_base_url(client):
    client.fake_session.request.return_value = _Response(
        {"response": {"templates": []}}
    )
    try:
        list_templates(client, DatasetDataType.image)
    except Exception:  # response shape is not what this test is about
        pass
    call = _calls(client)[0]
    _check(client, call, "/annotations/list_questions_templates")


def test_users_use_the_client_base_url(client):
    client.fake_session.request.return_value = _Response({"response": "ok"})
    client.users.add_user_to_project("proj-1", "someone@example.test", role_id="r")
    call = _calls(client)[0]
    _check(client, call, "/users/add_user_to_project")


def test_client_base_url_is_read_at_request_time(client):
    """labellerr-mcp reassigns ``client.base_url``; call sites must follow it."""
    client.base_url = "https://elsewhere.example.test"
    client.fake_session.request.return_value = _Response({"response": []})
    list_connections(client, ConnectorType._S3)
    (call,) = _calls(client)
    assert call.args[1].startswith("https://elsewhere.example.test/connectors/")
