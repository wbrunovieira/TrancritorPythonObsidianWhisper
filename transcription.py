import whisper
import os
from moviepy.video.io.VideoFileClip import VideoFileClip

def transcribe_audio(audio_path, model='base'):
    """Transcribes an audio file using Whisper."""
    print(f"🔄 Transcribing file: {audio_path}")
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(audio_path)
    print(f"✅ Transcription completed for: {audio_path}")
    return result['text']

def extract_audio_from_video(video_path, output_directory='./'):
    """Extracts the audio from a video file and saves it as a .wav file."""
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_directory, f"{video_name}.wav")
    
    print(f"🎥 Extracting audio from video: {video_path}")
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, codec="pcm_s16le", logger=None)
    print(f"✅ Audio extracted and saved to: {audio_path}")
    
    return audio_path