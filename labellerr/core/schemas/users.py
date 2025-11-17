"""
Schema models for user operations.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
