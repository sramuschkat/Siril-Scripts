"""
Svenesis Blink Comparator
Script Version: 1.2.8
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script prompts for a folder of FITS files, builds a temporary Siril
sequence from them (optionally registering), and plays it back as a blink
animation for rapid visual inspection. It helps identify:
- Satellite trails and airplane tracks
- Passing clouds or haze
- Bad frames (tracking errors, wind gusts)
- Comet, asteroid, or planet motion
- Focus drift over the session
- Artifacts and hot-pixel patterns

Features:
- Animated playback with configurable speed (1-30 FPS)
- Frame navigation (first/prev/next/last) and color-coded slider
- Keyboard shortcuts (Space, arrows, Home/End, G/B, 1-9, Ctrl+Z)
- Display modes: Normal, Only-included, Side-by-Side (vs. reference)
- Globally-linked autostretch (shared median/MAD across all frames)
- Frame marking: include/exclude with pending changes and batch apply
- Auto-advance after marking for rapid frame selection
- Batch reject by threshold (FWHM, Background, Roundness) or worst N%
- Sortable statistics table (all frames with FWHM, BG, roundness, stars)
- Statistics graph (FWHM, Background, Roundness over time)
- Thumbnail filmstrip with lazy loading and color-coded borders
- Undo for frame markings (Ctrl+Z)
- Export rejected frame list as text file
- Session summary on close (frames viewed, rejected, FWHM improvement)
- LRU frame cache with background preloading for smooth playback
- Autostretch (Midtone Transfer Function) with global parameters
- Zoom (scroll wheel) and pan (right-click drag)
- Per-frame info display (FWHM, background, noise, exposure, date)
- Dark themed PyQt6 GUI matching the Gradient Analyzer look and feel

Run from Siril via Processing -> Scripts. Place BlinkComparator.py inside a folder
named Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG (condensed; last officially published release was v1.2.3):

1.2.8 - Cross-platform polish, stability, and performance pass 3
      - UTF-8 encoding for rejected_frames.txt and CSV export (fixes Windows non-ASCII paths).
      - 1-9 FPS presets moved to keyPressEvent so focused spinboxes accept digits natively.
      - Folder paths with spaces are now quoted in cd/register/load_seq commands.
      - _apply_changes moves files first, then writes an audit list of only what actually moved.
      - Star-detection rebinds caches/stats and advances the progress bar through post-register phases.
      - Persists view-state (filter, display mode, graph metrics, scatter axes) across sessions.
      - Numerous scatter / graph / filmstrip / table hardening and optimizations.

1.2.7 - Marking responsiveness
      - Coalesced post-mark refresh (slider / scatter / graph) via a single 150 ms timer.
      - Filmstrip and table skip no-op stylesheet / highlight work.
      - Bug fix: mtf() out= kwarg crash introduced in 1.2.6.
      - Bug fix: stale temp sequence from a crashed run no longer blocks the next launch.

1.2.6 - Performance pass (playback, scrolling, statistics)
      - ThumbnailCache reuses FrameCache's stretched image (no re-load for thumbnails).
      - In-place mtf() + single-pass RGB autostretch.
      - FPS-aware preload pacing.
      - Diff-based filmstrip thumbnail loading on scroll.

1.2.5 - Simplified display modes
      - Removed: Difference mode + D shortcut (playing at 3-5 FPS catches the same artifacts).
      - Removed: Linked-stretch toggle - globally-linked autostretch is now the only mode.

1.2.4 - Folder-only workflow
      - The script always prompts for a folder of FITS files and builds its own temp sequence.
      - Rejected frames move to a rejected/ subfolder with a rejected_frames.txt audit file.
      - Autostretch preset dropdown (Conservative / Default / Aggressive / Linear).
      - Removed: ROI feature, per-frame histogram, "use currently loaded sequence" path.
"""
from __future__ import annotations

import sys
import os
import glob
import shutil
import logging
import traceback
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("BlinkComparator")

import numpy as np

import sirilpy as s
from sirilpy import NoImageError

try:
    from sirilpy.exceptions import SirilError, SirilConnectionError, NoSequenceError
except ImportError:
    class SirilError(Exception):
        pass
    class SirilConnectionError(Exception):
        pass
    class NoSequenceError(Exception):
        pass

s.ensure_installed("numpy", "PyQt6", "matplotlib")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QDialog, QScrollArea, QProgressBar, QRadioButton, QButtonGroup,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFileDialog, QAbstractItemView, QMenu,
    QProgressDialog, QAbstractSpinBox,
    QLineEdit, QTextEdit,
)
from PyQt6.QtCore import (
    Qt, QSettings, QUrl, QTimer, pyqtSignal, QObject, QRectF, QRect, QPoint,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QImage, QPixmap, QShortcut,
    QKeySequence, QDesktopServices, QWheelEvent, QMouseEvent,
)

VERSION = "1.2.8"

SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "BlinkComparator"

LEFT_PANEL_WIDTH = 340

DEFAULT_CACHE_SIZE = 80
THUMBNAIL_WIDTH = 80
THUMBNAIL_HEIGHT = 60
THUMBNAIL_CACHE_SIZE = 200


# ------------------------------------------------------------------------------
# STYLING (matching GradientAnalyzer)
# ------------------------------------------------------------------------------

def _nofocus(w: QWidget | None) -> None:
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
QPushButton#CoffeeButton{background-color:#FFDD00;color:#000000;border:1px solid #ccb100;font-weight:bold}
QPushButton#CoffeeButton:hover{background-color:#ffe740;border-color:#ddcc00}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#PlayButton{background-color:#2a4a2a;border:1px solid #408040;padding:8px;font-size:12pt}
QPushButton#PlayButton:hover{background-color:#3a6a3a}
QPushButton#ApplyButton{background-color:#2a3a5a;border:1px solid #4060a0;padding:8px;font-size:11pt}
QPushButton#ApplyButton:hover{background-color:#3a4a7a}
QPushButton#IncludeButton{background-color:#2a4a2a;border:1px solid #408040}
QPushButton#IncludeButton:hover{background-color:#3a6a3a}
QPushButton#ExcludeButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#ExcludeButton:hover{background-color:#7a3a3a}

QTabWidget::pane{border:1px solid #444444;background:#2b2b2b}
QTabBar::tab{background:#3c3c3c;color:#cccccc;padding:6px 12px;border:1px solid #444444;border-bottom:none;border-radius:4px 4px 0 0;margin-right:2px}
QTabBar::tab:selected{background:#2b2b2b;color:#88aaff;font-weight:bold}
QTabBar::tab:hover{background:#4a4a4a}

QTableWidget{background-color:#2b2b2b;gridline-color:#444444;border:1px solid #444444;color:#e0e0e0}
QTableWidget::item{padding:2px 6px}
QTableWidget::item:selected{background-color:#203a5a}
QHeaderView::section{background-color:#3c3c3c;color:#cccccc;border:1px solid #444444;padding:4px;font-weight:bold}

QScrollArea{border:none;background:#2b2b2b}

QProgressBar{background:#3c3c3c;border:1px solid #555;border-radius:3px;text-align:center;color:#ccc}
QProgressBar::chunk{background:#285299;border-radius:2px}
"""


# ------------------------------------------------------------------------------
# AUTOSTRETCH (Midtone Transfer Function)
# ------------------------------------------------------------------------------

def mtf(midtone: float, x: np.ndarray | float, out: np.ndarray | None = None) -> np.ndarray | float:
    """Midtone Transfer Function.

    Vectorized implementation. When ``out`` is provided, the result is
    written in-place to that buffer — saving one full-frame allocation
    per stretched frame. ``out`` may alias ``x`` for true in-place
    operation (the algorithm reads ``x`` before overwriting it).

    For scalar inputs, uses a fast early-return path.
    """
    if isinstance(x, np.ndarray):
        # denom = (2m - 1) * x - m   (one scratch allocation)
        denom = np.multiply(x, 2.0 * midtone - 1.0)
        denom -= midtone
        # Guard against |denom| ≈ 0 (rare for m in (0,1) with x clipped to [0,1]):
        # replace near-zero entries with 1.0 in-place so the later divide is safe.
        # (np.where(cond, x, y) does NOT support out=; np.putmask does.)
        np.putmask(denom, np.abs(denom) < 1e-10, 1.0)
        # result = (m - 1) * x / denom  →  into `out` (may alias x)
        if out is None:
            out = np.multiply(x, midtone - 1.0)
        else:
            np.multiply(x, midtone - 1.0, out=out)
        out /= denom
        np.clip(out, 0.0, 1.0, out=out)
        return out
    else:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        denom = (2 * midtone - 1) * x - midtone
        if abs(denom) < 1e-10:
            return 0.5
        return max(0.0, min(1.0, (midtone - 1) * x / denom))


# Autostretch presets — user-selectable in Display Options
AUTOSTRETCH_PRESETS: dict[str, dict | None] = {
    "Conservative": {"shadows_clip": -3.5, "target_median": 0.20},
    "Default":      {"shadows_clip": -2.8, "target_median": 0.25},
    "Aggressive":   {"shadows_clip": -1.5, "target_median": 0.35},
    "Linear":       None,  # Bypass MTF: just clip to [0,1] and scale to 255
}
DEFAULT_AUTOSTRETCH_PRESET = "Default"


def autostretch(
    data: np.ndarray,
    shadows_clip: float = -2.8,
    target_median: float = 0.25,
    global_median: float | None = None,
    global_mad: float | None = None,
    linear: bool = False,
) -> np.ndarray:
    """
    Midtone Transfer Function (MTF) Autostretch.
    If linear=True, bypasses MTF and just clips to [0,1] + scales to 255.
    If global_median/global_mad are provided, uses those for consistent brightness.
    """
    if linear:
        out = np.clip(data, 0.0, 1.0) * 255.0
        return out.astype(np.uint8)

    if global_median is not None and global_mad is not None:
        median = global_median
        mad = global_mad
    else:
        # Subsample for faster median/MAD on large arrays (>500k pixels)
        flat = data.ravel()
        if flat.size > 500000:
            step = flat.size // 500000
            flat = flat[::step]
        median = float(np.median(flat))
        # Raw MAD (no 1.4826 σ-conversion) — shadows_clip is expressed in units
        # of MAD to match Siril/PixInsight STF convention.
        mad = float(np.median(np.abs(flat - median)))

    shadow = max(0.0, median + shadows_clip * mad)
    highlight = 1.0

    rng = highlight - shadow
    if rng < 1e-10:
        rng = 1.0

    if median - shadow > 0:
        midtone = mtf(target_median, median - shadow)
    else:
        midtone = 0.5

    # Single allocation: subtract + scale + clip in one chain, reusing the buffer.
    # mtf(..., out=stretched) then runs in-place so no additional full-frame alloc.
    stretched = np.subtract(data, shadow, dtype=np.float32)
    stretched *= (1.0 / rng)
    np.clip(stretched, 0, 1, out=stretched)
    mtf(midtone, stretched, out=stretched)
    stretched *= 255.0
    return stretched.astype(np.uint8)


# ------------------------------------------------------------------------------
# SHARED IMAGE CONVERSION HELPERS
# ------------------------------------------------------------------------------

# Display constants
ZOOM_FACTOR = 1.15
MAX_ZOOM = 20.0
MIN_ZOOM = 0.1
SLIDER_HANDLE_MARGIN = 7  # Approximate half-width of slider handle in pixels


def frame_data_to_qimage(
    frame_data: np.ndarray,
    global_median: float | None = None,
    global_mad: float | None = None,
    preset: str = DEFAULT_AUTOSTRETCH_PRESET,
) -> QImage | None:
    """Convert sirilpy frame data (float32, channels×H×W) to a stretched QImage.

    Handles RGB (3×H×W), single-channel (1×H×W), and 2D mono arrays.
    Applies autostretch (per `preset`) and flips from Siril's bottom-up orientation.
    Returns a QImage that owns its own pixel data (.copy()), or None on failure.
    """
    params = AUTOSTRETCH_PRESETS.get(preset, AUTOSTRETCH_PRESETS[DEFAULT_AUTOSTRETCH_PRESET])
    if params is None:
        stretch_kwargs = {"linear": True}
    else:
        stretch_kwargs = {
            "shadows_clip": params["shadows_clip"],
            "target_median": params["target_median"],
            "global_median": global_median,
            "global_mad": global_mad,
        }

    # Vertical flip (Siril frames are bottom-up) is done via QImage.mirrored()
    # rather than np.ascontiguousarray(arr[::-1]). mirrored() returns a new
    # QImage that owns its buffer, so we also skip the subsequent .copy() —
    # saves one full-frame memcpy on every display refresh.
    if frame_data.ndim == 3 and frame_data.shape[0] == 3:
        # Vectorized RGB stretch: one autostretch() call on the whole (3,H,W)
        # array instead of three separate calls. Since the three channels share
        # stretch parameters (global median/MAD + preset), the output is
        # equivalent to per-channel calls when globals are provided, and gives
        # a single shared luminance curve across R/G/B when they aren't.
        rgb = autostretch(frame_data, **stretch_kwargs)  # (3, H, W) uint8
        _, h, w = rgb.shape
        alpha = np.full((h, w), 255, dtype=np.uint8)
        rgbx = np.ascontiguousarray(np.stack((rgb[0], rgb[1], rgb[2], alpha), axis=-1))
        qimg = QImage(rgbx.data, w, h, w * 4, QImage.Format.Format_RGBX8888)
        return qimg.mirrored(False, True)
    elif frame_data.ndim == 3 and frame_data.shape[0] == 1:
        mono = np.ascontiguousarray(autostretch(frame_data[0], **stretch_kwargs))
        h, w = mono.shape
        qimg = QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8)
        return qimg.mirrored(False, True)
    elif frame_data.ndim == 2:
        mono = np.ascontiguousarray(autostretch(frame_data, **stretch_kwargs))
        h, w = mono.shape
        qimg = QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8)
        return qimg.mirrored(False, True)
    return None


def load_frame_data(siril_iface, index: int) -> np.ndarray | None:
    """Load a single frame's pixel data as float32 [0, 1] from Siril. Returns None on error."""
    try:
        frame = siril_iface.get_seq_frame(index, with_pixels=True)
        if frame is None or frame.data is None:
            return None
        data = frame.data
        # Fast path: check dtype before scanning with max()
        if np.issubdtype(data.dtype, np.integer):
            # uint16 or similar integer data — always needs normalization
            return data.astype(np.float32) * (1.0 / 65535.0)
        data = data.astype(np.float32) if data.dtype != np.float32 else data
        # Float data: sample a few pixels to detect [0, 65535] vs [0, 1] range
        if data.flat[0] > 1.5 or (data.size > 100 and data.flat[data.size // 2] > 1.5):
            data = data * (1.0 / 65535.0)
        return data
    except (SirilError, OSError, ValueError, TypeError, RuntimeError) as exc:
        log.debug("Failed to load frame %d data: %s", index, exc)
        return None


# ------------------------------------------------------------------------------
# MATPLOTLIB LAZY LOADING (same pattern as GradientAnalyzer)
# ------------------------------------------------------------------------------

_MPL_CACHE = None


def _get_matplotlib() -> tuple | None:
    """Lazy-load matplotlib. Returns (FigureCanvasQTAgg, Figure, cm) or None."""
    global _MPL_CACHE
    if _MPL_CACHE is not None:
        return _MPL_CACHE if _MPL_CACHE is not False else None
    try:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        import matplotlib.cm as cm
        _MPL_CACHE = (FigureCanvasQTAgg, Figure, cm)
        return _MPL_CACHE
    except ImportError:
        _MPL_CACHE = False
        return None


class _MplWidgetBase(QWidget):
    """Base class for matplotlib-based display widgets."""

    def __init__(self, placeholder_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 180)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(placeholder_text)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 11pt;")
        self._layout.addWidget(self._placeholder)
        self._canvas = None
        self._fig = None
        mpl = _get_matplotlib()
        if mpl is not None:
            self._FigureCanvasQTAgg, self._Figure, self._cm = mpl
            self._mpl_available = True
        else:
            self._placeholder.setText("matplotlib is required for this widget")
            self._mpl_available = False
            self._FigureCanvasQTAgg = self._Figure = self._cm = None

    def _replace_canvas(self, fig) -> None:
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
            self._canvas = None
        # Close previous figure to prevent matplotlib memory leak
        # Use fig.clear() + del instead of plt.close() to avoid importing pyplot
        if self._fig is not None:
            try:
                self._fig.clear()
                del self._fig
            except Exception:
                pass
        self._placeholder.setVisible(False)
        self._fig = fig
        self._canvas = self._FigureCanvasQTAgg(fig)
        self._layout.insertWidget(0, self._canvas, 1)
        self._canvas.show()

    def clear(self) -> None:
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
            self._canvas = None
            self._fig = None
        self._placeholder.setVisible(True)


# ------------------------------------------------------------------------------
# FRAME STATISTICS (loaded once, consumed by table + graph + batch reject)
# ------------------------------------------------------------------------------

class FrameStatistics:
    """Loads and stores per-frame stats from Siril for the entire sequence."""

    COLUMNS = ["fwhm", "roundness", "background", "stars", "median", "sigma", "date_obs", "weight"]

    def __init__(self, siril_iface, seq):
        self.siril = siril_iface
        self.seq = seq
        self.total = seq.number
        self.data: list[dict] = []
        # Siril stores regdata on ch1 (green) for RGB, ch0 for mono.
        # We search all channels up to nb_layers to find the one with data.
        self._nb_layers = getattr(seq, 'nb_layers', 1)
        # M1 (v1.2.8 audit-5): monotonic revision counter. Bumped by every
        # mutation path (load_all, backfill_stats, invalidate_column_cache)
        # so render-signature dedupe can detect data changes without relying
        # on `id(self.data)` — which CPython reuses once the old list is GC'd
        # and could produce false-positive cache hits after a full reload.
        self.data_revision: int = 0

    def load_all(self, progress_callback=None, skip_stats: bool = False) -> None:
        """Load registration data, stats, and imgdata for all frames.

        When regdata is unavailable (sequence registered without star detection),
        falls back to stats.median for background and stats.bgnoise for noise.
        Sets self.has_regdata flag so the UI can offer to run seqfindstar.

        Performance: probes the regdata channel once at frame 0 and caches it
        (rather than re-searching all channels on every frame). Skips the
        get_seq_stats RPC entirely when regdata already carries a usable
        background + median — saves ~1 RPC per frame on registered sequences,
        which is the dominant cost for long stacks.

        P3 (v1.2.8 audit-4): `skip_stats=True` skips the per-frame
        get_seq_stats RPC (~1-2 s per 1000 frames). Median/Sigma/bgnoise
        will be blank until `backfill_stats()` is called. Opt-in — the
        default still populates all columns synchronously so the stats
        table is fully rendered when load_all returns.
        """
        self.data = []
        self.has_regdata = False  # Track whether any frame has registration data

        # Probe once: Siril stores regdata on ch1 (green) for RGB, ch0 for mono.
        # Scan channels at frame 0 to find the one with valid data, then use
        # that channel for every subsequent frame (the layout doesn't vary).
        reg_channel: int | None = None
        for ch in range(self._nb_layers):
            try:
                probe = self.siril.get_seq_regdata(0, ch)
                if probe is not None and getattr(probe, 'fwhm', 0) > 0:
                    reg_channel = ch
                    break
            except Exception:
                continue

        for i in range(self.total):
            row = {
                "frame_idx": i,
                "fwhm": 0.0,
                "roundness": 0.0,
                "background": 0.0,
                "stars": 0,
                "median": 0.0,
                "sigma": 0.0,
                "bgnoise": 0.0,
                "date_obs": "",
            }

            reg = None
            if reg_channel is not None:
                try:
                    reg = self.siril.get_seq_regdata(i, reg_channel)
                except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                    log.debug("Frame %d: regdata unavailable: %s", i, exc)
                    reg = None

            if reg is not None:
                v = getattr(reg, 'fwhm', 0)
                if v > 0:
                    row["fwhm"] = float(v)
                    self.has_regdata = True
                v = getattr(reg, 'roundness', 0)
                if v > 0:
                    row["roundness"] = float(v)
                v = getattr(reg, 'background_lvl', 0)
                if v > 0:
                    row["background"] = float(v)
                v = getattr(reg, 'number_of_stars', 0)
                if v > 0:
                    row["stars"] = int(v)

            # Always fetch get_seq_stats: regdata (fwhm/roundness/background_lvl/
            # number_of_stars) does NOT contain median or sigma, so if we skip
            # this call whenever regdata has background, the Median and Sigma
            # columns in the stats table stay permanently empty. The RPC cost
            # is paid once per frame at sequence-load time (not per playback
            # tick), so correctness wins over the marginal I/O savings of
            # the previous "need_stats" gate. [1.2.8 regression fix for 1.2.6]
            if not skip_stats:
                try:
                    stats = self.siril.get_seq_stats(i, 0)
                    if stats is not None:
                        v = getattr(stats, 'median', 0)
                        if v:
                            row["median"] = float(v)
                        v = getattr(stats, 'sigma', 0)
                        if v > 0:
                            row["sigma"] = float(v)
                        v = getattr(stats, 'bgnoise', 0)
                        if v > 0:
                            row["bgnoise"] = float(v)
                        # Fallback: use stats.median as background when regdata is missing
                        if row["background"] == 0.0 and row["median"] > 0:
                            row["background"] = row["median"]
                except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                    log.debug("Frame %d: stats unavailable: %s", i, exc)

            # Date-observed: try imgdata.date_obs first (Siril's canonical
            # attribute). Some sirilpy versions / Siril builds expose it as
            # .date instead, and a few leave imgdata bare and only surface
            # the timestamp on the frame header. Chain through all three so
            # the column populates regardless of which shape Siril returned.
            try:
                imgdata = self.siril.get_seq_imgdata(i)
                if imgdata is not None:
                    v = (getattr(imgdata, 'date_obs', None)
                         or getattr(imgdata, 'date', None)
                         or getattr(imgdata, 'DATE-OBS', None)
                         or getattr(imgdata, 'date-obs', None))
                    if v:
                        row["date_obs"] = str(v)
            except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                log.debug("Frame %d: imgdata unavailable: %s", i, exc)

            # Last-ditch date fallback: peek at the frame's FITS header.
            # Only fires if imgdata didn't yield one — keeps the hot path
            # cheap for the common case.
            if not row["date_obs"]:
                try:
                    frame = self.siril.get_seq_frame(i, with_pixels=False)
                    if frame is not None:
                        hdr = getattr(frame, 'header', None)
                        if hdr is not None:
                            # header may be a dict-like or a string blob
                            if hasattr(hdr, 'get'):
                                v = hdr.get('DATE-OBS') or hdr.get('DATE_OBS') or hdr.get('date_obs')
                            else:
                                v = None
                            if v:
                                row["date_obs"] = str(v)
                except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                    log.debug("Frame %d: header date lookup failed: %s", i, exc)

            self.data.append(row)

            if progress_callback and i % 5 == 0:
                progress_callback(i, self.total)

        # Compute composite quality weights
        self._compute_weights()
        # P1 (v1.2.8 audit-4): drop the np-column cache so the next graph/
        # scatter render re-builds it from the fresh data.
        self.invalidate_column_cache()

    def backfill_stats(self, progress_callback=None) -> None:
        """P3 (v1.2.8 audit-4): fill in Median/Sigma/bgnoise columns for
        rows loaded with `skip_stats=True`. Safe to call from a background
        thread — only mutates individual dict values, which is atomic under
        the GIL. Callers should invoke `invalidate_column_cache()` after
        and refresh the stats table/graph/scatter to pick up new values.
        """
        if not self.data:
            return
        for i, row in enumerate(self.data):
            # Skip if already populated (full load_all ran).
            if row.get("median", 0) or row.get("sigma", 0):
                continue
            try:
                stats = self.siril.get_seq_stats(i, 0)
                if stats is None:
                    continue
                v = getattr(stats, "median", 0)
                if v:
                    row["median"] = float(v)
                v = getattr(stats, "sigma", 0)
                if v > 0:
                    row["sigma"] = float(v)
                v = getattr(stats, "bgnoise", 0)
                if v > 0:
                    row["bgnoise"] = float(v)
                if row["background"] == 0.0 and row["median"] > 0:
                    row["background"] = row["median"]
            except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                log.debug("Frame %d: backfill stats unavailable: %s", i, exc)
            if progress_callback and i % 25 == 0:
                progress_callback(i, self.total)
        self.invalidate_column_cache()

    def _compute_weights(self) -> None:
        """Compute composite quality weight: (1/FWHM) * roundness * (1/background) * sqrt(stars)."""
        # Normalize each metric to [0, 1] range, then combine
        fwhm_vals = [r["fwhm"] for r in self.data if r["fwhm"] > 0]
        bg_vals = [r["background"] for r in self.data if r["background"] > 0]
        star_vals = [r["stars"] for r in self.data if r["stars"] > 0]
        rnd_vals = [r["roundness"] for r in self.data if r["roundness"] > 0]

        fwhm_min = min(fwhm_vals) if fwhm_vals else 1.0
        fwhm_max = max(fwhm_vals) if fwhm_vals else 1.0
        bg_min = min(bg_vals) if bg_vals else 0.0
        bg_max = max(bg_vals) if bg_vals else 1.0
        star_max = max(star_vals) if star_vals else 1.0

        for row in self.data:
            w = 0.0
            n_factors = 0
            if row["fwhm"] > 0 and fwhm_max > fwhm_min:
                # Lower FWHM = better → invert
                w_fwhm = 1.0 - (row["fwhm"] - fwhm_min) / (fwhm_max - fwhm_min)
                w += w_fwhm
                n_factors += 1
            if row["roundness"] > 0:
                # Higher roundness = better (closer to 1.0)
                w += row["roundness"]
                n_factors += 1
            if row["background"] > 0 and bg_max > bg_min:
                # Lower background = better → invert
                w_bg = 1.0 - (row["background"] - bg_min) / (bg_max - bg_min)
                w += w_bg
                n_factors += 1
            if row["stars"] > 0 and star_max > 0:
                w += row["stars"] / star_max
                n_factors += 1
            row["weight"] = round(w / max(1, n_factors), 4) if n_factors > 0 else 0.0

    def get(self, index: int) -> dict:
        if 0 <= index < len(self.data):
            return self.data[index]
        return {}

    def get_column(self, column: str) -> list:
        return [row.get(column, 0) for row in self.data]

    def get_column_np(self, column: str) -> np.ndarray:
        """P1 (v1.2.8 audit-4): numpy-cached column accessor. The graph
        and scatter widgets call this on every render (3+ metrics each);
        rebuilding a Python list of floats per call was wasteful. Cache
        is invalidated by `invalidate_column_cache()` — callers that
        mutate `self.data` (currently only `load_all`) must call it.
        """
        cache = getattr(self, "_np_columns", None)
        if cache is None:
            cache = {}
            self._np_columns = cache
        arr = cache.get(column)
        if arr is None:
            arr = np.asarray(
                [row.get(column, 0) for row in self.data],
                dtype=np.float64 if column != "stars" else np.int64,
            )
            cache[column] = arr
        return arr

    def invalidate_column_cache(self) -> None:
        """Drop the numpy column cache — call after `self.data` is mutated
        (re-load, register refresh). Graph/scatter will re-populate on
        their next render.

        M1 (v1.2.8 audit-5): also bumps `data_revision` so downstream
        render-signature dedupe treats the post-mutation state as distinct
        even if `id(self.data)` happens to match (CPython reuses ids).
        """
        self._np_columns = {}
        self.data_revision += 1

    def get_all_rows(self) -> list[dict]:
        return self.data


# ------------------------------------------------------------------------------
# UNDO STACK
# ------------------------------------------------------------------------------

class UndoStack:
    """Stack-based undo for marking operations with group support.

    Single marks push individual (frame_idx, prev_state) entries.
    Batch operations push a list of entries as a single group, so one
    Ctrl+Z undoes the entire batch at once.
    """

    def __init__(self, max_size: int = 500):
        # Each entry is either a single (idx, bool) or a list[(idx, bool)] for batch ops
        self._stack: list[tuple[int, bool] | list[tuple[int, bool]]] = []
        self._max_size = max_size

    def push(self, frame_idx: int, previous_included: bool) -> None:
        """Push a single marking action."""
        self._stack.append((frame_idx, previous_included))
        if len(self._stack) > self._max_size:
            self._stack.pop(0)

    def push_batch(self, entries: list[tuple[int, bool]]) -> None:
        """Push a batch of marking actions as a single undo group."""
        if entries:
            self._stack.append(entries)
            if len(self._stack) > self._max_size:
                self._stack.pop(0)

    def pop(self) -> tuple[int, bool] | list[tuple[int, bool]] | None:
        """Pop the last action (single or batch group)."""
        if self._stack:
            return self._stack.pop()
        return None

    def can_undo(self) -> bool:
        return len(self._stack) > 0

    def clear(self) -> None:
        self._stack.clear()


# ------------------------------------------------------------------------------
# FRAME CACHE
# ------------------------------------------------------------------------------

class FrameCache:
    """LRU cache for stretched frame preview images."""

    def __init__(
        self,
        siril_iface,
        seq,
        max_frames: int = DEFAULT_CACHE_SIZE,
        display_width: int = 800,
        display_height: int = 600,
        stretch_preset: str = DEFAULT_AUTOSTRETCH_PRESET,
    ):
        self.siril = siril_iface
        self.seq = seq
        self.max_frames = max_frames
        self.display_width = display_width
        self.display_height = display_height
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
        self.global_median: float | None = None
        self.global_mad: float | None = None
        self.reference_data: np.ndarray | None = None
        self.stretch_preset: str = stretch_preset
        # H1 (v1.2.8 audit-3): size epoch bumped on every invalidate/resize.
        # Worker threads snapshot this at entry and re-check under lock before
        # committing; if the epoch moved, their QImage was scaled to stale
        # display dimensions and must be dropped instead of cached.
        self._size_epoch: int = 0
        # M2 (v1.2.8 audit-3): early-exit flag for preload_range. Future.cancel()
        # is a no-op on already-running tasks, so a long preload could outlive
        # the main window on close. Main window toggles this in closeEvent.
        self._closing: bool = False

    def compute_global_stretch(self, sample_count: int = 10) -> None:
        """Sample the sequence to derive a shared median/MAD for linked autostretch.

        IMPORTANT: `autostretch()` operates on frame data normalized to [0, 1]
        (see load_frame_data), so the returned global_median / global_mad MUST
        also be in [0, 1]. Siril's `get_seq_stats` returns values in the image's
        native range (0-65535 for uint16 FITS), so we detect the scale by
        magnitude and normalize. If stats are unavailable, we fall back to
        loading a few sample frames and computing directly from the normalized
        pixel data.
        """
        total = self.seq.number
        step = max(1, total // sample_count)
        indices = list(range(0, total, step))[:sample_count]
        medians: list[float] = []
        mads: list[float] = []

        for idx in indices:
            try:
                stats = self.siril.get_seq_stats(idx, 0)
                if stats is None:
                    continue
                med = float(stats.median)
                # Prefer true MAD if sirilpy exposes it. Otherwise convert
                # avgDev (= MAD × 1.2533 for Gaussian data) or sigma
                # (= MAD × 1.4826 for Gaussian data) back to MAD so our
                # shadows_clip stays in units of MAD (Siril/PI STF convention).
                mad_val = float(getattr(stats, "mad", 0.0) or 0.0)
                if mad_val <= 0:
                    avg_dev = float(getattr(stats, "avgDev", 0.0) or 0.0)
                    if avg_dev > 0:
                        mad_val = avg_dev / 1.2533
                    else:
                        sigma = float(getattr(stats, "sigma", 0.0) or 0.0)
                        if sigma > 0:
                            mad_val = sigma / 1.4826
                if mad_val <= 0:
                    continue
                # Normalize to [0, 1] if the values look like 16-bit ADU.
                if med > 1.5 or mad_val > 1.5:
                    med *= (1.0 / 65535.0)
                    mad_val *= (1.0 / 65535.0)
                medians.append(med)
                mads.append(mad_val)
            except Exception:
                pass

        # Fallback: if the stats call returned nothing usable, sample a few
        # frames directly and compute median/MAD from the normalized data.
        if not medians:
            for idx in indices[:3]:
                data = load_frame_data(self.siril, idx)
                if data is None:
                    continue
                flat = data.ravel()
                if flat.size > 500000:
                    flat = flat[::flat.size // 500000]
                m = float(np.median(flat))
                medians.append(m)
                mads.append(float(np.median(np.abs(flat - m))))

        # L3 (v1.2.8 audit-5): compute into locals then publish both fields
        # atomically under `self.lock`. Previously `self.global_median` was
        # assigned a few lines before `self.global_mad`, and the star-detection
        # rebind calls this from the main thread while preload workers may
        # hold references to the cache — a background render that observed
        # a fresh median paired with a stale (or None) mad produced obviously
        # wrong autostretch on one frame. Single paired assignment prevents
        # that torn-read window.
        if medians:
            new_median = float(np.median(medians))
            new_mad = float(np.median(mads)) if mads else 0.001
        else:
            new_median = None
            new_mad = None
        with self.lock:
            self.global_median = new_median
            self.global_mad = new_mad

    def load_reference_frame(self) -> None:
        ref_idx = self.seq.reference_image
        if ref_idx < 0 or ref_idx >= self.seq.number:
            ref_idx = 0
        # L3 (v1.2.8 audit-5): load into a local then publish under lock so a
        # concurrent reader can never observe a half-populated reference_data
        # (load_frame_data can be slow and a preload worker checking
        # `self.reference_data is not None` should only see fully loaded data).
        new_ref = load_frame_data(self.siril, ref_idx)
        with self.lock:
            self.reference_data = new_ref

    def get_frame(self, index: int) -> QImage | None:
        """Get frame from cache or load from Siril. Thread-safe with double-check.

        Always applies globally-linked autostretch (shared median/MAD across
        the sequence) so brightness differences between frames are visible.
        """
        with self.lock:
            if index in self.cache:
                self.cache.move_to_end(index)
                return self.cache[index]
            # Mark as loading to prevent duplicate loads from preload threads
            self.cache[index] = None  # Placeholder
            # H1: snapshot size params + epoch under the lock so the worker
            # scales to the dimensions that were live when it started.
            epoch = self._size_epoch
            target_w = self.display_width
            target_h = self.display_height
        qimg = self._load_and_stretch(index, target_w, target_h)
        with self.lock:
            # H1: if invalidate() / resize bumped the epoch while we were
            # loading, our QImage is stale. Drop it rather than caching a
            # wrong-sized frame that would later flash on screen.
            if epoch != self._size_epoch:
                self.cache.pop(index, None)
                return None
            if qimg is not None:
                self.cache[index] = qimg
                self.cache.move_to_end(index)
            else:
                self.cache.pop(index, None)
            while len(self.cache) > self.max_frames:
                self.cache.popitem(last=False)
        return qimg

    def _load_and_stretch(
        self, index: int, target_w: int | None = None, target_h: int | None = None
    ) -> QImage | None:
        """Load frame from Siril, apply linked autostretch, return scaled QImage.

        target_w / target_h are snapshotted by the caller under lock (H1);
        callers that don't pass them fall back to the live attributes for
        backward compatibility.
        """
        frame_data = load_frame_data(self.siril, index)
        if frame_data is None:
            return None

        qimg = frame_data_to_qimage(
            frame_data, self.global_median, self.global_mad,
            preset=self.stretch_preset,
        )
        if qimg is None:
            return None

        w = target_w if target_w is not None else self.display_width
        h = target_h if target_h is not None else self.display_height
        return qimg.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def invalidate(self) -> None:
        with self.lock:
            self.cache.clear()
            # H1: bump epoch so any in-flight worker drops its result.
            self._size_epoch += 1

    def set_display_size(self, width: int, height: int) -> bool:
        """Atomically update display dimensions and bump the size epoch.

        Returns True if the size changed. Callers should invalidate()
        and repaint on True. Done under the cache lock so an in-flight
        worker cannot snapshot half-old/half-new state.
        """
        with self.lock:
            if self.display_width == width and self.display_height == height:
                return False
            self.display_width = width
            self.display_height = height
            self._size_epoch += 1
            self.cache.clear()
            return True

    def peek(self, index: int) -> QImage | None:
        """Return a cached frame WITHOUT triggering a load. Used by the
        thumbnail cache to recycle the already-stretched display image
        instead of re-reading the FITS from disk.
        """
        with self.lock:
            qimg = self.cache.get(index)
            if qimg is None:
                return None
            # Touch LRU so actively-displayed frames stay hot
            self.cache.move_to_end(index)
            return qimg

    def preload_range(self, start: int, count: int) -> None:
        total = self.seq.number
        for i in range(start, min(start + count, total)):
            # M2: exit early if the app is shutting down. Future.cancel() is a
            # no-op once the worker is RUNNING, so without this check we would
            # keep loading frames for up to `count` iterations after close.
            if self._closing:
                return
            if i < 0:
                continue
            with self.lock:
                if i in self.cache:
                    continue
            self.get_frame(i)


# Shared thread pool for preloading (1 worker — avoids flooding Siril's socket)
_preload_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preload")


# ------------------------------------------------------------------------------
# THUMBNAIL CACHE
# ------------------------------------------------------------------------------

class ThumbnailCache:
    """Separate LRU cache for small frame thumbnails."""

    def __init__(self, siril_iface, seq, global_median=None, global_mad=None,
                 max_items: int = THUMBNAIL_CACHE_SIZE,
                 stretch_preset: str = DEFAULT_AUTOSTRETCH_PRESET,
                 frame_cache: "FrameCache | None" = None):
        self.siril = siril_iface
        self.seq = seq
        self.global_median = global_median
        self.global_mad = global_mad
        self.max_items = max_items
        self.stretch_preset = stretch_preset
        # Optional reference to the main FrameCache. When provided, thumbnails
        # are derived from the already-stretched display image instead of
        # re-loading the FITS — a huge win during playback/scroll.
        self.frame_cache = frame_cache
        self.cache: OrderedDict[int, QPixmap] = OrderedDict()
        self.lock = threading.Lock()

    def invalidate(self) -> None:
        with self.lock:
            self.cache.clear()

    def get_thumbnail(self, index: int) -> QPixmap | None:
        """Get thumbnail from cache or load. Thread-safe with double-check."""
        with self.lock:
            if index in self.cache:
                self.cache.move_to_end(index)
                return self.cache[index]
            self.cache[index] = None  # Placeholder prevents duplicate loads

        pix = self._load_thumbnail(index)
        with self.lock:
            if pix is not None:
                self.cache[index] = pix
                self.cache.move_to_end(index)
            else:
                self.cache.pop(index, None)
            while len(self.cache) > self.max_items:
                self.cache.popitem(last=False)
        return pix

    def _load_thumbnail(self, index: int) -> QPixmap | None:
        """Load a single frame, stretch, and scale to thumbnail size.

        Fast path: if the main FrameCache already has this frame as a
        stretched display image, scale that down instead of re-reading
        the FITS and re-stretching. Saves ~40 MB of disk I/O + a full
        median/MAD pass per thumbnail when the main cache is warm.
        """
        # Thumbnails use FastTransformation (nearest-neighbor). At 80x60 px the
        # visual difference vs. Smooth is imperceptible on natural astro frames,
        # but Fast skips the bilinear filter pass — ~3–4× faster scaling per
        # thumbnail, which matters when building 1000+ entries on load.
        if self.frame_cache is not None:
            cached = self.frame_cache.peek(index)
            if cached is not None:
                scaled = cached.scaled(
                    THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                return QPixmap.fromImage(scaled)

        data = load_frame_data(self.siril, index)
        if data is None:
            return None
        qimg = frame_data_to_qimage(data, self.global_median, self.global_mad,
                                    preset=self.stretch_preset)
        if qimg is None:
            return None
        qimg = qimg.scaled(
            THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        return QPixmap.fromImage(qimg)


# ------------------------------------------------------------------------------
# FRAME MARKER (pending include/exclude changes)
# ------------------------------------------------------------------------------

class FrameMarker:
    """Manages frame inclusion/exclusion markings with pending changes.

    Collects mark_include/mark_exclude operations locally. Changes are
    only sent to Siril when apply_to_siril() is called, preventing
    accidental modifications to the sequence.
    """

    def __init__(self, seq):
        self.seq = seq
        self.total = seq.number
        self.original: dict[int, bool] = {}
        self._excluded_cache: set[int] | None = None  # Lazy-invalidated excluded set
        for i in range(self.total):
            try:
                imgdata = None
                try:
                    imgdata = seq.imgparam[i] if hasattr(seq, 'imgparam') else None
                except (AttributeError, IndexError):
                    pass
                if imgdata is not None and hasattr(imgdata, 'incl'):
                    self.original[i] = bool(imgdata.incl)
                else:
                    self.original[i] = True
            except Exception:
                self.original[i] = True
        self.changes: dict[int, bool] = {}

    def is_included(self, index: int) -> bool:
        if index in self.changes:
            return self.changes[index]
        return self.original.get(index, True)

    def mark_include(self, index: int) -> None:
        if self.original.get(index, True) and index not in self.changes:
            return
        if self.original.get(index, True):
            self.changes.pop(index, None)
        else:
            self.changes[index] = True
        self._excluded_cache = None  # Invalidate

    def mark_exclude(self, index: int) -> None:
        if not self.original.get(index, True) and index not in self.changes:
            return
        if not self.original.get(index, True):
            self.changes.pop(index, None)
        else:
            self.changes[index] = False
        self._excluded_cache = None  # Invalidate

    def get_pending_count(self) -> int:
        return len(self.changes)

    def commit(self) -> None:
        """Bake pending changes into the baseline — pending count becomes 0.

        Called after Apply Rejections so the user isn't prompted again on
        close about the same marks they already exported.
        """
        if not self.changes:
            return
        for idx, incl in self.changes.items():
            self.original[idx] = incl
        self.changes.clear()
        self._excluded_cache = None

    def commit_subset(self, indices: set[int]) -> None:
        """L4 (v1.2.8 audit-5): bake only the listed indices into the
        baseline, leaving other pending changes untouched.

        Used by `_apply_changes` when some file moves fail: frames that
        stayed in the working folder should remain flagged as
        "pending-excluded" (so the close-confirm dialog still asks the
        user about them) rather than being silently marked committed
        while their files are still sitting next to the included ones.
        """
        if not self.changes or not indices:
            return
        for idx in list(self.changes.keys()):
            if idx in indices:
                self.original[idx] = self.changes[idx]
                del self.changes[idx]
        self._excluded_cache = None

    def reset_all(self) -> None:
        """Force every frame back to 'included' — clears both the Siril-derived
        baseline and any pending changes. After this call, pending count is 0
        and get_excluded_indices() returns an empty set.
        """
        for i in range(self.total):
            self.original[i] = True
        self.changes.clear()
        self._excluded_cache = None

    def get_newly_excluded_count(self) -> int:
        return sum(1 for v in self.changes.values() if not v)

    def get_newly_included_count(self) -> int:
        return sum(1 for v in self.changes.values() if v)

    def get_excluded_indices(self) -> set[int]:
        """Get all currently excluded frame indices (original + pending). Cached until next mark."""
        if self._excluded_cache is not None:
            return self._excluded_cache
        excluded = set()
        for i in range(self.total):
            if not self.is_included(i):
                excluded.add(i)
        self._excluded_cache = excluded
        return excluded

    # L2 (v1.2.8 audit-5): `apply_to_siril` (set_seq_frame_incl bulk path)
    # was removed. Folder mode is the only surviving flow and it writes
    # changes through `_apply_changes` → file moves + `marker.commit*()`
    # instead of calling Siril's include/exclude RPC. Keeping dead code
    # around just invites future misuse.


# ------------------------------------------------------------------------------
# STATISTICS TABLE WIDGET
# ------------------------------------------------------------------------------

class StatisticsTableWidget(QWidget):
    """Sortable table showing all frame statistics."""
    frame_selected = pyqtSignal(int)
    reject_selected = pyqtSignal(list)  # Emitted when user right-clicks → reject selected

    HEADERS = ["Frame", "Weight", "FWHM", "Round", "BG Level", "Stars", "Median", "Sigma", "Date", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.table)

        self._current_frame = -1
        self._frame_to_row: dict[int, int] = {}  # frame_idx → visual row (rebuilt on sort)

        # Rebuild mapping when table is sorted
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._rebuild_row_map)

    def _rebuild_row_map(self) -> None:
        """Rebuild frame_idx → row mapping after sort. O(N) but only on sort events."""
        self._frame_to_row.clear()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None:
                frame_idx = item.data(Qt.ItemDataRole.UserRole)
                if frame_idx is not None:
                    self._frame_to_row[frame_idx] = r

    def populate(self, frame_stats: FrameStatistics, marker: FrameMarker) -> None:
        # Disable repaints + signal traffic during the bulk insert. For a
        # 1000-frame sequence this loop does ~10 000 QTableWidgetItem
        # constructions + setItem() calls; without the guard Qt re-lays-out
        # and re-paints the viewport after every cell.
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        rows = frame_stats.get_all_rows()
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            idx = row["frame_idx"]
            col = 0

            # Frame number
            item_frame = QTableWidgetItem()
            item_frame.setData(Qt.ItemDataRole.DisplayRole, idx + 1)
            item_frame.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item_frame)
            col += 1

            # Weight
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row.get("weight", 0), 4) if row.get("weight", 0) > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # FWHM
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row["fwhm"], 2) if row["fwhm"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Roundness
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row["roundness"], 2) if row["roundness"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Background
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row["background"], 4) if row["background"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Stars
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, row["stars"] if row["stars"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Median
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row["median"], 4) if row["median"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Sigma
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, round(row["sigma"], 4) if row["sigma"] > 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Date
            item = QTableWidgetItem(row.get("date_obs", ""))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.table.setItem(r, col, item)
            col += 1

            # Status
            incl = marker.is_included(idx)
            status_item = QTableWidgetItem("Included" if incl else "Excluded")
            status_item.setData(Qt.ItemDataRole.UserRole, idx)
            if not incl:
                status_item.setForeground(QColor("#dd4444"))
            else:
                status_item.setForeground(QColor("#55aa55"))
            self.table.setItem(r, col, status_item)

            # Row background for excluded
            if not incl:
                for c in range(self.table.columnCount()):
                    self.table.item(r, c).setBackground(QColor("#3a2020"))

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self._rebuild_row_map()
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

    def _set_row_background(self, row: int, color: QColor) -> None:
        """Set background color for all cells in a row."""
        for c in range(self.table.columnCount()):
            cell = self.table.item(row, c)
            if cell is not None:
                cell.setBackground(color)

    def highlight_current(self, index: int) -> None:
        """Highlight the current frame row. O(1) via frame→row mapping.

        Early-outs when the target frame is already highlighted — otherwise
        rapid slider scrubbing would issue O(cols) × 2 item.setBackground()
        calls per slider tick for no visual change.
        """
        if index == self._current_frame:
            return
        old_frame = self._current_frame
        self._current_frame = index

        # Restore old row color
        if old_frame >= 0 and old_frame in self._frame_to_row:
            old_row = self._frame_to_row[old_frame]
            status_col = self.table.columnCount() - 1
            status_item = self.table.item(old_row, status_col)
            is_excluded = status_item and status_item.text() == "Excluded"
            self._set_row_background(old_row, QColor("#3a2020") if is_excluded else QColor("#2b2b2b"))

        # Highlight new row
        if index in self._frame_to_row:
            new_row = self._frame_to_row[index]
            self._set_row_background(new_row, QColor("#203a5a"))
            item = self.table.item(new_row, 0)
            if item is not None:
                self.table.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)

    def update_frame_status(self, index: int, included: bool, marker: FrameMarker) -> None:
        """Update a single frame's status. O(1) via frame→row mapping."""
        if index not in self._frame_to_row:
            return
        r = self._frame_to_row[index]
        status_col = self.table.columnCount() - 1
        status = self.table.item(r, status_col)
        if status:
            status.setText("Included" if included else "Excluded")
            status.setForeground(QColor("#55aa55") if included else QColor("#dd4444"))
        bg = QColor("#3a2020") if not included else QColor("#2b2b2b")
        if index == self._current_frame:
            bg = QColor("#203a5a")
        self._set_row_background(r, bg)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            frame_idx = item.data(Qt.ItemDataRole.UserRole)
            if frame_idx is not None:
                self.frame_selected.emit(frame_idx)

    def _on_context_menu(self, pos) -> None:
        indices = self.get_selected_frame_indices()
        if not indices:
            return
        menu = QMenu(self)
        action_reject = menu.addAction(f"Reject {len(indices)} selected frame(s)")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == action_reject:
            self.reject_selected.emit(indices)

    def get_selected_frame_indices(self) -> list[int]:
        """Get frame indices of all selected rows."""
        indices = []
        for item in self.table.selectedItems():
            if item.column() == 0:
                frame_idx = item.data(Qt.ItemDataRole.UserRole)
                if frame_idx is not None:
                    indices.append(frame_idx)
        return indices


# ------------------------------------------------------------------------------
# SCATTER PLOT WIDGET
# ------------------------------------------------------------------------------

class ScatterPlotWidget(_MplWidgetBase):
    """2D scatter plot of frame metrics with click-to-select."""
    frame_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("Load statistics to see scatter plot", parent)
        self._frame_indices: list[int] = []
        self._scatter_coords: list[tuple[float, float]] = []
        self._x_range: tuple[float, float] = (0.0, 1.0)
        self._y_range: tuple[float, float] = (0.0, 1.0)
        self._current_marker = None  # matplotlib artist for current frame star
        self._ax = None  # axes reference for lightweight updates
        self._frame_to_coord: dict[int, tuple[float, float]] = {}  # frame_idx → (x, y)
        self._excluded_set: set[int] = set()  # to skip yellow-star on excluded frames
        # P2 (v1.2.8 audit-4): keep refs to the incl/excl PathCollection
        # artists so update_excluded() can just set_offsets() instead of
        # tearing down + rebuilding the Figure on every mark refresh.
        self._incl_scatter = None
        self._excl_scatter = None
        # Snapshot of the settings used on last full render. Fast path
        # requires same metrics; a metric change falls back to render().
        self._last_x_metric: str | None = None
        self._last_y_metric: str | None = None
        # Keep a ref to frame_stats so fast-path update can re-partition
        # on a fresh excluded set without re-fetching from caller.
        self._frame_stats_ref: FrameStatistics | None = None

    def render(self, frame_stats: FrameStatistics, marker: FrameMarker,
               x_metric: str = "fwhm", y_metric: str = "roundness",
               current_frame: int = 0) -> None:
        if not self._mpl_available:
            return

        fig = self._Figure(figsize=(8, 6), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")

        excluded = marker.get_excluded_indices()
        self._excluded_set = set(excluded)
        rows = frame_stats.get_all_rows()

        incl_x, incl_y, incl_idx = [], [], []
        excl_x, excl_y = [], []
        cur_x, cur_y = None, None
        # Build frame→coord map in the same pass — previously this was a
        # second full iteration of `rows` after the scatter lists were built.
        frame_to_coord: dict[int, tuple[float, float]] = {}

        for row in rows:
            xv = row.get(x_metric, 0)
            yv = row.get(y_metric, 0)
            if xv <= 0 or yv <= 0:
                continue
            idx = row["frame_idx"]
            frame_to_coord[idx] = (xv, yv)
            if idx == current_frame:
                cur_x, cur_y = xv, yv
            if idx in excluded:
                excl_x.append(xv)
                excl_y.append(yv)
            else:
                incl_x.append(xv)
                incl_y.append(yv)
                incl_idx.append(idx)

        self._frame_indices = incl_idx
        self._scatter_coords = list(zip(incl_x, incl_y))
        self._frame_to_coord = frame_to_coord
        # Store axis ranges for normalized click detection
        all_x = incl_x + excl_x
        all_y = incl_y + excl_y
        self._x_range = (min(all_x), max(all_x)) if all_x else (0.0, 1.0)
        self._y_range = (min(all_y), max(all_y)) if all_y else (0.0, 1.0)

        # P2: keep refs so update_excluded() can set_offsets() without
        # a full Figure rebuild. Always create both artists (hide if empty)
        # so the fast path never has to materialize one mid-session.
        self._incl_scatter = ax.scatter(
            incl_x if incl_x else [0], incl_y if incl_y else [0],
            color="#55cc55", s=30, alpha=0.8, label="Good", zorder=3,
        )
        if not incl_x:
            self._incl_scatter.set_visible(False)
        self._excl_scatter = ax.scatter(
            excl_x if excl_x else [0], excl_y if excl_y else [0],
            color="#dd4444", s=30, alpha=0.7, marker="x", label="Bad", zorder=2,
        )
        if not excl_x:
            self._excl_scatter.set_visible(False)
        self._last_x_metric = x_metric
        self._last_y_metric = y_metric
        self._frame_stats_ref = frame_stats

        # Plot current frame marker — yellow star always on top of Good (green)
        # and Bad (red) points.
        self._current_marker = None
        if cur_x is not None:
            self._current_marker = ax.scatter(
                [cur_x], [cur_y], color="#ffd700", s=200, marker="*",
                edgecolors="#000000", linewidths=1.4, label="Current", zorder=10)

        self._ax = ax

        labels = {"fwhm": "FWHM", "roundness": "Roundness", "background": "Background",
                  "stars": "Stars", "weight": "Weight", "median": "Median", "sigma": "Sigma"}
        ax.set_xlabel(labels.get(x_metric, x_metric), color="#cccccc", fontsize=10)
        ax.set_ylabel(labels.get(y_metric, y_metric), color="#cccccc", fontsize=10)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#555555")
        handles, lbls = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="best", fontsize=8, facecolor="#2b2b2b", edgecolor="#555",
                      labelcolor="#cccccc")

        fig.tight_layout()
        self._replace_canvas(fig)

        # Connect click event
        if self._canvas is not None:
            self._canvas.mpl_connect("button_press_event", self._on_click)

    def update_current_marker(self, frame_index: int) -> None:
        """Lightweight update: move the current-frame star marker without full re-render.

        Uses PathCollection.set_offsets() on the existing marker rather than
        removing and re-creating the scatter artist — avoids matplotlib's
        collection-construction overhead on every frame change.
        """
        if self._ax is None or self._canvas is None:
            return
        coord = self._frame_to_coord.get(frame_index)
        if coord is None:
            # Frame has no scatter point (e.g., missing stats) — hide the marker.
            if self._current_marker is not None:
                self._current_marker.set_visible(False)
        else:
            if self._current_marker is None:
                # First time — create the artist.
                self._current_marker = self._ax.scatter(
                    [coord[0]], [coord[1]], color="#ffd700", s=200, marker="*",
                    edgecolors="#000000", linewidths=1.4, zorder=10)
            else:
                self._current_marker.set_offsets([coord])
                self._current_marker.set_visible(True)
        try:
            self._canvas.draw_idle()
        except Exception:
            pass

    def update_excluded(self, marker: FrameMarker, current_frame: int) -> bool:
        """P2 (v1.2.8 audit-4): fast path that repartitions Good/Bad
        offsets on the existing matplotlib artists without rebuilding
        the Figure. Returns True on success; False if a full render()
        is still needed (first call, missing artists, metric change).
        Cuts post-mark refresh from ~100 ms to ~10 ms on N=2000.
        """
        if (self._incl_scatter is None or self._excl_scatter is None
                or self._ax is None or self._canvas is None
                or self._frame_stats_ref is None
                or self._last_x_metric is None or self._last_y_metric is None):
            return False

        x_metric = self._last_x_metric
        y_metric = self._last_y_metric
        excluded = marker.get_excluded_indices()
        self._excluded_set = set(excluded)
        rows = self._frame_stats_ref.get_all_rows()

        incl_coords: list[tuple[float, float]] = []
        incl_idx: list[int] = []
        excl_coords: list[tuple[float, float]] = []
        frame_to_coord: dict[int, tuple[float, float]] = {}
        cur_coord: tuple[float, float] | None = None

        for row in rows:
            xv = row.get(x_metric, 0)
            yv = row.get(y_metric, 0)
            if xv <= 0 or yv <= 0:
                continue
            idx = row["frame_idx"]
            frame_to_coord[idx] = (xv, yv)
            if idx == current_frame:
                cur_coord = (xv, yv)
            if idx in self._excluded_set:
                excl_coords.append((xv, yv))
            else:
                incl_coords.append((xv, yv))
                incl_idx.append(idx)

        self._frame_indices = incl_idx
        self._scatter_coords = incl_coords
        self._frame_to_coord = frame_to_coord

        # set_offsets on PathCollection: matplotlib accepts an (N, 2) array
        # or list of (x, y) pairs. Empty set_offsets is legal; we hide the
        # artist to keep the legend tidy.
        if incl_coords:
            self._incl_scatter.set_offsets(incl_coords)
            self._incl_scatter.set_visible(True)
        else:
            self._incl_scatter.set_visible(False)
        if excl_coords:
            self._excl_scatter.set_offsets(excl_coords)
            self._excl_scatter.set_visible(True)
        else:
            self._excl_scatter.set_visible(False)

        # Re-position the current-frame yellow star (cheap — reuses the
        # existing update_current_marker path).
        if cur_coord is not None and self._current_marker is not None:
            self._current_marker.set_offsets([cur_coord])
            self._current_marker.set_visible(True)
        elif self._current_marker is not None:
            self._current_marker.set_visible(False)

        try:
            self._canvas.draw_idle()
        except Exception:
            return False
        return True

    def _on_click(self, event) -> None:
        """Find nearest scatter point using axis-normalized distance."""
        if event.inaxes is None or not self._scatter_coords:
            return
        mx, my = event.xdata, event.ydata
        x_min, x_max = self._x_range
        y_min, y_max = self._y_range
        x_span = max(x_max - x_min, 1e-10)
        y_span = max(y_max - y_min, 1e-10)

        min_dist = float("inf")
        best_idx = -1
        for i, (sx, sy) in enumerate(self._scatter_coords):
            # Normalize both axes to [0, 1] so neither dominates distance
            dx = (sx - mx) / x_span
            dy = (sy - my) / y_span
            d = dx * dx + dy * dy
            if d < min_dist:
                min_dist = d
                best_idx = i
        if 0 <= best_idx < len(self._frame_indices):
            self.frame_clicked.emit(self._frame_indices[best_idx])


# ------------------------------------------------------------------------------
# APPROVAL EXPRESSION WIDGET
# ------------------------------------------------------------------------------

class ApprovalExpressionWidget(QWidget):
    """Multi-criteria approval expression filter with AND logic."""
    reject_frames = pyqtSignal(list)

    METRICS = {"FWHM": "fwhm", "Roundness": "roundness", "Background": "background",
               "Stars": "stars", "Weight": "weight", "Median": "median", "Sigma": "sigma"}
    OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
           ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats: FrameStatistics | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel("Expression (all conditions must match):")
        lbl.setStyleSheet("font-size: 8pt; color: #999;")
        layout.addWidget(lbl)

        # Condition rows
        self._conditions: list[tuple[QComboBox, QComboBox, QDoubleSpinBox]] = []
        self._cond_layout = QVBoxLayout()
        layout.addLayout(self._cond_layout)

        self._add_condition_row()

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Condition")
        btn_add.setStyleSheet("padding: 3px; font-size: 8pt;")
        _nofocus(btn_add)
        btn_add.clicked.connect(self._add_condition_row)
        btn_row.addWidget(btn_add)

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet("padding: 3px; font-size: 8pt;")
        _nofocus(btn_clear)
        btn_clear.clicked.connect(self._clear_conditions)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setStyleSheet("color: #aaaa55; font-size: 8pt;")
        layout.addWidget(self.lbl_preview)

        self.btn_reject = QPushButton("Reject Non-Matching")
        self.btn_reject.setObjectName("ExcludeButton")
        self.btn_reject.setToolTip("Reject all frames that do NOT satisfy ALL conditions")
        _nofocus(self.btn_reject)
        self.btn_reject.clicked.connect(self._apply_expression)
        layout.addWidget(self.btn_reject)

    def _add_condition_row(self) -> None:
        row = QHBoxLayout()
        combo_metric = QComboBox()
        combo_metric.addItems(list(self.METRICS.keys()))
        combo_metric.setFixedWidth(100)
        _nofocus(combo_metric)
        row.addWidget(combo_metric)

        combo_op = QComboBox()
        combo_op.addItems(list(self.OPS.keys()))
        combo_op.setFixedWidth(45)
        _nofocus(combo_op)
        row.addWidget(combo_op)

        spin = QDoubleSpinBox()
        spin.setRange(0, 999999)
        spin.setDecimals(3)
        spin.setValue(0)
        spin.setFixedWidth(80)
        _nofocus(spin)
        row.addWidget(spin)

        self._conditions.append((combo_metric, combo_op, spin))
        self._cond_layout.addLayout(row)

        # Connect for live preview
        combo_metric.currentIndexChanged.connect(self._update_preview)
        combo_op.currentIndexChanged.connect(self._update_preview)
        spin.valueChanged.connect(self._update_preview)

    def _clear_conditions(self) -> None:
        # M2 (v1.2.8 audit-4): disconnect the preview signals before
        # deleteLater so no handler can fire on a residual signal
        # between takeAt() and the next GC cycle. Previous version
        # just deleteLater'd the widgets and dropped Python refs,
        # leaving currentIndexChanged / valueChanged connections
        # technically live until Qt reparented them.
        for combo_m, combo_o, spin in self._conditions:
            try:
                combo_m.currentIndexChanged.disconnect(self._update_preview)
            except (TypeError, RuntimeError):
                pass
            try:
                combo_o.currentIndexChanged.disconnect(self._update_preview)
            except (TypeError, RuntimeError):
                pass
            try:
                spin.valueChanged.disconnect(self._update_preview)
            except (TypeError, RuntimeError):
                pass
            combo_m.deleteLater()
            combo_o.deleteLater()
            spin.deleteLater()
        self._conditions.clear()
        # Clear layout items (the per-row QHBoxLayouts themselves; their
        # child widgets are already queued for deletion above).
        while self._cond_layout.count():
            child = self._cond_layout.takeAt(0)
            child_layout = child.layout() if child is not None else None
            if child_layout is not None:
                # Drain any remaining items (safety net for widgets that
                # weren't tracked in _conditions — shouldn't happen, but
                # keeps the original defensive behavior).
                while child_layout.count():
                    sub = child_layout.takeAt(0)
                    w = sub.widget() if sub is not None else None
                    if w is not None:
                        w.deleteLater()
        self._add_condition_row()
        self._update_preview()

    def set_statistics(self, frame_stats: FrameStatistics) -> None:
        self._stats = frame_stats
        self._update_preview()

    def _get_non_matching(self) -> list[int]:
        """Return frame indices that do NOT match ALL conditions."""
        if self._stats is None:
            return []
        non_matching = []
        for row in self._stats.get_all_rows():
            passes_all = True
            for combo_metric, combo_op, spin in self._conditions:
                key = self.METRICS.get(combo_metric.currentText(), "fwhm")
                op_fn = self.OPS.get(combo_op.currentText(), lambda a, b: a > b)
                val = spin.value()
                frame_val = row.get(key, 0)
                if frame_val <= 0 or val <= 0:
                    continue  # Skip conditions with no data
                if not op_fn(frame_val, val):
                    passes_all = False
                    break
            if not passes_all:
                non_matching.append(row["frame_idx"])
        return non_matching

    def _update_preview(self) -> None:
        non_matching = self._get_non_matching()
        if non_matching:
            self.lbl_preview.setText(f"{len(non_matching)} frame(s) would be rejected")
        else:
            self.lbl_preview.setText("All frames pass the expression")

    def _apply_expression(self) -> None:
        non_matching = self._get_non_matching()
        if non_matching:
            self.reject_frames.emit(non_matching)


# ------------------------------------------------------------------------------
# STATISTICS GRAPH WIDGET
# ------------------------------------------------------------------------------

class StatisticsGraphWidget(_MplWidgetBase):
    """Line chart of frame statistics over time."""

    def __init__(self, parent=None):
        super().__init__("Load statistics to see graph", parent)
        self._vline = None
        # P1 (v1.2.8 audit-4): signature of the last render's inputs. If a
        # subsequent render() call has identical inputs (same excluded set,
        # same metric visibility, same data revision), we skip the full
        # matplotlib Figure rebuild — a ~30-100 ms savings per call on
        # long sequences that _run_post_mark_refresh hits after every
        # mark.
        self._last_render_sig: tuple | None = None

    def render(self, frame_stats: FrameStatistics, marker: FrameMarker,
               current_frame: int,
               show_fwhm: bool = True, show_bg: bool = True,
               show_roundness: bool = False,
               show_running_avg: bool = True) -> None:
        if not self._mpl_available:
            return

        # P1: cheap dedupe. Build a signature that captures everything the
        # Figure depends on (except current_frame, which is handled by the
        # lightweight update_current_line path). If unchanged, don't rebuild.
        excluded_key = frozenset(marker.get_excluded_indices())
        # M1 (v1.2.8 audit-5): use the monotonic data_revision counter instead
        # of id(frame_stats.data). CPython reuses object ids after GC, so a
        # full reload that happens to recycle the list address would produce
        # a false cache hit and leave a stale figure on screen.
        data_rev = frame_stats.data_revision
        sig = (excluded_key, show_fwhm, show_bg, show_roundness,
               show_running_avg, data_rev, frame_stats.total)
        if sig == self._last_render_sig:
            # Still update the current-frame vline in case that moved.
            self.update_current_line(current_frame)
            return
        self._last_render_sig = sig

        fig = self._Figure(figsize=(10, 4), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")

        x = list(range(1, frame_stats.total + 1))
        excluded = marker.get_excluded_indices()

        # Partition indices once for all metrics instead of re-running the
        # "i in excluded" test inside three separate 2N-comprehension bursts
        # per metric. excluded is a set (O(1) membership) but the Python
        # overhead of re-iterating range(N) N×(metrics) × 2 (x/y) was still
        # meaningful on long sequences. Computed once here.
        n = len(x)
        incl_indices = [i for i in range(n) if i not in excluded]
        excl_indices = [i for i in range(n) if i in excluded]

        def _moving_avg(xvals, yvals, window=7):
            """Compute moving average for smooth trend line."""
            if len(yvals) < window:
                return xvals, yvals
            ya = np.array(yvals, dtype=np.float64)
            kernel = np.ones(window) / window
            smooth = np.convolve(ya, kernel, mode='valid')
            offset = window // 2
            return xvals[offset:offset + len(smooth)], smooth.tolist()

        if show_fwhm:
            # L1 (v1.2.8 audit-5): numpy-cached column; indexing is
            # identical to the list version but subsequent renders skip
            # the list rebuild. incl_y/excl_y are built via list comp
            # (matplotlib accepts both), so the only saving is the
            # column fetch itself — negligible per call but multiplied
            # by three metrics × every mark refresh on long sequences.
            fwhm = frame_stats.get_column_np("fwhm")
            incl_x = [x[i] for i in incl_indices if fwhm[i] > 0]
            incl_y = [fwhm[i] for i in incl_indices if fwhm[i] > 0]
            excl_x = [x[i] for i in excl_indices if fwhm[i] > 0]
            excl_y = [fwhm[i] for i in excl_indices if fwhm[i] > 0]
            if incl_x:
                ax.plot(incl_x, incl_y, color="#88aaff", linewidth=1.0, label="FWHM", alpha=0.5)
                if show_running_avg and len(incl_y) >= 7:
                    avg_x, avg_y = _moving_avg(incl_x, incl_y)
                    ax.plot(avg_x, avg_y, color="#88aaff", linewidth=2.5, alpha=0.9, label="FWHM avg")
            if excl_x:
                ax.scatter(excl_x, excl_y, color="#dd4444", s=20, zorder=5, label="Excluded")

        if show_bg:
            bg = frame_stats.get_column_np("background")
            ax2 = ax.twinx()
            ax2.set_facecolor("#1e1e1e")
            incl_x = [x[i] for i in incl_indices if bg[i] > 0]
            incl_y = [bg[i] for i in incl_indices if bg[i] > 0]
            if incl_x:
                ax2.plot(incl_x, incl_y, color="#ffaa55", linewidth=1.5, label="Background", alpha=0.8)
            ax2.tick_params(colors="#aaaaaa", labelsize=8)
            ax2.set_ylabel("Background", color="#ffaa55", fontsize=9)
            for spine in ax2.spines.values():
                spine.set_edgecolor("#555555")

        if show_roundness:
            rnd = frame_stats.get_column_np("roundness")
            incl_x = [x[i] for i in incl_indices if rnd[i] > 0]
            incl_y = [rnd[i] for i in incl_indices if rnd[i] > 0]
            if incl_x:
                ax.plot(incl_x, incl_y, color="#55dd55", linewidth=1.5, label="Roundness",
                        alpha=0.7, linestyle="--")

        # Current frame indicator
        self._vline = ax.axvline(x=current_frame + 1, color="#ffffff", linestyle="--",
                                  alpha=0.6, linewidth=1)

        ax.set_xlabel("Frame", color="#cccccc", fontsize=9)
        ax.set_ylabel("FWHM", color="#88aaff", fontsize=9)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#555555")
        # Only show legend if there are labeled artists
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="upper left", fontsize=8, facecolor="#2b2b2b", edgecolor="#555",
                      labelcolor="#cccccc")

        fig.tight_layout()
        self._replace_canvas(fig)

    def update_current_line(self, index: int) -> None:
        if self._vline is not None and self._fig is not None:
            self._vline.set_xdata([index + 1, index + 1])
            if self._canvas is not None:
                self._canvas.draw_idle()


# ------------------------------------------------------------------------------
# BATCH REJECT WIDGET
# ------------------------------------------------------------------------------

class BatchRejectWidget(QWidget):
    """UI for threshold-based batch frame rejection."""
    reject_frames = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats: FrameStatistics | None = None
        self._marker: FrameMarker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Threshold row
        thresh_row = QHBoxLayout()
        self.combo_metric = QComboBox()
        self.combo_metric.addItems(["FWHM", "Background", "Roundness"])
        _nofocus(self.combo_metric)
        thresh_row.addWidget(self.combo_metric)

        self.combo_op = QComboBox()
        self.combo_op.addItems([">", "<", ">=", "<="])
        self.combo_op.setFixedWidth(50)
        _nofocus(self.combo_op)
        thresh_row.addWidget(self.combo_op)

        self.spin_value = QDoubleSpinBox()
        self.spin_value.setRange(0, 999999)
        self.spin_value.setDecimals(3)
        self.spin_value.setValue(5.0)
        self.spin_value.setFixedWidth(90)
        _nofocus(self.spin_value)
        thresh_row.addWidget(self.spin_value)
        layout.addLayout(thresh_row)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setStyleSheet("color: #aaaa55; font-size: 8pt;")
        layout.addWidget(self.lbl_preview)

        self.btn_apply_filter = QPushButton("Reject Matching")
        self.btn_apply_filter.setObjectName("ExcludeButton")
        _nofocus(self.btn_apply_filter)
        self.btn_apply_filter.clicked.connect(self._apply_filter)
        layout.addWidget(self.btn_apply_filter)

        # Worst N%
        worst_row = QHBoxLayout()
        worst_row.addWidget(QLabel("Reject worst"))
        self.spin_worst_pct = QSpinBox()
        self.spin_worst_pct.setRange(1, 50)
        self.spin_worst_pct.setValue(10)
        self.spin_worst_pct.setSuffix("%")
        self.spin_worst_pct.setFixedWidth(70)
        _nofocus(self.spin_worst_pct)
        worst_row.addWidget(self.spin_worst_pct)
        worst_row.addWidget(QLabel("by"))
        self.combo_worst_metric = QComboBox()
        self.combo_worst_metric.addItems(["FWHM", "Background", "Roundness"])
        _nofocus(self.combo_worst_metric)
        worst_row.addWidget(self.combo_worst_metric)
        layout.addLayout(worst_row)

        self.btn_reject_worst = QPushButton("Reject Worst N%")
        self.btn_reject_worst.setObjectName("ExcludeButton")
        _nofocus(self.btn_reject_worst)
        self.btn_reject_worst.clicked.connect(self._reject_worst_pct)
        layout.addWidget(self.btn_reject_worst)

        # Connect preview updates
        self.combo_metric.currentIndexChanged.connect(self._update_preview)
        self.combo_op.currentIndexChanged.connect(self._update_preview)
        self.spin_value.valueChanged.connect(self._update_preview)

    def set_statistics(self, frame_stats: FrameStatistics, marker: FrameMarker) -> None:
        self._stats = frame_stats
        self._marker = marker
        self._update_preview()

    def _get_metric_key(self, combo: QComboBox) -> str:
        text = combo.currentText().lower()
        return {"fwhm": "fwhm", "background": "background", "roundness": "roundness"}.get(text, "fwhm")

    def _get_matching_indices(self) -> list[int]:
        if self._stats is None:
            return []
        key = self._get_metric_key(self.combo_metric)
        op = self.combo_op.currentText()
        val = self.spin_value.value()
        indices = []
        for row in self._stats.get_all_rows():
            v = row.get(key, 0)
            if v <= 0:
                continue
            match = False
            if op == ">" and v > val:
                match = True
            elif op == "<" and v < val:
                match = True
            elif op == ">=" and v >= val:
                match = True
            elif op == "<=" and v <= val:
                match = True
            if match:
                indices.append(row["frame_idx"])
        return indices

    def _update_preview(self) -> None:
        indices = self._get_matching_indices()
        if indices:
            self.lbl_preview.setText(f"{len(indices)} frame(s) match this filter")
        else:
            self.lbl_preview.setText("No frames match")

    def _apply_filter(self) -> None:
        indices = self._get_matching_indices()
        if indices:
            self.reject_frames.emit(indices)

    def _reject_worst_pct(self) -> None:
        if self._stats is None:
            return
        key = self._get_metric_key(self.combo_worst_metric)
        pct = self.spin_worst_pct.value()
        values = self._stats.get_column(key)
        # Build (value, frame_idx) pairs with valid values
        valid = [(values[i], i) for i in range(len(values)) if values[i] > 0]
        if not valid:
            return
        # Sort: for FWHM and Background, worst = highest. For roundness, worst = lowest
        if key == "roundness":
            valid.sort(key=lambda x: x[0])  # lowest roundness = worst
        else:
            valid.sort(key=lambda x: x[0], reverse=True)  # highest FWHM/BG = worst
        n_reject = max(1, int(len(valid) * pct / 100))
        indices = [idx for _, idx in valid[:n_reject]]
        if indices:
            self.reject_frames.emit(indices)


# ------------------------------------------------------------------------------
# COLOR-CODED FRAME SLIDER
# ------------------------------------------------------------------------------

class ColorCodedSlider(QSlider):
    """QSlider subclass that paints red tick marks at excluded frame positions.

    Inherits all QSlider behavior; the only addition is a custom paintEvent
    overlay that draws markers after the standard slider rendering.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._excluded: set[int] = set()
        self._total: int = 1
        # Rasterized overlay of all excluded-frame ticks. Rebuilt only when
        # the exclusion set or widget geometry changes; paintEvent then blits
        # it with a single drawPixmap instead of iterating the whole excluded
        # set (can be hundreds of drawRect calls per repaint on long seqs).
        self._tick_pixmap: QPixmap | None = None

    def set_exclusions(self, excluded_indices: set[int], total: int) -> None:
        self._excluded = excluded_indices
        self._total = max(1, total)
        self._tick_pixmap = None  # invalidate cache
        self.update()

    def resizeEvent(self, event) -> None:
        self._tick_pixmap = None  # geometry-dependent cache must rebuild
        super().resizeEvent(event)

    def _build_tick_pixmap(self) -> QPixmap:
        pm = QPixmap(self.size())
        pm.fill(Qt.GlobalColor.transparent)
        if not self._excluded or self._total <= 1:
            return pm
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        groove_x = SLIDER_HANDLE_MARGIN
        groove_w = self.width() - SLIDER_HANDLE_MARGIN * 2
        groove_y = self.height() - 4
        tick_h = 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#dd4444"))
        denom = self._total - 1
        for idx in self._excluded:
            x = groove_x + int(idx / denom * groove_w)
            painter.drawRect(x - 1, groove_y, 3, tick_h)
        painter.end()
        return pm

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._excluded or self._total <= 1:
            return
        if self._tick_pixmap is None or self._tick_pixmap.size() != self.size():
            self._tick_pixmap = self._build_tick_pixmap()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._tick_pixmap)
        painter.end()


# ------------------------------------------------------------------------------
# THUMBNAIL FILMSTRIP
# ------------------------------------------------------------------------------

_THUMB_STYLE_INCLUDED = "background-color:#1a1a1a;border:2px solid #55aa55;"
_THUMB_STYLE_EXCLUDED = "background-color:#1a1a1a;border:2px solid #dd4444;"
_THUMB_STYLE_CURRENT = "background-color:#1a1a1a;border:2px solid #88aaff;"


class ThumbnailFilmstrip(QWidget):
    """Horizontal scrollable strip of frame thumbnails with color-coded borders.

    Creates one QLabel per frame upfront (lightweight). Thumbnails are loaded
    lazily via set_thumbnail() as the user scrolls. Borders indicate:
    green = included, red = excluded, blue = current frame.
    """
    frame_selected = pyqtSignal(int)

    def __init__(self, total_frames: int, marker: FrameMarker = None, parent=None):
        super().__init__(parent)
        self.total_frames = total_frames
        self._marker = marker
        self.setFixedHeight(THUMBNAIL_HEIGHT + 20)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(False)
        self.scroll.setFixedHeight(THUMBNAIL_HEIGHT + 20)

        self._container = QWidget()
        self._hlayout = QHBoxLayout(self._container)
        self._hlayout.setContentsMargins(2, 2, 2, 2)
        self._hlayout.setSpacing(2)

        self._labels: list[QLabel] = []
        self._current = -1
        # Tracks each label's last-applied style key so we can skip
        # redundant setStyleSheet() calls. Qt re-parses the full stylesheet
        # and invalidates layout/paint state on every setStyleSheet, so this
        # guard is a big win during playback (every frame advance touches 2
        # labels — same call repeated for identical state previously).
        self._label_states: list[str] = ["init"] * total_frames

        for i in range(total_frames):
            lbl = QLabel()
            lbl.setFixedSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"background-color:#1a1a1a;border:2px solid #55aa55;"
                f"font-size:7pt;color:#666;"
            )
            lbl.setText(str(i + 1))
            lbl.setProperty("frame_idx", i)
            lbl.mousePressEvent = lambda event, idx=i: self.frame_selected.emit(idx)
            self._labels.append(lbl)
            self._hlayout.addWidget(lbl)

        self.scroll.setWidget(self._container)
        layout.addWidget(self.scroll)

    def set_thumbnail(self, index: int, pixmap: QPixmap) -> None:
        if 0 <= index < len(self._labels):
            # Fast nearest-neighbor scaling for the filmstrip: 76x56 px final
            # size makes bilinear filtering invisible while being noticeably
            # cheaper per thumbnail assignment during scroll/preload.
            self._labels[index].setPixmap(pixmap.scaled(
                THUMBNAIL_WIDTH - 4, THUMBNAIL_HEIGHT - 4,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ))

    def _apply_style(self, index: int, state: str, style: str) -> None:
        """Apply ``style`` to label ``index`` only if its state has changed.

        Qt's setStyleSheet() forces a full CSS re-parse, selector-matching
        pass, and repaint. For identical state it still does all the work.
        We tag each label with a short state key (``'cur'`` / ``'inc'`` /
        ``'exc'``) and skip the call when it would be a no-op.
        """
        if not (0 <= index < len(self._labels)):
            return
        if self._label_states[index] == state:
            return
        self._labels[index].setStyleSheet(style)
        self._label_states[index] = state

    def highlight_current(self, index: int) -> None:
        if index == self._current:
            return  # No-op: same frame highlighted twice (common during scrubbing)
        if 0 <= self._current < len(self._labels):
            # Restore previous frame border based on include/exclude status
            if self._marker is not None and not self._marker.is_included(self._current):
                self._apply_style(self._current, "exc", _THUMB_STYLE_EXCLUDED)
            else:
                self._apply_style(self._current, "inc", _THUMB_STYLE_INCLUDED)
        self._current = index
        if 0 <= index < len(self._labels):
            self._apply_style(index, "cur", _THUMB_STYLE_CURRENT)
            # Skip ensureWidgetVisible when the label is already fully visible.
            # The call is cheap-looking but internally runs layout/geometry
            # math and can trigger a scroll-area relayout even when it ends
            # up a no-op — adds measurable jitter during playback scrubbing
            # where the current label is almost always already on screen.
            lbl = self._labels[index]
            vp = self.scroll.viewport()
            hsb = self.scroll.horizontalScrollBar()
            visible_rect = vp.rect().translated(hsb.value(), 0)
            if not visible_rect.contains(lbl.geometry()):
                self.scroll.ensureWidgetVisible(lbl, 50, 0)

    def update_border(self, index: int, included: bool) -> None:
        if 0 <= index < len(self._labels):
            if index == self._current:
                self._apply_style(index, "cur", _THUMB_STYLE_CURRENT)
            elif included:
                self._apply_style(index, "inc", _THUMB_STYLE_INCLUDED)
            else:
                self._apply_style(index, "exc", _THUMB_STYLE_EXCLUDED)

    def get_visible_range(self) -> tuple[int, int]:
        """Return (start, end) indices of visible thumbnails."""
        sb = self.scroll.horizontalScrollBar()
        pos = sb.value()
        visible_w = self.scroll.viewport().width()
        item_w = THUMBNAIL_WIDTH + 4  # including spacing
        start = max(0, pos // item_w)
        end = min(self.total_frames, (pos + visible_w) // item_w + 2)
        return start, end


# ------------------------------------------------------------------------------
# ZOOMABLE IMAGE WIDGET
# ------------------------------------------------------------------------------

class ImageCanvas(QWidget):
    """Widget that displays a QImage with zoom, pan, and side-by-side."""
    zoom_changed = pyqtSignal(float)
    resized = pyqtSignal(int, int)  # (width, height) — debounced by caller

    # Pre-allocated colors to avoid per-frame QColor construction from strings
    _CLR_BG = QColor(26, 26, 26)
    _CLR_GRAY = QColor(100, 100, 100)
    _CLR_ACCENT = QColor(136, 170, 255)       # #88aaff
    _CLR_OVERLAY_BG = QColor(0, 0, 0, 180)
    _CLR_OVERLAY_FG = QColor(224, 224, 224)    # #e0e0e0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap: QPixmap | None = None
        self._pixmap_right: QPixmap | None = None  # For side-by-side
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._dragging: bool = False
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._drag_pan_start_x: float = 0.0
        self._drag_pan_start_y: float = 0.0

        # Side-by-side mode
        self._side_by_side: bool = False

        # Frame info overlay
        self._overlay_text: str = ""
        self._show_overlay: bool = True

        self.setStyleSheet("background-color: #1a1a1a;")

    def resizeEvent(self, event) -> None:
        # Emit the current geometry so owners (main window) can re-size
        # the frame cache to match. Fires many times during an interactive
        # drag; the listener debounces.
        super().resizeEvent(event)
        self.resized.emit(self.width(), self.height())

    def grab_composite(self) -> QPixmap | None:
        """Return a QPixmap of the whole canvas exactly as it's drawn — so
        clipboard copies match what the user sees (side-by-side composite,
        overlay, zoom, pan). Previously callers reached into the private
        `_pixmap` and got only the left-side raw frame in SBS mode.
        """
        if self._pixmap is None and self._pixmap_right is None:
            return None
        return self.grab()

    def set_image(self, qimg: QImage | None, defer_update: bool = False) -> None:
        if qimg is None:
            self._pixmap = None
        else:
            self._pixmap = QPixmap.fromImage(qimg)
        if not defer_update:
            self.update()

    def set_side_by_side_image(self, qimg: QImage | None, defer_update: bool = False) -> None:
        if qimg is None:
            self._pixmap_right = None
        else:
            self._pixmap_right = QPixmap.fromImage(qimg)
        if not defer_update:
            self.update()

    def set_side_by_side(self, enabled: bool, defer_update: bool = False) -> None:
        self._side_by_side = enabled
        if not defer_update:
            self.update()

    def set_overlay_text(self, text: str, defer_update: bool = False) -> None:
        self._overlay_text = text
        if not defer_update:
            self.update()

    def set_show_overlay(self, show: bool) -> None:
        self._show_overlay = show
        self.update()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()
        self.zoom_changed.emit(self._zoom)

    def _draw_pixmap(self, painter: QPainter, pixmap: QPixmap, offset_x: float = 0,
                     available_width: float | None = None) -> None:
        if available_width is None:
            available_width = self.width()
        pw = pixmap.width() * self._zoom
        ph = pixmap.height() * self._zoom
        x = offset_x + (available_width - pw) / 2 + self._pan_x
        y = (self.height() - ph) / 2 + self._pan_y
        target = QRectF(x, y, pw, ph)
        source = QRectF(0, 0, pixmap.width(), pixmap.height())
        painter.drawPixmap(target, pixmap, source)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self._CLR_BG)

        if self._pixmap is None:
            painter.setPen(self._CLR_GRAY)
            painter.setFont(QFont("Helvetica", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No frame loaded")
            painter.end()
            return

        if self._side_by_side and self._pixmap_right is not None:
            half_w = self.width() / 2
            self._draw_pixmap(painter, self._pixmap, 0, half_w)
            painter.setPen(QPen(self._CLR_ACCENT, 2))
            painter.drawLine(int(half_w), 0, int(half_w), self.height())
            self._draw_pixmap(painter, self._pixmap_right, half_w, half_w)
            painter.setPen(self._CLR_ACCENT)
            painter.setFont(QFont("Helvetica", 9))
            painter.drawText(10, 20, "Current")
            painter.drawText(int(half_w) + 10, 20, "Reference")
        else:
            self._draw_pixmap(painter, self._pixmap)

        # Frame info overlay
        if self._show_overlay and self._overlay_text and self._pixmap is not None:
            painter.setOpacity(0.85)
            font = QFont("Helvetica", 11, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            lines = self._overlay_text.split("\n")
            line_h = fm.height()
            box_w = max(fm.horizontalAdvance(ln) for ln in lines) + 16
            box_h = line_h * len(lines) + 12
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._CLR_OVERLAY_BG)
            painter.drawRoundedRect(8, 8, box_w, box_h, 4, 4)
            painter.setPen(self._CLR_OVERLAY_FG)
            for i, ln in enumerate(lines):
                painter.drawText(16, 20 + i * line_h, ln)
            painter.setOpacity(1.0)

        painter.end()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self._zoom * ZOOM_FACTOR, MAX_ZOOM)
        elif delta < 0:
            self._zoom = max(self._zoom / ZOOM_FACTOR, MIN_ZOOM)
        self.update()
        self.zoom_changed.emit(self._zoom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._dragging = True
            self._drag_start_x = event.position().x()
            self._drag_start_y = event.position().y()
            self._drag_pan_start_x = self._pan_x
            self._drag_pan_start_y = self._pan_y

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            dx = event.position().x() - self._drag_start_x
            dy = event.position().y() - self._drag_start_y
            self._pan_x = self._drag_pan_start_x + dx
            self._pan_y = self._drag_pan_start_y + dy
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._dragging = False


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class BlinkComparatorWindow(QMainWindow):
    """
    Main window for the Blink Comparator.

    Left panel: playback controls, display mode, frame marking, batch selection.
    Right panel: tabbed (viewer, statistics table, statistics graph) + filmstrip.
    """

    def __init__(self, siril_iface=None, folder_mode_path: str = ""):
        super().__init__()
        if not folder_mode_path:
            raise ValueError("folder_mode_path is required — folder mode is the only mode.")
        self.siril = siril_iface or s.SirilInterface()
        self._folder_mode_path: str = folder_mode_path

        if not self.siril.connected:
            self.siril.connect()

        if not self.siril.is_sequence_loaded():
            raise NoSequenceError("No sequence is currently loaded in Siril.")

        self.seq = self.siril.get_seq()
        if self.seq is None:
            raise NoSequenceError("No sequence is currently loaded in Siril.")

        self.total_frames = self.seq.number
        if self.total_frames < 1:
            raise NoSequenceError("The loaded sequence contains no frames.")

        self.current_frame: int = 0
        self.playing: bool = False
        self.fps: float = 3.0
        self.direction: int = 1

        self.marker = FrameMarker(self.seq)
        self.undo_stack = UndoStack()
        self.frame_stats: FrameStatistics | None = None
        self._frames_viewed: set[int] = set()
        self._pinned_frame: int | None = None  # For A/B toggle

        # HOTFIX (v1.2.8 audit-5+): initialize cache / thumb_cache to None
        # BEFORE _init_ui() so handlers like `_on_mode_changed` that can
        # fire during widget construction or settings restore (QButtonGroup
        # emits `idToggled` from its own QObject, independent of individual
        # button blockSignals) can safely guard with `if self.cache is not
        # None`. Previously these were assigned after _init_ui / _load_settings,
        # and a stray signal → _show_frame crashed with `AttributeError:
        # 'BlinkComparatorWindow' object has no attribute 'cache'`.
        self.cache: FrameCache | None = None
        self.thumb_cache: ThumbnailCache | None = None

        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self._init_ui()
        self._load_settings()
        self._setup_shortcuts()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        # Tracks the most recently submitted preload future. We only enqueue a
        # new preload when the previous one has finished — prevents the
        # ThreadPoolExecutor queue from growing unboundedly during fast playback
        # (every frame advance would otherwise submit another preload task that
        # contends with the main thread for Siril's single socket).
        self._preload_future = None

        # Coalesced post-mark UI refresh. _after_marking() schedules a single
        # deferred refresh (scatter plot + graph + slider-exclusions repaint)
        # instead of running them synchronously per mark. When the user rapidly
        # marks dozens of frames with auto-advance, this collapses N×3 UI
        # renders into 1, keeping the hotkeys snappy.
        self._post_mark_refresh_pending = False

        # Coalesced frame-info label update. Rapid slider scrubbing fires
        # _show_frame many times per second; the HTML label build + setText
        # is cheap per call but still drives a layout pass. Debouncing to
        # 50 ms means the label follows the slider with no perceptible lag
        # while collapsing a 20+-call burst into 1.
        self._pending_frame_info_index: int = -1
        self._frame_info_pending: bool = False

        # Canvas-resize debounce: ImageCanvas.resized fires many times per
        # second during an interactive drag. Coalesce into a single trailing
        # cache-resize + current-frame reload.
        self._canvas_resize_pending: bool = False
        self._pending_canvas_size: tuple[int, int] = (0, 0)

        # M3 (v1.2.8 audit-3): gates _apply_canvas_resize. Flipped True at
        # the tail of _deferred_init so resizes that fire during startup
        # (window show, splitter settle) don't race with cache population.
        self._ready_for_display: bool = False

        # Last filmstrip visible range we loaded thumbnails for. Used to skip
        # re-querying the thumbnail cache for frames that are already on
        # screen (huge win during horizontal scrolling of long sequences).
        self._prev_visible_range: tuple[int, int] | None = None

        QTimer.singleShot(100, self._deferred_init)

    def _deferred_init(self) -> None:
        canvas_w = max(400, self.canvas.width())
        canvas_h = max(300, self.canvas.height())

        # Seed the caches with whatever preset the user has selected in the
        # zoom-bar dropdown (restored from QSettings in _load_settings). The
        # currentTextChanged signal fires before _deferred_init runs, but the
        # handler bails because the caches don't exist yet — so we pick it up
        # here so the very first frame is rendered with the correct preset.
        current_preset = self.combo_autostretch.currentText()

        self.cache = FrameCache(
            self.siril, self.seq,
            max_frames=DEFAULT_CACHE_SIZE,
            display_width=canvas_w,
            display_height=canvas_h,
            stretch_preset=current_preset,
        )

        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Computing stretch parameters...")
        self.progress_bar.setValue(10)
        QApplication.processEvents()

        self.cache.compute_global_stretch()

        self.progress_bar.setFormat("Loading reference frame...")
        self.progress_bar.setValue(20)
        QApplication.processEvents()

        self.cache.load_reference_frame()

        # Load frame statistics
        self.progress_bar.setFormat("Loading frame statistics...")
        self.progress_bar.setValue(30)
        QApplication.processEvents()

        self.frame_stats = FrameStatistics(self.siril, self.seq)

        def stats_progress(i, total):
            pct = 30 + int(40 * i / max(1, total))
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Loading stats... frame {i + 1}/{total}")
            QApplication.processEvents()

        self.frame_stats.load_all(progress_callback=stats_progress)

        # Check if registration data (FWHM/stars) is available
        if not self.frame_stats.has_regdata:
            try:
                self.siril.log(
                    "[BlinkComparator] No star detection data found. "
                    "Background column uses median from stats. "
                    "FWHM/Stars/Roundness require running star detection."
                )
            except (SirilError, OSError, RuntimeError):
                pass
            self._show_no_regdata_banner()

        # Populate table and graph
        self.progress_bar.setFormat("Building statistics table...")
        self.progress_bar.setValue(75)
        QApplication.processEvents()

        self.stats_table.populate(self.frame_stats, self.marker)
        self.batch_widget.set_statistics(self.frame_stats, self.marker)
        self.approval_widget.set_statistics(self.frame_stats)

        self.progress_bar.setFormat("Rendering statistics graph...")
        self.progress_bar.setValue(80)
        QApplication.processEvents()

        self._refresh_statistics_graph()
        self._refresh_scatter_plot()
        self._precompute_overlay_stats()

        # Initialize thumbnail cache
        self.thumb_cache = ThumbnailCache(
            self.siril, self.seq,
            global_median=self.cache.global_median,
            global_mad=self.cache.global_mad,
            stretch_preset=current_preset,
            frame_cache=self.cache,
        )

        self.progress_bar.setFormat("Loading first frame...")
        self.progress_bar.setValue(90)
        QApplication.processEvents()

        self._show_frame(0)

        # Update slider exclusions
        self.frame_slider.set_exclusions(self.marker.get_excluded_indices(), self.total_frames)

        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Ready")
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

        self._start_preload(1, 10)

        # Start loading visible thumbnails
        QTimer.singleShot(500, self._load_visible_thumbnails)

        # M3 (v1.2.8 audit-3): now that the cache, stats, first frame and
        # preload have all been set up, the canvas-resize handler is safe
        # to touch the cache. Any resizes that fired before this point
        # were swallowed by the _ready_for_display gate.
        self._ready_for_display = True

        # Log startup
        try:
            nb_incl = sum(1 for i in range(self.total_frames) if self.marker.is_included(i))
            nb_excl = self.total_frames - nb_incl
            img_type = "RGB" if self.seq.nb_layers == 3 else "Mono"
            self.siril.log(
                f"[BlinkComparator] Sequence: {self.seq.seqname} "
                f"({self.total_frames} frames, {self.seq.rx}x{self.seq.ry}, {img_type})"
            )
            self.siril.log(f"[BlinkComparator] {nb_incl} included, {nb_excl} excluded")
        except (SirilError, OSError, RuntimeError):
            pass

    # ------------------------------------------------------------------
    # MISSING REGDATA HANDLING
    # ------------------------------------------------------------------

    def _show_no_regdata_banner(self) -> None:
        """Show a banner in the right panel offering to run star detection."""
        self._regdata_banner = QWidget()
        banner_layout = QHBoxLayout(self._regdata_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel(
            "\u26A0 No star detection data found. "
            "FWHM, Roundness, and Stars columns are empty. "
            "Background uses median from statistics."
        )
        lbl.setStyleSheet("color: #ffaa33; font-size: 9pt;")
        lbl.setWordWrap(True)
        banner_layout.addWidget(lbl, 1)

        btn = QPushButton("Run Star Detection")
        btn.setObjectName("ApplyButton")
        btn.setToolTip(
            "Runs Siril's 'register -2pass' to detect stars in all frames.\n"
            "This computes FWHM, roundness, and star count for each frame.\n"
            "May take a few minutes for large sequences."
        )
        _nofocus(btn)
        btn.clicked.connect(self._run_star_detection)
        banner_layout.addWidget(btn)

        # Insert banner at top of right panel (above tabs)
        right_layout = self.right_tabs.parent().layout()
        if right_layout is not None:
            right_layout.insertWidget(0, self._regdata_banner)

    def _run_star_detection(self) -> None:
        """Run register -2pass via Siril to compute FWHM/roundness/stars, then reload stats."""
        reply = QMessageBox.question(
            self, "Run Star Detection",
            "This will run Siril's 'register -2pass' to detect stars in all frames.\n"
            "This computes FWHM, roundness, background, and star count\n"
            "without creating new output files.\n\n"
            "It may take a few minutes for large sequences.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Running star detection (register -2pass)...")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        try:
            self.siril.log("[BlinkComparator] Running register -2pass for star detection...")
            # -2pass computes transforms (FWHM, roundness, stars) without generating output images.
            # Quote the seqname: sirilpy joins args into a single command line
            # and Siril's parser splits on unquoted whitespace. Folder mode
            # uses a safe hard-coded name today, but this defends against any
            # sequence whose name might contain spaces.
            self.siril.cmd("register", f'"{self.seq.seqname}"', "-2pass")
            self.siril.log("[BlinkComparator] Registration complete. Reloading statistics...")
        except Exception as e:
            QMessageBox.warning(self, "Star Detection Failed",
                                f"register -2pass failed:\n{e}\n\n"
                                f"Try running 'register {self.seq.seqname} -2pass' manually in the Siril console.")
            self.progress_bar.setVisible(False)
            return

        # Force Siril to reload the .seq file from disk (register -2pass writes
        # regdata to the .seq file but doesn't update the in-memory sequence)
        seqname = self.seq.seqname
        try:
            self.siril.log(f"[BlinkComparator] Reloading sequence '{seqname}' from disk...")
            self.siril.cmd("load_seq", f'"{seqname}"')
        except Exception as ex:
            self.siril.log(f"[BlinkComparator] WARNING: load_seq failed: {ex}")

        # Now get the refreshed sequence object
        try:
            self.seq = self.siril.get_seq()
            self.siril.log(f"[BlinkComparator] Sequence reloaded: {self.seq.seqname}, "
                           f"{self.seq.number} frames, layers={self.seq.nb_layers}")
        except Exception as ex:
            self.siril.log(f"[BlinkComparator] WARNING: get_seq() failed after register: {ex}")

        # H1 (v1.2.8 audit-4): rebind every consumer that cached the old seq
        # object. Without this, FrameCache.seq / ThumbnailCache.seq /
        # FrameMarker.seq continue to reference the pre-register sequence —
        # silently wrong counts, orientations, and reference_image after a
        # mid-session star-detection run. Also invalidate image caches and
        # reload reference_data because rx/ry/reference_image may have moved.
        if self.cache is not None:
            self.cache.seq = self.seq
            self.cache.invalidate()
            # M2 (v1.2.8 audit-5): stretch + reference reload each take a few
            # seconds on large mono rigs / slow disks. The rebind runs on the
            # main thread (must — the cache is not thread-safe against paint
            # events), so without progress feedback the window looks frozen.
            # Drive the progress bar through 30%→50% and pump the event loop
            # around each blocking call so the bar actually repaints.
            self.progress_bar.setFormat("Computing stretch parameters...")
            self.progress_bar.setValue(30)
            QApplication.processEvents()
            try:
                self.cache.compute_global_stretch()
            except Exception as ex:
                self.siril.log(
                    f"[BlinkComparator] WARNING: compute_global_stretch after register failed: {ex}"
                )
            self.progress_bar.setFormat("Loading reference frame...")
            self.progress_bar.setValue(50)
            QApplication.processEvents()
            try:
                self.cache.load_reference_frame()
            except Exception as ex:
                self.siril.log(
                    f"[BlinkComparator] WARNING: load_reference_frame after register failed: {ex}"
                )
            self.progress_bar.setValue(60)
            QApplication.processEvents()
        if self.thumb_cache is not None:
            self.thumb_cache.seq = self.seq
            # Re-seed stretch parameters on the thumb cache too so newly
            # rendered thumbnails match the main canvas.
            try:
                self.thumb_cache.global_median = self.cache.global_median
                self.thumb_cache.global_mad = self.cache.global_mad
            except Exception:
                pass
            if hasattr(self.thumb_cache, "invalidate"):
                try:
                    self.thumb_cache.invalidate()
                except Exception:
                    pass
        if self.marker is not None:
            self.marker.seq = self.seq
            # self.marker.total stays valid as long as seq.number is unchanged;
            # if register somehow pruned frames we bail cleanly.
            if self.seq.number != self.marker.total:
                self.siril.log(
                    f"[BlinkComparator] WARNING: register changed frame count "
                    f"({self.marker.total} -> {self.seq.number}); pending marks may be misaligned."
                )

        # Diagnostic: check regdata on all channels for frame 0
        n_layers = getattr(self.seq, 'nb_layers', 1)
        for ch in range(n_layers):
            try:
                reg = self.siril.get_seq_regdata(0, ch)
                if reg is not None:
                    attrs = {a: getattr(reg, a, None) for a in
                             ['fwhm', 'weighted_fwhm', 'roundness', 'quality',
                              'background_lvl', 'number_of_stars']}
                    self.siril.log(f"[BlinkComparator] Frame 0 regdata ch{ch}: {attrs}")
                else:
                    self.siril.log(f"[BlinkComparator] Frame 0 regdata ch{ch}: None")
            except Exception as ex:
                self.siril.log(f"[BlinkComparator] Frame 0 regdata ch{ch} error: {ex}")

        # Reload all statistics
        self.frame_stats = FrameStatistics(self.siril, self.seq)

        def reload_progress(i, total):
            # M2 (v1.2.8 audit-5): the stretch/reference rebind already
            # advanced the bar to 60%; scale reload into the remaining
            # 60→95% span so the progress bar doesn't visibly regress.
            pct = 60 + int(35 * i / max(1, total))
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Reloading stats... frame {i + 1}/{total}")
            QApplication.processEvents()

        self.frame_stats.load_all(progress_callback=reload_progress)

        # Refresh all UI
        self.stats_table.populate(self.frame_stats, self.marker)
        self.batch_widget.set_statistics(self.frame_stats, self.marker)
        self.approval_widget.set_statistics(self.frame_stats)
        self._refresh_statistics_graph()
        self._refresh_scatter_plot()
        self._precompute_overlay_stats()
        self._update_frame_info(self.current_frame)
        self._update_canvas_overlay(self.current_frame)

        # Remove banner if regdata is now available
        if self.frame_stats.has_regdata and hasattr(self, '_regdata_banner'):
            self._regdata_banner.setVisible(False)

        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Star detection complete!")
        QTimer.singleShot(1500, lambda: self.progress_bar.setVisible(False))

        if self.frame_stats.has_regdata:
            QMessageBox.information(self, "Star Detection Complete",
                                    "FWHM, Roundness, and Stars data is now available.\n"
                                    "The statistics table has been refreshed.")
        else:
            QMessageBox.warning(self, "No Data",
                                "Star detection ran but no FWHM data was found.\n"
                                f"Try running 'register {self.seq.seqname} -2pass' manually\n"
                                "in the Siril console and restart the script.")

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.addWidget(self._build_left_panel())
        layout.addWidget(self._build_right_panel(), 1)
        self.setWindowTitle("Svenesis Blink Comparator")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 800)

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)

        lbl = QLabel(f"Blink Comparator {VERSION}")
        lbl.setStyleSheet("font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_playback_group(layout)
        self._build_mode_group(layout)
        self._build_marking_group(layout)
        self._build_batch_group(layout)
        self._build_approval_group(layout)

        # Display Options widgets live in the zoom bar (see _build_right_panel)
        self.chk_overlay = QCheckBox("Overlay")
        self.chk_overlay.setChecked(True)
        self.chk_overlay.setToolTip("Show frame number and FWHM burned into the image corner")
        _nofocus(self.chk_overlay)
        self.chk_overlay.stateChanged.connect(lambda s: self.canvas.set_show_overlay(s == Qt.CheckState.Checked.value))

        self.combo_autostretch = QComboBox()
        self.combo_autostretch.addItems(list(AUTOSTRETCH_PRESETS.keys()))
        self.combo_autostretch.setCurrentText(DEFAULT_AUTOSTRETCH_PRESET)
        self.combo_autostretch.setToolTip(
            "Conservative: darker background, preserves dim detail.\n"
            "Default: PixInsight-style STF (shadows_clip=-2.8, target=0.25).\n"
            "Aggressive: brighter, higher contrast.\n"
            "Linear: no stretch — raw data clipped to 0-255."
        )
        _nofocus(self.combo_autostretch)
        self.combo_autostretch.currentTextChanged.connect(self._on_autostretch_preset_changed)

        self.slider_thumb_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_thumb_size.setRange(40, 160)
        self.slider_thumb_size.setValue(THUMBNAIL_WIDTH)
        self.slider_thumb_size.setFixedWidth(100)
        self.slider_thumb_size.setToolTip("Thumbnail size (40–160 px)")
        _nofocus(self.slider_thumb_size)
        self.slider_thumb_size.valueChanged.connect(self._on_thumb_size_changed)

        layout.addStretch()

        # Export buttons
        export_row = QHBoxLayout()
        btn_csv = QPushButton("Export CSV...")
        _nofocus(btn_csv)
        btn_csv.setToolTip("Export full statistics table as CSV")
        btn_csv.clicked.connect(self._export_csv)
        export_row.addWidget(btn_csv)

        btn_gif = QPushButton("Export GIF...")
        _nofocus(btn_gif)
        btn_gif.setToolTip("Export blink animation as animated GIF")
        btn_gif.clicked.connect(self._export_gif)
        export_row.addWidget(btn_gif)
        layout.addLayout(export_row)

        btn_coffee = QPushButton("\u2615  Buy me a Coffee")
        _nofocus(btn_coffee)
        btn_coffee.setObjectName("CoffeeButton")
        btn_coffee.setToolTip("Support the development of this tool")
        btn_coffee.clicked.connect(self._show_coffee_dialog)
        btn_help = QPushButton("Help")
        _nofocus(btn_help)
        btn_help.clicked.connect(self._show_help_dialog)
        btn_close = QPushButton("Apply Rejections && Close")
        _nofocus(btn_close)
        btn_close.setObjectName("CloseButton")
        btn_close.setToolTip(
            "Apply any pending rejections (write rejected_frames.txt and "
            "move rejected FITS into a 'rejected/' subfolder), then close."
        )
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_coffee)
        layout.addWidget(btn_help)
        layout.addWidget(btn_close)

        scroll.setWidget(content)
        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return left

    def _build_playback_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Playback")
        g_layout = QVBoxLayout(group)

        transport = QHBoxLayout()
        self.btn_first = QPushButton("|<")
        self.btn_first.setToolTip("First frame (Home)")
        _nofocus(self.btn_first)
        self.btn_first.clicked.connect(self._go_first)
        transport.addWidget(self.btn_first)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setToolTip("Previous frame (Left arrow)")
        _nofocus(self.btn_prev)
        self.btn_prev.clicked.connect(self._go_prev)
        transport.addWidget(self.btn_prev)

        self.btn_play = QPushButton("\u25B6  Play")
        self.btn_play.setObjectName("PlayButton")
        self.btn_play.setToolTip("Play / Pause (Space)")
        _nofocus(self.btn_play)
        self.btn_play.clicked.connect(self._toggle_play)
        transport.addWidget(self.btn_play, 2)

        self.btn_next = QPushButton(">")
        self.btn_next.setToolTip("Next frame (Right arrow)")
        _nofocus(self.btn_next)
        self.btn_next.clicked.connect(self._go_next)
        transport.addWidget(self.btn_next)

        self.btn_last = QPushButton(">|")
        self.btn_last.setToolTip("Last frame (End)")
        _nofocus(self.btn_last)
        self.btn_last.clicked.connect(self._go_last)
        transport.addWidget(self.btn_last)
        g_layout.addLayout(transport)

        # Color-coded frame slider
        self.frame_slider = ColorCodedSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, max(0, self.total_frames - 1))
        self.frame_slider.setValue(0)
        self.frame_slider.setToolTip("Drag to navigate frames (red ticks = excluded)")
        _nofocus(self.frame_slider)
        self.frame_slider.valueChanged.connect(self._on_slider_changed)
        g_layout.addWidget(self.frame_slider)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 30)
        self.spin_fps.setValue(3)
        self.spin_fps.setSuffix(" fps")
        self.spin_fps.setFixedWidth(80)
        _nofocus(self.spin_fps)
        self.spin_fps.valueChanged.connect(self._on_fps_changed)
        speed_row.addWidget(self.spin_fps)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(3)
        _nofocus(self.speed_slider)
        self.speed_slider.valueChanged.connect(self.spin_fps.setValue)
        self.spin_fps.valueChanged.connect(self.speed_slider.setValue)
        speed_row.addWidget(self.speed_slider)
        g_layout.addLayout(speed_row)

        loop_row = QHBoxLayout()
        self.chk_loop = QCheckBox("Loop playback")
        self.chk_loop.setChecked(True)
        self.chk_loop.setToolTip("Restart from first frame after reaching the last")
        _nofocus(self.chk_loop)
        loop_row.addWidget(self.chk_loop)

        self.chk_only_included = QCheckBox("Only included frames")
        self.chk_only_included.setChecked(False)
        self.chk_only_included.setToolTip(
            "During playback, skip frames marked as rejected."
        )
        _nofocus(self.chk_only_included)
        loop_row.addWidget(self.chk_only_included)
        loop_row.addStretch()
        g_layout.addLayout(loop_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        g_layout.addWidget(self.progress_bar)

        parent_layout.addWidget(group)

    def _build_mode_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Display Mode")
        g_layout = QVBoxLayout(group)

        self.mode_group = QButtonGroup(self)
        self.radio_normal = QRadioButton("Normal")
        self.radio_normal.setChecked(True)
        self.radio_normal.setToolTip("Show each frame with autostretch.")
        self.radio_sidebyside = QRadioButton("Side by Side (vs. reference)")
        self.radio_sidebyside.setToolTip("Current frame on left, reference on right.")

        self.mode_group.addButton(self.radio_normal, 0)
        self.mode_group.addButton(self.radio_sidebyside, 1)

        for radio in (self.radio_normal, self.radio_sidebyside):
            _nofocus(radio)
            g_layout.addWidget(radio)

        self.mode_group.idToggled.connect(self._on_mode_changed)

        parent_layout.addWidget(group)

    def _build_marking_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Frame Marking")
        g_layout = QVBoxLayout(group)

        mark_row = QHBoxLayout()
        self.btn_include = QPushButton("\u2713  Keep  (G)")
        self.btn_include.setObjectName("IncludeButton")
        self.btn_include.setToolTip("Mark current frame as good / include (G)")
        _nofocus(self.btn_include)
        self.btn_include.clicked.connect(self._mark_include)
        mark_row.addWidget(self.btn_include)

        self.btn_exclude = QPushButton("\u2717  Reject  (B)")
        self.btn_exclude.setObjectName("ExcludeButton")
        self.btn_exclude.setToolTip("Mark current frame as bad / exclude (B)")
        _nofocus(self.btn_exclude)
        self.btn_exclude.clicked.connect(self._mark_exclude)
        mark_row.addWidget(self.btn_exclude)
        g_layout.addLayout(mark_row)

        self.btn_reset_all = QPushButton("Reset All Rejections")
        self.btn_reset_all.setToolTip(
            "Mark every frame as Included again — clears the Siril baseline "
            "and all pending rejections. Cannot be undone."
        )
        _nofocus(self.btn_reset_all)
        self.btn_reset_all.clicked.connect(self._reset_all_rejections)
        g_layout.addWidget(self.btn_reset_all)

        self.chk_auto_advance = QCheckBox("Auto-advance after marking")
        self.chk_auto_advance.setChecked(True)
        self.chk_auto_advance.setToolTip("Automatically go to next frame after pressing G or B")
        _nofocus(self.chk_auto_advance)
        g_layout.addWidget(self.chk_auto_advance)

        self.lbl_pending = QLabel("No pending changes")
        self.lbl_pending.setStyleSheet("color: #999; font-size: 9pt;")
        self.lbl_pending.setWordWrap(True)
        g_layout.addWidget(self.lbl_pending)

        parent_layout.addWidget(group)

    def _build_batch_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Batch Selection")
        g_layout = QVBoxLayout(group)
        self.batch_widget = BatchRejectWidget()
        self.batch_widget.reject_frames.connect(self._on_batch_reject)
        g_layout.addWidget(self.batch_widget)
        parent_layout.addWidget(group)

    def _build_approval_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Approval Expression")
        g_layout = QVBoxLayout(group)
        self.approval_widget = ApprovalExpressionWidget()
        self.approval_widget.reject_frames.connect(self._on_batch_reject)
        g_layout.addWidget(self.approval_widget)
        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # RIGHT PANEL (tabbed + filmstrip)
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(5, 5, 5, 5)

        # Tabs
        self.right_tabs = QTabWidget()
        self.right_tabs.setDocumentMode(True)

        # Tab 1: Viewer
        viewer_tab = QWidget()
        vt_layout = QVBoxLayout(viewer_tab)
        vt_layout.setContentsMargins(2, 2, 2, 2)

        self.lbl_frame_info = QLabel("No sequence loaded")
        self.lbl_frame_info.setStyleSheet("font-size: 10pt; color: #999;")
        vt_layout.addWidget(self.lbl_frame_info)

        self.canvas = ImageCanvas()
        self.canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        self.canvas.resized.connect(self._on_canvas_resized)
        vt_layout.addWidget(self.canvas, 1)

        zoom_bar = QHBoxLayout()
        self.lbl_zoom = QLabel("Zoom: 100%")
        self.lbl_zoom.setStyleSheet("color: #ffffff; font-size: 9pt;")
        zoom_bar.addWidget(self.lbl_zoom)

        btn_fit_window = QPushButton("Fit-in-Window")
        btn_fit_window.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        btn_fit_window.setToolTip("Fit image to window (Z)")
        _nofocus(btn_fit_window)
        btn_fit_window.clicked.connect(self._fit_to_window)
        zoom_bar.addWidget(btn_fit_window)

        btn_copy = QPushButton("Copy (Ctrl+C)")
        btn_copy.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        btn_copy.setToolTip("Copy current frame to clipboard")
        _nofocus(btn_copy)
        btn_copy.clicked.connect(self._copy_frame_to_clipboard)
        zoom_bar.addWidget(btn_copy)

        # Display Options (moved from right-side panel)
        _sep1 = QLabel("|")
        _sep1.setStyleSheet("color: #555;")
        zoom_bar.addWidget(_sep1)
        zoom_bar.addWidget(self.chk_overlay)
        zoom_bar.addSpacing(20)
        _lbl_as = QLabel("Stretch:")
        _lbl_as.setStyleSheet("color: #ffffff; font-size: 9pt;")
        zoom_bar.addWidget(_lbl_as)
        zoom_bar.addWidget(self.combo_autostretch)
        _lbl_th = QLabel("Thumbs:")
        _lbl_th.setStyleSheet("color: #ffffff; font-size: 9pt;")
        zoom_bar.addWidget(_lbl_th)
        zoom_bar.addWidget(self.slider_thumb_size)

        zoom_bar.addStretch()

        self.lbl_shortcuts = QLabel(
            "Space=Play  \u2190\u2192=Nav  G/B=Mark  T=A/B  Z=Zoom  "
            "Ctrl+Z=Undo  Ctrl+C=Copy  1-9=FPS  +/-=Speed  (Help for more)"
        )
        self.lbl_shortcuts.setStyleSheet("color: #666; font-size: 8pt;")
        zoom_bar.addWidget(self.lbl_shortcuts)
        vt_layout.addLayout(zoom_bar)

        self.right_tabs.addTab(viewer_tab, "Viewer")

        # Tab 2: Statistics Table
        self.stats_table = StatisticsTableWidget()
        self.stats_table.frame_selected.connect(self._on_table_frame_selected)
        self.stats_table.reject_selected.connect(self._on_batch_reject)
        self.right_tabs.addTab(self.stats_table, "Statistics Table")

        # Tab 3: Statistics Graph
        graph_tab = QWidget()
        gt_layout = QVBoxLayout(graph_tab)
        gt_layout.setContentsMargins(2, 2, 2, 2)

        graph_controls = QHBoxLayout()
        graph_controls.addWidget(QLabel("Show:"))
        self.chk_graph_fwhm = QCheckBox("FWHM")
        self.chk_graph_fwhm.setChecked(True)
        _nofocus(self.chk_graph_fwhm)
        self.chk_graph_fwhm.stateChanged.connect(self._on_graph_metric_toggled)
        graph_controls.addWidget(self.chk_graph_fwhm)
        self.chk_graph_bg = QCheckBox("Background")
        self.chk_graph_bg.setChecked(True)
        _nofocus(self.chk_graph_bg)
        self.chk_graph_bg.stateChanged.connect(self._on_graph_metric_toggled)
        graph_controls.addWidget(self.chk_graph_bg)
        self.chk_graph_round = QCheckBox("Roundness")
        self.chk_graph_round.setChecked(False)
        _nofocus(self.chk_graph_round)
        self.chk_graph_round.stateChanged.connect(self._on_graph_metric_toggled)
        graph_controls.addWidget(self.chk_graph_round)
        graph_controls.addStretch()
        gt_layout.addLayout(graph_controls)

        self.stats_graph = StatisticsGraphWidget()
        gt_layout.addWidget(self.stats_graph, 1)

        self.right_tabs.addTab(graph_tab, "Statistics Graph")

        # Tab 4: Scatter Plot
        scatter_tab = QWidget()
        st_layout = QVBoxLayout(scatter_tab)
        st_layout.setContentsMargins(2, 2, 2, 2)

        scatter_controls = QHBoxLayout()
        scatter_controls.addWidget(QLabel("X:"))
        self.combo_scatter_x = QComboBox()
        self.combo_scatter_x.addItems(["FWHM", "Roundness", "Background", "Stars", "Weight"])
        self.combo_scatter_x.setCurrentText("FWHM")
        _nofocus(self.combo_scatter_x)
        self.combo_scatter_x.currentIndexChanged.connect(self._refresh_scatter_plot)
        scatter_controls.addWidget(self.combo_scatter_x)

        scatter_controls.addWidget(QLabel("Y:"))
        self.combo_scatter_y = QComboBox()
        self.combo_scatter_y.addItems(["Roundness", "FWHM", "Background", "Stars", "Weight"])
        self.combo_scatter_y.setCurrentText("Roundness")
        _nofocus(self.combo_scatter_y)
        self.combo_scatter_y.currentIndexChanged.connect(self._refresh_scatter_plot)
        scatter_controls.addWidget(self.combo_scatter_y)

        scatter_controls.addStretch()
        st_layout.addLayout(scatter_controls)

        self.scatter_plot = ScatterPlotWidget()
        self.scatter_plot.frame_clicked.connect(self._on_scatter_frame_clicked)
        st_layout.addWidget(self.scatter_plot, 1)

        self.right_tabs.addTab(scatter_tab, "Scatter Plot")

        r_layout.addWidget(self.right_tabs, 1)

        # Filmstrip (always visible below tabs)
        self.filmstrip = ThumbnailFilmstrip(self.total_frames, marker=self.marker)
        self.filmstrip.frame_selected.connect(self._on_filmstrip_frame_selected)
        self.filmstrip.scroll.horizontalScrollBar().valueChanged.connect(
            lambda: QTimer.singleShot(100, self._load_visible_thumbnails)
        )
        r_layout.addWidget(self.filmstrip)

        return right

    # ------------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        # L1 (v1.2.8 audit-4): wrap every non-modifier shortcut so a
        # focused spinbox / line-edit keeps the raw keystroke instead of
        # seeing it stolen. `+`/`-` step spinbox values, arrow-keys step
        # or move the caret, G/B/T/Home/End are single-char text input.
        # Ctrl+Z and Ctrl+C keep firing because Qt naturally routes Ctrl
        # combos to shortcut targets even with focus in a line-edit (and
        # a QAbstractSpinBox doesn't support paste anyway).
        def guarded(handler):
            def _wrapped():
                fw = QApplication.focusWidget()
                if isinstance(fw, (QAbstractSpinBox, QLineEdit, QTextEdit)):
                    return
                handler()
            return _wrapped

        QShortcut(QKeySequence(Qt.Key.Key_Space), self, guarded(self._toggle_play))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, guarded(self._go_next))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, guarded(self._go_prev))
        QShortcut(QKeySequence(Qt.Key.Key_Home), self, guarded(self._go_first))
        QShortcut(QKeySequence(Qt.Key.Key_End), self, guarded(self._go_last))
        QShortcut(QKeySequence(Qt.Key.Key_G), self, guarded(self._mark_include))
        QShortcut(QKeySequence(Qt.Key.Key_B), self, guarded(self._mark_exclude))
        QShortcut(QKeySequence(Qt.Key.Key_Z), self, guarded(self._fit_to_window))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Plus), self, guarded(self._speed_up))
        QShortcut(QKeySequence(Qt.Key.Key_Minus), self, guarded(self._speed_down))
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_last_marking)
        QShortcut(QKeySequence(Qt.Key.Key_T), self, guarded(self._toggle_ab_frame))
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_frame_to_clipboard)

        # P2 (v1.2.8 audit-5): 1-9 FPS presets are deliberately NOT registered
        # as QShortcuts. A WindowShortcut-context QShortcut receives the key
        # event before the focused child widget's keyPressEvent, so even with
        # a focus-widget guard the digit never reaches a focused spinbox —
        # the exact bug the guard claims to prevent. Instead we override
        # QMainWindow.keyPressEvent below, which Qt only invokes after the
        # focused widget declined the event. That lets a focused spinbox
        # consume digits naturally, while idle focus (canvas, buttons, empty
        # space) still triggers the FPS preset.

    def keyPressEvent(self, event) -> None:
        """P2 (v1.2.8 audit-5): handle 1-9 as FPS presets without stealing
        digits from focused spinboxes / line-edits. Qt only routes the
        event here if the focused child didn't consume it — so this runs
        only when focus is on a widget (canvas, button, label, main window
        itself) that ignores plain digit input.
        """
        k = event.key()
        if Qt.Key.Key_1 <= k <= Qt.Key.Key_9 and not (event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier):
            fw = QApplication.focusWidget()
            # Defensive belt-and-suspenders: a misbehaving child that
            # forwards plain keys up the chain should still not have its
            # digit overwritten with an FPS change. Qt's normal dispatch
            # won't hit us in that case, but the check costs nothing.
            if not isinstance(fw, (QAbstractSpinBox, QLineEdit, QTextEdit)):
                self.spin_fps.setValue(k - Qt.Key.Key_0)
                event.accept()
                return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # PLAYBACK CONTROL
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        if self.playing:
            self._pause()
        else:
            self._play()

    def _play(self) -> None:
        self.playing = True
        self.btn_play.setText("\u23F8  Pause")
        delay = int(1000 / self.fps)
        self._timer.start(delay)

    def _pause(self) -> None:
        self.playing = False
        self.btn_play.setText("\u25B6  Play")
        self._timer.stop()
        # Refresh all UI elements that were skipped during playback
        self._update_frame_info(self.current_frame)
        self.stats_table.highlight_current(self.current_frame)
        self.stats_graph.update_current_line(self.current_frame)
        self.scatter_plot.update_current_marker(self.current_frame)

    def _advance_frame(self) -> None:
        if not self.playing:
            return
        next_frame = self.current_frame + self.direction
        only_included = self.chk_only_included.isChecked()

        if only_included:
            attempts = 0
            while 0 <= next_frame < self.total_frames and attempts < self.total_frames:
                if self.marker.is_included(next_frame):
                    break
                next_frame += self.direction
                attempts += 1

        if next_frame >= self.total_frames:
            if self.chk_loop.isChecked():
                next_frame = 0
                if only_included:
                    while next_frame < self.total_frames and not self.marker.is_included(next_frame):
                        next_frame += 1
                    if next_frame >= self.total_frames:
                        self._pause()
                        return
            else:
                self._pause()
                return
        elif next_frame < 0:
            if self.chk_loop.isChecked():
                next_frame = self.total_frames - 1
                if only_included:
                    while next_frame >= 0 and not self.marker.is_included(next_frame):
                        next_frame -= 1
                    if next_frame < 0:
                        self._pause()
                        return
            else:
                self._pause()
                return

        self._show_frame(next_frame)
        # Lookahead scales with FPS: at 30 fps we need a ~2 s cushion (60
        # frames) to keep the cache ahead of playback; at 3 fps, 10 is plenty.
        lookahead = max(10, int(self.fps * 2))
        self._start_preload(next_frame + self.direction * 2, lookahead)

    def _go_first(self) -> None:
        self._show_frame(0)

    def _go_last(self) -> None:
        self._show_frame(self.total_frames - 1)

    def _go_prev(self) -> None:
        if self.current_frame > 0:
            self._show_frame(self.current_frame - 1)

    def _go_next(self) -> None:
        if self.current_frame < self.total_frames - 1:
            self._show_frame(self.current_frame + 1)

    def _on_slider_changed(self, value: int) -> None:
        if value != self.current_frame:
            self._show_frame(value)

    def _on_fps_changed(self, value: int) -> None:
        self.fps = float(value)
        if self.playing:
            self._timer.setInterval(int(1000 / self.fps))

    def _speed_up(self) -> None:
        self.spin_fps.setValue(min(self.spin_fps.value() + 1, 30))

    def _speed_down(self) -> None:
        self.spin_fps.setValue(max(self.spin_fps.value() - 1, 1))

    # ------------------------------------------------------------------
    # FRAME DISPLAY
    # ------------------------------------------------------------------

    def _show_frame(self, index: int) -> None:
        if index < 0 or index >= self.total_frames:
            return

        # M1 (v1.2.8 audit-3): clear the "Reached end of sequence" banner as
        # soon as the user navigates anywhere. Otherwise the cue from the
        # auto-advance tail-stop lingers across prev/slider/jump until the
        # next mark-and-advance overwrites it. Delegate to _update_marking_ui
        # so the restored label reflects the real pending-count state.
        if self.lbl_pending.text().startswith("Reached end"):
            self._update_marking_ui()

        self._frames_viewed.add(index)
        self.current_frame = index

        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(index)
        self.frame_slider.blockSignals(False)

        sbs_mode = self.radio_sidebyside.isChecked()

        if self.cache is not None:
            # Defer all canvas .update() calls — we'll do a single repaint at the end
            qimg = self.cache.get_frame(index)
            self.canvas.set_image(qimg, defer_update=True)

            # Side-by-side: load reference frame
            if sbs_mode:
                self.canvas.set_side_by_side(True, defer_update=True)
                ref_idx = self.seq.reference_image
                if ref_idx < 0 or ref_idx >= self.total_frames:
                    ref_idx = 0
                ref_img = self.cache.get_frame(ref_idx)
                self.canvas.set_side_by_side_image(ref_img, defer_update=True)
            else:
                self.canvas.set_side_by_side(False, defer_update=True)

        # During playback, skip expensive UI updates that aren't visible at speed
        if self.playing:
            # Lightweight: only update canvas overlay (burned into image) and filmstrip
            self.canvas.set_overlay_text(self._build_overlay_text(index), defer_update=True)
            self.canvas.update()  # Single repaint for all deferred changes
            self.filmstrip.highlight_current(index)
        else:
            self._schedule_frame_info_update(index)
            self.canvas.set_overlay_text(self._build_overlay_text(index), defer_update=True)
            self.canvas.update()  # Single repaint
            self.filmstrip.highlight_current(index)
            self.stats_table.highlight_current(index)
            self.stats_graph.update_current_line(index)
            self.scatter_plot.update_current_marker(index)

    def _schedule_frame_info_update(self, index: int) -> None:
        """Debounce frame-info label updates to 50 ms.

        Rapid slider scrubbing / Ctrl+Z storms fire _show_frame dozens of
        times per second; collapsing those into a single label rebuild keeps
        the info strip visually in-sync with the slider while eliminating
        the per-tick layout pass.
        """
        self._pending_frame_info_index = index
        if self._frame_info_pending:
            return
        self._frame_info_pending = True
        QTimer.singleShot(50, self._run_frame_info_update)

    def _run_frame_info_update(self) -> None:
        self._frame_info_pending = False
        idx = self._pending_frame_info_index
        if idx < 0:
            return
        # Defensive: window may have closed during the 50 ms debounce, or
        # the user may have pressed a shortcut before _deferred_init finished.
        if not self.isVisible() or not hasattr(self, 'lbl_frame_info'):
            return
        self._update_frame_info(idx)

    def _update_frame_info(self, index: int) -> None:
        incl = self.marker.is_included(index)
        incl_str = "included" if incl else "EXCLUDED"
        incl_color = "#55aa55" if incl else "#dd4444"

        parts = [
            f"Frame <b>{index + 1}</b> / {self.total_frames}",
            f"<span style='color:{incl_color};'>{incl_str}</span>",
        ]

        if self.frame_stats is not None:
            row = self.frame_stats.get(index)
            if row:
                if row["fwhm"] > 0:
                    parts.append(f"FWHM: {row['fwhm']:.2f}\"")
                if row["roundness"] > 0:
                    parts.append(f"Round: {row['roundness']:.2f}")
                if row["background"] > 0:
                    parts.append(f"BG: {row['background']:.4f}")
                if row["stars"] > 0:
                    parts.append(f"Stars: {row['stars']}")
                if row["median"] > 0:
                    parts.append(f"Med: {row['median']:.4f}")
                if row["sigma"] > 0:
                    parts.append(f"\u03C3: {row['sigma']:.4f}")
                if row["date_obs"]:
                    parts.append(f"{row['date_obs']}")

        info_str = " &nbsp;\u2502&nbsp; ".join(parts)
        self.lbl_frame_info.setText(info_str)
        self.lbl_frame_info.setTextFormat(Qt.TextFormat.RichText)

    # ------------------------------------------------------------------
    # DISPLAY MODES
    # ------------------------------------------------------------------

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        # HOTFIX (v1.2.8 audit-5+): QButtonGroup.idToggled is emitted by the
        # *group* (its own QObject), not by the radio button, so the
        # blockSignals() wrapper in _load_settings on the individual radios
        # does not suppress this handler. Guard against _show_frame being
        # called before _deferred_init has built the cache / stats — any
        # programmatic setChecked during settings restore or a second Siril
        # load_seq can otherwise trip AttributeError: 'cache'.
        if getattr(self, "cache", None) is None:
            return
        # Normal ↔ Side-by-side only changes *how* we lay out already-stretched
        # frames on the canvas — the same cached QImages are reusable for both
        # modes. Previously we dropped the whole cache here, forcing every
        # subsequent frame load to re-read the FITS. _show_frame pulls from
        # the cache for both paths, so just ask for a repaint.
        self._show_frame(self.current_frame)

    def _on_autostretch_preset_changed(self, preset: str) -> None:
        if preset not in AUTOSTRETCH_PRESETS:
            return
        # Signal may fire during __init__ before caches exist — bail safely.
        cache = getattr(self, "cache", None)
        if cache is not None:
            cache.stretch_preset = preset
            cache.invalidate()
        thumb_cache = getattr(self, "thumb_cache", None)
        if thumb_cache is not None:
            thumb_cache.stretch_preset = preset
            thumb_cache.invalidate()
            # Diff-scroll bookkeeping must be cleared — every thumbnail needs
            # to be re-rendered with the new preset.
            self._prev_visible_range = None
            if hasattr(self, "filmstrip"):
                for lbl in self.filmstrip._labels:
                    lbl.setPixmap(QPixmap())
                QTimer.singleShot(50, self._load_visible_thumbnails)
        if hasattr(self, "current_frame") and cache is not None:
            self._show_frame(self.current_frame)

    # ------------------------------------------------------------------
    # FRAME MARKING
    # ------------------------------------------------------------------

    def _mark_include(self) -> None:
        idx = self.current_frame
        prev = self.marker.is_included(idx)
        # M1 (v1.2.8 audit-4): detect a true no-op — already-included
        # with no pending change — and skip undo-stack push + heavy
        # scatter/graph refresh. Previously G-spam on an included frame
        # filled the 500-entry undo stack with redundant entries and
        # made Ctrl+Z appear broken (many presses to reach a meaningful
        # prior state). Keep auto-advance so G still moves the viewer.
        if prev is True and idx not in self.marker.changes:
            if self.chk_auto_advance.isChecked() and idx < self.total_frames - 1:
                self._go_next()
            return
        self.undo_stack.push(idx, prev)
        self.marker.mark_include(idx)
        self._after_marking(idx)

    def _mark_exclude(self) -> None:
        idx = self.current_frame
        prev = self.marker.is_included(idx)
        # M1: symmetric no-op skip. B on an already-excluded frame
        # (baseline or pending) is a no-op.
        if prev is False and idx not in self.marker.changes:
            if self.chk_auto_advance.isChecked() and idx < self.total_frames - 1:
                self._go_next()
            return
        self.undo_stack.push(idx, prev)
        self.marker.mark_exclude(idx)
        self._after_marking(idx)

    def _reset_all_rejections(self) -> None:
        """Wipe baseline + pending exclusions so every frame is included again.

        Cannot be undone — the undo stack is cleared too, since individual
        per-frame entries no longer reflect a meaningful prior state.
        """
        n_excluded = len(self.marker.get_excluded_indices())
        if n_excluded == 0 and self.marker.get_pending_count() == 0:
            QMessageBox.information(
                self, "Reset All Rejections",
                "No frames are rejected — nothing to reset."
            )
            return

        box = QMessageBox(self)
        box.setWindowTitle("Reset All Rejections")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"This will mark every frame as Included again.\n\n"
            f"\u2022 {n_excluded} currently excluded frame(s) will be re-included\n"
            f"\u2022 All pending rejections are discarded\n"
            f"\u2022 The undo history is cleared\n\n"
            f"Files on disk are NOT modified. This cannot be undone.\n\n"
            f"Continue?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        self.marker.reset_all()
        self.undo_stack.clear()

        # P4 (v1.2.8 audit-4): refresh every UI surface incrementally
        # rather than a full table rebuild. `populate()` tears down and
        # re-creates all N×10 cells + the row-to-frame map (~100 ms on
        # N=2000). update_frame_status() is O(1) per row; the full loop
        # is ~5 ms on N=2000 — 20× faster and indistinguishable visually.
        for i in range(self.total_frames):
            self.stats_table.update_frame_status(i, True, self.marker)
            self.filmstrip.update_border(i, True)
        self.frame_slider.set_exclusions(set(), self.total_frames)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)
        self._refresh_statistics_graph()
        self._refresh_scatter_plot()

    def _after_marking(self, frame_idx: int) -> None:
        incl = self.marker.is_included(frame_idx)
        self._update_marking_ui()
        self._update_frame_info(frame_idx)
        self.stats_table.update_frame_status(frame_idx, incl, self.marker)
        self.filmstrip.update_border(frame_idx, incl)
        # Heavy refreshes (scatter plot Figure rebuild, statistics graph
        # rebuild, slider exclusions repaint) are deferred through a single
        # coalesced timer. When the user hammers G/B with auto-advance, this
        # is the difference between 50× rebuild-everything and 1× at the end.
        self._schedule_post_mark_refresh()

        if self.chk_auto_advance.isChecked():
            if self.current_frame < self.total_frames - 1:
                self._go_next()
            else:
                # Silent stall on the last frame left users unsure whether
                # the mark registered. Flash the pending-changes label to
                # make "you've reached the end" obvious without a modal.
                self.lbl_pending.setText(
                    f"Reached end of sequence — "
                    f"{self.marker.get_pending_count()} pending change(s)"
                )
                self.lbl_pending.setStyleSheet(
                    "color: #88aaff; font-size: 9pt; font-weight: bold;"
                )

    def _schedule_post_mark_refresh(self) -> None:
        """Debounce the heavy scatter/graph/slider refreshes after marking.

        Multiple marks within the debounce window collapse to a single
        full refresh — both visually identical to the synchronous version,
        but ~N times cheaper during rapid batch marking.
        """
        if self._post_mark_refresh_pending:
            return
        self._post_mark_refresh_pending = True
        QTimer.singleShot(150, self._run_post_mark_refresh)

    def _run_post_mark_refresh(self) -> None:
        self._post_mark_refresh_pending = False
        # Defensive: the 150 ms debounce window can span a window close or
        # race with _deferred_init. Bail out if critical state is gone /
        # not yet built so the timer callback never touches stale widgets.
        if not self.isVisible() or self.marker is None or self.frame_stats is None:
            return
        # Slider exclusions repaint (draws every excluded frame as a red tick)
        self.frame_slider.set_exclusions(
            self.marker.get_excluded_indices(), self.total_frames
        )
        # P2 (v1.2.8 audit-4): scatter fast path — set_offsets on existing
        # PathCollection artists rather than tearing down the Figure. Falls
        # back to full render on the first call (no artists yet) or after
        # a metric change.
        if not self.scatter_plot.update_excluded(self.marker, self.current_frame):
            self._refresh_scatter_plot()
        # Statistics graph — excluded points flip to red scatter, line skips them.
        # P1 (v1.2.8 audit-4): render() now dedupes on an input signature,
        # so back-to-back debounced calls with identical state are cheap.
        self._refresh_statistics_graph()

    def _undo_last_marking(self) -> None:
        """Undo the last marking action (single or batch group)."""
        action = self.undo_stack.pop()
        if action is None:
            return

        # Normalize: single action → list of one, batch → list of many
        if isinstance(action, list):
            entries = action
        else:
            entries = [action]

        # Snapshot where the user currently is BEFORE we touch anything.
        # For single-frame undo we want to land on the undone frame; for
        # batch undo (e.g. "Reject Worst 10%") landing on "the last index
        # in the batch" was disorienting — teleported the viewer to an
        # arbitrary frame far from where the user was working. Keep the
        # single-frame UX but stay put for batch undo.
        jump_target = self.current_frame
        is_single = (not isinstance(action, list)) or len(entries) == 1
        if is_single:
            jump_target = entries[0][0]

        for frame_idx, prev_included in entries:
            if prev_included:
                self.marker.mark_include(frame_idx)
            else:
                self.marker.mark_exclude(frame_idx)
            incl = self.marker.is_included(frame_idx)
            self.stats_table.update_frame_status(frame_idx, incl, self.marker)
            self.filmstrip.update_border(frame_idx, incl)

        self._update_marking_ui()
        # Route through the same deferred refresh as _after_marking so rapid
        # Ctrl+Z through an undo history collapses into a single heavy redraw
        # AND the scatter + graph reflect the restored inclusion state.
        self._schedule_post_mark_refresh()
        self._show_frame(jump_target)

    def _update_marking_ui(self) -> None:
        n = self.marker.get_pending_count()
        if n == 0:
            self.lbl_pending.setText("No pending changes")
            self.lbl_pending.setStyleSheet("color: #999; font-size: 9pt;")
        else:
            excl = self.marker.get_newly_excluded_count()
            incl = self.marker.get_newly_included_count()
            parts = []
            if excl > 0:
                parts.append(f"{excl} to exclude")
            if incl > 0:
                parts.append(f"{incl} to include")
            self.lbl_pending.setText(f"Pending: {', '.join(parts)}")
            self.lbl_pending.setStyleSheet("color: #aaaa55; font-size: 9pt;")

    def _apply_changes(self) -> None:
        """Folder mode: temp sequence is throwaway; write rejected list + optionally move files."""
        excluded = sorted(self.marker.get_excluded_indices())
        if not excluded:
            QMessageBox.information(
                self, "Apply Rejections",
                "No frames are marked as rejected — nothing to apply."
            )
            return

        # Map sequence-index → source FITS filename.
        # Primary path: ask Siril directly via get_seq_imgdata(i).filename so
        # the mapping is always correct regardless of how the OS / Python /
        # Siril ordered the folder listing during `convert`. Fall back to
        # the sorted-basename heuristic only if the RPC doesn't expose a
        # filename (older sirilpy builds) — and in that case, surface the
        # assumption clearly so the user can verify.
        rejected_names: list[str] = []
        used_fallback = False
        try:
            for i in excluded:
                name: str | None = None
                try:
                    imgdata = self.siril.get_seq_imgdata(i)
                except Exception:
                    imgdata = None
                if imgdata is not None:
                    fn = getattr(imgdata, 'filename', None) or getattr(imgdata, 'name', None)
                    if fn:
                        # Siril may return an absolute path; we want the basename
                        # for the move loop below to join against the folder.
                        name = os.path.basename(str(fn))
                if name:
                    rejected_names.append(name)
                else:
                    used_fallback = True
                    break
        except Exception:
            used_fallback = True

        if used_fallback:
            # Legacy mapping: sorted basename list indexed by sequence index.
            # Correct iff Siril's `convert -fitseq` iterated the folder in the
            # same order as Python's sorted(). Verified empirically on macOS
            # for simple ASCII filenames; flag to the user for awareness.
            all_fits = _scan_fits_files(self._folder_mode_path)
            source_files = [
                f for f in all_fits
                if not f.startswith(FOLDER_MODE_SEQNAME)
            ]
            if not source_files or len(source_files) < self.total_frames:
                QMessageBox.warning(
                    self, "Source Files Missing",
                    f"Expected {self.total_frames} FITS files in the source folder "
                    f"but only found {len(source_files)}.\n"
                    f"Apply was aborted."
                )
                return
            rejected_names = [source_files[i] for i in excluded if i < len(source_files)]

        move_box = QMessageBox(self)
        move_box.setWindowTitle("Apply Rejections")
        move_box.setText(
            f"{len(excluded)} frame(s) marked as rejected.\n\n"
            f"This will write 'rejected_frames.txt' to:\n{self._folder_mode_path}\n\n"
            "and move the rejected FITS files into a 'rejected/' subfolder.\n\n"
            "Continue?"
        )
        move_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        move_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        reply = move_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return

        # H2 (v1.2.8 audit-4): move files FIRST, then write the list of
        # files that actually landed in rejected/. Previously the list was
        # written up front, so a partial move failure (Windows lock,
        # permissions, disk full) left rejected_frames.txt claiming N
        # entries while only M < N actually moved — a silent audit-trail
        # divergence where users re-stacking from the folder would consume
        # files they believed were excluded.
        reject_dir = os.path.join(self._folder_mode_path, "rejected")
        try:
            os.makedirs(reject_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not create 'rejected/' folder:\n{e}")
            return

        # L4 (v1.2.8 audit-5): track which frame indices actually moved so
        # `commit_subset` can bake *only* those into the baseline below.
        # Previously `marker.commit()` promoted the full pending set even
        # when some files failed to move, so the close-confirm dialog
        # silently stopped asking about frames whose files were still
        # sitting next to the kept ones — a quiet audit-trail bug.
        moved_names: list[str] = []
        moved_indices: set[int] = set()
        failed: list[str] = []
        for k, name in enumerate(rejected_names):
            src = os.path.join(self._folder_mode_path, name)
            dst = os.path.join(reject_dir, name)
            try:
                shutil.move(src, dst)
                moved_names.append(name)
                # `excluded[k]` is the source frame index for rejected_names[k]
                # (built in lockstep above). Guard against length drift just
                # in case the fallback path truncated rejected_names.
                if k < len(excluded):
                    moved_indices.add(excluded[k])
            except OSError as e:
                failed.append(f"{name}: {e}")
        moved_count = len(moved_names)
        if failed:
            QMessageBox.warning(
                self, "Some Files Could Not Be Moved",
                f"Moved {moved_count} of {len(rejected_names)}. Failures:\n"
                + "\n".join(failed[:10])
            )

        # Only write the list after we know which names actually moved.
        # If NOTHING moved we still record an empty list with the failure
        # headers so the audit trail is self-describing.
        list_path = os.path.join(self._folder_mode_path, "rejected_frames.txt")
        try:
            with open(list_path, "w", encoding="utf-8") as f:
                f.write("# Blink Comparator — Rejected Frames (folder mode)\n")
                f.write(f"# Folder: {self._folder_mode_path}\n")
                f.write(f"# Total frames: {self.total_frames}\n")
                f.write(f"# Marked for rejection: {len(rejected_names)}\n")
                f.write(f"# Successfully moved: {moved_count}\n")
                if failed:
                    f.write(f"# Move failures: {len(failed)}\n")
                f.write("\n")
                for name in moved_names:
                    f.write(f"{name}\n")
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Failed to write {list_path}:\n{e}")
            # Files already moved — don't early-return; still commit marker
            # so user isn't prompted again about frames that are physically
            # gone from the source folder.

        summary = f"Wrote rejected_frames.txt with {moved_count} entries."
        if moved_count > 0:
            summary += f"\nMoved {moved_count} file(s) to 'rejected/' subfolder."
        if failed:
            summary += f"\n{len(failed)} file(s) could not be moved (see warning above)."
        QMessageBox.information(self, "Rejections Applied", summary)

        # L4 (v1.2.8 audit-5): only bake the frames whose files actually
        # moved. Any rejection whose move failed stays in `marker.changes`
        # so the close-confirm dialog re-prompts the user — their file is
        # still in the source folder and they likely want to retry.
        if moved_indices:
            self.marker.commit_subset(moved_indices)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)

    # ------------------------------------------------------------------
    # BATCH REJECT
    # ------------------------------------------------------------------

    def _on_batch_reject(self, frame_indices: list[int]) -> None:
        if not frame_indices:
            return
        reply = QMessageBox.question(
            self, "Batch Reject",
            f"Mark {len(frame_indices)} frame(s) as excluded?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # Collect undo entries as a batch group (single Ctrl+Z undoes all)
        batch_undo: list[tuple[int, bool]] = []
        for idx in frame_indices:
            prev = self.marker.is_included(idx)
            batch_undo.append((idx, prev))
            self.marker.mark_exclude(idx)
            self.stats_table.update_frame_status(idx, False, self.marker)
            self.filmstrip.update_border(idx, False)
        self.undo_stack.push_batch(batch_undo)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)
        # Route through the canonical post-mark refresh so the scatter plot
        # also reflects the new exclusions (previously only the slider ticks
        # and stats graph were refreshed here — the scatter kept showing
        # bad frames in the "good" color until some other event fired it).
        self._schedule_post_mark_refresh()

    # ------------------------------------------------------------------
    # ZOOM
    # ------------------------------------------------------------------

    def _fit_to_window(self) -> None:
        self.canvas.reset_view()

    def _on_canvas_zoom_changed(self, zoom: float) -> None:
        self.lbl_zoom.setText(f"Zoom: {int(zoom * 100)}%")

    def _on_canvas_resized(self, w: int, h: int) -> None:
        """Debounced canvas-resize handler. Updates the FrameCache's scaling
        target so future frame loads render at the new size, and invalidates
        already-cached images so they re-render lazily. Debounced to avoid
        a storm of cache invalidations during an interactive window drag.
        """
        if self.cache is None:
            return
        self._pending_canvas_size = (max(400, w), max(300, h))
        if self._canvas_resize_pending:
            return
        self._canvas_resize_pending = True
        # 250 ms trailing debounce — long enough that a drag settles, short
        # enough that the first post-drag frame load uses the new size.
        QTimer.singleShot(250, self._apply_canvas_resize)

    def _apply_canvas_resize(self) -> None:
        self._canvas_resize_pending = False
        if self.cache is None or not self.isVisible():
            return
        # M3 (v1.2.8 audit-3): skip if the deferred init hasn't finished yet.
        # An early resize (e.g. from show()) can otherwise invalidate a cache
        # that's about to be populated by the first preload, wasting the
        # startup work.
        if not getattr(self, "_ready_for_display", False):
            return
        w, h = self._pending_canvas_size
        # H1 + M3: single atomic size+epoch+clear so a concurrent preload
        # worker can't commit a stale-sized QImage.
        if not self.cache.set_display_size(w, h):
            return  # no-op
        # Repaint the current frame at the new size (loads fresh from Siril).
        self._show_frame(self.current_frame)

    # ------------------------------------------------------------------
    # STATISTICS GRAPH
    # ------------------------------------------------------------------

    def _refresh_statistics_graph(self) -> None:
        if self.frame_stats is None:
            return
        self.stats_graph.render(
            self.frame_stats, self.marker, self.current_frame,
            show_fwhm=self.chk_graph_fwhm.isChecked(),
            show_bg=self.chk_graph_bg.isChecked(),
            show_roundness=self.chk_graph_round.isChecked(),
        )

    def _on_graph_metric_toggled(self) -> None:
        self._refresh_statistics_graph()

    # ------------------------------------------------------------------
    # TABLE
    # ------------------------------------------------------------------

    def _on_table_frame_selected(self, frame_idx: int) -> None:
        self._show_frame(frame_idx)
        self.right_tabs.setCurrentIndex(0)  # Switch to viewer

    # ------------------------------------------------------------------
    # FILMSTRIP
    # ------------------------------------------------------------------

    def _on_filmstrip_frame_selected(self, frame_idx: int) -> None:
        self._show_frame(frame_idx)

    def _load_visible_thumbnails(self) -> None:
        if self.thumb_cache is None:
            return
        start, end = self.filmstrip.get_visible_range()
        prev = self._prev_visible_range
        if prev is not None:
            prev_start, prev_end = prev
            # Fully overlapping viewports (typical rapid-scroll deltas of 0–1
            # thumbnails): only process the edges rather than every visible
            # frame. Saves an O(visible) cache lookup on every scroll event.
            for i in range(start, end):
                if prev_start <= i < prev_end:
                    continue
                pix = self.thumb_cache.get_thumbnail(i)
                if pix is not None:
                    self.filmstrip.set_thumbnail(i, pix)
        else:
            for i in range(start, end):
                pix = self.thumb_cache.get_thumbnail(i)
                if pix is not None:
                    self.filmstrip.set_thumbnail(i, pix)
        self._prev_visible_range = (start, end)

    # ------------------------------------------------------------------
    # EXPORT REJECTED LIST
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # CANVAS OVERLAY
    # ------------------------------------------------------------------

    def _precompute_overlay_stats(self) -> None:
        """Pre-format the stats portion of overlay text for all frames (once)."""
        self._overlay_stats_cache: list[str] = [""] * self.total_frames
        if self.frame_stats is None:
            return
        for i in range(self.total_frames):
            row = self.frame_stats.get(i)
            if not row:
                continue
            parts = []
            if row["fwhm"] > 0:
                parts.append(f"FWHM:{row['fwhm']:.2f}\"")
            if row["roundness"] > 0:
                parts.append(f"Rnd:{row['roundness']:.2f}")
            if row.get("weight", 0) > 0:
                parts.append(f"Wt:{row['weight']:.3f}")
            if parts:
                self._overlay_stats_cache[i] = "  ".join(parts)

    def _build_overlay_text(self, index: int) -> str:
        """Build overlay text using pre-computed stats (fast path for playback)."""
        incl = self.marker.is_included(index)
        status = "INCLUDED" if incl else "EXCLUDED"
        header = f"Frame {index + 1}/{self.total_frames}  [{status}]"
        stats_line = self._overlay_stats_cache[index] if hasattr(self, '_overlay_stats_cache') and index < len(self._overlay_stats_cache) else ""
        if stats_line:
            return header + "\n" + stats_line
        return header

    def _update_canvas_overlay(self, index: int) -> None:
        self.canvas.set_overlay_text(self._build_overlay_text(index))

    # ------------------------------------------------------------------
    # SCATTER PLOT
    # ------------------------------------------------------------------

    def _refresh_scatter_plot(self) -> None:
        if self.frame_stats is None:
            return
        metric_map = {"FWHM": "fwhm", "Roundness": "roundness", "Background": "background",
                      "Stars": "stars", "Weight": "weight"}
        x_key = metric_map.get(self.combo_scatter_x.currentText(), "fwhm")
        y_key = metric_map.get(self.combo_scatter_y.currentText(), "roundness")
        self.scatter_plot.render(self.frame_stats, self.marker, x_key, y_key, self.current_frame)

    def _on_scatter_frame_clicked(self, frame_idx: int) -> None:
        self._show_frame(frame_idx)
        self.right_tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # A/B FRAME TOGGLE
    # ------------------------------------------------------------------

    def _toggle_ab_frame(self) -> None:
        if self._pinned_frame is None:
            self._pinned_frame = self.current_frame
        else:
            target = self._pinned_frame
            self._pinned_frame = self.current_frame
            self._show_frame(target)

    # ------------------------------------------------------------------
    # COPY TO CLIPBOARD
    # ------------------------------------------------------------------

    def _copy_frame_to_clipboard(self) -> None:
        # L2 (v1.2.8 audit-4): copy the composite view (including the
        # side-by-side layout and overlay) instead of only the raw left
        # frame. Users expect "copy" to match the pixels they see.
        pix = self.canvas.grab_composite()
        if pix is not None:
            QApplication.clipboard().setPixmap(pix)

    # ------------------------------------------------------------------
    # THUMBNAIL SIZE
    # ------------------------------------------------------------------

    def _on_thumb_size_changed(self, size: int) -> None:
        for lbl in self.filmstrip._labels:
            lbl.setFixedSize(size, int(size * 0.75))
        # Invalidate the visible-range diff cache: the new item pitch changes
        # which frame indices fall inside a given scroll range, so the
        # incremental "skip already-loaded frames" optimization would otherwise
        # leave stale / mis-scaled thumbnails on the left edge until the user
        # scrolls across them.
        self._prev_visible_range = None
        # Reload visible thumbnails at new size
        QTimer.singleShot(200, self._load_visible_thumbnails)

    # ------------------------------------------------------------------
    # CSV EXPORT
    # ------------------------------------------------------------------

    def _export_csv(self) -> None:
        if self.frame_stats is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Statistics CSV", "frame_statistics.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            # Buffer the entire CSV in memory and issue one write() instead of
            # N+1 write() syscalls (header + one per row). For multi-thousand
            # frame exports this is a large saving on slow disks / network
            # shares where each write round-trips.
            headers = ["Frame", "Weight", "FWHM", "Roundness", "Background", "Stars",
                       "Median", "Sigma", "Date", "Included"]
            lines = [",".join(headers)]
            for row in self.frame_stats.get_all_rows():
                idx = row["frame_idx"]
                incl = "Yes" if self.marker.is_included(idx) else "No"
                lines.append(",".join([
                    str(idx + 1),
                    f"{row.get('weight', 0):.4f}",
                    f"{row['fwhm']:.3f}",
                    f"{row['roundness']:.3f}",
                    f"{row['background']:.6f}",
                    str(row['stars']),
                    f"{row['median']:.6f}",
                    f"{row['sigma']:.6f}",
                    row.get('date_obs', ''),
                    incl,
                ]))
            # utf-8-sig so Excel on Windows (which would otherwise see plain
            # UTF-8 as cp1252) opens the CSV with correct glyphs for
            # non-ASCII filenames / date strings.
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(lines) + "\n")
            QMessageBox.information(self, "Export", f"Statistics exported to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export CSV:\n{e}")

    # ------------------------------------------------------------------
    # GIF EXPORT
    # ------------------------------------------------------------------

    def _export_gif(self) -> None:
        if self.cache is None:
            return
        try:
            from PIL import Image as PILImage
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency",
                                "Pillow is required for GIF export.\nInstall with: pip install Pillow")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Animated GIF", "blink_animation.gif", "GIF files (*.gif)"
        )
        if not path:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Exporting GIF...")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        included_indices = [i for i in range(self.total_frames) if self.marker.is_included(i)]
        total = len(included_indices)
        if total == 0:
            QMessageBox.warning(self, "Export", "No included frames to export.")
            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            return

        GIF_MAX_DIM = 480  # Scale down to limit memory (~0.7 MB per frame at 480px)
        delay_ms = int(1000 / self.fps)
        frames: list = []

        for n, i in enumerate(included_indices):
            qimg = self.cache.get_frame(i)
            if qimg is None:
                continue
            qimg_rgb = qimg.convertToFormat(QImage.Format.Format_RGBX8888)
            w, h = qimg_rgb.width(), qimg_rgb.height()
            ptr = qimg_rgb.bits()
            if ptr is None:
                continue
            ptr.setsize(w * h * 4)
            # .copy() is critical: numpy must own the data (QImage pointer may be freed)
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
            pil_img = PILImage.fromarray(arr[:, :, :3], 'RGB')
            if pil_img.width > GIF_MAX_DIM or pil_img.height > GIF_MAX_DIM:
                pil_img.thumbnail((GIF_MAX_DIM, GIF_MAX_DIM), PILImage.LANCZOS)
            frames.append(pil_img)

            pct = int((n + 1) / max(1, total) * 90)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Exporting GIF... frame {n + 1}/{total}")
            QApplication.processEvents()

        if frames:
            frames[0].save(
                path, save_all=True, append_images=frames[1:],
                duration=delay_ms, loop=0, optimize=True,
            )
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("GIF exported!")
            QMessageBox.information(self, "Export",
                                    f"Animated GIF exported ({len(frames)} frames):\n{path}")
        else:
            QMessageBox.warning(self, "Export", "No frames could be loaded.")

        QTimer.singleShot(1500, lambda: self.progress_bar.setVisible(False))

    # ------------------------------------------------------------------
    # PRELOADING
    # ------------------------------------------------------------------

    def _start_preload(self, start: int, count: int) -> None:
        if self.cache is None:
            return
        # Nothing sensible to preload past the end of the sequence.
        if start >= self.total_frames:
            return
        # L1 (v1.2.8 audit-3): on reverse playback near frame 0, the
        # lookahead math produces start < 0. Without this clamp we'd
        # burn N loop iterations on the "if i < 0: continue" check
        # inside preload_range for nothing. Absorb the negative span
        # into count so we only schedule the useful positive tail.
        if start < 0:
            count += start  # count shrinks by |start|
            start = 0
        # Clamp count so we never ask Siril for non-existent frames — the
        # pool worker can handle a short range cleanly.
        count = min(count, self.total_frames - start)
        if count <= 0:
            return
        # Coalesce preloads: if the previous preload hasn't finished yet, skip
        # this submission. Otherwise, at high FPS every frame advance would
        # pile another task onto the queue and contend with the main thread
        # for Siril's single socket — making playback worse, not better.
        prev = self._preload_future
        if prev is not None and not prev.done():
            return
        # Submit to shared pool — avoids spawning a new thread per frame advance
        self._preload_future = _preload_pool.submit(
            self.cache.preload_range, start, count
        )

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        st = self._settings
        # M4 (v1.2.8 audit-3): _load_settings runs in __init__, BEFORE
        # _deferred_init has built the cache / stats / frame_stats. Any
        # slot connected to these widgets (e.g. the display-mode radios
        # triggering a side-by-side rebuild, the graph checkboxes calling
        # _refresh_statistics_graph) would crash or silently no-op on the
        # missing state. Block signals for the entire restore so setters
        # below never fire handlers. _deferred_init drives the initial
        # render explicitly, so blocking costs us nothing.
        restore_targets = [
            self.spin_fps, self.chk_loop, self.chk_auto_advance,
            self.chk_overlay, self.slider_thumb_size, self.combo_autostretch,
            self.chk_only_included, self.radio_sidebyside, self.radio_normal,
            self.chk_graph_fwhm, self.chk_graph_bg, self.chk_graph_round,
            self.combo_scatter_x, self.combo_scatter_y,
        ]
        prev_blocked = [(w, w.blockSignals(True)) for w in restore_targets]
        try:
            self.spin_fps.setValue(int(st.value("fps", 3)))
            self.chk_loop.setChecked(st.value("loop", True, type=bool))
            self.chk_auto_advance.setChecked(st.value("auto_advance", True, type=bool))
            self.chk_overlay.setChecked(st.value("show_overlay", True, type=bool))
            self.slider_thumb_size.setValue(int(st.value("thumb_size", THUMBNAIL_WIDTH)))
            self.combo_autostretch.setCurrentText(
                st.value("autostretch_preset", DEFAULT_AUTOSTRETCH_PRESET, type=str))
            # Restore additional view-state toggles that the old session-only
            # policy lost on every close. All guarded with safe defaults so a
            # fresh QSettings (first launch) behaves exactly like before.
            self.chk_only_included.setChecked(
                st.value("only_included", False, type=bool))
            if st.value("display_mode", "normal", type=str) == "sidebyside":
                self.radio_sidebyside.setChecked(True)
            else:
                self.radio_normal.setChecked(True)
            self.chk_graph_fwhm.setChecked(st.value("graph_fwhm", True, type=bool))
            self.chk_graph_bg.setChecked(st.value("graph_bg", True, type=bool))
            self.chk_graph_round.setChecked(st.value("graph_round", False, type=bool))
            self.combo_scatter_x.setCurrentText(
                st.value("scatter_x", "FWHM", type=str))
            self.combo_scatter_y.setCurrentText(
                st.value("scatter_y", "Roundness", type=str))
        finally:
            for widget, was_blocked in prev_blocked:
                widget.blockSignals(was_blocked)
        # Restore table sort
        sort_col = int(st.value("table_sort_col", 0))
        sort_order = int(st.value("table_sort_order", 0))
        self.stats_table.table.horizontalHeader().setSortIndicator(
            sort_col, Qt.SortOrder(sort_order))

    def _save_settings(self) -> None:
        st = self._settings
        st.setValue("fps", self.spin_fps.value())
        st.setValue("loop", self.chk_loop.isChecked())
        st.setValue("auto_advance", self.chk_auto_advance.isChecked())
        st.setValue("show_overlay", self.chk_overlay.isChecked())
        st.setValue("thumb_size", self.slider_thumb_size.value())
        st.setValue("autostretch_preset", self.combo_autostretch.currentText())
        # Extended view-state persistence (see matching block in _load_settings)
        st.setValue("only_included", self.chk_only_included.isChecked())
        st.setValue("display_mode",
                    "sidebyside" if self.radio_sidebyside.isChecked() else "normal")
        st.setValue("graph_fwhm", self.chk_graph_fwhm.isChecked())
        st.setValue("graph_bg", self.chk_graph_bg.isChecked())
        st.setValue("graph_round", self.chk_graph_round.isChecked())
        st.setValue("scatter_x", self.combo_scatter_x.currentText())
        st.setValue("scatter_y", self.combo_scatter_y.currentText())
        # Save table sort
        header = self.stats_table.table.horizontalHeader()
        st.setValue("table_sort_col", header.sortIndicatorSection())
        st.setValue("table_sort_order", int(header.sortIndicatorOrder().value))

    def closeEvent(self, event) -> None:
        self._pause()
        self._save_settings()

        # Build session summary
        n_viewed = len(self._frames_viewed)
        n_excluded = len(self.marker.get_excluded_indices())
        n_pending = self.marker.get_pending_count()

        summary_parts = [f"Frames viewed: {n_viewed} / {self.total_frames}"]
        summary_parts.append(f"Currently excluded: {n_excluded}")

        if self.frame_stats is not None:
            fwhm_vals = [self.frame_stats.get(i).get("fwhm", 0)
                         for i in range(self.total_frames)
                         if self.marker.is_included(i) and self.frame_stats.get(i).get("fwhm", 0) > 0]
            if fwhm_vals:
                summary_parts.append(f"Included FWHM: mean {np.mean(fwhm_vals):.2f}\", "
                                     f"best {min(fwhm_vals):.2f}\", worst {max(fwhm_vals):.2f}\"")

        if n_pending > 0:
            # _apply_changes() has its own Yes/Cancel confirmation dialog with
            # the full path + file-move details. On Yes it calls marker.commit()
            # which clears the pending count; on Cancel the count is unchanged.
            self._apply_changes()
            if self.marker.get_pending_count() == n_pending:
                # User cancelled inside _apply_changes → abort close so they
                # can keep working (or explicitly discard marks).
                event.ignore()
                return
        else:
            if n_viewed > 1:
                QMessageBox.information(self, "Session Summary", "\n".join(summary_parts))

        try:
            self.siril.log(f"[BlinkComparator] Session ended. {n_viewed} frames viewed, {n_excluded} excluded.")
        except (SirilError, OSError, RuntimeError):
            pass

        # Cancel any in-flight preload future before tearing Siril down.
        # Otherwise the background worker can finish a `get_seq_frame` after
        # `siril.cmd("close")` and raise a benign-but-noisy exception in
        # the daemon thread (pollutes logs, nothing more).
        #
        # M2 (v1.2.8 audit-3): Future.cancel() is a no-op if the task has
        # already started running (PENDING → CANCELLED only, never
        # RUNNING → CANCELLED). Flip the FrameCache._closing flag so the
        # per-frame loop inside preload_range exits at the next iteration
        # boundary and we don't hit Siril with ~10 more frame loads after
        # the user has already closed the window.
        if self.cache is not None:
            self.cache._closing = True
        if self._preload_future is not None:
            try:
                self._preload_future.cancel()
            except Exception:
                pass
            self._preload_future = None

        # Ask Siril to release the sequence before we remove its files — otherwise
        # Siril keeps file handles open (Windows) or stale cache state (all OSes).
        try:
            self.siril.cmd("close")
        except (SirilError, OSError, RuntimeError) as ex:
            try:
                self.siril.log(f"[BlinkComparator] Siril 'close' returned: {ex}")
            except Exception:
                pass

        try:
            _cleanup_folder_sequence(self._folder_mode_path)
            self.siril.log(
                f"[BlinkComparator] Folder-mode temp sequence cleaned up in {self._folder_mode_path}"
            )
        except Exception as ex:
            try:
                self.siril.log(f"[BlinkComparator] Cleanup warning: {ex}")
            except Exception:
                pass

        super().closeEvent(event)

    # ------------------------------------------------------------------
    # COFFEE DIALOG
    # ------------------------------------------------------------------

    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"
        dlg = QDialog(self)
        dlg.setWindowTitle("\u2615 Support Blink Comparator")
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
            "<span style='font-size:48pt;'>\u2615</span><br>"
            "<span style='font-size:18pt; font-weight:bold; color:#FFDD00;'>"
            "Buy me a Coffee</span><br><br>"
            "<b style='color:#e0e0e0;'>Enjoying the Blink Comparator?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If this tool has saved you time, helped you spot bad frames, "
            "or made your frame selection workflow better \u2014 consider buying "
            "me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>\u2615 Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br><br>"
            "<span style='color:#aaaaaa;'>Your support helps maintain:</span><br>"
            "\u2022 Gradient Analyzer \u2022 Blink Comparator<br>"
            "\u2022 Multiple Histogram Viewer \u2022 Script Security Scanner<br>"
            "</div>"
        )
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)
        layout.addSpacing(8)

        btn_open = QPushButton("\u2615  Buy me a Coffee  \u2615")
        btn_open.setStyleSheet(
            "QPushButton{background-color:#FFDD00;color:#000000;font-size:14pt;"
            "font-weight:bold;padding:12px 24px;border-radius:8px;border:2px solid #ccb100}"
            "QPushButton:hover{background-color:#ffe740;border-color:#ddcc00}"
        )
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BMC_URL)))
        layout.addWidget(btn_open)
        layout.addSpacing(4)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton{background-color:#444;color:#ddd;border:1px solid #666;padding:6px}"
            "QPushButton:hover{background-color:#555}"
        )
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        footer = QLabel(
            f"<div style='text-align:center; line-height:1.8;'>"
            f"<a style='color:#88aaff; font-size:12pt;' href='{BMC_URL}'>{BMC_URL}</a><br>"
            f"<span style='font-size:13pt; color:#999;'>"
            f"Thank you for supporting open-source astrophotography tools!<br>"
            f"Clear skies \u2728</span></div>"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        footer.setOpenExternalLinks(True)
        layout.addWidget(footer)
        dlg.exec()

    # ------------------------------------------------------------------
    # HELP DIALOG
    # ------------------------------------------------------------------

    def _show_help_dialog(self) -> None:
        from PyQt6.QtWidgets import QTextEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Blink Comparator \u2014 Help")
        dlg.setMinimumSize(850, 650)
        layout = QVBoxLayout(dlg)

        base_style = (
            "font-size: 13pt; color: #e0e0e0; background: #1e1e1e;"
            " font-family: 'Helvetica Neue', Helvetica, Arial; padding: 12px;"
        )
        mono_style = (
            "font-size: 10pt; color: #e0e0e0; background: #1e1e1e;"
            " font-family: 'Courier New', monospace; padding: 10px;"
        )

        tabs = QTabWidget()

        # ---- Tab 1: Getting Started ----
        te_start = QTextEdit()
        te_start.setReadOnly(True)
        te_start.setStyleSheet(base_style)
        te_start.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f680 Getting Started</b><br><br>"

            "<b style='color:#ffcc66;'>What is frame selection?</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "After stacking, not all sub-exposures are equal. Some have:<br>"
            "\u2022 <b>Satellite trails</b> \u2014 bright streaks across the frame<br>"
            "\u2022 <b>Clouds or haze</b> \u2014 higher background, fewer stars<br>"
            "\u2022 <b>Tracking errors</b> \u2014 elongated or trailed stars<br>"
            "\u2022 <b>Focus drift</b> \u2014 gradually increasing FWHM over time<br>"
            "\u2022 <b>Wind gusts</b> \u2014 sudden star elongation in a few frames<br><br>"
            "Removing these <b>before</b> stacking (or re-stacking without them) "
            "significantly improves your final image. This tool helps you find "
            "and reject them quickly."
            "</div><br>"

            "<b style='color:#ffcc66;'>Quick Start \u2014 4 Steps</b><br>"
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border:1px solid #3a5a7a;'>"
            "<b>1.</b> Run <b>Blink Comparator</b> from Processing \u2192 Scripts "
            "and pick a folder of FITS frames.<br>"
            "<b>2.</b> Let it build the temp sequence \u2014 optionally tick "
            "<i>Register frames for statistics</i> in the folder picker to get "
            "FWHM / Roundness / Stars / Background data.<br>"
            "<b>3.</b> Go to the <b>Statistics Table</b> tab, sort by FWHM, "
            "and reject the worst frames with <b>B</b> (auto-advances).<br>"
            "<b>4.</b> Click <b style='color:#88aaff;'>Apply Rejections &amp; Close</b> "
            "\u2014 this writes <code>rejected_frames.txt</code>, moves the rejected "
            "FITS into a <code>rejected/</code> subfolder, and closes the window.</div><br>"

            "<b style='color:#ffcc66;'>Alternative: Data-Driven Batch Reject</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Instead of marking frames one by one, use:<br>"
            "\u2022 <b>Batch Selection:</b> Reject all frames where FWHM > 4.5<br>"
            "\u2022 <b>Reject Worst N%:</b> Reject the worst 10% by FWHM<br>"
            "\u2022 <b>Approval Expression:</b> FWHM < 4.5 AND Roundness > 0.7 AND Stars > 50<br>"
            "\u2022 <b>Multi-select in table:</b> Ctrl+click rows \u2192 right-click \u2192 Reject"
            "</div><br>"

            "<b style='color:#ffcc66;'>Keyboard Shortcuts</b><br>"
            "<table style='color:#cccccc;'>"
            "<tr><td style='padding:2px 8px;'><b>Space</b></td><td>Play / Pause</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>\u2190 / \u2192</b></td><td>Previous / Next frame</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Home / End</b></td><td>First / Last frame</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>G</b></td><td>Mark good (include)</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>B</b></td><td>Mark bad (exclude)</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Z</b></td><td>Reset zoom</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>T</b></td><td>Pin / toggle A/B comparison</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Ctrl+Z</b></td><td>Undo (single or batch)</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Ctrl+C</b></td><td>Copy frame to clipboard</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>1\u20139</b></td><td>Set FPS directly</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>+ / \u2212</b></td><td>Speed up / slow down</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Esc</b></td><td>Close</td></tr>"
            "</table><br>"

            "<b style='color:#ffcc66;'>Settings</b><br>"
            "All settings (FPS, loop, auto-advance, overlay, thumbnail size, "
            "autostretch preset, table sort) are automatically saved between "
            "sessions."
        )
        tabs.addTab(te_start, "\U0001f680 Getting Started")

        # ---- Tab 2: Tabs & Visualizations ----
        te_tabs = QTextEdit()
        te_tabs.setReadOnly(True)
        te_tabs.setStyleSheet(base_style)
        te_tabs.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f4ca Tabs & Visualizations</b><br><br>"

            "<b style='color:#ffcc66;'>Viewer</b><br>"
            "The main frame display. Controls: scroll wheel to zoom, right-click "
            "drag to pan, Z to reset. The frame info overlay (top-left corner) shows "
            "frame number, FWHM, roundness, and quality weight.<br><br>"

            "<b style='color:#ffcc66;'>Statistics Table</b><br>"
            "All frames listed with sortable columns: <b>Weight, FWHM, Roundness, "
            "Background, Stars, Median, Sigma, Date, Status</b>.<br>"
            "\u2022 Click any <b>column header</b> to sort (click again to reverse).<br>"
            "\u2022 Click a <b>row</b> to jump to that frame in the viewer.<br>"
            "\u2022 <b>Ctrl+click</b> or <b>Shift+click</b> to multi-select, then "
            "right-click \u2192 'Reject selected'.<br>"
            "\u2022 <b>Sort by FWHM descending</b> to instantly see the worst frames at the top.<br>"
            "\u2022 <b>Sort by Weight ascending</b> to see the lowest-quality frames first.<br><br>"

            "<b style='color:#ffcc66;'>Statistics Graph</b><br>"
            "FWHM, Background, and Roundness plotted as line charts across all frames. "
            "Toggleable via checkboxes above the graph.<br>"
            "\u2022 <b>Thin line</b> = raw values per frame<br>"
            "\u2022 <b>Bold line</b> = 7-frame running average (trend)<br>"
            "\u2022 <b>Red dots</b> = excluded frames<br>"
            "\u2022 <b>White dashed line</b> = your current frame position<br>"
            "Great for spotting: <b>focus drift</b> (FWHM ramp), <b>clouds</b> "
            "(background spike), <b>tracking degradation</b> (roundness drop).<br><br>"

            "<b style='color:#ffcc66;'>Scatter Plot</b><br>"
            "2D scatter of any two metrics (select X and Y with the dropdowns). "
            "Outlier frames are immediately visible as dots far from the main cluster.<br>"
            "\u2022 <span style='color:#55cc55;'><b>Green dots</b></span> = included frames<br>"
            "\u2022 <span style='color:#dd4444;'><b>Red X</b></span> = excluded frames<br>"
            "\u2022 <span style='color:#ffd700;'><b>Yellow star</b></span> = current frame (always on top)<br>"
            "\u2022 <b>Click a dot</b> to jump to that frame<br>"
            "Best combinations: <b>FWHM vs Roundness</b> (star quality), "
            "<b>FWHM vs Background</b> (clouds + seeing).<br><br>"

            "<b style='color:#ffcc66;'>Filmstrip</b><br>"
            "Horizontal thumbnail strip at the bottom (always visible). "
            "Color-coded borders: green = included, red = excluded, blue = current. "
            "Click any thumbnail to jump. Thumbnails load lazily as you scroll. "
            "Adjust size with the <b>Thumbs</b> slider in the zoom bar above the viewer."
        )
        tabs.addTab(te_tabs, "\U0001f4ca Tabs")

        # ---- Tab 3: Metrics & Statistics ----
        te_metrics = QTextEdit()
        te_metrics.setReadOnly(True)
        te_metrics.setStyleSheet(base_style)
        te_metrics.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f4cf Metrics & Statistics</b><br><br>"

            "The Statistics Table shows ten columns for every frame. Here is what "
            "each metric means, where the data comes from, and how to interpret the "
            "values for astrophotography frame selection.<br><br>"

            # ---- FWHM ----
            "<b style='color:#ffcc66;'>FWHM (Full Width at Half Maximum)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> The diameter of stars measured at half their peak "
            "brightness (in pixels). A smaller FWHM means sharper, tighter stars.<br>"
            "<b>Source:</b> Siril registration data (<span style='font-family:monospace;'>"
            "get_seq_regdata</span>). Requires star detection to have been run.<br>"
            "<b>Good values:</b> Depends on your focal length and seeing, but lower "
            "is always better. Typical range: 2\u20136 px for most setups.<br>"
            "<b>What to watch for:</b> A sudden increase indicates <b>focus drift</b>, "
            "<b>wind gusts</b>, or <b>poor seeing</b>. A gradual ramp across frames "
            "often indicates thermal focus shift.</div><br>"

            # ---- Roundness ----
            "<b style='color:#ffcc66;'>Roundness</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> How circular the stars are, on a scale of 0 to 1 "
            "(1.0 = perfect circle, 0.0 = a line). Related to eccentricity: "
            "<span style='font-family:monospace;'>ecc \u2248 1 \u2212 roundness</span>.<br>"
            "<b>Source:</b> Siril registration data.<br>"
            "<b>Good values:</b> Above 0.75 is generally good. Below 0.6 usually "
            "indicates problems.<br>"
            "<b>What to watch for:</b> Low roundness means <b>tracking errors</b> "
            "(elongated stars), <b>wind</b>, or <b>optical problems</b> (tilt, coma). "
            "If roundness drops in a group of frames, check for a wind gust or mount hiccup."
            "</div><br>"

            # ---- Background ----
            "<b style='color:#ffcc66;'>Background Level (BG Level)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> The median pixel value of the frame's sky background, "
            "normalized to [0, 1]. Lower = darker sky.<br>"
            "<b>Source:</b> Siril registration data (<span style='font-family:monospace;'>"
            "background_lvl</span>) or, if unavailable, <span style='font-family:monospace;'>"
            "stats.median</span> as fallback.<br>"
            "<b>Good values:</b> Consistent across frames. The absolute value depends "
            "on your light pollution, camera gain, and exposure length.<br>"
            "<b>What to watch for:</b> A sharp <b>spike</b> = clouds, airplane lights, "
            "or the moon moving into the field. A <b>rising trend</b> = dawn approaching "
            "or increasing light pollution (e.g. stadium lights turning on).</div><br>"

            # ---- Stars ----
            "<b style='color:#ffcc66;'>Stars (Star Count)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> Number of stars detected in the frame.<br>"
            "<b>Source:</b> Siril registration data (<span style='font-family:monospace;'>"
            "number_of_stars</span>).<br>"
            "<b>Good values:</b> Consistent count across frames. Higher is generally "
            "better, but the absolute number depends on your field of view and focal length.<br>"
            "<b>What to watch for:</b> A <b>sudden drop</b> = clouds obscuring the field, "
            "dew on the optics, or severe defocus. A <b>gradual decline</b> may indicate "
            "thin clouds or rising humidity.</div><br>"

            # ---- Weight ----
            "<b style='color:#ffcc66;'>Weight (Composite Quality Score)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> A single quality score from 0 to 1 that combines "
            "FWHM, Roundness, Background, and Stars into one number. Higher = better.<br>"
            "<b>Formula:</b><br>"
            "<span style='font-family:monospace; color:#aaffaa; background:#1a3a1a; "
            "padding:2px 4px;'>"
            "w_fwhm  = 1 \u2212 (fwhm \u2212 min) / (max \u2212 min)<br>"
            "w_round = roundness<br>"
            "w_bg    = 1 \u2212 (bg \u2212 min) / (max \u2212 min)<br>"
            "w_stars = sqrt(stars) / sqrt(max_stars)<br>"
            "Weight  = mean of available factors</span><br><br>"
            "<b>How to use it:</b> Sort by Weight ascending to see the worst frames "
            "first. Use 'Reject worst N%' with Weight to cull the lowest-quality "
            "subframes in one click. This is comparable to PixInsight's PSFSignalWeight, "
            "though with a simpler, transparent formula.</div><br>"

            # ---- Median ----
            "<b style='color:#ffcc66;'>Median</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> The median pixel value of the entire frame "
            "(normalized to [0, 1]). Represents the 'typical' brightness of a pixel.<br>"
            "<b>Source:</b> Siril per-channel statistics (<span style='font-family:monospace;'>"
            "get_seq_stats</span>). Always available, even without star detection.<br>"
            "<b>How to use it:</b> Nearly identical to Background Level for typical "
            "astro images (where the sky dominates). Useful as a fallback when "
            "registration data is unavailable.</div><br>"

            # ---- Sigma ----
            "<b style='color:#ffcc66;'>Sigma (\u03c3)</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> Standard deviation of pixel values in the frame. "
            "A measure of how much the pixel values vary \u2014 roughly proportional "
            "to signal + noise.<br>"
            "<b>Source:</b> Siril per-channel statistics.<br>"
            "<b>How to use it:</b> Higher sigma can indicate more signal (good) "
            "or more noise (bad). Compare with other metrics: if sigma is high AND "
            "background is high, it's noise from clouds. If sigma is high AND "
            "background is low, it's genuine deep-sky signal.</div><br>"

            # ---- Date ----
            "<b style='color:#ffcc66;'>Date</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> The observation timestamp from the FITS header "
            "(<span style='font-family:monospace;'>DATE-OBS</span> keyword).<br>"
            "<b>Source:</b> FITS file metadata via <span style='font-family:monospace;'>"
            "get_seq_imgdata</span>.<br>"
            "<b>Note:</b> Not all cameras write DATE-OBS (e.g. SeeStar S50 may leave "
            "this empty). When unavailable, the column shows '\u2014'.</div><br>"

            # ---- Status ----
            "<b style='color:#ffcc66;'>Status</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "<b>What it is:</b> Shows <span style='color:#55aa55;'>Included</span> or "
            "<span style='color:#dd4444;'>Excluded</span> for each frame.<br>"
            "<b>Note:</b> Marks are <b>local</b> until you click 'Apply Rejections'. "
            "The pending counter shows how many frames are marked but not yet "
            "exported.</div><br>"

            # ---- Star Detection ----
            "<b style='color:#ffcc66; font-size:12pt;'>"
            "\u2b50 Star Detection (required for FWHM, Roundness, Stars)</b><br>"
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border:1px solid #3a5a7a;'>"
            "If the FWHM, Roundness, Stars, and Weight columns are empty, "
            "star detection has not been run on the sequence. Click the yellow "
            "<b>'Run Star Detection'</b> banner at the top of the window.<br><br>"
            "This executes Siril's <span style='font-family:monospace;'>register "
            "&lt;seq&gt; -2pass</span> command, which:<br>"
            "\u2022 Detects stars in every frame<br>"
            "\u2022 Computes FWHM, roundness, background, and star count<br>"
            "\u2022 Stores results in the .seq file (persistent)<br>"
            "\u2022 Does <b>not</b> create new output files (no r_ prefix added)<br><br>"
            "<b>Note:</b> For RGB images, Siril stores registration data on the "
            "<b>green channel</b> (highest SNR). The script automatically scans "
            "all channels to find the data.<br><br>"
            "<b>Median and Sigma</b> are always available from Siril's basic "
            "per-channel statistics \u2014 no star detection needed."
            "</div>"
        )
        tabs.addTab(te_metrics, "\U0001f4cf Metrics")

        # ---- Tab 4: Frame Selection ----
        te_select = QTextEdit()
        te_select.setReadOnly(True)
        te_select.setStyleSheet(base_style)
        te_select.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f5d1\ufe0f Frame Selection</b><br><br>"

            "<b style='color:#ffcc66;'>Manual Marking</b><br>"
            "<div style='background:#252525; padding:8px; border-radius:4px;'>"
            "Press <b style='color:#55aa55;'>G</b> to mark a frame as <b>good</b> (include).<br>"
            "Press <b style='color:#dd4444;'>B</b> to mark a frame as <b>bad</b> (exclude).<br>"
            "With <b>Auto-advance</b> enabled (default), the viewer automatically "
            "jumps to the next frame after marking \u2014 you can rapidly scrub through "
            "a sequence pressing B on each bad frame.</div><br>"

            "<b style='color:#ffcc66;'>Batch Selection</b><br>"
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border:1px solid #3a5a7a;'>"
            "<b>Threshold filter:</b> Choose a metric (FWHM, Background, Roundness), "
            "an operator (>, <, >=, <=), and a value. The preview shows how many "
            "frames match. Click 'Reject Matching' to exclude them all.<br><br>"
            "<b>Worst N%:</b> Reject the worst 10% (or any %) of frames by the selected "
            "metric. For FWHM and Background, worst = highest value. For Roundness, "
            "worst = lowest value.</div><br>"

            "<b style='color:#ffcc66;'>Approval Expression</b><br>"
            "<div style='background:#1a2a3a; padding:10px; border-radius:6px;"
            " border:1px solid #3a5a7a;'>"
            "Define multiple conditions that good frames must satisfy (AND logic):<br>"
            "<span style='color:#aaffaa; background:#1a3a1a; padding:2px 4px;"
            " font-family:monospace;'>FWHM < 4.5 AND Roundness > 0.7 AND Stars > 50</span><br><br>"
            "Click '+ Add Condition' to add more rules. 'Reject Non-Matching' excludes "
            "all frames that fail <b>any</b> condition. This is comparable to PixInsight's "
            "SubframeSelector approval expressions.</div><br>"

            "<b style='color:#ffcc66;'>Quality Weight</b><br>"
            "Each frame gets a composite quality score (0\u20131) computed from:<br>"
            "\u2022 <b>FWHM</b> (lower = better) \u2014 inverted, normalized to range<br>"
            "\u2022 <b>Roundness</b> (higher = better) \u2014 used directly<br>"
            "\u2022 <b>Background</b> (lower = better) \u2014 inverted, normalized<br>"
            "\u2022 <b>Stars</b> (more = better) \u2014 normalized to max<br>"
            "Sort the Statistics Table by Weight to instantly see the best and worst frames.<br><br>"

            "<b style='color:#ffcc66;'>Undo</b><br>"
            "Press <b>Ctrl+Z</b> to undo the last marking. Single marks undo one at a time. "
            "Batch operations (threshold reject, worst N%, approval expression, multi-select) "
            "undo the entire batch with a single Ctrl+Z.<br><br>"

            "<b style='color:#ffcc66;'>Reset All Rejections</b><br>"
            "Button in the <b>Frame Marking</b> group. Marks every frame as "
            "Included again and clears the undo history \u2014 useful if you want "
            "to start frame selection over without re-loading the folder. Files "
            "on disk are not touched. This cannot be undone itself.<br><br>"

            "<b style='color:#ffcc66;'>Applying Rejections</b><br>"
            "All marks are <b>local</b> until you click "
            "<b style='color:#88aaff;'>Apply Rejections &amp; Close</b> (or close "
            "the window with the X button). That writes "
            "<code>rejected_frames.txt</code> into the source folder and moves "
            "the rejected FITS files into a <code>rejected/</code> subfolder, then "
            "cleans up the temp sequence. The pending count in the left panel "
            "shows how many marks are queued. You get a final Yes/Cancel "
            "confirmation before anything touches the disk."
        )
        tabs.addTab(te_select, "\U0001f5d1\ufe0f Selection")

        # ---- Tab 4: Display Modes & Options ----
        te_options = QTextEdit()
        te_options.setReadOnly(True)
        te_options.setStyleSheet(base_style)
        te_options.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\u2699\ufe0f Display Modes & Options</b><br><br>"

            "<b style='color:#ffcc66;'>Display Modes</b><br>"
            "Radio buttons in the left panel:<br>"
            "\u2022 <b>Normal</b> \u2014 single-frame autostretched view. Default. Use for "
            "general inspection and playback.<br>"
            "\u2022 <b>Side by Side (vs. reference)</b> \u2014 current frame on the left, "
            "the sequence reference frame on the right. Both zoom and pan together. "
            "Good for detailed comparison against the sharpest/best frame (reference "
            "is picked by Siril during <code>register -2pass</code>; falls back to "
            "frame 0 if registration was skipped).<br><br>"

            "<b style='color:#ffcc66;'>Playback Options</b><br>"
            "In the <b>Playback</b> group in the left panel:<br>"
            "\u2022 <b>Loop playback</b> \u2014 restart from frame 1 after reaching the end.<br>"
            "\u2022 <b>Only included frames</b> \u2014 during playback, skip past "
            "frames you have marked as rejected. Useful after a batch reject to "
            "verify what's left. Manual \u2190 / \u2192 navigation still steps by 1 "
            "so you can review excluded frames and undo if needed.<br><br>"

            "<b style='color:#ffcc66;'>Autostretch Preset (Zoom Bar)</b><br>"
            "Dropdown labelled <b>Stretch:</b> in the zoom bar above the viewer. "
            "Choices:<br>"
            "\u2022 <b>Conservative</b> \u2014 darker background, preserves dim detail "
            "(shadows_clip \u2212 3.5 MAD, target 0.20).<br>"
            "\u2022 <b>Default</b> \u2014 matches Siril/PixInsight STF defaults "
            "(shadows_clip \u2212 2.8 MAD, target 0.25).<br>"
            "\u2022 <b>Aggressive</b> \u2014 brighter, higher contrast "
            "(shadows_clip \u2212 1.5 MAD, target 0.35).<br>"
            "\u2022 <b>Linear</b> \u2014 no MTF stretch; raw data clipped to [0, 1].<br>"
            "The selected preset is applied to every frame and every filmstrip "
            "thumbnail, and persists between sessions.<br><br>"

            "<b style='color:#ffcc66;'>Linked Autostretch</b><br>"
            "All frames share the same median + MAD, sampled across the sequence "
            "at startup. That means brightness differences between frames stay "
            "visible \u2014 critical for spotting clouds, haze, and dew. There is "
            "no toggle; this is the only autostretch mode.<br><br>"

            "<b style='color:#ffcc66;'>Frame Info Overlay (Zoom Bar)</b><br>"
            "Checkbox labelled <b>Overlay</b> in the zoom bar. When on, the frame "
            "number, FWHM, roundness, and quality weight are burned into the "
            "top-left corner of the image. Useful during playback so you don't "
            "have to look away from the viewer.<br><br>"

            "<b style='color:#ffcc66;'>Thumbnail Size (Zoom Bar)</b><br>"
            "Slider labelled <b>Thumbs:</b> in the zoom bar (40\u2013160 px). "
            "Larger = easier to see, smaller = more frames fit on screen.<br><br>"

            "<b style='color:#ffcc66;'>Zoom & Pan</b><br>"
            "\u2022 <b>Scroll wheel:</b> zoom in/out (0.1\u00d7 to 20\u00d7)<br>"
            "\u2022 <b>Right-click + drag:</b> pan the zoomed image<br>"
            "\u2022 <b>Z key</b> or <b>Fit-in-Window button:</b> reset zoom to fit the viewer<br>"
            "Both the main frame and the side-by-side reference share the same "
            "zoom and pan state."
        )
        tabs.addTab(te_options, "\u2699\ufe0f Options")

        # ---- Tab 5: What to Look For ----
        te_look = QTextEdit()
        te_look.setReadOnly(True)
        te_look.setStyleSheet(base_style)
        te_look.setHtml(
            "<b style='color:#88aaff; font-size:16pt;'>"
            "\U0001f50d What to Look For</b><br><br>"

            "<b style='color:#ff6644;'>Satellite Trails</b><br>"
            "Bright streaks crossing the frame, usually diagonal. Play the "
            "sequence at 3\u20135 FPS \u2014 trails flash in a single frame and "
            "are easy to spot against the otherwise static star field. "
            "Reject the affected frame.<br><br>"

            "<b style='color:#dd6644;'>Clouds & Haze</b><br>"
            "Overall brightness increase in affected frames. Check the "
            "<b>Statistics Graph</b> \u2014 background level spikes indicate "
            "cloud passage. Haze causes gradual background increase + star "
            "count drop. Sort table by Background (descending) to find them.<br><br>"

            "<b style='color:#dd6644;'>Tracking Errors</b><br>"
            "Sudden star elongation in a few frames. Visible as stretched or "
            "double stars. Check <b>Roundness</b> column \u2014 low roundness = "
            "elongated stars. Use <b>Scatter Plot</b> (FWHM vs Roundness) to "
            "see outliers far from the main cluster.<br><br>"

            "<b style='color:#ffaa33;'>Focus Drift</b><br>"
            "Gradually increasing FWHM over time. Check the <b>Statistics Graph</b> "
            "\u2014 if the FWHM running average shows an upward slope, focus "
            "drifted during the session. Consider rejecting the last N frames "
            "where FWHM exceeds your threshold.<br><br>"

            "<b style='color:#ffaa33;'>Wind Gusts</b><br>"
            "Isolated frames with poor FWHM or roundness surrounded by good "
            "frames. The <b>Statistics Graph</b> shows these as sudden spikes. "
            "Best strategy: sort by FWHM, reject the worst 5\u201310%.<br><br>"

            "<b style='color:#ffaa33;'>Airplane Lights</b><br>"
            "Blinking or moving bright spots. Best seen by playing at 3\u20135 FPS "
            "in Normal mode. Affected frames usually have a bright spot that "
            "moves across the field.<br><br>"

            "<b style='color:#88aaff;'>Dew / Frost</b><br>"
            "Gradual increase in background brightness and FWHM toward the end "
            "of a session. The <b>Statistics Graph</b> shows both metrics rising "
            "in parallel. Reject the affected frames (usually the last batch).<br><br>"

            "<b style='color:#88aaff;'>Tips</b><br>"
            "\u2022 Start with the <b>Statistics Table</b> \u2014 data is faster than visual inspection.<br>"
            "\u2022 Use <b>Batch reject</b> for systematic issues (FWHM > threshold).<br>"
            "\u2022 Play at 3\u20135 FPS to spot visual artifacts (satellites, airplanes) \u2014 "
            "they flash in a single frame against the static star field.<br>"
            "\u2022 Check the <b>Scatter Plot</b> for outliers that single metrics might miss.<br>"
            "\u2022 Re-stack after rejecting frames \u2014 even removing 5% of bad subs "
            "can dramatically improve the final result."
        )
        tabs.addTab(te_look, "\U0001f50d Look For")

        # ---- Tab 6: Export & Reference ----
        te_ref = QTextEdit()
        te_ref.setReadOnly(True)
        te_ref.setStyleSheet(mono_style)
        te_ref.setPlainText(
            "Blink Comparator \u2014 Technical Reference\n"
            "==========================================\n\n"
            "Developed by Sven Ramuschkat\n"
            "Web: www.svenesis.org\n"
            "GitHub: https://github.com/sramuschkat/Siril-Scripts\n\n"
            "EXPORT OPTIONS\n"
            "  Export CSV...        Save full statistics table as .csv\n"
            "  Export GIF...        Save animated blink as .gif (480px, included frames)\n"
            "  Ctrl+C               Copy current frame image to clipboard\n\n"
            "QUALITY WEIGHT FORMULA\n"
            "  For each frame, four metrics are normalized to [0, 1]:\n"
            "    w_fwhm  = 1 - (fwhm - min) / (max - min)     [lower = better]\n"
            "    w_round = roundness                            [higher = better]\n"
            "    w_bg    = 1 - (bg - min) / (max - min)        [lower = better]\n"
            "    w_stars = stars / max_stars                    [more = better]\n"
            "  Weight = mean of available factors (0-1 range).\n"
            "  Metrics with zero values are excluded from the computation.\n\n"
            "AUTOSTRETCH (Midtone Transfer Function)\n"
            "  Matches Siril/PixInsight's STF autostretch.\n"
            "  shadows = max(0, median + shadows_clip * MAD), highlight = 1.0\n"
            "  midtone computed so target_median -> 0.25 in output\n"
            "  Global (median, MAD) sampled from 10 frames across the sequence\n"
            "  and shared by every frame and every thumbnail (linked mode).\n"
            "  Presets: Conservative / Default / Aggressive / Linear.\n\n"
            "WORKFLOW (folder mode)\n"
            "  1. Pick a folder of FITS files at startup.\n"
            "  2. Siril runs 'cd <folder>' + 'convert svenesis_blink -fitseq'\n"
            "     and optionally 'register svenesis_blink -2pass'.\n"
            "  3. Marks are kept locally (pending) until Apply.\n"
            "  4. Apply writes rejected_frames.txt next to the source FITS and\n"
            "     moves rejected files into a 'rejected/' subfolder.\n"
            "  5. On close, siril.cmd('close') is called and the temp sequence\n"
            "     files (svenesis_blink.seq, .fit, _conversion.txt, cache/) are\n"
            "     deleted. Original FITS files are never modified.\n\n"
            "FRAME CACHE\n"
            "  LRU cache (80 frames default) with thread-safe double-check locking.\n"
            "  One shared background worker preloads frames around the current one.\n"
            "  Separate thumbnail cache (200 entries) for the filmstrip.\n\n"
            "SIRIL API CALLS\n"
            "  get_seq()               Load sequence metadata\n"
            "  get_seq_frame()         Load frame pixel data (with_pixels=True)\n"
            "  get_seq_regdata()       Registration data (FWHM, roundness, stars, BG)\n"
            "  get_seq_stats()         Per-channel statistics (median, sigma, MAD)\n"
            "  get_seq_imgdata()       Frame metadata (date_obs, inclusion)\n"
            "  cmd('convert', ...)     Build the FITSEQ temp sequence\n"
            "  cmd('register', ...)    Run -2pass star detection / registration\n"
            "  cmd('close')            Release the sequence before cleanup\n\n"
            "REQUIREMENTS\n"
            "  Siril 1.4+ with Python script support\n"
            "  sirilpy (bundled), numpy, PyQt6, matplotlib\n"
            "  Optional: Pillow (for GIF export)\n\n"
            "KEYBOARD SHORTCUTS (FULL LIST)\n"
            "  Space       Play / Pause\n"
            "  Left/Right  Previous / Next frame (steps by 1, ignores 'only-included')\n"
            "  Home/End    First / Last frame\n"
            "  G           Mark good (include)\n"
            "  B           Mark bad (exclude)\n"
            "  Z           Reset zoom (fit-to-window)\n"
            "  T           Pin / toggle A/B frame comparison\n"
            "  Ctrl+Z      Undo last marking (single or batch)\n"
            "  Ctrl+C      Copy current frame to clipboard\n"
            "  1-9         Set FPS directly\n"
            "  + / -       Speed up / slow down\n"
            "  Esc         Close (same as the Apply Rejections & Close button)\n"
        )
        tabs.addTab(te_ref, "\U0001f4d6 Reference")

        layout.addWidget(tabs)
        lbl_guide = QLabel(
            '<span style="font-size:10pt;">📖 '
            '<a href="https://github.com/sramuschkat/Siril-Scripts/blob/main/'
            'Instructions/Svenesis-BlinkComparator-Instructions.md"'
            ' style="color:#88aaff;">Full User Guide (online)</a></span>'
        )
        lbl_guide.setOpenExternalLinks(True)
        layout.addWidget(lbl_guide)
        btn = QPushButton("Close")
        btn.setStyleSheet(
            "QPushButton{background-color:#444;color:#ddd;border:1px solid #666;"
            "padding:6px;font-weight:bold;border-radius:4px}"
            "QPushButton:hover{background-color:#555}"
        )
        _nofocus(btn)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


# ==============================================================================
# FOLDER MODE — build a temp sequence from loose FITS files
# ==============================================================================

FOLDER_MODE_SEQNAME = "svenesis_blink"
FITS_EXTENSIONS = (".fit", ".fits", ".fts")


def _scan_fits_files(folder: str) -> list[str]:
    """Return sorted list of FITS filenames (basenames only) in folder, case-insensitive."""
    found: list[str] = []
    try:
        for name in os.listdir(folder):
            if name.lower().endswith(FITS_EXTENSIONS):
                found.append(name)
    except OSError:
        return []
    return sorted(found)


def _show_welcome_dialog(parent=None) -> bool:
    """Intro dialog explaining the workflow. Returns True if user wants to continue."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Blink Comparator v{VERSION}")
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
        "<span style='font-size:28pt;'>\U0001F31F</span><br>"
        "<span style='font-size:20pt;font-weight:bold;color:#88aaff;'>"
        "Welcome to Blink Comparator</span>"
        "</div>"
    )
    title.setTextFormat(Qt.TextFormat.RichText)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    body = QLabel(
        "<div style='font-size:12pt;line-height:1.55;'>"
        "This tool helps you inspect a folder of FITS frames as a blink "
        "animation to quickly spot satellite trails, clouds, tracking errors, "
        "focus drift and other bad frames."
        "<br><br>"
        "<b style='color:#FFDD00;'>What happens next:</b>"
        "<ol style='margin-top:4px;'>"
        "<li>Pick a folder containing your FITS files "
        "(<code>.fit</code> / <code>.fits</code> / <code>.fts</code>).</li>"
        "<li>Siril builds a temporary FITSEQ sequence "
        f"(<code>{FOLDER_MODE_SEQNAME}</code>) from those files.</li>"
        "<li>Optionally registers the frames to extract FWHM, roundness "
        "and background statistics.</li>"
        "<li>The viewer opens — play / step through frames, mark bad ones "
        "with <b>B</b>, good ones with <b>G</b>, undo with <b>Ctrl+Z</b>.</li>"
        "<li>Apply writes <code>rejected_frames.txt</code> and can move "
        "rejected files into a <code>rejected/</code> subfolder.</li>"
        "</ol>"
        "<b style='color:#FFDD00;'>On close</b> the temp sequence, its "
        "conversion log and the Siril <code>cache/</code> directory are "
        "removed automatically — your original files are never modified "
        "unless you explicitly say so."
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
    btn_start = QPushButton("Select Folder \u2192")
    btn_start.setStyleSheet(
        "padding:8px 20px;font-weight:bold;border-radius:4px;"
        "background-color:#285299;color:white;"
    )
    btn_start.setDefault(True)
    btn_start.clicked.connect(dlg.accept)
    btn_row.addWidget(btn_start)
    layout.addLayout(btn_row)

    return dlg.exec() == QDialog.DialogCode.Accepted


def _prompt_load_folder(parent=None) -> tuple[str, bool] | None:
    """Prompt for a folder of FITS files. Returns (folder_path, register_yes_no) or None if cancelled."""
    if not _show_welcome_dialog(parent):
        return None

    folder = QFileDialog.getExistingDirectory(
        parent,
        "Blink Comparator — Select Folder of FITS Files"
    )
    if not folder:
        return None

    files = _scan_fits_files(folder)
    if not files:
        QMessageBox.warning(
            parent, "No FITS Files Found",
            f"No {', '.join(FITS_EXTENSIONS)} files were found in:\n{folder}"
        )
        return None

    # Confirm + register checkbox
    dlg = QDialog(parent)
    dlg.setWindowTitle("Load Folder")
    dlg.setStyleSheet("QDialog{background-color:#2b2b2b;color:#cccccc;}"
                      "QLabel{color:#cccccc;}"
                      "QCheckBox{color:#cccccc;}")
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(
        f"Found <b>{len(files)}</b> FITS file(s) in:<br>"
        f"<code>{folder}</code><br><br>"
        f"A temporary sequence named <code>{FOLDER_MODE_SEQNAME}</code> will be created."
    ))
    chk_register = QCheckBox("Register frames for statistics (FWHM, roundness, background)")
    chk_register.setChecked(True)
    chk_register.setToolTip(
        "Runs 'register -2pass' so statistics table, graph, batch-reject, and quality\n"
        "weights are available. May take several minutes on large sequences."
    )
    layout.addWidget(chk_register)

    btn_row = QHBoxLayout()
    btn_ok = QPushButton("Continue")
    btn_ok.setStyleSheet("padding:6px 16px;background-color:#285299;color:white;font-weight:bold;")
    btn_ok.clicked.connect(dlg.accept)
    btn_cancel = QPushButton("Cancel")
    btn_cancel.setStyleSheet("padding:6px 16px;")
    btn_cancel.clicked.connect(dlg.reject)
    btn_row.addStretch()
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_ok)
    layout.addLayout(btn_row)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    return folder, chk_register.isChecked()


def _build_folder_sequence(siril, folder: str, do_register: bool, parent=None) -> bool:
    """Run cd + convert (+ optional register). Returns True on success."""
    progress = QProgressDialog("Preparing temporary sequence...", None, 0, 0, parent)
    progress.setWindowTitle("Loading Folder")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.setAutoClose(False)
    progress.show()
    QApplication.processEvents()

    try:
        # Preflight: verify the folder still exists on disk. Catches
        # deletes/renames between dialog pick and conversion start, and
        # gives a clearer message than Siril's generic "Directory not found".
        if not os.path.isdir(folder):
            progress.close()
            QMessageBox.critical(
                parent, "Folder Not Found",
                f"The selected folder no longer exists:\n\n{folder}"
            )
            return False

        progress.setLabelText("Changing directory in Siril...")
        QApplication.processEvents()
        # Quote the folder path: sirilpy joins cmd args into a single Siril
        # command line, and Siril's `cd` parser treats unquoted whitespace
        # as an argument separator. Without quoting, any path containing
        # spaces (very common on macOS: "Application Support", "My Astro
        # Images", etc.) would fail with "Directory not found" — Siril
        # only saw the first token.
        siril.cmd("cd", f'"{folder}"')

        # Defensive cleanup: if a previous run crashed (or was force-killed)
        # its temp sequence artifacts may still be on disk, and `convert` will
        # refuse to proceed ("destination already exists"). Wipe them + close
        # any lingering sequence hold so `convert` always starts clean.
        progress.setLabelText("Cleaning up any leftover temp sequence...")
        QApplication.processEvents()
        try:
            siril.cmd("close")
        except Exception:
            pass
        _cleanup_folder_sequence(folder)

        progress.setLabelText(f"Converting FITS files to sequence '{FOLDER_MODE_SEQNAME}'...")
        QApplication.processEvents()
        siril.cmd("convert", FOLDER_MODE_SEQNAME, "-fitseq")

        if do_register:
            progress.setLabelText("Registering frames (may take several minutes)...")
            QApplication.processEvents()
            try:
                siril.cmd("register", FOLDER_MODE_SEQNAME, "-2pass")
            except Exception as ex:
                try:
                    siril.log(f"[BlinkComparator] Registration failed, continuing without stats: {ex}")
                except Exception:
                    pass
                QMessageBox.warning(
                    parent, "Registration Failed",
                    f"register -2pass failed. Continuing without statistics.\n\n{ex}"
                )

        progress.setLabelText("Loading sequence...")
        QApplication.processEvents()
        # `convert` already leaves the new sequence active, but call load_seq to
        # be explicit (and to refresh regdata if register was just run).
        try:
            siril.cmd("load_seq", FOLDER_MODE_SEQNAME)
        except Exception as ex:
            try:
                siril.log(f"[BlinkComparator] load_seq warning (continuing): {ex}")
            except Exception:
                pass
    except Exception as e:
        progress.close()
        QMessageBox.critical(
            parent, "Conversion Failed",
            f"Failed to build sequence from folder:\n{e}\n\n{traceback.format_exc()}"
        )
        return False
    finally:
        progress.close()

    return True


def _cleanup_folder_sequence(folder: str) -> None:
    """Remove everything that was created by _build_folder_sequence:
    the .seq files, the FITSEQ image files, the conversion log, and the
    Siril thumbnail cache directory.
    """
    patterns = [
        f"{FOLDER_MODE_SEQNAME}.seq",
        f"r_{FOLDER_MODE_SEQNAME}.seq",
        f"{FOLDER_MODE_SEQNAME}_*.fit",
        f"{FOLDER_MODE_SEQNAME}_*.fits",
        f"{FOLDER_MODE_SEQNAME}.fit",
        f"{FOLDER_MODE_SEQNAME}.fits",
        f"r_{FOLDER_MODE_SEQNAME}.fit",
        f"r_{FOLDER_MODE_SEQNAME}.fits",
        f"{FOLDER_MODE_SEQNAME}_conversion.txt",
    ]
    for pat in patterns:
        for path in glob.glob(os.path.join(folder, pat)):
            try:
                os.remove(path)
            except OSError:
                pass

    # Siril writes a "cache" directory into the working folder for sequence
    # thumbnails / computed data. Since folder mode creates a throwaway
    # sequence, wipe the whole cache subfolder on close.
    cache_dir = os.path.join(folder, "cache")
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main() -> int:
    app = QApplication(sys.argv)

    def _launch(siril, folder_mode_path: str) -> int:
        win = BlinkComparatorWindow(siril, folder_mode_path=folder_mode_path)
        win.showMaximized()

        def _bring_to_front():
            win.setWindowState(
                (win.windowState() & ~Qt.WindowState.WindowMinimized)
                | Qt.WindowState.WindowActive
            )
            win.raise_()
            win.activateWindow()

        _bring_to_front()
        # On macOS the window sometimes settles behind Siril; retry once after
        # the event loop has had a chance to process the show event.
        QTimer.singleShot(50, _bring_to_front)

        try:
            siril.log(f"Blink Comparator v{VERSION} loaded from folder: {folder_mode_path}")
        except (SirilError, OSError, RuntimeError):
            pass
        return app.exec()

    try:
        siril = s.SirilInterface()
        if not siril.connected:
            siril.connect()

        # Folder mode is the only mode — always prompt for a folder of FITS files
        # and build a temporary sequence.
        choice = _prompt_load_folder(None)
        if choice is None:
            return 0
        folder, do_register = choice

        if not _build_folder_sequence(siril, folder, do_register, None):
            return 1

        return _launch(siril, folder_mode_path=folder)

    except SirilConnectionError:
        QMessageBox.warning(
            None, "Siril Not Connected",
            "Could not connect to Siril.\n"
            "Ensure this script is launched from Siril's script menu."
        )
        return 1
    except NoImageError:
        QMessageBox.warning(
            None, "No Image",
            "No image or sequence is currently loaded in Siril."
        )
        return 1
    except Exception as e:
        QMessageBox.critical(
            None,
            "Blink Comparator Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
