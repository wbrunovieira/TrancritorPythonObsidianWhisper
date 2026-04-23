from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class TranscriptionJob(BaseModel):
    job_id: str
    status: JobStatus
    source_type: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    callback_url: str | None = None
    callback_secret: str | None = None


class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    text: str = ""
    language: str | None = None
    duration_seconds: float | None = None
    audio_path: str | None = None
    segments: list[TranscriptionSegment] = []
