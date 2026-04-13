from pathlib import Path

from transcritor.core.exceptions import SourceUnavailableError, UnsupportedFormatError

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".oga"}


class FileSource:
    def __init__(self, path: Path | str):
        self._path = Path(path)

    def acquire(self) -> Path:
        if not self._path.exists():
            raise SourceUnavailableError(f"File not found: {self._path}")

        if self._path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Unsupported format: {self._path.suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return self._path
