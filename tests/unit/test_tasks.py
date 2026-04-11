import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from transcritor.core.models import TranscriptionJob, TranscriptionResult, JobStatus
from transcritor.core.exceptions import TranscriptionError


def _make_job(job_id="job123", status=JobStatus.PENDING) -> TranscriptionJob:
    return TranscriptionJob(
        job_id=job_id,
        status=status,
        source_type="file",
        created_at=datetime(2026, 4, 11, 10, 0, 0),
    )


# ---------------------------------------------------------------------------
# Helpers para substituir dependências reais nas tasks
# ---------------------------------------------------------------------------

def _make_fake_source(audio_path="/tmp/audio.wav"):
    source = MagicMock()
    source.acquire.return_value = audio_path
    return source


def _make_fake_engine(text="hello world", language="pt"):
    engine = MagicMock()
    engine.transcribe.return_value = TranscriptionResult(text=text, language=language)
    return engine


# ---------------------------------------------------------------------------
# Testes da task principal
# ---------------------------------------------------------------------------

class TestTranscribeTask:
    def test_task_updates_status_to_processing(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        job_store.load.return_value = _make_job()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = _make_fake_engine()

        run_transcription("job123", source, engine, job_store, file_store)

        job_store.update_status.assert_any_call("job123", JobStatus.PROCESSING)

    def test_task_calls_source_acquire(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = _make_fake_engine()

        run_transcription("job123", source, engine, job_store, file_store)

        source.acquire.assert_called_once()

    def test_task_calls_engine_transcribe(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/audio.wav")
        engine = _make_fake_engine()

        run_transcription("job123", source, engine, job_store, file_store)

        engine.transcribe.assert_called_once_with("/tmp/audio.wav")

    def test_task_saves_result_to_file_store(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = _make_fake_engine(text="transcribed text")

        run_transcription("job123", source, engine, job_store, file_store)

        file_store.save_result.assert_called_once()
        saved_job_id, saved_result = file_store.save_result.call_args[0]
        assert saved_job_id == "job123"
        assert saved_result.text == "transcribed text"

    def test_task_updates_status_to_done_on_success(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = _make_fake_engine()

        run_transcription("job123", source, engine, job_store, file_store)

        job_store.update_status.assert_called_with("job123", JobStatus.DONE)

    def test_task_updates_status_to_failed_on_source_error(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("source failed")
        engine = _make_fake_engine()

        with pytest.raises(TranscriptionError):
            run_transcription("job123", source, engine, job_store, file_store)

        job_store.update_status.assert_called_with(
            "job123", JobStatus.FAILED, error="source failed"
        )

    def test_task_updates_status_to_failed_on_engine_error(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = MagicMock()
        engine.transcribe.side_effect = RuntimeError("model crashed")

        with pytest.raises(RuntimeError):
            run_transcription("job123", source, engine, job_store, file_store)

        job_store.update_status.assert_called_with(
            "job123", JobStatus.FAILED, error="model crashed"
        )

    def test_task_does_not_save_result_on_failure(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("boom")
        engine = _make_fake_engine()

        with pytest.raises(TranscriptionError):
            run_transcription("job123", source, engine, job_store, file_store)

        file_store.save_result.assert_not_called()

    def test_processing_status_set_before_done(self):
        from transcritor.workers.tasks import run_transcription

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source()
        engine = _make_fake_engine()
        call_order = []

        def track_update(job_id, status, **kwargs):
            call_order.append(status)

        job_store.update_status.side_effect = track_update

        run_transcription("job123", source, engine, job_store, file_store)

        assert call_order == [JobStatus.PROCESSING, JobStatus.DONE]


class TestCeleryTaskDispatch:
    def test_transcribe_task_is_registered(self):
        from transcritor.workers.celery_app import celery_app
        assert "transcritor.workers.tasks.transcribe_task" in celery_app.tasks

    def test_celery_app_has_correct_broker_config(self):
        from transcritor.workers.celery_app import celery_app
        assert celery_app.conf.broker_url is not None

    def test_transcribe_task_dispatches_run_transcription(self):
        """Com ALWAYS_EAGER, a task roda sincrona — verifica que chama run_transcription."""
        from transcritor.workers.celery_app import celery_app
        celery_app.conf.task_always_eager = True

        with patch("transcritor.workers.tasks.run_transcription") as mock_run:
            with patch("transcritor.workers.tasks._build_source") as mock_source:
                with patch("transcritor.workers.tasks.get_engine") as mock_engine:
                    mock_source.return_value = _make_fake_source()
                    mock_engine.return_value = _make_fake_engine()

                    from transcritor.workers.tasks import transcribe_task
                    transcribe_task.delay("job123", "file", {"path": "/audio.wav"})

            mock_run.assert_called_once()

        celery_app.conf.task_always_eager = False
