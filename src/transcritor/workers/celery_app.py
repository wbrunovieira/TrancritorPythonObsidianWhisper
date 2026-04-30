import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from transcritor.config import get_settings
from transcritor.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "transcritor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["transcritor.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Redis default visibility_timeout is 3600s — tasks longer than 1h get
    # re-queued while still running. Set to 6h to cover the longest videos.
    broker_transport_options={"visibility_timeout": 21600},
    beat_schedule={
        "cleanup-expired-results": {
            "task": "transcritor.workers.tasks.cleanup_task",
            "schedule": crontab(hour=3, minute=0),  # diariamente às 03:00 UTC
        }
    },
)


@worker_process_init.connect
def init_worker(**kwargs):
    """Carrega o modelo Whisper uma única vez na inicialização do processo worker."""
    logger.info("Worker process starting — loading Whisper model...")
    from transcritor.engine.registry import get_engine
    get_engine()
    logger.info("Whisper model loaded and ready.")
