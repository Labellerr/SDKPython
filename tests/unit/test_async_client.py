"""Unit tests for AsyncLabellerrClient request handling, with a fake aiohttp session."""

import asyncio
import json

import pytest

from labellerr import (
    AsyncLabellerrClient,
    AuthenticationError,
    LabellerrError,
    NotFoundError,
    RateLimitError,
    ServerError,
    Settings,
)

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, status, body="", headers=None):
        self.status = status
        self._text = body if isinstance(body, str) else json.dumps(body)
        self.headers = headers or {}

    async def text(self):
        return self._text

    async def json(self):
        return json.loads(self._text)


class _FakeRequestContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    closed = False

    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return _FakeRequestContext(self.response)

    async def close(self):
        self.closed = True


def _client(response, **kwargs):
    kwargs.setdefault("settings", Settings(base_url="https://gw.example.test"))
    client = AsyncLabellerrClient(access_token="tok", **kwargs)
    client._session = _FakeSession(response)
    return client


def _run(coro):
    return asyncio.run(coro)


def test_success_returns_json():
    client = _client(_FakeResponse(200, {"response": {"a": 1}}))
    assert _run(client._request("GET", "https://x")) == {"response": {"a": 1}}


def test_success_without_json_raises():
    client = _client(_FakeResponse(200, "<html>"))
    with pytest.raises(LabellerrError, match="Expected JSON"):
        _run(client._request("GET", "https://x"))


def test_4xx_json_body_is_kept():
    # The old code raised inside ``try/except Exception`` and so replaced the JSON
    # body with the raw text; the parsed body must survive.
    body = {"message": "bad input", "error_code": "SOMETHING"}
    client = _client(_FakeResponse(400, body))
    with pytest.raises(LabellerrError) as info:
        _run(client._request("GET", "https://x"))
    assert info.value.args[0] == {"error": body, "code": 400}
    assert isinstance(info.value.args[0]["error"], dict)
    assert info.value.response_body == body and info.value.status_code == 400


def test_4xx_text_body():
    client = _client(_FakeResponse(404, "Not Found"))
    with pytest.raises(NotFoundError) as info:
        _run(client._request("GET", "https://x"))
    assert info.value.args[0] == {"error": "Not Found", "code": 404}


def test_error_code_maps_the_class():
    client = _client(_FakeResponse(403, {"error_code": "TOKEN_INVALID"}))
    with pytest.raises(AuthenticationError):
        _run(client._request("GET", "https://x"))


def test_5xx_shape_and_request_id():
    client = _client(_FakeResponse(500, "boom"))
    with pytest.raises(ServerError) as info:
        _run(client._request("GET", "https://x", request_id="rid"))
    assert info.value.args[0] == {
        "status": "internal server error",
        "message": "Please contact support with the request tracking id",
        "request_id": "rid",
        "error": "boom",
    }


def test_429_retry_after():
    client = _client(_FakeResponse(429, {"m": 1}, {"retry-after": "4"}))
    with pytest.raises(RateLimitError) as info:
        _run(client._request("GET", "https://x"))
    assert info.value.retry_after == 4.0


def test_handle_response_wrapper():
    client = _client(_FakeResponse(200))
    assert _run(client._handle_response(_FakeResponse(201, {"ok": 1}))) == {"ok": 1}
    with pytest.raises(LabellerrError) as info:
        _run(client._handle_response(_FakeResponse(422, {"m": "x"})))
    assert info.value.args[0] == {"error": {"m": "x"}, "code": 422}


def test_get_dataset_sends_workspace_as_client_id_and_uses_base_url():
    client = _client(_FakeResponse(200, {"response": {}}))
    _run(client.get_dataset("ws-1", "ds-1"))
    method, url, kwargs = client._session.calls[0]
    assert method == "GET" and url == "https://gw.example.test/datasets/ds-1"
    headers = kwargs["headers"]
    assert headers["client_id"] == "ws-1"
    assert headers["Authorization"] == "Bearer tok"
    assert [k for k in headers if k.lower() == "origin"] == ["origin"]
    assert headers["origin"] == "https://sdk.labellerr.com"
    assert {"clientid", "email_id"}.isdisjoint(k.lower() for k in headers)


def test_connect_local_files_uses_base_url():
    client = _client(_FakeResponse(200, {"response": {}}))
    _run(client.connect_local_files("ws-1", ["a.jpg"]))
    _, url, kwargs = client._session.calls[0]
    assert url == "https://gw.example.test/connectors/connect/local"
    assert kwargs["headers"]["source"] == "sdk-async"


def test_from_access_token_methods_are_still_decorated_and_work():
    client = AsyncLabellerrClient.from_access_token(
        "tok", settings=Settings(base_url="https://gw.example.test")
    )
    client._session = _FakeSession(_FakeResponse(200, {"response": "u"}))
    assert _run(client.get_direct_upload_url("f.jpg", "ws")) == "u"
    assert hasattr(AsyncLabellerrClient.get_direct_upload_url, "__wrapped__")
