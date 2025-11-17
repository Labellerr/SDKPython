"""
Shared utilities for both sync and async Labellerr clients.
"""

import uuid
from typing import Any, Dict, Optional

import requests

from . import constants
from .exceptions import LabellerrError


def build_headers(
    api_key: str,
    api_secret: str,
    source: str = "sdk",
    client_id: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Builds standard headers for API requests.

    :param api_key: API key for authentication
    :param api_secret: API secret for authentication
    :param source: Source identifier (e.g., "sdk", "sdk-async")
    :param client_id: Optional client ID to include in headers
    :param extra_headers: Optional dictionary of additional headers
    :return: Dictionary of headers
    """
    headers = {
        "api_key": api_key,
        "api_secret": api_secret,
        "source": source,
        "origin": constants.ALLOWED_ORIGINS,
    }

    if client_id:
        headers["client_id"] = str(client_id)

    if extra_headers:
        headers.update(extra_headers)

    return headers


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


def handle_response(response, request_id=None, success_codes=None):
    """
    Legacy method for handling response objects directly.
    Kept for backward compatibility with special response handlers.

    :param response: requests.Response object
    :param request_id: Optional request tracking ID
    :param success_codes: Optional list of success status codes (default: [200, 201])
    :return: JSON response data for successful requests
    :raises LabellerrError: For non-successful responses
    """
    if success_codes is None:
        success_codes = [200, 201]

    if response.status_code in success_codes:
        try:
            return response.json()
        except ValueError:
            # Handle cases where response is successful but not JSON
            raise LabellerrError(f"Expected JSON response but got: {response.text}")
    elif 400 <= response.status_code < 500:
        try:
            error_data = response.json()
            raise LabellerrError({"error": error_data, "code": response.status_code})
        except ValueError:
            raise LabellerrError({"error": response.text, "code": response.status_code})
    else:
        raise LabellerrError(
            {
                "status": "internal server error",
                "message": "Please contact support with the request tracking id",
                "request_id": request_id or str(uuid.uuid4()),
            }
        )


def request(method, url, request_id=None, success_codes=None, **kwargs):
    """
    Make HTTP request and handle response in a single method.

    :param method: HTTP method (GET, POST, etc.)
    :param url: Request URL
    :param request_id: Optional request tracking ID (auto-generated if not provided)
    :param success_codes: Optional list of success status codes (default: [200, 201])
    :param kwargs: Additional arguments to pass to requests
    :return: JSON response data for successful requests
    :raises LabellerrError: For non-successful responses
    """
    # Generate request_id if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    # Set default timeout if not provided
    kwargs.setdefault("timeout", (30, 300))  # connect, read

    # Make the request[
    response = requests.request(method, url, **kwargs)

    # Handle the response
    if success_codes is None:
        success_codes = [200, 201]

    if response.status_code in success_codes:
        try:
            return response.json()
        except ValueError:
            # Handle cases where response is successful but not JSON
            raise LabellerrError(f"Expected JSON response but got: {response.text}")
    elif 400 <= response.status_code < 500:
        try:
            error_data = response.json()
            raise LabellerrError({"error": error_data, "code": response.status_code})
        except ValueError:
            raise LabellerrError({"error": response.text, "code": response.status_code})
    else:
        raise LabellerrError(
            {
                "status": "internal server error",
                "message": "Please contact support with the request tracking id",
                "request_id": request_id,
            }
        )
