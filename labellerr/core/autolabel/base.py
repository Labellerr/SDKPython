import uuid
from abc import ABCMeta
from typing import TYPE_CHECKING

from .. import constants
from .typings import TrainingRequest

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrAutoLabelMeta(ABCMeta):
    pass


class LabellerrAutoLabel(metaclass=LabellerrAutoLabelMeta):
    def __init__(self, client: "LabellerrClient"):
        self.client = client

    def train(self, training_request: TrainingRequest):
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/ml_training/training/start?client_id={self.client.client_id}"
            f"&uuid={unique_id}"
        )

        response = self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            json=training_request.model_dump(),
        )
        return response.get("response", None)

    def list_training_jobs(self):
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/ml_training/training/list?client_id={self.client.client_id}"
            f"&uuid={unique_id}"
        )

        response = self.client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)
