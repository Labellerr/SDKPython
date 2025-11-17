import uuid
from typing import TYPE_CHECKING

from .. import constants
from ...schemas import AWSConnectionParams, ConnectionType, ConnectorType
from ...schemas import GCSConnectionParams
from .connections import LabellerrConnection
from .gcs_connection import GCSConnection as LabellerrGCSConnection
from .s3_connection import S3Connection as LabellerrS3Connection

if TYPE_CHECKING:
    from ..client import LabellerrClient

__all__ = ["LabellerrGCSConnection", "LabellerrConnection", "LabellerrS3Connection"]


def create_connection(
    client: "LabellerrClient",
    connector_type: ConnectorType,
    params: AWSConnectionParams | GCSConnectionParams,
) -> LabellerrS3Connection | LabellerrGCSConnection:
    if connector_type == ConnectorType._S3:
        return LabellerrS3Connection.create_connection(client, params)
    elif connector_type == ConnectorType._GCS:
        return LabellerrGCSConnection.create_connection(client, params)
    else:
        raise ValueError(f"Unsupported connector type: {connector_type}")


def list_connections(
    client: "LabellerrClient",
    connector: ConnectorType,
    connection_type: ConnectionType = None,
) -> list[LabellerrGCSConnection | LabellerrS3Connection]:
    """
    Lists connections for a client
    :param client: LabellerrClient instance
    :param connection_type: Type of connection (import/export)
    :param connector: Optional connector type filter (s3, gcs, etc.)
    :return: List of connections
    """

    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/connectors/connections/list"

    params = {
        "client_id": client.client_id,
        "uuid": unique_id,
        "connector": connector,
    }
    if connection_type:
        params["connection_type"] = connection_type
    extra_headers = {"email_id": client.api_key}

    response = client.make_request(
        "GET", url, extra_headers=extra_headers, request_id=unique_id, params=params
    )
    return [
        LabellerrConnection(client, connection["connection_id"])
        for connection in response.get("response", [])
    ]


def delete_connection(client: "LabellerrClient", connection_id: str):
    """
    Deletes a connector connection by ID.
    :param connection_id: The ID of the connection to delete
    :return: Parsed JSON response
    """
    request_id = str(uuid.uuid4())
    url = (
        f"{constants.BASE_URL}/connectors/connections/delete"
        f"?client_id={client.client_id}&uuid={request_id}"
    )

    extra_headers = {"email_id": client.api_key}

    response = client.make_request(
        "POST",
        url,
        extra_headers=extra_headers,
        request_id=request_id,
        json={"connection_id": connection_id},
    )
    return response.get("response", None)
