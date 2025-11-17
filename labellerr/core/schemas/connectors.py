"""
Schema models for connection operations (AWS, GCS, etc.).
"""

import os
from enum import Enum
from typing import Optional
from .base import DatasetDataType
from pydantic import BaseModel, Field, field_validator


class ConnectionType(str, Enum):
    """Enum for connection types."""

    _IMPORT = "import"
    _EXPORT = "export"


class ConnectorType(str, Enum):
    """Enum for connector types."""

    _S3 = "s3"
    _GCS = "gcs"
    _LOCAL = "local"


class GCSConnectionTestParams(BaseModel):
    """Parameters for testing a GCS connection."""

    svc_account_json: Optional[str] = Field(default=None, min_length=1)
    path: str = Field(min_length=1)
    connection_type: ConnectionType = ConnectionType._IMPORT
    data_type: DatasetDataType

    @field_validator("svc_account_json")
    @classmethod
    def validate_svc_account_json(cls, v):
        if v and not os.path.exists(v):
            raise ValueError(f"GCS credential file not found: {v}")
        return v


class GCSConnectionParams(GCSConnectionTestParams):
    """Parameters for creating a GCS connection."""

    name: str = Field(min_length=1)
    description: str


class AWSConnectionTestParams(BaseModel):
    """Parameters for testing an AWS S3 connection."""

    aws_access_key: str = Field(min_length=1)
    aws_secrets_key: str = Field(min_length=1)
    path: str = Field(min_length=1)
    connection_type: ConnectionType = ConnectionType._IMPORT
    data_type: DatasetDataType


class AWSConnectionParams(AWSConnectionTestParams):
    """Parameters for creating an AWS S3 connection."""

    name: str = Field(min_length=1)
    description: str


class DeleteConnectionParams(BaseModel):
    """Parameters for deleting a connection."""

    client_id: str = Field(min_length=1)
    connection_id: str = Field(min_length=1)
