"""
This module will contain all validators for the SDK.
Example - validations like incorrect email format, incorrect data type, etc.
Invalid values that should not be accepted by the API go here.
Example - local upload file size limit, etc.
These validations should be only handle those which can't be captured by the typings.
"""

"""
Validation decorators for LabellerrClient methods
"""

import functools
import logging
from typing import Callable, List

from labellerr.core import constants
from labellerr.core.exceptions import LabellerrError


def validate_required(params: List[str]):
    """
    Decorator to validate required parameters are present and not None/empty.

    :param params: List of parameter names that are required
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            # Check required parameters
            for param in params:
                if param not in bound_args.arguments:
                    raise LabellerrError(f"Required parameter {param} is missing")

                value = bound_args.arguments[param]
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise LabellerrError(
                        f"Required parameter {param} cannot be null or empty"
                    )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_data_type(param_name: str = "data_type"):
    """
    Decorator to validate data_type parameter against allowed types.

    :param param_name: Name of the parameter to validate (default: 'data_type')
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                data_type = bound_args.arguments[param_name]
                if data_type not in constants.DATA_TYPES:
                    raise LabellerrError(
                        f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                    )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_list_not_empty(param_name: str):
    """
    Decorator to validate that a parameter is a non-empty list.

    :param param_name: Name of the parameter to validate
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                value = bound_args.arguments[param_name]
                if not isinstance(value, list):
                    raise LabellerrError(f"{param_name} must be a list")
                if len(value) == 0:
                    raise LabellerrError(f"{param_name} must be a non-empty list")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_client_id(param_name: str = "client_id"):
    """
    Decorator to validate client_id parameter.

    :param param_name: Name of the parameter to validate (default: 'client_id')
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                client_id = bound_args.arguments[param_name]
                if not isinstance(client_id, str):
                    raise LabellerrError(f"{param_name} must be a string")
                if not client_id.strip():
                    raise LabellerrError(f"{param_name} must be a non-empty string")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_questions_structure():
    """
    Decorator to validate questions structure for template creation.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if "questions" in bound_args.arguments:
                questions = bound_args.arguments["questions"]
                for i, question in enumerate(questions):
                    if not isinstance(question, dict):
                        raise LabellerrError(f"Question {i+1} must be a dictionary")

                    if "option_type" not in question:
                        raise LabellerrError(f"Question {i+1}: option_type is required")

                    if question["option_type"] not in constants.OPTION_TYPE_LIST:
                        raise LabellerrError(
                            f"Question {i+1}: option_type must be one of {constants.OPTION_TYPE_LIST}"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def log_method_call(include_params: bool = True):
    """
    Decorator to log method calls for debugging purposes.

    :param include_params: Whether to include parameter values in logs
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            method_name = func.__name__
            if include_params:
                # Get function signature to map args to parameter names
                import inspect

                sig = inspect.signature(func)
                bound_args = sig.bind(self, *args, **kwargs)
                bound_args.apply_defaults()

                # Filter out 'self' and sensitive parameters
                filtered_params = {
                    k: v
                    for k, v in bound_args.arguments.items()
                    if k != "self"
                    and "secret" not in k.lower()
                    and "key" not in k.lower()
                }
                logging.debug(f"Calling {method_name} with params: {filtered_params}")
            else:
                logging.debug(f"Calling {method_name}")

            try:
                result = func(self, *args, **kwargs)
                logging.debug(f"{method_name} completed successfully")
                return result
            except Exception as e:
                logging.error(f"{method_name} failed: {str(e)}")
                raise

        return wrapper

    return decorator


def validate_rotations_structure(param_name: str = "rotations"):
    """
    Decorator to validate rotation configuration structure.

    :param param_name: Name of the parameter to validate (default: 'rotations')
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                rotation_config = bound_args.arguments[param_name]
                if not isinstance(rotation_config, dict):
                    raise LabellerrError(f"{param_name} must be a dictionary")

                required_keys = [
                    "annotation_rotation_count",
                    "review_rotation_count",
                    "client_review_rotation_count",
                ]

                for key in required_keys:
                    if key not in rotation_config:
                        raise LabellerrError(f"{param_name} must contain '{key}'")

                    value = rotation_config[key]
                    if not isinstance(value, int) or value < 1:
                        raise LabellerrError(
                            f"{param_name}.{key} must be a positive integer"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_dataset_ids(param_name: str = "attached_datasets"):
    """
    Decorator to validate dataset IDs list.

    :param param_name: Name of the parameter to validate (default: 'attached_datasets')
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                dataset_ids = bound_args.arguments[param_name]
                if not isinstance(dataset_ids, list):
                    raise LabellerrError(f"{param_name} must be a list")
                if len(dataset_ids) == 0:
                    raise LabellerrError(
                        f"{param_name} must contain at least one dataset ID"
                    )

                for i, dataset_id in enumerate(dataset_ids):
                    if not isinstance(dataset_id, str) or not dataset_id.strip():
                        raise LabellerrError(
                            f"{param_name}[{i}] must be a non-empty string"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_uuid_format(param_name: str):
    """
    Decorator to validate UUID format for parameters.

    :param param_name: Name of the parameter to validate
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                value = bound_args.arguments[param_name]
                if value is not None:  # Allow None for optional parameters
                    import uuid as uuid_module

                    try:
                        uuid_module.UUID(str(value))
                    except (ValueError, TypeError):
                        raise LabellerrError(
                            f"{param_name} must be a valid UUID format"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_string_type(param_name: str, allow_empty: bool = False):
    """
    Decorator to validate that a parameter is a string and optionally non-empty.

    :param param_name: Name of the parameter to validate
    :param allow_empty: Whether empty strings are allowed (default: False)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                value = bound_args.arguments[param_name]
                if value is not None:  # Allow None for optional parameters
                    if not isinstance(value, str):
                        raise LabellerrError(f"{param_name} must be a string")
                    if not allow_empty and not value.strip():
                        raise LabellerrError(f"{param_name} must be a non-empty string")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_not_none(param_names: List[str]):
    """
    Decorator to validate that parameters are not None.

    :param param_names: List of parameter names that cannot be None
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if value is None:
                        raise LabellerrError(f"{param_name} cannot be null")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_file_exists(param_names: List[str]):
    """
    Decorator to validate that file parameters exist.

    :param param_names: List of parameter names that should be valid file paths
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect
            import os

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                if param_name in bound_args.arguments:
                    file_path = bound_args.arguments[param_name]
                    if file_path is not None:
                        if not os.path.exists(file_path):
                            raise LabellerrError(f"File does not exist: {file_path}")
                        if not os.path.isfile(file_path):
                            raise LabellerrError(f"Path is not a file: {file_path}")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_directory_exists(param_names: List[str]):
    """
    Decorator to validate that directory parameters exist and are accessible.

    :param param_names: List of parameter names that should be valid directory paths
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect
            import os

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                if param_name in bound_args.arguments:
                    dir_path = bound_args.arguments[param_name]
                    if dir_path is not None:
                        if not os.path.exists(dir_path):
                            raise LabellerrError(
                                f"Folder path does not exist: {dir_path}"
                            )
                        if not os.path.isdir(dir_path):
                            raise LabellerrError(f"Path is not a directory: {dir_path}")
                        if not os.access(dir_path, os.R_OK):
                            raise LabellerrError(
                                f"No read permission for folder: {dir_path}"
                            )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_file_list_or_string(param_names: List[str]):
    """
    Decorator to validate file list parameters (can be list or comma-separated string).

    :param param_names: List of parameter names that should be file lists
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect
            import os

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                if param_name in bound_args.arguments:
                    files_list = bound_args.arguments[param_name]
                    if files_list is not None:
                        # Convert string to list if necessary
                        if isinstance(files_list, str):
                            files_list = files_list.split(",")
                            # Update the bound args for the actual function
                            bound_args.arguments[param_name] = files_list
                        elif not isinstance(files_list, list):
                            raise LabellerrError(
                                f"{param_name} must be either a list or a comma-separated string"
                            )

                        if len(files_list) == 0:
                            raise LabellerrError(f"No files to upload in {param_name}")

                        # Validate each file exists
                        for file_path in files_list:
                            if not os.path.exists(file_path):
                                raise LabellerrError(
                                    f"File does not exist: {file_path}"
                                )
                            if not os.path.isfile(file_path):
                                raise LabellerrError(f"Path is not a file: {file_path}")

            # Update kwargs with potentially modified arguments
            for k, v in bound_args.arguments.items():
                if k != "self" and k in sig.parameters:
                    idx = list(sig.parameters.keys()).index(k) - 1  # -1 for self
                    if idx < len(args):
                        args = list(args)
                        args[idx] = v
                    else:
                        kwargs[k] = v

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_annotation_format(
    param_name: str = "annotation_format", file_param: str = None
):
    """
    Decorator to validate annotation format and optionally check file extension compatibility.

    :param param_name: Name of the annotation format parameter
    :param file_param: Optional name of the file parameter to check extension compatibility
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect
            import os

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                annotation_format = bound_args.arguments[param_name]
                if annotation_format is not None:
                    if annotation_format not in constants.ANNOTATION_FORMAT:
                        raise LabellerrError(
                            f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                        )

                    # Check file extension compatibility if file parameter is provided
                    if file_param and file_param in bound_args.arguments:
                        annotation_file = bound_args.arguments[file_param]
                        if (
                            annotation_file is not None
                            and annotation_format == "coco_json"
                        ):
                            file_extension = os.path.splitext(annotation_file)[
                                1
                            ].lower()
                            if file_extension != ".json":
                                raise LabellerrError(
                                    "For coco_json annotation format, the file must have a .json extension"
                                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_export_format(param_name: str = "export_format"):
    """
    Decorator to validate export format against allowed formats.

    :param param_name: Name of the parameter to validate
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                export_format = bound_args.arguments[param_name]
                if export_format is not None:
                    if export_format not in constants.LOCAL_EXPORT_FORMAT:
                        raise LabellerrError(
                            f"Invalid export_format. Must be one of {constants.LOCAL_EXPORT_FORMAT}"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_export_statuses(param_name: str = "statuses"):
    """
    Decorator to validate export statuses list.

    :param param_name: Name of the parameter to validate
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                statuses = bound_args.arguments[param_name]
                if statuses is not None:
                    if not isinstance(statuses, list):
                        raise LabellerrError(f"Invalid {param_name}. Must be an array")
                    for status in statuses:
                        if status not in constants.LOCAL_EXPORT_STATUS:
                            raise LabellerrError(
                                f"Invalid status. Must be one of {constants.LOCAL_EXPORT_STATUS}"
                            )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_scope(param_name: str = "scope"):
    """
    Decorator to validate scope parameter against allowed scopes.

    :param param_name: Name of the parameter to validate
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                scope = bound_args.arguments[param_name]
                if scope is not None:
                    if scope not in constants.SCOPE_LIST:
                        raise LabellerrError(
                            f"scope must be one of {', '.join(constants.SCOPE_LIST)}"
                        )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_upload_method_exclusive(
    file_param: str = "files_to_upload", folder_param: str = "folder_to_upload"
):
    """
    Decorator to validate that only one upload method is specified.

    :param file_param: Name of the files parameter
    :param folder_param: Name of the folder parameter
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            has_files = (
                file_param in bound_args.arguments
                and bound_args.arguments[file_param] is not None
            )
            has_folder = (
                folder_param in bound_args.arguments
                and bound_args.arguments[folder_param] is not None
            )

            if has_files and has_folder:
                raise LabellerrError(
                    f"Cannot provide both {file_param} and {folder_param}"
                )

            if not has_files and not has_folder:
                raise LabellerrError(
                    f"Either {file_param} or {folder_param} must be provided"
                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_file_limits(total_count_limit: int = None, total_size_limit: int = None):
    """
    Decorator to validate file count and size limits.

    :param total_count_limit: Maximum number of files allowed
    :param total_size_limit: Maximum total size in bytes
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # This decorator is more complex as it needs to work with method-specific logic
            # For now, we'll delegate to the method to perform the actual counting
            # The validation will be done within the method itself
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def validate_business_logic_rotation_config():
    """
    Decorator to validate rotation config business rules.
    This uses the existing client_utils validation.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()

            # Look for rotation config in various possible parameter names
            rotation_config = None
            for param_name in ["rotation_config", "rotations"]:
                if param_name in bound_args.arguments:
                    rotation_config = bound_args.arguments[param_name]
                    break

            if rotation_config is not None:
                from ..utils import validate_rotation_config

                validate_rotation_config(rotation_config)

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator to standardize API error handling.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except LabellerrError:
            # Re-raise LabellerrError as-is
            raise
        except Exception as e:
            method_name = func.__name__
            logging.error(f"Unexpected error in {method_name}: {e}")
            raise

    return wrapper


def auto_log_and_handle_errors(
    include_params: bool = False, exclude_methods: List[str] = None
):
    """
    Class decorator that automatically applies logging and error handling to all public methods.

    :param include_params: Whether to include parameters in log messages (default: False)
    :param exclude_methods: List of method names to exclude from auto-decoration
    """
    if exclude_methods is None:
        exclude_methods = []

    def class_decorator(cls):
        import inspect

        # Get all methods in the class
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            # Skip private methods, dunder methods, and excluded methods
            if name.startswith("_") or name in exclude_methods:
                continue

            # Check if method already has decorators we want to apply
            has_log_decorator = hasattr(method, "__wrapped__")
            has_error_decorator = hasattr(method, "__wrapped__")

            # Apply decorators if not already present
            if not has_log_decorator and not has_error_decorator:
                # Apply both decorators: error handling first, then logging
                decorated_method = log_method_call(include_params=include_params)(
                    method
                )
                decorated_method = handle_api_errors(decorated_method)
                setattr(cls, name, decorated_method)

        return cls

    return class_decorator


def auto_log_and_handle_errors_async(
    include_params: bool = False, exclude_methods: List[str] = None
):
    """
    Class decorator that automatically applies logging and error handling to all public async methods.

    :param include_params: Whether to include parameters in log messages (default: False)
    :param exclude_methods: List of method names to exclude from auto-decoration
    """
    if exclude_methods is None:
        exclude_methods = []

    def async_log_decorator(include_params: bool = True):
        """Async version of log_method_call decorator."""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                method_name = func.__name__
                if include_params:
                    import inspect

                    sig = inspect.signature(func)
                    bound_args = sig.bind(self, *args, **kwargs)
                    bound_args.apply_defaults()

                    filtered_params = {
                        k: v
                        for k, v in bound_args.arguments.items()
                        if k != "self"
                        and "secret" not in k.lower()
                        and "key" not in k.lower()
                    }
                    logging.debug(
                        f"Calling {method_name} with params: {filtered_params}"
                    )
                else:
                    logging.debug(f"Calling {method_name}")

                try:
                    result = await func(self, *args, **kwargs)
                    logging.debug(f"{method_name} completed successfully")
                    return result
                except Exception as e:
                    logging.error(f"{method_name} failed: {str(e)}")
                    raise

            return wrapper

        return decorator

    def async_error_handler(func: Callable) -> Callable:
        """Async version of handle_api_errors decorator."""

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except LabellerrError:
                raise
            except Exception as e:
                method_name = func.__name__
                logging.error(f"Unexpected error in {method_name}: {e}")
                raise

        return wrapper

    def class_decorator(cls):
        import inspect

        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("_") or name in exclude_methods:
                continue

            # Only apply to async methods
            if inspect.iscoroutinefunction(method):
                has_decorators = hasattr(method, "__wrapped__")
                if not has_decorators:
                    decorated_method = async_log_decorator(
                        include_params=include_params
                    )(method)
                    decorated_method = async_error_handler(decorated_method)
                    setattr(cls, name, decorated_method)

        return cls

    return class_decorator
