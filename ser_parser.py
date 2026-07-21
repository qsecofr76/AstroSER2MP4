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

        self._channels = 3 if color_id >= 100 else 1
        self._bytes_per_pixel = 1 if pixel_depth <= 8 else 2
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
        if color_mode_override != "AUTO":
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

        # Determine actual file channels from buffer size
        raw_elements = len(img)
        actual_channels = 3 if raw_elements == (w * h * 3) else 1

        if actual_channels == 3:
            # File actually contains 3-channel RGB/BGR data
            if color_mode_override == "RGB_PLANAR":
                planar_img = img.reshape((3, h, w))
                if cid == 100:
                    bgr_raw = cv2.merge([planar_img[2], planar_img[1], planar_img[0]])
                else:
                    bgr_raw = cv2.merge([planar_img[0], planar_img[1], planar_img[2]])
            elif color_mode_override in ["RGGB", "BGGR", "GRBG", "GBRG", "MONO"]:
                interleaved_img = img.reshape((h, w, 3))
                if self.header.color_id == 100:
                    bgr_temp = cv2.cvtColor(interleaved_img, cv2.COLOR_RGB2BGR)
                else:
                    bgr_temp = interleaved_img
                gray = cv2.cvtColor(bgr_temp, cv2.COLOR_BGR2GRAY)
                
                bayer_codes = {
                    1: cv2.COLOR_BayerRG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerRG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerRG2BGR),
                    2: cv2.COLOR_BayerGR2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGR2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGR2BGR),
                    3: cv2.COLOR_BayerGB2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGB2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGB2BGR),
                    4: cv2.COLOR_BayerBG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerBG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerBG2BGR),
                }
                if cid in bayer_codes:
                    bgr_raw = cv2.cvtColor(gray, bayer_codes[cid])
                else:
                    bgr_raw = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                interleaved_img = img.reshape((h, w, 3))
                if cid == 100:
                    bgr_raw = cv2.cvtColor(interleaved_img, cv2.COLOR_RGB2BGR)
                else:
                    bgr_raw = interleaved_img
        else:
            # File actually contains 1-channel raw Bayer/Mono data (w * h)
            gray = img.reshape((h, w))
            bayer_codes = {
                1: cv2.COLOR_BayerRG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerRG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerRG2BGR),
                2: cv2.COLOR_BayerGR2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGR2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGR2BGR),
                3: cv2.COLOR_BayerGB2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerGB2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerGB2BGR),
                4: cv2.COLOR_BayerBG2BGR_EA if debayer_algorithm == "EA" else (cv2.COLOR_BayerBG2BGR_VNG if debayer_algorithm == "VNG" else cv2.COLOR_BayerBG2BGR),
            }

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
