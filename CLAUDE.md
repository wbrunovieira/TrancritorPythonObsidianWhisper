# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Transcritor is a REST API service for async audio/video transcription using `faster-whisper` (`large-v3-turbo` model). It is a pure backend — no CLI, no frontend. Other apps on the same server consume it via HTTP.

**Stack:** FastAPI + Celery + Redis + faster-whisper (CTranslate2, int8 on CPU) + Docker Compose.

## Development Commands

```bash
# Setup
source venv/bin/activate
pip install -e ".[transcription,api,dev]"

# Run tests
python -m pytest tests/unit/ tests/integration/   # fast, no Docker needed
python -m pytest tests/unit/ tests/integration/ -q --tb=short
python -m pytest tests/unit/test_whisper_engine.py -v  # single file
python -m pytest -m "not slow and not e2e"         # skip heavy tests

# Run locally (requires Redis)
uvicorn transcritor.api.app:app --reload

# Run with Docker (full stack)
docker compose up --build
docker compose logs -f worker    # watch worker logs
```

**System dependencies:** FFmpeg (required by moviepy and yt-dlp), Python 3.11+.

## Architecture

```
src/transcritor/
├── api/
│   ├── app.py               # FastAPI app, lifespan, global exception handler
│   ├── dependencies.py      # get_transcription_service()
│   ├── schemas.py           # Request/response Pydantic models
│   └── routers/
│       ├── transcriptions.py  # all /transcriptions/* routes
│       └── health.py          # /health, /ready
├── core/
│   ├── models.py            # JobStatus, TranscriptionJob, TranscriptionResult
│   └── exceptions.py        # TranscriptionError, SourceUnavailableError, JobNotFoundError, JobNotReadyError
├── config.py                # Settings (pydantic-settings); get_settings() cached singleton
├── logging_config.py        # configure_logging() — call once at startup
├── engine/
│   ├── whisper_engine.py    # WhisperEngine: load() + transcribe() → TranscriptionResult
│   └── registry.py          # get_engine() → process-level singleton
├── sources/
│   ├── base.py              # AudioSource Protocol: .acquire() → Path
│   ├── file_source.py       # local uploaded file
│   ├── url_source.py        # generic HTTP URL (Drive, S3, etc.)
│   ├── video_source.py      # extract audio from video via moviepy
│   ├── youtube_source.py    # YouTube URL via yt-dlp
│   └── system_audio.py      # desktop audio capture (not used by API)
├── storage/
│   ├── file_store.py        # save/load TranscriptionResult as .json + .md
│   └── job_store.py         # job status in Redis; sorted set for listing
├── services/
│   └── transcription_service.py  # submit_job(), get_job(), get_result(), list_jobs()
└── workers/
    ├── celery_app.py        # Celery instance; loads Whisper model on worker_process_init
    └── tasks.py             # transcribe_task: _build_source() → run_transcription() or run_extraction()
```

## API Routes

```
POST   /transcriptions/audio              # upload file
POST   /transcriptions/audio/url          # via HTTP URL
POST   /transcriptions/audio/batch        # multiple uploads
POST   /transcriptions/video              # upload video file
POST   /transcriptions/video/url          # HTTP URL or YouTube (auto-detected)
POST   /transcriptions/video/batch        # multiple video uploads
POST   /transcriptions/video/extract      # extract audio only, no transcription
GET    /transcriptions                    # list jobs (paginated)
GET    /transcriptions/{job_id}           # job status
GET    /transcriptions/{job_id}/result    # result when done
GET    /health                            # liveness
GET    /ready                             # readiness (checks Redis + model)
```

Swagger UI: `http://localhost:8000/docs`

## Key Design Decisions

- **`_build_source(source_type, source_kwargs)`** in `tasks.py` is the dispatch table for all input types. Add new source types here.
- **`/video/url`** auto-detects YouTube URLs via `_is_youtube_url()` and routes to `YouTubeSource`, otherwise `UrlSource` + `VideoSource`.
- **`get_engine()`** returns a process-level singleton — Whisper model is loaded once per worker process, not per job.
- **`faster-whisper` API:** `model.transcribe()` returns `(segments_generator, info)`. Collect with `list()` before iterating — the generator is consumed once. Each segment has `.text`, `.start`, `.end`.
- **`TranscriptionResult.segments`** is always populated by the engine: `[TranscriptionSegment(start, end, text), ...]`. Stored in the `.json` result file. Old results without segments deserialize to `[]`.
- **`_build_source(source_type, source_kwargs)`** returns `(source, cleanup_paths)`. After successful transcription, `run_transcription()` deletes the audio file and any paths in `cleanup_paths` (e.g. source video for `video` and `video_url` jobs).
- **`compute_type="int8"`** on CPU: ~4× faster than openai-whisper with minimal quality loss.
- **Job persistence:** status in Redis (sorted set `jobs:all` for listing); result as `.json` + `.md` on disk. Audio/video files are deleted after transcription — only the transcript is kept.

## Testing Strategy

- **Unit tests** (`tests/unit/`): no I/O, no Redis, no model — mock everything. Run in milliseconds.
- **Integration tests** (`tests/integration/`): real FastAPI + real filesystem + `FakeRedis` + stubbed engine. `CELERY_TASK_ALWAYS_EAGER=True`.
- **E2e tests** (`tests/e2e/`): full Docker stack required. Run with `-m e2e`.
- `faster-whisper` mock: `model.transcribe()` must return `([mock_segment], mock_info)` where `mock_segment.text`, `.start`, `.end` are set and `mock_info.language`/`mock_info.duration` are set.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `large-v3-turbo` | faster-whisper model name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `DATA_DIR` | `~/.transcritor` | Root for audio/, video/, transcripts/ |
| `LOG_LEVEL` | `INFO` | Logging level |

In Docker, `REDIS_URL` must use the service hostname: `redis://redis:6379/0`.
