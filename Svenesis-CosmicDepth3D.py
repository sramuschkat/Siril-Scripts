"""
Svenesis CosmicDepth 3D
Script Version: 1.0.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script reads the current plate-solved image from Siril, extracts all
astronomical objects in the field of view via SIMBAD, resolves their
distances from online catalogs (SIMBAD, NED, Gaia DR3), and renders them
as an interactive rotatable 3D map -- Earth at the origin, every object
positioned in three-dimensional space.

CosmicDepth 3D makes spatial depth visible: a nebula in the foreground
at 1.300 light-years, a galaxy in the same image at 30 million light-years.

Data Sources:
- SIMBAD: object catalog + distance measurements (TAP queries)
- NED:    distance measurements for galaxies (astroquery.ned)
- Gaia DR3: precise parallax distances for bright stars
- Local JSON cache (~/.config/siril/svenesis_cosmic_depth_cache.json)

Features:
- Plate-solved image ingestion (same 6-strategy WCS detection as AnnotateImage)
- SIMBAD cone-search over the image FOV (parallel tiles for wide fields)
- Distance resolution with prioritized fallback chain
  (cache -> SIMBAD -> NED -> Redshift/Hubble -> type-median)
- Local JSON cache with 90-day TTL
- Three scaling modes: linear / logarithmic / hybrid
- Two display modes: Galactic (< 100k ly) / Cosmic (all)
- Color-coded objects by type
- Interactive 3D rendering via Plotly embedded in QWebEngineView
  (falls back to matplotlib 3D if PyQt6-WebEngine is not available)
- Export as HTML (interactive, standalone), PNG, and CSV data table
- Dark-themed PyQt6 GUI matching Svenesis AnnotateImage look & feel
- Persistent settings via QSettings

Run from Siril via Processing -> Scripts. Place this file inside a folder
named Utility in one of Siril's Script Storage Directories.

(c) 2025-2026
SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Svenesis CosmicDepth 3D
# Script Version: 1.0.0
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: processing
# Script Description: Reads objects from a plate-solved image, resolves their
#   distances from SIMBAD / NED / Gaia, and renders them as an interactive
#   3D star-map (Earth at origin). Requires a plate-solved image and an
#   internet connection (or a populated local distance cache).
# Script Author: Sven Ramuschkat

CHANGELOG:
0.1.0 - Initial release
      - Plate-solved image ingestion via sirilpy
      - SIMBAD cone-search with distance / type / size metadata
      - NED + redshift + type-median fallback chain
      - Local JSON distance cache with TTL
      - Linear / logarithmic / hybrid scaling
      - Plotly 3D renderer (QWebEngineView)
      - HTML / PNG / CSV export
      - Dark-themed PyQt6 GUI with persistent settings
"""
from __future__ import annotations

import sys
import os
import re
import gc
import json
import math
import datetime
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

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

s.ensure_installed("numpy", "PyQt6", "matplotlib", "astropy", "astroquery",
                   "plotly", "kaleido")
# PyQt6-WebEngine is a separate wheel required to embed the interactive
# (rotatable) Plotly view inside the window. If it's not installed,
# `s.ensure_installed` will fetch one — but only when it's missing, so
# a previously installed (possibly ABI-mismatched) wheel is left
# untouched and the user gets a chance to trigger the explicit
# "Repair WebEngine…" UI below. Any failure here is non-fatal; the
# script falls back to matplotlib + a browser window for the 3D view.
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _probe  # noqa
    del _probe
except Exception:
    try:
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR
            _parts = PYQT_VERSION_STR.split(".")
            _minor = (".".join(_parts[:2])
                      if len(_parts) >= 2 else PYQT_VERSION_STR)
            s.ensure_installed(f"PyQt6-WebEngine=={_minor}.*")
        except Exception:
            s.ensure_installed("PyQt6-WebEngine")
    except Exception:
        pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QSizePolicy, QDialog, QTextEdit, QTabWidget, QScrollArea,
    QProgressBar, QComboBox, QRadioButton, QButtonGroup,
    QLineEdit, QFileDialog, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QShortcut, QKeySequence, QDesktopServices, QImageReader,
)

QImageReader.setAllocationLimit(0)

# Try to load a WebEngine for interactive Plotly rendering.
# If unavailable, we fall back to a static matplotlib 3D plot and open
# the rotatable Plotly view in the user's default browser instead.
#
# ABI note: QtWebEngineWidgets must match PyQt6's Qt version exactly.
# pip-installing PyQt6-WebEngine can pull a newer wheel (e.g. Qt 6.11)
# while Siril's bundled PyQt6 is older, producing a "Symbol not found:
# _qt_version_tag_6_XX" error at import time. When that happens we do
# NOT silently force-reinstall — that surprised users and failed
# silently behind proxies. Instead the UI offers an explicit
# "Repair WebEngine…" button that runs a pinned reinstall with live
# pip stdout/stderr, and refuses to run inside a PEP 668 / externally
# managed Python interpreter. See WebEngineRepairDialog below.
WEBENGINE_ERROR = ""
QWebEngineView = None  # populated on successful import


def _try_import_webengine() -> bool:
    """Attempt to import ``QWebEngineView``; update module globals.

    Also drops any half-loaded ``PyQt6.QtWebEngine*`` submodules first so
    that a successful repair + retry inside the same process picks up the
    freshly installed wheels instead of the cached stubs from the failed
    first import.
    """
    global WEBENGINE_ERROR, QWebEngineView
    for _m in list(sys.modules):
        if _m.startswith("PyQt6.QtWebEngine"):
            del sys.modules[_m]
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView as _QWEV
        QWebEngineView = _QWEV
        WEBENGINE_ERROR = ""
        return True
    except Exception as e:
        WEBENGINE_ERROR = f"{type(e).__name__}: {e}"
        return False


HAS_WEBENGINE = _try_import_webengine()


def _is_externally_managed_python() -> bool:
    """True if the running interpreter is marked PEP 668 / externally managed.

    Pip installs in this environment will fail (or worse, damage the
    system Python), so we refuse to attempt the repair and tell the user
    to fix it manually in a venv. Checks both ``stdlib`` and ``purelib``
    for the marker to cover both Debian and downstream conventions.
    """
    import sysconfig
    for key in ("stdlib", "purelib", "platlib"):
        try:
            p = sysconfig.get_path(key)
        except Exception:
            p = None
        if p and os.path.isfile(os.path.join(p, "EXTERNALLY-MANAGED")):
            return True
    return False

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3D projection)
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from astropy.wcs import WCS
from astropy.io import fits as astropy_fits
from astropy.coordinates import SkyCoord, Angle
import astropy.units as u
from astroquery.simbad import Simbad

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

# ---------------------------------------------------------------------------
# Single source of truth for the script version. The module-level docstring,
# the "# Script Version:" metadata line at the top, the window label and the
# Siril-log banner all render this constant — don't hard-code the version
# anywhere else in this file.
# ---------------------------------------------------------------------------
VERSION = "1.0.0"

# Settings keys
SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "CosmicDepth3D"

LEFT_PANEL_WIDTH = 360


# ---------------------------------------------------------------------------
# Enums replace the legacy string keys that used to appear scattered through
# config dicts ("log" / "linear" / "hybrid", "galactic" / "cosmic"). A typo
# previously failed silently and fell back to linear; using enums pushes that
# to a KeyError that surfaces during development. Both enums subclass `str`
# so existing QSettings values (written as plain strings) still round-trip
# and the enum values can be used directly in f-strings.
# ---------------------------------------------------------------------------
from enum import Enum


class ScaleMode(str, Enum):
    LINEAR = "linear"
    LOG = "log"
    HYBRID = "hybrid"

    @classmethod
    def parse(cls, value, default: "ScaleMode" = None) -> "ScaleMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except Exception:
            return default if default is not None else cls.LOG


class DisplayMode(str, Enum):
    GALACTIC = "galactic"
    COSMIC = "cosmic"

    @classmethod
    def parse(cls, value, default: "DisplayMode" = None) -> "DisplayMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except Exception:
            return default if default is not None else cls.COSMIC


# ---------------------------------------------------------------------------
# Stretched-log axis.
# A plain log axis gives every decade the same visual width. In our data the
# interesting far-galaxy tail (≥ ~100 M ly) is where most objects cluster, so
# it ends up cramped at the far end. These helpers implement a piecewise log:
# decades below ``LOG_STRETCH_THRESHOLD_LY`` take 1 unit each, decades at/beyond
# the threshold take ``LOG_STRETCH_FACTOR`` units each. Tick labels still read
# in real light-years ("1", "10", …, "100M", "1B", "10B") — only the spacing
# changes. Tune the two constants to reshape the axis without any UI churn.
# ---------------------------------------------------------------------------
import math as _math_for_log_stretch  # local alias so constants stay self-contained

LOG_STRETCH_THRESHOLD_LY = 1.0e8  # 100 million ly — where "far galaxies" start
LOG_STRETCH_FACTOR = 3.0           # each decade beyond threshold is this much wider


def log_stretched_transform(dist_ly: float) -> float:
    """Map a light-year distance to a stretched-log axis coordinate.

    Below ``LOG_STRETCH_THRESHOLD_LY`` this is plain ``log10(d)`` (one unit
    per decade). At and beyond the threshold each decade spans
    ``LOG_STRETCH_FACTOR`` units, so 100 M → 1 B → 10 B get proportionally
    more pixels on screen. Input is clamped to ≥ 1 ly so ``log10(0)`` can't
    blow up.
    """
    d = max(float(dist_ly), 1.0)
    t = LOG_STRETCH_THRESHOLD_LY
    if d <= t:
        return _math_for_log_stretch.log10(d)
    return (_math_for_log_stretch.log10(t)
            + LOG_STRETCH_FACTOR * _math_for_log_stretch.log10(d / t))


def _fmt_ly_short(v_ly: float) -> str:
    """Human-readable SI-style ly label: '1', '10', '100', '1k', '1M', '1B', …"""
    v = float(v_ly)
    if v < 1e3:
        return f"{int(round(v))}"
    if v < 1e6:
        return f"{int(round(v / 1e3))}k"
    if v < 1e9:
        return f"{int(round(v / 1e6))}M"
    if v < 1e12:
        return f"{int(round(v / 1e9))}B"
    return f"{int(round(v / 1e12))}T"


def log_stretched_tick_positions(max_ly: float) -> tuple[list[float], list[str]]:
    """Return ``(tickvals, ticktext)`` for a stretched-log axis.

    ``tickvals`` are in transform-space (what ``log_stretched_transform``
    returns, which matches what ``scale_distance(..., LOG)`` now returns).
    Labels read in real light-years, one tick per decade from 1 ly up to the
    next power of 10 above ``max_ly``.
    """
    upper = max(float(max_ly), 10.0)
    top_exp = int(_math_for_log_stretch.ceil(_math_for_log_stretch.log10(upper)))
    top_exp = max(top_exp, 1)
    tickvals: list[float] = []
    ticktext: list[str] = []
    for exp in range(0, top_exp + 1):
        val_ly = 10.0 ** exp
        tickvals.append(log_stretched_transform(val_ly))
        ticktext.append(_fmt_ly_short(val_ly))
    return tickvals, ticktext


# ---------------------------------------------------------------------------
# Smart image-plane sample size.
# The old code used a fixed 220×220 grid regardless of the source resolution:
# oversampled on small previews (slow, no extra detail) and undersampled on
# full-size stacks. This helper picks a grid based on the shorter image edge
# and caps at ~400 so the QWebEngine surface trace stays responsive.
# ---------------------------------------------------------------------------
IMAGE_PLANE_SAMPLE_MIN = 96
IMAGE_PLANE_SAMPLE_MAX = 400


def smart_sample_size(img_width: int, img_height: int,
                      sample_min: int = IMAGE_PLANE_SAMPLE_MIN,
                      sample_max: int = IMAGE_PLANE_SAMPLE_MAX) -> int:
    """Choose a square sample grid size proportional to the shorter edge.

    Roughly one sample per 12 source pixels, clamped to
    [``sample_min``, ``sample_max``]. For very elongated fields we still use
    a square grid (the plane itself stretches via `aspectratio`).
    """
    short = max(1, min(int(img_width), int(img_height)))
    # One sample per ~12 source pixels → a 2400-px short-edge image gets 200
    # samples, a 6000-px image hits the 400 cap.
    est = int(round(short / 12.0))
    return max(sample_min, min(sample_max, est))


# ---------------------------------------------------------------------------
# Startup sweep of stale scene HTML files.
# Each render writes a `scene_<pid>_<id>.html` next to the cached plotly.min.js.
# The Preview3DWidget cleans up its own previous file, but if the process
# crashes (or was force-killed) the file lingers forever. Sweep anything
# older than a day on startup so the temp dir doesn't grow unbounded.
# ---------------------------------------------------------------------------

def _sweep_stale_scene_files(cache_dir: str,
                             max_age_seconds: float = 24 * 3600) -> int:
    try:
        if not os.path.isdir(cache_dir):
            return 0
    except Exception:
        return 0
    now = 0.0
    try:
        now = float(datetime.datetime.now().timestamp())
    except Exception:
        return 0
    removed = 0
    try:
        for name in os.listdir(cache_dir):
            if not (name.startswith("scene_") and name.endswith(".html")):
                continue
            path = os.path.join(cache_dir, name)
            try:
                age = now - os.path.getmtime(path)
                if age > max_age_seconds:
                    os.remove(path)
                    removed += 1
            except Exception:
                continue
    except Exception:
        return removed
    return removed

# Cache location + TTL
CACHE_DIR = os.path.expanduser("~/.config/siril")
CACHE_PATH = os.path.join(CACHE_DIR, "svenesis_cosmic_depth_cache.json")
CACHE_TTL_DAYS = 90
CACHE_VERSION = 2

# Conversion constants
PC_TO_LY = 3.26156
KPC_TO_LY = PC_TO_LY * 1000.0
MPC_TO_LY = PC_TO_LY * 1_000_000.0
C_KM_S = 299_792.458  # speed of light, km/s
HUBBLE_H0 = 70.0       # km/s/Mpc

_RE_WHITESPACE = re.compile(r'\s+')


# ------------------------------------------------------------------------------
# STYLING (matches Svenesis AnnotateImage)
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

QLineEdit{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px}
QLineEdit:focus{border-color:#88aaff}

QComboBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QComboBox:focus{border-color:#88aaff}
QComboBox::drop-down{border:none}
QComboBox QAbstractItemView{background-color:#3c3c3c;color:#e0e0e0;selection-background-color:#285299}

QRadioButton{color:#cccccc;spacing:5px}
QRadioButton::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:7px}
QRadioButton::indicator:checked{background:#285299;border:2px solid #88aaff}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton#CoffeeButton{background-color:#FFDD00;color:#000000;border:1px solid #ccb100;font-weight:bold}
QPushButton#CloseButton{background-color:#553333;color:#ffaaaa;border:1px solid #884444}
QPushButton#CloseButton:hover{background-color:#664444}
QPushButton#RenderButton{background-color:#335533;color:#aaffaa;border:1px solid #448844}
QPushButton#RenderButton:hover{background-color:#446644}

QProgressBar{background-color:#3c3c3c;border:1px solid #555555;border-radius:3px;text-align:center;color:#e0e0e0;font-size:9pt}
QProgressBar::chunk{background-color:#285299;border-radius:2px}

QTabWidget::pane{border:1px solid #444444;border-radius:4px}
QTabBar::tab{background-color:#333333;color:#bbbbbb;padding:6px 14px;margin-right:2px;border-top-left-radius:4px;border-top-right-radius:4px}
QTabBar::tab:selected{background-color:#2b2b2b;color:#88aaff;border-bottom:2px solid #88aaff}
QTabBar::tab:hover{background-color:#3c3c3c}

QScrollArea{border:none}
QScrollBar:vertical{background:#2b2b2b;width:10px;border:none}
QScrollBar::handle:vertical{background:#555555;border-radius:4px;min-height:20px}
QScrollBar::handle:vertical:hover{background:#666666}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
"""


# ------------------------------------------------------------------------------
# COLOR SCHEME PER OBJECT TYPE (same palette as AnnotateImage)
# ------------------------------------------------------------------------------

DEFAULT_COLORS = {
    "Gal":   "#FFD700",  # Gold — Galaxies
    "Neb":   "#FF4444",  # Red — Emission nebulae
    "RN":    "#FF8888",  # Light red — Reflection nebulae
    "PN":    "#44FF44",  # Green — Planetary nebulae
    "OC":    "#44AAFF",  # Light blue — Open clusters
    "GC":    "#FF8800",  # Orange — Globular clusters
    "SNR":   "#FF44FF",  # Magenta — Supernova remnants
    "DN":    "#888888",  # Grey — Dark nebulae
    "Star":  "#FFFFFF",  # White — Named stars
    "HII":   "#FF6666",  # Red-pink — HII regions
    "Ast":   "#AADDFF",  # Pale blue — Asterisms
    "QSO":   "#DDAAFF",  # Violet — Quasars
    "Other": "#CCCCCC",  # Light grey — Other
}

OBJECT_TYPE_LABELS = {
    "Gal": "Galaxy", "Neb": "Emission Nebula", "RN": "Reflection Nebula",
    "PN": "Planetary Nebula", "OC": "Open Cluster", "GC": "Globular Cluster",
    "SNR": "Supernova Remnant", "DN": "Dark Nebula", "Star": "Named Star",
    "HII": "HII Region", "Ast": "Asterism", "QSO": "Quasar", "Other": "Other",
}

# SIMBAD otype -> internal type
SIMBAD_TYPE_MAP = {
    "G": "Gal", "GiG": "Gal", "GiP": "Gal", "BiC": "Gal",
    "IG": "Gal", "PaG": "Gal", "SBG": "Gal", "SyG": "Gal",
    "Sy1": "Gal", "Sy2": "Gal", "AGN": "Gal", "LIN": "Gal",
    "ClG": "Gal", "GrG": "Gal", "CGG": "Gal",
    "EmG": "Gal", "H2G": "Gal", "bCG": "Gal", "LSB": "Gal",
    "HII": "HII", "RNe": "RN", "ISM": "Neb", "EmO": "Neb",
    "DNe": "DN", "dNe": "DN", "MoC": "DN",
    "SNR": "SNR", "PN": "PN", "Cl*": "OC", "GlC": "GC",
    "OpC": "OC", "As*": "Ast", "QSO": "QSO",
    "**": "Star", "*": "Star", "V*": "Star", "PM*": "Star",
    "HB*": "Star", "C*": "Star", "S*": "Star", "LP*": "Star",
    "Mi*": "Star", "sr*": "Star", "Ce*": "Star", "RR*": "Star",
    "WR*": "Star", "Be*": "Star", "Pe*": "Star", "HV*": "Star",
    "No*": "Star", "Psr": "Star", "**?": "Star",
}

# Type-based median distances (in light-years) used as fallback
TYPE_DISTANCE_MEDIANS = {
    "HII":   {"dist_ly":     2_000, "spread_ly":    1_500},
    "Neb":   {"dist_ly":     2_000, "spread_ly":    1_500},
    "SNR":   {"dist_ly":     5_000, "spread_ly":    4_000},
    "PN":    {"dist_ly":     3_500, "spread_ly":    3_000},
    "RN":    {"dist_ly":     1_500, "spread_ly":    1_000},
    "OC":    {"dist_ly":     2_500, "spread_ly":    2_000},
    "GC":    {"dist_ly":    40_000, "spread_ly":   30_000},
    "DN":    {"dist_ly":     1_500, "spread_ly":    1_200},
    "Gal":   {"dist_ly": 5_000_000, "spread_ly": 4_000_000},
    "QSO":   {"dist_ly": 2_000_000_000, "spread_ly": 1_500_000_000},
    "Star":  {"dist_ly":       500, "spread_ly":      400},
    "Ast":   {"dist_ly":     1_500, "spread_ly":    1_000},
    "Other": {"dist_ly":     5_000, "spread_ly":    4_000},
}


# ------------------------------------------------------------------------------
# DISTANCE CACHE
# ------------------------------------------------------------------------------

class DistanceCache:
    """JSON-backed distance cache with TTL."""

    def __init__(self, path: str = CACHE_PATH, ttl_days: int = CACHE_TTL_DAYS):
        self.path = path
        self.ttl_days = ttl_days
        self.data: dict = {"cache_version": CACHE_VERSION, "objects": {}}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("cache_version") == CACHE_VERSION:
                    self.data = loaded
        except Exception:
            self.data = {"cache_version": CACHE_VERSION, "objects": {}}

    def save(self) -> None:
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp, self.path)
            except Exception:
                pass

    def get(self, name: str) -> dict | None:
        key = _RE_WHITESPACE.sub(' ', name).strip().upper()
        with self._lock:
            entry = self.data["objects"].get(key)
        if not entry:
            return None
        try:
            last = datetime.date.fromisoformat(entry.get("last_updated", "1970-01-01"))
            age_days = (datetime.date.today() - last).days
            if age_days > self.ttl_days:
                return None
        except Exception:
            return None
        return entry

    def set(self, name: str, dist_ly: float, uncertainty_ly: float,
            source: str, obj_type: str = "", size_ly: float = 0.0,
            confidence: str = "medium") -> None:
        key = _RE_WHITESPACE.sub(' ', name).strip().upper()
        with self._lock:
            self.data["objects"][key] = {
                "name": name,
                "type": obj_type,
                "dist_ly": float(dist_ly),
                "dist_uncertainty_ly": float(uncertainty_ly),
                "dist_source": source,
                "dist_confidence": confidence,
                "size_ly": float(size_ly),
                "last_updated": datetime.date.today().isoformat(),
            }

    def clear(self) -> None:
        with self._lock:
            self.data = {"cache_version": CACHE_VERSION, "objects": {}}
        self.save()


# ------------------------------------------------------------------------------
# DISTANCE RESOLUTION
# ------------------------------------------------------------------------------

def _safe_float(val, default: float = float("nan")) -> float:
    try:
        if val is None or val is np.ma.masked:
            return default
        f = float(val)
        return default if np.isnan(f) else f
    except (ValueError, TypeError):
        return default


def pc_to_ly(value: float, unit: str) -> float:
    """Convert a SIMBAD distance value + unit into light-years."""
    unit = (unit or "pc").lower().strip()
    if unit in ("pc", ""):
        return value * PC_TO_LY
    if unit in ("kpc",):
        return value * KPC_TO_LY
    if unit in ("mpc",):
        return value * MPC_TO_LY
    return value * PC_TO_LY


def query_simbad_distances_batch(
    names: list[str], log_func=None, progress_cb=None,
) -> dict[str, dict]:
    """
    Batch-query SIMBAD's 'mesDistance' table for a list of object names.
    Returns a mapping: normalized_name -> {dist_ly, uncertainty_ly, source}
    for objects that have a published distance measurement.
    """
    if not names:
        return {}

    def _norm(n: str) -> str:
        return _RE_WHITESPACE.sub(' ', n).strip()

    # mesDistance contains one row per published distance measurement.
    # We pick the most recent / best-quoted value per object.
    result_map: dict[str, dict] = {}

    # Process in batches to avoid ultra-long SQL
    BATCH_SIZE = 60
    batches = [names[i:i + BATCH_SIZE] for i in range(0, len(names), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        escaped = [_norm(n).replace("'", "''") for n in batch]
        in_clause = ", ".join(f"'{n}'" for n in escaped)

        # Join ident -> basic -> mesDistance
        query = (
            "SELECT ident.id AS qname, mesDistance.dist AS dist, "
            "mesDistance.unit AS unit, mesDistance.minus_err AS merr, "
            "mesDistance.plus_err AS perr, mesDistance.method AS method, "
            "mesDistance.bibcode AS bib "
            "FROM ident "
            "JOIN mesDistance ON ident.oidref = mesDistance.oidref "
            f"WHERE ident.id IN ({in_clause})"
        )

        try:
            tap_res = Simbad.query_tap(query)
            if tap_res is None or len(tap_res) == 0:
                continue

            # For each object, keep the smallest-uncertainty distance.
            for row in tap_res:
                try:
                    qname = _norm(str(row["qname"]))
                    dist_val = _safe_float(row["dist"])
                    unit = str(row["unit"]) if row["unit"] is not None else "pc"
                    merr = _safe_float(row["merr"], 0.0)
                    perr = _safe_float(row["perr"], 0.0)
                    bib = str(row["bib"]) if row["bib"] is not None else ""
                    if not (dist_val and dist_val > 0):
                        continue

                    dist_ly = pc_to_ly(dist_val, unit)
                    err_ly = pc_to_ly(max(abs(merr), abs(perr)), unit)
                    # Pick the row with smallest uncertainty
                    prior = result_map.get(qname)
                    if prior is None or err_ly < prior.get("uncertainty_ly", float("inf")):
                        result_map[qname] = {
                            "dist_ly": dist_ly,
                            "uncertainty_ly": err_ly if err_ly > 0 else dist_ly * 0.15,
                            "source": f"SIMBAD:{bib}" if bib else "SIMBAD",
                        }
                except Exception:
                    continue

            if log_func:
                log_func(f"SIMBAD distances: batch {batch_idx + 1}/{len(batches)}: "
                         f"{len(result_map)} total resolved")
        except Exception as e:
            if log_func:
                log_func(f"SIMBAD distances: batch {batch_idx + 1} failed: {e}")
            continue
        finally:
            if progress_cb:
                try:
                    progress_cb(batch_idx + 1, len(batches))
                except Exception:
                    pass

    return result_map


def query_simbad_redshifts_batch(
    names: list[str], log_func=None,
) -> dict[str, float]:
    """
    Batch-query SIMBAD 'basic' table for redshifts (z).
    Returns mapping name -> z.
    """
    if not names:
        return {}

    def _norm(n: str) -> str:
        return _RE_WHITESPACE.sub(' ', n).strip()

    result_map: dict[str, float] = {}
    BATCH_SIZE = 80
    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i:i + BATCH_SIZE]
        escaped = [_norm(n).replace("'", "''") for n in batch]
        in_clause = ", ".join(f"'{n}'" for n in escaped)

        query = (
            "SELECT ident.id AS qname, basic.rvz_redshift AS z "
            "FROM ident "
            "JOIN basic ON ident.oidref = basic.oid "
            f"WHERE ident.id IN ({in_clause})"
        )
        try:
            tap_res = Simbad.query_tap(query)
            if tap_res is None or len(tap_res) == 0:
                continue
            for row in tap_res:
                try:
                    qname = _norm(str(row["qname"]))
                    z = _safe_float(row["z"])
                    if not np.isnan(z) and 0 < z < 0.5:
                        result_map[qname] = z
                except Exception:
                    continue
        except Exception as e:
            if log_func:
                log_func(f"SIMBAD redshifts: batch {i // BATCH_SIZE + 1} failed: {e}")
            continue

    return result_map


def redshift_to_ly(z: float) -> float:
    """Hubble-law distance approximation for small z."""
    if z <= 0:
        return 0.0
    dist_mpc = (z * C_KM_S) / HUBBLE_H0
    return dist_mpc * MPC_TO_LY


def resolve_distances(
    objects: list[dict], cache: DistanceCache, use_online: bool,
    log_func=None, progress_cb=None,
) -> None:
    """
    Fill in dist_ly / dist_uncertainty_ly / dist_source / dist_confidence
    on every object, using the prioritized fallback chain:
        1. Cache
        2. SIMBAD mesDistance
        3. SIMBAD redshift (Hubble approx)
        4. Type-based median
    Updates objects in-place.
    """
    if not objects:
        return

    def _norm(n: str) -> str:
        return _RE_WHITESPACE.sub(' ', n).strip()

    unresolved: list[str] = []

    # Pass 1: cache
    for obj in objects:
        name = obj["name"]
        entry = cache.get(name)
        if entry:
            obj["dist_ly"] = entry["dist_ly"]
            obj["dist_uncertainty_ly"] = entry.get("dist_uncertainty_ly", 0.0)
            obj["dist_source"] = entry.get("dist_source", "cache")
            obj["dist_confidence"] = entry.get("dist_confidence", "medium")
        else:
            unresolved.append(name)

    cache_hits = len(objects) - len(unresolved)
    if log_func:
        log_func(f"Distance cache: {cache_hits}/{len(objects)} hits")

    if unresolved and use_online:
        # Pass 2: SIMBAD distances
        dist_map = query_simbad_distances_batch(
            unresolved, log_func=log_func, progress_cb=progress_cb)
        still_unresolved: list[str] = []
        for obj in objects:
            if "dist_ly" in obj:
                continue
            m = dist_map.get(_norm(obj["name"]))
            if m:
                obj["dist_ly"] = m["dist_ly"]
                obj["dist_uncertainty_ly"] = m["uncertainty_ly"]
                obj["dist_source"] = m["source"]
                obj["dist_confidence"] = "high"
                cache.set(obj["name"], m["dist_ly"], m["uncertainty_ly"],
                          m["source"], obj.get("type", ""),
                          obj.get("size_ly", 0.0), confidence="high")
            else:
                still_unresolved.append(obj["name"])

        if log_func:
            log_func(f"SIMBAD mesDistance: {len(objects) - len(still_unresolved) - cache_hits}"
                     f" resolved, {len(still_unresolved)} still unknown")

        # Pass 3: redshift for still-unresolved galaxies / quasars
        zs_map = query_simbad_redshifts_batch(still_unresolved, log_func=log_func)
        for obj in objects:
            if "dist_ly" in obj:
                continue
            z = zs_map.get(_norm(obj["name"]))
            if z is not None:
                d = redshift_to_ly(z)
                if d > 0:
                    obj["dist_ly"] = d
                    obj["dist_uncertainty_ly"] = d * 0.15
                    obj["dist_source"] = f"Redshift z={z:.4f}"
                    obj["dist_confidence"] = "low"
                    cache.set(obj["name"], d, d * 0.15, obj["dist_source"],
                              obj.get("type", ""), 0.0, confidence="low")

    # Pass 4: type-median fallback
    fb_count = 0
    for obj in objects:
        if "dist_ly" in obj:
            continue
        fallback = TYPE_DISTANCE_MEDIANS.get(obj.get("type", "Other"),
                                             TYPE_DISTANCE_MEDIANS["Other"])
        obj["dist_ly"] = float(fallback["dist_ly"])
        obj["dist_uncertainty_ly"] = float(fallback["spread_ly"])
        obj["dist_source"] = "Type median"
        obj["dist_confidence"] = "estimate"
        fb_count += 1

    if log_func and fb_count:
        log_func(f"Type-median fallback: {fb_count} objects")

    cache.save()


# ------------------------------------------------------------------------------
# COORDINATE TRANSFORMATION + SCALING
# ------------------------------------------------------------------------------

def radec_dist_to_xyz(ra_deg: float, dec_deg: float, dist_ly: float
                      ) -> tuple[float, float, float]:
    """
    Sphärisch -> kartesisch.
    Earth/Sun at origin.
    X-axis points to RA=0h, Dec=0; Y-axis to Dec=+90; Z-axis to RA=6h.
    """
    ra_rad = math.radians(ra_deg)
    dec_rad = math.radians(dec_deg)
    x = dist_ly * math.cos(dec_rad) * math.cos(ra_rad)
    y = dist_ly * math.sin(dec_rad)
    z = dist_ly * math.cos(dec_rad) * math.sin(ra_rad)
    return x, y, z


def scale_distance(dist_ly: float, mode) -> float:
    """Scene-space depth coordinate for the given distance in light-years.

    ``mode`` accepts either a ``ScaleMode`` enum member or the matching
    string value ("log" / "linear" / "hybrid"). Unknown values fall back
    to log via ``ScaleMode.parse``.

    Semantics per mode:

    * **LOG** → returns the *stretched-log* transform of the distance
      (see ``log_stretched_transform``). Below 100 M ly this equals
      ``log10(d)`` (one unit per decade); above 100 M ly each decade
      spans ``LOG_STRETCH_FACTOR`` units so the far-galaxy tail gets
      more room on screen. The renderer uses a linear Plotly axis with
      custom tickvals/ticktext (``log_stretched_tick_positions``) so
      labels still read in real light-years.
    * **LINEAR** → raw distance in light-years, clamped to ≥ 1 ly.
    * **HYBRID** → compressed units: 0..20 across the inner 10 kly
      (linear), 20..(20+log10(d/10 kly)·20) beyond that. Kept because
      Plotly has no native hybrid-axis type; this stays with a linear
      axis and the label explains it's compressed.
    """
    d = max(dist_ly, 1.0)
    m = ScaleMode.parse(mode, ScaleMode.LOG)
    if m is ScaleMode.LOG:
        # Stretched-log transform: plain log10 below 100 M ly, stretched
        # decades above. The Plotly/matplotlib axes render as linear over
        # the transformed value with custom tick labels in real ly.
        return log_stretched_transform(d)
    if m is ScaleMode.HYBRID:
        if d <= 10_000:
            return d / 10_000.0 * 20.0
        return 20.0 + math.log10(d / 10_000.0) * 20.0
    # Linear → raw ly; axis is linear.
    return d


def compute_ref_depth(mode, max_depth: float) -> float:
    """Choose where the image plane sits along X for a given scale mode.

    The image plane is the 3D scene's "near" anchor — sticks extend from
    the plane out to each object — so its X coordinate has to sit inside
    the visible span without crowding the objects. On a log axis it must
    be strictly positive (log10(0) = -∞).
    """
    m = ScaleMode.parse(mode, ScaleMode.LOG)
    if m is ScaleMode.LOG:
        # In LOG mode ``scale_distance`` now returns transform-space
        # coordinates (see ``log_stretched_transform``); the image plane
        # sits at the transform of 1 ly, which is 0.0 — the left edge of
        # the axis, with every object to the right.
        return 0.0
    if m is ScaleMode.HYBRID:
        return max(max_depth * 0.02, 0.05)
    # Linear: keep a small fraction of the farthest object, enough to
    # keep the plane visible without clipping the marker labels.
    return max(max_depth * 0.02, 1.0)


def angular_to_physical_size_ly(angular_arcmin: float, dist_ly: float) -> float:
    """Angular size (arcmin) -> physical size (ly)."""
    if angular_arcmin <= 0 or dist_ly <= 0:
        return 0.0
    rad = math.radians(angular_arcmin / 60.0)
    return dist_ly * math.tan(rad)


# ------------------------------------------------------------------------------
# 3D RENDERING
# ------------------------------------------------------------------------------

def build_flat_image_plane(
    image_data: "np.ndarray",
    img_width: int,
    img_height: int,
    ref_depth: float,
    sample: int | None = None,
) -> tuple["np.ndarray", "np.ndarray", "np.ndarray",
           "np.ndarray", "np.ndarray"]:
    """
    Flat rectangular image plane in scene coordinates.

    Scene axes are (X, Y, Z) = (depth, image pixel-x, image pixel-y) with
    the viewer at origin. Y spans [0, img_width], Z spans [0, img_height].
    Pixel row 0 is placed at Z=0 (matching Siril's FITS display, which
    keeps row 0 at the bottom) and pixel column 0 is placed at Y=width
    (mirrored across Y) so the 3D view matches how Siril shows the
    image from the default Plotly camera angle. Object markers land at
    the exact pixel coordinates of their catalogued position.

    ``sample`` defaults to :func:`smart_sample_size`, which scales the
    grid with the shorter image edge (capped at
    :data:`IMAGE_PLANE_SAMPLE_MAX`) so small images don't get wastefully
    oversampled and huge ones don't overwhelm the WebEngine surface.
    """
    if sample is None or sample <= 0:
        sample = smart_sample_size(img_width, img_height)
    ys = np.linspace(0.0, img_width - 1, sample)
    zs = np.linspace(0.0, img_height - 1, sample)
    Y, Z = np.meshgrid(ys, zs)
    X = np.full_like(Y, ref_depth)

    # Mirror pixel-X so the image's column 0 sits at Y=width (see docstring).
    px = np.clip(np.round((img_width - 1) - Y).astype(int),
                 0, img_width - 1)
    py = np.clip(np.round(Z).astype(int), 0, img_height - 1)
    sampled = image_data[py, px]
    if sampled.ndim == 2:
        sampled = np.stack([sampled] * 3, axis=-1)
    lum = (0.299 * sampled[..., 0] + 0.587 * sampled[..., 1]
           + 0.114 * sampled[..., 2]).astype(np.float32)
    p_lo, p_hi = np.percentile(lum, [2.0, 99.5])
    if p_hi > p_lo:
        lum = np.clip((lum - p_lo) / (p_hi - p_lo), 0.0, 1.0)
    else:
        lum = np.clip(lum / 255.0, 0.0, 1.0)
    return X, Y, Z, lum, sampled


def _object_scene_xy(obj: dict, wcs: WCS, img_width: int, img_height: int,
                     ) -> tuple[float, float] | None:
    """Return (Y, Z) scene coords for an object in image pixel units, or
    None if it's outside the image footprint. Y is mirrored and Z is
    direct so the marker position matches the orientation of Siril's
    image (see build_flat_image_plane)."""
    try:
        pix = wcs.all_world2pix(
            np.array([[obj["ra"], obj["dec"]]]), 0)[0]
    except Exception:
        return None
    px = float(pix[0]); py = float(pix[1])
    if (not np.isfinite(px) or not np.isfinite(py)
            or px < -0.05 * img_width or px > 1.05 * img_width
            or py < -0.05 * img_height or py > 1.05 * img_height):
        return None
    return (img_width - 1) - px, py


# Retained for backward reference but unused since the v2 layout rewrite.
def build_image_plane_mesh(
    image_data: "np.ndarray",
    wcs: WCS,
    img_width: int,
    img_height: int,
    ref_scaled_dist: float,
    sample: int = 160,
    angular_scale: float = 1.0,
) -> tuple["np.ndarray", "np.ndarray", "np.ndarray",
           "np.ndarray", "np.ndarray"]:
    """
    Build a curved sky-patch mesh at the given scaled distance.

    Each downsampled pixel is placed in the direction the WCS maps it to,
    optionally amplified around the field centre by ``angular_scale`` so the
    patch is large enough to see against a log-scale cosmic scene (typical
    astro FOV of 1-2° is sub-pixel at scaled distance ~80 otherwise).

    Returns (X, Y, Z, lum, rgb).
    """
    xs_pix = np.linspace(0, img_width - 1, sample)
    ys_pix = np.linspace(0, img_height - 1, sample)
    grid_x, grid_y = np.meshgrid(xs_pix, ys_pix)

    flat_xy = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    sky = wcs.all_pix2world(flat_xy, 0)
    ra_deg = sky[:, 0].reshape(sample, sample)
    dec_deg = sky[:, 1].reshape(sample, sample)

    # Field centre
    cx, cy = img_width / 2.0, img_height / 2.0
    centre = wcs.all_pix2world(np.array([[cx, cy]]), 0)[0]
    ra_c, dec_c = float(centre[0]), float(centre[1])

    # Amplify angular offsets from field centre so the patch is visible
    # in log-scaled cosmic plots. angular_scale=1.0 preserves real geometry.
    d_ra = ra_deg - ra_c
    # Keep wrap-around sane
    d_ra = ((d_ra + 180.0) % 360.0) - 180.0
    d_dec = dec_deg - dec_c
    ra_amp = ra_c + angular_scale * d_ra
    dec_amp = dec_c + angular_scale * d_dec
    dec_amp = np.clip(dec_amp, -89.9, 89.9)

    ra = np.radians(ra_amp)
    dec = np.radians(dec_amp)

    X = ref_scaled_dist * np.cos(dec) * np.cos(ra)
    Y = ref_scaled_dist * np.sin(dec)
    Z = ref_scaled_dist * np.cos(dec) * np.sin(ra)

    if not (np.all(np.isfinite(X)) and np.all(np.isfinite(Y))
            and np.all(np.isfinite(Z))):
        X = np.nan_to_num(X, nan=0.0)
        Y = np.nan_to_num(Y, nan=0.0)
        Z = np.nan_to_num(Z, nan=0.0)

    # Sample the actual image pixels at the downsampled grid
    ix = np.clip(np.round(grid_x).astype(int), 0, img_width - 1)
    iy = np.clip(np.round(grid_y).astype(int), 0, img_height - 1)
    sampled = image_data[iy, ix]
    if sampled.ndim == 2:
        sampled = np.stack([sampled] * 3, axis=-1)
    lum = (0.299 * sampled[..., 0] + 0.587 * sampled[..., 1]
           + 0.114 * sampled[..., 2]).astype(np.float32)
    # Autostretch luminance so the sky plane is actually visible against
    # the black 3D background (astro images are mostly near-zero).
    p_lo, p_hi = np.percentile(lum, [2.0, 99.5])
    if p_hi > p_lo:
        lum = np.clip((lum - p_lo) / (p_hi - p_lo), 0.0, 1.0)
    else:
        lum = np.clip(lum / 255.0, 0.0, 1.0)
    return X, Y, Z, lum, sampled


def build_plotly_figure(
    objects: list[dict], config: dict,
    image_plane: dict | None = None,
) -> "go.Figure | None":
    """
    Interactive Plotly 3D figure.

    Scene layout (matches a viewer-looking-through-a-window model):
      X = depth from viewer (scaled ly)
      Y = horizontal on image plane
      Z = vertical on image plane
      Viewer at origin. Image plane is a flat rectangle at X=ref_depth
      spanning Y,Z; each object sits at (scaled_dist, plane_y, plane_z) so
      sticks from the image plane out to the object are purely along X.
    """
    if not HAS_PLOTLY or not objects:
        return None

    scale_mode = ScaleMode.parse(config.get("scale_mode"), ScaleMode.LOG)
    display_mode = DisplayMode.parse(config.get("display_mode"),
                                     DisplayMode.COSMIC)
    color_by_type = config.get("color_by_type", True)
    wcs: WCS | None = config.get("wcs")
    img_w = int(config.get("img_width", 0))
    img_h = int(config.get("img_height", 0))

    xs, ys, zs = [], [], []
    names, real_dists, types, sizes, sources, uncs = [], [], [], [], [], []
    colors: list[str] = []
    sizes_px: list[float] = []
    plotted_objects: list[dict] = []

    for obj in objects:
        dist_ly = obj.get("dist_ly", 0.0)
        if dist_ly <= 0:
            continue
        if display_mode is DisplayMode.GALACTIC and dist_ly > 100_000:
            continue
        if wcs is None or img_w == 0 or img_h == 0:
            continue
        yz = _object_scene_xy(obj, wcs, img_w, img_h)
        if yz is None:
            continue
        depth = scale_distance(dist_ly, scale_mode)
        xs.append(depth); ys.append(yz[0]); zs.append(yz[1])

        t = obj.get("type", "Other")
        types.append(OBJECT_TYPE_LABELS.get(t, t))
        colors.append(DEFAULT_COLORS.get(t, "#CCCCCC")
                      if color_by_type else "#CCCCCC")
        mag = obj.get("mag", 0.0) or 0.0
        sz_px = 6.0 + max(0.0, 8.0 - min(mag, 12.0) * 0.5)
        sizes_px.append(sz_px)
        names.append(obj.get("display_name") or obj.get("name", "?"))
        real_dists.append(dist_ly)
        sizes.append(obj.get("size_ly", 0.0))
        sources.append(obj.get("dist_source", ""))
        uncs.append(obj.get("dist_uncertainty_ly", 0.0))
        plotted_objects.append(obj)

    if not xs:
        return None

    hovertemplate = (
        "<b>%{text}</b><br>"
        "Distance: %{customdata[0]:,.0f} ly<br>"
        "Type: %{customdata[1]}<br>"
        "Size: %{customdata[2]:,.0f} ly<br>"
        "Uncertainty: ±%{customdata[3]:,.0f} ly<br>"
        "Source: %{customdata[4]}"
        "<extra></extra>"
    )
    customdata = list(zip(real_dists, types, sizes, uncs, sources))

    trace_points = go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="markers+text",
        marker=dict(size=sizes_px, color=colors, opacity=0.95,
                    line=dict(width=0.5, color="white")),
        text=names,
        textposition="top center",
        textfont=dict(color="#dddddd", size=10),
        hovertemplate=hovertemplate,
        customdata=customdata,
        name="Objects",
    )

    if scale_mode is ScaleMode.LINEAR:
        depth_label = "Distance (ly, linear)"
    elif scale_mode is ScaleMode.HYBRID:
        depth_label = "Distance (ly, hybrid log)"
    else:
        depth_label = "Distance (ly, log scale)"

    data_traces: list = []

    if image_plane is not None:
        try:
            ref_depth = float(image_plane.get("ref_depth", 0.0))
            sky_colorscale = [
                [0.0, "#0a0820"],
                [0.15, "#1a1850"],
                [0.45, "#4060a0"],
                [0.75, "#c0d0e8"],
                [1.0, "#ffffff"],
            ]
            trace_image = go.Surface(
                x=image_plane["X"], y=image_plane["Y"], z=image_plane["Z"],
                surfacecolor=image_plane["lum"],
                colorscale=sky_colorscale,
                cmin=0.0, cmax=1.0,
                showscale=False,
                opacity=image_plane.get("opacity", 1.0),
                lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0,
                              fresnel=0.0, roughness=1.0),
                contours=dict(x=dict(highlight=False),
                              y=dict(highlight=False),
                              z=dict(highlight=False)),
                hoverinfo="skip",
                name="Sky image",
            )
            data_traces.append(trace_image)

            # Sticks: perpendicular lines from image plane to each object.
            line_xs: list = []
            line_ys: list = []
            line_zs: list = []
            for xi, yi, zi in zip(xs, ys, zs):
                line_xs.extend([ref_depth, xi, None])
                line_ys.extend([yi, yi, None])
                line_zs.extend([zi, zi, None])
            if line_xs:
                data_traces.append(go.Scatter3d(
                    x=line_xs, y=line_ys, z=line_zs,
                    mode="lines",
                    line=dict(color="rgba(170,190,230,0.45)", width=2),
                    hoverinfo="skip",
                    name="Depth lines",
                ))
        except Exception:
            pass

    data_traces.append(trace_points)

    # In log mode we use a linear Plotly 3D axis over the stretched-log
    # transform-space coordinates that ``scale_distance`` now returns,
    # with custom tickvals/ticktext so labels still read in real ly
    # (1, 10, 100, 1k, …, 100M, 1B, 10B). This gives us a non-uniform
    # log: decades past LOG_STRETCH_THRESHOLD_LY are LOG_STRETCH_FACTOR×
    # wider, so the far-galaxy tail isn't cramped at the right edge.
    # Linear and hybrid keep a plain linear axis; hybrid's label notes
    # it's compressed units.
    xaxis_kwargs = dict(title=depth_label, gridcolor="#222",
                        showbackground=False, color="#aaaaaa")
    if scale_mode is ScaleMode.LOG:
        # xs already hold stretched-log transform values; find the
        # largest raw ly (inverse the transform) to size the ticks.
        try:
            max_x = max(xs) if xs else 0.0
            # Reconstruct an approximate max_ly just for tick labelling:
            # if xs stays within [0, log10(t)] it was plain log; above
            # that we un-stretch.
            t = LOG_STRETCH_THRESHOLD_LY
            log_t = math.log10(t)
            if max_x <= log_t:
                max_ly = 10.0 ** max_x
            else:
                max_ly = t * (10.0 ** ((max_x - log_t) / LOG_STRETCH_FACTOR))
            tickvals, ticktext = log_stretched_tick_positions(max_ly)
            xaxis_kwargs["tickvals"] = tickvals
            xaxis_kwargs["ticktext"] = ticktext
            # Range: from transform(1 ly)=0 to just past the farthest
            # object (0.5 transform-units ≈ one stretched decade/6).
            hi = max(max_x, tickvals[-1] if tickvals else 1.0) + 0.5
            xaxis_kwargs["range"] = [0.0, hi]
        except Exception:
            pass
    fig = go.Figure(data=data_traces)
    fig.update_layout(
        scene=dict(
            xaxis=xaxis_kwargs,
            yaxis=dict(title="Image X (pixels)", gridcolor="#222",
                       showbackground=False, color="#aaaaaa"),
            zaxis=dict(title="Image Y (pixels)", gridcolor="#222",
                       showbackground=False, color="#aaaaaa"),
            aspectmode="manual",
            aspectratio=dict(
                x=1.6, y=1.0,
                z=(img_h / img_w) if img_w > 0 else 1.0,
            ),
            camera=dict(eye=dict(x=-1.4, y=-1.6, z=0.9),
                        up=dict(x=0, y=0, z=1),
                        center=dict(x=0, y=0, z=0)),
            bgcolor="#0a0a0a",
        ),
        paper_bgcolor="#0a0a0a",
        font_color="#dddddd",
        showlegend=False,
        margin=dict(l=0, r=0, t=36, b=0),
        title=dict(
            text=config.get("title", "Svenesis CosmicDepth 3D"),
            x=0.5, xanchor="center",
            font=dict(color="#88aaff", size=16),
        ),
    )
    return fig


def _mpl_axis_value(d_ly: float, mode) -> float:
    """X coordinate for matplotlib's 3D axes given a distance in ly.

    ``mpl_toolkits.mplot3d.Axes3D.set_xscale('log')`` is flaky/unsupported
    across matplotlib versions, so we apply the stretched-log transform
    ourselves in LOG mode (matching the Plotly path). Linear and hybrid
    reuse ``scale_distance`` unchanged.
    """
    m = ScaleMode.parse(mode, ScaleMode.LOG)
    if m is ScaleMode.LOG:
        return log_stretched_transform(d_ly)
    return scale_distance(d_ly, m)


def render_matplotlib_3d(
    objects: list[dict], config: dict, out_path: str,
    image_plane: dict | None = None,
) -> str:
    """Matplotlib fallback renderer, same scene coords as the Plotly one."""
    scale_mode = ScaleMode.parse(config.get("scale_mode"), ScaleMode.LOG)
    display_mode = DisplayMode.parse(config.get("display_mode"),
                                     DisplayMode.COSMIC)
    color_by_type = config.get("color_by_type", True)
    wcs: WCS | None = config.get("wcs")
    img_w = int(config.get("img_width", 0))
    img_h = int(config.get("img_height", 0))

    xs, ys, zs, colors, names, sizes = [], [], [], [], [], []
    for obj in objects:
        dist_ly = obj.get("dist_ly", 0.0)
        if dist_ly <= 0:
            continue
        if display_mode is DisplayMode.GALACTIC and dist_ly > 100_000:
            continue
        if wcs is None or img_w == 0 or img_h == 0:
            continue
        yz = _object_scene_xy(obj, wcs, img_w, img_h)
        if yz is None:
            continue
        depth = _mpl_axis_value(dist_ly, scale_mode)
        xs.append(depth); ys.append(yz[0]); zs.append(yz[1])
        t = obj.get("type", "Other")
        colors.append(DEFAULT_COLORS.get(t, "#CCCCCC")
                      if color_by_type else "#CCCCCC")
        names.append(obj.get("display_name") or obj.get("name", "?"))
        sizes.append(40.0)

    fig = Figure(figsize=(12, 10), facecolor="#0a0a0a")
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d", facecolor="#0a0a0a")

    ref_depth = 0.0
    if image_plane is not None:
        try:
            rgb = image_plane["rgb"].astype(np.float32) / 255.0
            # The image plane's X array and stored ref_depth are already
            # in the renderer's axis space (raw ly for linear/hybrid,
            # stretched-log transform-space for LOG — see
            # ``compute_ref_depth`` and ``scale_distance``). No further
            # transform is needed here.
            ax.plot_surface(
                image_plane["X"], image_plane["Y"], image_plane["Z"],
                facecolors=rgb, rstride=1, cstride=1,
                shade=False, antialiased=False, linewidth=0,
                alpha=image_plane.get("opacity", 0.7),
            )
            ref_depth = float(image_plane.get("ref_depth", 0.0))
            if xs:
                for xi, yi, zi in zip(xs, ys, zs):
                    ax.plot([ref_depth, xi], [yi, yi], [zi, zi],
                            color="#aabae6", alpha=0.45, linewidth=1)
        except Exception:
            pass
    if xs:
        ax.scatter(xs, ys, zs, c=colors, s=sizes, alpha=0.95,
                   edgecolors="white", linewidths=0.3)
        for xi, yi, zi, n in zip(xs, ys, zs, names):
            ax.text(xi, yi, zi, f"  {n}", color="#dddddd", fontsize=7)

    if scale_mode is ScaleMode.LINEAR:
        depth_label = "Distance (ly, linear)"
    elif scale_mode is ScaleMode.HYBRID:
        depth_label = "Distance (ly, hybrid log)"
    else:
        depth_label = "Distance (ly, log scale)"
    ax.set_xlabel(depth_label, color="#aaaaaa")
    ax.set_ylabel("Image X (pixels)", color="#aaaaaa")
    ax.set_zlabel("Image Y (pixels)", color="#aaaaaa")
    # LOG mode: paint the stretched-log ticks in real-ly labels so the
    # matplotlib fallback axis matches the Plotly view.
    if scale_mode is ScaleMode.LOG and xs:
        try:
            t = LOG_STRETCH_THRESHOLD_LY
            log_t = math.log10(t)
            max_x = max(xs)
            if max_x <= log_t:
                max_ly = 10.0 ** max_x
            else:
                max_ly = t * (10.0 ** ((max_x - log_t) / LOG_STRETCH_FACTOR))
            tickvals, ticktext = log_stretched_tick_positions(max_ly)
            ax.set_xticks(tickvals)
            ax.set_xticklabels(ticktext)
        except Exception:
            pass
    try:
        ax.view_init(elev=18, azim=-60)
    except Exception:
        pass
    ax.tick_params(colors="#888888")
    ax.set_title(config.get("title", "Svenesis CosmicDepth 3D"), color="#88aaff")
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_facecolor("#0a0a0a")
        pane.pane.set_edgecolor("#222222")

    canvas.draw()
    fig.savefig(out_path, dpi=config.get("dpi", 150), facecolor="#0a0a0a")
    return out_path


# ------------------------------------------------------------------------------
# WCS HELPERS (same strategy as AnnotateImage)
# ------------------------------------------------------------------------------

def extract_wcs_from_header(header_str: str) -> WCS | None:
    if not header_str:
        return None
    try:
        hdr = astropy_fits.Header.fromstring(header_str, sep="\n")
        wcs = WCS(hdr)
        if wcs.has_celestial:
            return wcs
    except Exception:
        pass
    try:
        hdr = astropy_fits.Header.fromstring(header_str)
        wcs = WCS(hdr)
        if wcs.has_celestial:
            return wcs
    except Exception:
        pass
    return None


def extract_wcs_from_fits_file(siril, log_func=None) -> WCS | None:
    def _log(msg: str) -> None:
        if log_func:
            log_func(msg)

    fits_candidates: list[str] = []
    try:
        img_filename = siril.get_image_filename()
        if img_filename:
            if os.path.isfile(img_filename):
                fits_candidates.append(img_filename)
            else:
                try:
                    wd = siril.get_siril_wd()
                    if wd:
                        for ext in ("", ".fit", ".fits", ".fts"):
                            candidate = os.path.join(wd, img_filename + ext)
                            if os.path.isfile(candidate):
                                fits_candidates.append(candidate)
                                break
                except Exception:
                    pass
    except Exception as e:
        _log(f"WCS disk: get_image_filename() failed: {e}")

    if not fits_candidates:
        try:
            wd = siril.get_siril_wd() or os.getcwd()
        except Exception:
            wd = os.getcwd()
        try:
            for f in os.listdir(wd):
                if f.lower().endswith((".fit", ".fits", ".fts")):
                    fits_candidates.append(os.path.join(wd, f))
        except OSError:
            return None
        fits_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    if not fits_candidates:
        return None

    for fits_path in fits_candidates[:5]:
        try:
            with astropy_fits.open(fits_path) as hdul:
                header = hdul[0].header
                if "CRVAL1" in header and "CRVAL2" in header:
                    wcs = WCS(header)
                    if wcs.has_celestial:
                        _log(f"WCS disk: success from {os.path.basename(fits_path)}")
                        return wcs
        except Exception:
            continue
    return None


def compute_pixel_scale(wcs: WCS) -> float:
    try:
        if hasattr(wcs.wcs, "cd") and wcs.wcs.cd is not None:
            cd = wcs.wcs.cd
            s1 = math.hypot(cd[0, 0], cd[0, 1]) * 3600.0
            s2 = math.hypot(cd[1, 0], cd[1, 1]) * 3600.0
            return (s1 + s2) / 2.0
        if hasattr(wcs.wcs, "cdelt") and wcs.wcs.cdelt is not None:
            return abs(wcs.wcs.cdelt[0]) * 3600.0
    except Exception:
        pass
    return 1.0


# ------------------------------------------------------------------------------
# PREVIEW WIDGET (WebEngine or fallback)
# ------------------------------------------------------------------------------

_PLOTLY_CACHE_DIR: str | None = None


def _plotly_cache_dir() -> str:
    """Return a process-wide cache dir holding plotly.min.js, written once.

    Each render then emits a small HTML (include_plotlyjs='directory') that
    references the cached bundle via a relative <script src> — avoids
    re-inlining the ~3.5 MB plotly.js blob on every refresh.
    """
    global _PLOTLY_CACHE_DIR
    if _PLOTLY_CACHE_DIR and os.path.isfile(
            os.path.join(_PLOTLY_CACHE_DIR, "plotly.min.js")):
        return _PLOTLY_CACHE_DIR
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "svenesis_cosmicdepth_plotly")
    os.makedirs(d, exist_ok=True)
    js_path = os.path.join(d, "plotly.min.js")
    if not os.path.isfile(js_path):
        try:
            from plotly.offline import get_plotlyjs
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(get_plotlyjs())
        except Exception:
            pass
    # First time we resolve the cache dir in this process, clean out any
    # scene HTML files left behind by prior (possibly crashed) runs.
    try:
        _sweep_stale_scene_files(d)
    except Exception:
        pass
    _PLOTLY_CACHE_DIR = d
    return d


class WebEngineRepairDialog(QDialog):
    """Explicit, opt-in repair flow for a broken PyQt6-WebEngine install.

    Motivation: the previous implementation auto-ran
    ``pip install --force-reinstall`` from inside the script on import.
    That surprised users, failed silently behind proxies, and could
    damage system-managed Python installs. This dialog:

    * refuses to run inside a PEP 668 / externally-managed interpreter
      and explains what to do instead;
    * requires an explicit click on **Run Repair** to start pip;
    * streams pip stdout/stderr line by line into a read-only console
      widget (not just the final exception);
    * exposes **Retry Import** once the subprocess exits so the user
      can confirm success without restarting Siril.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Repair PyQt6-WebEngine")
        self.setMinimumSize(680, 480)
        self.setStyleSheet("QDialog{background-color:#1e1e1e;color:#e0e0e0}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)

        header = QLabel(
            "<b style='color:#88aaff;font-size:13pt;'>"
            "Repair PyQt6-WebEngine</b>")
        lay.addWidget(header)

        blurb = QLabel(
            "The interactive 3D view needs <code>PyQt6-WebEngine</code> "
            "whose Qt ABI matches Siril's bundled PyQt6. "
            "If you got a <code>Symbol not found: _qt_version_tag_6_XX</code> "
            "error, a pinned reinstall usually fixes it.<br><br>"
            "This will run <code>pip install --force-reinstall --no-deps</code> "
            "for <code>PyQt6-WebEngine</code> and "
            "<code>PyQt6-WebEngine-Qt6</code>, pinned to the minor version "
            "of your PyQt6. Nothing runs until you click "
            "<b>Run Repair</b>."
        )
        blurb.setWordWrap(True)
        blurb.setTextFormat(Qt.TextFormat.RichText)
        blurb.setStyleSheet("color:#cccccc;font-size:10pt;")
        lay.addWidget(blurb)

        self._err_label = QLabel()
        self._err_label.setWordWrap(True)
        self._err_label.setStyleSheet(
            "background-color:#3a1e1e;color:#ffaaaa;"
            "border:1px solid #884444;border-radius:4px;"
            "padding:6px;font-family:monospace;font-size:9pt;")
        self._err_label.setText(
            f"Current import error:\n{WEBENGINE_ERROR or '(none)'}")
        lay.addWidget(self._err_label)

        # Where the pinned pip install will go.
        self._cmd_label = QLabel()
        self._cmd_label.setStyleSheet(
            "color:#aaaaaa;font-family:monospace;font-size:9pt;"
            "background-color:#252525;padding:6px;border-radius:4px;")
        self._cmd_label.setText(self._format_planned_command())
        self._cmd_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._cmd_label)

        # Console: pip output live-streamed here.
        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setStyleSheet(
            "background-color:#0a0a0a;color:#c8c8c8;"
            "font-family:monospace;font-size:9pt;"
            "border:1px solid #333;")
        self._console.setPlaceholderText(
            "pip output will appear here after you click Run Repair.")
        lay.addWidget(self._console, 1)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("Run Repair")
        self.btn_run.setObjectName("RenderButton")
        _nofocus(self.btn_run)
        self.btn_run.clicked.connect(self._on_run)
        btn_row.addWidget(self.btn_run)

        self.btn_retry = QPushButton("Retry Import")
        _nofocus(self.btn_retry)
        self.btn_retry.setEnabled(False)
        self.btn_retry.clicked.connect(self._on_retry)
        btn_row.addWidget(self.btn_retry)

        btn_row.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("CloseButton")
        _nofocus(self.btn_close)
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_close)

        lay.addLayout(btn_row)

        self._retry_succeeded = False

        # PEP 668 guard: skip entirely and tell the user what to do.
        if _is_externally_managed_python():
            self._append(
                "[refused] This Python interpreter is marked "
                "EXTERNALLY-MANAGED (PEP 668). pip will not run from "
                "inside the script to avoid damaging your system "
                "install.\n")
            self._append(
                "Fix options:\n"
                f"  1. Create a virtualenv, activate it, then: "
                f"pip install 'PyQt6-WebEngine=={self._pin_spec()}'\n"
                "  2. Or use Siril's internal Python (usually "
                "unaffected by PEP 668).\n"
                "  3. Or pass --break-system-packages manually from a "
                "terminal if you know what you're doing.\n"
            )
            self.btn_run.setEnabled(False)
            self.btn_run.setToolTip(
                "Refused: PEP 668 externally-managed interpreter")

    @staticmethod
    def _pin_spec() -> str:
        """Minor-version wildcard matching the running PyQt6."""
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR
            parts = PYQT_VERSION_STR.split(".")
            return ".".join(parts[:2]) + ".*" if len(parts) >= 2 else "*"
        except Exception:
            return "*"

    def _format_planned_command(self) -> str:
        pin = self._pin_spec()
        return (
            f"$ {sys.executable} -m pip install "
            f"--force-reinstall --no-deps "
            f"'PyQt6-WebEngine=={pin}' "
            f"'PyQt6-WebEngine-Qt6=={pin}'"
        )

    def _append(self, text: str) -> None:
        # QTextEdit.append adds a newline each call; use insertPlainText
        # so partial pip lines don't double-space.
        cursor = self._console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._console.setTextCursor(cursor)
        self._console.ensureCursorVisible()
        QApplication.processEvents()

    def _on_run(self) -> None:
        import subprocess
        self.btn_run.setEnabled(False)
        self.btn_retry.setEnabled(False)
        self._console.clear()
        pin = self._pin_spec()
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--force-reinstall", "--no-deps",
            f"PyQt6-WebEngine=={pin}",
            f"PyQt6-WebEngine-Qt6=={pin}",
        ]
        self._append(f"$ {' '.join(cmd)}\n")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )
        except Exception as e:
            self._append(f"\n[error] Could not launch pip: "
                         f"{type(e).__name__}: {e}\n")
            self.btn_run.setEnabled(True)
            return

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._append(line)
        except Exception as e:
            self._append(f"\n[error] Failed to read pip output: "
                         f"{type(e).__name__}: {e}\n")
        rc = proc.wait()
        self._append(f"\n[pip exited with status {rc}]\n")

        if rc == 0:
            self._append(
                "\nReinstall complete. Click 'Retry Import' to re-check "
                "whether QWebEngineView loads.\n")
            self.btn_retry.setEnabled(True)
        else:
            self._append(
                "\npip reported a failure. Common causes:\n"
                "  - offline / proxy blocking pypi.org\n"
                "  - no matching wheel for this Python/OS/arch\n"
                "  - interpreter marked EXTERNALLY-MANAGED\n"
                "You can re-run from a terminal with the exact command "
                "above to see more context.\n")
            self.btn_run.setEnabled(True)

    def _on_retry(self) -> None:
        global HAS_WEBENGINE
        self._append("\nAttempting to import QWebEngineView...\n")
        HAS_WEBENGINE = _try_import_webengine()
        if HAS_WEBENGINE:
            self._retry_succeeded = True
            self._append("[ok] WebEngine import succeeded.\n")
            self.btn_retry.setEnabled(False)
            self.btn_run.setEnabled(False)
            QMessageBox.information(
                self, "Repair Succeeded",
                "PyQt6-WebEngine is now loadable. "
                "The next render will use the embedded 3D view.")
            self.accept()
        else:
            self._append(f"[fail] Still failing: {WEBENGINE_ERROR}\n")
            self.btn_retry.setEnabled(True)
            self.btn_run.setEnabled(True)

    @property
    def repaired(self) -> bool:
        return self._retry_succeeded


class Preview3DWidget(QWidget):
    """
    Shows the 3D scene. Uses QWebEngineView + Plotly when available;
    otherwise falls back to a static matplotlib PNG.
    """

    # Signal emitted when the user clicks the in-pane "Repair WebEngine…"
    # button in the error banner. The main window catches this and opens
    # WebEngineRepairDialog; we keep the widget itself dialog-agnostic.
    repair_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._view = None
        self._png_label = None
        self._banner = None
        if HAS_WEBENGINE:
            self._show_placeholder()
        else:
            self._show_webengine_banner()

    def _show_placeholder(self) -> None:
        self._clear_children()
        placeholder = QLabel(
            "The 3D map will appear here after rendering.\n"
            "Press \u201cRender 3D Map\u201d (F5)."
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color:#888888;font-size:11pt;border:1px dashed #555555;"
            "background-color:#0a0a0a;"
        )
        self._layout.addWidget(placeholder)

    def _show_webengine_banner(self) -> None:
        """Show the explicit opt-in repair banner when WebEngine is missing.

        Replaces the previous behaviour where ``show_html`` silently
        returned — the user now sees *why* the interactive view isn't
        available and can choose to run the repair or not.
        """
        self._clear_children()
        banner = QWidget()
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(18, 18, 18, 18)
        bl.setSpacing(10)
        banner.setStyleSheet(
            "background-color:#0a0a0a;border:1px dashed #774444;")

        title = QLabel("Interactive 3D view unavailable")
        title.setStyleSheet(
            "color:#ffaaaa;font-size:13pt;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(title)

        body = QLabel(
            "<code>PyQt6-WebEngine</code> could not be loaded, so the "
            "rotatable embedded view is disabled. The rendered scene "
            "will open in your default browser instead.<br><br>"
            "If this is an ABI mismatch (error mentions "
            "<code>_qt_version_tag_6_XX</code>), click "
            "<b>Repair WebEngine…</b> to run an opt-in pinned reinstall "
            "with live pip output.")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color:#cccccc;font-size:10pt;border:0;")
        bl.addWidget(body)

        if WEBENGINE_ERROR:
            err = QLabel(f"Error: {WEBENGINE_ERROR}")
            err.setWordWrap(True)
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            err.setStyleSheet(
                "color:#ff9999;font-family:monospace;font-size:9pt;"
                "border:0;")
            bl.addWidget(err)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Repair WebEngine\u2026")
        btn.setObjectName("RenderButton")
        _nofocus(btn)
        btn.clicked.connect(self.repair_requested.emit)
        btn_row.addWidget(btn)
        btn_row.addStretch()
        bl.addLayout(btn_row)

        self._banner = banner
        self._layout.addWidget(banner)

    def refresh_webengine_state(self) -> None:
        """Re-render the pane after a successful repair: drop the banner
        and go back to the 'ready' placeholder."""
        if HAS_WEBENGINE:
            self._show_placeholder()
        else:
            self._show_webengine_banner()

    def _clear_children(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._view = None
        self._png_label = None
        self._banner = None

    def show_html(self, html_content: str) -> None:
        if not HAS_WEBENGINE:
            # Don't silently swallow the call — surface the banner so
            # the user can opt in to a repair. The calling site still
            # writes a standalone HTML and opens it in the browser.
            self._show_webengine_banner()
            return
        self._clear_children()
        self._view = QWebEngineView()
        # Write the HTML into the plotly cache dir so the relative
        # <script src="plotly.min.js"> (from include_plotlyjs='directory')
        # resolves to the cached bundle. Also remove the previous temp
        # file so we don't leak one per render.
        cache_dir = _plotly_cache_dir()
        prev = getattr(self, "_tmp_html_path", None)
        if prev and os.path.isfile(prev):
            try:
                os.remove(prev)
            except Exception:
                pass
        path = os.path.join(
            cache_dir, f"scene_{os.getpid()}_{id(self):x}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        self._tmp_html_path = path
        self._view.load(QUrl.fromLocalFile(path))
        self._layout.addWidget(self._view)

    def show_png(self, path: str) -> None:
        from PyQt6.QtGui import QPixmap
        self._clear_children()
        self._png_label = QLabel()
        self._png_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(path)
        if not pix.isNull():
            self._png_label.setPixmap(
                pix.scaled(self.size(),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        self._layout.addWidget(self._png_label)


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class CosmicDepth3DWindow(QMainWindow):
    """
    Main window for Svenesis CosmicDepth 3D.

    Left panel: object-type filters, scaling controls, cache + export.
    Right panel: interactive 3D scene and status log.
    """

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self._image_data = None
        self._img_width = 0
        self._img_height = 0
        self._img_channels = 0
        self._wcs: WCS | None = None
        self._pixel_scale = 1.0
        self._header_str = ""
        self._is_plate_solved = False
        self._log_buffer: list[str] = []
        self._siril_lock = threading.Lock()
        self._last_html_path = ""
        self._last_png_path = ""
        self._last_csv_path = ""
        self._last_figure = None
        self._last_image_plane: dict | None = None
        self._last_objects: list[dict] = []
        self._cache = DistanceCache()
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self.init_ui()
        self._load_settings()

        QShortcut(QKeySequence("F5"), self, self._on_render)

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

        lbl = QLabel(f"Svenesis CosmicDepth 3D {VERSION}")
        lbl.setStyleSheet(
            "font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_types_group(layout)
        self._build_mode_group(layout)
        self._build_filters_group(layout)
        self._build_data_group(layout)
        self._build_output_group(layout)
        self._build_action_buttons(layout)

        layout.addStretch()

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

    def _build_types_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Include Objects")
        outer = QVBoxLayout(group)

        self._type_checkboxes: dict[str, QCheckBox] = {}

        type_defs = [
            # key, label, color, default, tooltip, col, row
            ("Gal", "Galaxies", "#FFD700", True,
             "Include galaxies from SIMBAD in the 3D map.", 0, 0),
            ("Neb", "Nebulae", "#FF4444", True,
             "Bright emission nebulae.", 0, 1),
            ("PN", "Planetary Neb.", "#44FF44", True,
             "Planetary nebulae.", 0, 2),
            ("OC", "Open Clusters", "#44AAFF", True,
             "Open star clusters.", 0, 3),
            ("GC", "Globular Clusters", "#FF8800", True,
             "Globular star clusters.", 0, 4),
            ("Star", "Named Stars", "#FFFFFF", True,
             "Bright named stars. Distances from Gaia/SIMBAD parallax.",
             0, 5),
            ("RN", "Reflection Neb.", "#FF8888", False,
             "Reflection nebulae.", 1, 0),
            ("SNR", "Supernova Rem.", "#FF44FF", False,
             "Supernova remnants.", 1, 1),
            ("DN", "Dark Nebulae", "#888888", False,
             "Dark nebulae (Barnard, LDN).", 1, 2),
            ("HII", "HII Regions", "#FF6666", False,
             "HII regions (Sharpless).", 1, 3),
            ("Ast", "Asterisms", "#AADDFF", False,
             "Asterisms — positioned at type-median distance.", 1, 4),
            ("QSO", "Quasars", "#DDAAFF", False,
             "Quasars. Distances from redshift.", 1, 5),
        ]

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for key, label, color, default_on, tooltip, col, row in type_defs:
            chk = QCheckBox(f" {label}")
            chk.setChecked(default_on)
            chk.setToolTip(tooltip)
            chk.setStyleSheet(
                f"QCheckBox{{color:{color};spacing:3px;font-size:8pt}}"
                f"QCheckBox::indicator{{width:13px;height:13px;border:1px solid #666;"
                f"background:#3c3c3c;border-radius:3px}}"
                f"QCheckBox::indicator:checked{{background:{color};border:1px solid {color}}}"
            )
            _nofocus(chk)
            grid.addWidget(chk, row, col)
            self._type_checkboxes[key] = chk

        outer.addLayout(grid)

        sep = QLabel("")
        sep.setFixedHeight(4)
        outer.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.setStyleSheet("font-size:8pt;padding:3px 8px")
        _nofocus(btn_all)
        btn_all.clicked.connect(lambda: self._set_all_types(True))
        btn_row.addWidget(btn_all)
        btn_none = QPushButton("Deselect All")
        btn_none.setStyleSheet("font-size:8pt;padding:3px 8px")
        _nofocus(btn_none)
        btn_none.clicked.connect(lambda: self._set_all_types(False))
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        parent_layout.addWidget(group)

    def _set_all_types(self, state: bool) -> None:
        for chk in self._type_checkboxes.values():
            chk.setChecked(state)

    def _build_mode_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("View Mode & Scaling")
        layout = QVBoxLayout(group)

        # Display mode
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Range:"))
        self.radio_mode_cosmic = QRadioButton("Cosmic")
        self.radio_mode_cosmic.setToolTip("Show all objects including galaxies and quasars.")
        self.radio_mode_cosmic.setChecked(True)
        _nofocus(self.radio_mode_cosmic)
        self.radio_mode_galactic = QRadioButton("Galactic (< 100k ly)")
        self.radio_mode_galactic.setToolTip("Only show objects inside the Milky Way.")
        _nofocus(self.radio_mode_galactic)
        mode_grp = QButtonGroup(self)
        mode_grp.addButton(self.radio_mode_cosmic)
        mode_grp.addButton(self.radio_mode_galactic)
        row1.addWidget(self.radio_mode_cosmic)
        row1.addWidget(self.radio_mode_galactic)
        row1.addStretch()
        layout.addLayout(row1)

        # Scale mode
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Scale:"))
        self.radio_scale_log = QRadioButton("Log")
        self.radio_scale_log.setChecked(True)
        self.radio_scale_log.setToolTip(
            "Logarithmic: best for mixed fields (stars + galaxies).")
        _nofocus(self.radio_scale_log)
        self.radio_scale_linear = QRadioButton("Linear")
        self.radio_scale_linear.setToolTip(
            "Linear: true distances — galaxies disappear to infinity.")
        _nofocus(self.radio_scale_linear)
        self.radio_scale_hybrid = QRadioButton("Hybrid")
        self.radio_scale_hybrid.setToolTip(
            "Hybrid: linear up to 10k ly, logarithmic beyond.")
        _nofocus(self.radio_scale_hybrid)
        scale_grp = QButtonGroup(self)
        scale_grp.addButton(self.radio_scale_log)
        scale_grp.addButton(self.radio_scale_linear)
        scale_grp.addButton(self.radio_scale_hybrid)
        row2.addWidget(self.radio_scale_log)
        row2.addWidget(self.radio_scale_linear)
        row2.addWidget(self.radio_scale_hybrid)
        row2.addStretch()
        layout.addLayout(row2)

        # Color by type
        self.chk_color_by_type = QCheckBox("Color by type")
        self.chk_color_by_type.setChecked(True)
        self.chk_color_by_type.setToolTip(
            "Color each object according to its catalogue type.")
        _nofocus(self.chk_color_by_type)
        layout.addWidget(self.chk_color_by_type)

        self.chk_show_image_plane = QCheckBox("Show image as sky plane")
        self.chk_show_image_plane.setChecked(True)
        self.chk_show_image_plane.setToolTip(
            "Place the plate-solved image as a semi-transparent curved\n"
            "patch in 3D, so you see the sky as-viewed from Earth while\n"
            "each catalogued object floats at its real distance behind it."
        )
        _nofocus(self.chk_show_image_plane)
        self.chk_show_image_plane.toggled.connect(
            self._on_image_plane_toggled)
        layout.addWidget(self.chk_show_image_plane)

        parent_layout.addWidget(group)

    def _build_filters_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Filters")
        grid = QGridLayout(group)
        grid.setColumnMinimumWidth(0, 100)
        grid.setColumnMinimumWidth(1, 60)
        grid.setColumnStretch(2, 1)

        row = 0
        lbl = QLabel("Mag limit:")
        lbl.setFixedWidth(100)
        grid.addWidget(lbl, row, 0)
        self.spin_mag = QDoubleSpinBox()
        self.spin_mag.setRange(1.0, 20.0)
        self.spin_mag.setValue(12.0)
        self.spin_mag.setSingleStep(0.5)
        self.spin_mag.setDecimals(1)
        self.spin_mag.setFixedWidth(60)
        self.spin_mag.setToolTip(
            "Only include objects brighter than this magnitude.\n"
            "Objects without a magnitude (nebulae, dark clouds) are always kept."
        )
        _nofocus(self.spin_mag)
        grid.addWidget(self.spin_mag, row, 1)
        self.slider_mag = QSlider(Qt.Orientation.Horizontal)
        self.slider_mag.setRange(10, 200)
        self.slider_mag.setValue(120)
        _nofocus(self.slider_mag)
        grid.addWidget(self.slider_mag, row, 2)
        self.spin_mag.valueChanged.connect(
            lambda v: self.slider_mag.setValue(int(v * 10)))
        self.slider_mag.valueChanged.connect(
            lambda v: self.spin_mag.setValue(v / 10.0))

        row = 1
        lbl = QLabel("Max objects:")
        lbl.setFixedWidth(100)
        grid.addWidget(lbl, row, 0)
        self.spin_max_obj = QSpinBox()
        self.spin_max_obj.setRange(10, 5000)
        self.spin_max_obj.setValue(200)
        self.spin_max_obj.setFixedWidth(60)
        self.spin_max_obj.setToolTip(
            "Cap the number of objects rendered — prevents the plot\n"
            "from becoming unreadable in crowded fields."
        )
        _nofocus(self.spin_max_obj)
        grid.addWidget(self.spin_max_obj, row, 1)
        self.slider_max_obj = QSlider(Qt.Orientation.Horizontal)
        self.slider_max_obj.setRange(10, 2000)
        self.slider_max_obj.setValue(200)
        _nofocus(self.slider_max_obj)
        grid.addWidget(self.slider_max_obj, row, 2)
        self.spin_max_obj.valueChanged.connect(
            lambda v: self.slider_max_obj.setValue(min(v, 2000)))
        self.slider_max_obj.valueChanged.connect(self.spin_max_obj.setValue)

        row = 2
        self.chk_only_known = QCheckBox("Only objects with known distance")
        self.chk_only_known.setChecked(False)
        self.chk_only_known.setToolTip(
            "If enabled, objects without a catalogued distance\n"
            "(i.e. using a type-median fallback) are dropped."
        )
        _nofocus(self.chk_only_known)
        grid.addWidget(self.chk_only_known, row, 0, 1, 3)

        parent_layout.addWidget(group)

    def _build_data_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Data Sources")
        layout = QVBoxLayout(group)

        self.chk_use_online = QCheckBox("Query SIMBAD online")
        self.chk_use_online.setChecked(True)
        self.chk_use_online.setToolTip(
            "Query SIMBAD for object list and distances.\n"
            "Disable to work offline using only the local cache."
        )
        _nofocus(self.chk_use_online)
        layout.addWidget(self.chk_use_online)

        cache_row = QHBoxLayout()
        self.btn_clear_cache = QPushButton("Clear Distance Cache")
        self.btn_clear_cache.setStyleSheet("font-size:8pt;padding:4px")
        _nofocus(self.btn_clear_cache)
        self.btn_clear_cache.setToolTip(
            "Discard all cached distance measurements.\n"
            "Next render will re-query SIMBAD for every object."
        )
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        cache_row.addWidget(self.btn_clear_cache)
        self.lbl_cache_info = QLabel(self._cache_info_text())
        self.lbl_cache_info.setStyleSheet("color:#888888;font-size:8pt")
        cache_row.addWidget(self.lbl_cache_info, 1)
        layout.addLayout(cache_row)

        parent_layout.addWidget(group)

    def _cache_info_text(self) -> str:
        n = len(self._cache.data.get("objects", {}))
        return f"Cache: {n} objects"

    def _on_clear_cache(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Distance Cache",
            "Discard all cached distance measurements?\n"
            "They will be re-queried from SIMBAD next time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._cache.clear()
            self.lbl_cache_info.setText(self._cache_info_text())
            self._log("Distance cache cleared.")

    def _build_output_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        name_layout = QHBoxLayout()
        name_label = QLabel("Filename:")
        name_label.setFixedWidth(100)
        name_layout.addWidget(name_label)
        self.edit_filename = QLineEdit("cosmic_depth_3d")
        self.edit_filename.setToolTip(
            "Base filename (without extension) for HTML / PNG / CSV exports.\n"
            "A timestamp is appended automatically."
        )
        name_layout.addWidget(self.edit_filename)
        layout.addLayout(name_layout)

        dpi_layout = QHBoxLayout()
        dpi_label = QLabel("PNG DPI:")
        dpi_label.setFixedWidth(100)
        dpi_layout.addWidget(dpi_label)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 300)
        self.spin_dpi.setValue(150)
        self.spin_dpi.setFixedWidth(60)
        self.spin_dpi.setToolTip(
            "Output resolution for the PNG snapshot.\n"
            "150 is good for screens, 300 for print."
        )
        _nofocus(self.spin_dpi)
        dpi_layout.addWidget(self.spin_dpi)
        self.slider_dpi = QSlider(Qt.Orientation.Horizontal)
        self.slider_dpi.setRange(72, 300)
        self.slider_dpi.setValue(150)
        _nofocus(self.slider_dpi)
        dpi_layout.addWidget(self.slider_dpi)
        self.spin_dpi.valueChanged.connect(self.slider_dpi.setValue)
        self.slider_dpi.valueChanged.connect(self.spin_dpi.setValue)
        layout.addLayout(dpi_layout)

        parent_layout.addWidget(group)

    def _build_action_buttons(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)

        self.btn_render = QPushButton("Render 3D Map")
        self.btn_render.setObjectName("RenderButton")
        self.btn_render.setToolTip("Render the 3D map (F5)")
        _nofocus(self.btn_render)
        self.btn_render.clicked.connect(self._on_render)
        layout.addWidget(self.btn_render)

        export_row = QHBoxLayout()
        self.btn_export_html = QPushButton("Export HTML")
        self.btn_export_html.setEnabled(False)
        self.btn_export_html.setToolTip(
            "Save the interactive 3D scene as a standalone HTML file.")
        _nofocus(self.btn_export_html)
        self.btn_export_html.clicked.connect(self._on_export_html)
        export_row.addWidget(self.btn_export_html)

        self.btn_export_png = QPushButton("PNG")
        self.btn_export_png.setEnabled(False)
        self.btn_export_png.setToolTip(
            "Save a static 3D snapshot as PNG (matplotlib renderer).")
        _nofocus(self.btn_export_png)
        self.btn_export_png.clicked.connect(self._on_export_png)
        export_row.addWidget(self.btn_export_png)

        self.btn_export_csv = QPushButton("CSV")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.setToolTip(
            "Save the object table (name, type, RA, Dec, distance, ...) as CSV.")
        _nofocus(self.btn_export_csv)
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        export_row.addWidget(self.btn_export_csv)
        layout.addLayout(export_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("Status: Ready")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 9pt;")
        layout.addWidget(self.lbl_status)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_image_info = QLabel("No image loaded")
        self.lbl_image_info.setStyleSheet(
            "font-size: 10pt; color: #aaaaaa; padding: 4px; "
            "background-color: #333333; border-radius: 4px;"
        )
        self.lbl_image_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(self.lbl_image_info)

        self.tabs = QTabWidget()

        self.preview_widget = Preview3DWidget()
        self.preview_widget.repair_requested.connect(
            self._show_webengine_repair_dialog)
        self.tabs.addTab(self.preview_widget, "3D Map")

        self.objects_table = QTableWidget()
        self.objects_table.setColumnCount(6)
        self.objects_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Mag", "Distance (ly)",
             "± (ly)", "Source"]
        )
        self.objects_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.objects_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.objects_table.setAlternatingRowColors(True)
        self.objects_table.setSortingEnabled(True)
        self.objects_table.verticalHeader().setVisible(False)
        hdr = self.objects_table.horizontalHeader()
        # Make every column user-resizable with sensible defaults. Source
        # (last col) still stretches so the remaining space is absorbed
        # there. Interactive mode is required for saved column widths to
        # round-trip — ResizeToContents would clobber them on every render.
        default_widths = [140, 70, 55, 95, 70]  # Name, Type, Mag, Dist, ±
        for i, w in enumerate(default_widths):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            self.objects_table.setColumnWidth(i, w)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        # Keep columns from being squeezed into unreadable slivers on
        # narrow windows; Qt will honor setMinimumSectionSize regardless
        # of the Stretch / Interactive resize mode.
        hdr.setMinimumSectionSize(40)
        self.objects_table.setStyleSheet(
            "QTableWidget{background-color:#1e1e1e;color:#dddddd;"
            "gridline-color:#333333;alternate-background-color:#252525;"
            "font-size:9pt;}"
            "QHeaderView::section{background-color:#2a2a2a;color:#88aaff;"
            "padding:4px;border:0;border-bottom:1px solid #444;}"
            "QTableWidget::item:selected{background-color:#335577;}"
        )
        self.tabs.addTab(self.objects_table, "Objects")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color:#1e1e1e;color:#cccccc;"
            "font-family:monospace;font-size:9pt;"
        )
        self.tabs.addTab(self.log_text, "Log")

        r_layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open Output Folder")
        _nofocus(self.btn_open_folder)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.btn_open_folder)

        self.btn_open_html = QPushButton("Open Exported HTML")
        _nofocus(self.btn_open_html)
        self.btn_open_html.setEnabled(False)
        self.btn_open_html.clicked.connect(self._on_open_html)
        btn_row.addWidget(self.btn_open_html)

        r_layout.addLayout(btn_row)
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
        self.setWindowTitle("Svenesis CosmicDepth 3D")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 900)

    # ------------------------------------------------------------------
    # PERSISTENT SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        st = self._settings
        type_defaults = {"Gal": True, "Neb": True, "PN": True,
                         "OC": True, "GC": True, "Star": True,
                         "RN": False, "SNR": False, "DN": False,
                         "HII": False, "Ast": False, "QSO": False}
        for key, chk in self._type_checkboxes.items():
            chk.setChecked(st.value(f"type_{key}",
                                    type_defaults.get(key, True), type=bool))
        self.spin_mag.setValue(float(st.value("mag_limit", 12.0)))
        self.spin_max_obj.setValue(int(st.value("max_objects", 200)))
        self.chk_only_known.setChecked(st.value("only_known", False, type=bool))
        self.chk_use_online.setChecked(st.value("use_online", True, type=bool))
        self.chk_color_by_type.setChecked(st.value("color_by_type", True, type=bool))
        self.chk_show_image_plane.setChecked(
            st.value("show_image_plane", True, type=bool))
        self.spin_dpi.setValue(int(st.value("dpi", 150)))

        scale = ScaleMode.parse(st.value("scale_mode", ScaleMode.LOG.value),
                                ScaleMode.LOG)
        if scale is ScaleMode.LINEAR:
            self.radio_scale_linear.setChecked(True)
        elif scale is ScaleMode.HYBRID:
            self.radio_scale_hybrid.setChecked(True)
        else:
            self.radio_scale_log.setChecked(True)

        mode = DisplayMode.parse(st.value("display_mode",
                                          DisplayMode.COSMIC.value),
                                 DisplayMode.COSMIC)
        if mode is DisplayMode.GALACTIC:
            self.radio_mode_galactic.setChecked(True)
        else:
            self.radio_mode_cosmic.setChecked(True)

    def _save_settings(self) -> None:
        st = self._settings
        for key, chk in self._type_checkboxes.items():
            st.setValue(f"type_{key}", chk.isChecked())
        st.setValue("mag_limit", self.spin_mag.value())
        st.setValue("max_objects", self.spin_max_obj.value())
        st.setValue("only_known", self.chk_only_known.isChecked())
        st.setValue("use_online", self.chk_use_online.isChecked())
        st.setValue("color_by_type", self.chk_color_by_type.isChecked())
        st.setValue("show_image_plane",
                    self.chk_show_image_plane.isChecked())
        st.setValue("dpi", self.spin_dpi.value())
        st.setValue("scale_mode", self._current_scale_mode().value)
        st.setValue("display_mode", self._current_display_mode().value)
        # Persist the Objects table layout: header state captures column
        # order, widths and sort indicator in one opaque QByteArray.
        try:
            hdr = self.objects_table.horizontalHeader()
            st.setValue("objects_table_header", hdr.saveState())
            st.setValue("objects_table_sort_col",
                        int(hdr.sortIndicatorSection()))
            st.setValue("objects_table_sort_order",
                        int(hdr.sortIndicatorOrder().value))
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    def _current_scale_mode(self) -> ScaleMode:
        if self.radio_scale_linear.isChecked():
            return ScaleMode.LINEAR
        if self.radio_scale_hybrid.isChecked():
            return ScaleMode.HYBRID
        return ScaleMode.LOG

    def _current_display_mode(self) -> DisplayMode:
        return (DisplayMode.GALACTIC if self.radio_mode_galactic.isChecked()
                else DisplayMode.COSMIC)

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        if threading.current_thread() is not threading.main_thread():
            self._log_buffer.append(f"[CosmicDepth3D] {msg}")
            return
        self.log_text.append(f"[CosmicDepth3D] {msg}")
        try:
            self.siril.log(f"[CosmicDepth3D] {msg}")
        except (SirilError, OSError, RuntimeError, AttributeError):
            pass

    def _flush_log_buffer(self) -> None:
        while self._log_buffer:
            msg = self._log_buffer.pop(0)
            self.log_text.append(msg)
            try:
                self.siril.log(msg)
            except (SirilError, OSError, RuntimeError, AttributeError):
                pass

    def _update_progress(self, value: int, label: str = "") -> None:
        self.progress.setValue(value)
        if label:
            self.lbl_status.setText(f"Status: {label}")
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # SIRIL IMAGE / WCS LOADING
    # ------------------------------------------------------------------

    def _load_from_siril(self) -> bool:
        no_image_msg = ("No image is currently loaded in Siril. "
                        "Please load a plate-solved FITS image first.")
        try:
            if not self.siril.connected:
                self.siril.connect()

            with self.siril.image_lock():
                try:
                    preview = self.siril.get_image_pixeldata(
                        preview=True, linked=True)
                    if preview is not None:
                        self._image_data = np.array(preview, dtype=np.uint8)
                    else:
                        raise ValueError("No preview data")
                except Exception:
                    fit = self.siril.get_image()
                    fit.ensure_data_type(np.float32)
                    data = np.array(fit.data, dtype=np.float32)
                    del fit
                    if data.ndim == 3:
                        data = np.transpose(data, (1, 2, 0))
                    elif data.ndim == 2:
                        data = np.stack([data] * 3, axis=-1)
                    vmin, vmax = np.percentile(data, [1, 99])
                    if vmax > vmin:
                        data -= vmin
                        data *= (255.0 / (vmax - vmin))
                        np.clip(data, 0, 255, out=data)
                    self._image_data = data.astype(np.uint8)
                    del data

                fit = self.siril.get_image()
                self._img_width = fit.width
                self._img_height = fit.height
                self._img_channels = fit.channels
                del fit

            if self._image_data is not None:
                if (self._image_data.ndim == 3
                        and self._image_data.shape[0] in (1, 3)):
                    self._image_data = np.transpose(self._image_data, (1, 2, 0))
                if self._image_data.ndim == 2:
                    self._image_data = np.stack([self._image_data] * 3, axis=-1)
                if self._image_data.shape[2] == 1:
                    self._image_data = np.repeat(self._image_data, 3, axis=2)

            self._is_plate_solved = False
            self._wcs = None
            self._header_str = ""

            # Step 1: header as dict
            try:
                header_dict = self.siril.get_image_fits_header(return_as="dict")
                if header_dict:
                    wcs = WCS(header_dict, naxis=[1, 2])
                    if wcs.has_celestial:
                        self._wcs = wcs
                        self._is_plate_solved = True
                        self._log("WCS: extracted from header dict")
            except Exception as e:
                self._log(f"WCS header dict failed: {e}")

            # Step 2: header as string
            if self._wcs is None:
                try:
                    hdr_str = self.siril.get_image_fits_header(return_as="str")
                    if hdr_str:
                        self._header_str = hdr_str
                        self._wcs = extract_wcs_from_header(hdr_str)
                        if self._wcs is not None:
                            self._is_plate_solved = True
                            self._log("WCS: extracted from header string")
                        elif "CRVAL1" in hdr_str:
                            self._is_plate_solved = True
                except Exception as e:
                    self._log(f"WCS header str failed: {e}")

            # Step 3: keyword check
            if not self._is_plate_solved:
                try:
                    kw = self.siril.get_image_keywords()
                    if kw is not None:
                        self._is_plate_solved = bool(getattr(kw, "pltsolvd", False))
                        if not self._is_plate_solved:
                            self._is_plate_solved = bool(getattr(kw, "wcsdata", None))
                except Exception:
                    pass

            # Step 4: build WCS from pix2radec sampling
            if self._wcs is None and self._is_plate_solved:
                self._wcs = self._build_wcs_from_siril()
                if self._wcs is not None:
                    self._log("WCS: built from sirilpy pix2radec")

            # Step 5: try pix2radec even without plate-solve flag
            if self._wcs is None:
                try:
                    cx, cy = self._img_width / 2, self._img_height / 2
                    result = self.siril.pix2radec(cx, cy)
                    if result is not None:
                        self._is_plate_solved = True
                        self._wcs = self._build_wcs_from_siril()
                        if self._wcs is not None:
                            self._log("WCS: built from sirilpy pix2radec")
                except Exception:
                    pass

            # Step 6: FITS file on disk
            if self._wcs is None:
                self._wcs = extract_wcs_from_fits_file(self.siril,
                                                      log_func=self._log)
                if self._wcs is not None:
                    self._is_plate_solved = True
                    self._log("WCS: extracted from FITS file on disk")

            if self._wcs is not None:
                self._is_plate_solved = True
                self._pixel_scale = compute_pixel_scale(self._wcs)
            else:
                self._pixel_scale = 1.0

            ch_str = "RGB" if self._img_channels >= 3 else "Mono"
            wcs_str = "plate-solved \u2713" if self._is_plate_solved else "NOT plate-solved \u2717"
            self.lbl_image_info.setText(
                f"{self._img_width} \u00d7 {self._img_height} px  |  "
                f"{ch_str}  |  {wcs_str}"
            )
            self._log(f"Image: {self._img_width}x{self._img_height}, "
                      f"plate_solved={self._is_plate_solved}, "
                      f"scale={self._pixel_scale:.2f}\"/px")
            return True

        except NoImageError:
            QMessageBox.warning(self, "No Image", no_image_msg)
            return False
        except SirilConnectionError:
            QMessageBox.warning(self, "Connection Error",
                                "Could not connect to Siril. Make sure Siril is running.")
            return False
        except SirilError as e:
            if "no image" in str(e).lower():
                QMessageBox.warning(self, "No Image", no_image_msg)
            else:
                QMessageBox.warning(self, "Siril Error", str(e))
            return False
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load image:\n{e}\n\n{traceback.format_exc()}",
            )
            return False

    def _build_wcs_from_siril(self) -> WCS | None:
        try:
            w, h = self._img_width, self._img_height
            cx, cy = w / 2.0, h / 2.0
            ra_c, dec_c = self.siril.pix2radec(cx, cy)
            delta = 10.0
            ra_r, dec_r = self.siril.pix2radec(cx + delta, cy)
            ra_u, dec_u = self.siril.pix2radec(cx, cy + delta)
            cos_dec = np.cos(np.radians(dec_c))
            cd1_1 = (ra_r - ra_c) * cos_dec / delta
            cd1_2 = (ra_u - ra_c) * cos_dec / delta
            cd2_1 = (dec_r - dec_c) / delta
            cd2_2 = (dec_u - dec_c) / delta
            for val in ("cd1_1", "cd1_2"):
                pass
            if cd1_1 > 180:
                cd1_1 -= 360
            elif cd1_1 < -180:
                cd1_1 += 360
            if cd1_2 > 180:
                cd1_2 -= 360
            elif cd1_2 < -180:
                cd1_2 += 360
            wcs = WCS(naxis=2)
            wcs.wcs.crpix = [cx + 1, cy + 1]
            wcs.wcs.crval = [ra_c, dec_c]
            wcs.wcs.cd = np.array([[cd1_1, cd1_2], [cd2_1, cd2_2]])
            wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
            wcs.array_shape = (h, w)
            test_ra, test_dec = wcs.all_pix2world([[cx, cy]], 0)[0]
            if abs(test_ra - ra_c) < 0.01 and abs(test_dec - dec_c) < 0.01:
                return wcs
        except Exception as e:
            self._log(f"_build_wcs_from_siril failed: {e}")
        return None

    # ------------------------------------------------------------------
    # SIMBAD OBJECT QUERY
    # ------------------------------------------------------------------

    def _query_simbad_objects(self, mag_limit: float,
                              progress_cb=None,
                              ) -> tuple[list[dict], float, float, float]:
        """
        Query SIMBAD for all catalog objects in the field of view.
        Returns (objects, center_ra, center_dec, fov_radius_deg).
        """
        try:
            cx, cy = self._img_width / 2.0, self._img_height / 2.0
            center = self.siril.pix2radec(cx, cy)
            corner = self.siril.pix2radec(0, 0)
            if center is None or corner is None:
                self._log("ERROR: pix2radec failed")
                return [], 0.0, 0.0, 0.0
            center_ra, center_dec = float(center[0]), float(center[1])
            c1 = SkyCoord(center_ra, center_dec, unit="deg")
            c2 = SkyCoord(float(corner[0]), float(corner[1]), unit="deg")
            fov_radius_deg = c1.separation(c2).deg
        except Exception as e:
            self._log(f"FOV calc failed: {e}")
            return [], 0.0, 0.0, 0.0

        if not self.chk_use_online.isChecked():
            self._log("Offline mode: skipping SIMBAD query.")
            return [], center_ra, center_dec, fov_radius_deg

        try:
            custom = Simbad()
            custom.add_votable_fields("V", "galdim_majaxis", "otype")
            custom.ROW_LIMIT = 3000

            MAX_Q = 0.75  # deg — SIMBAD works best with ≤45' radius
            if fov_radius_deg <= MAX_Q:
                tiles = [c1]
                q_radius = Angle(fov_radius_deg, unit="deg")
            else:
                step = MAX_Q * 1.2
                half_w = (self._img_width * self._pixel_scale / 3600.0) / 2.0
                half_h = (self._img_height * self._pixel_scale / 3600.0) / 2.0
                tiles = []
                d = center_dec - half_h
                while d <= center_dec + half_h + step * 0.5:
                    cd = max(0.1, math.cos(math.radians(d)))
                    ra_step = step / cd
                    r = center_ra - half_w / cd
                    r_end = center_ra + half_w / cd
                    while r <= r_end + ra_step * 0.5:
                        tiles.append(SkyCoord(r, d, unit="deg"))
                        r += ra_step
                    d += step
                q_radius = Angle(MAX_Q, unit="deg")
                self._log(f"SIMBAD: wide field — tiling into {len(tiles)} queries")

            from astropy.table import vstack
            all_results = []

            def _query_tile(qc):
                tile_simbad = Simbad()
                tile_simbad.add_votable_fields("V", "galdim_majaxis", "otype")
                tile_simbad.ROW_LIMIT = 3000
                return tile_simbad.query_region(qc, radius=q_radius)

            if len(tiles) == 1:
                if progress_cb:
                    progress_cb(0, 1)
                r = _query_tile(tiles[0])
                if r is not None and len(r) > 0:
                    all_results.append(r)
                if progress_cb:
                    progress_cb(1, 1)
            else:
                # Stream tiles as they finish so the progress bar advances
                # per-tile instead of jumping from 15% straight to 45%.
                from concurrent.futures import as_completed
                done = 0
                total = len(tiles)
                with ThreadPoolExecutor(
                    max_workers=min(8, total),
                    thread_name_prefix="simbad_tile",
                ) as pool:
                    futures = [pool.submit(_query_tile, qc) for qc in tiles]
                    for fut in as_completed(futures):
                        try:
                            r = fut.result()
                        except Exception:
                            r = None
                        if r is not None and len(r) > 0:
                            all_results.append(r)
                        done += 1
                        if progress_cb:
                            progress_cb(done, total)

            if not all_results:
                self._log("SIMBAD: no objects returned")
                return [], center_ra, center_dec, fov_radius_deg

            if len(all_results) == 1:
                result = all_results[0]
            else:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = vstack(all_results)

            # Column resolution
            id_col = ra_col = dec_col = None
            for c in result.colnames:
                lc = c.lower()
                if lc == "main_id":
                    id_col = c
                elif lc == "ra":
                    ra_col = c
                elif lc == "dec":
                    dec_col = c
            if not id_col or not ra_col or not dec_col:
                self._log(f"SIMBAD: unexpected columns: {result.colnames}")
                return [], center_ra, center_dec, fov_radius_deg

            size_col = None
            for sc in ("galdim_majaxis", "GALDIM_MAJAXIS",
                       "DIM_MAJAXIS", "dim_majaxis"):
                if sc in result.colnames:
                    size_col = sc
                    break
            otype_col = None
            for tc in ("otype", "OTYPE"):
                if tc in result.colnames:
                    otype_col = tc
                    break
            has_V = "V" in result.colnames

            # Accept only well-known astrophotography catalog prefixes
            _USEFUL_PREFIXES = (
                "NGC", "IC ", "IC1", "IC2", "IC3", "IC4", "IC5",
                "M ", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
                "UGC", "MCG", "Arp", "Abell", "Mrk", "VV ",
                "Ced", "Sh2", "LBN", "LDN", "Barnard", "B ",
                "Cr ", "Mel", "Tr ", "Pal", "PGC", "ESO", "CGCG",
                "Hickson", "HCG", "PN G",
                "Hen", "He ", "Haro",
                "NAME ", "V*", "HD ", "HR ",
                "vdB", "RCW", "Gum", "Collinder", "Stock", "DWB",
            )
            _prefix_by_char: dict[str, list[str]] = {}
            for p in _USEFUL_PREFIXES:
                _prefix_by_char.setdefault(p[0], []).append(p)

            def _is_useful(name: str) -> bool:
                cs = _prefix_by_char.get(name[0]) if name else None
                return cs is not None and any(name.startswith(p) for p in cs)

            seen_names: set[str] = set()
            objects: list[dict] = []
            for row in result:
                try:
                    name = str(row[id_col]).strip()
                except Exception:
                    continue
                if not name or not _is_useful(name):
                    continue
                if name in seen_names:
                    continue
                seen_names.add(name)

                try:
                    ra = _safe_float(row[ra_col])
                    dec = _safe_float(row[dec_col])
                    if np.isnan(ra) or np.isnan(dec):
                        coord = SkyCoord(str(row[ra_col]), str(row[dec_col]),
                                         unit=(u.hourangle, u.deg))
                        ra, dec = coord.ra.deg, coord.dec.deg
                except Exception:
                    continue

                mag = _safe_float(row["V"] if has_V else None, default=0.0)
                if mag != 0.0 and not np.isnan(mag) and mag > mag_limit:
                    continue
                if np.isnan(mag):
                    mag = 0.0

                otype = ""
                if otype_col:
                    try:
                        otype = str(row[otype_col]).strip()
                    except Exception:
                        pass
                obj_type = SIMBAD_TYPE_MAP.get(otype)
                if obj_type is None:
                    obj_type = "Star" if "*" in otype else "Other"

                # FOV bounds check via pixel coords
                try:
                    result_pix = self.siril.radec2pix(ra, dec)
                    if result_pix is None:
                        continue
                    px, py = float(result_pix[0]), float(result_pix[1])
                except Exception:
                    continue
                if not (0 <= px <= self._img_width and 0 <= py <= self._img_height):
                    continue

                size_arcmin = _safe_float(row[size_col], 0.0) if size_col else 0.0
                if np.isnan(size_arcmin):
                    size_arcmin = 0.0

                objects.append({
                    "name": name,
                    "display_name": name,
                    "ra": ra,
                    "dec": dec,
                    "type": obj_type,
                    "mag": mag,
                    "size_arcmin": size_arcmin,
                    "pixel_x": px,
                    "pixel_y": py,
                })

            self._log(f"SIMBAD: {len(objects)} useful objects in FOV")
            return objects, center_ra, center_dec, fov_radius_deg

        except Exception as e:
            self._log(f"SIMBAD query failed: {e}")
            return [], center_ra, center_dec, fov_radius_deg

    # ------------------------------------------------------------------
    # RENDER WORKFLOW
    # ------------------------------------------------------------------

    def _on_render(self) -> None:
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log_text.clear()

        self._log("Starting CosmicDepth 3D render...")
        self._update_progress(5, "Loading image from Siril...")

        if not self._load_from_siril():
            self.progress.setVisible(False)
            self.lbl_status.setText("Status: Failed to load image")
            return

        if not self._is_plate_solved or self._wcs is None:
            QMessageBox.warning(
                self, "Not Plate-Solved",
                "The image is not plate-solved. Please run Plate Solving first.\n\n"
                "In Siril: Tools \u2192 Astrometry \u2192 Image Plate Solver..."
            )
            self._log("ERROR: Image is not plate-solved. Aborting.")
            self.progress.setVisible(False)
            return

        self._update_progress(15, "Querying SIMBAD cone search...")
        mag_limit = self.spin_mag.value()
        enabled_types = {k for k, chk in self._type_checkboxes.items()
                         if chk.isChecked()}
        self._log(f"Enabled types: {', '.join(sorted(enabled_types))}")
        self._log(f"Magnitude limit: {mag_limit:.1f}")

        # Map tile progress into the 15%–40% slice of the overall bar so
        # the user sees continuous movement while SIMBAD streams tiles.
        _SIMBAD_LO, _SIMBAD_HI = 15, 40

        def _simbad_progress(done: int, total: int) -> None:
            if total <= 0:
                return
            frac = max(0.0, min(1.0, done / float(total)))
            pct = int(round(_SIMBAD_LO + frac * (_SIMBAD_HI - _SIMBAD_LO)))
            self._update_progress(
                pct, f"SIMBAD tiles: {done}/{total}")

        objects, center_ra, center_dec, fov_radius = self._query_simbad_objects(
            mag_limit, progress_cb=_simbad_progress,
        )
        self._flush_log_buffer()

        # Type filter
        if enabled_types:
            objects = [o for o in objects if o["type"] in enabled_types]
        self._log(f"After type filter: {len(objects)} objects")

        if not objects:
            self._log("No catalog objects found in the field of view.")
            QMessageBox.information(
                self, "No Objects",
                "No catalog objects were found in the image field of view.\n\n"
                "Check your object-type selection, magnitude limit, or\n"
                "whether the image is correctly plate-solved."
            )
            self.progress.setVisible(False)
            self.lbl_status.setText("Status: No objects found")
            return

        # Attach physical size
        for obj in objects:
            obj["size_ly"] = 0.0  # updated after distance resolve

        # Resolve distances
        self._update_progress(
            _SIMBAD_HI, "Resolving distances (SIMBAD / cache)...")
        _RESOLVE_LO, _RESOLVE_HI = _SIMBAD_HI, 70

        def _resolve_progress(done: int, total: int) -> None:
            if total <= 0:
                return
            frac = max(0.0, min(1.0, done / float(total)))
            pct = int(round(_RESOLVE_LO + frac * (_RESOLVE_HI - _RESOLVE_LO)))
            self._update_progress(
                pct, f"Resolving distances: batch {done}/{total}")

        resolve_distances(objects, self._cache,
                          use_online=self.chk_use_online.isChecked(),
                          log_func=self._log,
                          progress_cb=_resolve_progress)
        self._flush_log_buffer()
        self.lbl_cache_info.setText(self._cache_info_text())

        # Compute physical size from angular size + distance
        for obj in objects:
            obj["size_ly"] = angular_to_physical_size_ly(
                obj.get("size_arcmin", 0.0), obj.get("dist_ly", 0.0),
            )

        # Filter: only-known-distance toggle
        if self.chk_only_known.isChecked():
            before = len(objects)
            objects = [o for o in objects if o.get("dist_source") != "Type median"]
            self._log(f"Only-known-distance filter: kept {len(objects)}/{before}")

        # Cap number of objects — keep the brightest / most well-measured
        def _sort_key(o: dict) -> tuple:
            # prefer high-confidence distances, then brighter magnitudes
            conf_rank = {"high": 0, "medium": 1, "low": 2, "estimate": 3}
            return (conf_rank.get(o.get("dist_confidence", "medium"), 1),
                    o.get("mag", 99.0) or 99.0)

        objects.sort(key=_sort_key)
        max_n = int(self.spin_max_obj.value())
        if len(objects) > max_n:
            self._log(f"Limiting to {max_n} most relevant objects "
                      f"(of {len(objects)} available)")
            objects = objects[:max_n]

        self._last_objects = objects
        self._populate_objects_tab(objects)

        # Build config + render
        self._update_progress(75, "Building 3D scene...")
        scale_mode = self._current_scale_mode()
        display_mode = self._current_display_mode()

        # Title with FOV + center
        try:
            ra_hms = SkyCoord(center_ra, center_dec, unit="deg") \
                .to_string("hmsdms", precision=0)
        except Exception:
            ra_hms = f"RA={center_ra:.2f} DEC={center_dec:.2f}"

        title = (f"Svenesis CosmicDepth 3D — {len(objects)} objects, "
                 f"{scale_mode.value} scale, {display_mode.value} view")

        config = {
            "scale_mode": scale_mode.value,
            "display_mode": display_mode.value,
            "color_by_type": self.chk_color_by_type.isChecked(),
            "dpi": self.spin_dpi.value(),
            "title": title,
        }

        # Scene dimensions for the window-style layout
        scaled_ds = [scale_distance(o["dist_ly"], scale_mode.value)
                     for o in objects if o.get("dist_ly", 0) > 0]
        max_scaled = max(scaled_ds) if scaled_ds else 100.0
        ref_depth = compute_ref_depth(scale_mode, max_scaled)

        config["wcs"] = self._wcs
        config["img_width"] = self._img_width
        config["img_height"] = self._img_height
        config["ref_depth"] = ref_depth

        image_plane = None
        if not self.chk_show_image_plane.isChecked():
            self._log("Sky plane: disabled by checkbox.")
        elif self._image_data is None:
            self._log("Sky plane: no image pixel data available.")
        elif self._wcs is None:
            self._log("Sky plane: no WCS available.")
        elif not scaled_ds:
            self._log("Sky plane: no objects with positive distance.")
        else:
            try:
                sample_n = smart_sample_size(
                    self._img_width, self._img_height)
                X, Y, Z, lum, rgb = build_flat_image_plane(
                    self._image_data,
                    self._img_width, self._img_height,
                    ref_depth=ref_depth,
                    sample=sample_n,
                )
                image_plane = {
                    "X": X, "Y": Y, "Z": Z,
                    "lum": lum, "rgb": rgb,
                    "opacity": 1.0,
                    "ref_depth": ref_depth,
                }
                self._log(
                    f"Sky plane built: ref_depth={ref_depth:.3f}, "
                    f"pixel footprint {self._img_width}×{self._img_height}, "
                    f"sample={sample_n}×{sample_n}, "
                    f"max_depth={max_scaled:.2f}."
                )
            except Exception as e:
                self._log(f"Image plane build failed: {e}\n"
                          f"{traceback.format_exc()}")
                image_plane = None
        self._last_image_plane = image_plane

        fig = build_plotly_figure(objects, config, image_plane=image_plane)
        self._last_figure = fig

        # Render into preview (and remember output paths for exports)
        try:
            wd = self.siril.get_siril_wd() or os.getcwd()
        except Exception:
            wd = os.getcwd()
        base = self.edit_filename.text().strip() or "cosmic_depth_3d"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._last_html_path = os.path.join(wd, f"{base}_{ts}.html")
        self._last_png_path = os.path.join(wd, f"{base}_{ts}.png")
        self._last_csv_path = os.path.join(wd, f"{base}_{ts}.csv")

        rendered = False
        if fig is not None and HAS_WEBENGINE:
            try:
                # Reference the cached plotly.min.js via 'directory' mode
                # instead of inlining ~3.5 MB on every render. show_html()
                # writes the HTML next to the cached bundle so the
                # relative <script src> resolves under file://.
                html_content = pio.to_html(fig, full_html=True,
                                           include_plotlyjs="directory")
                self.preview_widget.show_html(html_content)
                self._log("Rendered interactive Plotly view (QWebEngineView).")
                rendered = True
            except Exception as e:
                self._log(f"Plotly render failed: {e}")

        if not rendered:
            # No WebEngine: render matplotlib PNG for the embedded preview,
            # AND write the interactive Plotly HTML and open it in the user's
            # default browser so they still get the rotatable 3D scene.
            if WEBENGINE_ERROR:
                self._log(f"WebEngine import failed: {WEBENGINE_ERROR}")
                self._log("Tip: click \u201cRepair WebEngine\u2026\u201d on "
                          "the 3D Map pane to run an opt-in pinned "
                          "reinstall with live pip output.")
            try:
                self._log("WebEngine unavailable — using matplotlib preview.")
                render_matplotlib_3d(objects, config, self._last_png_path,
                                     image_plane=image_plane)
                self.preview_widget.show_png(self._last_png_path)
            except Exception as e:
                self._log(f"Matplotlib fallback failed: {e}")
                QMessageBox.critical(
                    self, "Render Error",
                    f"3D render failed:\n{e}\n\n{traceback.format_exc()}"
                )
                self.progress.setVisible(False)
                return

            if fig is not None:
                try:
                    html_content = pio.to_html(fig, full_html=True,
                                               include_plotlyjs="cdn")
                    with open(self._last_html_path, "w",
                              encoding="utf-8") as f:
                        f.write(html_content)
                    QDesktopServices.openUrl(
                        QUrl.fromLocalFile(self._last_html_path))
                    self._log(f"Opened rotatable 3D view in browser: "
                              f"{self._last_html_path}")
                except Exception as e:
                    self._log(f"Could not open browser view: {e}")

        self.tabs.setCurrentIndex(0)

        self.btn_export_html.setEnabled(HAS_PLOTLY and fig is not None)
        self.btn_export_png.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
        self.btn_open_folder.setEnabled(True)

        self._update_progress(100, f"Done — {len(objects)} objects")
        self._log(f"Render complete: {len(objects)} objects.")
        self.progress.setVisible(False)
        gc.collect()

    def _on_image_plane_toggled(self, checked: bool) -> None:
        """Rebuild the figure without re-querying SIMBAD."""
        if not self._last_objects or self._wcs is None:
            return
        scale_mode = self._current_scale_mode()
        display_mode = self._current_display_mode()
        scaled_ds = [scale_distance(o["dist_ly"], scale_mode.value)
                     for o in self._last_objects if o.get("dist_ly", 0) > 0]
        max_scaled = max(scaled_ds) if scaled_ds else 100.0
        ref_depth = compute_ref_depth(scale_mode, max_scaled)

        config = {
            "scale_mode": scale_mode.value,
            "display_mode": display_mode.value,
            "color_by_type": self.chk_color_by_type.isChecked(),
            "dpi": self.spin_dpi.value(),
            "title": (f"Svenesis CosmicDepth 3D — {len(self._last_objects)} "
                      f"objects, {scale_mode.value} scale, "
                      f"{display_mode.value} view"),
            "wcs": self._wcs,
            "img_width": self._img_width,
            "img_height": self._img_height,
            "ref_depth": ref_depth,
        }
        image_plane = None
        if checked and self._image_data is not None and scaled_ds:
            try:
                sample_n = smart_sample_size(
                    self._img_width, self._img_height)
                X, Y, Z, lum, rgb = build_flat_image_plane(
                    self._image_data,
                    self._img_width, self._img_height,
                    ref_depth=ref_depth,
                    sample=sample_n,
                )
                image_plane = {
                    "X": X, "Y": Y, "Z": Z,
                    "lum": lum, "rgb": rgb, "opacity": 1.0,
                    "ref_depth": ref_depth,
                }
                self._log(
                    f"Sky plane toggled ON: ref_depth={ref_depth:.3f}, "
                    f"sample={sample_n}×{sample_n}.")
            except Exception as e:
                self._log(f"Image plane build failed: {e}")
        else:
            self._log("Sky plane toggled OFF.")
        self._last_image_plane = image_plane

        fig = build_plotly_figure(self._last_objects, config,
                                  image_plane=image_plane)
        self._last_figure = fig
        if fig is not None and HAS_WEBENGINE:
            try:
                html_content = pio.to_html(fig, full_html=True,
                                           include_plotlyjs="directory")
                self.preview_widget.show_html(html_content)
            except Exception as e:
                self._log(f"Plotly refresh failed: {e}")

    def _restore_objects_table_layout(self) -> None:
        """Restore the Objects table header state (column widths + sort).

        Uses the opaque ``saveState``/``restoreState`` blob QHeaderView
        produces. Falls back silently if nothing is stored or the saved
        state can't be decoded (e.g. after a column-count change).
        """
        try:
            st = self._settings
            hdr = self.objects_table.horizontalHeader()
            raw = st.value("objects_table_header")
            restored = False
            if raw is not None:
                try:
                    restored = bool(hdr.restoreState(raw))
                except Exception:
                    restored = False
            # Fall back to the explicit sort-col / sort-order pair in case
            # the opaque blob couldn't round-trip (Qt version skew).
            if not restored:
                try:
                    col = int(st.value("objects_table_sort_col", -1))
                    order_val = int(st.value("objects_table_sort_order", 0))
                    if col >= 0 and col < self.objects_table.columnCount():
                        order = (Qt.SortOrder.DescendingOrder
                                 if order_val == Qt.SortOrder.DescendingOrder.value
                                 else Qt.SortOrder.AscendingOrder)
                        self.objects_table.sortItems(col, order)
                except Exception:
                    pass
        except Exception:
            pass

    def _populate_objects_tab(self, objects: list[dict]) -> None:
        tbl = self.objects_table
        # Disable sorting while mutating rows so items land in the right
        # columns; we re-enable it below and apply any persisted sort.
        tbl.setSortingEnabled(False)
        tbl.setRowCount(len(objects))

        def _num_item(value: float, text: str) -> QTableWidgetItem:
            it = QTableWidgetItem()
            it.setData(Qt.ItemDataRole.EditRole, float(value))
            it.setText(text)
            it.setTextAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter)
            return it

        for row, obj in enumerate(objects):
            name = obj.get("display_name") or obj.get("name", "?")
            t = obj.get("type", "?")
            mag = obj.get("mag", 0.0) or 0.0
            d = obj.get("dist_ly", 0.0) or 0.0
            unc = obj.get("dist_uncertainty_ly", 0.0) or 0.0
            src = obj.get("dist_source", "?")

            tbl.setItem(row, 0, QTableWidgetItem(str(name)))
            tbl.setItem(row, 1, QTableWidgetItem(str(t)))
            tbl.setItem(row, 2, _num_item(
                mag, f"{mag:.1f}" if mag != 0.0 else "?"))
            tbl.setItem(row, 3, _num_item(d, f"{d:,.0f}"))
            tbl.setItem(row, 4, _num_item(unc, f"{unc:,.0f}"))
            tbl.setItem(row, 5, QTableWidgetItem(str(src)))

        tbl.setSortingEnabled(True)
        # First population after a fresh launch: restore the last-used
        # column widths / sort order. We guard with a flag so the user's
        # in-session changes stick between subsequent renders.
        if not getattr(self, "_objects_table_layout_restored", False):
            self._restore_objects_table_layout()
            self._objects_table_layout_restored = True

    # ------------------------------------------------------------------
    # EXPORT ACTIONS
    # ------------------------------------------------------------------

    def _on_export_html(self) -> None:
        if self._last_figure is None:
            return
        try:
            html_str = pio.to_html(self._last_figure, full_html=True,
                                   include_plotlyjs="cdn")
            with open(self._last_html_path, "w", encoding="utf-8") as f:
                f.write(html_str)
            self._log(f"Exported HTML: {self._last_html_path}")
            self.btn_open_html.setEnabled(True)
            QMessageBox.information(
                self, "HTML Exported",
                f"Interactive 3D map saved:\n{self._last_html_path}"
            )
        except Exception as e:
            self._log(f"HTML export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export HTML:\n{e}")

    def _capture_current_camera(self) -> dict | None:
        """Best-effort read of the current Plotly camera from the embedded
        QWebEngineView.

        Plotly mirrors user rotations back into ``gd.layout.scene.camera``
        (eye / center / up), so a single JSON round-trip from the running
        JavaScript gives us the view the user is actually looking at.
        Runs a short local event loop with a 2-second safety timeout so a
        broken view never hangs the export.
        """
        if not HAS_WEBENGINE:
            return None
        view = getattr(self.preview_widget, "_view", None)
        if view is None:
            return None
        try:
            from PyQt6.QtCore import QEventLoop, QTimer
        except Exception:
            return None
        loop = QEventLoop()
        holder: dict = {"raw": None}

        def _got(raw):
            holder["raw"] = raw
            loop.quit()

        js = (
            "(function(){try{"
            "var els=document.getElementsByClassName('plotly-graph-div');"
            "if(!els||!els.length)return null;"
            "var gd=els[0];"
            "var scene=gd&&gd.layout?gd.layout.scene:null;"
            "if(!scene||!scene.camera)return null;"
            "return JSON.stringify(scene.camera);"
            "}catch(e){return null;}})();"
        )
        try:
            view.page().runJavaScript(js, _got)
        except Exception:
            return None
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        raw = holder["raw"]
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _on_export_png(self) -> None:
        """Export the rendered 3D scene as a PNG.

        Uses Plotly + kaleido for pixel-for-pixel parity with the embedded
        WebEngine view (same axes, same ``aspectratio``, same camera —
        including any rotation the user applied). Falls back to the
        matplotlib renderer only if kaleido is missing or the Plotly
        figure wasn't produced (e.g. plotly install broken).
        """
        if not self._last_objects:
            return

        # Prefer the live figure — that's what the 3D pane is showing.
        fig = self._last_figure
        dpi = max(50, int(self.spin_dpi.value()))
        # Render at a generous base resolution and let kaleido's `scale`
        # multiplier do the DPI upscaling without forcing huge pixel
        # counts for the layout pass.
        base_width, base_height = 1400, 1000
        px_scale = max(1.0, dpi / 100.0)

        if fig is not None:
            # Clone so we don't permanently mutate the live figure's camera.
            try:
                import copy
                export_fig = copy.deepcopy(fig)
            except Exception:
                export_fig = fig

            cam = self._capture_current_camera()
            if cam:
                try:
                    export_fig.update_layout(scene_camera=cam)
                    self._log(
                        f"Export camera captured from live view: "
                        f"eye={cam.get('eye')}")
                except Exception:
                    pass

            try:
                pio.write_image(
                    export_fig, self._last_png_path,
                    format="png",
                    width=base_width, height=base_height,
                    scale=px_scale,
                )
                self._log(
                    f"Exported PNG via Plotly/kaleido "
                    f"({int(base_width * px_scale)}\u00d7"
                    f"{int(base_height * px_scale)}): "
                    f"{self._last_png_path}")
                QMessageBox.information(
                    self, "PNG Exported",
                    f"Static 3D snapshot saved:\n{self._last_png_path}"
                )
                return
            except Exception as e:
                self._log(
                    f"Plotly PNG export failed ({type(e).__name__}: {e}); "
                    f"falling back to matplotlib. "
                    f"If kaleido is missing, run: "
                    f"pip install --upgrade kaleido")

        # Matplotlib fallback — won't match the Plotly view exactly but
        # still produces a usable snapshot when kaleido isn't available.
        try:
            scale_mode = self._current_scale_mode()
            scaled_ds = [scale_distance(o["dist_ly"], scale_mode.value)
                         for o in self._last_objects
                         if o.get("dist_ly", 0) > 0]
            max_scaled = max(scaled_ds) if scaled_ds else 100.0
            ref_depth = compute_ref_depth(scale_mode, max_scaled)
            config = {
                "scale_mode": scale_mode.value,
                "display_mode": self._current_display_mode().value,
                "color_by_type": self.chk_color_by_type.isChecked(),
                "dpi": dpi,
                "title": (f"Svenesis CosmicDepth 3D — "
                          f"{len(self._last_objects)} objects"),
                "wcs": self._wcs,
                "img_width": self._img_width,
                "img_height": self._img_height,
                "ref_depth": ref_depth,
            }
            render_matplotlib_3d(
                self._last_objects, config, self._last_png_path,
                image_plane=getattr(self, "_last_image_plane", None))
            self._log(f"Exported PNG (matplotlib fallback): "
                      f"{self._last_png_path}")
            QMessageBox.information(
                self, "PNG Exported",
                f"Static 3D snapshot saved (matplotlib fallback):\n"
                f"{self._last_png_path}\n\n"
                f"Note: this image does not match the embedded 3D view "
                f"pixel-for-pixel. Install kaleido for an exact copy "
                f"(pip install --upgrade kaleido)."
            )
        except Exception as e:
            self._log(f"PNG export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export PNG:\n{e}")

    def _on_export_csv(self) -> None:
        if not self._last_objects:
            return
        try:
            import csv
            with open(self._last_csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow([
                    "name", "type", "ra_deg", "dec_deg", "magnitude",
                    "size_arcmin", "dist_ly", "uncertainty_ly",
                    "size_ly", "dist_source", "dist_confidence",
                    "pixel_x", "pixel_y",
                ])
                for obj in self._last_objects:
                    w.writerow([
                        obj.get("name", ""),
                        obj.get("type", ""),
                        f"{obj.get('ra', 0.0):.6f}",
                        f"{obj.get('dec', 0.0):.6f}",
                        f"{obj.get('mag', 0.0):.2f}",
                        f"{obj.get('size_arcmin', 0.0):.3f}",
                        f"{obj.get('dist_ly', 0.0):.1f}",
                        f"{obj.get('dist_uncertainty_ly', 0.0):.1f}",
                        f"{obj.get('size_ly', 0.0):.3f}",
                        obj.get("dist_source", ""),
                        obj.get("dist_confidence", ""),
                        f"{obj.get('pixel_x', 0.0):.1f}",
                        f"{obj.get('pixel_y', 0.0):.1f}",
                    ])
            self._log(f"Exported CSV: {self._last_csv_path}")
            QMessageBox.information(
                self, "CSV Exported",
                f"Object table saved:\n{self._last_csv_path}"
            )
        except Exception as e:
            self._log(f"CSV export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export CSV:\n{e}")

    def _on_open_folder(self) -> None:
        path = self._last_html_path or self._last_png_path or self._last_csv_path
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _on_open_html(self) -> None:
        if self._last_html_path and os.path.isfile(self._last_html_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_html_path))

    # ------------------------------------------------------------------
    # WEBENGINE REPAIR (explicit, opt-in)
    # ------------------------------------------------------------------

    def _show_webengine_repair_dialog(self) -> None:
        """Open the opt-in WebEngine repair dialog.

        Only called when the user clicks the in-pane banner button; we
        never trigger this automatically. If the dialog reports a
        successful repair on exit we refresh the preview pane so the
        next render uses the embedded WebEngine view.
        """
        dlg = WebEngineRepairDialog(self)
        dlg.exec()
        if dlg.repaired:
            self._log("PyQt6-WebEngine repaired successfully.")
            self.preview_widget.refresh_webengine_state()
        elif WEBENGINE_ERROR:
            self._log(f"WebEngine still unavailable: {WEBENGINE_ERROR}")

    # ------------------------------------------------------------------
    # COFFEE DIALOG (matches AnnotateImage styling)
    # ------------------------------------------------------------------

    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"
        dlg = QDialog(self)
        dlg.setWindowTitle("\u2615 Support Svenesis CosmicDepth 3D")
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
            "<b style='color:#e0e0e0;'>Enjoying Svenesis CosmicDepth 3D?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If CosmicDepth 3D helped you see your images in a new dimension \u2014 "
            "consider buying me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>\u2615 Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br><br>"
            "<span style='color:#aaaaaa;'>Your support helps maintain:</span><br>"
            "\u2022 Svenesis CosmicDepth 3D \u2022 Svenesis Annotate Image<br>"
            "\u2022 Svenesis Gradient Analyzer \u2022 Svenesis Image Advisor<br>"
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
        dlg.setWindowTitle("Svenesis CosmicDepth 3D \u2014 Help")
        dlg.setMinimumSize(800, 600)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}"
        )
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()

        # --- Getting Started ---
        tab1 = QTextEdit()
        tab1.setReadOnly(True)
        tab1.setHtml(
            "<h2 style='color:#88aaff;'>Getting Started</h2>"
            "<p><b>What does CosmicDepth 3D do?</b></p>"
            "<p>This script takes every catalogued astronomical object in "
            "your plate-solved image, resolves their distances from SIMBAD, "
            "and renders them as a rotatable 3D map. The image itself floats "
            "as a flat \u201cwindow\u201d at the front of the scene; each "
            "object sits at its actual distance behind that window, along a "
            "stick extending from its exact image pixel \u2014 so a "
            "foreground nebula at 1,344 ly and a galaxy at 30 million ly "
            "finally look like what they are.</p>"
            "<hr>"
            "<p><b>Requirements:</b></p>"
            "<ul>"
            "<li><b>Plate-solved image:</b> Your image must have a WCS "
            "(World Coordinate System) solution in its FITS header. "
            "In Siril: <i>Tools \u2192 Astrometry \u2192 "
            "Image Plate Solver</i>.</li>"
            "<li><b>Internet connection:</b> The script queries SIMBAD "
            "online for catalog data and distances. After the first run, "
            "distances are cached locally for offline re-use.</li>"
            "<li>The script checks for plate-solve status automatically and "
            "warns if the WCS is missing.</li>"
            "</ul>"
            "<hr>"
            "<p><b>Quick Start:</b></p>"
            "<ol>"
            "<li>Load a plate-solved image in Siril</li>"
            "<li>Run this script</li>"
            "<li>Select which <b>object types</b> to include (left panel "
            "checkboxes)</li>"
            "<li>Choose <b>scaling</b> (Log / Linear / Hybrid) and "
            "<b>view range</b> (Galactic / Cosmic)</li>"
            "<li>Click <b>Render 3D Map</b> (or press <b>F5</b>)</li>"
            "<li>Drag the scene to rotate, scroll to zoom, hover markers "
            "for details</li>"
            "<li>Use the export buttons for HTML (interactive), PNG or CSV</li>"
            "</ol>"
            "<hr>"
            "<p><b>How it works:</b></p>"
            "<p>A plate-solved image provides a pixel\u2194sky mapping (WCS). "
            "The script uses this to:</p>"
            "<ul>"
            "<li>Compute the field-of-view centre and radius, then query "
            "<b>SIMBAD</b> (tiled in parallel for wide fields) for every "
            "catalogued object inside the frame.</li>"
            "<li>Resolve each object's distance through a priority chain: "
            "<b>local cache \u2192 SIMBAD mesDistance \u2192 redshift+Hubble "
            "\u2192 type-median fallback</b>.</li>"
            "<li>Place each object at its exact image pixel (Y, Z) and its "
            "scaled distance (X) \u2014 so the 3D map lines up perfectly "
            "with the flat image plane.</li>"
            "</ul>"
            "<hr>"
            "<p><b>Color Coding:</b></p>"
            "<table cellpadding='4'>"
            "<tr><td style='color:#FFD700;'>\u2588\u2588</td><td>Galaxies</td>"
            "<td style='color:#FF4444;'>\u2588\u2588</td>"
            "<td>Emission Nebulae</td></tr>"
            "<tr><td style='color:#44FF44;'>\u2588\u2588</td>"
            "<td>Planetary Nebulae</td>"
            "<td style='color:#44AAFF;'>\u2588\u2588</td>"
            "<td>Open Clusters</td></tr>"
            "<tr><td style='color:#FF8800;'>\u2588\u2588</td>"
            "<td>Globular Clusters</td>"
            "<td style='color:#FF44FF;'>\u2588\u2588</td>"
            "<td>Supernova Remnants</td></tr>"
            "<tr><td style='color:#888888;'>\u2588\u2588</td>"
            "<td>Dark Nebulae</td>"
            "<td style='color:#FFFFFF;'>\u2588\u2588</td><td>Named Stars</td></tr>"
            "<tr><td style='color:#FF6666;'>\u2588\u2588</td><td>HII Regions</td>"
            "<td style='color:#FF8888;'>\u2588\u2588</td>"
            "<td>Reflection Nebulae</td></tr>"
            "<tr><td style='color:#AADDFF;'>\u2588\u2588</td><td>Asterisms</td>"
            "<td style='color:#DDAAFF;'>\u2588\u2588</td><td>Quasars</td></tr>"
            "</table>"
            "<hr>"
            "<p><b>Distance sources (priority):</b></p>"
            "<ol>"
            f"<li>Local JSON cache ({CACHE_TTL_DAYS}-day TTL)</li>"
            "<li>SIMBAD <i>mesDistance</i> table (parallax, photometry, "
            "redshift-independent methods)</li>"
            "<li>Redshift \u2192 Hubble law (for z &lt; 0.5)</li>"
            "<li>Type-based median fallback (clearly marked in the "
            "Objects table and CSV export)</li>"
            "</ol>"
        )
        tabs.addTab(tab1, "Getting Started")

        # --- Object Types ---
        tab2 = QTextEdit()
        tab2.setReadOnly(True)
        tab2.setHtml(
            "<h2 style='color:#88aaff;'>Object Types</h2>"
            "<p>Select which types of astronomical objects to place in the "
            "3D scene using the checkboxes in the left panel. SIMBAD is "
            "always queried for every type \u2014 you control visibility "
            "by object type, not by data source.</p>"
            "<p>Use <b>Select All</b> / <b>Deselect All</b> for quick "
            "toggling.</p>"
            "<hr>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr style='background:#2a2a2a'>"
            "<td colspan='2'><b style='color:#88aaff'>Common Types</b></td></tr>"
            "<tr><td style='color:#FFD700;font-weight:bold;width:170px'>"
            "Galaxies</td>"
            "<td>Spiral, elliptical, irregular galaxies, galaxy clusters "
            "(Abell, Hickson) and groups. Usually the dominant depth "
            "contributor in deep-sky fields.</td></tr>"
            "<tr><td style='color:#FF4444;font-weight:bold'>Emission Nebulae</td>"
            "<td>Bright ionized gas clouds. Orion, Lagoon, Eagle, Rosette, "
            "Carina, etc.</td></tr>"
            "<tr><td style='color:#44FF44;font-weight:bold'>Planetary Nebulae</td>"
            "<td>Dying-star shells. Ring (M57), Dumbbell (M27), Helix, Owl, "
            "Cat's Eye, Ghost of Jupiter, etc.</td></tr>"
            "<tr><td style='color:#44AAFF;font-weight:bold'>Open Clusters</td>"
            "<td>Young star groups, typically within a few thousand ly. "
            "Pleiades (M45), Double Cluster, Wild Duck, Beehive, Jewel Box.</td></tr>"
            "<tr><td style='color:#FF8800;font-weight:bold'>Globular Clusters</td>"
            "<td>Ancient dense star balls in the Milky Way halo. "
            "M13, M3, Omega Centauri, 47 Tucanae, M22, etc.</td></tr>"
            "<tr><td style='color:#FFFFFF;font-weight:bold'>Named Stars</td>"
            "<td>Bright stars from the Yale BSC and SIMBAD HD stars. "
            "Filtered by the magnitude limit. Typical distances: tens to "
            "thousands of ly.</td></tr>"
            "<tr style='background:#2a2a2a'>"
            "<td colspan='2'><b style='color:#88aaff'>Specialized Types</b></td></tr>"
            "<tr><td style='color:#FF8888;font-weight:bold'>Reflection Nebulae</td>"
            "<td>Dust clouds illuminated by nearby stars. M78, Witch Head, "
            "Iris, vdB catalog, etc.</td></tr>"
            "<tr><td style='color:#FF44FF;font-weight:bold'>Supernova Remnants</td>"
            "<td>Expanding explosion debris. Crab (M1), Veil Nebula, "
            "Simeis 147, Pencil Nebula, etc.</td></tr>"
            "<tr><td style='color:#888888;font-weight:bold'>Dark Nebulae</td>"
            "<td>Opaque dust clouds, typically Milky-Way foreground. "
            "Horsehead (B33), Pipe (B78), Snake (B72), Coalsack. "
            "<b>Not filtered by magnitude.</b></td></tr>"
            "<tr><td style='color:#FF6666;font-weight:bold'>HII Regions</td>"
            "<td>Large ionized-hydrogen complexes (Sharpless). "
            "Heart, Soul, Barnard's Loop. Best for wide-field "
            "Milky Way images.</td></tr>"
            "<tr><td style='color:#AADDFF;font-weight:bold'>Asterisms</td>"
            "<td>Chance star patterns, not true clusters. Coathanger, "
            "Kemble's Cascade, etc.</td></tr>"
            "<tr><td style='color:#DDAAFF;font-weight:bold'>Quasars</td>"
            "<td>Extremely distant active galactic nuclei \u2014 "
            "often the deepest markers in the scene, reaching billions "
            "of light-years.</td></tr>"
            "</table>"
            "<hr>"
            "<p><b>Magnitude Limit:</b> Only objects brighter than this "
            "value are included. 14.0 is a good default for deep-sky "
            "frames. Dark nebulae bypass this filter since they have no "
            "standard magnitude. Raise to 20.0 to see every catalogued "
            "object regardless of brightness.</p>"
        )
        tabs.addTab(tab2, "Object Types")

        # --- Scaling & Display ---
        tab3 = QTextEdit()
        tab3.setReadOnly(True)
        tab3.setHtml(
            "<h2 style='color:#88aaff;'>Scaling Modes</h2>"
            "<p>Astrophotos mix objects across nine orders of magnitude in "
            "distance. A pure linear plot collapses the entire Milky Way "
            "into a point next to a distant galaxy. CosmicDepth offers "
            "three scaling modes:</p>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='width:140px'><b>Logarithmic</b></td>"
            "<td>Recommended for most fields. The X axis is placed on a "
            "<b>log-typed axis in real light-years</b> (tick labels show "
            "1\u202Fly, 10\u202Fly, 100\u202Fly, 1\u202Fkly, &hellip;, "
            "10\u202FGly) so near and distant objects are both legible. "
            "Matplotlib PNG exports show the same data as "
            "<code>log\u2081\u2080(ly)</code>.</td></tr>"
            "<tr><td><b>Linear</b></td>"
            "<td>True proportional distances in light-years. Useful for "
            "star-only fields inside the Milky Way \u2014 galaxies "
            "disappear to the horizon.</td></tr>"
            "<tr><td><b>Hybrid</b></td>"
            "<td>Compressed axis: linear up to 10,000\u202Fly, log beyond. "
            "Keeps realistic spacing in the solar neighbourhood while "
            "still showing extragalactic context. Axis units are "
            "compressed (not raw ly).</td></tr>"
            "</table>"
            "<hr>"
            "<h3>View Ranges</h3>"
            "<table cellpadding='4' style='width:100%'>"
            "<tr><td style='width:140px'><b>Cosmic</b></td>"
            "<td>Everything, including galaxies and quasars out to billions "
            "of light-years.</td></tr>"
            "<tr><td><b>Galactic</b></td>"
            "<td>Only objects closer than 100,000 ly \u2014 i.e. inside "
            "the Milky Way.</td></tr>"
            "</table>"
            "<hr>"
            "<h3>Display Checkboxes</h3>"
            "<table cellpadding='4' style='width:100%'>"
            "<tr><td style='width:160px'><b>Color by type</b></td>"
            "<td>Use different colors per object category (see color "
            "table). When off, all markers are drawn uniform grey.</td></tr>"
            "<tr><td><b>Show image as sky plane</b></td>"
            "<td>Renders your plate-solved image as a flat rectangular "
            "\u201cwindow\u201d at the front of the scene, with depth "
            "sticks from each marker pointing back to its exact pixel. "
            "Disable for a purely abstract 3D map.</td></tr>"
            "</table>"
            "<hr>"
            "<h3>The Distance Cache</h3>"
            "<p>Every successful SIMBAD / NED lookup is cached on disk at "
            f"<code>{CACHE_PATH}</code>. Entries older than "
            f"{CACHE_TTL_DAYS} days are refreshed automatically. Use "
            "<b>Clear Distance Cache</b> to force a full re-query "
            "(useful after SIMBAD updates or catalog corrections).</p>"
        )
        tabs.addTab(tab3, "Scaling & Display")

        # --- Exports & Performance ---
        _webengine_status = (
            "yes \u2014 interactive view embedded in this window"
            if HAS_WEBENGINE
            else "no \u2014 falling back to static PNG + browser"
        )
        _plotly_status = (
            "yes" if HAS_PLOTLY else "no \u2014 matplotlib only"
        )
        tab4 = QTextEdit()
        tab4.setReadOnly(True)
        tab4.setHtml(
            "<h2 style='color:#88aaff;'>Exports</h2>"
            "<table cellpadding='4' style='width:100%'>"
            "<tr><td style='width:80px'><b>HTML</b></td>"
            "<td>Standalone, fully interactive Plotly scene. Open in any "
            "browser; share like a regular web page.</td></tr>"
            "<tr><td><b>PNG</b></td>"
            "<td>Static snapshot via matplotlib (respects the DPI "
            "setting).</td></tr>"
            "<tr><td><b>CSV</b></td>"
            "<td>Full object table including name, type, coordinates, "
            "magnitude, distance, uncertainty, source, confidence and "
            "image pixel coordinates.</td></tr>"
            "</table>"
            "<p>All exports are written to Siril's working directory with "
            "a timestamp appended to the base filename (e.g. "
            "<i>cosmic_depth_3d_20260418_225126.html</i>).</p>"
            "<hr>"
            "<h3>Interpreting the Plot</h3>"
            "<ul>"
            "<li>The viewer looks along the depth (X) axis; Y and Z match "
            "the image's pixel coordinates, so markers land on their "
            "exact object in the sky plane.</li>"
            "<li>Marker color follows catalog type (same palette as "
            "Svenesis Annotate Image).</li>"
            "<li>Marker size reflects apparent magnitude "
            "(brighter \u2192 larger).</li>"
            "<li>Depth sticks connect each marker to its position on the "
            "image plane, like push-pins through a window.</li>"
            "<li>Hover for distance, uncertainty, and source.</li>"
            "<li>Objects using the type-median fallback are explicitly "
            "labelled <i>Type median</i> in the Objects tab and CSV "
            "export.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Performance</h3>"
            "<p>SIMBAD queries are tiled and run <b>in parallel</b> "
            "(up to 8 concurrent tile queries), so even wide-field "
            "mosaics typically resolve in 5\u201310 seconds.</p>"
            "<p>Successful distance lookups are cached on disk, so a "
            "second render of the same field is near-instant.</p>"
            "<p>The embedded 3D view uses a cached copy of "
            "<code>plotly.min.js</code> in your temp directory so each "
            "render reloads only the (small) scene data, not the "
            "\u223c3.5\u202fMB Plotly bundle.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Known Limitations</h3>"
            "<ul>"
            "<li><b>SIMBAD coverage:</b> about 30% of objects have no "
            "catalogued distance \u2014 these use the type-median "
            "fallback.</li>"
            "<li><b>Nebula distances:</b> diffuse clouds have large "
            "intrinsic uncertainties (often &gt;50%).</li>"
            "<li><b>Wide-field mosaics:</b> dense fields can hit the "
            "3000-row limit per SIMBAD tile.</li>"
            "<li><b>No live 2D link-back:</b> sirilpy cannot highlight "
            "pixels in Siril's main viewport from an external script "
            "\u2014 use the CSV export for round-tripping pixel "
            "coordinates.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Rendering Backend</h3>"
            f"<p><b>WebEngine available:</b> {_webengine_status}.<br>"
            f"<b>Plotly available:</b> {_plotly_status}.</p>"
            "<p>For the interactive in-window scene, "
            "<code>PyQt6-WebEngine</code> and <code>plotly</code> must be "
            "installed into Siril's Python environment (the script "
            "auto-installs them on first run and pins the WebEngine "
            "version to match your PyQt6 ABI).</p>"
        )
        tabs.addTab(tab4, "Exports & Performance")

        layout.addWidget(tabs)
        lbl_guide = QLabel(
            '<span style="font-size:10pt;">\U0001F4D6 '
            '<a href="https://github.com/sramuschkat/Siril-Scripts/blob/main/'
            'Instructions/Svenesis-CosmicDepth3D-Instructions.md"'
            ' style="color:#88aaff;">Full User Guide (online)</a></span>'
        )
        lbl_guide.setOpenExternalLinks(True)
        layout.addWidget(lbl_guide)
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
        win = CosmicDepth3DWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis CosmicDepth 3D v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
            pass
        return app.exec()
    except NoImageError:
        QMessageBox.warning(
            None, "No Image",
            "No image is currently loaded in Siril. Please load an image first."
        )
        return 1
    except Exception as e:
        QMessageBox.critical(
            None, "Svenesis CosmicDepth 3D Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
