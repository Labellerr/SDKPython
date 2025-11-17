import os

import pytest
from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.datasets import create_dataset_from_local
from labellerr.core.schemas import DatasetConfig

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
IMG_DATASET_PATH = os.getenv("IMG_DATASET_PATH")


@pytest.fixture
def create_dataset_fixture():
    client = LabellerrClient(
        api_key=API_KEY, api_secret=API_SECRET, client_id=CLIENT_ID
    )

    dataset = create_dataset_from_local(
        client=client,
        dataset_config=DatasetConfig(dataset_name="My Dataset", data_type="image"),
        folder_to_upload=IMG_DATASET_PATH,
    )

    return dataset


def test_create_dataset(create_dataset_fixture):
    dataset = create_dataset_fixture

    assert dataset.dataset_id is not None

    result = dataset.status()

    assert result["status_code"] == 300
    assert result["files_count"] > 0
