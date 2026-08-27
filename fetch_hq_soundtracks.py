import os
import subprocess
import imageio_ffmpeg
import yt_dlp

os.makedirs("colonne_sonore", exist_ok=True)
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

def download_and_trim_hq_audio(search_query: str, base_name: str, start_sec: float = 0.0, dur_sec: float = 30.0):
    print(f"\n--- Searching and downloading HQ Audio for: {search_query} ---")
    
    raw_audio_file = os.path.join("colonne_sonore", f"{base_name}_full.m4a")
    final_30s_mp3 = os.path.join("colonne_sonore", f"{base_name}_30s.mp3")
    final_full_mp3 = os.path.join("colonne_sonore", f"{base_name}_full.mp3")

    # Configure yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': raw_audio_file,
        'overwrites': True,
        'quiet': False,
        'ffmpeg_location': ffmpeg_exe
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([search_query])

    # Convert full audio to high quality MP3 (320kbps)
    print(f"Converting to full HQ MP3: {final_full_mp3}")
    cmd_full = [
        ffmpeg_exe, "-y",
        "-i", raw_audio_file,
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        final_full_mp3
    ]
    subprocess.run(cmd_full, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Extract 30-second HQ MP3 clip with smooth fade-in and fade-out
    print(f"Extracting 30s HQ MP3 clip: {final_30s_mp3}")
    cmd_30s = [
        ffmpeg_exe, "-y",
        "-ss", str(start_sec),
        "-i", raw_audio_file,
        "-t", str(dur_sec),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        "-af", f"afade=t=in:st=0:d=1.5,afade=t=out:st={dur_sec - 1.5}:d=1.5",
        final_30s_mp3
    ]
    subprocess.run(cmd_30s, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Clean up temp raw file
    if os.path.exists(raw_audio_file):
        try:
            os.remove(raw_audio_file)
        except Exception:
            pass

    print(f"DONE: Created {final_30s_mp3} and {final_full_mp3}")

# 1. Hans Zimmer - Interstellar Main Theme
download_and_trim_hq_audio("ytsearch1:Hans Zimmer Interstellar Main Theme Official Audio", "Interstellar_Hans_Zimmer", start_sec=20.0, dur_sec=30.0)

# 2. Beethoven - Moonlight Sonata
download_and_trim_hq_audio("ytsearch1:Beethoven Moonlight Sonata 1st Movement Piano", "Beethoven_Moonlight_Sonata", start_sec=15.0, dur_sec=30.0)

# 3. Beethoven - 5th Symphony
download_and_trim_hq_audio("ytsearch1:Beethoven 5th Symphony First Movement Allegro con brio", "Beethoven_5th_Symphony", start_sec=0.0, dur_sec=30.0)

