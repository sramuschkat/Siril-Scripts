"""
Svenesis Annotate Image
Script Version: 1.0.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script reads the current plate-solved image from Siril, identifies catalog objects
(Messier, NGC, IC, named stars) within the field of view, and renders configurable
annotations (markers, labels, coordinate grid, info box, compass) onto an exportable
PNG/TIFF image. Inspired by PixInsight's AnnotateImage script.

Features:
- Requires a plate-solved image (WCS solution in FITS header)
- Embedded Messier catalog (110 objects) for zero-dependency annotation
- NGC/IC bright subset catalog (~600 objects)
- Named stars catalog (~50 brightest)
- Sharpless HII regions catalog (~50 brightest)
- Configurable colors per object type (Galaxy, Nebula, PN, OC, GC, SNR, etc.)
- Object size rendered as scaled ellipses (from catalog angular size)
- Magnitude limit filter
- Label collision avoidance (greedy placement algorithm)
- Optional coordinate grid overlay with RA/DEC labels
- Optional info box (center coords, FOV, pixel scale, rotation)
- Optional compass rose (N/E arrows)
- Configurable font size, marker size, DPI
- Output as PNG, TIFF, or JPEG
- Auto-stretch preview from Siril or raw linear data
- Dark-themed PyQt6 GUI matching Gradient Analyzer style
- Persistent settings via QSettings
- Progress feedback during annotation

Run from Siril via Processing -> Scripts. Place AnnotateImage.py inside a folder named
Utility in one of Siril's Script Storage Directories (Preferences -> Scripts).

(c) 2025
SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Svenesis Annotate Image
# Script Version: 1.0.0
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: processing
# Script Description: Renders catalog annotations (Messier, NGC, IC,
#   named stars) onto a plate-solved image and exports it as PNG/TIFF.
#   Similar to PixInsight's AnnotateImage script. Requires a plate-solved image.
# Script Author: Sven Ramuschkat

CHANGELOG:
1.0.0 - Initial release
      - Plate-solved image annotation with catalog objects
      - Embedded Messier, NGC bright, named stars, Sharpless catalogs
      - Color-coded markers and labels by object type
      - Coordinate grid overlay with RA/DEC labels
      - Info box with center, FOV, scale, rotation
      - Compass rose overlay (N/E arrows)
      - Label collision avoidance
      - Magnitude limit filtering
      - PNG/TIFF/JPEG export with configurable DPI
      - Dark-themed PyQt6 GUI
      - Persistent settings
"""
from __future__ import annotations

import sys
import os
import traceback
import math
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

s.ensure_installed("numpy", "PyQt6", "matplotlib", "astropy")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QSizePolicy, QDialog, QTextEdit, QTabWidget, QScrollArea,
    QProgressBar, QComboBox, QRadioButton, QButtonGroup,
    QLineEdit, QFileDialog, QGridLayout,
)
from PyQt6.QtCore import Qt, QSettings, QUrl
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QLinearGradient,
    QShortcut, QKeySequence, QDesktopServices,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Circle, FancyArrowPatch
import matplotlib.patheffects as pe
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from astropy.wcs import WCS
from astropy.io import fits as astropy_fits

VERSION = "1.0.0"

# Settings keys
SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "AnnotateImage"

# Layout constants
LEFT_PANEL_WIDTH = 360


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
QPushButton#AnnotateButton{background-color:#335533;color:#aaffaa;border:1px solid #448844}
QPushButton#AnnotateButton:hover{background-color:#446644}

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
# COLOR SCHEME PER OBJECT TYPE
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


# ------------------------------------------------------------------------------
# EMBEDDED CATALOGS
# ------------------------------------------------------------------------------

# All catalogs: (name, ra_deg, dec_deg, type, mag, size_arcmin, common_name)
# Coordinates: J2000 epoch. Magnitudes: integrated visual magnitude.
# Sizes: major axis angular diameter in arcminutes.
# Sources: SEDS Messier database, OpenNGC, IAU star names, Sharpless 1959,
#          Barnard 1927, Caldwell list (P. Moore), IC catalog.

# Messier catalog — all 110 objects, complete with common names
MESSIER_CATALOG = [
    ("M1", 83.6331, 22.0145, "SNR", 8.4, 6.0, "Crab Nebula"),
    ("M2", 323.3626, -0.8233, "GC", 6.5, 16.0, ""),
    ("M3", 205.5484, 28.3773, "GC", 6.2, 18.0, ""),
    ("M4", 245.8968, -26.5258, "GC", 5.6, 36.0, "Cat's Eye Cluster"),
    ("M5", 229.6384, 2.0811, "GC", 5.7, 23.0, "Rose Cluster"),
    ("M6", 265.0834, -32.2536, "OC", 4.2, 33.0, "Butterfly Cluster"),
    ("M7", 268.4667, -34.7928, "OC", 3.3, 80.0, "Ptolemy Cluster"),
    ("M8", 270.9042, -24.3833, "Neb", 6.0, 90.0, "Lagoon Nebula"),
    ("M9", 259.7980, -18.5161, "GC", 7.7, 12.0, ""),
    ("M10", 254.2877, -4.1003, "GC", 6.6, 20.0, ""),
    ("M11", 282.7667, -6.2667, "OC", 6.3, 14.0, "Wild Duck Cluster"),
    ("M12", 251.8093, -1.9483, "GC", 6.7, 16.0, "Gumball Globular"),
    ("M13", 250.4218, 36.4613, "GC", 5.8, 20.0, "Great Hercules Cluster"),
    ("M14", 264.4004, -3.2458, "GC", 7.6, 11.0, ""),
    ("M15", 322.4930, 12.1670, "GC", 6.2, 18.0, "Great Pegasus Cluster"),
    ("M16", 274.7000, -13.7833, "Neb", 6.0, 7.0, "Eagle Nebula"),
    ("M17", 275.1917, -16.1708, "Neb", 6.0, 11.0, "Omega Nebula"),
    ("M18", 275.2375, -17.1278, "OC", 7.5, 9.0, ""),
    ("M19", 255.6571, -26.2681, "GC", 6.8, 17.0, ""),
    ("M20", 270.6225, -23.0300, "Neb", 6.3, 28.0, "Trifid Nebula"),
    ("M21", 270.9708, -22.4917, "OC", 6.5, 13.0, ""),
    ("M22", 279.0998, -23.9047, "GC", 5.1, 32.0, "Sagittarius Cluster"),
    ("M23", 269.2667, -19.0167, "OC", 6.9, 27.0, ""),
    ("M24", 274.5375, -18.5167, "OC", 4.6, 90.0, "Sagittarius Star Cloud"),
    ("M25", 277.9042, -19.1167, "OC", 6.5, 40.0, ""),
    ("M26", 281.3208, -9.3833, "OC", 8.0, 15.0, ""),
    ("M27", 299.9015, 22.7211, "PN", 7.5, 8.0, "Dumbbell Nebula"),
    ("M28", 276.1364, -24.8700, "GC", 6.8, 11.0, ""),
    ("M29", 305.9708, 38.5083, "OC", 7.1, 7.0, "Cooling Tower"),
    ("M30", 325.0922, -23.1797, "GC", 7.2, 12.0, ""),
    ("M31", 10.6847, 41.2687, "Gal", 3.4, 178.0, "Andromeda Galaxy"),
    ("M32", 10.6743, 40.8652, "Gal", 8.1, 8.7, ""),
    ("M33", 23.4621, 30.6602, "Gal", 5.7, 73.0, "Triangulum Galaxy"),
    ("M34", 40.5125, 42.7833, "OC", 5.5, 35.0, "Spiral Cluster"),
    ("M35", 92.2250, 24.3500, "OC", 5.3, 28.0, ""),
    ("M36", 84.0833, 34.1333, "OC", 6.3, 12.0, "Pinwheel Cluster"),
    ("M37", 88.0708, 32.5500, "OC", 6.2, 24.0, "January Salt-and-Pepper"),
    ("M38", 82.1667, 35.8333, "OC", 7.4, 21.0, "Starfish Cluster"),
    ("M39", 323.0625, 48.4333, "OC", 4.6, 32.0, ""),
    ("M40", 185.5500, 58.0833, "Star", 8.4, 0.8, "Winnecke 4"),
    ("M41", 101.5042, -20.7500, "OC", 4.5, 38.0, "Little Beehive"),
    ("M42", 83.8221, -5.3911, "Neb", 4.0, 85.0, "Orion Nebula"),
    ("M43", 83.8917, -5.2667, "Neb", 9.0, 20.0, "De Mairan's Nebula"),
    ("M44", 130.0250, 19.6833, "OC", 3.7, 95.0, "Beehive Cluster"),
    ("M45", 56.6010, 24.1153, "OC", 1.6, 110.0, "Pleiades"),
    ("M46", 115.4417, -14.8167, "OC", 6.1, 27.0, ""),
    ("M47", 114.1500, -14.4833, "OC", 5.2, 30.0, ""),
    ("M48", 123.4167, -5.8000, "OC", 5.5, 54.0, ""),
    ("M49", 187.4449, 8.0004, "Gal", 8.4, 10.2, ""),
    ("M50", 105.6833, -8.3667, "OC", 5.9, 16.0, "Heart-Shaped Cluster"),
    ("M51", 202.4696, 47.1952, "Gal", 8.4, 11.2, "Whirlpool Galaxy"),
    ("M52", 351.2042, 61.5833, "OC", 7.3, 13.0, ""),
    ("M53", 198.2303, 18.1681, "GC", 7.6, 13.0, ""),
    ("M54", 283.7636, -30.4783, "GC", 7.6, 12.0, ""),
    ("M55", 294.9988, -30.9647, "GC", 6.3, 19.0, "Summer Rose Star"),
    ("M56", 289.1483, 30.1842, "GC", 8.3, 9.0, ""),
    ("M57", 283.3963, 33.0289, "PN", 8.8, 1.4, "Ring Nebula"),
    ("M58", 189.4316, 11.8181, "Gal", 9.7, 5.9, ""),
    ("M59", 190.5092, 11.6472, "Gal", 9.6, 5.4, ""),
    ("M60", 190.9167, 11.5528, "Gal", 8.8, 7.6, ""),
    ("M61", 185.4790, 4.4736, "Gal", 9.7, 6.5, "Swelling Spiral"),
    ("M62", 255.3032, -30.1136, "GC", 6.5, 15.0, ""),
    ("M63", 198.9553, 42.0293, "Gal", 8.6, 12.6, "Sunflower Galaxy"),
    ("M64", 194.1826, 21.6828, "Gal", 8.5, 10.7, "Black Eye Galaxy"),
    ("M65", 169.7330, 13.0922, "Gal", 9.3, 9.8, "Leo Triplet"),
    ("M66", 170.0626, 12.9914, "Gal", 8.9, 9.1, "Leo Triplet"),
    ("M67", 132.8500, 11.8167, "OC", 6.1, 30.0, "King Cobra Cluster"),
    ("M68", 189.8667, -26.7447, "GC", 7.8, 11.0, ""),
    ("M69", 277.8463, -32.3481, "GC", 7.6, 10.0, ""),
    ("M70", 280.8029, -32.2911, "GC", 7.9, 8.0, ""),
    ("M71", 298.4438, 18.7792, "GC", 8.2, 7.2, ""),
    ("M72", 313.3654, -12.5372, "GC", 9.3, 6.6, ""),
    ("M73", 314.7500, -12.6333, "Ast", 9.0, 2.8, ""),
    ("M74", 24.1740, 15.7836, "Gal", 9.4, 10.5, "Phantom Galaxy"),
    ("M75", 301.5201, -21.9211, "GC", 8.5, 7.4, ""),
    ("M76", 25.5821, 51.5753, "PN", 10.1, 2.7, "Little Dumbbell Nebula"),
    ("M77", 40.6696, -0.0133, "Gal", 8.9, 7.1, "Cetus A"),
    ("M78", 86.6500, 0.0833, "RN", 8.3, 8.0, "Casper the Friendly Ghost"),
    ("M79", 81.0462, -24.5247, "GC", 7.7, 9.6, ""),
    ("M80", 244.2601, -22.9758, "GC", 7.3, 10.0, ""),
    ("M81", 148.8882, 69.0653, "Gal", 6.9, 26.9, "Bode's Galaxy"),
    ("M82", 148.9685, 69.6797, "Gal", 8.4, 11.2, "Cigar Galaxy"),
    ("M83", 204.2538, -29.8654, "Gal", 7.6, 12.9, "Southern Pinwheel Galaxy"),
    ("M84", 186.2655, 12.8870, "Gal", 9.1, 6.5, ""),
    ("M85", 186.3504, 18.1912, "Gal", 9.1, 7.1, ""),
    ("M86", 186.5491, 12.9464, "Gal", 8.9, 8.9, ""),
    ("M87", 187.7059, 12.3911, "Gal", 8.6, 8.3, "Virgo A"),
    ("M88", 188.9960, 14.4204, "Gal", 9.6, 6.9, ""),
    ("M89", 188.9159, 12.5563, "Gal", 9.8, 5.1, ""),
    ("M90", 189.2093, 13.1631, "Gal", 9.5, 9.5, ""),
    ("M91", 188.8601, 14.4968, "Gal", 10.2, 5.4, ""),
    ("M92", 259.2808, 43.1364, "GC", 6.4, 14.0, ""),
    ("M93", 116.1375, -23.8667, "OC", 6.0, 22.0, ""),
    ("M94", 192.7215, 41.1203, "Gal", 8.2, 14.4, "Croc's Eye Galaxy"),
    ("M95", 160.9902, 11.7037, "Gal", 9.7, 7.4, ""),
    ("M96", 161.6904, 11.8197, "Gal", 9.3, 7.6, ""),
    ("M97", 168.6987, 55.0192, "PN", 9.9, 3.4, "Owl Nebula"),
    ("M98", 183.4512, 14.9003, "Gal", 10.1, 9.8, ""),
    ("M99", 184.7063, 14.4165, "Gal", 9.9, 5.4, "Coma Pinwheel"),
    ("M100", 185.7289, 15.8222, "Gal", 9.3, 7.4, "Mirror Galaxy"),
    ("M101", 210.8024, 54.3492, "Gal", 7.9, 28.8, "Pinwheel Galaxy"),
    ("M102", 226.6232, 55.7634, "Gal", 9.9, 6.5, "Spindle Galaxy"),
    ("M103", 23.3417, 60.6583, "OC", 7.4, 6.0, ""),
    ("M104", 189.9976, -11.6230, "Gal", 8.0, 8.7, "Sombrero Galaxy"),
    ("M105", 161.9565, 12.5816, "Gal", 9.3, 5.4, ""),
    ("M106", 184.7397, 47.3039, "Gal", 8.4, 18.6, ""),
    ("M107", 248.1333, -13.0531, "GC", 7.9, 13.0, ""),
    ("M108", 167.8791, 55.6741, "Gal", 10.0, 8.7, "Surfboard Galaxy"),
    ("M109", 179.3999, 53.3746, "Gal", 9.8, 7.6, "Vacuum Cleaner Galaxy"),
    ("M110", 10.0918, 41.6853, "Gal", 8.5, 21.9, ""),
]

# NGC bright subset — popular astrophotography targets not in Messier
# Only objects NOT duplicated by Messier are included (Messier takes priority).
NGC_BRIGHT_CATALOG = [
    ("NGC 55", 3.7231, -39.1967, "Gal", 7.9, 32.0, ""),
    ("NGC 104", 6.0236, -72.0814, "GC", 4.1, 50.0, "47 Tucanae"),
    ("NGC 224", 10.6847, 41.2687, "Gal", 3.4, 178.0, "Andromeda Galaxy"),
    ("NGC 253", 11.8881, -25.2883, "Gal", 7.1, 27.0, "Sculptor Galaxy"),
    ("NGC 281", 13.4708, 56.6244, "Neb", 7.4, 35.0, "Pacman Nebula"),
    ("NGC 292", 13.1867, -72.8286, "Gal", 2.3, 316.0, "Small Magellanic Cloud"),
    ("NGC 362", 15.8094, -70.8489, "GC", 6.4, 14.0, ""),
    ("NGC 457", 19.8208, 58.2833, "OC", 6.4, 13.0, "Owl Cluster"),
    ("NGC 663", 26.5583, 61.2333, "OC", 7.1, 16.0, ""),
    ("NGC 752", 29.1625, 37.7833, "OC", 5.7, 50.0, ""),
    ("NGC 869", 34.7583, 57.1333, "OC", 5.3, 30.0, "h Persei"),
    ("NGC 884", 35.0583, 57.1500, "OC", 6.1, 30.0, "Chi Persei"),
    ("NGC 891", 35.6393, 42.3478, "Gal", 9.9, 14.0, ""),
    ("NGC 1023", 40.1001, 39.0626, "Gal", 9.4, 9.0, ""),
    ("NGC 1039", 40.5125, 42.7833, "OC", 5.5, 35.0, ""),
    ("NGC 1068", 40.6696, -0.0133, "Gal", 8.9, 7.0, ""),
    ("NGC 1261", 48.0675, -55.2164, "GC", 8.4, 7.0, ""),
    ("NGC 1275", 49.9507, 41.5117, "Gal", 11.6, 3.0, "Perseus A"),
    ("NGC 1300", 49.9207, -19.4111, "Gal", 10.4, 6.0, ""),
    ("NGC 1316", 50.6738, -37.2083, "Gal", 8.5, 12.0, "Fornax A"),
    ("NGC 1333", 52.2917, 31.3167, "RN", 5.6, 6.0, ""),
    ("NGC 1365", 53.4015, -36.1404, "Gal", 9.6, 11.0, "Great Barred Spiral"),
    ("NGC 1399", 54.6211, -35.4506, "Gal", 9.6, 7.0, ""),
    ("NGC 1491", 61.4833, 51.3167, "Neb", 10.0, 3.0, ""),
    ("NGC 1499", 60.2042, 36.3833, "Neb", 5.0, 145.0, "California Nebula"),
    ("NGC 1502", 61.0708, 62.3333, "OC", 6.9, 8.0, ""),
    ("NGC 1528", 63.3500, 51.2167, "OC", 6.4, 24.0, ""),
    ("NGC 1535", 63.0833, -12.7433, "PN", 9.6, 0.8, ""),
    ("NGC 1555", 63.3125, 19.5367, "RN", 10.0, 0.5, "Hind's Variable Nebula"),
    ("NGC 1566", 65.0025, -54.9381, "Gal", 9.4, 8.0, ""),
    ("NGC 1614", 68.4986, -8.5783, "Gal", 11.6, 1.0, ""),
    ("NGC 1647", 71.4833, 19.1167, "OC", 6.4, 45.0, ""),
    ("NGC 1746", 75.7333, 23.7833, "OC", 6.1, 42.0, ""),
    ("NGC 1851", 78.5282, -40.0464, "GC", 7.1, 11.0, ""),
    ("NGC 1904", 81.0462, -24.5247, "GC", 7.7, 9.0, ""),
    ("NGC 1952", 83.6331, 22.0145, "SNR", 8.4, 6.0, "Crab Nebula"),
    ("NGC 1973", 83.8250, -4.7833, "RN", 7.0, 5.0, "Running Man Nebula"),
    ("NGC 1975", 83.8625, -4.6833, "RN", 7.0, 5.0, ""),
    ("NGC 1976", 83.8221, -5.3911, "Neb", 4.0, 85.0, "Orion Nebula"),
    ("NGC 1977", 83.8458, -4.8000, "RN", 7.0, 20.0, ""),
    ("NGC 1981", 83.8292, -4.4333, "OC", 4.6, 25.0, ""),
    ("NGC 1982", 83.8917, -5.2667, "Neb", 9.0, 20.0, "De Mairan's Nebula"),
    ("NGC 2024", 85.4213, -1.9033, "Neb", 2.0, 30.0, "Flame Nebula"),
    ("NGC 2070", 84.6763, -69.1009, "Neb", 5.0, 40.0, "Tarantula Nebula"),
    ("NGC 2099", 88.0708, 32.5500, "OC", 6.2, 24.0, ""),
    ("NGC 2158", 91.8583, 24.0833, "OC", 8.6, 5.0, ""),
    ("NGC 2168", 92.2250, 24.3500, "OC", 5.3, 28.0, ""),
    ("NGC 2174", 92.2125, 20.4833, "Neb", 6.8, 40.0, "Monkey Head Nebula"),
    ("NGC 2237", 97.9667, 5.0333, "Neb", 6.0, 80.0, "Rosette Nebula"),
    ("NGC 2244", 97.9833, 4.9333, "OC", 4.8, 24.0, ""),
    ("NGC 2261", 100.2458, 8.7400, "RN", 9.0, 2.0, "Hubble's Variable Nebula"),
    ("NGC 2264", 100.2417, 9.8833, "OC", 3.9, 20.0, "Christmas Tree Cluster"),
    ("NGC 2287", 101.5042, -20.7500, "OC", 4.5, 38.0, ""),
    ("NGC 2323", 105.6833, -8.3667, "OC", 5.9, 16.0, ""),
    ("NGC 2359", 109.2750, -13.2167, "Neb", 11.5, 10.0, "Thor's Helmet"),
    ("NGC 2362", 109.4292, -24.9583, "OC", 4.1, 8.0, "Tau Canis Majoris Cluster"),
    ("NGC 2392", 112.2917, 20.9117, "PN", 9.2, 0.8, "Eskimo Nebula"),
    ("NGC 2403", 114.2142, 65.6025, "Gal", 8.5, 22.0, ""),
    ("NGC 2419", 114.5333, 38.8817, "GC", 10.4, 6.0, ""),
    ("NGC 2438", 115.4542, -14.7333, "PN", 10.8, 1.1, ""),
    ("NGC 2440", 115.4250, -18.2083, "PN", 9.4, 1.2, ""),
    ("NGC 2447", 114.1500, -14.4833, "OC", 5.2, 30.0, ""),
    ("NGC 2451", 116.0167, -37.9667, "OC", 2.8, 45.0, ""),
    ("NGC 2477", 118.0458, -38.5333, "OC", 5.8, 27.0, ""),
    ("NGC 2516", 119.5167, -60.7500, "OC", 3.8, 30.0, ""),
    ("NGC 2548", 123.4167, -5.8000, "OC", 5.5, 54.0, ""),
    ("NGC 2682", 132.8500, 11.8167, "OC", 6.1, 30.0, ""),
    ("NGC 2736", 135.0417, -45.9500, "SNR", 12.0, 20.0, "Pencil Nebula"),
    ("NGC 2841", 140.5111, 50.9764, "Gal", 9.2, 8.0, ""),
    ("NGC 2903", 143.0422, 21.5006, "Gal", 9.0, 13.0, ""),
    ("NGC 2976", 146.8143, 67.9156, "Gal", 10.2, 6.0, ""),
    ("NGC 3031", 148.8882, 69.0653, "Gal", 6.9, 27.0, "Bode's Galaxy"),
    ("NGC 3034", 148.9685, 69.6797, "Gal", 8.4, 11.0, "Cigar Galaxy"),
    ("NGC 3079", 150.4908, 55.6797, "Gal", 10.9, 8.0, ""),
    ("NGC 3114", 150.6917, -60.0667, "OC", 4.2, 35.0, ""),
    ("NGC 3115", 151.3080, -7.7186, "Gal", 8.9, 7.0, "Spindle Galaxy"),
    ("NGC 3132", 151.7583, -40.4369, "PN", 8.2, 1.4, "Eight-Burst Nebula"),
    ("NGC 3184", 154.5706, 41.4242, "Gal", 9.8, 7.0, ""),
    ("NGC 3190", 154.5243, 21.8327, "Gal", 11.1, 4.0, ""),
    ("NGC 3195", 153.0000, -80.8611, "PN", 11.6, 0.6, ""),
    ("NGC 3201", 154.4034, -46.4116, "GC", 6.7, 18.0, ""),
    ("NGC 3228", 155.3375, -51.7167, "OC", 6.0, 18.0, ""),
    ("NGC 3242", 156.1833, -18.6414, "PN", 7.3, 0.8, "Ghost of Jupiter"),
    ("NGC 3293", 157.8917, -58.2333, "OC", 4.7, 6.0, ""),
    ("NGC 3324", 159.2625, -58.6333, "Neb", 6.7, 16.0, "Gabriela Mistral Nebula"),
    ("NGC 3344", 160.8811, 24.9225, "Gal", 9.9, 7.0, ""),
    ("NGC 3351", 160.9902, 11.7037, "Gal", 9.7, 7.0, ""),
    ("NGC 3368", 161.6904, 11.8197, "Gal", 9.3, 7.0, ""),
    ("NGC 3372", 161.2542, -59.8667, "Neb", 3.0, 120.0, "Carina Nebula"),
    ("NGC 3379", 161.9565, 12.5816, "Gal", 9.3, 5.0, ""),
    ("NGC 3521", 166.4526, -0.0361, "Gal", 8.9, 11.0, ""),
    ("NGC 3532", 166.4375, -58.7667, "OC", 3.0, 55.0, "Wishing Well Cluster"),
    ("NGC 3556", 167.8791, 55.6741, "Gal", 10.0, 8.0, ""),
    ("NGC 3587", 168.6987, 55.0192, "PN", 9.9, 3.4, "Owl Nebula"),
    ("NGC 3603", 168.7917, -61.2500, "OC", 9.1, 12.0, ""),
    ("NGC 3623", 169.7330, 13.0922, "Gal", 9.3, 10.0, ""),
    ("NGC 3627", 170.0626, 12.9914, "Gal", 8.9, 9.0, ""),
    ("NGC 3628", 170.0716, 13.5886, "Gal", 9.5, 15.0, "Hamburger Galaxy"),
    ("NGC 3766", 174.7958, -61.6167, "OC", 5.3, 12.0, ""),
    ("NGC 3918", 177.5042, -57.1853, "PN", 8.1, 0.3, "Blue Planetary"),
    ("NGC 4038", 180.4712, -18.8676, "Gal", 10.5, 5.0, "Antennae Galaxy"),
    ("NGC 4039", 180.4844, -18.8842, "Gal", 10.5, 3.0, ""),
    ("NGC 4244", 184.3739, 37.8071, "Gal", 10.4, 16.0, "Silver Needle"),
    ("NGC 4258", 184.7397, 47.3039, "Gal", 8.4, 19.0, ""),
    ("NGC 4321", 185.7289, 15.8222, "Gal", 9.3, 7.0, ""),
    ("NGC 4372", 186.4400, -72.6592, "GC", 7.8, 19.0, ""),
    ("NGC 4374", 186.2655, 12.8870, "Gal", 9.1, 7.0, ""),
    ("NGC 4382", 186.3504, 18.1912, "Gal", 9.1, 7.0, ""),
    ("NGC 4406", 186.5491, 12.9464, "Gal", 8.9, 9.0, ""),
    ("NGC 4472", 187.4449, 8.0004, "Gal", 8.4, 10.0, ""),
    ("NGC 4486", 187.7059, 12.3911, "Gal", 8.6, 8.0, "Virgo A"),
    ("NGC 4501", 188.0058, 14.4204, "Gal", 9.6, 7.0, ""),
    ("NGC 4548", 188.8601, 14.4968, "Gal", 10.2, 5.0, ""),
    ("NGC 4552", 188.9159, 12.5563, "Gal", 9.8, 5.0, ""),
    ("NGC 4565", 189.0866, 25.9876, "Gal", 9.6, 16.0, "Needle Galaxy"),
    ("NGC 4569", 189.2093, 13.1631, "Gal", 9.5, 10.0, ""),
    ("NGC 4579", 189.4316, 11.8181, "Gal", 9.7, 6.0, ""),
    ("NGC 4590", 189.8667, -26.7447, "GC", 7.8, 11.0, ""),
    ("NGC 4594", 189.9976, -11.6230, "Gal", 8.0, 9.0, "Sombrero Galaxy"),
    ("NGC 4631", 190.5333, 32.5417, "Gal", 9.2, 15.0, "Whale Galaxy"),
    ("NGC 4636", 190.7076, 2.6876, "Gal", 9.5, 6.0, ""),
    ("NGC 4649", 190.9167, 11.5528, "Gal", 8.8, 7.0, ""),
    ("NGC 4656", 190.9917, 32.1667, "Gal", 10.5, 15.0, "Hockey Stick Galaxy"),
    ("NGC 4676", 191.5387, 30.7271, "Gal", 13.0, 2.0, "Mice Galaxies"),
    ("NGC 4725", 192.6108, 25.5007, "Gal", 9.4, 11.0, ""),
    ("NGC 4736", 192.7215, 41.1203, "Gal", 8.2, 14.0, ""),
    ("NGC 4755", 193.4250, -60.3667, "OC", 4.2, 10.0, "Jewel Box"),
    ("NGC 4826", 194.1826, 21.6828, "Gal", 8.5, 10.0, "Black Eye Galaxy"),
    ("NGC 4833", 194.8913, -70.8764, "GC", 6.9, 14.0, ""),
    ("NGC 5024", 198.2303, 18.1681, "GC", 7.6, 13.0, ""),
    ("NGC 5055", 198.9553, 42.0293, "Gal", 8.6, 13.0, "Sunflower Galaxy"),
    ("NGC 5128", 201.3651, -43.0191, "Gal", 6.8, 26.0, "Centaurus A"),
    ("NGC 5139", 201.6968, -47.4797, "GC", 3.7, 36.0, "Omega Centauri"),
    ("NGC 5194", 202.4696, 47.1952, "Gal", 8.4, 11.0, "Whirlpool Galaxy"),
    ("NGC 5195", 202.4983, 47.2661, "Gal", 9.6, 6.0, ""),
    ("NGC 5236", 204.2538, -29.8654, "Gal", 7.6, 13.0, "Southern Pinwheel"),
    ("NGC 5272", 205.5484, 28.3773, "GC", 6.2, 18.0, ""),
    ("NGC 5457", 210.8024, 54.3492, "Gal", 7.9, 29.0, "Pinwheel Galaxy"),
    ("NGC 5466", 211.3637, 28.5339, "GC", 9.0, 11.0, ""),
    ("NGC 5822", 226.0583, -54.3500, "OC", 6.5, 40.0, ""),
    ("NGC 5866", 226.6232, 55.7634, "Gal", 9.9, 6.0, "Spindle Galaxy"),
    ("NGC 5897", 229.3519, -21.0106, "GC", 8.5, 13.0, ""),
    ("NGC 5904", 229.6384, 2.0811, "GC", 5.7, 23.0, ""),
    ("NGC 5907", 228.9732, 56.3287, "Gal", 10.3, 13.0, "Splinter Galaxy"),
    ("NGC 5986", 236.5125, -37.7864, "GC", 7.1, 10.0, ""),
    ("NGC 6087", 244.7583, -57.9333, "OC", 5.4, 12.0, ""),
    ("NGC 6093", 244.2601, -22.9758, "GC", 7.3, 10.0, ""),
    ("NGC 6121", 245.8968, -26.5258, "GC", 5.6, 36.0, ""),
    ("NGC 6171", 248.1333, -13.0531, "GC", 7.9, 13.0, ""),
    ("NGC 6205", 250.4218, 36.4613, "GC", 5.8, 20.0, "Hercules Cluster"),
    ("NGC 6210", 251.1250, 23.7997, "PN", 8.8, 0.3, ""),
    ("NGC 6218", 251.8093, -1.9483, "GC", 6.7, 16.0, ""),
    ("NGC 6231", 253.5417, -41.8333, "OC", 2.6, 15.0, ""),
    ("NGC 6254", 254.2877, -4.1003, "GC", 6.6, 20.0, ""),
    ("NGC 6266", 255.3032, -30.1136, "GC", 6.5, 15.0, ""),
    ("NGC 6273", 255.6571, -26.2681, "GC", 6.8, 17.0, ""),
    ("NGC 6302", 258.0833, -37.1044, "PN", 7.1, 1.4, "Bug Nebula"),
    ("NGC 6341", 259.2808, 43.1364, "GC", 6.4, 14.0, ""),
    ("NGC 6352", 261.3714, -48.4222, "GC", 8.1, 7.0, ""),
    ("NGC 6362", 262.9750, -67.0489, "GC", 7.6, 10.0, ""),
    ("NGC 6369", 261.3125, -23.7597, "PN", 11.4, 0.5, "Little Ghost Nebula"),
    ("NGC 6388", 264.0718, -44.7356, "GC", 6.7, 10.0, ""),
    ("NGC 6397", 265.1755, -53.6744, "GC", 5.7, 32.0, ""),
    ("NGC 6402", 264.4004, -3.2458, "GC", 7.6, 11.0, ""),
    ("NGC 6405", 265.0834, -32.2536, "OC", 4.2, 33.0, "Butterfly Cluster"),
    ("NGC 6475", 268.4667, -34.7928, "OC", 3.3, 80.0, "Ptolemy Cluster"),
    ("NGC 6494", 269.2667, -19.0167, "OC", 6.9, 27.0, ""),
    ("NGC 6514", 270.6225, -23.0300, "Neb", 6.3, 28.0, "Trifid Nebula"),
    ("NGC 6523", 270.9042, -24.3833, "Neb", 6.0, 90.0, "Lagoon Nebula"),
    ("NGC 6530", 271.1042, -24.2833, "OC", 4.6, 15.0, ""),
    ("NGC 6531", 270.9708, -22.4917, "OC", 6.5, 13.0, ""),
    ("NGC 6543", 269.6392, 66.6331, "PN", 8.1, 0.6, "Cat's Eye Nebula"),
    ("NGC 6544", 271.8333, -24.9972, "GC", 7.5, 9.0, ""),
    ("NGC 6572", 273.1250, 6.8528, "PN", 8.1, 0.1, ""),
    ("NGC 6603", 274.5375, -18.5167, "OC", 11.1, 5.0, ""),
    ("NGC 6611", 274.7000, -13.7833, "OC", 6.0, 7.0, "Eagle Nebula Cluster"),
    ("NGC 6613", 275.2375, -17.1278, "OC", 7.5, 9.0, ""),
    ("NGC 6618", 275.1917, -16.1708, "Neb", 6.0, 11.0, "Omega Nebula"),
    ("NGC 6626", 276.1364, -24.8700, "GC", 6.8, 11.0, ""),
    ("NGC 6633", 276.8417, 6.6167, "OC", 4.6, 27.0, ""),
    ("NGC 6637", 277.8463, -32.3481, "GC", 7.6, 10.0, ""),
    ("NGC 6656", 279.0998, -23.9047, "GC", 5.1, 32.0, ""),
    ("NGC 6681", 280.8029, -32.2911, "GC", 7.9, 8.0, ""),
    ("NGC 6694", 281.3208, -9.3833, "OC", 8.0, 15.0, ""),
    ("NGC 6705", 282.7667, -6.2667, "OC", 6.3, 14.0, "Wild Duck Cluster"),
    ("NGC 6709", 282.8417, 10.3333, "OC", 6.7, 13.0, ""),
    ("NGC 6720", 283.3963, 33.0289, "PN", 8.8, 1.4, "Ring Nebula"),
    ("NGC 6723", 284.8875, -36.6322, "GC", 7.3, 13.0, ""),
    ("NGC 6726", 285.4583, -36.9500, "RN", 7.0, 2.0, ""),
    ("NGC 6752", 287.7170, -59.9847, "GC", 5.4, 29.0, ""),
    ("NGC 6779", 289.1483, 30.1842, "GC", 8.3, 9.0, ""),
    ("NGC 6809", 294.9988, -30.9647, "GC", 6.3, 19.0, ""),
    ("NGC 6818", 295.3583, -14.1711, "PN", 9.3, 0.4, "Little Gem Nebula"),
    ("NGC 6822", 296.2354, -14.8003, "Gal", 8.7, 20.0, "Barnard's Galaxy"),
    ("NGC 6826", 296.2000, 50.5253, "PN", 8.8, 0.4, "Blinking Planetary"),
    ("NGC 6838", 298.4438, 18.7792, "GC", 8.2, 7.0, ""),
    ("NGC 6853", 299.9015, 22.7211, "PN", 7.5, 8.0, "Dumbbell Nebula"),
    ("NGC 6864", 301.5201, -21.9211, "GC", 8.5, 7.0, ""),
    ("NGC 6888", 303.0625, 38.3500, "Neb", 7.4, 18.0, "Crescent Nebula"),
    ("NGC 6913", 305.9708, 38.5083, "OC", 7.1, 7.0, ""),
    ("NGC 6934", 308.5474, 7.4044, "GC", 8.8, 7.0, ""),
    ("NGC 6946", 308.7179, 60.1539, "Gal", 8.8, 11.0, "Fireworks Galaxy"),
    ("NGC 6960", 312.1750, 30.7167, "SNR", 7.0, 70.0, "Western Veil"),
    ("NGC 6979", 313.0500, 32.1667, "SNR", 7.0, 25.0, "Pickering's Triangle"),
    ("NGC 6981", 313.3654, -12.5372, "GC", 9.3, 6.0, ""),
    ("NGC 6992", 313.9167, 31.7167, "SNR", 7.0, 60.0, "Eastern Veil"),
    ("NGC 6994", 314.7500, -12.6333, "Ast", 9.0, 2.8, ""),
    ("NGC 7000", 314.6802, 44.3117, "Neb", 4.0, 120.0, "North America Nebula"),
    ("NGC 7006", 315.3746, 16.1872, "GC", 10.6, 4.0, ""),
    ("NGC 7009", 316.0583, -11.3639, "PN", 8.0, 0.4, "Saturn Nebula"),
    ("NGC 7023", 315.3917, 68.1667, "RN", 7.1, 18.0, "Iris Nebula"),
    ("NGC 7027", 316.7583, 42.2353, "PN", 8.5, 0.3, ""),
    ("NGC 7078", 322.4930, 12.1670, "GC", 6.2, 18.0, ""),
    ("NGC 7089", 323.3626, -0.8233, "GC", 6.5, 16.0, ""),
    ("NGC 7099", 325.0922, -23.1797, "GC", 7.2, 12.0, ""),
    ("NGC 7129", 325.7375, 66.1167, "RN", 11.5, 3.0, ""),
    ("NGC 7209", 331.2833, 46.5000, "OC", 6.7, 25.0, ""),
    ("NGC 7235", 333.8458, 57.2500, "OC", 7.7, 4.0, ""),
    ("NGC 7243", 333.7917, 49.8833, "OC", 6.4, 21.0, ""),
    ("NGC 7293", 337.4108, -20.8372, "PN", 7.6, 16.0, "Helix Nebula"),
    ("NGC 7317", 338.8917, 33.9406, "Gal", 13.6, 0.5, ""),
    ("NGC 7318", 338.9583, 33.9628, "Gal", 13.0, 1.0, "Stephan's Quintet"),
    ("NGC 7320", 339.0208, 33.9483, "Gal", 12.6, 2.0, ""),
    ("NGC 7331", 339.2670, 34.4157, "Gal", 9.5, 11.0, ""),
    ("NGC 7380", 341.8250, 58.1333, "OC", 7.2, 12.0, "Wizard Nebula"),
    ("NGC 7479", 346.2361, 12.3228, "Gal", 10.9, 4.0, ""),
    ("NGC 7510", 348.0667, 60.5833, "OC", 7.9, 4.0, ""),
    ("NGC 7635", 350.2042, 61.2000, "Neb", 10.0, 15.0, "Bubble Nebula"),
    ("NGC 7654", 351.2042, 61.5833, "OC", 7.3, 13.0, ""),
    ("NGC 7662", 351.6583, 42.5328, "PN", 8.3, 0.5, "Blue Snowball"),
    ("NGC 7789", 359.3375, 56.7167, "OC", 6.7, 16.0, "Caroline's Rose"),
    ("NGC 7793", 359.4576, -32.5914, "Gal", 9.1, 6.0, ""),
]

# Named stars — ~300 IAU-named and Bayer-designated stars to mag ~5.5
# Provides full-sky coverage so any field will have labeled reference stars.
NAMED_STARS_CATALOG = [
    # --- Magnitude < 0 ---
    ("Sirius", 101.2872, -16.7161, "Star", -1.46, 0, "Alpha CMa"),
    ("Canopus", 95.9880, -52.6957, "Star", -0.74, 0, "Alpha Car"),
    ("Arcturus", 213.9153, 19.1824, "Star", -0.05, 0, "Alpha Boo"),
    # --- Magnitude 0–1 ---
    ("Vega", 279.2347, 38.7837, "Star", 0.03, 0, "Alpha Lyr"),
    ("Capella", 79.1723, 45.9980, "Star", 0.08, 0, "Alpha Aur"),
    ("Rigel", 78.6344, -8.2016, "Star", 0.13, 0, "Beta Ori"),
    ("Procyon", 114.8255, 5.2250, "Star", 0.34, 0, "Alpha CMi"),
    ("Betelgeuse", 88.7929, 7.4071, "Star", 0.42, 0, "Alpha Ori"),
    ("Achernar", 24.4285, -57.2368, "Star", 0.46, 0, "Alpha Eri"),
    ("Hadar", 210.9558, -60.3730, "Star", 0.61, 0, "Beta Cen"),
    ("Altair", 297.6958, 8.8683, "Star", 0.77, 0, "Alpha Aql"),
    ("Acrux", 186.6496, -63.0990, "Star", 0.76, 0, "Alpha Cru"),
    ("Aldebaran", 68.9802, 16.5093, "Star", 0.86, 0, "Alpha Tau"),
    ("Antares", 247.3519, -26.4320, "Star", 0.96, 0, "Alpha Sco"),
    ("Spica", 201.2983, -11.1614, "Star", 0.97, 0, "Alpha Vir"),
    # --- Magnitude 1–2 ---
    ("Pollux", 116.3289, 28.0262, "Star", 1.14, 0, "Beta Gem"),
    ("Fomalhaut", 344.4127, -29.6222, "Star", 1.16, 0, "Alpha PsA"),
    ("Deneb", 310.3580, 45.2803, "Star", 1.25, 0, "Alpha Cyg"),
    ("Mimosa", 191.9302, -59.6885, "Star", 1.25, 0, "Beta Cru"),
    ("Regulus", 152.0929, 11.9672, "Star", 1.35, 0, "Alpha Leo"),
    ("Adhara", 104.6565, -28.9723, "Star", 1.50, 0, "Epsilon CMa"),
    ("Shaula", 263.4022, -37.1038, "Star", 1.63, 0, "Lambda Sco"),
    ("Castor", 113.6497, 31.8884, "Star", 1.58, 0, "Alpha Gem"),
    ("Gacrux", 187.7914, -57.1132, "Star", 1.64, 0, "Gamma Cru"),
    ("Bellatrix", 81.2828, 6.3497, "Star", 1.64, 0, "Gamma Ori"),
    ("Elnath", 81.5728, 28.6075, "Star", 1.65, 0, "Beta Tau"),
    ("Miaplacidus", 138.3000, -69.7172, "Star", 1.68, 0, "Beta Car"),
    ("Alnilam", 84.0533, -1.2019, "Star", 1.69, 0, "Epsilon Ori"),
    ("Alnair", 332.0583, -46.9611, "Star", 1.74, 0, "Alpha Gru"),
    ("Alnitak", 85.1897, -1.9425, "Star", 1.77, 0, "Zeta Ori"),
    ("Alioth", 193.5073, 55.9599, "Star", 1.77, 0, "Epsilon UMa"),
    ("Dubhe", 165.9319, 61.7510, "Star", 1.79, 0, "Alpha UMa"),
    ("Mirfak", 51.0808, 49.8613, "Star", 1.80, 0, "Alpha Per"),
    ("Wezen", 107.0978, -26.3932, "Star", 1.84, 0, "Delta CMa"),
    ("Kaus Australis", 276.0430, -34.3845, "Star", 1.85, 0, "Epsilon Sgr"),
    ("Alkaid", 206.8853, 49.3133, "Star", 1.86, 0, "Eta UMa"),
    ("Avior", 125.6285, -59.5095, "Star", 1.86, 0, "Epsilon Car"),
    ("Sargas", 264.3297, -42.9980, "Star", 1.87, 0, "Theta Sco"),
    ("Menkalinan", 89.8827, 44.9474, "Star", 1.90, 0, "Beta Aur"),
    ("Atria", 252.1662, -69.0277, "Star", 1.92, 0, "Alpha TrA"),
    ("Alhena", 99.4279, 16.3993, "Star", 1.93, 0, "Gamma Gem"),
    ("Peacock", 306.4119, -56.7350, "Star", 1.94, 0, "Alpha Pav"),
    ("Alsephina", 131.1760, -54.7087, "Star", 1.96, 0, "Delta Vel"),
    ("Mirzam", 95.6749, -17.9559, "Star", 1.98, 0, "Beta CMa"),
    # --- Magnitude 2–3 ---
    ("Alphard", 141.8968, -8.6586, "Star", 2.00, 0, "Alpha Hya"),
    ("Polaris", 37.9546, 89.2641, "Star", 2.02, 0, "Alpha UMi"),
    ("Hamal", 31.7933, 23.4624, "Star", 2.00, 0, "Alpha Ari"),
    ("Diphda", 10.8974, -17.9866, "Star", 2.02, 0, "Beta Cet"),
    ("Mizar", 200.9814, 54.9254, "Star", 2.04, 0, "Zeta UMa"),
    ("Nunki", 283.8163, -26.2967, "Star", 2.05, 0, "Sigma Sgr"),
    ("Menkent", 211.6706, -36.3700, "Star", 2.06, 0, "Theta Cen"),
    ("Rasalhague", 263.7334, 12.5600, "Star", 2.08, 0, "Alpha Oph"),
    ("Kochab", 222.6764, 74.1555, "Star", 2.08, 0, "Beta UMi"),
    ("Saiph", 86.9391, -9.6696, "Star", 2.09, 0, "Kappa Ori"),
    ("Algol", 47.0422, 40.9564, "Star", 2.12, 0, "Beta Per"),
    ("Denebola", 177.2649, 14.5720, "Star", 2.14, 0, "Beta Leo"),
    ("Tiaki", 340.6668, -46.8847, "Star", 2.17, 0, "Beta Gru"),
    ("Muhlifain", 190.3794, -48.9600, "Star", 2.17, 0, "Gamma Cen"),
    ("Sadr", 305.5572, 40.2567, "Star", 2.20, 0, "Gamma Cyg"),
    ("Aspidiske", 139.2725, -59.2753, "Star", 2.21, 0, "Iota Car"),
    ("Suhail", 136.9990, -43.4326, "Star", 2.21, 0, "Lambda Vel"),
    ("Alphecca", 233.6720, 26.7147, "Star", 2.23, 0, "Alpha CrB"),
    ("Mintaka", 83.0017, -0.2992, "Star", 2.23, 0, "Delta Ori"),
    ("Schedar", 10.1268, 56.5373, "Star", 2.23, 0, "Alpha Cas"),
    ("Eltanin", 269.1516, 51.4890, "Star", 2.23, 0, "Gamma Dra"),
    ("Naos", 120.8961, -40.0033, "Star", 2.25, 0, "Zeta Pup"),
    ("Caph", 2.2946, 59.1498, "Star", 2.27, 0, "Beta Cas"),
    ("Merak", 165.4603, 56.3824, "Star", 2.37, 0, "Beta UMa"),
    ("Enif", 326.0465, 9.8750, "Star", 2.39, 0, "Epsilon Peg"),
    ("Scheat", 345.9437, 28.0828, "Star", 2.42, 0, "Beta Peg"),
    ("Phecda", 178.4576, 53.6948, "Star", 2.44, 0, "Gamma UMa"),
    ("Aludra", 111.0238, -29.3031, "Star", 2.45, 0, "Eta CMa"),
    ("Markab", 346.1903, 15.2053, "Star", 2.49, 0, "Alpha Peg"),
    ("Alderamin", 319.6448, 62.5856, "Star", 2.51, 0, "Alpha Cep"),
    ("Zubeneschamali", 229.2519, -9.3830, "Star", 2.61, 0, "Beta Lib"),
    ("Unukalhai", 236.0670, 6.4256, "Star", 2.65, 0, "Alpha Ser"),
    ("Ruchbah", 21.4540, 60.2353, "Star", 2.68, 0, "Delta Cas"),
    ("Tarazed", 296.5647, 10.6133, "Star", 2.72, 0, "Gamma Aql"),
    ("Rasalgethi", 258.6618, 14.3903, "Star", 2.81, 0, "Alpha Her"),
    ("Algenib", 3.3089, 15.1836, "Star", 2.83, 0, "Gamma Peg"),
    ("Vindemiatrix", 195.5443, 10.9592, "Star", 2.83, 0, "Epsilon Vir"),
    ("Cor Caroli", 194.0068, 38.3183, "Star", 2.90, 0, "Alpha CVn"),
    ("Tureis", 121.8861, -24.3044, "Star", 2.93, 0, "Rho Pup"),
    ("Alshat", 305.2571, -14.7814, "Star", 2.87, 0, "Alpha Cap"),
    ("Zubenelgenubi", 222.7196, -16.0416, "Star", 2.75, 0, "Alpha Lib"),
    ("Sabik", 257.5948, -15.7249, "Star", 2.43, 0, "Eta Oph"),
    ("Kaus Media", 275.2485, -29.8281, "Star", 2.70, 0, "Delta Sgr"),
    ("Kaus Borealis", 275.3255, -25.4217, "Star", 2.81, 0, "Lambda Sgr"),
    ("Ascella", 285.6530, -29.8801, "Star", 2.59, 0, "Zeta Sgr"),
    # --- Magnitude 3–4 ---
    ("Mira", 34.8366, -2.9776, "Star", 2.00, 0, "Omicron Cet"),
    ("Albireo", 292.6804, 27.9597, "Star", 3.18, 0, "Beta Cyg"),
    ("Propus", 95.7400, 22.5069, "Star", 3.28, 0, "Eta Gem"),
    ("Megrez", 183.8565, 57.0326, "Star", 3.31, 0, "Delta UMa"),
    ("Thuban", 211.0973, 64.3757, "Star", 3.67, 0, "Alpha Dra"),
    ("Alcor", 201.3063, 54.9879, "Star", 3.99, 0, "80 UMa"),
    ("Errai", 354.8365, 77.6324, "Star", 3.21, 0, "Gamma Cep"),
    ("Alfirk", 322.1649, 70.5607, "Star", 3.23, 0, "Beta Cep"),
    ("Pherkad", 230.1821, 71.8340, "Star", 3.05, 0, "Gamma UMi"),
    ("Muscida", 127.5661, 60.7183, "Star", 3.36, 0, "Omicron UMa"),
    ("Tania Borealis", 154.2744, 42.9144, "Star", 3.45, 0, "Lambda UMa"),
    ("Tania Australis", 155.5825, 41.4994, "Star", 3.06, 0, "Mu UMa"),
    ("Talitha", 134.8019, 48.0418, "Star", 3.14, 0, "Iota UMa"),
    ("Chara", 188.4357, 41.3575, "Star", 4.26, 0, "Beta CVn"),
    ("La Superba", 191.2826, 45.4403, "Star", 4.80, 0, "Y CVn"),
    ("Nusakan", 231.9574, 29.1057, "Star", 3.68, 0, "Beta CrB"),
    ("Izar", 221.2466, 27.0743, "Star", 2.37, 0, "Epsilon Boo"),
    ("Nekkar", 225.3654, 40.3906, "Star", 3.58, 0, "Beta Boo"),
    ("Seginus", 218.0197, 38.3083, "Star", 3.03, 0, "Gamma Boo"),
    ("Muphrid", 208.6712, 18.3977, "Star", 2.68, 0, "Eta Boo"),
    ("Princeps", 218.5178, 19.1825, "Star", 3.47, 0, "Delta Boo"),
    ("Alkalurops", 219.9063, 37.3773, "Star", 4.31, 0, "Mu Boo"),
    ("Rastaban", 262.6082, 52.3014, "Star", 2.79, 0, "Beta Dra"),
    ("Altais", 288.1388, 67.6616, "Star", 3.07, 0, "Delta Dra"),
    ("Edasich", 231.2328, 58.9660, "Star", 3.29, 0, "Iota Dra"),
    ("Grumium", 268.3828, 56.8726, "Star", 3.75, 0, "Xi Dra"),
    ("Giausar", 172.8510, 69.3311, "Star", 3.85, 0, "Lambda Dra"),
    ("Aldhibah", 256.1175, 65.7148, "Star", 3.17, 0, "Zeta Dra"),
    ("Tyl", 271.0873, 72.1488, "Star", 3.57, 0, "Epsilon Dra"),
    ("Sheliak", 282.5199, 33.3628, "Star", 3.52, 0, "Beta Lyr"),
    ("Sulafat", 284.7360, 32.6896, "Star", 3.24, 0, "Gamma Lyr"),
    ("Gienah", 183.9516, -17.5419, "Star", 2.59, 0, "Gamma Crv"),
    ("Algorab", 187.4660, -16.5152, "Star", 2.95, 0, "Delta Crv"),
    ("Kraz", 188.5968, -23.3968, "Star", 2.65, 0, "Beta Crv"),
    ("Minkar", 182.1034, -22.6198, "Star", 3.02, 0, "Epsilon Crv"),
    ("Zosma", 168.5270, 20.5242, "Star", 2.56, 0, "Delta Leo"),
    ("Chertan", 168.5600, 15.4297, "Star", 3.33, 0, "Theta Leo"),
    ("Algieba", 154.9929, 19.8414, "Star", 2.28, 0, "Gamma Leo"),
    ("Subra", 148.1908, 9.8925, "Star", 3.52, 0, "Omicron Leo"),
    ("Adhafera", 154.1725, 23.4173, "Star", 3.44, 0, "Zeta Leo"),
    ("Rasalas", 148.1908, 26.0070, "Star", 3.88, 0, "Mu Leo"),
    ("Alterf", 142.9302, 22.9681, "Star", 4.31, 0, "Lambda Leo"),
    ("Zavijava", 177.6738, 1.7647, "Star", 3.61, 0, "Beta Vir"),
    ("Porrima", 190.4151, -1.4494, "Star", 2.74, 0, "Gamma Vir"),
    ("Heze", 203.6733, -0.5958, "Star", 3.37, 0, "Zeta Vir"),
    ("Zaniah", 185.1798, -0.6668, "Star", 3.89, 0, "Eta Vir"),
    ("Syrma", 214.0036, -6.0006, "Star", 4.07, 0, "Iota Vir"),
    ("Rijl al Awwa", 193.9002, 3.3975, "Star", 3.89, 0, "Mu Vir"),
    ("Navi", 14.1772, 60.7167, "Star", 2.47, 0, "Gamma Cas"),
    ("Segin", 28.5987, 63.6701, "Star", 3.37, 0, "Epsilon Cas"),
    ("Achird", 12.2763, 57.8152, "Star", 3.44, 0, "Eta Cas"),
    ("Marfak", 36.4868, 55.8955, "Star", 4.17, 0, "Theta Cas"),
    ("Fulu", 24.4984, 48.6284, "Star", 4.59, 0, "Zeta Cas"),
    ("Mirach", 17.4333, 35.6206, "Star", 2.06, 0, "Beta And"),
    ("Almach", 30.9751, 42.3298, "Star", 2.17, 0, "Gamma And"),
    ("Alpheratz", 2.0965, 29.0904, "Star", 2.06, 0, "Alpha And"),
    ("Sheratan", 28.6604, 20.8081, "Star", 2.64, 0, "Beta Ari"),
    ("Mesarthim", 28.3826, 19.2937, "Star", 3.86, 0, "Gamma Ari"),
    ("Botein", 44.5657, 19.7267, "Star", 4.35, 0, "Delta Ari"),
    ("Bharani", 41.2358, 27.2607, "Star", 3.63, 0, "41 Ari"),
    ("Menkib", 59.7413, 35.7911, "Star", 3.98, 0, "Xi Per"),
    ("Atik", 56.0792, 32.2882, "Star", 3.85, 0, "Omicron Per"),
    ("Electra", 56.2188, 24.1134, "Star", 3.70, 0, "17 Tau"),
    ("Taygeta", 56.3025, 24.4673, "Star", 4.30, 0, "19 Tau"),
    ("Maia", 56.4565, 24.3678, "Star", 3.87, 0, "20 Tau"),
    ("Merope", 56.5812, 23.9484, "Star", 4.18, 0, "23 Tau"),
    ("Alcyone", 56.8712, 24.1053, "Star", 2.87, 0, "Eta Tau"),
    ("Atlas", 57.2907, 24.0534, "Star", 3.63, 0, "27 Tau"),
    ("Pleione", 57.2967, 24.1367, "Star", 5.09, 0, "28 Tau"),
    ("Ain", 67.1542, 19.1804, "Star", 3.53, 0, "Epsilon Tau"),
    ("Hyadum I", 65.7337, 15.9622, "Star", 3.65, 0, "Gamma Tau"),
    ("Hyadum II", 64.9484, 15.6276, "Star", 3.76, 0, "Delta1 Tau"),
    ("Prima Hyadum", 64.9484, 15.6276, "Star", 3.76, 0, "Delta1 Tau"),
    ("Tianguan", 84.4112, 21.1426, "Star", 3.00, 0, "Zeta Tau"),
    ("Tejat", 95.7400, 22.5069, "Star", 3.28, 0, "Mu Gem"),
    ("Mebsuta", 100.9833, 25.1311, "Star", 3.06, 0, "Epsilon Gem"),
    ("Wasat", 110.0308, 21.9822, "Star", 3.53, 0, "Delta Gem"),
    ("Alzirr", 104.6557, 16.5404, "Star", 3.36, 0, "Xi Gem"),
    ("Furud", 95.0784, -30.0634, "Star", 3.02, 0, "Zeta CMa"),
    ("Muliphein", 100.9821, -15.6333, "Star", 4.07, 0, "Gamma CMa"),
    ("Gomeisa", 111.7876, 8.2894, "Star", 2.89, 0, "Beta CMi"),
    ("Acubens", 134.6215, 11.8577, "Star", 4.25, 0, "Alpha Cnc"),
    ("Tegmine", 123.0531, 17.6476, "Star", 4.67, 0, "Zeta Cnc"),
    ("Asellus Borealis", 131.1712, 21.4686, "Star", 4.66, 0, "Gamma Cnc"),
    ("Asellus Australis", 131.6714, 18.1543, "Star", 3.94, 0, "Delta Cnc"),
    ("Alkes", 164.9437, -18.2986, "Star", 4.08, 0, "Alpha Crt"),
    ("Lesath", 263.6189, -37.2958, "Star", 2.69, 0, "Upsilon Sco"),
    ("Acrab", 241.3593, -19.8054, "Star", 2.62, 0, "Beta Sco"),
    ("Dschubba", 240.0833, -22.6217, "Star", 2.32, 0, "Delta Sco"),
    ("Sargas", 264.3297, -42.9980, "Star", 1.87, 0, "Theta Sco"),
    ("Fang", 239.7130, -26.1140, "Star", 3.96, 0, "Pi Sco"),
    ("Iklil", 239.2213, -25.5925, "Star", 3.88, 0, "Rho Sco"),
    ("Jabbah", 242.9990, -19.4608, "Star", 4.00, 0, "Nu Sco"),
    ("Grafias", 241.0930, -19.8053, "Star", 2.62, 0, "Beta1 Sco"),
    ("Cebalrai", 265.8682, 4.5673, "Star", 2.77, 0, "Beta Oph"),
    ("Yed Prior", 243.5862, -3.6945, "Star", 2.74, 0, "Delta Oph"),
    ("Yed Posterior", 244.5804, -4.6925, "Star", 3.24, 0, "Epsilon Oph"),
    ("Marfik", 248.9711, 1.9840, "Star", 3.82, 0, "Lambda Oph"),
    ("Kornephoros", 247.5549, 21.4896, "Star", 2.77, 0, "Beta Her"),
    ("Sarin", 258.7580, 24.8392, "Star", 3.14, 0, "Delta Her"),
    ("Maasym", 262.6846, 26.1106, "Star", 4.40, 0, "Lambda Her"),
    ("Ruticulus", 258.0380, 33.1004, "Star", 3.89, 0, "Zeta Her"),
    ("Kajam", 265.8682, 27.7245, "Star", 3.16, 0, "Omega Her"),
    ("Marsic", 258.7580, 17.0467, "Star", 3.42, 0, "Kappa Her"),
    ("Rotanev", 309.3872, 14.5954, "Star", 3.63, 0, "Beta Del"),
    ("Sualocin", 309.9095, 15.9122, "Star", 3.77, 0, "Alpha Del"),
    ("Albali", 311.9189, -9.4958, "Star", 3.77, 0, "Epsilon Aqr"),
    ("Sadalsuud", 322.8897, -5.5712, "Star", 2.91, 0, "Beta Aqr"),
    ("Sadalmelik", 331.4461, -0.3199, "Star", 2.96, 0, "Alpha Aqr"),
    ("Skat", 343.9864, -15.8208, "Star", 3.27, 0, "Delta Aqr"),
    ("Ancha", 339.1876, -7.7838, "Star", 4.17, 0, "Theta Aqr"),
    ("Situla", 342.3911, -4.2283, "Star", 5.03, 0, "Kappa Aqr"),
    ("Biham", 345.9693, 6.1979, "Star", 3.52, 0, "Theta Peg"),
    ("Homam", 340.7506, 10.8311, "Star", 3.41, 0, "Zeta Peg"),
    ("Matar", 340.3655, 30.2214, "Star", 2.94, 0, "Eta Peg"),
    ("Alkarab", 349.2945, 23.4041, "Star", 4.40, 0, "Upsilon Peg"),
    ("Sadalbari", 343.2925, 24.6018, "Star", 3.51, 0, "Mu Peg"),
    ("Errakis", 262.0853, 58.5662, "Star", 3.75, 0, "Mu Dra"),
    ("Alsafi", 288.1396, 69.6613, "Star", 3.17, 0, "Sigma Dra"),
    ("Athebyne", 274.4100, 67.1613, "Star", 4.22, 0, "Eta Dra"),
    ("Fawaris", 296.2444, 45.1309, "Star", 2.87, 0, "Delta Cyg"),
    ("Aljanah", 311.5528, 33.9703, "Star", 2.48, 0, "Epsilon Cyg"),
    ("Azelfafage", 326.7607, 51.1895, "Star", 4.56, 0, "Pi1 Cyg"),
    ("Rukh", 296.8296, 36.0897, "Star", 3.89, 0, "Delta2 Cyg"),
    # --- Magnitude 4–5.5 (key constellation stars for field identification) ---
    # Ursa Major faint members
    ("Muscida", 127.5661, 60.7183, "Star", 3.36, 0, "Omicron UMa"),
    ("Alula Borealis", 169.6197, 33.0944, "Star", 3.49, 0, "Nu UMa"),
    ("Alula Australis", 169.5451, 31.5293, "Star", 3.78, 0, "Xi UMa"),
    # Cassiopeia
    ("Tsih", 14.1772, 60.7167, "Star", 2.47, 0, "Gamma Cas"),
    # Cepheus
    ("Kurhah", 332.7137, 64.6279, "Star", 4.29, 0, "Xi Cep"),
    # Draco far north
    ("Kuma", 260.5018, 61.5142, "Star", 4.57, 0, "Nu Dra"),
    # Cygnus
    ("Ruchba", 296.2444, 45.1309, "Star", 2.87, 0, "Delta Cyg"),
    # Lyra
    ("Aladfar", 286.3536, 39.1458, "Star", 4.34, 0, "Eta Lyr"),
    # Hercules keystone
    ("Cujam", 265.2035, 31.6025, "Star", 4.41, 0, "Omega Her"),
    # Bootes
    ("Xuange", 222.7285, 51.7850, "Star", 4.18, 0, "Lambda Boo"),
    # Corona Borealis
    ("Nusakan", 231.9574, 29.1057, "Star", 3.68, 0, "Beta CrB"),
    # Serpens
    ("Alya", 284.0544, 4.2035, "Star", 4.62, 0, "Theta Ser"),
    # Aquila
    ("Deneb el Okab", 286.3526, 13.8634, "Star", 3.36, 0, "Zeta Aql"),
    ("Okab", 286.1725, 13.7265, "Star", 3.44, 0, "Epsilon Aql"),
    # Sagitta
    ("Sham", 295.0244, 18.0139, "Star", 4.37, 0, "Alpha Sge"),
    # Vulpecula
    ("Anser", 297.6322, 24.6648, "Star", 4.44, 0, "Alpha Vul"),
    # Perseus
    ("Miram", 55.7313, 48.4093, "Star", 4.04, 0, "Eta Per"),
    # Auriga
    ("Hassaleh", 74.2489, 33.1661, "Star", 2.69, 0, "Iota Aur"),
    ("Saclateni", 75.4923, 41.2346, "Star", 3.03, 0, "Zeta Aur"),
    ("Haedus", 75.6196, 41.0762, "Star", 3.17, 0, "Eta Aur"),
    ("Mahasim", 74.6370, 43.8232, "Star", 4.71, 0, "Theta Aur"),
    # Triangulum
    ("Mothallah", 28.2705, 29.5790, "Star", 3.41, 0, "Alpha Tri"),
    ("Deltotum", 32.3856, 34.9872, "Star", 3.00, 0, "Beta Tri"),
    # Pisces
    ("Alpherg", 21.4962, 15.3454, "Star", 3.62, 0, "Eta Psc"),
    ("Fumalsamakah", 22.8710, 3.8205, "Star", 4.52, 0, "Beta Psc"),
    # Cetus
    ("Menkar", 45.5700, 4.0897, "Star", 2.53, 0, "Alpha Cet"),
    ("Kaffaljidhma", 40.8254, 10.1142, "Star", 3.47, 0, "Gamma Cet"),
    ("Baten Kaitos", 27.8655, -10.3352, "Star", 3.74, 0, "Zeta Cet"),
    # Eridanus
    ("Cursa", 76.9625, -5.0864, "Star", 2.79, 0, "Beta Eri"),
    ("Zaurak", 59.5074, -13.5085, "Star", 2.95, 0, "Gamma Eri"),
    ("Rana", 53.2328, -9.4583, "Star", 3.54, 0, "Delta Eri"),
    ("Azha", 44.1066, -8.8983, "Star", 3.89, 0, "Eta Eri"),
    ("Zibal", 48.9589, -8.8200, "Star", 4.80, 0, "Zeta Eri"),
    # Orion additional
    ("Meissa", 83.7845, 9.9342, "Star", 3.33, 0, "Lambda Ori"),
    ("Tabit", 72.4600, 6.9614, "Star", 3.16, 0, "Pi3 Ori"),
    ("Hatsya", 83.8583, -5.9098, "Star", 2.77, 0, "Iota Ori"),
    # Monoceros
    ("Lucida", 99.1717, -7.0331, "Star", 3.93, 0, "Alpha Mon"),
    # Hydra
    ("Minchir", 126.4153, -3.9066, "Star", 3.82, 0, "Sigma Hya"),
    # Centaurus
    ("Rigil Kentaurus", 219.9021, -60.8340, "Star", -0.27, 0, "Alpha Cen"),
    ("Proxima Centauri", 217.4290, -62.6794, "Star", 11.13, 0, "Alpha Cen C"),
    # Crux
    ("Imai", 183.7863, -63.0989, "Star", 1.28, 0, "Delta Cru"),
    # Sagittarius
    ("Alnasl", 275.2485, -30.4241, "Star", 2.99, 0, "Gamma Sgr"),
    ("Kaus Borealis", 275.3255, -25.4217, "Star", 2.81, 0, "Lambda Sgr"),
    ("Arkab Prior", 290.6598, -44.7997, "Star", 3.96, 0, "Beta1 Sgr"),
    ("Rukbat", 290.9714, -40.6159, "Star", 3.97, 0, "Alpha Sgr"),
    # Scorpius additional
    ("Paikauhale", 265.6225, -37.0431, "Star", 3.32, 0, "Tau Sco"),
    ("Al Niyat", 244.5803, -25.5928, "Star", 2.89, 0, "Sigma Sco"),
    # Libra
    ("Brachium", 228.0720, -25.2818, "Star", 3.29, 0, "Sigma Lib"),
    # Lupus
    ("Men", 227.2080, -47.3880, "Star", 2.30, 0, "Alpha Lup"),
    # Ara
    ("Choo", 262.7748, -49.8764, "Star", 2.85, 0, "Beta Ara"),
    # Corona Australis
    ("Meridiana", 287.3681, -37.9045, "Star", 4.10, 0, "Alpha CrA"),
    # Piscis Austrinus
    ("Delta PsA", 339.2900, -32.5397, "Star", 4.20, 0, "Delta PsA"),
    # Sculptor
    ("Alpha Scl", 14.6608, -29.3573, "Star", 4.31, 0, "Alpha Scl"),
    # Fornax
    ("Dalim", 48.0188, -28.9836, "Star", 3.87, 0, "Alpha For"),
    # Columba
    ("Phact", 84.9121, -34.0741, "Star", 2.64, 0, "Alpha Col"),
    ("Wazn", 87.7400, -35.7683, "Star", 3.12, 0, "Beta Col"),
    # Lepus
    ("Arneb", 83.1826, -17.8224, "Star", 2.58, 0, "Alpha Lep"),
    ("Nihal", 82.0613, -20.7595, "Star", 2.84, 0, "Beta Lep"),
    # Puppis
    ("Naos", 120.8961, -40.0033, "Star", 2.25, 0, "Zeta Pup"),
    ("Azmidi", 105.9396, -23.8334, "Star", 3.34, 0, "Xi Pup"),
    # Vela
    ("Regor", 122.3831, -47.3367, "Star", 1.83, 0, "Gamma Vel"),
    ("Markeb", 138.3000, -55.0107, "Star", 2.50, 0, "Kappa Vel"),
]

# Sharpless HII regions — expanded with accurate positions and sizes
SHARPLESS_CATALOG = [
    ("Sh2-1", 244.2500, -24.8000, "HII", 10.0, 15.0, ""),
    ("Sh2-9", 247.7917, -10.5333, "HII", 5.0, 240.0, "Zeta Oph Nebula"),
    ("Sh2-11", 248.0625, -19.3167, "HII", 8.0, 30.0, ""),
    ("Sh2-25", 270.9042, -24.3833, "HII", 6.0, 90.0, "Lagoon Nebula"),
    ("Sh2-30", 270.6225, -23.0300, "HII", 6.3, 28.0, "Trifid Nebula"),
    ("Sh2-45", 274.7000, -13.7833, "HII", 6.0, 30.0, "Eagle Nebula region"),
    ("Sh2-49", 275.1917, -16.1708, "HII", 6.0, 46.0, "Omega Nebula region"),
    ("Sh2-54", 275.2000, -13.7833, "HII", 6.0, 30.0, ""),
    ("Sh2-71", 284.0833, 2.3167, "HII", 12.0, 4.0, ""),
    ("Sh2-82", 286.6875, 18.2667, "HII", 10.0, 8.0, "Little Cocoon Nebula"),
    ("Sh2-86", 289.0625, 24.7333, "HII", 7.0, 28.0, ""),
    ("Sh2-88", 290.8750, 25.2667, "HII", 10.0, 7.0, ""),
    ("Sh2-91", 291.6250, 29.0000, "HII", 10.0, 25.0, ""),
    ("Sh2-101", 299.2083, 35.2833, "HII", 8.0, 12.0, "Tulip Nebula"),
    ("Sh2-103", 303.0000, 40.0000, "HII", 5.0, 230.0, "Cygnus Loop"),
    ("Sh2-105", 303.0625, 38.3500, "HII", 7.4, 18.0, "Crescent Nebula"),
    ("Sh2-106", 303.7167, 37.4167, "HII", 11.0, 3.0, "Celestial Snow Angel"),
    ("Sh2-108", 306.4917, 40.1667, "HII", 5.0, 80.0, ""),
    ("Sh2-112", 316.7583, 45.6833, "HII", 8.0, 20.0, ""),
    ("Sh2-115", 317.7917, 48.5000, "HII", 10.0, 30.0, ""),
    ("Sh2-119", 313.0000, 45.0000, "HII", 4.0, 300.0, "Cygnus-X region"),
    ("Sh2-125", 316.7500, 43.9167, "HII", 8.0, 10.0, "Cocoon Nebula"),
    ("Sh2-126", 318.0000, 59.0000, "HII", 8.0, 80.0, ""),
    ("Sh2-129", 321.4583, 59.8833, "HII", 8.0, 190.0, "Flying Bat Nebula"),
    ("Sh2-131", 323.0000, 55.0000, "HII", 8.0, 120.0, ""),
    ("Sh2-132", 335.0417, 56.3833, "HII", 10.0, 40.0, "Lion Nebula"),
    ("Sh2-140", 345.0000, 62.0000, "HII", 10.0, 10.0, ""),
    ("Sh2-142", 350.2042, 61.2000, "HII", 10.0, 15.0, "Bubble Nebula"),
    ("Sh2-155", 352.3917, 62.6333, "HII", 7.7, 50.0, "Cave Nebula"),
    ("Sh2-157", 354.2917, 60.3000, "HII", 10.0, 40.0, "Lobster Claw Nebula"),
    ("Sh2-162", 356.0500, 60.5000, "HII", 8.0, 60.0, ""),
    ("Sh2-170", 0.0000, 67.4000, "HII", 12.0, 3.0, "Little Rosette Nebula"),
    ("Sh2-171", 0.2083, 67.8833, "HII", 8.0, 20.0, ""),
    ("Sh2-173", 3.0000, 61.0000, "HII", 10.0, 10.0, "Phantom of the Opera"),
    ("Sh2-184", 22.5000, 61.5000, "HII", 10.0, 20.0, "Pacman Nebula region"),
    ("Sh2-188", 25.0000, 58.5000, "HII", 12.0, 9.0, "Dolphin Nebula"),
    ("Sh2-190", 38.3333, 61.4667, "HII", 7.0, 150.0, "Heart Nebula"),
    ("Sh2-199", 43.3750, 62.0667, "HII", 7.0, 150.0, "Soul Nebula"),
    ("Sh2-202", 52.0000, 56.0000, "HII", 8.0, 250.0, ""),
    ("Sh2-216", 63.5000, 42.5833, "HII", 8.0, 100.0, ""),
    ("Sh2-220", 57.5000, 32.0000, "HII", 6.0, 330.0, "California Nebula region"),
    ("Sh2-224", 67.0000, 46.0000, "HII", 10.0, 100.0, ""),
    ("Sh2-229", 74.0000, 36.0000, "HII", 8.0, 100.0, "Flaming Star region"),
    ("Sh2-232", 83.1250, 36.1667, "HII", 10.0, 35.0, ""),
    ("Sh2-235", 84.7917, 35.8167, "HII", 10.0, 12.0, ""),
    ("Sh2-236", 82.0000, 34.0000, "HII", 8.0, 60.0, ""),
    ("Sh2-240", 85.0000, 28.0000, "HII", 8.0, 180.0, "Simeis 147"),
    ("Sh2-245", 86.5000, 25.0000, "HII", 8.0, 200.0, ""),
    ("Sh2-248", 88.0000, 21.0000, "HII", 10.0, 30.0, ""),
    ("Sh2-252", 92.2125, 20.4833, "HII", 6.8, 40.0, "Monkey Head Nebula"),
    ("Sh2-261", 93.2917, 13.7667, "HII", 10.0, 10.0, "Lower's Nebula"),
    ("Sh2-264", 87.0000, 2.0000, "HII", 4.0, 300.0, "Lambda Orionis Ring"),
    ("Sh2-273", 97.9667, 5.0333, "HII", 6.0, 80.0, "Rosette Nebula"),
    ("Sh2-275", 100.0000, 9.0000, "HII", 7.0, 60.0, "Cone Nebula region"),
    ("Sh2-276", 93.0000, -4.0000, "HII", 5.0, 480.0, "Barnard's Loop"),
    ("Sh2-277", 83.8000, -5.4000, "HII", 4.0, 100.0, "Orion Nebula region"),
    ("Sh2-278", 83.0000, -3.0000, "HII", 4.0, 210.0, ""),
    ("Sh2-301", 102.5000, -16.0000, "HII", 10.0, 10.0, ""),
    ("Sh2-308", 103.5500, -26.3500, "HII", 10.0, 40.0, "Dolphin Head Nebula"),
    ("Sh2-311", 108.5000, -15.0000, "HII", 10.0, 15.0, ""),
]

# Caldwell catalog — 109 objects selected by Patrick Moore
# Only objects NOT already in Messier are included.
CALDWELL_CATALOG = [
    ("C1", 11.3125, 85.3333, "OC", 8.1, 45.0, ""),
    ("C2", 11.3125, 72.5333, "OC", 6.4, 13.0, ""),
    ("C3", 19.7208, -75.3167, "Gal", 8.0, 25.0, ""),
    ("C4", 20.0000, 62.6333, "Neb", 9.0, 50.0, "Iris Nebula region"),
    ("C5", 351.2042, 68.1667, "RN", 7.1, 18.0, "IC 342"),
    ("C6", 350.2042, 61.2000, "Neb", 10.0, 15.0, "Cat's Paw Nebula"),
    ("C7", 352.3917, 62.6333, "Neb", 7.7, 50.0, ""),
    ("C8", 7.8583, 59.0167, "OC", 7.0, 18.0, ""),
    ("C9", 352.3917, 62.6333, "Neb", 10.0, 50.0, "Cave Nebula"),
    ("C10", 23.3417, 60.6583, "OC", 7.4, 6.0, ""),
    ("C11", 350.2042, 61.2000, "Neb", 10.0, 15.0, "Bubble Nebula"),
    ("C12", 314.6802, 44.3117, "Neb", 4.0, 120.0, ""),
    ("C13", 305.5572, 40.2567, "OC", 4.6, 60.0, "Owl Cluster"),
    ("C14", 34.7583, 57.1333, "OC", 5.3, 30.0, "Double Cluster h Per"),
    ("C15", 270.0000, -24.0000, "Neb", 6.0, 90.0, "Blinking Planetary"),
    ("C16", 2.9375, 72.2167, "OC", 3.5, 330.0, ""),
    ("C17", 19.7867, 60.7142, "OC", 6.4, 29.0, ""),
    ("C18", 21.0333, 61.2333, "OC", 5.7, 18.0, ""),
    ("C19", 315.3917, 68.1667, "RN", 7.1, 18.0, "Cocoon Nebula"),
    ("C20", 314.6802, 44.3117, "Neb", 4.0, 120.0, "North America Nebula"),
    ("C22", 296.2354, -14.8003, "Gal", 8.7, 20.0, "Blue Snowball"),
    ("C23", 346.8583, 57.5167, "OC", 5.7, 24.0, ""),
    ("C24", 0.8000, 61.3333, "OC", 7.9, 5.0, ""),
    ("C25", 329.2708, 60.4167, "OC", 8.2, 5.0, ""),
    ("C27", 303.0625, 38.3500, "Neb", 7.4, 18.0, "Crescent Nebula"),
    ("C28", 26.5583, 61.2333, "OC", 7.1, 16.0, ""),
    ("C30", 315.0000, 68.0000, "RN", 7.1, 18.0, ""),
    ("C31", 61.4833, 51.3167, "Neb", 10.0, 3.0, "Flaming Star Nebula"),
    ("C33", 313.9167, 31.7167, "SNR", 7.0, 60.0, "Eastern Veil Nebula"),
    ("C34", 312.1750, 30.7167, "SNR", 7.0, 70.0, "Western Veil Nebula"),
    ("C35", 116.0167, -37.9667, "OC", 2.8, 45.0, ""),
    ("C37", 119.5167, -60.7500, "OC", 3.8, 30.0, ""),
    ("C38", 253.5417, -41.8333, "OC", 2.6, 15.0, ""),
    ("C39", 296.2354, -14.8003, "Gal", 8.7, 20.0, "Eskimo Nebula"),
    ("C40", 187.7914, -57.1132, "OC", 4.0, 10.0, ""),
    ("C41", 107.6250, -26.5833, "OC", 4.5, 15.0, "Hyades"),
    ("C43", 258.0833, -37.1044, "PN", 7.1, 1.4, "Bug Nebula"),
    ("C44", 265.1755, -53.6744, "GC", 5.7, 32.0, ""),
    ("C45", 287.7170, -59.9847, "GC", 5.4, 29.0, ""),
    ("C46", 118.0458, -38.5333, "OC", 5.8, 27.0, ""),
    ("C47", 201.6968, -47.4797, "GC", 3.7, 36.0, "Omega Centauri"),
    ("C48", 194.8913, -70.8764, "GC", 6.9, 14.0, ""),
    ("C49", 193.4250, -60.3667, "OC", 4.2, 10.0, "Jewel Box Cluster"),
    ("C50", 174.7958, -61.6167, "OC", 5.3, 12.0, ""),
    ("C51", 150.6917, -60.0667, "OC", 4.2, 35.0, ""),
    ("C53", 166.4375, -58.7667, "OC", 3.0, 55.0, "Wishing Well Cluster"),
    ("C55", 262.9750, -67.0489, "GC", 7.6, 10.0, "Saturn Nebula"),
    ("C56", 156.1833, -18.6414, "PN", 7.3, 0.8, "Ghost of Jupiter"),
    ("C57", 151.7583, -40.4369, "PN", 8.2, 1.4, "Eight-Burst Nebula"),
    ("C58", 161.2542, -59.8667, "Neb", 3.0, 120.0, "Eta Carinae Nebula"),
    ("C59", 159.2625, -58.6333, "Neb", 6.7, 16.0, ""),
    ("C60", 207.4000, -47.5000, "Gal", 7.0, 23.0, "Antennae Galaxy"),
    ("C61", 157.8917, -58.2333, "OC", 4.7, 6.0, ""),
    ("C63", 337.4108, -20.8372, "PN", 7.6, 16.0, "Helix Nebula"),
    ("C64", 3.2000, -72.0814, "GC", 4.1, 50.0, "47 Tucanae"),
    ("C65", 11.8881, -25.2883, "Gal", 7.1, 27.5, "Sculptor Galaxy"),
    ("C67", 13.1867, -72.8286, "Gal", 2.3, 316.0, "Small Magellanic Cloud"),
    ("C69", 258.0833, -37.1044, "PN", 7.1, 1.4, ""),
    ("C71", 236.5125, -37.7864, "GC", 7.1, 10.0, ""),
    ("C72", 226.0583, -54.3500, "OC", 6.5, 40.0, ""),
    ("C73", 154.4034, -46.4116, "GC", 6.7, 18.0, ""),
    ("C74", 235.0000, -33.0000, "PN", 8.0, 0.5, ""),
    ("C76", 244.7583, -57.9333, "OC", 5.4, 12.0, ""),
    ("C77", 201.3651, -43.0191, "Gal", 6.8, 25.6, "Centaurus A"),
    ("C78", 204.2538, -29.8654, "Gal", 7.6, 12.9, ""),
    ("C79", 154.4034, -46.4116, "GC", 6.7, 18.0, ""),
    ("C80", 264.0718, -44.7356, "GC", 6.7, 10.0, ""),
    ("C82", 261.3714, -48.4222, "GC", 8.1, 7.0, ""),
    ("C84", 139.2725, -59.2753, "OC", 3.0, 50.0, ""),
    ("C85", 138.3000, -69.7172, "OC", 4.5, 50.0, ""),
    ("C86", 244.7583, -57.9333, "OC", 5.4, 12.0, ""),
    ("C87", 168.7917, -61.2500, "OC", 9.1, 12.0, ""),
    ("C89", 186.4400, -72.6592, "GC", 7.8, 19.0, ""),
    ("C91", 153.0000, -80.8611, "PN", 11.6, 0.6, ""),
    ("C92", 161.2542, -59.8667, "Neb", 3.0, 120.0, "Eta Carinae Nebula"),
    ("C93", 186.4400, -72.6592, "GC", 7.8, 19.0, ""),
    ("C94", 193.4250, -60.3667, "OC", 4.2, 10.0, ""),
    ("C96", 118.0458, -38.5333, "OC", 5.8, 27.0, ""),
    ("C98", 155.3375, -51.7167, "OC", 6.0, 18.0, ""),
    ("C99", 286.0000, -37.0000, "DN", 5.0, 30.0, "Coalsack Nebula"),
    ("C100", 261.3125, -23.7597, "PN", 11.4, 0.5, ""),
    ("C102", 6.0236, -72.0814, "GC", 4.1, 50.0, "47 Tucanae"),
    ("C103", 30.0000, -73.0000, "Neb", 5.0, 60.0, "Tarantula Nebula"),
    ("C106", 201.6968, -47.4797, "GC", 3.7, 36.0, ""),
    ("C109", 252.1662, -69.0277, "OC", 6.0, 12.0, ""),
]

# IC catalog — bright Index Catalogue objects popular for astrophotography
IC_BRIGHT_CATALOG = [
    ("IC 59", 14.1750, 61.1833, "RN", 10.0, 10.0, "Gamma Cas Nebula"),
    ("IC 63", 14.3000, 60.9333, "RN", 10.0, 10.0, "Ghost of Cassiopeia"),
    ("IC 342", 56.7042, 68.0958, "Gal", 9.1, 21.0, "Hidden Galaxy"),
    ("IC 405", 75.2500, 34.2667, "Neb", 6.0, 30.0, "Flaming Star Nebula"),
    ("IC 410", 77.3958, 33.3500, "Neb", 7.0, 40.0, "Tadpole Nebula"),
    ("IC 417", 78.1208, 34.4167, "Neb", 10.0, 13.0, "Spider Nebula"),
    ("IC 418", 81.8708, -12.6983, "PN", 9.3, 0.2, "Spirograph Nebula"),
    ("IC 434", 85.2500, -2.4500, "Neb", 7.3, 60.0, "Horsehead Nebula"),
    ("IC 443", 94.2542, 22.5333, "SNR", 12.0, 50.0, "Jellyfish Nebula"),
    ("IC 1275", 271.7500, -23.7167, "Neb", 10.0, 10.0, ""),
    ("IC 1284", 273.5750, -19.6833, "RN", 10.0, 20.0, ""),
    ("IC 1295", 281.3958, -29.1833, "PN", 12.7, 1.5, ""),
    ("IC 1318", 305.0000, 40.3333, "Neb", 7.0, 60.0, "Butterfly Nebula"),
    ("IC 1396", 324.7500, 57.5000, "Neb", 3.5, 170.0, "Elephant's Trunk Nebula"),
    ("IC 1613", 16.1992, 2.1178, "Gal", 9.2, 16.0, ""),
    ("IC 1795", 38.0208, 62.0000, "Neb", 7.0, 27.0, "Fishhead Nebula"),
    ("IC 1805", 38.2083, 61.4667, "Neb", 6.5, 60.0, "Heart Nebula"),
    ("IC 1848", 43.3750, 60.4333, "Neb", 6.5, 60.0, "Soul Nebula"),
    ("IC 1871", 47.2917, 60.2167, "Neb", 10.0, 8.0, ""),
    ("IC 2118", 77.7500, -7.2333, "RN", 10.0, 180.0, "Witch Head Nebula"),
    ("IC 2177", 103.7917, -10.4167, "Neb", 7.0, 120.0, "Seagull Nebula"),
    ("IC 2220", 114.7917, -62.0667, "RN", 10.0, 2.0, "Toby Jug Nebula"),
    ("IC 2391", 130.0542, -53.0333, "OC", 2.5, 50.0, "Omicron Vel Cluster"),
    ("IC 2395", 130.5750, -48.1333, "OC", 4.6, 20.0, ""),
    ("IC 2488", 141.8583, -56.9833, "OC", 7.4, 15.0, ""),
    ("IC 2574", 157.0853, 68.4121, "Gal", 10.8, 13.0, "Coddington's Nebula"),
    ("IC 2602", 160.7375, -64.4000, "OC", 1.9, 100.0, "Southern Pleiades"),
    ("IC 2944", 170.6250, -63.3833, "Neb", 4.5, 75.0, "Running Chicken Nebula"),
    ("IC 3568", 186.5833, 82.5653, "PN", 10.6, 0.3, "Lemon Slice Nebula"),
    ("IC 4406", 215.4875, -44.1617, "PN", 10.6, 1.6, "Retina Nebula"),
    ("IC 4592", 242.0000, -19.5000, "RN", 7.0, 90.0, "Blue Horsehead Nebula"),
    ("IC 4603", 243.5000, -19.5000, "RN", 10.0, 60.0, ""),
    ("IC 4604", 246.0833, -23.6000, "RN", 4.6, 60.0, "Rho Ophiuchi Nebula"),
    ("IC 4628", 254.5542, -40.3500, "Neb", 7.0, 90.0, "Prawn Nebula"),
    ("IC 4665", 266.5542, 5.6167, "OC", 4.2, 41.0, ""),
    ("IC 4703", 274.7000, -13.7833, "Neb", 6.0, 35.0, "Eagle Nebula cloud"),
    ("IC 4756", 279.6458, 5.4333, "OC", 4.6, 52.0, "Graff's Cluster"),
    ("IC 5067", 314.0000, 44.4000, "Neb", 8.0, 60.0, "Pelican Nebula"),
    ("IC 5070", 313.5000, 44.0000, "Neb", 8.0, 80.0, "Pelican Nebula"),
    ("IC 5146", 328.3917, 47.2667, "Neb", 7.2, 12.0, "Cocoon Nebula"),
    ("IC 5332", 354.7583, -36.1000, "Gal", 11.0, 7.0, ""),
]

# Barnard dark nebulae — the most prominent dark nebulae
BARNARD_CATALOG = [
    ("B33", 85.2708, -2.4583, "DN", 0.0, 6.0, "Horsehead Nebula"),
    ("B34", 85.0000, -2.5000, "DN", 0.0, 15.0, ""),
    ("B59", 258.0000, -27.2000, "DN", 0.0, 30.0, "Pipe Nebula stem"),
    ("B68", 262.5000, -23.9167, "DN", 0.0, 4.0, ""),
    ("B72", 262.0000, -23.5000, "DN", 0.0, 30.0, "Snake Nebula"),
    ("B77", 263.0000, -23.0000, "DN", 0.0, 60.0, "Pipe Nebula bowl"),
    ("B78", 264.5000, -25.7500, "DN", 0.0, 200.0, "Pipe Nebula"),
    ("B86", 272.1250, -27.8500, "DN", 0.0, 5.0, "Inkspot Nebula"),
    ("B87", 273.3750, -32.5000, "DN", 0.0, 12.0, ""),
    ("B88", 273.5000, -32.7500, "DN", 0.0, 20.0, ""),
    ("B92", 274.2500, -18.2500, "DN", 0.0, 15.0, ""),
    ("B93", 274.5000, -18.4167, "DN", 0.0, 10.0, ""),
    ("B133", 290.0000, -6.5000, "DN", 0.0, 10.0, ""),
    ("B142", 295.0000, 10.4167, "DN", 0.0, 40.0, "Barnard's E"),
    ("B143", 295.2500, 11.0833, "DN", 0.0, 30.0, "Barnard's E"),
    ("B150", 308.3750, 35.3333, "DN", 0.0, 15.0, "Seahorse Nebula"),
    ("B163", 319.0000, 52.0000, "DN", 0.0, 15.0, ""),
    ("B168", 314.7500, 44.0000, "DN", 0.0, 30.0, ""),
    ("B169", 315.0000, 44.5000, "DN", 0.0, 20.0, ""),
    ("B170", 318.0000, 52.0000, "DN", 0.0, 15.0, ""),
    ("B171", 320.0000, 55.0000, "DN", 0.0, 10.0, ""),
    ("B173", 321.5000, 60.5000, "DN", 0.0, 15.0, ""),
    ("B174", 322.0000, 60.0000, "DN", 0.0, 10.0, ""),
    ("B175", 323.0000, 59.0000, "DN", 0.0, 10.0, ""),
    ("B352", 297.0000, 24.0000, "DN", 0.0, 8.0, ""),
    ("B361", 311.0000, 36.0000, "DN", 0.0, 30.0, ""),
    ("B362", 312.0000, 37.0000, "DN", 0.0, 15.0, ""),
    ("B367", 317.0000, 42.0000, "DN", 0.0, 10.0, ""),
    ("LDN 1622", 86.0833, 1.8167, "DN", 0.0, 10.0, "Boogeyman Nebula"),
    ("LDN 1251", 340.0000, 75.0000, "DN", 0.0, 30.0, ""),
    ("LDN 1495", 63.5000, 28.0000, "DN", 0.0, 200.0, "Taurus Dark Cloud"),
    ("LDN 673", 286.5000, 11.0000, "DN", 0.0, 30.0, ""),
]


# ------------------------------------------------------------------------------
# COORDINATE UTILITIES
# ------------------------------------------------------------------------------

def degrees_to_hms(deg: float) -> str:
    """Convert degrees to RA hours:minutes:seconds string."""
    h = deg / 15.0
    hours = int(h)
    m = (h - hours) * 60
    minutes = int(m)
    seconds = (m - minutes) * 60
    return f"{hours:02d}h {minutes:02d}m {seconds:04.1f}s"


def degrees_to_dms(deg: float) -> str:
    """Convert degrees to DEC degrees:arcmin:arcsec string."""
    sign = "+" if deg >= 0 else "-"
    deg = abs(deg)
    d = int(deg)
    m = (deg - d) * 60
    minutes = int(m)
    seconds = (m - minutes) * 60
    return f"{sign}{d:02d}\u00b0 {minutes:02d}' {seconds:04.1f}\""


def choose_grid_step(fov_degrees: float) -> float:
    """Choose an appropriate grid line spacing in degrees for the given FOV."""
    steps = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 45.0]
    target_lines = 5  # aim for ~5 grid lines across the FOV
    ideal_step = fov_degrees / target_lines
    for step in steps:
        if step >= ideal_step:
            return step
    return steps[-1]


# ------------------------------------------------------------------------------
# CATALOG FILTERING
# ------------------------------------------------------------------------------

def filter_objects_in_fov(
    catalog: list[tuple],
    wcs: WCS | None,
    width: int,
    height: int,
    mag_limit: float = 15.0,
    margin: int = 30,
    siril=None,
    log_func=None,
) -> list[dict]:
    """
    Filter catalog objects to those visible in the image field of view.
    Uses siril.radec2pix() as primary method (like Galaxy_Annotations.py),
    falls back to astropy WCS if siril is not available.
    Returns list of dicts with pixel coordinates added.
    """
    visible = []

    # Strategy 1: Use siril.radec2pix() — most reliable, same as Galaxy_Annotations.py
    if siril is not None:
        for i, obj in enumerate(catalog):
            mag = obj[4]
            if mag > mag_limit:
                continue
            try:
                result = siril.radec2pix(obj[1], obj[2])
                if result is None:
                    continue
                x, y = result
                x, y = float(x), float(y)
            except Exception:
                continue
            if margin < x < width - margin and margin < y < height - margin:
                visible.append({
                    "name": obj[0],
                    "ra": obj[1],
                    "dec": obj[2],
                    "type": obj[3],
                    "mag": obj[4],
                    "size_arcmin": obj[5],
                    "common_name": obj[6],
                    "pixel_x": x,
                    "pixel_y": y,
                })
        if log_func and len(catalog) > 0:
            log_func(f"  filter: {len(visible)}/{len(catalog)} objects via radec2pix")
        return visible

    # Strategy 2: Fall back to astropy WCS
    if wcs is None:
        return visible

    ra_arr = np.array([obj[1] for obj in catalog])
    dec_arr = np.array([obj[2] for obj in catalog])

    try:
        pixel_coords = wcs.all_world2pix(np.column_stack([ra_arr, dec_arr]), 0)
    except Exception as e:
        if log_func:
            log_func(f"  filter: all_world2pix failed: {e}")
        return visible

    for i, obj in enumerate(catalog):
        x, y = float(pixel_coords[i][0]), float(pixel_coords[i][1])
        mag = obj[4]
        if mag > mag_limit:
            continue
        if margin < x < width - margin and margin < y < height - margin:
            visible.append({
                "name": obj[0],
                "ra": obj[1],
                "dec": obj[2],
                "type": obj[3],
                "mag": obj[4],
                "size_arcmin": obj[5],
                "common_name": obj[6],
                "pixel_x": x,
                "pixel_y": y,
            })
    if log_func and len(catalog) > 0:
        log_func(f"  filter: {len(visible)}/{len(catalog)} objects via astropy WCS")
    return visible


# ------------------------------------------------------------------------------
# LABEL COLLISION AVOIDANCE
# ------------------------------------------------------------------------------

def resolve_label_collisions(objects: list[dict], min_distance_px: int = 60) -> list[dict]:
    """
    Assign label offsets to avoid overlapping labels.
    Uses a greedy algorithm with 4 placement quadrants.
    """
    placements = [
        (15, 15),    # top-right
        (-15, 15),   # top-left
        (15, -15),   # bottom-right
        (-15, -15),  # bottom-left
        (25, 0),     # right
        (-25, 0),    # left
        (0, 25),     # above
        (0, -25),    # below
    ]
    placed: list[tuple[float, float]] = []

    for obj in objects:
        x, y = obj["pixel_x"], obj["pixel_y"]
        best_offset = placements[0]

        for offset_x, offset_y in placements:
            lx = x + offset_x
            ly = y + offset_y
            collision = False
            for px, py in placed:
                if abs(lx - px) < min_distance_px and abs(ly - py) < min_distance_px:
                    collision = True
                    break
            if not collision:
                best_offset = (offset_x, offset_y)
                break

        obj["label_offset_x"] = best_offset[0]
        obj["label_offset_y"] = best_offset[1]
        placed.append((x + best_offset[0], y + best_offset[1]))

    return objects


# ------------------------------------------------------------------------------
# RENDERING ENGINE (matplotlib)
# ------------------------------------------------------------------------------

def render_annotated_image(
    image_data: np.ndarray,
    objects: list[dict],
    wcs: WCS | None,
    config: dict,
    output_path: str,
    progress_callback=None,
) -> str:
    """
    Render the annotated image and save to disk.
    Returns the output file path.
    """
    dpi = config.get("dpi", 150)
    height, width = image_data.shape[:2]
    fig_w = width / dpi
    fig_h = height / dpi

    fig = Figure(figsize=(fig_w, fig_h), dpi=dpi, facecolor="black")
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])

    # Background image
    # sirilpy preview data is in display order (row 0 = top of image),
    # while radec2pix returns FITS coordinates (y=0 = bottom).
    # Use origin='upper' so the image displays correctly, then
    # flip y-coordinates of annotations: y_display = height - y_fits.
    ax.imshow(image_data, origin="upper", aspect="equal", interpolation="nearest")
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    # Flip y-coordinates from FITS (bottom-up) to display (top-down)
    for obj in objects:
        obj["pixel_y"] = height - obj["pixel_y"]

    if progress_callback:
        progress_callback(20, "Rendering object annotations...")

    # Compute pixel scale (arcsec/pixel)
    pixel_scale = config.get("pixel_scale_arcsec", 1.0)

    # Render object annotations
    total = len(objects)
    for idx, obj in enumerate(objects):
        _render_object(ax, obj, config, pixel_scale)
        if progress_callback and total > 0 and idx % max(1, total // 5) == 0:
            pct = 20 + int(40 * (idx + 1) / total)
            progress_callback(pct, f"Annotating {idx + 1}/{total} objects...")

    if progress_callback:
        progress_callback(65, "Rendering overlays...")

    # Coordinate grid
    if config.get("show_grid", False) and wcs is not None:
        _render_grid(ax, wcs, width, height, config)

    if progress_callback:
        progress_callback(75, "Rendering info box...")

    # Info box
    if config.get("show_info_box", True) and wcs is not None:
        _render_info_box(ax, wcs, width, height, config, len(objects))

    # Compass
    if config.get("show_compass", False) and wcs is not None:
        _render_compass(ax, wcs, width, height, config)

    # Color legend
    if config.get("show_legend", True) and len(objects) > 0:
        _render_legend(ax, width, height, objects, config)

    if progress_callback:
        progress_callback(85, "Saving output file...")

    # Save
    fig.savefig(output_path, dpi=dpi, facecolor="black", edgecolor="none")
    plt.close(fig)

    if progress_callback:
        progress_callback(100, "Done!")

    return output_path


def _render_object(ax, obj: dict, config: dict, pixel_scale: float) -> None:
    """Render marker + label for a single catalog object."""
    x, y = obj["pixel_x"], obj["pixel_y"]
    obj_type = obj.get("type", "Other")
    colors = config.get("colors", DEFAULT_COLORS)

    if config.get("color_by_type", True):
        color = colors.get(obj_type, colors.get("Other", "#CCCCCC"))
    else:
        color = colors.get(obj_type, "#CCCCCC")

    font_size = config.get("font_size", 10)
    marker_size = config.get("marker_size", 20)
    line_width = config.get("line_width", 1.5)

    # Marker: ellipse for extended objects, crosshair for point-like
    if config.get("show_ellipses", True) and obj.get("size_arcmin", 0) > 0 and pixel_scale > 0:
        size_px = obj["size_arcmin"] * 60.0 / pixel_scale
        size_px = max(size_px, marker_size * 0.6)
        ellipse = Ellipse(
            (x, y), size_px, size_px,
            fill=False, edgecolor=color, linewidth=line_width, alpha=0.8,
        )
        ax.add_patch(ellipse)
    else:
        # Crosshair marker
        half = marker_size * 0.3
        ax.plot([x - half, x + half], [y, y], "-", color=color,
                linewidth=line_width, alpha=0.8)
        ax.plot([x, x], [y - half, y + half], "-", color=color,
                linewidth=line_width, alpha=0.8)

    # Label
    label_parts = []
    name = obj["name"]
    common = obj.get("common_name", "")
    if common and config.get("show_common_names", True):
        label_parts.append(f"{name} ({common})")
    else:
        label_parts.append(name)

    if config.get("show_magnitude", False) and obj.get("mag", 0) != 0:
        label_parts[0] += f"  {obj['mag']:.1f}m"

    if config.get("show_type_label", False):
        type_label = OBJECT_TYPE_LABELS.get(obj_type, obj_type)
        label_parts[0] += f"  [{type_label}]"

    label = label_parts[0]
    offset_x = obj.get("label_offset_x", 15)
    offset_y = obj.get("label_offset_y", 15)

    ha = "left" if offset_x >= 0 else "right"
    va = "bottom" if offset_y >= 0 else "top"

    # Leader line: thin line connecting object position to label
    if config.get("show_leader_lines", True):
        leader_len = math.hypot(offset_x, offset_y)
        if leader_len > 10:  # only draw if label is actually offset
            ax.plot(
                [x, x + offset_x * 0.7], [y, y + offset_y * 0.7],
                "-", color=color, linewidth=0.6, alpha=0.5,
                path_effects=[pe.withStroke(linewidth=1.5, foreground="black")],
            )

    ax.text(
        x + offset_x, y + offset_y,
        label, fontsize=font_size, color=color, fontweight="bold",
        ha=ha, va=va,
        path_effects=[
            pe.withStroke(linewidth=2.5, foreground="black"),
        ],
    )


def _render_grid(ax, wcs: WCS, width: int, height: int, config: dict) -> None:
    """Render RA/DEC coordinate grid overlay."""
    grid_color = config.get("grid_color", "#4466AA")
    grid_alpha = config.get("grid_alpha", 0.4)
    label_size = config.get("grid_label_size", 7)

    # Get FOV corners in world coordinates
    corners_pix = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=float)
    try:
        corners_wcs = wcs.all_pix2world(corners_pix, 0)
    except Exception:
        return

    ra_min, ra_max = corners_wcs[:, 0].min(), corners_wcs[:, 0].max()
    dec_min, dec_max = corners_wcs[:, 1].min(), corners_wcs[:, 1].max()

    # Handle RA wrap-around
    if ra_max - ra_min > 180:
        ras = corners_wcs[:, 0]
        ras[ras > 180] -= 360
        ra_min, ra_max = ras.min(), ras.max()

    fov_size = max(ra_max - ra_min, dec_max - dec_min)
    grid_step = choose_grid_step(fov_size)

    # RA lines
    ra_start = np.floor(ra_min / grid_step) * grid_step
    ra_end = np.ceil(ra_max / grid_step) * grid_step + grid_step
    for ra in np.arange(ra_start, ra_end, grid_step):
        dec_range = np.linspace(dec_min - 1, dec_max + 1, 200)
        ra_arr = np.full_like(dec_range, ra)
        try:
            pixels = wcs.all_world2pix(np.column_stack([ra_arr, dec_range]), 0)
        except Exception:
            continue
        x_px, y_px = pixels[:, 0], pixels[:, 1]
        mask = (x_px >= 0) & (x_px < width) & (y_px >= 0) & (y_px < height)
        if np.any(mask):
            ax.plot(x_px[mask], y_px[mask], "-", color=grid_color,
                    alpha=grid_alpha, linewidth=0.5)
            # Label at first visible point
            idx = np.where(mask)[0][0]
            ra_label = degrees_to_hms(ra % 360)
            ax.text(
                x_px[idx], y_px[idx] + 8, ra_label,
                fontsize=label_size, color=grid_color, alpha=grid_alpha + 0.2,
                ha="center", va="bottom",
                path_effects=[pe.withStroke(linewidth=1.5, foreground="black")],
            )

    # DEC lines
    dec_start = np.floor(dec_min / grid_step) * grid_step
    dec_end = np.ceil(dec_max / grid_step) * grid_step + grid_step
    for dec in np.arange(dec_start, dec_end, grid_step):
        if dec < -90 or dec > 90:
            continue
        ra_range = np.linspace(ra_min - 1, ra_max + 1, 200)
        dec_arr = np.full_like(ra_range, dec)
        try:
            pixels = wcs.all_world2pix(np.column_stack([ra_range, dec_arr]), 0)
        except Exception:
            continue
        x_px, y_px = pixels[:, 0], pixels[:, 1]
        mask = (x_px >= 0) & (x_px < width) & (y_px >= 0) & (y_px < height)
        if np.any(mask):
            ax.plot(x_px[mask], y_px[mask], "-", color=grid_color,
                    alpha=grid_alpha, linewidth=0.5)
            idx = np.where(mask)[0][0]
            dec_label = degrees_to_dms(dec)
            ax.text(
                x_px[idx] + 8, y_px[idx], dec_label,
                fontsize=label_size, color=grid_color, alpha=grid_alpha + 0.2,
                ha="left", va="center",
                path_effects=[pe.withStroke(linewidth=1.5, foreground="black")],
            )


def _render_info_box(
    ax, wcs: WCS, width: int, height: int, config: dict, n_objects: int,
) -> None:
    """Render an info box with field metadata in a corner."""
    try:
        center_coords = wcs.all_pix2world([[width / 2, height / 2]], 0)[0]
        center_ra, center_dec = center_coords

        corner1 = wcs.all_pix2world([[0, 0]], 0)[0]
        corner2 = wcs.all_pix2world([[width, height]], 0)[0]
        fov_w = abs(corner2[0] - corner1[0]) * np.cos(np.radians(center_dec))
        fov_h = abs(corner2[1] - corner1[1])

        pixel_scale = config.get("pixel_scale_arcsec", 0)

        # Rotation from CD matrix
        rotation = 0.0
        if hasattr(wcs.wcs, "cd") and wcs.wcs.cd is not None:
            cd = wcs.wcs.cd
            rotation = np.degrees(np.arctan2(cd[0, 1], cd[0, 0]))
    except Exception:
        return

    info_lines = []
    obj_name = config.get("object_name", "")
    if obj_name:
        info_lines.append(obj_name)

    info_lines.extend([
        f"Center: {degrees_to_hms(center_ra)}  {degrees_to_dms(center_dec)}",
        f"FOV: {fov_w * 60:.1f}' \u00d7 {fov_h * 60:.1f}'",
    ])
    if pixel_scale > 0:
        info_lines.append(f"Scale: {pixel_scale:.2f}\"/px")
    info_lines.append(f"Rotation: {rotation:.1f}\u00b0")
    info_lines.append(f"Objects annotated: {n_objects}")

    info_text = "\n".join(info_lines)

    ax.text(
        width * 0.02, height * 0.98, info_text,
        fontsize=9, color="white", fontfamily="monospace",
        va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="black", alpha=0.6),
        path_effects=[pe.withStroke(linewidth=1, foreground="black")],
    )


def _render_legend(ax, width: int, height: int, objects: list[dict], config: dict) -> None:
    """Render a color legend box showing which types are present in the annotation."""
    colors = config.get("colors", DEFAULT_COLORS)

    # Collect unique types actually present in the annotated objects
    present_types = {}
    for obj in objects:
        t = obj.get("type", "Other")
        if t not in present_types:
            present_types[t] = OBJECT_TYPE_LABELS.get(t, t)

    if not present_types:
        return

    # Sort by the order defined in DEFAULT_COLORS
    type_order = list(DEFAULT_COLORS.keys())
    sorted_types = sorted(
        present_types.items(),
        key=lambda kv: type_order.index(kv[0]) if kv[0] in type_order else 99,
    )

    # Build legend text lines
    font_size = max(7, config.get("font_size", 10) - 2)
    line_height = font_size * 1.8
    padding = 8
    box_w = 14  # color swatch width

    # Position: bottom-left corner (opposite to info box which is top-left)
    x_base = width * 0.02
    y_base = height * 0.02

    # Background box
    total_h = len(sorted_types) * line_height + padding * 2 + font_size
    total_w = 180  # approximate width

    from matplotlib.patches import FancyBboxPatch
    bg = FancyBboxPatch(
        (x_base - padding, y_base - padding),
        total_w + padding * 2, total_h,
        boxstyle="round,pad=4", facecolor="black", alpha=0.6,
        edgecolor="none",
    )
    ax.add_patch(bg)

    # Title
    ax.text(
        x_base + total_w / 2, y_base + total_h - padding - font_size * 0.5,
        "Legend", fontsize=font_size, color="white", fontweight="bold",
        ha="center", va="top",
        path_effects=[pe.withStroke(linewidth=1, foreground="black")],
    )

    # Legend entries
    for i, (type_key, type_label) in enumerate(sorted_types):
        color = colors.get(type_key, "#CCCCCC")
        y_pos = y_base + total_h - padding - font_size * 2.2 - i * line_height

        # Color swatch
        swatch = FancyBboxPatch(
            (x_base, y_pos - font_size * 0.3),
            box_w, font_size * 0.8,
            boxstyle="round,pad=1", facecolor=color, alpha=0.9,
            edgecolor="none",
        )
        ax.add_patch(swatch)

        # Label text
        ax.text(
            x_base + box_w + 6, y_pos,
            type_label, fontsize=font_size - 1, color="white",
            ha="left", va="center",
            path_effects=[pe.withStroke(linewidth=1, foreground="black")],
        )


def _render_compass(ax, wcs: WCS, width: int, height: int, config: dict) -> None:
    """Render N/E compass arrows in the corner."""
    # Place compass in bottom-right corner
    cx = width * 0.92
    cy = height * 0.08
    arrow_len = min(width, height) * 0.05

    try:
        # Get the direction of North and East at the compass position
        ra0, dec0 = wcs.all_pix2world([[cx, cy]], 0)[0]

        # North direction: increase DEC slightly
        delta = 0.01  # degrees
        x_n, y_n = wcs.all_world2pix([[ra0, dec0 + delta]], 0)[0]
        dx_n = x_n - cx
        dy_n = y_n - cy
        norm_n = math.hypot(dx_n, dy_n)
        if norm_n > 0:
            dx_n, dy_n = dx_n / norm_n * arrow_len, dy_n / norm_n * arrow_len

        # East direction: decrease RA slightly (RA increases to the East)
        x_e, y_e = wcs.all_world2pix([[ra0 - delta, dec0]], 0)[0]
        dx_e = x_e - cx
        dy_e = y_e - cy
        norm_e = math.hypot(dx_e, dy_e)
        if norm_e > 0:
            dx_e, dy_e = dx_e / norm_e * arrow_len, dy_e / norm_e * arrow_len
    except Exception:
        return

    compass_color = config.get("compass_color", "#88AAFF")

    # North arrow
    ax.annotate(
        "N", (cx + dx_n, cy + dy_n),
        xytext=(cx, cy),
        fontsize=10, fontweight="bold", color=compass_color,
        ha="center", va="center",
        arrowprops=dict(arrowstyle="->", color=compass_color, lw=2),
        path_effects=[pe.withStroke(linewidth=2, foreground="black")],
    )

    # East arrow
    ax.annotate(
        "E", (cx + dx_e, cy + dy_e),
        xytext=(cx, cy),
        fontsize=10, fontweight="bold", color=compass_color,
        ha="center", va="center",
        arrowprops=dict(arrowstyle="->", color=compass_color, lw=2),
        path_effects=[pe.withStroke(linewidth=2, foreground="black")],
    )


# ------------------------------------------------------------------------------
# WCS EXTRACTION
# ------------------------------------------------------------------------------

def extract_wcs_from_header(header_str: str) -> WCS | None:
    """Parse a FITS header string into an astropy WCS object."""
    if not header_str:
        return None
    try:
        hdr = astropy_fits.Header.fromstring(header_str, sep="\n")
        wcs = WCS(hdr)
        if wcs.has_celestial:
            return wcs
    except Exception:
        pass
    # Fallback: try parsing as 80-char FITS card images
    try:
        hdr = astropy_fits.Header.fromstring(header_str)
        wcs = WCS(hdr)
        if wcs.has_celestial:
            return wcs
    except Exception:
        pass
    return None


def extract_wcs_from_fits_file(siril, log_func=None) -> WCS | None:
    """
    Try to read WCS from the actual FITS file on disk.
    Fallback when header string parsing fails.
    """
    def _log(msg: str) -> None:
        if log_func:
            log_func(msg)

    # Strategy A: Use get_image_filename() to find the exact file
    fits_candidates = []
    try:
        img_filename = siril.get_image_filename()
        if img_filename:
            _log(f"WCS disk: image filename = {img_filename}")
            # get_image_filename may return just basename or full path
            if os.path.isfile(img_filename):
                fits_candidates.append(img_filename)
            else:
                # Try combining with working directory
                try:
                    wd = siril.get_siril_wd()
                    if wd:
                        # Siril may omit extension, try common ones
                        base = img_filename
                        for ext in ("", ".fit", ".fits", ".fts"):
                            candidate = os.path.join(wd, base + ext)
                            if os.path.isfile(candidate):
                                fits_candidates.append(candidate)
                                break
                except Exception:
                    pass
    except Exception as e:
        _log(f"WCS disk: get_image_filename() failed: {e}")

    # Strategy B: Scan working directory for FITS files
    if not fits_candidates:
        try:
            wd = siril.get_siril_wd()
            if not wd:
                wd = os.getcwd()
        except Exception:
            wd = os.getcwd()

        _log(f"WCS disk: scanning {wd}")
        try:
            for f in os.listdir(wd):
                if f.lower().endswith((".fit", ".fits", ".fts")):
                    fits_candidates.append(os.path.join(wd, f))
        except OSError:
            return None

        # Use most recently modified
        fits_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    if not fits_candidates:
        _log("WCS disk: no FITS files found")
        return None

    _log(f"WCS disk: trying {len(fits_candidates)} file(s)")

    for fits_path in fits_candidates[:5]:
        try:
            with astropy_fits.open(fits_path) as hdul:
                header = hdul[0].header
                if "CRVAL1" in header and "CRVAL2" in header:
                    wcs = WCS(header)
                    if wcs.has_celestial:
                        _log(f"WCS disk: success from {os.path.basename(fits_path)}")
                        return wcs
                else:
                    _log(f"WCS disk: {os.path.basename(fits_path)} has no CRVAL1/CRVAL2")
        except Exception as e:
            _log(f"WCS disk: {os.path.basename(fits_path)} failed: {e}")
            continue

    return None


def compute_pixel_scale(wcs: WCS) -> float:
    """Compute pixel scale in arcsec/pixel from WCS."""
    try:
        if hasattr(wcs.wcs, "cd") and wcs.wcs.cd is not None:
            cd = wcs.wcs.cd
            scale1 = math.hypot(cd[0, 0], cd[0, 1]) * 3600.0
            scale2 = math.hypot(cd[1, 0], cd[1, 1]) * 3600.0
            return (scale1 + scale2) / 2.0
        elif hasattr(wcs.wcs, "cdelt") and wcs.wcs.cdelt is not None:
            return abs(wcs.wcs.cdelt[0]) * 3600.0
    except Exception:
        pass
    return 1.0


# ------------------------------------------------------------------------------
# PREVIEW WIDGET
# ------------------------------------------------------------------------------

class PreviewWidget(QLabel):
    """Shows a scaled preview of the annotated output image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setText("Preview will appear here after annotation.")
        self.setStyleSheet("color: #888888; font-size: 11pt; border: 1px dashed #555555;")
        self._pixmap = None

    def set_image(self, path: str) -> None:
        """Load and display the annotated image from file."""
        from PyQt6.QtGui import QPixmap
        pix = QPixmap(path)
        if not pix.isNull():
            self._pixmap = pix
            scaled = pix.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.setStyleSheet("border: 1px solid #555555;")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pixmap is not None:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)


# ------------------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------------------

class AnnotateImageWindow(QMainWindow):
    """
    Main window for the Annotate Image script.

    Left panel: configuration controls (catalogs, display, extras, output).
    Right panel: image preview and status log.
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
        self._last_output_path = ""
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.init_ui()
        self._load_settings()
        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self, self._on_annotate)

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
        lbl = QLabel(f"Svenesis Annotate Image {VERSION}")
        lbl.setStyleSheet("font-size: 15pt; font-weight: bold; color: #88aaff; margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_catalogs_group(layout)
        self._build_display_group(layout)
        self._build_extras_group(layout)
        self._build_output_group(layout)
        self._build_action_buttons(layout)

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

    def _build_catalogs_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Annotate Objects")
        layout = QVBoxLayout(group)

        # Object type checkboxes — matching the color coding scheme
        self._type_checkboxes: dict[str, QCheckBox] = {}
        type_defs = [
            ("Gal", "Galaxies", "#FFD700", True,
             "Galaxies from all catalogs (Messier, NGC, IC, Caldwell, SIMBAD).\n"
             "Shown in gold."),
            ("Neb", "Emission Nebulae", "#FF4444", True,
             "Emission nebulae (HII regions, star-forming regions).\n"
             "Includes Orion, Lagoon, Eagle, Rosette, etc. Shown in red."),
            ("RN", "Reflection Nebulae", "#FF8888", True,
             "Reflection nebulae (dust clouds illuminated by nearby stars).\n"
             "Includes M78, Witch Head, Iris Nebula, etc. Shown in light red."),
            ("PN", "Planetary Nebulae", "#44FF44", True,
             "Planetary nebulae (dying star shells).\n"
             "Includes Ring, Dumbbell, Helix, Owl, etc. Shown in green."),
            ("OC", "Open Clusters", "#44AAFF", True,
             "Open star clusters.\n"
             "Includes Pleiades, Double Cluster, Wild Duck, etc. Shown in blue."),
            ("GC", "Globular Clusters", "#FF8800", True,
             "Globular star clusters.\n"
             "Includes M13, Omega Centauri, 47 Tucanae, etc. Shown in orange."),
            ("SNR", "Supernova Remnants", "#FF44FF", True,
             "Supernova remnants.\n"
             "Includes Crab Nebula, Veil Nebula, Simeis 147, etc. Shown in magenta."),
            ("DN", "Dark Nebulae", "#888888", False,
             "Dark nebulae (opaque dust clouds).\n"
             "Includes Horsehead, Pipe, Snake, Barnard's E, Coalsack.\n"
             "No magnitude — always shown regardless of mag limit. Shown in grey."),
            ("HII", "HII Regions", "#FF6666", False,
             "HII ionized hydrogen regions (Sharpless catalog).\n"
             "Large emission complexes: Heart, Soul, Barnard's Loop, etc.\n"
             "Best for wide-field Milky Way images. Shown in red-pink."),
            ("Star", "Named Stars", "#FFFFFF", True,
             "~300 IAU-named and Bayer-designated stars to magnitude ~5.5.\n"
             "Full-sky coverage for field identification. Shown in white."),
        ]

        for type_key, label, color, default_on, tooltip in type_defs:
            chk = QCheckBox(f"  {label}")
            chk.setChecked(default_on)
            chk.setToolTip(tooltip)
            chk.setStyleSheet(
                f"QCheckBox{{color:{color};spacing:5px}}"
                f"QCheckBox::indicator{{width:14px;height:14px;border:1px solid #666;"
                f"background:#3c3c3c;border-radius:3px}}"
                f"QCheckBox::indicator:checked{{background:{color};border:1px solid {color}}}"
            )
            _nofocus(chk)
            layout.addWidget(chk)
            self._type_checkboxes[type_key] = chk

        # Separator
        sep = QLabel("")
        sep.setFixedHeight(4)
        layout.addWidget(sep)

        # SIMBAD online option
        self.chk_simbad = QCheckBox("  SIMBAD online (additional objects)")
        self.chk_simbad.setChecked(False)
        self.chk_simbad.setToolTip(
            "Query the SIMBAD astronomical database online for additional objects\n"
            "not found in the embedded catalogs (UGC, MCG, PGC, Abell, etc.).\n\n"
            "Requires internet connection and the 'astroquery' package.\n"
            "Found objects are filtered by the type checkboxes above."
        )
        self.chk_simbad.setStyleSheet(
            "QCheckBox{color:#AADDFF;spacing:5px}"
            "QCheckBox::indicator{width:14px;height:14px;border:1px solid #666;"
            "background:#3c3c3c;border-radius:3px}"
            "QCheckBox::indicator:checked{background:#AADDFF;border:1px solid #AADDFF}"
        )
        _nofocus(self.chk_simbad)
        layout.addWidget(self.chk_simbad)

        # Select All / Deselect All buttons
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
        layout.addLayout(btn_row)

        parent_layout.addWidget(group)

    def _set_all_types(self, state: bool) -> None:
        """Set all object type checkboxes to the given state."""
        for chk in self._type_checkboxes.values():
            chk.setChecked(state)

    def _build_display_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Display")
        grid = QGridLayout(group)
        grid.setColumnMinimumWidth(0, 100)
        grid.setColumnMinimumWidth(1, 60)
        grid.setColumnStretch(2, 1)

        # Font size
        row = 0
        lbl = QLabel("Font size:")
        lbl.setFixedWidth(100)
        grid.addWidget(lbl, row, 0)
        self.spin_font = QSpinBox()
        self.spin_font.setRange(6, 24)
        self.spin_font.setValue(10)
        self.spin_font.setFixedWidth(60)
        _nofocus(self.spin_font)
        grid.addWidget(self.spin_font, row, 1)
        self.slider_font = QSlider(Qt.Orientation.Horizontal)
        self.slider_font.setRange(6, 24)
        self.slider_font.setValue(10)
        _nofocus(self.slider_font)
        grid.addWidget(self.slider_font, row, 2)
        self.spin_font.valueChanged.connect(self.slider_font.setValue)
        self.slider_font.valueChanged.connect(self.spin_font.setValue)

        # Marker size
        row = 1
        lbl = QLabel("Marker size:")
        lbl.setFixedWidth(100)
        grid.addWidget(lbl, row, 0)
        self.spin_marker = QSpinBox()
        self.spin_marker.setRange(8, 60)
        self.spin_marker.setValue(20)
        self.spin_marker.setFixedWidth(60)
        _nofocus(self.spin_marker)
        grid.addWidget(self.spin_marker, row, 1)
        self.slider_marker = QSlider(Qt.Orientation.Horizontal)
        self.slider_marker.setRange(8, 60)
        self.slider_marker.setValue(20)
        _nofocus(self.slider_marker)
        grid.addWidget(self.slider_marker, row, 2)
        self.spin_marker.valueChanged.connect(self.slider_marker.setValue)
        self.slider_marker.valueChanged.connect(self.spin_marker.setValue)

        # Magnitude limit
        row = 2
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
            "Only annotate objects brighter than this magnitude.\n"
            "Lower values = fewer, brighter objects only.\n"
            "12.0 is a good default for most wide-field images."
        )
        _nofocus(self.spin_mag)
        grid.addWidget(self.spin_mag, row, 1)
        self.slider_mag = QSlider(Qt.Orientation.Horizontal)
        self.slider_mag.setRange(10, 200)  # *10 for 1.0-20.0
        self.slider_mag.setValue(120)
        _nofocus(self.slider_mag)
        grid.addWidget(self.slider_mag, row, 2)
        self.spin_mag.valueChanged.connect(lambda v: self.slider_mag.setValue(int(v * 10)))
        self.slider_mag.valueChanged.connect(lambda v: self.spin_mag.setValue(v / 10.0))

        # Checkboxes
        row = 3
        self.chk_ellipses = QCheckBox("Show object size as ellipse")
        self.chk_ellipses.setChecked(True)
        self.chk_ellipses.setToolTip(
            "Draw ellipses proportional to the cataloged angular size.\n"
            "Disable for a cleaner look with crosshair markers only."
        )
        _nofocus(self.chk_ellipses)
        grid.addWidget(self.chk_ellipses, row, 0, 1, 3)

        row = 4
        self.chk_magnitude = QCheckBox("Show magnitude in label")
        self.chk_magnitude.setChecked(False)
        self.chk_magnitude.setToolTip("Append the visual magnitude to each label (e.g. 'M31 3.4m').")
        _nofocus(self.chk_magnitude)
        grid.addWidget(self.chk_magnitude, row, 0, 1, 3)

        row = 5
        self.chk_type_label = QCheckBox("Show object type in label")
        self.chk_type_label.setChecked(False)
        self.chk_type_label.setToolTip("Append the object type to each label (e.g. 'M31 [Galaxy]').")
        _nofocus(self.chk_type_label)
        grid.addWidget(self.chk_type_label, row, 0, 1, 3)

        row = 6
        self.chk_common_names = QCheckBox("Show common names")
        self.chk_common_names.setChecked(True)
        self.chk_common_names.setToolTip(
            "Show common names where available (e.g. 'M31 (Andromeda Galaxy)').\n"
            "Disable for a more compact display."
        )
        _nofocus(self.chk_common_names)
        grid.addWidget(self.chk_common_names, row, 0, 1, 3)

        row = 7
        self.chk_color_by_type = QCheckBox("Color by object type")
        self.chk_color_by_type.setChecked(True)
        self.chk_color_by_type.setToolTip(
            "Use different colors for different object types:\n"
            "Gold = Galaxies, Red = Nebulae, Green = Planetary Nebulae,\n"
            "Blue = Open Clusters, Orange = Globular Clusters, etc."
        )
        _nofocus(self.chk_color_by_type)
        grid.addWidget(self.chk_color_by_type, row, 0, 1, 3)

        parent_layout.addWidget(group)

    def _build_extras_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Extras")
        layout = QVBoxLayout(group)

        self.chk_grid = QCheckBox("Coordinate grid (RA/DEC)")
        self.chk_grid.setChecked(True)
        self.chk_grid.setToolTip(
            "Overlay an equatorial coordinate grid with RA/DEC labels.\n"
            "Grid spacing is chosen automatically based on the field of view."
        )
        _nofocus(self.chk_grid)
        layout.addWidget(self.chk_grid)

        self.chk_info_box = QCheckBox("Info box (center, FOV, scale)")
        self.chk_info_box.setChecked(True)
        self.chk_info_box.setToolTip(
            "Show a semi-transparent info box with:\n"
            "- Center RA/DEC coordinates\n"
            "- Field of view dimensions\n"
            "- Pixel scale and rotation angle\n"
            "- Number of annotated objects"
        )
        _nofocus(self.chk_info_box)
        layout.addWidget(self.chk_info_box)

        self.chk_compass = QCheckBox("Compass (N/E arrows)")
        self.chk_compass.setChecked(False)
        self.chk_compass.setToolTip(
            "Show North and East direction arrows in the corner.\n"
            "Useful for understanding image orientation."
        )
        _nofocus(self.chk_compass)
        layout.addWidget(self.chk_compass)

        self.chk_legend = QCheckBox("Color legend")
        self.chk_legend.setChecked(True)
        self.chk_legend.setToolTip(
            "Show a color legend box explaining what each annotation color means.\n"
            "Only shows types that are actually present in the annotated image.\n"
            "Placed in the bottom-left corner."
        )
        _nofocus(self.chk_legend)
        layout.addWidget(self.chk_legend)

        self.chk_leader_lines = QCheckBox("Leader lines (label to object)")
        self.chk_leader_lines.setChecked(True)
        self.chk_leader_lines.setToolTip(
            "Draw thin connecting lines from each label to its object marker.\n"
            "Essential in crowded fields to see which label belongs to which object.\n"
            "Disable for a cleaner look on sparse fields."
        )
        _nofocus(self.chk_leader_lines)
        layout.addWidget(self.chk_leader_lines)

        parent_layout.addWidget(group)

    def _build_output_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        # Format radio buttons
        fmt_layout = QHBoxLayout()
        fmt_label = QLabel("Format:")
        fmt_layout.addWidget(fmt_label)
        self.radio_png = QRadioButton("PNG")
        self.radio_png.setChecked(True)
        _nofocus(self.radio_png)
        self.radio_tiff = QRadioButton("TIFF")
        _nofocus(self.radio_tiff)
        self.radio_jpeg = QRadioButton("JPEG")
        _nofocus(self.radio_jpeg)
        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.radio_png)
        self.format_group.addButton(self.radio_tiff)
        self.format_group.addButton(self.radio_jpeg)
        fmt_layout.addWidget(self.radio_png)
        fmt_layout.addWidget(self.radio_tiff)
        fmt_layout.addWidget(self.radio_jpeg)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        # DPI
        dpi_layout = QHBoxLayout()
        dpi_label = QLabel("DPI:")
        dpi_label.setFixedWidth(100)
        dpi_layout.addWidget(dpi_label)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 300)
        self.spin_dpi.setValue(150)
        self.spin_dpi.setFixedWidth(60)
        self.spin_dpi.setToolTip("Output resolution. Higher = larger file.\n150 is good for screens, 300 for print.")
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

        # Filename
        name_layout = QHBoxLayout()
        name_label = QLabel("Filename:")
        name_label.setFixedWidth(100)
        name_layout.addWidget(name_label)
        self.edit_filename = QLineEdit("annotated")
        self.edit_filename.setToolTip(
            "Base filename for the output (without extension).\n"
            "A timestamp will be appended automatically."
        )
        name_layout.addWidget(self.edit_filename)
        layout.addLayout(name_layout)

        parent_layout.addWidget(group)

    def _build_action_buttons(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)

        self.btn_annotate = QPushButton("Annotate Image")
        self.btn_annotate.setObjectName("AnnotateButton")
        self.btn_annotate.setToolTip("Annotate the current image and export (F5)")
        _nofocus(self.btn_annotate)
        self.btn_annotate.clicked.connect(self._on_annotate)
        layout.addWidget(self.btn_annotate)

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

        # Image info bar
        self.lbl_image_info = QLabel("No image loaded")
        self.lbl_image_info.setStyleSheet(
            "font-size: 10pt; color: #aaaaaa; padding: 4px; "
            "background-color: #333333; border-radius: 4px;"
        )
        self.lbl_image_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(self.lbl_image_info)

        # Tab widget for preview and log
        self.tabs = QTabWidget()

        # Preview tab
        self.preview_widget = PreviewWidget()
        self.tabs.addTab(self.preview_widget, "Preview")

        # Log tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #cccccc; font-family: monospace; font-size: 9pt;"
        )
        self.tabs.addTab(self.log_text, "Log")

        r_layout.addWidget(self.tabs, 1)

        # Open output folder button
        btn_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open Output Folder")
        _nofocus(self.btn_open_folder)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.btn_open_folder)

        self.btn_open_image = QPushButton("Open Annotated Image")
        _nofocus(self.btn_open_image)
        self.btn_open_image.setEnabled(False)
        self.btn_open_image.clicked.connect(self._on_open_image)
        btn_row.addWidget(self.btn_open_image)

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
        self.setWindowTitle("Svenesis Annotate Image")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1200, 800)

    # ------------------------------------------------------------------
    # PERSISTENT SETTINGS
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        st = self._settings
        # Object type checkboxes
        type_defaults = {"Gal": True, "Neb": True, "RN": True, "PN": True,
                         "OC": True, "GC": True, "SNR": True, "DN": False,
                         "HII": False, "Star": True}
        for key, chk in self._type_checkboxes.items():
            chk.setChecked(st.value(f"type_{key}", type_defaults.get(key, True), type=bool))
        self.chk_simbad.setChecked(st.value("cat_simbad", False, type=bool))
        self.spin_font.setValue(int(st.value("font_size", 10)))
        self.spin_marker.setValue(int(st.value("marker_size", 20)))
        self.spin_mag.setValue(float(st.value("mag_limit", 12.0)))
        self.chk_ellipses.setChecked(st.value("show_ellipses", True, type=bool))
        self.chk_magnitude.setChecked(st.value("show_magnitude", False, type=bool))
        self.chk_type_label.setChecked(st.value("show_type_label", False, type=bool))
        self.chk_common_names.setChecked(st.value("show_common_names", True, type=bool))
        self.chk_color_by_type.setChecked(st.value("color_by_type", True, type=bool))
        self.chk_grid.setChecked(st.value("show_grid", True, type=bool))
        self.chk_info_box.setChecked(st.value("show_info_box", True, type=bool))
        self.chk_compass.setChecked(st.value("show_compass", False, type=bool))
        self.chk_legend.setChecked(st.value("show_legend", True, type=bool))
        self.chk_leader_lines.setChecked(st.value("show_leader_lines", True, type=bool))
        self.spin_dpi.setValue(int(st.value("dpi", 150)))

        fmt = st.value("output_format", "PNG")
        if fmt == "TIFF":
            self.radio_tiff.setChecked(True)
        elif fmt == "JPEG":
            self.radio_jpeg.setChecked(True)
        else:
            self.radio_png.setChecked(True)

    def _save_settings(self) -> None:
        st = self._settings
        for key, chk in self._type_checkboxes.items():
            st.setValue(f"type_{key}", chk.isChecked())
        st.setValue("cat_simbad", self.chk_simbad.isChecked())
        st.setValue("font_size", self.spin_font.value())
        st.setValue("marker_size", self.spin_marker.value())
        st.setValue("mag_limit", self.spin_mag.value())
        st.setValue("show_ellipses", self.chk_ellipses.isChecked())
        st.setValue("show_magnitude", self.chk_magnitude.isChecked())
        st.setValue("show_type_label", self.chk_type_label.isChecked())
        st.setValue("show_common_names", self.chk_common_names.isChecked())
        st.setValue("color_by_type", self.chk_color_by_type.isChecked())
        st.setValue("show_grid", self.chk_grid.isChecked())
        st.setValue("show_info_box", self.chk_info_box.isChecked())
        st.setValue("show_compass", self.chk_compass.isChecked())
        st.setValue("show_legend", self.chk_legend.isChecked())
        st.setValue("show_leader_lines", self.chk_leader_lines.isChecked())
        st.setValue("dpi", self.spin_dpi.value())

        if self.radio_tiff.isChecked():
            st.setValue("output_format", "TIFF")
        elif self.radio_jpeg.isChecked():
            st.setValue("output_format", "JPEG")
        else:
            st.setValue("output_format", "PNG")

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        """Append a message to the log tab and Siril console."""
        self.log_text.append(f"[AnnotateImage] {msg}")
        try:
            self.siril.log(f"[AnnotateImage] {msg}")
        except (SirilError, OSError, RuntimeError, AttributeError):
            pass

    # ------------------------------------------------------------------
    # PROGRESS
    # ------------------------------------------------------------------

    def _update_progress(self, value: int, label: str = "") -> None:
        self.progress.setValue(value)
        if label:
            self.lbl_status.setText(f"Status: {label}")
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # SIRIL IMAGE LOADING
    # ------------------------------------------------------------------

    def _load_from_siril(self) -> bool:
        """Load the current image and WCS from Siril."""
        no_image_msg = "No image is currently loaded in Siril. Please load a FITS image first."
        try:
            if not self.siril.connected:
                self.siril.connect()

            with self.siril.image_lock():
                # Get preview image data (auto-stretched, 8-bit)
                try:
                    preview = self.siril.get_image_pixeldata(preview=True, linked=True)
                    if preview is not None:
                        self._image_data = np.array(preview, dtype=np.uint8)
                    else:
                        raise ValueError("No preview data")
                except Exception:
                    # Fallback: get raw data
                    fit = self.siril.get_image()
                    fit.ensure_data_type(np.float32)
                    data = np.array(fit.data, dtype=np.float32)
                    # Simple autostretch for display
                    if data.ndim == 3:
                        # (C, H, W) -> (H, W, C)
                        data = np.transpose(data, (1, 2, 0))
                    elif data.ndim == 2:
                        data = np.stack([data] * 3, axis=-1)
                    # Normalize to 0-255
                    vmin, vmax = np.percentile(data, [1, 99])
                    if vmax > vmin:
                        data = np.clip((data - vmin) / (vmax - vmin) * 255, 0, 255)
                    self._image_data = data.astype(np.uint8)

                fit = self.siril.get_image()
                self._img_width = fit.width
                self._img_height = fit.height
                self._img_channels = fit.channels

            # Ensure image data is (H, W, 3)
            if self._image_data is not None:
                if self._image_data.ndim == 3 and self._image_data.shape[0] in (1, 3):
                    # (C, H, W) -> (H, W, C)
                    self._image_data = np.transpose(self._image_data, (1, 2, 0))
                if self._image_data.ndim == 2:
                    self._image_data = np.stack([self._image_data] * 3, axis=-1)
                if self._image_data.shape[2] == 1:
                    self._image_data = np.repeat(self._image_data, 3, axis=2)

            # --- WCS / plate-solve detection ---
            # Uses the same approach as Galaxy_Annotations.py from siril-scripts.
            self._is_plate_solved = False
            self._wcs = None
            self._header_str = ""

            # Step 1: Get FITS header as DICT and build WCS (Galaxy_Annotations approach)
            try:
                header_dict = self.siril.get_image_fits_header(return_as="dict")
                if header_dict:
                    self._log(f"FITS header dict: got {len(header_dict)} keys")
                    wcs = WCS(header_dict, naxis=[1, 2])
                    if wcs.has_celestial:
                        self._wcs = wcs
                        self._is_plate_solved = True
                        self._log("WCS: extracted from header dict")
                    else:
                        self._log("WCS: header dict has no celestial WCS")
                else:
                    self._log("FITS header dict: returned empty/None")
            except Exception as e:
                self._log(f"FITS header dict: failed: {e}")

            # Step 2: Fallback — header as string
            if self._wcs is None:
                try:
                    hdr_str = self.siril.get_image_fits_header(return_as="str")
                    if hdr_str:
                        self._header_str = hdr_str
                        self._log(f"FITS header str: got {len(hdr_str)} chars")
                        self._wcs = extract_wcs_from_header(hdr_str)
                        if self._wcs is not None:
                            self._is_plate_solved = True
                            self._log("WCS: extracted from header string")
                        else:
                            self._log("WCS: header string parsing failed")
                            if "CRVAL1" in hdr_str:
                                self._is_plate_solved = True
                except Exception as e:
                    self._log(f"FITS header str: failed: {e}")

            # Step 3: Check keywords for plate-solve flag
            if not self._is_plate_solved:
                try:
                    kw = self.siril.get_image_keywords()
                    if kw is not None:
                        self._is_plate_solved = bool(getattr(kw, "pltsolvd", False))
                        if not self._is_plate_solved:
                            self._is_plate_solved = bool(getattr(kw, "wcsdata", None))
                        self._log(f"Keywords: pltsolvd={getattr(kw, 'pltsolvd', '?')}")
                except Exception as e:
                    self._log(f"Keywords: failed: {e}")

            # Step 4: Build WCS from pix2radec sampling (if plate-solved but no WCS yet)
            if self._wcs is None and self._is_plate_solved:
                self._log("WCS: trying pix2radec sampling...")
                self._wcs = self._build_wcs_from_siril()
                if self._wcs is not None:
                    self._log("WCS: built from sirilpy pix2radec")

            # Step 5: Try pix2radec even without plate-solve flag
            if self._wcs is None:
                try:
                    cx, cy = self._img_width / 2, self._img_height / 2
                    result = self.siril.pix2radec(cx, cy)
                    if result is not None:
                        ra, dec = result
                        self._log(f"WCS: pix2radec works! center=({ra:.4f}, {dec:.4f})")
                        self._is_plate_solved = True
                        self._wcs = self._build_wcs_from_siril()
                        if self._wcs is not None:
                            self._log("WCS: built from sirilpy pix2radec")
                    else:
                        self._log("WCS: pix2radec returned None")
                except Exception as e:
                    self._log(f"WCS: pix2radec failed: {e}")

            # Step 6: Last resort — read FITS file from disk
            if self._wcs is None:
                self._log("WCS: trying FITS file on disk...")
                self._wcs = extract_wcs_from_fits_file(self.siril, log_func=self._log)
                if self._wcs is not None:
                    self._is_plate_solved = True
                    self._log("WCS: extracted from FITS file on disk")

            # Finalize
            if self._wcs is not None:
                self._is_plate_solved = True
                self._pixel_scale = compute_pixel_scale(self._wcs)
            else:
                self._pixel_scale = 1.0

            # Update info bar
            ch_str = "RGB" if self._img_channels >= 3 else "Mono"
            wcs_str = "plate-solved \u2713" if self._is_plate_solved else "NOT plate-solved \u2717"
            self.lbl_image_info.setText(
                f"{self._img_width} \u00d7 {self._img_height} px  |  {ch_str}  |  {wcs_str}"
            )
            self._log(f"Result: plate_solved={self._is_plate_solved}, "
                       f"wcs={'OK' if self._wcs else 'NONE'}, "
                       f"scale={self._pixel_scale:.2f}\"/px")

            return True

        except NoImageError:
            QMessageBox.warning(self, "No Image", no_image_msg)
            return False
        except SirilConnectionError:
            QMessageBox.warning(
                self, "Connection Error",
                "Could not connect to Siril. Make sure Siril is running."
            )
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
                f"Failed to load image:\n{e}\n\n{traceback.format_exc()}"
            )
            return False

    def _build_wcs_from_siril(self) -> WCS | None:
        """
        Build an astropy WCS object by sampling sirilpy's pix2radec.
        Used as last resort when header parsing fails but Siril has WCS internally.
        """
        try:
            w, h = self._img_width, self._img_height
            cx, cy = w / 2.0, h / 2.0

            # Get center coordinates
            ra_c, dec_c = self.siril.pix2radec(cx, cy)

            # Get pixel scale and rotation by sampling nearby points
            delta = 10.0  # pixels
            ra_r, dec_r = self.siril.pix2radec(cx + delta, cy)
            ra_u, dec_u = self.siril.pix2radec(cx, cy + delta)

            # Build CD matrix from finite differences
            cos_dec = np.cos(np.radians(dec_c))
            cd1_1 = (ra_r - ra_c) * cos_dec / delta  # dRA/dx (degrees/pixel)
            cd1_2 = (ra_u - ra_c) * cos_dec / delta  # dRA/dy
            cd2_1 = (dec_r - dec_c) / delta            # dDEC/dx
            cd2_2 = (dec_u - dec_c) / delta            # dDEC/dy

            # Handle RA wrap-around
            if cd1_1 > 180:
                cd1_1 -= 360
            elif cd1_1 < -180:
                cd1_1 += 360
            if cd1_2 > 180:
                cd1_2 -= 360
            elif cd1_2 < -180:
                cd1_2 += 360

            # Create WCS
            wcs = WCS(naxis=2)
            wcs.wcs.crpix = [cx + 1, cy + 1]  # FITS is 1-indexed
            wcs.wcs.crval = [ra_c, dec_c]
            wcs.wcs.cd = np.array([[cd1_1, cd1_2], [cd2_1, cd2_2]])
            wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
            wcs.array_shape = (h, w)

            # Validate: round-trip check
            test_ra, test_dec = wcs.all_pix2world([[cx, cy]], 0)[0]
            if abs(test_ra - ra_c) < 0.01 and abs(test_dec - dec_c) < 0.01:
                return wcs
            else:
                self._log(f"WCS: round-trip check failed: "
                          f"({test_ra:.4f},{test_dec:.4f}) vs ({ra_c:.4f},{dec_c:.4f})")
        except Exception as e:
            self._log(f"WCS: _build_wcs_from_siril failed: {e}")
        return None

    # ------------------------------------------------------------------
    # ANNOTATION
    # ------------------------------------------------------------------

    def _on_annotate(self) -> None:
        """Main annotation workflow."""
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log_text.clear()

        self._log("Starting annotation...")
        self._update_progress(5, "Loading image from Siril...")

        if not self._load_from_siril():
            self.progress.setVisible(False)
            self.lbl_status.setText("Status: Failed to load image")
            return

        self._log(f"Image loaded: {self._img_width} x {self._img_height} px")

        if not self._is_plate_solved or self._wcs is None:
            if self._is_plate_solved and self._wcs is None:
                msg = (
                    "The image appears plate-solved but the WCS data could not be read.\n\n"
                    "Try saving the image as FITS first, then reload and run this script.\n"
                    "The FITS file must be in Siril's working directory."
                )
            else:
                msg = (
                    "The image is not plate-solved. Please run Plate Solving first.\n\n"
                    "In Siril: Tools \u2192 Astrometry \u2192 Image Plate Solver..."
                )
            QMessageBox.warning(self, "Not Plate-Solved", msg)
            self._log("ERROR: Image is not plate-solved or WCS could not be read. Aborting.")
            self.progress.setVisible(False)
            self.lbl_status.setText("Status: Image not plate-solved")
            return

        # Log WCS info
        try:
            center = self._wcs.all_pix2world(
                [[self._img_width / 2, self._img_height / 2]], 0
            )[0]
            self._log(f"WCS: Center RA={degrees_to_hms(center[0])}  DEC={degrees_to_dms(center[1])}")
            self._log(f"Pixel Scale: {self._pixel_scale:.2f}\"/px")
        except Exception:
            pass

        self._update_progress(10, "Loading catalogs...")

        # Collect catalog objects
        all_objects: list[dict] = []
        mag_limit = self.spin_mag.value()

        # Determine which object types are enabled
        enabled_types = {k for k, chk in self._type_checkboxes.items() if chk.isChecked()}
        self._log(f"Enabled types: {', '.join(sorted(enabled_types))}")

        # Common kwargs for all filter calls
        fov_kw = dict(
            wcs=self._wcs, width=self._img_width, height=self._img_height,
            siril=self.siril, log_func=self._log,
        )

        # Load ALL offline catalogs, then filter by selected object types
        all_catalogs = [
            ("Messier", MESSIER_CATALOG, mag_limit),
            ("NGC", NGC_BRIGHT_CATALOG, mag_limit),
            ("Named Stars", NAMED_STARS_CATALOG, mag_limit),
            ("Sharpless", SHARPLESS_CATALOG, mag_limit),
            ("Caldwell", CALDWELL_CATALOG, mag_limit),
            ("IC", IC_BRIGHT_CATALOG, mag_limit),
            ("Barnard", BARNARD_CATALOG, 99.0),  # dark nebulae bypass mag limit
        ]

        catalog_summary = []
        for cat_name, cat_data, cat_mag in all_catalogs:
            raw = filter_objects_in_fov(cat_data, mag_limit=cat_mag, **fov_kw)
            # Filter by enabled object types
            typed = [o for o in raw if o["type"] in enabled_types]
            # Deduplicate against already collected objects
            deduped = self._deduplicate(typed, all_objects)
            if deduped:
                catalog_summary.append(f"{cat_name}: {len(deduped)}")
                all_objects.extend(deduped)

        # SIMBAD online query (optional)
        if self.chk_simbad.isChecked():
            self._update_progress(12, "Querying SIMBAD online...")
            simbad_objs = self._query_simbad(mag_limit)
            if simbad_objs:
                # Filter by enabled types
                typed = [o for o in simbad_objs if o["type"] in enabled_types]
                deduped = self._deduplicate(typed, all_objects)
                if deduped:
                    catalog_summary.append(f"SIMBAD: {len(deduped)}")
                    all_objects.extend(deduped)

        self._log("\u2500" * 40)
        self._log(f"Catalogs loaded: {', '.join(catalog_summary)}")
        self._log(f"Magnitude limit: {mag_limit:.1f}")
        self._log(f"Total objects in field: {len(all_objects)}")

        if len(all_objects) == 0:
            self._log("No catalog objects found in the field of view.")
            self._log("The image will be exported with grid/info box only (if enabled).")

        # Log found objects
        for obj in all_objects:
            common = f" ({obj['common_name']})" if obj.get("common_name") else ""
            mag_str = f"{obj['mag']:.1f}" if obj['mag'] != 0.0 else "?"
            self._log(f"  {obj['name']}{common}  [{obj['type']}]  mag={mag_str}")

        self._log("\u2500" * 40)

        self._update_progress(15, "Resolving label positions...")

        # Resolve label collisions
        all_objects = resolve_label_collisions(all_objects)

        # Build config
        config = {
            "colors": DEFAULT_COLORS,
            "font_size": self.spin_font.value(),
            "marker_size": self.spin_marker.value(),
            "line_width": 1.5,
            "pixel_scale_arcsec": self._pixel_scale,
            "show_ellipses": self.chk_ellipses.isChecked(),
            "show_magnitude": self.chk_magnitude.isChecked(),
            "show_type_label": self.chk_type_label.isChecked(),
            "show_common_names": self.chk_common_names.isChecked(),
            "color_by_type": self.chk_color_by_type.isChecked(),
            "show_grid": self.chk_grid.isChecked(),
            "show_info_box": self.chk_info_box.isChecked(),
            "show_compass": self.chk_compass.isChecked(),
            "show_legend": self.chk_legend.isChecked(),
            "show_leader_lines": self.chk_leader_lines.isChecked(),
            "dpi": self.spin_dpi.value(),
            "grid_color": "#4466AA",
            "grid_alpha": 0.4,
            "grid_label_size": 7,
            "compass_color": "#88AAFF",
        }

        # Try to get object name from FITS header
        try:
            kw = self.siril.get_keywords()
            if kw is not None:
                obj_name = getattr(kw, "object", "") or ""
                if not obj_name:
                    # Try objctra/objctdec as fallback object identifier
                    obj_name = getattr(kw, "object_name", "") or ""
                if obj_name:
                    config["object_name"] = obj_name
        except Exception:
            pass
        # Fallback: try parsing OBJECT from FITS header string
        if "object_name" not in config and self._header_str:
            for line in self._header_str.split("\n"):
                if line.startswith("OBJECT"):
                    val = line.split("=", 1)[-1].split("/")[0].strip().strip("'\" ")
                    if val:
                        config["object_name"] = val
                        break

        # Output path
        ext_map = {"PNG": ".png", "TIFF": ".tiff", "JPEG": ".jpg"}
        if self.radio_tiff.isChecked():
            ext = ext_map["TIFF"]
        elif self.radio_jpeg.isChecked():
            ext = ext_map["JPEG"]
        else:
            ext = ext_map["PNG"]

        base_name = self.edit_filename.text().strip() or "annotated"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}{ext}"

        # Save next to the image if possible, otherwise working directory
        try:
            wd = self.siril.get_siril_wd()
            output_dir = wd if wd else os.getcwd()
        except Exception:
            output_dir = os.getcwd()

        output_path = os.path.join(output_dir, filename)

        # Render
        try:
            result_path = render_annotated_image(
                self._image_data,
                all_objects,
                self._wcs,
                config,
                output_path,
                progress_callback=self._update_progress,
            )
            self._last_output_path = result_path
            self.btn_open_folder.setEnabled(True)
            self.btn_open_image.setEnabled(True)

            # Show preview
            self.preview_widget.set_image(result_path)
            self.tabs.setCurrentIndex(0)  # switch to preview tab

            file_size = os.path.getsize(result_path)
            size_str = f"{file_size / 1024 / 1024:.1f} MB" if file_size > 1024 * 1024 else f"{file_size / 1024:.0f} KB"
            self._log(f"Output: {result_path} ({size_str})")
            self._log(f"Annotation complete: {len(all_objects)} objects annotated.")
            self.lbl_status.setText(f"Status: Done \u2014 {len(all_objects)} objects annotated")

        except Exception as e:
            self._log(f"ERROR: {e}")
            QMessageBox.critical(
                self, "Rendering Error",
                f"Failed to render annotated image:\n{e}\n\n{traceback.format_exc()}"
            )
            self.lbl_status.setText("Status: Error during rendering")

        self.progress.setVisible(False)

    # ------------------------------------------------------------------
    # OUTPUT ACTIONS
    # ------------------------------------------------------------------

    def _query_simbad(self, mag_limit: float) -> list[dict]:
        """
        Query SIMBAD for all objects in the field of view.
        Returns list of dicts compatible with embedded catalog format.
        """
        try:
            from astroquery.simbad import Simbad
            from astropy.coordinates import SkyCoord
            import astropy.units as u
        except ImportError:
            self._log("SIMBAD: astroquery not installed. Run: pip install astroquery")
            QMessageBox.warning(
                self, "Missing Package",
                "The 'astroquery' package is required for SIMBAD queries.\n\n"
                "Install it with: pip install astroquery"
            )
            return []

        try:
            # Get field center and radius via siril.pix2radec
            cx, cy = self._img_width / 2, self._img_height / 2
            center_result = self.siril.pix2radec(cx, cy)
            corner_result = self.siril.pix2radec(0, 0)
            if center_result is None or corner_result is None:
                self._log("SIMBAD: pix2radec failed for center/corner")
                return []
            center_ra, center_dec = center_result
            corner_ra, corner_dec = corner_result
            center_coord = SkyCoord(center_ra, center_dec, unit="deg")
            corner_coord = SkyCoord(corner_ra, corner_dec, unit="deg")
            radius = center_coord.separation(corner_coord)

            self._log(f"SIMBAD: querying radius={radius.arcmin:.1f}' "
                      f"around RA={center_ra:.4f} DEC={center_dec:.4f}")

            # Configure Simbad query
            custom_simbad = Simbad()
            custom_simbad.add_votable_fields("V", "galdim_majaxis", "otype")
            custom_simbad.ROW_LIMIT = 1000

            result = custom_simbad.query_region(center_coord, radius=radius)
            if result is None or len(result) == 0:
                self._log("SIMBAD: no objects found")
                return []

            self._log(f"SIMBAD: {len(result)} objects returned")

            # Detect column names (astroquery changed them across versions)
            colnames = [c.lower() for c in result.colnames]
            id_col = "main_id" if "main_id" in colnames else "MAIN_ID"
            ra_col = "ra" if "ra" in colnames else "RA"
            dec_col = "dec" if "dec" in colnames else "DEC"
            # Find the actual column names case-sensitively
            for c in result.colnames:
                if c.lower() == "main_id":
                    id_col = c
                elif c.lower() == "ra":
                    ra_col = c
                elif c.lower() == "dec":
                    dec_col = c

            self._log(f"SIMBAD: columns = {result.colnames}")

            # SIMBAD object type to our type mapping
            type_map = {
                "G": "Gal", "GiG": "Gal", "GiP": "Gal", "BiC": "Gal",
                "IG": "Gal", "PaG": "Gal", "SBG": "Gal", "SyG": "Gal",
                "Sy1": "Gal", "Sy2": "Gal", "AGN": "Gal", "LIN": "Gal",
                "HII": "HII", "RNe": "RN", "ISM": "Neb", "EmO": "Neb",
                "SNR": "SNR", "PN": "PN", "Cl*": "OC", "GlC": "GC",
                "OpC": "OC", "As*": "Ast", "QSO": "QSO",
                "**": "Star", "*": "Star", "V*": "Star",
                "Galaxy": "Gal", "GinCl": "Gal", "GinPair": "Gal",
                "StarburstG": "Gal", "Seyfert": "Gal", "BClG": "Gal",
                "InteractingG": "Gal",
            }

            # Prefixes of catalogs worth showing in astrophotography annotations.
            # Skip survey/survey-star catalogs (SDSS, 2MASS, GPM, Pul, UCAC, TYC, etc.)
            USEFUL_PREFIXES = (
                "NGC", "IC", "M ", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                "M8", "M9", "UGC", "MCG", "Arp", "Abell", "Mrk", "VV",
                "Ced", "Sh2", "LBN", "LDN", "Barnard", "B ", "Cr ",
                "Mel", "Tr ", "Pal", "NGC", "PGC", "ESO", "CGCG",
                "Hickson", "HCG", "Minkowski", "PK", "PN G",
                "Hen", "He ", "Haro", "Ho ", "K ", "Terzan",
                "NAME ", "V*", "HD ", "HR ",
            )
            # Prefixes to always skip (survey junk)
            JUNK_PREFIXES = (
                "SDSS", "2MASS", "2XMM", "GPM", "Pul", "UCAC", "TYC",
                "WISEA", "LEDA", "FIRST", "NVSS", "[", "Gaia",
                "USNO", "GSC", "IRAS", "PSO", "GALEX", "XMM", "ROSAT",
                "AG+", "BD+", "BD-", "CPD-", "CD-",
            )

            def _safe_float(val, default: float = 0.0) -> float:
                """Safely convert a possibly-masked value to float."""
                try:
                    if val is None or val is np.ma.masked:
                        return default
                    f = float(val)
                    return default if np.isnan(f) else f
                except (ValueError, TypeError):
                    return default

            objects = []
            skipped_junk = 0
            for row in result:
                try:
                    name = str(row[id_col]).strip()
                except Exception:
                    continue

                # Filter: skip junk survey catalog IDs
                is_junk = any(name.startswith(p) for p in JUNK_PREFIXES)
                is_useful = any(name.startswith(p) for p in USEFUL_PREFIXES)
                if is_junk and not is_useful:
                    skipped_junk += 1
                    continue

                # Parse coordinates
                try:
                    ra = _safe_float(row[ra_col], default=float("nan"))
                    dec = _safe_float(row[dec_col], default=float("nan"))
                    if np.isnan(ra) or np.isnan(dec):
                        # Fall back to sexagesimal parsing
                        coord = SkyCoord(
                            str(row[ra_col]), str(row[dec_col]),
                            unit=(u.hourangle, u.deg),
                        )
                        ra = coord.ra.deg
                        dec = coord.dec.deg
                except Exception:
                    continue

                # Magnitude
                mag = _safe_float(row.get("V", None) if hasattr(row, "get")
                                  else row["V"] if "V" in result.colnames else None,
                                  default=0.0)
                mag_known = mag != 0.0

                # Filter by magnitude: skip only if known and too faint
                if mag_known and mag > mag_limit:
                    continue

                # Size
                size = 0.0
                for sc in ("galdim_majaxis", "GALDIM_MAJAXIS",
                           "DIM_MAJAXIS", "dim_majaxis"):
                    if sc in result.colnames:
                        size = _safe_float(row[sc], 0.0)
                        if size > 0:
                            break

                # Type
                otype = ""
                for tc in ("otype", "OTYPE"):
                    if tc in result.colnames:
                        try:
                            otype = str(row[tc]).strip()
                            break
                        except Exception:
                            pass
                obj_type = type_map.get(otype, "Other")

                # Convert to pixel via siril.radec2pix
                try:
                    result_pix = self.siril.radec2pix(ra, dec)
                    if result_pix is None:
                        continue
                    x, y = float(result_pix[0]), float(result_pix[1])
                except Exception:
                    continue

                margin = 30
                if margin < x < self._img_width - margin and margin < y < self._img_height - margin:
                    objects.append({
                        "name": name,
                        "ra": ra,
                        "dec": dec,
                        "type": obj_type,
                        "mag": mag,
                        "size_arcmin": size,
                        "common_name": "",
                        "pixel_x": x,
                        "pixel_y": y,
                    })

            self._log(f"SIMBAD: {len(objects)} useful objects in FOV "
                      f"({skipped_junk} survey catalog entries filtered out)")
            return objects

        except Exception as e:
            self._log(f"SIMBAD: query failed: {e}")
            return []

    @staticmethod
    def _deduplicate(
        new_objs: list[dict], existing: list[dict], min_dist: int = 20,
    ) -> list[dict]:
        """Remove objects from new_objs that are too close to existing ones."""
        deduped = []
        for obj in new_objs:
            too_close = False
            for ex in existing:
                dx = abs(obj["pixel_x"] - ex["pixel_x"])
                dy = abs(obj["pixel_y"] - ex["pixel_y"])
                if dx < min_dist and dy < min_dist:
                    too_close = True
                    break
            if not too_close:
                deduped.append(obj)
        return deduped

    def _on_open_folder(self) -> None:
        if self._last_output_path:
            folder = os.path.dirname(self._last_output_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_open_image(self) -> None:
        if self._last_output_path and os.path.isfile(self._last_output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_output_path))

    # ------------------------------------------------------------------
    # BUY ME A COFFEE
    # ------------------------------------------------------------------

    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"

        dlg = QDialog(self)
        dlg.setWindowTitle("\u2615 Support Svenesis Annotate Image")
        dlg.setMinimumSize(520, 480)
        dlg.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#e0e0e0}"
            "QLabel{color:#e0e0e0}"
            "QPushButton{font-weight:bold;padding:8px;border-radius:6px}"
        )
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Combined header + message
        header_msg = QLabel(
            "<div style='text-align:center; font-size:12pt; line-height:1.6;'>"
            "<span style='font-size:48pt;'>\u2615</span><br>"
            "<span style='font-size:18pt; font-weight:bold; color:#FFDD00;'>"
            "Buy me a Coffee</span><br><br>"
            "<b style='color:#e0e0e0;'>Enjoying Svenesis Annotate Image?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If this tool has helped you create beautiful annotated images "
            "or made sharing your astrophotography easier \u2014 consider buying "
            "me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>\u2615 Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br><br>"
            "<span style='color:#aaaaaa;'>Your support helps maintain:</span><br>"
            "\u2022 Svenesis Gradient Analyzer \u2022 Svenesis Image Advisor<br>"
            "\u2022 Svenesis Annotate Image \u2022 Svenesis Script Security Scanner<br>"
            "</div>"
        )
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)

        layout.addSpacing(8)

        # Open link button
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

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton{background-color:#444;color:#ddd;border:1px solid #666;padding:6px}"
            "QPushButton:hover{background-color:#555}"
        )
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        # Footer
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
    # HELP
    # ------------------------------------------------------------------

    def _show_help_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Svenesis Annotate Image \u2014 Help")
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
            "<p><b>What does Annotate Image do?</b></p>"
            "<p>This script takes your plate-solved astrophotography image and creates "
            "an annotated version with labeled deep-sky objects, stars, coordinate grids, "
            "and field information \u2014 ready to share on social media or forums.</p>"
            "<hr>"
            "<p><b>Requirements:</b></p>"
            "<ul>"
            "<li><b>Plate-solved image:</b> Your image must have a WCS (World Coordinate System) "
            "solution in its FITS header. In Siril: <i>Tools \u2192 Astrometry \u2192 Image Plate Solver</i>.</li>"
            "<li>The script will check this automatically and warn you if the image is not plate-solved.</li>"
            "</ul>"
            "<hr>"
            "<p><b>Quick Start:</b></p>"
            "<ol>"
            "<li>Load a plate-solved image in Siril</li>"
            "<li>Run this script</li>"
            "<li>Select which <b>object types</b> to annotate (Galaxies, Nebulae, Stars...)</li>"
            "<li>Adjust display settings (font size, magnitude limit, etc.)</li>"
            "<li>Click <b>Annotate Image</b> (or press F5)</li>"
            "<li>The annotated image is saved as PNG/TIFF/JPEG in Siril's working directory</li>"
            "</ol>"
            "<hr>"
            "<p><b>How it works:</b></p>"
            "<p>The script searches all embedded catalogs (Messier, NGC, IC, Caldwell, "
            "Sharpless, Barnard, Named Stars) and optionally queries SIMBAD online. "
            "Objects are filtered by the type checkboxes you select \u2014 so you control "
            "<i>what kinds</i> of objects appear, not which catalog they come from.</p>"
            "<hr>"
            "<p><b>Color Coding:</b></p>"
            "<table cellpadding='4'>"
            "<tr><td style='color:#FFD700;'>\u2588\u2588</td><td>Galaxies</td>"
            "<td style='color:#FF4444;'>\u2588\u2588</td><td>Emission Nebulae</td></tr>"
            "<tr><td style='color:#44FF44;'>\u2588\u2588</td><td>Planetary Nebulae</td>"
            "<td style='color:#44AAFF;'>\u2588\u2588</td><td>Open Clusters</td></tr>"
            "<tr><td style='color:#FF8800;'>\u2588\u2588</td><td>Globular Clusters</td>"
            "<td style='color:#FF44FF;'>\u2588\u2588</td><td>Supernova Remnants</td></tr>"
            "<tr><td style='color:#888888;'>\u2588\u2588</td><td>Dark Nebulae</td>"
            "<td style='color:#FFFFFF;'>\u2588\u2588</td><td>Named Stars</td></tr>"
            "<tr><td style='color:#FF6666;'>\u2588\u2588</td><td>HII Regions</td>"
            "<td style='color:#FF8888;'>\u2588\u2588</td><td>Reflection Nebulae</td></tr>"
            "</table>"
        )
        tabs.addTab(tab1, "Getting Started")

        # --- Object Types ---
        tab2 = QTextEdit()
        tab2.setReadOnly(True)
        tab2.setHtml(
            "<h2 style='color:#88aaff;'>Object Types</h2>"
            "<p>Select which types of astronomical objects to annotate. "
            "All embedded catalogs (Messier, NGC, IC, Caldwell, Sharpless, Barnard, "
            "Named Stars) are always searched — objects are filtered by type.</p>"
            "<hr>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='color:#FFD700;font-weight:bold'>Galaxies</td>"
            "<td>Spiral, elliptical, and irregular galaxies from all catalogs. "
            "M31, M51, M81, NGC 4565, Centaurus A, etc.</td></tr>"
            "<tr><td style='color:#FF4444;font-weight:bold'>Emission Nebulae</td>"
            "<td>HII regions and star-forming clouds. "
            "Orion, Lagoon, Eagle, Rosette, Carina, etc.</td></tr>"
            "<tr><td style='color:#FF8888;font-weight:bold'>Reflection Nebulae</td>"
            "<td>Dust clouds illuminated by nearby stars. "
            "M78, Witch Head, Iris, Running Man, Rho Ophiuchi, etc.</td></tr>"
            "<tr><td style='color:#44FF44;font-weight:bold'>Planetary Nebulae</td>"
            "<td>Dying star shells. Ring (M57), Dumbbell (M27), "
            "Helix, Owl, Cat's Eye, Ghost of Jupiter, etc.</td></tr>"
            "<tr><td style='color:#44AAFF;font-weight:bold'>Open Clusters</td>"
            "<td>Young star groups. Pleiades (M45), Double Cluster, "
            "Wild Duck, Beehive, Jewel Box, etc.</td></tr>"
            "<tr><td style='color:#FF8800;font-weight:bold'>Globular Clusters</td>"
            "<td>Ancient dense star balls. M13, M3, Omega Centauri, "
            "47 Tucanae, M22, etc.</td></tr>"
            "<tr><td style='color:#FF44FF;font-weight:bold'>Supernova Remnants</td>"
            "<td>Explosion debris. Crab (M1), Veil Nebula, "
            "Simeis 147, Pencil Nebula, etc.</td></tr>"
            "<tr><td style='color:#888888;font-weight:bold'>Dark Nebulae</td>"
            "<td>Opaque dust clouds (Barnard catalog). Horsehead (B33), "
            "Pipe (B78), Snake (B72), Coalsack. Always shown regardless of "
            "magnitude limit.</td></tr>"
            "<tr><td style='color:#FF6666;font-weight:bold'>HII Regions</td>"
            "<td>Sharpless catalog ionized hydrogen regions. Large emission "
            "complexes: Heart, Soul, Barnard's Loop, Simeis 147, etc. "
            "Best for wide-field Milky Way images.</td></tr>"
            "<tr><td style='color:#FFFFFF;font-weight:bold'>Named Stars</td>"
            "<td>~275 IAU-named stars to mag ~5.5 with Bayer designations. "
            "Full-sky coverage for orientation: Vega, Deneb, Polaris, "
            "Betelgeuse, Pleiades members, constellation stars, etc.</td></tr>"
            "</table>"
            "<hr>"
            "<p><b>SIMBAD Online:</b> Queries the SIMBAD database for additional "
            "objects not in the embedded catalogs. Finds fainter galaxies, "
            "obscure NGC/IC objects, UGC, MCG, Abell clusters, etc. "
            "Requires internet and the <code>astroquery</code> package.</p>"
            "<hr>"
            "<p><b>Magnitude Limit:</b> Only objects brighter than this value "
            "are annotated. 12.0 is good for most images. Dark nebulae bypass this.</p>"
        )
        tabs.addTab(tab2, "Object Types")

        # --- Display Options ---
        tab3 = QTextEdit()
        tab3.setReadOnly(True)
        tab3.setHtml(
            "<h2 style='color:#88aaff;'>Display Options</h2>"
            "<p><b>Font Size:</b> Controls the label text size. Larger for social media sharing, "
            "smaller for high-resolution prints. Default: 10pt.</p>"
            "<p><b>Marker Size:</b> Controls the crosshair/ellipse marker size for point-like "
            "objects. Default: 20px.</p>"
            "<p><b>Object Size as Ellipse:</b> When enabled, extended objects (galaxies, nebulae) "
            "are shown as ellipses proportional to their cataloged angular size. When disabled, "
            "all objects get simple crosshair markers.</p>"
            "<p><b>Magnitude in Label:</b> Appends the visual magnitude to each label, "
            "e.g. 'M31 3.4m'. Useful for understanding object brightness.</p>"
            "<p><b>Object Type in Label:</b> Appends the type designation, "
            "e.g. 'M31 [Galaxy]'. Helpful for identification.</p>"
            "<p><b>Common Names:</b> Shows popular names where available, "
            "e.g. 'M31 (Andromeda Galaxy)'. Disable for a cleaner, more compact look.</p>"
            "<p><b>Color by Type:</b> Uses different colors for different object categories "
            "(see Getting Started tab for color legend).</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Extras</h3>"
            "<p><b>Coordinate Grid:</b> Overlays RA/DEC grid lines with labels. "
            "Grid spacing is chosen automatically based on your field of view.</p>"
            "<p><b>Info Box:</b> Semi-transparent box (top-left) with center coordinates, "
            "field of view, pixel scale, rotation, and object count.</p>"
            "<p><b>Compass:</b> North/East direction arrows (bottom-right) showing "
            "image orientation derived from the WCS solution.</p>"
            "<p><b>Color Legend:</b> Auto-generated legend box (bottom-left) showing "
            "color swatches for each object type present in the annotation. Only types "
            "that actually appear in the image are listed.</p>"
            "<p><b>Leader Lines:</b> Thin connecting lines from each label to its "
            "object marker. Essential in crowded fields to see which label belongs "
            "to which object. Can be disabled for a cleaner look on sparse fields.</p>"
        )
        tabs.addTab(tab3, "Display Options")

        # --- Output ---
        tab4 = QTextEdit()
        tab4.setReadOnly(True)
        tab4.setHtml(
            "<h2 style='color:#88aaff;'>Output</h2>"
            "<p><b>Format:</b></p>"
            "<ul>"
            "<li><b>PNG:</b> Lossless compression, best for sharing. Recommended default.</li>"
            "<li><b>TIFF:</b> Lossless, larger files. Good for further editing.</li>"
            "<li><b>JPEG:</b> Lossy compression, smaller files. Good for web uploads.</li>"
            "</ul>"
            "<p><b>DPI:</b> Controls the output resolution. 150 DPI is good for screens "
            "and social media. Use 300 DPI for print-quality output (larger file size).</p>"
            "<p><b>Filename:</b> Base name for the output file. A timestamp is appended "
            "automatically to avoid overwriting previous annotations.</p>"
            "<p>The output file is saved in Siril's working directory (the same folder "
            "as your image).</p>"
        )
        tabs.addTab(tab4, "Output")

        layout.addWidget(tabs)
        lbl_guide = QLabel(
            '<span style="font-size:10pt;">📖 '
            '<a href="https://github.com/sramuschkat/Siril-Scripts/blob/main/'
            'Instructions/Svenesis-AnnotateImage-Instructions.md"'
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
        win = AnnotateImageWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis Annotate Image v{VERSION} loaded.")
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
            "Svenesis Annotate Image Error",
            f"{e}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
