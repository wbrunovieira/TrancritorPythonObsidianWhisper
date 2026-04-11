from pathlib import Path
from uuid import uuid4

import httpx

from transcritor.core.exceptions import SourceUnavailableError

CONTENT_TYPE_TO_EXTENSION: dict[str, str] = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
}


class UrlSource:
    def __init__(self, url: str, download_dir: Path | None = None):
        self._url = url
        self._download_dir = download_dir or Path("/tmp")

    def acquire(self) -> Path:
        try:
            with httpx.Client() as client:
                response = client.get(self._url, follow_redirects=True)
                response.raise_for_status()

            extension = self._resolve_extension(response)
            output_path = self._download_dir / f"{uuid4().hex}{extension}"
            output_path.write_bytes(response.content)
            return output_path

        except httpx.HTTPStatusError as e:
            raise SourceUnavailableError(
                f"HTTP error downloading {self._url}: {e}"
            ) from e
        except httpx.RequestError as e:
            raise SourceUnavailableError(
                f"Connection error downloading {self._url}: {e}"
            ) from e

    def _resolve_extension(self, response: httpx.Response) -> str:
        raw_content_type = response.headers.get("content-type", "")
        content_type = raw_content_type.split(";")[0].strip()
        if content_type in CONTENT_TYPE_TO_EXTENSION:
            return CONTENT_TYPE_TO_EXTENSION[content_type]

        # fallback: infer from URL path
        url_path = Path(self._url.split("?")[0])
        return url_path.suffix or ".tmp"
