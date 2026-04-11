class TranscriptionError(Exception):
    """Base exception for all transcription errors."""


class UnsupportedFormatError(TranscriptionError):
    """Raised when the audio/video format is not supported."""


class SourceUnavailableError(TranscriptionError):
    """Raised when the audio source cannot be accessed (file not found, URL error, etc)."""


class JobNotFoundError(TranscriptionError):
    """Raised when a job ID does not exist in the store."""


class JobNotReadyError(TranscriptionError):
    """Raised when trying to fetch a result for a job that is not done yet."""
