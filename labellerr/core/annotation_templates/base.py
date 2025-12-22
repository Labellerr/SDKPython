import uuid

from .. import constants
from ..client import LabellerrClient
from ..exceptions import InvalidAnnotationTemplateError


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

    def __new__(
        cls,
        client: "LabellerrClient",
        annotation_template_id: str,
        _skip_api_fetch: bool = False,
        **kwargs,
    ):
        # If skip flag is set, create instance without API call
        if _skip_api_fetch:
            return super().__new__(cls)

        # Otherwise, fetch from API and validate
        annotation_template_data = cls.get_annotation_template(
            client, annotation_template_id
        )

        if not annotation_template_data or (
            isinstance(annotation_template_data, dict) and not annotation_template_data
        ):
            raise InvalidAnnotationTemplateError(
                f"Annotation template with ID '{annotation_template_id}' does not exist or could not be retrieved."
            )

        # Pass fetched data to __init__ via kwargs
        kwargs["_fetched_data"] = annotation_template_data
        return super().__new__(cls)

    def __init__(
        self,
        client: "LabellerrClient",
        annotation_template_id: str,
        _skip_api_fetch: bool = False,
        **kwargs,
    ):
        self.client = client
        self.__annotation_template_id = annotation_template_id

        # Set __annotation_template_data from either source
        if "_cached_data" in kwargs:
            # Data provided directly (from factory method)
            self.__annotation_template_data = kwargs["_cached_data"]
        elif "_fetched_data" in kwargs:
            # Data fetched in __new__
            self.__annotation_template_data = kwargs["_fetched_data"]
        else:
            # Fallback - shouldn't happen in normal usage
            self.__annotation_template_data = {}

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

        # Create instance without API call - explicit flag makes intent clear
        return cls(
            client,
            annotation_template_id=kwargs.get("template_id"),
            _skip_api_fetch=True,
            _cached_data=kwargs,
        )

    @property
    def template_name(self):
        return self.__annotation_template_data.get("template_name")

    @property
    def data_type(self):
        return self.__annotation_template_data.get("data_type")

    @property
    def annotation_template_id(self):
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
