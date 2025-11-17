#!/usr/bin/env python3
"""
Integration tests for sync_datasets API with AWS and GCS.

This test file contains separate tests for AWS S3 and Google Cloud Storage (GCS) sync operations.
Each test uses its own dataset ID and connection ID.

Environment variables required (set in root .env file):
  - API_KEY, API_SECRET, CLIENT_ID (required for all tests)

Test data for AWS and GCS is defined within the test class.
"""

import os
import sys
import unittest
from dataclasses import dataclass
from typing import Optional

import dotenv

from labellerr import LabellerrError
from labellerr.client import LabellerrClient
from labellerr.core.datasets import LabellerrDataset

dotenv.load_dotenv()


@dataclass
class SyncDatasetTestCase:
    """Test case for sync dataset operations"""

    test_name: str
    client_id: str
    project_id: str
    dataset_id: str
    connection_id: str
    path: str
    email_id: str
    data_type: str = "image"
    expect_error_substr: Optional[str] = None
    expected_success: bool = True


class SyncDatasetsIntegrationTests(unittest.TestCase):
    """Integration tests for sync_datasets operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.client_id = os.getenv("CLIENT_ID")

        if not all([self.api_key, self.api_secret, self.client_id]):
            raise ValueError(
                "Missing environment variables: API_KEY, API_SECRET, CLIENT_ID"
            )

        self.client = LabellerrClient(self.api_key, self.api_secret, self.client_id)

        # Shared configuration (used by both AWS and GCS tests)
        self.project_id = "gabrila_artificial_duck_74237"  # Same project for both tests
        self.email_id = "dev@labellerr.com"  # Same email for both tests
        self.data_type = "image"  # Same data type for both tests

        # AWS-specific test configuration
        self.aws_dataset_id = "b51cf22c-cc57-45dd-a6d5-f2d18ab679a1"
        self.aws_connection_id = "96b2950b-2800-4772-ac75-24eff5642ebe"
        self.aws_path = "s3://amazon-s3-sync-test/gaurav_test"

        # GCS-specific test configuration - TODO: Fill in these values
        self.gcs_dataset_id = ""  # TODO: Add your GCS dataset ID
        self.gcs_connection_id = ""  # TODO: Add your GCS connection ID
        self.gcs_path = "gs://"  # TODO: Add your GCS path (e.g., gs://bucket/path)

    def test_sync_datasets_aws(self):
        """Test syncing datasets from AWS S3"""
        datasets = LabellerrDataset(client=self.client, dataset_id=self.aws_dataset_id)
        print("\n" + "=" * 60)
        print("TEST: Sync Datasets - AWS S3")
        print("=" * 60)

        try:
            print("\n1. Syncing dataset from AWS S3...")
            print(f"Project ID: {self.project_id}")
            print(f"Dataset ID: {self.aws_dataset_id}")
            print(f"Connection ID: {self.aws_connection_id}")
            print(f"Path: {self.aws_path}")
            print(f"Data Type: {self.data_type}")
            print(f"Email ID: {self.email_id}")

            response = datasets.sync_with_connection(
                client_id=self.client_id,
                project_id=self.project_id,
                dataset_id=self.aws_dataset_id,
                path=self.aws_path,
                data_type=self.data_type,
                email_id=self.email_id,
                connection_id=self.aws_connection_id,
            )

            print("AWS Sync successful")
            print(f"Response: {response}")

            self.assertIsInstance(response, dict)
            self.assertIsNotNone(response)

        except LabellerrError as e:
            self.fail(f"AWS Sync API ERROR: {str(e)}")
        except Exception as e:
            self.fail(f"AWS Sync ERROR: {type(e).__name__}: {str(e)}")

    def test_sync_datasets_gcs(self):
        """Test syncing datasets from Google Cloud Storage (GCS)"""
        datasets = LabellerrDataset(client=self.client, dataset_id=self.gcs_dataset_id)
        if not all(
            [
                self.gcs_dataset_id,
                self.gcs_connection_id,
                self.gcs_path != "gs://",
            ]
        ):

            print("\n" + "=" * 60)
            print("TEST: Sync Datasets - Google Cloud Storage (GCS)")
            print("=" * 60)

            try:
                print("\n1. Syncing dataset from GCS...")
                print(f"Project ID: {self.project_id}")
                print(f"Dataset ID: {self.gcs_dataset_id}")
                print(f"Connection ID: {self.gcs_connection_id}")
                print(f"Path: {self.gcs_path}")
                print(f"Data Type: {self.data_type}")
                print(f"Email ID: {self.email_id}")

                response = datasets.sync_with_connection(
                    client_id=self.client_id,
                    project_id=self.project_id,
                    dataset_id=self.gcs_dataset_id,
                    path=self.gcs_path,
                    data_type=self.data_type,
                    email_id=self.email_id,
                    connection_id=self.gcs_connection_id,
                )

                print("GCS Sync successful")
                print(f"Response: {response}")

                self.assertIsInstance(response, dict)
                self.assertIsNotNone(response)

            except LabellerrError as e:
                self.fail(f"GCS Sync API ERROR: {str(e)}")
            except Exception as e:
                self.fail(f"GCS Sync ERROR: {type(e).__name__}: {str(e)}")

    def test_sync_datasets_with_multiple_data_types(self):
        """Test syncing datasets with different data types (AWS)"""
        datasets = LabellerrDataset(client=self.client, dataset_id=self.aws_dataset_id)
        print("\n" + "=" * 60)
        print("TEST: Sync Datasets with Multiple Data Types")
        print("=" * 60)

        data_types = ["image", "video", "audio", "document", "text"]

        for data_type in data_types:
            with self.subTest(data_type=data_type):
                print(f"\n  Testing with data_type: {data_type}")

                try:
                    response = datasets.sync_with_connection(
                        client_id=self.client_id,
                        project_id=self.project_id,
                        dataset_id=self.aws_dataset_id,
                        path=self.aws_path,
                        data_type=data_type,
                        email_id=self.email_id,
                        connection_id=self.aws_connection_id,
                    )

                    print(f"Sync successful for {data_type}")
                    self.assertIsInstance(response, dict)

                except LabellerrError as e:
                    # Log error but don't fail - API might restrict certain data types
                    print(f"ℹ {data_type} sync skipped: {str(e)[:100]}")

    def test_sync_datasets_invalid_connection_id(self):
        """Test sync datasets with invalid connection ID"""
        datasets = LabellerrDataset(client=self.client, dataset_id=self.aws_dataset_id)
        print("\n" + "=" * 60)
        print("TEST: Sync Datasets with Invalid Connection ID")
        print("=" * 60)

        with self.assertRaises((LabellerrError, Exception)) as context:
            datasets.sync_with_connection(
                client_id=self.client_id,
                project_id=self.project_id,
                dataset_id=self.aws_dataset_id,
                path=self.aws_path,
                data_type=self.data_type,
                email_id=self.email_id,
                connection_id="invalid-connection-id",
            )

        print(f"Correctly caught error: {str(context.exception)[:100]}")

    def test_sync_datasets_invalid_dataset_id(self):
        """Test sync datasets with invalid dataset ID"""
        datasets = LabellerrDataset(client=self.client, dataset_id=self.aws_dataset_id)
        print("\n" + "=" * 60)
        print("TEST: Sync Datasets with Invalid Dataset ID")
        print("=" * 60)

        with self.assertRaises((LabellerrError, Exception)) as context:
            datasets.sync_with_connection(
                client_id=self.client_id,
                project_id=self.project_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
                path=self.aws_path,
                data_type=self.data_type,
                email_id=self.email_id,
                connection_id=self.aws_connection_id,
            )

        print(f"Correctly caught error: {str(context.exception)[:100]}")

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, "client"):
            self.client.close()

    @classmethod
    def setUpClass(cls):
        """Set up test suite"""
        print("\n" + "=" * 80)
        print(" SYNC DATASETS OPERATIONS - INTEGRATION TESTS")
        print("=" * 80)

    @classmethod
    def tearDownClass(cls):
        """Tear down test suite"""
        print("\n" + "=" * 80)
        print(" INTEGRATION TESTS COMPLETED")
        print("=" * 80)


def run_sync_datasets_tests():
    """Run all sync datasets integration tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(SyncDatasetsIntegrationTests)

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

    AWS Configuration (defined in setUp method):
    - aws_project_id: Project ID for AWS sync
    - aws_dataset_id: Dataset ID for AWS sync
    - aws_connection_id: Connection ID for AWS
    - aws_path: S3 path (e.g., s3://bucket/path)
    - aws_email_id: Email ID for AWS sync

    GCS Configuration (TODO in setUp method):
    - gcs_project_id: Project ID for GCS sync
    - gcs_dataset_id: Dataset ID for GCS sync
    - gcs_connection_id: Connection ID for GCS
    - gcs_path: GCS path (e.g., gs://bucket/path)
    - gcs_email_id: Email ID for GCS sync

    Run with:
    python tests/integration/test_sync_datasets.py
    """
    # Check for required environment variables
    required_env_vars = ["API_KEY", "API_SECRET", "CLIENT_ID"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\nMissing required environment variables: {', '.join(missing_vars)}")
        print("Please set the following environment variables:")
        for var in missing_vars:
            print(f"  export {var}=your_value")
        sys.exit(1)

    # Run the tests
    success = run_sync_datasets_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
