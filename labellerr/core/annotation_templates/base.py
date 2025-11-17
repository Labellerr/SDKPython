from .. import constants
from ..client import LabellerrClient
from ..exceptions import InvalidAnnotationTemplateError
import uuid


class LabellerrAnnotationTemplate:
    @staticmethod
    def get_annotation_template(client: "LabellerrClient", annotation_template_id: str):
        """Get annotation template from Labellerr API"""
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/annotations/get_template?template_id={annotation_template_id}&client_id={client.client_id}"
            f"&uuid={unique_id}"
        )

        response = client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)

    """Base class for all Labellerr projects with factory behavior"""

    def __new__(cls, client: "LabellerrClient", annotation_template_id: str):
        # Validate that the annotation template exists before creating the instance
        annotation_template_data = cls.get_annotation_template(
            client, annotation_template_id
        )

        if not annotation_template_data or (
            isinstance(annotation_template_data, dict) and not annotation_template_data
        ):
            raise InvalidAnnotationTemplateError(
                f"Annotation template with ID '{annotation_template_id}' does not exist or could not be retrieved."
            )

        # Create the instance only if validation passes
        instance = super().__new__(cls)
        # Store the data on the instance to avoid calling API again in __init__
        instance.__annotation_template_data = annotation_template_data
        return instance

    def __init__(self, client: "LabellerrClient", annotation_template_id: str):
        self.client = client
        self.annotation_template_id = annotation_template_id
        # Use the data already fetched in __new__
        self.annotation_template_data = self.__annotation_template_data
