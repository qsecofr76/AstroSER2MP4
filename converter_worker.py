import os
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import numpy as np
from PIL import Image
from ser_parser import SERParser

class ConverterWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    conversion_finished = pyqtSignal(bool, str)

    def __init__(self, ser_path: str, mp4_path: str, output_fps: float,
                 auto_stretch: bool = False, auto_wb: bool = False, 
                 brightness: int = 0, gamma: float = 1.0,
                 color_mode_override: str = "AUTO",
                 debayer_algorithm: str = "EA",
                 quality: int = 95):
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
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        parser = None
        writer = None
        try:
            self.status_changed.emit("Apertura del file SER in corso...")
            parser = SERParser(self.ser_path)
            header = parser.header
            
            w = header.image_width
            h = header.image_height
            total_frames = header.frame_count

            # Check if output is GIF or MP4
            is_gif = self.mp4_path.lower().endswith('.gif')

            if is_gif:
                self.status_changed.emit(f"Preparazione animazione GIF: {w}x{h}, {total_frames} fotogrammi...")
                gif_frames = []
            else:
                self.status_changed.emit(f"Preparazione video MP4: {w}x{h}, {total_frames} fotogrammi...")

                codecs_to_try = [
                    ('avc1', "H.264 (avc1)"),
                    ('H264', "H.264 (H264)"),
                    ('mp4v', "MPEG-4 (mp4v)")
                ]

                writer = None
                chosen_codec_name = ""

                for fourcc_str, codec_desc in codecs_to_try:
                    if self._is_cancelled:
                        raise InterruptedError("Conversione annullata dall'utente.")
                    
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
                    
                    # Try with quality parameter first (unsupported by some backends but great if works)
                    try:
                        test_writer = cv2.VideoWriter(
                            self.mp4_path, 
                            fourcc, 
                            self.output_fps, 
                            (w, h), 
                            params=[cv2.VIDEOWRITER_PROP_QUALITY, self.quality]
                        )
                    except Exception:
                        test_writer = cv2.VideoWriter(self.mp4_path, fourcc, self.output_fps, (w, h))

                    if not test_writer.isOpened():
                        # Fallback to standard
                        test_writer.release()
                        test_writer = cv2.VideoWriter(self.mp4_path, fourcc, self.output_fps, (w, h))

                    if test_writer.isOpened():
                        writer = test_writer
                        chosen_codec_name = codec_desc
                        break
                    else:
                        test_writer.release()
                        if os.path.exists(self.mp4_path):
                            try:
                                os.remove(self.mp4_path)
                            except Exception:
                                pass

                if writer is None:
                    raise RuntimeError("Impossibile inizializzare alcun codec video compatibile (avc1, H264, mp4v) su questa macchina.")

                self.status_changed.emit(f"Codificatore selezionato: {chosen_codec_name} (Qualità: {self.quality}%). Avvio conversione...")

            # Frame conversion loop
            for idx in range(total_frames):
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

                if is_gif:
                    # Convert BGR (OpenCV default) to RGB for PIL
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)
                    gif_frames.append(pil_img)
                else:
                    writer.write(frame)

                progress_pct = int(((idx + 1) / total_frames) * 100)
                self.progress_changed.emit(progress_pct)
                if idx % 10 == 0 or idx == total_frames - 1:
                    self.status_changed.emit(f"Elaborazione in corso: fotogramma {idx + 1} di {total_frames} ({progress_pct}%)")

            # Finalize output
            if is_gif:
                self.status_changed.emit("Scrittura del file animato GIF in corso (ottimizzazione dei colori)...")
                duration_ms = int(1000.0 / self.output_fps) if self.output_fps > 0 else 33
                
                # Save as animated GIF using PIL
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
