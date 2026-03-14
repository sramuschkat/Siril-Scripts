"""
Siril Histogram Viewer

Reads the current linear image from Siril, applies autostretch, and displays
a combined RGB histogram with normal/log modes, axis scaling, and Fit Histogram.
Supports loading linear FITS files and up to 3 comparison stretched FITS files.

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later
Contact: Siril forum / scripts repository

Menu section: Siril uses the script's parent folder name as the Scripts menu section.
To show this script under "Utility", place HistogramViewer.py inside a folder named
Utility in one of Siril's Script Storage Directories (Preferences → Scripts).
"""

from __future__ import annotations

import os
import sys
import traceback
import math
import numpy as np

import sirilpy as s
from sirilpy import NoImageError

try:
    from sirilpy.exceptions import SirilError, SirilConnectionError
except ImportError:
    # Fallback for older sirilpy without these exceptions (then we only catch NoImageError)
    class _SirilErrorPlaceholder(Exception):
        pass
    SirilError = _SirilErrorPlaceholder
    SirilConnectionError = _SirilErrorPlaceholder

s.ensure_installed("numpy", "PyQt6", "Pillow", "astropy", "matplotlib")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QRadioButton, QCheckBox, QGraphicsView, QButtonGroup,
    QGraphicsScene, QGraphicsPixmapItem,
    QFileDialog, QSizePolicy, QDialog, QTextEdit,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QRectF, QTimer, QPointF, QEvent, QObject
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QPen, QPainterPath, QFont, QMouseEvent

VERSION = "1.0.0"

# Layout constants
LEFT_PANEL_WIDTH = 320
COL_MIN_WIDTH = 280  # ensure x-axis labels fit when extra columns (FITS 1–3) are visible
COL_MIN_HEIGHT = 480
VIEW_MIN_WIDTH = 220
VIEW_MIN_HEIGHT = 180
STATS_LABEL_MIN_HEIGHT = 60
FILENAME_BUTTON_MAX_LEN = 40
HISTOGRAM_BINS = 256

# Luminance coefficients: Rec.709 (BT.709) — same as sRGB for luminance.
LUMINANCE_R = 0.2126
LUMINANCE_G = 0.7152
LUMINANCE_B = 0.0722

# Performance: downscale display when image exceeds this (reduces memory and paint time)
DISPLAY_MAX_DIMENSION = 4096

# ------------------------------------------------------------------------------
# STYLING
# ------------------------------------------------------------------------------

def _nofocus(w) -> None:
    """Disable focus on widget to avoid keyboard focus issues."""
    try:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    except (AttributeError, TypeError):
        pass


def _adu_max_from_data(pixeldata: np.ndarray) -> int:
    """
    Derive ADU max from the actual max value in the linear image data.
    Used for normalization and ADU display.
    """
    if pixeldata.dtype == np.uint8:
        return max(1, int(np.max(pixeldata)))
    if pixeldata.dtype == np.uint16:
        return max(1, int(np.max(pixeldata)))
    if pixeldata.dtype == np.int16:
        return 65535  # int16 uses fixed scaling
    return 65535


def _prepare_display_image(img: np.ndarray, max_dim: int = DISPLAY_MAX_DIMENSION) -> tuple[np.ndarray, int, int]:
    """
    Convert float 0-1 image to uint8 for display, optionally downscaling.
    Returns (uint8 array HWC, display_h, display_w).
    """
    disp = np.clip(img * 255, 0, 255).astype(np.uint8)
    if disp.ndim == 2:
        disp = np.dstack([disp, disp, disp])
    h, w = disp.shape[0], disp.shape[1]
    if max(h, w) <= max_dim:
        disp = np.flipud(disp)
        return np.ascontiguousarray(disp), h, w
    scale = max_dim / max(h, w)
    new_h, new_w = max(1, int(h * scale)), max(1, int(w * scale))
    try:
        from PIL import Image
        pil_img = Image.fromarray(disp)
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        disp = np.array(pil_img)
    except ImportError:
        step_h = max(1, (h - 1) // new_h + 1) if new_h < h else 1
        step_w = max(1, (w - 1) // new_w + 1) if new_w < w else 1
        disp = disp[::step_h, ::step_w, :]
        disp = disp[:new_h, :new_w, :]
    disp = np.flipud(disp)
    return np.ascontiguousarray(disp), new_h, new_w


def _empty_histogram_data() -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Return empty histogram dict and bin edges for clearing histogram widgets."""
    edges = np.linspace(0, 1, HISTOGRAM_BINS + 1)
    hist = {ch: np.zeros(HISTOGRAM_BINS) for ch in ("RGB", "R", "G", "B", "L")}
    return hist, edges


STATS_MAX_PIXELS = 5_000_000
"""Maximum number of pixels to use for statistics and histograms.

Large images are subsampled to stay under this limit so that np.percentile / np.mean /
np.std and np.histogram stay responsive while remaining visually representative.
"""


def _subsample_for_stats(arr: np.ndarray, max_pixels: int = STATS_MAX_PIXELS) -> np.ndarray:
    """
    Return a possibly-subsampled view of ``arr`` for statistics and histograms.

    If ``arr.size`` exceeds ``max_pixels``, the array is subsampled with a uniform stride
    in X and Y so that the resulting view has roughly ``max_pixels`` elements. This keeps
    histogram and statistics computations fast on huge images while remaining
    representative. Small and medium images are returned unchanged.
    """
    if arr.size <= max_pixels:
        return arr
    h, w = arr.shape[0], arr.shape[1]
    if h <= 0 or w <= 0:
        return arr
    # Choose a single stride for both axes so that total pixels ~= max_pixels.
    stride = int(math.ceil(math.sqrt(arr.size / float(max_pixels))))
    stride = max(1, stride)
    return arr[::stride, ::stride, ...]


SURFACE_PLOT_MAX_SIDE = 100
"""Maximum side length for the 3D surface plot grid (keeps the dialog responsive)."""


def _image_to_intensity_2d(img: np.ndarray) -> np.ndarray:
    """
    Convert image to a 2D intensity array for 3D surface plot.
    RGB images use Rec.709 luminance; grayscale is returned as-is.
    """
    if img.ndim == 2:
        return img.astype(np.float32, copy=False)
    if img.ndim == 3 and img.shape[2] >= 3:
        return (LUMINANCE_R * img[:, :, 0] + LUMINANCE_G * img[:, :, 1] + LUMINANCE_B * img[:, :, 2]).astype(np.float32)
    return img.reshape(img.shape[0], -1).astype(np.float32)


def _image_to_channel_2d(img: np.ndarray, channel: str) -> np.ndarray:
    """
    Extract a 2D channel array for 3D surface plot. channel in ('RGB','R','G','B','L').
    RGB/L = Rec.709 luminance; R,G,B = red/green/blue. Grayscale: same for all.
    """
    if img.ndim == 2:
        return img.astype(np.float32, copy=False)
    if img.ndim == 3 and img.shape[2] >= 3:
        if channel == "R":
            return img[:, :, 0].astype(np.float32)
        if channel == "G":
            return img[:, :, 1].astype(np.float32)
        if channel == "B":
            return img[:, :, 2].astype(np.float32)
        if channel in ("L", "RGB"):
            return (LUMINANCE_R * img[:, :, 0] + LUMINANCE_G * img[:, :, 1] + LUMINANCE_B * img[:, :, 2]).astype(np.float32)
    return img.reshape(img.shape[0], -1).astype(np.float32)


DARK_STYLESHEET = """
QWidget{background-color:#2b2b2b;color:#e0e0e0;font-size:10pt}

QToolTip{background-color:#333333;color:#ffffff;border:1px solid #88aaff}

QGroupBox{border:1px solid #444444;margin-top:5px;font-weight:bold;border-radius:4px;padding-top:12px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 3px;color:#88aaff}

QLabel{color:#cccccc}

QRadioButton,QCheckBox{color:#cccccc;spacing:5px}
QRadioButton::indicator,QCheckBox::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:7px}
QCheckBox::indicator{border-radius:3px}
QRadioButton::indicator:checked{background:qradialgradient(cx:0.5,cy:0.5,radius:0.4,fx:0.5,fy:0.5,stop:0 #ffffff,stop:1 #285299);border:1px solid #88aaff;image:none}
QCheckBox::indicator:checked{background:#285299;border:1px solid #88aaff;image:none}
QRadioButton:hover{background-color:#333333;border-radius:4px}

QDoubleSpinBox,QSpinBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:70px}
QDoubleSpinBox:focus,QSpinBox:focus{border-color:#88aaff}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#ZoomBtn{min-width:30px;font-weight:bold;background-color:#3c3c3c}

QGraphicsView{border:none;background-color:#151515}
"""


# ------------------------------------------------------------------------------
# IMAGE PROCESSING
# ------------------------------------------------------------------------------

def normalize_input(img_data: np.ndarray, adu_max: int | None = None) -> np.ndarray:
    """
    Normalize input to 0.0-1.0 float32.

    For uint16, adu_max (255, 4095, 16383, 65535) controls the divisor.
    Handles uint8, uint16, int16; clips and scales outliers via 99.99th percentile.

    Returns:
        Float32 array in [0, 1] range, HWC format.
    """
    img = img_data.astype(np.float32, copy=False)
    if img_data.dtype == np.uint8:
        img = img / 255.0
    elif img_data.dtype == np.uint16:
        div = float(adu_max) if adu_max is not None else 65535.0
        img = img / div
    elif img_data.dtype == np.int16:
        img = (img + 32768.0) / 65535.0
    mn = float(np.min(img))
    if mn < 0.0:
        img = np.maximum(img, 0.0)
    mx = float(np.max(img))
    if mx > 1.0 + 1e-4:
        p = float(np.percentile(img, 99.99))
        if p > 0.0:
            img = img / p
    return np.clip(img, 0.0, 1.0).astype(np.float32, copy=False)


def ensure_hwc(img: np.ndarray) -> np.ndarray:
    """
    Ensure image is Height-Width-Channels (HWC) format.

    Converts 2D to 3-channel grayscale; handles various 3D layouts (CHW, HWC).
    """
    if img.ndim == 2:
        return np.dstack([img, img, img])
    if img.ndim == 3:
        if img.shape[0] == 1 and img.shape[2] != 3:
            m = img[0, :, :]
            return np.dstack([m, m, m])
        if img.shape[2] == 1:
            m = img[:, :, 0]
            return np.dstack([m, m, m])
        if img.shape[2] == 3:
            return img
        if img.shape[0] == 3:
            return img.transpose(1, 2, 0)
    return img


def autostretch_percentile(img: np.ndarray, low: float = 2, high: float = 98) -> np.ndarray:
    """
    Apply percentile-based autostretch.

    Maps [low, high] percentiles to [0, 1]. Pure numpy, no numba.
    """
    img = img.astype(np.float32, copy=False)
    p_low, p_high = np.percentile(img, [low, high])
    if p_high <= p_low:
        return np.clip(img, 0.0, 1.0).astype(np.float32)
    stretched = (img - p_low) / (p_high - p_low)
    return np.clip(stretched, 0.0, 1.0).astype(np.float32)


def load_fits_pixeldata(path: str) -> np.ndarray:
    """
    Load FITS image from path.

    Returns numpy array (H, W) or (H, W, C). Preserves dtype for linear FITS.
    Handles 2D and 3D HDUs; transposes (n,H,W) to (H,W,n) for n in {1,3}.

    Raises:
        ValueError: If no image HDU found.
    """
    from astropy.io import fits
    with fits.open(path) as hdul:
        for hdu in hdul:
            if hdu.data is not None and hasattr(hdu.data, "shape"):
                data = np.asarray(hdu.data)
                if data.ndim == 2:
                    return data
                if data.ndim == 3:
                    # (n, H, W) -> (H, W, n) for n in {1,3}
                    if data.shape[0] in (1, 3):
                        return np.transpose(data, (1, 2, 0))
                    if data.shape[2] in (1, 3):
                        return data
                    return data
    raise ValueError("No image HDU found in FITS file")


def normalize_stretched_fits(arr: np.ndarray) -> np.ndarray:
    """
    Normalize already-stretched FITS to 0-1 float32 HWC.

    Uses max from each file's data (like linear), not fixed bit-depth.
    uint8/uint16→divide by actual max; float→clip [0,1].
    """
    arr = np.asarray(arr)
    if arr.dtype == np.uint8:
        div = max(1.0, float(np.max(arr)))
        img = arr.astype(np.float32, copy=False) / div
    elif arr.dtype == np.uint16:
        div = max(1.0, float(np.max(arr)))
        img = arr.astype(np.float32, copy=False) / div
    else:
        img = arr.astype(np.float32, copy=False)
        img = np.clip(img, 0.0, 1.0)
    return ensure_hwc(np.clip(img, 0.0, 1.0)).astype(np.float32, copy=False)


# ------------------------------------------------------------------------------
# HISTOGRAM WIDGET
# ------------------------------------------------------------------------------

class HistogramWidget(QWidget):
    """Custom widget for displaying combined RGB and per-channel histograms."""

    # Channel colors: RGB (white), R (red), G (green), B (blue)
    CHANNEL_COLORS = {
        'RGB': QColor(255, 255, 255),
        'R': QColor(255, 80, 80),
        'G': QColor(80, 255, 80),
        'B': QColor(80, 80, 255),
        'L': QColor(255, 220, 50),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 240)  # ensure axes and labels fit when columns are narrow
        self.histograms = {}  # 'RGB', 'R', 'G', 'B' -> np array of counts
        self.bin_edges = None
        self.visible = {'RGB': True, 'R': True, 'G': True, 'B': True, 'L': True}  # L on by default (matches UI checkbox)
        self.log_mode = False
        self.x_axis_mode = 'adu'  # fixed to ADU mode
        self.adu_max = 65535
        self.x_min = 0.0
        self.x_max = 1.0
        self.y_min = 0.0
        self.y_max = 1.0
        self._y_max_raw = 1.0  # max count for fit
        self._clicked_intensity = None  # intensity at last image click (for vertical line)
        self._clicked_px = None  # pixel x at last click (for label)
        self._clicked_py = None  # pixel y at last click (for label)

    def set_clicked_value(
        self, intensity: float | None, px: int | None = None, py: int | None = None
    ) -> None:
        """Set the intensity value to show as a vertical line (from image click). Optionally px, py for label. None to clear."""
        self._clicked_intensity = intensity
        self._clicked_px = px
        self._clicked_py = py
        self.update()

    def set_x_axis_mode(self, mode, adu_max=65535):
        """Set X-axis display to ADU (0-adu_max). Intensity mode is no longer supported."""
        self.x_axis_mode = 'adu'
        self.adu_max = adu_max
        self.update()

    def set_histograms(self, histograms_dict, bin_edges):
        """Set histogram data. histograms_dict: {'RGB': array, 'R': array, 'G': array, 'B': array}."""
        self.histograms = {k: np.asarray(v, dtype=np.float64) for k, v in histograms_dict.items()}
        self.bin_edges = np.asarray(bin_edges, dtype=np.float64)
        all_counts = np.concatenate([h for h in self.histograms.values() if h.size > 0]) if self.histograms else np.array([0])
        self._y_max_raw = float(np.max(all_counts)) if all_counts.size > 0 else 1.0
        self.x_min = 0.0
        self.x_max = 1.0
        self.y_min = 0.0
        self.y_max = self._y_max_raw if not self.log_mode else math.log10(self._y_max_raw + 1)
        self.update()

    def set_visibility(self, rgb=True, r=True, g=True, b=True, l=False):
        """Toggle which channel curves are visible."""
        self.visible = {'RGB': rgb, 'R': r, 'G': g, 'B': b, 'L': l}
        self.update()

    def set_log_mode(self, log_mode):
        self.log_mode = log_mode
        if self.histograms:
            all_counts = np.concatenate([h for h in self.histograms.values() if h.size > 0])
            if all_counts.size > 0:
                mx = float(np.max(all_counts))
                self.y_max = math.log10(mx + 1) if log_mode else mx
        self.update()

    def set_axis_limits(self, x_min, x_max, y_min, y_max):
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.update()

    def get_fit_extent(self):
        """Return (x_min, x_max, y_min, y_max) for fit, or None if no data."""
        channel_keys = ["RGB", "R", "G", "B", "L"]
        visible_hists = [
            self.histograms[k]
            for k in channel_keys
            if self.visible.get(k) and k in self.histograms and self.histograms[k].size > 0
        ]
        if not visible_hists:
            return None
        combined = np.maximum.reduce(visible_hists) if len(visible_hists) > 1 else visible_hists[0]
        nonzero = np.nonzero(combined)[0]
        if len(nonzero) == 0:
            return None
        i_min, i_max = int(nonzero[0]), int(nonzero[-1])
        n = len(combined)
        margin = 0.05 * (i_max - i_min + 1) if i_max > i_min else 1
        i_min = max(0, int(i_min - margin))
        i_max = min(n - 1, int(i_max + margin))
        x_min = self.bin_edges[i_min]
        x_max = self.bin_edges[min(i_max + 1, len(self.bin_edges) - 1)]
        region = np.maximum.reduce([h[i_min:i_max + 1] for h in visible_hists]) if len(visible_hists) > 1 else visible_hists[0][i_min:i_max + 1]
        mx = float(np.max(region))
        y_max = math.log10(mx + 1) if self.log_mode else mx * 1.05
        return (x_min, x_max, 0.0, y_max)

    def fit_to_data(self):
        """Auto-adjust axis limits so data fits visually."""
        ext = self.get_fit_extent()
        if ext is None:
            return
        self.x_min, self.x_max, self.y_min, self.y_max = ext
        self.update()

    def _draw_channel_curve(self, painter, ch, hist_counts, plot_x0, plot_y1, plot_w, plot_h, x_range, y_range):
        """Draw a single channel curve (line or filled). ch: 'RGB', 'R', 'G', or 'B'."""
        color = self.CHANNEL_COLORS.get(ch, QColor(200, 200, 200))
        filled = (ch == 'RGB')
        n_bins = len(hist_counts)
        points = []
        for i in range(n_bins):
            bin_center = (self.bin_edges[i] + self.bin_edges[i + 1]) / 2 if i + 1 < len(self.bin_edges) else self.bin_edges[i]
            if bin_center < self.x_min or bin_center > self.x_max:
                continue
            val = hist_counts[i]
            y_val = math.log10(val + 1) if self.log_mode else val
            y_norm = (y_val - self.y_min) / y_range
            y_norm = max(0.0, min(1.0, y_norm))
            x_pos = plot_x0 + (bin_center - self.x_min) / x_range * plot_w
            y_pos = plot_y1 - y_norm * plot_h
            points.append((x_pos, y_pos))
        if not points:
            return
        path = QPainterPath()
        path.moveTo(points[0][0], plot_y1)
        path.lineTo(points[0][0], points[0][1])
        for x_pos, y_pos in points[1:]:
            path.lineTo(x_pos, y_pos)
        path.lineTo(points[-1][0], plot_y1)
        path.closeSubpath()
        if filled:
            fill_color = QColor(color)
            fill_color.setAlpha(60)
            painter.setBrush(fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_width = 2 if ch == 'RGB' else 1.5
        painter.setPen(QPen(color, pen_width))
        line_path = QPainterPath()
        line_path.moveTo(points[0][0], points[0][1])
        for x_pos, y_pos in points[1:]:
            line_path.lineTo(x_pos, y_pos)
        painter.drawPath(line_path)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()

        margin_left = 70
        margin_bottom = 72  # room for ticks, tick labels, and axis title
        margin_right = 55   # enough for rightmost x-axis tick label (70px wide, centered)
        margin_top = 10
        plot_x0 = margin_left
        plot_y0 = margin_top
        plot_x1 = w - margin_right
        plot_y1 = h - margin_bottom
        plot_w = plot_x1 - plot_x0
        plot_h = plot_y1 - plot_y0

        painter.fillRect(0, 0, w, h, QColor(25, 25, 25))

        if not self.histograms or not any(self.histograms[k].size > 0 for k in self.histograms):
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(plot_x0, h // 2, "No histogram data")
            return

        n_bins = len(self.bin_edges) - 1
        x_range = self.x_max - self.x_min
        if x_range <= 0:
            x_range = 1e-6
        y_range = self.y_max - self.y_min
        if y_range <= 0:
            y_range = 1e-6

        # Draw Y axis (vertical line)
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(plot_x0, plot_y0, plot_x0, plot_y1)

        # Draw X axis (horizontal line)
        painter.drawLine(plot_x0, plot_y1, plot_x1, plot_y1)

        # Y-axis ticks and labels
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        for i in range(5):
            frac = i / 4.0
            val = self.y_min + frac * y_range
            y_px = plot_y1 - frac * plot_h
            painter.setPen(QPen(QColor(140, 140, 140), 1))
            painter.drawLine(plot_x0 - 5, int(y_px), plot_x0, int(y_px))
            if self.log_mode:
                label = f"{val:.2f}"
            else:
                label = f"{int(val)}" if val >= 100 else f"{val:.2f}"
            painter.setPen(QColor(180, 180, 180))
            rect = QRectF(0, int(y_px) - 7, margin_left - 8, 14)
            painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        # X-axis ticks and labels
        x_tick_y = plot_y1 + 6
        for i in range(5):
            frac = i / 4.0
            val = self.x_min + frac * x_range
            x_px = plot_x0 + frac * plot_w
            painter.setPen(QPen(QColor(140, 140, 140), 1))
            painter.drawLine(int(x_px), plot_y1, int(x_px), plot_y1 + 5)
            label = str(int(val * self.adu_max))
            painter.setPen(QColor(180, 180, 180))
            rect = QRectF(int(x_px) - 35, x_tick_y, 70, 14)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        # Axis labels (below tick labels to avoid overlap)
        painter.setPen(QColor(200, 200, 200))
        axis_title = f"Pixel Value (ADU 0–{self.adu_max})"
        x_title_y = plot_y1 + 28
        rect = QRectF(plot_x0, x_title_y, plot_w, 14)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, axis_title)
        painter.save()
        # Use x=50 so rotated label rect (-50..50) stays within widget (avoids left-edge clipping)
        painter.translate(50, plot_y0 + plot_h // 2)
        painter.rotate(-90)
        rect = QRectF(-50, 0, 100, 14)
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            "Pixel Count" if not self.log_mode else "log(Pixel Count)",
        )
        painter.restore()

        # Grid (behind curves)
        painter.setPen(QPen(QColor(50, 50, 50), 1, Qt.PenStyle.DotLine))
        for i in range(1, 4):
            v_x = plot_x0 + int(i * 0.25 * plot_w)
            painter.drawLine(v_x, plot_y0, v_x, plot_y1)
            v_y = plot_y1 - int(i * 0.25 * plot_h)
            painter.drawLine(plot_x0, v_y, plot_x1, v_y)

        # Draw channel curves (order: RGB fill first, then R, G, B lines, then RGB outline)
        draw_order = ['RGB', 'R', 'G', 'B', 'L']
        for ch in draw_order:
            if not self.visible.get(ch, False) or ch not in self.histograms or self.histograms[ch].size == 0:
                continue
            self._draw_channel_curve(
                painter, ch, self.histograms[ch],
                plot_x0, plot_y1, plot_w, plot_h, x_range, y_range
            )

        # Draw vertical line at clicked value if set
        if self._clicked_intensity is not None and self.x_min <= self._clicked_intensity <= self.x_max:
            x_pos = plot_x0 + (self._clicked_intensity - self.x_min) / x_range * plot_w
            painter.setPen(QPen(QColor(255, 200, 50), 2, Qt.PenStyle.DashLine))
            painter.drawLine(int(x_pos), plot_y0, int(x_pos), plot_y1)
            # Show Pixel Value (ADU) and Pixel Count at top of marker line
            pixel_value_adu = int(round(self._clicked_intensity * self.adu_max))
            count = 0
            if self.bin_edges is not None and len(self.bin_edges) >= 2 and "RGB" in self.histograms:
                n_bins = len(self.bin_edges) - 1
                bin_idx = int(np.searchsorted(self.bin_edges, self._clicked_intensity, side="right")) - 1
                bin_idx = max(0, min(n_bins - 1, bin_idx))
                count = int(self.histograms["RGB"][bin_idx])
            label = f"Value: {pixel_value_adu}   Count: {count}"
            painter.setPen(QColor(255, 200, 50))
            painter.setFont(QFont("", 9))
            painter.drawText(int(x_pos) + 4, plot_y0 + 12, label)


# ------------------------------------------------------------------------------
# ENLARGE DIAGRAM DIALOGS (Histogram and 3D)
# ------------------------------------------------------------------------------

class HistogramEnlargeDialog(QDialog):
    """Modal dialog showing the current histogram enlarged with the same data and settings."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        histograms: dict,
        bin_edges: np.ndarray,
        visibility: dict,
        log_mode: bool,
        adu_max: int,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(720, 480)
        layout = QVBoxLayout(self)
        hist = HistogramWidget(self)
        hist.setMinimumSize(680, 400)
        hist.set_histograms(histograms, bin_edges)
        hist.set_visibility(**visibility)
        hist.set_log_mode(log_mode)
        hist.set_x_axis_mode("adu", adu_max)
        layout.addWidget(hist, 1)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


# ------------------------------------------------------------------------------
# 3D SURFACE PROFILE DIALOG
# ------------------------------------------------------------------------------

def _subsample_for_surface(img_2d: np.ndarray, max_side: int = SURFACE_PLOT_MAX_SIDE) -> np.ndarray:
    """Subsample 2D image to at most max_side x max_side for the 3D surface plot."""
    h, w = img_2d.shape[0], img_2d.shape[1]
    if h <= max_side and w <= max_side:
        return img_2d
    stride_h = max(1, (h - 1) // max_side + 1)
    stride_w = max(1, (w - 1) // max_side + 1)
    return img_2d[::stride_h, ::stride_w]


class SurfacePlotWidget(QWidget):
    """
    Inline 3D surface plot (same content as SurfacePlotDialog).
    Use set_image(img_2d) to set or update the plot; set_image(None) for placeholder.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(340, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel("No image")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 10pt;")
        self._layout.addWidget(self._placeholder)
        self._canvas = None
        self._ax = None
        self._z_plot = None
        self._orig_w = self._orig_h = None
        self._nx = self._ny = None
        self._click_line = None
        self._click_marker = None
        self._click_text = None
        self._mpl_available = False
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            from matplotlib import cm
            self._FigureCanvasQTAgg = FigureCanvasQTAgg
            self._Figure = Figure
            self._cm = cm
            self._mpl_available = True
        except ImportError:
            self._placeholder.setText("matplotlib required")
            self._FigureCanvasQTAgg = None
            self._Figure = None
            self._cm = None

    def set_image(
        self,
        img_2d: np.ndarray | None,
        log_mode: bool = False,
        adu_max: int = 65535,
        channel: str = "RGB",
    ) -> None:
        if not self._mpl_available:
            return
        # Remove previous canvas if any
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
            self._canvas = None
        self._placeholder.setVisible(img_2d is None)
        if img_2d is None:
            self._ax = None
            self._z_plot = None
            self._orig_w = self._orig_h = self._nx = self._ny = None
            self._click_line = self._click_marker = self._click_text = None
            return
        orig_h, orig_w = img_2d.shape[0], img_2d.shape[1]
        z_norm = _subsample_for_surface(img_2d.astype(np.float64))
        # Z-axis in ADU (input is 0-1 normalized). In log mode, plot log10(Z) so surface height is logarithmic.
        z_adu = z_norm * float(adu_max)
        if log_mode:
            z_plot = np.log10(np.maximum(z_adu, 1e-10))
        else:
            z_plot = z_adu
        ny, nx = z_plot.shape
        # X/Y in real pixel coordinates (0 to orig_w-1, 0 to orig_h-1)
        x_vals = np.linspace(0, orig_w - 1, nx, dtype=np.float64)
        y_vals = np.linspace(0, orig_h - 1, ny, dtype=np.float64)
        X, Y = np.meshgrid(x_vals, y_vals)
        fig = self._Figure(figsize=(4, 3.5), facecolor="#191919")
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#191919")
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor("#555")
        ax.yaxis.pane.set_edgecolor("#555")
        ax.zaxis.pane.set_edgecolor("#555")
        ax.tick_params(colors="#ccc")
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.zaxis.label.set_color("#fff")
        ch = channel.upper() if channel else "RGB"
        if ch not in ("RGB", "R", "G", "B", "L"):
            ch = "RGB"
        z_label = f"log({ch}) (ADU)" if log_mode else f"{ch} (ADU)"
        ax.set_xlabel("X (px)")
        ax.set_ylabel("Y (px)")
        ax.set_zlabel(z_label)
        surf = ax.plot_surface(X, Y, z_plot, cmap=self._cm.viridis, edgecolor="none", antialiased=True, zorder=0)
        # Cuboid aspect: X/Y preserve image ratio; scale so X,Y,Z share a common "large" scale (good cube/quader)
        x_range = float(orig_w)
        y_range = float(orig_h)
        z_range = max(float(z_plot.max() - z_plot.min()), 1e-6)
        z_scale = max(x_range, y_range) * 0.35 / max(z_range, 1e-6)  # Z visible vs X/Y
        z_display = z_range * z_scale
        max_dim = max(x_range, y_range, z_display)
        sx = x_range / max_dim
        sy = y_range / max_dim
        sz = z_display / max_dim
        try:
            ax.set_box_aspect((sx, sy, sz))
        except AttributeError:
            pass  # matplotlib < 3.3.5
        if log_mode:
            from matplotlib.ticker import FuncFormatter
            def log_tick_fmt(x, pos):
                val = 10 ** x
                if val >= 10000:
                    return f"{int(val):,}"
                if val >= 1:
                    return str(int(round(val)))
                return f"{val:.2g}"
            ax.zaxis.set_major_formatter(FuncFormatter(log_tick_fmt))
        self._canvas = self._FigureCanvasQTAgg(fig)
        self._layout.insertWidget(0, self._canvas, 1)
        self._canvas.show()
        # Store for click indicator (vertical line on 3D surface)
        self._ax = ax
        self._z_plot = z_plot
        self._orig_w, self._orig_h = orig_w, orig_h
        self._nx, self._ny = nx, ny
        self._click_line = None
        self._click_marker = None
        self._click_text = None

    def set_clicked_pixel(self, px: int | None, py: int | None) -> None:
        """Show a vertical line on the 3D surface at the clicked pixel (from image click). None to clear."""
        if self._ax is None or self._z_plot is None:
            return
        # Remove previous indicator
        if self._click_line is not None:
            self._click_line.remove()
            self._click_line = None
        if self._click_marker is not None:
            self._click_marker.remove()
            self._click_marker = None
        if self._click_text is not None:
            self._click_text.remove()
            self._click_text = None
        if px is None or py is None:
            if self._canvas is not None:
                self._canvas.draw_idle()
            return
        # Map pixel to subsampled grid
        nx, ny = self._nx, self._ny
        orig_w, orig_h = self._orig_w, self._orig_h
        ix = int(round(px * (nx - 1) / max(1, orig_w - 1)))
        iy = int(round(py * (ny - 1) / max(1, orig_h - 1)))
        ix = max(0, min(nx - 1, ix))
        iy = max(0, min(ny - 1, iy))
        z_val = float(self._z_plot[iy, ix])
        z_min = float(self._z_plot.min())
        z_max = float(self._z_plot.max())
        # Vertical line from base to Z max so the pixel position is easy to see.
        # Use high zorder so the line and marker draw on top of the surface (no occlusion).
        # Same style as histogram: yellow/amber dashed line (QColor(255, 200, 50), 2, DashLine)
        self._click_line = self._ax.plot(
            [px, px], [py, py], [z_min, z_max],
            color="#ffc832", linewidth=2, linestyle="--", alpha=0.95, zorder=1e5
        )[0]
        # Marker dot at actual surface height (Z value) at this pixel
        self._click_marker = self._ax.scatter(
            [px], [py], [z_val], color="#ffc832", s=60, edgecolors="none", alpha=0.95, zorder=1e5
        )
        # Text label showing the Z value at the dot
        z_str = f"{z_val:.1f}" if abs(z_val) < 1e4 else f"{int(z_val)}"
        self._click_text = self._ax.text(px, py, z_val, f"  {z_str}", color="#ffc832", fontsize=8, zorder=1e5)
        if self._canvas is not None:
            self._canvas.draw_idle()


class SurfacePlotDialog(QDialog):
    """
    Modal dialog showing the image as a 3D surface plot (height = channel value).
    X/Y = pixel position, Z = selected channel (R, G, B, or L). Useful to judge background flatness and gradients.
    """

    def __init__(
        self,
        parent: QWidget | None,
        img: np.ndarray,
        title: str = "3D Profile",
        log_mode: bool = False,
        adu_max: int = 65535,
        channel: str = "RGB",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 520)
        layout = QVBoxLayout(self)
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            from matplotlib import cm
        except ImportError:
            lbl = QLabel("matplotlib is required for the 3D surface plot. Please install it.")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            btn = QPushButton("Close")
            _nofocus(btn)
            btn.clicked.connect(self.accept)
            layout.addWidget(btn)
            return
        img_2d = _image_to_channel_2d(img, channel)
        orig_h, orig_w = img_2d.shape[0], img_2d.shape[1]
        z_norm = _subsample_for_surface(img_2d.astype(np.float64))
        z_adu = z_norm * float(adu_max)
        if log_mode:
            z_plot = np.log10(np.maximum(z_adu, 1e-10))
        else:
            z_plot = z_adu
        ny, nx = z_plot.shape
        x_vals = np.linspace(0, orig_w - 1, nx, dtype=np.float64)
        y_vals = np.linspace(0, orig_h - 1, ny, dtype=np.float64)
        X, Y = np.meshgrid(x_vals, y_vals)
        fig = Figure(figsize=(6, 5), facecolor="#191919")
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#191919")
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor("#555")
        ax.yaxis.pane.set_edgecolor("#555")
        ax.zaxis.pane.set_edgecolor("#555")
        ax.tick_params(colors="#ccc")
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.zaxis.label.set_color("#fff")
        ch = channel.upper() if channel else "RGB"
        if ch not in ("RGB", "R", "G", "B", "L"):
            ch = "RGB"
        z_label = f"log({ch}) (ADU)" if log_mode else f"{ch} (ADU)"
        ax.set_xlabel("X (px)")
        ax.set_ylabel("Y (px)")
        ax.set_zlabel(z_label)
        surf = ax.plot_surface(X, Y, z_plot, cmap=cm.viridis, edgecolor="none", antialiased=True)
        # Cuboid aspect: X/Y preserve image ratio; scale so X,Y,Z share a common "large" scale (good cube/quader)
        x_range = float(orig_w)
        y_range = float(orig_h)
        z_range = max(float(z_plot.max() - z_plot.min()), 1e-6)
        z_scale = max(x_range, y_range) * 0.35 / max(z_range, 1e-6)  # Z visible vs X/Y
        z_display = z_range * z_scale
        max_dim = max(x_range, y_range, z_display)
        sx = x_range / max_dim
        sy = y_range / max_dim
        sz = z_display / max_dim
        try:
            ax.set_box_aspect((sx, sy, sz))
        except AttributeError:
            pass  # matplotlib < 3.3.5
        if log_mode:
            from matplotlib.ticker import FuncFormatter
            def log_tick_fmt(x, pos):
                val = 10 ** x
                if val >= 10000:
                    return f"{int(val):,}"
                if val >= 1:
                    return str(int(round(val)))
                return f"{val:.2g}"
            ax.zaxis.set_major_formatter(FuncFormatter(log_tick_fmt))
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class HistogramViewerWindow(QMainWindow):
    """
    Main window for the Histogram Viewer.

    Displays linear and auto-stretched images with histograms, supports
    loading FITS from Siril or file, and up to 3 comparison stretched FITS.
    """

    NUM_EXTRA_STRETCHED = 3

    def _all_histogram_widgets(self) -> list[HistogramWidget]:
        """Return list of all histogram widgets (linear, stretched, extra)."""
        return [self.hist_widget_linear, self.hist_widget_stretched] + self.hist_widget_extra

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self.img_linear = None
        self.img_stretched = None
        self.img_stretched_extra = [None, None, None]  # 3 slots for already-stretched FITS
        self.stretched_filenames = [None, None, None]  # filename per slot for display
        self.adu_max = 65535
        self.x_axis_mode = 'adu'
        self._last_click_info = {}  # column_type -> {"x", "y", "r", "g", "b", "intensity"}
        self.init_ui()
        try:
            self.load_image()
        except (NoImageError, OSError, ConnectionError, RuntimeError, SirilError, SirilConnectionError):
            self.img_linear = None
            self.img_stretched = None

    def _build_left_panel(self) -> QWidget:
        """Build the left control panel with histogram, axis, and image controls."""
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)
        l_layout = QVBoxLayout(left)
        l_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Histogram Viewer")
        lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_layout.addWidget(lbl)
        self._build_view_type_group(l_layout)
        self._build_yaxis_group(l_layout)
        self._build_histogram_group(l_layout)
        self._build_3d_channel_group(l_layout)
        self._build_image_group(l_layout)
        self._build_stretched_comparisons_group(l_layout)
        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.setObjectName("CloseButton")
        btn_close.clicked.connect(self.close)
        l_layout.addStretch()
        l_layout.addWidget(btn_close)
        return left

    def _build_histogram_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the Histogram Channels group (channels, X-axis, ADU, axis limits, Fit button)."""
        g_hist = QGroupBox("Histogram Channels")
        gh_layout = QVBoxLayout(g_hist)
        chan_layout = QHBoxLayout()
        self.chk_rgb = QCheckBox("RGB")
        _nofocus(self.chk_rgb)
        self.chk_rgb.setChecked(True)
        self.chk_rgb.toggled.connect(self.on_channel_toggled)
        self.chk_r = QCheckBox("R")
        _nofocus(self.chk_r)
        self.chk_r.setChecked(True)
        self.chk_r.toggled.connect(self.on_channel_toggled)
        self.chk_g = QCheckBox("G")
        _nofocus(self.chk_g)
        self.chk_g.setChecked(True)
        self.chk_g.toggled.connect(self.on_channel_toggled)
        self.chk_b = QCheckBox("B")
        _nofocus(self.chk_b)
        self.chk_b.setChecked(True)
        self.chk_b.toggled.connect(self.on_channel_toggled)
        self.chk_l = QCheckBox("L")
        _nofocus(self.chk_l)
        self.chk_l.setChecked(True)  # luminance channel on after start
        self.chk_l.toggled.connect(self.on_channel_toggled)
        chan_layout.addWidget(self.chk_rgb)
        chan_layout.addWidget(self.chk_r)
        chan_layout.addWidget(self.chk_g)
        chan_layout.addWidget(self.chk_b)
        chan_layout.addWidget(self.chk_l)
        chan_layout.addStretch()
        gh_layout.addLayout(chan_layout)
        # X-axis is fixed to ADU for all histograms, so no toggle is needed here.
        parent_layout.addWidget(g_hist)

    def _build_yaxis_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the Data-Mode group (Normal/Logarithmic) only."""
        g_yaxis = QGroupBox("Data-Mode")
        gy_layout = QHBoxLayout(g_yaxis)
        self.radio_normal = QRadioButton("Normal")
        _nofocus(self.radio_normal)
        self.radio_log = QRadioButton("Logarithmic")
        _nofocus(self.radio_log)
        self.radio_normal.setChecked(True)
        self.radio_normal.toggled.connect(lambda c: self.on_mode_changed(not c))
        self.radio_log.toggled.connect(lambda c: self.on_mode_changed(c))
        gy_layout.addWidget(self.radio_normal)
        gy_layout.addWidget(self.radio_log)
        gy_layout.addStretch()
        parent_layout.addWidget(g_yaxis)

    def _build_view_type_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the view type group (Histogram / 3D Surface Plot), independent of Y-axis."""
        g_view = QGroupBox("View")
        gv_layout = QHBoxLayout(g_view)
        self.radio_histogram = QRadioButton("Histogram")
        _nofocus(self.radio_histogram)
        self.radio_3d_surface = QRadioButton("3D Surface Plot")
        _nofocus(self.radio_3d_surface)
        self.radio_histogram.setChecked(True)
        self.radio_histogram.toggled.connect(lambda c: self.on_view_type_changed(not c))
        self.radio_3d_surface.toggled.connect(lambda c: self.on_view_type_changed(c))
        gv_layout.addWidget(self.radio_histogram)
        gv_layout.addWidget(self.radio_3d_surface)
        gv_layout.addStretch()
        parent_layout.addWidget(g_view)

    def _build_3d_channel_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the 3D Plot Channels group (RGB, R, G, B, L). RGB selected by default."""
        g_3d = QGroupBox("3D Plot Channels")
        g3_layout = QHBoxLayout(g_3d)
        self.btngrp_3d_channel = QButtonGroup(self)
        self.radio_3d_rgb = QRadioButton("RGB")
        _nofocus(self.radio_3d_rgb)
        self.radio_3d_r = QRadioButton("R")
        _nofocus(self.radio_3d_r)
        self.radio_3d_g = QRadioButton("G")
        _nofocus(self.radio_3d_g)
        self.radio_3d_b = QRadioButton("B")
        _nofocus(self.radio_3d_b)
        self.radio_3d_l = QRadioButton("L")
        _nofocus(self.radio_3d_l)
        self.radio_3d_rgb.setChecked(True)
        for rb in (self.radio_3d_rgb, self.radio_3d_r, self.radio_3d_g, self.radio_3d_b, self.radio_3d_l):
            self.btngrp_3d_channel.addButton(rb)
        self.radio_3d_rgb.toggled.connect(lambda c: c and self._compute_histogram())
        self.radio_3d_r.toggled.connect(lambda c: c and self._compute_histogram())
        self.radio_3d_g.toggled.connect(lambda c: c and self._compute_histogram())
        self.radio_3d_b.toggled.connect(lambda c: c and self._compute_histogram())
        self.radio_3d_l.toggled.connect(lambda c: c and self._compute_histogram())
        g3_layout.addWidget(self.radio_3d_rgb)
        g3_layout.addWidget(self.radio_3d_r)
        g3_layout.addWidget(self.radio_3d_g)
        g3_layout.addWidget(self.radio_3d_b)
        g3_layout.addWidget(self.radio_3d_l)
        g3_layout.addStretch()
        parent_layout.addWidget(g_3d)

    def _get_3d_channel(self) -> str:
        """Return the selected 3D plot channel: 'RGB', 'R', 'G', 'B', or 'L'."""
        if self.radio_3d_rgb.isChecked():
            return "RGB"
        if self.radio_3d_r.isChecked():
            return "R"
        if self.radio_3d_g.isChecked():
            return "G"
        if self.radio_3d_b.isChecked():
            return "B"
        return "L"

    def _build_image_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the Image group (Refresh from Siril, Load linear FITS)."""
        g_img = QGroupBox("Image")
        gi_layout = QVBoxLayout(g_img)
        btn_refresh = QPushButton("Refresh from Siril")
        _nofocus(btn_refresh)
        btn_refresh.setToolTip("Reload the current image from Siril")
        btn_refresh.clicked.connect(self.load_image)
        gi_layout.addWidget(btn_refresh)
        btn_load_linear = QPushButton("Load linear FITS...")
        _nofocus(btn_load_linear)
        btn_load_linear.setToolTip("Load a linear FITS file as the primary image")
        btn_load_linear.clicked.connect(self._on_load_linear_fits_clicked)
        gi_layout.addWidget(btn_load_linear)
        parent_layout.addWidget(g_img)

    def _build_stretched_comparisons_group(self, parent_layout: QVBoxLayout) -> None:
        """Build the Stretched comparisons group (Load/Clear for slots 1-3)."""
        g_extra = QGroupBox("Stretched comparisons")
        ge_layout = QVBoxLayout(g_extra)
        self.btn_load_stretched = []
        self.btn_clear_stretched = []
        for i in range(self.NUM_EXTRA_STRETCHED):
            row = QHBoxLayout()
            btn_load = QPushButton(f"Load stretched FITS {i + 1}")
            _nofocus(btn_load)
            btn_load.setToolTip(f"Load an already-stretched FITS for comparison slot {i + 1}")
            btn_load.clicked.connect(lambda checked=False, idx=i: self._on_load_stretched_fits_clicked(idx))
            btn_clear = QPushButton("Clear")
            _nofocus(btn_clear)
            btn_clear.setToolTip(f"Clear slot {i + 1}")
            btn_clear.clicked.connect(lambda checked=False, idx=i: self.clear_stretched_slot(idx))
            row.addWidget(btn_load)
            row.addWidget(btn_clear)
            ge_layout.addLayout(row)
            self.btn_load_stretched.append(btn_load)
            self.btn_clear_stretched.append(btn_clear)
        parent_layout.addWidget(g_extra)

    def _build_right_panel(self) -> QWidget:
        """Build the right panel with image columns (Linear, Auto-Stretched, Stretched 1-3)."""
        right = QWidget()
        r_layout = QHBoxLayout(right)
        r_layout.setContentsMargins(0, 0, 0, 0)

        def make_column(title, zoom_in_cb, zoom_out_cb, fit_cb, zoom_11_cb, explain_cb, enlarge_diagram_cb):
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(5, 5, 5, 5)
            lbl = QLabel(title)
            lbl.setStyleSheet("font-weight: bold; color: #88aaff; font-size: 11pt;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_layout.addWidget(lbl)
            tb = QHBoxLayout()
            b_zm = QPushButton("-")
            _nofocus(b_zm)
            b_zm.setObjectName("ZoomBtn")
            b_zm.setToolTip("Zoom Out")
            b_zm.clicked.connect(zoom_out_cb)
            b_fit = QPushButton("Fit")
            _nofocus(b_fit)
            b_fit.setObjectName("ZoomBtn")
            b_fit.setToolTip("Fit image to view")
            b_fit.clicked.connect(fit_cb)
            b_11 = QPushButton("1:1")
            _nofocus(b_11)
            b_11.setObjectName("ZoomBtn")
            b_11.setToolTip("View at 100%")
            b_11.clicked.connect(zoom_11_cb)
            b_zp = QPushButton("+")
            _nofocus(b_zp)
            b_zp.setObjectName("ZoomBtn")
            b_zp.setToolTip("Zoom In")
            b_zp.clicked.connect(zoom_in_cb)
            tb.addWidget(b_zm)
            tb.addWidget(b_fit)
            tb.addWidget(b_11)
            tb.addWidget(b_zp)
            tb.addStretch()
            col_layout.addLayout(tb)
            scene = QGraphicsScene()
            view = QGraphicsView(scene)
            view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            view.setDragMode(QGraphicsView.DragMode.NoDrag)
            view.setCursor(Qt.CursorShape.CrossCursor)
            view.setMinimumSize(VIEW_MIN_WIDTH, VIEW_MIN_HEIGHT)
            pix_item = QGraphicsPixmapItem()
            scene.addItem(pix_item)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            col_layout.addWidget(view, 1)
            hist_widget = HistogramWidget()
            surface_plot_widget = SurfacePlotWidget()
            stacked_widget = QStackedWidget()
            stacked_widget.addWidget(hist_widget)       # index 0 = Histogram
            stacked_widget.addWidget(surface_plot_widget)  # index 1 = 3D Surface Plot
            col_layout.addWidget(stacked_widget, 1)
            # Stats section with Explain and Enlarge Diagram buttons
            stats_section = QWidget()
            stats_layout = QVBoxLayout(stats_section)
            stats_layout.setContentsMargins(0, 0, 0, 0)
            stats_row = QHBoxLayout()
            stats_label = QLabel("")
            stats_label.setStyleSheet("font-size: 11pt; color: #aaa; font-family: 'Courier New', Courier;")
            stats_label.setWordWrap(True)
            stats_label.setMinimumHeight(STATS_LABEL_MIN_HEIGHT)
            stats_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            stats_row.addWidget(stats_label, 1)
            btn_explain = QPushButton("Explain")
            _nofocus(btn_explain)
            btn_explain.setToolTip("Show how data was stretched from linear to this image")
            btn_explain.clicked.connect(explain_cb)
            stats_row.addWidget(btn_explain)
            btn_enlarge = QPushButton("Enlarge Diagram")
            _nofocus(btn_enlarge)
            btn_enlarge.setToolTip("Open the current diagram (histogram or 3D plot) in a larger modal window.")
            btn_enlarge.clicked.connect(enlarge_diagram_cb)
            stats_row.addWidget(btn_enlarge)
            stats_layout.addLayout(stats_row)
            col_layout.addWidget(stats_section)
            col.setMinimumWidth(COL_MIN_WIDTH)
            col.setMinimumHeight(COL_MIN_HEIGHT)
            col.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            return col, view, pix_item, hist_widget, surface_plot_widget, stacked_widget, stats_label, lbl

        self.col_linear, self.view_linear, self.pix_item_linear, self.hist_widget_linear, self.surface_widget_linear, self.stacked_widget_linear, self.stats_label_linear, _ = make_column(
            "Linear",
            self.zoom_in_linear,
            self.zoom_out_linear,
            self.fit_view_linear,
            self.zoom_11_linear,
            self._show_linear_explain,
            self._show_enlarge_diagram_linear,
        )
        self.col_stretched, self.view_stretched, self.pix_item_stretched, self.hist_widget_stretched, self.surface_widget_stretched, self.stacked_widget_stretched, self.stats_label_stretched, _ = make_column(
            "Auto-Stretched",
            self.zoom_in_stretched,
            self.zoom_out_stretched,
            self.fit_view_stretched,
            self.zoom_11_stretched,
            self._show_auto_stretched_explain,
            self._show_enlarge_diagram_stretched,
        )

        # Extra columns: Stretched 1, 2, 3 (already-stretched FITS)
        self.col_extra = []
        self.view_extra = []
        self.pix_item_extra = []
        self.hist_widget_extra = []
        self.surface_widget_extra = []
        self.stacked_widget_extra = []
        self.stats_label_extra = []
        self.col_title_extra = []
        for i in range(self.NUM_EXTRA_STRETCHED):
            col, view, pix_item, hist_widget, surface_plot_widget, stacked_widget, stats_label, title_label = make_column(
                f"Stretched {i + 1}",
                lambda checked=False, idx=i: self._zoom_in_extra(idx),
                lambda checked=False, idx=i: self._zoom_out_extra(idx),
                lambda checked=False, idx=i: self._fit_view_extra(idx),
                lambda checked=False, idx=i: self._zoom_11_extra(idx),
                lambda checked=False, idx=i: self._show_stretched_fits_explain(idx),
                lambda checked=False, idx=i: self._show_enlarge_diagram_extra(idx),
            )
            self.col_extra.append(col)
            self.view_extra.append(view)
            self.pix_item_extra.append(pix_item)
            self.hist_widget_extra.append(hist_widget)
            self.surface_widget_extra.append(surface_plot_widget)
            self.stacked_widget_extra.append(stacked_widget)
            self.stats_label_extra.append(stats_label)
            self.col_title_extra.append(title_label)
            col.setVisible(False)

        # Install mouse click handlers to show pixel value in histogram
        # Map viewport -> (column_type, view) so eventFilter can identify and use mapToScene
        self._view_column_map = {
            self.view_linear.viewport(): ("linear", self.view_linear),
            self.view_stretched.viewport(): ("stretched", self.view_stretched),
        }
        for i, v in enumerate(self.view_extra):
            self._view_column_map[v.viewport()] = (f"stretched_{i + 1}", v)
        for vp in self._view_column_map:
            vp.installEventFilter(self)

        r_layout.addWidget(self.col_linear, 1)
        r_layout.addWidget(self.col_stretched, 1)
        for col in self.col_extra:
            r_layout.addWidget(col, 1)
        return right

    def init_ui(self) -> None:
        """Build and layout the main UI."""
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.addWidget(self._build_left_panel())
        layout.addWidget(self._build_right_panel(), 1)
        self.setWindowTitle("Siril Histogram Viewer")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1200, 700)

    def _zoom(self, view: QGraphicsView, factor: float) -> None:
        """Scale a graphics view by the given factor."""
        view.scale(factor, factor)

    def _reset_zoom(self, view: QGraphicsView) -> None:
        """Reset a graphics view to 1:1."""
        view.resetTransform()

    def _fit_view(self, view: QGraphicsView, pix_item: QGraphicsPixmapItem) -> None:
        """Fit the given pixmap item into the view while preserving aspect ratio."""
        if pix_item.pixmap() and not pix_item.pixmap().isNull():
            view.fitInView(pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in_linear(self) -> None:
        self._zoom(self.view_linear, 1.2)

    def zoom_out_linear(self) -> None:
        self._zoom(self.view_linear, 1 / 1.2)

    def zoom_11_linear(self) -> None:
        self._reset_zoom(self.view_linear)

    def fit_view_linear(self) -> None:
        self._fit_view(self.view_linear, self.pix_item_linear)

    def zoom_in_stretched(self) -> None:
        self._zoom(self.view_stretched, 1.2)

    def zoom_out_stretched(self) -> None:
        self._zoom(self.view_stretched, 1 / 1.2)

    def zoom_11_stretched(self) -> None:
        self._reset_zoom(self.view_stretched)

    def fit_view_stretched(self) -> None:
        self._fit_view(self.view_stretched, self.pix_item_stretched)

    def _zoom_in_extra(self, i: int) -> None:
        self._zoom(self.view_extra[i], 1.2)

    def _zoom_out_extra(self, i: int) -> None:
        self._zoom(self.view_extra[i], 1 / 1.2)

    def _zoom_11_extra(self, i: int) -> None:
        self._reset_zoom(self.view_extra[i])

    def _fit_view_extra(self, i: int) -> None:
        self._fit_view(self.view_extra[i], self.pix_item_extra[i])

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle mouse clicks on image views to show pixel value in histogram."""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress and obj in self._view_column_map:
            column_type, view = self._view_column_map[obj]
            self._on_image_clicked(column_type, view, event)
            return False  # let the event propagate (e.g. for pan/zoom)
        return super().eventFilter(obj, event)

    def _on_image_clicked(self, column_type: str, view, event) -> None:
        """Show clicked pixel value in the histogram for this column."""
        # Resolve pix_item, source image, stats_label, hist_widget
        if column_type == "linear":
            pix_item = self.pix_item_linear
            img = self.img_linear
            stats_label, hist_widget = self.stats_label_linear, self.hist_widget_linear
        elif column_type == "stretched":
            view, pix_item = self.view_stretched, self.pix_item_stretched
            img = self.img_stretched
            stats_label, hist_widget = self.stats_label_stretched, self.hist_widget_stretched
        elif column_type in ("stretched_1", "stretched_2", "stretched_3"):
            idx = int(column_type.split("_")[1]) - 1
            view, pix_item = self.view_extra[idx], self.pix_item_extra[idx]
            img = self.img_stretched_extra[idx]
            stats_label, hist_widget = self.stats_label_extra[idx], self.hist_widget_extra[idx]
        else:
            return
        if img is None or pix_item.pixmap() is None or pix_item.pixmap().isNull():
            return
        # Map click to scene then to pixmap item coords
        view_pos = event.position() if hasattr(event, "position") else event.pos()
        scene_pos = view.mapToScene(view_pos.toPoint() if hasattr(view_pos, "toPoint") else view_pos)
        item_pos = pix_item.mapFromScene(scene_pos)
        px, py = item_pos.x(), item_pos.y()
        w_d = pix_item.pixmap().width()
        h_d = pix_item.pixmap().height()
        orig_h, orig_w = img.shape[0], img.shape[1]
        # Map display coords to source (display may be downscaled; display uses flipud)
        orig_col = max(0, min(orig_w - 1, int(px * orig_w / w_d)))
        orig_row = max(0, min(orig_h - 1, orig_h - 1 - int(py * orig_h / h_d)))
        # Sample pixel (HWC)
        if img.ndim == 3 and img.shape[2] >= 3:
            r, g, b = float(img[orig_row, orig_col, 0]), float(img[orig_row, orig_col, 1]), float(img[orig_row, orig_col, 2])
            intensity = LUMINANCE_R * r + LUMINANCE_G * g + LUMINANCE_B * b
        else:
            intensity = float(img[orig_row, orig_col])
            r = g = b = intensity
        # Format for stats (append to existing or replace last-click line)
        scale = float(self.adu_max)
        r_s, g_s, b_s = f"{int(round(r * scale))}", f"{int(round(g * scale))}", f"{int(round(b * scale))}"
        i_s = f"{int(round(intensity * scale))}"
        click_line = f"\nClick (x={orig_col}, y={orig_row}): R={r_s} G={g_s} B={b_s}  I={i_s}"
        base = stats_label.text()
        if "\nClick (" in base:
            base = base.split("\nClick (")[0]
        stats_label.setText(base.rstrip() + click_line)
        hist_widget.set_clicked_value(intensity, orig_col, orig_row)
        for w in self._all_histogram_widgets():
            if w is not hist_widget:
                w.set_clicked_value(None)
        # Show clicked pixel on 3D surface (vertical line at that x,y)
        if column_type == "linear":
            surface_widget = self.surface_widget_linear
        elif column_type == "stretched":
            surface_widget = self.surface_widget_stretched
        elif column_type in ("stretched_1", "stretched_2", "stretched_3"):
            idx = int(column_type.split("_")[1]) - 1
            surface_widget = self.surface_widget_extra[idx]
        else:
            surface_widget = None
        all_surface = [self.surface_widget_linear, self.surface_widget_stretched] + self.surface_widget_extra
        for sw in all_surface:
            if sw is surface_widget:
                sw.set_clicked_pixel(orig_col, orig_row)
            else:
                sw.set_clicked_pixel(None, None)

    def _on_load_linear_fits_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load linear FITS",
            "",
            "FITS files (*.fit *.fits *.fts);;All files (*)",
        )
        if path:
            self.load_linear_fits(path)

    def _on_load_stretched_fits_clicked(self, slot):
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Load stretched FITS {slot + 1}",
            "",
            "FITS files (*.fit *.fits *.fts);;All files (*)",
        )
        if path:
            self.load_stretched_fits(slot, path)

    def load_linear_fits(self, path: str) -> None:
        try:
            pixeldata = load_fits_pixeldata(path)
            self.adu_max = _adu_max_from_data(pixeldata)
            img = normalize_input(pixeldata, self.adu_max)
            img = ensure_hwc(img)
            self.img_linear = img.copy()
            self.img_stretched = autostretch_percentile(img)
            self._update_image_display()
            self._compute_histogram()
            self.setWindowTitle("Siril Histogram Viewer - Loaded")
            QTimer.singleShot(100, self.fit_view_linear)
            QTimer.singleShot(100, self.fit_view_stretched)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load linear FITS: {e}\n\n{traceback.format_exc()}",
            )

    def load_stretched_fits(self, slot: int, path: str) -> None:
        if not 0 <= slot < self.NUM_EXTRA_STRETCHED:
            return
        try:
            pixeldata = load_fits_pixeldata(path)
            img = normalize_stretched_fits(pixeldata)
            self.img_stretched_extra[slot] = img
            filename = os.path.basename(path)
            self.stretched_filenames[slot] = filename
            btn_text = filename if len(filename) <= FILENAME_BUTTON_MAX_LEN else filename[: FILENAME_BUTTON_MAX_LEN - 3] + "..."
            self.btn_load_stretched[slot].setText(btn_text)
            self.btn_load_stretched[slot].setToolTip(path)
            self.col_title_extra[slot].setText(filename)
            self.col_title_extra[slot].setToolTip(path)
            self.col_extra[slot].setVisible(True)
            self._update_image_display()
            self._compute_histogram()
            self._update_stats()
            QTimer.singleShot(100, lambda: self._fit_view_extra(slot))
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load stretched FITS: {e}\n\n{traceback.format_exc()}",
            )

    def clear_stretched_slot(self, slot: int) -> None:
        if not 0 <= slot < self.NUM_EXTRA_STRETCHED:
            return
        self.img_stretched_extra[slot] = None
        self.stretched_filenames[slot] = None
        self.col_extra[slot].setVisible(False)
        self.btn_load_stretched[slot].setText(f"Load stretched FITS {slot + 1}")
        self.btn_load_stretched[slot].setToolTip(f"Load an already-stretched FITS for comparison slot {slot + 1}")
        self.col_title_extra[slot].setText(f"Stretched {slot + 1}")
        self.pix_item_extra[slot].setPixmap(QPixmap())
        empty_hist, empty_edges = _empty_histogram_data()
        self.hist_widget_extra[slot].set_histograms(empty_hist, empty_edges)
        self.stats_label_extra[slot].setText("")

    def on_mode_changed(self, log_mode: bool) -> None:
        for w in self._all_histogram_widgets():
            w.set_log_mode(log_mode)
        # Refresh inline 3D plots so Z-axis uses the new log/linear scale and selected channel
        ch = self._get_3d_channel()
        if self.img_linear is not None:
            self.surface_widget_linear.set_image(
                _image_to_channel_2d(self.img_linear, ch), log_mode=log_mode, adu_max=self.adu_max, channel=ch
            )
        if self.img_stretched is not None:
            self.surface_widget_stretched.set_image(
                _image_to_channel_2d(self.img_stretched, ch), log_mode=log_mode, adu_max=self.adu_max, channel=ch
            )
        for i in range(self.NUM_EXTRA_STRETCHED):
            if self.img_stretched_extra[i] is not None:
                self.surface_widget_extra[i].set_image(
                    _image_to_channel_2d(self.img_stretched_extra[i], ch),
                    log_mode=log_mode,
                    adu_max=self.adu_max,
                    channel=ch,
                )

    def on_view_type_changed(self, surface_plot: bool) -> None:
        """Called when Histogram vs 3D Surface Plot is toggled. True = 3D Surface Plot selected."""
        index = 1 if surface_plot else 0
        self.stacked_widget_linear.setCurrentIndex(index)
        self.stacked_widget_stretched.setCurrentIndex(index)
        for i in range(self.NUM_EXTRA_STRETCHED):
            self.stacked_widget_extra[i].setCurrentIndex(index)

    def on_x_axis_mode_changed(self, adu_mode: bool | None = None) -> None:
        """Legacy hook for X-axis mode changes. Histograms now always use ADU."""
        self.x_axis_mode = "adu"
        for w in self._all_histogram_widgets():
            w.set_x_axis_mode(self.x_axis_mode, self.adu_max)
        self._update_stats()

    def on_channel_toggled(self):
        vis = {"rgb": self.chk_rgb.isChecked(), "r": self.chk_r.isChecked(), "g": self.chk_g.isChecked(), "b": self.chk_b.isChecked(), "l": self.chk_l.isChecked()}
        for w in self._all_histogram_widgets():
            w.set_visibility(**vis)

    def _compute_histogram_from(self, arr: np.ndarray) -> tuple[dict[str, np.ndarray], np.ndarray]:
        # For very large images, subsample for histogram computation to keep UI responsive.
        arr_s = _subsample_for_stats(arr)
        bins = HISTOGRAM_BINS
        range_01 = (0, 1)
        if arr_s.ndim == 3 and arr_s.shape[2] >= 3:
            lum = (LUMINANCE_R * arr_s[:, :, 0] + LUMINANCE_G * arr_s[:, :, 1] + LUMINANCE_B * arr_s[:, :, 2]).astype(np.float32)
            h_rgb, edges = np.histogram(lum.ravel(), bins=bins, range=range_01)  # RGB = luminance (Rec.709, same as 3D plot)
            histograms = {'RGB': h_rgb}
            h_r, _ = np.histogram(arr_s[:, :, 0].ravel(), bins=bins, range=range_01)
            h_g, _ = np.histogram(arr_s[:, :, 1].ravel(), bins=bins, range=range_01)
            h_b, _ = np.histogram(arr_s[:, :, 2].ravel(), bins=bins, range=range_01)
            histograms['R'] = h_r
            histograms['G'] = h_g
            histograms['B'] = h_b
            h_l, _ = np.histogram(lum.ravel(), bins=bins, range=range_01)
            histograms['L'] = h_l
        else:
            h_rgb, edges = np.histogram(arr_s.ravel(), bins=bins, range=range_01)
            histograms = {'RGB': h_rgb, 'R': h_rgb.copy(), 'G': h_rgb.copy(), 'B': h_rgb.copy(), 'L': h_rgb.copy()}
        return histograms, edges

    def _format_stats(self, arr: np.ndarray, adu_mode: bool = False, adu_max: int = 65535) -> str:
        """
        Compute and format image statistics for display under each histogram.

        For large images a subsampled view is used internally so that percentile and
        mean/std computations remain fast; image size and pixel count still reflect the
        full-resolution array. When ``adu_mode`` is True values are scaled to ADU.
        """
        arr_s = _subsample_for_stats(arr)
        flat = arr_s.ravel()
        h, w = arr.shape[0], arr.shape[1]
        # Single-pass stats: percentile gets min, p2, p98, max; mean/std are separate
        pct = np.percentile(flat, [0, 2, 50, 98, 100])
        mn, p2, med, p98, mx = float(pct[0]), float(pct[1]), float(pct[2]), float(pct[3]), float(pct[4])
        mean_val = float(np.mean(flat))
        std_val = float(np.std(flat))
        # Percentage and count of pixels near black/white in normalized space
        n = flat.size
        if n > 0:
            eps = 1.0 / 255.0  # treat one 8-bit step as "near 0/1"
            blacks_count = int(np.count_nonzero(flat <= eps))
            whites_count = int(np.count_nonzero(flat >= 1.0 - eps))
            blacks_pct = 100.0 * blacks_count / n
            whites_pct = 100.0 * whites_count / n
        else:
            blacks_count = whites_count = 0
            blacks_pct = whites_pct = 0.0
        if adu_mode:
            scale = float(adu_max)
            mn, mx = int(round(mn * scale)), int(round(mx * scale))
            mean_val = int(round(mean_val * scale))
            med = int(round(med * scale))
            std_val = int(round(std_val * scale))
            p2, p98 = int(round(p2 * scale)), int(round(p98 * scale))
            lines = [
                f"Size: {w}×{h}  Pixels: {w*h:,}",
                f"Min: {mn}  Max: {mx}  (ADU)",
                f"Mean: {mean_val}  Median: {med}",
                f"Std: {std_val}  %2/98: {p2} / {p98}",
                f"Blacks: {blacks_pct:.2f}% ({blacks_count:,})  Whites: {whites_pct:.2f}% ({whites_count:,})",
            ]
        else:
            lines = [
                f"Size: {w}×{h}  Pixels: {w*h:,}",
                f"Min: {mn:.4f}  Max: {mx:.4f}",
                f"Mean: {mean_val:.4f}  Median: {med:.4f}",
                f"Std: {std_val:.4f}  %2/98: {p2:.3f} / {p98:.3f}",
                f"Blacks: {blacks_pct:.2f}% ({blacks_count:,})  Whites: {whites_pct:.2f}% ({whites_count:,})",
            ]
        return "\n".join(lines)

    def _update_stats(self):
        """Update statistical info under each histogram."""
        if self.img_linear is not None:
            self.stats_label_linear.setText(self._format_stats(self.img_linear, adu_mode=True, adu_max=self.adu_max))
        else:
            self.stats_label_linear.setText("")
        if self.img_stretched is not None:
            self.stats_label_stretched.setText(self._format_stats(self.img_stretched, adu_mode=True, adu_max=self.adu_max))
        else:
            self.stats_label_stretched.setText("")
        for i in range(self.NUM_EXTRA_STRETCHED):
            img = self.img_stretched_extra[i]
            if img is not None:
                try:
                    text = self._format_stats(img, adu_mode=True, adu_max=self.adu_max)
                    self.stats_label_extra[i].setText(text)
                except Exception:
                    self.stats_label_extra[i].setText("(stats unavailable)")
            else:
                self.stats_label_extra[i].setText("")

    def _show_linear_explain(self) -> None:
        self._show_explain_dialog("linear")

    def _show_auto_stretched_explain(self) -> None:
        self._show_explain_dialog("stretched")

    def _show_stretched_fits_explain(self, idx: int) -> None:
        self._show_explain_dialog(f"stretched_{idx + 1}")

    def _show_enlarge_diagram_linear(self) -> None:
        """Open modal with current diagram (histogram or 3D) for the linear column, enlarged."""
        if self.stacked_widget_linear.currentIndex() == 1:
            # 3D view
            if self.img_linear is None:
                QMessageBox.information(self, "Enlarge Diagram", "No image loaded.")
                return
            ch = self._get_3d_channel()
            dlg = SurfacePlotDialog(
                self, self.img_linear, "Enlarge — Linear",
                log_mode=self.radio_log.isChecked(), adu_max=self.adu_max, channel=ch,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()
        else:
            # Histogram view
            if self.img_linear is None:
                QMessageBox.information(self, "Enlarge Diagram", "No image loaded.")
                return
            histograms, edges = self._compute_histogram_from(self.img_linear.astype(np.float32))
            vis = {"rgb": self.chk_rgb.isChecked(), "r": self.chk_r.isChecked(), "g": self.chk_g.isChecked(), "b": self.chk_b.isChecked(), "l": self.chk_l.isChecked()}
            dlg = HistogramEnlargeDialog(
                self, "Enlarge — Linear", histograms, edges, vis,
                self.radio_log.isChecked(), self.adu_max,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()

    def _show_enlarge_diagram_stretched(self) -> None:
        """Open modal with current diagram (histogram or 3D) for the auto-stretched column, enlarged."""
        if self.stacked_widget_stretched.currentIndex() == 1:
            if self.img_stretched is None:
                QMessageBox.information(self, "Enlarge Diagram", "No image loaded.")
                return
            ch = self._get_3d_channel()
            dlg = SurfacePlotDialog(
                self, self.img_stretched, "Enlarge — Auto-Stretched",
                log_mode=self.radio_log.isChecked(), adu_max=self.adu_max, channel=ch,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()
        else:
            if self.img_stretched is None:
                QMessageBox.information(self, "Enlarge Diagram", "No image loaded.")
                return
            histograms, edges = self._compute_histogram_from(self.img_stretched.astype(np.float32))
            vis = {"rgb": self.chk_rgb.isChecked(), "r": self.chk_r.isChecked(), "g": self.chk_g.isChecked(), "b": self.chk_b.isChecked(), "l": self.chk_l.isChecked()}
            dlg = HistogramEnlargeDialog(
                self, "Enlarge — Auto-Stretched", histograms, edges, vis,
                self.radio_log.isChecked(), self.adu_max,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()

    def _show_enlarge_diagram_extra(self, idx: int) -> None:
        """Open modal with current diagram (histogram or 3D) for the given extra column, enlarged."""
        if not 0 <= idx < self.NUM_EXTRA_STRETCHED:
            return
        img = self.img_stretched_extra[idx]
        if img is None:
            QMessageBox.information(self, "Enlarge Diagram", "No image in this slot.")
            return
        stacked = self.stacked_widget_extra[idx]
        if stacked.currentIndex() == 1:
            ch = self._get_3d_channel()
            title = f"Enlarge — Stretched {idx + 1}"
            if self.stretched_filenames[idx]:
                title += f" — {self.stretched_filenames[idx]}"
            dlg = SurfacePlotDialog(
                self, img, title,
                log_mode=self.radio_log.isChecked(), adu_max=self.adu_max, channel=ch,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()
        else:
            histograms, edges = self._compute_histogram_from(img.astype(np.float32))
            vis = {"rgb": self.chk_rgb.isChecked(), "r": self.chk_r.isChecked(), "g": self.chk_g.isChecked(), "b": self.chk_b.isChecked(), "l": self.chk_l.isChecked()}
            title = f"Enlarge — Stretched {idx + 1}"
            if self.stretched_filenames[idx]:
                title += f" — {self.stretched_filenames[idx]}"
            dlg = HistogramEnlargeDialog(
                self, title, histograms, edges, vis,
                self.radio_log.isChecked(), self.adu_max,
            )
            dlg.setWindowState(Qt.WindowState.WindowMaximized)
            dlg.exec()

    def _show_explain_dialog(self, column_type: str) -> None:
        """Show a dialog explaining how data was stretched from linear to this image."""
        if column_type == "linear":
            text = self._get_linear_explain_text()
        elif column_type == "stretched":
            text = self._get_auto_stretched_explain_text()
        elif column_type == "stretched_1":
            text = self._get_veralux_explain_text()
        elif column_type in ("stretched_2", "stretched_3"):
            slot = 2 if column_type == "stretched_2" else 3
            text = self._get_stretched_fits_explain_text(slot - 1)
        else:
            text = "No explanation available."
        dlg = QDialog(self)
        dlg.setWindowTitle("Linear → This Image")
        dlg.setMinimumSize(420, 320)
        layout = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(text)
        te.setStyleSheet("font-size: 10pt; color: #e0e0e0; background: #2b2b2b;")
        layout.addWidget(te)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    def _get_linear_explain_text(self) -> str:
        """Explanation for the Linear column."""
        return (
            "Linear — Raw sensor data, normalized to 0–1.\n\n"
            "The camera captures photons linearly: twice the photons = twice the pixel value. "
            "Raw astronomical images are very dark because the sky background is faint and only "
            "a small fraction of pixels are bright (stars, nebula). Most values cluster near zero.\n\n"
            "This histogram shows that distribution directly: a strong peak at the left (shadows) "
            "and a long tail to the right. No stretch has been applied; the data is as the sensor "
            "recorded it (after normalization to 0–1)."
        )

    def _get_auto_stretched_explain_text(self) -> str:
        """
        Explanation for the Auto-Stretched column, using Siril_Stretch_Comparison.html
        and current image values.

        Percentiles and means are computed on a subsampled view for very large images
        to keep the UI responsive; values remain representative of the full frame.
        """
        if self.img_linear is None or self.img_stretched is None:
            return "No image loaded."
        arr_s = _subsample_for_stats(self.img_linear)
        flat = arr_s.ravel()
        p_low = float(np.percentile(flat, 2))
        p_high = float(np.percentile(flat, 98))
        mean_lin = float(np.mean(flat))
        mean_str = float(np.mean(self.img_stretched.ravel()))
        factor = p_high - p_low
        stretch_ratio = 1.0 / factor if factor > 1e-9 else float('inf')
        scale = self.adu_max
        p_low_s = f"{int(round(p_low * scale))} ADU"
        p_high_s = f"{int(round(p_high * scale))} ADU"
        mean_lin_s = f"{int(round(mean_lin * scale))} ADU"
        mean_str_s = f"{int(round(mean_str * scale))} ADU"
        return (
            "Auto-Stretched — Stretch explanation (from Siril stretch comparison)\n"
            "══════════════════════════════════════════════════════════════════\n\n"
            "What is stretching?\n"
            "An astronomical camera captures photons linearly; most nebula detail lives in the "
            "bottom 1–5% of that range, invisible on screen. Stretching is a nonlinear remapping "
            "that boosts faint signals and compresses bright stars so everything becomes visible.\n\n"
            "Siril built-in autostretch (GHT / MTF):\n"
            "Siril's native autostretch uses a Midtone Transfer Function (MTF), the same rational "
            "function as PixInsight's STF. Since Siril 1.2+ it is wrapped in the Generalised "
            "Hyperbolic Stretch (GHT) framework; the default mode is still classic MTF.\n\n"
            "  • Formula:  MTF(x, m) = (m − 1)·x / ((2m − 1)·x − m)\n"
            "    where m = midtone balance (0 < m < 1), x = pixel value in [0,1] after black-point subtraction.\n\n"
            "  • Pipeline: Compute median + MAD → Derive shadow clip → Solve for midtone m → "
            "Apply MTF to all channels (linked).\n\n"
            "  • Color: Channels are linked — one set of (shadows, midtones, highlights) for R,G,B. "
            "Preserves color balance; no per-channel tuning. Fast and predictable; limited highlight "
            "control (bright stars can clip); purely automatic.\n\n"
            "This viewer’s Auto-Stretched column:\n"
            "Here we use a simpler 2%–98% percentile stretch for a quick preview (not the full MTF). "
            "The range between the 2nd and 98th percentiles is mapped to 0–1; values outside clip to black/white.\n\n"
            f"Parameters for this image:\n"
            f"  • Low cut (2nd %):  {p_low_s}\n"
            f"  • High cut (98th %): {p_high_s}\n"
            f"  • Formula: new = (old − {p_low_s}) ÷ ({p_high_s} − {p_low_s})\n"
            f"  • Stretch factor: ×{stretch_ratio:.1f}\n"
            f"  • Linear mean: {mean_lin_s}  →  Stretched mean: {mean_str_s}"
        )

    def _get_veralux_explain_text(self) -> str:
        """Explanation for FITS 1 — VeraLux HyperMetric Stretch."""
        return (
            "FITS 1 — VeraLux HyperMetric Stretch (Riccardo Paterniti)\n"
            "Linear → This histogram\n\n"
            "Step 1 — Adaptive Anchor:\n"
            "  Subtract an adaptive black point (morphological analysis) so the sky background "
            "maps to ~0. More robust than median−σ for gradients and faint targets.\n\n"
            "Step 2 — Luminance Extraction:\n"
            "  Extract L from RGB using sensor-weighted coefficients (25+ camera profiles). "
            "Store color ratios R/L, G/L, B/L to preserve hue.\n\n"
            "Step 3 — arcsinh on L only:\n"
            "  Apply inverse hyperbolic sine stretch to luminance only:\n"
            "  IHS(x) = (arcsinh(D·x+b) − arcsinh(b)) / (arcsinh(D+b) − arcsinh(b))\n"
            "  Shadows (small x) get a steep boost; bright values flatten, so faint nebula "
            "expands while star cores avoid clipping. Unlike MTF, arcsinh compresses highlights gracefully.\n\n"
            "Step 4 — Rebuild RGB:\n"
            "  R_out = L_stretched · (R/L), G_out = L_stretched · (G/L), B_out = L_stretched · (B/L).\n"
            "  Hue is preserved; only brightness changes.\n\n"
            "Result: Values that peaked near zero in linear now span 0–1. The histogram shape "
            "reflects this new distribution. Best for extreme dynamic range and true-color imaging."
        )

    def _get_stretched_fits_explain_text(self, slot: int) -> str:
        """Explanation for FITS 2 or 3 — generic stretched file."""
        name = self.stretched_filenames[slot] if slot < len(self.stretched_filenames) else None
        name_s = name or f"Stretched {slot + 1}"
        return (
            f"FITS {slot + 1} ({name_s}) — Externally stretched\n\n"
            "This file was stretched outside this viewer (e.g. in Siril, PixInsight, or another tool). "
            "The histogram shows the distribution of pixel values in the already-processed image.\n\n"
            "We do not know the exact stretch method used, but the result is normalized to 0–1. "
            "Compare with Linear and Auto-Stretched to see how different algorithms redistribute "
            "the original data."
        )

    def _compute_histogram(self):
        vis = {'rgb': self.chk_rgb.isChecked(), 'r': self.chk_r.isChecked(), 'g': self.chk_g.isChecked(), 'b': self.chk_b.isChecked(), 'l': self.chk_l.isChecked()}
        log_mode = self.radio_log.isChecked()
        if self.img_linear is not None and self.img_stretched is not None:
            arr_linear = self.img_linear.astype(np.float32)
            arr_stretched = self.img_stretched.astype(np.float32)
            hist_linear, edges = self._compute_histogram_from(arr_linear)
            hist_stretched, _ = self._compute_histogram_from(arr_stretched)
            self.hist_widget_linear.set_histograms(hist_linear, edges)
            self.hist_widget_linear.set_visibility(**vis)
            self.hist_widget_linear.set_x_axis_mode(self.x_axis_mode, self.adu_max)
            self.hist_widget_stretched.set_histograms(hist_stretched, edges)
            self.hist_widget_stretched.set_visibility(**vis)
            self.hist_widget_stretched.set_x_axis_mode(self.x_axis_mode, self.adu_max)
            self.hist_widget_linear.set_log_mode(log_mode)
            self.hist_widget_stretched.set_log_mode(log_mode)
        for i in range(self.NUM_EXTRA_STRETCHED):
            arr = self.img_stretched_extra[i]
            if arr is not None:
                hist, edges = self._compute_histogram_from(arr.astype(np.float32))
                self.hist_widget_extra[i].set_histograms(hist, edges)
                self.hist_widget_extra[i].set_x_axis_mode(self.x_axis_mode, self.adu_max)
            else:
                empty_hist, empty_edges = _empty_histogram_data()
                self.hist_widget_extra[i].set_histograms(empty_hist, empty_edges)
            self.hist_widget_extra[i].set_visibility(**vis)
            self.hist_widget_extra[i].set_log_mode(log_mode)
        # Keep inline 3D surface widgets in sync with current images (Z = selected channel, log/linear from Y-axis radios)
        log_mode = self.radio_log.isChecked()
        ch = self._get_3d_channel()
        if self.img_linear is not None:
            self.surface_widget_linear.set_image(
                _image_to_channel_2d(self.img_linear, ch), log_mode=log_mode, adu_max=self.adu_max, channel=ch
            )
        else:
            self.surface_widget_linear.set_image(None)
        if self.img_stretched is not None:
            self.surface_widget_stretched.set_image(
                _image_to_channel_2d(self.img_stretched, ch), log_mode=log_mode, adu_max=self.adu_max, channel=ch
            )
        else:
            self.surface_widget_stretched.set_image(None)
        for i in range(self.NUM_EXTRA_STRETCHED):
            if self.img_stretched_extra[i] is not None:
                self.surface_widget_extra[i].set_image(
                    _image_to_channel_2d(self.img_stretched_extra[i], ch),
                    log_mode=log_mode,
                    adu_max=self.adu_max,
                    channel=ch,
                )
            else:
                self.surface_widget_extra[i].set_image(None)
        self._update_stats()

    def _update_image_display(self) -> None:
        if self.img_linear is not None and self.img_stretched is not None:
            # Linear: display stretch (min-max) so structure is visible
            lin = self.img_linear.astype(np.float32)
            mn, mx = lin.min(), lin.max()
            if mx > mn + 1e-8:
                lin = (lin - mn) / (mx - mn)
            lin = np.clip(lin, 0.0, 1.0)
            disp_linear, h_d, w_d = _prepare_display_image(lin)
            qimg_linear = QImage(disp_linear.data, w_d, h_d, w_d * 3, QImage.Format.Format_RGB888)
            self.pix_item_linear.setPixmap(QPixmap.fromImage(qimg_linear))
            self.view_linear.scene().setSceneRect(0, 0, w_d, h_d)
            # Stretched: as-is
            disp_stretched, h_d, w_d = _prepare_display_image(self.img_stretched)
            qimg_stretched = QImage(disp_stretched.data, w_d, h_d, w_d * 3, QImage.Format.Format_RGB888)
            self.pix_item_stretched.setPixmap(QPixmap.fromImage(qimg_stretched))
            self.view_stretched.scene().setSceneRect(0, 0, w_d, h_d)
        else:
            self.pix_item_linear.setPixmap(QPixmap())
            self.pix_item_stretched.setPixmap(QPixmap())
        # Extra stretched columns
        for i in range(self.NUM_EXTRA_STRETCHED):
            img = self.img_stretched_extra[i]
            if img is not None:
                disp, h_d, w_d = _prepare_display_image(img)
                qimg = QImage(disp.data, w_d, h_d, w_d * 3, QImage.Format.Format_RGB888)
                self.pix_item_extra[i].setPixmap(QPixmap.fromImage(qimg))
                self.view_extra[i].scene().setSceneRect(0, 0, w_d, h_d)
            else:
                self.pix_item_extra[i].setPixmap(QPixmap())

    def load_image(self):
        no_image_msg = "No image is currently loaded in Siril. Please load a FITS image first."
        try:
            if not self.siril.connected:
                self.siril.connect()
            with self.siril.image_lock():
                pixeldata = self.siril.get_image_pixeldata(preview=False)
            if pixeldata is None:
                QMessageBox.warning(self, "No Image", no_image_msg)
                return
            self.adu_max = _adu_max_from_data(pixeldata)
            img = normalize_input(pixeldata, self.adu_max)
            img = ensure_hwc(img)
            self.img_linear = img.copy()
            self.img_stretched = autostretch_percentile(img)
            self._update_image_display()
            self._compute_histogram()
            self.setWindowTitle("Siril Histogram Viewer - Loaded")
            QTimer.singleShot(100, self.fit_view_linear)
            QTimer.singleShot(100, self.fit_view_stretched)
        except NoImageError:
            QMessageBox.warning(self, "No Image", no_image_msg)
        except SirilConnectionError:
            QMessageBox.warning(
                self,
                "Connection Timeout",
                "The connection to Siril timed out (e.g. while releasing the image lock). "
                "Ensure a FITS image is loaded in Siril and try \"Refresh from Siril\" again."
            )
        except SirilError as e:
            err = str(e).lower()
            if "no image" in err or "fits" in err or "pixeldaten" in err or "pixel data" in err:
                QMessageBox.warning(self, "No Image", no_image_msg)
            else:
                QMessageBox.critical(self, "Siril Error", f"Siril error: {e}")
        except (OSError, ConnectionError, RuntimeError):
            QMessageBox.warning(self, "No Image", no_image_msg)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load image: {e}\n\n{traceback.format_exc()}"
            )


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        win = HistogramViewerWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Histogram Viewer v{VERSION} loaded.")
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
            "Histogram Viewer Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
