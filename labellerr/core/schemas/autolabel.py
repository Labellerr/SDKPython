"""
Schema models for autolabel and keyframe operations.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


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


class Hyperparameters(BaseModel):
    epochs: int = 10


class TrainingRequest(BaseModel):
    model_id: str
    projects: Optional[List[str]] = None
    hyperparameters: Optional[Hyperparameters] = Hyperparameters()
    slice_id: Optional[str] = None
    min_samples_per_class: Optional[int] = 100
    job_name: str
