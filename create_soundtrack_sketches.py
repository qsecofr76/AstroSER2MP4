import os
import wave
import numpy as np

os.makedirs("colonne_sonore", exist_ok=True)

def write_wav(filename: str, samples: np.ndarray, sample_rate: int = 44100):
    samples_clipped = np.clip(samples, -1.0, 1.0)
    int_samples = (samples_clipped * 32767).astype(np.int16)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        stereo_samples = np.column_stack((int_samples, int_samples)).flatten()
        wav_file.writeframes(stereo_samples.tobytes())

sr = 44100
dur = 30.0
N = int(sr * dur)
t = np.linspace(0, dur, N, endpoint=False)
fade_len = int(sr * 1.5)
fade = np.ones(N)
fade[:fade_len] = np.linspace(0, 1, fade_len)
fade[-fade_len:] = np.linspace(1, 0, fade_len)

# 1. Synthesize 30s Interstellar Hans Zimmer Organ Theme Sketch
print("Generating Interstellar Hans Zimmer Organ Theme Sketch (30s)...")
notes = np.array([440.0, 659.25, 698.46, 659.25, 587.33, 523.25, 493.88, 440.0])
bass_notes = np.array([110.0, 87.31, 130.81, 98.00])

note_idx = (t / 1.0).astype(int) % len(notes)
freqs = notes[note_idx]

bass_idx = (t / 4.0).astype(int) % len(bass_notes)
b_freqs = bass_notes[bass_idx]

organ_lead = (
    0.50 * np.sin(2 * np.pi * freqs * t) +
    0.30 * np.sin(2 * np.pi * (freqs * 2) * t) +
    0.15 * np.sin(2 * np.pi * (freqs * 3) * t) +
    0.25 * np.sin(2 * np.pi * (freqs * 0.5) * t)
)

organ_bass = (
    0.40 * np.sin(2 * np.pi * b_freqs * t) +
    0.25 * np.sin(2 * np.pi * (b_freqs * 2) * t) +
    0.15 * np.sin(2 * np.pi * (b_freqs * 0.5) * t)
)

tick_phase = t % 1.0
tick = 0.05 * np.exp(-100 * tick_phase) * np.sin(2 * np.pi * 3000 * t)
swell = 0.6 + 0.3 * np.sin(2 * np.pi * 0.1 * t)

audio_interstellar = (organ_lead * 0.5 + organ_bass * 0.5 + tick) * swell * fade
write_wav("colonne_sonore/Interstellar_Hans_Zimmer_Style_30s.wav", audio_interstellar, sr)
print("Saved colonne_sonore/Interstellar_Hans_Zimmer_Style_30s.wav")

# 2. Synthesize 30s Moonlight Sonata Piano Sketch
print("Generating Moonlight Sonata Piano Sketch (30s)...")
arpeggio_freqs = np.array([138.59, 207.65, 277.18, 207.65])
triplet_dur = 0.4
step = (t / triplet_dur).astype(int) % len(arpeggio_freqs)
f_moon = arpeggio_freqs[step]

note_t = t % triplet_dur
env_moon = np.exp(-4.0 * note_t)

tone_moon = (
    0.60 * np.sin(2 * np.pi * f_moon * t) +
    0.25 * np.sin(2 * np.pi * 2 * f_moon * t) +
    0.10 * np.sin(2 * np.pi * 3 * f_moon * t)
)
audio_moon = tone_moon * env_moon * 0.7 * fade
write_wav("colonne_sonore/Beethoven_Moonlight_Sonata_30s.wav", audio_moon, sr)
print("Saved colonne_sonore/Beethoven_Moonlight_Sonata_30s.wav")

# 3. Synthesize 30s Beethoven 5th Symphony Motif Sketch
print("Generating Beethoven 5th Symphony Motif Sketch (30s)...")
audio_5th = np.zeros(N)
motif_seq = [
    (392.0, 0.2), (392.0, 0.2), (392.0, 0.2), (311.13, 0.8), (0.0, 0.3),
    (349.23, 0.2), (349.23, 0.2), (349.23, 0.2), (293.66, 0.8), (0.0, 0.5)
]
cur_t = 0.0
events = []
while cur_t < dur:
    for freq, d in motif_seq:
        events.append((cur_t, cur_t + d, freq))
        cur_t += d + 0.05
        if cur_t >= dur:
            break

for start_t, end_t, freq in events:
    if freq == 0.0:
        continue
    start_idx = int(start_t * sr)
    end_idx = min(N, int(end_t * sr))
    note_t = t[start_idx:end_idx] - start_t
    
    env = np.ones_like(note_t)
    rampin = int(sr * 0.02)
    rampout = int(sr * 0.05)
    if len(env) > rampin:
        env[:rampin] = np.linspace(0, 1, rampin)
    if len(env) > rampout:
        env[-rampout:] = np.linspace(1, 0, rampout)

    brass = (
        0.50 * np.sin(2 * np.pi * freq * note_t) +
        0.30 * np.sin(2 * np.pi * 2 * freq * note_t) +
        0.15 * np.sin(2 * np.pi * 3 * freq * note_t) +
        0.10 * np.sin(2 * np.pi * 4 * freq * note_t)
    )
    audio_5th[start_idx:end_idx] += brass * env * 0.6

audio_5th = audio_5th * fade
write_wav("colonne_sonore/Beethoven_5th_Symphony_30s.wav", audio_5th, sr)
print("Saved colonne_sonore/Beethoven_5th_Symphony_30s.wav")

