from menu import display_menu
from transcription import transcribe_audio
from file_manager import process_multiple_files, get_audio_files, save_transcription
from file_manager import process_video_file
from utils import get_user_choice
from config import AUDIO_DIRECTORY, VIDEO_DIRECTORY

import os

def process_audio_files():
    """Processes all audio files in the directory."""
    files = get_audio_files()
    if not files:
        print("❌ No audio files found in the directory.")
        return
    
    for file_name in files:
        file_path = f"{AUDIO_DIRECTORY}/{file_name}"
        transcription = transcribe_audio(file_path)
        save_transcription(file_name, transcription)

if __name__ == "__main__":
    while True:
        display_menu()
        choice = get_user_choice("👉 Please select an option (1-9): ", 
                                 {'1', '2', '3', '4', '5', '6', '7', '8', '9'})
        
        if choice == '1':
            print("🟢 Option 1: Transcribe from audio file selected.")
            files = get_audio_files()
            if not files:
                print("❌ No audio files found in the directory.")
            else:
                print("\n📂 Available audio files:\n")
                for idx, file_name in enumerate(files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = get_user_choice("\n👉 Select the file number to transcribe: ", 
                                              [str(i) for i in range(1, len(files) + 1)])
                selected_file = files[int(file_choice) - 1]
                audio_path = f"{AUDIO_DIRECTORY}/{selected_file}"
                print(f"📁 Selected file: {audio_path}")
                transcription = transcribe_audio(audio_path)
                save_transcription(selected_file, transcription)
        
        elif choice == '2':
            print("🟢 Option 2: Transcribe from multiple audio files selected.")
            process_multiple_files()
        
        elif choice == '3':
            print("🟢 Option 3: Transcribe from video file selected.")
            video_files = [f for f in os.listdir(VIDEO_DIRECTORY) 
                           if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
            if not video_files:
                print("❌ No video files found in the directory.")
            else:
                print("\n📂 Available video files:\n")
                for idx, file_name in enumerate(video_files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = get_user_choice("\n👉 Select the file number to transcribe: ", 
                                              [str(i) for i in range(1, len(video_files) + 1)])
                selected_file = video_files[int(file_choice) - 1]
                video_path = os.path.join(VIDEO_DIRECTORY, selected_file)
                print(f"🎥 Selected video: {video_path}")
                process_video_file(video_path)
        
        elif choice == '4':
            print("🟢 Option 4: Extract audio from video selected.")
            video_files = [f for f in os.listdir(VIDEO_DIRECTORY) 
                           if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
            if not video_files:
                print("❌ No video files found in the directory.")
            else:
                print("\n📂 Available video files:\n")
                for idx, file_name in enumerate(video_files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = get_user_choice("\n👉 Select the file number to extract audio: ", 
                                              [str(i) for i in range(1, len(video_files) + 1)])
                selected_file = video_files[int(file_choice) - 1]
                video_path = os.path.join(VIDEO_DIRECTORY, selected_file)
                print(f"🎥 Selected video: {video_path}")
                
                from transcription import extract_audio_from_video
                extract_audio_from_video(video_path, AUDIO_DIRECTORY)
        
        elif choice == '5':
            print("🟢 Option 5: Transcribe from computer audio output selected.")
            # Implemente aqui a funcionalidade desejada para capturar áudio da saída do computador
        
        elif choice == '6':
            print("🟢 Option 6: Transcribe from local environment audio selected.")
            # Implemente aqui a funcionalidade desejada para transcrever áudio do ambiente local
        
        elif choice == '7':
            print("🟢 Option 7: Analyze voice from audio selected.")
            audio_files = get_audio_files()
            if not audio_files:
                print("❌ No audio files found in the directory.")
            else:
                print("\n📂 Available audio files:\n")
                for idx, file_name in enumerate(audio_files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = get_user_choice("\n👉 Select the file number to analyze voice: ", 
                                              [str(i) for i in range(1, len(audio_files) + 1)])
                selected_file = audio_files[int(file_choice) - 1]
                audio_path = f"{AUDIO_DIRECTORY}/{selected_file}"
                print(f"📁 Selected file: {audio_path}")
                from voice_analysis import analyze_voice
                analyze_voice(audio_path)
        
        elif choice == '8':
            print("🟢 Option 8: Transcribe ALL video files in the directory.")
            video_files = [f for f in os.listdir(VIDEO_DIRECTORY) 
                           if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
            if not video_files:
                print("❌ No video files found in the directory.")
            else:
                for file_name in video_files:
                    video_path = os.path.join(VIDEO_DIRECTORY, file_name)
                    print(f"🎥 Processing video: {video_path}")
                    process_video_file(video_path)
        
        elif choice == '9':
            print("🏁 Exiting the transcriber. Goodbye!")
            break