import json
import os
from pathlib import Path
from typing import List

import cv2
from PIL import Image
from pydantic import BaseModel, Field
from scenedetect import AdaptiveDetector, detect

from labellerr.core.base.singleton import Singleton

# ============================================================================
# Exception Classes
# ============================================================================


class PySceneDetectError(Exception):
    """Base exception for all PySceneDetect-related errors.

    This is the parent exception class for all PySceneDetect-specific errors in this module.
    Catching this exception will catch all scene detection-related issues including:
    - Video file errors
    - Scene detection failures
    - Frame extraction failures
    - No scenes detected
    """

    pass


class VideoFileError(PySceneDetectError):
    """Raised when there are issues with the input video file.

    Common causes:
    - File does not exist
    - Path points to a directory instead of a file
    - Unsupported video format
    - File is not readable (permission issues)
    - Video file is corrupted
    """

    pass


class NoScenesError(PySceneDetectError):
    """Raised when no scene changes are found in the video.

    This can occur if:
    - The video is very short (single scene)
    - The video has no significant visual changes
    - The video file is corrupted
    """

    pass


class FrameExtractionError(PySceneDetectError):
    """Raised when frame extraction fails.

    This can occur if:
    - OpenCV cannot read the video
    - Frame number is out of range
    - Video codec is unsupported
    """

    pass


# ============================================================================
# Data Models
# ============================================================================


class SceneFrame(BaseModel):
    """Represents a single extracted frame from a detected scene.

    Attributes:
        frame_path (str): Absolute or relative path to the extracted frame image file.
                         Example: "PyScene_detects/video_id/frames/250.jpg"
        frame_index (int): The 0-indexed frame number in the source video.
                          Example: 250 means this is the 250th frame of the video.
    """

    frame_path: str
    frame_index: int


class DetectionResult(BaseModel):
    """Contains all scene detection results for a video file.

    This model encapsulates the complete output of the scene detection process,
    including metadata about the video and a list of all extracted frames.

    Attributes:
        file_id (str): Unique identifier for the video (filename without extension).
        output_folder (str): Path to the folder containing extracted frames and metadata.
        total_frames (int): Total number of frames in the source video.
        selected_frames (List[SceneFrame]): List of all successfully extracted scene frames.
                                           Each frame includes its path and frame index.
    """

    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame] = Field(default_factory=list)


# ============================================================================
# Main Scene Detection Class
# ============================================================================


class PySceneDetect(Singleton):
    """Scene change detection and frame extraction using PySceneDetect.

    This singleton class provides methods to detect scene changes in video files
    and extract representative frames from each scene. It uses PySceneDetect's
    AdaptiveDetector algorithm for robust scene detection.

    The class implements the Singleton pattern to ensure only one instance exists,
    which is useful for managing video processing and avoiding redundant initialization.

    Attributes:
        SUPPORTED_EXTENSIONS (set): Set of supported video file extensions.

    Example:
        >>> detector = PySceneDetect()
        >>> result = detector.detect_and_extract("video.mp4")
        >>> print(f"Detected {len(result.selected_frames)} scenes")
    """

    # Supported video file extensions
    SUPPORTED_EXTENSIONS = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".flv",
        ".wmv",
        ".webm",
        ".m4v",
    }

    def _validate_video_file(self, video_path: str) -> None:
        """Validate that the video file exists and is a supported format.

        Args:
            video_path: Path to the video file

        Raises:
            VideoFileError: If file doesn't exist or format is unsupported
        """
        path = Path(video_path)

        if not path.exists():
            raise VideoFileError(f"Video file not found: {video_path}")

        if not path.is_file():
            raise VideoFileError(f"Path is not a file: {video_path}")

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise VideoFileError(
                f"Unsupported video format: {path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        # Check if file is readable
        if not os.access(video_path, os.R_OK):
            raise VideoFileError(f"Video file is not readable: {video_path}")

    def detect_and_extract(self, video_path: str) -> DetectionResult:
        """
        Detect scenes and extract representative frames.
        Always extracts the first frame (frame 0) of the video.

        Args:
            video_path: Path to the video file

        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects

        Raises:
            VideoFileError: If video file is invalid or inaccessible
            NoScenesError: If no scene changes are detected
            FrameExtractionError: If frame extraction fails
            PySceneDetectError: If scene detection processing fails
        """
        # Validate input file before processing
        self._validate_video_file(video_path)

        # Extract identifiers from the video path
        # file_id: Video filename without extension (e.g., "video_123")
        # dataset_id: Parent directory name (used for organizing outputs)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))

        # Create hierarchical output folder structure:
        # PyScene_detects/
        #   └── <dataset_id>/
        #       └── <file_id>/
        #           ├── frames/          (extracted frame images)
        #           └── <file_id>_mapping.json  (metadata)
        base_detect_folder = "PyScene_detects"

        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")

        try:
            # ================================================================
            # PHASE 1: Detect scene changes
            # ================================================================
            print("Detecting scene changes...")
            scenes = detect(video_path, AdaptiveDetector())

            # Create all necessary directories (no error if they already exist)
            os.makedirs(frames_folder, exist_ok=True)

            # ================================================================
            # PHASE 2: Extract frames from detected scenes
            # ================================================================
            # Open video for frame extraction
            video = cv2.VideoCapture(video_path)

            if not video.isOpened():
                raise FrameExtractionError(f"Failed to open video file: {video_path}")

            # Get total frames in video
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"Detected {len(scenes)} scene changes")
            print(f"Total frames in video: {total_frames}")

            # Extract and save frames from detected scenes
            scene_frames = []
            frame_numbers_extracted = set()  # Track which frames we've extracted

            for idx, scene in enumerate(scenes, 1):
                # Calculate middle frame number of the scene
                frame_no = (scene[1] - scene[0]).frame_num // 2 + scene[0].frame_num

                # Extract frame
                try:
                    frame = self._get_frame(video, frame_no)

                    # Save frame with frame number as filename inside frames folder
                    frame_filename = f"{frame_no}.jpg"
                    frame_path = os.path.join(frames_folder, frame_filename)
                    frame.save(frame_path)

                    # Create SceneFrame object
                    scene_frame = SceneFrame(
                        frame_path=frame_path, frame_index=frame_no
                    )
                    scene_frames.append(scene_frame)
                    frame_numbers_extracted.add(frame_no)

                    # Progress update: Print every 10 scenes to avoid console spam
                    if idx % 10 == 0:
                        print(f"Extracted {idx}/{len(scenes)} scene frames...")
                except Exception as e:
                    # Log warning but continue with other frames (graceful degradation)
                    print(f"Warning: Failed to extract frame {frame_no}: {e}")
                    continue

            # ================================================================
            # PHASE 3: Always extract first frame (frame 0)
            # ================================================================
            # Ensure frame 0 is always extracted, even if it's not a scene change
            if 0 not in frame_numbers_extracted:
                try:
                    print("Extracting first frame (frame 0)...")
                    frame = self._get_frame(video, 0)

                    frame_filename = "0.jpg"
                    frame_path = os.path.join(frames_folder, frame_filename)
                    frame.save(frame_path)

                    # Insert at the beginning of the list
                    scene_frame = SceneFrame(frame_path=frame_path, frame_index=0)
                    scene_frames.insert(0, scene_frame)
                except Exception as e:
                    print(f"Warning: Failed to extract first frame: {e}")

            video.release()

            # Validate that at least one frame was successfully extracted
            if not scene_frames:
                raise NoScenesError(
                    f"No scenes detected and failed to extract first frame from video: {video_path}"
                )

            # Final success message with extraction statistics
            print(
                f"Successfully extracted {len(scene_frames)} frames to {frames_folder}"
            )

            # Create result
            result = DetectionResult(
                file_id=file_id,
                output_folder=output_folder,
                total_frames=total_frames,
                selected_frames=scene_frames,
            )

            # Save JSON mapping
            self._save_json_mapping(result, output_folder, file_id)

            return result

        except (VideoFileError, NoScenesError, FrameExtractionError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise PySceneDetectError(
                f"Unexpected error during scene detection: {e}"
            ) from e

    def _get_frame(self, video: cv2.VideoCapture, frame_no: int) -> Image.Image:
        """
        Extract a specific frame from video.

        Args:
            video: OpenCV video capture object
            frame_no: Frame number to extract

        Returns:
            PIL Image of the frame

        Raises:
            FrameExtractionError: If frame extraction fails
        """
        try:
            video.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = video.read()

            if not ret or frame is None:
                raise FrameExtractionError(f"Failed to read frame {frame_no}")

            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        except Exception as e:
            raise FrameExtractionError(f"Error extracting frame {frame_no}: {e}") from e

    def _save_json_mapping(
        self, result: DetectionResult, output_folder: str, file_id: str
    ) -> None:
        """
        Save JSON mapping of file_id to extracted scenes.

        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file
            file_id: Unique identifier for the video

        Raises:
            PySceneDetectError: If JSON file cannot be saved
        """
        try:
            # Use Pydantic's model_dump
            result_dict = result.model_dump()
            result_dict["total_selected_frames"] = len(result.selected_frames)

            json_path = os.path.join(output_folder, f"{file_id}_mapping.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)

            print(f"JSON mapping saved to: {json_path}")
        except (IOError, OSError) as e:
            raise PySceneDetectError(
                f"Failed to save JSON mapping to {json_path}: {e}"
            ) from e


if __name__ == "__main__":
    video_path = r"D:\Professional\Labellerr_SDK\SDKPython\labellerr\notebooks\Labellerr_datasets\354681d3-034a-4d66-b070-365f4bd11d8a\2a8d96ca-9161-4dee-ad3b-a5faf301bc6c.mp4"

    detector = PySceneDetect()
    result = detector.detect_and_extract(video_path)
