from .base import LabellerrProject, LabellerrProjectMeta


class ImageProject(LabellerrProject):

    pass


LabellerrProjectMeta._register("image", ImageProject)
