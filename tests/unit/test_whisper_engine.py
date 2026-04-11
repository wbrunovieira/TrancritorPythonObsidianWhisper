import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from transcritor.engine.whisper_engine import WhisperEngine
from transcritor.core.models import TranscriptionResult


def _make_mock_model(text=" olá mundo", language="pt", duration=10.5):
    """Retorna mock que imita a API do faster-whisper."""
    mock_segment = MagicMock()
    mock_segment.text = text

    mock_info = MagicMock()
    mock_info.language = language
    mock_info.duration = duration

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    return mock_model


class TestWhisperEngine:
    def test_transcribe_raises_if_not_loaded(self):
        engine = WhisperEngine("small")
        with pytest.raises(RuntimeError, match="not loaded"):
            engine.transcribe(Path("audio.wav"))

    def test_transcribe_returns_transcription_result(self):
        engine = WhisperEngine("small")
        engine._model = _make_mock_model()

        result = engine.transcribe(Path("audio.wav"))

        assert isinstance(result, TranscriptionResult)

    def test_transcribe_maps_text_correctly(self):
        engine = WhisperEngine("small")
        engine._model = _make_mock_model(text=" olá mundo")

        result = engine.transcribe(Path("audio.wav"))

        assert result.text == " olá mundo"

    def test_transcribe_joins_multiple_segments(self):
        """faster-whisper retorna segmentos — todos devem ser concatenados."""
        engine = WhisperEngine("small")

        seg1 = MagicMock()
        seg1.text = " Primeiro segmento."
        seg2 = MagicMock()
        seg2.text = " Segundo segmento."
        mock_info = MagicMock()
        mock_info.language = "pt"
        mock_info.duration = 20.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg1, seg2], mock_info)
        engine._model = mock_model

        result = engine.transcribe(Path("audio.wav"))

        assert result.text == " Primeiro segmento. Segundo segmento."

    def test_transcribe_maps_language_correctly(self):
        engine = WhisperEngine("small")
        engine._model = _make_mock_model(language="en")

        result = engine.transcribe(Path("audio.wav"))

        assert result.language == "en"

    def test_transcribe_maps_duration_correctly(self):
        engine = WhisperEngine("small")
        engine._model = _make_mock_model(duration=42.5)

        result = engine.transcribe(Path("audio.wav"))

        assert result.duration_seconds == 42.5

    def test_transcribe_passes_path_as_string_to_model(self):
        engine = WhisperEngine("small")
        engine._model = _make_mock_model()

        engine.transcribe(Path("/some/path/audio.wav"))

        engine._model.transcribe.assert_called_once_with(
            "/some/path/audio.wav", beam_size=5
        )

    def test_load_creates_faster_whisper_model(self):
        engine = WhisperEngine("small")
        with patch("transcritor.engine.whisper_engine.FasterWhisperModel") as mock_cls:
            engine.load()
            mock_cls.assert_called_once_with("small", device="cpu", compute_type="int8")

    def test_load_stores_model(self):
        engine = WhisperEngine("small")
        mock_instance = MagicMock()
        with patch("transcritor.engine.whisper_engine.FasterWhisperModel", return_value=mock_instance):
            engine.load()
        assert engine._model is mock_instance

    def test_load_uses_configured_model_name(self):
        engine = WhisperEngine("turbo")
        with patch("transcritor.engine.whisper_engine.FasterWhisperModel") as mock_cls:
            engine.load()
            mock_cls.assert_called_once_with("turbo", device="cpu", compute_type="int8")


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
