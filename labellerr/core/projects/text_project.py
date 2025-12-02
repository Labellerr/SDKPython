from .base import LabellerrProject, LabellerrProjectMeta


class TextProject(LabellerrProject):

    pass


LabellerrProjectMeta._register("text", TextProject)
