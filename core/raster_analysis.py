"""
core/raster_analysis.py

Deterministic, offline analysis of JPEG/PNG raster files.
No network calls. No guessed/faked scores. Every number here is either
read from the file directly or computed with a named algorithm.
"""
from __future__ import annotations
import os
import io
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image, ExifTags
import cv2


@dataclass
class RasterReport:
    filepath: str
    filename: str
    file_format: str
    file_size_bytes: int
    width: int
    height: int
    megapixels: float
    aspect_ratio: str
    dpi: Optional[tuple]
    color_mode: str
    icc_profile_present: bool
    icc_profile_name: Optional[str]
    has_alpha: bool
    bit_depth: Optional[int]
    exif_present: bool
    gps_metadata_present: bool
    exif_tags_found: list = field(default_factory=list)

    # quality metrics (photo module)
    sharpness_laplacian_var: Optional[float] = None
    sharpness_verdict: Optional[str] = None
    noise_estimate: Optional[float] = None
    noise_verdict: Optional[str] = None
    brightness_mean: Optional[float] = None
    contrast_std: Optional[float] = None
    exposure_verdict: Optional[str] = None
    clipped_highlights_pct: Optional[float] = None
    clipped_shadows_pct: Optional[float] = None
    histogram_balance: Optional[str] = None

    # composition / occupancy
    empty_space_pct: Optional[float] = None
    object_occupancy_pct: Optional[float] = None
    center_of_mass_offset_pct: Optional[tuple] = None

    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _read_exif(img: Image.Image):
    tags_found = []
    gps_present = False
    try:
        exif = img.getexif()
        if not exif:
            return False, False, []
        for tag_id, _value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            tags_found.append(tag)
            if tag == "GPSInfo":
                gps_present = True
        return True, gps_present, tags_found
    except Exception:
        return False, False, []


def _laplacian_sharpness(cv_img_gray: np.ndarray) -> float:
    """Variance of the Laplacian — a standard, well-established, deterministic
    blur/sharpness metric. Higher = sharper. This is NOT a subjective score,
    it's a documented CV technique (Pech-Pacheco et al.)."""
    return float(cv2.Laplacian(cv_img_gray, cv2.CV_64F).var())


def _noise_estimate(cv_img_gray: np.ndarray) -> float:
    """Fast noise estimation using the median absolute deviation of the
    high-frequency (Laplacian) response — a common deterministic proxy for
    sensor/compression noise. Not a marketplace-specific 'noise score'."""
    lap = cv2.Laplacian(cv_img_gray, cv2.CV_64F)
    return float(np.median(np.abs(lap - np.median(lap))))


def _occupancy_via_background(cv_img_bgr: np.ndarray, has_alpha: bool, alpha_channel: Optional[np.ndarray]):
    """Estimate how much of the frame is 'subject' vs 'empty/background'.
    If the image has an alpha channel, transparency is used directly (exact).
    Otherwise, a background heuristic (near-uniform border color) is used,
    which is clearly labeled as an ESTIMATE, not an exact measurement.
    """
    h, w = cv_img_bgr.shape[:2]
    total = h * w

    if has_alpha and alpha_channel is not None:
        opaque = np.count_nonzero(alpha_channel > 10)
        occupancy = 100.0 * opaque / total
        return round(occupancy, 2), round(100.0 - occupancy, 2), "exact (alpha channel)"

    # Heuristic: sample border pixels to estimate background color, then
    # count pixels within a tolerance of that color as "empty space".
    border_pixels = np.concatenate([
        cv_img_bgr[0, :, :], cv_img_bgr[-1, :, :],
        cv_img_bgr[:, 0, :], cv_img_bgr[:, -1, :]
    ])
    bg_color = np.median(border_pixels, axis=0)
    diff = np.linalg.norm(cv_img_bgr.astype(np.float32) - bg_color.astype(np.float32), axis=2)
    tolerance = 18.0
    empty_mask = diff < tolerance
    empty_pct = 100.0 * np.count_nonzero(empty_mask) / total
    occupancy_pct = 100.0 - empty_pct
    return round(occupancy_pct, 2), round(empty_pct, 2), "estimate (border-color heuristic)"


def analyze_raster(filepath: str) -> RasterReport:
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    ext = os.path.splitext(filepath)[1].lower().lstrip(".")

    with Image.open(filepath) as img:
        width, height = img.size
        mode = img.mode
        dpi = img.info.get("dpi")
        icc = img.info.get("icc_profile")
        icc_present = icc is not None
        icc_name = None
        if icc_present:
            try:
                from PIL import ImageCms
                profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                icc_name = ImageCms.getProfileName(profile).strip()
            except Exception:
                icc_name = "Present (name unreadable)"

        has_alpha = mode in ("RGBA", "LA") or (mode == "P" and "transparency" in img.info)
        bit_depth = None
        try:
            bit_depth = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "CMYK": 32, "I": 32, "F": 32}.get(mode)
        except Exception:
            pass

        exif_present, gps_present, exif_tags = _read_exif(img)

        # Convert to arrays for CV analysis
        rgb_img = img.convert("RGB")
        cv_bgr = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY)

        alpha_channel = None
        if has_alpha:
            rgba = img.convert("RGBA")
            alpha_channel = np.array(rgba)[:, :, 3]

    mp = round((width * height) / 1_000_000, 2)

    def _ratio(w, h):
        g = math.gcd(w, h)
        return f"{w//g}:{h//g}"

    aspect = _ratio(width, height)

    report = RasterReport(
        filepath=filepath,
        filename=filename,
        file_format=ext.upper(),
        file_size_bytes=file_size,
        width=width,
        height=height,
        megapixels=mp,
        aspect_ratio=aspect,
        dpi=dpi,
        color_mode=mode,
        icc_profile_present=icc_present,
        icc_profile_name=icc_name,
        has_alpha=has_alpha,
        bit_depth=bit_depth,
        exif_present=exif_present,
        gps_metadata_present=gps_present,
        exif_tags_found=exif_tags,
    )

    # Sharpness
    lap_var = _laplacian_sharpness(gray)
    report.sharpness_laplacian_var = round(lap_var, 2)
    if lap_var < 50:
        report.sharpness_verdict = "Likely blurry (low detail/edge energy)"
    elif lap_var < 150:
        report.sharpness_verdict = "Soft — borderline, inspect visually"
    else:
        report.sharpness_verdict = "Sharp (high edge energy)"

    # Noise
    noise = _noise_estimate(gray)
    report.noise_estimate = round(noise, 3)
    report.noise_verdict = "Elevated noise — inspect visually" if noise > 6.0 else "Low noise"

    # Exposure / histogram
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    report.brightness_mean = round(brightness, 2)
    report.contrast_std = round(contrast, 2)
    if brightness < 60:
        report.exposure_verdict = "Likely underexposed"
    elif brightness > 200:
        report.exposure_verdict = "Likely overexposed"
    else:
        report.exposure_verdict = "Exposure within normal range"

    clipped_hi = 100.0 * np.count_nonzero(gray >= 250) / gray.size
    clipped_lo = 100.0 * np.count_nonzero(gray <= 5) / gray.size
    report.clipped_highlights_pct = round(clipped_hi, 2)
    report.clipped_shadows_pct = round(clipped_lo, 2)
    if clipped_hi > 5 or clipped_lo > 5:
        report.histogram_balance = "Significant clipping detected (loss of detail)"
    else:
        report.histogram_balance = "No significant clipping"

    # Occupancy / composition
    occ, empty, method = _occupancy_via_background(cv_bgr, has_alpha, alpha_channel)
    report.object_occupancy_pct = occ
    report.empty_space_pct = empty
    if method.startswith("estimate"):
        report.warnings.append(
            f"Occupancy/empty-space is an ESTIMATE ({method}); exact measurement requires alpha transparency or manual crop."
        )

    # Center of mass offset (composition balance) — only meaningful for occupancy-mask, use gray gradient magnitude as subject proxy
    grad = cv2.Laplacian(gray, cv2.CV_64F)
    mask = np.abs(grad) > np.percentile(np.abs(grad), 75)
    ys, xs = np.nonzero(mask)
    if len(xs) > 0:
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        offset_x_pct = round(100.0 * (cx - width / 2) / (width / 2), 2)
        offset_y_pct = round(100.0 * (cy - height / 2) / (height / 2), 2)
        report.center_of_mass_offset_pct = (offset_x_pct, offset_y_pct)

    # Warnings
    if gps_present:
        report.warnings.append("GPS metadata found in EXIF — consider stripping before upload (privacy).")
    if not icc_present:
        report.warnings.append("No embedded ICC color profile detected — recommend embedding sRGB.")
    if mode not in ("RGB", "RGBA"):
        report.warnings.append(f"Color mode is {mode}, not RGB — most marketplaces require RGB/sRGB.")

    return report


def phash(filepath: str, hash_size: int = 8) -> str:
    """Deterministic perceptual hash (DCT-based) for near-duplicate detection
    within a batch. Implemented locally, no external service."""
    with Image.open(filepath) as img:
        img = img.convert("L").resize((hash_size * 4, hash_size * 4), Image.LANCZOS)
        arr = np.asarray(img, dtype=np.float32)
        dct = cv2.dct(arr)
        dct_low = dct[:hash_size, :hash_size]
        med = np.median(dct_low)
        bits = (dct_low > med).flatten()
        return "".join("1" if b else "0" for b in bits)


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(hash_a, hash_b))


def strip_exif_and_save(src_path: str, dst_path: str) -> None:
    """User-requested explicit fix action: strip EXIF/GPS metadata.
    Only runs when the user explicitly clicks 'Apply Fix' in the UI."""
    with Image.open(src_path) as img:
        data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)
        clean.save(dst_path)
