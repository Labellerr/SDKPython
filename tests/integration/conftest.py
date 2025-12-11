"""
Integration-specific pytest configuration and fixtures for the Labellerr SDK.
"""

import os
import sys
import pytest
from dotenv import load_dotenv
from labellerr.client import LabellerrClient

# Add root directory to PYTHONPATH
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

# Load .env from root
load_dotenv(os.path.join(root_dir, ".env"))


# ------------------------------
# Helper
# ------------------------------
def get_credential(env_var, required=False):
    """Fetch credential or skip test when required."""
    value = os.environ.get(env_var)
    if required and not value:
        pytest.skip(f"Missing required credential: {env_var}")
    return value


# ------------------------------
# SDK import verification
# ------------------------------
@pytest.fixture(scope="session", autouse=True)
def verify_sdk_import():
    """Ensure SDK is installed before running any integration test."""
    try:
        import labellerr  # noqa
    except Exception:
        pytest.exit("Labellerr SDK is not installed or not importable.")
    return True


# ------------------------------
# Base Credentials
# ------------------------------
@pytest.fixture(scope="session")
def api_key():
    return get_credential("API_KEY", required=True)


@pytest.fixture(scope="session")
def api_secret():
    return get_credential("API_SECRET", required=True)


@pytest.fixture(scope="session")
def client_id():
    return get_credential("CLIENT_ID", required=True)


@pytest.fixture(scope="session")
def email_id():
    return get_credential("EMAIL_ID") or get_credential("CLIENT_EMAIL") or ""


# ------------------------------
# Project / Dataset
# ------------------------------
@pytest.fixture(scope="session")
def project_id():
    return get_credential("PROJECT_ID") or None


@pytest.fixture(scope="session")
def dataset_id():
    return get_credential("DATASET_ID") or None


@pytest.fixture(scope="session")
def data_path():
    return get_credential("DATA_PATH") or "/data"


@pytest.fixture(scope="session")
def data_type():
    return get_credential("DATA_TYPE") or "image"


@pytest.fixture(scope="session")
def connection_id():
    return get_credential("CONNECTION_ID") or None


# ------------------------------
# AWS
# ------------------------------
@pytest.fixture(scope="session")
def aws_dataset_id():
    return get_credential("AWS_DATASET_ID") or None


@pytest.fixture(scope="session")
def aws_connection_id():
    return get_credential("AWS_CONNECTION_ID") or None


@pytest.fixture(scope="session")
def aws_path():
    return get_credential("AWS_PATH") or None


# ------------------------------
# GCS
# ------------------------------
@pytest.fixture(scope="session")
def gcs_dataset_id():
    return get_credential("GCS_DATASET_ID") or None


@pytest.fixture(scope="session")
def gcs_connection_id():
    return get_credential("GCS_CONNECTION_ID") or None


@pytest.fixture(scope="session")
def gcs_path():
    return get_credential("GCS_PATH") or None


# ------------------------------
# SDK Authenticated Client
# ------------------------------
@pytest.fixture
def client(api_key, api_secret, client_id):
    return LabellerrClient(
        api_key=api_key,
        api_secret=api_secret,
        client_id=client_id,
    )
