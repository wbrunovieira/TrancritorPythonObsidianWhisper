# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Transcritor is a Python-based audio/video transcription tool using OpenAI's Whisper model. It provides a command-line menu interface for various transcription tasks including audio files, videos, system audio recording, and batch processing.

## Development Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (openai-whisper is installed from git, not PyPI)
pip install -r requirements.txt

# Run the application
python main.py
```

### Key System Dependencies
- **FFmpeg**: Required for audio/video processing (not in requirements.txt)
- **BlackHole** (macOS): Required for system audio capture (option 5)
- **Python 3.11+**

## Architecture

All source modules live at the project root (no `src/` directory):

| File | Role |
|------|------|
| `main.py` | Entry point — menu loop and option dispatch |
| `menu.py` | `display_menu()` — prints the numbered menu |
| `utils.py` | `get_user_choice()` — validates user input |
| `config.py` | Directory constants (`AUDIO_DIRECTORY`, `VIDEO_DIRECTORY`, `TRANSCRIPT_DIRECTORY`); auto-creates dirs on import |
| `transcription.py` | `transcribe_audio()` (Whisper), `extract_audio_from_video()` (moviepy) |
| `file_manager.py` | `save_transcription()`, `get_audio_files()`, `process_multiple_files()`, `process_video_file()` |
| `system_audio.py` | `record_system_audio_until_stop()` — records via sounddevice, saves WAV |
| `youtube_downloader.py` | `download_youtube_video()` — uses pytube (currently broken) |

### Data Flow
```
User selects menu option
  → file/audio input
  → extract_audio_from_video() if video (moviepy → WAV)
  → transcribe_audio() (Whisper "base" model)
  → save_transcription() → transcriptions/{name}.md
```

### Transcription Output Format
Saved to `transcriptions/{original_name}.md`:
```markdown
# Course Transcription: {filename}
**Transcription Date:** YYYY-MM-DD HH:MM:SS

{transcription text}
```

## Known Broken / Incomplete Features

- **Option 6** (local environment audio): stub only — no implementation
- **Option 7** (voice analysis): imports `voice_analysis.analyze_voice` which does not exist
- **Option 10** (YouTube): `youtube_downloader.py` uses `pytube` which is blocked by YouTube

## Adding New Features

- New functionality belongs in its own module; wire it into `main.py`'s `if/elif` chain
- New directories must be declared and `os.makedirs`'d in `config.py`
- The Whisper model is loaded fresh on every call to `transcribe_audio()` — consider caching it for batch workflows
- Audio files recognised by `get_audio_files()`: `.mp3`, `.wav`, `.mp4`, `.m4a`
- Video files recognised inline in `main.py`: `.mp4`, `.mkv`, `.avi`, `.mov`
