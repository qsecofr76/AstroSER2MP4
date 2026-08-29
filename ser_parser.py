import os
import struct
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import numpy as np
import cv2

@dataclass
class SERHeader:
    file_id: str
    lu_id: int
    color_id: int
    little_endian: int  # 1 = little endian, 0 = big endian
    image_width: int
    image_height: int
    pixel_depth: int    # bits per pixel (e.g. 8, 12, 14, 16)
    frame_count: int
    observer: str
    instrument: str
    telescope: str
    datetime_utc: Optional[datetime]
    datetime_local: Optional[datetime]

class SERParser:
    HEADER_SIZE = 178
    FILE_ID_MAGIC = b"LUCAM-RECORDER"

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.header: Optional[SERHeader] = None
        self._file_handle = None
        self._frame_size_bytes = 0
        self._bytes_per_pixel = 0
        self._channels = 0
        self._file_size = 0
        self._has_timestamps = False

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File non trovato: {file_path}")
        
        self._file_size = os.path.getsize(file_path)
        self._file_handle = open(file_path, "rb")
        self.parse_header()

    def parse_header(self) -> SERHeader:
        self._file_handle.seek(0)
        header_bytes = self._file_handle.read(self.HEADER_SIZE)
        if len(header_bytes) < self.HEADER_SIZE:
            raise ValueError("File troppo piccolo per contenere l'header SER di 178 byte.")

        fmt = "<14sIIIIIII40s40s40sQQ"
        unpacked = struct.unpack(fmt, header_bytes)

        file_id = unpacked[0].decode("ascii", errors="ignore").strip()
        if not file_id.startswith("LUCAM-RECORDER"):
            raise ValueError(f"Firma file non valida. Atteso 'LUCAM-RECORDER', trovato: '{file_id}'")

        lu_id = unpacked[1]
        color_id = unpacked[2]
        little_endian = unpacked[3]
        image_width = unpacked[4]
        image_height = unpacked[5]
        pixel_depth = unpacked[6]
        frame_count = unpacked[7]

        observer = unpacked[8].replace(b"\x00", b"").decode("utf-8", errors="ignore").strip()
        instrument = unpacked[9].replace(b"\x00", b"").decode("utf-8", errors="ignore").strip()
        telescope = unpacked[10].replace(b"\x00", b"").decode("utf-8", errors="ignore").strip()

        datetime_utc = self._ticks_to_datetime(unpacked[11])
        datetime_local = self._ticks_to_datetime(unpacked[12])

        self.header = SERHeader(
            file_id=file_id,
            lu_id=lu_id,
            color_id=color_id,
            little_endian=little_endian,
            image_width=image_width,
            image_height=image_height,
            pixel_depth=pixel_depth,
            frame_count=frame_count,
            observer=observer,
            instrument=instrument,
            telescope=telescope,
            datetime_utc=datetime_utc,
            datetime_local=datetime_local
        )

        self._bytes_per_pixel = 1 if pixel_depth <= 8 else 2
        single_frame_bytes_1chan = image_width * image_height * self._bytes_per_pixel
        single_frame_bytes_3chan = single_frame_bytes_1chan * 3

        if color_id >= 100:
            self._channels = 3
        else:
            self._channels = 1
            if frame_count > 0:
                payload_size = self._file_size - self.HEADER_SIZE
                min_3chan_bytes = single_frame_bytes_3chan * frame_count
                if payload_size >= min_3chan_bytes:
                    self._channels = 3

        self._frame_size_bytes = image_width * image_height * self._bytes_per_pixel * self._channels

        expected_size_with_timestamps = self.HEADER_SIZE + frame_count * self._frame_size_bytes + frame_count * 8
        if self._file_size >= expected_size_with_timestamps:
            self._has_timestamps = True

        return self.header

    def _ticks_to_datetime(self, ticks: int) -> Optional[datetime]:
        if ticks == 0:
            return None
        try:
            return datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)
        except Exception:
            return None

    def read_frame_raw(self, frame_idx: int) -> bytes:
        if not self.header:
            raise ValueError("Header non ancora letto.")
        if frame_idx < 0 or frame_idx >= self.header.frame_count:
            raise IndexError(f"Indice frame {frame_idx} fuori dai limiti (0 - {self.header.frame_count - 1}).")

        offset = self.HEADER_SIZE + frame_idx * self._frame_size_bytes
        self._file_handle.seek(offset)
        frame_bytes = self._file_handle.read(self._frame_size_bytes)
        if len(frame_bytes) < self._frame_size_bytes:
            raise IOError(f"Impossibile leggere il frame {frame_idx}: file troncato o corrotto.")
        return frame_bytes

    def get_frame(self, frame_idx: int, 
                  auto_stretch: bool = False, 
                  auto_wb: bool = False,
                  brightness: int = 0, 
                  gamma: float = 1.0,
                  color_mode_override: str = "AUTO",
                  debayer_algorithm: str = "EA") -> np.ndarray:
        
        raw_bytes = self.read_frame_raw(frame_idx)
        w = self.header.image_width
        h = self.header.image_height

        if self._bytes_per_pixel == 1:
            dtype = np.uint8
        else:
            dtype = np.dtype("<u2") if self.header.little_endian == 1 else np.dtype(">u2")

        img = np.frombuffer(raw_bytes, dtype=dtype)
        
        if self._bytes_per_pixel == 2:
            img = img.astype(np.uint16)

        cid = self.header.color_id
        if color_mode_override not in ["AUTO", "DISABLED", "NONE"]:
            mode_map = {
                "MONO": 0,
                "RGGB": 1,
                "GRBG": 2,
                "GBRG": 3,
                "BGGR": 4,
                "RGB": 100,
                "BGR": 101,
                "RGB_PLANAR": 100
            }
            cid = mode_map.get(color_mode_override, cid)
        elif color_mode_override in ["DISABLED", "NONE"] and cid < 100:
            cid = 100

        raw_elements = len(img)
        actual_channels = 3 if raw_elements == (w * h * 3) else 1

        disable_debayer = (
            actual_channels == 3 or 
            color_mode_override in ["DISABLED", "NONE", "RGB", "RGB_PLANAR", "BGR"] or
            cid >= 100
        )

        if actual_channels == 3:
            interleaved_img = img.reshape((h, w, 3))
            
            if color_mode_override == "RGB_PLANAR":
                planar_img = img.reshape((3, h, w))
                if cid == 100:
                    bgr_raw = cv2.merge([planar_img[2], planar_img[1], planar_img[0]])
                else:
                    bgr_raw = cv2.merge([planar_img[0], planar_img[1], planar_img[2]])
            elif color_mode_override == "MONO":
                if self.header.color_id == 100:
                    bgr_temp = cv2.cvtColor(interleaved_img, cv2.COLOR_RGB2BGR)
                else:
                    bgr_temp = interleaved_img
                gray = cv2.cvtColor(bgr_temp, cv2.COLOR_BGR2GRAY)
                bgr_raw = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                if cid == 100:
                    bgr_raw = cv2.cvtColor(interleaved_img, cv2.COLOR_RGB2BGR)
                elif cid == 101:
                    bgr_raw = interleaved_img
                else:
                    bgr_raw = cv2.cvtColor(interleaved_img, cv2.COLOR_RGB2BGR)
        else:
            gray = img.reshape((h, w))
            
            ea = debayer_algorithm == "EA"
            vng = debayer_algorithm == "VNG"
            code_rggb = cv2.COLOR_BayerRG2BGR_EA if ea else (cv2.COLOR_BayerRG2BGR_VNG if vng else cv2.COLOR_BayerRG2BGR)
            code_grbg = cv2.COLOR_BayerGR2BGR_EA if ea else (cv2.COLOR_BayerGR2BGR_VNG if vng else cv2.COLOR_BayerGR2BGR)
            code_gbrg = cv2.COLOR_BayerGB2BGR_EA if ea else (cv2.COLOR_BayerGB2BGR_VNG if vng else cv2.COLOR_BayerGB2BGR)
            code_bggr = cv2.COLOR_BayerBG2BGR_EA if ea else (cv2.COLOR_BayerBG2BGR_VNG if vng else cv2.COLOR_BayerBG2BGR)

            bayer_codes = {
                # Manual overrides (standard OpenCV names):
                1: code_rggb,
                2: code_grbg,
                3: code_gbrg,
                4: code_bggr,
                # SER Header IDs (astronomy sensor origin -> OpenCV mapping):
                8: code_bggr,  # SER ColorID 8 (Bayer RGGB in SER header)
                9: code_gbrg,  # SER ColorID 9 (Bayer GRBG in SER header)
                10: code_grbg, # SER ColorID 10 (Bayer GBRG in SER header)
                11: code_rggb, # SER ColorID 11 (Bayer BGGR in SER header)
            }

            if color_mode_override == "MONO":
                # If explicitly forced to Mono from a Bayer source, debayer first to eliminate Bayer grid artifacts
                active_cid = cid if cid in bayer_codes else 8
                bgr_deb = cv2.cvtColor(gray, bayer_codes[active_cid])
                gray_clean = cv2.cvtColor(bgr_deb, cv2.COLOR_BGR2GRAY)
                bgr_raw = cv2.cvtColor(gray_clean, cv2.COLOR_GRAY2BGR)
            elif cid == 0 or disable_debayer or color_mode_override in ["DISABLED", "NONE"]:
                bgr_raw = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                if cid in bayer_codes:
                    bgr_raw = cv2.cvtColor(gray, bayer_codes[cid])
                else:
                    bgr_raw = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Handle 16-bit to 8-bit scaling and Auto-Stretch
        if self._bytes_per_pixel == 2:
            if auto_stretch:
                p_min, p_max = np.percentile(bgr_raw, [0.1, 99.9])
                if p_max > p_min:
                    bgr_stretched = np.clip((bgr_raw.astype(np.float32) - p_min) * (255.0 / (p_max - p_min)), 0, 255)
                    bgr_8 = bgr_stretched.astype(np.uint8)
                else:
                    bgr_8 = (bgr_raw / 256.0).astype(np.uint8)
            else:
                max_val = np.max(bgr_raw)
                if max_val > 0 and max_val <= 4095:
                    bgr_8 = np.clip(bgr_raw.astype(np.float32) * (255.0 / 4095.0), 0, 255).astype(np.uint8)
                else:
                    bgr_8 = (bgr_raw / 256.0).astype(np.uint8)
        else:
            if auto_stretch:
                p_min, p_max = np.percentile(bgr_raw, [0.1, 99.9])
                if p_max > p_min:
                    bgr_stretched = np.clip((bgr_raw.astype(np.float32) - p_min) * (255.0 / (p_max - p_min)), 0, 255)
                    bgr_8 = bgr_stretched.astype(np.uint8)
                else:
                    bgr_8 = bgr_raw.copy()
            else:
                bgr_8 = bgr_raw.copy()

        # Apply Auto White Balance (Gray World algorithm)
        if auto_wb:
            bgr_float = bgr_8.astype(np.float32)
            mean_b = np.mean(bgr_float[:, :, 0])
            mean_g = np.mean(bgr_float[:, :, 1])
            mean_r = np.mean(bgr_float[:, :, 2])

            if mean_b > 0 and mean_r > 0 and mean_g > 0:
                kb = mean_g / mean_b
                kr = mean_g / mean_r
                bgr_float[:, :, 0] = np.clip(bgr_float[:, :, 0] * kb, 0, 255)
                bgr_float[:, :, 2] = np.clip(bgr_float[:, :, 2] * kr, 0, 255)
                bgr_8 = bgr_float.astype(np.uint8)

        # Apply Gamma Correction / Non-linear Stretch
        if gamma != 1.0 and gamma > 0:
            exponent = 1.0 / gamma
            table = np.array([((i / 255.0) ** exponent) * 255 for i in range(256)]).astype("uint8")
            bgr_8 = cv2.LUT(bgr_8, table)

        # Apply linear brightness adjustment
        if brightness != 0:
            bgr_8 = cv2.convertScaleAbs(bgr_8, alpha=1.0, beta=brightness)

        return np.ascontiguousarray(bgr_8)

    def get_frame_timestamp(self, frame_idx: int) -> Optional[datetime]:
        if not self._has_timestamps or not self.header:
            return None
        if frame_idx < 0 or frame_idx >= self.header.frame_count:
            return None
        
        offset = self.HEADER_SIZE + self.header.frame_count * self._frame_size_bytes + frame_idx * 8
        self._file_handle.seek(offset)
        timestamp_bytes = self._file_handle.read(8)
        if len(timestamp_bytes) < 8:
            return None
        ticks = struct.unpack("<Q", timestamp_bytes)[0]
        return self._ticks_to_datetime(ticks)

    def get_average_fps(self, default_fps: float = 30.0) -> float:
        if not self._has_timestamps or not self.header or self.header.frame_count < 2:
            return default_fps

        t_start = self.get_frame_timestamp(0)
        t_end = self.get_frame_timestamp(self.header.frame_count - 1)

        if t_start and t_end:
            duration_sec = (t_end - t_start).total_seconds()
            if duration_sec > 0:
                fps = (self.header.frame_count - 1) / duration_sec
                if 0.1 <= fps <= 1000:
                    return round(fps, 2)
        return default_fps

    def close(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __del__(self):
        self.close()

class VideoParser:
    """Parser for standard video files (.avi, .mp4, .mov, .mkv, etc.) using OpenCV VideoCapture."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File non trovato: {file_path}")

        self.cap = cv2.VideoCapture(file_path)
        if not self.cap.isOpened():
            raise ValueError(f"Impossibile aprire il file video: {file_path}")

        image_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        image_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            frame_count = 1

        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0
        self._fps = fps

        filename = os.path.basename(file_path)
        mtime = os.path.getmtime(file_path)
        dt_utc = datetime.fromtimestamp(mtime, tz=timezone.utc)
        ext = filename.split(".")[-1].upper()

        self.header = SERHeader(
            file_id=f"VIDEO-{ext}",
            lu_id=0,
            color_id=0,
            little_endian=1,
            image_width=image_width,
            image_height=image_height,
            pixel_depth=8,
            frame_count=frame_count,
            observer="-",
            instrument=f"Video Codec ({ext})",
            telescope="-",
            datetime_utc=dt_utc,
            datetime_local=dt_utc
        )
        self._channels = 1
        
        # Analyze first frame to automatically detect optimal Bayer pattern ID
        self._detected_bayer_id = 2  # Default to GRBG
        ret, first_frame = self.cap.read()
        if ret and first_frame is not None:
            if len(first_frame.shape) == 3:
                gray_sample = first_frame[:, :, 0]
            else:
                gray_sample = first_frame.squeeze()
            self._detected_bayer_id = self._detect_best_bayer_id(gray_sample)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _detect_best_bayer_id(self, gray_sample: np.ndarray) -> int:
        """Detects which Bayer pattern ID (1=RGGB, 2=GRBG, 3=GBRG, 4=BGGR) minimizes high-frequency Bayer grid variance."""
        h, w = gray_sample.shape[:2]
        crop_h, crop_w = min(120, h), min(120, w)
        patch = gray_sample[:crop_h, :crop_w]
        
        bayer_test_codes = {
            1: cv2.COLOR_BayerRG2BGR,
            2: cv2.COLOR_BayerGR2BGR,
            3: cv2.COLOR_BayerGB2BGR,
            4: cv2.COLOR_BayerBG2BGR,
        }
        
        variances = {}
        for cid, code in bayer_test_codes.items():
            deb = cv2.cvtColor(patch, code)
            g_clean = cv2.cvtColor(deb, cv2.COLOR_BGR2GRAY)
            variances[cid] = g_clean.std()
            
        return min(variances, key=variances.get)

    def get_average_fps(self, default_fps: float = 30.0) -> float:
        return self._fps if self._fps > 0 else default_fps

    def get_frame(self, frame_idx: int, 
                  auto_stretch: bool = False, 
                  auto_wb: bool = False,
                  brightness: int = 0, 
                  gamma: float = 1.0,
                  color_mode_override: str = "AUTO",
                  debayer_algorithm: str = "EA") -> np.ndarray:
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame_read = self.cap.read()
        if not ret or frame_read is None:
            w = self.header.image_width
            h = self.header.image_height
            frame_read = np.zeros((h, w, 3), dtype=np.uint8)

        # Determine if frame is raw Bayer / grayscale matrix
        if len(frame_read.shape) == 2:
            gray = frame_read
            is_grayscale_matrix = True
        elif len(frame_read.shape) == 3:
            b, g, r = frame_read[:, :, 0], frame_read[:, :, 1], frame_read[:, :, 2]
            mean_channel_diff = float(np.mean(np.abs(b.astype(np.float32) - g.astype(np.float32))))
            if mean_channel_diff < 5.0:
                gray = b
                is_grayscale_matrix = True
            else:
                gray = cv2.cvtColor(frame_read, cv2.COLOR_BGR2GRAY)
                is_grayscale_matrix = False
        else:
            gray = frame_read.squeeze()
            is_grayscale_matrix = True

        mode_map = {
            "RGGB": 1,
            "GRBG": 2,
            "GBRG": 3,
            "BGGR": 4,
            "MONO": 0,
            "RGB": 100,
            "BGR": 101,
        }

        bayer_pattern_id = mode_map.get(color_mode_override, self._detected_bayer_id)
        if bayer_pattern_id not in [1, 2, 3, 4]:
            bayer_pattern_id = self._detected_bayer_id

        bayer_codes = {
            1: cv2.COLOR_BayerRG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerRG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerRG2BGR),
            2: cv2.COLOR_BayerGR2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGR2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGR2BGR),
            3: cv2.COLOR_BayerGB2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGB2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGB2BGR),
            4: cv2.COLOR_BayerBG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerBG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerBG2BGR),
        }

        if is_grayscale_matrix:
            if color_mode_override in ["MONO", "AUTO"]:
                # Clean debayer-then-mono pipeline using the auto-detected optimal Bayer phase (GRBG/GBRG)
                bgr_deb = cv2.cvtColor(gray, bayer_codes[bayer_pattern_id])
                gray_clean = cv2.cvtColor(bgr_deb, cv2.COLOR_BGR2GRAY)
                bgr_raw = cv2.cvtColor(gray_clean, cv2.COLOR_GRAY2BGR)
            elif color_mode_override in ["DISABLED", "NONE", "RGB", "BGR"]:
                bgr_raw = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                bgr_raw = cv2.cvtColor(gray, bayer_codes[bayer_pattern_id])
        else:
            if color_mode_override == "MONO":
                gray_tmp = cv2.cvtColor(frame_read, cv2.COLOR_BGR2GRAY)
                bgr_raw = cv2.cvtColor(gray_tmp, cv2.COLOR_GRAY2BGR)
            else:
                bgr_raw = frame_read

        bgr_8 = bgr_raw

        if auto_stretch:
            p_min, p_max = np.percentile(bgr_8, [0.1, 99.9])
            if p_max > p_min:
                bgr_stretched = np.clip((bgr_8.astype(np.float32) - p_min) * (255.0 / (p_max - p_min)), 0, 255)
                bgr_8 = bgr_stretched.astype(np.uint8)

        if auto_wb:
            bgr_float = bgr_8.astype(np.float32)
            mean_b = np.mean(bgr_float[:, :, 0])
            mean_g = np.mean(bgr_float[:, :, 1])
            mean_r = np.mean(bgr_float[:, :, 2])
            if mean_b > 0 and mean_r > 0 and mean_g > 0:
                kb = mean_g / mean_b
                kr = mean_g / mean_r
                bgr_float[:, :, 0] = np.clip(bgr_float[:, :, 0] * kb, 0, 255)
                bgr_float[:, :, 2] = np.clip(bgr_float[:, :, 2] * kr, 0, 255)
                bgr_8 = bgr_float.astype(np.uint8)

        if gamma != 1.0 and gamma > 0:
            exponent = 1.0 / gamma
            table = np.array([((i / 255.0) ** exponent) * 255 for i in range(256)]).astype("uint8")
            bgr_8 = cv2.LUT(bgr_8, table)

        if brightness != 0:
            bgr_8 = cv2.convertScaleAbs(bgr_8, alpha=1.0, beta=brightness)

        return np.ascontiguousarray(bgr_8)

    def get_frame_timestamp(self, frame_idx: int) -> Optional[datetime]:
        if not self.header or self.header.datetime_utc is None:
            return None
        offset_sec = frame_idx / self._fps if self._fps > 0 else 0
        return self.header.datetime_utc + timedelta(seconds=offset_sec)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def __del__(self):
        self.close()

def open_ser_or_video_file(file_path: str):
    """Factory function to open either a .SER file or a standard video (.avi, .mp4, etc.)"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".ser":
        return SERParser(file_path)
    elif ext in [".avi", ".mp4", ".mov", ".mkv", ".webm", ".m4v"]:
        return VideoParser(file_path)
    else:
        try:
            return SERParser(file_path)
        except Exception:
            return VideoParser(file_path)
