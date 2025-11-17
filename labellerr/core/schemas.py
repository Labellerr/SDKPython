"""
Pydantic models for LabellerrClient method parameter validation.
"""

import os
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .autolabel.typings import *  # noqa: F403, F401


class NonEmptyStr(str):
    """Custom string type that cannot be empty or whitespace-only."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class FilePathStr(str):
    """File path that must exist and be a valid file."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not os.path.exists(v):
            raise ValueError(f"file does not exist: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"path is not a file: {v}")
        return v


class DirPathStr(str):
    """Directory path that must exist and be accessible."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not os.path.exists(v):
            raise ValueError(f"folder path does not exist: {v}")
        if not os.path.isdir(v):
            raise ValueError(f"path is not a directory: {v}")
        if not os.access(v, os.R_OK):
            raise ValueError(f"no read permission for folder: {v}")
        return v


class RotationConfig(BaseModel):
    """Rotation configuration model."""

    annotation_rotation_count: int = Field(ge=1)
    review_rotation_count: int = Field(ge=1)
    client_review_rotation_count: int = Field(ge=1)


class Question(BaseModel):
    """Question structure for annotation templates."""

    option_type: Literal[
        "input",
        "radio",
        "boolean",
        "select",
        "dropdown",
        "stt",
        "imc",
        "BoundingBox",
        "polygon",
        "dot",
        "audio",
    ]
    # Additional fields can be added as needed


class AWSConnectionParams(BaseModel):
    """Parameters for creating an AWS S3 connection."""

    client_id: str = Field(min_length=1)
    aws_access_key: str = Field(min_length=1)
    aws_secrets_key: str = Field(min_length=1)
    s3_path: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    name: str = Field(min_length=1)
    description: str
    connection_type: str = "import"


class DatasetDataType(str, Enum):
    """Enum for dataset data types."""

    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    text = "text"


class GCSConnectionParams(BaseModel):
    """Parameters for creating a GCS connection."""

    client_id: str = Field(min_length=1)
    gcs_cred_file: str
    gcs_path: str = Field(min_length=1)
    data_type: DatasetDataType
    name: str = Field(min_length=1)
    description: str
    connection_type: str = "import"
    credentials: str = "svc_account_json"

    @field_validator("gcs_cred_file")
    @classmethod
    def validate_gcs_cred_file(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"GCS credential file not found: {v}")
        return v


class DeleteConnectionParams(BaseModel):
    """Parameters for deleting a connection."""

    client_id: str = Field(min_length=1)
    connection_id: str = Field(min_length=1)


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


class CreateLocalExportParams(BaseModel):
    """Parameters for creating a local export."""

    project_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    export_config: Dict[str, Any]


class CreateProjectParams(BaseModel):
    """Parameters for creating a project."""

    project_name: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    client_id: str = Field(min_length=1)
    attached_datasets: List[str] = Field(min_length=1)
    annotation_template_id: str
    rotations: RotationConfig
    use_ai: bool = False
    created_by: Optional[str] = None

    @field_validator("attached_datasets")
    @classmethod
    def validate_attached_datasets(cls, v):
        if not v:
            raise ValueError("must contain at least one dataset ID")
        for i, dataset_id in enumerate(v):
            if not isinstance(dataset_id, str) or not dataset_id.strip():
                raise ValueError(f"dataset_id at index {i} must be a non-empty string")
        return v


class CreateTemplateParams(BaseModel):
    """Parameters for creating an annotation template."""

    client_id: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    template_name: str = Field(min_length=1)
    questions: List[Question] = Field(min_length=1)


class CreateUserParams(BaseModel):
    """Parameters for creating a user."""

    client_id: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    projects: List[str] = Field(min_length=1)
    roles: List[Dict[str, Any]] = Field(min_length=1)
    work_phone: str = ""
    job_title: str = ""
    language: str = "en"
    timezone: str = "GMT"


class UpdateUserRoleParams(BaseModel):
    """Parameters for updating a user's role."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    roles: List[Dict[str, Any]] = Field(min_length=1)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    work_phone: str = ""
    job_title: str = ""
    language: str = "en"
    timezone: str = "GMT"
    profile_image: str = ""


class DeleteUserParams(BaseModel):
    """Parameters for deleting a user."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: int = 1
    role: str = "Annotator"
    user_created_at: Optional[str] = None
    max_activity_created_at: Optional[str] = None
    image_url: str = ""
    name: Optional[str] = None
    activity: str = "No Activity"
    creation_date: Optional[str] = None
    status: str = "Activated"


class AddUserToProjectParams(BaseModel):
    """Parameters for adding a user to a project."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    role_id: Optional[str] = None


class RemoveUserFromProjectParams(BaseModel):
    """Parameters for removing a user from a project."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    email_id: str = Field(min_length=1)


class ChangeUserRoleParams(BaseModel):
    """Parameters for changing a user's role."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    new_role_id: str = Field(min_length=1)


class ListFileParams(BaseModel):
    """Parameters for listing files."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    search_queries: Dict[str, Any]
    size: int = Field(default=10, gt=0)
    next_search_after: Optional[Any] = None


class BulkAssignFilesParams(BaseModel):
    """Parameters for bulk assigning files."""

    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    file_ids: List[str] = Field(min_length=1)
    new_status: str = Field(min_length=1)
    assign_to: Optional[str] = None


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
    data_type: Literal["image", "video", "audio", "document", "text"]
    dataset_description: str = ""
    connector_type: Literal["local", "aws", "gcp"] = "local"


class KeyFrame(BaseModel):
    """
    Represents a key frame with validation using Pydantic.

    Business constraints:
    - frame_number must be non-negative (>= 0) as negative frame numbers don't make sense
    - All fields are strictly typed to prevent data corruption
    """

    model_config = {"strict": True}

    frame_number: int = Field(ge=0, description="Frame number must be non-negative")
    is_manual: bool = True
    method: str = "manual"
    source: str = "manual"
