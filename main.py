from menu import display_menu
from transcription import transcribe_audio
from file_manager import process_multiple_files, get_audio_files, save_transcription
from file_manager import get_audio_files, save_transcription
from utils import get_user_choice
from config import AUDIO_DIRECTORY

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
        choice = get_user_choice("👉 Please select an option (1-6): ", {'1', '2', '3', '4', '5', '6'})
        
        if choice == '1':
            print("🟢 Option 1: Transcribe from audio file selected.")
            files = get_audio_files()
            
            if not files:
                print("❌ No audio files found in the directory.")
            else:
                print("\n📂 Available audio files:\n")
                for idx, file_name in enumerate(files, start=1):
                    print(f"  {idx}. {file_name}")
                
                file_choice = get_user_choice("\n👉 Select the file number to transcribe: ", [str(i) for i in range(1, len(files) + 1)])
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
        
        elif choice == '4':
            print("🟢 Option 4: Transcribe from computer audio output selected.")
        
        elif choice == '5':
            print("🟢 Option 5: Transcribe from local environment audio selected.")
        
        elif choice == '6':
            print("🏁 Exiting the transcriber. Goodbye!")
            break