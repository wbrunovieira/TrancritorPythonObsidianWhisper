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

    def test_save_calls_zadd_for_sorted_set(self, store, mock_redis):
        store.save(_make_job(job_id="abc123"))
        mock_redis.zadd.assert_called_once()
        key = mock_redis.zadd.call_args[0][0]
        assert key == "jobs:all"

    def test_save_zadd_includes_job_id(self, store, mock_redis):
        store.save(_make_job(job_id="abc123"))
        mapping = mock_redis.zadd.call_args[0][1]
        assert "abc123" in mapping


class TestJobStoreListJobs:
    def _setup_list(self, mock_redis, job_ids: list[str], total: int | None = None):
        """Configura mock_redis.zcard e zrevrange para simular uma lista de jobs."""
        jobs = {jid: _make_job(job_id=jid) for jid in job_ids}
        mock_redis.zcard.return_value = total if total is not None else len(job_ids)
        mock_redis.zrevrange.return_value = [jid.encode() for jid in job_ids]
        mock_redis.get.side_effect = lambda key: jobs[key.split(":")[1]].model_dump_json().encode()

    def test_returns_dict_with_jobs_key(self, store, mock_redis):
        self._setup_list(mock_redis, [])
        result = store.list_jobs()
        assert "jobs" in result

    def test_returns_empty_list_when_no_jobs(self, store, mock_redis):
        self._setup_list(mock_redis, [])
        result = store.list_jobs()
        assert result["jobs"] == []

    def test_returns_total(self, store, mock_redis):
        self._setup_list(mock_redis, ["a", "b"], total=2)
        result = store.list_jobs()
        assert result["total"] == 2

    def test_returns_page_and_page_size(self, store, mock_redis):
        self._setup_list(mock_redis, [])
        result = store.list_jobs(page=2, page_size=10)
        assert result["page"] == 2
        assert result["page_size"] == 10

    def test_returns_correct_number_of_jobs(self, store, mock_redis):
        self._setup_list(mock_redis, ["a", "b", "c"])
        result = store.list_jobs()
        assert len(result["jobs"]) == 3

    def test_calls_zrevrange_with_correct_range(self, store, mock_redis):
        self._setup_list(mock_redis, [])
        store.list_jobs(page=1, page_size=20)
        mock_redis.zrevrange.assert_called_once_with("jobs:all", 0, 19)

    def test_second_page_uses_correct_offset(self, store, mock_redis):
        self._setup_list(mock_redis, [])
        store.list_jobs(page=2, page_size=5)
        mock_redis.zrevrange.assert_called_once_with("jobs:all", 5, 9)
