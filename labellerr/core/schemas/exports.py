from typing import Dict
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class ExportDestination(str, Enum):
    LOCAL = "local"
    S3 = "s3"


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
    updated_after_timestamp: Optional[int] = Field(
        default=None,
        description="Unix Timestamp in milliseconds to filter files to be exported based on last updated time",
    )


class ExportsListResponse(BaseModel):
    completed: List[Dict] = Field(default=[])
    in_progress: List[Dict] = Field(default=[])
