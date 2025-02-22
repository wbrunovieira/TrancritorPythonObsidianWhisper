from pytube import YouTube
from urllib.error import HTTPError
def download_youtube_video(url, output_directory):
    try:
        yt = YouTube(url)
        stream = yt.streams.get_highest_resolution()
        video_path = stream.download(output_path=output_directory)
        if video_path is None:
            print("❌ Download do vídeo falhou. Abortando transcrição.")
            return None
        return video_path
    except HTTPError as e:
        print(f"❌ Erro ao acessar o vídeo: {e}")
        return None