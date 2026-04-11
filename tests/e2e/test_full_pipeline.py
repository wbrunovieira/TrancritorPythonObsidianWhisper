"""
Testes E2E — requerem o stack completo rodando via docker-compose.

Para rodar:
    docker-compose up -d
    pytest tests/e2e/ -m e2e -v
    docker-compose down

Excluídos do pytest padrão (sem a flag -m e2e).
"""
import io
import math
import struct
import time
import wave

import httpx
import pytest

BASE_URL = "http://localhost:8000"
POLL_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_wav_bytes(duration: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Gera um arquivo WAV válido com tom de 440Hz — sem dependências externas."""
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n_frames = int(sample_rate * duration)
        frames = b"".join(
            struct.pack("<h", int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate)))
            for i in range(n_frames)
        )
        wf.writeframes(frames)
    return buf.getvalue()


def poll_until_done(job_id: str, timeout: int = POLL_TIMEOUT_SECONDS) -> dict:
    """Faz polling do status do job até DONE ou FAILED."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
        if data["status"] == "done":
            return data
        if data["status"] == "failed":
            pytest.fail(f"Job {job_id} failed: {data.get('error')}")
        time.sleep(POLL_INTERVAL_SECONDS)
    pytest.fail(f"Job {job_id} timed out after {timeout}s")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wav_audio() -> bytes:
    return generate_wav_bytes(duration=3.0)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestHealthEndpoints:
    def test_health_returns_200(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_ready_returns_200(self):
        r = httpx.get(f"{BASE_URL}/ready", timeout=5)
        assert r.status_code == 200
        assert r.json()["redis"] == "ok"

    def test_openapi_docs_available(self):
        r = httpx.get(f"{BASE_URL}/docs", timeout=5)
        assert r.status_code == 200


@pytest.mark.e2e
class TestAudioUploadPipeline:
    def test_submit_returns_202_with_job_id(self, wav_audio):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("test.wav", wav_audio, "audio/wav")},
            timeout=15,
        )
        assert r.status_code == 202
        assert "job_id" in r.json()

    def test_full_pipeline_completes(self, wav_audio):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("test.wav", wav_audio, "audio/wav")},
            timeout=15,
        )
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        poll_until_done(job_id)

        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}/result", timeout=10)
        assert r.status_code == 200
        assert "text" in r.json()
        assert r.json()["job_id"] == job_id

    def test_result_has_language_field(self, wav_audio):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("test.wav", wav_audio, "audio/wav")},
            timeout=15,
        )
        job_id = r.json()["job_id"]
        poll_until_done(job_id)

        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}/result", timeout=10)
        assert "language" in r.json()

    def test_status_transitions_pending_to_done(self, wav_audio):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("test.wav", wav_audio, "audio/wav")},
            timeout=15,
        )
        job_id = r.json()["job_id"]

        # Immediately after submit, should be pending or processing
        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}", timeout=10)
        assert r.json()["status"] in ("pending", "processing", "done")

        poll_until_done(job_id)

        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}", timeout=10)
        assert r.json()["status"] == "done"
        assert r.json()["completed_at"] is not None

    def test_result_returns_409_before_done(self, wav_audio):
        """Submete job e tenta buscar resultado imediatamente — deve retornar 409."""
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("test.wav", wav_audio, "audio/wav")},
            timeout=15,
        )
        job_id = r.json()["job_id"]

        # Tenta buscar resultado logo após submit
        r = httpx.get(f"{BASE_URL}/transcriptions/{job_id}/result", timeout=10)
        # Pode ser 409 (não pronto) ou 200 (se worker foi muito rápido)
        assert r.status_code in (200, 409)


@pytest.mark.e2e
class TestErrorHandling:
    def test_unsupported_audio_format_returns_422(self):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/audio",
            files={"file": ("doc.pdf", b"fake pdf", "application/pdf")},
            timeout=10,
        )
        assert r.status_code == 422

    def test_unsupported_video_format_returns_422(self):
        r = httpx.post(
            f"{BASE_URL}/transcriptions/video",
            files={"file": ("doc.txt", b"fake txt", "text/plain")},
            timeout=10,
        )
        assert r.status_code == 422

    def test_unknown_job_id_returns_404(self):
        r = httpx.get(f"{BASE_URL}/transcriptions/nonexistent-job-id", timeout=10)
        assert r.status_code == 404
