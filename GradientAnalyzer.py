"""
Siril Gradient Analyzer
Script Version: 1.8.1
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script reads the current image from Siril, divides it into a configurable grid of tiles,
computes sigma-clipped median background levels per tile, and renders a color-coded heatmap.
It helps assess background gradients (e.g. from light pollution) and whether background
extraction is needed.

Features:
- Configurable grid resolution (4-64 rows/cols)
- Iterative sigma-clipping to exclude stars and bright objects
- Gradient strength, direction, and uniformity metrics
- Visual strength gauge with color-coded severity
- 2D heatmap and optional 3D surface view
- Gradient profile cross-sections (horizontal + vertical)
- Tile median histogram showing background value distribution
- Vignetting vs. linear gradient detection
- Quadrant analysis (NW/NE/SW/SE) for sample point guidance
- Concrete Siril command suggestions (subsky parameters)
- Before/After comparison with delta display
- Optional per-channel (R, G, B) analysis for chromaticity
- PNG export of heatmap
- Linear data detection with warning for stretched images
- Background model preview (fitted polynomial surface + residuals)
- Gradient magnitude map (rate of change visualization)
- Gradient direction arrow overlay on heatmap
- Star density warning for dense star fields
- Light pollution color characterization from RGB channel ratios
- Vignetting symmetry analysis (flat calibration quality check)
- Gradient-free region percentage (localized vs full-field gradient)
- Extended object detection (nebula/galaxy bias warning)
- Subsky sample point coordinate export (setref/addref commands)
- Mosaic panel boundary detection
- JSON sidecar file for temporal comparison across sessions
- Hotspot/outlier tile detection (artifacts, satellite trails)
- RMS improvement prediction (estimated post-extraction gradient)
- Subtraction preview (side-by-side before/after gradient removal)
- Gradient history log (tracks gradient evolution across sessions)
- Residual pattern detection (Moran's I spatial autocorrelation)
- Configurable threshold presets (Broadband, Narrowband, Fast optics)
- Annotated PNG export (metrics burned into heatmap image)
- Sub-frame batch ranking (FITS quality analysis via astropy)
- Adaptive sigma suggestion (based on star density rejection rates)
- Weighted background model (excludes flagged tiles from polynomial fit)
- Dither/rotation edge detection (detects tapered stacking borders)
- Banding/column bias detection (periodic sensor readout artifacts via FFT)
- Per-channel gradient direction (LP direction analysis per RGB channel)
- Cos^4 corner vignetting correction (natural falloff for fast optics)
- Interactive sample point editing (click heatmap to place/remove points)
- One-click subsky execution (Apply subsky & Re-analyze via Siril API)
- FWHM/eccentricity map (star shape variation across the field)
- Background normalization detection (warns about pre-normalized data)
- FITS header calibration cross-check (FLATCOR/CALSTAT/DARKCOR keywords)
- WCS-aware geographic LP direction (real-world compass bearing from WCS rotation)
- Photometric sky brightness in mag/arcsec² (from SPCC calibration + plate scale)
- Subsky sample point passthrough (feeds setref/addref points to subsky execution)
- Auto-iterate extraction (repeat subsky until gradient < 2% or max passes)
- Temporal sky gradient modeling (DATE-OBS correlation for sub-frame rejection)
- Residual map with exclusion mask overlay (shows which tiles were excluded and why)
- Dew/frost detection (cross-correlates FWHM radial increase with brightness pattern)
- Amplifier glow detection (exponential corner profile vs LP differentiation)
- Consolidated report export (plain-text report for documentation/forums)
- Artifact-adjusted gradient note (warns when reported % includes artifact contributions)
- Priority-based workflow (critical calibration/hardware issues flagged before extraction)
- Dual-scale gradient-free analysis (global + local 3x3 neighborhood check)
- Robust improvement prediction (original median reference, ineffective extraction warning)
- Poor polynomial fit handling (degree 1 fallback when all R² < 0.5)
- FWHM reliability guards (min 3 stars/tile, 3-sigma outlier rejection, eccentricity caveat)

Run from Siril via Processing -> Scripts. Place GradientAnalyzer.py inside a folder named
Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.8.1 - Analysis accuracy and code quality refinements
      - Artifact-adjusted gradient note: warns when reported % includes banding/amp glow/dew/missing flats
      - Priority-based workflow: critical issues flagged before extraction; subsky labeled "AFTER FIXING ISSUES"
      - Dual-scale gradient-free: tiles must pass global + local 3x3 check (prevents contradictory metrics)
      - Robust prediction: uses original median, warns when reduction < 20% ("essentially ineffective")
      - Poor fit handling: degree 1 fallback when all R² < 0.5, avoids overfitting noise
      - FWHM reliability: min 3 stars/tile, 3-sigma outlier rejection, eccentricity >= 0.40 caveat
      - Residuals / Mask tab added to help documentation
      - Code cleanup: removed unused load_history(), dead code in analyze_single_fits()
      - Narrowed 14 broad except Exception clauses to specific exception types
      - Refactored R/G/B channel computation to loop
1.8.0 - Professional workflow integration and hardware diagnostics
      - FITS header calibration check: reads FLATCOR/CALSTAT/DARKCOR from FITS headers
      - WCS geographic LP direction: converts gradient direction to real-world compass bearing
      - Photometric sky brightness: mag/arcsec² with Bortle class estimate (requires SPCC)
      - Sample point passthrough: feeds manual/auto points via setref/addref before subsky
      - Auto-iterate extraction: repeats subsky+analyze until gradient < 2% or 3 passes
      - Temporal gradient modeling: correlates DATE-OBS with gradient for sub rejection
      - Residual/exclusion mask tab: shows fit residuals + which tiles were excluded (red overlay)
      - Dew/frost detection: cross-correlates radial FWHM increase with brightness pattern
      - Amplifier glow detection: exponential corner profile analysis vs LP differentiation
      - Consolidated report export: plain-text report with all diagnostics for documentation
1.7.0 - Expert-level diagnostics and interactive workflow
      - Weighted background model: excludes extended objects, hotspots, stacking edges from fit
      - Dither/rotation edge detection: identifies tapered borders from stacking
      - Banding detection: periodic row/column sensor bias via FFT analysis
      - Per-channel gradient direction: detects LP from different compass directions per RGB
      - Cos^4 vignetting correction: separates natural optical falloff from true gradients
      - Interactive sample points: left-click heatmap to add, right-click to remove
      - One-click subsky: execute recommended subsky command and auto re-analyze
      - FWHM/eccentricity map: star shape variation with tilt/curvature detection
      - Normalization detection: warns when background-normalized data may mislead analysis
      - Weight mask system: unified tile exclusion for all flagged anomalies
1.6.0 - Workflow automation and quality-of-life features
      - Subtraction preview: side-by-side before/after gradient removal visualization
      - Gradient history log: tracks gradient evolution across sessions (last 50 entries)
      - Residual pattern detection: Moran's I spatial autocorrelation on fit residuals
      - Configurable threshold presets: Broadband, Narrowband, Fast optics
      - Annotated PNG export: burns key metrics into saved heatmap image
      - Sub-frame batch ranking: analyzes FITS files for gradient quality sorting
      - Adaptive sigma suggestion: recommends sigma based on star density rejection rates
1.5.0 - Advanced diagnostics and workflow automation
      - Vignetting symmetry analysis: detects asymmetric flat residuals
      - Gradient-free region percentage: localized vs full-field gradient
      - Extended object detection: flags tiles with nebulae/galaxies
      - Subsky sample point export: generates setref/addref commands
      - Mosaic panel boundary detection from gradient magnitude
      - JSON sidecar persistence for cross-session comparison
      - Hotspot detection: outlier tiles (artifacts, satellite trails)
      - RMS improvement prediction: estimated strength after subsky
1.4.0 - Astro-expert analysis features
      - Linear data detection: warns when image appears stretched (non-linear)
      - Background model preview tab: shows fitted polynomial surface and residuals
      - Gradient magnitude tab: rate-of-change map highlighting steepest gradients
      - Gradient direction arrow overlay on heatmap (darkest → brightest)
      - Star density warning: detects dense star fields via sigma-clip rejection rates
      - Light pollution color characterization from per-channel gradient strengths
1.3.0 - Usability and quality improvements
      - Progress bar during analysis (UI stays responsive)
      - Keyboard shortcut F5 for Analyze
      - Copy results to clipboard button
      - Persistent settings (grid, sigma, checkboxes via QSettings)
      - Adaptive grid resolution warning when tiles are too small
      - Per-channel gradient data feeds into VeraLux Nox recommendation
      - Colorbar range locking for meaningful before/after visual comparison
1.2.0 - Advanced decision support
      - Gradient complexity estimation (linear/quadratic/cubic polynomial fits)
      - Tool-specific recommendations: subsky, AutoBGE, GraXpert, VeraLux Nox
      - Sample point guidance overlay on heatmap (green=good, red=avoid)
      - Measurement confidence indicator (based on gradient SNR)
      - Step-by-step workflow guidance with ordered actions
      - Edge-to-center ratio for robust vignetting detection
1.1.0 - Decision-support enhancements
      - Visual gradient strength gauge
      - Horizontal/vertical gradient profile cross-sections
      - Vignetting vs. linear gradient detection
      - Quadrant summary (NW/NE/SW/SE median values)
      - Tile median histogram (background value distribution)
      - Before/After comparison with delta values
      - Concrete Siril command suggestions (subsky)
1.0.0 - Initial release
      - Grid-based background gradient analysis with heatmap and 3D view
"""
from __future__ import annotations

import sys
import os
import traceback
import re
import datetime
import numpy as np

import sirilpy as s
from sirilpy import NoImageError

try:
    from sirilpy.exceptions import SirilError, SirilConnectionError
except ImportError:
    class SirilError(Exception):
        pass
    class SirilConnectionError(Exception):
        pass

s.ensure_installed("numpy", "PyQt6", "matplotlib", "scipy")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QSizePolicy, QDialog, QTextEdit, QTabWidget, QScrollArea,
    QProgressBar, QComboBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QShortcut, QKeySequence

VERSION = "1.8.1"

# Settings keys
SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "GradientAnalyzer"

# Minimum recommended tile dimension (pixels) for reliable sigma-clipping
MIN_TILE_PX = 50

# Layout constants
LEFT_PANEL_WIDTH = 340

# Luminance coefficients: Rec.709 (BT.709)
LUMINANCE_R = 0.2126
LUMINANCE_G = 0.7152
LUMINANCE_B = 0.0722

# Gradient strength thresholds for assessment (default: Broadband)
GRADIENT_THRESHOLDS = [
    (2.0, "Very uniform — no extraction needed", "#55aa55"),
    (5.0, "Slight gradient — gentle extraction recommended", "#aaaa55"),
    (15.0, "Significant gradient — extraction strongly recommended", "#dd8833"),
    (float("inf"), "Strong gradient — aggressive extraction required", "#dd4444"),
]

# Threshold presets: (uniform_cutoff, slight_cutoff, significant_cutoff)
THRESHOLD_PRESETS = {
    "Broadband (default)": (2.0, 5.0, 15.0),
    "Narrowband (strict)": (1.0, 3.0, 8.0),
    "Fast optics (tolerant)": (4.0, 8.0, 20.0),
}


# ------------------------------------------------------------------------------
# STYLING
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

QSlider::groove:horizontal{background:#3c3c3c;height:6px;border-radius:3px}
QSlider::handle:horizontal{background:#88aaff;width:14px;margin:-4px 0;border-radius:7px}
QSlider::sub-page:horizontal{background:#285299;border-radius:3px}

QSpinBox,QDoubleSpinBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QSpinBox:focus,QDoubleSpinBox:focus{border-color:#88aaff}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton#CloseButton{background-color:#5a2a2a;border:1px solid #804040}
QPushButton#CloseButton:hover{background-color:#7a3a3a}
QPushButton#AnalyzeButton{background-color:#2a4a2a;border:1px solid #408040;padding:10px;font-size:12pt}
QPushButton#AnalyzeButton:hover{background-color:#3a6a3a}

QTabWidget::pane{border:1px solid #444444;background:#2b2b2b}
QTabBar::tab{background:#3c3c3c;color:#cccccc;padding:6px 12px;border:1px solid #444444;border-bottom:none;border-radius:4px 4px 0 0;margin-right:2px}
QTabBar::tab:selected{background:#2b2b2b;color:#88aaff;font-weight:bold}
QTabBar::tab:hover{background:#4a4a4a}

QScrollArea{border:none;background:#2b2b2b}
"""


# ------------------------------------------------------------------------------
# ANALYSIS ENGINE
# ------------------------------------------------------------------------------

def compute_luminance(data: np.ndarray) -> np.ndarray:
    """
    Compute luminance from image data.
    data shape: (channels, height, width) as delivered by sirilpy.
    Returns 2D array (height, width).
    """
    if data.ndim == 3 and data.shape[0] == 3:
        return (LUMINANCE_R * data[0] + LUMINANCE_G * data[1] + LUMINANCE_B * data[2]).astype(np.float32)
    elif data.ndim == 3 and data.shape[0] == 1:
        return data[0].astype(np.float32)
    elif data.ndim == 2:
        return data.astype(np.float32)
    return data.reshape(data.shape[-2], data.shape[-1]).astype(np.float32)


def analyse_tile(tile_data: np.ndarray, sigma: float = 2.5, iterations: int = 3) -> dict:
    """
    Compute sigma-clipped median and std for a single tile.
    Iterative clipping excludes stars and bright objects.
    Returns dict with 'median', 'std', and 'rejection_pct'.
    """
    data = tile_data.flatten().astype(np.float64)
    if data.size == 0:
        return {"median": 0.0, "std": 0.0, "rejection_pct": 0.0}

    original_size = data.size
    for _ in range(iterations):
        if data.size == 0:
            break
        med = np.median(data)
        std = np.std(data)
        if std < 1e-15:
            break
        mask = np.abs(data - med) < sigma * std
        clipped = data[mask]
        if clipped.size == 0:
            break
        data = clipped

    med = float(np.median(data))
    std = float(np.std(data))
    rejection_pct = (1.0 - data.size / original_size) * 100.0 if original_size > 0 else 0.0
    return {"median": med, "std": std, "rejection_pct": rejection_pct}


def compute_tile_grid(
    image_2d: np.ndarray,
    grid_rows: int = 16,
    grid_cols: int = 16,
    sigma: float = 2.5,
    return_stds: bool = False,
    return_rejections: bool = False,
) -> np.ndarray | tuple:
    """
    Divide image into grid and compute sigma-clipped median per tile.
    Returns 2D array of shape (grid_rows, grid_cols) with median values.
    If return_stds=True, also returns per-tile std array (for confidence).
    If return_rejections=True, also returns per-tile rejection % array.
    """
    h, w = image_2d.shape
    tile_h = h // grid_rows
    tile_w = w // grid_cols
    medians = np.zeros((grid_rows, grid_cols), dtype=np.float64)
    stds = np.zeros((grid_rows, grid_cols), dtype=np.float64) if return_stds else None
    rejections = np.zeros((grid_rows, grid_cols), dtype=np.float64) if return_rejections else None

    for row in range(grid_rows):
        for col in range(grid_cols):
            y0 = row * tile_h
            y1 = (row + 1) * tile_h if row < grid_rows - 1 else h
            x0 = col * tile_w
            x1 = (col + 1) * tile_w if col < grid_cols - 1 else w
            tile = image_2d[y0:y1, x0:x1]
            stats = analyse_tile(tile, sigma=sigma)
            medians[row, col] = stats["median"]
            if stds is not None:
                stds[row, col] = stats["std"]
            if rejections is not None:
                rejections[row, col] = stats["rejection_pct"]

    result = [medians]
    if return_stds:
        result.append(stds)
    if return_rejections:
        result.append(rejections)
    return tuple(result) if len(result) > 1 else medians


def compute_gradient_metrics(tile_medians: np.ndarray) -> dict:
    """Compute global gradient metrics from the tile median matrix."""
    bg_min = float(np.min(tile_medians))
    bg_max = float(np.max(tile_medians))
    bg_median = float(np.median(tile_medians))

    if bg_median > 1e-15:
        strength_pct = (bg_max - bg_min) / bg_median * 100.0
        uniformity = float(np.std(tile_medians)) / bg_median * 100.0
    else:
        strength_pct = 0.0
        uniformity = 0.0

    max_pos = np.unravel_index(np.argmax(tile_medians), tile_medians.shape)
    min_pos = np.unravel_index(np.argmin(tile_medians), tile_medians.shape)
    dy = max_pos[0] - min_pos[0]
    dx = max_pos[1] - min_pos[1]
    angle = float(np.degrees(np.arctan2(dy, dx)))

    return {
        "strength_pct": strength_pct,
        "angle_deg": angle,
        "bg_min": bg_min,
        "bg_max": bg_max,
        "bg_range": bg_max - bg_min,
        "bg_median": bg_median,
        "uniformity": uniformity,
        "max_pos": max_pos,
        "min_pos": min_pos,
    }


def compute_quadrant_summary(tile_medians: np.ndarray) -> dict:
    """
    Compute median background per image quadrant (NW, NE, SW, SE).
    Helps the user identify which corners are brightest/darkest for
    sample point placement during background extraction.
    """
    rows, cols = tile_medians.shape
    mid_r = rows // 2
    mid_c = cols // 2
    # Image origin is lower-left, so row 0 = bottom
    sw = float(np.median(tile_medians[:mid_r, :mid_c]))
    se = float(np.median(tile_medians[:mid_r, mid_c:]))
    nw = float(np.median(tile_medians[mid_r:, :mid_c]))
    ne = float(np.median(tile_medians[mid_r:, mid_c:]))
    quadrants = {"NW": nw, "NE": ne, "SW": sw, "SE": se}
    brightest = max(quadrants, key=quadrants.get)
    darkest = min(quadrants, key=quadrants.get)
    return {
        "quadrants": quadrants,
        "brightest": brightest,
        "darkest": darkest,
        "spread": max(quadrants.values()) - min(quadrants.values()),
    }


def _build_normalized_grid(rows: int, cols: int) -> tuple[np.ndarray, np.ndarray]:
    """Build coordinate arrays normalized to [-1, 1] for surface fitting."""
    yy, xx = np.meshgrid(
        np.linspace(-1, 1, rows),
        np.linspace(-1, 1, cols),
        indexing="ij",
    )
    return xx.flatten(), yy.flatten()


def detect_vignetting(tile_medians: np.ndarray) -> dict:
    """
    Distinguish vignetting (radial falloff from center) from directional gradient
    (light pollution). Fits both a radial model and a linear plane, comparing R^2
    to determine which explains the data better.

    Returns dict with:
      - radial_r2: R-squared of radial (vignetting) fit
      - linear_r2: R-squared of linear (gradient) fit
      - is_vignetting: True if radial fit is significantly better
      - diagnosis: Human-readable string
    """
    rows, cols = tile_medians.shape
    flat = tile_medians.flatten()
    n = flat.size
    if n < 4:
        return {"radial_r2": 0.0, "linear_r2": 0.0, "is_vignetting": False, "diagnosis": "Too few tiles"}

    xx_flat, yy_flat = _build_normalized_grid(rows, cols)

    ss_tot = float(np.sum((flat - np.mean(flat)) ** 2))
    if ss_tot < 1e-20:
        return {"radial_r2": 1.0, "linear_r2": 1.0, "is_vignetting": False, "diagnosis": "Perfectly uniform"}

    # Linear fit: z = a*x + b*y + c
    A_lin = np.column_stack([xx_flat, yy_flat, np.ones(n)])
    try:
        coeffs_lin, _, _, _ = np.linalg.lstsq(A_lin, flat, rcond=None)
        pred_lin = A_lin @ coeffs_lin
        ss_res_lin = float(np.sum((flat - pred_lin) ** 2))
        r2_lin = 1.0 - ss_res_lin / ss_tot
    except np.linalg.LinAlgError:
        r2_lin = 0.0

    # Radial fit: z = a*r^2 + b*r + c  (r = distance from center)
    rr = np.sqrt(xx_flat**2 + yy_flat**2)
    A_rad = np.column_stack([rr**2, rr, np.ones(n)])
    try:
        coeffs_rad, _, _, _ = np.linalg.lstsq(A_rad, flat, rcond=None)
        pred_rad = A_rad @ coeffs_rad
        ss_res_rad = float(np.sum((flat - pred_rad) ** 2))
        r2_rad = 1.0 - ss_res_rad / ss_tot
    except np.linalg.LinAlgError:
        r2_rad = 0.0

    # Decision: vignetting if radial R^2 is notably better than linear
    is_vig = r2_rad > r2_lin + 0.05 and r2_rad > 0.3

    if is_vig:
        diagnosis = "Vignetting detected (radial falloff from center) — correct with flat frames"
    elif r2_lin > r2_rad + 0.05 and r2_lin > 0.3:
        diagnosis = "Directional gradient (light pollution) — use background extraction (subsky)"
    elif max(r2_rad, r2_lin) < 0.15:
        diagnosis = "No strong pattern — background is fairly uniform"
    else:
        diagnosis = "Mixed pattern — may contain both vignetting and directional gradient"

    return {
        "radial_r2": r2_rad,
        "linear_r2": r2_lin,
        "is_vignetting": is_vig,
        "diagnosis": diagnosis,
    }


def estimate_gradient_complexity(tile_medians: np.ndarray) -> dict:
    """
    Estimate gradient complexity by fitting polynomial surfaces of increasing degree
    and comparing residuals. Determines whether the gradient is linear (degree 1),
    quadratic (degree 2), or higher order — directly maps to subsky degree parameter.

    Returns dict with:
      - best_degree: recommended polynomial degree (1, 2, or 3)
      - r2_by_degree: {1: r2, 2: r2, 3: r2}
      - improvement_2_over_1: relative improvement of degree 2 over 1
      - improvement_3_over_2: relative improvement of degree 3 over 2
      - description: human-readable complexity assessment
    """
    rows, cols = tile_medians.shape
    flat = tile_medians.flatten()
    n = flat.size

    xx_flat, yy_flat = _build_normalized_grid(rows, cols)

    ss_tot = float(np.sum((flat - np.mean(flat)) ** 2))
    if ss_tot < 1e-20:
        return {
            "best_degree": 1, "r2_by_degree": {1: 1.0, 2: 1.0, 3: 1.0},
            "improvement_2_over_1": 0.0, "improvement_3_over_2": 0.0,
            "description": "Perfectly uniform — any degree works",
        }

    r2 = {}

    # Degree 1: z = a*x + b*y + c
    A1 = np.column_stack([xx_flat, yy_flat, np.ones(n)])
    try:
        c1, _, _, _ = np.linalg.lstsq(A1, flat, rcond=None)
        r2[1] = 1.0 - float(np.sum((flat - A1 @ c1) ** 2)) / ss_tot
    except np.linalg.LinAlgError:
        r2[1] = 0.0

    # Degree 2: z = a*x^2 + b*y^2 + c*x*y + d*x + e*y + f
    A2 = np.column_stack([xx_flat**2, yy_flat**2, xx_flat * yy_flat, xx_flat, yy_flat, np.ones(n)])
    try:
        c2, _, _, _ = np.linalg.lstsq(A2, flat, rcond=None)
        r2[2] = 1.0 - float(np.sum((flat - A2 @ c2) ** 2)) / ss_tot
    except np.linalg.LinAlgError:
        r2[2] = r2[1]

    # Degree 3: add cubic terms
    A3 = np.column_stack([
        xx_flat**3, yy_flat**3, xx_flat**2 * yy_flat, xx_flat * yy_flat**2,
        xx_flat**2, yy_flat**2, xx_flat * yy_flat, xx_flat, yy_flat, np.ones(n),
    ])
    try:
        c3, _, _, _ = np.linalg.lstsq(A3, flat, rcond=None)
        r2[3] = 1.0 - float(np.sum((flat - A3 @ c3) ** 2)) / ss_tot
    except np.linalg.LinAlgError:
        r2[3] = r2[2]

    # Determine best degree: significant improvement threshold
    imp_2_over_1 = r2[2] - r2[1]
    imp_3_over_2 = r2[3] - r2[2]

    # Check if ALL polynomial fits are poor (none explain the data well)
    best_r2 = max(r2.values())
    all_fits_poor = best_r2 < 0.5

    if r2[1] > 0.90:
        best = 1
        desc = "Simple linear gradient — polynomial degree 1 is sufficient"
    elif imp_2_over_1 > 0.05 and r2[2] > 0.85:
        if imp_3_over_2 > 0.05 and r2[3] > r2[2] + 0.03:
            best = 3
            desc = "Complex non-linear gradient — degree 3 needed, consider GraXpert for AI-based extraction"
        else:
            best = 2
            desc = "Quadratic gradient — polynomial degree 2 recommended"
    elif imp_3_over_2 > 0.05:
        best = 3
        desc = "Complex gradient — degree 3 needed, consider GraXpert for AI-based extraction"
    elif all_fits_poor:
        # None of the polynomial degrees explain more than 50% of the variation.
        # This usually means the "gradient" is actually dominated by local anomalies
        # (hotspots, extended objects, banding, amp glow) rather than a smooth background.
        # Use degree 1 (lowest) to avoid overfitting noise with higher degrees
        # that barely improve R² (e.g., 0.353 → 0.384 is not meaningful).
        best = 1
        desc = (
            f"Poor polynomial fit (best R\u00b2={best_r2:.2f}) — the background variation is NOT "
            "well-explained by any polynomial. This often indicates hotspots, extended objects, "
            "sensor artifacts, or amp glow rather than a smooth gradient. "
            "GraXpert or manual investigation is strongly recommended over subsky."
        )
    else:
        best = 1
        desc = "Low-order gradient — polynomial degree 1 should suffice"

    return {
        "best_degree": best,
        "r2_by_degree": r2,
        "improvement_2_over_1": imp_2_over_1,
        "improvement_3_over_2": imp_3_over_2,
        "description": desc,
    }


def compute_edge_center_ratio(tile_medians: np.ndarray) -> dict:
    """
    Compute the ratio of edge brightness to center brightness.
    Helps distinguish vignetting (edges darker than center) from
    light pollution (one edge brighter, other edge/center darker).

    Returns dict with:
      - edge_median: median of all edge tiles
      - center_median: median of inner tiles
      - ratio: edge/center (< 1.0 = edges darker = vignetting pattern)
      - diagnosis: human-readable string
    """
    rows, cols = tile_medians.shape
    if rows < 4 or cols < 4:
        return {"edge_median": 0.0, "center_median": 0.0, "ratio": 1.0,
                "diagnosis": "Grid too small for edge/center analysis"}

    # Edge tiles: first/last row and first/last column
    edge_mask = np.zeros_like(tile_medians, dtype=bool)
    edge_mask[0, :] = True
    edge_mask[-1, :] = True
    edge_mask[:, 0] = True
    edge_mask[:, -1] = True

    # Center tiles: inner quarter
    r1, r2 = rows // 4, 3 * rows // 4
    c1, c2 = cols // 4, 3 * cols // 4
    center = tile_medians[r1:r2, c1:c2]

    edge_med = float(np.median(tile_medians[edge_mask]))
    center_med = float(np.median(center))
    ratio = edge_med / center_med if center_med > 1e-15 else 1.0

    if ratio < 0.92:
        diag = "Edges significantly darker than center — strong vignetting pattern, apply flats"
    elif ratio < 0.97:
        diag = "Edges slightly darker — mild vignetting, flats recommended"
    elif ratio > 1.08:
        diag = "Edges brighter than center — light pollution from edges"
    elif ratio > 1.03:
        diag = "Edges slightly brighter — mild light pollution at edges"
    else:
        diag = "Edge and center brightness similar — no obvious vignetting"

    return {
        "edge_median": edge_med,
        "center_median": center_med,
        "ratio": ratio,
        "diagnosis": diag,
    }


def compute_confidence(tile_medians: np.ndarray, tile_stds: np.ndarray) -> dict:
    """
    Compute a confidence score for the gradient measurement.
    High tile noise relative to the gradient range means the measurement
    is less reliable.

    Returns dict with:
      - score: 0.0 (unreliable) to 1.0 (very confident)
      - label: "High" / "Medium" / "Low"
      - color: hex color for display
      - reason: explanation
    """
    grad_range = float(np.max(tile_medians) - np.min(tile_medians))
    mean_noise = float(np.mean(tile_stds))

    if grad_range < 1e-15:
        return {"score": 1.0, "label": "High", "color": "#55aa55",
                "reason": "Background is perfectly uniform"}

    # Signal-to-noise of the gradient itself
    snr = grad_range / max(mean_noise, 1e-15)

    if snr > 10.0:
        score = min(1.0, 0.8 + (snr - 10) * 0.02)
        return {"score": score, "label": "High", "color": "#55aa55",
                "reason": f"Gradient SNR={snr:.1f} — measurements are reliable"}
    elif snr > 3.0:
        score = 0.5 + (snr - 3) / 7 * 0.3
        return {"score": score, "label": "Medium", "color": "#aaaa55",
                "reason": f"Gradient SNR={snr:.1f} — results are usable but tile noise is notable"}
    else:
        score = max(0.1, snr / 3 * 0.5)
        return {"score": score, "label": "Low", "color": "#dd6644",
                "reason": f"Gradient SNR={snr:.1f} — high tile noise, increase grid size or sigma-clip"}


def check_linear_data(tile_medians: np.ndarray) -> dict:
    """
    Check whether the image data appears to be linear (unstretched).
    Background extraction should be performed on linear data.
    Returns dict with is_linear, median_level, and warning message.
    """
    med = float(np.median(tile_medians))
    if med > 0.4:
        return {
            "is_linear": False, "median_level": med,
            "warning": (
                f"Median background level is {med:.3f} — this image appears to be "
                "already stretched (non-linear). Background extraction on stretched data "
                "produces poor results. Apply gradient removal BEFORE stretching."
            ),
        }
    elif med > 0.25:
        return {
            "is_linear": False, "median_level": med,
            "warning": (
                f"Median background level is {med:.3f} — this image may be partially "
                "stretched. For best results, apply background extraction on linear data "
                "before any histogram stretch."
            ),
        }
    return {"is_linear": True, "median_level": med, "warning": ""}


def compute_background_model(
    tile_medians: np.ndarray,
    degree: int,
    weight_mask: np.ndarray | None = None,
) -> np.ndarray:
    """
    Compute the fitted polynomial background surface at the resolution of the
    tile grid. This shows what subsky would subtract at the given degree.

    weight_mask: optional 2D array (same shape as tile_medians) with values 0.0-1.0.
    Tiles with weight 0 are excluded from the fit (extended objects, hotspots, edges).
    Returns array same shape as tile_medians with the fitted model values.
    """
    rows, cols = tile_medians.shape
    flat = tile_medians.flatten()
    n = flat.size
    xx_flat, yy_flat = _build_normalized_grid(rows, cols)

    if degree == 1:
        A = np.column_stack([xx_flat, yy_flat, np.ones(n)])
    elif degree == 2:
        A = np.column_stack([xx_flat**2, yy_flat**2, xx_flat * yy_flat,
                             xx_flat, yy_flat, np.ones(n)])
    else:
        A = np.column_stack([
            xx_flat**3, yy_flat**3, xx_flat**2 * yy_flat, xx_flat * yy_flat**2,
            xx_flat**2, yy_flat**2, xx_flat * yy_flat, xx_flat, yy_flat, np.ones(n),
        ])

    try:
        if weight_mask is not None:
            w = weight_mask.flatten()
            # Only fit using tiles with weight > 0
            valid = w > 1e-10
            if np.sum(valid) < A.shape[1] + 1:
                # Not enough valid tiles — fall back to unweighted
                coeffs, _, _, _ = np.linalg.lstsq(A, flat, rcond=None)
            else:
                W = np.diag(np.sqrt(w[valid]))
                coeffs, _, _, _ = np.linalg.lstsq(W @ A[valid], W @ flat[valid], rcond=None)
        else:
            coeffs, _, _, _ = np.linalg.lstsq(A, flat, rcond=None)
        model = (A @ coeffs).reshape(rows, cols)
    except np.linalg.LinAlgError:
        model = np.full((rows, cols), np.median(flat))

    return model


def compute_gradient_magnitude(tile_medians: np.ndarray) -> np.ndarray:
    """
    Compute local gradient magnitude (rate of change) across the tile grid.
    Uses Sobel-like finite differences. Returns array of same shape with
    magnitude values — highlights where the background changes fastest.
    """
    # Gradient in row and column directions
    dy = np.gradient(tile_medians, axis=0)
    dx = np.gradient(tile_medians, axis=1)
    magnitude = np.sqrt(dx**2 + dy**2)
    return magnitude


def check_star_density(tile_rejections: np.ndarray, threshold: float = 40.0) -> dict:
    """
    Analyze sigma-clip rejection rates to detect star-dense regions.
    High rejection indicates many pixels were clipped (dense star fields,
    nebulosity, etc.) making the background estimate less reliable.

    Returns dict with:
      - max_rejection: highest rejection % across all tiles
      - mean_rejection: average rejection %
      - dense_tile_count: number of tiles above threshold
      - dense_tile_pct: percentage of tiles above threshold
      - warning: human-readable warning (empty if no issue)
    """
    max_rej = float(np.max(tile_rejections))
    mean_rej = float(np.mean(tile_rejections))
    dense_count = int(np.sum(tile_rejections > threshold))
    dense_pct = dense_count / tile_rejections.size * 100.0

    warning = ""
    if dense_pct > 30:
        warning = (
            f"{dense_count} tiles ({dense_pct:.0f}%) have rejection rates above {threshold:.0f}%. "
            "This suggests dense star fields or bright nebulosity. Background estimates "
            "in these areas may be unreliable — consider increasing sigma-clip to 3.0-3.5."
        )
    elif dense_pct > 10:
        warning = (
            f"{dense_count} tiles ({dense_pct:.0f}%) have elevated rejection rates. "
            "Some areas may contain dense star fields. Results are usable but less "
            "confident in those regions."
        )

    return {
        "max_rejection": max_rej,
        "mean_rejection": mean_rej,
        "dense_tile_count": dense_count,
        "dense_tile_pct": dense_pct,
        "warning": warning,
    }


def characterize_lp_color(channel_metrics: dict) -> dict:
    """
    Analyze per-channel gradient strengths to characterize light pollution type.
    channel_metrics: dict with 'r', 'g', 'b' keys, each containing metrics dict.

    Returns dict with:
      - dominant_channel: which channel has the strongest gradient
      - channel_strengths: {r, g, b} strength values
      - lp_type: estimated LP source type
      - description: human-readable assessment
    """
    r_str = channel_metrics["r"]["strength_pct"]
    g_str = channel_metrics["g"]["strength_pct"]
    b_str = channel_metrics["b"]["strength_pct"]
    strengths = {"R": r_str, "G": g_str, "B": b_str}
    dominant = max(strengths, key=strengths.get)
    spread = max(strengths.values()) - min(strengths.values())

    if spread < 1.5:
        lp_type = "Neutral / broadband"
        desc = (
            f"Channel gradients are similar (spread {spread:.1f}%). "
            "Light pollution appears broadband (natural skyglow or white LED). "
            "Standard polynomial extraction should work well."
        )
    elif dominant == "R" and r_str > g_str * 1.3:
        lp_type = "Sodium vapor (HPS)"
        desc = (
            f"Red channel dominates (R={r_str:.1f}%, G={g_str:.1f}%, B={b_str:.1f}%). "
            "Pattern matches high-pressure sodium (HPS) street lighting. "
            "VeraLux Nox is well-suited for this type of chromatic LP."
        )
    elif dominant == "B" and b_str > g_str * 1.3:
        lp_type = "LED / mercury vapor"
        desc = (
            f"Blue channel dominates (R={r_str:.1f}%, G={g_str:.1f}%, B={b_str:.1f}%). "
            "Pattern matches LED or mercury vapor lighting. "
            "VeraLux Nox or per-channel subsky extraction recommended."
        )
    elif dominant == "G":
        lp_type = "Mixed / fluorescent"
        desc = (
            f"Green channel dominates (R={r_str:.1f}%, G={g_str:.1f}%, B={b_str:.1f}%). "
            "May indicate fluorescent or mixed LP sources. "
            "Consider VeraLux Nox for color-aware extraction."
        )
    else:
        lp_type = "Chromatic (mixed)"
        desc = (
            f"Channels differ notably (R={r_str:.1f}%, G={g_str:.1f}%, B={b_str:.1f}%). "
            "Light pollution has a chromatic component. "
            "VeraLux Nox or per-channel extraction recommended."
        )

    return {
        "dominant_channel": dominant,
        "channel_strengths": strengths,
        "lp_type": lp_type,
        "description": desc,
    }


def check_vignetting_symmetry(tile_medians: np.ndarray) -> dict:
    """
    Check whether vignetting residuals are symmetric (properly corrected by flats)
    or asymmetric (tilted sensor, optical axis misalignment, incomplete flat correction).

    Compares median brightness of opposite edge strips:
      NW-edge vs SE-edge, NE-edge vs SW-edge, Top vs Bottom, Left vs Right.
    Large asymmetry suggests flat calibration is incomplete.

    Returns dict with:
      - pairs: dict of {pair_name: (val_a, val_b, delta_pct)}
      - max_asymmetry_pct: worst-case asymmetry percentage
      - is_asymmetric: True if asymmetry exceeds threshold
      - diagnosis: human-readable string
    """
    rows, cols = tile_medians.shape
    if rows < 6 or cols < 6:
        return {
            "pairs": {},
            "max_asymmetry_pct": 0.0,
            "is_asymmetric": False,
            "diagnosis": "Grid too small for symmetry analysis (need >= 6x6)",
        }

    # Edge strips: 2 rows/cols deep for stability
    top = float(np.median(tile_medians[-2:, :]))       # top 2 rows
    bottom = float(np.median(tile_medians[:2, :]))      # bottom 2 rows
    left = float(np.median(tile_medians[:, :2]))        # left 2 cols
    right = float(np.median(tile_medians[:, -2:]))      # right 2 cols

    # Corner quadrant edges (2x2 blocks in corners)
    nw = float(np.median(tile_medians[-2:, :2]))
    ne = float(np.median(tile_medians[-2:, -2:]))
    sw = float(np.median(tile_medians[:2, :2]))
    se = float(np.median(tile_medians[:2, -2:]))

    center_med = float(np.median(tile_medians[rows // 4 : 3 * rows // 4, cols // 4 : 3 * cols // 4]))

    def _asym_pct(a: float, b: float) -> float:
        denom = max(abs(a), abs(b), 1e-15)
        return abs(a - b) / denom * 100.0

    pairs = {
        "Top vs Bottom": (top, bottom, _asym_pct(top, bottom)),
        "Left vs Right": (left, right, _asym_pct(left, right)),
        "NW vs SE": (nw, se, _asym_pct(nw, se)),
        "NE vs SW": (ne, sw, _asym_pct(ne, sw)),
    }

    max_asym = max(p[2] for p in pairs.values())
    worst_pair = max(pairs, key=lambda k: pairs[k][2])

    # Threshold: > 2% asymmetry between opposite edges is notable
    if max_asym > 5.0:
        is_asym = True
        diag = (
            f"Significant asymmetry detected ({worst_pair}: {max_asym:.1f}%). "
            "Flat calibration may be incomplete — check for tilted sensor, "
            "misaligned optical train, or inconsistent flat illumination."
        )
    elif max_asym > 2.0:
        is_asym = True
        diag = (
            f"Mild asymmetry detected ({worst_pair}: {max_asym:.1f}%). "
            "Flat correction is mostly effective but residuals remain. "
            "May need better flat frames or synthetic flat correction."
        )
    else:
        is_asym = False
        diag = "Vignetting pattern is symmetric — flat calibration appears good."

    return {
        "pairs": pairs,
        "max_asymmetry_pct": max_asym,
        "is_asymmetric": is_asym,
        "diagnosis": diag,
    }


def compute_gradient_free_pct(
    tile_medians: np.ndarray,
    threshold_pct: float = 2.0,
) -> dict:
    """
    Compute what percentage of the image area has gradient below the 'uniform' threshold.

    Uses a dual-scale analysis:
    1. Global: each tile is compared to the image-wide median (catches large-scale gradients)
    2. Local: each tile is compared to its 3x3 neighborhood (catches local discontinuities)
    A tile is "gradient-free" only if it passes BOTH checks.

    Returns dict with:
      - uniform_pct: percentage of tiles in uniform regions
      - gradient_pct: percentage of tiles in gradient regions
      - uniform_tile_count: number of uniform tiles
      - total_tiles: total number of tiles
      - description: human-readable assessment
    """
    rows, cols = tile_medians.shape
    global_median = float(np.median(tile_medians))
    if global_median < 1e-15:
        return {
            "uniform_pct": 100.0, "gradient_pct": 0.0,
            "uniform_tile_count": rows * cols, "total_tiles": rows * cols,
            "description": "Image is empty or fully dark",
        }

    # Absolute threshold: tile deviating more than this from the global median
    # is considered to be in a gradient region
    abs_threshold = global_median * threshold_pct / 100.0
    uniform_count = 0
    total = rows * cols

    for r in range(rows):
        for c in range(cols):
            # Global check: tile vs image-wide median
            global_ok = abs(tile_medians[r, c] - global_median) < abs_threshold

            # Local check: tile vs 3x3 neighborhood median (catches discontinuities)
            r0, r1 = max(0, r - 1), min(rows, r + 2)
            c0, c1 = max(0, c - 1), min(cols, c + 2)
            local_med = np.median(tile_medians[r0:r1, c0:c1])
            local_ok = abs(tile_medians[r, c] - local_med) < abs_threshold

            if global_ok and local_ok:
                uniform_count += 1

    uniform_pct = uniform_count / total * 100.0
    gradient_pct = 100.0 - uniform_pct

    if uniform_pct > 90:
        desc = f"{uniform_pct:.0f}% of the image is gradient-free — very uniform background"
    elif uniform_pct > 70:
        desc = (
            f"{uniform_pct:.0f}% gradient-free, {gradient_pct:.0f}% affected. "
            "Gradient is localized — consider targeted extraction or manual sample placement "
            "in the affected region."
        )
    elif uniform_pct > 40:
        desc = (
            f"Only {uniform_pct:.0f}% gradient-free — gradient affects most of the image. "
            "Full-field extraction recommended."
        )
    else:
        desc = (
            f"Only {uniform_pct:.0f}% gradient-free — strong gradient across the entire field. "
            "Aggressive extraction is necessary."
        )

    return {
        "uniform_pct": uniform_pct,
        "gradient_pct": gradient_pct,
        "uniform_tile_count": uniform_count,
        "total_tiles": total,
        "description": desc,
    }


def detect_extended_objects(
    tile_medians: np.ndarray,
    tile_rejections: np.ndarray,
    sigma_threshold: float = 2.0,
) -> dict:
    """
    Detect tiles likely containing extended objects (large nebulae, galaxies)
    that bias background estimates. A tile is flagged if its clipped median
    is still notably above the global background AND rejection is low
    (ruling out star fields which have high rejection).

    Returns dict with:
      - flagged_tiles: list of (row, col) tuples
      - flagged_count: number of flagged tiles
      - flagged_pct: percentage of tiles flagged
      - warning: human-readable warning (empty if none)
    """
    rows, cols = tile_medians.shape
    flat = tile_medians.flatten()
    global_med = float(np.median(flat))
    global_std = float(np.std(flat))

    if global_std < 1e-15:
        return {"flagged_tiles": [], "flagged_count": 0, "flagged_pct": 0.0, "warning": ""}

    flagged = []
    for r in range(rows):
        for c in range(cols):
            val = tile_medians[r, c]
            rej = tile_rejections[r, c]
            # Bright tile (above threshold) with low rejection (not star field)
            if (val - global_med) > sigma_threshold * global_std and rej < 30.0:
                flagged.append((r, c))

    count = len(flagged)
    pct = count / (rows * cols) * 100.0

    warning = ""
    if count > 0:
        warning = (
            f"{count} tile{'s' if count > 1 else ''} ({pct:.1f}%) appear to contain "
            "extended objects (bright background, low star rejection). "
            "These tiles may bias the gradient fit — consider excluding them from "
            "sample point placement or using AI-based extraction (GraXpert) which "
            "handles nebulosity better."
        )

    return {
        "flagged_tiles": flagged,
        "flagged_count": count,
        "flagged_pct": pct,
        "warning": warning,
    }


def generate_sample_points(
    tile_medians: np.ndarray,
    img_width: int,
    img_height: int,
    extended_object_tiles: list | None = None,
    max_points: int = 20,
) -> dict:
    """
    Generate subsky sample point coordinates from the gradient analysis.
    Selects tiles in the darkest, most uniform regions — the best background
    sample locations. Avoids tiles flagged as extended objects.

    Returns dict with:
      - points: list of (x_px, y_px) tuples in image pixel coordinates
      - siril_commands: list of Siril console command strings
      - description: human-readable explanation
    """
    rows, cols = tile_medians.shape
    tile_w = img_width / cols
    tile_h = img_height / rows

    # Build exclusion set
    excluded = set()
    if extended_object_tiles:
        excluded = set(extended_object_tiles)

    # Score each tile: lower median = better background sample
    # Also prefer tiles with low local variance (uniform neighborhoods)
    candidates = []
    for r in range(rows):
        for c in range(cols):
            if (r, c) in excluded:
                continue
            # Skip edge tiles (first/last row/col) — often unreliable
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                continue
            val = tile_medians[r, c]
            # Local smoothness: std of 3x3 neighborhood
            r0, r1 = max(0, r - 1), min(rows, r + 2)
            c0, c1 = max(0, c - 1), min(cols, c + 2)
            local_std = float(np.std(tile_medians[r0:r1, c0:c1]))
            # Score: lower is better (prefer dark + smooth)
            score = val + local_std * 5.0
            candidates.append((score, r, c))

    candidates.sort()
    # Select up to max_points, ensuring spatial spread (min distance between points)
    min_dist_tiles = max(2, min(rows, cols) // 5)
    selected = []
    for score, r, c in candidates:
        if len(selected) >= max_points:
            break
        # Check minimum distance to already-selected points
        too_close = False
        for sr, sc in selected:
            if abs(r - sr) + abs(c - sc) < min_dist_tiles:
                too_close = True
                break
        if not too_close:
            selected.append((r, c))

    # Convert to pixel coordinates (tile center)
    points = []
    for r, c in selected:
        px_x = int((c + 0.5) * tile_w)
        px_y = int((r + 0.5) * tile_h)
        points.append((px_x, px_y))

    # Generate Siril commands
    commands = []
    if points:
        # Note: Siril's setref uses 1-based pixel coordinates
        for i, (px, py) in enumerate(points):
            if i == 0:
                commands.append(f"setref {px} {py}")
            else:
                commands.append(f"addref {px} {py}")

    desc = (
        f"Generated {len(points)} sample points in the darkest, most uniform regions. "
        f"Avoids edge tiles and extended objects. Copy the commands to Siril's console "
        f"for manual subsky sample placement."
    )

    return {
        "points": points,
        "siril_commands": commands,
        "description": desc,
    }


def detect_panel_boundaries(
    tile_medians: np.ndarray,
    magnitude: np.ndarray,
) -> dict:
    """
    Detect possible mosaic panel boundaries by looking for sharp linear
    discontinuities in the gradient magnitude map. A panel boundary appears
    as a line of high-magnitude tiles along a row or column.

    Returns dict with:
      - horizontal_boundaries: list of row indices with suspected boundaries
      - vertical_boundaries: list of col indices with suspected boundaries
      - is_mosaic: True if boundaries detected
      - description: human-readable assessment
    """
    rows, cols = magnitude.shape
    if rows < 8 or cols < 8:
        return {
            "horizontal_boundaries": [], "vertical_boundaries": [],
            "is_mosaic": False,
            "description": "Grid too small for panel boundary detection",
        }

    global_mag_med = float(np.median(magnitude))
    global_mag_std = float(np.std(magnitude))
    if global_mag_std < 1e-15:
        return {
            "horizontal_boundaries": [], "vertical_boundaries": [],
            "is_mosaic": False,
            "description": "No gradient variation detected",
        }

    threshold = global_mag_med + 2.5 * global_mag_std

    # Check each row: if the row's median magnitude is high AND significantly
    # above neighbors, it may be a panel boundary
    h_bounds = []
    for r in range(2, rows - 2):
        row_mag = float(np.median(magnitude[r, :]))
        neighbors = float(np.median(magnitude[max(0, r - 2):r, :]))
        neighbors2 = float(np.median(magnitude[r + 1:min(rows, r + 3), :]))
        neighbor_avg = (neighbors + neighbors2) / 2.0
        if row_mag > threshold and row_mag > neighbor_avg * 1.8:
            # Also check that the discontinuity spans most of the row
            high_cols = np.sum(magnitude[r, :] > threshold)
            if high_cols > cols * 0.4:
                h_bounds.append(r)

    # Check each column similarly
    v_bounds = []
    for c in range(2, cols - 2):
        col_mag = float(np.median(magnitude[:, c]))
        neighbors = float(np.median(magnitude[:, max(0, c - 2):c]))
        neighbors2 = float(np.median(magnitude[:, c + 1:min(cols, c + 3)]))
        neighbor_avg = (neighbors + neighbors2) / 2.0
        if col_mag > threshold and col_mag > neighbor_avg * 1.8:
            high_rows = np.sum(magnitude[:, c] > threshold)
            if high_rows > rows * 0.4:
                v_bounds.append(c)

    is_mosaic = len(h_bounds) > 0 or len(v_bounds) > 0

    if is_mosaic:
        parts = []
        if h_bounds:
            parts.append(f"{len(h_bounds)} horizontal")
        if v_bounds:
            parts.append(f"{len(v_bounds)} vertical")
        desc = (
            f"Possible mosaic panel boundaries detected ({', '.join(parts)}). "
            "Sharp gradient discontinuities suggest panel seams. "
            "Consider applying background extraction per-panel before stitching, "
            "or use GraXpert which handles panel boundaries well."
        )
    else:
        desc = "No panel boundaries detected — image appears to be a single exposure."

    return {
        "horizontal_boundaries": h_bounds,
        "vertical_boundaries": v_bounds,
        "is_mosaic": is_mosaic,
        "description": desc,
    }


def save_analysis_json(
    filepath: str,
    metrics: dict,
    complexity_data: dict,
    vignetting_data: dict,
    edge_center_data: dict,
    confidence_data: dict,
    linear_data_info: dict,
    star_density_info: dict,
    gradient_free_info: dict,
    img_width: int,
    img_height: int,
    grid_rows: int,
    grid_cols: int,
    sigma: float,
    lp_color_info: dict | None = None,
    symmetry_info: dict | None = None,
    extended_obj_info: dict | None = None,
    panel_info: dict | None = None,
    hotspot_info: dict | None = None,
    prediction_info: dict | None = None,
) -> str:
    """
    Save analysis results to a JSON sidecar file for later comparison.
    Returns the path of the saved file.
    """
    import json

    data = {
        "version": VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "image": {
            "width": img_width,
            "height": img_height,
        },
        "settings": {
            "grid_rows": grid_rows,
            "grid_cols": grid_cols,
            "sigma": sigma,
        },
        "gradient": {
            "strength_pct": metrics["strength_pct"],
            "angle_deg": metrics["angle_deg"],
            "bg_min": metrics["bg_min"],
            "bg_max": metrics["bg_max"],
            "bg_range": metrics["bg_range"],
            "bg_median": metrics["bg_median"],
            "uniformity": metrics["uniformity"],
        },
        "complexity": {
            "best_degree": complexity_data["best_degree"],
            "r2_by_degree": {str(k): v for k, v in complexity_data["r2_by_degree"].items()},
            "description": complexity_data["description"],
        },
        "vignetting": {
            "radial_r2": vignetting_data["radial_r2"],
            "linear_r2": vignetting_data["linear_r2"],
            "is_vignetting": vignetting_data["is_vignetting"],
            "diagnosis": vignetting_data["diagnosis"],
        },
        "edge_center": {
            "ratio": edge_center_data["ratio"],
            "diagnosis": edge_center_data["diagnosis"],
        },
        "confidence": {
            "score": confidence_data["score"],
            "label": confidence_data["label"],
        },
        "linear_data": {
            "is_linear": linear_data_info["is_linear"],
            "median_level": linear_data_info["median_level"],
        },
        "star_density": {
            "max_rejection": star_density_info["max_rejection"],
            "mean_rejection": star_density_info["mean_rejection"],
            "dense_tile_pct": star_density_info["dense_tile_pct"],
        },
        "gradient_free": {
            "uniform_pct": gradient_free_info["uniform_pct"],
        },
    }

    if lp_color_info is not None:
        data["lp_color"] = {
            "lp_type": lp_color_info["lp_type"],
            "channel_strengths": lp_color_info["channel_strengths"],
        }
    if symmetry_info is not None:
        data["symmetry"] = {
            "max_asymmetry_pct": symmetry_info["max_asymmetry_pct"],
            "is_asymmetric": symmetry_info["is_asymmetric"],
            "diagnosis": symmetry_info["diagnosis"],
        }
    if extended_obj_info is not None:
        data["extended_objects"] = {
            "flagged_count": extended_obj_info["flagged_count"],
            "flagged_pct": extended_obj_info["flagged_pct"],
        }
    if panel_info is not None:
        data["panel_boundaries"] = {
            "is_mosaic": panel_info["is_mosaic"],
        }
    if hotspot_info is not None:
        data["hotspots"] = {
            "count": hotspot_info["count"],
        }
    if prediction_info is not None:
        data["prediction"] = {
            "predicted_strength_pct": prediction_info["predicted_strength_pct"],
            "predicted_reduction_pct": prediction_info["predicted_reduction_pct"],
        }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return filepath


def load_previous_analysis(filepath: str) -> dict | None:
    """
    Load a previously saved analysis JSON file.
    Returns the data dict or None if file doesn't exist or is invalid.
    """
    import json

    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def detect_hotspots(tile_medians: np.ndarray, sigma_threshold: float = 3.0) -> dict:
    """
    Detect outlier tiles whose values deviate significantly from their neighbors.
    These often indicate satellite trails, airplane lights, or sensor artifacts
    that survived stacking.

    Returns dict with:
      - hotspots: list of (row, col, value, neighbor_median) tuples
      - count: number of hotspots detected
      - warning: human-readable message (empty if none)
    """
    rows, cols = tile_medians.shape
    hotspots = []

    for r in range(rows):
        for c in range(cols):
            # Collect neighbors (excluding self)
            r0, r1 = max(0, r - 1), min(rows, r + 2)
            c0, c1 = max(0, c - 1), min(cols, c + 2)
            neighborhood = tile_medians[r0:r1, c0:c1].flatten().tolist()
            # Remove self
            self_idx = (r - r0) * (c1 - c0) + (c - c0)
            if 0 <= self_idx < len(neighborhood):
                neighborhood.pop(self_idx)
            if len(neighborhood) < 3:
                continue

            n_arr = np.array(neighborhood)
            n_med = float(np.median(n_arr))
            n_std = float(np.std(n_arr))
            if n_std < 1e-15:
                continue

            val = float(tile_medians[r, c])
            if abs(val - n_med) > sigma_threshold * n_std:
                hotspots.append((r, c, val, n_med))

    warning = ""
    if len(hotspots) > 0:
        warning = (
            f"{len(hotspots)} tile{'s' if len(hotspots) > 1 else ''} "
            "deviate significantly from neighbors — possible artifacts "
            "(satellite trails, airplane lights, sensor defects). "
            "These may bias the gradient fit if not masked."
        )

    return {
        "hotspots": hotspots,
        "count": len(hotspots),
        "warning": warning,
    }


def predict_improvement(
    tile_medians: np.ndarray,
    bg_model: np.ndarray,
    metrics: dict,
) -> dict:
    """
    Predict gradient strength after polynomial background subtraction.
    Uses the residuals from the background model fit to estimate post-extraction
    gradient strength.

    Returns dict with:
      - predicted_strength_pct: estimated gradient % after subtraction
      - predicted_reduction_pct: percentage reduction in gradient strength
      - residual_std: standard deviation of residuals
      - description: human-readable prediction
    """
    residuals = tile_medians - bg_model
    res_min = float(np.min(residuals))
    res_max = float(np.max(residuals))
    res_range = res_max - res_min
    residual_std = float(np.std(residuals))

    # Always use the ORIGINAL median as the normalization reference.
    # After subtraction, residual median approaches zero, so using it
    # as denominator would produce nonsensically large percentages.
    original_median = metrics["bg_median"]
    if original_median > 1e-15:
        predicted_strength = res_range / original_median * 100.0
    else:
        predicted_strength = 0.0

    original_strength = metrics["strength_pct"]
    if original_strength > 1e-15:
        reduction = (1.0 - predicted_strength / original_strength) * 100.0
    else:
        reduction = 0.0

    reduction = max(0.0, min(100.0, reduction))

    if predicted_strength < 2.0:
        desc = (
            f"Predicted strength after subtraction: {predicted_strength:.1f}% "
            f"(from {original_strength:.1f}%, ~{reduction:.0f}% reduction). "
            "The polynomial fit should bring the background below the uniform threshold."
        )
    elif predicted_strength < original_strength * 0.5:
        desc = (
            f"Predicted strength after subtraction: {predicted_strength:.1f}% "
            f"(from {original_strength:.1f}%, ~{reduction:.0f}% reduction). "
            "Significant improvement expected, but residual gradient may remain. "
            "Consider a second pass or GraXpert for remaining non-polynomial residuals."
        )
    elif reduction < 20.0:
        desc = (
            f"After subsky: {predicted_strength:.1f}% "
            f"(from {original_strength:.1f}%, only ~{reduction:.0f}% reduction). "
            "Polynomial extraction will be essentially ineffective. "
            "The background variation is likely NOT a smooth gradient — check for "
            "sensor artifacts, amp glow, banding, or incomplete calibration. "
            "GraXpert may help, but fixing the root cause is preferred."
        )
    else:
        desc = (
            f"After subsky: {predicted_strength:.1f}% "
            f"(from {original_strength:.1f}%, only ~{reduction:.0f}% reduction). "
            "Polynomial model is a poor fit for this gradient. "
            "Strongly recommend GraXpert or trying a higher degree."
        )

    return {
        "predicted_strength_pct": predicted_strength,
        "predicted_reduction_pct": reduction,
        "residual_std": residual_std,
        "description": desc,
    }


def detect_stacking_edges(
    luminance: np.ndarray,
    grid_rows: int,
    grid_cols: int,
    drop_threshold: float = 0.3,
) -> dict:
    """
    Detect tapered/dark edges from dithering or rotation during stacking.
    Stacked images often have borders where pixel coverage drops, creating
    anomalously dark strips that mimic strong gradients.

    Checks the outermost ring of tiles for values far below the interior.

    Returns dict with:
      - edge_tiles: set of (row, col) tuples identified as stacking artifacts
      - edge_tile_count: number of affected tiles
      - has_stacking_edges: True if edges detected
      - description: human-readable assessment
    """
    h, w = luminance.shape
    tile_h = h // grid_rows
    tile_w = w // grid_cols

    # Quick per-tile median for edge vs interior comparison
    edge_vals = []
    interior_vals = []
    edge_coords = []

    for r in range(grid_rows):
        for c in range(grid_cols):
            y0 = r * tile_h
            y1 = (r + 1) * tile_h if r < grid_rows - 1 else h
            x0 = c * tile_w
            x1 = (c + 1) * tile_w if c < grid_cols - 1 else w
            tile = luminance[y0:y1, x0:x1]
            med = float(np.median(tile))

            is_edge = (r == 0 or r == grid_rows - 1 or c == 0 or c == grid_cols - 1)
            if is_edge:
                edge_vals.append(med)
                edge_coords.append((r, c))
            else:
                interior_vals.append(med)

    if not interior_vals or not edge_vals:
        return {
            "edge_tiles": set(), "edge_tile_count": 0,
            "has_stacking_edges": False,
            "description": "Grid too small for edge detection",
        }

    interior_med = float(np.median(interior_vals))
    if interior_med < 1e-15:
        return {
            "edge_tiles": set(), "edge_tile_count": 0,
            "has_stacking_edges": False,
            "description": "Image appears empty",
        }

    # Flag edge tiles significantly darker than interior
    flagged = set()
    for (r, c), val in zip(edge_coords, edge_vals):
        if val < interior_med * (1.0 - drop_threshold):
            flagged.add((r, c))

    has_edges = len(flagged) > len(edge_coords) * 0.3  # More than 30% of edge tiles affected

    if has_edges:
        desc = (
            f"{len(flagged)} edge tiles ({len(flagged) / len(edge_coords) * 100:.0f}%) "
            "are significantly darker than the interior. This pattern is typical of "
            "dithered or rotated stacks with incomplete border coverage. "
            "These tiles are excluded from the gradient fit to avoid bias."
        )
    else:
        desc = "No stacking edge artifacts detected."

    return {
        "edge_tiles": flagged,
        "edge_tile_count": len(flagged),
        "has_stacking_edges": has_edges,
        "description": desc,
    }


def build_weight_mask(
    tile_medians: np.ndarray,
    extended_tiles: list | None = None,
    hotspot_tiles: list | None = None,
    edge_tiles: set | None = None,
    star_dense_tiles: np.ndarray | None = None,
    star_dense_threshold: float = 50.0,
) -> np.ndarray:
    """
    Build a weight mask for weighted polynomial fitting.
    Tiles flagged as extended objects, hotspots, stacking edges, or
    excessively star-dense get zero weight; all others get weight 1.0.

    Returns array same shape as tile_medians with values 0.0 or 1.0.
    """
    rows, cols = tile_medians.shape
    weights = np.ones((rows, cols), dtype=np.float64)

    if extended_tiles:
        for r, c in extended_tiles:
            weights[r, c] = 0.0

    if hotspot_tiles:
        for r, c, _, _ in hotspot_tiles:
            weights[r, c] = 0.0

    if edge_tiles:
        for r, c in edge_tiles:
            weights[r, c] = 0.0

    if star_dense_tiles is not None:
        weights[star_dense_tiles > star_dense_threshold] = 0.0

    return weights


def detect_banding(tile_medians: np.ndarray, bg_model: np.ndarray) -> dict:
    """
    Detect periodic row/column bias patterns (sensor banding) in residuals.
    CCD/CMOS sensors can have systematic row or column offsets that look like
    gradients but require bias/dark correction, not background extraction.

    Uses FFT on row-median and column-median profiles of the residuals to
    find periodic components.

    Returns dict with:
      - has_row_banding: True if periodic row pattern detected
      - has_col_banding: True if periodic column pattern detected
      - row_period: dominant period in rows (tiles), or None
      - col_period: dominant period in cols (tiles), or None
      - row_amplitude: strength of row banding relative to residual std
      - col_amplitude: strength of column banding relative to residual std
      - description: human-readable assessment
    """
    residuals = tile_medians - bg_model
    rows, cols = residuals.shape

    if rows < 8 or cols < 8:
        return {
            "has_row_banding": False, "has_col_banding": False,
            "row_period": None, "col_period": None,
            "row_amplitude": 0.0, "col_amplitude": 0.0,
            "description": "Grid too small for banding detection (need >= 8x8)",
        }

    residual_std = float(np.std(residuals))
    if residual_std < 1e-15:
        return {
            "has_row_banding": False, "has_col_banding": False,
            "row_period": None, "col_period": None,
            "row_amplitude": 0.0, "col_amplitude": 0.0,
            "description": "Residuals are zero — no banding possible",
        }

    def _detect_periodic(profile: np.ndarray) -> tuple[bool, float | None, float]:
        """Check a 1D profile for periodic patterns via FFT."""
        n = len(profile)
        if n < 6:
            return False, None, 0.0
        # Remove DC component
        profile = profile - np.mean(profile)
        fft = np.abs(np.fft.rfft(profile))
        # Skip DC (index 0) and Nyquist, look for peaks in useful range
        if len(fft) < 3:
            return False, None, 0.0
        fft[0] = 0  # remove DC
        # Only consider periods from 2 tiles to n/2 tiles
        useful = fft[1:n // 2]
        if len(useful) == 0:
            return False, None, 0.0
        peak_idx = int(np.argmax(useful)) + 1  # +1 because we skipped index 0
        peak_amplitude = float(fft[peak_idx])
        # Significance: peak should be > 2x the mean of other components
        other_mean = float(np.mean(np.delete(fft[1:n // 2 + 1], peak_idx - 1))) if len(useful) > 1 else 0.0
        is_periodic = peak_amplitude > max(other_mean * 3.0, residual_std * 0.5)
        period = n / peak_idx if peak_idx > 0 else None
        rel_amplitude = peak_amplitude / residual_std if residual_std > 1e-15 else 0.0
        return is_periodic, period, rel_amplitude

    # Row banding: check median of each row (horizontal stripes)
    row_profile = np.median(residuals, axis=1)
    has_row, row_period, row_amp = _detect_periodic(row_profile)

    # Column banding: check median of each column (vertical stripes)
    col_profile = np.median(residuals, axis=0)
    has_col, col_period, col_amp = _detect_periodic(col_profile)

    parts = []
    if has_row:
        period_str = f" (period ~{row_period:.1f} tiles)" if row_period else ""
        parts.append(f"Row banding detected{period_str}, amplitude {row_amp:.1f}x residual noise")
    if has_col:
        period_str = f" (period ~{col_period:.1f} tiles)" if col_period else ""
        parts.append(f"Column banding detected{period_str}, amplitude {col_amp:.1f}x residual noise")

    if parts:
        desc = (
            " | ".join(parts) + ". "
            "This pattern is typical of sensor readout artifacts (bias/dark residuals). "
            "Background extraction will NOT fix this — check bias and dark calibration."
        )
    else:
        desc = "No periodic banding detected in residuals."

    return {
        "has_row_banding": has_row,
        "has_col_banding": has_col,
        "row_period": row_period,
        "col_period": col_period,
        "row_amplitude": row_amp,
        "col_amplitude": col_amp,
        "description": desc,
    }


def compute_channel_directions(channel_metrics: dict) -> dict:
    """
    Analyze gradient direction per RGB channel to detect LP from
    different compass directions per channel. Different LP sources
    (sodium from south, LED from east) affect channels differently.

    channel_metrics: dict with 'r', 'g', 'b' keys each containing metrics.

    Returns dict with:
      - directions: {R: (angle, compass), G: (angle, compass), B: (angle, compass)}
      - max_direction_spread: largest angular difference between channels
      - has_directional_difference: True if channels have notably different directions
      - description: human-readable assessment
    """
    directions = {}
    angles = []
    for ch_name, ch_key in [("R", "r"), ("G", "g"), ("B", "b")]:
        m = channel_metrics[ch_key]
        angle = m["angle_deg"] % 360.0  # Normalize to [0, 360)
        compass = angle_to_direction(angle)
        directions[ch_name] = (angle, compass)
        angles.append(angle)

    # Compute maximum angular spread (accounting for wrap-around)
    max_spread = 0.0
    for i in range(len(angles)):
        for j in range(i + 1, len(angles)):
            diff = abs(angles[i] - angles[j])
            diff = min(diff, 360.0 - diff)  # Handle wrap-around
            max_spread = max(max_spread, diff)

    has_diff = max_spread > 30.0  # More than 30 degrees apart

    if has_diff:
        ch_parts = [f"{ch}: {angle:.0f}\u00b0 ({compass})" for ch, (angle, compass) in directions.items()]
        desc = (
            f"LP gradient direction differs between channels (spread: {max_spread:.0f}\u00b0). "
            f"{', '.join(ch_parts)}. "
            "This suggests multiple LP sources from different directions. "
            "Per-channel extraction or VeraLux Nox is recommended."
        )
    else:
        desc = (
            f"All channels share similar gradient direction (spread: {max_spread:.0f}\u00b0). "
            "Single LP source likely — standard extraction should work."
        )

    return {
        "directions": directions,
        "max_direction_spread": max_spread,
        "has_directional_difference": has_diff,
        "description": desc,
    }


def compute_cos4_correction(
    tile_medians: np.ndarray,
    focal_ratio: float | None = None,
) -> dict:
    """
    Compute theoretical cos^4 vignetting profile and compare against actual.
    For fast optics (f/2-f/4), significant natural vignetting is expected —
    the script should normalize against this before diagnosing residual gradient.

    If focal_ratio is None, estimates it from the vignetting pattern.

    Returns dict with:
      - cos4_model: 2D array of expected cos^4 falloff (normalized)
      - corrected_medians: tile_medians with cos^4 removed
      - estimated_focal_ratio: estimated f-ratio from pattern
      - corner_falloff_pct: theoretical corner darkening %
      - residual_after_cos4_pct: gradient strength after cos^4 removal
      - description: human-readable assessment
    """
    rows, cols = tile_medians.shape
    xx, yy = _build_normalized_grid(rows, cols)
    xx = xx.reshape(rows, cols)
    yy = yy.reshape(rows, cols)

    # Distance from center (normalized so corner = sqrt(2))
    r = np.sqrt(xx**2 + yy**2)

    # If no focal ratio given, estimate from edge-to-center ratio
    center = tile_medians[rows // 4:3 * rows // 4, cols // 4:3 * cols // 4]
    center_med = float(np.median(center))
    corner_vals = [
        tile_medians[0, 0], tile_medians[0, -1],
        tile_medians[-1, 0], tile_medians[-1, -1],
    ]
    corner_med = float(np.median(corner_vals))

    if center_med < 1e-15:
        return {
            "cos4_model": np.ones_like(tile_medians),
            "corrected_medians": tile_medians,
            "estimated_focal_ratio": None,
            "corner_falloff_pct": 0.0,
            "residual_after_cos4_pct": 0.0,
            "description": "Image too dark for cos^4 analysis",
        }

    actual_falloff = corner_med / center_med

    # cos^4(theta) where theta = arctan(r / (2*f_ratio)) for sensor diagonal
    # For normalized coords, r_corner ~ sqrt(2), so we fit the exponent
    # Simplified: model = cos^4(k * r) where k is related to FOV
    # Estimate k from actual corner falloff
    r_corner = float(np.max(r))
    if actual_falloff > 0.01 and actual_falloff < 1.0:
        # cos^4(k * r_corner) = actual_falloff => k = arccos(actual_falloff^0.25) / r_corner
        k = float(np.arccos(actual_falloff ** 0.25)) / max(r_corner, 0.01)
    else:
        k = 0.0

    cos4_model = np.cos(k * r) ** 4
    cos4_model = cos4_model / np.max(cos4_model)  # Normalize peak to 1.0

    # Correct tile medians by dividing out cos^4
    corrected = tile_medians / np.maximum(cos4_model, 0.01)

    # Compute residual gradient after cos^4 removal
    corr_min = float(np.min(corrected))
    corr_max = float(np.max(corrected))
    corr_med = float(np.median(corrected))
    residual_pct = (corr_max - corr_min) / max(corr_med, 1e-15) * 100.0

    corner_falloff_pct = (1.0 - actual_falloff) * 100.0

    # Estimate focal ratio (very rough): f/2 ~ 30% falloff, f/4 ~ 8%, f/8 ~ 2%
    if corner_falloff_pct > 20:
        est_f = 2.0
    elif corner_falloff_pct > 10:
        est_f = 3.0
    elif corner_falloff_pct > 5:
        est_f = 4.0
    elif corner_falloff_pct > 2:
        est_f = 6.0
    else:
        est_f = 8.0

    if focal_ratio is not None:
        est_f = focal_ratio

    if corner_falloff_pct > 8.0:
        desc = (
            f"Corner falloff: {corner_falloff_pct:.1f}% (estimated ~f/{est_f:.0f}). "
            f"After cos\u2074 correction, residual gradient: {residual_pct:.1f}%. "
            f"{'Significant residual remains — true gradient or incomplete flat correction.' if residual_pct > 3.0 else 'Most variation is natural vignetting — flats should correct this.'}"
        )
    else:
        desc = (
            f"Corner falloff: {corner_falloff_pct:.1f}% — minimal natural vignetting. "
            f"Cos\u2074 correction not significant for this optical setup."
        )

    return {
        "cos4_model": cos4_model,
        "corrected_medians": corrected,
        "estimated_focal_ratio": est_f,
        "corner_falloff_pct": corner_falloff_pct,
        "residual_after_cos4_pct": residual_pct,
        "description": desc,
    }


def estimate_tile_fwhm(
    tile_data: np.ndarray,
    sigma_clip: float = 2.5,
) -> dict:
    """
    Estimate FWHM and eccentricity from a single tile using peak detection.
    Finds bright point sources and estimates their half-width.

    Returns dict with:
      - fwhm: estimated FWHM in pixels (or None if no stars found)
      - eccentricity: estimated elongation (0 = round, 1 = line) (or None)
      - star_count: number of stars detected
    """
    data = tile_data.astype(np.float64)
    med = np.median(data)
    std = np.std(data)
    if std < 1e-15:
        return {"fwhm": None, "eccentricity": None, "star_count": 0}

    # Threshold for star detection
    threshold = med + sigma_clip * std
    # Find local maxima above threshold
    from scipy.ndimage import label, maximum_filter

    local_max = maximum_filter(data, size=5)
    peaks = (data == local_max) & (data > threshold)
    labeled, n_stars = label(peaks)

    if n_stars == 0:
        return {"fwhm": None, "eccentricity": None, "star_count": 0}

    fwhms = []
    eccentricities = []

    for star_idx in range(1, min(n_stars + 1, 20)):  # Limit to 20 stars
        ys, xs = np.where(labeled == star_idx)
        if len(ys) == 0:
            continue
        cy, cx = int(np.mean(ys)), int(np.mean(xs))

        # Extract small stamp around peak
        stamp_r = 8
        y0, y1 = max(0, cy - stamp_r), min(data.shape[0], cy + stamp_r + 1)
        x0, x1 = max(0, cx - stamp_r), min(data.shape[1], cx + stamp_r + 1)
        stamp = data[y0:y1, x0:x1] - med

        if stamp.size < 9:
            continue

        peak_val = float(np.max(stamp))
        if peak_val < 1e-15:
            continue

        half_max = peak_val / 2.0

        # FWHM from horizontal and vertical profiles through peak
        py, px = np.unravel_index(np.argmax(stamp), stamp.shape)

        # Horizontal profile
        h_profile = stamp[py, :]
        h_above = np.where(h_profile >= half_max)[0]
        fwhm_x = float(h_above[-1] - h_above[0]) if len(h_above) >= 2 else 2.0

        # Vertical profile
        v_profile = stamp[:, px]
        v_above = np.where(v_profile >= half_max)[0]
        fwhm_y = float(v_above[-1] - v_above[0]) if len(v_above) >= 2 else 2.0

        fwhm = (fwhm_x + fwhm_y) / 2.0
        fwhms.append(fwhm)

        # Eccentricity: 0 = circular, approaching 1 = elongated
        if max(fwhm_x, fwhm_y) > 0:
            ecc = 1.0 - min(fwhm_x, fwhm_y) / max(fwhm_x, fwhm_y)
            eccentricities.append(ecc)

    if not fwhms:
        return {"fwhm": None, "eccentricity": None, "star_count": n_stars}

    return {
        "fwhm": float(np.median(fwhms)),
        "eccentricity": float(np.median(eccentricities)) if eccentricities else None,
        "star_count": n_stars,
    }


def compute_fwhm_map(
    luminance: np.ndarray,
    grid_rows: int,
    grid_cols: int,
    sigma: float = 2.5,
) -> dict:
    """
    Compute a coarse FWHM and eccentricity map across the image.
    Returns maps showing how star shape varies spatially — correlations
    with gradient pattern indicate optical issues vs LP.

    Returns dict with:
      - fwhm_map: 2D array (grid_rows, grid_cols) of median FWHM per tile
      - eccentricity_map: 2D array of eccentricity per tile
      - star_count_map: 2D array of star counts per tile
      - median_fwhm: overall median FWHM
      - median_eccentricity: overall median eccentricity
      - fwhm_variation_pct: FWHM variation across field (%)
      - has_tilt: True if eccentricity pattern suggests sensor tilt
      - description: human-readable assessment
    """
    h, w = luminance.shape
    tile_h = h // grid_rows
    tile_w = w // grid_cols

    fwhm_map = np.full((grid_rows, grid_cols), np.nan)
    ecc_map = np.full((grid_rows, grid_cols), np.nan)
    star_map = np.zeros((grid_rows, grid_cols), dtype=int)

    for r in range(grid_rows):
        for c in range(grid_cols):
            y0 = r * tile_h
            y1 = (r + 1) * tile_h if r < grid_rows - 1 else h
            x0 = c * tile_w
            x1 = (c + 1) * tile_w if c < grid_cols - 1 else w
            tile = luminance[y0:y1, x0:x1]

            result = estimate_tile_fwhm(tile, sigma)
            # Require minimum 3 stars for reliable FWHM/eccentricity
            if result["fwhm"] is not None and result["star_count"] >= 3:
                fwhm_map[r, c] = result["fwhm"]
            if result["eccentricity"] is not None and result["star_count"] >= 3:
                ecc_map[r, c] = result["eccentricity"]
            star_map[r, c] = result["star_count"]

    # Compute statistics (ignoring NaN tiles)
    valid_fwhm = fwhm_map[~np.isnan(fwhm_map)]
    valid_ecc = ecc_map[~np.isnan(ecc_map)]

    # Remove extreme FWHM outliers (> 3 sigma from median) that are likely noise
    if len(valid_fwhm) > 4:
        fwhm_med = float(np.median(valid_fwhm))
        fwhm_std = float(np.std(valid_fwhm))
        if fwhm_std > 0:
            fwhm_mask = np.abs(fwhm_map - fwhm_med) > 3 * fwhm_std
            fwhm_map[fwhm_mask & ~np.isnan(fwhm_map)] = np.nan
            valid_fwhm = fwhm_map[~np.isnan(fwhm_map)]
    if len(valid_ecc) > 4:
        ecc_med = float(np.median(valid_ecc))
        ecc_std = float(np.std(valid_ecc))
        if ecc_std > 0:
            ecc_mask = np.abs(ecc_map - ecc_med) > 3 * ecc_std
            ecc_map[ecc_mask & ~np.isnan(ecc_map)] = np.nan
            valid_ecc = ecc_map[~np.isnan(ecc_map)]

    if len(valid_fwhm) < 4:
        return {
            "fwhm_map": fwhm_map, "eccentricity_map": ecc_map,
            "star_count_map": star_map,
            "median_fwhm": None, "median_eccentricity": None,
            "fwhm_variation_pct": 0.0,
            "has_tilt": False,
            "description": "Too few stars detected for FWHM mapping",
        }

    med_fwhm = float(np.median(valid_fwhm))
    med_ecc = float(np.median(valid_ecc)) if len(valid_ecc) > 0 else 0.0
    fwhm_var = (float(np.max(valid_fwhm)) - float(np.min(valid_fwhm))) / max(med_fwhm, 1e-15) * 100.0

    # Check for tilt: eccentricity should increase toward edges/corners
    # and have a consistent direction
    has_tilt = False
    if len(valid_ecc) > 4:
        center_ecc = ecc_map[grid_rows // 4:3 * grid_rows // 4, grid_cols // 4:3 * grid_cols // 4]
        center_ecc = center_ecc[~np.isnan(center_ecc)]
        edge_ecc_vals = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                if not np.isnan(ecc_map[r, c]):
                    if r < 2 or r >= grid_rows - 2 or c < 2 or c >= grid_cols - 2:
                        edge_ecc_vals.append(ecc_map[r, c])
        if len(center_ecc) > 0 and len(edge_ecc_vals) > 0:
            has_tilt = float(np.median(edge_ecc_vals)) > float(np.median(center_ecc)) + 0.1

    parts = [f"Median FWHM: {med_fwhm:.1f} px"]
    if med_ecc > 0.15:
        ecc_note = f"eccentricity: {med_ecc:.2f} (stars are elongated)"
        if med_ecc >= 0.40:
            ecc_note += " — NOTE: very high values at coarse tile resolution may reflect noise or nebulosity, not true star elongation"
        parts.append(ecc_note)
    if fwhm_var > 30:
        parts.append(f"FWHM varies {fwhm_var:.0f}% across field")
    if has_tilt:
        parts.append("edge elongation suggests sensor tilt or field curvature")

    if has_tilt or fwhm_var > 50:
        desc = (
            f"{'. '.join(parts)}. Optical aberrations correlate with the gradient — "
            "consider mechanical adjustment (collimation, tilt, spacing) rather than "
            "relying solely on software extraction."
        )
    elif fwhm_var > 30:
        desc = (
            f"{'. '.join(parts)}. Some optical variation across the field, but within "
            "acceptable range for most setups."
        )
    else:
        desc = f"{'. '.join(parts)}. Star shapes are consistent across the field."

    return {
        "fwhm_map": fwhm_map,
        "eccentricity_map": ecc_map,
        "star_count_map": star_map,
        "median_fwhm": med_fwhm,
        "median_eccentricity": med_ecc,
        "fwhm_variation_pct": fwhm_var,
        "has_tilt": has_tilt,
        "description": desc,
    }


def detect_normalization(image_data: np.ndarray) -> dict:
    """
    Detect whether the image has been background-normalized during stacking.
    Normalized images have artificially uniform backgrounds which can mask
    residual gradients and mislead the analysis.

    Checks for:
    - Very tight background distribution (suspiciously uniform)
    - Background values centered near a common normalization target
    - Per-channel backgrounds at identical levels (multichannel normalization)

    Returns dict with:
      - is_normalized: True if normalization detected
      - evidence: list of clues found
      - description: human-readable assessment
    """
    evidence = []

    if image_data.ndim == 3 and image_data.shape[0] == 3:
        # Multi-channel: check if per-channel backgrounds are suspiciously equal
        ch_medians = []
        for ch in range(3):
            # Sample center region for background estimate
            h, w = image_data.shape[1], image_data.shape[2]
            center = image_data[ch, h // 4:3 * h // 4, w // 4:3 * w // 4]
            ch_medians.append(float(np.median(center)))

        spread = max(ch_medians) - min(ch_medians)
        mean_bg = float(np.mean(ch_medians))

        if mean_bg > 1e-15 and spread / mean_bg < 0.005:
            evidence.append(
                f"Per-channel backgrounds nearly identical "
                f"(R={ch_medians[0]:.6f}, G={ch_medians[1]:.6f}, B={ch_medians[2]:.6f}, "
                f"spread={spread:.6f}) — typical of background normalization"
            )

    # Check luminance for tight distribution
    if image_data.ndim == 3:
        lum = (LUMINANCE_R * image_data[0] + LUMINANCE_G * image_data[1] + LUMINANCE_B * image_data[2]).astype(np.float32) \
            if image_data.shape[0] == 3 else image_data[0].astype(np.float32)
    else:
        lum = image_data.astype(np.float32)

    h, w = lum.shape
    # Sample sparse pixels for speed
    step = max(1, h * w // 100000)
    sample = lum.flatten()[::step]
    bg_std = float(np.std(sample))
    bg_med = float(np.median(sample))

    if bg_med > 1e-15:
        cv = bg_std / bg_med * 100.0
        if cv < 0.5 and bg_med < 0.3:
            evidence.append(
                f"Background CV is extremely low ({cv:.2f}%) — "
                "suspiciously uniform for a real sky background"
            )

    # Check for common normalization targets
    common_targets = [0.0, 0.1, 0.15, 0.2, 0.25]
    for target in common_targets:
        if abs(bg_med - target) < 0.005:
            evidence.append(
                f"Background median ({bg_med:.4f}) is near common "
                f"normalization target {target}"
            )
            break

    is_normalized = len(evidence) >= 1

    if is_normalized:
        desc = (
            "Image appears background-normalized. Evidence: "
            + "; ".join(evidence) + ". "
            "Gradient measurements on normalized data may underestimate the true gradient. "
            "For best results, analyze before background normalization is applied."
        )
    else:
        desc = "No signs of background normalization detected."

    return {
        "is_normalized": is_normalized,
        "evidence": evidence,
        "description": desc,
    }


def detect_residual_pattern(tile_medians: np.ndarray, bg_model: np.ndarray) -> dict:
    """
    Check if polynomial residuals show spatial structure (autocorrelation).
    Structured residuals mean the polynomial degree is insufficient.
    Random-looking residuals mean the fit is adequate.

    Uses Moran's I spatial autocorrelation on the residual grid.

    Returns dict with:
      - morans_i: spatial autocorrelation coefficient (-1 to 1, 0 = random)
      - has_structure: True if significant structure detected
      - row_autocorr: mean autocorrelation along rows
      - col_autocorr: mean autocorrelation along columns
      - description: human-readable assessment
    """
    residuals = tile_medians - bg_model
    rows, cols = residuals.shape

    if rows < 4 or cols < 4:
        return {
            "morans_i": 0.0, "has_structure": False,
            "row_autocorr": 0.0, "col_autocorr": 0.0,
            "description": "Grid too small for residual pattern analysis",
        }

    # Compute lag-1 autocorrelation along rows and columns
    res_flat = residuals.flatten()
    mean_r = float(np.mean(res_flat))
    var_r = float(np.var(res_flat))
    if var_r < 1e-20:
        return {
            "morans_i": 0.0, "has_structure": False,
            "row_autocorr": 0.0, "col_autocorr": 0.0,
            "description": "Residuals are zero — perfect polynomial fit",
        }

    # Row autocorrelation: correlation of each tile with its right neighbor
    row_pairs = residuals[:, :-1].flatten()
    row_shift = residuals[:, 1:].flatten()
    row_autocorr = float(np.corrcoef(row_pairs, row_shift)[0, 1]) if len(row_pairs) > 2 else 0.0

    # Column autocorrelation: correlation of each tile with its below neighbor
    col_pairs = residuals[:-1, :].flatten()
    col_shift = residuals[1:, :].flatten()
    col_autocorr = float(np.corrcoef(col_pairs, col_shift)[0, 1]) if len(col_pairs) > 2 else 0.0

    # Simplified Moran's I: average of row and column autocorrelation
    morans_i = (row_autocorr + col_autocorr) / 2.0

    # Handle NaN from corrcoef
    if np.isnan(morans_i):
        morans_i = 0.0
    if np.isnan(row_autocorr):
        row_autocorr = 0.0
    if np.isnan(col_autocorr):
        col_autocorr = 0.0

    has_structure = abs(morans_i) > 0.3

    if has_structure and morans_i > 0.5:
        desc = (
            f"Strong spatial structure in residuals (I={morans_i:.2f}). "
            "The polynomial degree is too low — residuals show correlated patterns. "
            "Increase degree or switch to GraXpert for non-polynomial extraction."
        )
    elif has_structure:
        desc = (
            f"Moderate spatial structure in residuals (I={morans_i:.2f}). "
            "Some gradient pattern remains after polynomial subtraction. "
            "Consider increasing the polynomial degree by 1."
        )
    else:
        desc = (
            f"Residuals appear random (I={morans_i:.2f}). "
            "The polynomial fit adequately captures the gradient structure."
        )

    return {
        "morans_i": morans_i,
        "has_structure": has_structure,
        "row_autocorr": row_autocorr,
        "col_autocorr": col_autocorr,
        "description": desc,
    }


def suggest_sigma(star_density_info: dict, current_sigma: float) -> dict:
    """
    Suggest an optimal sigma-clip value based on star density analysis.
    Dense star fields need higher sigma to avoid over-clipping background.

    Returns dict with:
      - suggested_sigma: recommended sigma value
      - reason: explanation
      - needs_change: True if suggestion differs from current
    """
    dense_pct = star_density_info.get("dense_tile_pct", 0.0)
    max_rej = star_density_info.get("max_rejection", 0.0)

    if dense_pct > 30 and current_sigma < 3.0:
        suggested = 3.5
        reason = (
            f"Dense star field detected ({dense_pct:.0f}% tiles with high rejection). "
            f"Current sigma {current_sigma:.1f} is too aggressive — "
            f"recommend sigma {suggested:.1f} to preserve background accuracy."
        )
    elif dense_pct > 10 and current_sigma < 2.5:
        suggested = 3.0
        reason = (
            f"Moderately dense star field ({dense_pct:.0f}% high rejection). "
            f"Recommend sigma {3.0:.1f} for better background estimates."
        )
    elif max_rej < 10 and current_sigma > 3.0:
        suggested = 2.5
        reason = (
            f"Low star density (max rejection {max_rej:.0f}%). "
            f"Current sigma {current_sigma:.1f} is conservative — "
            f"sigma {2.5:.1f} would give tighter clipping and more precise background."
        )
    else:
        suggested = current_sigma
        reason = f"Current sigma {current_sigma:.1f} is appropriate for this star density."

    return {
        "suggested_sigma": suggested,
        "reason": reason,
        "needs_change": abs(suggested - current_sigma) > 0.05,
    }


def save_history_entry(
    history_path: str,
    metrics: dict,
    complexity_data: dict,
    timestamp: str | None = None,
) -> list:
    """
    Append a gradient analysis entry to the history log file.
    Returns the updated history list.
    """
    import json

    history = []
    if os.path.isfile(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []

    entry = {
        "timestamp": timestamp or datetime.datetime.now().isoformat(),
        "strength_pct": metrics["strength_pct"],
        "uniformity": metrics["uniformity"],
        "bg_range": metrics["bg_range"],
        "best_degree": complexity_data["best_degree"],
    }
    history.append(entry)

    # Keep last 50 entries to avoid unbounded growth
    if len(history) > 50:
        history = history[-50:]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return history


def analyze_single_fits(
    filepath: str,
    grid_rows: int = 12,
    grid_cols: int = 12,
    sigma: float = 2.5,
) -> dict | None:
    """
    Analyze a single FITS file for gradient strength without Siril.
    Used for batch sub-frame ranking.

    Returns dict with filepath, strength_pct, uniformity, bg_range, or None on error.
    """
    try:
        from astropy.io import fits as afits
    except ImportError:
        return None  # Cannot read FITS without astropy

    try:
        with afits.open(filepath, memmap=True) as hdul:
            data = hdul[0].data
            if data is None:
                return None
            data = data.astype(np.float32)

            # Handle multi-channel: convert to luminance
            if data.ndim == 3:
                if data.shape[0] == 3:
                    lum = (LUMINANCE_R * data[0] + LUMINANCE_G * data[1] + LUMINANCE_B * data[2])
                else:
                    lum = data[0]
            elif data.ndim == 2:
                lum = data
            else:
                return None

            # Normalize to [0, 1] if needed
            dmax = float(np.max(lum))
            if dmax > 2.0:
                lum = lum / max(dmax, 1.0)

            medians = compute_tile_grid(lum, grid_rows, grid_cols, sigma)
            metrics = compute_gradient_metrics(medians)

            return {
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "strength_pct": metrics["strength_pct"],
                "uniformity": metrics["uniformity"],
                "bg_range": metrics["bg_range"],
                "angle_deg": metrics["angle_deg"],
            }
    except (OSError, ValueError):
        return None


def read_fits_calibration_headers(image_data: np.ndarray) -> dict:
    """
    Read calibration-related FITS header keywords from Siril's loaded image.
    Since sirilpy doesn't expose headers directly, we infer calibration state
    from the image data characteristics and from the working directory for
    FITS files that might contain the headers.

    Also attempts to read the original FITS file from the current working
    directory to extract actual headers.

    Returns dict with:
      - flat_applied: True/False/None (None = unknown)
      - dark_applied: True/False/None
      - bias_applied: True/False/None
      - calibration_keywords: dict of found header values
      - plate_scale: arcsec/pixel if WCS present, else None
      - wcs_rotation: image rotation angle in degrees, else None
      - object_ra: RA string if present, else None
      - object_dec: DEC string if present, else None
      - date_obs: observation date string if present, else None
      - exposure: exposure time in seconds if present, else None
      - focal_length: focal length in mm if present, else None
      - pixel_size: pixel size in microns if present, else None
      - spcc_applied: True if photometric calibration detected, else False
      - description: human-readable calibration status
    """
    result = {
        "flat_applied": None, "dark_applied": None, "bias_applied": None,
        "calibration_keywords": {},
        "plate_scale": None, "wcs_rotation": None,
        "object_ra": None, "object_dec": None,
        "date_obs": None, "exposure": None,
        "focal_length": None, "pixel_size": None,
        "spcc_applied": False,
        "description": "No FITS header information available",
    }

    # Try to find and read the FITS file from the working directory
    try:
        from astropy.io import fits as afits
    except ImportError:
        return result

    # Look for common FITS file patterns in cwd
    cwd = os.getcwd()
    fits_candidates = []
    try:
        for f in os.listdir(cwd):
            if f.lower().endswith((".fit", ".fits", ".fts")):
                fits_candidates.append(os.path.join(cwd, f))
    except OSError:
        return result

    if not fits_candidates:
        return result

    # Use the most recently modified FITS file (likely the one loaded in Siril)
    fits_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    fits_path = fits_candidates[0]

    try:
        with afits.open(fits_path, memmap=True) as hdul:
            header = hdul[0].header

            kw = result["calibration_keywords"]

            # Siril calibration keywords
            for key in ("FLATCOR", "DARKCOR", "BIASCOR", "CALSTAT"):
                if key in header:
                    kw[key] = str(header[key])

            # Check CALSTAT (Siril writes "BDF" for Bias+Dark+Flat)
            calstat = kw.get("CALSTAT", "")
            if "F" in calstat.upper():
                result["flat_applied"] = True
            elif "FLATCOR" in kw:
                result["flat_applied"] = True
            if "D" in calstat.upper():
                result["dark_applied"] = True
            elif "DARKCOR" in kw:
                result["dark_applied"] = True
            if "B" in calstat.upper():
                result["bias_applied"] = True
            elif "BIASCOR" in kw:
                result["bias_applied"] = True

            # WCS info
            if "CROTA1" in header or "CROTA2" in header:
                result["wcs_rotation"] = float(header.get("CROTA2", header.get("CROTA1", 0)))
            elif "CD1_1" in header and "CD1_2" in header:
                import math
                cd11 = float(header["CD1_1"])
                cd12 = float(header["CD1_2"])
                result["wcs_rotation"] = math.degrees(math.atan2(cd12, cd11))

            if "CDELT1" in header:
                result["plate_scale"] = abs(float(header["CDELT1"])) * 3600.0  # deg to arcsec
            elif "CD1_1" in header and "CD1_2" in header:
                cd11 = float(header["CD1_1"])
                cd12 = float(header["CD1_2"])
                result["plate_scale"] = (cd11**2 + cd12**2)**0.5 * 3600.0

            # Object coordinates
            for ra_key in ("OBJCTRA", "RA", "CRVAL1"):
                if ra_key in header:
                    result["object_ra"] = str(header[ra_key])
                    break
            for dec_key in ("OBJCTDEC", "DEC", "CRVAL2"):
                if dec_key in header:
                    result["object_dec"] = str(header[dec_key])
                    break

            # Observation metadata
            if "DATE-OBS" in header:
                result["date_obs"] = str(header["DATE-OBS"])
            if "EXPTIME" in header or "EXPOSURE" in header:
                result["exposure"] = float(header.get("EXPTIME", header.get("EXPOSURE", 0)))
            if "FOCALLEN" in header:
                result["focal_length"] = float(header["FOCALLEN"])
            if "XPIXSZ" in header or "PIXSIZE1" in header:
                result["pixel_size"] = float(header.get("XPIXSZ", header.get("PIXSIZE1", 0)))

            # SPCC / photometric calibration detection
            for key in ("PHOTFLAG", "BSCALE", "SPCCCAL"):
                if key in header:
                    kw[key] = str(header[key])
            # Siril SPCC sets specific keywords
            if "SPCCCAL" in kw or header.get("COMMENT", "") and any("SPCC" in str(c) for c in header.get("COMMENT", [])):
                result["spcc_applied"] = True

            # Build description
            parts = []
            if result["flat_applied"] is True:
                parts.append("Flat: applied")
            elif result["flat_applied"] is False:
                parts.append("Flat: NOT applied")
            if result["dark_applied"] is True:
                parts.append("Dark: applied")
            if result["bias_applied"] is True:
                parts.append("Bias: applied")
            if calstat:
                parts.append(f"CALSTAT={calstat}")
            if result["spcc_applied"]:
                parts.append("SPCC: calibrated")
            if not parts:
                parts.append("No calibration keywords found in FITS header")
            result["description"] = " | ".join(parts)

    except (OSError, KeyError, ValueError, TypeError):
        pass

    return result


def compute_geographic_lp_direction(
    gradient_angle_deg: float,
    wcs_rotation: float | None,
    channel_directions: dict | None = None,
) -> dict:
    """
    Convert image gradient direction to geographic compass bearing using WCS rotation.
    The gradient points from darkest to brightest — the brightest direction is where LP comes from.

    gradient_angle_deg: angle from compute_gradient_metrics (image pixel coords)
    wcs_rotation: CROTA2 or equivalent from FITS header (degrees)
    channel_directions: optional per-channel directions dict

    Returns dict with:
      - geographic_bearing: float degrees (0=N, 90=E, 180=S, 270=W)
      - compass: human-readable compass direction
      - confidence: "high" if WCS available, "estimated" if inferred
      - channel_bearings: per-channel geographic bearings if available
      - description: human-readable assessment
    """
    if wcs_rotation is None:
        return {
            "geographic_bearing": None,
            "compass": None,
            "confidence": "unavailable",
            "channel_bearings": None,
            "description": "No WCS rotation in FITS header — cannot determine geographic LP direction. "
                           "Plate-solve the image first for geographic LP source identification.",
        }

    # Convert image angle to geographic: subtract WCS rotation
    # Image angle: 0=right, 90=up. Geographic: 0=N, 90=E
    # WCS rotation (CROTA2) is the angle from N through E
    geo_bearing = (gradient_angle_deg - wcs_rotation + 360.0) % 360.0

    def _bearing_to_compass(b: float) -> str:
        dirs = [
            (22.5, "N"), (67.5, "NE"), (112.5, "E"), (157.5, "SE"),
            (202.5, "S"), (247.5, "SW"), (292.5, "W"), (337.5, "NW"),
            (360.0, "N"),
        ]
        for upper, name in dirs:
            if b < upper:
                return name
        return "N"

    compass = _bearing_to_compass(geo_bearing)

    # Per-channel geographic bearings
    ch_bearings = None
    if channel_directions is not None:
        ch_bearings = {}
        for ch_name, (angle, _) in channel_directions.get("directions", {}).items():
            ch_geo = (angle - wcs_rotation + 360.0) % 360.0
            ch_bearings[ch_name] = (ch_geo, _bearing_to_compass(ch_geo))

    ch_desc = ""
    if ch_bearings:
        ch_parts = [f"{ch}: {b:.0f}\u00b0 {c}" for ch, (b, c) in ch_bearings.items()]
        ch_desc = f" Per-channel: {', '.join(ch_parts)}."

    desc = (
        f"Light pollution source is toward geographic {compass} "
        f"({geo_bearing:.0f}\u00b0 bearing).{ch_desc}"
    )

    return {
        "geographic_bearing": geo_bearing,
        "compass": compass,
        "confidence": "high",
        "channel_bearings": ch_bearings,
        "description": desc,
    }


def compute_sky_brightness(
    metrics: dict,
    plate_scale: float | None,
    exposure: float | None,
    spcc_applied: bool = False,
) -> dict:
    """
    Convert gradient measurements to sky brightness in mag/arcsec² if
    sufficient metadata is available (plate scale + exposure time + SPCC calibration).

    For SPCC-calibrated images, pixel values are proportional to flux, enabling
    approximate magnitude estimation.

    Returns dict with:
      - sky_mag_min: brightest sky region in mag/arcsec² (or None)
      - sky_mag_max: darkest sky region in mag/arcsec² (or None)
      - sky_mag_median: median sky brightness (or None)
      - bortle_estimate: estimated Bortle class (or None)
      - has_photometry: True if photometric conversion was possible
      - description: human-readable assessment
    """
    if not spcc_applied or plate_scale is None or exposure is None or exposure <= 0:
        return {
            "sky_mag_min": None, "sky_mag_max": None, "sky_mag_median": None,
            "bortle_estimate": None, "has_photometry": False,
            "description": (
                "Photometric sky brightness requires plate-solved + SPCC-calibrated image "
                "with known exposure time. Missing: "
                + (", ".join(
                    [x for x, v in [
                        ("SPCC calibration", not spcc_applied),
                        ("plate scale", plate_scale is None),
                        ("exposure time", exposure is None or (exposure is not None and exposure <= 0)),
                    ] if v]
                ) or "none")
                + "."
            ),
        }

    # For SPCC-calibrated data, pixel values ≈ flux in ADU/sec (approximately)
    # Convert to surface brightness: mag/arcsec² = -2.5 * log10(flux_per_arcsec2) + zeropoint
    # Without a specific zeropoint, we use relative values and a typical CCD zeropoint
    pixel_area_arcsec2 = plate_scale ** 2  # arcsec² per pixel

    # flux per arcsec² = pixel_value / exposure / pixel_area
    bg_min = metrics["bg_min"]
    bg_max = metrics["bg_max"]
    bg_med = metrics["bg_median"]

    # Rough zeropoint for typical amateur setup (calibrated roughly)
    # This gives order-of-magnitude correct Bortle estimates
    zp = 25.0  # typical instrumental zeropoint

    def _to_mag(flux_val: float) -> float | None:
        if flux_val <= 0:
            return None
        flux_per_arcsec2 = flux_val / max(exposure, 0.001) / max(pixel_area_arcsec2, 0.001)
        if flux_per_arcsec2 <= 0:
            return None
        return float(-2.5 * np.log10(flux_per_arcsec2) + zp)

    mag_min = _to_mag(bg_min)   # darkest = highest mag
    mag_max = _to_mag(bg_max)   # brightest = lowest mag
    mag_med = _to_mag(bg_med)

    # Bortle estimate from median sky brightness
    bortle = None
    if mag_med is not None:
        if mag_med > 21.7:
            bortle = 1
        elif mag_med > 21.3:
            bortle = 2
        elif mag_med > 20.8:
            bortle = 3
        elif mag_med > 20.3:
            bortle = 4
        elif mag_med > 19.5:
            bortle = 5
        elif mag_med > 18.9:
            bortle = 6
        elif mag_med > 18.3:
            bortle = 7
        elif mag_med > 17.5:
            bortle = 8
        else:
            bortle = 9

    parts = []
    if mag_med is not None:
        parts.append(f"Median sky: ~{mag_med:.1f} mag/arcsec\u00b2")
    if mag_min is not None and mag_max is not None:
        parts.append(f"range {mag_max:.1f} (brightest) to {mag_min:.1f} (darkest)")
    if bortle is not None:
        parts.append(f"estimated Bortle {bortle}")

    desc = " | ".join(parts) if parts else "Could not compute sky brightness."
    desc += " (approximate — based on SPCC calibration and estimated zeropoint)"

    return {
        "sky_mag_min": mag_min,
        "sky_mag_max": mag_max,
        "sky_mag_median": mag_med,
        "bortle_estimate": bortle,
        "has_photometry": mag_med is not None,
        "description": desc,
    }


def detect_dew_frost(
    fwhm_data: dict | None,
    vignetting_data: dict,
    tile_medians: np.ndarray,
) -> dict:
    """
    Detect dew or frost on corrector plate / front lens element.
    Dew manifests as:
    1. Radial FWHM increase from center outward (scattering)
    2. A soft radial bright component that's NOT vignetting (bright center, dim edges)
    3. Combined: bright center + blurred edges is the signature

    Returns dict with:
      - has_dew: True if dew/frost pattern detected
      - fwhm_radial_increase: FWHM increase ratio (edge/center)
      - brightness_pattern: "bright_center" / "normal" / "vignetting"
      - confidence: "high" / "medium" / "low"
      - description: human-readable assessment
    """
    if fwhm_data is None or fwhm_data.get("median_fwhm") is None:
        return {
            "has_dew": False, "fwhm_radial_increase": None,
            "brightness_pattern": "unknown", "confidence": "low",
            "description": "Insufficient FWHM data for dew/frost analysis",
        }

    fwhm_map = fwhm_data["fwhm_map"]
    rows, cols = fwhm_map.shape

    # Check radial FWHM increase
    center_fwhm = fwhm_map[rows // 4:3 * rows // 4, cols // 4:3 * cols // 4]
    center_fwhm = center_fwhm[~np.isnan(center_fwhm)]

    edge_fwhms = []
    for r in range(rows):
        for c in range(cols):
            if not np.isnan(fwhm_map[r, c]):
                if r < 2 or r >= rows - 2 or c < 2 or c >= cols - 2:
                    edge_fwhms.append(fwhm_map[r, c])

    if len(center_fwhm) < 2 or len(edge_fwhms) < 2:
        return {
            "has_dew": False, "fwhm_radial_increase": None,
            "brightness_pattern": "unknown", "confidence": "low",
            "description": "Not enough stars in center/edges for dew detection",
        }

    center_med_fwhm = float(np.median(center_fwhm))
    edge_med_fwhm = float(np.median(edge_fwhms))

    if center_med_fwhm < 0.1:
        fwhm_ratio = 1.0
    else:
        fwhm_ratio = edge_med_fwhm / center_med_fwhm

    # Check brightness pattern: dew makes center brighter (scattering adds light)
    center_bright = float(np.median(tile_medians[rows // 4:3 * rows // 4, cols // 4:3 * cols // 4]))
    edge_bright = float(np.median(np.concatenate([
        tile_medians[0, :], tile_medians[-1, :],
        tile_medians[:, 0], tile_medians[:, -1],
    ])))

    if center_bright > 1e-15:
        bright_ratio = edge_bright / center_bright
    else:
        bright_ratio = 1.0

    # Dew signature: FWHM increases radially AND center is brighter (not vignetting)
    is_bright_center = bright_ratio < 0.85  # edges significantly darker
    is_fwhm_increase = fwhm_ratio > 1.4  # edges have 40%+ larger FWHM
    is_not_vignetting = not vignetting_data.get("is_vignetting", False) or is_fwhm_increase

    # Dew: bright center + FWHM increase together
    has_dew = is_bright_center and is_fwhm_increase and is_not_vignetting

    if bright_ratio < 0.85:
        bp = "bright_center"
    elif bright_ratio > 1.05:
        bp = "vignetting"
    else:
        bp = "normal"

    if has_dew:
        confidence = "high" if fwhm_ratio > 1.8 and bright_ratio < 0.75 else "medium"
        desc = (
            f"Dew/frost likely detected! Edge FWHM is {fwhm_ratio:.1f}x center FWHM, "
            f"and center is {(1.0 - bright_ratio) * 100:.0f}% brighter than edges. "
            "This pattern of radial FWHM increase + bright center scattering is characteristic "
            "of dew/frost on the corrector plate or front lens. "
            "Check your dew heater and consider discarding affected subs."
        )
    elif is_fwhm_increase and not is_bright_center:
        confidence = "low"
        desc = (
            f"Edge FWHM is {fwhm_ratio:.1f}x center ({edge_med_fwhm:.1f} vs {center_med_fwhm:.1f} px). "
            "Could be field curvature, tilt, or early-stage dew. Monitor across subs."
        )
    else:
        confidence = "low"
        desc = "No dew/frost pattern detected."

    return {
        "has_dew": has_dew,
        "fwhm_radial_increase": fwhm_ratio,
        "brightness_pattern": bp,
        "confidence": confidence,
        "description": desc,
    }


def detect_amp_glow(tile_medians: np.ndarray) -> dict:
    """
    Detect amplifier glow, which appears as a warm (bright) gradient
    concentrated in one specific corner with a characteristic exponential
    falloff. Unlike LP gradients (linear/planar), amp glow is corner-anchored
    and drops off quickly. Unlike vignetting (radial/symmetric), amp glow
    is always in one corner.

    Returns dict with:
      - has_amp_glow: True if amp glow pattern detected
      - affected_corner: "NW"/"NE"/"SW"/"SE" or None
      - glow_strength_pct: excess brightness at the affected corner (%)
      - falloff_rate: how quickly the glow drops off (higher = more localized)
      - description: human-readable assessment
    """
    rows, cols = tile_medians.shape
    if rows < 6 or cols < 6:
        return {
            "has_amp_glow": False, "affected_corner": None,
            "glow_strength_pct": 0.0, "falloff_rate": 0.0,
            "description": "Grid too small for amp glow detection",
        }

    center = tile_medians[rows // 4:3 * rows // 4, cols // 4:3 * cols // 4]
    center_med = float(np.median(center))
    if center_med < 1e-15:
        return {
            "has_amp_glow": False, "affected_corner": None,
            "glow_strength_pct": 0.0, "falloff_rate": 0.0,
            "description": "Image too dark for amp glow analysis",
        }

    # Measure each corner (3x3 block) and its falloff toward center
    corners = {
        "SW": (0, 0),
        "SE": (0, cols - 1),
        "NW": (rows - 1, 0),
        "NE": (rows - 1, cols - 1),
    }

    best_corner = None
    best_excess = 0.0
    best_falloff = 0.0

    for name, (cr, cc) in corners.items():
        # Corner value (3x3 block)
        r0, r1 = max(0, cr - 1), min(rows, cr + 2)
        c0, c1 = max(0, cc - 1), min(cols, cc + 2)
        corner_val = float(np.median(tile_medians[r0:r1, c0:c1]))

        excess = (corner_val - center_med) / center_med * 100.0
        if excess < 3.0:
            continue  # Not bright enough to be amp glow

        # Check falloff: measure brightness at 25%, 50%, 75% distance from corner to center
        center_r, center_c = rows // 2, cols // 2
        falloff_vals = []
        for frac in [0.25, 0.5, 0.75]:
            fr = int(cr + (center_r - cr) * frac)
            fc = int(cc + (center_c - cc) * frac)
            fr = max(0, min(rows - 1, fr))
            fc = max(0, min(cols - 1, fc))
            r0f, r1f = max(0, fr - 1), min(rows, fr + 2)
            c0f, c1f = max(0, fc - 1), min(cols, fc + 2)
            falloff_vals.append(float(np.median(tile_medians[r0f:r1f, c0f:c1f])))

        # Amp glow: rapid falloff (exponential-like)
        # Check that brightness drops quickly from corner
        if len(falloff_vals) >= 3:
            drop_25 = (corner_val - falloff_vals[0]) / max(corner_val - center_med, 1e-15)
            drop_50 = (corner_val - falloff_vals[1]) / max(corner_val - center_med, 1e-15)
            # Exponential: most of the drop happens in the first 25-50%
            falloff_rate = drop_25 + drop_50  # Higher = more localized = more amp-glow-like
        else:
            falloff_rate = 0.0

        if excess > best_excess:
            best_corner = name
            best_excess = excess
            best_falloff = falloff_rate

    # Amp glow: bright corner with rapid falloff, and NOT symmetric (only one corner)
    # Differentiate from LP: LP affects a full edge/side, amp glow is corner-localized
    has_glow = best_excess > 5.0 and best_falloff > 0.8

    # Check asymmetry: opposite corner should NOT have similar brightness
    if has_glow and best_corner is not None:
        opp = {"SW": "NE", "NE": "SW", "NW": "SE", "SE": "NW"}[best_corner]
        opp_r, opp_c = corners[opp]
        r0o, r1o = max(0, opp_r - 1), min(rows, opp_r + 2)
        c0o, c1o = max(0, opp_c - 1), min(cols, opp_c + 2)
        opp_val = float(np.median(tile_medians[r0o:r1o, c0o:c1o]))
        opp_excess = (opp_val - center_med) / center_med * 100.0
        if opp_excess > best_excess * 0.5:
            has_glow = False  # Symmetric brightness — more likely LP or vignetting

    if has_glow:
        desc = (
            f"Amplifier glow detected in {best_corner} corner "
            f"({best_excess:.1f}% above center, falloff rate {best_falloff:.2f}). "
            "Amp glow is a sensor artifact that dark frames should correct. "
            "If darks were applied, they may be insufficient (wrong temperature, "
            "wrong exposure). Background extraction will partially mask this but "
            "the proper fix is better dark calibration."
        )
    else:
        desc = "No amplifier glow pattern detected."

    return {
        "has_amp_glow": has_glow,
        "affected_corner": best_corner if has_glow else None,
        "glow_strength_pct": best_excess,
        "falloff_rate": best_falloff,
        "description": desc,
    }


def analyze_batch_temporal(
    fits_dir: str,
    grid_rows: int = 12,
    grid_cols: int = 12,
    sigma: float = 2.5,
) -> dict:
    """
    Analyze a directory of FITS sub-frames for temporal gradient evolution.
    Correlates gradient strength with DATE-OBS timestamps to identify
    when gradients improve or worsen during a session.

    Returns dict with:
      - entries: list of {filename, date_obs, strength_pct, angle_deg}
      - trend: "improving" / "worsening" / "stable" / "insufficient_data"
      - best_period: time range with lowest gradients
      - worst_period: time range with highest gradients
      - recommendation: human-readable recommendation
      - description: human-readable summary
    """
    try:
        from astropy.io import fits as afits
    except ImportError:
        return {
            "entries": [], "trend": "insufficient_data",
            "best_period": None, "worst_period": None,
            "recommendation": "Install astropy for temporal analysis.",
            "description": "astropy required for FITS temporal analysis",
        }

    entries = []
    for fname in sorted(os.listdir(fits_dir)):
        if not fname.lower().endswith((".fit", ".fits", ".fts")):
            continue
        fpath = os.path.join(fits_dir, fname)
        try:
            with afits.open(fpath, memmap=True) as hdul:
                header = hdul[0].header
                date_obs = str(header.get("DATE-OBS", ""))
                if not date_obs:
                    continue

                data = hdul[0].data
                if data is None:
                    continue
                data = data.astype(np.float32)

                if data.ndim == 3 and data.shape[0] == 3:
                    lum = (LUMINANCE_R * data[0] + LUMINANCE_G * data[1] + LUMINANCE_B * data[2])
                elif data.ndim == 3:
                    lum = data[0]
                elif data.ndim == 2:
                    lum = data
                else:
                    continue

                dmax = float(np.max(lum))
                if dmax > 2.0:
                    lum = lum / max(dmax, 1.0)

                medians = compute_tile_grid(lum, grid_rows, grid_cols, sigma)
                metrics = compute_gradient_metrics(medians)

                entries.append({
                    "filename": fname,
                    "date_obs": date_obs,
                    "strength_pct": metrics["strength_pct"],
                    "angle_deg": metrics["angle_deg"],
                })
        except (OSError, ValueError):
            continue

    if len(entries) < 3:
        return {
            "entries": entries, "trend": "insufficient_data",
            "best_period": None, "worst_period": None,
            "recommendation": "Need at least 3 sub-frames with DATE-OBS for temporal analysis.",
            "description": f"Only {len(entries)} frames with timestamps found",
        }

    # Sort by time
    entries.sort(key=lambda e: e["date_obs"])
    strengths = [e["strength_pct"] for e in entries]

    # Simple trend: linear regression on strength over time
    x = np.arange(len(strengths), dtype=np.float64)
    y = np.array(strengths, dtype=np.float64)
    # Linear fit: y = mx + b
    n = len(x)
    slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / max(n * np.sum(x**2) - np.sum(x)**2, 1e-15)

    if slope < -0.1:
        trend = "improving"
    elif slope > 0.1:
        trend = "worsening"
    else:
        trend = "stable"

    # Find best and worst thirds
    third = max(1, len(entries) // 3)
    first_avg = float(np.mean(strengths[:third]))
    last_avg = float(np.mean(strengths[-third:]))

    best_idx = int(np.argmin(strengths))
    worst_idx = int(np.argmax(strengths))

    best_period = f"{entries[max(0, best_idx - 1)]['date_obs']} to {entries[min(len(entries) - 1, best_idx + 1)]['date_obs']}"
    worst_period = f"{entries[max(0, worst_idx - 1)]['date_obs']} to {entries[min(len(entries) - 1, worst_idx + 1)]['date_obs']}"

    # Recommendation
    if trend == "improving":
        rec = (
            f"Gradient improves over the session (first third avg: {first_avg:.1f}%, "
            f"last third avg: {last_avg:.1f}%). Consider excluding the earliest subs "
            f"(before {entries[third]['date_obs']}) for cleaner stacking."
        )
    elif trend == "worsening":
        rec = (
            f"Gradient worsens over the session (first third avg: {first_avg:.1f}%, "
            f"last third avg: {last_avg:.1f}%). Later subs have stronger LP — "
            f"consider excluding subs after {entries[-third]['date_obs']}."
        )
    else:
        rec = f"Gradient is relatively stable across the session (avg: {float(np.mean(strengths)):.1f}%)."

    desc = (
        f"Analyzed {len(entries)} frames. Trend: {trend} "
        f"(slope: {slope:+.2f}%/frame). "
        f"Range: {min(strengths):.1f}% to {max(strengths):.1f}%."
    )

    return {
        "entries": entries,
        "trend": trend,
        "best_period": best_period,
        "worst_period": worst_period,
        "recommendation": rec,
        "description": desc,
    }


def generate_analysis_report(
    metrics: dict,
    quadrant_data: dict,
    vignetting_data: dict,
    complexity_data: dict,
    edge_center_data: dict,
    confidence_data: dict,
    suggestions: list[str],
    linear_data_info: dict | None = None,
    star_density_info: dict | None = None,
    lp_color_info: dict | None = None,
    symmetry_info: dict | None = None,
    gradient_free_info: dict | None = None,
    extended_obj_info: dict | None = None,
    prediction_info: dict | None = None,
    banding_info: dict | None = None,
    cos4_info: dict | None = None,
    stacking_edge_info: dict | None = None,
    fwhm_data: dict | None = None,
    channel_direction_info: dict | None = None,
    normalization_info: dict | None = None,
    fits_header_info: dict | None = None,
    geo_direction_info: dict | None = None,
    sky_brightness_info: dict | None = None,
    dew_info: dict | None = None,
    amp_glow_info: dict | None = None,
    img_width: int = 0,
    img_height: int = 0,
    grid_rows: int = 16,
    grid_cols: int = 16,
    sigma: float = 2.5,
) -> str:
    """
    Generate a comprehensive plain-text analysis report suitable for
    export, forum posting, or documentation.

    Returns a formatted multi-line string.
    """
    lines = []
    sep = "=" * 72
    subsep = "-" * 40

    lines.append(sep)
    lines.append(f"  GRADIENT ANALYZER REPORT  v{VERSION}")
    lines.append(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(sep)
    lines.append("")

    # Image info
    lines.append("IMAGE INFORMATION")
    lines.append(subsep)
    lines.append(f"  Dimensions: {img_width} x {img_height} px")
    lines.append(f"  Analysis grid: {grid_rows} x {grid_cols} tiles")
    lines.append(f"  Sigma-clip: {sigma:.1f}")
    if fits_header_info is not None:
        if fits_header_info.get("exposure"):
            lines.append(f"  Exposure: {fits_header_info['exposure']:.1f}s")
        if fits_header_info.get("focal_length"):
            lines.append(f"  Focal length: {fits_header_info['focal_length']:.0f}mm")
        if fits_header_info.get("plate_scale"):
            lines.append(f"  Plate scale: {fits_header_info['plate_scale']:.2f}\"/px")
        lines.append(f"  Calibration: {fits_header_info['description']}")
    lines.append("")

    # Gradient metrics
    direction = angle_to_direction(metrics["angle_deg"])
    assessment, _ = get_gradient_assessment(metrics["strength_pct"])
    lines.append("GRADIENT METRICS")
    lines.append(subsep)
    lines.append(f"  Strength: {metrics['strength_pct']:.1f}%  [{assessment}]")
    lines.append(f"  Direction: {metrics['angle_deg']:.1f}\u00b0 ({direction})")
    lines.append(f"  Background: min={metrics['bg_min']:.6f}  max={metrics['bg_max']:.6f}  "
                 f"median={metrics['bg_median']:.6f}")
    lines.append(f"  Uniformity (CV): {metrics['uniformity']:.2f}%")
    lines.append(f"  Confidence: {confidence_data['label']} ({confidence_data['score']:.2f})")
    lines.append(f"  Complexity: {complexity_data['description']}")
    lines.append(f"    Degree 1 R\u00b2={complexity_data['r2_by_degree'][1]:.3f}  "
                 f"Degree 2 R\u00b2={complexity_data['r2_by_degree'][2]:.3f}  "
                 f"Degree 3 R\u00b2={complexity_data['r2_by_degree'][3]:.3f}")

    if geo_direction_info and geo_direction_info.get("compass"):
        lines.append(f"  Geographic LP direction: {geo_direction_info['description']}")
    if sky_brightness_info and sky_brightness_info.get("has_photometry"):
        lines.append(f"  Sky brightness: {sky_brightness_info['description']}")

    # Artifact caveat in report
    _report_has_artifacts = (
        (banding_info and (banding_info.get("has_row_banding") or banding_info.get("has_col_banding")))
        or (amp_glow_info and amp_glow_info.get("has_amp_glow"))
        or (dew_info and dew_info.get("has_dew"))
        or (fits_header_info and fits_header_info.get("flat_applied") is False)
    )
    if _report_has_artifacts and metrics["strength_pct"] >= 5.0:
        lines.append("  NOTE: Gradient % includes artifact contributions (banding, amp glow,")
        lines.append("        missing flats, etc.). True sky gradient may be significantly lower.")
    lines.append("")

    # Diagnostics
    lines.append("DIAGNOSTICS")
    lines.append(subsep)
    lines.append(f"  Vignetting: {vignetting_data['diagnosis']}")
    lines.append(f"  Edge/Center ratio: {edge_center_data['ratio']:.3f} — {edge_center_data['diagnosis']}")
    if linear_data_info and not linear_data_info["is_linear"]:
        lines.append(f"  \u26a0 LINEAR DATA: {linear_data_info['warning']}")
    if symmetry_info:
        lines.append(f"  Symmetry: {symmetry_info['diagnosis']}")
    if gradient_free_info:
        lines.append(f"  Gradient-free area: {gradient_free_info['description']}")
    if star_density_info and star_density_info.get("warning"):
        lines.append(f"  Star density: {star_density_info['warning']}")
    if extended_obj_info and extended_obj_info.get("warning"):
        lines.append(f"  Extended objects: {extended_obj_info['warning']}")
    if lp_color_info:
        lines.append(f"  LP type: {lp_color_info['description']}")
    if channel_direction_info and channel_direction_info.get("has_directional_difference"):
        lines.append(f"  Channel directions: {channel_direction_info['description']}")
    if prediction_info:
        lines.append(f"  Improvement prediction: {prediction_info['description']}")
    lines.append("")

    # v1.7/1.8 diagnostics
    has_issues = False
    issue_lines = []
    if banding_info and (banding_info.get("has_row_banding") or banding_info.get("has_col_banding")):
        issue_lines.append(f"  \u26a0 Banding: {banding_info['description']}")
        has_issues = True
    if stacking_edge_info and stacking_edge_info.get("has_stacking_edges"):
        issue_lines.append(f"  \u26a0 Stacking edges: {stacking_edge_info['description']}")
        has_issues = True
    if cos4_info and cos4_info.get("corner_falloff_pct", 0) > 5:
        issue_lines.append(f"  Cos\u2074 vignetting: {cos4_info['description']}")
        has_issues = True
    if normalization_info and normalization_info.get("is_normalized"):
        issue_lines.append(f"  \u26a0 Normalization: {normalization_info['description']}")
        has_issues = True
    if dew_info and dew_info.get("has_dew"):
        issue_lines.append(f"  \u26a0 DEW/FROST: {dew_info['description']}")
        has_issues = True
    if amp_glow_info and amp_glow_info.get("has_amp_glow"):
        issue_lines.append(f"  \u26a0 AMP GLOW: {amp_glow_info['description']}")
        has_issues = True
    if fwhm_data and fwhm_data.get("median_fwhm") is not None:
        issue_lines.append(f"  Star shape: {fwhm_data['description']}")

    if issue_lines:
        lines.append("ADDITIONAL DIAGNOSTICS")
        lines.append(subsep)
        lines.extend(issue_lines)
        lines.append("")

    # Quadrant summary
    quads = quadrant_data["quadrants"]
    lines.append("QUADRANT SUMMARY")
    lines.append(subsep)
    lines.append(f"  NW: {quads['NW']:.6f}  |  NE: {quads['NE']:.6f}")
    lines.append(f"  SW: {quads['SW']:.6f}  |  SE: {quads['SE']:.6f}")
    lines.append(f"  Brightest: {quadrant_data['brightest']}  Darkest: {quadrant_data['darkest']}")
    lines.append("")

    # Recommendations
    lines.append("RECOMMENDATIONS")
    lines.append(subsep)
    for sug in suggestions:
        for line in sug.split("\n"):
            lines.append(f"  {line}")
        lines.append("")

    lines.append(sep)
    lines.append(f"  Generated by GradientAnalyzer v{VERSION}")
    lines.append(sep)

    return "\n".join(lines)


def suggest_tool_and_workflow(
    metrics: dict,
    vignetting: dict,
    complexity: dict,
    edge_center: dict,
    confidence: dict,
    channel_metrics: dict | None = None,
    banding_info: dict | None = None,
    amp_glow_info: dict | None = None,
    dew_info: dict | None = None,
    normalization_info: dict | None = None,
    fits_header_info: dict | None = None,
    fwhm_data: dict | None = None,
) -> list[str]:
    """
    Generate tool-specific recommendations with reasoning, including
    subsky, AutoBGE, GraXpert, and VeraLux Nox.
    channel_metrics: optional dict with 'r', 'g', 'b' keys each holding
    a metrics dict from compute_gradient_metrics (per-channel analysis).
    Returns a list of recommendation strings.
    """
    strength = metrics["strength_pct"]
    degree = complexity["best_degree"]
    is_vig = vignetting["is_vignetting"]
    suggestions = []

    # --- Priority 0: Critical calibration/hardware issues that must be fixed first ---
    has_critical = False

    if banding_info and (banding_info.get("has_row_banding") or banding_info.get("has_col_banding")):
        suggestions.append(
            "\u26a0 CRITICAL — Sensor banding detected:\n"
            "  Background extraction will NOT fix row/column banding.\n"
            "  Check your bias and dark calibration before proceeding.\n"
            "  Apply fresh master bias and dark with matching temperature/exposure."
        )
        has_critical = True

    if amp_glow_info and amp_glow_info.get("has_amp_glow"):
        corner = amp_glow_info.get("affected_corner", "?")
        suggestions.append(
            f"\u26a0 CRITICAL — Amplifier glow in {corner} corner:\n"
            "  This is a sensor artifact, not light pollution.\n"
            "  Background extraction will only partially mask it.\n"
            "  Fix: Apply dark frames with matching temperature and exposure.\n"
            "  If darks were already applied, they may be inadequate."
        )
        has_critical = True

    if dew_info and dew_info.get("has_dew"):
        suggestions.append(
            "\u26a0 CRITICAL — Dew/frost detected on optics:\n"
            "  Affected sub-frames should be discarded if possible.\n"
            "  Software correction cannot fully fix scattering from dew.\n"
            "  Check dew heater and consider discarding these subs."
        )
        has_critical = True

    if normalization_info and normalization_info.get("is_normalized"):
        suggestions.append(
            "\u26a0 WARNING — Background normalization detected:\n"
            "  Gradient measurements on normalized data may be unreliable.\n"
            "  For accurate gradient analysis, re-stack without background\n"
            "  normalization and analyze the un-normalized result."
        )

    if fits_header_info and fits_header_info.get("flat_applied") is False:
        suggestions.append(
            "\u26a0 CRITICAL — Flat frames not applied:\n"
            "  Vignetting and dust donuts cannot be corrected without flats.\n"
            "  Apply master flat BEFORE gradient extraction.\n"
            "  Siril: calibrate -flat=master_flat.fit"
        )
        has_critical = True

    # Warn about poor polynomial fit
    best_r2 = max(complexity["r2_by_degree"].values())
    if best_r2 < 0.5 and strength > 5.0:
        suggestions.append(
            f"\u26a0 WARNING — Poor polynomial fit (best R\u00b2={best_r2:.2f}):\n"
            "  No polynomial degree explains more than 50% of the background variation.\n"
            "  This suggests the 'gradient' may be dominated by local anomalies\n"
            "  (hotspots, extended objects, amp glow, banding) rather than a smooth gradient.\n"
            "  Consider fixing the root cause before applying background extraction."
        )

    # Detect chromatic gradient (channels differ significantly)
    chromatic_spread = 0.0
    if channel_metrics is not None:
        ch_strengths = [channel_metrics[ch]["strength_pct"] for ch in ("r", "g", "b")]
        chromatic_spread = max(ch_strengths) - min(ch_strengths)

    # --- Step 0: Confidence warning ---
    if confidence["label"] == "Low":
        suggestions.append(
            f"\u26a0 LOW CONFIDENCE: {confidence['reason']}\n"
            "  Consider increasing grid resolution or adjusting sigma-clip before acting on these results."
        )

    # --- Step 1: Vignetting / flat correction ---
    if is_vig or edge_center["ratio"] < 0.95:
        suggestions.append(
            "STEP 1 — Flat Field Correction (vignetting detected):\n"
            "  Apply master flat before gradient extraction.\n"
            "  Siril: calibrate -flat=master_flat.fit\n"
            "  Then re-analyze to see the remaining gradient."
        )

    # --- Step 2: Tool recommendation based on complexity and strength ---
    if strength < 2.0:
        suggestions.append(
            "RESULT — Background is very uniform. No extraction needed.\n"
            "  Proceed with your processing workflow."
        )
        return suggestions

    # AutoBGE recommendation
    if strength < 8.0 and degree <= 2:
        suggestions.append(
            "OPTION A — Siril AutoBGE (recommended for this gradient):\n"
            "  Automatic background extraction, good for moderate gradients.\n"
            "  Siril: autobackgroundextraction\n"
            "  Fast, no external tools needed. Works well for simple/moderate gradients."
        )

    # subsky recommendation with degree from complexity analysis
    samples = {1: 15, 2: 25, 3: 40}.get(degree, 25)
    subsky_prefix = "AFTER FIXING ISSUES — " if has_critical else ""
    option_label = "A" if (strength >= 8.0 or degree > 2) and not has_critical else "B" if not has_critical else ""
    option_str = f"OPTION {option_label} — " if option_label else ""
    suggestions.append(
        f"{subsky_prefix}{option_str}Siril subsky (polynomial degree {degree}):\n"
        f"  Manual background extraction with polynomial fitting.\n"
        f"  Siril: subsky -degree={degree} -samples={samples}\n"
        f"  Complexity analysis: {complexity['description']}\n"
        f"  Fit quality: degree 1 R\u00b2={complexity['r2_by_degree'][1]:.3f}, "
        f"degree 2 R\u00b2={complexity['r2_by_degree'][2]:.3f}, "
        f"degree 3 R\u00b2={complexity['r2_by_degree'][3]:.3f}"
    )

    # GraXpert recommendation
    if degree >= 3 or strength >= 15.0 or (complexity["r2_by_degree"][3] < 0.8 and strength >= 5.0):
        suggestions.append(
            "OPTION — GraXpert (AI-based, recommended for complex gradients):\n"
            "  Best choice when polynomial fitting cannot fully model the gradient.\n"
            "  GraXpert uses AI to separate background from signal.\n"
            "  Download: https://www.graxpert.com\n"
            "  Especially useful for multi-directional or non-linear gradients\n"
            "  that subsky struggles with."
        )
    elif strength >= 5.0:
        suggestions.append(
            "ALTERNATIVE — GraXpert (AI-based):\n"
            "  If subsky/AutoBGE leaves residual gradients, try GraXpert.\n"
            "  Download: https://www.graxpert.com\n"
            "  AI-based extraction handles complex patterns better than polynomials."
        )

    # VeraLux Nox recommendation — stronger if chromatic gradient detected
    if chromatic_spread > 3.0 and strength >= 3.0:
        ch_detail = ""
        if channel_metrics is not None:
            ch_detail = (
                f"\n  Channel gradients: R={channel_metrics['r']['strength_pct']:.1f}%  "
                f"G={channel_metrics['g']['strength_pct']:.1f}%  "
                f"B={channel_metrics['b']['strength_pct']:.1f}%  "
                f"(spread: {chromatic_spread:.1f}%)"
            )
        suggestions.append(
            "OPTION — VeraLux Nox (RECOMMENDED — chromatic gradient detected):\n"
            "  Specialized light pollution removal script for Siril.\n"
            "  Works on linear data, handles color-dependent LP gradients.\n"
            "  Your RGB channels show significantly different gradient strengths,\n"
            "  which is a strong indicator of chromatic light pollution."
            f"{ch_detail}\n"
            "  Install via Siril's script repository or get from the VeraLux project."
        )
    elif strength >= 5.0:
        suggestions.append(
            "ALTERNATIVE — VeraLux Nox (Siril script):\n"
            "  Specialized light pollution removal script for Siril.\n"
            "  Works on linear data, can handle color-dependent LP gradients.\n"
            "  Enable 'Analyze channels separately' to check for chromatic LP.\n"
            "  Install via Siril's script repository or get from the VeraLux project."
        )

    # --- Step 3: Workflow guidance ---
    workflow_lines = ["WORKFLOW — Recommended order:"]
    step = 1

    # Calibration fixes first (if critical issues detected)
    if has_critical:
        workflow_lines.append(f"  {step}. \u26a0 FIX CALIBRATION ISSUES FIRST (see warnings above)")
        step += 1
        workflow_lines.append(f"  {step}. Re-stack with corrected calibration masters")
        step += 1
        workflow_lines.append(f"  {step}. Re-run Gradient Analyzer on the corrected stack")
        step += 1

    if is_vig or edge_center["ratio"] < 0.95:
        workflow_lines.append(f"  {step}. Apply flat field correction (fixes vignetting)")
        step += 1
        workflow_lines.append(f"  {step}. Re-run Gradient Analyzer to assess remaining gradient")
        step += 1

    if strength >= 2.0:
        if best_r2 < 0.5 and strength > 5.0:
            workflow_lines.append(
                f"  {step}. Investigate anomalies (poor polynomial fit R\u00b2={best_r2:.2f}) — "
                "fix root cause before extraction"
            )
            step += 1
        if strength < 8.0 and degree <= 2 and best_r2 >= 0.5:
            workflow_lines.append(f"  {step}. Try AutoBGE first (autobackgroundextraction)")
        else:
            workflow_lines.append(f"  {step}. Apply subsky -degree={degree} -samples={samples}")
        step += 1
        workflow_lines.append(f"  {step}. Re-run Gradient Analyzer ('Refresh from Siril')")
        step += 1
        workflow_lines.append(f"  {step}. If gradient still > 2%, try GraXpert or increase degree")
        step += 1
        workflow_lines.append(f"  {step}. Once gradient < 2%, proceed with stretching")

    suggestions.append("\n".join(workflow_lines))

    return suggestions


def build_thresholds(preset_name: str | None = None) -> list:
    """Build a GRADIENT_THRESHOLDS list from a preset name."""
    if preset_name and preset_name in THRESHOLD_PRESETS:
        t1, t2, t3 = THRESHOLD_PRESETS[preset_name]
    else:
        t1, t2, t3 = 2.0, 5.0, 15.0
    return [
        (t1, "Very uniform — no extraction needed", "#55aa55"),
        (t2, "Slight gradient — gentle extraction recommended", "#aaaa55"),
        (t3, "Significant gradient — extraction strongly recommended", "#dd8833"),
        (float("inf"), "Strong gradient — aggressive extraction required", "#dd4444"),
    ]


def get_gradient_assessment(
    strength_pct: float,
    thresholds: list | None = None,
) -> tuple[str, str]:
    """Return (assessment text, color hex) for a given gradient strength."""
    thr = thresholds or GRADIENT_THRESHOLDS
    for threshold, text, color in thr:
        if strength_pct < threshold:
            return text, color
    return thr[-1][1], thr[-1][2]


def angle_to_direction(angle_deg: float) -> str:
    """Convert angle in degrees to compass direction string."""
    a = angle_deg % 360
    directions = [
        (22.5, "E"), (67.5, "NE"), (112.5, "N"), (157.5, "NW"),
        (202.5, "W"), (247.5, "SW"), (292.5, "S"), (337.5, "SE"),
        (360.0, "E"),
    ]
    for upper, name in directions:
        if a < upper:
            return name
    return "E"


def auto_stretch(image_2d: np.ndarray, clip_low: float = 0.5, clip_high: float = 99.5) -> np.ndarray:
    """
    Auto-stretch a 2D image to [0, 1] range using percentile clipping.
    Produces a visually useful grayscale representation for underlay display.
    """
    lo = np.percentile(image_2d, clip_low)
    hi = np.percentile(image_2d, clip_high)
    if hi - lo < 1e-15:
        return np.zeros_like(image_2d, dtype=np.float32)
    stretched = (image_2d.astype(np.float64) - lo) / (hi - lo)
    return np.clip(stretched, 0.0, 1.0).astype(np.float32)


# ------------------------------------------------------------------------------
# MATPLOTLIB WIDGETS
# ------------------------------------------------------------------------------

_MPL_CACHE: tuple | None | bool = False


def _get_matplotlib() -> tuple | None:
    global _MPL_CACHE
    if _MPL_CACHE is not False:
        return _MPL_CACHE
    try:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from matplotlib import cm
        _MPL_CACHE = (FigureCanvasQTAgg, Figure, cm)
    except ImportError:
        _MPL_CACHE = None
    return _MPL_CACHE


class _MplWidgetBase(QWidget):
    """Base class for matplotlib-based display widgets."""

    def __init__(self, placeholder_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 220)
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
            self._placeholder.setText("matplotlib is required")
            self._mpl_available = False
            self._FigureCanvasQTAgg = self._Figure = self._cm = None

    def _replace_canvas(self, fig) -> None:
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
            self._canvas = None
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

    def save_to_file(self, path: str, dpi: int = 150) -> bool:
        if self._fig is not None:
            try:
                self._fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="#1e1e1e")
                return True
            except (OSError, ValueError, RuntimeError):
                return False
        return False


class HeatmapWidget(_MplWidgetBase):
    """Widget displaying a 2D heatmap of tile medians with interactive sample points."""

    # Signal emitted when manual sample points change: list of (px_x, px_y) tuples
    sample_points_changed = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Click 'Analyze' to generate heatmap", parent)
        self._manual_points: list[tuple[int, int]] = []
        self._img_width = 0
        self._img_height = 0
        self._click_cid = None

    def _on_click(self, event) -> None:
        """Handle mouse clicks on the heatmap for interactive sample point editing."""
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        px_x = int(round(event.xdata))
        px_y = int(round(event.ydata))
        if px_x < 0 or px_x >= self._img_width or px_y < 0 or px_y >= self._img_height:
            return

        # Right-click: remove nearest point (within 3% of image diagonal)
        if event.button == 3:
            diag = (self._img_width**2 + self._img_height**2) ** 0.5
            remove_radius = diag * 0.03
            best_idx = -1
            best_dist = float("inf")
            for i, (px, py) in enumerate(self._manual_points):
                dist = ((px - px_x)**2 + (py - px_y)**2) ** 0.5
                if dist < remove_radius and dist < best_dist:
                    best_dist = dist
                    best_idx = i
            if best_idx >= 0:
                self._manual_points.pop(best_idx)
                self._redraw_manual_points()
                self.sample_points_changed.emit(list(self._manual_points))
            return

        # Left-click: add point
        self._manual_points.append((px_x, px_y))
        self._redraw_manual_points()
        self.sample_points_changed.emit(list(self._manual_points))

    def _redraw_manual_points(self) -> None:
        """Redraw manual sample point markers on the existing axes."""
        if self._fig is None:
            return
        ax = self._fig.axes[0] if self._fig.axes else None
        if ax is None:
            return

        # Remove existing manual point artists
        to_remove = [a for a in ax.lines + ax.texts if getattr(a, "_manual_point", False)]
        for a in to_remove:
            a.remove()

        # Draw new markers
        for i, (px, py) in enumerate(self._manual_points):
            marker, = ax.plot(px, py, "D", color="#00ff88", markersize=7, markeredgecolor="#ffffff",
                              markeredgewidth=1.2, alpha=0.9)
            marker._manual_point = True
            txt = ax.text(px + self._img_width * 0.01, py, str(i + 1), fontsize=7,
                          color="#00ff88", fontweight="bold",
                          bbox=dict(boxstyle="round,pad=0.15", fc="#000000aa", ec="none"))
            txt._manual_point = True

        if self._canvas is not None:
            self._canvas.draw_idle()

    def get_manual_commands(self) -> list[str]:
        """Get Siril setref/addref commands for manually placed sample points."""
        commands = []
        for i, (px, py) in enumerate(self._manual_points):
            if i == 0:
                commands.append(f"setref {px} {py}")
            else:
                commands.append(f"addref {px} {py}")
        return commands

    def clear_manual_points(self) -> None:
        """Remove all manually placed sample points."""
        self._manual_points.clear()
        self._redraw_manual_points()
        self.sample_points_changed.emit([])

    def render_heatmap(
        self,
        tile_medians: np.ndarray,
        img_width: int,
        img_height: int,
        cmap_name: str = "inferno",
        smoothing: bool = True,
        title: str = "Background Gradient Heatmap",
        show_sample_guide: bool = False,
        vmin: float | None = None,
        vmax: float | None = None,
        image_underlay: np.ndarray | None = None,
        heatmap_alpha: float = 0.55,
        gradient_arrow: tuple | None = None,
    ) -> None:
        if not self._mpl_available:
            return

        if smoothing:
            try:
                from scipy.ndimage import zoom
                display_data = zoom(tile_medians, 4, order=1)
            except ImportError:
                display_data = tile_medians
        else:
            display_data = tile_medians

        # Figure size follows image aspect ratio
        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(5, min(10, 6 * aspect_ratio))
        fig_h = max(4, min(8, 6 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")
        ax.set_aspect("equal")

        # Image underlay: auto-stretched grayscale image behind the heatmap
        if image_underlay is not None:
            ax.imshow(
                image_underlay, cmap="gray", origin="lower",
                extent=[0, img_width, 0, img_height],
            )

        im = ax.imshow(
            display_data, cmap=cmap_name, origin="lower",
            extent=[0, img_width, 0, img_height],
            vmin=vmin, vmax=vmax,
            alpha=heatmap_alpha if image_underlay is not None else 1.0,
        )
        fig.suptitle(title, color="#e0e0e0", fontsize=11, fontweight="bold", y=0.98)
        ax.set_xlabel(f"Image Width ({img_width} px)", color="#cccccc", fontsize=9)
        ax.set_ylabel(f"Image Height ({img_height} px)", color="#cccccc", fontsize=9)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#555555")
        cbar = fig.colorbar(im, ax=ax, label="Median Background Level")
        cbar.ax.yaxis.label.set_color("#cccccc")
        cbar.ax.tick_params(colors="#aaaaaa", labelsize=8)

        # Sample point guidance overlay
        if show_sample_guide:
            rows, cols = tile_medians.shape
            flat = tile_medians.flatten()
            threshold_low = np.percentile(flat, 40)  # darkest 40% = good sample regions
            threshold_high = np.percentile(flat, 85)  # brightest 15% = avoid regions
            tile_w = img_width / cols
            tile_h = img_height / rows
            for r in range(rows):
                for c in range(cols):
                    cx = (c + 0.5) * tile_w
                    cy = (r + 0.5) * tile_h
                    val = tile_medians[r, c]
                    if val <= threshold_low:
                        # Good sample point: green circle
                        ax.plot(cx, cy, "o", color="#00ff00", markersize=4, alpha=0.6)
                    elif val >= threshold_high:
                        # Avoid: red X
                        ax.plot(cx, cy, "x", color="#ff3333", markersize=5, alpha=0.6, markeredgewidth=1.5)

            # Legend
            ax.plot([], [], "o", color="#00ff00", markersize=6, label="Good sample region")
            ax.plot([], [], "x", color="#ff3333", markersize=7, markeredgewidth=2, label="Avoid (bright)")
            ax.legend(loc="upper right", fontsize=7, facecolor="#2a2a2aCC", edgecolor="#555",
                      labelcolor="#ccc", framealpha=0.8)

        # Gradient direction arrow (min → max, darkest → brightest)
        if gradient_arrow is not None:
            min_pos, max_pos = gradient_arrow  # (row, col) tuples in tile coords
            rows, cols = tile_medians.shape
            tile_w = img_width / cols
            tile_h = img_height / rows
            x_start = (min_pos[1] + 0.5) * tile_w
            y_start = (min_pos[0] + 0.5) * tile_h
            x_end = (max_pos[1] + 0.5) * tile_w
            y_end = (max_pos[0] + 0.5) * tile_h
            ax.annotate(
                "", xy=(x_end, y_end), xytext=(x_start, y_start),
                arrowprops=dict(
                    arrowstyle="->,head_width=0.4,head_length=0.3",
                    color="#00ffff", lw=2.5, connectionstyle="arc3,rad=0",
                ),
            )
            ax.text(
                x_start, y_start, "dark", fontsize=7, color="#00ffff",
                ha="center", va="top", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#000000aa", ec="none"),
            )
            ax.text(
                x_end, y_end, "bright", fontsize=7, color="#00ffff",
                ha="center", va="bottom", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#000000aa", ec="none"),
            )

        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._img_width = img_width
        self._img_height = img_height
        self._replace_canvas(fig)

        # Connect click handler for interactive sample point editing
        if self._canvas is not None:
            if self._click_cid is not None:
                self._canvas.mpl_disconnect(self._click_cid)
            self._click_cid = self._canvas.mpl_connect("button_press_event", self._on_click)

        # Redraw any existing manual points
        if self._manual_points:
            self._redraw_manual_points()


class SurfacePlotWidget(_MplWidgetBase):
    """Widget displaying a 3D surface plot of tile medians."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Click 'Analyze' to generate 3D view", parent)

    def render_surface(
        self,
        tile_medians: np.ndarray,
        img_width: int = 0,
        img_height: int = 0,
        cmap_name: str = "inferno",
        title: str = "Gradient 3D View",
    ) -> None:
        if not self._mpl_available:
            return

        rows, cols = tile_medians.shape
        # Use real pixel coordinates if dimensions provided, else tile indices
        use_px = img_width > 0 and img_height > 0

        aspect_ratio = (img_width / max(img_height, 1)) if use_px else (cols / max(rows, 1))
        fig_w = max(5, min(10, 6 * aspect_ratio))
        fig_h = max(4, min(8, 6 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#1e1e1e")
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor("#555")
        ax.yaxis.pane.set_edgecolor("#555")
        ax.zaxis.pane.set_edgecolor("#555")
        ax.tick_params(colors="#ccc", labelsize=8)
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.zaxis.label.set_color("#fff")

        if use_px:
            # Tile center positions in pixel coordinates
            x_coords = np.linspace(img_width / (2 * cols), img_width - img_width / (2 * cols), cols)
            y_coords = np.linspace(img_height / (2 * rows), img_height - img_height / (2 * rows), rows)
            X, Y = np.meshgrid(x_coords, y_coords)
            x_range = float(img_width)
            y_range = float(img_height)
        else:
            X, Y = np.meshgrid(range(cols), range(rows))
            x_range = float(cols)
            y_range = float(rows)

        ax.plot_surface(X, Y, tile_medians, cmap=cmap_name, alpha=0.9, edgecolor="none", antialiased=True)
        fig.suptitle(title, color="#e0e0e0", fontsize=11, fontweight="bold", y=0.98)
        ax.set_xlabel("X (px)" if use_px else "Column")
        ax.set_ylabel("Y (px)" if use_px else "Row")
        ax.set_zlabel("Background Level")

        z_range = max(float(tile_medians.max() - tile_medians.min()), 1e-6)
        z_scale = max(x_range, y_range) * 0.35 / max(z_range, 1e-6)
        z_display = z_range * z_scale
        max_dim = max(x_range, y_range, z_display)
        try:
            ax.set_box_aspect((x_range / max_dim, y_range / max_dim, z_display / max_dim))
        except AttributeError:
            pass
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._replace_canvas(fig)


class ProfileWidget(_MplWidgetBase):
    """Widget showing horizontal and vertical gradient cross-section profiles."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Click 'Analyze' to generate profiles", parent)

    def render_profiles(self, tile_medians: np.ndarray, img_width: int, img_height: int) -> None:
        if not self._mpl_available:
            return

        fig = self._Figure(figsize=(10, 4), facecolor="#1e1e1e")

        # Horizontal profile: median of each column of tiles
        h_profile = np.median(tile_medians, axis=0)
        cols = len(h_profile)
        x_positions = np.linspace(0, img_width, cols, endpoint=False) + img_width / (2 * cols)

        ax1 = fig.add_subplot(121)
        ax1.set_facecolor("#1e1e1e")
        ax1.plot(x_positions, h_profile, color="#88aaff", linewidth=2)
        ax1.fill_between(x_positions, h_profile, alpha=0.2, color="#88aaff")
        ax1.set_title("Horizontal Profile (Left \u2192 Right)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax1.set_xlabel("Image X (px)", color="#cccccc", fontsize=9)
        ax1.set_ylabel("Median Background", color="#cccccc", fontsize=9)
        ax1.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax1.spines.values():
            spine.set_edgecolor("#555555")
        # Mark min/max
        ax1.axhline(y=np.min(h_profile), color="#55aa55", linestyle="--", alpha=0.6, linewidth=1)
        ax1.axhline(y=np.max(h_profile), color="#dd4444", linestyle="--", alpha=0.6, linewidth=1)

        # Vertical profile: median of each row of tiles
        v_profile = np.median(tile_medians, axis=1)
        rows = len(v_profile)
        y_positions = np.linspace(0, img_height, rows, endpoint=False) + img_height / (2 * rows)

        ax2 = fig.add_subplot(122)
        ax2.set_facecolor("#1e1e1e")
        ax2.plot(y_positions, v_profile, color="#ffaa55", linewidth=2)
        ax2.fill_between(y_positions, v_profile, alpha=0.2, color="#ffaa55")
        ax2.set_title("Vertical Profile (Bottom \u2192 Top)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Image Y (px)", color="#cccccc", fontsize=9)
        ax2.set_ylabel("Median Background", color="#cccccc", fontsize=9)
        ax2.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555555")
        ax2.axhline(y=np.min(v_profile), color="#55aa55", linestyle="--", alpha=0.6, linewidth=1)
        ax2.axhline(y=np.max(v_profile), color="#dd4444", linestyle="--", alpha=0.6, linewidth=1)

        fig.tight_layout()
        self._replace_canvas(fig)


class TileHistogramWidget(_MplWidgetBase):
    """Widget showing the distribution of tile median values as a histogram."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Click 'Analyze' to generate histogram", parent)

    def render_histogram(self, tile_medians: np.ndarray) -> None:
        if not self._mpl_available:
            return

        flat = tile_medians.flatten()
        n_bins = max(10, min(50, len(flat) // 2))

        fig = self._Figure(figsize=(6, 4), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")

        counts, edges, patches = ax.hist(flat, bins=n_bins, color="#88aaff", alpha=0.7, edgecolor="#5577cc")

        # Color patches by value (low=green, high=red)
        norm_edges = (edges[:-1] - flat.min()) / max(flat.max() - flat.min(), 1e-15)
        for p, nv in zip(patches, norm_edges):
            r = int(min(255, 100 + nv * 155))
            g = int(max(80, 200 - nv * 120))
            b = 100
            p.set_facecolor(f"#{r:02x}{g:02x}{b:02x}")

        ax.axvline(x=np.median(flat), color="#ffaa55", linestyle="--", linewidth=2, label=f"Median: {np.median(flat):.6f}")
        ax.axvline(x=np.mean(flat), color="#55aaff", linestyle=":", linewidth=2, label=f"Mean: {np.mean(flat):.6f}")
        ax.legend(loc="upper right", fontsize=8, facecolor="#2a2a2a", edgecolor="#555", labelcolor="#ccc")

        ax.set_title("Tile Median Distribution", color="#e0e0e0", fontsize=11, fontweight="bold")
        ax.set_xlabel("Background Level", color="#cccccc", fontsize=9)
        ax.set_ylabel("Number of Tiles", color="#cccccc", fontsize=9)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#555555")
        fig.tight_layout()
        self._replace_canvas(fig)


class ChannelComparisonWidget(_MplWidgetBase):
    """Widget showing R, G, B channel heatmaps side by side."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Enable 'Analyze channels separately' and click 'Analyze'", parent)

    def render_channels(
        self,
        r_medians: np.ndarray,
        g_medians: np.ndarray,
        b_medians: np.ndarray,
        r_metrics: dict,
        g_metrics: dict,
        b_metrics: dict,
        cmap_name: str = "inferno",
        smoothing: bool = True,
    ) -> None:
        if not self._mpl_available:
            return

        fig = self._Figure(figsize=(14, 4), facecolor="#1e1e1e")
        channels = [
            ("R Channel", r_medians, r_metrics, "#ff5050"),
            ("G Channel", g_medians, g_metrics, "#50ff50"),
            ("B Channel", b_medians, b_metrics, "#5050ff"),
        ]

        vmin = min(np.min(r_medians), np.min(g_medians), np.min(b_medians))
        vmax = max(np.max(r_medians), np.max(g_medians), np.max(b_medians))

        zoom_func = None
        if smoothing:
            try:
                from scipy.ndimage import zoom
                zoom_func = zoom
            except ImportError:
                pass

        for i, (title, medians, metrics, color) in enumerate(channels):
            ax = fig.add_subplot(1, 3, i + 1)
            ax.set_facecolor("#1e1e1e")
            display_data = zoom_func(medians, 4, order=1) if zoom_func is not None else medians

            ax.imshow(display_data, cmap=cmap_name, origin="lower", aspect="auto", vmin=vmin, vmax=vmax)
            ax.set_title(
                f"{title}\nGradient: {metrics['strength_pct']:.1f}%",
                color=color, fontsize=10, fontweight="bold",
            )
            ax.tick_params(colors="#aaaaaa", labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor("#555555")

        fig.tight_layout()
        self._replace_canvas(fig)


class BackgroundModelWidget(_MplWidgetBase):
    """Widget showing the fitted polynomial background model and residuals."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Run analysis to see background model preview", parent)

    def render_model(
        self,
        tile_medians: np.ndarray,
        model: np.ndarray,
        degree: int,
        img_width: int,
        img_height: int,
        smoothing: bool = True,
    ) -> None:
        if not self._mpl_available:
            return

        residuals = tile_medians - model

        zoom_func = None
        if smoothing:
            try:
                from scipy.ndimage import zoom
                zoom_func = zoom
            except ImportError:
                pass

        disp_model = zoom_func(model, 4, order=1) if zoom_func else model
        disp_residuals = zoom_func(residuals, 4, order=1) if zoom_func else residuals

        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(8, min(14, 10 * aspect_ratio))
        fig_h = max(3, min(6, 5 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")

        # Left: fitted model (what subsky would subtract)
        ax1 = fig.add_subplot(121)
        ax1.set_facecolor("#1e1e1e")
        ax1.set_aspect("equal")
        im1 = ax1.imshow(disp_model, cmap="inferno", origin="lower",
                         extent=[0, img_width, 0, img_height])
        ax1.set_title(f"Background Model (degree {degree})", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax1.set_xlabel("X (px)", color="#ccc", fontsize=8)
        ax1.set_ylabel("Y (px)", color="#ccc", fontsize=8)
        ax1.tick_params(colors="#aaa", labelsize=7)
        for spine in ax1.spines.values():
            spine.set_edgecolor("#555")
        cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        cbar1.ax.tick_params(colors="#aaa", labelsize=7)
        cbar1.ax.yaxis.label.set_color("#ccc")

        # Right: residuals after subtraction
        ax2 = fig.add_subplot(122)
        ax2.set_facecolor("#1e1e1e")
        ax2.set_aspect("equal")
        # Center colormap around zero for residuals
        abs_max = max(abs(float(np.min(disp_residuals))), abs(float(np.max(disp_residuals))))
        im2 = ax2.imshow(disp_residuals, cmap="coolwarm", origin="lower",
                         extent=[0, img_width, 0, img_height],
                         vmin=-abs_max, vmax=abs_max)
        ax2.set_title("Residuals (after subtraction)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax2.set_xlabel("X (px)", color="#ccc", fontsize=8)
        ax2.set_ylabel("Y (px)", color="#ccc", fontsize=8)
        ax2.tick_params(colors="#aaa", labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555")
        cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
        cbar2.ax.tick_params(colors="#aaa", labelsize=7)
        cbar2.ax.yaxis.label.set_color("#ccc")

        fig.tight_layout(rect=[0, 0, 1, 0.95])
        residual_std = float(np.std(residuals))
        fig.suptitle(
            f"Background Model Preview — degree {degree}  |  residual σ = {residual_std:.6f}",
            color="#88aaff", fontsize=10, fontweight="bold", y=0.98,
        )
        self._replace_canvas(fig)


class SubtractionPreviewWidget(_MplWidgetBase):
    """Widget showing a before/after subtraction preview at pixel resolution."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Run analysis to see subtraction preview", parent)

    def render_preview(
        self,
        luminance: np.ndarray,
        bg_model: np.ndarray,
        img_width: int,
        img_height: int,
        grid_rows: int,
        grid_cols: int,
    ) -> None:
        if not self._mpl_available:
            return

        # Upscale bg_model from tile resolution to full image resolution
        try:
            from scipy.ndimage import zoom
            zoom_y = luminance.shape[0] / bg_model.shape[0]
            zoom_x = luminance.shape[1] / bg_model.shape[1]
            model_full = zoom(bg_model, (zoom_y, zoom_x), order=3)
        except ImportError:
            # Simple nearest-neighbor upscale
            model_full = np.repeat(np.repeat(bg_model, luminance.shape[0] // bg_model.shape[0], axis=0),
                                    luminance.shape[1] // bg_model.shape[1], axis=1)
            # Trim to match
            model_full = model_full[:luminance.shape[0], :luminance.shape[1]]

        # Subtract model from luminance
        corrected = luminance - model_full
        # Shift so median is at the original median (preserve brightness)
        corrected = corrected - np.median(corrected) + np.median(luminance)
        corrected = np.clip(corrected, 0, None)

        # Auto-stretch both for display
        def _stretch(img):
            lo = np.percentile(img, 0.5)
            hi = np.percentile(img, 99.5)
            if hi - lo < 1e-15:
                return np.zeros_like(img, dtype=np.float32)
            return np.clip((img - lo) / (hi - lo), 0, 1).astype(np.float32)

        orig_stretched = _stretch(luminance)
        corr_stretched = _stretch(corrected)

        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(8, min(14, 10 * aspect_ratio))
        fig_h = max(3, min(7, 5 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")

        ax1 = fig.add_subplot(121)
        ax1.set_facecolor("#1e1e1e")
        ax1.imshow(orig_stretched, cmap="gray", origin="lower",
                   extent=[0, img_width, 0, img_height], aspect="equal")
        ax1.set_title("Before (original)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax1.tick_params(colors="#aaa", labelsize=7)
        for spine in ax1.spines.values():
            spine.set_edgecolor("#555")

        ax2 = fig.add_subplot(122)
        ax2.set_facecolor("#1e1e1e")
        ax2.imshow(corr_stretched, cmap="gray", origin="lower",
                   extent=[0, img_width, 0, img_height], aspect="equal")
        ax2.set_title("After (simulated subtraction)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax2.tick_params(colors="#aaa", labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555")

        fig.suptitle("Subtraction Preview (polynomial background removal)",
                     color="#88aaff", fontsize=10, fontweight="bold", y=0.98)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._replace_canvas(fig)


class GradientMagnitudeWidget(_MplWidgetBase):
    """Widget showing a gradient magnitude map (rate of change)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Run analysis to see gradient magnitude", parent)

    def render_magnitude(
        self,
        magnitude: np.ndarray,
        img_width: int,
        img_height: int,
        smoothing: bool = True,
    ) -> None:
        if not self._mpl_available:
            return

        if smoothing:
            try:
                from scipy.ndimage import zoom
                display_data = zoom(magnitude, 4, order=1)
            except ImportError:
                display_data = magnitude
        else:
            display_data = magnitude

        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(5, min(10, 6 * aspect_ratio))
        fig_h = max(4, min(8, 6 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e1e")
        ax.set_aspect("equal")

        im = ax.imshow(display_data, cmap="hot", origin="lower",
                       extent=[0, img_width, 0, img_height])
        ax.set_xlabel("X (px)", color="#ccc", fontsize=9)
        ax.set_ylabel("Y (px)", color="#ccc", fontsize=9)
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#555")
        cbar = fig.colorbar(im, ax=ax, label="Gradient Magnitude")
        cbar.ax.yaxis.label.set_color("#ccc")
        cbar.ax.tick_params(colors="#aaa", labelsize=8)

        fig.suptitle("Gradient Magnitude (rate of change)", color="#e0e0e0",
                     fontsize=11, fontweight="bold", y=0.98)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._replace_canvas(fig)


class ResidualMaskWidget(_MplWidgetBase):
    """Widget showing polynomial fit residuals with exclusion mask overlay."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Run analysis to see residual map", parent)

    def render_residual_map(
        self,
        tile_medians: np.ndarray,
        bg_model: np.ndarray,
        weight_mask: np.ndarray,
        img_width: int,
        img_height: int,
    ) -> None:
        if not self._mpl_available:
            return

        residuals = tile_medians - bg_model
        rows, cols = residuals.shape

        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(8, min(14, 10 * aspect_ratio))
        fig_h = max(3, min(6, 5 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")

        # Left: Residual map
        ax1 = fig.add_subplot(121)
        ax1.set_facecolor("#1e1e1e")
        ax1.set_aspect("equal")

        # Smooth residuals for display
        try:
            from scipy.ndimage import zoom
            display_res = zoom(residuals, 4, order=1)
        except ImportError:
            display_res = residuals

        vmax = max(abs(float(np.min(residuals))), abs(float(np.max(residuals))))
        if vmax < 1e-15:
            vmax = 1.0
        im1 = ax1.imshow(display_res, cmap="RdBu_r", origin="lower",
                         extent=[0, img_width, 0, img_height],
                         vmin=-vmax, vmax=vmax)
        ax1.set_title("Fit Residuals", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax1.tick_params(colors="#aaa", labelsize=7)
        for spine in ax1.spines.values():
            spine.set_edgecolor("#555")
        cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        cbar1.ax.tick_params(colors="#aaa", labelsize=7)

        # Right: Exclusion mask overlay on tile medians
        ax2 = fig.add_subplot(122)
        ax2.set_facecolor("#1e1e1e")
        ax2.set_aspect("equal")

        try:
            from scipy.ndimage import zoom
            display_med = zoom(tile_medians, 4, order=1)
            display_mask = zoom(weight_mask, 4, order=0)  # Nearest neighbor for mask
        except ImportError:
            display_med = tile_medians
            display_mask = weight_mask

        im2 = ax2.imshow(display_med, cmap="inferno", origin="lower",
                         extent=[0, img_width, 0, img_height])

        # Overlay excluded tiles in red
        import matplotlib.colors as mcolors
        mask_rgba = np.zeros((*display_mask.shape, 4))
        mask_rgba[display_mask < 0.5, 0] = 1.0  # Red
        mask_rgba[display_mask < 0.5, 3] = 0.4  # Semi-transparent
        ax2.imshow(mask_rgba, origin="lower",
                   extent=[0, img_width, 0, img_height])

        # Count excluded
        excluded_count = int(np.sum(weight_mask < 0.5))
        total_tiles = weight_mask.size
        ax2.set_title(
            f"Exclusion Mask ({excluded_count}/{total_tiles} excluded)",
            color="#e0e0e0", fontsize=10, fontweight="bold",
        )
        ax2.tick_params(colors="#aaa", labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555")

        residual_std = float(np.std(residuals))
        fig.suptitle(
            f"Residuals after polynomial fit (RMS: {residual_std:.6f})",
            color="#88aaff", fontsize=10, fontweight="bold", y=0.98,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._replace_canvas(fig)


class FWHMMapWidget(_MplWidgetBase):
    """Widget showing FWHM and eccentricity maps across the field."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Run analysis to see FWHM/eccentricity map", parent)

    def render_fwhm_map(
        self,
        fwhm_data: dict,
        img_width: int,
        img_height: int,
    ) -> None:
        if not self._mpl_available:
            return

        fwhm_map = fwhm_data["fwhm_map"]
        ecc_map = fwhm_data["eccentricity_map"]

        aspect_ratio = img_width / max(img_height, 1)
        fig_w = max(8, min(14, 10 * aspect_ratio))
        fig_h = max(3, min(6, 5 / aspect_ratio))
        fig = self._Figure(figsize=(fig_w, fig_h), facecolor="#1e1e1e")

        # Left: FWHM map
        ax1 = fig.add_subplot(121)
        ax1.set_facecolor("#1e1e1e")
        ax1.set_aspect("equal")

        # Replace NaN with 0 for display
        fwhm_display = np.copy(fwhm_map)
        fwhm_display[np.isnan(fwhm_display)] = 0

        try:
            from scipy.ndimage import zoom
            fwhm_display = zoom(fwhm_display, 4, order=1)
        except ImportError:
            pass

        im1 = ax1.imshow(fwhm_display, cmap="viridis", origin="lower",
                         extent=[0, img_width, 0, img_height])
        ax1.set_title("FWHM Map (px)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax1.tick_params(colors="#aaa", labelsize=7)
        for spine in ax1.spines.values():
            spine.set_edgecolor("#555")
        cbar1 = fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        cbar1.ax.tick_params(colors="#aaa", labelsize=7)

        # Right: Eccentricity map
        ax2 = fig.add_subplot(122)
        ax2.set_facecolor("#1e1e1e")
        ax2.set_aspect("equal")

        ecc_display = np.copy(ecc_map)
        ecc_display[np.isnan(ecc_display)] = 0

        try:
            from scipy.ndimage import zoom
            ecc_display = zoom(ecc_display, 4, order=1)
        except ImportError:
            pass

        im2 = ax2.imshow(ecc_display, cmap="plasma", origin="lower",
                         extent=[0, img_width, 0, img_height],
                         vmin=0, vmax=0.5)
        ax2.set_title("Eccentricity Map (0=round)", color="#e0e0e0", fontsize=10, fontweight="bold")
        ax2.tick_params(colors="#aaa", labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555")
        cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
        cbar2.ax.tick_params(colors="#aaa", labelsize=7)

        med_fwhm = fwhm_data.get("median_fwhm")
        med_ecc = fwhm_data.get("median_eccentricity")
        title_parts = []
        if med_fwhm is not None:
            title_parts.append(f"FWHM: {med_fwhm:.1f} px")
        if med_ecc is not None:
            title_parts.append(f"Ecc: {med_ecc:.2f}")
        fig.suptitle(
            " | ".join(title_parts) if title_parts else "FWHM / Eccentricity",
            color="#88aaff", fontsize=10, fontweight="bold", y=0.98,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        self._replace_canvas(fig)


# ------------------------------------------------------------------------------
# GRADIENT STRENGTH GAUGE (custom painted widget)
# ------------------------------------------------------------------------------

class GradientGaugeWidget(QWidget):
    """
    A color-coded horizontal gauge showing gradient strength from 0% to 25%+.
    Green zone (0-2%), yellow (2-5%), orange (5-15%), red (15%+).
    """

    ZONE_COLORS = [
        (2.0, QColor(85, 170, 85)),     # green
        (5.0, QColor(170, 170, 85)),     # yellow
        (15.0, QColor(221, 136, 51)),    # orange
        (25.0, QColor(221, 68, 68)),     # red
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(280, 75)
        self.setMaximumHeight(80)
        self._value = 0.0
        self._label = ""

    def set_value(self, pct: float, label: str = "") -> None:
        self._value = pct
        self._label = label
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(43, 43, 43))

        bar_x = 10
        bar_y = 8
        bar_w = w - 20
        bar_h = 22
        max_pct = 25.0

        # Draw zone backgrounds
        prev_x = bar_x
        for threshold, color in self.ZONE_COLORS:
            zone_x = bar_x + int(threshold / max_pct * bar_w)
            zone_x = min(zone_x, bar_x + bar_w)
            dark = QColor(color.red() // 3, color.green() // 3, color.blue() // 3)
            painter.fillRect(prev_x, bar_y, zone_x - prev_x, bar_h, dark)
            prev_x = zone_x

        # Draw filled portion up to current value
        fill_pct = min(self._value, max_pct)
        fill_w = int(fill_pct / max_pct * bar_w)

        # Gradient fill matching zones
        if fill_w > 0:
            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            prev_stop = 0.0
            for threshold, color in self.ZONE_COLORS:
                stop = min(threshold / max_pct, fill_pct / max_pct)
                norm_stop = stop / (fill_pct / max_pct) if fill_pct > 0 else 0
                norm_stop = min(1.0, max(0.0, norm_stop))
                if norm_stop > prev_stop:
                    grad.setColorAt(norm_stop, color)
                    prev_stop = norm_stop
                if threshold >= fill_pct:
                    break
            painter.fillRect(bar_x, bar_y, fill_w, bar_h, grad)

        # Border
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(bar_x, bar_y, bar_w, bar_h)

        # Zone boundary markers
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        for threshold, _ in self.ZONE_COLORS[:-1]:
            x = bar_x + int(threshold / max_pct * bar_w)
            painter.drawLine(x, bar_y, x, bar_y + bar_h)

        # Needle / indicator
        needle_x = bar_x + int(min(self._value, max_pct) / max_pct * bar_w)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(needle_x, bar_y - 2, needle_x, bar_y + bar_h + 2)

        font = QFont()
        _, color = get_gradient_assessment(self._value)

        # Zone labels just below bar
        zone_y = bar_y + bar_h + 12
        font.setPointSize(7)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(150, 150, 150))
        zone_labels = [("0%", 0), ("2%", 2), ("5%", 5), ("15%", 15), ("25%", 25)]
        for label, pct in zone_labels:
            lx = bar_x + int(pct / max_pct * bar_w)
            painter.drawText(lx - 10, zone_y, label)

        # Value + assessment on next row
        row2_y = zone_y + 16
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(color))
        value_text = f"{self._value:.1f}%"
        if self._value > max_pct:
            value_text += "+"
        painter.drawText(bar_x, row2_y, value_text)

        # Assessment label (same row, offset right)
        if self._label:
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(bar_x + 60, row2_y, self._label)


# ------------------------------------------------------------------------------
# QUADRANT DISPLAY WIDGET
# ------------------------------------------------------------------------------

class QuadrantWidget(QWidget):
    """Visual display of NW/NE/SW/SE quadrant median values."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(220, 140)
        self.setMaximumHeight(160)
        self._data = None

    def set_data(self, quadrant_data: dict) -> None:
        self._data = quadrant_data
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(43, 43, 43))

        if self._data is None:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(10, h // 2, "No data")
            return

        quads = self._data["quadrants"]
        brightest = self._data["brightest"]
        darkest = self._data["darkest"]
        all_vals = list(quads.values())
        vmin, vmax = min(all_vals), max(all_vals)
        vrange = vmax - vmin if vmax > vmin else 1e-10

        # Draw 2x2 grid
        margin = 10
        grid_w = (w - 3 * margin) // 2
        grid_h = (h - 3 * margin - 20) // 2  # space for title
        title_y = 14

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(136, 170, 255))
        painter.drawText(margin, title_y, "Quadrant Analysis")

        positions = {
            "NW": (margin, margin + 18),
            "NE": (margin * 2 + grid_w, margin + 18),
            "SW": (margin, margin * 2 + grid_h + 18),
            "SE": (margin * 2 + grid_w, margin * 2 + grid_h + 18),
        }

        for name, (x, y) in positions.items():
            val = quads[name]
            intensity = (val - vmin) / vrange
            # Color: darker green for low, brighter red/orange for high
            r = int(60 + intensity * 140)
            g = int(140 - intensity * 80)
            b = int(60)
            bg_color = QColor(r, g, b)
            painter.fillRect(x, y, grid_w, grid_h, bg_color)

            # Border highlight for brightest/darkest
            if name == brightest:
                painter.setPen(QPen(QColor(255, 100, 100), 2))
                painter.drawRect(x, y, grid_w, grid_h)
            elif name == darkest:
                painter.setPen(QPen(QColor(100, 255, 100), 2))
                painter.drawRect(x, y, grid_w, grid_h)
            else:
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawRect(x, y, grid_w, grid_h)

            # Text
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x + 4, y + 16, name)
            font.setPointSize(8)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(x + 4, y + 30, f"{val:.6f}")

            # Label brightest/darkest
            if name == brightest:
                painter.setPen(QColor(255, 120, 120))
                painter.drawText(x + 4, y + grid_h - 4, "BRIGHTEST")
            elif name == darkest:
                painter.setPen(QColor(120, 255, 120))
                painter.drawText(x + 4, y + grid_h - 4, "DARKEST")


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class GradientAnalyzerWindow(QMainWindow):
    """
    Main window for the Gradient Analyzer.

    Left panel: configuration controls.
    Right panel: tabbed visualization (heatmap, profiles, histogram, 3D, channels)
                 plus results, gauge, quadrant display, and suggestions.
    """

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self._image_data = None
        self._img_width = 0
        self._img_height = 0
        self._img_channels = 0
        self._ch_str = ""
        self._last_metrics = None
        self._last_tile_medians = None
        self._last_channel_metrics: dict | None = None
        # Before/After state
        self._previous_metrics = None
        self._previous_tile_medians = None
        self._run_count = 0
        # Colorbar range locking for before/after comparison
        self._locked_vmin: float | None = None
        self._locked_vmax: float | None = None
        self._last_sample_commands: list[str] = []
        self._last_complexity: dict | None = None
        self._last_report_data: dict | None = None
        self._last_weight_mask: np.ndarray | None = None
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.init_ui()
        self._load_settings()
        # Connect interactive sample point signal
        self.heatmap_widget.sample_points_changed.connect(self._on_manual_points_changed)
        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self, self._on_analyze)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._on_refresh_and_analyze)

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
        lbl = QLabel(f"Gradient Analyzer {VERSION}")
        lbl.setStyleSheet("font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_grid_settings_group(layout)
        self._build_options_group(layout)
        self._build_action_buttons(layout)

        # Gauge in left panel (compact)
        gauge_group = QGroupBox("Gradient Strength")
        gauge_layout = QVBoxLayout(gauge_group)
        self.gauge_widget = GradientGaugeWidget()
        gauge_layout.addWidget(self.gauge_widget)
        layout.addWidget(gauge_group)

        # Quadrant display in left panel
        self.quadrant_widget = QuadrantWidget()
        layout.addWidget(self.quadrant_widget)

        layout.addStretch()

        # Help / Close
        btn_help = QPushButton("Help")
        _nofocus(btn_help)
        btn_help.clicked.connect(self._show_help_dialog)
        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.setObjectName("CloseButton")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_help)
        layout.addWidget(btn_close)

        scroll.setWidget(content)

        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        return left

    def _build_grid_settings_group(self, parent_layout: QVBoxLayout) -> None:
        from PyQt6.QtWidgets import QGridLayout

        group = QGroupBox("Grid Settings")
        grid = QGridLayout(group)
        grid.setColumnMinimumWidth(0, 75)  # label column
        grid.setColumnMinimumWidth(1, 60)  # spinbox column
        grid.setColumnStretch(2, 1)        # slider takes remaining space

        lbl_cols = QLabel("Columns:")
        lbl_cols.setFixedWidth(75)
        grid.addWidget(lbl_cols, 0, 0)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(4, 64)
        self.spin_cols.setValue(16)
        self.spin_cols.setFixedWidth(60)
        _nofocus(self.spin_cols)
        grid.addWidget(self.spin_cols, 0, 1)
        self.slider_cols = QSlider(Qt.Orientation.Horizontal)
        self.slider_cols.setRange(4, 64)
        self.slider_cols.setValue(16)
        _nofocus(self.slider_cols)
        self.slider_cols.valueChanged.connect(self.spin_cols.setValue)
        self.spin_cols.valueChanged.connect(self.slider_cols.setValue)
        grid.addWidget(self.slider_cols, 0, 2)

        lbl_rows = QLabel("Rows:")
        lbl_rows.setFixedWidth(75)
        grid.addWidget(lbl_rows, 1, 0)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(4, 64)
        self.spin_rows.setValue(16)
        self.spin_rows.setFixedWidth(60)
        _nofocus(self.spin_rows)
        grid.addWidget(self.spin_rows, 1, 1)
        self.slider_rows = QSlider(Qt.Orientation.Horizontal)
        self.slider_rows.setRange(4, 64)
        self.slider_rows.setValue(16)
        _nofocus(self.slider_rows)
        self.slider_rows.valueChanged.connect(self.spin_rows.setValue)
        self.spin_rows.valueChanged.connect(self.slider_rows.setValue)
        grid.addWidget(self.slider_rows, 1, 2)

        lbl_sigma = QLabel("Sigma-Clip:")
        lbl_sigma.setFixedWidth(75)
        grid.addWidget(lbl_sigma, 2, 0)
        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(1.5, 4.0)
        self.spin_sigma.setValue(2.5)
        self.spin_sigma.setSingleStep(0.1)
        self.spin_sigma.setDecimals(1)
        self.spin_sigma.setFixedWidth(60)
        _nofocus(self.spin_sigma)
        grid.addWidget(self.spin_sigma, 2, 1)

        # Sigma suggestion label (updated after analysis)
        self.lbl_sigma_hint = QLabel("")
        self.lbl_sigma_hint.setStyleSheet("color: #aaaa55; font-size: 8pt;")
        self.lbl_sigma_hint.setWordWrap(True)
        grid.addWidget(self.lbl_sigma_hint, 3, 0, 1, 3)

        # Threshold preset
        lbl_preset = QLabel("Preset:")
        lbl_preset.setFixedWidth(75)
        grid.addWidget(lbl_preset, 4, 0)
        self.combo_preset = QComboBox()
        for name in THRESHOLD_PRESETS:
            self.combo_preset.addItem(name)
        self.combo_preset.setCurrentIndex(0)
        self.combo_preset.setToolTip(
            "Broadband: standard thresholds (2/5/15%)\n"
            "Narrowband: stricter thresholds for faint signals (1/3/8%)\n"
            "Fast optics: tolerant thresholds for fast f-ratio systems (4/8/20%)"
        )
        _nofocus(self.combo_preset)
        grid.addWidget(self.combo_preset, 4, 1, 1, 2)

        parent_layout.addWidget(group)

    def _build_options_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Options")
        g_layout = QVBoxLayout(group)

        self.chk_smoothing = QCheckBox("Smoothing (bilinear interpolation)")
        self.chk_smoothing.setChecked(True)
        _nofocus(self.chk_smoothing)
        g_layout.addWidget(self.chk_smoothing)

        self.chk_3d = QCheckBox("3D view")
        self.chk_3d.setChecked(True)
        _nofocus(self.chk_3d)
        g_layout.addWidget(self.chk_3d)

        self.chk_rgb_separate = QCheckBox("Analyze channels separately (RGB)")
        self.chk_rgb_separate.setChecked(False)
        _nofocus(self.chk_rgb_separate)
        g_layout.addWidget(self.chk_rgb_separate)

        self.chk_sample_guide = QCheckBox("Show sample point guidance")
        self.chk_sample_guide.setChecked(True)
        self.chk_sample_guide.setToolTip(
            "Overlay green circles (good sample regions) and red X marks (avoid) on the heatmap"
        )
        _nofocus(self.chk_sample_guide)
        g_layout.addWidget(self.chk_sample_guide)

        self.chk_image_underlay = QCheckBox("Show image under heatmap")
        self.chk_image_underlay.setChecked(False)
        self.chk_image_underlay.setToolTip(
            "Display the auto-stretched image underneath the heatmap overlay.\n"
            "Helps see which parts of the actual image correspond to the gradient pattern."
        )
        _nofocus(self.chk_image_underlay)
        g_layout.addWidget(self.chk_image_underlay)

        self.chk_save_png = QCheckBox("Save heatmap as PNG")
        self.chk_save_png.setChecked(False)
        _nofocus(self.chk_save_png)
        g_layout.addWidget(self.chk_save_png)

        self.chk_save_json = QCheckBox("Save analysis JSON (for comparison)")
        self.chk_save_json.setChecked(False)
        self.chk_save_json.setToolTip(
            "Save analysis results to a JSON sidecar file. On next run, "
            "automatically compare against the saved results."
        )
        _nofocus(self.chk_save_json)
        g_layout.addWidget(self.chk_save_json)

        parent_layout.addWidget(group)

    def _build_action_buttons(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Actions")
        g_layout = QVBoxLayout(group)

        btn_analyze = QPushButton("Analyze  (F5)")
        btn_analyze.setObjectName("AnalyzeButton")
        _nofocus(btn_analyze)
        btn_analyze.setToolTip("Analyze background gradient of the current Siril image (F5)")
        btn_analyze.clicked.connect(self._on_analyze)
        g_layout.addWidget(btn_analyze)

        btn_refresh = QPushButton("Refresh from Siril  (Ctrl+Shift+R)")
        _nofocus(btn_refresh)
        btn_refresh.setToolTip("Reload the current image from Siril and re-analyze")
        btn_refresh.clicked.connect(self._on_refresh_and_analyze)
        g_layout.addWidget(btn_refresh)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar{background:#3c3c3c;border:1px solid #555;border-radius:3px;text-align:center;color:#ccc}"
            "QProgressBar::chunk{background:#285299;border-radius:2px}"
        )
        g_layout.addWidget(self.progress_bar)

        btn_batch = QPushButton("Analyze Sub-frames...")
        _nofocus(btn_batch)
        btn_batch.setToolTip(
            "Select a directory of FITS files and rank them by gradient severity.\n"
            "Requires astropy. Useful for identifying worst subs before stacking."
        )
        btn_batch.clicked.connect(self._on_batch_analyze)
        g_layout.addWidget(btn_batch)

        btn_apply_subsky = QPushButton("Apply subsky && Re-analyze")
        _nofocus(btn_apply_subsky)
        btn_apply_subsky.setToolTip(
            "Execute the recommended subsky command in Siril, then\n"
            "automatically reload and re-analyze the result."
        )
        btn_apply_subsky.clicked.connect(self._on_apply_subsky)
        g_layout.addWidget(btn_apply_subsky)

        btn_auto_iterate = QPushButton("Auto-iterate until <2%")
        _nofocus(btn_auto_iterate)
        btn_auto_iterate.setToolTip(
            "Repeatedly apply subsky and re-analyze (up to 3 passes)\n"
            "until gradient drops below 2%. Uses the recommended degree\n"
            "from the complexity analysis for each pass."
        )
        btn_auto_iterate.clicked.connect(self._on_auto_iterate)
        g_layout.addWidget(btn_auto_iterate)

        # History sparkline label
        self.lbl_history = QLabel("")
        self.lbl_history.setStyleSheet("color: #888; font-size: 8pt;")
        self.lbl_history.setWordWrap(True)
        g_layout.addWidget(self.lbl_history)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # RIGHT PANEL (tabbed)
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(5, 5, 5, 5)

        # Image info bar
        self.lbl_image_info = QLabel("No image loaded — click 'Analyze' or 'Refresh from Siril'")
        self.lbl_image_info.setStyleSheet("font-size: 10pt; color: #999;")
        r_layout.addWidget(self.lbl_image_info)

        # Tab widget for visualizations
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tab 1: Heatmap + 3D
        tab_heatmap = QWidget()
        tab_heatmap_layout = QHBoxLayout(tab_heatmap)
        self.heatmap_widget = HeatmapWidget()
        tab_heatmap_layout.addWidget(self.heatmap_widget, 1)
        self.surface_widget = SurfacePlotWidget()
        tab_heatmap_layout.addWidget(self.surface_widget, 1)
        self.tabs.addTab(tab_heatmap, "Heatmap / 3D")

        # Tab 2: Gradient Profiles
        tab_profiles = QWidget()
        tab_profiles_layout = QVBoxLayout(tab_profiles)
        self.profile_widget = ProfileWidget()
        tab_profiles_layout.addWidget(self.profile_widget)
        self.tabs.addTab(tab_profiles, "Profiles")

        # Tab 3: Tile Histogram
        tab_tilehist = QWidget()
        tab_tilehist_layout = QVBoxLayout(tab_tilehist)
        self.tile_hist_widget = TileHistogramWidget()
        tab_tilehist_layout.addWidget(self.tile_hist_widget)
        self.tabs.addTab(tab_tilehist, "Tile Distribution")

        # Tab 4: Channel Comparison
        tab_channels = QWidget()
        tab_channels_layout = QVBoxLayout(tab_channels)
        self.channel_widget = ChannelComparisonWidget()
        tab_channels_layout.addWidget(self.channel_widget)
        self.tabs.addTab(tab_channels, "RGB Channels")

        # Tab 5: Background Model
        tab_bgmodel = QWidget()
        tab_bgmodel_layout = QVBoxLayout(tab_bgmodel)
        self.bg_model_widget = BackgroundModelWidget()
        tab_bgmodel_layout.addWidget(self.bg_model_widget)
        self.tabs.addTab(tab_bgmodel, "Background Model")

        # Tab 6: Gradient Magnitude
        tab_magnitude = QWidget()
        tab_magnitude_layout = QVBoxLayout(tab_magnitude)
        self.magnitude_widget = GradientMagnitudeWidget()
        tab_magnitude_layout.addWidget(self.magnitude_widget)
        self.tabs.addTab(tab_magnitude, "Gradient Magnitude")

        # Tab 7: Subtraction Preview
        tab_preview = QWidget()
        tab_preview_layout = QVBoxLayout(tab_preview)
        self.preview_widget = SubtractionPreviewWidget()
        tab_preview_layout.addWidget(self.preview_widget)
        self.tabs.addTab(tab_preview, "Subtraction Preview")

        # Tab 8: FWHM / Eccentricity
        tab_fwhm = QWidget()
        tab_fwhm_layout = QVBoxLayout(tab_fwhm)
        self.fwhm_widget = FWHMMapWidget()
        tab_fwhm_layout.addWidget(self.fwhm_widget)
        self.tabs.addTab(tab_fwhm, "FWHM / Eccentricity")

        # Tab 9: Residual Map with Exclusion Mask
        tab_residual = QWidget()
        tab_residual_layout = QVBoxLayout(tab_residual)
        self.residual_mask_widget = ResidualMaskWidget()
        tab_residual_layout.addWidget(self.residual_mask_widget)
        self.tabs.addTab(tab_residual, "Residuals / Mask")

        r_layout.addWidget(self.tabs, 3)

        # Results section (below tabs) — scrollable
        results_group = QGroupBox("Analysis Results")
        results_group_layout = QVBoxLayout(results_group)
        results_group_layout.setContentsMargins(2, 2, 2, 2)

        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results_scroll.setMinimumHeight(100)
        results_scroll.setMaximumHeight(220)

        self.lbl_results = QLabel("")
        self.lbl_results.setStyleSheet(
            "font-size: 10pt; color: #e0e0e0; font-family: 'Courier New', monospace; padding: 5px;"
        )
        self.lbl_results.setWordWrap(True)
        self.lbl_results.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_results.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        results_scroll.setWidget(self.lbl_results)
        results_group_layout.addWidget(results_scroll)

        r_layout.addWidget(results_group)

        # Suggestions section — scrollable
        suggestions_group = QGroupBox("Recommendations")
        suggestions_group_layout = QVBoxLayout(suggestions_group)
        suggestions_group_layout.setContentsMargins(2, 2, 2, 2)

        suggestions_scroll = QScrollArea()
        suggestions_scroll.setWidgetResizable(True)
        suggestions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        suggestions_scroll.setMinimumHeight(100)
        suggestions_scroll.setMaximumHeight(250)

        self.lbl_suggestions = QLabel("")
        self.lbl_suggestions.setStyleSheet(
            "font-size: 10pt; color: #ccddff; font-family: 'Courier New', monospace; padding: 5px;"
        )
        self.lbl_suggestions.setWordWrap(True)
        self.lbl_suggestions.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_suggestions.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        suggestions_scroll.setWidget(self.lbl_suggestions)
        suggestions_group_layout.addWidget(suggestions_scroll)
        r_layout.addWidget(suggestions_group)

        # Button row
        btn_row = QHBoxLayout()

        btn_copy = QPushButton("Copy Results")
        _nofocus(btn_copy)
        btn_copy.setToolTip("Copy analysis results and recommendations as plain text")
        btn_copy.clicked.connect(self._copy_results_to_clipboard)
        btn_row.addWidget(btn_copy)

        btn_copy_samples = QPushButton("Copy Sample Points")
        _nofocus(btn_copy_samples)
        btn_copy_samples.setToolTip(
            "Copy generated subsky sample point commands (setref/addref) to clipboard"
        )
        btn_copy_samples.clicked.connect(self._copy_sample_points_to_clipboard)
        btn_row.addWidget(btn_copy_samples)

        btn_clear_points = QPushButton("Clear Points")
        _nofocus(btn_clear_points)
        btn_clear_points.setToolTip("Remove all manually placed sample points from the heatmap")
        btn_clear_points.clicked.connect(self._clear_manual_points)
        btn_row.addWidget(btn_clear_points)

        # Manual sample point count label
        self.lbl_manual_points = QLabel("")
        self.lbl_manual_points.setStyleSheet("color: #00ff88; font-size: 8pt;")
        btn_row.addWidget(self.lbl_manual_points)

        r_layout.addLayout(btn_row)

        # Second button row: Export Report + Temporal Analysis
        btn_row2 = QHBoxLayout()

        btn_export_report = QPushButton("Export Report")
        _nofocus(btn_export_report)
        btn_export_report.setToolTip(
            "Save a comprehensive plain-text analysis report to a .txt file.\n"
            "Suitable for forum posting, documentation, or record-keeping."
        )
        btn_export_report.clicked.connect(self._on_export_report)
        btn_row2.addWidget(btn_export_report)

        btn_temporal = QPushButton("Temporal Analysis...")
        _nofocus(btn_temporal)
        btn_temporal.setToolTip(
            "Analyze a directory of FITS sub-frames for gradient evolution over time.\n"
            "Correlates gradient strength with DATE-OBS timestamps.\n"
            "Requires astropy."
        )
        btn_temporal.clicked.connect(self._on_temporal_analysis)
        btn_row2.addWidget(btn_temporal)

        r_layout.addLayout(btn_row2)

        return right

    # ------------------------------------------------------------------
    # INIT UI
    # ------------------------------------------------------------------

    def init_ui(self) -> None:
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.addWidget(self._build_left_panel())
        layout.addWidget(self._build_right_panel(), 1)
        self.setWindowTitle("Siril Gradient Analyzer")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 800)

    # ------------------------------------------------------------------
    # PERSISTENT SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self._settings
        self.spin_cols.setValue(int(s.value("grid_cols", 16)))
        self.spin_rows.setValue(int(s.value("grid_rows", 16)))
        self.spin_sigma.setValue(float(s.value("sigma", 2.5)))
        self.chk_smoothing.setChecked(s.value("smoothing", True, type=bool))
        self.chk_3d.setChecked(s.value("show_3d", True, type=bool))
        self.chk_rgb_separate.setChecked(s.value("rgb_separate", False, type=bool))
        self.chk_sample_guide.setChecked(s.value("sample_guide", True, type=bool))
        self.chk_image_underlay.setChecked(s.value("image_underlay", False, type=bool))
        self.chk_save_png.setChecked(s.value("save_png", False, type=bool))
        self.chk_save_json.setChecked(s.value("save_json", False, type=bool))
        preset_idx = int(s.value("preset_index", 0))
        if 0 <= preset_idx < self.combo_preset.count():
            self.combo_preset.setCurrentIndex(preset_idx)

    def _save_settings(self) -> None:
        s = self._settings
        s.setValue("grid_cols", self.spin_cols.value())
        s.setValue("grid_rows", self.spin_rows.value())
        s.setValue("sigma", self.spin_sigma.value())
        s.setValue("smoothing", self.chk_smoothing.isChecked())
        s.setValue("show_3d", self.chk_3d.isChecked())
        s.setValue("rgb_separate", self.chk_rgb_separate.isChecked())
        s.setValue("sample_guide", self.chk_sample_guide.isChecked())
        s.setValue("image_underlay", self.chk_image_underlay.isChecked())
        s.setValue("save_png", self.chk_save_png.isChecked())
        s.setValue("save_json", self.chk_save_json.isChecked())
        s.setValue("preset_index", self.combo_preset.currentIndex())

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # SIRIL IMAGE LOADING
    # ------------------------------------------------------------------

    def _load_from_siril(self) -> bool:
        no_image_msg = "No image is currently loaded in Siril. Please load a FITS image first."
        try:
            if not self.siril.connected:
                self.siril.connect()
            with self.siril.image_lock():
                fit = self.siril.get_image()
                fit.ensure_data_type(np.float32)
                self._image_data = np.array(fit.data, dtype=np.float32)
                self._img_channels = fit.channels
                self._img_width = fit.width
                self._img_height = fit.height

            self._ch_str = f"{self._img_channels} channel{'s' if self._img_channels > 1 else ''}"
            self.lbl_image_info.setText(
                f"Image: {self._img_width} x {self._img_height} px, {self._ch_str}"
            )
            self.lbl_image_info.setStyleSheet("font-size: 10pt; color: #88aaff;")
            self._log(f"Image loaded: {self._img_width} x {self._img_height} px, {self._ch_str}")
            return True

        except NoImageError:
            QMessageBox.warning(self, "No Image", no_image_msg)
        except SirilConnectionError:
            QMessageBox.warning(
                self, "Connection Timeout",
                "The connection to Siril timed out. Ensure a FITS image is loaded and try again."
            )
        except SirilError as e:
            err = str(e).lower()
            if "no image" in err or "fits" in err:
                QMessageBox.warning(self, "No Image", no_image_msg)
            else:
                QMessageBox.critical(self, "Siril Error", f"Siril error: {e}")
        except (OSError, ConnectionError, RuntimeError):
            QMessageBox.warning(self, "No Image", no_image_msg)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load image: {e}\n\n{traceback.format_exc()}"
            )
        return False

    def _on_refresh_and_analyze(self) -> None:
        if self._load_from_siril():
            # Reset colorbar lock for new image data
            self._locked_vmin = None
            self._locked_vmax = None
            self._run_count = 0
            self._on_analyze()

    # ------------------------------------------------------------------
    # ANALYSIS
    # ------------------------------------------------------------------

    def _update_progress(self, value: int, label: str = "") -> None:
        self.progress_bar.setValue(value)
        if label:
            self.progress_bar.setFormat(label)
        QApplication.processEvents()

    def _on_analyze(self) -> None:
        if self._image_data is None:
            if not self._load_from_siril():
                return

        grid_rows = self.spin_rows.value()
        grid_cols = self.spin_cols.value()
        sigma = self.spin_sigma.value()
        smoothing = self.chk_smoothing.isChecked()
        show_3d = self.chk_3d.isChecked()
        rgb_separate = self.chk_rgb_separate.isChecked()
        save_png = self.chk_save_png.isChecked()
        sample_guide = self.chk_sample_guide.isChecked()
        image_underlay = self.chk_image_underlay.isChecked()
        cmap = "inferno"
        preset_name = self.combo_preset.currentText()
        active_thresholds = build_thresholds(preset_name)

        # Show progress bar
        self.progress_bar.setVisible(True)
        self._update_progress(0, "Starting analysis...")

        self._log(f"Analysis started — Grid: {grid_cols}x{grid_rows}, Sigma-Clip: {sigma}")
        self._log(f"Image: {self._img_width} x {self._img_height} px, {self._ch_str}")

        tile_h = self._img_height // grid_rows
        tile_w = self._img_width // grid_cols
        self._log(f"Tile size: {tile_w} x {tile_h} px")

        # Adaptive grid resolution warning
        if tile_w < MIN_TILE_PX or tile_h < MIN_TILE_PX:
            self._log(f"WARNING: Tile size {tile_w}x{tile_h} px is very small — "
                       f"sigma-clipping may be unreliable. Consider reducing grid resolution.")
            QMessageBox.warning(
                self, "Small Tile Warning",
                f"Tile size is only {tile_w} x {tile_h} pixels.\n\n"
                f"With fewer than {MIN_TILE_PX} pixels per dimension, sigma-clipping "
                f"becomes unreliable and results may be noisy.\n\n"
                f"Consider reducing the grid to {max(4, self._img_width // MIN_TILE_PX)}x"
                f"{max(4, self._img_height // MIN_TILE_PX)} or fewer."
            )

        # Store previous results for before/after comparison
        if self._last_metrics is not None:
            self._previous_metrics = self._last_metrics
            self._previous_tile_medians = self._last_tile_medians

        self._update_progress(10, "Computing luminance...")

        # Compute luminance
        luminance = compute_luminance(self._image_data)

        # Prepare auto-stretched image for underlay (if requested)
        underlay_data = auto_stretch(luminance) if image_underlay else None

        self._update_progress(20, "Analyzing tile grid...")

        # Grid analysis (with per-tile stds for confidence and rejection rates)
        tile_medians, tile_stds, tile_rejections = compute_tile_grid(
            luminance, grid_rows, grid_cols, sigma,
            return_stds=True, return_rejections=True,
        )

        self._update_progress(35, "Computing metrics...")

        metrics = compute_gradient_metrics(tile_medians)
        quadrant_data = compute_quadrant_summary(tile_medians)
        vignetting_data = detect_vignetting(tile_medians)
        complexity_data = estimate_gradient_complexity(tile_medians)
        edge_center_data = compute_edge_center_ratio(tile_medians)
        confidence_data = compute_confidence(tile_medians, tile_stds)

        # v1.4 analysis
        linear_data_info = check_linear_data(tile_medians)
        star_density_info = check_star_density(tile_rejections)

        # v1.5 analysis
        symmetry_info = check_vignetting_symmetry(tile_medians)
        gradient_free_info = compute_gradient_free_pct(tile_medians)
        extended_obj_info = detect_extended_objects(tile_medians, tile_rejections)
        hotspot_info = detect_hotspots(tile_medians)

        # v1.7: Detect stacking edges and build weight mask for robust fitting
        stacking_edge_info = detect_stacking_edges(
            luminance, grid_rows, grid_cols,
        )
        weight_mask = build_weight_mask(
            tile_medians,
            extended_tiles=extended_obj_info["flagged_tiles"],
            hotspot_tiles=hotspot_info["hotspots"],
            edge_tiles=stacking_edge_info["edge_tiles"],
            star_dense_tiles=tile_rejections,
        )

        # v1.4: Background model — now uses weighted fitting
        bg_model = compute_background_model(
            tile_medians, complexity_data["best_degree"],
            weight_mask=weight_mask,
        )
        grad_magnitude = compute_gradient_magnitude(tile_medians)

        # v1.5 continued
        panel_info = detect_panel_boundaries(tile_medians, grad_magnitude)
        prediction_info = predict_improvement(tile_medians, bg_model, metrics)

        # Generate sample point commands
        sample_data = generate_sample_points(
            tile_medians, self._img_width, self._img_height,
            extended_object_tiles=extended_obj_info["flagged_tiles"],
        )
        self._last_sample_commands = sample_data["siril_commands"]

        # v1.6 analysis
        residual_pattern_info = detect_residual_pattern(tile_medians, bg_model)
        sigma_suggestion = suggest_sigma(star_density_info, sigma)

        # v1.7 analysis
        banding_info = detect_banding(tile_medians, bg_model)
        cos4_info = compute_cos4_correction(tile_medians)
        normalization_info = detect_normalization(self._image_data)

        # v1.7: Per-channel direction analysis (computed after channel analysis below)
        channel_direction_info = None

        # v1.8 analysis
        fits_header_info = read_fits_calibration_headers(self._image_data)
        amp_glow_info = detect_amp_glow(tile_medians)

        # v1.8: Geographic LP direction (needs WCS from FITS header)
        geo_direction_info = compute_geographic_lp_direction(
            metrics["angle_deg"],
            fits_header_info.get("wcs_rotation"),
        )

        # v1.8: Photometric sky brightness (needs SPCC + plate scale + exposure)
        sky_brightness_info = compute_sky_brightness(
            metrics,
            fits_header_info.get("plate_scale"),
            fits_header_info.get("exposure"),
            fits_header_info.get("spcc_applied", False),
        )

        self._update_progress(42, "Computing metrics...")

        self._last_metrics = metrics
        self._last_tile_medians = tile_medians
        self._last_complexity = complexity_data
        self._last_weight_mask = weight_mask
        self._run_count += 1

        # Linear data warning
        if not linear_data_info["is_linear"]:
            self._log(f"WARNING: Data appears stretched/non-linear (median={linear_data_info['median_level']:.3f}). "
                       "Results are most accurate on linear data before stretching.")

        # Star density warning
        if star_density_info["warning"]:
            self._log(f"WARNING: {star_density_info['warning']}")

        # Lock colorbar range on first run; reuse for subsequent runs
        if self._run_count == 1:
            self._locked_vmin = float(np.min(tile_medians))
            self._locked_vmax = float(np.max(tile_medians))

        self._update_progress(50, "Rendering heatmap...")

        # --- Update visualizations ---

        # Heatmap (with sample point guidance, gradient arrow, and locked colorbar range)
        show_arrow = metrics["strength_pct"] >= 2.0
        self.heatmap_widget.render_heatmap(
            tile_medians, self._img_width, self._img_height,
            cmap_name=cmap, smoothing=smoothing,
            show_sample_guide=sample_guide and show_arrow,
            vmin=self._locked_vmin, vmax=self._locked_vmax,
            image_underlay=underlay_data,
            gradient_arrow=(metrics["min_pos"], metrics["max_pos"]) if show_arrow else None,
        )

        self._update_progress(55, "Rendering 3D / profiles...")

        # 3D view
        if show_3d:
            self.surface_widget.setVisible(True)
            self.surface_widget.render_surface(
                tile_medians, img_width=self._img_width, img_height=self._img_height, cmap_name=cmap,
            )
        else:
            self.surface_widget.setVisible(False)
            self.surface_widget.clear()

        # Profiles
        self.profile_widget.render_profiles(tile_medians, self._img_width, self._img_height)

        self._update_progress(70, "Rendering histogram...")

        # Tile histogram
        self.tile_hist_widget.render_histogram(tile_medians)

        self._update_progress(75, "Channel analysis...")

        # Channel comparison + per-channel metrics for recommendations
        channel_metrics = None
        if rgb_separate and self._img_channels == 3:
            ch_medians = {}
            ch_metrics = {}
            for ch_key, ch_idx in (("r", 0), ("g", 1), ("b", 2)):
                ch_medians[ch_key] = compute_tile_grid(self._image_data[ch_idx], grid_rows, grid_cols, sigma)
                ch_metrics[ch_key] = compute_gradient_metrics(ch_medians[ch_key])
            channel_metrics = ch_metrics
            self.channel_widget.render_channels(
                ch_medians["r"], ch_medians["g"], ch_medians["b"],
                ch_metrics["r"], ch_metrics["g"], ch_metrics["b"],
                cmap_name=cmap, smoothing=smoothing,
            )
        else:
            self.channel_widget.clear()
        self._last_channel_metrics = channel_metrics

        # LP color characterization (requires per-channel data)
        lp_color_info = None
        if channel_metrics is not None:
            lp_color_info = characterize_lp_color(channel_metrics)
            # v1.7: Per-channel gradient direction
            channel_direction_info = compute_channel_directions(channel_metrics)
            # v1.8: Update geographic direction with per-channel info
            geo_direction_info = compute_geographic_lp_direction(
                metrics["angle_deg"],
                fits_header_info.get("wcs_rotation"),
                channel_direction_info,
            )

        self._update_progress(80, "Rendering background model...")

        # Background model preview
        self.bg_model_widget.render_model(
            tile_medians, bg_model, complexity_data["best_degree"],
            self._img_width, self._img_height, smoothing=smoothing,
        )

        # Gradient magnitude map
        self.magnitude_widget.render_magnitude(
            grad_magnitude, self._img_width, self._img_height, smoothing=smoothing,
        )

        # Subtraction preview (pixel-resolution before/after)
        self.preview_widget.render_preview(
            luminance, bg_model, self._img_width, self._img_height,
            grid_rows, grid_cols,
        )

        # v1.7: FWHM / Eccentricity map
        self._update_progress(82, "Computing FWHM map...")
        try:
            fwhm_data = compute_fwhm_map(luminance, grid_rows, grid_cols, sigma)
            self.fwhm_widget.render_fwhm_map(
                fwhm_data, self._img_width, self._img_height,
            )
        except (ValueError, RuntimeError, ImportError):
            fwhm_data = None
            self.fwhm_widget.clear()

        # v1.8: Dew/frost detection (needs FWHM data)
        dew_info = detect_dew_frost(fwhm_data, vignetting_data, tile_medians)

        # v1.8: Residual map with exclusion mask
        self.residual_mask_widget.render_residual_map(
            tile_medians, bg_model, weight_mask,
            self._img_width, self._img_height,
        )

        # v1.8: Update geographic direction with per-channel info (computed later)
        # This will be updated after channel analysis

        self._update_progress(85, "Building results...")

        # Sigma suggestion hint
        if sigma_suggestion["needs_change"]:
            self.lbl_sigma_hint.setText(
                f"\u2192 Suggest: {sigma_suggestion['suggested_sigma']:.1f} "
                f"({sigma_suggestion['reason'][:60]}...)"
            )
        else:
            self.lbl_sigma_hint.setText("")

        # Gauge (with active thresholds)
        assessment_text, _ = get_gradient_assessment(metrics["strength_pct"], active_thresholds)
        self.gauge_widget.set_value(metrics["strength_pct"], assessment_text)

        # Quadrant display
        self.quadrant_widget.set_data(quadrant_data)

        # Results text
        self._display_results(
            metrics, quadrant_data, vignetting_data, complexity_data,
            edge_center_data, confidence_data,
            linear_data_info=linear_data_info,
            star_density_info=star_density_info,
            lp_color_info=lp_color_info,
            symmetry_info=symmetry_info,
            gradient_free_info=gradient_free_info,
            extended_obj_info=extended_obj_info,
            hotspot_info=hotspot_info,
            panel_info=panel_info,
            prediction_info=prediction_info,
            sample_data=sample_data,
            residual_pattern_info=residual_pattern_info,
            thresholds=active_thresholds,
            banding_info=banding_info,
            cos4_info=cos4_info,
            stacking_edge_info=stacking_edge_info,
            fwhm_data=fwhm_data,
            channel_direction_info=channel_direction_info,
            normalization_info=normalization_info,
            fits_header_info=fits_header_info,
            geo_direction_info=geo_direction_info,
            sky_brightness_info=sky_brightness_info,
            dew_info=dew_info,
            amp_glow_info=amp_glow_info,
        )

        # Tool-specific suggestions with workflow (includes per-channel data)
        suggestions = suggest_tool_and_workflow(
            metrics, vignetting_data, complexity_data, edge_center_data, confidence_data,
            channel_metrics=channel_metrics,
            banding_info=banding_info,
            amp_glow_info=amp_glow_info,
            dew_info=dew_info,
            normalization_info=normalization_info,
            fits_header_info=fits_header_info,
            fwhm_data=fwhm_data,
        )
        self._display_suggestions(suggestions)

        # Store report data for export
        self._last_report_data = dict(
            metrics=metrics, quadrant_data=quadrant_data,
            vignetting_data=vignetting_data, complexity_data=complexity_data,
            edge_center_data=edge_center_data, confidence_data=confidence_data,
            suggestions=suggestions,
            linear_data_info=linear_data_info, star_density_info=star_density_info,
            lp_color_info=lp_color_info, symmetry_info=symmetry_info,
            gradient_free_info=gradient_free_info, extended_obj_info=extended_obj_info,
            prediction_info=prediction_info,
            banding_info=banding_info, cos4_info=cos4_info,
            stacking_edge_info=stacking_edge_info, fwhm_data=fwhm_data,
            channel_direction_info=channel_direction_info,
            normalization_info=normalization_info,
            fits_header_info=fits_header_info,
            geo_direction_info=geo_direction_info,
            sky_brightness_info=sky_brightness_info,
            dew_info=dew_info, amp_glow_info=amp_glow_info,
            img_width=self._img_width, img_height=self._img_height,
            grid_rows=grid_rows, grid_cols=grid_cols, sigma=sigma,
        )

        # Show linear data warning dialog (first time only per session)
        if not linear_data_info["is_linear"] and self._run_count == 1:
            QMessageBox.information(
                self, "Non-Linear Data Detected",
                f"The image appears to be stretched (median background = "
                f"{linear_data_info['median_level']:.3f}).\n\n"
                f"Gradient analysis works best on linear data (before stretching).\n"
                f"Results are still shown but may be less accurate for tool recommendations.",
            )

        self._update_progress(95, "Logging to Siril...")

        # Log to Siril
        self._log_results(
            metrics, quadrant_data, vignetting_data, complexity_data,
            edge_center_data, confidence_data, suggestions,
            linear_data_info=linear_data_info,
            star_density_info=star_density_info,
            lp_color_info=lp_color_info,
            symmetry_info=symmetry_info,
            gradient_free_info=gradient_free_info,
            extended_obj_info=extended_obj_info,
            hotspot_info=hotspot_info,
            panel_info=panel_info,
            prediction_info=prediction_info,
            residual_pattern_info=residual_pattern_info,
            banding_info=banding_info,
            stacking_edge_info=stacking_edge_info,
            cos4_info=cos4_info,
            fwhm_data=fwhm_data,
            channel_direction_info=channel_direction_info,
            normalization_info=normalization_info,
            fits_header_info=fits_header_info,
            geo_direction_info=geo_direction_info,
            sky_brightness_info=sky_brightness_info,
            dew_info=dew_info,
            amp_glow_info=amp_glow_info,
        )

        # Save PNG (with annotations if metrics available)
        if save_png:
            self._save_heatmap_png(metrics=metrics, thresholds=active_thresholds)

        # Save gradient history log
        try:
            cwd = os.getcwd()
            history_path = os.path.join(cwd, "gradient_history.json")
            history = save_history_entry(history_path, metrics, complexity_data)
            # Display history sparkline
            if len(history) > 1:
                vals = [f"{e['strength_pct']:.1f}%" for e in history[-8:]]
                arrow = " \u2192 "
                self.lbl_history.setText(f"History: {arrow.join(vals)}")
            else:
                self.lbl_history.setText("")
        except (OSError, ValueError, KeyError):
            pass

        # Save analysis JSON + compare with previous
        save_json = self.chk_save_json.isChecked()
        if save_json:
            self._save_analysis_json(
                metrics, complexity_data, vignetting_data, edge_center_data,
                confidence_data, linear_data_info, star_density_info,
                gradient_free_info, grid_rows, grid_cols, sigma,
                lp_color_info=lp_color_info,
                symmetry_info=symmetry_info,
                extended_obj_info=extended_obj_info,
                panel_info=panel_info,
                hotspot_info=hotspot_info,
                prediction_info=prediction_info,
            )

        self._update_progress(100, "Done")
        self.progress_bar.setVisible(False)

    def _display_results(
        self, metrics: dict, quadrant_data: dict, vignetting_data: dict,
        complexity_data: dict, edge_center_data: dict, confidence_data: dict,
        linear_data_info: dict | None = None,
        star_density_info: dict | None = None,
        lp_color_info: dict | None = None,
        symmetry_info: dict | None = None,
        gradient_free_info: dict | None = None,
        extended_obj_info: dict | None = None,
        hotspot_info: dict | None = None,
        panel_info: dict | None = None,
        prediction_info: dict | None = None,
        sample_data: dict | None = None,
        residual_pattern_info: dict | None = None,
        thresholds: list | None = None,
        banding_info: dict | None = None,
        cos4_info: dict | None = None,
        stacking_edge_info: dict | None = None,
        fwhm_data: dict | None = None,
        channel_direction_info: dict | None = None,
        normalization_info: dict | None = None,
        fits_header_info: dict | None = None,
        geo_direction_info: dict | None = None,
        sky_brightness_info: dict | None = None,
        dew_info: dict | None = None,
        amp_glow_info: dict | None = None,
    ) -> None:
        assessment, color = get_gradient_assessment(metrics["strength_pct"], thresholds)
        direction = angle_to_direction(metrics["angle_deg"])
        quads = quadrant_data["quadrants"]

        lines = [
            f"<b>Gradient Strength:   {metrics['strength_pct']:.1f} %</b>"
            f"  &nbsp; <span style='color:{confidence_data['color']}'>"
            f"Confidence: {confidence_data['label']} ({confidence_data['score']:.0%})</span>",
            f"<span style='color:{color}'>{assessment}</span>",
            f"Direction:           {metrics['angle_deg']:.0f}\u00b0 ({direction})",
            "",
            f"Background Min:      {metrics['bg_min']:.6f}     Max: {metrics['bg_max']:.6f}",
            f"Background Range:    {metrics['bg_range']:.6f}     Median: {metrics['bg_median']:.6f}",
            f"Uniformity (CV):     {metrics['uniformity']:.1f} %",
            "",
            f"<b>Complexity:</b> {complexity_data['description']}",
            f"  Polynomial fit: deg1 R\u00b2={complexity_data['r2_by_degree'][1]:.3f}  "
            f"deg2 R\u00b2={complexity_data['r2_by_degree'][2]:.3f}  "
            f"deg3 R\u00b2={complexity_data['r2_by_degree'][3]:.3f}  "
            f"\u2192 <b>recommended degree: {complexity_data['best_degree']}</b>",
            "",
            f"<b>Pattern:</b> {vignetting_data['diagnosis']}",
            f"  Radial R\u00b2={vignetting_data['radial_r2']:.3f}  |  "
            f"Linear R\u00b2={vignetting_data['linear_r2']:.3f}  |  "
            f"Edge/Center ratio: {edge_center_data['ratio']:.3f}",
            f"  {edge_center_data['diagnosis']}",
            "",
            f"<b>Quadrants:</b>  NW={quads['NW']:.6f}  NE={quads['NE']:.6f}  "
            f"SW={quads['SW']:.6f}  SE={quads['SE']:.6f}",
            f"  Brightest: <span style='color:#ff8888'>{quadrant_data['brightest']}</span>"
            f"  |  Darkest: <span style='color:#88ff88'>{quadrant_data['darkest']}</span>"
            f"  |  Spread: {quadrant_data['spread']:.6f}",
        ]

        # Artifact caveat — when critical issues are present, the reported
        # gradient % includes their contribution and is not purely sky gradient.
        _has_artifacts = (
            (banding_info and (banding_info.get("has_row_banding") or banding_info.get("has_col_banding")))
            or (amp_glow_info and amp_glow_info.get("has_amp_glow"))
            or (dew_info and dew_info.get("has_dew"))
            or (fits_header_info and fits_header_info.get("flat_applied") is False)
        )
        if _has_artifacts and metrics["strength_pct"] >= 5.0:
            lines.append(
                "<span style='color:#ffaa33'><i>Note: the gradient % above includes "
                "contributions from detected artifacts (banding, amp glow, missing flats, etc.). "
                "The true sky gradient may be significantly lower.</i></span>"
            )

        # Linear data warning
        if linear_data_info is not None and not linear_data_info["is_linear"]:
            lines.append("")
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>Non-linear data</b> (median={linear_data_info['median_level']:.3f})"
                f" — {linear_data_info['warning']}</span>"
            )

        # Star density warning
        if star_density_info is not None and star_density_info["warning"]:
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>Dense star field</b>"
                f" — {star_density_info['dense_tile_pct']:.0f}% of tiles exceed"
                f" {star_density_info['max_rejection']:.0f}% rejection rate</span>"
            )

        # LP color characterization
        if lp_color_info is not None:
            lines.append("")
            lines.append(
                f"<b>Light Pollution Color:</b> {lp_color_info['lp_type']}"
                f"  (dominant: <span style='color:#ff8888'>R</span>={lp_color_info['channel_strengths']['R']:.1f}%"
                f"  <span style='color:#88ff88'>G</span>={lp_color_info['channel_strengths']['G']:.1f}%"
                f"  <span style='color:#8888ff'>B</span>={lp_color_info['channel_strengths']['B']:.1f}%)"
            )
            lines.append(f"  {lp_color_info['description']}")

        # Gradient-free percentage
        if gradient_free_info is not None:
            lines.append("")
            lines.append(
                f"<b>Coverage:</b> {gradient_free_info['uniform_pct']:.0f}% gradient-free"
                f"  |  {gradient_free_info['gradient_pct']:.0f}% affected"
            )
            lines.append(f"  {gradient_free_info['description']}")

        # Vignetting symmetry
        if symmetry_info is not None and symmetry_info["max_asymmetry_pct"] > 1.0:
            asym_color = "#ffaa33" if symmetry_info["is_asymmetric"] else "#88aaff"
            lines.append("")
            lines.append(
                f"<span style='color:{asym_color}'><b>Symmetry:</b> "
                f"{symmetry_info['diagnosis']}</span>"
            )

        # Prediction
        if prediction_info is not None and metrics["strength_pct"] >= 2.0:
            pred_color = "#55aa55" if prediction_info["predicted_strength_pct"] < 2.0 else "#aaaa55"
            lines.append("")
            lines.append(
                f"<b>Prediction:</b> <span style='color:{pred_color}'>"
                f"After subsky deg {complexity_data['best_degree']}: "
                f"~{prediction_info['predicted_strength_pct']:.1f}% "
                f"({prediction_info['predicted_reduction_pct']:.0f}% reduction)</span>"
            )

        # Residual pattern
        if residual_pattern_info is not None and metrics["strength_pct"] >= 2.0:
            rp_color = "#dd6644" if residual_pattern_info["has_structure"] else "#55aa55"
            lines.append(
                f"<b>Residuals:</b> <span style='color:{rp_color}'>"
                f"{residual_pattern_info['description']}</span>"
            )

        # Hotspots
        if hotspot_info is not None and hotspot_info["count"] > 0:
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>{hotspot_info['count']} hotspot(s)</b>"
                f" — {hotspot_info['warning']}</span>"
            )

        # Extended objects
        if extended_obj_info is not None and extended_obj_info["flagged_count"] > 0:
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>Extended objects:</b> "
                f"{extended_obj_info['warning']}</span>"
            )

        # Panel boundaries
        if panel_info is not None and panel_info["is_mosaic"]:
            lines.append(
                f"<span style='color:#88aaff'>\u26a0 <b>Mosaic:</b> {panel_info['description']}</span>"
            )

        # Sample points summary
        if sample_data is not None and sample_data["points"]:
            lines.append("")
            lines.append(
                f"<b>Sample Points:</b> {len(sample_data['points'])} points generated"
                f" — click 'Copy Sample Points' for Siril commands"
            )

        # v1.7: Stacking edge artifacts
        if stacking_edge_info is not None and stacking_edge_info["has_stacking_edges"]:
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>Stacking edges:</b> "
                f"{stacking_edge_info['description']}</span>"
            )

        # v1.7: Banding / sensor bias
        if banding_info is not None and (banding_info["has_row_banding"] or banding_info["has_col_banding"]):
            lines.append(
                f"<span style='color:#dd6644'>\u26a0 <b>Sensor banding:</b> "
                f"{banding_info['description']}</span>"
            )

        # v1.7: Cos^4 vignetting profile
        if cos4_info is not None and cos4_info["corner_falloff_pct"] > 5.0:
            lines.append("")
            lines.append(
                f"<b>Cos\u2074 Vignetting:</b> {cos4_info['description']}"
            )

        # v1.7: Per-channel direction
        if channel_direction_info is not None and channel_direction_info["has_directional_difference"]:
            lines.append("")
            lines.append(
                f"<b>Channel Directions:</b> <span style='color:#ffaa33'>"
                f"{channel_direction_info['description']}</span>"
            )

        # v1.7: FWHM / eccentricity summary
        if fwhm_data is not None and fwhm_data.get("median_fwhm") is not None:
            fwhm_color = "#dd6644" if fwhm_data.get("has_tilt", False) else "#88aaff"
            lines.append("")
            lines.append(
                f"<b>Star Shape:</b> <span style='color:{fwhm_color}'>"
                f"{fwhm_data['description']}</span>"
            )

        # v1.7: Normalization detection
        if normalization_info is not None and normalization_info["is_normalized"]:
            lines.append("")
            lines.append(
                f"<span style='color:#ffaa33'>\u26a0 <b>Normalization detected:</b> "
                f"{normalization_info['description']}</span>"
            )

        # v1.8: FITS calibration status
        if fits_header_info is not None and fits_header_info.get("flat_applied") is not None:
            cal_color = "#55aa55" if fits_header_info["flat_applied"] else "#dd6644"
            lines.append("")
            lines.append(
                f"<b>Calibration:</b> <span style='color:{cal_color}'>"
                f"{fits_header_info['description']}</span>"
            )
            if fits_header_info["flat_applied"] is False:
                lines.append(
                    "<span style='color:#dd6644'>  Flat frames not applied — "
                    "vignetting cannot be corrected without flats!</span>"
                )

        # v1.8: Geographic LP direction
        if geo_direction_info is not None and geo_direction_info.get("compass"):
            lines.append("")
            lines.append(
                f"<b>LP Source Direction:</b> <span style='color:#88aaff'>"
                f"{geo_direction_info['description']}</span>"
            )

        # v1.8: Sky brightness
        if sky_brightness_info is not None and sky_brightness_info.get("has_photometry"):
            lines.append("")
            bortle = sky_brightness_info.get("bortle_estimate")
            bortle_str = f" (Bortle {bortle})" if bortle else ""
            lines.append(
                f"<b>Sky Brightness:</b> {sky_brightness_info['description']}{bortle_str}"
            )

        # v1.8: Dew/frost
        if dew_info is not None and dew_info.get("has_dew"):
            lines.append("")
            lines.append(
                f"<span style='color:#ff6644'>\u26a0 <b>DEW/FROST DETECTED:</b> "
                f"{dew_info['description']}</span>"
            )

        # v1.8: Amp glow
        if amp_glow_info is not None and amp_glow_info.get("has_amp_glow"):
            lines.append("")
            lines.append(
                f"<span style='color:#dd6644'>\u26a0 <b>Amp Glow:</b> "
                f"{amp_glow_info['description']}</span>"
            )

        # Before/After delta
        if self._previous_metrics is not None and self._run_count > 1:
            prev = self._previous_metrics
            delta_strength = metrics["strength_pct"] - prev["strength_pct"]
            delta_range = metrics["bg_range"] - prev["bg_range"]
            delta_uniformity = metrics["uniformity"] - prev["uniformity"]

            delta_color = "#55aa55" if delta_strength < 0 else "#dd4444"
            arrow = "\u2193" if delta_strength < 0 else "\u2191"

            lines.append("")
            lines.append(f"<b style='color:#88aaff'>\u0394 vs. Previous Run (run #{self._run_count}):</b>")
            lines.append(
                f"  <span style='color:{delta_color}'>Strength: {delta_strength:+.1f}% {arrow}</span>"
                f"  |  Range: {delta_range:+.6f}"
                f"  |  Uniformity: {delta_uniformity:+.1f}%"
            )
            if delta_strength < -1.0:
                lines.append("  <span style='color:#55aa55'>Improvement detected after extraction!</span>")
            elif delta_strength > 1.0:
                lines.append("  <span style='color:#dd4444'>Gradient increased — check processing.</span>")

        self.lbl_results.setText("<br>".join(lines))

    def _display_suggestions(self, suggestions: list[str]) -> None:
        html_parts = []
        for i, sug in enumerate(suggestions, 1):
            formatted = sug.replace("\n", "<br>")
            # Highlight Siril command lines (indented lines starting with "Siril:" or common commands)
            formatted = re.sub(
                r"(  Siril:.*?)(<br>|$)",
                r"<span style='color:#aaffaa; background:#1a3a1a; padding:2px 4px;'>\1</span>\2",
                formatted,
            )
            # Highlight other indented command-like lines
            formatted = re.sub(
                r"(  (?:calibrate|subsky|autobackgroundextraction).*?)(<br>|$)",
                r"<span style='color:#aaffaa; background:#1a3a1a; padding:2px 4px;'>\1</span>\2",
                formatted,
            )
            # Highlight step headers
            formatted = re.sub(
                r"(STEP \d+|OPTION [A-Z]?|RESULT|WORKFLOW|ALTERNATIVE|\u26a0 LOW CONFIDENCE)",
                r"<b style='color:#ffcc66'>\1</b>",
                formatted,
            )
            html_parts.append(f"<b>{i}.</b> {formatted}")

        self.lbl_suggestions.setText("<br><br>".join(html_parts))

    def _copy_results_to_clipboard(self) -> None:
        """Copy analysis results + recommendations as plain text to clipboard."""
        results_text = self.lbl_results.text()
        suggestions_text = self.lbl_suggestions.text()
        if not results_text and not suggestions_text:
            return
        # Strip HTML tags for plain text
        tag_re = re.compile(r"<[^>]+>")
        plain_results = tag_re.sub("", results_text).replace("&nbsp;", " ")
        plain_suggestions = tag_re.sub("", suggestions_text)
        # Replace <br> with newlines (before stripping tags)
        plain_results = self.lbl_results.text().replace("<br>", "\n").replace("<br/>", "\n")
        plain_results = tag_re.sub("", plain_results).replace("&nbsp;", " ")
        plain_suggestions = self.lbl_suggestions.text().replace("<br>", "\n").replace("<br/>", "\n")
        plain_suggestions = tag_re.sub("", plain_suggestions).replace("&nbsp;", " ")

        text = f"=== Gradient Analyzer Results ===\n{plain_results}\n\n=== Recommendations ===\n{plain_suggestions}"
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self._log("Results copied to clipboard")

    def _copy_sample_points_to_clipboard(self) -> None:
        """Copy sample point commands to clipboard (manual points take priority)."""
        manual_cmds = self.heatmap_widget.get_manual_commands()
        commands = manual_cmds if manual_cmds else self._last_sample_commands
        if not commands:
            QMessageBox.information(
                self, "No Sample Points",
                "No sample points available yet.\n"
                "Either run an analysis (auto-generates points) or\n"
                "left-click on the heatmap to place points manually.\n"
                "Right-click to remove a point.",
            )
            return
        text = "\n".join(commands)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            source = "manual" if manual_cmds else "auto-generated"
            self._log(f"Copied {len(commands)} {source} sample point commands to clipboard")

    def _clear_manual_points(self) -> None:
        """Clear all manually placed sample points."""
        self.heatmap_widget.clear_manual_points()
        self.lbl_manual_points.setText("")

    def _on_manual_points_changed(self, points: list) -> None:
        """Handle changes to manually placed sample points."""
        if points:
            self.lbl_manual_points.setText(f"{len(points)} manual point(s)")
        else:
            self.lbl_manual_points.setText("")

    def _on_apply_subsky(self) -> None:
        """Execute subsky with sample points if available, then reload and re-analyze."""
        if self._last_complexity is None:
            QMessageBox.information(
                self, "No Analysis",
                "Run an analysis first so the script knows which degree to use.",
            )
            return

        degree = self._last_complexity["best_degree"]
        samples = {1: 15, 2: 25, 3: 40}.get(degree, 25)

        # Check for manual or auto-generated sample points
        manual_cmds = self.heatmap_widget.get_manual_commands()
        auto_cmds = self._last_sample_commands
        has_points = bool(manual_cmds or auto_cmds)
        point_cmds = manual_cmds if manual_cmds else auto_cmds

        if has_points:
            msg = (
                f"This will set {len(point_cmds)} sample points, then execute:\n\n"
                + "\n".join(point_cmds[:5])
                + (f"\n  ... and {len(point_cmds) - 5} more" if len(point_cmds) > 5 else "")
                + f"\n\nsubsky -degree={degree}\n\n"
                "The current image will be modified. Continue?"
            )
        else:
            msg = (
                f"This will execute in Siril:\n\n"
                f"  subsky -degree={degree} -samples={samples}\n\n"
                "The current image will be modified. Continue?"
            )

        reply = QMessageBox.question(
            self, "Apply subsky", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if has_points:
                # Execute sample point commands first
                for cmd in point_cmds:
                    self._log(f"Executing: {cmd}")
                    self.siril.cmd(cmd)
                self._log(f"Executing: subsky -degree={degree}")
                self.siril.cmd(f"subsky -degree={degree}")
            else:
                self._log(f"Executing: subsky -degree={degree} -samples={samples}")
                self.siril.cmd(f"subsky -degree={degree} -samples={samples}")
            self._log("subsky completed — reloading and re-analyzing...")
            self._on_refresh_and_analyze()
        except (SirilError, OSError, RuntimeError) as e:
            QMessageBox.critical(
                self, "subsky Failed",
                f"Failed to execute subsky:\n{e}\n\n"
                "You can run the command manually in Siril's console.",
            )
            self._log(f"subsky error: {e}")

    def _on_auto_iterate(self, max_passes: int = 3, target_pct: float = 2.0) -> None:
        """Repeatedly apply subsky and re-analyze until gradient < target or max passes reached."""
        if self._last_complexity is None:
            QMessageBox.information(
                self, "No Analysis",
                "Run an analysis first before auto-iterating.",
            )
            return

        reply = QMessageBox.question(
            self, "Auto-iterate subsky",
            f"This will apply subsky up to {max_passes} times, re-analyzing after each pass, "
            f"until gradient drops below {target_pct:.1f}%.\n\n"
            "Each pass modifies the image. You may want to save a backup first.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for pass_num in range(1, max_passes + 1):
            degree = self._last_complexity["best_degree"]
            samples = {1: 15, 2: 25, 3: 40}.get(degree, 25)

            self._log(f"Auto-iterate pass {pass_num}/{max_passes}: "
                      f"subsky -degree={degree} -samples={samples}")
            try:
                self.siril.cmd(f"subsky -degree={degree} -samples={samples}")
            except (SirilError, OSError, RuntimeError) as e:
                self._log(f"subsky failed on pass {pass_num}: {e}")
                QMessageBox.warning(
                    self, "Auto-iterate stopped",
                    f"subsky failed on pass {pass_num}:\n{e}",
                )
                break

            # Re-analyze
            self._on_refresh_and_analyze()

            # Check if target reached
            if self._last_metrics and self._last_metrics["strength_pct"] < target_pct:
                self._log(f"Target reached after {pass_num} pass(es): "
                          f"{self._last_metrics['strength_pct']:.1f}% < {target_pct:.1f}%")
                QMessageBox.information(
                    self, "Auto-iterate complete",
                    f"Gradient reduced to {self._last_metrics['strength_pct']:.1f}% "
                    f"after {pass_num} pass(es).",
                )
                return

        final_pct = self._last_metrics["strength_pct"] if self._last_metrics else 0
        self._log(f"Auto-iterate complete: {max_passes} passes, final gradient: {final_pct:.1f}%")
        QMessageBox.information(
            self, "Auto-iterate complete",
            f"Completed {max_passes} passes. Final gradient: {final_pct:.1f}%.\n"
            f"{'Target not reached — consider GraXpert for remaining gradient.' if final_pct >= target_pct else ''}",
        )

    def _on_export_report(self) -> None:
        """Export comprehensive analysis report to a text file."""
        if self._last_report_data is None:
            QMessageBox.information(
                self, "No Analysis",
                "Run an analysis first to generate a report.",
            )
            return

        report_text = generate_analysis_report(**self._last_report_data)

        # Save to file
        cwd = os.getcwd()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(cwd, f"gradient_report_{timestamp}.txt")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report_text)
            self._log(f"Report saved to {filepath}")

            # Also copy to clipboard
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(report_text)

            QMessageBox.information(
                self, "Report Exported",
                f"Report saved to:\n{filepath}\n\nAlso copied to clipboard.",
            )
        except OSError as e:
            QMessageBox.critical(
                self, "Export Failed",
                f"Failed to save report:\n{e}",
            )

    def _on_temporal_analysis(self) -> None:
        """Run temporal gradient analysis on a directory of FITS sub-frames."""
        fits_dir = QFileDialog.getExistingDirectory(
            self, "Select directory with FITS sub-frames",
            os.getcwd(),
        )
        if not fits_dir:
            return

        self._log(f"Running temporal analysis on {fits_dir}...")
        grid_rows = self.spin_rows.value()
        grid_cols = self.spin_cols.value()
        sigma = self.spin_sigma.value()

        result = analyze_batch_temporal(fits_dir, grid_rows, grid_cols, sigma)

        if result["trend"] == "insufficient_data":
            QMessageBox.information(
                self, "Temporal Analysis",
                f"Insufficient data: {result['description']}\n\n"
                f"{result['recommendation']}",
            )
            return

        # Build results dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Temporal Gradient Analysis")
        dlg.setMinimumSize(600, 400)
        dlg_layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0; font-family: monospace;")

        lines = [
            f"<b>Temporal Gradient Analysis</b>",
            f"<br>Directory: {fits_dir}",
            f"<br>Frames analyzed: {len(result['entries'])}",
            f"<br>Trend: <b>{result['trend']}</b>",
            f"<br>{result['description']}",
            f"<br><br><b>Recommendation:</b> {result['recommendation']}",
            f"<br><br><b>Frame details:</b>",
        ]
        for e in result["entries"]:
            color = "#55aa55" if e["strength_pct"] < 2 else "#aaaa55" if e["strength_pct"] < 5 else "#dd4444"
            lines.append(
                f"<br><span style='color:{color}'>"
                f"{e['filename']:40s}  {e['date_obs']:25s}  {e['strength_pct']:5.1f}%  "
                f"{angle_to_direction(e['angle_deg'])}</span>"
            )

        text.setHtml("".join(lines))
        dlg_layout.addWidget(text)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        dlg_layout.addWidget(btn_close)
        dlg.exec()

    def _log(self, msg: str) -> None:
        try:
            self.siril.log(f"[GradientAnalyzer] {msg}")
        except (SirilError, OSError, RuntimeError):
            pass

    def _log_results(
        self, metrics: dict, quadrant_data: dict, vignetting_data: dict,
        complexity_data: dict, edge_center_data: dict, confidence_data: dict,
        suggestions: list[str],
        linear_data_info: dict | None = None,
        star_density_info: dict | None = None,
        lp_color_info: dict | None = None,
        symmetry_info: dict | None = None,
        gradient_free_info: dict | None = None,
        extended_obj_info: dict | None = None,
        hotspot_info: dict | None = None,
        panel_info: dict | None = None,
        prediction_info: dict | None = None,
        residual_pattern_info: dict | None = None,
        banding_info: dict | None = None,
        stacking_edge_info: dict | None = None,
        cos4_info: dict | None = None,
        fwhm_data: dict | None = None,
        channel_direction_info: dict | None = None,
        normalization_info: dict | None = None,
        fits_header_info: dict | None = None,
        geo_direction_info: dict | None = None,
        sky_brightness_info: dict | None = None,
        dew_info: dict | None = None,
        amp_glow_info: dict | None = None,
    ) -> None:
        assessment, _ = get_gradient_assessment(metrics["strength_pct"])
        direction = angle_to_direction(metrics["angle_deg"])
        quads = quadrant_data["quadrants"]
        sep = "\u2500" * 40
        self._log(sep)
        self._log(f"Gradient Strength:   {metrics['strength_pct']:.1f} %  "
                   f"(Confidence: {confidence_data['label']})")
        self._log(f"Assessment:          {assessment}")
        self._log(f"Gradient Direction:  {metrics['angle_deg']:.0f}\u00b0 ({direction})")
        self._log(f"Background Min:      {metrics['bg_min']:.6f}")
        self._log(f"Background Max:      {metrics['bg_max']:.6f}")
        self._log(f"Background Range:    {metrics['bg_range']:.6f}")
        self._log(f"Uniformity (CV):     {metrics['uniformity']:.1f} %")
        self._log(f"Complexity:          {complexity_data['description']}")
        self._log(f"  Recommended degree: {complexity_data['best_degree']}")
        self._log(f"Pattern:             {vignetting_data['diagnosis']}")
        self._log(f"Edge/Center ratio:   {edge_center_data['ratio']:.3f} — {edge_center_data['diagnosis']}")
        self._log(f"Quadrants: NW={quads['NW']:.6f} NE={quads['NE']:.6f} "
                   f"SW={quads['SW']:.6f} SE={quads['SE']:.6f}")

        if linear_data_info is not None and not linear_data_info["is_linear"]:
            self._log(f"\u26a0 Non-linear data (median={linear_data_info['median_level']:.3f}) — "
                       f"{linear_data_info['warning']}")
        if star_density_info is not None and star_density_info["warning"]:
            self._log(f"\u26a0 {star_density_info['warning']}")
        if lp_color_info is not None:
            self._log(f"LP Color: {lp_color_info['lp_type']} — {lp_color_info['description']}")
        if gradient_free_info is not None:
            self._log(f"Coverage: {gradient_free_info['uniform_pct']:.0f}% gradient-free — "
                       f"{gradient_free_info['description']}")
        if symmetry_info is not None and symmetry_info["is_asymmetric"]:
            self._log(f"Symmetry: {symmetry_info['diagnosis']}")
        if prediction_info is not None and metrics["strength_pct"] >= 2.0:
            self._log(f"Prediction: ~{prediction_info['predicted_strength_pct']:.1f}% after subsky "
                       f"({prediction_info['predicted_reduction_pct']:.0f}% reduction)")
        if hotspot_info is not None and hotspot_info["count"] > 0:
            self._log(f"\u26a0 {hotspot_info['warning']}")
        if extended_obj_info is not None and extended_obj_info["flagged_count"] > 0:
            self._log(f"\u26a0 {extended_obj_info['warning']}")
        if panel_info is not None and panel_info["is_mosaic"]:
            self._log(f"\u26a0 {panel_info['description']}")
        if residual_pattern_info is not None and residual_pattern_info["has_structure"]:
            self._log(f"Residuals: {residual_pattern_info['description']}")
        if banding_info is not None and (banding_info.get("has_row_banding") or banding_info.get("has_col_banding")):
            self._log(f"\u26a0 Banding: {banding_info['description']}")
        if stacking_edge_info is not None and stacking_edge_info.get("has_stacking_edges"):
            self._log(f"\u26a0 Stacking edges: {stacking_edge_info['description']}")
        if cos4_info is not None and cos4_info.get("corner_falloff_pct", 0) > 5.0:
            self._log(f"Cos\u2074: {cos4_info['description']}")
        if fwhm_data is not None and fwhm_data.get("median_fwhm") is not None:
            self._log(f"Star shape: {fwhm_data['description']}")
        if channel_direction_info is not None and channel_direction_info.get("has_directional_difference"):
            self._log(f"Channel directions: {channel_direction_info['description']}")
        if normalization_info is not None and normalization_info.get("is_normalized"):
            self._log(f"\u26a0 Normalization: {normalization_info['description']}")
        if fits_header_info is not None and fits_header_info.get("flat_applied") is not None:
            self._log(f"Calibration: {fits_header_info['description']}")
        if geo_direction_info is not None and geo_direction_info.get("compass"):
            self._log(f"LP direction: {geo_direction_info['description']}")
        if sky_brightness_info is not None and sky_brightness_info.get("has_photometry"):
            self._log(f"Sky brightness: {sky_brightness_info['description']}")
        if dew_info is not None and dew_info.get("has_dew"):
            self._log(f"\u26a0 DEW/FROST: {dew_info['description']}")
        if amp_glow_info is not None and amp_glow_info.get("has_amp_glow"):
            self._log(f"\u26a0 Amp glow: {amp_glow_info['description']}")

        if self._previous_metrics is not None and self._run_count > 1:
            delta = metrics["strength_pct"] - self._previous_metrics["strength_pct"]
            arrow = "\u2193" if delta < 0 else "\u2191"
            self._log(f"Delta vs previous:   {delta:+.1f}% {arrow}")

        for sug in suggestions:
            for line in sug.split("\n"):
                stripped = line.strip()
                if stripped:
                    self._log(stripped)
        self._log(sep)

    def _save_heatmap_png(self, metrics: dict | None = None, thresholds: list | None = None) -> None:
        try:
            cwd = os.getcwd()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gradient_heatmap_{timestamp}.png"
            path = os.path.join(cwd, filename)

            if metrics is not None:
                # Save annotated version with burned-in metrics
                self._save_annotated_heatmap(path, metrics, thresholds)
            else:
                if self.heatmap_widget.save_to_file(path):
                    self._log(f"Heatmap saved: {path}")
                else:
                    self._log("Failed to save heatmap PNG")
        except (OSError, ValueError, RuntimeError) as e:
            self._log(f"Error saving heatmap: {e}")

    def _on_batch_analyze(self) -> None:
        """Analyze a directory of FITS sub-frames and rank by gradient severity."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Sub-frames Directory", os.getcwd(),
        )
        if not directory:
            return

        # Find FITS files
        fits_exts = (".fit", ".fits", ".fts", ".FIT", ".FITS", ".FTS")
        files = [
            os.path.join(directory, f)
            for f in sorted(os.listdir(directory))
            if any(f.endswith(ext) for ext in fits_exts)
        ]
        if not files:
            QMessageBox.information(
                self, "No FITS Files",
                f"No FITS files found in:\n{directory}",
            )
            return

        self.progress_bar.setVisible(True)
        self._update_progress(0, f"Analyzing {len(files)} sub-frames...")

        grid_rows = min(12, self.spin_rows.value())
        grid_cols = min(12, self.spin_cols.value())
        sigma = self.spin_sigma.value()

        results = []
        for i, fpath in enumerate(files):
            self._update_progress(
                int((i / len(files)) * 90),
                f"Sub-frame {i + 1}/{len(files)}...",
            )
            result = analyze_single_fits(fpath, grid_rows, grid_cols, sigma)
            if result is not None:
                results.append(result)

        self._update_progress(95, "Ranking...")

        if not results:
            QMessageBox.warning(
                self, "Analysis Failed",
                "Could not analyze any FITS files.\n"
                "Ensure astropy is installed: pip install astropy",
            )
            self.progress_bar.setVisible(False)
            return

        # Sort by gradient strength (worst first)
        results.sort(key=lambda r: r["strength_pct"], reverse=True)

        # Show results in a dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sub-frame Gradient Ranking — {len(results)} files")
        dlg.setMinimumSize(700, 500)
        layout = QVBoxLayout(dlg)

        te = QTextEdit()
        te.setReadOnly(True)
        te.setStyleSheet("font-size: 10pt; color: #e0e0e0; background: #2b2b2b; font-family: 'Courier New', monospace;")

        lines = [
            f"{'Rank':<5} {'Gradient':>9} {'Uniformity':>11} {'Direction':>10}  {'Filename'}",
            "\u2500" * 70,
        ]
        for i, r in enumerate(results, 1):
            direction = angle_to_direction(r["angle_deg"])
            lines.append(
                f"{i:<5} {r['strength_pct']:>8.1f}% {r['uniformity']:>10.1f}% "
                f"{r['angle_deg']:>6.0f}\u00b0 {direction:<3}  {r['filename']}"
            )

        # Summary
        strengths = [r["strength_pct"] for r in results]
        lines.append("")
        lines.append(f"Mean gradient: {np.mean(strengths):.1f}%  |  "
                     f"Worst: {max(strengths):.1f}%  |  Best: {min(strengths):.1f}%")
        if len(results) > 3:
            # Flag worst 20%
            n_worst = max(1, len(results) // 5)
            lines.append(f"\nWorst {n_worst} sub-frame(s) — consider excluding:")
            for r in results[:n_worst]:
                lines.append(f"  {r['filename']} ({r['strength_pct']:.1f}%)")

        te.setPlainText("\n".join(lines))
        layout.addWidget(te)

        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        self._update_progress(100, "Done")
        self.progress_bar.setVisible(False)

        self._log(f"Batch analysis: {len(results)} sub-frames, "
                   f"worst={max(strengths):.1f}%, best={min(strengths):.1f}%")

        dlg.exec()

    def _save_annotated_heatmap(
        self, path: str, metrics: dict, thresholds: list | None = None,
    ) -> None:
        """Save heatmap with burned-in metrics summary for self-documenting PNG."""
        fig = self.heatmap_widget._fig
        if fig is None:
            if self.heatmap_widget.save_to_file(path):
                self._log(f"Heatmap saved (plain): {path}")
            return

        # Add annotation text at the bottom of the existing figure
        assessment, _ = get_gradient_assessment(metrics["strength_pct"], thresholds)
        direction = angle_to_direction(metrics["angle_deg"])
        annotation = (
            f"Gradient: {metrics['strength_pct']:.1f}%  |  "
            f"Dir: {metrics['angle_deg']:.0f}\u00b0 ({direction})  |  "
            f"Range: {metrics['bg_range']:.6f}  |  "
            f"{assessment}  |  "
            f"Gradient Analyzer v{VERSION}"
        )
        txt = fig.text(
            0.5, 0.01, annotation,
            ha="center", va="bottom", fontsize=8, color="#cccccc",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.3", fc="#1a1a1aee", ec="#444"),
        )

        try:
            fig.savefig(path, dpi=150, facecolor="#1e1e1e", bbox_inches="tight")
            self._log(f"Annotated heatmap saved: {path}")
        finally:
            # Remove the annotation so it doesn't persist on the displayed widget
            txt.remove()

    def _save_analysis_json(
        self, metrics, complexity_data, vignetting_data, edge_center_data,
        confidence_data, linear_data_info, star_density_info,
        gradient_free_info, grid_rows, grid_cols, sigma, **kwargs,
    ) -> None:
        try:
            cwd = os.getcwd()
            filepath = os.path.join(cwd, "gradient_analysis.json")
            # Load previous for comparison logging
            previous = load_previous_analysis(filepath)
            if previous is not None:
                prev_str = previous.get("gradient", {}).get("strength_pct")
                if prev_str is not None:
                    delta = metrics["strength_pct"] - prev_str
                    arrow = "\u2193" if delta < 0 else "\u2191"
                    self._log(f"JSON comparison: previous strength={prev_str:.1f}%, "
                               f"current={metrics['strength_pct']:.1f}%, "
                               f"delta={delta:+.1f}% {arrow}")
            save_analysis_json(
                filepath, metrics, complexity_data, vignetting_data,
                edge_center_data, confidence_data, linear_data_info,
                star_density_info, gradient_free_info,
                self._img_width, self._img_height, grid_rows, grid_cols, sigma,
                **kwargs,
            )
            self._log(f"Analysis saved: {filepath}")
        except (OSError, ValueError, TypeError) as e:
            self._log(f"Error saving JSON: {e}")

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------

    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Gradient Analyzer \u2014 Help")
        dlg.setMinimumSize(660, 620)
        layout = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(
            "Gradient Analyzer \u2014 Help\n"
            "========================\n\n"
            "This script was developed by Sven Ramuschkat.\n"
            "Web: www.svenesis.org\n"
            "GitHub: https://github.com/sramuschkat/Siril-Scripts\n\n"
            "1. OVERVIEW\n"
            "-----------\n"
            "The Gradient Analyzer reads the current image from Siril, divides it into a\n"
            "configurable grid of tiles, and computes sigma-clipped median background levels\n"
            "per tile. It helps you decide whether, how, and with which tool to apply\n"
            "background extraction.\n\n"
            "2. TABS\n"
            "-------\n"
            "  - Heatmap / 3D: Color-coded 2D heatmap with optional sample point guidance\n"
            "    overlay (green circles = good sample regions, red X = avoid) and 3D surface.\n"
            "  - Profiles: Horizontal and vertical cross-section profiles showing\n"
            "    where exactly the gradient ramps across the image.\n"
            "  - Tile Distribution: Histogram of tile median values. A tight peak\n"
            "    means uniform background; a broad/bimodal distribution = gradient.\n"
            "  - RGB Channels: Per-channel heatmaps (enable 'Analyze channels separately').\n"
            "    Useful for detecting chromaticity in light pollution.\n"
            "  - Background Model: Shows the fitted polynomial surface (what subsky\n"
            "    would subtract) and residuals after subtraction.\n"
            "  - Gradient Magnitude: Rate-of-change map highlighting where the\n"
            "    gradient changes most steeply across the image.\n"
            "  - Subtraction Preview: Side-by-side before/after gradient removal.\n"
            "  - FWHM / Eccentricity: Star shape map showing optical quality\n"
            "    variation across the field (tilt, curvature detection).\n"
            "  - Residuals / Mask: Polynomial fit residuals (blue-red diverging) and\n"
            "    the exclusion mask overlay (red tiles = excluded from fit).\n\n"
            "3. GRADIENT STRENGTH GAUGE\n"
            "--------------------------\n"
            "Color-coded bar in the left panel:\n"
            "  Green  (0-2%) : Very uniform \u2014 no extraction needed\n"
            "  Yellow (2-5%) : Slight gradient \u2014 gentle extraction recommended\n"
            "  Orange (5-15%): Significant gradient \u2014 extraction strongly recommended\n"
            "  Red    (15%+) : Strong gradient \u2014 aggressive extraction required\n\n"
            "4. CONFIDENCE INDICATOR\n"
            "-----------------------\n"
            "Shows how reliable the measurement is. Based on the ratio of gradient\n"
            "range to per-tile noise (SNR). If confidence is Low, the gradient may\n"
            "be indistinguishable from noise \u2014 try increasing grid size or sigma.\n\n"
            "5. GRADIENT COMPLEXITY\n"
            "----------------------\n"
            "Fits polynomial surfaces of degree 1, 2, and 3, comparing R-squared values.\n"
            "Determines whether the gradient is:\n"
            "  - Linear (degree 1): Simple tilt, subsky degree=1 or AutoBGE sufficient\n"
            "  - Quadratic (degree 2): Curved, subsky degree=2 recommended\n"
            "  - Cubic/complex (degree 3): Non-linear, consider GraXpert\n"
            "The recommended polynomial degree maps directly to subsky parameters.\n\n"
            "6. VIGNETTING vs. GRADIENT DETECTION\n"
            "-------------------------------------\n"
            "Two methods work together:\n"
            "  a) Radial vs. linear model fitting (R-squared comparison)\n"
            "  b) Edge-to-center brightness ratio\n"
            "     - Ratio < 1.0: Edges darker than center = vignetting\n"
            "     - Ratio > 1.0: Edges brighter = light pollution from edges\n"
            "Combined, these reliably distinguish flat calibration issues from LP.\n\n"
            "7. QUADRANT ANALYSIS\n"
            "--------------------\n"
            "Shows median background per quadrant (NW, NE, SW, SE):\n"
            "  - Red border = brightest quadrant (avoid for sample points)\n"
            "  - Green border = darkest quadrant (good for sample points)\n"
            "  - Spread value shows the total quadrant variation\n\n"
            "8. SAMPLE POINT GUIDANCE\n"
            "------------------------\n"
            "When enabled, the heatmap shows:\n"
            "  - Green circles: Tiles in the darkest 40% = good sample point locations\n"
            "  - Red X marks: Tiles in the brightest 15% = avoid these areas\n"
            "Use this to guide manual sample placement in background extraction.\n\n"
            "9. TOOL RECOMMENDATIONS\n"
            "-----------------------\n"
            "The script recommends the best tool based on your gradient:\n\n"
            "  AutoBGE (Siril built-in):\n"
            "    Automatic background extraction. Fast, no external tools.\n"
            "    Best for: moderate gradients (< 8%), simple patterns (degree 1-2).\n"
            "    Command: autobackgroundextraction\n\n"
            "  subsky (Siril built-in):\n"
            "    Polynomial background subtraction with configurable degree.\n"
            "    Best for: all gradient strengths with predictable polynomial patterns.\n"
            "    Command: subsky -degree=N -samples=M\n"
            "    The degree and sample count are suggested based on complexity analysis.\n\n"
            "  GraXpert (external, AI-based):\n"
            "    Uses AI to separate background from signal.\n"
            "    Best for: complex, non-linear, multi-directional gradients that\n"
            "    polynomial fitting cannot fully model (degree 3 still insufficient).\n"
            "    Download: https://www.graxpert.com\n\n"
            "  VeraLux Nox (Siril script):\n"
            "    Specialized light pollution removal script.\n"
            "    Best for: color-dependent LP gradients where R/G/B channels show\n"
            "    different gradient strengths (e.g. LED street lights affecting\n"
            "    blue channel more). Works on linear data.\n"
            "    Install via Siril's script repository.\n\n"
            "10. WORKFLOW GUIDANCE\n"
            "---------------------\n"
            "The Recommendations section uses priority-based ordering:\n"
            "  Priority 0: Critical hardware/calibration issues that must be fixed first\n"
            "    (banding, amp glow, dew/frost, missing flats). These cannot be solved\n"
            "    by background extraction.\n"
            "  Priority 1: Gradient extraction workflow:\n"
            "    1. Fix vignetting with flats (if detected)\n"
            "    2. Apply gradient extraction (tool depends on complexity)\n"
            "    3. Re-analyze with 'Refresh from Siril'\n"
            "    4. If gradient still > 2%, try a more powerful tool\n"
            "    5. Once uniform, proceed with stretching\n"
            "When critical issues are detected, extraction is labeled\n"
            "'AFTER FIXING ISSUES' to prevent wasted effort.\n"
            "When all polynomial fits are poor (R² < 0.5), the script recommends\n"
            "degree 1 to avoid overfitting and suggests AI-based tools instead.\n\n"
            "11. BEFORE/AFTER COMPARISON\n"
            "---------------------------\n"
            "Each re-analysis shows delta values vs. the previous run:\n"
            "  - Green arrow down = gradient reduced (extraction worked)\n"
            "  - Red arrow up = gradient increased (check processing)\n"
            "This iterative workflow lets you tune extraction step by step.\n\n"
            "12. GRID SETTINGS\n"
            "-----------------\n"
            "  - Columns / Rows: 4-64 tiles per axis. Default 16x16.\n"
            "  - Sigma-Clip: 1.5-4.0. Iterative clipping to exclude stars.\n"
            "  - A warning appears if tiles are smaller than 50 px per dimension,\n"
            "    as sigma-clipping becomes unreliable with too few pixels.\n\n"
            "13. KEYBOARD SHORTCUTS\n"
            "----------------------\n"
            "  - F5: Run analysis\n"
            "  - Ctrl+Shift+R: Refresh from Siril and re-analyze\n\n"
            "14. PERSISTENT SETTINGS\n"
            "-----------------------\n"
            "Grid size, sigma, and all checkbox options are saved\n"
            "between sessions and restored on next launch.\n\n"
            "15. COPY TO CLIPBOARD\n"
            "---------------------\n"
            "Click 'Copy Results to Clipboard' to copy analysis results and\n"
            "recommendations as plain text (useful for forum posts or notes).\n\n"
            "16. COLORBAR LOCKING\n"
            "--------------------\n"
            "On the first analysis, the heatmap colorbar range is locked.\n"
            "Subsequent runs use the same scale, making before/after comparison\n"
            "visually meaningful. Reload from Siril to reset.\n\n"
            "17. LINEAR DATA DETECTION\n"
            "-------------------------\n"
            "The analyzer checks if the image appears to be stretched (non-linear).\n"
            "If median background > 0.25, a warning is shown because gradient analysis\n"
            "is most accurate on linear data before any stretching is applied.\n\n"
            "18. GRADIENT DIRECTION ARROW\n"
            "----------------------------\n"
            "When gradient strength >= 2%, a cyan arrow is overlaid on the heatmap\n"
            "pointing from the darkest tile to the brightest tile, showing the\n"
            "dominant gradient direction.\n\n"
            "19. BACKGROUND MODEL PREVIEW\n"
            "----------------------------\n"
            "Shows the polynomial surface that subsky would subtract (left) and\n"
            "the residuals after subtraction (right). Small residuals = good fit.\n\n"
            "20. GRADIENT MAGNITUDE MAP\n"
            "--------------------------\n"
            "Shows how rapidly the background changes at each position. Hot spots\n"
            "indicate steep transitions — these need the most attention during\n"
            "background extraction.\n\n"
            "21. STAR DENSITY WARNING\n"
            "------------------------\n"
            "If many tiles have high sigma-clipping rejection rates (> 40%),\n"
            "the image contains dense star fields. This can bias background\n"
            "estimates — consider increasing sigma or reducing grid resolution.\n\n"
            "22. LIGHT POLLUTION COLOR\n"
            "-------------------------\n"
            "When RGB analysis is enabled, compares gradient strength per channel:\n"
            "  - Red-dominant: Sodium vapor (HPS) street lighting\n"
            "  - Blue-dominant: LED or mercury vapor lighting\n"
            "  - Green-dominant: Mercury vapor lighting\n"
            "  - Balanced: Broadband light pollution (sky glow)\n"
            "This helps choose the right LP filter or removal technique.\n\n"
            "23. VIGNETTING SYMMETRY\n"
            "-----------------------\n"
            "Compares opposite edge strips (NW vs SE, NE vs SW, Top vs Bottom,\n"
            "Left vs Right). Asymmetry > 2% indicates incomplete flat correction,\n"
            "tilted sensor, or optical axis misalignment.\n\n"
            "24. GRADIENT-FREE COVERAGE\n"
            "--------------------------\n"
            "Shows what percentage of tiles are in uniform regions vs. gradient-\n"
            "affected regions. Uses dual-scale analysis: a tile must pass both a\n"
            "global check (close to overall median) and a local check (close to\n"
            "3x3 neighborhood median). This prevents contradictions where a smooth\n"
            "large-scale gradient is missed by local-only comparison.\n\n"
            "25. EXTENDED OBJECT DETECTION\n"
            "-----------------------------\n"
            "Flags tiles that contain nebulae or galaxies (bright background +\n"
            "low star rejection). These can bias the gradient fit.\n\n"
            "26. SAMPLE POINT EXPORT\n"
            "------------------------\n"
            "Generates subsky sample point coordinates in the darkest, most uniform\n"
            "regions. Click 'Copy Sample Points' to get setref/addref commands\n"
            "for Siril's console.\n\n"
            "27. MOSAIC PANEL DETECTION\n"
            "--------------------------\n"
            "Detects sharp linear discontinuities in the gradient magnitude map\n"
            "that may indicate mosaic panel boundaries.\n\n"
            "28. JSON SIDECAR PERSISTENCE\n"
            "----------------------------\n"
            "Enable 'Save analysis JSON' to persist results to gradient_analysis.json.\n"
            "On re-analysis, automatically compares with the previous saved results.\n\n"
            "29. HOTSPOT DETECTION\n"
            "---------------------\n"
            "Detects outlier tiles that deviate > 3 sigma from their neighbors.\n"
            "Often indicates satellite trails, airplane lights, or sensor artifacts.\n\n"
            "30. IMPROVEMENT PREDICTION\n"
            "--------------------------\n"
            "Estimates gradient strength after polynomial subtraction using the\n"
            "background model residuals. Uses the original image median as\n"
            "reference (not the near-zero residual median) to avoid inflated\n"
            "predictions. When the predicted reduction is less than 20%, the\n"
            "script warns that extraction will be essentially ineffective.\n\n"
            "31. SUBTRACTION PREVIEW\n"
            "-----------------------\n"
            "The 'Subtraction Preview' tab shows a side-by-side comparison of the\n"
            "original luminance and the result after subtracting the fitted background\n"
            "model. Both images are auto-stretched for visibility. This lets you\n"
            "preview what gradient removal would look like before applying it.\n\n"
            "32. GRADIENT HISTORY\n"
            "--------------------\n"
            "Tracks gradient strength across analysis sessions in a JSON log file\n"
            "(gradient_history.json alongside your image). The left panel shows a\n"
            "sparkline of recent values so you can see if your processing is reducing\n"
            "the gradient over time. Up to 50 entries are retained.\n\n"
            "33. RESIDUAL PATTERN DETECTION\n"
            "------------------------------\n"
            "After polynomial subtraction, checks whether the residuals contain\n"
            "structured patterns using Moran's I spatial autocorrelation. Values\n"
            "near +1 indicate the polynomial degree is too low and systematic\n"
            "gradients remain. Values near 0 indicate good random residuals.\n\n"
            "34. CONFIGURABLE THRESHOLD PRESETS\n"
            "----------------------------------\n"
            "The threshold preset dropdown changes the gradient severity thresholds:\n"
            "  - Broadband (default): 2% / 5% / 15%\n"
            "  - Narrowband (strict): 1% / 3% / 8%\n"
            "  - Fast optics (tolerant): 4% / 8% / 20%\n"
            "Narrowband data requires stricter thresholds because narrowband filters\n"
            "amplify gradients. Fast optics (< f/4) inherently have more vignetting.\n\n"
            "35. ANNOTATED PNG EXPORT\n"
            "------------------------\n"
            "When 'Save heatmap PNG' is enabled, the exported image includes key\n"
            "metrics (gradient strength, direction, uniformity, assessment) burned\n"
            "directly into the image for easy reference without the GUI.\n\n"
            "36. SUB-FRAME BATCH RANKING\n"
            "--------------------------\n"
            "Click 'Analyze Sub-frames...' to select a directory of FITS files.\n"
            "Each file is analyzed for gradient strength and uniformity. Results\n"
            "are ranked from best to worst, helping you identify and reject frames\n"
            "with the worst gradients before stacking. Requires astropy.\n\n"
            "37. ADAPTIVE SIGMA SUGGESTION\n"
            "-----------------------------\n"
            "Based on star density (sigma-clip rejection rates), suggests whether\n"
            "to increase or decrease the sigma parameter. Dense star fields need\n"
            "lower sigma for better star exclusion; sparse fields can use higher\n"
            "sigma for more stable statistics.\n\n"
            "38. WEIGHTED BACKGROUND MODEL\n"
            "-----------------------------\n"
            "The polynomial background fit now excludes tiles flagged as extended\n"
            "objects, hotspots, stacking edge artifacts, or extremely star-dense\n"
            "regions. This produces a more accurate background model that isn't\n"
            "biased by nebulae, satellite trails, or dithering borders.\n\n"
            "39. STACKING EDGE DETECTION\n"
            "---------------------------\n"
            "Detects tapered dark borders that appear in stacked images from\n"
            "dithering or rotation. Edge tiles significantly darker than the\n"
            "interior are flagged and excluded from the gradient fit. This\n"
            "prevents false high-gradient readings from incomplete borders.\n\n"
            "40. BANDING / SENSOR BIAS DETECTION\n"
            "-----------------------------------\n"
            "Uses FFT analysis on polynomial residuals to detect periodic row\n"
            "or column patterns from sensor readout artifacts. Unlike gradients,\n"
            "banding requires bias/dark correction, not background extraction.\n"
            "The script warns when banding is detected so you don't waste time\n"
            "trying to extract a pattern that subsky can't fix.\n\n"
            "41. PER-CHANNEL GRADIENT DIRECTION\n"
            "----------------------------------\n"
            "When RGB analysis is enabled, compares gradient direction per channel.\n"
            "If channels point in different directions (> 30 degrees apart), this\n"
            "indicates multiple LP sources from different compass directions.\n"
            "Per-channel extraction or VeraLux Nox is recommended in this case.\n\n"
            "42. COS^4 VIGNETTING CORRECTION\n"
            "-------------------------------\n"
            "Estimates the natural cos^4 optical vignetting expected for the\n"
            "focal ratio and compares it against the actual falloff. This helps\n"
            "distinguish expected optical vignetting (fix with flats) from true\n"
            "gradients (fix with extraction). Particularly useful for fast optics\n"
            "(f/2 to f/4) where natural falloff is significant.\n\n"
            "43. INTERACTIVE SAMPLE POINTS\n"
            "----------------------------\n"
            "Left-click on the heatmap to manually place sample points.\n"
            "Right-click near an existing point to remove it. Manual points\n"
            "are shown as green diamonds with numbered labels. Click\n"
            "'Copy Sample Points' to get setref/addref commands — manual\n"
            "points take priority over auto-generated ones. Click 'Clear Points'\n"
            "to remove all manual placements.\n\n"
            "44. ONE-CLICK SUBSKY EXECUTION\n"
            "------------------------------\n"
            "Click 'Apply subsky & Re-analyze' to execute the recommended subsky\n"
            "command directly in Siril via the API. The script uses the degree and\n"
            "sample count determined by the complexity analysis. After execution,\n"
            "it automatically reloads the modified image and re-analyzes, showing\n"
            "the before/after delta. Saves manual copy-paste of commands.\n\n"
            "45. FWHM / ECCENTRICITY MAP\n"
            "---------------------------\n"
            "The 'FWHM / Eccentricity' tab shows how star shape varies across the\n"
            "field. FWHM (full width at half maximum) measures star size; eccentricity\n"
            "measures elongation (0 = round, 1 = line). Requires minimum 3 stars per\n"
            "tile with 3-sigma outlier rejection for reliability. Very high eccentricity\n"
            "(>= 0.40) at coarse tile resolution may reflect noise or nebulosity, not\n"
            "true star elongation — a caveat is shown in such cases. If star shape\n"
            "correlates with the gradient pattern, the issue may be optical (tilt,\n"
            "spacing, collimation) rather than light pollution.\n\n"
            "46. NORMALIZATION DETECTION\n"
            "--------------------------\n"
            "Detects whether the image has been background-normalized during stacking.\n"
            "Normalized images have artificially uniform backgrounds that can mask\n"
            "residual gradients. The script checks for suspiciously identical per-channel\n"
            "backgrounds, very low background CV, and common normalization target values.\n"
            "If detected, a warning advises analyzing before normalization.\n\n"
            "47. FITS CALIBRATION CHECK\n"
            "-------------------------\n"
            "Reads FITS header keywords (FLATCOR, DARKCOR, BIASCOR, CALSTAT) to\n"
            "determine whether flat, dark, and bias frames were applied during\n"
            "calibration. Warns explicitly if flats are missing, since vignetting\n"
            "cannot be corrected without them.\n\n"
            "48. GEOGRAPHIC LP DIRECTION\n"
            "---------------------------\n"
            "If the image is plate-solved (WCS headers present), converts the\n"
            "gradient direction from image pixel coordinates to real-world geographic\n"
            "compass bearing. Tells you 'LP comes from the South' rather than just\n"
            "'gradient points at 135 degrees'. Per-channel bearings are included\n"
            "if RGB analysis is enabled.\n\n"
            "49. PHOTOMETRIC SKY BRIGHTNESS\n"
            "------------------------------\n"
            "For SPCC-calibrated images with known plate scale and exposure time,\n"
            "converts background levels to approximate mag/arcsec\u00b2 and estimates\n"
            "the Bortle class. Useful for documenting site quality and comparing\n"
            "sessions. Requires plate-solved + SPCC-calibrated data.\n\n"
            "50. SAMPLE POINT PASSTHROUGH\n"
            "----------------------------\n"
            "When clicking 'Apply subsky & Re-analyze', the script now feeds any\n"
            "manually placed or auto-generated sample points to Siril via setref/\n"
            "addref commands before executing subsky. This gives you full control\n"
            "over where subsky samples the background, rather than relying on its\n"
            "automatic placement.\n\n"
            "51. AUTO-ITERATE EXTRACTION\n"
            "---------------------------\n"
            "Click 'Auto-iterate until <2%%' to automatically run subsky, re-analyze,\n"
            "and repeat up to 3 times until gradient drops below 2%%. Each pass uses\n"
            "the complexity analysis to choose the optimal degree. If 3 passes aren't\n"
            "enough, GraXpert is recommended for the residual.\n\n"
            "52. TEMPORAL GRADIENT ANALYSIS\n"
            "-----------------------------\n"
            "Click 'Temporal Analysis...' to analyze a directory of FITS sub-frames\n"
            "over time. Reads DATE-OBS timestamps and measures gradient per frame.\n"
            "Shows trend (improving/worsening/stable), identifies the best and worst\n"
            "periods, and recommends which subs to exclude based on gradient evolution.\n\n"
            "53. RESIDUAL MAP WITH EXCLUSION MASK\n"
            "------------------------------------\n"
            "The 'Residuals / Mask' tab shows two views:\n"
            "  Left: Polynomial fit residuals (blue-red diverging map)\n"
            "  Right: The heatmap overlaid with the exclusion mask (red = excluded tiles)\n"
            "This lets you verify which tiles were excluded from the fit and whether\n"
            "the remaining residuals are random (good) or structured (needs attention).\n\n"
            "54. DEW / FROST DETECTION\n"
            "------------------------\n"
            "Cross-correlates the FWHM map with the brightness pattern. Dew on the\n"
            "corrector plate causes: (1) radial FWHM increase from center to edges,\n"
            "(2) a bright center from light scattering. When both patterns appear\n"
            "together, a dew/frost warning is raised. Check your dew heater!\n\n"
            "55. AMPLIFIER GLOW DETECTION\n"
            "---------------------------\n"
            "Detects the characteristic exponential brightness profile of CCD/CMOS\n"
            "amplifier glow, which is always anchored to one specific corner with\n"
            "rapid falloff. Distinguished from LP (linear, edge-wide) and vignetting\n"
            "(symmetric). The proper fix is better dark calibration, not background\n"
            "extraction.\n\n"
            "56. REPORT EXPORT\n"
            "-----------------\n"
            "Click 'Export Report' to save a comprehensive plain-text analysis report\n"
            "containing all metrics, diagnostics, and recommendations. The report is\n"
            "saved as a .txt file and also copied to clipboard. Suitable for forum\n"
            "posting, documentation, or sharing your processing workflow.\n\n"
            "57. ARTIFACT-ADJUSTED GRADIENT NOTE\n"
            "-----------------------------------\n"
            "When critical artifacts are detected (banding, amp glow, dew/frost,\n"
            "missing flats), the reported gradient percentage includes their\n"
            "contribution. An italic note appears below the strength line warning\n"
            "that the true sky gradient may be significantly lower. This prevents\n"
            "users from over-extracting when the root cause is calibration, not LP.\n\n"
            "58. REQUIREMENTS\n"
            "----------------\n"
            "Siril 1.4+ with Python script support, sirilpy (bundled), numpy, PyQt6,\n"
            "matplotlib, scipy (installed automatically). Optional: astropy (for\n"
            "sub-frame batch ranking and FITS header reading).\n"
        )
        te.setStyleSheet("font-size: 10pt; color: #e0e0e0; background: #2b2b2b;")
        layout.addWidget(te)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        win = GradientAnalyzerWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Gradient Analyzer v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
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
            "Gradient Analyzer Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
