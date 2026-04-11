from datetime import datetime

from pydantic import BaseModel

from transcritor.core.models import JobStatus


class UrlTranscriptionRequest(BaseModel):
    url: str


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class TranscriptionResultResponse(BaseModel):
    job_id: str
    text: str
    language: str | None = None
    duration_seconds: float | None = None


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    redis: str
