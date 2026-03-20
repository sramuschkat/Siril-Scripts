"""
Siril Image Advisor
Script Version: 1.3.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script analyses a stacked, linear, unprocessed image loaded in Siril and provides
a prioritised list of recommended processing steps — including concrete Siril commands,
suggested parameters and reasoning. The script does NOT process the image automatically;
it outputs a diagnostic report the user can follow step by step.

Run from Siril via Processing → Scripts (or your configured Scripts menu). Siril uses
the script's parent folder name as the menu section; to show under "Utility", place
ImageAdvisor.py inside a folder named Utility in one of Siril's Script Storage
Directories (Preferences → Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.3.0 - Contextual intelligence improvements
      - Add: Gradient pattern classification (vignetting / linear LP / corner amp glow)
      - Add: Integration-time-aware noise advice (short vs long integration context)
      - Add: History-aware calibration detection (unknown vs missing distinction)
      - Add: Gradient pattern label on background heatmap
      - Add: Nebulosity-aware subsky -samples (higher sample count with nebulae)
      - Add: Narrowband-adjusted nebulosity thresholds (3σ floor vs 5σ broadband)
      - Add: Autostretch preview tip before starnet recommendation
      - Fix: Multi-line commands now display correctly in HTML and text reports
      - Fix: Gradient spread calculation no longer inflates near zero background
      - Fix: starnet -stretch conditional on linear state (avoids double-stretch)
      - Fix: Calibration shows "Unknown" instead of false negatives when no HISTORY
      - Fix: rl command uses -loadpsf=psf.fits (was missing PSF reference)
      - Fix: Script export requires 1.4.1 (denoise -mod= needs 1.4.1+)
      - Fix: VERSION constant now matches changelog

1.2.0 - Major diagnostic improvements
      - Add: Linear-state detection — warns if image is already stretched
      - Add: Calibration detection — checks FITS history for darks/flats/biases
      - Add: Background tile heatmap (8x8 grid) — reveals gradient direction/vignetting
      - Add: Per-channel noise table — shows R/G/B noise levels and noisiest channel
      - Add: Save checkpoints in exported .ssf scripts
      - Add: Per-sub vs total exposure display (EXPOSURE vs LIVETIME)
      - Fix: rl command — uses makepsf + rl -iters= (verified against Siril 1.4.x)
      - Fix: denoise — restored -mod= modulation, added -vst for photon-starved data
      - Fix: starnet — added -stretch flag for linear images
      - Fix: pltsolvd keyword used for plate-solve detection

1.1.0 - Expert review improvements
      - Fix: uint16 normalisation — divide by 65535, not max(data)
      - Add: Deconvolution step (Richardson-Lucy) between denoise and starless
      - Add: Dual-narrowband OSC filter detection (L-eNhance, L-Extreme, etc.)
      - Add: Scale-aware FWHM assessment (arcsec thresholds when plate-solved)
      - Add: Script export warning about current image context

1.0.0 - Initial release
      - Analyse linear image: type detection, noise/SNR, gradient, colour balance,
        star quality, plate-solve status, dynamic range
      - Generate prioritised workflow with Siril commands
      - PyQt6 dark-themed report GUI with optional script export
"""
from __future__ import annotations

import math
import re
import sys
import traceback
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

import sirilpy as s
from sirilpy import NoImageError

try:
    from sirilpy.exceptions import SirilError, SirilConnectionError
except ImportError:
    class _SirilErrorPlaceholder(Exception):
        pass
    SirilError = _SirilErrorPlaceholder
    SirilConnectionError = _SirilErrorPlaceholder

s.ensure_installed("numpy", "PyQt6")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QDialog, QTextEdit, QFileDialog, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer

VERSION = "1.3.0"

# Layout constants
LEFT_PANEL_WIDTH = 340
TILE_GRID = 8  # gradient detection grid size (8×8 tiles)
STATS_MAX_PIXELS = 5_000_000

# Luminance coefficients: Rec.709 (BT.709)
LUMINANCE_R = 0.2126
LUMINANCE_G = 0.7152
LUMINANCE_B = 0.0722


# ------------------------------------------------------------------------------
# STYLING
# ------------------------------------------------------------------------------

def _nofocus(w: QWidget | None) -> None:
    """Disable focus on widget to avoid keyboard focus issues."""
    if w is not None:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


DARK_STYLESHEET = """
QWidget{background-color:#2b2b2b;color:#e0e0e0;font-size:10pt}

QToolTip{background-color:#333333;color:#ffffff;border:1px solid #88aaff}

QGroupBox{border:1px solid #444444;margin-top:5px;font-weight:bold;border-radius:4px;padding-top:12px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 3px;color:#88aaff}

QLabel{color:#cccccc}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#RunButton{background-color:#2a4a2a;border:1px solid #408040}
QPushButton#RunButton:hover{background-color:#3a6a3a}

QScrollArea{border:none;background-color:#2b2b2b}

QProgressBar{border:1px solid #555555;border-radius:4px;text-align:center;background-color:#333333;color:#e0e0e0}
QProgressBar::chunk{background-color:#88aaff;border-radius:3px}

QTextEdit{background-color:#1e1e1e;color:#e0e0e0;border:1px solid #444444;border-radius:4px;font-family:'Menlo','Courier New'}
"""

SEVERITY_COLORS = {
    "info": "#88aaff",
    "minor": "#88cc88",
    "moderate": "#ddaa44",
    "critical": "#dd5555",
}

SEVERITY_ICONS = {
    "info": "ℹ",
    "minor": "✓",
    "moderate": "⚠",
    "critical": "✗",
}


# ------------------------------------------------------------------------------
# DATA STRUCTURES
# ------------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """Single analysis finding with recommendation."""
    category: str           # e.g. "gradient", "noise", "color"
    severity: str           # "info" | "minor" | "moderate" | "critical"
    finding: str            # Description of the finding
    recommendation: str     # Recommended step
    siril_command: str      # Concrete Siril command
    priority: int = 99      # Order in workflow (1 = first)


@dataclass
class ImageInfo:
    """Collected image metadata and statistics."""
    width: int = 0
    height: int = 0
    channels: int = 1
    bitpix: int = 16
    is_color: bool = False
    is_mono: bool = True
    bayer_pattern: str = ""
    filter_name: str = ""
    exposure: float = 0.0
    stack_count: int = 0
    focal_length: float = 0.0
    pixel_size: float = 0.0
    arcsec_per_pixel: float = 0.0
    is_plate_solved: bool = False
    # Per-channel statistics
    channel_means: list = field(default_factory=list)
    channel_medians: list = field(default_factory=list)
    channel_stddevs: list = field(default_factory=list)
    # Derived
    image_type: str = "Unknown"       # "OSC Broadband", "Mono", "Narrowband", etc.
    snr_estimate: float = 0.0
    noise_mad: float = 0.0            # MAD-based noise estimate (normalised)
    gradient_spread: float = 0.0      # percentage
    gradient_tile_medians: list = field(default_factory=list)
    gradient_pattern: str = ""        # "vignetting", "linear", "corner", or ""
    color_balance_ratios: list = field(default_factory=list)  # R:G, B:G ratios
    green_excess: bool = False
    clip_black_pct: float = 0.0
    clip_white_pct: float = 0.0
    # Cropping
    crop_top: int = 0                 # rows of near-zero pixels at top edge
    crop_bottom: int = 0
    crop_left: int = 0
    crop_right: int = 0
    needs_cropping: bool = False
    # Star data
    num_stars: int = 0
    mean_fwhm: float = 0.0
    mean_elongation: float = 0.0
    fwhm_centre: float = 0.0
    fwhm_edge: float = 0.0
    elongation_spatial_issue: bool = False
    saturated_stars: int = 0            # count of stars with saturated cores
    star_error: str = ""              # error message if star detection failed
    # Dynamic range
    bg_median: float = 0.0
    bg_mad: float = 0.0              # MAD of background
    peak_value: float = 0.0
    dynamic_range_ratio: float = 0.0
    dynamic_range_stops: float = 0.0  # log2(peak/noise) — usable DR in stops
    # Nebulosity detection
    nebulosity_fraction: float = 0.0  # fraction of pixels significantly above background
    # Processing state
    is_linear: bool = True            # True if no stretch operations detected in history
    stretch_history: list = field(default_factory=list)  # stretch-related history entries
    # Calibration
    has_history: bool = False          # True if any HISTORY entries were found
    has_darks: bool = False
    has_flats: bool = False
    has_biases: bool = False
    livetime: float = 0.0            # total integration time (LIVETIME keyword)
    exposure_per_sub: float = 0.0    # per-sub exposure (EXPOSURE keyword)
    # Per-channel noise (MAD-based sigma per channel)
    channel_noise: list = field(default_factory=list)
    # Sanity flag: set when image fails basic checks (extreme clipping, phone dims)
    # When True, downstream processing recommendations are suppressed.
    image_suspect: bool = False


# ------------------------------------------------------------------------------
# ANALYSIS HELPERS
# ------------------------------------------------------------------------------

def _subsample(arr: np.ndarray, max_pixels: int = STATS_MAX_PIXELS) -> np.ndarray:
    """Return a possibly-subsampled view of arr for fast statistics."""
    if arr.size <= max_pixels:
        return arr
    h, w = arr.shape[0], arr.shape[1] if arr.ndim >= 2 else 1
    if h <= 0 or w <= 0:
        return arr
    stride = int(math.ceil(math.sqrt(arr.size / float(max_pixels))))
    stride = max(1, stride)
    return arr[::stride, ::stride, ...] if arr.ndim >= 2 else arr[::stride]


def _normalize_to_float(data: np.ndarray) -> np.ndarray:
    """Normalize pixel data to 0-1 float32.

    Siril stores linear FITS as 32-bit float already in [0, 1]. Dividing by
    np.max would destroy the absolute scale — a faint image with peak 0.3
    would be stretched to [0, 1], making SNR/noise metrics unreliable.
    For float data in [0, 1] we therefore pass through without rescaling.
    """
    img = data.astype(np.float32, copy=True)
    if data.dtype == np.uint8:
        img /= 255.0
    elif data.dtype == np.uint16:
        img /= 65535.0
    elif data.dtype == np.int16:
        img = (img + 32768.0) / 65535.0
    else:
        # Float data: Siril normalises to [0, 1]. Only rescale if clearly
        # in a different range (e.g. [0, 65535] from some pipelines).
        mx = float(np.max(img))
        if mx > 1.5:
            img /= mx
        # If max <= 1.5, data is already in roughly [0, 1] — keep as-is
    return np.clip(img, 0.0, 1.0)


def _ensure_chw_to_hwc(data: np.ndarray) -> np.ndarray:
    """Convert Siril CHW format to HWC if needed."""
    if data.ndim == 2:
        return data[:, :, np.newaxis]
    if data.ndim == 3:
        if data.shape[0] in (1, 3) and data.shape[2] not in (1, 3):
            return np.transpose(data, (1, 2, 0))
    return data


# ------------------------------------------------------------------------------
# DATA COLLECTION (Phase 1)
# ------------------------------------------------------------------------------

def collect_image_info(siril) -> ImageInfo:
    """Collect all image metadata and pixel data from Siril."""
    info = ImageInfo()

    # Get pixel data — use get_image_pixeldata (proven API, same as MultipleHistogramViewer)
    pixeldata = siril.get_image_pixeldata(preview=False)
    if pixeldata is None:
        raise NoImageError("No pixel data returned from Siril")
    raw_data = np.asarray(pixeldata)
    data = _ensure_chw_to_hwc(raw_data)
    norm = _normalize_to_float(data)

    info.height, info.width = norm.shape[0], norm.shape[1]
    info.channels = norm.shape[2] if norm.ndim == 3 else 1
    info.is_color = info.channels >= 3
    info.is_mono = not info.is_color

    # Keywords — try get_keywords first, fall back gracefully
    try:
        kw = siril.get_keywords()
        info.bitpix = getattr(kw, "bitpix", 16)
        info.bayer_pattern = getattr(kw, "bayer_pattern", "") or ""
        info.filter_name = (getattr(kw, "filter", "") or "").strip()
        info.exposure_per_sub = getattr(kw, "exposure", 0.0) or 0.0
        info.livetime = getattr(kw, "livetime", 0.0) or 0.0
        info.exposure = info.livetime if info.livetime > 0 else info.exposure_per_sub
        info.stack_count = getattr(kw, "stackcnt", 0) or 0
        info.focal_length = getattr(kw, "focal_length", 0.0) or 0.0
        info.pixel_size = getattr(kw, "pixel_size_x", 0.0) or getattr(kw, "pixel_size", 0.0) or 0.0
        info.is_plate_solved = bool(getattr(kw, "pltsolvd", False))
        if not info.is_plate_solved:
            info.is_plate_solved = bool(getattr(kw, "wcsdata", None))
    except Exception:
        pass

    # Image history — check for stretch operations and calibration
    try:
        history = siril.get_image_history()
        if history and len(history) > 0:
            info.has_history = True
            # Stretch detection: match whole words/commands to avoid false positives.
            # "ght" is Siril's Generalised Hyperbolic Transformations command —
            # substring match would hit "lighting", "weighted", etc.
            # Use word-boundary regex (\b) for short keywords.
            stretch_patterns = [
                re.compile(r'\bght\b', re.IGNORECASE),
                re.compile(r'\bautostretch\b', re.IGNORECASE),
                re.compile(r'\bmtf\b', re.IGNORECASE),
                re.compile(r'\basinh\b', re.IGNORECASE),
                re.compile(r'\bhisteq\b', re.IGNORECASE),
                re.compile(r'\bclahe\b', re.IGNORECASE),
                re.compile(r'\bhisto_transfer\b', re.IGNORECASE),
                # "histogram" as a standalone command (not "histogram equalization" from calibration)
                re.compile(r'\bhistogram\s+(transformation|transfer|stretch)', re.IGNORECASE),
            ]
            for entry in history:
                entry_lower = entry.lower()
                # Stretch detection
                for pat in stretch_patterns:
                    if pat.search(entry):
                        info.is_linear = False
                        info.stretch_history.append(entry.strip())
                        break
                # Calibration detection from sirilpy history
                if "dark" in entry_lower and ("subtracted" in entry_lower or "applied" in entry_lower or "calibrat" in entry_lower):
                    info.has_darks = True
                if "flat" in entry_lower and ("divided" in entry_lower or "applied" in entry_lower or "calibrat" in entry_lower):
                    info.has_flats = True
                if "bias" in entry_lower or "offset" in entry_lower:
                    info.has_biases = True
    except Exception:
        pass

    # Fallback: try FITS header parsing for metadata we couldn't get from keywords,
    # and detect calibration frames
    try:
        hdr = siril.get_fits_header()
        if hdr:
            for line in hdr.split("\n"):
                line_upper = line.upper()
                if line.startswith("FILTER") and not info.filter_name:
                    val = line.split("=", 1)[-1].split("/")[0].strip().strip("'\" ")
                    if val:
                        info.filter_name = val
                elif line.startswith("LIVETIME") and info.livetime <= 0:
                    val = line.split("=", 1)[-1].split("/")[0].strip()
                    try:
                        info.livetime = float(val)
                        if info.livetime > 0 and info.exposure <= 0:
                            info.exposure = info.livetime
                    except ValueError:
                        pass
                elif line.startswith("STACKCNT") and info.stack_count <= 0:
                    val = line.split("=", 1)[-1].split("/")[0].strip()
                    try:
                        info.stack_count = int(val)
                    except ValueError:
                        pass
                elif line.startswith("CRVAL1") and not info.is_plate_solved:
                    info.is_plate_solved = True
                # Calibration detection from FITS HISTORY entries
                if "HISTORY" in line_upper:
                    info.has_history = True
                    hist_val = line.split("HISTORY", 1)[-1].strip()
                    hist_lower = hist_val.lower()
                    if "dark" in hist_lower and ("subtracted" in hist_lower or "calibrat" in hist_lower):
                        info.has_darks = True
                    if "flat" in hist_lower and ("divided" in hist_lower or "applied" in hist_lower or "calibrat" in hist_lower):
                        info.has_flats = True
                    if "bias" in hist_lower or "offset" in hist_lower:
                        info.has_biases = True
    except Exception:
        pass

    # Arcsec per pixel
    if info.focal_length > 0 and info.pixel_size > 0:
        info.arcsec_per_pixel = (info.pixel_size / info.focal_length) * 206.265

    # Per-channel statistics on subsampled data
    sample = _subsample(norm)
    if info.is_color:
        for c in range(min(3, info.channels)):
            ch = sample[:, :, c]
            info.channel_means.append(float(np.mean(ch)))
            info.channel_medians.append(float(np.median(ch)))
            info.channel_stddevs.append(float(np.std(ch)))
            # Per-channel MAD noise (darkest 25%)
            ch_sorted = np.sort(ch.ravel())
            n_bg = max(1, len(ch_sorted) // 4)
            ch_bg = ch_sorted[:n_bg]
            ch_med = float(np.median(ch_bg))
            ch_mad = float(np.median(np.abs(ch_bg - ch_med)))
            info.channel_noise.append(1.4826 * ch_mad)
    else:
        ch = sample[:, :, 0] if sample.ndim == 3 else sample
        info.channel_means.append(float(np.mean(ch)))
        info.channel_medians.append(float(np.median(ch)))
        info.channel_stddevs.append(float(np.std(ch)))
        ch_sorted = np.sort(ch.ravel())
        n_bg = max(1, len(ch_sorted) // 4)
        ch_bg = ch_sorted[:n_bg]
        ch_med = float(np.median(ch_bg))
        ch_mad = float(np.median(np.abs(ch_bg - ch_med)))
        info.channel_noise.append(1.4826 * ch_mad)

    # Image type detection
    info.image_type = _detect_image_type(info)

    # --- Luminance channel for all subsequent analysis ---
    lum = _get_luminance(sample)

    # --- MAD-based noise and SNR estimation ---
    # Use the darkest 25% of pixels (background region) to avoid nebula contamination.
    # MAD (Median Absolute Deviation) is robust against outliers (stars, hot pixels).
    lum_sorted = np.sort(lum.ravel())
    n_bg = max(1, len(lum_sorted) // 4)  # darkest 25%
    bg_pixels = lum_sorted[:n_bg]
    info.bg_median = float(np.median(bg_pixels))
    info.bg_mad = float(np.median(np.abs(bg_pixels - info.bg_median)))
    # Convert MAD to sigma-equivalent: sigma ~= 1.4826 * MAD (for Gaussian)
    bg_sigma = 1.4826 * info.bg_mad
    info.noise_mad = bg_sigma
    info.snr_estimate = info.bg_median / bg_sigma if bg_sigma > 1e-10 else 0.0

    # --- Dynamic range (robust) ---
    # Use 99.5th percentile instead of 99.9th to avoid single hot pixels.
    # On linear data, work with absolute values rather than ratios when bg is near zero.
    info.peak_value = float(np.percentile(lum.ravel(), 99.5))
    if info.bg_median > 1e-6:
        info.dynamic_range_ratio = info.peak_value / info.bg_median
    else:
        # Background near zero: express DR as peak / noise floor instead
        info.dynamic_range_ratio = info.peak_value / bg_sigma if bg_sigma > 1e-10 else 0.0
    # Usable dynamic range in stops: log2(peak / noise_floor)
    if bg_sigma > 1e-10 and info.peak_value > bg_sigma:
        info.dynamic_range_stops = math.log2(info.peak_value / bg_sigma)
    else:
        info.dynamic_range_stops = 0.0

    # --- Gradient detection (sigma-clipped) ---
    _compute_gradient(info, norm, bg_sigma)

    # --- Colour balance ---
    # Record the raw channel ratios as factual data. On linear uncalibrated data
    # (especially OSC) the green channel is naturally brighter (2 green photosites
    # per Bayer quad), so we do NOT use these ratios to flag "green excess" —
    # that can only be judged after SPCC.
    if info.is_color and len(info.channel_medians) >= 3:
        g_med = info.channel_medians[1]
        if g_med > 1e-10:
            r_ratio = info.channel_medians[0] / g_med
            b_ratio = info.channel_medians[2] / g_med
            info.color_balance_ratios = [r_ratio, b_ratio]
            # green_excess is NOT set here — it's unreliable before colour calibration
            info.green_excess = False

    # --- Clipping check ---
    lum_flat = lum.ravel()
    info.clip_black_pct = float(np.sum(lum_flat < 0.001)) / lum_flat.size * 100.0
    info.clip_white_pct = float(np.sum(lum_flat > 0.999)) / lum_flat.size * 100.0

    # --- Edge/crop analysis ---
    _detect_stacking_borders(info, norm)

    # --- Nebulosity detection ---
    # Pixels significantly above background but below star threshold indicate
    # extended nebulosity, which informs the starless recommendation.
    # Narrowband data has lower-contrast diffuse emission, so use a lower floor
    # (3σ vs 5σ) to avoid under-counting nebulosity on Ha/OIII/SII images.
    if bg_sigma > 1e-10:
        is_narrowband = ("Narrowband" in info.image_type or "Dual-Narrowband" in info.image_type)
        nebula_floor = 3.0 if is_narrowband else 5.0
        nebula_threshold = info.bg_median + nebula_floor * bg_sigma
        star_threshold = info.bg_median + 50.0 * bg_sigma
        nebula_mask = (lum_flat > nebula_threshold) & (lum_flat < star_threshold)
        info.nebulosity_fraction = float(np.sum(nebula_mask)) / lum_flat.size

    return info


def _get_luminance(data: np.ndarray) -> np.ndarray:
    """Extract 2D luminance from HWC or 2D array."""
    if data.ndim == 2:
        return data
    if data.ndim == 3 and data.shape[2] >= 3:
        return (LUMINANCE_R * data[:, :, 0] +
                LUMINANCE_G * data[:, :, 1] +
                LUMINANCE_B * data[:, :, 2])
    if data.ndim == 3:
        return data[:, :, 0]
    return data


def _detect_stacking_borders(info: ImageInfo, norm: np.ndarray) -> None:
    """
    Detect stacking borders by checking edge rows/columns for near-zero pixels.

    Stacking typically produces borders of black (zero) pixels where frames didn't
    overlap. We scan inward from each edge until we find a row/column where the
    median is above a low threshold.
    """
    lum = _get_luminance(norm)
    h, w = lum.shape
    threshold = 0.005  # normalised; anything below is considered black border
    max_scan = min(100, h // 4, w // 4)  # don't scan more than 25% of the image

    # Top edge
    for i in range(max_scan):
        if float(np.median(lum[i, :])) > threshold:
            info.crop_top = i
            break
    else:
        info.crop_top = max_scan

    # Bottom edge
    for i in range(max_scan):
        if float(np.median(lum[h - 1 - i, :])) > threshold:
            info.crop_bottom = i
            break
    else:
        info.crop_bottom = max_scan

    # Left edge
    for i in range(max_scan):
        if float(np.median(lum[:, i])) > threshold:
            info.crop_left = i
            break
    else:
        info.crop_left = max_scan

    # Right edge
    for i in range(max_scan):
        if float(np.median(lum[:, w - 1 - i])) > threshold:
            info.crop_right = i
            break
    else:
        info.crop_right = max_scan

    info.needs_cropping = any([info.crop_top > 0, info.crop_bottom > 0,
                               info.crop_left > 0, info.crop_right > 0])


def _detect_image_type(info: ImageInfo) -> str:
    """Classify the image type based on metadata."""
    filt = info.filter_name.upper()
    nb_filters = {"HA", "H-ALPHA", "HALPHA", "SII", "S-II", "OIII", "O-III",
                  "NII", "N-II", "SHO", "HOO"}
    # Dual-narrowband filters used with OSC cameras — NOT suitable for SPCC
    dual_nb_filters = {"L-ENHANCE", "LENHANCE", "L-EXTREME", "LEXTREME",
                       "L-PRO", "LPRO", "NBZ", "L-ULTIMATE", "LULTIMATE",
                       "ANTLIA ALP-T"}

    if info.is_mono:
        if any(nb in filt for nb in nb_filters):
            return "Narrowband (Mono)"
        if "L" == filt or "LUM" in filt or "LUMINANCE" in filt:
            return "Luminance (Mono)"
        return "Mono"

    # Color image
    if any(nb in filt for nb in nb_filters):
        return "Narrowband (Colour)"
    if any(dnb in filt for dnb in dual_nb_filters):
        return "Dual-Narrowband OSC"
    if info.bayer_pattern:
        return "OSC Broadband (RGB)"
    return "Broadband (RGB)"


def _compute_gradient(info: ImageInfo, norm: np.ndarray, bg_sigma: float) -> None:
    """
    Compute gradient spread from sigma-clipped tile medians.

    Stars and bright nebula are rejected (pixels > median + 2*sigma per tile)
    before computing the tile median. This prevents bright objects from being
    mistaken for gradient.
    """
    lum = _get_luminance(norm)
    h, w = lum.shape
    tile_h = max(1, h // TILE_GRID)
    tile_w = max(1, w // TILE_GRID)
    tile_medians = []

    for row in range(TILE_GRID):
        for col in range(TILE_GRID):
            r0 = row * tile_h
            r1 = min((row + 1) * tile_h, h)
            c0 = col * tile_w
            c1 = min((col + 1) * tile_w, w)
            tile = lum[r0:r1, c0:c1].ravel()
            if tile.size == 0:
                continue
            # Sigma-clip: iteratively reject pixels > 2 sigma above tile median
            # Two iterations is enough to reject stars and bright nebula cores.
            clipped = tile
            for _ in range(2):
                med = float(np.median(clipped))
                mad = float(np.median(np.abs(clipped - med)))
                sigma = max(1.4826 * mad, bg_sigma, 1e-10)
                mask = clipped < med + 2.0 * sigma
                if np.sum(mask) < clipped.size * 0.3:
                    break  # don't reject more than 70% of pixels
                clipped = clipped[mask]
            tile_medians.append(float(np.median(clipped)))

    info.gradient_tile_medians = tile_medians
    if tile_medians:
        med_of_meds = float(np.median(tile_medians))
        spread = max(tile_medians) - min(tile_medians)
        # Percentage spread relative to median — but guard against very low backgrounds
        # where a tiny absolute difference produces a misleadingly huge percentage.
        # If median < 0.005 (background near zero on 0-1 scale), fall back to absolute
        # spread scaled to a reference level of 0.01 (1% of full range).
        if med_of_meds > 0.005:
            info.gradient_spread = (spread / med_of_meds * 100.0)
        elif spread > 1e-10:
            # Absolute spread: treat 0.01 difference as ~100% gradient
            info.gradient_spread = min(spread / 0.01 * 100.0, 100.0)
        else:
            info.gradient_spread = 0.0


def collect_star_info(siril, info: ImageInfo) -> None:
    """Detect stars using get_image_stars() and collect quality metrics.

    Uses sirilpy's get_image_stars() which internally runs findstar if needed.
    PSFStar objects provide fwhmx/fwhmy (pixels and arcsec), position, angle, etc.
    """
    try:
        stars = siril.get_image_stars()
    except Exception as e:
        info.star_error = f"Star detection failed: {e}"
        return

    if not stars:
        info.star_error = "No stars detected in image"
        return

    info.num_stars = len(stars)
    fwhms = []
    elongations = []
    star_positions = []  # (x, y, fwhm, elongation)
    saturated_count = 0

    for star in stars:
        # Count saturated stars (PSFStar.has_saturated)
        if getattr(star, "has_saturated", False):
            saturated_count += 1
        # PSFStar provides fwhmx and fwhmy (pixels)
        fwhmx = getattr(star, "fwhmx", 0.0) or 0.0
        fwhmy = getattr(star, "fwhmy", 0.0) or 0.0
        fwhm = (fwhmx + fwhmy) / 2.0 if fwhmx > 0 and fwhmy > 0 else max(fwhmx, fwhmy)
        # Elongation: ratio of major/minor FWHM axis (>=1.0, 1.0 = round)
        if fwhmx > 0 and fwhmy > 0:
            elong = max(fwhmx, fwhmy) / min(fwhmx, fwhmy)
        else:
            elong = 1.0
        x = getattr(star, "xpos", 0.0) or getattr(star, "x0", 0.0) or 0.0
        y = getattr(star, "ypos", 0.0) or getattr(star, "y0", 0.0) or 0.0
        if fwhm > 0:
            fwhms.append(fwhm)
            elongations.append(elong)
            star_positions.append((x, y, fwhm, elong))

    info.saturated_stars = saturated_count

    if not fwhms:
        return

    info.mean_fwhm = float(np.mean(fwhms))
    info.mean_elongation = float(np.mean(elongations))

    # Spatial FWHM and elongation analysis: centre vs edge
    if star_positions and info.width > 0 and info.height > 0:
        cx, cy = info.width / 2.0, info.height / 2.0
        max_dist = math.sqrt(cx ** 2 + cy ** 2)
        centre_fwhms = []
        edge_fwhms = []
        centre_elongs = []
        edge_elongs = []

        for x, y, fwhm, elong in star_positions:
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist < max_dist * 0.4:
                centre_fwhms.append(fwhm)
                centre_elongs.append(elong)
            elif dist > max_dist * 0.7:
                edge_fwhms.append(fwhm)
                edge_elongs.append(elong)

        if centre_fwhms:
            info.fwhm_centre = float(np.mean(centre_fwhms))
        if edge_fwhms:
            info.fwhm_edge = float(np.mean(edge_fwhms))

        # Check if edge elongation is significantly worse
        if centre_elongs and edge_elongs:
            if float(np.mean(edge_elongs)) > float(np.mean(centre_elongs)) * 1.2:
                info.elongation_spatial_issue = True


# ------------------------------------------------------------------------------
# ANALYSIS MODULES (Phase 2)
#
# Workflow path (from user's processing diagram):
#
# PROCESSING LINEAR:
#   1. Cropping
#   2. Background Extraction (Hintergrund-Extraktion)
#   3. Platesolving
#   4. SPCC (Spectrophotometric Colour Calibration)
#   5. Remove Green / SCNR (optional)
#   6. Denoising
#   7. Deconvolution (when SNR allows)
#   8. Starless (SyQon) — star removal in linear stage
#
# STRETCHING:
#   8. VeraLux HMS
#
# POST-PROCESSING (non-linear):
#   9.  Fine-tuning (Revela / Curves / Vectra)
#  10.  StarComposer (star recomposition)
#  11.  Signature
#  12.  Final image
# ------------------------------------------------------------------------------

def analyse_linear_state(info: ImageInfo) -> Optional[AnalysisResult]:
    """Check if the image is still in linear state — critical for all recommendations."""
    if not info.is_linear:
        history_str = "; ".join(info.stretch_history[:3])
        return AnalysisResult(
            category="WARNING",
            severity="critical",
            finding=f"Image appears ALREADY STRETCHED — detected: {history_str}. "
                    "All linear-stage recommendations below may be WRONG.",
            recommendation="Reload the original linear stack before processing. "
                          "Do NOT apply linear-stage operations to a stretched image.",
            siril_command="",
            priority=-1,  # show first, before everything

        )
    return None


def analyse_calibration(info: ImageInfo) -> list[AnalysisResult]:
    """Check if calibration frames were applied — affects gradient and noise interpretation."""
    results = []

    # If no HISTORY entries were found at all, we cannot determine calibration status.
    # The image may have been stacked in another tool (PixInsight, APP, DSS) that doesn't
    # write Siril-style HISTORY. Don't alarm the user with false negatives.
    if not info.has_history:
        results.append(AnalysisResult(
            category="calibration",
            severity="info",
            finding="No processing history detected in FITS headers",
            recommendation="Calibration status unknown — image may have been stacked in another application. "
                          "If you stacked in Siril, check that calibration masters were applied.",
            siril_command="",
            priority=-1,

        ))
        return results

    if not info.has_flats:
        results.append(AnalysisResult(
            category="calibration",
            severity="moderate",
            finding="No flat-field calibration detected in image history",
            recommendation="Gradient and vignetting may be from missing flats, not light pollution. "
                          "Re-stack with flat frames if available.",
            siril_command="",
            priority=-1,

        ))
    if not info.has_darks and not info.has_biases:
        results.append(AnalysisResult(
            category="calibration",
            severity="minor",
            finding="No dark/bias calibration detected in image history",
            recommendation="Hot pixels and amp glow may be present. Consider cosmetic correction "
                          "or re-stack with darks/biases.",
            siril_command="",
            priority=-1,

        ))
    return results


def analyse_cropping(info: ImageInfo) -> Optional[AnalysisResult]:
    """Check if cropping is needed based on edge pixel analysis."""
    # Priority 1: Cropping is the first step in the linear workflow
    if info.needs_cropping:
        borders = []
        if info.crop_top > 0:
            borders.append(f"top: {info.crop_top} px")
        if info.crop_bottom > 0:
            borders.append(f"bottom: {info.crop_bottom} px")
        if info.crop_left > 0:
            borders.append(f"left: {info.crop_left} px")
        if info.crop_right > 0:
            borders.append(f"right: {info.crop_right} px")
        border_str = ", ".join(borders)

        # Check if scan hit the limit — borders may extend further than detected
        max_scan = min(100, info.height // 4, info.width // 4)
        all_at_limit = all([
            info.crop_top >= max_scan,
            info.crop_bottom >= max_scan,
            info.crop_left >= max_scan,
            info.crop_right >= max_scan,
        ])

        # Use boxselect + crop — this is safe across Siril versions.
        # boxselect x y width height sets the selection, crop applies it.
        new_x = info.crop_left
        new_y = info.crop_top
        new_w = info.width - info.crop_left - info.crop_right
        new_h = info.height - info.crop_top - info.crop_bottom

        if all_at_limit:
            # All edges hit the scan ceiling — borders may extend further.
            # If image_suspect is set, this is a serious concern.
            # Otherwise, it's likely just wide stacking borders on a normal image.
            if info.image_suspect:
                return AnalysisResult(
                    category="crop",
                    severity="critical",
                    finding=f"All borders hit scan limit ({max_scan} px on every side) — "
                            "the actual black region may extend much further",
                    recommendation="The image appears mostly empty. Check that this is the correct "
                                  "stacked file.",
                    siril_command=f"boxselect {new_x} {new_y} {new_w} {new_h}\ncrop",

                    priority=0,
        
                )
            else:
                return AnalysisResult(
                    category="crop",
                    severity="moderate",
                    finding=f"Wide stacking borders detected (≥{max_scan} px on all sides) — "
                            "borders may extend further than detected",
                    recommendation=f"Crop stacking borders. The suggested crop below removes {max_scan} px "
                                  "per side — verify in Siril and adjust if needed.",
                    siril_command=f"boxselect {new_x} {new_y} {new_w} {new_h}\ncrop",

                    priority=1,
        
                )

        return AnalysisResult(
            category="crop",
            severity="moderate",
            finding=f"Stacking borders detected — {border_str}",
            recommendation=f"Crop stacking borders ({border_str})",
            siril_command=f"boxselect {new_x} {new_y} {new_w} {new_h}\ncrop",

            priority=1,

        )
    else:
        return AnalysisResult(
            category="crop",
            severity="info",
            finding="No stacking borders detected",
            recommendation="No cropping needed",
            siril_command="",
            priority=1,

        )


def classify_gradient_pattern(info: ImageInfo) -> str:
    """Classify gradient pattern from the 8×8 tile heatmap.

    Returns one of:
        "vignetting" — corners dark, centre bright (needs flats, not subsky)
        "linear"     — one side systematically brighter (light pollution, subsky appropriate)
        "corner"     — single corner bright (amp glow, may need masking)
        ""           — no clear pattern or gradient too small to classify
    """
    tiles = info.gradient_tile_medians
    n = TILE_GRID
    if not tiles or len(tiles) != n * n:
        return ""

    grid = np.array(tiles).reshape(n, n)
    med = np.median(grid)
    if med < 1e-10:
        return ""

    # Normalise to median
    norm = grid / med

    # Define regions
    # Centre: inner 4×4 of 8×8
    centre = norm[2:6, 2:6]
    centre_mean = float(np.mean(centre))

    # Corners: 2×2 blocks at each corner
    corners = [norm[:2, :2], norm[:2, -2:], norm[-2:, :2], norm[-2:, -2:]]
    corner_means = [float(np.mean(c)) for c in corners]
    all_corners_mean = float(np.mean(corner_means))

    # Edges: full rows/columns
    top_mean = float(np.mean(norm[0, :]))
    bottom_mean = float(np.mean(norm[-1, :]))
    left_mean = float(np.mean(norm[:, 0]))
    right_mean = float(np.mean(norm[:, -1]))

    # 1. Vignetting: centre brighter than all corners
    # All four corners should be dimmer than centre by ≥ 3%
    if all(cm < centre_mean - 0.03 for cm in corner_means) and centre_mean > all_corners_mean + 0.03:
        info.gradient_pattern = "vignetting"
        return "vignetting"

    # 2. Single corner bright (amp glow): one corner is significantly brighter than the other three
    max_corner_idx = int(np.argmax(corner_means))
    max_corner = corner_means[max_corner_idx]
    other_corners = [corner_means[i] for i in range(4) if i != max_corner_idx]
    other_mean = float(np.mean(other_corners))
    if max_corner > other_mean + 0.05 and max_corner > centre_mean + 0.02:
        info.gradient_pattern = "corner"
        return "corner"

    # 3. Linear gradient: one side systematically brighter than the opposite
    # Check horizontal (left vs right) and vertical (top vs bottom) asymmetry
    lr_diff = abs(left_mean - right_mean)
    tb_diff = abs(top_mean - bottom_mean)
    max_diff = max(lr_diff, tb_diff)
    if max_diff > 0.04:
        info.gradient_pattern = "linear"
        return "linear"

    info.gradient_pattern = ""
    return ""


def _subsky_cmd(degree: int, info: ImageInfo) -> str:
    """Build subsky command with nebulosity-aware sample count.

    When significant nebulosity is present, increase the sample count so the
    polynomial fit has enough clean background points and doesn't overcorrect
    by fitting to nebula emission.
    """
    if info.nebulosity_fraction > 0.05:
        return f"subsky {degree} -samples=25"
    elif info.nebulosity_fraction > 0.01:
        return f"subsky {degree} -samples=15"
    return f"subsky {degree}"


def analyse_gradient(info: ImageInfo) -> Optional[AnalysisResult]:
    """Evaluate background gradient severity with pattern-aware recommendations."""
    # Priority 2: Background Extraction
    spread = info.gradient_spread

    # Calibration context: if flats are missing, gradients may be from vignetting
    cal_note = ""
    if info.has_history and not info.has_flats:
        cal_note = " ⚠ No flats detected — part of this gradient may be vignetting that subsky cannot fully correct."

    # Classify the gradient pattern before making recommendations
    pattern = classify_gradient_pattern(info)

    if spread < 2.0:
        # Gradient is negligible — suppress any pattern classification since
        # the classifier is just fitting noise at this level.
        info.gradient_pattern = ""
        return AnalysisResult(
            category="gradient",
            severity="info",
            finding=f"Minimal gradient detected (spread {spread:.1f}%)",
            recommendation="Background extraction can be skipped",
            siril_command="",
            priority=2,

        )

    # Pattern-specific recommendations for significant gradients
    if pattern == "vignetting":
        rec = ("Gradient pattern looks like vignetting (corners dark, centre bright). "
               "This is best corrected with flat frames, not background extraction. "
               "If flats are unavailable, subsky with a low degree may partially help.")
        cmd = _subsky_cmd(2, info) if spread < 15.0 else _subsky_cmd(3, info)
        if not info.has_flats and info.has_history:
            rec += " ⚠ No flats detected — re-stack with flats for a proper fix."
        return AnalysisResult(
            category="gradient",
            severity="moderate",
            finding=f"Vignetting pattern detected (spread {spread:.1f}%)",
            recommendation=rec,
            siril_command=cmd,

            priority=2,

        )

    if pattern == "corner":
        corner_names = ["top-left", "top-right", "bottom-left", "bottom-right"]
        # Re-derive which corner is brightest for the finding text
        grid = np.array(info.gradient_tile_medians).reshape(TILE_GRID, TILE_GRID)
        corners_2x2 = [grid[:2, :2], grid[:2, -2:], grid[-2:, :2], grid[-2:, -2:]]
        bright_idx = int(np.argmax([float(np.mean(c)) for c in corners_2x2]))
        bright_corner = corner_names[bright_idx]
        return AnalysisResult(
            category="gradient",
            severity="moderate",
            finding=f"Amp glow pattern detected — {bright_corner} corner bright (spread {spread:.1f}%)",
            recommendation=f"Single-corner brightness ({bright_corner}) suggests amp glow. "
                          "Consider masking the affected region before background extraction, "
                          "or use GraXpert for targeted removal. Subsky alone may smear the artefact.",
            siril_command=_subsky_cmd(3, info),

            priority=2,

        )

    # Default: linear gradient (one side brighter) or unclassified — standard subsky advice
    if spread < 10.0:
        return AnalysisResult(
            category="gradient",
            severity="moderate",
            finding=f"Moderate {'linear ' if pattern == 'linear' else ''}gradient detected (spread {spread:.1f}%)",
            recommendation=f"Background extraction with polynomial degree 1-2{cal_note}",
            siril_command=_subsky_cmd(2, info),

            priority=2,

        )
    elif spread < 30.0:
        return AnalysisResult(
            category="gradient",
            severity="moderate",
            finding=f"Significant {'linear ' if pattern == 'linear' else ''}gradient detected (spread {spread:.1f}%)",
            recommendation=f"Background extraction with polynomial degree 2-4{cal_note}",
            siril_command=_subsky_cmd(3, info),

            priority=2,

        )
    else:
        return AnalysisResult(
            category="gradient",
            severity="critical",
            finding=f"Severe {'linear ' if pattern == 'linear' else ''}gradient detected (spread {spread:.1f}%)",
            recommendation=f"Background extraction with high degree or use GraXpert{cal_note}",
            siril_command=_subsky_cmd(4, info),

            priority=2,

        )


def analyse_plate_solve(info: ImageInfo) -> Optional[AnalysisResult]:
    """Check plate-solve status (required for SPCC)."""
    # Priority 3: Platesolving
    if info.is_plate_solved:
        return AnalysisResult(
            category="plate_solve",
            severity="info",
            finding="Image is plate-solved (WCS data present)",
            recommendation="No action needed — ready for SPCC",
            siril_command="",
            priority=3,

        )
    else:
        return AnalysisResult(
            category="plate_solve",
            severity="moderate",
            finding="Image is NOT plate-solved",
            recommendation="Plate-solve to enable SPCC",
            siril_command="platesolve",
            priority=3,

        )


def analyse_colour_balance(info: ImageInfo) -> list[AnalysisResult]:
    """Evaluate colour balance for colour images — recommend SPCC.

    On linear uncalibrated data the channel ratios are NOT meaningful for judging
    colour accuracy (OSC Bayer has inherent green dominance, camera white balance
    is arbitrary). We always recommend SPCC for broadband colour images and
    present the raw ratios as factual context only.
    """
    # Priority 4: SPCC (Spectrophotometric Colour Calibration)
    results = []
    if not info.is_color:
        return results

    is_broadband = ("Broadband" in info.image_type or "OSC" in info.image_type) and "Dual" not in info.image_type
    is_narrowband = "Narrowband" in info.image_type
    is_dual_nb = "Dual-Narrowband" in info.image_type

    if is_dual_nb:
        results.append(AnalysisResult(
            category="color",
            severity="info",
            finding="Dual-narrowband OSC — SPCC not applicable (use manual colour balance)",
            recommendation="Manual colour balance for dual-narrowband; consider SHO/HOO palette mapping",
            siril_command="",
            priority=4,

        ))
    elif is_broadband:
        ratio_str = ""
        if info.color_balance_ratios:
            r_ratio, b_ratio = info.color_balance_ratios
            ratio_str = f" (current R/G: {r_ratio:.2f}, B/G: {b_ratio:.2f} — uncalibrated)"

        if info.is_plate_solved:
            results.append(AnalysisResult(
                category="color",
                severity="moderate",
                finding=f"Broadband colour image — SPCC recommended{ratio_str}",
                recommendation="Spectrophotometric Colour Calibration (SPCC)",
                siril_command="spcc",
                priority=4,
    
            ))
        else:
            results.append(AnalysisResult(
                category="color",
                severity="moderate",
                finding=f"Broadband colour image — SPCC recommended (requires plate-solve first){ratio_str}",
                recommendation="Spectrophotometric Colour Calibration (run after plate-solving)",
                siril_command="spcc",
                priority=4,
    
            ))
    elif is_narrowband:
        results.append(AnalysisResult(
            category="color",
            severity="info",
            finding="Narrowband image — SPCC not applicable",
            recommendation="Manual channel weighting for SHO/HOO palette",
            siril_command="",
            priority=4,

        ))

    return results


def analyse_green_noise(info: ImageInfo) -> Optional[AnalysisResult]:
    """Advise on SCNR — must be evaluated visually after SPCC, not before.

    Green excess cannot be reliably detected on uncalibrated linear data because
    OSC sensors have inherent green dominance from the Bayer pattern (2G per RGGB).
    We always recommend checking for green residual AFTER running SPCC.
    """
    # Priority 5: Remove Green (optional, post-SPCC advisory)
    if not info.is_color:
        return None

    is_broadband = ("Broadband" in info.image_type or "OSC" in info.image_type) and "Dual" not in info.image_type
    if is_broadband:
        return AnalysisResult(
            category="green_removal",
            severity="info",
            finding="Check for green residual after SPCC (cannot assess on uncalibrated data)",
            recommendation="After SPCC: inspect image for green cast, apply SCNR if needed",
            siril_command="",
            priority=5,

        )
    return None



def analyse_noise(info: ImageInfo) -> Optional[AnalysisResult]:
    """Evaluate noise level and recommend denoising.

    SNR thresholds are calibrated for MAD-based estimation on normalised 0-1
    linear data (darkest 25%). Typical values:
      - Excellent deep integration (5+ hours): SNR > 10
      - Good integration (2-4 hours):          SNR 5-10
      - Short integration (30min-2h):          SNR 2-5
      - Very short / single sub:               SNR < 2
    """
    # Priority 6: Denoising (before starless, in linear stage)
    snr = info.snr_estimate
    noise_sigma = info.noise_mad

    # Near-zero background with no real content: SNR measures consistency of
    # the zero floor, not signal strength. Only flag when image_suspect is set.
    if info.image_suspect and info.bg_median < 0.005:
        return AnalysisResult(
            category="noise",
            severity="moderate",
            finding=f"SNR {snr:.1f} is misleading — background is near zero "
                    f"({info.bg_median:.4f}) with no significant signal detected",
            recommendation="Cannot reliably assess noise — verify this is the correct stacked file.",
            siril_command="",
            priority=6,

        )

    # Format noise level for display — include integration time when known
    noise_str = f"SNR {snr:.1f}, noise σ={noise_sigma:.5f}"
    if info.livetime > 0:
        if info.livetime >= 3600:
            lt = f"{int(info.livetime // 3600)}h {int((info.livetime % 3600) // 60)}min"
        else:
            lt = f"{int(info.livetime // 60)}min {int(info.livetime % 60)}s"
        noise_str += f", {lt} integration"

    # Integration-aware advice: short integration + low SNR → more subs would help
    # Long integration + low SNR → target is faint, denoising is essential
    integration_hint = ""
    if info.livetime > 0 and snr <= 5:
        if info.livetime < 3600:  # < 1 hour
            integration_hint = " More integration time would improve signal more than aggressive denoising."
        elif info.livetime > 14400:  # > 4 hours
            integration_hint = " Long integration but still noisy — faint target, denoising is essential."

    if snr > 10:
        # If deconvolution will follow (stars detected with measurable FWHM),
        # promote denoise to "minor" so it appears in the workflow — RL amplifies noise.
        will_deconvolve = info.num_stars > 0 and info.mean_fwhm > 0
        return AnalysisResult(
            category="noise",
            severity="minor" if will_deconvolve else "info",
            finding=f"Excellent signal — {noise_str}",
            recommendation="Light denoise before deconvolution (RL amplifies noise)"
                          if will_deconvolve
                          else "Denoising optional — light pass with reduced modulation",
            siril_command="denoise -mod=0.5",
            priority=6,

        )
    elif snr > 5:
        return AnalysisResult(
            category="noise",
            severity="minor",
            finding=f"Good signal — {noise_str}",
            recommendation="Standard denoise in linear stage",
            siril_command="denoise -mod=0.8",
            priority=6,

        )
    elif snr > 2:
        return AnalysisResult(
            category="noise",
            severity="moderate",
            finding=f"Noisy image — {noise_str}",
            recommendation=f"Denoise recommended.{integration_hint}" if integration_hint
                          else "Denoise recommended; consider -vst for photon-starved data",
            siril_command="denoise",
            priority=6,

        )
    else:
        return AnalysisResult(
            category="noise",
            severity="critical",
            finding=f"Very noisy / photon-starved — {noise_str}",
            recommendation=f"Strong denoise with variance stabilisation needed.{integration_hint}"
                          if integration_hint
                          else "Strong denoise with variance stabilisation needed",
            siril_command="denoise -vst",
            priority=6,

        )


def analyse_deconvolution(info: ImageInfo) -> Optional[AnalysisResult]:
    """Recommend deconvolution when SNR and FWHM allow it.

    Richardson-Lucy deconvolution in the linear stage can sharpen detail —
    but only when SNR is sufficient (> 5) and PSF is well-defined.
    RL requires a PSF file (created via makepsf or selected from a star).
    We provide the makepsf + rl commands as a two-step sequence.
    """
    # Priority 7: Deconvolution (after denoise, before starless)
    if info.num_stars == 0 or info.mean_fwhm <= 0:
        return None  # can't estimate PSF without stars

    if info.snr_estimate <= 5:
        return AnalysisResult(
            category="deconvolution",
            severity="info",
            finding=f"SNR too low for deconvolution ({info.snr_estimate:.1f})",
            recommendation="Skip deconvolution — insufficient signal for sharpening",
            siril_command="",
            priority=7,

        )

    # PSF sigma from FWHM: sigma = FWHM / (2 * sqrt(2 * ln(2))) ≈ FWHM / 2.355
    psf_sigma = info.mean_fwhm / 2.355

    if info.snr_estimate > 10:
        return AnalysisResult(
            category="deconvolution",
            severity="minor",
            finding=f"Good candidate for deconvolution (SNR {info.snr_estimate:.1f}, "
                    f"FWHM {info.mean_fwhm:.1f} px, PSF σ≈{psf_sigma:.2f})",
            recommendation="Richardson-Lucy deconvolution — use the GUI deconvolution tool for best control, "
                          "or run the commands below (makepsf saves psf.fits in working dir)",
            siril_command=f"makepsf manual -gaussian -fwhm={info.mean_fwhm:.2f}\n"
                         f"rl -loadpsf=psf.fits -iters=10",
            priority=7,

        )
    else:
        return AnalysisResult(
            category="deconvolution",
            severity="info",
            finding=f"Marginal for deconvolution (SNR {info.snr_estimate:.1f}, "
                    f"FWHM {info.mean_fwhm:.1f} px) — use with caution",
            recommendation="Light deconvolution possible — fewer iterations to avoid amplifying noise. "
                          "Prefer the GUI deconvolution tool for interactive control.",
            siril_command=f"makepsf manual -gaussian -fwhm={info.mean_fwhm:.2f}\n"
                         f"rl -loadpsf=psf.fits -iters=5",
            priority=7,

        )


def analyse_starless(info: ImageInfo) -> Optional[AnalysisResult]:
    """Recommend star removal in linear stage — only when nebulosity is present."""
    # Priority 8: Starless (SyQon) — last step before stretch
    #
    # Starless processing makes sense when there is extended nebulosity that
    # benefits from separate stretching. For pure star fields (globular clusters,
    # open clusters, Milky Way wide-field) it is counterproductive.

    # StarNet needs -stretch when input is linear (so it can internally stretch
    # for detection). On already-stretched data, omit it to avoid double-stretch.
    starnet_cmd = "starnet -stretch" if info.is_linear else "starnet"

    if info.nebulosity_fraction > 0.05:
        # More than 5% of pixels show extended emission — strong nebulosity
        preview_note = ""
        if info.is_linear:
            preview_note = " Tip: preview with 'autostretch' first to verify the image looks right."
        return AnalysisResult(
            category="starless",
            severity="moderate",
            finding=f"Significant nebulosity detected ({info.nebulosity_fraction * 100:.1f}% "
                    f"of pixels above background) — starless processing recommended",
            recommendation=f"Generate starless version (StarNet or SyQon) before stretching.{preview_note}",
            siril_command=starnet_cmd,
            priority=8,

        )
    elif info.nebulosity_fraction > 0.01:
        # 1-5%: some nebulosity, suggest it as optional
        return AnalysisResult(
            category="starless",
            severity="minor",
            finding=f"Some nebulosity detected ({info.nebulosity_fraction * 100:.1f}% "
                    f"of pixels above background) — starless processing optional",
            recommendation="Starless processing optional (StarNet or SyQon)",
            siril_command="",
            priority=8,

        )
    else:
        # Star field / no significant nebulosity
        return AnalysisResult(
            category="starless",
            severity="info",
            finding=f"Minimal nebulosity ({info.nebulosity_fraction * 100:.1f}% above "
                    f"background) — starless processing not needed",
            recommendation="Star field — process with stars, no starless extraction needed",
            siril_command="",
            priority=8,

        )


def analyse_stars(info: ImageInfo) -> list[AnalysisResult]:
    """Evaluate star quality (FWHM, elongation) — informational diagnostics."""
    results = []
    if info.num_stars == 0:
        if info.star_error:
            results.append(AnalysisResult(
                category="stars",
                severity="moderate",
                finding=f"Star detection failed — {info.star_error}",
                recommendation="Star analysis unavailable. Try running 'findstar' "
                               "manually in Siril to diagnose the issue",
                siril_command="",
                priority=90,
    
            ))
        else:
            results.append(AnalysisResult(
                category="stars",
                severity="info",
                finding="No stars detected",
                recommendation="Check image — may be blank, heavily cropped, or non-stellar field",
                siril_command="",
                priority=90,
    
            ))
        return results

    # FWHM assessment
    fwhm_arcsec = ""
    if info.arcsec_per_pixel > 0:
        arcsec = info.mean_fwhm * info.arcsec_per_pixel
        fwhm_arcsec = f" ({arcsec:.1f}\")"

    # Scale-aware FWHM thresholds (arcsec when available, pixels as fallback)
    if info.arcsec_per_pixel > 0:
        fwhm_arcsec_val = info.mean_fwhm * info.arcsec_per_pixel
        if fwhm_arcsec_val > 6.0:
            fwhm_sev = "moderate"
            fwhm_verdict = "Very soft stars"
            fwhm_rec = "Severe focus/seeing issue — check optics and guiding"
        elif fwhm_arcsec_val > 4.0:
            fwhm_sev = "moderate"
            fwhm_verdict = "Soft stars"
            fwhm_rec = "Soft stars detected — check focus, seeing, or guiding"
        elif fwhm_arcsec_val > 2.0:
            fwhm_sev = "info"
            fwhm_verdict = "Good star quality"
            fwhm_rec = ""
        else:
            fwhm_sev = "info"
            fwhm_verdict = "Excellent star quality"
            fwhm_rec = ""
    else:
        # Pixel-only fallback
        if info.mean_fwhm > 5.0:
            fwhm_sev = "moderate"
            fwhm_verdict = "Soft stars"
            fwhm_rec = "Soft stars detected — check focus and optics"
        else:
            fwhm_sev = "info"
            fwhm_verdict = "Good star quality"
            fwhm_rec = ""

    # Soft/very soft stars are an acquisition issue — show them early (priority 0)
    # so the user sees the warning before investing time in the processing workflow.
    # Good/excellent stars stay at priority 90 as informational diagnostics.
    fwhm_priority = 0 if fwhm_sev == "moderate" else 90

    results.append(AnalysisResult(
        category="stars_fwhm",
        severity=fwhm_sev,
        finding=f"{fwhm_verdict} — FWHM {info.mean_fwhm:.1f} px{fwhm_arcsec}, "
                f"elongation {info.mean_elongation:.2f}",
        recommendation=fwhm_rec,
        siril_command="",
        priority=fwhm_priority,
    ))

    # Elongation — acquisition issue, show early (priority 0)
    if info.mean_elongation > 1.3:
        if info.elongation_spatial_issue:
            results.append(AnalysisResult(
                category="stars_elongation",
                severity="moderate",
                finding=f"Elongated stars at edges (elongation {info.mean_elongation:.2f}) "
                        "— likely optical aberration (coma/tilt)",
                recommendation="Not correctable in processing — check optics/spacing",
                siril_command="",
                priority=0,
    
            ))
        else:
            results.append(AnalysisResult(
                category="stars_elongation",
                severity="moderate",
                finding=f"Elongated stars across field (elongation {info.mean_elongation:.2f}) "
                        "— likely tracking/guiding issue",
                recommendation="Not correctable in processing — check mount/guiding",
                siril_command="",
                priority=0,
    
            ))

    # Spatial FWHM variation
    if info.fwhm_centre > 0 and info.fwhm_edge > 0:
        ratio = info.fwhm_edge / info.fwhm_centre
        if ratio > 1.5:
            results.append(AnalysisResult(
                category="stars_field",
                severity="moderate",
                finding=f"Field curvature/coma detected — edge FWHM {info.fwhm_edge:.1f} px "
                        f"vs centre {info.fwhm_centre:.1f} px (ratio {ratio:.2f}×)",
                recommendation="Check optical train / flattener",
                siril_command="",
                priority=90,
    
            ))

    # Saturated stars
    if info.saturated_stars > 0:
        sat_pct = info.saturated_stars / info.num_stars * 100.0
        sev = "moderate" if sat_pct > 5.0 else "minor"
        results.append(AnalysisResult(
            category="stars_saturated",
            severity=sev,
            finding=f"{info.saturated_stars} of {info.num_stars} stars have saturated cores "
                    f"({sat_pct:.1f}%)",
            recommendation="Consider shorter sub-exposures or HDR merge for bright stars",
            siril_command="",
            priority=90,

        ))

    # Star count info
    results.append(AnalysisResult(
        category="stars_count",
        severity="info",
        finding=f"{info.num_stars} stars detected",
        recommendation="",
        siril_command="",
        priority=99,
    ))

    return results



def get_postprocessing_roadmap(info: ImageInfo) -> list[dict]:
    """
    Return the post-processing roadmap (non-linear stage) as a list of dicts.

    These are not analysis results — they are fixed workflow steps that always
    follow after stretching. They are displayed in a separate section in the
    report, not mixed into the findings.
    """
    roadmap = [
        {
            "step": "Stretching",
            "tool": "VeraLux HMS",
            "phase": "transition",
            "note": _stretch_note(info),
        },
        {
            "step": "Fine-tuning",
            "tool": "Revela / Curves / Vectra",
            "phase": "nonlinear",
            "note": "Adjust contrast, colour saturation, local detail",
        },
    ]

    # Only include StarComposer if starless processing was recommended
    if info.nebulosity_fraction > 0.05:
        roadmap.append({
            "step": "Star Recomposition",
            "tool": "StarComposer",
            "phase": "nonlinear",
            "note": "Recompose stars onto processed starless image",
        })

    roadmap.append({
        "step": "Signature & Export",
        "tool": "Siril / external editor",
        "phase": "nonlinear",
        "note": "Add signature, export final TIFF/PNG/JPEG",
    })

    return roadmap


def _stretch_note(info: ImageInfo) -> str:
    """Generate a stretch recommendation note based on usable dynamic range and background level."""
    stops = info.dynamic_range_stops

    # High background pedestal (>10% of full range) means the image needs careful
    # black point adjustment during stretching — otherwise the background will appear
    # washed out grey instead of dark sky.
    bg_warning = ""
    if info.bg_median > 0.15:
        bg_warning = f" Background is high ({info.bg_median:.1%} of full range) — set black point carefully to avoid washed-out sky."
    elif info.bg_median > 0.08:
        bg_warning = f" Elevated background ({info.bg_median:.1%}) — watch the black point during stretching."

    if stops < 4:
        return f"Narrow dynamic range ({stops:.1f} stops) — use aggressive stretch settings.{bg_warning}"
    elif stops < 10:
        return f"Good dynamic range ({stops:.1f} stops) — moderate stretch settings.{bg_warning}"
    else:
        return f"Wide dynamic range ({stops:.1f} stops) — careful with highlights, avoid clipping bright stars.{bg_warning}"


def analyse_clipping(info: ImageInfo) -> list[AnalysisResult]:
    """Check for black/white clipping."""
    results = []
    if info.clip_black_pct > 50.0:
        # High percentage of pixels near zero. On linear data this is NORMAL —
        # the background sits near zero and most pixels are background.
        # Only flag as suspect when the image also lacks evidence of real content:
        # no stars detected, and very low dynamic range (peak barely above noise).
        has_content = info.num_stars > 10 or info.dynamic_range_ratio > 3.0 or info.nebulosity_fraction > 0.02

        if not has_content:
            # Genuinely empty/broken — no stars, no signal variation
            info.image_suspect = True
            results.append(AnalysisResult(
                category="WARNING",
                severity="critical",
                finding=f"Extreme black clipping: {info.clip_black_pct:.1f}% of pixels are near zero "
                        "with no significant signal detected",
                recommendation="This does not look like a normal stacked astronomical image. "
                              "Possible causes: image is a screenshot or phone photo, "
                              "a heavily masked/cropped export, or the stacking produced mostly empty frame. "
                              "Processing recommendations have been suppressed.",
                siril_command="",
                priority=-1,
    
            ))
        else:
            # Linear data with real content — background near zero is expected
            results.append(AnalysisResult(
                category="clipping",
                severity="info",
                finding=f"{info.clip_black_pct:.0f}% of pixels near zero — normal for linear data "
                        "(background sits near zero before stretching)",
                recommendation="",
                siril_command="",
                priority=0,
    
            ))
    elif info.clip_black_pct > 1.0:
        results.append(AnalysisResult(
            category="clipping",
            severity="moderate" if info.clip_black_pct > 5.0 else "minor",
            finding=f"Black clipping: {info.clip_black_pct:.1f}% of pixels near zero",
            recommendation="Check stacking settings — aggressive rejection or dark subtraction issue?",
            siril_command="",
            priority=0,

        ))
    if info.clip_white_pct > 0.1:
        results.append(AnalysisResult(
            category="clipping",
            severity="moderate" if info.clip_white_pct > 1.0 else "minor",
            finding=f"White clipping: {info.clip_white_pct:.2f}% of pixels saturated",
            recommendation="Saturated cores — consider shorter sub-exposures or HDR merge",
            siril_command="",
            priority=0,

        ))
    return results


# ------------------------------------------------------------------------------
# WORKFLOW BUILDER (Phase 3)
#
# Follows the exact workflow path:
#   LINEAR:      Crop → Background Extraction → Platesolving → SPCC →
#                Remove Green → Denoising → Deconvolution → Starless (SyQon)
#   TRANSITION:  Stretching (VeraLux HMS)
#   NON-LINEAR:  Fine-tuning (Revela/Curves/Vectra) → StarComposer → Signature
# ------------------------------------------------------------------------------

def _check_image_dimensions(info: ImageInfo) -> Optional[AnalysisResult]:
    """Flag non-astronomical image dimensions (phone, screenshot, standard video).

    This is a hint, not a hard block — some astro cameras and binning modes do
    produce standard resolutions. Only shown as informational context.
    """
    w, h = info.width, info.height
    # Common non-astro resolutions (either orientation)
    phone_video = {
        (1080, 1920), (1920, 1080),  # 1080p / phone
        (750, 1334), (1334, 750),    # iPhone 6/7/8
        (1170, 2532), (2532, 1170),  # iPhone 12/13/14
        (1284, 2778), (2778, 1284),  # iPhone 12/13/14 Pro Max
        (1440, 2560), (2560, 1440),  # QHD phone
        (720, 1280), (1280, 720),    # 720p
        (3840, 2160), (2160, 3840),  # 4K UHD
        (2560, 1440), (1440, 2560),  # 1440p
    }
    if (w, h) in phone_video:
        return AnalysisResult(
            category="image_info",
            severity="info",
            finding=f"Image dimensions {w}×{h} match a common phone/screen resolution — "
                    "unusual for an astronomical camera sensor",
            recommendation="If this is not a stacked astro image, the analysis below "
                          "may not be meaningful.",
            siril_command="",
            priority=-1,

        )
    return None


def build_workflow(info: ImageInfo) -> list[AnalysisResult]:
    """Run all analysis modules and build prioritised workflow."""
    results: list[AnalysisResult] = []

    # Critical pre-checks (priority -1)
    dim_check = _check_image_dimensions(info)
    if dim_check:
        results.append(dim_check)
    linear_check = analyse_linear_state(info)
    if linear_check:
        results.append(linear_check)
    results.extend(analyse_calibration(info))

    # Pre-checks (priority 0)
    results.extend(analyse_clipping(info))

    # If image failed sanity checks, skip processing recommendations —
    # they would be based on misleading statistics and confuse the user.
    if info.image_suspect:
        # Still include crop analysis (user may need to crop the black region)
        crop = analyse_cropping(info)
        if crop:
            results.append(crop)
        # Add a summary note explaining why the workflow is suppressed
        results.append(AnalysisResult(
            category="workflow",
            severity="info",
            finding="Processing workflow suppressed — image failed basic sanity checks (see warnings above)",
            recommendation="Load the correct stacked linear FITS file and re-analyse.",
            siril_command="",
            priority=99,

        ))
        results.sort(key=lambda r: (r.priority, {"critical": 0, "moderate": 1, "minor": 2, "info": 3}.get(r.severity, 4)))
        return results

    # LINEAR STAGE — in exact workflow order
    # Step 1: Cropping (priority 1)
    crop = analyse_cropping(info)
    if crop:
        results.append(crop)

    # Step 2: Background Extraction (priority 2)
    grad = analyse_gradient(info)
    if grad:
        results.append(grad)

    # Step 3: Platesolving (priority 3)
    ps = analyse_plate_solve(info)
    if ps:
        results.append(ps)

    # Step 4: SPCC (priority 4)
    results.extend(analyse_colour_balance(info))

    # Step 5: Remove Green / SCNR (priority 5)
    green = analyse_green_noise(info)
    if green:
        results.append(green)

    # Step 6: Denoising (priority 6)
    noise = analyse_noise(info)
    if noise:
        results.append(noise)

    # Step 7: Deconvolution (priority 7)
    deconv = analyse_deconvolution(info)
    if deconv:
        results.append(deconv)

    # Step 8: Starless — SyQon (priority 8)
    starless = analyse_starless(info)
    if starless:
        results.append(starless)

    # DIAGNOSTIC INFO — star quality (priority 90+, informational)
    results.extend(analyse_stars(info))

    # Sort by priority, then severity
    severity_order = {"critical": 0, "moderate": 1, "minor": 2, "info": 3}
    results.sort(key=lambda r: (r.priority, severity_order.get(r.severity, 4)))

    return results


def generate_script(results: list[AnalysisResult]) -> str:
    """Generate an executable Siril script from the workflow with save checkpoints."""
    lines = [
        "# Auto-generated by Image Advisor",
        "# WARNING: This script operates on whatever image is currently loaded in Siril.",
        "# Make sure the correct stacked linear image is loaded before running.",
        "requires 1.4.1",
        "",
    ]
    # Categories after which we insert a save checkpoint
    checkpoint_categories = {"crop", "gradient", "color", "noise"}
    step = 0
    for r in results:
        if r.siril_command and r.severity != "info":
            step += 1
            cmds = [c.strip() for c in r.siril_command.split("\n") if c.strip()]
            if cmds:
                lines.append(f"# Step {step}: {r.recommendation}")
                for cmd in cmds:
                    lines.append(cmd)
                # Save checkpoint after key stages
                if r.category in checkpoint_categories:
                    checkpoint_name = f"checkpoint_{r.category}"
                    lines.append(f"save {checkpoint_name}")
                    lines.append(f"# Checkpoint saved: {checkpoint_name}")
                lines.append("")
    lines.append("save result_processed")
    lines.append("# Processing complete.")
    return "\n".join(lines)


# ------------------------------------------------------------------------------
# REPORT FORMATTING
# ------------------------------------------------------------------------------

def format_report_text(info: ImageInfo, results: list[AnalysisResult]) -> str:
    """Format the full analysis report as plain text."""
    lines = []
    sep = "=" * 55
    thin = "-" * 55

    lines.append(sep)
    lines.append("  IMAGE ADVISOR — Analysis Report")
    lines.append(sep)
    lines.append("")

    # Image summary
    lines.append(f"  Type:         {info.image_type}")
    lines.append(f"  Size:         {info.width} x {info.height} px")
    if info.channels >= 3:
        lines.append(f"  Channels:     3 (RGB)")
    else:
        lines.append(f"  Channels:     1 (Mono)")
    if info.stack_count > 0:
        lines.append(f"  Stack:        {info.stack_count} frames")
    if info.exposure > 0:
        if info.exposure >= 3600:
            hours = int(info.exposure // 3600)
            mins = int((info.exposure % 3600) // 60)
            lines.append(f"  Exposure:     {hours}h {mins}min total")
        elif info.exposure >= 60:
            mins = int(info.exposure // 60)
            secs = int(info.exposure % 60)
            lines.append(f"  Exposure:     {mins}min {secs}s total")
        else:
            lines.append(f"  Exposure:     {info.exposure:.1f}s")
    if info.arcsec_per_pixel > 0:
        lines.append(f"  Resolution:   {info.arcsec_per_pixel:.2f}\"/px")
    lines.append(f"  Plate-Solve:  {'Yes' if info.is_plate_solved else 'No'}")
    if info.filter_name:
        lines.append(f"  Filter:       {info.filter_name}")
    lines.append("")

    # Key statistics
    lines.append(thin)
    lines.append("  KEY STATISTICS")
    lines.append(thin)
    lines.append("")
    lines.append(f"  SNR (MAD):     {info.snr_estimate:.1f}")
    lines.append(f"  Noise (sigma): {info.noise_mad:.6f}")
    lines.append(f"  Gradient:      {info.gradient_spread:.1f}%")
    lines.append(f"  Dynamic Range: {info.dynamic_range_stops:.1f} stops (peak / noise floor)")
    lines.append(f"  Nebulosity:    {info.nebulosity_fraction * 100:.1f}%")
    if info.num_stars > 0:
        lines.append(f"  Stars:         {info.num_stars}")
        lines.append(f"  FWHM:          {info.mean_fwhm:.1f} px")
        lines.append(f"  Elongation:    {info.mean_elongation:.2f}")
        if info.saturated_stars > 0:
            lines.append(f"  Saturated:     {info.saturated_stars} "
                         f"({info.saturated_stars / info.num_stars * 100:.1f}%)")
    elif info.star_error:
        lines.append(f"  Stars:         {info.star_error}")
    lines.append("")

    # Processing State
    lines.append(thin)
    lines.append("  PROCESSING STATE")
    lines.append(thin)
    lines.append("")
    lines.append(f"  Linear:       {'Yes' if info.is_linear else 'NO — STRETCHED'}")
    if not info.is_linear:
        lines.append(f"  Stretch:      {'; '.join(info.stretch_history[:3])}")
    if info.has_history:
        cal_str = []
        cal_str.append(f"Darks:{'Y' if info.has_darks else 'N'}")
        cal_str.append(f"Flats:{'Y' if info.has_flats else 'N'}")
        cal_str.append(f"Bias:{'Y' if info.has_biases else 'N'}")
        lines.append(f"  Calibration:  {' '.join(cal_str)}")
    else:
        lines.append("  Calibration:  Unknown (no processing history)")
    if info.livetime > 0 and info.exposure_per_sub > 0 and info.livetime != info.exposure_per_sub:
        lines.append(f"  Per-Sub:      {info.exposure_per_sub:.1f}s")
        if info.livetime >= 3600:
            lt_str = f"{int(info.livetime // 3600)}h {int((info.livetime % 3600) // 60)}min"
        else:
            lt_str = f"{int(info.livetime // 60)}min {int(info.livetime % 60)}s"
        lines.append(f"  Integration:  {lt_str}")
    lines.append("")

    # Per-channel noise (colour images)
    if info.is_color and len(info.channel_noise) >= 3:
        lines.append(thin)
        lines.append("  PER-CHANNEL NOISE")
        lines.append(thin)
        lines.append("")
        ch_names = ["Red", "Green", "Blue"]
        min_noise = min(info.channel_noise[:3])
        for i, name in enumerate(ch_names):
            med = info.channel_medians[i] if i < len(info.channel_medians) else 0
            noise = info.channel_noise[i]
            rel = noise / min_noise if min_noise > 1e-10 else 0
            marker = " (noisiest)" if rel > 1.3 else ""
            lines.append(f"  {name:6s}  median={med:.5f}  σ={noise:.6f}  {rel:.2f}x{marker}")
        if len(info.channel_medians) >= 3:
            meds = info.channel_medians[:3]
            max_med = max(meds)
            min_med = min(meds)
            if max_med > 1e-10 and (max_med - min_med) / max_med < 0.05:
                lines.append("  Channels well-balanced (within 5%) — may already be colour-calibrated")
        lines.append("")

    # Findings
    lines.append(thin)
    lines.append("  FINDINGS")
    lines.append(thin)
    lines.append("")
    for r in results:
        icon = SEVERITY_ICONS.get(r.severity, " ")
        lines.append(f"  [{icon}] {r.category.upper():16s} {r.finding}")
    lines.append("")

    # Workflow — linear stage
    actionable = [r for r in results if r.siril_command and r.severity != "info"]
    if actionable:
        lines.append(thin)
        lines.append("  RECOMMENDED WORKFLOW — LINEAR STAGE")
        lines.append(thin)
        lines.append("")
        for i, r in enumerate(actionable, 1):
            lines.append(f"  Step {i:2d} | {r.recommendation}")
            cmd_lines = r.siril_command.split("\n")
            lines.append(f"          | Command:  {cmd_lines[0]}")
            for extra_cmd in cmd_lines[1:]:
                lines.append(f"          |           {extra_cmd}")
            lines.append(f"          | Reason:   {r.finding}")
            lines.append("")

    # Post-Processing Roadmap
    roadmap = get_postprocessing_roadmap(info)
    lines.append(thin)
    lines.append("  POST-PROCESSING ROADMAP")
    lines.append(thin)
    lines.append("")
    step_offset = len(actionable) if actionable else 0
    for i, rm in enumerate(roadmap, 1):
        lines.append(f"  Step {step_offset + i:2d} | [{rm['phase'].upper()}] {rm['step']}")
        lines.append(f"          | Tool: {rm['tool']}")
        lines.append(f"          | {rm['note']}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def format_report_html(info: ImageInfo, results: list[AnalysisResult]) -> str:
    """Format the analysis report as styled HTML for the GUI."""
    html = []
    html.append("<div style='font-family: Menlo, Courier New; color: #e0e0e0;'>")

    # Title
    html.append("<h2 style='color: #88aaff; margin-bottom: 4px;'>Image Advisor — Analysis Report</h2>")
    html.append("<hr style='border-color: #555;'>")

    _row = lambda k, v: f"<tr><td style='color: #999; padding-right: 16px;'>{k}</td><td>{v}</td></tr>"

    # Image summary
    html.append("<h3 style='color: #88aaff;'>Image Summary</h3>")
    html.append("<table style='margin-left: 10px; border-collapse: collapse;'>")
    html.append(_row("Type", info.image_type))
    html.append(_row("Size", f"{info.width} × {info.height} px"))
    html.append(_row("Channels", "3 (RGB)" if info.is_color else "1 (Mono)"))
    if info.stack_count > 0:
        html.append(_row("Stack", f"{info.stack_count} frames"))
    if info.exposure > 0:
        if info.exposure >= 3600:
            exp_str = f"{int(info.exposure // 3600)}h {int((info.exposure % 3600) // 60)}min"
        elif info.exposure >= 60:
            exp_str = f"{int(info.exposure // 60)}min {int(info.exposure % 60)}s"
        else:
            exp_str = f"{info.exposure:.1f}s"
        html.append(_row("Exposure", exp_str))
    if info.arcsec_per_pixel > 0:
        html.append(_row("Resolution", f"{info.arcsec_per_pixel:.2f}\"/px"))
    html.append(_row("Plate-Solve", "Yes" if info.is_plate_solved else "No"))
    if info.filter_name:
        html.append(_row("Filter", info.filter_name))
    html.append("</table>")

    # Key Statistics
    html.append("<h3 style='color: #88aaff;'>Key Statistics</h3>")
    html.append("<table style='margin-left: 10px; border-collapse: collapse;'>")
    html.append(_row("SNR Estimate (MAD)", f"{info.snr_estimate:.1f}"))
    html.append(_row("Background Noise (σ)", f"{info.noise_mad:.6f}"))
    html.append(_row("Gradient Spread", f"{info.gradient_spread:.1f}%"))
    html.append(_row("Dynamic Range", f"{info.dynamic_range_stops:.1f} stops (peak / noise floor)"))
    html.append(_row("Nebulosity", f"{info.nebulosity_fraction * 100:.1f}%"))
    if info.num_stars > 0:
        html.append(_row("Stars Detected", str(info.num_stars)))
        fwhm_str = f"{info.mean_fwhm:.1f} px"
        if info.arcsec_per_pixel > 0:
            fwhm_str += f" ({info.mean_fwhm * info.arcsec_per_pixel:.1f}\")"
        html.append(_row("Mean FWHM", fwhm_str))
        html.append(_row("Mean Elongation", f"{info.mean_elongation:.2f}"))
        if info.saturated_stars > 0:
            html.append(_row("Saturated Stars",
                             f"<span style='color: #dd5555;'>{info.saturated_stars} "
                             f"({info.saturated_stars / info.num_stars * 100:.1f}%)</span>"))
    elif info.star_error:
        html.append(_row("Stars", f"<span style='color: #dd5555;'>{info.star_error}</span>"))
    if info.clip_black_pct > 0.1:
        html.append(_row("Black Clipping", f"{info.clip_black_pct:.1f}%"))
    if info.clip_white_pct > 0.01:
        html.append(_row("White Clipping", f"{info.clip_white_pct:.2f}%"))
    if info.is_color and info.color_balance_ratios:
        html.append(_row("Colour R/G (raw)", f"{info.color_balance_ratios[0]:.3f}"))
        html.append(_row("Colour B/G (raw)", f"{info.color_balance_ratios[1]:.3f}"))
    if info.needs_cropping:
        borders = []
        if info.crop_top > 0:
            borders.append(f"T:{info.crop_top}")
        if info.crop_bottom > 0:
            borders.append(f"B:{info.crop_bottom}")
        if info.crop_left > 0:
            borders.append(f"L:{info.crop_left}")
        if info.crop_right > 0:
            borders.append(f"R:{info.crop_right}")
        html.append(_row("Stacking Borders", " ".join(borders) + " px"))
    html.append("</table>")

    # Processing State & Calibration
    html.append("<h3 style='color: #88aaff;'>Processing State</h3>")
    html.append("<table style='margin-left: 10px; border-collapse: collapse;'>")
    if info.is_linear:
        html.append(_row("Linear State", "<span style='color: #88cc88;'>Linear (good)</span>"))
    else:
        html.append(_row("Linear State",
                         f"<span style='color: #dd5555; font-weight: bold;'>STRETCHED — "
                         f"{'; '.join(info.stretch_history[:3])}</span>"))
    if info.has_history:
        cal_parts = []
        if info.has_darks:
            cal_parts.append("<span style='color: #88cc88;'>Darks ✓</span>")
        else:
            cal_parts.append("<span style='color: #dd8844;'>Darks ✗</span>")
        if info.has_flats:
            cal_parts.append("<span style='color: #88cc88;'>Flats ✓</span>")
        else:
            cal_parts.append("<span style='color: #dd8844;'>Flats ✗</span>")
        if info.has_biases:
            cal_parts.append("<span style='color: #88cc88;'>Bias ✓</span>")
        else:
            cal_parts.append("<span style='color: #dd8844;'>Bias ✗</span>")
        html.append(_row("Calibration", "  ".join(cal_parts)))
    else:
        html.append(_row("Calibration",
                         "<span style='color: #999;'>Unknown (no processing history)</span>"))
    if info.livetime > 0 and info.exposure_per_sub > 0 and info.livetime != info.exposure_per_sub:
        html.append(_row("Per-Sub Exposure", f"{info.exposure_per_sub:.1f}s"))
        if info.livetime >= 3600:
            lt_str = f"{int(info.livetime // 3600)}h {int((info.livetime % 3600) // 60)}min"
        else:
            lt_str = f"{int(info.livetime // 60)}min {int(info.livetime % 60)}s"
        html.append(_row("Total Integration", lt_str))
    html.append("</table>")

    # Per-channel statistics (colour images)
    if info.is_color and len(info.channel_noise) >= 3:
        html.append("<h3 style='color: #88aaff;'>Per-Channel Statistics</h3>")
        html.append("<table style='margin-left: 10px; border-collapse: collapse;'>")
        html.append(
            "<tr style='border-bottom: 1px solid #555;'>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Channel</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Median</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Noise (σ)</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Relative</th>"
            "</tr>"
        )
        ch_names = ["Red", "Green", "Blue"]
        ch_colors = ["#ff6666", "#66ff66", "#6688ff"]
        min_noise = min(info.channel_noise[:3]) if info.channel_noise else 1.0
        for i, (name, color) in enumerate(zip(ch_names, ch_colors)):
            med = info.channel_medians[i] if i < len(info.channel_medians) else 0
            noise = info.channel_noise[i] if i < len(info.channel_noise) else 0
            rel = noise / min_noise if min_noise > 1e-10 else 0
            # Highlight the noisiest channel
            noise_style = " font-weight: bold;" if rel > 1.3 else ""
            html.append(
                f"<tr><td style='color: {color}; padding: 4px;'>{name}</td>"
                f"<td style='padding: 4px;'>{med:.5f}</td>"
                f"<td style='padding: 4px;{noise_style}'>{noise:.6f}</td>"
                f"<td style='padding: 4px;{noise_style}'>{rel:.2f}×</td></tr>"
            )
        html.append("</table>")
        # Note when channels are unusually well-balanced (within 5%) — this is
        # noteworthy because uncalibrated OSC typically has green dominance.
        if len(info.channel_medians) >= 3:
            meds = info.channel_medians[:3]
            max_med = max(meds)
            min_med = min(meds)
            if max_med > 1e-10 and (max_med - min_med) / max_med < 0.05:
                html.append("<p style='margin: 4px 10px; color: #88cc88; font-size: 9pt;'>"
                           "Channels are well-balanced (within 5%) — "
                           "unusual for uncalibrated OSC data; may already be colour-calibrated.</p>")

    # Background tile heatmap (8×8 grid of background levels)
    if info.gradient_tile_medians and len(info.gradient_tile_medians) == TILE_GRID * TILE_GRID:
        html.append("<h3 style='color: #88aaff;'>Background Heatmap (8×8 tile medians)</h3>")
        html.append("<p style='margin-left: 10px; color: #999; font-size: 9pt;'>"
                     "Bright = higher background. Reveals gradient direction, vignetting, amp glow.</p>")
        tile_min = min(info.gradient_tile_medians)
        tile_max = max(info.gradient_tile_medians)
        tile_range = tile_max - tile_min if tile_max > tile_min else 1e-10
        html.append("<table style='margin-left: 10px; border-collapse: collapse;'>")
        for row in range(TILE_GRID):
            html.append("<tr>")
            for col in range(TILE_GRID):
                val = info.gradient_tile_medians[row * TILE_GRID + col]
                # Map to 0-255 intensity for background colour
                intensity = int(((val - tile_min) / tile_range) * 200 + 30)
                intensity = max(30, min(230, intensity))
                # Text colour: dark on bright, bright on dark
                text_col = "#000" if intensity > 140 else "#ddd"
                html.append(
                    f"<td style='width: 42px; height: 28px; text-align: center; "
                    f"font-size: 7pt; color: {text_col}; "
                    f"background-color: rgb({intensity},{intensity},{int(intensity * 0.85)});'>"
                    f"{val:.4f}</td>"
                )
            html.append("</tr>")
        html.append("</table>")
        if info.gradient_pattern:
            pattern_labels = {
                "vignetting": "Vignetting (corners dark, centre bright — needs flats)",
                "linear": "Linear gradient (one side bright — light pollution, use subsky)",
                "corner": "Amp glow (single corner bright — consider masking)",
            }
            label = pattern_labels.get(info.gradient_pattern, info.gradient_pattern)
            html.append(f"<p style='margin: 4px 10px; color: #ddaa55; font-size: 9pt;'>"
                        f"Pattern: {label}</p>")

    # Findings
    html.append("<h3 style='color: #88aaff;'>Findings</h3>")
    for r in results:
        col = SEVERITY_COLORS.get(r.severity, "#cccccc")
        icon = SEVERITY_ICONS.get(r.severity, " ")
        html.append(
            f"<p style='margin: 3px 10px;'>"
            f"<span style='color: {col}; font-weight: bold;'>[{icon}]</span> "
            f"<span style='color: #aaa;'>{r.category.upper()}</span> &mdash; "
            f"{r.finding}</p>"
        )

    # Recommended Workflow (linear stage — actionable commands)
    actionable = [r for r in results if r.siril_command and r.severity != "info"]
    if actionable:
        html.append("<h3 style='color: #88aaff;'>Recommended Workflow — Linear Stage</h3>")
        html.append("<table style='margin-left: 10px; border-collapse: collapse; width: 95%;'>")
        html.append(
            "<tr style='border-bottom: 1px solid #555;'>"
            "<th style='text-align: left; color: #888; padding: 4px;'>#</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Step</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Command</th>"
            "<th style='text-align: left; color: #888; padding: 4px;'>Reason</th>"
            "</tr>"
        )
        for i, r in enumerate(actionable, 1):
            html.append(
                f"<tr style='border-bottom: 1px solid #3a3a3a;'>"
                f"<td style='padding: 4px 8px; color: #88aaff; font-weight: bold;'>{i}</td>"
                f"<td style='padding: 4px 8px;'>{r.recommendation}</td>"
                f"<td style='padding: 4px 8px; color: #ffcc66; font-family: Menlo, Courier New;'>"
                f"{r.siril_command.replace(chr(10), '<br>')}</td>"
                f"<td style='padding: 4px 8px; color: #999; font-size: 9pt;'>{r.finding}</td>"
                f"</tr>"
            )
        html.append("</table>")

    # Post-Processing Roadmap (stretching + non-linear — always shown)
    roadmap = get_postprocessing_roadmap(info)
    html.append("<h3 style='color: #88aaff;'>Post-Processing Roadmap</h3>")
    html.append("<table style='margin-left: 10px; border-collapse: collapse; width: 95%;'>")
    html.append(
        "<tr style='border-bottom: 1px solid #555;'>"
        "<th style='text-align: left; color: #888; padding: 4px;'>#</th>"
        "<th style='text-align: left; color: #888; padding: 4px;'>Phase</th>"
        "<th style='text-align: left; color: #888; padding: 4px;'>Step</th>"
        "<th style='text-align: left; color: #888; padding: 4px;'>Tool</th>"
        "<th style='text-align: left; color: #888; padding: 4px;'>Note</th>"
        "</tr>"
    )
    step_offset = len(actionable)
    for i, rm in enumerate(roadmap, 1):
        phase_col = "#dd8844" if rm["phase"] == "transition" else "#cc88dd"
        html.append(
            f"<tr style='border-bottom: 1px solid #3a3a3a;'>"
            f"<td style='padding: 4px 8px; color: #88aaff; font-weight: bold;'>{step_offset + i}</td>"
            f"<td style='padding: 4px 8px; color: {phase_col};'>{rm['phase'].upper()}</td>"
            f"<td style='padding: 4px 8px;'>{rm['step']}</td>"
            f"<td style='padding: 4px 8px; color: #ffcc66;'>{rm['tool']}</td>"
            f"<td style='padding: 4px 8px; color: #999; font-size: 9pt;'>{rm['note']}</td>"
            f"</tr>"
        )
    html.append("</table>")

    html.append("</div>")
    return "\n".join(html)


# ------------------------------------------------------------------------------
# GUI
# ------------------------------------------------------------------------------

class ImageAdvisorWindow(QMainWindow):
    """
    Main window for the Image Advisor.

    Displays analysis report with findings and recommended workflow, supports
    exporting the report or a generated Siril script.
    """

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self.info: Optional[ImageInfo] = None
        self.results: list[AnalysisResult] = []
        self.init_ui()
        QTimer.singleShot(200, self._run_analysis)

    def init_ui(self) -> None:
        """Build the UI layout."""
        self.setWindowTitle(f"Siril Image Advisor {VERSION}")
        self.setStyleSheet(DARK_STYLESHEET)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Left panel
        left = self._build_left_panel()
        main_layout.addWidget(left)

        # Right panel: report area
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setHtml(
            "<div style='color: #888; font-size: 14pt; padding: 40px; text-align: center;'>"
            "Analysing image... please wait.</div>"
        )
        right_layout.addWidget(self.report_view)

        main_layout.addWidget(right, stretch=1)

    def _build_left_panel(self) -> QWidget:
        """Build the left control panel."""
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        lbl = QLabel(f"Image Advisor {VERSION}")
        lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        # Status group
        grp_status = QGroupBox("Status")
        status_layout = QVBoxLayout(grp_status)
        self.lbl_status = QLabel("Initialising...")
        self.lbl_status.setWordWrap(True)
        status_layout.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        status_layout.addWidget(self.progress)
        layout.addWidget(grp_status)

        # Image info group (populated after analysis)
        grp_info = QGroupBox("Image Info")
        info_layout = QVBoxLayout(grp_info)
        self.lbl_info = QLabel("—")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("font-size: 9pt;")
        info_layout.addWidget(self.lbl_info)
        layout.addWidget(grp_info)

        # Actions group
        grp_actions = QGroupBox("Actions")
        actions_layout = QVBoxLayout(grp_actions)

        btn_rerun = QPushButton("Re-Analyse")
        btn_rerun.setObjectName("RunButton")
        _nofocus(btn_rerun)
        btn_rerun.setToolTip("Re-run analysis on the current Siril image")
        btn_rerun.clicked.connect(self._run_analysis)
        actions_layout.addWidget(btn_rerun)

        btn_export_txt = QPushButton("Export Report (.txt)")
        _nofocus(btn_export_txt)
        btn_export_txt.setToolTip("Save the analysis report as a text file")
        btn_export_txt.clicked.connect(self._export_report_txt)
        actions_layout.addWidget(btn_export_txt)

        btn_export_script = QPushButton("Export Script (.ssf)")
        _nofocus(btn_export_script)
        btn_export_script.setToolTip("Generate a Siril script with the recommended workflow")
        btn_export_script.clicked.connect(self._export_script)
        actions_layout.addWidget(btn_export_script)

        layout.addWidget(grp_actions)

        # Help & Close
        layout.addStretch()

        btn_help = QPushButton("Help")
        _nofocus(btn_help)
        btn_help.clicked.connect(self._show_help_dialog)
        layout.addWidget(btn_help)

        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.setObjectName("CloseButton")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return left

    def _run_analysis(self) -> None:
        """Run the full image analysis pipeline."""
        self.lbl_status.setText("Collecting image data...")
        self.progress.setRange(0, 0)
        self.report_view.setHtml(
            "<div style='color: #888; font-size: 14pt; padding: 40px; text-align: center;'>"
            "Analysing image... please wait.</div>"
        )
        QApplication.processEvents()

        try:
            # Ensure connection
            if not self.siril.connected:
                self.siril.connect()

            # Phase 1: Collect pixel data (inside image_lock to prevent timeout)
            self.lbl_status.setText("Phase 1: Collecting image data...")
            QApplication.processEvents()
            with self.siril.image_lock():
                self.info = collect_image_info(self.siril)

            # Star analysis — runs outside image_lock (get_image_stars triggers findstar internally)
            self.lbl_status.setText("Phase 1: Detecting stars...")
            QApplication.processEvents()
            collect_star_info(self.siril, self.info)

            # Phase 2+3: Analyse and build workflow
            self.lbl_status.setText("Phase 2: Running analysis modules...")
            QApplication.processEvents()
            self.results = build_workflow(self.info)

            # Phase 4: Display
            self.lbl_status.setText("Phase 3: Generating report...")
            QApplication.processEvents()
            self._display_report()

            self.lbl_status.setText("Analysis complete.")
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

            # Update info panel
            self._update_info_panel()

            # Log to Siril console
            try:
                report_text = format_report_text(self.info, self.results)
                for line in report_text.split("\n"):
                    self.siril.log(line)
            except Exception:
                pass

        except NoImageError:
            self._show_no_image_error()
        except SirilConnectionError:
            self.lbl_status.setText("Connection error")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            QMessageBox.warning(
                self,
                "Connection Timeout",
                "The connection to Siril timed out. "
                "Ensure a FITS image is loaded in Siril and try again."
            )
        except SirilError as e:
            err = str(e).lower()
            if "no image" in err or "fits" in err:
                self._show_no_image_error()
            else:
                self.lbl_status.setText("Siril error")
                self.progress.setRange(0, 1)
                self.progress.setValue(0)
                QMessageBox.critical(self, "Siril Error", f"Siril error: {e}")
        except (OSError, ConnectionError, RuntimeError):
            self._show_no_image_error()
        except Exception as e:
            self.lbl_status.setText("Error")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            QMessageBox.critical(
                self,
                "Error",
                f"Analysis failed: {e}\n\n{traceback.format_exc()}"
            )

    def _show_no_image_error(self) -> None:
        self.lbl_status.setText("No image loaded")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        QMessageBox.warning(
            self,
            "No Image",
            "No image is currently loaded in Siril.\n"
            "Please load a stacked, linear FITS image first."
        )

    def _display_report(self) -> None:
        """Render the HTML report in the text view."""
        if self.info and self.results:
            html = format_report_html(self.info, self.results)
            self.report_view.setHtml(html)

    def _update_info_panel(self) -> None:
        """Update the left-panel image info label."""
        if not self.info:
            return
        lines = [
            f"{self.info.image_type}",
            f"{self.info.width} × {self.info.height} px",
        ]
        if self.info.stack_count > 0:
            lines.append(f"{self.info.stack_count} frames stacked")
        if self.info.num_stars > 0:
            lines.append(f"{self.info.num_stars} stars detected")
        actionable = [r for r in self.results if r.siril_command and r.severity != "info"]
        lines.append(f"{len(actionable)} steps recommended")
        self.lbl_info.setText("\n".join(lines))

    def _export_report_txt(self) -> None:
        """Export the report as a .txt file."""
        if not self.info or not self.results:
            QMessageBox.information(self, "No Report", "Run analysis first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "image_advisor_report.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            try:
                report = format_report_text(self.info, self.results)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report)
                QMessageBox.information(self, "Saved", f"Report saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save report:\n{e}")

    def _export_script(self) -> None:
        """Export the recommended workflow as a Siril .ssf script."""
        if not self.info or not self.results:
            QMessageBox.information(self, "No Report", "Run analysis first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Siril Script", "image_advisor_workflow.ssf",
            "Siril Scripts (*.ssf);;All Files (*)"
        )
        if path:
            try:
                script = generate_script(self.results)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                QMessageBox.information(self, "Saved", f"Script saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save script:\n{e}")

    def _show_help_dialog(self) -> None:
        """Show a modal Help dialog with usage information."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Image Advisor — Help")
        dlg.setMinimumSize(620, 520)
        layout = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(
            f"Image Advisor v{VERSION} — Help\n"
            "==============================\n\n"
            "This script was developed by Sven Ramuschkat.\n"
            "Web: www.svenesis.org\n"
            "GitHub: https://github.com/sramuschkat/Siril-Scripts\n\n"
            "1. OVERVIEW\n"
            "-----------\n"
            "Image Advisor analyses a stacked, linear FITS image loaded in Siril and\n"
            "generates a prioritised list of processing recommendations with concrete\n"
            "Siril commands. It does NOT modify the image — it only diagnoses and advises.\n"
            "Think of it as a second opinion from an experienced astrophotographer.\n\n"
            "2. WHAT IS ANALYSED\n"
            "-------------------\n"
            "• Image type (OSC / Mono / Narrowband / Dual-NB / Luminance)\n"
            "• Linear state — warns if image is already stretched\n"
            "• Calibration status — detects darks/flats/biases from HISTORY\n"
            "• Background gradient (8x8 sigma-clipped tile grid)\n"
            "• Gradient pattern (vignetting / linear LP / amp glow)\n"
            "• Plate-solve status (WCS / pltsolvd keyword)\n"
            "• Colour balance (R/G/B ratios, SPCC recommendation)\n"
            "• Noise / SNR (MAD-based, integration-time-aware)\n"
            "• Deconvolution suitability (PSF from star FWHM)\n"
            "• Nebulosity detection (narrowband-adjusted thresholds)\n"
            "• Star quality (FWHM in px/arcsec, elongation, centre vs edge)\n"
            "• Saturated star count\n"
            "• Dynamic range (usable stops)\n"
            "• Pixel clipping (black and white)\n"
            "• Stacking border detection\n"
            "• Image sanity checks (extreme clipping, unusual dimensions)\n\n"
            "3. WORKFLOW ORDER\n"
            "-----------------\n"
            "The recommended workflow follows the golden rule:\n"
            "\"Do everything possible in the linear stage.\"\n\n"
            "  LINEAR:      Crop → Background Extraction → Platesolving → SPCC →\n"
            "               Remove Green (opt.) → Denoising → Deconvolution →\n"
            "               Starless (StarNet/SyQon)\n"
            "  TRANSITION:  Stretching (VeraLux HMS)\n"
            "  NON-LINEAR:  Fine-tuning (Revela/Curves/Vectra) → StarComposer →\n"
            "               Signature & Export\n\n"
            "4. REPORT SECTIONS\n"
            "------------------\n"
            "• Image Summary — type, size, exposure, resolution, plate-solve\n"
            "• Key Statistics — SNR, noise, gradient, DR, nebulosity, stars\n"
            "• Processing State — linear/stretched, calibration status\n"
            "• Per-Channel Statistics — R/G/B noise with noisiest highlighted\n"
            "• Background Heatmap — 8x8 tile grid with gradient pattern label\n"
            "• Findings — all analysis results with severity icons\n"
            "• Recommended Workflow — actionable steps with Siril commands\n"
            "• Post-Processing Roadmap — stretch and non-linear steps\n\n"
            "5. EXPORT\n"
            "---------\n"
            "• Export Report (.txt) — Save the full analysis as a text file.\n"
            "• Export Script (.ssf) — Generate a Siril script with the\n"
            "  recommended commands and save checkpoints. The script includes\n"
            "  a 'requires 1.4.1' directive.\n\n"
            "6. SEVERITY LEVELS\n"
            "------------------\n"
            "  [ℹ] Info      — Informational, no action needed\n"
            "  [✓] Minor     — Optional improvement\n"
            "  [⚠] Moderate  — Recommended action\n"
            "  [✗] Critical  — Strong recommendation or significant issue\n\n"
            "7. SMART BEHAVIOUR\n"
            "------------------\n"
            "• Gradient recommendations include -samples when nebulosity is present\n"
            "• Denoise is promoted before deconvolution (RL amplifies noise)\n"
            "• StarNet uses -stretch only on linear images\n"
            "• Soft stars / elongation are shown early as acquisition warnings\n"
            "• Stretch advice includes background pedestal warnings\n"
            "• Workflow is suppressed when image fails sanity checks\n"
            "• Channel balance note when R/G/B are unusually equal\n\n"
            "8. REQUIREMENTS\n"
            "---------------\n"
            "• Siril ≥ 1.4.1 with Python scripting (sirilpy)\n"
            "• Image must be loaded in Siril (stacked, linear FITS)\n"
            "• Python packages: numpy, PyQt6 (auto-installed by sirilpy)\n"
        )
        layout.addWidget(te)

        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.close)
        layout.addWidget(btn_close)
        dlg.exec()


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        win = ImageAdvisorWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Image Advisor v{VERSION} loaded.")
        except Exception:
            pass
        return app.exec()
    except NoImageError:
        QMessageBox.warning(
            None,
            "No Image",
            "No image is currently loaded in Siril. Please load an image first."
        )
        return 1
    except Exception as e:
        QMessageBox.critical(
            None,
            "Image Advisor Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
