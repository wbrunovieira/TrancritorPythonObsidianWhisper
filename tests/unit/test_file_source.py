import pytest
from pathlib import Path

from transcritor.sources.file_source import FileSource
from transcritor.core.exceptions import UnsupportedFormatError, SourceUnavailableError

SUPPORTED_EXTENSIONS = [".mp3", ".wav", ".m4a", ".flac", ".ogg"]
UNSUPPORTED_EXTENSIONS = [".pdf", ".xyz", ".txt", ".docx", ".py"]


class TestFileSource:
    def test_acquire_returns_path_for_mp3(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake mp3 data")
        source = FileSource(audio)
        assert source.acquire() == audio

    def test_acquire_returns_path_for_wav(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"fake wav data")
        source = FileSource(audio)
        assert source.acquire() == audio

    @pytest.mark.parametrize("ext", SUPPORTED_EXTENSIONS)
    def test_acquire_returns_path_for_all_supported_formats(self, tmp_path, ext):
        audio = tmp_path / f"audio{ext}"
        audio.write_bytes(b"fake data")
        source = FileSource(audio)
        assert source.acquire() == audio

    @pytest.mark.parametrize("ext", UNSUPPORTED_EXTENSIONS)
    def test_acquire_raises_unsupported_format(self, tmp_path, ext):
        file = tmp_path / f"file{ext}"
        file.write_bytes(b"fake data")
        source = FileSource(file)
        with pytest.raises(UnsupportedFormatError):
            source.acquire()

    def test_acquire_raises_if_file_not_found(self, tmp_path):
        missing = tmp_path / "nonexistent.wav"
        source = FileSource(missing)
        with pytest.raises(SourceUnavailableError):
            source.acquire()

    def test_accepts_string_path(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake data")
        source = FileSource(str(audio))
        assert source.acquire() == audio

    def test_error_message_contains_filename(self, tmp_path):
        missing = tmp_path / "my_audio.wav"
        source = FileSource(missing)
        with pytest.raises(SourceUnavailableError, match="my_audio.wav"):
            source.acquire()

    def test_unsupported_format_message_contains_extension(self, tmp_path):
        file = tmp_path / "doc.pdf"
        file.write_bytes(b"fake data")
        source = FileSource(file)
        with pytest.raises(UnsupportedFormatError, match=".pdf"):
            source.acquire()

    def test_case_insensitive_extension(self, tmp_path):
        audio = tmp_path / "audio.MP3"
        audio.write_bytes(b"fake data")
        source = FileSource(audio)
        assert source.acquire() == audio
