"""
Svenesis Blink Comparator
Script Version: 1.0.0
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
- Frame navigation (first/prev/next/last) and slider
- Keyboard shortcuts (Space, arrows, Home/End, G/B, D, 1-9)
- Three display modes: Normal, Difference (vs. reference), Selected-only
- Frame marking: include/exclude with pending changes and batch apply
- LRU frame cache with background preloading for smooth playback
- Autostretch (Midtone Transfer Function) with global parameters
- Zoom (scroll wheel) and pan (right-click drag)
- Per-frame info display (FWHM, background, noise, exposure, date)
- Dark themed PyQt6 GUI matching the Gradient Analyzer look and feel

Run from Siril via Processing -> Scripts. Place BlinkComparator.py inside a folder
named Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
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
import traceback
import threading
import time
from collections import OrderedDict

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

s.ensure_installed("numpy", "PyQt6")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QSizePolicy, QDialog,
    QScrollArea, QProgressBar, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QImage, QPixmap, QShortcut,
    QKeySequence, QDesktopServices, QWheelEvent, QMouseEvent,
)

VERSION = "1.0.0"

SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "BlinkComparator"

LEFT_PANEL_WIDTH = 340

# Default display size for cached frames
DEFAULT_CACHE_SIZE = 60


# ------------------------------------------------------------------------------
# STYLING (matching GradientAnalyzer)
# ------------------------------------------------------------------------------

def _nofocus(w: QWidget | None) -> None:
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

QSpinBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QSpinBox:focus{border-color:#88aaff}

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

QScrollArea{border:none;background:#2b2b2b}

QProgressBar{background:#3c3c3c;border:1px solid #555;border-radius:3px;text-align:center;color:#ccc}
QProgressBar::chunk{background:#285299;border-radius:2px}
"""


# ------------------------------------------------------------------------------
# AUTOSTRETCH (Midtone Transfer Function)
# ------------------------------------------------------------------------------

def mtf(midtone: float, x: np.ndarray | float) -> np.ndarray | float:
    """Midtone Transfer Function."""
    if isinstance(x, np.ndarray):
        result = np.zeros_like(x, dtype=np.float32)
        mask = (x > 0) & (x < 1)
        denom = (2 * midtone - 1) * x[mask] - midtone
        # Avoid division by zero
        safe = np.abs(denom) > 1e-10
        full_mask = np.zeros_like(x, dtype=bool)
        full_mask_indices = np.where(mask)[0]
        full_mask[full_mask_indices[safe]] = True
        denom_safe = (2 * midtone - 1) * x[full_mask] - midtone
        result[full_mask] = (midtone - 1) * x[full_mask] / denom_safe
        result[x >= 1] = 1.0
        return np.clip(result, 0, 1)
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
    Replicates Siril/PixInsight STF autostretch.

    data: numpy array float32, values 0.0 - 1.0
    Returns: numpy array uint8 (0-255), stretched.

    If global_median/global_mad are provided, uses those instead of
    per-frame statistics (important for consistent brightness across frames).
    """
    if global_median is not None and global_mad is not None:
        median = global_median
        mad = global_mad
    else:
        median = float(np.median(data))
        mad = float(np.median(np.abs(data - median))) * 1.4826

    shadow = max(0.0, median + shadows_clip * mad)
    highlight = 1.0

    rng = highlight - shadow
    if rng < 1e-10:
        rng = 1.0

    if median - shadow > 0:
        midtone = mtf(target_median, median - shadow)
    else:
        midtone = 0.5

    stretched = np.clip((data - shadow) / rng, 0, 1).astype(np.float32)
    stretched = mtf(midtone, stretched)
    return (stretched * 255).astype(np.uint8)


# ------------------------------------------------------------------------------
# FRAME CACHE
# ------------------------------------------------------------------------------

class FrameCache:
    """
    LRU cache for stretched frame preview images.
    Stores frames as QImage objects scaled to display size.
    """

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
        self.cache: OrderedDict[int, QImage] = OrderedDict()
        self.lock = threading.Lock()

        # Global stretch parameters (computed once from sample frames)
        self.global_median: float | None = None
        self.global_mad: float | None = None

        # Reference frame data for difference mode
        self.reference_data: np.ndarray | None = None

    def compute_global_stretch(self, sample_count: int = 10) -> None:
        """Compute stretch parameters from sample frames for consistency."""
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
        """Load the reference frame data for difference mode."""
        ref_idx = self.seq.reference_image
        if ref_idx < 0 or ref_idx >= self.seq.number:
            ref_idx = 0
        try:
            frame = self.siril.get_seq_frame(ref_idx, with_pixels=True)
            if frame is not None and frame.data is not None:
                data = frame.data.astype(np.float32)
                if data.max() > 1.5:
                    data = data / 65535.0
                self.reference_data = data
        except Exception:
            self.reference_data = None

    def get_frame(self, index: int, difference: bool = False) -> QImage | None:
        """Get frame from cache or load from Siril. Returns QImage."""
        cache_key = (index, difference)

        with self.lock:
            if cache_key in self.cache:
                self.cache.move_to_end(cache_key)
                return self.cache[cache_key]

        # Load frame outside lock
        qimg = self._load_and_stretch(index, difference)
        if qimg is None:
            return None

        with self.lock:
            self.cache[cache_key] = qimg
            self.cache.move_to_end(cache_key)
            while len(self.cache) > self.max_frames:
                self.cache.popitem(last=False)

        return qimg

    def _load_and_stretch(self, index: int, difference: bool) -> QImage | None:
        """Load a frame from Siril, stretch it, and convert to QImage."""
        try:
            frame = self.siril.get_seq_frame(index, with_pixels=True)
            if frame is None or frame.data is None:
                return None

            frame_data = frame.data.astype(np.float32)
            if frame_data.max() > 1.5:
                frame_data = frame_data / 65535.0

            if difference and self.reference_data is not None:
                # Compute absolute difference to reference
                ref = self.reference_data
                if frame_data.shape == ref.shape:
                    diff = np.abs(frame_data - ref)
                    diff = np.clip(diff * 5.0, 0, 1)
                    frame_data = diff

            # Determine channels
            if frame_data.ndim == 3 and frame_data.shape[0] == 3:
                r = autostretch(frame_data[0], global_median=self.global_median, global_mad=self.global_mad)
                g = autostretch(frame_data[1], global_median=self.global_median, global_mad=self.global_mad)
                b = autostretch(frame_data[2], global_median=self.global_median, global_mad=self.global_mad)
                h, w = r.shape
                # Siril stores bottom-up → flip
                r = np.flipud(r)
                g = np.flipud(g)
                b = np.flipud(b)
                # Build RGBX (32-bit) for QImage
                rgbx = np.zeros((h, w, 4), dtype=np.uint8)
                rgbx[:, :, 0] = r
                rgbx[:, :, 1] = g
                rgbx[:, :, 2] = b
                rgbx[:, :, 3] = 255
                qimg = QImage(rgbx.data, w, h, w * 4, QImage.Format.Format_RGBX8888).copy()
            elif frame_data.ndim == 3 and frame_data.shape[0] == 1:
                mono = autostretch(frame_data[0], global_median=self.global_median, global_mad=self.global_mad)
                mono = np.flipud(mono)
                h, w = mono.shape
                qimg = QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
            elif frame_data.ndim == 2:
                mono = autostretch(frame_data, global_median=self.global_median, global_mad=self.global_mad)
                mono = np.flipud(mono)
                h, w = mono.shape
                qimg = QImage(mono.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
            else:
                return None

            # Scale to display size
            qimg = qimg.scaled(
                self.display_width, self.display_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            return qimg

        except Exception:
            return None

    def invalidate(self) -> None:
        """Clear entire cache."""
        with self.lock:
            self.cache.clear()

    def preload_range(self, start: int, count: int, difference: bool = False) -> None:
        """Preload a range of frames in the background."""
        total = self.seq.number
        for i in range(start, min(start + count, total)):
            if i < 0:
                continue
            cache_key = (i, difference)
            with self.lock:
                if cache_key in self.cache:
                    continue
            self.get_frame(i, difference)


# ------------------------------------------------------------------------------
# PRELOAD WORKER (signals for thread-safe Qt updates)
# ------------------------------------------------------------------------------

class PreloadSignals(QObject):
    finished = pyqtSignal()


class PreloadWorker(threading.Thread):
    """Background thread that preloads frames ahead of playback."""

    def __init__(self, cache: FrameCache, start: int, count: int, difference: bool = False):
        super().__init__(daemon=True)
        self.cache = cache
        self.start_idx = start
        self.count = count
        self.difference = difference
        self.signals = PreloadSignals()

    def run(self) -> None:
        self.cache.preload_range(self.start_idx, self.count, self.difference)
        self.signals.finished.emit()


# ------------------------------------------------------------------------------
# FRAME MARKER (pending include/exclude changes)
# ------------------------------------------------------------------------------

class FrameMarker:
    """Manages frame inclusion/exclusion markings with pending changes."""

    def __init__(self, seq):
        self.seq = seq
        self.total = seq.number
        # Original inclusion state from Siril
        self.original: dict[int, bool] = {}
        for i in range(self.total):
            try:
                imgdata = None
                # Try the newer API first
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

        # Pending changes: {frame_index: new_included_state}
        self.changes: dict[int, bool] = {}

    def is_included(self, index: int) -> bool:
        """Get current effective inclusion state (original + pending changes)."""
        if index in self.changes:
            return self.changes[index]
        return self.original.get(index, True)

    def mark_include(self, index: int) -> None:
        if self.original.get(index, True) and index not in self.changes:
            return
        if self.original.get(index, True):
            # Was originally included and no change needed
            self.changes.pop(index, None)
        else:
            self.changes[index] = True

    def mark_exclude(self, index: int) -> None:
        if not self.original.get(index, True) and index not in self.changes:
            return
        if not self.original.get(index, True):
            self.changes.pop(index, None)
        else:
            self.changes[index] = False

    def get_pending_count(self) -> int:
        return len(self.changes)

    def get_newly_excluded_count(self) -> int:
        return sum(1 for v in self.changes.values() if not v)

    def get_newly_included_count(self) -> int:
        return sum(1 for v in self.changes.values() if v)

    def apply_to_siril(self, siril_iface) -> str:
        """Apply all pending changes to Siril. Returns summary string."""
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

        # Update originals
        for idx, val in self.changes.items():
            self.original[idx] = val
        self.changes.clear()

        return msg


# ------------------------------------------------------------------------------
# ZOOMABLE IMAGE WIDGET
# ------------------------------------------------------------------------------

class ImageCanvas(QWidget):
    """Widget that displays a QImage with zoom and pan support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap: QPixmap | None = None
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._dragging: bool = False
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._drag_pan_start_x: float = 0.0
        self._drag_pan_start_y: float = 0.0

        self.setStyleSheet("background-color: #1a1a1a;")

    def set_image(self, qimg: QImage | None) -> None:
        """Set the image to display."""
        if qimg is None:
            self._pixmap = None
        else:
            self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    def reset_view(self) -> None:
        """Reset zoom and pan."""
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(26, 26, 26))

        if self._pixmap is None:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("sans-serif", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No frame loaded")
            return

        # Calculate scaled size
        pw = self._pixmap.width() * self._zoom
        ph = self._pixmap.height() * self._zoom

        # Center with pan offset
        x = (self.width() - pw) / 2 + self._pan_x
        y = (self.height() - ph) / 2 + self._pan_y

        from PyQt6.QtCore import QRectF
        target = QRectF(x, y, pw, ph)
        source = QRectF(0, 0, self._pixmap.width(), self._pixmap.height())
        painter.drawPixmap(target, self._pixmap, source)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self._zoom * 1.15, 20.0)
        elif delta < 0:
            self._zoom = max(self._zoom / 1.15, 0.1)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton or event.button() == Qt.MouseButton.MiddleButton:
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
        if event.button() == Qt.MouseButton.RightButton or event.button() == Qt.MouseButton.MiddleButton:
            self._dragging = False


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class BlinkComparatorWindow(QMainWindow):
    """
    Main window for the Blink Comparator.

    Left panel: playback controls, display mode, frame marking.
    Right panel: zoomable image canvas with frame info bar.
    """

    def __init__(self, siril_iface=None):
        super().__init__()
        self.siril = siril_iface or s.SirilInterface()

        # Ensure connection to Siril is established
        if not self.siril.connected:
            self.siril.connect()

        # Load sequence
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
        self.direction: int = 1  # 1=forward, -1=backward

        # Frame marker
        self.marker = FrameMarker(self.seq)

        # Settings
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        # Build UI
        self._init_ui()
        self._load_settings()
        self._setup_shortcuts()

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        # Frame cache (sized after UI is built)
        self.cache: FrameCache | None = None

        # Deferred initialization after window is shown
        QTimer.singleShot(100, self._deferred_init)

    def _deferred_init(self) -> None:
        """Initialize cache and load first frame after window is visible."""
        canvas_w = max(400, self.canvas.width())
        canvas_h = max(300, self.canvas.height())

        self.cache = FrameCache(
            self.siril, self.seq,
            max_frames=DEFAULT_CACHE_SIZE,
            display_width=canvas_w,
            display_height=canvas_h,
        )

        # Progress for initialization
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Computing stretch parameters...")
        self.progress_bar.setValue(20)
        QApplication.processEvents()

        self.cache.compute_global_stretch()

        self.progress_bar.setFormat("Loading reference frame...")
        self.progress_bar.setValue(50)
        QApplication.processEvents()

        self.cache.load_reference_frame()

        self.progress_bar.setFormat("Loading first frame...")
        self.progress_bar.setValue(80)
        QApplication.processEvents()

        self._show_frame(0)

        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Ready")
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

        # Preload next frames
        self._start_preload(1, 10)

        # Log startup
        try:
            nb_incl = sum(1 for i in range(self.total_frames) if self.marker.is_included(i))
            nb_excl = self.total_frames - nb_incl
            img_type = "RGB" if self.seq.nb_layers == 3 else "Mono"
            self.siril.log(
                f"[BlinkComparator] Sequence loaded: {self.seq.seqname} "
                f"({self.total_frames} frames, {self.seq.rx}x{self.seq.ry}, {img_type})"
            )
            self.siril.log(f"[BlinkComparator] {nb_incl} included, {nb_excl} excluded")
        except (SirilError, OSError, RuntimeError):
            pass

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

        # Title
        lbl = QLabel(f"Svenesis Blink Comparator {VERSION}")
        lbl.setStyleSheet("font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_playback_group(layout)
        self._build_mode_group(layout)
        self._build_marking_group(layout)

        layout.addStretch()

        # Buy me a Coffee / Help / Close
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

        # Transport buttons row
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

        # Frame slider
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, max(0, self.total_frames - 1))
        self.frame_slider.setValue(0)
        self.frame_slider.setToolTip("Drag to navigate frames")
        _nofocus(self.frame_slider)
        self.frame_slider.valueChanged.connect(self._on_slider_changed)
        g_layout.addWidget(self.frame_slider)

        # Speed control
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

        # Loop checkbox
        self.chk_loop = QCheckBox("Loop playback")
        self.chk_loop.setChecked(True)
        self.chk_loop.setToolTip("Restart from first frame after reaching the last")
        _nofocus(self.chk_loop)
        g_layout.addWidget(self.chk_loop)

        # Progress bar
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
        self.radio_normal.setToolTip(
            "Show each frame with autostretch.\n"
            "Standard mode for visual inspection."
        )
        self.radio_diff = QRadioButton("Difference (vs. reference)")
        self.radio_diff.setToolTip(
            "Show the absolute difference of each frame to the\n"
            "reference frame. Highlights satellites, clouds,\n"
            "tracking errors, and moving objects."
        )
        self.radio_selected = QRadioButton("Only included frames")
        self.radio_selected.setToolTip(
            "Skip excluded frames during playback.\n"
            "Useful to verify after marking bad frames."
        )

        self.mode_group.addButton(self.radio_normal, 0)
        self.mode_group.addButton(self.radio_diff, 1)
        self.mode_group.addButton(self.radio_selected, 2)

        for radio in (self.radio_normal, self.radio_diff, self.radio_selected):
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

        # Pending changes info
        self.lbl_pending = QLabel("No pending changes")
        self.lbl_pending.setStyleSheet("color: #999; font-size: 9pt;")
        self.lbl_pending.setWordWrap(True)
        g_layout.addWidget(self.lbl_pending)

        # Apply button
        self.btn_apply = QPushButton("Apply Changes to Siril")
        self.btn_apply.setObjectName("ApplyButton")
        self.btn_apply.setToolTip(
            "Send all pending include/exclude changes to Siril.\n"
            "Changes are only applied when you click this button."
        )
        _nofocus(self.btn_apply)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_changes)
        g_layout.addWidget(self.btn_apply)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(5, 5, 5, 5)

        # Frame info bar
        self.lbl_frame_info = QLabel("No sequence loaded")
        self.lbl_frame_info.setStyleSheet("font-size: 10pt; color: #999;")
        r_layout.addWidget(self.lbl_frame_info)

        # Image canvas
        self.canvas = ImageCanvas()
        r_layout.addWidget(self.canvas, 1)

        # Zoom info bar
        zoom_bar = QHBoxLayout()
        self.lbl_zoom = QLabel("Zoom: Fit")
        self.lbl_zoom.setStyleSheet("color: #777; font-size: 9pt;")
        zoom_bar.addWidget(self.lbl_zoom)

        btn_reset_zoom = QPushButton("Reset Zoom (Z)")
        btn_reset_zoom.setStyleSheet("padding: 3px 8px; font-size: 9pt;")
        _nofocus(btn_reset_zoom)
        btn_reset_zoom.clicked.connect(self._reset_zoom)
        zoom_bar.addWidget(btn_reset_zoom)

        zoom_bar.addStretch()

        self.lbl_shortcuts = QLabel(
            "Space=Play  \u2190\u2192=Nav  Home/End  G/B=Mark  D=Diff  Z=Zoom  1-9=FPS  Esc=Close"
        )
        self.lbl_shortcuts.setStyleSheet("color: #666; font-size: 8pt;")
        zoom_bar.addWidget(self.lbl_shortcuts)

        r_layout.addLayout(zoom_bar)

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

        # Number keys 1-9 for direct FPS setting
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

    def _advance_frame(self) -> None:
        """Called by timer to advance to next frame."""
        if not self.playing:
            return

        next_frame = self.current_frame + self.direction
        only_included = self.radio_selected.isChecked()

        # Skip excluded frames if in selected-only mode
        if only_included:
            attempts = 0
            while 0 <= next_frame < self.total_frames and attempts < self.total_frames:
                if self.marker.is_included(next_frame):
                    break
                next_frame += self.direction
                attempts += 1

        # Handle wrap-around or stop
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

        # Preload ahead
        self._start_preload(
            next_frame + self.direction * 2,
            5,
        )

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
        """Display a specific frame."""
        if index < 0 or index >= self.total_frames:
            return

        self.current_frame = index

        # Update slider without triggering signal loop
        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(index)
        self.frame_slider.blockSignals(False)

        # Get frame from cache
        diff_mode = self.radio_diff.isChecked()
        if self.cache is not None:
            qimg = self.cache.get_frame(index, difference=diff_mode)
            self.canvas.set_image(qimg)

        # Update frame info
        self._update_frame_info(index)

    def _update_frame_info(self, index: int) -> None:
        """Update the frame info label."""
        incl = self.marker.is_included(index)
        incl_str = "included" if incl else "EXCLUDED"
        incl_color = "#55aa55" if incl else "#dd4444"

        parts = [
            f"Frame <b>{index + 1}</b> / {self.total_frames}",
            f"<span style='color:{incl_color};'>{incl_str}</span>",
        ]

        # Try to get registration data (FWHM, roundness, quality)
        try:
            reg = self.siril.get_seq_regdata(index, 0)
            if reg is not None:
                if hasattr(reg, 'fwhm') and reg.fwhm > 0:
                    parts.append(f"FWHM: {reg.fwhm:.2f}\"")
                if hasattr(reg, 'roundness') and reg.roundness > 0:
                    parts.append(f"Round: {reg.roundness:.2f}")
                if hasattr(reg, 'background_lvl') and reg.background_lvl > 0:
                    parts.append(f"BG: {reg.background_lvl:.4f}")
                if hasattr(reg, 'number_of_stars') and reg.number_of_stars > 0:
                    parts.append(f"Stars: {reg.number_of_stars}")
        except Exception:
            pass

        # Try to get statistics
        try:
            stats = self.siril.get_seq_stats(index, 0)
            if stats is not None:
                if hasattr(stats, 'median'):
                    parts.append(f"Med: {stats.median:.4f}")
                if hasattr(stats, 'sigma') and stats.sigma > 0:
                    parts.append(f"\u03C3: {stats.sigma:.4f}")
        except Exception:
            pass

        # Try to get image data (exposure, date)
        try:
            imgdata = self.siril.get_seq_imgdata(index)
            if imgdata is not None:
                if hasattr(imgdata, 'date_obs') and imgdata.date_obs:
                    parts.append(f"{imgdata.date_obs}")
        except Exception:
            pass

        info_str = " &nbsp;\u2502&nbsp; ".join(parts)
        self.lbl_frame_info.setText(info_str)
        self.lbl_frame_info.setTextFormat(Qt.TextFormat.RichText)

        # Update zoom label
        zoom_pct = int(self.canvas._zoom * 100)
        self.lbl_zoom.setText(f"Zoom: {zoom_pct}%")

    # ------------------------------------------------------------------
    # DISPLAY MODES
    # ------------------------------------------------------------------

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        # Invalidate cache when switching to/from difference mode
        if self.cache is not None:
            self.cache.invalidate()
        self._show_frame(self.current_frame)

    def _toggle_diff_mode(self) -> None:
        if self.radio_diff.isChecked():
            self.radio_normal.setChecked(True)
        else:
            self.radio_diff.setChecked(True)

    # ------------------------------------------------------------------
    # FRAME MARKING
    # ------------------------------------------------------------------

    def _mark_include(self) -> None:
        self.marker.mark_include(self.current_frame)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)

    def _mark_exclude(self) -> None:
        self.marker.mark_exclude(self.current_frame)
        self._update_marking_ui()
        self._update_frame_info(self.current_frame)

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
            self,
            "Apply Changes",
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
    # ZOOM
    # ------------------------------------------------------------------

    def _reset_zoom(self) -> None:
        self.canvas.reset_view()
        self.lbl_zoom.setText("Zoom: Fit")

    # ------------------------------------------------------------------
    # PRELOADING
    # ------------------------------------------------------------------

    def _start_preload(self, start: int, count: int) -> None:
        if self.cache is None:
            return
        diff_mode = self.radio_diff.isChecked()
        worker = PreloadWorker(self.cache, start, count, diff_mode)
        worker.start()

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        st = self._settings
        self.spin_fps.setValue(int(st.value("fps", 3)))
        self.chk_loop.setChecked(st.value("loop", True, type=bool))

    def _save_settings(self) -> None:
        st = self._settings
        st.setValue("fps", self.spin_fps.value())
        st.setValue("loop", self.chk_loop.isChecked())

    def closeEvent(self, event) -> None:
        self._pause()
        self._save_settings()

        # Warn about unsaved changes
        if self.marker.get_pending_count() > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have {self.marker.get_pending_count()} pending frame marking change(s).\n"
                "Apply them before closing?",
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

        # Log session summary
        try:
            self.siril.log("[BlinkComparator] Session ended.")
        except (SirilError, OSError, RuntimeError):
            pass

        super().closeEvent(event)

    # ------------------------------------------------------------------
    # COFFEE DIALOG
    # ------------------------------------------------------------------

    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"

        dlg = QDialog(self)
        dlg.setWindowTitle("\u2615 Support Svenesis Blink Comparator")
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
            "<b style='color:#e0e0e0;'>Enjoying the Svenesis Blink Comparator?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If this tool has saved you time, helped you spot bad frames, "
            "or made your frame selection workflow better \u2014 consider buying "
            "me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>\u2615 Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br><br>"
            "<span style='color:#aaaaaa;'>Your support helps maintain:</span><br>"
            "\u2022 Svenesis Gradient Analyzer \u2022 Svenesis Blink Comparator<br>"
            "\u2022 Svenesis Multiple Histogram Viewer \u2022 Svenesis Script Security Scanner<br>"
            "</div>"
        )
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)

        layout.addSpacing(8)

        btn_open = QPushButton("\u2615  Buy me a Coffee  \u2615")
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
            f"Clear skies \u2728</span>"
            f"</div>"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        footer.setOpenExternalLinks(True)
        layout.addWidget(footer)

        dlg.exec()

    # ------------------------------------------------------------------
    # HELP DIALOG
    # ------------------------------------------------------------------

    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Svenesis Blink Comparator \u2014 Help")
        dlg.setMinimumSize(700, 550)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}"
        )
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)

        from PyQt6.QtWidgets import QTextEdit

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet(
            "QTextEdit{background-color:#2b2b2b;color:#e0e0e0;"
            "border:1px solid #444;border-radius:4px;padding:12px;"
            "font-size:10pt;}"
        )
        text.setHtml("""
<h2 style='color:#88aaff;'>Blink Comparator</h2>
<p>Animates the currently loaded sequence for rapid visual inspection.
Similar to PixInsight's Blink process.</p>

<h3 style='color:#88aaff;'>Getting Started</h3>
<ol>
<li>Load a sequence in Siril (Open &rarr; Open Sequence)</li>
<li>Run the Blink Comparator script</li>
<li>Press <b>Space</b> or click <b>Play</b> to start the animation</li>
<li>Mark bad frames with <b>B</b>, good frames with <b>G</b></li>
<li>Click <b>Apply Changes to Siril</b> when done</li>
</ol>

<h3 style='color:#88aaff;'>Keyboard Shortcuts</h3>
<table style='color:#cccccc;'>
<tr><td style='padding:2px 12px;'><b>Space</b></td><td>Play / Pause</td></tr>
<tr><td style='padding:2px 12px;'><b>&larr; / &rarr;</b></td><td>Previous / Next frame</td></tr>
<tr><td style='padding:2px 12px;'><b>Home / End</b></td><td>First / Last frame</td></tr>
<tr><td style='padding:2px 12px;'><b>G</b></td><td>Mark frame as good (include)</td></tr>
<tr><td style='padding:2px 12px;'><b>B</b></td><td>Mark frame as bad (exclude)</td></tr>
<tr><td style='padding:2px 12px;'><b>D</b></td><td>Toggle difference mode</td></tr>
<tr><td style='padding:2px 12px;'><b>Z</b></td><td>Reset zoom</td></tr>
<tr><td style='padding:2px 12px;'><b>1&ndash;9</b></td><td>Set playback speed (FPS)</td></tr>
<tr><td style='padding:2px 12px;'><b>+ / &minus;</b></td><td>Speed up / slow down</td></tr>
<tr><td style='padding:2px 12px;'><b>Esc</b></td><td>Close</td></tr>
</table>

<h3 style='color:#88aaff;'>Display Modes</h3>
<p><b>Normal:</b> Shows each frame with autostretch. Use this for general inspection.</p>
<p><b>Difference:</b> Shows the absolute difference between each frame and the
reference frame. Bright spots indicate changes &mdash; satellites, clouds, tracking
errors, or moving objects become immediately visible.</p>
<p><b>Only included:</b> Skips excluded frames during playback. Use this after
marking to verify all bad frames have been removed.</p>

<h3 style='color:#88aaff;'>Zoom &amp; Pan</h3>
<p><b>Scroll wheel:</b> Zoom in/out on the image.</p>
<p><b>Right-click + drag:</b> Pan the zoomed image.</p>
<p><b>Z key:</b> Reset to fit-to-window view.</p>

<h3 style='color:#88aaff;'>Frame Marking</h3>
<p>Markings are collected locally and <b>not sent to Siril</b> until you click
<b>Apply Changes</b>. This prevents accidental changes. The pending count
shows how many frames have been marked.</p>

<h3 style='color:#88aaff;'>What to Look For</h3>
<ul>
<li><b>Satellite trails:</b> Bright streaks crossing the frame (best seen in Difference mode)</li>
<li><b>Clouds/haze:</b> Overall brightness changes between frames</li>
<li><b>Tracking errors:</b> Sudden shifts or elongated stars</li>
<li><b>Focus drift:</b> Gradually increasing star FWHM over time</li>
<li><b>Airplane lights:</b> Blinking or moving bright spots</li>
<li><b>Dew/frost:</b> Gradual increase in haze/background brightness</li>
</ul>

<h3 style='color:#88aaff;'>Tips</h3>
<ul>
<li>Start at 3 FPS and increase speed once frames are cached</li>
<li>Use Difference mode to spot subtle artifacts</li>
<li>Check the FWHM values in the info bar for focus quality</li>
<li>The reference frame is set in Siril's sequence tab</li>
</ul>
""")
        layout.addWidget(text)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton{background-color:#444;color:#ddd;border:1px solid #666;"
            "padding:6px;font-weight:bold;border-radius:4px}"
            "QPushButton:hover{background-color:#555}"
        )
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

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
            siril.log(f"Svenesis Blink Comparator v{VERSION} loaded.")
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
            "Svenesis Blink Comparator Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
