"""All the code for video sampling will go here.

All algorithms for video sampling  will go in separate files.
"""

from .ffmpeg import FFMPEGSceneDetect
from .pyscene_detect import PySceneDetect
from .ssim import SSIMSceneDetect

__all__ = [
    "FFMPEGSceneDetect",
    "PySceneDetect",
    "SSIMSceneDetect",
]
