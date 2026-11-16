"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc."""

import concurrent.futures
import json
import logging
import os
import threading
import time
import uuid
from abc import ABCMeta
from typing import Dict, Optional

import requests

from .. import client_utils, constants, schemas
from ..exceptions import (
    InvalidProjectError,
    JobTimeoutError,
    LabellerrError,
    RateLimitError,
    ServerError,
)
from .utils import poll
from ..exports import Export

from ..client import LabellerrClient

# Pre-annotation job polling defaults (the interval matches what poll() used).
PREANNOTATION_POLL_INTERVAL = 2.0
PREANNOTATION_TIMEOUT = 3600.0


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
            f"{client.base_url}/projects/project/{project_id}?client_id={client.client_id}"
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
    def project_name(self):
        return self.__project_data.get("project_name")

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

    def status(self) -> Dict:
        """
        Poll project status until completion or timeout.

        Returns:
            Final project data with status information

        Examples:
            # Get current project status
            final_status = project.status()
        """

        def get_project_status():
            unique_id = str(uuid.uuid4())
            url = (
                f"{self.client.base_url}/projects/project/{self.project_id}?client_id={self.client.client_id}"
                f"&uuid={unique_id}"
            )

            response = self.client.make_request(
                "GET",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )
            project_data = response.get("response", {})
            if project_data:
                self.__project_data = project_data
            return project_data

        def is_completed(project_data):
            status_code = project_data.get("status_code", 500)
            # Consider project complete when status_code is 300 (success) or >= 400 (error/failed)
            return status_code == 300 or status_code >= 400

        def on_success(project_data):
            status_code = project_data.get("status_code", 500)
            if status_code == 300:
                logging.info(
                    "Project %s processing completed successfully!", self.project_id
                )
            else:
                logging.warning(
                    "Project %s processing finished with status code: %s",
                    self.project_id,
                    status_code,
                )
            return project_data

        return poll(
            function=get_project_status,
            condition=is_completed,
            interval=2.0,
            timeout=None,
            max_retries=None,
            on_success=on_success,
        )

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
        url = f"{self.client.base_url}/actions/jobs/delete_datasets_from_project?project_id={self.project_id}&uuid={unique_id}"

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
        url = f"{self.client.base_url}/actions/jobs/add_datasets_to_project?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

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
            url = f"{self.client.base_url}/projects/rotations/add?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"

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

    def preannotation_job_status(self, job_id: str) -> Dict:
        """
        Fetch the status of a pre-annotation job with a single request (no polling).

        :param job_id: The job ID to check status for
        :return: The API response; the job status is at ``["response"]["status"]``
        :raises LabellerrError: If the job reports ``failed`` or the request fails
        """
        url = f"{self.client.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={job_id}&client_id={self.client.client_id}"
        response_data = self.client.make_request("GET", url)

        current_status = (response_data.get("response") or {}).get("status", "unknown")
        logging.info(f"Pre-annotation job status: {current_status}")

        if current_status == "failed":
            raise LabellerrError("Internal server error: ", response_data)

        return response_data

    def wait_for_preannotation_job(
        self,
        job_id: str,
        timeout: Optional[float] = PREANNOTATION_TIMEOUT,
        interval: float = PREANNOTATION_POLL_INTERVAL,
    ) -> Dict:
        """
        Poll a pre-annotation job until it completes, fails or the timeout passes.

        Authentication, permission and not-found errors are raised at once. Transient
        failures (5xx, 429, connection problems) are retried until the deadline.

        :param job_id: The job ID to wait for
        :param timeout: Maximum seconds to wait (default 3600); None waits forever
        :param interval: Seconds between status requests (default 2)
        :return: The API response of the completed job
        :raises JobTimeoutError: If the job is not completed before the timeout
        :raises LabellerrError: If the job fails or a non-transient error occurs
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        last_error = None

        while True:
            try:
                response_data = self.preannotation_job_status(job_id)
                last_error = None
                if (response_data.get("response") or {}).get("status") == "completed":
                    logging.info("Pre-annotation job completed successfully!")
                    return response_data
            except (
                ServerError,
                RateLimitError,
                requests.exceptions.RequestException,
            ) as e:
                last_error = e
                logging.warning(f"Transient error checking pre-annotation job: {e}")
            except LabellerrError as e:
                if type(e) is LabellerrError:
                    # A failed job (or other untyped error): keep the message the
                    # blocking call has always raised. Typed errors pass through.
                    logging.error(f"Failed to get preannotation job status: {e}")
                    raise LabellerrError(
                        f"Failed to get preannotation job status: {e}"
                    ) from e
                raise

            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                message = (
                    f"Pre-annotation job {job_id} did not complete within "
                    f"{timeout} seconds"
                )
                if last_error is not None:
                    raise JobTimeoutError(message) from last_error
                raise JobTimeoutError(message)
            time.sleep(interval if remaining is None else min(interval, remaining))

    def preannotation_job_status_async(
        self,
        job_id: str,
        timeout: Optional[float] = PREANNOTATION_TIMEOUT,
        interval: float = PREANNOTATION_POLL_INTERVAL,
    ) -> concurrent.futures.Future:
        """
        Wait for a pre-annotation job in the background and return at once.

        A daemon thread runs :meth:`wait_for_preannotation_job` and ends when the
        job completes, fails or times out; it never outlives the deadline.

        :param job_id: The job ID to check status for
        :param timeout: Maximum seconds to wait (default 3600); None waits forever
        :param interval: Seconds between status requests (default 2)
        :return: concurrent.futures.Future whose result is the final job response.
            ``future.result()`` raises LabellerrError (JobTimeoutError on timeout).
        """
        future = concurrent.futures.Future()

        def run():
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(
                    self.wait_for_preannotation_job(job_id, timeout, interval)
                )
            except BaseException as e:
                if not isinstance(e, LabellerrError):
                    wrapped = LabellerrError(
                        f"Failed to get preannotation job status: {e}"
                    )
                    wrapped.__cause__ = e
                    e = wrapped
                logging.error(f"Failed to get preannotation job status: {e}")
                future.set_exception(e)

        threading.Thread(
            target=run, name=f"preannotation-job-{job_id}", daemon=True
        ).start()
        return future

    def __start_preannotation_upload(
        self,
        annotation_format,
        annotation_file,
        conf_bucket=None,
    ):
        """
        Uploads preannotation data to a project and returns the job ID.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: The pre-annotation job ID
        :raises LabellerrError: If the upload fails.
        """
        try:
            if annotation_format not in constants.ANNOTATION_FORMAT:
                raise LabellerrError(
                    f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                )

            request_uuid = str(uuid.uuid4())
            url = f"{self.client.base_url}/actions/upload_answers?project_id={self.project_id}&answer_format={annotation_format}&client_id={self.client.client_id}&uuid={request_uuid}"
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
                    request_id=request_uuid,
                    handle_response=False,
                    data=payload,
                    files=files,
                )
            response_data = self.client.handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]

            logging.info(f"Preannotation job started successfully. Job ID: {job_id}")

            return job_id
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def upload_preannotations(
        self,
        annotation_format: str,
        annotation_file: str,
        conf_bucket: Optional[str] = None,
        _async: bool = False,
        timeout: Optional[float] = PREANNOTATION_TIMEOUT,
        interval: float = PREANNOTATION_POLL_INTERVAL,
    ):
        """
        Upload preannotations and wait for the processing job.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :param _async: If True, return a Future right after the upload request;
            otherwise block until the job completes (or ``timeout`` passes)
        :param timeout: Maximum seconds to wait for the job (default 3600)
        :param interval: Seconds between status requests (default 2)
        :return: A Future (``_async=True``) or the final job response
        :raises LabellerrError: If the upload or the job fails
        :raises JobTimeoutError: If the job does not finish before ``timeout``
        """
        job_id = self.__start_preannotation_upload(
            annotation_format, annotation_file, conf_bucket
        )
        if _async:
            return self.preannotation_job_status_async(job_id, timeout, interval)
        return self.wait_for_preannotation_job(job_id, timeout, interval)

    def _build_export_search_queries(
        self, export_config: schemas.CreateExportParams
    ) -> list:
        import time

        search_queries = []
        valid_statuses = [s for s in (export_config.statuses or []) if s]
        if valid_statuses:
            search_queries.append(
                {
                    "op": "OR",
                    "id": "file_status",
                    "values": [{"p": "in", "v": valid_statuses}],
                }
            )
        if export_config.updated_after_timestamp:
            now_ms = int(time.time() * 1000)
            search_queries.append(
                {
                    "op": "OR",
                    "id": "last_updated_date",
                    "values": [
                        {
                            "p": "between",
                            "v": [
                                {
                                    "start": export_config.updated_after_timestamp,
                                    "end": now_ms,
                                }
                            ],
                        }
                    ],
                }
            )
        return search_queries

    def _fetch_slice_id(self, search_queries: list) -> str:
        files_res = self.list_files(search_queries=search_queries, size=10)
        response_data = files_res.get("response", {})
        slice_id = response_data.get("slice_id")
        if not slice_id:
            raise LabellerrError("Could not retrieve slice_id from project files.")
        return slice_id

    def _submit_export_job(self, export_config: schemas.CreateExportParams):
        # 1. Get slice_id based on user search filters
        search_queries = self._build_export_search_queries(export_config)
        slice_id = self._fetch_slice_id(search_queries)

        # 2. Build the payload
        unique_id = client_utils.generate_request_id()
        payload = {
            "export_name": export_config.export_name,
            "export_description": export_config.export_description or "",
            "export_format": export_config.export_format,
            "connection_id": export_config.connection_id,
            "destination": export_config.export_destination.value,
            "export_all": True,
            "export_status": "Generating Export",
            "file_activity": False,
            "question_ids": export_config.question_ids or ["all"],
            "slice_id": slice_id,
            "export_path": export_config.export_folder_path,
        }
        # Only send layout/delivery when set so the backend can auto-set them (e.g. for video)
        if export_config.export_layout:
            payload["export_layout"] = export_config.export_layout.value
        if export_config.delivery_format:
            payload["delivery_format"] = export_config.delivery_format.value

        # 3. Call the UI exports endpoint
        url = f"{self.client.base_url}/exports/files?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"
        headers = {"Content-Type": "application/json"}

        response = self.client.make_request(
            "POST",
            url,
            extra_headers=headers,
            request_id=unique_id,
            data=json.dumps(payload),
        )

        # 4. Extract report_id from response
        report_id = response.get("response") if isinstance(response, dict) else response
        return Export(report_id=report_id, project=self)

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
            if not export_config.connection_id or export_config.connection_id == "":
                raise LabellerrError("connection_id is required")
            return self._submit_export_job(export_config)

    def create_local_export(self, export_config: schemas.CreateExportParams):
        """
        Creates a local export with the given configuration.

        :param export_config: Export configuration dictionary
        :return: Export instance with report_id and status tracking
        :raises LabellerrError: If the export creation fails
        """
        return self._submit_export_job(export_config)

    def list_exports(self):
        """
        Lists all exports for the project.

        :return: ExportsListResponse
        :raises LabellerrError: If the request fails
        """
        request_uuid = client_utils.generate_request_id()
        url = f"{self.client.base_url}/exports/list?project_id={self.project_id}&uuid={request_uuid}&client_id={self.client.client_id}"

        response = self.client.make_request(
            "GET",
            url,
            request_id=request_uuid,
        )
        if not response:
            raise LabellerrError(
                f"No response received from list exports API (request_id: {request_uuid})"
            )
        if "response" not in response:
            error_msg = response.get("error", "Unknown error")
            raise LabellerrError(
                f"List exports API failed: {error_msg} (request_id: {request_uuid})"
            )
        response_data = response.get("response", {})

        return schemas.ExportsListResponse(
            completed=response_data.get("completed", []),
            in_progress=response_data.get("inProgress", []),
        )

    def check_export_status(self, report_ids: list[str]):
        request_uuid = client_utils.generate_request_id()
        try:
            if not report_ids:
                raise LabellerrError("report_ids cannot be empty")

            # Construct URL
            url = f"{self.client.base_url}/exports/status?project_id={self.project_id}&uuid={request_uuid}&client_id={self.client.client_id}"

            payload = json.dumps({"report_ids": report_ids})

            result = self.client.make_request(
                "POST",
                url,
                extra_headers={"Content-Type": "application/json"},
                request_id=request_uuid,
                data=payload,
            )

            # Now process each report_id
            for idx, status_item in enumerate(result.get("response", [])):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = self.__fetch_exports_download_url(
                        project_id=self.project_id,
                        uuid=request_uuid,
                        export_id=status_item["report_id"],
                        client_id=self.client.client_id,
                    )
                    result["response"][idx]["download_url"] = download_url

            return result

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
        url = f"{self.client.base_url}/search/project_files?project_id={params.project_id}&client_id={params.client_id}&uuid={unique_id}"

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
        url = f"{self.client.base_url}/actions/files/bulk_assign?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

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
            url = f"{self.client.base_url}/exports/download?project_id={project_id}&uuid={uuid}&report_id={export_id}&client_id={client_id}"
            response = self.client.make_request(
                "GET",
                url,
                extra_headers={"Content-Type": "application/json"},
                request_id=uuid,
            )
            return response.get("response")
        except LabellerrError:
            raise
        except Exception as e:
            raise LabellerrError(f"Failed to download export: {str(e)}")

    def import_users(self, from_project: "LabellerrProject"):
        """
        Imports users from a source project to the current project.

        :param from_project: The source project to import users from
        :return: Dictionary containing import results
        :raises LabellerrError: If the import fails
        """
        # Validate parameters using Pydantic
        unique_id = str(uuid.uuid4())
        url = f"{self.client.base_url}/users/projects/import_users?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {"selected_project_id": from_project.project_id, "import_all_users": True}
        )

        response = self.client.make_request(
            "POST",
            url,
            data=payload,
            extra_headers={"Content-Type": "application/json"},
        )
        return response.get("response")
