"""Unit tests for credentials: API key and secret, or a user access token (Bearer)."""

import asyncio
import gc
import warnings
from unittest.mock import patch

import pytest

from labellerr import (
    ApiKeyCredentials,
    AsyncLabellerrClient,
    AuthenticationError,
    BearerTokenCredentials,
    Credentials,
    LabellerrClient,
    Settings,
)
from labellerr.core import client_utils

pytestmark = pytest.mark.unit

SECRET = "tok-DO-NOT-LEAK-1234567890"


@pytest.fixture(autouse=True)
def _no_env_overrides(monkeypatch):
    monkeypatch.delenv("LABELLERR_BASE_URL", raising=False)
    monkeypatch.delenv("LABELLERR_ORIGIN", raising=False)


class _Response:
    status_code = 200
    headers = {}

    def json(self):
        return {"response": "ok"}


def _sent_headers(client):
    with patch(
        "labellerr.core.client.requests.request", return_value=_Response()
    ) as request:
        client.make_request("GET", "https://example.test/x")
    return request.call_args.kwargs["headers"]


# --- Credentials classes ---------------------------------------------------------


def test_api_key_credentials_headers():
    creds = ApiKeyCredentials("k", "s")
    assert creds.kind == "api_key"
    assert creds.auth_headers() == {"api_key": "k", "api_secret": "s"}


@pytest.mark.parametrize(
    "key, secret",
    [(None, "s"), ("k", None), ("", "s"), ("k", "   "), (1, "s"), ("k", b"s")],
)
def test_api_key_credentials_reject_missing_or_blank(key, secret):
    with pytest.raises(AuthenticationError):
        ApiKeyCredentials(key, secret)


def test_bearer_credentials_headers():
    creds = BearerTokenCredentials("tok")
    assert creds.kind == "bearer"
    assert creds.auth_headers() == {"Authorization": "Bearer tok"}


@pytest.mark.parametrize("token", [None, "", "   ", 123, b"tok"])
def test_bearer_credentials_reject_empty_or_wrong_type(token):
    with pytest.raises(AuthenticationError):
        BearerTokenCredentials(token)


def test_bearer_provider_is_called_on_every_request():
    calls = []

    def provider():
        calls.append(1)
        return f"tok{len(calls)}"

    creds = BearerTokenCredentials(provider)
    assert creds.auth_headers() == {"Authorization": "Bearer tok1"}
    assert creds.auth_headers() == {"Authorization": "Bearer tok2"}


@pytest.mark.parametrize("value", [None, "", "  ", 42])
def test_bearer_provider_returning_no_token_raises(value):
    creds = BearerTokenCredentials(lambda: value)
    with pytest.raises(AuthenticationError):
        creds.auth_headers()


def test_async_def_provider_is_rejected_at_construction():
    async def provider():
        return "tok"

    with pytest.raises(AuthenticationError, match="async"):
        BearerTokenCredentials(provider)


def test_object_with_async_call_is_rejected_at_construction():
    class Provider:
        async def __call__(self):
            return "tok"

    with pytest.raises(AuthenticationError, match="async"):
        BearerTokenCredentials(Provider())


def test_provider_returning_a_coroutine_raises_and_closes_it():
    async def make_token():
        return "tok"

    creds = BearerTokenCredentials(lambda: make_token())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(AuthenticationError, match="awaitable"):
            creds.auth_headers()
        gc.collect()
    assert not [w for w in caught if "never awaited" in str(w.message)]


def test_base_credentials_is_abstract():
    with pytest.raises(NotImplementedError):
        Credentials().auth_headers()


# --- Secrets never leak into messages or reprs -----------------------------------


def test_repr_shows_only_the_kind():
    for creds in (
        BearerTokenCredentials(SECRET),
        BearerTokenCredentials(lambda: SECRET),
        ApiKeyCredentials(SECRET, SECRET),
    ):
        assert SECRET not in repr(creds) and SECRET not in str(creds)
        assert creds.kind in repr(creds)


def test_client_repr_of_credentials_hides_the_token():
    client = LabellerrClient.from_access_token(
        SECRET, "cid", enable_connection_pooling=False
    )
    assert SECRET not in repr(client.credentials)


@pytest.mark.parametrize(
    "build",
    [
        lambda: ApiKeyCredentials(SECRET, " "),
        lambda: ApiKeyCredentials(" ", SECRET),
        lambda: LabellerrClient(SECRET, SECRET, "cid", access_token=SECRET),
        lambda: LabellerrClient(SECRET, None, "cid"),
        lambda: BearerTokenCredentials(lambda: SECRET.encode()).auth_headers(),
    ],
)
def test_error_messages_never_contain_the_secret(build):
    with pytest.raises(AuthenticationError) as info:
        build()
    assert SECRET not in str(info.value)
    assert SECRET not in repr(info.value)
    assert all(SECRET not in str(arg) for arg in info.value.args)


# --- Sync client construction ----------------------------------------------------


def test_positional_api_key_construction_is_unchanged():
    client = LabellerrClient("key", "secret", "client_id")
    try:
        assert client.api_key == "key" and client.api_secret == "secret"
        assert client.client_id == "client_id"
        assert client.access_token is None and client.email_id is None
        assert isinstance(client.credentials, ApiKeyCredentials)
        assert client.base_url == "https://api.labellerr.com"
    finally:
        client.close()


def test_keyword_api_key_construction():
    client = LabellerrClient(
        api_key="k", api_secret="s", client_id="c", enable_connection_pooling=False
    )
    assert client.credentials.auth_headers() == {"api_key": "k", "api_secret": "s"}


def test_no_credentials_raises():
    with pytest.raises(AuthenticationError):
        LabellerrClient(None, None, "cid")


def test_empty_token_raises():
    with pytest.raises(AuthenticationError):
        LabellerrClient.from_access_token("", "cid")


def test_token_and_key_together_raise():
    with pytest.raises(AuthenticationError, match="one of"):
        LabellerrClient("k", "s", "cid", access_token="tok")


def test_credentials_and_token_together_raise():
    with pytest.raises(AuthenticationError, match="one of"):
        LabellerrClient(
            client_id="cid",
            access_token="tok",
            credentials=BearerTokenCredentials("tok"),
        )


def test_credentials_must_be_a_credentials_object():
    with pytest.raises(AuthenticationError):
        LabellerrClient(client_id="cid", credentials={"api_key": "k"})


def test_credentials_object_is_used():
    creds = BearerTokenCredentials("tok")
    client = LabellerrClient(
        client_id="cid", credentials=creds, enable_connection_pooling=False
    )
    assert client.credentials is creds
    assert client.access_token == "tok" and client.api_key is None


def test_api_key_credentials_object_fills_legacy_attributes():
    client = LabellerrClient(
        client_id="cid",
        credentials=ApiKeyCredentials("k", "s"),
        enable_connection_pooling=False,
    )
    assert client.api_key == "k" and client.api_secret == "s"
    assert client.access_token is None


def test_client_with_token_sends_bearer():
    client = LabellerrClient.from_access_token(
        "tok", 7, email_id="u@example.com", enable_connection_pooling=False
    )
    headers = _sent_headers(client)
    assert headers["Authorization"] == "Bearer tok"
    assert "api_key" not in headers and "api_secret" not in headers
    assert client.email_id == "u@example.com" and client.api_key is None
    assert client.access_token == "tok"


def test_client_with_token_provider_keeps_it_as_access_token():
    def provider():
        return "tok"

    client = LabellerrClient.from_access_token(
        provider, 7, enable_connection_pooling=False
    )
    assert client.access_token is provider
    assert _sent_headers(client)["Authorization"] == "Bearer tok"


def test_client_with_api_key_is_unchanged():
    client = LabellerrClient("k", "s", 7, enable_connection_pooling=False)
    headers = _sent_headers(client)
    assert headers["api_key"] == "k" and headers["api_secret"] == "s"
    assert headers["client_id"] == "7" and headers["source"] == "sdk"
    assert headers["origin"] == "https://pro.labellerr.com"
    assert "Authorization" not in headers
    assert client.access_token is None and client.email_id is None


def test_token_client_sends_no_clientid_or_email_header():
    client = LabellerrClient.from_access_token(
        "tok", 7, email_id="u@example.com", enable_connection_pooling=False
    )
    headers = _sent_headers(client)
    assert headers["client_id"] == "7"
    assert {"clientid", "email_id"}.isdisjoint(k.lower() for k in headers)


def test_headers_are_sent_without_a_client_id():
    client = LabellerrClient("k", "s", None, enable_connection_pooling=False)
    headers = _sent_headers(client)
    assert headers["api_key"] == "k" and "client_id" not in headers


def test_caller_identity():
    token_client = LabellerrClient.from_access_token(
        "tok", 7, email_id="u@example.com", enable_connection_pooling=False
    )
    key_client = LabellerrClient("k", "s", 7, enable_connection_pooling=False)
    no_email = LabellerrClient.from_access_token(
        "tok", 7, enable_connection_pooling=False
    )
    assert token_client.caller_identity == "u@example.com"
    assert key_client.caller_identity == "k"
    assert no_email.caller_identity is None
    with pytest.raises(AttributeError):
        key_client.caller_identity = "x"


def test_caller_id_helper_is_gone():
    assert not hasattr(client_utils, "caller_id")


# --- Async client construction ---------------------------------------------------


def test_async_client_with_token_sends_bearer():
    headers = AsyncLabellerrClient(access_token="tok")._build_headers(client_id="7")
    assert headers["Authorization"] == "Bearer tok" and headers["source"] == "sdk-async"
    assert headers["client_id"] == "7"
    assert "api_key" not in headers and "clientid" not in headers


def test_async_client_with_api_key_is_unchanged():
    client = AsyncLabellerrClient("k", "s")
    headers = client._build_headers(client_id="7")
    assert headers["api_key"] == "k" and headers["api_secret"] == "s"
    assert "Authorization" not in headers
    assert headers["origin"] == "https://pro.labellerr.com"
    assert client.api_key == "k" and client.access_token is None


def test_async_from_access_token():
    client = AsyncLabellerrClient.from_access_token(
        "tok", settings=Settings(base_url="https://gw.example.test/")
    )
    assert isinstance(client, AsyncLabellerrClient)
    assert isinstance(client.credentials, BearerTokenCredentials)
    assert client.base_url == "https://gw.example.test"
    assert client._build_headers()["Authorization"] == "Bearer tok"


def test_async_client_validation_matches_sync():
    async def provider():
        return "tok"

    with pytest.raises(AuthenticationError, match="async"):
        AsyncLabellerrClient(access_token=provider)
    with pytest.raises(AuthenticationError, match="async"):
        AsyncLabellerrClient.from_access_token(provider)
    with pytest.raises(AuthenticationError):
        AsyncLabellerrClient()
    with pytest.raises(AuthenticationError):
        AsyncLabellerrClient(access_token="")
    with pytest.raises(AuthenticationError, match="one of"):
        AsyncLabellerrClient("k", "s", access_token="tok")


def test_async_client_accepts_credentials_object():
    creds = ApiKeyCredentials("k", "s")
    client = AsyncLabellerrClient(credentials=creds)
    assert client.credentials is creds and client.api_key == "k"


def test_async_provider_called_per_request():
    tokens = iter(["a", "b"])
    client = AsyncLabellerrClient(access_token=lambda: next(tokens))

    async def run():
        return [client._build_headers()["Authorization"] for _ in range(2)]

    assert asyncio.run(run()) == ["Bearer a", "Bearer b"]


# --- Whitespace and control characters --------------------------------------------


def test_surrounding_whitespace_is_stripped_everywhere():
    keys = ApiKeyCredentials("key\n", " sec\r\n")
    assert keys.auth_headers() == {"api_key": "key", "api_secret": "sec"}
    assert BearerTokenCredentials("tok\n").auth_headers() == {
        "Authorization": "Bearer tok"
    }
    provider = BearerTokenCredentials(lambda: "  tok2\n")
    assert provider.auth_headers() == {"Authorization": "Bearer tok2"}


def test_embedded_control_character_is_rejected_without_echoing_it():
    with pytest.raises(AuthenticationError) as info:
        BearerTokenCredentials("abc-SECRETPART\ndef")
    assert "SECRETPART" not in str(info.value)
    with pytest.raises(AuthenticationError) as info:
        ApiKeyCredentials("key", "SECRETPART\x00x")
    assert "SECRETPART" not in str(info.value)
    with pytest.raises(AuthenticationError) as info:
        BearerTokenCredentials(lambda: "SECRETPART\r\nX-Evil: 1").token()
    assert "SECRETPART" not in str(info.value)


def test_provider_exception_becomes_authentication_error():
    def provider():
        raise RuntimeError("refresh failed for SECRETPART")

    with pytest.raises(AuthenticationError) as info:
        BearerTokenCredentials(provider).token()
    assert "SECRETPART" not in str(info.value)
    assert isinstance(info.value.__cause__, RuntimeError)
