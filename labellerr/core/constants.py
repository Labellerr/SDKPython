BASE_URL = "https://api.labellerr.com"
ALLOWED_ORIGINS = "https://pro.labellerr.com"


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
