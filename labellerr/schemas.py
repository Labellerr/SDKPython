"""
Backward compatibility module.
All schemas have been moved to labellerr.core.schemas.
This module re-exports everything for backward compatibility.
"""

# Re-export everything from core.schemas for backward compatibility
from labellerr.core.schemas import *  # noqa: F403

__all__ = [
    # Base types
    "NonEmptyStr",
    "FilePathStr",
    "DirPathStr",
    # Connection schemas
    "AWSConnectionParams",
    "GCSConnectionParams",
    "DeleteConnectionParams",
    "AWSConnectorConfig",
    "GCPConnectorConfig",
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
]
