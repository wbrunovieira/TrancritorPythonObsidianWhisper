from pathlib import Path

try:
    import whisper
except ImportError:
    whisper = None  # type: ignore[assignment]

from transcritor.core.models import TranscriptionResult


class WhisperEngine:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    def load(self) -> None:
        if whisper is None:
            raise ImportError(
                "openai-whisper is not installed. "
                "Run: pip install 'transcritor[transcription]'"
            )
        self._model = whisper.load_model(self._model_name)

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if self._model is None:
            raise RuntimeError(
                "Engine not loaded. Call load() before transcribe()."
            )
        result = self._model.transcribe(str(audio_path))
        return TranscriptionResult(
            text=result["text"],
            language=result.get("language"),
        )
