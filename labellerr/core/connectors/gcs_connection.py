import uuid
import logging
import os
from .. import client_utils, constants
from ..client import LabellerrClient
from .connections import LabellerrConnection, LabellerrConnectionMeta
from ..schemas import GCSConnectionTestParams, GCSConnectionParams
from ..exceptions import LabellerrError


class GCSConnection(LabellerrConnection):

    @staticmethod
    def test_connection(
        client: "LabellerrClient", params: GCSConnectionTestParams
    ) -> dict:
        request_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={client.client_id}&uuid={request_id}"
        )

        # Prepare multipart form data
        files = []
        if params.svc_account_json and os.path.exists(params.svc_account_json):
            # If file path is provided, read and upload as file
            with open(params.svc_account_json, "rb") as f:
                files = [
                    (
                        "attachment_files",
                        (
                            params.svc_account_json.split("/")[-1],
                            f.read(),
                            "application/json",
                        ),
                    )
                ]
        else:
            raise LabellerrError("Service account JSON file is required")

        # Prepare form data payload
        form_data = {
            "connector": "gcs",
            "path": params.path,
            "connection_type": params.connection_type.value,
            "data_type": params.data_type.value,
        }

        # Build headers without content-type for multipart form data
        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client.client_id,
        )

        response = client_utils.request(
            "POST",
            url,
            headers=headers,
            data=form_data,
            files=files,
            request_id=request_id,
        )
        return response.get("response", {})

    @staticmethod
    def create_connection(
        client: "LabellerrClient", params: GCSConnectionParams
    ) -> str:
        """
        Sets up GCP connector for dataset creation (quick connection).

        :param client: The LabellerrClient instance
        :param gcp_config: GCP configuration containing bucket_name, folder_path, service_account_key
        :return: Connection ID for GCP connector
        """
        response = GCSConnection.test_connection(client, params)
        logging.info(f"GCS connection test response: {response}")

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/connections/create?client_id={client.client_id}&uuid={unique_id}"

        # Build headers without content-type for multipart form data
        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client.client_id,
        )

        # Prepare multipart form data
        with open(params.svc_account_json, "rb") as f:
            files = [
                (
                    "attachment_files",
                    (
                        params.svc_account_json.split("/")[-1],
                        f.read(),
                        "application/json",
                    ),
                )
            ]

        # Prepare form data (not JSON)
        form_data = {
            "connector": "gcs",
            "connection_type": params.connection_type.value,
            "name": params.name,
            "description": params.description,
            "credentials": "svc_account_json",
            "client_id": client.client_id,
        }

        response_data = client_utils.request(
            "POST",
            url,
            headers=headers,
            data=form_data,
            files=files,
            request_id=unique_id,
        )
        return LabellerrConnection(
            client=client,
            connection_id=response_data.get("response", {}).get("connection_id"),
        )


LabellerrConnectionMeta._register("gcs", GCSConnection)
