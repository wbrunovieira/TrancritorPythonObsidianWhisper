from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    def acquire(self) -> Path:
        """Acquire audio from the source and return a path to a local audio file."""
        ...
