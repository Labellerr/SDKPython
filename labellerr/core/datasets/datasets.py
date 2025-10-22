import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from labellerr import client_utils, gcs, schemas, utils
from labellerr.core import constants
from labellerr.exceptions import LabellerrError
from labellerr.utils import validate_params


class DataSets(object):
    """
    Handles dataset-related operations for the Labellerr API.
    """

    def __init__(self, api_key, api_secret, client):
        """
        Initialize the DataSets handler.

        :param api_key: The API key for authentication
        :param api_secret: The API secret for authentication
        :param client: Reference to the parent Labellerr Client instance for delegating certain operations
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = client

    def create_project(
        self,
        project_name,
        data_type,
        client_id,
        attached_datasets,
        annotation_template_id,
        rotations,
        use_ai=False,
        created_by=None,
    ):
        """
        Creates a project with the given configuration.

        :param project_name: Name of the project
        :param data_type: Type of data (image, video, etc.)
        :param client_id: ID of the client
        :param attached_datasets: List of dataset IDs to attach to the project
        :param annotation_template_id: ID of the annotation template
        :param rotations: Dictionary containing rotation configuration
        :param use_ai: Boolean flag for AI usage (default: False)
        :param created_by: Optional creator information
        :return: Project creation response
        :raises LabellerrError: If the creation fails
        """
        # Validate parameters using Pydantic
        params = schemas.CreateProjectParams(
            project_name=project_name,
            data_type=data_type,
            client_id=client_id,
            attached_datasets=attached_datasets,
            annotation_template_id=annotation_template_id,
            rotations=rotations,
            use_ai=use_ai,
            created_by=created_by,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/projects/create?client_id={params.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "project_name": params.project_name,
                "attached_datasets": params.attached_datasets,
                "data_type": params.data_type,
                "annotation_template_id": str(params.annotation_template_id),
                "rotations": params.rotations.model_dump(),
                "use_ai": params.use_ai,
                "created_by": params.created_by,
            }
        )

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def initiate_create_project(self, payload):
        """
        Orchestrates project creation by handling dataset creation, annotation guidelines,
        and final project setup.
        """

        try:
            # validate all the parameters
            required_params = [
                "client_id",
                "dataset_name",
                "dataset_description",
                "data_type",
                "created_by",
                "project_name",
                # Either annotation_guide or annotation_template_id must be provided
                "autolabel",
            ]
            for param in required_params:
                if param not in payload:
                    raise LabellerrError(f"Required parameter {param} is missing")

                if param == "client_id":
                    if (
                        not isinstance(payload[param], str)
                        or not payload[param].strip()
                    ):
                        raise LabellerrError("client_id must be a non-empty string")

            # Validate created_by email format
            created_by = payload.get("created_by")
            if (
                not isinstance(created_by, str)
                or "@" not in created_by
                or "." not in created_by.split("@")[-1]
            ):
                raise LabellerrError("Please enter email id in created_by")

            # Ensure either annotation_guide or annotation_template_id is provided
            if not payload.get("annotation_guide") and not payload.get(
                "annotation_template_id"
            ):
                raise LabellerrError(
                    "Please provide either annotation guide or annotation template id"
                )

            # If annotation_guide is provided, validate its entries
            if payload.get("annotation_guide"):
                for guide in payload["annotation_guide"]:
                    if "option_type" not in guide:
                        raise LabellerrError(
                            "option_type is required in annotation_guide"
                        )
                    if guide["option_type"] not in constants.OPTION_TYPE_LIST:
                        raise LabellerrError(
                            f"option_type must be one of {constants.OPTION_TYPE_LIST}"
                        )

            if "folder_to_upload" in payload and "files_to_upload" in payload:
                raise LabellerrError(
                    "Cannot provide both files_to_upload and folder_to_upload"
                )

            if "folder_to_upload" not in payload and "files_to_upload" not in payload:
                raise LabellerrError(
                    "Either files_to_upload or folder_to_upload must be provided"
                )

            if (
                isinstance(payload.get("files_to_upload"), list)
                and len(payload["files_to_upload"]) == 0
            ):
                payload.pop("files_to_upload")

            if "rotation_config" not in payload:
                payload["rotation_config"] = {
                    "annotation_rotation_count": 1,
                    "review_rotation_count": 1,
                    "client_review_rotation_count": 1,
                }
            self.validate_rotation_config(payload["rotation_config"])

            if payload["data_type"] not in constants.DATA_TYPES:
                raise LabellerrError(
                    f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                )

            logging.info("Rotation configuration validated . . .")

            logging.info("Creating dataset . . .")
            dataset_response = self.create_dataset(
                {
                    "client_id": payload["client_id"],
                    "dataset_name": payload["dataset_name"],
                    "data_type": payload["data_type"],
                    "dataset_description": payload["dataset_description"],
                },
                files_to_upload=payload.get("files_to_upload"),
                folder_to_upload=payload.get("folder_to_upload"),
            )

            dataset_id = dataset_response["dataset_id"]

            def check_dataset_status():
                dataset_status = self.client.get_dataset(
                    payload["client_id"], dataset_id
                )

                if isinstance(dataset_status, dict):
                    if "response" in dataset_status:
                        return dataset_status["response"].get("status_code", 200) == 300
                    else:
                        return True
                return False

            def is_dataset_ready(status):
                return status is True

            def on_success(status):
                logging.info("Dataset created and ready for use")

            def on_exception(e):
                logging.error(f"Error checking dataset status: {str(e)}")
                raise LabellerrError(f"Failed to check dataset status: {str(e)}")

            utils.poll(
                function=check_dataset_status,
                condition=is_dataset_ready,
                interval=5,
                on_success=on_success,
                on_exception=on_exception
            )

            if payload.get("annotation_template_id"):
                annotation_template_id = payload["annotation_template_id"]
            else:
                annotation_template_id = self.create_annotation_guideline(
                    payload["client_id"],
                    payload["annotation_guide"],
                    payload["project_name"],
                    payload["data_type"],
                )
            logging.info(f"Annotation guidelines created {annotation_template_id}")

            project_response = self.create_project(
                project_name=payload["project_name"],
                data_type=payload["data_type"],
                client_id=payload["client_id"],
                attached_datasets=[dataset_id],
                annotation_template_id=annotation_template_id,
                rotations=payload["rotation_config"],
                use_ai=payload.get("use_ai", False),
                created_by=payload["created_by"],
            )

            return {
                "status": "success",
                "message": "Project created successfully",
                "project_id": project_response,
            }

        except LabellerrError:
            raise
        except Exception:
            logging.exception("Unexpected error in project creation")
            raise

    def create_annotation_guideline(
        self, client_id, questions, template_name, data_type
    ):
        """
        Updates the annotation guideline for a project.

        :param config: A dictionary containing the project ID, data type, client ID, autolabel status, and the annotation guideline.
        :return: None
        :raises LabellerrError: If the update fails.
        """
        unique_id = str(uuid.uuid4())

        url = f"{constants.BASE_URL}/annotations/create_template?data_type={data_type}&client_id={client_id}&uuid={unique_id}"

        guide_payload = json.dumps(
            {"templateName": template_name, "questions": questions}
        )

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=client_id,
            extra_headers={"content-type": "application/json"},
        )

        try:
            response_data = client_utils.request(
                "POST", url, headers=headers, data=guide_payload, request_id=unique_id
            )
            return response_data["response"]["template_id"]
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to update project annotation guideline: {str(e)}")
            raise

    def validate_rotation_config(self, rotation_config):
        """
        Validates a rotation configuration.

        :param rotation_config: A dictionary containing the configuration for the rotations.
        :raises LabellerrError: If the configuration is invalid.
        """
        client_utils.validate_rotation_config(rotation_config)

    def create_dataset(
        self,
        dataset_config,
        files_to_upload=None,
        folder_to_upload=None,
        connector_config=None,
    ):
        """
        Creates a dataset with support for multiple data types and connectors.

        :param dataset_config: A dictionary containing the configuration for the dataset.
                              Required fields: client_id, dataset_name, data_type
                              Optional fields: dataset_description, connector_type
        :param files_to_upload: List of file paths to upload (for local connector)
        :param folder_to_upload: Path to folder to upload (for local connector)
        :param connector_config: Configuration for cloud connectors (GCP/AWS)
        :return: A dictionary containing the response status and the ID of the created dataset.
        """

        try:
            # Validate required fields
            required_fields = ["client_id", "dataset_name", "data_type"]
            for field in required_fields:
                if field not in dataset_config:
                    raise LabellerrError(
                        f"Required field '{field}' missing in dataset_config"
                    )

            # Validate data_type
            if dataset_config.get("data_type") not in constants.DATA_TYPES:
                raise LabellerrError(
                    f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                )

            connector_type = dataset_config.get("connector_type", "local")
            connection_id = None
            path = connector_type

            # Handle different connector types
            if connector_type == "local":
                if files_to_upload is not None:
                    try:
                        connection_id = self.client.upload_files(
                            client_id=dataset_config["client_id"],
                            files_list=files_to_upload,
                        )
                    except Exception as e:
                        raise LabellerrError(
                            f"Failed to upload files to dataset: {str(e)}"
                        )

                elif folder_to_upload is not None:
                    try:
                        result = self.upload_folder_files_to_dataset(
                            {
                                "client_id": dataset_config["client_id"],
                                "folder_path": folder_to_upload,
                                "data_type": dataset_config["data_type"],
                            }
                        )
                        connection_id = result["connection_id"]
                    except Exception as e:
                        raise LabellerrError(
                            f"Failed to upload folder files to dataset: {str(e)}"
                        )
                elif connector_config is None:
                    # Create empty dataset for local connector
                    connection_id = None

            elif connector_type in ["gcp", "aws"]:
                if connector_config is None:
                    raise LabellerrError(
                        f"connector_config is required for {connector_type} connector"
                    )

                try:
                    connection_id = self.client._setup_cloud_connector(
                        connector_type, dataset_config["client_id"], connector_config
                    )
                except Exception as e:
                    raise LabellerrError(
                        f"Failed to setup {connector_type} connector: {str(e)}"
                    )
            else:
                raise LabellerrError(f"Unsupported connector type: {connector_type}")

            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/datasets/create?client_id={dataset_config['client_id']}&uuid={unique_id}"
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=dataset_config["client_id"],
                extra_headers={"content-type": "application/json"},
            )

            payload = json.dumps(
                {
                    "dataset_name": dataset_config["dataset_name"],
                    "dataset_description": dataset_config.get(
                        "dataset_description", ""
                    ),
                    "data_type": dataset_config["data_type"],
                    "connection_id": connection_id,
                    "path": path,
                    "client_id": dataset_config["client_id"],
                    "connector_type": connector_type,
                }
            )
            response_data = client_utils.request(
                "POST", url, headers=headers, data=payload, request_id=unique_id
            )
            dataset_id = response_data["response"]["dataset_id"]

            return {"response": "success", "dataset_id": dataset_id}

        except LabellerrError as e:
            logging.error(f"Failed to create dataset: {e}")
            raise

    def delete_dataset(self, client_id, dataset_id):
        """
        Deletes a dataset from the system.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset to delete
        :return: Dictionary containing deletion status
        :raises LabellerrError: If the deletion fails
        """
        # Validate parameters using Pydantic
        params = schemas.DeleteDatasetParams(client_id=client_id, dataset_id=dataset_id)
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{params.dataset_id}/delete?client_id={params.client_id}&uuid={unique_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        return client_utils.request(
            "DELETE", url, headers=headers, request_id=unique_id
        )

    def upload_folder_files_to_dataset(self, data_config):
        """
        Uploads local files from a folder to a dataset using parallel processing.

        :param data_config: A dictionary containing the configuration for the data.
        :return: A dictionary containing the response status and the list of successfully uploaded files.
        :raises LabellerrError: If there are issues with file limits, permissions, or upload process
        """
        try:
            # Validate required fields in data_config
            required_fields = ["client_id", "folder_path", "data_type"]
            missing_fields = [
                field for field in required_fields if field not in data_config
            ]
            if missing_fields:
                raise LabellerrError(
                    f"Missing required fields in data_config: {', '.join(missing_fields)}"
                )

            # Validate folder path exists and is accessible
            if not os.path.exists(data_config["folder_path"]):
                raise LabellerrError(
                    f"Folder path does not exist: {data_config['folder_path']}"
                )
            if not os.path.isdir(data_config["folder_path"]):
                raise LabellerrError(
                    f"Path is not a directory: {data_config['folder_path']}"
                )
            if not os.access(data_config["folder_path"], os.R_OK):
                raise LabellerrError(
                    f"No read permission for folder: {data_config['folder_path']}"
                )

            success_queue = []
            fail_queue = []

            try:
                # Get files from folder
                total_file_count, total_file_volumn, filenames = (
                    self.client.get_total_folder_file_count_and_total_size(
                        data_config["folder_path"], data_config["data_type"]
                    )
                )
            except Exception as e:
                logging.error(f"Failed to analyze folder contents: {str(e)}")
                raise

            # Check file limits
            if total_file_count > constants.TOTAL_FILES_COUNT_LIMIT_PER_DATASET:
                raise LabellerrError(
                    f"Total file count: {total_file_count} exceeds limit of {constants.TOTAL_FILES_COUNT_LIMIT_PER_DATASET} files"
                )
            if total_file_volumn > constants.TOTAL_FILES_SIZE_LIMIT_PER_DATASET:
                raise LabellerrError(
                    f"Total file size: {total_file_volumn/1024/1024:.1f}MB exceeds limit of {constants.TOTAL_FILES_SIZE_LIMIT_PER_DATASET/1024/1024:.1f}MB"
                )

            logging.info(f"Total file count: {total_file_count}")
            logging.info(f"Total file size: {total_file_volumn/1024/1024:.1f} MB")

            # Use generator for memory-efficient batch creation
            def create_batches():
                current_batch = []
                current_batch_size = 0

                for file_path in filenames:
                    try:
                        file_size = os.path.getsize(file_path)
                        if (
                            current_batch_size + file_size > constants.FILE_BATCH_SIZE
                            or len(current_batch) >= constants.FILE_BATCH_COUNT
                        ):
                            if current_batch:
                                yield current_batch
                            current_batch = [file_path]
                            current_batch_size = file_size
                        else:
                            current_batch.append(file_path)
                            current_batch_size += file_size
                    except OSError as e:
                        logging.error(f"Error accessing file {file_path}: {str(e)}")
                        fail_queue.append(file_path)
                    except Exception as e:
                        logging.error(
                            f"Unexpected error processing {file_path}: {str(e)}"
                        )
                        fail_queue.append(file_path)

                if current_batch:
                    yield current_batch

            # Convert generator to list for ThreadPoolExecutor
            batches = list(create_batches())

            if not batches:
                raise LabellerrError(
                    "No valid files found to upload in the specified folder"
                )

            logging.info(f"CPU count: {os.cpu_count()}, Batch Count: {len(batches)}")

            # Calculate optimal number of workers based on CPU count and batch count
            max_workers = min(
                os.cpu_count(),  # Number of CPU cores
                len(batches),  # Number of batches
                20,
            )
            connection_id = str(uuid.uuid4())
            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self.__process_batch,
                        data_config["client_id"],
                        batch,
                        connection_id,
                    ): batch
                    for batch in batches
                }

                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        result = future.result()
                        if (
                            isinstance(result, dict)
                            and result.get("message") == "200: Success"
                        ):
                            success_queue.extend(batch)
                        else:
                            fail_queue.extend(batch)
                    except Exception as e:
                        logging.exception(e)
                        logging.error(f"Batch upload failed: {str(e)}")
                        fail_queue.extend(batch)

            if not success_queue and fail_queue:
                raise LabellerrError(
                    "All file uploads failed. Check individual file errors above."
                )

            return {
                "connection_id": connection_id,
                "success": success_queue,
                "fail": fail_queue,
            }

        except LabellerrError:
            raise
        except Exception as e:
            logging.error(f"Failed to upload files: {str(e)}")
            raise

    def __process_batch(self, client_id, files_list, connection_id=None):
        """
        Processes a batch of files.
        """
        # Prepare files for upload
        files = {}
        for file_path in files_list:
            file_name = os.path.basename(file_path)
            files[file_name] = file_path

        response = self.client.connect_local_files(
            client_id, list(files.keys()), connection_id
        )
        resumable_upload_links = response["response"]["resumable_upload_links"]
        for file_name in resumable_upload_links.keys():
            gcs.upload_to_gcs_resumable(
                resumable_upload_links[file_name], files[file_name]
            )

        return response

    def attach_dataset_to_project(
        self, client_id, project_id, dataset_id=None, dataset_ids=None
    ):
        """
        Attaches one or more datasets to an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
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
                client_id=client_id, project_id=project_id, dataset_id=ds_id
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.AttachDatasetParams(
            client_id=client_id, project_id=project_id, dataset_id=dataset_ids[0]
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/add_datasets_to_project?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def detach_dataset_from_project(
        self, client_id, project_id, dataset_id=None, dataset_ids=None
    ):
        """
        Detaches one or more datasets from an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
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
                client_id=client_id, project_id=project_id, dataset_id=ds_id
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.DetachDatasetParams(
            client_id=client_id, project_id=project_id, dataset_id=dataset_ids[0]
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/delete_datasets_from_project?project_id={params.project_id}&uuid={unique_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    @validate_params(client_id=str, datatype=str, project_id=str, scope=str)
    def get_all_datasets(
        self, client_id: str, datatype: str, project_id: str, scope: str
    ):
        """
        Retrieves datasets by parameters.

        :param client_id: The ID of the client.
        :param datatype: The type of data for the dataset.
        :param project_id: The ID of the project.
        :param scope: The permission scope for the dataset.
        :return: The dataset list as JSON.
        """
        # Validate parameters using Pydantic
        params = schemas.GetAllDatasetParams(
            client_id=client_id,
            datatype=datatype,
            project_id=project_id,
            scope=scope,
        )
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/list?client_id={params.client_id}&data_type={params.datatype}&permission_level={params.scope}"
            f"&project_id={params.project_id}&uuid={unique_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        return client_utils.request("GET", url, headers=headers, request_id=unique_id)
