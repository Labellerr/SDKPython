"""
Test script to convert COCO JSON export to Video JSON format.
Tests the import from labellerr.services.video_sampling module.
"""

from labellerr.services.video_sampling import coco_to_video_json

# Input COCO JSON file path
coco_json_path = r"D:\Professional\Labellerr_SDK\SDKPython\labellerr\notebooks\export-#huy0VWY14med4McdKd6h.json"

# Output Video JSON file path
output_path = r"D:\Professional\Labellerr_SDK\SDKPython\labellerr\notebooks\video_keyframe_annotations.json"

# Convert COCO to Video JSON format
# FPS will be extracted from filenames if available
# Falls back to default_fps=25 if not found in filename
video_annotations = coco_to_video_json(
    coco_json_path=coco_json_path, output_path=output_path, default_fps=25
)

print(f"\n✅ Conversion complete!")
print(f"📁 Output saved to: {output_path}")
print(f"📊 Total videos processed: {len(video_annotations)}")

# Print summary for each video
for video in video_annotations:
    print(f"\n  🎬 {video['file_name']}")
    print(f"     Annotations: {len(video['annotations'])}")
