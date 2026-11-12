"""Unit tests for user-token authentication (Authorization: Bearer instead of api_key/api_secret)."""

import pytest

from labellerr.core import client_utils, constants

pytestmark = pytest.mark.unit


def test_api_key_headers_are_unchanged():
    headers = client_utils.build_headers(api_key="k", api_secret="s", client_id=7)
    assert headers == {
        "api_key": "k",
        "api_secret": "s",
        "source": "sdk",
        "origin": constants.ALLOWED_ORIGINS,
        "client_id": "7",
    }


def test_access_token_replaces_key_and_secret():
    headers = client_utils.build_headers(api_key=None, api_secret=None, client_id=7, access_token="tok")
    assert headers["Authorization"] == "Bearer tok"
    assert "api_key" not in headers and "api_secret" not in headers
    assert headers["client_id"] == "7" and headers["clientid"] == "7" and headers["source"] == "sdk"


def test_access_token_wins_over_key_and_secret():
    headers = client_utils.build_headers(api_key="k", api_secret="s", access_token="tok")
    assert headers["Authorization"] == "Bearer tok"
    assert "api_key" not in headers and "api_secret" not in headers


def test_access_token_may_be_a_callable():
    calls = []

    def provider():
        calls.append(1)
        return f"tok{len(calls)}"

    assert client_utils.build_headers(access_token=provider)["Authorization"] == "Bearer tok1"
    assert client_utils.build_headers(access_token=provider)["Authorization"] == "Bearer tok2"


def test_none_valued_headers_are_dropped():
    headers = client_utils.build_headers(access_token="tok", extra_headers={"email_id": None, "x": "1"})
    assert "email_id" not in headers and headers["x"] == "1"


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_caller_id_prefers_email_then_api_key():
    assert client_utils.caller_id(_Obj(email_id="u@example.com", api_key="k")) == "u@example.com"
    assert client_utils.caller_id(_Obj(api_key="k")) == "k"
    assert client_utils.caller_id(_Obj(email_id=None, api_key=None)) is None


from unittest.mock import patch

from labellerr.core.client import LabellerrClient


class _Response:
    status_code = 200

    def json(self):
        return {"response": "ok"}


def _sent_headers(client):
    with patch("labellerr.core.client.requests.request", return_value=_Response()) as request:
        client.make_request("GET", "https://example.test/x")
    return request.call_args.kwargs["headers"]


def test_client_with_token_sends_bearer():
    client = LabellerrClient.from_access_token("tok", 7, email_id="u@example.com", enable_connection_pooling=False)
    headers = _sent_headers(client)
    assert headers["Authorization"] == "Bearer tok"
    assert "api_key" not in headers and "api_secret" not in headers
    assert client.email_id == "u@example.com" and client.api_key is None


def test_client_with_api_key_is_unchanged():
    client = LabellerrClient("k", "s", 7, enable_connection_pooling=False)
    headers = _sent_headers(client)
    assert headers["api_key"] == "k" and headers["api_secret"] == "s"
    assert "Authorization" not in headers
    assert client.access_token is None and client.email_id is None


import re
from pathlib import Path

import labellerr

CORE = Path(labellerr.__file__).parent / "core"


def _call_text(text, start):
    """Source of the call starting at `start` (index of the name), up to its matching ')'."""
    depth = 0
    for i in range(text.index("(", start), len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError("unbalanced call")


def test_every_build_headers_call_passes_the_access_token():
    missing = []
    for path in CORE.rglob("*.py"):
        if path.name == "client_utils.py":
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"client_utils\.build_headers\(", text):
            if "access_token=" not in _call_text(text, match.start()):
                missing.append(f"{path.relative_to(CORE)}:{text.count(chr(10), 0, match.start()) + 1}")
    assert missing == []


def test_no_call_site_sends_the_api_key_as_identity():
    offenders = []
    for path in CORE.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"email_id\W+(self\.)?client\.api_key", line):
                offenders.append(f"{path.relative_to(CORE)}:{number}")
    assert offenders == []


def test_list_connections_with_token_client_sends_bearer_and_email():
    from labellerr.core.connectors import list_connections

    client = LabellerrClient.from_access_token("tok", 7, email_id="u@example.com", enable_connection_pooling=False)
    with patch("labellerr.core.client.requests.request") as request:
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"response": []}
        list_connections(client, "s3")
    headers = request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok" and headers["email_id"] == "u@example.com"
    assert "api_key" not in headers


import importlib


def test_base_url_and_origin_default_to_production(monkeypatch):
    monkeypatch.delenv("LABELLERR_BASE_URL", raising=False)
    monkeypatch.delenv("LABELLERR_ORIGIN", raising=False)
    try:
        importlib.reload(constants)
        assert constants.BASE_URL == "https://api.labellerr.com"
        assert constants.ALLOWED_ORIGINS == "https://pro.labellerr.com"
    finally:
        importlib.reload(constants)


def test_base_url_and_origin_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("LABELLERR_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://mcp.labellerr.com")
    try:
        importlib.reload(constants)
        assert constants.BASE_URL == "https://gateway.example.test"
        assert constants.ALLOWED_ORIGINS == "https://mcp.labellerr.com"
    finally:
        monkeypatch.undo()
        importlib.reload(constants)
