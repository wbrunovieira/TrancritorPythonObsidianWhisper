import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from transcritor.sources.video_source import VideoSource
from transcritor.core.exceptions import TranscriptionError

SUPPORTED_VIDEO_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov"]


class TestVideoSource:
    def _make_video_file(self, tmp_path, name="video.mp4"):
        video = tmp_path / name
        video.write_bytes(b"fake video data")
        return video

    def _patch_moviepy(self):
        mock_video = MagicMock()
        mock_video.audio.write_audiofile.return_value = None
        return patch(
            "transcritor.sources.video_source.VideoFileClip",
            return_value=mock_video,
        )

    def test_acquire_returns_path(self, tmp_path):
        video = self._make_video_file(tmp_path)
        with self._patch_moviepy():
            source = VideoSource(video, output_dir=tmp_path)
            result = source.acquire()
        assert isinstance(result, Path)

    def test_acquire_returns_wav_extension(self, tmp_path):
        video = self._make_video_file(tmp_path, "lecture.mp4")
        with self._patch_moviepy():
            source = VideoSource(video, output_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".wav"

    def test_acquire_output_in_correct_directory(self, tmp_path):
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        video = self._make_video_file(tmp_path)
        with self._patch_moviepy():
            source = VideoSource(video, output_dir=audio_dir)
            result = source.acquire()
        assert result.parent == audio_dir

    def test_acquire_preserves_original_stem_in_output_name(self, tmp_path):
        video = self._make_video_file(tmp_path, "my_lecture.mp4")
        with self._patch_moviepy():
            source = VideoSource(video, output_dir=tmp_path)
            result = source.acquire()
        assert result.stem == "my_lecture"

    def test_acquire_calls_write_audiofile_with_pcm_codec(self, tmp_path):
        video = self._make_video_file(tmp_path)
        mock_video = MagicMock()
        with patch("transcritor.sources.video_source.VideoFileClip", return_value=mock_video):
            source = VideoSource(video, output_dir=tmp_path)
            source.acquire()
        mock_video.audio.write_audiofile.assert_called_once()
        call_kwargs = mock_video.audio.write_audiofile.call_args
        assert call_kwargs.kwargs.get("codec") == "pcm_s16le"

    def test_acquire_closes_video_after_extraction(self, tmp_path):
        video = self._make_video_file(tmp_path)
        mock_video = MagicMock()
        with patch("transcritor.sources.video_source.VideoFileClip", return_value=mock_video):
            source = VideoSource(video, output_dir=tmp_path)
            source.acquire()
        mock_video.close.assert_called_once()

    def test_acquire_closes_video_even_on_error(self, tmp_path):
        video = self._make_video_file(tmp_path)
        mock_video = MagicMock()
        mock_video.audio.write_audiofile.side_effect = Exception("write failed")
        with patch("transcritor.sources.video_source.VideoFileClip", return_value=mock_video):
            source = VideoSource(video, output_dir=tmp_path)
            with pytest.raises(TranscriptionError):
                source.acquire()
        mock_video.close.assert_called_once()

    def test_acquire_raises_transcription_error_on_corrupt_video(self, tmp_path):
        video = self._make_video_file(tmp_path)
        with patch(
            "transcritor.sources.video_source.VideoFileClip",
            side_effect=Exception("corrupt file"),
        ):
            source = VideoSource(video, output_dir=tmp_path)
            with pytest.raises(TranscriptionError):
                source.acquire()

    def test_error_message_contains_video_filename(self, tmp_path):
        video = self._make_video_file(tmp_path, "broken_video.mp4")
        with patch(
            "transcritor.sources.video_source.VideoFileClip",
            side_effect=Exception("oops"),
        ):
            source = VideoSource(video, output_dir=tmp_path)
            with pytest.raises(TranscriptionError, match="broken_video.mp4"):
                source.acquire()

    def test_accepts_string_paths(self, tmp_path):
        video = self._make_video_file(tmp_path)
        with self._patch_moviepy():
            source = VideoSource(str(video), output_dir=str(tmp_path))
            result = source.acquire()
        assert isinstance(result, Path)
