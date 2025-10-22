import os
from scenedetect import detect, AdaptiveDetector
from PIL import Image
import cv2
from pydantic import BaseModel, Field
from typing import List
import json
from labellerr.base.singleton import Singleton


class SceneFrame(BaseModel):
    """Represents a detected scene with its extracted frame."""
    frame_path: str
    frame_index: int
    

class DetectionResult(BaseModel):
    """Contains all detection results for a video."""
    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame] = Field(default_factory=list)
    

class PySceneDetect(Singleton):
    """Scene detection and frame extraction for videos (Singleton)."""
    
    def detect_and_extract(self, video_path: str) -> DetectionResult:
        """
        Detect scenes and extract representative frames.
        
        Args:
            video_path: Path to the video file
        
        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects
        """
        # Derive file_id from video_path (base name without extension)
        file_id = os.path.splitext(os.path.basename(video_path))[0]
        dataset_id = os.path.basename(os.path.dirname(video_path))
        
        # Create base detect folder and file_id specific folder
        base_detect_folder = "PyScene_detects"
        
        output_folder = os.path.join(base_detect_folder, dataset_id, file_id)
        frames_folder = os.path.join(output_folder, "frames")  # New frames subfolder
        
        # Detect scene transitions
        scenes = detect(video_path, AdaptiveDetector())
        
        # Create nested output folders
        os.makedirs(frames_folder, exist_ok=True)  # Create frames subfolder
        
        # Open video for frame extraction
        video = cv2.VideoCapture(video_path)
        
        # Get total frames in video
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Extract and save frames
        scene_frames = []
        for scene in scenes:
            # Calculate middle frame number
            frame_no = (scene[1] - scene[0]).frame_num // 2 + scene[0].frame_num
            
            # Extract frame
            frame = self._get_frame(video, frame_no)
            
            # Save frame with frame number as filename inside frames folder
            frame_filename = f"{frame_no}.jpg"
            frame_path = os.path.join(frames_folder, frame_filename)  # Updated path
            frame.save(frame_path)
            
            # Create SceneFrame object
            scene_frame = SceneFrame(
                frame_path=frame_path,
                frame_index=frame_no
            )
            scene_frames.append(scene_frame)
        
        video.release()
        
        # Create result
        result = DetectionResult(
            file_id=file_id,
            output_folder=output_folder,
            total_frames=total_frames,
            selected_frames=scene_frames
        )
        
        # Save JSON mapping
        self._save_json_mapping(result, output_folder, file_id)
        
        return result
    
    def _get_frame(self, video: cv2.VideoCapture, frame_no: int) -> Image.Image:
        """
        Extract a specific frame from video.
        
        Args:
            video: OpenCV video capture object
            frame_no: Frame number to extract
            
        Returns:
            PIL Image of the frame
        """
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        _, frame = video.read()
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    def _save_json_mapping(self, result: DetectionResult, output_folder: str, file_id: str) -> None:
        """
        Save JSON mapping of file_id to extracted scenes.
        
        Args:
            result: DetectionResult object
            output_folder: Folder to save the JSON file
            file_id: Unique identifier for the video
        """
        # Use Pydantic's model_dump instead of asdict
        result_dict = result.model_dump()
        result_dict["total_selected_frames"] = len(result.selected_frames)
        
        json_path = os.path.join(output_folder, f"{file_id}_mapping.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        print(f"JSON mapping saved to: {json_path}")


# if __name__ == "__main__":
#     video_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\notebooks\c44f38f6-0186-436f-8c2d-ffb50a539c76.mp4"
    
#     detector = PySceneDetect()
#     result = detector.detect_and_extract(video_path)