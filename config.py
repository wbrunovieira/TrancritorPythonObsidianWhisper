import os

AUDIO_DIRECTORY = './audios'
TRANSCRIPT_DIRECTORY = './transcriptions'


os.makedirs(AUDIO_DIRECTORY, exist_ok=True)
os.makedirs(TRANSCRIPT_DIRECTORY, exist_ok=True)