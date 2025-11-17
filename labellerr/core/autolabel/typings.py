from typing import List, Optional

from pydantic import BaseModel


class Hyperparameters(BaseModel):
    epochs: int = 10


class TrainingRequest(BaseModel):
    model_id: str
    projects: Optional[List[str]] = None
    hyperparameters: Optional[Hyperparameters] = Hyperparameters()
    slice_id: Optional[str] = None
    min_samples_per_class: Optional[int] = 100
    job_name: str
