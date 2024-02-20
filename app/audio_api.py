from pytube import YouTube
from pathlib import Path
import os
import urllib

# Function to download audio from YouTube URL
def download_from_youtube(youtube_url: str, output_dir: Path) -> Path:
    yt = YouTube(youtube_url)
    audio = yt.streams.filter(only_audio=True).first()
    audio_file = Path(audio.download(str(output_dir)))
    file_name = urllib.parse.quote(audio_file.name.strip().lower().replace(' ', '_'))
    os.replace(str(audio_file), str(output_dir / file_name))
    return output_dir / file_name
