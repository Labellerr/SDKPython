import json
import os
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field
from skimage.metrics import structural_similarity as ssim

from labellerr.core.base.singleton import Singleton

# ============================================================================
# Exception Classes
# ============================================================================


class SSIMDetectError(Exception):
    """Base exception for all SSIM detection-related errors.

    This is the parent exception class for all SSIM-specific errors in this module.
    Catching this exception will catch all SSIM detection-related issues including:
    - Video file errors
    - Frame extraction failures
    - SSIM calculation errors
    """

    pass


class VideoFileError(SSIMDetectError):
    """Raised when there are issues with the input video file.

    Common causes:
    - File does not exist
    - Path points to a directory instead of a file
    - Unsupported video format
    - File is not readable (permission issues)
    - Video file is corrupted
    - OpenCV cannot open the video
    """

    pass


class FrameExtractionError(SSIMDetectError):
    """Raised when frame extraction fails.

    This can occur if:
    - OpenCV cannot read the video
    - Frame number is out of range
    - Video codec is unsupported
    - Frame data is corrupted
    """

    pass


# ============================================================================
# Data Models
# ============================================================================


class SceneFrame(BaseModel):
    """Represents a single extracted frame from a detected scene.

    Attributes:
        frame_path (str): Absolute or relative path to the extracted frame image file.
                         Example: "SSIM_detects/video_id/frames/250.jpg"
        frame_index (int): The 0-indexed frame number in the source video.
                          Example: 250 means this is the 250th frame of the video.
        ssim_score (float): The SSIM score that triggered this frame extraction.
                           Range: 0.0 to 1.0 (lower = more different from previous frame)
    """

    frame_path: str
    frame_index: int
    ssim_score: float


class DetectionResult(BaseModel):
    """Contains all SSIM detection results for a video file.

    This model encapsulates the complete output of the SSIM detection process,
    including metadata about the video and a list of all extracted frames.

    Attributes:
        file_id (str): Unique identifier for the video (filename without extension).
        output_folder (str): Path to the folder containing extracted frames and metadata.
        total_frames (int): Total number of frames in the source video.
        selected_frames (List[SceneFrame]): List of all successfully extracted scene frames.
                                           Each frame includes its path, frame index, and SSIM score.
    """

    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame] = Field(default_factory=list)


# ============================================================================
# Main SSIM Detection Class
# ============================================================================


class SSIMSceneDetect(Singleton):
    """SSIM-based scene change detection and frame extraction.

    This singleton class provides methods to detect scene changes in video files
    using SSIM (Structural Similarity Index) metric. SSIM measures perceptual
    similarity between frames, making it effective for scene change detection.

    The class implements the Singleton pattern to ensure only one instance exists,
    which is useful for managing video processing and avoiding redundant initialization.

    Attributes:
        SUPPORTED_EXTENSIONS (set): Set of supported video file extensions.

    Example:
        >>> detector = SSIMSceneDetect()
        >>> result = detector.detect_and_extract("video.mp4", threshold=0.6)
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

    def detect_and_extract(
        self, video_path: str, threshold: float = 0.3, resize_dim: tuple = (320, 240)
    ) -> DetectionResult:
        """
        Detect scenes using SSIM and extract representative frames.
        Always extracts the first frame (frame 0) of the video.

        Args:
            video_path: Path to the video file
            threshold: SSIM threshold for scene detection (lower = stricter, default: 0.3)
                      Range: 0.0 to 1.0. Values below threshold indicate scene change.
            resize_dim: Dimensions to resize frames for SSIM calculation (default: (320, 240))
                       Smaller dimensions = faster computation

        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects

        Raises:
            VideoFileError: If video file is invalid or inaccessible
            FrameExtractionError: If frame extraction fails
            SSIMDetectError: If SSIM detection processing fails
        """
        # Validate input file before processing
        self._validate_video_file(video_path)

        # Extract identifiers from the video path
        # file_id: Video filename without extension (e.g., "video_123")
        # dataset_id: Parent directory name (used for organizing outputs)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))

        # Create hierarchical output folder structure:
        # SSIM_detects/
        #   └── <dataset_id>/
        #       └── <file_id>/
        #           ├── frames/          (extracted frame images)
        #           └── <file_id>_mapping.json  (metadata)
        base_detect_folder = "SSIM_detects"
        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")

        # Create all necessary directories (no error if they already exist)
        os.makedirs(frames_folder, exist_ok=True)

        try:
            # ================================================================
            # PHASE 1: Open video and validate
            # ================================================================
            video = cv2.VideoCapture(video_path)

            if not video.isOpened():
                raise VideoFileError(f"Cannot open video: {video_path}")

            # Get total frames in video
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"Processing video: {video_path}")
            print(f"Total frames: {total_frames}")
            print(f"SSIM threshold: {threshold}")

            # ================================================================
            # PHASE 2: Extract first frame (always included)
            # ================================================================
            success, prev_frame = video.read()
            if not success:
                video.release()
                raise FrameExtractionError(
                    f"Cannot read first frame from: {video_path}"
                )

            scene_frames: List[SceneFrame] = []
            frame_count = 0

            # Always save first frame with SSIM score of 1.0 (perfect match with itself)
            self._save_frame(prev_frame, frame_count, 1.0, scene_frames, frames_folder)
            print("Saved first frame (frame 0)")

            # ================================================================
            # PHASE 3: Process remaining frames with SSIM detection
            # ================================================================
            while True:
                success, curr_frame = video.read()
                if not success:
                    break

                frame_count += 1

                try:
                    # Calculate SSIM between current and previous frame
                    ssim_score = self._calculate_ssim(
                        prev_frame, curr_frame, resize_dim
                    )

                    # If SSIM is below threshold, it's a scene change
                    if ssim_score < threshold:
                        self._save_frame(
                            curr_frame,
                            frame_count,
                            ssim_score,
                            scene_frames,
                            frames_folder,
                        )
                        print(
                            f"Saved keyframe {len(scene_frames) - 1} at frame {frame_count} (SSIM: {ssim_score:.3f})"
                        )
                        prev_frame = curr_frame
                    elif frame_count % 100 == 0:
                        # Progress update every 100 frames
                        print(
                            f"Frame {frame_count}/{total_frames}: SSIM = {ssim_score:.3f} (threshold: {threshold})"
                        )
                except Exception as e:
                    # Log warning but continue with other frames (graceful degradation)
                    print(f"Warning: Failed to process frame {frame_count}: {e}")
                    continue

            video.release()

            # Validate that at least one frame was successfully extracted
            if not scene_frames:
                raise SSIMDetectError(
                    f"No frames extracted from video: {video_path}. "
                    "All frame extractions failed."
                )

            # Final success message with extraction statistics
            print(
                f"\nSuccessfully extracted {len(scene_frames)} frames from {frame_count + 1} total frames"
            )

            # Create result
            result = DetectionResult(
                file_id=file_id,
                output_folder=output_folder,
                total_frames=total_frames,
                selected_frames=scene_frames,
            )

            # Save JSON mapping
            self._save_json_mapping(
                result, output_folder, file_id, threshold, resize_dim
            )

            return result

        except (VideoFileError, FrameExtractionError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise SSIMDetectError(f"Unexpected error during SSIM detection: {e}") from e

    def _calculate_ssim(
        self, frame1: np.ndarray, frame2: np.ndarray, resize_dim: tuple
    ) -> float:
        """
        Calculate SSIM score between two frames.

        Args:
            frame1: First frame (BGR format from OpenCV)
            frame2: Second frame (BGR format from OpenCV)
            resize_dim: Dimensions to resize frames for SSIM calculation

        Returns:
            SSIM score (0-1, where 1 is identical, 0 is completely different)

        Raises:
            SSIMDetectError: If SSIM calculation fails
        """
        try:
            # Resize frames for faster computation
            # Convert to grayscale for SSIM calculation
            gray1 = cv2.cvtColor(cv2.resize(frame1, resize_dim), cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(cv2.resize(frame2, resize_dim), cv2.COLOR_BGR2GRAY)

            # Calculate SSIM using scikit-image
            # full=True returns the full SSIM image, we only need the score
            score, _ = ssim(gray1, gray2, full=True)

            return float(score)
        except Exception as e:
            raise SSIMDetectError(f"Failed to calculate SSIM: {e}") from e

    def _save_frame(
        self,
        frame: np.ndarray,
        frame_no: int,
        ssim_score: float,
        scene_frames: List[SceneFrame],
        frames_folder: str,
    ) -> None:
        """
        Save a frame to disk and add to scene_frames list.

        Args:
            frame: Frame to save (BGR format from OpenCV)
            frame_no: Frame number (0-indexed)
            ssim_score: SSIM score that triggered this frame extraction
            scene_frames: List to append SceneFrame object to
            frames_folder: Folder to save the frame

        Raises:
            FrameExtractionError: If frame saving fails
        """
        try:
            # Convert BGR (OpenCV format) to RGB (PIL format)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)

            # Save frame with frame number as filename
            frame_filename = f"{frame_no}.jpg"
            frame_path = os.path.join(frames_folder, frame_filename)
            pil_image.save(frame_path)

            # Create SceneFrame object with SSIM score
            scene_frame = SceneFrame(
                frame_path=frame_path, frame_index=frame_no, ssim_score=ssim_score
            )
            scene_frames.append(scene_frame)
        except Exception as e:
            raise FrameExtractionError(f"Failed to save frame {frame_no}: {e}") from e

    def _save_json_mapping(
        self,
        result: DetectionResult,
        output_folder: str,
        file_id: str,
        threshold: float,
        resize_dim: tuple,
    ) -> None:
        """
        Save JSON mapping of file_id to extracted scenes.

        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file
            file_id: Unique identifier for the video
            threshold: SSIM threshold used for detection
            resize_dim: Resize dimensions used for SSIM calculation

        Raises:
            SSIMDetectError: If JSON file cannot be saved
        """
        try:
            # Use Pydantic's model_dump
            result_dict = result.model_dump()
            result_dict["total_selected_frames"] = len(result.selected_frames)
            result_dict["threshold"] = threshold
            result_dict["resize_dim"] = resize_dim

            json_path = os.path.join(output_folder, f"{file_id}_mapping.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)

            print(f"JSON mapping saved to: {json_path}")
        except (IOError, OSError) as e:
            raise SSIMDetectError(
                f"Failed to save JSON mapping to {json_path}: {e}"
            ) from e


if __name__ == "__main__":
    # Example usage
    video_path = r"D:\Professional\Labellerr_SDK\SDKPython\labellerr\notebooks\Labellerr_datasets\354681d3-034a-4d66-b070-365f4bd11d8a\2a8d96ca-9161-4dee-ad3b-a5faf301bc6c.mp4"

    # Get singleton instance
    detector = SSIMSceneDetect()

    # Detect and extract frames
    result = detector.detect_and_extract(
        video_path=video_path,
        threshold=0.6,  # Lower value = more sensitive to changes
        resize_dim=(320, 240),
    )

    print("\nDetection complete!")
    print(f"Total frames extracted: {len(result.selected_frames)}")
    print(f"Output folder: {result.output_folder}")
