import uuid
from abc import ABCMeta

from .. import constants
from ..client import LabellerrClient
from ..exceptions import LabellerrError


class LabellerrFileMeta(ABCMeta):
    """Metaclass that combines ABC functionality with factory pattern"""

    _registry = {}

    @classmethod
    def _register(cls, data_type, file_class):
        """Register a file type handler"""
        cls._registry[data_type.lower()] = file_class

    def __call__(
        cls,
        client: LabellerrClient,
        file_id: str,
        project_id: str | None = None,
        dataset_id: str | None = None,
        **kwargs,
    ):

        if cls.__name__ != "LabellerrFile":

            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(
                    client, file_id, project_id, dataset_id=dataset_id, **kwargs
                )
            return instance

        try:
            unique_id = str(uuid.uuid4())
            client_id = client.client_id
            assert (
                project_id or dataset_id
            ), "Either project_id or dataset_id must be provided"
            params = {
                "file_id": file_id,
                "include_answers": "false",
                "uuid": unique_id,
                "client_id": client_id,
            }
            if project_id:
                params["project_id"] = project_id
            elif dataset_id:
                params["dataset_id"] = dataset_id

            # Priority: project_id > dataset_id
            url = f"{constants.BASE_URL}/data/file_data"
            response = client.make_request(
                "GET", url, request_id=unique_id, params=params
            )
            data_type = response.get("data_type", "").lower()

            file_class = cls._registry.get(data_type)
            if file_class is None:
                raise LabellerrError(f"Unsupported file type: {data_type}")

            return file_class(
                client,
                file_id,
                project_id,
                dataset_id=dataset_id,
                file_data=response,
            )

        except Exception as e:
            raise LabellerrError(f"Failed to create file instance: {str(e)}")


class LabellerrFile(metaclass=LabellerrFileMeta):
    """Base class for all Labellerr files with factory behavior"""

    def __init__(
        self,
        client: "LabellerrClient",
        file_id: str,
        project_id: str | None = None,
        dataset_id: str | None = None,
        **kwargs,
    ):
        """
        Initialize base file attributes

        :param client: LabellerrClient instance
        :param file_id: Unique file identifier
        :param project_id: Project ID containing the file
        :param dataset_id: Optional dataset ID
        :param kwargs: Additional file data (file_metadata, response, etc.)
        """
        self.client = client
        self.__file_data = kwargs.get("file_data", {})

    @property
    def file_id(self):
        return self.__file_data.get("file_id", "")

    @property
    def project_id(self):
        return self.__file_data.get("project_id", "")

    @property
    def dataset_id(self):
        return self.__file_data.get("dataset_id", "")

    @property
    def metadata(self):
        return self.__file_data.get("file_metadata", {})
