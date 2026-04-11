from pathlib import Path

try:
    from faster_whisper import WhisperModel as FasterWhisperModel
except ImportError:
    FasterWhisperModel = None  # type: ignore[assignment,misc]

from transcritor.core.models import TranscriptionResult


class WhisperEngine:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    def load(self) -> None:
        if FasterWhisperModel is None:
            raise ImportError(
                "faster-whisper is not installed. "
                "Run: pip install 'transcritor[transcription]'"
            )
        self._model = FasterWhisperModel(
            self._model_name,
            device="cpu",
            compute_type="int8",
        )

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if self._model is None:
            raise RuntimeError(
                "Engine not loaded. Call load() before transcribe()."
            )
        segments, info = self._model.transcribe(str(audio_path), beam_size=5)
        text = "".join(segment.text for segment in segments)
        return TranscriptionResult(
            text=text,
            language=info.language,
            duration_seconds=info.duration,
        )
