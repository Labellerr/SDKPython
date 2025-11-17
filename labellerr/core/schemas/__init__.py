"""
Pydantic models for LabellerrClient method parameter validation.

This module provides organized schema models for various operations:
- base: Custom types and validators
- connections: AWS, GCS connection parameters
- datasets: Dataset operations and configurations
- projects: Project creation and management
- users: User management operations
- files: File operations and bulk assignments
- autolabel: Autolabel, keyframe, and training operations
"""

# Import from autolabel.typings for backward compatibility
from labellerr.core.autolabel.typings import *  # noqa: F403, F401

# Base custom types
from labellerr.core.schemas.base import DirPathStr, FilePathStr, NonEmptyStr

# Connection schemas
from labellerr.core.schemas.connectors import (
    AWSConnectionParams,
    DatasetDataType,
    DeleteConnectionParams,
    GCSConnectionParams,
    AWSConnectionTestParams,
    ConnectionType,
    ConnectorType,
    GCSConnectionTestParams,
)

# Dataset schemas
from labellerr.core.schemas.datasets import (
    AttachDatasetParams,
    DatasetConfig,
    DataSetScope,
    DeleteDatasetParams,
    DetachDatasetParams,
    EnableMultimodalIndexingParams,
    GetAllDatasetParams,
    GetMultimodalIndexingStatusParams,
    SyncDataSetParams,
    UploadFilesParams,
)

# File operation schemas
from labellerr.core.schemas.files import BulkAssignFilesParams, ListFileParams

# Project schemas
from labellerr.core.schemas.projects import (
    CreateLocalExportParams,
    CreateProjectParams,
    CreateTemplateParams,
    Question,
    RotationConfig,
)

# User schemas
from labellerr.core.schemas.users import (
    AddUserToProjectParams,
    ChangeUserRoleParams,
    CreateUserParams,
    DeleteUserParams,
    RemoveUserFromProjectParams,
    UpdateUserRoleParams,
)

# Autolabel schemas
from labellerr.core.schemas.autolabel import (
    Hyperparameters,
    KeyFrame,
    TrainingRequest,
)

# Export schemas
from labellerr.core.schemas.exports import CreateExportParams, ExportDestination


# Export annotation templates
from labellerr.core.schemas.annotation_templates import (
    AnnotationQuestion,
    Option,
    QuestionType,
)


__all__ = [
    # Base types
    "NonEmptyStr",
    "FilePathStr",
    "DirPathStr",
    # Connection schemas
    "AWSConnectionParams",
    "AWSConnectionTestParams",
    "GCSConnectionParams",
    "GCSConnectionTestParams",
    "DeleteConnectionParams",
    "ConnectorType",
    "ConnectionType",
    "DatasetDataType",
    # Dataset schemas
    "UploadFilesParams",
    "DeleteDatasetParams",
    "EnableMultimodalIndexingParams",
    "GetMultimodalIndexingStatusParams",
    "AttachDatasetParams",
    "DetachDatasetParams",
    "DataSetScope",
    "GetAllDatasetParams",
    "SyncDataSetParams",
    "DatasetConfig",
    # Project schemas
    "RotationConfig",
    "Question",
    "CreateProjectParams",
    "CreateTemplateParams",
    "CreateLocalExportParams",
    # User schemas
    "CreateUserParams",
    "UpdateUserRoleParams",
    "DeleteUserParams",
    "AddUserToProjectParams",
    "RemoveUserFromProjectParams",
    "ChangeUserRoleParams",
    # File operation schemas
    "ListFileParams",
    "BulkAssignFilesParams",
    # Autolabel schemas
    "KeyFrame",
    "Hyperparameters",
    "TrainingRequest",
    # Export schemas
    "CreateExportParams",
    "ExportDestination",
    # Annotation templates schemas
    "AnnotationQuestion",
    "Option",
    "QuestionType",
]
