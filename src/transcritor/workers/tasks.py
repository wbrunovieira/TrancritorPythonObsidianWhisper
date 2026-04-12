import logging
from pathlib import Path

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
        return YouTubeSource(url=source_kwargs["url"], download_dir=settings.audio_dir), []

    if source_type == "extract":
        from transcritor.sources.video_source import VideoSource
        from transcritor.config import get_settings
        settings = get_settings()
        return VideoSource(
            video_path=Path(source_kwargs["path"]),
            output_dir=settings.audio_dir,
        ), []

    raise ValueError(f"Unknown source type: {source_type}")


def run_transcription(
    job_id: str,
    source,
    engine: WhisperEngine,
    job_store: JobStore,
    file_store: FileStore,
    cleanup_paths: list | None = None,
) -> None:
    """Lógica pura de execução — sem Celery, testável diretamente."""
    from transcritor.core.models import TranscriptionResult
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
    except Exception as e:
        logger.error("job=%s status=failed error=%s", job_id, e)
        job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        raise


def run_extraction(
    job_id: str,
    source,
    job_store: JobStore,
    file_store: FileStore,
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
    except Exception as e:
        logger.error("job=%s status=failed error=%s", job_id, e)
        job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        raise


@celery_app.task(name="transcritor.workers.tasks.transcribe_task", bind=True, max_retries=3)
def transcribe_task(self, job_id: str, source_type: str, source_kwargs: dict) -> None:
    """Task Celery — monta as dependências e delega para run_transcription ou run_extraction."""
    from transcritor.config import get_settings

    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url)
    job_store = JobStore(redis_client)
    file_store = FileStore(settings.transcripts_dir)
    source, cleanup_paths = _build_source(source_type, source_kwargs)

    if source_type == "extract":
        run_extraction(job_id, source, job_store, file_store)
    else:
        engine = get_engine()
        run_transcription(job_id, source, engine, job_store, file_store, cleanup_paths=cleanup_paths)
