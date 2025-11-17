"""
Schema models for file operations.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
