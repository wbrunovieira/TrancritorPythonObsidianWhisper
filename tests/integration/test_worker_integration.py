"""
Testes de integração do worker.

Usam CELERY_TASK_ALWAYS_EAGER=True — tasks rodam síncronas no mesmo processo,
sem Redis ou worker real. O engine é substituído por um stub para não carregar
o modelo Whisper. O filesystem é real (tmp_path).

A task cria internamente suas próprias stores — os testes substituem
redis.from_url e os diretórios via patch para usar fakeredis e tmp_path.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from transcritor.core.models import TranscriptionJob, JobStatus
from transcritor.storage.file_store import FileStore
from transcritor.storage.job_store import JobStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def celery_eager_mode():
    from transcritor.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def fake_redis():
    import fakeredis
    return fakeredis.FakeRedis()


@pytest.fixture
def fake_engine():
    from transcritor.engine.whisper_engine import WhisperEngine
    engine = WhisperEngine.__new__(WhisperEngine)
    engine._model_name = "base"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "text": "integration test transcription",
        "language": "en",
    }
    engine._model = mock_model
    return engine


@pytest.fixture
def transcripts_dir(tmp_path):
    d = tmp_path / "transcripts"
    d.mkdir()
    return d


@pytest.fixture
def audio_dir(tmp_path):
    d = tmp_path / "audio"
    d.mkdir()
    return d


def _run_task(job_id, source_type, source_kwargs, fake_redis, transcripts_dir, fake_engine):
    """
    Executa transcribe_task com todas as dependências reais
    substituídas por fakes: redis, filesystem e engine.
    """
    from transcritor.workers.tasks import transcribe_task

    with patch("transcritor.workers.tasks.get_engine", return_value=fake_engine), \
         patch("transcritor.workers.tasks.redis") as mock_redis_mod, \
         patch("transcritor.workers.tasks.FileStore") as MockFileStore:

        mock_redis_mod.from_url.return_value = fake_redis
        MockFileStore.return_value = FileStore(transcripts_dir)

        transcribe_task.delay(job_id, source_type, source_kwargs)


def _save_job(fake_redis, job_id, source_type="file"):
    from datetime import datetime
    job = TranscriptionJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        source_type=source_type,
        created_at=datetime.now(),
    )
    JobStore(fake_redis).save(job)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestWorkerIntegration:
    def test_task_completes_file_job(self, fake_redis, fake_engine, transcripts_dir, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav")

        _save_job(fake_redis, "integ-job-1")
        _run_task(
            "integ-job-1", "file", {"path": str(audio_file)},
            fake_redis, transcripts_dir, fake_engine
        )

        job = JobStore(fake_redis).load("integ-job-1")
        assert job.status == JobStatus.DONE

    def test_task_saves_transcription_result(self, fake_redis, fake_engine, transcripts_dir, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav")

        _save_job(fake_redis, "integ-job-2")
        _run_task(
            "integ-job-2", "file", {"path": str(audio_file)},
            fake_redis, transcripts_dir, fake_engine
        )

        result = FileStore(transcripts_dir).load_result("integ-job-2")
        assert result.text == "integration test transcription"
        assert result.language == "en"

    def test_task_marks_failed_on_missing_file(self, fake_redis, fake_engine, transcripts_dir):
        _save_job(fake_redis, "integ-job-3")

        with pytest.raises(Exception):
            _run_task(
                "integ-job-3", "file", {"path": "/nonexistent/audio.wav"},
                fake_redis, transcripts_dir, fake_engine
            )

        job = JobStore(fake_redis).load("integ-job-3")
        assert job.status == JobStatus.FAILED
        assert job.error is not None

    def test_task_creates_both_json_and_markdown(self, fake_redis, fake_engine, transcripts_dir, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav")

        _save_job(fake_redis, "integ-job-4")
        _run_task(
            "integ-job-4", "file", {"path": str(audio_file)},
            fake_redis, transcripts_dir, fake_engine
        )

        assert (transcripts_dir / "integ-job-4.json").exists()
        assert (transcripts_dir / "integ-job-4.md").exists()

    def test_task_sets_processing_before_done(self, fake_redis, fake_engine, transcripts_dir, tmp_path):
        """Verifica que o status PROCESSING é gravado antes de DONE."""
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav")

        status_sequence = []
        real_job_store = JobStore(fake_redis)
        original_update = real_job_store.update_status

        def tracking_update(job_id, status, **kwargs):
            status_sequence.append(status)
            original_update(job_id, status, **kwargs)

        _save_job(fake_redis, "integ-job-5")

        with patch("transcritor.workers.tasks.get_engine", return_value=fake_engine), \
             patch("transcritor.workers.tasks.redis") as mock_redis_mod, \
             patch("transcritor.workers.tasks.FileStore") as MockFileStore, \
             patch("transcritor.workers.tasks.JobStore") as MockJobStore:

            mock_redis_mod.from_url.return_value = fake_redis
            MockFileStore.return_value = FileStore(transcripts_dir)
            mock_js = MagicMock(wraps=real_job_store)
            mock_js.update_status.side_effect = tracking_update
            MockJobStore.return_value = mock_js

            from transcritor.workers.tasks import transcribe_task
            transcribe_task.delay("integ-job-5", "file", {"path": str(audio_file)})

        assert status_sequence == [JobStatus.PROCESSING, JobStatus.DONE]
