"""
Testes de integração para callback_url/callback_secret na API.

Verifica que os campos chegam do request até o submit_job do service.
Sem Celery, sem Redis, sem Whisper — FakeService intercepta as chamadas.
"""
import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport

from transcritor.core.models import TranscriptionJob, JobStatus


class FakeServiceWithCallback:
    """FakeService que captura callback_url e callback_secret passados ao submit_job."""

    def __init__(self):
        self.submitted: list[dict] = []

    def submit_job(
        self,
        source_type: str,
        source_kwargs: dict,
        callback_url: str | None = None,
        callback_secret: str | None = None,
    ) -> TranscriptionJob:
        from uuid import uuid4
        self.submitted.append({
            "source_type": source_type,
            "source_kwargs": source_kwargs,
            "callback_url": callback_url,
            "callback_secret": callback_secret,
        })
        return TranscriptionJob(
            job_id=uuid4().hex,
            status=JobStatus.PENDING,
            source_type=source_type,
            created_at=datetime.now(),
        )

    def submit_batch(self, source_type, items):
        return [self.submit_job(source_type, kw) for kw in items]

    def get_job(self, job_id):
        raise Exception("not used in these tests")

    def get_result(self, job_id):
        raise Exception("not used in these tests")

    def list_jobs(self, page=1, page_size=20):
        return {"jobs": [], "page": page, "page_size": page_size, "total": 0}


@pytest.fixture
def fake_service():
    return FakeServiceWithCallback()


@pytest.fixture
async def client(fake_service, tmp_path):
    from transcritor.api.app import app
    from transcritor.api.dependencies import get_transcription_service
    from transcritor.config import Settings, get_settings

    test_settings = Settings(
        data_dir=tmp_path,
        redis_url="redis://localhost:6379/0",
        whisper_model="base",
        api_key="",
    )
    app.dependency_overrides[get_transcription_service] = lambda: fake_service
    app.dependency_overrides[get_settings] = lambda: test_settings
    get_settings.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Testes para endpoints de URL (JSON body)
# ---------------------------------------------------------------------------

class TestCallbackInAudioUrlEndpoint:
    async def test_accepts_callback_url_in_body(self, client, fake_service):
        resp = await client.post("/transcriptions/audio/url", json={
            "url": "https://example.com/audio.mp3",
            "callback_url": "https://crm.example.com/hook",
        })
        assert resp.status_code == 202

    async def test_passes_callback_url_to_service(self, client, fake_service):
        await client.post("/transcriptions/audio/url", json={
            "url": "https://example.com/audio.mp3",
            "callback_url": "https://crm.example.com/hook",
        })
        assert fake_service.submitted[0]["callback_url"] == "https://crm.example.com/hook"

    async def test_passes_callback_secret_to_service(self, client, fake_service):
        await client.post("/transcriptions/audio/url", json={
            "url": "https://example.com/audio.mp3",
            "callback_url": "https://crm.example.com/hook",
            "callback_secret": "my-secret",
        })
        assert fake_service.submitted[0]["callback_secret"] == "my-secret"

    async def test_callback_url_is_none_when_omitted(self, client, fake_service):
        await client.post("/transcriptions/audio/url", json={
            "url": "https://example.com/audio.mp3",
        })
        assert fake_service.submitted[0]["callback_url"] is None

    async def test_callback_secret_is_none_when_omitted(self, client, fake_service):
        await client.post("/transcriptions/audio/url", json={
            "url": "https://example.com/audio.mp3",
        })
        assert fake_service.submitted[0]["callback_secret"] is None


class TestCallbackInVideoUrlEndpoint:
    async def test_passes_callback_url_to_service(self, client, fake_service):
        await client.post("/transcriptions/video/url", json={
            "url": "https://example.com/video.mp4",
            "callback_url": "https://crm.example.com/hook",
        })
        assert fake_service.submitted[0]["callback_url"] == "https://crm.example.com/hook"

    async def test_callback_url_is_none_when_omitted(self, client, fake_service):
        await client.post("/transcriptions/video/url", json={
            "url": "https://example.com/video.mp4",
        })
        assert fake_service.submitted[0]["callback_url"] is None


# ---------------------------------------------------------------------------
# Testes para endpoints de upload (Form + File)
# ---------------------------------------------------------------------------

class TestCallbackInAudioUploadEndpoint:
    async def test_accepts_callback_url_as_form_field(self, client, fake_service):
        resp = await client.post(
            "/transcriptions/audio",
            files={"file": ("audio.mp3", b"fake audio", "audio/mpeg")},
            data={"callback_url": "https://crm.example.com/hook"},
        )
        assert resp.status_code == 202

    async def test_passes_callback_url_to_service(self, client, fake_service):
        await client.post(
            "/transcriptions/audio",
            files={"file": ("audio.mp3", b"fake audio", "audio/mpeg")},
            data={"callback_url": "https://crm.example.com/hook"},
        )
        assert fake_service.submitted[0]["callback_url"] == "https://crm.example.com/hook"

    async def test_passes_callback_secret_to_service(self, client, fake_service):
        await client.post(
            "/transcriptions/audio",
            files={"file": ("audio.mp3", b"fake audio", "audio/mpeg")},
            data={
                "callback_url": "https://crm.example.com/hook",
                "callback_secret": "shhh",
            },
        )
        assert fake_service.submitted[0]["callback_secret"] == "shhh"

    async def test_callback_url_is_none_when_omitted(self, client, fake_service):
        await client.post(
            "/transcriptions/audio",
            files={"file": ("audio.mp3", b"fake audio", "audio/mpeg")},
        )
        assert fake_service.submitted[0]["callback_url"] is None


class TestCallbackInVideoUploadEndpoint:
    async def test_passes_callback_url_to_service(self, client, fake_service):
        await client.post(
            "/transcriptions/video",
            files={"file": ("video.mp4", b"fake video", "video/mp4")},
            data={"callback_url": "https://crm.example.com/hook"},
        )
        assert fake_service.submitted[0]["callback_url"] == "https://crm.example.com/hook"
