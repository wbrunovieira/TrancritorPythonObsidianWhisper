import subprocess
from pathlib import Path
from uuid import uuid4

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
    def __init__(self, url: str, download_dir: Path | None = None, cookies_file: Path | None = None):
        if not _is_youtube_url(url):
            raise ValueError(f"Invalid YouTube URL: {url!r}")
        self._url = url
        self._download_dir = download_dir or Path("/tmp")
        self._cookies_file = Path(cookies_file) if cookies_file else None

    def acquire(self) -> Path:
        uuid_stem = uuid4().hex
        output_template = str(self._download_dir / f"{uuid_stem}.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--format", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "--output", output_template,
            "--quiet",
            "--no-warnings",
            "--extract-audio",
            "--audio-format", "m4a",
        ]

        # OAuth2 token persisted in /config (bind mount) — not invalidated on IP change.
        # Token is written there by: yt-dlp --username oauth2 --password '' --cache-dir /config <url>
        oauth_token_file = Path("/config/yt-dlp/youtube-oauth2.token")
        if oauth_token_file.exists():
            cmd += ["--username", "oauth2", "--password", "", "--cache-dir", "/config"]

        cmd.append(self._url)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                raise SourceUnavailableError(
                    f"YouTube download unavailable for {self._url}: {stderr}"
                )
            return self._find_downloaded_file(output_template, uuid_stem)
        except SourceUnavailableError:
            raise
        except Exception as e:
            raise SourceUnavailableError(
                f"Failed to download YouTube video {self._url}: {e}"
            ) from e

    def _find_downloaded_file(self, output_template: str, uuid_stem: str) -> Path:
        parent = Path(output_template).parent
        for ext in ("m4a", "mp3", "ogg", "opus", "wav", "webm"):
            candidate = parent / f"{uuid_stem}.{ext}"
            if candidate.exists():
                return candidate
        raise SourceUnavailableError(
            f"Downloaded file not found for template: {output_template}"
        )
