"""
Export class for handling export operations with status tracking and polling.
"""

from typing import TYPE_CHECKING, Dict, Any, Optional
import logging
import json

if TYPE_CHECKING:
    from ..projects.base import LabellerrProject


class Export:
    """
    Represents an export job with status tracking and polling capabilities.

    Usage:
        # Get report_id
        export = project.create_export(config)
        print(export.report_id)

        # Check status once
        current_status = export.status

        # Poll until completion
        final_status = export.status()
    """

    def __init__(self, report_id: str, project: "LabellerrProject"):
        self._report_id = report_id
        self._project = project

    @property
    def report_id(self) -> str:
        """Get the export report ID."""
        return self._report_id

    @property
    def _status(self) -> Dict[str, Any]:
        """Get current export status (single check)."""
        response = self._project.check_export_status([self._report_id])
        if isinstance(response, str):
            response = json.loads(response)

        for status_item in response.get("status", []):
            if status_item.get("report_id") == self._report_id:
                return status_item
        return {}

    def status(
        self,
        interval: float = 2.0,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Poll export status until completion."""
        from ..utils import poll

        def get_status():
            response = self._project.check_export_status([self._report_id])
            if isinstance(response, str):
                response = json.loads(response)
            return response

        def is_completed(response_data):
            for status_item in response_data.get("status", []):
                if status_item.get("report_id") == self._report_id:
                    if status_item.get("export_status", "").lower() == "failed":
                        return on_failure(response_data)
                    return (
                        status_item.get("is_completed", False)
                        and status_item.get("export_status", "").lower() == "created"
                    )
            return False

        def on_success(response_data):
            logging.info(f"Export {self._report_id} completed successfully!")
            return response_data

        def on_failure(response_data):
            logging.error(f"Export {self._report_id} failed: {response_data}")
            return response_data

        return poll(
            function=get_status,
            condition=is_completed,
            interval=interval,
            timeout=timeout,
            max_retries=max_retries,
            on_success=on_success,
        )

    def __repr__(self) -> str:
        return f"Export(report_id='{self._report_id}')"
