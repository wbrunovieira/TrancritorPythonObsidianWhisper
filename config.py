import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

AUDIO_DIRECTORY = './audios'
TRANSCRIPT_DIRECTORY = './transcriptions'
VIDEO_DIRECTORY = os.path.join(BASE_DIR, './videos')


os.makedirs(AUDIO_DIRECTORY, exist_ok=True)
os.makedirs(TRANSCRIPT_DIRECTORY, exist_ok=True)
os.makedirs(VIDEO_DIRECTORY, exist_ok=True)