import json
import uuid
from ..client import LabellerrClient
from ..schemas import AWSConnectionParams, AWSConnectionTestParams
from .. import client_utils, constants
from .connections import LabellerrConnection, LabellerrConnectionMeta
import logging


class S3Connection(LabellerrConnection):

    @staticmethod
    def test_connection(
        client: "LabellerrClient", params: AWSConnectionTestParams
    ) -> dict:
        """
        Tests an AWS S3 connection.
        :param client: The LabellerrClient instance
        :param params: The AWS connection parameters
        :return: True if the connection is successful, False otherwise
        """
        request_id = str(uuid.uuid4())
        test_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={client.client_id}&uuid={request_id}"
        )

        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client.client_id,
            extra_headers={"email_id": client.api_key},
        )

        aws_credentials_json = json.dumps(
            {
                "access_key_id": params.aws_access_key,
                "secret_access_key": params.aws_secrets_key,
            }
        )

        # Test endpoint also expects multipart/form-data format
        test_request = {
            "credentials": (None, aws_credentials_json),
            "connector": (None, "s3"),
            "path": (None, params.path),
            "connection_type": (None, params.connection_type.value),
            "data_type": (None, params.data_type.value),
        }

        # Remove content-type from headers to let requests set it with boundary
        headers_without_content_type = {
            k: v for k, v in headers.items() if k.lower() != "content-type"
        }

        response = client_utils.request(
            "POST",
            test_connection_url,
            headers=headers_without_content_type,
            files=test_request,
            request_id=request_id,
        )
        return response.get("response", {})

    @staticmethod
    def create_connection(
        client: "LabellerrClient", params: AWSConnectionParams
    ) -> dict:
        """
        Creates an AWS S3 connection.

        :param client: The LabellerrClient instance
        :param params: AWSConnectionParams instance
        :return: Dictionary containing the response from the API
        """

        # Tests the connection before creating it
        response = S3Connection.test_connection(client, params)

        logging.info(f"Connection test response: {response}")

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/connections/create?client_id={client.client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client.client_id,
            extra_headers={"email_id": client.api_key},
        )

        creds_payload = json.dumps(
            {
                "access_key_id": params.aws_access_key,
                "secret_access_key": params.aws_secrets_key,
            }
        )
        request_payload = {
            "credentials": (None, creds_payload),
            "connector": (None, "s3"),
            "connection_type": (None, params.connection_type.value),
            "name": (None, params.name),
            "description": (None, params.description),
            "client_id": (None, client.client_id),
        }
        response_data = client_utils.request(
            "POST", url, headers=headers, files=request_payload, request_id=unique_id
        )
        return LabellerrConnection(
            client=client,
            connection_id=response_data.get("response", {}).get("connection_id"),
        )


LabellerrConnectionMeta._register("s3", S3Connection)
