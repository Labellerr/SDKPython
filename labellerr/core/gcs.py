import os

import requests

from .exceptions import LabellerrError

CONTENT_TYPE = "application/octet-stream"


def _handle_gcs_response(response, operation_name="GCS operation"):
    """
    Standardized error handling for Google Cloud Storage operations.

    :param response: requests.Response object
    :param operation_name: Name of the operation for error messages
    :return: True for successful operations
    :raises LabellerrError: For non-successful responses
    """
    if operation_name == "resumable_start":
        expected_codes = [201]
    elif operation_name == "upload":
        expected_codes = [200, 201]
    else:
        expected_codes = [200]

    if response.status_code in expected_codes:
        return True
    else:
        raise LabellerrError(
            f"{operation_name} failed: {response.status_code} - {response.text}"
        )


def upload_to_gcs_direct(signed_url, file_path, chunk_size=8192):
    """
    Upload file to GCS using streaming to minimize memory usage.

    :param signed_url: GCS signed URL for upload
    :param file_path: Local file path to upload
    :param chunk_size: Size of chunks to read (default 8KB)
    """
    file_size = os.path.getsize(file_path)
    headers = {"Content-Type": CONTENT_TYPE, "Content-Length": str(file_size)}

    # Use streaming upload to minimize memory usage
    with open(file_path, "rb") as f:
        upload_response = requests.put(signed_url, headers=headers, data=f)

    _handle_gcs_response(upload_response, "direct upload")
    return True


def upload_to_gcs_resumable(signed_url, file_path, chunk_size=1024 * 1024):
    """
    Upload file to GCS using resumable upload with streaming for memory efficiency.

    :param signed_url: GCS signed URL for resumable upload
    :param file_path: Local file path to upload
    :param chunk_size: Size of chunks to upload (default 1MB)
    """
    # Step 1: Start a resumable upload session
    file_size = os.path.getsize(file_path)
    headers = {
        "x-goog-resumable": "start",
        "Content-Type": CONTENT_TYPE,
        "Content-Length": "0",
    }
    response = requests.post(signed_url, headers=headers)
    _handle_gcs_response(response, "resumable_start")
    upload_url = response.headers["Location"]

    # Step 2: Upload the file in chunks using streaming
    with open(file_path, "rb") as f:
        if file_size <= chunk_size:
            # Small file - upload in one chunk
            headers = {
                "Content-Type": CONTENT_TYPE,
                "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                "Content-Length": str(file_size),
            }
            upload_response = requests.put(upload_url, headers=headers, data=f)
        else:
            # Large file - upload using streaming
            headers = {
                "Content-Type": CONTENT_TYPE,
                "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                "Content-Length": str(file_size),
            }
            upload_response = requests.put(upload_url, headers=headers, data=f)

    _handle_gcs_response(upload_response, "resumable upload")
    return True
