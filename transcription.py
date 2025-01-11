import whisper

def transcribe_audio(audio_path, model='base'):
    """Transcribes an audio file using Whisper."""
    print(f"🔄 Transcribing file: {audio_path}")
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(audio_path)
    print(f"✅ Transcription completed for: {audio_path}")
    return result['text']