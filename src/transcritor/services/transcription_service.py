from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from transcritor.core.exceptions import JobNotReadyError
from transcritor.core.models import JobStatus, TranscriptionJob, TranscriptionResult
from transcritor.storage.file_store import FileStore
from transcritor.storage.job_store import JobStore


class TranscriptionService:
    def __init__(
        self,
        file_store: FileStore,
        job_store: JobStore,
        task_dispatcher: Callable[[str, str, dict], None],
    ):
        self._file_store = file_store
        self._job_store = job_store
        self._dispatch = task_dispatcher

    def submit_job(self, source_type: str, source_kwargs: dict) -> TranscriptionJob:
        job = TranscriptionJob(
            job_id=uuid4().hex,
            status=JobStatus.PENDING,
            source_type=source_type,
            created_at=datetime.now(),
        )
        self._job_store.save(job)
        self._dispatch(job.job_id, source_type, source_kwargs)
        return job

    def get_job(self, job_id: str) -> TranscriptionJob:
        return self._job_store.load(job_id)

    def submit_batch(self, source_type: str, items: list[dict]) -> list[TranscriptionJob]:
        return [self.submit_job(source_type, kwargs) for kwargs in items]

    def list_jobs(self, page: int = 1, page_size: int = 20) -> dict:
        return self._job_store.list_jobs(page=page, page_size=page_size)

    def get_result(self, job_id: str) -> TranscriptionResult:
        job = self._job_store.load(job_id)
        if job.status != JobStatus.DONE:
            raise JobNotReadyError(
                f"Job {job_id} is not done yet. Current status: {job.status}"
            )
        return self._file_store.load_result(job_id)
