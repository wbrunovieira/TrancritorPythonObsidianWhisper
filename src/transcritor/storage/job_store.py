from datetime import datetime

from transcritor.core.exceptions import JobNotFoundError
from transcritor.core.models import JobStatus, TranscriptionJob


class JobStore:
    def __init__(self, redis_client):
        self._redis = redis_client

    def save(self, job: TranscriptionJob) -> None:
        self._redis.set(f"job:{job.job_id}", job.model_dump_json())

    def load(self, job_id: str) -> TranscriptionJob:
        data = self._redis.get(f"job:{job_id}")
        if data is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return TranscriptionJob.model_validate_json(data)

    def update_status(
        self, job_id: str, status: JobStatus, error: str | None = None
    ) -> None:
        job = self.load(job_id)
        updates: dict = {"status": status}
        if error is not None:
            updates["error"] = error
        if status in (JobStatus.DONE, JobStatus.FAILED):
            updates["completed_at"] = datetime.now()
        self.save(job.model_copy(update=updates))
