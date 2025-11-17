import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union

from .. import client_utils, constants, gcs
from ..exceptions import LabellerrError
from ..client import LabellerrClient


def get_total_folder_file_count_and_total_size(folder_path, data_type):
    """
    Retrieves the total count and size of files in a folder using memory-efficient iteration.

    :param folder_path: The path to the folder.
    :param data_type: The type of data for the files.
    :return: The total count and size of the files.
    """
    total_file_count = 0
    total_file_size = 0
    files_list = []

    # Use os.scandir for better performance and memory efficiency
    def scan_directory(directory):
        nonlocal total_file_count, total_file_size
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file():
                        file_path = entry.path
                        # Check if the file extension matches based on datatype
                        if not any(
                            file_path.endswith(ext)
                            for ext in constants.DATA_TYPE_FILE_EXT[data_type]
                        ):
                            continue
                        try:
                            file_size = entry.stat().st_size
                            files_list.append(file_path)
                            total_file_count += 1
                            total_file_size += file_size
                        except OSError as e:
                            logging.error(f"Error reading {file_path}: {str(e)}")
                    elif entry.is_dir():
                        # Recursively scan subdirectories
                        scan_directory(entry.path)
        except OSError as e:
            logging.error(f"Error scanning directory {directory}: {str(e)}")

    scan_directory(folder_path)
    return total_file_count, total_file_size, files_list


def get_total_file_count_and_total_size(files_list, data_type):
    """
    Retrieves the total count and size of files in a list.

    :param files_list: The list of file paths.
    :param data_type: The type of data for the files.
    :return: The total count and size of the files.
    """
    total_file_count = 0
    total_file_size = 0
    # for root, dirs, files in os.walk(folder_path):
    for file_path in files_list:
        if file_path is None:
            continue
        try:
            # check if the file extension matching based on datatype
            if not any(
                file_path.endswith(ext)
                for ext in constants.DATA_TYPE_FILE_EXT[data_type]
            ):
                continue
            file_size = os.path.getsize(file_path)
            total_file_count += 1
            total_file_size += file_size
        except OSError as e:
            logging.error(f"Error reading {file_path}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error reading {file_path}: {str(e)}")

    return total_file_count, total_file_size, files_list


def connect_local_files(
    client: "LabellerrClient", client_id, file_names, connection_id=None
):
    """
    Connects local files to the API.

    :param client_id: The ID of the client.
    :param file_names: The list of file names.
    :param connection_id: The ID of the connection.
    :return: The response from the API.
    """
    url = f"{constants.BASE_URL}/connectors/connect/local?client_id={client_id}"
    headers = client_utils.build_headers(
        api_key=client.api_key, api_secret=client.api_secret, client_id=client_id
    )

    body = {"file_names": file_names}
    if connection_id is not None:
        body["temporary_connection_id"] = connection_id

    return client_utils.request("POST", url, headers=headers, json=body)


def upload_files(
    client: "LabellerrClient", client_id: str, files_list: Union[str, List[str]]
):
    """
    Uploads files to the API.

    :param client_id: The ID of the client.
    :param files_list: The list of files to upload or a comma-separated string of file paths.
    :return: The connection ID from the API.
    :raises LabellerrError: If the upload fails.
    """
    if len(files_list) == 0:
        raise LabellerrError("No files to upload")

    response = __process_batch(client, client_id, files_list)
    connection_id = response["response"]["temporary_connection_id"]
    return connection_id


def __process_batch(
    client: "LabellerrClient", client_id, files_list, connection_id=None
):
    """
    Processes a batch of files for upload.

    :param client_id: The ID of the client
    :param files_list: List of file paths to process
    :param connection_id: Optional connection ID
    :return: Response from connect_local_files
    """
    # Prepare files for upload
    files = {}
    for file_path in files_list:
        file_name = os.path.basename(file_path)
        files[file_name] = file_path

    response = connect_local_files(client, client_id, list(files.keys()), connection_id)
    resumable_upload_links = response["response"]["resumable_upload_links"]
    for file_name in resumable_upload_links.keys():
        gcs.upload_to_gcs_resumable(resumable_upload_links[file_name], files[file_name])

    return response


def upload_folder_files_to_dataset(client: "LabellerrClient", data_config):
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
                get_total_folder_file_count_and_total_size(
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
                    logging.error(f"Unexpected error processing {file_path}: {str(e)}")
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
            os.cpu_count() or 1,  # Number of CPU cores (default to 1 if None)
            len(batches),  # Number of batches
            20,
        )
        connection_id = str(uuid.uuid4())
        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {
                executor.submit(
                    __process_batch,
                    client,
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
