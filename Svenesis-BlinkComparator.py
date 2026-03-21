"""
Svenesis Blink Comparator
Script Version: 1.2.1
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script reads the currently loaded sequence from Siril and plays it as
a blink animation for rapid visual inspection. It helps identify:
- Satellite trails and airplane tracks
- Passing clouds or haze
- Bad frames (tracking errors, wind gusts)
- Comet, asteroid, or planet motion
- Focus drift over the session
- Artifacts and hot-pixel patterns

Features:
- Animated playback with configurable speed (1-30 FPS)
- Frame navigation (first/prev/next/last) and color-coded slider
- Keyboard shortcuts (Space, arrows, Home/End, G/B, D, 1-9, Ctrl+Z)
- Three display modes: Normal, Difference (vs. reference), Selected-only
- Side-by-side comparison mode (current vs. reference frame)
- Crossfade transition option for smooth blending
- Linked or independent per-frame autostretch
- Frame marking: include/exclude with pending changes and batch apply
- Auto-advance after marking for rapid frame selection
- Batch reject by threshold (FWHM, Background, Roundness) or worst N%
- Sortable statistics table (all frames with FWHM, BG, roundness, stars)
- Statistics graph (FWHM, Background, Roundness over time)
- Thumbnail filmstrip with lazy loading and color-coded borders
- Per-frame histogram
- Undo for frame markings (Ctrl+Z)
- Export rejected frame list as text file
- Session summary on close (frames viewed, rejected, FWHM improvement)
- LRU frame cache with background preloading for smooth playback
- Autostretch (Midtone Transfer Function) with global parameters
- Zoom (scroll wheel) and pan (right-click drag)
- ROI blink mode (select region, blink at 1:1 pixel scale)
- Per-frame info display (FWHM, background, noise, exposure, date)
- Dark themed PyQt6 GUI matching the Gradient Analyzer look and feel

Run from Siril via Processing -> Scripts. Place BlinkComparator.py inside a folder
named Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.2.3 - Architecture-level performance pass
      - Optimized: single canvas.update() per frame (was up to 3 queued repaints)
        via defer_update parameter on set_image/set_side_by_side/set_overlay_text
      - Optimized: ThreadPoolExecutor(max_workers=1) replaces per-frame thread spawning
        for preloading — eliminates thread creation overhead and OS scheduling pressure
      - Optimized: pre-computed overlay stats strings at load time (_precompute_overlay_stats)
        — playback builds overlay from cached strings instead of formatting per frame
      - Optimized: frame_data_to_qimage uses np.stack for RGBX assembly (single memcpy
        vs 4 separate slice assignments)
      - Optimized: FrameStatistics.load_all uses getattr(obj, attr, default) instead of
        hasattr+getattr (2 lookups → 1 per attribute × 7 attrs × N frames)
      - Optimized: load_reference_frame reuses shared load_frame_data() helper
      - Optimized: _build_overlay_text uses pre-computed stats + simple string concat
1.2.2 - Performance optimizations (playback & memory)
      - Optimized: mtf() — cache np.abs(denom) result (was computed twice per call)
      - Optimized: autostretch() — in-place subtract+scale+clip chain; subsample median/MAD
      - Optimized: frame_data_to_qimage() — single flip on assembled RGBX (was 3 separate flipud)
      - Optimized: load_frame_data() — dtype check instead of full-array max() scan
      - Optimized: difference mode — in-place subtract/abs/scale/clip (was 3 temp arrays)
      - Optimized: FrameMarker.get_excluded_indices() — cached set with lazy invalidation
      - Optimized: playback hot path — skip RichText info bar, stats table highlight,
        matplotlib graph, and histogram during play; refresh all on pause
      - Optimized: ImageCanvas.paintEvent() — pre-allocated QColor class attributes
      - Optimized: ThumbnailFilmstrip — cached stylesheet strings (avoid CSS reparse)
      - Optimized: _replace_canvas() — fig.clear()+del instead of importing pyplot
      - Optimized: HistogramWidget — uses shared load_frame_data() helper; ravel not flatten
      - Fixed: SortOrder enum serialization in _save_settings() (TypeError on close)
      - Fixed: _on_stretch_mode_changed() guard for early signal during __init__
1.2.1 - Code quality, performance, and robustness fixes
      - Fixed: matplotlib figure memory leak (plt.close() on figure replacement)
      - Fixed: Qt signal emission from background thread removed (PreloadWorker)
      - Fixed: bare except clauses replaced with specific exception types + logging
      - Fixed: table highlight_current() reduced from O(N) to O(1) via frame→row index map
      - Fixed: GIF export numpy pointer lifetime (.copy() on frombuffer)
      - Refactored: extracted shared frame_data_to_qimage() and load_frame_data() helpers
      - Refactored: FrameCache and ThumbnailCache now use shared helpers (no code duplication)
      - Added: named constants (ZOOM_FACTOR, MAX_ZOOM, MIN_ZOOM, SLIDER_HANDLE_MARGIN, etc.)
      - Added: docstrings on all public classes and key helper functions
      - Added: logging module for debug-level diagnostics instead of silent failures
1.2.0 - SubframeSelector-level upgrade
      - Composite quality weight score per frame (1/FWHM * roundness * 1/background * stars)
      - Quality Weight column in statistics table (sortable)
      - Approval expressions: multi-criteria filter with AND logic (FWHM < 4.5 AND Roundness > 0.7)
      - Scatter plot tab: FWHM vs Roundness / FWHM vs Background (click dot to jump to frame)
      - Frame info overlay on canvas (frame number, FWHM, status burned into image corner)
      - Multi-select in statistics table (Ctrl+click, Shift+click, right-click to reject selected)
      - Statistics CSV export (full table with all metrics)
      - Running average (moving average line) on statistics graph
      - 1:1 pixel zoom button for precise star shape inspection
      - Frame A/B toggle (T key to pin current frame, T again to toggle back)
      - Animated GIF export of blink animation (configurable frame range and FPS)
      - Adjustable thumbnail size slider
      - Copy current frame to clipboard (Ctrl+C)
      - Table keyboard navigation (arrow keys move between rows)
      - Remember table sort column and direction between sessions
1.1.0 - PixInsight Blink-level upgrade
      - Sortable statistics table with all frames (FWHM, roundness, BG, stars, median, sigma, date)
      - Batch reject by threshold (metric > value) or worst N%
      - Auto-advance after marking (G/B) for rapid frame selection
      - Statistics graph: FWHM, Background, Roundness plotted over all frames
      - Thumbnail filmstrip with lazy loading and color-coded borders
      - Color-coded frame slider (red ticks at excluded frames)
      - ROI blink mode: select region, blink at 1:1 pixel scale
      - Crossfade transition option for smooth frame blending
      - Side-by-side comparison mode (current vs. reference)
      - Linked vs. independent per-frame autostretch toggle
      - Per-frame pixel histogram widget
      - Undo last marking (Ctrl+Z)
      - Session summary on close with FWHM statistics
      - Export rejected frame list as text file
1.0.0 - Initial release
      - Animated sequence playback with LRU cache and background preloading
      - Normal, Difference, and Selected-only display modes
      - Frame marking (include/exclude) with batch apply to Siril
      - Zoom/pan canvas with keyboard shortcuts
      - Per-frame info bar (FWHM, background, noise, exposure, date)
      - Dark PyQt6 GUI matching Gradient Analyzer style
"""
from __future__ import annotations

import sys
import os
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
    QComboBox, QFileDialog, QAbstractItemView, QMenu, QLineEdit,
)
from PyQt6.QtCore import (
    Qt, QSettings, QUrl, QTimer, pyqtSignal, QObject, QRectF, QRect, QPoint,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QImage, QPixmap, QShortcut,
    QKeySequence, QDesktopServices, QWheelEvent, QMouseEvent,
)

VERSION = "1.2.3"

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

def mtf(midtone: float, x: np.ndarray | float) -> np.ndarray | float:
    """Midtone Transfer Function.

    Vectorized implementation avoids intermediate boolean index arrays.
    For scalar inputs, uses a fast early-return path.
    """
    if isinstance(x, np.ndarray):
        # Compute denom for entire array; handle division-by-zero via np.where
        denom = (2.0 * midtone - 1.0) * x - midtone
        abs_denom = np.abs(denom)
        denom_ok = abs_denom > 1e-10
        safe_denom = np.where(denom_ok, denom, 1.0)  # avoid div/0
        result = np.where(
            (x > 0) & (x < 1) & denom_ok,
            (midtone - 1.0) * x / safe_denom,
            0.0,
        )
        result = np.where(x >= 1.0, 1.0, result)
        return np.clip(result, 0.0, 1.0, out=result)
    else:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        denom = (2 * midtone - 1) * x - midtone
        if abs(denom) < 1e-10:
            return 0.5
        return max(0.0, min(1.0, (midtone - 1) * x / denom))


def autostretch(
    data: np.ndarray,
    shadows_clip: float = -2.8,
    target_median: float = 0.25,
    global_median: float | None = None,
    global_mad: float | None = None,
) -> np.ndarray:
    """
    Midtone Transfer Function (MTF) Autostretch.
    If global_median/global_mad are provided, uses those for consistent brightness.
    """
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
        mad = float(np.median(np.abs(flat - median))) * 1.4826

    shadow = max(0.0, median + shadows_clip * mad)
    highlight = 1.0

    rng = highlight - shadow
    if rng < 1e-10:
        rng = 1.0

    if median - shadow > 0:
        midtone = mtf(target_median, median - shadow)
    else:
        midtone = 0.5

    # Single allocation: subtract + scale + clip in one chain, reusing the buffer
    stretched = np.subtract(data, shadow, dtype=np.float32)
    stretched *= (1.0 / rng)
    np.clip(stretched, 0, 1, out=stretched)
    stretched = mtf(midtone, stretched)
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
HISTOGRAM_SUBSAMPLE = 100000  # Max pixels for histogram rendering


def frame_data_to_qimage(
    frame_data: np.ndarray,
    global_median: float | None = None,
    global_mad: float | None = None,
) -> QImage | None:
    """Convert sirilpy frame data (float32, channels×H×W) to a stretched QImage.

    Handles RGB (3×H×W), single-channel (1×H×W), and 2D mono arrays.
    Applies autostretch and flips from Siril's bottom-up orientation.
    Returns a QImage that owns its own pixel data (.copy()), or None on failure.
    """
    if frame_data.ndim == 3 and frame_data.shape[0] == 3:
        r = autostretch(frame_data[0], global_median=global_median, global_mad=global_mad)
        g = autostretch(frame_data[1], global_median=global_median, global_mad=global_mad)
        b = autostretch(frame_data[2], global_median=global_median, global_mad=global_mad)
        h, w = r.shape
        # Stack RGB + alpha in one call, flip, ensure C-contiguous for QImage
        alpha = np.full((h, w), 255, dtype=np.uint8)
        rgbx = np.stack((r, g, b, alpha), axis=-1)
        rgbx = np.ascontiguousarray(rgbx[::-1])
        return QImage(rgbx.data, w, h, w * 4, QImage.Format.Format_RGBX8888).copy()
    elif frame_data.ndim == 3 and frame_data.shape[0] == 1:
        mono = autostretch(frame_data[0], global_median=global_median, global_mad=global_mad)
        mono = np.ascontiguousarray(mono[::-1])
        h, w = mono.shape
        return QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    elif frame_data.ndim == 2:
        mono = autostretch(frame_data, global_median=global_median, global_mad=global_mad)
        mono = np.ascontiguousarray(mono[::-1])
        h, w = mono.shape
        return QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
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

    def load_all(self, progress_callback=None) -> None:
        """Load registration data, stats, and imgdata for all frames.

        When regdata is unavailable (sequence registered without star detection),
        falls back to stats.median for background and stats.bgnoise for noise.
        Sets self.has_regdata flag so the UI can offer to run seqfindstar.
        """
        self.data = []
        self.has_regdata = False  # Track whether any frame has registration data

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

            try:
                # Siril stores regdata on the green channel (1) for RGB images.
                # Try all channels and use the first one with valid FWHM data.
                reg = None
                for ch in range(self._nb_layers):
                    try:
                        reg = self.siril.get_seq_regdata(i, ch)
                        if reg is not None and getattr(reg, 'fwhm', 0) > 0:
                            break
                        reg = None
                    except Exception:
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
            except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                log.debug("Frame %d: regdata unavailable: %s", i, exc)

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

            try:
                imgdata = self.siril.get_seq_imgdata(i)
                if imgdata is not None:
                    v = getattr(imgdata, 'date_obs', None)
                    if v:
                        row["date_obs"] = str(v)
            except (SirilError, OSError, AttributeError, TypeError, ValueError) as exc:
                log.debug("Frame %d: imgdata unavailable: %s", i, exc)

            self.data.append(row)

            if progress_callback and i % 5 == 0:
                progress_callback(i, self.total)

        # Compute composite quality weights
        self._compute_weights()

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

    def compute_global_stretch(self, sample_count: int = 10) -> None:
        total = self.seq.number
        step = max(1, total // sample_count)
        indices = list(range(0, total, step))[:sample_count]
        medians = []
        mads = []
        for idx in indices:
            try:
                stats = self.siril.get_seq_stats(idx, 0)
                if stats is not None:
                    medians.append(stats.median)
                    mads.append(stats.avgDev if stats.avgDev > 0 else stats.sigma)
            except Exception:
                pass
        if medians:
            self.global_median = float(np.median(medians))
            self.global_mad = float(np.median(mads)) * 1.4826 if mads else 0.001
        else:
            self.global_median = None
            self.global_mad = None

    def load_reference_frame(self) -> None:
        ref_idx = self.seq.reference_image
        if ref_idx < 0 or ref_idx >= self.seq.number:
            ref_idx = 0
        self.reference_data = load_frame_data(self.siril, ref_idx)

    def get_frame(self, index: int, difference: bool = False, linked: bool = True) -> QImage | None:
        """Get frame from cache or load from Siril. Thread-safe with double-check."""
        cache_key = (index, difference, linked)
        with self.lock:
            if cache_key in self.cache:
                self.cache.move_to_end(cache_key)
                return self.cache[cache_key]
            # Mark as loading to prevent duplicate loads from preload threads
            self.cache[cache_key] = None  # Placeholder
        qimg = self._load_and_stretch(index, difference, linked)
        with self.lock:
            if qimg is not None:
                self.cache[cache_key] = qimg
                self.cache.move_to_end(cache_key)
            else:
                self.cache.pop(cache_key, None)
            while len(self.cache) > self.max_frames:
                self.cache.popitem(last=False)
        return qimg

    def _load_and_stretch(self, index: int, difference: bool, linked: bool = True) -> QImage | None:
        """Load frame from Siril, apply stretch, return scaled QImage."""
        frame_data = load_frame_data(self.siril, index)
        if frame_data is None:
            return None

        if difference and self.reference_data is not None:
            if frame_data.shape == self.reference_data.shape:
                # In-place: subtract, abs, scale, clip — avoids 3 intermediate arrays
                frame_data = np.subtract(frame_data, self.reference_data)
                np.abs(frame_data, out=frame_data)
                frame_data *= 5.0
                np.clip(frame_data, 0, 1, out=frame_data)

        g_med = self.global_median if linked else None
        g_mad = self.global_mad if linked else None

        qimg = frame_data_to_qimage(frame_data, g_med, g_mad)
        if qimg is None:
            return None

        return qimg.scaled(
            self.display_width, self.display_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def invalidate(self) -> None:
        with self.lock:
            self.cache.clear()

    def preload_range(self, start: int, count: int, difference: bool = False, linked: bool = True) -> None:
        total = self.seq.number
        for i in range(start, min(start + count, total)):
            if i < 0:
                continue
            cache_key = (i, difference, linked)
            with self.lock:
                if cache_key in self.cache:
                    continue
            self.get_frame(i, difference, linked)


# Shared thread pool for preloading (1 worker — avoids flooding Siril's socket)
_preload_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preload")


# ------------------------------------------------------------------------------
# THUMBNAIL CACHE
# ------------------------------------------------------------------------------

class ThumbnailCache:
    """Separate LRU cache for small frame thumbnails."""

    def __init__(self, siril_iface, seq, global_median=None, global_mad=None,
                 max_items: int = THUMBNAIL_CACHE_SIZE):
        self.siril = siril_iface
        self.seq = seq
        self.global_median = global_median
        self.global_mad = global_mad
        self.max_items = max_items
        self.cache: OrderedDict[int, QPixmap] = OrderedDict()
        self.lock = threading.Lock()

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
        """Load a single frame, stretch, and scale to thumbnail size."""
        data = load_frame_data(self.siril, index)
        if data is None:
            return None
        qimg = frame_data_to_qimage(data, self.global_median, self.global_mad)
        if qimg is None:
            return None
        qimg = qimg.scaled(
            THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
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

    def apply_to_siril(self, siril_iface) -> str:
        exclude_list = [i for i, v in self.changes.items() if not v]
        include_list = [i for i, v in self.changes.items() if v]
        if exclude_list:
            for idx in exclude_list:
                siril_iface.set_seq_frame_incl(idx, False)
        if include_list:
            for idx in include_list:
                siril_iface.set_seq_frame_incl(idx, True)
        msg = f"{len(exclude_list)} excluded, {len(include_list)} included"
        siril_iface.log(f"[BlinkComparator] Applied: {msg}")
        for idx, val in self.changes.items():
            self.original[idx] = val
        self.changes.clear()
        self._excluded_cache = None  # Invalidate
        return msg


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

    def _set_row_background(self, row: int, color: QColor) -> None:
        """Set background color for all cells in a row."""
        for c in range(self.table.columnCount()):
            cell = self.table.item(row, c)
            if cell is not None:
                cell.setBackground(color)

    def highlight_current(self, index: int) -> None:
        """Highlight the current frame row. O(1) via frame→row mapping."""
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

    def render(self, frame_stats: FrameStatistics, marker: FrameMarker,
               x_metric: str = "fwhm", y_metric: str = "roundness",
               current_frame: int = 0) -> None:
        if not self._mpl_available:
            return

        fig = self._Figure(figsize=(8, 6), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")

        excluded = marker.get_excluded_indices()
        rows = frame_stats.get_all_rows()

        incl_x, incl_y, incl_idx = [], [], []
        excl_x, excl_y = [], []
        cur_x, cur_y = None, None

        for row in rows:
            xv = row.get(x_metric, 0)
            yv = row.get(y_metric, 0)
            if xv <= 0 or yv <= 0:
                continue
            idx = row["frame_idx"]
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
        # Store axis ranges for normalized click detection
        all_x = incl_x + excl_x
        all_y = incl_y + excl_y
        self._x_range = (min(all_x), max(all_x)) if all_x else (0.0, 1.0)
        self._y_range = (min(all_y), max(all_y)) if all_y else (0.0, 1.0)

        if incl_x:
            ax.scatter(incl_x, incl_y, color="#88aaff", s=30, alpha=0.7, label="Included", zorder=3)
        if excl_x:
            ax.scatter(excl_x, excl_y, color="#dd4444", s=30, alpha=0.5, marker="x",
                       label="Excluded", zorder=2)
        if cur_x is not None:
            ax.scatter([cur_x], [cur_y], color="#ffffff", s=100, marker="*",
                       edgecolors="#88aaff", linewidths=1.5, label="Current", zorder=5)

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
        while self._conditions:
            self._conditions.pop()
        # Clear layout
        while self._cond_layout.count():
            child = self._cond_layout.takeAt(0)
            if child.layout():
                while child.layout().count():
                    w = child.layout().takeAt(0).widget()
                    if w:
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

    def render(self, frame_stats: FrameStatistics, marker: FrameMarker,
               current_frame: int,
               show_fwhm: bool = True, show_bg: bool = True,
               show_roundness: bool = False,
               show_running_avg: bool = True) -> None:
        if not self._mpl_available:
            return

        fig = self._Figure(figsize=(10, 4), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")

        x = list(range(1, frame_stats.total + 1))
        excluded = marker.get_excluded_indices()

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
            fwhm = frame_stats.get_column("fwhm")
            incl_x = [x[i] for i in range(len(x)) if i not in excluded and fwhm[i] > 0]
            incl_y = [fwhm[i] for i in range(len(x)) if i not in excluded and fwhm[i] > 0]
            excl_x = [x[i] for i in range(len(x)) if i in excluded and fwhm[i] > 0]
            excl_y = [fwhm[i] for i in range(len(x)) if i in excluded and fwhm[i] > 0]
            if incl_x:
                ax.plot(incl_x, incl_y, color="#88aaff", linewidth=1.0, label="FWHM", alpha=0.5)
                if show_running_avg and len(incl_y) >= 7:
                    avg_x, avg_y = _moving_avg(incl_x, incl_y)
                    ax.plot(avg_x, avg_y, color="#88aaff", linewidth=2.5, alpha=0.9, label="FWHM avg")
            if excl_x:
                ax.scatter(excl_x, excl_y, color="#dd4444", s=20, zorder=5, label="Excluded")

        if show_bg:
            bg = frame_stats.get_column("background")
            ax2 = ax.twinx()
            ax2.set_facecolor("#1e1e1e")
            incl_x = [x[i] for i in range(len(x)) if i not in excluded and bg[i] > 0]
            incl_y = [bg[i] for i in range(len(x)) if i not in excluded and bg[i] > 0]
            if incl_x:
                ax2.plot(incl_x, incl_y, color="#ffaa55", linewidth=1.5, label="Background", alpha=0.8)
            ax2.tick_params(colors="#aaaaaa", labelsize=8)
            ax2.set_ylabel("Background", color="#ffaa55", fontsize=9)
            for spine in ax2.spines.values():
                spine.set_edgecolor("#555555")

        if show_roundness:
            rnd = frame_stats.get_column("roundness")
            incl_x = [x[i] for i in range(len(x)) if i not in excluded and rnd[i] > 0]
            incl_y = [rnd[i] for i in range(len(x)) if i not in excluded and rnd[i] > 0]
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

    def set_exclusions(self, excluded_indices: set[int], total: int) -> None:
        self._excluded = excluded_indices
        self._total = max(1, total)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._excluded or self._total <= 1:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get groove geometry (handle half-width approximation)
        groove_x = SLIDER_HANDLE_MARGIN
        groove_w = self.width() - SLIDER_HANDLE_MARGIN * 2
        groove_y = self.height() - 4
        tick_h = 4

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#dd4444"))

        for idx in self._excluded:
            x = groove_x + int(idx / (self._total - 1) * groove_w) if self._total > 1 else groove_x
            painter.drawRect(x - 1, groove_y, 3, tick_h)

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

    def __init__(self, total_frames: int, parent=None):
        super().__init__(parent)
        self.total_frames = total_frames
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
            self._labels[index].setPixmap(pixmap.scaled(
                THUMBNAIL_WIDTH - 4, THUMBNAIL_HEIGHT - 4,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def highlight_current(self, index: int) -> None:
        if self._current >= 0 and self._current < len(self._labels):
            # Restore previous frame to included style (will be corrected by update_border if needed)
            self._labels[self._current].setStyleSheet(_THUMB_STYLE_INCLUDED)
        self._current = index
        if 0 <= index < len(self._labels):
            self._labels[index].setStyleSheet(_THUMB_STYLE_CURRENT)
            self.scroll.ensureWidgetVisible(self._labels[index], 50, 0)

    def update_border(self, index: int, included: bool) -> None:
        if 0 <= index < len(self._labels):
            if index == self._current:
                style = _THUMB_STYLE_CURRENT
            elif included:
                style = _THUMB_STYLE_INCLUDED
            else:
                style = _THUMB_STYLE_EXCLUDED
            self._labels[index].setStyleSheet(style)

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
# PER-FRAME HISTOGRAM WIDGET
# ------------------------------------------------------------------------------

class HistogramWidget(_MplWidgetBase):
    """Small per-frame pixel histogram."""

    def __init__(self, parent=None):
        super().__init__("Histogram", parent)
        self.setMinimumSize(300, 100)
        self.setMaximumHeight(140)

    def render_histogram(self, cache: FrameCache, frame_index: int,
                         linked: bool = True) -> None:
        """Render histogram for a frame. Loads data via shared load_frame_data() helper."""
        if not self._mpl_available:
            return
        try:
            data = load_frame_data(cache.siril, frame_index)
            if data is None:
                return
            # Use channel 0 (or mono)
            ch = data[0] if data.ndim == 3 else data
            # Subsample: take every Nth pixel for speed
            ch_flat = ch.ravel()
            if ch_flat.size > HISTOGRAM_SUBSAMPLE:
                ch_flat = ch_flat[::ch_flat.size // HISTOGRAM_SUBSAMPLE]

            fig = self._Figure(figsize=(4, 1.5), facecolor="#1e1e1e")
            ax = fig.add_subplot(111)
            ax.set_facecolor("#1e1e1e")
            ax.hist(ch_flat, bins=200, color="#88aaff", alpha=0.8, edgecolor="none")
            ax.set_xlim(0, max(0.01, float(np.percentile(ch_flat, 99.5))))
            ax.tick_params(colors="#aaaaaa", labelsize=6)
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor("#555555")
            fig.tight_layout(pad=0.3)
            self._replace_canvas(fig)
        except (SirilError, OSError, ValueError, TypeError, RuntimeError) as exc:
            log.debug("Failed to render histogram for frame %d: %s", frame_index, exc)


# ------------------------------------------------------------------------------
# ZOOMABLE IMAGE WIDGET
# ------------------------------------------------------------------------------

class ImageCanvas(QWidget):
    """Widget that displays a QImage with zoom, pan, ROI, side-by-side, and crossfade."""
    roi_selected = pyqtSignal(QRect)

    # Pre-allocated colors to avoid per-frame QColor construction from strings
    _CLR_BG = QColor(26, 26, 26)
    _CLR_GRAY = QColor(100, 100, 100)
    _CLR_ACCENT = QColor(136, 170, 255)       # #88aaff
    _CLR_ROI_FILL = QColor(136, 170, 255, 30)
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

        # Crossfade
        self._crossfade_alpha: float = 1.0
        self._crossfade_pixmap: QPixmap | None = None

        # ROI mode
        self._roi_mode: bool = False
        self._roi_drawing: bool = False
        self._roi_rect: QRect | None = None
        self._roi_start: QPoint | None = None

        # Frame info overlay
        self._overlay_text: str = ""
        self._show_overlay: bool = True

        self.setStyleSheet("background-color: #1a1a1a;")

    def set_image(self, qimg: QImage | None, defer_update: bool = False) -> None:
        if qimg is None:
            self._pixmap = None
        else:
            self._pixmap = QPixmap.fromImage(qimg)
        self._crossfade_alpha = 1.0
        self._crossfade_pixmap = None
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

    def start_crossfade(self, from_pixmap: QPixmap) -> None:
        self._crossfade_pixmap = from_pixmap
        self._crossfade_alpha = 0.0

    def set_crossfade_alpha(self, alpha: float) -> None:
        self._crossfade_alpha = alpha
        self.update()

    def set_overlay_text(self, text: str, defer_update: bool = False) -> None:
        self._overlay_text = text
        if not defer_update:
            self.update()

    def set_show_overlay(self, show: bool) -> None:
        self._show_overlay = show
        self.update()

    def set_roi_mode(self, enabled: bool) -> None:
        self._roi_mode = enabled
        if not enabled:
            self._roi_rect = None
            self._roi_drawing = False
        self.update()

    def get_roi_rect(self) -> QRect | None:
        return self._roi_rect

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

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
            # Crossfade
            if self._crossfade_pixmap is not None and self._crossfade_alpha < 1.0:
                painter.setOpacity(1.0 - self._crossfade_alpha)
                self._draw_pixmap(painter, self._crossfade_pixmap)
                painter.setOpacity(self._crossfade_alpha)
                self._draw_pixmap(painter, self._pixmap)
                painter.setOpacity(1.0)
            else:
                self._draw_pixmap(painter, self._pixmap)

        # ROI overlay
        if self._roi_rect is not None and not self._roi_rect.isNull():
            painter.setPen(QPen(self._CLR_ACCENT, 2, Qt.PenStyle.DashLine))
            painter.setBrush(self._CLR_ROI_FILL)
            painter.drawRect(self._roi_rect)

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._roi_mode and event.button() == Qt.MouseButton.LeftButton:
            self._roi_drawing = True
            self._roi_start = event.position().toPoint()
            self._roi_rect = QRect(self._roi_start, self._roi_start)
            return
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._dragging = True
            self._drag_start_x = event.position().x()
            self._drag_start_y = event.position().y()
            self._drag_pan_start_x = self._pan_x
            self._drag_pan_start_y = self._pan_y

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._roi_drawing and self._roi_start is not None:
            self._roi_rect = QRect(self._roi_start, event.position().toPoint()).normalized()
            self.update()
            return
        if self._dragging:
            dx = event.position().x() - self._drag_start_x
            dy = event.position().y() - self._drag_start_y
            self._pan_x = self._drag_pan_start_x + dx
            self._pan_y = self._drag_pan_start_y + dy
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._roi_drawing and event.button() == Qt.MouseButton.LeftButton:
            self._roi_drawing = False
            if self._roi_rect is not None and self._roi_rect.width() > 10 and self._roi_rect.height() > 10:
                self.roi_selected.emit(self._roi_rect)
            return
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

    def __init__(self, siril_iface=None):
        super().__init__()
        self.siril = siril_iface or s.SirilInterface()

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

        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self._init_ui()
        self._load_settings()
        self._setup_shortcuts()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        # Crossfade timer
        self._cf_timer = QTimer(self)
        self._cf_timer.timeout.connect(self._crossfade_tick)
        self._cf_steps = 0

        self.cache: FrameCache | None = None
        self.thumb_cache: ThumbnailCache | None = None

        QTimer.singleShot(100, self._deferred_init)

    def _deferred_init(self) -> None:
        canvas_w = max(400, self.canvas.width())
        canvas_h = max(300, self.canvas.height())

        self.cache = FrameCache(
            self.siril, self.seq,
            max_frames=DEFAULT_CACHE_SIZE,
            display_width=canvas_w,
            display_height=canvas_h,
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
            # -2pass computes transforms (FWHM, roundness, stars) without generating output images
            self.siril.cmd("register", self.seq.seqname, "-2pass")
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
            self.siril.cmd("seqfind", seqname)
        except Exception as ex:
            self.siril.log(f"[BlinkComparator] WARNING: seqfind failed: {ex}")

        # Now get the refreshed sequence object
        try:
            self.seq = self.siril.get_seq()
            self.siril.log(f"[BlinkComparator] Sequence reloaded: {self.seq.seqname}, "
                           f"{self.seq.number} frames, layers={self.seq.nb_layers}")
        except Exception as ex:
            self.siril.log(f"[BlinkComparator] WARNING: get_seq() failed after register: {ex}")

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
            pct = int(80 * i / max(1, total))
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

        # Display options
        opts_group = QGroupBox("Display Options")
        opts_layout = QVBoxLayout(opts_group)

        self.chk_overlay = QCheckBox("Show frame info overlay")
        self.chk_overlay.setChecked(True)
        self.chk_overlay.setToolTip("Show frame number and FWHM burned into the image corner")
        _nofocus(self.chk_overlay)
        self.chk_overlay.stateChanged.connect(lambda s: self.canvas.set_show_overlay(s == Qt.CheckState.Checked.value))
        opts_layout.addWidget(self.chk_overlay)

        thumb_row = QHBoxLayout()
        thumb_row.addWidget(QLabel("Thumb size:"))
        self.slider_thumb_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_thumb_size.setRange(40, 160)
        self.slider_thumb_size.setValue(THUMBNAIL_WIDTH)
        _nofocus(self.slider_thumb_size)
        self.slider_thumb_size.valueChanged.connect(self._on_thumb_size_changed)
        thumb_row.addWidget(self.slider_thumb_size)
        opts_layout.addLayout(thumb_row)

        layout.addWidget(opts_group)

        # Per-frame histogram
        hist_group = QGroupBox("Frame Histogram")
        hist_layout = QVBoxLayout(hist_group)
        self.histogram_widget = HistogramWidget()
        hist_layout.addWidget(self.histogram_widget)
        layout.addWidget(hist_group)

        layout.addStretch()

        # Export buttons
        export_row = QHBoxLayout()
        btn_export = QPushButton("Export Rejected...")
        _nofocus(btn_export)
        btn_export.setToolTip("Save list of rejected frame indices as text file")
        btn_export.clicked.connect(self._export_rejected_list)
        export_row.addWidget(btn_export)

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
        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.setObjectName("CloseButton")
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

        self.chk_loop = QCheckBox("Loop playback")
        self.chk_loop.setChecked(True)
        self.chk_loop.setToolTip("Restart from first frame after reaching the last")
        _nofocus(self.chk_loop)
        g_layout.addWidget(self.chk_loop)

        self.chk_crossfade = QCheckBox("Crossfade transition")
        self.chk_crossfade.setChecked(False)
        self.chk_crossfade.setToolTip("Smooth blend between frames instead of hard cut")
        _nofocus(self.chk_crossfade)
        g_layout.addWidget(self.chk_crossfade)

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
        self.radio_diff = QRadioButton("Difference (vs. reference)")
        self.radio_diff.setToolTip("Absolute difference to reference frame.")
        self.radio_selected = QRadioButton("Only included frames")
        self.radio_selected.setToolTip("Skip excluded frames during playback.")
        self.radio_sidebyside = QRadioButton("Side by Side (vs. reference)")
        self.radio_sidebyside.setToolTip("Current frame on left, reference on right.")

        self.mode_group.addButton(self.radio_normal, 0)
        self.mode_group.addButton(self.radio_diff, 1)
        self.mode_group.addButton(self.radio_selected, 2)
        self.mode_group.addButton(self.radio_sidebyside, 3)

        for radio in (self.radio_normal, self.radio_diff, self.radio_selected, self.radio_sidebyside):
            _nofocus(radio)
            g_layout.addWidget(radio)

        self.mode_group.idToggled.connect(self._on_mode_changed)

        # Linked stretch
        self.chk_linked_stretch = QCheckBox("Linked stretch (same for all frames)")
        self.chk_linked_stretch.setChecked(True)
        self.chk_linked_stretch.setToolTip(
            "ON: All frames use the same stretch parameters (shows brightness differences).\n"
            "OFF: Each frame is stretched independently (shows details but hides brightness changes)."
        )
        _nofocus(self.chk_linked_stretch)
        self.chk_linked_stretch.stateChanged.connect(self._on_stretch_mode_changed)
        g_layout.addWidget(self.chk_linked_stretch)

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

        self.chk_auto_advance = QCheckBox("Auto-advance after marking")
        self.chk_auto_advance.setChecked(True)
        self.chk_auto_advance.setToolTip("Automatically go to next frame after pressing G or B")
        _nofocus(self.chk_auto_advance)
        g_layout.addWidget(self.chk_auto_advance)

        self.lbl_pending = QLabel("No pending changes")
        self.lbl_pending.setStyleSheet("color: #999; font-size: 9pt;")
        self.lbl_pending.setWordWrap(True)
        g_layout.addWidget(self.lbl_pending)

        self.btn_apply = QPushButton("Apply Changes to Siril")
        self.btn_apply.setObjectName("ApplyButton")
        self.btn_apply.setToolTip("Send all pending changes to Siril.")
        _nofocus(self.btn_apply)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_changes)
        g_layout.addWidget(self.btn_apply)

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
        vt_layout.addWidget(self.canvas, 1)

        zoom_bar = QHBoxLayout()
        self.lbl_zoom = QLabel("Zoom: Fit")
        self.lbl_zoom.setStyleSheet("color: #777; font-size: 9pt;")
        zoom_bar.addWidget(self.lbl_zoom)

        btn_reset_zoom = QPushButton("Reset Zoom (Z)")
        btn_reset_zoom.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        _nofocus(btn_reset_zoom)
        btn_reset_zoom.clicked.connect(self._reset_zoom)
        zoom_bar.addWidget(btn_reset_zoom)

        self.btn_roi = QPushButton("Select ROI")
        self.btn_roi.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        self.btn_roi.setCheckable(True)
        _nofocus(self.btn_roi)
        self.btn_roi.toggled.connect(self._toggle_roi_mode)
        zoom_bar.addWidget(self.btn_roi)

        btn_clear_roi = QPushButton("Clear ROI")
        btn_clear_roi.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        _nofocus(btn_clear_roi)
        btn_clear_roi.clicked.connect(self._clear_roi)
        zoom_bar.addWidget(btn_clear_roi)

        btn_zoom_1to1 = QPushButton("1:1")
        btn_zoom_1to1.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        btn_zoom_1to1.setToolTip("Zoom to 100% (1:1 pixel view)")
        _nofocus(btn_zoom_1to1)
        btn_zoom_1to1.clicked.connect(self._zoom_1to1)
        zoom_bar.addWidget(btn_zoom_1to1)

        btn_copy = QPushButton("Copy (Ctrl+C)")
        btn_copy.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        btn_copy.setToolTip("Copy current frame to clipboard")
        _nofocus(btn_copy)
        btn_copy.clicked.connect(self._copy_frame_to_clipboard)
        zoom_bar.addWidget(btn_copy)

        zoom_bar.addStretch()

        self.lbl_shortcuts = QLabel(
            "Space=Play  \u2190\u2192=Nav  G/B=Mark  D=Diff  Z=Zoom  Ctrl+Z=Undo  1-9=FPS"
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
        self.filmstrip = ThumbnailFilmstrip(self.total_frames)
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
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._go_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Home), self, self._go_first)
        QShortcut(QKeySequence(Qt.Key.Key_End), self, self._go_last)
        QShortcut(QKeySequence(Qt.Key.Key_G), self, self._mark_include)
        QShortcut(QKeySequence(Qt.Key.Key_B), self, self._mark_exclude)
        QShortcut(QKeySequence(Qt.Key.Key_D), self, self._toggle_diff_mode)
        QShortcut(QKeySequence(Qt.Key.Key_Z), self, self._reset_zoom)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Plus), self, self._speed_up)
        QShortcut(QKeySequence(Qt.Key.Key_Minus), self, self._speed_down)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_last_marking)
        QShortcut(QKeySequence(Qt.Key.Key_T), self, self._toggle_ab_frame)
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_frame_to_clipboard)

        for n in range(1, 10):
            QShortcut(
                QKeySequence(str(n)), self,
                lambda fps=n: self.spin_fps.setValue(fps)
            )

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
        linked = self.chk_linked_stretch.isChecked()
        if self.cache is not None:
            self.histogram_widget.render_histogram(self.cache, self.current_frame, linked)

    def _advance_frame(self) -> None:
        if not self.playing:
            return
        next_frame = self.current_frame + self.direction
        only_included = self.radio_selected.isChecked()

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
        self._start_preload(next_frame + self.direction * 2, 5)

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

        self._frames_viewed.add(index)
        old_frame = self.current_frame
        self.current_frame = index

        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(index)
        self.frame_slider.blockSignals(False)

        diff_mode = self.radio_diff.isChecked()
        sbs_mode = self.radio_sidebyside.isChecked()
        linked = self.chk_linked_stretch.isChecked()

        if self.cache is not None:
            # Defer all canvas .update() calls — we'll do a single repaint at the end
            if self.chk_crossfade.isChecked() and self.canvas._pixmap is not None and old_frame != index:
                old_pixmap = self.canvas._pixmap
                qimg = self.cache.get_frame(index, difference=diff_mode, linked=linked)
                if qimg is not None:
                    self.canvas.start_crossfade(old_pixmap)
                    self.canvas.set_image(qimg, defer_update=True)
                    self._cf_steps = 0
                    self._cf_timer.start(50)
            else:
                qimg = self.cache.get_frame(index, difference=diff_mode, linked=linked)
                self.canvas.set_image(qimg, defer_update=True)

            # Side-by-side: load reference frame
            if sbs_mode:
                self.canvas.set_side_by_side(True, defer_update=True)
                ref_idx = self.seq.reference_image
                if ref_idx < 0 or ref_idx >= self.total_frames:
                    ref_idx = 0
                ref_img = self.cache.get_frame(ref_idx, difference=False, linked=linked)
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
            self._update_frame_info(index)
            self.canvas.set_overlay_text(self._build_overlay_text(index), defer_update=True)
            self.canvas.update()  # Single repaint
            self.filmstrip.highlight_current(index)
            self.stats_table.highlight_current(index)
            self.stats_graph.update_current_line(index)
            if self.cache is not None:
                self.histogram_widget.render_histogram(self.cache, index, linked)

        zoom_pct = int(self.canvas._zoom * 100)
        self.lbl_zoom.setText(f"Zoom: {zoom_pct}%")

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
    # CROSSFADE
    # ------------------------------------------------------------------

    def _crossfade_tick(self) -> None:
        self._cf_steps += 1
        alpha = min(1.0, self._cf_steps * 0.25)
        self.canvas.set_crossfade_alpha(alpha)
        if alpha >= 1.0:
            self._cf_timer.stop()

    # ------------------------------------------------------------------
    # DISPLAY MODES
    # ------------------------------------------------------------------

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        if self.cache is not None:
            self.cache.invalidate()
        self._show_frame(self.current_frame)

    def _toggle_diff_mode(self) -> None:
        if self.radio_diff.isChecked():
            self.radio_normal.setChecked(True)
        else:
            self.radio_diff.setChecked(True)

    def _on_stretch_mode_changed(self) -> None:
        if not hasattr(self, 'cache') or self.cache is None:
            return
        self.cache.invalidate()
        self._show_frame(self.current_frame)

    # ------------------------------------------------------------------
    # FRAME MARKING
    # ------------------------------------------------------------------

    def _mark_include(self) -> None:
        prev = self.marker.is_included(self.current_frame)
        self.undo_stack.push(self.current_frame, prev)
        self.marker.mark_include(self.current_frame)
        self._after_marking(self.current_frame)

    def _mark_exclude(self) -> None:
        prev = self.marker.is_included(self.current_frame)
        self.undo_stack.push(self.current_frame, prev)
        self.marker.mark_exclude(self.current_frame)
        self._after_marking(self.current_frame)

    def _after_marking(self, frame_idx: int) -> None:
        incl = self.marker.is_included(frame_idx)
        self._update_marking_ui()
        self._update_frame_info(frame_idx)
        self.stats_table.update_frame_status(frame_idx, incl, self.marker)
        self.filmstrip.update_border(frame_idx, incl)
        self.frame_slider.set_exclusions(self.marker.get_excluded_indices(), self.total_frames)

        if self.chk_auto_advance.isChecked():
            self._go_next()

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

        last_frame_idx = entries[0][0]
        for frame_idx, prev_included in entries:
            if prev_included:
                self.marker.mark_include(frame_idx)
            else:
                self.marker.mark_exclude(frame_idx)
            incl = self.marker.is_included(frame_idx)
            self.stats_table.update_frame_status(frame_idx, incl, self.marker)
            self.filmstrip.update_border(frame_idx, incl)
            last_frame_idx = frame_idx

        self._update_marking_ui()
        self.frame_slider.set_exclusions(self.marker.get_excluded_indices(), self.total_frames)
        self._show_frame(last_frame_idx)

    def _update_marking_ui(self) -> None:
        n = self.marker.get_pending_count()
        if n == 0:
            self.lbl_pending.setText("No pending changes")
            self.lbl_pending.setStyleSheet("color: #999; font-size: 9pt;")
            self.btn_apply.setEnabled(False)
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
            self.btn_apply.setEnabled(True)

    def _apply_changes(self) -> None:
        n = self.marker.get_pending_count()
        if n == 0:
            return
        reply = QMessageBox.question(
            self, "Apply Changes",
            f"Apply {n} pending change(s) to Siril?\n\n"
            f"{self.marker.get_newly_excluded_count()} frame(s) will be excluded.\n"
            f"{self.marker.get_newly_included_count()} frame(s) will be included.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            msg = self.marker.apply_to_siril(self.siril)
            QMessageBox.information(self, "Changes Applied", f"Successfully applied: {msg}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to apply changes:\n{e}")
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
        self.frame_slider.set_exclusions(self.marker.get_excluded_indices(), self.total_frames)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)
        self._refresh_statistics_graph()

    # ------------------------------------------------------------------
    # ROI
    # ------------------------------------------------------------------

    def _toggle_roi_mode(self, checked: bool) -> None:
        self.canvas.set_roi_mode(checked)
        if checked:
            self.btn_roi.setText("Drawing ROI...")
        else:
            self.btn_roi.setText("Select ROI")

    def _clear_roi(self) -> None:
        self.canvas.set_roi_mode(False)
        self.canvas._roi_rect = None
        self.btn_roi.setChecked(False)
        self.canvas.update()

    # ------------------------------------------------------------------
    # ZOOM
    # ------------------------------------------------------------------

    def _reset_zoom(self) -> None:
        self.canvas.reset_view()
        self.lbl_zoom.setText("Zoom: Fit")

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
        for i in range(start, end):
            pix = self.thumb_cache.get_thumbnail(i)
            if pix is not None:
                self.filmstrip.set_thumbnail(i, pix)

    # ------------------------------------------------------------------
    # EXPORT REJECTED LIST
    # ------------------------------------------------------------------

    def _export_rejected_list(self) -> None:
        excluded = sorted(self.marker.get_excluded_indices())
        if not excluded:
            QMessageBox.information(self, "Export", "No excluded frames to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Rejected Frames", "rejected_frames.txt", "Text files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write(f"# Blink Comparator — Rejected Frames\n")
                f.write(f"# Sequence: {self.seq.seqname}\n")
                f.write(f"# Total frames: {self.total_frames}\n")
                f.write(f"# Rejected: {len(excluded)}\n\n")
                for idx in excluded:
                    f.write(f"{idx}\n")
            QMessageBox.information(self, "Export", f"Saved {len(excluded)} rejected frame indices to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save:\n{e}")

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
    # 1:1 ZOOM
    # ------------------------------------------------------------------

    def _zoom_1to1(self) -> None:
        """Set zoom so one image pixel = one display pixel (true 1:1 view)."""
        if self.canvas._pixmap is not None:
            # The canvas paints: display_size = pixmap_size * zoom
            # For 1:1, we need zoom such that the pixmap draws at its native size.
            # Since the canvas centers the image, zoom=1.0 means native pixmap size.
            # The pixmap was already scaled to display_width during caching,
            # so zoom=1.0 is effectively "fit" and we need the inverse ratio
            # to get back to original image resolution.
            self.canvas._zoom = 1.0
            self.canvas._pan_x = 0.0
            self.canvas._pan_y = 0.0
            self.canvas.update()
            self.lbl_zoom.setText("Zoom: 100%")

    # ------------------------------------------------------------------
    # COPY TO CLIPBOARD
    # ------------------------------------------------------------------

    def _copy_frame_to_clipboard(self) -> None:
        if self.canvas._pixmap is not None:
            QApplication.clipboard().setPixmap(self.canvas._pixmap)

    # ------------------------------------------------------------------
    # THUMBNAIL SIZE
    # ------------------------------------------------------------------

    def _on_thumb_size_changed(self, size: int) -> None:
        for lbl in self.filmstrip._labels:
            lbl.setFixedSize(size, int(size * 0.75))
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
            with open(path, "w") as f:
                headers = ["Frame", "Weight", "FWHM", "Roundness", "Background", "Stars",
                           "Median", "Sigma", "Date", "Included"]
                f.write(",".join(headers) + "\n")
                for row in self.frame_stats.get_all_rows():
                    idx = row["frame_idx"]
                    incl = "Yes" if self.marker.is_included(idx) else "No"
                    vals = [
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
                    ]
                    f.write(",".join(vals) + "\n")
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

        linked = self.chk_linked_stretch.isChecked()
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
            qimg = self.cache.get_frame(i, difference=False, linked=linked)
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
        diff_mode = self.radio_diff.isChecked()
        linked = self.chk_linked_stretch.isChecked()
        # Submit to shared pool — avoids spawning a new thread per frame advance
        _preload_pool.submit(self.cache.preload_range, start, count, diff_mode, linked)

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        st = self._settings
        self.spin_fps.setValue(int(st.value("fps", 3)))
        self.chk_loop.setChecked(st.value("loop", True, type=bool))
        self.chk_auto_advance.setChecked(st.value("auto_advance", True, type=bool))
        self.chk_crossfade.setChecked(st.value("crossfade", False, type=bool))
        self.chk_linked_stretch.setChecked(st.value("linked_stretch", True, type=bool))
        self.chk_overlay.setChecked(st.value("show_overlay", True, type=bool))
        self.slider_thumb_size.setValue(int(st.value("thumb_size", THUMBNAIL_WIDTH)))
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
        st.setValue("crossfade", self.chk_crossfade.isChecked())
        st.setValue("linked_stretch", self.chk_linked_stretch.isChecked())
        st.setValue("show_overlay", self.chk_overlay.isChecked())
        st.setValue("thumb_size", self.slider_thumb_size.value())
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
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"You have {n_pending} pending change(s).\nApply them before closing?\n\n"
                + "\n".join(summary_parts),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.marker.apply_to_siril(self.siril)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to apply changes:\n{e}")
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        else:
            # Show session summary if user did work
            if n_viewed > 1:
                QMessageBox.information(self, "Session Summary", "\n".join(summary_parts))

        try:
            self.siril.log(f"[BlinkComparator] Session ended. {n_viewed} frames viewed, {n_excluded} excluded.")
        except (SirilError, OSError, RuntimeError):
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
            "<b>1.</b> Load a <b>registered sequence</b> in Siril.<br>"
            "<b>2.</b> Run <b>Blink Comparator</b> from Processing \u2192 Scripts.<br>"
            "<b>3.</b> Go to the <b>Statistics Table</b> tab, sort by FWHM, "
            "and reject the worst frames with <b>B</b> (auto-advances).<br>"
            "<b>4.</b> Click <b style='color:#88aaff;'>Apply Changes to Siril</b> "
            "when done.</div><br>"

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
            "<tr><td style='padding:2px 8px;'><b>D</b></td><td>Toggle difference mode</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Z</b></td><td>Reset zoom</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>T</b></td><td>Pin / toggle A/B comparison</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Ctrl+Z</b></td><td>Undo (single or batch)</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Ctrl+C</b></td><td>Copy frame to clipboard</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>1\u20139</b></td><td>Set FPS directly</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>+ / \u2212</b></td><td>Speed up / slow down</td></tr>"
            "<tr><td style='padding:2px 8px;'><b>Esc</b></td><td>Close</td></tr>"
            "</table><br>"

            "<b style='color:#ffcc66;'>Settings</b><br>"
            "All settings (FPS, loop, auto-advance, crossfade, linked stretch, "
            "overlay, thumbnail size, table sort) are automatically saved between sessions."
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
            "\u2022 <b>Blue dots</b> = included frames<br>"
            "\u2022 <b>Red X</b> = excluded frames<br>"
            "\u2022 <b>White star</b> = current frame<br>"
            "\u2022 <b>Click a dot</b> to jump to that frame<br>"
            "Best combinations: <b>FWHM vs Roundness</b> (star quality), "
            "<b>FWHM vs Background</b> (clouds + seeing).<br><br>"

            "<b style='color:#ffcc66;'>Filmstrip</b><br>"
            "Horizontal thumbnail strip at the bottom (always visible). "
            "Color-coded borders: green = included, red = excluded, blue = current. "
            "Click any thumbnail to jump. Thumbnails load lazily as you scroll. "
            "Adjust size with the slider in Display Options."
        )
        tabs.addTab(te_tabs, "\U0001f4ca Tabs")

        # ---- Tab 3: Frame Selection ----
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

            "<b style='color:#ffcc66;'>Applying Changes</b><br>"
            "All marks are <b>local</b> until you click 'Apply Changes to Siril'. "
            "The pending count in the left panel shows how many changes are queued. "
            "If you close with unsaved changes, you'll be asked whether to apply them."
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
            "\u2022 <b>Normal</b> \u2014 Standard autostretch view. Use for general inspection.<br>"
            "\u2022 <b>Difference</b> \u2014 Absolute difference between each frame and the "
            "reference. Satellites, clouds, and tracking errors appear as bright spots "
            "on a dark background. Toggle with <b>D</b> key.<br>"
            "\u2022 <b>Only included</b> \u2014 Skips excluded frames during playback. "
            "Use after marking to verify all bad frames are gone.<br>"
            "\u2022 <b>Side by Side</b> \u2014 Current frame on the left, reference on the right. "
            "Both zoom and pan together. Good for detailed comparison.<br><br>"

            "<b style='color:#ffcc66;'>Linked Stretch</b><br>"
            "\u2022 <b>ON (default):</b> All frames use the same stretch parameters "
            "(computed from sample frames). Brightness differences between frames "
            "are visible \u2014 important for detecting clouds and haze.<br>"
            "\u2022 <b>OFF:</b> Each frame gets its own autostretch. Better for "
            "comparing fine details, but hides brightness changes.<br><br>"

            "<b style='color:#ffcc66;'>Crossfade Transition</b><br>"
            "When enabled, frames blend smoothly instead of hard-cutting. "
            "Makes subtle motion artifacts (comets, asteroids) easier to spot. "
            "Adds slight playback overhead.<br><br>"

            "<b style='color:#ffcc66;'>Frame Info Overlay</b><br>"
            "Shows frame number, FWHM, roundness, and quality weight in the "
            "top-left corner of the image. Toggle in Display Options. "
            "Useful during playback so you don't have to look away from the image.<br><br>"

            "<b style='color:#ffcc66;'>Thumbnail Size</b><br>"
            "Slider in Display Options (40\u2013160 px). Larger thumbnails = easier "
            "to see, smaller = more frames visible at once.<br><br>"

            "<b style='color:#ffcc66;'>Zoom & Pan</b><br>"
            "\u2022 <b>Scroll wheel:</b> Zoom in/out (0.1x to 20x)<br>"
            "\u2022 <b>Right-click + drag:</b> Pan the zoomed image<br>"
            "\u2022 <b>Z key:</b> Reset to fit-to-window<br>"
            "\u2022 <b>1:1 button:</b> Show at 100% (native pixel size)<br><br>"

            "<b style='color:#ffcc66;'>ROI Blink</b><br>"
            "Click 'Select ROI' in the viewer bar, draw a rectangle on the image. "
            "Only that region is displayed during playback \u2014 perfect for checking "
            "star shapes in a specific corner. Click 'Clear ROI' to return to full frame."
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
            "Bright streaks crossing the frame, usually diagonal. Best seen in "
            "<b>Difference mode</b> (D key) where they appear as bright lines "
            "on a dark background. Reject the affected frame.<br><br>"

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
            "\u2022 Use <b>Difference mode</b> for visual artifacts (satellites, airplanes).<br>"
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
            "  Export Rejected...   Save excluded frame indices as .txt\n"
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
            "  Replicates Siril/PixInsight's STF autostretch.\n"
            "  Global parameters computed from 10 sample frames across the sequence.\n"
            "  Linked mode: same stretch for all frames (shows brightness differences).\n"
            "  Independent mode: per-frame statistics (shows details).\n\n"
            "DIFFERENCE MODE\n"
            "  abs(frame - reference) * 5.0, clipped to [0, 1].\n"
            "  Reference = sequence reference frame (set in Siril's sequence tab).\n\n"
            "FRAME CACHE\n"
            "  LRU cache (80 frames default) with thread-safe double-check locking.\n"
            "  Background preload threads load 5-10 frames ahead of playback.\n"
            "  Separate thumbnail cache (200 entries) for the filmstrip.\n\n"
            "SIRIL API CALLS\n"
            "  get_seq()               Load sequence metadata\n"
            "  get_seq_frame()         Load frame pixel data (with_pixels=True)\n"
            "  get_seq_regdata()       Registration data (FWHM, roundness, stars, BG)\n"
            "  get_seq_stats()         Per-channel statistics (median, sigma)\n"
            "  get_seq_imgdata()       Frame metadata (date_obs, inclusion)\n"
            "  set_seq_frame_incl()    Set frame inclusion status\n\n"
            "REQUIREMENTS\n"
            "  Siril 1.4+ with Python script support\n"
            "  sirilpy (bundled), numpy, PyQt6, matplotlib\n"
            "  Optional: Pillow (for GIF export)\n\n"
            "KEYBOARD SHORTCUTS (FULL LIST)\n"
            "  Space       Play / Pause\n"
            "  Left/Right  Previous / Next frame\n"
            "  Home/End    First / Last frame\n"
            "  G           Mark good (include)\n"
            "  B           Mark bad (exclude)\n"
            "  D           Toggle difference mode\n"
            "  Z           Reset zoom\n"
            "  T           Pin / toggle A/B frame\n"
            "  Ctrl+Z      Undo last marking (single or batch)\n"
            "  Ctrl+C      Copy frame to clipboard\n"
            "  1-9         Set FPS directly\n"
            "  +/-         Speed up / slow down\n"
            "  Esc         Close\n"
        )
        tabs.addTab(te_ref, "\U0001f4d6 Reference")

        layout.addWidget(tabs)
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
# ENTRY POINT
# ==============================================================================

def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        win = BlinkComparatorWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Blink Comparator v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
            pass
        return app.exec()
    except (NoSequenceError, SirilConnectionError):
        QMessageBox.warning(
            None,
            "No Sequence",
            "No sequence is currently loaded in Siril, or Siril is not connected.\n"
            "Please load a sequence first (Open \u2192 Open Sequence)\n"
            "and ensure this script is run from Siril's script menu."
        )
        return 1
    except NoImageError:
        QMessageBox.warning(
            None,
            "No Image",
            "No image or sequence is currently loaded in Siril.\n"
            "Please load a sequence first."
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
