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
