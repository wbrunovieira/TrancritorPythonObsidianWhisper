"""
Fase 7 — testes de integração para novas rotas:
  POST /transcriptions/audio/batch
  POST /transcriptions/video/batch
  POST /transcriptions/video/extract
  GET  /transcriptions

FakeService estende o FakeService base com list_jobs.
"""
import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport

from transcritor.core.models import TranscriptionJob, TranscriptionResult, JobStatus
from transcritor.core.exceptions import JobNotFoundError, JobNotReadyError


# ---------------------------------------------------------------------------
# FakeService with list_jobs support
# ---------------------------------------------------------------------------

class FakeService:
    def __init__(self):
        self._jobs: dict[str, TranscriptionJob] = {}
        self._results: dict[str, TranscriptionResult] = {}
        self.submitted: list[tuple[str, dict]] = []

    def preset_job(self, job: TranscriptionJob) -> None:
        self._jobs[job.job_id] = job

    def submit_job(self, source_type: str, source_kwargs: dict) -> TranscriptionJob:
        from uuid import uuid4
        job = TranscriptionJob(
            job_id=uuid4().hex,
            status=JobStatus.PENDING,
            source_type=source_type,
            created_at=datetime.now(),
        )
        self._jobs[job.job_id] = job
        self.submitted.append((source_type, source_kwargs))
        return job

    def get_job(self, job_id: str) -> TranscriptionJob:
        if job_id not in self._jobs:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self._jobs[job_id]

    def get_result(self, job_id: str) -> TranscriptionResult:
        if job_id not in self._jobs:
            raise JobNotFoundError(f"Job not found: {job_id}")
        job = self._jobs[job_id]
        if job.status != JobStatus.DONE:
            raise JobNotReadyError(f"Job {job_id} not ready: {job.status}")
        if job_id not in self._results:
            raise JobNotFoundError(f"Result not found: {job_id}")
        return self._results[job_id]

    def list_jobs(self, page: int = 1, page_size: int = 20) -> dict:
        all_jobs = list(self._jobs.values())
        total = len(all_jobs)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "jobs": all_jobs[start:end],
            "page": page,
            "page_size": page_size,
            "total": total,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_service():
    return FakeService()


@pytest.fixture
async def client(fake_service, tmp_path):
    from transcritor.api.app import app
    from transcritor.api.dependencies import get_transcription_service
    from transcritor.config import Settings, get_settings

    test_settings = Settings(
        data_dir=tmp_path,
        redis_url="redis://localhost:6379/0",
        whisper_model="base",
    )
    app.dependency_overrides[get_transcription_service] = lambda: fake_service
    app.dependency_overrides[get_settings] = lambda: test_settings
    get_settings.cache_clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _audio_files(*names):
    return [("files", (name, b"fake audio", "audio/mpeg")) for name in names]


def _video_files(*names):
    return [("files", (name, b"fake video", "video/mp4")) for name in names]


# ---------------------------------------------------------------------------
# POST /transcriptions/audio/batch
# ---------------------------------------------------------------------------

class TestAudioBatch:
    async def test_returns_202(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3", "b.wav"),
        )
        assert r.status_code == 202

    async def test_response_is_list_of_jobs(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3", "b.wav"),
        )
        body = r.json()
        assert "jobs" in body
        assert isinstance(body["jobs"], list)
        assert len(body["jobs"]) == 2

    async def test_each_job_has_job_id(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3", "b.wav"),
        )
        for job in r.json()["jobs"]:
            assert "job_id" in job

    async def test_each_job_status_is_pending(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3", "b.wav"),
        )
        for job in r.json()["jobs"]:
            assert job["status"] == "pending"

    async def test_submits_file_source_type_for_each(self, client, fake_service):
        await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3", "b.wav"),
        )
        assert len(fake_service.submitted) == 2
        assert all(s[0] == "file" for s in fake_service.submitted)

    async def test_single_file_accepted(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=_audio_files("a.mp3"),
        )
        assert r.status_code == 202
        assert len(r.json()["jobs"]) == 1

    async def test_unsupported_format_returns_422(self, client):
        r = await client.post(
            "/transcriptions/audio/batch",
            files=[("files", ("doc.pdf", b"fake", "application/pdf"))],
        )
        assert r.status_code == 422

    async def test_mixed_formats_returns_422_on_bad_file(self, client):
        files = _audio_files("a.mp3") + [
            ("files", ("bad.pdf", b"fake", "application/pdf"))
        ]
        r = await client.post("/transcriptions/audio/batch", files=files)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /transcriptions/video/batch
# ---------------------------------------------------------------------------

class TestVideoBatch:
    async def test_returns_202(self, client):
        r = await client.post(
            "/transcriptions/video/batch",
            files=_video_files("a.mp4", "b.mkv"),
        )
        assert r.status_code == 202

    async def test_response_has_jobs_list(self, client):
        r = await client.post(
            "/transcriptions/video/batch",
            files=_video_files("a.mp4", "b.mkv"),
        )
        body = r.json()
        assert "jobs" in body
        assert len(body["jobs"]) == 2

    async def test_submits_video_source_type_for_each(self, client, fake_service):
        await client.post(
            "/transcriptions/video/batch",
            files=_video_files("a.mp4", "b.mkv"),
        )
        assert len(fake_service.submitted) == 2
        assert all(s[0] == "video" for s in fake_service.submitted)

    async def test_unsupported_format_returns_422(self, client):
        r = await client.post(
            "/transcriptions/video/batch",
            files=[("files", ("doc.txt", b"fake", "text/plain"))],
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /transcriptions/video/extract
# ---------------------------------------------------------------------------

class TestVideoExtract:
    async def test_returns_202(self, client):
        r = await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("video.mp4", b"fake video", "video/mp4"))],
        )
        assert r.status_code == 202

    async def test_response_has_job_id(self, client):
        r = await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("video.mp4", b"fake video", "video/mp4"))],
        )
        assert "job_id" in r.json()

    async def test_response_status_is_pending(self, client):
        r = await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("video.mp4", b"fake video", "video/mp4"))],
        )
        assert r.json()["status"] == "pending"

    async def test_submits_extract_source_type(self, client, fake_service):
        await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("video.mp4", b"fake video", "video/mp4"))],
        )
        assert fake_service.submitted[0][0] == "extract"

    async def test_unsupported_format_returns_422(self, client):
        r = await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("audio.mp3", b"fake", "audio/mpeg"))],
        )
        assert r.status_code == 422

    async def test_mkv_accepted(self, client):
        r = await client.post(
            "/transcriptions/video/extract",
            files=[("file", ("video.mkv", b"fake video", "video/x-matroska"))],
        )
        assert r.status_code == 202


# ---------------------------------------------------------------------------
# GET /transcriptions
# ---------------------------------------------------------------------------

class TestListJobs:
    async def test_returns_200(self, client):
        r = await client.get("/transcriptions")
        assert r.status_code == 200

    async def test_response_has_jobs_list(self, client):
        r = await client.get("/transcriptions")
        body = r.json()
        assert "jobs" in body
        assert isinstance(body["jobs"], list)

    async def test_response_has_pagination_fields(self, client):
        r = await client.get("/transcriptions")
        body = r.json()
        assert "page" in body
        assert "page_size" in body
        assert "total" in body

    async def test_empty_when_no_jobs(self, client):
        r = await client.get("/transcriptions")
        assert r.json()["total"] == 0
        assert r.json()["jobs"] == []

    async def test_returns_submitted_jobs(self, client, fake_service):
        fake_service.submit_job("file", {})
        fake_service.submit_job("file", {})
        r = await client.get("/transcriptions")
        assert r.json()["total"] == 2
        assert len(r.json()["jobs"]) == 2

    async def test_default_page_is_1(self, client):
        r = await client.get("/transcriptions")
        assert r.json()["page"] == 1

    async def test_default_page_size_is_20(self, client):
        r = await client.get("/transcriptions")
        assert r.json()["page_size"] == 20

    async def test_custom_page_size(self, client, fake_service):
        for _ in range(5):
            fake_service.submit_job("file", {})
        r = await client.get("/transcriptions?page_size=2")
        assert r.json()["page_size"] == 2
        assert len(r.json()["jobs"]) == 2

    async def test_custom_page(self, client, fake_service):
        for _ in range(5):
            fake_service.submit_job("file", {})
        r = await client.get("/transcriptions?page=2&page_size=3")
        assert r.json()["page"] == 2
        assert len(r.json()["jobs"]) == 2  # 5 total, 3 per page, page 2 has 2

    async def test_each_job_has_required_fields(self, client, fake_service):
        fake_service.submit_job("file", {})
        r = await client.get("/transcriptions")
        job = r.json()["jobs"][0]
        assert "job_id" in job
        assert "status" in job
        assert "created_at" in job
