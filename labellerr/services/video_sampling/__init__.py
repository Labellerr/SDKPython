"""All the code for video sampling will go here.

All algorithms for video sampling  will go in separate files.
"""

from .ffmpeg_detect import FFMPEGSceneDetect
from .pyscene_detect import PySceneDetect
from .ssim_detect import SSIMSceneDetect

__all__ = [
    "FFMPEGSceneDetect",
    "PySceneDetect",
    "SSIMSceneDetect",
]
