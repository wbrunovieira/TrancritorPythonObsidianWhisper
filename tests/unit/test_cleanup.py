"""TDD tests for run_cleanup — written before implementation."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, call

from transcritor.core.models import TranscriptionJob, JobStatus


def _make_job(
    job_id="job1",
    status=JobStatus.DONE,
    completed_at=None,
    hours_ago: float | None = 25.0,
) -> TranscriptionJob:
    if completed_at is None and hours_ago is not None:
        completed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return TranscriptionJob(
        job_id=job_id,
        status=status,
        source_type="file",
        created_at=datetime(2026, 4, 1, 10, 0, 0),
        completed_at=completed_at,
    )


@pytest.fixture
def job_store():
    store = MagicMock()
    store.list_all_ids.return_value = []
    return store


@pytest.fixture
def file_store():
    return MagicMock()


class TestRunCleanupNoJobs:
    def test_returns_zero_when_no_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        assert run_cleanup(job_store, file_store, ttl_hours=24) == 0

    def test_does_not_touch_file_store_when_no_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        run_cleanup(job_store, file_store, ttl_hours=24)
        file_store.delete_result.assert_not_called()

    def test_does_not_touch_job_store_delete_when_no_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        run_cleanup(job_store, file_store, ttl_hours=24)
        job_store.delete.assert_not_called()


class TestRunCleanupSkipsActiveJobs:
    def test_skips_pending_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.PENDING, completed_at=None, hours_ago=None)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0
        file_store.delete_result.assert_not_called()

    def test_skips_processing_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.PROCESSING, completed_at=None, hours_ago=None)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0
        file_store.delete_result.assert_not_called()

    def test_skips_done_job_completed_within_ttl(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.DONE, hours_ago=1.0)  # 1 hour ago, TTL=24h
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0
        file_store.delete_result.assert_not_called()

    def test_skips_done_job_without_completed_at(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.DONE, completed_at=None, hours_ago=None)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0


class TestRunCleanupDeletesExpiredJobs:
    def test_deletes_done_job_expired(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.DONE, hours_ago=25.0)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 1

    def test_deletes_failed_job_expired(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(status=JobStatus.FAILED, hours_ago=48.0)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 1

    def test_calls_file_store_delete_result(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(job_id="expired-job", hours_ago=30.0)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        run_cleanup(job_store, file_store, ttl_hours=24)

        file_store.delete_result.assert_called_once_with("expired-job")

    def test_calls_job_store_delete(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        job = _make_job(job_id="expired-job", hours_ago=30.0)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        run_cleanup(job_store, file_store, ttl_hours=24)

        job_store.delete.assert_called_once_with("expired-job")

    def test_naive_completed_at_treated_as_utc(self, job_store, file_store):
        """completed_at sem tzinfo (como salvo pelo job_store) deve ser tratado como UTC."""
        from transcritor.workers.tasks import run_cleanup
        naive_completed = datetime.utcnow() - timedelta(hours=30)  # naive, 30h ago
        job = _make_job(job_id="naive-job", completed_at=naive_completed, hours_ago=None)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 1


class TestRunCleanupMultipleJobs:
    def test_counts_multiple_expired_jobs(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        jobs = [
            _make_job(job_id="exp1", hours_ago=30.0),
            _make_job(job_id="exp2", hours_ago=48.0),
            _make_job(job_id="exp3", hours_ago=72.0),
        ]
        job_store.list_all_ids.return_value = [j.job_id for j in jobs]
        job_store.load.side_effect = jobs

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 3

    def test_only_deletes_expired_in_mixed_list(self, job_store, file_store):
        from transcritor.workers.tasks import run_cleanup
        expired = _make_job(job_id="expired", hours_ago=30.0)
        fresh = _make_job(job_id="fresh", hours_ago=1.0)
        pending = _make_job(job_id="pending", status=JobStatus.PENDING,
                            completed_at=None, hours_ago=None)

        job_store.list_all_ids.return_value = ["expired", "fresh", "pending"]
        job_store.load.side_effect = [expired, fresh, pending]

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 1
        file_store.delete_result.assert_called_once_with("expired")
        job_store.delete.assert_called_once_with("expired")

    def test_file_deleted_before_redis_entry(self, job_store, file_store):
        """file_store.delete_result deve ser chamado antes de job_store.delete."""
        from transcritor.workers.tasks import run_cleanup
        call_order = []
        file_store.delete_result.side_effect = lambda _: call_order.append("file")
        job_store.delete.side_effect = lambda _: call_order.append("redis")

        job = _make_job(job_id="exp", hours_ago=30.0)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        run_cleanup(job_store, file_store, ttl_hours=24)

        assert call_order == ["file", "redis"]


class TestRunCleanupEdgeCases:
    def test_job_exactly_at_ttl_boundary_is_not_deleted(self, job_store, file_store):
        """Job completado exatamente há TTL horas não deve ser deletado (< não <=)."""
        from transcritor.workers.tasks import run_cleanup
        # Completado exatamente TTL horas atrás + 1 segundo (ainda dentro do prazo)
        completed = datetime.now(timezone.utc) - timedelta(hours=24) + timedelta(seconds=1)
        job = _make_job(job_id="boundary", completed_at=completed, hours_ago=None)
        job_store.list_all_ids.return_value = [job.job_id]
        job_store.load.return_value = job

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0

    def test_continues_after_load_exception(self, job_store, file_store):
        """Se job_store.load levantar exceção, continua para o próximo job."""
        from transcritor.workers.tasks import run_cleanup
        from transcritor.core.exceptions import JobNotFoundError
        job_store.list_all_ids.return_value = ["ghost-job"]
        job_store.load.side_effect = JobNotFoundError("ghost-job")

        result = run_cleanup(job_store, file_store, ttl_hours=24)

        assert result == 0
        file_store.delete_result.assert_not_called()
