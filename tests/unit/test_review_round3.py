"""Regression tests for the third review of PR #57: polling, network errors, request IDs."""

import asyncio
import inspect
import pathlib
import socket
from unittest.mock import MagicMock

import aiohttp
import pytest
import requests

from labellerr import (
    APIConnectionError,
    APITimeoutError,
    AsyncLabellerrClient,
    AuthenticationError,
    JobTimeoutError,
    LabellerrClient,
    LabellerrError,
    NotFoundError,
    RateLimitError,
    ServerError,
    Settings,
)
from labellerr.core import client_utils
from labellerr.core import utils as poll_utils
from labellerr.core.datasets.image_dataset import ImageDataset
from labellerr.core.exports import Export
from labellerr.core.projects.image_project import ImageProject
from labellerr.core.schemas.exports import CreateExportParams, ExportDestination
from labellerr.core.utils import DEFAULT_POLL_TIMEOUT, poll

pytestmark = pytest.mark.unit

REPO = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://gw.example.test"


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    # The tests poll every 0.01 s; the SDK's floor is 0.5 s.
    monkeypatch.setattr(poll_utils, "MIN_POLL_INTERVAL", 0.0)


def _mock_client():
    client = MagicMock()
    client.client_id = "client-1"
    client.base_url = BASE
    return client


# --- 1. poll() re-raises everything except transient errors -------------------------


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("expired", status_code=401),
        NotFoundError("gone", status_code=404),
        LabellerrError("bad request", status_code=400),
        ValueError("bug in the poll function"),
    ],
)
def test_poll_raises_non_transient_errors_at_once(error):
    function = MagicMock(side_effect=error)
    seen = []

    with pytest.raises(type(error)):
        poll(function, lambda r: True, interval=0.01, on_exception=seen.append)

    assert function.call_count == 1
    assert seen == [error]


@pytest.mark.parametrize(
    "error",
    [
        ServerError("503", status_code=503),
        RateLimitError("429", status_code=429),
        APIConnectionError("refused"),
        APITimeoutError("slow"),
        requests.exceptions.ConnectionError("refused"),
    ],
)
def test_poll_retries_transient_errors(error):
    function = MagicMock(side_effect=[error, error, "done"])

    assert poll(function, lambda r: r == "done", interval=0.01) == "done"
    assert function.call_count == 3


def test_poll_without_any_result_raises_job_timeout_from_the_last_error():
    error = ServerError("503", status_code=503)
    function = MagicMock(side_effect=error)

    with pytest.raises(JobTimeoutError) as exc:
        poll(function, lambda r: True, interval=0.01, max_retries=3)

    assert function.call_count == 3
    assert exc.value.__cause__ is error


def test_poll_without_any_result_times_out_on_the_deadline():
    function = MagicMock(side_effect=APIConnectionError("refused"))

    with pytest.raises(JobTimeoutError, match="timed out"):
        poll(function, lambda r: True, interval=0.01, timeout=0.05)


def test_poll_timeout_returns_the_last_result():
    function = MagicMock(return_value={"status_code": 100})

    result = poll(function, lambda r: False, interval=0.01, timeout=0.05)

    assert result == {"status_code": 100}


# --- 2. status() of datasets, projects and exports ----------------------------------


def _dataset(client):
    return ImageDataset(client, "ds-1", dataset_data={"data_type": "image"})


def _project(client):
    return ImageProject(client, "proj-1", project_data={"data_type": "image"})


def _export(client):
    project = _project(client)
    project.check_export_status = MagicMock(
        side_effect=lambda ids: client.make_request("GET", "export-status")
    )
    return Export("rep-1", project)


TARGETS = {"dataset": _dataset, "project": _project, "export": _export}
DONE = {
    "dataset": {"response": {"status_code": 300}},
    "project": {"response": {"status_code": 300}},
    "export": {
        "response": [
            {"report_id": "rep-1", "is_completed": True, "export_status": "Created"}
        ]
    },
}


@pytest.mark.parametrize("kind", TARGETS)
@pytest.mark.parametrize("timeout", [DEFAULT_POLL_TIMEOUT, 5, None])
@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("Token expired", status_code=401),
        NotFoundError("Not found", status_code=404),
    ],
)
def test_status_raises_auth_and_not_found_errors_at_once(kind, timeout, error):
    client = _mock_client()
    client.make_request.side_effect = error

    with pytest.raises(type(error)):
        TARGETS[kind](client).status(interval=0.01, timeout=timeout)

    assert client.make_request.call_count == 1


@pytest.mark.parametrize("kind", TARGETS)
def test_status_retries_transient_errors(kind):
    client = _mock_client()
    client.make_request.side_effect = [
        ServerError("503", status_code=503),
        APIConnectionError("refused"),
        DONE[kind],
    ]

    result = TARGETS[kind](client).status(interval=0.01)

    assert client.make_request.call_count == 3
    assert result == (DONE[kind] if kind == "export" else DONE[kind]["response"])


@pytest.mark.parametrize("kind", TARGETS)
def test_status_has_a_default_timeout(kind):
    status = inspect.signature(TARGETS[kind](_mock_client()).status)

    assert status.parameters["timeout"].default == DEFAULT_POLL_TIMEOUT == 3600.0
    assert set(status.parameters) == {"interval", "timeout", "max_retries"}


@pytest.mark.parametrize("kind", TARGETS)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"interval": 0.1},
        {"interval": 0},
        {"interval": -1},
        {"interval": float("nan")},
        {"interval": True},
        {"interval": "2"},
        {"timeout": -1},
        {"timeout": float("inf")},
    ],
)
def test_status_validates_polling_before_any_request(kind, kwargs, monkeypatch):
    monkeypatch.setattr(poll_utils, "MIN_POLL_INTERVAL", 0.5)
    client = _mock_client()

    with pytest.raises(LabellerrError, match="interval|timeout"):
        TARGETS[kind](client).status(**kwargs)

    client.make_request.assert_not_called()


def test_project_status_honours_timeout_and_max_retries():
    client = _mock_client()
    client.make_request.return_value = {"response": {"status_code": 100}}
    project = _project(client)

    assert project.status(interval=0.01, max_retries=2) == {"status_code": 100}
    assert client.make_request.call_count == 2
    assert project.status(interval=0.01, timeout=0.03) == {"status_code": 100}


def test_project_status_without_any_response_raises_job_timeout():
    client = _mock_client()
    client.make_request.side_effect = ServerError("503", status_code=503)

    with pytest.raises(JobTimeoutError):
        _project(client).status(interval=0.01, max_retries=2)


def test_wait_for_preannotation_job_retries_connection_errors():
    client = _mock_client()
    client.make_request.side_effect = [
        APIConnectionError("refused"),
        APITimeoutError("slow"),
        {"response": {"status": "completed"}},
    ]

    result = _project(client).wait_for_preannotation_job("job-1", interval=0.01)

    assert result == {"response": {"status": "completed"}}
    assert client.make_request.call_count == 3


# --- 3. Network errors are wrapped in APIConnectionError / APITimeoutError ----------


class _RaisingSession:
    def __init__(self, error):
        self.error = error
        self.headers = None

    def request(self, method, url, **kwargs):
        self.headers = kwargs["headers"]
        raise self.error


@pytest.mark.parametrize(
    "error, expected",
    [
        (requests.exceptions.ConnectionError("refused"), APIConnectionError),
        (requests.exceptions.ChunkedEncodingError("dropped"), APIConnectionError),
        (requests.exceptions.ReadTimeout("read"), APITimeoutError),
        (requests.exceptions.ConnectTimeout("connect"), APITimeoutError),
    ],
)
def test_make_request_wraps_network_errors(error, expected):
    session = _RaisingSession(error)
    client = LabellerrClient("k", "s", "c", session=session)

    with pytest.raises(expected) as exc:
        client.make_request(
            "GET", f"{BASE}/datasets/x?client_id=c&secret=hidden", request_id="rid-1"
        )

    assert isinstance(exc.value, APIConnectionError)
    assert isinstance(exc.value, LabellerrError)
    assert exc.value.__cause__ is error
    assert exc.value.request_id == "rid-1"
    assert session.headers[client_utils.CORRELATION_ID_HEADER] == "rid-1"
    assert "secret=hidden" not in str(exc.value)
    assert f"{BASE}/datasets/x" in str(exc.value)


def test_make_request_leaves_other_request_errors_alone():
    error = requests.exceptions.InvalidURL("bad url")
    client = LabellerrClient("k", "s", "c", session=_RaisingSession(error))

    with pytest.raises(requests.exceptions.InvalidURL):
        client.make_request("GET", "http://")


def _closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_make_request_connection_refused_is_api_connection_error():
    client = LabellerrClient(
        "k", "s", "c", settings=Settings(base_url=f"http://127.0.0.1:{_closed_port()}")
    )

    with pytest.raises(APIConnectionError) as exc:
        client.make_request("GET", f"{client.base_url}/ping", timeout=5)

    assert not isinstance(exc.value, APITimeoutError)
    assert exc.value.request_id


class _RaisingContext:
    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        raise self.error

    async def __aexit__(self, *exc):
        return False


class _RaisingAsyncSession:
    closed = False

    def __init__(self, error):
        self.error = error
        self.headers = None

    def request(self, method, url, **kwargs):
        self.headers = kwargs["headers"]
        return _RaisingContext(self.error)


@pytest.mark.parametrize(
    "error, expected",
    [
        (aiohttp.ServerDisconnectedError(), APIConnectionError),
        (aiohttp.ClientOSError(104, "reset"), APIConnectionError),
        (aiohttp.ClientPayloadError("truncated"), APIConnectionError),
        (asyncio.TimeoutError(), APITimeoutError),
        (aiohttp.ServerTimeoutError("read timeout"), APITimeoutError),
    ],
)
def test_async_request_wraps_network_errors(error, expected):
    client = AsyncLabellerrClient("k", "s", settings=Settings(base_url=BASE))
    session = _RaisingAsyncSession(error)
    client._session = session  # type: ignore[assignment]

    with pytest.raises(expected) as exc:
        asyncio.run(client._request("GET", f"{BASE}/x?uuid=1", request_id="rid-2"))

    assert isinstance(exc.value, LabellerrError)
    assert exc.value.__cause__ is error
    assert exc.value.request_id == "rid-2"
    assert session.headers[client_utils.CORRELATION_ID_HEADER] == "rid-2"
    assert "uuid=1" not in str(exc.value)


def test_async_connection_refused_is_api_connection_error():
    base = f"http://127.0.0.1:{_closed_port()}"

    async def call():
        async with AsyncLabellerrClient(
            "k", "s", settings=Settings(base_url=base)
        ) as client:
            await client._request("GET", f"{base}/ping")

    with pytest.raises(APIConnectionError) as exc:
        asyncio.run(call())

    assert not isinstance(exc.value, APITimeoutError)


# --- 4. The uuid query parameter matches x-correlation-id ---------------------------


def test_import_users_sends_its_uuid_as_request_id():
    client = _mock_client()
    client.make_request.return_value = {"response": {"ok": True}}

    _project(client).import_users(_project(_mock_client()))

    url = client.make_request.call_args.args[1]
    request_id = client.make_request.call_args.kwargs["request_id"]
    assert f"uuid={request_id}" in url


def test_async_get_dataset_sends_its_uuid_as_request_id():
    client = AsyncLabellerrClient("k", "s", settings=Settings(base_url=BASE))
    calls = []

    async def fake_request(method, url, **kwargs):
        calls.append(kwargs)
        return {"response": {}}

    client._request = fake_request  # type: ignore[method-assign]
    asyncio.run(client.get_dataset("ws-1", "ds-1"))

    (kwargs,) = calls
    assert kwargs["request_id"] == kwargs["params"]["uuid"]


# --- 5. Typing ----------------------------------------------------------------------


def test_projects_base_is_type_checked():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")

    assert "labellerr/core/projects/base.py" in makefile


def test_export_without_report_id_raises():
    client = _mock_client()
    client.make_request.return_value = {"response": None}
    project = _project(client)
    project._fetch_slice_id = MagicMock(return_value="slice-1")
    config = CreateExportParams(
        export_name="n",
        export_description="d",
        export_format="json",
        statuses=["accepted"],
        export_destination=ExportDestination.S3,
        connection_id="conn-1",
    )

    with pytest.raises(LabellerrError, match="no report ID"):
        project.create_export(config)
