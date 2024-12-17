import os
import whisper
import datetime
import soundfile as sf
import warnings
warnings.filterwarnings('ignore', message="FP16 is not supported on CPU; using FP32 instead")


AUDIO_DIRECTORY = './audios'
TRANSCRIPT_DIRECTORY = './transcriptions'

def display_menu():
    """Displays the menu options for the user."""
    print("\033[1;34m\n📢 Audio Transcriber Menu\033[0m\n")  
    print("\033[1;34m\n=========================\033[0m\n")  
    print("\033[1;32m1️⃣  🎙️   - Transcribe from audio file\033[0m\n")  
    print("\033[1;32m2️⃣  🗂️🎙️ - Transcribe from multiple audio files\033[0m\n")  
    print("\033[1;32m3️⃣  🎥   - Transcribe from video file\033[0m\n")  
    print("\033[1;32m4️⃣  🔊   - Transcribe from computer audio output\033[0m\n")  
    print("\033[1;32m5️⃣  🌐   - Transcribe from local environment audio\033[0m\n")  
    print("\033[1;31m6️⃣ 🚪    - Exit\033[0m\n")  
    print("\033[1;34m\n=========================\033[0m\n")  


def transcribe_audio(audio_path, model='base'):
    """Transcribes an audio file using Whisper."""
    print(f"🔄 Transcribing file: {audio_path}")
    whisper_model = whisper.load_model(model)
    result = whisper_model.transcribe(audio_path)
    print(f"✅ Transcription completed for: {audio_path}")
    return result['text']


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


def process_audio_files():
    """Scans the audio directory and processes the audio files."""
    files = os.listdir(AUDIO_DIRECTORY)
    for file_name in files:
        if file_name.endswith(('.mp3', '.wav', '.mp4', '.m4a')):
            file_path = os.path.join(AUDIO_DIRECTORY, file_name)
            transcription = transcribe_audio(file_path)
            save_transcription(file_name, transcription)
        else:
            print(f"❌ Unsupported file format: {file_name}")


if __name__ == "__main__":
    while True:
        display_menu()
        choice = input("👉 Please select an option (1-6): ")
        
        if choice == '1':
            print("🟢 Option 1: Transcribe from audio file selected.")
            files = [f for f in os.listdir(AUDIO_DIRECTORY) if f.endswith(('.mp3', '.wav', '.mp4', '.m4a'))]
            
            if not files:
                print("❌ No audio files found in the directory.")
            else:
                print("\n📂 Available audio files:\n")
                for idx, file_name in enumerate(files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = input("\n👉 Please select the number of the file to transcribe: ")
                
                if file_choice.isdigit() and 1 <= int(file_choice) <= len(files):
                    selected_file = files[int(file_choice) - 1]
                    audio_path = os.path.join(AUDIO_DIRECTORY, selected_file)
                    print(f"📁 Selected file: {audio_path}")
                    transcription = transcribe_audio(audio_path)
                    save_transcription(selected_file, transcription)
                else:
                    print("❌ Invalid selection. Please select a valid file number.")
        
        elif choice == '2':
            print("🟢 Option 2: Transcribe from multiple audio files selected.")
            process_audio_files()

        elif choice == '3':
            print("🟢 Option 3: Transcribe from video file selected.")
        
        elif choice == '4':
            print("🟢 Option 4: Transcribe from computer audio output selected.")
        
        elif choice == '5':
            print("🟢 Option 5: Transcribe from local environment audio selected.")
        
        elif choice == '6':
            print("🏁 Exiting the transcriber. Goodbye!")
            break
        
        else:
            print("❌ Invalid option. Please select a valid option (1-6).")
