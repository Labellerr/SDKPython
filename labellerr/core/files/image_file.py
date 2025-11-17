from labellerr.core.files.base import LabellerrFile


class LabellerrImageFile(LabellerrFile):
    pass


LabellerrFile._register("image", LabellerrImageFile)
