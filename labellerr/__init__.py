"""Labellerr SDK - Python client for Labellerr API."""

from .async_client import AsyncLabellerrClient
from .client import LabellerrClient
from .exceptions import LabellerrError

# Get version from package metadata
try:
    import importlib.metadata as _importlib_metadata
except ImportError:  # Python < 3.8
    import importlib_metadata as _importlib_metadata  # type: ignore[no-redef]

try:
    __version__ = _importlib_metadata.version("labellerr-sdk")
except Exception:
    __version__ = "unknown"

__all__ = [
    "__version__",
    "LabellerrClient",
    "AsyncLabellerrClient",
    "LabellerrError",
]
