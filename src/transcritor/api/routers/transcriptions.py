from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from transcritor.api.dependencies import get_transcription_service, verify_api_key
from transcritor.api.schemas import (
    BatchJobsResponse,
    JobCreatedResponse,
    JobListResponse,
    JobStatusResponse,
    TranscriptionResultResponse,
    UrlTranscriptionRequest,
)
from transcritor.config import Settings, get_settings
from transcritor.core.exceptions import JobNotFoundError, JobNotReadyError
from transcritor.services.transcription_service import TranscriptionService

router = APIRouter(
    prefix="/transcriptions",
    tags=["transcriptions"],
    dependencies=[Depends(verify_api_key)],
)

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".oga"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}


def _save_upload(file: UploadFile, content: bytes, settings: Settings) -> Path:
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
    settings: Settings = Depends(get_settings),
) -> JobCreatedResponse:
    _validate_extension(file.filename or "", SUPPORTED_AUDIO_EXTENSIONS)
    content = await file.read()
    saved_path = _save_upload(file, content, settings)
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
    settings: Settings = Depends(get_settings),
) -> JobCreatedResponse:
    _validate_extension(file.filename or "", SUPPORTED_VIDEO_EXTENSIONS)
    content = await file.read()
    saved_path = _save_upload(file, content, settings)
    job = service.submit_job("video", {"path": str(saved_path)})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.post("/video/url", status_code=202, response_model=JobCreatedResponse)
def transcribe_video_url(
    request: UrlTranscriptionRequest,
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobCreatedResponse:
    from transcritor.sources.youtube_source import _is_youtube_url
    source_type = "youtube" if _is_youtube_url(request.url) else "video_url"
    job = service.submit_job(source_type, {"url": request.url})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


# ---------------------------------------------------------------------------
# Batch endpoints
# ---------------------------------------------------------------------------

@router.post("/audio/batch", status_code=202, response_model=BatchJobsResponse)
async def transcribe_audio_batch(
    files: list[UploadFile] = File(...),
    service: TranscriptionService = Depends(get_transcription_service),
    settings: Settings = Depends(get_settings),
) -> BatchJobsResponse:
    for f in files:
        _validate_extension(f.filename or "", SUPPORTED_AUDIO_EXTENSIONS)
    jobs = []
    for f in files:
        content = await f.read()
        saved_path = _save_upload(f, content, settings)
        job = service.submit_job("file", {"path": str(saved_path)})
        jobs.append(JobCreatedResponse(job_id=job.job_id, status=job.status))
    return BatchJobsResponse(jobs=jobs)


@router.post("/video/batch", status_code=202, response_model=BatchJobsResponse)
async def transcribe_video_batch(
    files: list[UploadFile] = File(...),
    service: TranscriptionService = Depends(get_transcription_service),
    settings: Settings = Depends(get_settings),
) -> BatchJobsResponse:
    for f in files:
        _validate_extension(f.filename or "", SUPPORTED_VIDEO_EXTENSIONS)
    jobs = []
    for f in files:
        content = await f.read()
        saved_path = _save_upload(f, content, settings)
        job = service.submit_job("video", {"path": str(saved_path)})
        jobs.append(JobCreatedResponse(job_id=job.job_id, status=job.status))
    return BatchJobsResponse(jobs=jobs)


@router.post("/video/extract", status_code=202, response_model=JobCreatedResponse)
async def extract_audio_from_video(
    file: UploadFile = File(...),
    service: TranscriptionService = Depends(get_transcription_service),
    settings: Settings = Depends(get_settings),
) -> JobCreatedResponse:
    _validate_extension(file.filename or "", SUPPORTED_VIDEO_EXTENSIONS)
    content = await file.read()
    saved_path = _save_upload(file, content, settings)
    job = service.submit_job("extract", {"path": str(saved_path)})
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------

@router.get("", response_model=JobListResponse)
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: TranscriptionService = Depends(get_transcription_service),
) -> JobListResponse:
    result = service.list_jobs(page=page, page_size=page_size)
    return JobListResponse(
        jobs=[
            JobStatusResponse(
                job_id=j.job_id,
                status=j.status,
                created_at=j.created_at,
                completed_at=j.completed_at,
                error=j.error,
            )
            for j in result["jobs"]
        ],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )


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
        audio_path=result.audio_path,
        segments=result.segments,
    )
