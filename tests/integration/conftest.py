"""
Integration-specific pytest configuration and fixtures.

This module extends the main conftest.py with integration-specific fixtures
for AWS, GCS, and other external service configurations.
"""

import os
import sys

import pytest
from dotenv import load_dotenv

# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

# Load .env file from the root directory
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)


def get_credential(env_var, required=False):
    """
    Get credential from environment variable (loaded from .env file).

    Args:
        env_var: Environment variable name
        required: If True, skip test if credential is not found

    Returns:
        str: The credential value or None
    """
    value = os.environ.get(env_var)

    # Check if required
    if required and not value:
        pytest.skip(f"Missing required credential: {env_var}")

    return value


@pytest.fixture(scope="session")
def api_key():
    """API key for authentication."""
    return get_credential("API_KEY", required=True)


@pytest.fixture(scope="session")
def api_secret():
    """API secret for authentication."""
    return get_credential("API_SECRET", required=True)


@pytest.fixture(scope="session")
def client_id():
    """Client ID."""
    return get_credential("CLIENT_ID", required=True)


@pytest.fixture(scope="session")
def project_id():
    """Project ID."""
    return get_credential("PROJECT_ID", required=False) or ""


@pytest.fixture(scope="session")
def dataset_id():
    """Dataset ID for sync operations."""
    return get_credential("DATASET_ID", required=False) or ""


@pytest.fixture(scope="session")
def path():
    """Path to the data."""
    return get_credential("PATH", required=False) or "/data"


@pytest.fixture(scope="session")
def data_type():
    """Type of data (image, video, audio, document, text)."""
    return get_credential("DATA_TYPE", required=False) or "image"


@pytest.fixture(scope="session")
def email_id():
    """Email ID of the user."""
    return (
        get_credential("EMAIL_ID", required=False)
        or get_credential("CLIENT_EMAIL", required=False)
        or ""
    )


@pytest.fixture(scope="session")
def connection_id():
    """Connection ID."""
    return get_credential("CONNECTION_ID", required=False) or ""


# AWS-specific fixtures
@pytest.fixture(scope="session")
def aws_dataset_id():
    """Dataset ID for AWS sync operations."""
    return get_credential("AWS_DATASET_ID", required=False) or ""


@pytest.fixture(scope="session")
def aws_connection_id():
    """Connection ID for AWS."""
    return get_credential("AWS_CONNECTION_ID", required=False) or ""


@pytest.fixture(scope="session")
def aws_path():
    """Path to the AWS data (e.g., s3://bucket/path)."""
    return get_credential("AWS_PATH", required=False) or ""


# GCS-specific fixtures
@pytest.fixture(scope="session")
def gcs_dataset_id():
    """Dataset ID for GCS sync operations."""
    return get_credential("GCS_DATASET_ID", required=False) or ""


@pytest.fixture(scope="session")
def gcs_connection_id():
    """Connection ID for GCS."""
    return get_credential("GCS_CONNECTION_ID", required=False) or ""


@pytest.fixture(scope="session")
def gcs_path():
    """Path to the GCS data (e.g., gs://bucket/path)."""
    return get_credential("GCS_PATH", required=False) or ""
