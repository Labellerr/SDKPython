from ..schemas import DatasetDataType
from .base import LabellerrProject, LabellerrProjectMeta


class DocucmentProject(LabellerrProject):

    def fetch_datasets(self):
        print("Yo I am gonna fetch some datasets!")


LabellerrProjectMeta._register(DatasetDataType.document, DocucmentProject)
