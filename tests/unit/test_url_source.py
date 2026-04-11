import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from transcritor.sources.url_source import UrlSource
from transcritor.core.exceptions import SourceUnavailableError


def _make_mock_response(content_type="audio/mpeg", content=b"fake audio", status=200):
    response = MagicMock()
    response.headers = {"content-type": content_type}
    response.content = content
    response.raise_for_status.return_value = None
    return response


def _patch_httpx(response):
    """Context manager que substitui httpx.Client pelo mock."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = response
    return patch("transcritor.sources.url_source.httpx.Client", return_value=mock_client)


class TestUrlSource:
    def test_acquire_downloads_and_saves_file(self, tmp_path):
        response = _make_mock_response(content_type="audio/mpeg", content=b"audio data")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/audio.mp3", download_dir=tmp_path)
            result = source.acquire()
        assert result.exists()
        assert result.read_bytes() == b"audio data"

    def test_acquire_returns_path(self, tmp_path):
        response = _make_mock_response()
        with _patch_httpx(response):
            source = UrlSource("https://example.com/audio.mp3", download_dir=tmp_path)
            result = source.acquire()
        assert isinstance(result, Path)

    def test_acquire_infers_mp3_from_content_type(self, tmp_path):
        response = _make_mock_response(content_type="audio/mpeg")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/file", download_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".mp3"

    def test_acquire_infers_wav_from_content_type(self, tmp_path):
        response = _make_mock_response(content_type="audio/wav")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/file", download_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".wav"

    def test_acquire_infers_mp4_from_content_type(self, tmp_path):
        response = _make_mock_response(content_type="video/mp4")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/file", download_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".mp4"

    def test_acquire_infers_extension_from_url_when_content_type_unknown(self, tmp_path):
        response = _make_mock_response(content_type="application/octet-stream")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/audio.wav", download_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".wav"

    def test_acquire_raises_on_http_404(self, tmp_path):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        with patch("transcritor.sources.url_source.httpx.Client", return_value=mock_client):
            source = UrlSource("https://example.com/missing.mp3", download_dir=tmp_path)
            with pytest.raises(SourceUnavailableError):
                source.acquire()

    def test_acquire_raises_on_connection_error(self, tmp_path):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        with patch("transcritor.sources.url_source.httpx.Client", return_value=mock_client):
            source = UrlSource("https://example.com/audio.mp3", download_dir=tmp_path)
            with pytest.raises(SourceUnavailableError):
                source.acquire()

    def test_acquire_error_message_contains_url(self, tmp_path):
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("refused")
        with patch("transcritor.sources.url_source.httpx.Client", return_value=mock_client):
            source = UrlSource("https://my-server.com/audio.mp3", download_dir=tmp_path)
            with pytest.raises(SourceUnavailableError, match="my-server.com"):
                source.acquire()

    def test_acquire_ignores_content_type_params(self, tmp_path):
        """content-type pode vir com charset, ex: 'audio/mpeg; charset=utf-8'"""
        response = _make_mock_response(content_type="audio/mpeg; charset=utf-8")
        with _patch_httpx(response):
            source = UrlSource("https://example.com/file", download_dir=tmp_path)
            result = source.acquire()
        assert result.suffix == ".mp3"
