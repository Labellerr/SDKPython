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

    def __new__(cls, client: "LabellerrClient", annotation_template_id: str, **kwargs):
        # If annotation_template_data is provided in kwargs, use it directly
        if "annotation_template_data" in kwargs:
            instance = super().__new__(cls)
            instance.__annotation_template_data = kwargs["annotation_template_data"]
            return instance

        # Otherwise, fetch from API
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

    def __init__(
        self, client: "LabellerrClient", annotation_template_id: str, **kwargs
    ):
        self.client = client
        if "annotation_template_data" in kwargs:
            self.__annotation_template_id = kwargs["annotation_template_data"].get(
                "template_id"
            )
        else:
            self.__annotation_template_id = annotation_template_id

    @classmethod
    def from_annotation_template_data(cls, client: "LabellerrClient", **kwargs):
        """
        Create a LabellerrAnnotationTemplate instance from annotation template data.

        :param client: LabellerrClient instance
        :param kwargs: Annotation template fields (template_id, template_name, questions, etc.)
        :return: Instance of LabellerrAnnotationTemplate
        """
        # Validate required fields
        required_fields = {
            "template_id",
            "template_name",
            "questions",
            "created_at",
            "created_by",
        }
        missing_fields = required_fields - set(kwargs.keys())
        if missing_fields:
            raise ValueError(
                f"Missing required fields in annotation_template_data: {missing_fields}"
            )

        # Create instance without calling API - pass annotation_template_data to skip API call
        return cls(
            client,
            annotation_template_id=kwargs.get("template_id"),
            annotation_template_data=kwargs,
        )

    @property
    def template_name(self):
        return self.__annotation_template_data.get("template_name")

    @property
    def data_type(self):
        return self.__annotation_template_data.get("data_type")

    @property
    def template_id(self):
        return self.__annotation_template_id

    @property
    def created_at(self):
        return self.__annotation_template_data.get("created_at")

    @property
    def created_by(self):
        return self.__annotation_template_data.get("created_by")

    @property
    def questions(self):
        return self.__annotation_template_data.get("questions")
