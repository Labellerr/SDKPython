"""Regression tests for the second review of the user-token sign-in work (PR #57)."""

import asyncio
import contextvars
import logging
import pathlib
import re
import uuid
import warnings
from unittest.mock import MagicMock, patch

import pytest
import requests

from labellerr import (
    ApiKeyCredentials,
    AsyncLabellerrClient,
    AuthenticationError,
    BearerTokenCredentials,
    LabellerrClient,
    LabellerrError,
    PermissionDeniedError,
    RateLimitError,
    Settings,
)
from labellerr.core import client_utils, constants
from labellerr.core.datasets import utils as dataset_utils
from labellerr.core.projects.image_project import ImageProject
from labellerr.core.projects.utils import get_direct_upload_url
from labellerr.core.schemas.base import DatasetDataType

pytestmark = pytest.mark.unit

PACKAGE = pathlib.Path(__file__).resolve().parents[2] / "labellerr"


# --- 1. Async create_dataset -------------------------------------------------------


def _async_client(response_body):
    client = AsyncLabellerrClient(
        "k", "s", settings=Settings(base_url="https://gw.example.test")
    )
    calls = []

    async def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response_body

    client._request = fake_request  # type: ignore[method-assign]
    return client, calls


@pytest.mark.parametrize("data_type", ["image", DatasetDataType.video])
def test_async_create_dataset_works(data_type):
    client, calls = _async_client({"response": {"dataset_id": "ds-1"}})
    config = {"client_id": "c1", "dataset_name": "n", "data_type": data_type}

    result = asyncio.run(client.create_dataset(config, connection_id="conn-1"))

    assert result == {"response": "success", "dataset_id": "ds-1"}
    method, url, kwargs = calls[0]
    assert (method, url) == ("POST", "https://gw.example.test/datasets/create")
    assert kwargs["json"]["data_type"] == data_type
    assert kwargs["json"]["connection_id"] == "conn-1"


@pytest.mark.parametrize("data_type", ["pdf", None, ""])
def test_async_create_dataset_rejects_an_unknown_data_type(data_type):
    client, calls = _async_client({})
    config = {"client_id": "c1", "dataset_name": "n", "data_type": data_type}

    with pytest.raises(LabellerrError, match="Invalid data_type"):
        asyncio.run(client.create_dataset(config, connection_id="conn-1"))
    assert calls == []


def test_unused_validate_data_type_decorators_are_gone():
    import labellerr.core.projects.validators as project_validators
    import labellerr.validators as validators

    assert not hasattr(validators, "validate_data_type")
    assert not hasattr(project_validators, "validate_data_type")
    assert not hasattr(constants, "DATA_TYPES")
    for path in PACKAGE.rglob("*.py"):
        if "mcp_server" in path.parts or path.name == "constants.py":
            continue  # constants.py names the typo in a docstring
        assert "constants.DATA_TYPES" not in path.read_text(encoding="utf-8"), path


# --- 5. get_direct_upload_url sends its params ---------------------------------------


def test_get_direct_upload_url_sends_params():
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c1"
    client.make_request.return_value = {"response": "https://upload"}

    assert get_direct_upload_url(client, "f.json", purpose="p") == "https://upload"

    method, url = client.make_request.call_args.args
    assert (method, url) == ("GET", "https://x.test/connectors/direct-upload-url")
    assert client.make_request.call_args.kwargs["params"] == {
        "client_id": "c1",
        "purpose": "p",
        "file_name": "f.json",
    }


# --- 7/8. Folder upload: fatal errors stop it, contextvars reach the workers ---------


@pytest.fixture
def image_folder(tmp_path, monkeypatch):
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setattr(constants, "FILE_BATCH_COUNT", 1)  # one batch per file
    return str(tmp_path)


def _config(folder):
    return {"client_id": "c1", "folder_path": folder, "data_type": "image"}


@pytest.mark.parametrize(
    "error", [AuthenticationError, PermissionDeniedError, RateLimitError]
)
def test_folder_upload_reraises_caller_errors(image_folder, error):
    with patch.object(
        dataset_utils, "__process_batch", side_effect=error("no"), create=True
    ):
        with pytest.raises(error):
            dataset_utils.upload_folder_files_to_dataset(
                MagicMock(), _config(image_folder)
            )


def test_folder_upload_still_collects_other_batch_failures(image_folder):
    calls = []

    def flaky(client, client_id, batch, connection_id):
        calls.append(batch)
        if len(calls) == 1:
            raise OSError("disk")
        return {"message": "200: Success"}

    with patch.object(dataset_utils, "__process_batch", side_effect=flaky, create=True):
        result = dataset_utils.upload_folder_files_to_dataset(
            MagicMock(), _config(image_folder)
        )

    assert len(result["success"]) == 2 and len(result["fail"]) == 1


def test_folder_upload_workers_see_the_callers_context_vars(image_folder):
    current_user = contextvars.ContextVar("current_user", default=None)
    seen = []

    def record(client, client_id, batch, connection_id):
        seen.append(current_user.get())
        return {"message": "200: Success"}

    current_user.set("alice")
    with patch.object(
        dataset_utils, "__process_batch", side_effect=record, create=True
    ):
        dataset_utils.upload_folder_files_to_dataset(MagicMock(), _config(image_folder))

    assert seen == ["alice"] * 3


# --- 9. Settings.base_url ----------------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    [
        "api.labellerr.com",
        "http://api.labellerr.com",
        "ftp://api.labellerr.com",
        "https://",
        "https:///path",
        "//api.labellerr.com",
    ],
)
def test_settings_rejects_unsafe_base_urls(base_url):
    with pytest.raises(ValueError, match="base_url"):
        Settings(base_url=base_url)


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.labellerr.com",
        "HTTPS://api.labellerr.com/v1/",
        "https://gw.example.test:8443",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://[::1]:3000",
    ],
)
def test_settings_accepts_https_and_local_http(base_url):
    assert Settings(base_url=base_url).base_url == base_url.rstrip("/")


def test_env_base_url_is_validated_too(monkeypatch):
    monkeypatch.setenv("LABELLERR_BASE_URL", "http://gateway.example.test")
    with pytest.raises(ValueError):
        Settings.from_env()


# --- 10. x-correlation-id on async requests ------------------------------------------


def test_async_request_sends_its_request_id():
    from tests.unit.test_async_client import _client, _FakeResponse

    client = _client(_FakeResponse(500, {"message": "boom"}))
    with pytest.raises(LabellerrError) as info:
        asyncio.run(client._request("GET", "https://x"))

    _, _, kwargs = client._session.calls[0]
    sent = kwargs["headers"]["x-correlation-id"]
    assert sent and info.value.request_id == sent


# --- 12. Unexpected 2xx/3xx are not "internal server error" ------------------------


@pytest.mark.parametrize("status", [202, 204, 302])
def test_unexpected_status_is_not_called_a_server_error(status):
    error = client_utils.error_from_response(status, "", None, "rid")
    assert type(error) is LabellerrError
    assert error.args[0]["status"] == "unexpected response"
    assert error.args[0]["code"] == status
    assert error.args[0]["request_id"] == "rid"
    assert "internal server error" not in str(error)


def test_5xx_text_is_unchanged():
    error = client_utils.error_from_response(503, {"m": 1}, None, "rid")
    assert error.args[0]["status"] == "internal server error"


# --- 13. Credentials: Bearer prefix and non-ASCII -----------------------------------


@pytest.mark.parametrize("token", ["Bearer xyz", "bearer xyz", "BEARER   xyz"])
def test_bearer_prefix_is_removed(token):
    assert BearerTokenCredentials(token).auth_headers() == {
        "Authorization": "Bearer xyz"
    }
    assert BearerTokenCredentials(lambda: token).auth_headers() == {
        "Authorization": "Bearer xyz"
    }


def test_bearer_alone_is_rejected():
    with pytest.raises(AuthenticationError):
        BearerTokenCredentials("Bearer ")
    with pytest.raises(AuthenticationError):
        BearerTokenCredentials(lambda: "Bearer  ").auth_headers()


@pytest.mark.parametrize(
    "build",
    [
        lambda: BearerTokenCredentials("tök"),
        lambda: BearerTokenCredentials(lambda: "tök").auth_headers(),
        lambda: ApiKeyCredentials("kéy", "s"),
        lambda: ApiKeyCredentials("k", "sécret"),
        lambda: LabellerrClient("kéy", "s", "c"),
    ],
)
def test_non_ascii_credentials_are_rejected_up_front(build):
    with pytest.raises(AuthenticationError, match="non-ASCII") as info:
        build()
    assert "ö" not in str(info.value) and "é" not in str(info.value)


# --- 16. Read-only credential attributes --------------------------------------------


@pytest.mark.parametrize("make", [LabellerrClient, AsyncLabellerrClient])
@pytest.mark.parametrize("name", ["api_key", "api_secret", "access_token"])
def test_credential_attributes_are_read_only(make, name):
    client = make("k", "s", "c") if make is LabellerrClient else make("k", "s")
    with pytest.raises(AttributeError):
        setattr(client, name, "other")


def test_credential_attributes_reflect_the_credentials():
    key_client = LabellerrClient("k", "s", "c")
    assert (key_client.api_key, key_client.api_secret) == ("k", "s")
    assert key_client.access_token is None

    token_client = AsyncLabellerrClient(access_token="tok")
    assert token_client.access_token == "tok"
    assert token_client.api_key is None and token_client.api_secret is None


# --- 17. secret_values ------------------------------------------------------------


def test_secret_values():
    assert ApiKeyCredentials("k", "s").secret_values() == ("k", "s")
    assert BearerTokenCredentials("tok").secret_values() == ("tok",)


def test_secret_values_never_calls_the_provider():
    provider = MagicMock(return_value="fresh")
    creds = BearerTokenCredentials(provider)

    assert creds.secret_values() == ()
    provider.assert_not_called()

    creds.auth_headers()
    assert creds.secret_values() == ("fresh",)
    assert provider.call_count == 1


# --- 18. Header values ----------------------------------------------------------


def test_header_numbers_and_uuids_become_strings():
    value = uuid.uuid4()
    merged = client_utils.merge_headers({"a": "1"}, {"n": 7, "f": 1.5, "u": value})
    assert merged == {"a": "1", "n": "7", "f": "1.5", "u": str(value)}


@pytest.mark.parametrize("value", [{"x": 1}, ["x"], object()])
def test_other_header_values_are_rejected_clearly(value):
    with pytest.raises(TypeError, match="'X-Thing' must be a string"):
        client_utils.merge_headers({}, {"X-Thing": value})


def test_make_request_rejects_a_bad_header_before_sending():
    session = MagicMock(spec=requests.Session)
    client = LabellerrClient("k", "s", "c", session=session)
    with pytest.raises(TypeError):
        client.make_request("GET", "https://x.test", headers={"X-Thing": {"a": 1}})
    session.request.assert_not_called()


# --- 19. Deprecated constants --------------------------------------------------------


@pytest.mark.parametrize("name", ["BASE_URL", "ALLOWED_ORIGINS"])
def test_legacy_constants_warn(name):
    with pytest.warns(DeprecationWarning, match=name):
        getattr(constants, name)


def test_other_constants_do_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert constants.DEFAULT_BASE_URL


# --- 15. Logging --------------------------------------------------------------------


def test_sdk_has_no_root_logger_calls():
    pattern = re.compile(
        r"\blogging\.(debug|info|warning|error|exception|critical|log)\("
    )
    offenders = [
        str(path)
        for path in PACKAGE.rglob("*.py")
        if "mcp_server" not in path.parts
        and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_sdk_logging_leaves_an_unconfigured_root_logger_alone():
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()
    try:
        client = MagicMock()
        client.base_url = "https://x.test"
        client.client_id = "c1"
        client.make_request.return_value = {"response": {"status": "processing"}}
        project = ImageProject(client, "p1", project_data={"data_type": "image"})

        project.preannotation_job_status("job-1")  # logs at INFO

        assert root.handlers == []
    finally:
        root.handlers[:] = saved


def test_sdk_loggers_are_named_after_their_module(caplog):
    client = MagicMock()
    client.base_url = "https://x.test"
    client.client_id = "c1"
    client.make_request.return_value = {"response": {"status": "processing"}}
    project = ImageProject(client, "p1", project_data={"data_type": "image"})

    with caplog.at_level(logging.INFO, logger="labellerr"):
        project.preannotation_job_status("job-1")

    assert [r.name for r in caplog.records] == ["labellerr.core.projects.base"]
    assert caplog.records[0].getMessage() == "Pre-annotation job status: processing"
