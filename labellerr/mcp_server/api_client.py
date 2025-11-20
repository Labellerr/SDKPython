#!/usr/bin/env python3
"""
Pure API Client for Labellerr - No SDK Dependencies

This client makes direct REST API calls to https://api.labellerr.com
and is completely independent of the SDK implementation.
"""

import os
import json
import uuid
import logging
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class LabellerrAPIError(Exception):
    """Exception raised for API errors"""
    def __init__(self, status_code: int, message: str, response_data: Any = None):
        self.status_code = status_code
        self.message = message
        self.response_data = response_data
        super().__init__(f"API Error {status_code}: {message}")


class LabellerrAPIClient:
    """Pure API client for Labellerr - no SDK dependencies"""
    
    BASE_URL = "https://api.labellerr.com"
    ALLOWED_ORIGINS = "https://pro.labellerr.com"
    
    # File upload constants
    DATA_TYPE_FILE_EXT = {
        "image": [".jpg", ".jpeg", ".png", ".tiff"],
        "video": [".mp4"],
        "audio": [".mp3", ".wav"],
        "document": [".pdf"],
        "text": [".txt"],
    }
    
    def __init__(self, api_key: str, api_secret: str, client_id: str):
        """
        Initialize the API client
        
        :param api_key: Labellerr API key
        :param api_secret: Labellerr API secret
        :param client_id: Labellerr client ID
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.client_id = client_id
        self.session = self._setup_session()
    
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry strategy and connection pooling"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Build request headers with authentication
        
        :param extra_headers: Additional headers to merge
        :return: Complete headers dictionary
        """
        headers = {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "client_id": self.client_id,
            "source": "mcp-server",
            "origin": self.ALLOWED_ORIGINS,
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request and handle response
        
        :param method: HTTP method (GET, POST, etc.)
        :param url: Full URL to request
        :param kwargs: Additional arguments for requests
        :return: Parsed JSON response
        :raises LabellerrAPIError: If request fails
        """
        # Build headers if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = self._build_headers()
        else:
            kwargs['headers'] = self._build_headers(kwargs['headers'])
        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (30, 300)  # (connect, read)
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Handle successful responses
            if response.status_code in [200, 201]:
                try:
                    return response.json()
                except ValueError:
                    raise LabellerrAPIError(
                        response.status_code,
                        f"Expected JSON response but got: {response.text}"
                    )
            
            # Handle error responses
            elif 400 <= response.status_code < 500:
                try:
                    error_data = response.json()
                    raise LabellerrAPIError(
                        response.status_code,
                        f"Client error: {error_data}",
                        error_data
                    )
                except ValueError:
                    raise LabellerrAPIError(
                        response.status_code,
                        f"Client error: {response.text}"
                    )
            
            else:  # 500+ errors
                raise LabellerrAPIError(
                    response.status_code,
                    f"Server error: {response.text}"
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise LabellerrAPIError(0, f"Request failed: {str(e)}")
    
    def close(self):
        """Close the session and cleanup resources"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    # =============================================================================
    # Dataset Operations
    # =============================================================================
    
    def create_dataset(
        self,
        dataset_name: str,
        data_type: str,
        dataset_description: str = "",
        connection_id: Optional[str] = None,
        path: str = "local",
        multimodal_indexing: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new dataset
        
        :param dataset_name: Name of the dataset
        :param data_type: Type of data (image, video, audio, document, text)
        :param dataset_description: Optional description
        :param connection_id: Connection ID for file storage
        :param path: Path to data source
        :param multimodal_indexing: Enable multimodal indexing
        :return: API response with dataset_id
        """
        unique_id = str(uuid.uuid4())
        url = f"{self.BASE_URL}/datasets/create?client_id={self.client_id}&uuid={unique_id}"
        
        payload = {
            "dataset_name": dataset_name,
            "dataset_description": dataset_description,
            "data_type": data_type,
            "connection_id": connection_id,
            "path": path,
            "client_id": self.client_id,
            "es_multimodal_index": multimodal_indexing
        }
        
        return self._make_request(
            "POST",
            url,
            headers={"content-type": "application/json"},
            data=json.dumps(payload)
        )
    
    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get dataset details
        
        :param dataset_id: ID of the dataset
        :return: Dataset information
        """
        unique_id = str(uuid.uuid4())
        url = f"{self.BASE_URL}/datasets/{dataset_id}?client_id={self.client_id}&uuid={unique_id}"
        
        return self._make_request(
            "GET",
            url,
            headers={"content-type": "application/json"}
        )
    
    def poll_dataset_status(
        self, 
        dataset_id: str, 
        interval: float = 2.0, 
        timeout: Optional[float] = 300
    ) -> Dict[str, Any]:
        """
        Poll dataset status until processing is complete
        
        :param dataset_id: ID of the dataset to poll
        :param interval: Time between status checks in seconds (default: 2.0)
        :param timeout: Maximum time to wait in seconds (default: 300, None for no timeout)
        :return: Final dataset status
        :raises LabellerrAPIError: If timeout is reached or dataset processing fails
        """
        import time
        
        start_time = time.time()
        
        while True:
            dataset_data = self.get_dataset(dataset_id)
            status_code = dataset_data.get("response", {}).get("status_code", 500)
            
            logger.debug(f"Dataset {dataset_id} status: {status_code}")
            
            # Status codes: 100=processing, 300=success, 400+=error
            if status_code == 300:
                logger.info(f"Dataset {dataset_id} processing completed successfully")
                return dataset_data
            elif status_code >= 400:
                logger.error(f"Dataset {dataset_id} processing failed with status {status_code}")
                return dataset_data
                
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise LabellerrAPIError(
                    408, 
                    f"Dataset status polling timed out after {timeout}s"
                )
                
            time.sleep(interval)
    
    def list_datasets(
        self,
        data_type: str = "image",
        scope: str = "client",
        page_size: int = 10,
        last_dataset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List datasets with pagination
        
        :param data_type: Type of data to filter by
        :param scope: Permission level (project, client, public)
        :param page_size: Number of datasets per page
        :param last_dataset_id: ID of last dataset from previous page
        :return: List of datasets
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/datasets/list"
            f"?client_id={self.client_id}"
            f"&data_type={data_type}"
            f"&permission_level={scope}"
            f"&page_size={page_size}"
            f"&uuid={unique_id}"
        )
        
        if last_dataset_id:
            url += f"&last_dataset_id={last_dataset_id}"
        
        return self._make_request(
            "GET",
            url,
            headers={"content-type": "application/json"}
        )
    
    def delete_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Delete a dataset
        
        :param dataset_id: ID of the dataset to delete
        :return: Deletion confirmation
        """
        unique_id = str(uuid.uuid4())
        url = f"{self.BASE_URL}/datasets/{dataset_id}/delete?client_id={self.client_id}&uuid={unique_id}"
        
        return self._make_request(
            "DELETE",
            url,
            headers={"content-type": "application/json"}
        )
    
    # =============================================================================
    # File Upload Operations
    # =============================================================================
    
    def upload_files_to_connector(self, file_paths: List[str]) -> str:
        """
        Upload files to GCS and get connection_id (using SDK-compatible approach)
        
        :param file_paths: List of local file paths to upload
        :return: connection_id for the uploaded files
        """
        # Get file names
        file_names = [os.path.basename(fp) for fp in file_paths]
        
        # Request resumable upload links from API (SDK approach)
        url = f"{self.BASE_URL}/connectors/connect/local?client_id={self.client_id}"
        payload = {"file_names": file_names}
        
        response = self._make_request(
            "POST",
            url,
            headers={"content-type": "application/json"},
            json=payload  # Use json parameter instead of data
        )
        
        # SDK returns temporary_connection_id and resumable_upload_links
        connection_id = response.get("response", {}).get("temporary_connection_id")
        resumable_upload_links = response.get("response", {}).get("resumable_upload_links", {})
        
        if not connection_id or not resumable_upload_links:
            raise LabellerrAPIError(500, "Failed to get resumable upload links from API")
        
        # Upload files to GCS using resumable upload (SDK approach)
        self._upload_files_to_gcs_resumable(file_paths, resumable_upload_links)
        
        return connection_id
    
    def upload_folder_to_connector(self, folder_path: str, data_type: str) -> str:
        """
        Upload all files from a folder to GCS
        
        :param folder_path: Path to folder containing files
        :param data_type: Type of data (determines which files to include)
        :return: connection_id for the uploaded files
        """
        # Scan folder for matching files
        file_paths = self._scan_folder(folder_path, data_type)
        
        if not file_paths:
            raise LabellerrAPIError(400, f"No {data_type} files found in {folder_path}")
        
        logger.info(f"Found {len(file_paths)} {data_type} files in {folder_path}")
        
        # Upload files
        return self.upload_files_to_connector(file_paths)
    
    def _scan_folder(self, folder_path: str, data_type: str) -> List[str]:
        """
        Recursively scan folder for files matching data type
        
        :param folder_path: Path to folder
        :param data_type: Type of data to filter by
        :return: List of file paths
        """
        file_paths = []
        extensions = self.DATA_TYPE_FILE_EXT.get(data_type, [])
        
        def scan_directory(directory):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_file():
                            if any(entry.name.lower().endswith(ext) for ext in extensions):
                                file_paths.append(entry.path)
                        elif entry.is_dir():
                            scan_directory(entry.path)
            except OSError as e:
                logger.error(f"Error scanning directory {directory}: {e}")
        
        scan_directory(folder_path)
        return file_paths
    
    def _upload_files_to_gcs_resumable(self, file_paths: List[str], resumable_upload_links: Dict[str, str]) -> None:
        """
        Upload files to GCS using resumable upload (SDK-compatible approach)
        
        :param file_paths: List of local file paths
        :param resumable_upload_links: Dictionary mapping file names to resumable upload URLs
        """
        # Create mapping of filename to file path
        files_map = {os.path.basename(fp): fp for fp in file_paths}
        
        def upload_single_file_resumable(file_name: str, resumable_url: str) -> bool:
            """Upload a single file to GCS using resumable upload"""
            file_path = files_map.get(file_name)
            
            if not file_path:
                logger.error(f"No file path for: {file_name}")
                return False
            
            try:
                file_size = os.path.getsize(file_path)
                
                # Step 1: Start resumable upload session
                headers = {
                    "x-goog-resumable": "start",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": "0"
                }
                
                response = requests.post(resumable_url, headers=headers, timeout=(30, 60))
                
                if response.status_code != 201:
                    logger.error(f"Failed to start resumable upload for {file_name}: {response.status_code}")
                    return False
                
                upload_url = response.headers.get("Location")
                if not upload_url:
                    logger.error(f"No upload URL returned for {file_name}")
                    return False
                
                # Step 2: Upload file content
                with open(file_path, 'rb') as f:
                    headers = {
                        "Content-Type": "application/octet-stream",
                        "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                        "Content-Length": str(file_size)
                    }
                    
                    upload_response = requests.put(
                        upload_url,
                        headers=headers,
                        data=f,
                        timeout=(30, 300)
                    )
                    
                    if upload_response.status_code in [200, 201]:
                        logger.debug(f"Uploaded {file_name} successfully (resumable)")
                        return True
                    else:
                        logger.error(f"Failed to upload {file_name}: {upload_response.status_code}")
                        return False
                    
            except Exception as e:
                logger.error(f"Error uploading {file_name}: {e}")
                return False
        
        # Upload files in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(upload_single_file_resumable, file_name, url): file_name 
                for file_name, url in resumable_upload_links.items()
            }
            
            failed_uploads = []
            for future in as_completed(futures):
                file_name = futures[future]
                try:
                    success = future.result()
                    if not success:
                        failed_uploads.append(file_name)
                except Exception as e:
                    logger.error(f"Upload failed for {file_name}: {e}")
                    failed_uploads.append(file_name)
            
            if failed_uploads:
                raise LabellerrAPIError(
                    500,
                    f"Failed to upload {len(failed_uploads)} files: {failed_uploads[:5]}"
                )
    
    # =============================================================================
    # Annotation Template Operations
    # =============================================================================
    
    def create_annotation_template(
        self,
        template_name: str,
        data_type: str,
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create an annotation template
        
        :param template_name: Name of the template
        :param data_type: Type of data (image, video, etc.)
        :param questions: List of annotation questions
        :return: API response with template_id
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/annotations/create_template"
            f"?client_id={self.client_id}"
            f"&data_type={data_type}"
            f"&uuid={unique_id}"
        )
        
        payload = {
            "templateName": template_name,
            "questions": questions
        }
        
        return self._make_request(
            "POST",
            url,
            headers={"content-type": "application/json"},
            json=payload
        )
    
    def get_annotation_template(self, template_id: str) -> Dict[str, Any]:
        """
        Get annotation template details
        
        :param template_id: ID of the template
        :return: Template information
        """
        url = (
            f"{self.BASE_URL}/annotations/get_template"
            f"?template_id={template_id}"
            f"&client_id={self.client_id}"
        )
        
        return self._make_request(
            "GET",
            url,
            headers={"content-type": "application/json"}
        )
    
    # =============================================================================
    # Project Operations
    # =============================================================================
    
    def create_project(
        self,
        project_name: str,
        data_type: str,
        attached_datasets: List[str],
        annotation_template_id: str,
        rotations: Dict[str, int],
        use_ai: bool = False,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new project
        
        :param project_name: Name of the project
        :param data_type: Type of data
        :param attached_datasets: List of dataset IDs to attach
        :param annotation_template_id: ID of annotation template
        :param rotations: Rotation configuration dict
        :param use_ai: Whether to use AI features
        :param created_by: Email of creator
        :return: API response with project_id
        """
        unique_id = str(uuid.uuid4())
        url = f"{self.BASE_URL}/projects/create?client_id={self.client_id}&uuid={unique_id}"
        
        payload = {
            "project_name": project_name,
            "attached_datasets": attached_datasets,
            "data_type": data_type,
            "annotation_template_id": annotation_template_id,
            "rotations": rotations,
            "use_ai": use_ai,
            "created_by": created_by
        }
        
        return self._make_request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
    
    def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Get project details
        
        :param project_id: ID of the project
        :return: Project information
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/projects/project/{project_id}"
            f"?client_id={self.client_id}"
            f"&uuid={unique_id}"
        )
        
        return self._make_request(
            "GET",
            url,
            headers={"content-type": "application/json"}
        )
    
    def list_projects(self) -> Dict[str, Any]:
        """
        List all projects for the client
        
        :return: List of projects
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/project_drafts/projects/detailed_list"
            f"?client_id={self.client_id}"
            f"&uuid={unique_id}"
        )
        
        return self._make_request(
            "GET",
            url,
            headers={"content-type": "application/json"}
        )
    
    def update_project_rotations(
        self,
        project_id: str,
        rotations: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Update project rotation configuration
        
        :param project_id: ID of the project
        :param rotations: New rotation configuration
        :return: API response
        """
        unique_id = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/projects/rotations/add"
            f"?project_id={project_id}"
            f"&client_id={self.client_id}"
            f"&uuid={unique_id}"
        )
        
        return self._make_request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(rotations)
        )
    
    # =============================================================================
    # Export Operations
    # =============================================================================
    
    def create_export(
        self,
        project_id: str,
        export_name: str,
        export_description: str,
        export_format: str,
        statuses: List[str]
    ) -> Dict[str, Any]:
        """
        Create an export of project annotations
        
        :param project_id: ID of the project
        :param export_name: Name for the export
        :param export_description: Description of the export
        :param export_format: Format (json, coco_json, csv, png)
        :param statuses: List of annotation statuses to include
        :return: API response with report_id
        """
        payload = {
            "export_name": export_name,
            "export_description": export_description,
            "export_format": export_format,
            "statuses": statuses,
            "export_destination": "local",
            "question_ids": ["all"]
        }
        
        url = (
            f"{self.BASE_URL}/sdk/export/files"
            f"?project_id={project_id}"
            f"&client_id={self.client_id}"
        )
        
        return self._make_request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
    
    def check_export_status(
        self,
        project_id: str,
        report_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Check status of export jobs
        
        :param project_id: ID of the project
        :param report_ids: List of export report IDs to check
        :return: Status information for each export
        """
        uuid_str = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/exports/status"
            f"?project_id={project_id}"
            f"&uuid={uuid_str}"
            f"&client_id={self.client_id}"
        )
        
        payload = {"report_ids": report_ids}
        
        return self._make_request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
    
    def get_export_download_url(
        self,
        project_id: str,
        export_id: str
    ) -> Dict[str, Any]:
        """
        Get download URL for a completed export
        
        :param project_id: ID of the project
        :param export_id: ID of the export (report_id)
        :return: Download URL information
        """
        uuid_str = str(uuid.uuid4())
        url = (
            f"{self.BASE_URL}/exports/download"
            f"?project_id={project_id}"
            f"&uuid={uuid_str}"
            f"&report_id={export_id}"
            f"&client_id={self.client_id}"
        )
        
        return self._make_request("GET", url)

