import pytest
from datetime import datetime

from transcritor.services.transcription_service import TranscriptionService
from transcritor.core.models import TranscriptionJob, TranscriptionResult, JobStatus
from transcritor.core.exceptions import JobNotFoundError, JobNotReadyError, TranscriptionError


# ---------------------------------------------------------------------------
# Fakes — substituem Redis e filesystem nos testes unitários
# ---------------------------------------------------------------------------

class FakeJobStore:
    def __init__(self):
        self._jobs: dict[str, TranscriptionJob] = {}

    def save(self, job: TranscriptionJob) -> None:
        self._jobs[job.job_id] = job

    def load(self, job_id: str) -> TranscriptionJob:
        if job_id not in self._jobs:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self._jobs[job_id]

    def update_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None:
        job = self.load(job_id)
        updates: dict = {"status": status}
        if error is not None:
            updates["error"] = error
        if status in (JobStatus.DONE, JobStatus.FAILED):
            updates["completed_at"] = datetime.now()
        self._jobs[job_id] = job.model_copy(update=updates)


class FakeFileStore:
    def __init__(self):
        self._results: dict[str, TranscriptionResult] = {}

    def save_result(self, job_id: str, result: TranscriptionResult) -> None:
        self._results[job_id] = result

    def load_result(self, job_id: str) -> TranscriptionResult:
        if job_id not in self._results:
            raise TranscriptionError(f"Result not found: {job_id}")
        return self._results[job_id]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dispatched():
    return []


@pytest.fixture
def job_store():
    return FakeJobStore()


@pytest.fixture
def file_store():
    return FakeFileStore()


@pytest.fixture
def service(job_store, file_store, dispatched):
    def fake_dispatch(job_id, source_type, source_kwargs):
        dispatched.append((job_id, source_type, source_kwargs))

    return TranscriptionService(
        file_store=file_store,
        job_store=job_store,
        task_dispatcher=fake_dispatch,
    )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestSubmitJob:
    def test_returns_job_with_pending_status(self, service):
        job = service.submit_job("file", {"path": "/audio.wav"})
        assert job.status == JobStatus.PENDING

    def test_returns_job_with_non_empty_id(self, service):
        job = service.submit_job("file", {"path": "/audio.wav"})
        assert job.job_id
        assert len(job.job_id) > 0

    def test_two_jobs_have_different_ids(self, service):
        job1 = service.submit_job("file", {"path": "/a.wav"})
        job2 = service.submit_job("file", {"path": "/b.wav"})
        assert job1.job_id != job2.job_id

    def test_dispatches_job_to_queue(self, service, dispatched):
        job = service.submit_job("file", {"path": "/audio.wav"})
        assert len(dispatched) == 1
        assert dispatched[0][0] == job.job_id

    def test_dispatches_correct_source_type(self, service, dispatched):
        service.submit_job("video", {"path": "/video.mp4"})
        assert dispatched[0][1] == "video"

    def test_dispatches_correct_source_kwargs(self, service, dispatched):
        service.submit_job("url", {"url": "https://example.com/audio.mp3"})
        assert dispatched[0][2] == {"url": "https://example.com/audio.mp3"}

    def test_persists_job_to_store(self, service, job_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        stored = job_store.load(job.job_id)
        assert stored.job_id == job.job_id

    def test_sets_created_at(self, service):
        job = service.submit_job("file", {"path": "/audio.wav"})
        assert job.created_at is not None


class TestGetJob:
    def test_returns_job_with_current_status(self, service, job_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        job_store.update_status(job.job_id, JobStatus.PROCESSING)
        retrieved = service.get_job(job.job_id)
        assert retrieved.status == JobStatus.PROCESSING

    def test_raises_for_unknown_id(self, service):
        with pytest.raises(JobNotFoundError):
            service.get_job("nonexistent-id")

    def test_reflects_done_status(self, service, job_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        job_store.update_status(job.job_id, JobStatus.DONE)
        retrieved = service.get_job(job.job_id)
        assert retrieved.status == JobStatus.DONE

    def test_reflects_failed_status_with_error(self, service, job_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        job_store.update_status(job.job_id, JobStatus.FAILED, error="timeout")
        retrieved = service.get_job(job.job_id)
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error == "timeout"


class TestGetResult:
    def test_returns_text_when_done(self, service, job_store, file_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        job_store.update_status(job.job_id, JobStatus.DONE)
        file_store.save_result(job.job_id, TranscriptionResult(text="hello world"))
        result = service.get_result(job.job_id)
        assert result.text == "hello world"

    def test_raises_job_not_ready_when_pending(self, service):
        job = service.submit_job("file", {"path": "/audio.wav"})
        with pytest.raises(JobNotReadyError):
            service.get_result(job.job_id)

    def test_raises_job_not_ready_when_processing(self, service, job_store):
        job = service.submit_job("file", {"path": "/audio.wav"})
        job_store.update_status(job.job_id, JobStatus.PROCESSING)
        with pytest.raises(JobNotReadyError):
            service.get_result(job.job_id)

    def test_raises_job_not_found_for_unknown_id(self, service):
        with pytest.raises(JobNotFoundError):
            service.get_result("nonexistent")

    def test_error_message_contains_job_id_when_not_ready(self, service):
        job = service.submit_job("file", {"path": "/audio.wav"})
        with pytest.raises(JobNotReadyError, match=job.job_id):
            service.get_result(job.job_id)
