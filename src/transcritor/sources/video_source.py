from pathlib import Path

from transcritor.core.exceptions import TranscriptionError

try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
except ImportError:
    VideoFileClip = None  # type: ignore[assignment,misc]


class VideoSource:
    def __init__(self, video_path: Path | str, output_dir: Path | str):
        self._video_path = Path(video_path)
        self._output_dir = Path(output_dir)

    def acquire(self) -> Path:
        if VideoFileClip is None:
            raise ImportError(
                "moviepy is not installed. "
                "Run: pip install 'transcritor[transcription]'"
            )

        audio_path = self._output_dir / f"{self._video_path.stem}.wav"
        video = None
        try:
            video = VideoFileClip(str(self._video_path))
            video.audio.write_audiofile(
                str(audio_path),
                codec="pcm_s16le",
                logger=None,
            )
            return audio_path
        except Exception as e:
            raise TranscriptionError(
                f"Failed to extract audio from {self._video_path.name}: {e}"
            ) from e
        finally:
            if video is not None:
                video.close()
