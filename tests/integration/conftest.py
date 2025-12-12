"""
Shared test configuration and fixtures for the Labellerr SDK test suite.

This module provides common fixtures, test data, and configuration
that can be used across both unit and integration tests.
"""

import os
import tempfile
import time
from typing import List, Optional

import pytest

from labellerr.client import LabellerrClient


class TestConfig:
    """Centralized test configuration"""

    # Default test values
    DEFAULT_PAGE_SIZE = 10
    DEFAULT_TIMEOUT = 60

    # Test data types
    VALID_DATA_TYPES = ["image", "video", "audio", "document", "text"]

    # Test file extensions
    FILE_EXTENSIONS = {
        "image": [".jpg", ".png", ".jpeg", ".gif"],
        "video": [".mp4", ".avi", ".mov"],
        "audio": [".mp3", ".wav", ".flac"],
        "document": [".pdf", ".doc", ".docx", ".txt"],
    }

    # Sample annotation guides
    SAMPLE_ANNOTATION_GUIDES = {
        "image_classification": [
            {
                "question": "What objects do you see?",
                "option_type": "select",
                "options": ["cat", "dog", "car", "person", "other"],
            },
            {
                "question": "Image quality rating",
                "option_type": "radio",
                "options": ["excellent", "good", "fair", "poor"],
            },
        ],
        "document_processing": [
            {
                "question": "Document type",
                "option_type": "select",
                "options": ["invoice", "receipt", "contract", "other"],
            },
            {
                "question": "Is document complete?",
                "option_type": "boolean",
                "options": ["Yes", "No"],
            },
        ],
    }

    # Default rotation config
    DEFAULT_ROTATION_CONFIG = {
        "annotation_rotation_count": 1,
        "review_rotation_count": 1,
        "client_review_rotation_count": 1,
    }


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    return TestConfig()


@pytest.fixture(scope="session")
def test_credentials():
    """Load test credentials from environment variables"""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    client_id = os.getenv("CLIENT_ID")
    test_email = os.getenv("TEST_EMAIL", "test@example.com")

    if not all([api_key, api_secret, client_id]):
        pytest.skip(
            "Integration tests require credentials. Set environment variables: "
            "API_KEY, API_SECRET, CLIENT_ID"
        )

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "client_id": client_id,
        "test_email": test_email,
    }


@pytest.fixture
def mock_client():
    """Create a mock client for unit testing"""
    return LabellerrClient("test_api_key", "test_api_secret", "test_client_id")


@pytest.fixture
def client():
    """Create a test client with mock credentials - alias for mock_client"""
    return LabellerrClient("test_api_key", "test_api_secret", "test_client_id")


@pytest.fixture
def integration_client(test_credentials):
    """Create a real client for integration testing"""
    return LabellerrClient(
        test_credentials["api_key"],
        test_credentials["api_secret"],
        test_credentials["client_id"],
    )


@pytest.fixture
def temp_files():
    """Create temporary test files and clean them up after test"""
    created_files = []

    def _create_temp_file(suffix=".jpg", content=b"fake_test_data"):
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.write(content)
        temp_file.close()
        created_files.append(temp_file.name)
        return temp_file.name

    yield _create_temp_file

    # Cleanup
    for file_path in created_files:
        try:
            os.unlink(file_path)
        except OSError:
            pass


@pytest.fixture
def temp_json_file():
    """Create temporary JSON file for testing"""

    def _create_json_file(data: dict):
        import json

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, temp_file)
        temp_file.close()
        return temp_file.name

    return _create_json_file


@pytest.fixture
def sample_project_payload(test_credentials, temp_files, test_config):
    """Create a sample project payload for testing"""

    def _create_payload(data_type="image", num_files=3):
        files = []
        for i in range(num_files):
            ext = test_config.FILE_EXTENSIONS[data_type][0]
            file_path = temp_files(
                suffix=ext, content=f"fake_{data_type}_data_{i}".encode()
            )
            files.append(file_path)

        return {
            "client_id": test_credentials["client_id"],
            "dataset_name": f"SDK_Test_Dataset_{int(time.time())}",
            "dataset_description": f"Test dataset for {data_type} SDK integration testing",
            "data_type": data_type,
            "created_by": test_credentials["test_email"],
            "project_name": f"SDK_Test_Project_{int(time.time())}",
            "autolabel": False,
            "files_to_upload": files,
            "annotation_guide": test_config.SAMPLE_ANNOTATION_GUIDES.get(
                f"{data_type}_classification",
                test_config.SAMPLE_ANNOTATION_GUIDES["image_classification"],
            ),
            "rotation_config": test_config.DEFAULT_ROTATION_CONFIG,
        }

    return _create_payload


@pytest.fixture
def sample_annotation_data():
    """Sample annotation data for pre-annotation tests"""
    return {
        "coco_json": {
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [100, 100, 200, 200],
                    "area": 40000,
                    "iscrowd": 0,
                }
            ],
            "images": [
                {"id": 1, "width": 640, "height": 480, "file_name": "test_image.jpg"}
            ],
            "categories": [{"id": 1, "name": "person", "supercategory": "human"}],
        },
        "json": {
            "labels": [
                {
                    "image": "test.jpg",
                    "annotations": [{"label": "cat", "confidence": 0.95}],
                }
            ]
        },
    }


@pytest.fixture
def test_project_ids():
    """Test project and dataset IDs from environment or defaults"""
    return {
        "project_id": os.getenv("TEST_PROJECT_ID", "sisely_serious_tarantula_26824"),
        "dataset_id": os.getenv(
            "TEST_DATASET_ID", "bfd09b6a-a593-4246-82f7-505a497a887c"
        ),
    }


def validate_api_response(response: dict, expected_keys: Optional[List[str]] = None):
    """Helper function to validate API response structure"""
    assert isinstance(response, dict), "Response should be a dictionary"

    if expected_keys:
        for key in expected_keys:
            assert key in response, f"Response should contain '{key}' key"

    # Common validations
    if "status" in response:
        assert response["status"] in ["success", "completed", "pending", "failed"]

    if "response" in response:
        assert response["response"] is not None


def skip_if_no_credentials():
    """Skip test if credentials are not available"""
    required_vars = ["API_KEY", "API_SECRET", "CLIENT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        pytest.skip(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )


# Pytest markers for test categorization
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "aws: Tests requiring AWS credentials")
    config.addinivalue_line("markers", "gcs: Tests requiring GCS credentials")
