"""
Unit tests for dataset pagination functionality.

This module tests the pagination functionality in the get_all_datasets method
with proper mocking and parameterized test cases.
"""

from unittest.mock import patch

import pytest

from labellerr.core.datasets import list_datasets
from labellerr.core.schemas import DataSetScope

# Helper to use correct enum values
SCOPE_CLIENT = DataSetScope.client
SCOPE_PROJECT = DataSetScope.project
SCOPE_PUBLIC = DataSetScope.public


@pytest.fixture
def mock_single_page_response():
    """Mock response for a single page with no more pages"""
    return {
        "response": {
            "datasets": [
                {"id": "dataset1", "name": "Dataset 1", "data_type": "image"},
                {"id": "dataset2", "name": "Dataset 2", "data_type": "image"},
                {"id": "dataset3", "name": "Dataset 3", "data_type": "image"},
            ],
            "has_more": False,
            "last_dataset_id": "dataset3",
        }
    }


@pytest.fixture
def mock_first_page_response():
    """Mock response for first page with more pages available"""
    return {
        "response": {
            "datasets": [
                {"id": "dataset1", "name": "Dataset 1", "data_type": "image"},
                {"id": "dataset2", "name": "Dataset 2", "data_type": "image"},
            ],
            "has_more": True,
            "last_dataset_id": "dataset2",
        }
    }


@pytest.fixture
def mock_second_page_response():
    """Mock response for second page with more pages available"""
    return {
        "response": {
            "datasets": [
                {"id": "dataset3", "name": "Dataset 3", "data_type": "image"},
                {"id": "dataset4", "name": "Dataset 4", "data_type": "image"},
            ],
            "has_more": True,
            "last_dataset_id": "dataset4",
        }
    }


@pytest.fixture
def mock_last_page_response():
    """Mock response for last page with no more pages"""
    return {
        "response": {
            "datasets": [
                {"id": "dataset5", "name": "Dataset 5", "data_type": "image"},
            ],
            "has_more": False,
            "last_dataset_id": "dataset5",
        }
    }


@pytest.mark.unit
class TestGetAllDatasetsDefaultBehavior:
    """Test default pagination behavior (page_size not specified)"""

    def test_default_page_size_used(self, client, mock_single_page_response):
        """Test that default page size is used when not specified"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            result = list_datasets(client=client, datatype="image", scope=SCOPE_CLIENT)

            # Consume the generator to trigger the API call
            list(result)

            # Verify the request was made
            assert mock_request.called
            call_args = mock_request.call_args

            # Check that page_size=10 is in the URL (default)
            url = call_args[0][1]
            assert "page_size=10" in url
            assert "data_type=image" in url
            assert f"permission_level={SCOPE_CLIENT.value}" in url

    def test_default_returns_generator(self, client, mock_single_page_response):
        """Test that default behavior returns a generator"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            result = list_datasets(client=client, datatype="image", scope=SCOPE_CLIENT)

            # Check that result is a generator
            import types

            assert isinstance(result, types.GeneratorType)

            # Consume generator and verify datasets
            datasets = list(result)
            assert len(datasets) == 3
            assert datasets[0]["id"] == "dataset1"


@pytest.mark.unit
class TestGetAllDatasetsManualPagination:
    """Test manual pagination with explicit page_size"""

    def test_custom_page_size(self, client, mock_single_page_response):
        """Test that custom page size is used when specified"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            result = list_datasets(
                client=client, datatype="image", scope=SCOPE_CLIENT, page_size=20
            )

            # Consume generator
            list(result)

            call_args = mock_request.call_args
            url = call_args[0][1]
            assert "page_size=20" in url

    def test_pagination_with_last_dataset_id(self, client, mock_second_page_response):
        """Test pagination using last_dataset_id"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_second_page_response

            result = list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=2,
                last_dataset_id="dataset2",
            )

            # Consume generator
            list(result)

            call_args = mock_request.call_args
            url = call_args[0][1]
            assert "last_dataset_id=dataset2" in url
            assert "page_size=2" in url

    def test_manual_pagination_flow(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test complete manual pagination flow"""
        with patch.object(client, "make_request") as mock_request:
            # First page
            mock_request.return_value = mock_first_page_response
            first_page_gen = list_datasets(
                client=client, datatype="image", scope=SCOPE_CLIENT, page_size=2
            )
            first_page_datasets = list(first_page_gen)

            assert len(first_page_datasets) == 2
            assert first_page_datasets[0]["id"] == "dataset1"
            assert first_page_datasets[1]["id"] == "dataset2"

            # For next page, we need to track the last_dataset_id manually
            # In real usage, you'd extract this from the API response metadata
            # For this test, we know it's "dataset2"

            # Second page
            mock_request.return_value = mock_last_page_response
            second_page_gen = list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=2,
                last_dataset_id="dataset2",
            )
            second_page_datasets = list(second_page_gen)

            assert len(second_page_datasets) == 1
            assert second_page_datasets[0]["id"] == "dataset5"


@pytest.mark.unit
class TestGetAllDatasetsAutoPagination:
    """Test auto-pagination with page_size=-1"""

    def test_auto_pagination_returns_generator(self, client, mock_single_page_response):
        """Test that page_size=-1 returns a generator"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            result = list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=-1,
            )

            # Check that result is a generator
            import types

            assert isinstance(result, types.GeneratorType)

    def test_auto_pagination_yields_individual_datasets(
        self, client, mock_single_page_response
    ):
        """Test that auto-pagination yields individual datasets, not lists"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            # Should yield 3 individual datasets
            assert len(datasets) == 3
            assert datasets[0]["id"] == "dataset1"
            assert datasets[1]["id"] == "dataset2"
            assert datasets[2]["id"] == "dataset3"

    def test_auto_pagination_single_page(self, client, mock_single_page_response):
        """Test auto-pagination with only one page"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            # Should make only one request
            assert mock_request.call_count == 1
            assert len(datasets) == 3

    def test_auto_pagination_multiple_pages(
        self,
        client,
        mock_first_page_response,
        mock_second_page_response,
        mock_last_page_response,
    ):
        """Test auto-pagination across multiple pages"""
        with patch.object(client, "make_request") as mock_request:
            # Setup responses for 3 pages
            mock_request.side_effect = [
                mock_first_page_response,
                mock_second_page_response,
                mock_last_page_response,
            ]

            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            # Should make 3 requests
            assert mock_request.call_count == 3

            # Should yield all 5 datasets
            assert len(datasets) == 5
            assert datasets[0]["id"] == "dataset1"
            assert datasets[1]["id"] == "dataset2"
            assert datasets[2]["id"] == "dataset3"
            assert datasets[3]["id"] == "dataset4"
            assert datasets[4]["id"] == "dataset5"

    def test_auto_pagination_uses_default_page_size_internally(
        self, client, mock_single_page_response
    ):
        """Test that auto-pagination uses default page size for API calls"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            call_args = mock_request.call_args
            url = call_args[0][1]
            # Should use default page size (10) internally
            assert "page_size=10" in url

    def test_auto_pagination_passes_last_dataset_id(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test that auto-pagination correctly passes last_dataset_id between pages"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_last_page_response,
            ]

            list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            # Check second request includes last_dataset_id
            second_call_url = mock_request.call_args_list[1][0][1]
            assert "last_dataset_id=dataset2" in second_call_url

    def test_auto_pagination_early_termination(
        self, client, mock_first_page_response, mock_second_page_response
    ):
        """Test that auto-pagination allows early termination"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_second_page_response,
            ]

            generator = list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=-1,
            )

            # Get only first 3 datasets
            datasets = []
            for i, dataset in enumerate(generator):
                if i >= 3:
                    break
                datasets.append(dataset)

            # Should have 3 datasets
            assert len(datasets) == 3

            # Should have made 2 requests (to get 3 datasets)
            assert mock_request.call_count == 2


@pytest.mark.unit
class TestGetAllDatasetsEdgeCases:
    """Test edge cases and error scenarios"""

    def test_empty_results(self, client):
        """Test behavior when no datasets are returned"""
        empty_response = {
            "response": {"datasets": [], "has_more": False, "last_dataset_id": None}
        }

        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = empty_response

            result = list_datasets(client=client, datatype="image", scope=SCOPE_CLIENT)

            datasets = list(result)
            assert datasets == []

    def test_empty_results_auto_pagination(self, client):
        """Test auto-pagination with no results"""
        empty_response = {
            "response": {"datasets": [], "has_more": False, "last_dataset_id": None}
        }

        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = empty_response

            datasets = list(
                list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            )

            assert len(datasets) == 0

    def test_different_data_types(self, client, mock_single_page_response):
        """Test pagination with different data types"""
        data_types = ["image", "video", "audio", "document", "text"]

        for data_type in data_types:
            with patch.object(client, "make_request") as mock_request:
                mock_request.return_value = mock_single_page_response

                result = list_datasets(
                    client=client, datatype=data_type, scope=SCOPE_CLIENT
                )
                list(result)  # Consume generator

                call_args = mock_request.call_args
                url = call_args[0][1]
                assert f"data_type={data_type}" in url

    def test_different_scopes(self, client, mock_single_page_response):
        """Test pagination with different permission scopes"""
        scopes = [SCOPE_CLIENT, SCOPE_PROJECT, SCOPE_PUBLIC]

        for scope in scopes:
            with patch.object(client, "make_request") as mock_request:
                mock_request.return_value = mock_single_page_response

                result = list_datasets(client=client, datatype="image", scope=scope)
                list(result)  # Consume generator

                call_args = mock_request.call_args
                url = call_args[0][1]
                assert f"permission_level={scope.value}" in url

    def test_large_page_size(self, client, mock_single_page_response):
        """Test with very large page size"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.return_value = mock_single_page_response

            result = list_datasets(
                client=client, datatype="image", scope=SCOPE_CLIENT, page_size=1000
            )
            list(result)  # Consume generator

            call_args = mock_request.call_args
            url = call_args[0][1]
            assert "page_size=1000" in url

    def test_auto_pagination_memory_efficiency(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test that auto-pagination doesn't load all results into memory"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_last_page_response,
            ]

            generator = list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=-1,
            )

            # Only call next() once
            first_dataset = next(generator)
            assert first_dataset["id"] == "dataset1"

            # Only one request should have been made so far
            assert mock_request.call_count == 1


@pytest.mark.unit
class TestGetAllDatasetsIntegration:
    """Integration-style tests that simulate real usage patterns"""

    def test_iterate_with_for_loop(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test typical for-loop iteration pattern"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_last_page_response,
            ]

            dataset_ids = []
            for dataset in list_datasets(
                client=client,
                datatype="image",
                scope=SCOPE_CLIENT,
                page_size=-1,
            ):
                dataset_ids.append(dataset["id"])

            assert dataset_ids == ["dataset1", "dataset2", "dataset5"]

    def test_list_comprehension(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test using generator with list comprehension"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_last_page_response,
            ]

            dataset_names = [
                d["name"]
                for d in list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
            ]

            assert dataset_names == ["Dataset 1", "Dataset 2", "Dataset 5"]

    def test_filtering_while_iterating(
        self, client, mock_first_page_response, mock_last_page_response
    ):
        """Test filtering datasets while iterating"""
        with patch.object(client, "make_request") as mock_request:
            mock_request.side_effect = [
                mock_first_page_response,
                mock_last_page_response,
            ]

            # Get only datasets with even IDs
            even_datasets = [
                d
                for d in list_datasets(
                    client=client,
                    datatype="image",
                    scope=SCOPE_CLIENT,
                    page_size=-1,
                )
                if int(d["id"][-1]) % 2 == 0
            ]

            assert len(even_datasets) == 1
            assert even_datasets[0]["id"] == "dataset2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
