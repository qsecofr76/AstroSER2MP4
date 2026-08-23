import os
import cv2
import numpy as np
from typing import Optional, Tuple

def load_fits_image(file_path: str, target_shape: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """
    Loads a .fit / .fits astronomical image using astropy, normalizes it to uint8 BGR,
    and optionally resizes it to target_shape (width, height).
    """
    from astropy.io import fits
    with fits.open(file_path) as hdul:
        data = None
        for hdu in hdul:
            if hdu.data is not None:
                data = hdu.data
                break
        if data is None:
            raise ValueError("Nessun dato immagine valido trovato nel file FITS.")

    data = np.squeeze(data).astype(np.float32)

    if data.ndim == 3:
        if data.shape[0] in [1, 3, 4]:
            data = np.transpose(data, (1, 2, 0))
        if data.shape[2] == 1:
            data = data[:, :, 0]

    d_min, d_max = np.percentile(data, [0.1, 99.9])
    if d_max > d_min:
        data_norm = np.clip((data - d_min) * (255.0 / (d_max - d_min)), 0, 255).astype(np.uint8)
    else:
        data_norm = np.clip(data, 0, 255).astype(np.uint8)

    if data_norm.ndim == 2:
        bgr = cv2.cvtColor(data_norm, cv2.COLOR_GRAY2BGR)
    elif data_norm.shape[2] == 3:
        bgr = cv2.cvtColor(data_norm, cv2.COLOR_RGB2BGR)
    else:
        bgr = cv2.cvtColor(data_norm[:, :, :3], cv2.COLOR_RGB2BGR)

    if target_shape is not None and (bgr.shape[1] != target_shape[0] or bgr.shape[0] != target_shape[1]):
        bgr = cv2.resize(bgr, (target_shape[0], target_shape[1]), interpolation=cv2.INTER_AREA)

    return bgr

def load_title_image(file_path: str, target_shape: Tuple[int, int]) -> np.ndarray:
    """
    Loads an intro/outro title card (supports PNG, JPG, BMP, TIF, FIT, FITS)
    and resizes it to target_shape (width, height).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File immagine non trovato: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".fit", ".fits"]:
        return load_fits_image(file_path, target_shape)

    img = cv2.imread(file_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Impossibile caricare l'immagine: {file_path}")

    if img.shape[1] != target_shape[0] or img.shape[0] != target_shape[1]:
        img = cv2.resize(img, (target_shape[0], target_shape[1]), interpolation=cv2.INTER_AREA)

    return img

def create_solar_lut(hue_deg: float, sat_pct: float, lum_offset: int, highlight_shift: float = 0.0) -> np.ndarray:
    """
    Generates a 256-entry BGR lookup table for solar colorization.
    """
    hsv = np.zeros((1, 256, 3), dtype=np.uint8)
    sat_val = int(np.clip(255.0 * (sat_pct / 100.0), 0, 255))
    
    for i in range(256):
        if i == 0:
            hsv[0, i] = [0, 0, 0]
            continue
        
        t = i / 255.0
        current_hue = (hue_deg + highlight_shift * (t ** 2)) % 360.0
        h_cv = int((current_hue / 2.0) % 180)
        v_cv = int(np.clip(i + lum_offset, 0, 255))
        
        hsv[0, i] = [h_cv, sat_val, v_cv]
        
    bgr_lut = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    bgr_lut[0, 0] = [0, 0, 0]
    return bgr_lut

def apply_hsl_colorization(
    bgr_img: np.ndarray,
    enabled: bool = False,
    preset: str = "Nessuno (Originale)",
    hue: int = 0,
    saturation: int = 100,
    luminance: int = 0
) -> np.ndarray:
    """
    Applies solar red/yellow/orange colorization, colormap presets, or custom HSL adjustments using LUTs.
    Eliminates outer halo / black space inversion artifacts completely.
    """
    if not enabled or preset == "Nessuno (Originale)":
        return bgr_img

    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)

    if preset in ["Inferno (Falso Colore)", "Inferno"]:
        return cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    elif preset in ["Plasma (Falso Colore)", "Plasma"]:
        return cv2.applyColorMap(gray, cv2.COLORMAP_PLASMA)

    if preset in ["Rosso Solare H-alpha (656nm - Rubino)", "H-alpha"]:
        lut = create_solar_lut(hue_deg=355.0, sat_pct=100.0, lum_offset=0, highlight_shift=20.0)
    elif preset in ["Arancione Solare (Prominenze / Luce Solare)", "Arancione Solare"]:
        lut = create_solar_lut(hue_deg=20.0, sat_pct=100.0, lum_offset=0, highlight_shift=10.0)
    elif preset in ["Giallo Solare (Continuum / Luce Bianca)", "Giallo Solare"]:
        lut = create_solar_lut(hue_deg=38.0, sat_pct=90.0, lum_offset=0)
    elif preset == "Oro Solare":
        lut = create_solar_lut(hue_deg=32.0, sat_pct=85.0, lum_offset=0)
    elif preset in ["Calcio-K / CaK (393nm - Violetto)", "Calcio-K"]:
        lut = create_solar_lut(hue_deg=270.0, sat_pct=100.0, lum_offset=0)
    elif preset == "Blu (Deep Sky)":
        lut = create_solar_lut(hue_deg=210.0, sat_pct=90.0, lum_offset=0)
    else:
        # "Personalizzato" or manual custom parameters
        lut = create_solar_lut(hue_deg=float(hue), sat_pct=float(saturation), lum_offset=luminance)

    bgr_gray = cv2.merge([gray, gray, gray])
    return cv2.LUT(bgr_gray, lut)

def apply_logo_overlay(
    bgr_img: np.ndarray,
    logo_path: Optional[str] = None,
    position: str = "In Basso a Destra",
    scale_pct: int = 15,
    opacity_pct: int = 100
) -> np.ndarray:
    """
    Overlays a PNG logo (with optional alpha channel transparency) onto a BGR frame.
    """
    if not logo_path or not os.path.exists(logo_path):
        return bgr_img

    logo = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
    if logo is None:
        return bgr_img

    frame_h, frame_w, _ = bgr_img.shape
    scale = max(5, min(50, scale_pct)) / 100.0
    logo_target_w = int(frame_w * scale)
    
    if logo_target_w <= 0:
        return bgr_img

    aspect = logo.shape[0] / float(logo.shape[1])
    logo_target_h = int(logo_target_w * aspect)

    if logo_target_h > frame_h:
        logo_target_h = frame_h
        logo_target_w = int(logo_target_h / aspect)

    logo_resized = cv2.resize(logo, (logo_target_w, logo_target_h), interpolation=cv2.INTER_AREA)

    margin = 15
    if position == "In Alto a Sinistra":
        x, y = margin, margin
    elif position == "In Alto a Destra":
        x, y = frame_w - logo_target_w - margin, margin
    elif position == "In Basso a Sinistra":
        x, y = margin, frame_h - logo_target_h - margin
    elif position == "Centro":
        x, y = (frame_w - logo_target_w) // 2, (frame_h - logo_target_h) // 2
    else:  # "In Basso a Destra"
        x, y = frame_w - logo_target_w - margin, frame_h - logo_target_h - margin

    x = max(0, min(frame_w - logo_target_w, x))
    y = max(0, min(frame_h - logo_target_h, y))

    opacity = max(0, min(100, opacity_pct)) / 100.0
    out_img = bgr_img.copy()

    roi = out_img[y:y+logo_target_h, x:x+logo_target_w]

    if logo_resized.shape[2] == 4:
        logo_rgb = logo_resized[:, :, :3]
        alpha = (logo_resized[:, :, 3] / 255.0) * opacity
        alpha = alpha[:, :, np.newaxis]
        roi_blended = (logo_rgb * alpha + roi * (1.0 - alpha)).astype(np.uint8)
        out_img[y:y+logo_target_h, x:x+logo_target_w] = roi_blended
    else:
        roi_blended = (logo_resized * opacity + roi * (1.0 - opacity)).astype(np.uint8)
        out_img[y:y+logo_target_h, x:x+logo_target_w] = roi_blended

    return out_img
