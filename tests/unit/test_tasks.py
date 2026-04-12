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


# ---------------------------------------------------------------------------
# Testes de run_extraction
# ---------------------------------------------------------------------------

class TestRunExtraction:
    def test_updates_status_to_processing(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/extracted.wav")

        run_extraction("job123", source, job_store, file_store)

        job_store.update_status.assert_any_call("job123", JobStatus.PROCESSING)

    def test_calls_source_acquire(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/extracted.wav")

        run_extraction("job123", source, job_store, file_store)

        source.acquire.assert_called_once()

    def test_saves_result_with_audio_path(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/extracted.wav")

        run_extraction("job123", source, job_store, file_store)

        file_store.save_result.assert_called_once()
        _, result = file_store.save_result.call_args[0]
        assert result.audio_path == "/tmp/extracted.wav"

    def test_updates_status_to_done_on_success(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/extracted.wav")

        run_extraction("job123", source, job_store, file_store)

        job_store.update_status.assert_called_with("job123", JobStatus.DONE)

    def test_updates_status_to_failed_on_error(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("video broken")

        with pytest.raises(TranscriptionError):
            run_extraction("job123", source, job_store, file_store)

        job_store.update_status.assert_called_with(
            "job123", JobStatus.FAILED, error="video broken"
        )

    def test_does_not_save_result_on_failure(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = MagicMock()
        source.acquire.side_effect = TranscriptionError("boom")

        with pytest.raises(TranscriptionError):
            run_extraction("job123", source, job_store, file_store)

        file_store.save_result.assert_not_called()

    def test_result_has_empty_text(self):
        from transcritor.workers.tasks import run_extraction

        job_store = MagicMock()
        file_store = MagicMock()
        source = _make_fake_source("/tmp/extracted.wav")

        run_extraction("job123", source, job_store, file_store)

        _, result = file_store.save_result.call_args[0]
        assert result.text == ""


# ---------------------------------------------------------------------------
# Testes do _build_source para tipo "extract"
# ---------------------------------------------------------------------------

class TestBuildSourceExtract:
    def test_extract_source_type_recognized(self):
        """extract não deve lançar ValueError (tipo desconhecido)."""
        from transcritor.workers.tasks import _build_source

        mock_settings = MagicMock()
        mock_settings.audio_dir = "/tmp/audio"

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.video_source.VideoSource") as mock_vs:
                mock_vs.return_value = MagicMock()
                try:
                    _build_source("extract", {"path": "/tmp/video.mp4"})
                except ValueError as e:
                    pytest.fail(f"_build_source raised ValueError for 'extract': {e}")


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
                    mock_source.return_value = (_make_fake_source(), [])
                    mock_engine.return_value = _make_fake_engine()

                    from transcritor.workers.tasks import transcribe_task
                    transcribe_task.delay("job123", "file", {"path": "/audio.wav"})

            mock_run.assert_called_once()

        celery_app.conf.task_always_eager = False


# ---------------------------------------------------------------------------
# Testes de limpeza de arquivos temporários
# ---------------------------------------------------------------------------

class TestTranscriptionCleanup:
    def test_audio_file_deleted_after_successful_transcription(self, tmp_path):
        from transcritor.workers.tasks import run_transcription

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file

        run_transcription("job123", source, _make_fake_engine(), job_store, file_store)

        assert not audio_file.exists()

    def test_audio_file_not_deleted_when_transcription_fails(self, tmp_path):
        from transcritor.workers.tasks import run_transcription

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file
        engine = MagicMock()
        engine.transcribe.side_effect = RuntimeError("model crashed")

        with pytest.raises(RuntimeError):
            run_transcription("job123", source, engine, job_store, file_store)

        assert audio_file.exists()

    def test_extra_cleanup_paths_deleted_after_transcription(self, tmp_path):
        from transcritor.workers.tasks import run_transcription

        audio_file = tmp_path / "audio.wav"
        video_file = tmp_path / "video.mp4"
        audio_file.write_bytes(b"fake audio")
        video_file.write_bytes(b"fake video")

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file

        run_transcription("job123", source, _make_fake_engine(), job_store, file_store,
                          cleanup_paths=[video_file])

        assert not video_file.exists()

    def test_extra_cleanup_paths_not_deleted_on_failure(self, tmp_path):
        from transcritor.workers.tasks import run_transcription

        audio_file = tmp_path / "audio.wav"
        video_file = tmp_path / "video.mp4"
        audio_file.write_bytes(b"fake audio")
        video_file.write_bytes(b"fake video")

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file
        engine = MagicMock()
        engine.transcribe.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            run_transcription("job123", source, engine, job_store, file_store,
                              cleanup_paths=[video_file])

        assert video_file.exists()

    def test_cleanup_does_not_raise_if_audio_file_missing(self, tmp_path):
        from transcritor.workers.tasks import run_transcription

        audio_file = tmp_path / "audio.wav"
        # arquivo não existe — não deve lançar exceção

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file

        run_transcription("job123", source, _make_fake_engine(), job_store, file_store)

    def test_extraction_keeps_audio_file(self, tmp_path):
        from transcritor.workers.tasks import run_extraction

        audio_file = tmp_path / "extracted.wav"
        audio_file.write_bytes(b"fake audio")

        job_store, file_store = MagicMock(), MagicMock()
        source = MagicMock()
        source.acquire.return_value = audio_file

        run_extraction("job123", source, job_store, file_store)

        assert audio_file.exists()


# ---------------------------------------------------------------------------
# Testes de _build_source: retorno de cleanup_paths
# ---------------------------------------------------------------------------

class TestBuildSourceCleanupPaths:
    def test_file_source_returns_empty_cleanup(self):
        from transcritor.workers.tasks import _build_source

        with patch("transcritor.sources.file_source.FileSource") as mock_fs:
            mock_fs.return_value = MagicMock()
            _, cleanup = _build_source("file", {"path": "/tmp/audio.wav"})

        assert cleanup == []

    def test_url_source_returns_empty_cleanup(self):
        from transcritor.workers.tasks import _build_source

        mock_settings = MagicMock()
        mock_settings.audio_dir = "/tmp/audio"

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.url_source.UrlSource") as mock_us:
                mock_us.return_value = MagicMock()
                _, cleanup = _build_source("url", {"url": "https://example.com/a.mp3"})

        assert cleanup == []

    def test_youtube_source_returns_empty_cleanup(self):
        from transcritor.workers.tasks import _build_source

        mock_settings = MagicMock()
        mock_settings.audio_dir = "/tmp/audio"

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.youtube_source.YouTubeSource") as mock_yt:
                mock_yt.return_value = MagicMock()
                _, cleanup = _build_source("youtube", {"url": "https://youtube.com/watch?v=x"})

        assert cleanup == []

    def test_video_source_cleanup_includes_original_video(self, tmp_path):
        from pathlib import Path
        from transcritor.workers.tasks import _build_source

        video_file = tmp_path / "video.mp4"
        mock_settings = MagicMock()
        mock_settings.audio_dir = tmp_path

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.video_source.VideoSource") as mock_vs:
                mock_vs.return_value = MagicMock()
                _, cleanup = _build_source("video", {"path": str(video_file)})

        assert Path(str(video_file)) in [Path(str(p)) for p in cleanup]

    def test_video_url_source_cleanup_includes_downloaded_video(self, tmp_path):
        from pathlib import Path
        from transcritor.workers.tasks import _build_source

        fake_video = tmp_path / "downloaded.mp4"
        mock_settings = MagicMock()
        mock_settings.video_dir = tmp_path
        mock_settings.audio_dir = tmp_path

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.url_source.UrlSource") as mock_us:
                mock_us.return_value.acquire.return_value = fake_video
                with patch("transcritor.sources.video_source.VideoSource") as mock_vs:
                    mock_vs.return_value = MagicMock()
                    _, cleanup = _build_source("video_url", {"url": "https://example.com/v.mp4"})

        assert fake_video in cleanup

    def test_extract_source_returns_empty_cleanup(self):
        from transcritor.workers.tasks import _build_source

        mock_settings = MagicMock()
        mock_settings.audio_dir = "/tmp/audio"

        with patch("transcritor.config.get_settings", return_value=mock_settings):
            with patch("transcritor.sources.video_source.VideoSource") as mock_vs:
                mock_vs.return_value = MagicMock()
                _, cleanup = _build_source("extract", {"path": "/tmp/video.mp4"})

        assert cleanup == []
