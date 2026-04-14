import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from transcritor.core.exceptions import SourceUnavailableError


class TestYouTubeSource:
    def test_acquire_calls_yt_dlp_with_url(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        source = YouTubeSource(url="https://www.youtube.com/watch?v=abc123", download_dir=tmp_path)

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl.prepare_filename.return_value = str(tmp_path / "video.mp4")
            mock_ydl.extract_info.return_value = {"title": "Test Video"}
            mock_yt.YoutubeDL.return_value = mock_ydl

            # create the file so acquire() can return it
            (tmp_path / "video.mp4").touch()
            (tmp_path / "audio.m4a").touch()

            try:
                source.acquire()
            except Exception:
                pass

            mock_yt.YoutubeDL.assert_called_once()
            call_opts = mock_yt.YoutubeDL.call_args[0][0]
            assert call_opts["format"] == "bestaudio/best"

    def test_acquire_returns_audio_path(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        source = YouTubeSource(url="https://www.youtube.com/watch?v=abc123", download_dir=tmp_path)

        def fake_extract_info(url, download):
            # Simulate yt-dlp creating a file: find the outtmpl from the ydl_opts
            # by creating a file matching the expected pattern
            for f in tmp_path.iterdir():
                pass  # no files yet; we create via side effect below
            return {"title": "Test", "ext": "m4a"}

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            def extract_and_create(url, download):
                # Create a file so _find_downloaded_file can return it
                opts = mock_yt.YoutubeDL.call_args[0][0]
                template = opts["outtmpl"]
                uuid_stem = Path(template).name.split(".")[0]
                audio_file = tmp_path / f"{uuid_stem}.m4a"
                audio_file.write_bytes(b"fake audio")
                return {"title": "Test", "ext": "m4a"}

            mock_ydl.extract_info.side_effect = extract_and_create
            mock_yt.YoutubeDL.return_value = mock_ydl

            result = source.acquire()

        assert isinstance(result, Path)
        assert result.exists()

    def test_acquire_raises_source_unavailable_on_download_error(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        source = YouTubeSource(url="https://www.youtube.com/watch?v=private", download_dir=tmp_path)

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            import yt_dlp as real_yt_dlp
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.side_effect = Exception("Video unavailable")
            mock_yt.YoutubeDL.return_value = mock_ydl
            mock_yt.DownloadError = Exception

            with pytest.raises(SourceUnavailableError, match="unavailable"):
                source.acquire()

    def test_acquire_raises_on_invalid_url(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            YouTubeSource(url="https://example.com/not-youtube", download_dir=tmp_path)

    def test_cookies_file_passed_to_ydl_opts_when_exists(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# cookies")

        source = YouTubeSource(
            url="https://www.youtube.com/watch?v=abc123",
            download_dir=tmp_path,
            cookies_file=cookies_file,
        )

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            def extract_and_create(url, download):
                opts = mock_yt.YoutubeDL.call_args[0][0]
                template = opts["outtmpl"]
                uuid_stem = Path(template).name.split(".")[0]
                (tmp_path / f"{uuid_stem}.m4a").write_bytes(b"fake")
                return {"ext": "m4a"}

            mock_ydl.extract_info.side_effect = extract_and_create
            mock_yt.YoutubeDL.return_value = mock_ydl

            source.acquire()

        opts = mock_yt.YoutubeDL.call_args[0][0]
        assert opts.get("cookiefile") == str(cookies_file)

    def test_cookies_file_not_passed_when_none(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        source = YouTubeSource(
            url="https://www.youtube.com/watch?v=abc123",
            download_dir=tmp_path,
            cookies_file=None,
        )

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            def extract_and_create(url, download):
                opts = mock_yt.YoutubeDL.call_args[0][0]
                template = opts["outtmpl"]
                uuid_stem = Path(template).name.split(".")[0]
                (tmp_path / f"{uuid_stem}.m4a").write_bytes(b"fake")
                return {"ext": "m4a"}

            mock_ydl.extract_info.side_effect = extract_and_create
            mock_yt.YoutubeDL.return_value = mock_ydl

            source.acquire()

        opts = mock_yt.YoutubeDL.call_args[0][0]
        assert "cookiefile" not in opts

    def test_cookies_file_not_passed_when_file_missing(self, tmp_path):
        from transcritor.sources.youtube_source import YouTubeSource

        source = YouTubeSource(
            url="https://www.youtube.com/watch?v=abc123",
            download_dir=tmp_path,
            cookies_file=tmp_path / "nonexistent_cookies.txt",
        )

        with patch("transcritor.sources.youtube_source.yt_dlp") as mock_yt:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            def extract_and_create(url, download):
                opts = mock_yt.YoutubeDL.call_args[0][0]
                template = opts["outtmpl"]
                uuid_stem = Path(template).name.split(".")[0]
                (tmp_path / f"{uuid_stem}.m4a").write_bytes(b"fake")
                return {"ext": "m4a"}

            mock_ydl.extract_info.side_effect = extract_and_create
            mock_yt.YoutubeDL.return_value = mock_ydl

            source.acquire()

        opts = mock_yt.YoutubeDL.call_args[0][0]
        assert "cookiefile" not in opts

    def test_acquire_raises_if_yt_dlp_not_installed(self, tmp_path):
        import sys
        import importlib

        with patch.dict(sys.modules, {"yt_dlp": None}):
            # force reimport with yt_dlp missing
            import transcritor.sources.youtube_source as ys_mod
            importlib.reload(ys_mod)
            if ys_mod.yt_dlp is None:
                source = ys_mod.YouTubeSource.__new__(ys_mod.YouTubeSource)
                source._url = "https://www.youtube.com/watch?v=abc"
                source._download_dir = tmp_path
                with pytest.raises(ImportError, match="yt-dlp"):
                    source.acquire()
