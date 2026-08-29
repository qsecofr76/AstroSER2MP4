import os
import subprocess
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import numpy as np
from PIL import Image
import imageio_ffmpeg
from ser_parser import SERParser, open_ser_or_video_file
from image_utils import apply_denoise, apply_hsl_colorization, apply_logo_overlay, load_title_image, embed_audio_into_video

class FFmpegVideoWriter:
    """
    Video writer using FFmpeg with native libx264 (H.264 / yuv420p) via subprocess pipe.
    Eliminates OpenCV OpenH264 DLL missing errors and provides pristine compression & compatibility.
    Falls back gracefully to OpenCV VideoWriter if FFmpeg is unavailable.
    """
    def __init__(self, output_path: str, width: int, height: int, fps: float, quality: int = 95):
        self.output_path = output_path
        # libx264 yuv420p requires even width and height
        self.enc_w = width if (width % 2 == 0) else (width - 1)
        self.enc_h = height if (height % 2 == 0) else (height - 1)
        self.fps = fps
        self.quality = quality
        self.process = None
        self._cv2_writer = None
        self.codec_name = ""

        # Map quality (1-100) to CRF (36 to 12). Default 95 quality -> CRF 13-14 (near-visually lossless)
        crf = int(np.clip(round(36 - (self.quality / 100.0) * 24), 12, 36))

        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg_exe and os.path.exists(ffmpeg_exe):
                cmd = [
                    ffmpeg_exe, "-y",
                    "-f", "rawvideo",
                    "-vcodec", "rawvideo",
                    "-s", f"{self.enc_w}x{self.enc_h}",
                    "-pix_fmt", "bgr24",
                    "-r", str(fps),
                    "-i", "-",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-crf", str(crf),
                    "-preset", "medium",
                    "-g", "1",
                    "-bf", "0",
                    "-tune", "fastdecode",
                    "-movflags", "+faststart",
                    output_path
                ]
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
                self.codec_name = f"H.264 (FFmpeg libx264, CRF {crf})"
        except Exception:
            self.process = None

        if self.process is None:
            # Fallback to OpenCV VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._cv2_writer = cv2.VideoWriter(output_path, fourcc, fps, (self.enc_w, self.enc_h))
            if not self._cv2_writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                self._cv2_writer = cv2.VideoWriter(output_path, fourcc, fps, (self.enc_w, self.enc_h))
                self.codec_name = "Motion-JPEG (OpenCV MJPG)"
            else:
                self.codec_name = "MPEG-4 (OpenCV mp4v)"

    def is_opened(self) -> bool:
        if self.process is not None:
            return self.process.poll() is None
        if self._cv2_writer is not None:
            return self._cv2_writer.isOpened()
        return False

    def write(self, frame_bgr: np.ndarray):
        if frame_bgr.shape[1] != self.enc_w or frame_bgr.shape[0] != self.enc_h:
            frame_bgr = cv2.resize(frame_bgr, (self.enc_w, self.enc_h), interpolation=cv2.INTER_AREA)

        if self.process is not None:
            if self.process.poll() is not None:
                _, stderr = self.process.communicate()
                err_msg = stderr.decode('utf-8', errors='ignore') if stderr else 'Processo FFmpeg terminato inaspettatamente.'
                raise RuntimeError(f"Errore codifica video FFmpeg: {err_msg}")
            self.process.stdin.write(frame_bgr.tobytes())
        elif self._cv2_writer is not None:
            self._cv2_writer.write(frame_bgr)

    def release(self):
        if self.process is not None:
            try:
                if self.process.stdin:
                    try:
                        self.process.stdin.close()
                    except Exception:
                        pass
                # Drain buffers and wait cleanly for moov atom and index finalization
                stdout, stderr = self.process.communicate(timeout=30)
                if self.process.returncode != 0:
                    err_msg = stderr.decode('utf-8', errors='ignore') if stderr else f"Exit code {self.process.returncode}"
                    print(f"FFmpeg exit status: {err_msg}")
            except Exception as e:
                print(f"Error during FFmpeg release: {e}")
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        if self._cv2_writer is not None:
            self._cv2_writer.release()
            self._cv2_writer = None

class ConverterWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)

    def __init__(self, ser_path: str, mp4_path: str, output_fps: float,
                 auto_stretch: bool = False, auto_wb: bool = False, 
                 brightness: int = 0, gamma: float = 1.0,
                 color_mode_override: str = "AUTO",
                 debayer_algorithm: str = "EA",
                 quality: int = 95,
                 start_frame: int = 1,
                 end_frame: Optional[int] = None,
                 denoise_enabled: bool = False,
                 denoise_method: str = "Bilateral Edge-Aware (Consigliato)",
                 denoise_strength: int = 7,
                 hsl_enabled: bool = False,
                 hsl_preset: str = "Nessuno (Originale)",
                 hsl_hue: int = 0,
                 hsl_saturation: int = 100,
                 hsl_luminance: int = 0,
                 logo_enabled: bool = False,
                 logo_path: Optional[str] = None,
                 logo_position: str = "In Basso a Destra",
                 logo_scale: int = 15,
                 logo_opacity: int = 100,
                 intro_enabled: bool = False,
                 intro_path: Optional[str] = None,
                 intro_duration: float = 2.0,
                 outro_enabled: bool = False,
                 outro_path: Optional[str] = None,
                 outro_duration: float = 2.0,
                 audio_enabled: bool = False,
                 audio_path: Optional[str] = None,
                 audio_loop: bool = True):
        super().__init__()
        self.ser_path = ser_path
        self.mp4_path = mp4_path
        self.output_fps = output_fps
        self.auto_stretch = auto_stretch
        self.auto_wb = auto_wb
        self.brightness = brightness
        self.gamma = gamma
        self.color_mode_override = color_mode_override
        self.debayer_algorithm = debayer_algorithm
        self.quality = quality
        
        self.start_frame = start_frame
        self.end_frame = end_frame
        
        self.denoise_enabled = denoise_enabled
        self.denoise_method = denoise_method
        self.denoise_strength = denoise_strength

        self.hsl_enabled = hsl_enabled
        self.hsl_preset = hsl_preset
        self.hsl_hue = hsl_hue
        self.hsl_saturation = hsl_saturation
        self.hsl_luminance = hsl_luminance

        self.logo_enabled = logo_enabled
        self.logo_path = logo_path
        self.logo_position = logo_position
        self.logo_scale = logo_scale
        self.logo_opacity = logo_opacity

        self.intro_enabled = intro_enabled
        self.intro_path = intro_path
        self.intro_duration = intro_duration
        self.outro_enabled = outro_enabled
        self.outro_path = outro_path
        self.outro_duration = outro_duration

        self.audio_enabled = audio_enabled
        self.audio_path = audio_path
        self.audio_loop = audio_loop

        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        parser = None
        writer = None
        try:
            self.status_changed.emit("Apertura del file sorgente in corso...")
            parser = open_ser_or_video_file(self.ser_path)
            header = parser.header

            total_ser_frames = header.frame_count

            start_idx = max(0, self.start_frame - 1)
            if self.end_frame and self.end_frame > 0:
                end_idx = min(total_ser_frames - 1, self.end_frame - 1)
            else:
                end_idx = total_ser_frames - 1

            if start_idx > end_idx:
                start_idx, end_idx = 0, total_ser_frames - 1

            num_ser_selected = end_idx - start_idx + 1

            # Fetch sample frame to get exact frame dimensions for VideoWriter
            sample_frame = parser.get_frame(start_idx, auto_stretch=self.auto_stretch)
            h, w = sample_frame.shape[0], sample_frame.shape[1]

            # Intro and Outro setup
            num_intro_frames = int(round(self.intro_duration * self.output_fps)) if (self.intro_enabled and self.intro_path) else 0
            num_outro_frames = int(round(self.outro_duration * self.output_fps)) if (self.outro_enabled and self.outro_path) else 0

            total_output_frames = num_intro_frames + num_ser_selected + num_outro_frames

            # Load Intro/Outro images if enabled
            intro_img = None
            if num_intro_frames > 0:
                self.status_changed.emit("Caricamento scheda di titolo iniziale (Intro)...")
                intro_img = load_title_image(self.intro_path, (w, h))

            outro_img = None
            if num_outro_frames > 0:
                self.status_changed.emit("Caricamento scheda di titolo finale (Outro)...")
                outro_img = load_title_image(self.outro_path, (w, h))

            is_gif = self.mp4_path.lower().endswith('.gif')

            if is_gif:
                self.status_changed.emit(f"Preparazione GIF: {w}x{h}, {total_output_frames} fotogrammi totali...")
                gif_frames = []
            else:
                self.status_changed.emit(f"Preparazione video MP4: {w}x{h}, {total_output_frames} fotogrammi...")
                writer = FFmpegVideoWriter(
                    output_path=self.mp4_path,
                    width=w,
                    height=h,
                    fps=self.output_fps,
                    quality=self.quality
                )
                if not writer.is_opened():
                    raise RuntimeError("Impossibile inizializzare il writer video MP4.")

                chosen_codec_name = writer.codec_name
                self.status_changed.emit(f"Codificatore selezionato: {chosen_codec_name}. Avvio conversione...")

            current_processed_count = 0

            # 1. Render Intro frames
            if num_intro_frames > 0 and intro_img is not None:
                self.status_changed.emit(f"Scrittura titolo iniziale (Intro: {self.intro_duration:.1f}s)...")
                for _ in range(num_intro_frames):
                    if self._is_cancelled:
                        raise InterruptedError("Conversione annullata dall'utente.")
                    if is_gif:
                        rgb_intro = cv2.cvtColor(intro_img, cv2.COLOR_BGR2RGB)
                        gif_frames.append(Image.fromarray(rgb_intro))
                    else:
                        writer.write(intro_img)
                    current_processed_count += 1
                    pct = int((current_processed_count / total_output_frames) * 100)
                    self.progress_changed.emit(pct)

            # 2. Render Main video frames (within trim range)
            for idx in range(start_idx, end_idx + 1):
                if self._is_cancelled:
                    raise InterruptedError("Conversione annullata dall'utente.")

                frame = parser.get_frame(
                    frame_idx=idx,
                    auto_stretch=self.auto_stretch,
                    auto_wb=self.auto_wb,
                    brightness=self.brightness,
                    gamma=self.gamma,
                    color_mode_override=self.color_mode_override,
                    debayer_algorithm=self.debayer_algorithm
                )

                # Ensure frame size matches writer exactly
                if frame.shape[1] != w or frame.shape[0] != h:
                    frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)

                # Post-processing: Noise Reduction (Denoise)
                if self.denoise_enabled:
                    frame = apply_denoise(
                        frame,
                        enabled=True,
                        method=self.denoise_method,
                        strength=self.denoise_strength
                    )

                # Post-processing: HSL Colorization
                if self.hsl_enabled:
                    frame = apply_hsl_colorization(
                        frame,
                        enabled=True,
                        preset=self.hsl_preset,
                        hue=self.hsl_hue,
                        saturation=self.hsl_saturation,
                        luminance=self.hsl_luminance
                    )

                # Post-processing: Logo Overlay
                if self.logo_enabled and self.logo_path:
                    frame = apply_logo_overlay(
                        frame,
                        logo_path=self.logo_path,
                        position=self.logo_position,
                        scale_pct=self.logo_scale,
                        opacity_pct=self.logo_opacity
                    )

                if is_gif:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    gif_frames.append(Image.fromarray(frame_rgb))
                else:
                    writer.write(frame)

                current_processed_count += 1
                pct = int((current_processed_count / total_output_frames) * 100)
                self.progress_changed.emit(pct)
                if current_processed_count % 10 == 0 or current_processed_count == total_output_frames:
                    self.status_changed.emit(f"Elaborazione in corso: {current_processed_count} / {total_output_frames} ({pct}%)")

            # 3. Render Outro frames
            if num_outro_frames > 0 and outro_img is not None:
                self.status_changed.emit(f"Scrittura titolo finale (Outro: {self.outro_duration:.1f}s)...")
                for _ in range(num_outro_frames):
                    if self._is_cancelled:
                        raise InterruptedError("Conversione annullata dall'utente.")
                    if is_gif:
                        rgb_outro = cv2.cvtColor(outro_img, cv2.COLOR_BGR2RGB)
                        gif_frames.append(Image.fromarray(rgb_outro))
                    else:
                        writer.write(outro_img)
                    current_processed_count += 1
                    pct = int((current_processed_count / total_output_frames) * 100)
                    self.progress_changed.emit(pct)

            # Finalize output
            if is_gif:
                self.status_changed.emit("Scrittura del file animato GIF in corso (ottimizzazione dei colori)...")
                duration_ms = int(1000.0 / self.output_fps) if self.output_fps > 0 else 33
                gif_frames[0].save(
                    self.mp4_path,
                    save_all=True,
                    append_images=gif_frames[1:],
                    optimize=True,
                    duration=duration_ms,
                    loop=0
                )
                self.conversion_finished.emit(True, "Esportazione GIF completata con successo!")
            else:
                writer.release()
                writer = None

                # Audio soundtrack embedding step
                if self.audio_enabled and self.audio_path and os.path.exists(self.audio_path):
                    self.status_changed.emit("Incorporamento della colonna sonora audio nell'MP4 in corso...")
                    mux_ok = embed_audio_into_video(
                        video_path=self.mp4_path,
                        audio_path=self.audio_path,
                        output_path=self.mp4_path,
                        loop=self.audio_loop
                    )
                    if mux_ok:
                        self.conversion_finished.emit(True, "Conversione MP4 completata con successo con colonna sonora audio inclusa!")
                    else:
                        self.conversion_finished.emit(True, f"Conversione MP4 completata col codec {chosen_codec_name} (senza audio).")
                else:
                    self.conversion_finished.emit(True, f"Conversione completata con successo usando il codec {chosen_codec_name}!")

            parser.close()
            parser = None

        except InterruptedError as ie:
            self.conversion_finished.emit(False, str(ie))
        except Exception as e:
            self.conversion_finished.emit(False, f"Errore durante la conversione: {str(e)}")
        finally:
            if writer:
                writer.release()
            if parser:
                parser.close()
            if self._is_cancelled and os.path.exists(self.mp4_path):
                try:
                    os.remove(self.mp4_path)
                except Exception:
                    pass
