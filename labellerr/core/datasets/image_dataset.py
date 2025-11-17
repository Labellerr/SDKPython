from ..schemas import DatasetDataType
from .base import LabellerrDataset, LabellerrDatasetMeta


class ImageDataset(LabellerrDataset):
    pass


LabellerrDatasetMeta._register(DatasetDataType.image, ImageDataset)
