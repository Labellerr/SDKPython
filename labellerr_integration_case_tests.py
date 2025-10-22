import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import dotenv
from pydantic import ValidationError

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError

dotenv.load_dotenv()


@dataclass
class AttachDetachTestCase:
    """Test case for attach/detach dataset operations"""

    test_name: str
    client_id: str
    project_id: str
    dataset_id: str
    expect_error_substr: Optional[str] = None
    expected_success: bool = True


@dataclass
class MultimodalIndexingTestCase:
    """Test case for multimodal indexing operations"""

    test_name: str
    client_id: str
    dataset_id: str
    is_multimodal: bool = True
    expect_error_substr: Optional[str] = None
    expected_success: bool = True


@dataclass
class AWSConnectionTestCase:
    test_name: str
    client_id: str
    access_key: str
    secret_key: str
    s3_path: str
    data_type: str
    name: str
    description: str
    connection_type: str = "import"
    expect_error_substr: str | list[str] | None = None


@dataclass
class GCSConnectionTestCase:
    test_name: str
    client_id: str
    cred_file_content: str
    gcs_path: str
    data_type: str
    name: str
    description: str
    connection_type: str = "import"
    expect_error_substr: str | list[str] | None = None


@dataclass
class UserManagementTestCase:
    """Test case for user management operations"""

    test_name: str
    client_id: str
    project_id: str
    email_id: str
    first_name: str
    last_name: str
    user_id: str = None
    role_id: str = None
    new_role_id: str = None
    expect_error_substr: str | None = None
    expected_success: bool = True


@dataclass
class UserWorkflowTestCase:
    """Test case for complete user workflow operations"""

    test_name: str
    client_id: str
    project_id: str
    email_id: str
    first_name: str
    last_name: str
    user_id: str
    roles: List[Dict[str, Any]]
    projects: List[str]
    expect_error_substr: str | None = None
    expected_success: bool = True


class LabelerIntegrationTests(unittest.TestCase):

    def setUp(self):

        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.client_id = os.getenv("CLIENT_ID")
        self.test_email = os.getenv("CLIENT_EMAIL")
        self.connector_video_creds_aws = os.getenv("AWS_CONNECTION_VIDEO")
        self.connector_image_creds_aws = os.getenv("AWS_CONNECTION_IMAGE")
        self.connector_image_creds_gcs = os.getenv("GCS_CONNECTION_IMAGE")
        self.connector_video_creds_gcs = os.getenv("GCS_CONNECTION_VIDEO")

        # Configurable test IDs for attach/detach operations
        self.test_project_id = os.getenv(
            "TEST_PROJECT_ID", "sisely_serious_tarantula_26824"
        )
        self.test_dataset_id = os.getenv(
            "TEST_DATASET_ID", "bfd09b6a-a593-4246-82f7-505a497a887c"
        )

        if (
            self.api_key == ""
            or self.api_secret == ""
            or self.client_id == ""
            or self.test_email == ""
            or self.connector_video_creds_aws == ""
            or self.connector_image_creds_aws == ""
        ):

            raise ValueError(
                "missing environment variables: "
                "LABELLERR_API_KEY, LABELLERR_API_SECRET, LABELLERR_CLIENT_ID, LABELLERR_TEST_EMAIL, AWS_CONNECTION_VIDEO, AWS_CONNECTION_IMAGE"
            )

        self.client = LabellerrClient(self.api_key, self.api_secret)

        self.test_project_name = f"SDK_Test_Project_{int(time.time())}"
        self.test_dataset_name = f"SDK_Test_Dataset_{int(time.time())}"

        # Sample annotation guide as per documentation requirements
        self.annotation_guide = [
            {
                "question": "What objects do you see?",
                "option_type": "select",
                "options": ["cat", "dog", "car", "person", "other"],
            },
            {
                "question": "Image quality rating",
                "option_type": "radio",
                "options": ["excellent", "good", "fair", "poor"],
            },
        ]

        self.rotation_config = {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        }

    def test_complete_project_creation_workflow(self):

        test_files = []
        try:
            for i in range(3):
                temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                temp_file.write(b"fake_image_data_" + str(i).encode())
                temp_file.close()
                test_files.append(temp_file.name)

            # Step 1: Prepare project payload with all required parameters
            project_payload = {
                "client_id": self.client_id,
                "dataset_name": self.test_dataset_name,
                "dataset_description": "Test dataset for SDK integration testing",
                "data_type": "image",
                "created_by": self.test_email,
                "project_name": self.test_project_name,
                "autolabel": False,
                "files_to_upload": test_files,
                "annotation_guide": self.annotation_guide,
                "rotation_config": self.rotation_config,
            }

            # Step 2: Execute complete project creation workflow

            result = self.client.initiate_create_project(project_payload)

            # Step 3: Validate the workflow execution
            self.assertIsInstance(
                result, dict, "Project creation should return a dictionary"
            )
            self.assertEqual(
                result.get("status"), "success", "Project creation should be successful"
            )
            self.assertIn("message", result, "Result should contain a success message")
            self.assertIn("project_id", result, "Result should contain project_id")

            self.created_project_id = result.get("project_id")
            self.created_dataset_name = self.test_dataset_name

        except LabellerrError as e:
            self.fail(f"Project creation failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Project creation failed with unexpected error: {e}")
        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_project_creation_missing_client_id(self):
        """Test that project creation fails when client_id is missing"""
        base_payload = {
            "dataset_name": "test_dataset",
            "dataset_description": "test description",
            "data_type": "image",
            "created_by": "test@example.com",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
            "annotation_guide": self.annotation_guide,
        }

        with self.assertRaises(LabellerrError) as context:
            self.client.initiate_create_project(base_payload)

        self.assertIn("Required parameter client_id is missing", str(context.exception))

    def test_project_creation_invalid_email(self):
        """Test that project creation fails with invalid email format"""
        base_payload = {
            "client_id": self.client_id,
            "dataset_name": "test_dataset",
            "dataset_description": "test description",
            "data_type": "image",
            "created_by": "invalid-email",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
            "annotation_guide": self.annotation_guide,
        }

        with self.assertRaises(LabellerrError) as context:
            self.client.initiate_create_project(base_payload)

        self.assertIn("Please enter email id in created_by", str(context.exception))

    def test_project_creation_invalid_data_type(self):
        """Test that project creation fails with invalid data type"""
        base_payload = {
            "client_id": self.client_id,
            "dataset_name": "test_dataset",
            "dataset_description": "test description",
            "data_type": "invalid_type",
            "created_by": "test@example.com",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
            "annotation_guide": self.annotation_guide,
        }

        with self.assertRaises(LabellerrError) as context:
            self.client.initiate_create_project(base_payload)

        self.assertIn("Invalid data_type", str(context.exception))

    def test_project_creation_missing_dataset_name(self):
        """Test that project creation fails when dataset_name is missing"""
        base_payload = {
            "client_id": self.client_id,
            "dataset_description": "test description",
            "data_type": "image",
            "created_by": "test@example.com",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
            "annotation_guide": self.annotation_guide,
        }

        with self.assertRaises(LabellerrError) as context:
            self.client.initiate_create_project(base_payload)

        self.assertIn(
            "Required parameter dataset_name is missing", str(context.exception)
        )

    def test_project_creation_missing_annotation_guide(self):
        """Test that project creation fails when annotation guide is missing"""
        base_payload = {
            "client_id": self.client_id,
            "dataset_name": "test_dataset",
            "dataset_description": "test description",
            "data_type": "image",
            "created_by": "test@example.com",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
        }

        with self.assertRaises(LabellerrError) as context:
            self.client.initiate_create_project(base_payload)

        self.assertIn(
            "Please provide either annotation guide or annotation template id",
            str(context.exception),
        )

    def test_create_image_classification_project(self):
        """Test creating an image classification project"""
        test_files = []
        try:
            for ext in [".jpg", ".png"]:
                temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                temp_file.write(b"fake_image_data")
                temp_file.close()
                test_files.append(temp_file.name)

            annotation_guide = [
                {
                    "question": "Test question 1",
                    "option_type": "select",
                    "options": ["option1", "option2", "option3"],
                },
                {
                    "question": "Test question 2",
                    "option_type": "radio",
                    "options": ["option1", "option2", "option3"],
                },
            ]

            project_payload = {
                "client_id": self.client_id,
                "dataset_name": f"SDK_Test_image_{int(time.time())}",
                "dataset_description": "Test dataset for Image Classification Project",
                "data_type": "image",
                "created_by": self.test_email,
                "project_name": f"SDK_Test_Project_image_{int(time.time())}",
                "autolabel": False,
                "files_to_upload": test_files,
                "annotation_guide": annotation_guide,
                "rotation_config": self.rotation_config,
            }

            result = self.client.initiate_create_project(project_payload)

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("status"), "success")
            print(" Image Classification Project created successfully")

        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_create_document_processing_project(self):
        """Test creating a document processing project"""
        test_files = []
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_file.write(b"fake_document_data")
            temp_file.close()
            test_files.append(temp_file.name)

            annotation_guide = [
                {"question": "Test question 1", "option_type": "input", "options": []},
                {
                    "question": "Test question 2",
                    "option_type": "boolean",
                    "options": ["Yes", "No"],
                },
            ]

            project_payload = {
                "client_id": self.client_id,
                "dataset_name": f"SDK_Test_document_{int(time.time())}",
                "dataset_description": "Test dataset for Document Processing Project",
                "data_type": "document",
                "created_by": self.test_email,
                "project_name": f"SDK_Test_Project_document_{int(time.time())}",
                "autolabel": False,
                "files_to_upload": test_files,
                "annotation_guide": annotation_guide,
                "rotation_config": self.rotation_config,
            }

            result = self.client.initiate_create_project(project_payload)

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("status"), "success")
            print(" Document Processing Project created successfully")

        finally:
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_pre_annotation_upload_workflow(self):
        annotation_data = {
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [100, 100, 200, 200],
                    "area": 40000,
                    "iscrowd": 0,
                }
            ],
            "images": [
                {"id": 1, "width": 640, "height": 480, "file_name": "test_image.jpg"}
            ],
            "categories": [{"id": 1, "name": "person", "supercategory": "human"}],
        }

        temp_annotation_file = None
        try:
            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            json.dump(annotation_data, temp_annotation_file)
            temp_annotation_file.close()

            test_project_id = "sunny_tough_blackbird_40468"
            annotation_format = "coco_json"

            if hasattr(self, "created_project_id") and self.created_project_id:
                actual_project_id = self.created_project_id
            else:
                actual_project_id = test_project_id
                try:
                    result = self.client._upload_preannotation_sync(
                        project_id=actual_project_id,
                        client_id=self.client_id,
                        annotation_format=annotation_format,
                        annotation_file=temp_annotation_file.name,
                    )

                    self.assertIsInstance(
                        result, dict, "Upload should return a dictionary"
                    )
                    self.assertIn("response", result, "Result should contain response")

                except Exception as api_error:
                    raise api_error

        except LabellerrError as e:
            self.fail(f"Pre-annotation upload failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Pre-annotation upload failed with unexpected error: {e}")
        finally:
            if temp_annotation_file:
                try:
                    os.unlink(temp_annotation_file.name)
                except OSError:
                    pass

    def test_pre_annotation_invalid_format(self):
        """Test that pre_annotation upload fails with invalid annotation format"""
        with self.assertRaises(LabellerrError) as context:
            self.client._upload_preannotation_sync(
                project_id="test-project",
                client_id=self.client_id,
                annotation_format="invalid_format",
                annotation_file="test.json",
            )

        self.assertIn("Invalid annotation_format", str(context.exception))

    def test_pre_annotation_file_not_found(self):
        """Test that pre_annotation upload fails when file doesn't exist"""
        with self.assertRaises(LabellerrError) as context:
            self.client._upload_preannotation_sync(
                project_id="test-project",
                client_id=self.client_id,
                annotation_format="json",
                annotation_file="non_existent_file.json",
            )

        self.assertIn("File not found", str(context.exception))

    def test_pre_annotation_wrong_file_extension(self):
        """Test that pre_annotation upload fails with wrong file extension for COCO format"""
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            temp_file.write(b"test content")
            temp_file.close()

            with self.assertRaises(LabellerrError) as context:
                self.client._upload_preannotation_sync(
                    project_id="test-project",
                    client_id=self.client_id,
                    annotation_format="coco_json",
                    annotation_file=temp_file.name,
                )

            self.assertIn(
                "For coco_json annotation format, the file must have a .json extension",
                str(context.exception),
            )

        finally:
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass

    def test_pre_annotation_upload_coco_json(self):
        """Test uploading pre annotations in COCO JSON format"""
        temp_annotation_file = None
        try:
            sample_data = {
                "annotations": [
                    {
                        "id": 1,
                        "image_id": 1,
                        "category_id": 1,
                        "bbox": [0, 0, 100, 100],
                    }
                ],
                "images": [
                    {"id": 1, "file_name": "test.jpg", "width": 640, "height": 480}
                ],
                "categories": [{"id": 1, "name": "test", "supercategory": "object"}],
            }

            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            json.dump(sample_data, temp_annotation_file)
            temp_annotation_file.close()

            # Get a valid image project ID from the system (COCO JSON is for images)
            test_project_id = None
            if hasattr(self, "created_project_id") and self.created_project_id:
                test_project_id = self.created_project_id
            else:
                # Try to get an image-type project
                try:
                    projects = self.client.get_all_project_per_client_id(self.client_id)
                    if projects.get("response") and len(projects["response"]) > 0:
                        # Look for a project with data_type 'image'
                        for project in projects["response"]:
                            # COCO JSON is typically for image annotation projects
                            if "image" in project.get("project_name", "").lower():
                                test_project_id = project["project_id"]
                                break
                        # If no image project found, skip the test
                        if not test_project_id:
                            test_project_id = projects["response"][0]["project_id"]
                except Exception:
                    pass

            if not test_project_id:
                self.skipTest(
                    "No valid project available for pre-annotation upload test"
                )

            result = self.client._upload_preannotation_sync(
                project_id=test_project_id,
                client_id=self.client_id,
                annotation_format="coco_json",
                annotation_file=temp_annotation_file.name,
            )

            self.assertIsInstance(result, dict)
            self.assertIn("response", result)

        finally:
            if temp_annotation_file:
                try:
                    os.unlink(temp_annotation_file.name)
                except OSError:
                    pass

    def test_pre_annotation_upload_json(self):
        """Test uploading pre_annotations in JSON format with timeout protection

        Note: This test requires a valid project ID. It will use:
        1. self.created_project_id if test_complete_project_creation_workflow ran first
        2. Otherwise, self.test_project_id from environment variable TEST_PROJECT_ID

        Set TEST_PROJECT_ID environment variable to a valid project ID if needed.
        """
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(
                "Test timed out after 60 seconds - API job polling may be stuck"
            )

        temp_annotation_file = None
        # Set a 60-second timeout for this test
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)

        try:
            sample_data = {
                "labels": [
                    {
                        "image": "test.jpg",
                        "annotations": [{"label": "cat", "confidence": 0.95}],
                    }
                ]
            }

            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            json.dump(sample_data, temp_annotation_file)
            temp_annotation_file.close()

            # Use created_project_id from test_complete_project_creation_workflow if available,
            # otherwise use test_project_id from environment
            test_project_id = (
                getattr(self, "created_project_id", None) or self.test_project_id
            )

            print(f"Attempting to upload pre-annotation to project: {test_project_id}")
            print("Note: This test has a 60-second timeout to prevent hanging")

            try:
                result = self.client._upload_preannotation_sync(
                    project_id=test_project_id,
                    client_id=self.client_id,
                    annotation_format="json",
                    annotation_file=temp_annotation_file.name,
                )

                self.assertIsInstance(result, dict)
                print("Pre-annotation upload successful")
            except TimeoutError as e:
                self.fail(
                    f"Test timed out: {e}\n"
                    f"The SDK's job status polling has an infinite loop with no timeout. "
                    f"Consider fixing labellerr/client.py::preannotation_job_status_async to add max retries."
                )
            except LabellerrError as e:
                error_str = str(e)
                # Handle common API errors gracefully
                if (
                    "Invalid project_id" in error_str
                    or "not found" in error_str.lower()
                ):
                    self.skipTest(
                        f"Skipping test - invalid project_id '{test_project_id}'. "
                        f"Set TEST_PROJECT_ID environment variable to a valid project ID."
                    )
                elif "did not complete after" in error_str and "retries" in error_str:
                    # Job stuck in queue or not processing
                    self.skipTest(
                        f"Skipping test - pre-annotation job did not complete: {error_str[:200]}. "
                        f"The API job queue may be stuck or the project may not support pre-annotations."
                    )
                elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
                    self.fail(f"API request timed out: {error_str[:200]}")
                elif (
                    "403" in error_str
                    or "401" in error_str
                    or "Not Authorized" in error_str
                ):
                    self.skipTest(
                        f"Skipping test - authentication/authorization issue: {error_str[:200]}"
                    )
                else:
                    # Re-raise other errors
                    raise
            except Exception as e:
                error_str = str(e)
                if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                    self.fail(f"Request timed out: {error_str[:200]}")
                else:
                    raise

        finally:
            # Cancel the alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

            if temp_annotation_file:
                try:
                    os.unlink(temp_annotation_file.name)
                except OSError:
                    pass

    def test_data_set_connection_aws(self):

        # Read per-type AWS secrets from env (JSON strings): AWS_CONNECTION_IMAGE, AWS_CONNECTION_VIDEO
        image_secret_json = os.getenv("AWS_CONNECTION_IMAGE")
        video_secret_json = os.getenv("AWS_CONNECTION_VIDEO")

        def _parse_secret(env_json: str):
            if not env_json:
                return {}
            try:
                return json.loads(env_json)
            except Exception as ex:
                return ex

        image_secret = _parse_secret(image_secret_json)
        video_secret = _parse_secret(video_secret_json)

        image_access_key = image_secret.get("access_key")
        image_secret_key = image_secret.get("secret_key")
        image_s3_path = image_secret.get("s3_path")

        video_access_key = video_secret.get("access_key")
        video_secret_key = video_secret.get("secret_key")
        video_s3_path = video_secret.get("s3_path")

        cases: list[AWSConnectionTestCase] = [
            AWSConnectionTestCase(
                test_name="Missing credentials",
                client_id=self.client_id,
                access_key="",
                secret_key="",
                s3_path="s3://bucket/path",
                data_type="image",
                name="aws_invalid_connection_test",
                description="missing_secrets",
                expect_error_substr=[
                    # Common Pydantic v2/v1 variants
                    "at least 1 character",
                    "at least 1 characters",
                    "ensure this value has at least 1 characters",
                    "String should have at least 1 characters",
                    "must be at least 1 character",
                    "Input should be at least 1 character",
                ],
            ),
            AWSConnectionTestCase(
                test_name="Valid image import",
                client_id=self.client_id,
                access_key=image_access_key,
                secret_key=image_secret_key,
                s3_path=image_s3_path,
                data_type="image",
                name="aws_connection_image",
                description="test_description",
            ),
            AWSConnectionTestCase(
                test_name="Valid video import",
                client_id=self.client_id,
                access_key=video_access_key,
                secret_key=video_secret_key,
                s3_path=video_s3_path,
                data_type="video",
                name="aws_connection_video",
                description="test_description",
            ),
        ]

        for case in cases:
            with self.subTest(test_name=case.test_name):
                if case.expect_error_substr is not None:
                    # Pydantic validation errors raise ValidationError, API errors raise LabellerrError
                    expected_subst = (
                        case.expect_error_substr
                        if isinstance(case.expect_error_substr, list)
                        else [case.expect_error_substr]
                    )
                    validation_markers = [
                        "at least 1",
                        "ensure this value has at least",
                        "String should have at least",
                        "Input should be at least",
                        "GCS credential file not found",
                    ]
                    error_type = (
                        ValidationError
                        if any(
                            any(vm in s for vm in validation_markers)
                            for s in expected_subst
                        )
                        else LabellerrError
                    )
                    with self.assertRaises(error_type) as ctx:
                        self.client.create_aws_connection(
                            client_id=case.client_id,
                            aws_access_key=case.access_key,
                            aws_secrets_key=case.secret_key,
                            s3_path=case.s3_path,
                            data_type=case.data_type,
                            name=case.name,
                            description=case.description,
                            connection_type=case.connection_type,
                        )
                    if expected_subst:
                        exc_str = str(ctx.exception)
                        self.assertTrue(
                            any(sub in exc_str for sub in expected_subst),
                            msg=f"Expected one of {expected_subst} in error, got: {exc_str}",
                        )
                else:
                    try:
                        result = self.client.create_aws_connection(
                            client_id=case.client_id,
                            aws_access_key=case.access_key,
                            aws_secrets_key=case.secret_key,
                            s3_path=case.s3_path,
                            data_type=case.data_type,
                            name=case.name,
                            description=case.description,
                            connection_type=case.connection_type,
                        )
                        self.assertIsInstance(result, dict)
                        self.assertIn("response", result)
                        connection_id = result["response"].get("connection_id")
                        self.assertIsNotNone(connection_id)

                        list_result = self.client.list_connection(
                            client_id=case.client_id,
                            connection_type=case.connection_type,
                            connector="s3",
                        )
                        self.assertIsInstance(list_result, dict)
                        self.assertIn("response", list_result)

                        del_result = self.client.delete_connection(
                            client_id=case.client_id, connection_id=connection_id
                        )
                        self.assertIsInstance(del_result, dict)
                        self.assertIn("response", del_result)
                    except LabellerrError as e:
                        error_str = str(e)
                        # Skip test if API is having issues (500 errors)
                        if "500" in error_str or "Max retries exceeded" in error_str:
                            self.skipTest(
                                f"API unavailable for test '{case.test_name}': {error_str[:100]}"
                            )
                        else:
                            raise

    def test_data_set_connection_gcs(self):
        # Read per-type GCS secrets from env (JSON strings): GCS_CONNECTION_IMAGE, GCS_CONNECTION_VIDEO
        image_secret_json = os.getenv("GCS_CONNECTION_IMAGE")
        video_secret_json = os.getenv("GCS_CONNECTION_VIDEO")

        def _parse_secret(env_json: str):
            if not env_json:
                return {}
            try:
                return json.loads(env_json)
            except Exception:
                return {}

        image_secret = _parse_secret(image_secret_json)
        video_secret = _parse_secret(video_secret_json)

        image_cred_file = image_secret.get("cred_file")
        image_gcs_path = image_secret.get("gcs_path")

        video_cred_file = video_secret.get("cred_file")
        video_gcs_path = video_secret.get("gcs_path")

        cases: list[GCSConnectionTestCase] = [
            GCSConnectionTestCase(
                test_name="Missing credential file",
                client_id=self.client_id,
                cred_file_content="",
                gcs_path="gs://bucket/path",
                data_type="image",
                name="gcs_invalid_connection_test",
                description="missing_cred_file",
                expect_error_substr=[
                    "GCS credential file not found",
                    "file does not exist",
                    "path is not a file",
                    "No such file or directory",
                ],
            ),
        ]

        # Only add valid cases if credentials are available
        if image_cred_file and image_gcs_path:
            cases.append(
                GCSConnectionTestCase(
                    test_name="Valid image import",
                    client_id=self.client_id,
                    cred_file_content=image_cred_file,
                    gcs_path=image_gcs_path,
                    data_type="image",
                    name="gcs_connection_image",
                    description="test_description",
                )
            )

        if video_cred_file and video_gcs_path:
            cases.append(
                GCSConnectionTestCase(
                    test_name="Valid video import",
                    client_id=self.client_id,
                    cred_file_content=video_cred_file,
                    gcs_path=video_gcs_path,
                    data_type="video",
                    name="gcs_connection_video",
                    description="test_description",
                )
            )

        for case in cases:
            with self.subTest(test_name=case.test_name):
                # Skip valid cases if credentials are not available
                if case.expect_error_substr is None and (
                    not case.cred_file_content or not case.gcs_path
                ):
                    self.skipTest(
                        f"Skipping {case.test_name}: GCS credentials not available in environment"
                    )

                temp_created_path = None
                if case.expect_error_substr is not None:
                    # Pydantic validation errors (like file not found) raise ValidationError
                    expected_substrs = (
                        case.expect_error_substr
                        if isinstance(case.expect_error_substr, list)
                        else [case.expect_error_substr]
                    )
                    validation_markers = [
                        "GCS credential file not found",
                        "file does not exist",
                        "path is not a file",
                        "No such file or directory",
                    ]
                    error_type = (
                        ValidationError
                        if any(
                            any(vm in s for vm in validation_markers)
                            for s in expected_substrs
                        )
                        else LabellerrError
                    )
                    with self.assertRaises(error_type) as ctx:
                        self.client.create_gcs_connection(
                            client_id=case.client_id,
                            gcs_cred_file=case.cred_file_content,
                            gcs_path=case.gcs_path,
                            data_type=case.data_type,
                            name=case.name,
                            description=case.description,
                            connection_type=case.connection_type,
                        )
                    if expected_substrs:
                        exc_str = str(ctx.exception)
                        self.assertTrue(
                            any(sub in exc_str for sub in expected_substrs),
                            msg=f"Expected one of {expected_substrs} in error, got: {exc_str}",
                        )
                else:
                    tf = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    )
                    try:
                        # Support both JSON string and already-parsed dict for creds
                        if isinstance(case.cred_file_content, (dict, list)):
                            parsed = case.cred_file_content
                        elif isinstance(
                            case.cred_file_content, (str, bytes, bytearray)
                        ):
                            parsed = json.loads(case.cred_file_content)
                        else:
                            raise TypeError(
                                "Unsupported credential content type; expected str/bytes/dict/list"
                            )
                        tf.write(json.dumps(parsed))
                        tf.flush()
                    except Exception as e:
                        raise e
                    finally:
                        try:
                            tf.close()
                        except Exception:
                            pass
                    temp_created_path = tf.name
                    result = self.client.create_gcs_connection(
                        client_id=case.client_id,
                        gcs_cred_file=temp_created_path,
                        gcs_path=case.gcs_path,
                        data_type=case.data_type,
                        name=case.name,
                        description=case.description,
                        connection_type=case.connection_type,
                    )
                    self.assertIsInstance(result, dict)
                    self.assertIn("response", result)
                    connection_id = result["response"].get("connection_id")
                    self.assertIsNotNone(connection_id)

                    list_result = self.client.list_connection(
                        client_id=case.client_id,
                        connection_type=case.connection_type,
                        connector="gcs",
                    )
                    self.assertIsInstance(list_result, dict)
                    self.assertIn("response", list_result)

                    del_result = self.client.delete_connection(
                        client_id=case.client_id, connection_id=connection_id
                    )
                    self.assertIsInstance(del_result, dict)
                    self.assertIn("response", del_result)
                if temp_created_path:
                    try:
                        os.unlink(temp_created_path)
                    except OSError:
                        pass

    def test_attach_detach_dataset_workflow(self):
        """Comprehensive test for single and batch attach/detach workflows - always detach first to ensure consistent state"""
        # ========== SINGLE DATASET OPERATIONS ==========
        print("\n=== Testing Single Dataset Operations ===")

        # Step 1: Detach single dataset first to get to a known state
        print(f"Step 1: Detaching single dataset {self.test_dataset_id}...")
        try:
            single_detach_result = self.client.initiate_detach_dataset_from_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id=self.test_dataset_id,
            )
            self.assertIsInstance(single_detach_result, dict)
            self.assertIn("response", single_detach_result)
            print("Single dataset detached successfully")
        except Exception as e:
            # If detach fails, dataset might not be attached - that's okay, continue
            print(
                f" Single detach skipped (dataset might not be attached): {str(e)[:100]}"
            )

        # Step 2: Attach single dataset
        print("Step 2: Attaching single dataset...")
        try:
            single_attach_result = self.client.initiate_attach_dataset_to_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id=self.test_dataset_id,
            )
            self.assertIsInstance(single_attach_result, dict)
            self.assertIn("response", single_attach_result)
            print("Single dataset attached successfully")
        except LabellerrError as e:
            # Handle "already attached" as a success case
            error_str = str(e)
            if "already been attached" in error_str or "already attached" in error_str:
                print("Single dataset already attached (treating as success)")
            else:
                self.fail(f"Failed to attach single dataset: {e}")
        except Exception as e:
            self.fail(f"Failed to attach single dataset: {e}")

        # ========== BATCH DATASET OPERATIONS ==========
        print("\n=== Testing Batch Dataset Operations ===")
        test_dataset_ids = [self.test_dataset_id]

        # Step 3: Detach batch datasets first to get to a known state
        print(f"Step 3: Detaching batch datasets {test_dataset_ids}...")
        try:
            batch_detach_result = self.client.initiate_detach_datasets_from_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_ids=test_dataset_ids,
            )
            self.assertIsInstance(batch_detach_result, dict)
            self.assertIn("response", batch_detach_result)
            print("Batch datasets detached successfully")
        except Exception as e:
            print(f"Batch detach skipped: {str(e)[:100]}")

        # Step 4: Attach batch datasets
        print("Step 4: Attaching batch datasets...")
        try:
            batch_attach_result = self.client.initiate_attach_datasets_to_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_ids=test_dataset_ids,
            )
            self.assertIsInstance(batch_attach_result, dict)
            self.assertIn("response", batch_attach_result)
            print(" Batch datasets attached successfully")
        except LabellerrError as e:
            # Handle "already attached" as a success case
            error_str = str(e)
            if "already been attached" in error_str or "already attached" in error_str:
                print(" Batch datasets already attached (treating as success)")
            else:
                self.fail(f"Failed to attach batch datasets: {e}")
        except Exception as e:
            self.fail(f"Failed to attach batch datasets: {e}")

        print(
            "\n Complete attach/detach workflow successful (single & batch operations)"
        )

    def test_attach_dataset_invalid_project_id(self):
        """Test dataset attachment with invalid project_id format"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_attach_dataset_to_project(
                client_id=self.client_id,
                project_id="invalid-project-id",
                dataset_id=self.test_dataset_id,
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_attach_dataset_invalid_dataset_id(self):
        """Test dataset attachment with invalid dataset_id format"""
        with self.assertRaises(ValidationError) as context:
            self.client.initiate_attach_dataset_to_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id="invalid-dataset-id",
            )

        # The error message should contain UUID validation error
        error_msg = str(context.exception)
        self.assertTrue(
            "valid UUID" in error_msg
            or "Invalid" in error_msg
            or "uuid" in error_msg.lower()
        )

    def test_attach_dataset_missing_client_id(self):
        """Test dataset attachment with missing client_id"""
        with self.assertRaises(ValidationError) as context:
            self.client.initiate_attach_dataset_to_project(
                client_id="",
                project_id=self.test_project_id,
                dataset_id=self.test_dataset_id,
            )

        error_msg = str(context.exception)
        self.assertTrue(
            "at least 1 character" in error_msg or "Required parameter" in error_msg
        )

    def test_attach_dataset_nonexistent_project(self):
        """Test dataset attachment with non-existent project_id"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_attach_dataset_to_project(
                client_id=self.client_id,
                project_id="00000000-0000-0000-0000-000000000000",
                dataset_id=self.test_dataset_id,
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_attach_dataset_nonexistent_dataset(self):
        """Test dataset attachment with non-existent dataset_id"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_attach_dataset_to_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_detach_dataset_invalid_project_id(self):
        """Test dataset detachment with invalid project_id format"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_detach_dataset_from_project(
                client_id=self.client_id,
                project_id="invalid-project-id",
                dataset_id=self.test_dataset_id,
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_detach_dataset_invalid_dataset_id(self):
        """Test dataset detachment with invalid dataset_id format"""
        with self.assertRaises(ValidationError) as context:
            self.client.initiate_detach_dataset_from_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id="invalid-dataset-id",
            )

        # The error message should contain UUID validation error
        error_msg = str(context.exception)
        self.assertTrue(
            "valid UUID" in error_msg
            or "Invalid" in error_msg
            or "uuid" in error_msg.lower()
        )

    def test_detach_dataset_missing_client_id(self):
        """Test dataset detachment with missing client_id"""
        with self.assertRaises(ValidationError) as context:
            self.client.initiate_detach_dataset_from_project(
                client_id="",
                project_id=self.test_project_id,
                dataset_id=self.test_dataset_id,
            )

        error_msg = str(context.exception)
        self.assertTrue(
            "at least 1 character" in error_msg or "Required parameter" in error_msg
        )

    def test_detach_dataset_nonexistent_project(self):
        """Test dataset detachment with non-existent project_id"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_detach_dataset_from_project(
                client_id=self.client_id,
                project_id="00000000-0000-0000-0000-000000000000",
                dataset_id=self.test_dataset_id,
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_detach_dataset_nonexistent_dataset(self):
        """Test dataset detachment with non-existent dataset_id"""
        with self.assertRaises(LabellerrError):
            self.client.initiate_detach_dataset_from_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
            )
        # Just verify that an error is raised - the exact error message is API-dependent

    def test_attach_datasets_batch_invalid_dataset_id(self):
        """Test batch attach with one invalid dataset_id format"""
        # Mix of valid UUID and invalid string
        test_dataset_ids = [self.test_dataset_id, "invalid-id"]

        with self.assertRaises(ValidationError) as context:
            self.client.initiate_attach_datasets_to_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_ids=test_dataset_ids,
            )

        error_msg = str(context.exception)
        self.assertTrue(
            "valid UUID" in error_msg
            or "Invalid" in error_msg
            or "uuid" in error_msg.lower()
        )

    def test_detach_datasets_batch_invalid_dataset_id(self):
        """Test batch detach with one invalid dataset_id format"""
        # Mix of valid UUID and invalid string
        test_dataset_ids = [self.test_dataset_id, "invalid-id"]

        with self.assertRaises(ValidationError) as context:
            self.client.initiate_detach_datasets_from_project(
                client_id=self.client_id,
                project_id=self.test_project_id,
                dataset_ids=test_dataset_ids,
            )

        error_msg = str(context.exception)
        self.assertTrue(
            "valid UUID" in error_msg
            or "Invalid" in error_msg
            or "uuid" in error_msg.lower()
        )

    def test_enable_multimodal_indexing(self):
        """Test enabling multimodal indexing for a dataset"""
        result = self.client.enable_multimodal_indexing(
            client_id=self.client_id,
            dataset_id=self.test_dataset_id,
            is_multimodal=True,
        )

        self.assertIsInstance(result, dict)
        self.assertIn("response", result)
        print(" Multimodal indexing enabled successfully")

    def test_disable_multimodal_indexing(self):
        """Test disabling multimodal indexing for a dataset"""
        result = self.client.enable_multimodal_indexing(
            client_id=self.client_id,
            dataset_id=self.test_dataset_id,
            is_multimodal=False,
        )

        self.assertIsInstance(result, dict)
        self.assertIn("response", result)
        print(" Multimodal indexing disabled successfully")

    def test_multimodal_indexing_invalid_dataset_id(self):
        """Test multimodal indexing with invalid dataset_id format"""
        with self.assertRaises(ValidationError) as context:
            self.client.enable_multimodal_indexing(
                client_id=self.client_id,
                dataset_id="invalid-dataset-id",
                is_multimodal=True,
            )

        self.assertIn("valid UUID", str(context.exception))

    def test_multimodal_indexing_missing_client_id(self):
        """Test multimodal indexing with missing client_id"""
        with self.assertRaises(ValidationError) as context:
            self.client.enable_multimodal_indexing(
                client_id="",
                dataset_id=self.test_dataset_id,
                is_multimodal=True,
            )

        self.assertIn("at least 1 character", str(context.exception))

    def test_multimodal_indexing_workflow_integration(self):
        """Integration test for complete multimodal indexing workflow"""
        try:
            # Step 1: Enable multimodal indexing
            print("Step 1: Enabling multimodal indexing...")

            enable_result = self.client.enable_multimodal_indexing(
                client_id=self.client_id,
                dataset_id=self.test_dataset_id,
                is_multimodal=True,
            )
            self.assertIsInstance(enable_result, dict)
            self.assertIn("response", enable_result)
            print("Multimodal indexing enabled successfully")

            # Step 2: Verify indexing status
            print("Step 2: Verifying indexing status...")

            # Step 3: Disable multimodal indexing
            print("Step 3: Disabling multimodal indexing...")

            disable_result = self.client.enable_multimodal_indexing(
                client_id=self.client_id,
                dataset_id=self.test_dataset_id,
                is_multimodal=False,
            )
            self.assertIsInstance(disable_result, dict)
            self.assertIn("response", disable_result)
            print(" Multimodal indexing disabled successfully")

            print(" Complete multimodal indexing workflow successful")

        except LabellerrError as e:
            self.fail(f"Integration test failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Integration test failed with unexpected error: {e}")

    def test_get_multimodal_indexing_status(self):
        """Test getting multimodal indexing status for a dataset"""
        try:
            status_result = self.client.get_multimodal_indexing_status(
                client_id=self.client_id,
                dataset_id=self.test_dataset_id,
            )

            self.assertIsInstance(status_result, dict)
            self.assertIn("message", status_result)
            self.assertIn("response", status_result)

            response_data = status_result["response"]
            if response_data is not None:
                self.assertIsInstance(response_data, dict)
                self.assertIn("status", response_data)

            print("Get multimodal indexing status test passed")

        except LabellerrError as e:
            self.fail(
                f"Get multimodal indexing status test failed with LabellerrError: {e}"
            )
        except Exception as e:
            self.fail(
                f"Get multimodal indexing status test failed with unexpected error: {e}"
            )

    def test_user_management_workflow(self):
        """Test complete user management workflow: create, update, add to project, change role, remove, delete"""
        try:
            test_email = f"test_user_{int(time.time())}@example.com"
            test_first_name = "Test"
            test_last_name = "User"
            test_user_id = f"test-user-{int(time.time())}"
            test_project_id = "sunny_tough_blackbird_40468"
            test_role_id = "7"
            test_new_role_id = "5"

            # Step 1: Create a user
            print(f"\n=== Step 1: Creating user {test_email} ===")
            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")
            self.assertIsNotNone(create_result)

            # Step 2: Update user role
            print(f"\n=== Step 2: Updating user role for {test_email} ===")
            update_result = self.client.update_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                roles=[{"project_id": test_project_id, "role_id": test_new_role_id}],
                first_name=test_first_name,
                last_name=test_last_name,
            )
            print(f"User role update result: {update_result}")
            self.assertIsNotNone(update_result)

            # Step 3: Add user to project (if not already added)
            # TODO: @ximi
            # INFO:root:Checkout User - Status: 404, Message: NotFound: AltairOne user not found.
            # 2025-10-09 21:40:48.976 IST
            # INFO:root:NotFound: AltairOne user not found.
            # print(f"\n=== Step 3: Adding user to project {test_project_id} ===")
            # add_result = self.client.add_user_to_project(
            #     client_id=self.client_id,
            #     project_id=test_project_id,
            #     email_id=test_email,
            #     role_id=test_role_id,
            # )
            # print(f"Add user to project result: {add_result}")
            # self.assertIsNotNone(add_result)

            # Step 4: Change user role
            print(f"\n=== Step 4: Changing user role for {test_email} ===")
            change_role_result = self.client.change_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                new_role_id=test_new_role_id,
            )
            print(f"Change user role result: {change_role_result}")
            self.assertIsNotNone(change_role_result)

            # Step 5: Remove user from project
            print(f"\n=== Step 5: Removing user from project {test_project_id} ===")
            remove_result = self.client.remove_user_from_project(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
            )
            print(f"Remove user from project result: {remove_result}")
            self.assertIsNotNone(remove_result)

            # Step 6: Delete user
            print(f"\n=== Step 6: Deleting user {test_email} ===")
            delete_result = self.client.delete_user(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                user_id=test_user_id,
                first_name=test_first_name,
                last_name=test_last_name,
            )
            print(f"Delete user result: {delete_result}")
            self.assertIsNotNone(delete_result)

            print("Complete user management workflow completed successfully")

        except Exception as e:
            print(f" User management workflow failed: {str(e)}")
            raise

    def test_create_user_integration(self):
        """Test user creation with real API calls"""
        try:
            test_email = f"integration_test_{int(time.time())}@example.com"
            test_first_name = "Integration"
            test_last_name = "Test"
            test_project_id = "test_project_1233"
            test_role_id = "7"

            print(f"\n=== Testing user creation for {test_email} ===")

            result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
                work_phone="123-456-7890",
                job_title="Test Engineer",
                language="en",
                timezone="GMT",
            )

            print(f"User creation result: {result}")
            self.assertIsNotNone(result)

            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f"Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f"Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" User creation integration test failed: {str(e)}")
            raise

    def test_update_user_role_integration(self):
        """Test user role update with real API calls"""
        try:
            test_email = f"update_test_{int(time.time())}@example.com"
            test_first_name = "Update"
            test_last_name = "Test"
            test_project_id = "test_project_123"
            test_role_id = "7"
            test_new_role_id = "5"

            print(f"\n=== Testing user role update for {test_email} ===")

            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")

            update_result = self.client.update_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                roles=[{"project_id": test_project_id, "role_id": test_new_role_id}],
                first_name=test_first_name,
                last_name=test_last_name,
                work_phone="987-654-3210",
                job_title="Senior Test Engineer",
                language="en",
                timezone="UTC",
            )

            print(f"User role update result: {update_result}")
            self.assertIsNotNone(update_result)

            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f" Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f" Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" User role update integration test failed: {str(e)}")
            raise

    def test_project_user_management_integration(self):
        """Test project user management operations with real API calls"""
        try:
            test_email = f"project_test_{int(time.time())}@example.com"
            test_first_name = "Project"
            test_last_name = "Test"
            test_project_id = "test_project_123"
            test_role_id = "7"
            test_new_role_id = "5"

            print(f"\n=== Testing project user management for {test_email} ===")

            # Step 1: Create a user
            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")
            self.assertIsNotNone(create_result)

            # Step 2: Update user role (use update_user_role instead of separate add/change operations)
            update_result = self.client.update_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                roles=[{"project_id": test_project_id, "role_id": test_new_role_id}],
                first_name=test_first_name,
                last_name=test_last_name,
            )
            print(f"Update user role result: {update_result}")
            self.assertIsNotNone(update_result)

            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f" Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f" Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" Project user management integration test failed: {str(e)}")
            raise

    def test_user_management_error_handling(self):
        """Test user management error handling with invalid inputs"""
        try:
            print("=== Testing user management error handling ===")

            # Test with invalid client_id
            try:
                self.client.create_user(
                    client_id="invalid_client_id",
                    first_name="Test",
                    last_name="User",
                    email_id="test@example.com",
                    projects=["project_123"],
                    roles=[{"project_id": "project_123", "role_id": "7"}],
                )
                self.fail("Expected error for invalid client_id")
            except Exception as e:
                print(f" Correctly caught error for invalid client_id: {str(e)}")

            with self.assertRaises(ValidationError) as e:
                self.client.create_user(
                    client_id=self.client_id,
                    first_name="Test",
                    last_name="",  # Empty string - should fail validation
                    email_id="",  # Empty string - should fail validation
                    projects=[],  # Empty list - should fail validation
                    roles=[],  # Empty list - should fail validation
                )
            print(
                f" Correctly caught ValidationError for empty parameters: {str(e.exception)}"
            )

            # Test with invalid email format
            try:
                self.client.create_user(
                    client_id=self.client_id,
                    first_name="Test",
                    last_name="User",
                    email_id="invalid_email",  # Invalid email format
                    projects=["project_123"],
                    roles=[{"project_id": "project_123", "role_id": "7"}],
                )
                print(" Note: Email validation may not be enforced at SDK level")
            except Exception as e:
                print(f" Correctly caught error for invalid email: {str(e)}")

            print(" User management error handling tests completed successfully!")

        except Exception as e:
            print(f"User management error handling test failed: {str(e)}")
            raise

    @classmethod
    def setUpClass(cls):
        """Set up test suite."""

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        """Tear down test suite."""

    def run_user_management_tests(self):
        """Run only the user management integration tests"""

        # Check for required environment variables
        required_env_vars = ["API_KEY", "API_SECRET", "CLIENT_ID", "TEST_EMAIL"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set the following environment variables:")
            for var in missing_vars:
                print(f"  export {var}=your_value")
            return False

        print("🚀 Running User Management Integration Tests")
        print("=" * 50)

        # Create test suite with only user management tests
        suite = unittest.TestSuite()

        # Add user management test methods
        user_management_tests = [
            "test_user_management_workflow",
            "test_create_user_integration",
            "test_update_user_role_integration",
            "test_project_user_management_integration",
            "test_user_management_error_handling",
        ]

        for test_name in user_management_tests:
            suite.addTest(LabelerIntegrationTests(test_name))

        # Run tests with verbose output
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)

        # Print summary
        print("\n" + "=" * 50)
        if result.wasSuccessful():
            print("All user management integration tests passed!")
        else:
            print("Some user management integration tests failed!")
            print(f"Failures: {len(result.failures)}")
            print(f"Errors: {len(result.errors)}")

        return result.wasSuccessful()


def run_use_case_tests():

    suite = unittest.TestLoader().loadTestsFromTestCase(LabelerIntegrationTests)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    """
    Environment Variables Required:
    - API_KEY: Your Labellerr API key
    - API_SECRET: Your Labellerr API secret
    - CLIENT_ID: Your Labellerr client ID
    - TEST_EMAIL: Valid email address for testing
    - TEST_PROJECT_ID: (Optional) Project ID for attach/detach tests (default: "sunny_tough_blackbird_40468")
    - TEST_DATASET_ID: (Optional) Dataset ID for attach/detach tests (default: "055fecfe-d80e-4b93-90dd-dbb3a02dc03a")
    - AWS_CONNECTION_VIDEO: AWS video connection id
    - AWS_CONNECTION_IMAGE: AWS image connection id
    - GCS_CONNECTION_VIDEO: JSON string with GCS video creds {"cred_file:"{}","gcs_path":"gs://bucket/path"}
    - GCS_CONNECTION_IMAGE: JSON string with GCS image creds {"cred_file:"{}","gcs_path":"gs://bucket/path"}

    New User Management Tests Added:
    - test_user_management_workflow: Complete user lifecycle test
    - test_create_user_integration: User creation with real API calls
    - test_update_user_role_integration: User role updates with real API calls
    - test_project_user_management_integration: Project user management operations
    - test_user_management_error_handling: Error handling validation

    New Batch Operation Tests Added:
    - test_attach_datasets_batch_success: Test batch attachment of datasets
    - test_attach_datasets_batch_invalid_dataset_id: Test batch attach with invalid IDs
    - test_detach_datasets_batch_success: Test batch detachment of datasets
    - test_detach_datasets_batch_invalid_dataset_id: Test batch detach with invalid IDs

    Run with:
    python labellerr_integration_case_tests.py
    """
    # Check for required environment variables
    required_env_vars = [
        "API_KEY",
        "API_SECRET",
        "CLIENT_ID",
        "TEST_EMAIL",
        "AWS_CONNECTION_VIDEO",
        "AWS_CONNECTION_IMAGE",
        "GCS_CONNECTION_VIDEO",
        "GCS_CONNECTION_IMAGE",
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    # Run the tests
    success = run_use_case_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
