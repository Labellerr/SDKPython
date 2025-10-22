import json
import logging
import uuid

from labellerr import LabellerrError, constants


def _setup_cloud_connector(self, connector_type, client_id, connector_config):
    """
    Sets up cloud connector (GCP/AWS) for dataset creation.

    :param connector_type: Type of connector ('gcp' or 'aws')
    :param client_id: Client ID
    :param connector_config: Configuration dictionary for the connector
    :return: Connection ID for the cloud connector
    """
    try:
        if connector_type == "gcp":
            return self._setup_gcp_connector(client_id, connector_config)
        elif connector_type == "aws":
            return self._setup_aws_connector(client_id, connector_config)
        else:
            raise LabellerrError(f"Unsupported connector type: {connector_type}")
    except Exception as e:
        logging.error(f"Failed to setup {connector_type} connector: {e}")
        raise


def _setup_gcp_connector(self, client_id, gcp_config):
    """
    Sets up GCP connector for dataset creation.

    :param client_id: Client ID
    :param gcp_config: GCP configuration containing bucket_name, folder_path, credentials
    :return: Connection ID for GCP connector
    """
    required_fields = ["bucket_name"]
    for field in required_fields:
        if field not in gcp_config:
            raise LabellerrError(f"Required field '{field}' missing in gcp_config")

    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/connectors/connect/gcp?client_id={client_id}&uuid={unique_id}"
    headers = self._build_headers(
        client_id=client_id,
        extra_headers={"content-type": "application/json"},
    )

    payload = json.dumps(
        {
            "bucket_name": gcp_config["bucket_name"],
            "folder_path": gcp_config.get("folder_path", ""),
            "service_account_key": gcp_config.get("service_account_key"),
        }
    )

    response_data = self._request(
        "POST", url, headers=headers, data=payload, request_id=unique_id
    )
    return response_data["response"]["connection_id"]


def _setup_aws_connector(self, client_id, aws_config):
    """
    Sets up AWS S3 connector for dataset creation.

    :param client_id: Client ID
    :param aws_config: AWS configuration containing bucket_name, folder_path, credentials
    :return: Connection ID for AWS connector
    """
    required_fields = ["bucket_name"]
    for field in required_fields:
        if field not in aws_config:
            raise LabellerrError(f"Required field '{field}' missing in aws_config")

    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/connectors/connect/aws?client_id={client_id}&uuid={unique_id}"
    headers = self._build_headers(
        client_id=client_id,
        extra_headers={"content-type": "application/json"},
    )

    payload = json.dumps(
        {
            "bucket_name": aws_config["bucket_name"],
            "folder_path": aws_config.get("folder_path", ""),
            "access_key_id": aws_config.get("access_key_id"),
            "secret_access_key": aws_config.get("secret_access_key"),
            "region": aws_config.get("region", "us-east-1"),
        }
    )

    response_data = self._request(
        "POST", url, headers=headers, data=payload, request_id=unique_id
    )
    return response_data["response"]["connection_id"]
