"""
Schema models for project operations.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .base import DatasetDataType


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


class CreateProjectParams(BaseModel):
    """Parameters for creating a project."""

    project_name: str = Field(min_length=1)
    data_type: DatasetDataType
    rotations: RotationConfig
    use_ai: bool = False
    created_by: Optional[str] = Field(
        None, pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )


class CreateTemplateParams(BaseModel):
    """Parameters for creating an annotation template."""

    client_id: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    template_name: str = Field(min_length=1)
    questions: List[Question] = Field(min_length=1)


class CreateLocalExportParams(BaseModel):
    """Parameters for creating a local export."""

    project_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    export_config: Dict[str, Any]


class StageProgress(BaseModel):
    """Files in one workflow stage."""

    queued: int
    """Waiting for someone to pick them up."""
    working: int
    """Picked up and in progress."""
    rework: int
    """Sent back to this stage to be done again."""


class WorkflowStages(BaseModel):
    """Files in each workflow stage."""

    annotation: StageProgress
    review: StageProgress
    client_review: StageProgress


class ProjectProgress(BaseModel):
    """
    How far a project's files have got through the workflow, all counted at one
    instant (``computed_at``). Fields match the API; unknown fields are ignored.
    """

    file_count: int
    """Total files in the project."""
    counts: Dict[str, int]
    """Files per status, e.g. ``{"None": 120, "review": 30, "accepted": 900}``."""
    unmapped: int
    """Files whose status isn't part of the workflow."""
    stages: WorkflowStages
    """Queued, working and rework files for annotation, review and client review."""
    done: int
    """Files accepted."""
    blocked: int
    """Files set aside (skipped too many times)."""
    finished: int
    """Accepted, with the client, or set aside: the dashboard's "complete"."""
    computed_at: int
    """When the files were counted, in epoch milliseconds."""

    @property
    def percent_complete(self) -> int:
        """
        ``finished`` as a whole percentage of ``file_count``, rounded down like the
        dashboard (so it never says 100 before every file is finished); 0 with no
        files.
        """
        if self.file_count <= 0:
            return 0
        return self.finished * 100 // self.file_count

    @property
    def is_complete(self) -> bool:
        """True when the project has files and every one of them is finished."""
        return self.file_count > 0 and self.finished == self.file_count
