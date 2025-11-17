# labellerr/exceptions.py


class LabellerrError(Exception):
    """Custom exception for Labellerr SDK errors."""

    pass


class InvalidDatasetError(Exception):
    """Custom exception for invalid dataset errors."""

    pass


class InvalidProjectError(Exception):
    """Custom exception for invalid project errors."""

    pass


class InvalidDatasetIDError(Exception):
    pass


class InvalidConnectionError(Exception):
    pass


class InvalidAnnotationTemplateError(Exception):
    """Custom exception for invalid annotation template errors."""

    pass
