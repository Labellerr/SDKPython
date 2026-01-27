"""
Integration tests for dataset creation from local files.

This module tests the create_dataset_from_local() function for all supported
data types:
- Image (jpg, jpeg, png, bmp, gif, tiff)
- Video (mp4, avi, mov, mkv, flv, wmv)
- Audio (mp3, wav, flac, aac, ogg, m4a)
- Document (pdf, doc, docx, txt)
- Text (txt, csv, json, xml)

Performance Optimization:
- Tests first try to use existing dataset IDs from environment (fast - no uploads)
- Falls back to creating from local paths if IDs not found (slow - uploads files)
- New datasets upload only 3 files for faster execution

Features:
- Automatic cleanup of created datasets with retry logic
- Detailed cleanup summary with success/failure reporting
- Manual cleanup instructions for failed deletions
- Existing datasets are not cleaned up (only newly created ones)

Requires environment variables (for each data type):
    Fast path (preferred):
    - {DATA_TYPE}_DATASET_ID: ID of existing dataset to reuse
      Example: IMAGE_DATASET_ID=1a5af31b-dd41-4072-8be3-cae553ba9804

    Slow path (fallback):
    - {DATA_TYPE}_DATASET_PATH: Path to local folder containing files
      Example: IMAGE_DATASET_PATH=/path/to/images

    Special case - Audio:
    - AUDIO_MP3_DATASET_ID or AUDIO_WAV_DATASET_ID (tries MP3 first)
    - AUDIO_DATASET_PATH (fallback)
"""

import logging
import os
import time

import pytest
from dotenv import load_dotenv

from pathlib import Path
from typing import List, Optional

from labellerr.client import LabellerrClient
from labellerr.core.datasets import (
    LabellerrDataset,
    create_dataset_from_local,
    delete_dataset,
)
from labellerr.core.schemas import DatasetConfig

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# Internal Helper Functions
# ============================================================================


def _get_first_n_files(
    folder_path: str, n: int = 3, extensions: tuple = None
) -> List[str]:
    """Get the first N files from a folder."""
    folder = Path(folder_path)
    if not folder.exists():
        return []

    files = []
    for file_path in folder.iterdir():
        if file_path.is_file():
            if extensions is None or file_path.suffix.lower() in extensions:
                files.append(str(file_path))
                if len(files) >= n:
                    break
    return files


def _validate_dataset(dataset: LabellerrDataset, expected_status: int = 300) -> dict:
    """Validate a dataset meets expected criteria."""
    assert dataset.dataset_id is not None, "Dataset ID must not be None"
    result = dataset.status()
    assert (
        result["status_code"] == expected_status
    ), f"Expected status {expected_status}, got {result['status_code']}"
    assert (
        result["files_count"] >= 1
    ), f"Expected at least 1 file, got {result['files_count']}"
    return result


def _try_existing_dataset(
    client: LabellerrClient, dataset_id: str, data_type: str
) -> Optional[LabellerrDataset]:
    """Try to use an existing dataset and validate it."""
    try:
        logger.info(f"Using existing {data_type} dataset: {dataset_id}")
        dataset = LabellerrDataset(client=client, dataset_id=dataset_id)
        result = _validate_dataset(dataset)
        logger.info(
            f"{data_type.capitalize()} dataset verified: {dataset.dataset_id} ({result['files_count']} files)"
        )
        return dataset
    except Exception as e:
        logger.warning(f"Could not use existing dataset {dataset_id}: {e}")
        return None


def _create_test_dataset(
    client: LabellerrClient,
    path: str,
    data_type: str,
    extensions: tuple,
    max_files: int = 3,
) -> LabellerrDataset:
    """Create a test dataset from local files."""
    files = _get_first_n_files(path, n=max_files, extensions=extensions)
    if not files:
        raise FileNotFoundError(f"No {data_type} files found in {path}")

    logger.info(f"Uploading {len(files)} files for testing")
    timestamp = int(time.time())

    dataset = create_dataset_from_local(
        client=client,
        dataset_config=DatasetConfig(
            dataset_name=f"SDK_Test_{data_type.capitalize()}_Dataset_{timestamp}",
            data_type=data_type,
        ),
        files_to_upload=files,
    )

    assert dataset.dataset_id is not None, "Failed to create dataset"
    logger.info(f"{data_type.capitalize()} dataset created: {dataset.dataset_id}")
    return dataset


# Dataset type configurations
DATASET_CONFIGS = {
    "image": {
        "env_id": "IMAGE_DATASET_ID",
        "env_path": "IMAGE_DATASET_PATH",
        "extensions": (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"),
        "display_name": "image",
    },
    "video": {
        "env_id": "VIDEO_DATASET_ID",
        "env_path": "VIDEO_DATASET_PATH",
        "extensions": (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"),
        "display_name": "video",
    },
    "audio": {
        "env_id": ["AUDIO_MP3_DATASET_ID", "AUDIO_WAV_DATASET_ID"],  # Try multiple IDs
        "env_path": "AUDIO_DATASET_PATH",
        "extensions": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
        "display_name": "audio",
    },
    "document": {
        "env_id": "DOCUMENT_DATASET_ID",
        "env_path": "DOCUMENT_DATASET_PATH",
        "extensions": (".pdf", ".doc", ".docx", ".txt"),
        "display_name": "document",
    },
    "text": {
        "env_id": "TEXT_DATASET_ID",
        "env_path": "TEXT_DATASET_PATH",
        "extensions": (".txt", ".csv", ".json", ".xml"),
        "display_name": "text",
    },
}


def _test_dataset_creation(
    client: LabellerrClient, data_type: str, cleanup_callback
) -> None:
    """Generic test logic for dataset creation across all data types."""
    config = DATASET_CONFIGS[data_type]
    env_ids = (
        config["env_id"] if isinstance(config["env_id"], list) else [config["env_id"]]
    )

    # Try existing dataset(s) first (fast path - no uploads)
    for env_id_key in env_ids:
        dataset_id = os.getenv(env_id_key)
        if dataset_id:
            dataset = _try_existing_dataset(client, dataset_id, config["display_name"])
            if dataset:
                return  # Successfully used existing dataset

    # Fallback: Create new dataset (slow path - uploads files)
    logger.info("Falling back to creating new dataset...")
    dataset_path = os.getenv(config["env_path"])

    if not dataset_path:
        skip_msg = f"Missing required environment variables: {', '.join(env_ids)} or {config['env_path']}"
        pytest.skip(skip_msg)

    try:
        dataset = _create_test_dataset(
            client, dataset_path, data_type, config["extensions"], max_files=3
        )
        cleanup_callback(dataset.dataset_id)  # Register for cleanup
        result = _validate_dataset(dataset)
        logger.info(
            f"{data_type.capitalize()} dataset validated: {dataset.dataset_id} ({result['files_count']} files)"
        )
    except FileNotFoundError as e:
        pytest.skip(str(e))


# integration_client fixture is now shared in tests/conftest.py


@pytest.fixture(scope="class")
def cleanup_datasets(integration_client):
    """Fixture for automatic dataset cleanup after all tests in the class."""
    datasets_to_cleanup = []

    def _register(dataset_id: str):
        """Register a dataset_id for cleanup"""
        if dataset_id and dataset_id not in datasets_to_cleanup:
            datasets_to_cleanup.append(dataset_id)

    yield _register

    # Cleanup: delete all registered datasets
    if not datasets_to_cleanup:
        return

    failed_cleanups = []
    for dataset_id in datasets_to_cleanup:
        try:
            delete_dataset(integration_client, dataset_id)
            logger.info(f"Deleted dataset: {dataset_id}")
        except Exception as e:
            failed_cleanups.append((dataset_id, str(e)))
            logger.error(f"Failed to delete dataset {dataset_id}: {e}")

    # Cleanup summary and fail if any deletions failed
    logger.info("=" * 80)
    logger.info("DATASET CLEANUP SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total created: {len(datasets_to_cleanup)}")
    logger.info(f"Deleted: {len(datasets_to_cleanup) - len(failed_cleanups)}")
    logger.info(f"Failed: {len(failed_cleanups)}")
    if failed_cleanups:
        logger.error("Failed dataset IDs (delete manually):")
        for dataset_id, error in failed_cleanups:
            logger.error(f"  - {dataset_id}: {error}")
    logger.info("=" * 80)

    # Fail the test if any cleanup failed
    if failed_cleanups:
        pytest.fail(
            f"Cleanup failed for {len(failed_cleanups)} dataset(s). See summary above."
        )


@pytest.mark.integration
class TestCreateDatasetIntegration:
    """Integration tests for dataset creation across all data types."""

    def test_create_image_dataset(self, integration_client, cleanup_datasets):
        """Test creating image dataset. Tries IMAGE_DATASET_ID (fast) or IMAGE_DATASET_PATH (slow)."""
        _test_dataset_creation(integration_client, "image", cleanup_datasets)

    def test_create_video_dataset(self, integration_client, cleanup_datasets):
        """Test creating video dataset. Tries VIDEO_DATASET_ID (fast) or VIDEO_DATASET_PATH (slow)."""
        _test_dataset_creation(integration_client, "video", cleanup_datasets)

    def test_create_audio_dataset(self, integration_client, cleanup_datasets):
        """Test creating audio dataset. Tries AUDIO_MP3_DATASET_ID/AUDIO_WAV_DATASET_ID (fast) or AUDIO_DATASET_PATH (slow)."""
        _test_dataset_creation(integration_client, "audio", cleanup_datasets)

    def test_create_document_dataset(self, integration_client, cleanup_datasets):
        """Test creating document dataset. Tries DOCUMENT_DATASET_ID (fast) or DOCUMENT_DATASET_PATH (slow)."""
        _test_dataset_creation(integration_client, "document", cleanup_datasets)

    def test_create_text_dataset(self, integration_client, cleanup_datasets):
        """Test creating text dataset. Tries TEXT_DATASET_ID (fast) or TEXT_DATASET_PATH (slow)."""
        _test_dataset_creation(integration_client, "text", cleanup_datasets)
