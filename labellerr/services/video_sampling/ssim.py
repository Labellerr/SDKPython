import json
import os
from typing import List

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field
from skimage.metrics import structural_similarity as ssim

from labellerr.core.base.singleton import Singleton


class SceneFrame(BaseModel):
    """Represents a detected scene with its extracted frame."""

    frame_path: str
    frame_index: int
    ssim_score: float


class DetectionResult(BaseModel):
    """Contains all detection results for a video."""

    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame] = Field(default_factory=list)


class SSIMSceneDetect(Singleton):
    """SSIM-based scene detection and frame extraction for videos (Singleton)."""

    def detect_and_extract(
        self, video_path: str, threshold: float = 0.6, resize_dim: tuple = (320, 240)
    ) -> DetectionResult:
        """
        Detect scenes using SSIM and extract representative frames.

        Args:
            video_path: Path to the video file
            threshold: SSIM threshold for scene detection (lower = stricter, default: 0.6)
            resize_dim: Dimensions to resize frames for SSIM calculation (default: (320, 240))

        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects
        """
        # Derive file_id from video_path (base name without extension)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))

        # Create detects folder structure
        base_detect_folder = "SSIM_detects"
        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")

        # Create nested output folders
        os.makedirs(frames_folder, exist_ok=True)

        # Open video for processing
        video = cv2.VideoCapture(video_path)

        if not video.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        # Get total frames in video
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"Processing video: {video_path}")
        print(f"Total frames: {total_frames}")
        print(f"SSIM threshold: {threshold}")

        # Read first frame
        success, prev_frame = video.read()
        if not success:
            video.release()
            raise ValueError(f"Cannot read first frame from: {video_path}")

        # Extract and save frames
        scene_frames = []
        frame_count = 0

        # Always save first frame
        self._save_frame(prev_frame, frame_count, 1.0, scene_frames, frames_folder)
        # print(f"Saved keyframe 0 at frame {frame_count} (First frame)")

        # Process remaining frames
        while True:
            success, curr_frame = video.read()
            if not success:
                break

            frame_count += 1

            # Calculate SSIM between current and previous frame
            ssim_score = self._calculate_ssim(prev_frame, curr_frame, resize_dim)

            # If SSIM is below threshold, it's a scene change
            if ssim_score < threshold:
                self._save_frame(
                    curr_frame, frame_count, ssim_score, scene_frames, frames_folder
                )
                print(
                    f"Saved keyframe {len(scene_frames) - 1} at frame {frame_count} (SSIM: {ssim_score:.3f})"
                )
                prev_frame = curr_frame
            elif frame_count % 100 == 0:
                print(
                    f"Frame {frame_count}: SSIM = {ssim_score:.3f} (threshold: {threshold})"
                )

        video.release()

        # print(f"\nExtracted {len(scene_frames)} keyframes from {frame_count + 1} frames.")

        # Create result
        result = DetectionResult(
            file_id=file_id,
            output_folder=output_folder,  # Main detects/file_id folder
            total_frames=total_frames,
            selected_frames=scene_frames,
        )

        # Save JSON mapping
        self._save_json_mapping(result, output_folder, file_id, threshold, resize_dim)

        return result

    def _calculate_ssim(
        self, frame1: np.ndarray, frame2: np.ndarray, resize_dim: tuple
    ) -> float:
        """
        Calculate SSIM score between two frames.

        Args:
            frame1: First frame (BGR format)
            frame2: Second frame (BGR format)
            resize_dim: Dimensions to resize frames for SSIM calculation

        Returns:
            SSIM score (0-1, where 1 is identical)
        """
        # Resize frames for faster computation
        gray1 = cv2.cvtColor(cv2.resize(frame1, resize_dim), cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cv2.resize(frame2, resize_dim), cv2.COLOR_BGR2GRAY)

        # Calculate SSIM
        score, _ = ssim(gray1, gray2, full=True)

        return score

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
            frame: Frame to save (BGR format)
            frame_no: Frame number
            ssim_score: SSIM score that triggered this frame
            scene_frames: List to append SceneFrame object to
            frames_folder: Folder to save the frame (detects/file_id/frames)
        """
        # Convert BGR to RGB for PIL
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)

        # Save frame with frame number as filename in frames folder
        frame_filename = f"{frame_no}.jpg"
        frame_path = os.path.join(
            frames_folder, frame_filename
        )  # Now uses frames_folder
        pil_image.save(frame_path)

        # Create SceneFrame object
        scene_frame = SceneFrame(
            frame_path=frame_path, frame_index=frame_no, ssim_score=ssim_score
        )
        scene_frames.append(scene_frame)

    def _save_json_mapping(
        self,
        result: DetectionResult,
        output_folder: str,  # This is now detects/file_id/
        file_id: str,
        threshold: float,
        resize_dim: tuple,
    ) -> None:
        """
        Save JSON mapping of file_id to extracted scenes.

        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file (detects/file_id/)
            file_id: Unique identifier for the video
            threshold: SSIM threshold used
            resize_dim: Resize dimensions used
        """
        # Use Pydantic's model_dump
        result_dict = result.model_dump()
        result_dict["total_selected_frames"] = len(result.selected_frames)
        result_dict["threshold"] = threshold
        result_dict["resize_dim"] = resize_dim

        json_path = os.path.join(output_folder, f"{file_id}_mapping.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)

        print(f"JSON mapping saved to: {json_path}")


if __name__ == "__main__":
    # Example usage
    video_path = r"D:\professional\LABELLERR\Task\Repos\Python_SDK\services\video_sampling\video2.mp4"

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
