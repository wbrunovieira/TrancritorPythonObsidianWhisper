from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from transcritor.api.dependencies import get_transcription_service
from transcritor.api.schemas import (
    JobCreatedResponse,
    JobStatusResponse,
    TranscriptionResultResponse,
    UrlTranscriptionRequest,
)
from transcritor.config import get_settings
from transcritor.core.exceptions import JobNotFoundError, JobNotReadyError
from transcritor.services.transcription_service import TranscriptionService

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}


def _save_upload(file: UploadFile, content: bytes) -> Path:
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    dest = settings.audio_dir / f"{uuid4().hex}{suffix}"
    dest.write_bytes(content)
    return dest


def _validate_extension(filename: str, supported: set[str]) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in supported:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file format '{suffix}'. "
                   f"Supported: {', '.join(sorted(supported))}",
        )
    return suffix


# ---------------------------------------------------------------------------
# Audio endpoints
# ---------------------------------------------------------------------------

@router.post("/audio", status_code=202, response_model=JobCreatedResponse)
async def transcribe_audio_upload(
    file: UploadFile = File(...),
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobCreatedResponse:
    _validate_extension(file.filename or "", SUPPORTED_AUDIO_EXTENSIONS)
    content = await file.read()
    saved_path = _save_upload(file, content)
    job = service.submit_job("file", {"path": str(saved_path)})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.post("/audio/url", status_code=202, response_model=JobCreatedResponse)
def transcribe_audio_url(
    request: UrlTranscriptionRequest,
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobCreatedResponse:
    job = service.submit_job("url", {"url": request.url})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


# ---------------------------------------------------------------------------
# Video endpoints
# ---------------------------------------------------------------------------

@router.post("/video", status_code=202, response_model=JobCreatedResponse)
async def transcribe_video_upload(
    file: UploadFile = File(...),
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobCreatedResponse:
    _validate_extension(file.filename or "", SUPPORTED_VIDEO_EXTENSIONS)
    content = await file.read()
    saved_path = _save_upload(file, content)
    job = service.submit_job("video", {"path": str(saved_path)})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.post("/video/url", status_code=202, response_model=JobCreatedResponse)
def transcribe_video_url(
    request: UrlTranscriptionRequest,
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobCreatedResponse:
    job = service.submit_job("video_url", {"url": request.url})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


# ---------------------------------------------------------------------------
# Job status and result
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobStatusResponse:
    try:
        job = service.get_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
    )


@router.get("/{job_id}/result", response_model=TranscriptionResultResponse)
def get_job_result(
    job_id: str,
    service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResultResponse:
    try:
        result = service.get_result(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    except JobNotReadyError:
        raise HTTPException(status_code=409, detail=f"Job '{job_id}' is not done yet")
    return TranscriptionResultResponse(
        job_id=job_id,
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )
