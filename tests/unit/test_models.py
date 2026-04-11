import pytest
from datetime import datetime
from transcritor.core.models import JobStatus, TranscriptionJob, TranscriptionResult


class TestJobStatus:
    def test_pending_value(self):
        assert JobStatus.PENDING == "pending"

    def test_processing_value(self):
        assert JobStatus.PROCESSING == "processing"

    def test_done_value(self):
        assert JobStatus.DONE == "done"

    def test_failed_value(self):
        assert JobStatus.FAILED == "failed"

    def test_is_string_enum(self):
        assert isinstance(JobStatus.PENDING, str)


class TestTranscriptionJob:
    def _make_job(self, **kwargs):
        defaults = dict(
            job_id="abc123",
            status=JobStatus.PENDING,
            source_type="file",
            created_at=datetime(2026, 4, 11, 10, 0, 0),
        )
        return TranscriptionJob(**{**defaults, **kwargs})

    def test_required_fields(self):
        job = self._make_job()
        assert job.job_id == "abc123"
        assert job.status == JobStatus.PENDING
        assert job.source_type == "file"

    def test_optional_fields_default_to_none(self):
        job = self._make_job()
        assert job.completed_at is None
        assert job.error is None

    def test_serialization_status_is_string(self):
        job = self._make_job(status=JobStatus.DONE)
        data = job.model_dump()
        assert data["status"] == "done"

    def test_serialization_contains_all_fields(self):
        job = self._make_job()
        data = job.model_dump()
        assert "job_id" in data
        assert "status" in data
        assert "source_type" in data
        assert "created_at" in data
        assert "completed_at" in data
        assert "error" in data

    def test_json_round_trip(self):
        job = self._make_job(status=JobStatus.PROCESSING)
        json_str = job.model_dump_json()
        restored = TranscriptionJob.model_validate_json(json_str)
        assert restored.job_id == job.job_id
        assert restored.status == job.status

    def test_missing_job_id_raises(self):
        with pytest.raises(Exception):
            TranscriptionJob(
                status=JobStatus.PENDING,
                source_type="file",
                created_at=datetime.now(),
            )


class TestTranscriptionResult:
    def test_only_text_required(self):
        result = TranscriptionResult(text="olá mundo")
        assert result.text == "olá mundo"

    def test_optional_fields_default_to_none(self):
        result = TranscriptionResult(text="test")
        assert result.language is None
        assert result.duration_seconds is None

    def test_with_all_fields(self):
        result = TranscriptionResult(
            text="hello world",
            language="en",
            duration_seconds=42.5,
        )
        assert result.language == "en"
        assert result.duration_seconds == 42.5

    def test_serialization(self):
        result = TranscriptionResult(text="test", language="pt")
        data = result.model_dump()
        assert data["text"] == "test"
        assert data["language"] == "pt"
        assert data["duration_seconds"] is None

    def test_empty_text_is_valid(self):
        result = TranscriptionResult(text="")
        assert result.text == ""
