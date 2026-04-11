from pathlib import Path
from uuid import uuid4

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore[assignment]

from transcritor.core.exceptions import SourceUnavailableError

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}


def _is_youtube_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        return host in _YOUTUBE_HOSTS
    except Exception:
        return False


class YouTubeSource:
    def __init__(self, url: str, download_dir: Path | None = None):
        if not _is_youtube_url(url):
            raise ValueError(f"Invalid YouTube URL: {url!r}")
        self._url = url
        self._download_dir = download_dir or Path("/tmp")

    def acquire(self) -> Path:
        if yt_dlp is None:
            raise ImportError(
                "yt-dlp is not installed. "
                "Run: pip install 'transcritor[transcription]'"
            )

        output_template = str(self._download_dir / f"{uuid4().hex}.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self._url, download=True)
                # After postprocessing, find the downloaded audio file
                downloaded = self._find_downloaded_file(output_template, info)
                return downloaded
        except Exception as e:
            _download_error = getattr(yt_dlp, "DownloadError", None)
            is_download_error = (
                isinstance(_download_error, type)
                and issubclass(_download_error, BaseException)
                and isinstance(e, _download_error)
            )
            if is_download_error:
                raise SourceUnavailableError(
                    f"YouTube download unavailable for {self._url}: {e}"
                ) from e
            raise SourceUnavailableError(
                f"Failed to download YouTube video {self._url}: {e}"
            ) from e

    def _find_downloaded_file(self, output_template: str, info: dict) -> Path:
        # output_template is like "/tmp/<uuid>.%(ext)s"
        # Split on "." and take the first part (the UUID) as the stem
        parent = Path(output_template).parent
        uuid_stem = Path(output_template).name.split(".")[0]

        # Try known audio extensions in preference order
        for ext in ("m4a", "mp3", "ogg", "opus", "wav", "webm"):
            candidate = parent / f"{uuid_stem}.{ext}"
            if candidate.exists():
                return candidate
        # Fallback: use the ext reported by yt-dlp before postprocessing
        if info and "ext" in info:
            candidate = parent / f"{uuid_stem}.{info['ext']}"
            if candidate.exists():
                return candidate
        raise SourceUnavailableError(
            f"Downloaded file not found for template: {output_template}"
        )
