import os
import subprocess
import imageio_ffmpeg

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

raw_full_mp3 = os.path.join("colonne_sonore", "Starman_David_Bowie_full.mp3")
final_30s_mp3 = os.path.join("colonne_sonore", "Starman_David_Bowie_30s.mp3")

# Start at 56 seconds (0:56) where the chorus "There's a starman waiting in the sky..." begins
start_sec = 56.0
dur_sec = 30.0

print(f"Extracting 30s Starman chorus clip starting at {start_sec}s (0:56)...")
cmd_30s = [
    ffmpeg_exe, "-y",
    "-ss", str(start_sec),
    "-i", raw_full_mp3,
    "-t", str(dur_sec),
    "-vn",
    "-c:a", "libmp3lame",
    "-b:a", "320k",
    "-af", f"afade=t=in:st=0:d=1.5,afade=t=out:st={dur_sec - 1.5}:d=1.5",
    final_30s_mp3
]
res = subprocess.run(cmd_30s, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"SUCCESS: Created {final_30s_mp3}")
else:
    print("ERROR:", res.stderr.decode('utf-8', errors='ignore'))
