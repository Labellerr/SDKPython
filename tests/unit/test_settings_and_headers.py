"""Unit tests for Settings (base URL, origin, User-Agent) and client_utils.build_headers."""

import asyncio
import importlib
import subprocess
import sys

import pytest

import labellerr
from labellerr import (
    ApiKeyCredentials,
    AsyncLabellerrClient,
    BearerTokenCredentials,
    LabellerrClient,
    Settings,
)
from labellerr.core import client_utils, constants
from labellerr.core.settings import DEFAULT_USER_AGENT

pytestmark = pytest.mark.unit

KEY = ApiKeyCredentials("k", "s")
TOKEN = BearerTokenCredentials("tok")


@pytest.fixture(autouse=True)
def _no_env_overrides(monkeypatch):
    monkeypatch.delenv("LABELLERR_BASE_URL", raising=False)
    monkeypatch.delenv("LABELLERR_ORIGIN", raising=False)


# --- constants -------------------------------------------------------------------


def test_constants_hold_the_defaults():
    assert constants.DEFAULT_BASE_URL == "https://api.labellerr.com"
    assert constants.DEFAULT_ORIGIN == "https://pro.labellerr.com"
    assert constants.BASE_URL == "https://api.labellerr.com"
    assert constants.ALLOWED_ORIGINS == "https://pro.labellerr.com"
    assert constants.TOKEN_DEFAULT_ORIGIN == "https://sdk.labellerr.com"


def test_constants_do_not_read_the_environment_at_import(monkeypatch):
    monkeypatch.setenv("LABELLERR_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://mcp.labellerr.com")
    try:
        importlib.reload(constants)
        assert "BASE_URL" not in vars(constants)
        assert "ALLOWED_ORIGINS" not in vars(constants)
        assert constants.DEFAULT_BASE_URL == "https://api.labellerr.com"
        assert constants.DEFAULT_ORIGIN == "https://pro.labellerr.com"
    finally:
        monkeypatch.undo()
        importlib.reload(constants)


def test_legacy_constant_names_follow_the_environment(monkeypatch):
    monkeypatch.setenv("LABELLERR_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://mcp.labellerr.com")
    assert constants.BASE_URL == "https://gateway.example.test"
    assert constants.ALLOWED_ORIGINS == "https://mcp.labellerr.com"
    monkeypatch.delenv("LABELLERR_BASE_URL")
    assert constants.BASE_URL == "https://api.labellerr.com"
    with pytest.raises(AttributeError):
        constants.NOT_A_CONSTANT


# --- Settings --------------------------------------------------------------------


def test_settings_defaults():
    settings = Settings()
    assert settings.base_url == "https://api.labellerr.com"
    assert settings.origin is None and settings.source == "sdk"
    assert settings.user_agent is None
    assert settings.resolve_user_agent() == DEFAULT_USER_AGENT


def test_settings_strips_trailing_slash():
    assert Settings(base_url="https://gw.example.test/").base_url == (
        "https://gw.example.test"
    )


def test_settings_rejects_empty_base_url():
    with pytest.raises(ValueError):
        Settings(base_url="  ")


def test_settings_is_frozen():
    with pytest.raises(Exception):
        Settings().base_url = "x"


def test_from_env_reads_environment_when_called(monkeypatch):
    monkeypatch.setenv("LABELLERR_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://mcp.labellerr.com")
    settings = Settings.from_env()
    assert settings.base_url == "https://gateway.example.test"
    assert settings.origin == "https://mcp.labellerr.com"


def test_from_env_overrides_win(monkeypatch):
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://env.example.test")
    settings = Settings.from_env(origin="https://explicit.example.test", base_url=None)
    assert settings.origin == "https://explicit.example.test"
    assert settings.base_url == "https://api.labellerr.com"


def test_origin_defaults_by_credential_kind():
    assert Settings().resolve_origin("api_key") == "https://pro.labellerr.com"
    assert Settings().resolve_origin("bearer") == "https://sdk.labellerr.com"
    explicit = Settings(origin="https://x.example.test")
    assert explicit.resolve_origin("bearer") == "https://x.example.test"


def test_client_reads_environment_at_construction_not_import(monkeypatch):
    # labellerr is already imported; setting the variables now must still apply.
    monkeypatch.setenv("LABELLERR_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("LABELLERR_ORIGIN", "https://mcp.labellerr.com")
    client = LabellerrClient.from_access_token(
        "tok", "c", enable_connection_pooling=False
    )
    assert client.base_url == "https://gateway.example.test"
    assert client._build_headers()["origin"] == "https://mcp.labellerr.com"
    async_client = AsyncLabellerrClient(access_token="tok")
    assert async_client.base_url == "https://gateway.example.test"


def test_origin_precedence_explicit_then_env_then_kind(monkeypatch):
    token_client = LabellerrClient.from_access_token(
        "tok", "c", enable_connection_pooling=False
    )
    key_client = LabellerrClient("k", "s", "c", enable_connection_pooling=False)
    assert token_client._build_headers()["origin"] == "https://sdk.labellerr.com"
    assert key_client._build_headers()["origin"] == "https://pro.labellerr.com"

    monkeypatch.setenv("LABELLERR_ORIGIN", "https://env.example.test")
    env_client = LabellerrClient.from_access_token(
        "tok", "c", enable_connection_pooling=False
    )
    assert env_client._build_headers()["origin"] == "https://env.example.test"

    explicit = LabellerrClient.from_access_token(
        "tok",
        "c",
        enable_connection_pooling=False,
        settings=Settings.from_env(origin="https://explicit.example.test"),
    )
    assert explicit._build_headers()["origin"] == "https://explicit.example.test"


def test_client_base_url_is_assignable():
    client = LabellerrClient(
        "k",
        "s",
        "c",
        enable_connection_pooling=False,
        settings=Settings(base_url="https://a.example.test"),
    )
    assert client.base_url == "https://a.example.test"
    client.base_url = "https://b.example.test"
    assert client.base_url == "https://b.example.test"
    assert client.settings.base_url == "https://a.example.test"


def test_settings_must_be_a_settings_object():
    with pytest.raises(TypeError):
        LabellerrClient("k", "s", "c", settings={"base_url": "x"})


# --- User-Agent ------------------------------------------------------------------


def test_default_user_agent_names_the_version():
    assert DEFAULT_USER_AGENT == f"labellerr-sdk-python/{labellerr.__version__}"
    assert labellerr.DEFAULT_USER_AGENT == DEFAULT_USER_AGENT


def test_sync_and_async_send_the_same_user_agent():
    sync_headers = LabellerrClient.from_access_token(
        "tok", "c", enable_connection_pooling=False
    )._build_headers()
    client = AsyncLabellerrClient(access_token="tok")
    async_headers = client._build_headers()

    async def session_user_agent():
        await client._ensure_session()
        try:
            return client._session.headers["User-Agent"]
        finally:
            await client.close()

    assert sync_headers["User-Agent"] == DEFAULT_USER_AGENT
    assert async_headers["User-Agent"] == DEFAULT_USER_AGENT
    assert asyncio.run(session_user_agent()) == DEFAULT_USER_AGENT


def test_custom_user_agent():
    settings = Settings(user_agent="my-app/1")
    headers = client_utils.build_headers(KEY, settings)
    assert headers["User-Agent"] == "my-app/1"


def test_settings_module_imports_without_a_cycle():
    code = (
        "import labellerr.core.settings as s, labellerr; "
        "assert s.DEFAULT_USER_AGENT.startswith('labellerr-sdk-python/'); "
        "assert labellerr.__version__ == s.__version__"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)


# --- build_headers ---------------------------------------------------------------


def test_build_headers_api_key():
    assert client_utils.build_headers(KEY, Settings(), client_id=7) == {
        "api_key": "k",
        "api_secret": "s",
        "source": "sdk",
        "origin": "https://pro.labellerr.com",
        "User-Agent": DEFAULT_USER_AGENT,
        "client_id": "7",
    }


def test_build_headers_token():
    assert client_utils.build_headers(TOKEN, Settings(), client_id="7") == {
        "Authorization": "Bearer tok",
        "source": "sdk",
        "origin": "https://sdk.labellerr.com",
        "User-Agent": DEFAULT_USER_AGENT,
        "client_id": "7",
    }


def test_build_headers_without_client_id():
    headers = client_utils.build_headers(TOKEN, Settings())
    assert "client_id" not in headers and "clientid" not in headers


def test_build_headers_source_argument_and_setting():
    assert client_utils.build_headers(KEY, Settings(), source="x")["source"] == "x"
    assert client_utils.build_headers(KEY, Settings(source="y"))["source"] == "y"


def test_build_headers_drops_none_values():
    headers = client_utils.build_headers(
        TOKEN, Settings(), extra_headers={"email_id": None, "x": "1"}
    )
    assert "email_id" not in headers and headers["x"] == "1"


def test_extra_origin_header_does_not_create_a_second_origin():
    headers = client_utils.build_headers(
        KEY, Settings(), extra_headers={"Origin": "https://other.example.test"}
    )
    origins = [k for k in headers if k.lower() == "origin"]
    assert origins == ["Origin"]
    assert headers["Origin"] == "https://other.example.test"


def test_async_source_is_sdk_async_unless_settings_change_it():
    assert AsyncLabellerrClient("k", "s")._build_headers()["source"] == "sdk-async"
    custom = AsyncLabellerrClient("k", "s", settings=Settings(source="my-tool"))
    assert custom._build_headers()["source"] == "my-tool"
