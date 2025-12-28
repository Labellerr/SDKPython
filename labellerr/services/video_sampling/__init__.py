"""All the code for video sampling will go here.

All algorithms for video sampling  will go in separate files.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Try to import detectors (optional dependencies)
try:
    from .ffmpeg_detect import FFMPEGSceneDetect
    from .pyscene_detect import PySceneDetect
    from .ssim_detect import SSIMSceneDetect

    _DETECTORS_AVAILABLE = True
except ImportError:
    _DETECTORS_AVAILABLE = False
    FFMPEGSceneDetect = None
    PySceneDetect = None
    SSIMSceneDetect = None

__all__ = [
    "FFMPEGSceneDetect",
    "PySceneDetect",
    "SSIMSceneDetect",
    "process_videos_batch",
    "coco_to_video_json",
]


# Supported video file extensions
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v"}


def process_videos_batch(
    detector: Union[PySceneDetect, FFMPEGSceneDetect, SSIMSceneDetect],
    dataset_dir: Union[str, Path],
    **detector_kwargs,
) -> List[Dict[str, Any]]:
    """
    Process all video files in a directory using the specified detector algorithm.

    This function works with any detector algorithm (PySceneDetect, FFMPEGSceneDetect,
    SSIMSceneDetect) and processes all video files in the specified directory.
    All extracted frames will be stored according to each detector's output structure.

    Args:
        detector: Instance of any detector class (PySceneDetect, FFMPEGSceneDetect, or SSIMSceneDetect)
        dataset_dir: Path to directory containing video files to process
        **detector_kwargs: Additional keyword arguments to pass to the detector's detect_and_extract method
                          (e.g., threshold=0.3, resize_dim=(320, 240) for SSIMSceneDetect)

    Returns:
        List of dictionaries containing processing results for each video:
        - filename: Name of the video file
        - status: 'success' or 'failed'
        - frames_extracted: Number of frames extracted (if successful)
        - output_folder: Path where frames were stored (if successful)
        - error: Error message (if failed)

    Example:
        >>> from labellerr.services.video_sampling import PySceneDetect, process_videos_batch
        >>> detector = PySceneDetect()
        >>> results = process_videos_batch(detector, "./Labellerr_datasets")
        >>> print(f"Processed {len(results)} videos")

        >>> # Using SSIMSceneDetect with custom parameters
        >>> from labellerr.services.video_sampling import SSIMSceneDetect, process_videos_batch
        >>> detector = SSIMSceneDetect()
        >>> results = process_videos_batch(
        ...     detector,
        ...     "./Labellerr_datasets",
        ...     threshold=0.3,
        ...     resize_dim=(320, 240)
        ... )
    """
    # Convert to Path object for easier handling
    dataset_path = Path(dataset_dir)

    # Verify dataset directory exists
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dataset_dir}")

    # Get all video files from the dataset directory
    video_files = [
        f
        for f in os.listdir(dataset_path)
        if os.path.isfile(os.path.join(dataset_path, f))
        and os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
    ]

    if not video_files:
        print(f"⚠️  No video files found in {dataset_dir}")
        return []

    print(f"Found {len(video_files)} video files to process")
    print("=" * 70)

    # Process each video file
    results = []
    for idx, filename in enumerate(video_files, 1):
        file_path = os.path.join(dataset_path, filename)
        print(f"\n[{idx}/{len(video_files)}] Processing: {filename}")
        print("-" * 70)

        try:
            # Call the detector's detect_and_extract method with optional kwargs
            result = detector.detect_and_extract(str(file_path), **detector_kwargs)

            results.append(
                {
                    "filename": filename,
                    "status": "success",
                    "frames_extracted": len(result.selected_frames),
                    "output_folder": result.output_folder,
                }
            )
            print(f"✓ Successfully extracted {len(result.selected_frames)} frames")

        except Exception as e:
            results.append({"filename": filename, "status": "failed", "error": str(e)})
            print(f"✗ Failed: {str(e)}")

    # Print summary
    print("\n" + "=" * 70)
    print("PROCESSING SUMMARY")
    print("=" * 70)

    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_frames = sum(
        r.get("frames_extracted", 0) for r in results if r["status"] == "success"
    )

    print(f"Total videos processed: {len(video_files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total frames extracted: {total_frames}")

    if successful > 0:
        # Get output folder from first successful result
        output_folder = next(
            (r["output_folder"] for r in results if r["status"] == "success"), "N/A"
        )
        print(f"\n✓ Frames stored in: {output_folder}/")

    # Print detailed results for failed videos
    if failed > 0:
        print("\n" + "=" * 70)
        print("FAILED VIDEOS:")
        print("=" * 70)
        for r in results:
            if r["status"] == "failed":
                print(f"  • {r['filename']}: {r['error']}")

    return results


# ============================================================================
# COCO to Video JSON Converter
# ============================================================================


def _extract_video_name_and_frame(filename: str) -> tuple[str, int, int]:
    """
    Extract video name, frame number, and FPS from keyframe filename.

    Format: {dataset_id}+{file_id}+{video_name}+FPS{fps}+frame_{frame_number}.jpg
    Example: 15908795-09eb-4cdb-a39b-8689f8f936e5+471163aa-19dc-4bc7-9aee-04780591281a+butterflies_960p+FPS29+frame_1064.jpg
    Returns: ("butterflies_960p.mp4", 1064, 29)

    Args:
        filename: The keyframe filename

    Returns:
        Tuple of (video_name, frame_number, fps)

    Raises:
        ValueError: If filename format is invalid
    """
    # Split by '+' to get parts
    parts = filename.split("+")

    if len(parts) < 4:
        raise ValueError(f"Invalid filename format: {filename}")

    # Last part contains frame_X.jpg
    last_part = parts[-1]

    # Extract frame number using regex
    frame_match = re.search(r"frame_(\d+)\.jpg$", last_part)
    if not frame_match:
        raise ValueError(f"Could not extract frame number from: {filename}")

    frame_number = int(frame_match.group(1))

    # Extract FPS from the parts (format: FPS{number})
    fps = 25  # Default FPS
    video_name_part = None

    for i, part in enumerate(parts):
        fps_match = re.match(r"FPS(\d+)$", part)
        if fps_match:
            fps = int(fps_match.group(1))
            # Video name is the part before FPS
            if i > 0:
                video_name_part = parts[i - 1]
            break

    # If no FPS found, use the second-to-last part as video name (old format)
    if video_name_part is None:
        video_name_part = parts[-2]

    video_name = f"{video_name_part}.mp4"

    return video_name, frame_number, fps


def _convert_segmentation_to_polygon(segmentation: List[float]) -> List[Dict[str, int]]:
    """
    Convert COCO segmentation format to video polygon format.

    COCO format: [x1, y1, x2, y2, x3, y3, ...]
    Video format: [{"x": x1, "y": y1}, {"x": x2, "y": y2}, ...]

    Args:
        segmentation: List of alternating x, y coordinates

    Returns:
        List of coordinate dictionaries
    """
    polygon = []
    for i in range(0, len(segmentation), 2):
        polygon.append({"x": int(segmentation[i]), "y": int(segmentation[i + 1])})
    return polygon


def _convert_bbox_to_video_format(bbox: List[float]) -> Dict[str, Any]:
    """
    Convert COCO bbox format to video bbox format.

    COCO format: [xmin, ymin, width, height]
    Video format: {"xmin": x, "ymin": y, "xmax": x+w, "ymax": y+h, "rotation": 0}

    Args:
        bbox: COCO bounding box [x, y, width, height]

    Returns:
        Video format bounding box dictionary
    """
    xmin, ymin, width, height = bbox
    return {
        "xmin": int(xmin),
        "ymin": int(ymin),
        "xmax": int(xmin + width),
        "ymax": int(ymin + height),
        "rotation": 0,
    }


def coco_to_video_json(
    coco_json_path: str,
    output_path: Optional[str] = "Video_Keyframe_annot.json",
    default_fps: int = 25,
) -> List[Dict[str, Any]]:
    """
    Convert COCO JSON format (from keyframe exports) to Video JSON format.

    This function transforms annotations exported from keyframe image projects
    into the format required for video project preannotation upload.

    Args:
        coco_json_path: Path to the COCO JSON file
        output_path: Path to save the converted JSON. Default: "Video_Keyframe_annot.json"
                     Set to None to skip saving
        default_fps: Default frames per second if not found in filename (default: 25)

    Returns:
        List of video annotation dictionaries

    Example:
        >>> from labellerr.services.video_sampling import coco_to_video_json
        >>> video_annotations = coco_to_video_json(
        ...     "export_zmYykSJhCAJqAaXaJQ3g.json",
        ...     "Video_Keyframe_annot.json"
        ... )
    """
    # Load COCO JSON
    with open(coco_json_path, "r", encoding="utf-8") as f:
        coco_data = json.load(f)

    # Create mappings
    images = {img["id"]: img for img in coco_data["images"]}
    categories = {cat["id"]: cat for cat in coco_data["categories"]}

    # Group annotations by video file
    video_annotations: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "file_name": "",
            "annotations": defaultdict(
                lambda: {"question_type": "", "question_name": "", "answer": []}
            ),
        }
    )

    # Process each annotation
    for annotation in coco_data["annotations"]:
        image_id = annotation["image_id"]
        category_id = annotation["category_id"]

        # Get image and category info
        image = images[image_id]
        category = categories[category_id]

        # Extract video name, frame number, and FPS
        try:
            video_name, frame_number, fps = _extract_video_name_and_frame(
                image["file_name"]
            )
        except ValueError as e:
            print(f"Warning: Skipping annotation - {e}")
            fps = default_fps  # Use default if extraction fails
            continue

        # Determine question type based on annotation structure
        if "segmentation" in annotation and annotation["segmentation"]:
            question_type = "polygon"
            # Convert segmentation to polygon format
            answer_data = _convert_segmentation_to_polygon(
                annotation["segmentation"][0]
            )
        elif "bbox" in annotation:
            question_type = "BoundingBox"
            # Convert bbox to video format
            answer_data = _convert_bbox_to_video_format(annotation["bbox"])
        else:
            print(
                f"Warning: Unknown annotation type for annotation {annotation.get('id')}"
            )
            continue

        # Get or create video entry
        video_key = video_name
        if not video_annotations[video_key]["file_name"]:
            video_annotations[video_key]["file_name"] = video_name

        # Get or create question entry
        question_name = category["name"]
        question_key = f"{category_id}_{question_type}"

        if not video_annotations[video_key]["annotations"][question_key][
            "question_type"
        ]:
            video_annotations[video_key]["annotations"][question_key][
                "question_type"
            ] = question_type
            video_annotations[video_key]["annotations"][question_key][
                "question_name"
            ] = question_name
            video_annotations[video_key]["annotations"][question_key]["answer"] = []

        # Create a new answer group for each annotation
        # This allows multiple annotations on the same frame
        new_answer_group = {"startFrame": frame_number, "frames": {}}

        # Add frame data
        frame_data = {
            "frame": frame_number,
            "answer": answer_data,
            "isManualAnnotation": True,
            "fps": fps,
        }

        new_answer_group["frames"][str(frame_number)] = frame_data
        video_annotations[video_key]["annotations"][question_key]["answer"].append(
            new_answer_group
        )

    # Convert to list format
    result = []
    for video_name, video_data in video_annotations.items():
        # Convert annotations dict to list
        annotations_list = []
        for question_data in video_data["annotations"].values():
            # Ensure startFrame is set correctly for each answer group
            for answer_group in question_data["answer"]:
                frames = answer_group["frames"]
                if frames:
                    # Set startFrame to the minimum frame number
                    min_frame = min(int(f) for f in frames.keys())
                    answer_group["startFrame"] = min_frame

            annotations_list.append(
                {
                    "question_type": question_data["question_type"],
                    "question_name": question_data["question_name"],
                    "answer": question_data["answer"],
                }
            )

        result.append(
            {"file_name": video_data["file_name"], "annotations": annotations_list}
        )

    # Save to file if output path is provided
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Video JSON saved to: {output_path}")

    return result
