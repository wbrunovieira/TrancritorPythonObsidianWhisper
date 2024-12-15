import os
import whisper
import datetime
import soundfile as sf

# Directory paths
AUDIO_DIRECTORY = './audio_files'
TRANSCRIPT_DIRECTORY = './transcripts'

# Function to convert video files to audio

def convert_video_to_audio(file_path, format='wav'):
    """Converts video files to audio in the desired format (wav, mp3, etc.)"""
    filename, extension = os.path.splitext(file_path)
    output_file = f"{filename}.{format}"
    
    command = f"ffmpeg -i \"{file_path}\" -vn -acodec pcm_s16le -ar 44100 -ac 2 \"{output_file}\""
    os.system(command)
    
    return output_file

# Function to transcribe the audio

def transcribe_audio(audio_path, model='base'):
    """Transcribes an audio file using Whisper."""
    print(f"🔄 Transcribing file: {audio_path}")
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(audio_path)
    print(f"✅ Transcription completed for: {audio_path}")
    return result['text']

# Function to save the transcription in Markdown

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

# Main function to process audio files

def process_audio_files():
    """Scans the audio directory and processes the audio files."""
    files = os.listdir(AUDIO_DIRECTORY)
    for file_name in files:
        if file_name.endswith(('.mp3', '.wav', '.mp4', '.m4a')):
            file_path = os.path.join(AUDIO_DIRECTORY, file_name)
            
            # Convert video to audio if necessary
            if file_name.endswith(('.mp4', '.m4a')):
                file_path = convert_video_to_audio(file_path)
            
            # Transcribe the audio
            transcription = transcribe_audio(file_path)
            
            # Save the transcription in Markdown format
            save_transcription(file_name, transcription)
        else:
            print(f"❌ Unsupported file format: {file_name}")

if __name__ == "__main__":
    print("📢 Starting course audio transcriber")
    process_audio_files()
    print("🏁 Transcription process completed!")
