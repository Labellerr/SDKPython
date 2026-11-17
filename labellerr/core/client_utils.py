"""
Shared utilities for both sync and async Labellerr clients.
"""

import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Mapping, Optional, Type

from . import constants
from .credentials import Credentials
from .exceptions import (
    AuthenticationError,
    LabellerrError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from .settings import Settings

# Sent with every API request; the gateway's trace middleware reads it, so the
# request ID in an error matches the server's logs.
CORRELATION_ID_HEADER = "x-correlation-id"


def _set_header(headers: Dict[str, Any], name: str, value: Any) -> None:
    """Set a header, replacing any existing header of the same name in another case."""
    for existing in [key for key in headers if key.lower() == name.lower()]:
        del headers[existing]
    headers[name] = value


def _header_text(name: str, value: Any) -> Any:
    """
    A header value ``requests`` can send: strings and bytes as they are; numbers
    and UUIDs as strings.

    :raises TypeError: For any other type (``requests`` would only fail, with
        ``InvalidHeader``, when the request is sent)
    """
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, (int, float, uuid.UUID)):
        return str(value)
    raise TypeError(f"Header {name!r} must be a string, got {type(value).__name__}")


def merge_headers(
    headers: Dict[str, Any], extra_headers: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    """
    Merge ``extra_headers`` over ``headers``, matching names case-insensitively so
    that, e.g., ``Origin`` replaces ``origin`` instead of sending both. Headers whose
    value is None are dropped (so a None in ``extra_headers`` removes a header).
    Numbers and UUIDs are sent as strings.

    :param headers: Base headers (not modified)
    :param extra_headers: Headers to add or replace
    :return: A new dictionary of headers
    :raises TypeError: If a header value is not a string, bytes, number or UUID
    """
    merged = dict(headers)
    if extra_headers:
        for name, value in extra_headers.items():
            _set_header(merged, name, value)
    return {
        name: _header_text(name, value)
        for name, value in merged.items()
        if value is not None
    }


def build_headers(
    credentials: Credentials,
    settings: Settings,
    client_id: Optional[Any] = None,
    extra_headers: Optional[Mapping[str, Any]] = None,
    source: Optional[str] = None,
) -> Dict[str, str]:
    """
    Builds the headers of an API request, for the sync and the async client.

    :param credentials: The client's credentials (produce the authentication headers)
    :param settings: The client's settings (origin, source and User-Agent)
    :param client_id: Optional client ID, sent as the ``client_id`` header
    :param extra_headers: Optional additional headers; names are matched
        case-insensitively and a None value removes a header
    :param source: ``source`` header; defaults to ``settings.source``
    :return: Dictionary of headers
    :raises AuthenticationError: If the credentials cannot produce a token
    """
    headers: Dict[str, Any] = dict(credentials.auth_headers())
    headers["source"] = source or settings.source
    headers["origin"] = settings.resolve_origin(credentials.kind)
    headers["User-Agent"] = settings.resolve_user_agent()
    if client_id is not None and client_id != "":
        headers["client_id"] = str(client_id)
    return merge_headers(headers, extra_headers)


def validate_required_params(params: Dict[str, Any], required_list: list) -> None:
    """
    Validates that all required parameters are present.

    :param params: Dictionary of parameters to validate
    :param required_list: List of required parameter names
    :raises LabellerrError: If any required parameter is missing
    """
    from .exceptions import LabellerrError

    for param in required_list:
        if param not in params:
            raise LabellerrError(f"Required parameter {param} is missing")


def validate_file_exists(file_path: str) -> str:
    """
    Validates that a file exists and returns the basename.

    :param file_path: Path to the file
    :return: basename of the file
    :raises LabellerrError: If file doesn't exist
    """
    import os

    from .exceptions import LabellerrError

    if os.path.exists(file_path):
        return os.path.basename(file_path)
    else:
        raise LabellerrError(f"File not found: {file_path}")


def validate_annotation_format(annotation_format: str, annotation_file: str) -> None:
    """
    Validates annotation format and file extension compatibility.

    :param annotation_format: Format of the annotation
    :param annotation_file: Path to the annotation file
    :raises LabellerrError: If format/extension mismatch
    """
    import os

    from .exceptions import LabellerrError

    if annotation_format not in constants.ANNOTATION_FORMAT:
        raise LabellerrError(
            f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
        )

    # Check if the file extension is .json when annotation_format is coco_json
    if annotation_format == "coco_json":
        file_extension = os.path.splitext(annotation_file)[1].lower()
        if file_extension != ".json":
            raise LabellerrError(
                "For coco_json annotation format, the file must have a .json extension"
            )


def validate_export_config(export_config: Dict[str, Any]) -> None:
    """
    Validates export configuration parameters.

    :param export_config: Export configuration dictionary
    :raises LabellerrError: If configuration is invalid
    """
    from .exceptions import LabellerrError

    required_params = [
        "export_name",
        "export_description",
        "export_format",
        "statuses",
    ]

    for param in required_params:
        if param not in export_config:
            raise LabellerrError(f"Required parameter {param} is missing")

        if param == "export_format":
            if export_config[param] not in constants.LOCAL_EXPORT_FORMAT:
                raise LabellerrError(
                    f"Invalid export_format. Must be one of {constants.LOCAL_EXPORT_FORMAT}"
                )

        if param == "statuses":
            if not isinstance(export_config[param], list):
                raise LabellerrError(f"Invalid statuses. Must be an array {param}")
            for status in export_config[param]:
                if status not in constants.LOCAL_EXPORT_STATUS:
                    raise LabellerrError(
                        f"Invalid status. Must be one of {constants.LOCAL_EXPORT_STATUS}"
                    )


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


# Gateway error codes that decide the error class regardless of the HTTP status.
_ERROR_CODE_CLASSES: Dict[str, Type[LabellerrError]] = {
    "INVALID_API_KEY": AuthenticationError,
    "TOKEN_INVALID": AuthenticationError,
    "SESSION_REVOKED": AuthenticationError,
    "NOT_A_MEMBER": PermissionDeniedError,
    "RATE_LIMITED": RateLimitError,
}

_STATUS_CLASSES: Dict[int, Type[LabellerrError]] = {
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitError,
}


def _gateway_error_code(body: Any) -> Optional[str]:
    """The gateway's ``error_code``, at the top level of the body or under ``error``."""
    if not isinstance(body, dict):
        return None
    code = body.get("error_code")
    if not isinstance(code, str) and isinstance(body.get("error"), dict):
        code = body["error"].get("error_code")
    return code if isinstance(code, str) and code else None


def _header_value(headers: Any, name: str) -> Optional[str]:
    """Case-insensitive header lookup that tolerates any mapping (or None)."""
    if not headers:
        return None
    try:
        items = list(headers.items())
    except Exception:
        return None
    for key, value in items:
        if isinstance(key, str) and key.lower() == name.lower():
            return value if isinstance(value, str) else str(value)
    return None


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """
    Parse a ``Retry-After`` header value into seconds.

    :param value: Delay in seconds (integer or decimal), or an HTTP date
    :return: Seconds to wait (never negative), or None if it cannot be parsed
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if seconds != seconds or seconds in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return max(0.0, seconds)


def error_from_response(
    status_code: int,
    body: Any,
    headers: Optional[Mapping[str, Any]] = None,
    request_id: Optional[str] = None,
) -> LabellerrError:
    """
    Map a failed API response to a ``LabellerrError`` (or subclass). The one place
    the SDK does this; the sync and async clients both call it. It does no I/O.

    The class comes from the gateway's ``error_code`` when it is a known one, else
    from the status: 401 ``AuthenticationError``, 403 ``PermissionDeniedError``,
    404 ``NotFoundError``, 429 ``RateLimitError``, 5xx ``ServerError``, anything else
    ``LabellerrError``.

    ``args[0]`` keeps the shape the SDK has always raised: for a 4xx
    ``{"error": body, "code": status}``; for a 5xx ``{"status": "internal server
    error", "message": ..., "request_id": ..., "error": body}`` (``error`` only when
    there is a body). Any other status (e.g. a 202 or 204 the caller did not expect)
    gets ``{"status": "unexpected response", "message": ..., "code": status,
    "request_id": ..., "error": body}``.

    :param status_code: HTTP status
    :param body: Parsed JSON body (dict/list), or the response text when not JSON
    :param headers: Response headers (for ``Retry-After``)
    :param request_id: Request tracking ID (the ``x-correlation-id`` sent; one is
        generated only when it is unknown)
    :return: The error, to be raised by the caller
    """
    error_code = _gateway_error_code(body)
    error_class = _ERROR_CODE_CLASSES.get(error_code or "")
    if error_class is None:
        if status_code in _STATUS_CLASSES:
            error_class = _STATUS_CLASSES[status_code]
        elif isinstance(status_code, int) and status_code >= 500:
            error_class = ServerError
        else:
            error_class = LabellerrError

    is_int = isinstance(status_code, int)
    if is_int and 400 <= status_code < 500:
        payload: Dict[str, Any] = {"error": body, "code": status_code}
    else:
        request_id = request_id or generate_request_id()
        if is_int and status_code >= 500:
            payload = {
                "status": "internal server error",
                "message": "Please contact support with the request tracking id",
                "request_id": request_id,
            }
        else:
            payload = {
                "status": "unexpected response",
                "message": f"The API answered with unexpected status {status_code}",
                "code": status_code,
                "request_id": request_id,
            }
        if body is not None and body != "":
            payload["error"] = body

    details: Dict[str, Any] = {
        "status_code": status_code,
        "error_code": error_code,
        "request_id": request_id,
        "response_body": body,
    }
    if issubclass(error_class, RateLimitError):
        details["retry_after"] = parse_retry_after(
            _header_value(headers, "Retry-After")
        )
    return error_class(payload, **details)


def sent_request_id(response: Any) -> Optional[str]:
    """
    The ``x-correlation-id`` a ``requests`` response's request was sent with.

    :param response: requests.Response object
    :return: The ID, or None when the request carried none
    """
    request = getattr(response, "request", None)
    return _header_value(getattr(request, "headers", None), CORRELATION_ID_HEADER)


def response_body(response: Any) -> Any:
    """
    The body of a ``requests`` response: parsed JSON, or the text when not JSON.

    :param response: requests.Response object
    :return: Parsed JSON, or text
    """
    try:
        return response.json()
    except ValueError:
        return response.text


def handle_response(response, request_id=None, success_codes=None):
    """
    Return the JSON body of a successful ``requests`` response, or raise the error
    ``error_from_response`` maps it to.

    :param response: requests.Response object
    :param request_id: Optional request tracking ID; defaults to the
        ``x-correlation-id`` the request was sent with
    :param success_codes: Optional list of success status codes (default: [200, 201])
    :return: JSON response data for successful requests
    :raises LabellerrError: For non-successful responses
    """
    if success_codes is None:
        success_codes = [200, 201]
    if request_id is None:
        request_id = sent_request_id(response)

    if response.status_code in success_codes:
        try:
            return response.json()
        except ValueError:
            # Handle cases where response is successful but not JSON
            raise LabellerrError(
                f"Expected JSON response but got: {response.text}",
                status_code=response.status_code,
                request_id=request_id,
                response_body=response.text,
            )
    raise error_from_response(
        response.status_code,
        response_body(response),
        getattr(response, "headers", None),
        request_id,
    )
