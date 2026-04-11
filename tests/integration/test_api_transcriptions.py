"""
Testes de integração da API FastAPI.

Usa httpx.AsyncClient com ASGITransport — sem servidor real.
O TranscriptionService é substituído por FakeService via dependency_overrides.
Sem Redis, sem Celery, sem Whisper.
"""
import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport

from transcritor.core.models import TranscriptionJob, TranscriptionResult, JobStatus
from transcritor.core.exceptions import JobNotFoundError, JobNotReadyError


# ---------------------------------------------------------------------------
# FakeService — substitui TranscriptionService nos testes
# ---------------------------------------------------------------------------

class FakeService:
    def __init__(self):
        self._jobs: dict[str, TranscriptionJob] = {}
        self._results: dict[str, TranscriptionResult] = {}
        self.submitted: list[tuple[str, dict]] = []

    def preset_job(self, job: TranscriptionJob) -> None:
        self._jobs[job.job_id] = job

    def preset_result(self, job_id: str, result: TranscriptionResult) -> None:
        self._results[job_id] = result

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
        api_key="test-secret",
    )
    app.dependency_overrides[get_transcription_service] = lambda: fake_service
    app.dependency_overrides[get_settings] = lambda: test_settings
    get_settings.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-secret"},
    ) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
async def client_no_auth(fake_service, tmp_path):
    """Client sem header de autenticação — para testar rejeição."""
    from transcritor.api.app import app
    from transcritor.api.dependencies import get_transcription_service
    from transcritor.config import Settings, get_settings

    test_settings = Settings(
        data_dir=tmp_path,
        redis_url="redis://localhost:6379/0",
        whisper_model="base",
        api_key="test-secret",
    )
    app.dependency_overrides[get_transcription_service] = lambda: fake_service
    app.dependency_overrides[get_settings] = lambda: test_settings
    get_settings.cache_clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _audio_file(filename="audio.mp3", content=b"fake audio"):
    return ("file", (filename, content, "audio/mpeg"))


def _video_file(filename="video.mp4", content=b"fake video"):
    return ("file", (filename, content, "video/mp4"))


# ---------------------------------------------------------------------------
# POST /transcriptions/audio — upload
# ---------------------------------------------------------------------------

class TestAudioUpload:
    async def test_returns_202(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file()])
        assert r.status_code == 202

    async def test_response_has_job_id(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file()])
        assert "job_id" in r.json()

    async def test_response_status_is_pending(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file()])
        assert r.json()["status"] == "pending"

    async def test_submits_file_source_type(self, client, fake_service):
        await client.post("/transcriptions/audio", files=[_audio_file()])
        assert fake_service.submitted[0][0] == "file"

    async def test_unsupported_format_returns_422(self, client):
        bad_file = ("file", ("document.pdf", b"fake", "application/pdf"))
        r = await client.post("/transcriptions/audio", files=[bad_file])
        assert r.status_code == 422

    async def test_mp3_accepted(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file("audio.mp3")])
        assert r.status_code == 202

    async def test_wav_accepted(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file("audio.wav")])
        assert r.status_code == 202

    async def test_m4a_accepted(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file("audio.m4a")])
        assert r.status_code == 202


# ---------------------------------------------------------------------------
# POST /transcriptions/audio/url
# ---------------------------------------------------------------------------

class TestAudioUrl:
    async def test_returns_202(self, client):
        r = await client.post(
            "/transcriptions/audio/url",
            json={"url": "https://example.com/audio.mp3"},
        )
        assert r.status_code == 202

    async def test_response_has_job_id(self, client):
        r = await client.post(
            "/transcriptions/audio/url",
            json={"url": "https://example.com/audio.mp3"},
        )
        assert "job_id" in r.json()

    async def test_submits_url_source_type(self, client, fake_service):
        await client.post(
            "/transcriptions/audio/url",
            json={"url": "https://example.com/audio.mp3"},
        )
        assert fake_service.submitted[0][0] == "url"

    async def test_missing_url_returns_422(self, client):
        r = await client.post("/transcriptions/audio/url", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /transcriptions/video — upload
# ---------------------------------------------------------------------------

class TestVideoUpload:
    async def test_returns_202(self, client):
        r = await client.post("/transcriptions/video", files=[_video_file()])
        assert r.status_code == 202

    async def test_submits_video_source_type(self, client, fake_service):
        await client.post("/transcriptions/video", files=[_video_file()])
        assert fake_service.submitted[0][0] == "video"

    async def test_unsupported_format_returns_422(self, client):
        bad = ("file", ("doc.txt", b"fake", "text/plain"))
        r = await client.post("/transcriptions/video", files=[bad])
        assert r.status_code == 422

    async def test_mp4_accepted(self, client):
        r = await client.post("/transcriptions/video", files=[_video_file("video.mp4")])
        assert r.status_code == 202

    async def test_mkv_accepted(self, client):
        r = await client.post("/transcriptions/video", files=[_video_file("video.mkv")])
        assert r.status_code == 202


# ---------------------------------------------------------------------------
# POST /transcriptions/video/url
# ---------------------------------------------------------------------------

class TestVideoUrl:
    async def test_returns_202(self, client):
        r = await client.post(
            "/transcriptions/video/url",
            json={"url": "https://example.com/video.mp4"},
        )
        assert r.status_code == 202

    async def test_submits_video_url_source_type(self, client, fake_service):
        await client.post(
            "/transcriptions/video/url",
            json={"url": "https://example.com/video.mp4"},
        )
        assert fake_service.submitted[0][0] == "video_url"

    async def test_missing_url_returns_422(self, client):
        r = await client.post("/transcriptions/video/url", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /transcriptions/{job_id}
# ---------------------------------------------------------------------------

class TestGetJobStatus:
    async def test_returns_pending_status(self, client, fake_service):
        job = fake_service.submit_job("file", {})
        r = await client.get(f"/transcriptions/{job.job_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    async def test_returns_done_status(self, client, fake_service):
        job = TranscriptionJob(
            job_id="done-job",
            status=JobStatus.DONE,
            source_type="file",
            created_at=datetime.now(),
        )
        fake_service.preset_job(job)
        r = await client.get("/transcriptions/done-job")
        assert r.json()["status"] == "done"

    async def test_returns_404_for_unknown_job(self, client):
        r = await client.get("/transcriptions/nonexistent-id")
        assert r.status_code == 404

    async def test_response_has_job_id(self, client, fake_service):
        job = fake_service.submit_job("file", {})
        r = await client.get(f"/transcriptions/{job.job_id}")
        assert r.json()["job_id"] == job.job_id

    async def test_response_has_created_at(self, client, fake_service):
        job = fake_service.submit_job("file", {})
        r = await client.get(f"/transcriptions/{job.job_id}")
        assert "created_at" in r.json()

    async def test_returns_failed_status_with_error(self, client, fake_service):
        job = TranscriptionJob(
            job_id="failed-job",
            status=JobStatus.FAILED,
            source_type="file",
            created_at=datetime.now(),
            error="model crashed",
        )
        fake_service.preset_job(job)
        r = await client.get("/transcriptions/failed-job")
        assert r.json()["status"] == "failed"
        assert r.json()["error"] == "model crashed"


# ---------------------------------------------------------------------------
# GET /transcriptions/{job_id}/result
# ---------------------------------------------------------------------------

class TestGetResult:
    async def test_returns_text_when_done(self, client, fake_service):
        job = TranscriptionJob(
            job_id="done-job",
            status=JobStatus.DONE,
            source_type="file",
            created_at=datetime.now(),
        )
        fake_service.preset_job(job)
        fake_service.preset_result("done-job", TranscriptionResult(text="hello world"))
        r = await client.get("/transcriptions/done-job/result")
        assert r.status_code == 200
        assert r.json()["text"] == "hello world"

    async def test_returns_language(self, client, fake_service):
        job = TranscriptionJob(
            job_id="done-job",
            status=JobStatus.DONE,
            source_type="file",
            created_at=datetime.now(),
        )
        fake_service.preset_job(job)
        fake_service.preset_result(
            "done-job", TranscriptionResult(text="olá", language="pt")
        )
        r = await client.get("/transcriptions/done-job/result")
        assert r.json()["language"] == "pt"

    async def test_returns_409_when_pending(self, client, fake_service):
        job = fake_service.submit_job("file", {})
        r = await client.get(f"/transcriptions/{job.job_id}/result")
        assert r.status_code == 409

    async def test_returns_409_when_processing(self, client, fake_service):
        job = TranscriptionJob(
            job_id="proc-job",
            status=JobStatus.PROCESSING,
            source_type="file",
            created_at=datetime.now(),
        )
        fake_service.preset_job(job)
        r = await client.get("/transcriptions/proc-job/result")
        assert r.status_code == 409

    async def test_returns_404_for_unknown_job(self, client):
        r = await client.get("/transcriptions/nonexistent/result")
        assert r.status_code == 404

    async def test_response_has_job_id(self, client, fake_service):
        job = TranscriptionJob(
            job_id="done-job",
            status=JobStatus.DONE,
            source_type="file",
            created_at=datetime.now(),
        )
        fake_service.preset_job(job)
        fake_service.preset_result("done-job", TranscriptionResult(text="test"))
        r = await client.get("/transcriptions/done-job/result")
        assert r.json()["job_id"] == "done-job"


# ---------------------------------------------------------------------------
# API Key authentication
# ---------------------------------------------------------------------------

class TestApiKeyAuth:
    async def test_missing_key_returns_401(self, client_no_auth):
        r = await client_no_auth.post("/transcriptions/audio", files=[_audio_file()])
        assert r.status_code == 401

    async def test_wrong_key_returns_401(self, client_no_auth):
        r = await client_no_auth.post(
            "/transcriptions/audio",
            files=[_audio_file()],
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 401

    async def test_correct_key_returns_202(self, client):
        r = await client.post("/transcriptions/audio", files=[_audio_file()])
        assert r.status_code == 202

    async def test_health_requires_no_key(self, client_no_auth):
        r = await client_no_auth.get("/health")
        assert r.status_code == 200

    async def test_ready_requires_no_key(self, client_no_auth):
        r = await client_no_auth.get("/ready")
        assert r.status_code in (200, 503)

    async def test_get_job_status_requires_key(self, client_no_auth):
        r = await client_no_auth.get("/transcriptions/some-job-id")
        assert r.status_code == 401

    async def test_get_result_requires_key(self, client_no_auth):
        r = await client_no_auth.get("/transcriptions/some-job-id/result")
        assert r.status_code == 401
