import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from transcritor.storage.job_store import JobStore
from transcritor.core.models import TranscriptionJob, JobStatus
from transcritor.core.exceptions import JobNotFoundError


def _make_job(**kwargs) -> TranscriptionJob:
    defaults = dict(
        job_id="abc123",
        status=JobStatus.PENDING,
        source_type="file",
        created_at=datetime(2026, 4, 11, 10, 0, 0),
    )
    return TranscriptionJob(**{**defaults, **kwargs})


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def store(mock_redis):
    return JobStore(mock_redis)


class TestJobStoreSave:
    def test_save_calls_redis_set(self, store, mock_redis):
        store.save(_make_job())
        mock_redis.set.assert_called_once()

    def test_save_key_contains_job_id(self, store, mock_redis):
        store.save(_make_job(job_id="abc123"))
        key = mock_redis.set.call_args[0][0]
        assert "abc123" in key

    def test_save_value_is_valid_json(self, store, mock_redis):
        store.save(_make_job())
        value = mock_redis.set.call_args[0][1]
        data = json.loads(value)
        assert data["job_id"] == "abc123"

    def test_save_json_contains_status(self, store, mock_redis):
        store.save(_make_job(status=JobStatus.PROCESSING))
        value = mock_redis.set.call_args[0][1]
        data = json.loads(value)
        assert data["status"] == "processing"


class TestJobStoreLoad:
    def test_load_returns_job_with_correct_id(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        loaded = store.load("abc123")
        assert loaded.job_id == "abc123"

    def test_load_returns_job_with_correct_status(self, store, mock_redis):
        job = _make_job(status=JobStatus.PROCESSING)
        mock_redis.get.return_value = job.model_dump_json().encode()
        loaded = store.load("abc123")
        assert loaded.status == JobStatus.PROCESSING

    def test_load_raises_job_not_found_when_missing(self, store, mock_redis):
        mock_redis.get.return_value = None
        with pytest.raises(JobNotFoundError):
            store.load("nonexistent")

    def test_load_error_contains_job_id(self, store, mock_redis):
        mock_redis.get.return_value = None
        with pytest.raises(JobNotFoundError, match="missing-job"):
            store.load("missing-job")

    def test_load_uses_correct_redis_key(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.load("abc123")
        key = mock_redis.get.call_args[0][0]
        assert "abc123" in key


class TestJobStoreUpdateStatus:
    def test_update_status_to_done(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.update_status("abc123", JobStatus.DONE)
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["status"] == "done"

    def test_update_status_sets_completed_at_when_done(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.update_status("abc123", JobStatus.DONE)
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["completed_at"] is not None

    def test_update_status_sets_completed_at_when_failed(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.update_status("abc123", JobStatus.FAILED, error="boom")
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["completed_at"] is not None

    def test_update_status_does_not_set_completed_at_when_processing(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.update_status("abc123", JobStatus.PROCESSING)
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["completed_at"] is None

    def test_update_status_saves_error_message(self, store, mock_redis):
        job = _make_job()
        mock_redis.get.return_value = job.model_dump_json().encode()
        store.update_status("abc123", JobStatus.FAILED, error="something broke")
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["error"] == "something broke"
