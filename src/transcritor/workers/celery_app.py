from celery import Celery
from celery.signals import worker_process_init

from transcritor.config import get_settings

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
)


@worker_process_init.connect
def init_worker(**kwargs):
    """Carrega o modelo Whisper uma única vez na inicialização do processo worker."""
    from transcritor.engine.registry import get_engine
    get_engine()
