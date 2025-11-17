"""This module will contain all CRUD for connections. Example, create, list connections, get connection, delete connection, update connection, etc."""

import uuid
from abc import ABCMeta
from typing import Dict
from .. import client_utils, constants
from ..schemas import ConnectionType, DatasetDataType
from ..exceptions import InvalidConnectionError

from ..client import LabellerrClient


class LabellerrConnectionMeta(ABCMeta):
    # Class-level registry for connection types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, connection_type, connection_class):
        """Register a connection type handler"""
        cls._registry[connection_type] = connection_class

    @staticmethod
    def get_connection(client: "LabellerrClient", connection_id: str):
        """Get connection from Labellerr API"""

        assert connection_id, "Connection ID is can't be empty"
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/connections/{connection_id}/details"

        params = {"client_id": client.client_id, "uuid": unique_id}

        extra_headers = {"content-type": "application/json"}

        response = client.make_request(
            "GET", url, extra_headers=extra_headers, request_id=unique_id, params=params
        )
        return response.get("response", None)

    """Metaclass that combines ABC functionality with factory pattern"""

    def __call__(cls, client, connection_id, **kwargs):
        # Only intercept calls to the base LabellerrConnection class
        if cls.__name__ != "LabellerrConnection":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, connection_id, **kwargs)
            return instance
        connection_data = cls.get_connection(client, connection_id)
        if connection_data is None:
            raise InvalidConnectionError(f"Connection not found: {connection_id}")
        connector = connection_data.get("connector")
        connection_class = cls._registry.get(connector)
        if connection_class is None:
            raise InvalidConnectionError(f"Unknown connector type: {connector}")
        kwargs["connection_data"] = connection_data
        return connection_class(client, connection_id, **kwargs)


class LabellerrConnection(metaclass=LabellerrConnectionMeta):
    """Base class for all Labellerr connections with factory behavior"""

    def __init__(self, client: "LabellerrClient", connection_id: str, **kwargs):
        self.client = client
        self.__connection_id_input = connection_id
        self.__connection_data = kwargs["connection_data"]

    @property
    def name(self):
        return self.__connection_data.get("name")

    @property
    def description(self):
        return self.__connection_data.get("description")

    @property
    def connection_id(self):
        return self.__connection_id_input

    @property
    def connection_type(self):
        return self.__connection_data.get("connection_type")

    @property
    def connector(self):
        return self.__connection_data.get("connector")

    @property
    def created_at(self):
        return self.__connection_data.get("created_at")

    @property
    def created_by(self):
        return self.__connection_data.get("created_by")

    def test(
        self, path: str, connection_type: ConnectionType, data_type: DatasetDataType
    ):
        request_id = str(uuid.uuid4())
        test_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={self.client.client_id}&uuid={request_id}"
        )

        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=self.client.client_id,
            extra_headers={"email_id": self.client.api_key},
        )

        # Test endpoint also expects multipart/form-data format
        test_request = {
            "connector": (None, self.connector),
            "path": (None, path),
            "connection_type": (None, connection_type.value),
            "connection_id": (None, self.connection_id),
            "data_type": (None, data_type.value),
        }
        response = client_utils.request(
            "POST",
            test_connection_url,
            headers=headers,
            files=test_request,
            request_id=request_id,
        )
        return response.get("response", {})
