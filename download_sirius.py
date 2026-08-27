import os
import subprocess
import imageio_ffmpeg
import yt_dlp

os.makedirs("colonne_sonore", exist_ok=True)
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

search_query = "ytsearch1:The Alan Parsons Project Sirius Official Audio"
base_name = "Sirius_Alan_Parsons"

raw_audio_file = os.path.join("colonne_sonore", f"{base_name}_full.m4a")
final_30s_mp3 = os.path.join("colonne_sonore", f"{base_name}_30s.mp3")
final_full_mp3 = os.path.join("colonne_sonore", f"{base_name}_full.mp3")

print(f"--- Downloading HQ Audio for: {search_query} ---")
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': raw_audio_file,
    'overwrites': True,
    'quiet': False,
    'ffmpeg_location': ffmpeg_exe
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([search_query])

print(f"Converting full track to 320kbps MP3: {final_full_mp3}")
cmd_full = [
    ffmpeg_exe, "-y",
    "-i", raw_audio_file,
    "-vn",
    "-c:a", "libmp3lame",
    "-b:a", "320k",
    final_full_mp3
]
subprocess.run(cmd_full, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print(f"Extracting 30s HQ MP3 clip with fade: {final_30s_mp3}")
cmd_30s = [
    ffmpeg_exe, "-y",
    "-ss", "0.0",
    "-i", raw_audio_file,
    "-t", "30.0",
    "-vn",
    "-c:a", "libmp3lame",
    "-b:a", "320k",
    "-af", "afade=t=in:st=0:d=1.5,afade=t=out:st=28.5:d=1.5",
    final_30s_mp3
]
subprocess.run(cmd_30s, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

if os.path.exists(raw_audio_file):
    try:
        os.remove(raw_audio_file)
    except Exception:
        pass

print("DONE! Created Sirius HQ MP3 tracks.")
