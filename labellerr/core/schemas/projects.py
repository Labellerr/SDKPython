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

    data_type: Literal["image", "video", "audio", "document", "text"]
    template_name: str = Field(min_length=1)
    questions: List[Question] = Field(min_length=1)


class CreateLocalExportParams(BaseModel):
    """Parameters for creating a local export."""

    project_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    export_config: Dict[str, Any]
