from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ExportDestination(str, Enum):
    LOCAL = "local"
    S3 = "s3"


class ExportLayout(str, Enum):
    MONOLITHIC = "monolithic"
    PER_FILE = "per_file"


class DeliveryFormat(str, Enum):
    DATA_FILE = "data_file"
    MANIFEST = "manifest"
    ARCHIVE = "archive"


class CreateExportParams(BaseModel):
    """Parameters for creating an export."""

    export_name: str = Field(min_length=1)
    export_description: str = Field(min_length=1)
    export_format: str = Field(min_length=1)
    statuses: List[str] = Field(min_length=1)
    question_ids: List[str] = Field(default=["all"])
    export_destination: ExportDestination = Field(default=ExportDestination.LOCAL)
    connection_id: Optional[str] = None
    export_folder_path: Optional[str] = None
    export_layout: Optional[ExportLayout] = Field(
        default=None,
        description="'monolithic' (single file) or 'per_file' (one file per asset). Auto-set to 'per_file' for video projects when omitted",
    )
    delivery_format: Optional[DeliveryFormat] = Field(
        default=None,
        description="'data_file' for monolithic layout, 'manifest' or 'archive' for per_file layout. Auto-set based on layout when omitted",
    )
    updated_after_timestamp: Optional[int] = Field(
        default=None,
        description="Unix Timestamp in milliseconds to filter files to be exported based on last updated time",
    )


class ExportsListResponse(BaseModel):
    completed: List[Dict] = Field(default=[])
    in_progress: List[Dict] = Field(default=[])
