"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc."""

import concurrent.futures
import json
import logging
import os
import uuid
from abc import ABCMeta
from typing import Dict

import requests

from .. import client_utils, constants, schemas
from ..exceptions import InvalidProjectError, LabellerrError
from .utils import poll
from ..exports import Export

from ..client import LabellerrClient


class LabellerrProjectMeta(ABCMeta):
    # Class-level registry for project types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, data_type, project_class):
        """Register a project type handler"""
        cls._registry[data_type] = project_class

    @staticmethod
    def get_project(client: "LabellerrClient", project_id: str):
        """Get project from Labellerr API"""
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/projects/project/{project_id}?client_id={client.client_id}"
            f"&uuid={unique_id}"
        )

        response = client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)

    """Metaclass that combines ABC functionality with factory pattern"""

    def __call__(cls, client, project_id, **kwargs):
        # Only intercept calls to the base LabellerrProject class
        if cls.__name__ != "LabellerrProject":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, project_id, **kwargs)
            return instance
        project_data = cls.get_project(client, project_id)
        if project_data is None:
            raise InvalidProjectError(f"Project not found: {project_id}")
        data_type = project_data.get("data_type")

        project_class = cls._registry.get(data_type)
        if project_class is None:
            raise InvalidProjectError(f"Unknown data type: {data_type}")
        kwargs["project_data"] = project_data
        return project_class(client, project_id, **kwargs)


class LabellerrProject(metaclass=LabellerrProjectMeta):
    """Base class for all Labellerr projects with factory behavior"""

    def __init__(self, client: "LabellerrClient", project_id: str, **kwargs):
        self.client = client
        self.__project_id_input = project_id
        self.__project_data = kwargs["project_data"]

    @property
    def project_id(self):
        return self.__project_id_input

    @property
    def status_code(self):
        return self.__project_data.get("status_code", 501)  # if not found, return 501

    @property
    def annotation_template_id(self):
        return self.__project_data.get("annotation_template_id")

    @property
    def created_by(self):
        return self.__project_data.get("created_by")

    @property
    def created_at(self):
        return self.__project_data.get("created_at")

    @property
    def data_type(self):
        return self.__project_data.get("data_type")

    @property
    def attached_datasets(self):
        return self.__project_data.get("attached_datasets")

    def detach_dataset_from_project(self, dataset_id=None, dataset_ids=None):
        """
        Detaches one or more datasets from an existing project.

        :param dataset_id: The ID of a single dataset to detach (for backward compatibility)
        :param dataset_ids: List of dataset IDs to detach (for batch operations)
        :return: Dictionary containing detachment status
        :raises LabellerrError: If the operation fails or if neither dataset_id nor dataset_ids is provided
        """
        # Handle both single and batch operations
        if dataset_id is None and dataset_ids is None:
            raise LabellerrError("Either dataset_id or dataset_ids must be provided")

        if dataset_id is not None and dataset_ids is not None:
            raise LabellerrError(
                "Cannot provide both dataset_id and dataset_ids. Use dataset_ids for batch operations."
            )

        # Convert single dataset_id to list for uniform processing
        if dataset_id is not None:
            dataset_ids = [dataset_id]

        # Validate parameters using Pydantic for each dataset
        validated_dataset_ids = []
        for ds_id in dataset_ids:
            params = schemas.DetachDatasetParams(
                client_id=self.client.client_id,
                project_id=self.project_id,
                dataset_id=ds_id,
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.DetachDatasetParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            dataset_id=dataset_ids[0],
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/delete_datasets_from_project?project_id={self.project_id}&uuid={unique_id}"

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def attach_dataset_to_project(self, dataset_id=None, dataset_ids=None):
        """
        Attaches one or more datasets to an existing project.

        :param dataset_id: The ID of a single dataset to attach (for backward compatibility)
        :param dataset_ids: List of dataset IDs to attach (for batch operations)
        :return: Dictionary containing attachment status
        :raises LabellerrError: If the operation fails or if neither dataset_id nor dataset_ids is provided
        """
        # Handle both single and batch operations
        if dataset_id is None and dataset_ids is None:
            raise LabellerrError("Either dataset_id or dataset_ids must be provided")

        if dataset_id is not None and dataset_ids is not None:
            raise LabellerrError(
                "Cannot provide both dataset_id and dataset_ids. Use dataset_ids for batch operations."
            )

        # Convert single dataset_id to list for uniform processing
        if dataset_id is not None:
            dataset_ids = [dataset_id]

        # Validate parameters using Pydantic for each dataset
        validated_dataset_ids = []
        for ds_id in dataset_ids:
            params = schemas.AttachDatasetParams(
                client_id=self.client.client_id,
                project_id=self.project_id,
                dataset_id=ds_id,
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.AttachDatasetParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            dataset_id=dataset_ids[0],
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/add_datasets_to_project?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def update_rotation_count(self, rotation_config):
        """
        Updates the rotation count for a project.

        :param rotation_config: Dictionary containing rotation configuration settings
        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/projects/rotations/add?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"

            payload = json.dumps(rotation_config)
            logging.info(f"Update Rotation Count Payload: {payload}")

            self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                data=payload,
            )

            logging.info("Rotation configuration updated successfully.")

            return {"msg": "project rotation configuration updated"}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    def preannotation_job_status_async(self, job_id):
        """
        Get the status of a preannotation job asynchronously with timeout protection.

        :param job_id: The job ID to check status for
        :return: concurrent.futures.Future object that will contain the final job status
        :raises LabellerrError: If job status check fails
        """

        def check_status():
            url = f"{constants.BASE_URL}/actions/upload_answers_status?project_id={self.project_id}&job_id={job_id}&client_id={self.client.client_id}"

            def get_job_status():
                response_data = self.client.make_request(
                    "GET",
                    url,
                    extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                )

                # Log current status for visibility
                current_status = response_data.get("response", {}).get(
                    "status", "unknown"
                )
                logging.info(f"Pre-annotation job status: {current_status}")

                # Check if job failed and raise error immediately
                if current_status == "failed":
                    raise LabellerrError("Internal server error: ", response_data)

                return response_data

            def is_job_completed(response_data):
                return response_data.get("response", {}).get("status") == "completed"

            def on_success(response_data):
                logging.info("Pre-annotation job completed successfully!")

            def on_exception(e):
                logging.exception(f"Failed to get preannotation job status: {str(e)}")
                raise LabellerrError(
                    f"Failed to get preannotation job status: {str(e)}"
                )

            return poll(
                function=get_job_status,
                condition=is_job_completed,
                on_success=on_success,
                on_exception=on_exception,
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(check_status)

    def __upload_preannotations(
        self,
        annotation_format,
        annotation_file,
        conf_bucket=None,
    ):
        """
        Uploads preannotation data to a project asynchronously.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: concurrent.futures.Future - call .result() to wait for completion
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = [
                "annotation_format",
                "annotation_file",
            ]
            for param in required_params:
                if param not in locals():
                    raise LabellerrError(f"Required parameter {param} is missing")

            if annotation_format not in constants.ANNOTATION_FORMAT:
                raise LabellerrError(
                    f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                )

            request_uuid = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/upload_answers?project_id={self.project_id}&answer_format={annotation_format}&client_id={self.client.client_id}&uuid={request_uuid}"
            if conf_bucket:
                assert conf_bucket in [
                    "low",
                    "medium",
                    "high",
                ], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                url += f"&conf_bucket={conf_bucket}"
            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, "rb") as f:
                files = [("file", (file_name, f, "application/octet-stream"))]
                response = self.client.make_request(
                    "POST",
                    url,
                    extra_headers={"email_id": self.client.api_key},
                    request_id=request_uuid,
                    handle_response=False,
                    data=payload,
                    files=files,
                )
            response_data = self.client.handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]

            logging.info(f"Preannotation job started successfully. Job ID: {job_id}")

            return self.preannotation_job_status_async(job_id)
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def upload_preannotations(
        self, annotation_format, annotation_file, conf_bucket=None, _async=False
    ):
        """
        Backward compatibility method for upload_preannotations.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :param _async: Whether to return a future object (True) or block until completion (False)
        :return: The response from the API (blocks until completion).
        :raises LabellerrError: If the upload fails.
        """
        future = self.__upload_preannotations(
            annotation_format, annotation_file, conf_bucket
        )
        if _async:
            return future
        else:
            return future.result()

    def create_export(self, export_config: schemas.CreateExportParams):
        """
        Creates an export with the given configuration.

        :param export_config: Export configuration dictionary
        :return: Export instance with report_id and status tracking
        :raises LabellerrError: If the export creation fails
        """
        if export_config.export_destination == schemas.ExportDestination.LOCAL:
            return self.create_local_export(export_config)

        else:
            payload = export_config.model_dump()
            if not export_config.connection_id or export_config.connection_id == "":
                raise LabellerrError("connection_id is required")
            payload.update(
                {
                    "question_ids": ["all"],
                }
            )

            response = self.client.make_request(
                "POST",
                f"{constants.BASE_URL}/sdk/export/files?project_id={self.project_id}&client_id={self.client.client_id}",
                extra_headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            report_id = response.get("response", {}).get("report_id")
            return Export(report_id=report_id, project=self)

    def create_local_export(self, export_config):
        """
        Creates a local export with the given configuration.

        :param export_config: Export configuration dictionary
        :return: Export instance with report_id and status tracking
        :raises LabellerrError: If the export creation fails
        """
        # Validate export config using client_utils
        client_utils.validate_export_config(export_config)

        unique_id = client_utils.generate_request_id()
        export_config.update({"export_destination": "local", "question_ids": ["all"]})

        payload = json.dumps(export_config)

        response = self.client.make_request(
            "POST",
            f"{constants.BASE_URL}/sdk/export/files?project_id={self.project_id}&client_id={self.client.client_id}",
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
            request_id=unique_id,
            data=payload,
        )
        report_id = response.get("response", {}).get("report_id")
        return Export(report_id=report_id, project=self)

    def check_export_status(self, report_ids: list[str]):
        request_uuid = client_utils.generate_request_id()
        try:
            if not report_ids:
                raise LabellerrError("report_ids cannot be empty")

            # Construct URL
            url = f"{constants.BASE_URL}/exports/status?project_id={self.project_id}&uuid={request_uuid}&client_id={self.client.client_id}"

            payload = json.dumps({"report_ids": report_ids})

            result = self.client.make_request(
                "POST",
                url,
                extra_headers={"Content-Type": "application/json"},
                request_id=request_uuid,
                data=payload,
            )

            # Now process each report_id
            for status_item in result.get("status", []):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = (  # noqa E999 todo check use of that
                        self.__fetch_exports_download_url(
                            project_id=self.project_id,
                            uuid=request_uuid,
                            export_id=status_item["report_id"],
                            client_id=self.client.client_id,
                        )
                    )

            return json.dumps(result, indent=2)

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to check export status: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error checking export status: {str(e)}")
            raise

    def list_files(self, search_queries, size=10, next_search_after=None):
        """
        Lists files in the project based on search queries.

        :param search_queries: Search query filters for finding files
        :param size: Number of results to return (default: 10)
        :param next_search_after: Pagination cursor for retrieving next page of results
        :return: Dictionary containing list of files and pagination info
        :raises LabellerrError: If the request fails
        """
        # Validate parameters using Pydantic
        params = schemas.ListFileParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            search_queries=search_queries,
            size=size,
            next_search_after=next_search_after,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/project_files?project_id={params.project_id}&client_id={params.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "search_queries": params.search_queries,
                "size": params.size,
                "next_search_after": params.next_search_after,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def bulk_assign_files(self, file_ids, new_status, assign_to=None):
        """
        Assigns multiple files to a new status or user in bulk.

        :param file_ids: List of file IDs to assign
        :param new_status: New status to assign to the files
        :param assign_to: Optional user email to assign files to
        :return: Dictionary containing bulk assignment results
        :raises LabellerrError: If the bulk assignment fails
        """
        # Validate parameters using Pydantic
        params = schemas.BulkAssignFilesParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            file_ids=file_ids,
            new_status=new_status,
            assign_to=assign_to,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/files/bulk_assign?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        payload = {
            "file_ids": params.file_ids,
            "new_status": params.new_status,
        }
        if assign_to:
            payload["assign_to"] = assign_to

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=json.dumps(payload),
        )

    def __fetch_exports_download_url(self, project_id, uuid, export_id, client_id):
        try:
            url = f"{constants.BASE_URL}/exports/download?project_id={project_id}&uuid={uuid}&report_id={export_id}&client_id={client_id}"
            response = self.client.make_request(
                "GET",
                url,
                extra_headers={"Content-Type": "application/json"},
                request_id=uuid,
            )
            return response.get("response")
        except Exception as e:
            raise LabellerrError(f"Failed to download export: {str(e)}")
