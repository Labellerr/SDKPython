from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError
from labellerr import constants
import uuid
import os
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from abc import ABCMeta, abstractmethod

class LabellerrFileMeta(ABCMeta):
    """Metaclass that combines ABC functionality with factory pattern"""
    
    def __call__(cls, client, file_id, project_id, dataset_id = None, **kwargs):
        
        if cls.__name__ != 'LabellerrFile':
            
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, file_id, project_id, dataset_id=dataset_id, **kwargs)
            return instance
        
        
        try:
            unique_id = str(uuid.uuid4())
            client_id = client.client_id
            params = {
                'file_id': file_id,
                'include_answers': 'false',
                'project_id': project_id,
                'uuid': unique_id,
                'client_id': client_id
            }
            
            # TODO: Add dataset_id to params based on precedence logic
            # Priority: project_id > dataset_id
            
            url = f"{constants.BASE_URL}/data/file_data"
            response = client.make_api_request(client_id, url, params, unique_id)
            
            # Extract data_type from response
            file_metadata = response.get('file_metadata', {})
            data_type = response.get('data_type', '').lower()
            
            # print(f"Detected file type: {data_type}")
            
            # Route to appropriate subclass
            if data_type == 'image':
                return LabellerrImageFile(client, file_id, project_id, dataset_id=dataset_id, 
                                         file_metadata=file_metadata)
            elif data_type == 'video':
                return LabellerrVideoFile(client, file_id, project_id, dataset_id=dataset_id,
                                         file_metadata=file_metadata)
            elif data_type == 'pdf':
                return LabellerrPDFFile(client, file_id, project_id, dataset_id=dataset_id,
                                       file_metadata=file_metadata)
            else:
                raise LabellerrError(f"Unsupported file type: {data_type}")

                
        except Exception as e:
            raise LabellerrError(f"Failed to create file instance: {str(e)}")


class LabellerrFile(metaclass=LabellerrFileMeta):
    """Base class for all Labellerr files with factory behavior"""
    
    def __init__(self, client: LabellerrClient, file_id: str, project_id: str,
                  dataset_id: str | None = None, **kwargs):
        """
        Initialize base file attributes
        
        :param client: LabellerrClient instance
        :param file_id: Unique file identifier
        :param project_id: Project ID containing the file
        :param dataset_id: Optional dataset ID
        :param kwargs: Additional file data (file_metadata, response, etc.)
        """
        self.client = client
        self.file_id = file_id
        self.project_id = project_id
        self.client_id = client.client_id
        self.dataset_id = dataset_id
        
        # Store metadata from factory creation
        self.metadata = kwargs.get('file_metadata', {})

        
    def get_metadata(self, include_answers: bool = False):
        """
        Refresh and retrieve file metadata from Labellerr API.
        
        :param include_answers: Whether to include annotation answers
        :return: Dictionary containing file metadata
        """
        try:
            unique_id = str(uuid.uuid4())
            
            params = {
                'file_id': self.file_id,
                'include_answers': str(include_answers).lower(),
                'project_id': self.project_id,
                'uuid': unique_id,
                'client_id': self.client_id
            }
            
            # TODO: Add dataset_id handling if needed
            
            url = f"{constants.BASE_URL}/data/file_data"
            response = self.client.make_api_request(self.client_id, url, params, unique_id)
            
            # Update cached metadata
            self.metadata = response.get('file_metadata', {})
            
            return response
                    
        except Exception as e:
            raise LabellerrError(f"Failed to fetch file metadata: {str(e)}")


class LabellerrImageFile(LabellerrFile):
    pass

class LabellerrVideoFile(LabellerrFile):
    """Specialized class for handling video files including frame operations"""
    
    def __init__(self, client: LabellerrClient, file_id: str, project_id: str, dataset_id: str | None = None, **kwargs):
        super().__init__(client, file_id, project_id, dataset_id=dataset_id, **kwargs)
    
    @property
    def total_frames(self):
        """Get total number of frames in the video."""
        return self.metadata.get('total_frames', 0)
    
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
                'dataset_id': self.dataset_id,
                'file_id': self.file_id,
                'frame_start': frame_start,
                'frame_end': frame_end,
                'project_id': self.project_id,
                'uuid': unique_id,
                'client_id': self.client_id
            }
            
            response = self.client.make_api_request(self.client_id, url, params, unique_id)
            
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
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                with print_lock:
                    print(f"Downloaded: {filename}")
                
                return True, frame_number, None
            else:
                error_info = {
                    'frame': frame_number,
                    'status': response.status_code
                }
                with print_lock:
                    print(f"Failed to download frame {frame_number}: Status {response.status_code}")
                
                return False, frame_number, error_info
                
        except Exception as e:
            error_info = {
                'frame': frame_number,
                'error': str(e)
            }
            with print_lock:
                print(f"Error downloading frame {frame_number}: {str(e)}")
            
            return False, frame_number, error_info
    
    def download_frames(self, frames_data: dict, output_folder: str | None = None, 
                       max_workers: int = 10):
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
            
            print(f"Downloading {len(frames_data)} frames to: {save_path}")
            print(f"Using {max_workers} concurrent threads")
            
            # Use ThreadPoolExecutor for concurrent downloads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_frame = {
                    executor.submit(
                        self._download_single_frame, 
                        frame_number, 
                        frame_url, 
                        save_path,
                        print_lock
                    ): frame_number 
                    for frame_number, frame_url in frames_data.items()
                }
                
                # Process completed downloads
                for future in as_completed(future_to_frame):
                    success, frame_number, error_info = future.result()
                    
                    if success:
                        success_count += 1
                    else:
                        failed_frames.append(error_info)
            
            result = {
                'total_frames': len(frames_data),
                'successful_downloads': success_count,
                'failed_downloads': len(failed_frames),
                'save_path': save_path,
                'failed_frames': failed_frames
            }
            
            # print(f"\nDownload complete: {success_count}/{len(frames_data)} frames downloaded successfully")
            
            return result
                    
        except Exception as e:
            raise LabellerrError(f"Failed to download video frames: {str(e)}")
    
    def create_video(self, frames_folder: str, output_file: str = "output.mp4", 
                    framerate: int = 30, pattern: str = "%d.jpg"):
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

        # FFmpeg command
        command = [
            "ffmpeg",
            "-y",  # Overwrite output file if exists
            "-framerate", str(framerate),
            "-i", input_pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_file
        ]

        try:
            print("Running command:", " ".join(command))
            subprocess.run(command, check=True)
            print(f"Video saved as {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            raise LabellerrError(f"Error while joining frames: {str(e)}")

class LabellerrVideoDataset:
    """
    Class for handling video dataset operations and fetching multiple video files.
    """
    
    def __init__(self, client: LabellerrClient, dataset_id: str, project_id: str):
        """
        Initialize video dataset instance.
        
        :param client: LabellerrClient instance
        :param dataset_id: Dataset ID
        :param project_id: Project ID containing the dataset
        """
        self.client = client
        self.dataset_id = dataset_id
        self.project_id = project_id
        self.client_id = client.client_id
    
    def fetch_files(self, limit: int | None = None, page_size: int = 10):
        """
        Fetch all video files in this dataset as LabellerrVideoFile instances.
        
        :param limit: Maximum number of files to fetch (None for all)
        :param page_size: Number of files to fetch per API request (default: 10)
        :return: List of LabellerrVideoFile instances
        """
        try:
            all_file_ids = []
            next_search_after = ""  # Start with empty string for first page
            
            # while True:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/search/files/all"
            params = {
                'sort_by': 'created_at',
                'sort_order': 'desc',
                'size': page_size,
                'next_search_after': next_search_after,
                'uuid': unique_id,
                'dataset_id': self.dataset_id,
                'client_id': self.client_id
            }
            
            response = self.client.make_api_request(self.client_id, url, params, unique_id)
            print(response)
                
                            
            # Create LabellerrVideoFile instances for each file_id
            # video_files = []
            # print(f"\nCreating LabellerrFile instances for {len(all_file_ids)} files...")
            
            # for file_id in all_file_ids:
            #     try:
            #         video_file = LabellerrFile(
            #             client=self.client,
            #             file_id=file_id,
            #             project_id=self.project_id,
            #             dataset_id=self.dataset_id
            #         )
            #         video_files.append(video_file)
            #     except Exception as e:
            #         print(f"Warning: Failed to create file instance for {file_id}: {str(e)}")
            
        except Exception as e:
            raise LabellerrError(f"Failed to fetch dataset files: {str(e)}")
        
# Example usage
if __name__ == "__main__":
    
    api_key = "66f4d8.9f402742f58a89568f5bcc0f86"
    api_secret = "1e2478b930d4a842a526beb585e60d2a9ee6a6f1e3aa89cb3c8ead751f418215"
    client_id = "14078"
    dataset_id = "16257fd6-b91b-4d00-a680-9ece9f3f241c"
    project_id = "gabrila_artificial_duck_74237"
    file_id = "c44f38f6-0186-436f-8c2d-ffb50a539c76"
    
    client = LabellerrClient(api_key=api_key, api_secret=api_secret, client_id=client_id)
    
    lb_file = LabellerrFile(
        client=client,
        file_id=file_id,
        project_id=project_id,
        dataset_id=dataset_id
    )
    
    
    # print(f"File type: {type(lb_file).__name__}")
    
    # if isinstance(lb_file, LabellerrVideoFile):
    #     print(f"Total frames: {lb_file.total_frames}")
        
        # Get video frames 
        # frames = lb_file.get_frames()
        
        # Download frames
        # lb_file.download_frames(frames, output_folder="./output")
        
        # Create video from frames
        # frames_path = f"./output/{file_id}"
        # lb_file.create_video(frames_folder=frames_path, output_file="final_video.mp4", framerate=30)
        
    lb_dataset = LabellerrVideoDataset(client=client, dataset_id=dataset_id, project_id=project_id)
    lb_dataset.fetch_files()
    # print(f"Fetched {len(video_files)} video files from dataset {dataset_id}")
    # print(video_files)
    