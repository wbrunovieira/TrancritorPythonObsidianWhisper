import redis
from fastapi import Depends

from transcritor.config import Settings, get_settings
from transcritor.services.transcription_service import TranscriptionService
from transcritor.storage.file_store import FileStore
from transcritor.storage.job_store import JobStore
from transcritor.workers.tasks import transcribe_task


def get_transcription_service(
    settings: Settings = Depends(get_settings),
) -> TranscriptionService:
    redis_client = redis.from_url(settings.redis_url)
    job_store = JobStore(redis_client)
    file_store = FileStore(settings.transcripts_dir)

    def dispatch(job_id: str, source_type: str, source_kwargs: dict) -> None:
        transcribe_task.delay(job_id, source_type, source_kwargs)

    return TranscriptionService(
        file_store=file_store,
        job_store=job_store,
        task_dispatcher=dispatch,
    )
