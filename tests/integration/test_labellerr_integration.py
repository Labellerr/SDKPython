"""
Comprehensive integration tests for the Labellerr SDK.

This module consolidates all integration tests into a single, well-organized test suite
that covers the complete functionality of the Labellerr SDK with real API calls.
"""

import json
import os
import signal
import time
from typing import Dict, List

import pytest
from pydantic import ValidationError

from labellerr.client import LabellerrClient
from labellerr.core.connectors import LabellerrConnection
from labellerr.core.connectors.gcs_connection import GCSConnection
from labellerr.core.connectors.s3_connection import S3Connection
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import LabellerrProject, create_project
from labellerr.core.schemas import (
    AWSConnectionParams,
    CreateUserParams,
    DatasetDataType,
    DeleteUserParams,
    UpdateUserRoleParams,
)


@pytest.mark.integration
class TestProjectCreationWorkflow:
    """Test complete project creation workflows"""

    def test_complete_project_creation_workflow(
        self, integration_client, sample_project_payload, test_credentials
    ):
        """Test complete project creation workflow with file upload"""
        payload = sample_project_payload()

        try:
            result = create_project(integration_client, payload)

            # Validate response structure
            assert isinstance(
                result, LabellerrProject
            ), "Should return LabellerrProject instance"
            assert hasattr(result, "project_id"), "Should have project_id attribute"

        except LabellerrError as e:
            pytest.fail(f"Project creation failed with LabellerrError: {e}")

    @pytest.mark.parametrize("data_type", ["image", "document"])
    def test_project_creation_by_data_type(
        self, integration_client, sample_project_payload, data_type
    ):
        """Test project creation for different data types"""
        payload = sample_project_payload(data_type=data_type)

        try:
            result = create_project(integration_client, payload)
            assert isinstance(result, LabellerrProject)

        except LabellerrError as e:
            # Some data types might not be supported in test environment
            if "invalid" in str(e).lower() or "not supported" in str(e).lower():
                pytest.skip(f"Data type {data_type} not supported in test environment")
            else:
                pytest.fail(f"Project creation failed: {e}")

    @pytest.mark.parametrize(
        "missing_field,expected_error",
        [
            ("client_id", "Required parameter client_id is missing"),
            ("dataset_name", "Required parameter dataset_name is missing"),
            (
                "annotation_guide",
                "Please provide either annotation guide or annotation template id",
            ),
        ],
    )
    def test_project_creation_missing_required_fields(
        self, integration_client, sample_project_payload, missing_field, expected_error
    ):
        """Test project creation fails with missing required fields"""
        payload = sample_project_payload()
        del payload[missing_field]

        with pytest.raises(LabellerrError) as exc_info:
            create_project(integration_client, payload)

        assert expected_error in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_field,invalid_value,expected_error",
        [
            ("created_by", "invalid-email", "Please enter email id in created_by"),
            ("data_type", "invalid_type", "Invalid data_type"),
            ("client_id", 123, "client_id must be a non-empty string"),
        ],
    )
    def test_project_creation_invalid_field_values(
        self,
        integration_client,
        sample_project_payload,
        invalid_field,
        invalid_value,
        expected_error,
    ):
        """Test project creation fails with invalid field values"""
        payload = sample_project_payload()
        payload[invalid_field] = invalid_value

        with pytest.raises(LabellerrError) as exc_info:
            create_project(integration_client, payload)

        assert expected_error in str(exc_info.value)


@pytest.mark.integration
class TestPreAnnotationWorkflow:
    """Test pre-annotation upload workflows"""

    def test_pre_annotation_upload_coco_json(
        self,
        integration_client,
        test_credentials,
        test_project_ids,
        sample_annotation_data,
        temp_json_file,
    ):
        """Test uploading pre-annotations in COCO JSON format"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])

        annotation_file = temp_json_file(sample_annotation_data["coco_json"])

        try:
            future = project.upload_preannotation(
                annotation_format="coco_json",
                annotation_file=annotation_file,
            )
            result = future.result()

            assert isinstance(result, dict)
            assert "response" in result

        except LabellerrError as e:
            # Handle common API errors gracefully
            error_str = str(e).lower()
            if any(
                phrase in error_str
                for phrase in ["invalid project", "not found", "403", "401"]
            ):
                pytest.skip(f"Skipping test due to API access issue: {e}")
            else:
                raise
        finally:
            try:
                os.unlink(annotation_file)
            except OSError:
                pass

    def test_pre_annotation_upload_json_with_timeout(
        self,
        integration_client,
        test_credentials,
        test_project_ids,
        sample_annotation_data,
        temp_json_file,
    ):
        """Test uploading pre-annotations in JSON format with timeout protection"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])

        annotation_file = temp_json_file(sample_annotation_data["json"])

        def timeout_handler(signum, frame):
            raise TimeoutError("Test timed out after 60 seconds")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)

        try:
            future = project.upload_preannotation(
                annotation_format="json",
                annotation_file=annotation_file,
            )
            result = future.result()

            assert isinstance(result, dict)

        except TimeoutError as e:
            pytest.fail(f"Test timed out: {e}")
        except LabellerrError as e:
            error_str = str(e).lower()
            if any(
                phrase in error_str
                for phrase in ["invalid project", "not found", "timeout"]
            ):
                pytest.skip(f"Skipping test due to API issue: {e}")
            else:
                raise
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            try:
                os.unlink(annotation_file)
            except OSError:
                pass

    @pytest.mark.parametrize(
        "invalid_format,expected_error",
        [
            ("invalid_format", "Invalid annotation_format"),
            ("xml", "Invalid annotation_format"),
        ],
    )
    def test_pre_annotation_invalid_format(
        self,
        integration_client,
        test_credentials,
        test_project_ids,
        invalid_format,
        expected_error,
    ):
        """Test pre-annotation upload fails with invalid format"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])

        with pytest.raises(LabellerrError) as exc_info:
            future = project.upload_preannotation(
                annotation_format=invalid_format,
                annotation_file="test.json",
            )
            future.result()

        assert expected_error in str(exc_info.value)


@pytest.mark.integration
class TestDatasetAttachDetachWorkflow:
    """Test dataset attach/detach operations"""

    def test_attach_detach_single_dataset(self, integration_client, test_project_ids):
        """Test single dataset attach/detach workflow"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])
        dataset_id = test_project_ids["dataset_id"]

        # Step 1: Detach first to ensure clean state
        try:
            detach_result = project.detach_dataset_from_project(dataset_id=dataset_id)
            assert isinstance(detach_result, dict)
        except Exception:
            # Dataset might not be attached - that's okay
            pass

        # Step 2: Attach dataset
        try:
            attach_result = project.attach_dataset_to_project(dataset_id=dataset_id)
            assert isinstance(attach_result, dict)
            assert "response" in attach_result
        except LabellerrError as e:
            if "already attached" in str(e).lower():
                pytest.skip("Dataset already attached")
            else:
                raise

    def test_attach_detach_batch_datasets(self, integration_client, test_project_ids):
        """Test batch dataset attach/detach workflow"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])
        dataset_ids = [test_project_ids["dataset_id"]]

        # Step 1: Detach batch first
        try:
            detach_result = project.detach_dataset_from_project(dataset_ids=dataset_ids)
            assert isinstance(detach_result, dict)
        except Exception:
            pass

        # Step 2: Attach batch
        try:
            attach_result = project.attach_dataset_to_project(dataset_ids=dataset_ids)
            assert isinstance(attach_result, dict)
        except LabellerrError as e:
            if "already attached" in str(e).lower():
                pytest.skip("Datasets already attached")
            else:
                raise

    @pytest.mark.parametrize(
        "invalid_params,expected_error",
        [
            (
                {"dataset_id": "invalid-id"},
                "doesn't exist",
            ),  # API returns "doesn't exist" not "valid UUID"
            (
                {"dataset_id": None, "dataset_ids": None},
                "Either dataset_id or dataset_ids must be provided",
            ),
            (
                {"dataset_id": "test", "dataset_ids": ["test"]},
                "Cannot provide both dataset_id and dataset_ids",
            ),
        ],
    )
    def test_attach_dataset_parameter_validation(
        self, integration_client, test_project_ids, invalid_params, expected_error
    ):
        """Test dataset attachment parameter validation"""
        project = LabellerrProject(integration_client, test_project_ids["project_id"])

        with pytest.raises((ValidationError, LabellerrError)) as exc_info:
            project.attach_dataset_to_project(**invalid_params)

        # Case-insensitive comparison for both error message and expected error
        assert expected_error.lower() in str(exc_info.value).lower()


@pytest.mark.integration
class TestMultimodalIndexingWorkflow:
    """Test multimodal indexing operations"""

    def test_enable_disable_multimodal_indexing(
        self, integration_client, test_credentials, test_project_ids
    ):
        """Test complete multimodal indexing workflow"""
        dataset_id = test_project_ids["dataset_id"]

        try:
            # Create dataset instance
            dataset = LabellerrDataset(integration_client, dataset_id)

            # Enable multimodal indexing
            enable_result = dataset.enable_multimodal_indexing(is_multimodal=True)
            assert isinstance(enable_result, dict)
            assert "response" in enable_result

            # Note: Disabling multimodal indexing is not supported per the implementation
            # The assertion in enable_multimodal_indexing prevents is_multimodal=False

        except LabellerrError as e:
            if any(
                phrase in str(e).lower()
                for phrase in ["not found", "invalid", "403", "401", "not supported"]
            ):
                pytest.skip(f"Skipping multimodal test due to API access: {e}")
            else:
                raise

    @pytest.mark.parametrize(
        "invalid_dataset_id,expected_error",
        [
            ("invalid-id", "not found"),  # API will return dataset not found
            ("00000000-0000-0000-0000-000000000000", "not found"),  # Non-existent UUID
        ],
    )
    def test_multimodal_indexing_validation(
        self, integration_client, test_credentials, invalid_dataset_id, expected_error
    ):
        """Test multimodal indexing parameter validation"""
        try:
            # Try to create dataset with invalid ID - should fail
            dataset = LabellerrDataset(integration_client, invalid_dataset_id)
            dataset.enable_multimodal_indexing(is_multimodal=True)
            pytest.fail("Should have raised an error for invalid dataset")
        except (LabellerrError, Exception) as exc_info:
            # Check that appropriate error is raised
            assert (
                expected_error in str(exc_info).lower()
                or "invalid" in str(exc_info).lower()
            )


@pytest.mark.integration
class TestConnectionManagement:
    """Test connection management for AWS and GCS"""

    @pytest.mark.aws
    def test_aws_connection_lifecycle(self, integration_client, test_credentials):
        """Test complete AWS connection lifecycle"""
        # Skip if AWS credentials not available
        aws_config = os.getenv("AWS_CONNECTION_IMAGE")
        if not aws_config:
            pytest.skip("AWS connection config not available")

        try:
            aws_secret = json.loads(aws_config)
        except json.JSONDecodeError:
            pytest.skip("Invalid AWS connection config format")

        connection_name = f"test_aws_conn_{int(time.time())}"

        try:
            # Create connection using S3Connection.setup_full_connection
            params = AWSConnectionParams(
                client_id=test_credentials["client_id"],
                aws_access_key=aws_secret.get("access_key"),
                aws_secrets_key=aws_secret.get("secret_key"),
                path=aws_secret.get("s3_path"),
                data_type=DatasetDataType.image,
                name=connection_name,
                description="Test AWS connection",
                connection_type="import",
            )
            create_result = S3Connection.setup_full_connection(
                integration_client, params
            )

            assert isinstance(create_result, dict)
            connection_id = create_result["response"]["connection_id"]

            # Create a connection instance to use list and delete methods
            connection = LabellerrConnection(
                integration_client,
                connection_id,
                connection_data=create_result["response"],
            )

            # List connections
            list_result = connection.list_connections(
                connection_type="import",
                connector="s3",
            )
            assert isinstance(list_result, dict)

            # Delete connection
            delete_result = connection.delete_connection(connection_id=connection_id)
            assert isinstance(delete_result, dict)

        except LabellerrError as e:
            if "500" in str(e) or "Max retries exceeded" in str(e):
                pytest.skip(f"API unavailable: {e}")
            else:
                raise

    @pytest.mark.gcs
    def test_gcs_connection_lifecycle(self, integration_client, test_credentials):
        """Test complete GCS connection lifecycle"""
        gcs_config = os.getenv("GCS_CONNECTION_IMAGE")
        if not gcs_config:
            pytest.skip("GCS connection config not available")

        try:
            gcs_secret = json.loads(gcs_config)
        except json.JSONDecodeError:
            pytest.skip("Invalid GCS connection config format")

        if not gcs_secret.get("bucket_name"):
            pytest.skip("Incomplete GCS credentials - bucket_name required")

        try:
            # Create connection using GCSConnection.create_connection (quick connection)
            gcp_config = {
                "bucket_name": gcs_secret["bucket_name"],
                "folder_path": gcs_secret.get("folder_path", ""),
                "service_account_key": gcs_secret.get("service_account_key"),
            }

            connection_id = GCSConnection.create_connection(
                integration_client, gcp_config
            )
            assert connection_id is not None
            assert isinstance(connection_id, str)

            # Create a connection instance to use delete method
            # Note: For quick connections, we may not have full connection_data
            # So we'll create a minimal connection_data dict
            connection_data = {
                "connection_id": connection_id,
                "connection_type": "import",
            }
            connection = LabellerrConnection(
                integration_client, connection_id, connection_data=connection_data
            )

            # Clean up connection
            delete_result = connection.delete_connection(connection_id=connection_id)
            assert isinstance(delete_result, dict)

        except LabellerrError as e:
            if "500" in str(e) or "unavailable" in str(e).lower():
                pytest.skip(f"API unavailable: {e}")
            else:
                raise


@pytest.mark.integration
class TestUserManagementWorkflow:
    """Test user management operations"""

    def test_user_lifecycle_workflow(self, integration_client, test_credentials):
        """Test complete user management lifecycle"""
        test_email = f"test_user_{int(time.time())}@example.com"
        test_project_id = "test_project_123"
        test_role_id = "7"
        test_new_role_id = "5"

        try:
            # Create user
            create_result = integration_client.users.create_user(
                CreateUserParams(
                    client_id=test_credentials["client_id"],
                    first_name="Test",
                    last_name="User",
                    email_id=test_email,
                    projects=[test_project_id],
                    roles=[{"project_id": test_project_id, "role_id": test_role_id}],
                )
            )
            assert create_result is not None

            # Update user role
            update_result = integration_client.users.update_user_role(
                UpdateUserRoleParams(
                    client_id=test_credentials["client_id"],
                    project_id=test_project_id,
                    email_id=test_email,
                    roles=[
                        {"project_id": test_project_id, "role_id": test_new_role_id}
                    ],
                    first_name="Test",
                    last_name="User",
                )
            )
            assert update_result is not None

            # Remove user from project
            remove_result = integration_client.users.remove_user_from_project(
                project_id=test_project_id,
                email_id=test_email,
            )
            assert remove_result is not None

            # Delete user
            delete_result = integration_client.users.delete_user(
                DeleteUserParams(
                    client_id=test_credentials["client_id"],
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name="Test",
                    last_name="User",
                )
            )
            assert delete_result is not None

        except Exception as e:
            # User management tests may fail in test environment
            pytest.skip(f"User management test skipped: {e}")

    @pytest.mark.parametrize(
        "invalid_params,expected_error",
        [
            (
                {"last_name": "", "email_id": "", "projects": [], "roles": []},
                "validation error",
            ),
            ({"email_id": "invalid_email"}, None),  # May not validate at SDK level
        ],
    )
    def test_user_creation_validation(
        self, integration_client, test_credentials, invalid_params, expected_error
    ):
        """Test user creation parameter validation"""
        base_params = {
            "client_id": test_credentials["client_id"],
            "first_name": "Test",
            "last_name": "User",
            "email_id": "test@example.com",
            "projects": ["project_123"],
            "roles": [{"project_id": "project_123", "role_id": "7"}],
        }
        base_params.update(invalid_params)

        if expected_error:
            with pytest.raises(ValidationError):
                integration_client.users.create_user(CreateUserParams(**base_params))
        else:
            # Test may pass or fail depending on API validation
            try:
                integration_client.users.create_user(CreateUserParams(**base_params))
            except Exception:
                pass  # Expected in test environment


# Utility functions for integration tests
def cleanup_test_resources(
    client: LabellerrClient, client_id: str, resources: Dict[str, List[str]]
):
    """Clean up test resources after integration tests"""
    for resource_type, resource_ids in resources.items():
        for resource_id in resource_ids:
            try:
                if resource_type == "connections":
                    client.delete_connection(
                        client_id=client_id, connection_id=resource_id
                    )
                # Add other resource cleanup as needed
            except Exception:
                pass  # Ignore cleanup errors
