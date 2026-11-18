"""Unit tests for pre-annotation job status, waiting and non-blocking upload."""

import contextvars
import threading
import time
from unittest.mock import MagicMock

import pytest
import requests

from labellerr.core.exceptions import (
    AuthenticationError,
    JobFailedError,
    JobTimeoutError,
    LabellerrError,
    ServerError,
)
from labellerr.core import utils as poll_utils
from labellerr.core.projects.base import PREANNOTATION_TIMEOUT
from labellerr.core.projects.image_project import ImageProject

BASE = "https://custom.example.test"
# Read before the autouse fixture lowers it.
DEFAULT_FLOOR = poll_utils.MIN_POLL_INTERVAL


def _status(value):
    return {"response": {"status": value}}


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    # The tests poll every 0.01 s; the SDK's floor is 0.5 s.
    monkeypatch.setattr(poll_utils, "MIN_POLL_INTERVAL", 0.0)


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

        with pytest.raises(JobFailedError) as exc:
            project.preannotation_job_status("job-1")

        assert isinstance(exc.value, LabellerrError)
        assert exc.value.job_id == "job-1"
        assert exc.value.response_body == _status("failed")


@pytest.mark.unit
class TestPollingValidation:
    @pytest.mark.parametrize(
        "interval", [0, -1, 0.1, float("nan"), float("inf"), True, "2", None]
    )
    def test_bad_interval_is_rejected(self, project, client, monkeypatch, interval):
        monkeypatch.setattr(poll_utils, "MIN_POLL_INTERVAL", 0.5)

        with pytest.raises(LabellerrError, match="interval"):
            project.wait_for_preannotation_job("job-1", interval=interval)
        with pytest.raises(LabellerrError, match="interval"):
            project.preannotation_job_status_async("job-1", interval=interval)
        client.make_request.assert_not_called()

    @pytest.mark.parametrize("timeout", [-1, -0.01, float("nan"), "10", True])
    def test_bad_timeout_is_rejected(self, project, client, timeout):
        with pytest.raises(LabellerrError, match="timeout"):
            project.wait_for_preannotation_job("job-1", timeout=timeout, interval=1)
        client.make_request.assert_not_called()

    def test_default_floor_is_half_a_second(self):
        assert DEFAULT_FLOOR == 0.5

    def test_zero_timeout_and_none_are_accepted(self, project, client):
        client.make_request.return_value = _status("completed")

        assert project.wait_for_preannotation_job("job-1", timeout=0, interval=1)
        assert project.wait_for_preannotation_job("job-1", timeout=None, interval=1)


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

        with pytest.raises(JobFailedError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert str(exc.value).startswith("Failed to get preannotation job status:")

    def test_untyped_errors_pass_through_unwrapped(self, project, client):
        client.make_request.side_effect = LabellerrError("Expected JSON response")

        with pytest.raises(LabellerrError) as exc:
            project.wait_for_preannotation_job("job-1", timeout=5, interval=0.01)

        assert str(exc.value) == "Expected JSON response"
        assert client.make_request.call_count == 1

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

    def test_thread_sees_the_callers_context_vars(self, project, client):
        current_user = contextvars.ContextVar("current_user", default=None)
        seen = []

        def fake_request(*args, **kwargs):
            seen.append(current_user.get())
            return _status("completed")

        client.make_request.side_effect = fake_request
        current_user.set("alice")

        project.preannotation_job_status_async("job-1", interval=0.01).result(timeout=5)

        assert seen == ["alice"]

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

    def test_start_upload_returns_job_id_without_polling(
        self, project, client, annotation_file
    ):
        client.make_request.return_value = MagicMock()

        job_id = project.start_preannotation_upload("coco_json", annotation_file)

        assert job_id == "job-9"
        methods = [c.args[0] for c in client.make_request.call_args_list]
        assert methods == ["POST"]

    def test_start_upload_then_single_status_call(
        self, project, client, annotation_file
    ):
        # How labellerr-mcp follows a job: start it, then check it on demand.
        client.make_request.side_effect = [MagicMock(), _status("processing")]

        job_id = project.start_preannotation_upload("coco_json", annotation_file)
        status = project.preannotation_job_status(job_id)

        assert status == _status("processing")
        assert "job_id=job-9" in client.make_request.call_args.args[1]

    def test_invalid_conf_bucket_is_a_labellerr_error(
        self, project, client, annotation_file
    ):
        with pytest.raises(LabellerrError, match="confidence bucket"):
            project.start_preannotation_upload(
                "coco_json", annotation_file, conf_bucket="huge"
            )
        client.make_request.assert_not_called()

    @pytest.mark.parametrize(
        "kwargs", [{"interval": 0}, {"interval": -1}, {"timeout": -1}]
    )
    def test_invalid_polling_is_rejected_before_the_upload(
        self, project, client, annotation_file, kwargs, monkeypatch
    ):
        monkeypatch.setattr(poll_utils, "MIN_POLL_INTERVAL", 0.5)
        with pytest.raises(LabellerrError):
            project.upload_preannotations("coco_json", annotation_file, **kwargs)
        client.make_request.assert_not_called()

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
