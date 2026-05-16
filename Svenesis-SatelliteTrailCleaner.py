"""
Svenesis Satellite Trail Cleaner
Script Version: 0.8.9
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

Per-frame satellite / aircraft trail detection and removal for a folder of
FITS or RAW sub-exposures, run *before* stacking. Siril's built-in approach
to trails is sigma-clipped stack rejection, which works for >=8 well-distributed
subs but leaves visible streaks in short sequences. This tool fills that gap.

Detection pipeline (v0.5+):

The detection backend is **STScI's acstools.findsat_mrt.TrailFinder** —
the same Median Radon Transform pipeline used to find satellite trails in
HST/ACS images. This is the published state-of-the-art for the problem,
and it solves the killer failure mode of sum-Radon: bright stars
contributing a "fan" of false-positive lines via point-source flux in
every line integral.

The MRT replaces the sum-along-line with the *median* of pixel values
along the line. A real satellite trail has roughly constant flux along
its entire length, so the median equals the per-pixel signal. A bright
star occupies <1% of the line's pixels — the median treats it as a
high-value outlier and ignores it. Comet tails are non-uniform (head
bright, tail fades) and are killed by the persistence test, which
chunks the candidate trail in 100-px segments and demands that a
majority show consistent SNR.

Steps:
  1. background subtraction (median or photutils.Background2D)
  2. TrailFinder(image).run_all() -- MRT + matched-filter peak detection
     in MRT space (3 line-width kernels) + image-space width / persistence
     validation per candidate
  3. Endpoints are returned per accepted line
  4. The existing mask/dilate/star-protect/inpaint pipeline takes over


Features:
- Folder picker for FITS, PixInsight XISF, TIFF (8/16/32-bit + float), and RAW (CR2 / CR3 / NEF / ARW / DNG and others via Siril/libraw)
- Hough-line detection on a background-subtracted, MTF-stretched residual
- Star protection via photutils so stars under a trail are preserved when possible
- Live mask overlay (red) and cleaned-preview view modes
- Hybrid UX: tune detection on the current frame, then "Apply to all" with
  optional per-frame confirmation
- Non-destructive output: source files are moved to an `originals/` subfolder;
  the cleaned image is written with the original filename so existing stacking
  pipelines pick it up unchanged
- XISF round-trip: cleaned output stays as `.xisf` with all FITS keywords AND
  XISFProperties preserved (incl. plate-solving astrometry) via the
  sergio-dr/xisf Python package. FITS round-trips its header verbatim. TIFF
  round-trips via the tifffile package, preserving dtype (uint8/uint16/
  uint32/float32), compression, photometric interpretation, and the
  ImageDescription / Software / DateTime tags. RAW inputs are debayered
  and written as FITS
- Per-folder `trail_cleanup_report.txt` audit (frames cleaned, trail count,
  line length, pixels replaced)
- Dark themed PyQt6 GUI matching the rest of the Svenesis suite
- Persistent settings via QSettings

Run from Siril via Processing -> Scripts. Place this file inside a folder
named Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2026
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import sys
import os
import shutil
import logging
import traceback
import threading
import datetime as _dt
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("SatelliteTrailCleaner")

import numpy as np

import sirilpy as s

try:
    from sirilpy.exceptions import SirilError, SirilConnectionError
except ImportError:
    class SirilError(Exception):
        pass
    class SirilConnectionError(Exception):
        pass

s.ensure_installed(
    "numpy", "PyQt6", "astropy",
    "opencv-python-headless", "photutils",
    "scikit-image", "acstools", "xisf",
    "tifffile",
)

import cv2
from astropy.io import fits
from astropy.stats import sigma_clipped_stats

try:
    from photutils.detection import find_peaks
    from astropy.stats import SigmaClip
    _HAVE_PHOTUTILS = True
except ImportError:
    _HAVE_PHOTUTILS = False

try:
    from acstools.findsat_mrt import TrailFinder
    _HAVE_FINDSAT_MRT = True
except ImportError:
    _HAVE_FINDSAT_MRT = False

try:
    from xisf import XISF
    _HAVE_XISF = True
except ImportError:
    _HAVE_XISF = False

try:
    import tifffile
    _HAVE_TIFFFILE = True
except ImportError:
    _HAVE_TIFFFILE = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QDialog, QScrollArea, QProgressBar, QButtonGroup, QRadioButton,
    QTabWidget, QComboBox, QFileDialog, QProgressDialog,
    QLineEdit, QTextEdit, QTextBrowser, QFrame,
)
from PyQt6.QtCore import (
    Qt, QSettings, QUrl, QTimer, pyqtSignal, QObject, QRect,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QImage, QPixmap,
    QDesktopServices, QShortcut, QKeySequence,
)

VERSION = "0.8.9"

SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "SatelliteTrailCleaner"

LEFT_PANEL_WIDTH = 360

FITS_EXTENSIONS = (".fit", ".fits", ".fts")
RAW_EXTENSIONS = (
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".rw2",
    ".orf", ".pef", ".srw", ".mrw", ".x3f", ".kdc",
)
# PixInsight's native XISF format. Loaded via Siril (native XISF reader since
# 1.4); we have no XISF write path, so cleaned XISF inputs are written as .fit
# (same handling as RAW: synthesised header, original moved to originals/).
XISF_EXTENSIONS = (".xisf",)
# Plain TIFF: handled directly via the tifffile package, NOT via Siril,
# so we get bit-exact dtype round-trip (uint8 / uint16 / uint32 / float32)
# and can preserve ImageDescription / Software / DateTime tags.
TIFF_EXTENSIONS = (".tif", ".tiff")

# Single guard around every sirilpy RPC call. The Python binding to Siril
# uses a single socket; concurrent calls from worker threads + the UI
# thread occasionally deliver partly-overwritten buffers.
_siril_io_lock = threading.Lock()


# ------------------------------------------------------------------------------
# STYLING (shared Svenesis dark theme)
# ------------------------------------------------------------------------------

def _nofocus(w) -> None:
    """Disable keyboard focus on a widget to prevent focus-rectangle artifacts."""
    if w is not None:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


DARK_STYLESHEET = """
QWidget{background-color:#2b2b2b;color:#e0e0e0;font-size:10pt}

QToolTip{background-color:#333333;color:#ffffff;border:1px solid #88aaff}

QGroupBox{border:1px solid #444444;margin-top:5px;font-weight:bold;border-radius:4px;padding-top:12px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 3px;color:#88aaff}

QLabel{color:#cccccc}

QCheckBox{color:#cccccc;spacing:5px}
QCheckBox::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:3px}
QCheckBox::indicator:checked{background:#285299;border:1px solid #88aaff;image:none}

QRadioButton{color:#cccccc;spacing:5px}
QRadioButton::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:7px}
QRadioButton::indicator:checked{background:#285299;border:2px solid #88aaff}

QSlider::groove:horizontal{background:#3c3c3c;height:6px;border-radius:3px}
QSlider::handle:horizontal{background:#88aaff;width:14px;margin:-4px 0;border-radius:7px}
QSlider::sub-page:horizontal{background:#285299;border-radius:3px}

QSpinBox,QDoubleSpinBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QSpinBox:focus,QDoubleSpinBox:focus{border-color:#88aaff}

QComboBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QComboBox:focus{border-color:#88aaff}
QComboBox::drop-down{border:none}
QComboBox QAbstractItemView{background:#3c3c3c;color:#e0e0e0;selection-background-color:#285299}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton:disabled{background-color:#3a3a3a;color:#777777;border-color:#555555}
QPushButton#CoffeeButton{background-color:#FFDD00;color:#000000;border:1px solid #ccb100;font-weight:bold}
QPushButton#CoffeeButton:hover{background-color:#ffe740;border-color:#ddcc00}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#ApplyButton{background-color:#2a3a5a;border:1px solid #4060a0;padding:8px;font-size:11pt}
QPushButton#ApplyButton:hover{background-color:#3a4a7a}
QPushButton#ApplyAllButton{background-color:#2a4a3a;border:1px solid #408060;padding:8px;font-size:11pt}
QPushButton#ApplyAllButton:hover{background-color:#3a6a5a}
QPushButton#DetectButton{background-color:#3a3a5a;border:1px solid #5060a0}
QPushButton#DetectButton:hover{background-color:#4a4a7a}
QPushButton#SkipButton{background-color:#444444;border:1px solid #777777}

QTabWidget::pane{border:1px solid #444444;background:#2b2b2b}
QTabBar::tab{background:#3c3c3c;color:#cccccc;padding:6px 12px;border:1px solid #444444;border-bottom:none;border-radius:4px 4px 0 0;margin-right:2px}
QTabBar::tab:selected{background:#2b2b2b;color:#88aaff;font-weight:bold}
QTabBar::tab:hover{background:#4a4a4a}

QProgressBar{background:#3c3c3c;border:1px solid #555;border-radius:3px;text-align:center;color:#ccc}
QProgressBar::chunk{background:#285299;border-radius:2px}

QScrollArea{border:none;background:#2b2b2b}
"""


# ------------------------------------------------------------------------------
# AUTOSTRETCH (Midtone Transfer Function) -- copied from BlinkComparator for
# rendering consistency across the Svenesis tools. A later refactor can move
# these into a shared svenesis_common module.
# ------------------------------------------------------------------------------

def mtf(midtone: float, x, out=None):
    if isinstance(x, np.ndarray):
        denom = np.multiply(x, 2.0 * midtone - 1.0)
        denom -= midtone
        np.putmask(denom, np.abs(denom) < 1e-10, 1.0)
        if out is None:
            out = np.multiply(x, midtone - 1.0)
        else:
            np.multiply(x, midtone - 1.0, out=out)
        out /= denom
        np.clip(out, 0.0, 1.0, out=out)
        return out
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    denom = (2 * midtone - 1) * x - midtone
    if abs(denom) < 1e-10:
        return 0.5
    return max(0.0, min(1.0, (midtone - 1) * x / denom))


def _build_mtf_lut_u16(shadow_f: float, rng_f: float, midtone_f: float) -> np.ndarray:
    x = np.arange(65536, dtype=np.float32) * (1.0 / 65535.0)
    x -= shadow_f
    x *= (1.0 / rng_f)
    np.clip(x, 0.0, 1.0, out=x)
    mtf(midtone_f, x, out=x)
    x *= 255.0
    return x.astype(np.uint8)


def autostretch(
    data: np.ndarray,
    shadows_clip: float = -2.8,
    target_median: float = 0.25,
) -> np.ndarray:
    """MTF autostretch. Accepts uint16 or float32 input, returns uint8.

    Uses a 65k-entry LUT for uint16 (the common 16-bit FITS path).
    """
    is_u16 = data.dtype == np.uint16

    flat = data.ravel()
    if flat.size > 500000:
        step = flat.size // 500000
        flat = flat[::step]
    if is_u16:
        flat = flat.astype(np.float32) * (1.0 / 65535.0)
    median = float(np.median(flat))
    mad = float(np.median(np.abs(flat - median)))

    shadow = max(0.0, median + shadows_clip * mad)
    rng = 1.0 - shadow
    if rng < 1e-10:
        rng = 1.0
    if median - shadow > 0:
        midtone = mtf(target_median, median - shadow)
    else:
        midtone = 0.5

    if is_u16:
        lut = _build_mtf_lut_u16(shadow, rng, float(midtone))
        return lut[data]

    stretched = np.subtract(data, shadow, dtype=np.float32)
    stretched *= (1.0 / rng)
    np.clip(stretched, 0, 1, out=stretched)
    mtf(midtone, stretched, out=stretched)
    stretched *= 255.0
    return stretched.astype(np.uint8)


# ------------------------------------------------------------------------------
# FILE LOAD HELPERS
# ------------------------------------------------------------------------------

def is_supported_file(path: str) -> bool:
    p = path.lower()
    return (
        p.endswith(FITS_EXTENSIONS)
        or p.endswith(RAW_EXTENSIONS)
        or p.endswith(XISF_EXTENSIONS)
        or p.endswith(TIFF_EXTENSIONS)
    )


def is_raw_file(path: str) -> bool:
    return path.lower().endswith(RAW_EXTENSIONS)


def is_fits_file(path: str) -> bool:
    return path.lower().endswith(FITS_EXTENSIONS)


def is_xisf_file(path: str) -> bool:
    return path.lower().endswith(XISF_EXTENSIONS)


def is_tiff_file(path: str) -> bool:
    return path.lower().endswith(TIFF_EXTENSIONS)


def load_frame_data(siril_iface, path: str):
    """Load a single frame via Siril (handles FITS + RAW debayer automatically).

    Returns the data as a numpy array. RAW files come back debayered.
    Header (for FITS) is fetched separately via astropy when we need to
    preserve it on write.

    TIFF is handled directly via the tifffile package, bypassing Siril.
    Siril CAN load TIFF, but its 8/16-bit auto-promotion path and the
    way it surfaces planar config differs from what we need for bit-
    exact round-trip — and tifffile gives us all the metadata we need
    for the write side anyway.
    """
    if not path:
        return None
    # ---- TIFF fast path: direct via tifffile ----
    if is_tiff_file(path) and _HAVE_TIFFFILE:
        try:
            data, _meta = read_tiff_with_meta(path)
            if data is None:
                return None
            # Normalise dtype to what the rest of the pipeline expects.
            # uint8 / uint16: keep as uint16 (promote 8 -> 16 to avoid
            # precision loss in the inpaint step). uint32 / float: keep
            # as float32 in [0,1] (consistent with FITS path).
            if data.dtype == np.uint8:
                return (data.astype(np.uint16) << 8)
            if data.dtype == np.uint16:
                return np.array(data, dtype=np.uint16, copy=True)
            if np.issubdtype(data.dtype, np.integer):
                # uint32 / int32: scale to float32 [0,1] via max range
                info = np.iinfo(data.dtype)
                scale = 1.0 / float(max(info.max, 1))
                return data.astype(np.float32) * scale
            # float TIFF: leave the dynamic range alone — astro TIFFs
            # written by Siril / PixInsight are already [0,1] floats.
            arr = data.astype(np.float32, copy=True)
            mx = float(np.nanmax(arr)) if arr.size else 0.0
            if mx > 1.5:
                # Likely a 16-bit-scaled float TIFF (some tools store
                # float in 0..65535 to match uint16 range). Normalise.
                arr *= (1.0 / 65535.0)
            return arr
        except Exception as exc:
            log.debug("tifffile read failed for %s: %s; falling back to Siril",
                      path, exc)
            # fall through to Siril path

    try:
        with _siril_io_lock:
            frame = siril_iface.load_image_from_file(path, with_pixels=True)
        if frame is None or frame.data is None:
            return None
        raw = frame.data
        # Avoid the unconditional full-image copy (v0.8.8). Only copy
        # when the dtype actually needs to change, and use np.asarray()
        # which is a no-op when the dtype already matches. On a 60 MP
        # frame this saves ~50 ms per load and ~240 MB of transient
        # memory traffic.
        if np.issubdtype(raw.dtype, np.integer):
            if raw.dtype == np.uint16:
                # Hand the buffer back as-is. Downstream code never
                # writes through this view (detection / inpaint always
                # materialise their own working copies), so sharing
                # memory with Siril's internal buffer is safe.
                return raw
            return raw.astype(np.uint16, copy=False)
        # Float path: must materialise as float32 for the [0,1] scaling
        # below, so a copy is necessary if dtype differs. asarray() is
        # a no-op when raw.dtype is already float32 — we then *do* need
        # a copy because we mutate in-place at line `data *= ...`.
        if raw.dtype == np.float32:
            data = np.array(raw, copy=True)
        else:
            data = raw.astype(np.float32, copy=False)
        # Defensive: zero-pixel arrays can come back from Siril if a
        # decoder silently fails on an unusual file. Indexing data.flat
        # below would raise IndexError, so short-circuit here.
        if data.size == 0:
            return data
        if data.flat[0] > 1.5 or (data.size > 100 and data.flat[data.size // 2] > 1.5):
            data *= (1.0 / 65535.0)
        return data
    except (SirilError, OSError, ValueError, TypeError, RuntimeError) as exc:
        log.debug("Failed to load frame data from %s: %s", path, exc)
        return None


def to_mono_float32(frame: np.ndarray, mode: str = "mean") -> np.ndarray:
    """Reduce (3,H,W) / (1,H,W) / (H,W) frame to a single-channel float32
    [0, 1] image suitable for trail detection.

    The ``mode`` parameter controls the RGB → mono reduction:

    * ``"mean"`` (default): equal-weight average across channels. Fast,
      symmetric, what we've used historically — preserves overall
      brightness statistics and matches what users see in a desaturated
      preview.
    * ``"max"``: per-pixel maximum over the three channels. Useful when
      a satellite trail is bright in only ONE channel (e.g. a sodium-
      reflective satellite glowing red) — that trail would have only
      1/3 of its true brightness under a mean reduction and lose √3 of
      its SNR for the MRT detector. The max reduction preserves the
      full per-channel signal regardless of colour.

    Performance: both modes use ``np.tensordot`` / ``np.max`` directly
    on the source buffer with the float32 cast fused in — no large
    intermediate copy.
    """
    if frame.ndim == 3 and frame.shape[0] == 3:
        frame_f = frame.astype(np.float32, copy=False)
        if mode == "max":
            # Per-pixel max over channels. Single pass via np.max.
            mono = np.max(frame_f, axis=0)
        else:
            # Default "mean": equal-weight reduction fused with the
            # float32 cast via tensordot — one pass, no 720 MB
            # (3, H, W) float32 intermediate.
            weights = np.full(3, 1.0 / 3.0, dtype=np.float32)
            mono = np.tensordot(weights, frame_f, axes=1)
    elif frame.ndim == 3 and frame.shape[0] == 1:
        mono = frame[0].astype(np.float32, copy=False)
    elif frame.ndim == 2:
        mono = frame.astype(np.float32, copy=False)
    else:
        raise ValueError(f"Unsupported frame shape: {frame.shape}")
    # tensordot already produces float32 because the weights are float32
    # and we cast frame to float32. No second astype needed.
    # Normalise to [0, 1] regardless of source dtype.
    mx = float(mono.max())
    if mx > 1.5:
        # Out-of-place multiply only when needed — keeps the function
        # safe for callers that share their input buffer.
        scale = 1.0 / 65535.0 if mx > 256.0 else 1.0 / 255.0
        mono = mono * scale
    return mono


# ------------------------------------------------------------------------------
# TRAIL DETECTION
# ------------------------------------------------------------------------------

class DetectionParams:
    """User-tunable detection parameters (findsat_mrt / Median Radon Transform)."""

    def __init__(self) -> None:
        # TrailFinder parameters (see acstools.findsat_mrt.TrailFinder)
        self.snr_threshold: float = 5.0          # SNR threshold on the MRT
        self.min_length: int = 50                # min trail length (MRT pixels)
        self.max_width: int = 75                 # max trail width (image pixels)
        self.check_persistence: bool = True      # split trail into chunks + verify SNR
        self.min_persistence: float = 0.5        # fraction of chunks that must pass
        self.persistence_chunk: int = 100        # pixels per persistence chunk
        self.min_persistence_snr: float = 3.0    # SNR floor inside each chunk
        # Auto-detect process count: half the logical CPUs, clamped to [2, 8].
        # MRT parallelises over angles -- diminishing returns above 8 workers
        # because of process startup cost vs. per-angle work.
        try:
            _cpu = os.cpu_count() or 4
        except Exception:
            _cpu = 4
        self.processes: int = max(2, min(8, _cpu // 2))

        # Performance controls
        self.downsample: int = 2                 # pre-downsample factor (1/2/4)
        self.theta_step_deg: float = 0.5         # MRT angle resolution
        self.scan_mode: str = "normal"           # "quick" | "normal" | "deep"

        # RGB → mono reduction for the MRT detector. "mean" averages
        # channels (default, what we've always done — works perfectly
        # for white / luminance-only frames). "max" takes the per-pixel
        # maximum across channels, which preserves the full signal of a
        # trail that's bright in only one colour channel (e.g. a sodium-
        # reflective satellite glowing red): under "mean" that trail
        # would lose √3 of its SNR and might fall below the threshold.
        self.mono_mode: str = "mean"             # "mean" | "max"

        # Mask construction
        self.dilation_radius: int = 7            # px to thicken each line into a mask

        # Star protection (for inpaint: optionally preserve real stars
        # detected in the halo around the trail). Default OFF because a
        # bright satellite trail produces many local maxima along its
        # length that find_peaks misidentifies as stars; turning star
        # protection on can then mask out the trail itself and leave it
        # uncleaned. Enable manually when you have a known star sitting
        # in the trail's dilation halo that you want to preserve.
        self.protect_stars: bool = False
        self.star_sigma: float = 5.0
        self.star_dilation: int = 4

        # Inpainting
        # "perp_strip" / "harmonic" / "cv2_ns" / "cv2_telea" /
        # "cv2_navier_stokes" / "biharmonic"
        self.inpaint_method: str = "perp_strip"
        self.strip_width: int = 15
        # Post-process: add Gaussian noise matching the local sky std
        # so the inpainted region is statistically indistinguishable
        # from real sky background. ON by default; the visual effect is
        # subtle but a trained eye can spot smooth-patch artefacts
        # otherwise.
        self.match_sky_noise: bool = True

        # Legacy fields retained for backward compat with code paths that
        # still reference them (border_margin is read by the line endpoint
        # helper from v0.4)
        self.border_margin: int = 10


class TrailDetection:
    """Result of running detection on a single frame.

    ``selections`` is parallel to ``lines`` and marks which lines the user
    wants inpainted. Default after fresh detection is all True (everything
    gets removed). The user toggles entries via the canvas line-overlay UI;
    ``rebuild_effective_mask`` then refreshes ``mask`` / ``effective_mask``
    from the current selections.
    """

    def __init__(
        self,
        lines: list[tuple[int, int, int, int]],
        mask: np.ndarray,
        star_mask: np.ndarray,
        effective_mask: np.ndarray,
        diag_px: float,
        notes: str = "",
        selections: list[bool] | None = None,
    ) -> None:
        self.lines = lines
        self.mask = mask                       # raw line mask (uint8 0/255)
        self.star_mask = star_mask             # star protection mask
        self.effective_mask = effective_mask   # mask AND NOT star_mask -> what gets inpainted
        self.diag_px = diag_px
        self.notes = notes
        if selections is None:
            self.selections = [True] * len(lines)
        else:
            self.selections = list(selections)
        # Inpaint-method recommendation, filled by analyse_trail_profile()
        # after detection completes. Empty by default so callers that
        # build a TrailDetection without analysis (the empty/error
        # constructors) don't show a stale suggestion.
        self.recommended_method: str = ""
        self.recommendation_rationale: str = ""
        # Sky statistics from the halo-growth sigma-clipping step.
        # Carried on the detection so analyse_trail_profile() and any
        # other downstream consumer can reuse them without re-running
        # the (expensive on 60 MP) sigma-clip loop. 0.0 means "not
        # computed" — consumers should re-derive if they need them.
        self.sky_med: float = 0.0
        self.sky_sigma: float = 0.0

    @property
    def has_trails(self) -> bool:
        return len(self.lines) > 0

    @property
    def has_selected(self) -> bool:
        return any(self.selections)

    @property
    def selected_lines(self) -> list[tuple[int, int, int, int]]:
        return [ln for ln, sel in zip(self.lines, self.selections) if sel]

    @property
    def pixels_to_inpaint(self) -> int:
        return int(np.count_nonzero(self.effective_mask))

    def rebuild_effective_mask(self, params: "DetectionParams") -> None:
        """Recompute mask + effective_mask from currently selected lines.

        Called after the user toggles line selections in the UI. Star mask
        does not need recomputing here -- it depends on the frame, not on
        which lines were chosen. We DO filter star_mask entries that fall
        inside the (newly selected) trail mask, because those are
        misclassified trail pixels masquerading as stars.
        """
        h, w = self.mask.shape
        new_mask = np.zeros((h, w), dtype=np.uint8)
        sel_lines = self.selected_lines
        for (x1, y1, x2, y2) in sel_lines:
            cv2.line(new_mask, (x1, y1), (x2, y2), 255, thickness=1)
        if sel_lines and params.dilation_radius > 0:
            k = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (2 * params.dilation_radius + 1, 2 * params.dilation_radius + 1),
            )
            new_mask = cv2.dilate(new_mask, k)
        self.mask = new_mask
        eff = new_mask.copy()
        if sel_lines and self.star_mask.any():
            # Same filter as in detect_trails: any star detection that
            # lies inside the dilated trail mask is almost certainly a
            # trail pixel picked up as a peak -- discard it so the trail
            # gets fully inpainted.
            star_outside = self.star_mask.copy()
            star_outside[new_mask > 0] = 0
            eff[star_outside > 0] = 0
        self.effective_mask = eff


def _sigma_clip_background(mono: np.ndarray) -> tuple[float, float]:
    """Return (median, std) using sigma-clipped statistics. Fast for our use:
    only the residual is what feeds into the edge detector."""
    try:
        _, med, std = sigma_clipped_stats(mono, sigma=3.0, maxiters=3)
        return float(med), float(std)
    except Exception:
        med = float(np.median(mono))
        std = float(np.std(mono))
        return med, std


def _detect_star_mask(mono: np.ndarray, params: DetectionParams) -> np.ndarray:
    """Build a 0/255 uint8 mask of star pixels (dilated) so they can be
    excluded from the trail mask. Falls back to a plain sigma-threshold
    when photutils is not available.
    """
    h, w = mono.shape
    star_mask = np.zeros((h, w), dtype=np.uint8)
    if not params.protect_stars:
        return star_mask

    med, std = _sigma_clip_background(mono)
    threshold = med + params.star_sigma * std

    if _HAVE_PHOTUTILS:
        try:
            peaks = find_peaks(mono, threshold=threshold, box_size=11)
        except Exception:
            peaks = None
        if peaks is not None and len(peaks) > 0:
            xs = np.asarray(peaks["x_peak"], dtype=np.int32)
            ys = np.asarray(peaks["y_peak"], dtype=np.int32)
            r = max(1, params.star_dilation)
            for x, y in zip(xs, ys):
                cv2.circle(star_mask, (int(x), int(y)), r, 255, thickness=-1)
            return star_mask

    # Fallback: simple sigma threshold + dilate
    bright = (mono > threshold).astype(np.uint8) * 255
    if params.star_dilation > 0:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (2 * params.star_dilation + 1, 2 * params.star_dilation + 1),
        )
        bright = cv2.dilate(bright, k)
    return bright


def _line_endpoints_in_image(
    rho: float, theta_deg: float, w: int, h: int,
) -> tuple[int, int, int, int] | None:
    """Compute endpoints of the line at (rho, theta) inside image [0..w-1, 0..h-1].

    Convention:
      - center of the image is (w/2, h/2)
      - theta_deg is the line's angle measured from the +x axis (CCW in screen
        coords, i.e. clockwise visually because y points down)
      - rho is the signed perpendicular distance from the center to the line,
        measured along the normal direction (-sin(theta), cos(theta))

    Returns (x1, y1, x2, y2) integer endpoints or None if the line does not
    cross the image.
    """
    theta = float(np.deg2rad(theta_deg))
    nx = -np.sin(theta)
    ny = np.cos(theta)
    dx = np.cos(theta)
    dy = np.sin(theta)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    px = cx + rho * nx
    py = cy + rho * ny

    # Parametric: (x, y) = (px + t*dx, py + t*dy). Find t range so the point
    # stays inside the image rectangle.
    t_candidates: list[float] = []
    if abs(dx) > 1e-9:
        t_candidates.append((0.0 - px) / dx)
        t_candidates.append((w - 1.0 - px) / dx)
    if abs(dy) > 1e-9:
        t_candidates.append((0.0 - py) / dy)
        t_candidates.append((h - 1.0 - py) / dy)
    if not t_candidates:
        return None
    # Keep only ts whose resulting point is on the image
    valid: list[float] = []
    for t in t_candidates:
        x = px + t * dx
        y = py + t * dy
        if -0.5 <= x <= w - 0.5 and -0.5 <= y <= h - 0.5:
            valid.append(t)
    if len(valid) < 2:
        return None
    valid.sort()
    t1, t2 = valid[0], valid[-1]
    if abs(t2 - t1) < 1.0:
        return None
    x1 = int(np.clip(round(px + t1 * dx), 0, w - 1))
    y1 = int(np.clip(round(py + t1 * dy), 0, h - 1))
    x2 = int(np.clip(round(px + t2 * dx), 0, w - 1))
    y2 = int(np.clip(round(py + t2 * dy), 0, h - 1))
    return (x1, y1, x2, y2)


def _extend_endpoints_to_boundary(
    x1: int, y1: int, x2: int, y2: int, w: int, h: int,
) -> tuple[int, int, int, int]:
    """Extend a finite line segment to the image rectangle boundary.

    TrailFinder's per-source endpoint estimate often truncates where
    the trail signal weakens at the ends -- the real satellite trail
    typically continues all the way to (or beyond) the image edge.
    Extending the segment along its own direction until it crosses
    the image border ensures the dilated inpaint mask covers the
    full sweep of the trail.

    A side effect: for trails that are *not* full-frame (entered or
    exited the field mid-exposure), the extension paints over a few
    extra sky pixels at the ends. cv2.inpaint replaces them with the
    local sky background -- effectively a no-op since they were sky
    pixels anyway.
    """
    dx = float(x2 - x1)
    dy = float(y2 - y1)
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return (x1, y1, x2, y2)
    t_candidates: list[float] = []
    if abs(dx) > 1e-9:
        t_candidates.append((0.0 - x1) / dx)
        t_candidates.append((w - 1.0 - x1) / dx)
    if abs(dy) > 1e-9:
        t_candidates.append((0.0 - y1) / dy)
        t_candidates.append((h - 1.0 - y1) / dy)
    valid: list[float] = []
    for t in t_candidates:
        x = x1 + t * dx
        y = y1 + t * dy
        if -0.5 <= x <= w - 0.5 and -0.5 <= y <= h - 0.5:
            valid.append(t)
    if len(valid) < 2:
        return (x1, y1, x2, y2)
    valid.sort()
    t_min, t_max = valid[0], valid[-1]
    nx1 = int(np.clip(round(x1 + t_min * dx), 0, w - 1))
    ny1 = int(np.clip(round(y1 + t_min * dy), 0, h - 1))
    nx2 = int(np.clip(round(x1 + t_max * dx), 0, w - 1))
    ny2 = int(np.clip(round(y1 + t_max * dy), 0, h - 1))
    return (nx1, ny1, nx2, ny2)


def _trailfinder_endpoints(row, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Extract image-space endpoints for a TrailFinder source-list row.

    Tries multiple column conventions: direct endpoint columns
    (``endpoints``, ``x1`` / ``x2`` / ``y1`` / ``y2``) first, then falls
    back to (rho, theta) -> line intersection with the image rectangle.
    """
    # Direct endpoints column (some versions expose this as a 4-tuple)
    for key in ("endpoints", "ep"):
        try:
            ep = row[key]
        except Exception:
            ep = None
        if ep is None:
            continue
        try:
            arr = np.asarray(ep).ravel()
            if arr.size >= 4:
                x1, y1, x2, y2 = (int(v) for v in arr[:4])
                return (x1, y1, x2, y2)
        except Exception:
            pass

    # Component columns (x1, y1, x2, y2)
    try:
        x1 = int(round(float(row["x1"])))
        y1 = int(round(float(row["y1"])))
        x2 = int(round(float(row["x2"])))
        y2 = int(round(float(row["y2"])))
        return (x1, y1, x2, y2)
    except Exception:
        pass

    # rho, theta convention -> compute endpoints
    try:
        rho = float(row["rho"])
        theta = float(row["theta"])
    except Exception:
        return None
    return _line_endpoints_in_image(rho, theta, w, h)


# ------------------------------------------------------------------------------
# INPAINT METHOD RECOMMENDATION
# ------------------------------------------------------------------------------

# Human-readable labels — must stay in sync with the dropdown labels in
# the main window (see SatelliteTrailCleanerWindow._build_left_panel).
INPAINT_METHOD_LABELS = {
    "perp_strip": "Perpendicular Strip Median",
    "harmonic": "Harmonic / Laplace",
    "cv2_ns": "Nearest Neighbor + Smooth",
    "cv2_telea": "cv2 Fast Marching (Telea)",
    "cv2_navier_stokes": "cv2 Navier-Stokes",
    "biharmonic": "Biharmonic (experimental)",
}


def analyse_trail_profile(
    mono: np.ndarray, detection: "TrailDetection",
) -> tuple[str, str]:
    """Inspect the detected trail(s) and recommend an inpaint method.

    Heuristic, not learned — looks at three properties of the trail
    geometry and the local sky:

      1. **Cross-trail sky gradient** — sample two parallel strips
         offset ±30 px to either side of the longest trail. If their
         medians differ by more than 2 σ_sky, there's a real gradient
         (vignetting, light-pollution slope, nearby extended source)
         that a PDE-based method would average away. → recommend
         Perpendicular Strip Median.

      2. **Pearl / flashing pattern** — count distinct bright peaks
         along the trail centreline (mono >> sky baseline). If there
         are many evenly-spaced bright maxima (a tumbling rocket
         body, a flashing satellite), the underlying trail has very
         uneven brightness. Perpendicular Strip Median is robust
         here because the median quietly rejects pearl peaks at the
         centreline as outliers; biharmonic OVERSHOOTS these peaks.
         → recommend Perpendicular Strip Median.

      3. **Compact mask** — short trails (< 8 % of diagonal) with
         small area are well-suited to Harmonic / Laplace, which
         produces the smoothest physically-motivated fill. The
         maximum principle keeps the result bounded by surrounding
         sky values, no ringing risk on the short geometry.
         → recommend Harmonic + Match-sky-noise.

    Default when none of the special cases apply: Perpendicular
    Strip Median (the safest choice on real astro data — survives
    everything the existing test corpus throws at it).

    Returns (method_id, rationale_string). method_id is one of the
    keys in INPAINT_METHOD_LABELS; rationale is human-readable text
    suitable for tooltip / status display.
    """
    if not detection.has_trails:
        return "", ""

    h, w = mono.shape
    diag = float(np.hypot(h, w))

    # Longest accepted line determines the geometry to analyse.
    longest = max(
        detection.lines,
        key=lambda L: float(np.hypot(L[2] - L[0], L[3] - L[1])),
    )
    x1, y1, x2, y2 = longest
    dx = float(x2 - x1); dy = float(y2 - y1)
    L = float(np.hypot(dx, dy))
    length_frac = L / diag if diag > 0 else 0.0

    # Sky stats — reuse the sigma-clipped values that detect_trails()
    # already computed, if available. Saves ~80 ms on a 60 MP frame
    # by skipping the full re-pass over 100k+ sky pixels. Falls back
    # to local computation only when detect_trails() didn't run or
    # found no trails (in which case there's nothing to recommend
    # anyway, but the local computation keeps the function self-
    # contained for external callers).
    sky_med = float(getattr(detection, "sky_med", 0.0) or 0.0)
    sky_sigma = float(getattr(detection, "sky_sigma", 0.0) or 0.0)
    if sky_sigma <= 0:
        outside = mono[detection.mask == 0]
        if outside.size > 1000:
            vals = outside.astype(np.float32)
            for _ in range(4):
                if vals.size < 100:
                    break
                m = float(np.median(vals))
                s = float(np.median(np.abs(vals - m))) * 1.4826
                sky_med = m
                if s > 0:
                    sky_sigma = s
                if s <= 0:
                    break
                keep = np.abs(vals - m) < 3.0 * s
                if int(keep.sum()) == vals.size:
                    break
                vals = vals[keep]

    mask_area = int((detection.mask > 0).sum())

    # ---- Feature 1: cross-trail gradient ----
    gradient_strength = 0.0  # in units of sky σ
    if L >= 1.0 and sky_sigma > 0:
        px = -dy / L; py = dx / L  # perpendicular unit vector
        offset = 30.0              # px from centreline
        half = 5                   # ±strip thickness
        n_samples = 40
        left_vals, right_vals = [], []
        for i in range(n_samples):
            t = i / max(n_samples - 1, 1)
            cx = x1 + dx * t; cy = y1 + dy * t
            for d in range(-half, half + 1):
                # Walk along the line direction by d for thickness sampling
                tx = d * (dx / L); ty = d * (dy / L)
                for off, bucket in ((-offset, left_vals), (offset, right_vals)):
                    sx = int(round(cx + off * px + tx))
                    sy = int(round(cy + off * py + ty))
                    if 0 <= sx < w and 0 <= sy < h and detection.mask[sy, sx] == 0:
                        bucket.append(float(mono[sy, sx]))
        if len(left_vals) >= 30 and len(right_vals) >= 30:
            ml = float(np.median(left_vals))
            mr = float(np.median(right_vals))
            gradient_strength = abs(ml - mr) / sky_sigma

    # ---- Feature 2: pearl / peak count along trail centreline ----
    pearl_count = 0
    if L >= 50 and sky_sigma > 0:
        peak_thr = sky_med + 5.0 * sky_sigma
        # Sample a 1-D profile along the centreline
        n_pts = int(min(L, 4000))
        ts = np.linspace(0.0, 1.0, n_pts)
        xs = np.clip(np.round(x1 + dx * ts).astype(int), 0, w - 1)
        ys = np.clip(np.round(y1 + dy * ts).astype(int), 0, h - 1)
        profile = mono[ys, xs]
        bright = profile > peak_thr
        # Count connected runs of bright pixels = peak count
        if bright.any():
            transitions = np.diff(bright.astype(np.int8))
            pearl_count = int((transitions == 1).sum())
            if bright[0]:
                pearl_count += 1

    # ---- Decision tree ----
    if gradient_strength >= 2.0:
        return (
            "perp_strip",
            f"Strong sky gradient ({gradient_strength:.1f}σ) across the "
            "trail — Perpendicular Strip Median preserves it. "
            "PDE methods (Harmonic / Biharmonic) would average it away."
        )
    if pearl_count >= 5:
        return (
            "perp_strip",
            f"{pearl_count} bright peaks along the trail axis "
            "('flashing satellite' / tumbling debris). "
            "Perpendicular Strip Median's median operator quietly "
            "rejects the pearl peaks; PDE methods risk overshoot."
        )
    if length_frac < 0.08 and mask_area < 4000:
        return (
            "harmonic",
            f"Short compact mask ({mask_area:,} px, "
            f"{length_frac * 100:.1f}% of diagonal) — Harmonic / Laplace "
            "gives the smoothest physical fill. Combine with "
            "Match-sky-noise for realistic texture."
        )
    if gradient_strength < 0.8 and pearl_count <= 2:
        return (
            "harmonic",
            "Uniform sky, no pearl pattern detected. "
            "Harmonic / Laplace + Match-sky-noise gives a smooth, "
            "physically motivated fill. Perpendicular Strip Median is a "
            "safe alternative."
        )
    # Default fall-through
    return (
        "perp_strip",
        "Mixed conditions detected — Perpendicular Strip Median is the "
        "robust default for typical satellite trails."
    )


def detect_trails(
    mono: np.ndarray, params: DetectionParams,
    progress_cb=None,
    mrt_cache: dict | None = None,
    cache_key=None,
) -> TrailDetection:
    """Detect satellite trails via STScI's findsat_mrt.TrailFinder.

    Returns ``TrailDetection`` with ``lines`` = list of (x1, y1, x2, y2)
    endpoints in image coordinates (y=0 at row 0 of the numpy array).
    See module docstring for the algorithmic rationale.

    ``progress_cb`` (optional callable) receives a string for each
    pipeline phase: "preprocess", "mrt", "mrt_cached", "peaks", "filter",
    "mask". Used by the UI to update a progress bar / status label.

    ``mrt_cache`` + ``cache_key`` enable cross-call reuse of the
    expensive MRT computation. When the caller passes the same
    ``cache_key`` again the MRT itself is reused and only the
    (post-MRT) peak detection + per-candidate filtering re-runs --
    giving a ~5-10x speedup when the user is iterating on SNR
    threshold, max_width, or persistence settings.
    """
    def _emit(stage: str) -> None:
        if progress_cb is not None:
            try:
                progress_cb(stage)
            except Exception:
                pass

    h, w = mono.shape
    diag = float(np.hypot(h, w))
    notes_parts: list[str] = []

    if not _HAVE_FINDSAT_MRT:
        return TrailDetection(
            lines=[], mask=np.zeros((h, w), dtype=np.uint8),
            star_mask=np.zeros((h, w), dtype=np.uint8),
            effective_mask=np.zeros((h, w), dtype=np.uint8),
            diag_px=diag,
            notes="acstools is not installed -- detection unavailable. "
                  "Run `pip install acstools`.",
        )

    # ---- Preprocessing per TrailFinder docstring recommendation ----
    # Subtract median background so the noise stats are centred on zero.
    _emit("preprocess")
    mono_f = mono.astype(np.float32, copy=True)
    if not np.all(np.isfinite(mono_f)):
        mono_f = np.where(np.isfinite(mono_f), mono_f, 0.0)
    bg = float(np.nanmedian(mono_f))
    mono_f -= bg

    # ---- Downsample for speed ----
    # MRT cost scales as O(image_area * n_theta). A 2x downsample is 4x
    # cheaper, 4x downsample is 16x cheaper. Trails ~5000 px long are
    # still > 1000 px at 4x -- well above min_length. Endpoints are
    # scaled back to full-res after detection.
    ds = max(1, int(params.downsample))
    if ds > 1:
        ds_h = max(8, h // ds)
        ds_w = max(8, w // ds)
        mono_ds = cv2.resize(
            mono_f, (ds_w, ds_h), interpolation=cv2.INTER_AREA,
        )
    else:
        mono_ds = mono_f
        ds_h, ds_w = h, w

    # ---- TrailFinder ----
    # min_length is in MRT/image pixels of whatever image we feed in. If
    # we downsample, we want the same effective trail length, so scale the
    # threshold down by the downsample factor (e.g. min_length=50 full-res
    # becomes 12 px at 4x downsample).
    ds_min_length = max(8, int(round(params.min_length / max(ds, 1))))

    theta = np.arange(0.0, 180.0, float(params.theta_step_deg), dtype=np.float32)

    # Build kwargs adaptively so older / newer acstools releases that have
    # renamed parameters still work.
    base_kwargs = dict(
        image=mono_ds,
        threshold=float(params.snr_threshold),
        min_length=ds_min_length,
        max_width=int(params.max_width),
        check_persistence=bool(params.check_persistence),
        min_persistence=float(params.min_persistence),
        persistence_chunk=max(20, int(params.persistence_chunk / max(ds, 1))),
        min_persistence_snr=float(params.min_persistence_snr),
        processes=int(params.processes),
        theta=theta,
    )

    def _make_finder(kw):
        try:
            return TrailFinder(**kw)
        except TypeError:
            # Strip optional kwargs that this acstools version doesn't accept.
            for k in ("theta", "min_persistence_snr", "persistence_chunk",
                      "min_persistence", "check_persistence", "processes"):
                kw.pop(k, None)
            return TrailFinder(**kw)

    # ---- Cache-aware MRT execution ----
    # Cache is keyed on (path, downsample, theta_step) by the caller; we
    # additionally check that the cached image shape matches what we're
    # about to feed in (defence against bug).
    cached = None
    if mrt_cache is not None and cache_key is not None:
        cached = mrt_cache.get(cache_key)
        if cached is not None and getattr(cached, "image", None) is not None:
            try:
                if cached.image.shape != mono_ds.shape:
                    cached = None  # invalidate, dimensions differ
            except Exception:
                cached = None

    try:
        if cached is not None:
            # Reuse the cached MRT. Update only the post-MRT thresholds in
            # place so the user's slider changes take effect without a
            # full recompute.
            finder = cached
            for attr, value in (
                ("threshold", float(params.snr_threshold)),
                ("max_width", int(params.max_width)),
                ("check_persistence", bool(params.check_persistence)),
                ("min_persistence", float(params.min_persistence)),
                ("min_persistence_snr", float(params.min_persistence_snr)),
                ("persistence_chunk",
                    max(20, int(params.persistence_chunk / max(ds, 1)))),
            ):
                try:
                    setattr(finder, attr, value)
                except Exception:
                    pass
            try:
                _emit("mrt_cached")
                _emit("peaks")
                finder.find_mrt_sources()
                _emit("filter")
                finder.filter_sources()
                _emit("mask")
                finder.make_mask()
            except AttributeError:
                # Older acstools without per-phase methods -> fall back
                # to full re-run, no cache benefit this call.
                finder = _make_finder(base_kwargs)
                _emit("mrt")
                finder.run_all()
        else:
            finder = _make_finder(base_kwargs)
            # Run the four phases individually so we can emit progress
            # between each. If the acstools release we have doesn't
            # expose them separately we fall back to run_all().
            try:
                _emit("mrt")
                finder.run_mrt()
                _emit("peaks")
                finder.find_mrt_sources()
                _emit("filter")
                finder.filter_sources()
                _emit("mask")
                finder.make_mask()
            except AttributeError:
                _emit("mrt")
                finder.run_all()

        # Populate cache after a successful run (or after a successful
        # reuse: idempotent update).
        if mrt_cache is not None and cache_key is not None:
            mrt_cache[cache_key] = finder
    except Exception as exc:
        log.debug("TrailFinder failed: %s", exc, exc_info=True)
        return TrailDetection(
            lines=[], mask=np.zeros((h, w), dtype=np.uint8),
            star_mask=np.zeros((h, w), dtype=np.uint8),
            effective_mask=np.zeros((h, w), dtype=np.uint8),
            diag_px=diag,
            notes=f"TrailFinder error: {exc.__class__.__name__}: {exc}",
        )

    # ---- Pull accepted trails out of the source list ----
    accepted: list[tuple[int, int, int, int]] = []
    source_list = getattr(finder, "source_list", None)
    n_total = 0
    n_status_ok = 0
    if source_list is not None:
        try:
            n_total = len(source_list)
        except Exception:
            n_total = 0
        # TrailFinder marks accepted candidates with status == 2
        # (1 = SNR filtered out, 0 = duplicates removed). Older versions
        # may not have a status column -- in that case all rows are taken.
        for row in source_list:
            keep = True
            try:
                status = int(row["status"])
                keep = (status == 2)
            except Exception:
                keep = True
            if not keep:
                continue
            n_status_ok += 1
            # Endpoints come back in the *downsampled* image coords --
            # _trailfinder_endpoints derives them from rho/theta against
            # the array TrailFinder was actually given. Scale to full-res.
            ep = _trailfinder_endpoints(row, ds_w, ds_h)
            if ep is None:
                continue
            x1, y1, x2, y2 = ep
            if ds > 1:
                x1 *= ds
                x2 *= ds
                y1 *= ds
                y2 *= ds
            x1 = int(np.clip(x1, 0, w - 1))
            x2 = int(np.clip(x2, 0, w - 1))
            y1 = int(np.clip(y1, 0, h - 1))
            y2 = int(np.clip(y2, 0, h - 1))
            # Extend to image boundary so the dilated mask covers the
            # full sweep of the trail, including the faint PSF-tail
            # ends that TrailFinder truncates.
            x1, y1, x2, y2 = _extend_endpoints_to_boundary(
                x1, y1, x2, y2, w, h,
            )
            accepted.append((x1, y1, x2, y2))

    # Diagnostic for the status bar
    if not accepted:
        if n_total == 0:
            notes_parts.append(
                "findsat_mrt found no candidates. Lower SNR threshold "
                "or relax max_width / min_length."
            )
        else:
            notes_parts.append(
                f"findsat_mrt: {n_total} candidate(s) -> "
                f"{n_status_ok} status OK, 0 with valid endpoints."
            )
    elif n_total > len(accepted):
        notes_parts.append(
            f"findsat_mrt: {n_total} candidate(s) -> "
            f"{len(accepted)} accepted (rest filtered by width / "
            "persistence / SNR)."
        )

    # ---- Build masks from accepted lines ----
    mask = np.zeros((h, w), dtype=np.uint8)
    for (x1, y1, x2, y2) in accepted:
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=1)
    if accepted and params.dilation_radius > 0:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (2 * params.dilation_radius + 1, 2 * params.dilation_radius + 1),
        )
        mask = cv2.dilate(mask, k)

    # ---- Bright-halo growth (v0.7.4) ----
    # A "flashing satellite" / tumbling-debris trail has periodic bright
    # peaks (pearls) whose PSF halos extend WIDER than the trail itself.
    # A fixed-radius dilation covers the line but truncates the pearls,
    # leaving a ring of bright pixels just outside the mask. Inpaint
    # then fills the mask centre with sky but the ring survives,
    # producing the classic "string of pearls" remnant in the output.
    #
    # Fix: any bright pixel (> sky + Nσ) that is in the same connected
    # component as the current mask is absorbed into it. The mask
    # follows the actual bright structure regardless of cross-section.
    # This is cheap (one connectedComponents pass) and degenerates to
    # a no-op on uniform trails.
    # Sky stats — kept at function scope so they survive the halo-growth
    # branch and can be persisted on the TrailDetection result for
    # downstream consumers (analyse_trail_profile, _match_sky_noise) to
    # reuse instead of re-running their own sigma-clip pass.
    sky_med_out = 0.0
    sky_sigma_out = 0.0
    if accepted and mask.any():
        outside_pixels = mono[mask == 0].astype(np.float32)
        if outside_pixels.size > 1000:
            # Sigma-clipped sky stats. Plain MAD breaks when the field
            # contains an extended bright source (comet halo, nebula,
            # galaxy halo): those pixels inflate the median absolute
            # deviation by 10-100×, pushing sky+Nσ so high that no
            # pearl pixel qualifies and halo growth does nothing.
            # Iteratively reject pixels >3σ from the running median
            # until the surviving population is stable.
            vals = outside_pixels
            sky_med = float(np.median(vals))
            sky_mad = 0.0
            for _ in range(5):
                if vals.size < 100:
                    break
                m = float(np.median(vals))
                s = float(np.median(np.abs(vals - m))) * 1.4826
                # Always commit the current (m, s) estimate before any
                # exit branch — otherwise a degenerate first-iteration
                # case (s == 0 because the surviving pixels are all
                # identical, which is rare but real on flat synthetic
                # data) would leave sky_mad at its 0.0 sentinel and
                # disable halo growth entirely.
                sky_med = m
                if s > 0:
                    sky_mad = s
                if s <= 0:
                    break
                keep = np.abs(vals - m) < 3.0 * s
                if int(keep.sum()) == vals.size:
                    break
                vals = vals[keep]

            # Lift to the function scope so the result carries them.
            sky_med_out = sky_med
            sky_sigma_out = sky_mad

            if sky_mad > 0:
                # Bounded iterative dilation into bright pixels. Each
                # hop grows the mask by exactly 1 px (3×3 SE) AND
                # restricts new pixels to those above sky + Nσ. The
                # hop cap prevents runaway growth along a thin bright
                # bridge into an unrelated extended source.
                bright_thr = sky_med + 3.0 * sky_mad
                bright = mono > bright_thr
                growth = (mask > 0)
                max_hops = 25
                kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                hops_used = 0
                for hop in range(max_hops):
                    growth_u8 = growth.astype(np.uint8)
                    dilated = cv2.dilate(growth_u8, kern).astype(bool)
                    new_pix = dilated & bright & ~growth
                    if not new_pix.any():
                        break
                    growth = growth | new_pix
                    hops_used = hop + 1
                grown_count = int(growth.sum() - (mask > 0).sum())
                bright_total = int(bright.sum())
                if grown_count > 0:
                    mask = np.where(
                        growth, np.uint8(255), mask,
                    ).astype(np.uint8)
                notes_parts.append(
                    f"halo growth: +{grown_count} px in {hops_used} hops "
                    f"(sky={sky_med:.1f}±{sky_mad:.1f}, "
                    f"thr={bright_thr:.1f}, bright px={bright_total})"
                )

    star_mask = (
        _detect_star_mask(mono, params)
        if accepted else np.zeros((h, w), dtype=np.uint8)
    )
    # Discard "star" detections that fall inside the *entire dilated
    # trail mask*. A bright trail produces many local maxima along its
    # length which find_peaks misclassifies as stars, and each peak is
    # dilated by `star_dilation` (default 4 px) producing 9-px circles
    # that completely cover the trail. If those circles remained in
    # star_mask, the inpaint mask would be cleared in the trail region
    # and the trail would survive Apply unchanged. Real stars far from
    # the trail are outside `mask` to begin with -- they don't need
    # protection because the inpaint never touches them.
    if accepted and star_mask.any():
        star_mask = star_mask.copy()
        star_mask[mask > 0] = 0

    effective = mask.copy()
    if accepted:
        effective[star_mask > 0] = 0

    result = TrailDetection(
        lines=accepted,
        mask=mask,
        star_mask=star_mask,
        effective_mask=effective,
        diag_px=diag,
        notes="; ".join(notes_parts),
    )
    # Carry the just-computed sigma-clipped sky stats so downstream
    # consumers (analyse_trail_profile, _match_sky_noise) can skip
    # their own pass on 100k+ pixels. ~80 ms saved per Detect on 60 MP.
    result.sky_med = sky_med_out
    result.sky_sigma = sky_sigma_out

    # Inpaint-method recommendation: cheap (~10 ms even on 15 MP) so
    # it always runs when we have at least one accepted trail. Empty
    # rec stays as "" defaults from the constructor when no trails
    # were found.
    if accepted:
        try:
            rec_method, rec_rationale = analyse_trail_profile(mono, result)
            result.recommended_method = rec_method
            result.recommendation_rationale = rec_rationale
        except Exception as exc:
            log.debug("analyse_trail_profile failed: %s", exc, exc_info=True)

    return result


# ------------------------------------------------------------------------------
# INPAINTING
# ------------------------------------------------------------------------------

def _inpaint_cv2_fmm(
    plane: np.ndarray, mask: np.ndarray, flag: int,
) -> np.ndarray:
    """Shared OpenCV inpaint path — used by both Telea (FMM) and
    Navier-Stokes (NS). They differ only in the algorithm flag passed
    to ``cv2.inpaint``.

    Routes the plane through uint8 (with percentile-based linear scaling
    to preserve dynamic range in the inpaint region) because cv2.inpaint
    silently no-ops on float32 / uint16 inputs on several macOS / Apple-
    Silicon OpenCV builds. The percentile scaling clips the brightest
    1 % of pixels (typically saturated stars — not inpainted anyway) so
    the sky values get most of the 0-255 range, which preserves the
    bit-depth that actually matters for the fill.

    Precision: 8-bit in the masked region only; all unmasked pixels
    keep their full original precision exactly.
    """
    if not mask.any():
        return plane.copy()

    src_dtype = plane.dtype
    radius = 3

    if src_dtype == np.uint8:
        mask_u8 = mask.astype(np.uint8) if mask.dtype != np.uint8 else mask
        return cv2.inpaint(plane, mask_u8, radius, flag)

    # Scale to uint8 [0, 255] via percentile so the cv2 call sees a
    # well-conditioned image. Bright stars saturate to 255 (irrelevant —
    # we don't inpaint star pixels) and sky values get most of the
    # 0-255 range to themselves.
    plane_f = plane.astype(np.float32, copy=False)
    lo = float(np.percentile(plane_f, 1.0))
    hi = float(np.percentile(plane_f, 99.5))
    if hi - lo < 1e-6:
        lo = float(plane_f.min())
        hi = float(plane_f.max())
    span = max(hi - lo, 1e-6)

    norm = (plane_f - lo) * (255.0 / span)
    np.clip(norm, 0.0, 255.0, out=norm)
    plane_u8 = norm.astype(np.uint8)
    mask_u8 = mask.astype(np.uint8) if mask.dtype != np.uint8 else mask

    inp_u8 = cv2.inpaint(plane_u8, mask_u8, radius, flag)

    inp_f = inp_u8.astype(np.float32) * (span / 255.0) + lo
    out = plane.copy()
    masked = mask > 0
    if np.issubdtype(src_dtype, np.integer):
        info = np.iinfo(src_dtype)
        out[masked] = np.clip(
            np.round(inp_f[masked]), info.min, info.max,
        ).astype(src_dtype)
    else:
        out[masked] = inp_f[masked].astype(src_dtype)
    return out


def _inpaint_cv2_telea(plane: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fast Marching Method inpaint via cv2.inpaint(INPAINT_TELEA).

    Telea 2004: each masked pixel is filled as a normalised weighted
    sum of its known neighbours, with weights depending on geometric
    distance and surface direction. Fast Marching processes pixels in
    order of distance from the boundary — fastest of the cv2 methods.
    Quality: visually smooth, may slightly blur fine structure.
    """
    return _inpaint_cv2_fmm(plane, mask, cv2.INPAINT_TELEA)


def _inpaint_cv2_navier_stokes(
    plane: np.ndarray, mask: np.ndarray,
) -> np.ndarray:
    """Inpaint via cv2.inpaint(INPAINT_NS).

    Bertalmio, Bertozzi & Sapiro 2001: models the inpaint region as a
    fluid and propagates isophotes (level curves of intensity) into
    the masked area while preserving local image smoothness. For
    sky-dominated regions the result is essentially harmonic
    (Laplace-like); for textured regions it preserves edge direction
    better than Telea. Slightly slower than Telea but same complexity
    class — both run in well under a second on a typical trail mask.
    """
    return _inpaint_cv2_fmm(plane, mask, cv2.INPAINT_NS)


def _inpaint_biharmonic(plane: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Biharmonic inpainting: solves ∇⁴u = 0 inside the mask with the
    surrounding sky as Dirichlet boundary. Mathematically optimal
    smooth interpolation (minimum thin-plate energy).

    Chunked along the trail's principal axis (v0.7.4) — skimage's sparse
    biharmonic solver becomes numerically ill-conditioned on very long,
    thin masks (typical: 5000×14 px), producing a periodic "string of
    pearls" artefact along the centreline. The fix: split the mask into
    overlapping segments of ~CHUNK_LEN pixels along its longest axis,
    solve each segment in its own bbox crop with a halo of Dirichlet
    boundary, and paste back. Each sub-problem is roughly square so the
    sparse matrix stays well-conditioned. Short / blob-like masks fall
    through to the original single-pass code path.

    Halo (150 px) is wide enough that skimage's solver sees enough sky
    on every side to stabilise the PDE away from crop edges. Chunks
    overlap by HALO so neighbouring solutions agree at their seams.
    """
    if not mask.any():
        return plane.copy()
    try:
        from skimage.restoration import inpaint_biharmonic
    except ImportError:
        return _inpaint_cv2_ns(plane, mask)

    src_dtype = plane.dtype
    mask_bool = mask > 0
    h, w = plane.shape

    ys, xs = np.where(mask_bool)
    if ys.size == 0:
        return plane.copy()

    # Normalise plane to [0,1]-ish range once for skimage's internal
    # normalisation (works better than tiny ~0.02 sky values).
    if np.issubdtype(src_dtype, np.integer):
        info = np.iinfo(src_dtype)
        scale = 1.0 / float(max(info.max, 1))
        plane_f = plane.astype(np.float32) * scale
    else:
        plane_f = plane.astype(np.float32)
        scale = 1.0

    HALO = 150
    CHUNK_LEN = 250  # px along principal axis per sub-problem
    out = plane.copy()

    def _solve_segment(
        seg_mask_full: np.ndarray,
    ) -> None:
        """Crop bbox+halo, biharmonic, paste back into ``out``."""
        seg_ys, seg_xs = np.where(seg_mask_full)
        if seg_ys.size == 0:
            return
        y0 = max(0, int(seg_ys.min()) - HALO)
        y1 = min(h, int(seg_ys.max()) + 1 + HALO)
        x0 = max(0, int(seg_xs.min()) - HALO)
        x1 = min(w, int(seg_xs.max()) + 1 + HALO)

        crop_f = plane_f[y0:y1, x0:x1]
        crop_mask = seg_mask_full[y0:y1, x0:x1]
        if not crop_mask.any():
            return
        try:
            crop_result = inpaint_biharmonic(crop_f, crop_mask)
        except Exception as exc:
            log.warning(
                "Biharmonic chunk failed (%s); falling back to "
                "nearest-neighbour for this segment", exc,
            )
            ny_full = seg_mask_full.copy()
            fb = _inpaint_cv2_ns(plane, ny_full)
            out[ny_full] = fb[ny_full]
            return

        if np.issubdtype(src_dtype, np.integer):
            info = np.iinfo(src_dtype)
            crop_back = np.clip(
                np.round(crop_result / scale), info.min, info.max,
            ).astype(src_dtype)
        else:
            crop_back = crop_result.astype(src_dtype)

        out_view = out[y0:y1, x0:x1]
        out_view[crop_mask] = crop_back[crop_mask]

    # Principal-axis projection via covariance eigenvector.
    pts = np.column_stack((ys.astype(np.float64), xs.astype(np.float64)))
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    # 2x2 covariance — eigenvector for largest eigenvalue is the axis.
    cov = np.cov(centered, rowvar=False)
    try:
        eigvals, eigvecs = np.linalg.eigh(cov)
        axis = eigvecs[:, int(np.argmax(eigvals))]
    except np.linalg.LinAlgError:
        axis = np.array([0.0, 1.0])

    proj = centered @ axis
    pmin, pmax = float(proj.min()), float(proj.max())
    extent = pmax - pmin

    # If the mask is short or roughly square, skip chunking — the
    # single-pass solver is well-conditioned and ~2× faster.
    if extent < CHUNK_LEN * 1.5:
        _solve_segment(mask_bool)
        return out

    # Build chunk boundaries along the principal axis with overlap so
    # adjacent segments share boundary pixels and produce a smooth seam.
    n_chunks = int(np.ceil(extent / CHUNK_LEN))
    step = extent / n_chunks
    # 20 % overlap (was 50 %, v0.8.8). The Dirichlet boundary for each
    # chunk comes from the 150-px halo around its bbox (sky pixels
    # outside the mask), NOT from the mask-side overlap region. So the
    # overlap only needs to be wide enough to bridge any single-pixel
    # seam between adjacent chunks. 20 % gives us a comfortable safety
    # margin while halving the per-pixel solver cost (previously each
    # interior pixel was solved by two chunks; now by ~1.2 on average).
    overlap = step * 0.2

    for k in range(n_chunks):
        lo = pmin + k * step - overlap
        hi = pmin + (k + 1) * step + overlap
        sel = (proj >= lo) & (proj <= hi)
        if not sel.any():
            continue
        seg_full = np.zeros_like(mask_bool)
        seg_full[ys[sel], xs[sel]] = True
        _solve_segment(seg_full)

    return out


def _inpaint_cv2_ns(plane: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Inpaint the masked region of ``plane``.

    Despite the name (kept for backwards compatibility with the rest of
    the codebase), this no longer uses cv2.inpaint -- the OpenCV Python
    binding silently no-ops on CV_16UC1 / CV_32FC1 inputs on several
    macOS / Apple-Silicon builds, and the uint8 round-trip workaround
    has its own failure modes.

    The implementation here uses a Euclidean Distance Transform
    (scipy.ndimage.distance_transform_edt): for every pixel inside the
    mask, we look up the (y, x) of the NEAREST pixel outside the mask
    and copy its value. A subsequent small Gaussian blur ONLY inside
    the mask softens any visible staircase artefact at the centreline
    where the two perpendicular fills meet.

    This is mathematically deterministic, dtype-preserving, and
    guaranteed to actually modify pixels -- no silent failure modes.
    """
    if not mask.any():
        return plane.copy()
    try:
        from scipy.ndimage import distance_transform_edt, gaussian_filter
    except ImportError:
        # Last-resort fallback: just fill the mask with the global
        # background median. Visually inferior but still better than
        # leaving the trail untouched.
        out = plane.copy()
        bg = float(np.median(plane[mask == 0])) if (mask == 0).any() else 0.0
        out[mask > 0] = (
            np.clip(bg, 0, 65535).astype(plane.dtype)
            if np.issubdtype(plane.dtype, np.integer)
            else plane.dtype.type(bg)
        )
        return out

    invalid = mask > 0
    # Distance transform: distances (max distance ≈ half-thickness of mask)
    # AND indices of the nearest unmasked pixel, both in one pass.
    dist, (idx_y, idx_x) = distance_transform_edt(invalid, return_indices=True)

    # Step 1: nearest-neighbour fill
    work = plane.astype(np.float32, copy=True)
    work[invalid] = plane[idx_y[invalid], idx_x[invalid]].astype(np.float32)

    # Step 2: feather the filled region with a Gaussian. σ scales with
    # the mask thickness so wider masks (large dilation) get more
    # smoothing — that hides the centreline ridge where fills from
    # opposite sides of the trail collide.
    max_thickness = float(dist[invalid].max()) if invalid.any() else 1.0
    sigma = max(1.0, min(8.0, max_thickness * 0.75))
    blurred = gaussian_filter(work, sigma=sigma)
    work[invalid] = blurred[invalid]

    out = plane.copy()
    if np.issubdtype(plane.dtype, np.integer):
        info = np.iinfo(plane.dtype)
        out[invalid] = np.clip(
            np.round(work[invalid]), info.min, info.max,
        ).astype(plane.dtype)
    else:
        out[invalid] = work[invalid].astype(plane.dtype)
    return out


def _inpaint_harmonic(
    plane: np.ndarray, mask: np.ndarray,
    max_iter: int = 400, tol: float | None = None,
) -> np.ndarray:
    """Harmonic (Laplace) inpainting: solves ∇²u = 0 inside the mask
    with the surrounding sky as Dirichlet boundary.

    Mathematical contrast to biharmonic (∇⁴u = 0): the Laplace
    equation HAS a maximum principle — the inpainted values are
    bounded by the boundary minima/maxima. That eliminates the
    'string of pearls' overshoot/undershoot artefact that breaks
    biharmonic on long thin masks. The trade-off: the harmonic
    solution is smoother (it can produce a visible 'soft patch'
    where a real-noise sky should be). That's exactly what the
    Match-sky-noise post-step is for — physical fill + statistical
    noise on top recovers the look of real sky.

    Implementation: bbox-crop with halo for boundary context, seed
    with a nearest-neighbour fill (gives the iteration a good warm
    start), then run Gauss-Seidel-style 5-point Laplace smoothing
    inside the mask only. Outside-mask pixels stay locked at their
    original values, so the boundary condition is enforced at every
    iteration without an explicit linear-system build.

    Convergence (v0.8.8 tuned): max_iter dropped 800 → 400; tol is
    dtype-adaptive instead of a fixed 1e-4. For uint16 inputs we
    converge when no masked pixel changes by more than 1 ADU between
    32-iteration checks (tol = 1.0/65535). For float inputs we use
    a relative 1e-6 tol on the (already roughly [0, 1]-scaled) plane.
    On typical 5000×15 px masks the loop now exits in ~150-300
    iterations instead of running to the old 800-cap. Visual delta
    against the higher iteration count is below the sky-noise floor.
    """
    if not mask.any():
        return plane.copy()
    src_dtype = plane.dtype
    h, w = plane.shape
    mask_bool = mask > 0

    # Dtype-adaptive convergence threshold. uint16: 1 ADU is the
    # smallest distinguishable value. float: noise floor of a normalised
    # astro frame is ~1e-4, so a 1e-6 tol stops solving once the masked
    # interior has settled well below the sky-noise level. The caller
    # can still force a specific tol if needed.
    if tol is None:
        if np.issubdtype(src_dtype, np.integer):
            tol = 1.0  # 1 ADU on the integer scale
        else:
            tol = 1e-6  # well below the sky-noise floor on normalised data

    # Bbox crop with halo for sufficient boundary context.
    ys, xs = np.where(mask_bool)
    halo = 8  # 5-point Laplace decays fast — small halo is enough
    y0 = max(0, int(ys.min()) - halo)
    y1 = min(h, int(ys.max()) + 1 + halo)
    x0 = max(0, int(xs.min()) - halo)
    x1 = min(w, int(xs.max()) + 1 + halo)
    crop = plane[y0:y1, x0:x1].astype(np.float32, copy=True)
    crop_mask = mask_bool[y0:y1, x0:x1]

    # Warm start: seed the masked region with nearest-neighbour values.
    # Without it, Jacobi/Gauss-Seidel iteration starts from arbitrary
    # values inside the mask and needs many more iterations to converge.
    try:
        from scipy.ndimage import distance_transform_edt
        _, (iy, ix) = distance_transform_edt(
            crop_mask, return_indices=True,
        )
        seeded = crop.copy()
        seeded[crop_mask] = crop[iy[crop_mask], ix[crop_mask]]
        crop = seeded
    except ImportError:
        # No scipy: fall back to global median seed (still better than
        # leaving the masked region at its trail brightness).
        bg = float(np.median(crop[~crop_mask])) if (~crop_mask).any() else 0.0
        crop[crop_mask] = bg

    # 5-point Laplace iteration. cv2.filter2D handles edge replication
    # automatically; we re-lock the non-mask pixels each iteration so
    # they act as Dirichlet boundary conditions.
    kern = np.array(
        [[0.0, 0.25, 0.0],
         [0.25, 0.0, 0.25],
         [0.0, 0.25, 0.0]],
        dtype=np.float32,
    )
    original_crop = plane[y0:y1, x0:x1].astype(np.float32, copy=True)
    prev_inside = crop[crop_mask].copy()
    for it in range(max_iter):
        avg = cv2.filter2D(crop, -1, kern, borderType=cv2.BORDER_REPLICATE)
        # Update only inside the mask; outside stays at original value.
        crop[crop_mask] = avg[crop_mask]
        # Re-lock non-mask pixels (cv2.filter2D didn't touch them at
        # this step but a future change might; cheap insurance).
        crop[~crop_mask] = original_crop[~crop_mask]
        # Convergence check every 32 iterations: max absolute change of
        # any masked pixel since the last check. tol is in the same
        # units as the input (typically 1e-4 of full range — ~7 ADU
        # at 16-bit).
        if (it & 31) == 31:
            cur_inside = crop[crop_mask]
            delta = float(np.max(np.abs(cur_inside - prev_inside)))
            if delta < tol:
                break
            prev_inside = cur_inside.copy()

    out = plane.copy()
    out_view = out[y0:y1, x0:x1]
    if np.issubdtype(src_dtype, np.integer):
        info = np.iinfo(src_dtype)
        out_view[crop_mask] = np.clip(
            np.round(crop[crop_mask]), info.min, info.max,
        ).astype(src_dtype)
    else:
        out_view[crop_mask] = crop[crop_mask].astype(src_dtype)
    return out


def _inpaint_perpendicular_strip(
    plane: np.ndarray,
    detection: TrailDetection,
    strip_width: int,
) -> np.ndarray:
    """Fill the dilated mask region with the median of perpendicular sky.

    Rotates the image so the trail is horizontal, then for every column
    in rotated space replaces the masked pixels with the median of the
    ``strip_width`` unmasked pixels immediately above and below the
    masked stripe. Rotation back uses bilinear interpolation; the final
    output keeps original pixel values outside the mask exactly.

    Fills the ENTIRE dilated mask region, not just the centreline
    (the previous bug). Vectorised with numpy instead of a per-pixel
    Python loop, ~10x faster for typical trail sizes.

    Falls back to nearest-neighbour for masked pixels where no
    above-or-below sky samples are available (e.g. image-edge cases).
    """
    if not detection.lines or not detection.effective_mask.any():
        return plane.copy()

    h, w = plane.shape
    src_dtype = plane.dtype
    plane_f = plane.astype(np.float32, copy=False)
    mask_full = (detection.effective_mask > 0).astype(np.float32)

    # The accepted lines all describe (approximately) the same orientation
    # in practice (a single trail), but a frame may have multiple. We
    # process each line independently so different orientations are handled
    # correctly; the mask region we fill per line is the FULL dilated
    # effective mask (subset of pixels close to this line).
    out = plane_f.copy()
    handled = np.zeros((h, w), dtype=bool)

    selected = detection.selected_lines if detection.selected_lines else detection.lines
    for (x1, y1, x2, y2) in selected:
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        length = float(np.hypot(dx, dy))
        if length < 1.0:
            continue
        angle_deg = float(np.degrees(np.arctan2(dy, dx)))

        # Rotate image and mask so the line is horizontal in the working
        # frame. Use cv2.warpAffine (much faster than scipy.ndimage.rotate
        # for large images -- single-shot affine warp via SIMD vs.
        # iterative spline interpolation). cv2.BORDER_CONSTANT with NaN
        # marks padding so per-column nanmedian later excludes those
        # pixels automatically.
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        M = cv2.getRotationMatrix2D((cx, cy), -angle_deg, 1.0)
        img_rot = cv2.warpAffine(
            plane_f, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=float('nan'),
        )
        mask_rot_f = cv2.warpAffine(
            mask_full, M, (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        )
        mask_rot = mask_rot_f > 0.5

        if not mask_rot.any():
            continue

        rh, rw = img_rot.shape

        # For each column find the top and bottom of the masked stripe.
        any_col = mask_rot.any(axis=0)
        if not any_col.any():
            continue
        # Top row of mask per column (0 if not present, then masked by any_col)
        top_rows = np.argmax(mask_rot, axis=0)
        # Bottom row = rh - 1 - argmax-from-bottom
        bot_rows = rh - 1 - np.argmax(mask_rot[::-1, :], axis=0)

        # Sample `strip_width` rows above the mask (rows top-1, top-2, ...)
        # and `strip_width` rows below. Clip to image. Out-of-range or NaN
        # samples are filtered out per-column.
        sw = max(1, int(strip_width))
        col_idx = np.arange(rw)

        # Indexing: build 2D arrays of (offset, column) -> sampled row index
        offsets = np.arange(1, sw + 1)
        above_rows = top_rows[None, :] - offsets[:, None]   # shape (sw, rw)
        below_rows = bot_rows[None, :] + offsets[:, None]
        above_rows = np.clip(above_rows, 0, rh - 1)
        below_rows = np.clip(below_rows, 0, rh - 1)

        # Sample values
        above_vals = img_rot[above_rows, col_idx[None, :]]
        below_vals = img_rot[below_rows, col_idx[None, :]]
        samples = np.concatenate([above_vals, below_vals], axis=0)  # (2sw, rw)
        col_medians = np.nanmedian(samples, axis=0)   # NaNs (padding) ignored

        # Build a rotated-space filled image: keep original outside mask,
        # broadcast col_medians into the mask region.
        filled_rot = np.where(mask_rot, col_medians[None, :], img_rot)

        # Some columns may have only NaNs available (line at image edge); for
        # those, leave the original rotated values and let the NN fallback
        # below handle them after un-rotating.
        bad_cols = np.isnan(col_medians)
        if bad_cols.any():
            filled_rot[:, bad_cols] = img_rot[:, bad_cols]

        # Rotate back to image coordinates (inverse affine, same speed)
        M_inv = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
        filled_back = cv2.warpAffine(
            filled_rot, M_inv, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        )

        # Apply only inside the original dilated mask region; don't touch
        # unmasked pixels (preserve original sky precision exactly).
        line_mask = detection.effective_mask > 0
        # Where filled_back is sane (not 0 from corner padding), use it.
        good = np.isfinite(filled_back) & (~np.isnan(filled_back))
        write = line_mask & good
        out[write] = filled_back[write]
        handled |= write

    # Fallback for pixels we couldn't fill via the rotated strip (rare:
    # image-corner cases or very short residual mask fragments). Use
    # nearest-neighbour for those.
    line_mask = detection.effective_mask > 0
    leftover = line_mask & (~handled)
    if leftover.any():
        nn_mask = leftover.astype(np.uint8) * 255
        nn_fill = _inpaint_cv2_ns(out.astype(src_dtype), nn_mask)
        out[leftover] = nn_fill[leftover].astype(np.float32)

    # Cast back to source dtype
    if np.issubdtype(src_dtype, np.integer):
        info = np.iinfo(src_dtype)
        return np.clip(
            np.round(out), info.min, info.max,
        ).astype(src_dtype)
    return out.astype(src_dtype)


def _match_sky_noise(
    cleaned: np.ndarray, original: np.ndarray, mask: np.ndarray,
    halo_width: int = 30,
) -> np.ndarray:
    """Add Gaussian noise to ``cleaned`` inside the mask, with σ taken
    from the local sky in a halo around the mask. Makes the inpainted
    region statistically indistinguishable from real sky (real sky has
    Poisson + read noise; a smooth inpaint does not, which stack-
    rejection algorithms can spot).

    Performance: dilates the mask with cv2.dilate (O(N), separable
    rectangular kernel) instead of scipy.ndimage.binary_dilation which
    is O(N · K²) for a 61×61 structuring element. ~50× faster on a
    typical 15-megapixel frame.
    """
    if not mask.any():
        return cleaned

    bool_mask = mask > 0
    # Halo: pixels within halo_width of the mask but NOT in the mask.
    # cv2.dilate uses a separable rectangular kernel internally and is
    # vastly faster than scipy's general binary_dilation for large SEs.
    mask_u8 = bool_mask.astype(np.uint8)
    k_size = 2 * halo_width + 1
    se = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
    dilated_u8 = cv2.dilate(mask_u8, se)
    halo = (dilated_u8 > 0) & ~bool_mask
    if not halo.any():
        return cleaned

    halo_vals = original[halo].astype(np.float32)
    # Sigma-clipped σ estimation. Plain MAD is robust to a FEW stellar
    # outliers but breaks when the halo crosses an extended bright
    # feature (comet tail, bright nebula, large galaxy) -- the MAD
    # picks up the bright-feature pixels and inflates σ by 10-30×,
    # which would then make the noise-injection add MASSIVE artificial
    # noise to the inpainted region. Iteratively reject pixels more
    # than 3σ from the running median to converge on the true sky std.
    vals = halo_vals
    for _ in range(4):
        if vals.size < 100:
            break
        m = float(np.median(vals))
        s = float(np.median(np.abs(vals - m))) * 1.4826
        if s <= 0:
            break
        keep = np.abs(vals - m) < 3.0 * s
        if keep.sum() == vals.size:
            break  # converged
        vals = vals[keep]
    if vals.size < 10:
        return cleaned
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med)))
    sigma = float(mad * 1.4826)
    if sigma <= 0:
        return cleaned

    rng = np.random.default_rng(seed=42)
    noise = rng.normal(0.0, sigma, size=int(bool_mask.sum())).astype(np.float32)
    src_dtype = cleaned.dtype
    if np.issubdtype(src_dtype, np.integer):
        info = np.iinfo(src_dtype)
        new_vals = cleaned[bool_mask].astype(np.float32) + noise
        cleaned[bool_mask] = np.clip(
            np.round(new_vals), info.min, info.max,
        ).astype(src_dtype)
    else:
        cleaned[bool_mask] = (cleaned[bool_mask].astype(np.float32) + noise).astype(src_dtype)
    return cleaned


def inpaint_frame(
    frame: np.ndarray,
    detection: TrailDetection,
    params: DetectionParams,
) -> np.ndarray:
    """Apply inpainting to a (C,H,W) / (1,H,W) / (H,W) frame and return the
    cleaned array in the same shape and dtype.

    After the chosen inpaint method runs, optional ``match_sky_noise``
    adds Gaussian noise inside the mask region with σ taken from the
    local sky halo. This makes the filled region statistically
    indistinguishable from real sky background.
    """
    if not detection.has_trails or detection.pixels_to_inpaint == 0:
        return frame.copy()

    method = params.inpaint_method
    mask = detection.effective_mask
    match_noise = bool(getattr(params, "match_sky_noise", True))

    def _clean_plane(plane: np.ndarray, orig: np.ndarray) -> np.ndarray:
        if method == "perp_strip":
            cleaned = _inpaint_perpendicular_strip(
                plane, detection, params.strip_width,
            )
        elif method == "biharmonic":
            cleaned = _inpaint_biharmonic(plane, mask)
        elif method == "harmonic":
            cleaned = _inpaint_harmonic(plane, mask)
        elif method == "cv2_telea":
            cleaned = _inpaint_cv2_telea(plane, mask)
        elif method == "cv2_navier_stokes":
            cleaned = _inpaint_cv2_navier_stokes(plane, mask)
        elif method == "cv2_ns":
            cleaned = _inpaint_cv2_ns(plane, mask)
        else:
            # Unknown method: warn loudly and use Perpendicular Strip
            # Median (the recommended safe default) rather than silently
            # routing to whichever branch the else used to fall through
            # to. The Settings whitelist normally prevents this, but
            # third-party callers of inpaint_frame() could pass anything.
            log.warning(
                "Unknown inpaint_method '%s' — using 'perp_strip' as "
                "safe fallback", method,
            )
            cleaned = _inpaint_perpendicular_strip(
                plane, detection, params.strip_width,
            )
        if match_noise:
            cleaned = _match_sky_noise(cleaned, orig, mask)
        return cleaned

    if frame.ndim == 3 and frame.shape[0] in (1, 3):
        cleaned = np.empty_like(frame)
        for c in range(frame.shape[0]):
            cleaned[c] = _clean_plane(frame[c], frame[c])
        return cleaned
    if frame.ndim == 2:
        return _clean_plane(frame, frame)
    raise ValueError(f"Unsupported frame shape for inpaint: {frame.shape}")


# ------------------------------------------------------------------------------
# FITS I/O -- writes preserving original headers (WCS, DATE-OBS, BSCALE, BZERO)
# ------------------------------------------------------------------------------

def read_fits_with_header(path: str) -> tuple[np.ndarray, fits.Header]:
    """Open a FITS file with astropy, return (data, header). The data
    array is in its native FITS axis order (H, W) for mono, (C, H, W)
    for multi-channel."""
    with fits.open(path, memmap=False) as hdul:
        hdu = hdul[0]
        data = np.array(hdu.data, copy=True)
        header = hdu.header.copy()
    return data, header


def write_fits_with_header(
    path: str,
    data: np.ndarray,
    header: fits.Header,
    overwrite: bool = True,
) -> None:
    """Write a FITS file, preserving the supplied header."""
    hdu = fits.PrimaryHDU(data=data, header=header)
    hdu.writeto(path, overwrite=overwrite)


def synthesise_header_for_raw(
    src_path: str,
    cleaned_dtype: np.dtype,
    extra_history: list[str] | None = None,
) -> fits.Header:
    """Build a minimal FITS header for an image originally loaded from a
    RAW. Records source filename and processing history."""
    hdr = fits.Header()
    hdr["BITPIX"] = -32 if np.issubdtype(cleaned_dtype, np.floating) else 16
    hdr["ORIGIN"] = "Svenesis-SatelliteTrailCleaner"
    hdr["SOURCE"] = (os.path.basename(src_path), "Original raw file")
    hdr["DATE"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if extra_history:
        for line in extra_history:
            hdr.add_history(line)
    return hdr


# ------------------------------------------------------------------------------
# XISF I/O -- read PixInsight metadata, write back preserving FITS keywords /
# XISF properties (incl. astrometric solutions). Uses sergio-dr/xisf package.
# ------------------------------------------------------------------------------

def read_xisf_metadata_only(path: str):
    """Parse just the XISF header (image_metadata + file_metadata).

    Returns (image_metadata_dict, file_metadata_dict) for the first image
    in the container, or (None, None) on failure. Does NOT read pixel
    data -- header parsing is fast even for multi-GB files.
    """
    if not _HAVE_XISF:
        return None, None
    try:
        x = XISF(path)
        ims = x.get_images_metadata()
        if not ims:
            return None, None
        return ims[0], x.get_file_metadata()
    except Exception as exc:
        log.debug("XISF metadata read failed for %s: %s", path, exc)
        return None, None


def _frame_to_xisf_layout(frame: np.ndarray) -> np.ndarray:
    """Convert a Siril-style frame to the (H, W, C) layout XISF expects,
    flipping the Y axis to match the XISF top-down storage convention.

    Y-flip rationale: Siril reads/writes images bottom-up (FITS
    convention -- pixel row 0 = bottom of sky). XISF stores pixels
    top-down (row 0 = top of image). If we write Siril's bottom-up
    array as-is, any XISF reader that follows the spec (PixInsight,
    Astrobin uploads, etc.) renders the image upside-down. Flipping the
    Y axis once at this boundary keeps the XISF file spec-compliant
    while leaving the on-disk WCS (which references the unchanged
    underlying physical sky) untouched -- it was already stored in the
    XISF's own coordinate system in the original FITSKeywords.
    """
    if frame.ndim == 2:
        hwc = frame[:, :, np.newaxis]
    elif frame.ndim == 3 and frame.shape[0] in (1, 3):
        hwc = np.transpose(frame, (1, 2, 0))
    else:
        hwc = frame  # already (H, W, C)
    return hwc[::-1, :, :]


def _cast_for_xisf(data: np.ndarray, target_dtype) -> np.ndarray:
    """Cast cleaned float/int data back to the XISF original dtype.

    XISF's writer accepts uint8 / uint16 / uint32 / float32 / float64.
    For float targets we additionally clip to [0, 1] because xisf
    hard-codes ``bounds="0:1"`` for float images.
    """
    td = np.dtype(target_dtype) if target_dtype is not None else data.dtype
    if td == data.dtype:
        if np.issubdtype(td, np.floating):
            return np.clip(data, 0.0, 1.0).astype(td, copy=False)
        return data
    if np.issubdtype(td, np.integer):
        info = np.iinfo(td)
        if np.issubdtype(data.dtype, np.floating):
            scaled = np.clip(data, 0.0, 1.0) * float(info.max)
            return scaled.astype(td, copy=False)
        return np.clip(data, info.min, info.max).astype(td, copy=False)
    if np.issubdtype(td, np.floating):
        if np.issubdtype(data.dtype, np.integer):
            info = np.iinfo(data.dtype)
            out = data.astype(np.float32) * (1.0 / float(max(info.max, 1)))
            return out.astype(td, copy=False)
        return np.clip(data, 0.0, 1.0).astype(td, copy=False)
    return data.astype(td, copy=False)


def _xisf_compression_from_metadata(image_metadata: dict | None) -> tuple:
    """Inspect an XISF image_metadata dict for the original compression
    settings (codec / shuffle / level). Returns the kwargs to pass back
    to XISF.write so the cleaned output matches the source's storage
    profile.

    Honours these forms seen in the wild:
      - ``compression`` as a string ``"lz4hc:9:1"`` (codec[:level[:shuffle]])
      - ``compression`` as a dict with ``codec`` / ``shuffle`` / ``level``
      - missing / None -> default to lz4hc + shuffle (good for astro data)
    """
    if not image_metadata:
        return {"codec": "lz4hc", "shuffle": True}
    raw = image_metadata.get("compression")
    if raw is None:
        return {"codec": "lz4hc", "shuffle": True}
    if isinstance(raw, dict):
        codec = raw.get("codec") or raw.get("name") or "lz4hc"
        shuffle = bool(raw.get("shuffle", True))
        level = raw.get("level")
        out = {"codec": str(codec).lower(), "shuffle": shuffle}
        if level is not None:
            out["level"] = int(level)
        return out
    if isinstance(raw, str):
        parts = raw.split(":")
        codec = parts[0].lower() if parts else "lz4hc"
        out = {"codec": codec, "shuffle": True}
        try:
            if len(parts) > 1 and parts[1]:
                out["level"] = int(parts[1])
        except ValueError:
            pass
        try:
            if len(parts) > 2 and parts[2]:
                # "1" / "true" => shuffle on
                out["shuffle"] = parts[2].strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            pass
        return out
    return {"codec": "lz4hc", "shuffle": True}


def write_xisf_cleaned(
    dest_path: str,
    cleaned_frame: np.ndarray,
    image_metadata: dict | None,
    file_metadata: dict | None,
    history_lines: list[str],
) -> None:
    """Write the cleaned pixel data as XISF, preserving FITSKeywords and
    XISFProperties from the original container (incl. astrometric
    solutions). Appends ``history_lines`` as HISTORY FITS keywords.

    Compression matches the source XISF where possible (so a NINA-saved
    uncompressed XISF stays uncompressed; a PixInsight-saved LZ4-with-
    shuffle XISF stays LZ4-with-shuffle). Fallback when the source is
    silent: lz4hc + byte shuffle, which is the strongest lossless option
    PixInsight understands by default.
    """
    if not _HAVE_XISF:
        raise RuntimeError("xisf library not installed")

    # Build the (H, W, C) array the writer expects, in the source dtype if known
    hwc = _frame_to_xisf_layout(cleaned_frame)
    target_dtype = None
    if image_metadata is not None:
        target_dtype = image_metadata.get("dtype")
    hwc = _cast_for_xisf(hwc, target_dtype)
    hwc = np.ascontiguousarray(hwc)

    # Carry-forward metadata (with HISTORY notes appended).
    if image_metadata is None:
        meta = {"FITSKeywords": {}, "XISFProperties": {}}
    else:
        meta = dict(image_metadata)
        meta["FITSKeywords"] = dict(meta.get("FITSKeywords") or {})
        meta["XISFProperties"] = dict(meta.get("XISFProperties") or {})
        meta["FITSKeywords"] = {k: list(v) for k, v in meta["FITSKeywords"].items()}

    if history_lines:
        hist = meta["FITSKeywords"].setdefault("HISTORY", [])
        for line in history_lines:
            hist.append({"value": "", "comment": str(line)})

    compression_kwargs = _xisf_compression_from_metadata(image_metadata)

    XISF.write(
        dest_path,
        hwc,
        creator_app=f"Svenesis-SatelliteTrailCleaner v{VERSION}",
        image_metadata=meta,
        xisf_metadata=file_metadata,
        **compression_kwargs,
    )


# ------------------------------------------------------------------------------
# TIFF I/O -- direct read/write via tifffile so we get bit-exact dtype
# round-trip plus ImageDescription / Software / DateTime preservation.
# Unlike FITS / XISF there's no canonical WCS keyword block to carry —
# astro TIFFs typically embed plate-solving solutions in ImageDescription
# as a free-form text blob (Siril, ASTAP, NINA all do this differently);
# we preserve that blob verbatim and append our cleaning history.
# ------------------------------------------------------------------------------

def read_tiff_with_meta(path: str):
    """Read a TIFF file's pixels plus the tags we care about preserving.

    Returns ``(data, meta)`` where ``data`` is the pixel array in
    ``(C, H, W)`` for RGB or ``(H, W)`` for mono (matching the rest of
    the pipeline's layout convention), and ``meta`` is a dict of tag
    info to round-trip into the cleaned output. Returns ``(None, None)``
    on failure.
    """
    if not _HAVE_TIFFFILE:
        return None, None
    try:
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            data = page.asarray()
            tags = page.tags

            def _tag_value(name):
                t = tags.get(name)
                if t is None:
                    return None
                try:
                    return t.value
                except Exception:
                    return None

            meta = {
                "description": _tag_value("ImageDescription"),
                "software": _tag_value("Software"),
                "datetime": _tag_value("DateTime"),
                "make": _tag_value("Make"),
                "model": _tag_value("Model"),
                "resolution_x": _tag_value("XResolution"),
                "resolution_y": _tag_value("YResolution"),
                "resolution_unit": _tag_value("ResolutionUnit"),
                "photometric": getattr(page, "photometric", None),
                "planar_config": getattr(page, "planarconfig", None),
                "compression": getattr(page, "compression", None),
                "bits_per_sample": getattr(page, "bitspersample", None),
                "samples_per_pixel": getattr(page, "samplesperpixel", None),
                "dtype": data.dtype,
            }

        # tifffile returns (H,W) for mono. For RGB/RGBA the layout
        # depends on the file's PlanarConfiguration tag:
        #   PlanarConfig.CONTIG (1, default): pixels interleaved (H,W,C)
        #   PlanarConfig.SEPARATE (2):        channels separate  (C,H,W)
        # Pipeline expects (C,H,W). Decide via the tag, not by guessing
        # at shape[-1] — a 3-pixel-wide planar TIFF would otherwise be
        # transposed into garbage.
        if data.ndim == 3:
            planar = meta.get("planar_config")
            try:
                planar_val = int(getattr(planar, "value", planar))
            except Exception:
                planar_val = 1  # default to interleaved (most common)
            if planar_val == 1 and data.shape[-1] in (1, 3, 4):
                # CONTIG / interleaved → (H,W,C) → (C,H,W)
                data = np.transpose(data, (2, 0, 1))
            # else: SEPARATE → already (C,H,W); leave as-is

            # RGBA: drop the alpha channel — the inpaint pipeline only
            # supports 1- or 3-channel data, and the alpha plane carries
            # no astrophysical information. Log so the user knows.
            if data.shape[0] == 4:
                log.warning(
                    "%s is a 4-channel TIFF (RGBA); discarding alpha "
                    "before processing", path,
                )
                data = data[:3]
        return data, meta
    except Exception as exc:
        log.debug("read_tiff_with_meta failed for %s: %s", path, exc)
        return None, None


def _tiff_compression_name(compression):
    """Map a tifffile.COMPRESSION enum / int to the string keyword the
    writer accepts. Returns ``None`` (= no compression) for unknown
    values so the write never fails on a quirky source.
    """
    if compression is None:
        return "zlib"
    try:
        val = int(getattr(compression, "value", compression))
    except Exception:
        return "zlib"
    # Common TIFF compression codes
    return {
        1: None,          # NONE
        5: "lzw",         # LZW
        7: "jpeg",        # OJPEG / JPEG (lossy; we never emit this)
        8: "zlib",        # ADOBE_DEFLATE
        32773: "packbits",
        32946: "zlib",    # DEFLATE
        34925: "lzma",    # LZMA
        50000: "zstd",    # ZSTD
    }.get(val, "zlib")


def _cast_for_tiff(arr: np.ndarray, target_dtype) -> np.ndarray:
    """Cast cleaned data back to the original TIFF dtype.

    Astro TIFFs come in four practical flavours: uint8 (rare, drizzle
    previews), uint16 (the workhorse — Siril, ASTAP, most cameras),
    uint32 (scientific cameras with deep wells), float32 (PixInsight /
    Siril floating-point exports). We preserve whichever was on the
    source so a 16-bit stack-input stays 16-bit and a 32-bit float
    export stays 32-bit float.
    """
    if target_dtype is None:
        return arr
    if arr.dtype == target_dtype:
        return arr
    src = arr
    src_is_float = np.issubdtype(src.dtype, np.floating)
    tgt_is_int = np.issubdtype(target_dtype, np.integer)
    if src_is_float and tgt_is_int:
        info = np.iinfo(target_dtype)
        # Float pipeline runs in [0,1]; rescale to target range.
        scale = float(info.max)
        return np.clip(np.round(src * scale), info.min, info.max).astype(target_dtype)
    if not src_is_float and tgt_is_int:
        # uint16 -> uint8 (rare): downsize via shift
        src_info = np.iinfo(src.dtype)
        tgt_info = np.iinfo(target_dtype)
        if src_info.bits > tgt_info.bits:
            shift = src_info.bits - tgt_info.bits
            return (src >> shift).astype(target_dtype)
        return src.astype(target_dtype)
    if src_is_float and np.issubdtype(target_dtype, np.floating):
        return src.astype(target_dtype)
    if not src_is_float and np.issubdtype(target_dtype, np.floating):
        info = np.iinfo(src.dtype)
        return (src.astype(np.float32) * (1.0 / max(info.max, 1))).astype(target_dtype)
    return src.astype(target_dtype)


def write_tiff_cleaned(
    dest_path: str,
    cleaned_frame: np.ndarray,
    meta: dict | None,
    history_lines: list[str],
) -> None:
    """Write the cleaned data back as a TIFF, preserving the source's
    dtype, photometric interpretation, compression, and a sensible
    subset of TIFF tags (Software, DateTime, ImageDescription).

    Cleaning history is appended to the ImageDescription tag (Siril
    and ASTAP both encode their plate-solve / processing notes there,
    so this matches the file format's convention).
    """
    if not _HAVE_TIFFFILE:
        raise RuntimeError("tifffile not installed; cannot write TIFF.")

    target_dtype = (meta or {}).get("dtype")
    data = cleaned_frame

    # (C,H,W) -> (H,W) mono or (H,W,C) RGB for the writer.
    if data.ndim == 3 and data.shape[0] in (1, 3, 4):
        if data.shape[0] == 1:
            data = data[0]
        else:
            data = np.transpose(data, (1, 2, 0))

    data = _cast_for_tiff(data, target_dtype)
    data = np.ascontiguousarray(data)

    # ---- Build the description (carry-forward + cleaning history) ----
    desc_parts: list[str] = []
    if meta is not None and meta.get("description"):
        existing = meta["description"]
        if isinstance(existing, bytes):
            try:
                existing = existing.decode("utf-8", errors="replace")
            except Exception:
                existing = str(existing)
        desc_parts.append(str(existing).rstrip())
    desc_parts.append("--- Svenesis-SatelliteTrailCleaner ---")
    desc_parts.extend(history_lines)
    description = "\n".join(desc_parts)

    # ---- Compression: match source where we can ----
    compression = _tiff_compression_name((meta or {}).get("compression"))

    # ---- Photometric interpretation ----
    if data.ndim == 3 and data.shape[-1] >= 3:
        photometric = "rgb"
    else:
        photometric = "minisblack"

    extra_kwargs = {}
    # Carry-forward resolution if present (kept as raw tag rationals)
    rx = (meta or {}).get("resolution_x")
    ry = (meta or {}).get("resolution_y")
    if rx is not None and ry is not None:
        try:
            extra_kwargs["resolution"] = (rx, ry)
        except Exception:
            pass

    tifffile.imwrite(
        dest_path,
        data,
        photometric=photometric,
        compression=compression,
        description=description,
        software=f"Svenesis-SatelliteTrailCleaner v{VERSION}",
        datetime=True,
        **extra_kwargs,
    )


# ------------------------------------------------------------------------------
# PREVIEW RENDERING -- numpy -> QImage with optional mask overlay
# ------------------------------------------------------------------------------

def _halve_u8_box(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        h, w = arr.shape
        r = arr.astype(np.uint16).reshape(h // 2, 2, w // 2, 2)
        return (r.sum(axis=(1, 3)) >> 2).astype(np.uint8)
    h, w, c = arr.shape
    r = arr.astype(np.uint16).reshape(h // 2, 2, w // 2, 2, c)
    return (r.sum(axis=(1, 3)) >> 2).astype(np.uint8)


def _quality_downscale_array(arr: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Anti-aliased downscale of a numpy uint8 array via progressive halving.

    Avoids the "barcode" aliasing artefact that a single-shot 4x+ downscale
    triggers on bright-star FITS frames.
    """
    if arr.size == 0:
        return arr
    while arr.shape[1] >= target_w * 4 and arr.shape[0] >= target_h * 4:
        h2 = arr.shape[0] - (arr.shape[0] & 1)
        w2 = arr.shape[1] - (arr.shape[1] & 1)
        if arr.ndim == 2:
            arr = arr[:h2, :w2]
        else:
            arr = arr[:h2, :w2, :]
        arr = _halve_u8_box(arr)
    if arr.shape[1] != target_w or arr.shape[0] != target_h:
        interp = cv2.INTER_AREA
        if arr.ndim == 2:
            arr = cv2.resize(arr, (target_w, target_h), interpolation=interp)
        else:
            arr = cv2.resize(arr, (target_w, target_h), interpolation=interp)
    return arr


def stretched_to_qimage(stretched_u8: np.ndarray) -> QImage | None:
    """Render an autostretched uint8 mono or (3,H,W) RGB array as a QImage,
    flipping rows from Siril's bottom-up orientation."""
    if stretched_u8.ndim == 3 and stretched_u8.shape[0] == 3:
        _, h, w = stretched_u8.shape
        alpha = np.full((h, w), 255, dtype=np.uint8)
        rgbx = np.stack(
            (stretched_u8[0], stretched_u8[1], stretched_u8[2], alpha), axis=-1
        )
        rgbx = np.ascontiguousarray(rgbx[::-1, :, :])
        buf = rgbx.tobytes()
        img = QImage(buf, w, h, w * 4, QImage.Format.Format_RGBX8888)
        return img.copy()
    if stretched_u8.ndim == 3 and stretched_u8.shape[0] == 1:
        stretched_u8 = stretched_u8[0]
    if stretched_u8.ndim != 2:
        return None
    mono = np.ascontiguousarray(stretched_u8[::-1, :])
    h, w = mono.shape
    buf = mono.tobytes()
    img = QImage(buf, w, h, w, QImage.Format.Format_Grayscale8)
    return img.copy()


def overlay_mask_on_stretched(stretched_u8: np.ndarray, mask: np.ndarray) -> QImage | None:
    """Render the stretched preview with mask drawn in semi-transparent red.

    Used for the 'Mask Overlay' view mode.
    """
    if stretched_u8.ndim == 3 and stretched_u8.shape[0] == 3:
        _, h, w = stretched_u8.shape
        rgb = np.stack((stretched_u8[0], stretched_u8[1], stretched_u8[2]), axis=-1)
        rgb = rgb.astype(np.uint8)
    elif stretched_u8.ndim == 2:
        h, w = stretched_u8.shape
        rgb = np.stack((stretched_u8, stretched_u8, stretched_u8), axis=-1)
    else:
        return stretched_to_qimage(stretched_u8)

    m = (mask > 0)
    # Blend 60% red where the mask is set
    red = np.array([255, 70, 70], dtype=np.uint8)
    rgb_over = rgb.copy()
    rgb_over[m] = (rgb[m].astype(np.uint16) * 40 // 100
                   + red.astype(np.uint16) * 60 // 100).astype(np.uint8)

    alpha = np.full((h, w), 255, dtype=np.uint8)
    rgbx = np.concatenate([rgb_over, alpha[:, :, None]], axis=-1)
    rgbx = np.ascontiguousarray(rgbx[::-1, :, :])
    buf = rgbx.tobytes()
    img = QImage(buf, w, h, w * 4, QImage.Format.Format_RGBX8888)
    return img.copy()


def stretch_for_display(frame: np.ndarray) -> np.ndarray:
    """Apply autostretch and return uint8 mono (H,W) or RGB (3,H,W)."""
    if frame.ndim == 3 and frame.shape[0] == 3:
        out = np.empty_like(frame, dtype=np.uint8)
        for c in range(3):
            out[c] = autostretch(frame[c])
        return out
    if frame.ndim == 3 and frame.shape[0] == 1:
        return autostretch(frame[0])
    return autostretch(frame)


# ------------------------------------------------------------------------------
# IMAGE CANVAS WIDGET -- displays the current view as a centred QPixmap
# ------------------------------------------------------------------------------

def _point_to_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Minimum distance from point (px, py) to the segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-9:
        ddx = px - x1
        ddy = py - y1
        return float(np.hypot(ddx, ddy))
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return float(np.hypot(px - nx, py - ny))


class ImageCanvas(QWidget):
    """Scaled image display with optional clickable line overlays.

    Lines are passed in image-array coordinates (y=0 = row 0 of the numpy
    frame). Because the displayed image is row-flipped to match the
    Siril-bottom-up source, the canvas applies a y-flip when drawing and
    when hit-testing clicks.
    """

    selection_toggled = pyqtSignal(int)  # emitted with index of toggled line

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: QImage | None = None
        self._image_size: tuple[int, int] = (0, 0)   # (W, H) of source array
        self._lines: list[tuple[int, int, int, int]] = []
        self._selections: list[bool] = []
        self._needs_y_flip: bool = True
        self._last_paint: tuple[float, float, int, int, int, int] | None = None
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#1a1a1a;")
        self._placeholder = "No frame loaded"
        self.setMouseTracking(False)

    def set_image(self, img: QImage | None, image_size: tuple[int, int] | None = None) -> None:
        self._image = img
        if image_size is not None:
            self._image_size = image_size
        elif img is not None and not img.isNull():
            self._image_size = (img.width(), img.height())
        else:
            self._image_size = (0, 0)
        self.update()

    def set_lines(
        self,
        lines: list[tuple[int, int, int, int]],
        selections: list[bool],
    ) -> None:
        self._lines = list(lines)
        self._selections = list(selections)
        self.update()

    def clear_lines(self) -> None:
        self._lines = []
        self._selections = []
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        if self._image is None:
            self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1a1a1a"))
        if self._image is None or self._image.isNull():
            p.setPen(QColor("#888888"))
            f = p.font()
            f.setPointSize(14)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            p.end()
            return

        w, h = self.width(), self.height()
        scaled = self._image.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (w - scaled.width()) // 2
        oy = (h - scaled.height()) // 2
        p.drawImage(ox, oy, scaled)

        iw, ih = self._image_size
        if iw > 0 and ih > 0 and self._lines and scaled.width() > 0 and scaled.height() > 0:
            sx = scaled.width() / iw
            sy = scaled.height() / ih
            self._last_paint = (sx, sy, ox, oy, iw, ih)

            # Adapt visual weight to line count: when there are many lines
            # (a Newton/SCT spider with rich star field produces hundreds
            # of false-positive spike segments), drawing them all in bold
            # green completely obscures the underlying image. We thin the
            # strokes and drop alpha so the photo remains readable through
            # the overlay.
            n_lines = len(self._lines)
            if n_lines > 60:
                sel_w, sel_a = 1, 180
                keep_w, keep_a = 1, 70
            elif n_lines > 20:
                sel_w, sel_a = 2, 210
                keep_w, keep_a = 1, 100
            else:
                sel_w, sel_a = 2, 235
                keep_w, keep_a = 1, 150

            # Draw deselected first (so selected lines paint on top)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for sel_state in (False, True):
                for line, sel in zip(self._lines, self._selections):
                    if sel != sel_state:
                        continue
                    x1, y1, x2, y2 = line
                    if self._needs_y_flip:
                        y1 = ih - 1 - y1
                        y2 = ih - 1 - y2
                    wx1 = ox + x1 * sx
                    wy1 = oy + y1 * sy
                    wx2 = ox + x2 * sx
                    wy2 = oy + y2 * sy
                    if sel:
                        pen = QPen(QColor(120, 255, 120, sel_a), sel_w)
                    else:
                        pen = QPen(QColor(160, 160, 160, keep_a), keep_w)
                    p.setPen(pen)
                    p.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))
        else:
            self._last_paint = None

        p.end()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if not self._lines or self._last_paint is None:
            return
        sx, sy, ox, oy, iw, ih = self._last_paint
        if sx <= 0 or sy <= 0:
            return
        wx = float(ev.position().x())
        wy = float(ev.position().y())
        img_x = (wx - ox) / sx
        img_y_disp = (wy - oy) / sy
        if not (0 <= img_x < iw and 0 <= img_y_disp < ih):
            return
        img_y = (ih - 1 - img_y_disp) if self._needs_y_flip else img_y_disp

        # Hit tolerance: 10 widget-px in image space (slightly generous so
        # picking a faint trail under a crowded overlay is forgiving).
        tol = 10.0 / max(sx, sy)
        best_idx = -1
        best_d = float("inf")
        for i, (x1, y1, x2, y2) in enumerate(self._lines):
            d = _point_to_segment_distance(img_x, img_y, x1, y1, x2, y2)
            if d < best_d:
                best_d = d
                best_idx = i
        if best_idx >= 0 and best_d <= tol:
            # Toggle is owned by the main window (single source of truth).
            # We only emit -- the window updates `selections` and pushes
            # back via set_lines().
            self.selection_toggled.emit(best_idx)


# ------------------------------------------------------------------------------
# WORKER -- detection + apply on a background thread
# ------------------------------------------------------------------------------

class DetectionResult:
    """Bundle of state returned by the worker after detection."""

    def __init__(
        self,
        index: int,
        path: str,
        frame: np.ndarray,
        stretched: np.ndarray,
        detection: TrailDetection,
        error: str | None = None,
    ) -> None:
        self.index = index
        self.path = path
        self.frame = frame
        self.stretched = stretched
        self.detection = detection
        self.error = error


# ------------------------------------------------------------------------------
# APPLY-TO-ONE PIPELINE (used by both single and batch modes)
# ------------------------------------------------------------------------------

class ApplyOutcome:
    def __init__(
        self,
        path: str,
        status: str,
        lines: int = 0,
        pixels_replaced: int = 0,
        note: str = "",
        cleaned_path: str | None = None,
    ) -> None:
        self.path = path
        self.status = status              # "cleaned" / "skipped_no_trail" / "skipped_user" / "error"
        self.lines = lines
        self.pixels_replaced = pixels_replaced
        self.note = note
        # For RAW inputs the cleaned file lives at a different path (.fit)
        # than the source (.cr2). For FITS this equals `path`. None on
        # non-cleaning outcomes.
        self.cleaned_path = cleaned_path


def apply_to_path(
    siril_iface,
    path: str,
    params: DetectionParams,
    originals_dir: str,
    precomputed_frame: np.ndarray | None = None,
    precomputed_detection: TrailDetection | None = None,
) -> ApplyOutcome:
    """Detect + inpaint + write the cleaned FITS for a single source file.

    For RAW input the cleaned FITS replaces the RAW (RAW is moved to
    `originals/` and the FITS is written with the basename + .fit).
    For FITS input the original is moved to `originals/` and a cleaned FITS
    with the same filename is written in its place.

    If ``precomputed_frame`` and ``precomputed_detection`` are provided the
    function uses them verbatim (so any user-curated line selections in
    the UI are honoured). Otherwise it re-loads and re-detects from
    scratch (batch / auto path).
    """
    try:
        if precomputed_frame is not None and precomputed_detection is not None:
            frame = precomputed_frame
            det = precomputed_detection
        else:
            frame = load_frame_data(siril_iface, path)
            if frame is None:
                return ApplyOutcome(path, "error", note="failed to load via Siril")
            mono = to_mono_float32(frame, mode=getattr(params, "mono_mode", "mean"))
            det = detect_trails(mono, params)

        if not det.has_trails or det.pixels_to_inpaint == 0:
            return ApplyOutcome(path, "skipped_no_trail", note=det.notes)

        cleaned = inpaint_frame(frame, det, params)

        folder = os.path.dirname(path)
        basename = os.path.basename(path)
        name_no_ext, _ext = os.path.splitext(basename)

        history_lines = [
            f"Cleaned by Svenesis-SatelliteTrailCleaner v{VERSION}",
            f"Trails detected: {len(det.lines)}; pixels replaced: {det.pixels_to_inpaint}",
            f"Inpaint method: {params.inpaint_method}, dilation: {params.dilation_radius} px",
        ]

        # Decide write strategy based on input type
        write_strategy = "fits"  # default
        xisf_image_meta = None
        xisf_file_meta = None
        tiff_meta = None
        if is_fits_file(path):
            write_strategy = "fits"
        elif is_xisf_file(path) and _HAVE_XISF:
            # Read XISF metadata BEFORE moving the source so the cleaned
            # output retains FITSKeywords + XISFProperties (WCS, filter,
            # exposure, plate-solving solutions, etc.).
            xisf_image_meta, xisf_file_meta = read_xisf_metadata_only(path)
            if xisf_image_meta is not None:
                write_strategy = "xisf"
            else:
                write_strategy = "fits"  # fall back if metadata parse failed
        elif is_tiff_file(path) and _HAVE_TIFFFILE:
            # Read TIFF tags BEFORE moving the source so the cleaned
            # output retains description / software / datetime and the
            # original dtype + compression. If metadata read fails we
            # still write a clean TIFF (synthesised tags) rather than
            # downgrading to FITS — preserving the user's chosen
            # file format is more important than a perfect metadata
            # round-trip.
            _, tiff_meta = read_tiff_with_meta(path)
            write_strategy = "tiff"
        else:
            # RAW input, or XISF without xisf library, or TIFF without
            # tifffile
            write_strategy = "fits"

        if write_strategy == "fits":
            if is_fits_file(path):
                # Preserve original FITS header
                try:
                    _, header = read_fits_with_header(path)
                except Exception:
                    header = fits.Header()
                    header["ORIGIN"] = "Svenesis-SatelliteTrailCleaner"
                for line in history_lines:
                    header.add_history(line)
                dest_path = path  # overwrite after move-out below
            else:
                # RAW or XISF-fallback: synthesise a header, target is .fit
                header = synthesise_header_for_raw(path, cleaned.dtype, history_lines)
                dest_basename = name_no_ext + ".fit"
                dest_path = os.path.join(folder, dest_basename)
            original_target = os.path.join(originals_dir, basename)
        elif write_strategy == "xisf":
            dest_path = path  # overwrite after move-out (same filename)
            original_target = os.path.join(originals_dir, basename)
        else:  # write_strategy == "tiff"
            dest_path = path  # overwrite after move-out (same filename)
            original_target = os.path.join(originals_dir, basename)

        os.makedirs(originals_dir, exist_ok=True)
        # 1) move original out of the way
        shutil.move(path, original_target)
        # 2) write cleaned output in the source slot
        try:
            if write_strategy == "xisf":
                write_xisf_cleaned(
                    dest_path, cleaned,
                    image_metadata=xisf_image_meta,
                    file_metadata=xisf_file_meta,
                    history_lines=history_lines,
                )
            elif write_strategy == "tiff":
                write_tiff_cleaned(
                    dest_path, cleaned,
                    meta=tiff_meta,
                    history_lines=history_lines,
                )
            else:
                write_fits_with_header(dest_path, cleaned, header, overwrite=True)
        except Exception as wexc:
            # Best-effort rollback: put the original back
            try:
                shutil.move(original_target, path)
            except Exception as rb_exc:
                # Rollback itself failed — log so user can recover
                # manually from originals/. This is the worst-case
                # diagnostic path; we want a full stacktrace in the
                # debug log so the on-call (or the user) can see what
                # happened.
                log.error(
                    "Rollback failed for %s after write error: %s",
                    path, rb_exc, exc_info=True,
                )
            log.exception(
                "write failed for %s (strategy=%s)", path, write_strategy,
            )
            return ApplyOutcome(path, "error", note=f"write failed: {wexc}")

        return ApplyOutcome(
            path,
            "cleaned",
            lines=len(det.lines),
            pixels_replaced=det.pixels_to_inpaint,
            note=det.notes,
            cleaned_path=dest_path,
        )
    except Exception as exc:
        # Outer catch-all: capture the full traceback in the log so a
        # cryptic "ValueError: …" in the UI can still be tracked to a
        # specific line in this function. The ApplyOutcome note stays
        # short for the UI display.
        log.exception("apply_to_path failed for %s", path)
        return ApplyOutcome(path, "error", note=f"{type(exc).__name__}: {exc}")


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class SatelliteTrailCleanerWindow(QMainWindow):

    detection_complete = pyqtSignal(object)  # DetectionResult
    detection_progress = pyqtSignal(str)     # phase tag

    def __init__(self, siril_iface, folder: str, paths: list[str]) -> None:
        super().__init__()
        self.siril = siril_iface
        self.folder = folder
        self.paths: list[str] = list(paths)
        self.params = DetectionParams()
        self.current_index: int = 0
        self.last_detection: DetectionResult | None = None
        self.view_mode: str = "mask_overlay"   # "stretched" / "mask_overlay" / "cleaned_preview"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trailcleaner")
        self._busy = False
        self._cancel_batch = False

        # MRT result cache: keyed on (path, downsample, theta_step). Hits
        # skip the expensive run_mrt() phase and only re-run the cheap
        # peak-detect + per-candidate filtering, giving a ~5-10x speedup
        # when the user iterates on SNR / max_width / persistence sliders.
        # Bounded LRU; entries are TrailFinder objects which hold the
        # downsampled image and its MRT, so we cap at 3 to bound memory.
        self._mrt_cache: "OrderedDict[tuple, object]" = OrderedDict()
        self._mrt_cache_max_size = 3

        self.setWindowTitle(f"Svenesis Satellite Trail Cleaner  v{VERSION}")
        self.resize(1500, 880)
        self.setStyleSheet(DARK_STYLESHEET)

        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._build_ui()
        self._load_settings()
        self._wire_signals()
        self._update_frame_label()
        self._update_selection_label()
        self._update_persistence_enabled()
        self._update_strip_enabled()
        self._show_placeholder()
        QTimer.singleShot(50, lambda: self._load_and_show(self.current_index, autodetect=False))
        # Workflow walkthrough — pops up once the main window is on
        # screen and rendered. 200 ms gives Qt time to lay out the
        # window first, so the dialog appears centred over a fully
        # painted background instead of a half-empty frame. The dialog
        # has a 'Don't show this again' checkbox; the QSettings flag
        # keeps power users from being nagged after they've internalised
        # the flow.
        QTimer.singleShot(200, self._maybe_show_workflow_dialog)

    # ---- UI construction ----

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---- Left panel ----
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        title = QLabel(f"Svenesis Satellite Trail Cleaner {VERSION}")
        title.setStyleSheet("font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        self.lbl_folder = QLabel(self.folder)
        self.lbl_folder.setStyleSheet("color:#999; font-size:9pt;")
        self.lbl_folder.setWordWrap(True)
        left_layout.addWidget(self.lbl_folder)

        # Detection group (findsat_mrt / Median Radon Transform)
        grp_det = QGroupBox("Detection (MRT)")
        f_det = QFormLayout(grp_det)
        f_det.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_scan = QComboBox()
        self.cmb_scan.addItem("Quick (fast, less sensitive)", "quick")
        self.cmb_scan.addItem("Normal (recommended)", "normal")
        self.cmb_scan.addItem("Deep (slow, max sensitivity)", "deep")
        idx = self.cmb_scan.findData(self.params.scan_mode)
        if idx >= 0:
            self.cmb_scan.setCurrentIndex(idx)
        self.cmb_scan.setToolTip(
            "Quick: downsample 4x, coarse 1deg theta, no persistence check.\n"
            "Normal: downsample 2x, 0.5deg theta, persistence check on.\n"
            "Deep: full resolution, 0.5deg theta, all filters on. ~4x slower."
        )
        f_det.addRow("Scan mode:", self.cmb_scan)

        self.sp_snr = QDoubleSpinBox()
        self.sp_snr.setRange(2.0, 20.0)
        self.sp_snr.setSingleStep(0.5)
        self.sp_snr.setDecimals(1)
        self.sp_snr.setValue(self.params.snr_threshold)
        self.sp_snr.setToolTip(
            "SNR threshold on the MRT map. STScI default is 5.0 "
            "(robust on HST data). Lower = catch fainter trails."
        )
        f_det.addRow("SNR threshold:", self.sp_snr)

        self.sp_min_len = QSpinBox()
        self.sp_min_len.setRange(10, 1000)
        self.sp_min_len.setValue(self.params.min_length)
        self.sp_min_len.setSuffix(" px")
        self.sp_min_len.setToolTip(
            "Minimum trail length in MRT pixels. Default 50 catches "
            "most satellite trails on amateur sub-frames."
        )
        f_det.addRow("Min length:", self.sp_min_len)

        self.sp_max_w = QSpinBox()
        self.sp_max_w.setRange(3, 500)
        self.sp_max_w.setValue(self.params.max_width)
        self.sp_max_w.setSuffix(" px")
        self.sp_max_w.setToolTip(
            "Maximum trail width in image pixels. Wider candidates "
            "are rejected (kills comet tails, nebula filaments). "
            "Real satellite trails are 3-10 px wide; set this around 20."
        )
        f_det.addRow("Max width:", self.sp_max_w)

        self.cb_persistence = QCheckBox("Check persistence (kills comets)")
        self.cb_persistence.setChecked(self.params.check_persistence)
        self.cb_persistence.setToolTip(
            "Split each candidate trail into chunks along its length and "
            "verify that a fraction of chunks show consistent SNR. A "
            "satellite trail is uniform along its length and passes; a "
            "comet tail fades and fails. ON by default."
        )
        f_det.addRow(self.cb_persistence)

        self.sp_persist_frac = QDoubleSpinBox()
        self.sp_persist_frac.setRange(0.05, 1.0)
        self.sp_persist_frac.setSingleStep(0.05)
        self.sp_persist_frac.setDecimals(2)
        self.sp_persist_frac.setValue(self.params.min_persistence)
        self.sp_persist_frac.setToolTip(
            "Min fraction of length-chunks that must individually pass "
            "the persistence SNR test. 0.5 = majority must show signal."
        )
        f_det.addRow("Min persistence:", self.sp_persist_frac)

        self.sp_persist_chunk = QSpinBox()
        self.sp_persist_chunk.setRange(20, 1000)
        self.sp_persist_chunk.setValue(self.params.persistence_chunk)
        self.sp_persist_chunk.setSuffix(" px")
        self.sp_persist_chunk.setToolTip(
            "Pixel length of each persistence chunk. STScI default 100."
        )
        f_det.addRow("Chunk size:", self.sp_persist_chunk)

        self.sp_processes = QSpinBox()
        self.sp_processes.setRange(1, 16)
        self.sp_processes.setValue(self.params.processes)
        self.sp_processes.setToolTip(
            "Worker processes for the MRT computation. Higher = faster "
            "on multi-core machines. 4 is a sensible default."
        )
        f_det.addRow("Processes:", self.sp_processes)

        self.sp_dilate = QSpinBox()
        self.sp_dilate.setRange(1, 30)
        self.sp_dilate.setValue(self.params.dilation_radius)
        self.sp_dilate.setToolTip(
            "Half-width (px) of the inpaint mask around each accepted line."
        )
        f_det.addRow("Mask dilation:", self.sp_dilate)

        # RGB → mono reduction mode (only matters for colour frames;
        # ignored for single-channel FITS / luminance-only data).
        self.cmb_mono_mode = QComboBox()
        self.cmb_mono_mode.addItem("Mean (default, fast)", "mean")
        self.cmb_mono_mode.addItem("Max per pixel (for coloured trails)", "max")
        idx_mm = self.cmb_mono_mode.findData(self.params.mono_mode)
        if idx_mm >= 0:
            self.cmb_mono_mode.setCurrentIndex(idx_mm)
        self.cmb_mono_mode.setToolTip(
            "How to collapse RGB channels into a single intensity image "
            "for trail detection.\n"
            "Mean: average across R+G+B. Works for white / luminance "
            "trails (the typical satellite). Fast.\n"
            "Max per pixel: takes the brightest channel at each pixel. "
            "Use when the trail is bright in only one channel (e.g. a "
            "sodium-reflective satellite that glows red against a "
            "balanced background) — under Mean reduction such a trail "
            "loses ~√3 of its SNR and may fall below the threshold."
        )
        f_det.addRow("RGB reduce:", self.cmb_mono_mode)

        left_layout.addWidget(grp_det)

        # Star protection
        grp_star = QGroupBox("Star Protection (Inpaint)")
        f_star = QFormLayout(grp_star)

        self.cb_protect = QCheckBox("Protect detected stars")
        self.cb_protect.setChecked(self.params.protect_stars)
        f_star.addRow(self.cb_protect)

        self.sp_star_sigma = QDoubleSpinBox()
        self.sp_star_sigma.setRange(1.0, 20.0)
        self.sp_star_sigma.setSingleStep(0.5)
        self.sp_star_sigma.setValue(self.params.star_sigma)
        self.sp_star_sigma.setToolTip("Detect stars above (median + N * sigma).")
        f_star.addRow("Sigma:", self.sp_star_sigma)

        self.sp_star_dil = QSpinBox()
        self.sp_star_dil.setRange(1, 15)
        self.sp_star_dil.setValue(self.params.star_dilation)
        self.sp_star_dil.setToolTip("Halo radius (px) around each detected star.")
        f_star.addRow("Star halo:", self.sp_star_dil)

        left_layout.addWidget(grp_star)

        # Inpaint
        grp_inp = QGroupBox("Inpainting")
        f_inp = QFormLayout(grp_inp)

        self.cmb_method = QComboBox()
        self.cmb_method.addItem("Perpendicular Strip Median (recommended)", "perp_strip")
        self.cmb_method.addItem("Harmonic / Laplace (∇²u = 0, no ringing)", "harmonic")
        self.cmb_method.addItem("Nearest Neighbor + Smooth (fast)", "cv2_ns")
        self.cmb_method.addItem("cv2 Fast Marching / Telea (very fast)", "cv2_telea")
        self.cmb_method.addItem("cv2 Navier-Stokes (very fast)", "cv2_navier_stokes")
        self.cmb_method.addItem("Biharmonic (experimental, may ring)", "biharmonic")
        idx = self.cmb_method.findData(self.params.inpaint_method)
        if idx >= 0:
            self.cmb_method.setCurrentIndex(idx)
        self.cmb_method.setToolTip(
            "Perpendicular Strip Median (default): replaces each masked "
            "pixel with the median of a strip ±strip_width perpendicular "
            "to the trail. Preserves any sky gradient that runs across "
            "the trail (vignetting / light-pollution slope). Robust on "
            "flashing-satellite / tumbling-debris trails with bright "
            "pearls — no PDE ringing.\n"
            "Harmonic / Laplace: iterative 5-point ∇²u=0 solver on a "
            "bbox crop. Has the maximum principle (no overshoot, unlike "
            "biharmonic), produces very smooth fills — combined with "
            "Match-sky-noise this gives physical fill + realistic noise.\n"
            "Nearest Neighbor + Smooth: pure-Python via scipy, ~500 ms "
            "on 15 MP. Good fallback for live preview.\n"
            "cv2 Fast Marching (Telea): OpenCV's C++ FMM algorithm via "
            "percentile-scaled uint8. Fastest option (~200 ms).\n"
            "cv2 Navier-Stokes (Bertalmio): propagates isophotes into "
            "the masked region instead of normalised distance weights. "
            "Same speed class as Telea; sometimes nicer edge behaviour "
            "but on sky-dominated regions essentially identical.\n"
            "Biharmonic: skimage ∇⁴u=0 PDE solver on a bbox crop. "
            "Mathematically smooth but the biharmonic equation has no "
            "maximum principle — long thin masks can produce periodic "
            "over/undershoot (the classic 'string of pearls' artefact)."
        )
        f_inp.addRow("Method:", self.cmb_method)

        # Recommendation banner: populated by _update_inpaint_recommendation()
        # after each detection completes. The label wraps long rationales
        # and stays hidden until there's a non-empty recommendation. The
        # "Apply" button switches the dropdown to the recommended value
        # without nagging the user with auto-changes.
        self.rec_container = QWidget()
        rec_layout = QHBoxLayout(self.rec_container)
        rec_layout.setContentsMargins(0, 4, 0, 4)
        rec_layout.setSpacing(6)
        self.lbl_recommendation = QLabel("")
        self.lbl_recommendation.setWordWrap(True)
        self.lbl_recommendation.setStyleSheet(
            "color:#88aaff; font-size:9pt; "
            "background:#1f2630; border:1px solid #3a5a7a; "
            "border-radius:4px; padding:4px 6px;"
        )
        self.lbl_recommendation.setTextFormat(Qt.TextFormat.RichText)
        rec_layout.addWidget(self.lbl_recommendation, stretch=1)
        self.btn_apply_rec = QPushButton("Apply")
        self.btn_apply_rec.setToolTip(
            "Switch the inpaint method to the recommendation above."
        )
        self.btn_apply_rec.setMaximumWidth(60)
        rec_layout.addWidget(self.btn_apply_rec, alignment=Qt.AlignmentFlag.AlignTop)
        self.rec_container.setVisible(False)
        f_inp.addRow(self.rec_container)

        self.sp_strip = QSpinBox()
        self.sp_strip.setRange(5, 80)
        self.sp_strip.setValue(self.params.strip_width)
        self.sp_strip.setToolTip("Strip half-width (px) for perpendicular-strip median.")
        f_inp.addRow("Strip width:", self.sp_strip)

        self.cb_match_noise = QCheckBox("Match sky noise (subtle, recommended)")
        self.cb_match_noise.setChecked(self.params.match_sky_noise)
        self.cb_match_noise.setToolTip(
            "After inpainting, add Gaussian noise inside the mask with "
            "σ matching the local sky halo. Makes the cleaned region "
            "statistically indistinguishable from real sky -- otherwise "
            "the filled patch is too smooth and can be spotted on close "
            "inspection or by stack-rejection algorithms."
        )
        f_inp.addRow(self.cb_match_noise)

        left_layout.addWidget(grp_inp)

        # Batch / Apply controls
        grp_apply = QGroupBox("Apply")
        v_apply = QVBoxLayout(grp_apply)

        self.cb_confirm_each = QCheckBox("Confirm each frame before writing")
        v_apply.addWidget(self.cb_confirm_each)

        self.lbl_apply_stats = QLabel("")
        self.lbl_apply_stats.setStyleSheet("color:#999; font-size:9pt;")
        v_apply.addWidget(self.lbl_apply_stats)

        h_apply = QHBoxLayout()
        self.btn_apply_current = QPushButton("✓ Apply to Current")
        self.btn_apply_current.setObjectName("ApplyButton")
        h_apply.addWidget(self.btn_apply_current)
        self.btn_skip_current = QPushButton("Skip")
        self.btn_skip_current.setObjectName("SkipButton")
        h_apply.addWidget(self.btn_skip_current)
        v_apply.addLayout(h_apply)

        self.btn_apply_all = QPushButton("⏩ Apply to All Frames")
        self.btn_apply_all.setObjectName("ApplyAllButton")
        v_apply.addWidget(self.btn_apply_all)

        left_layout.addWidget(grp_apply)

        left_layout.addStretch(1)

        # Buy me a Coffee / Help / Close
        self.btn_coffee = QPushButton("☕  Buy me a Coffee")
        _nofocus(self.btn_coffee)
        self.btn_coffee.setObjectName("CoffeeButton")
        self.btn_coffee.setToolTip("Support the development of this tool")
        self.btn_help = QPushButton("Help")
        _nofocus(self.btn_help)
        self.btn_close = QPushButton("Close")
        _nofocus(self.btn_close)
        self.btn_close.setObjectName("CloseButton")
        left_layout.addWidget(self.btn_coffee)
        left_layout.addWidget(self.btn_help)
        left_layout.addWidget(self.btn_close)

        root.addWidget(left)

        # ---- Right side ----
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(6)

        # Top bar: view-mode + detect button
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("View:"))
        self.cmb_view = QComboBox()
        self.cmb_view.addItem("Stretched", "stretched")
        self.cmb_view.addItem("Mask Overlay", "mask_overlay")
        self.cmb_view.addItem("Cleaned Preview", "cleaned_preview")
        idx = self.cmb_view.findData(self.view_mode)
        if idx >= 0:
            self.cmb_view.setCurrentIndex(idx)
        top_bar.addWidget(self.cmb_view)

        top_bar.addSpacing(20)
        self.btn_detect = QPushButton("\U0001f6f0  Detect Trails on Current")
        self.btn_detect.setObjectName("DetectButton")
        top_bar.addWidget(self.btn_detect)
        top_bar.addSpacing(20)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#ccc;")
        # Constrain to a single line so long detection summaries
        # ("Cleaned Preview — inpaint changed 49,684 px (mask: 50,543
        # expected) — findsat_mrt: 33 candidates → 1 accepted; halo
        # growth +129 px in 6 hops (sky=…, thr=…)") can never wrap to
        # two lines and push the canvas down. Full text is preserved
        # in the tooltip via _set_status_text().
        self.lbl_info.setWordWrap(False)
        self.lbl_info.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )
        fm_h = self.lbl_info.fontMetrics().height()
        self.lbl_info.setMinimumHeight(fm_h + 2)
        self.lbl_info.setMaximumHeight(fm_h + 2)
        self.lbl_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        # Reserve a sane minimum width so the layout doesn't try to
        # shrink the label to zero before clipping. Anything wider than
        # this is clipped at the right edge (no wrap).
        self.lbl_info.setMinimumWidth(200)
        # stretch=1 makes this the elastic widget — it absorbs any
        # leftover horizontal space, so the Detect button on its left
        # stays anchored even when the label is empty. Without it, a
        # short label would let the Detect button drift to the right.
        top_bar.addWidget(self.lbl_info, stretch=1)

        r_layout.addLayout(top_bar)

        # Progress bar (visible during detection / apply work)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate / pulsing
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("")
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setVisible(False)
        r_layout.addWidget(self.progress_bar)

        # Line-selection toolbar (visible after detection)
        sel_bar = QHBoxLayout()
        self.lbl_selection = QLabel("")
        self.lbl_selection.setStyleSheet("color:#88aaff; font-size:10pt;")
        sel_bar.addWidget(self.lbl_selection)
        sel_bar.addSpacing(12)
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_invert = QPushButton("Invert")
        for b in (self.btn_select_all, self.btn_select_none, self.btn_select_invert):
            b.setFixedHeight(24)
            _nofocus(b)
            sel_bar.addWidget(b)
        sel_bar.addStretch(1)
        self.lbl_pick_hint = QLabel("Click a line to toggle remove / keep")
        self.lbl_pick_hint.setStyleSheet("color:#888; font-size:9pt;")
        sel_bar.addWidget(self.lbl_pick_hint)
        r_layout.addLayout(sel_bar)

        # Canvas
        self.canvas = ImageCanvas()
        r_layout.addWidget(self.canvas, 1)

        # Navigation bar
        nav_bar = QHBoxLayout()
        self.btn_first = QPushButton("|<")
        self.btn_prev = QPushButton("<")
        self.btn_next = QPushButton(">")
        self.btn_last = QPushButton(">|")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setFixedWidth(40)
            nav_bar.addWidget(b)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, len(self.paths) - 1))
        nav_bar.addWidget(self.slider, 1)

        self.lbl_frame = QLabel("")
        self.lbl_frame.setStyleSheet("color:#ccc; min-width: 120px;")
        nav_bar.addWidget(self.lbl_frame)

        r_layout.addLayout(nav_bar)

        root.addWidget(right, 1)

    def _wire_signals(self) -> None:
        # Detection params (findsat_mrt pipeline)
        self.sp_snr.valueChanged.connect(self._on_params_changed)
        self.sp_min_len.valueChanged.connect(self._on_params_changed)
        self.sp_max_w.valueChanged.connect(self._on_params_changed)
        self.cb_persistence.toggled.connect(self._on_params_changed)
        self.sp_persist_frac.valueChanged.connect(self._on_params_changed)
        self.sp_persist_chunk.valueChanged.connect(self._on_params_changed)
        self.sp_processes.valueChanged.connect(self._on_params_changed)
        self.sp_dilate.valueChanged.connect(self._on_params_changed)
        self.cmb_mono_mode.currentIndexChanged.connect(self._on_params_changed)
        self.cb_protect.toggled.connect(self._on_params_changed)
        self.sp_star_sigma.valueChanged.connect(self._on_params_changed)
        self.sp_star_dil.valueChanged.connect(self._on_params_changed)
        # Inpaint param changes trigger a Cleaned-Preview refresh when
        # the user is currently in that view -- otherwise the user has
        # to switch View away and back to see the new result.
        self.cmb_method.currentIndexChanged.connect(self._on_inpaint_param_changed)
        self.sp_strip.valueChanged.connect(self._on_inpaint_param_changed)
        self.cb_match_noise.toggled.connect(self._on_inpaint_param_changed)

        self.cmb_view.currentIndexChanged.connect(self._on_view_changed)

        self.btn_detect.clicked.connect(self._on_detect_current)
        self.btn_apply_current.clicked.connect(self._on_apply_current)
        self.btn_skip_current.clicked.connect(self._on_skip_current)
        self.btn_apply_all.clicked.connect(self._on_apply_all)
        self.btn_help.clicked.connect(self._show_help_dialog)
        self.btn_coffee.clicked.connect(self._show_coffee_dialog)
        self.btn_close.clicked.connect(self.close)
        self.btn_apply_rec.clicked.connect(self._on_apply_recommendation)

        self.btn_first.clicked.connect(lambda: self._navigate(0, absolute=True))
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(+1))
        self.btn_last.clicked.connect(lambda: self._navigate(len(self.paths) - 1, absolute=True))
        self.slider.valueChanged.connect(self._on_slider_change)

        self.detection_complete.connect(self._on_detection_complete)
        self.detection_progress.connect(self._on_detection_progress)

        self.cmb_scan.currentIndexChanged.connect(self._on_scan_mode_changed)

        # Disable persistence sub-fields when the persistence check is off
        self.cb_persistence.toggled.connect(self._update_persistence_enabled)
        # Disable strip-width when inpaint method is OpenCV NS (it's only
        # used by the perpendicular-strip method)
        self.cmb_method.currentIndexChanged.connect(self._update_strip_enabled)
        # Warn once (per QSettings) when the user picks Biharmonic — it's
        # mathematically the most "sophisticated" option but has known
        # numerical instability on long thin masks. Most users see the
        # artefact and assume the whole tool is broken; the warning
        # short-circuits that loop.
        self.cmb_method.currentIndexChanged.connect(self._maybe_warn_biharmonic)

        # Line-selection toolbar
        self.canvas.selection_toggled.connect(self._on_line_toggled)
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_select_none.clicked.connect(self._on_select_none)
        self.btn_select_invert.clicked.connect(self._on_select_invert)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Left"), self, activated=lambda: self._navigate(-1))
        QShortcut(QKeySequence("Right"), self, activated=lambda: self._navigate(+1))
        QShortcut(QKeySequence("Home"), self, activated=lambda: self._navigate(0, absolute=True))
        QShortcut(QKeySequence("End"), self,
                  activated=lambda: self._navigate(len(self.paths) - 1, absolute=True))
        QShortcut(QKeySequence("Escape"), self, activated=self.close)

    # ---- Settings ----

    def _load_settings(self) -> None:
        s_ = self._settings
        try:
            self.params.snr_threshold = float(s_.value("snr_threshold", self.params.snr_threshold))
            self.params.min_length = int(s_.value("min_length", self.params.min_length))
            self.params.max_width = int(s_.value("max_width", self.params.max_width))
            self.params.check_persistence = (
                str(s_.value("check_persistence", self.params.check_persistence)).lower()
                in ("1", "true")
            )
            self.params.min_persistence = float(s_.value("min_persistence", self.params.min_persistence))
            self.params.persistence_chunk = int(s_.value("persistence_chunk", self.params.persistence_chunk))
            self.params.min_persistence_snr = float(s_.value("min_persistence_snr", self.params.min_persistence_snr))
            self.params.processes = int(s_.value("processes", self.params.processes))
            self.params.scan_mode = str(s_.value("scan_mode", self.params.scan_mode))
            self.params.downsample = int(s_.value("downsample", self.params.downsample))
            self.params.theta_step_deg = float(s_.value("theta_step_deg", self.params.theta_step_deg))
            stored_mono_mode = str(
                s_.value("mono_mode", self.params.mono_mode)
            )
            if stored_mono_mode in ("mean", "max"):
                self.params.mono_mode = stored_mono_mode
            self.params.dilation_radius = int(s_.value("dilation_radius", self.params.dilation_radius))
            self.params.protect_stars = (
                str(s_.value("protect_stars", self.params.protect_stars)).lower() in ("1", "true")
            )
            self.params.star_sigma = float(s_.value("star_sigma", self.params.star_sigma))
            self.params.star_dilation = int(s_.value("star_dilation", self.params.star_dilation))
            stored_method = str(
                s_.value("inpaint_method", self.params.inpaint_method)
            )
            # Whitelist the stored value: if the user upgraded from an
            # older release whose method name no longer exists (e.g. a
            # renamed key), silently fall back to the current default
            # rather than letting the dispatcher's else-branch route to
            # whatever the last fallback happens to be.
            if stored_method in INPAINT_METHOD_LABELS:
                self.params.inpaint_method = stored_method
            else:
                log.warning(
                    "Unknown stored inpaint_method '%s' — reverting to "
                    "default '%s'", stored_method, self.params.inpaint_method,
                )
            self.params.strip_width = int(s_.value("strip_width", self.params.strip_width))
            self.params.match_sky_noise = (
                str(s_.value("match_sky_noise", self.params.match_sky_noise)).lower()
                in ("1", "true")
            )
            self.view_mode = str(s_.value("view_mode", self.view_mode))
            confirm_each = (str(s_.value("confirm_each", "false")).lower() in ("1", "true"))
            self.cb_confirm_each.setChecked(confirm_each)
        except (TypeError, ValueError):
            pass

        # Push into widgets
        self.sp_snr.setValue(self.params.snr_threshold)
        self.sp_min_len.setValue(self.params.min_length)
        self.sp_max_w.setValue(self.params.max_width)
        self.cb_persistence.setChecked(self.params.check_persistence)
        self.sp_persist_frac.setValue(self.params.min_persistence)
        self.sp_persist_chunk.setValue(self.params.persistence_chunk)
        self.sp_processes.setValue(self.params.processes)
        idx_scan = self.cmb_scan.findData(self.params.scan_mode)
        if idx_scan >= 0:
            self.cmb_scan.blockSignals(True)
            self.cmb_scan.setCurrentIndex(idx_scan)
            self.cmb_scan.blockSignals(False)
        self.sp_dilate.setValue(self.params.dilation_radius)
        idx_mm = self.cmb_mono_mode.findData(self.params.mono_mode)
        if idx_mm >= 0:
            self.cmb_mono_mode.blockSignals(True)
            self.cmb_mono_mode.setCurrentIndex(idx_mm)
            self.cmb_mono_mode.blockSignals(False)
        self.cb_protect.setChecked(self.params.protect_stars)
        self.sp_star_sigma.setValue(self.params.star_sigma)
        self.sp_star_dil.setValue(self.params.star_dilation)
        idx = self.cmb_method.findData(self.params.inpaint_method)
        if idx >= 0:
            self.cmb_method.setCurrentIndex(idx)
        self.sp_strip.setValue(self.params.strip_width)
        idx = self.cmb_view.findData(self.view_mode)
        if idx >= 0:
            self.cmb_view.setCurrentIndex(idx)

        # If the restored inpaint method is Biharmonic, the user hasn't
        # actively re-selected it this session — the per-selection
        # warning hook in _maybe_warn_biharmonic would never fire. Show
        # the warning once on startup so they're reminded of the ringing
        # caveat. Delayed via QTimer so the dialog appears after the
        # main window is on screen (and after the workflow dialog if
        # that one is also showing).
        if self.params.inpaint_method == "biharmonic":
            QTimer.singleShot(800, self._maybe_warn_biharmonic)

    def _save_settings(self) -> None:
        s_ = self._settings
        s_.setValue("snr_threshold", self.params.snr_threshold)
        s_.setValue("min_length", self.params.min_length)
        s_.setValue("max_width", self.params.max_width)
        s_.setValue("check_persistence", self.params.check_persistence)
        s_.setValue("min_persistence", self.params.min_persistence)
        s_.setValue("persistence_chunk", self.params.persistence_chunk)
        s_.setValue("min_persistence_snr", self.params.min_persistence_snr)
        s_.setValue("processes", self.params.processes)
        s_.setValue("scan_mode", self.params.scan_mode)
        s_.setValue("downsample", self.params.downsample)
        s_.setValue("theta_step_deg", self.params.theta_step_deg)
        s_.setValue("dilation_radius", self.params.dilation_radius)
        s_.setValue("mono_mode", self.params.mono_mode)
        s_.setValue("protect_stars", self.params.protect_stars)
        s_.setValue("star_sigma", self.params.star_sigma)
        s_.setValue("star_dilation", self.params.star_dilation)
        s_.setValue("inpaint_method", self.params.inpaint_method)
        s_.setValue("strip_width", self.params.strip_width)
        s_.setValue("match_sky_noise", self.params.match_sky_noise)
        s_.setValue("view_mode", self.view_mode)
        s_.setValue("confirm_each", self.cb_confirm_each.isChecked())

    def closeEvent(self, ev) -> None:  # noqa: N802
        self._save_settings()
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self._executor.shutdown(wait=False)
        super().closeEvent(ev)

    def resizeEvent(self, ev) -> None:  # noqa: N802
        """When the window resizes, the status label's available width
        changes — so re-elide the displayed text against the new width.
        The full text is preserved in the tooltip, so this is just a
        visual refresh.

        Re-entrancy guard: ``_set_status_text`` calls ``QLabel.setText``,
        which can in principle trigger another resize-event on the
        parent if the layout has to reflow. The flag ensures we run the
        elision exactly once per logical resize event, even on
        fractional-DPI Qt builds that fire nested events.
        """
        super().resizeEvent(ev)
        if getattr(self, "_in_resize_event", False):
            return
        self._in_resize_event = True
        try:
            full = self.lbl_info.toolTip()
            if full:
                self._set_status_text(full)
        except Exception:
            pass
        finally:
            self._in_resize_event = False

    # ---- Param updates ----

    def _read_params_from_widgets(self) -> None:
        self.params.snr_threshold = float(self.sp_snr.value())
        self.params.min_length = int(self.sp_min_len.value())
        self.params.max_width = int(self.sp_max_w.value())
        self.params.check_persistence = self.cb_persistence.isChecked()
        self.params.min_persistence = float(self.sp_persist_frac.value())
        self.params.persistence_chunk = int(self.sp_persist_chunk.value())
        self.params.processes = int(self.sp_processes.value())
        self.params.dilation_radius = int(self.sp_dilate.value())
        self.params.mono_mode = str(self.cmb_mono_mode.currentData())
        self.params.protect_stars = self.cb_protect.isChecked()
        self.params.star_sigma = float(self.sp_star_sigma.value())
        self.params.star_dilation = int(self.sp_star_dil.value())
        self.params.inpaint_method = str(self.cmb_method.currentData())
        self.params.strip_width = int(self.sp_strip.value())
        self.params.match_sky_noise = self.cb_match_noise.isChecked()

    def _on_params_changed(self) -> None:
        self._read_params_from_widgets()
        # Don't auto-rerun detection on every spinbox tick -- user clicks Detect.

    def _on_inpaint_param_changed(self) -> None:
        """Inpaint params (method / strip width / match-noise) -- update
        the Cleaned Preview live if that's the active view. The detection
        and mask are unchanged; only the post-detection rendering needs
        to re-run."""
        self._read_params_from_widgets()
        # Refresh the recommendation banner so the "currently selected"
        # marker tracks the dropdown change.
        if hasattr(self, "rec_container"):
            self._update_inpaint_recommendation()
        if (
            self.view_mode == "cleaned_preview"
            and self.last_detection is not None
            and self.last_detection.detection is not None
            and self.last_detection.detection.has_trails
        ):
            self._refresh_canvas()

    def _on_scan_mode_changed(self) -> None:
        """Apply a preset bundle of params when the scan mode changes.

        v0.8.9: scan-mode now also auto-tunes ``processes`` (MRT worker
        count). Deep mode runs on a downsample-1 image whose MRT is
        much larger, so the per-process overhead amortises better at
        full CPU; quick mode has a tiny MRT where extra workers
        actually add startup overhead.
        """
        try:
            _cpu = os.cpu_count() or 4
        except Exception:
            _cpu = 4
        mode = str(self.cmb_scan.currentData())
        self.params.scan_mode = mode
        if mode == "quick":
            self.params.downsample = 4
            self.params.theta_step_deg = 1.0
            self.params.check_persistence = False
            # Tiny MRT (16× cheaper than full-res). 2 workers is the
            # sweet spot — more processes pay startup cost on a job
            # that's <1 s anyway.
            self.params.processes = max(2, min(4, _cpu // 2))
        elif mode == "deep":
            self.params.downsample = 1
            self.params.theta_step_deg = 0.5
            self.params.check_persistence = True
            # Full-resolution MRT — let it use all cores. The MRT itself
            # is embarrassingly parallel over theta angles, so 8 cores
            # = ~8× speedup on the dominant phase.
            self.params.processes = max(2, _cpu)
        else:  # normal
            self.params.downsample = 2
            self.params.theta_step_deg = 0.5
            self.params.check_persistence = True
            # Compromise. ~half the cores keeps the rest of the system
            # responsive during interactive Detect.
            self.params.processes = max(2, min(8, _cpu // 2 + 1))
        # Reflect the new process count in the spinner so power users
        # who want to override see the preset value first.
        try:
            self.sp_processes.blockSignals(True)
            self.sp_processes.setValue(self.params.processes)
        finally:
            self.sp_processes.blockSignals(False)
        # Push the persistence checkbox so the user sees it match the preset
        try:
            self.cb_persistence.blockSignals(True)
            self.cb_persistence.setChecked(self.params.check_persistence)
        finally:
            self.cb_persistence.blockSignals(False)

    def _update_persistence_enabled(self) -> None:
        """Grey out persistence sub-fields when the check is off."""
        enabled = self.cb_persistence.isChecked()
        self.sp_persist_frac.setEnabled(enabled)
        self.sp_persist_chunk.setEnabled(enabled)

    def _update_strip_enabled(self) -> None:
        """Strip width is only used by the perpendicular-strip method."""
        is_strip = (str(self.cmb_method.currentData()) == "perp_strip")
        self.sp_strip.setEnabled(is_strip)

    def _maybe_warn_biharmonic(self) -> None:
        """Show a one-time modal warning when the user selects Biharmonic.

        Biharmonic is the only inpaint method here that solves a PDE
        (∇⁴u = 0). The biharmonic equation has no maximum principle, so
        on long thin masks the iterative solver overshoots / undershoots
        and produces a periodic 'string of pearls' dark-spot artefact
        along the trail centreline. This is a mathematical property of
        the method, not a bug we can fix server-side — but most users
        try it first (because the label sounds best) and conclude the
        tool is broken when the artefact appears. The warning is shown
        once per machine via QSettings and has a 'don't show again'
        opt-out (defaulted to off so a future re-tickle still warns).
        """
        if str(self.cmb_method.currentData()) != "biharmonic":
            return
        if not hasattr(self, "_settings") or self._settings is None:
            return
        suppressed = str(
            self._settings.value("biharmonic_warning_suppressed", "false")
        ).lower() == "true"
        if suppressed:
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Biharmonic — experimental")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            "<b>Biharmonic is marked experimental for a reason.</b>"
        )
        box.setInformativeText(
            "It solves ∇⁴u = 0 inside the mask — mathematically elegant, "
            "but the biharmonic equation has <i>no maximum principle</i>, "
            "so on long thin satellite-trail masks the solver overshoots "
            "and undershoots its sky-boundary values periodically. "
            "Visually this looks like a regular pattern of dark dots along "
            "the trail (\"string of pearls\"). It is not a bug we can fix "
            "— it is a property of the equation.<br><br>"
            "Recommended methods for normal use:<br>"
            "&nbsp;&nbsp;• <b>Perpendicular Strip Median</b> (default) — "
            "robust on flashing-satellite trails<br>"
            "&nbsp;&nbsp;• <b>Nearest Neighbor + Smooth</b> — fast, no "
            "overshoot<br><br>"
            "Use Biharmonic only on short, compact masks (single isolated "
            "blobs, very short trails) where the geometry stays "
            "well-conditioned."
        )
        cb = QCheckBox("Don't show this warning again")
        box.setCheckBox(cb)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        if cb.isChecked():
            try:
                self._settings.setValue(
                    "biharmonic_warning_suppressed", "true",
                )
            except Exception:
                pass

    def _set_status_text(self, text: str) -> None:
        """Single setter for the top-bar status label.

        Stores the full text as the tooltip (visible on hover) and
        displays an elided version that fits the label's current width
        on a single line. This guarantees the top bar never wraps to
        two lines and pushes the canvas down — the original cause of
        the 'image shifts after Detect' UX bug.
        """
        if not text:
            self.lbl_info.setText("")
            self.lbl_info.setToolTip("")
            return
        # Always preserve full text on hover.
        self.lbl_info.setToolTip(text)
        try:
            fm = self.lbl_info.fontMetrics()
            avail = max(self.lbl_info.width() - 8, 100)
            elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, avail)
        except Exception:
            elided = text
        self.lbl_info.setText(elided)

    def _on_detection_progress(self, stage: str) -> None:
        """Update the progress bar / status label with the current phase."""
        labels = {
            "preprocess": "Background subtraction…",
            "mrt":        "Computing Median Radon Transform…",
            "mrt_cached": "Reusing cached MRT (fast path)…",
            "peaks":      "Finding peaks in MRT space…",
            "filter":     "Validating candidates (width + persistence)…",
            "mask":       "Building trail mask…",
        }
        msg = labels.get(stage, stage)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat(msg)
        self._set_status_text(msg)

    def _on_view_changed(self) -> None:
        self.view_mode = str(self.cmb_view.currentData())
        # Mask Overlay and Cleaned Preview need an active detection to
        # have anything to draw. Tell the user explicitly when they
        # switch to one without first running Detect.
        det = (
            self.last_detection.detection
            if self.last_detection is not None else None
        )
        needs_det = self.view_mode in ("mask_overlay", "cleaned_preview")
        if needs_det and (det is None or not det.has_trails):
            label_for = {
                "mask_overlay": "Mask Overlay",
                "cleaned_preview": "Cleaned Preview",
            }[self.view_mode]
            self._set_status_text(
                f"{label_for} needs a detection. "
                "Click 'Detect Trails on Current' first."
            )
        self._refresh_canvas()

    # ---- Navigation ----

    def _navigate(self, delta: int, absolute: bool = False) -> None:
        if not self.paths:
            return
        if absolute:
            new_idx = max(0, min(delta, len(self.paths) - 1))
        else:
            new_idx = max(0, min(self.current_index + delta, len(self.paths) - 1))
        if new_idx == self.current_index:
            return
        self.current_index = new_idx
        self.slider.blockSignals(True)
        self.slider.setValue(new_idx)
        self.slider.blockSignals(False)
        self._update_frame_label()
        self._load_and_show(new_idx, autodetect=False)

    def _on_slider_change(self, value: int) -> None:
        self.current_index = value
        self._update_frame_label()
        self._load_and_show(value, autodetect=False)

    def _update_frame_label(self) -> None:
        total = len(self.paths)
        if total == 0:
            self.lbl_frame.setText("0 / 0")
            return
        name = os.path.basename(self.paths[self.current_index])
        self.lbl_frame.setText(f"{self.current_index + 1} / {total}  —  {name}")

    # ---- Frame load + detect ----

    def _show_placeholder(self) -> None:
        self.canvas.set_placeholder("Loading...")
        self.canvas.set_image(None)

    def _load_and_show(self, index: int, autodetect: bool = False) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._set_status_text("Loading frame...")
        self.canvas.set_placeholder("Loading...")
        self.canvas.set_image(None)

        params_snapshot = self._snapshot_params()
        path = self.paths[index]

        def _work():
            try:
                frame = load_frame_data(self.siril, path)
                if frame is None:
                    raise RuntimeError("load_image_from_file returned None")
                stretched = stretch_for_display(frame)
                detection: TrailDetection | None = None
                if autodetect:
                    mono = to_mono_float32(
                        frame,
                        mode=getattr(params_snapshot, "mono_mode", "mean"),
                    )
                    detection = detect_trails(mono, params_snapshot)
                return DetectionResult(index, path, frame, stretched, detection)
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
                log.debug("Load/detect failed for %s: %s\n%s", path, err, traceback.format_exc())
                empty_mask = np.zeros((1, 1), dtype=np.uint8)
                empty_det = TrailDetection([], empty_mask, empty_mask, empty_mask, 0.0)
                return DetectionResult(
                    index, path,
                    np.zeros((1, 1), dtype=np.float32),
                    np.zeros((1, 1), dtype=np.uint8),
                    empty_det,
                    error=err,
                )

        fut = self._executor.submit(_work)
        fut.add_done_callback(lambda f: self.detection_complete.emit(f.result()))

    def _make_cache_key(self, path: str, params: DetectionParams) -> tuple:
        """Cache key for the MRT result: identifies what would change the
        MRT itself. Threshold / max_width / persistence are NOT in the
        key because they only affect post-MRT filtering."""
        return (
            path,
            int(params.downsample),
            round(float(params.theta_step_deg), 3),
            int(params.min_length),
        )

    def _put_in_mrt_cache(self, key: tuple, value: object) -> None:
        """LRU put: move to end on insert / re-insert, evict oldest if over cap."""
        if key in self._mrt_cache:
            self._mrt_cache.move_to_end(key)
            self._mrt_cache[key] = value
            return
        self._mrt_cache[key] = value
        while len(self._mrt_cache) > self._mrt_cache_max_size:
            self._mrt_cache.popitem(last=False)

    def _clear_mrt_cache(self) -> None:
        self._mrt_cache.clear()

    def _snapshot_params(self) -> DetectionParams:
        p = DetectionParams()
        p.snr_threshold = self.params.snr_threshold
        p.min_length = self.params.min_length
        p.max_width = self.params.max_width
        p.check_persistence = self.params.check_persistence
        p.min_persistence = self.params.min_persistence
        p.persistence_chunk = self.params.persistence_chunk
        p.min_persistence_snr = self.params.min_persistence_snr
        p.processes = self.params.processes
        p.scan_mode = self.params.scan_mode
        p.downsample = self.params.downsample
        p.theta_step_deg = self.params.theta_step_deg
        p.dilation_radius = self.params.dilation_radius
        p.protect_stars = self.params.protect_stars
        p.star_sigma = self.params.star_sigma
        p.star_dilation = self.params.star_dilation
        p.border_margin = self.params.border_margin
        p.inpaint_method = self.params.inpaint_method
        p.strip_width = self.params.strip_width
        p.match_sky_noise = self.params.match_sky_noise
        return p

    def _on_detect_current(self) -> None:
        if self._busy:
            return
        self._read_params_from_widgets()
        self._set_busy(True)
        self._set_status_text("Detecting trails...")

        params_snapshot = self._snapshot_params()
        path = self.paths[self.current_index]
        index = self.current_index

        # Use already-loaded frame if it's the current one
        if self.last_detection is not None and self.last_detection.index == index and self.last_detection.frame is not None:
            frame = self.last_detection.frame
            stretched = self.last_detection.stretched

            progress_emit = lambda stage: self.detection_progress.emit(stage)
            cache_key = self._make_cache_key(path, params_snapshot)
            cache_dict = self._mrt_cache

            def _work_redetect():
                try:
                    mono = to_mono_float32(
                        frame,
                        mode=getattr(params_snapshot, "mono_mode", "mean"),
                    )
                    det = detect_trails(
                        mono, params_snapshot,
                        progress_cb=progress_emit,
                        mrt_cache=cache_dict, cache_key=cache_key,
                    )
                    return DetectionResult(index, path, frame, stretched, det)
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"
                    empty_mask = np.zeros((1, 1), dtype=np.uint8)
                    empty_det = TrailDetection([], empty_mask, empty_mask, empty_mask, 0.0)
                    return DetectionResult(index, path, frame, stretched, empty_det, error=err)

            fut = self._executor.submit(_work_redetect)
            fut.add_done_callback(lambda f: self.detection_complete.emit(f.result()))
            return

        # Otherwise reload + detect
        progress_emit = lambda stage: self.detection_progress.emit(stage)
        cache_key = self._make_cache_key(path, params_snapshot)
        cache_dict = self._mrt_cache

        def _work_load_detect():
            try:
                frame = load_frame_data(self.siril, path)
                if frame is None:
                    raise RuntimeError("load_image_from_file returned None")
                stretched = stretch_for_display(frame)
                mono = to_mono_float32(
                    frame,
                    mode=getattr(params_snapshot, "mono_mode", "mean"),
                )
                det = detect_trails(
                    mono, params_snapshot,
                    progress_cb=progress_emit,
                    mrt_cache=cache_dict, cache_key=cache_key,
                )
                return DetectionResult(index, path, frame, stretched, det)
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
                empty_mask = np.zeros((1, 1), dtype=np.uint8)
                empty_det = TrailDetection([], empty_mask, empty_mask, empty_mask, 0.0)
                return DetectionResult(
                    index, path,
                    np.zeros((1, 1), dtype=np.float32),
                    np.zeros((1, 1), dtype=np.uint8),
                    empty_det,
                    error=err,
                )

        fut = self._executor.submit(_work_load_detect)
        fut.add_done_callback(lambda f: self.detection_complete.emit(f.result()))

    def _on_detection_complete(self, result: DetectionResult) -> None:
        self.last_detection = result
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("")

        # Enforce MRT-cache LRU + size cap. detect_trails just sets the
        # entry; we age it here so the most-recent (current frame's)
        # cache entry stays warm.
        while len(self._mrt_cache) > self._mrt_cache_max_size:
            self._mrt_cache.popitem(last=False)

        if result.error:
            self._set_status_text(f"Error: {result.error}")
            QMessageBox.warning(self, "Frame Error",
                                f"Could not load / process frame:\n{result.error}")
            return

        det = result.detection
        if det is None or not det.has_trails:
            note = f"  —  {det.notes}" if (det is not None and det.notes) else ""
            self._set_status_text(f"No trails detected.{note}")
        else:
            # Many-candidate safety net: with the segmentation pipeline the
            # typical false-positive rate is very low (the elongation +
            # straightness filter does most of the work). But if relaxed
            # thresholds yield a flood of candidates, default to "keep all"
            # so the user can click only the ones they want to remove
            # instead of having to deselect dozens.
            if len(det.lines) > 10:
                det.selections = [False] * len(det.lines)
                det.rebuild_effective_mask(self._snapshot_params())
                hint = (
                    f"{len(det.lines)} candidate(s) detected. All set to "
                    "KEEP — click each line you want to remove. Tighten "
                    "elongation / straightness sliders to filter more "
                    "aggressively."
                )
                self._set_status_text(hint)
            else:
                note = f"  —  {det.notes}" if det.notes else ""
                self._set_status_text(f"{len(det.lines)} trail(s) detected.{note}")

        self._update_selection_label()
        self._update_inpaint_recommendation()
        self._refresh_canvas()

    def _update_inpaint_recommendation(self) -> None:
        """Show / hide the inpaint-method recommendation banner.

        Called after every detection. Compares the recommended method
        against the currently selected method:
          - if they match, the banner shows a confirmation (green-ish)
          - if they differ, the banner suggests switching and the
            "Apply" button becomes meaningful
          - if there's no detection or no recommendation, hide.
        """
        det = self.last_detection.detection if self.last_detection else None
        if det is None or not det.has_trails or not det.recommended_method:
            self.rec_container.setVisible(False)
            return

        rec_id = det.recommended_method
        rec_label = INPAINT_METHOD_LABELS.get(rec_id, rec_id)
        current_id = str(self.cmb_method.currentData())
        if rec_id == current_id:
            self.lbl_recommendation.setText(
                f"<b>💡 Recommendation:</b> <b>{rec_label}</b> "
                f"<span style='color:#88ff88;'>(currently selected)</span>"
                f"<br><span style='color:#aab;'>{det.recommendation_rationale}</span>"
            )
            self.btn_apply_rec.setEnabled(False)
            self.btn_apply_rec.setText("✓ in use")
        else:
            self.lbl_recommendation.setText(
                f"<b>💡 Recommendation:</b> <b>{rec_label}</b>"
                f"<br><span style='color:#aab;'>{det.recommendation_rationale}</span>"
            )
            self.btn_apply_rec.setEnabled(True)
            self.btn_apply_rec.setText("Apply")
        self.rec_container.setVisible(True)

    def _on_apply_recommendation(self) -> None:
        """Switch the dropdown to the recommended method. Does NOT
        re-run detection — only swaps the inpaint choice and refreshes
        the Cleaned Preview if it's currently shown."""
        det = self.last_detection.detection if self.last_detection else None
        if det is None or not det.recommended_method:
            return
        idx = self.cmb_method.findData(det.recommended_method)
        if idx >= 0:
            self.cmb_method.setCurrentIndex(idx)
        # _on_inpaint_param_changed will be triggered automatically by
        # currentIndexChanged → it pushes params + refreshes preview.
        self._update_inpaint_recommendation()

    def _update_selection_label(self) -> None:
        det = self.last_detection.detection if self.last_detection else None
        if det is None or not det.has_trails:
            self.lbl_selection.setText("")
            self.lbl_pick_hint.setVisible(False)
            self.btn_select_all.setEnabled(False)
            self.btn_select_none.setEnabled(False)
            self.btn_select_invert.setEnabled(False)
            return
        total = len(det.lines)
        n_sel = sum(1 for s in det.selections if s)
        self.lbl_selection.setText(
            f"{n_sel} of {total} line(s) marked for removal  "
            f"—  ~{det.pixels_to_inpaint:,} px to inpaint"
        )
        self.lbl_pick_hint.setVisible(True)
        self.btn_select_all.setEnabled(n_sel < total)
        self.btn_select_none.setEnabled(n_sel > 0)
        self.btn_select_invert.setEnabled(total > 0)

    def _on_line_toggled(self, idx: int) -> None:
        if self.last_detection is None or self.last_detection.detection is None:
            return
        det = self.last_detection.detection
        if not (0 <= idx < len(det.selections)):
            return
        det.selections[idx] = not det.selections[idx]
        det.rebuild_effective_mask(self._snapshot_params())
        self._update_selection_label()
        # Push the updated selections back to the canvas + refresh underlay
        # (mask overlay / cleaned preview reflect the new mask).
        self._refresh_canvas()

    def _on_select_all(self) -> None:
        if self.last_detection is None or self.last_detection.detection is None:
            return
        det = self.last_detection.detection
        det.selections = [True] * len(det.lines)
        det.rebuild_effective_mask(self._snapshot_params())
        self._update_selection_label()
        self._refresh_canvas()

    def _on_select_none(self) -> None:
        if self.last_detection is None or self.last_detection.detection is None:
            return
        det = self.last_detection.detection
        det.selections = [False] * len(det.lines)
        det.rebuild_effective_mask(self._snapshot_params())
        self._update_selection_label()
        self._refresh_canvas()

    def _on_select_invert(self) -> None:
        if self.last_detection is None or self.last_detection.detection is None:
            return
        det = self.last_detection.detection
        det.selections = [not s for s in det.selections]
        det.rebuild_effective_mask(self._snapshot_params())
        self._update_selection_label()
        self._refresh_canvas()

    def _refresh_canvas(self, preserve_lines: bool = False) -> None:
        if self.last_detection is None:
            return
        result = self.last_detection
        stretched = result.stretched
        det = result.detection
        if stretched is None or stretched.size == 0:
            self.canvas.set_image(None)
            return

        # Determine source-array dimensions for the line-overlay transform.
        # `stretched` is uint8 mono (H,W) or RGB (3,H,W) -- same orientation
        # as the numpy frame the detector ran on.
        if stretched.ndim == 3:
            ih, iw = stretched.shape[1], stretched.shape[2]
        else:
            ih, iw = stretched.shape

        if self.view_mode == "stretched" or det is None or not det.has_trails:
            img = stretched_to_qimage(stretched)
        elif self.view_mode == "mask_overlay":
            img = overlay_mask_on_stretched(stretched, det.effective_mask)
        elif self.view_mode == "cleaned_preview":
            if det is not None and det.has_selected:
                cleaned = inpaint_frame(result.frame, det, self._snapshot_params())
                # DIAGNOSTIC: count how many pixels actually changed. This
                # lets the user see whether the inpaint is running and
                # producing modifications.
                try:
                    n_diff = int(np.count_nonzero(cleaned != result.frame))
                except Exception:
                    n_diff = -1
                target = int(det.pixels_to_inpaint)
                note_suffix = (
                    f"  —  {det.notes}" if det.notes else ""
                )
                self._set_status_text(
                    f"Cleaned Preview — inpaint changed "
                    f"{n_diff:,} pixels (mask: {target:,} px expected)"
                    f"{note_suffix}"
                )
                cleaned_stretched = stretch_for_display(cleaned)
                img = stretched_to_qimage(cleaned_stretched)
            else:
                img = stretched_to_qimage(stretched)
        else:
            img = stretched_to_qimage(stretched)

        self.canvas.set_image(img, image_size=(iw, ih))
        # In Cleaned Preview we deliberately HIDE the selection-line
        # overlay -- otherwise the green/grey lines drawn on top of the
        # cleaned image are easily misread as "the trail is still
        # there", when in fact the line is just the selection marker
        # and the underlying pixels have already been inpainted.
        # In Mask Overlay and Stretched views we keep the overlay so
        # the user can interact (click to toggle, see what's detected).
        if det is not None and det.has_trails and self.view_mode != "cleaned_preview":
            self.canvas.set_lines(det.lines, det.selections)
        else:
            self.canvas.clear_lines()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for w in (
            self.btn_detect, self.btn_apply_current, self.btn_skip_current,
            self.btn_apply_all, self.btn_first, self.btn_prev,
            self.btn_next, self.btn_last, self.slider,
        ):
            w.setEnabled(not busy)

    # ---- Apply actions ----

    def _on_apply_current(self) -> None:
        if self._busy or self.last_detection is None:
            return
        det = self.last_detection.detection
        if det is None or not det.has_trails:
            QMessageBox.information(
                self, "Nothing to Apply",
                "No trails were detected on this frame. Run 'Detect Trails on Current' first, "
                "or tune the thresholds if you can see a trail in the image."
            )
            return
        if not det.has_selected:
            QMessageBox.information(
                self, "Nothing Selected",
                "All detected lines are currently marked as 'keep'. "
                "Click a line in the preview (or use Select All) to mark "
                "at least one line for removal before applying."
            )
            return

        path = self.last_detection.path
        originals_dir = os.path.join(os.path.dirname(path), "originals")
        n_total = len(det.lines)
        n_sel = sum(1 for s in det.selections if s)

        confirm = QMessageBox.question(
            self, "Apply to Current Frame",
            f"Clean this frame?\n\n"
            f"  Source: {os.path.basename(path)}\n"
            f"  Lines marked for removal: {n_sel} of {n_total}\n"
            f"  Pixels to replace: {det.pixels_to_inpaint:,}\n\n"
            f"The original will be moved to:\n  {originals_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True)
        self._set_status_text("Applying...")

        params_snapshot = self._snapshot_params()
        # Pass through the user-curated detection so apply uses the actual
        # selected lines, not a fresh re-detection that ignores selections.
        precomp_frame = self.last_detection.frame
        precomp_det = det

        def _work():
            return apply_to_path(
                self.siril, path, params_snapshot, originals_dir,
                precomputed_frame=precomp_frame,
                precomputed_detection=precomp_det,
            )

        fut = self._executor.submit(_work)

        def _done(f):
            outcome: ApplyOutcome = f.result()
            QTimer.singleShot(0, lambda: self._after_apply_single(outcome))

        fut.add_done_callback(_done)

    def _after_apply_single(self, outcome: ApplyOutcome) -> None:
        self._set_busy(False)
        self._append_audit_line(outcome)

        # The cleaned file is different content from the original we cached.
        # Invalidate the entire MRT cache so a subsequent Detect runs fresh.
        if outcome.status == "cleaned":
            self._clear_mrt_cache()

        if outcome.status == "cleaned":
            self._set_status_text(
                f"Cleaned. {outcome.lines} trail(s), {outcome.pixels_replaced:,} px replaced."
            )
            self._log_siril(f"Cleaned {os.path.basename(outcome.path)}: "
                            f"{outcome.lines} trail(s), {outcome.pixels_replaced} px replaced.")
            # For RAW input the cleaned file has a new path (.fit). Update
            # self.paths so navigation/reload points at the new file.
            if outcome.cleaned_path and outcome.cleaned_path != outcome.path:
                try:
                    idx = self.paths.index(outcome.path)
                    self.paths[idx] = outcome.cleaned_path
                except ValueError:
                    pass
            self._update_frame_label()
            self._load_and_show(self.current_index, autodetect=False)
        elif outcome.status == "skipped_no_trail":
            self._set_status_text("Skipped: no trails detected (re-run detection if needed).")
        else:
            self._set_status_text(f"Error: {outcome.note}")
            QMessageBox.warning(self, "Apply Failed", outcome.note or "Unknown error")

    def _on_skip_current(self) -> None:
        self._navigate(+1)

    def _on_apply_all(self) -> None:
        if self._busy:
            return
        if not self.paths:
            return
        self._read_params_from_widgets()

        msg = (
            f"This will run detection + inpainting on all {len(self.paths)} frame(s) "
            f"in:\n  {self.folder}\n\n"
            f"Originals will be moved to the 'originals/' subfolder.\n"
            f"Cleaned FITS files will replace them in the source folder.\n\n"
        )
        if self.cb_confirm_each.isChecked():
            msg += "You will be asked to confirm each frame with a detected trail.\n\n"
        else:
            msg += "Frames with detected trails will be cleaned automatically.\n\n"
        msg += "Continue?"

        ans = QMessageBox.question(
            self, "Apply to All Frames", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self._run_batch()

    def _run_batch(self) -> None:
        self._cancel_batch = False
        self._set_busy(True)

        dlg = QProgressDialog("Processing frames...", "Cancel", 0, len(self.paths), self)
        dlg.setWindowTitle("Apply to All Frames")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(self._cancel_batch_action)
        # Make the label tall enough for the 3-line status block
        # (frame/total + cleaned/skipped/errors + elapsed/ETA).
        dlg.setMinimumWidth(560)

        # Wall-clock anchor for ETA calculation.
        import time as _time_mod
        _t0 = _time_mod.monotonic()

        def _fmt_dur(s: float) -> str:
            """Compact mm:ss / hh:mm:ss for elapsed/ETA display."""
            if s < 0 or not np.isfinite(s):
                return "—"
            s = int(round(s))
            h, rem = divmod(s, 3600)
            m, sec = divmod(rem, 60)
            if h > 0:
                return f"{h:d}:{m:02d}:{sec:02d}"
            return f"{m:d}:{sec:02d}"

        def _update_progress_label(
            current_idx: int, total: int, current_path: str,
            outcomes_so_far: list,
        ) -> None:
            """Multi-line status label: frame info + running counters
            + elapsed/ETA. Called every frame so the user always sees
            an up-to-date view, including during long single frames
            where the bar would otherwise look frozen."""
            n_clean = sum(1 for o in outcomes_so_far if o.status == "cleaned")
            n_skip = sum(
                1 for o in outcomes_so_far if o.status.startswith("skipped")
            )
            n_err = sum(1 for o in outcomes_so_far if o.status == "error")
            done = current_idx  # frames completed = index of the one about to start
            elapsed = _time_mod.monotonic() - _t0
            if done > 0:
                avg = elapsed / done
                remaining = total - done
                eta = avg * remaining
                eta_str = _fmt_dur(eta)
            else:
                eta_str = "estimating…"
            dlg.setLabelText(
                f"Frame {current_idx + 1}/{total}: "
                f"{os.path.basename(current_path)}\n"
                f"Cleaned: {n_clean}   Skipped: {n_skip}   Errors: {n_err}\n"
                f"Elapsed: {_fmt_dur(elapsed)}   ETA: {eta_str}"
            )

        originals_dir = os.path.join(self.folder, "originals")
        params_snapshot = self._snapshot_params()
        confirm_each = self.cb_confirm_each.isChecked()

        outcomes: list[ApplyOutcome] = []
        # Snapshot the path list (apply_to_path moves source files in-place,
        # so iterating the original list keeps indices stable).
        paths = list(self.paths)

        # ---- Pipelined batch (v0.8.8) ----
        # The work per frame splits cleanly into two phases:
        #   PHASE A: load_frame_data + to_mono_float32 + detect_trails
        #   PHASE B: apply_to_path (inpaint + write)
        # Phase A is I/O + CPU-heavy (MRT). Phase B is CPU + I/O. They
        # don't share state once the (frame, det) tuple is handed off.
        # We run Phase A for frame i+1 in a worker thread while the
        # main thread runs Phase B for frame i. Net effect: the slower
        # phase becomes the wall-clock floor instead of the sum.
        #
        # Caveats:
        #  - confirm_each=True needs a synchronous user dialog before
        #    each Phase B. We fall back to the serial path in that
        #    case (the user's reaction time dominates anyway).
        #  - The Siril RPC lock inside load_frame_data already
        #    serialises FITS/RAW reads — only the CPU portions overlap.
        #    TIFF/XISF reads go direct (tifffile/xisf) and overlap
        #    fully.
        #  - _cancel_batch is checked between phases; any in-flight
        #    Phase A future is drained so the executor shuts down
        #    cleanly.

        def _phase_a(path: str) -> tuple[str, np.ndarray | None, "TrailDetection | None", str]:
            """Load + mono-convert + detect. Returns (path, frame, det,
            error_msg). On error, frame and det may be None and
            error_msg is non-empty."""
            try:
                frame = load_frame_data(self.siril, path)
                if frame is None:
                    return path, None, None, "failed to load"
                mono = to_mono_float32(
                    frame,
                    mode=getattr(params_snapshot, "mono_mode", "mean"),
                )
                det = detect_trails(mono, params_snapshot)
                return path, frame, det, ""
            except Exception as exc:
                log.exception("Phase A failed for %s", path)
                return path, None, None, f"{type(exc).__name__}: {exc}"

        if confirm_each:
            # Serial path: user gates each frame, no benefit from
            # pipelining.
            pipeline_iter = ((path, *_phase_a(path)[1:]) for path in paths)
        else:
            from concurrent.futures import ThreadPoolExecutor

            def _gen_pipelined():
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="batch-prefetch") as ex:
                    # Prime: submit frame 0's Phase A
                    fut = ex.submit(_phase_a, paths[0]) if paths else None
                    for i, path in enumerate(paths):
                        if self._cancel_batch:
                            if fut is not None:
                                fut.cancel()
                            return
                        # Wait for current frame's Phase A to complete
                        path_done, frame, det, err = fut.result()
                        # Submit NEXT frame's Phase A so it overlaps
                        # with the Phase B we're about to do.
                        if i + 1 < len(paths):
                            fut = ex.submit(_phase_a, paths[i + 1])
                        else:
                            fut = None
                        yield path_done, frame, det, err

            pipeline_iter = _gen_pipelined()

        for i, path in enumerate(paths):
            if self._cancel_batch:
                break
            dlg.setValue(i)
            _update_progress_label(i, len(paths), path, outcomes)
            QApplication.processEvents()

            # Pull the (frame, det, err) tuple for this frame from the
            # pipeline (or serial generator).
            if confirm_each:
                # Inline Phase A for the serial / confirm-each path.
                path_done, frame, det, err = _phase_a(path)
            else:
                try:
                    path_done, frame, det, err = next(pipeline_iter)
                except StopIteration:
                    break

            if err:
                outcomes.append(ApplyOutcome(path, "error", note=err))
                continue
            if frame is None or det is None:
                outcomes.append(ApplyOutcome(path, "error", note="phase A returned no data"))
                continue
            if not det.has_trails or det.pixels_to_inpaint == 0:
                outcomes.append(ApplyOutcome(path, "skipped_no_trail", note=det.notes))
                continue

            if confirm_each:
                # Show the frame in the main window so the user can see what they're confirming
                self.current_index = i
                self.slider.blockSignals(True)
                self.slider.setValue(i)
                self.slider.blockSignals(False)
                self._update_frame_label()
                self.last_detection = DetectionResult(
                    i, path, frame, stretch_for_display(frame), det,
                )
                self._refresh_canvas()
                QApplication.processEvents()

                ans = QMessageBox.question(
                    self, "Confirm Trail Removal",
                    f"Frame {i + 1}/{len(paths)}: {os.path.basename(path)}\n\n"
                    f"  {len(det.lines)} trail(s) detected\n"
                    f"  ~{det.pixels_to_inpaint:,} px will be replaced\n\n"
                    "Clean this frame?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if ans == QMessageBox.StandardButton.Cancel:
                    self._cancel_batch = True
                    break
                if ans == QMessageBox.StandardButton.No:
                    outcomes.append(ApplyOutcome(path, "skipped_user", note="user skipped"))
                    continue

            # Phase B: apply_to_path (inpaint + write). This runs on
            # the main thread while the prefetch worker is already
            # loading + detecting paths[i+1] in the background.
            outcome = apply_to_path(
                self.siril, path, params_snapshot, originals_dir,
                precomputed_frame=frame,
                precomputed_detection=det,
            )
            outcomes.append(outcome)
            self._append_audit_line(outcome)
            # RAW -> FITS path rewrite so the slider/navigation reflects
            # the file that's actually on disk at index i now.
            if (outcome.status == "cleaned"
                    and outcome.cleaned_path
                    and outcome.cleaned_path != path):
                try:
                    j = self.paths.index(path)
                    self.paths[j] = outcome.cleaned_path
                except ValueError:
                    pass

        dlg.setValue(len(paths))
        dlg.close()
        self._set_busy(False)

        cleaned = sum(1 for o in outcomes if o.status == "cleaned")
        skipped = sum(1 for o in outcomes if o.status.startswith("skipped"))
        errors = sum(1 for o in outcomes if o.status == "error")
        summary = (
            f"Done.\n\n"
            f"  Cleaned: {cleaned}\n"
            f"  Skipped (no trail or user skip): {skipped}\n"
            f"  Errors: {errors}\n\n"
            f"See trail_cleanup_report.txt in the source folder for the per-file audit."
        )
        if self._cancel_batch:
            summary = "Cancelled.\n\n" + summary
        QMessageBox.information(self, "Apply to All Frames", summary)
        self._set_status_text(f"Batch done: {cleaned} cleaned, {skipped} skipped, {errors} errors.")
        self._log_siril(
            f"Apply-to-all complete: cleaned={cleaned} skipped={skipped} errors={errors}"
        )

        # Files have been rewritten -- invalidate the MRT cache so a
        # subsequent Detect re-reads the cleaned content from disk.
        if cleaned > 0:
            self._clear_mrt_cache()

        # Refresh current view (current file may have been replaced)
        self._load_and_show(self.current_index, autodetect=False)

    def _cancel_batch_action(self) -> None:
        self._cancel_batch = True

    # ---- Audit / Logging ----

    def _append_audit_line(self, outcome: ApplyOutcome) -> None:
        report_path = os.path.join(self.folder, "trail_cleanup_report.txt")
        json_path = os.path.join(self.folder, "trail_cleanup_report.json")
        new_file = not os.path.exists(report_path)
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # ---- Human-readable TSV (unchanged format, backwards compatible) ----
        try:
            with open(report_path, "a", encoding="utf-8") as f:
                if new_file:
                    f.write("# Svenesis Satellite Trail Cleaner -- per-file audit\n")
                    f.write(f"# Folder: {self.folder}\n")
                    f.write("# A machine-readable JSON twin lives next to this file: "
                            "trail_cleanup_report.json\n")
                    f.write("# timestamp\tstatus\tlines\tpixels_replaced\tfile\tnote\n")
                f.write(
                    f"{ts}\t{outcome.status}\t{outcome.lines}\t"
                    f"{outcome.pixels_replaced}\t{os.path.basename(outcome.path)}\t"
                    f"{outcome.note}\n"
                )
        except OSError as exc:
            log.debug("Failed to append audit line: %s", exc)

        # ---- Structured JSON twin (v0.8.9) ----
        # Same data, parseable by other tools. Read-modify-write of the
        # whole file each call is fine — audit files have ~100s of
        # entries max, not millions. Atomic via tempfile + rename so
        # a crash mid-write doesn't corrupt the JSON.
        try:
            import json
            import tempfile

            record = {
                "timestamp": ts,
                "file": os.path.basename(outcome.path),
                "path": outcome.path,
                "status": outcome.status,
                "lines": int(outcome.lines or 0),
                "pixels_replaced": int(outcome.pixels_replaced or 0),
                "inpaint_method": self.params.inpaint_method,
                "mask_dilation": int(self.params.dilation_radius),
                "match_sky_noise": bool(self.params.match_sky_noise),
                "scan_mode": self.params.scan_mode,
                "mono_mode": getattr(self.params, "mono_mode", "mean"),
                "cleaned_path": outcome.cleaned_path,
                "note": outcome.note or "",
                "tool_version": VERSION,
            }

            existing = {"folder": self.folder, "records": []}
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        existing = json.load(jf)
                    if "records" not in existing or not isinstance(existing["records"], list):
                        existing["records"] = []
                except (OSError, ValueError) as jexc:
                    log.debug("Existing JSON audit unreadable, starting fresh: %s", jexc)
                    existing = {"folder": self.folder, "records": []}
            existing["records"].append(record)

            # Atomic write: dump to a sibling temp file, then rename.
            # Rename on the same filesystem is atomic on POSIX and
            # essentially atomic on macOS HFS+/APFS — protects against
            # partial writes if the app is killed mid-flush.
            dir_ = os.path.dirname(json_path) or "."
            fd, tmp_path = tempfile.mkstemp(
                prefix=".trail_cleanup_report.", suffix=".json.tmp", dir=dir_,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as jf:
                    json.dump(existing, jf, indent=2, ensure_ascii=False)
                os.replace(tmp_path, json_path)
            except Exception:
                # Clean up the temp file on any error
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except (OSError, ValueError, TypeError) as exc:
            log.debug("Failed to write JSON audit record: %s", exc)

    def _log_siril(self, msg: str) -> None:
        try:
            self.siril.log(f"[SatelliteTrailCleaner] {msg}")
        except (SirilError, OSError, RuntimeError):
            pass

    # ---- Help / About ----

    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"

        dlg = QDialog(self)
        dlg.setWindowTitle("☕ Support Svenesis Satellite Trail Cleaner")
        dlg.setMinimumSize(520, 480)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}"
            "QPushButton{font-weight:bold;padding:8px;border-radius:6px}"
        )
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header_msg = QLabel(
            "<div style='text-align:center; font-size:12pt; line-height:1.6;'>"
            "<span style='font-size:48pt;'>☕</span><br>"
            "<span style='font-size:18pt; font-weight:bold; color:#FFDD00;'>"
            "Buy me a Coffee</span><br><br>"
            "<b style='color:#e0e0e0;'>Enjoying the Svenesis Satellite Trail Cleaner?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If this tool has saved a session from a satellite streak, helped you "
            "rescue short sequences, or simply made your processing workflow better "
            "— consider buying me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>☕ Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br><br>"
            "<span style='color:#aaaaaa;'>Your support helps maintain:</span><br>"
            "• Svenesis Blink Comparator • Svenesis Satellite Trail Cleaner<br>"
            "• Svenesis Gradient Analyzer • Svenesis CosmicDepth 3D<br>"
            "• Svenesis GalacticView 3D • Svenesis Annotate Image<br>"
            "</div>"
        )
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)

        layout.addSpacing(8)

        btn_open = QPushButton("☕  Buy me a Coffee  ☕")
        btn_open.setStyleSheet(
            "QPushButton{"
            "  background-color:#FFDD00; color:#000000;"
            "  font-size:14pt; font-weight:bold;"
            "  padding:12px 24px; border-radius:8px;"
            "  border:2px solid #ccb100;"
            "}"
            "QPushButton:hover{"
            "  background-color:#ffe740; border-color:#ddcc00;"
            "}"
        )
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BMC_URL)))
        layout.addWidget(btn_open)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton{background-color:#444; color:#ddd; border:1px solid #666;}"
            "QPushButton:hover{background-color:#555;}"
        )
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()

    def _maybe_show_workflow_dialog(self) -> None:
        """One-time-per-user (toggleable) walkthrough dialog that shows
        the recommended 5-step workflow as soon as the app screen is
        ready. The 'Don't show this again' checkbox is mirrored to
        QSettings, so power users can silence the dialog once they've
        memorised the flow. They can still open the full Help dialog
        from the left panel any time."""
        if not hasattr(self, "_settings") or self._settings is None:
            return
        suppressed = str(
            self._settings.value("workflow_dialog_suppressed", "false")
        ).lower() == "true"
        if suppressed:
            return
        self._show_workflow_dialog()

    def _show_workflow_dialog(self) -> None:
        """Modal walkthrough — explains the recommended 5-step flow
        without burying it in the full Help tabs."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Quick Workflow — Recommended Steps")
        dlg.setMinimumSize(820, 640)
        dlg.setStyleSheet(DARK_STYLESHEET)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # Headline
        head = QLabel(
            "<span style='font-size:18pt; color:#88aaff;'>"
            "<b>How to clean a folder of subs &mdash; 5 steps</b></span>"
        )
        head.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(head)

        sub = QLabel(
            "<span style='font-size:11pt; color:#aab;'>Tune detection and "
            "inpainting on <b>one good test frame</b>, then apply the same "
            "settings to the whole folder.</span>"
        )
        sub.setTextFormat(Qt.TextFormat.RichText)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Body — scrollable so it works on small displays too
        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setStyleSheet(
            "font-size: 13pt; color: #e0e0e0; background: #1e1e1e;"
            " font-family: 'Helvetica Neue', Helvetica, Arial; padding: 14px;"
            " border: 1px solid #3a3a3a; border-radius: 6px;"
        )
        body.setHtml(
            "<div style='line-height:1.55;'>"
            # Step 1
            "<div style='background:#1f2630; padding:10px; border-radius:6px;"
            " border-left:4px solid #88aaff; margin-bottom:10px;'>"
            "<b style='color:#88aaff; font-size:14pt;'>1 &nbsp; Find a frame with a visible trail</b>"
            "<br>Use the slider or the <code>&lt;</code>/<code>&gt;</code> buttons at "
            "the bottom of the canvas to step through your subs. Switch the "
            "<b>View</b> dropdown to <i>Stretched</i> so faint trails become "
            "visible. Pick the frame where the satellite trail is the "
            "clearest — that's your tuning reference."
            "</div>"
            # Step 2
            "<div style='background:#1f2630; padding:10px; border-radius:6px;"
            " border-left:4px solid #88aaff; margin-bottom:10px;'>"
            "<b style='color:#88aaff; font-size:14pt;'>2 &nbsp; Click \U0001f6f0 Detect Trails on Current</b>"
            "<br>STScI's Median Radon Transform analyses the frame. Detected "
            "trails are drawn as <span style='color:#88ff88;'>green</span> "
            "overlays (marked for removal) or <span style='color:#aaa;'>grey</span> "
            "(kept). <b>Click any line</b> in the canvas to toggle its state. "
            "If false positives appear, tighten <i>SNR threshold</i> / "
            "<i>Min length</i> / <i>Max width</i> in the left panel and re-run."
            "</div>"
            # Step 3
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border-left:4px solid #ffcc66; margin-bottom:10px;'>"
            "<b style='color:#ffcc66; font-size:14pt;'>3 &nbsp; \U0001f4a1 Follow the recommendation</b>"
            "<br>Right under the <b>Method</b> dropdown a banner appears with "
            "the inpaint method that fits <i>your specific frame</i> best. "
            "The recommendation is based on three measurements the tool just "
            "took on your data: cross-trail sky gradient, pearl/peak pattern, "
            "and mask compactness."
            "<br><br>"
            "Click the banner's <b>Apply</b> button to switch the method "
            "automatically. If you want to override, just pick another method "
            "from the dropdown — the banner stays visible so you can see how "
            "your manual choice compares to the recommendation."
            "</div>"
            # Step 4
            "<div style='background:#1f2630; padding:10px; border-radius:6px;"
            " border-left:4px solid #88aaff; margin-bottom:10px;'>"
            "<b style='color:#88aaff; font-size:14pt;'>4 &nbsp; Verify in Cleaned Preview</b>"
            "<br>Switch <b>View</b> to <i>Cleaned Preview</i>. You now see "
            "the actual result of the chosen inpaint method on this frame. "
            "Toggle <i>Mask Overlay</i> to see which pixels will be replaced "
            "(red). If the result still shows residual artefacts:"
            "<ul style='margin-top:4px;'>"
            "<li>Increase <b>Mask dilation</b> (covers wider PSF halos around "
            "bright pearls)</li>"
            "<li>Try a different <b>Method</b> from the dropdown</li>"
            "<li>Tweak <b>Strip width</b> if you're using Perpendicular Strip "
            "Median</li>"
            "<li>Toggle <b>Match sky noise</b> on / off to compare</li>"
            "</ul>"
            "The preview re-renders live with every change — no need to "
            "re-detect."
            "</div>"
            # Step 5
            "<div style='background:#1a2a1a; padding:10px; border-radius:6px;"
            " border-left:4px solid #88ff88; margin-bottom:10px;'>"
            "<b style='color:#88ff88; font-size:14pt;'>5 &nbsp; ▶ Apply to All Frames</b>"
            "<br>When the test frame looks clean, click <b>Apply to All "
            "Frames</b>. The current settings are <b>frozen</b> and applied "
            "to every sub in the folder:"
            "<ul style='margin-top:4px;'>"
            "<li>Each frame is re-detected with the same parameters</li>"
            "<li>Frames with no trail are <b>skipped</b> (file untouched)</li>"
            "<li>Frames with a trail: original moved to "
            "<code>originals/</code>, cleaned version written under the "
            "original filename — same format (FITS / XISF / TIFF) and same "
            "header / WCS / dtype</li>"
            "</ul>"
            "Optional: enable <b>Confirm each frame before writing</b> if you "
            "want to review every detection during the batch. Cancel during "
            "the run is always safe — already-cleaned frames stay cleaned, "
            "no half-written outputs."
            "</div>"
            # Summary block
            "<div style='background:#252525; padding:10px; border-radius:6px;"
            " margin-top:8px;'>"
            "<b style='color:#ffcc66;'>\U0001f4dd What you get after the batch</b>"
            "<br>The tool writes <code>trail_cleanup_report.txt</code> in the "
            "source folder. It contains one line per frame — cleaned vs "
            "skipped vs error, line count, pixels replaced, inpaint method, "
            "mask-dilation setting, timestamp. Open it any time to audit "
            "what the batch did. The <code>originals/</code> subfolder is "
            "your safety net: every modified file is recoverable bit-exact."
            "</div>"
            "</div>"
        )
        layout.addWidget(body, stretch=1)

        # Footer: don't-show-again + close
        footer = QHBoxLayout()
        cb_silence = QCheckBox("Don't show this dialog again")
        cb_silence.setToolTip(
            "You can always re-open the full guide via the Help button on "
            "the left panel."
        )
        footer.addWidget(cb_silence)
        footer.addStretch(1)
        btn_open_help = QPushButton("Open full Help")
        btn_open_help.setToolTip("Open the multi-tab help (Detection, Output, Tips, Science Notes).")
        btn_close = QPushButton("Got it — let's start")
        btn_close.setDefault(True)
        btn_close.setObjectName("DetectButton")
        footer.addWidget(btn_open_help)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        def _on_close():
            if cb_silence.isChecked():
                try:
                    self._settings.setValue(
                        "workflow_dialog_suppressed", "true",
                    )
                except Exception:
                    pass
            dlg.accept()

        def _on_open_help():
            _on_close()
            QTimer.singleShot(0, self._show_help_dialog)

        btn_close.clicked.connect(_on_close)
        btn_open_help.clicked.connect(_on_open_help)
        dlg.exec()

    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Satellite Trail Cleaner — Help")
        dlg.setMinimumSize(900, 680)
        layout = QVBoxLayout(dlg)

        base_style = (
            "font-size: 13pt; color: #e0e0e0; background: #1e1e1e;"
            " font-family: 'Helvetica Neue', Helvetica, Arial; padding: 12px;"
        )

        tabs = QTabWidget()

        # ---- Tab 1: Getting Started ----
        te1 = QTextEdit()
        te1.setReadOnly(True)
        te1.setStyleSheet(base_style)
        te1.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f680 Getting Started</b><br><br>"
            "<b style='color:#ffcc66;'>What does this tool do?</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Detects linear satellite or aircraft trails in your individual "
            "sub-exposures and inpaints (paints over) the pixels along the "
            "trail using the local sky background. Runs <b>before stacking</b>, "
            "on every FITS, XISF, TIFF or RAW frame in a folder.<br><br>"
            "Siril's normal answer to trails is sigma-clipping during stacking, "
            "which works well for 8+ subs but leaves visible streaks in short "
            "sequences. This tool fills that gap."
            "</div><br>"
            "<b style='color:#ffcc66;'>Quick Start — 5 Steps</b><br>"
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border:1px solid #3a5a7a;'>"
            "<b>1.</b> Run <b>Satellite Trail Cleaner</b> from Processing → "
            "Scripts and pick the folder of subs you want to clean.<br>"
            "<b>2.</b> Navigate to a frame that has a visible trail and "
            "click <b>Detect Trails on Current</b>. Detected lines are "
            "drawn as <span style='color:#88ff88;'><b>green</b></span> "
            "(marked for removal) or "
            "<span style='color:#aaaaaa;'>grey</span> (kept) overlays.<br>"
            "<b>3.</b> Click any line in the preview to toggle its state. "
            "Use <b>Select None</b> + click only the satellite if many "
            "candidates were found (e.g. extra false positives). Switch "
            "the View dropdown to <b>Cleaned Preview</b> to see the "
            "result of the current selection.<br>"
            "<b>4.</b> Tune the <b>Scan mode</b> (Quick / Normal / Deep) "
            "or other sliders if needed and re-run Detect.<br>"
            "<b>5.</b> Click <b>Apply to All Frames</b>. Each cleaned "
            "frame's original is moved to <code>originals/</code>; the "
            "cleaned image takes its place under the same filename."
            "</div><br>"
            "<b style='color:#ffcc66;'>What gets written</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "• <b>originals/</b> — subfolder created next to your subs; "
            "every cleaned frame's source file lands here.<br>"
            "• <b>&lt;name&gt;.fit</b> — cleaned FITS with the original "
            "filename and FITS header preserved (WCS, DATE-OBS, BSCALE/BZERO).<br>"
            "• <b>trail_cleanup_report.txt</b> — tab-separated audit "
            "per file (status, line count, pixels replaced).<br>"
            "</div><br>"
            "<b style='color:#ffcc66;'>RAW input note</b><br>"
            "<div style='background:#2a2a1a; padding:8px; border-radius:4px;"
            " border:1px solid #6a6a3a;'>"
            "RAW files (CR2 / NEF / ARW / DNG, etc.) are debayered by Siril "
            "before detection. The cleaned output is always a FITS "
            "(<code>&lt;name&gt;.fit</code>), and the RAW is moved to "
            "<code>originals/</code>. Your stacking pipeline must consume the "
            "new <code>.fit</code> files instead of the original RAWs for those "
            "frames."
            "</div>"
        )
        tabs.addTab(te1, "\U0001f680 Getting Started")

        # ---- Tab 2: Detection Controls ----
        te2 = QTextEdit()
        te2.setReadOnly(True)
        te2.setStyleSheet(base_style)
        te2.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f50d Detection Controls</b><br><br>"
            "<b style='color:#aaaaaa; font-size:10pt;'>"
            "Detection backend: STScI <code>acstools.findsat_mrt.TrailFinder</code> "
            "— Median Radon Transform pipeline (Stark et al. 2022, ACS ISR 2022-8)."
            "</b><br><br>"
            "<b style='color:#ffcc66;'>Scan mode</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>Quick</b> — 4× downsample, 1° angle resolution, no persistence "
            "check. ~15× faster than Deep. Use for first-pass sighting of "
            "obvious trails or when going through many frames.<br><br>"
            "<b>Normal</b> — 2× downsample, 0.5° resolution, persistence "
            "check on. Recommended default for typical amateur sub-frames.<br><br>"
            "<b>Deep</b> — full resolution, 0.5° resolution, all filters "
            "on. Slowest but most sensitive — use when a faint trail wasn't "
            "found in Normal mode."
            "</div><br>"
            "<b style='color:#ffcc66;'>SNR threshold</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Minimum signal-to-noise ratio on the Median Radon Transform "
            "map for a candidate to be considered. STScI default 5.0 is "
            "robust on HST data; lower to 3-4 to catch fainter trails at the "
            "cost of more false positives (which you can deselect via the "
            "interactive line picker)."
            "</div><br>"
            "<b style='color:#ffcc66;'>Min length (pixels)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Minimum trail length in image pixels. Default 50 catches most "
            "satellite trails. The Quick / Normal modes auto-scale this with "
            "the downsample factor so the effective physical length stays "
            "constant."
            "</div><br>"
            "<b style='color:#ffcc66;'>Max width (pixels) — comet/nebula killer</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "After a candidate is found, TrailFinder rotates a strip around "
            "it, fits a Gaussian across the trail width, and rejects "
            "candidates whose fitted width exceeds this value. Real satellite "
            "trails are 3-10 px wide (PSF-convolved). A comet tail is "
            "typically 30-100 px wide. Setting <b>Max width = 20</b> reliably "
            "rejects comets while keeping all real trails."
            "</div><br>"
            "<b style='color:#ffcc66;'>Persistence check — the second comet killer</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Each candidate trail is sliced into chunks along its length. "
            "Real satellites have <b>uniform</b> brightness end-to-end → most "
            "chunks pass an SNR test. A comet has a bright head and a fading "
            "tail → chunks toward the tail fail. The candidate is rejected "
            "if fewer than <b>Min persistence</b> (default 0.5 = majority) "
            "of chunks individually show SNR ≥ 3.<br><br>"
            "<b>Chunk size</b> controls the segment length. Default 100 px. "
            "Smaller chunks are stricter; larger chunks tolerate more "
            "variability."
            "</div><br>"
            "<b style='color:#ffcc66;'>Processes</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Number of worker processes for the MRT computation (TrailFinder "
            "parallelises over angles). Match to your CPU core count "
            "(usually 4-8)."
            "</div><br>"
            "<b style='color:#ffcc66;'>Mask dilation</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Half-width (px) of the inpaint mask drawn around each accepted "
            "line. Should comfortably exceed the visual width of the trail. "
            "Default 7 px (so the mask is ~14 px wide)."
            "</div><br>"
            "<b style='color:#ffcc66;'>Star Protection (inpaint-only)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>OFF by default in v0.6+.</b> When enabled, detects bright "
            "peaks in the image and excludes them from the inpaint mask "
            "(so they survive the cleanup). Star detections that lie on "
            "the trail core itself are now ignored — otherwise a bright "
            "trail's own local maxima would protect the trail from being "
            "cleaned and you'd see the trail still in the output. "
            "Enable manually only when you have a known star in the trail's "
            "dilation halo that you want to preserve.<br><br>"
            "<b>Sigma</b> — detection threshold above background "
            "(median + N · sigma). Lower = catch fainter stars. Default 5.<br><br>"
            "<b>Star halo</b> — pixels of protection around each star "
            "centroid. Increase if cleaned stars look haloed or hollowed."
            "</div><br>"
            "<b style='color:#ffcc66;'>Inpainting (v0.7+)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Four algorithms, all dtype-preserving and applied only "
            "inside the mask region (the rest of the frame keeps full "
            "original precision).<br><br>"
            "<b>Nearest Neighbor + Smooth (default)</b><br>"
            "For each masked pixel, copy the value of the nearest "
            "unmasked pixel via a Euclidean distance transform, then "
            "smooth the filled region with a Gaussian whose σ scales "
            "with the local mask thickness (σ ≈ mask half-width × "
            "0.75). Pure scipy, ~500 ms on 15 MP. Good for live "
            "preview while tuning sliders.<br><br>"
            "<b>cv2 Fast Marching (very fast, C++)</b><br>"
            "Telea's Fast Marching Method via "
            "<code>cv2.inpaint(INPAINT_TELEA)</code>. Propagates pixels "
            "from the mask boundary inward, weighted by distance and "
            "local gradient. Runs on percentile-scaled uint8 (8-bit "
            "precision in the masked region only; full precision "
            "outside). ~200 ms on 15 MP — fastest option. Quality "
            "sits between NN and Biharmonic.<br><br>"
            "<b>Biharmonic (highest quality, slow)</b><br>"
            "Solves the biharmonic PDE ∇⁴u = 0 inside the mask with "
            "boundary values fixed to the surrounding sky "
            "(<code>skimage.restoration.inpaint_biharmonic</code>). "
            "Mathematically optimal smooth interpolation (minimum "
            "thin-plate energy). Slower (~5-15 s) but produces "
            "results visually indistinguishable from real sky. Best "
            "for final Apply on critical frames.<br><br>"
            "<b>Perpendicular Strip Median</b><br>"
            "Rotates the image so the trail is horizontal, then for "
            "every column in rotated space replaces the masked pixels "
            "with the median of <b>strip_width</b> unmasked pixels "
            "immediately above and below the masked stripe. "
            "Vectorised — comparable speed to NN+Smooth. Preserves "
            "any sky-background gradient perpendicular to the trail "
            "(useful when vignetting or light-pollution gradient is "
            "noticeable). <b>Fixed in v0.7</b> — previous versions "
            "only filled the centreline pixel of each line and left "
            "92% of the dilated mask untouched.<br><br>"
            "<b>Match sky noise (checkbox, recommended)</b><br>"
            "After the chosen method runs, add Gaussian noise inside "
            "the mask with σ taken robustly (via MAD) from a 30-px "
            "halo of unmasked sky around the trail. Real sky has "
            "photon shot-noise + read-noise; without this step the "
            "filled patch is statistically too smooth and can be "
            "spotted on close inspection or by stack-rejection "
            "algorithms. Adds < 50 ms overhead and is recommended on "
            "for all photometry-aware workflows."
            "</div>"
        )
        tabs.addTab(te2, "\U0001f50d Detection Controls")

        # ---- Tab 3: Algorithm & Math ----
        # QTextBrowser (a QTextEdit subclass) so links open externally.
        te_math = QTextBrowser()
        te_math.setReadOnly(True)
        te_math.setStyleSheet(base_style)
        te_math.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f9ee Algorithm &amp; Math</b><br><br>"
            "<b style='color:#aaaaaa; font-size:10pt;'>"
            "Backend: <a href='https://acstools.readthedocs.io/en/stable/findsat_mrt.html' "
            "style='color:#88aaff;'>acstools.findsat_mrt.TrailFinder</a> "
            "&nbsp;·&nbsp; "
            "Reference: Stark et al. 2022, "
            "<a href='https://www.stsci.edu/files/live/sites/www/files/home/hst/"
            "instrumentation/acs/documentation/instrument-science-reports-isrs/_documents/isr2208.pdf' "
            "style='color:#88aaff;'>ACS Instrument Science Report 2022-08</a>"
            "</b><br><br>"

            "<b style='color:#ffcc66;'>1. Standard Radon Transform (the baseline)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Given an image <i>I(x, y)</i>, the Radon transform maps every "
            "possible straight line — parametrised by perpendicular offset "
            "ρ and angle θ — to the <b>sum</b> of the pixel values along it:"
            "<br><br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 6px;'>"
            "R<sub>sum</sub>(ρ, θ) = Σ<sub>(x,y) on line</sub> I(x, y)"
            "</span><br><br>"
            "A real satellite trail produces a strong peak in "
            "R<sub>sum</sub>(ρ, θ) at exactly the (ρ, θ) of its line: "
            "every trail pixel contributes flux to one summed line, so "
            "the integral grows as N × signal where N is the trail length.<br><br>"
            "<b style='color:#ff8888;'>Problem:</b> a bright star is a "
            "delta-like spike. <b>Any</b> line that passes through it adds "
            "the star's flux to its sum. In a star-rich field this "
            "produces a fan-shaped pattern of false peaks centred on every "
            "bright source — exactly the failure mode the classical "
            "Hough/Radon approach suffers from."
            "</div><br>"

            "<b style='color:#ffcc66;'>2. Median Radon Transform (the fix)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "The MRT replaces the sum with the median:<br><br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 6px;'>"
            "R<sub>med</sub>(ρ, θ) = median{ I(x, y) : (x, y) on line }"
            "</span><br><br>"
            "<b style='color:#88ff88;'>Why this works:</b>"
            "<ul style='margin-top:4px;'>"
            "<li>A real satellite trail has roughly <b>constant flux S</b> "
            "along its entire length L. The median of those L pixels "
            "equals S → trail peak preserved.</li>"
            "<li>A bright star occupies <b>≤ 1%</b> of any line passing "
            "through it (e.g. 10 px out of a 5000-px integration line). "
            "The median treats those 10 bright pixels as <b>outliers</b> "
            "and ignores them → star contribution to R<sub>med</sub> "
            "≈ background.</li>"
            "</ul>"
            "The point-source fan suppression is therefore <b>automatic</b> "
            "— a mathematical property of the median operator, not a heuristic."
            "</div><br>"

            "<b style='color:#ffcc66;'>3. Noise model</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Per-pixel image noise σ<sub>img</sub> is estimated robustly "
            "from the median absolute deviation:<br><br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 6px;'>"
            "σ<sub>img</sub> = MAD(I) / 0.6745"
            "</span><br><br>"
            "The expected scatter of the <b>median</b> of L Gaussian-noise "
            "samples is √(π/2) ≈ 1.2533 times the scatter of the mean. "
            "So the MRT noise at a line of length L is:<br><br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 6px;'>"
            "σ<sub>mrt</sub>(L) = 1.2533 · σ<sub>img</sub> / √L"
            "</span><br><br>"
            "The signal-to-noise map is then "
            "<i>SNR</i>(ρ, θ) = R<sub>med</sub>(ρ, θ) / σ<sub>mrt</sub>(L)."
            "</div><br>"

            "<b style='color:#ffcc66;'>4. Matched-filter peak detection</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "A genuine trail of width w produces a 2-D blob in MRT space "
            "with a characteristic shape (sharp in ρ, somewhat extended "
            "in θ). findsat_mrt convolves the SNR map with three "
            "<b>precomputed kernels</b> (synthetic MRT responses of "
            "3 / 7 / 15 px wide trails) and runs "
            "<code>photutils.detection.StarFinder</code> on each "
            "convolved map. This is a 2-D matched filter in MRT space: "
            "candidate trails that fit one of the kernels survive, "
            "isolated noise peaks don't.<br><br>"
            "Detection threshold = your <b>SNR threshold</b> slider (default 5σ)."
            "</div><br>"

            "<b style='color:#ffcc66;'>5. Per-candidate image-space validation</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Each surviving (ρ, θ) candidate is verified back in the "
            "original image:<br>"
            "<b>(a) Width fit:</b> the image is rotated so the candidate "
            "is horizontal; the median across rows yields a 1-D profile "
            "across the trail; a Gaussian is fitted. Candidates with "
            "<b>FWHM &gt; max_width</b> are rejected. <b>This is the "
            "comet-tail killer #1</b> — a comet tail is ≥ 30 px wide, "
            "a real trail is 3–10 px.<br><br>"
            "<b>(b) Persistence test:</b> the trail is split into chunks "
            "of length <i>persistence_chunk</i> (default 100 px). For "
            "each chunk, a local SNR is computed. The candidate is "
            "rejected if the fraction of chunks with SNR ≥ "
            "<i>min_persistence_snr</i> (3) falls below "
            "<i>min_persistence</i> (0.5). <b>This is the comet-tail "
            "killer #2</b> — a comet has a bright head and a fading "
            "tail; chunks toward the tail fail SNR=3 → fraction "
            "&lt; 0.5 → rejected. A real satellite has constant "
            "brightness end-to-end and passes."
            "</div><br>"

            "<b style='color:#ffcc66;'>6. Inpaint algorithms</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Once a trail is detected and its mask M built, the three "
            "available inpaint methods solve different mathematical "
            "objectives.<br><br>"

            "<b>Nearest Neighbor + Smooth.</b> Let D(p) be the "
            "Euclidean distance transform of M (distance from each "
            "p ∈ M to the closest non-mask pixel q*(p)). Step 1 sets "
            "the filled value I'(p) = I(q*(p)). Step 2 smooths the "
            "filled region with a Gaussian G<sub>σ</sub> where σ ≈ "
            "max<sub>p∈M</sub> D(p) × 0.75 (adapts to mask "
            "thickness). The smoothing happens only inside M:<br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 4px;'>"
            "I'(p) = (G<sub>σ</sub> * I')(p)  for p ∈ M"
            "</span>"
            "<br><br>"

            "<b>Biharmonic.</b> Find I' minimising ∫<sub>M</sub> "
            "(Δu)² over u with u = I on ∂M. Solution satisfies "
            "∇⁴u = 0 inside M with Dirichlet boundary I|<sub>∂M</sub>. "
            "This is the thin-plate spline; minimum-curvature "
            "interpolation. Implementation: "
            "<code>skimage.restoration.inpaint_biharmonic</code> "
            "solves the discrete linear system per connected mask "
            "component.<br><br>"

            "<b>Perpendicular Strip Median.</b> Rotate the image by "
            "−θ so the trail axis is horizontal. In the rotated "
            "frame, M is a horizontal stripe at rows "
            "[y<sub>top</sub>(x), y<sub>bot</sub>(x)] per column x. "
            "For each column we sample S = "
            "{I<sub>rot</sub>(y, x) | y ∈ [y<sub>top</sub>−w, "
            "y<sub>top</sub>) ∪ (y<sub>bot</sub>, y<sub>bot</sub>+w]} "
            "and set I'<sub>rot</sub>(y, x) = median(S) for all "
            "y ∈ M in this column. Rotate back to image coordinates "
            "with bilinear interpolation.<br><br>"

            "<b>Sky-noise matching (post-process).</b> Real sky has "
            "Poisson + read noise; a smooth inpaint does not. After "
            "any of the above runs, we estimate σ<sub>sky</sub> "
            "robustly from a 30-px halo H around M:<br>"
            "<span style='font-family:monospace; color:#aaffaa; "
            "background:#1a3a1a; padding:2px 4px;'>"
            "σ<sub>sky</sub> = 1.4826 · MAD(I[H])"
            "</span><br>"
            "Then add Gaussian noise N(0, σ<sub>sky</sub>²) to each "
            "pixel of I' inside M. The filled region is now "
            "statistically indistinguishable from real sky for "
            "stack-rejection algorithms and for the human eye."
            "</div><br>"

            "<b style='color:#ffcc66;'>7. Performance scaling</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Cost of one MRT: <b>O(N<sub>θ</sub> · H · W)</b> where "
            "H, W is the image size. The expensive step is one "
            "image rotation + per-row median for each angle. "
            "<ul>"
            "<li>Downsampling by 2× → 4× faster (Normal scan mode default).</li>"
            "<li>Downsampling by 4× → 16× faster (Quick scan mode).</li>"
            "<li>Doubling θ-step from 0.5° to 1° → 2× faster.</li>"
            "<li>findsat_mrt parallelises over θ → ~linear speedup "
            "with worker process count.</li>"
            "</ul>"
            "This tool additionally caches the MRT result between "
            "Detect calls. When you change only the SNR threshold, "
            "max_width, or persistence settings (not downsample / "
            "θ-step), the MRT itself is reused and only the cheap "
            "post-MRT phases re-run — typical re-detection in &lt; 1 second."
            "</div><br>"

            "<b style='color:#ffcc66;'>References</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>Library:</b> "
            "<a href='https://acstools.readthedocs.io/en/stable/findsat_mrt.html' "
            "style='color:#88aaff;'>acstools.findsat_mrt</a> "
            "(<code>pip install acstools</code>)<br>"
            "<b>Paper:</b> Stark et al. 2022, "
            "<a href='https://www.stsci.edu/files/live/sites/www/files/home/hst/"
            "instrumentation/acs/documentation/instrument-science-reports-isrs/_documents/isr2208.pdf' "
            "style='color:#88aaff;'>"
            "<i>An Improved Algorithm for Identifying Satellite Trails "
            "in HST/ACS Images</i>, ACS ISR 2022-08</a><br>"
            "<b>Source code:</b> "
            "<a href='https://github.com/spacetelescope/acstools/blob/main/acstools/findsat_mrt.py' "
            "style='color:#88aaff;'>"
            "github.com/spacetelescope/acstools/findsat_mrt.py</a><br>"
            "<b>License:</b> findsat_mrt is BSD-3-Clause, maintained by "
            "the Space Telescope Science Institute (STScI). All credit "
            "for the algorithm and reference implementation goes to the "
            "STScI authors; this tool only wraps their library in a "
            "PyQt UI for amateur astrophotography workflows."
            "</div>"
        )
        # Allow the hyperlinks to be opened externally
        te_math.setOpenExternalLinks(True)
        tabs.addTab(te_math, "\U0001f9ee Algorithm")

        # ---- Tab 3: Output & Safety ----
        te3 = QTextEdit()
        te3.setReadOnly(True)
        te3.setStyleSheet(base_style)
        te3.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f4be Output &amp; Safety</b><br><br>"
            "<b style='color:#ffcc66;'>File-handling model</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Every cleaned frame triggers two moves:<br>"
            "• The <b>original file</b> is moved to "
            "<code>originals/&lt;name&gt;.&lt;ext&gt;</code>.<br>"
            "• The <b>cleaned image</b> is written back in the source "
            "folder using the original filename (same extension where "
            "possible — see per-format notes below).<br><br>"
            "<b>FITS inputs (.fit / .fits / .fts):</b> the FITS header is "
            "preserved verbatim, with the cleaning operation appended as "
            "HISTORY lines. WCS, DATE-OBS, BSCALE/BZERO and instrument "
            "keywords are unchanged. Output file extension is identical "
            "to the input.<br><br>"
            "<b>XISF inputs (.xisf):</b> cleaned output is written back "
            "as <code>.xisf</code> with all original FITSKeywords AND "
            "XISFProperties preserved — including PixInsight-style "
            "astrometric solutions (PCL:AstrometricSolution matrices). "
            "Cleaning operations are appended as HISTORY keywords. "
            "Output uses LZ4HC compression. (Requires the <code>xisf</code> "
            "package; falls back to FITS write if unavailable.)<br><br>"
            "<b>TIFF inputs (.tif / .tiff):</b> cleaned output is written "
            "back as <code>.tif</code> via the <code>tifffile</code> "
            "package. The original <b>dtype</b> (uint8 / uint16 / uint32 / "
            "float32) is preserved bit-exact, as are the original "
            "compression scheme (LZW / ZSTD / Deflate / none), photometric "
            "interpretation (mono vs RGB), and resolution tags. Cleaning "
            "history is appended to the <code>ImageDescription</code> tag "
            "where Siril / ASTAP / NINA typically store plate-solve and "
            "processing notes. (Requires the <code>tifffile</code> "
            "package; falls back to FITS write if unavailable.)<br><br>"
            "<b>RAW inputs (.cr2 / .nef / .arw / .dng / …):</b> debayered "
            "by Siril before cleaning. Output is always FITS "
            "(<code>&lt;name&gt;.fit</code>) with a minimal synthesised "
            "header (<code>SOURCE</code> records the original RAW "
            "filename). The original RAW is preserved in "
            "<code>originals/</code>.<br><br>"
            "Frames where <i>no</i> trail is detected are <b>not "
            "touched</b>: no move, no rewrite. Only frames with a "
            "detected trail change state on disk."
            "</div><br>"
            "<b style='color:#ffcc66;'>Reversibility</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "To undo a cleaning operation, move the original file from "
            "<code>originals/</code> back into the source folder "
            "(overwriting the cleaned file if you want to). For FITS and "
            "XISF this is a single move and you're done. For RAW inputs "
            "the cleaned <code>.fit</code> sits alongside the restored "
            "RAW — delete the <code>.fit</code> manually if not needed.<br><br>"
            "The script does not delete anything except via the move into "
            "<code>originals/</code>."
            "</div><br>"
            "<b style='color:#ffcc66;'>Audit trail</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<code>trail_cleanup_report.txt</code> is appended in the source "
            "folder. One tab-separated line per processed file: timestamp, "
            "status (cleaned / skipped_no_trail / skipped_user / error), "
            "trail count, pixels replaced, source filename, optional note. "
            "The file is created on first write and never truncated."
            "</div>"
        )
        tabs.addTab(te3, "\U0001f4be Output && Safety")

        # ---- Tab 4: Tips & Pitfalls ----
        te4 = QTextEdit()
        te4.setReadOnly(True)
        te4.setStyleSheet(base_style)
        te4.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f4a1 Tips &amp; Pitfalls</b><br><br>"
            "<b style='color:#ffcc66;'>When you don't need this tool</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "If you have 10+ well-distributed sub-exposures, Siril's sigma- "
            "clipped stack rejection (Winsorized / linear-fit) already removes "
            "satellite trails statistically. This tool's main value is at "
            "<b>short sequence lengths</b> (3-8 subs) where the clipping has "
            "too few samples to work reliably.<br><br>"
            "Quick sanity check: stack first <i>without</i> cleaning. If you "
            "still see a visible streak in the result, run this tool and "
            "re-stack."
            "</div><br>"
            "<b style='color:#ffcc66;'>Common pitfalls</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "• <b>Faint trail not detected</b> — switch Scan mode to "
            "<b>Deep</b> (full resolution, finest angle step). If still not "
            "found, lower SNR threshold from 5 to 3-4. The Median Radon "
            "Transform is ~10× more sensitive than classical methods but "
            "extremely faint trails (per-pixel signal &lt; 0.5σ) may still "
            "fall under the noise floor.<br>"
            "• <b>Comet / nebula picked up as a trail</b> — increase "
            "Persistence check stringency (raise Min persistence to 0.7) "
            "or lower Max width to 15-20. A real satellite has uniform "
            "brightness end-to-end and width ≤ 10 px; a comet tail fades "
            "and flares.<br>"
            "• <b>Multiple lines fan from a bright star</b> — should not "
            "happen with MRT (the median trick suppresses point-source "
            "fans). If it does, the star may be saturated to such a degree "
            "that even the median is biased. Use the line picker to "
            "deselect the false fans and keep only the real trail.<br>"
            "• <b>Trail visible after cleaning</b> — increase Mask "
            "dilation to widen the inpaint area. A trail that the eye can "
            "see is wider than just the detected pixel line.<br>"
            "• <b>RAW debayer artefacts</b> — debayering happens in "
            "Siril, which uses the user-selected debayer in Preferences. "
            "Verify your debayer choice (RCD / VNG / AHD) before "
            "batch-cleaning a session of RAWs.<br>"
            "• <b>Detection too slow</b> — switch to Quick scan mode "
            "(4× downsample), or raise Processes to match your CPU cores."
            "</div><br>"
            "<b style='color:#ffcc66;'>Choosing an inpaint method (v0.7+)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "• <b>Nearest Neighbor + Smooth (default)</b> — use for "
            "live preview iteration and most batch cleanups. Fast "
            "(&lt;1 s), adaptive σ scales the Gaussian with mask "
            "thickness so no visible centreline.<br>"
            "• <b>Biharmonic</b> — switch to this just before the "
            "final Apply on critical frames. Mathematically optimal "
            "smooth fill, ~5-15 s per frame. Visually indistinguishable "
            "from real sky after the noise-matching post-process.<br>"
            "• <b>Perpendicular Strip Median</b> — use when there's a "
            "noticeable sky gradient (heavy vignetting, light pollution "
            "gradient) perpendicular to the trail. Preserves that "
            "gradient because the median is taken from pixels just "
            "above and below the trail at each column in rotated "
            "space. Comparable speed to NN.<br><br>"
            "<b>Always keep 'Match sky noise' on</b> unless you have "
            "a specific reason to want a perfectly smooth fill. The "
            "noise-matched fill is statistically invisible to "
            "stack-rejection algorithms; the smooth fill is not.<br><br>"
            "<b>Mask dilation</b> tradeoff: wider dilation (e.g. 10 "
            "instead of 7) better covers faint trail wings but the "
            "inpainted region grows quadratically. Stick with 7 for "
            "typical PSF-convolved trails."
            "</div><br>"
            "<b style='color:#ffcc66;'>Photometry</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "For photometric work, inpainted pixels are <b>synthetic data</b>. "
            "Sky-noise matching makes the patch statistically realistic for "
            "stack-rejection but the underlying signal is still interpolated, "
            "not measured. If you are doing photometry, prefer to <b>reject</b> "
            "any frame whose trail crosses your science target rather than "
            "clean it; use this tool for the remaining frames where the trail "
            "passes through empty sky."
            "</div>"
        )
        tabs.addTab(te4, "\U0001f4a1 Tips && Pitfalls")

        # ---- Tab: Scientific Positioning ----
        te_sci = QTextEdit()
        te_sci.setReadOnly(True)
        te_sci.setStyleSheet(base_style)
        te_sci.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f52c Why we inpaint &mdash; and what STScI does instead"
            "</b><br><br>"
            "<b style='color:#ffcc66;'>The honest scientific positioning"
            "</b><br>"
            "<div style='background:#252525; padding:8px; "
            "border-radius:4px;'>"
            "The detection backend in this tool is "
            "<b>STScI's <code>findsat_mrt.TrailFinder</code></b> &mdash; "
            "the same Median Radon Transform algorithm published in "
            "Stark, Avila, Anderson et&nbsp;al. (ACS&nbsp;ISR&nbsp;2022-08) "
            "and used to find satellite trails in HST/ACS images.<br><br>"
            "Importantly, the original paper does <b>NOT</b> recommend "
            "any specific inpainting algorithm. It treats the output "
            "mask as a Data Quality flag for the downstream HST pipeline "
            "(<code>AstroDrizzle</code>), which combines multiple "
            "exposures and simply <b>rejects</b> the masked pixels &mdash; "
            "the sky information for the trail region comes from the "
            "<i>other</i> exposures in the stack, not from spatial "
            "interpolation. That is the cleanest possible approach: "
            "every output pixel is a real measurement from some sub, "
            "never an estimate."
            "</div><br>"
            "<b style='color:#ffcc66;'>Why we deviate &mdash; the amateur "
            "regime</b><br>"
            "<div style='background:#1a2a3a; padding:10px; "
            "border-radius:6px; border:1px solid #3a5a7a;'>"
            "STScI's mask-and-reject approach requires <b>enough "
            "exposures</b> for the rejection to leave a clean sky in the "
            "trail region. HST programmes typically have 8&ndash;16+ "
            "well-dithered sub-exposures &mdash; the trail in a single "
            "sub is, statistically, an outlier the σ-clip rejects "
            "cleanly.<br><br>"
            "Amateur astrophotography usually has 4&ndash;6 subs (often "
            "fewer on rare targets). At <i>n=5</i>, σ-clipping a single "
            "outlier doesn't have enough surviving population to leave "
            "a confident sky estimate; below <i>n=4</i> it is "
            "statistically not possible. The trail residual survives "
            "the stack and degrades the final image.<br><br>"
            "<b>That gap is what this tool fills.</b> Spatial inpainting "
            "per-frame, <i>before</i> stacking, lets the σ-clip in "
            "Siril's stacker work on already-clean inputs."
            "</div><br>"
            "<b style='color:#ffcc66;'>How we stay HST-faithful in "
            "spirit</b><br>"
            "<div style='background:#252525; padding:8px; "
            "border-radius:4px;'>"
            "Even though spatial inpainting introduces "
            "<i>synthetic data</i>, the HST tradition of <b>not "
            "hallucinating structure</b> guides our defaults:"
            "<ul style='margin-top:6px;'>"
            "<li>The default method, <b>Perpendicular Strip Median</b>, "
            "copies the median of the local sky perpendicular to the "
            "trail &mdash; no model, no learned prior, no invented "
            "stars. The strongest possible &laquo;don't invent "
            "structure&raquo; constraint short of leaving the mask "
            "untouched.</li>"
            "<li><b>Match-sky-noise</b> adds Gaussian noise with σ "
            "matching the local sky. The inpainted region is "
            "<i>statistically</i> a sky sample, so stack-rejection "
            "downstream cannot tell it apart from a real sky pixel.</li>"
            "<li><b>Star Protection</b> excludes detected stars from "
            "the mask so we never replace a real star with sky.</li>"
            "<li>We <b>refuse to ship deep-learning inpainting</b> "
            "(LaMa, Stable Diffusion, etc.) because those models "
            "halluzinate stars, galaxies and Bahtinov-spike-like "
            "structure that is not in the original data. That is "
            "<i>fabrication</i>, not interpolation, and incompatible "
            "with the scientific posture of the underlying STScI "
            "algorithm.</li>"
            "</ul>"
            "</div><br>"
            "<b style='color:#ffcc66;'>If you have enough subs &mdash; "
            "consider skipping this tool</b><br>"
            "<div style='background:#2a1a1a; padding:10px; "
            "border-radius:6px; border:1px solid #7a3a3a;'>"
            "If your stack has <b>8 or more well-dithered subs</b> and "
            "the trail does not repeat across multiple of them, "
            "Siril's built-in σ-clip / Winsorized / Linear-Fit "
            "rejection during <code>Stacking → Image stacking</code> "
            "is mathematically the correct choice. It uses real "
            "measurements, not estimates. This tool is most useful "
            "for the regime where σ-clip cannot reach a clean result: "
            "few subs, repeating trails, or trails crossing science "
            "targets where you want to preserve the frame."
            "</div><br>"
            "<b style='color:#888;'>Reference: Stark et&nbsp;al. 2022, "
            "&laquo;findsat_mrt: A New Algorithm for Detecting Linear "
            "Features in Astronomical Images&raquo;, "
            "ACS&nbsp;ISR&nbsp;2022-08, STScI.</b>"
        )
        tabs.addTab(te_sci, "\U0001f52c Science Notes")

        layout.addWidget(tabs)

        btns = QHBoxLayout()
        # Re-open the guided 5-step Quick Workflow dialog directly from
        # the Help dialog. Useful if the user dismissed it earlier and
        # forgot the recommended flow — no need to go hunting in
        # QSettings for the suppress flag.
        btn_workflow = QPushButton("Show Quick Workflow")
        btn_workflow.setToolTip(
            "Re-open the 5-step guided walkthrough that appeared "
            "the first time you launched the tool."
        )
        def _open_workflow():
            dlg.accept()
            QTimer.singleShot(0, self._show_workflow_dialog)
        btn_workflow.clicked.connect(_open_workflow)
        btns.addWidget(btn_workflow)

        # Reset every 'Don't show this again' flag in QSettings — the
        # workflow dialog and the Biharmonic warning will reappear on
        # their normal triggers (next start, next biharmonic selection).
        btn_reset_dialogs = QPushButton("Reset dismissed dialogs")
        btn_reset_dialogs.setToolTip(
            "Re-enable all 'don't show again' dialogs so they reappear "
            "the next time their trigger fires."
        )
        def _reset_dismissed():
            try:
                self._settings.setValue("workflow_dialog_suppressed", "false")
                self._settings.setValue("biharmonic_warning_suppressed", "false")
            except Exception:
                pass
            QMessageBox.information(
                dlg, "Reset complete",
                "All dismissed dialogs have been re-enabled.\n\n"
                "• The Quick Workflow will reappear on the next launch.\n"
                "• The Biharmonic warning will reappear the next time "
                "you select that method.",
            )
        btn_reset_dialogs.clicked.connect(_reset_dismissed)
        btns.addWidget(btn_reset_dialogs)

        btns.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

        dlg.exec()


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------

def _collect_supported_files(folder: str) -> list[str]:
    out: list[str] = []
    for entry in sorted(os.listdir(folder)):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full):
            continue
        if is_supported_file(full):
            out.append(full)
    return out


def _show_welcome_dialog(parent=None) -> bool:
    """Intro dialog explaining the workflow. Returns True if user wants to continue."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Satellite Trail Cleaner v{VERSION}")
    dlg.setMinimumWidth(680)
    dlg.setStyleSheet(
        "QDialog{background-color:#1e1e1e;color:#e0e0e0;}"
        "QLabel{color:#e0e0e0;font-size:12pt;}"
        "QPushButton{padding:10px 24px;font-weight:bold;font-size:11pt;border-radius:4px;}"
    )
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

    title = QLabel(
        "<div style='text-align:center;'>"
        "<span style='font-size:28pt;'>\U0001f6f0</span><br>"
        "<span style='font-size:20pt;font-weight:bold;color:#88aaff;'>"
        "Welcome to Satellite Trail Cleaner</span>"
        "</div>"
    )
    title.setTextFormat(Qt.TextFormat.RichText)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    body = QLabel(
        "<div style='font-size:12pt;line-height:1.55;'>"
        "This tool detects linear satellite or aircraft trails in your "
        "individual sub-exposures and inpaints the trail pixels using the "
        "local sky background — <b>before stacking</b>."
        "<br><br>"
        "<b style='color:#FFDD00;'>What happens next:</b>"
        "<ol style='margin-top:4px;'>"
        "<li>Pick a folder containing your FITS files "
        "(<code>.fit</code> / <code>.fits</code> / <code>.fts</code>), "
        "PixInsight XISF (<code>.xisf</code>), "
        "TIFF (<code>.tif</code> / <code>.tiff</code>) or "
        "DSLR/mirrorless RAWs (<code>.cr2</code>, <code>.nef</code>, "
        "<code>.arw</code>, <code>.dng</code>, …).</li>"
        "<li>The viewer opens — navigate to a frame with a visible "
        "trail and click <b>Detect Trails on Current</b>. Detected lines "
        "appear as <span style='color:#88ff88;'><b>green</b></span> "
        "(marked for removal) or "
        "<span style='color:#aaaaaa;'>grey</span> (kept) overlays.</li>"
        "<li>Click any line to toggle its state. Switch the View "
        "dropdown to <b>Cleaned Preview</b> to see the inpainting "
        "result of your current selection. Apply to the current frame "
        "or to all frames in the folder.</li>"
        "<li>Each cleaned frame's original is moved to "
        "<code>originals/</code>; the cleaned image takes the original "
        "filename, so your existing stacking pipeline picks it up "
        "unchanged. A per-folder "
        "<code>trail_cleanup_report.txt</code> records what was done.</li>"
        "</ol>"
        "<b style='color:#FFDD00;'>Your original files are never "
        "modified</b> — they are moved into <code>originals/</code> "
        "(reversible by moving them back). Frames with no detected trail "
        "are not touched at all."
        "<br><br>"
        "<i style='color:#BBBBBB;font-size:10pt;'>Note on RAW files: "
        "trail removal cannot operate on raw CFA data without corrupting "
        "the Bayer pattern, so RAWs are debayered by Siril and the "
        "cleaned output is written as <code>.fit</code>. The original "
        "RAW is preserved in <code>originals/</code>."
        "<br><br>"
        "Note on XISF files: cleaned output stays as <code>.xisf</code> "
        "with all original FITS keywords AND XISF properties preserved "
        "(astrometric solutions, filter, exposure, instrument metadata). "
        "Cleaning operations are appended as HISTORY entries. Your "
        "PixInsight / Siril stacking pipeline can keep using the same "
        "filenames as before.</i>"
        "<br><br>"
        "<i style='color:#BBBBBB;font-size:10pt;'>When you don't need "
        "this tool: with 10+ well-distributed subs, Siril's sigma-clipped "
        "stacking already removes trails statistically. The cleaner's "
        "main value is at short sequence lengths (3–8 subs).</i>"
        "</div>"
    )
    body.setTextFormat(Qt.TextFormat.RichText)
    body.setWordWrap(True)
    layout.addWidget(body)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_cancel = QPushButton("Cancel")
    btn_cancel.clicked.connect(dlg.reject)
    btn_row.addWidget(btn_cancel)
    btn_start = QPushButton("Select Folder →")
    btn_start.setStyleSheet(
        "padding:8px 20px;font-weight:bold;border-radius:4px;"
        "background-color:#285299;color:white;"
    )
    btn_start.setDefault(True)
    btn_start.clicked.connect(dlg.accept)
    btn_row.addWidget(btn_start)
    layout.addLayout(btn_row)

    return dlg.exec() == QDialog.DialogCode.Accepted


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    siril = s.SirilInterface()
    try:
        siril.connect()
    except (SirilConnectionError, SirilError, OSError) as exc:
        print(f"Could not connect to Siril: {exc}", file=sys.stderr)
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)

    # Welcome / intro dialog -> Cancel aborts before any folder picker shows.
    if not _show_welcome_dialog(None):
        return 0

    # Folder picker
    folder = QFileDialog.getExistingDirectory(
        None,
        "Svenesis Satellite Trail Cleaner -- Select Folder of Sub-Exposures",
        "",
    )
    if not folder:
        return 0

    paths = _collect_supported_files(folder)
    if not paths:
        QMessageBox.warning(
            None,
            "Svenesis Satellite Trail Cleaner",
            f"No FITS, XISF, TIFF or RAW files found in:\n{folder}\n\n"
            f"Supported extensions:\n  FITS: {', '.join(FITS_EXTENSIONS)}\n"
            f"  XISF: {', '.join(XISF_EXTENSIONS)}\n"
            f"  TIFF: {', '.join(TIFF_EXTENSIONS)}\n"
            f"  RAW: {', '.join(RAW_EXTENSIONS)}",
        )
        return 0

    try:
        siril.log(f"[SatelliteTrailCleaner] Loaded {len(paths)} file(s) from {folder}")
    except (SirilError, OSError, RuntimeError):
        pass

    win = SatelliteTrailCleanerWindow(siril, folder, paths)
    # showMaximized() rather than show() — the preview canvas benefits
    # massively from extra screen real estate (Mask Overlay / Cleaned
    # Preview are essentially side-by-side comparisons in the user's
    # head, and a 1500×880 default barely fits a single 4k-resolution
    # sub at 50 %). On macOS this triggers the green-button maximize
    # equivalent, on Linux/Windows it fills the available screen
    # excluding the taskbar.
    win.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
