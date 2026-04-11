from contextlib import asynccontextmanager

from fastapi import FastAPI

from transcritor.api.routers import health, transcriptions


@asynccontextmanager
async def lifespan(app: FastAPI):
    from transcritor.config import get_settings
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    settings.video_dir.mkdir(parents=True, exist_ok=True)
    settings.transcripts_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Transcritor API",
    version="0.1.0",
    description="Audio and video transcription service using Whisper",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(transcriptions.router)
