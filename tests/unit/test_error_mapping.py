"""Unit tests for the typed exceptions and client_utils.error_from_response."""

from email.utils import format_datetime
from datetime import datetime, timedelta, timezone

import pytest

import labellerr
from labellerr.core import client_utils
from labellerr.core.client import LabellerrClient
from labellerr.core.exceptions import (
    AuthenticationError,
    InvalidAnnotationTemplateError,
    InvalidConnectionError,
    InvalidDatasetError,
    InvalidDatasetIDError,
    InvalidProjectError,
    LabellerrError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)

pytestmark = pytest.mark.unit


class _Response:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code, body=None, text=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else ("" if body is None else str(body))
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


# --- Exceptions ------------------------------------------------------------------


def test_labellerr_error_is_constructed_as_before():
    assert LabellerrError("text").args == ("text",)
    assert LabellerrError({"a": 1}).args[0] == {"a": 1}
    assert LabellerrError("a", 2).args == ("a", 2)
    error = LabellerrError("text")
    assert error.status_code is None and error.error_code is None
    assert error.request_id is None and error.response_body is None


def test_new_attributes_are_keyword_only():
    error = LabellerrError(
        "x", status_code=400, error_code="E", request_id="r", response_body={"b": 1}
    )
    assert (error.status_code, error.error_code, error.request_id) == (400, "E", "r")
    assert error.response_body == {"b": 1} and error.args == ("x",)


@pytest.mark.parametrize(
    "cls",
    [
        AuthenticationError,
        PermissionDeniedError,
        NotFoundError,
        RateLimitError,
        ServerError,
        InvalidDatasetError,
        InvalidProjectError,
        InvalidDatasetIDError,
        InvalidConnectionError,
        InvalidAnnotationTemplateError,
    ],
)
def test_every_sdk_error_is_a_labellerr_error(cls):
    assert issubclass(cls, LabellerrError)


def test_rate_limit_error_has_retry_after():
    assert RateLimitError("x").retry_after is None
    assert RateLimitError("x", retry_after=2.5, status_code=429).retry_after == 2.5


def test_new_errors_are_exported_from_the_package():
    for name in (
        "AuthenticationError",
        "PermissionDeniedError",
        "NotFoundError",
        "RateLimitError",
        "ServerError",
    ):
        assert name in labellerr.__all__ and hasattr(labellerr, name)


# --- error_from_response: class --------------------------------------------------


@pytest.mark.parametrize(
    "status, cls",
    [
        (400, LabellerrError),
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, LabellerrError),
        (422, LabellerrError),
        (429, RateLimitError),
        (500, ServerError),
        (502, ServerError),
        (503, ServerError),
        (302, LabellerrError),
    ],
)
def test_class_from_status(status, cls):
    error = client_utils.error_from_response(status, {"message": "m"})
    assert type(error) is cls


@pytest.mark.parametrize(
    "code, cls",
    [
        ("INVALID_API_KEY", AuthenticationError),
        ("TOKEN_INVALID", AuthenticationError),
        ("SESSION_REVOKED", AuthenticationError),
        ("NOT_A_MEMBER", PermissionDeniedError),
        ("RATE_LIMITED", RateLimitError),
    ],
)
def test_error_code_wins_over_status(code, cls):
    # 400/500 on purpose: the class must come from the code, not the status.
    for status in (400, 500):
        error = client_utils.error_from_response(status, {"error_code": code})
        assert type(error) is cls and error.error_code == code


def test_error_code_nested_under_error():
    body = {"error": {"error_code": "TOKEN_INVALID", "message": "expired"}}
    error = client_utils.error_from_response(403, body)
    assert type(error) is AuthenticationError
    assert error.error_code == "TOKEN_INVALID"


def test_unknown_error_code_falls_back_to_status():
    error = client_utils.error_from_response(404, {"error_code": "SOMETHING_NEW"})
    assert type(error) is NotFoundError and error.error_code == "SOMETHING_NEW"


@pytest.mark.parametrize("body", ["plain text", ["a"], None, {"error_code": 7}])
def test_bodies_without_a_usable_code(body):
    error = client_utils.error_from_response(401, body)
    assert type(error) is AuthenticationError and error.error_code is None


# --- error_from_response: args shape and attributes ------------------------------


def test_4xx_args_shape_is_unchanged():
    body = {"message": "bad"}
    error = client_utils.error_from_response(400, body, request_id="rid")
    assert error.args[0] == {"error": body, "code": 400}
    assert error.status_code == 400 and error.request_id == "rid"
    assert error.response_body == body


def test_4xx_text_body_args_shape():
    error = client_utils.error_from_response(404, "Not Found")
    assert error.args[0] == {"error": "Not Found", "code": 404}


def test_5xx_args_shape_with_body():
    error = client_utils.error_from_response(500, {"message": "boom"}, request_id="r1")
    assert error.args[0] == {
        "status": "internal server error",
        "message": "Please contact support with the request tracking id",
        "request_id": "r1",
        "error": {"message": "boom"},
    }
    assert error.request_id == "r1" and error.status_code == 500


@pytest.mark.parametrize("body", [None, ""])
def test_5xx_args_shape_without_body(body):
    error = client_utils.error_from_response(503, body)
    assert set(error.args[0]) == {"status", "message", "request_id"}
    # A request id is generated when none was given.
    assert (
        error.args[0]["request_id"] and error.request_id == error.args[0]["request_id"]
    )


# --- Retry-After -----------------------------------------------------------------


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"Retry-After": "7"}, 7.0),
        ({"retry-after": "1.5"}, 1.5),
        ({"RETRY-AFTER": " 3 "}, 3.0),
        ({"Retry-After": "-4"}, 0.0),
        ({"Retry-After": "soon"}, None),
        ({"Retry-After": ""}, None),
        ({}, None),
        (None, None),
    ],
)
def test_retry_after(headers, expected):
    error = client_utils.error_from_response(429, {"message": "slow down"}, headers)
    assert isinstance(error, RateLimitError)
    assert error.retry_after == expected


def test_retry_after_http_date():
    when = datetime.now(timezone.utc) + timedelta(seconds=120)
    error = client_utils.error_from_response(
        429, None, {"Retry-After": format_datetime(when, usegmt=True)}
    )
    assert 100 <= error.retry_after <= 121


def test_retry_after_http_date_in_the_past():
    assert client_utils.parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


def test_retry_after_from_error_code_on_another_status():
    error = client_utils.error_from_response(
        400, {"error_code": "RATE_LIMITED"}, {"Retry-After": "9"}
    )
    assert isinstance(error, RateLimitError) and error.retry_after == 9.0


def test_retry_after_tolerates_odd_header_objects():
    class Weird:
        def items(self):
            raise RuntimeError("no")

    error = client_utils.error_from_response(429, None, Weird())
    assert error.retry_after is None


# --- Wrappers call the one mapping -----------------------------------------------


def test_handle_response_success_returns_json():
    assert client_utils.handle_response(_Response(200, {"ok": 1})) == {"ok": 1}


def test_handle_response_success_without_json_raises():
    with pytest.raises(LabellerrError, match="Expected JSON"):
        client_utils.handle_response(_Response(200, None, text="<html>"))


def test_handle_response_maps_4xx_json_body():
    with pytest.raises(PermissionDeniedError) as info:
        client_utils.handle_response(
            _Response(403, {"error_code": "NOT_A_MEMBER", "message": "no"})
        )
    assert info.value.args[0] == {
        "error": {"error_code": "NOT_A_MEMBER", "message": "no"},
        "code": 403,
    }


def test_handle_response_maps_4xx_text_body():
    with pytest.raises(NotFoundError) as info:
        client_utils.handle_response(_Response(404, None, text="nope"))
    assert info.value.args[0] == {"error": "nope", "code": 404}


def test_handle_response_maps_5xx_and_keeps_request_id():
    with pytest.raises(ServerError) as info:
        client_utils.handle_response(_Response(502, None, text="bad gw"), "rid-1")
    assert info.value.args[0]["request_id"] == "rid-1"
    assert info.value.args[0]["error"] == "bad gw"


def test_handle_response_maps_429_with_retry_after():
    with pytest.raises(RateLimitError) as info:
        client_utils.handle_response(
            _Response(429, {"message": "m"}, headers={"Retry-After": "5"})
        )
    assert info.value.retry_after == 5.0


def test_handle_response_custom_success_codes():
    assert client_utils.handle_response(_Response(202, {"a": 1}), None, [202]) == {
        "a": 1
    }


@pytest.fixture
def client():
    return LabellerrClient("k", "s", "c", enable_connection_pooling=False)


def test_handle_upload_response_success(client):
    assert client.handle_upload_response(_Response(201, {"ok": True})) == {"ok": True}


def test_handle_upload_response_4xx_shape(client):
    with pytest.raises(LabellerrError) as info:
        client.handle_upload_response(_Response(400, {"message": "bad"}))
    assert info.value.args[0] == {"error": {"message": "bad"}, "code": 400}


def test_handle_upload_response_5xx_shape(client):
    with pytest.raises(ServerError) as info:
        client.handle_upload_response(_Response(500, {"message": "x"}), "rid")
    assert info.value.args[0]["error"] == {"message": "x"}
    assert info.value.args[0]["request_id"] == "rid"


def test_handle_upload_response_success_not_json(client):
    with pytest.raises(LabellerrError, match="Failed to parse response"):
        client.handle_upload_response(_Response(200, None, text="oops"))


def test_handle_gcs_response_is_unchanged(client):
    assert client._handle_gcs_response(_Response(200), "download") is True
    assert client._handle_gcs_response(_Response(201), "upload") is True
    with pytest.raises(LabellerrError, match="download failed: 403"):
        client._handle_gcs_response(_Response(403, text="denied"), "download")
