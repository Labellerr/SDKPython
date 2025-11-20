import os
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import TYPE_CHECKING, Optional

import requests

from labellerr.core.files.base import LabellerrFile, LabellerrFileMeta

from .. import constants
from ..exceptions import LabellerrError

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrVideoFile(LabellerrFile):
    """Specialized class for handling video files including frame operations"""

    def __init__(
        self,
        client: "LabellerrClient",
        file_id: str,
        project_id: str,
        dataset_id: str | None = None,
        **kwargs,
    ):
        super().__init__(client, file_id, project_id, dataset_id=dataset_id, **kwargs)

    @property
    def total_frames(self):
        """Get total number of frames in the video."""
        return self.metadata.get("total_frames", 0)

    def get_frames(self, frame_start: int = 0, frame_end: int | None = None):
        """
        Retrieve video frames data from Labellerr API.

        :param frame_start: Starting frame index (default: 0)
        :param frame_end: Ending frame index (default: total_frames)
        :return: Dictionary containing video frames data with frame numbers as keys and URLs as values
        """
        try:
            if self.dataset_id is None:
                raise ValueError("dataset_id is required for fetching video frames")

            # Use total_frames as default for frame_end
            if frame_end is None:
                frame_end = self.total_frames

            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/data/video_frames"

            params = {
                "dataset_id": self.dataset_id,
                "file_id": self.file_id,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "project_id": self.project_id,
                "uuid": unique_id,
                "client_id": self.client.client_id,
            }

            response = self.client.make_request(
                "GET", url, extra_headers=None, request_id=unique_id, params=params
            )

            return response

        except Exception as e:
            raise LabellerrError(f"Failed to fetch video frames data: {str(e)}")

    def _download_single_frame(self, frame_number, frame_url, save_path, print_lock):
        """
        Download a single frame (helper method for threading).

        :param frame_number: Frame number
        :param frame_url: URL to download from
        :param save_path: Directory to save the frame
        :param print_lock: Lock for thread-safe printing
        :return: Tuple of (success: bool, frame_number: str, error_info: dict or None)
        """
        try:
            filename = f"{frame_number}.jpg"
            filepath = os.path.join(save_path, filename)

            response = requests.get(frame_url, timeout=30)

            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return True, frame_number, None
            else:
                error_info = {"frame": frame_number, "status": response.status_code}
                return False, frame_number, error_info

        except Exception as e:
            error_info = {"frame": frame_number, "error": str(e)}
            with print_lock:
                print(f"Error downloading frame {frame_number}: {str(e)}")

            return False, frame_number, error_info

    def download_frames(
        self, frames_data: dict, output_folder: str | None = None, max_workers: int = 30
    ):
        """
        Download video frames from URLs to a local folder using multithreading.

        :param frames_data: Dictionary with frame numbers as keys and URLs as values
        :param output_folder: Base folder path where frames will be saved (default: current directory)
        :param max_workers: Maximum number of concurrent download threads (default: 10)
        :return: Dictionary with download statistics
        """
        try:
            # Use file_id as folder name
            folder_name = self.file_id

            # Set output path
            if output_folder:
                save_path = os.path.join(output_folder, folder_name)
            else:
                save_path = folder_name

            # Create directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)

            success_count = 0
            failed_frames = []
            print_lock = Lock()
            total_frames = len(frames_data)

            print(f"Starting download of {total_frames} frames...")

            # Use ThreadPoolExecutor for concurrent downloads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_frame = {
                    executor.submit(
                        self._download_single_frame,
                        frame_number,
                        frame_url,
                        save_path,
                        print_lock,
                    ): frame_number
                    for frame_number, frame_url in frames_data.items()
                }

                completed = 0
                # Process completed downloads
                for future in as_completed(future_to_frame):
                    success, frame_number, error_info = future.result()
                    completed += 1

                    if success:
                        success_count += 1
                    else:
                        failed_frames.append(error_info)

                    # Update progress
                    with print_lock:
                        print(
                            f"\rFrames downloaded: {completed}/{total_frames} ({success_count} successful, {len(failed_frames)} failed)",
                            end="",
                            flush=True,
                        )

            # Print newline after progress
            print()

            result = {
                "file_id": self.file_id,
                "total_frames": total_frames,
                "successful_downloads": success_count,
                "failed_downloads": len(failed_frames),
                "save_path": save_path,
                "failed_frames": failed_frames,
            }

            # print(f"\nDownload complete: {success_count}/{len(frames_data)} frames downloaded successfully")

            return result

        except Exception as e:
            raise LabellerrError(f"Failed to download video frames: {str(e)}")

    def create_video(
        self,
        frames_folder: str,
        framerate: int = 30,
        pattern: str = "%d.jpg",
        output_file: str | None = None,
    ):
        """
        Join frames into a video using ffmpeg.

        :param frames_folder: Path to folder containing sequential frames (e.g., 1.jpg, 2.jpg).
        :param output_file: Name of the output video file (default: output.mp4).
        :param framerate: Desired video framerate (default: 30 fps).
        :param pattern: Pattern for sequential frames (default: %d.jpg → 1.jpg, 2.jpg, ...).
        :return: Path to created video file
        """
        if frames_folder is None:
            raise ValueError("frames_folder must be provided")

        input_pattern = os.path.join(frames_folder, pattern)
        if output_file is None:
            output_file = f"{self.file_id}.mp4"

        # FFmpeg command
        command = [
            "ffmpeg",
            "-y",  # Overwrite output file if exists
            "-start_number",
            "0",
            "-framerate",
            str(framerate),
            "-i",
            input_pattern,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            output_file,
        ]

        try:
            print("Running command:", " ".join(command))
            subprocess.run(command, check=True)
            print(f"Video saved as {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            raise LabellerrError(f"Error while joining frames: {str(e)}")

    def download_create_video_auto_cleanup(
        self, output_folder: str = "./Labellerr_datasets"
    ):
        """
        Download frames, create video, and automatically clean up temporary frames.
        This is an all-in-one method for processing video files.
        Downloads all frames from 0 to total_frames automatically.

        :return: Dictionary with operation results
        """
        try:
            print(f"\n{'='*60}")
            print(f"Processing file: {self.file_id}")
            print(f"{'='*60}")

            # Step 1: Get total frames
            total_frames = self.total_frames
            if total_frames == 0:
                raise LabellerrError("No frames found for this video file")

            # Step 2: Fetch frame data from API
            print(f"\n[1/4] Fetching frame data from API (0 to {total_frames})...")
            frames_data = self.get_frames(frame_start=0, frame_end=total_frames)

            # print(frames_data)

            if not frames_data:
                raise LabellerrError("No frame data retrieved from API")

            print(f"Retrieved {len(frames_data)} frames")

            # Step 2: Create dataset folder structure
            print("\n[2/4] Setting up output folders...")
            if self.dataset_id is None:
                dataset_folder = output_folder
            else:
                dataset_folder = os.path.join(output_folder, self.dataset_id)
            os.makedirs(dataset_folder, exist_ok=True)

            # Define actual frames folder path
            actual_frames_folder = os.path.join(dataset_folder, self.file_id)

            # Step 3: Download frames
            print("\n[3/4] Downloading frames...")
            download_result = self.download_frames(
                frames_data=frames_data, output_folder=dataset_folder
            )

            if download_result["failed_downloads"] > 0:
                print(
                    f"\nWarning: {download_result['failed_downloads']} frames failed to download"
                )

            # Step 4: Create video from downloaded frames
            print("\n[4/4] Creating video from frames...")
            video_output_path = os.path.join(dataset_folder, f"{self.file_id}.mp4")

            self.create_video(
                frames_folder=actual_frames_folder, output_file=video_output_path
            )

            # Step 5: Clean up temporary frames folder
            print("\nCleaning up temporary frames...")
            if os.path.exists(actual_frames_folder):
                shutil.rmtree(actual_frames_folder)
                print(f"Removed temporary frames folder: {actual_frames_folder}")

            result = {
                "status": "success",
                "file_id": self.file_id,
                "dataset_id": self.dataset_id,
                "video_path": video_output_path,
                "output_folder": dataset_folder,
                "frames_downloaded": download_result["successful_downloads"],
                "frames_failed": download_result["failed_downloads"],
                "failed_frames_info": download_result["failed_frames"],
            }

            print(f"\n{'='*60}")
            print("Processing complete!")
            print(f"Video saved to: {video_output_path}")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            # Attempt cleanup on error
            # Get the frames folder path
            if self.dataset_id is None:
                cleanup_folder = os.path.join(output_folder, self.file_id)
            else:
                cleanup_folder = os.path.join(
                    output_folder, self.dataset_id, self.file_id
                )

            if os.path.exists(cleanup_folder):
                shutil.rmtree(cleanup_folder)

            raise LabellerrError(f"Failed in video processing: {str(e)}")


LabellerrFileMeta._register("video", LabellerrVideoFile)
