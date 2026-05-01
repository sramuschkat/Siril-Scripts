"""
Svenesis GalacticView 3D
Script Version: 0.9.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script reads the current plate-solved image from Siril, identifies the
main astronomical object via SIMBAD, and renders the Milky Way as an
interactive 3D model -- with Earth physically positioned in the Orion Arm
and the astrophoto itself placed as a textured rectangle pointing in the
exact viewing direction in space.

GalacticView 3D makes spatial orientation visible:
  "Your photo is not just anywhere. It is a window into one specific
   direction of the universe -- and now you can see where."

Two modes, automatically selected from object distance and type:
- Galactic (< 150.000 ly): 1 unit = 1.000 ly, where inside the Milky Way am I looking?
- Cosmic   (>= 150.000 ly): 1 unit = 100.000 ly, embedded neighbor galaxies,
  with compressed log scaling beyond 1 Mly.

Data sources:
- SIMBAD: main-object distance + type (TAP queries)
- Local JSON cache (~/.config/siril/svenesis_galacticview_cache.json, 90-day TTL)
- Redshift -> Hubble (H0 = 70 km/s/Mpc) for distant galaxies
- Type-based median fallback (clearly marked as estimate)

Features:
- Plate-solved image ingestion (same 6-strategy WCS detection as CosmicDepth 3D)
- Main-object identification from OBJECT keyword / embedded catalog / cone search
- Distance resolution: cache -> SIMBAD -> redshift -> type-median
- Full Milky Way scene: 5 spiral arms, galactic disk stars, galactic center,
  Earth in the Orion Arm, optional neighbor-galaxy overlay (cosmic mode)
- Photo rectangle from four WCS corners, textured with auto-stretched FITS
- Viewing ray from Earth to the photo center
- Interactive 3D rendering via Plotly embedded in QWebEngineView
  (falls back to matplotlib 3D if PyQt6-WebEngine is not available)
- Export as HTML (interactive, standalone), PNG, and CSV coordinate table
- Dark-themed PyQt6 GUI matching the Svenesis look & feel
- Persistent settings via QSettings

Run from Siril via Processing -> Scripts. Place this file inside a folder
named Utility in one of Siril's Script Storage Directories.

(c) 2025-2026
SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Svenesis GalacticView 3D
# Script Version: 0.9.0
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: processing
# Script Description: Reads the main object from a plate-solved image and
#   renders the Milky Way as an interactive 3D star-map with Earth in the
#   Orion Arm and the astrophoto placed in the exact viewing direction.
#   Requires a plate-solved image and an internet connection (or a
#   populated local distance cache).
# Script Author: Sven Ramuschkat

CHANGELOG:
1.0.0 - Initial release
      - Plate-solved image ingestion via sirilpy
      - WCS -> galactic coordinates (l, b) via astropy
      - Main-object identification via SIMBAD / OBJECT keyword / cone search
      - Distance resolution: cache -> SIMBAD -> redshift -> type-median
      - Full Milky Way scene: spiral arms, disk, galactic center, Earth
      - Photo rectangle from WCS corners, auto-stretched FITS texture
      - Automatic Galactic / Cosmic mode selection with manual override
      - Neighbor galaxies in cosmic mode
      - Plotly 3D renderer (QWebEngineView) with matplotlib fallback
      - HTML / PNG / CSV export
      - Dark-themed PyQt6 GUI with persistent settings
"""
from __future__ import annotations

import sys
import os
import re
import gc
import io
import json
import math
import base64
import datetime
import threading
import traceback
import warnings

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
                   "plotly", "Pillow", "kaleido")

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
    QLineEdit, QFileDialog, QGridLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QShortcut, QKeySequence, QDesktopServices, QImageReader,
    QPainter, QColor, QPen, QBrush, QRadialGradient,
)

QImageReader.setAllocationLimit(0)


WEBENGINE_ERROR = ""
QWebEngineView = None


def _try_import_webengine() -> bool:
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
    import sysconfig
    for key in ("stdlib", "purelib", "platlib"):
        try:
            p = sysconfig.get_path(key)
        except Exception:
            p = None
        if p and os.path.isfile(os.path.join(p, "EXTERNALLY-MANAGED")):
            return True
    return False


def _pyqt6_minor_version() -> str | None:
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR
        parts = PYQT_VERSION_STR.split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else PYQT_VERSION_STR
    except Exception:
        return None


def _installed_webengine_minor() -> str | None:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except Exception:
        return None
    try:
        v = version("PyQt6-WebEngine")
    except PackageNotFoundError:
        return None
    except Exception:
        return None
    parts = v.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else v


def diagnose_webengine_state() -> dict:
    if HAS_WEBENGINE:
        return {"kind": "ok", "pyqt_minor": _pyqt6_minor_version(),
                "webengine_minor": _installed_webengine_minor(),
                "message": "WebEngine loaded."}
    pyqt_minor = _pyqt6_minor_version()
    we_minor = _installed_webengine_minor()
    err = WEBENGINE_ERROR or ""
    if we_minor is None:
        return {
            "kind": "missing", "pyqt_minor": pyqt_minor,
            "webengine_minor": None,
            "message": ("PyQt6-WebEngine is not installed. "
                        "Click 'Install WebEngine' to fetch the matching wheel."),
        }
    if "_qt_version_tag" in err or (
            pyqt_minor and we_minor and pyqt_minor != we_minor):
        return {
            "kind": "abi_skew", "pyqt_minor": pyqt_minor,
            "webengine_minor": we_minor,
            "message": (
                f"ABI mismatch: Siril's bundled PyQt6 is "
                f"{pyqt_minor or '?'} but PyQt6-WebEngine is "
                f"{we_minor or '?'}. A pinned reinstall aligns the versions."),
        }
    return {
        "kind": "unknown_failure", "pyqt_minor": pyqt_minor,
        "webengine_minor": we_minor,
        "message": ("PyQt6-WebEngine is installed but failed to load. "
                    "A reinstall pinned to your PyQt6 version usually fixes it."),
    }

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from astropy.wcs import WCS
from astropy.io import fits as astropy_fits
from astropy.coordinates import SkyCoord, Angle
import astropy.units as u

# Cosmology helpers used in cosmic mode.  Optional: if astropy's
# cosmology subpackage is unavailable (very minimal install) the
# code falls back to a low-z linear approximation.
try:
    from astropy.cosmology import Planck18 as _COSMO
    from astropy.cosmology import z_at_value as _Z_AT_VALUE
    _HAS_COSMOLOGY = True
except Exception:
    _COSMO = None
    _Z_AT_VALUE = None
    _HAS_COSMOLOGY = False


# P4.12 — Distance-metric toggle for cosmic mode.
#
# At z > 0.05 the choice of distance metric matters significantly:
#   * "light-travel"     — c × lookback_time(z).  How far the light
#                          travelled to reach us.  Default; what
#                          SIMBAD's redshift→distance conversion
#                          produces for non-radial Hubble flow.
#   * "comoving"         — proper distance NOW, accounting for
#                          cosmic expansion since the light left.
#                          Always ≥ light-travel.
#   * "angular-diameter" — comoving / (1+z).  Smaller than comoving
#                          for high z; this is the distance that
#                          determines apparent angular size, so it's
#                          the right metric for "how big does this
#                          object appear in my photo?".
#
# We keep the canonical light-year values as light-travel everywhere
# in the pipeline.  When `_ACTIVE_DISTANCE_METRIC` is set to one of
# the other two, `scale_dist` converts on the fly before scaling to
# scene units — so the 3D scene physically reorganises when the user
# toggles.
#
# Galactic mode (sub-Mly) is unaffected: the three metrics are
# identical for low z.
_ACTIVE_DISTANCE_METRIC = "light-travel"


def convert_distance_for_metric(dist_ly: float, metric: str) -> float:
    """Convert a light-travel distance (ly) to ``metric``.

    Falls back to the input value if astropy.cosmology isn't available
    or z is too small for the conversion to matter.  Approximations
    for low z ensure this never blows up.
    """
    if (dist_ly is None or dist_ly <= 0
            or not (dist_ly == dist_ly)
            or metric == "light-travel"):
        return dist_ly
    # Threshold: below ~10 Mly (z ≈ 0.0007) the three metrics agree
    # within sub-percent, so skip the round-trip.
    if dist_ly < 1e7:
        return dist_ly
    z, _ = estimate_z_and_lookback(dist_ly)
    if z <= 0.0:
        return dist_ly
    if not _HAS_COSMOLOGY:
        # Linear-z fallback: comoving ≈ light-travel * (1+z).
        if metric == "comoving":
            return dist_ly * (1.0 + z)
        if metric == "angular-diameter":
            return dist_ly / (1.0 + z)
        return dist_ly
    try:
        if metric == "comoving":
            d_mpc = float(_COSMO.comoving_distance(z).to(u.Mpc).value)
            return d_mpc * 3.262e6   # Mpc → ly
        if metric == "angular-diameter":
            d_mpc = float(
                _COSMO.angular_diameter_distance(z).to(u.Mpc).value)
            return d_mpc * 3.262e6
    except Exception:
        # On numeric failure, return input — better than crashing.
        return dist_ly
    return dist_ly


def estimate_z_and_lookback(dist_ly: float
                             ) -> tuple[float, float]:
    """Return ``(redshift, lookback_gyr)`` for a light-travel distance
    in light-years.

    Light-travel distance equals lookback time × c, so
    ``lookback_gyr = dist_ly / 1e9`` exactly.  The redshift then comes
    from inverting the cosmological lookback-time integral; that's
    where Planck18 is used.  For very low z (≤ 0.01, ≈ 140 Mly) the
    integral collapses to the Hubble-flow linear relation
    ``z ≈ H0·d/c`` with ``H0 ≈ 67.4 km/s/Mpc, 1 Mpc ≈ 3.262e6 ly``,
    which is accurate enough for a hover label.
    """
    if dist_ly is None or dist_ly <= 0 or not (dist_ly == dist_ly):
        return (0.0, 0.0)
    lookback_gyr = float(dist_ly) / 1e9
    # Linear approximation: z ≈ d / (c / H0).  c/H0 in ly:
    #   c/H0 ≈ 3e5 km/s / 67.4 km/s/Mpc ≈ 4451 Mpc ≈ 1.452e10 ly.
    z_linear = float(dist_ly) / 1.452e10
    if not _HAS_COSMOLOGY or lookback_gyr < 0.01:
        return (z_linear, lookback_gyr)
    try:
        z = float(_Z_AT_VALUE(_COSMO.lookback_time,
                              lookback_gyr * u.Gyr))
        return (z, lookback_gyr)
    except Exception:
        return (z_linear, lookback_gyr)
from astroquery.simbad import Simbad

# astroquery emits NoResultsWarning / deprecation chatter on normal empty
# results and renamed votable fields — we log our own outcomes, so silence
# the duplicate noise.
try:
    from astroquery.exceptions import NoResultsWarning as _NoResultsWarning
    warnings.filterwarnings("ignore", category=_NoResultsWarning)
except Exception:
    pass
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="astroquery.*")

try:
    from PIL import Image
    HAS_PIL = True
    # Pillow ≥10 removed the top-level resampling constants (Image.LANCZOS
    # etc.) — they live on Image.Resampling now.  Resolve once so downstream
    # callers don't crash on modern installs.
    _PIL_LANCZOS = getattr(
        getattr(Image, "Resampling", Image), "LANCZOS", 1)
except Exception:
    HAS_PIL = False
    _PIL_LANCZOS = 1  # numeric fallback (Pillow uses 1 for LANCZOS)

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "0.9.0"
SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "GalacticView3D"
LEFT_PANEL_WIDTH = 360

# Cache
CACHE_DIR = os.path.expanduser("~/.config/siril")
CACHE_PATH = os.path.join(CACHE_DIR, "svenesis_galacticview_cache.json")
CACHE_TTL_DAYS = 90
CACHE_VERSION = 1

# Distance conversions
PC_TO_LY = 3.26156
KPC_TO_LY = PC_TO_LY * 1000.0
MPC_TO_LY = PC_TO_LY * 1_000_000.0
GPC_TO_LY = PC_TO_LY * 1_000_000_000.0
C_KM_S = 299_792.458
HUBBLE_H0 = 70.0

# Milky Way astronomical constants (distances in light-years)
EARTH_TO_GC_LY = 26_000          # Earth -> Sgr A*
GALAXY_RADIUS_LY = 50_000        # MW radius
GALAXY_THICK_LY = 3_000          # disk half-thickness
GALACTIC_THRESHOLD_LY = 150_000  # switch mode above this distance

# Backward-compat aliases (legacy "lj" naming — German "Lichtjahr" —
# kept so external callers / pickled dumps don't break).  Internal
# code uses the new *_LY names.
EARTH_TO_GC_LJ = EARTH_TO_GC_LY
GALAXY_RADIUS_LJ = GALAXY_RADIUS_LY
GALAXY_THICK_LJ = GALAXY_THICK_LY
GALACTIC_THRESHOLD_LJ = GALACTIC_THRESHOLD_LY

# ---- Scene / navigation tuning ------------------------------------------
# Camera dolly limits applied in the Plotly navigation-pad JS (_JS_CAMERA).
# The values are the radial eye distance in Plotly scene units.
NAV_EYE_MIN = 0.35               # closest zoom-in
NAV_EYE_MAX = 40.0                # farthest zoom-out

# Log-distance window (in decades) used by build_background_pins() to
# keep "nearby" pins only.  Galactic mode is narrower, cosmic wider.
LOG_WINDOW_GALACTIC = 0.5        # picked … picked × ~3.16
LOG_WINDOW_COSMIC = 1.0          # picked … picked × 10

# Photo texture resolution (longest edge, px) — user-overridable from the
# Scene Elements panel; this is the default fallback.
PHOTO_DEFAULT_PX = 480

# SIMBAD tile timeout (seconds) for the per-future guard in
# collect_simbad_candidates().
SIMBAD_TILE_TIMEOUT_S = 30.0

_RE_WHITESPACE = re.compile(r'\s+')


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------
from enum import Enum


class ViewMode(str, Enum):
    GALACTIC = "galactic"
    COSMIC = "cosmic"

    @classmethod
    def parse(cls, value, default=None):
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except Exception:
            return default if default is not None else cls.GALACTIC


# ---------------------------------------------------------------------------
# SIMBAD type classification
# ---------------------------------------------------------------------------
COSMIC_TYPES = {
    "Galaxy", "GinPair", "GinGroup", "GinCl", "ClG", "PartofG",
    "Seyfert", "Seyfert_1", "Seyfert_2", "QSO", "AGN", "Quasar",
    "LINER", "G", "GiG", "GiP", "IG", "PaG", "SBG", "SyG", "Sy1",
    "Sy2", "GrG", "CGG", "EmG", "H2G", "bCG", "LSB",
}
GALACTIC_TYPES = {
    "HII", "SNR", "PN", "OpC", "GlC", "DkNeb", "RNe", "Neb",
    "EmObj", "Star", "Assoc*", "SFR", "MolCld", "Cl*", "As*",
    "**", "*", "V*", "PM*", "HB*", "C*", "S*", "LP*", "Mi*",
    "ISM", "EmO", "DNe", "dNe", "MoC",
}

TYPE_DISTANCE_MEDIANS = {
    "HII":    {"dist_ly":     2_000, "spread_ly":  1_500},
    "SNR":    {"dist_ly":     5_000, "spread_ly":  4_000},
    "PN":     {"dist_ly":     3_500, "spread_ly":  3_000},
    "RNe":    {"dist_ly":     1_500, "spread_ly":  1_000},
    "OpC":    {"dist_ly":     2_500, "spread_ly":  2_000},
    "Cl*":    {"dist_ly":     2_500, "spread_ly":  2_000},
    "GlC":    {"dist_ly":    40_000, "spread_ly": 30_000},
    "Galaxy": {"dist_ly": 5_000_000, "spread_ly": 4_000_000},
    "G":      {"dist_ly": 5_000_000, "spread_ly": 4_000_000},
    "Star":   {"dist_ly":       500, "spread_ly":    400},
    "*":      {"dist_ly":       500, "spread_ly":    400},
    "DkNeb":  {"dist_ly":     1_500, "spread_ly":  1_000},
    "Assoc*": {"dist_ly":     3_000, "spread_ly":  2_000},
    "As*":    {"dist_ly":     3_000, "spread_ly":  2_000},
    "Neb":    {"dist_ly":     2_000, "spread_ly":  1_500},
    "EmObj":  {"dist_ly":     2_000, "spread_ly":  1_500},
    "QSO":    {"dist_ly": 2_000_000_000, "spread_ly": 1_500_000_000},
}

OBJECT_TYPE_LABELS = {
    "HII": "HII Region (Emission Nebula)",
    "SNR": "Supernova Remnant",
    "PN": "Planetary Nebula",
    "RNe": "Reflection Nebula",
    "OpC": "Open Cluster",
    "Cl*": "Open Cluster",
    "GlC": "Globular Cluster",
    "Galaxy": "Galaxy",
    "G": "Galaxy",
    "GiG": "Galaxy in Group",
    "GiP": "Galaxy in Pair",
    "GinCl": "Galaxy in Cluster",
    "Star": "Named Star",
    "*": "Star",
    "DkNeb": "Dark Nebula",
    "Assoc*": "Stellar Association",
    "As*": "Asterism",
    "Neb": "Nebula",
    "EmObj": "Emission Object",
    "QSO": "Quasar",
    "AGN": "Active Galactic Nucleus",
}


# ---------------------------------------------------------------------------
# Milky Way spiral arms (Hou & Han 2014)
# ---------------------------------------------------------------------------
# P4.10 — Curated catalog of well-known galactic landmarks: open
# clusters, globular clusters, prominent nebulae.  Rendered in
# galactic mode behind a legend toggle so users can switch on a
# familiar-sky overlay.  (l, b) in degrees, distance in light-years.
# Distances are best-known approximations; precision to 2 sig figs
# is enough for visual context at galactic scale.
GALACTIC_LANDMARKS = [
    {"name": "Pleiades (M45)",       "l":   166.6, "b": -23.5,
     "dist_ly":     444, "kind": "OpC"},
    {"name": "Hyades",               "l":   180.4, "b": -22.3,
     "dist_ly":     153, "kind": "OpC"},
    {"name": "Beehive (M44)",        "l":   205.5, "b":  32.5,
     "dist_ly":     577, "kind": "OpC"},
    {"name": "Double Cluster",       "l":   135.0, "b":  -3.7,
     "dist_ly":   7_500, "kind": "OpC"},
    {"name": "Orion Nebula (M42)",   "l":   209.0, "b": -19.4,
     "dist_ly":   1_344, "kind": "Neb"},
    {"name": "Crab Nebula (M1)",     "l":   184.6, "b":  -5.8,
     "dist_ly":   6_500, "kind": "SNR"},
    {"name": "Veil Nebula",          "l":    74.5, "b":  -8.6,
     "dist_ly":   2_400, "kind": "SNR"},
    {"name": "Ring Nebula (M57)",    "l":    63.2, "b":  13.8,
     "dist_ly":   2_300, "kind": "PN"},
    {"name": "Dumbbell (M27)",       "l":    60.8, "b":  -3.7,
     "dist_ly":   1_360, "kind": "PN"},
    {"name": "Eagle Nebula (M16)",   "l":    17.0, "b":   0.8,
     "dist_ly":   7_000, "kind": "Neb"},
    {"name": "Lagoon (M8)",          "l":     6.0, "b":  -1.2,
     "dist_ly":   4_100, "kind": "Neb"},
    {"name": "Trifid (M20)",         "l":     7.0, "b":  -0.2,
     "dist_ly":   5_200, "kind": "Neb"},
    {"name": "M13 (Hercules cluster)", "l":  59.0, "b":  40.9,
     "dist_ly":  22_200, "kind": "GlC"},
    {"name": "Omega Centauri",       "l":   309.1, "b":  15.0,
     "dist_ly":  17_300, "kind": "GlC"},
    {"name": "47 Tucanae",           "l":   305.9, "b": -44.9,
     "dist_ly":  13_000, "kind": "GlC"},
    {"name": "M22",                  "l":     9.9, "b":  -7.6,
     "dist_ly":  10_400, "kind": "GlC"},
    {"name": "Carina Nebula",        "l":   287.6, "b":  -0.6,
     "dist_ly":   8_500, "kind": "Neb"},
    {"name": "Helix Nebula",         "l":    36.2, "b": -57.1,
     "dist_ly":     650, "kind": "PN"},
    {"name": "California Nebula",    "l":   161.0, "b":  -8.5,
     "dist_ly":   1_000, "kind": "Neb"},
    {"name": "Rosette Nebula",       "l":   206.3, "b":  -2.1,
     "dist_ly":   5_200, "kind": "Neb"},
]

# Visual styling per object kind, matched to the SIMBAD object
# classes already used elsewhere in the module so the legend reads
# consistently with the rest of the UI.
LANDMARK_STYLE = {
    "OpC": {"color": "#88ccff", "symbol": "circle"},   # open clusters
    "GlC": {"color": "#ffcc88", "symbol": "diamond"},  # globular clusters
    "Neb": {"color": "#ff7799", "symbol": "circle"},   # diffuse nebulae
    "SNR": {"color": "#ff5566", "symbol": "x"},        # supernova remnants
    "PN":  {"color": "#bbaaff", "symbol": "circle-open"},  # planetary
}

SPIRAL_ARMS = [
    {"name": "Norma Arm",        "phi0":  10, "pitch": 12,
     "r0_ly": 12_000, "rmax_ly": 52_000, "col": "#ff5a5a", "is_local": False},
    {"name": "Scutum-Centaurus", "phi0":  82, "pitch": 12,
     "r0_ly": 13_000, "rmax_ly": 50_000, "col": "#ffb347", "is_local": False},
    {"name": "Sagittarius Arm",  "phi0": 154, "pitch": 12,
     "r0_ly": 14_000, "rmax_ly": 48_000, "col": "#4ddb7a", "is_local": False},
    {"name": "Orion Arm (local)", "phi0": 226, "pitch": 12,
     "r0_ly": 15_000, "rmax_ly": 45_000, "col": "#66d9ff", "is_local": True},
    {"name": "Perseus Arm",      "phi0": 298, "pitch": 12,
     "r0_ly": 18_000, "rmax_ly": 52_000, "col": "#c07cff", "is_local": False},
]


# Neighbor galaxies in cosmic mode (l, b, dist_ly, diam_ly, color)
# P2.7 — Curated cosmic landmarks catalog: famous extragalactic
# objects an astrophotographer recognizes by sight.  Plotted as
# labeled markers in cosmic mode, behind a legend toggle so the
# scene stays clean by default.  Distances are best-known values.
COSMIC_LANDMARKS = [
    # --- Local Group / nearby (sub-10 Mly) ---
    {"name": "M31 (Andromeda)",         "l": 121.2, "b": -21.6,
     "dist_ly":   2_537_000, "kind": "Galaxy-spiral"},
    {"name": "M33 (Triangulum)",        "l": 133.6, "b": -31.3,
     "dist_ly":   2_730_000, "kind": "Galaxy-spiral"},
    {"name": "NGC 6822 (Barnard's)",    "l":  25.3, "b": -18.4,
     "dist_ly":   1_630_000, "kind": "Galaxy-dwarf"},
    {"name": "IC 10",                   "l": 119.0, "b":  -3.3,
     "dist_ly":   2_230_000, "kind": "Galaxy-dwarf"},
    # --- Sculptor / M81 / Centaurus groups (~10-15 Mly) ---
    {"name": "NGC 253 (Sculptor)",      "l":  97.4, "b": -87.9,
     "dist_ly":  10_700_000, "kind": "Galaxy-spiral"},
    {"name": "M81 (Bode's)",            "l": 142.1, "b":  40.9,
     "dist_ly":  11_800_000, "kind": "Galaxy-spiral"},
    {"name": "M82 (Cigar)",             "l": 141.4, "b":  40.6,
     "dist_ly":  12_700_000, "kind": "Galaxy-starburst"},
    {"name": "Centaurus A (NGC 5128)",  "l": 309.5, "b":  19.4,
     "dist_ly":  13_700_000, "kind": "Galaxy-AGN"},
    {"name": "M83 (Southern Pinwheel)", "l": 314.6, "b":  31.9,
     "dist_ly":  14_700_000, "kind": "Galaxy-spiral"},
    # --- Mid-distance (~20-50 Mly) ---
    {"name": "M51 (Whirlpool)",         "l": 104.9, "b":  68.6,
     "dist_ly":  23_000_000, "kind": "Galaxy-spiral"},
    {"name": "M101 (Pinwheel)",         "l": 102.0, "b":  59.8,
     "dist_ly":  21_000_000, "kind": "Galaxy-spiral"},
    {"name": "M104 (Sombrero)",         "l": 298.5, "b":  51.2,
     "dist_ly":  29_350_000, "kind": "Galaxy-spiral"},
    {"name": "Leo Triplet (M65/66/3628)", "l":  240.6, "b":  64.4,
     "dist_ly":  35_000_000, "kind": "Galaxy-group"},
    {"name": "Stephan's Quintet",       "l":  93.7, "b": -27.3,
     "dist_ly": 290_000_000, "kind": "Galaxy-group"},
    # --- Famous deep-sky / interacting (50-300 Mly) ---
    {"name": "Cartwheel Galaxy",        "l":  52.4, "b": -76.3,
     "dist_ly": 500_000_000, "kind": "Galaxy-peculiar"},
    {"name": "Hoag's Object",           "l":  29.4, "b":  73.5,
     "dist_ly": 612_000_000, "kind": "Galaxy-peculiar"},
    {"name": "NGC 4319 / Markarian 205", "l": 124.3, "b":  29.3,
     "dist_ly": 350_000_000, "kind": "Galaxy-AGN"},
    {"name": "Markarian's Chain (Virgo)", "l": 282.6, "b":  72.1,
     "dist_ly":  54_000_000, "kind": "Galaxy-group"},
    # --- Very distant landmarks (Gly range) ---
    {"name": "3C 273 (brightest quasar)", "l": 290.0, "b":  64.4,
     "dist_ly": 2_443_000_000, "kind": "Quasar"},
    {"name": "Hubble Ultra-Deep Field", "l": 223.0, "b": -54.4,
     "dist_ly": 13_000_000_000, "kind": "Reference-pointer"},
]

# Visual styling per cosmic-landmark kind.
COSMIC_LANDMARK_STYLE = {
    "Galaxy-spiral":   {"color": "#88ccff", "symbol": "circle"},
    "Galaxy-dwarf":    {"color": "#aaccdd", "symbol": "circle-open"},
    "Galaxy-starburst": {"color": "#ffaa66", "symbol": "circle"},
    "Galaxy-AGN":      {"color": "#ff7799", "symbol": "diamond"},
    "Galaxy-peculiar": {"color": "#ddaaff", "symbol": "diamond"},
    "Galaxy-group":    {"color": "#aaffaa", "symbol": "square"},
    "Quasar":          {"color": "#ffeeaa", "symbol": "x"},
    "Reference-pointer": {"color": "#666666", "symbol": "cross"},
}


# P2.6 — Curated galaxy-cluster catalog for cosmic-mode rendering.
# Each cluster is drawn as a translucent sphere centered on its
# (l, b, distance), with a radius chosen to roughly match its core
# extent.  Communicates large-scale structure: at ~50 Mly+ you're
# in supercluster territory, and the void should show recognizable
# anchor points.
GALAXY_CLUSTERS = [
    {"name": "Virgo Cluster",        "l": 283.8, "b":  74.5,
     "dist_ly":   54_000_000, "extent_ly":  6_000_000,
     "col": "#9090c0",
     "note": "Heart of the Local Supercluster.  Hosts M87, M84, "
             "M86, M58, M59, M60, M89, M90, M91, M98, M99, M100."},
    {"name": "Fornax Cluster",       "l": 236.7, "b": -53.6,
     "dist_ly":   62_000_000, "extent_ly":  3_000_000,
     "col": "#a09070",
     "note": "Second-richest local cluster.  Notable for NGC 1316 "
             "(Fornax A radio source)."},
    {"name": "Centaurus Cluster",    "l": 302.4, "b":  21.6,
     "dist_ly":  170_000_000, "extent_ly":  4_000_000,
     "col": "#c08060",
     "note": "Anchor of the Hydra-Centaurus Supercluster."},
    {"name": "Coma Cluster",         "l":  58.1, "b":  87.96,
     "dist_ly":  321_000_000, "extent_ly":  6_000_000,
     "col": "#9080c0",
     "note": "One of the densest known clusters; ~10,000 galaxies. "
             "Where Fritz Zwicky first inferred dark matter (1933)."},
    {"name": "Perseus Cluster",      "l": 150.6, "b": -13.3,
     "dist_ly":  240_000_000, "extent_ly":  6_000_000,
     "col": "#b07090",
     "note": "Brightest X-ray cluster in the sky; hosts NGC 1275."},
    {"name": "Hercules Cluster",     "l":  31.0, "b":  44.5,
     "dist_ly":  500_000_000, "extent_ly":  4_000_000,
     "col": "#7090c0",
     "note": "Spiral-rich cluster; member of the Hercules "
             "Supercluster.  Many late-type galaxies (unlike Coma)."},
    {"name": "Shapley Supercluster", "l": 311.7, "b":  31.5,
     "dist_ly":  650_000_000, "extent_ly": 50_000_000,
     "col": "#a060a0",
     "note": "Largest known mass concentration in the local "
             "universe.  Contributes to the Great Attractor flow."},
]


NEIGHBOR_GALAXIES = [
    {"name": "Andromeda M31",          "l": 121.2, "b": -21.6,
     "dist_ly":  2_537_000, "diam_ly": 220_000, "col": "#c09060",
     "type": "SAb spiral", "group": "Local Group",
     "note": "Nearest large galaxy.  ~1 trillion stars.  "
             "On a collision course with the Milky Way (~4.5 Gyr)."},
    {"name": "Triangulum M33",         "l": 133.6, "b": -31.3,
     "dist_ly":  2_730_000, "diam_ly":  60_000, "col": "#90a070",
     "type": "SA(s)cd spiral", "group": "Local Group",
     "note": "Third-largest in the Local Group; satellite of M31."},
    {"name": "Large Magellanic Cloud", "l": 280.5, "b": -32.9,
     "dist_ly":    160_000, "diam_ly":  14_000, "col": "#b08050",
     "type": "Irregular dwarf", "group": "Milky Way satellite",
     "note": "Visible to the naked eye from the southern sky."},
    {"name": "Small Magellanic Cloud", "l": 302.8, "b": -44.3,
     "dist_ly":    200_000, "diam_ly":   7_000, "col": "#a07040",
     "type": "Irregular dwarf", "group": "Milky Way satellite",
     "note": "Tidally distorted by interaction with the LMC."},
    {"name": "Bode's Galaxy M81",      "l": 142.1, "b":  40.9,
     "dist_ly": 11_800_000, "diam_ly":  90_000, "col": "#8090c0",
     "type": "SA(s)ab spiral", "group": "M81 Group",
     "note": "Grand-design spiral; interacts gravitationally with M82."},
    {"name": "Cigar Galaxy M82",       "l": 141.4, "b":  40.6,
     "dist_ly": 12_700_000, "diam_ly":  37_000, "col": "#a06080",
     "type": "Starburst irregular", "group": "M81 Group",
     "note": "Intense star-forming region; tidally heated by M81."},
    {"name": "Whirlpool M51",          "l": 104.9, "b":  68.6,
     "dist_ly": 23_000_000, "diam_ly":  76_000, "col": "#7080b0",
     "type": "SA(s)bc spiral + companion",
     "group": "M51 Group",
     "note": "Iconic face-on spiral with NGC 5195 companion."},
    {"name": "Centaurus A",            "l": 309.5, "b":  19.4,
     "dist_ly": 13_700_000, "diam_ly":  97_000, "col": "#c08060",
     "type": "Peculiar S0 (active galactic nucleus)",
     "group": "Centaurus A/M83 Group",
     "note": "Closest powerful AGN; obscured by a dust lane."},
    {"name": "Virgo Cluster",          "l": 283.8, "b":  74.5,
     "dist_ly": 54_000_000, "diam_ly": 8_000_000, "col": "#9090c0",
     "type": "Galaxy cluster (~1300 members)",
     "group": "Virgo Supercluster (anchor)",
     "note": "Centre of our Local Supercluster; M87 hosts a "
             "supermassive black hole imaged by EHT (2019)."},
    {"name": "Sculptor NGC253",        "l":  97.4, "b": -87.9,
     "dist_ly": 10_700_000, "diam_ly":  70_000, "col": "#b09070",
     "type": "SAB(s)c starburst spiral",
     "group": "Sculptor Group",
     "note": "Brightest spiral outside the Local Group; "
             "edge-on dust-lane structure visible in amateur photos."},
]


# ---------------------------------------------------------------------------
# Constellation stick figures (sparse hand-curated set)
# ---------------------------------------------------------------------------
# Line segments between bright Bayer-designation stars, in ICRS J2000
# (RA deg, Dec deg).  Used when the camera is near Earth (galactic mode,
# target within ~1 kly or generic "local" view) to overlay the
# constellation that contains the target — so the scene reads as the
# same sky the astrophotographer is already familiar with.
#
# Not exhaustive: covers the ~dozen brightest / most recognisable
# constellations.  Unknown constellations silently fall through.
#
# Keys match what ``astropy.coordinates.SkyCoord.get_constellation()``
# returns (full IAU English name).
CONSTELLATION_STICKS: dict[str, list[tuple[tuple[float, float],
                                           tuple[float, float]]]] = {
    "Orion": [
        ((88.793,  7.407), (81.283,  6.350)),   # Betelgeuse → Bellatrix
        ((81.283,  6.350), (83.002, -0.299)),   # Bellatrix → Mintaka
        ((83.002, -0.299), (84.053, -1.202)),   # Mintaka → Alnilam
        ((84.053, -1.202), (85.190, -1.943)),   # Alnilam → Alnitak
        ((85.190, -1.943), (86.939, -9.670)),   # Alnitak → Saiph
        ((86.939, -9.670), (78.634, -8.202)),   # Saiph → Rigel
        ((78.634, -8.202), (81.283,  6.350)),   # Rigel → Bellatrix
        ((85.190, -1.943), (88.793,  7.407)),   # Alnitak → Betelgeuse
    ],
    "Ursa Major": [
        ((165.932, 61.751), (165.460, 56.382)),   # Dubhe → Merak
        ((165.460, 56.382), (178.457, 53.695)),   # Merak → Phecda
        ((178.457, 53.695), (183.857, 57.033)),   # Phecda → Megrez
        ((183.857, 57.033), (165.932, 61.751)),   # Megrez → Dubhe
        ((183.857, 57.033), (193.507, 55.960)),   # Megrez → Alioth
        ((193.507, 55.960), (200.981, 54.925)),   # Alioth → Mizar
        ((200.981, 54.925), (206.885, 49.313)),   # Mizar → Alkaid
    ],
    "Cassiopeia": [
        ((2.294,  59.150), (10.127, 56.537)),     # β Caph → α Schedar
        ((10.127, 56.537), (14.177, 60.717)),     # α → γ Navi
        ((14.177, 60.717), (21.454, 60.235)),     # γ → δ Ruchbah
        ((21.454, 60.235), (28.599, 63.670)),     # δ → ε Segin
    ],
    "Cygnus": [
        ((310.358, 45.280), (305.557, 40.257)),   # Deneb → Sadr
        ((305.557, 40.257), (311.553, 33.970)),   # Sadr → Gienah
        ((305.557, 40.257), (296.846, 45.131)),   # Sadr → δ
        ((305.557, 40.257), (292.680, 27.960)),   # Sadr → Albireo
    ],
    "Lyra": [
        ((279.234, 38.784), (281.083, 39.670)),   # Vega → ε
        ((279.234, 38.784), (281.194, 37.605)),   # Vega → ζ
        ((281.194, 37.605), (283.626, 36.899)),   # ζ → δ
        ((281.194, 37.605), (282.520, 33.363)),   # ζ → β Sheliak
        ((282.520, 33.363), (284.736, 32.690)),   # β → γ Sulafat
        ((283.626, 36.899), (284.736, 32.690)),   # δ → γ
    ],
    "Leo": [
        ((152.093, 11.967), (151.829, 16.762)),   # Regulus → η
        ((151.829, 16.762), (154.993, 19.841)),   # η → Algieba
        ((154.993, 19.841), (168.527, 20.524)),   # Algieba → Zosma
        ((168.527, 20.524), (177.265, 14.572)),   # Zosma → Denebola
        ((177.265, 14.572), (168.560, 15.430)),   # Denebola → Chertan
        ((168.560, 15.430), (152.093, 11.967)),   # Chertan → Regulus
        ((154.993, 19.841), (146.462, 23.774)),   # Algieba → ε Ras Elased
    ],
    "Sagittarius": [
        ((271.452, -30.424), (276.043, -34.384)),  # γ → ε
        ((276.043, -34.384), (275.249, -29.828)),  # ε → δ
        ((275.249, -29.828), (276.993, -25.421)),  # δ → λ
        ((276.993, -25.421), (281.409, -26.990)),  # λ → φ
        ((281.409, -26.990), (283.816, -26.297)),  # φ → σ Nunki
        ((283.816, -26.297), (287.441, -29.880)),  # σ → ζ Ascella
        ((287.441, -29.880), (286.740, -27.670)),  # ζ → τ
        ((286.740, -27.670), (281.409, -26.990)),  # τ → φ
    ],
    "Andromeda": [
        ((2.097, 29.091),  (9.832, 30.862)),      # Alpheratz → δ
        ((9.832, 30.862),  (17.433, 35.621)),     # δ → Mirach
        ((17.433, 35.621), (30.975, 42.330)),     # Mirach → Almach
    ],
    "Perseus": [
        ((46.200, 53.506), (51.081, 49.861)),     # γ → Mirphak
        ((51.081, 49.861), (55.731, 47.788)),     # Mirphak → δ
        ((55.731, 47.788), (59.464, 40.011)),     # δ → ε
        ((51.081, 49.861), (47.042, 40.956)),     # Mirphak → Algol
        ((47.042, 40.956), (58.533, 31.883)),     # Algol → ζ
        ((42.674, 55.896), (51.081, 49.861)),     # η → Mirphak
    ],
    "Taurus": [
        ((68.980, 16.509), (67.154, 15.870)),     # Aldebaran → θ
        ((67.154, 15.870), (64.948, 15.628)),     # θ → γ
        ((64.948, 15.628), (60.171, 12.490)),     # γ → λ
        ((64.948, 15.628), (66.709, 17.542)),     # γ → δ
        ((66.709, 17.542), (67.154, 19.180)),     # δ → ε
        ((68.980, 16.509), (81.573, 28.608)),     # Aldebaran → Elnath
        ((68.980, 16.509), (84.411, 21.142)),     # Aldebaran → ζ
    ],
    "Gemini": [
        ((113.650, 31.888), (95.740, 22.514)),    # Castor → μ
        ((95.740, 22.514),  (101.322, 25.131)),   # μ → ε
        ((116.329, 28.026), (110.030, 21.982)),   # Pollux → δ
        ((110.030, 21.982), (106.027, 20.570)),   # δ → ζ
        ((106.027, 20.570), (99.428, 16.399)),    # ζ → γ Alhena
        ((101.322, 25.131), (106.027, 20.570)),   # ε → ζ
    ],
    "Boötes": [
        ((213.915, 19.182), (221.247, 27.074)),   # Arcturus → ε
        ((221.247, 27.074), (221.240, 33.315)),   # ε → δ
        ((221.240, 33.315), (219.116, 38.309)),   # δ → γ
        ((219.116, 38.309), (218.020, 40.391)),   # γ → β
        ((219.116, 38.309), (213.915, 19.182)),   # γ → Arcturus
    ],
}


# ---------------------------------------------------------------------------
# Styling (matches the Svenesis family)
# ---------------------------------------------------------------------------
def _nofocus(w) -> None:
    if w is not None:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# Shared stylesheet for the 3D-view button row (nav pad + presets +
# Spin toggle + export buttons).  Polished dark theme with a proper
# :checked state so the Spin toggle reads clearly as "on".  Applied
# per-widget rather than globally to avoid affecting unrelated
# QPushButtons elsewhere in the app.
NAV_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2f36;
    color: #e6e6e6;
    border: 1px solid #3a3d46;
    border-radius: 5px;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #363a44;
    border-color: #6a8ec8;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #253246;
    border-color: #88aaff;
}
QPushButton:checked {
    background-color: #2a4a6a;
    border-color: #88aaff;
    color: #ffffff;
}
QPushButton:disabled {
    background-color: #1f2025;
    color: #555555;
    border-color: #2a2b30;
}
"""


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


# ---------------------------------------------------------------------------
# Distance / mode helpers
# ---------------------------------------------------------------------------
def _safe_float(val, default: float = float("nan")) -> float:
    try:
        if val is None or val is np.ma.masked:
            return default
        f = float(val)
        return default if np.isnan(f) else f
    except (ValueError, TypeError):
        return default


def to_ly(value: float, unit: str) -> float:
    """Convert a SIMBAD distance value + unit into light-years."""
    unit = (unit or "pc").lower().strip()
    if unit in ("pc", ""):
        return value * PC_TO_LY
    if unit == "kpc":
        return value * KPC_TO_LY
    if unit == "mpc":
        return value * MPC_TO_LY
    if unit == "gpc":
        return value * GPC_TO_LY
    return value * PC_TO_LY


def decide_mode(dist_ly: float | None, obj_type: str) -> ViewMode:
    if obj_type in COSMIC_TYPES:
        return ViewMode.COSMIC
    if obj_type in GALACTIC_TYPES:
        return ViewMode.GALACTIC
    if dist_ly and dist_ly >= GALACTIC_THRESHOLD_LY:
        return ViewMode.COSMIC
    return ViewMode.GALACTIC


# ---------------------------------------------------------------------------
# Galactic-coordinate pipeline
# ---------------------------------------------------------------------------
def radec_to_galactic(ra_deg: float, dec_deg: float) -> tuple[float, float]:
    c = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    return float(c.galactic.l.deg), float(c.galactic.b.deg)


def gal_to_xyz(l_deg: float, b_deg: float, dist_units: float
               ) -> tuple[float, float, float]:
    l_rad = math.radians(l_deg)
    b_rad = math.radians(b_deg)
    return (dist_units * math.cos(b_rad) * math.cos(l_rad),
            dist_units * math.cos(b_rad) * math.sin(l_rad),
            dist_units * math.sin(b_rad))


def scale_dist(dist_ly: float, mode: ViewMode) -> float:
    """Map a distance in light-years to scene units.

    In cosmic mode, honours ``_ACTIVE_DISTANCE_METRIC`` (P4.12) — the
    incoming ``dist_ly`` is interpreted as light-travel distance and
    converted to comoving / angular-diameter as needed before scaling.
    Galactic mode is sub-Mly; the three metrics are identical there
    so the conversion is skipped.
    """
    if mode is ViewMode.GALACTIC:
        return dist_ly / 1_000.0
    # COSMIC — apply metric conversion if active.
    d_eff = convert_distance_for_metric(dist_ly, _ACTIVE_DISTANCE_METRIC)
    if d_eff <= 1_000_000:
        return d_eff / 100_000.0
    # Beyond 1 Mly: 10.0 + dampened log
    return 10.0 + math.log10(d_eff / 1_000_000.0) * 8.0


def _format_ly_label(ly: float) -> str:
    """Human-friendly distance label in ly / kly / Mly / Gly."""
    if ly == 0:
        return "0"
    a = abs(ly)
    sign = "-" if ly < 0 else ""
    if a < 1e3:
        return f"{sign}{a:,.0f} ly"
    if a < 1e6:
        return f"{sign}{a/1e3:g} kly"
    if a < 1e9:
        return f"{sign}{a/1e6:g} Mly"
    return f"{sign}{a/1e9:g} Gly"


def build_axis_ticks(mode: ViewMode
                     ) -> tuple[list[float], list[str]]:
    """Return (tickvals, ticktext) for scene axes in the given mode.

    - GALACTIC mode: linear ticks every 10,000 ly out to ±50,000 ly
      (1 scene unit = 1,000 ly, so tickvals are 10/20/30/...).
    - COSMIC mode: log-distance ticks at decades from 1 kly to 10 Gly
      (both positive and negative), labelled in kly / Mly / Gly. The
      scene mapping already compresses beyond 1 Mly (see
      ``scale_dist``), so these tickvals are evaluated through it.
    """
    if mode is ViewMode.GALACTIC:
        # Linear ticks across several magnitudes so they read the same
        # at the 50,000-ly galaxy view AND the adaptive zoom-box view
        # for nearby targets (which can be only a few thousand ly wide).
        pos_vals_ly = [100, 200, 500,
                       1_000, 2_000, 5_000,
                       10_000, 20_000, 30_000, 40_000, 50_000]
        vals_ly = [-v for v in reversed(pos_vals_ly)] + [0] + pos_vals_ly
        tickvals = []
        for v in vals_ly:
            s = scale_dist(abs(v), mode)
            tickvals.append(-s if v < 0 else s)
        ticktext = [_format_ly_label(v) for v in vals_ly]
        return tickvals, ticktext

    # COSMIC mode — log decades
    decades_ly = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10]
    tickvals: list[float] = []
    ticktext: list[str] = []
    # Negative side (largest magnitude first)
    for v in reversed(decades_ly):
        tickvals.append(-scale_dist(v, mode))
        ticktext.append(_format_ly_label(-v))
    tickvals.append(0.0)
    ticktext.append("0")
    for v in decades_ly:
        tickvals.append(scale_dist(v, mode))
        ticktext.append(_format_ly_label(v))
    return tickvals, ticktext


def which_arm(l_deg: float, b_deg: float, dist_ly: float
              ) -> tuple[str, float] | None:
    """Identify which Milky Way spiral arm a target is closest to.

    Returns ``(arm_name, perpendicular_distance_ly)`` for the closest
    arm centerline, or ``None`` if the target is outside the disk
    (|b| > 5° or distance > 60 kly — beyond meaningful arm membership)
    or if no arms are available.

    Uses galactic mode scene-unit positions internally for consistency
    with how arms are drawn, then converts the centerline distance
    back to light-years for the caller.
    """
    if (dist_ly is None or not (dist_ly == dist_ly)
            or dist_ly <= 0 or dist_ly > 60_000):
        return None
    if abs(b_deg) > 5.0:
        return None  # well above/below the disk plane
    # Target position in galactic-mode scene coords.
    tx, ty, tz = gal_to_xyz(l_deg, b_deg,
                             scale_dist(float(dist_ly), ViewMode.GALACTIC))
    best_name = None
    best_dist_units = float("inf")
    # Sample each arm at high resolution and take the closest segment
    # endpoint.  Plenty accurate for arm-name labeling (sub-kly
    # precision unnecessary).
    for arm in SPIRAL_ARMS:
        pts = arm_scene_points(arm, ViewMode.GALACTIC, n_pts=160)
        xs = pts["x"]
        ys = pts["y"]
        zs = pts["z"]
        for i in range(len(xs)):
            dx = xs[i] - tx
            dy = ys[i] - ty
            dz = zs[i] - tz
            d2 = dx * dx + dy * dy + dz * dz
            if d2 < best_dist_units:
                best_dist_units = d2
                best_name = arm["name"]
    if best_name is None:
        return None
    # In galactic mode, scale_dist == dist_ly / 1000 → convert back.
    perp_ly = math.sqrt(best_dist_units) * 1000.0
    return (best_name, perp_ly)


def arm_scene_points(arm: dict, mode: ViewMode, n_pts: int = 80) -> dict:
    """Return {'x':..., 'y':..., 'z':...} for a logarithmic-spiral arm."""
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    zs = [0.0] * (n_pts + 1)
    phi0 = math.radians(arm["phi0"])
    tan_p = math.tan(math.radians(arm["pitch"]))
    xs, ys = [], []
    for i in range(n_pts + 1):
        t = i / n_pts
        phi = phi0 + t * 2 * math.pi
        r_ly = min(arm["r0_ly"] * math.exp(tan_p * t * 2 * math.pi),
                   arm["rmax_ly"])
        r = scale_dist(r_ly, mode)
        xs.append(gc_x + r * math.cos(phi))
        ys.append(r * math.sin(phi))
    return {"x": xs, "y": ys, "z": zs}


def build_constellation_lines(center_ra: float, center_dec: float,
                              mode: ViewMode,
                              shell_ly: float = 800.0
                              ) -> dict | None:
    """Return line-segment data for the constellation that contains the
    target sky position.

    Uses :func:`astropy.coordinates.SkyCoord.get_constellation` to pick
    the IAU constellation, then looks up its stick figure in
    ``CONSTELLATION_STICKS``.  Each vertex is projected to a "near-Earth
    shell" at ``shell_ly`` (scaled through the view mode so the lines
    are actually visible in the scene), with Nones separating each
    segment for Plotly's Scatter3d line-break convention.

    Returns ``None`` if the constellation isn't in our curated set or
    astropy isn't available — the caller silently skips in that case.
    """
    try:
        c = SkyCoord(center_ra * u.deg, center_dec * u.deg)
        const_name = str(c.get_constellation())
    except Exception:
        return None
    segs = CONSTELLATION_STICKS.get(const_name)
    if not segs:
        return None
    shell = scale_dist(shell_ly, mode)
    xs: list[float | None] = []
    ys: list[float | None] = []
    zs: list[float | None] = []
    for (ra_a, dec_a), (ra_b, dec_b) in segs:
        la, ba = radec_to_galactic(ra_a, dec_a)
        lb, bb = radec_to_galactic(ra_b, dec_b)
        xa, ya, za = gal_to_xyz(la, ba, shell)
        xb, yb, zb = gal_to_xyz(lb, bb, shell)
        xs.extend([xa, xb, None])
        ys.extend([ya, yb, None])
        zs.extend([za, zb, None])
    return {
        "name": const_name,
        "x": xs, "y": ys, "z": zs,
        "shell_ly": shell_ly,
    }


def build_arm_name_labels(mode: ViewMode) -> dict:
    """Return labelled points for each spiral arm, placed ~62% of the
    way along the arm's parametric sweep and lifted a couple hundred
    light-years above the disk plane so the text doesn't overlap the
    line.  The label is the short arm token ("Orion", "Perseus", ...)
    in the arm's own colour — the astrophotographer's first question
    when reading a galactic map is "which arm lives here", and naming
    them answers it at a glance.
    """
    xs, ys, zs, texts, cols = [], [], [], [], []
    lift = scale_dist(300.0, mode)  # few hundred ly above the plane
    for arm in SPIRAL_ARMS:
        pts = arm_scene_points(arm, mode, n_pts=80)
        n = len(pts["x"])
        if n < 2:
            continue
        idx = max(0, min(n - 1, int(n * 0.62)))
        # "Orion Arm (local)" → "Orion"; "Scutum-Centaurus" → "Scutum"
        short = arm["name"].split(" (")[0].replace(" Arm", "")
        if "-" in short:
            short = short.split("-")[0]
        xs.append(pts["x"][idx])
        ys.append(pts["y"][idx])
        zs.append(lift)
        texts.append(short)
        cols.append(arm["col"])
    return {"x": xs, "y": ys, "z": zs, "text": texts, "colors": cols}


def generate_disk_stars(mode: ViewMode, n: int = 500, seed: int = 42,
                        arm_bias: float = 0.55) -> dict:
    """Disk stars with an exponential radial profile, sech² vertical
    profile, and a fraction of stars biased to live near the spiral
    arms (matching what a Milky-Way map actually looks like from above).

    ``arm_bias`` is the fraction of stars drawn from arm-adjacent
    positions; the remainder are smoothly distributed across the disk.
    """
    rng = np.random.default_rng(seed)
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    rmax = scale_dist(GALAXY_RADIUS_LY, mode)
    hmax = scale_dist(GALAXY_THICK_LY, mode)
    xs, ys, zs, bs = [], [], [], []

    n_arm = int(n * max(0.0, min(1.0, arm_bias)))
    n_smooth = n - n_arm

    # --- Arm-biased stars: sample along each spiral arm curve and
    #     add a small perpendicular Gaussian scatter, so the overhead
    #     impression is of stars *tracing* the arms rather than filling
    #     a uniform cloud.  Brightness is proportional to radial density
    #     (bright near the centre, dim at the rim) like a real galaxy.
    if n_arm > 0 and SPIRAL_ARMS:
        per_arm = max(1, n_arm // len(SPIRAL_ARMS))
        for arm in SPIRAL_ARMS:
            pts = arm_scene_points(arm, mode, n_pts=80)
            ax_arr = np.asarray(pts["x"], dtype=float)
            ay_arr = np.asarray(pts["y"], dtype=float)
            if ax_arr.size < 2:
                continue
            # Pick random parameter positions along the arm.
            ts = rng.uniform(0, ax_arr.size - 1, size=per_arm)
            i0 = ts.astype(int)
            i1 = np.clip(i0 + 1, 0, ax_arr.size - 1)
            frac = ts - i0
            bx = ax_arr[i0] * (1 - frac) + ax_arr[i1] * frac
            by = ay_arr[i0] * (1 - frac) + ay_arr[i1] * frac
            # Perpendicular scatter (≈ arm half-width / 2 kly).
            arm_halfwidth = scale_dist(1500.0, mode)
            sx = rng.normal(0, arm_halfwidth, size=per_arm)
            sy = rng.normal(0, arm_halfwidth, size=per_arm)
            sz = rng.normal(0, hmax * 0.22, size=per_arm)
            xs.extend((bx + sx).tolist())
            ys.extend((by + sy).tolist())
            zs.extend(sz.tolist())
            # Brightness: warmer/brighter where closer to GC.
            r_from_gc = np.hypot(bx + sx - gc_x, by + sy)
            bright = np.exp(-r_from_gc / (rmax * 0.6))
            bs.extend((bright * rng.uniform(0.45, 1.0,
                                            size=per_arm)).tolist())

    # --- Smooth exponential disk: sech² in z, exponential in r.
    for _ in range(n_smooth):
        r = float(min(rng.exponential(rmax * 0.35), rmax))
        phi = float(rng.uniform(0, 2 * math.pi))
        # sech²(z/h) sampling via inverse-cdf trick on the logistic-like
        # profile: z = h * atanh(U) with U ~ U(-1, 1), clamped away
        # from the singular tails.  Much closer to a real disk than the
        # plain Gaussian used before.
        uu = float(rng.uniform(-0.97, 0.97))
        h = hmax * 0.55 * math.atanh(uu)
        b = float(np.exp(-r / (rmax * 0.5)) * rng.uniform(0.35, 1.0))
        xs.append(gc_x + r * math.cos(phi))
        ys.append(r * math.sin(phi))
        zs.append(h)
        bs.append(b)

    return {"x": xs, "y": ys, "z": zs, "b": bs}


def generate_bulge_stars(mode: ViewMode, n: int = 180, seed: int = 43
                         ) -> dict:
    """Central bulge — warmer/denser stellar population centred on
    Sgr A*.  Gaussian in r, slightly oblate (shorter in z than in the
    plane), warm amber tint.
    """
    rng = np.random.default_rng(seed)
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    # ~8 kly scale length — roughly the bulge half-diameter in ly.
    r_scale = scale_dist(4_000.0, mode)
    z_scale = r_scale * 0.55
    rs = np.abs(rng.normal(0, r_scale, size=n))
    phis = rng.uniform(0, 2 * math.pi, size=n)
    zs_arr = rng.normal(0, z_scale, size=n)
    xs = (gc_x + rs * np.cos(phis)).tolist()
    ys = (rs * np.sin(phis)).tolist()
    zs = zs_arr.tolist()
    return {"x": xs, "y": ys, "z": zs}


def build_disk_plane_mesh(mode: ViewMode, n_ring: int = 72) -> dict:
    """Translucent annulus at z=0 giving the eye a 'galactic plane'
    surface to mount the arms on.  Returns a Mesh3d-ready dict with
    ``x``/``y``/``z``/``i``/``j``/``k`` lists.
    """
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    r_inner = scale_dist(2_000.0, mode)
    r_outer = scale_dist(GALAXY_RADIUS_LY, mode) * 1.05
    phis = np.linspace(0, 2 * math.pi, n_ring, endpoint=False)
    inner_x = gc_x + r_inner * np.cos(phis)
    inner_y = r_inner * np.sin(phis)
    outer_x = gc_x + r_outer * np.cos(phis)
    outer_y = r_outer * np.sin(phis)
    xs = np.concatenate([inner_x, outer_x]).tolist()
    ys = np.concatenate([inner_y, outer_y]).tolist()
    zs = [0.0] * (2 * n_ring)
    # P3.8 — radial gradient.  Per-vertex intensity = 1 on the inner
    # ring (bulge edge), 0 on the outer ring (disk edge).  Combined
    # with a brightness-only colorscale this reads as "brightest near
    # the bulge, fading toward the disk edge" — sells the 'galaxy
    # disk' shape rather than a uniform tinted rectangle.
    intensity = ([1.0] * n_ring) + ([0.0] * n_ring)
    # Triangulate: for each ring segment, two triangles connect
    # inner[i],inner[i+1],outer[i+1] and inner[i],outer[i+1],outer[i].
    i_idx, j_idx, k_idx = [], [], []
    for i in range(n_ring):
        in0 = i
        in1 = (i + 1) % n_ring
        out0 = n_ring + i
        out1 = n_ring + in1
        i_idx += [in0, in0]
        j_idx += [in1, out1]
        k_idx += [out1, out0]
    return {"x": xs, "y": ys, "z": zs,
            "i": i_idx, "j": j_idx, "k": k_idx,
            "intensity": intensity}


def build_distance_rings(mode: ViewMode) -> list[dict]:
    """Concentric rings on z=0 at canonical distances from the
    galactic centre (galactic mode) or from Earth (cosmic mode).
    Returns a list of ``{"x","y","z","label","r_ly"}`` dicts, one per
    ring — the caller renders them as individual thin line traces so
    each can carry its own hover label.
    """
    rings: list[dict] = []
    if mode is ViewMode.GALACTIC:
        center_x = scale_dist(EARTH_TO_GC_LY, mode)
        radii_ly = [10_000, 20_000, 30_000, 40_000]
    else:
        center_x = 0.0   # ring centred on Earth for cosmic mode
        # Densified: each visible decade now has a midpoint, so the
        # log-compressed scale beyond 1 Mly has more visual cues for
        # judging distance.  Was [1e6, 1e7, 1e8, 1e9] (4 rings); now
        # 8 rings with 5×10^n midpoints.
        radii_ly = [1e6, 5e6, 1e7, 5e7, 1e8, 5e8, 1e9, 5e9]
    # 120 vertices / ring (~3° per chord).  Was 240, dropped for
    # performance — at the camera distances people actually use,
    # 120 reads as smooth.  Re-bump to 240 if you see polygon
    # facets when zoomed close to a ring plane.
    phis = np.linspace(0, 2 * math.pi, 120)
    cos_p = np.cos(phis)
    sin_p = np.sin(phis)
    for d_ly in radii_ly:
        r = scale_dist(d_ly, mode)
        xs = (center_x + r * cos_p).tolist()
        ys = (r * sin_p).tolist()
        zs = [0.0] * len(xs)
        rings.append({
            "x": xs, "y": ys, "z": zs,
            "label": _format_ly_label(d_ly),
            "r_ly": d_ly,
            "r_scene": r,
            "center_x": center_x,
        })
    return rings


def build_helio_rings(mode: ViewMode) -> list[dict]:
    """Heliocentric distance rings — concentric circles centered on
    Earth (not the Galactic Center).  Renders in galactic mode only;
    cosmic mode's existing rings are already Earth-centered, so a
    second set there would be redundant.

    Astronomers and amateurs alike think distance-from-Earth, not
    distance-from-Galactic-Center.  The default `build_distance_rings`
    set is GC-centered for galactic structure context — but you also
    need the "how far is this from us?" answer at a glance.  These
    rings provide that.
    """
    rings: list[dict] = []
    if mode is not ViewMode.GALACTIC:
        return rings
    # Earth sits at the scene origin (0,0,0); GC is offset to +x.
    # Centre the heliocentric rings on Earth.
    center_x = 0.0
    # Decade-style radii sized to the visible 50 kly disk.
    radii_ly = [1_000, 5_000, 10_000, 25_000]
    phis = np.linspace(0, 2 * math.pi, 120)
    cos_p = np.cos(phis)
    sin_p = np.sin(phis)
    for d_ly in radii_ly:
        r = scale_dist(d_ly, mode)
        xs = (center_x + r * cos_p).tolist()
        ys = (r * sin_p).tolist()
        zs = [0.0] * len(xs)
        rings.append({
            "x": xs, "y": ys, "z": zs,
            "label": _format_ly_label(d_ly),
            "r_ly": d_ly,
            "r_scene": r,
            "center_x": center_x,
        })
    return rings


def build_compass_rose(scene: dict, mode: ViewMode,
                       length: float | None = None
                       ) -> list[dict]:
    """Three short labeled arrows at Earth's origin pointing at:
       → Galactic Center  (warm)
       ↑ North Galactic Pole  (cool)
       → Target (viewing ray)  (yellow)
    Returns a list of trace-ready dicts with xs/ys/zs/color/label.
    """
    if length is None:
        # Make the rose ~8 kly long in galactic mode, ~0.8 units in
        # cosmic mode — visible without dominating.
        length = (scale_dist(8_000.0, mode)
                  if mode is ViewMode.GALACTIC else 0.8)

    # Direction toward Galactic Center is always +x in scene coords.
    gc_dir = (1.0, 0.0, 0.0)
    ngp_dir = (0.0, 0.0, 1.0)
    target_dir = None
    photo_center = scene.get("photo_center_xyz")
    if photo_center is not None:
        tx, ty, tz = float(photo_center[0]), float(photo_center[1]), float(photo_center[2])
        m = math.sqrt(tx * tx + ty * ty + tz * tz)
        if m > 1e-6:
            target_dir = (tx / m, ty / m, tz / m)

    arrows = []
    arrows.append({"dir": gc_dir, "color": "#ffaa55",
                   "label": "→ Galactic Center",
                   "name": "Compass: Galactic Center"})
    arrows.append({"dir": ngp_dir, "color": "#66b0ff",
                   "label": "↑ North Galactic Pole",
                   "name": "Compass: Galactic North"})
    if target_dir is not None:
        arrows.append({"dir": target_dir, "color": "#ffdd66",
                       "label": "→ Target",
                       "name": "Compass: Target"})
    # Materialise shaft + tip coordinates.
    for a in arrows:
        dx, dy, dz = a["dir"]
        a["xs"] = [0.0, dx * length]
        a["ys"] = [0.0, dy * length]
        a["zs"] = [0.0, dz * length]
        a["tip"] = (dx * length, dy * length, dz * length)
    return arrows


# ---------------------------------------------------------------------------
# WCS detection (same 6-strategy pattern as CosmicDepth 3D)
# ---------------------------------------------------------------------------
def extract_wcs_from_header(header_str: str) -> WCS | None:
    try:
        hdr = astropy_fits.Header.fromstring(header_str, sep="\n")
        w = WCS(hdr, naxis=[1, 2])
        if w.has_celestial:
            return w
    except Exception:
        pass
    try:
        # Sometimes header is returned without line-endings
        hdr = astropy_fits.Header.fromstring(header_str)
        w = WCS(hdr, naxis=[1, 2])
        if w.has_celestial:
            return w
    except Exception:
        pass
    return None


def extract_wcs_from_fits_file(siril, log_func=None) -> WCS | None:
    candidates: list[str] = []
    try:
        fn = siril.get_image_filename()
        if fn and os.path.isfile(fn):
            candidates.append(fn)
    except Exception:
        pass
    try:
        wd = siril.get_siril_wd() or os.getcwd()
        if wd and os.path.isdir(wd):
            for name in sorted(os.listdir(wd),
                               key=lambda n: os.path.getmtime(
                                   os.path.join(wd, n)), reverse=True):
                if name.lower().endswith((".fit", ".fits", ".fts")):
                    candidates.append(os.path.join(wd, name))
    except Exception:
        pass
    seen = set()
    for path in candidates[:5]:
        if path in seen:
            continue
        seen.add(path)
        try:
            with astropy_fits.open(path) as hdul:
                for hdu in hdul:
                    if hdu.header.get("CRVAL1") is None:
                        continue
                    w = WCS(hdu.header, naxis=[1, 2])
                    if w.has_celestial:
                        if log_func:
                            log_func(f"WCS: loaded from {path}")
                        return w
        except Exception as e:
            if log_func:
                log_func(f"FITS probe failed for {path}: {e}")
    return None


def compute_pixel_scale(wcs: WCS) -> float:
    """Arcseconds per pixel from WCS CD or CDELT."""
    try:
        if hasattr(wcs.wcs, "cd") and wcs.wcs.cd is not None \
                and not np.all(wcs.wcs.cd == 0):
            cd = wcs.wcs.cd
            scale = math.sqrt(abs(cd[0, 0] * cd[1, 1]
                                  - cd[0, 1] * cd[1, 0])) * 3600.0
            if scale > 0:
                return float(scale)
    except Exception:
        pass
    try:
        return float(abs(wcs.wcs.cdelt[0]) * 3600.0)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Distance cache (GalacticView-owned)
# ---------------------------------------------------------------------------
class GalacticViewCache:
    """JSON-backed single-object distance cache with TTL."""

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
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except Exception as e:
                # Best-effort: a failed save just means the next session
                # will re-query online sources.  Log to stderr so at least
                # the reason (permissions? disk full?) is traceable.
                sys.stderr.write(
                    f"[GalacticView3D] distance cache save failed: {e}\n")

    def _key(self, name: str) -> str:
        return _RE_WHITESPACE.sub(' ', name).strip().upper()

    def get(self, name: str) -> dict | None:
        k = self._key(name)
        with self._lock:
            entry = self.data["objects"].get(k)
        if not entry:
            return None
        try:
            last = datetime.date.fromisoformat(
                entry.get("last_updated", "1970-01-01"))
            if (datetime.date.today() - last).days > self.ttl_days:
                return None
        except Exception:
            return None
        # Backward-compat: older cache files used "dist_lj" / "dist_err_lj"
        # (German "Lichtjahr").  Promote them into the new "dist_ly" keys
        # on the fly so the rest of the code can assume the modern names.
        if "dist_ly" not in entry and "dist_lj" in entry:
            entry["dist_ly"] = entry["dist_lj"]
        if "dist_err_ly" not in entry and "dist_err_lj" in entry:
            entry["dist_err_ly"] = entry["dist_err_lj"]
        return entry

    def set(self, name: str, dist_ly: float, dist_err_ly: float,
            source: str, obj_type: str = "", mode: str = "",
            bibcode: str = "", confidence: str = "medium") -> None:
        k = self._key(name)
        with self._lock:
            self.data["objects"][k] = {
                "name": name,
                "dist_ly": float(dist_ly),
                "dist_err_ly": float(dist_err_ly),
                "dist_source": source,
                "dist_bibcode": bibcode,
                "obj_type": obj_type,
                "mode": mode,
                "confidence": confidence,
                "last_updated": datetime.date.today().isoformat(),
            }
        self.save()

    def clear(self) -> None:
        with self._lock:
            self.data = {"cache_version": CACHE_VERSION, "objects": {}}
        self.save()


# ---------------------------------------------------------------------------
# Main-object identification + distance resolution
# ---------------------------------------------------------------------------
def _simbad_query_object(name: str, log_func=None):
    """Query SIMBAD for a named object. Tries common spelling variants
    (e.g. 'M42' <-> 'M 42', 'NGC 1976' <-> 'NGC1976') before giving up."""
    def _try(n: str):
        try:
            custom = Simbad()
            custom.add_votable_fields("otype", "V")
            # 'rvz_redshift' is the modern field; 'z_value' was deprecated.
            for field in ("rvz_redshift", "rvz_radvel"):
                try:
                    custom.add_votable_fields(field)
                except Exception:
                    pass
            custom.ROW_LIMIT = 5
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return custom.query_object(n)
        except Exception as e:
            if log_func:
                log_func(f"SIMBAD query_object('{n}') failed: {e}")
            return None

    variants = [name]
    stripped = name.strip()
    if stripped and stripped not in variants:
        variants.append(stripped)
    # 'M 42' <-> 'M42' ; 'NGC 1976' <-> 'NGC1976'
    compact = stripped.replace(" ", "")
    if compact and compact != stripped:
        variants.append(compact)
    spaced = None
    for pref in ("M", "NGC", "IC"):
        if stripped.upper().startswith(pref) and len(stripped) > len(pref):
            rest = stripped[len(pref):].lstrip()
            if rest and not stripped[len(pref)].isspace():
                spaced = f"{pref} {rest}"
                break
    if spaced and spaced not in variants:
        variants.append(spaced)

    for v in variants:
        result = _try(v)
        if result is not None and len(result) > 0:
            return result
    return None


# Accept only well-known astrophotography catalog prefixes (copied from
# Svenesis-CosmicDepth3D to keep picker entries limited to human-
# recognisable catalog names — M 42, NGC 1976 — rather than cryptic
# SIMBAD main_ids like "* iot Ori" or "2MASS Jxxxxx".
_USEFUL_CATALOG_PREFIXES = (
    "NGC", "IC ", "IC1", "IC2", "IC3", "IC4", "IC5",
    "M ", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
    "UGC", "MCG", "Arp", "Abell", "Mrk", "VV ",
    "Ced", "Sh2", "LBN", "LDN", "Barnard", "B ",
    "Cr ", "Mel", "Tr ", "Pal", "PGC", "ESO", "CGCG",
    "Hickson", "HCG", "PN G",
    "Hen", "He ", "Haro",
    "NAME ",
    "vdB", "RCW", "Gum", "Collinder", "Stock", "DWB",
)
_USEFUL_PREFIX_BY_CHAR: dict[str, list[str]] = {}
for _p in _USEFUL_CATALOG_PREFIXES:
    _USEFUL_PREFIX_BY_CHAR.setdefault(_p[0], []).append(_p)


def _is_useful_catalog_name(name: str) -> bool:
    if not name:
        return False
    cs = _USEFUL_PREFIX_BY_CHAR.get(name[0])
    return cs is not None and any(name.startswith(p) for p in cs)


def collect_simbad_candidates(center_ra: float, center_dec: float,
                              fov_radius_deg: float,
                              row_limit: int = 3000,
                              log_func=None,
                              siril=None,
                              img_w: int = 0, img_h: int = 0,
                              pixel_scale_arcsec: float = 0.0,
                              mag_limit: float = 99.0,
                              wcs=None) -> list[dict]:
    """Return SIMBAD cone-search hits as a ranked list of candidates.

    Mirrors the query flow of Svenesis-CosmicDepth3D._query_simbad_objects:
    the same votable fields (``V``, ``galdim_majaxis``, ``otype``), the
    same tile-wide-fields logic (>0.75° radius), the same useful-catalog
    prefix filter, name dedup, magnitude cut, and pixel-bounds check.

    Extra bits kept for GalacticView3D's own use: parallax / redshift /
    distance estimate. Distance is *not* used to filter candidates — the
    list matches CosmicDepth3D's object set exactly.
    """

    def _build_simbad() -> Simbad:
        s = Simbad()
        # Add each field individually so a rename between astroquery
        # versions can't silently abort the whole query.
        for field in ("V", "galdim_majaxis", "otype",
                      "plx_value", "rvz_redshift"):
            try:
                s.add_votable_fields(field)
            except Exception as fe:
                if log_func:
                    log_func(f"SIMBAD field '{field}' not available: {fe}")
        s.ROW_LIMIT = row_limit
        return s

    # --- Build the tile list (same strategy as CosmicDepth3D) ---
    center = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg)
    MAX_Q = 0.75  # deg — SIMBAD prefers ≤45′ radius
    if fov_radius_deg <= MAX_Q:
        tiles = [center]
        q_radius = Angle(max(0.01, fov_radius_deg), unit="deg")
    else:
        step = MAX_Q * 1.2
        # Image half-size in degrees; fall back to radius if no pixel info.
        if img_w > 0 and img_h > 0 and pixel_scale_arcsec > 0:
            half_w = (img_w * pixel_scale_arcsec / 3600.0) / 2.0
            half_h = (img_h * pixel_scale_arcsec / 3600.0) / 2.0
        else:
            half_w = half_h = fov_radius_deg / math.sqrt(2.0)
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
        if log_func:
            log_func(f"SIMBAD: wide field — tiling into {len(tiles)} queries")

    if log_func:
        log_func(f"SIMBAD cone-search: center="
                 f"({center_ra:.4f},{center_dec:.4f}) "
                 f"radius={float(q_radius.deg):.3f}° "
                 f"over {len(tiles)} tile(s)")

    # --- Run the queries ---
    all_results = []
    try:
        def _query_tile(qc: SkyCoord):
            simbad = _build_simbad()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return simbad.query_region(qc, radius=q_radius)

        if len(tiles) == 1:
            r = _query_tile(tiles[0])
            if r is not None and len(r) > 0:
                all_results.append(r)
        else:
            from concurrent.futures import (
                ThreadPoolExecutor, as_completed, TimeoutError as FutTimeout,
            )
            # Per-future timeout so a single hung DNS / network stall
            # cannot freeze the UI thread indefinitely.  Value comes from
            # the module-level SIMBAD_TILE_TIMEOUT_S constant (30 s by
            # default, matching the astroquery default with vstack room).
            TILE_TIMEOUT_S = SIMBAD_TILE_TIMEOUT_S
            with ThreadPoolExecutor(
                max_workers=min(8, len(tiles)),
                thread_name_prefix="simbad_tile",
            ) as pool:
                futures = [pool.submit(_query_tile, qc) for qc in tiles]
                timed_out = 0
                for fut in as_completed(futures, timeout=None):
                    try:
                        r = fut.result(timeout=TILE_TIMEOUT_S)
                    except FutTimeout:
                        timed_out += 1
                        r = None
                        fut.cancel()
                    except Exception as e:
                        if log_func:
                            log_func(f"SIMBAD tile failed: {e}")
                        r = None
                    if r is not None and len(r) > 0:
                        all_results.append(r)
                if timed_out and log_func:
                    log_func(
                        f"SIMBAD: {timed_out} of {len(tiles)} tile(s) "
                        f"timed out after {TILE_TIMEOUT_S:.0f}s "
                        "— results may be incomplete.")
    except Exception as e:
        if log_func:
            log_func(f"Cone-search failed: {e}")
        return []

    if not all_results:
        if log_func:
            log_func("SIMBAD cone-search returned 0 rows.")
        return []

    if len(all_results) == 1:
        result = all_results[0]
    else:
        from astropy.table import vstack
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = vstack(all_results)

    if log_func:
        log_func(f"SIMBAD cone-search returned {len(result)} raw rows "
                 f"(over {len(tiles)} tile(s)).")

    id_col = next((c for c in result.colnames
                   if c.lower() == "main_id"), None)
    v_col = "V" if "V" in result.colnames else None
    otype_col = next((c for c in result.colnames
                      if c.lower() == "otype"), None)
    ra_col = next((c for c in result.colnames
                   if c.lower() in ("ra", "ra_d")), None)
    dec_col = next((c for c in result.colnames
                    if c.lower() in ("dec", "dec_d")), None)
    plx_col = next((c for c in result.colnames
                    if c.lower() in ("plx_value", "plx")), None)
    z_col = next((c for c in result.colnames
                  if c.lower() in ("rvz_redshift", "z_value",
                                   "redshift")), None)
    ids_col = next((c for c in result.colnames
                    if c.lower() == "ids"), None)
    size_col = next((c for c in result.colnames
                     if c.lower() in ("galdim_majaxis", "dim_majaxis")),
                    None)
    if id_col is None:
        return []

    def _pick_best_name(alt_ids: list[str], main_id: str) -> str:
        """Rank SIMBAD alternative ids for human readability.

        Priority: Messier > NAME-prefixed popular name > NGC > IC > main_id.
        """
        messier, namep, ngc, ic = None, None, None, None
        for p in alt_ids:
            if not p:
                continue
            up = p.upper()
            if up.startswith("M ") and up[2:].strip().isdigit():
                if messier is None:
                    messier = p.strip()
            elif (up.startswith("M") and len(up) > 1
                  and up[1:].strip().isdigit()):
                if messier is None:
                    messier = f"M {up[1:].strip()}"
            elif up.startswith("NAME "):
                if namep is None:
                    namep = p[5:].strip()
            elif up.startswith("NGC"):
                if ngc is None:
                    tail = p[3:].lstrip()
                    ngc = f"NGC {tail}" if tail else p.strip()
            elif up.startswith("IC") and (len(up) == 2
                                          or not up[2].isalpha()):
                if ic is None:
                    tail = p[2:].lstrip()
                    ic = f"IC {tail}" if tail else p.strip()
        return messier or namep or ngc or ic or main_id

    def _best_display_name(ids_str: str, main_id: str) -> str:
        if not ids_str:
            return main_id
        parts = [p.strip() for p in str(ids_str).split("|") if p.strip()]
        return _pick_best_name(parts, main_id)

    preferred_prefixes = ("M ", "NGC", "IC ",
                          "IC1", "IC2", "IC3", "IC4", "IC5")

    def _estimate_distance(otype: str, plx: float, z: float
                           ) -> tuple[float, str]:
        """Return (dist_ly, source_tag) or (nan, '') if unknown.

        Priority: parallax > redshift > object-type median.
        """
        if plx == plx and plx > 0.1:  # parallax in mas
            dist_pc = 1000.0 / plx
            return dist_pc * PC_TO_LY, "plx"
        if z == z and abs(z) > 1e-4:
            dist_mpc = (abs(z) * C_KM_S) / HUBBLE_H0
            return dist_mpc * MPC_TO_LY, "z"
        if otype:
            fb = TYPE_DISTANCE_MEDIANS.get(otype)
            if fb is None:
                if otype in COSMIC_TYPES:
                    fb = TYPE_DISTANCE_MEDIANS.get("Galaxy")
                elif otype in GALACTIC_TYPES:
                    fb = TYPE_DISTANCE_MEDIANS.get("Neb")
            if fb is not None:
                return float(fb["dist_ly"]), "type"
        return float("nan"), ""

    # Staged two-pass build: the per-row hot path used to build a fresh
    # SkyCoord *per candidate* for the angular-separation test, and called
    # siril.radec2pix() per candidate for the bounds filter.  Both are
    # ~O(N) Python calls that dominate for N≈2000–5000.  Instead:
    #   Pass 1 → cryptic/dup/mag filter + ra/dec parse, stage records.
    #   Batch  → one SkyCoord(ras*u.deg, decs*u.deg) + one separation().
    #            WCS.all_world2pix() in one call if a WCS is available
    #            (otherwise fall back to per-row siril.radec2pix).
    seen_names: set[str] = set()
    filtered_cryptic = 0
    filtered_dup = 0
    filtered_mag = 0
    filtered_bounds = 0
    staged: list[dict] = []
    for row in result:
        main_id = str(row[id_col]).strip()
        if not main_id:
            continue
        # Reject cryptic SIMBAD main_ids that are not in a well-known
        # astrophotography catalog (same approach as CosmicDepth3D).
        if not _is_useful_catalog_name(main_id):
            filtered_cryptic += 1
            continue
        if main_id in seen_names:
            filtered_dup += 1
            continue
        seen_names.add(main_id)

        ids_str = (str(row[ids_col]).strip()
                   if ids_col is not None else "")
        name = _best_display_name(ids_str, main_id)
        mag = _safe_float(row[v_col], 0.0) if v_col else 0.0
        if mag != 0.0 and not (mag != mag) and mag > mag_limit:
            filtered_mag += 1
            continue
        if mag != mag:  # NaN
            mag = 0.0

        otype = (str(row[otype_col]).strip()
                 if otype_col is not None else "")
        try:
            ra_val = _safe_float(row[ra_col]) if ra_col else float("nan")
            dec_val = _safe_float(row[dec_col]) if dec_col else float("nan")
            if ra_val != ra_val or dec_val != dec_val:
                coord = SkyCoord(str(row[ra_col]), str(row[dec_col]),
                                 unit=(u.hourangle, u.deg))
                ra_val, dec_val = coord.ra.deg, coord.dec.deg
        except Exception:
            ra_val, dec_val = float("nan"), float("nan")

        plx_val = (_safe_float(row[plx_col], float("nan"))
                   if plx_col is not None else float("nan"))
        z_val = (_safe_float(row[z_col], float("nan"))
                 if z_col is not None else float("nan"))
        size_arcmin = (_safe_float(row[size_col], float("nan"))
                       if size_col is not None else float("nan"))
        staged.append({
            "main_id": main_id,
            "name": name,
            "otype": otype,
            "mag": mag,
            "ra": ra_val,
            "dec": dec_val,
            "plx": plx_val,
            "z": z_val,
            "size_arcmin": size_arcmin,
        })

    n = len(staged)
    # Batch 1 — pixel-rectangle bounds check.
    # Prefer WCS (vectorised, no siril round-trip); fall back to
    # per-row siril.radec2pix for back-compat when no WCS is available.
    keep_bounds = np.ones(n, dtype=bool)
    if n > 0 and img_w > 0 and img_h > 0:
        ras_all = np.array([s["ra"] for s in staged], dtype=float)
        decs_all = np.array([s["dec"] for s in staged], dtype=float)
        finite_mask = np.isfinite(ras_all) & np.isfinite(decs_all)
        if wcs is not None:
            try:
                # One vectorised call instead of N SIP-aware round-trips.
                world = np.column_stack([ras_all, decs_all])
                # Guard NaN inputs: fill with center, will be re-masked out.
                safe_world = world.copy()
                safe_world[~finite_mask] = [center_ra, center_dec]
                pix = wcs.all_world2pix(safe_world, 0)
                px = pix[:, 0]
                py = pix[:, 1]
                inside = ((px >= 0) & (px <= img_w)
                          & (py >= 0) & (py <= img_h)
                          & np.isfinite(px) & np.isfinite(py)
                          & finite_mask)
                keep_bounds = inside
            except Exception as e:
                if log_func:
                    log_func(f"WCS bulk bounds-check failed ({e}); "
                             "falling back to per-row siril.radec2pix.")
                keep_bounds = np.ones(n, dtype=bool)  # retry below
                wcs = None  # force fallback path
        if wcs is None and siril is not None:
            # Per-row fallback — unavoidable, siril.radec2pix isn't batched.
            for i, s in enumerate(staged):
                try:
                    px_res = siril.radec2pix(s["ra"], s["dec"])
                    if px_res is None:
                        keep_bounds[i] = False
                        continue
                    px, py = float(px_res[0]), float(px_res[1])
                    if not (0 <= px <= img_w and 0 <= py <= img_h):
                        keep_bounds[i] = False
                except Exception:
                    keep_bounds[i] = False

    filtered_bounds = int((~keep_bounds).sum())

    # Batch 2 — angular separation from frame center.
    # One SkyCoord constructor call + one separation() call instead of N.
    seps_deg = np.full(n, float("nan"), dtype=float)
    if n > 0:
        ras_all = np.array([s["ra"] for s in staged], dtype=float)
        decs_all = np.array([s["dec"] for s in staged], dtype=float)
        finite_mask = np.isfinite(ras_all) & np.isfinite(decs_all)
        if finite_mask.any():
            try:
                pts = SkyCoord(ra=ras_all[finite_mask] * u.deg,
                               dec=decs_all[finite_mask] * u.deg)
                seps_finite = center.separation(pts).deg
                seps_deg[finite_mask] = np.asarray(seps_finite, dtype=float)
            except Exception:
                # Leave NaN; ranking falls back to 99.0 below.
                pass

    candidates: list[dict] = []
    for i, s in enumerate(staged):
        if not keep_bounds[i]:
            continue
        sep_deg = float(seps_deg[i])
        # Approximate "size in the photo" in pixels from the plate-solve
        # pixel scale (arcsec/px). Useful for finding the largest object.
        size_arcmin = s["size_arcmin"]
        size_px = float("nan")
        if (size_arcmin == size_arcmin and size_arcmin > 0
                and pixel_scale_arcsec > 0):
            size_px = (size_arcmin * 60.0) / pixel_scale_arcsec
        # Distance estimate is kept for display/ranking but does NOT
        # gate inclusion — CosmicDepth3D shows objects regardless.
        dist_ly_est, dist_source = _estimate_distance(
            s["otype"], s["plx"], s["z"])
        name = s["name"]
        mag = s["mag"]
        pref = 0 if any(name.startswith(p)
                        for p in preferred_prefixes) else 1
        rank_key = (pref,
                    mag if (mag is not None and mag > 0) else 99.0,
                    sep_deg if sep_deg == sep_deg else 99.0)
        candidates.append({
            "name": name,
            "simbad_id": s["main_id"],
            "otype": s["otype"],
            "mag": mag,
            "ra": s["ra"],
            "dec": s["dec"],
            "sep_deg": sep_deg,
            "plx_mas": s["plx"],
            "redshift": s["z"],
            "dist_ly_estimate": dist_ly_est,
            "dist_source_hint": dist_source,
            "size_arcmin": size_arcmin,
            "size_px": size_px,
            "rank_key": rank_key,
        })
    candidates.sort(key=lambda c: c["rank_key"])
    if log_func:
        log_func(
            f"Cone-search: {len(candidates)} candidates "
            f"(filtered: {filtered_cryptic} non-catalog, "
            f"{filtered_dup} dup, {filtered_mag} over mag "
            f"{mag_limit:g}, {filtered_bounds} outside frame).")
    return candidates


class _NumericSortItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by a numeric key rather than by text."""

    def __init__(self, display: str, sort_value: float):
        super().__init__(display)
        self._sort_value = float(sort_value)

    def __lt__(self, other):
        if isinstance(other, _NumericSortItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


class TargetPickerDialog(QDialog):
    """Let the user pick the main target from a list of SIMBAD candidates."""

    _ROLE_CANDIDATE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, candidates: list[dict], parent=None,
                 preselect_name: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select main target")
        self.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QTableWidget{background-color:#252525;color:#e0e0e0;"
            "gridline-color:#333;selection-background-color:#3c6fa8;}"
            "QHeaderView::section{background-color:#2d2d2d;"
            "color:#cccccc;padding:4px;border:0;}"
            "QLineEdit{background-color:#252525;color:#e0e0e0;"
            "border:1px solid #555;padding:4px 6px;border-radius:3px;}"
            "QPushButton{background-color:#3a3a3a;color:#e0e0e0;"
            "padding:6px 14px;border:1px solid #555;border-radius:3px;}"
            "QPushButton:hover{background-color:#4a4a4a;}"
        )
        self.resize(680, 460)

        # Drop candidates whose distance is unknown — the 3D scene has no
        # place to put them, and the user asked never to list them.
        def _has_dist(c: dict) -> bool:
            d = c.get("dist_ly_estimate", float("nan"))
            try:
                d = float(d)
            except Exception:
                return False
            return d == d and d > 0  # filters NaN and non-positive

        candidates = [c for c in candidates if _has_dist(c)]
        self._candidates = candidates
        self._selected: dict | None = None

        layout = QVBoxLayout(self)
        header = QLabel(
            f"{len(candidates)} SIMBAD objects fall inside the field "
            "(objects without a known distance are hidden). "
            "Pick the one you want as the main target:"
        )
        header.setWordWrap(True)
        header.setStyleSheet("color:#ccc;padding:2px 2px 6px 2px;")
        layout.addWidget(header)

        # Filter row
        filter_row = QHBoxLayout()
        flabel = QLabel("Filter name:")
        flabel.setStyleSheet("color:#bbb;")
        filter_row.addWidget(flabel)
        self.edit_filter = QLineEdit(self)
        self.edit_filter.setPlaceholderText(
            "Type to filter by name (case-insensitive)…")
        self.edit_filter.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.edit_filter, 1)
        self.lbl_filter_count = QLabel("")
        self.lbl_filter_count.setStyleSheet("color:#888;")
        filter_row.addWidget(self.lbl_filter_count)
        layout.addLayout(filter_row)

        self.table = QTableWidget(len(candidates), 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Type", "V mag", "Distance",
             "Size in photo", "Offset from center"])
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(False)  # populate first, then enable

        for i, c in enumerate(candidates):
            name_item = QTableWidgetItem(c["name"])
            name_item.setData(self._ROLE_CANDIDATE, c)
            type_label = OBJECT_TYPE_LABELS.get(c["otype"], c["otype"] or "—")
            type_item = QTableWidgetItem(type_label)
            mag_val = c.get("mag", 99.0)
            mag_str = (f"{mag_val:.2f}"
                       if mag_val is not None and mag_val < 90
                       else "—")
            mag_sort = (float(mag_val)
                        if mag_val is not None and mag_val < 90
                        else float("inf"))
            mag_item = _NumericSortItem(mag_str, mag_sort)
            mag_item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
            sep = c.get("sep_deg", float("nan"))
            if sep == sep:
                if sep < 1.0 / 60.0:
                    sep_str = f"{sep*3600:.1f}″"
                elif sep < 1.0:
                    sep_str = f"{sep*60:.2f}′"
                else:
                    sep_str = f"{sep:.3f}°"
                sep_sort = float(sep)
            else:
                sep_str = "—"
                sep_sort = float("inf")
            sep_item = _NumericSortItem(sep_str, sep_sort)
            sep_item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)

            dist_ly = c.get("dist_ly_estimate", float("nan"))
            dist_src = c.get("dist_source_hint", "")
            src_suffix = {"plx": " (π)", "z": " (z)", "type": " ~"}.get(
                dist_src, "")
            if dist_ly == dist_ly and dist_ly > 0:
                if dist_ly < 1e6:
                    dist_str = f"{dist_ly:,.0f} ly"
                elif dist_ly < 1e9:
                    dist_str = f"{dist_ly/1e6:.2f} Mly"
                else:
                    dist_str = f"{dist_ly/1e9:.2f} Gly"
                dist_str += src_suffix
                dist_sort = float(dist_ly)
            else:
                dist_str = "—"
                dist_sort = float("inf")
            dist_item = _NumericSortItem(dist_str, dist_sort)
            dist_item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                       | Qt.AlignmentFlag.AlignVCenter)

            size_arcmin = c.get("size_arcmin", float("nan"))
            size_px = c.get("size_px", float("nan"))
            if size_arcmin == size_arcmin and size_arcmin > 0:
                if size_arcmin < 1.0:
                    size_str = f"{size_arcmin*60:.1f}″"
                else:
                    size_str = f"{size_arcmin:.2f}′"
                if size_px == size_px and size_px > 0:
                    size_str += f"  ({size_px:,.0f} px)"
                size_sort = float(size_arcmin)
            else:
                size_str = "—"
                size_sort = -1.0  # sort unknown sizes to the bottom
            size_item = _NumericSortItem(size_str, size_sort)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                       | Qt.AlignmentFlag.AlignVCenter)

            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, type_item)
            self.table.setItem(i, 2, mag_item)
            self.table.setItem(i, 3, dist_item)
            self.table.setItem(i, 4, size_item)
            self.table.setItem(i, 5, sep_item)

        self.table.setSortingEnabled(True)
        # Default: largest-in-photo first (biggest target is usually the
        # one the user wants to pick).
        self.table.sortItems(4, Qt.SortOrder.DescendingOrder)
        self.table.horizontalHeader().setSortIndicator(
            4, Qt.SortOrder.DescendingOrder)
        self.table.cellDoubleClicked.connect(
            lambda *_: self._accept_selection())
        layout.addWidget(self.table)

        # Pre-select after sorting is enabled — look up by name
        self._select_by_name(preselect_name)
        self._update_filter_count()
        # Keep the view anchored at the top so the largest-in-photo rows
        # (the default descending sort) are always visible on open —
        # even when the preselect is further down the list.  We scroll
        # both now and again after show via showEvent, because sorting +
        # column auto-sizing can adjust the scrollbar asynchronously.
        self.table.scrollToTop()
        self.table.verticalScrollBar().setValue(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self)
        self.btn_save_json = QPushButton("Save as JSON…", self)
        self.btn_save_json.clicked.connect(self._save_as_json)
        buttons.addButton(self.btn_save_json,
                          QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def showEvent(self, event):  # noqa: N802 (Qt naming)
        """Re-assert top-of-list scroll after Qt finishes laying out the
        sorted table.  Sorting + column auto-resizing can reset the
        vertical scrollbar after ``__init__`` runs, so we pin it to 0
        once the dialog is actually on screen."""
        super().showEvent(event)

        from PyQt6.QtCore import QTimer

        def _pin_to_top():
            try:
                self.table.scrollToTop()
                sb = self.table.verticalScrollBar()
                if sb is not None:
                    sb.setValue(0)
            except Exception:
                pass

        # Run twice: once at the end of this event-loop tick (after
        # layout), and once more on a short delay in case Qt issues a
        # deferred re-layout (e.g. ResizeToContents on column headers).
        QTimer.singleShot(0, _pin_to_top)
        QTimer.singleShot(50, _pin_to_top)

    def _select_by_name(self, name: str | None) -> None:
        if not name:
            # Fall back to first visible row
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    self.table.selectRow(r)
                    return
            return
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and item.text() == name:
                self.table.selectRow(r)
                # Do NOT scrollToItem here — the caller wants the first
                # rows visible, and scrollToTop() runs after this.
                return
        # Not found: select first visible
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                self.table.selectRow(r)
                return

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            name = item.text().lower() if item is not None else ""
            self.table.setRowHidden(r, bool(needle) and needle not in name)
        self._update_filter_count()
        # Ensure selection remains on a visible row
        cur = self.table.currentRow()
        if cur < 0 or self.table.isRowHidden(cur):
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    self.table.selectRow(r)
                    break

    def _update_filter_count(self) -> None:
        total = self.table.rowCount()
        visible = sum(1 for r in range(total) if not self.table.isRowHidden(r))
        self.lbl_filter_count.setText(f"{visible} of {total}")

    def _accept_selection(self) -> None:
        row = self.table.currentRow()
        if row < 0 or self.table.isRowHidden(row):
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        cand = item.data(self._ROLE_CANDIDATE)
        if isinstance(cand, dict):
            self._selected = cand
            self.accept()

    def selected_candidate(self) -> dict | None:
        return self._selected

    def _save_as_json(self) -> None:
        """Export the currently visible (filtered) rows as a JSON file."""
        headers = [self.table.horizontalHeaderItem(c).text()
                   for c in range(self.table.columnCount())]
        rows: list[dict] = []
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            name_item = self.table.item(r, 0)
            cand = (name_item.data(self._ROLE_CANDIDATE)
                    if name_item is not None else None)
            display: dict = {}
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                display[headers[c]] = it.text() if it is not None else ""
            entry = {"display": display}
            if isinstance(cand, dict):
                entry["candidate"] = {
                    k: (None if (isinstance(v, float)
                                 and v != v)  # NaN → null
                        else v)
                    for k, v in cand.items()
                }
            rows.append(entry)

        default_name = "target-candidates.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save candidates as JSON",
            default_name, "JSON files (*.json);;All files (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Save failed",
                                f"Could not write JSON file:\n{e}")
            return
        QMessageBox.information(
            self, "Saved",
            f"Wrote {len(rows)} candidate(s) to:\n{path}")


def identify_main_object(siril, wcs: WCS, img_w: int, img_h: int,
                         center_ra: float, center_dec: float,
                         fov_radius_deg: float, log_func=None
                         ) -> tuple[str | None, object]:
    """Return (object_name, simbad_row_like_result) or (None, None)."""
    # Strategy A: OBJECT keyword
    try:
        kw = siril.get_image_keywords()
        obj_name = ""
        if kw is not None:
            for attr in ("object", "OBJECT"):
                v = getattr(kw, attr, None)
                if v:
                    obj_name = str(v).strip()
                    break
    except Exception:
        obj_name = ""
    if obj_name:
        if log_func:
            log_func(f"OBJECT keyword: '{obj_name}'")
        result = _simbad_query_object(obj_name, log_func=log_func)
        if result is not None and len(result) > 0:
            return obj_name, result[0:1]
        # Trust the OBJECT keyword even if SIMBAD has no metadata for it:
        # downstream distance resolution will still try mesDistance / cache /
        # type-median, and the target picker lets the user override.
        if log_func:
            log_func(f"SIMBAD has no direct match for '{obj_name}'; "
                     "keeping it as the main target anyway.")
        return obj_name, None

    # Strategy B: SIMBAD cone search - brightest/main object
    try:
        custom = Simbad()
        custom.add_votable_fields("otype", "V")
        custom.ROW_LIMIT = 200
        center = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg)
        radius = Angle(max(0.01, min(fov_radius_deg, 1.5)), unit="deg")
        result = custom.query_region(center, radius=radius)
        if result is not None and len(result) > 0:
            id_col = next((c for c in result.colnames
                           if c.lower() == "main_id"), None)
            v_col = "V" if "V" in result.colnames else None
            otype_col = next((c for c in result.colnames
                              if c.lower() == "otype"), None)
            if id_col is not None:
                # Prefer bright, well-known prefixes (Messier/NGC/IC) then mag.
                preferred_prefixes = ("M ", "NGC", "IC ",
                                      "IC1", "IC2", "IC3", "IC4", "IC5")

                def _rank(row) -> tuple:
                    name = str(row[id_col]).strip()
                    mag = _safe_float(row[v_col], 99.0) if v_col else 99.0
                    pref = 0 if any(name.startswith(p)
                                    for p in preferred_prefixes) else 1
                    return (pref, mag)

                best = min(result, key=_rank)
                name = str(best[id_col]).strip()
                if log_func:
                    log_func(f"Cone-search best match: '{name}'")
                # Re-query to get full distance metadata.
                result = _simbad_query_object(name, log_func=log_func)
                if result is not None and len(result) > 0:
                    return name, result[0:1]
                return name, best
    except Exception as e:
        if log_func:
            log_func(f"Cone-search identification failed: {e}")

    return None, None


_SIMBAD_ID_ALLOWED = re.compile(r"^[A-Za-z0-9 _\-+*./\[\]()]{1,64}$")


def _sanitize_simbad_name(name: str) -> str | None:
    """Validate a user-provided SIMBAD identifier.

    astroquery's ``Simbad.query_tap`` doesn't expose ADQL bind
    parameters, so we reject anything outside a conservative
    identifier whitelist instead of trying to escape it.  Catalogue
    names like ``M 42``, ``NGC 1976``, ``HD 148937``, ``[VGC99] 4``,
    ``2MASS J17585508-2325268`` all fit.  Anything containing
    backslashes, NULs, control chars, or semicolons is refused.
    """
    if not isinstance(name, str):
        return None
    n = name.strip()
    if not n:
        return None
    # Reject control characters and NULs up front — the regex below
    # would anyway, but this makes the reason explicit in logs.
    if any(c < " " for c in n):
        return None
    if not _SIMBAD_ID_ALLOWED.match(n):
        return None
    return n


def query_mesdistance(name: str, log_func=None) -> dict | None:
    """Query SIMBAD mesDistance for a single object name. Returns dict or None."""
    try:
        safe = _sanitize_simbad_name(name)
        if safe is None:
            if log_func:
                log_func(
                    f"mesDistance: rejected non-whitelisted name "
                    f"{name!r}; skipping TAP query.")
            return None
        # Defense-in-depth: the whitelist already forbids "'", but keep
        # the SQL-style doubling in case the whitelist is ever widened.
        safe = safe.replace("'", "''")
        query = (
            "SELECT mesDistance.dist AS dist, mesDistance.unit AS unit, "
            "mesDistance.minus_err AS merr, mesDistance.plus_err AS perr, "
            "mesDistance.method AS method, mesDistance.bibcode AS bib "
            "FROM ident JOIN mesDistance ON "
            "ident.oidref = mesDistance.oidref "
            f"WHERE ident.id = '{safe}'"
        )
        tap_res = Simbad.query_tap(query)
        if tap_res is None or len(tap_res) == 0:
            return None
        best = None
        best_err = float("inf")
        for row in tap_res:
            dist_val = _safe_float(row["dist"])
            if not (dist_val and dist_val > 0):
                continue
            unit = str(row["unit"]) if row["unit"] is not None else "pc"
            merr = _safe_float(row["merr"], 0.0)
            perr = _safe_float(row["perr"], 0.0)
            err = max(abs(merr), abs(perr))
            if err == 0:
                err = dist_val * 0.1
            if err < best_err:
                best_err = err
                bib = (str(row["bib"])
                       if row["bib"] is not None else "")
                best = {
                    "dist_ly": to_ly(dist_val, unit),
                    "dist_err_ly": to_ly(err, unit),
                    "bibcode": bib,
                }
        return best
    except Exception as e:
        if log_func:
            log_func(f"mesDistance query failed: {e}")
        return None


def redshift_to_ly(z: float) -> float:
    dist_mpc = (z * C_KM_S) / HUBBLE_H0
    return dist_mpc * MPC_TO_LY / PC_TO_LY * PC_TO_LY  # = dist_mpc * MPC_TO_LY


def resolve_object_distance(name: str, obj_type: str,
                            simbad_result, cache: GalacticViewCache,
                            use_online: bool = True, log_func=None
                            ) -> tuple[float | None, float, str, str]:
    """
    Returns (dist_ly, dist_err_ly, source_label, confidence).
    confidence ∈ {'high', 'medium', 'low', 'none'}.
    """
    # 1. Cache
    cached = cache.get(name)
    if cached:
        if log_func:
            log_func(f"Distance: cache hit ({cached['dist_ly']:.0f} ly)")
        return (float(cached["dist_ly"]),
                float(cached.get("dist_err_ly", 0.0)),
                "Cache", cached.get("confidence", "high"))

    # 2. SIMBAD mesDistance
    if use_online:
        mesd = query_mesdistance(name, log_func=log_func)
        if mesd and mesd.get("dist_ly", 0) > 0:
            mode = decide_mode(mesd["dist_ly"], obj_type).value
            cache.set(name, mesd["dist_ly"], mesd["dist_err_ly"],
                      "SIMBAD", obj_type, mode,
                      bibcode=mesd.get("bibcode", ""), confidence="high")
            if log_func:
                log_func(f"Distance: SIMBAD "
                         f"({mesd['dist_ly']:.0f} ly, "
                         f"bib={mesd.get('bibcode', '')})")
            return (mesd["dist_ly"], mesd["dist_err_ly"],
                    "SIMBAD", "high")

    # 3. Redshift / radial velocity from simbad_result
    if simbad_result is not None:
        try:
            z = 0.0
            for col in ("Z_VALUE", "z_value"):
                if col in simbad_result.colnames:
                    z = _safe_float(simbad_result[col][0], 0.0)
                    break
            if z == 0.0:
                for col in ("RVZ_RADVEL", "rvz_radvel", "RV_VALUE"):
                    if col in simbad_result.colnames:
                        rv = _safe_float(simbad_result[col][0], 0.0)
                        if rv != 0:
                            z = rv / C_KM_S
                        break
            if 0 < z < 0.5:
                dist_mpc = (z * C_KM_S) / HUBBLE_H0
                dist_ly = dist_mpc * MPC_TO_LY
                err_ly = dist_ly * 0.15
                mode = decide_mode(dist_ly, obj_type).value
                cache.set(name, dist_ly, err_ly,
                          f"Redshift z={z:.4f}", obj_type, mode,
                          confidence="medium")
                if log_func:
                    log_func(f"Distance: redshift z={z:.4f} "
                             f"-> {dist_ly:.0f} ly")
                return dist_ly, err_ly, f"Redshift z={z:.4f}", "medium"
        except Exception as e:
            if log_func:
                log_func(f"Redshift fallback failed: {e}")

    # 4. Type-based median fallback
    fb = TYPE_DISTANCE_MEDIANS.get(obj_type)
    if fb is None:
        # Try broader mapping
        if obj_type in COSMIC_TYPES:
            fb = TYPE_DISTANCE_MEDIANS.get("Galaxy")
        elif obj_type in GALACTIC_TYPES:
            fb = TYPE_DISTANCE_MEDIANS.get("Neb")
    if fb:
        d, e = fb["dist_ly"], fb["spread_ly"]
        mode = decide_mode(d, obj_type).value
        cache.set(name, d, e, "Type-median (estimate)",
                  obj_type, mode, confidence="low")
        if log_func:
            log_func(f"Distance: type-median estimate "
                     f"({d:.0f} ly, type={obj_type})")
        return d, e, "Type-median (estimate)", "low"

    if log_func:
        log_func("Distance: unknown")
    return None, 0.0, "unknown", "none"


# ---------------------------------------------------------------------------
# Photo texture and 3D corners
# ---------------------------------------------------------------------------
def autostretch_for_texture(img: np.ndarray,
                            low_pct: float = 0.5,
                            high_pct: float = 99.5) -> np.ndarray:
    lo = float(np.percentile(img, low_pct))
    hi = float(np.percentile(img, high_pct))
    if hi <= lo:
        hi = lo + 1.0
    out = np.clip((img - lo) / (hi - lo + 1e-10), 0.0, 1.0)
    return out


def prepare_texture_array(image_data: np.ndarray,
                          max_size: int = 256) -> np.ndarray:
    """Return a (H, W, 3) uint8 auto-stretched thumbnail."""
    img = image_data
    if img.dtype != np.float32 and img.dtype != np.float64:
        img = img.astype(np.float32) / 255.0 if img.dtype == np.uint8 else img.astype(np.float32)
    stretched = autostretch_for_texture(img)
    u8 = (stretched * 255.0).astype(np.uint8)
    if u8.ndim == 2:
        u8 = np.stack([u8] * 3, axis=-1)
    elif u8.ndim == 3 and u8.shape[2] == 1:
        u8 = np.repeat(u8, 3, axis=2)
    # Downsample
    if HAS_PIL:
        try:
            pil = Image.fromarray(u8, "RGB")
            pil.thumbnail((max_size, max_size), _PIL_LANCZOS)
            u8 = np.array(pil, dtype=np.uint8)
        except Exception as e:
            # Fall back to nearest-neighbour numpy stride (below), but at
            # least surface the reason on stderr — a bad Pillow install or
            # unexpected dtype would otherwise look like a silent quality
            # regression.
            sys.stderr.write(
                f"[GalacticView3D] PIL thumbnail failed ({e}); "
                "using stride fallback.\n")
            h, w = u8.shape[:2]
            step_y = max(1, h // max_size)
            step_x = max(1, w // max_size)
            u8 = u8[::step_y, ::step_x]
    else:
        h, w = u8.shape[:2]
        step_y = max(1, h // max_size)
        step_x = max(1, w // max_size)
        u8 = u8[::step_y, ::step_x]
    return u8


def build_photo_pixel_grid(texture_u8: np.ndarray,
                           corners: list[tuple[float, float, float]],
                           ) -> dict | None:
    """Project a downsampled image onto the photo rectangle as coloured points.

    ``corners`` are in order TL, TR, BR, BL. Returns a dict with lists
    ``x``, ``y``, ``z``, ``colors`` (hex strings) suitable for a single
    ``go.Scatter3d`` marker trace. Plotly has no native UV-mapped textures
    for 3D meshes, so each pixel becomes a tiny coloured marker at its
    bilinearly interpolated position on the quad.
    """
    if (texture_u8 is None or texture_u8.ndim != 3
            or texture_u8.shape[2] < 3
            or not corners or len(corners) != 4):
        return None
    tl = np.asarray(corners[0], dtype=np.float64)
    tr = np.asarray(corners[1], dtype=np.float64)
    br = np.asarray(corners[2], dtype=np.float64)
    bl = np.asarray(corners[3], dtype=np.float64)

    h, w = texture_u8.shape[:2]
    # u goes left->right (0..1), v goes top->bottom (0..1)
    us = (np.arange(w) + 0.5) / w
    vs = (np.arange(h) + 0.5) / h
    uu, vv = np.meshgrid(us, vs)  # shape (h, w)

    # Bilinear interpolation across the quad (TL, TR, BR, BL)
    top = tl[None, None, :] * (1 - uu)[..., None] + tr[None, None, :] * uu[..., None]
    bot = bl[None, None, :] * (1 - uu)[..., None] + br[None, None, :] * uu[..., None]
    pts = top * (1 - vv)[..., None] + bot * vv[..., None]  # (h, w, 3)

    # Return numpy arrays (not .tolist()) for x/y/z: Plotly's internal
    # `_validate_coerce_fraction` has a fast path for numpy numeric
    # arrays that skips the per-element PyFloat→float unbox that the
    # list-of-Python-floats path triggers.  At 480×480 that's ~230k
    # elements per axis saved.
    xs = np.ascontiguousarray(pts[..., 0].ravel())
    ys = np.ascontiguousarray(pts[..., 1].ravel())
    zs = np.ascontiguousarray(pts[..., 2].ravel())

    # Hex conversion hot path.  At PHOTO_DEFAULT_PX=480 this loop runs
    # ~230k times per render; the naive
    #   "#{:02x}{:02x}{:02x}".format(r, g, b)
    # form spends ~200 ms of pure Python formatting.  bytes.hex() does
    # the hex encoding in one C call, then we slice out 6-char chunks
    # and prepend "#" — roughly 4-5× faster on measured workloads.
    # NB: we *tried* a vectorised numpy |S7→<U7 view in an earlier pass;
    # benchmarking at 230k elements showed it was slightly *slower* than
    # the CPython list-slice specialisation (~28ms vs ~25ms), and Plotly
    # iterates string arrays element-by-element during JSON-serialisation
    # either way.  Keep the list form — it's the fastest we measured.
    rgb = texture_u8[..., :3].reshape(-1, 3)
    if rgb.dtype != np.uint8:
        rgb = rgb.astype(np.uint8, copy=False)
    else:
        rgb = np.ascontiguousarray(rgb)
    hex_flat = rgb.tobytes().hex()
    colors = ["#" + hex_flat[i:i + 6]
              for i in range(0, len(hex_flat), 6)]
    return {"x": xs, "y": ys, "z": zs, "colors": colors,
            "w": w, "h": h}


def build_photo_texture_mesh(corners: list[tuple[float, float, float]],
                             texture_u8: np.ndarray,
                             subdiv: int | None = None) -> dict | None:
    """Build a subdivided ``Mesh3d`` quad with per-face colours sampled
    from ``texture_u8``.

    This is the **primary** visual representation of the astrophoto in
    3D — a single WebGL draw call (one Mesh3d trace, a few thousand
    flat-shaded triangles) that reads as a continuous textured surface.
    It replaces the legacy per-pixel Scatter3d grid which dumped
    ~150–230k markers into the scene and rendered as a pointillist
    cloud rather than an image.

    Plotly 3D has no UV texture mapping on meshes, so the texture is
    baked in as a ``facecolor`` list (one hex string per triangle).
    Subdividing the quad beyond the texture's cell count adds no
    detail, so ``subdiv`` is auto-clamped to ~1 cell per source
    pixel (minimum 8).

    ``corners`` are in order TL, TR, BR, BL (matching
    :func:`get_photo_corners_3d`).  Returns a dict ready to splat
    straight into ``go.Mesh3d(**dict)``:

        x, y, z   — flat vertex lists
        i, j, k   — triangle index lists
        facecolor — hex string per triangle
        nx, ny    — grid resolution (for logging / diagnostics)
    """
    if (texture_u8 is None or texture_u8.ndim != 3
            or texture_u8.shape[2] < 3
            or not corners or len(corners) != 4):
        return None
    h_px, w_px = texture_u8.shape[:2]
    if subdiv is None:
        # Cap at ~96 cells per long axis → <= ~18k tris, well within
        # WebGL's fast path, and visually indistinguishable from the
        # texture resolution because cells are flat-shaded anyway.
        subdiv = min(96, max(8, max(w_px, h_px) // 4))
    nx = max(2, int(subdiv))
    # Preserve the texture's aspect ratio on the grid so square pixels
    # stay square.
    ny = max(2, int(round(nx * (h_px / max(1, w_px)))))

    tl = np.asarray(corners[0], dtype=np.float64)
    tr = np.asarray(corners[1], dtype=np.float64)
    br = np.asarray(corners[2], dtype=np.float64)
    bl = np.asarray(corners[3], dtype=np.float64)

    # Vertex grid: (ny+1) rows × (nx+1) cols.
    us = np.linspace(0.0, 1.0, nx + 1)
    vs = np.linspace(0.0, 1.0, ny + 1)
    uu, vv = np.meshgrid(us, vs)  # (ny+1, nx+1)
    top = (tl[None, None, :] * (1 - uu)[..., None]
           + tr[None, None, :] * uu[..., None])
    bot = (bl[None, None, :] * (1 - uu)[..., None]
           + br[None, None, :] * uu[..., None])
    verts = top * (1 - vv)[..., None] + bot * vv[..., None]

    xs = verts[..., 0].ravel().tolist()
    ys = verts[..., 1].ravel().tolist()
    zs = verts[..., 2].ravel().tolist()

    # Triangulate: each (r, c) grid cell → 2 triangles.
    # Vertex index at (row, col) = row * (nx + 1) + col.
    def vi(r: int, c: int) -> int:
        return r * (nx + 1) + c

    i_idx: list[int] = []
    j_idx: list[int] = []
    k_idx: list[int] = []
    for r in range(ny):
        for c in range(nx):
            v00 = vi(r, c)
            v01 = vi(r, c + 1)
            v10 = vi(r + 1, c)
            v11 = vi(r + 1, c + 1)
            # Triangle 1: TL, TR, BR
            i_idx.append(v00)
            j_idx.append(v01)
            k_idx.append(v11)
            # Triangle 2: TL, BR, BL
            i_idx.append(v00)
            j_idx.append(v11)
            k_idx.append(v10)

    # Sample cell-centre colours from the texture.
    u_cells = (np.arange(nx) + 0.5) / nx
    v_cells = (np.arange(ny) + 0.5) / ny
    tex_cols = np.clip((u_cells * w_px).astype(int), 0, w_px - 1)
    tex_rows = np.clip((v_cells * h_px).astype(int), 0, h_px - 1)
    rgb = texture_u8[tex_rows[:, None], tex_cols[None, :], :3]
    if rgb.dtype != np.uint8:
        rgb = rgb.astype(np.uint8, copy=False)
    rgb_flat = np.ascontiguousarray(rgb.reshape(-1, 3))
    # Same bytes.hex() trick as build_photo_pixel_grid — one C call,
    # then slice into 6-char chunks.
    hex_flat = rgb_flat.tobytes().hex()
    cell_colors = ["#" + hex_flat[i:i + 6]
                   for i in range(0, len(hex_flat), 6)]
    # Two triangles per cell — both take the same colour so the quad
    # reads as a single flat-shaded pixel.
    facecolor: list[str] = []
    for col in cell_colors:
        facecolor.append(col)
        facecolor.append(col)

    return {
        "x": xs, "y": ys, "z": zs,
        "i": i_idx, "j": j_idx, "k": k_idx,
        "facecolor": facecolor,
        "nx": nx, "ny": ny,
    }


def texture_to_base64_png(u8: np.ndarray) -> str | None:
    if not HAS_PIL:
        return None
    try:
        pil = Image.fromarray(u8, "RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        return ("data:image/png;base64,"
                + base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return None


def _bilinear_on_quad(corners: list[tuple[float, float, float]],
                      u: float, v: float
                      ) -> tuple[float, float, float]:
    """Bilinear interpolate a point on the TL,TR,BR,BL quad.

    ``u`` in [0,1] runs left→right, ``v`` in [0,1] runs top→bottom.
    """
    tl, tr, br, bl = corners
    top = (tl[0]*(1-u) + tr[0]*u,
           tl[1]*(1-u) + tr[1]*u,
           tl[2]*(1-u) + tr[2]*u)
    bot = (bl[0]*(1-u) + br[0]*u,
           bl[1]*(1-u) + br[1]*u,
           bl[2]*(1-u) + br[2]*u)
    return (top[0]*(1-v) + bot[0]*v,
            top[1]*(1-v) + bot[1]*v,
            top[2]*(1-v) + bot[2]*v)


def build_background_pins(siril, img_w: int, img_h: int,
                          photo_corners: list[tuple[float, float, float]],
                          picked_dist_ly: float,
                          candidates: list[dict],
                          picked_name: str,
                          mode: ViewMode,
                          log_func=None,
                          wcs: WCS | None = None) -> list[dict]:
    """Push-pin markers for candidates BEHIND the main target.

    Filtering rules:
      * distance must be > picked target's distance (so the pin sits
        behind the image plane and a depth stick makes sense);
      * distance must be within a **log-distance window** of the main
        target (the user works in log-space, so "nearby" means close
        in decades, not in absolute light-years).  The window is
        wider in cosmic mode, where distances can span many orders
        of magnitude, and narrower in galactic mode.

    Each returned dict has:
        name       — display name
        anchor_xyz — 3D point on the photo plane at the object's pixel
        target_xyz — 3D point at the object's actual galactic position
        dist_ly    — the object's distance
        otype      — SIMBAD object type
    """
    if (not candidates or not photo_corners or len(photo_corners) != 4
            or img_w <= 0 or img_h <= 0 or siril is None
            or not (picked_dist_ly == picked_dist_ly) or picked_dist_ly <= 0):
        return []

    # The log-distance upper bound (formerly `picked × 10^N decades`)
    # has been removed.  Objects arbitrarily far behind the photo now
    # get pins too — distant background galaxies that previously fell
    # outside the window are now drawn at their real depth.  The
    # log_window constants (LOG_WINDOW_COSMIC / LOG_WINDOW_GALACTIC)
    # remain in the module in case anyone ever wants the cap back.

    # ---- Batch WCS pixel pre-compute (B7) ---------------------------
    # If a WCS is available, convert every candidate's (ra, dec) to
    # pixel in ONE vectorized call instead of N per-candidate Siril
    # round-trips. This is dramatically faster for large candidate
    # lists (cosmic mode can have 10k+ entries).
    #
    # When WCS is absent we fall back to the per-row siril.radec2pix
    # path.  Entries that failed the vectorized call (NaN) are re-
    # tried individually.
    batch_pix: dict[int, tuple[float, float] | None] = {}
    if wcs is not None and candidates:
        try:
            ras_arr = np.array(
                [float(c.get("ra", float("nan"))) for c in candidates],
                dtype=np.float64,
            )
            decs_arr = np.array(
                [float(c.get("dec", float("nan"))) for c in candidates],
                dtype=np.float64,
            )
            pix_arr = wcs.all_world2pix(
                np.column_stack([ras_arr, decs_arr]), 0
            )
            for i in range(len(candidates)):
                pxv = pix_arr[i, 0]
                pyv = pix_arr[i, 1]
                if math.isfinite(pxv) and math.isfinite(pyv):
                    batch_pix[i] = (float(pxv), float(pyv))
                else:
                    batch_pix[i] = None
        except Exception as e:
            if log_func:
                log_func(f"WCS batch pix failed, falling back: {e}")
            batch_pix = {}

    # ---- Photo plane geometry (for radial anchor intersection) ----
    # The visible photo rectangle has been enlarged from its true
    # angular size for visibility (see get_photo_corners_3d's
    # min_visual_size).  If we anchor each pin via bilinear pixel
    # interpolation INSIDE that enlarged quad, anchors near the photo
    # edges are pulled outward — they no longer lie on the same
    # radial line from Earth as the object's true RA/Dec direction,
    # and the depth sticks come out diagonal instead of radial.
    #
    # Fix: ray-cast from Earth (origin) along the object's true
    # direction-of-arrival onto the photo's plane.  The resulting
    # anchor sits on the visible rectangle AND on the same radial
    # line as the target, so the stick is perfectly radial.
    photo_plane: tuple | None = None
    try:
        c0 = np.asarray(photo_corners[0], dtype=np.float64)  # TL
        c1 = np.asarray(photo_corners[1], dtype=np.float64)  # TR
        c3 = np.asarray(photo_corners[3], dtype=np.float64)  # BL
        edge_u = c1 - c0   # TL → TR
        edge_v = c3 - c0   # TL → BL
        normal = np.cross(edge_u, edge_v)
        n_len = float(np.linalg.norm(normal))
        if n_len > 1e-9:
            normal /= n_len
            # The plane passes through any corner; cache
            # plane_d = corner · normal so the ray-cast is just
            # t = plane_d / (d_hat · normal).
            plane_d = float(np.dot(c0, normal))
            photo_plane = (normal, plane_d)
    except Exception as e:
        if log_func:
            log_func(f"Photo-plane build failed, falling back to "
                     f"bilinear anchors: {e}")
        photo_plane = None

    def _radial_anchor(target_xyz: tuple[float, float, float]
                        ) -> tuple[float, float, float] | None:
        """Intersect ray (origin → target_xyz) with the photo plane.

        Returns the 3D point on the plane, or None if the geometry is
        degenerate (ray parallel to plane, or anchor would land
        behind Earth).
        """
        if photo_plane is None:
            return None
        n, pd = photo_plane
        d_vec = np.asarray(target_xyz, dtype=np.float64)
        d_norm = float(np.linalg.norm(d_vec))
        if d_norm < 1e-9:
            return None
        d_hat = d_vec / d_norm
        denom = float(np.dot(d_hat, n))
        if abs(denom) < 1e-9:
            return None  # ray parallel to plane
        t = pd / denom
        if t <= 0.0:
            return None  # plane is "behind" the camera
        p = d_hat * t
        return (float(p[0]), float(p[1]), float(p[2]))

    pins: list[dict] = []
    skipped_closer = skipped_no_pix = skipped_outside = 0
    for idx, c in enumerate(candidates):
        if c.get("name") == picked_name:
            continue
        d = c.get("dist_ly_estimate", float("nan"))
        if not (d == d) or d <= picked_dist_ly:
            skipped_closer += 1
            continue
        ra = c.get("ra")
        dec = c.get("dec")
        if ra is None or dec is None or ra != ra or dec != dec:
            continue
        # Prefer the batch pixel coord if we have one; otherwise ask Siril.
        px_res = batch_pix.get(idx) if batch_pix else None
        if px_res is None:
            try:
                px_res = siril.radec2pix(float(ra), float(dec))
            except Exception as e:
                if log_func:
                    log_func(
                        f"skipped {c.get('name','?')}: radec2pix failed ({e})"
                    )
                px_res = None
        if px_res is None:
            skipped_no_pix += 1
            continue
        try:
            px, py = float(px_res[0]), float(px_res[1])
        except Exception as e:
            if log_func:
                log_func(f"skipped {c.get('name','?')}: bad pixel tuple ({e})")
            continue
        if not (0 <= px <= img_w and 0 <= py <= img_h):
            skipped_outside += 1
            continue
        l_deg, b_deg = radec_to_galactic(float(ra), float(dec))
        target = gal_to_xyz(l_deg, b_deg, scale_dist(float(d), mode))
        # Radial anchor: intersect (Earth → target) with the photo
        # plane.  Falls back to the legacy bilinear anchor if the
        # plane geometry is degenerate or the ray misses behind us.
        anchor = _radial_anchor(target)
        if anchor is None:
            u = px / float(img_w)
            v = py / float(img_h)
            anchor = _bilinear_on_quad(photo_corners, u, v)
        pins.append({
            "name": c.get("name", "?"),
            "anchor_xyz": anchor,
            "target_xyz": target,
            "dist_ly": float(d),
            "otype": c.get("otype", ""),
            "dist_source_hint": c.get("dist_source_hint", ""),
        })
    if log_func:
        log_func(
            f"Background pins: {len(pins)} "
            f"(picked {picked_dist_ly:,.0f} ly; "
            f"no upper-distance cap; skipped "
            f"{skipped_closer} not-behind, "
            f"{skipped_no_pix} no-pix, "
            f"{skipped_outside} outside-frame)."
        )
    return pins


def get_photo_corners_3d(siril, w: int, h: int,
                         dist_ly: float, mode: ViewMode,
                         min_visual_size: float | None = None,
                         ) -> list[tuple[float, float, float]]:
    """Project 4 image corners to 3D. Order: TL, TR, BR, BL.

    The true angular extent of an astrophoto (typically <1°) projects to a
    rectangle far too small to see at galactic/cosmic scale. If
    ``min_visual_size`` is given, the rectangle is uniformly enlarged around
    its centroid so that its longest edge reaches that size (in scene units).
    This is a visualization aid — the orientation and aspect ratio of the
    frame are preserved.
    """
    d = scale_dist(dist_ly, mode)
    raw: list[tuple[float, float, float]] = []
    for px, py in [(0, 0), (w, 0), (w, h), (0, h)]:
        try:
            ra, dec = siril.pix2radec(px, py)
        except Exception:
            ra, dec = None, None
        if ra is None or dec is None:
            raw.append((0.0, 0.0, 0.0))
            continue
        l_deg, b_deg = radec_to_galactic(float(ra), float(dec))
        raw.append(gal_to_xyz(l_deg, b_deg, d))

    if min_visual_size is None or min_visual_size <= 0:
        return raw

    # Default fallback if any corner projection failed
    if any(c == (0.0, 0.0, 0.0) for c in raw):
        return raw

    cx = sum(c[0] for c in raw) / 4.0
    cy = sum(c[1] for c in raw) / 4.0
    cz = sum(c[2] for c in raw) / 4.0

    def _edge(a, b):
        return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

    longest = max(_edge(raw[0], raw[1]), _edge(raw[1], raw[2]),
                  _edge(raw[2], raw[3]), _edge(raw[3], raw[0]))
    if longest <= 0:
        return raw
    if longest >= min_visual_size:
        return raw

    scale = min_visual_size / longest
    return [(cx + (c[0]-cx) * scale,
             cy + (c[1]-cy) * scale,
             cz + (c[2]-cz) * scale) for c in raw]


def build_viewing_ray_cues(photo_center: tuple[float, float, float],
                           dist_ly: float, mode: ViewMode,
                           n_gradient: int = 40) -> dict:
    """Depth cues along the Earth → target line of sight:

      * a gradient of small markers (bright near Earth, dim at the
        photo plane) so the line reads as depth, not just a line;
      * log-decade reference ticks (100 ly / 1 kly / 10 kly / ...) with
        short text labels — the single most informative feature for
        communicating scale without a dedicated axis.

    Returns a dict of pre-computed arrays:
      ``grad_x/y/z/colors`` for the gradient markers,
      ``tick_x/y/z/labels``  for the decade ticks.
    """
    px, py, pz = (float(photo_center[0]),
                  float(photo_center[1]),
                  float(photo_center[2]))
    vec = np.array([px, py, pz], dtype=float)
    mag = float(np.linalg.norm(vec))
    if mag < 1e-9:
        return {"grad_x": [], "grad_y": [], "grad_z": [], "grad_colors": [],
                "tick_x": [], "tick_y": [], "tick_z": [], "tick_labels": []}
    unit = vec / mag

    # Gradient: t in [0.02, 0.98] so markers don't sit exactly on
    # Earth or the photo centre and fight with those markers.
    ts = np.linspace(0.02, 0.98, n_gradient)
    pts = ts[:, None] * vec[None, :]
    # Brightness interpolates amber (near) → deep violet (far).
    # Using the linear t along the ray is the right depth cue: the
    # user's eye reads the colour transition as "far away".
    def _blend(t: float) -> str:
        # (near_rgb) → (far_rgb).  Stay in warm→cool.
        near = (255, 214, 102)    # warm amber
        far = (80, 60, 140)       # deep violet
        r = int(round(near[0] * (1 - t) + far[0] * t))
        g = int(round(near[1] * (1 - t) + far[1] * t))
        b = int(round(near[2] * (1 - t) + far[2] * t))
        return f"rgb({r},{g},{b})"
    grad_colors = [_blend(float(t)) for t in ts]

    # Log-decade ticks.  We convert each log-decade light-year distance
    # into a scene-unit distance, then walk along the ray until we pass
    # the photo's position.
    if dist_ly and dist_ly > 0:
        if mode is ViewMode.GALACTIC:
            decade_ly = [100, 1_000, 10_000]
        else:
            decade_ly = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9]
    else:
        decade_ly = []
    tick_x, tick_y, tick_z, tick_labels = [], [], [], []
    for d_ly in decade_ly:
        d_scene = scale_dist(d_ly, mode)
        if d_scene >= mag * 0.98:
            break  # past the photo centre — skip
        p = unit * d_scene
        tick_x.append(float(p[0]))
        tick_y.append(float(p[1]))
        tick_z.append(float(p[2]))
        tick_labels.append(_format_ly_label(d_ly))

    return {
        "grad_x": pts[:, 0].tolist(),
        "grad_y": pts[:, 1].tolist(),
        "grad_z": pts[:, 2].tolist(),
        "grad_colors": grad_colors,
        "tick_x": tick_x,
        "tick_y": tick_y,
        "tick_z": tick_z,
        "tick_labels": tick_labels,
    }


def _textposition_for(x: float, y: float, z: float) -> str:
    """Pick a Plotly 3D ``textposition`` for a labelled marker that
    biases the label **away from the scene origin** (Earth).  This
    avoids a cluster of labels all saying ``"top center"`` and
    overlapping near the galactic centre.

    It's not a true collision solver, but it reliably spreads labels
    across the four screen-space quadrants based on where each marker
    sits relative to the origin — a major readability win in dense
    scenes without any JS/relayout machinery.
    """
    # Horizontal bias: +x goes right; −x goes left.
    horiz = "right" if x >= 0 else "left"
    # Vertical bias: above the galactic plane → top; below → bottom.
    if z > 0.25:
        vert = "top"
    elif z < -0.25:
        vert = "bottom"
    else:
        # In the plane: use y as the tiebreaker so labels don't all
        # stack on the same row.
        vert = "top" if y >= 0 else "bottom"
    return f"{vert} {horiz}"


# ---------------------------------------------------------------------------
# Plotly figure builder
# ---------------------------------------------------------------------------
def build_galaxy_figure(scene: dict) -> object:
    """Build the interactive 3D Plotly figure for the Milky Way + photo.

    Trace z-order (earliest = drawn first = visually behind):
      1. Galactic-plane mesh   (very faint, gives arms a surface)
      2. Distance rings         (reference scale)
      3. Compass rose           (origin-centred direction arrows)
      4. Disk stars + bulge     (Milky-Way structure)
      5. Spiral arms            (main visible structure)
      6. Sgr A* + Earth         (anchor points)
      7. Neighbor galaxies      (cosmic mode)
      8. Photo pixel-grid + frame + viewing-ray depth cues
      9. Background push-pin markers

    Legend is grouped so the user reads it like a table of contents
    (``Milky Way`` / ``References`` / ``Target`` / ``Background``)
    instead of a flat dump of every trace.
    """
    if not HAS_PLOTLY:
        return None
    mode: ViewMode = scene["mode"]
    show_neighbors = scene.get("show_neighbors",
                               mode is ViewMode.COSMIC)

    # P4.12 — apply the chosen distance metric for the entire render
    # pass.  scale_dist() consults this global, so all 3D positions
    # (and any pre-computed photo_center / pin xyz that came from
    # data-pipeline scale_dist calls) honour the metric.  Reset on
    # the way out so an exception or a parallel call doesn't leak
    # the setting.
    global _ACTIVE_DISTANCE_METRIC
    _prev_metric = _ACTIVE_DISTANCE_METRIC
    _ACTIVE_DISTANCE_METRIC = scene.get(
        "distance_metric", "light-travel")

    fig = go.Figure()
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    photo_center_pre = scene.get("photo_center_xyz")

    # --- 1. Galactic-plane mesh (translucent annulus) ---
    # Gives the eye a surface for the arms to sit on.  In galactic mode
    # only — in cosmic mode the scale compression makes the plane look
    # like a tiny disk at the origin, which is misleading.  Suppressed
    # when the spiral-arm overlay is on: the arms already imply the
    # disk, and the redundant tinted rectangle just adds visual noise.
    if (mode is ViewMode.GALACTIC and scene.get("show_disk", True)
            and not scene.get("show_arms", True)):
        try:
            plane = build_disk_plane_mesh(mode)
            fig.add_trace(go.Mesh3d(
                x=plane["x"], y=plane["y"], z=plane["z"],
                i=plane["i"], j=plane["j"], k=plane["k"],
                # Radial gradient (P3.8): brightest near the bulge,
                # fades to near-black at the disk edge.  Reads as
                # "this is a disk" rather than a flat rectangle.
                intensity=plane["intensity"],
                colorscale=[[0.0, "rgba(15,20,35,0.0)"],
                            [1.0, "rgba(80,110,160,1.0)"]],
                opacity=0.18,
                name="Galactic plane",
                hoverinfo="skip", showscale=False, showlegend=False,
                legendgroup="milkyway",
            ))
        except Exception:
            pass

    # --- 2. Distance rings (scale reference) ---
    if scene.get("show_disk", True):
        try:
            rings = build_distance_rings(mode)
            # Pre-compute phi samples once — reused for the two
            # vertical great circles added below to give each ring
            # a "spherical wireframe" feel rather than a flat disk.
            _phis_3d = np.linspace(0, 2 * math.pi, 120)
            _cos_phi = np.cos(_phis_3d)
            _sin_phi = np.sin(_phis_3d)
            for ring in rings:
                # P1.4 — append redshift + lookback time to cosmic-mode
                # ring hovers (and the +x labels).  Galactic-mode rings
                # are well within the Milky Way; z and lookback there
                # are essentially zero and would just clutter the
                # tooltip, so the annotation is gated to cosmic mode.
                if mode is ViewMode.COSMIC:
                    z_ring, lb_ring = estimate_z_and_lookback(
                        float(ring["r_ly"]))
                    z_str = (f"{z_ring:.4f}" if z_ring < 0.01
                             else f"{z_ring:.3f}" if z_ring < 1.0
                             else f"{z_ring:.2f}")
                    lb_str = (f"{lb_ring*1000:.0f} Myr"
                              if lb_ring < 1.0
                              else f"{lb_ring:.2f} Gyr")
                    cosmic_tag = (f"<br>z ≈ {z_str} · "
                                  f"lookback {lb_str}")
                    label_tag = f" · z≈{z_str}"
                else:
                    cosmic_tag = ""
                    label_tag = ""
                # Three orthogonal great circles per ring radius:
                #   • horizontal (z = 0)         ← original
                #   • vertical, y = 0            ← new (z up, x out)
                #   • vertical, x = center_x     ← new (z up, y out)
                # Concatenated into one Scatter3d trace via None
                # separators — keeps trace count the same as before
                # while making the rings read as spherical shells.
                _r_s = ring["r_scene"]
                _cx_s = ring["center_x"]
                # Horizontal (z = 0)
                rxs: list[float | None] = list(ring["x"])
                rys: list[float | None] = list(ring["y"])
                rzs: list[float | None] = list(ring["z"])
                rxs.append(None); rys.append(None); rzs.append(None)
                # Vertical 1: y = 0 plane, ring spans (x − center_x, z)
                rxs.extend((_cx_s + _r_s * _cos_phi).tolist())
                rys.extend([0.0] * len(_phis_3d))
                rzs.extend((_r_s * _sin_phi).tolist())
                rxs.append(None); rys.append(None); rzs.append(None)
                # Vertical 2: x = center_x plane, ring spans (y, z)
                rxs.extend([_cx_s] * len(_phis_3d))
                rys.extend((_r_s * _cos_phi).tolist())
                rzs.extend((_r_s * _sin_phi).tolist())
                fig.add_trace(go.Scatter3d(
                    x=rxs, y=rys, z=rzs,
                    mode="lines",
                    line=dict(color="rgba(136,170,200,0.25)",
                              width=1, dash="dot"),
                    name=f"Ring: {ring['label']}",
                    hovertext=(f"{ring['label']} from "
                               + ("Galactic Center"
                                  if mode is ViewMode.GALACTIC
                                  else "Earth")
                               + cosmic_tag),
                    hoverinfo="text",
                    showlegend=False,
                    legendgroup="references",
                ))
                # A tiny label anchored at (+x) of each ring, tucked at
                # z=0.  Readable at a glance, doesn't clutter the legend.
                fig.add_trace(go.Scatter3d(
                    x=[ring["center_x"] + ring["r_scene"] * 1.01],
                    y=[0.0], z=[0.0],
                    mode="text",
                    text=[ring["label"] + label_tag],
                    textposition="middle right",
                    textfont=dict(color="rgba(170,190,220,0.55)",
                                  size=9),
                    name=f"Ring label: {ring['label']}",
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="references",
                ))
        except Exception:
            pass

    # --- 2a. Log-compression boundary (cosmic mode, 1 Mly) ---
    # `scale_dist` is linear inside 1 Mly, log-compressed beyond.
    # Without a marker the discontinuity is invisible; the user has
    # no way to know that "10 cm of screen here" represents a
    # different physical distance than "10 cm of screen there".
    # Render a faint extra-wide ring at exactly 1 Mly, double-dashed
    # so it reads as "this line is structural", with a label.
    if mode is ViewMode.COSMIC and scene.get("show_disk", True):
        try:
            r_boundary = scale_dist(1e6, mode)   # = 10.0 scene units
            phis = np.linspace(0, 2 * math.pi, 120)
            cos_b_p = np.cos(phis)
            sin_b_p = np.sin(phis)
            n_pts = len(phis)
            # Three-circle wireframe to match the rest of the
            # distance-ring set (horizontal + 2 verticals).
            xs_b: list[float | None] = (r_boundary * cos_b_p).tolist()
            ys_b: list[float | None] = (r_boundary * sin_b_p).tolist()
            zs_b: list[float | None] = [0.0] * n_pts
            xs_b.append(None); ys_b.append(None); zs_b.append(None)
            xs_b.extend((r_boundary * cos_b_p).tolist())
            ys_b.extend([0.0] * n_pts)
            zs_b.extend((r_boundary * sin_b_p).tolist())
            xs_b.append(None); ys_b.append(None); zs_b.append(None)
            xs_b.extend([0.0] * n_pts)
            ys_b.extend((r_boundary * cos_b_p).tolist())
            zs_b.extend((r_boundary * sin_b_p).tolist())
            fig.add_trace(go.Scatter3d(
                x=xs_b, y=ys_b, z=zs_b,
                mode="lines",
                line=dict(color="rgba(255,170,100,0.45)",
                          width=2, dash="longdashdot"),
                name="Scale boundary: 1 Mly",
                hovertext=("Scale-compression boundary.<br>"
                           "Inside this ring: linear scale.<br>"
                           "Outside: logarithmic compression "
                           "(1 ring = 1 decade)."),
                hoverinfo="text",
                showlegend=False,
                legendgroup="references",
            ))
            # Single label tucked at +x, above the disk so it doesn't
            # collide with the regular ring labels along z=0.
            fig.add_trace(go.Scatter3d(
                x=[r_boundary * 1.02],
                y=[0.0],
                z=[r_boundary * 0.06],
                mode="text",
                text=["1 Mly · linear/log boundary"],
                textposition="middle right",
                textfont=dict(color="rgba(255,170,100,0.75)",
                              size=9),
                name="Scale boundary label",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="references",
            ))
        except Exception:
            pass

    # --- 2c. CMB / observable-universe edge (cosmic mode) ---
    # The cosmic microwave background's last-scattering surface sits
    # at z ≈ 1100 / lookback ≈ 13.8 Gyr, the practical edge of the
    # observable universe in light-travel distance.  A solid mesh
    # sphere there would dominate the scene (scene radius ≈ 43 units
    # vs. ±50 typical extent), so we draw it as a sparse wireframe:
    # one bright equatorial great circle + four faint latitude rings
    # at b = ±30°, ±60°.  Reads as "spherical boundary" without
    # eating the visual budget.
    if mode is ViewMode.COSMIC and scene.get("show_cmb", True):
        try:
            r_cmb = scale_dist(13.8e9, mode)
            # Spherical shape — physically honest.  The observable
            # universe is isotropic by construction in standard
            # ΛCDM cosmology, so the CMB last-scattering surface is
            # genuinely the same distance away in every direction.
            # The (ax_x, ax_y, ax_z) triplet is kept so that all
            # CMB visuals (rings, meridians, stylized texture mesh)
            # share a single shape definition; tweak the ratios if
            # you ever want a stylized non-spherical shape.
            ax_x, ax_y, ax_z = r_cmb * 1.0, r_cmb * 1.0, r_cmb * 1.0
            n_phi = 120   # was 240 — half the points, no visible
                          # difference at the CMB radius (~6° per
                          # chord is well below screen-pixel limit)
            phis = np.linspace(0, 2 * math.pi, n_phi)
            cos_p = np.cos(phis); sin_p = np.sin(phis)
            # Equatorial circle (b = 0) — the "headline" ring.
            fig.add_trace(go.Scatter3d(
                x=(ax_x * cos_p).tolist(),
                y=(ax_y * sin_p).tolist(),
                z=[0.0] * n_phi,
                mode="lines",
                line=dict(color="rgba(255,200,140,0.55)",
                          width=2, dash="dot"),
                name="CMB last-scattering (z ≈ 1100, 13.8 Gyr)",
                hovertext=("Cosmic Microwave Background — "
                           "last-scattering surface.<br>"
                           "z ≈ 1100 (380,000 yr after Big Bang).<br>"
                           "Light-travel distance ≈ 13.8 Gly "
                           "(comoving ≈ 46 Gly).<br>"
                           "<i>Practical edge of the observable "
                           "universe.</i>"),
                hoverinfo="text",
                showlegend=True,
                legendgroup="references",
            ))
            # Latitude rings to suggest sphere shape — fainter so
            # they read as scaffolding, not content.  All four carry
            # the same hover as the equatorial ring so users can
            # mouse over any visible CMB ring and get the same
            # context (consistent discoverability).
            cmb_hover = ("Cosmic Microwave Background — "
                         "last-scattering surface.<br>"
                         "z ≈ 1100 (380,000 yr after Big Bang).<br>"
                         "Light-travel distance ≈ 13.8 Gly "
                         "(comoving ≈ 46 Gly).<br>"
                         "<i>Practical edge of the observable "
                         "universe.</i>")
            # CMB scaffolding (4 latitude rings + 8 meridian arcs)
            # consolidated into a single Scatter3d trace using None-
            # separated polylines.  Was 12 separate traces — Plotly
            # has fixed per-trace overhead in WebGL, so collapsing
            # this into one is a measurable performance win at no
            # visual cost.
            scaf_x: list[float | None] = []
            scaf_y: list[float | None] = []
            scaf_z: list[float | None] = []
            for b_deg in (-60.0, -30.0, 30.0, 60.0):
                b_rad = math.radians(b_deg)
                cos_b_lat = math.cos(b_rad)
                z_at_b = ax_z * math.sin(b_rad)
                scaf_x.extend((ax_x * cos_b_lat * cos_p).tolist())
                scaf_y.extend((ax_y * cos_b_lat * sin_p).tolist())
                scaf_z.extend([z_at_b] * n_phi)
                scaf_x.append(None); scaf_y.append(None); scaf_z.append(None)
            # Meridian arcs at 0°, 45°, ..., 315° (8 longitudes,
            # pole-to-pole).  Same trace as the latitudes — Plotly
            # only sees one polyline trace with gaps.
            n_b = 40   # was 60 — visually identical, less data
            b_arc = np.linspace(-math.pi / 2.0, math.pi / 2.0, n_b)
            cos_b_arc = np.cos(b_arc)
            sin_b_arc = np.sin(b_arc)
            for l_deg in (0, 45, 90, 135, 180, 225, 270, 315):
                l_rad = math.radians(l_deg)
                scaf_x.extend(
                    (ax_x * cos_b_arc * math.cos(l_rad)).tolist())
                scaf_y.extend(
                    (ax_y * cos_b_arc * math.sin(l_rad)).tolist())
                scaf_z.extend((ax_z * sin_b_arc).tolist())
                scaf_x.append(None); scaf_y.append(None); scaf_z.append(None)
            fig.add_trace(go.Scatter3d(
                x=scaf_x, y=scaf_y, z=scaf_z,
                mode="lines",
                line=dict(color="rgba(255,200,140,0.20)",
                          width=1, dash="dot"),
                name="CMB wireframe scaffolding",
                hovertext=cmb_hover,
                hoverinfo="text",
                showlegend=False,
                legendgroup="references",
            ))
            # Single text label tucked at +x.
            fig.add_trace(go.Scatter3d(
                x=[ax_x * 0.99], y=[0.0], z=[ax_z * 0.04],
                mode="text",
                text=["13.8 Gly · CMB · z ≈ 1100"],
                textposition="middle right",
                textfont=dict(color="rgba(255,200,140,0.85)",
                              size=10),
                name="CMB label",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="references",
            ))
        except Exception:
            pass

    # --- 2c-tex. CMB stylized texture sphere (cosmic mode, opt-in) ---
    # Procedural Gaussian-noise texture on a low-poly sphere at the
    # CMB radius.  NOT real Planck/COBE data — that would require
    # licensing-cleared assets and a multi-MB texture file.  The
    # noise pattern is purely visual ("looks like a CMB map at
    # arm's length") with explicit "stylized" labelling in the
    # hover so users don't mistake it for measurement data.
    #
    # Default-off (visible="legendonly") because the sphere lives at
    # scene radius ~43 — toggling it on triggers Plotly's autorange
    # to expand the bounding box, which makes everything else look
    # smaller.  Opt-in is the right call for a "show me the edge of
    # the universe" gesture.
    if mode is ViewMode.COSMIC and scene.get("show_cmb", True):
        try:
            r_cmb_t = scale_dist(13.8e9, mode)
            # Match the wireframe's spherical aspect.  Kept as a
            # triplet so this stays in sync if anyone ever stylizes
            # the shape (just change both blocks together).
            ax_x_t = r_cmb_t * 1.0
            ax_y_t = r_cmb_t * 1.0
            ax_z_t = r_cmb_t * 1.0
            # Reduced from 60×30 = 1800 → 36×18 = 648 vertices.
            # The CMB texture is already a soft procedural noise
            # blur; the lower-poly mesh is visually nearly identical
            # but ~3× cheaper on the WebGL side.
            n_lon, n_lat = 36, 18
            lons_t = np.linspace(0.0, 2.0 * math.pi, n_lon,
                                  endpoint=False)
            lats_t = np.linspace(-math.pi / 2.0 * 0.97,
                                  math.pi / 2.0 * 0.97, n_lat)
            xs_t = []
            ys_t = []
            zs_t = []
            for lat in lats_t:
                cos_lat = math.cos(lat)
                sin_lat = math.sin(lat)
                for lon in lons_t:
                    xs_t.append(ax_x_t * cos_lat * math.cos(lon))
                    ys_t.append(ax_y_t * cos_lat * math.sin(lon))
                    zs_t.append(ax_z_t * sin_lat)
            # Procedural Gaussian noise + a few smoothing passes so
            # the texture has spatially-correlated patches rather
            # than per-pixel salt-and-pepper.  Seeded so re-renders
            # of the same scene don't flicker.
            rng_cmb = np.random.default_rng(seed=2725)
            T_grid = rng_cmb.standard_normal((n_lat, n_lon))
            for _ in range(3):
                T_grid = (
                    T_grid
                    + np.roll(T_grid, 1, axis=0)
                    + np.roll(T_grid, -1, axis=0)
                    + np.roll(T_grid, 1, axis=1)
                    + np.roll(T_grid, -1, axis=1)
                ) / 5.0
            T_flat = T_grid.flatten().tolist()
            i_idx, j_idx, k_idx = [], [], []
            for la in range(n_lat - 1):
                for lo in range(n_lon):
                    a = la * n_lon + lo
                    b = la * n_lon + (lo + 1) % n_lon
                    c = (la + 1) * n_lon + (lo + 1) % n_lon
                    d_ = (la + 1) * n_lon + lo
                    i_idx.extend([a, a]); j_idx.extend([b, c]); k_idx.extend([c, d_])
            fig.add_trace(go.Mesh3d(
                x=xs_t, y=ys_t, z=zs_t,
                i=i_idx, j=j_idx, k=k_idx,
                intensity=T_flat,
                # Red-blue colorscale mimicking real CMB anisotropy
                # plots (cold spots blue/violet, hot spots warm).
                colorscale=[[0.0, "rgba(60,40,150,0.6)"],
                            [0.5, "rgba(20,20,30,0.4)"],
                            [1.0, "rgba(220,90,40,0.6)"]],
                opacity=0.20,
                name="CMB texture (stylized)",
                hovertext=(
                    "<b>Stylized CMB texture</b> — procedural "
                    "Gaussian noise.<br>"
                    "<i>Not real Planck data.</i>  Real CMB "
                    "anisotropies are at the ~10 µK level "
                    "(one part in 100,000 of the 2.725 K mean).<br>"
                    "Toggle off in legend to use just the wireframe "
                    "boundary."),
                hoverinfo="text",
                showscale=False,
                showlegend=True,
                legendgroup="references",
                # Default-off so cosmic-mode autorange doesn't
                # expand to ±43 by default.  User opts in to see
                # the dramatic edge-of-universe view.
                visible="legendonly",
            ))
        except Exception:
            pass

    # --- 2b. Heliocentric distance rings (galactic mode) ---
    # Earth-centered companion to the GC-centered rings above.  Same
    # dotted style but in a warmer hue so the two ring sets read as
    # different things ("from us" vs "from the Galactic Center").
    # Only fires in galactic mode; cosmic-mode rings are already
    # Earth-centered.
    if scene.get("show_disk", True) and mode is ViewMode.GALACTIC:
        try:
            helio_rings = build_helio_rings(mode)
            for ring in helio_rings:
                # Same three-orthogonal-circles treatment as the
                # GC-centered rings above so the heliocentric ring
                # set reads as a spherical shell around Earth.
                _r_s = ring["r_scene"]
                _cx_s = ring["center_x"]
                rxs: list[float | None] = list(ring["x"])
                rys: list[float | None] = list(ring["y"])
                rzs: list[float | None] = list(ring["z"])
                rxs.append(None); rys.append(None); rzs.append(None)
                rxs.extend((_cx_s + _r_s * _cos_phi).tolist())
                rys.extend([0.0] * len(_phis_3d))
                rzs.extend((_r_s * _sin_phi).tolist())
                rxs.append(None); rys.append(None); rzs.append(None)
                rxs.extend([_cx_s] * len(_phis_3d))
                rys.extend((_r_s * _cos_phi).tolist())
                rzs.extend((_r_s * _sin_phi).tolist())
                fig.add_trace(go.Scatter3d(
                    x=rxs, y=rys, z=rzs,
                    mode="lines",
                    line=dict(color="rgba(220,180,140,0.30)",
                              width=1, dash="dot"),
                    name=f"Earth ring: {ring['label']}",
                    hovertext=f"{ring['label']} from Earth",
                    hoverinfo="text",
                    showlegend=False,
                    legendgroup="references",
                ))
                # Ring label tucked near the ring's "+x relative to
                # Earth" point, slightly above the disk so it
                # doesn't collide with the GC-centered ring labels
                # along z=0.
                fig.add_trace(go.Scatter3d(
                    x=[ring["center_x"] + ring["r_scene"] * 1.01],
                    y=[0.0],
                    z=[ring["r_scene"] * 0.04],
                    mode="text",
                    text=[ring["label"]],
                    textposition="middle right",
                    textfont=dict(color="rgba(220,180,140,0.65)",
                                  size=9),
                    name=f"Earth ring label: {ring['label']}",
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="references",
                ))
        except Exception:
            pass

    # --- 3. Compass rose ---
    try:
        arrows = build_compass_rose(scene, mode)
        for a in arrows:
            fig.add_trace(go.Scatter3d(
                x=a["xs"], y=a["ys"], z=a["zs"],
                mode="lines",
                line=dict(color=a["color"], width=4),
                name=a["name"],
                hovertext=a["label"],
                hoverinfo="text",
                showlegend=False,
                legendgroup="references",
            ))
            # Tip marker + short label at the arrowhead.
            tip = a["tip"]
            fig.add_trace(go.Scatter3d(
                x=[tip[0]], y=[tip[1]], z=[tip[2]],
                mode="markers+text",
                marker=dict(size=4, color=a["color"], symbol="diamond",
                            opacity=0.9),
                text=[a["label"]],
                textposition=_textposition_for(tip[0], tip[1], tip[2]),
                textfont=dict(color=a["color"], size=9),
                name=a["name"] + " tip",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="references",
            ))
    except Exception:
        pass

    # --- 4. Galactic disk stars (exponential + arm-biased) ---
    if scene.get("show_disk", True):
        disk = generate_disk_stars(mode, n=scene.get("disk_n", 500))
        fig.add_trace(go.Scatter3d(
            x=disk["x"], y=disk["y"], z=disk["z"],
            mode="markers",
            marker=dict(
                size=1.8,
                color=disk["b"],
                colorscale=[[0, "rgba(80,80,120,0.2)"],
                            [1, "rgba(235,225,200,0.95)"]],
                showscale=False,
                opacity=0.75,
            ),
            name="Disk stars",
            hoverinfo="skip",
            showlegend=False,
            legendgroup="milkyway",
        ))
        # Central bulge — separate trace, warmer colour.
        try:
            bulge = generate_bulge_stars(mode, n=scene.get("bulge_n", 180))
            fig.add_trace(go.Scatter3d(
                x=bulge["x"], y=bulge["y"], z=bulge["z"],
                mode="markers",
                marker=dict(size=2.2, color="#ffcc77",
                            opacity=0.55,
                            line=dict(width=0)),
                name="Galactic bulge",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="milkyway",
            ))
        except Exception:
            pass

    # --- 5. Spiral arms ---
    if scene.get("show_arms", True):
        # 320 vertices per arm (~1.1° per chord) — 80 was smooth at the
        # default zoom but visibly angular once the camera pushes in
        # close to the galactic plane.  320 gives a crisp curve at any
        # reasonable zoom for negligible memory cost (~1.6k floats
        # total across 5 arms).
        for arm in SPIRAL_ARMS:
            pts = arm_scene_points(arm, mode, n_pts=320)
            fig.add_trace(go.Scatter3d(
                x=pts["x"], y=pts["y"], z=pts["z"],
                mode="lines",
                line=dict(color=arm["col"],
                          width=6 if arm.get("is_local") else 3),
                name=arm["name"],
                hovertext=arm["name"],
                hoverinfo="text",
                legendgroup="milkyway",
                legendgrouptitle_text="Milky Way",
            ))
        # Arm-name labels (galactic mode only — arms are compressed
        # to an invisible dot in cosmic mode).  One short token per
        # arm, tinted with the arm's own colour so it reads as a
        # caption of the line it sits on.
        if mode is ViewMode.GALACTIC:
            try:
                arm_labels = build_arm_name_labels(mode)
                if arm_labels["text"]:
                    fig.add_trace(go.Scatter3d(
                        x=arm_labels["x"], y=arm_labels["y"],
                        z=arm_labels["z"],
                        mode="text",
                        text=arm_labels["text"],
                        textposition="top center",
                        textfont=dict(color=arm_labels["colors"],
                                      size=11,
                                      family="Arial Black"),
                        name="Arm names",
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup="milkyway",
                    ))
            except Exception:
                pass

    # --- 6. Galactic centre Sgr A* ---
    fig.add_trace(go.Scatter3d(
        x=[gc_x], y=[0], z=[0],
        mode="markers+text",
        marker=dict(size=9, color="#ffaa33",
                    symbol="diamond", opacity=0.95,
                    line=dict(color="#ffddaa", width=1)),
        text=["Sgr A*"],
        textposition=_textposition_for(gc_x, 0, 0),
        textfont=dict(color="#ffcc88", size=10),
        name="Sgr A* (Galactic Center)",
        hovertext=(f"Galactic Center (Sgr A*)<br>"
                   f"Distance from Earth: {EARTH_TO_GC_LY:,} ly"),
        hoverinfo="text",
        legendgroup="milkyway",
        legendgrouptitle_text="Milky Way",
    ))

    # --- 6a. Galactic landmarks catalog (galactic mode) ---
    # Curated set of famous open / globular clusters and nebulae.
    # Plotted as labeled markers at their real (l, b, distance)
    # positions.  Behind a legend toggle (`show_landmarks`) so the
    # scene stays clean by default.  Cosmic-mode rendering would
    # collapse them all near origin, so it's gated to galactic mode.
    if mode is ViewMode.GALACTIC and scene.get("show_landmarks", False):
        try:
            # Group by kind so each kind becomes a separately-toggle-
            # able legend entry rather than 20+ individual rows.
            by_kind: dict[str, list[dict]] = {}
            for lm in GALACTIC_LANDMARKS:
                by_kind.setdefault(lm["kind"], []).append(lm)
            kind_labels = {
                "OpC": "Open clusters",
                "GlC": "Globular clusters",
                "Neb": "Nebulae",
                "SNR": "Supernova remnants",
                "PN":  "Planetary nebulae",
            }
            for kind, lms in by_kind.items():
                style = LANDMARK_STYLE.get(
                    kind, {"color": "#cccccc", "symbol": "circle"})
                xs_lm, ys_lm, zs_lm = [], [], []
                names_lm, hovers_lm = [], []
                for lm in lms:
                    x, y, z = gal_to_xyz(
                        lm["l"], lm["b"],
                        scale_dist(float(lm["dist_ly"]), mode))
                    xs_lm.append(x); ys_lm.append(y); zs_lm.append(z)
                    names_lm.append(lm["name"])
                    if lm["dist_ly"] < 1000:
                        d_str = f"{lm['dist_ly']:,.0f} ly"
                    else:
                        d_str = f"{lm['dist_ly']/1000:.1f} kly"
                    hovers_lm.append(
                        f"<b>{lm['name']}</b><br>"
                        f"l={lm['l']:.1f}°, b={lm['b']:.1f}°<br>"
                        f"Distance: {d_str}<br>"
                        f"Type: {kind_labels.get(kind, kind)}"
                    )
                fig.add_trace(go.Scatter3d(
                    x=xs_lm, y=ys_lm, z=zs_lm,
                    mode="markers+text",
                    marker=dict(size=5, color=style["color"],
                                symbol=style["symbol"], opacity=0.9,
                                line=dict(color="#ffffff", width=0.5)),
                    text=names_lm,
                    textposition="top center",
                    textfont=dict(color=style["color"], size=8),
                    name=kind_labels.get(kind, kind),
                    hovertext=hovers_lm,
                    hoverinfo="text",
                    legendgroup="landmarks",
                    legendgrouptitle_text="Landmarks",
                ))
        except Exception:
            # Landmark rendering is decorative — a parse error in
            # one entry shouldn't kill the figure.  Silently skip.
            pass

    # (Cosmic-history event markers removed by request — labels at
    # specific lookback times along the +x axis are no longer drawn.
    # Lookback / age context still appears in the target's mid-ray
    # label, the cosmic-mode distance-ring hovers, and the CMB
    # boundary marker.)

    # (Stylized cosmic-web filaments removed by request — they
    # connected known cluster centroids with curated wandering
    # polylines but were decorative rather than measurement-driven.
    # The cluster halos and cosmic-mode landmarks now carry the
    # large-scale-structure context on their own.)

    # (Procedural background-galaxy sprinkle removed by request — the
    # 500-dot log-distance shell from 100 Mly to 5 Gly is no longer
    # drawn.  Real-data catalog overlay is the swap-in if anyone
    # wants populated cosmic background later.)

    # --- 6e. Cosmic-mode landmarks catalog ---
    # Famous extragalactic objects plotted at their real (l, b, d).
    # Grouped by kind so each kind gets one toggleable legend entry.
    if mode is ViewMode.COSMIC and scene.get("show_cosmic_landmarks", True):
        try:
            by_kind: dict[str, list[dict]] = {}
            for lm in COSMIC_LANDMARKS:
                by_kind.setdefault(lm["kind"], []).append(lm)
            kind_labels = {
                "Galaxy-spiral":     "Spiral galaxies",
                "Galaxy-dwarf":      "Dwarf galaxies",
                "Galaxy-starburst":  "Starburst galaxies",
                "Galaxy-AGN":        "Active galaxies (AGN)",
                "Galaxy-peculiar":   "Peculiar galaxies",
                "Galaxy-group":      "Galaxy groups",
                "Quasar":            "Quasars",
                "Reference-pointer": "Reference pointers",
            }
            for kind, lms in by_kind.items():
                style = COSMIC_LANDMARK_STYLE.get(
                    kind, {"color": "#cccccc", "symbol": "circle"})
                xs_lm, ys_lm, zs_lm = [], [], []
                names_lm, hovers_lm = [], []
                for lm in lms:
                    x, y, z = gal_to_xyz(
                        lm["l"], lm["b"],
                        scale_dist(float(lm["dist_ly"]), mode))
                    xs_lm.append(x); ys_lm.append(y); zs_lm.append(z)
                    names_lm.append(lm["name"])
                    z_lm, lb_lm = estimate_z_and_lookback(
                        float(lm["dist_ly"]))
                    if z_lm < 0.001:
                        z_str = f"{z_lm:.5f}"
                    elif z_lm < 0.01:
                        z_str = f"{z_lm:.4f}"
                    elif z_lm < 1.0:
                        z_str = f"{z_lm:.3f}"
                    else:
                        z_str = f"{z_lm:.2f}"
                    lb_str = (f"{lb_lm*1000:.0f} Myr"
                              if lb_lm < 1.0
                              else f"{lb_lm:.2f} Gyr")
                    if lm["dist_ly"] < 1e6:
                        d_str = f"{lm['dist_ly']:,} ly"
                    elif lm["dist_ly"] < 1e9:
                        d_str = f"{lm['dist_ly']/1e6:.1f} Mly"
                    else:
                        d_str = f"{lm['dist_ly']/1e9:.2f} Gly"
                    hovers_lm.append(
                        f"<b>{lm['name']}</b><br>"
                        f"l={lm['l']:.1f}°, b={lm['b']:.1f}°<br>"
                        f"Distance: {d_str} · z ≈ {z_str}<br>"
                        f"Lookback: {lb_str}<br>"
                        f"Type: {kind_labels.get(kind, kind)}"
                    )
                fig.add_trace(go.Scatter3d(
                    x=xs_lm, y=ys_lm, z=zs_lm,
                    mode="markers+text",
                    marker=dict(size=4, color=style["color"],
                                symbol=style["symbol"], opacity=0.9,
                                line=dict(color="#ffffff", width=0.4)),
                    text=names_lm,
                    textposition="top center",
                    textfont=dict(color=style["color"], size=8),
                    name=kind_labels.get(kind, kind),
                    hovertext=hovers_lm,
                    hoverinfo="text",
                    legendgroup="cosmic_landmarks",
                    legendgrouptitle_text="Cosmic landmarks",
                ))
        except Exception:
            pass

    # --- 6d. Galaxy-cluster halos (cosmic mode) ---
    # Translucent spheres at known cluster positions, radius ≈ each
    # cluster's core extent.  Default-on but cheap — each cluster is
    # a single low-poly sphere mesh.  Combined with the new cosmic-
    # landmarks catalog, turns the void into recognizable structure.
    if mode is ViewMode.COSMIC and scene.get("show_clusters", True):
        try:
            # Cluster halos are translucent shells; 12×8 = 96 verts
            # is plenty given the ~10% opacity (was 16×12 = 192).
            n_lon, n_lat = 12, 8
            lons = np.linspace(0.0, 2.0 * math.pi, n_lon, endpoint=False)
            lats = np.linspace(-math.pi / 2.0, math.pi / 2.0, n_lat)
            for cluster in GALAXY_CLUSTERS:
                cx, cy, cz = gal_to_xyz(
                    cluster["l"], cluster["b"],
                    scale_dist(float(cluster["dist_ly"]), mode))
                r_units = scale_dist(
                    float(cluster["extent_ly"]), mode)
                # In cosmic mode `scale_dist` is non-linear; the
                # cluster's apparent size in scene units depends on
                # whether we're in the linear (≤1 Mly) or log
                # (>1 Mly) range.  Compute the radius by taking the
                # difference between (dist+extent) and (dist-extent)
                # in scene units, halved — the right answer for both.
                r_outer = scale_dist(
                    float(cluster["dist_ly"] + cluster["extent_ly"]),
                    mode)
                r_inner = scale_dist(
                    max(1.0,
                        float(cluster["dist_ly"]
                              - cluster["extent_ly"])),
                    mode)
                r_units = max(0.05, (r_outer - r_inner) * 0.5)
                xs_c, ys_c, zs_c = [], [], []
                for lat in lats:
                    for lon in lons:
                        xs_c.append(cx + r_units * math.cos(lat) * math.cos(lon))
                        ys_c.append(cy + r_units * math.cos(lat) * math.sin(lon))
                        zs_c.append(cz + r_units * math.sin(lat))
                i_idx, j_idx, k_idx = [], [], []
                for la in range(n_lat - 1):
                    for lo in range(n_lon):
                        a = la * n_lon + lo
                        b = la * n_lon + (lo + 1) % n_lon
                        c = (la + 1) * n_lon + (lo + 1) % n_lon
                        d_ = (la + 1) * n_lon + lo
                        i_idx.extend([a, a]); j_idx.extend([b, c]); k_idx.extend([c, d_])
                z_cl, lb_cl = estimate_z_and_lookback(
                    float(cluster["dist_ly"]))
                z_str = (f"{z_cl:.4f}" if z_cl < 0.01
                         else f"{z_cl:.3f}" if z_cl < 1.0
                         else f"{z_cl:.2f}")
                lb_str = (f"{lb_cl*1000:.0f} Myr"
                          if lb_cl < 1.0
                          else f"{lb_cl:.2f} Gyr")
                fig.add_trace(go.Mesh3d(
                    x=xs_c, y=ys_c, z=zs_c,
                    i=i_idx, j=j_idx, k=k_idx,
                    color=cluster["col"], opacity=0.10,
                    name=cluster["name"],
                    hovertext=(
                        f"<b>{cluster['name']}</b><br>"
                        f"l={cluster['l']:.1f}°, "
                        f"b={cluster['b']:.1f}°<br>"
                        f"Distance: {cluster['dist_ly']/1e6:.1f} Mly · "
                        f"z ≈ {z_str}<br>"
                        f"Lookback: {lb_str}<br>"
                        f"Core extent: ≈ "
                        f"{cluster['extent_ly']/1e6:.1f} Mly<br>"
                        f"<i>{cluster['note']}</i>"),
                    hoverinfo="text",
                    showscale=False, showlegend=True,
                    legendgroup="clusters",
                    legendgrouptitle_text="Galaxy clusters",
                ))
        except Exception:
            pass

    # --- 6c. Local Group boundary (cosmic mode, nearby targets) ---
    # The Milky Way + Andromeda + ~80 satellites form the Local
    # Group, gravitationally bound, within ~3 Mly.  For sub-5-Mly
    # extragalactic targets, a translucent sphere of that radius
    # gives "your photo is in the Local Group" framing.
    dist_ly_lg = scene.get("dist_ly") or 0.0
    if (mode is ViewMode.COSMIC and dist_ly_lg > 0
            and dist_ly_lg <= 5_000_000.0
            and scene.get("show_disk", True)):
        try:
            r_units = scale_dist(3_000_000.0, mode)   # 3 Mly
            n_lon, n_lat = 16, 10
            lons = np.linspace(0.0, 2.0 * math.pi, n_lon, endpoint=False)
            lats = np.linspace(-math.pi / 2.0, math.pi / 2.0, n_lat)
            xs_g, ys_g, zs_g = [], [], []
            for lat in lats:
                for lon in lons:
                    xs_g.append(r_units * math.cos(lat) * math.cos(lon))
                    ys_g.append(r_units * math.cos(lat) * math.sin(lon))
                    zs_g.append(r_units * math.sin(lat))
            i_idx, j_idx, k_idx = [], [], []
            for la in range(n_lat - 1):
                for lo in range(n_lon):
                    a = la * n_lon + lo
                    b = la * n_lon + (lo + 1) % n_lon
                    c = (la + 1) * n_lon + (lo + 1) % n_lon
                    d_ = (la + 1) * n_lon + lo
                    i_idx.extend([a, a]); j_idx.extend([b, c]); k_idx.extend([c, d_])
            fig.add_trace(go.Mesh3d(
                x=xs_g, y=ys_g, z=zs_g,
                i=i_idx, j=j_idx, k=k_idx,
                color="#a08060", opacity=0.05,
                name="Local Group (~3 Mly)",
                hovertext=("Local Group — gravitationally bound "
                           "collection of the Milky Way, Andromeda, "
                           "Triangulum, and ~80 dwarf satellites.<br>"
                           "Approx. 3 Mly radius."),
                hoverinfo="text",
                showscale=False, showlegend=True,
                legendgroup="references",
                legendgrouptitle_text="References",
            ))
        except Exception:
            pass

    # --- 6b. Local Bubble (galactic mode, nearby targets only) ---
    # The Solar System sits inside a low-density cavity carved by
    # past supernovae, extending ~300-500 ly in most directions
    # (~1000 ly toward Cetus; the cavity is asymmetric).  For sub-
    # 2-kly targets, drawing it as a translucent sphere centered on
    # Earth gives the photo's distance meaningful local context —
    # "the target is just outside / just inside the bubble".
    # Skipped for distant or extragalactic targets (would only
    # clutter the scene).
    dist_ly_val_bubble = scene.get("dist_ly") or 0.0
    if (mode is ViewMode.GALACTIC and dist_ly_val_bubble > 0
            and dist_ly_val_bubble <= 2000.0
            and scene.get("show_disk", True)):
        try:
            bubble_r_ly = 400.0   # ~400-ly average radius
            r_units = scale_dist(bubble_r_ly, mode)
            # Low-poly sphere mesh (UV sphere) — 16×10 = 160 verts.
            n_lon, n_lat = 16, 10
            lons = np.linspace(0.0, 2.0 * math.pi, n_lon, endpoint=False)
            lats = np.linspace(-math.pi / 2.0, math.pi / 2.0, n_lat)
            xs_b, ys_b, zs_b = [], [], []
            for lat in lats:
                for lon in lons:
                    xs_b.append(r_units * math.cos(lat) * math.cos(lon))
                    ys_b.append(r_units * math.cos(lat) * math.sin(lon))
                    zs_b.append(r_units * math.sin(lat))
            i_idx, j_idx, k_idx = [], [], []
            for la in range(n_lat - 1):
                for lo in range(n_lon):
                    a = la * n_lon + lo
                    b = la * n_lon + (lo + 1) % n_lon
                    c = (la + 1) * n_lon + (lo + 1) % n_lon
                    d_ = (la + 1) * n_lon + lo
                    i_idx.extend([a, a]); j_idx.extend([b, c]); k_idx.extend([c, d_])
            fig.add_trace(go.Mesh3d(
                x=xs_b, y=ys_b, z=zs_b,
                i=i_idx, j=j_idx, k=k_idx,
                color="#5a8aaa", opacity=0.06,
                name="Local Bubble (~400 ly)",
                hovertext=("Local Bubble — supernova-carved cavity "
                           "around the Solar System.<br>Approx. 400 "
                           "ly mean radius (asymmetric)."),
                hoverinfo="text",
                showscale=False, showlegend=True,
                legendgroup="references",
                legendgrouptitle_text="References",
            ))
        except Exception:
            pass

    # --- 7. Earth at origin (target-reticle "you are here" glyph) ---
    # Stacked traces: outer open ring (halo) + inner solid dot.  Reads
    # as a target reticle so users orient on Earth far faster than off
    # the plain dot the previous version used.  Keep the labelled
    # marker as the legend-visible trace; the halo is decorative and
    # hidden from the legend.
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode="markers",
        marker=dict(size=14, color="rgba(0,0,0,0)",
                    symbol="circle-open", opacity=0.9,
                    line=dict(color="#aaddff", width=2)),
        name="Earth halo",
        hoverinfo="skip",
        showlegend=False,
        legendgroup="milkyway",
    ))
    # P2.5 — hover-rich Earth marker.  Compact summary of where we
    # actually are, what direction the photo points in galactic
    # coordinates, and how that line of sight relates to nearby
    # structure.  Free information density — costs nothing at render
    # time, helps users orient.
    earth_hover_lines = [
        "<b>Earth</b> — origin of the scene",
        "Located in the Orion Arm (the <i>local</i> arm)",
        f"Distance to Galactic Center: {EARTH_TO_GC_LY:,} ly",
        "Galactic latitude: 0° (we're <i>in</i> the disk plane)",
    ]
    target_l = scene.get("l_deg")
    target_b = scene.get("b_deg")
    if target_l is not None and target_b is not None:
        earth_hover_lines.append(
            f"Photo points toward (l={target_l:.1f}°, "
            f"b={target_b:.1f}°)"
        )
    arm_hint_str = scene.get("arm_hint")
    if arm_hint_str:
        earth_hover_lines.append(
            f"Line of sight: {arm_hint_str}"
        )
    earth_hover = "<br>".join(earth_hover_lines)

    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode="markers+text",
        marker=dict(size=6, color="#55aaff",
                    symbol="circle", opacity=1.0,
                    line=dict(color="#ffffff", width=1)),
        text=["Earth (Orion Arm)"],
        textposition="bottom center",
        textfont=dict(color="#aaddff", size=11),
        name="Earth",
        hovertext=earth_hover,
        hoverinfo="text",
        legendgroup="milkyway",
        legendgrouptitle_text="Milky Way",
    ))

    # P4.9 — Earth's galactic-rotation velocity arrow.  Earth orbits
    # the GC at ~220 km/s in the +Y direction (galactic east) since
    # +X = toward GC by convention.  Reminds users that Earth is
    # moving through this static-looking scene.  Galactic mode only
    # because in cosmic mode the arrow would collapse to a dot.
    if mode is ViewMode.GALACTIC:
        try:
            arrow_len = scale_dist(2_500.0, mode)  # ~2.5 kly visual length
            fig.add_trace(go.Scatter3d(
                x=[0, 0], y=[0, arrow_len], z=[0, 0],
                mode="lines",
                line=dict(color="rgba(120,220,180,0.55)", width=4),
                name="Earth's orbital motion (~220 km/s)",
                hovertext=("Earth's orbital motion around the "
                           "Galactic Center.<br>~220 km/s toward "
                           "galactic longitude 90°.<br>One full "
                           "galactic year ≈ 225 Myr."),
                hoverinfo="text",
                showlegend=False,
                legendgroup="milkyway",
            ))
            # Tip marker so the arrow reads as directional, not just
            # as a line segment.
            fig.add_trace(go.Scatter3d(
                x=[0], y=[arrow_len], z=[0],
                mode="markers+text",
                marker=dict(size=4, color="#78dcb4",
                            symbol="diamond", opacity=0.9,
                            line=dict(width=0)),
                text=["→ rotation"],
                textposition="middle right",
                textfont=dict(color="rgba(120,220,180,0.75)", size=9),
                name="Rotation arrow tip",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="milkyway",
            ))
        except Exception:
            pass

    # --- 8. Neighbor galaxies (cosmic mode) ---
    if show_neighbors:
        gx, gy, gz, gname, ghover, gsize, gcol = [], [], [], [], [], [], []
        gtext_pos = []  # per-marker textposition (anti-collision)
        for g in NEIGHBOR_GALAXIES:
            x, y, z = gal_to_xyz(g["l"], g["b"],
                                 scale_dist(g["dist_ly"], mode))
            gx.append(x)
            gy.append(y)
            gz.append(z)
            gname.append(g["name"])
            # P1.3 — hover-rich neighbor info: type, group membership,
            # redshift, lookback time, and a one-sentence note.  Turns
            # the neighbor markers from decoration into mini reference
            # cards.
            z_g, lb_g = estimate_z_and_lookback(float(g["dist_ly"]))
            if z_g < 0.001:
                z_str = f"{z_g:.5f}"
            elif z_g < 0.01:
                z_str = f"{z_g:.4f}"
            else:
                z_str = f"{z_g:.3f}"
            lb_str = (f"{lb_g*1000:.0f} Myr"
                      if lb_g < 1.0
                      else f"{lb_g:.2f} Gyr")
            hover_lines = [
                f"<b>{g['name']}</b>",
                f"l={g['l']:.1f}°, b={g['b']:.1f}°",
                f"Distance: {g['dist_ly']:,} ly · z ≈ {z_str}",
                f"Lookback: {lb_str}",
                f"Diameter: {g['diam_ly']:,} ly",
            ]
            if g.get("type"):
                hover_lines.append(f"Type: {g['type']}")
            if g.get("group"):
                hover_lines.append(f"Member of: {g['group']}")
            if g.get("note"):
                hover_lines.append(f"<i>{g['note']}</i>")
            ghover.append("<br>".join(hover_lines))
            gsize.append(max(6, min(22, math.log10(g["diam_ly"]) * 4)))
            gcol.append(g["col"])
            gtext_pos.append(_textposition_for(x, y, z))
        fig.add_trace(go.Scatter3d(
            x=gx, y=gy, z=gz,
            mode="markers+text",
            marker=dict(size=gsize, color=gcol, symbol="circle",
                        opacity=0.85,
                        line=dict(color="#ffffff", width=0.5)),
            text=gname,
            # Per-point textposition biases labels away from the origin
            # so neighbours at ±l / ±b don't pile up on top of each
            # other at "top center" (the prior default).
            textposition=gtext_pos,
            textfont=dict(color="#e0d0b0", size=9),
            name="Neighbor galaxies",
            hovertext=ghover,
            hoverinfo="text",
            legendgroup="background",
            legendgrouptitle_text="Background",
        ))

    # --- Photo rectangle + viewing ray ---
    corners = scene.get("photo_corners")
    photo_center = scene.get("photo_center_xyz")
    obj_name = scene.get("object_name", "Target")
    dist_label = scene.get("distance_label", "")

    if corners and len(corners) == 4:
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        zs = [c[2] for c in corners]

        # Photo surface — preferred path is a subdivided Mesh3d quad
        # with per-face colours baked from the downsampled texture.
        # That's a single WebGL draw call (~5-18k flat-shaded tris)
        # which reads as a continuous image.
        #
        # Legacy path: a Scatter3d pixel cloud at 480 px (~230k markers)
        # — still available behind the "debug pixel scatter" switch
        # in Scene Elements so developers can compare.  Hover is
        # ``skip`` on both because per-pixel hover is meaningless
        # (identification comes from the outline trace below).
        texture_mesh = scene.get("photo_texture_mesh")
        pixel_grid = scene.get("photo_pixel_grid")
        if texture_mesh:
            try:
                fig.add_trace(go.Mesh3d(
                    x=texture_mesh["x"],
                    y=texture_mesh["y"],
                    z=texture_mesh["z"],
                    i=texture_mesh["i"],
                    j=texture_mesh["j"],
                    k=texture_mesh["k"],
                    facecolor=texture_mesh["facecolor"],
                    flatshading=True,
                    # Turn off lighting so the baked colours read as
                    # the actual photo, not a shaded surface.
                    lighting=dict(ambient=1.0, diffuse=0.0,
                                  specular=0.0, roughness=1.0,
                                  fresnel=0.0),
                    name=f"Photo: {obj_name}",
                    hoverinfo="skip",
                    showscale=False,
                    showlegend=True,
                    legendgroup="target",
                    legendgrouptitle_text="Target",
                ))
            except Exception:
                # On failure, fall through to the legacy scatter
                # (if available) or the translucent fallback.
                texture_mesh = None
        if texture_mesh is None and pixel_grid:
            fig.add_trace(go.Scatter3d(
                x=pixel_grid["x"],
                y=pixel_grid["y"],
                z=pixel_grid["z"],
                mode="markers",
                marker=dict(
                    size=pixel_grid.get("marker_size", 3),
                    color=pixel_grid["colors"],
                    opacity=1.0,
                    line=dict(width=0),
                ),
                name=f"Photo: {obj_name} (pixels)",
                hoverinfo="skip",
                showlegend=True,
                legendgroup="target",
                legendgrouptitle_text="Target",
            ))
        elif texture_mesh is None and not pixel_grid:
            # Fallback: translucent Mesh3d fill when no texture is available
            try:
                fig.add_trace(go.Mesh3d(
                    x=xs, y=ys, z=zs,
                    i=[0, 0], j=[1, 2], k=[2, 3],
                    color="#ffee88", opacity=0.28,
                    name="Photo surface",
                    hoverinfo="skip",
                    showscale=False,
                    legendgroup="target",
                    legendgrouptitle_text="Target",
                ))
            except Exception:
                pass

        # Bright outline always on top
        fig.add_trace(go.Scatter3d(
            x=xs + [xs[0]], y=ys + [ys[0]], z=zs + [zs[0]],
            mode="lines",
            line=dict(color="#ffee88", width=5),
            name="Photo frame",
            hovertext=f"{obj_name}<br>{dist_label}",
            hoverinfo="text",
            legendgroup="target",
            legendgrouptitle_text="Target",
        ))

        # (Photo solid-angle cone removed by request — the four
        # dotted lines from Earth to the photo corners and the
        # translucent pyramid skin are no longer drawn.  Only the
        # single centre-of-photo viewing-ray line below remains.)

    if photo_center is not None:
        # Dashed "backbone" of the viewing ray for continuity.
        fig.add_trace(go.Scatter3d(
            x=[0, photo_center[0]],
            y=[0, photo_center[1]],
            z=[0, photo_center[2]],
            mode="lines",
            line=dict(color="rgba(255,204,68,0.55)", width=2,
                      dash="dot"),
            name="Viewing ray",
            hovertext=f"Line of sight from Earth to {obj_name}",
            hoverinfo="text",
            legendgroup="target",
            legendgrouptitle_text="Target",
        ))

        # Depth cues along the viewing ray have been removed — the
        # earlier render stacked the dotted line, a 40-marker warm→cool
        # gradient, AND log-decade tick crosses with labels along the
        # same path, which most users read as visual noise.  Scale
        # along the ray is now communicated by:
        #   - the blue-grey distance rings centered on Earth (radial
        #     scale),
        #   - the depth-fan rings (nearest / chosen / farthest target),
        #   - the scale bar in the top-left HUD,
        #   - and the ray itself, which is just a single clean
        #     dotted line connecting Earth to the photo.
        # build_viewing_ray_cues() is left in the module — re-enabling
        # it is a one-line restore if a future user wants the ticks
        # back.

        # Photo-plane halo removed — at certain camera distances it
        # rendered as a too-large yellow blob at the ray-photo
        # intersection, drawing more attention than the photo itself.
        # The dotted viewing ray's clean termination on the photo
        # frame is enough of a pierce-point cue without it.

        # Object name + distance label at the midpoint of the ray.
        dist_ly_val = scene.get("dist_ly")
        if dist_ly_val and dist_ly_val > 0:
            if dist_ly_val < 1e6:
                dist_text = f"{dist_ly_val:,.0f} ly"
            elif dist_ly_val < 1e9:
                dist_text = f"{dist_ly_val/1e6:.2f} Mly"
            else:
                dist_text = f"{dist_ly_val/1e9:.2f} Gly"
            # Append the arm-membership tag if the target is in-disk.
            # which_arm() returns None for distant or out-of-plane
            # targets where membership isn't meaningful.
            arm_tag = ""
            arm_info = scene.get("target_arm_membership")
            if arm_info:
                arm_name, _perp_ly = arm_info
                arm_tag = f"<br><i>in {arm_name}</i>"
            # P1.1 — cosmic-mode redshift + lookback time on the
            # target.  For local-group / sub-Mly targets z is
            # essentially zero, so the annotation is gated to
            # cosmic-mode targets at ≥ 1 Mly.
            cosmo_tag = ""
            if (mode is ViewMode.COSMIC
                    and dist_ly_val and dist_ly_val >= 1e6):
                z_t, lb_t = estimate_z_and_lookback(float(dist_ly_val))
                if z_t > 0:
                    z_str = (f"{z_t:.4f}" if z_t < 0.01
                             else f"{z_t:.3f}" if z_t < 1.0
                             else f"{z_t:.2f}")
                    lb_str = (f"{lb_t*1000:.0f} Myr"
                              if lb_t < 1.0
                              else f"{lb_t:.2f} Gyr")
                    cosmo_tag = (f"<br>z ≈ {z_str} · "
                                 f"lookback {lb_str}")
            label = (f"{obj_name}<br>{dist_text}{arm_tag}{cosmo_tag}"
                     if obj_name
                     else f"{dist_text}{arm_tag}{cosmo_tag}")
            mid_x = photo_center[0] * 0.5
            mid_y = photo_center[1] * 0.5
            mid_z = photo_center[2] * 0.5
            fig.add_trace(go.Scatter3d(
                x=[mid_x], y=[mid_y], z=[mid_z],
                mode="text",
                text=[label],
                textposition=_textposition_for(mid_x, mid_y, mid_z),
                textfont=dict(color="#ffd97a", size=12,
                              family="Arial Black"),
                name="Target label",
                hoverinfo="skip",
                showlegend=False,
                legendgroup="target",
            ))

        # Distance uncertainty was previously drawn as a 41-marker
        # "cigar" plus a thicker axial line segment along the viewing
        # ray near the target.  Combined with the dotted ray itself
        # this read as visual noise.  The numeric uncertainty is now
        # surfaced in the mid-ray "<object> · <distance> ± <err> ly"
        # label and in the chosen-target ring's hover text — that's
        # enough.  Pulled here to keep the ray visually clean; restore
        # is a single block re-add if anyone wants the cigar back.
        dist_err_ly_val = scene.get("dist_err_ly") or 0.0
        dist_ly_center = scene.get("dist_ly") or 0.0

        # (Depth-fan rings removed by request — the tilted heliocentric
        # circles around the chosen target plus the lighter "nearest"
        # and "farthest" companion rings are no longer drawn.  Distance
        # context now lives in the mid-ray label, the dotted distance
        # rings around Earth / the Galactic Center, and the per-pin
        # hover info on background sticks.)

    # --- Push-pin depth sticks for background objects ---
    # Objects from the picker with distance > chosen target, drawn at
    # their real galactic position behind the image plane and joined to
    # their exact pixel position on the photo rectangle.
    pins = scene.get("background_pins") or []
    if pins:
        px_xs, px_ys, px_zs = [], [], []
        tx_xs, tx_ys, tx_zs = [], [], []
        line_xs, line_ys, line_zs = [], [], []
        hover_texts: list[str] = []
        for pin in pins:
            ax, ay, az = pin["anchor_xyz"]
            tx, ty, tz = pin["target_xyz"]
            tx_xs.append(tx); tx_ys.append(ty); tx_zs.append(tz)
            px_xs.append(ax); px_ys.append(ay); px_zs.append(az)
            line_xs.extend([ax, tx, None])
            line_ys.extend([ay, ty, None])
            line_zs.extend([az, tz, None])
            d = pin.get("dist_ly", 0.0)
            if d < 1e6:
                dstr = f"{d:,.0f} ly"
            elif d < 1e9:
                dstr = f"{d/1e6:.2f} Mly"
            else:
                dstr = f"{d/1e9:.2f} Gly"
            src = pin.get("dist_source_hint", "")
            hover_texts.append(
                f"<b>{pin['name']}</b><br>"
                f"Type: {pin.get('otype', '—')}<br>"
                f"Distance: {dstr}"
                + (f" ({src})" if src else ""))

        # Sticks (lines from photo-plane pixel anchor → object position)
        fig.add_trace(go.Scatter3d(
            x=line_xs, y=line_ys, z=line_zs,
            mode="lines",
            line=dict(color="rgba(170,190,230,0.55)", width=2),
            name="Depth sticks",
            hoverinfo="skip",
            showlegend=False,
            legendgroup="background",
        ))
        # Anchor dots on the photo plane (small, subtle)
        fig.add_trace(go.Scatter3d(
            x=px_xs, y=px_ys, z=px_zs,
            mode="markers",
            marker=dict(size=3, color="#aac0e6", opacity=0.9,
                        line=dict(width=0)),
            name="Photo-plane anchors",
            hoverinfo="skip",
            showlegend=False,
            legendgroup="background",
        ))
        # Object markers at their real 3D position.  Per-point
        # textposition picked from _textposition_for so the labels
        # don't all pile at the same corner when many pins align.
        pin_names = [p["name"] for p in pins]
        pin_positions = [_textposition_for(px, py, pz)
                         for px, py, pz in zip(tx_xs, tx_ys, tx_zs)]
        fig.add_trace(go.Scatter3d(
            x=tx_xs, y=tx_ys, z=tx_zs,
            mode="markers+text",
            marker=dict(size=7, color="#ffb3d9", opacity=0.95,
                        line=dict(width=0.5, color="#ffffff")),
            text=pin_names,
            textposition=pin_positions,
            textfont=dict(color="#ffd5ee", size=9),
            hovertext=hover_texts,
            hoverinfo="text",
            name="Background objects",
            legendgroup="background",
            legendgrouptitle_text="Background",
        ))

    # --- Constellation stick figures (near-Earth, galactic mode) ---
    # When the camera is looking at something local, overlay the IAU
    # constellation containing the target as connecting lines on a
    # ~800-ly shell.  Turns an abstract coordinate plot into the
    # familiar sky shape the astrophotographer actually knows.
    const_lines = scene.get("constellation_lines")
    if (const_lines and mode is ViewMode.GALACTIC
            and const_lines.get("x")):
        try:
            fig.add_trace(go.Scatter3d(
                x=const_lines["x"],
                y=const_lines["y"],
                z=const_lines["z"],
                mode="lines",
                line=dict(color="rgba(170,200,255,0.55)", width=2),
                name=f"Constellation: {const_lines['name']}",
                hovertext=f"Stick figure of {const_lines['name']}"
                          f" on {const_lines['shell_ly']:.0f} ly shell",
                hoverinfo="text",
                legendgroup="references",
                legendgrouptitle_text="References",
            ))
        except Exception:
            pass

    # --- Layout ---
    title = scene.get("title", "Svenesis GalacticView 3D")
    if mode is ViewMode.GALACTIC:
        unit_label = "Linear scale — light years"
    else:
        # P4.12 — show the active distance metric so users always
        # know what the scene's distances mean.  Light-travel is
        # the default and least surprising; flag the others
        # explicitly so people don't quietly misread positions.
        metric_now = scene.get("distance_metric", "light-travel")
        metric_label = {
            "light-travel": "light-travel",
            "comoving": "comoving (proper distance now)",
            "angular-diameter": "angular-diameter (apparent size)",
        }.get(metric_now, metric_now)
        unit_label = (
            f"Log scale — {metric_label} ly "
            "(compressed beyond 1 Mly)"
        )

    # Adaptive zoom for nearby targets in galactic mode. The default view
    # spans the full 50,000-ly galaxy, so a star at 100 ly (0.1 scene units)
    # is indistinguishable from Earth. If the photo is within ~10,000 ly,
    # tighten the axis ranges to a box around Earth + photo so the frame
    # fills the view.
    # Hide the xyz grid and tick labels.  Distance rings + the compass
    # rose communicate scale far more effectively for an astronomy
    # viewer than a linear/log numeric grid does.  Axis-range control is
    # still kept (it's used by the adaptive near-target zoom and by the
    # NavigationPad's zoom-past-near-clip trick).
    axis_base = dict(
        backgroundcolor="#0a0a0a",
        gridcolor="rgba(0,0,0,0)",
        color="rgba(0,0,0,0)",
        showbackground=False,
        showgrid=False,
        zeroline=False,
        showspikes=False,
        showticklabels=False,
        showline=False,
        visible=False,
        title=dict(text=""),
    )
    xaxis_kw = dict(axis_base)
    yaxis_kw = dict(axis_base)
    zaxis_kw = dict(axis_base)
    aspect_kw: dict = dict(aspectmode="data")

    if mode is ViewMode.GALACTIC and photo_center_pre is not None:
        pc_mag = math.sqrt(photo_center_pre[0] ** 2
                           + photo_center_pre[1] ** 2
                           + photo_center_pre[2] ** 2)
        # In galactic mode `scale_dist` is just dist_ly / 1000, so
        # pc_mag (in scene units) == target_distance_ly / 1000.
        # Tier the adaptive box by photo distance:
        #   sub-kly target  → very tight box, ±500 ly floor.
        #     The full Milky Way arms become visual noise at this
        #     scale (distances are 100-1000× the target's distance),
        #     so we'd rather not center the scene on something that
        #     the user can't even see.  Suppression of the arms in
        #     this tier is left to the JS LOD fade below.
        #   1-10 kly target → previous behaviour (±4 kly floor).
        #   ≥10 kly target  → no override (full ±50 kly disk).
        if pc_mag < 1.0:        # target ≤ 1 kly
            box = max(pc_mag * 2.5, 0.5)   # ±500 ly floor
            xaxis_kw["range"] = [
                min(-box, photo_center_pre[0] - box),
                max(box, photo_center_pre[0] + box)]
            yaxis_kw["range"] = [
                min(-box, photo_center_pre[1] - box),
                max(box, photo_center_pre[1] + box)]
            zaxis_kw["range"] = [-box * 0.6, box * 0.6]
            aspect_kw = dict(aspectmode="manual",
                             aspectratio=dict(x=1.0, y=1.0, z=0.55))
        elif pc_mag < 10.0:     # target 1-10 kly
            box = max(pc_mag * 2.2, 4.0)   # ±4 kly floor
            xaxis_kw["range"] = [
                min(-box, photo_center_pre[0] - box),
                max(box, photo_center_pre[0] + box)]
            yaxis_kw["range"] = [
                min(-box, photo_center_pre[1] - box),
                max(box, photo_center_pre[1] + box)]
            zaxis_kw["range"] = [-box * 0.6, box * 0.6]
            aspect_kw = dict(aspectmode="manual",
                             aspectratio=dict(x=1.0, y=1.0, z=0.55))

    # Mode label → small fixed HUD at the bottom-left.  Paper refs so
    # it stays put during camera orbits.
    hud_annotations = [
        dict(text=unit_label, showarrow=False,
             xref="paper", yref="paper", x=0.01, y=0.02,
             xanchor="left", yanchor="bottom",
             font=dict(color="#888", size=10)),
    ]

    # P3.7 — pre-framed initial camera for nearby targets.  Default
    # eye = (1.6, 1.6, 1.0) is sized for the full 50-kly disk; for a
    # sub-kly target it leaves the photo as an invisible dot at
    # origin until the user manually zooms in.  Detect this and
    # start with a tighter eye so the adaptive box already fills the
    # view.  Distant targets unchanged.
    initial_eye = dict(x=1.6, y=1.6, z=1.0)
    if (mode is ViewMode.GALACTIC and photo_center_pre is not None):
        pc_mag_init = math.sqrt(photo_center_pre[0] ** 2
                                + photo_center_pre[1] ** 2
                                + photo_center_pre[2] ** 2)
        if pc_mag_init < 1.0:        # ≤ 1 kly target
            initial_eye = dict(x=0.55, y=0.55, z=0.35)
        elif pc_mag_init < 10.0:     # 1-10 kly target
            initial_eye = dict(x=0.95, y=0.95, z=0.6)

    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(color="#e0e0e0", size=15)),
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#0a0a0a",
        annotations=hud_annotations,
        scene=dict(
            domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            xaxis=xaxis_kw,
            yaxis=yaxis_kw,
            zaxis=zaxis_kw,
            camera=dict(eye=initial_eye),
            **aspect_kw,
        ),
        legend=dict(bgcolor="rgba(30,30,30,0.6)",
                    font=dict(color="#ddd", size=9),
                    itemsizing="constant",
                    groupclick="toggleitem"),
        margin=dict(l=0, r=0, b=0, t=40),
    )
    # P4.12 — reset metric so a subsequent call (or an unrelated
    # scale_dist invocation in the data pipeline) sees the default.
    _ACTIVE_DISTANCE_METRIC = _prev_metric
    return fig


# ---------------------------------------------------------------------------
# Matplotlib fallback renderer (static PNG)
# ---------------------------------------------------------------------------
def render_matplotlib_galaxy(scene: dict, out_path: str,
                             width: int = 1400, height: int = 1000,
                             dpi: int = 150) -> None:
    mode: ViewMode = scene["mode"]
    fig = Figure(figsize=(width / dpi, height / dpi),
                 dpi=dpi, facecolor="#0a0a0a")
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d", facecolor="#0a0a0a")

    # Spiral arms
    for arm in SPIRAL_ARMS:
        pts = arm_scene_points(arm, mode, n_pts=80)
        ax.plot(pts["x"], pts["y"], pts["z"],
                color=arm["col"],
                linewidth=3 if arm.get("is_local") else 1.5,
                label=arm["name"])

    # Disk stars
    disk = generate_disk_stars(mode, n=300)
    ax.scatter(disk["x"], disk["y"], disk["z"],
               c="#aabbdd", s=3, alpha=0.5)

    # Galactic centre
    gc_x = scale_dist(EARTH_TO_GC_LY, mode)
    ax.scatter([gc_x], [0], [0], c="#ffaa33", s=80, marker="D")

    # Earth
    ax.scatter([0], [0], [0], c="#55aaff", s=60, marker="o",
               edgecolors="white")

    # Neighbor galaxies in cosmic mode
    if scene.get("show_neighbors", mode is ViewMode.COSMIC):
        for g in NEIGHBOR_GALAXIES:
            x, y, z = gal_to_xyz(g["l"], g["b"],
                                 scale_dist(g["dist_ly"], mode))
            ax.scatter([x], [y], [z], c=g["col"], s=40, alpha=0.8)
            ax.text(x, y, z, g["name"], color="#ccbb99", fontsize=7)

    # Photo rectangle
    corners = scene.get("photo_corners")
    if corners and len(corners) == 4:
        xs = [c[0] for c in corners] + [corners[0][0]]
        ys = [c[1] for c in corners] + [corners[0][1]]
        zs = [c[2] for c in corners] + [corners[0][2]]
        ax.plot(xs, ys, zs, color="#ffee88", linewidth=2.5)

    photo_center = scene.get("photo_center_xyz")
    if photo_center is not None:
        ax.plot([0, photo_center[0]], [0, photo_center[1]],
                [0, photo_center[2]],
                color="#ffcc44", linewidth=1.5, linestyle=":")

    ax.set_title(scene.get("title", "GalacticView 3D"),
                 color="#e0e0e0")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.label.set_color("#aaa")
        axis.pane.set_facecolor("#0a0a0a")
    ax.tick_params(colors="#888")
    ax.set_xlabel("X (toward GC)")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z (gal. north)")
    ax.legend(loc="upper left", fontsize=7, facecolor="#1e1e1e",
              edgecolor="#444", labelcolor="#ccc")

    fig.tight_layout()
    canvas.print_png(out_path)


# ---------------------------------------------------------------------------
# Plotly cache helpers (same pattern as CosmicDepth 3D)
# ---------------------------------------------------------------------------
_PLOTLY_CACHE_DIR: str | None = None
# H5: track the last sweep timestamp separately from the cache-dir memo.
# Previously the sweep lived inside the memoised init path and therefore
# ran exactly once per process — a long-running Siril session (hours or
# days with the plugin loaded) would never re-sweep, defeating the
# purpose of the 24 h cleanup.  Now the dir is memoised; the sweep
# itself re-runs at most once per SWEEP_INTERVAL_S.
_PLOTLY_LAST_SWEEP_TS: float = 0.0
_PLOTLY_SWEEP_INTERVAL_S: float = 3600.0  # run the sweep at most hourly
_PLOTLY_SWEEP_MAX_AGE_S: float = 24 * 3600.0  # delete files older than this


def _sweep_orphan_scene_html(d: str) -> None:
    """Delete scene_*.html files in ``d`` older than 24 h.

    Each render writes scene_<pid>_<id>.html (~200 KB – 5 MB depending on
    candidate count / photo resolution); the current session cleans up
    its own previous file inside show_html(), but process crashes, kills,
    or Siril plugin reloads leave debris here forever.  Called
    opportunistically from _plotly_cache_dir().
    """
    global _PLOTLY_LAST_SWEEP_TS
    import time as _time
    now = _time.time()
    if now - _PLOTLY_LAST_SWEEP_TS < _PLOTLY_SWEEP_INTERVAL_S:
        return
    _PLOTLY_LAST_SWEEP_TS = now
    try:
        import glob
        cutoff = now - _PLOTLY_SWEEP_MAX_AGE_S
        removed = 0
        for orphan in glob.iglob(os.path.join(d, "scene_*.html")):
            try:
                if os.path.getmtime(orphan) < cutoff:
                    os.remove(orphan)
                    removed += 1
            except OSError:
                # File vanished mid-sweep (another process) or perms —
                # nothing we can do, next call will retry.
                continue
        if removed:
            sys.stderr.write(
                f"[GalacticView3D] plotly cache sweep removed "
                f"{removed} orphan scene HTML file(s).\n")
    except Exception as e:
        sys.stderr.write(
            f"[GalacticView3D] plotly cache sweep skipped: {e}\n")


def _plotly_cache_dir() -> str:
    global _PLOTLY_CACHE_DIR
    if _PLOTLY_CACHE_DIR and os.path.isfile(
            os.path.join(_PLOTLY_CACHE_DIR, "plotly.min.js")):
        # Fast path on hot reruns — but still give the sweep a chance
        # (it rate-limits itself via _PLOTLY_LAST_SWEEP_TS).
        _sweep_orphan_scene_html(_PLOTLY_CACHE_DIR)
        return _PLOTLY_CACHE_DIR
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "svenesis_galacticview_plotly")
    os.makedirs(d, exist_ok=True)
    js_path = os.path.join(d, "plotly.min.js")
    if not os.path.isfile(js_path):
        try:
            from plotly.offline import get_plotlyjs
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(get_plotlyjs())
        except Exception as e:
            sys.stderr.write(
                f"[GalacticView3D] plotly.min.js cache write failed: {e}\n")

    _sweep_orphan_scene_html(d)
    _PLOTLY_CACHE_DIR = d
    return d


# ---------------------------------------------------------------------------
# Camera-preset + animation bootstrap JS
# ---------------------------------------------------------------------------
# Installed as ``window.gv3d`` on the rendered Plotly page, driven from
# the Python side via preview_widget.run_js(...).  The Python code
# decides *which* preset to play; all the per-frame math runs in the
# browser so Plotly doesn't round-trip through Python for each rAF tick.
#
# Key methods:
#   gv3d.preset(name)   → snap camera to a named preset
#   gv3d.flyTo(name)    → animate camera over ~1.4 s (ease-in-out) to a
#                         named preset.  Used by all preset buttons so
#                         the user sees a fluid transition instead of a
#                         jump — the single thing that most sells the
#                         3D-ness of the scene.
#   gv3d.autoRotate(on) → toggle a slow azimuthal spin (non-blocking,
#                         cancels on any user input).
#
# Named presets ("reset" / "earth_pov" / "top" / "side"):
#   - reset     — default iso view (matches NavigationPad's ⟲)
#   - earth_pov — camera at Earth, looking down the viewing ray.  The
#                 money shot: shows which part of the galaxy the photo
#                 is looking *through*.
#   - top       — galactic-plane top-down view.  Shows arm membership.
#   - side      — along +y looking across the disk.  Shows b-latitude.
_CAMERA_BOOTSTRAP_JS = r"""
<script>
(function() {
    // Capture any uncaught JS exception and surface it through the
    // [GV3D] logging channel so we see it in the Python Log tab
    // instead of it dying silently inside the embedded WebEngine.
    window.addEventListener('error', function(ev) {
        try {
            console.log('[GV3D] JS error: ' +
                (ev && ev.message ? ev.message : '(no message)') +
                ' at ' + (ev && ev.filename ? ev.filename : '?') +
                ':' + (ev && ev.lineno ? ev.lineno : '?'));
        } catch (e) {}
    });
    window.addEventListener('unhandledrejection', function(ev) {
        try {
            var r = ev && ev.reason;
            console.log('[GV3D] JS promise rejection: ' +
                (r && r.message ? r.message : String(r)));
        } catch (e) {}
    });

    // Photo centre in **scene world coordinates**.  Null when no photo
    // has been projected yet (e.g. WCS failure).  Injected from Python.
    var PHOTO = __PHOTO_CENTER__;
    // P2.6 — arm centroids in scene coords, keyed by arm name.
    // Used by presetCamera('arm:<name>') to fly to that arm.
    // Empty object in cosmic mode (arms collapse to nothing there).
    var ARMS = __ARMS__;
    // View mode ("galactic"/"cosmic") so the scale-bar knows how to
    // translate scene units → light-years.
    var MODE = __MODE__;
    // Default eye for the "reset" preset — mirrors build_galaxy_figure's
    // initial scene.camera.eye so Reset goes back to the exact startup
    // view even after axis ranges have been shrunk by the zoom trick.
    var DEFAULT_EYE = {x: 1.6, y: 1.6, z: 1.0};
    var DEFAULT_UP = {x: 0, y: 0, z: 1};
    var DEFAULT_CENTER = {x: 0, y: 0, z: 0};

    function _plot() { return document.querySelector('.js-plotly-plot'); }

    function _box() {
        var gd = _plot();
        if (!gd || !gd._fullLayout || !gd._fullLayout.scene) return null;
        var sc = gd._fullLayout.scene;
        function ax(a) {
            if (!a || !a.range || a.range.length !== 2) return null;
            return [+a.range[0], +a.range[1]];
        }
        var xr = ax(sc.xaxis), yr = ax(sc.yaxis), zr = ax(sc.zaxis);
        if (!xr || !yr || !zr) return null;
        return {
            gd: gd,
            cx: (xr[0] + xr[1]) / 2,
            cy: (yr[0] + yr[1]) / 2,
            cz: (zr[0] + zr[1]) / 2,
            hx: Math.max(1e-6, (xr[1] - xr[0]) / 2),
            hy: Math.max(1e-6, (yr[1] - yr[0]) / 2),
            hz: Math.max(1e-6, (zr[1] - zr[0]) / 2),
        };
    }

    function toCam(b, x, y, z) {
        return {
            x: (x - b.cx) / b.hx,
            y: (y - b.cy) / b.hy,
            z: (z - b.cz) / b.hz,
        };
    }
    function lenV(v) {
        return Math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z);
    }
    function normV(v) {
        var l = lenV(v);
        if (l < 1e-9) return {x:0, y:0, z:1};
        return {x: v.x/l, y: v.y/l, z: v.z/l};
    }
    function subV(a, b) { return {x:a.x-b.x, y:a.y-b.y, z:a.z-b.z}; }
    function addV(a, b) { return {x:a.x+b.x, y:a.y+b.y, z:a.z+b.z}; }
    function mulV(a, s) { return {x:a.x*s, y:a.y*s, z:a.z*s}; }

    function presetCamera(name) {
        if (name === 'reset') {
            return {eye: DEFAULT_EYE, up: DEFAULT_UP, center: DEFAULT_CENTER};
        }
        if (name === 'top') {
            return {eye: {x:0, y:0, z:2.2}, up: {x:0, y:1, z:0},
                    center: {x:0, y:0, z:0}};
        }
        if (name === 'side') {
            return {eye: {x:0, y:2.2, z:0}, up: {x:0, y:0, z:1},
                    center: {x:0, y:0, z:0}};
        }
        // P2.6 — fly to a named spiral arm.  The arm's centroid sits
        // somewhere inside the disk; we want to look at it from
        // outside the disk, slightly above the plane.  Eye = the
        // centroid pushed outward + up; center = the centroid.
        if (name && name.indexOf('arm:') === 0) {
            var armName = name.slice(4);
            var mid = ARMS[armName];
            if (!mid) {
                if (window.console) {
                    console.warn('gv3d: unknown arm preset', armName);
                }
                return null;
            }
            var b1 = _box();
            if (!b1) { return null; }
            var midCam = toCam(b1, mid[0], mid[1], mid[2]);
            // Push outward from origin (in camera space), with a
            // small +z tilt so we look slightly down on the arm.
            var midLen = lenV(midCam);
            var outScale = midLen > 1e-6 ? (1.6 / midLen) : 1.0;
            var armEye = {
                x: midCam.x * outScale,
                y: midCam.y * outScale,
                z: midCam.z * outScale + 0.6,
            };
            return {
                eye: armEye,
                center: midCam,
                up: {x: 0, y: 0, z: 1},
            };
        }
        // Earth-POV wants the photo centre as its look-at target.
        // Degrades gracefully (uses a sensible default direction)
        // when no photo has been projected yet.
        var b = _box();
        if (!b) {
            if (window.console) { console.warn('gv3d: scene box not ready'); }
            return null;
        }
        var earthCam = toCam(b, 0, 0, 0);
        var photoCam, dir;
        if (PHOTO) {
            photoCam = toCam(b, PHOTO[0], PHOTO[1], PHOTO[2]);
            dir = normV(subV(photoCam, earthCam));
            // If photo coincides with Earth (dist ≈ 0 in scene units),
            // dir collapses to (0,0,1) from normV's fallback — that's
            // fine for Earth POV.
        } else {
            // Fallback direction: look roughly toward galactic centre
            // for galactic mode, or along +x for cosmic mode.
            dir = (MODE === 'galactic')
                ? {x: 1, y: 0, z: 0}
                : {x: 1, y: 0, z: 0};
            photoCam = addV(earthCam, mulV(dir, 0.5));
            if (window.console) {
                console.info('gv3d: earth_pov using fallback direction '
                             + '(no PHOTO set)');
            }
        }
        // Up vector: +z unless the line of sight is within ~15° of
        // vertical, in which case roll to +y to avoid gimbal lock.
        var up = (Math.abs(dir.z) > 0.95) ? {x:0, y:1, z:0}
                                          : {x:0, y:0, z:1};
        if (name === 'earth_pov') {
            // Option B — over-the-shoulder, Earth as foreground.
            //
            // Desired framing (user spec):
            //   "I'm behind Earth, I see Earth not far away in front
            //    of me, and I see the line from Earth to the photo."
            //
            // Geometry:
            //   eye    = Earth − dir·BACK + perp·SIDE
            //   center = Earth
            //   up     = +z world
            //
            // The critical bit: the camera is offset perpendicular to
            // the LOS (`perp`), NOT just vertically.  A pure +z lift
            // fails when the LOS is itself near-vertical (e.g. a
            // photo near a galactic pole — +z lift ends up parallel
            // to dir, so the camera stays on-axis and the LOS
            // collapses to a pixel).  We compute `perp = dir × ẑ` —
            // a genuine perpendicular that always gives us a true
            // third-person side-view of the LOS — with a fallback
            // to +x when dir is itself ≈ ẑ.
            //
            // BACK + SIDE magnitudes are chosen so |eye − Earth| ≈
            // 1.6 — outside the scene cube (Plotly's perspective
            // needs this to render) but closer than Reset so Earth
            // reads as a foreground subject rather than a tiny dot.
            var BACK = 1.2;
            var SIDE = 1.1;
            // perp = dir × (0,0,1) → horizontal perpendicular to LOS.
            var perp = {
                x: dir.y * 1.0 - dir.z * 0.0,
                y: dir.z * 0.0 - dir.x * 1.0,
                z: dir.x * 0.0 - dir.y * 0.0,
            };
            var perpLen = Math.sqrt(perp.x*perp.x + perp.y*perp.y
                                    + perp.z*perp.z);
            if (perpLen < 0.05) {
                // LOS is ≈ +z — use +x as a stable fallback.
                perp = {x: 1, y: 0, z: 0};
            } else {
                perp = {x: perp.x/perpLen,
                        y: perp.y/perpLen,
                        z: perp.z/perpLen};
            }
            // Note: Plotly's camera.center is NOT a look-at point —
            // it acts as a pivot/offset that shifts the whole scene
            // in the viewport.  Setting it to earthCam (which is off
            // origin when axis ranges are asymmetric) pushes the
            // rendered scene to one side of the plot area.  So we
            // keep center at (0,0,0) and instead use eye relative to
            // origin (not relative to earthCam) for the camera
            // position.  The perpendicular offset still guarantees
            // the LOS isn't collapsed.
            var eye = {
                x: -dir.x * BACK + perp.x * SIDE,
                y: -dir.y * BACK + perp.y * SIDE,
                z: -dir.z * BACK + perp.z * SIDE,
            };
            if (window.console) {
                console.log('gv3d earth_pov (option B, side-offset):',
                    'earthCam=', JSON.stringify(earthCam),
                    'eye=', JSON.stringify(eye),
                    'center=', '(0,0,0)',
                    'dir=', JSON.stringify(dir),
                    'perp=', JSON.stringify(perp),
                    '|eye|=',
                    Math.sqrt(eye.x*eye.x + eye.y*eye.y
                              + eye.z*eye.z).toFixed(3),
                    'PHOTO=', PHOTO);
            }
            return {
                eye: eye,
                center: {x: 0, y: 0, z: 0},   // scene geometric centre
                up: {x: 0, y: 0, z: 1},
            };
        }
        return null;
    }

    function snapTo(target) {
        var gd = _plot();
        if (!gd || !target) { return; }
        Plotly.relayout(gd, {
            'scene.camera.eye': target.eye,
            'scene.camera.up': target.up,
            'scene.camera.center': target.center,
        });
    }

    var _flyAF = null;
    function flyToTarget(target, durationMs) {
        if (_flyAF) { cancelAnimationFrame(_flyAF); _flyAF = null; }
        var gd = _plot();
        if (!gd || !target) { return; }
        var sc = gd._fullLayout.scene;
        var cam = (sc && sc.camera) || {};
        var fromEye = {x:+cam.eye.x, y:+cam.eye.y, z:+cam.eye.z};
        var fromUp = {x:+(cam.up && cam.up.x || 0),
                       y:+(cam.up && cam.up.y || 0),
                       z:+(cam.up && cam.up.z || 1)};
        var fromCtr = {x:+(cam.center && cam.center.x || 0),
                        y:+(cam.center && cam.center.y || 0),
                        z:+(cam.center && cam.center.z || 0)};
        var start = performance.now();
        function lerp(a, b, t) { return a + (b - a) * t; }
        function lerpV(a, b, t) {
            return {x: lerp(a.x, b.x, t),
                    y: lerp(a.y, b.y, t),
                    z: lerp(a.z, b.z, t)};
        }
        // `up` is special: linearly interpolating between two unit
        // vectors yields non-unit intermediates, which Plotly can
        // misinterpret as camera roll — on top→earth_pov transitions
        // (up=(0,1,0) → up=(0,0,1)) the half-way vector (0, 0.5, 0.5)
        // leaves the camera rolled 45° and the scene sometimes ends
        // up rendered outside the viewport.  Cheap fix: snap `up` at
        // the very start of the fly, and lerp only eye/center.  The
        // camera pose at t=0 already matches the current view, so
        // there's no visual discontinuity — just no roll artefact.
        Plotly.relayout(gd, {'scene.camera.up': target.up});
        function step(now) {
            var t = Math.min(1, (now - start) / durationMs);
            // Cubic ease in-out for a smooth, "this is cinematic" feel.
            var e = (t < 0.5) ? (4 * t * t * t)
                              : (1 - Math.pow(-2 * t + 2, 3) / 2);
            Plotly.relayout(gd, {
                'scene.camera.eye': lerpV(fromEye, target.eye, e),
                'scene.camera.center': lerpV(fromCtr, target.center, e),
            });
            if (t < 1) { _flyAF = requestAnimationFrame(step); }
            else { _flyAF = null; }
        }
        _flyAF = requestAnimationFrame(step);
    }

    var _rotAF = null;
    var _rotLastT = 0;
    var _ROT_RAD_PER_SEC = 0.12;
    function stopAutoRotate() {
        if (_rotAF) {
            cancelAnimationFrame(_rotAF);
            _rotAF = null;
            if (typeof _gvlog === 'function') { _gvlog('auto-rotate stop'); }
        }
    }
    function startAutoRotate() {
        stopAutoRotate();
        var gd = _plot();
        if (!gd) { return; }
        if (typeof _gvlog === 'function') { _gvlog('auto-rotate start'); }
        _rotLastT = performance.now();
        function tick(now) {
            var dt = Math.min(0.1, (now - _rotLastT) / 1000);
            _rotLastT = now;
            var sc = gd._fullLayout && gd._fullLayout.scene;
            if (!sc || !sc.camera) { return; }
            var eye = sc.camera.eye;
            var ctr = sc.camera.center || {x:0, y:0, z:0};
            var dx = eye.x - ctr.x, dy = eye.y - ctr.y;
            var r = Math.sqrt(dx*dx + dy*dy);
            var phi = Math.atan2(dy, dx) + _ROT_RAD_PER_SEC * dt;
            Plotly.relayout(gd, {
                'scene.camera.eye': {
                    x: ctr.x + r * Math.cos(phi),
                    y: ctr.y + r * Math.sin(phi),
                    z: eye.z,
                },
            });
            _rotAF = requestAnimationFrame(tick);
        }
        _rotAF = requestAnimationFrame(tick);
    }

    // Idle auto-rotate: start after 10 s of no mouse/key/touch activity;
    // kill on any input.  This is the "ambient 3D" cue for a desktop
    // viewer — like a screensaver, but only when the user is clearly
    // not interacting.
    var _idleTimer = null;
    var _IDLE_MS = 10000;
    function _kickIdle() {
        stopAutoRotate();
        if (_idleTimer) { clearTimeout(_idleTimer); }
        _idleTimer = setTimeout(startAutoRotate, _IDLE_MS);
    }
    var _EVENTS = ['mousedown','mousemove','mousewheel','wheel',
                   'touchstart','touchmove','keydown'];
    _EVENTS.forEach(function(evt) {
        window.addEventListener(evt, _kickIdle, {passive: true, capture: true});
    });

    // -----------------------------------------------------------
    // Scale bar overlay (context-sensitive ruler)
    // -----------------------------------------------------------
    // Draws a floating HTML bar pinned to the top-left of the plot
    // DIV that represents ~12% of the visible scene width in the
    // current mode.  Updates whenever the camera moves.  Not a
    // Plotly trace — a plain absolutely-positioned <div> so it
    // doesn't interact with hover/legend events.
    function _unitsToLy(units) {
        // Inverse of scale_dist() from the Python side.  Galactic
        // mode is linear; cosmic is linear up to 10 scene units
        // (= 1 Mly) then log-compressed beyond.
        if (MODE === 'cosmic') {
            if (units <= 10.0) { return units * 100000.0; }
            return Math.pow(10, (units - 10.0) / 8.0) * 1e6;
        }
        return units * 1000.0;  // galactic
    }
    function _fmtLy(ly) {
        if (ly >= 1e9) return (ly / 1e9).toFixed(2) + ' Gly';
        if (ly >= 1e6) return (ly / 1e6).toFixed(2) + ' Mly';
        if (ly >= 1e3) return (ly / 1e3).toFixed(0) + ' kly';
        return Math.round(ly) + ' ly';
    }
    // P3.10 — redshift estimate for a given light-travel distance
    // in light-years.  Low-z linear approximation
    //   z ≈ d / (c / H0) ≈ d / 1.452e10 ly.
    // Accurate enough for a scale-bar tag; the high-z hover labels
    // use the proper Planck18 inversion via Python.
    function _zFromLy(ly) {
        if (!isFinite(ly) || ly <= 0) { return 0; }
        return ly / 1.452e10;
    }
    function _fmtZ(z) {
        if (z < 0.001) return z.toFixed(5);
        if (z < 0.01)  return z.toFixed(4);
        if (z < 1.0)   return z.toFixed(3);
        return z.toFixed(2);
    }
    function _niceLy(ly) {
        // Pick the nearest 1/2/5 * 10^n ly.
        if (ly <= 0 || !isFinite(ly)) { return 1; }
        var exp = Math.floor(Math.log10(ly));
        var base = Math.pow(10, exp);
        var mant = ly / base;
        var nice = 1;
        if      (mant < 1.5) nice = 1;
        else if (mant < 3.5) nice = 2;
        else if (mant < 7.5) nice = 5;
        else                  nice = 10;
        return nice * base;
    }
    var _scaleBar = null;
    function _ensureScaleBar() {
        if (_scaleBar) { return _scaleBar; }
        var gd = _plot();
        if (!gd) { return null; }
        var host = gd.parentElement || document.body;
        // Make sure the host can position absolutely-placed children.
        if (host && host !== document.body) {
            var cs = host.style;
            if (!cs.position || cs.position === 'static') {
                cs.position = 'relative';
            }
        }
        var d = document.createElement('div');
        d.style.position = 'absolute';
        d.style.left = '12px';
        d.style.top = '48px';
        d.style.zIndex = '5';
        d.style.color = '#d8d8e8';
        d.style.font = '11px Arial, sans-serif';
        d.style.pointerEvents = 'none';
        d.style.userSelect = 'none';
        d.style.padding = '4px 6px';
        d.style.background = 'rgba(20,20,28,0.55)';
        d.style.border = '1px solid rgba(180,190,220,0.25)';
        d.style.borderRadius = '3px';
        d.style.textShadow = '0 1px 1px #000';
        var rule = document.createElement('div');
        rule.style.height = '2px';
        rule.style.background = 'rgba(220,220,240,0.85)';
        rule.style.margin = '3px 0 2px 0';
        rule.style.width = '80px';
        var lbl = document.createElement('div');
        lbl.textContent = '— scale —';
        d.appendChild(lbl);
        d.appendChild(rule);
        host.appendChild(d);
        _scaleBar = {root: d, rule: rule, label: lbl};
        return _scaleBar;
    }
    function updateScaleBar() {
        var gd = _plot();
        if (!gd || !gd._fullLayout) { return; }
        var sc = gd._fullLayout.scene;
        if (!sc) { return; }
        var sb = _ensureScaleBar();
        if (!sb) { return; }
        // Visible half-width in scene units along X.
        var xr = sc.xaxis && sc.xaxis.range;
        if (!xr || xr.length !== 2) { return; }
        var width_units = Math.abs(xr[1] - xr[0]);
        // Camera distance correction: further away → bar represents
        // more units at the same pixel width.  Use eye magnitude in
        // scene-normalised coordinates as a cheap proxy.
        var cam = sc.camera && sc.camera.eye;
        var camMag = cam ? Math.sqrt(cam.x*cam.x + cam.y*cam.y
                                     + cam.z*cam.z) : 1.5;
        var target_units = width_units * 0.12 * (camMag / 1.5);
        var target_ly = _unitsToLy(target_units);
        var nice_ly = _niceLy(target_ly);
        // Pixel width = (nice_ly / target_ly) * 12% of plot width.
        var plotRect = gd.getBoundingClientRect();
        var pct = (nice_ly / Math.max(1e-9, target_ly)) * 0.12;
        var px = Math.max(20, Math.min(220,
                    Math.round(plotRect.width * pct)));
        sb.rule.style.width = px + 'px';
        // P3.10 — append redshift annotation in cosmic mode for any
        // distance ≥ 100 Mly.  Below that z is so close to zero
        // it'd just be visual clutter.
        var lblText = _fmtLy(nice_ly);
        if (MODE === 'cosmic' && nice_ly >= 1e8) {
            lblText += '  ·  z ≈ ' + _fmtZ(_zFromLy(nice_ly));
        }
        sb.label.textContent = lblText;
    }

    // -----------------------------------------------------------
    // Spiral-arm LOD fade (galactic mode only)
    // -----------------------------------------------------------
    // The spiral-arm overlay is informative at default zoom but
    // dominates the scene when the camera is close to a sub-kly
    // target — at that scale the arms are visual noise about a
    // structure 100-1000× larger than what's being inspected.  Fade
    // arm + arm-name traces toward zero opacity once |scene.eye|
    // drops below ~1.6, fully gone by ~0.5.  Cosmic mode arms
    // collapse to a dot anyway, so the fade is short-circuited
    // there.
    var _armIdx = null;       // cached trace indices, computed once
    var _lastArmAlpha = -1;   // restyle dedup
    var _ARM_NAMES = {
        'Norma Arm': 1,
        'Scutum-Centaurus': 1,
        'Sagittarius Arm': 1,
        'Orion Arm (local)': 1,
        'Perseus Arm': 1,
        'Arm names': 1,
        // P1.1 extension: galactic-mode field stars + bulge are also
        // visual noise when zoomed close to a sub-kly target, so they
        // ride the same LOD fade as the arms.
        'Disk stars': 1,
        'Galactic bulge': 1,
    };
    function _findArmTraces(gd) {
        // Match Plotly traces against the SPIRAL_ARMS name table
        // (kept in sync with the Python side).  Returns an array of
        // trace indices to fade.
        var idxs = [];
        if (!gd || !gd.data) { return idxs; }
        for (var i = 0; i < gd.data.length; i++) {
            var t = gd.data[i];
            if (!t || !t.name) { continue; }
            if (_ARM_NAMES[t.name]) { idxs.push(i); }
        }
        return idxs;
    }
    function _updateArmFade() {
        if (MODE !== 'galactic') { return; }
        var gd = _plot();
        if (!gd || !gd._fullLayout || !gd._fullLayout.scene) { return; }
        if (_armIdx === null) {
            _armIdx = _findArmTraces(gd);
        }
        if (!_armIdx || _armIdx.length === 0) { return; }
        var cam = gd._fullLayout.scene.camera;
        if (!cam || !cam.eye) { return; }
        var e = cam.eye;
        var mag = Math.sqrt(e.x*e.x + e.y*e.y + e.z*e.z);
        // Linear ramp: full opacity at |eye| >= 1.6, zero at <= 0.5.
        var alpha;
        if (mag >= 1.6)      { alpha = 1.0; }
        else if (mag <= 0.5) { alpha = 0.0; }
        else                 { alpha = (mag - 0.5) / 1.1; }
        // Skip the restyle if the change is too small to see —
        // restyle is not free and we get called on every relayout.
        if (Math.abs(alpha - _lastArmAlpha) < 0.02) { return; }
        _lastArmAlpha = alpha;
        try {
            Plotly.restyle(gd, {opacity: alpha}, _armIdx);
        } catch (e) { /* ignore */ }
    }

    // Hook scene redraws — Plotly fires plotly_relayout whenever the
    // camera moves or the user resizes.  We refresh the scale bar
    // and zoom hint on every such event, plus prime them once after
    // the first paint.
    function hookRelayout() {
        var gd = _plot();
        if (!gd || !gd.on) {
            setTimeout(hookRelayout, 200);
            return;
        }
        gd.on('plotly_relayout', function(ev) {
            var mainTouched = true;
            if (ev && typeof ev === 'object') {
                mainTouched = false;
                for (var k in ev) {
                    if (k.indexOf('scene.') === 0 ||
                        k === 'scene' ||
                        k.indexOf('xaxis') === 0 ||
                        k.indexOf('yaxis') === 0 ||
                        k.indexOf('width') === 0 ||
                        k.indexOf('height') === 0 ||
                        k.indexOf('autosize') === 0) {
                        mainTouched = true;
                        break;
                    }
                }
            }
            if (mainTouched) {
                updateScaleBar();
                _updateZoomHint();
                _updateArmFade();
            }
        });
        updateScaleBar();
        _updateZoomHint();
        _updateArmFade();
    }

    // Context-aware hint text.  Plotly's default camera.eye magnitude
    // is ~2.39; mouse-wheel zoom-in shrinks it.  Once it drops below
    // ~0.6 (≈ 25% of default) the camera has pushed deep into the
    // scene and far-field references (photo rectangle, distance rings,
    // neighbor galaxies in cosmic mode) have fallen outside the
    // perspective frustum.  That's not a bug — it's standard 3D
    // projection — but the user's natural reaction is "where did they
    // go?".  So we retarget the top-right hint from the generic
    // "Lost?" nudge to an explanation + reset prompt when we detect
    // that state.
    var _lastZoomState = null;  // 'deep' | 'normal' — for edge-log only
    function _updateZoomHint() {
        var h = document.getElementById('gv3d-hint');
        if (!h) { return; }
        var gd = _plot();
        if (!gd || !gd.layout || !gd.layout.scene) { return; }
        var e = gd.layout.scene.camera && gd.layout.scene.camera.eye;
        if (!e) { return; }
        var mag = Math.sqrt(e.x*e.x + e.y*e.y + e.z*e.z);
        var state = (mag < 0.6) ? 'deep' : 'normal';
        if (state === 'deep') {
            h.textContent = 'Zoomed in — photo & rings off-frame · Press R to reset';
            h.style.borderColor = 'rgba(255,180,120,0.55)';
            h.style.background = 'rgba(40,26,16,0.72)';
        } else {
            h.textContent = 'Lost? Press R to reset view';
            h.style.borderColor = 'rgba(180,190,220,0.25)';
            h.style.background = 'rgba(20,20,28,0.55)';
        }
        // Log only on state change — avoids flooding the Log tab when
        // Plotly fires dozens of relayout events per mouse drag.
        if (state !== _lastZoomState) {
            if (typeof _gvlog === 'function') {
                _gvlog('zoom state: ' + state +
                       ' (|eye|=' + mag.toFixed(3) + ')');
            }
            _lastZoomState = state;
        }
    }
    hookRelayout();
    window.addEventListener('resize', function() {
        updateScaleBar();
    });

    // Pulse the "Viewing ray" trace — brighter, thicker, and solid
    // for ~1 s, then restore the dotted amber line.  Fired when we
    // land in Earth POV so the user sees which line in the figure IS
    // the line of sight.  No-op if the trace can't be found (e.g.
    // photo projection failed → no ray drawn).
    //
    // Two timer handles track the in-flight pulse so rapid preset
    // switches can cancel it cleanly (otherwise the restore fires
    // 1.2 s later and trashes newer state, or pulses stack).
    var _pulseDeferId = null;
    var _pulseRestoreId = null;
    var _pulseOrig = null;   // {idx, w, c, d} — remember to restore
    function _cancelPulse() {
        if (_pulseDeferId) { clearTimeout(_pulseDeferId); _pulseDeferId = null; }
        if (_pulseRestoreId) { clearTimeout(_pulseRestoreId); _pulseRestoreId = null; }
        // If we cancelled mid-pulse, put the trace back right now
        // rather than leaving it in the "loud" style.
        if (_pulseOrig) {
            var gd = _plot();
            if (gd && gd.data && gd.data[_pulseOrig.idx]) {
                try {
                    Plotly.restyle(gd, {
                        'line.width': _pulseOrig.w,
                        'line.color': _pulseOrig.c,
                        'line.dash': _pulseOrig.d,
                    }, [_pulseOrig.idx]);
                } catch (e) { /* ignore */ }
            }
            _pulseOrig = null;
        }
    }
    function _pulseViewingRay() {
        _cancelPulse();
        var gd = _plot();
        if (!gd || !gd.data) { return; }
        var idx = -1;
        for (var i = 0; i < gd.data.length; i++) {
            if (gd.data[i] && gd.data[i].name === 'Viewing ray') {
                idx = i; break;
            }
        }
        if (idx < 0) { return; }
        var ln = gd.data[idx].line || {};
        _pulseOrig = {
            idx: idx,
            w: ln.width || 2,
            c: ln.color || 'rgba(255,204,68,0.55)',
            d: ln.dash || 'dot',
        };
        try {
            Plotly.restyle(gd, {
                'line.width': 7,
                'line.color': 'rgba(255,230,140,1.0)',
                'line.dash': 'solid',
            }, [idx]);
        } catch (e) { _pulseOrig = null; return; }
        _pulseRestoreId = setTimeout(function() {
            _pulseRestoreId = null;
            if (!_pulseOrig) { return; }
            try {
                Plotly.restyle(gd, {
                    'line.width': _pulseOrig.w,
                    'line.color': _pulseOrig.c,
                    'line.dash': _pulseOrig.d,
                }, [_pulseOrig.idx]);
            } catch (e) { /* figure may have been re-rendered */ }
            _pulseOrig = null;
        }, 1200);
    }

    // Cancel everything in flight (fly animation, auto-rotate, pulse)
    // at the start of any preset click.  Without this, rapid preset
    // switches stack up animations/restyles, and the lerp of camera.up
    // can leave Plotly in a half-rolled state where the scene exits
    // the viewport entirely (root cause of "model gone after clicking
    // between Earth POV / Top / Side").
    function _cancelAll() {
        if (_flyAF) { cancelAnimationFrame(_flyAF); _flyAF = null; }
        stopAutoRotate();
        _cancelPulse();
    }

    // Lightweight logger: anything tagged '[GV3D]' is captured by the
    // Python side (see _LoggingPage in Preview3DWidget).  Wrap in a
    // try/catch so a broken console never blocks normal operation.
    function _gvlog(msg) {
        try { console.log('[GV3D] ' + msg); } catch (e) {}
    }
    window._gvlog = _gvlog;  // exposed for use from other handlers
    _gvlog('bootstrap ready');

    window.gv3d = {
        preset: function(name) {
            _gvlog('preset snap: ' + name);
            _cancelAll();
            snapTo(presetCamera(name));
            if (name === 'earth_pov') { _pulseViewingRay(); }
        },
        flyTo: function(name) {
            _gvlog('preset fly: ' + name);
            _cancelAll();
            flyToTarget(presetCamera(name), 1400);
            _kickIdle();
            if (name === 'earth_pov') {
                _pulseDeferId = setTimeout(function() {
                    _pulseDeferId = null;
                    _pulseViewingRay();
                }, 1200);
            }
        },
        autoRotate: function(on) {
            _gvlog('autoRotate: ' + (on ? 'on' : 'off'));
            if (on) { startAutoRotate(); } else { stopAutoRotate(); }
        },
        setIdleMs: function(ms) { _IDLE_MS = +ms || 10000; _kickIdle(); },
        // P2.6 — public API for "fly to spiral arm".
        flyToArm: function(armName) {
            _cancelAll();
            _gvlog('arm fly: ' + armName);
            var tgt = presetCamera('arm:' + armName);
            if (!tgt) { return; }
            flyToTarget(tgt, 1400);
            _kickIdle();
        },
        updateScaleBar: updateScaleBar,
    };

    // P2.6 — legend double-click to fly to an arm.  Plotly's default
    // double-click on a legend entry "solos" that trace (hides all
    // others).  For arm-named entries we override that to fly the
    // camera to the arm instead, which is the more useful gesture
    // for an astronomy viewer.  Other legend entries keep the
    // default solo behaviour.
    function _hookLegendArmFly() {
        var gd = _plot();
        if (!gd || !gd.on) {
            setTimeout(_hookLegendArmFly, 200);
            return;
        }
        gd.on('plotly_legenddoubleclick', function(ev) {
            if (!ev || typeof ev.curveNumber !== 'number') {
                return true;   // let Plotly handle it
            }
            var t = gd.data && gd.data[ev.curveNumber];
            if (!t || !t.name) { return true; }
            if (ARMS && ARMS[t.name]) {
                _gvlog('legend dbl-click → fly to arm: ' + t.name);
                window.gv3d.flyToArm(t.name);
                return false;  // prevent the default solo
            }
            return true;       // not an arm — default solo
        });
    }
    _hookLegendArmFly();

    // -----------------------------------------------------------
    // Rescue keys: users routinely orbit/zoom themselves into
    // nothingness in a 3D view.  Map the universal "get me home"
    // keys (R, Home, Escape) to the reset preset so there is always
    // a one-keystroke way back.  Also show a small persistent hint
    // so the user knows the shortcut exists.
    // -----------------------------------------------------------
    // Cache the render-time axis ranges so reset can restore them.
    // The NavigationPad's zoom buttons (and mouse-wheel dolly past the
    // near clip) SHRINK the axis ranges to "zoom in more than Plotly
    // normally allows".  That's a feature — but it means resetting
    // only camera.eye is insufficient: the ranges stay squeezed and
    // the scene appears collapsed inside a tiny axis box.  Cache once
    // after first paint; restore alongside the camera on reset.
    function _cacheOrigRanges() {
        var gd = _plot();
        if (!gd) { return; }
        if (gd.__gv3d_origRanges) { return; }
        var sc = gd._fullLayout && gd._fullLayout.scene;
        if (!sc) { return; }
        function r(ax) {
            if (ax && ax.range && ax.range.length === 2) {
                return [+ax.range[0], +ax.range[1]];
            }
            return null;
        }
        gd.__gv3d_origRanges = {
            x: r(sc.xaxis), y: r(sc.yaxis), z: r(sc.zaxis),
        };
        _gvlog('cached original axis ranges: ' +
               JSON.stringify(gd.__gv3d_origRanges));
    }
    // Defer caching a few frames so Plotly has finished its first
    // autorange pass.  Multiple attempts are cheap (no-op after first).
    setTimeout(_cacheOrigRanges, 400);
    setTimeout(_cacheOrigRanges, 1500);
    setTimeout(_cacheOrigRanges, 4000);

    function _resetView(animated) {
        var tgt = presetCamera('reset');
        if (!tgt) { _gvlog('reset: no target'); return; }
        _gvlog('reset view' + (animated ? ' (animated)' : ' (snap)'));
        stopAutoRotate();
        // Restore axis ranges FIRST, so the camera reset that follows
        // lands in the correct axis frame.  Reuse whichever cache is
        // populated (NavigationPad caches to __navpad_origRanges; our
        // bootstrap caches to __gv3d_origRanges).  If neither is set
        // yet, fall back to autorange=true so Plotly recomputes from
        // data extents — always recoverable.
        try {
            var gd = _plot();
            if (gd) {
                var oR = gd.__gv3d_origRanges || gd.__navpad_origRanges || {};
                var rArgs = {};
                if (oR.x) {
                    rArgs['scene.xaxis.range'] = oR.x;
                    rArgs['scene.xaxis.autorange'] = false;
                } else {
                    rArgs['scene.xaxis.autorange'] = true;
                }
                if (oR.y) {
                    rArgs['scene.yaxis.range'] = oR.y;
                    rArgs['scene.yaxis.autorange'] = false;
                } else {
                    rArgs['scene.yaxis.autorange'] = true;
                }
                if (oR.z) {
                    rArgs['scene.zaxis.range'] = oR.z;
                    rArgs['scene.zaxis.autorange'] = false;
                } else {
                    rArgs['scene.zaxis.autorange'] = true;
                }
                Plotly.relayout(gd, rArgs);
                _gvlog('restored axis ranges from ' +
                       (gd.__gv3d_origRanges ? 'gv3d'
                        : (gd.__navpad_origRanges ? 'navpad'
                           : 'autorange fallback')));
            }
        } catch (e) {
            _gvlog('axis-range restore failed: ' + (e && e.message));
        }
        if (animated) { flyToTarget(tgt, 900); }
        else { snapTo(tgt); }
        _kickIdle();
    }
    window.gv3d.reset = _resetView;
    window.addEventListener('keydown', function(ev) {
        // Skip if the user is typing into an input element.
        var t = ev.target;
        var tag = t && t.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable)) {
            return;
        }
        var k = ev.key;
        if (k === 'r' || k === 'R' || k === 'Home' || k === 'Escape') {
            _gvlog('rescue key: ' + k);
            ev.preventDefault();
            _resetView(true);
        }
    }, {capture: true});

    function _ensureHint() {
        var gd = _plot();
        if (!gd || document.getElementById('gv3d-hint')) { return; }
        var host = gd.parentElement || document.body;
        if (host && host !== document.body) {
            var cs = host.style;
            if (!cs.position || cs.position === 'static') {
                cs.position = 'relative';
            }
        }
        var h = document.createElement('div');
        h.id = 'gv3d-hint';
        h.textContent = 'Lost? Press R to reset view';
        h.style.position = 'absolute';
        h.style.right = '12px';
        h.style.top = '12px';
        h.style.zIndex = '6';
        h.style.color = '#e8e8f0';
        h.style.font = '11px Arial, sans-serif';
        h.style.padding = '4px 8px';
        h.style.background = 'rgba(20,20,28,0.55)';
        h.style.border = '1px solid rgba(180,190,220,0.25)';
        h.style.borderRadius = '3px';
        h.style.pointerEvents = 'auto';
        h.style.cursor = 'pointer';
        h.style.userSelect = 'none';
        h.title = 'Click or press R / Home / Esc to return to the default view';
        h.addEventListener('click', function() { _resetView(true); });
        host.appendChild(h);
    }
    // Defer so the plot container exists.
    setTimeout(_ensureHint, 400);
    setTimeout(_ensureHint, 1500);  // second try in case of slow paint

    // Kick the idle timer once so auto-rotate eventually fires even if
    // the user never moves the mouse.
    _kickIdle();
})();
</script>
"""


def _arms_json_for_js(mode: ViewMode | None) -> str:
    """Return a JSON literal mapping arm names to their midpoint
    scene-space (x, y, z) so the JS preset code can fly the camera
    to a named arm.  Galactic mode only — in cosmic mode the arms
    collapse to nothing.
    """
    if mode is not ViewMode.GALACTIC:
        return "{}"
    parts = []
    for arm in SPIRAL_ARMS:
        try:
            pts = arm_scene_points(arm, ViewMode.GALACTIC, n_pts=80)
            xs, ys, zs = pts["x"], pts["y"], pts["z"]
            if not xs:
                continue
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)
            mz = sum(zs) / len(zs)
            # Escape any embedded quote in the name (defensive).
            name = arm["name"].replace('"', '\\"')
            parts.append(f'"{name}":[{mx:.4f},{my:.4f},{mz:.4f}]')
        except Exception:
            continue
    return "{" + ",".join(parts) + "}"


def _inject_camera_bootstrap(html_content: str,
                             photo_center_xyz,
                             mode: ViewMode | None = None) -> str:
    """Splice the camera-preset/animation ``<script>`` into a Plotly
    HTML page just before ``</body>``.  Injecting inline (instead of
    runJavaScript-after-load) eliminates a race where a click on a
    preset button during page load would no-op because ``window.gv3d``
    didn't exist yet.

    ``mode`` is forwarded so the browser-side scale bar knows whether
    the scene uses galactic-linear (1 unit = 1 kly) or cosmic
    linear-then-log (1 unit = 100 kly up to 10 units, log beyond)
    distance scaling.
    """
    if photo_center_xyz is None:
        photo_json = "null"
    else:
        try:
            px, py, pz = (float(photo_center_xyz[0]),
                          float(photo_center_xyz[1]),
                          float(photo_center_xyz[2]))
            photo_json = f"[{px:.6f}, {py:.6f}, {pz:.6f}]"
        except Exception:
            photo_json = "null"
    if mode is ViewMode.COSMIC:
        mode_json = '"cosmic"'
    elif mode is ViewMode.GALACTIC:
        mode_json = '"galactic"'
    else:
        # Best-effort fallback: most scenes are galactic.
        mode_json = '"galactic"'
    snippet = (_CAMERA_BOOTSTRAP_JS
               .replace("__PHOTO_CENTER__", photo_json)
               .replace("__MODE__", mode_json)
               .replace("__ARMS__", _arms_json_for_js(mode)))
    # Inject just before </body>; fall back to append if the close
    # tag isn't present (pio.to_html should always include one).
    low = html_content.lower()
    idx = low.rfind("</body>")
    if idx < 0:
        return html_content + snippet
    return html_content[:idx] + snippet + html_content[idx:]


# ---------------------------------------------------------------------------
# WebEngine repair dialog (same pattern as CosmicDepth 3D)
# ---------------------------------------------------------------------------
class WebEngineRepairDialog(QDialog):
    """Opt-in repair flow for a broken PyQt6-WebEngine install."""

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
            "whose Qt ABI matches Siril's bundled PyQt6.<br><br>"
            "This will run <code>pip install --force-reinstall --no-deps</code> "
            "for <code>PyQt6-WebEngine</code> and "
            "<code>PyQt6-WebEngine-Qt6</code>, pinned to the minor version "
            "of your PyQt6. Nothing runs until you click <b>Run Repair</b>."
        )
        blurb.setWordWrap(True)
        blurb.setTextFormat(Qt.TextFormat.RichText)
        blurb.setStyleSheet("color:#cccccc;font-size:10pt;")
        lay.addWidget(blurb)

        _diag = diagnose_webengine_state()
        diag_label = QLabel(_diag["message"])
        diag_label.setWordWrap(True)
        diag_label.setStyleSheet(
            "color:#ffd27f;font-size:10pt;font-weight:bold;"
            "background-color:#2a2410;padding:6px;border-radius:4px;")
        lay.addWidget(diag_label)

        self._err_label = QLabel()
        self._err_label.setWordWrap(True)
        self._err_label.setStyleSheet(
            "background-color:#3a1e1e;color:#ffaaaa;"
            "border:1px solid #884444;border-radius:4px;"
            "padding:6px;font-family:monospace;font-size:9pt;")
        self._err_label.setText(
            f"Current import error:\n{WEBENGINE_ERROR or '(none)'}")
        lay.addWidget(self._err_label)

        self._cmd_label = QLabel()
        self._cmd_label.setStyleSheet(
            "color:#aaaaaa;font-family:monospace;font-size:9pt;"
            "background-color:#252525;padding:6px;border-radius:4px;")
        self._cmd_label.setText(self._format_planned_command())
        self._cmd_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._cmd_label)

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

        if _is_externally_managed_python():
            self._append(
                "[refused] This Python interpreter is marked "
                "EXTERNALLY-MANAGED (PEP 668). pip will not run from "
                "inside the script to avoid damaging your system "
                "install.\n")
            self.btn_run.setEnabled(False)

    @staticmethod
    def _pin_spec() -> str:
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR
            parts = PYQT_VERSION_STR.split(".")
            return ".".join(parts[:2]) + ".*" if len(parts) >= 2 else "*"
        except Exception:
            return "*"

    def _format_planned_command(self) -> str:
        pin = self._pin_spec()
        return (f"$ {sys.executable} -m pip install "
                f"--force-reinstall --no-deps "
                f"'PyQt6-WebEngine=={pin}' "
                f"'PyQt6-WebEngine-Qt6=={pin}'")

    def _append(self, text: str) -> None:
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
        cmd = [sys.executable, "-m", "pip", "install",
               "--force-reinstall", "--no-deps",
               f"PyQt6-WebEngine=={pin}",
               f"PyQt6-WebEngine-Qt6=={pin}"]
        self._append(f"$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    bufsize=1, text=True)
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
            self.btn_retry.setEnabled(True)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(600, self._on_retry)
        else:
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


# ---------------------------------------------------------------------------
# Navigation pad — camera control wheel for the Plotly 3D view
# ---------------------------------------------------------------------------
class _TrackballWidget(QWidget):
    """A round draggable ball that emits orbit deltas (azimuth, elevation).

    Click-drag inside the ball to orbit the camera.  The motion is
    continuous and two-axis, so diagonal drags produce diagonal orbits.
    Mouse-wheel over the ball zooms in/out.
    """

    _DEG_PER_PIXEL = 0.55     # drag sensitivity
    _WHEEL_ZOOM = 0.92        # per-notch zoom factor (<1 zooms in)

    def __init__(self, orbit_cb, zoom_cb, parent=None):
        super().__init__(parent)
        self._orbit_cb = orbit_cb
        self._zoom_cb = zoom_cb
        self._dragging = False
        self._last_pos = None
        self._hover_pos = None
        self._drag_vec = (0.0, 0.0)  # visual feedback dot offset
        # Accumulate drag deltas and flush them at ~60 Hz instead of
        # firing a JS relayout on every mouseMoveEvent (which can be
        # 120+ per second on a fast trackpad and causes stutter).
        self._pending_daz = 0.0
        self._pending_del = 0.0
        from PyQt6.QtCore import QTimer
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(16)  # 16 ms ≈ 62 Hz
        self._flush_timer.timeout.connect(self._flush_pending)
        self.setFixedSize(60, 60)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(
            "Drag to orbit the 3D camera (diagonals supported). "
            "Mouse-wheel zooms.")

    def _flush_pending(self) -> None:
        """Drain accumulated orbit deltas into a single JS call."""
        if self._orbit_cb is None:
            return
        daz = self._pending_daz
        delev = self._pending_del
        if daz == 0.0 and delev == 0.0:
            return
        self._pending_daz = 0.0
        self._pending_del = 0.0
        try:
            self._orbit_cb(daz, delev)
        except Exception:
            pass

    # ---- painting -----------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        w = self.width()
        h = self.height()
        side = min(w, h) - 6
        cx = w / 2.0
        cy = h / 2.0
        r = side / 2.0

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Ball with radial gradient — looks 3-dimensional.
        highlight = QColor("#6a7aa8") if self._dragging else QColor("#4e5a80")
        base = QColor("#1a1f33")
        shadow = QColor("#05060a")
        grad = QRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 1.4)
        grad.setColorAt(0.0, highlight)
        grad.setColorAt(0.55, base)
        grad.setColorAt(1.0, shadow)
        p.setBrush(QBrush(grad))
        rim_col = (QColor("#88aaff") if self._dragging
                   else QColor("#3a4466"))
        p.setPen(QPen(rim_col, 1.5))
        p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Equator + meridian guides.
        guide = QColor(120, 140, 180, 90)
        p.setPen(QPen(guide, 1))
        p.drawLine(int(cx - r), int(cy), int(cx + r), int(cy))
        p.drawLine(int(cx), int(cy - r), int(cx), int(cy + r))
        # Inner ring.
        p.setPen(QPen(QColor(120, 140, 180, 60), 1))
        p.drawEllipse(int(cx - r * 0.55), int(cy - r * 0.55),
                      int(r * 1.1), int(r * 1.1))

        # Drag indicator dot (offset from centre proportional to drag).
        dx, dy = self._drag_vec
        mag = math.hypot(dx, dy)
        max_off = r * 0.8
        if mag > max_off and mag > 0:
            dx *= max_off / mag
            dy *= max_off / mag
        dot_x = cx + dx
        dot_y = cy + dy
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#ffd27f") if self._dragging
                          else QColor(200, 210, 240, 200)))
        dr = 5.0 if self._dragging else 3.5
        p.drawEllipse(int(dot_x - dr), int(dot_y - dr),
                      int(dr * 2), int(dr * 2))
        p.end()

    # ---- mouse --------------------------------------------------------
    def _pos(self, event):
        try:
            return event.position()  # PyQt6 returns QPointF
        except Exception:
            return event.pos()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_pos = self._pos(event)
            self._drag_vec = (0.0, 0.0)
            self._pending_daz = 0.0
            self._pending_del = 0.0
            self._flush_timer.start()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        pos = self._pos(event)
        if self._dragging and self._last_pos is not None:
            dx = float(pos.x() - self._last_pos.x())
            dy = float(pos.y() - self._last_pos.y())
            self._last_pos = pos
            # Update indicator dot (cumulative w/ decay for nice feel).
            self._drag_vec = (
                0.8 * self._drag_vec[0] + dx,
                0.8 * self._drag_vec[1] + dy,
            )
            # Accumulate orbit deltas instead of firing immediately.
            # The _flush_timer drains them at ~60 Hz into one JS call.
            self._pending_daz += -dx * self._DEG_PER_PIXEL
            self._pending_del += dy * self._DEG_PER_PIXEL
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._last_pos = None
            self._drag_vec = (0.0, 0.0)
            # Emit any leftover delta before stopping the pump.
            self._flush_pending()
            self._flush_timer.stop()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
            event.accept()

    def wheelEvent(self, event):  # noqa: N802
        if self._zoom_cb is None:
            return
        try:
            steps = event.angleDelta().y() / 120.0
        except Exception:
            steps = 0.0
        if steps == 0:
            return
        factor = self._WHEEL_ZOOM ** steps
        self._zoom_cb(factor)
        event.accept()


class NavigationPad(QWidget):
    """Camera control wheel for the embedded Plotly 3D scene.

    Uses a draggable trackball for two-axis orbit (so diagonals just
    work) plus dedicated zoom and reset buttons.  Each gesture sends a
    small JS snippet to the QWebEngineView that calls
    ``Plotly.relayout(gd, {'scene.camera': newCamera})`` with an
    updated ``eye`` / ``up`` / ``center`` — effectively orbiting the
    camera around the scene centre.
    """

    _ZOOM_FACTOR = 0.85  # button step; <1 zooms in, >1 zooms out

    # JS helper template: rotates / zooms the Plotly 3D camera in-place.
    _JS_CAMERA = """
(function(daz, del, zoom, resetView) {
    var gd = document.querySelector('.js-plotly-plot');
    if (!gd || !gd.layout || !gd.layout.scene) { return; }

    function axRange(ax) {
        if (ax && ax.range && ax.range.length === 2) {
            return [+ax.range[0], +ax.range[1]];
        }
        return null;
    }
    function scene() { return gd._fullLayout && gd._fullLayout.scene; }

    // Cache the render-time axis ranges once, so reset can restore them
    // even after we've shrunk them to zoom past Plotly's near clip.
    if (!gd.__navpad_origRanges) {
        var sc0 = scene();
        gd.__navpad_origRanges = {
            x: sc0 ? axRange(sc0.xaxis) : null,
            y: sc0 ? axRange(sc0.yaxis) : null,
            z: sc0 ? axRange(sc0.zaxis) : null
        };
    }

    if (resetView) {
        // Dead-simple reset: one synchronous Plotly.relayout, per-key
        // camera form, and hard autorange=true on all three axes.  No
        // animation, no dependency on the bootstrap JS, no chained
        // relayouts.  Autorange asks Plotly to recompute ranges from
        // the actual data extents — bulletproof recovery from any
        // prior zoom-in that shrank the ranges.
        try {
            if (typeof console !== 'undefined') {
                console.log('[GV3D] navpad reset: direct relayout '
                            + '(autorange + camera defaults)');
            }
        } catch (logErr) {}
        Plotly.relayout(gd, {
            'scene.camera.eye': {x:1.6, y:1.6, z:1.0},
            'scene.camera.up': {x:0, y:0, z:1},
            'scene.camera.center': {x:0, y:0, z:0},
            'scene.xaxis.autorange': true,
            'scene.yaxis.autorange': true,
            'scene.zaxis.autorange': true,
        });
        return;
    }

    var cam = (scene() && scene().camera) ||
              gd.layout.scene.camera ||
              {eye:{x:1.6,y:1.6,z:1.0}, up:{x:0,y:0,z:1},
               center:{x:0,y:0,z:0}};
    var eye = {x:+cam.eye.x, y:+cam.eye.y, z:+cam.eye.z};
    var ctr = {x:+(cam.center && cam.center.x || 0),
               y:+(cam.center && cam.center.y || 0),
               z:+(cam.center && cam.center.z || 0)};
    var up = {x:+(cam.up && cam.up.x || 0),
              y:+(cam.up && cam.up.y || 0),
              z:+(cam.up && cam.up.z || 1)};
    var vx = eye.x - ctr.x, vy = eye.y - ctr.y, vz = eye.z - ctr.z;
    var r = Math.sqrt(vx*vx + vy*vy + vz*vz);
    if (r < 1e-9) { r = 1; }
    var theta = Math.acos(Math.max(-1, Math.min(1, vz / r)));
    var phi = Math.atan2(vy, vx);
    phi += daz;
    theta = Math.max(0.05, Math.min(Math.PI - 0.05, theta + del));

    // --- Dolly with near-clip limit (no more range-shrink trick) -----
    // Plotly clamps the eye against an internal near plane at roughly
    // r≈0.3 (scene-normalised units); below that, moving the camera
    // does nothing visible.  We used to shrink the axis RANGES to
    // zoom past that limit, but that caused two mutually-incompatible
    // behaviors to collide:
    //
    //   1. Shrinking the range cuts off any data outside the shrunk
    //      cube (Plotly culls by axis range) — the "arms disappear"
    //      bug.
    //   2. Widening the range back to include must-keep traces fixes
    //      (1) but then the camera at MIN_R=0.3 sees a wide scene
    //      through a narrow perspective cone — most of the scene
    //      falls outside the FOV frustum, producing the broken
    //      partial-arm stubs seen in recent screenshots.
    //
    // The honest fix is to stop zooming past the near clip on
    // zoom-IN.  The camera hits MIN_R and further zoom-in presses
    // become no-ops.  For zoom-OUT we still want range expansion
    // (so the user can pull back far enough to see distant neighbor
    // galaxies), so the MAX_R branch keeps the old behavior.
    var MIN_R = __NAV_EYE_MIN__;
    var MAX_R = __NAV_EYE_MAX__;
    var desiredR = r * zoom;
    var rangeFactor = 1.0;
    var zoomCapped = false;
    if (desiredR < MIN_R) {
        // Zoom-in capped at near clip.  No range shrink — we accept
        // Plotly's natural zoom limit rather than fight it.
        r = MIN_R;
        zoomCapped = true;
    } else if (desiredR > MAX_R) {
        rangeFactor = desiredR / MAX_R;   // >1 → expand ranges (zoom out more)
        r = MAX_R;
    } else {
        r = desiredR;
    }

    var nx = r * Math.sin(theta) * Math.cos(phi);
    var ny = r * Math.sin(theta) * Math.sin(phi);
    var nz = r * Math.cos(theta);

    var relayoutArgs = {
        'scene.camera.eye': {x: ctr.x + nx, y: ctr.y + ny, z: ctr.z + nz},
        'scene.camera.up':  up,
        'scene.camera.center': ctr
    };

    if (zoomCapped) {
        try {
            if (typeof _gvlog === 'function') {
                _gvlog('zoom-in capped at near-clip (r=MIN_R=' +
                       MIN_R.toFixed(3) + ') — use mode switch to ' +
                       'Galactic or rotate for more detail');
            }
        } catch (cappedErr) {}
    }

    if (rangeFactor !== 1.0) {
        // Unlimited zoom: no span clamp.  Ranges can shrink
        // arbitrarily close to 0 (or grow arbitrarily large on
        // zoom-out).  At extreme zoom-in levels, float64 precision
        // around the axis centre eventually limits the rendering,
        // but that is a hardware limit, not a Plotly one — we apply
        // whatever factor the user asks for.
        //
        // CRITICAL: Plotly 3D culls any vertex that falls outside
        // the axis range cube.  A naive "shrink around midpoint"
        // (or even "shrink around cam.center", since cam.center is
        // fixed at (0,0,0) here) will cut off the photo frame,
        // viewing-ray ticks and target label as soon as the cube
        // is smaller than |photo_center| — which manifests as
        // rectangular slabs of content vanishing on the next tick.
        //
        // Fix: after computing the shrunk box, WIDEN it
        // asymmetrically so all vertices of "must-keep" traces
        // (the target legendgroup + Earth at origin) stay inside.
        // Background traces (far spiral-arm tails, distant
        // neighbor galaxies) can still be culled on deep zoom,
        // which is the correct behavior.  aspectmode="data"
        // handles the resulting asymmetric box without distortion.
        var sc = scene();

        // Collect must-keep vertices.  Preserve the `target`
        // legendgroup (photo, viewing ray, target label,
        // uncertainty cigar) AND the `milkyway` legendgroup
        // (spiral arms, disk stars, bulge, Sgr A*, Earth, galactic
        // plane mesh) — the user's complaint "arms of our galaxy
        // disappear on zoom" is precisely the milkyway group being
        // culled by an over-shrunk axis box.  `references` (big
        // distance rings) and `background` (neighbor galaxies) are
        // intentionally NOT preserved: rings span the whole scene
        // and would prevent any zoom at all, and neighbor galaxies
        // are decorative.
        // _fullData carries the rendered traces; fall back to
        // gd.data if necessary.
        var keepX = [0], keepY = [0], keepZ = [0];  // Earth always kept
        try {
            var data = gd._fullData || gd.data || [];
            for (var i = 0; i < data.length; i++) {
                var tr = data[i];
                if (!tr) { continue; }
                var lg = tr.legendgroup;
                if (lg !== 'target' && lg !== 'milkyway') { continue; }
                if (!tr.x || !tr.y || !tr.z) { continue; }
                var n = Math.min(tr.x.length, tr.y.length, tr.z.length);
                for (var j = 0; j < n; j++) {
                    var xj = +tr.x[j], yj = +tr.y[j], zj = +tr.z[j];
                    if (isFinite(xj)) { keepX.push(xj); }
                    if (isFinite(yj)) { keepY.push(yj); }
                    if (isFinite(zj)) { keepZ.push(zj); }
                }
            }
        } catch (collectErr) {}

        function minOf(arr) {
            var m = arr[0];
            for (var k = 1; k < arr.length; k++) {
                if (arr[k] < m) { m = arr[k]; }
            }
            return m;
        }
        function maxOf(arr) {
            var m = arr[0];
            for (var k = 1; k < arr.length; k++) {
                if (arr[k] > m) { m = arr[k]; }
            }
            return m;
        }

        var keepMin = [minOf(keepX), minOf(keepY), minOf(keepZ)];
        var keepMax = [maxOf(keepX), maxOf(keepY), maxOf(keepZ)];
        var axes = [
            ['xaxis', 'scene.xaxis.range', 0],
            ['yaxis', 'scene.yaxis.range', 1],
            ['zaxis', 'scene.zaxis.range', 2]
        ];
        var _logParts = [];
        axes.forEach(function(pair) {
            var axKey = pair[0];
            var relKey = pair[1];
            var idx = pair[2];
            var cur = sc ? axRange(sc[axKey]) : null;
            if (!cur) { return; }
            var mid = (cur[0] + cur[1]) / 2;
            var half = (cur[1] - cur[0]) / 2;
            var newHalf = Math.max(half * rangeFactor, 1e-6);
            var lo = mid - newHalf;
            var hi = mid + newHalf;
            // Widen so every must-keep vertex on this axis stays
            // inside [lo, hi].  Small 2%% pad so points don't sit
            // exactly on the clipping plane (where Plotly's
            // numerical tolerance sometimes still culls them).
            var kmin = keepMin[idx];
            var kmax = keepMax[idx];
            if (isFinite(kmin) && kmin < lo) {
                lo = kmin - Math.abs(kmin) * 0.02 - 1e-6;
            }
            if (isFinite(kmax) && kmax > hi) {
                hi = kmax + Math.abs(kmax) * 0.02 + 1e-6;
            }
            relayoutArgs[relKey] = [lo, hi];
            relayoutArgs['scene.' + axKey + '.autorange'] = false;
            _logParts.push(axKey + '=[' + lo.toPrecision(4) +
                           ',' + hi.toPrecision(4) + ']');
        });
        try {
            if (typeof _gvlog === 'function') {
                _gvlog('navpad zoom: rangeFactor=' +
                       rangeFactor.toPrecision(4) +
                       ' keepMin=(' + keepMin[0].toPrecision(4) +
                       ',' + keepMin[1].toPrecision(4) +
                       ',' + keepMin[2].toPrecision(4) + ')' +
                       ' keepMax=(' + keepMax[0].toPrecision(4) +
                       ',' + keepMax[1].toPrecision(4) +
                       ',' + keepMax[2].toPrecision(4) + ') ' +
                       _logParts.join(' '));
            }
        } catch (logErr) {}
    }

    // Also handle mouse-wheel zoom: Plotly's built-in wheel handler
    // on 3D scenes shrinks axis ranges around the range midpoint —
    // the SAME failure mode the navpad zoom-in used to have.  We
    // previously tried to widen the shrunk ranges back to include
    // must-keep traces, but that produced an incoherent state
    // (wide scene + camera clamped near origin = narrow perspective
    // cone cuts most of the scene).
    //
    // Cleaner behavior: REVERT any wheel-induced axis-range shrink
    // back to the cached original autoranged bounds.  Wheel zoom-in
    // then effectively becomes a no-op on the axis box; the user
    // uses the NavigationPad for zoom (which is capped at the near
    // clip).  Legitimate navpad zoom-out still works because it
    // sets ranges LARGER than orig, and our revert only triggers
    // when they're TIGHTER than orig.
    if (!gd.__gv3d_relayoutHook) {
        gd.__gv3d_relayoutHook = true;
        gd.on('plotly_relayout', function(ev) {
            if (!ev) { return; }
            // Only react when an axis range was touched.
            var touched = false;
            for (var k in ev) {
                if (k.indexOf('scene.xaxis.range') === 0 ||
                    k.indexOf('scene.yaxis.range') === 0 ||
                    k.indexOf('scene.zaxis.range') === 0) {
                    touched = true; break;
                }
            }
            if (!touched) { return; }
            var scW = scene();
            if (!scW) { return; }
            var orig = gd.__navpad_origRanges;
            if (!orig || !orig.x || !orig.y || !orig.z) { return; }

            var fixArgs = {};
            var reverted = false;
            var axPairs = [['xaxis', orig.x],
                           ['yaxis', orig.y],
                           ['zaxis', orig.z]];
            for (var a = 0; a < axPairs.length; a++) {
                var axK = axPairs[a][0];
                var origR = axPairs[a][1];
                var curR = axRange(scW[axK]);
                if (!curR || !origR) { continue; }
                var origSpan = Math.abs(origR[1] - origR[0]);
                var curSpan = Math.abs(curR[1] - curR[0]);
                // Revert only when the current span is tighter than
                // the original — i.e. a zoom-in shrink from wheel or
                // from Plotly's internal drag handling.  Expansion
                // (zoom-out past orig) is left alone so the navpad
                // zoom-out path can pull back farther.
                if (curSpan < origSpan * 0.999) {
                    fixArgs['scene.' + axK + '.range'] = origR.slice();
                    fixArgs['scene.' + axK + '.autorange'] = false;
                    reverted = true;
                }
            }
            if (reverted) {
                try {
                    if (typeof _gvlog === 'function') {
                        _gvlog('wheel-zoom reverted: axis shrink undone ' +
                               '(use navpad + / - or R to reset)');
                    }
                } catch (le) {}
                // Deferred to avoid re-entering relayout mid-dispatch.
                setTimeout(function() {
                    try { Plotly.relayout(gd, fixArgs); } catch (re) {}
                }, 0);
            }
        });
    }

    Plotly.relayout(gd, relayoutArgs);
})(%f, %f, %f, %s);
"""
    # Inject module-level camera clamps into the JS template so the
    # Python constant is the single source of truth.  Done once at
    # class-definition time (no per-call overhead).
    _JS_CAMERA = (_JS_CAMERA
                  .replace("__NAV_EYE_MIN__", repr(float(NAV_EYE_MIN)))
                  .replace("__NAV_EYE_MAX__", repr(float(NAV_EYE_MAX))))

    def __init__(self, run_js, parent=None):
        """``run_js`` is a ``Callable[[str], None]`` that dispatches JS
        to the current WebEngine view.  Passing a callable (instead of
        a view reference) lets the pad keep working when the view is
        recreated on every render."""
        super().__init__(parent)
        self._run_js = run_js
        # Use the shared NAV_BUTTON_STYLE (with tweaks for compact
        # +/-/reset) so the whole 3D-view button row reads as a
        # single coherent toolbar.
        self.setStyleSheet(
            "NavigationPad{background:transparent;}"
            + NAV_BUTTON_STYLE
            + "QPushButton{min-width:28px;padding:6px 8px;"
              "font-size:11pt;}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        # The trackball — drag to orbit (diagonals supported).
        self._ball = _TrackballWidget(
            orbit_cb=self._orbit,
            zoom_cb=self._zoom,
            parent=self,
        )
        self._ball.setToolTip(
            "Drag to orbit the 3D camera (diagonals supported). "
            "Mouse-wheel zooms.")
        row.addWidget(self._ball)

        def _add(btn_text: str, tip: str, handler):
            b = QPushButton(btn_text, self)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setFixedWidth(34)
            b.clicked.connect(handler)
            row.addWidget(b)
            return b

        _add("+", "Zoom in",
             lambda: self._zoom(self._ZOOM_FACTOR))
        _add("−", "Zoom out",
             lambda: self._zoom(1.0 / self._ZOOM_FACTOR))
        _add("⟲", "Reset camera to default view",
             self._reset)

    # ---- JS bridge ----------------------------------------------------
    def _run(self, daz_deg: float, del_deg: float,
             zoom: float, reset: bool) -> None:
        if self._run_js is None:
            return
        daz = math.radians(daz_deg)
        del_ = math.radians(del_deg)
        # Guard against NaN/Inf sneaking into the JS template — Python
        # renders them as "nan"/"inf" which is not valid JavaScript and
        # would silently break the camera call.
        if not (math.isfinite(daz) and math.isfinite(del_)
                and math.isfinite(zoom)):
            return
        js = self._JS_CAMERA % (daz, del_, zoom,
                                "true" if reset else "false")
        try:
            self._run_js(js)
        except Exception:
            pass

    def _orbit(self, daz_deg: float, del_deg: float) -> None:
        self._run(daz_deg, del_deg, 1.0, False)

    def _zoom(self, factor: float) -> None:
        self._run(0.0, 0.0, float(factor), False)

    def _reset(self) -> None:
        self._run(0.0, 0.0, 1.0, True)


# ---------------------------------------------------------------------------
# Preview widget (same pattern as CosmicDepth 3D)
# ---------------------------------------------------------------------------
class Preview3DWidget(QWidget):
    """Shows the 3D scene (QWebEngineView when available, PNG fallback)."""

    repair_requested = pyqtSignal()
    # Relays JS-side `console.log('[GV3D] …')` messages out of the
    # embedded page so the main window can route them into the Log tab
    # (and Siril's log).  Only messages beginning with the '[GV3D]' tag
    # are forwarded — third-party Plotly noise is suppressed.
    js_log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._view = None
        self._page = None
        self._png_label = None
        self._banner = None
        self._tmp_html_path = None
        if HAS_WEBENGINE:
            self._show_placeholder()
        else:
            self._show_webengine_banner()

    def _show_placeholder(self) -> None:
        self._clear_children()
        placeholder = QLabel(
            "The 3D map will appear here after rendering.\n"
            "Press \u201cRender 3D Map\u201d (F5).")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color:#888888;font-size:11pt;border:1px dashed #555555;"
            "background-color:#0a0a0a;")
        self._layout.addWidget(placeholder)

    def _show_webengine_banner(self) -> None:
        self._clear_children()
        diag = diagnose_webengine_state()
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
        diag_label = QLabel(diag["message"])
        diag_label.setWordWrap(True)
        diag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diag_label.setStyleSheet(
            "color:#ffd27f;font-size:10pt;font-weight:bold;border:0;")
        bl.addWidget(diag_label)
        button_text = ("Install WebEngine\u2026"
                       if diag["kind"] == "missing"
                       else "Repair WebEngine\u2026")
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
        btn = QPushButton(button_text)
        btn.setObjectName("RenderButton")
        _nofocus(btn)
        btn.clicked.connect(self.repair_requested.emit)
        btn_row.addWidget(btn)
        btn_row.addStretch()
        bl.addLayout(btn_row)
        self._banner = banner
        self._layout.addWidget(banner)

    def refresh_webengine_state(self) -> None:
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
        self._page = None
        self._png_label = None
        self._banner = None

    def show_html(self, html_content: str) -> None:
        if not HAS_WEBENGINE:
            self._show_webengine_banner()
            return
        self._clear_children()
        self._view = QWebEngineView()
        # Attach a page that forwards JS console.log('[GV3D] …') lines
        # to our js_log signal.  Without this, events happening inside
        # the embedded page (camera moves, preset switches, rescue key
        # presses, caught errors) are invisible to the user — which
        # makes diagnosing "something is broken" reports very hard.
        try:
            from PyQt6.QtWebEngineCore import QWebEnginePage

            outer = self

            class _LoggingPage(QWebEnginePage):
                def javaScriptConsoleMessage(self, level, message,
                                             lineNumber, sourceID):
                    if message and message.startswith("[GV3D]"):
                        try:
                            outer.js_log.emit(message)
                        except Exception:
                            pass
                    # Drop everything else — Plotly/WebEngine emit a lot
                    # of benign chatter we don't want in the Log tab.

            page = _LoggingPage(self._view)
            self._view.setPage(page)
            self._page = page
        except Exception:
            # Older PyQt6 layouts may not expose QWebEnginePage here;
            # fall back to the default page (no JS logs, but the view
            # still renders).
            self._page = None
        cache_dir = _plotly_cache_dir()
        prev = getattr(self, "_tmp_html_path", None)
        if prev and os.path.isfile(prev):
            try:
                os.remove(prev)
            except Exception:
                pass
        path = os.path.join(cache_dir,
                            f"scene_{os.getpid()}_{id(self):x}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        self._tmp_html_path = path
        self._view.load(QUrl.fromLocalFile(path))
        self._layout.addWidget(self._view)

    def run_js(self, js: str) -> None:
        """Dispatch a JavaScript snippet to the current WebEngine view.

        Used by the external NavigationPad — because the view is
        recreated on every render, the pad holds a reference to this
        method rather than to a specific view instance.
        """
        view = self._view
        if view is None:
            return
        try:
            view.page().runJavaScript(js)
        except Exception:
            pass

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
                           Qt.TransformationMode.SmoothTransformation))
        self._layout.addWidget(self._png_label)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class GalacticView3DWindow(QMainWindow):
    """
    Main window for Svenesis GalacticView 3D.

    Left panel: view mode, object info, view presets, cache, export.
    Right panel: interactive 3D Milky Way scene and status log.
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
        # NOTE: all siril.pix2radec / radec2pix / get_image* calls happen
        # on the Qt main thread (render path + build_background_pins run
        # there).  A threading lock around them would be misleading
        # scaffolding, so there isn't one.  If future work moves any
        # siril RPC to a worker thread, wrap with a fresh lock here.
        self._last_html_path = ""
        self._last_png_path = ""
        self._last_csv_path = ""
        self._last_figure = None
        self._last_scene: dict | None = None
        # H3 re-entrancy guard.  _update_progress() calls
        # QApplication.processEvents() and TargetPickerDialog.exec()
        # spins a modal loop, so a second F5 or a rapid double-click on
        # "Render 3D Map" can re-enter _on_render() while the first
        # call still holds _image_data / _wcs / _pixel_grid_cache
        # references.  The flag + disabled button are a belt-and-
        # braces guard.
        self._rendering = False
        self._cache = GalacticViewCache()
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        # WCS detection is expensive (up to 6 strategies, FITS re-reads).
        # Cache by (file path, mtime) — re-renders for the same image
        # skip the whole detection ladder.
        self._wcs_cache: dict = {"path": None, "mtime": None,
                                 "wcs": None, "plate_solved": False,
                                 "header_str": ""}
        # Photo-texture pixel grid is ~150-230k markers; only rebuild
        # when image bytes, resolution, or photo corners change.
        self._pixel_grid_cache: dict = {"key": None, "grid": None}

        self.init_ui()
        self._load_settings()

        QShortcut(QKeySequence("F5"), self, self._on_render)
        # Rescue keys at the Qt level — the in-page window.addEventListener
        # hook only fires when keyboard focus is inside the embedded
        # WebEngineView, which isn't where focus lives after the user
        # clicks most UI buttons.  Binding the same keys at the window
        # level guarantees they always work, and we route them through
        # the same `window.gv3d.reset` the in-page handler uses so the
        # behaviour is identical (axis ranges + camera restored).
        def _rescue_reset():
            self._log("Rescue reset triggered (Qt shortcut).")
            # Dead-simple Qt-side rescue: one synchronous Plotly.relayout
            # with autorange=true on all three axes + camera at defaults.
            # Does not depend on window.gv3d loading successfully — if
            # the bootstrap has any error at all (syntax, exception
            # during install), the fly-based reset would silently do
            # nothing and the user would be stuck.  This path only
            # requires that Plotly itself loaded, which is guaranteed
            # by `pio.to_html(..., include_plotlyjs='directory')`.
            try:
                self.preview_widget.run_js(
                    "(function(){"
                    "try{"
                    "  var gd = document.querySelector('.js-plotly-plot');"
                    "  if (!gd || !window.Plotly) {"
                    "    console.log('[GV3D] rescue: no plot / Plotly');"
                    "    return;"
                    "  }"
                    "  console.log('[GV3D] rescue: direct relayout');"
                    "  Plotly.relayout(gd, {"
                    "    'scene.camera.eye': {x:1.6, y:1.6, z:1.0},"
                    "    'scene.camera.up':  {x:0, y:0, z:1},"
                    "    'scene.camera.center': {x:0, y:0, z:0},"
                    "    'scene.xaxis.autorange': true,"
                    "    'scene.yaxis.autorange': true,"
                    "    'scene.zaxis.autorange': true"
                    "  });"
                    "} catch(e){"
                    "  console.log('[GV3D] rescue failed: ' + "
                    "    (e && e.message));"
                    "}"
                    "})();"
                )
            except Exception as exc:
                self._log(f"Rescue reset failed: {exc}")
        # ApplicationShortcut context is critical: QWebEngineView eats
        # keystrokes via its internal focus proxy, so a default
        # WindowShortcut never fires when the user clicks into the 3D
        # view.  Application-level shortcuts dispatch before widget
        # event delivery, so they survive the WebEngine focus trap.
        for seq in ("R", "Home", "Esc"):
            sc = QShortcut(QKeySequence(seq), self, _rescue_reset)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------
    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        left.setFixedWidth(LEFT_PANEL_WIDTH)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)

        lbl = QLabel(f"Svenesis GalacticView 3D {VERSION}")
        lbl.setStyleSheet(
            "font-size: 15pt; font-weight: bold; color: #88aaff; "
            "margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_mode_group(layout)
        self._build_scene_group(layout)
        self._build_object_group(layout)
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

    def _build_mode_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("View Mode")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Scale:"))
        self.radio_auto = QRadioButton("Auto")
        self.radio_auto.setChecked(True)
        self.radio_auto.setToolTip(
            "Choose mode automatically from object distance/type.")
        _nofocus(self.radio_auto)
        self.radio_galactic = QRadioButton("Galactic")
        self.radio_galactic.setToolTip(
            "Force Galactic mode — 1 unit = 1,000 ly. "
            "Best for objects inside the Milky Way.")
        _nofocus(self.radio_galactic)
        self.radio_cosmic = QRadioButton("Cosmic")
        self.radio_cosmic.setToolTip(
            "Force Cosmic mode — neighbor galaxies visible, "
            "log-scaled beyond 1 Mly.")
        _nofocus(self.radio_cosmic)
        grp = QButtonGroup(self)
        grp.addButton(self.radio_auto)
        grp.addButton(self.radio_galactic)
        grp.addButton(self.radio_cosmic)
        row.addWidget(self.radio_auto)
        row.addWidget(self.radio_galactic)
        row.addWidget(self.radio_cosmic)
        row.addStretch()
        layout.addLayout(row)

        parent_layout.addWidget(group)

    def _build_scene_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Scene Elements")
        layout = QVBoxLayout(group)

        self.chk_arms = QCheckBox("Spiral arms (5)")
        self.chk_arms.setChecked(True)
        self.chk_arms.setToolTip(
            "<b>Milky Way spiral arms</b><br><br>"
            "Render five logarithmic-spiral arm lines that approximate "
            "the Milky Way's large-scale structure:<br>"
            "&nbsp;• <b>Norma</b> — innermost arm<br>"
            "&nbsp;• <b>Scutum-Centaurus</b> — one of the two dominant arms<br>"
            "&nbsp;• <b>Sagittarius</b> — nearer side, rich in H II regions<br>"
            "&nbsp;• <b>Orion</b> (local spur) — the Sun sits on the inner edge<br>"
            "&nbsp;• <b>Perseus</b> — second dominant arm, on the far side<br><br>"
            "Arms are drawn out to ~30 kly from the Galactic centre and "
            "fade with distance. Only visible in <b>galactic mode</b>; "
            "in cosmic mode the arms are hidden (the Milky Way collapses "
            "to a single dot).<br><br>"
            "Turn off for a cleaner view of individual stars / photo.")
        _nofocus(self.chk_arms)
        layout.addWidget(self.chk_arms)

        self.chk_disk = QCheckBox("Disk stars (background)")
        self.chk_disk.setChecked(True)
        self.chk_disk.setToolTip(
            "<b>Galactic disk star-field backdrop</b><br><br>"
            "Adds a pseudo-random field of background stars distributed "
            "inside a flattened disk (exponential radial profile, "
            "sech²-like vertical profile) to give the galactic map a "
            "sense of depth and population.<br><br>"
            "&nbsp;• Seeded with <code>random.seed(42)</code>, so the "
            "pattern is identical every render (no flicker between "
            "renders).<br>"
            "&nbsp;• Marker sizes are varied logarithmically to mimic "
            "apparent brightness.<br>"
            "&nbsp;• Purely cosmetic — these are <i>not</i> catalog stars "
            "and carry no astrometric meaning.<br><br>"
            "Turn off if the backdrop is making the scene too cluttered "
            "or to speed up very weak GPUs. Only affects "
            "<b>galactic mode</b>.")
        _nofocus(self.chk_disk)
        layout.addWidget(self.chk_disk)

        self.chk_neighbors = QCheckBox("Neighbor galaxies (cosmic mode)")
        self.chk_neighbors.setChecked(True)
        self.chk_neighbors.setToolTip(
            "<b>Nearby galaxies in the Local Group and beyond</b><br><br>"
            "Adds labelled markers for well-known neighbours so you can "
            "see where your target sits in the larger structure:<br>"
            "&nbsp;• <b>M31 Andromeda</b> (≈ 2.5 Mly)<br>"
            "&nbsp;• <b>M33 Triangulum</b> (≈ 2.7 Mly)<br>"
            "&nbsp;• <b>LMC</b> and <b>SMC</b> (≈ 0.16 / 0.20 Mly)<br>"
            "&nbsp;• <b>M81 / M82</b> group (≈ 12 Mly)<br>"
            "&nbsp;• <b>M51 Whirlpool</b> (≈ 23 Mly)<br>"
            "&nbsp;• <b>NGC 5128 Centaurus A</b> (≈ 12 Mly)<br>"
            "&nbsp;• <b>Virgo cluster</b> (≈ 54 Mly)<br>"
            "&nbsp;• <b>Sculptor group</b> (≈ 11 Mly)<br><br>"
            "Positions are from hard-coded literature values; distances "
            "use the same log-scaling as the rest of the cosmic scene.<br><br>"
            "Only visible in <b>cosmic mode</b>. Turn off to focus on "
            "your target and its immediate SIMBAD neighbours.")
        _nofocus(self.chk_neighbors)
        layout.addWidget(self.chk_neighbors)

        # P4.12 — distance-metric toggle (cosmic mode only).  Three
        # radio buttons: light-travel (default), comoving (proper
        # distance now), angular-diameter (apparent-size distance).
        # Galactic mode ignores the setting since the metrics are
        # identical at sub-Mly distances.
        from PyQt6.QtWidgets import QButtonGroup, QRadioButton
        lbl_metric = QLabel("Distance metric (cosmic mode):")
        lbl_metric.setStyleSheet("color:#888; font-size:10pt;")
        layout.addWidget(lbl_metric)
        self.metric_grp = QButtonGroup(self)
        self.radio_metric_lt = QRadioButton(
            "Light-travel (default)")
        self.radio_metric_lt.setChecked(True)
        self.radio_metric_lt.setToolTip(
            "<b>Light-travel distance</b> = c × lookback time.<br>"
            "How far the light from the object travelled to reach "
            "us.  This is the default and matches SIMBAD's "
            "redshift-derived 'distance' values.<br><br>"
            "Best for: 'how old is this image?' framing.")
        _nofocus(self.radio_metric_lt)
        self.radio_metric_co = QRadioButton(
            "Comoving (proper distance now)")
        self.radio_metric_co.setToolTip(
            "<b>Comoving distance</b> = the proper distance to the "
            "object NOW, accounting for the universe's expansion "
            "since the light left.<br><br>"
            "At z = 0.5 it's ~25% larger than light-travel.  At "
            "z = 1100 (CMB) it's ~46 Gly vs. ~13.8 Gly light-travel."
            "<br><br>"
            "Best for: 'where is this object in the universe right "
            "now?' framing.")
        _nofocus(self.radio_metric_co)
        self.radio_metric_ad = QRadioButton(
            "Angular-diameter (apparent size)")
        self.radio_metric_ad.setToolTip(
            "<b>Angular-diameter distance</b> = comoving / (1+z).<br>"
            "Determines how big the object appears in the sky for "
            "a given physical size.  Smaller than comoving and "
            "(at z > 1.6) even smaller than light-travel.<br><br>"
            "Best for: understanding why high-z objects look "
            "deceptively close in arcseconds.")
        _nofocus(self.radio_metric_ad)
        self.metric_grp.addButton(self.radio_metric_lt)
        self.metric_grp.addButton(self.radio_metric_co)
        self.metric_grp.addButton(self.radio_metric_ad)
        layout.addWidget(self.radio_metric_lt)
        layout.addWidget(self.radio_metric_co)
        layout.addWidget(self.radio_metric_ad)

        self.chk_photo = QCheckBox("Photo rectangle + viewing ray")
        self.chk_photo.setChecked(True)
        self.chk_photo.setToolTip(
            "<b>Your plate-solved astrophoto in 3D</b><br><br>"
            "When enabled the scene adds three things:<br>"
            "&nbsp;• A <b>photo rectangle</b> — a quadrilateral with "
            "vertices at the four WCS-solved image corners, projected "
            "to the target's distance. The rectangle is textured with "
            "your auto-stretched image (see "
            "<i>Photo resolution</i> below).<br>"
            "&nbsp;• A <b>viewing ray</b> — a dashed line from Earth "
            "(0,0,0) to the rectangle's centre. This is the actual "
            "line-of-sight at which you pointed the scope.<br>"
            "&nbsp;• A <b>midpoint label</b> showing the target's name "
            "and distance along the ray.<br><br>"
            "The rectangle is uniformly enlarged around its centroid if "
            "the true angular size would render smaller than a few "
            "scene units, so wide-field images stay visible at galactic "
            "and cosmic scale.<br><br>"
            "Requires a plate-solved image (FITS with valid WCS keywords "
            "or a previous Siril solve). Turn off if WCS is missing or "
            "for a cleaner pure-galaxy view.")
        _nofocus(self.chk_photo)
        layout.addWidget(self.chk_photo)

        # Photo resolution (longest-axis pixel count for the 3D texture).
        # Each pixel becomes a Scatter3d marker; higher = sharper photo
        # but more GPU load.
        photo_res_row = QHBoxLayout()
        photo_res_row.setContentsMargins(20, 0, 0, 0)  # indent under the checkbox
        lbl_photo_res = QLabel("Photo resolution (px):")
        lbl_photo_res.setStyleSheet("color:#bbb;")
        lbl_photo_res.setToolTip(
            "<b>Photo resolution (longest axis)</b><br><br>"
            "Controls how many pixels the astrophoto is downsampled to "
            "before being projected onto the 3D photo rectangle.<br><br>"
            "Plotly 3D has no UV-mapped textures on meshes, so each "
            "pixel of the downsampled image becomes one WebGL "
            "<code>Scatter3d</code> marker. The spinbox to the right "
            "sets the <i>longest</i>-axis size; the other axis is "
            "scaled to preserve the photo's aspect ratio.<br><br>"
            "Only active while <i>Photo rectangle + viewing ray</i> is "
            "checked.")
        photo_res_row.addWidget(lbl_photo_res)
        self.spin_photo_res = QSpinBox()
        self.spin_photo_res.setRange(80, 1280)
        self.spin_photo_res.setSingleStep(40)
        self.spin_photo_res.setValue(PHOTO_DEFAULT_PX)
        self.spin_photo_res.setToolTip(
            "<b>Photo resolution (longest axis, in pixels)</b><br><br>"
            "Each pixel becomes a marker in WebGL. More markers = "
            "sharper photo but heavier on the GPU.<br><br>"
            "Typical choices:<br>"
            "&nbsp;• <b>80–160</b> — fast, very coarse. Useful on old "
            "GPUs or for quick previews. (Legacy default was 80.)<br>"
            "&nbsp;• <b>240–320</b> — good balance between detail and "
            "frame-rate; ≈ 40–100 k markers.<br>"
            "&nbsp;• <b>480</b> — <i>current default</i>: sharp, "
            "≈ 150–230 k markers depending on aspect ratio.<br>"
            "&nbsp;• <b>640–1280</b> — very sharp, ≈ 250 k – 1.6 M "
            "markers. Can stutter on integrated GPUs; try this if "
            "you have a discrete GPU and want print-quality detail.<br><br>"
            "The marker's on-screen size auto-adapts so adjacent pixels "
            "read as a continuous surface (size 4 under 160 px, "
            "3 for 160–319 px, 2 for 320 px and up).<br><br>"
            "Settings persist across sessions. Re-render after changing.")
        _nofocus(self.spin_photo_res)
        photo_res_row.addWidget(self.spin_photo_res)
        photo_res_row.addStretch(1)
        layout.addLayout(photo_res_row)

        # Debug toggle: use the legacy per-pixel Scatter3d grid
        # instead of the new textured Mesh3d quad.  The mesh quad is
        # what users want 99% of the time (one draw call, continuous
        # image, clean export).  The scatter grid is kept behind this
        # switch for A/B comparison and because some power-users want
        # true per-pixel control of marker size.
        self.chk_pixel_grid_debug = QCheckBox(
            "Debug: per-pixel scatter grid (slow)")
        self.chk_pixel_grid_debug.setChecked(False)
        self.chk_pixel_grid_debug.setToolTip(
            "<b>Legacy per-pixel scatter renderer</b><br><br>"
            "When <b>off</b> (the default), the photo is drawn as a "
            "subdivided <code>Mesh3d</code> with per-face colours "
            "baked from the texture — a single WebGL draw call that "
            "reads as a continuous image.<br><br>"
            "When <b>on</b>, each pixel becomes a <code>Scatter3d</code> "
            "marker (150–230k at 480 px). Slower, more GPU-heavy, and "
            "reads as a pointillist cloud rather than a photo — but "
            "useful for A/B comparison or if you want to see exactly "
            "which pixels sampled where on the 3D plane.")
        _nofocus(self.chk_pixel_grid_debug)
        pixel_grid_row = QHBoxLayout()
        pixel_grid_row.setContentsMargins(20, 0, 0, 0)
        pixel_grid_row.addWidget(self.chk_pixel_grid_debug)
        pixel_grid_row.addStretch(1)
        layout.addLayout(pixel_grid_row)

        # Grey out the spinbox and debug toggle when the photo itself
        # is disabled.
        def _sync_photo_res_enabled(checked: bool) -> None:
            self.spin_photo_res.setEnabled(bool(checked))
            lbl_photo_res.setEnabled(bool(checked))
            self.chk_pixel_grid_debug.setEnabled(bool(checked))

        self.chk_photo.toggled.connect(_sync_photo_res_enabled)
        _sync_photo_res_enabled(self.chk_photo.isChecked())

        parent_layout.addWidget(group)

    def _build_object_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Main Object")
        layout = QFormLayout(group)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_obj_name = QLabel("—")
        self.lbl_obj_name.setStyleSheet("color:#e0e0e0;font-weight:bold;")
        layout.addRow("Name:", self.lbl_obj_name)

        self.lbl_obj_type = QLabel("—")
        layout.addRow("Type:", self.lbl_obj_type)

        self.lbl_obj_dist = QLabel("—")
        self.lbl_obj_dist.setStyleSheet("color:#88aaff;")
        layout.addRow("Distance:", self.lbl_obj_dist)

        self.lbl_obj_source = QLabel("—")
        self.lbl_obj_source.setStyleSheet("color:#aaaaaa;font-size:9pt;")
        layout.addRow("Source:", self.lbl_obj_source)

        self.lbl_obj_gal = QLabel("—")
        self.lbl_obj_gal.setStyleSheet("color:#aaaaaa;font-size:9pt;")
        layout.addRow("Galactic l, b:", self.lbl_obj_gal)

        self.lbl_obj_arm = QLabel("—")
        self.lbl_obj_arm.setStyleSheet("color:#aaaaaa;font-size:9pt;")
        layout.addRow("Looking toward:", self.lbl_obj_arm)

        parent_layout.addWidget(group)

    def _build_data_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Data Sources")
        layout = QVBoxLayout(group)

        self.chk_use_online = QCheckBox("Query SIMBAD online")
        self.chk_use_online.setChecked(True)
        self.chk_use_online.setToolTip(
            "Query SIMBAD for the main object's distance and type.\n"
            "Disable to work offline using only the local cache.")
        _nofocus(self.chk_use_online)
        layout.addWidget(self.chk_use_online)

        cache_row = QHBoxLayout()
        self.btn_clear_cache = QPushButton("Clear Distance Cache")
        self.btn_clear_cache.setStyleSheet("font-size:8pt;padding:4px")
        _nofocus(self.btn_clear_cache)
        self.btn_clear_cache.setToolTip(
            "Discard all cached distance measurements.\n"
            "Next render will re-query SIMBAD.")
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
            "Discard all cached distance measurements?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
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
        self.edit_filename = QLineEdit("galactic_view_3d")
        self.edit_filename.setToolTip(
            "Base filename for HTML / PNG / CSV exports. "
            "A timestamp is appended automatically.")
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
        self.btn_render.setToolTip("Render the Milky Way 3D map (F5)")
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
            "Save a static 3D snapshot as PNG.")
        _nofocus(self.btn_export_png)
        self.btn_export_png.clicked.connect(self._on_export_png)
        export_row.addWidget(self.btn_export_png)

        self.btn_export_csv = QPushButton("CSV")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.setToolTip(
            "Save the scene metadata (object, distance, coordinates, "
            "photo corners) as CSV.")
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
            "background-color: #333333; border-radius: 4px;")
        self.lbl_image_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(self.lbl_image_info)

        self.tabs = QTabWidget()

        self.preview_widget = Preview3DWidget()
        self.preview_widget.repair_requested.connect(
            self._show_webengine_repair_dialog)
        # Route JS [GV3D] console messages into our _log pipeline so
        # they show up in the Log tab and Siril's log alongside Python
        # events.  Lets the user paste a unified timeline when
        # reporting "something strange happened in 3D".
        self.preview_widget.js_log.connect(self._on_js_log)
        self.tabs.addTab(self.preview_widget, "3D Map")

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet(
            "background-color:#1e1e1e;color:#dddddd;"
            "font-family:monospace;font-size:10pt;")
        self.info_text.setHtml(
            "<p style='color:#888'>Render the scene to see scene details here.</p>")
        self.tabs.addTab(self.info_text, "Info")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color:#1e1e1e;color:#cccccc;"
            "font-family:monospace;font-size:9pt;")
        self.tabs.addTab(self.log_text, "Log")

        r_layout.addWidget(self.tabs, 1)

        # One compact row: camera trackball + zoom/reset + export buttons.
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        btn_row.setSpacing(8)

        self.nav_pad = NavigationPad(
            run_js=self.preview_widget.run_js, parent=right)
        btn_row.addWidget(self.nav_pad)

        # Camera-preset buttons: named viewpoints that most
        # effectively communicate the scene.  Each one fires a
        # ``window.gv3d.flyTo(name)`` so the camera glides instead of
        # jumping — a 1.4 s ease-in-out animation that sells the depth
        # far better than any static starting angle does.
        # Extra "Spin" toggle exposes the auto-rotate animation.
        self._preset_buttons: list[QPushButton] = []

        # Preset/Spin/export buttons are styled consistently with the
        # NavigationPad via NAV_BUTTON_STYLE.  Height is a compact
        # ~36px (not the full trackball height) so the row reads as
        # "a trackball plus a toolbar" rather than as a row of tall
        # rectangles — which was the look in the pre-fix screenshot.
        _PRESET_BTN_HEIGHT = 36

        def _add_preset(text: str, tip: str, preset_name: str):
            b = QPushButton(text, parent=right)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setFixedHeight(_PRESET_BTN_HEIGHT)
            b.setStyleSheet(NAV_BUTTON_STYLE)
            b.clicked.connect(
                lambda _=False, n=preset_name: self._fly_camera_to(n))
            btn_row.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
            self._preset_buttons.append(b)
            return b

        _add_preset("Earth POV",
                    "Fly to Earth's viewpoint, looking down the "
                    "line of sight to the target.",
                    "earth_pov")
        _add_preset("Top",
                    "Top-down view of the galactic plane.",
                    "top")
        _add_preset("Side",
                    "Side view across the galactic disk.",
                    "side")
        _add_preset("Iso",
                    "Default isometric view.",
                    "reset")

        # Auto-rotate toggle.  A checkable button so its state stays in
        # sync with what the JS side is doing.  NAV_BUTTON_STYLE gives
        # the :checked state a clearly distinct fill + border, so the
        # user always knows at a glance whether Spin is on.
        self.btn_spin = QPushButton("Spin", parent=right)
        self.btn_spin.setCheckable(True)
        self.btn_spin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_spin.setFixedHeight(_PRESET_BTN_HEIGHT)
        self.btn_spin.setStyleSheet(NAV_BUTTON_STYLE)
        self.btn_spin.setToolTip(
            "Toggle slow auto-rotation of the scene.  Also triggered "
            "automatically after 10 s of inactivity; any mouse / "
            "keyboard / wheel input cancels it.")
        self.btn_spin.toggled.connect(self._toggle_auto_rotate)
        btn_row.addWidget(self.btn_spin, 0, Qt.AlignmentFlag.AlignVCenter)

        btn_row.addStretch(1)

        self.btn_open_folder = QPushButton("Open Output Folder")
        _nofocus(self.btn_open_folder)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.setFixedHeight(_PRESET_BTN_HEIGHT)
        self.btn_open_folder.setStyleSheet(NAV_BUTTON_STYLE)
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.btn_open_folder, 0,
                          Qt.AlignmentFlag.AlignVCenter)

        self.btn_open_html = QPushButton("Open Exported HTML")
        _nofocus(self.btn_open_html)
        self.btn_open_html.setEnabled(False)
        self.btn_open_html.setFixedHeight(_PRESET_BTN_HEIGHT)
        self.btn_open_html.setStyleSheet(NAV_BUTTON_STYLE)
        self.btn_open_html.clicked.connect(self._on_open_html)
        btn_row.addWidget(self.btn_open_html, 0,
                          Qt.AlignmentFlag.AlignVCenter)

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
        self.setWindowTitle("Svenesis GalacticView 3D")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 900)

    # ------------------------------------------------------------------
    # PERSISTENT SETTINGS
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        st = self._settings
        self.chk_arms.setChecked(st.value("show_arms", True, type=bool))
        self.chk_disk.setChecked(st.value("show_disk", True, type=bool))
        self.chk_neighbors.setChecked(
            st.value("show_neighbors", True, type=bool))
        self.chk_photo.setChecked(st.value("show_photo", True, type=bool))
        self.spin_photo_res.setValue(
            int(st.value("photo_res_px", PHOTO_DEFAULT_PX)))
        self.chk_pixel_grid_debug.setChecked(
            st.value("pixel_grid_debug", False, type=bool))
        self.chk_use_online.setChecked(
            st.value("use_online", True, type=bool))
        self.spin_dpi.setValue(int(st.value("dpi", 150)))
        mode = str(st.value("mode_override", "auto"))
        if mode == "galactic":
            self.radio_galactic.setChecked(True)
        elif mode == "cosmic":
            self.radio_cosmic.setChecked(True)
        else:
            self.radio_auto.setChecked(True)

    def _save_settings(self) -> None:
        st = self._settings
        st.setValue("show_arms", self.chk_arms.isChecked())
        st.setValue("show_disk", self.chk_disk.isChecked())
        st.setValue("show_neighbors", self.chk_neighbors.isChecked())
        st.setValue("show_photo", self.chk_photo.isChecked())
        st.setValue("photo_res_px", int(self.spin_photo_res.value()))
        st.setValue("pixel_grid_debug",
                    self.chk_pixel_grid_debug.isChecked())
        st.setValue("use_online", self.chk_use_online.isChecked())
        st.setValue("dpi", self.spin_dpi.value())
        st.setValue("mode_override", self._current_mode_override())

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    def _current_mode_override(self) -> str:
        if self.radio_galactic.isChecked():
            return "galactic"
        if self.radio_cosmic.isChecked():
            return "cosmic"
        return "auto"

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        if threading.current_thread() is not threading.main_thread():
            self._log_buffer.append(f"[GalacticView3D] {msg}")
            return
        self.log_text.append(f"[GalacticView3D] {msg}")
        try:
            self.siril.log(f"[GalacticView3D] {msg}")
        except (SirilError, OSError, RuntimeError, AttributeError):
            pass

    def _on_js_log(self, msg: str) -> None:
        """Handle a '[GV3D] …' console.log from the embedded page.

        The JS side is the authoritative source of truth for camera /
        preset / keyboard / pulse state — surfacing its events here
        turns the Log tab into a complete timeline that's safe to paste
        into a bug report.
        """
        try:
            # Strip the '[GV3D] ' tag so _log's own '[GalacticView3D]'
            # prefix doesn't stack awkwardly.  Add a 'JS:' marker so
            # users can tell which side of the boundary fired.
            trimmed = msg[len("[GV3D]"):].lstrip(" :")
            self._log(f"JS: {trimmed}")
        except Exception:
            # Never let logging throw inside a Qt signal slot.
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
    # SIRIL IMAGE / WCS LOADING (same 6-strategy pattern)
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
                    self._image_data = np.transpose(
                        self._image_data, (1, 2, 0))
                if self._image_data.ndim == 2:
                    self._image_data = np.stack(
                        [self._image_data] * 3, axis=-1)
                if self._image_data.shape[2] == 1:
                    self._image_data = np.repeat(
                        self._image_data, 3, axis=2)

            self._is_plate_solved = False
            self._wcs = None
            self._header_str = ""

            # --- WCS cache check (B5) --------------------------------------
            # If the Siril image file path + mtime match the last
            # detection, reuse the cached WCS instead of re-running the
            # whole 6-step ladder.  Saves hundreds of ms per render on
            # slow disks and avoids several FITS re-reads.
            cache_path = None
            cache_mtime = None
            try:
                fn = self.siril.get_image_filename()
                if fn and os.path.isfile(fn):
                    cache_path = os.path.abspath(fn)
                    cache_mtime = os.path.getmtime(cache_path)
            except Exception:
                cache_path = None
                cache_mtime = None
            cached = self._wcs_cache
            if (cache_path is not None
                    and cached.get("path") == cache_path
                    and cached.get("mtime") == cache_mtime
                    and cached.get("wcs") is not None):
                self._wcs = cached["wcs"]
                self._is_plate_solved = bool(cached.get("plate_solved"))
                self._header_str = str(cached.get("header_str") or "")
                self._log("WCS: reused cache for current image file.")

            # Step 1: header as dict
            if self._wcs is None:
                try:
                    header_dict = self.siril.get_image_fits_header(
                        return_as="dict")
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

            # Step 3: keyword flag
            if not self._is_plate_solved:
                try:
                    kw = self.siril.get_image_keywords()
                    if kw is not None:
                        self._is_plate_solved = bool(
                            getattr(kw, "pltsolvd", False))
                        if not self._is_plate_solved:
                            self._is_plate_solved = bool(
                                getattr(kw, "wcsdata", None))
                except Exception as e:
                    self._log(f"WCS keyword probe failed: {e}")

            # Step 4: build WCS from pix2radec sampling
            if self._wcs is None and self._is_plate_solved:
                self._wcs = self._build_wcs_from_siril()
                if self._wcs is not None:
                    self._log("WCS: built from sirilpy pix2radec")

            # Step 5: try pix2radec probe even without flag
            if self._wcs is None:
                try:
                    cx, cy = self._img_width / 2, self._img_height / 2
                    result = self.siril.pix2radec(cx, cy)
                    if result is not None:
                        self._is_plate_solved = True
                        self._wcs = self._build_wcs_from_siril()
                        if self._wcs is not None:
                            self._log("WCS: built from sirilpy pix2radec")
                except Exception as e:
                    self._log(f"WCS pix2radec probe failed: {e}")

            # Step 6: FITS file on disk
            if self._wcs is None:
                self._wcs = extract_wcs_from_fits_file(
                    self.siril, log_func=self._log)
                if self._wcs is not None:
                    self._is_plate_solved = True
                    self._log("WCS: extracted from FITS file on disk")

            if self._wcs is not None:
                self._is_plate_solved = True
                self._pixel_scale = compute_pixel_scale(self._wcs)
            else:
                self._pixel_scale = 1.0

            # Update WCS cache so the next render skips detection.
            if cache_path is not None:
                self._wcs_cache = {
                    "path": cache_path,
                    "mtime": cache_mtime,
                    "wcs": self._wcs,
                    "plate_solved": self._is_plate_solved,
                    "header_str": self._header_str,
                }

            ch_str = "RGB" if self._img_channels >= 3 else "Mono"
            wcs_str = ("plate-solved \u2713" if self._is_plate_solved
                       else "NOT plate-solved \u2717")
            self.lbl_image_info.setText(
                f"{self._img_width} \u00d7 {self._img_height} px  |  "
                f"{ch_str}  |  {wcs_str}")
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
                f"Failed to load image:\n{e}\n\n{traceback.format_exc()}")
            return False

    def _build_wcs_from_siril(self) -> WCS | None:
        try:
            w, h = self._img_width, self._img_height
            cx, cy = w / 2.0, h / 2.0
            ra_c, dec_c = self.siril.pix2radec(cx, cy)
            # H4 guard: sirilpy can return valid (ra, dec) near the poles,
            # but the linear-tangent CD matrix built below is singular at
            # |dec|→90° (cos(dec)→0 zeros out the RA column).  Hand off to
            # the FITS-header / file path instead of synthesising a bad
            # matrix.  0.5° margin is comfortable for real astrophotos.
            if abs(float(dec_c)) > 89.5:
                self._log(
                    f"_build_wcs_from_siril: skipping synthetic WCS — "
                    f"target too close to celestial pole "
                    f"(dec={dec_c:.3f}°); deferring to FITS-header path.")
                return None
            delta = 10.0
            ra_r, dec_r = self.siril.pix2radec(cx + delta, cy)
            ra_u, dec_u = self.siril.pix2radec(cx, cy + delta)
            cos_dec = math.cos(math.radians(dec_c))
            cd1_1 = (ra_r - ra_c) * cos_dec / delta
            cd1_2 = (ra_u - ra_c) * cos_dec / delta
            cd2_1 = (dec_r - dec_c) / delta
            cd2_2 = (dec_u - dec_c) / delta
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

            # H2: the round-trip check MUST probe a pixel that is NOT
            # CRPIX, otherwise the test is tautological.  With
            # crpix = [cx+1, cy+1] and origin=0 (1-based→0-based shift),
            # all_pix2world([[cx, cy]], 0) reduces to evaluating CRVAL at
            # offset 0 and returns (ra_c, dec_c) by construction.
            # Instead, probe the same displaced pixel we used to
            # estimate cd1_1/cd2_1 and compare to the MEASURED
            # (ra_r, dec_r).  If the linear matrix inverts correctly,
            # the error should be tiny (sub-arcsec for typical fields);
            # we allow 0.01° ≈ 36″ to cover mild tangent-plane
            # curvature at delta=10 px.
            test_ra, test_dec = wcs.all_pix2world(
                [[cx + delta, cy]], 0)[0]
            # RA wraparound: shortest angular distance instead of raw
            # subtraction (a field at RA≈0° can round-trip to 359.99°
            # which would fail a naive |Δ|<0.01 check).
            d_ra = (((test_ra - ra_r) + 180.0) % 360.0) - 180.0
            d_dec = test_dec - dec_r
            if abs(d_ra) < 0.01 and abs(d_dec) < 0.01:
                return wcs
            self._log(
                f"_build_wcs_from_siril: round-trip mismatch at probe "
                f"pixel (Δra={d_ra*3600:.2f}″, Δdec={d_dec*3600:.2f}″) "
                f"— discarding synthetic WCS.")
        except Exception as e:
            self._log(f"_build_wcs_from_siril failed: {e}")
        return None

    # ------------------------------------------------------------------
    # RENDER WORKFLOW
    # ------------------------------------------------------------------
    def _on_render(self) -> None:
        """Public entry — re-entrancy-guarded wrapper around _do_render.

        The real work lives in _do_render() so every early-return there
        is automatically caught by the try/finally below.
        """
        if getattr(self, "_rendering", False):
            # Silent drop: logging would risk landing in the old log
            # buffer that the in-flight render is about to clear.
            return
        self._rendering = True
        try:
            self.btn_render.setEnabled(False)
        except Exception:
            pass
        try:
            self._do_render()
        finally:
            self._rendering = False
            try:
                self.btn_render.setEnabled(True)
            except Exception:
                pass

    def _do_render(self) -> None:
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log_text.clear()

        self._log("Starting GalacticView 3D render...")
        self._update_progress(5, "Loading image from Siril...")

        if not self._load_from_siril():
            self.progress.setVisible(False)
            self.lbl_status.setText("Status: Failed to load image")
            return

        if not self._is_plate_solved or self._wcs is None:
            QMessageBox.warning(
                self, "Not Plate-Solved",
                "The image is not plate-solved. Please run Plate Solving first.\n\n"
                "In Siril: Tools \u2192 Astrometry \u2192 Image Plate Solver...")
            self._log("ERROR: Image is not plate-solved. Aborting.")
            self.progress.setVisible(False)
            return

        # Image centre + four corners
        try:
            cx, cy = self._img_width / 2.0, self._img_height / 2.0
            center_ra, center_dec = self.siril.pix2radec(cx, cy)
            corner_ra, corner_dec = self.siril.pix2radec(0, 0)
            c1 = SkyCoord(center_ra, center_dec, unit="deg")
            c2 = SkyCoord(corner_ra, corner_dec, unit="deg")
            fov_radius_deg = float(c1.separation(c2).deg)
        except Exception as e:
            self._log(f"FOV compute failed: {e}")
            QMessageBox.critical(self, "Error",
                                 f"Could not compute field-of-view:\n{e}")
            self.progress.setVisible(False)
            return

        # Galactic coordinates of image centre
        l_deg, b_deg = radec_to_galactic(float(center_ra), float(center_dec))
        self._log(f"Image centre: RA={center_ra:.4f} Dec={center_dec:.4f}")
        self._log(f"Galactic:    l={l_deg:.2f}° b={b_deg:.2f}°, "
                  f"FOV radius {fov_radius_deg:.3f}°")

        # Identify main object
        self._update_progress(25, "Identifying main object...")
        obj_name, simbad_result = identify_main_object(
            self.siril, self._wcs,
            self._img_width, self._img_height,
            float(center_ra), float(center_dec),
            fov_radius_deg, log_func=self._log)
        self._flush_log_buffer()

        # Extract obj_type from the SIMBAD result of the auto pick so we
        # can seed the picker with authoritative Type + Distance info.
        obj_type = ""
        if simbad_result is not None:
            for col in ("OTYPE", "otype"):
                if col in simbad_result.colnames:
                    try:
                        obj_type = str(simbad_result[col][0]).strip()
                    except Exception as e:
                        self._log(f"obj_type extract failed ({col}): {e}")
                    break

        # Resolve the auto-pick's distance NOW (cache → SIMBAD → z →
        # type-median) so the picker row shows the same values as the
        # main-object panel instead of dashes.
        auto_dist_ly = None
        auto_dist_err = 0.0
        auto_dist_src = ""
        auto_dist_conf = "none"
        if obj_name:
            self._update_progress(30, "Resolving auto-pick distance...")
            (auto_dist_ly, auto_dist_err,
             auto_dist_src, auto_dist_conf) = resolve_object_distance(
                obj_name, obj_type, simbad_result, self._cache,
                use_online=self.chk_use_online.isChecked(),
                log_func=self._log)
            self._flush_log_buffer()

        # Always show the target picker (both galactic and cosmic scenes)
        # so the user can confirm or override the auto pick — even for a
        # single hit, or an empty cone-search result.
        self._update_progress(35, "Collecting SIMBAD candidates...")
        candidates = []
        if self.chk_use_online.isChecked():
            candidates = collect_simbad_candidates(
                float(center_ra), float(center_dec),
                fov_radius_deg, log_func=self._log,
                siril=self.siril,
                img_w=self._img_width, img_h=self._img_height,
                pixel_scale_arcsec=self._pixel_scale,
                wcs=getattr(self, "_wcs", None))
            self._flush_log_buffer()
        else:
            self._log("Offline mode: skipping SIMBAD cone-search "
                      "(picker will be empty).")

        # If the cone-search was empty but we identified the main target
        # (e.g. via OBJECT keyword + distance cache), seed the picker
        # with a fully-populated row built from simbad_result + the
        # already-resolved distance.
        if not candidates and obj_name:
            self._log(f"Seeding picker with auto-identified target "
                      f"'{obj_name}' (cone-search was empty).")

            def _pick(tbl, *names):
                if tbl is None:
                    return None
                for n in names:
                    if n in tbl.colnames:
                        try:
                            return tbl[n][0]
                        except Exception:
                            return None
                return None

            mag_seed = 99.0
            plx_seed = float("nan")
            z_seed = float("nan")
            if simbad_result is not None:
                v = _pick(simbad_result, "V", "flux_V", "FLUX_V")
                mag_seed = _safe_float(v, 99.0) if v is not None else 99.0
                v = _pick(simbad_result, "plx_value", "PLX_VALUE",
                          "plx", "PLX")
                plx_seed = (_safe_float(v, float("nan"))
                            if v is not None else float("nan"))
                v = _pick(simbad_result, "rvz_redshift", "RVZ_REDSHIFT",
                          "z_value", "Z_VALUE")
                z_seed = (_safe_float(v, float("nan"))
                          if v is not None else float("nan"))

            dist_seed = (float(auto_dist_ly)
                         if auto_dist_ly is not None else float("nan"))
            dist_src_seed = (auto_dist_src.lower().replace(" ", "_")
                             if auto_dist_src else "unknown")
            # Map resolve_object_distance labels to picker's short tags
            if "cache" in dist_src_seed:
                dist_src_seed = "cache"
            elif "simbad" in dist_src_seed:
                dist_src_seed = "simbad"
            elif "redshift" in dist_src_seed or dist_src_seed.startswith("z"):
                dist_src_seed = "z"

            candidates = [{
                "name": obj_name,
                "simbad_id": obj_name,
                "otype": obj_type,
                "mag": mag_seed,
                "ra": float(center_ra),
                "dec": float(center_dec),
                "sep_deg": 0.0,
                "plx_mas": plx_seed,
                "redshift": z_seed,
                "dist_ly_estimate": dist_seed,
                "dist_source_hint": dist_src_seed,
                "rank_key": (0, mag_seed if mag_seed < 90 else 99.0, 0.0),
            }]

        dlg = TargetPickerDialog(candidates, parent=self,
                                 preselect_name=obj_name)
        user_changed_target = False
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sel = dlg.selected_candidate()
            if sel:
                picked = sel["name"]
                if picked != obj_name:
                    self._log(f"User selected target: '{picked}' "
                              f"(auto pick was '{obj_name or '—'}')")
                    obj_name = picked
                    simbad_result = _simbad_query_object(
                        picked, log_func=self._log)
                    user_changed_target = True
                else:
                    self._log(f"Confirmed auto pick: '{obj_name}'")
        else:
            self._log("Target selection cancelled - using auto pick.")

        # Re-derive obj_type if the user switched target.
        if user_changed_target:
            obj_type = ""
            if simbad_result is not None:
                for col in ("OTYPE", "otype"):
                    if col in simbad_result.colnames:
                        try:
                            obj_type = str(simbad_result[col][0]).strip()
                        except Exception as e:
                            self._log(
                                f"obj_type re-extract failed ({col}): {e}")
                        break

        if not obj_name:
            obj_name = "Unknown target"
            self._log("No main object identified - proceeding without SIMBAD distance.")

        # Re-resolve distance for the picked target (cheap cache hit if
        # unchanged); skip the duplicate query when the user confirmed
        # the auto pick.
        if user_changed_target or auto_dist_ly is None:
            self._update_progress(45, "Resolving distance...")
            dist_ly, dist_err_ly, source, confidence = resolve_object_distance(
                obj_name, obj_type, simbad_result, self._cache,
                use_online=self.chk_use_online.isChecked(),
                log_func=self._log)
            self._flush_log_buffer()
        else:
            dist_ly, dist_err_ly = auto_dist_ly, auto_dist_err
            source, confidence = auto_dist_src, auto_dist_conf
        self.lbl_cache_info.setText(self._cache_info_text())

        # Decide mode
        override = self._current_mode_override()
        if override == "galactic":
            mode = ViewMode.GALACTIC
        elif override == "cosmic":
            mode = ViewMode.COSMIC
        else:
            mode = decide_mode(dist_ly, obj_type)
        self._log(f"Mode: {mode.value} (override={override}, "
                  f"type={obj_type or '?'})")

        # P4.12 — read the selected distance metric from the radio
        # group and apply it for the entire render pass.  scale_dist()
        # consults this global; setting it BEFORE corner / pin / texture
        # geometry is built means everything in the scene honours the
        # metric in 3D, not just the labels.  Reset on the way out.
        if self.radio_metric_co.isChecked():
            metric_choice = "comoving"
        elif self.radio_metric_ad.isChecked():
            metric_choice = "angular-diameter"
        else:
            metric_choice = "light-travel"
        global _ACTIVE_DISTANCE_METRIC
        _saved_metric = _ACTIVE_DISTANCE_METRIC
        _ACTIVE_DISTANCE_METRIC = metric_choice
        if mode is ViewMode.COSMIC and metric_choice != "light-travel":
            self._log(f"Distance metric: {metric_choice} "
                      "(cosmic mode 3D positions reflect this).")

        # Photo corners + centre point in 3D
        placeholder_dist_ly = (dist_ly
                               if (dist_ly and dist_ly > 0)
                               else (5_000.0
                                     if mode is ViewMode.GALACTIC
                                     else 5_000_000.0))
        # Visualization-size floor so the frame is always visible at
        # galactic/cosmic scale. Galactic: 1 unit = 1000 ly -> 3000 ly edge;
        # Cosmic: 1 unit = 100,000 ly -> 300,000 ly edge. Orientation and
        # aspect of the real FOV are preserved.
        min_vis = 3.0 if mode is ViewMode.GALACTIC else 3.0
        corners_3d = get_photo_corners_3d(
            self.siril, self._img_width, self._img_height,
            placeholder_dist_ly, mode, min_visual_size=min_vis)
        photo_center_xyz = gal_to_xyz(l_deg, b_deg,
                                      scale_dist(placeholder_dist_ly, mode))

        # --- Photo texture (primary + debug) -----------------------------
        # Primary path: a subdivided Mesh3d quad with per-face colours
        # baked from the downsampled image.  One WebGL draw call,
        # reads as a continuous photo.
        #
        # Debug path (opt-in via chk_pixel_grid_debug): the legacy
        # per-pixel Scatter3d cloud.  Useful for A/B comparison but
        # slow and visually pointillist.
        photo_texture_mesh = None
        pixel_grid = None
        if (self.chk_photo.isChecked()
                and self._image_data is not None
                and corners_3d is not None):
            try:
                photo_max_px = int(self.spin_photo_res.value())
                want_debug_grid = bool(
                    self.chk_pixel_grid_debug.isChecked())
                img = self._image_data

                def _cheap_fingerprint(a: np.ndarray) -> int:
                    """~4 KB sampled hash — fast for large mono/colour
                    astrophotos but still distinguishes different frames
                    of the same shape (corners + a diagonal stride).
                    """
                    try:
                        flat = a.ravel()
                        n = flat.size
                        if n == 0:
                            return 0
                        step = max(1, n // 512)  # ≤ 512 samples
                        samples = flat[::step]
                        h, w = a.shape[:2]
                        corners_sig = (
                            int(a[0, 0].sum() if a.ndim >= 2 else a[0]),
                            int(a[0, w - 1].sum() if a.ndim >= 2 else a[-1]),
                            int(a[h - 1, 0].sum() if a.ndim >= 2 else a[0]),
                            int(a[h - 1, w - 1].sum() if a.ndim >= 2 else a[-1]),
                        )
                        return hash((samples.tobytes(), corners_sig))
                    except Exception:
                        return 0

                # Shared cache key for both mesh + scatter — both are
                # derived from the same tex + corners, so a single
                # fingerprint invalidates both.
                cache_key = (
                    tuple(img.shape),
                    int(img.nbytes),
                    str(img.dtype),
                    _cheap_fingerprint(img),
                    int(photo_max_px),
                    tuple(
                        tuple(round(float(v), 6) for v in c)
                        for c in corners_3d
                    ),
                )
                cached = self._pixel_grid_cache
                cached_mesh = cached.get("mesh")
                cached_grid = cached.get("grid")
                if cached.get("key") == cache_key and cached_mesh:
                    photo_texture_mesh = cached_mesh
                    self._log(
                        f"Photo texture mesh: reused cached quad "
                        f"({photo_texture_mesh['nx']}x"
                        f"{photo_texture_mesh['ny']} cells).")
                    if want_debug_grid and cached_grid:
                        pixel_grid = cached_grid
                        self._log(
                            f"Photo pixel grid (debug): reused cached "
                            f"({pixel_grid['w']}x{pixel_grid['h']}, "
                            f"{pixel_grid['w']*pixel_grid['h']:,} "
                            f"markers).")

                if photo_texture_mesh is None:
                    tex = prepare_texture_array(
                        self._image_data, max_size=photo_max_px)
                    photo_texture_mesh = build_photo_texture_mesh(
                        corners_3d, tex)
                    if photo_texture_mesh:
                        self._log(
                            f"Photo texture mesh: "
                            f"{photo_texture_mesh['nx']}x"
                            f"{photo_texture_mesh['ny']} cells "
                            f"({2*photo_texture_mesh['nx']*photo_texture_mesh['ny']:,} "
                            f"triangles).")
                    # Rebuild (or invalidate) debug grid alongside.
                    if want_debug_grid:
                        pixel_grid = build_photo_pixel_grid(tex, corners_3d)
                        if pixel_grid:
                            longest = max(pixel_grid["w"],
                                          pixel_grid["h"])
                            if longest >= 320:
                                pixel_grid["marker_size"] = 2
                            elif longest >= 160:
                                pixel_grid["marker_size"] = 3
                            else:
                                pixel_grid["marker_size"] = 4
                            self._log(
                                f"Photo pixel grid (debug): "
                                f"{pixel_grid['w']}x{pixel_grid['h']} "
                                f"({pixel_grid['w']*pixel_grid['h']:,} "
                                f"markers, "
                                f"size={pixel_grid['marker_size']}).")
                    self._pixel_grid_cache = {
                        "key": cache_key,
                        "mesh": photo_texture_mesh,
                        "grid": pixel_grid,
                    }
            except Exception as exc:
                self._log(f"Photo texture build failed: {exc}")
                photo_texture_mesh = None
                pixel_grid = None

        # Update GUI object info panel
        self.lbl_obj_name.setText(obj_name)
        self.lbl_obj_type.setText(
            OBJECT_TYPE_LABELS.get(obj_type, obj_type or "—"))
        if dist_ly:
            if dist_ly < 1e6:
                dtxt = f"{dist_ly:,.0f} ly"
            elif dist_ly < 1e9:
                dtxt = f"{dist_ly/1e6:.2f} Mly"
            else:
                dtxt = f"{dist_ly/1e9:.2f} Gly"
            if dist_err_ly:
                dtxt += f" ± {dist_err_ly:,.0f} ly"
            self.lbl_obj_dist.setText(dtxt)
        else:
            self.lbl_obj_dist.setText("unknown")
        self.lbl_obj_source.setText(f"{source} ({confidence})")
        self.lbl_obj_gal.setText(f"l={l_deg:.2f}°, b={b_deg:.2f}°")

        # Which arm is the line of sight pointing toward?
        arm_hint = self._which_direction(l_deg, b_deg)
        self.lbl_obj_arm.setText(arm_hint)

        # P1.2 — physical arm membership of the target itself.
        # `_which_direction` answers "if I look this way from Earth,
        # what arm does the line of sight cross?", which is angular.
        # `which_arm` answers "is the target physically inside an
        # arm?" by comparing its 3D position to each arm centerline.
        # Returns None for distant (>60 kly) or out-of-plane (|b|>5°)
        # targets where arm membership isn't meaningful.
        target_arm_membership: tuple[str, float] | None = None
        if mode is ViewMode.GALACTIC and dist_ly:
            try:
                target_arm_membership = which_arm(
                    l_deg, b_deg, float(dist_ly))
                if target_arm_membership is not None:
                    arm_name, perp_ly = target_arm_membership
                    self._log(
                        f"Target arm membership: {arm_name} "
                        f"(centerline ≈ {perp_ly:,.0f} ly away).")
            except Exception as e:
                self._log(f"Arm-membership inference failed: {e}")

        # Constellation stick figure containing the target — galactic
        # mode only, silently ``None`` when the constellation isn't in
        # our curated set.  Small, fast; no caching needed.
        constellation_lines = None
        if mode is ViewMode.GALACTIC:
            try:
                # Anchor the stick figure to the target's distance
                # shell rather than a fixed 800-ly shell.  When the
                # target is at e.g. 5 kly the constellation drawing
                # otherwise floats in the 800-ly foreground and reads
                # as disconnected from the photo.  Putting it at the
                # target's distance frames the field correctly: the
                # photo rectangle sits inside the stick figure's
                # outline, communicating "this is the patch of sky
                # that constellation is in".  Floor at 400 ly so the
                # geometry doesn't collapse for sub-kly targets.
                shell_ly_target = max(400.0, float(dist_ly or 800.0))
                constellation_lines = build_constellation_lines(
                    float(center_ra), float(center_dec), mode,
                    shell_ly=shell_ly_target)
                if constellation_lines:
                    self._log(
                        f"Constellation: {constellation_lines['name']} "
                        f"stick figure on "
                        f"{constellation_lines['shell_ly']:.0f} ly shell.")
            except Exception as e:
                self._log(f"Constellation build failed: {e}")

        # Build scene dict + figure
        self._update_progress(70, "Building 3D scene...")
        dist_label = (dtxt if dist_ly else "distance unknown")
        title = (f"Svenesis GalacticView 3D — {obj_name} "
                 f"({mode.value} mode)")

        # --- Nearest / farthest fan-out across the picked field ------
        # The chosen target gets a bright dotted ring at its distance.
        # If the SIMBAD candidate list contains other objects with
        # known distances, also surface the nearest and farthest of
        # them as their own dotted rings.  This converts the previous
        # "±1σ statistical companion rings" (which most users found
        # opaque) into a depth fan that matches astronomers' mental
        # model: "what's in the foreground / target / background of my
        # photo?".
        nearest_dist_ly: float | None = None
        nearest_name: str | None = None
        farthest_dist_ly: float | None = None
        farthest_name: str | None = None
        try:
            ranked = []
            dropped_unreliable = 0
            for c in (candidates or []):
                name_c = c.get("name") or "?"
                # Exclude the picked target — its ring is drawn
                # separately as the bright "chosen" ring.  Without
                # this exclusion, "nearest" would coincide with the
                # chosen ring whenever the picked object happens to
                # be the closest in the field (very common: users
                # usually point their camera at a foreground galaxy
                # and the SIMBAD cone-search picks up more distant
                # background objects).
                if name_c == obj_name:
                    continue
                d = c.get("dist_ly_estimate")
                if d is None:
                    continue
                # NaN guard: NaN != NaN
                if not (d == d) or d <= 0:
                    continue
                # Sanity: SIMBAD returns parallaxes for many
                # extragalactic objects too, but they're pure noise
                # for anything past a few hundred parsecs (a sub-mas
                # parallax has a fractional error ~100 %).  When the
                # candidate has a non-trivial redshift (z > 0.001
                # → ≥ ~4 Mly) AND its distance was sourced from
                # parallax, the parallax distance is essentially a
                # random number and would land the depth-fan ring at
                # an absurd few-thousand-ly radius around a
                # multi-Mly target.  Drop those entries from the
                # ranking; the redshift-derived distance would be
                # the right answer but our pipeline already picked
                # plx upstream.
                src = c.get("dist_source_hint", "")
                z = c.get("redshift")
                if (src == "plx" and z is not None
                        and float(z) > 0.001):
                    dropped_unreliable += 1
                    continue
                ranked.append((float(d), name_c))
            if ranked:
                ranked.sort(key=lambda t: t[0])
                nearest_dist_ly, nearest_name = ranked[0]
                farthest_dist_ly, farthest_name = ranked[-1]
                # Single other candidate → nearest == farthest.  Show
                # only one ring (the nearest) so we don't paint two
                # rings at the same radius and label them confusingly.
                if len(ranked) == 1:
                    farthest_dist_ly = None
                    farthest_name = None
                self._log(
                    f"Depth fan: chosen={obj_name!r} "
                    f"({(dist_ly or 0):,.0f} ly), "
                    f"nearest-other={nearest_name!r} "
                    f"({nearest_dist_ly:,.0f} ly)"
                    + (f", farthest-other={farthest_name!r} "
                       f"({farthest_dist_ly:,.0f} ly)"
                       if farthest_dist_ly else "")
                    + f" [from {len(ranked)} other candidates"
                    + (f"; {dropped_unreliable} dropped: "
                       f"plx+z disagreement"
                       if dropped_unreliable else "")
                    + "]."
                )
            else:
                self._log(
                    "Depth fan: no other candidates with known "
                    "distance — only the chosen-target ring will "
                    "be drawn."
                )
        except Exception as e:
            self._log(f"Depth fan build failed: {e}")

        scene = {
            "mode": mode,
            "object_name": obj_name,
            "object_type": obj_type,
            "dist_ly": dist_ly,
            "dist_err_ly": dist_err_ly,
            "nearest_dist_ly": nearest_dist_ly,
            "nearest_name": nearest_name,
            "farthest_dist_ly": farthest_dist_ly,
            "farthest_name": farthest_name,
            "dist_source": source,
            "dist_confidence": confidence,
            "center_ra": float(center_ra),
            "center_dec": float(center_dec),
            "l_deg": l_deg,
            "b_deg": b_deg,
            "fov_radius_deg": fov_radius_deg,
            "photo_corners": corners_3d if self.chk_photo.isChecked() else None,
            "photo_center_xyz": (photo_center_xyz
                                 if self.chk_photo.isChecked() else None),
            "photo_texture_mesh": photo_texture_mesh,
            "photo_pixel_grid": pixel_grid,
            "constellation_lines": constellation_lines,
            "background_pins": (
                build_background_pins(
                    self.siril, self._img_width, self._img_height,
                    corners_3d, float(dist_ly or 0.0),
                    candidates, obj_name, mode, log_func=self._log,
                    wcs=self._wcs)
                if (self.chk_photo.isChecked() and corners_3d is not None
                    and candidates and dist_ly)
                else []),
            "show_arms": self.chk_arms.isChecked(),
            "show_disk": self.chk_disk.isChecked(),
            "show_neighbors": (self.chk_neighbors.isChecked()
                               and mode is ViewMode.COSMIC),
            # P4.10 — galactic-landmarks catalog (open clusters,
            # globular clusters, nebulae).  Default-on; the legend
            # entries let users hide individual kinds.
            "show_landmarks": True,
            "title": title,
            "distance_label": dist_label,
            "arm_hint": arm_hint,
            "target_arm_membership": target_arm_membership,
            # P4.12 — recorded so build_galaxy_figure() (and any
            # subsequent re-render from cache) reuses the same metric.
            "distance_metric": metric_choice,
        }
        self._last_scene = scene
        self._populate_info_tab(scene)

        # Scene summary in the log — one clean line per render with
        # everything needed to diagnose "the scene looked wrong" reports
        # without having to reproduce.  Includes mode, target, distance,
        # scene-space photo centre, and which toggles are on.
        try:
            pc = scene.get("photo_center_xyz")
            pc_txt = ("none" if pc is None
                      else f"({pc[0]:+.3f}, {pc[1]:+.3f}, {pc[2]:+.3f})")
            toggles = []
            for k in ("show_arms", "show_stars", "show_bulge",
                      "show_disk", "show_neighbors"):
                if scene.get(k):
                    toggles.append(k.replace("show_", ""))
            self._log(
                f"Scene built: mode={mode.value}, target={obj_name!r}, "
                f"dist_ly={dist_ly if dist_ly else 0:,.0f}, "
                f"photo_center={pc_txt}, "
                f"toggles=[{', '.join(toggles) or '-'}]."
            )
        except Exception:
            pass

        fig = build_galaxy_figure(scene) if HAS_PLOTLY else None
        # P4.12 — restore the original metric now that geometry is
        # done.  build_galaxy_figure already sets/resets internally,
        # but the data-pipeline calls (build_background_pins, photo
        # geometry, etc.) ran with the override set above; this is
        # the matched cleanup point.
        _ACTIVE_DISTANCE_METRIC = _saved_metric
        self._last_figure = fig
        # Trace-count summary: count of Scatter3d + Mesh3d traces in the
        # finished figure.  If a user reports "the photo is missing",
        # this tells us whether the photo trace was actually built or
        # not, which narrows the bug by 80%.
        try:
            if fig is not None and hasattr(fig, "data"):
                self._log(
                    f"Figure has {len(fig.data)} trace(s); "
                    f"types=[{', '.join(sorted({t.type for t in fig.data}))}]"
                )
        except Exception:
            pass

        # Prepare paths
        try:
            wd = self.siril.get_siril_wd() or os.getcwd()
        except Exception:
            wd = os.getcwd()
        base = self.edit_filename.text().strip() or "galactic_view_3d"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._last_html_path = os.path.join(wd, f"{base}_{ts}.html")
        self._last_png_path = os.path.join(wd, f"{base}_{ts}.png")
        self._last_csv_path = os.path.join(wd, f"{base}_{ts}.csv")

        # Render
        self._update_progress(90, "Rendering...")
        rendered = False
        if fig is not None and HAS_WEBENGINE:
            try:
                html_content = pio.to_html(fig, full_html=True,
                                           include_plotlyjs="directory")
                # Inject window.gv3d (camera presets, fly-through,
                # auto-rotate) into the page before handing it to
                # QWebEngineView.  Inline injection avoids the race
                # where a button click during load-in-flight would
                # dispatch JS that found no window.gv3d.
                html_content = _inject_camera_bootstrap(
                    html_content, scene.get("photo_center_xyz"),
                    mode=scene.get("mode"))
                self.preview_widget.show_html(html_content)
                self._log("Rendered interactive Plotly view (QWebEngineView).")
                rendered = True
            except Exception as e:
                self._log(f"Plotly render failed: {e}")

        if not rendered:
            if WEBENGINE_ERROR:
                self._log(f"WebEngine import failed: {WEBENGINE_ERROR}")
                self._log("Tip: click \u201cRepair WebEngine\u2026\u201d "
                          "on the 3D Map pane.")
            try:
                self._log("WebEngine unavailable - using matplotlib preview.")
                render_matplotlib_galaxy(
                    scene, self._last_png_path,
                    dpi=self.spin_dpi.value())
                self.preview_widget.show_png(self._last_png_path)
            except Exception as e:
                self._log(f"Matplotlib fallback failed: {e}")
                QMessageBox.critical(
                    self, "Render Error",
                    f"3D render failed:\n{e}\n\n{traceback.format_exc()}")
                self.progress.setVisible(False)
                return

            if fig is not None:
                try:
                    html_content = pio.to_html(fig, full_html=True,
                                               include_plotlyjs="cdn")
                    html_content = _inject_camera_bootstrap(
                        html_content, scene.get("photo_center_xyz"),
                        mode=scene.get("mode"))
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

        self._update_progress(100, f"Done — {obj_name}")
        self._log("Render complete.")
        self.progress.setVisible(False)
        gc.collect()

    def _which_direction(self, l_deg: float, b_deg: float) -> str:
        """Short hint about what part of the sky this line of sight points to."""
        if abs(b_deg) > 60:
            return ("Galactic north pole"
                    if b_deg > 0 else "Galactic south pole")
        l = l_deg % 360
        if l < 30 or l >= 330:
            return "Toward Galactic Center (Sgr A*)"
        if 150 < l < 210:
            return "Toward Galactic Anti-centre"
        if 60 <= l <= 120:
            return "Along Galactic rotation"
        if 240 <= l <= 300:
            return "Opposite Galactic rotation"
        if 30 <= l < 60:
            return "Inner Sagittarius direction"
        if 120 < l <= 150:
            return "Outer Perseus direction"
        if 210 <= l < 240:
            return "Outer Carina direction"
        return f"l = {l_deg:.0f}°"

    def _populate_info_tab(self, scene: dict) -> None:
        mode = scene["mode"]
        dist_ly = scene.get("dist_ly") or 0
        err = scene.get("dist_err_ly") or 0
        html = [
            "<h2 style='color:#88aaff;'>Scene Overview</h2>",
            "<table cellpadding='6'>",
            f"<tr><td><b>Object</b></td><td>{scene['object_name']}</td></tr>",
            f"<tr><td><b>Type</b></td><td>"
            f"{OBJECT_TYPE_LABELS.get(scene.get('object_type',''), scene.get('object_type') or '—')}"
            "</td></tr>",
            f"<tr><td><b>Distance</b></td><td>"
            f"{'{:,.0f} ly'.format(dist_ly) if dist_ly else 'unknown'}"
            f"{' ± {:,.0f} ly'.format(err) if err else ''}</td></tr>",
            f"<tr><td><b>Distance source</b></td><td>"
            f"{scene['dist_source']} ({scene['dist_confidence']})</td></tr>",
            f"<tr><td><b>Image centre</b></td><td>"
            f"RA = {scene['center_ra']:.4f}°, "
            f"Dec = {scene['center_dec']:.4f}°</td></tr>",
            f"<tr><td><b>Galactic</b></td><td>"
            f"l = {scene['l_deg']:.2f}°, "
            f"b = {scene['b_deg']:.2f}°</td></tr>",
            f"<tr><td><b>Viewing direction</b></td><td>"
            f"{scene['arm_hint']}</td></tr>",
            f"<tr><td><b>FOV radius</b></td><td>"
            f"{scene['fov_radius_deg']:.3f}°</td></tr>",
            f"<tr><td><b>Mode</b></td><td>{mode.value} "
            f"({'1 unit = 1,000 ly' if mode is ViewMode.GALACTIC else '1 unit = 100,000 ly + log beyond 1 Mly'})</td></tr>",
            "</table>",
            "<hr>",
            "<h3 style='color:#88aaff;'>Milky Way model</h3>",
            "<ul>",
            "<li>Earth at origin (0, 0, 0), located in the Orion Arm.</li>",
            f"<li>Galactic Center (Sgr A*) at "
            f"{EARTH_TO_GC_LY:,} ly along +X.</li>",
            f"<li>Milky Way radius: {GALAXY_RADIUS_LY:,} ly, "
            f"disc half-thickness {GALAXY_THICK_LY:,} ly.</li>",
            "<li>Five spiral arms (log-spirals after Hou &amp; Han 2014).</li>",
            "</ul>",
        ]
        self.info_text.setHtml("\n".join(html))

    # ------------------------------------------------------------------
    # EXPORT ACTIONS
    # ------------------------------------------------------------------
    def _on_export_html(self) -> None:
        if self._last_figure is None:
            return
        try:
            html_str = pio.to_html(self._last_figure, full_html=True,
                                   include_plotlyjs="cdn")
            # Inject the camera-preset + fly-through JS so the exported
            # file behaves identically to the in-app view.
            photo_center = (self._last_scene.get("photo_center_xyz")
                            if self._last_scene else None)
            scene_mode = (self._last_scene.get("mode")
                          if self._last_scene else None)
            html_str = _inject_camera_bootstrap(html_str, photo_center,
                                                mode=scene_mode)
            with open(self._last_html_path, "w", encoding="utf-8") as f:
                f.write(html_str)
            self._log(f"Exported HTML: {self._last_html_path}")
            self.btn_open_html.setEnabled(True)
            QMessageBox.information(
                self, "HTML Exported",
                f"Interactive 3D map saved:\n{self._last_html_path}")
        except Exception as e:
            self._log(f"HTML export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export HTML:\n{e}")

    def _capture_current_camera(self) -> dict | None:
        """Read the current Plotly camera back from the live WebEngine
        view via a synchronous JS round-trip.

        This spins a nested ``QEventLoop`` for up to 2 s.  We guard
        every step so that:
          * the view being torn down mid-call doesn't crash;
          * the event loop is always properly quit and deleted;
          * a callback that arrives AFTER the widget is gone can't
            poke a deleted Python object (the closure only writes into
            ``holder``, not into ``self`` or the view).
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
        # ``sip`` lets us check whether a QObject's C++ side has been
        # destroyed.  It's part of PyQt6's runtime; if import fails we
        # fall back to a best-effort "not deleted" assumption.
        try:
            from PyQt6 import sip  # type: ignore
        except Exception:
            sip = None  # noqa: N806

        def _is_alive(obj) -> bool:
            if obj is None:
                return False
            if sip is not None:
                try:
                    return not sip.isdeleted(obj)
                except Exception:
                    return True
            return True

        loop = QEventLoop()
        holder: dict = {"raw": None, "done": False}

        def _got(raw):
            holder["raw"] = raw
            holder["done"] = True
            if _is_alive(loop):
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
            if not _is_alive(view):
                return None
            page = view.page() if _is_alive(view) else None
            if page is None or not _is_alive(page):
                return None
            page.runJavaScript(js, _got)
        except Exception as e:
            self._log(f"_capture_current_camera: dispatch failed ({e}).")
            return None

        # H6: deterministic abort if the view or page is torn down while
        # loop.exec() is pumping.  Without this, a user pressing Render
        # during the 2 s window would leave the callback scheduled on a
        # dying page, risking a "wrapped C/C++ object deleted" error
        # when Qt tries to deliver it.  Connecting destroyed → loop.quit
        # means teardown closes the loop cleanly.
        def _abort():
            holder["done"] = True
            if _is_alive(loop):
                loop.quit()
        try:
            view.destroyed.connect(_abort)
        except Exception:
            pass
        try:
            page.destroyed.connect(_abort)
        except Exception:
            pass

        # Watchdog: always fires, but only quits if the loop is still
        # alive (otherwise it's a harmless no-op).
        def _watchdog():
            if _is_alive(loop) and not holder["done"]:
                loop.quit()

        QTimer.singleShot(2000, _watchdog)
        try:
            loop.exec()
        finally:
            # Explicit teardown so a deferred callback into a dead loop
            # can't reach live Python state on the next tick.
            try:
                loop.deleteLater()
            except Exception:
                pass

        # View may have been destroyed while we were blocked in exec().
        if not _is_alive(view):
            return None
        raw = holder["raw"]
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as e:
            self._log(f"_capture_current_camera: JSON parse failed ({e}).")
            return None

    def _capture_png_via_plotly_toimage(
            self, width: int, height: int,
            scale: float) -> bytes | None:
        """Ask the live Plotly graph inside the WebEngine view to render
        itself to a PNG via ``Plotly.toImage()`` and return the decoded
        bytes.

        This guarantees parity with what the user actually sees — same
        camera, same sizing, same marker/line/halo rendering — which the
        static kaleido path can't match because it re-runs Plotly in a
        headless browser with different defaults.

        Returns ``None`` when:
          * WebEngine isn't available
          * the view/page is torn down mid-call
          * Plotly/the graph div can't be found on the page
          * the promise times out (8 s watchdog)
          * the returned data URL can't be decoded

        The call spins a nested ``QEventLoop`` and polls a
        ``window.__gv3d_png`` sentinel set by the resolved Promise.
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
        try:
            from PyQt6 import sip  # type: ignore
        except Exception:
            sip = None  # noqa: N806

        def _is_alive(obj) -> bool:
            if obj is None:
                return False
            if sip is not None:
                try:
                    return not sip.isdeleted(obj)
                except Exception:
                    return True
            return True

        loop = QEventLoop()
        holder: dict = {"raw": None, "done": False}

        def _got(raw):
            # ``null`` from the poll JS means "not ready yet" —
            # keep polling until we get a real payload or the
            # watchdog fires.
            if raw is None:
                return
            holder["raw"] = raw
            holder["done"] = True
            if _is_alive(loop):
                loop.quit()

        w_i = int(max(1, width))
        h_i = int(max(1, height))
        s_f = float(max(0.1, scale))
        kick_js = (
            "(function(){try{"
            "window.__gv3d_png=null;window.__gv3d_png_err=null;"
            "var els=document.getElementsByClassName("
            "'plotly-graph-div');"
            "if(!els||!els.length){"
            "window.__gv3d_png_err='no_gd';return 'no_gd';}"
            "var gd=els[0];"
            "if(!window.Plotly||!window.Plotly.toImage){"
            "window.__gv3d_png_err='no_plotly';return 'no_plotly';}"
            f"Plotly.toImage(gd,{{format:'png',width:{w_i},"
            f"height:{h_i},scale:{s_f}}})"
            ".then(function(url){window.__gv3d_png=url;})"
            ".catch(function(e){"
            "window.__gv3d_png_err=String(e&&e.message||e);});"
            "return 'started';"
            "}catch(e){window.__gv3d_png_err=String(e);"
            "return 'throw';}})();"
        )
        poll_js = (
            "(function(){try{"
            "if(window.__gv3d_png){return window.__gv3d_png;}"
            "if(window.__gv3d_png_err){"
            "return 'ERR:'+window.__gv3d_png_err;}"
            "return null;"
            "}catch(e){return 'ERR:'+String(e);}})();"
        )

        try:
            page = view.page() if _is_alive(view) else None
            if page is None or not _is_alive(page):
                return None
            page.runJavaScript(kick_js, lambda _r: None)
        except Exception as e:
            self._log(
                f"_capture_png_via_plotly_toimage: dispatch failed "
                f"({e}).")
            return None

        def _abort():
            holder["done"] = True
            if _is_alive(loop):
                loop.quit()

        try:
            view.destroyed.connect(_abort)
        except Exception:
            pass
        try:
            page.destroyed.connect(_abort)
        except Exception:
            pass

        def _poll():
            if holder["done"]:
                return
            if not _is_alive(view):
                _abort()
                return
            try:
                p = view.page()
                if p is None or not _is_alive(p):
                    _abort()
                    return
                p.runJavaScript(poll_js, _got)
            except Exception:
                _abort()

        # First poll after 400 ms so the kick promise has a beat to
        # resolve on simple figures; then every 300 ms.
        poll_timer = QTimer()
        poll_timer.setInterval(300)
        poll_timer.timeout.connect(_poll)
        poll_timer.start()
        QTimer.singleShot(400, _poll)

        def _watchdog():
            if _is_alive(loop) and not holder["done"]:
                holder["done"] = True
                loop.quit()

        QTimer.singleShot(8000, _watchdog)
        try:
            loop.exec()
        finally:
            try:
                poll_timer.stop()
            except Exception:
                pass
            try:
                loop.deleteLater()
            except Exception:
                pass

        if not _is_alive(view):
            return None
        raw = holder["raw"]
        if not raw or not isinstance(raw, str):
            return None
        if raw.startswith("ERR:"):
            self._log(
                f"_capture_png_via_plotly_toimage: JS error: "
                f"{raw[4:]}")
            return None
        if not raw.startswith("data:image/"):
            return None
        try:
            import base64
            b64 = raw.split(",", 1)[1]
            return base64.b64decode(b64)
        except Exception as e:
            self._log(
                f"_capture_png_via_plotly_toimage: decode failed "
                f"({e}).")
            return None

    def _on_export_png(self) -> None:
        if self._last_scene is None:
            return
        fig = self._last_figure
        dpi = max(50, int(self.spin_dpi.value()))
        base_width, base_height = 1400, 1000
        px_scale = max(1.0, dpi / 100.0)

        # Path A — WYSIWYG via Plotly.toImage() inside the live
        # WebEngine view.  This is the only way to get a PNG that
        # matches what's on screen (same camera, same marker sizes,
        # same depth cues) because the headless kaleido path can't
        # see runtime user-driven camera changes baked in via the
        # window.gv3d bootstrap.  We try it first and only fall
        # through to kaleido / matplotlib if it fails.
        png_bytes = None
        try:
            png_bytes = self._capture_png_via_plotly_toimage(
                base_width, base_height, px_scale)
        except Exception as e:
            self._log(f"PNG export (WebEngine): {e}")
            png_bytes = None

        if png_bytes:
            try:
                with open(self._last_png_path, "wb") as f:
                    f.write(png_bytes)
                self._log(
                    f"Exported PNG via WebEngine/Plotly.toImage: "
                    f"{self._last_png_path}")
                QMessageBox.information(
                    self, "PNG Exported",
                    f"Static 3D snapshot saved:\n"
                    f"{self._last_png_path}")
                return
            except Exception as e:
                self._log(
                    f"PNG export: WebEngine bytes captured but write "
                    f"failed ({e}); trying kaleido next.")

        if fig is not None:
            # Avoid copy.deepcopy(fig): for a figure that contains the
            # pixel-grid trace (~230k markers) the deepcopy walks every
            # marker x/y/z/color element and allocates a fresh Python
            # object — hundreds of MB and several seconds of work.
            # Instead, snapshot just the scene_camera layout value,
            # mutate the live figure in-place for the write_image call,
            # and restore the snapshot in a finally block so the on-screen
            # view is untouched.
            cam = self._capture_current_camera()
            prev_cam = None
            prev_cam_captured = False
            if cam:
                try:
                    # to_plotly_json() gives us a dict that round-trips
                    # cleanly back through update_layout.
                    scene = getattr(fig.layout, "scene", None)
                    cam_obj = getattr(scene, "camera", None) if scene else None
                    if cam_obj is not None:
                        prev_cam = cam_obj.to_plotly_json()
                        prev_cam_captured = True
                    fig.update_layout(scene_camera=cam)
                except Exception as e:
                    self._log(
                        f"PNG export: couldn't apply current camera ({e}).")
            try:
                pio.write_image(
                    fig, self._last_png_path,
                    format="png",
                    width=base_width, height=base_height,
                    scale=px_scale)
                self._log(f"Exported PNG via Plotly/kaleido: "
                          f"{self._last_png_path}")
                QMessageBox.information(
                    self, "PNG Exported",
                    f"Static 3D snapshot saved:\n{self._last_png_path}")
                return
            except Exception as e:
                self._log(f"Plotly PNG export failed "
                          f"({type(e).__name__}: {e}); "
                          f"falling back to matplotlib.")
            finally:
                if prev_cam_captured:
                    try:
                        fig.update_layout(scene_camera=prev_cam)
                    except Exception:
                        # Restore-best-effort: the on-screen figure is
                        # already drawn from the cached scene JSON, so a
                        # stale camera on the Python-side Figure object
                        # doesn't break anything visible.
                        pass

        try:
            render_matplotlib_galaxy(
                self._last_scene, self._last_png_path, dpi=dpi)
            self._log(f"Exported PNG (matplotlib fallback): "
                      f"{self._last_png_path}")
            QMessageBox.information(
                self, "PNG Exported",
                f"Static 3D snapshot saved (matplotlib fallback):\n"
                f"{self._last_png_path}")
        except Exception as e:
            self._log(f"PNG export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export PNG:\n{e}")

    def _on_export_csv(self) -> None:
        if self._last_scene is None:
            return
        try:
            import csv
            sc = self._last_scene
            with open(self._last_csv_path, "w",
                      encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["field", "value"])
                w.writerow(["object_name", sc["object_name"]])
                w.writerow(["object_type", sc.get("object_type", "")])
                w.writerow(["distance_ly",
                            f"{sc.get('dist_ly') or '':.1f}"
                            if sc.get('dist_ly') else ""])
                w.writerow(["distance_uncertainty_ly",
                            f"{sc.get('dist_err_ly', 0) or 0:.1f}"])
                w.writerow(["distance_source", sc.get("dist_source", "")])
                w.writerow(["distance_confidence",
                            sc.get("dist_confidence", "")])
                w.writerow(["image_center_ra_deg",
                            f"{sc['center_ra']:.6f}"])
                w.writerow(["image_center_dec_deg",
                            f"{sc['center_dec']:.6f}"])
                w.writerow(["galactic_l_deg", f"{sc['l_deg']:.4f}"])
                w.writerow(["galactic_b_deg", f"{sc['b_deg']:.4f}"])
                w.writerow(["fov_radius_deg",
                            f"{sc['fov_radius_deg']:.4f}"])
                w.writerow(["view_mode", sc["mode"].value])
                w.writerow(["viewing_direction", sc.get("arm_hint", "")])
                w.writerow([])
                w.writerow(["photo_corner", "x", "y", "z"])
                corners = sc.get("photo_corners") or []
                for i, c in enumerate(corners):
                    w.writerow([f"corner_{i}",
                                f"{c[0]:.4f}", f"{c[1]:.4f}",
                                f"{c[2]:.4f}"])
            self._log(f"Exported CSV: {self._last_csv_path}")
            QMessageBox.information(
                self, "CSV Exported",
                f"Scene metadata saved:\n{self._last_csv_path}")
        except Exception as e:
            self._log(f"CSV export failed: {e}")
            QMessageBox.warning(self, "Export Failed",
                                f"Could not export CSV:\n{e}")

    # ------------------------------------------------------------------
    # CAMERA PRESETS + AUTO-ROTATE (drives window.gv3d in the WebView)
    # ------------------------------------------------------------------
    def _fly_camera_to(self, preset_name: str) -> None:
        """Animate the 3D camera to a named preset via window.gv3d.

        No-ops silently when the WebEngine view isn't ready or when
        the bootstrap hasn't been injected yet (e.g. matplotlib
        fallback path).  The JS itself is defensive: if
        ``window.gv3d`` isn't defined the guard inside the snippet
        just returns.
        """
        # JSON-encode the preset name so embedding user-configurable
        # names in the future doesn't open an injection seam.
        safe = json.dumps(str(preset_name))
        js = (
            "try {"
            f"  if (window.gv3d && window.gv3d.flyTo) {{ window.gv3d.flyTo({safe}); }}"
            "} catch (e) { console.warn('gv3d.flyTo failed', e); }"
        )
        try:
            self.preview_widget.run_js(js)
        except Exception as e:
            self._log(f"Camera preset '{preset_name}' failed: {e}")

    def _toggle_auto_rotate(self, on: bool) -> None:
        """Toggle the in-browser auto-rotation animation."""
        flag = "true" if on else "false"
        js = (
            "try {"
            f"  if (window.gv3d && window.gv3d.autoRotate) {{ window.gv3d.autoRotate({flag}); }}"
            "} catch (e) { console.warn('gv3d.autoRotate failed', e); }"
        )
        try:
            self.preview_widget.run_js(js)
        except Exception as e:
            self._log(f"Auto-rotate toggle failed: {e}")

    def _on_open_folder(self) -> None:
        path = (self._last_html_path or self._last_png_path
                or self._last_csv_path)
        if path:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(path)))

    def _on_open_html(self) -> None:
        if self._last_html_path and os.path.isfile(self._last_html_path):
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(self._last_html_path))

    # ------------------------------------------------------------------
    # WEBENGINE REPAIR
    # ------------------------------------------------------------------
    def _show_webengine_repair_dialog(self) -> None:
        dlg = WebEngineRepairDialog(self)
        dlg.exec()
        if dlg.repaired:
            self._log("PyQt6-WebEngine repaired successfully.")
            self.preview_widget.refresh_webengine_state()
        elif WEBENGINE_ERROR:
            self._log(f"WebEngine still unavailable: {WEBENGINE_ERROR}")

    # ------------------------------------------------------------------
    # COFFEE DIALOG
    # ------------------------------------------------------------------
    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"
        dlg = QDialog(self)
        dlg.setWindowTitle("\u2615 Support Svenesis GalacticView 3D")
        dlg.setMinimumSize(520, 480)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}"
            "QPushButton{font-weight:bold;padding:8px;border-radius:6px}")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header_msg = QLabel(
            "<div style='text-align:center; font-size:12pt; line-height:1.6;'>"
            "<span style='font-size:48pt;'>\u2615</span><br>"
            "<span style='font-size:18pt; font-weight:bold; color:#FFDD00;'>"
            "Buy me a Coffee</span><br><br>"
            "<b style='color:#e0e0e0;'>Enjoying Svenesis GalacticView 3D?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If GalacticView 3D helped you see your image's place in the Milky Way \u2014 "
            "consider buying me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>\u2615 Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br>"
            "</div>")
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)

        layout.addSpacing(8)

        btn_open = QPushButton("\u2615  Buy me a Coffee  \u2615")
        btn_open.setStyleSheet(
            "QPushButton{background-color:#FFDD00;color:#000;"
            "font-size:14pt;font-weight:bold;"
            "padding:12px 24px;border-radius:8px;"
            "border:2px solid #ccb100;}"
            "QPushButton:hover{background-color:#ffe740;border-color:#ddcc00;}")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(BMC_URL)))
        layout.addWidget(btn_open)

        layout.addSpacing(4)
        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        footer = QLabel(
            f"<div style='text-align:center; line-height:1.8;'>"
            f"<a style='color:#88aaff; font-size:12pt;' href='{BMC_URL}'>"
            f"{BMC_URL}</a><br>"
            f"<span style='font-size:13pt; color:#999;'>"
            f"Thank you for supporting open-source astrophotography tools!<br>"
            f"Clear skies \u2728</span></div>")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        footer.setOpenExternalLinks(True)
        layout.addWidget(footer)

        dlg.exec()

    # ------------------------------------------------------------------
    # HELP DIALOG
    # ------------------------------------------------------------------
    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Svenesis GalacticView 3D \u2014 Help")
        dlg.setMinimumSize(800, 600)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()

        tab1 = QTextEdit()
        tab1.setReadOnly(True)
        tab1.setHtml(
            "<h2 style='color:#88aaff;'>Getting Started</h2>"
            "<p><b>What does GalacticView 3D do?</b></p>"
            "<p>This script shows <i>where</i> your astrophoto is pointing "
            "in the universe.  It renders the Milky Way (or the cosmic "
            "neighbourhood) as an interactive 3D model and places your "
            "plate-solved image as a rectangle along the exact line of "
            "sight that produced it.</p>"
            "<blockquote style='color:#88aaff;'><i>Your photo is not just "
            "anywhere.  It is a window into one specific direction of "
            "the universe \u2014 and now you can see where.</i></blockquote>"
            "<hr>"
            "<p><b>Requirements:</b></p>"
            "<ul>"
            "<li><b>Plate-solved image</b> \u2014 the FITS header must "
            "carry a WCS solution.  In Siril: "
            "<i>Tools \u2192 Astrometry \u2192 Image Plate Solver</i>.</li>"
            "<li><b>Internet</b> \u2014 SIMBAD provides the target's "
            "type, distance, and the cone-search candidate list.  "
            "Results are cached locally so re-renders are offline-fast.</li>"
            "<li><b>PyQt6-WebEngine + plotly</b> for the interactive "
            "in-window 3D view.  Without them the script falls back to a "
            "static matplotlib PNG.</li>"
            "</ul>"
            "<hr>"
            "<p><b>Quick Start:</b></p>"
            "<ol>"
            "<li>Load a plate-solved image in Siril.</li>"
            "<li>Run this script.</li>"
            "<li>Click <b>Render 3D Map</b> (or press <b>F5</b>).</li>"
            "<li>The Target Picker opens \u2014 confirm the auto-pick or "
            "choose a different SIMBAD candidate from the cone search.</li>"
            "<li>Drag the scene to orbit, mouse-wheel to zoom, hover any "
            "marker for hover-rich context.</li>"
            "<li>Export as HTML / PNG / CSV when ready.</li>"
            "</ol>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Camera Controls</h3>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='width:160px'><b>Trackball widget</b></td>"
            "<td>Drag (left of the button row) for two-axis orbit, "
            "diagonals supported.  Mouse-wheel over it zooms.</td></tr>"
            "<tr><td><b>+ / \u2212 / \u27f2</b></td>"
            "<td>Zoom in / out / reset.  Zoom-in stops at the near-clip "
            "plane (logged as <i>capped at near-clip</i>) so the photo "
            "and references stay in frame.</td></tr>"
            "<tr><td><b>Earth POV</b></td>"
            "<td>Fly to Earth's position, looking along the line of "
            "sight to the target.  The viewing ray pulses on arrival.</td></tr>"
            "<tr><td><b>Top / Side / Iso</b></td>"
            "<td>Orthogonal preset views.  Iso resets to the default "
            "3/4-perspective.</td></tr>"
            "<tr><td><b>Spin</b></td>"
            "<td>Toggle slow auto-rotation.  Also auto-engages after "
            "10 s of inactivity; any input cancels it.</td></tr>"
            "<tr><td><b>R / Home / Esc</b></td>"
            "<td>Universal &ldquo;get me home&rdquo; \u2014 reset the "
            "camera and any zoomed-in axis ranges.</td></tr>"
            "<tr><td><b>Legend double-click</b></td>"
            "<td>Double-click a spiral-arm legend entry "
            "(<i>Norma Arm</i>, <i>Scutum-Centaurus</i>\u2026) to fly the "
            "camera to that arm.</td></tr>"
            "</table>")
        tabs.addTab(tab1, "Getting Started")

        tab2 = QTextEdit()
        tab2.setReadOnly(True)
        tab2.setHtml(
            "<h2 style='color:#88aaff;'>Galactic Mode</h2>"
            "<p>Activated for in-Milky-Way targets "
            "(distance &lt; 150,000 ly, or SIMBAD type matches an "
            "in-galaxy class — HII region, nebula, cluster, "
            "star…).  <b>Linear scale</b>: 1 scene unit = 1,000 ly.  "
            "Earth sits at the scene origin; the Galactic Center "
            "(Sgr A*) is offset to +x at 26,000 ly.</p>"
            "<p><i>Auto-mode is chosen from the object type and "
            "distance: galaxies, QSOs and anything beyond 150,000 "
            "ly map to <b>Cosmic Mode</b> (next tab); HII regions, "
            "nebulae, clusters, stars map to Galactic.  Override at "
            "any time via the radio buttons in the top-left "
            "panel.</i></p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Always-on layers</h3>"
            "<ul>"
            "<li><b>5 spiral arms</b> (Hou &amp; Han 2014): Norma, "
            "Scutum-Centaurus, Sagittarius, Orion (Earth's arm "
            "— thicker), Perseus.  Auto-fade as the camera "
            "approaches origin so the arms don't clutter sub-kly "
            "scenes.</li>"
            "<li><b>Disk stars + bulge</b> — seeded so re-renders "
            "match.  Same LOD fade as the arms.</li>"
            "<li><b>Earth glyph</b> — target reticle (open ring + "
            "centre dot) at origin with a hover-rich tooltip "
            "(distance to GC, galactic coords, line-of-sight arm).</li>"
            "<li><b>Earth orbital arrow</b> — small cyan arrow "
            "showing our ~220 km/s motion around the Galactic "
            "Center (one full galactic year ≈ 225 Myr).</li>"
            "<li><b>Sgr A*</b> at the Galactic Center, marked with a "
            "warm diamond.</li>"
            "<li><b>Galactic-plane mesh</b> — translucent radial "
            "gradient.  Auto-suppressed when arms are visible "
            "(the arms already imply the disk).</li>"
            "<li><b>Distance rings</b> in two sets, both rendered as "
            "three orthogonal great circles per radius "
            "(spherical-shell wireframe):"
            "<ul>"
            "<li>Cool blue, GC-centred at 10 / 20 / 30 / 40 kly "
            "(Milky-Way structural reference).</li>"
            "<li>Warm amber, Earth-centred at 1 / 5 / 10 / 25 kly "
            "(&ldquo;how far from us&rdquo;).</li>"
            "</ul></li>"
            "<li><b>Constellation stick figure</b> containing the "
            "target, anchored at the target's distance shell so the "
            "photo rectangle sits inside the constellation outline.</li>"
            "<li><b>Local Bubble</b> (translucent ~400-ly sphere) for "
            "very nearby targets (≤ 2 kly).  The supernova-"
            "carved cavity around the Solar System.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Galactic landmarks "
            "(legend toggle)</h3>"
            "<p>Curated catalog of ~20 famous in-galaxy objects "
            "(Pleiades, Hyades, Beehive, Orion Nebula, M42, M13, "
            "Veil, Lagoon, Trifid, Eagle, Carina, Helix, Omega "
            "Centauri, 47 Tucanae…) grouped by kind into 5 "
            "toggleable legend entries: Open clusters, Globular "
            "clusters, Nebulae, SNRs, Planetary nebulae.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Smart features</h3>"
            "<ul>"
            "<li><b>Arm membership</b> on the chosen target — if "
            "the target is in-disk, its mid-ray label appends "
            "<i>in &lt;Sagittarius&nbsp;Arm&gt;</i> (etc).  Inferred "
            "from the closest arm centerline.</li>"
            "<li><b>Adaptive scene box</b> — sub-kly targets get "
            "a ±500-ly tight box; 1–10 kly get ±4 kly; "
            "≥ 10 kly use the full ±50-kly disk.  The "
            "initial camera pre-frames so the photo is visible "
            "from the first paint without requiring a manual "
            "zoom-in.</li>"
            "<li><b>Click an arm in the legend</b> (double-click) to "
            "fly the camera to that arm — turns the legend into "
            "a navigation menu.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Distance Resolution</h3>"
            "<ol>"
            f"<li>Local JSON cache ({CACHE_TTL_DAYS}-day TTL)</li>"
            "<li>SIMBAD <i>mesDistance</i> table</li>"
            "<li>Redshift \u2192 cosmological distance via "
            "<code>astropy.cosmology.Planck18</code></li>"
            "<li>Parallax (\u03c0) where available</li>"
            "<li>Type-based median fallback (clearly marked as "
            "estimate)</li>"
            "</ol>"
            "<p>Objects using the type-median fallback are clearly "
            "labelled in the Info tab and CSV export.</p>")
        tabs.addTab(tab2, "Galactic Mode")

        # ---------- Tab 3: Cosmic Mode ----------
        tab3 = QTextEdit()
        tab3.setReadOnly(True)
        tab3.setHtml(
            "<h2 style='color:#88aaff;'>Cosmic Mode</h2>"
            "<p>Activated for extragalactic targets "
            "(distance \u2265 150,000 ly, or SIMBAD type is Galaxy / "
            "QSO / AGN / Seyfert\u2026).  Earth sits at the origin.  "
            "Distances use a <b>piecewise scale</b>:</p>"
            "<ul>"
            "<li>Linear inside 1 Mly: 1 scene unit = 100,000 ly.</li>"
            "<li>Logarithmic beyond 1 Mly: 1 scene-unit step = "
            "1 decade in light-years.</li>"
            "</ul>"
            "<p>The transition is marked by a faint orange "
            "long-dashdot ring at <b>1 Mly</b> (the "
            "<i>Scale boundary</i> trace).</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Distance metric toggle</h3>"
            "<p>The Scene Elements panel offers three radio buttons "
            "for the distance metric used in cosmic mode:</p>"
            "<ul>"
            "<li><b>Light-travel</b> (default) \u2014 c \u00d7 lookback "
            "time.  Matches SIMBAD's redshift\u2192distance "
            "convention.</li>"
            "<li><b>Comoving</b> \u2014 the proper distance to the "
            "object <i>now</i>, accounting for cosmic expansion "
            "since the light left.</li>"
            "<li><b>Angular-diameter</b> \u2014 comoving / (1+z); the "
            "metric that determines apparent angular size.</li>"
            "</ul>"
            "<p>The HUD label at bottom-left always shows which "
            "metric is active.  Cosmology is "
            "<code>astropy.cosmology.Planck18</code> "
            "(H<sub>0</sub> \u2248 67.4 km/s/Mpc, "
            "\u03a9<sub>m</sub> \u2248 0.315, \u03a9<sub>\u039b</sub> \u2248 0.685).</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Always-on layers</h3>"
            "<ul>"
            "<li><b>8 distance rings</b> centred on Earth at 1, 5, "
            "10, 50, 100, 500 Mly and 1, 5 Gly.  Three orthogonal "
            "great circles per radius (spherical-shell wireframe).  "
            "Each label includes the equivalent redshift "
            "(<i>z \u2248 0.07</i> at 1 Gly, etc.).</li>"
            "<li><b>1 Mly scale boundary</b> \u2014 marks the "
            "linear/log transition.</li>"
            "<li><b>10 neighbour galaxies</b> with hover-rich "
            "descriptions (M31, M33, LMC, SMC, M81, M82, M51, "
            "Centaurus A, Virgo Cluster, NGC 253).  Each shows "
            "distance, redshift, lookback time, type, group "
            "membership, and a one-sentence cultural / scientific "
            "note.</li>"
            "<li><b>CMB last-scattering surface</b> at 13.8 Gly "
            "(z \u2248 1100).  Wireframe globe \u2014 1 bright equatorial "
            "great circle + 4 latitude rings + 8 meridian arcs.  "
            "Marks the practical edge of the observable "
            "universe.</li>"
            "<li><b>Local Group sphere</b> (~3 Mly) \u2014 only for "
            "sub-5-Mly targets, framing your photo as &ldquo;in "
            "our local group&rdquo;.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Cosmic landmarks &amp; "
            "clusters (legend toggle)</h3>"
            "<ul>"
            "<li><b>Galaxy clusters</b> (translucent halos): Virgo, "
            "Fornax, Centaurus, Coma, Perseus, Hercules, Shapley "
            "Supercluster.  Each at its real (l, b, distance), with "
            "extent matching its core radius and a one-sentence note "
            "(&ldquo;where Zwicky inferred dark matter&rdquo;, "
            "&ldquo;Great Attractor flow&rdquo;\u2026).</li>"
            "<li><b>Cosmic landmarks</b> (~20 famous objects): "
            "M31, M33, M51, M81/82, M83, M101, M104 Sombrero, "
            "NGC 253, Cartwheel, Hoag's Object, Stephan's Quintet, "
            "Markarian's Chain, 3C 273 (brightest quasar), HUDF "
            "direction\u2026  Grouped by kind (spiral / dwarf / "
            "starburst / AGN / peculiar / group / quasar / "
            "pointer) into 8 toggleable legend entries.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Stylized CMB texture (opt-in)</h3>"
            "<p>The <b>CMB texture (stylized)</b> legend entry, "
            "default-off, paints a translucent procedural Gaussian "
            "noise pattern on the CMB sphere (red-blue colorscale "
            "mimicking the look of real Planck/WMAP maps).  It is "
            "<i>not</i> real CMB data \u2014 just an evocative visual.  "
            "Toggling it on triggers the scene's autorange to expand "
            "to the CMB radius, so other content gets visually "
            "smaller.</p>")
        tabs.addTab(tab3, "Cosmic Mode")

        # ---------- Tab 4: Exports, performance, troubleshooting ----------
        _webengine_status = (
            "yes \u2014 interactive view embedded in this window"
            if HAS_WEBENGINE
            else "no \u2014 falling back to static PNG + browser")
        _plotly_status = "yes" if HAS_PLOTLY else "no \u2014 matplotlib only"
        tab4 = QTextEdit()
        tab4.setReadOnly(True)
        tab4.setHtml(
            "<h2 style='color:#88aaff;'>Exports</h2>"
            "<table cellpadding='4' style='width:100%'>"
            "<tr><td style='width:80px'><b>HTML</b></td>"
            "<td>Standalone, fully interactive Plotly scene.  "
            "Self-contained (Plotly bundled inline).  Works "
            "offline.  Open in any modern browser.</td></tr>"
            "<tr><td><b>PNG</b></td>"
            "<td>Static snapshot via <code>kaleido</code>; falls "
            "back to a matplotlib renderer if kaleido isn't "
            "available.</td></tr>"
            "<tr><td><b>CSV</b></td>"
            "<td>Object name, type, distance, galactic coordinates, "
            "viewing direction, and the four photo-rectangle "
            "corners in 3D scene units.</td></tr>"
            "</table>"
            "<p>Two convenience buttons in the right panel:</p>"
            "<ul>"
            "<li><b>Open Output Folder</b> \u2014 reveal the export "
            "folder in your file manager.</li>"
            "<li><b>Open Exported HTML</b> \u2014 open the most-recent "
            "HTML export in your default browser.</li>"
            "</ul>"
            "<hr>"
            "<h2 style='color:#88aaff;'>Tips &amp; Troubleshooting</h2>"
            "<ul>"
            "<li><b>Scene feels sluggish?</b>  Lower the photo "
            "resolution (Scene Elements \u2192 Photo resolution) "
            "from the default \u2014 the textured photo mesh is the "
            "biggest single GPU cost.  240 px renders ~4\u00d7 faster "
            "than 480 px with mild quality loss.</li>"
            "<li><b>Hide overlays you don't need.</b>  The legend "
            "is grouped (<i>Milky Way</i> / <i>References</i> / "
            "<i>Target</i> / <i>Background</i> / <i>Galaxy "
            "clusters</i> / <i>Cosmic landmarks</i>).  Click any "
            "entry to toggle, double-click to solo (or \u2014 for "
            "spiral-arm entries \u2014 to fly to that arm).</li>"
            "<li><b>Lost the scene?</b>  Press <b>R</b>, "
            "<b>Home</b>, or <b>Escape</b>.  Or use the <b>\u27f2</b> "
            "trackball button.  Auto-rotate also kicks in after "
            "10 s of inactivity as an ambient-demo cue.</li>"
            "<li><b>SIMBAD slow / timing out?</b>  CDS occasionally "
            "has outages.  The script logs <i>SIMBAD tile "
            "timeout</i> and proceeds without that tile's "
            "candidates.  Re-renders of cached targets stay fast "
            "offline.  Lower <code>SIMBAD_TILE_TIMEOUT_S</code> in "
            "the source if you want fail-fast behaviour during "
            "outages.</li>"
            "<li><b>Photo rectangle invisible.</b>  Astrophoto FOVs "
            "(typically &lt; 1\u00b0) project to a sub-pixel rectangle "
            "at galactic / cosmic scale; the script auto-enlarges "
            "the rectangle around its centroid so it stays "
            "visible.  Orientation and aspect are preserved.</li>"
            "</ul>"
            "<hr>"
            "<h2 style='color:#88aaff;'>Rendering Backend</h2>"
            f"<p><b>WebEngine available:</b> {_webengine_status}.<br>"
            f"<b>Plotly available:</b> {_plotly_status}.</p>"
            "<p>For the interactive in-window scene, "
            "<code>PyQt6-WebEngine</code> and <code>plotly</code> "
            "must be installed into Siril's Python environment.  "
            "<code>astropy \u2265 5</code> is required for the Planck18 "
            "cosmology used by the redshift / lookback / metric "
            "conversion code.</p>")
        tabs.addTab(tab4, "Exports &amp; Tips")

        layout.addWidget(tabs)
        btn = QPushButton("Close")
        _nofocus(btn)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        win = GalacticView3DWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis GalacticView 3D v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
            pass
        return app.exec()
    except NoImageError:
        QMessageBox.warning(
            None, "No Image",
            "No image is currently loaded in Siril. Please load an image first.")
        return 1
    except Exception as e:
        QMessageBox.critical(
            None, "Svenesis GalacticView 3D Error",
            f"{e}\n\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
