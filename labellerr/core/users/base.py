import json
import uuid

from .. import LabellerrClient
from .. import constants, schemas
from ..base.singleton import Singleton
from ..schemas import CreateUserParams, DeleteUserParams, UpdateUserRoleParams


class LabellerrUsers(Singleton):

    def __init__(self, client: "LabellerrClient", *args):
        super().__init__(*args)
        self.client = client

    def create_user(self, params: CreateUserParams):
        """
        Creates a new user in the system.

        :param params: CreateUserParams object containing user details (first_name, last_name, email_id, projects, roles, work_phone, job_title, language, timezone)
        :return: Dictionary containing user creation response
        :raises LabellerrError: If the creation fails
        """
        # Validate parameters using Pydantic

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/register?client_id={params.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "first_name": params.first_name,
                "last_name": params.last_name,
                "work_phone": params.work_phone,
                "job_title": params.job_title,
                "language": params.language,
                "timezone": params.timezone,
                "email_id": params.email_id,
                "projects": params.projects,
                "client_id": params.client_id,
                "roles": params.roles,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def update_user_role(self, params: UpdateUserRoleParams):
        """
        Updates a user's role and profile information.

        :param params: UpdateUserRoleParams object containing user update details (project_id, email_id, roles, first_name, last_name, work_phone, job_title, language, timezone, profile_image)
        :return: Dictionary containing update response
        :raises LabellerrError: If the update fails
        """

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/update?client_id={self.client.client_id}&project_id={params.project_id}&uuid={unique_id}"

        # Build the payload with all provided information
        # Extract project_ids from roles for API requirement
        project_ids = [
            role.get("project_id") for role in params.roles if "project_id" in role
        ]

        payload_data = {
            "profile_image": params.profile_image,
            "work_phone": params.work_phone,
            "job_title": params.job_title,
            "language": params.language,
            "timezone": params.timezone,
            "email_id": params.email_id,
            "client_id": params.client_id,
            "roles": params.roles,
            "projects": project_ids,  # API requires projects list extracted from roles (same format as create_user)
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name

        payload = json.dumps(payload_data)

        return self.client.make_request(
            "POST",
            url,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def delete_user(self, params: DeleteUserParams):
        """
        Deletes a user from the system.

        :param params: DeleteUserParams object containing user deletion details
        (project_id, email_id, user_id, first_name, last_name, is_active, role, user_created_at, max_activity_created_at, image_url, name, activity, creation_date, status)
        :return: Dictionary containing deletion response
        :raises LabellerrError: If the deletion fails
        """
        # Validate parameters using Pydantic

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/delete?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        # Build the payload with all provided information
        payload_data = {
            "email_id": params.email_id,
            "is_active": params.is_active,
            "role": params.role,
            "user_id": params.user_id,
            "imageUrl": params.image_url,
            "email": params.email_id,
            "activity": params.activity,
            "status": params.status,
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name
        if params.user_created_at is not None:
            payload_data["user_created_at"] = params.user_created_at
        if params.max_activity_created_at is not None:
            payload_data["max_activity_created_at"] = params.max_activity_created_at
        if params.name is not None:
            payload_data["name"] = params.name
        if params.creation_date is not None:
            payload_data["creationDate"] = params.creation_date

        payload = json.dumps(payload_data)

        return self.client.make_request(
            "POST",
            url,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def add_user_to_project(self, project_id, email_id, role_id=None):
        """
        Adds a user to a project.

        :param project_id: The ID of the project
        :param email_id: User's email address
        :param role_id: Optional role ID to assign to the user
        :return: Dictionary containing addition response
        :raises LabellerrError: If the addition fails
        """
        # Validate parameters using Pydantic
        params = schemas.AddUserToProjectParams(
            client_id=self.client.client_id,
            project_id=project_id,
            email_id=email_id,
            role_id=role_id,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/add_user_to_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        if params.role_id is not None:
            payload_data["role_id"] = params.role_id

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def remove_user_from_project(self, project_id, email_id):
        """
        Removes a user from a project.

        :param project_id: The ID of the project
        :param email_id: User's email address
        :return: Dictionary containing removal response
        :raises LabellerrError: If the removal fails
        """
        # Validate parameters using Pydantic
        params = schemas.RemoveUserFromProjectParams(
            client_id=self.client.client_id, project_id=project_id, email_id=email_id
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/remove_user_from_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    # TODO: this is not working from UI
    def change_user_role(self, project_id, email_id, new_role_id):
        """
        Changes a user's role in a project.

        :param project_id: The ID of the project
        :param email_id: User's email address
        :param new_role_id: The new role ID to assign to the user
        :return: Dictionary containing role change response
        :raises LabellerrError: If the role change fails
        """
        # Validate parameters using Pydantic
        params = schemas.ChangeUserRoleParams(
            client_id=self.client.client_id,
            project_id=project_id,
            email_id=email_id,
            new_role_id=new_role_id,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/change_user_role?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {
            "email_id": params.email_id,
            "new_role_id": params.new_role_id,
            "uuid": unique_id,
        }

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )
