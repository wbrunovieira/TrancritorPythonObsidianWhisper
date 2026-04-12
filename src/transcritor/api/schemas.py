from datetime import datetime

from pydantic import BaseModel

from transcritor.core.models import JobStatus, TranscriptionSegment


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
    text: str = ""
    language: str | None = None
    duration_seconds: float | None = None
    audio_path: str | None = None
    segments: list[TranscriptionSegment] = []


class BatchJobsResponse(BaseModel):
    jobs: list[JobCreatedResponse]


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]
    page: int
    page_size: int
    total: int


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    redis: str
