import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from transcritor.engine.whisper_engine import WhisperEngine
from transcritor.core.models import TranscriptionResult


class TestWhisperEngine:
    def test_transcribe_raises_if_not_loaded(self):
        engine = WhisperEngine("base")
        with pytest.raises(RuntimeError, match="not loaded"):
            engine.transcribe(Path("audio.wav"))

    def test_transcribe_returns_transcription_result(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "olá mundo", "language": "pt"}
        engine._model = mock_model

        result = engine.transcribe(Path("audio.wav"))

        assert isinstance(result, TranscriptionResult)

    def test_transcribe_maps_text_correctly(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "olá mundo", "language": "pt"}
        engine._model = mock_model

        result = engine.transcribe(Path("audio.wav"))

        assert result.text == "olá mundo"

    def test_transcribe_maps_language_correctly(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "hello", "language": "en"}
        engine._model = mock_model

        result = engine.transcribe(Path("audio.wav"))

        assert result.language == "en"

    def test_transcribe_handles_missing_language(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "hello"}
        engine._model = mock_model

        result = engine.transcribe(Path("audio.wav"))

        assert result.language is None

    def test_transcribe_passes_path_as_string_to_model(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "test"}
        engine._model = mock_model

        engine.transcribe(Path("/some/path/audio.wav"))

        mock_model.transcribe.assert_called_once_with("/some/path/audio.wav")

    def test_load_calls_whisper_load_model(self):
        engine = WhisperEngine("base")
        with patch("transcritor.engine.whisper_engine.whisper") as mock_whisper:
            engine.load()
            mock_whisper.load_model.assert_called_once_with("base")

    def test_load_stores_model(self):
        engine = WhisperEngine("base")
        mock_model = MagicMock()
        with patch("transcritor.engine.whisper_engine.whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model
            engine.load()
        assert engine._model is mock_model

    def test_load_uses_configured_model_name(self):
        engine = WhisperEngine("small")
        with patch("transcritor.engine.whisper_engine.whisper") as mock_whisper:
            engine.load()
            mock_whisper.load_model.assert_called_once_with("small")


class TestGetEngine:
    def test_returns_whisper_engine_instance(self, reset_engine):
        with patch("transcritor.engine.whisper_engine.WhisperEngine.load"):
            from transcritor.engine.registry import get_engine
            engine = get_engine()
        assert isinstance(engine, WhisperEngine)

    def test_returns_singleton(self, reset_engine):
        with patch("transcritor.engine.whisper_engine.WhisperEngine.load"):
            from transcritor.engine.registry import get_engine
            engine1 = get_engine()
            engine2 = get_engine()
        assert engine1 is engine2

    def test_calls_load_only_once(self, reset_engine):
        with patch.object(WhisperEngine, "load") as mock_load:
            from transcritor.engine.registry import get_engine
            get_engine()
            get_engine()
            get_engine()
        mock_load.assert_called_once()

    def test_uses_model_from_settings(self, reset_engine, reset_settings):
        with patch.dict("os.environ", {"WHISPER_MODEL": "small"}):
            with patch.object(WhisperEngine, "load"):
                from transcritor.engine.registry import get_engine
                engine = get_engine()
        assert engine._model_name == "small"
