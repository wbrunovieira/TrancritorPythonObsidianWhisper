import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import redis

from transcritor.core.models import JobStatus

logger = logging.getLogger(__name__)
from transcritor.engine.registry import get_engine
from transcritor.engine.whisper_engine import WhisperEngine
from transcritor.storage.file_store import FileStore
from transcritor.storage.job_store import JobStore
from transcritor.workers.celery_app import celery_app


def _build_source(source_type: str, source_kwargs: dict) -> tuple:
    """Instancia o source correto a partir do tipo e argumentos.

    Retorna ``(source, cleanup_paths)`` onde ``cleanup_paths`` é a lista de
    arquivos que devem ser apagados após a transcrição bem-sucedida (além do
    próprio áudio produzido pelo source).
    """
    if source_type == "file":
        from transcritor.sources.file_source import FileSource
        return FileSource(Path(source_kwargs["path"])), []

    if source_type == "video":
        from transcritor.sources.video_source import VideoSource
        from transcritor.config import get_settings
        settings = get_settings()
        video_path = Path(source_kwargs["path"])
        return VideoSource(video_path=video_path, output_dir=settings.audio_dir), [video_path]

    if source_type == "url":
        from transcritor.sources.url_source import UrlSource
        from transcritor.config import get_settings
        settings = get_settings()
        return UrlSource(url=source_kwargs["url"], download_dir=settings.audio_dir), []

    if source_type == "video_url":
        from transcritor.sources.url_source import UrlSource
        from transcritor.sources.video_source import VideoSource
        from transcritor.config import get_settings
        settings = get_settings()
        url_source = UrlSource(url=source_kwargs["url"], download_dir=settings.video_dir)
        video_path = url_source.acquire()
        return VideoSource(video_path=video_path, output_dir=settings.audio_dir), [video_path]

    if source_type == "youtube":
        from transcritor.sources.youtube_source import YouTubeSource
        from transcritor.config import get_settings
        settings = get_settings()
        return YouTubeSource(
            url=source_kwargs["url"],
            download_dir=settings.audio_dir,
            cookies_file=settings.youtube_cookies_file,
        ), []

    if source_type == "extract":
        from transcritor.sources.video_source import VideoSource
        from transcritor.config import get_settings
        settings = get_settings()
        return VideoSource(
            video_path=Path(source_kwargs["path"]),
            output_dir=settings.audio_dir,
        ), []

    raise ValueError(f"Unknown source type: {source_type}")


def fire_callback(
    callback_url: str,
    payload: dict,
    secret: str | None = None,
    *,
    _max_retries: int = 3,
) -> None:
    """POSTa payload para callback_url. Tenta até _max_retries vezes. Nunca levanta exceção."""
    headers: dict[str, str] = {}
    if secret:
        headers["X-Callback-Secret"] = secret

    for attempt in range(_max_retries):
        try:
            with httpx.Client() as client:
                response = client.post(callback_url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
            logger.info("callback sent url=%s attempt=%d", callback_url, attempt + 1)
            return
        except Exception as exc:
            logger.warning("callback attempt=%d/%d url=%s error=%s", attempt + 1, _max_retries, callback_url, exc)
            if attempt < _max_retries - 1:
                time.sleep(2 ** attempt)

    logger.error("callback failed after %d attempts url=%s", _max_retries, callback_url)


def run_transcription(
    job_id: str,
    source,
    engine: WhisperEngine,
    job_store: JobStore,
    file_store: FileStore,
    cleanup_paths: list | None = None,
    callback_url: str | None = None,
    callback_secret: str | None = None,
) -> None:
    """Lógica pura de execução — sem Celery, testável diretamente."""
    job_store.update_status(job_id, JobStatus.PROCESSING)
    logger.info("job=%s status=processing", job_id)
    try:
        audio_path = source.acquire()
        logger.info("job=%s audio_ready path=%s", job_id, audio_path)
        result = engine.transcribe(audio_path)
        file_store.save_result(job_id, result)
        job_store.update_status(job_id, JobStatus.DONE)
        logger.info("job=%s status=done language=%s duration=%.1fs", job_id, result.language, result.duration_seconds or 0)
        for path in [audio_path, *(cleanup_paths or [])]:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("job=%s could not delete temp file %s: %s", job_id, path, exc)
        if callback_url:
            fire_callback(
                callback_url,
                {
                    "job_id": job_id,
                    "status": "done",
                    "text": result.text,
                    "language": result.language,
                    "duration_seconds": result.duration_seconds,
                    "segments": [s.model_dump() for s in result.segments],
                },
                callback_secret,
            )
    except Exception as e:
        logger.error("job=%s status=failed error=%s", job_id, e)
        job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        if callback_url:
            fire_callback(
                callback_url,
                {"job_id": job_id, "status": "failed", "error": str(e)},
                callback_secret,
            )
        raise


def run_extraction(
    job_id: str,
    source,
    job_store: JobStore,
    file_store: FileStore,
    callback_url: str | None = None,
    callback_secret: str | None = None,
) -> None:
    """Extrai áudio de um vídeo sem transcrever — lógica pura, testável sem Celery."""
    from transcritor.core.models import TranscriptionResult
    job_store.update_status(job_id, JobStatus.PROCESSING)
    logger.info("job=%s status=processing type=extract", job_id)
    try:
        audio_path = source.acquire()
        result = TranscriptionResult(audio_path=str(audio_path))
        file_store.save_result(job_id, result)
        job_store.update_status(job_id, JobStatus.DONE)
        logger.info("job=%s status=done audio_path=%s", job_id, audio_path)
        if callback_url:
            fire_callback(
                callback_url,
                {"job_id": job_id, "status": "done", "audio_path": str(audio_path)},
                callback_secret,
            )
    except Exception as e:
        logger.error("job=%s status=failed error=%s", job_id, e)
        job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        if callback_url:
            fire_callback(
                callback_url,
                {"job_id": job_id, "status": "failed", "error": str(e)},
                callback_secret,
            )
        raise


def run_cleanup(job_store: JobStore, file_store: FileStore, ttl_hours: int) -> int:
    """Deleta jobs (done/failed) cujo completed_at é mais antigo que ttl_hours. Retorna o total deletado."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    deleted = 0

    for job_id in job_store.list_all_ids():
        try:
            job = job_store.load(job_id)
        except Exception:
            continue

        if job.status not in (JobStatus.DONE, JobStatus.FAILED):
            continue

        if job.completed_at is None:
            continue

        completed_at = job.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        if completed_at < cutoff:
            file_store.delete_result(job_id)
            job_store.delete(job_id)
            deleted += 1
            logger.info("job=%s deleted reason=ttl_expired ttl_hours=%d", job_id, ttl_hours)

    logger.info("cleanup done deleted=%d ttl_hours=%d", deleted, ttl_hours)
    return deleted


@celery_app.task(name="transcritor.workers.tasks.cleanup_task")
def cleanup_task() -> None:
    """Celery Beat task — monta dependências e delega para run_cleanup."""
    from transcritor.config import get_settings

    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url)
    job_store = JobStore(redis_client)
    file_store = FileStore(settings.transcripts_dir)
    run_cleanup(job_store, file_store, ttl_hours=settings.result_ttl_hours)


@celery_app.task(name="transcritor.workers.tasks.transcribe_task", bind=True, max_retries=3)
def transcribe_task(
    self,
    job_id: str,
    source_type: str,
    source_kwargs: dict,
    callback_url: str | None = None,
    callback_secret: str | None = None,
) -> None:
    """Task Celery — monta as dependências e delega para run_transcription ou run_extraction."""
    from transcritor.config import get_settings

    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url)
    job_store = JobStore(redis_client)
    file_store = FileStore(settings.transcripts_dir)
    source, cleanup_paths = _build_source(source_type, source_kwargs)

    if source_type == "extract":
        run_extraction(job_id, source, job_store, file_store, callback_url=callback_url, callback_secret=callback_secret)
    else:
        engine = get_engine()
        run_transcription(job_id, source, engine, job_store, file_store, cleanup_paths=cleanup_paths, callback_url=callback_url, callback_secret=callback_secret)
