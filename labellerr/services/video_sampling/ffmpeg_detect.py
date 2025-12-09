import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from labellerr.core.base.singleton import Singleton


class FFMPEGError(Exception):
    """Base exception for FFMPEG-related errors."""

    pass


class FFMPEGNotFoundError(FFMPEGError):
    """Raised when FFMPEG is not installed or not found in PATH."""

    pass


class VideoFileError(FFMPEGError):
    """Raised when there are issues with the video file."""

    pass


class NoKeyframesError(FFMPEGError):
    """Raised when no I-frames are found in the video."""

    pass


class SceneFrame(BaseModel):
    """Represents an extracted keyframe."""

    frame_path: str
    frame_index: int


class DetectionResult(BaseModel):
    """Contains all extraction results for a video."""

    file_id: str
    output_folder: str
    selected_frames: List[SceneFrame] = Field(default_factory=list)


class FFMPEGSceneDetect(Singleton):
    """Keyframe extraction from videos using FFMPEG (Singleton)."""

    # Supported video extensions
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

    def __init__(self):
        """Initialize and verify FFMPEG is available."""
        super().__init__()
        self._verify_ffmpeg()

    def _verify_ffmpeg(self) -> None:
        """Verify that FFMPEG is installed and accessible."""
        if not shutil.which("ffmpeg"):
            raise FFMPEGNotFoundError(
                "FFMPEG is not installed or not found in PATH. "
                "Please install FFMPEG from https://ffmpeg.org/download.html"
            )

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
        Extract keyframes from video and save to detects folder structure.
        Frames are saved with pattern: video_name+frame_X.jpg (e.g., video_name+frame_5.jpg for frame 5).

        Args:
            video_path: Path to the video file

        Returns:
            DetectionResult containing file_id, output_folder, and list of SceneFrame objects

        Raises:
            VideoFileError: If video file is invalid or inaccessible
            NoKeyframesError: If no I-frames are found in the video
            FFMPEGError: If FFMPEG processing fails
        """
        # Validate input file before processing
        self._validate_video_file(video_path)

        # Extract identifiers from the video path
        # file_id: Video filename without extension (e.g., "video_123")
        # dataset_id: Parent directory name (used for organizing outputs)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))

        # Create hierarchical output folder structure:
        # FFMPEG_detects/
        #   └── <dataset_id>/
        #       └── <file_id>/
        #           ├── frames/          (extracted frame images)
        #           └── <file_id>_mapping.json  (metadata)
        base_detect_folder = "FFMPEG_detects"

        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")

        # Create all necessary directories (no error if they already exist)
        os.makedirs(frames_folder, exist_ok=True)

        try:
            # ================================================================
            # PHASE 1: Identify I-frame positions
            # ================================================================
            # First pass: Scan the video to find all I-frame positions
            # This is done WITHOUT extracting frames to get the complete list
            # of frame numbers before extraction begins
            print("Identifying I-frame positions...")
            frame_numbers = self._get_iframe_numbers(video_path)

            # Validate that at least one I-frame was found
            if not frame_numbers:
                raise NoKeyframesError(
                    f"No I-frames (keyframes) found in video: {video_path}. "
                    "The video may be corrupted or in an unsupported format."
                )

            # Show preview of detected I-frames (limit to first 10 for readability)
            print(
                f"Found {len(frame_numbers)} I-frames at positions: {frame_numbers[:10]}{'...' if len(frame_numbers) > 10 else ''}"
            )

            # ================================================================
            # PHASE 2: Extract each I-frame individually
            # ================================================================
            # Second pass: Extract each I-frame and save with its actual frame number
            # Using actual frame numbers ensures frames are named correctly
            # (e.g., frame 250 from video → video_name+frame_250.jpg)
            selected_frames = []
            for idx, frame_num in enumerate(frame_numbers, 1):
                # Save frame with naming pattern: video_name+frame_X.jpg
                frame_filename = f"{file_id}+frame_{frame_num}.jpg"
                frame_path = os.path.join(frames_folder, frame_filename)
                try:
                    self._extract_single_frame(video_path, frame_num, frame_path)
                    selected_frames.append(
                        SceneFrame(frame_path=frame_path, frame_index=frame_num)
                    )
                    if idx % 10 == 0:  # Progress update every 10 frames
                        print(f"Extracted {idx}/{len(frame_numbers)} frames...")
                except Exception as e:
                    print(f"Warning: Failed to extract frame {frame_num}: {e}")
                    continue

            if not selected_frames:
                raise FFMPEGError(
                    f"Failed to extract any frames from video: {video_path}. "
                    "All frame extractions failed."
                )

            print(
                f"Successfully extracted {len(selected_frames)}/{len(frame_numbers)} keyframes to {frames_folder}"
            )

            # Create result
            detection_result = DetectionResult(
                file_id=file_id,
                output_folder=output_folder,
                selected_frames=selected_frames,
            )

            # Save JSON mapping
            self._save_json_mapping(detection_result, output_folder, file_id)

            return detection_result

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            raise FFMPEGError(f"FFMPEG command failed: {error_msg}") from e
        except (FFMPEGError, VideoFileError, NoKeyframesError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise FFMPEGError(
                f"Unexpected error during keyframe extraction: {e}"
            ) from e

    def _get_iframe_numbers(self, video_path: str) -> List[int]:
        """
        Identify all I-frame (keyframe) positions in the video.

        Args:
            video_path: Path to the video file

        Returns:
            List of frame numbers (0-indexed) where I-frames occur

        Raises:
            FFMPEGError: If FFMPEG command fails
        """
        # Build FFMPEG command to identify I-frames without extracting them
        # - select filter: Only pass through I-frames (PICT_TYPE_I)
        # - showinfo: Print detailed information about each frame to stderr
        # - null output: Don't actually save frames, just analyze
        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            "select='eq(pict_type,PICT_TYPE_I)',showinfo",
            "-vsync",
            "vfr",  # Variable frame rate to preserve original timing
            "-f",
            "null",  # Null muxer - discard output, we only need stderr info
            "-",
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        # ================================================================
        # STEP 1: Extract frame rate from video metadata
        # ================================================================
        # We need the frame rate to convert pts_time (seconds) to frame numbers
        # Frame number = pts_time × frame_rate
        frame_rate = None
        for line in result.stderr.split("\n"):
            if "Stream #" in line and "Video:" in line:
                # Extract frame rate from stream info
                # Example: Stream #0:0: Video: h264, 1920x1080, 30 fps
                parts = line.split(",")
                for part in parts:
                    if "fps" in part or "tbr" in part:
                        try:
                            fps_str = part.strip().split()[0]
                            frame_rate = float(fps_str)
                            break
                        except (ValueError, IndexError):
                            continue
                if frame_rate:
                    break

        # Fallback to 30 fps if frame rate detection fails
        if not frame_rate:
            frame_rate = 30.0
            print(
                f"Warning: Could not detect frame rate, defaulting to {frame_rate} fps"
            )

        # ================================================================
        # STEP 2: Parse showinfo output to get actual frame numbers
        # ================================================================
        # IMPORTANT: The 'n:' value in showinfo is the FILTERED output index (0, 1, 2...)
        # NOT the source frame number. We must use pts_time to calculate the real frame number.
        frame_numbers = []
        for line in result.stderr.split("\n"):
            if "showinfo" in line and "pts_time:" in line:
                try:
                    # Extract pts_time (presentation timestamp in seconds)
                    # This tells us the exact time position of this frame in the video
                    pts_time_str = line.split("pts_time:")[1].split()[0]
                    pts_time = float(pts_time_str)

                    # Calculate frame number from pts_time and frame rate
                    frame_num = int(round(pts_time * frame_rate))
                    frame_numbers.append(frame_num)
                except (ValueError, IndexError):
                    # If pts_time parsing fails, skip this frame
                    continue

        # Always ensure frame 0 (first frame) is included
        if 0 not in frame_numbers:
            frame_numbers.insert(0, 0)

        return frame_numbers

    def _extract_single_frame(
        self, video_path: str, frame_num: int, output_path: str
    ) -> None:
        """
        Extract a specific frame from the video.

        Args:
            video_path: Path to the video file
            frame_num: Frame number to extract (0-indexed)
            output_path: Path where the frame should be saved

        Raises:
            FFMPEGError: If frame extraction fails
        """
        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            f"select='eq(n,{frame_num})'",
            "-vsync",
            "vfr",
            "-frames:v",
            "1",
            "-y",  # Overwrite output file if it exists
            output_path,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout per frame
            )

            # Verify the output file was created
            if not os.path.exists(output_path):
                raise FFMPEGError(
                    f"Frame extraction succeeded but output file not found: {output_path}"
                )

            # Verify the output file has content
            if os.path.getsize(output_path) == 0:
                raise FFMPEGError(f"Extracted frame is empty: {output_path}")

        except subprocess.TimeoutExpired:
            raise FFMPEGError(f"Frame extraction timed out for frame {frame_num}")
        except subprocess.CalledProcessError as e:
            raise FFMPEGError(f"Failed to extract frame {frame_num}: {e.stderr}") from e

    def _save_json_mapping(
        self, result: DetectionResult, output_folder: str, file_id: str
    ) -> None:
        """
        Save JSON mapping of file_id to extracted keyframes.

        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file (detects/file_id/)
            file_id: Unique identifier for the video

        Raises:
            FFMPEGError: If JSON file cannot be saved
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
            raise FFMPEGError(f"Failed to save JSON mapping to {json_path}: {e}") from e


if __name__ == "__main__":
    video_path = r"D:\Professional\Labellerr_SDK\SDKPython\labellerr\notebooks\Labellerr_datasets\354681d3-034a-4d66-b070-365f4bd11d8a\2a8d96ca-9161-4dee-ad3b-a5faf301bc6c.mp4"

    # Get singleton instance
    detector = FFMPEGSceneDetect()
    result = detector.detect_and_extract(video_path)
