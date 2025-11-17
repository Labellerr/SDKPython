"""
Base custom types and validators for schemas.
"""

import os


class NonEmptyStr(str):
    """Custom string type that cannot be empty or whitespace-only."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class FilePathStr(str):
    """File path that must exist and be a valid file."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not os.path.exists(v):
            raise ValueError(f"file does not exist: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"path is not a file: {v}")
        return v


class DirPathStr(str):
    """Directory path that must exist and be accessible."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("must be a string")
        if not os.path.exists(v):
            raise ValueError(f"folder path does not exist: {v}")
        if not os.path.isdir(v):
            raise ValueError(f"path is not a directory: {v}")
        if not os.access(v, os.R_OK):
            raise ValueError(f"no read permission for folder: {v}")
        return v
