"""
Svenesis ImageMono Train
Script Version: 1.1.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script turns a single N.I.N.A. capture folder into finished master
lights -- one integrated stack per optical filter -- without you ever
touching the Siril command line.  Point it at the root folder of a target,
and it walks the tree, reads every FITS header, groups the light frames by
their FILTER keyword, tells you exactly what it found, and then registers
and stacks each filter in turn.

ImageMono Train makes mono multi-filter processing a one-click affair:
  "Load a whole night of Ha / OIII / SII (or L R G B) into one folder,
   press one button, and walk away with one clean stack per filter."

Built for a mono rig:
- Designed around a monochrome camera behind a filter wheel (e.g. the
  Player One Ares-M Pro / IMX533) driven by N.I.N.A.
- Frames are NEVER debayered -- the whole pipeline is monochrome, exactly
  as a mono sensor requires.
- Understands the N.I.N.A. folder/naming schema
  DATE\\IMAGETYPE\\TARGETNAME\\FILTER\\TARGETNAME_FILTER_EXPs_Gxx_..., but
  does not rely on it: the FILTER / IMAGETYP / OBJECT FITS keywords are the
  source of truth, with the folder names used only as a fallback.

What it does:
- Folder picker for the target's root folder (files usually arrive there
  automatically via a Dropbox sync from the remote rig PC).
- Recursive discovery: reads FITS headers, keeps only LIGHT frames, and
  groups them by optical filter across any number of dates / sessions.
- A clear "here is what I found" report: every filter, its frame count,
  total integration time, exposure, gain and sensor temperature, shown
  before anything is stacked.
- Per-filter integration, following the proven Naztronomy Mono_PP command
  sequence: link/convert -> (optional background extraction) ->
  2-pass star registration (or plate-solve registration) -> apply
  registration -> rejection integration, with the rejection algorithm
  chosen automatically from the frame count.
- Cross-filter alignment onto one common pixel grid, so the channels
  overlay exactly for colour combination.
- Colour composition with a palette picker: LRGB / RGB / SHO / HOO /
  HaRGB.  Narrowband channels are normalised to Ha first; for LRGB the
  luminance is kept separate so it can be combined after stretching
  (Siril's recommended order).
- Auto-finish on the composite: plate-solve, background extraction,
  Photometric Colour Calibration (broadband only) and SCNR -- leaving a
  calibrated, still-linear result.
- Blank/black frame rejection, adaptive pixel rejection, weighted-FWHM
  frame weighting, optional drizzle, quality filtering and rejection maps.
- One-click option presets (Quick look / Balanced / Final).
- A tidy output folder plus a Markdown processing report (output.md) and
  a step-by-step post-processing guide (todo.md).
- Dark-themed PyQt6 GUI matching the Svenesis look & feel, with a live
  processing log and persistent settings.

Run from Siril via Processing -> Scripts.  Place this file inside a folder
named Utility in one of Siril's Script Storage Directories.

(c) 2025-2026
SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Svenesis ImageMono Train
# Script Version: 1.1.0
# Siril Version: 1.4.0
# Python Module Version: 1.1.0
# Script Category: preprocessing
# Script Description: Point it at a N.I.N.A. target folder; it discovers the
#   light frames per optical filter, integrates one master stack for each
#   filter (mono, never debayered), aligns the channels onto a common grid
#   and combines them into a colour image (LRGB / RGB / SHO / HOO / HaRGB)
#   with background extraction and photometric colour calibration.  Writes a
#   Markdown processing report and a post-processing guide alongside.
# Script Author: Sven Ramuschkat

CHANGELOG:
1.1.0 - Colour composition, reporting and robustness
      - Colour composition via rgbcomp: LRGB / RGB / SHO / HOO / HaRGB,
        with automatic palette detection and manual channel mapping
      - Narrowband channels normalised to the Ha reference (linear_match)
        before combining, so a SHO stack no longer comes out green
      - LRGB luminance kept separate for the post-stretch combine (per
        Siril's guidance); optional "quick" one-step linear LRGB
      - HaRGB: Ha screen-blended into Red with an adjustable strength
      - Auto-finish: plate-solve -> background -> PCC (broadband only,
        with a local-Gaia fallback) -> SCNR -> save linear
      - Cross-filter alignment onto a common grid (framing=min), so the
        channels are pixel-identical for combination
      - Adaptive pixel rejection by frame count, weighted-FWHM weighting,
        quality filtering, optional rejection maps
      - Per-channel background extraction on the linear masters
      - Blank / black frame detection and rejection
      - Option presets (Quick look / Balanced / Final)
      - Full and partial reuse of existing masters
      - Tidy output folder (masters/ + _work/) with a Markdown processing
        report (output.md) and post-processing guide (todo.md)
      - Total integration time per filter in the analysis
      - Fixes: .fits.fz (Rice) extension handling; output folder no longer
        re-ingested as light frames; rgbcomp/pm path handling for folders
        containing spaces; worker/GUI thread separation for sirilpy access;
        safe window close while a run is in progress
1.0.0 - Initial release
      - Recursive FITS-header discovery of LIGHT frames, grouped by FILTER
      - N.I.N.A. folder-schema awareness with header-first fallback
      - Per-filter pipeline: link/convert -> seqsubsky (optional) ->
        register -2pass / plate-solve -> seqapplyreg -> stack
      - Optional drizzle, background extraction, output normalisation
      - Symlink or copy working set, tidy per-filter output naming
      - Dark-themed PyQt6 GUI with live log and persistent settings
"""
from __future__ import annotations

import os
import sys
import json
import math
import shutil
import traceback
import datetime

import sirilpy as s
from sirilpy import LogColor, NoImageError

try:
    from sirilpy.exceptions import (
        SirilError, SirilConnectionError, CommandError, DataError,
    )
except ImportError:                       # older sirilpy
    class SirilError(Exception):
        pass

    class SirilConnectionError(Exception):
        pass

    class CommandError(Exception):
        pass

    class DataError(Exception):
        pass

s.ensure_installed("PyQt6", "astropy", "numpy")

import numpy as np
from astropy.io import fits

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QComboBox, QSpinBox, QSizePolicy, QDialog,
    QTextEdit, QTabWidget, QScrollArea, QProgressBar,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, pyqtSignal, QThread
from PyQt6.QtGui import QDesktopServices


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.1.0"
SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "ImageMonoTrain"
LEFT_PANEL_WIDTH = 380

# Our output folder, created inside the target folder.  Discovery MUST prune
# it, otherwise a second run re-ingests the masters / composites / work files
# it produced as if they were new light frames.
STACKS_DIRNAME = "output"
# Sub-structure inside the output folder (kept human-readable):
#   <STACKS_DIRNAME>/
#     TARGET_<palette>.fit        the finished colour image(s), at the top
#     masters/                    per-channel masters (TARGET_FILTER.fit =
#                                 aligned; *_fullframe.fit = uncropped)
#     _work/                      all intermediates -- safe to delete
#       sequences/<filter>/       Siril sequences per filter
#       align/                    cross-filter alignment work
#       helpers/                  compose helpers (_nbnorm, _RED_Ha)
MASTERS_DIRNAME = "masters"
WORK_DIRNAME = "_work"

# Recognised FITS containers.  ``.fz`` variants are Rice-compressed FITS.
FITS_EXTS = (".fit", ".fits", ".fts", ".fit.fz", ".fits.fz")

# Header IMAGETYP values that mean "science frame".  N.I.N.A. writes
# "LIGHT"; some pipelines write "Light Frame".  Matched case-insensitively
# as a substring so both are covered.
LIGHT_TOKENS = ("light",)

# Frame types we must never treat as lights, even if a FILTER is present.
CALIB_TOKENS = ("dark", "flat", "bias", "offset")

# Placeholder for frames without a FILTER keyword (e.g. an OSC-style
# capture accidentally dropped in, or a broadband run with no wheel).
NO_FILTER = "NOFILTER"

# Never let the quality filters shrink a stack below this many frames --
# outlier rejection needs a population, and a sharp 2-frame stack is worse
# than a slightly softer 6-frame one.
MIN_STACK_FRAMES = 4

# Quality filters only pay off once a channel has enough frames.  Dropping
# subs always costs signal-to-noise (noise scales with 1/sqrt(n)), and on a
# short run that loss outweighs whatever removing the worst frame gains.
# Measured on real data: filtering 8 luminance frames down to 6 raised the
# background noise by 19% -- almost exactly the sqrt(8/6) you would predict
# from the frame count alone, i.e. the dropped frames were not actually bad.
FILTER_MIN_FRAMES = 20

# Warn when the quality filters throw away more than this share of a set.
FILTER_WARN_FRACTION = 0.15

# One-click option profiles.  "Custom" is selected automatically as soon as
# the user changes any individual option, so the combo never lies about what
# is actually set.  Only the options a profile cares about are listed; the
# rest keep whatever the user chose.
PRESETS = {
    "Quick look": {
        # Fastest path to "does this data look good?" -- no QA extras, no
        # colour calibration, no frame filtering, keep every frame.
        "skip_blank": False, "rejection": True, "weighting": False,
        "f_wfwhm_val": 90, "f_wfwhm_on": False, "f_round_on": False,
        "f_stars_on": False, "f_bkg_on": False,
        "bg_master": False, "bg_extract": False,
        "rejmap": False, "platesolve_master": False, "compose": True,
        "finish": False, "finish_stretch": True, "nb_normalize": True,
        "cleanup_work": False,
    },
    "Balanced": {
        # The sensible default for a normal night.
        "skip_blank": True, "rejection": True, "weighting": True,
        "f_wfwhm_val": 90, "f_wfwhm_on": False, "f_round_on": False,
        "f_stars_on": False, "f_bkg_on": False,
        "bg_master": True, "bg_extract": False,
        "rejmap": False, "platesolve_master": False, "compose": True,
        "finish": True, "finish_stretch": False, "nb_normalize": True,
        "cleanup_work": False,
    },
    "Final": {
        # Everything on: quality filtering, QA artifacts, WCS in the masters.
        "skip_blank": True, "rejection": True, "weighting": True,
        "f_wfwhm_val": 90, "f_wfwhm_on": True, "f_round_on": True,
        "f_stars_on": False, "f_bkg_on": False,
        "bg_master": True, "bg_extract": False,
        "rejmap": True, "platesolve_master": True, "compose": True,
        "finish": True, "finish_stretch": False, "nb_normalize": True,
        "cleanup_work": False,
    },
}


def _log_swallowed(exc: BaseException) -> None:
    """One-line stderr trace for intentionally-swallowed exceptions.

    Siril surfaces stderr in its console, so a decorative feature that
    fails leaves a breadcrumb instead of a silent ``pass``.
    """
    try:
        tb = exc.__traceback__
        lineno = -1
        while tb is not None:
            lineno = tb.tb_lineno
            tb = tb.tb_next
        sys.stderr.write(
            f"[ImageMonoTrain] swallowed {type(exc).__name__} "
            f"(line {lineno}): {exc}\n")
    except Exception:
        pass


def _nofocus(w) -> None:
    if w is not None:
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ---------------------------------------------------------------------------
# Dark theme -- shared verbatim with the rest of the Svenesis suite
# ---------------------------------------------------------------------------
DARK_STYLESHEET = """
QWidget{background-color:#2b2b2b;color:#e0e0e0;font-size:10pt}

QToolTip{background-color:#333333;color:#ffffff;border:1px solid #88aaff}

QGroupBox{border:1px solid #444444;margin-top:5px;font-weight:bold;border-radius:4px;padding-top:12px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 3px;color:#88aaff}

QLabel{color:#cccccc}

QCheckBox{color:#cccccc;spacing:5px}
QCheckBox::indicator{width:14px;height:14px;border:1px solid #666666;background:#3c3c3c;border-radius:3px}
QCheckBox::indicator:checked{background:#285299;border:1px solid #88aaff;image:none}

QSpinBox,QDoubleSpinBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QSpinBox:focus,QDoubleSpinBox:focus{border-color:#88aaff}

QLineEdit{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px}
QLineEdit:focus{border-color:#88aaff}

QComboBox{background-color:#3c3c3c;color:#e0e0e0;border:1px solid #666666;border-radius:4px;padding:4px;min-width:60px}
QComboBox:focus{border-color:#88aaff}
QComboBox::drop-down{border:none}
QComboBox QAbstractItemView{background-color:#3c3c3c;color:#e0e0e0;selection-background-color:#285299}

QPushButton{background-color:#444444;color:#dddddd;border:1px solid #666666;border-radius:4px;padding:6px;font-weight:bold}
QPushButton:hover{background-color:#555555;border-color:#777777}
QPushButton:disabled{background-color:#333333;color:#666666;border-color:#444444}
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

QTableWidget{background-color:#1e1e1e;color:#dddddd;gridline-color:#3a3a3a;border:1px solid #444444;border-radius:4px}
QHeaderView::section{background-color:#333333;color:#88aaff;padding:4px;border:none;border-right:1px solid #444444;font-weight:bold}
QTableWidget::item:selected{background-color:#285299;color:#ffffff}

QScrollArea{border:none}
QScrollBar:vertical{background:#2b2b2b;width:10px;border:none}
QScrollBar::handle:vertical{background:#555555;border-radius:4px;min-height:20px}
QScrollBar::handle:vertical:hover{background:#666666}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
"""


# ---------------------------------------------------------------------------
# FITS header helpers
# ---------------------------------------------------------------------------
def _is_fits(name: str) -> bool:
    low = name.lower()
    return low.endswith(FITS_EXTS)


def _fits_ext(name: str) -> str:
    """Return the FITS extension, keeping compound ones like ``.fits.fz``.

    ``os.path.splitext`` only strips the final component, so a
    Rice-compressed ``foo.fits.fz`` would come back as ``.fz`` -- which
    Siril does not recognise as FITS.  N.I.N.A. writes exactly that when
    "Add .fz extension" is on, so the full suffix must be preserved.
    """
    low = name.lower()
    for ext in (".fits.fz", ".fit.fz", ".fts.fz",
                ".fits", ".fit", ".fts"):
        if low.endswith(ext):
            return ext
    return os.path.splitext(name)[1]


def _is_fits_like(ext: str) -> bool:
    """True for any FITS container Siril can ``link`` (incl. compressed)."""
    return ext.lower() in (".fits.fz", ".fit.fz", ".fts.fz",
                           ".fits", ".fit", ".fts")


def _read_header(path: str):
    """Return the first FITS header carrying real metadata.

    Rice-compressed FITS (``.fz``) keep an empty primary HDU and the real
    header in extension 1, so we scan HDUs until one exposes FILTER /
    IMAGETYP / OBJECT.  Only headers are read -- never the pixel data --
    so discovery over a whole night stays fast.
    """
    try:
        with fits.open(path, memmap=False) as hdul:
            best = hdul[0].header
            for hdu in hdul:
                h = hdu.header
                if any(k in h for k in ("FILTER", "IMAGETYP", "OBJECT")):
                    return h
            return best
    except Exception as exc:
        _log_swallowed(exc)
        return None


def _clean_token(value) -> str:
    """Normalise a header string into a filesystem-friendly token."""
    if value is None:
        return ""
    txt = str(value).strip().strip("'\"").strip()
    return txt


def _inspect(path: str) -> dict:
    """Read a FITS header ONCE and return everything discovery needs.

    Returns a dict with ``is_light`` / ``filter`` / ``object`` plus the
    display fields (``exp`` / ``gain`` / ``temp``) and the numeric exposure
    (``exp_s``) used for the integration-time totals.  Merging classification
    and summary into a single pass halves the header reads, which matters on
    a cloud-synced folder with hundreds of frames.
    """
    out = {"is_light": False, "filter": NO_FILTER, "object": "",
           "exp": "", "gain": "", "temp": "", "exp_s": 0.0}
    header = _read_header(path)
    parts = [p.lower() for p in os.path.normpath(path).split(os.sep)]

    if header is None:
        return out

    out["object"] = _clean_token(header.get("OBJECT"))

    # A 3-channel (colour) image is never a mono light — e.g. a colour
    # composite that ended up in the tree.  Reject it outright.
    try:
        if (int(header.get("NAXIS", 0)) >= 3
                and int(header.get("NAXIS3", 1)) > 1):
            out["filter"] = ""
            return out
    except (ValueError, TypeError):
        pass

    imagetyp = _clean_token(header.get("IMAGETYP"))
    it_low = imagetyp.lower()
    if it_low:
        is_light = any(t in it_low for t in LIGHT_TOKENS)
        if any(t in it_low for t in CALIB_TOKENS):
            is_light = False
    else:
        # No IMAGETYP -> trust the N.I.N.A. folder convention.
        is_light = any(t in parts for t in LIGHT_TOKENS)
        if any(t in parts for t in CALIB_TOKENS):
            is_light = False
    out["is_light"] = is_light

    filt = _clean_token(header.get("FILTER"))
    if not filt:
        # Parent directory name is the FILTER in the N.I.N.A. schema.
        parent = os.path.basename(os.path.dirname(path))
        if parent and parent.lower() not in LIGHT_TOKENS:
            filt = parent
    out["filter"] = filt or NO_FILTER

    for key in ("EXPTIME", "EXPOSURE"):
        if key in header:
            try:
                secs = float(header[key])
                out["exp_s"] = secs
                out["exp"] = f"{secs:g}s"
            except (ValueError, TypeError):
                pass
            break
    if "GAIN" in header:
        try:
            out["gain"] = f"G{int(float(header['GAIN']))}"
        except (ValueError, TypeError):
            pass
    for key in ("CCD-TEMP", "CCD_TEMP"):
        if key in header:
            try:
                out["temp"] = f"{float(header[key]):.0f}C"
            except (ValueError, TypeError):
                pass
            break
    return out


def _is_blank_frame(path: str) -> bool:
    """True if a frame carries no usable signal (black / blank / stuck).

    Cloud outages, a closed flap, a failed download or a dropped exposure
    leave frames that are all-zero or perfectly flat.  They poison
    registration ("no stars found") and drag the stack down, so they are
    skipped.  Only every 8th pixel in each axis is examined (1/64 of the
    data) -- enough to tell "black" from "sky", and fast on a cloud-synced
    folder.  On any doubt the frame is KEPT (returns False): dropping a good
    frame is worse than keeping a marginal one.
    """
    try:
        with fits.open(path, memmap=True) as hdul:
            # Pick the image HDU from the HEADER only.  Touching `.data`
            # here would already decompress a Rice-compressed (.fz) frame in
            # full -- exactly what this sampling is meant to avoid.
            image_hdu = None
            for hdu in hdul:
                try:
                    if int(hdu.header.get("NAXIS", 0)) >= 2:
                        image_hdu = hdu
                        break
                except (ValueError, TypeError):
                    continue
            if image_hdu is None:
                return False
            sample = _sample_pixels(image_hdu)
        if sample is None or sample.size == 0:
            return False
        finite = sample[np.isfinite(sample)]
        if finite.size == 0:
            return True                          # all NaN/inf -> unusable
        if float(np.max(finite)) <= 0.0:
            return True                          # completely black
        # A real sky frame always has stars/noise on top of the pedestal.
        # A dead-flat frame (std == 0) carries no information at all.
        return float(np.std(finite)) <= 0.0
    except Exception as exc:
        _log_swallowed(exc)
        return False                             # unreadable -> let Siril judge


def _sample_pixels(hdu):
    """A small pixel sample of an image HDU, as float32 (or None).

    Prefers ``hdu.section``, which reads only the requested rows -- for
    Rice-compressed frames that decompresses just those tiles instead of
    the whole image.  Falls back to a strided read of the full array if
    ``section`` is unavailable or unhappy with this HDU.
    """
    try:
        ny = int(hdu.header.get("NAXIS2", 0))
        if ny >= 8 and int(hdu.header.get("NAXIS", 0)) == 2:
            rows = []
            for y in range(0, ny, max(1, ny // 8)):
                rows.append(np.asarray(hdu.section[y:y + 1, :],
                                       dtype=np.float32).ravel())
            if rows:
                return np.concatenate(rows)
    except (AttributeError, TypeError, IndexError, ValueError):
        pass                         # no usable .section -- expected, quiet
    except Exception as exc:
        _log_swallowed(exc)          # anything else is worth a breadcrumb
    data = hdu.data
    if data is None or getattr(data, "ndim", 0) < 2:
        return None
    return np.asarray(data[..., ::8, ::8], dtype=np.float32).ravel()


def _format_duration(seconds: float) -> str:
    """Human-friendly integration time: 4560 -> '1h 16m'."""
    try:
        secs = int(round(float(seconds)))
    except (ValueError, TypeError):
        return "—"
    if secs <= 0:
        return "—"
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
# Discovery worker (off the UI thread)
# ---------------------------------------------------------------------------
class AnalyzeWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)     # {"groups": {...}, "target": str, "total": int}
    failed = pyqtSignal(str)

    def __init__(self, root: str):
        super().__init__()
        self._root = root

    def run(self) -> None:
        try:
            all_fits = []
            for dirpath, dirs, files in os.walk(self._root):
                # Prune our own output folder so previously-generated masters,
                # composites and work files are never re-ingested as lights.
                dirs[:] = [d for d in dirs if d != STACKS_DIRNAME]
                for name in files:
                    if name.startswith("."):
                        continue
                    if _is_fits(name):
                        all_fits.append(os.path.join(dirpath, name))

            total = len(all_fits)
            if total == 0:
                self.failed.emit(
                    "No FITS files were found anywhere under the selected "
                    "folder.  Make sure the light frames have finished syncing.")
                return

            groups: dict[str, dict] = {}
            objects: set[str] = set()
            target = ""
            for i, path in enumerate(sorted(all_fits)):
                if self.isInterruptionRequested():
                    return              # window is closing; drop the scan
                if i % 5 == 0 or i == total - 1:
                    self.progress.emit(
                        int(5 + 90 * (i + 1) / total),
                        f"Reading headers... {i + 1}/{total}")
                info = _inspect(path)          # one header read per file
                if not info["is_light"]:
                    continue
                if info["object"]:
                    if not target:
                        target = info["object"]
                    # Remember every distinct OBJECT among the LIGHT frames:
                    # pooling two targets into one stack would be silent
                    # garbage, so the UI has to warn about it.
                    objects.add(info["object"])
                g = groups.setdefault(
                    info["filter"],
                    {"files": [], "sample": {}, "exp_total": 0.0})
                g["files"].append(path)
                g["exp_total"] = g.get("exp_total", 0.0) + info["exp_s"]
                if not g["sample"]:
                    g["sample"] = {"exp": info["exp"], "gain": info["gain"],
                                   "temp": info["temp"]}

            if not groups:
                self.failed.emit(
                    "FITS files were found, but none looked like LIGHT frames "
                    "(their IMAGETYP / folder said dark, flat, or bias).  "
                    "Nothing to stack.")
                return

            if not target:
                target = os.path.basename(os.path.normpath(self._root))

            self.progress.emit(100, "Analysis complete.")
            self.finished.emit(
                {"groups": groups, "target": target, "total": total,
                 "objects": sorted(objects)})
        except Exception as exc:      # worker must never crash the app
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Stacking worker (off the UI thread)
# ---------------------------------------------------------------------------
class StackWorker(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, object)       # (message, LogColor)
    finished = pyqtSignal(dict)         # {"results": {filter: path}, "errors": {...}}
    failed = pyqtSignal(str)

    def __init__(self, siril, groups: dict, target: str,
                 out_dir: str, ext: str, opts: dict):
        super().__init__()
        self.siril = siril
        self._groups = groups
        self._target = target
        self._out_dir = out_dir
        self._ext = ext or ".fit"
        self._opts = opts
        # Set by _compose when L is kept separate (correct LRGB path).
        self._separate_lum = None
        # Human-readable record of what the finish step actually did, for the
        # processing report (output.md).
        self._finish_steps: list[str] = []
        # Count of blank/black frames dropped during staging (for the report).
        self._blank_skipped = 0
        # Frame count of the filter currently being processed, so the
        # quality filters can be skipped on very small sets.
        self._current_n_frames = 0
        # What each filter really contributed: {filter: (staged, effective)}.
        # The report must quote these, not the discovered counts -- blank
        # frames and the quality filters both shrink the set on the way in.
        self._stacked_counts: dict = {}
        # Collision-free filename token per filter (see _build_filter_tokens).
        self._ftok = self._build_filter_tokens()

    def _build_filter_tokens(self) -> dict:
        """One unique, filesystem-safe token per filter name.

        ``_safe`` maps every non-alphanumeric character to '_', so two
        genuinely different filters ("L Pro" and "L.Pro") can collapse onto
        the same token -- and would then overwrite each other's master,
        silently putting the same data into two colour channels.  A numeric
        suffix keeps them apart.  Case-insensitive, because Windows and
        macOS filesystems are.

        Note: suffixes are assigned per run, in sorted filter order.  Names
        that do not collide (the normal case -- LUMINOS, RED, HA ...) are
        therefore always identical across runs, which is what master reuse
        relies on.  Only if you *remove* one of two colliding filters
        between runs could a suffix shift; re-stack instead of reusing.
        """
        tokens: dict = {}
        used: set = set()
        for filt in sorted(self._groups):
            base = _safe(filt)
            tok, n = base, 2
            while tok.lower() in used:
                tok = f"{base}_{n}"
                n += 1
            used.add(tok.lower())
            tokens[filt] = tok
        return tokens

    def _tok(self, filt: str) -> str:
        """Filename token for a filter (falls back for unknown names)."""
        return self._ftok.get(filt) or _safe(filt)

    # -- helpers ----------------------------------------------------------
    def _cmd(self, *args) -> None:
        self.siril.cmd(*args)

    def _emit(self, msg: str, color=LogColor.BLUE) -> None:
        """Log a worker message.

        The Siril-console write happens HERE, on the worker thread, so it is
        serialised with the ``siril.cmd`` calls that also run on this thread.
        The GUI text update is handed to the main thread via the ``log``
        signal (queued), which never touches sirilpy -- avoiding concurrent
        access to the sirilpy transport from two threads.
        """
        try:
            self.siril.log(f"[ImageMonoTrain] {msg}", color)
        except Exception as exc:
            _log_swallowed(exc)
        self.log.emit(msg, color)

    def _link_frames(self, files: list[str], lights_dir: str) -> int:
        """Populate ``lights_dir`` with the light frames (symlink or copy).

        The original filename is kept so the FITS extension survives intact
        (crucially the compound ``.fits.fz`` that N.I.N.A. writes with Rice
        compression on).  Only when two source frames share a basename --
        rare, since N.I.N.A. names carry a frame number and timestamp -- is
        an index prefix added to disambiguate.
        """
        os.makedirs(lights_dir, exist_ok=True)
        copy = self._opts.get("copy", False)
        skip_blank = self._opts.get("skip_blank", True)
        n = 0
        blank = 0
        used: set[str] = set()
        for i, src in enumerate(files):
            if skip_blank and _is_blank_frame(src):
                blank += 1
                self._emit(f"    Skipped blank/black frame: "
                           f"{os.path.basename(src)}", LogColor.SALMON)
                continue
            base = os.path.basename(src)
            if base in used:
                base = f"{i:04d}_{base}"
            used.add(base)
            dst = os.path.join(lights_dir, base)
            try:
                if os.path.lexists(dst):
                    os.remove(dst)
                if copy:
                    shutil.copy2(src, dst)
                else:
                    try:
                        os.symlink(os.path.abspath(src), dst)
                    except (OSError, NotImplementedError):
                        shutil.copy2(src, dst)   # symlink not permitted here
                n += 1
            except Exception as exc:
                _log_swallowed(exc)
        if blank:
            self._blank_skipped += blank
        return n

    def _quality_filters_enabled(self) -> bool:
        """True if the user ticked any quality filter (regardless of size)."""
        return any(self._opts.get(k + "_on") for k in
                   ("f_wfwhm", "f_round", "f_stars", "f_bkg"))

    def _quality_filter_args(self, n_frames: int) -> list:
        """Build the -filter-* arguments for seqapplyreg.

        Siril takes ``value[%|k]``: ``%`` keeps that share of the best
        frames, ``k`` rejects beyond k sigma.  Filtering happens here rather
        than at stack time so rejected frames are never re-projected.

        Returns nothing at all below ``FILTER_MIN_FRAMES``: on a short run
        every dropped sub costs more SNR than the worst frame costs
        sharpness, so quiet filtering there would make the master worse.
        """
        args: list = []
        if n_frames < FILTER_MIN_FRAMES:
            return args
        suffix = "k" if self._opts.get("filter_mode") == "k-sigma" else "%"
        for key, flag in (("f_wfwhm", "-filter-wfwhm"),
                          ("f_round", "-filter-round"),
                          ("f_stars", "-filter-nbstars"),
                          ("f_bkg", "-filter-bkg")):
            if not self._opts.get(key + "_on"):
                continue
            value = int(self._opts.get(key + "_val", 90))
            if suffix == "%":
                if value >= 100:
                    continue                 # 100% keeps everything
                # Never filter down to a stack too small to reject outliers.
                if int(n_frames * value / 100) < MIN_STACK_FRAMES:
                    continue
            args.append(f"{flag}={value}{suffix}")
        return args

    def _register(self, seq: str) -> str:
        """Register the sequence; return the resulting sequence name."""
        drizzle = self._opts.get("drizzle", 1)
        # -framing=min keeps only the area covered by ALL sub-frames, so the
        # master has no ragged low-coverage border to crop later.  max keeps
        # the full field (with those partial edges) when the user prefers it.
        framing = "min" if self._opts.get("crop_edges", True) else "max"
        apply_args = ["seqapplyreg", seq, f"-framing={framing}"]
        if drizzle and drizzle > 1:
            apply_args += ["-drizzle", f"-scale={drizzle}", "-pixfrac=1.0",
                           "-kernel=square"]
        n_in = self._current_n_frames
        qfilters = self._quality_filter_args(n_in)
        if qfilters:
            apply_args += qfilters
            self._emit("  Quality filters: " + " ".join(qfilters),
                       LogColor.BLUE)
            # Dropping frames always costs SNR; say so when it is a lot.
            n_eff = self._effective_frame_count(n_in)
            dropped = n_in - n_eff
            if dropped > 0 and dropped / n_in > FILTER_WARN_FRACTION:
                noise = (math.sqrt(n_in / n_eff) - 1.0) * 100.0
                self._emit(
                    f"  Note: the filters drop ~{dropped} of {n_in} frames "
                    f"(~{noise:.0f}% more background noise).  Loosen them if "
                    "the frames were not actually bad.", LogColor.SALMON)
        elif self._quality_filters_enabled() and n_in < FILTER_MIN_FRAMES:
            self._emit(
                f"  Quality filters skipped: only {n_in} frame(s).  Filtering "
                f"pays off from about {FILTER_MIN_FRAMES}; below that, losing "
                "a sub costs more signal than the worst frame costs "
                "sharpness.", LogColor.BLUE)

        if self._opts.get("platesolve_reg", False):
            solve_args = ["seqplatesolve", seq, "-nocache", "-force"]
            if self._opts.get("disto_master", False):
                # Load the matching distortion master for each image.
                solve_args.append("-disto=master")
            try:
                self._cmd(*solve_args)
                self._cmd(*apply_args)
                self._emit(f"  Registered {seq} via plate solving.",
                              LogColor.GREEN)
                return f"r_{seq}"
            except (CommandError, DataError, SirilError) as exc:
                self._emit(
                    f"  Plate-solve registration failed ({exc}); "
                    "falling back to star alignment.", LogColor.SALMON)

        # Star-based two-pass registration.
        try:
            self._cmd("register", seq, "-2pass")
            self._cmd(*apply_args)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  2-pass registration unavailable ({exc}); "
                "using single-pass global registration.", LogColor.SALMON)
            self._cmd("register", seq)
        return f"r_{seq}"

    def _effective_frame_count(self, n_frames: int) -> int:
        """Frames expected to survive the quality filters.

        The rejection algorithm must be picked for the population that is
        actually integrated: filtering 21 frames down to the best 90% leaves
        18, which wants Winsorized sigma, not the linear fit that 21 frames
        would suggest.

        Derived from the arguments _quality_filter_args() really emits, so a
        filter that was dropped there (too few frames left, 100%, k-sigma)
        can never shrink the count here -- the two must not disagree.
        """
        keep = 100
        for arg in self._quality_filter_args(n_frames):
            value = arg.split("=", 1)[1]
            if value.endswith("%"):
                try:
                    keep = min(keep, int(value[:-1]))
                except ValueError:
                    pass                    # k-sigma: unpredictable, ignore
        if keep >= 100:
            return n_frames
        return max(1, int(n_frames * keep / 100))

    def _stack(self, seq: str, out_name: str, n_frames: int) -> None:
        # Choose rejection for the number of frames that will really be
        # integrated, not the number that was staged.
        n_eff = self._effective_frame_count(n_frames)
        rej_tokens, rej_label = _rejection_args(
            n_eff, self._opts.get("rejection", True))
        args = ["stack", seq] + rej_tokens
        args += ["-norm=addscale"]
        if self._opts.get("output_norm", True):
            args += ["-output_norm"]

        # Frame weighting by weighted-FWHM lifts the sharpest subs -- only
        # meaningful once there are a few frames left to weight.
        if self._opts.get("weighting", True) and n_eff >= 3:
            args += ["-weight=wfwhm"]

        # Frame quality filtering already happened at registration time
        # (see _quality_filter_args), so the sequence handed to stack only
        # contains the frames that passed; -filter-included keeps it that way.
        if self._quality_filter_args(n_frames):
            args += ["-filter-included"]

        if self._opts.get("rejmap", False):
            args += ["-rejmap"]

        args += ["-32b", f"-out={out_name}"]
        n_txt = (f"n={n_frames}" if n_eff == n_frames
                 else f"n≈{n_eff} of {n_frames} after filtering")
        self._emit(f"  Rejection: {rej_label} ({n_txt})", LogColor.BLUE)
        self._emit("  " + " ".join(args), LogColor.BLUE)
        self._cmd(*args)

    # -- per-filter stacking ---------------------------------------------
    def _stack_all_filters(self, reuse: dict | None = None
                           ) -> tuple[dict, dict, str | None]:
        """Stack every discovered filter into a per-filter master.

        ``reuse`` maps filter -> existing master path; those filters are
        kept as-is instead of being re-stacked (partial reuse).  Returns
        ``(results, errors, last_result)`` where results maps
        filter -> master path.
        """
        reuse = reuse or {}
        results: dict[str, str] = {}
        errors: dict[str, str] = {}
        last_result = None
        filters = list(self._groups.keys())
        n_f = len(filters)

        for fi, filt in enumerate(filters):
            # Cooperative abort: a Siril command cannot be interrupted
            # mid-flight, so we stop between filters -- the last finished
            # master stays valid.
            if self.isInterruptionRequested():
                self._emit("Aborted by user — stopping after the current "
                           "filter.", LogColor.SALMON)
                break
            # Stacking occupies 5..75% of the bar; alignment, composition and
            # the finish steps get the rest, so the tail isn't one big jump.
            base_prog = int(5 + 70 * fi / max(1, n_f))
            if filt in reuse:
                self._emit(f"=== Filter {filt}: reusing existing master "
                           f"({os.path.basename(reuse[filt])}) ===",
                           LogColor.GREEN)
                results[filt] = reuse[filt]
                last_result = reuse[filt]
                continue
            self.progress.emit(
                base_prog, f"Stacking {filt} ({fi + 1}/{n_f})...")
            files = self._groups[filt]["files"]
            self._emit(
                f"=== Filter {filt}: {len(files)} light frame(s) ===",
                LogColor.GREEN)

            work = os.path.join(self._out_dir, WORK_DIRNAME, "sequences",
                                self._tok(filt))
            lights_dir = os.path.join(work, "lights")
            if os.path.isdir(work):
                shutil.rmtree(work, ignore_errors=True)
            n_linked = self._link_frames(files, lights_dir)
            self._emit(
                f"  Staged {n_linked} frame(s) into {lights_dir}",
                LogColor.BLUE)
            if n_linked < 2:
                msg = (f"only {n_linked} usable frame(s); need at least 2 "
                       "to register and stack.")
                self._emit(f"  Skipping {filt}: {msg}", LogColor.SALMON)
                errors[filt] = msg
                continue

            try:
                # cd INTO the per-filter lights dir: link/convert reads the
                # frames from the current directory and writes the "lights"
                # sequence to ../process (i.e. work/<filter>/process), which
                # is unique per filter.
                self._cmd("cd", f'"{lights_dir}"')

                # FITS (incl. Rice-compressed .fits.fz) -> link is instant;
                # anything else needs convert.
                conv = "link" if _is_fits_like(_fits_ext(files[0])) \
                    else "convert"
                self._cmd(conv, "lights", "-out=../process")
                self._cmd("cd", "../process")

                seq = "lights"
                if self._opts.get("bg_extract", False):
                    self._emit("  Extracting background gradient...",
                               LogColor.BLUE)
                    self._cmd("seqsubsky", seq, "1", "-samples=10")
                    seq = f"bkg_{seq}"

                self._current_n_frames = n_linked
                self._stacked_counts[filt] = (
                    n_linked, self._effective_frame_count(n_linked))
                self._emit("  Registering frames...", LogColor.BLUE)
                seq = self._register(seq)

                # Full-frame (uncropped) per-channel master.  Kept in
                # masters/ as *_fullframe; the aligned/cropped version is
                # produced later by _align_masters as TARGET_FILTER.fit.
                out_name = f"{_safe(self._target)}_{self._tok(filt)}_fullframe"
                self._emit("  Integrating...", LogColor.BLUE)
                self._stack(seq, out_name, n_linked)

                produced = os.path.join(work, "process",
                                        f"{out_name}{self._ext}")
                masters_dir = os.path.join(self._out_dir, MASTERS_DIRNAME)
                os.makedirs(masters_dir, exist_ok=True)
                final = os.path.join(masters_dir, f"{out_name}{self._ext}")
                if os.path.exists(produced):
                    if os.path.exists(final):
                        os.remove(final)
                    shutil.copy2(produced, final)
                    # Per-channel background extraction on the linear master --
                    # gradients differ per filter, so removing them before the
                    # channels are combined works better than one pass on the
                    # finished colour image.
                    if self._opts.get("bg_master", True):
                        self._bg_extract_master(final)
                    results[filt] = final
                    last_result = final
                    self._emit(
                        f"  -> {os.path.basename(final)}", LogColor.GREEN)
                else:
                    errors[filt] = "stack produced no output file."
                    self._emit(
                        f"  {filt}: stack produced no output.", LogColor.RED)

                # Return to a neutral directory before the next filter.
                self._cmd("cd", f'"{self._out_dir}"')
                try:
                    self._cmd("close")
                except (CommandError, DataError, SirilError):
                    pass
            except (CommandError, DataError, SirilError) as exc:
                errors[filt] = str(exc)
                self._emit(f"  {filt} failed: {exc}", LogColor.RED)

        return results, errors, last_result

    def _write_stub_report(self) -> None:
        """Write a brief output.md (replaced by the full report when done)."""
        txt = (
            "# Svenesis ImageMono Train — output\n\n"
            "Processing is running… the **full report** is written to this "
            "file when the run finishes.\n\n"
            "**Folder layout**\n\n"
            "- `TARGET_<palette>.fit` — the finished colour image (linear)\n"
            "- `masters/` — per-channel masters "
            "(`*_fullframe` = full field, the others are aligned)\n"
            "- `_work/` — intermediate files, safe to delete\n"
            "- `todo.md` — step-by-step final-processing guide\n")
        self._write_file("output.md", txt)

    def _write_file(self, name: str, text: str) -> None:
        try:
            with open(os.path.join(self._out_dir, name),
                      "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            _log_swallowed(exc)

    def _write_docs(self, final_paths: dict, composite, errors: dict,
                    did_align: bool, reused: bool,
                    partial_reuse: list | None = None) -> None:
        """Write output.md (detailed report) and todo.md (next steps)."""
        opts = self._opts
        palette = opts.get("compose_palette", "RGB")
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts = "(unknown)"
        comp_name = os.path.basename(composite) if composite else None

        L: list[str] = []
        A = L.append
        A("# 🌌 Svenesis ImageMono Train — Processing Report")
        A("")
        A(f"- **Target:** {self._target}")
        A(f"- **Generated:** {ts}")
        A(f"- **Script version:** {VERSION}")
        if opts.get("preset"):
            A(f"- **Preset:** {opts['preset']}")
        A("")
        A("This folder was produced automatically from your N.I.N.A. light "
          "frames. The script stacked each filter, aligned the channels, and "
          "combined them into a colour image. **Every image here is still "
          "_linear_** (not stretched) — the final, creative processing is up "
          "to you and is described in **[`todo.md`](todo.md)**.")
        A("")
        A("---")
        A("")

        # 1 · Folder contents ------------------------------------------------
        A("## 1 · What's in this folder")
        A("")
        A("| File / folder | What it is |")
        A("| --- | --- |")
        if comp_name:
            A(f"| **`{comp_name}`** | Your finished colour image — linear & "
              "calibrated. **Start here.** |")
        A("| `masters/…_<FILTER>.fit` | Per-channel master, **aligned** to a "
          "common grid — use these to combine channels. |")
        A("| `masters/…_<FILTER>_fullframe.fit` | The same channel at "
          "**full, uncropped** size. |")
        A("| `_work/` | All intermediate files. **Safe to delete** any "
          "time. |")
        A("| `output.md` | This report — what the script did, step by step. |")
        A("| `todo.md` | Step-by-step guide for the final image processing. |")
        A("")
        A("---")
        A("")

        # 2 · Input frames ---------------------------------------------------
        A("## 2 · The frames that went in")
        A("")
        A("| Filter | Found | Stacked | Integration | Rejection used |")
        A("| --- | ---: | ---: | ---: | --- |")
        total = 0
        total_exp = 0.0
        any_reduced = False
        for filt in sorted(self._groups):
            g = self._groups[filt]
            n = len(g.get("files", []))
            total += n
            exp = g.get("exp_total", 0.0)
            # Quote what was really integrated: blank frames and the quality
            # filters both shrink the set, and the rejection algorithm was
            # chosen for that smaller number.
            staged, effective = self._stacked_counts.get(filt, (n, n))
            _tok, rej_label = _rejection_args(
                effective, opts.get("rejection", True))
            # Integration time must follow the frames that were really
            # integrated, not the ones that were merely found.
            exp_used = exp * effective / n if n else 0.0
            if effective != n:
                any_reduced = True
                used = f"**{effective}**"
            else:
                used = str(effective)
            total_exp += exp_used
            A(f"| {filt} | {n} | {used} | {_format_duration(exp_used)} "
              f"| {rej_label} |")
        A("")
        A(f"**Total:** {total} light frame(s) found across "
          f"{len(self._groups)} filter(s) — "
          f"**{_format_duration(total_exp)}** actually integrated.")
        if any_reduced:
            A("")
            A("> The **Stacked** column is lower than **Found** where blank "
              "frames were dropped or the quality filters removed subs.  The "
              "rejection algorithm was chosen for that smaller number.")
        if self._blank_skipped:
            A("")
            A(f"> ⚠️ **{self._blank_skipped} blank/black frame(s)** were "
              "detected and left out of the stack (all-zero or dead-flat — "
              "e.g. a failed download or a closed flap).")
        if reused:
            A("")
            A("> ℹ️ **Masters were reused** from a previous run — the stacking "
              "and alignment below were skipped this time; only the colour "
              "image was rebuilt.")
        elif partial_reuse:
            A("")
            A(f"> ℹ️ **Partial reuse:** the existing master(s) for "
              f"**{', '.join(sorted(partial_reuse))}** were kept from an "
              "earlier run; only the remaining filters were stacked again. "
              "The channels were then re-aligned together.")
        A("")
        A("---")
        A("")

        # 3 · What the script did -------------------------------------------
        A("## 3 · Exactly what the script did")
        A("")
        if not reused:
            A("### 3.1 · Building each channel master")
            A("")
            A("For **every filter**, the raw lights were turned into one "
              "master light:")
            A("")
            A("1. **Staging & linking** — the frames were linked into a Siril "
              "sequence (`link`). Compressed `.fits.fz` files are read "
              "directly, and nothing is ever debayered (this is a mono "
              "workflow)."
              + ((f" Blank / black frames were checked for — "
                  f"{self._blank_skipped} dropped."
                  if self._blank_skipped else
                  " Blank / black frames were checked for; none were found.")
                 if opts.get("skip_blank", True) else ""))
            if opts.get("bg_extract"):
                A("2. **Per-sub background** — a gradient was removed from "
                  "every individual sub before registration (`seqsubsky`).")
            A(("3." if opts.get("bg_extract") else "2.")
              + " **Registration** — 2-pass global star alignment "
              "(`register -2pass` → `seqapplyreg`). Siril picks the sharpest "
              "frame as the reference and aligns every other frame to it with "
              "sub-pixel accuracy.")
            # The quality filters run as part of seqapplyreg, so they belong
            # under Registration -- not under the framing bullet below.
            qf = []
            mode = ("k sigma" if opts.get("filter_mode") == "k-sigma"
                    else "% best")
            for key, label in (("f_wfwhm", "weighted FWHM"),
                               ("f_round", "roundness"),
                               ("f_stars", "star count"),
                               ("f_bkg", "background")):
                if opts.get(key + "_on"):
                    qf.append(f"{label} {opts.get(key + '_val', 90)}"
                              + ("k" if mode == "k sigma" else "%"))
            if qf:
                # Say plainly whether they actually fired this run: listing
                # the settings alone would imply frames were dropped.
                applied = [f for f, (st, ef) in self._stacked_counts.items()
                           if ef < st]
                if applied:
                    where = (f"They applied to {', '.join(sorted(applied))} "
                             "(the filters with enough frames).")
                else:
                    where = (f"They did **not** apply this run — no filter "
                             f"reached {FILTER_MIN_FRAMES} frames, and on "
                             "shorter sets losing a sub costs more "
                             "signal-to-noise than the worst frame costs "
                             "sharpness.")
                A("    - **Frame quality filters configured:** "
                  + ", ".join(qf) + f".  {where}")
            if opts.get("crop_edges", True):
                frm = ("**Framing `min`** — only the area covered by *every* "
                       "frame is kept, so the master has no ragged, "
                       "low-signal edges.")
            else:
                frm = ("**Framing `max`** — the full field is kept (the edges "
                       "may be only partly exposed).")
            drz = opts.get("drizzle", 1)
            drz_txt = (f" Drizzle **{drz}×** upscaling was applied."
                       if drz and drz > 1 else "")
            A(("4." if opts.get("bg_extract") else "3.")
              + f" {frm}{drz_txt}")
            A(("5." if opts.get("bg_extract") else "4.")
              + " **Integration** (`stack`):")
            A("    - **Rejection** is chosen automatically from each filter's "
              "frame count (see the table above) — percentile clipping for "
              "few frames, Winsorized sigma for more, linear-fit for large "
              "sets. Sigma-based methods need enough frames to work, so "
              "few-frame channels use gentler percentile clipping.")
            A("    - **Normalization:** additive + scaling — matches the "
              "background level and brightness of every sub before averaging.")
            A("    - **Weighting:** by weighted-FWHM — sharper subs contribute "
              "more.")
            A("    - **Bit depth:** 32-bit float"
              + (", output-normalized." if opts.get("output_norm", True)
                 else "."))
            if opts.get("bg_master", True):
                A(("6." if opts.get("bg_extract") else "5.")
                  + " **Background extraction** (`subsky`, degree 1) — the sky "
                  "gradient was removed from each finished master while still "
                  "linear (gradients differ per filter, so this works better "
                  "per channel than once on the colour image).")
            A("")
            A("→ saved as `masters/<TARGET>_<FILTER>_fullframe.fit`.")
            A("")
            if did_align:
                A("### 3.2 · Aligning the channels to each other")
                A("")
                A("Each filter is stacked against its *own* reference, so the "
                  "masters can sit on slightly different pixel grids — the "
                  "colour channels wouldn't line up. To fix that, all masters "
                  "were pooled and re-registered onto **one common grid** "
                  "(`seqapplyreg -framing=min`), producing **pixel-identical** "
                  "channels:")
                A("")
                A("→ `masters/<TARGET>_<FILTER>.fit` (these feed the colour "
                  "image).")
                A("")
        if opts.get("platesolve_master"):
            A("The per-filter masters were also **plate-solved** (a WCS / sky "
              "coordinate solution was written into each).")
            A("")

        if composite:
            A(f"### 3.3 · Building the colour image ({palette})")
            A("")
            mp = []
            for role, key in (("R", "map_red"), ("G", "map_green"),
                              ("B", "map_blue"), ("L", "map_lum")):
                v = opts.get(key, "")
                if v:
                    mp.append(f"**{role}** = {v}")
            A("**Channel mapping:** " + " · ".join(mp))
            A("")
            if palette in ("SHO", "HOO") and opts.get("nb_normalize", True):
                A("- **Normalized** the channels to the Ha reference "
                  "(`linear_match`) first, so the strong Ha doesn't dominate "
                  "and turn the result green.")
            if palette == "HaRGB":
                A(f"- **Blended Ha into Red** at "
                  f"{int(opts.get('ha_strength', 50))}% (a PixelMath screen "
                  "blend) for stronger emission-nebula detail.")
            baked = palette == "LRGB" and opts.get("quick_lrgb")
            A("- **Combined** the channels with `rgbcomp`"
              + (" (luminance baked in linearly — the *quick* mode)." if baked
                 else "."))
            if self._separate_lum:
                A(f"- The **luminance** master "
                  f"(`masters/{os.path.basename(self._separate_lum)}`) was "
                  "kept **separate** — combining it after stretching gives "
                  "much better colour (this is Siril's recommended order).")
            A("")
            if opts.get("finish", True) and self._finish_steps:
                A("**Auto-finish** (each step is resilient — a failure is "
                  "logged and skipped, never fatal):")
                A("")
                for i, step in enumerate(self._finish_steps, 1):
                    A(f"{i}. {step}")
                A("")
            A(f"→ saved **linear** as `{comp_name}`.")
            A("")
        else:
            A("### 3.3 · Colour image")
            A("")
            A("No colour composite was produced this run.")
            A("")

        # 4 · Linear note ----------------------------------------------------
        A("---")
        A("")
        A("## 4 · Important — this image is still _linear_")
        A("")
        A("A linear image looks almost black: the faint galaxy / nebula "
          "signal sits just above the background. Colour calibration (PCC) "
          "**must** run on linear data, which is why the script stops here. "
          "The next step — **stretching** — is creative and best done by eye.")
        A("")
        A("👉 Open **[`todo.md`](todo.md)** for a step-by-step guide.")
        A("")

        # 5 · Good to know ---------------------------------------------------
        A("## 5 · Good to know")
        A("")
        A("- **No calibration frames** (darks / flats / bias) were used. "
          "Without flats you may see some vignetting and dust shadows — "
          "apply calibration beforehand for the cleanest result.")
        A("- Keep the **linear masters** in `masters/`; you can redo the "
          "processing from any step without re-stacking.")
        if errors:
            A("")
            A("### Skipped / failed")
            A("")
            for f, m in errors.items():
                A(f"- **{f}:** {m}")
        A("")
        A("---")
        A(f"_Generated by Svenesis ImageMono Train v{VERSION}._")
        self._write_file("output.md", "\n".join(L) + "\n")

        self._write_file("todo.md", self._todo_text(palette, composite))

    def _todo_text(self, palette: str, composite) -> str:
        target = self._target
        comp = os.path.basename(composite) if composite else \
            "your colour image"
        lum = (f"masters/{os.path.basename(self._separate_lum)}"
               if self._separate_lum else None)
        S: list[str] = []
        A = S.append

        A(f"# 🎨 Final Processing — {target} ({palette})")
        A("")
        A("Everything the script produced is **linear** and colour-calibrated. "
          "The steps below are the *creative*, non-linear part — they're yours "
          "to taste. Do them in **Siril** (or PixInsight / Photoshop / "
          "Affinity Photo).")
        A("")
        A("> 💡 **Work on a copy**, and keep the linear masters in `masters/` "
          "so you can always redo from any step.")
        A("")
        A("> 📖 New to this? The three stages are always: **(1) flatten the "
          "background → (2) calibrate colour (already done for you) → "
          "(3) stretch**, and only *then* the artistic touches. Stretching "
          "before calibrating ruins the colour, which is why the script "
          "hands the image over still linear.")
        A("")
        A("---")
        A("")

        if palette in ("LRGB", "RGB", "HaRGB"):
            A(f"## Part A — Colour (open `{comp}`)")
            A("")
            A("1. **Background check.** If a gradient still shows, run "
              "*Image Processing → Background Extraction* (degree 1, "
              "**Subtract**). A flat background is essential before stretching.")
            if palette == "HaRGB":
                A("2. **White balance.** PCC was **not** applied (the Red "
                  "channel carries Ha, so star photometry is invalid). Set the "
                  "balance by hand: *Image Processing → Color Calibration*, "
                  "pick a neutral background reference.")
            else:
                A("2. **White balance.** The colour is already "
                  "**PCC-calibrated** — leave the white balance as it is.")
            A("3. **Stretch.** Use *Histogram Transformation* or *GHS "
              "(Generalised Hyperbolic Stretch)*. Aim for a **neutral grey "
              "background** around 0.10–0.15 and don't clip the bright stars. "
              "This is the single most impactful step — take your time.")
            A("4. **Denoise** *(optional)* — reduce colour noise now while "
              "it's easy.")
            A("5. **Saturation** *(optional)* — boost gently for richer "
              "colour.")
            A("")
            if lum:
                A(f"## Part B — Luminance (open `{lum}`)")
                A("")
                A("6. **Sharpen while linear** *(optional)* — deconvolution or "
                  "a tool like BlurXTerminator. The luminance carries all the "
                  "fine detail, so this is where sharpening pays off most.")
                A("7. **Stretch L** to taste — this defines the contrast and "
                  "detail of the final image.")
                A("8. **Denoise, then sharpen** *(optional)*.")
                A("")
                A("## Part C — Combine L + RGB  *(do this LAST)*")
                A("")
                A("9. With **both already stretched**, combine them: in Siril "
                  "use *Image Processing → RGB composition* with the "
                  "**luminance** slot, or the command "
                  "`rgbcomp -lum=<stretched L> <stretched RGB>`. The luminance "
                  "supplies detail, the RGB supplies colour.")
                A("10. **Final touches** — curves, local contrast, star "
                  "reduction, crop the edges.")
                A("11. **Export** a 16-bit TIFF or PNG.")
            else:
                A("## Part B — Finish")
                A("")
                A("6. **Final touches** — curves, local contrast, star "
                  "reduction, crop the edges.")
                A("7. **Export** a 16-bit TIFF or PNG.")
            A("")
            A("---")
            A("")
            A("### Tips")
            A("- To reuse an existing luminance next time, keep the palette on "
              "**LRGB** — the script keeps L separate automatically.")
            A("- Re-run with **Reuse existing masters** ticked to try another "
              "palette in seconds (no re-stacking).")
            return "\n".join(S) + "\n"

        # Narrowband SHO / HOO
        A(f"## Narrowband (open `{comp}`)")
        A("")
        A("1. **Starting point.** The channels were already normalized to Ha, "
          "so the image is balanced — not the pure-green you'd get from a raw "
          "SHO combine.")
        A("2. **Background check** *(optional)* — *Image Processing → "
          "Background Extraction* (degree 1) if a gradient remains.")
        A("3. **Stretch.** *Histogram* or *GHS*. Keep the background neutral "
          "and dark.")
        A("4. **Colour balance** to the look you want (the classic Hubble "
          "gold/teal): per-channel *Curves*, or Siril's colour tools. A "
          "little goes a long way.")
        A("5. **SCNR** (remove green) again if a green cast or green stars "
          "reappear after stretching.")
        A("6. **Denoise** — narrowband is noisier than broadband — then "
          "**boost saturation** for the vivid emission-line colours.")
        A("7. **Star reduction** *(recommended)* — SHO stars look best small; "
          "or replace them with round RGB stars for natural colours.")
        A("8. **Final** contrast / curves, crop the borders.")
        A("9. **Export** a 16-bit TIFF or PNG.")
        A("")
        A("---")
        A("")
        A("### Tips")
        A("- A separate broadband **RGB run** gives you natural star colours "
          "to blend over the narrowband nebula.")
        A("- Re-run with **Reuse existing masters** ticked to try HOO (or "
          "LRGB) on the same data in seconds.")
        return "\n".join(S) + "\n"

    # -- main -------------------------------------------------------------
    def run(self) -> None:
        try:
            os.makedirs(self._out_dir, exist_ok=True)
            self._write_stub_report()
            filters = list(self._groups.keys())
            errors: dict[str, str] = {}
            last_result = None
            did_align = False

            # ---- reuse of earlier results --------------------------------
            # Two levels, both opt-in via "Reuse existing masters":
            #   full    - every ALIGNED master exists  -> skip stacking AND
            #             alignment (a new palette costs only the compose)
            #   partial - some FULLFRAME masters exist -> stack only the
            #             filters that are missing, then re-align everything
            # Whatever is skipped is always logged, so a silent full re-stack
            # can never be mistaken for reuse.
            mdir = os.path.join(self._out_dir, MASTERS_DIRNAME)
            want_reuse = self._opts.get("reuse_masters", False)
            aligned_paths = {
                filt: os.path.join(
                    mdir, f"{_safe(self._target)}_{self._tok(filt)}{self._ext}")
                for filt in filters}
            full_paths = {
                filt: os.path.join(
                    mdir,
                    f"{_safe(self._target)}_{self._tok(filt)}_fullframe{self._ext}")
                for filt in filters}
            missing_aligned = [f for f, p in aligned_paths.items()
                               if not os.path.exists(p)]
            reusable_full = {f: p for f, p in full_paths.items()
                             if os.path.exists(p)}
            reuse_ok = bool(want_reuse and filters and not missing_aligned)
            partial_reuse: list = []

            if reuse_ok:
                self._emit(
                    f"Reusing {len(aligned_paths)} existing aligned master(s) "
                    "— skipping stacking and alignment.", LogColor.GREEN)
                results = dict(aligned_paths)
                final_paths = dict(aligned_paths)
                did_align = True          # the reused masters are aligned
            else:
                if want_reuse:
                    shown = ", ".join(missing_aligned[:4]) + (
                        "…" if len(missing_aligned) > 4 else "")
                    self._emit(
                        f"Full reuse not possible — no aligned master for: "
                        f"{shown}.", LogColor.SALMON)
                # Partial reuse: keep the fullframe masters we already have.
                skip = set(reusable_full) if want_reuse else set()
                partial_reuse = sorted(skip)
                if skip:
                    self._emit(
                        f"Partial reuse: keeping {len(skip)} existing master(s) "
                        f"({', '.join(sorted(skip))}); stacking the rest.",
                        LogColor.GREEN)
                results, errors, last_result = self._stack_all_filters(
                    reuse={f: reusable_full[f] for f in skip})

                # Cross-filter alignment: register the per-filter masters to a
                # common grid so LRGB / SHO channels overlay pixel-for-pixel.
                # Composition needs one identical grid, so it implies
                # alignment even if the user left that box unchecked.
                final_paths = dict(results)
                want_compose = self._opts.get("compose", False)
                do_align = (self._opts.get("align_filters", True)
                            or want_compose)
                if do_align and len(results) >= 2:
                    self.progress.emit(78, "Aligning filters to each other...")
                    if (want_compose
                            and not self._opts.get("align_filters", True)):
                        self._emit(
                            "Aligning filters (required for colour "
                            "composition).", LogColor.BLUE)
                    aligned = self._align_masters(results)
                    if aligned:
                        final_paths = aligned
                        did_align = True

            want_compose = self._opts.get("compose", False)

            # Optional: plate-solve the final masters so they carry a WCS.
            if self._opts.get("platesolve_master", False):
                n_m = max(1, len(final_paths))
                for i, (filt, path) in enumerate(list(final_paths.items())):
                    self.progress.emit(
                        int(84 + 6 * i / n_m),
                        f"Plate-solving masters ({i + 1}/{n_m})...")
                    self._platesolve_file(path)

            # Optional: combine the aligned masters into a colour composite.
            composite = None
            composite_load = None
            if want_compose and len(final_paths) >= 3:
                self.progress.emit(90, "Composing colour image...")
                composite = self._compose(final_paths)
                composite_load = composite
                if composite and self._opts.get("finish", True):
                    self.progress.emit(
                        94, "Finishing composite (background + colour)...")
                    composite_load = self._finish_composite(composite)
            elif want_compose:
                self._emit(
                    "Colour composition skipped: need at least 3 filters "
                    "(R, G, B).", LogColor.SALMON)

            # Load the colour composite if we made one, else the last master.
            last = composite_load or (list(final_paths.values())[-1]
                                      if final_paths else last_result)
            if last and self._opts.get("load_result", True):
                try:
                    self._cmd("load", f'"{last}"')
                except (CommandError, DataError, SirilError) as exc:
                    _log_swallowed(exc)

            # Processing report + step-by-step post-processing guide.
            self.progress.emit(98, "Writing report...")
            self._write_docs(final_paths, composite, errors, did_align,
                             reuse_ok, partial_reuse)

            # Optional: drop the intermediates now that everything worked.
            # Only on success, and only when at least one master survived --
            # never delete the evidence of a run that produced nothing.
            if self._opts.get("cleanup_work", False) and final_paths:
                work_root = os.path.join(self._out_dir, WORK_DIRNAME)
                try:
                    # Siril may still hold the last sequence open in there.
                    self._cmd("cd", f'"{self._out_dir}"')
                except (CommandError, DataError, SirilError) as exc:
                    _log_swallowed(exc)
                if os.path.isdir(work_root):
                    shutil.rmtree(work_root, ignore_errors=True)
                    self._emit(
                        "Cleaned up intermediates (_work/ removed).  The "
                        "masters in masters/ are untouched, so master reuse "
                        "still works next time.", LogColor.BLUE)

            self.progress.emit(100, "Done.")
            self.finished.emit(
                {"results": final_paths, "errors": errors,
                 "aligned": did_align,
                 "composite": composite,
                 "finished": bool(composite and self._opts.get("finish", True)),
                 "preview": (composite_load
                             if composite_load != composite else None),
                 "separate_lum": self._separate_lum})
        except Exception as exc:
            # Never leave the "processing is running…" stub behind: replace it
            # with an honest failure report so the folder explains itself.
            self._write_failure_report(exc, traceback.format_exc())
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")

    def _write_failure_report(self, exc: BaseException, tb: str) -> None:
        """Replace output.md with a failure report when a run blows up."""
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts = "(unknown)"
        L = [
            "# ⚠️ Svenesis ImageMono Train — Run FAILED",
            "",
            f"- **Target:** {self._target}",
            f"- **Failed at:** {ts}",
            f"- **Script version:** {VERSION}",
            "",
            "This run did **not** finish. Anything already in `masters/` is "
            "from an earlier, successful run — do not trust files written "
            "during this attempt.",
            "",
            "## What went wrong",
            "",
            "```",
            f"{type(exc).__name__}: {exc}",
            "```",
            "",
            "## What to try",
            "",
            "1. Check the **Log** tab in the script window — the last few "
            "lines usually name the Siril command that failed.",
            "2. Make sure Siril is still running and no other tool is using "
            "the same working directory.",
            "3. If a filter has too few usable frames, it is skipped — that "
            "is normal and not an error.",
            "4. Re-run. If it fails again at the same step, the details "
            "below help pin it down.",
            "",
            "<details><summary>Technical traceback</summary>",
            "",
            "```",
            tb.strip(),
            "```",
            "",
            "</details>",
            "",
            "---",
            f"_Generated by Svenesis ImageMono Train v{VERSION}._",
        ]
        self._write_file("output.md", "\n".join(L) + "\n")

    # -- colour composition ----------------------------------------------
    def _compose(self, paths: dict) -> str | None:
        """Combine the aligned per-filter masters into one colour image.

        Uses Siril's ``rgbcomp`` (``-lum=`` for LRGB) on the channel mapping
        chosen in the UI.  Inputs must be identical in size -- guaranteed
        because they come from the ``-framing=min`` alignment step.  Returns
        the composite path, or None if a required channel is missing.
        """
        m_lum = self._opts.get("map_lum", "")
        m_red = self._opts.get("map_red", "")
        m_green = self._opts.get("map_green", "")
        m_blue = self._opts.get("map_blue", "")
        palette = self._opts.get("compose_palette", "RGB")

        for role, fname in (("red", m_red), ("green", m_green),
                            ("blue", m_blue)):
            if not fname or fname not in paths:
                self._emit(
                    f"  Colour composition skipped: no aligned master mapped "
                    f"to the {role.upper()} channel.", LogColor.SALMON)
                return None

        # LRGB best practice (Siril docs): compose R,G,B ONLY, colour-calibrate
        # that linear RGB, and combine luminance AFTER stretching -- baking L
        # in linearly skews PCC and gives weak colour.  So by default L is kept
        # separate; the "quick" option restores the one-step linear LRGB.
        quick = self._opts.get("quick_lrgb", False)
        use_lum = (bool(m_lum) and m_lum in paths
                   and palette == "LRGB" and quick)
        # Name reflects the actual content: RGB-only vs L baked in.
        out_label = palette
        if palette == "LRGB" and not use_lum:
            out_label = "RGB"
        self._separate_lum = None
        if palette in ("LRGB", "HaRGB") and not use_lum and m_lum in paths:
            # L is calibrated/kept on its own for the post-stretch combine.
            self._separate_lum = paths[m_lum]

        # rgbcomp does NOT honour quoted paths the way cd/load/save do, so a
        # space in the folder (e.g. a Dropbox "Pinwheel Galaxy" dir) splits
        # the filename.  Work around it: cd into the folder that holds the
        # masters and pass BARE BASENAMES (underscored, space-free), with a
        # relative -out.  All mapped masters live in the same directory.
        in_dir = os.path.dirname(paths[m_red])
        # Compose helpers (_nbnorm / _RED_Ha) are written under _work/helpers
        # so masters/ stays clean.  Referenced relative to the masters dir
        # (space-free, so rgbcomp/pm are happy).
        helpers = os.path.join(self._out_dir, WORK_DIRNAME, "helpers")
        os.makedirs(helpers, exist_ok=True)
        helpers_rel = os.path.relpath(helpers, in_dir)
        try:
            self._cmd("cd", f'"{in_dir}"')
            red_basename = os.path.basename(paths[m_red])
            green_basename = os.path.basename(paths[m_green])
            blue_basename = os.path.basename(paths[m_blue])

            # Narrowband normalization (Siril's recommendation): before
            # combining SHO/HOO, linear-match each channel to the Ha
            # reference so the strong Ha doesn't dominate and turn the
            # result green.  Matched copies (*_nbnorm) are written so the
            # original aligned masters stay untouched.
            if (palette in ("SHO", "HOO")
                    and self._opts.get("nb_normalize", True)):
                ref_filter = next(
                    (f for f in (m_red, m_green, m_blue)
                     if _filter_role(f) == "ha"), m_green)
                ref_base = os.path.basename(paths[ref_filter])
                # 32-bit images live in [0,1]; ignore near-saturated stars.
                low, high = "0", "0.92"
                norm_cache: dict = {}

                def _norm(fname):
                    if fname == ref_filter:
                        return os.path.basename(paths[fname])   # reference
                    if fname in norm_cache:
                        return norm_cache[fname]
                    src = os.path.basename(paths[fname])
                    out = os.path.join(
                        helpers_rel, os.path.splitext(src)[0] + "_nbnorm")
                    self._cmd("load", src)
                    self._cmd("linear_match", ref_base, low, high)
                    self._cmd("save", out)
                    norm_cache[fname] = out + self._ext
                    return norm_cache[fname]

                self._emit(
                    f"  {out_label}: normalizing channels to {ref_filter} "
                    "(linear_match).", LogColor.BLUE)
                red_basename = _norm(m_red)
                green_basename = _norm(m_green)
                blue_basename = _norm(m_blue)

            # HaRGB: screen-blend the Ha master into the Red channel first,
            # then compose as usual.  Ha is located by filter role among the
            # aligned masters.  Values are in [0,1] (32-bit), so the screen
            # blend 1-(1-R)*(1-k*Ha) stays bounded -- no rescale needed.
            if palette == "HaRGB":
                ha_filter = next(
                    (f for f in paths if _filter_role(f) == "ha"), None)
                if ha_filter and ha_filter in paths:
                    k = max(0, min(100,
                                   int(self._opts.get("ha_strength", 50)))) / 100.0
                    r_var = os.path.splitext(
                        os.path.basename(paths[m_red]))[0]
                    ha_var = os.path.splitext(
                        os.path.basename(paths[ha_filter]))[0]
                    enhanced = os.path.join(
                        helpers_rel, f"{_safe(self._target)}_RED_Ha")
                    expr = f"1-(1-${r_var}$)*(1-{k:g}*${ha_var}$)"
                    self._emit(
                        f"  HaRGB: blending {ha_filter} into Red at "
                        f"{int(k * 100)}% (PixelMath).", LogColor.BLUE)
                    self._cmd("pm", f'"{expr}"')
                    self._cmd("save", f'"{enhanced}"')
                    red_basename = enhanced + self._ext
                else:
                    self._emit(
                        "  HaRGB: no Ha master found; composing plain RGB.",
                        LogColor.SALMON)
                    out_label = "RGB"

            out_path = os.path.join(
                self._out_dir, f"{_safe(self._target)}_{_safe(out_label)}")
            out_rel = os.path.relpath(out_path, in_dir)
            args = ["rgbcomp"]
            if use_lum:
                args.append(f"-lum={os.path.basename(paths[m_lum])}")
            args += [red_basename, green_basename, blue_basename,
                     f"-out={out_rel}"]
            self._emit(
                f"  Composing {out_label}: "
                + (f"L={m_lum} " if use_lum else "")
                + f"R={m_red} G={m_green} B={m_blue}"
                + ("  (L kept separate for post-stretch combine)"
                   if self._separate_lum else ""), LogColor.BLUE)
            self._emit("  " + " ".join(args), LogColor.BLUE)
            self._cmd(*args)

            result = out_path + self._ext
            if os.path.exists(result):
                self._emit(
                    f"  Colour composite -> {os.path.basename(result)}",
                    LogColor.GREEN)
                return result
            self._emit(
                "  rgbcomp produced no output file.", LogColor.RED)
            return None
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Colour composition failed: {exc}", LogColor.RED)
            return None

    def _bg_extract_master(self, path: str) -> None:
        """Background-extract a single linear per-filter master, in place."""
        ext = self._ext
        base = path[:-len(ext)] if path.lower().endswith(ext.lower()) else path
        try:
            self._cmd("load", f'"{path}"')
            self._cmd("subsky", "1", "-samples=20")
            self._cmd("save", f'"{base}"')
            self._emit("  Background extracted (per-channel master).",
                          LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Per-channel background extraction skipped ({exc}).",
                LogColor.SALMON)

    def _finish_composite(self, path: str) -> str:
        """Background-extract + colour-calibrate the composite in place.

        Runs, all resiliently (a failing step logs and is skipped, never
        aborts): plate-solve (PCC needs a WCS), background extraction,
        Photometric Colour Calibration, and SCNR green removal.  The
        calibrated *linear* result is saved over the composite.  If a
        stretched preview is requested, an autostretched copy is written
        alongside as ``*_preview`` and returned for loading.  Returns the
        path that should be loaded into Siril.
        """
        ext = self._ext
        base = path[:-len(ext)] if path.lower().endswith(ext.lower()) else path
        self._finish_steps = []
        try:
            self._cmd("load", f'"{path}"')
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Finish: could not load composite ({exc}).",
                          LogColor.SALMON)
            return path

        # Plate-solve so PCC has astrometry (rgbcomp output may lack a WCS).
        solved = True
        try:
            self._cmd("platesolve")
            self._finish_steps.append("Plate-solved the composite.")
        except (CommandError, DataError, SirilError) as exc:
            solved = False
            self._finish_steps.append("Plate-solve failed (colour "
                                      "calibration skipped).")
            self._emit(
                f"  Finish: plate-solve failed ({exc}); skipping colour "
                "calibration.", LogColor.SALMON)

        # Background / gradient extraction on the COMBINED image, before PCC.
        # Even with per-channel extraction, the freshly-combined RGB carries
        # its own residual gradient, and PCC explicitly wants a flat
        # background ("correct the image gradient first") for an accurate
        # colour solution -- so this runs regardless of the per-channel pass.
        try:
            self._cmd("subsky", "1", "-samples=20")
            self._finish_steps.append(
                "Extracted the background gradient (subsky, degree 1).")
            self._emit("  Finish: composite background extracted "
                          "(pre-PCC).", LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Finish: composite background extraction skipped ({exc}).",
                LogColor.SALMON)

        # Photometric Colour Calibration -- ONLY for true broadband (LRGB/RGB).
        # PCC calibrates real star colours against a photometric catalog; on
        # a narrowband palette (SHO/HOO) the "colours" are mapped emission
        # lines, and on HaRGB the Red channel is Ha-boosted -- in both cases
        # the photometry is invalid, so PCC is skipped.
        palette = self._opts.get("compose_palette", "RGB")
        is_broadband = palette in ("LRGB", "RGB")
        if solved and is_broadband:
            try:
                self._cmd("pcc")
                self._finish_steps.append(
                    "Photometric Colour Calibration (PCC, NOMAD catalog).")
                self._emit("  Finish: photometric colour calibration done.",
                              LogColor.GREEN)
            except (CommandError, DataError, SirilError) as exc:
                # Default catalog (NOMAD) is online; retry with the local
                # Gaia catalog, which works offline if it is installed.
                try:
                    self._cmd("pcc", "-catalog=localgaia")
                    self._finish_steps.append(
                        "Photometric Colour Calibration (PCC, local Gaia).")
                    self._emit(
                        "  Finish: photometric colour calibration done "
                        "(local Gaia).", LogColor.GREEN)
                except (CommandError, DataError, SirilError) as exc2:
                    self._finish_steps.append(
                        "PCC FAILED (no reachable catalog) — colour NOT "
                        "calibrated; set white balance manually.")
                    self._emit(
                        f"  Finish: PCC failed ({exc2}) — no reachable "
                        "photometry catalog; composite left uncalibrated.",
                        LogColor.SALMON)
        elif not is_broadband:
            why = ("Ha-boosted Red" if palette == "HaRGB"
                   else "mapped emission lines")
            self._finish_steps.append(
                f"PCC skipped ({palette}: {why}) — balance colour manually.")
            self._emit(
                f"  Finish: PCC skipped for {palette} ({why}); balance the "
                "channels manually.", LogColor.BLUE)

        # SCNR green removal (mono-narrowband / RGB both benefit).
        try:
            self._cmd("rmgreen")
            self._finish_steps.append("Removed the green cast (SCNR).")
        except (CommandError, DataError, SirilError) as exc:
            _log_swallowed(exc)

        # Save the calibrated LINEAR composite over the original.
        try:
            self._cmd("save", f'"{base}"')
            self._finish_steps.append(
                "Saved the calibrated, still-LINEAR composite.")
            self._emit(
                f"  Finish: calibrated composite saved "
                f"({os.path.basename(base)}{ext}).", LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Finish: save failed ({exc}).", LogColor.RED)

        load_path = path
        # Optional stretched, ready-to-view preview.
        if self._opts.get("finish_stretch", False):
            try:
                self._cmd("autostretch")
                preview = f"{base}_preview"
                self._cmd("save", f'"{preview}"')
                load_path = preview + ext
                self._emit(
                    f"  Finish: stretched preview saved "
                    f"({os.path.basename(preview)}{ext}).", LogColor.GREEN)
            except (CommandError, DataError, SirilError) as exc:
                self._emit(f"  Finish: preview stretch skipped ({exc}).",
                              LogColor.SALMON)
        return load_path

    # -- cross-filter alignment ------------------------------------------
    def _align_masters(self, results: dict) -> dict:
        """Register the per-filter masters onto one shared pixel grid.

        Each filter is stacked against its OWN reference frame, so the
        masters can sit on slightly different grids.  Here they are pooled
        into one tiny sequence, star-registered (2-pass auto-picks the
        richest frame -- usually Luminance -- as reference) and re-projected
        with ``-framing=min``, yielding ``masters/TARGET_FILTER.fit`` copies
        that are pixel-identical in size and overlay exactly for LRGB / SHO
        combination.  Returns ``{filter: aligned_path}`` (empty on failure).
        """
        try:
            adir = os.path.join(self._out_dir, MASTERS_DIRNAME)
            work = os.path.join(self._out_dir, WORK_DIRNAME, "align")
            lights = os.path.join(work, "masters")
            if os.path.isdir(work):
                shutil.rmtree(work, ignore_errors=True)
            os.makedirs(lights, exist_ok=True)
            os.makedirs(adir, exist_ok=True)

            # Zero-padded index prefixes fix the sequence order so each
            # registered frame maps back to a known filter.
            #
            # CRITICAL: the counter must advance ONLY for files that are
            # actually copied.  Siril's `link` numbers the files it finds
            # consecutively from 1, so skipping a missing master while still
            # consuming its index would shift every later channel by one --
            # silently writing e.g. the RED data into the LUMINOS master.
            ordered = sorted(results.items())
            index_to_filter = {}
            seq_idx = 0
            for filt, path in ordered:
                if not os.path.exists(path):
                    self._emit(
                        f"  Alignment: master for {filt} is missing "
                        "— excluding it from the colour image.",
                        LogColor.SALMON)
                    continue
                seq_idx += 1
                dst = os.path.join(
                    lights, f"{seq_idx:02d}_{self._tok(filt)}{self._ext}")
                shutil.copy2(path, dst)
                index_to_filter[seq_idx] = filt

            if len(index_to_filter) < 2:
                return {}

            self._cmd("cd", f'"{lights}"')
            self._cmd("link", "masters", "-out=../process")
            self._cmd("cd", "../process")
            try:
                self._cmd("register", "masters", "-2pass")
                # -framing=min (intersection) so every aligned master comes
                # out PIXEL-IDENTICAL in size and free of ragged missing-data
                # edges -- required for direct LRGB / SHO channel combination.
                # (max framing leaves per-channel canvases a few px apart.)
                self._cmd("seqapplyreg", "masters", "-framing=min")
            except (CommandError, DataError, SirilError):
                # Fall back to single-pass global registration.
                self._cmd("register", "masters")

            aligned: dict[str, str] = {}
            for idx, filt in index_to_filter.items():
                src = os.path.join(
                    work, "process", f"r_masters_{idx:05d}{self._ext}")
                if not os.path.exists(src):
                    continue
                out = os.path.join(
                    adir, f"{_safe(self._target)}_{self._tok(filt)}{self._ext}")
                if os.path.exists(out):
                    os.remove(out)
                shutil.copy2(src, out)
                aligned[filt] = out
                self._emit(
                    f"  Aligned {filt} -> {os.path.basename(out)}",
                    LogColor.GREEN)

            self._cmd("cd", f'"{self._out_dir}"')
            try:
                self._cmd("close")
            except (CommandError, DataError, SirilError):
                pass

            if aligned:
                self._emit(
                    f"Cross-filter alignment complete: {len(aligned)} master(s) "
                    "on a common grid (in 'masters/').", LogColor.GREEN)
            return aligned
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"Cross-filter alignment failed ({exc}); keeping "
                "per-filter masters.", LogColor.SALMON)
            return {}
        except Exception as exc:
            _log_swallowed(exc)
            return {}

    def _platesolve_file(self, path: str) -> None:
        """Load a master, plate-solve it, and save the WCS back in place."""
        try:
            self._cmd("load", f'"{path}"')
            self._cmd("platesolve")
            base = path
            for e in (".fits.fz", ".fit.fz", ".fits", ".fit", ".fts"):
                if base.lower().endswith(e):
                    base = base[:-len(e)]
                    break
            self._cmd("save", f'"{base}"')
            self._emit(
                f"  Plate-solved {os.path.basename(path)}", LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Plate-solve of {os.path.basename(path)} failed: {exc}",
                LogColor.SALMON)


def _safe(token: str) -> str:
    """Filesystem-safe version of a filter / target token."""
    keep = "".join(c if (c.isalnum() or c in "-_") else "_" for c in token)
    return keep.strip("_") or "X"


def _rejection_args(n: int, enabled: bool) -> tuple[list[str], str]:
    """Pick a stacking rejection algorithm suited to the frame count.

    Sigma-based methods (winsorized, linear fit) need enough frames to
    estimate a reliable per-pixel distribution; with only a handful of
    subs they reject poorly or over-aggressively.  Siril's guidance --
    and general practice -- is percentile clipping for small sets and
    winsorized / linear-fit for larger ones.  Returns ``(tokens, label)``.
    """
    if not enabled:
        return ["rej", "none"], "no rejection"
    if n <= 4:
        # Percentile clipping -- params are fractions, not sigmas.
        return ["rej", "percentile", "0.2", "0.1"], "percentile 0.2/0.1"
    if n <= 20:
        return ["rej", "winsorized", "3", "3"], "winsorized 3/3"
    # Large sets: linear fit handles residual gradients between subs well.
    return ["rej", "linear", "3", "3"], "linear fit 3/3"


# ---------------------------------------------------------------------------
# Colour-composition helpers: map filter names to R / G / B / L roles
# ---------------------------------------------------------------------------
# Exact (space-stripped, upper-cased) filter-name -> channel role.
_BROAD_ROLES = {
    "R": "red", "RED": "red", "ROT": "red",
    "G": "green", "GREEN": "green", "GRUEN": "green", "GRÜN": "green",
    "B": "blue", "BLUE": "blue", "BLAU": "blue",
    "L": "lum", "LUM": "lum", "LUMINANCE": "lum", "LUMINOS": "lum",
    "LUMINOSITY": "lum", "CLEAR": "lum",
}
_NB_ROLES = {
    "HA": "ha", "HALPHA": "ha", "H-ALPHA": "ha", "HALPHA3NM": "ha",
    "HYDROGEN": "ha",
    "SII": "sii", "S2": "sii", "SULPHUR": "sii", "SULFUR": "sii",
    "OIII": "oiii", "O3": "oiii", "OXYGEN": "oiii",
}


def _filter_role(name: str) -> str | None:
    """Best-guess R/G/B/L or Ha/OIII/SII role for a filter name."""
    key = "".join(str(name).upper().split())
    if key in _NB_ROLES:
        return _NB_ROLES[key]
    if key in _BROAD_ROLES:
        return _BROAD_ROLES[key]
    # Narrowband names are distinctive enough for a prefix match.
    for k, v in _NB_ROLES.items():
        if key.startswith(k):
            return v
    return None


def _detect_palette(filters: list[str]) -> str:
    """Choose a sensible default palette from the available filters.

    Only ever returns a palette whose three channels can actually be
    filled -- proposing e.g. HOO for an Ha-only night would leave Green and
    Blue empty and the composition would just refuse later.  Broadband
    wins over narrowband when both are complete, because R/G/B gives
    natural colour; switch to SHO/HOO manually for the mapped look.
    """
    roles = {_filter_role(f) for f in filters}
    has_rgb = {"red", "green", "blue"} <= roles
    if has_rgb:
        # Ha present too?  HaRGB needs the user to opt in (it disables PCC),
        # so the safe default stays plain LRGB / RGB.
        return "LRGB" if "lum" in roles else "RGB"
    if {"sii", "ha", "oiii"} <= roles:
        return "SHO"
    if {"ha", "oiii"} <= roles:
        return "HOO"
    # Nothing complete (e.g. a single filter): fall back to RGB so the
    # mapping combos stay usable; composition will say what is missing.
    return "RGB"


def _first_with_role(filters: list[str], role: str) -> str:
    for f in filters:
        if _filter_role(f) == role:
            return f
    return ""


def _auto_channel_map(filters: list[str], palette: str) -> dict:
    """Return {lum,red,green,blue: filtername} for a palette (''=unused)."""
    m = {"lum": "", "red": "", "green": "", "blue": ""}
    if palette == "Auto":
        palette = _detect_palette(filters)
    if palette in ("LRGB", "RGB", "HaRGB"):
        # HaRGB uses the same broadband R/G/B/L mapping; the Ha master is
        # located separately (by role) and blended into Red at compose time.
        m["red"] = _first_with_role(filters, "red")
        m["green"] = _first_with_role(filters, "green")
        m["blue"] = _first_with_role(filters, "blue")
        if palette in ("LRGB", "HaRGB"):
            m["lum"] = _first_with_role(filters, "lum")
    elif palette == "SHO":               # Hubble: S->R, H->G, O->B
        m["red"] = _first_with_role(filters, "sii")
        m["green"] = _first_with_role(filters, "ha")
        m["blue"] = _first_with_role(filters, "oiii")
    elif palette == "HOO":               # Ha->R, OIII->G+B
        m["red"] = _first_with_role(filters, "ha")
        m["green"] = _first_with_role(filters, "oiii")
        m["blue"] = _first_with_role(filters, "oiii")
    return m


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class ImageMonoTrainWindow(QMainWindow):
    """
    Main window for Svenesis ImageMono Train.

    Left panel: folder selection, discovered-filter table, stacking
    options, and actions.  Right panel: analysis summary and live log.
    """

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._root = ""
        self._groups: dict = {}
        self._target = ""
        self._ext = ".fit"
        self._analyze_worker: AnalyzeWorker | None = None
        self._stack_worker: StackWorker | None = None
        # Guard so applying a preset doesn't immediately flip it to "Custom".
        self._applying_preset = False
        # Set while a worker runs, so closing the window can offer to abort.
        self._busy = False
        # Distinct OBJECT names found by the last analysis (>1 = warn).
        self._multi_target: list = []

        self.init_ui()
        self._load_settings()
        self._connect_preset_watchers()

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------
    def init_ui(self) -> None:
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        self._left_panel = self._build_left_panel()
        layout.addWidget(self._left_panel)
        layout.addWidget(self._build_right_panel(), 1)
        self.setWindowTitle("Svenesis ImageMono Train")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 900)

    # ---- LEFT PANEL ---------------------------------------------------
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

        lbl = QLabel(f"Svenesis ImageMono Train {VERSION}")
        lbl.setStyleSheet(
            "font-size: 15pt; font-weight: bold; color: #88aaff; "
            "margin-top: 5px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._build_source_group(layout)
        self._build_filters_group(layout)
        self._build_options_group(layout)
        self._build_compose_group(layout)
        self._build_output_group(layout)
        self._build_action_buttons(layout)

        layout.addStretch()

        btn_coffee = QPushButton("☕  Buy me a Coffee")
        _nofocus(btn_coffee)
        btn_coffee.setObjectName("CoffeeButton")
        btn_coffee.setToolTip("Support the development of this tool")
        btn_coffee.clicked.connect(self._show_coffee_dialog)
        btn_help = QPushButton("Help")
        _nofocus(btn_help)
        btn_help.clicked.connect(self._show_help_dialog)
        self.btn_close = QPushButton("Close")
        _nofocus(self.btn_close)
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(btn_coffee)
        layout.addWidget(btn_help)
        layout.addWidget(self.btn_close)

        scroll.setWidget(content)

        outer = QVBoxLayout(left)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return left

    def _build_source_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Target Folder")
        layout = QVBoxLayout(group)

        self.btn_pick = QPushButton("\U0001F4C1  Select Target Folder…")
        _nofocus(self.btn_pick)
        self.btn_pick.setToolTip(
            "Pick the root folder of one target.  Everything below it is "
            "scanned for light frames.")
        self.btn_pick.clicked.connect(self._on_pick_folder)
        layout.addWidget(self.btn_pick)

        self.lbl_folder = QLabel("No folder selected.")
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setStyleSheet("color:#888888;font-size:9pt;")
        layout.addWidget(self.lbl_folder)

        self.btn_analyze = QPushButton("Analyze Folder")
        _nofocus(self.btn_analyze)
        self.btn_analyze.setToolTip(
            "Read every FITS header and group the LIGHT frames by filter.")
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_analyze.setEnabled(False)
        layout.addWidget(self.btn_analyze)

        parent_layout.addWidget(group)

    def _build_filters_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Discovered Filters")
        layout = QVBoxLayout(group)

        self.tbl_filters = QTableWidget(0, 4)
        self.tbl_filters.setHorizontalHeaderLabels(
            ["Filter", "Lights", "Integration", "Details"])
        self.tbl_filters.verticalHeader().setVisible(False)
        self.tbl_filters.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_filters.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        hdr = self.tbl_filters.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_filters.setMinimumHeight(130)
        layout.addWidget(self.tbl_filters)

        self.lbl_target = QLabel("Target: —")
        self.lbl_target.setStyleSheet("color:#88aaff;font-weight:bold;")
        layout.addWidget(self.lbl_target)

        parent_layout.addWidget(group)

    def _build_options_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Stacking Options")
        layout = QVBoxLayout(group)

        prow = QHBoxLayout()
        prow.addWidget(QLabel("Preset:"))
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(list(PRESETS.keys()) + ["Custom"])
        self.cmb_preset.setCurrentText("Balanced")
        self.cmb_preset.setToolTip(
            "One-click option profiles:\n"
            "• Quick look — fastest 'is this data any good?' pass "
            "(no colour calibration, stretched preview)\n"
            "• Balanced — sensible defaults for a normal night\n"
            "• Final — best quality: keep best 90%, QA rejection map, "
            "plate-solved masters\n"
            "Changing any option below switches this to 'Custom'.")
        _nofocus(self.cmb_preset)
        self.cmb_preset.activated.connect(self._on_preset_chosen)
        prow.addWidget(self.cmb_preset, 1)

        btn_save_preset = QPushButton("💾")
        btn_save_preset.setFixedWidth(34)
        btn_save_preset.setToolTip(
            "Save all current settings to a .json preset file, so you can "
            "reuse or share this exact configuration.")
        _nofocus(btn_save_preset)
        btn_save_preset.clicked.connect(self._save_preset_file)
        prow.addWidget(btn_save_preset)

        btn_load_preset = QPushButton("📂")
        btn_load_preset.setFixedWidth(34)
        btn_load_preset.setToolTip("Load settings from a .json preset file.")
        _nofocus(btn_load_preset)
        btn_load_preset.clicked.connect(self._load_preset_file)
        prow.addWidget(btn_load_preset)
        layout.addLayout(prow)

        self.chk_rejection = QCheckBox("Pixel rejection (auto algorithm)")
        self.chk_rejection.setChecked(True)
        self.chk_rejection.setToolTip(
            "Reject hot pixels, cosmics and satellite trails during "
            "integration.  The algorithm is chosen per filter from the "
            "frame count: percentile for few frames (≤4), winsorized for "
            "more, linear fit for large sets.  Recommended.")
        _nofocus(self.chk_rejection)
        layout.addWidget(self.chk_rejection)

        self.chk_weighting = QCheckBox("Frame weighting (weighted FWHM)")
        self.chk_weighting.setChecked(True)
        self.chk_weighting.setToolTip(
            "Weight sharper sub-exposures higher during integration "
            "(-weight=wfwhm).  Improves SNR when frame quality varies.")
        _nofocus(self.chk_weighting)
        layout.addWidget(self.chk_weighting)

        # --- frame quality filters --------------------------------------
        # Applied at registration time (seqapplyreg), so rejected frames are
        # never even re-projected.  Siril accepts value[%|k]: '%' keeps that
        # share of the best frames, 'k' rejects beyond k sigma.
        lbl_f = QLabel(f"Frame quality filters (from {FILTER_MIN_FRAMES} "
                       "frames):")
        lbl_f.setStyleSheet("color:#88aaff;margin-top:4px;")
        layout.addWidget(lbl_f)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Mode:"))
        self.cmb_filter_mode = QComboBox()
        self.cmb_filter_mode.addItems(["% best", "k-sigma"])
        self.cmb_filter_mode.setToolTip(
            "How the values below are read:\n"
            "• % best — keep that percentage of the best frames "
            "(e.g. 90% drops the worst tenth)\n"
            "• k-sigma — reject frames further than k standard deviations "
            "from the mean (e.g. 3)")
        _nofocus(self.cmb_filter_mode)
        row_mode.addWidget(self.cmb_filter_mode, 1)
        layout.addLayout(row_mode)

        common_tip = (f"\n\nApplied only to filters with at least "
                      f"{FILTER_MIN_FRAMES} frames — on shorter runs losing "
                      "a sub costs more signal-to-noise than the worst frame "
                      "costs quality.")

        def _filter_row(label: str, tip: str, default: int):
            tip = tip + common_tip
            row = QHBoxLayout()
            chk = QCheckBox(label)
            chk.setToolTip(tip)
            _nofocus(chk)
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(default)
            spin.setFixedWidth(70)
            spin.setToolTip(tip)
            _nofocus(spin)
            spin.setEnabled(False)
            chk.toggled.connect(spin.setEnabled)
            row.addWidget(chk, 1)
            row.addWidget(spin)
            layout.addLayout(row)
            return chk, spin

        self.chk_f_wfwhm, self.spin_keep = _filter_row(
            "Weighted FWHM",
            "Drop the softest frames (weighted FWHM = sharpness including "
            "the star count).  The most useful single filter.", 90)
        self.chk_f_round, self.spin_f_round = _filter_row(
            "Roundness",
            "Drop frames with elongated stars — guiding errors, wind or "
            "a bumped mount.", 90)
        self.chk_f_stars, self.spin_f_stars = _filter_row(
            "Star count",
            "Drop frames with too few detected stars — clouds, haze or a "
            "passing thin veil.", 90)
        self.chk_f_bkg, self.spin_f_bkg = _filter_row(
            "Background level",
            "Drop frames with a bright background — moonlight, twilight or "
            "passing headlights.", 90)

        self.chk_output_norm = QCheckBox("Output normalization")
        self.chk_output_norm.setChecked(True)
        self.chk_output_norm.setToolTip(
            "Normalise the final integrated frame's background level.")
        _nofocus(self.chk_output_norm)
        layout.addWidget(self.chk_output_norm)

        self.chk_rejmap = QCheckBox("Save rejection map (QA)")
        self.chk_rejmap.setChecked(False)
        self.chk_rejmap.setToolTip(
            "Also write a map showing which pixels were rejected — handy "
            "for checking that rejection behaved.")
        _nofocus(self.chk_rejmap)
        layout.addWidget(self.chk_rejmap)

        self.chk_skip_blank = QCheckBox("Skip blank / black frames")
        self.chk_skip_blank.setChecked(True)
        self.chk_skip_blank.setToolTip(
            "Drop frames that carry no signal at all (all-black, dead-flat or "
            "corrupt — e.g. a failed download or a closed flap) before "
            "stacking.  They break registration and drag the stack down.\n"
            "Only truly dead frames are dropped; faint subs are kept.")
        _nofocus(self.chk_skip_blank)
        layout.addWidget(self.chk_skip_blank)

        self.chk_crop_edges = QCheckBox("Crop stacking edges (min framing)")
        self.chk_crop_edges.setChecked(True)
        self.chk_crop_edges.setToolTip(
            "Keep only the area covered by ALL sub-frames (seqapplyreg "
            "-framing=min), so the master has no ragged low-coverage border. "
            "Uncheck to keep the full field with those partial edges.")
        _nofocus(self.chk_crop_edges)
        layout.addWidget(self.chk_crop_edges)

        self.chk_bg_master = QCheckBox("Background extraction per channel")
        self.chk_bg_master.setChecked(True)
        self.chk_bg_master.setToolTip(
            "Remove the sky gradient from each linear per-filter master "
            "(subsky) before the channels are combined — gradients differ "
            "per filter, so this beats one pass on the finished colour image.")
        _nofocus(self.chk_bg_master)
        layout.addWidget(self.chk_bg_master)

        self.chk_bg_extract = QCheckBox("Background extraction per sub-frame")
        self.chk_bg_extract.setChecked(False)
        self.chk_bg_extract.setToolTip(
            "Run seqsubsky on every individual light before registration. "
            "Rarely needed — prefer 'per channel' above.  Off by default.")
        _nofocus(self.chk_bg_extract)
        layout.addWidget(self.chk_bg_extract)

        self.chk_platesolve_reg = QCheckBox("Register via plate solving")
        self.chk_platesolve_reg.setChecked(False)
        self.chk_platesolve_reg.setToolTip(
            "Use seqplatesolve + WCS registration instead of star "
            "alignment.  Falls back to star alignment automatically.")
        _nofocus(self.chk_platesolve_reg)
        layout.addWidget(self.chk_platesolve_reg)

        self.chk_disto = QCheckBox("     + use distortion master")
        self.chk_disto.setChecked(False)
        self.chk_disto.setEnabled(False)
        self.chk_disto.setToolTip(
            "Adds -disto=master to the plate solve, so Siril loads the "
            "matching distortion master for each image and corrects optical "
            "distortion during registration.\n"
            "Only useful if you have distortion masters set up in Siril; "
            "without them the solve just proceeds normally.")
        _nofocus(self.chk_disto)
        self.chk_platesolve_reg.toggled.connect(self.chk_disto.setEnabled)
        layout.addWidget(self.chk_disto)

        row = QHBoxLayout()
        row.addWidget(QLabel("Drizzle:"))
        self.cmb_drizzle = QComboBox()
        self.cmb_drizzle.addItems(["Off", "2x", "3x"])
        self.cmb_drizzle.setToolTip(
            "Drizzle upsampling during registration.  Needs well-dithered "
            "sub-exposures and produces much larger files.")
        _nofocus(self.cmb_drizzle)
        row.addWidget(self.cmb_drizzle)
        row.addStretch()
        layout.addLayout(row)

        self.chk_copy = QCheckBox("Copy frames (don't symlink)")
        self.chk_copy.setChecked(False)
        self.chk_copy.setToolTip(
            "Copy the light frames into the working folder instead of "
            "symlinking.  Use if symlinks are not allowed on your drive.")
        _nofocus(self.chk_copy)
        layout.addWidget(self.chk_copy)

        parent_layout.addWidget(group)

    def _build_compose_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Colour Composition")
        layout = QVBoxLayout(group)

        self.chk_compose = QCheckBox("Create colour composite")
        self.chk_compose.setChecked(True)
        self.chk_compose.setToolTip(
            "After stacking, combine the aligned per-filter masters into a "
            "single colour image with rgbcomp (implies filter alignment).")
        _nofocus(self.chk_compose)
        self.chk_compose.toggled.connect(self._on_compose_toggled)
        layout.addWidget(self.chk_compose)

        prow = QHBoxLayout()
        prow.addWidget(QLabel("Palette:"))
        self.cmb_palette = QComboBox()
        self.cmb_palette.addItems(
            ["Auto", "LRGB", "RGB", "SHO", "HOO", "HaRGB"])
        self.cmb_palette.setToolTip(
            "Auto picks LRGB / SHO / HOO from the filters found.  SHO = "
            "Hubble (S→R, Ha→G, O→B); HOO = Ha→R, OIII→G+B; "
            "HaRGB = RGB with Ha blended into Red for more nebula detail.")
        _nofocus(self.cmb_palette)
        self.cmb_palette.currentTextChanged.connect(
            lambda _t: self._on_palette_changed())
        prow.addWidget(self.cmb_palette)
        prow.addStretch()
        layout.addLayout(prow)

        # Ha blend strength (HaRGB only): how strongly Ha is mixed into Red.
        self.row_ha = QHBoxLayout()
        self.lbl_ha = QLabel("Ha → Red:")
        self.row_ha.addWidget(self.lbl_ha)
        self.spin_ha = QSpinBox()
        self.spin_ha.setRange(0, 100)
        self.spin_ha.setSingleStep(10)
        self.spin_ha.setValue(50)
        self.spin_ha.setSuffix(" %")
        self.spin_ha.setToolTip(
            "HaRGB only: how strongly the Ha master is screen-blended into "
            "the Red channel (0% = plain RGB, 100% = maximum Ha).")
        _nofocus(self.spin_ha)
        self.row_ha.addWidget(self.spin_ha)
        self.row_ha.addStretch()
        layout.addLayout(self.row_ha)
        self.lbl_ha.setVisible(False)   # shown only for the HaRGB palette
        self.spin_ha.setVisible(False)

        # Per-channel mapping combos, populated with discovered filters.
        self.cmb_map_lum = self._make_map_combo("Luminance channel (optional)")
        self.cmb_map_red = self._make_map_combo("Red channel")
        self.cmb_map_green = self._make_map_combo("Green channel")
        self.cmb_map_blue = self._make_map_combo("Blue channel")
        for lab, cmb in (("L:", self.cmb_map_lum), ("R:", self.cmb_map_red),
                         ("G:", self.cmb_map_green), ("B:", self.cmb_map_blue)):
            r = QHBoxLayout()
            tag = QLabel(lab)
            tag.setFixedWidth(18)
            r.addWidget(tag)
            r.addWidget(cmb, 1)
            layout.addLayout(r)

        self.chk_nb_norm = QCheckBox("Normalize narrowband channels (SHO/HOO)")
        self.chk_nb_norm.setChecked(True)
        self.chk_nb_norm.setToolTip(
            "Before combining SHO/HOO, linear-match the channels to the Ha "
            "reference (Siril's recommendation) so no single channel — "
            "usually the strong Ha — dominates and turns the result green.")
        _nofocus(self.chk_nb_norm)
        layout.addWidget(self.chk_nb_norm)

        self.chk_quick_lrgb = QCheckBox("Quick linear LRGB (bake in luminance)")
        self.chk_quick_lrgb.setChecked(False)
        self.chk_quick_lrgb.setToolTip(
            "OFF (recommended, per Siril docs): compose R,G,B only and "
            "colour-calibrate that linear RGB; the L master is kept separate "
            "so you combine luminance AFTER stretching.\n"
            "ON: bake L in linearly in one rgbcomp step — a single file, but "
            "less accurate colour and weaker saturation.")
        _nofocus(self.chk_quick_lrgb)
        layout.addWidget(self.chk_quick_lrgb)

        self.chk_finish = QCheckBox("Auto-finish: background + colour calib.")
        self.chk_finish.setChecked(True)
        self.chk_finish.setToolTip(
            "After composing, plate-solve the colour image, extract the "
            "background, run Photometric Colour Calibration (PCC) and remove "
            "the green cast — leaving a calibrated (still linear) result.")
        _nofocus(self.chk_finish)
        self.chk_finish.toggled.connect(
            lambda on: self.chk_finish_stretch.setEnabled(
                on and self.chk_compose.isChecked()))
        layout.addWidget(self.chk_finish)

        self.chk_finish_stretch = QCheckBox("     + save stretched preview")
        self.chk_finish_stretch.setChecked(False)
        self.chk_finish_stretch.setToolTip(
            "Also save an autostretched, ready-to-view copy "
            "(TARGET_PALETTE_preview) — handy for a quick look; the linear "
            "calibrated file stays untouched for serious processing.")
        _nofocus(self.chk_finish_stretch)
        layout.addWidget(self.chk_finish_stretch)

        parent_layout.addWidget(group)

    def _make_map_combo(self, tip: str) -> QComboBox:
        cmb = QComboBox()
        cmb.addItem("(none)")
        cmb.setToolTip(tip)
        _nofocus(cmb)
        return cmb

    # ---- option presets ------------------------------------------------
    def _preset_widgets(self) -> dict:
        """Map preset option keys to their widgets."""
        return {
            "skip_blank": self.chk_skip_blank,
            "rejection": self.chk_rejection,
            "weighting": self.chk_weighting,
            "f_wfwhm_on": self.chk_f_wfwhm,
            "f_wfwhm_val": self.spin_keep,
            "f_round_on": self.chk_f_round,
            "f_stars_on": self.chk_f_stars,
            "f_bkg_on": self.chk_f_bkg,
            "cleanup_work": self.chk_cleanup,
            "bg_master": self.chk_bg_master,
            "bg_extract": self.chk_bg_extract,
            "rejmap": self.chk_rejmap,
            "platesolve_master": self.chk_platesolve_master,
            "compose": self.chk_compose,
            "finish": self.chk_finish,
            "finish_stretch": self.chk_finish_stretch,
            "nb_normalize": self.chk_nb_norm,
        }

    def _connect_preset_watchers(self) -> None:
        """Any manual option change flips the preset combo to 'Custom'."""
        for w in self._preset_widgets().values():
            if isinstance(w, QCheckBox):
                w.toggled.connect(self._mark_custom_preset)
            elif isinstance(w, QSpinBox):
                w.valueChanged.connect(self._mark_custom_preset)

    def _mark_custom_preset(self, *_args) -> None:
        if self._applying_preset:
            return
        if self.cmb_preset.currentText() != "Custom":
            self.cmb_preset.setCurrentText("Custom")

    def _all_setting_widgets(self) -> dict:
        """Every persisted option widget, keyed by its settings name.

        Used by the .json preset export/import so a saved preset covers the
        whole configuration, not just the handful a built-in profile sets.
        """
        w = {
            "filter_mode": self.cmb_filter_mode,
            "f_wfwhm_val": self.spin_keep,
            "f_round_val": self.spin_f_round,
            "f_stars_val": self.spin_f_stars,
            "f_bkg_val": self.spin_f_bkg,
            "crop_edges": self.chk_crop_edges,
            "output_norm": self.chk_output_norm,
            "rejmap": self.chk_rejmap,
            "bg_extract": self.chk_bg_extract,
            "platesolve_reg": self.chk_platesolve_reg,
            "disto_master": self.chk_disto,
            "drizzle": self.cmb_drizzle,
            "copy": self.chk_copy,
            "align_filters": self.chk_align_filters,
            "reuse_masters": self.chk_reuse,
            "load_result": self.chk_load_result,
            "clear_log": self.chk_clear_log,
            "palette": self.cmb_palette,
            "quick_lrgb": self.chk_quick_lrgb,
            "ha_strength": self.spin_ha,
            "finish_stretch": self.chk_finish_stretch,
        }
        w.update(self._preset_widgets())      # the profile-controlled ones
        return w

    def _save_preset_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preset", os.path.join(
                self._root or os.path.expanduser("~"),
                "ImageMonoTrain-preset.json"), "Preset (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        data = {"_script": "Svenesis ImageMono Train", "_version": VERSION,
                "settings": {}}
        for key, w in self._all_setting_widgets().items():
            if isinstance(w, QCheckBox):
                data["settings"][key] = bool(w.isChecked())
            elif isinstance(w, QSpinBox):
                data["settings"][key] = int(w.value())
            elif isinstance(w, QComboBox):
                data["settings"][key] = w.currentText()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Save preset",
                                f"Could not write the preset:\n{exc}")
            return
        self._log(f"Preset saved: {path}", LogColor.GREEN)

    def _load_preset_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load preset", self._root or os.path.expanduser("~"),
            "Preset (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Load preset",
                                f"Could not read the preset:\n{exc}")
            return
        settings = data.get("settings")
        if not isinstance(settings, dict):
            QMessageBox.warning(
                self, "Load preset",
                "That file is not an ImageMono Train preset.")
            return

        widgets = self._all_setting_widgets()
        applied, unknown = 0, 0
        self._applying_preset = True          # don't trip "Custom" per widget
        try:
            for key, value in settings.items():
                w = widgets.get(key)
                if w is None:
                    unknown += 1
                    continue
                try:
                    if isinstance(w, QCheckBox):
                        w.setChecked(bool(value))
                    elif isinstance(w, QSpinBox):
                        w.setValue(int(value))
                    elif isinstance(w, QComboBox):
                        # Ignore values this version doesn't offer.
                        if w.findText(str(value)) >= 0:
                            w.setCurrentText(str(value))
                        else:
                            unknown += 1
                            continue
                    applied += 1
                except (TypeError, ValueError):
                    unknown += 1
            self._on_compose_toggled(self.chk_compose.isChecked())
            self._on_palette_changed()
            self.chk_disto.setEnabled(self.chk_platesolve_reg.isChecked())
        finally:
            self._applying_preset = False
        # A file preset is by definition a custom configuration.
        self.cmb_preset.setCurrentText("Custom")
        self._log(
            f"Preset loaded: {os.path.basename(path)} — {applied} setting(s)"
            + (f", {unknown} ignored (unknown or unsupported)"
               if unknown else ""), LogColor.GREEN)

    def _on_preset_chosen(self, *_args) -> None:
        name = self.cmb_preset.currentText()
        if name == "Custom" or name not in PRESETS:
            return
        self._apply_preset(name)
        self._log(f"Applied preset: {name}", LogColor.BLUE)

    def _apply_preset(self, name: str) -> None:
        """Set every option a preset defines (without tripping 'Custom')."""
        preset = PRESETS.get(name)
        if not preset:
            return
        widgets = self._preset_widgets()
        self._applying_preset = True
        try:
            for key, value in preset.items():
                w = widgets.get(key)
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(value))
                elif isinstance(w, QSpinBox):
                    w.setValue(int(value))
            # Keep dependent enable-states in sync.
            self._on_compose_toggled(self.chk_compose.isChecked())
        finally:
            self._applying_preset = False

    def _on_compose_toggled(self, on: bool) -> None:
        for w in (self.cmb_palette, self.cmb_map_lum, self.cmb_map_red,
                  self.cmb_map_green, self.cmb_map_blue, self.chk_nb_norm,
                  self.chk_quick_lrgb, self.chk_finish):
            w.setEnabled(on)
        self.chk_finish_stretch.setEnabled(on and self.chk_finish.isChecked())

    def _populate_compose_combos(self) -> None:
        """Refill the channel combos with the discovered filters."""
        filters = sorted(self._groups.keys())
        for cmb in (self.cmb_map_lum, self.cmb_map_red,
                    self.cmb_map_green, self.cmb_map_blue):
            cmb.blockSignals(True)
            cmb.clear()
            cmb.addItem("(none)")
            cmb.addItems(filters)
            cmb.blockSignals(False)
        self._apply_palette_mapping()

    def _on_palette_changed(self) -> None:
        """React to a palette change: remap channels and toggle the Ha row."""
        self._apply_palette_mapping()
        is_hargb = self.cmb_palette.currentText() == "HaRGB"
        self.lbl_ha.setVisible(is_hargb)
        self.spin_ha.setVisible(is_hargb)

    def _apply_palette_mapping(self) -> None:
        """Set the channel combos from the selected/auto palette."""
        filters = sorted(self._groups.keys())
        if not filters:
            return
        palette = self.cmb_palette.currentText()
        mapping = _auto_channel_map(filters, palette)
        for role, cmb in (("lum", self.cmb_map_lum), ("red", self.cmb_map_red),
                          ("green", self.cmb_map_green),
                          ("blue", self.cmb_map_blue)):
            val = mapping.get(role, "")
            idx = cmb.findText(val) if val else 0
            cmb.setCurrentIndex(idx if idx >= 0 else 0)

    def _build_output_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        self.lbl_out = QLabel("Output: <target folder>/output")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet("color:#888888;font-size:9pt;")
        layout.addWidget(self.lbl_out)

        self.chk_align_filters = QCheckBox("Align filters to each other (LRGB)")
        self.chk_align_filters.setChecked(True)
        self.chk_align_filters.setToolTip(
            "After stacking, register all per-filter masters onto one shared "
            "pixel grid so the channels overlay exactly for LRGB / SHO "
            "combination.  Writes the aligned masters into masters/ "
            "(TARGET_FILTER.fit).")
        _nofocus(self.chk_align_filters)
        layout.addWidget(self.chk_align_filters)

        self.chk_platesolve_master = QCheckBox("Plate-solve final masters")
        self.chk_platesolve_master.setChecked(False)
        self.chk_platesolve_master.setToolTip(
            "Plate-solve each finished master so it carries a WCS solution "
            "for later annotation / mosaicking.")
        _nofocus(self.chk_platesolve_master)
        layout.addWidget(self.chk_platesolve_master)

        self.chk_reuse = QCheckBox("Reuse existing masters (skip re-stacking)")
        self.chk_reuse.setChecked(False)
        self.chk_reuse.setToolTip(
            "When the aligned masters from a previous run already exist, skip "
            "stacking and alignment and jump straight to colour composition. "
            "Great for trying another palette on the same night in seconds.\n"
            "Leave OFF after changing stacking options or adding new frames.")
        _nofocus(self.chk_reuse)
        layout.addWidget(self.chk_reuse)

        self.chk_load_result = QCheckBox("Load final stack into Siril")
        self.chk_load_result.setChecked(True)
        self.chk_load_result.setToolTip(
            "Load the last integrated stack back into Siril when finished.")
        _nofocus(self.chk_load_result)
        layout.addWidget(self.chk_load_result)

        self.chk_cleanup = QCheckBox("Delete _work/ when finished")
        self.chk_cleanup.setChecked(False)
        self.chk_cleanup.setToolTip(
            "Remove the _work/ folder (sequences, registered frames, compose "
            "helpers) after a successful run to reclaim disk space.\n"
            "The masters and the colour image are kept, so master reuse "
            "still works afterwards.  Leave OFF if you want to inspect the "
            "sequences and registered frames.")
        _nofocus(self.chk_cleanup)
        layout.addWidget(self.chk_cleanup)

        self.chk_clear_log = QCheckBox("Clear log before each run")
        self.chk_clear_log.setChecked(True)
        self.chk_clear_log.setToolTip(
            "Empty the in-window Log tab at the start of every analysis / "
            "stacking run, so you only see the current run's messages.")
        _nofocus(self.chk_clear_log)
        layout.addWidget(self.chk_clear_log)

        parent_layout.addWidget(group)

    def _build_action_buttons(self, parent_layout: QVBoxLayout) -> None:
        self.btn_stack = QPushButton("Stack All Filters")
        self.btn_stack.setObjectName("RenderButton")
        _nofocus(self.btn_stack)
        self.btn_stack.setToolTip(
            "Register and integrate one master light per discovered filter.")
        self.btn_stack.clicked.connect(self._on_stack)
        self.btn_stack.setEnabled(False)
        parent_layout.addWidget(self.btn_stack)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        parent_layout.addWidget(self.progress)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 9pt;")
        self.lbl_status.setWordWrap(True)
        parent_layout.addWidget(self.lbl_status)

    # ---- RIGHT PANEL --------------------------------------------------
    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_header = QLabel("Select a target folder to begin.")
        self.lbl_header.setStyleSheet(
            "font-size: 10pt; color: #aaaaaa; padding: 4px; "
            "background-color: #333333; border-radius: 4px;")
        self.lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(self.lbl_header)

        self.tabs = QTabWidget()

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet(
            "background-color:#1e1e1e;color:#dddddd;"
            "font-family:monospace;font-size:10pt;")
        self.info_text.setHtml(
            "<p style='color:#888'>Analyze a folder to see the discovered "
            "filters and frame counts here.</p>")
        self.tabs.addTab(self.info_text, "Overview")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color:#1e1e1e;color:#cccccc;"
            "font-family:monospace;font-size:9pt;")
        self.tabs.addTab(self.log_text, "Log")

        r_layout.addWidget(self.tabs, 1)
        return right

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        st = self._settings
        self.chk_skip_blank.setChecked(st.value("skip_blank", True, type=bool))
        self.chk_rejection.setChecked(st.value("rejection", True, type=bool))
        self.chk_weighting.setChecked(st.value("weighting", True, type=bool))
        self.spin_keep.setValue(int(st.value("f_wfwhm_val", 90)))
        self.cmb_filter_mode.setCurrentText(
            str(st.value("filter_mode", "% best")))
        self.chk_f_wfwhm.setChecked(st.value("f_wfwhm_on", False, type=bool))
        self.chk_f_round.setChecked(st.value("f_round_on", False, type=bool))
        self.spin_f_round.setValue(int(st.value("f_round_val", 90)))
        self.chk_f_stars.setChecked(st.value("f_stars_on", False, type=bool))
        self.spin_f_stars.setValue(int(st.value("f_stars_val", 90)))
        self.chk_f_bkg.setChecked(st.value("f_bkg_on", False, type=bool))
        self.spin_f_bkg.setValue(int(st.value("f_bkg_val", 90)))
        self.chk_disto.setChecked(st.value("disto_master", False, type=bool))
        self.chk_cleanup.setChecked(st.value("cleanup_work", False, type=bool))
        self.chk_output_norm.setChecked(st.value("output_norm", True, type=bool))
        self.chk_rejmap.setChecked(st.value("rejmap", False, type=bool))
        self.chk_crop_edges.setChecked(st.value("crop_edges", True, type=bool))
        self.chk_bg_master.setChecked(st.value("bg_master", True, type=bool))
        self.chk_bg_extract.setChecked(st.value("bg_extract", False, type=bool))
        self.chk_platesolve_reg.setChecked(
            st.value("platesolve_reg", False, type=bool))
        self.chk_copy.setChecked(st.value("copy", False, type=bool))
        self.chk_align_filters.setChecked(
            st.value("align_filters", True, type=bool))
        self.chk_platesolve_master.setChecked(
            st.value("platesolve_master", False, type=bool))
        self.chk_reuse.setChecked(st.value("reuse_masters", False, type=bool))
        self.chk_load_result.setChecked(st.value("load_result", True, type=bool))
        self.chk_clear_log.setChecked(st.value("clear_log", True, type=bool))
        # Restore the preset label last: the individual options above were
        # already restored, so just reflect what was saved (no re-apply).
        self.cmb_preset.setCurrentText(str(st.value("preset", "Balanced")))
        self.cmb_drizzle.setCurrentText(str(st.value("drizzle", "Off")))
        self.chk_compose.setChecked(st.value("compose", True, type=bool))
        self.cmb_palette.setCurrentText(str(st.value("palette", "Auto")))
        self.chk_nb_norm.setChecked(st.value("nb_normalize", True, type=bool))
        self.chk_quick_lrgb.setChecked(st.value("quick_lrgb", False, type=bool))
        self.spin_ha.setValue(int(st.value("ha_strength", 50)))
        self._on_palette_changed()
        self.chk_finish.setChecked(st.value("finish", True, type=bool))
        self.chk_finish_stretch.setChecked(
            st.value("finish_stretch", False, type=bool))
        self._on_compose_toggled(self.chk_compose.isChecked())
        last = str(st.value("last_folder", ""))
        if last and os.path.isdir(last):
            self._set_root(last)

    def _save_settings(self) -> None:
        st = self._settings
        st.setValue("preset", self.cmb_preset.currentText())
        st.setValue("skip_blank", self.chk_skip_blank.isChecked())
        st.setValue("rejection", self.chk_rejection.isChecked())
        st.setValue("weighting", self.chk_weighting.isChecked())
        st.setValue("f_wfwhm_val", int(self.spin_keep.value()))
        st.setValue("filter_mode", self.cmb_filter_mode.currentText())
        st.setValue("f_wfwhm_on", self.chk_f_wfwhm.isChecked())
        st.setValue("f_round_on", self.chk_f_round.isChecked())
        st.setValue("f_round_val", int(self.spin_f_round.value()))
        st.setValue("f_stars_on", self.chk_f_stars.isChecked())
        st.setValue("f_stars_val", int(self.spin_f_stars.value()))
        st.setValue("f_bkg_on", self.chk_f_bkg.isChecked())
        st.setValue("f_bkg_val", int(self.spin_f_bkg.value()))
        st.setValue("disto_master", self.chk_disto.isChecked())
        st.setValue("cleanup_work", self.chk_cleanup.isChecked())
        st.setValue("output_norm", self.chk_output_norm.isChecked())
        st.setValue("rejmap", self.chk_rejmap.isChecked())
        st.setValue("crop_edges", self.chk_crop_edges.isChecked())
        st.setValue("bg_master", self.chk_bg_master.isChecked())
        st.setValue("bg_extract", self.chk_bg_extract.isChecked())
        st.setValue("platesolve_reg", self.chk_platesolve_reg.isChecked())
        st.setValue("copy", self.chk_copy.isChecked())
        st.setValue("align_filters", self.chk_align_filters.isChecked())
        st.setValue("platesolve_master", self.chk_platesolve_master.isChecked())
        st.setValue("reuse_masters", self.chk_reuse.isChecked())
        st.setValue("load_result", self.chk_load_result.isChecked())
        st.setValue("clear_log", self.chk_clear_log.isChecked())
        st.setValue("drizzle", self.cmb_drizzle.currentText())
        st.setValue("compose", self.chk_compose.isChecked())
        st.setValue("palette", self.cmb_palette.currentText())
        st.setValue("nb_normalize", self.chk_nb_norm.isChecked())
        st.setValue("quick_lrgb", self.chk_quick_lrgb.isChecked())
        st.setValue("ha_strength", int(self.spin_ha.value()))
        st.setValue("finish", self.chk_finish.isChecked())
        st.setValue("finish_stretch", self.chk_finish_stretch.isChecked())
        if self._root:
            st.setValue("last_folder", self._root)

    def _running_worker(self):
        """Return the worker that is currently running, if any."""
        for w in (self._stack_worker, self._analyze_worker):
            try:
                if w is not None and w.isRunning():
                    return w
            except RuntimeError:
                pass            # already deleted by Qt
        return None

    def closeEvent(self, event) -> None:
        """Never let Qt destroy a running worker thread (that hard-crashes).

        A Siril command cannot be interrupted mid-flight, so the worker is
        asked to stop at its next safe point and we wait for it.  If it is
        stuck inside a long command the user can force the window closed.
        """
        worker = self._running_worker()
        if worker is not None:
            reply = QMessageBox.question(
                self, "Processing is still running",
                "A run is still in progress.\n\n"
                "Stop it and close the window?  Masters that are already "
                "finished are kept; the current step is allowed to end "
                "first.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            self._set_status("Stopping — waiting for the current step…")
            worker.requestInterruption()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                finished = worker.wait(15000)     # up to 15 s
            finally:
                QApplication.restoreOverrideCursor()

            if not finished:
                force = QMessageBox.warning(
                    self, "Still busy",
                    "The current Siril step has not finished yet.\n\n"
                    "Close anyway?  Siril may be left mid-command and the "
                    "unfinished files could be incomplete.",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if force != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                # Last resort: give it a final short grace period, then let
                # Qt tear it down rather than hanging the UI forever.
                worker.wait(3000)

            # The worker may have emitted finished/failed just before it
            # stopped; those are queued for this thread and would run against
            # a window that is on its way out.  Drop them.
            for w in (self._stack_worker, self._analyze_worker):
                if w is None:
                    continue
                for sig in ("progress", "log", "finished", "failed"):
                    try:
                        # AnalyzeWorker has no `log` signal -> AttributeError.
                        getattr(w, sig).disconnect()
                    except (AttributeError, TypeError, RuntimeError):
                        pass          # absent / not connected / already gone

        self._save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------
    def _append_log(self, msg: str, color=None) -> None:
        """Append a line to the in-window Log tab only (no sirilpy access).

        This is the slot the StackWorker's ``log`` signal connects to.  It
        runs on the main thread but must NOT call ``siril.log`` -- the worker
        already logged to the Siril console on its own thread, and touching
        sirilpy here would race with the worker's ``siril.cmd`` calls.
        """
        # Map Siril log colours to HTML.  Built by name so a LogColor variant
        # missing on older sirilpy is simply absent (falls back to grey).
        col_map = {}
        for name, hexcol in (("RED", "#ff8888"), ("GREEN", "#88ff88"),
                             ("BLUE", "#88aaff"), ("SALMON", "#ffb0a0")):
            member = getattr(LogColor, name, None)
            if member is not None:
                col_map[member] = hexcol
        html_col = col_map.get(color, "#cccccc")
        self.log_text.append(f"<span style='color:{html_col}'>{msg}</span>")

    def _log(self, msg: str, color=None) -> None:
        """Main-thread logger: GUI text + Siril console.

        Only called directly from the main thread (never during a worker run,
        so the sirilpy access here can't race with the worker).
        """
        self._append_log(msg, color)
        try:
            self.siril.log(f"[ImageMonoTrain] {msg}", color or LogColor.DEFAULT)
        except Exception as exc:
            _log_swallowed(exc)

    def _set_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    # ------------------------------------------------------------------
    # FOLDER SELECTION + ANALYSIS
    # ------------------------------------------------------------------
    def _set_root(self, path: str) -> None:
        self._root = path
        self.lbl_folder.setText(path)
        self.lbl_out.setText(
            f"Output: {os.path.join(path, STACKS_DIRNAME)}")
        self.btn_analyze.setEnabled(True)

    def _looks_like_our_output(self, path: str) -> bool:
        """True if `path` is an output folder this script produced.

        Discovery prunes a nested output/ folder, but picking that folder
        *itself* as the target would side-step the guard and re-ingest our
        own masters as if they were light frames.
        """
        if os.path.basename(os.path.normpath(path)) != STACKS_DIRNAME:
            return False
        return (os.path.isdir(os.path.join(path, MASTERS_DIRNAME))
                or os.path.isfile(os.path.join(path, "output.md")))

    def _on_pick_folder(self) -> None:
        start = self._root or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, "Select the target's root folder", start)
        if not path:
            return
        if self._looks_like_our_output(path):
            parent = os.path.dirname(os.path.normpath(path))
            reply = QMessageBox.question(
                self, "That is the results folder",
                f"'{os.path.basename(path)}' is a folder this script wrote "
                "its results into, not a folder of light frames.\n\n"
                f"Use the folder above it instead?\n{parent}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                path = parent
            else:
                self._log(
                    "Selected folder is a results folder — stacked masters "
                    "may be picked up as light frames.", LogColor.SALMON)
        self._set_root(path)
        self._on_analyze()

    def _maybe_clear_log(self) -> None:
        """Empty the Log tab before a new run if the option is enabled."""
        if self.chk_clear_log.isChecked():
            self.log_text.clear()

    def _on_analyze(self) -> None:
        if not self._root:
            return
        self._maybe_clear_log()
        self._groups = {}
        self.tbl_filters.setRowCount(0)
        self._set_left_enabled(False)
        self.lbl_header.setText(f"Analyzing: {self._root}")
        self._set_status("Scanning for light frames…")
        self._log(f"Analyzing folder: {self._root}", LogColor.BLUE)

        self._analyze_worker = AnalyzeWorker(self._root)
        self._analyze_worker.progress.connect(self._on_progress)
        self._analyze_worker.finished.connect(self._on_analyze_done)
        self._analyze_worker.failed.connect(self._on_worker_failed)
        self._analyze_worker.start()

    def _on_analyze_done(self, payload: dict) -> None:
        self._groups = payload["groups"]
        self._target = payload["target"]
        total = payload["total"]
        objects = payload.get("objects", [])

        self._set_left_enabled(True)

        self.lbl_target.setText(f"Target: {self._target}")
        self._populate_compose_combos()

        # Frames from two different objects must never be pooled into one
        # stack -- that silently produces garbage.  Warn loudly.
        self._multi_target = objects if len(objects) > 1 else []
        if self._multi_target:
            names = ", ".join(objects)
            self._log(
                f"WARNING: {len(objects)} different targets found ({names}). "
                "Their frames would be stacked together!", LogColor.RED)
            QMessageBox.warning(
                self, "More than one target in this folder",
                f"The selected folder contains frames of {len(objects)} "
                f"different objects:\n\n{names}\n\n"
                "Stacking them together would combine different parts of "
                "the sky into one image.\n\n"
                "Pick the folder of a single target instead (usually one "
                "level deeper).")

        # Populate the table.
        filters = sorted(self._groups.keys())
        self.tbl_filters.setRowCount(len(filters))
        total_lights = 0
        total_exp = 0.0
        for r, filt in enumerate(filters):
            g = self._groups[filt]
            n = len(g["files"])
            total_lights += n
            exp_total = g.get("exp_total", 0.0)
            total_exp += exp_total
            samp = g.get("sample", {})
            detail = " ".join(
                v for v in (samp.get("exp"), samp.get("gain"),
                            samp.get("temp")) if v) or "—"
            self.tbl_filters.setItem(r, 0, QTableWidgetItem(filt))
            self.tbl_filters.setItem(r, 1, QTableWidgetItem(str(n)))
            self.tbl_filters.setItem(
                r, 2, QTableWidgetItem(_format_duration(exp_total)))
            self.tbl_filters.setItem(r, 3, QTableWidgetItem(detail))

        total_txt = _format_duration(total_exp)
        self.lbl_header.setText(
            f"{self._target}: {len(filters)} filter(s), "
            f"{total_lights} light frame(s), {total_txt} total integration.")
        self._set_status(
            f"Found {len(filters)} filter(s), {total_lights} lights "
            f"({total_txt}).")

        # Overview HTML.
        rows = "".join(
            f"<tr><td style='padding:3px 12px 3px 0;color:#88aaff;'><b>{f}</b></td>"
            f"<td style='padding:3px 12px 3px 0;'>{len(self._groups[f]['files'])} lights</td>"
            f"<td style='padding:3px 12px 3px 0;color:#88ff88;'>"
            f"{_format_duration(self._groups[f].get('exp_total', 0.0))}</td>"
            f"<td style='padding:3px 0;color:#aaaaaa;'>"
            f"{' '.join(v for v in (self._groups[f]['sample'].get('exp'), self._groups[f]['sample'].get('gain'), self._groups[f]['sample'].get('temp')) if v)}</td></tr>"
            for f in filters)
        self.info_text.setHtml(
            f"<h2 style='color:#88aaff;'>{self._target}</h2>"
            f"<p>Scanned <b>{total}</b> FITS file(s) under:<br>"
            f"<span style='color:#888;'>{self._root}</span></p>"
            f"<p><b>{len(filters)}</b> optical filter(s) with light frames — "
            f"<b>{total_txt}</b> total integration:</p>"
            f"<table cellspacing='0'>{rows}</table>"
            "<hr>"
            "<p style='color:#aaaaaa;'>Review the list, adjust the stacking "
            "options if needed, then press <b>Stack All Filters</b>.  "
            "One integrated master light is written per filter into the "
            "output folder.</p>")

        self._log(
            f"Discovered target '{self._target}': {len(filters)} filter(s), "
            f"{total_lights} light frame(s), {total_txt} total integration.",
            LogColor.GREEN)
        for filt in filters:
            g = self._groups[filt]
            self._log(f"  {filt}: {len(g['files'])} lights "
                      f"({_format_duration(g.get('exp_total', 0.0))})",
                      LogColor.BLUE)

    # ------------------------------------------------------------------
    # STACKING
    # ------------------------------------------------------------------
    def _current_opts(self) -> dict:
        drizzle_txt = self.cmb_drizzle.currentText()
        drizzle = {"Off": 1, "2x": 2, "3x": 3}.get(drizzle_txt, 1)

        def _map(cmb):
            t = cmb.currentText()
            return "" if t == "(none)" else t

        palette = self.cmb_palette.currentText()
        if palette == "Auto":
            palette = _detect_palette(sorted(self._groups.keys()))

        return {
            "skip_blank": self.chk_skip_blank.isChecked(),
            "rejection": self.chk_rejection.isChecked(),
            "weighting": self.chk_weighting.isChecked(),
            "filter_mode": self.cmb_filter_mode.currentText(),
            "f_wfwhm_on": self.chk_f_wfwhm.isChecked(),
            "f_wfwhm_val": int(self.spin_keep.value()),
            "f_round_on": self.chk_f_round.isChecked(),
            "f_round_val": int(self.spin_f_round.value()),
            "f_stars_on": self.chk_f_stars.isChecked(),
            "f_stars_val": int(self.spin_f_stars.value()),
            "f_bkg_on": self.chk_f_bkg.isChecked(),
            "f_bkg_val": int(self.spin_f_bkg.value()),
            "disto_master": self.chk_disto.isChecked(),
            "cleanup_work": self.chk_cleanup.isChecked(),
            "output_norm": self.chk_output_norm.isChecked(),
            "rejmap": self.chk_rejmap.isChecked(),
            "crop_edges": self.chk_crop_edges.isChecked(),
            "bg_master": self.chk_bg_master.isChecked(),
            "bg_extract": self.chk_bg_extract.isChecked(),
            "platesolve_reg": self.chk_platesolve_reg.isChecked(),
            "drizzle": drizzle,
            "copy": self.chk_copy.isChecked(),
            "align_filters": self.chk_align_filters.isChecked(),
            "platesolve_master": self.chk_platesolve_master.isChecked(),
            "preset": self.cmb_preset.currentText(),
            "compose": self.chk_compose.isChecked(),
            "compose_palette": palette,
            "reuse_masters": self.chk_reuse.isChecked(),
            "quick_lrgb": self.chk_quick_lrgb.isChecked(),
            "nb_normalize": self.chk_nb_norm.isChecked(),
            "ha_strength": int(self.spin_ha.value()),
            "map_lum": _map(self.cmb_map_lum),
            "map_red": _map(self.cmb_map_red),
            "map_green": _map(self.cmb_map_green),
            "map_blue": _map(self.cmb_map_blue),
            "finish": self.chk_finish.isChecked(),
            "finish_stretch": self.chk_finish_stretch.isChecked(),
            "load_result": self.chk_load_result.isChecked(),
        }

    def _on_stack(self) -> None:
        if not self._groups:
            return
        # Last line of defence: stacking two objects together is never what
        # the user wants, so make them confirm it explicitly.
        if self._multi_target:
            reply = QMessageBox.warning(
                self, "More than one target",
                "This folder holds frames of different objects:\n\n"
                + ", ".join(self._multi_target)
                + "\n\nStacking them together mixes different parts of the "
                  "sky into one image.\n\nStack anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._save_settings()
        try:
            if not self.siril.connected:
                self.siril.connect()
        except Exception as exc:
            QMessageBox.critical(
                self, "Siril", f"Could not connect to Siril:\n{exc}")
            return

        try:
            self._ext = self.siril.get_siril_config("core", "extension") or ".fit"
        except Exception:
            self._ext = ".fit"
        if not self._ext.startswith("."):
            self._ext = "." + self._ext

        out_dir = os.path.join(self._root, STACKS_DIRNAME)

        self._maybe_clear_log()
        self._set_left_enabled(False)
        self.tabs.setCurrentWidget(self.log_text)
        self._log(f"Stacking {len(self._groups)} filter(s) into {out_dir}",
                  LogColor.GREEN)

        self._stack_worker = StackWorker(
            self.siril, self._groups, self._target, out_dir,
            self._ext, self._current_opts())
        self._stack_worker.progress.connect(self._on_progress)
        # Text-only slot: the worker already logged to the Siril console on
        # its own thread, so the main thread must not touch sirilpy here.
        self._stack_worker.log.connect(self._append_log)
        self._stack_worker.finished.connect(self._on_stack_done)
        self._stack_worker.failed.connect(self._on_worker_failed)
        self._stack_worker.start()

    def _on_stack_done(self, payload: dict) -> None:
        results = payload["results"]
        errors = payload["errors"]
        aligned = payload.get("aligned", False)
        composite = payload.get("composite")
        finished = payload.get("finished", False)
        preview = payload.get("preview")
        separate_lum = payload.get("separate_lum")
        self._set_left_enabled(True)
        self.progress.setValue(100)

        n_ok = len(results)
        n_err = len(errors)
        self.lbl_header.setText(
            f"Done: {n_ok} master(s) written"
            + (", cross-filter aligned" if aligned else "")
            + (", colour composite" if composite else "")
            + (f", {n_err} filter(s) failed." if n_err else "."))
        self._set_status(f"Finished: {n_ok} ok, {n_err} failed.")

        out_root = os.path.join(self._root, STACKS_DIRNAME)
        ok_rows = "".join(
            f"<li><b style='color:#88ff88;'>{f}</b> → "
            f"<span style='color:#aaa;'>{os.path.basename(p)}</span></li>"
            for f, p in results.items())
        err_rows = "".join(
            f"<li><b style='color:#ff8888;'>{f}</b>: {msg}</li>"
            for f, msg in errors.items())
        align_note = (
            "<p style='color:#88ff88;'>✓ Masters are aligned to a common "
            "grid — the <b>masters/TARGET_FILTER.fit</b> files overlay "
            "pixel-for-pixel.</p>"
            if aligned else
            "<p style='color:#ffb0a0;'>Note: per-filter masters are on "
            "independent grids; re-register them together before combining "
            "channels (enable <i>Align filters</i> to do this "
            "automatically).</p>")
        if composite:
            calib = (" (background-extracted + colour-calibrated, linear)"
                     if finished else " — still linear, uncalibrated")
            prev = (f"<br>A stretched preview <b>{os.path.basename(preview)}"
                    "</b> was also saved and is loaded in Siril."
                    if preview else "")
            if separate_lum:
                # Correct LRGB path: RGB is calibrated, L kept separate.
                lum_note = (
                    "<br>This is the calibrated <b>RGB</b> (colour only). "
                    "Your luminance master <b>"
                    f"{os.path.basename(separate_lum)}</b> is kept separate — "
                    "per Siril's guidance, stretch RGB and L, then combine "
                    "them last with <tt>rgbcomp -lum</tt>.")
            else:
                lum_note = "<br>Stretch it (Histogram / GHS) to taste."
            compose_note = (
                "<p style='color:#88ff88;'>🎨 Colour composite <b>"
                f"{os.path.basename(composite)}</b>{calib}.{prev}{lum_note}</p>")
        else:
            compose_note = ""
        self.info_text.setHtml(
            "<h2 style='color:#88aaff;'>Stacking complete</h2>"
            f"<p><b>{n_ok}</b> master light(s) written to:<br>"
            f"<span style='color:#888;'>{out_root}</span></p>"
            + (f"<ul>{ok_rows}</ul>" if ok_rows else "")
            + align_note
            + compose_note
            + (f"<h3 style='color:#ff8888;'>Skipped / failed</h3>"
               f"<ul>{err_rows}</ul>" if err_rows else ""))

        self._log(f"All done: {n_ok} master(s) written, {n_err} failed."
                  + (f" Composite: {os.path.basename(composite)}"
                     if composite else ""), LogColor.GREEN)
        if results:
            QMessageBox.information(
                self, "ImageMono Train",
                f"Stacked {n_ok} filter(s) successfully.\n\n"
                + ("Cross-filter aligned masters are in masters/.\n"
                   if aligned else "")
                + (f"Colour composite: {os.path.basename(composite)} "
                   "(loaded in Siril).\n" if composite else "")
                + f"\nOutput folder:\n{out_root}")

    # ------------------------------------------------------------------
    # WORKER FEEDBACK
    # ------------------------------------------------------------------
    def _on_progress(self, value: int, label: str) -> None:
        self.progress.setValue(value)
        if label:
            self._set_status(label)

    def _on_worker_failed(self, msg: str) -> None:
        self._set_left_enabled(True)
        self.btn_analyze.setEnabled(bool(self._root))
        self.btn_stack.setEnabled(bool(self._groups))
        self._set_status("Failed.")
        self._log(msg, LogColor.RED)
        QMessageBox.critical(self, "ImageMono Train", msg)

    def _set_left_enabled(self, enabled: bool) -> None:
        self._busy = not enabled
        for w in (self.btn_pick, self.btn_analyze, self.btn_stack,
                  self.cmb_preset):
            w.setEnabled(enabled)
        # The window can still be closed while busy (closeEvent then offers to
        # abort), but greying the button out makes the state obvious.
        self.btn_close.setEnabled(enabled)
        self.btn_close.setText("Close" if enabled else "Running…")

    # ------------------------------------------------------------------
    # COFFEE DIALOG
    # ------------------------------------------------------------------
    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"
        dlg = QDialog(self)
        dlg.setWindowTitle("☕ Support Svenesis ImageMono Train")
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
            "<span style='font-size:48pt;'>☕</span><br>"
            "<span style='font-size:18pt; font-weight:bold; color:#FFDD00;'>"
            "Buy me a Coffee</span><br><br>"
            "<b style='color:#e0e0e0;'>Enjoying Svenesis ImageMono Train?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If ImageMono Train saved you an evening of clicking through "
            "convert / register / stack for every filter — "
            "consider buying me a coffee to keep development going!<br><br>"
            "<span style='color:#FFDD00;'>☕ Every coffee fuels a new feature, "
            "bug fix, or clear-sky night of testing.</span><br>"
            "</div>")
        header_msg.setWordWrap(True)
        header_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header_msg)

        layout.addSpacing(8)

        btn_open = QPushButton("☕  Buy me a Coffee  ☕")
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
            f"Clear skies ✨</span></div>")
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
        dlg.setWindowTitle("Svenesis ImageMono Train — Help")
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
            "<p><b>What does ImageMono Train do?</b></p>"
            "<p>It turns one N.I.N.A. capture folder into finished master "
            "lights — <i>one integrated stack per optical filter</i> — "
            "without you touching the Siril command line.  Point it at a "
            "target's root folder; it reads every FITS header, keeps only "
            "the LIGHT frames, groups them by filter, tells you exactly "
            "what it found, then registers and stacks each filter.</p>"
            "<blockquote style='color:#88aaff;'><i>Load a whole night of "
            "Ha / OIII / SII (or L R G B) into one folder, press one "
            "button, and walk away with one clean stack per filter.</i>"
            "</blockquote>"
            "<hr>"
            "<p><b>Built for a mono rig:</b></p>"
            "<ul>"
            "<li>Designed around a <b>monochrome camera</b> behind a "
            "filter wheel (e.g. the Player One Ares-M Pro / IMX533) driven "
            "by N.I.N.A.</li>"
            "<li>Frames are <b>never debayered</b> — the whole "
            "pipeline is monochrome, exactly as a mono sensor requires.</li>"
            "<li>Files usually land in the target folder automatically via "
            "a Dropbox sync from the remote rig PC — just point the "
            "script at that folder.</li>"
            "</ul>"
            "<hr>"
            "<p><b>Quick Start:</b></p>"
            "<ol>"
            "<li>Click <b>Select Target Folder…</b> and pick the root "
            "folder of one target.</li>"
            "<li>The script <b>analyzes</b> the tree and lists every filter "
            "with its light-frame count (exposure / gain / temperature).</li>"
            "<li>Review the <b>Discovered Filters</b> table and the "
            "<b>Overview</b> tab.</li>"
            "<li>Adjust <b>Stacking Options</b> if needed (defaults are "
            "sensible).</li>"
            "<li>Press <b>Stack All Filters</b>.  Watch progress in the "
            "<b>Log</b> tab.</li>"
            "<li>Collect one FITS master light per filter from the "
            "<b>output</b> folder.</li>"
            "</ol>"
            "<hr>"
            "<h3 style='color:#88aaff;'>How folders are read</h3>"
            "<p>N.I.N.A. is assumed to save with this schema:</p>"
            "<p style='font-family:monospace;color:#aaddaa;'>"
            "DATE\\IMAGETYPE\\TARGETNAME\\FILTER\\"
            "TARGETNAME_FILTER_EXPs_Gxx_TEMPC_FRAME_DATETIME</p>"
            "<p>But the script does not depend on the folder names: the "
            "<b>FILTER</b>, <b>IMAGETYP</b> and <b>OBJECT</b> FITS keywords "
            "are the source of truth, with folder names used only as a "
            "fallback.  Frames whose type is dark / flat / bias are "
            "ignored.  The same filter spread across several nights is "
            "pooled into a single stack.</p>"
            "<p><b>Pick the folder of ONE target.</b>  If the folder holds "
            "frames of several objects (e.g. you picked the date or LIGHT "
            "folder), their frames would end up in the same stack — so the "
            "script detects that from the <tt>OBJECT</tt> keyword, warns you "
            "after the analysis, and asks again before stacking.</p>"
            "<p>Its own results folder (<b>output/</b>) is skipped while "
            "scanning, so a second run never re-reads the masters it wrote "
            "as if they were new light frames.</p>")
        tabs.addTab(tab1, "Getting Started")

        tab2 = QTextEdit()
        tab2.setReadOnly(True)
        tab2.setHtml(
            "<h2 style='color:#88aaff;'>The Pipeline</h2>"
            "<p>Each filter is processed independently, following the "
            "proven mono preprocessing sequence:</p>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='width:170px'><b>Collect</b></td>"
            "<td>The filter's light frames are gathered into a working "
            "folder (symlinked by default, or copied).</td></tr>"
            "<tr><td><b>link / convert</b></td>"
            "<td>FITS frames are linked into a Siril sequence; non-FITS "
            "raws are converted.  Never debayered.</td></tr>"
            "<tr><td><b>seqsubsky</b> <i>(optional)</i></td>"
            "<td>Background / gradient extraction on every sub before "
            "registration.  Off by default.</td></tr>"
            "<tr><td><b>register −2pass</b></td>"
            "<td>Two-pass star registration picks the best reference and "
            "aligns all frames (or plate-solve registration if enabled; it "
            "falls back to star alignment automatically).</td></tr>"
            "<tr><td><b>seqapplyreg</b></td>"
            "<td>Applies the registration.  <i>min</i> framing (default) "
            "crops the ragged stacking edges; <i>max</i> keeps the full "
            "field.  Drizzle when selected.</td></tr>"
            "<tr><td><b>stack</b></td>"
            "<td>Rejection integration with additive+scaling "
            "normalisation, weighted-FWHM weighting and 32-bit output.</td></tr>"
            "<tr><td><b>subsky</b> (per channel)</td>"
            "<td>Background / gradient removed from each linear master "
            "before the channels are combined.</td></tr>"
            "<tr><td><b>align filters</b> <i>(optional)</i></td>"
            "<td>All per-filter masters are re-registered onto one shared "
            "grid (min framing → identical size) so the channels overlay "
            "pixel-for-pixel.</td></tr>"
            "<tr><td><b>rgbcomp</b> <i>(optional)</i></td>"
            "<td>Combines the aligned masters into a single colour image "
            "(LRGB / RGB / SHO / HOO).</td></tr>"
            "</table>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Adaptive rejection</h3>"
            "<p>The rejection algorithm is chosen <b>per filter</b> from the "
            "frame count, because sigma-based methods need a population to "
            "work well:</p>"
            "<ul>"
            "<li><b>≤ 4 frames</b> → percentile clipping (0.2 / 0.1)</li>"
            "<li><b>5 – 20 frames</b> → Winsorized sigma (3σ / 3σ)</li>"
            "<li><b>&gt; 20 frames</b> → linear-fit clipping (3σ / 3σ)</li>"
            "</ul>"
            "<h3 style='color:#88aaff;'>Stacking Options</h3>"
            "<ul>"
            "<li><b>Preset</b> — one-click profiles: <i>Quick look</i> "
            "(fast 'is this data good?' pass with a stretched preview), "
            "<i>Balanced</i> (sensible defaults) and <i>Final</i> (best "
            "quality: keep best 90%, rejection map, plate-solved masters). "
            "Changing any option switches the box to <i>Custom</i>.</li>"
            "<li><b>Skip blank / black frames</b> — drops frames with no "
            "signal at all (all-zero, dead-flat or corrupt) before "
            "stacking; they break registration. Faint subs are kept.</li>"
            "<li><b>Pixel rejection (auto)</b> — removes hot pixels, "
            "cosmics and trails; algorithm adapts to frame count. "
            "Recommended.</li>"
            "<li><b>Frame weighting (wFWHM)</b> — weights sharper subs "
            "higher for better SNR.</li>"
            "<li><b>Frame quality filters</b> — drop bad subs "
            "<i>before</i> they are registered.  Tick any of "
            "<b>Weighted FWHM</b> (softness), <b>Roundness</b> (guiding "
            "errors / wind), <b>Star count</b> (clouds, haze) or "
            "<b>Background level</b> (moonlight, twilight).  "
            "<b>Mode</b> decides how the numbers are read: "
            "<i>% best</i> keeps that share of the best frames, "
            "<i>k-sigma</i> rejects beyond k standard deviations.  "
            f"Applied only from <b>{FILTER_MIN_FRAMES} frames</b> per "
            "filter: every dropped sub costs signal-to-noise (noise scales "
            "with 1/√n), and on a short run that loss outweighs what "
            "removing the worst frame gains — a real 8→6 frame test raised "
            "the background noise by 19%.  Above the threshold the log warns "
            "when the filters drop more than 15% of a set.</li>"
            "<li><b>Output normalization</b> — normalises the final "
            "frame's background level.</li>"
            "<li><b>Save rejection map</b> — QA artifact of what was "
            "rejected.</li>"
            "<li><b>Background extraction</b> — flattens gradients "
            "per sub before registration.</li>"
            "<li><b>Register via plate solving</b> — WCS-based "
            "registration (also aligns filters to each other for free).  "
            "<b>+ use distortion master</b> adds <tt>-disto=master</tt> so "
            "Siril loads the matching distortion master per image and "
            "corrects optical distortion — only useful if you have those "
            "masters set up.</li>"
            "<li><b>Delete _work/ when finished</b> — remove the "
            "intermediates after a successful run to reclaim disk space.  "
            "The masters and the colour image live outside <tt>_work/</tt>, "
            "so master reuse keeps working.</li>"
            "<li><b>💾 / 📂 next to the preset</b> — save the complete "
            "configuration to a <tt>.json</tt> file, or load one back "
            "(handy to share a recipe or keep one per target type).</li>"
            "<li><b>Drizzle</b> — 2× / 3× upsampling; needs "
            "well-dithered subs and makes much larger files.</li>"
            "<li><b>Copy frames</b> — copy instead of symlink, for "
            "drives where symlinks are not permitted.</li>"
            "<li><b>Align filters (LRGB)</b> — put all masters on one "
            "shared grid; writes the aligned masters to masters/.</li>"
            "<li><b>Plate-solve final masters</b> — tag each master with "
            "a WCS solution.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Colour Composition</h3>"
            "<p>When <b>Create colour composite</b> is on, the aligned "
            "masters are combined with Siril's <tt>rgbcomp</tt> into one "
            "colour image (this implies filter alignment).  The "
            "<b>Palette</b> and the four <b>L / R / G / B</b> mapping "
            "dropdowns are auto-filled from the filters found — override "
            "any of them manually:</p>"
            "<ul>"
            "<li><b>Auto</b> — detects LRGB / SHO / HOO from the filters "
            "(broadband first; only ever a palette it can actually "
            "fill).</li>"
            "<li><b>LRGB</b> — R, G, B channels with a Luminance layer.</li>"
            "<li><b>RGB</b> — R, G, B only (no luminance).</li>"
            "<li><b>SHO</b> — Hubble palette: SII→R, Ha→G, OIII→B.  "
            "Channels are normalized to Ha first (see below).</li>"
            "<li><b>HOO</b> — Ha→R, OIII→G and B.</li>"
            "<li><b>HaRGB</b> — broadband RGB with the Ha master "
            "screen-blended into Red (adjustable <b>Ha → Red</b> strength) "
            "for stronger emission-nebula detail.  PCC is skipped (the Red "
            "channel is no longer photometric); balance colour manually.</li>"
            "</ul>"
            "<p>The composite (<span style='font-family:monospace;"
            "color:#aaddaa;'>TARGET_RGB</span> / <span "
            "style='font-family:monospace;color:#aaddaa;'>TARGET_SHO</span>…) "
            "is written to the output folder and loaded in Siril.  Needs at "
            "least R, G and B mapped.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Narrowband (SHO / HOO) order</h3>"
            "<p>Following Siril's guidance for narrowband, the channels are "
            "<b>normalized before combining</b> — each is linear-matched to "
            "the Ha reference (<tt>linear_match</tt>) so the strong Ha "
            "doesn't dominate and turn the result green.  Then they are "
            "combined <b>linearly</b>; you stretch and fine-tune colour "
            "afterwards.  Normalized copies (<span style='font-family:"
            "monospace;color:#aaddaa;'>*_nbnorm</span>) are written under "
            "<tt>_work/helpers/</tt> so the masters stay untouched.  PCC is "
            "skipped "
            "(mapped emission lines aren't photometric).  Turn normalization "
            "off with <i>Normalize narrowband channels</i> if you prefer to "
            "balance manually.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Luminance (LRGB) — the correct order</h3>"
            "<p>Following Siril's own guidance, the <b>L</b> channel is "
            "<b>not</b> baked into the colour image.  Instead the script "
            "composes and colour-calibrates <b>RGB only</b> (linear), and "
            "keeps your L master separate.  That is deliberate:</p>"
            "<ul>"
            "<li>Photometric Colour Calibration must run on linear RGB — a "
            "baked-in luminance skews the star photometry.</li>"
            "<li>Luminance should be combined <b>after</b> stretching: "
            "linear L gives weak, washed-out colour.</li>"
            "</ul>"
            "<p>So the recommended finish is: stretch the calibrated "
            "<b>TARGET_RGB</b>, stretch the L master, then combine them last "
            "in Siril (RGB Composition → luminance, or "
            "<tt>rgbcomp -lum</tt>).</p>"
            "<p><b>Quick linear LRGB</b> (option, off by default) restores "
            "the old one-step behaviour: L is baked in linearly and the file "
            "is named <span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_LRGB</span>.  Convenient (one file) but less accurate "
            "colour — use only for a fast look.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Auto-finish</h3>"
            "<p>With <b>Auto-finish</b> on, the fresh composite is "
            "cleaned up automatically — each step is resilient (a failure "
            "is logged and skipped, never fatal):</p>"
            "<ol>"
            "<li><b>Plate-solve</b> the colour image (needed for PCC).</li>"
            "<li><b>Background extraction</b> (subsky) to flatten "
            "gradients.</li>"
            "<li><b>Photometric Colour Calibration</b> (pcc) for neutral, "
            "physically-correct star colours.</li>"
            "<li><b>SCNR</b> green-cast removal.</li>"
            "</ol>"
            "<p>The result stays <b>linear</b> — saved over the composite, "
            "ready for your own stretch.  Tick <b>+ save stretched "
            "preview</b> to also get an autostretched "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_PALETTE_preview</span> for a quick look; the linear "
            "file is left untouched for serious processing.</p>"
            "<p style='color:#888;'>PCC needs its photometry catalog "
            "reachable (online, or a local Gaia catalog installed).  If it "
            "can't reach one, calibration is skipped and the composite is "
            "still saved.</p>")
        tabs.addTab(tab2, "The Pipeline")

        tab_ref = QTextEdit()
        tab_ref.setReadOnly(True)
        tab_ref.setHtml(
            "<h2 style='color:#88aaff;'>Colour Palettes — Reference</h2>"
            "<p>Every palette runs on the <b>co-registered, "
            "background-extracted per-filter masters</b> (identical pixel "
            "grid).  One colour image is produced per run — pick the palette "
            "in the dropdown, or leave it on <b>Auto</b>.  Below is exactly "
            "what each variant does, with the Siril commands it issues.</p>"
            "<p style='color:#888;'><i>Legend:</i> <tt>TARGET</tt> = object "
            "name; masters are the aligned <tt>masters/TARGET_FILTER.fit</tt> "
            "files.  <b>Auto-finish</b> = plate-solve → "
            "background → (PCC) → SCNR → save linear.</p>"

            "<hr><h3 style='color:#88aaff;'>LRGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(default, broadband + luminance)</span></h3>"
            "<p><b>Mapping:</b> R=Red&nbsp; G=Green&nbsp; B=Blue&nbsp; "
            "L=Luminance <i>(kept separate)</i></p>"
            "<p>RGB is composed and colour-calibrated on its own; the L "
            "master is <b>not</b> baked in (that would skew PCC and give weak "
            "colour).  You add L after stretching.</p>"
            "<pre style='color:#aaddaa'>rgbcomp  R  G  B  -out=TARGET_RGB\n"
            "platesolve → subsky → pcc → rmgreen → save   (linear)</pre>"
            "<p><b>Output:</b> <tt>TARGET_RGB.fit</tt> (calibrated, linear) "
            "&nbsp;+&nbsp; <tt>masters/…_LUMINOS.fit</tt> kept separate.<br>"
            "<b>You finish:</b> stretch RGB and L, then combine luminance "
            "last (RGB Composition → luminance, or <tt>rgbcomp -lum</tt>).</p>"

            "<hr><h3 style='color:#88aaff;'>RGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(broadband, no luminance)</span></h3>"
            "<p><b>Mapping:</b> R=Red&nbsp; G=Green&nbsp; B=Blue</p>"
            "<pre style='color:#aaddaa'>rgbcomp  R  G  B  -out=TARGET_RGB\n"
            "platesolve → subsky → pcc → rmgreen → save   (linear)</pre>"
            "<p><b>Output:</b> <tt>TARGET_RGB.fit</tt>. Just stretch it.</p>"

            "<hr><h3 style='color:#88aaff;'>Quick linear LRGB &nbsp;"
            "<span style='color:#888;font-weight:normal'>(option, off by "
            "default)</span></h3>"
            "<p>Bakes L in linearly in one step — a single file, but less "
            "accurate colour (PCC runs on the L-mixed image).  For a fast "
            "look only.</p>"
            "<pre style='color:#aaddaa'>rgbcomp -lum=L  R  G  B  "
            "-out=TARGET_LRGB\n"
            "platesolve → subsky → pcc → rmgreen → save   (linear)</pre>"
            "<p><b>Output:</b> <tt>TARGET_LRGB.fit</tt>.</p>"

            "<hr><h3 style='color:#88aaff;'>SHO &nbsp;<span style='color:#888;"
            "font-weight:normal'>(Hubble palette)</span></h3>"
            "<p><b>Mapping:</b> R=SII&nbsp; G=Ha&nbsp; B=OIII</p>"
            "<p>Channels are <b>normalized to Ha first</b> (else the strong "
            "Ha dominates and the image goes green), then combined linearly. "
            "PCC is skipped — mapped emission lines aren't photometric.</p>"
            "<pre style='color:#aaddaa'>linear_match Ha 0 0.92   → SII_nbnorm\n"
            "linear_match Ha 0 0.92   → OIII_nbnorm\n"
            "rgbcomp  SII_nbnorm  Ha  OIII_nbnorm  -out=TARGET_SHO\n"
            "platesolve → subsky → (PCC skipped) → rmgreen → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_SHO.fit</tt> (linear).<br>"
            "<b>You finish:</b> stretch, then colour-balance / saturation to "
            "taste (Ha often still leans green).</p>"

            "<hr><h3 style='color:#88aaff;'>HOO &nbsp;<span style='color:#888;"
            "font-weight:normal'>(bicolour)</span></h3>"
            "<p><b>Mapping:</b> R=Ha&nbsp; G=OIII&nbsp; B=OIII</p>"
            "<pre style='color:#aaddaa'>linear_match Ha 0 0.92   → OIII_nbnorm\n"
            "rgbcomp  Ha  OIII_nbnorm  OIII_nbnorm  -out=TARGET_HOO\n"
            "platesolve → subsky → (PCC skipped) → rmgreen → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_HOO.fit</tt> (linear).</p>"

            "<hr><h3 style='color:#88aaff;'>HaRGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(Ha-enhanced broadband)</span></h3>"
            "<p><b>Mapping:</b> R=Red <i>(+Ha blended in)</i>&nbsp; G=Green"
            "&nbsp; B=Blue&nbsp; L=Luminance <i>(separate)</i></p>"
            "<p>The Ha master is <b>screen-blended into Red</b> at the "
            "<b>Ha → Red</b> strength you set, then composed like RGB.  Values "
            "are in [0,1] so the blend stays bounded.  PCC is skipped (the "
            "Red channel is no longer photometric).</p>"
            "<pre style='color:#aaddaa'>pm \"1-(1-$R$)*(1-k*$Ha$)\"  → "
            "TARGET_RED_Ha      (k = Ha→Red %)\n"
            "rgbcomp  TARGET_RED_Ha  G  B  -out=TARGET_HaRGB\n"
            "platesolve → subsky → (PCC skipped) → rmgreen → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_HaRGB.fit</tt> + L separate.<br>"
            "<b>Note:</b> classic HaRGB is refined <i>after</i> stretching; "
            "this is a linear starting point — tune the strength, or redo the "
            "blend post-stretch for full control.</p>"

            "<hr><h3 style='color:#88aaff;'>Auto detection</h3>"
            "<p>With palette = <b>Auto</b>: R+G+B present → <b>LRGB</b> "
            "(or RGB without L); otherwise Ha+OIII+SII → <b>SHO</b>, "
            "Ha+OIII → <b>HOO</b>.  Broadband wins when it is complete "
            "because it gives natural colour — switch to SHO / HOO / HaRGB "
            "manually for the mapped look.  Auto only ever proposes a "
            "palette whose three channels can actually be filled.  "
            "Filter names are read from the FITS "
            "<tt>FILTER</tt> keyword (LUMINOS/RED/GREEN/BLUE/HA/OIII/SII and "
            "common aliases).  Override the palette and any channel with the "
            "dropdowns.  For several looks from one dataset, run again with a "
            "different palette and tick <b>Reuse existing masters</b> — it "
            "skips stacking + alignment and re-composes in seconds.</p>")
        tabs.addTab(tab_ref, "Palettes")

        tab3 = QTextEdit()
        tab3.setReadOnly(True)
        tab3.setHtml(
            "<h2 style='color:#88aaff;'>Output &amp; Tips</h2>"
            "<p>Results go into an <b>output</b> folder inside your "
            "target folder, with a tidy, self-explaining layout:</p>"
            "<pre style='color:#aaddaa'>output/\n"
            "├─ TARGET_RGB.fit        the finished colour image(s)\n"
            "├─ masters/\n"
            "│   ├─ TARGET_FILTER.fit            aligned (use to combine)\n"
            "│   └─ TARGET_FILTER_fullframe.fit  full, uncropped stack\n"
            "├─ output.md             exactly what the script did\n"
            "├─ todo.md               step-by-step final processing\n"
            "└─ _work/                intermediates — safe to delete\n"
            "    ├─ sequences/  per-filter Siril sequences\n"
            "    ├─ align/      cross-filter alignment\n"
            "    └─ helpers/    _nbnorm, _RED_Ha</pre>"
            "<p><b>output.md</b> is a full processing report (filters, "
            "frame counts, every step and option used).  <b>todo.md</b> "
            "gives the palette-specific, step-by-step final processing "
            "(stretch, luminance combine, colour balance…).</p>"
            "<ul>"
            "<li>The <b>colour composite</b> sits at the top, alone: "
            "<span style='font-family:monospace;color:#aaddaa;'>TARGET_RGB / "
            "_SHO / _HOO / _HaRGB / _LRGB</span> — calibrated and linear, "
            "loaded into Siril automatically.</li>"
            "<li><b>masters/</b> holds two versions per channel: "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_FILTER.fit</span> (aligned to a common grid — combine "
            "these) and "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_FILTER_fullframe.fit</span> (the full, uncropped stack).</li>"
            "<li>Everything else lives under <b>_work/</b> — you can delete "
            "that whole folder any time without losing a result.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Tips</h3>"
            "<ul>"
            "<li>A filter needs at least <b>2</b> light frames to register "
            "and stack; single-frame filters are skipped.</li>"
            "<li>This release stacks <b>lights only</b> (no dark / flat / "
            "bias calibration).  Without flats, expect some vignetting and "
            "dust shadows — apply calibration beforehand, or keep "
            "master-calibrated lights in the folder, for the best result.</li>"
            "<li>The colour composite is produced for you (see the "
            "<b>Palettes</b> tab).  The remaining <b>stretch</b> and, for "
            "LRGB, the final <b>luminance combine</b> are yours — they are "
            "subjective and best done interactively.</li>"
            "<li>Want several looks (LRGB and SHO…) from one night?  Run "
            "again with a different palette and enable <b>Reuse existing "
            "masters</b> — stacking + alignment are skipped, so you only pay "
            "for the composition (seconds).  If only some masters exist "
            "(e.g. a new filter was added), the script reuses what it can "
            "and stacks just the missing filters — and always logs what it "
            "skipped and why.</li>"
            "<li>Re-running is safe: existing outputs are overwritten.  Turn "
            "reuse OFF after changing stacking options or adding frames.</li>"
            "<li>Closing the window mid-run asks first, then stops cleanly "
            "after the current step — finished masters are kept.</li>"
            "</ul>"
            "<hr>"
            "<p style='color:#888;'>Svenesis ImageMono Train "
            f"v{VERSION} — part of the Svenesis Siril script suite.</p>")
        # Tab titles are PLAIN TEXT, not HTML: "&amp;" would show literally,
        # and a lone "&" is Qt's mnemonic marker -- "&&" renders one "&".
        tabs.addTab(tab3, "Output && Tips")

        layout.addWidget(tabs)

        btn_close = QPushButton("Close")
        _nofocus(btn_close)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        try:
            siril.connect()
        except (SirilError, SirilConnectionError, OSError, RuntimeError):
            # The GUI still opens; connection is retried before stacking.
            pass
        win = ImageMonoTrainWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis ImageMono Train v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
            pass
        return app.exec()
    except NoImageError:
        QMessageBox.warning(
            None, "No Image",
            "Could not talk to Siril. Please start it and try again.")
        return 1
    except Exception as e:
        QMessageBox.critical(
            None, "Svenesis ImageMono Train Error",
            f"{e}\n\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
