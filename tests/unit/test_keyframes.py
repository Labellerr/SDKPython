"""
Unit tests for KeyFrame functionality and validation.

This module contains unit tests for KeyFrame dataclass,
validation decorators, and keyframe-related client methods.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from labellerr.client import LabellerrClient
from labellerr.core.exceptions import LabellerrError
from labellerr.core.schemas import KeyFrame
from labellerr.core.utils import validate_params


@pytest.mark.unit
class TestKeyFrame:
    """Unit tests for KeyFrame dataclass"""

    @pytest.mark.parametrize(
        "frame_number,is_manual,method,source,expected",
        [
            # Valid creation with defaults
            (
                10,
                None,
                None,
                None,
                {
                    "frame_number": 10,
                    "is_manual": True,
                    "method": "manual",
                    "source": "manual",
                },
            ),
            # Custom values
            (
                5,
                False,
                "automatic",
                "ai",
                {
                    "frame_number": 5,
                    "is_manual": False,
                    "method": "automatic",
                    "source": "ai",
                },
            ),
            # Edge cases
            (
                0,
                True,
                "manual",
                "manual",
                {
                    "frame_number": 0,
                    "is_manual": True,
                    "method": "manual",
                    "source": "manual",
                },
            ),
            (
                999,
                False,
                "ai",
                "system",
                {
                    "frame_number": 999,
                    "is_manual": False,
                    "method": "ai",
                    "source": "system",
                },
            ),
        ],
    )
    def test_keyframe_valid_creation(
        self, frame_number, is_manual, method, source, expected
    ):
        """Test creating valid KeyFrame objects with various parameters"""
        kwargs = {"frame_number": frame_number}
        if is_manual is not None:
            kwargs["is_manual"] = is_manual
        if method is not None:
            kwargs["method"] = method
        if source is not None:
            kwargs["source"] = source

        keyframe = KeyFrame(**kwargs)
        assert keyframe.model_dump() == expected

    @pytest.mark.parametrize(
        "invalid_params,expected_error",
        [
            # Invalid frame_number
            ({"frame_number": "not_an_int"}, "validation error"),
            ({"frame_number": 1.5}, "validation error"),
            ({"frame_number": None}, "validation error"),
            # Invalid is_manual
            (
                {"frame_number": 1, "is_manual": "not_a_bool"},
                "validation error",
            ),
            ({"frame_number": 1, "is_manual": 1}, "validation error"),
            # Invalid method
            ({"frame_number": 1, "method": 123}, "validation error"),
            ({"frame_number": 1, "method": []}, "validation error"),
            # Invalid source
            ({"frame_number": 1, "source": 456}, "validation error"),
            ({"frame_number": 1, "source": {}}, "validation error"),
        ],
    )
    def test_keyframe_invalid_creation(self, invalid_params, expected_error):
        """Test KeyFrame creation with invalid parameters"""
        with pytest.raises(ValidationError, match=expected_error):
            KeyFrame(**invalid_params)


@pytest.mark.unit
class TestValidateParamsDecorator:
    """Unit tests for validate_params decorator"""

    @pytest.mark.parametrize(
        "validation_spec,args,kwargs,expected_result",
        [
            # Single type validation
            ({"param1": str, "param2": int}, ("hello", 42), {}, "hello_42"),
            # Union types
            ({"param1": (str, int)}, ("hello",), {}, "hello"),
            ({"param1": (str, int)}, (42,), {}, 42),
            # Keyword arguments
            ({"param1": str, "param2": int}, ("hello",), {"param2": 20}, "hello_20"),
            # Missing optional parameter
            ({"param1": str, "param2": int}, ("hello",), {}, "hello_10"),
        ],
    )
    def test_validate_params_valid_cases(
        self, validation_spec, args, kwargs, expected_result
    ):
        """Test validation decorator with valid parameters"""
        if len(validation_spec) == 1 and "param1" in validation_spec:

            @validate_params(**validation_spec)
            def test_func(param1):
                return param1

        else:

            @validate_params(**validation_spec)
            def test_func(param1, param2=10):
                return f"{param1}_{param2}"

        result = test_func(*args, **kwargs)
        assert result == expected_result

    @pytest.mark.parametrize(
        "validation_spec,args,kwargs,expected_error",
        [
            # Invalid single type
            ({"param1": str}, (123,), {}, "param1 must be a str"),
            # Invalid union type
            ({"param1": (str, int)}, ([1, 2, 3],), {}, "param1 must be a str or int"),
            # Invalid type with multiple params
            (
                {"param1": str, "param2": int},
                ("hello", "not_int"),
                {},
                "param2 must be a int",
            ),
        ],
    )
    def test_validate_params_invalid_cases(
        self, validation_spec, args, kwargs, expected_error
    ):
        """Test validation decorator with invalid parameters"""

        @validate_params(**validation_spec)
        def test_func(param1, param2=10):
            return f"{param1}_{param2}"

        with pytest.raises(LabellerrError, match=expected_error):
            test_func(*args, **kwargs)


@pytest.fixture
def mock_client():
    """Create a mock client for testing"""
    client = LabellerrClient("test_api_key", "test_api_secret", "test_client_id")
    client.base_url = "https://api.labellerr.com"
    return client


@pytest.fixture
def mock_video_project(mock_client):
    """Create a mock video project instance"""
    from labellerr.core.projects.video_project import VideoProject

    # Create instance bypassing metaclass
    project = VideoProject.__new__(VideoProject)
    project.client = mock_client
    project._LabellerrProject__project_id_input = "test_project_id"
    project._LabellerrProject__project_data = {
        "project_id": "test_project_id",
        "data_type": "video",
        "attached_datasets": [],
    }
    return project


@pytest.mark.unit
class TestAddOrUpdateKeyFramesMethod:
    """Unit tests for add_or_update_keyframes method on VideoProject"""

    @patch("labellerr.core.client.LabellerrClient.make_request")
    def test_add_or_update_keyframes_success(
        self, mock_make_request, mock_video_project
    ):
        """Test successful key frame linking"""
        # Arrange
        mock_make_request.return_value = {"status": "success"}

        keyframes = [
            KeyFrame(frame_number=0),
            KeyFrame(frame_number=10, is_manual=False),
        ]

        # Act
        result = mock_video_project.add_or_update_keyframes("test_file", keyframes)

        # Assert
        assert result == {"status": "success"}
        mock_make_request.assert_called_once()
        args, kwargs = mock_make_request.call_args

        assert args[0] == "POST"
        assert "/actions/add_update_keyframes" in args[1]
        assert "client_id=test_client_id" in args[1]
        assert kwargs["extra_headers"]["content-type"] == "application/json"

        expected_body = {
            "project_id": "test_project_id",
            "file_id": "test_file",
            "keyframes": [
                {
                    "frame_number": 0,
                    "is_manual": True,
                    "method": "manual",
                    "source": "manual",
                },
                {
                    "frame_number": 10,
                    "is_manual": False,
                    "method": "manual",
                    "source": "manual",
                },
            ],
        }
        assert kwargs["json"] == expected_body

    @pytest.mark.parametrize(
        "file_id,keyframes,expected_error",
        [
            # Invalid file_id
            (
                789,
                [KeyFrame(frame_number=0)],
                "file_id must be a str",
            ),
            (
                {},
                [KeyFrame(frame_number=0)],
                "file_id must be a str",
            ),
            # Invalid keyframes
            (
                "test_file",
                "not_a_list",
                "keyframes must be a list",
            ),
            (
                "test_file",
                123,
                "keyframes must be a list",
            ),
            (
                "test_file",
                None,
                "keyframes must be a list",
            ),
        ],
    )
    def test_add_or_update_keyframes_invalid_parameters(
        self, mock_video_project, file_id, keyframes, expected_error
    ):
        """Test add_or_update_keyframes with various invalid parameters"""
        with pytest.raises(LabellerrError, match=expected_error):
            mock_video_project.add_or_update_keyframes(file_id, keyframes)

    def test_add_or_update_keyframes_api_error(self, mock_video_project):
        """Test add_or_update_keyframes when API call fails"""
        mock_video_project.client.make_request = MagicMock(
            side_effect=Exception("API Error")
        )
        keyframes = [KeyFrame(frame_number=0)]

        with pytest.raises(
            LabellerrError, match="Failed to link key frames: API Error"
        ):
            mock_video_project.add_or_update_keyframes("test_file", keyframes)

    @patch("labellerr.core.client.LabellerrClient.make_request")
    def test_add_or_update_keyframes_with_dict_keyframes(
        self, mock_make_request, mock_video_project
    ):
        """Test add_or_update_keyframes with dictionary keyframes instead of KeyFrame objects"""
        mock_make_request.return_value = {"status": "success"}

        keyframes = [
            {
                "frame_number": 0,
                "is_manual": True,
                "method": "manual",
                "source": "manual",
            }
        ]

        result = mock_video_project.add_or_update_keyframes("test_file", keyframes)

        assert result == {"status": "success"}
        args, kwargs = mock_make_request.call_args
        expected_body = {
            "project_id": "test_project_id",
            "file_id": "test_file",
            "keyframes": keyframes,
        }
        assert kwargs["json"] == expected_body


@pytest.mark.unit
class TestDeleteKeyFramesMethod:
    """Unit tests for delete_keyframes method on VideoProject"""

    @patch("labellerr.core.client.LabellerrClient.make_request")
    def test_delete_keyframes_success(self, mock_make_request, mock_video_project):
        """Test successful key frame deletion"""
        # Arrange
        mock_make_request.return_value = {"status": "deleted"}

        # Act
        result = mock_video_project.delete_keyframes("test_file", [0, 10, 20])

        # Assert
        assert result == {"status": "deleted"}
        mock_make_request.assert_called_once()
        args, kwargs = mock_make_request.call_args

        assert args[0] == "POST"
        assert "/actions/delete_keyframes" in args[1]
        assert "project_id=test_project_id" in args[1]
        assert "client_id=test_client_id" in args[1]
        assert "uuid=" in args[1]
        assert kwargs["extra_headers"]["content-type"] == "application/json"

        expected_body = {
            "project_id": "test_project_id",
            "file_id": "test_file",
            "keyframes": [0, 10, 20],
        }
        assert kwargs["json"] == expected_body

    @pytest.mark.parametrize(
        "file_id,keyframes,expected_error",
        [
            # Invalid file_id
            (456, [0, 10], "file_id must be a str"),
            ([], [0, 10], "file_id must be a str"),
            ({}, [0, 10], "file_id must be a str"),
            # Invalid keyframes
            ("test_file", "not_a_list", "keyframes must be a list"),
            ("test_file", 123, "keyframes must be a list"),
            ("test_file", None, "keyframes must be a list"),
        ],
    )
    def test_delete_keyframes_invalid_parameters(
        self, mock_video_project, file_id, keyframes, expected_error
    ):
        """Test delete_keyframes with various invalid parameters"""
        with pytest.raises(LabellerrError, match=expected_error):
            mock_video_project.delete_keyframes(file_id, keyframes)

    def test_delete_keyframes_api_error(self, mock_video_project):
        """Test delete_keyframes when API call fails"""
        mock_video_project.client.make_request = MagicMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(
            LabellerrError, match="Failed to delete key frames: API Error"
        ):
            mock_video_project.delete_keyframes("test_file", [0, 10])

    @patch("labellerr.core.client.LabellerrClient.make_request")
    def test_delete_keyframes_labellerr_error(
        self, mock_make_request, mock_video_project
    ):
        """Test delete_keyframes when LabellerrError is raised"""
        mock_make_request.side_effect = LabellerrError("Custom error")

        with pytest.raises(LabellerrError, match="Custom error"):
            mock_video_project.delete_keyframes("test_file", [0, 10])
