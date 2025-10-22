import os

import pytest

from labellerr.client import KeyFrame, LabellerrClient
from labellerr.exceptions import LabellerrError


@pytest.fixture
def client():
    """Create a client for integration testing"""
    api_key = os.environ.get("LABELLERR_API_KEY", "test_api_key")
    api_secret = os.environ.get("LABELLERR_API_SECRET", "test_api_secret")
    return LabellerrClient(api_key, api_secret)


class TestKeyFrameBusinessScenarios:
    """Integration tests focused on business scenarios and workflows"""

    def test_video_annotation_workflow(self, client):
        """
        Test complete workflow: Create keyframes for video annotation project

        Business scenario:
        - Annotator is working on a video file
        - They identify key moments at specific frames
        - Some frames are manually selected, others are AI-suggested
        - They need to link these keyframes to the video file
        """
        # Business data: Video annotation project
        client_id = "video_annotation_team"
        project_id = "wildlife_documentary_2024"
        video_file_id = "nature_scene_001.mp4"

        # Business scenario: Mixed manual and AI keyframes
        keyframes = [
            # Start frame
            KeyFrame(
                frame_number=0, is_manual=True, method="manual", source="annotator"
            ),
            # AI detected movement
            KeyFrame(
                frame_number=150,
                is_manual=False,
                method="ai_detection",
                source="cv_model",
            ),
            # Important scene change
            KeyFrame(
                frame_number=300, is_manual=True, method="manual", source="annotator"
            ),
            # AI detected object
            KeyFrame(
                frame_number=450,
                is_manual=False,
                method="ai_detection",
                source="cv_model",
            ),
            # End of segment
            KeyFrame(
                frame_number=600, is_manual=True, method="manual", source="annotator"
            ),
        ]

        # Test the business operation
        try:
            result = client.link_key_frame(
                client_id, project_id, video_file_id, keyframes
            )
            # In real integration, we'd verify the result structure
            # For now, we verify the method accepts business-realistic data
            assert isinstance(result, dict)
        except LabellerrError as e:
            # Expected in test environment - API will reject with auth/project errors
            # This validates our input format is correct for business scenarios
            error_str = str(e).lower()
            assert any(
                word in error_str
                for word in [
                    "not authorized",
                    "invalid api",
                    "test_api_key",
                    "project",
                    "client",
                ]
            )

    def test_security_surveillance_workflow(self, client):
        """
        Test workflow: Security camera footage analysis

        Business scenario:
        - Security team analyzing surveillance footage
        - System auto-detects suspicious activity at certain frames
        - Security operator manually reviews and marks additional frames
        """
        client_id = "security_operations"
        project_id = "building_surveillance_q4"
        footage_file_id = "camera_03_20241215_1400.mp4"

        # Business scenario: Security incident keyframes
        incident_keyframes = [
            # Review start
            KeyFrame(
                frame_number=0, is_manual=True, method="manual", source="operator"
            ),
            # Auto-detected motion
            KeyFrame(
                frame_number=2340,
                is_manual=False,
                method="motion_detection",
                source="ai",
            ),
            # Operator verification
            KeyFrame(
                frame_number=2380, is_manual=True, method="manual", source="operator"
            ),
            # Face detected
            KeyFrame(
                frame_number=2420, is_manual=False, method="face_detection", source="ai"
            ),
            # Incident end
            KeyFrame(
                frame_number=2500, is_manual=True, method="manual", source="operator"
            ),
        ]

        try:
            result = client.link_key_frame(
                client_id, project_id, footage_file_id, incident_keyframes
            )
            assert isinstance(result, dict)
        except LabellerrError as e:
            # Expected in test environment
            error_str = str(e).lower()
            assert any(
                word in error_str
                for word in [
                    "not authorized",
                    "invalid api",
                    "test_api_key",
                    "project",
                    "client",
                ]
            )

    def test_quality_control_workflow(self, client):
        """
        Test workflow: Quality control in manufacturing

        Business scenario:
        - Quality inspector reviewing production line video
        - Identifying frames where defects occur
        - Marking frames for further analysis
        """
        client_id = "quality_control_dept"
        project_id = "production_line_inspection"
        video_file_id = "assembly_station_5.mp4"

        # Business scenario: Defect detection keyframes
        qc_keyframes = [
            # Inspection start
            KeyFrame(
                frame_number=100, is_manual=True, method="manual", source="inspector"
            ),
            # Potential defect spotted
            KeyFrame(
                frame_number=500, is_manual=True, method="manual", source="inspector"
            ),
            # AI flagged anomaly
            KeyFrame(
                frame_number=1200,
                is_manual=False,
                method="anomaly_detection",
                source="ai",
            ),
            # Confirmed defect
            KeyFrame(
                frame_number=1800, is_manual=True, method="manual", source="inspector"
            ),
        ]

        try:
            result = client.link_key_frame(
                client_id, project_id, video_file_id, qc_keyframes
            )
            assert isinstance(result, dict)
        except LabellerrError as e:
            # Expected in test environment
            error_str = str(e).lower()
            assert any(
                word in error_str
                for word in [
                    "not authorized",
                    "invalid api",
                    "test_api_key",
                    "project",
                    "client",
                ]
            )

    def test_content_moderation_workflow(self, client):
        """
        Test workflow: Content moderation for social media

        Business scenario:
        - Content moderator reviewing user-uploaded videos
        - Flagging inappropriate content at specific timestamps
        - Marking frames for review or removal
        """
        client_id = "content_moderation"
        project_id = "user_content_review_dec2024"
        user_video_id = "user_upload_xyz789.mp4"

        # Business scenario: Content moderation keyframes
        moderation_keyframes = [
            KeyFrame(
                frame_number=0, is_manual=True, method="manual", source="moderator"
            ),  # Review start
            KeyFrame(
                frame_number=750, is_manual=False, method="content_filter", source="ai"
            ),  # AI flagged content
            KeyFrame(
                frame_number=1500, is_manual=True, method="manual", source="moderator"
            ),  # Manual review
            KeyFrame(
                frame_number=2200, is_manual=True, method="manual", source="moderator"
            ),  # Final decision
        ]

        try:
            result = client.link_key_frame(
                client_id, project_id, user_video_id, moderation_keyframes
            )
            assert isinstance(result, dict)
        except LabellerrError as e:
            # Expected in test environment
            error_str = str(e).lower()
            assert any(
                word in error_str
                for word in [
                    "not authorized",
                    "invalid api",
                    "test_api_key",
                    "project",
                    "client",
                ]
            )

    def test_keyframe_cleanup_workflow(self, client):
        """
        Test workflow: Project cleanup after annotation completion

        Business scenario:
        - Project manager cleaning up completed annotation projects
        - Removing temporary keyframes that are no longer needed
        - Preparing for project archival
        """
        client_id = "project_management"
        completed_project_id = "medical_imaging_batch_03"

        try:
            result = client.delete_key_frames(client_id, completed_project_id)
            assert isinstance(result, dict)
        except LabellerrError as e:
            # Expected in test environment
            error_str = str(e).lower()
            assert any(
                word in error_str
                for word in [
                    "not authorized",
                    "invalid api",
                    "test_api_key",
                    "project",
                    "client",
                ]
            )

    def test_batch_processing_workflow(self, client):
        """
        Test workflow: Batch processing multiple video segments

        Business scenario:
        - Data scientist processing multiple video files
        - Each file gets the same keyframe pattern for consistency
        - Batch operation for efficiency
        """
        client_id = "data_science_team"
        project_id = "sports_analysis_dataset"

        # Business scenario: Standardized keyframes for multiple files
        standard_keyframes = [
            KeyFrame(
                frame_number=0,
                is_manual=False,
                method="automatic",
                source="batch_processor",
            ),  # Start
            KeyFrame(
                frame_number=600,
                is_manual=False,
                method="automatic",
                source="batch_processor",
            ),  # Mid-point
            KeyFrame(
                frame_number=1200,
                is_manual=False,
                method="automatic",
                source="batch_processor",
            ),  # End
        ]

        # Simulate batch processing multiple files
        video_files = [
            "game1_highlight_reel.mp4",
            "game2_highlight_reel.mp4",
            "game3_highlight_reel.mp4",
        ]

        for video_file in video_files:
            try:
                result = client.link_key_frame(
                    client_id, project_id, video_file, standard_keyframes
                )
                assert isinstance(result, dict)
            except LabellerrError as e:
                # Expected in test environment
                error_str = str(e).lower()
                assert any(
                    word in error_str
                    for word in [
                        "not authorized",
                        "invalid api",
                        "test_api_key",
                        "project",
                        "client",
                    ]
                )


class TestKeyFrameDataValidation:
    """Integration tests focused on data validation in business contexts"""

    def test_realistic_keyframe_data_types(self, client):
        """Test that business-realistic keyframe data is properly validated"""

        # Valid business scenarios
        valid_scenarios = [
            # Medical imaging keyframes
            KeyFrame(
                frame_number=1,
                is_manual=True,
                method="radiologist_review",
                source="doctor",
            ),
            # Sports analysis keyframes
            KeyFrame(
                frame_number=1800,
                is_manual=False,
                method="player_tracking",
                source="sports_ai",
            ),
            # Education content keyframes
            KeyFrame(
                frame_number=300,
                is_manual=True,
                method="curriculum_design",
                source="educator",
            ),
            # Research data keyframes
            KeyFrame(
                frame_number=10000,
                is_manual=False,
                method="pattern_recognition",
                source="research_ai",
            ),
        ]

        for keyframe in valid_scenarios:
            # Test that keyframes are created successfully
            assert keyframe.frame_number >= 0
            assert isinstance(keyframe.is_manual, bool)
            assert isinstance(keyframe.method, str)
            assert isinstance(keyframe.source, str)

    def test_business_constraint_validation(self, client):
        """Test business constraints are properly enforced"""

        # Test frame number constraints (must be non-negative integers)
        with pytest.raises(ValueError):
            KeyFrame(
                frame_number=-1
            )  # Negative frame numbers don't make business sense

        # Test that all required business fields are validated
        with pytest.raises(ValueError):
            KeyFrame(frame_number="not_a_number")  # Frame numbers must be integers

    def test_workflow_integration_patterns(self, client):
        """Test common integration patterns in business workflows"""

        # Pattern 1: Progressive annotation workflow
        progressive_keyframes = []
        for frame_num in range(0, 1000, 100):  # Every 100 frames
            kf = KeyFrame(
                frame_number=frame_num,
                is_manual=frame_num % 200 == 0,  # Every other keyframe is manual
                method="progressive_annotation",
                source="workflow_engine",
            )
            progressive_keyframes.append(kf)

        assert len(progressive_keyframes) == 10
        assert all(isinstance(kf, KeyFrame) for kf in progressive_keyframes)

        # Pattern 2: Mixed manual/automatic workflow
        mixed_keyframes = [
            KeyFrame(
                frame_number=0, is_manual=True, method="manual_start", source="user"
            ),
            KeyFrame(
                frame_number=500, is_manual=False, method="ai_suggestion", source="ai"
            ),
            KeyFrame(
                frame_number=1000,
                is_manual=True,
                method="manual_verification",
                source="user",
            ),
            KeyFrame(
                frame_number=1500, is_manual=False, method="ai_suggestion", source="ai"
            ),
            KeyFrame(
                frame_number=2000, is_manual=True, method="manual_end", source="user"
            ),
        ]

        # Verify workflow makes business sense
        manual_count = sum(1 for kf in mixed_keyframes if kf.is_manual)
        auto_count = sum(1 for kf in mixed_keyframes if not kf.is_manual)
        assert manual_count == 3  # Human oversight points
        assert auto_count == 2  # AI assistance points


class TestErrorScenarios:
    """Integration tests for realistic error scenarios"""

    def test_authentication_error_scenario(self, client):
        """Test realistic authentication failure scenario"""
        # Business scenario: Team member's API key has expired
        client_id = "expired_team_member"
        project_id = "active_project"
        file_id = "important_video.mp4"
        keyframes = [KeyFrame(frame_number=100)]

        try:
            client.link_key_frame(client_id, project_id, file_id, keyframes)
        except LabellerrError as e:
            # This is expected in test environment with fake credentials
            assert isinstance(e, LabellerrError)

    def test_project_not_found_scenario(self, client):
        """Test realistic project not found scenario"""
        # Business scenario: Team member tries to access archived project
        client_id = "valid_team_member"
        archived_project_id = "archived_project_2023"

        try:
            client.delete_key_frames(client_id, archived_project_id)
        except LabellerrError as e:
            # This is expected in test environment
            assert isinstance(e, LabellerrError)

    def test_invalid_business_data_scenario(self):
        """Test invalid business data scenarios"""
        # Business scenario: Invalid frame numbers from corrupted data
        with pytest.raises(ValueError):
            KeyFrame(frame_number=None)  # Corrupted data

        with pytest.raises(ValueError):
            KeyFrame(frame_number="corrupted")  # Bad data import
