from transcritor.config import get_settings
from transcritor.engine.whisper_engine import WhisperEngine

_engine: WhisperEngine | None = None


def get_engine() -> WhisperEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = WhisperEngine(settings.whisper_model)
        _engine.load()
    return _engine
