"""
Schema models for dataset operations.
"""

import os
from enum import StrEnum
from typing import List, Literal
from uuid import UUID

from .base import DatasetDataType
from pydantic import BaseModel, Field, field_validator


class DataSetScope(StrEnum):
    project = "project"
    client = "client"
    public = "public"


class UploadFilesParams(BaseModel):
    """Parameters for uploading files."""

    client_id: str = Field(min_length=1)
    files_list: List[str] = Field(min_length=1)

    @field_validator("files_list", mode="before")
    @classmethod
    def validate_files_list(cls, v):
        # Convert comma-separated string to list
        if isinstance(v, str):
            v = v.split(",")
        elif not isinstance(v, list):
            raise ValueError("must be either a list or a comma-separated string")

        if len(v) == 0:
            raise ValueError("no files to upload")

        # Validate each file exists
        for file_path in v:
            if not os.path.exists(file_path):
                raise ValueError(f"file does not exist: {file_path}")
            if not os.path.isfile(file_path):
                raise ValueError(f"path is not a file: {file_path}")

        return v


class DeleteDatasetParams(BaseModel):
    """Parameters for deleting a dataset."""

    client_id: str = Field(min_length=1)
    dataset_id: UUID


class EnableMultimodalIndexingParams(BaseModel):
    """Parameters for enabling multimodal indexing."""

    client_id: str = Field(min_length=1)
    dataset_id: UUID
    is_multimodal: bool = True


class GetMultimodalIndexingStatusParams(BaseModel):
    """Parameters for getting multimodal indexing status."""

    client_id: str = Field(min_length=1)
    dataset_id: UUID


class AttachDatasetParams(BaseModel):
    """Parameters for attaching a dataset to a project."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)  # Accept both UUID and string formats
    dataset_id: str


class DetachDatasetParams(BaseModel):
    """Parameters for detaching a dataset from a project."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)  # Accept both UUID and string formats
    dataset_id: str


class GetAllDatasetParams(BaseModel):
    """Parameters for getting all datasets."""

    client_id: str = Field(min_length=1)
    datatype: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    scope: Literal["project", "client", "public"]


class SyncDataSetParams(BaseModel):
    """Parameters for syncing datasets from cloud storage."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    connection_id: str = Field(min_length=1)


class DatasetConfig(BaseModel):
    """Configuration for creating a dataset."""

    dataset_name: str = Field(min_length=1)
    data_type: DatasetDataType
    dataset_description: str = ""
    multimodal_indexing: bool = False
