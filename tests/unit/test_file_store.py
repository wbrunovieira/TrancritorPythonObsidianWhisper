import json
import pytest

from transcritor.storage.file_store import FileStore
from transcritor.core.models import TranscriptionResult
from transcritor.core.exceptions import TranscriptionError


@pytest.fixture
def store(tmp_path):
    return FileStore(tmp_path)


@pytest.fixture
def result():
    return TranscriptionResult(text="hello world", language="pt", duration_seconds=42.5)


class TestFileStoreSave:
    def test_save_creates_json_file(self, store, tmp_path, result):
        store.save_result("job123", result)
        assert (tmp_path / "job123.json").exists()

    def test_save_creates_markdown_file(self, store, tmp_path, result):
        store.save_result("job123", result)
        assert (tmp_path / "job123.md").exists()

    def test_json_contains_text(self, store, tmp_path, result):
        store.save_result("job123", result)
        data = json.loads((tmp_path / "job123.json").read_text())
        assert data["text"] == "hello world"

    def test_json_contains_language(self, store, tmp_path, result):
        store.save_result("job123", result)
        data = json.loads((tmp_path / "job123.json").read_text())
        assert data["language"] == "pt"

    def test_json_contains_duration(self, store, tmp_path, result):
        store.save_result("job123", result)
        data = json.loads((tmp_path / "job123.json").read_text())
        assert data["duration_seconds"] == 42.5

    def test_markdown_contains_text(self, store, tmp_path, result):
        store.save_result("job123", result)
        md = (tmp_path / "job123.md").read_text()
        assert "hello world" in md

    def test_markdown_contains_language(self, store, tmp_path, result):
        store.save_result("job123", result)
        md = (tmp_path / "job123.md").read_text()
        assert "pt" in md

    def test_markdown_contains_job_id(self, store, tmp_path, result):
        store.save_result("job123", result)
        md = (tmp_path / "job123.md").read_text()
        assert "job123" in md

    def test_creates_directory_if_not_exists(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        store = FileStore(nested)
        store.save_result("job1", TranscriptionResult(text="test"))
        assert (nested / "job1.json").exists()


class TestFileStoreLoad:
    def test_load_returns_correct_text(self, store, result):
        store.save_result("job123", result)
        loaded = store.load_result("job123")
        assert loaded.text == "hello world"

    def test_load_returns_correct_language(self, store, result):
        store.save_result("job123", result)
        loaded = store.load_result("job123")
        assert loaded.language == "pt"

    def test_load_returns_correct_duration(self, store, result):
        store.save_result("job123", result)
        loaded = store.load_result("job123")
        assert loaded.duration_seconds == 42.5

    def test_load_raises_if_not_found(self, store):
        with pytest.raises(TranscriptionError):
            store.load_result("nonexistent")

    def test_load_error_message_contains_job_id(self, store):
        with pytest.raises(TranscriptionError, match="nonexistent-job"):
            store.load_result("nonexistent-job")

    def test_json_round_trip(self, store, result):
        store.save_result("job123", result)
        loaded = store.load_result("job123")
        assert loaded.model_dump() == result.model_dump()
