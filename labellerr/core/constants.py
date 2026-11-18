# Defaults only. The environment (LABELLERR_BASE_URL / LABELLERR_ORIGIN) is read when a
# client is created, by ``labellerr.core.settings.Settings.from_env``; requests use
# ``client.base_url`` and the client's settings, not these constants.
DEFAULT_BASE_URL = "https://api.labellerr.com"
# Origin sent with API-key credentials (the web app's origin).
DEFAULT_ORIGIN = "https://pro.labellerr.com"
# Origin sent with a user access token. The gateway keeps one session per email and
# origin, so a token client on the web app's origin would sign the user out of it.
TOKEN_DEFAULT_ORIGIN = "https://sdk.labellerr.com"


FILE_BATCH_SIZE = 15 * 1024 * 1024  # 15MB
FILE_BATCH_COUNT = 900
TOTAL_FILES_SIZE_LIMIT_PER_DATASET = 2.5 * 1024 * 1024 * 1024  # 2.5GB
TOTAL_FILES_COUNT_LIMIT_PER_DATASET = 2500

ANNOTATION_FORMAT = ["json", "coco_json", "csv", "png"]
LOCAL_EXPORT_FORMAT = ["json", "coco_json", "csv", "png"]
LOCAL_EXPORT_STATUS = [
    "review",
    "r_assigned",
    "client_review",
    "cr_assigned",
    "accepted",
]

DATA_TYPE_FILE_EXT = {
    "image": [".jpg", ".jpeg", ".png", ".tiff"],
    "video": [".mp4"],
    "audio": [".mp3", ".wav"],
    "document": [".pdf"],
    "text": [".txt"],
}

SCOPE_LIST = ["project", "client", "public"]
DEFAULT_PAGE_SIZE = 10
OPTION_TYPE_LIST = [
    "input",
    "radio",
    "boolean",
    "select",
    "dropdown",
    "stt",
    "imc",
    "BoundingBox",
    "polygon",
    "dot",
    "audio",
]
cdn_server_address = "cdn-951134552678.us-central1.run.app:443"


def __getattr__(name):
    """
    Legacy names ``BASE_URL`` and ``ALLOWED_ORIGINS``, kept for external callers
    (labellerr-mcp still reads them). Reading either one warns: use
    ``client.base_url`` / ``client.settings`` instead.

    They resolve from the environment each time they are read (nothing is read at
    import). The SDK itself uses ``DEFAULT_BASE_URL`` / ``DEFAULT_ORIGIN``.

    Note: because this module defines ``__getattr__``, mypy accepts any attribute
    name on it, so a typo such as ``constants.DATA_TYPES`` is not caught statically.
    """
    import os
    import warnings

    if name in ("BASE_URL", "ALLOWED_ORIGINS"):
        replacement = "client.base_url" if name == "BASE_URL" else "client.settings"
        warnings.warn(
            f"labellerr.core.constants.{name} is deprecated; use {replacement}",
            DeprecationWarning,
            stacklevel=2,
        )
    if name == "BASE_URL":
        value = (os.environ.get("LABELLERR_BASE_URL") or "").strip().rstrip("/")
        return value or DEFAULT_BASE_URL
    if name == "ALLOWED_ORIGINS":
        value = (os.environ.get("LABELLERR_ORIGIN") or "").strip()
        return value or DEFAULT_ORIGIN
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
