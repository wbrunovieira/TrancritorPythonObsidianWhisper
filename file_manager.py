import os
import datetime
from transcription import transcribe_audio
from config import AUDIO_DIRECTORY, TRANSCRIPT_DIRECTORY

def get_audio_files():
    """Returns a list of audio files in the directory."""
    return [f for f in os.listdir(AUDIO_DIRECTORY) if f.endswith(('.mp3', '.wav', '.mp4', '.m4a'))]

def save_transcription(file_name, transcription):
    """Saves the transcription in Markdown (.md) format."""
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    markdown_file_name = os.path.splitext(file_name)[0] + '.md'
    transcription_path = os.path.join(TRANSCRIPT_DIRECTORY, markdown_file_name)
    
    with open(transcription_path, 'w', encoding='utf-8') as markdown_file:
        markdown_file.write(f"# Course Transcription: {file_name}\n")
        markdown_file.write(f"**Transcription Date:** {current_date}\n\n")
        markdown_file.write(transcription)
    
    print(f"💾 Transcription saved in: {transcription_path}")

def process_multiple_files():
    """Processes and transcribes all audio files in the directory."""
    files = [f for f in os.listdir(AUDIO_DIRECTORY) if f.endswith(('.mp3', '.wav', '.mp4', '.m4a'))]

    if not files:
        print("❌ No audio files found in the directory.")
        return
    
    print(f"📂 Found {len(files)} audio files. Starting transcription...")
    for idx, file_name in enumerate(files, start=1):
        file_path = os.path.join(AUDIO_DIRECTORY, file_name)
        print(f"🔄 Transcribing file {idx}/{len(files)}: {file_name}")
        transcription = transcribe_audio(file_path)
        save_transcription(file_name, transcription)
    print("✅ All files have been transcribed successfully.")