import json
import os
import subprocess
from typing import List

from pydantic import BaseModel, Field

from labellerr.core.base.singleton import Singleton


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

    def detect_and_extract(self, video_path: str) -> DetectionResult:
        """
        Extract keyframes from video and save to detects folder structure.

        Args:
            video_path: Path to the video file

        Returns:
            DetectionResult containing file_id, output_folder, and list of SceneFrame objects
        """
        # Derive file_id from video_path (base name without extension)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))

        # Create detects folder structure
        base_detect_folder = "FFMPEG_detects"

        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")

        # Create nested folders
        os.makedirs(frames_folder, exist_ok=True)

        # Update output pattern to use frames subfolder in detects structure
        output_pattern = os.path.join(frames_folder, "%d.jpg")

        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            "select='eq(pict_type,PICT_TYPE_I)',showinfo",
            "-vsync",
            "vfr",
            "-frame_pts",
            "1",
            output_pattern,
        ]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Keyframes extracted to {frames_folder}")

            # Parse frame information from FFMPEG output
            selected_frames = self._parse_ffmpeg_output(result.stderr, frames_folder)

            # Create result
            detection_result = DetectionResult(
                file_id=file_id,
                output_folder=output_folder,  # Main detects/file_id folder
                selected_frames=selected_frames,
            )

            # Save JSON mapping
            self._save_json_mapping(detection_result, output_folder, file_id)

            return detection_result

        except subprocess.CalledProcessError as e:
            print(f"Error extracting keyframes: {e}")
            raise

    def _parse_ffmpeg_output(
        self, stderr_output: str, frames_folder: str
    ) -> List[SceneFrame]:
        """
        Parse FFMPEG stderr output to extract frame information.

        Args:
            stderr_output: FFMPEG stderr output containing showinfo data
            frames_folder: Folder where frames are saved (detects/file_id/frames)

        Returns:
            List of SceneFrame objects
        """
        frames = []
        frame_counter = 1

        # Parse showinfo output from stderr
        for line in stderr_output.split("\n"):
            if "showinfo" in line and "n:" in line:
                # The frame file is named sequentially starting from 1
                frame_path = os.path.join(frames_folder, f"{frame_counter}.jpg")

                # Extract frame number from showinfo line if needed
                # Example: [Parsed_showinfo_1 @ 0x...] n:   0 pts:      0 ...
                try:
                    if "pts_time:" in line:
                        # Extract the actual frame number from the source
                        parts = line.split("n:")
                        if len(parts) > 1:
                            frame_no = int(parts[1].split()[0])
                        else:
                            frame_no = frame_counter - 1
                    else:
                        frame_no = frame_counter - 1

                    frames.append(
                        SceneFrame(frame_path=frame_path, frame_index=frame_no)
                    )
                    frame_counter += 1
                except (ValueError, IndexError):
                    continue

        return frames

    def _save_json_mapping(
        self, result: DetectionResult, output_folder: str, file_id: str
    ) -> None:
        """
        Save JSON mapping of file_id to extracted keyframes.

        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file (detects/file_id/)
            file_id: Unique identifier for the video
        """
        # Use Pydantic's model_dump
        result_dict = result.model_dump()
        result_dict["total_selected_frames"] = len(result.selected_frames)

        json_path = os.path.join(output_folder, f"{file_id}_mapping.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)

        print(f"JSON mapping saved to: {json_path}")


if __name__ == "__main__":
    video_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\download_video\59438ec3-12e0-4687-8847-1e6e01b0bf25\1cb2eec4-5125-4272-ad09-c249f40fffb3.mp4"

    # Get singleton instance
    detector = FFMPEGSceneDetect()
    result = detector.detect_and_extract(video_path)
