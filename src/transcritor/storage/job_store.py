from datetime import datetime

from transcritor.core.exceptions import JobNotFoundError
from transcritor.core.models import JobStatus, TranscriptionJob


class JobStore:
    def __init__(self, redis_client):
        self._redis = redis_client

    def save(self, job: TranscriptionJob) -> None:
        self._redis.set(f"job:{job.job_id}", job.model_dump_json())
        self._redis.zadd("jobs:all", {job.job_id: job.created_at.timestamp()})

    def load(self, job_id: str) -> TranscriptionJob:
        data = self._redis.get(f"job:{job_id}")
        if data is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return TranscriptionJob.model_validate_json(data)

    def list_jobs(self, page: int = 1, page_size: int = 20) -> dict:
        total = self._redis.zcard("jobs:all")
        start = (page - 1) * page_size
        stop = start + page_size - 1
        job_ids = self._redis.zrevrange("jobs:all", start, stop)
        jobs = [self.load(jid.decode() if isinstance(jid, bytes) else jid) for jid in job_ids]
        return {"jobs": jobs, "page": page, "page_size": page_size, "total": total}

    def delete(self, job_id: str) -> None:
        self._redis.delete(f"job:{job_id}")
        self._redis.zrem("jobs:all", job_id)

    def list_all_ids(self) -> list[str]:
        ids = self._redis.zrange("jobs:all", 0, -1)
        return [jid.decode() if isinstance(jid, bytes) else jid for jid in ids]

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
