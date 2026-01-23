from ..schemas import DatasetDataType
from .base import LabellerrDataset, LabellerrDatasetMeta


class TextDataset(LabellerrDataset):
    def fetch_files(self):
        print("Yo I am gonna fetch some files!")


LabellerrDatasetMeta._register(DatasetDataType.text, TextDataset)
