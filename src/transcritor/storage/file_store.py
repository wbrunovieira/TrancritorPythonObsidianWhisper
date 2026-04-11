from datetime import datetime
from pathlib import Path

from transcritor.core.exceptions import TranscriptionError
from transcritor.core.models import TranscriptionResult


class FileStore:
    def __init__(self, transcripts_dir: Path | str):
        self._dir = Path(transcripts_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, job_id: str, result: TranscriptionResult) -> None:
        (self._dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )
        (self._dir / f"{job_id}.md").write_text(
            self._to_markdown(job_id, result), encoding="utf-8"
        )

    def load_result(self, job_id: str) -> TranscriptionResult:
        path = self._dir / f"{job_id}.json"
        if not path.exists():
            raise TranscriptionError(f"Result not found for job: {job_id}")
        return TranscriptionResult.model_validate_json(path.read_text(encoding="utf-8"))

    def _to_markdown(self, job_id: str, result: TranscriptionResult) -> str:
        lines = [
            f"# Transcription: {job_id}",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        if result.language:
            lines.append(f"**Language:** {result.language}")
        if result.duration_seconds is not None:
            lines.append(f"**Duration:** {result.duration_seconds:.1f}s")
        lines.extend(["", result.text])
        return "\n".join(lines)
