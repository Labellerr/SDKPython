# Import base classes
from labellerr.core.files.base import LabellerrFile, LabellerrFileMeta

# Import subclasses to trigger registration
# These imports register each file type with the metaclass
from labellerr.core.files.image_file import LabellerrImageFile
from labellerr.core.files.video_file import LabellerrVideoFile

__all__ = [
    "LabellerrFile",
    "LabellerrImageFile",
    "LabellerrVideoFile",
    "LabellerrFileMeta",
]
