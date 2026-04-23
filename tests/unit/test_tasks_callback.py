"""Testes TDD para o comportamento de callback em run_transcription e run_extraction."""
import pytest
from unittest.mock import MagicMock, patch

from transcritor.core.models import TranscriptionResult, JobStatus
from transcritor.core.exceptions import TranscriptionError


def _make_fake_source(audio_path="/tmp/audio.wav"):
    source = MagicMock()
    source.acquire.return_value = audio_path
    return source


def _make_fake_engine(text="transcribed", language="pt"):
    engine = MagicMock()
    engine.transcribe.return_value = TranscriptionResult(text=text, language=language, duration_seconds=10.0)
    return engine


class TestRunTranscriptionCallbackOnSuccess:
    def test_fires_callback_when_url_provided(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        mock_cb.assert_called_once()

    def test_callback_payload_has_status_done(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        payload = mock_cb.call_args[0][1]
        assert payload["status"] == "done"

    def test_callback_payload_has_job_id(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job-xyz",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        payload = mock_cb.call_args[0][1]
        assert payload["job_id"] == "job-xyz"

    def test_callback_payload_has_transcription_text(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(text="olá mundo"),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        payload = mock_cb.call_args[0][1]
        assert payload["text"] == "olá mundo"

    def test_callback_payload_has_language(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(language="en"),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        payload = mock_cb.call_args[0][1]
        assert payload["language"] == "en"

    def test_callback_passes_secret(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
                callback_secret="super-secret",
            )

        mock_cb.assert_called_once_with(
            "https://crm.example.com/hook",
            mock_cb.call_args[0][1],
            "super-secret",
        )

    def test_no_callback_when_url_is_none(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url=None,
            )

        mock_cb.assert_not_called()

    def test_callback_fired_after_status_updated_to_done(self):
        """O callback deve ser disparado apenas após update_status(DONE)."""
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()
        call_order = []

        job_store.update_status.side_effect = lambda jid, status, **kw: call_order.append(("status", status))

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            mock_cb.side_effect = lambda *a, **kw: call_order.append(("callback", None))
            run_transcription(
                "job1",
                _make_fake_source(),
                _make_fake_engine(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        statuses = [s for kind, s in call_order if kind == "status"]
        callback_idx = next(i for i, (k, _) in enumerate(call_order) if k == "callback")
        done_idx = next(i for i, (k, s) in enumerate(call_order) if k == "status" and s == JobStatus.DONE)
        assert callback_idx > done_idx


class TestRunTranscriptionCallbackOnFailure:
    def test_fires_callback_on_failure_when_url_provided(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("source broken")

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            with pytest.raises(TranscriptionError):
                run_transcription(
                    "job1", source, _make_fake_engine(), job_store, file_store,
                    callback_url="https://crm.example.com/hook",
                )

        mock_cb.assert_called_once()

    def test_failure_callback_payload_has_status_failed(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("boom")

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            with pytest.raises(TranscriptionError):
                run_transcription(
                    "job1", source, _make_fake_engine(), job_store, file_store,
                    callback_url="https://crm.example.com/hook",
                )

        payload = mock_cb.call_args[0][1]
        assert payload["status"] == "failed"

    def test_failure_callback_payload_has_error_message(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("source broken")

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            with pytest.raises(TranscriptionError):
                run_transcription(
                    "job1", source, _make_fake_engine(), job_store, file_store,
                    callback_url="https://crm.example.com/hook",
                )

        payload = mock_cb.call_args[0][1]
        assert "error" in payload
        assert "source broken" in payload["error"]

    def test_no_callback_on_failure_when_url_is_none(self):
        from transcritor.workers.tasks import run_transcription

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("boom")

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            with pytest.raises(TranscriptionError):
                run_transcription(
                    "job1", source, _make_fake_engine(), job_store, file_store,
                    callback_url=None,
                )

        mock_cb.assert_not_called()


class TestRunExtractionCallback:
    def test_fires_callback_on_success(self):
        from transcritor.workers.tasks import run_extraction

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_extraction(
                "job1",
                _make_fake_source("/tmp/audio.wav"),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        mock_cb.assert_called_once()

    def test_extraction_callback_payload_has_status_done(self):
        from transcritor.workers.tasks import run_extraction

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_extraction(
                "job1",
                _make_fake_source(),
                job_store,
                file_store,
                callback_url="https://crm.example.com/hook",
            )

        payload = mock_cb.call_args[0][1]
        assert payload["status"] == "done"

    def test_no_callback_when_url_is_none(self):
        from transcritor.workers.tasks import run_extraction

        job_store, file_store = MagicMock(), MagicMock()

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            run_extraction(
                "job1",
                _make_fake_source(),
                job_store,
                file_store,
                callback_url=None,
            )

        mock_cb.assert_not_called()

    def test_fires_callback_on_failure(self):
        from transcritor.workers.tasks import run_extraction

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("video broken")

        with patch("transcritor.workers.tasks.fire_callback") as mock_cb:
            with pytest.raises(TranscriptionError):
                run_extraction(
                    "job1", source, job_store, file_store,
                    callback_url="https://crm.example.com/hook",
                )

        mock_cb.assert_called_once()
        payload = mock_cb.call_args[0][1]
        assert payload["status"] == "failed"
