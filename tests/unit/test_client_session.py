"""Unit tests for LabellerrClient: retry policy, sessions and make_request. No network."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from urllib3.exceptions import (
    ConnectTimeoutError,
    NewConnectionError,
    ProtocolError,
    ReadTimeoutError,
)
from urllib3.util.retry import Retry

from labellerr import LabellerrClient, RateLimitError, ServerError
from labellerr.core.client import RETRY_METHODS, build_retry

pytestmark = pytest.mark.unit

URL = "https://api.example.test/x"


class _Response:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = {"response": "ok"} if body is None else body
        self.text = str(self._body)
        self.headers = headers or {}

    def json(self):
        return self._body


def _retry_of(client):
    return client._session.get_adapter("https://api.labellerr.com").max_retries


# --- Retry policy ----------------------------------------------------------------


def test_mounted_retry_policy():
    client = LabellerrClient("k", "s", "c")
    try:
        for prefix in ("https://api.labellerr.com", "http://localhost"):
            retry = client._session.get_adapter(prefix).max_retries
            assert isinstance(retry, Retry)
            assert set(retry.allowed_methods) == {
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
            }
            assert "POST" not in retry.allowed_methods
            assert set(retry.status_forcelist) == {429, 500, 502, 503, 504}
            assert retry.raise_on_status is False
            assert retry.respect_retry_after_header is False
            assert retry.total == 3
    finally:
        client.close()


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_post_is_not_retried_on_status(status):
    retry = build_retry()
    assert retry.is_retry("POST", status) is False
    assert retry.is_retry("PATCH", status) is False
    assert retry.is_retry("GET", status) is True


def test_post_is_not_retried_on_a_read_error():
    retry = build_retry()
    for error in (
        ReadTimeoutError(None, URL, "read timed out"),
        ProtocolError("Connection aborted.", ConnectionResetError()),
    ):
        with pytest.raises(type(error)):
            retry.increment("POST", URL, error=error)
        # Idempotent methods are retried on the same error.
        assert retry.increment("GET", URL, error=error).total == 2


def test_connection_errors_are_retried_for_every_method():
    retry = build_retry()
    for error in (
        NewConnectionError(None, "connection refused"),
        ConnectTimeoutError(None, URL, "connect timed out"),
    ):
        for method in ("POST", "GET", "PATCH"):
            assert retry.increment(method, URL, error=error).total == 2


def test_retry_methods_constant():
    assert RETRY_METHODS == frozenset({"HEAD", "GET", "PUT", "DELETE", "OPTIONS"})


# --- Responses after retries run out are mapped, not RetryError -------------------


def test_exhausted_5xx_becomes_server_error():
    session = MagicMock(spec=requests.Session)
    session.request.return_value = _Response(503, {"message": "down"})
    client = LabellerrClient("k", "s", "c", session=session)
    with pytest.raises(ServerError) as info:
        client.make_request("GET", URL, request_id="rid")
    assert info.value.status_code == 503 and info.value.request_id == "rid"


def test_429_becomes_rate_limit_error():
    session = MagicMock(spec=requests.Session)
    session.request.return_value = _Response(
        429, {"message": "slow"}, {"Retry-After": "3"}
    )
    client = LabellerrClient("k", "s", "c", session=session)
    with pytest.raises(RateLimitError) as info:
        client.make_request("POST", URL)
    assert info.value.retry_after == 3.0


# --- Sessions --------------------------------------------------------------------


def test_injected_session_is_used_as_is_and_not_closed():
    session = MagicMock(spec=requests.Session)
    session.request.return_value = _Response()
    client = LabellerrClient("k", "s", "c", session=session)
    assert client.make_request("GET", URL) == {"response": "ok"}
    session.request.assert_called_once()
    session.mount.assert_not_called()
    client.close()
    session.close.assert_not_called()
    with LabellerrClient("k", "s", "c", session=session):
        pass
    session.close.assert_not_called()


def test_own_session_is_closed():
    client = LabellerrClient("k", "s", "c")
    session = client._session
    with patch.object(session, "close") as close:
        client.close()
    close.assert_called_once()
    assert client._session is None


def test_no_pooling_uses_requests_directly():
    client = LabellerrClient("k", "s", "c", enable_connection_pooling=False)
    assert client._session is None
    with patch(
        "labellerr.core.client.requests.request", return_value=_Response()
    ) as request:
        client.make_request("GET", URL)
    request.assert_called_once()


# --- make_request ----------------------------------------------------------------


def _request_kwargs(client, *args, **kwargs):
    with patch(
        "labellerr.core.client.requests.request", return_value=_Response()
    ) as request:
        result = client.make_request(*args, **kwargs)
    return result, request.call_args


@pytest.fixture
def client():
    return LabellerrClient("k", "s", "c", enable_connection_pooling=False)


def test_make_request_default_timeout(client):
    _, call = _request_kwargs(client, "GET", URL)
    assert call.kwargs["timeout"] == 30


def test_make_request_passes_timeout_params_and_body(client):
    _, call = _request_kwargs(
        client,
        "POST",
        URL,
        timeout=(5, 120),
        params={"a": 1},
        json={"b": 2},
    )
    assert call.args == ("POST", URL)
    assert call.kwargs["timeout"] == (5, 120)
    assert call.kwargs["params"] == {"a": 1} and call.kwargs["json"] == {"b": 2}


def test_make_request_raw_response(client):
    result, _ = _request_kwargs(client, "GET", URL, handle_response=False)
    assert isinstance(result, _Response)


def test_make_request_merges_extra_and_explicit_headers(client):
    _, call = _request_kwargs(
        client,
        "POST",
        URL,
        extra_headers={"content-type": "application/json"},
        headers={"X-Trace": "1", "Origin": "https://o.example.test"},
    )
    headers = call.kwargs["headers"]
    assert headers["api_key"] == "k" and headers["content-type"] == "application/json"
    assert headers["X-Trace"] == "1"
    assert [k for k in headers if k.lower() == "origin"] == ["Origin"]


def test_make_request_without_client_id_still_authenticates():
    client = LabellerrClient.from_access_token(
        "tok", None, enable_connection_pooling=False
    )
    _, call = _request_kwargs(client, "GET", URL)
    assert call.kwargs["headers"]["Authorization"] == "Bearer tok"
    assert "client_id" not in call.kwargs["headers"]
