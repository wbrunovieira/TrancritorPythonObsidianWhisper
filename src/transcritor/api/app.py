import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from transcritor.api.routers import health, transcriptions
from transcritor.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from transcritor.config import get_settings
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    settings.video_dir.mkdir(parents=True, exist_ok=True)
    settings.transcripts_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Transcritor API started — data_dir=%s", settings.data_dir)
    yield
    logger.info("Transcritor API shutting down")


app = FastAPI(
    title="Transcritor API",
    version="0.1.0",
    description="Audio and video transcription service using Whisper",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(health.router)
app.include_router(transcriptions.router)
