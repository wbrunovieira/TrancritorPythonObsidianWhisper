import redis
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from transcritor.config import Settings, get_settings
from transcritor.services.transcription_service import TranscriptionService
from transcritor.storage.file_store import FileStore
from transcritor.storage.job_store import JobStore
from transcritor.workers.tasks import transcribe_task

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_key:
        return  # API key not configured — open access (dev/local)
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_transcription_service(
    settings: Settings = Depends(get_settings),
) -> TranscriptionService:
    redis_client = redis.from_url(settings.redis_url)
    job_store = JobStore(redis_client)
    file_store = FileStore(settings.transcripts_dir)

    def dispatch(job_id: str, source_type: str, source_kwargs: dict, callback_url: str | None = None, callback_secret: str | None = None) -> None:
        transcribe_task.delay(job_id, source_type, source_kwargs, callback_url, callback_secret)

    return TranscriptionService(
        file_store=file_store,
        job_store=job_store,
        task_dispatcher=dispatch,
    )
