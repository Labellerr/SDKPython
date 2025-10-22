from unittest.mock import Mock, patch

import pytest

from labellerr.client import KeyFrame, LabellerrClient, validate_params
from labellerr.exceptions import LabellerrError


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
        assert keyframe.__dict__ == expected

    @pytest.mark.parametrize(
        "invalid_params,expected_error",
        [
            # Invalid frame_number
            ({"frame_number": "not_an_int"}, "frame_number must be an integer"),
            ({"frame_number": 1.5}, "frame_number must be an integer"),
            ({"frame_number": None}, "frame_number must be an integer"),
            # Invalid is_manual
            (
                {"frame_number": 1, "is_manual": "not_a_bool"},
                "is_manual must be a boolean",
            ),
            ({"frame_number": 1, "is_manual": 1}, "is_manual must be a boolean"),
            # Invalid method
            ({"frame_number": 1, "method": 123}, "method must be a string"),
            ({"frame_number": 1, "method": []}, "method must be a string"),
            # Invalid source
            ({"frame_number": 1, "source": 456}, "source must be a string"),
            ({"frame_number": 1, "source": {}}, "source must be a string"),
        ],
    )
    def test_keyframe_invalid_creation(self, invalid_params, expected_error):
        """Test KeyFrame creation with invalid parameters"""
        with pytest.raises(ValueError, match=expected_error):
            KeyFrame(**invalid_params)


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
    client = LabellerrClient("test_api_key", "test_api_secret")
    client.base_url = "https://api.labellerr.com"
    return client


class TestLinkKeyFrameMethod:
    """Unit tests for link_key_frame method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    @patch("labellerr.client.LabellerrClient._handle_response")
    def test_link_key_frame_success(
        self, mock_handle_response, mock_make_request, mock_client
    ):
        """Test successful key frame linking"""
        # Arrange
        mock_response = Mock()
        mock_make_request.return_value = mock_response
        mock_handle_response.return_value = {"status": "success"}

        keyframes = [
            KeyFrame(frame_number=0),
            KeyFrame(frame_number=10, is_manual=False),
        ]

        # Act
        result = mock_client.link_key_frame(
            "test_client", "test_project", "test_file", keyframes
        )

        # Assert
        assert result == {"status": "success"}
        mock_make_request.assert_called_once()
        args, kwargs = mock_make_request.call_args

        assert args[0] == "POST"
        assert "/actions/add_update_keyframes" in args[1]
        assert "client_id=test_client" in args[1]
        assert kwargs["headers"]["content-type"] == "application/json"

        expected_body = {
            "project_id": "test_project",
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
        "client_id,project_id,file_id,keyframes,expected_error",
        [
            # Invalid client_id
            (
                123,
                "test_project",
                "test_file",
                [KeyFrame(frame_number=0)],
                "client_id must be a str",
            ),
            (
                None,
                "test_project",
                "test_file",
                [KeyFrame(frame_number=0)],
                "client_id must be a str",
            ),
            (
                [],
                "test_project",
                "test_file",
                [KeyFrame(frame_number=0)],
                "client_id must be a str",
            ),
            # Invalid project_id
            (
                "test_client",
                456,
                "test_file",
                [KeyFrame(frame_number=0)],
                "project_id must be a str",
            ),
            (
                "test_client",
                None,
                "test_file",
                [KeyFrame(frame_number=0)],
                "project_id must be a str",
            ),
            # Invalid file_id
            (
                "test_client",
                "test_project",
                789,
                [KeyFrame(frame_number=0)],
                "file_id must be a str",
            ),
            (
                "test_client",
                "test_project",
                {},
                [KeyFrame(frame_number=0)],
                "file_id must be a str",
            ),
            # Invalid keyframes
            (
                "test_client",
                "test_project",
                "test_file",
                "not_a_list",
                "key_frames must be a list",
            ),
            (
                "test_client",
                "test_project",
                "test_file",
                123,
                "key_frames must be a list",
            ),
            (
                "test_client",
                "test_project",
                "test_file",
                None,
                "key_frames must be a list",
            ),
        ],
    )
    def test_link_key_frame_invalid_parameters(
        self, mock_client, client_id, project_id, file_id, keyframes, expected_error
    ):
        """Test link_key_frame with various invalid parameters"""
        with pytest.raises(LabellerrError, match=expected_error):
            mock_client.link_key_frame(client_id, project_id, file_id, keyframes)

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_link_key_frame_api_error(self, mock_make_request, mock_client):
        """Test link_key_frame when API call fails"""
        mock_make_request.side_effect = Exception("API Error")
        keyframes = [KeyFrame(frame_number=0)]

        with pytest.raises(
            LabellerrError, match="Failed to link key frames: API Error"
        ):
            mock_client.link_key_frame(
                "test_client", "test_project", "test_file", keyframes
            )

    @patch("labellerr.client.LabellerrClient._make_request")
    @patch("labellerr.client.LabellerrClient._handle_response")
    def test_link_key_frame_with_dict_keyframes(
        self, mock_handle_response, mock_make_request, mock_client
    ):
        """Test link_key_frame with dictionary keyframes instead of KeyFrame objects"""
        mock_response = Mock()
        mock_make_request.return_value = mock_response
        mock_handle_response.return_value = {"status": "success"}

        keyframes = [
            {
                "frame_number": 0,
                "is_manual": True,
                "method": "manual",
                "source": "manual",
            }
        ]

        result = mock_client.link_key_frame(
            "test_client", "test_project", "test_file", keyframes
        )

        assert result == {"status": "success"}
        args, kwargs = mock_make_request.call_args
        expected_body = {
            "project_id": "test_project",
            "file_id": "test_file",
            "keyframes": keyframes,
        }
        assert kwargs["json"] == expected_body


class TestDeleteKeyFramesMethod:
    """Unit tests for delete_key_frames method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    @patch("labellerr.client.LabellerrClient._handle_response")
    def test_delete_key_frames_success(
        self, mock_handle_response, mock_make_request, mock_client
    ):
        """Test successful key frame deletion"""
        # Arrange
        mock_response = Mock()
        mock_make_request.return_value = mock_response
        mock_handle_response.return_value = {"status": "deleted"}

        # Act
        result = mock_client.delete_key_frames("test_client", "test_project")

        # Assert
        assert result == {"status": "deleted"}
        mock_make_request.assert_called_once()
        args, _ = mock_make_request.call_args

        assert args[0] == "POST"
        assert "/actions/delete_keyframes" in args[1]
        assert "project_id=test_project" in args[1]
        assert "client_id=test_client" in args[1]
        assert "uuid=" in args[1]

    @pytest.mark.parametrize(
        "client_id,project_id,expected_error",
        [
            # Invalid client_id
            (123, "test_project", "client_id must be a str"),
            (None, "test_project", "client_id must be a str"),
            ([], "test_project", "client_id must be a str"),
            ({}, "test_project", "client_id must be a str"),
            # Invalid project_id
            ("test_client", 456, "project_id must be a str"),
            ("test_client", None, "project_id must be a str"),
            ("test_client", [], "project_id must be a str"),
            ("test_client", {}, "project_id must be a str"),
        ],
    )
    def test_delete_key_frames_invalid_parameters(
        self, mock_client, client_id, project_id, expected_error
    ):
        """Test delete_key_frames with various invalid parameters"""
        with pytest.raises(LabellerrError, match=expected_error):
            mock_client.delete_key_frames(client_id, project_id)

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_delete_key_frames_api_error(self, mock_make_request, mock_client):
        """Test delete_key_frames when API call fails"""
        mock_make_request.side_effect = Exception("API Error")

        with pytest.raises(
            LabellerrError, match="Failed to delete key frames: API Error"
        ):
            mock_client.delete_key_frames("test_client", "test_project")

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_delete_key_frames_labellerr_error(self, mock_make_request, mock_client):
        """Test delete_key_frames when LabellerrError is raised"""
        mock_make_request.side_effect = LabellerrError("Custom error")

        with pytest.raises(LabellerrError, match="Custom error"):
            mock_client.delete_key_frames("test_client", "test_project")
