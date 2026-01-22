import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.datasets import create_dataset_from_local, LabellerrDataset, delete_dataset
from labellerr.core.schemas import DatasetConfig

load_dotenv()


def get_first_n_files(folder_path: str, n: int = 3, extensions: tuple = None):
    """
    Get the first N files from a folder.

    :param folder_path: Path to the folder
    :param n: Number of files to get (default: 3)
    :param extensions: Tuple of file extensions to filter (e.g., ('.jpg', '.png'))
    :return: List of file paths
    """
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


@pytest.fixture(scope="session")
def integration_client():
    """Create a client instance for integration tests."""
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    CLIENT_ID = os.getenv("CLIENT_ID")

    if not all([API_KEY, API_SECRET, CLIENT_ID]):
        pytest.skip("Missing required environment variables: API_KEY, API_SECRET, CLIENT_ID")

    return LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )


@pytest.fixture(scope="class")
def cleanup_datasets(integration_client):
    """
    Fixture for automatic dataset cleanup after all tests in the class.
    """
    datasets_to_cleanup = []

    def _register(dataset_id: str):
        """Register a dataset_id for cleanup"""
        if dataset_id and dataset_id not in datasets_to_cleanup:
            datasets_to_cleanup.append(dataset_id)

    yield _register

    # Cleanup: delete all registered datasets with retry logic
    if not datasets_to_cleanup:
        return  # No datasets to cleanup

    failed_cleanups = []
    for dataset_id in datasets_to_cleanup:
        max_retries = 5
        retry_delay = 3

        for attempt in range(max_retries):
            try:
                # Wait for dataset upload to complete before deletion
                try:
                    dataset = LabellerrDataset(integration_client, dataset_id=dataset_id)
                    status_data = dataset.status()
                    status_code = status_data.get("status_code", 500)

                    # Status code 200 means still uploading, wait and retry
                    if status_code == 200:
                        print(f"\n⏳ Waiting for dataset {dataset_id} to finish uploading (status: {status_code})...")
                        time.sleep(5)
                        continue

                    # Status code 300 means upload complete, ready to delete
                    # Other status codes: proceed with deletion attempt anyway
                    print(f"\n🗑️  Deleting dataset {dataset_id} (status: {status_code})...")

                except Exception as status_error:
                    print(f"\n⚠️  Could not check dataset status for {dataset_id}: {status_error}")
                    print(f"   Attempting deletion anyway...")

                # Delete dataset
                try:
                    delete_dataset(integration_client, dataset_id)
                    print(f"✅ Successfully deleted dataset: {dataset_id}")
                    break  # Success - exit retry loop
                except Exception as delete_error:
                    # If deletion fails, raise to trigger retry logic
                    raise delete_error

            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    print(f"\n⚠️  Deletion attempt {attempt + 1}/{max_retries} failed for {dataset_id}: {error_msg}")
                    print(f"   Retrying in {retry_delay:.1f}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    failed_cleanups.append(dataset_id)
                    print(f"\n❌ Failed to delete dataset {dataset_id} after {max_retries} attempts: {error_msg}")

    # Report detailed cleanup summary
    print("\n" + "=" * 80)
    print("🧹 DATASET CLEANUP SUMMARY")
    print("=" * 80)
    print(f"  Total datasets created:       {len(datasets_to_cleanup)}")
    print(f"  ✅ Successfully deleted:       {len(datasets_to_cleanup) - len(failed_cleanups)}")
    print(f"  ❌ Failed to delete:           {len(failed_cleanups)}")
    if failed_cleanups:
        print(f"\n  ⚠️  Failed dataset IDs (PLEASE DELETE MANUALLY):")
        for dataset_id in failed_cleanups:
            print(f"    - {dataset_id}")
    else:
        print(f"\n  🎉 All datasets cleaned up successfully!")
    print("=" * 80)


@pytest.mark.integration
class TestCreateDatasetIntegration:
    """Integration tests for dataset creation across all data types."""

    def test_create_image_dataset(self, integration_client, cleanup_datasets):
        """Test creating an image dataset from local folder (limited to 3 files for speed)."""
        IMAGE_DATASET_PATH = os.getenv("IMAGE_DATASET_PATH")

        if not IMAGE_DATASET_PATH:
            pytest.skip("Missing required environment variable: IMAGE_DATASET_PATH")

        # Get only first 3 image files for faster testing
        image_files = get_first_n_files(
            IMAGE_DATASET_PATH,
            n=3,
            extensions=('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
        )

        if not image_files:
            pytest.skip(f"No image files found in {IMAGE_DATASET_PATH}")

        print(f"\n📁 Uploading {len(image_files)} files for testing")

        timestamp = int(time.time())
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Image_Dataset_{timestamp}",
                data_type="image"
            ),
            files_to_upload=image_files,
        )

        assert dataset.dataset_id is not None

        # Register for cleanup
        cleanup_datasets(dataset.dataset_id)

        result = dataset.status()

        assert result["status_code"] == 300
        assert result["files_count"] > 0

        print(f"\n✓ Image dataset created: {dataset.dataset_id} ({len(image_files)} files)")

    def test_create_video_dataset(self, integration_client, cleanup_datasets):
        """Test creating a video dataset from local folder (limited to 3 files for speed)."""
        VIDEO_DATASET_PATH = os.getenv("VIDEO_DATASET_PATH")

        if not VIDEO_DATASET_PATH:
            pytest.skip("Missing required environment variable: VIDEO_DATASET_PATH")

        # Get only first 3 video files for faster testing
        video_files = get_first_n_files(
            VIDEO_DATASET_PATH,
            n=3,
            extensions=('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        )

        if not video_files:
            pytest.skip(f"No video files found in {VIDEO_DATASET_PATH}")

        print(f"\n📁 Uploading {len(video_files)} files for testing")

        timestamp = int(time.time())
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Video_Dataset_{timestamp}",
                data_type="video"
            ),
            files_to_upload=video_files,
        )

        assert dataset.dataset_id is not None

        # Register for cleanup
        cleanup_datasets(dataset.dataset_id)

        result = dataset.status()

        assert result["status_code"] == 300
        assert result["files_count"] > 0

        print(f"\n✓ Video dataset created: {dataset.dataset_id} ({len(video_files)} files)")

    def test_create_audio_dataset(self, integration_client, cleanup_datasets):
        """Test creating an audio dataset from local folder (limited to 3 files for speed)."""
        AUDIO_DATASET_PATH = os.getenv("AUDIO_DATASET_PATH")

        if not AUDIO_DATASET_PATH:
            pytest.skip("Missing required environment variable: AUDIO_DATASET_PATH")

        # Get only first 3 audio files for faster testing
        audio_files = get_first_n_files(
            AUDIO_DATASET_PATH,
            n=3,
            extensions=('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a')
        )

        if not audio_files:
            pytest.skip(f"No audio files found in {AUDIO_DATASET_PATH}")

        print(f"\n📁 Uploading {len(audio_files)} files for testing")

        timestamp = int(time.time())
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Audio_Dataset_{timestamp}",
                data_type="audio"
            ),
            files_to_upload=audio_files,
        )

        assert dataset.dataset_id is not None

        # Register for cleanup
        cleanup_datasets(dataset.dataset_id)

        result = dataset.status()

        assert result["status_code"] == 300
        assert result["files_count"] > 0

        print(f"\n✓ Audio dataset created: {dataset.dataset_id} ({len(audio_files)} files)")

    def test_create_document_dataset(self, integration_client, cleanup_datasets):
        """Test creating a document (PDF) dataset from local folder (limited to 3 files for speed)."""
        DOCUMENT_DATASET_PATH = os.getenv("DOCUMENT_DATASET_PATH")

        if not DOCUMENT_DATASET_PATH:
            pytest.skip("Missing required environment variable: DOCUMENT_DATASET_PATH")

        # Get only first 3 document files for faster testing
        document_files = get_first_n_files(
            DOCUMENT_DATASET_PATH,
            n=3,
            extensions=('.pdf', '.doc', '.docx', '.txt')
        )

        if not document_files:
            pytest.skip(f"No document files found in {DOCUMENT_DATASET_PATH}")

        print(f"\n📁 Uploading {len(document_files)} files for testing")

        timestamp = int(time.time())
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Document_Dataset_{timestamp}",
                data_type="document"
            ),
            files_to_upload=document_files,
        )

        assert dataset.dataset_id is not None

        # Register for cleanup
        cleanup_datasets(dataset.dataset_id)

        result = dataset.status()

        assert result["status_code"] == 300
        assert result["files_count"] > 0

        print(f"\n✓ Document dataset created: {dataset.dataset_id} ({len(document_files)} files)")

    def test_create_text_dataset(self, integration_client, cleanup_datasets):
        """Test creating a text dataset from local folder (limited to 3 files for speed)."""
        TEXT_DATASET_PATH = os.getenv("TEXT_DATASET_PATH")

        if not TEXT_DATASET_PATH:
            pytest.skip("Missing required environment variable: TEXT_DATASET_PATH")

        # Get only first 3 text files for faster testing
        text_files = get_first_n_files(
            TEXT_DATASET_PATH,
            n=3,
            extensions=('.txt', '.csv', '.json', '.xml')
        )

        if not text_files:
            pytest.skip(f"No text files found in {TEXT_DATASET_PATH}")

        print(f"\n📁 Uploading {len(text_files)} files for testing")

        timestamp = int(time.time())
        dataset = create_dataset_from_local(
            client=integration_client,
            dataset_config=DatasetConfig(
                dataset_name=f"SDK_Test_Text_Dataset_{timestamp}",
                data_type="text"
            ),
            files_to_upload=text_files,
        )

        assert dataset.dataset_id is not None

        # Register for cleanup
        cleanup_datasets(dataset.dataset_id)

        result = dataset.status()

        assert result["status_code"] == 300
        assert result["files_count"] > 0

        print(f"\n✓ Text dataset created: {dataset.dataset_id} ({len(text_files)} files)")
