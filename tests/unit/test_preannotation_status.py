"""Unit tests for pre-annotation job status, waiting and non-blocking upload."""

import threading
import time
from unittest.mock import MagicMock

import pytest
import requests

from labellerr.core.exceptions import (
    AuthenticationError,
    JobTimeoutError,
    LabellerrError,
    ServerError,
)
from labellerr.core.projects.base import PREANNOTATION_TIMEOUT
from labellerr.core.projects.image_project import ImageProject

BASE = "https://custom.example.test"


def _status(value):
    return {"response": {"status": value}}


@pytest.fixture
def client():
    mock = MagicMock()
    mock.client_id = "client-1"
    mock.base_url = BASE
    return mock


@pytest.fixture
def project(client):
    return ImageProject(client, "proj-1", project_data={"data_type": "image"})


@pytest.mark.unit
class TestStatus:
    def test_single_call_returns_response(self, project, client):
        client.make_request.return_value = _status("processing")

        result = project.preannotation_job_status("job-1")

        assert result == _status("processing")
        assert client.make_request.call_count == 1
        method, url = client.make_request.call_args.args[:2]
        assert method == "GET"
        assert url.startswith(f"{BASE}/actions/upload_answers_status?")
        assert "job_id=job-1" in url and "project_id=proj-1" in url

    def test_failed_raises(self, project, client):
        client.make_request.return_value = _status("failed")

        with pytest.raises(LabellerrError):
            project.preannotation_job_status("job-1")


@pytest.mark.unit
class TestWait:
    def test_returns_on_completed(self, project, client):
        client.make_request.side_effect = [
            _status("processing"),
            _status("processing"),
            _status("completed"),
        ]

        result = project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert result == _status("completed")
        assert client.make_request.call_count == 3

    def test_timeout_names_job_id(self, project, client):
        client.make_request.return_value = _status("processing")

        with pytest.raises(JobTimeoutError) as exc:
            project.wait_for_preannotation_job("job-xyz", timeout=0.05, interval=0.01)

        assert "job-xyz" in str(exc.value)
        assert "0.05" in str(exc.value)
        assert isinstance(exc.value, LabellerrError)

    def test_failed_raises_immediately(self, project, client):
        client.make_request.return_value = _status("failed")

        with pytest.raises(LabellerrError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert not isinstance(exc.value, JobTimeoutError)
        assert client.make_request.call_count == 1

    def test_failed_message_keeps_the_blocking_prefix(self, project, client):
        client.make_request.return_value = _status("failed")

        with pytest.raises(LabellerrError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert str(exc.value).startswith("Failed to get preannotation job status:")

    def test_typed_errors_are_not_rewrapped(self, project, client):
        client.make_request.side_effect = AuthenticationError("bad token")

        with pytest.raises(AuthenticationError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert str(exc.value) == "bad token"

    def test_default_timeout_is_one_hour(self):
        assert PREANNOTATION_TIMEOUT == 3600.0

    def test_auth_error_propagates_at_once(self, project, client):
        client.make_request.side_effect = AuthenticationError("bad token")

        with pytest.raises(AuthenticationError):
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert client.make_request.call_count == 1

    def test_transient_errors_are_retried(self, project, client):
        client.make_request.side_effect = [
            ServerError("boom"),
            requests.exceptions.ConnectionError("down"),
            _status("completed"),
        ]

        result = project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert result == _status("completed")

    def test_persistent_transient_error_ends_in_timeout(self, project, client):
        client.make_request.side_effect = ServerError("boom")

        with pytest.raises(JobTimeoutError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=0.05, interval=0.01)

        assert isinstance(exc.value.__cause__, ServerError)


@pytest.mark.unit
class TestAsync:
    def test_future_returns_before_job_completes(self, project, client):
        release = threading.Event()

        def fake_request(*args, **kwargs):
            return _status("completed" if release.is_set() else "processing")

        client.make_request.side_effect = fake_request

        started = time.monotonic()
        future = project.preannotation_job_status_async(
            "job-1", timeout=5, interval=0.01
        )
        assert time.monotonic() - started < 1
        assert not future.done()

        release.set()
        assert future.result(timeout=5) == _status("completed")

    def test_future_raises_on_timeout(self, project, client):
        client.make_request.return_value = _status("processing")

        future = project.preannotation_job_status_async(
            "job-1", timeout=0.05, interval=0.01
        )

        with pytest.raises(JobTimeoutError):
            future.result(timeout=5)

    def test_future_wraps_unexpected_errors(self, project, client):
        client.make_request.side_effect = ValueError("odd")

        future = project.preannotation_job_status_async("job-1", timeout=1)

        with pytest.raises(LabellerrError):
            future.result(timeout=5)

    def test_thread_ends_after_job_finishes(self, project, client):
        client.make_request.return_value = _status("completed")

        future = project.preannotation_job_status_async("job-1", interval=0.01)
        future.result(timeout=5)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and any(
            t.name == "preannotation-job-job-1" for t in threading.enumerate()
        ):
            time.sleep(0.01)

        assert not any(
            t.name == "preannotation-job-job-1" for t in threading.enumerate()
        )


@pytest.mark.unit
class TestUpload:
    @pytest.fixture
    def annotation_file(self, tmp_path):
        path = tmp_path / "ann.json"
        path.write_text("{}")
        return str(path)

    @pytest.fixture(autouse=True)
    def _upload_response(self, client):
        client.handle_upload_response.return_value = {"response": {"job_id": "job-9"}}

    def _route(self, client, release):
        def fake_request(method, url, **kwargs):
            if method == "POST":
                return MagicMock()
            return _status("completed" if release.is_set() else "processing")

        client.make_request.side_effect = fake_request

    def test_async_returns_before_job_completes(self, project, client, annotation_file):
        release = threading.Event()
        self._route(client, release)

        started = time.monotonic()
        future = project.upload_preannotations(
            "coco_json", annotation_file, _async=True, timeout=5, interval=0.01
        )

        assert time.monotonic() - started < 1
        assert not future.done()
        release.set()
        assert future.result(timeout=5) == _status("completed")

    def test_sync_blocks_with_timeout(self, project, client, annotation_file):
        self._route(client, threading.Event())

        with pytest.raises(JobTimeoutError):
            project.upload_preannotations(
                "coco_json", annotation_file, timeout=0.05, interval=0.01
            )

    def test_urls_use_client_base_url_and_no_email_header(
        self, project, client, annotation_file
    ):
        release = threading.Event()
        release.set()
        self._route(client, release)

        project.upload_preannotations(
            "coco_json", annotation_file, timeout=5, interval=0.01
        )

        calls = client.make_request.call_args_list
        assert all(c.args[1].startswith(BASE) for c in calls)
        post = next(c for c in calls if c.args[0] == "POST")
        headers = post.kwargs.get("extra_headers") or {}
        assert not any(k.lower() == "email_id" for k in headers)
