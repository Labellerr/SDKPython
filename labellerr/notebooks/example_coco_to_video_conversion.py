"""
Example: Converting COCO JSON (Keyframe Export) to Video JSON Format

This notebook demonstrates how to convert COCO JSON annotations exported from
keyframe image projects into the video JSON format required for preannotation upload.
"""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path.cwd().parent.parent))

from labellerr.services.video_sampling.coco_to_video import coco_to_video_json

# Example 1: Basic conversion
print("=" * 70)
print("EXAMPLE 1: Basic COCO to Video JSON Conversion")
print("=" * 70)

coco_json_path = "export_zmYykSJhCAJqAaXaJQ3g.json"
output_path = "video_preannotations.json"

video_annotations = coco_to_video_json(
    coco_json_path=coco_json_path,
    output_path=output_path,
    fps=23  # Frames per second of your videos
)

print(f"\n✓ Converted {len(video_annotations)} video(s)")
print(f"✓ Output saved to: {output_path}")

# Example 2: Conversion without saving to file
print("\n" + "=" * 70)
print("EXAMPLE 2: Conversion without saving (returns data only)")
print("=" * 70)

video_data = coco_to_video_json(
    coco_json_path=coco_json_path,
    output_path=None,  # Don't save to file
    fps=25
)

print(f"\n✓ Converted {len(video_data)} video(s) (data in memory)")

# Display structure
for video in video_data[:1]:  # Show first video only
    print(f"\nVideo: {video['file_name']}")
    print(f"  Annotations: {len(video['annotations'])}")
    for ann in video['annotations']:
        print(f"    - {ann['question_name']} ({ann['question_type']})")
        print(f"      Answer groups: {len(ann['answer'])}")

# Example 3: Using the converted JSON for preannotation upload
print("\n" + "=" * 70)
print("EXAMPLE 3: Upload converted annotations to video project")
print("=" * 70)

# Uncomment to use:
# from labellerr import LabellerrClient
# from labellerr.core.projects import LabellerrProject
#
# client = LabellerrClient(api_key="your_api_key")
# project = LabellerrProject(client=client, project_id="your_video_project_id")
#
# # Upload the converted annotations
# result = project.upload_preannotations(
#     annotation_format="video_json",
#     annotation_file=output_path
# )
# print(f"✓ Preannotations uploaded successfully!")

print("\nDone!")
