"""
Svenesis LightCurve
Script Version: 1.0.7
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script turns a folder of sub-exposures of an exoplanet host star into a
differential light curve, and then tells you whether there is a transit in it.

The division of labour follows what each side is demonstrably good at:

  * SIRIL does the staging, calibration, two-pass registration, star
    detection, plate solving and per-frame quality.
  * THIS SCRIPT measures the flux itself, the way EXOTIC and HOPS do:
    every star re-centroided per frame from its registration-predicted
    position (the follow-star that Siril's `light_curve` lacks), subpixel
    circular apertures against a sigma-clipped sky annulus, the aperture
    chosen by point-to-point noise, comparison stars kept by their
    MEASURED scatter, errors from the CCD equation.  Measured on the same
    drifting 142-frame run: 140 points where `light_curve` kept 67.
    Siril's `light_curve` remains intact as the loud fallback.  And the
    script does the analysis: airmass detrending, the transit fit, and --
    most importantly -- the honest question of whether the dip is real.

Validated against EXOTIC on its own HAT-P-32 sample data:
Rp/Rs = 0.1525 +/- 0.0064 against EXOTIC's published 0.1541 +/- 0.0033 --
0.2 sigma apart, at the same residual scatter (0.58% vs 0.55%).

Full manual (per design decision, with the measurement behind it):
https://github.com/sramuschkat/Siril-Scripts/blob/main/Instructions/Svenesis-LightCurve-Instructions.md
Deutsche Anleitung:
https://github.com/sramuschkat/Siril-Scripts/blob/main/Instructions/Svenesis-LightCurve-Instructions_de.md

Features:
- Folder of subs in, light curve out: link -> calibrate -> register ->
  measure -> fit
- Point at any folder above the subs: the scan is recursive, sorts lights
  from calibration frames by header, and drops duplicate exposures
- Calibration finds its own frames: inside your selection, beside the
  lights in the N.I.N.A. LIGHT/FLAT layout, and in a library folder you set
  once.  Masters are stacked and cached automatically; a dark that does not
  match the lights is reported and skipped rather than applied
- Comparison-star ensemble chosen from Siril's own star detection, filtered
  by SNR, saturation, distance from the target, and isolation -- a neighbour
  inside the sky annulus is a seeing-driven trend, not a comparison star
- Target from the frames: OBJCTRA/OBJCTDEC when present, otherwise the
  archive position of the OBJECT name with the reference plate-solved
  around it; the frames outrank a form entry left from a previous target,
  out loud.  Also by pixel position, by RA/Dec, or brightest star
- Mid-exposure times from DATE-OBS + EXPTIME/2, optionally converted to
  BJD_TDB via astropy, from the site position and the target direction
      - Red-noise (beta) correction on every reported significance
- Airmass detrending anchored on the out-of-transit baseline, with a
  one-sided least-trimmed fit so a setting target's ramp is not mistaken
  for -- or absorbed into -- the transit depth
- Quality detrending against Siril's own per-frame FWHM, sky level and star
  count, anchored on the same out-of-transit rows
- Aperture chosen by scanning six radii and measuring, not by formula
- Comparison stars screened by photometering each against the others
- Model-free spike rejection: one satellite used to cost the detection
- Both depth conventions, reported and labelled: the limb-darkened central
  depth the fit measures, and the (Rp/Rs)^2 that EXOTIC, HOPS and
  AstroImageJ quote
- AAVSO Exoplanet Watch submission file (T0, both depths, Rp/Rs, duration)
- Mid-transit time with a calibrated error bar, and chi2/nu against a
  model-independent noise floor
- Limb-darkened transit fit, solved SIMULTANEOUSLY with the systematics:
  a grid over (T0, duration, shape) with the depth, the baseline and every
  systematic coefficient solved analytically at each node.  No optimiser to
  get stuck, no random seed, the same answer every run
- Stacked detection significance with the correct standard error, checked
  against the baseline on BOTH sides of the event so a monotonic trend
  cannot be reported as a transit, and a refusal to claim anything below a
  CALIBRATED floor: the grid search spans ~40 000 nodes, so the number is
  not a Gaussian sigma.  Measured over 1200 transit-free noise runs, 4.5
  gives 0.25% false alarms where 3.0 gives 7.67%, and the measured rate is
  printed next to every result
- Binned overlay, residual panel, per-point scatter and the measured RMS
- CSV export of the full series, PNG export of the plot, plain-text report
- Every number that is an estimate is marked as one

Run from Siril via Processing -> Scripts.  Place Svenesis-LightCurve.py inside a
folder named Utility in one of Siril's Script Storage Directories
(Preferences -> Scripts).

(c) 2026
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.0.7 - HOPS-compatible mode, Claret coefficients from Phoenix, and
        three review passes over the whole script
      - Fit mode dropdown: "Svenesis — blind detection" (default) or
        "HOPS-compatible — ephemeris-locked".  HOPS mode takes the orbit
        from the archive (a/R*, i, e, w; a/R* from the duration with b=0
        when missing), fits Rp/R*, mid-time (±0.2 d), normalisation and
        HOPS's detrending (airmass / time / time², plus the meridian-flip
        step when one was detected), averages the model over each
        exposure in 10 s sub-steps, uses HOPS's photometry (target over
        the raw comp sum) and outlier filter, rescales the errors, and
        samples with a seeded Goodman-Weare ensemble sampler.  Verified
        head to head against pylightcurve's Fitting class with emcee on
        HAT-P-32: outliers and scale factor identical, parameters within
        0.1 sigma.  The blind test still decides whether a transit is
        CLAIMED; a fitted contact outside the run is flagged in the log,
        results.txt (#WARNING) and the report.
      - "Compute Claret (Phoenix)": ExoTETHyS's SAIL method reimplemented
        on the Phoenix 2018 models (fetched at run time, cached under
        ~/.svenesis), verified against ExoTETHyS to 1e-7.  Filter names
        as HOPS spells them, plus RGB (RED/GREEN/BLUE as the nearest
        standard passband, labelled), Johnson/Cousins/Sloan/2MASS, and
        HOPS's clear/luminance/ExoPlanet-BB curves from pylightcurve's
        photometry database (MIT licence, fetched at run time).
      - Frames are sequenced by DATE-OBS, not file name (N.I.N.A. puts
        the sensor temperature in the name; "-10.10C" sorted after
        "-10.00C" and read as a second flip).  The time-stamp convention
        is checked against DATE-AVG/DATE-END instead of assumed; the
        Siril fallback's times get the same correction.
      - From reading pylightcurve 4 (MIT): the occultation integral is
        analytic (1e-15 vs pylightcurve, 3e-6 vs the ring integration
        kept as reference, a quarter of the cost); transit contacts are
        found on the actual orbit by bisection.
      - The expected curve of a TESS candidate inverts SPOC's
        limb-darkened depth instead of taking its square root (1.42 %
        was drawn as 1.68 %).
      - Three independent review passes (photometry, fit statistics,
        frame/time handling, Phoenix, ephemerides) found no high-severity
        error and about forty smaller ones, all fixed: iterative comp
        ranking, leave-one-out spike clipping, chi2/nu bias corrections
        with a 32-point noise floor and a scatter bar, Rp/R* bar with the
        impact-parameter spread, red-noise beta by phase averaging,
        collinear bases dropped at r > 0.995, geocentric BJD fallback,
        header RA/Dec unit rules, DATAMAX-aware clip level, every array
        filtered together after a dropped row, NaN airmass no longer
        aborting HOPS mode, grazing orbits keeping a finite duration, a
        Claret thread that reports instead of dying, and a dozen
        wording fixes in log, report and HTML.
      - Test suite: over 700 checks (was ~450).  Help, README and both
        manuals describe all of the above.

1.0.6 - The chart compares measured against expected, and no frame
        vanishes from the curve unnamed
      - Measured contacts drawn as dashed lines with clock times,
        Δduration and Δstart/Δend spans (measured − predicted) on a
        detection; one duration formatter for every label; the legend
        moved above the plot; the whole prediction has an on/off switch.
      - Siril clamps calibrated floats to [0, 1], so a flat division
        pushed bright comps into a ceiling their raw frames never
        touched — 73 of 223 frames lost without a word.  Now: per-frame
        accounting of every loss, a headroom guard (comps at 70 % of the
        clip level dropped up front), the ranked reserve promoting a
        replacement for each dropped comp, and a clamp warning.
      - "Save results…" writes results.txt in HOPS's exact layout
        (parameter table, #Filter/#Epoch block, residual statistics with
        a pure-numpy Shapiro-Wilk W verified against scipy) and the full
        narrative report as report.txt.
      - Manuals grew a beginner's glossary and plainer language.
1.0.5 - A ranking key no longer prints as an SNR: on runs where
        findstar carries no SNR, the Stars tab and the report showed the
        ranking artefact as "SNR 2, 1, 1"; it now reads "—".
1.0.4 - TESS candidates (TOI-XXXX.NN) get their ephemeris from the
        archive's TOI table (ppm and hours converted), with the TFOPWG
        disposition said out loud and a red warning on false positives.
      - The expected curve no longer needs a detection; its epoch comes
        from the window's centre, and a prediction outside the run
        names the nearest transit in hours.
      - A wall-clock axis on top (local time from DATE-LOC, else UTC),
        predicted contacts stamped in clock time, the meridian flip
        drawn as a dashed marker, and detection markers only on a
        claimed fit.  New "Reading the chart" help tab.
1.0.3 - The expected transit from the archive ephemeris is drawn beside
        the fit (BJD_TDB only) and the O−C quoted; rejected points shown
        as red crosses; legend with T0, Rp/R* and the detrending bases;
        residual panel with STD and lag-1 autocorrelation verdict;
        provenance title; measured duration as a double arrow.  Fixed:
        the model overlay used the trended model on detrended points.
1.0.2 - Per-point error bars in both panels, behind a switch.
1.0.1 - The airmass basis says in the log why it was skipped.
1.0.0 - Initial release
"""
from __future__ import annotations

import os
import re
import sys
import csv
import json
import io
import http.client
import urllib.parse
import urllib.request
import math
import shutil
import pickle
import datetime
import traceback

import sirilpy as s

try:
    from sirilpy.exceptions import (
        SirilError, SirilConnectionError, CommandError, DataError,
    )
except ImportError:                                   # older sirilpy
    class SirilError(Exception):
        pass

    class SirilConnectionError(SirilError):
        pass

    class CommandError(SirilError):
        pass

    class DataError(SirilError):
        pass

s.ensure_installed("numpy", "PyQt6", "matplotlib", "astropy")

# Start multiprocessing's resource-tracker helper NOW, while the process
# environment is still pristine.  sirilpy moves pixel data over
# multiprocessing.shared_memory, and the FIRST such access spawns this
# helper (`python -c ...`) mid-run — on macOS that spawn was seen dying
# with `PermissionError: Operation not permitted` during importlib's
# path scan and being relaunched, spraying tracebacks into Siril's log
# (harmless: the run completed identically, but a traceback that means
# nothing trains people to ignore the ones that do).  Started here it
# inherits a working environment once; if it cannot start at all,
# nothing is lost — Python relaunches it on demand exactly as before.
try:
    from multiprocessing import resource_tracker as _resource_tracker
    _resource_tracker.ensure_running()
except Exception:                                     # noqa: BLE001
    pass

import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QFileDialog, QMessageBox, QTabWidget, QTextEdit,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase
from PyQt6.QtCore import QUrl


def fixed_font_family() -> str:
    """The platform's fixed-pitch family by name.  A stylesheet asking
    for the generic "monospace" makes Qt look for a family literally
    called Monospace, which macOS lacks -- a warning in Siril's log and
    70 ms of alias building on every window."""
    try:
        fam = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont).family()
        return fam or "monospace"
    except Exception:                        # noqa: BLE001
        return "monospace"

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from sirilpy import LogColor

VERSION = "1.0.7"

# The full manual on GitHub, linked from the help dialog.  The in-app
# tabs are the quick reference; the manual carries the measurements
# behind every design decision, per section, in two languages.
_DOCS_BASE = ("https://github.com/sramuschkat/Siril-Scripts/blob/main/"
              "Instructions/Svenesis-LightCurve-Instructions")
DOCS_URL_EN = f"{_DOCS_BASE}.md"
DOCS_URL_DE = f"{_DOCS_BASE}_de.md"

SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "LightCurve"
# The NASA Exoplanet Archive's TAP service.  Reached with urllib rather
# than astroquery: astroquery ships in some Siril installs and not others,
# and a lookup that works on one machine and not the next is worse than
# none.  The whole call is one URL and the csv module.
ARCHIVE_TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
ARCHIVE_TIMEOUT_S = 20.0
# How far the per-frame OBJCTRA/OBJCTDEC may scatter before the folder is
# treated as holding more than one target.  Generous: these come from the
# sequence plan, so they are usually bit-identical.
# How many headers the folder picker reads to prefill the target fields.
# It runs on the UI thread: 30 compressed N.I.N.A. subs measured 153 ms,
# which is a click; several hundred would be a freeze.
PROBE_HEADERS = 30
HEADER_RADEC_SPREAD_ARCSEC = 300.0
# How close a computed altitude must come to the one the header records
# before the longitude sign counts as settled.  Generous: the header
# altitude is usually rounded and may be the commanded rather than the
# achieved position, while the WRONG sign is off by tens of degrees.
LON_SIGN_TOLERANCE_DEG = 5.0
# How far the header target and the archive may disagree before the run
# says so.  The measured agreement on this rig is 5.7 arcsec; anything at
# arcminute scale means the name and the pointing describe different
# things, and that is worth a line rather than a silent preference.
TARGET_DISAGREE_ARCSEC = 120.0
# Pre-filled AAVSO observer code.  Saved settings still win: this is only
# what a fresh install starts with.
DEFAULT_OBSCODE = "V57"

LEFT_PANEL_WIDTH = 400

FITS_EXTS = (".fit", ".fits", ".fts", ".fit.fz", ".fits.fz", ".fts.fz")

# Working sub-directory under the chosen folder.  Everything the run creates
# lives here so the source frames are never written to.
WORK_DIRNAME = "_lightcurve"
OUT_DIRNAME = "lightcurve"
# Never descended into by the recursive scan.  "_flux"/"flux" are this
# script's own folder names from before it was renamed: a run that walks
# its own previous output re-ingests staged symlinks and converted frames
# as if they were subs.  The name list is the cheap half of the guard --
# the half that catches folders nobody thought to name is the duplicate
# check in `split_frames`, which works off DATE-OBS and does not care
# where a copy came from.
PRUNED_DIRNAMES = (WORK_DIRNAME, OUT_DIRNAME, "_flux", "flux")

# --- photometry defaults ---------------------------------------------------
# Comparison stars below this signal-to-noise contribute more scatter than
# signal to the ensemble.  Siril reports SNR per detected star; 20 is the
# level at which a comp's own Poisson noise stays well under a millimag on a
# typical amateur sub.
MIN_COMP_SNR = 20.0
# A comp closer than this to the target risks aperture overlap at the ring
# radii `-autoring` picks (6.3 x FWHM outer).  Ten FWHM is comfortably clear.
MIN_COMP_SEPARATION_FWHM = 10.0
# Default size of the ensemble.  More comps average down the ensemble noise,
# but each one added is fainter than the last and the gain flattens quickly.
DEFAULT_N_COMPS = 5
# Below this an ensemble is not an ensemble -- a single comp puts all of its
# own variability straight into the curve.
MIN_COMPS = 2

# How far a comparison star may sit from the target in instrumental
# magnitude when SNR is unavailable.  Two magnitudes down is 16% of the
# flux -- past that a comp adds noise to the ensemble without adding
# usable signal; the same distance up runs into saturation.
COMP_MAG_WINDOW = 2.0

# Siril's `-autoring` derives the photometry rings from the frame's FWHM:
# inner 4.2 x FWHM, outer 6.3 x FWHM.  Read off a real run -- "inner and
# outer photometry ring radii to 8.2 and 12.3 (FWHM is 1.954648)".
AUTORING_OUTER_FWHM = 6.3
AUTORING_INNER_FWHM = 4.2
# Siril's default "radius / half-FWHM" for a DYNAMIC aperture.  Setting it
# is the only way to un-force an aperture that `setphot -aperture=` fixed.
DYNAMIC_APERTURE_RATIO = 4.0
# Siril REFUSES `light_curve` outright when any frame's registration shift
# exceeds this, printing a line it calls a "Warning" and then returning a
# generic error.  Measured against Siril 1.4.4 on EXOTIC's demo set by
# bisection: hypot(dx, dy) = 159.6 px runs, 160.7 px aborts.  The value is
# a fixed number of pixels, not a fraction of the frame.
SIRIL_DRIFT_LIMIT_PX = 160.0
# How far under that limit a re-centred reference must land before it is
# worth switching.  A run that only just squeaks under would abort again
# on the next frame the mount nudges.
DRIFT_LIMIT_MARGIN = 0.95
# Two stars whose outer annuli touch share sky.  A neighbour inside this
# multiple of the outer radius contaminates the aperture AND the sky
# estimate, and the contamination breathes with the seeing -- which reads
# as a slow trend, the same shape a transit has.
COMP_ISOLATION_OUTER = 2.0
# The floor the isolation cut may relax to, in FWHM.  Below this a
# neighbour is inside the APERTURE, which is blended photometry rather
# than a background error -- no report rescues that, so it is never
# traded away for a larger comparison ensemble.
COMP_APERTURE_FLOOR_FWHM = 2.0
# How far the field may drift before the run says so.  Below this the
# geometry filter still runs silently; above it the number is worth
# knowing, because it is what limits which stars can be used at all.
DRIFT_REPORT_PX = 20.0
# How many light_curve calls may fail in a row before the probes stop.
# Three is enough to tell an unlucky aperture from a broken geometry, and
# every further call is another chance to take Siril's process with it.
MAX_PHOTOMETRY_FAILURES = 3
# UNEXPLAINED, and left here so the next reader does not have to rediscover
# it: Siril's "Photometry for star at X, Y in image 0" does not always agree
# with the `-refat=` that produced it.  Three of six comps came back 16, 33
# and 63 px away in one run.  The first guess -- that `-refat` is a search
# hint and Siril locks onto a neighbour -- is refuted by Siril's own log:
# the "No star found in the area ... around X,Y" lines put the search box at
# `requested - 19` in both axes, and two of those three reported positions
# fall OUTSIDE their own 38 px box.  A fit cannot land outside the box it
# ran in, so the reported line is probably a different quantity (or a
# different convention) rather than a mismeasurement.  Until that is
# settled, no filter is built on it.

# --- calibration -----------------------------------------------------------
# Siril's `calibrate` does the pixel arithmetic, for the same reason
# `light_curve` does the photometry: a second implementation of bias/dark/
# flat here would be one more thing to keep in step with the first, and it
# would be worse.  This script decides WHICH frames belong together, builds
# the masters through Siril, and says what it used.
#
# The shape of the user-facing part is Svenesis ImageMono-Train's, because
# asking for three ready-made masters was the wrong question: it demanded
# work -- stacking flats by hand in Siril -- that the script is better
# placed to do.  Here you point at the lights and, once, at wherever your
# reusable darks live.  Flats belong to the session and are found beside
# the lights.
CALIB_PREFIX = "pp_"
KIND_LIGHT, KIND_DARK, KIND_FLAT = "light", "dark", "flat"
KIND_DARKFLAT, KIND_BIAS = "darkflat", "bias"
# A cooled setpoint is an integer and CCD-TEMP is a measurement that wobbles
# by tenths, so a session lands inside this window while two genuinely
# different setpoints do not.
CALIB_TEMP_TOLERANCE_C = 2.0
# How far up from the lights folder to look for sibling FLAT / DARK / BIAS
# folders.  N.I.N.A. writes <target>/LIGHT/<date>/<filter>/, so the flats
# sit three levels up beside the LIGHT folder; four gives one to spare
# without wandering into an unrelated part of the disk.
CALIB_SEARCH_LEVELS = 4
# Below this a "stack" is not a stack.  One frame is adopted as a
# ready-made master instead; two is the fewest that can reject anything.
CALIB_MIN_STACK = 2
# What `CALSTAT` means where a camera or capture program writes it.  Absent
# in raw N.I.N.A. output, which is why its absence is evidence but not
# proof -- hence the three-state answer in `frames_are_calibrated`.
CALSTAT_LETTERS = {"B": "bias", "D": "dark", "F": "flat"}
# HISTORY is free text, so the scan is deliberately narrow: these words in
# a HISTORY card mean somebody calibrated the frame.
CALIB_HISTORY_WORDS = ("calibrat", "bias subtract", "offset subtract",
                       "dark subtract", "flat field", "flat-field",
                       "flat divi")
# A dark taken at a different exposure than the lights removes the wrong
# amount of dark current -- proportionally wrong, and the shot noise it
# adds is not removed at all.  Siril subtracts it anyway without comment,
# so the mismatch is checked here.  2% covers rounding in the header.
DARK_EXPTIME_TOLERANCE = 0.02

# A pixel this close to full scale is clipped for photometric purposes:
# the sensor stopped responding linearly well before the ADC ran out.  The
# Ares-M PRO clips at 65532 of 65535, so the test cannot ask for the exact
# maximum.
SATURATION_FRACTION = 0.98
# Half-width of the box searched around the target for its peak.  Wide
# enough to hold the core wherever the centroid landed, narrow enough not
# to catch a neighbour: at FWHM 2 px this is seven times the core.
SATURATION_BOX_PX = 15

# A target match is called ambiguous when the runner-up sits within this
# multiple of the nearest star's distance.  On a field with hundreds of
# stars the nearest neighbour to an arbitrary point is normally many times
# further than the intended star, so a close second is a real signal that
# the wrong star may have been picked.
TARGET_AMBIGUOUS_RATIO = 3.0

# Above this, a value in the JD column is already a full Julian Date and
# the header's "(+ N)" is a plot label rather than a subtraction.  JD
# 2.4e6 is 1858; nothing a camera writes is below it and a relative offset
# never reaches it.
JD_ALREADY_ABSOLUTE = 2.4e6

# Binning timescales for the red-noise test, as fractions of the fitted
# transit duration.  Tied to the duration rather than to fixed minutes
# because the noise that matters is the noise on the timescale of the
# feature being claimed.
RED_NOISE_WIDTH_FRACTIONS = (0.15, 0.25, 0.4, 0.6, 1.0)
RED_NOISE_MIN_POINTS = 20
RED_NOISE_MIN_BINS = 4
RED_NOISE_PHASES = 4         # bin-grid phases averaged per width (see red_noise_beta)

# Fraction of frames Siril must keep before the light curve is treated
# as a fair sample of the night rather than a seeing-selected subset.
POOR_YIELD_FRACTION = 0.5

# Field rotation between frames beyond which the run is treated as having
# flipped.  A meridian flip is ~180 degrees; ordinary field rotation on an
# alt-az mount is a slow drift of a few degrees across a night, and a
# well-polar-aligned EQ mount shows a fraction of one.  Ten degrees is
# comfortably above the second and far below the first.
FLIP_ROTATION_DEG = 10.0

# --- analysis --------------------------------------------------------------
# Minimum stacked significance below which the script refuses to call a dip a
# transit.  Three sigma is the textbook lower bound for claiming a detection;
# ExoClock and AAVSO submissions want five or more, but that is a decision
# for the submission, not for the fit.
# CALIBRATED, not chosen.  The significance is the best of ~40 000 grid
# nodes (121 T0 x 41 durations x 8 ingress fractions), and nothing in the
# formula knows that.  A search that large finds a contrast on pure noise
# that a single a-priori test never would, so the number is not a Gaussian
# sigma and a threshold picked to look like one is 30x weaker than it reads.
#
# Measured over 1200 transit-free white-noise runs (150 points, 5 h, 4 mmag
# per point), with detection rates on injected transits beside it:
#
#     threshold   false alarm | 4mmag  5mmag  6mmag  8mmag  12mmag
#           3.0         7.67% |  88%    95%   100%   100%    100%
#           3.5         1.92% |  70%    91%    97%   100%    100%
#           4.0         0.50% |  45%    77%    93%   100%    100%
#           4.5         0.25% |  29%    57%    89%   100%    100%
#           5.0         0.00% |  15%    40%    78%   100%    100%
#
# 4.5 halves the false-alarm rate against 4.0 for four points of detection
# at 6 mmag and none at 8, which is the right trade for a test whose only
# job is to refuse to overclaim.  What it costs is the 4-5 mmag case -- a
# dip at or just above the per-point scatter -- and those were never safe
# to claim from one night.
#
# The table has been re-measured three times, and every move is worth
# knowing: the T0 refinement pass (~2700 more nodes per fit) roughly
# doubled every rate, because more search finds a deeper minimum in pure
# noise; making the post-fit scatter robust raised them again, because a
# MAD is a smaller divisor than an RMS outliers have inflated; and the
# move to a limb-darkened model fitted simultaneously with the systematics
# brought them back down, because a rounded shape matches noise less well
# than a shape with a free corner did.
#
# The rate at 4.5 came out at 0.25% before and after that last change --
# coincidence, not stability.  A calibration table is only valid for the
# search AND the statistic AND the model it was measured on, which is why
# it is re-run rather than assumed every time one of the three moves.
#
# Measured WITHOUT the spike clip, which is the conservative direction: on
# pure Gaussian noise the clip removes about 0.2 points per run, trimming
# exactly the tail this table is about.
MIN_DETECTION_SIGMA = 4.5
# The false-alarm rate measured AT that threshold, reported next to every
# claim.  A threshold without its own calibration is a number the reader
# has to trust; with it, they can weigh it.  0.25% is ~700x the
# two-sided Gaussian tail at 4.5 sigma (3.4e-6), as a ~40 000-node search must be -- and 42x better than the 10.58% a 3.0
# floor would now deliver.
MEASURED_FALSE_ALARM = 0.0025
MEASURED_FALSE_ALARM_RUNS = 1200
# Grid resolution of the transit fit.  The parameters are strongly
# correlated, so a dense grid beats a local optimiser that can walk into a
# noise minimum -- and it is deterministic.
# How far the T0 error bar may walk before giving up.  The chi-square
# surface is a parabola near the minimum; if delta-chi2 = 1 is not reached
# within a quarter of the run the fit is unconstrained and NaN is the
# honest answer.
# The half-width of the window the T0 parabola is fitted over, in sampling
# intervals.  Five is measured: the bar tracks the true scatter within
# +/-25% across a 20-to-6 mmag range, while 0.15 and 0.3 of the duration
# over-state it by up to 1.85x.
# Below this many out-of-transit rows the multi-basis solve is fitting more
# coefficients than it has independent information for.
# Spike rejection.  The window is a running median, in POINTS: long enough
# that a single frame cannot define its own reference, short enough that a
# transit is flat across it.  Nine points at a one-minute cadence is nine
# minutes against a transit measured in hours.
# A comparison star scattering this many times the ensemble median is
# doing something the others are not, and differential photometry has no
# way to tell that apart from the target varying.  Three is loose enough
# that ordinary Poisson spread between a bright and a faint comp does not
# trip it.
COMP_VARIABILITY_RATIO = 3.0
# Aperture radii to try, in FWHM.  EXOTIC scans 1.5-6 PSF sigma, which is
# 0.64-2.55 FWHM; this is the same span at a coarser step, because every
# rung costs one full pass of Siril's photometry.
APERTURE_SCAN_FWHM = (0.75, 1.0, 1.3, 1.6, 2.0, 2.5)
# An aperture is only comparable with the best-yielding one if it measured
# a similar number of frames.  Least-scatter alone REWARDS an aperture that
# drops the hard frames: measured on a night with a 3x seeing swing and
# identical underlying noise, a candidate surviving on 7% of frames shows
# 3.81 mmag where the full sample shows 8.08 -- a factor 2.1, bought purely
# by selection.  At 80% the bias is 8.08 -> 7.49, which is small enough to
# live with.
APERTURE_MIN_YIELD_RATIO = 0.8
APERTURE_INNER_RATIO = 2.0
APERTURE_OUTER_RATIO = 3.0
CLIP_WINDOW = 9
CLIP_KAPPA = 4.0
# Past this share the outliers are the data.  Removing a tenth of a light
# curve to make it look better is the opposite of the job.
CLIP_MAX_FRACTION = 0.05
MULTI_DETREND_MIN_ANCHOR = 12
T0_ERROR_CADENCES = 5.0
T0_ERROR_SAMPLES = 21
# The local pass around the winning node.  The coarse T0 step is 105 s on a
# 5 h run, which quantised the answer visibly; 1/20th of that is 5 s, below
# anything the photometry can resolve.
FIT_REFINE_T0_STEPS = 61
FIT_REFINE_DUR_STEPS = 21
# Below this many out-of-transit points the MAD of that subset is too noisy
# to be a noise floor, and chi2/nu falls back to first differences.
CHI2_MIN_OOT = 32
FIT_T0_STEPS = 121
FIT_DURATION_STEPS = 41
FIT_INGRESS_FRACTIONS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
# Quadratic limb darkening.  These are a property of the STAR and the
# FILTER, not of this code: 0.35/0.23 is a reasonable pair for a Sun-like
# host in a broad visual band, and the report names whatever was used
# because the fitted depth depends on it.
LD_U1 = 0.35
LD_U2 = 0.23
# The shape family the fit searches, in place of the trapezoid's eight
# ingress fractions -- same count, but each one is a real transit
# geometry rather than a shape with a free corner.
LD_RP_GRID = (0.06, 0.10, 0.14, 0.18)
LD_B_GRID = (0.0, 0.5)
LD_PHASE_STEPS = 1201
LD_RADIAL_STEPS = 400
# A transit shorter than this fraction of the run cannot be told from a
# handful of bad frames; longer than this and there is no baseline left to
# measure it against.
FIT_MIN_DURATION_FRAC = 0.05
FIT_MAX_DURATION_FRAC = 0.80
# Fraction of the points kept by the one-sided trimmed airmass baseline.
# The dip lives on the faint side, so trimming the faintest 40% removes it
# from the fit once the line straightens.
TRIM_KEEP_FRACTION = 0.60
# Where the BLIND (first-pass) airmass baseline starts to fail.  Measured on
# synthetic runs carrying a known 30 mmag/airmass ramp and a 15 mmag transit,
# 15 noise realisations per point, as the mean error in the recovered slope:
#
#     duty cycle   naive fit   blind trim   out-of-transit anchor
#        25 %         6.2 %       0.9 %            0.8 %
#        38 %         8.6 %       0.9 %            1.0 %
#        50 %        10.1 %       1.0 %            1.0 %
#        60 %        10.7 %       2.3 %            0.9 %
#        75 %        10.8 %      10.6 %            2.7 %
#
# Two things to read out of that.  The blind trim buys an order of magnitude
# over a plain fit and holds to 50 %, where it starts to run out of untouched
# baseline to trim to.  And at 75 % it is no better than the naive fit -- but
# the SECOND pass, anchored on the fitted transit window, still lands within
# 3 %.  So the honest breakdown of the whole two-pass scheme sits well beyond
# this number; what this number marks is where the FIRST pass alone stops
# being trustworthy and the report should say which one carried the result.
BLIND_DETREND_BREAKDOWN = 0.50
BASIS_COLLINEAR_R = 0.995    # |r| above which a second basis is a COPY of the first
                             # (0.95 was tried and threw out sky-vs-seeing pairs at
                             #  r = 0.97 that the solve separates without trouble)

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
QPushButton#CoffeeButton:hover{background-color:#ffe740;border-color:#ddcc00}
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
# Small numeric helpers.  Kept free of Siril and of Qt so they can be checked
# against input with a known answer.
# ---------------------------------------------------------------------------
def _median(values) -> float:
    """True median, including the average of the middle two on even counts."""
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)],
                     dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(np.median(arr))


def _mad_std(values) -> float:
    """Robust standard deviation from the median absolute deviation.

    1.4826 is the factor that makes the MAD an unbiased estimator of sigma
    for Gaussian data.  Used instead of ``std`` everywhere a single bad
    frame -- a satellite through the aperture, a cloud -- would otherwise
    inflate the scatter and hide the transit it is being compared against.
    """
    arr = np.asarray([v for v in values if v is not None and np.isfinite(v)],
                     dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(arr - np.median(arr))))


def _is_fits(name: str) -> bool:
    low = name.lower()
    return low.endswith(FITS_EXTS)


def _fits_files(folder: str) -> list:
    """Every FITS file under ``folder``, recursively, sorted by full path.

    Recursive, because that is how a night is actually filed: point at
    ``WASP-75b`` and the subs are three levels down under
    ``LIGHT/<date>/<filter>/`` while the flats sit under ``FLAT/``.  Only
    reading the top level meant you had to navigate to the exact leaf
    folder, and calibration frames anywhere inside your own selection were
    invisible.

    What comes back is every FITS, of every KIND -- sorting them into lights
    and calibration frames is `split_frames`'s job, and it needs the headers
    to do it.  Two directories are pruned: this script's own working and
    output folders, or a second run would ingest the first run's staged
    symlinks and built masters as if they were subs.

    Sorted by full path, not in directory order: the sequence order decides
    which frame becomes the reference, and a run that picks a different
    reference each time cannot be compared with the previous one.
    """
    out = []
    try:
        for base, dirs, names in os.walk(folder):
            dirs[:] = sorted(d for d in dirs
                             if not d.startswith(".")
                             and d not in PRUNED_DIRNAMES)
            for n in sorted(names):
                if n.startswith(".") or not _is_fits(n):
                    continue
                path = os.path.join(base, n)
                if os.path.isfile(path):
                    out.append(path)
    except OSError:
        return []
    return sorted(out)


def _log_swallowed(exc: BaseException) -> None:
    """One-line stderr trace for an intentionally-swallowed exception.

    Siril surfaces stderr in its console, so a fallback that fires leaves a
    breadcrumb instead of a silent ``pass``.

    This was CALLED from three handlers before it existed.  Nothing noticed,
    because every one of them is a fallback for a case that had not come up
    yet -- and when one finally did, the handler would have raised NameError
    over the top of the error it was there to absorb.  A static check that
    every name resolves now runs in the suite.
    """
    try:
        tb, lineno = exc.__traceback__, -1
        while tb is not None:
            lineno = tb.tb_lineno
            tb = tb.tb_next
        sys.stderr.write(f"[LightCurve] swallowed {type(exc).__name__} "
                         f"(line {lineno}): {exc}\n")
    except Exception:
        pass


def _read_header(path: str):
    """The primary header of a FITS file, or None.

    Reads the header only -- never ``.data`` -- so a folder of
    Rice-compressed subs is not decompressed just to find out when it was
    taken.
    """
    try:
        from astropy.io import fits
        with fits.open(path, memmap=True, ignore_missing_simple=True) as hdul:
            for hdu in hdul:
                try:
                    if int(hdu.header.get("NAXIS", 0)) >= 2:
                        return hdu.header
                except (ValueError, TypeError):
                    continue
            return hdul[0].header
    except Exception:
        return None


def _jd_from_dateobs(date_obs: str) -> float:
    """Julian Date from an ISO ``DATE-OBS``, or NaN.

    Written out rather than imported so a folder with one unreadable header
    does not need astropy to be present just to skip that frame.  The
    algorithm is the standard Fliegel-Van Flandern conversion, exact for
    every Gregorian date.
    """
    txt = (date_obs or "").strip().replace("Z", "")
    if not txt:
        return float("nan")
    # Two forms `fromisoformat` refuses on Python 3.10 and earlier, both
    # met on real data and both previously silent NaN:
    #   N.I.N.A.  2026-08-15T07:26:29.1714366   -- SEVEN fractional digits
    #   MicroObs  2017-12-19T18:33:43.317-0700  -- a UTC offset
    # The N.I.N.A. one mattered most: every frame of a 178-sub run parsed
    # to NaN, so the seeing, sky and star-count bases could never be paired
    # with a light-curve row and the fit quietly ran on airmass alone.
    txt = re.sub(r"(\.\d{6})\d+", r"\1", txt)
    # fromisoformat before Python 3.11 accepts only 3 or 6 fraction
    # digits; N.I.N.A. writes whatever it has.  Pad the seconds fraction.
    txt = re.sub(r"(:\d{2}\.)(\d{1,5})(?!\d)",
                 lambda mm: mm.group(1) + mm.group(2).ljust(6, "0"), txt)
    m = re.match(r"^(.*?)([+-]\d{2}):?(\d{2})$", txt)
    off_h = 0.0
    if m and "T" in m.group(1):
        # An offset means the stamp is NOT UTC.  Subtracting it is the
        # whole point: taking a -0700 local time as UTC is a seven-hour
        # error in a quantity measured in minutes.
        txt = m.group(1)
        off_h = float(m.group(2)) + math.copysign(float(m.group(3)) / 60.0,
                                                  float(m.group(2)))
    try:
        dt = datetime.datetime.fromisoformat(txt)
    except (ValueError, TypeError):
        return float("nan")
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = (dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100
           + y // 400 - 32045)
    day_frac = (dt.hour + dt.minute / 60.0
                + (dt.second + dt.microsecond / 1e6) / 3600.0) / 24.0
    return float(jdn) - 0.5 + day_frac - off_h / 24.0


def chronological_frames(infos):
    """``(infos sorted by DATE-OBS, number of frames that moved)``.

    Every consumer downstream — the sequence index, the flip boundary,
    the point-to-point scatter of the aperture scan, the residual
    autocorrelation — reads "next frame" as "next in time".  File names
    do not promise that: a TOI-4033 run had five frames numbered 43–47
    whose timestamps lay 1–3 h earlier than frame 42's, and in file
    order they looked like a second flip and a 60 mmag step.  The
    file name is not consulted at all: N.I.N.A. had put the sensor
    temperature in it, and "-10.10C" sorts after "-10.00C".  Frames
    whose DATE-OBS cannot be read go to the END in file order — they
    cannot enter a time series anyway, and the photometry drops them
    with a count — rather than being guessed into a slot.
    """
    infos = list(infos or [])
    jds = [_jd_from_dateobs(str(i.get("date_obs") or "")) for i in infos]
    if len(infos) < 2:
        return infos, 0
    order = sorted(range(len(infos)),
                   key=lambda k: (not math.isfinite(jds[k]),
                                  jds[k] if math.isfinite(jds[k]) else 0.0,
                                  k))
    # "Moved" counts the frames that had to pass others, not every
    # position that shifted: one misfiled frame shifts everything behind
    # it by one, and "211 of 223" for thirteen odd file names would send
    # the user hunting for a fault that is not there.  n minus the
    # longest run that was already in order is exactly that number.
    rank = {k: pos for pos, k in enumerate(order)}
    tails = []
    for k in range(len(infos)):
        r = rank[k]
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if tails[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(r)
        else:
            tails[lo] = r
    moved = len(infos) - len(tails)
    return [infos[k] for k in order], moved


def mid_exposure_jd(date_obs: str, exp_s: float, date_avg: str = "",
                    date_end: str = ""):
    """``(JD of mid-exposure, which stamps it came from)``.

    A mid-exposure stamp (DATE-AVG) is taken as it is; failing that the
    midpoint of DATE-OBS and DATE-END; failing that DATE-OBS plus half
    the exposure -- the convention (FITS standard, N.I.N.A., SGP) that
    DATE-OBS is the START.  pylightcurve makes the caller say whether a
    stamp is start, mid or end; a run with DATE-AVG lets this script
    check instead of assume (``timestamp_diagnosis``).
    """
    j_avg = _jd_from_dateobs(date_avg) if date_avg else float("nan")
    j_obs = _jd_from_dateobs(date_obs) if date_obs else float("nan")
    try:
        e = float(exp_s or 0.0)
    except (TypeError, ValueError):
        e = 0.0
    if math.isfinite(j_avg) and (not math.isfinite(j_obs) or abs(
            j_avg - j_obs) * 86400.0 <= e + 60.0):
        # A DATE-AVG hours away from DATE-OBS (a local-time stamp, another
        # day) is not a mid-exposure time; it is ignored for this frame.
        return j_avg, "DATE-AVG"
    j_end = _jd_from_dateobs(date_end) if date_end else float("nan")
    if math.isfinite(j_obs) and math.isfinite(j_end) and j_end > j_obs:
        return 0.5 * (j_obs + j_end), "DATE-OBS/DATE-END"
    if math.isfinite(j_obs):
        return j_obs + e / 172800.0, ("DATE-OBS+exp/2" if e > 0
                                      else "DATE-OBS")
    return float("nan"), ""


def timestamp_diagnosis(infos):
    """What the headers say about DATE-OBS, as ``(kind, message, shift_s)``.

    ``shift_s`` is what must be ADDED to a time built the FITS-standard
    way (DATE-OBS + exp/2 -- Siril's light_curve does exactly that) to
    land on the mid-exposure the native engine uses: 0 for the start
    convention, -exp/2 for a program that stamps mid-exposure, the
    measured offset otherwise.

    kind: 'start' (DATE-AVG sits half an exposure after DATE-OBS, so the
    START convention holds), 'mid' (DATE-AVG equals DATE-OBS: the
    program stamps mid-exposure and the half-exposure must NOT be
    added), 'odd' (DATE-AVG is neither), 'end' (DATE-END only),
    'unchecked' (DATE-OBS alone, the convention is assumed).  A wrong
    convention is half an exposure on every time -- 145 s on 290 s
    subs, more than a good night's T0 error bar.
    """
    infos = list(infos or [])
    offs, exps = [], []
    n_end = 0
    for i in infos:
        j_obs = _jd_from_dateobs(str(i.get("date_obs") or ""))
        j_avg = _jd_from_dateobs(str(i.get("date_avg") or ""))
        if math.isfinite(j_obs) and math.isfinite(j_avg):
            offs.append((j_avg - j_obs) * 86400.0)
            try:
                exps.append(float(i.get("exp_s") or 0.0))
            except (TypeError, ValueError):
                exps.append(0.0)
        elif math.isfinite(j_obs) and (
                _jd_from_dateobs(str(i.get("date_end") or "")) > j_obs):
            n_end += 1
    exp = 0.0
    for i in infos:
        try:
            exp = float(i.get("exp_s") or 0.0)
        except (TypeError, ValueError):
            exp = 0.0
        if exp:
            break
    if offs:
        off = float(np.median(offs))
        e = float(np.median([x for x in exps if x > 0] or [0.0]))
        tol = max(1.0, 0.1 * e)
        # For exposures of a second or two both hypotheses fit inside the
        # tolerance; the closer one wins rather than the first tested.
        if e > 0 and abs(off - 0.5 * e) <= tol \
                and abs(off - 0.5 * e) <= abs(off):
            return "start", (
                f"DATE-AVG sits {off:.1f} s after DATE-OBS on {len(offs)} "
                f"frame(s), half the {e:g} s exposure: DATE-OBS is the "
                "exposure START, as assumed; mid-exposure taken from "
                "DATE-AVG."), 0.0
        if abs(off) <= tol:
            return "mid", (
                f"DATE-AVG equals DATE-OBS on {len(offs)} frame(s): this "
                "program stamps MID-exposure. Times taken from DATE-AVG; "
                "no half-exposure added, which would have put every point "
                f"{0.5 * e:.0f} s late."), -0.5 * e
        if abs(off) > e + 60.0:
            # mid_exposure_jd ignores such a DATE-AVG frame by frame
            return "odd", (
                f"DATE-AVG sits {off:.0f} s from DATE-OBS on {len(offs)} "
                f"frame(s) — more than the {e:g} s exposure plus a minute, "
                "so it is not a mid-exposure stamp and is IGNORED; DATE-OBS "
                "is taken as the exposure start and half the exposure "
                "added. Check the capture program's clock settings."), 0.0
        return "odd", (
            f"DATE-AVG sits {off:.1f} s after DATE-OBS on {len(offs)} "
            f"frame(s) — neither 0 nor half the {e:g} s exposure. "
            "DATE-AVG is taken as the mid-exposure time; check the "
            "capture program's clock settings."), off - 0.5 * e
    if n_end:
        return "end", (
            f"DATE-END present on {n_end} frame(s): mid-exposure taken as "
            "the midpoint of DATE-OBS and DATE-END."), 0.0
    return "unchecked", (
        "No DATE-AVG or DATE-END in the headers: DATE-OBS is taken as "
        f"the exposure START and half of {exp:g} s added. If your "
        "capture program stamps mid-exposure instead, every time below "
        f"is {0.5 * exp:.0f} s late."), 0.0


def utc_offset_hours(date_obs: str, date_loc: str):
    """The site's UTC offset in hours, or None when it cannot be known.

    N.I.N.A. writes ``DATE-LOC`` (the local civil clock) next to
    ``DATE-OBS`` (UTC) into every frame, and their difference IS the
    observatory's UTC offset — time zone AND daylight saving already
    folded in, with nothing to configure and no tz database to guess
    from a longitude.  Rounded to a quarter hour because real offsets
    come in nothing finer (Nepal is :45), which also swallows the
    sub-second write skew between the two stamps.  Anything beyond
    ±14 h is no time zone on Earth and returns None rather than a
    clock that lies.
    """
    j_utc = _jd_from_dateobs(date_obs)
    j_loc = _jd_from_dateobs(date_loc)
    if not (math.isfinite(j_utc) and math.isfinite(j_loc)):
        return None
    off = round((j_loc - j_utc) * 24.0 * 4.0) / 4.0
    if abs(off) > 14.0:
        return None
    return off


def clock_hhmm(jd_utc_val: float, utc_off_h=None) -> str:
    """``HH:MM`` civil clock reading for a UTC Julian Date.

    A planning tool speaks in wall-clock time ("start 21:50, flip
    00:55") and a light curve in Julian Dates; this is the bridge.
    The +0.5 moves from the JD convention (integer boundary at NOON
    UTC) to the civil one (midnight), the offset shifts to local time
    when the caller knows it, and the rounding is symmetric so 23:59:31
    reads 00:00, not 24:00.
    """
    if jd_utc_val is None or not math.isfinite(jd_utc_val):
        return ""
    v = jd_utc_val + (utc_off_h or 0.0) / 24.0
    mins = int(round(((v + 0.5) % 1.0) * 1440.0)) % 1440
    return f"{mins // 60:02d}:{mins % 60:02d}"


def dur_hhmm(hours: float) -> str:
    """``H h MM min`` for a duration in hours, or "" when unknowable.

    One formatter for every duration the chart prints — the measured
    arrow, the expected arrow and their delta all speak through it, so
    they can never round differently.  The rollover keeps 1.9999 h from
    reading "1 h 60 min".
    """
    if hours is None or not math.isfinite(hours) or hours < 0.0:
        return ""
    hh = int(hours)
    mm = int(round((hours - hh) * 60.0))
    if mm == 60:
        hh, mm = hh + 1, 0
    return f"{hh} h {mm:02d} min"


def flip_boundary_index(homographies):
    """Index of the first frame past the meridian flip, or None.

    The rotation is read off each homography exactly the way
    ``rotation_spread_deg`` reads it; the boundary is the first frame
    sitting more than 90° (on the circle) from the first readable
    frame.  90° splits the two clusters a real flip produces — frames
    live at ~0° or ~180°, never in between — while staying far above
    any genuine field rotation a tracked run can accumulate.  The
    caller turns the index into a TIME via that frame's DATE-OBS, so
    the flip can be drawn where it happened instead of only warned
    about.
    """
    base = None
    for i, h in enumerate(homographies or []):
        if h is None:
            continue
        try:
            h00 = float(getattr(h, "h00", 0.0))
            h10 = float(getattr(h, "h10", 0.0))
        except (TypeError, ValueError):
            continue
        if abs(h00) < 1e-12 and abs(h10) < 1e-12:
            continue                    # unset registration, not a rotation
        ang = math.degrees(math.atan2(h10, h00))
        if base is None:
            base = ang
            continue
        if abs((ang - base + 180.0) % 360.0 - 180.0) > 90.0:
            return i
    return None


def _sexagesimal(text: str) -> float:
    """Degrees from ``12:34:56.7``, ``12 34 56.7`` or a plain decimal.

    Returns NaN for anything unparseable.  Hours-vs-degrees is the caller's
    problem: this only splits and combines the fields, because a helper that
    guesses the unit is a helper that silently puts a target 15x off.
    """
    txt = (text or "").strip()
    if not txt:
        return float("nan")
    txt = txt.replace(",", ".")
    parts = [p for p in re.split(r"[\s:hdms\'\"°]+", txt) if p]
    if not parts:
        return float("nan")
    try:
        vals = [float(p) for p in parts[:3]]
    except ValueError:
        return float("nan")
    sign = -1.0 if txt.lstrip().startswith("-") else 1.0
    total = abs(vals[0])
    if len(vals) > 1:
        total += abs(vals[1]) / 60.0
    if len(vals) > 2:
        total += abs(vals[2]) / 3600.0
    return sign * total


def _gmst_deg(jd_ut: float) -> float:
    """Greenwich mean sidereal time in degrees for a UT Julian Date."""
    d = jd_ut - 2451545.0
    return (280.46061837 + 360.98564736629 * d) % 360.0


def _altitude_deg(jd_ut: float, ra_deg: float, dec_deg: float,
                  lat_deg: float, lon_deg_east: float) -> float:
    """Apparent altitude of a fixed target, in degrees.

    Plain spherical trigonometry: no refraction, and the catalogue J2000
    position is used as if it were apparent, so precession, nutation and
    aberration are all absent.  Measured against astropy for WASP-75 from
    central Texas across one night: the altitude is out by up to 21
    arcminutes and the airmass by up to 0.044.

    That is fine HERE and nowhere else, because the airmass is a DETRENDING
    BASIS, not an ephemeris.  The fit removes a linear ramp in it; an error
    that is itself a smooth function of time is absorbed almost entirely by
    the same linear term, and what survives is far below the per-point
    scatter.  Do not reuse this to point a telescope.
    """
    for v in (jd_ut, ra_deg, dec_deg, lat_deg, lon_deg_east):
        if v is None or not np.isfinite(v):
            return float("nan")
    ha = math.radians((_gmst_deg(jd_ut) + lon_deg_east - ra_deg) % 360.0)
    dec = math.radians(dec_deg)
    lat = math.radians(lat_deg)
    sin_alt = (math.sin(dec) * math.sin(lat)
               + math.cos(dec) * math.cos(lat) * math.cos(ha))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    return math.degrees(math.asin(sin_alt))


def _airmass(alt_deg: float) -> float:
    """Kasten & Young (1989) airmass, or NaN below the horizon.

    The plain ``sec z`` runs away near the horizon and is already 2% out at
    60 degrees zenith distance; Kasten & Young stays within 0.1% down to the
    horizon itself, which matters because the ramp being fitted is largest
    exactly where the target is lowest.
    """
    if alt_deg is None or not np.isfinite(alt_deg) or alt_deg <= 0.0:
        return float("nan")
    z = math.radians(alt_deg)
    return 1.0 / (math.sin(z)
                  + 0.50572 * (alt_deg + 6.07995) ** -1.6364)


# ---------------------------------------------------------------------------
# Reading what Siril produced
# ---------------------------------------------------------------------------
def _parse_light_curve_dat(path: str):
    """``(jd, diff_mag, err, n_unmeasured)`` from Siril's ``light_curve.dat``.

    The JD column is already the MIDDLE of the exposure -- verified against
    178 raw headers of a 60 s run: Siril's times sit 0.02 s from
    ``DATE-OBS + EXPTIME/2`` and 30.00 s from ``DATE-OBS``.  This file used
    to carry a `_mid_exposure_jd` helper to add that half-exposure itself;
    nothing called it, and calling it would have shifted every mid-transit
    time 30 s late.  Recorded here because "should I add EXPTIME/2?" is the
    obvious question and the answer is no.


    The file is three columns -- ``JD_UT``, ``V-C``, ``err`` -- under a
    comment header.  Two traps, both found on real data:

    **The header offset is a LABEL, not a subtraction.**  Siril writes
    ``#JD_UT (+ 2461267)`` and then puts the FULL Julian Date in the
    column underneath.  Adding the declared offset therefore doubles it:
    the WASP-75b run came out at JD 4922534, the year 8600, which is what
    astropy was complaining about with "date outside the range 1900-2100
    AD".  The offset is now applied only when the column clearly does NOT
    already hold one -- a real JD is above 2.4 million, and nothing else
    plausibly is -- so both conventions read correctly and neither can
    double.

    **``nan`` parses as a float.**  Siril emits a row for every frame it
    attempted, with ``V-C`` set to ``nan`` where the photometry failed.
    Counting those as points turned 3 real measurements into "35
    photometric points" on the run that prompted this.  Unmeasured rows
    are dropped and counted, so the caller can say how many were dropped
    rather than inflating the sample.
    """
    jds, mags, errs = [], [], []
    offset = 0.0
    dropped = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    m = re.search(r"\(\s*\+\s*([0-9]+(?:\.[0-9]+)?)\s*\)", line)
                    if m:
                        try:
                            offset = float(m.group(1))
                        except ValueError:
                            offset = 0.0
                    continue
                parts = re.split(r"[\s,;]+", line)
                if len(parts) < 2:
                    continue
                try:
                    t = float(parts[0])
                    v = float(parts[1])
                except ValueError:
                    continue
                if not math.isfinite(t):
                    continue
                if not math.isfinite(v):
                    dropped += 1        # Siril tried and could not measure
                    continue
                e = float("nan")
                if len(parts) > 2:
                    try:
                        e = float(parts[2])
                    except ValueError:
                        e = float("nan")
                jds.append(t)
                mags.append(v)
                errs.append(e)
    except OSError:
        return np.empty(0), np.empty(0), np.empty(0), 0
    if not jds:
        return np.empty(0), np.empty(0), np.empty(0), dropped
    jd = np.asarray(jds, dtype=float)
    if offset and float(np.median(jd)) < JD_ALREADY_ABSOLUTE:
        jd = jd + offset
    return (jd, np.asarray(mags, dtype=float),
            np.asarray(errs, dtype=float), dropped)


# ---------------------------------------------------------------------------
# Detrending
# ---------------------------------------------------------------------------
def airmass_detrend(diff_mag, airmass, oot_mask=None):
    """Remove a linear airmass ramp from a differential light curve.

    Returns ``(detrended, slope_mag_per_airmass, intercept)``, with the
    slope and intercept ``None`` when no fit was possible.

    The naive version of this -- fit a line through every point -- absorbs
    part of the transit depth whenever the dip correlates with the ramp,
    which is the standard evening-target case: the star sets during egress,
    so airmass and dimming rise together and the line splits the difference.

    With ``oot_mask`` (True where the point is known to be out of transit,
    from a first fit) the baseline is fitted DIRECTLY on those rows.  That is
    exact, and it is the second pass of the fit -> mask -> re-detrend ->
    re-fit refinement the caller runs.

    Without a mask -- the first pass, when the window is not yet known --
    the anchoring is a ONE-SIDED least-trimmed fit rather than a sigma clip.
    A sigma clip seeded from the all-points line is a no-op in exactly the
    case that motivates it: the seed line already tilts into the dip, so no
    in-transit residual ever exceeds the threshold.  Iterating instead on
    the brightest-residual 60% works because the dip lives on the FAINT side
    and therefore falls into the trimmed 40% as soon as the line
    straightens.  A final pass re-admits every point within 2 MAD-sigma of
    the trimmed core, so the baseline ends up using all the real
    out-of-transit data rather than only the brightest half.

    Trimming selects on the residual, not on airmass, so the slope stays
    unbiased on dip-free data; the intercept shifts, which is harmless
    because a differential magnitude zero point is arbitrary anyway.

    Breakdown, stated rather than hidden.  The blind pass holds to about
    ``BLIND_DETREND_BREAKDOWN`` duty cycle and then runs out of untouched
    baseline to trim to: at 75 % coverage it is no better than the naive fit
    it replaces.  The out-of-transit anchor above is what carries the result
    from there -- it still lands within 3 % at 75 % -- which is why the
    caller runs both passes and why the report names the one that was used.
    See the constant's own comment for the measured table.
    """
    ys = np.asarray(diff_mag, dtype=float)
    if airmass is None:
        return ys.copy(), None, None
    xs = np.asarray(airmass, dtype=float)
    good = np.isfinite(xs) & np.isfinite(ys)
    if good.sum() < 3 or float(np.ptp(xs[good])) < 0.01:
        # No spread in airmass means no ramp to remove -- and a line fitted
        # through a vertical stripe is arbitrary.
        return ys.copy(), None, None

    if oot_mask is not None:
        anchor = good & np.asarray(oot_mask, dtype=bool)
        if anchor.sum() >= 3 and float(np.ptp(xs[anchor])) >= 0.01:
            a, b = np.polyfit(xs[anchor], ys[anchor], 1)
            out = ys.copy()
            out[good] = ys[good] - (a * xs[good] + b)
            return out, float(a), float(b)
        # Degenerate mask: too few out-of-transit rows, or all of them at
        # the same airmass.  Fall through to the blind fit rather than
        # failing the pass outright.

    idx = np.flatnonzero(good)
    a, b = np.polyfit(xs[idx], ys[idx], 1)
    keep = idx
    for _ in range(12):
        resid = ys[idx] - (a * xs[idx] + b)
        n_keep = max(3, int(round(TRIM_KEEP_FRACTION * idx.size)))
        order = np.argsort(resid)          # brightest (most negative) first
        keep = idx[order[:n_keep]]
        if float(np.ptp(xs[keep])) < 0.01:
            break
        a_new, b_new = np.polyfit(xs[keep], ys[keep], 1)
        if abs(a_new - a) < 1e-12 and abs(b_new - b) < 1e-12:
            a, b = a_new, b_new
            break
        a, b = a_new, b_new

    # Re-admit everything close to the trimmed core so the baseline uses all
    # the genuine out-of-transit points, not just the brightest 60%.
    resid_all = ys[idx] - (a * xs[idx] + b)
    core = ys[keep] - (a * xs[keep] + b)
    sigma = _mad_std(core)
    if np.isfinite(sigma) and sigma > 0:
        wide = idx[np.abs(resid_all - float(np.median(core))) <= 2.0 * sigma]
        if wide.size >= 3 and float(np.ptp(xs[wide])) >= 0.01:
            a, b = np.polyfit(xs[wide], ys[wide], 1)

    out = ys.copy()
    out[good] = ys[good] - (a * xs[good] + b)
    return out, float(a), float(b)


def sigma_clip_series(t, y, kappa: float = CLIP_KAPPA,
                      window: int = CLIP_WINDOW):
    """``(keep_mask, n_clipped, note)`` -- drop spikes, keep the transit.

    MODEL-FREE, and that is the point.  Clipping against a fitted transit
    is circular: the fit has already been pulled by the outlier, so the
    residual that should be largest is the one that has been made smallest.
    Here the reference is a RUNNING MEDIAN over a window far shorter than
    any transit, so a smooth multi-point dip passes through untouched while
    a one-frame spike -- a satellite, a cosmic ray, a cloud edge -- stands
    out against its own neighbours.

    Why it is worth doing at all: on a 12 mmag transit measured at 4 mmag
    per point, ONE 100 mmag outlier took the significance from 12.1 to 3.2
    sigma.  A robust post-fit scatter recovers most of that (6.9), but the
    in/out contrast is still computed from means, and a mean has no
    defence.  Removing the point is the rest of the fix.

    Never clips more than ``CLIP_MAX_FRACTION`` of the run: past that the
    thing being removed is not an outlier population, and quietly deleting
    a tenth of a light curve to make it look better is the opposite of what
    this script is for.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    keep = np.isfinite(t) & np.isfinite(y)
    n = int(keep.sum())
    if n < max(8, window):
        return keep, 0, "too few points to clip"
    order = np.argsort(t)
    ys = y[order]
    half = max(1, int(window) // 2)
    # Running median with edge padding, so the first and last points are
    # judged against real neighbours rather than against nothing.
    # Reflected WITHOUT the end point itself, so the first and last points
    # are judged against neighbours only, like every interior point.
    padded = np.concatenate([ys[1:half + 1][::-1], ys, ys[-half - 1:-1][::-1]])
    # Leave-one-out: the point is judged against its neighbours, never
    # against a median it sits inside -- that shrank every residual and
    # made a nominal 4 sigma a real 3.5 (false-clip rate 4.6e-4 per
    # point instead of 6e-5).  The residual carries the neighbours'
    # median noise too, so its own robust scale is the right yardstick:
    # measured on white noise, kappa = 4 now clips 1.0e-4 of the points.
    smooth = np.array([np.median(np.concatenate(
        [padded[i:i + half], padded[i + half + 1:i + 2 * half + 1]]))
        for i in range(ys.size)])
    resid = ys - smooth
    scale = _mad_std(resid)
    if not (np.isfinite(scale) and scale > 0):
        return keep, 0, "scatter is zero; nothing to clip against"
    bad_sorted = np.abs(resid) > kappa * scale
    n_bad = int(bad_sorted.sum())
    if n_bad == 0:
        return keep, 0, ""
    if n_bad > CLIP_MAX_FRACTION * ys.size:
        return keep, 0, (f"{n_bad} point(s) exceed {kappa:g} sigma, more than "
                         f"{100 * CLIP_MAX_FRACTION:.0f}% of the run — that is "
                         "a noisy night, not an outlier population, and "
                         "nothing was removed")
    bad = np.zeros(y.size, dtype=bool)
    bad[order[bad_sorted]] = True
    keep = keep & ~bad
    return keep, n_bad, (f"{n_bad} point(s) beyond {kappa:g} x the "
                         f"point-to-point scatter removed")


def _fill_gaps(xs):
    """Linear interpolation over NaNs against index, nearest-fill at the ends.

    Leaving a NaN row out of the fit while detrending every other row puts a
    discontinuity exactly at the missing sample: its neighbours get the
    trend subtracted and it does not.  Seeing, sky and airmass all vary
    smoothly frame to frame, so interpolating lets the same trend apply
    everywhere.  A gap at the very start or end has no two bracketing
    points, so it nearest-fills rather than extrapolating a wild slope.
    """
    xs = np.asarray(xs, dtype=float).copy()
    finite = np.isfinite(xs)
    n = int(finite.sum())
    if n == 0 or n == xs.size:
        return xs
    idx = np.arange(xs.size, dtype=float)
    xs[~finite] = np.interp(idx[~finite], idx[finite], xs[finite])
    return xs


def match_frames_to_curve(jd_curve, jd_frames, tol_s: float = 5.0):
    """Index into ``jd_frames`` for every row of ``jd_curve``, or -1.

    Siril measures a SUBSET of the frames, and its light_curve.dat carries
    only a time -- no frame number.  Matching on that time is exact rather
    than approximate: Siril's JD is the mid-exposure, verified against 178
    raw headers to 0.02 s, so a tolerance of a few seconds pairs each row
    with its frame or with nothing at all.

    Matching on ORDER would be wrong: the dropped frames are scattered
    through the run, so the k-th measured row is not the k-th frame.
    """
    jc = np.asarray(jd_curve, dtype=float)
    jf = np.asarray(jd_frames, dtype=float)
    out = np.full(jc.size, -1, dtype=int)
    if jf.size == 0:
        return out
    tol = tol_s / 86400.0
    for i, j in enumerate(jc):
        if not np.isfinite(j):
            continue
        d = np.abs(jf - j)
        k = int(np.argmin(d))
        if d[k] <= tol:
            out[i] = k
    return out


# ---------------------------------------------------------------------------
# Transit fit
# ---------------------------------------------------------------------------
def header_target_radec(infos):
    """``(ra_deg, dec_deg, note)`` from OBJCTRA/OBJCTDEC, or ``(None, None, why)``.

    N.I.N.A. writes the POSITION OF THE OBJECT here, not the telescope
    pointing, and on the run this was written for all 178 lights carry it
    identically and land 5.7" x 0.2" from the archive -- under three
    pixels at 2 arcsec/px, comfortably inside Siril's own +/-19 px search
    box.  That makes the header the better source than any lookup: it is
    already on disk, it needs no network, and it cannot be wrong about
    which target this folder holds.

    Two things it must not do.

    **Only LIGHT frames.**  A flat is shot with the mount parked, and this
    rig then writes OBJCTRA '00 00 00' with RA/DEC 359.10/+89.85 -- the
    celestial pole.  Reading one flat instead of a light is exactly the
    mistake that made these fields look untrustworthy in the first place.

    **Never the RA/DEC pair.**  Those are the telescope pointing: 342.24 /
    -10.30 here, a quarter of a degree from the target, because the target
    is not the field centre.  Close enough to look right, wrong enough to
    matter.
    """
    seen = []
    bare_hours = False
    for info in infos or ():
        # Only frames KNOWN to be something else are skipped.  A flat says
        # so in IMAGETYP; a frame with no IMAGETYP at all is one the caller
        # already decided to treat as a light, and dropping it here made
        # this whole path invisible on data whose headers carry OBJECT but
        # no IMAGETYP -- which is most archive and school-telescope data.
        kind = (info.get("kind") or "").strip().lower()
        if kind and kind != KIND_LIGHT.lower():
            continue
        ra_txt = str(info.get("objctra") or "").strip()
        ra = _sexagesimal(ra_txt)
        dec = _sexagesimal(info.get("objctdec") or "")
        if not (np.isfinite(ra) and np.isfinite(dec)):
            continue
        # OBJCTRA is H M S by convention, and a sexagesimal string is
        # always hours.  A bare decimal above 24 can only be degrees
        # (some drivers write it that way); multiplying it by 15 put a
        # 339-degree target at 5087 degrees, wrapped to 47.
        if re.search(r"[\s:hm]", ra_txt) or abs(ra) <= 24.0:
            if not re.search(r"[\s:hm]", ra_txt):
                bare_hours = True
            ra *= 15.0
        if abs(ra) > 360.0:
            continue
        # '00 00 00' / '+00 00 00' is this rig's "I do not know", not a
        # position on the sky.  A real target there would be a coincidence
        # nobody has ever had.
        if abs(ra) < 1e-6 and abs(dec) < 1e-6:
            continue
        seen.append((ra, dec))
    if not seen:
        return None, None, ("no usable OBJCTRA/OBJCTDEC in the light frames")
    ras = np.asarray([v[0] for v in seen])
    decs = np.asarray([v[1] for v in seen])
    ra_m, dec_m = float(np.median(ras)), float(np.median(decs))
    hours_note = (" — OBJCTRA is a bare decimal below 24, read as HOURS by "
                  "the FITS convention; a driver writing degrees there "
                  "would be 15x off, which the archive cross-check would "
                  "show" if bare_hours else "")
    spread = float(np.max(np.hypot(
        (ras - ra_m) * np.cos(np.radians(dec_m)), decs - dec_m))) * 3600.0
    if spread > HEADER_RADEC_SPREAD_ARCSEC:
        return None, None, (
            f"OBJCTRA/OBJCTDEC disagree by {spread:.0f}\" across the lights "
            "— that is more than one target in this folder, not one "
            "position, so it is not used")
    return ra_m, dec_m, (f"{len(seen)} light frame(s) agree to "
                         f"{spread:.1f}\"" if len(seen) > 1 else
                         "one light frame") + hours_note


def angular_sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    """Separation of two sky positions, in arcseconds."""
    d = math.radians(dec1 + dec2) / 2.0
    return math.hypot((ra1 - ra2) * math.cos(d), dec1 - dec2) * 3600.0


def normalise_planet_name(raw) -> str:
    """A header's OBJECT into the form the NASA archive indexes.

    N.I.N.A. writes what you typed into the sequence, and what people type
    is ``WASP-75b``; the archive holds ``WASP-75 b``.  One missing space is
    the whole difference between a hit and a silent miss, so it is fixed
    here rather than left to the user to discover.
    """
    txt = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not txt:
        return ""
    # A trailing planet letter, glued on or separated: WASP-75b, HAT-P-32B.
    m = re.match(r"^(.*?[0-9])\s*([b-i])$", txt, re.IGNORECASE)
    if m:
        return f"{m.group(1)} {m.group(2).lower()}"
    return txt


def target_key(raw) -> str:
    """Two names into one comparable key: same star, same key.

    ``WASP-75 b``, ``WASP-75b``, ``wasp75`` and ``WASP 75`` all describe
    one target; ``HATP-32`` does not.  Separators go, case goes, and a
    trailing planet letter goes -- OBJECT usually names the HOST while
    people type the planet, and that difference is spelling, not
    disagreement.
    """
    key = re.sub(r"[-\s]", "", normalise_planet_name(raw)).upper()
    return re.sub(r"([0-9])[B-I]$", r"\1", key)


def archive_lookup(name: str, timeout: float = ARCHIVE_TIMEOUT_S,
                   opener=None):
    """Ask the NASA Exoplanet Archive about one planet.  ``(dict, note)``.

    A plain HTTPS call to the archive's TAP service, deliberately NOT via
    astroquery: astroquery is present in some Siril installs and absent in
    others, and a lookup that works on one machine and not the next is
    worse than no lookup.  Everything needed is one URL and the csv module.

    The dict carries what this script can actually use -- sky position, and
    the ephemeris the measured mid-time gets compared against.  Anything
    the archive does not have for a given planet comes back as None rather
    than as a plausible-looking zero.
    """
    planet = normalise_planet_name(name)
    if not planet:
        return None, "no target name to look up"
    cols = ("pl_name,hostname,ra,dec,pl_orbper,pl_tranmid,pl_trandur,"
            "pl_trandep,st_teff,st_logg,sy_vmag,"
            "pl_ratdor,pl_orbincl,pl_orbeccen,pl_orblper,pl_ratror")
    # Compare with hyphens and spaces stripped from BOTH sides.  People
    # type what their capture software wrote -- OBJECT read 'HATP-32' on
    # EXOTIC's own demo set -- while the archive holds 'HAT-P-32 b'.  Every
    # spelling in between then works without a table of survey prefixes.
    key = re.sub(r"[-\s]", "", planet).upper().replace("'", "''")
    strip = "REPLACE(REPLACE(UPPER({0}),'-',''),' ','')"
    # hostname as well as pl_name: a name with no planet letter -- which is
    # what a header usually carries -- exists only in the hostname column.
    query = (f"select {cols} from pscomppars where "
             f"{strip.format('pl_name')} = '{key}' or "
             f"{strip.format('hostname')} = '{key}'")
    url = (ARCHIVE_TAP + "?"
           + urllib.parse.urlencode({"query": query, "format": "csv"}))
    try:
        fetch = opener or urllib.request.urlopen
        with fetch(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception as exc:                       # noqa: BLE001
        _log_swallowed(exc)
        return None, f"the archive could not be reached ({type(exc).__name__})"
    rows = list(csv.DictReader(io.StringIO(body)))
    if not rows:
        return None, (f"the archive has no planet or host called {planet!r} "
                      "— check the spelling, or enter RA/Dec by hand")
    if len(rows) > 1:
        names = ", ".join(sorted(r.get("pl_name", "?") for r in rows))
        return None, (f"{planet!r} is a system with {len(rows)} known "
                      f"planets ({names}) — name the one you observed, "
                      "because their ephemerides differ")

    def _num(key_):
        try:
            v = float(rows[0].get(key_, "") or "nan")
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    ra, dec = _num("ra"), _num("dec")
    if ra is None or dec is None:
        return None, f"the archive knows {planet!r} but has no position for it"
    return {
        "name": rows[0].get("pl_name", planet) or planet,
        "ra_deg": ra, "dec_deg": dec,
        "period_d": _num("pl_orbper"),
        "t0_bjd": _num("pl_tranmid"),
        "duration_h": _num("pl_trandur"),
        "depth_pct": _num("pl_trandep"),
        "teff_k": _num("st_teff"),
        "logg": _num("st_logg"),
        "vmag": _num("sy_vmag"),
        # The orbit, for the HOPS-compatible mode: it locks the transit's
        # duration and shape to these instead of fitting them.
        "a_rs": _num("pl_ratdor"),
        "inc_deg": _num("pl_orbincl"),
        "ecc": _num("pl_orbeccen"),
        "peri_deg": _num("pl_orblper"),
        "rprs_archive": _num("pl_ratror"),
    }, ""


_TOI_RE = re.compile(r"^TOI[-_\s]*(\d+)(?:\.(\d{1,2}))?$", re.IGNORECASE)

# TFOPWG working-group dispositions, spelled out for the log.  FP/FA are
# the ones worth shouting about: a "transit" matching a false positive's
# ephemeris is most likely not a planet.
_TOI_DISPOSITIONS = {
    "PC": "planet candidate", "CP": "confirmed planet",
    "KP": "known planet", "APC": "ambiguous planet candidate",
    "FP": "FALSE POSITIVE", "FA": "false alarm",
}


def looks_like_toi(name) -> bool:
    """True when a name is a TESS Object of Interest designation."""
    return bool(_TOI_RE.match(str(name or "").replace(" ", "")))


def toi_lookup(name: str, timeout: float = ARCHIVE_TIMEOUT_S,
               opener=None):
    """The TESS candidate list, for names the planet tables cannot know.

    ``TOI-3540.01`` is a CANDIDATE designation.  The archive's confirmed-
    planet tables index final names ("TOI-3540 b" once confirmed), so a
    follow-up run on a candidate used to lose its whole ephemeris —
    expected model, O−C, transit window — to a spelling nobody got wrong.
    The archive publishes the ``toi`` table for exactly these; its depth
    arrives in ppm and its duration in hours, converted here to the units
    the rest of this script speaks.

    Returns ``(dict, note)`` shaped like `archive_lookup`, plus a
    ``disposition`` field (TFOPWG: PC/CP/KP/APC/FP/FA) the caller is
    expected to SAY — an ephemeris for a false positive deserves a
    warning, not a quiet green line.
    """
    m = _TOI_RE.match(str(normalise_planet_name(name)).replace(" ", ""))
    if not m:
        return None, "not a TOI designation"
    base = int(m.group(1))
    cols = ("toi,tfopwg_disp,ra,dec,pl_orbper,pl_tranmid,pl_trandurh,"
            "pl_trandep,st_teff,st_logg,st_tmag")
    # The toi column is numeric, so the WHERE clause is built from parsed
    # integers only — nothing user-typed reaches the query as text.
    if m.group(2):
        where = f"toi = {base}.{int(m.group(2)):02d}"
    else:
        # A bare "TOI-3540" means any candidate of that star.
        where = f"toi >= {base}.01 and toi < {base + 1}"
    query = f"select {cols} from toi where {where}"
    url = (ARCHIVE_TAP + "?"
           + urllib.parse.urlencode({"query": query, "format": "csv"}))
    try:
        fetch = opener or urllib.request.urlopen
        with fetch(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception as exc:                       # noqa: BLE001
        _log_swallowed(exc)
        return None, f"the TOI list could not be reached ({type(exc).__name__})"
    rows = list(csv.DictReader(io.StringIO(body)))
    if not rows:
        return None, f"the TOI list has no candidate called {name!r} either"
    if len(rows) > 1:
        tois = ", ".join(sorted("TOI-" + str(r.get("toi", "?"))
                                for r in rows))
        return None, (f"TOI-{base} has {len(rows)} candidates ({tois}) — "
                      "name the one you observed, because their "
                      "ephemerides differ")

    def _num(key_):
        try:
            v = float(rows[0].get(key_, "") or "nan")
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    ra, dec = _num("ra"), _num("dec")
    if ra is None or dec is None:
        return None, ("the TOI list knows this candidate but has no "
                      "position for it")
    depth_ppm = _num("pl_trandep")
    return {
        "name": "TOI-" + str(rows[0].get("toi", "") or base),
        "ra_deg": ra, "dec_deg": dec,
        "period_d": _num("pl_orbper"),
        "t0_bjd": _num("pl_tranmid"),
        "duration_h": _num("pl_trandurh"),      # already hours
        "depth_pct": (depth_ppm / 1e4 if depth_ppm is not None else None),
        "teff_k": _num("st_teff"),
        "logg": _num("st_logg"),
        "vmag": _num("st_tmag"),                # TESS mag, display only
        "disposition": str(rows[0].get("tfopwg_disp", "") or "").strip(),
    }, ""


def o_minus_c(measured_bjd: float, t0_bjd: float, period_d: float):
    """``(minutes, epoch)`` -- how late the measured mid-transit ran.

    The number ExoClock and ETD exist to collect.  A light curve on its own
    says a transit happened; O-C says the ephemeris is drifting, and that
    is what accumulates into a detection of anything interesting.

    The epoch is ROUNDED to the nearest integer, which is only meaningful
    while the ephemeris is good enough to predict which transit this was.
    Over thousands of epochs a stale period eventually mislabels one, and
    then O-C jumps by a whole period -- so the caller is given the epoch
    and the drift together, never the drift alone.
    """
    if not (period_d and math.isfinite(period_d) and period_d > 0):
        return None, None
    if not all(math.isfinite(v) for v in (measured_bjd, t0_bjd)):
        return None, None
    epoch = int(round((measured_bjd - t0_bjd) / period_d))
    predicted = t0_bjd + epoch * period_d
    return (measured_bjd - predicted) * 1440.0, epoch


def ld_template(rp: float, b: float = 0.0, u1: float = LD_U1,
                u2: float = LD_U2, n_phase: int = LD_PHASE_STEPS,
                n_rad: int = LD_RADIAL_STEPS):
    """A limb-darkened transit shape on a NORMALISED phase axis.

    Returns ``(phase, shape)`` with phase running -0.5 to +0.5 across the
    full first-to-fourth-contact duration and shape 0 outside, 1 at the
    deepest point.  Because the axis is normalised, the SAME template
    serves every T0 and every duration -- which is what makes this
    affordable: built once per (rp, b), then interpolated at each grid
    node for about the cost of the trapezoid it replaces.  Recomputing the
    occultation per node would take 15 s per fit.

    Why bother at all: a trapezoid fitted to a limb-darkened transit comes
    out 5-6% too SHALLOW, systematically, across rp/Rs 0.08 to 0.15 -- and
    chi2/nu stays at 1.0, so the misfit is invisible at amateur precision.
    A single template at rp 0.10 brings that to +0.6/-0.0/-1.5%.

    The occultation is integrated radially rather than over the disc:
    at radius r the planet covers an arc whose half-angle follows from the
    law of cosines, so the blocked flux is a ONE-dimensional integral over
    r.  That needs no elliptic integrals and therefore no scipy, and it is
    verified against an independent two-dimensional integration.

    ``u1``/``u2`` are the quadratic limb-darkening coefficients.  They are
    a property of the STAR and the FILTER, not of this code, and the depth
    depends on them -- which is why they are settable and why the report
    names the pair it used.
    """
    rp = max(1e-4, float(rp))
    b = abs(float(b))
    x_max2 = (1.0 + rp) ** 2 - b * b
    if x_max2 <= 0:
        # The planet never reaches the disc at this impact parameter.
        ph = np.linspace(-0.5, 0.5, n_phase)
        return ph, np.zeros_like(ph)
    x_max = math.sqrt(x_max2)

    # Stellar surface brightness, quadratic law, and the total flux it
    # integrates to -- both on the same radial grid, so the normalisation
    # is exact for this quadrature rather than analytic-in-principle.
    edges = np.linspace(0.0, 1.0, n_rad + 1)
    r = 0.5 * (edges[:-1] + edges[1:])
    dr = edges[1] - edges[0]
    mu = np.sqrt(np.clip(1.0 - r * r, 0.0, None))
    intensity = 1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) ** 2
    ring = intensity * 2.0 * np.pi * r * dr
    total = float(ring.sum())

    phase = np.linspace(-0.5, 0.5, n_phase)
    x = phase * 2.0 * x_max
    z = np.sqrt(x * x + b * b)                       # planet centre distance
    blocked = np.zeros(phase.size)
    # Half-angle of the covered arc at radius r, vectorised over phase.
    zz = z[:, None]
    rr = r[None, :]
    lo = np.abs(zz - rp)
    hi = zz + rp
    inside = rr <= lo                               # ring fully covered
    partial = (rr > lo) & (rr < hi)
    cosang = np.ones_like(rr * zz)
    with np.errstate(invalid="ignore", divide="ignore"):
        cosang = (rr * rr + zz * zz - rp * rp) / (2.0 * rr * zz)
    frac = np.zeros_like(cosang)
    frac[partial] = np.arccos(np.clip(cosang[partial], -1.0, 1.0)) / np.pi
    frac[inside & (zz < rp)] = 1.0                  # ring inside the planet
    blocked = (frac * ring[None, :]).sum(axis=1)
    shape = blocked / total
    peak = float(shape.max())
    if peak <= 0:
        return phase, np.zeros_like(phase)
    return phase, shape / peak


def ld_central_depth(rp: float, b: float = 0.0, u1: float = LD_U1,
                     u2: float = LD_U2, n_rad: int = LD_RADIAL_STEPS):
    """Blocked flux fraction at the DEEPEST point, for a given rp/Rs.

    The same radial integral as ``ld_template``, evaluated only at the
    planet-centre distance z = b.  This is the bridge between the two
    depth conventions: the template fit measures the limb-darkened
    CENTRAL depth, while EXOTIC, HOPS and AstroImageJ all quote
    (Rp/Rs)^2 -- and with quadratic limb darkening the central depth is
    deeper by the ratio of central to mean surface brightness (~1.2 for
    a solar-type star in V).  Verified: with u1 = u2 = 0 this returns
    exactly rp^2 for a central transit.
    """
    rp = float(rp)
    z = abs(float(b))
    if rp <= 0.0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_rad + 1)
    r = 0.5 * (edges[:-1] + edges[1:])
    dr = edges[1] - edges[0]
    mu = np.sqrt(np.clip(1.0 - r * r, 0.0, None))
    intensity = 1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) ** 2
    ring = intensity * 2.0 * np.pi * r * dr
    total = float(ring.sum())
    lo = abs(z - rp)
    hi = z + rp
    frac = np.zeros_like(r)
    if z < 1e-12:
        # Linear ramp across the ring that straddles rp — an all-or-
        # nothing ring makes this function STEPWISE in rp (plateau width
        # = one ring), and the bisection in rprs_from_depth then lands
        # anywhere on the plateau: measured 0.14875 for a true 0.15.
        frac = np.clip((rp - (r - 0.5 * dr)) / dr, 0.0, 1.0)
    else:
        inside = r <= lo
        partial = (r > lo) & (r < hi)
        with np.errstate(invalid="ignore", divide="ignore"):
            cosang = (r * r + z * z - rp * rp) / (2.0 * r * z)
        frac[partial] = np.arccos(np.clip(cosang[partial], -1.0, 1.0)) / np.pi
        frac[inside & (z < rp)] = 1.0
    return float((frac * ring).sum() / total)


def rprs_from_depth(depth_flux: float, b: float = 0.0, u1: float = LD_U1,
                    u2: float = LD_U2):
    """The measured central FLUX depth back into Rp/Rs, or None.

    Bisection on ``ld_central_depth`` -- monotonic in rp.  This is what
    lets the report quote the SAME number EXOTIC, HOPS and AstroImageJ
    quote ((Rp/Rs)^2), instead of a central depth ~20% deeper that reads
    as a disagreement when it is only a convention.
    """
    try:
        d = float(depth_flux)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(d) or d <= 0.0:
        return None
    lo, hi = 1e-4, 0.999
    if d >= ld_central_depth(hi, b, u1, u2):
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if ld_central_depth(mid, b, u1, u2) < d:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ld_shape(t, t0: float, duration: float, template):
    """A template evaluated at real times.  Same contract as the trapezoid.

    Zero outside the event, 1 at the deepest point, and linear in depth --
    which is the whole reason for the template form.  A physically free
    rp/Rs would make depth and shape vary together, the closed-form solve
    would be gone, and with it the determinism and the no-optimiser
    guarantee this fit is built on.
    """
    phase, shape = template
    if duration <= 0:
        return np.zeros_like(np.asarray(t, dtype=float))
    ph = (np.asarray(t, dtype=float) - t0) / duration
    return np.interp(ph, phase, shape, left=0.0, right=0.0)


# -- HOPS-compatible mode ---------------------------------------------
# The blind-detection fit above answers "is there a transit?"; HOPS
# (ExoWorldsSpies) answers "given the catalogue's planet, how deep and
# when?".  This mode reproduces HOPS's MODEL and CONVENTIONS on this
# script's photometry: the planet's orbit from the archive (P, a/R*, i,
# e, omega), so the duration is physics rather than a free parameter; a
# Claret four-coefficient limb-darkening law; a multiplicative flux
# model n * (1 + c*x) * transit(t); HOPS's iterative 3-sigma outlier
# filter and its rescaling of the error bars to chi2/nu = 1; and
# posteriors from an affine-invariant ensemble sampler (Goodman & Weare
# 2010 -- the algorithm emcee implements), summarised at the 16/50/84
# percentiles exactly as pylightcurve does.  The orbit and the
# occultation are verified against pylightcurve 4.1's own functions
# (see the test suite); the sampler is seeded, so unlike HOPS a rerun
# reproduces its numbers.

HOPS_SUB_EXPOSURE_S = 10.0     # HOPS averages its model over the exposure in steps this long
# Bump when the archive lookup learns new columns: a cached ephemeris
# from an older schema is refreshed instead of quietly lacking them.
TARGET_CACHE_SCHEMA = 2

# HOPS's own filter table: what people call a filter -> the passband name
# pylightcurve/ExoTETHyS know it by.  Same spellings HOPS accepts.
HOPS_FILTERS = {
    "clear": "clear", "none": "clear",
    "luminance": "luminance", "lum": "luminance", "l": "luminance",
    "u": "JOHNSON_U", "uj": "JOHNSON_U", "b": "JOHNSON_B", "bj": "JOHNSON_B",
    "v": "JOHNSON_V", "vj": "JOHNSON_V", "r": "COUSINS_R", "rc": "COUSINS_R",
    "i": "COUSINS_I", "ic": "COUSINS_I", "h": "2mass_h", "j": "2mass_j",
    "k": "2mass_ks", "ks": "2mass_ks",
    "exoplanets_bb": "exoplanets_bb", "exoplanets": "exoplanets_bb",
    "astrodon exoplanet-bb": "exoplanets_bb",
    # the same two as _filter_key writes them (- and _ become spaces)
    "astrodon exoplanet bb": "exoplanets_bb", "exoplanets bb": "exoplanets_bb",
    "up": "sdss_u", "u'": "sdss_u", "gp": "sdss_g", "g'": "sdss_g",
    "rp": "sdss_r", "r'": "sdss_r", "ip": "sdss_i", "i'": "sdss_i",
    "zp": "sdss_z", "z'": "sdss_z",
}


# What an RGB or a survey filter wheel writes into FILTER, with the
# nearest standard passband and the caveat that goes with it.  These are
# approximations and are labelled as such wherever the coefficients are
# quoted: an RGB red filter passes ~590-690 nm, Cousins R ~550-800 nm,
# and the limb darkening differs by a few percent between the two.
HOPS_FILTER_ALIASES = {
    "red": ("COUSINS_R", "an RGB red filter taken as Cousins R"),
    "green": ("JOHNSON_V", "an RGB green filter taken as Johnson V"),
    "blue": ("JOHNSON_B", "an RGB blue filter taken as Johnson B"),
    "g": ("JOHNSON_V", "a 'G' filter taken as Johnson V"),
    "johnson u": ("JOHNSON_U", ""), "johnson b": ("JOHNSON_B", ""),
    "johnson v": ("JOHNSON_V", ""), "cousins r": ("COUSINS_R", ""),
    "cousins i": ("COUSINS_I", ""),
    "sloan u": ("sdss_u", ""), "sloan g": ("sdss_g", ""),
    "sloan r": ("sdss_r", ""), "sloan i": ("sdss_i", ""),
    "sloan z": ("sdss_z", ""), "sdss u": ("sdss_u", ""),
    "sdss g": ("sdss_g", ""), "sdss r": ("sdss_r", ""),
    "sdss i": ("sdss_i", ""), "sdss z": ("sdss_z", ""),
    "2mass j": ("2mass_j", ""), "2mass h": ("2mass_h", ""),
    "2mass k": ("2mass_ks", ""), "2mass ks": ("2mass_ks", ""),
    "lp": ("luminance", ""), "l pro": ("luminance", ""),
    "lpro": ("luminance", ""),
    "uv/ir cut": ("luminance", ""), "uvir": ("luminance", ""),
    "no filter": ("clear", ""), "": ("clear", "no filter named — clear"),
}
# Narrowband: no limb-darkening table exists for a 7 nm line, and HOPS
# refuses them too.  Named so the dialog can say WHY, not just "unknown".
HOPS_NARROWBAND = ("ha", "h-alpha", "halpha", "h_alpha", "hα", "oiii",
                   "o-iii", "o3", "sii", "s-ii", "s2", "hb", "hbeta",
                   "h-beta", "nii", "n2")


def _filter_key(text) -> str:
    return re.sub(r"[\s_\-]+", " ", (text or "").strip().lower())


def hops_filter_name(text):
    """pylightcurve's passband name for a filter as people write it, or None.

    HOPS's own spellings first, then the RGB / survey aliases above.
    A trailing comment in brackets ("Red (Baader)") is ignored."""
    key = _filter_key(text)
    key = re.sub(r"\s*[\(\[].*$", "", key).strip()
    if key in HOPS_FILTERS:
        return HOPS_FILTERS[key]
    hit = HOPS_FILTER_ALIASES.get(key) or HOPS_FILTER_ALIASES.get(
        key.replace(" ", ""))
    return hit[0] if hit else None


def hops_filter_note(text) -> str:
    """The approximation caveat for an aliased filter name, or ''."""
    key = re.sub(r"\s*[\(\[].*$", "", _filter_key(text)).strip()
    if key in HOPS_FILTERS:
        return ""
    hit = HOPS_FILTER_ALIASES.get(key) or HOPS_FILTER_ALIASES.get(
        key.replace(" ", ""))
    return hit[1] if hit else ""


def is_narrowband_filter(text) -> bool:
    key = re.sub(r"\s*[\(\[].*$", "", _filter_key(text)).strip()
    return key.replace(" ", "") in HOPS_NARROWBAND


def hops_relative_flux(target, comps, target_err, comp_errs):
    """HOPS's light curve from per-star fluxes: the target divided by the
    RAW sum of the comparison stars, the error propagated exactly as
    HOPS's photometry step does.  NaN wherever any comp is missing -- a
    raw sum is not NaN-robust, and neither is HOPS."""
    t = np.asarray(target, dtype=float)
    te = np.asarray(target_err, dtype=float)
    if not comps:
        return np.full(t.shape, np.nan), np.full(t.shape, np.nan)
    c = np.vstack([np.asarray(x, dtype=float) for x in comps])
    ce = np.vstack([np.asarray(x, dtype=float) for x in comp_errs])
    csum = c.sum(axis=0)
    cerr = np.sqrt((ce * ce).sum(axis=0))
    with np.errstate(invalid="ignore", divide="ignore"):
        rel = t / csum
        err = np.sqrt((te / t) ** 2 + (cerr / csum) ** 2) * rel
    return rel, err


# -- Claret coefficients from Phoenix models -------------------------------
# HOPS takes its limb-darkening coefficients from ExoTETHyS (Morello et
# al. 2020; GPLv3, like this script): the specific intensities I(lambda,
# mu) of a Phoenix 2018 model atmosphere integrated over the passband,
# the quasi-spherical cut that removes the model's outer drop-off, a
# weighted fit of the four-coefficient law, interpolated between the
# star's eight nearest grid neighbours.  The functions below reproduce
# that method from the published code.  Nothing is bundled: the model
# files (21 MB each, four per star at solar metallicity) come from the
# links ExoTETHyS itself publishes and are cached under ~/.svenesis, the
# passband curves from the SVO Filter Profile Service.  Verified against
# ExoTETHyS's own output on three stars and five passbands (tests,
# changelog).
PHOENIX_INDEX_URL = ("https://raw.githubusercontent.com/ucl-exoplanets/"
                     "ExoTETHyS/master/exotethys/_0database.pickle")
PHOENIX_GRID = "Phoenix_2018"
PHOENIX_R_CUT = 0.99623           # ExoTETHyS's quasi-spherical cut in r/R
PHOENIX_WAVE_RANGE = (500.0, 25999.0)   # Angstrom, the grid's coverage
SVO_FPS_URL = "http://svo2.cab.inta-csic.es/svo/theory/fps3/fps.php?ID="
# HOPS's "clear", "luminance" and Astrodon ExoPlanet-BB passbands are
# measured curves in pylightcurve's photometry database (MIT licence),
# not on SVO.  pylightcurve publishes the database links in its own
# repository; they are followed at run time and the curve is cached
# beside the SVO ones.  Nothing is bundled.
PLC_DATABASES_URL = ("https://raw.githubusercontent.com/ucl-exoplanets/"
                     "pylightcurve/master/pylightcurve/__databases__.pickle")
PLC_PASSBANDS = {"clear": "clear", "luminance": "luminance",
                 "exoplanets_bb": "exoplanets_bb"}
# The photometry index HOPS's own pylightcurve copy (4.1) names.  Tried
# after the links in pylightcurve's repository, whose 4.0/4.1 entries
# pointed at a retired file on the day this was written (an HTML "not
# found" page comes back, not a pickle).
PLC_PHOTOMETRY_FALLBACK_URLS = [
    "https://www.dropbox.com/scl/fi/9m3aqhl9p4m3t78n4awzr/photometry_2."
    "pickle?rlkey=h4l1d904yljeb83k0n2zonuys&dl=1",
]
# pylightcurve's passband names (HOPS's vocabulary) -> SVO filter ids.
# None: HOPS ships a curve of its own that SVO does not carry.
SVO_FILTER_IDS = {
    "JOHNSON_U": "Generic/Johnson.U", "JOHNSON_B": "Generic/Johnson.B",
    "JOHNSON_V": "Generic/Johnson.V", "COUSINS_R": "Generic/Cousins.R",
    "COUSINS_I": "Generic/Cousins.I", "2mass_j": "2MASS/2MASS.J",
    "2mass_h": "2MASS/2MASS.H", "2mass_ks": "2MASS/2MASS.Ks",
    "sdss_u": "SLOAN/SDSS.u", "sdss_g": "SLOAN/SDSS.g",
    "sdss_r": "SLOAN/SDSS.r", "sdss_i": "SLOAN/SDSS.i",
    "sdss_z": "SLOAN/SDSS.z",
    "clear": None, "luminance": None, "exoplanets_bb": None,
}
# The only classes a model file or the index may contain.  A pickle from
# the network can otherwise run arbitrary code on load.
_SAFE_PICKLE_GLOBALS = {
    "numpy.core.multiarray._reconstruct", "numpy._core.multiarray._reconstruct",
    "numpy.ndarray", "numpy.dtype", "numpy.core.multiarray.scalar",
    "numpy._core.multiarray.scalar", "_codecs.encode",
    "astropy.units.quantity.Quantity", "astropy.units.core.CompositeUnit",
    "astropy.units.core.IrreducibleUnit", "astropy.units.core.PrefixUnit",
    "astropy.units.core.Unit", "astropy.units.core._recreate_irreducible_unit",
    "collections.OrderedDict",
}


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        key = module + "." + name
        if key in _SAFE_PICKLE_GLOBALS:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {key} from a pickle")


def safe_unpickle(path: str):
    with open(path, "rb") as fh:
        return _SafeUnpickler(fh).load()


class _PlainUnpickler(pickle.Unpickler):
    """Containers and scalars only -- for an index that is a dict of
    strings.  Everything else is refused before it can run."""
    _OK = {("builtins", "dict"), ("builtins", "list"), ("builtins", "str"),
           ("builtins", "int"), ("builtins", "float"), ("builtins", "bool"),
           ("builtins", "tuple"), ("collections", "OrderedDict")}

    def find_class(self, module, name):
        if (module, name) in self._OK:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name}")


def _plain_unpickle_url(url: str, timeout: float = 60.0):
    req = urllib.request.Request(url, headers={"User-Agent":
                                               "Svenesis-LightCurve"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data.startswith(b"\x80"):
        # A retired Dropbox link answers 200 with an HTML page.
        raise pickle.UnpicklingError(f"not a pickle at {url[:60]}…")
    return _PlainUnpickler(io.BytesIO(data)).load()


def pass_from_zip(zip_path: str, name: str):
    """``(wavelength_A, transmission)`` for ``photometry/<name>.pass`` in
    pylightcurve's photometry archive."""
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        entry = None
        for n in z.namelist():
            if n.lower().endswith("/" + name.lower() + ".pass") \
                    or n.lower() == name.lower() + ".pass":
                entry = n
                break
        if entry is None:
            raise KeyError(f"{name}.pass is not in the archive")
        arr = np.loadtxt(io.BytesIO(z.read(entry))).reshape(-1, 2)
    return arr[:, 0], arr[:, 1]


def plc_passband(name: str, cache_dir=None, progress=None,
                 timeout: float = 60.0):
    """pylightcurve's transmission curve for ``name`` (clear, luminance,
    exoplanets_bb), cached as plain text like the SVO ones.

    The route is the one pylightcurve itself takes: its repository's
    ``__databases__.pickle`` names the photometry index of the newest
    version, the index names a zip archive, the archive holds the .pass
    files.  Both pickles are read with a container-only unpickler."""
    say = progress or (lambda _m: None)
    path = (os.path.join(cache_dir, f"passband_plc_{name}.txt")
            if cache_dir else None)
    if path and os.path.isfile(path):
        arr = np.loadtxt(path).reshape(-1, 2)
        return arr[:, 0], arr[:, 1]
    zip_path = os.path.join(cache_dir, "plc_photometry.zip") if cache_dir \
        else None
    if not (zip_path and os.path.isfile(zip_path)):
        say("Reading pylightcurve's database index…")
        candidates = []
        try:
            db = _plain_unpickle_url(PLC_DATABASES_URL, timeout)
            versions = [k for k in db if isinstance(db.get(k), dict)
                        and db[k].get("photometry")]
            versions.sort(key=lambda k: [int(x) for x in
                                         re.findall(r"\d+", str(k))],
                          reverse=True)
            candidates = [str(db[k]["photometry"]) for k in versions]
        except (OSError, ValueError, KeyError,
                pickle.UnpicklingError) as exc:
            _log_swallowed(exc)
        candidates += [u for u in PLC_PHOTOMETRY_FALLBACK_URLS
                       if u not in candidates]
        zip_url, last = "", None
        for url in candidates:
            try:
                index = _plain_unpickle_url(url, timeout)
                zip_url = str(index.get("zipfile") or "")
                if zip_url.startswith("http"):
                    break
            except (OSError, ValueError, KeyError,
                    pickle.UnpicklingError) as exc:
                last = exc
                _log_swallowed(exc)
        if not zip_url.startswith("http"):
            raise KeyError("none of pylightcurve's photometry indexes "
                           f"could be read ({last})")
        if zip_path is None:
            import tempfile
            zip_path = os.path.join(tempfile.gettempdir(),
                                    "svenesis_plc_photometry.zip")
        say("Downloading pylightcurve's passband archive…")
        download_file(zip_url, zip_path, timeout=timeout)
        with open(zip_path, "rb") as fh:
            if fh.read(2) != b"PK":
                os.remove(zip_path)
                raise ValueError("the passband archive is not a zip file")
    w, t = pass_from_zip(zip_path, PLC_PASSBANDS.get(name, name))
    if path:
        np.savetxt(path, np.column_stack([w, t]), fmt="%.6f %.8f")
    return w, t


def ldc_cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".svenesis", "phoenix_2018")
    os.makedirs(d, exist_ok=True)
    return d


def download_file(url: str, dest: str, progress=None, timeout: float = 60.0):
    """Fetch url to dest via a .part file; progress(fraction) if the
    server says how big it is."""
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent":
                                               "Svenesis-LightCurve"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, \
            open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if progress and total:
                progress(got / total)
    os.replace(tmp, dest)


def phoenix_index(cache_dir: str) -> dict:
    """{model file name: download link} for the Phoenix 2018 grid, from
    ExoTETHyS's published index (cached)."""
    path = os.path.join(cache_dir, "exotethys_index.pickle")
    if not os.path.isfile(path):
        download_file(PHOENIX_INDEX_URL, path)
    data = safe_unpickle(path)
    grid = data.get(PHOENIX_GRID) if isinstance(data, dict) else None
    if not isinstance(grid, dict):
        raise ValueError("the ExoTETHyS index carries no Phoenix_2018 grid")
    out = {}
    for name, entry in grid.items():
        link = entry.get("link") if isinstance(entry, dict) else None
        if isinstance(name, str) and isinstance(link, str) \
                and link.startswith("https://"):
            out[name] = link
    return out


_MODEL_NAME_RE = re.compile(
    r"teff(\d+(?:\.\d+)?)_logg(-?\d+(?:\.\d+)?)_MH(-?\d+(?:\.\d+)?)")


def phoenix_grid_params(names):
    """(n, 3) array of Teff, log g, [M/H] parsed from the file names, and
    the names that parsed, in order."""
    rows, kept = [], []
    for n in names:
        m = _MODEL_NAME_RE.search(n)
        if m:
            rows.append([float(m.group(1)), float(m.group(2)),
                         float(m.group(3))])
            kept.append(n)
    return np.array(rows, dtype=float).reshape(-1, 3), kept


def phoenix_neighbours(teff: float, logg: float, mh: float, params):
    """The eight grid neighbours in ExoTETHyS's order (Teff above/below x
    log g above/below x [M/H] above/below, nearest first in Teff, then
    log g, then [M/H]), or None when the star falls outside the grid.
    Indices repeat when the star sits on a grid line."""
    out = []
    for t_sup in (True, False):
        for g_sup in (True, False):
            for m_sup in (True, False):
                dt = params[:, 0] - teff if t_sup else teff - params[:, 0]
                dg = params[:, 1] - logg if g_sup else logg - params[:, 1]
                dm = params[:, 2] - mh if m_sup else mh - params[:, 2]
                cand = np.where((dt >= 0) & (dg >= 0) & (dm >= 0))[0]
                if cand.size == 0:
                    return None
                c = cand[dt[cand] == dt[cand].min()]
                c = c[dg[c] == dg[c].min()]
                out.append(int(c[np.argmin(dm[c])]))
    return out


def parse_svo_votable(xml: str):
    """(wavelength [Angstrom], transmission) from an SVO Filter Profile
    Service VOTable."""
    rows = re.findall(r"<TR>\s*<TD>([^<]+)</TD>\s*<TD>([^<]+)</TD>\s*</TR>",
                      xml)
    if len(rows) < 3:
        raise ValueError("no transmission table in the SVO reply")
    arr = np.array([[float(a), float(b)] for a, b in rows], dtype=float)
    if np.any(arr[:, 1] < 0) or np.any(np.diff(arr[:, 0]) <= 0):
        raise ValueError("the SVO transmission table is not a rising "
                         "wavelength grid with non-negative values")
    return arr[:, 0], arr[:, 1]


def svo_passband(svo_id: str, cache_dir=None, timeout: float = 60.0):
    """A filter's transmission curve from SVO, cached as plain text."""
    path = (os.path.join(cache_dir, "passband_" + svo_id.replace("/", "_")
                         + ".txt") if cache_dir else None)
    if path and os.path.isfile(path):
        arr = np.loadtxt(path).reshape(-1, 2)
        return arr[:, 0], arr[:, 1]
    url = SVO_FPS_URL + urllib.parse.quote(svo_id, safe="/.")
    req = urllib.request.Request(url, headers={"User-Agent":
                                               "Svenesis-LightCurve"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        xml = resp.read().decode("utf-8", "replace")
    w, t = parse_svo_votable(xml)
    if path:
        np.savetxt(path, np.column_stack([w, t]), fmt="%.6f %.8f")
    return w, t


def passband_integrated_intensities(model_w, model_i, pb_w, pb_t):
    """I(mu) integrated over the passband, normalised at disc centre.

    ExoTETHyS interpolates model and passband linearly onto a grid of
    resolving power 1e6 and applies Simpson's rule; the product of two
    linear interpolants times lambda (photon counting) is a cubic on
    every segment between grid points, so three-point Simpson on the
    union of the two grids integrates the SAME function exactly, with
    no 400 000-point arrays.
    """
    model_w = np.asarray(model_w, dtype=float)
    model_i = np.asarray(model_i, dtype=float)
    pb_w = np.asarray(pb_w, dtype=float)
    pb_t = np.asarray(pb_t, dtype=float)
    lo, hi = float(pb_w.min()), float(pb_w.max())
    inner = model_w[(model_w > lo) & (model_w < hi)]
    nodes = np.union1d(np.union1d(inner, pb_w), np.array([lo, hi]))
    mids = 0.5 * (nodes[:-1] + nodes[1:])
    pts = np.concatenate([nodes, mids])
    idx = np.clip(np.searchsorted(model_w, pts), 1, model_w.size - 1)
    w0, w1 = model_w[idx - 1], model_w[idx]
    frac = ((pts - w0) / (w1 - w0))[:, None]
    ints = model_i[idx - 1] * (1.0 - frac) + model_i[idx] * frac
    f = ints * (np.interp(pts, pb_w, pb_t) * pts)[:, None]
    n = nodes.size
    fa, fb, fm = f[:n - 1], f[1:n], f[n:]
    integ = ((nodes[1:] - nodes[:-1])[:, None] / 6.0
             * (fa + 4.0 * fm + fb)).sum(axis=0)
    return integ


def phoenix_rescale_weights(mu, ints, r_cut: float = PHOENIX_R_CUT):
    """ExoTETHyS's treatment of a spherical Phoenix model: find the
    intensity drop-off at the limb, rescale radii to it, keep r <= r_cut,
    and weight each mu by its share of the radius axis."""
    mu = np.asarray(mu, dtype=float)
    ints = np.asarray(ints, dtype=float)
    radi = np.sqrt(1.0 - mu * mu)
    dint_dr = np.abs((ints[1:] - ints[:-1]) / (radi[1:] - radi[:-1]))
    k = int(np.argmax(dint_dr))
    rmax = 0.5 * (radi[k + 1] + radi[k])
    keep = radi <= rmax
    r = radi[keep] / rmax
    i = ints[keep]
    qs = r <= r_cut
    r, i = r[qs], i[qs]
    w = np.zeros_like(r)
    w[1:-1] = -0.5 * (r[2:] - r[:-2])
    w[0] = (1.0 - r[0]) - 0.5 * (r[1] - r[0])
    w[-1] = 0.5 * r[-2]
    return np.sqrt(1.0 - r * r), i, w


def claret4_ok(c) -> bool:
    """ExoTETHyS's admissibility: intensity positive at the limb and
    monotonically decreasing towards it."""
    c1, c2, c3, c4 = [float(x) for x in c]
    return (np.all(np.isfinite(c)) and c1 + c2 + c3 + c4 <= 1.0
            and c1 >= 0.0 and c1 + 2 * c2 + 3 * c3 + 4 * c4 >= 0.0)


def claret4_wrms(c, mu, ints, w) -> float:
    if not claret4_ok(c):
        return float("inf")
    model = ld_intensity(mu, "claret", c)
    return float(np.sum(w * (ints - model) ** 2) / np.sum(w))


def nelder_mead(f, x0, xatol=1e-8, fatol=1e-4, maxfev=10000):
    """Nelder-Mead as scipy runs it (simplex from 5 % steps, standard
    coefficients, both tolerances required) -- the optimiser ExoTETHyS
    fits with, kept for the rare case the closed form lands outside the
    admissible region."""
    x0 = np.asarray(x0, dtype=float)
    n = x0.size
    sim = np.empty((n + 1, n))
    sim[0] = x0
    for k in range(n):
        y = x0.copy()
        y[k] = y[k] * 1.05 if y[k] != 0 else 0.00025
        sim[k + 1] = y
    fsim = np.array([f(x) for x in sim])
    nfev = n + 1
    while nfev < maxfev:
        order = np.argsort(fsim)
        sim, fsim = sim[order], fsim[order]
        if (np.max(np.abs(sim[1:] - sim[0])) <= xatol
                and np.max(np.abs(fsim[0] - fsim[1:])) <= fatol):
            break
        xbar = sim[:-1].mean(axis=0)
        xr = 2.0 * xbar - sim[-1]
        fr = f(xr)
        nfev += 1
        if fr < fsim[0]:
            xe = 3.0 * xbar - 2.0 * sim[-1]
            fe = f(xe)
            nfev += 1
            if fe < fr:
                sim[-1], fsim[-1] = xe, fe
            else:
                sim[-1], fsim[-1] = xr, fr
        elif fr < fsim[-2]:
            sim[-1], fsim[-1] = xr, fr
        else:
            if fr < fsim[-1]:
                xc = 1.5 * xbar - 0.5 * sim[-1]
                fc = f(xc)
                nfev += 1
                if fc <= fr:
                    sim[-1], fsim[-1] = xc, fc
                    continue
            else:
                xcc = 0.5 * xbar + 0.5 * sim[-1]
                fcc = f(xcc)
                nfev += 1
                if fcc < fsim[-1]:
                    sim[-1], fsim[-1] = xcc, fcc
                    continue
            for k in range(1, n + 1):
                sim[k] = sim[0] + 0.5 * (sim[k] - sim[0])
                fsim[k] = f(sim[k])
                nfev += 1
    k = int(np.argmin(fsim))
    return sim[k], float(fsim[k])


def claret4_fit(mu, ints, w):
    """Weighted least-squares Claret-4 coefficients, the exact minimum of
    the objective ExoTETHyS minimises numerically; Nelder-Mead from its
    starting point only if the closed form violates its constraints.
    Returns (coefficients, weighted rms residual)."""
    mu = np.asarray(mu, dtype=float)
    ints = np.asarray(ints, dtype=float)
    w = np.asarray(w, dtype=float)
    basis = np.column_stack([1.0 - mu ** 0.5, 1.0 - mu, 1.0 - mu ** 1.5,
                             1.0 - mu ** 2])
    sw = np.sqrt(w)
    c, *_ = np.linalg.lstsq(basis * sw[:, None], (1.0 - ints) * sw,
                            rcond=None)
    if not claret4_ok(c):
        c, _v = nelder_mead(lambda x: claret4_wrms(x, mu, ints, w),
                            np.array([0.9, -0.5, 0.9, -0.5]))
    return [float(x) for x in c], math.sqrt(claret4_wrms(c, mu, ints, w))


def interp_ldc8(teff, logg, mh, neigh_params, coeffs, wres):
    """ExoTETHyS's trilinear interpolation between the eight neighbours:
    first in [M/H] (pairs 0-1, 2-3, 4-5, 6-7), then log g, then Teff."""
    def _lerp(x, x_hi, x_lo, a_hi, a_lo):
        w2, w1 = x_hi - x, x - x_lo
        if w1 + w2 == 0:
            return a_hi
        return (w1 * a_hi + w2 * a_lo) / (w1 + w2)
    P = np.asarray(neigh_params, dtype=float)
    C = np.asarray(coeffs, dtype=float)
    W = np.asarray(wres, dtype=float)
    c_g, w_g, p_g = [], [], []
    for i in (0, 2, 4, 6):
        c_g.append(_lerp(mh, P[i, 2], P[i + 1, 2], C[i], C[i + 1]))
        w_g.append(_lerp(mh, P[i, 2], P[i + 1, 2], W[i], W[i + 1]))
        p_g.append(_lerp(mh, P[i, 2], P[i + 1, 2], P[i], P[i + 1]))
    c_t, w_t, p_t = [], [], []
    for i in (0, 2):
        c_t.append(_lerp(logg, p_g[i][1], p_g[i + 1][1], c_g[i], c_g[i + 1]))
        w_t.append(_lerp(logg, p_g[i][1], p_g[i + 1][1], w_g[i], w_g[i + 1]))
        p_t.append(_lerp(logg, p_g[i][1], p_g[i + 1][1], p_g[i], p_g[i + 1]))
    c = _lerp(teff, p_t[0][0], p_t[1][0], c_t[0], c_t[1])
    w = _lerp(teff, p_t[0][0], p_t[1][0], w_t[0], w_t[1])
    return [float(x) for x in np.atleast_1d(c)], float(w)


def load_phoenix_model(path: str):
    """(wavelengths [Angstrom], mu, intensities[wave, mu]) from a cached
    ExoTETHyS model file."""
    d = safe_unpickle(path)
    w = d["wavelengths"]
    i = d["intensities"]
    w = np.asarray(getattr(w, "value", w), dtype=float)
    i = np.asarray(getattr(i, "value", i), dtype=float)
    return w, np.asarray(d["mu"], dtype=float), i


def claret_from_phoenix(teff: float, logg: float, filter_key: str,
                        mh: float = 0.0, cache_dir=None, progress=None):
    """Claret coefficients the way HOPS gets them, computed here.

    Returns ``(coefficients, note)`` or ``(None, reason)``.  progress(str)
    receives one line per step for a status bar."""
    say = progress or (lambda _m: None)
    svo_id = SVO_FILTER_IDS.get(filter_key)
    plc_name = PLC_PASSBANDS.get(filter_key) if not svo_id else None
    if not svo_id and not plc_name:
        return None, (f"no public transmission curve for the {filter_key} "
                      "passband — enter the coefficients by hand")
    cache_dir = cache_dir or ldc_cache_dir()
    try:
        say("Fetching ExoTETHyS's model index…")
        index = phoenix_index(cache_dir)
        params, names = phoenix_grid_params(list(index.keys()))
        neigh = phoenix_neighbours(float(teff), float(logg), float(mh),
                                   params)
        if neigh is None:
            return None, (f"Teff {teff:g} K / log g {logg:g} lies outside "
                          f"the Phoenix 2018 grid ({params[:, 0].min():g}–"
                          f"{params[:, 0].max():g} K, log g "
                          f"{params[:, 1].min():g}–{params[:, 1].max():g})")
        pb_src = "SVO"
        if svo_id:
            say(f"Fetching the {svo_id} passband from SVO…")
            pb_w, pb_t = svo_passband(svo_id, cache_dir)
        else:
            say(f"Fetching HOPS's {plc_name} passband from pylightcurve's "
                "photometry database…")
            pb_w, pb_t = plc_passband(plc_name, cache_dir, progress)
            svo_id = f"HOPS's {plc_name}"
            pb_src = "pylightcurve's photometry database"
        if pb_w.min() < PHOENIX_WAVE_RANGE[0] or \
                pb_w.max() > PHOENIX_WAVE_RANGE[1]:
            return None, (f"the {svo_id} passband exceeds the Phoenix grid's "
                          "wavelength coverage")
        nfits = {}
        uniq = sorted(set(neigh))
        for k, i in enumerate(uniq):
            name = names[i]
            path = os.path.join(cache_dir, name)
            if not os.path.isfile(path):
                say(f"Downloading model {k + 1}/{len(uniq)} ({name}, "
                    "21 MB)…")
                download_file(index[name], path)
            say(f"Integrating model {k + 1}/{len(uniq)} ({name})…")
            w, mu, ints = load_phoenix_model(path)
            integ = passband_integrated_intensities(w, ints, pb_w, pb_t)
            integ = integ / integ[int(np.argmax(mu))]
            rmu, rints, rw = phoenix_rescale_weights(mu, integ)
            nfits[i] = claret4_fit(rmu, rints, rw)
        coeffs, wres = interp_ldc8(
            float(teff), float(logg), float(mh), [params[i] for i in neigh],
            [nfits[i][0] for i in neigh], [nfits[i][1] for i in neigh])
    except (OSError, ValueError, KeyError, TypeError, IndexError,
            pickle.UnpicklingError, http.client.HTTPException) as exc:
        return None, f"Phoenix coefficients could not be computed: {exc}"
    note = (f"ExoTETHyS method on Phoenix_2018 ({len(uniq)} neighbour "
            f"model(s), Teff {teff:g} K, log g {logg:g}, [M/H] {mh:g}), "
            f"{svo_id} passband from {pb_src}; weighted rms {wres:.1e}")
    return coeffs, note


def ld_intensity(mu, law: str, coeffs):
    """Surface brightness at mu = cos(theta), normalised to 1 at centre."""
    mu = np.asarray(mu, dtype=float)
    if law == "claret":
        a1, a2, a3, a4 = [float(c) for c in list(coeffs)[:4]]
        return (1.0 - a1 * (1.0 - mu ** 0.5) - a2 * (1.0 - mu)
                - a3 * (1.0 - mu ** 1.5) - a4 * (1.0 - mu ** 2))
    u1, u2 = float(coeffs[0]), float(coeffs[1])
    return 1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) ** 2


def quad_to_claret(u1: float, u2: float):
    """The quadratic law written as a Claret four-coefficient law.

    (1 - mu)^2 = 1 - 2 mu + mu^2, so u1 (1-mu) + u2 (1-mu)^2 equals
    (u1 + 2 u2)(1 - mu) - u2 (1 - mu^2): a2 = u1 + 2 u2, a4 = -u2,
    a1 = a3 = 0.  Exact, so HOPS mode with no coefficients entered uses
    precisely the star the blind fit assumed.
    """
    return [0.0, float(u1) + 2.0 * float(u2), 0.0, -float(u2)]


def parse_claret_ldc(text: str):
    """Four Claret coefficients from a text field, or None.

    Accepts commas, semicolons or whitespace between the numbers.  Blank
    means "not given" (the caller falls back to the quadratic defaults);
    anything else that is not exactly four finite numbers is None too, so
    a typo cannot silently become a different star.
    """
    parts = [p for p in re.split(r"[,;\s]+", (text or "").strip()) if p]
    if len(parts) != 4:
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    return vals if all(math.isfinite(v) for v in vals) else None


def _lens_area(R, rp: float, z):
    """Area of the overlap of a disc of radius rp centred at distance z
    with a concentric-to-the-star disc of radius R (broadcasts)."""
    R = np.asarray(R, dtype=float)
    z = np.asarray(z, dtype=float)
    R, z = np.broadcast_arrays(R, z)
    out = np.zeros(R.shape)
    full = z <= np.abs(R - rp)
    out[full] = np.pi * np.minimum(R[full], rp) ** 2
    mid = ~full & (z < R + rp)
    if np.any(mid):
        Rm, zm = R[mid], z[mid]
        c1 = np.clip((zm * zm + rp * rp - Rm * Rm) / (2.0 * zm * rp), -1, 1)
        c2 = np.clip((zm * zm + Rm * Rm - rp * rp) / (2.0 * zm * Rm), -1, 1)
        k = np.clip((-zm + rp + Rm) * (zm + rp - Rm) * (zm - rp + Rm)
                    * (zm + rp + Rm), 0.0, None)
        out[mid] = (rp * rp * np.arccos(c1) + Rm * Rm * np.arccos(c2)
                    - 0.5 * np.sqrt(k))
    return out


# Gauss-Legendre nodes for the one remaining numerical integral of the
# analytic occultation (30 nodes: pylightcurve's "precision 3").
_GL_NODES, _GL_WEIGHTS = np.polynomial.legendre.leggauss(30)


def claret_coefficients(law: str, coeffs):
    """Any supported limb-darkening law written as Claret's four
    coefficients: exact for the quadratic and linear laws (see
    ``quad_to_claret``), so one occultation routine serves all."""
    if law == "claret":
        return [float(c) for c in list(coeffs)[:4]]
    if law == "linear":
        return [0.0, float(coeffs[0]), 0.0, 0.0]
    return quad_to_claret(coeffs[0], coeffs[1])


def _claret_primitive(a, r):
    """Primitive of I(r) r dr for the Claret law, up to the constant.
    With mu = sqrt(1 - r^2): each term integrates to a power of mu."""
    a1, a2, a3, a4 = a
    mu44 = 1.0 - r * r
    mu24 = np.sqrt(mu44)
    mu14 = np.sqrt(mu24)
    return (-(2.0 * (1.0 - a1 - a2 - a3 - a4) / 4.0) * mu44
            - (2.0 * a1 / 5.0) * mu44 * mu14
            - (2.0 * a2 / 6.0) * mu44 * mu24
            - (2.0 * a3 / 7.0) * mu44 * mu24 * mu14
            - (2.0 * a4 / 8.0) * mu44 * mu44)


def _claret_arc_integrand(r, a, rp, z):
    """I(r) r times the half-angle of the arc of radius r that lies
    inside the planet's disc: the part of the occulted area that has
    no closed form and is integrated numerically."""
    a1, a2, a3, a4 = a
    rsq = r * r
    mu44 = 1.0 - rsq
    mu24 = np.sqrt(mu44)
    mu14 = np.sqrt(mu24)
    inten = ((1.0 - a1 - a2 - a3 - a4) + a1 * mu14 + a2 * mu24
             + a3 * mu24 * mu14 + a4 * mu44)
    return inten * r * np.arccos(np.minimum(
        (-rp * rp + z * z + rsq) / (2.0 * z * r), 1.0))


def _claret_arc_integral(a, rp, z, r1, r2):
    half = (r2 - r1) / 2.0
    mid = (r2 + r1) / 2.0
    r = half[None, :] * _GL_NODES[:, None] + mid[None, :]
    return half * np.sum(_GL_WEIGHTS[:, None]
                         * _claret_arc_integrand(r, a, rp, z), axis=0)


def _sector_integral(a, radius, w1, w2):
    """Flux inside a circle of the given radius over a sector of angle
    |w2 - w1|."""
    return (_claret_primitive(a, radius) - _claret_primitive(a, 0.0)) \
        * np.abs(w2 - w1)


def _lune_integral(a, rp, z, ww1, ww2, sign):
    """Flux over the region between the planet's near (sign -1) or far
    (sign +1) edge and the star's centre, for angles ww1..ww2."""
    if len(z) == 0:
        return z
    rr1 = z * np.cos(ww1) + sign * np.sqrt(np.maximum(
        rp * rp - (z * np.sin(ww1)) ** 2, 0.0))
    rr2 = z * np.cos(ww2) + sign * np.sqrt(np.maximum(
        rp * rp - (z * np.sin(ww2)) ** 2, 0.0))
    rr1 = np.clip(rr1, 0.0, 1.0)
    rr2 = np.clip(rr2, 0.0, 1.0)
    w1, w2 = np.minimum(ww1, ww2), np.maximum(ww1, ww2)
    r1, r2 = np.minimum(rr1, rr2), np.maximum(rr1, rr2)
    parta = _claret_primitive(a, 0.0) * (w1 - w2)
    partd = _claret_arc_integral(a, rp, z, r1, r2)
    if sign > 0:
        return (parta + _claret_primitive(a, r1) * w2
                - _claret_primitive(a, r2) * w1 + partd)
    return (parta - _claret_primitive(a, r1) * w1
            + _claret_primitive(a, r2) * w2 - partd)


def occulted_fraction(z, rp: float, law: str = "quad",
                      coeffs=(LD_U1, LD_U2), n_rad: int = LD_RADIAL_STEPS):
    """Fraction of the stellar flux blocked at planet-centre distances z.

    Analytic: the occulted area is split by the planet's edge into a
    sector of the star and lunes whose radial integrals have closed
    forms for the Claret law; only the arc-angle term is quadrature
    (30-node Gauss-Legendre).  This is the formulation pylightcurve (MIT licence) uses, written here from reading it, and
    it reproduces ``occulted_fraction_rings`` to 3e-6 at a quarter of
    the cost -- the HOPS-mode sampler spends its time here.  ``n_rad``
    is accepted for the callers that pass it and ignored.
    """
    z = np.abs(np.asarray(z, dtype=float)).ravel()
    rp = float(rp)
    if rp <= 0.0 or z.size == 0:
        return np.zeros(z.shape)
    a = claret_coefficients(law, coeffs)
    z = np.maximum(z, 1e-10)
    if rp > 1.0:
        # A planet larger than the star (the HOPS prior allows up to
        # ten times the archive's Rp/R*) covers it whole out to
        # z = rp - 1; the case split below has no row for that
        # boundary and returns zero there.
        full = z <= rp - 1.0 + 1e-12      # rp - 1 rounds below z = rp - 1
        rest = np.zeros(z.shape)
        if np.any(~full):
            rest[~full] = _occulted_partial(z[~full], rp, a)
        rest[full] = 1.0
        return rest
    return _occulted_partial(z, rp, a)


def _occulted_partial(z, rp: float, a):
    """The case split of the analytic occultation for z > rp - 1."""
    zsq = z * z
    sum_z = z + rp
    dif_z = rp - z
    sqr_dif = zsq - rp * rp
    case1 = np.where((z < rp) & (sum_z <= 1))[0]
    casea = np.where((z < rp) & (sum_z > 1) & (dif_z < 1))[0]
    caseb = np.where((z < rp) & (sum_z > 1) & (dif_z > 1))[0]
    case2 = np.where((z == rp) & (sum_z <= 1))[0]
    casec = np.where((z == rp) & (sum_z > 1))[0]
    case3 = np.where((z > rp) & (sum_z < 1))[0]
    case4 = np.where((z > rp) & (sum_z == 1))[0]
    case5 = np.where((z > rp) & (sum_z > 1) & (sqr_dif < 1))[0]
    case6 = np.where((z > rp) & (sum_z > 1) & (sqr_dif == 1))[0]
    case7 = np.where((z > rp) & (sum_z > 1) & (sqr_dif > 1)
                     & (-1 < dif_z))[0]
    plus_case = np.concatenate((case1, case2, case3, case4, case5,
                                casea, casec))
    minus_case = np.concatenate((case3, case4, case5, case6, case7))
    star_case = np.concatenate((case5, case6, case7, casea, casec))
    ph = np.arccos(np.clip((1.0 - rp * rp + zsq) / (2.0 * z), -1.0, 1.0))
    theta_1 = np.zeros(z.size)
    ph_case = np.concatenate((case5, casea, casec))
    theta_1[ph_case] = ph[ph_case]
    theta_2 = np.arcsin(np.minimum(rp / z, 1.0))
    theta_2[case1] = np.pi
    theta_2[case2] = np.pi / 2.0
    theta_2[casea] = np.pi
    theta_2[casec] = np.pi / 2.0
    theta_2[case7] = ph[case7]
    plusflux = np.zeros(z.size)
    plusflux[plus_case] = _lune_integral(a, rp, z[plus_case],
                                         theta_1[plus_case],
                                         theta_2[plus_case], +1)
    if caseb.size:
        plusflux[caseb] = _sector_integral(a, 1.0, 0.0, np.pi)
    minsflux = np.zeros(z.size)
    minsflux[minus_case] = _lune_integral(a, rp, z[minus_case], 0.0,
                                          theta_2[minus_case], -1)
    starflux = np.zeros(z.size)
    starflux[star_case] = _sector_integral(a, 1.0, 0.0, ph[star_case])
    total = _sector_integral(a, 1.0, 0.0, 2.0 * np.pi)
    return (2.0 / total) * (plusflux + starflux - minsflux)


def occulted_fraction_rings(z, rp: float, law: str = "quad",
                      coeffs=(LD_U1, LD_U2), n_rad: int = LD_RADIAL_STEPS):
    """Fraction of the stellar flux blocked at planet-centre distances z,
    by ring integration -- the reference the analytic route is tested
    against, and the fallback for a law the analytic route lacks.

    The star is cut into n_rad concentric rings; each ring's covered
    AREA is the exact lens overlap of the planet's disc with the ring's
    outer circle minus its inner one, weighted by the limb-darkened
    intensity at the ring's centre.  Exact per ring for a uniform ring,
    so the planet's edge falling inside a ring (any rp, z near zero)
    costs nothing — the arc-at-ring-centre rule ``ld_template`` uses
    misplaces up to half a ring there.  Vectorised over z, any law.
    Verified against pylightcurve's ``transit_flux_drop`` (tests).
    """
    z = np.abs(np.asarray(z, dtype=float))
    rp = float(rp)
    out = np.zeros(z.shape)
    if rp <= 0.0:
        return out
    edges = np.linspace(0.0, 1.0, n_rad + 1)
    r = 0.5 * (edges[:-1] + edges[1:])
    mu = np.sqrt(np.clip(1.0 - r * r, 0.0, None))
    inten = ld_intensity(mu, law, coeffs)
    total = float(np.sum(inten * np.pi * (edges[1:] ** 2 - edges[:-1] ** 2)))
    active = z < 1.0 + rp
    if not np.any(active):
        return out
    a_edges = _lens_area(edges[None, :], rp, z[active][:, None])
    covered = np.diff(a_edges, axis=1)
    out[active] = (covered * inten[None, :]).sum(axis=1) / total
    return out


def planet_position(period: float, a_rs: float, ecc: float, inc_deg: float,
                    peri_deg: float, mid_time: float, t):
    """Planet position in stellar radii: x toward the observer, (y, z)
    in the sky plane.  Same conventions as pylightcurve's planet_orbit,
    which this reproduces to 1e-9 (tests)."""
    t = np.asarray(t, dtype=float)
    inc = math.radians(float(inc_deg))
    w = math.radians(float(peri_deg))
    a = float(a_rs)
    e = float(ecc)
    if e == 0.0:
        ph = (2.0 * np.pi / period) * (t - mid_time)
        cph, sph = np.cos(ph), np.sin(ph)
        return (a * math.sin(inc) * cph, a * sph, -a * math.cos(inc) * cph)
    f_mid = np.pi / 2.0 - w
    e_mid = 2.0 * math.atan(math.sqrt((1.0 - e) / (1.0 + e))
                            * math.tan(f_mid / 2.0))
    if e_mid < 0:
        e_mid += 2.0 * np.pi
    tp = mid_time - (period / 2.0 / np.pi) * (e_mid - e * math.sin(e_mid))
    m = ((t - tp - np.int_((t - tp) / period) * period)
         * 2.0 * np.pi / period)
    ea = m.copy()
    for _ in range(200):
        step = (ea - e * np.sin(ea) - m) / (1.0 - e * np.cos(ea))
        ea = ea - step
        if np.max(np.abs(step)) < 1e-12:
            break
    f = 2.0 * np.arctan(math.sqrt((1.0 + e) / (1.0 - e)) * np.tan(ea / 2.0))
    rad = a * (1.0 - e * e) / (1.0 + e * np.cos(f))
    fw = f + w
    return (rad * np.sin(fw) * math.sin(inc), -rad * np.cos(fw),
            -rad * np.sin(fw) * math.cos(inc))


def projected_distance(period, a_rs, ecc, inc_deg, peri_deg, mid_time, t,
                       rp: float = 0.1):
    """Sky-plane planet-star distance, with the planet parked well off
    the disc while it is BEHIND the star (x < 0) — pylightcurve's
    convention, so a secondary eclipse can never masquerade as a
    transit."""
    x, y, z = planet_position(period, a_rs, ecc, inc_deg, peri_deg,
                              mid_time, t)
    return np.where(x < 0, 1.0 + 10.0 * rp, np.sqrt(y * y + z * z))


def transit_duration_days(rp: float, period: float, a_rs: float, ecc: float,
                          inc_deg: float, peri_deg: float) -> float:
    """First-to-fourth-contact duration from the orbit, or NaN when the
    planet misses the disc.

    Winn (2010) with the eccentric correction gives the start value;
    the contacts themselves are then found on the actual orbit by
    bisection on the projected distance (z = 1 + rp), as pylightcurve
    does with a root finder.  The formula alone is exact for a circular
    orbit and up to 0.2 min off at e = 0.4; the bisection removes that.
    """
    w = math.radians(float(peri_deg))
    ii = math.radians(float(inc_deg))
    e = float(ecc)
    a = float(a_rs)
    rho = (1.0 - e * e) / (1.0 + e * math.sin(w))
    b = a * rho * math.cos(ii)
    s = 1.0 + float(rp)
    if b >= s:
        return float("nan")
    arg = (s * s - b * b) / (a * a * rho * rho - b * b)
    if arg <= 0 or arg > 1:
        return float("nan")
    guess = (period * rho * rho / (np.pi * math.sqrt(1.0 - e * e))
             * math.asin(math.sqrt(arg)))
    if e == 0.0 or not math.isfinite(guess) or guess <= 0:
        return guess

    def z_at(t):
        return projected_distance(period, a, e, inc_deg, peri_deg, 0.0,
                                  np.asarray(t, dtype=float), rp)

    # Bracket each contact between mid-transit (inside) and a point
    # well outside; give up on the refinement if the bracket fails.
    outside = np.array([-guess, guess])
    if not (z_at(np.array([0.0]))[0] < s) or np.any(z_at(outside) <= s):
        outside = np.array([-period / 4.0, period / 4.0])
        if not (z_at(np.array([0.0]))[0] < s) or np.any(z_at(outside) <= s):
            return guess
    lo = np.array([outside[0], 0.0])        # z(lo) > s for the first,
    hi = np.array([0.0, outside[1]])        # z(hi) > s for the fourth
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        inside = z_at(mid) < s
        # first contact: an inside midpoint moves the upper end down
        hi[0] = mid[0] if inside[0] else hi[0]
        lo[0] = lo[0] if inside[0] else mid[0]
        # fourth contact: an inside midpoint moves the lower end up
        lo[1] = mid[1] if inside[1] else lo[1]
        hi[1] = hi[1] if inside[1] else mid[1]
    t1 = 0.5 * (lo[0] + hi[0])
    t4 = 0.5 * (lo[1] + hi[1])
    return float(t4 - t1) if t4 > t1 else guess


def hops_transit_flux(t, rp: float, mid_time: float, geom: dict,
                      law: str, coeffs, n_rad: int = LD_RADIAL_STEPS,
                      exp_s: float = 0.0):
    """Relative flux of the star with the planet in front, from the
    archive's orbit — HOPS's transit model on this script's integrator.

    With ``exp_s`` the model is averaged over the exposure exactly as
    HOPS does: ``int(exp/10) + 1`` sub-steps centred on each mid-exposure
    time, the model evaluated at each and the mean taken."""
    t = np.asarray(t, dtype=float)
    args = (geom["period_d"], geom["a_rs"], geom["ecc"], geom["inc_deg"],
            geom["peri_deg"], mid_time)
    if exp_s and exp_s > 0:
        tf = int(exp_s / HOPS_SUB_EXPOSURE_S) + 1
        e = exp_s / 86400.0
        offs = np.arange(-e / 2 + e / tf / 2, e / 2, e / tf)[:tf]
        z = projected_distance(*args, (t[:, None] + offs[None, :]).ravel(),
                               rp)
        f = 1.0 - occulted_fraction(z, rp, law, coeffs, n_rad)
        return f.reshape(t.size, offs.size).mean(axis=1)
    z = projected_distance(*args, t, rp)
    return 1.0 - occulted_fraction(z, rp, law, coeffs, n_rad)


def ensemble_sampler(log_prob, p0, n_steps: int, rng, a: float = 2.0,
                     progress=None):
    """Affine-invariant ensemble sampler, stretch move (Goodman & Weare
    2010), the algorithm behind emcee.  Two half-ensembles update in
    turn so every proposal draws from walkers already at the current
    step.  Returns the chain (steps, walkers, dims) and the acceptance
    fraction."""
    p = np.array(p0, dtype=float)
    nw, nd = p.shape
    lp = np.array([log_prob(x) for x in p], dtype=float)
    chain = np.empty((n_steps, nw, nd))
    accepted = 0
    half = nw // 2
    for step in range(n_steps):
        for s0, s1 in ((0, half), (half, nw)):
            comp = p[s1:] if s0 == 0 else p[:s0]
            for k in range(s0, s1):
                j = rng.integers(comp.shape[0])
                zf = ((a - 1.0) * rng.random() + 1.0) ** 2 / a
                prop = comp[j] + zf * (p[k] - comp[j])
                lpn = log_prob(prop)
                if (np.isfinite(lpn) and math.log(rng.random())
                        < (nd - 1) * math.log(zf) + lpn - lp[k]):
                    p[k] = prop
                    lp[k] = lpn
                    accepted += 1
        chain[step] = p
        if progress is not None and n_steps >= 10 and step % (n_steps // 10) == 0:
            progress(step / n_steps)
    return chain, accepted / float(n_steps * nw)


def hops_mode_fit(t, mag, err_mag, geom: dict, ldc, detrend: dict,
                  mid_guess: float, rp_initial: float = 0.1,
                  iterations: int = 2000, burn_frac: float = 0.2,
                  seed: int = 1, law: str = "claret",
                  filter_outliers: bool = True,
                  scale_uncertainties: bool = True,
                  n_rad_fit: int = 200, progress=None, exp_s: float = 0.0):
    """HOPS's transit fit on this script's photometry.

    ``geom`` carries period_d, a_rs, ecc, inc_deg, peri_deg; ``ldc`` the
    four Claret coefficients; ``detrend`` maps HOPS's series names to
    arrays already reduced by their minimum (its convention).  The
    magnitudes are turned into relative flux, the prefit profiles the
    linear parameters (n and the detrending coefficients) in closed form
    over a grid in rp and mid-time, then HOPS's outlier loop and error
    rescaling run, then the sampler.  Returns everything results.txt,
    the chart and the report need, or None when the geometry cannot
    make a transit.
    """
    t = np.asarray(t, dtype=float)
    mag = np.asarray(mag, dtype=float)
    err_mag = np.asarray(err_mag, dtype=float)
    ok = np.isfinite(t) & np.isfinite(mag) & np.isfinite(err_mag)
    # A NaN in a detrending column (airmass below the horizon) would
    # otherwise run through the prefit, make every SSR NaN and abort the
    # mode with "the orbit makes no transit".
    for _col in detrend.values():
        _arr = np.asarray(_col, dtype=float)
        if _arr.size == ok.size:
            ok &= np.isfinite(_arr)
    n_nonfinite = int((~ok).sum())
    t, mag, err_mag = t[ok], mag[ok], err_mag[ok]
    if t.size < 10:
        return None
    flux = 10.0 ** (-0.4 * mag)
    med = float(np.median(flux))
    flux = flux / med
    ferr = flux * (math.log(10.0) / 2.5) * err_mag
    ferr = np.where(ferr > 0, ferr, np.nanmedian(ferr[ferr > 0])
                    if np.any(ferr > 0) else 1e-3)
    names = list(detrend.keys())
    xcols = [np.asarray(detrend[k], dtype=float)[ok] for k in names]
    coeffs = [float(c) for c in ldc]
    period = float(geom["period_d"])
    dur = transit_duration_days(rp_initial, period, geom["a_rs"],
                                geom["ecc"], geom["inc_deg"],
                                geom["peri_deg"])
    if not np.isfinite(dur) or dur <= 0:
        return None

    def transit(rp, mid):
        return hops_transit_flux(t, rp, mid, geom, law, coeffs, n_rad_fit,
                                 exp_s)

    def linear_solve(tr, werr):
        # flux = tr * (n + sum d_k x_k): weighted least squares, exact.
        cols = [tr] + [tr * x for x in xcols]
        A = np.column_stack(cols)
        w = 1.0 / (werr * werr)
        try:
            beta = np.linalg.solve((A * w[:, None]).T @ A,
                                   (A * w[:, None]).T @ flux)
        except np.linalg.LinAlgError:
            return None, np.inf
        model = A @ beta
        return beta, float(np.sum(w * (flux - model) ** 2))

    # HOPS's priors, verbatim: mid-time ±0.2 d around the prediction,
    # Rp/R* within a factor 10 of the catalogue value, the normalisation
    # between the flux extremes widened by twice the larger half-range.
    lo_mid, hi_mid = mid_guess - 0.2, mid_guess + 0.2
    lo_rp, hi_rp = 0.1 * rp_initial, 10.0 * rp_initial
    df = max(float(np.median(flux) - flux.min()),
             float(flux.max() - np.median(flux)))
    lo_n = max(1e-10, float(flux.min()) - 2.0 * df)
    hi_n = float(flux.max()) + 2.0 * df

    def profile(rp, mid, werr):
        beta, ssr = linear_solve(transit(rp, mid), werr)
        return beta, ssr

    def refine(rp, mid, werr, rounds=4):
        drp, dmid = 0.25 * rp, max(0.004, 0.05 * dur)
        best = (rp, mid) + profile(rp, mid, werr)
        for _ in range(rounds):
            for cand in np.linspace(best[1] - dmid, best[1] + dmid, 11):
                if lo_mid <= cand <= hi_mid:
                    beta, ssr = profile(best[0], cand, werr)
                    if ssr < best[3]:
                        best = (best[0], cand, beta, ssr)
            for cand in np.linspace(max(lo_rp, best[0] - drp),
                                    min(hi_rp, best[0] + drp), 11):
                beta, ssr = profile(cand, best[1], werr)
                if ssr < best[3]:
                    best = (cand, best[1], beta, ssr)
            drp *= 0.35
            dmid *= 0.35
        return best

    werr = ferr.copy()
    rp_grid = np.linspace(0.3 * rp_initial, 2.0 * rp_initial, 12)
    mid_step = min(2.0 / 1440.0, max(1e-4, (hi_mid - lo_mid) / 200.0))
    mid_grid = np.arange(lo_mid, hi_mid + 0.5 * mid_step, mid_step)
    best = None
    for rp in rp_grid:
        for mid in mid_grid:
            beta, ssr = profile(rp, mid, werr)
            if beta is not None and beta[0] > 0 and (best is None or ssr < best[3]):
                best = (rp, mid, beta, ssr)
    if best is None:
        return None
    best = refine(best[0], best[1], werr)

    # HOPS's outlier loop: normalised residuals beyond 3 x their own STD
    # get an "infinite" error, the fit repeats, until none remain.
    outlier_mask = np.zeros(t.size, dtype=bool)
    if filter_outliers:
        for _ in range(20):
            model = transit(best[0], best[1]) * (
                best[2][0] + sum(b * x for b, x in zip(best[2][1:], xcols)))
            nres = (flux - model) / werr
            # sigma over ALL points, flagged ones included at ~0 (error
            # 1e9) -- which tightens the threshold a little each round.
            # That is HOPS's own rule (pylightcurve41 optimisation.py,
            # np.std(norm_res) over the full array), kept on purpose:
            # this mode reproduces HOPS, and the head-to-head agreement
            # on outlier counts depends on it.
            flags = np.abs(nres) >= 3.0 * float(np.std(nres))
            flags &= ~outlier_mask
            if not np.any(flags):
                break
            outlier_mask |= flags
            werr = np.where(outlier_mask, 1e9, ferr)
            best = refine(best[0], best[1], werr, rounds=3)
    keep = ~outlier_mask
    t_k, flux_k, ferr_k = t[keep], flux[keep], ferr[keep]
    xcols_k = [x[keep] for x in xcols]

    def model_of(theta):
        n = theta[0]
        cs = theta[1:1 + len(names)]
        rp, mid = theta[1 + len(names)], theta[2 + len(names)]
        tr = hops_transit_flux(t_k, rp, mid, geom, law, coeffs, n_rad_fit,
                               exp_s)
        return tr * n * (1.0 + sum(c * x for c, x in zip(cs, xcols_k)))

    n0 = float(best[2][0])
    c0 = [float(b / n0) for b in best[2][1:]]
    theta0 = np.array([n0] + c0 + [best[0], best[1]])
    scale = 1.0
    if scale_uncertainties:
        res = flux_k - model_of(theta0)
        scale = float(np.sqrt(np.nanmean((res / ferr_k) ** 2)))
        if not (np.isfinite(scale) and scale > 0):
            scale = 1.0
    ferr_k = ferr_k * scale

    lo_b = np.array([lo_n] + [-2.0] * len(names) + [lo_rp, lo_mid])
    hi_b = np.array([hi_n] + [2.0] * len(names) + [hi_rp, hi_mid])

    def log_prob(theta):
        if np.any(theta < lo_b) or np.any(theta > hi_b):
            return -np.inf
        res = (flux_k - model_of(theta)) / ferr_k
        return -0.5 * float(res @ res)

    rng = np.random.default_rng(seed)
    nd = theta0.size
    nw = 3 * nd
    spread = 0.01 * (hi_b - lo_b)
    p0 = theta0[None, :] + rng.uniform(-0.5, 0.5, (nw, nd)) * spread[None, :]
    p0 = np.clip(p0, lo_b + 1e-9, hi_b - 1e-9)
    chain, acc = ensemble_sampler(log_prob, p0, int(iterations), rng,
                                  progress=progress)
    burn = int(burn_frac * chain.shape[0])
    flat = chain[burn:].reshape(-1, nd)
    # pylightcurve's 10-MAD joint filter before the percentiles.
    good = np.ones(flat.shape[0], dtype=bool)
    for k in range(nd):
        col = flat[:, k]
        medc = float(np.median(col))
        madc = float(np.sqrt(np.median((col - medc) ** 2)))
        if madc > 0:
            good &= (col > medc - 10 * madc) & (col < medc + 10 * madc)
    flat = flat[good] if np.count_nonzero(good) > 10 else flat
    q16, q50, q84 = np.quantile(flat, [0.16, 0.5, 0.84], axis=0)
    values = q50
    m_err = q50 - q16
    p_err = q84 - q50

    theta_med = values.copy()
    model_flux = model_of(theta_med)
    n_med = float(theta_med[0])
    cs_med = theta_med[1:1 + len(names)]
    rp_med = float(theta_med[1 + len(names)])
    mid_med = float(theta_med[2 + len(names)])
    trend_flux = n_med * (1.0 + sum(c * x for c, x in zip(cs_med, xcols_k)))
    transit_flux = hops_transit_flux(t_k, rp_med, mid_med, geom, law,
                                     coeffs, LD_RADIAL_STEPS, exp_s)
    depth_flux = float(1.0 - np.min(hops_transit_flux(
        np.array([mid_med]), rp_med, mid_med, geom, law, coeffs,
        LD_RADIAL_STEPS)))
    dur_med = transit_duration_days(rp_med, period, geom["a_rs"],
                                    geom["ecc"], geom["inc_deg"],
                                    geom["peri_deg"])
    duration_note = ""
    if not (np.isfinite(dur_med) and dur_med > 0):
        # Grazing orbit: the posterior's Rp/R* fell below the value at
        # which the planet still touches the disc, so the chord is NaN.
        # The start value's chord keeps the chart, the report and the
        # coverage test alive, and says so.
        dur_med = dur
        duration_note = ("duration taken from the catalogue's Rp/R* — at "
                         "the fitted value the planet no longer reaches "
                         "the disc (grazing orbit)")
    # A normalised template for the chart: -2.5 log10 of the transit
    # over one full duration, scaled to 1 at the deepest point.
    ph = np.linspace(-0.5, 0.5, LD_PHASE_STEPS)
    tt = mid_med + ph * dur_med
    sh = -2.5 * np.log10(np.clip(hops_transit_flux(
        tt, rp_med, mid_med, geom, law, coeffs, LD_RADIAL_STEPS, exp_s),
        1e-9, None))
    peak = float(sh.max())
    template = (ph, sh / peak if peak > 0 else sh)

    rows = []
    def _fit_row(name, k, initial):
        rows.append((name, "fit", float(values[k]), float(m_err[k]),
                     float(p_err[k]), initial, float(lo_b[k]), float(hi_b[k])))
    _fit_row("n", 0, float(np.median(flux)))
    for i, nm in enumerate(names):
        _fit_row(nm, 1 + i, 0)
    for i in range(4):
        rows.append((f"a_{i + 1}", "fix", coeffs[i]))
    _fit_row("rp_over_rs", 1 + len(names), rp_initial)
    rows.append(("period", "fix", period))
    rows.append(("sma_over_rs", "fix", float(geom["a_rs"])))
    rows.append(("eccentricity", "fix", float(geom["ecc"])))
    rows.append(("inclination", "fix", float(geom["inc_deg"])))
    rows.append(("periastron", "fix", float(geom["peri_deg"])))
    _fit_row("mid_time", 2 + len(names), mid_guess)

    return {
        "names": names,
        "values": values, "m_err": m_err, "p_err": p_err,
        "rows": rows,
        "n": n_med, "coeffs": [float(c) for c in cs_med],
        "rp": rp_med, "rp_m": float(m_err[1 + len(names)]),
        "rp_p": float(p_err[1 + len(names)]),
        "mid_time": mid_med, "mid_m": float(m_err[2 + len(names)]),
        "mid_p": float(p_err[2 + len(names)]),
        "duration_d": float(dur_med), "depth_flux": depth_flux,
        "duration_note": duration_note, "n_nonfinite": n_nonfinite,
        "outliers": int(np.count_nonzero(outlier_mask)),
        "outlier_mask": outlier_mask, "keep_mask": keep,
        "scale_factor": scale, "acceptance": acc,
        "iterations": int(iterations), "walkers": nw, "burn_in": burn,
        "exp_s": float(exp_s),
        "sub_steps": (int(exp_s / HOPS_SUB_EXPOSURE_S) + 1
                      if exp_s and exp_s > 0 else 1),
        "t": t_k, "flux": flux_k, "flux_err": ferr_k,
        "model_flux": model_flux, "trend_flux": trend_flux,
        "transit_flux": transit_flux, "template": template,
        "ldc": coeffs, "law": law, "geom": dict(geom),
        "mid_guess": float(mid_guess), "flux_median": med,
    }


def stacked_significance(t, mag, t0: float, duration: float,
                         sigma_postfit: float) -> float:
    """Significance of the in/out contrast, in sigma.

    ``(mean_in - mean_out) / sigma * sqrt(N_in * N_out / (N_in + N_out))``

    The scale factor is the inverse standard error of the difference of two
    means.  The tempting ``sqrt(N_total)`` over-credits a long
    out-of-transit baseline: doubling the pre-ingress coverage does not make
    a shallow dip twice as certain, because the uncertainty is dominated by
    how many points actually fall inside the event.

    The EMPIRICAL in/out contrast is used, not the fitted depth.  The
    model has no free baseline term of its own, so on transit-free data
    the fitter
    can always absorb a small offset as a wide, shallow "dip" with a nonzero
    depth -- but the data's own in/out contrast on such a run is
    approximately zero, so noise-only runs are rejected where a
    depth-based test would pass them.

    The test is TWO-SIDED, and that is the part that separates a transit
    from a trend.  A real transit RETURNS to the baseline it left, so the
    in-transit level has to sit below the points BEFORE ingress *and* below
    the points AFTER egress.  Pooling both sides into one out-of-transit
    mean loses exactly that: on a monotonic ramp -- uncorrected extinction,
    a drifting cloud, focus creep -- the fitter puts its window over the
    faint half, the pooled contrast is genuinely large, and a trend gets
    reported as a transit.  Comparing against each side separately and
    taking the WEAKER of the two kills that: on a ramp one side is brighter
    and the other fainter, so the weaker side is negative.

    The cost is a slightly conservative number on a real detection -- each
    side carries about half the baseline, and a minimum of two noisy
    quantities sits below either -- which is the right direction for a test
    whose whole job is to refuse to overclaim.

    Returns 0 when EITHER side is empty.  A transit with no pre-ingress or
    no post-egress baseline cannot be told from a trend by any means, and
    saying so is more use than a number that looks like a measurement.
    """
    t = np.asarray(t, dtype=float)
    mag = np.asarray(mag, dtype=float)
    if not np.isfinite(sigma_postfit) or sigma_postfit <= 0:
        return 0.0
    half = duration / 2.0
    inside = np.abs(t - t0) < half
    before = t <= t0 - half
    after = t >= t0 + half
    n_in = int(np.count_nonzero(inside))
    n_b = int(np.count_nonzero(before))
    n_a = int(np.count_nonzero(after))
    if n_in == 0 or n_b == 0 or n_a == 0:
        return 0.0
    # Magnitudes: in transit the star is FAINTER, so the in-transit mean is
    # the larger number.  Positive significance means "dimmer inside".
    mean_in = float(np.mean(mag[inside]))
    sides = []
    for n_side, sel in ((n_b, before), (n_a, after)):
        contrast = mean_in - float(np.mean(mag[sel]))
        scale = math.sqrt(n_in * n_side / float(n_in + n_side))
        sides.append(contrast / sigma_postfit * scale)
    return float(min(sides))


def chi2_nu_scatter(n_points: int, n_varys: int, n_noise: int) -> float:
    """One-sigma scatter of chi2/nu on white noise: the chi-square's own
    sqrt(2/nu) in quadrature with twice the relative error of a MAD
    noise estimate from n_noise points (sqrt(1.35/n)).  Printed beside
    the number so 1.4 from 40 points is not read as a failed model."""
    nu = max(1, int(n_points) - int(n_varys))
    m = max(1, int(n_noise))
    return math.sqrt(2.0 / nu + 4.0 * 1.35 / m)


def chi2_per_dof(resid, n_varys: int, oot_mask=None) -> float:
    """Reduced chi-square against a MODEL-INDEPENDENT noise floor.

    The residual scatter of a fit cannot judge that same fit -- divide the
    residuals by their own RMS and the answer is 1 by construction, whether
    the model is right or nonsense.  So the noise is estimated without the
    model, two ways, in preference order:

    * the MAD of the OUT-OF-TRANSIT residuals, which are signal-free by
      construction for a real transit, so nothing leaks either way;
    * failing that, the MAD of the FIRST DIFFERENCES divided by sqrt(2).
      Differencing removes any trend slower than the cadence, so what is
      left is the point-to-point noise -- but a steep ingress does enter
      it, which inflates the noise and DEFLATES chi2/nu.  Optimistic, and
      named as such.

    Around 1 means the model describes the data.  Well above 1 means it
    does not -- systematics, or a transit shape the template family
    cannot make.
    Well below 1 means the noise estimate is too large, usually because the
    out-of-transit window still holds part of the event.
    """
    r = np.asarray(resid, dtype=float)
    r = r[np.isfinite(r)]
    if r.size <= n_varys:
        return float("nan")
    noise = 0.0
    bias = 1.0
    if oot_mask is not None:
        m = np.asarray(oot_mask, dtype=bool)
        if m.size == r.size and int(m.sum()) >= CHI2_MIN_OOT:
            noise = _mad_std(r[m])
            # E[1/s^2] > 1/sigma^2 for any noise estimate from n points;
            # for a MAD-based sigma the excess is ~5.5/n (measured over
            # 20 000 Gaussian draws), which read as chi2/nu = 1.05-1.08
            # on pure white noise.  Divided out.
            bias = 1.0 + 5.5 / int(m.sum())
    if not (noise > 0):
        d = np.diff(r)
        noise = _mad_std(d) / math.sqrt(2.0) if d.size else 0.0
        bias = 1.0 + 5.2 / max(1, d.size)      # same measurement, 5.2/n
    if not (noise > 0):
        return float("nan")
    nfree = max(1, r.size - n_varys)
    return float(np.sum(r * r) / (noise * noise * nfree) / bias)


# -- HOPS-format results file --------------------------------------------
# The "Save results" button writes a `results.txt` byte-compatible in
# LAYOUT with the file HOPS (ExoWorldsSpies) leaves in its fitting
# folder: the column-aligned parameter table, then the #Filter/#Epoch
# block, then two residual-statistics blocks.  Everything below is a
# faithful port of pylightcurve 4.1 (hops/pylightcurve41) so a pipeline
# that parses a HOPS results.txt parses this one unchanged.  Parameter
# ROWS necessarily describe THIS script's model (quadratic limb
# darkening, named systematics bases), using HOPS's names where the
# concept is the same.

def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation).

    |error| < 1.2e-9 over (0, 1) — far below anything the Shapiro-Wilk
    weights can feel.  Exists because scipy is deliberately not a
    dependency of this script.
    """
    if not (0.0 < p < 1.0):
        return float("nan")
    a = (-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00)
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return ((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4])
                 * q + c[5])
                / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4])
                  * q + c[5])
                 / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    q = p - 0.5
    r = q * q
    return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4])
             * r + a[5]) * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4])
               * r + 1.0))


def shapiro_wilk_w(x):
    """The Shapiro-Wilk W statistic (Royston 1995, AS R94), W only.

    HOPS prints W and derives its flag from (1 - W); the p-value never
    appears in results.txt, so it is not computed.  Verified against
    scipy.stats.shapiro on the classic 11-point weight sample
    (W = 0.788815) and on synthetic normal/uniform draws.
    """
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    if n < 3 or float(x[-1] - x[0]) == 0.0:
        return float("nan")
    m = np.array([_norm_ppf((i - 0.375) / (n + 0.25))
                  for i in range(1, n + 1)])
    c = m / math.sqrt(float(m @ m))
    u = 1.0 / math.sqrt(n)
    a = np.empty(n)
    if n == 3:
        a = np.array([-math.sqrt(0.5), 0.0, math.sqrt(0.5)])
    else:
        an = (c[-1] + 0.221157 * u - 0.147981 * u ** 2
              - 2.071190 * u ** 3 + 4.434685 * u ** 4 - 2.706056 * u ** 5)
        if n <= 5:
            phi = (float(m @ m) - 2.0 * m[-1] ** 2) / (1.0 - 2.0 * an ** 2)
            a[1:-1] = m[1:-1] / math.sqrt(phi)
            a[-1], a[0] = an, -an
        else:
            an1 = (c[-2] + 0.042981 * u - 0.293762 * u ** 2
                   - 1.752461 * u ** 3 + 5.682633 * u ** 4
                   - 3.582633 * u ** 5)
            phi = ((float(m @ m) - 2.0 * m[-1] ** 2 - 2.0 * m[-2] ** 2)
                   / (1.0 - 2.0 * an ** 2 - 2.0 * an1 ** 2))
            a[2:-2] = m[2:-2] / math.sqrt(phi)
            a[-1], a[0] = an, -an
            a[-2], a[1] = an1, -an1
    num = float(a @ x) ** 2
    den = float(np.sum((x - x.mean()) ** 2))
    return float(num / den) if den > 0 else float("nan")


def hops_values_to_print(value, error_minus, error_plus):
    """pylightcurve's values_to_print, ported verbatim.

    The rounding width comes from the SMALLER error's decimal exponent
    minus one; infinite errors print the value at two decimals with
    'NaN' bars — both behaviours copied, not approximated.
    """
    value = float(value)
    error_minus = float(error_minus)
    error_plus = float(error_plus)
    if (math.isinf(error_minus) or math.isinf(error_plus)
            or math.isnan(error_minus) or math.isnan(error_plus)
            or error_minus <= 0 or error_plus <= 0):
        return str(round(value, 2)), "NaN", "NaN"
    width = min(int("{:.1e}".format(error_minus).split("e")[1]),
                int("{:.1e}".format(error_plus).split("e")[1]))
    width -= 1
    width *= -1
    return (str(round(value, width)), str(round(error_minus, width)),
            str(round(error_plus, width)))


def _hops_gaussian(x, model_norm, model_floor, model_mean, model_std):
    return model_floor + (model_norm * math.exp(
        -0.5 * (model_mean - x) * (model_mean - x)
        / (model_std * model_std)))


def hops_residual_stats(resid, err, n_free: int) -> dict:
    """pylightcurve's residual_statistics, ported: same keys, same
    autocorrelation, the same empirical flag thresholds (the gaussian
    constants are copied from the source, not re-fitted)."""
    resid = np.asarray(resid, dtype=float)
    err = np.asarray(err, dtype=float)
    norm = resid / err
    ac = np.correlate(norm, norm, mode="full")
    ac = ac[ac.size // 2:]
    ac = ac / ac[0] if ac[0] != 0 else ac
    lim_ac = _hops_gaussian(math.log10(norm.size),
                            1.08401, 0.03524, -0.26884, 1.49379)
    lim_sh = _hops_gaussian(math.log10(norm.size),
                            0.65521, 0.00213, -0.21983, 0.96882)
    w = shapiro_wilk_w(norm)
    max_ac = float(np.max(np.abs(ac[1:]))) if ac.size > 1 else float("nan")
    return {
        "res_max_autocorr": max_ac,
        "res_max_autocorr_flag": bool(max_ac > lim_ac),
        "res_shapiro": w,
        "res_shapiro_flag": bool((1.0 - w) > lim_sh)
        if np.isfinite(w) else False,
        "res_mean": float(np.mean(resid)),
        "res_std": float(np.std(resid)),
        "res_rms": float(np.sqrt(np.mean(resid ** 2))),
        "res_chi_sqr": float(np.sum(norm ** 2)),
        "res_red_chi_sqr": float(np.sum(norm ** 2)
                                 / max(1, norm.size - n_free)),
    }


def hops_results_text(r: dict) -> str:
    """The run's fit as a HOPS-layout ``results.txt``.

    Layout is pylightcurve's per-observation writer verbatim: a table of
    ``# variable  fix/fit  value  uncertainty  initial  min.allowed
    max.allowed`` with each column padded to its widest cell and columns
    joined by two spaces, then ``#Filter/#Epoch/#Number of outliers
    removed/#Uncertainties scale factor``, then ``#Residuals:`` and
    ``#Detrended Residuals:`` blocks.  In this script's additive-in-
    magnitude model the two residual series are numerically identical;
    both blocks are still written so a HOPS parser finds every line it
    expects.
    """
    fit = r.get("fit") or {}
    rows = []          # (name, fixfit, value, unc, initial, minv, maxv)

    def _fit_row(name, value, sig, initial="--", lo="--", hi="--"):
        if sig is not None and np.isfinite(sig) and sig > 0:
            v, em, ep = hops_values_to_print(value, sig, sig)
        else:
            v, em, ep = str(round(float(value), 6)), "NaN", "NaN"
        rows.append((name, "fit", v, f"-{em} +{ep}",
                     str(initial), str(lo), str(hi)))

    def _fix_row(name, value):
        rows.append((name, "fix", str(value), "-- --", "--", "--", "--"))

    hops = fit.get("hops")
    eph = r.get("ephemeris") or {}
    t0 = fit.get("t0")
    if hops:
        # The HOPS-compatible fit: its own parameter table, asymmetric
        # bars from the posterior, the same names HOPS writes.
        for row in hops["rows"]:
            if row[1] == "fit":
                name, _f, val, em, ep, initial, lo, hi = row
                v, sm, sp = hops_values_to_print(val, em, ep)
                rows.append((name, "fit", v, f"-{sm} +{sp}", str(initial),
                             str(lo), str(hi)))
            else:
                _fix_row(row[0], row[2])
    else:
        csig = fit.get("coeff_sigmas") or []
        _fit_row("n", fit.get("baseline", 0.0),
                 csig[0] if len(csig) > 0 else None, initial=0)
        for i, base in enumerate(fit.get("bases") or []):
            _fit_row(base, (fit.get("basis_coeffs") or [0.0] * (i + 1))[i],
                     csig[1 + i] if len(csig) > 1 + i else None, initial=0)
        _fix_row("ldc_1", fit.get("ld_u1", ""))
        _fix_row("ldc_2", fit.get("ld_u2", ""))
        rprs, rsig = fit.get("rprs"), fit.get("rprs_sigma")
        if rprs is not None:
            _fit_row("rp_over_rs", rprs, rsig)
        if eph.get("period_d"):
            _fix_row("period", eph["period_d"])
        if t0 is not None:
            _fit_row("mid_time", t0, fit.get("t0_sigma_d"))

    cols = [["# variable"], ["fix/fit"], ["value"], ["uncertainty"],
            ["initial"], ["min.allowed"], ["max.allowed"]]
    for row in rows:
        for k in range(7):
            cols[k].append(row[k])
    for col in cols:
        width = max(len(ff) for ff in col)
        for k in range(len(col)):
            col[k] = col[k] + " " * (width - len(col[k]))
    lines = ["  ".join(col[k] for col in cols)
             for k in range(len(cols[0]))]

    epoch = "--"
    if eph.get("period_d") and eph.get("t0_bjd") and t0 is not None:
        epoch = int(round((t0 - eph["t0_bjd"]) / eph["period_d"]))
    lines.append("")
    lines.append("#Filter: {0}".format(r.get("filter") or "--"))
    lines.append("#Epoch: {0}".format(epoch))
    lines.append("#Number of outliers removed: {0}".format(
        int(hops["outliers"]) if hops else int(r.get("n_clipped") or 0)))
    lines.append("#Uncertainties scale factor: {0}".format(
        float(hops["scale_factor"]) if hops else 1.0))
    if hops and hops.get("coverage_warning"):
        lines.append("#WARNING: " + hops["coverage_warning"])

    blocks = None
    if hops:
        # HOPS's residuals live in relative flux, after its outlier
        # filter and with its rescaled errors -- so do these.
        flux = np.asarray(hops["flux"], dtype=float)
        ferr = np.asarray(hops["flux_err"], dtype=float)
        trend = np.asarray(hops["trend_flux"], dtype=float)
        n_free = len([row for row in rows if row[1] == "fit"])
        blocks = (("#Residuals:",
                   flux - np.asarray(hops["model_flux"], dtype=float), ferr),
                  ("#Detrended Residuals:",
                   flux / trend - np.asarray(hops["transit_flux"],
                                             dtype=float), ferr / trend))
    elif fit.get("model_mag") is not None and r.get("mag") is not None:
        err = np.asarray(r.get("err"), dtype=float)
        model = np.asarray(fit["model_mag"], dtype=float)
        mag = np.asarray(r["mag"], dtype=float)
        n_free = len([row for row in rows if row[1] == "fit"]) + 2
        blocks = (("#Residuals:", mag - model, err),
                  ("#Detrended Residuals:",
                   np.asarray(fit["detrended"], dtype=float)
                   - (model - np.asarray(fit["trend"], dtype=float)), err))
    if blocks:
        for title, series, err in blocks:
            stats = hops_residual_stats(series, err, n_free)
            lines.append("")
            lines.append(title)
            lines.append("#Mean: {0}".format(stats["res_mean"]))
            lines.append("#STD: {0}".format(stats["res_std"]))
            lines.append("#RMS: {0}".format(stats["res_rms"]))
            lines.append("#Chi squared: {0}".format(stats["res_chi_sqr"]))
            lines.append("#Reduced chi squared: {0}".format(
                stats["res_red_chi_sqr"]))
            lines.append("#Max auto-correlation: {0}".format(
                stats["res_max_autocorr"]))
            lines.append("#Max auto-correlation flag: {0}".format(
                stats["res_max_autocorr_flag"]))
            lines.append("#Shapiro test: {0}".format(stats["res_shapiro"]))
            lines.append("#Shapiro test flag: {0}".format(
                stats["res_shapiro_flag"]))
    return "\n".join(lines)


def t0_uncertainty(t, mag, t0: float, duration: float, template,
                   sigma: float, grid_step: float, beta: float = 1.0,
                   durations=None, fixed=None, gram=None, rhs=None,
                   mm=None):
    """1-sigma on the mid-transit time, in days, or NaN.

    From the CURVATURE of the chi-square surface along T0, measured by
    fitting a parabola to the profiled sum of squares over a window, rather
    than by walking outward to delta-chi2 = 1.  Profiled over the SAME
    design matrix the fit used -- systematics included -- because a bar
    measured without them describes a fit nobody ran, and comes out too
    narrow.

    The walk was tried first and is wrong here, for a reason worth keeping:
    a boxy model on sampled data has a BUMPY surface.  Shifting T0 by less
    than one cadence changes which points fall inside the window, so the
    minimum sits in a narrow local dell whose width is a fraction of the
    sampling, not the width of the envelope the fit actually explores.
    Measured over 60 runs at 4 mmag per point on a 120 s cadence, the walk
    returned 86 s at every depth below 12 mmag -- a plateau at 0.7 cadences
    -- while the true run-to-run scatter kept growing: 47, 86, 171 s.  The
    parabola averages over the bumps and tracks it: 52, 91, 133 s against
    58, 90, 125 s measured.

    The window is five cadences.  Wider was tested and over-states: at 0.3
    durations the bar came out 1.5x to 1.75x the true scatter at every
    depth, because the surface stops being a parabola out there.

    At every trial T0 the depth and baseline are re-solved in closed form
    and the duration is re-minimised over the grid the fit searched, so the
    interval carries the T0/duration correlation.

    Scaled by the red-noise ``beta``, for the same reason the significance
    is.  Floored at half the T0 grid step -- the search cannot resolve
    finer than it samples.  NOT floored at the exposure time: a transit
    mid-point is constrained by the whole curve and is routinely known to a
    fraction of one frame.  That floor belongs to an occultation edge,
    where a single crossing sample sets the answer.
    """
    t = np.asarray(t, dtype=float)
    mag = np.asarray(mag, dtype=float)
    if not (np.isfinite(sigma) and sigma > 0) or t.size < 6:
        return float("nan")
    durs = (np.asarray(durations, dtype=float)
            if durations is not None and len(durations)
            else np.asarray([duration], dtype=float))
    # The SAME design matrix the fit walked.  Profiling a different surface
    # than the one that was minimised gives a bar for a fit nobody ran --
    # and with the systematics in the model, "different" means "without
    # them", which comes out too narrow.
    if fixed is None:
        fixed = np.ones((t.size, 1))
        gram = fixed.T @ fixed
        rhs = fixed.T @ mag
        mm = float(mag @ mag)
    order = np.sort(t)
    cadence = float(np.median(np.diff(order))) if order.size > 1 else 0.0
    window = max(T0_ERROR_CADENCES * cadence, 3.0 * abs(grid_step))
    if not (window > 0):
        return float("nan")

    offsets = np.linspace(-window, window, T0_ERROR_SAMPLES)
    ssr = np.full(offsets.size, np.nan)
    for i, off in enumerate(offsets):
        best = np.inf
        for d in durs:
            got = _solve_simultaneous(mag, ld_shape(t, t0 + off, d, template),
                                      fixed, gram, rhs, mm)
            if got is not None and got[2] < best:
                best = got[2]
        if math.isfinite(best):
            ssr[i] = best
    ok = np.isfinite(ssr)
    if int(ok.sum()) < 5:
        return float("nan")
    curv = np.polyfit(offsets[ok], ssr[ok], 2)[0]
    if not (curv > 0):
        # A surface with no upward curvature over the window means T0 is
        # unconstrained here; a number would be an invention.
        return float("nan")
    sigma_t0 = (sigma / math.sqrt(curv)) * max(1.0, float(beta))
    return max(sigma_t0, 0.5 * abs(grid_step))


def build_design(n: int, bases=None):
    """``(fixed, names, note)`` -- the constant column plus usable bases.

    Each basis is centred and scaled to unit spread so the normal
    equations stay conditioned when airmass (1-3), FWHM (2-5 px) and sky
    (hundreds of ADU) share one matrix.  A basis with fewer than three
    finite values or no spread is dropped and named; NaNs inside a usable
    one are interpolated rather than excluded, or the row it sits in would
    be the only one that never gets the trend subtracted.
    """
    cols = [np.ones(n)]
    names, dropped, scales, offsets = [], [], [], []
    for name, vec in (bases or {}).items():
        if vec is None:
            continue
        xs = np.asarray(vec, dtype=float)
        if xs.size != n:
            dropped.append(f"{name} (wrong length)")
            continue
        if int(np.isfinite(xs).sum()) < 3:
            dropped.append(f"{name} (too few values)")
            continue
        xs = _fill_gaps(xs)
        mu = float(np.mean(xs))
        sd = float(np.std(xs))
        if sd < 1e-12:
            dropped.append(f"{name} (no spread)")
            continue
        col = (xs - mu) / sd
        # Two bases that track each other (sky level follows airmass on
        # most nights) leave the depth a valid least-squares answer but
        # make their own coefficients, their bars and the airmass slope
        # meaningless -- and a singular node used to be reported as "too
        # few points".  The later one is dropped, and says why.
        twin = None
        for other_name, other in zip(names, cols[1:]):
            rr = abs(float(np.corrcoef(col, other)[0, 1]))
            if rr > BASIS_COLLINEAR_R:
                twin = (other_name, rr)
                break
        if twin:
            dropped.append(f"{name} (collinear with {twin[0]}, "
                           f"r = {twin[1]:.2f})")
            continue
        cols.append(col)
        names.append(name)
        offsets.append(mu)
        scales.append(sd)
    note = "+".join(names) if names else "none"
    if dropped:
        note += " (dropped: " + ", ".join(dropped) + ")"
    return (np.column_stack(cols), names, note, np.asarray(offsets),
            np.asarray(scales))


def _solve_simultaneous(mag, shape, fixed, gram, rhs, mm):
    """One node of the simultaneous fit: ``(coeffs, depth, ssr)`` or None.

    ``fixed`` holds the constant column and the systematics; only the
    ``shape`` column changes from node to node, so the expensive part --
    the Gram matrix of everything else -- is computed once by the caller
    and pasted in here.  Measured against the plain 2x2 solve this
    replaces: 11.1 us per node against 13.8, i.e. fitting the systematics
    at the same time is FASTER than not doing it, because the old version
    recomputed sums it did not have to.
    """
    k = fixed.shape[1]
    fs = fixed.T @ shape
    ss = float(shape @ shape)
    bs = float(shape @ mag)
    G = np.empty((k + 1, k + 1))
    G[:k, :k] = gram
    G[:k, k] = fs
    G[k, :k] = fs
    G[k, k] = ss
    b = np.empty(k + 1)
    b[:k] = rhs
    b[k] = bs
    try:
        c = np.linalg.solve(G, b)
    except np.linalg.LinAlgError:
        return None
    ssr = float(mm - c @ b)
    if not math.isfinite(ssr):
        return None
    return c[:k], float(c[k]), max(0.0, ssr)


def fit_transit(t, mag, bases=None, u1: float = LD_U1, u2: float = LD_U2):
    """Fit a limb-darkened transit AND the systematics, together.

    Returns a dict, or ``None`` when there is not enough data to try.

    Two things changed here at once, and both were measured first.

    **The shape is a limb-darkened transit, not a trapezoid.**  A trapezoid
    fitted to a real transit comes out 5-6% too SHALLOW across rp/Rs 0.08
    to 0.15, systematically -- and chi2/nu stays at 1.0, so nothing in the
    output would ever say so.  The shapes searched are now real geometries:
    four planet-to-star radius ratios crossed with two impact parameters,
    the same eight variants the eight ingress fractions used to provide.
    Each is a TEMPLATE on normalised phase, so the model stays LINEAR in
    depth and the closed-form solve survives -- a physically free rp/Rs
    would couple depth and shape, and with them would go the determinism
    and the no-optimiser guarantee.  Measured: the template family brings
    the depth bias to about 1%.

    **The systematics are fitted WITH the transit, not before it.**  The
    old sequence was detrend, fit, re-detrend on the fitted window, re-fit
    -- three passes that each treated the previous baseline as exactly
    known.  It is not: the baseline has an uncertainty, and a sequential
    fit throws it away instead of propagating it into the depth and the
    mid-time.  Here the airmass, seeing, sky and star-count columns sit in
    the same design matrix as the transit, so the transit CANNOT be
    absorbed into a correlated basis -- which is what the out-of-transit
    anchoring existed to prevent -- and the covariance is carried rather
    than discarded.

    The search is still a grid over ``(T0, duration, shape)`` with
    everything linear solved in closed form at every node.  Same answer
    every run, no optimiser, no convergence to fail.
    """
    t = np.asarray(t, dtype=float)
    mag = np.asarray(mag, dtype=float)
    good = np.isfinite(t) & np.isfinite(mag)
    if good.sum() < 10:
        return None
    t = t[good]
    mag = mag[good]
    sub = {k: np.asarray(v, dtype=float)[good]
           for k, v in (bases or {}).items()
           if v is not None and np.asarray(v).size == good.size}
    fixed, base_names, base_note, offsets, scales = build_design(t.size, sub)

    span = float(t.max() - t.min())
    if span <= 0:
        return None

    gram = fixed.T @ fixed
    rhs = fixed.T @ mag
    mm = float(mag @ mag)

    templates = [((rp, b), ld_template(rp, b, u1, u2))
                 for rp in LD_RP_GRID for b in LD_B_GRID]

    # T0 is searched over the middle of the run only.  A "transit" whose
    # centre sits outside the observed window is an extrapolation, and its
    # depth is then set by whichever end of the baseline happens to droop.
    t0_lo = t.min() + 0.15 * span
    t0_hi = t.max() - 0.15 * span
    if t0_hi <= t0_lo:
        t0_lo, t0_hi = t.min(), t.max()
    t0_grid = np.linspace(t0_lo, t0_hi, FIT_T0_STEPS)
    dur_grid = np.linspace(FIT_MIN_DURATION_FRAC * span,
                           FIT_MAX_DURATION_FRAC * span,
                           FIT_DURATION_STEPS)

    best = None
    for dur in dur_grid:
        for (rp, bimp), tmpl in templates:
            for t0 in t0_grid:
                shape = ld_shape(t, t0, dur, tmpl)
                if np.count_nonzero(shape > 0.5) < 3:
                    continue
                got = _solve_simultaneous(mag, shape, fixed, gram, rhs, mm)
                if got is None:
                    continue
                coeffs, depth, ssr = got
                if depth <= 0:
                    # Brightening, not a transit.  Skipped rather than
                    # clamped: a zero-depth node would win the chi-square
                    # race on noise and mask a real shallow dip elsewhere.
                    continue
                if best is None or ssr < best["ssr"]:
                    best = {"ssr": ssr, "t0": float(t0), "duration": float(dur),
                            "rp": float(rp), "b": float(bimp),
                            "depth": depth, "coeffs": coeffs}
    if best is None:
        return None

    # Refine around the winning node.  The coarse grid quantises T0 to
    # (0.7 * span) / 120 -- 105 s on a 5 h run -- and that showed up as a
    # measurement artefact: over 60 runs of a 20 mmag transit every fit
    # returned the SAME T0.  The data were being rounded to the search.
    coarse_t0 = float(t0_grid[1] - t0_grid[0]) if t0_grid.size > 1 else 0.0
    coarse_dur = float(dur_grid[1] - dur_grid[0]) if dur_grid.size > 1 else 0.0
    if coarse_t0 > 0:
        fine_t0 = np.linspace(best["t0"] - 1.5 * coarse_t0,
                              best["t0"] + 1.5 * coarse_t0, FIT_REFINE_T0_STEPS)
        fine_dur = (np.linspace(max(1e-9, best["duration"] - 1.5 * coarse_dur),
                                best["duration"] + 1.5 * coarse_dur,
                                FIT_REFINE_DUR_STEPS)
                    if coarse_dur > 0 else np.asarray([best["duration"]]))
        for dur in fine_dur:
            for (rp, bimp), tmpl in templates:
                for t0 in fine_t0:
                    shape = ld_shape(t, t0, dur, tmpl)
                    if np.count_nonzero(shape > 0.5) < 3:
                        continue
                    got = _solve_simultaneous(mag, shape, fixed, gram, rhs, mm)
                    if got is None or got[1] <= 0:
                        continue
                    if got[2] < best["ssr"]:
                        best = {"ssr": got[2], "t0": float(t0),
                                "duration": float(dur), "rp": float(rp),
                                "b": float(bimp), "depth": got[1],
                                "coeffs": got[0]}
        coarse_t0 = (float(fine_t0[1] - fine_t0[0])
                     if fine_t0.size > 1 else coarse_t0)
        dur_grid = np.unique(np.concatenate([dur_grid, fine_dur]))

    tmpl = dict(templates)[(best["rp"], best["b"])]
    shape = ld_shape(t, best["t0"], best["duration"], tmpl)
    coeffs = best["coeffs"]
    trend = fixed[:, 1:] @ coeffs[1:] if fixed.shape[1] > 1 else np.zeros(t.size)
    model = fixed @ coeffs + best["depth"] * shape
    resid = mag - model
    # The systematics-free curve everything downstream reads.
    detrended = mag - trend

    n_free = 3 + len(base_names)    # t0, duration, shape variant + bases
    dof = max(1, t.size - n_free - 2)          # + depth + baseline
    rms_resid = _mad_std(resid)
    sigma = float(rms_resid * math.sqrt(t.size / float(dof)))
    if not (np.isfinite(sigma) and sigma > 0):
        sigma = float(np.sqrt(np.sum(resid * resid) / dof))

    sig = stacked_significance(t, detrended, best["t0"], best["duration"],
                               sigma)
    beta, beta_rows = red_noise_beta(t, resid, best["duration"])
    sig_white = sig
    sig = sig / beta

    inside = shape > 0.5
    n_in = int(np.count_nonzero(inside))
    n_out = int(np.count_nonzero(~inside))
    # The depth bar comes from the COVARIANCE of the joint solve, not
    # from the two-box formula sigma*sqrt(1/n_in + 1/n_out) it replaces.
    # The box formula ignores the correlation between the depth and the
    # fitted baseline-plus-systematics, and it treats ingress points as
    # either fully in or fully out.  Calibrated over 24 synthetic nights
    # (12 mmag transit, 4 mmag noise, airmass ramp in the design): true
    # run-to-run depth scatter 1.01 mmag, box formula 0.81 (26% narrow --
    # and this number goes into the AAVSO file), covariance 0.89.  The
    # remaining ~15% is the discreteness of the template family, which
    # the profile over T0/duration was measured NOT to carry.
    depth_sigma = float("nan")
    coeff_sigmas = None
    if sigma > 0 and n_in > 0 and n_out > 0:
        try:
            a_full = np.column_stack([fixed, shape])
            g_inv = np.linalg.inv(a_full.T @ a_full)
            depth_sigma = beta * sigma * math.sqrt(max(g_inv[-1, -1], 0.0))
            # The same covariance also prices the baseline and each
            # systematic coefficient — kept for the HOPS-format results
            # file, where a fitted parameter must carry its error bar.
            coeff_sigmas = [float(beta * sigma
                                  * math.sqrt(max(g_inv[k, k], 0.0)))
                            for k in range(fixed.shape[1])]
        except np.linalg.LinAlgError:
            depth_sigma = beta * sigma * math.sqrt(1.0 / n_in + 1.0 / n_out)

    t0_sigma = t0_uncertainty(t, mag, best["t0"], best["duration"],
                              tmpl, sigma, coarse_t0, beta,
                              durations=dur_grid, fixed=fixed, gram=gram,
                              rhs=rhs, mm=mm)
    chi2_nu = chi2_per_dof(resid, n_free + 2, ~inside)
    _n_oot = int(np.count_nonzero(~inside))
    chi2_nu_sigma = chi2_nu_scatter(
        resid.size, n_free + 2,
        _n_oot if _n_oot >= CHI2_MIN_OOT else max(1, resid.size - 1))

    # The airmass coefficient, back in the unit anyone can read.  The
    # column was centred and scaled to keep the solve conditioned.
    slope = None
    if "airmass" in base_names:
        i = base_names.index("airmass")
        sd = float(scales[i])
        slope = float(coeffs[1 + i] / sd) if sd > 0 else None

    # The measured depth translated into the convention EXOTIC, HOPS and
    # AstroImageJ quote: Rp/Rs from inverting the same limb-darkened
    # model the fit used, and (Rp/Rs)^2 as "the depth".  The error bar
    # propagates by inverting depth +/- sigma -- the mapping is smooth
    # and nearly linear over any real bar.
    _dflux = 1.0 - 10.0 ** (-0.4 * best["depth"])
    _rprs = rprs_from_depth(_dflux, b=best["b"], u1=u1, u2=u2)
    _rprs_sig = None
    if _rprs is not None and np.isfinite(depth_sigma) and depth_sigma > 0:
        _up = rprs_from_depth(1.0 - 10.0 ** (-0.4 * (best["depth"]
                                                     + depth_sigma)),
                              b=best["b"], u1=u1, u2=u2)
        _dn = rprs_from_depth(1.0 - 10.0 ** (-0.4 * (best["depth"]
                                                     - depth_sigma)),
                              b=best["b"], u1=u1, u2=u2)
        if _up is not None and _dn is not None:
            _rprs_sig = 0.5 * abs(_up - _dn)
            # The depth -> Rp/R* conversion depends on WHICH impact-
            # parameter node the search picked, and noise picks it: b = 0
            # and b = 0.5 turn the same depth into radii 2.7 % apart, more
            # than the depth bar on a good night.  Measured over 40
            # realisations the radius scattered 1.4x its bar (coverage
            # 47 %).  Half the spread across the grid nodes goes in, in
            # quadrature.  The depth bar itself was and is calibrated.
            _alt = [rprs_from_depth(_dflux, b=float(bb), u1=u1, u2=u2)
                    for bb in LD_B_GRID]
            _alt = [x for x in _alt if x is not None]
            if len(_alt) >= 2:
                _rprs_sig = math.hypot(_rprs_sig,
                                       0.5 * (max(_alt) - min(_alt)))

    return {
        "t0": best["t0"],
        "duration_d": best["duration"],
        "duration_h": best["duration"] * 24.0,
        "rp_over_rs": best["rp"],
        "impact_b": best["b"],
        "ld_u1": float(u1),
        "ld_u2": float(u2),
        "depth_mag": best["depth"],
        "depth_mmag": best["depth"] * 1000.0,
        "depth_pct": (1.0 - 10.0 ** (-0.4 * best["depth"])) * 100.0,
        "rprs": _rprs,
        "rprs_sigma": _rprs_sig,
        "depth_rprs2_pct": (None if _rprs is None
                            else _rprs * _rprs * 100.0),
        "depth_rprs2_pct_sigma": (None if _rprs is None or _rprs_sig is None
                                  else 2.0 * _rprs * _rprs_sig * 100.0),
        "depth_sigma_mmag": depth_sigma * 1000.0,
        "t0_sigma_d": t0_sigma,
        "t0_sigma_s": t0_sigma * 86400.0,
        "chi2_nu": chi2_nu, "chi2_nu_sigma": chi2_nu_sigma,
        "baseline": float(coeffs[0]),
        "basis_coeffs": [float(c) for c in coeffs[1:1 + len(base_names)]],
        "coeff_sigmas": coeff_sigmas,
        "bases": base_names,
        "base_note": base_note,
        "airmass_slope": slope,
        "trend": trend,
        "detrended": detrended,
        "good_mask": good,
        "sigma_postfit_mmag": sigma * 1000.0,
        "rms_resid_mmag": rms_resid * 1000.0,
        "significance": sig,
        "significance_white": sig_white,
        "red_noise_beta": beta,
        "red_noise_rows": beta_rows,
        "n_in": n_in,
        "n_out": n_out,
        "detected": bool(sig >= MIN_DETECTION_SIGMA),
        "model_t": t,
        "model_mag": model,
        "oot_mask": ~inside,
        "duty_cycle": best["duration"] / span if span > 0 else float("nan"),
    }


def bin_series(t, y, n_bins: int):
    """Equal-width bins over time: ``(centres, means, standard errors, counts)``.

    Binning is presentation, never input to the fit: the fit sees every
    point, because binning first throws away the very scatter the
    significance test needs in order to be honest about itself.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(t) & np.isfinite(y)
    t, y = t[good], y[good]
    if t.size == 0 or n_bins < 1:
        return (np.empty(0),) * 4
    edges = np.linspace(t.min(), t.max() + 1e-12, n_bins + 1)
    idx = np.clip(np.digitize(t, edges) - 1, 0, n_bins - 1)
    ct, cm, ce, cn = [], [], [], []
    for b in range(n_bins):
        sel = idx == b
        n = int(np.count_nonzero(sel))
        if n == 0:
            continue
        ct.append(float(np.mean(t[sel])))
        cm.append(float(np.mean(y[sel])))
        # ddof=1: the standard error of a mean needs the SAMPLE deviation.
        # With numpy's default ddof=0 the bars come out 29% too small at
        # two points per bin, 11% at five -- and a light curve whose error
        # bars are systematically small looks more convincing than it is.
        ce.append(float(np.std(y[sel], ddof=1) / math.sqrt(n))
                  if n > 1 else float("nan"))
        cn.append(n)
    return (np.asarray(ct), np.asarray(cm), np.asarray(ce), np.asarray(cn))


def rotation_spread_deg(homographies):
    """Largest field rotation between any two frames, in degrees, or None.

    Each homography maps its frame onto the registration reference, so the
    rotation it encodes is that frame's orientation relative to the
    reference.  ``atan2(h10, h00)`` reads it off the upper-left 2x2 block.

    Why this is worth measuring at all: a MERIDIAN FLIP puts half the run
    at 180 degrees to the other half, and for photometry that is not a
    cosmetic difference.  The star lands on a completely different patch of
    sensor -- different flat-field response, different hot pixels, a
    different corner of the vignette -- so the light curve carries a STEP
    at the flip.  A step in the middle of a run is exactly the shape a
    transit ingress has, and exactly the shape that can cancel one.

    Returns None when there is nothing to compare.
    """
    angles = []
    for h in homographies or []:
        if h is None:
            continue
        try:
            h00 = float(getattr(h, "h00", 0.0))
            h10 = float(getattr(h, "h10", 0.0))
        except (TypeError, ValueError):
            continue
        if abs(h00) < 1e-12 and abs(h10) < 1e-12:
            continue                    # unset registration, not a rotation
        angles.append(math.degrees(math.atan2(h10, h00)))
    if len(angles) < 2:
        return None
    # Compare on the circle: -179.9 and +179.9 are 0.2 degrees apart, not
    # 359.8.  Without this a run that straddles the wrap would report a
    # flip that is not there.
    worst = 0.0
    for i, a in enumerate(angles):
        for b in angles[i + 1:]:
            d = abs((a - b + 180.0) % 360.0 - 180.0)
            if d > worst:
                worst = d
    return worst

# ---------------------------------------------------------------------------
# Comparison-star selection
# ---------------------------------------------------------------------------
def _header_ra_deg(header):
    """Telescope pointing RA in degrees, or None.

    Only used to CHECK the longitude sign, and that makes the unit
    ambiguity harmless: if a header stated RA in hours and this read it as
    degrees, the computed altitude would miss by far more than the
    tolerance and the check would come back "not conclusive" — never a
    wrong flip.  A guess that can only fail safe does not need to be
    perfect.
    """
    for key in ("RA", "OBJCTRA", "CRVAL1", "RA_OBJ"):
        raw = header.get(key, None)
        if raw is None or str(raw).strip() == "":
            continue
        txt = str(raw).strip()
        try:
            return float(txt) % 360.0          # already degrees
        except ValueError:
            v = _sexagesimal(txt)              # H M S
            if np.isfinite(v):
                return (v * 15.0) % 360.0
    return None


def _header_dec_deg(header):
    """Telescope pointing Dec in degrees, or None."""
    for key in ("DEC", "OBJCTDEC", "CRVAL2", "DEC_OBJ"):
        raw = header.get(key, None)
        if raw is None or str(raw).strip() == "":
            continue
        txt = str(raw).strip()
        try:
            v = float(txt)
        except ValueError:
            v = _sexagesimal(txt)
        if np.isfinite(v) and -90.0 <= v <= 90.0:
            return v
    return None


def longitude_sign_check(header, lat, lon):
    """``(lon, note)`` -- the longitude, with its SIGN decided by measurement.

    FITS never settled this.  N.I.N.A. writes east-positive; older systems,
    MicroObservatory among them, write WEST-positive, and the two are
    indistinguishable from the number alone.  Getting it wrong mirrors the
    site across the globe, which does not fail loudly: it silently
    computes the airmass for the wrong place and detrends against it.

    But the frames usually carry the answer.  An altitude in the header,
    together with the pointing and the time, is a measurement of where the
    telescope was -- so both signs are tried and the one that reproduces
    it wins.  Measured on this data: -110.88 gives +62.60 deg against the
    header's +62.592, while +110.88 puts the target 10 deg BELOW the
    horizon.  No ambiguity left to warn about.
    """
    if lon is None or not math.isfinite(float(lon)) or abs(float(lon)) < 1e-9:
        return lon, ""
    alt_obs = None
    for key in ("TELALT", "CENTALT", "OBJCTALT", "ALTITUDE", "ALT-OBJ"):
        try:
            v = float(str(header.get(key, "")).strip() or "nan")
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and -90.0 <= v <= 90.0:
            alt_obs, alt_key = v, key
            break
    if alt_obs is None:
        return lon, ("longitude is taken as EAST positive — no altitude in "
                     "the header to check the sign against")
    ra = _header_ra_deg(header)
    dec = _header_dec_deg(header)
    jd = _jd_from_dateobs(str(header.get("DATE-OBS", "")
                              or header.get("UT-OBS", "")))
    if ra is None or dec is None or not np.isfinite(jd):
        return lon, ("longitude is taken as EAST positive — no pointing or "
                     "time to check the sign against")
    best, gaps = None, {}
    for cand in (float(lon), -float(lon)):
        alt = _altitude_deg(jd, ra, dec, float(lat), cand)
        gaps[cand] = abs(alt - alt_obs) if np.isfinite(alt) else float("inf")
        if best is None or gaps[cand] < gaps[best]:
            best = cand
    if not math.isfinite(gaps[best]) or gaps[best] > LON_SIGN_TOLERANCE_DEG:
        return lon, (f"longitude is taken as EAST positive — neither sign "
                     f"reproduces {alt_key}={alt_obs:.2f}deg (closest is "
                     f"{gaps[best]:.1f}deg off), so the check is not "
                     "conclusive")
    if abs(best - float(lon)) < 1e-9:
        return lon, (f"sign confirmed against {alt_key}={alt_obs:.2f}deg "
                     f"(agrees to {gaps[best]:.2f}deg)")
    return best, (f"SIGN FLIPPED to {best:+.4f}: the header value would put "
                  f"the target {gaps[float(lon)]:.0f}deg from the "
                  f"{alt_key}={alt_obs:.2f}deg it records, the flipped one "
                  f"reproduces it to {gaps[best]:.2f}deg. This header is "
                  "WEST-positive")


def image_scale_arcsec(header):
    """``(arcsec_per_px, where)`` from a header, or ``(None, why)``.

    Siril needs the plate scale to solve, and takes it from FOCALLEN and
    XPIXSZ.  When those are absent it falls back to whatever it last SAVED
    as a default -- which is the previous target's telescope.  Measured on
    EXOTIC's demo set: Siril used 3.76 um / 380.33 mm left over from a
    different rig, computed a 0.46 degree field where the truth is 0.94,
    and the solve failed with "Generic error" after fetching 373 000 stars.
    Nothing in that message says "wrong scale".

    Many headers state the scale outright instead -- IM_SCALE on
    MicroObservatory, SECPIX on older systems -- so it is read directly
    when it is there and derived from the optics when it is not.
    """
    if header is None:
        return None, "no header"
    for key in ("IM_SCALE", "SECPIX", "SECPIX1", "PIXSCALE", "SCALE",
                "PLTSCALE"):
        try:
            v = float(str(header.get(key, "")).strip() or "nan")
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and 0.01 < v < 3600.0:
            return v, key
    focal = None
    for key in ("FOCALLEN", "FOCAL"):
        try:
            v = float(str(header.get(key, "")).strip() or "nan")
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            focal = v
            break
    pix = None
    for key in ("XPIXSZ", "PIXSIZE1", "XPIXELSZ"):
        try:
            v = float(str(header.get(key, "")).strip() or "nan")
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            pix = v
            break
    if focal and pix:
        return 206.265 * pix / focal, "FOCALLEN and XPIXSZ"
    return None, ("no IM_SCALE/SECPIX and no FOCALLEN+XPIXSZ — Siril will "
                  "fall back to its saved defaults, which belong to "
                  "whatever telescope it solved last")


def scale_to_focal_pixel(arcsec_per_px: float, pixel_um: float = 9.0):
    """``(focal_mm, pixel_um)`` that reproduce a plate scale.

    Only the RATIO matters to a solver, so the pixel size is fixed at a
    plausible value and the focal length follows.  Handing Siril a
    consistent pair is what stops it reaching for the previous target's
    optics.
    """
    if not (arcsec_per_px and math.isfinite(arcsec_per_px)
            and arcsec_per_px > 0):
        return None, None
    return 206.265 * float(pixel_um) / float(arcsec_per_px), float(pixel_um)


def site_from_header(header):
    """Observatory position out of the FITS header, or None.

    Returns ``(lat_deg, lon_deg, height_m, source)``.

    Every frame carries this.  N.I.N.A. writes SITELAT / SITELONG /
    SITEELEV, and the run that prompted this had SITENAME "Starfront
    Building 8" sitting in all 178 subs while the script refused to
    convert times for want of a latitude nobody had typed in.  Asking the
    user to key in what the data already states is how a correct pipeline
    gets silently downgraded: the airmass detrend and the BJD_TDB
    conversion BOTH need this, and both had quietly switched themselves
    off.

    Longitude sign is the trap.  The FITS convention and astropy both take
    EAST as positive, and so does this function; a site at 99.4 W must
    read -99.38.  Nothing here can detect a file that got the sign wrong,
    so the value is reported back to the log for a human to recognise.
    """
    if header is None:
        return None
    def _num(*keys):
        for k in keys:
            if k in header:
                try:
                    v = float(header[k])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(v):
                    return v
        return None
    lat = _num("SITELAT", "LAT-OBS", "OBSGEO-B", "LATITUDE")
    lon = _num("SITELONG", "LONG-OBS", "OBSGEO-L", "LONGITUD")
    if lat is None or lon is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 360.0):
        return None
    if lon > 180.0:                       # 0..360 convention
        lon -= 360.0
    height = _num("SITEELEV", "ALT-OBS", "OBSGEO-H", "ELEVATIO") or 0.0
    name = str(header.get("SITENAME", "")).strip()
    where = f"FITS header ({name})" if name else "FITS header"
    return lat, lon, height, where


def to_bjd_tdb(jd_utc, ra_deg, dec_deg, lat_deg, lon_deg, height_m=0.0):
    """Convert JD_UTC mid-exposure times to BJD_TDB.

    Returns ``(bjd_array, note)`` on success, ``(None, reason)`` otherwise.

    Why this is not optional for a transit script.  Every published
    ephemeris -- ExoClock, ETD, the NASA Exoplanet Archive -- quotes T0 in
    BJD_TDB, and two separate corrections stand between that and the clock
    in the camera:

    * **Barycentric light travel**, up to +/-499 s (8.3 minutes) depending
      on where Earth sits in its orbit relative to the target.  This is the
      big one: eight minutes dwarfs the timing precision a transit run is
      trying to reach, so a T0 in JD_UTC cannot be compared with a
      published one at all.
    * **TDB - UTC**, currently about 69 s (32.184 s plus TAI-UTC), a
      near-constant offset that leap seconds step.

    Both are done here by astropy, which is already a hard dependency: the
    site position gives the diurnal term, the target direction gives the
    projection of Earth's orbital position onto the line of sight.

    Site height is a genuine input but a negligible one -- a kilometre of
    elevation is 3 microseconds of light travel -- so 0 m is a safe
    default rather than a reason to refuse.
    """
    if ra_deg is None or dec_deg is None:
        return None, ("no target RA/Dec, so the barycentric direction is "
                      "unknown")
    try:
        from astropy import units as u
        from astropy.coordinates import EarthLocation, SkyCoord
        from astropy.time import Time
    except Exception as exc:                          # pragma: no cover
        return None, f"astropy unavailable ({exc})"
    # The site only enters the diurnal light-travel term, +/-21 ms at
    # most.  Refusing the whole conversion for want of it threw away the
    # barycentric term (up to +/-8 min) and the 69 s of TDB-UTC, and
    # with them the O-C, the expected curve and the HOPS prior.  Without
    # a site the Earth's centre stands in, and the note says so.
    geocentric = lat_deg is None or lon_deg is None
    try:
        if geocentric:
            site = EarthLocation.from_geocentric(0.0, 0.0, 0.0, unit=u.m)
        else:
            site = EarthLocation(lat=float(lat_deg) * u.deg,
                                 lon=float(lon_deg) * u.deg,
                                 height=float(height_m) * u.m)
        times = Time(np.asarray(jd_utc, dtype=float), format="jd",
                     scale="utc", location=site)
        target = SkyCoord(ra=float(ra_deg) * u.deg,
                          dec=float(dec_deg) * u.deg, frame="icrs")
        ltt = times.light_travel_time(target, "barycentric")
        bjd = (times.tdb + ltt).jd
    except Exception as exc:
        return None, f"astropy refused the conversion ({exc})"
    bjd = np.asarray(bjd, dtype=float)
    shift_s = float(np.median(bjd - np.asarray(jd_utc, dtype=float))) * 86400.0
    return bjd, (f"BJD_TDB = JD_UTC {shift_s:+.1f} s "
                 "(barycentric light travel + TDB-UTC"
                 + ("; geocentric — no site given, at most 21 ms off)"
                    if geocentric else ")"))


def red_noise_beta(t, resid, duration_days):
    """The Pont/Zucker/Queloz beta factor: how far from white the noise is.

    Returns ``(beta, rows)`` with ``beta >= 1`` and ``rows`` a list of
    ``(width_days, beta_at_that_width, n_bins, mean_points_per_bin)`` for
    the report.

    Why a transit script cannot skip this.  Every significance in this
    file scales as sqrt(N) -- ``stacked_significance`` uses
    sqrt(N_in*N_out/(N_in+N_out)) -- and that scaling is only valid if the
    points are INDEPENDENT.  Ground-based transit photometry is famously
    not: seeing, transparency, flat-field error as the star drifts across
    the sensor, and colour-dependent extinction all vary on timescales of
    minutes to hours, which is exactly the timescale a transit lives on.
    Averaging correlated points does not beat the noise down by sqrt(N),
    so an uncorrected significance is an overstatement -- and it is an
    overstatement precisely where the systematic looks most like a
    transit.

    The measurement is Pont, Zucker & Queloz (2006): bin the residuals on
    a range of timescales; for white noise the scatter of the bin means
    falls as sigma_1/sqrt(n), so the ratio of what is observed to what is
    expected is 1.  Anything above 1 is correlated noise, and the
    significance is divided by it.

    The ladder of widths is tied to the fitted DURATION rather than to
    fixed minutes: the noise that matters is the noise on the timescale
    of the feature being claimed.

    The estimator has real scatter, and knowing how much is what makes
    the number readable.  Measured over 400 pure-white-noise runs of 240
    points (bins of 4 to 18 per rung): mean beta 1.09, 90th percentile
    1.29, 31 % of runs above 1.1 -- a Pont estimator with that few bins
    has ~35 % sampling error per rung, and the clamp at 1 turns symmetric
    noise into a one-sided excess.  Averaging over shifted bin grids,
    weighting rungs, or gating at one sigma were all tried and move the
    mean by less than 0.03, so the scatter is accepted rather than
    disguised: on a clean night the bars run ~9 % wide on average and
    30 % wide one night in ten, always in the safe direction, and AR(1)
    noise of rho 0.5 / 0.8 still reads 1.6 / 2.6.  A single beta near
    1.3 on visibly clean data is therefore a fluctuation, not a verdict.
    Across 60 real-transit runs NOT ONE detection was pushed below the
    3-sigma floor by this correction, while a false positive on pure
    noise was.  The correction costs detections
    Clamped at 1 by construction -- this correction may only ever make a
    detection weaker.  A beta below 1 means the residuals bin down FASTER
    than white noise, which is a small-sample fluctuation, not evidence
    that the data are better than Poisson allows.
    """
    r = np.asarray(resid, dtype=float)
    tt = np.asarray(t, dtype=float)
    ok = np.isfinite(r) & np.isfinite(tt)
    r, tt = r[ok], tt[ok]
    if r.size < RED_NOISE_MIN_POINTS or not math.isfinite(duration_days) \
            or duration_days <= 0:
        return 1.0, []
    # Robust, like every other scatter in this file.  `np.std` was used
    # here and nowhere else, and it defeats the whole point: three
    # satellite trails inflate sigma1 by 2.1x, which DIVIDES beta by the
    # same factor and switches the red-noise correction off exactly when
    # the data are bad enough to need it.  Measured on 150 points at 4
    # mmag: std 3.75 -> 8.16 mmag with three 50 mmag outliers, MAD 3.80 ->
    # 3.84.
    sigma1 = _mad_std(r)
    if not math.isfinite(sigma1) or sigma1 <= 0:
        return 1.0, []
    span = float(tt.max() - tt.min())
    rows = []
    for frac in RED_NOISE_WIDTH_FRACTIONS:
        width = duration_days * frac
        if width <= 0 or width > 0.5 * span:
            continue
        # With 4-8 bins per width a single binning has ~35 % sampling
        # error; the median of four such rungs, clamped at 1, read 1.09
        # on average and above 1.3 on a tenth of pure-noise runs.  The
        # bin grid is slid by width/k for k phases and the ratios
        # averaged: same data, more bin means, half the scatter.
        def _one_phase(shift):
            idx = np.floor((tt - tt.min() + shift) / width).astype(int)
            means, counts = [], []
            for b in np.unique(idx):
                sel = idx == b
                k = int(sel.sum())
                if k >= 2:                     # a one-point "bin" is not a mean
                    means.append(float(r[sel].mean()))
                    counts.append(k)
            n_bins = len(means)
            if n_bins < RED_NOISE_MIN_BINS:
                return None
            n_mean = float(np.mean(counts))
            # `observed` stays a plain standard deviation while sigma1 is
            # robust, and the asymmetry is deliberate.  On clean data the two
            # agree, so beta is unbiased.  On data with an outlier, the outlier
            # raises the bin mean it lands in -- so it enters `observed` -- but
            # not the robust sigma1, and beta goes UP.  That is the direction a
            # safety net should fail in.  A MAD over four to eight bin means
            # would be too noisy to use.
            observed = float(np.std(means, ddof=1))
            # The expected scatter of the SET of bin means, not of a typical
            # bin mean.  Bin i has variance sigma1^2 / k_i, so the mean variance
            # across bins is sigma1^2 * mean(1/k) -- NOT sigma1^2 / mean(k),
            # which is what this used to compute.  Jensen's inequality makes
            # the two differ whenever the bins are unequally filled, and always
            # in the same direction: measured 0% apart on equal bins, 55% on
            # [2,4,8,16,32] and 86% on [2,2,2,30].
            #
            # c4(M) is the small-sample correction: E[std(x, ddof=1)] is
            # BELOW the true sigma by that factor, so every short ladder rung
            # reads low and beta is biased toward "the noise is fine".  The
            # first version multiplied expected by sqrt(M/(M-1)) instead --
            # the WRONG DIRECTION, deflating beta further.  Measured on 40000
            # white-noise draws per M: uncorrected rungs average 0.92-0.98,
            # the sqrt factor drove them to 0.80-0.94, c4 lands on
            # 0.997-0.999.  A deflated beta overstates every significance on
            # exactly the nights the correction exists for.
            c4 = (math.sqrt(2.0 / (n_bins - 1))
                  * math.gamma(n_bins / 2.0)
                  * (1.0 / math.gamma((n_bins - 1) / 2.0)))
            expected = sigma1 * math.sqrt(float(np.mean(1.0 / np.asarray(
                counts, dtype=float)))) * c4
            if expected > 0:
                return observed / expected, n_bins, n_mean
            return None

        got = [_one_phase(width * ph / RED_NOISE_PHASES)
               for ph in range(RED_NOISE_PHASES)]
        got = [g for g in got if g is not None]
        if got:
            rows.append((width, float(np.mean([g[0] for g in got])),
                         int(round(np.mean([g[1] for g in got]))),
                         float(np.mean([g[2] for g in got]))))
    if not rows:
        return 1.0, []
    # The MEDIAN across the ladder, not the maximum: one noisy rung with
    # few bins should not set the correction for the whole run.
    beta = float(np.median([b for _w, b, _n, _k in rows]))
    return max(1.0, beta), rows


def full_scale_of(data) -> float:
    """The value that counts as "clipped" for this array's type.

    Siril hands back integers in their native range and floats normalised
    to [0, 1].  A float array whose peak is far above 1 is neither, so its
    own maximum is used and the answer becomes relative -- worse than
    knowing the ADC range, better than declaring an arbitrary threshold.
    """
    dtype = getattr(data, "dtype", None)
    if dtype is not None and dtype.kind in "ui":
        return float(np.iinfo(dtype).max)
    peak = float(np.nanmax(data)) if getattr(data, "size", 0) else 1.0
    return 1.0 if peak <= 1.5 else peak


def _sat_fraction(why: str):
    """The measured peak as a fraction of full scale, from the verdict text.

    `saturation_verdict` writes "(2.6% of full scale)" and that number is
    what decides whether Siril's flag gets the benefit of the doubt.  Read
    back out of the message rather than threaded through a second return
    value, so the two can never describe different things -- a test pins
    the round trip.
    """
    m = re.search(r"\(([\d.]+)% of full scale\)", str(why or ""))
    if not m:
        return None
    try:
        return float(m.group(1)) / 100.0
    except ValueError:
        return None


def saturation_verdict(data, x: float, y: float,
                       half: int = SATURATION_BOX_PX):
    """Is the star at ``(x, y)`` clipped?  ``(saturated, evidence)``.

    Read from the PIXELS, not from Siril's ``has_saturated`` flag.  The
    flag is right on the raw 16-bit frames and stops firing once the frames
    have been calibrated to 32-bit float -- the saturation is unchanged,
    the warning simply disappears, and the run then reports a 4% yield with
    no cause attached.  Measured on a real pair: raw peak 65532 of 65535
    inside the box, calibrated peak 1.000 of 1.0, flag set in the first
    case and not in the second.

    Returns ``(None, reason)`` when the data cannot be read at all.
    """
    if data is None or not getattr(data, "size", 0):
        return None, "no pixel data"
    arr = np.asarray(data)
    if arr.ndim > 2:
        arr = arr[0]
    h, w = arr.shape[-2], arr.shape[-1]
    xi, yi = int(round(float(x))), int(round(float(y)))
    if not (0 <= xi < w and 0 <= yi < h):
        return None, f"target ({xi}, {yi}) lies outside the {w}x{h} frame"
    box = arr[max(0, yi - half):yi + half + 1,
              max(0, xi - half):xi + half + 1]
    if not box.size:
        return None, "empty box around the target"
    peak = float(np.nanmax(box))
    full = full_scale_of(arr)
    frac = peak / full if full else 0.0
    return (frac >= SATURATION_FRACTION,
            f"peak {peak:.6g} of {full:.6g} ({100.0 * frac:.1f}% of full "
            f"scale) within {half} px of the target")


def oc_lines(r, fit):
    """The O-C block, or an empty list.  ``(plain, html)`` per entry.

    A light curve on its own says a transit happened.  O-C says whether
    the published ephemeris still predicts it, and that is what a single
    night is actually worth contributing -- it is the number ExoClock and
    ETD collect.  Until now this script measured T0 with a calibrated
    error bar and had nothing to compare it against.

    Refused unless the times are BJD_TDB.  The archive's T0 is BJD_TDB;
    subtracting a JD_UTC from it would put an 8-minute offset into a
    quantity whose whole interest is minutes.
    """
    eph = (r or {}).get("ephemeris") or {}
    if not fit or not eph.get("period_d") or not eph.get("t0_bjd"):
        return []
    if r.get("time_system") != "BJD_TDB":
        return [("   O-C            not computed — the times are "
                 f"{r.get('time_system')}, and the archive ephemeris is "
                 "BJD_TDB; the difference would be an 8-minute error in a "
                 "number measured in minutes.", None)]
    drift, epoch = o_minus_c(float(fit["t0"]), float(eph["t0_bjd"]),
                             float(eph["period_d"]))
    if drift is None:
        return []
    sig_s = fit.get("t0_sigma_s", float("nan"))
    sig_min = sig_s / 60.0 if np.isfinite(sig_s) else float("nan")
    bar = f" +/- {sig_min:.1f} min" if np.isfinite(sig_min) else ""
    verdict = ""
    if np.isfinite(sig_min) and sig_min > 0:
        n_sig = abs(drift) / sig_min
        verdict = (f"  ({n_sig:.1f} sigma from the prediction)" if n_sig >= 1.0
                   else "  (consistent with the prediction)")
    out = [(f"   O-C            {drift:+.2f} min{bar}{verdict}", None),
           (f"                  epoch {epoch} of {eph.get('name', '?')}, "
            f"P = {eph['period_d']:.6f} d", None)]
    if abs(drift) > 60.0:
        out.append(("                  more than an hour off — over "
                    f"{epoch} epochs a stale period eventually mislabels "
                    "which transit this was, so check the epoch before "
                    "reading anything into the drift", None))
    return out


def photometry_yield_note(n_points: int, n_frames: int,
                          target_saturated: bool,
                          engine: str = "Siril"):
    """Say whether Siril kept enough frames, and name the likely cause.

    Returns (severity, message) with severity in {"ok", "warn", "bad"},
    or ("ok", None) when the yield is fine.

    Siril's own reason codes are the evidence.  "pixel out of range" is
    PSF_ERR_INVALID_PIX_VALUE -- a pixel inside the aperture is saturated
    or out of the valid range.  It is NOT a positioning error, and that
    distinction matters: on the first real WASP-75b run 143 of 178 frames
    were dropped that way, which reads like a tracking or registration
    problem and is actually an exposure problem.  A saturated core does
    not scale with flux, so the frames that DO pass are the ones where
    seeing happened to spread the star out -- a seeing-dependent
    selection, which is the worst possible sampling for a transit.
    """
    if n_frames <= 0:
        return "bad", "no frames were measured at all."
    frac = n_points / float(n_frames)
    if frac >= POOR_YIELD_FRACTION and not target_saturated:
        return "ok", None
    # The message names whichever engine actually measured.  It used to
    # say "Siril kept..." unconditionally, and the first full native run
    # printed "83 points measured by this script" immediately followed by
    # "Siril kept 83 of 178" -- two sentences about the same numbers
    # attributing them to different programs.
    lines = [f"{engine} kept {n_points} of {n_frames} frames "
             f"({100.0 * frac:.0f}%)."]
    if target_saturated:
        drop = ("Siril drops a frame whose aperture holds a saturated "
                "pixel (\"pixel out of range\")"
                if engine == "Siril" else
                "This script drops a frame whose target core is clipped")
        lines.append(
            f"The target is SATURATED in the reference frame. {drop}, "
            "and a saturated core carries no flux information "
            "anyway. Worse, the frames that survive are the ones where "
            "seeing spread the star out — so what is left is a "
            "seeing-selected subset, not a fair sample of the night.")
        lines.append(
            "This is an exposure problem, not a processing one: shorten "
            "the sub-exposure or stop down until the target peaks below "
            "about half of full well.")
    elif frac < POOR_YIELD_FRACTION:
        lines.append(
            "Below half, the curve samples the night unevenly and the "
            "detection statistics below are optimistic."
            + (" Check Siril's own reasons above — \"pixel out of range\" "
               "means saturation, \"not in area\" means the star left "
               "the search box." if engine == "Siril" else
               " The per-frame reasons are counted in the lines above."))
    return ("bad" if frac < 0.33 or target_saturated else "warn",
            " ".join(lines))


def light_curve_args(seq: str, channel: int, autoring: bool,
                     target_xy, comps):
    """Build the `light_curve` command line.

    The coordinates go in as INTEGERS.  Siril parses `-at=`/`-refat=`
    with an integer reader that stops at the first character which is
    neither digit nor comma, so `-at=1503.646,1505.257` is rejected on
    the decimal point -- and it is rejected AFTER `-autoring` has been
    read, so the log shows the ring radii being set and then a bare
    "invalid arguments", which points at the wrong end of the command.

    Rounding costs nothing: `light_curve` re-fits the PSF in a box around
    whatever position it is given, so half a pixel in the seed is
    irrelevant to the centre it actually measures.
    """
    args = ["light_curve", seq, str(int(channel))]
    if autoring:
        # NOT `-autoring`.  Measured against Siril 1.4.4: passing the flag
        # makes `light_curve` abort with "The given coordinates are not in
        # the image" on coordinates that are demonstrably inside it -- the
        # same command without the flag, on the same sequence and the same
        # stars, produces the light curve.  The caller sets the identical
        # radii with `setphot` beforehand instead; the factors are Siril's
        # own and reproduce its arithmetic exactly (it logs "ring radii to
        # 7.5 and 11.3 (FWHM is 1.797542)" -- 4.2x and 6.3x to the digit).
        pass
    args.append(f"-at={int(round(float(target_xy[0])))},"
                f"{int(round(float(target_xy[1])))}")
    for comp in comps:
        args.append(f"-refat={int(round(float(comp[0])))},"
                    f"{int(round(float(comp[1])))}")
    return args


def _any_solved(stars) -> bool:
    """True when at least one star carries sky coordinates.

    `findstar` fills ra/dec from the image WCS, so zero across hundreds of
    stars means no astrometric solution -- not a marginal one.
    """
    for st in stars or []:
        if (abs(float(getattr(st, "ra", 0.0) or 0.0)) > 1e-9
                or abs(float(getattr(st, "dec", 0.0) or 0.0)) > 1e-9):
            return True
    return False


def classify_kind(imagetyp: str):
    """A frame kind from an ``IMAGETYP`` value, or ``None``.

    Substring matching, because the keyword is a type name: "Light Frame",
    "Flat Field" and "Dark Frame" must all be recognised.  Order matters --
    "DARKFLAT" and "Dark Flat" contain both words, so the combined form is
    tested first or a dark-flat becomes a plain dark and gets subtracted
    from the lights.
    """
    h = (imagetyp or "").strip().lower()
    if not h:
        return None
    has_dark, has_flat = "dark" in h, "flat" in h
    if has_dark and has_flat:
        return KIND_DARKFLAT
    if has_flat:
        return KIND_FLAT
    if has_dark:
        return KIND_DARK
    if "bias" in h or "offset" in h:
        return KIND_BIAS
    if "light" in h or "object" in h or "science" in h:
        return KIND_LIGHT
    return None


def classify_path(path: str):
    """A frame kind from the folder names, for files with no ``IMAGETYP``.

    WHOLE path segments, never substrings: a target called "Dark-Nebula" or
    "Flaming Star" must not have its lights read as calibration frames.
    N.I.N.A. writes the type as its own folder, in capitals, so the
    comparison is case-folded -- a case-sensitive one would never match.
    """
    seg = {p.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
           for p in os.path.normpath(path).split(os.sep)}
    if seg & {"darkflat", "flatdark", "darkflats", "flatdarks"}:
        return KIND_DARKFLAT
    if seg & {"flat", "flats"}:
        return KIND_FLAT
    if seg & {"dark", "darks"}:
        return KIND_DARK
    if seg & {"bias", "biases", "offset", "offsets"}:
        return KIND_BIAS
    if seg & {"light", "lights"}:
        return KIND_LIGHT
    return None


def inspect_frame(path: str, header=None) -> dict:
    """One header read, everything discovery and matching need.

    ``IMAGETYP`` is authoritative and the folder layout is the fallback --
    that order and not the reverse, because a keyword written by the
    capture program knows what the frame is and a folder only says where
    somebody filed it.
    """
    out = {"path": path, "kind": None, "exp_s": None, "gain_v": None,
           "temp_v": None, "binning": 1, "dims": None, "instrument": None,
           "filter": "", "date_obs": "", "date_loc": "", "object": "",
           "objctra": "", "objctdec": "", "datamax": None}
    h = header if header is not None else _read_header(path)
    if h is None:
        out["kind"] = classify_path(path)
        return out
    out["kind"] = (classify_kind(str(h.get("IMAGETYP", "") or ""))
                   or classify_path(path))
    out["filter"] = str(h.get("FILTER", "") or "").strip()
    out["object"] = str(h.get("OBJECT", "") or "").strip()
    out["objctra"] = str(h.get("OBJCTRA", "") or "").strip()
    out["objctdec"] = str(h.get("OBJCTDEC", "") or "").strip()
    out["date_obs"] = str(h.get("DATE-OBS", h.get("DATE_OBS", "")) or "").strip()
    # N.I.N.A.'s local-clock twin of DATE-OBS: the pair yields the site's
    # UTC offset, so the chart can label its axis in the same wall-clock
    # time the user's planning tool speaks.
    out["date_loc"] = str(h.get("DATE-LOC", h.get("DATE_LOC", "")) or "").strip()
    # Mid- and end-of-exposure stamps where the capture program writes
    # them (N.I.N.A.: DATE-AVG); they settle what DATE-OBS means.
    out["date_avg"] = str(h.get("DATE-AVG", h.get("DATE_AVG", h.get(
        "DATE-MID", ""))) or "").strip()
    out["date_end"] = str(h.get("DATE-END", h.get("DATE_END", "")) or "").strip()
    out["instrument"] = str(h.get("INSTRUME", "") or "").strip() or None
    for key in ("EXPTIME", "EXPOSURE"):
        if key in h:
            try:
                out["exp_s"] = float(h[key])
            except (TypeError, ValueError):
                pass
            break
    for key in ("DATAMAX", "SATURATE", "MAXADU"):
        if key in h:
            try:
                out["datamax"] = float(h[key])
            except (TypeError, ValueError):
                pass
            break
    for key in ("GAIN", "EGAIN"):
        if key in h:
            try:
                out["gain_v"] = float(h[key])
            except (TypeError, ValueError):
                pass
            break
    for key in ("CCD-TEMP", "CCDTEMP", "SET-TEMP"):
        if key in h:
            try:
                out["temp_v"] = float(h[key])
            except (TypeError, ValueError):
                pass
            break
    for key in ("XBINNING", "BINNING", "XBIN"):
        if key in h:
            try:
                out["binning"] = int(float(h[key]))
            except (TypeError, ValueError):
                pass
            break
    try:
        out["dims"] = (int(h.get("NAXIS1", 0)), int(h.get("NAXIS2", 0)))
    except (TypeError, ValueError):
        pass
    return out


def calib_signature(info: dict, with_temp: bool = False) -> tuple:
    """Grouping key: what must agree before two frames share a master.

    ``with_temp`` is required for DARKS -- dark current is a function of
    temperature, so averaging a -10 C and a -20 C frame gives a master that
    is correct for neither.  BIAS is read noise only and essentially
    temperature-independent, so splitting it would just make every master
    noisier for nothing.

    The camera is part of the key.  Without it two bodies of the same model
    -- same size, same gain, same binning -- land in one group and get
    averaged together before anything checks whether they belong.
    """
    temp = info.get("temp_v")
    return (round(float(info.get("exp_s") or 0.0), 3),
            info.get("gain_v"),
            info.get("binning", 1),
            info.get("dims"),
            (round(float(temp)) if with_temp and temp is not None else None),
            info.get("instrument") or None)


def signature_matches(master: dict, target: dict, check_exposure=True):
    """``(ok, why)`` -- may ``master`` calibrate frames like ``target``?

    A missing gain, temperature or size is "unknown, don't block": refusing
    a usable master because a keyword is absent would be worse than the
    mismatch it guards against.  Exposure is the exception for darks, where
    3 s against 60 s is exactly the mismatch that must not slip through.

    Returns the reason as well as the verdict, because a master that was
    found and then rejected is the case where silence hurts most -- the run
    would look identical to one where no master existed at all.
    """
    mi, ti = master.get("instrument"), target.get("instrument")
    if mi and ti and mi != ti:
        return False, f"different camera ({mi} vs {ti})"
    md, td = master.get("dims"), target.get("dims")
    if md and td and md != td:
        return False, f"different image size ({md} vs {td})"
    if master.get("binning", 1) != target.get("binning", 1):
        return False, (f"different binning ({master.get('binning')} vs "
                       f"{target.get('binning')})")
    mg, tg = master.get("gain_v"), target.get("gain_v")
    if mg is not None and tg is not None and mg != tg:
        return False, f"different gain ({mg:g} vs {tg:g})"
    mt, tt = master.get("temp_v"), target.get("temp_v")
    if mt is not None and tt is not None \
            and abs(mt - tt) > CALIB_TEMP_TOLERANCE_C:
        return False, f"different temperature ({mt:g} C vs {tt:g} C)"
    if check_exposure:
        me, te = master.get("exp_s"), target.get("exp_s")
        if me is None or te is None:
            return False, "exposure time unknown on one side"
        if abs(float(me) - float(te)) > 0.01:
            return False, f"different exposure ({me:g} s vs {te:g} s)"
    return True, "matches"


def calibration_roots(lights_dir: str, library: str = "",
                      levels: int = CALIB_SEARCH_LEVELS) -> list:
    """Folders worth scanning for calibration frames, nearest first.

    N.I.N.A. files a session as ``<target>/LIGHT/<date>/<filter>/``, which
    puts the flats three levels up beside the LIGHT folder rather than
    anywhere near the lights themselves.  So this walks UP from the lights
    and, at each ancestor, takes any immediate child that classifies as a
    calibration folder.

    Only calibration folders are returned, never a whole ancestor: walking
    up four levels from a subs folder can reach a directory holding every
    project on the disk, and scanning that would read thousands of headers
    to find nothing.
    """
    roots, seen = [], set()

    def _add(path):
        real = os.path.realpath(path)
        if real not in seen and os.path.isdir(real):
            seen.add(real)
            roots.append(path)

    node = os.path.abspath(lights_dir)
    for _ in range(max(0, int(levels)) + 1):
        try:
            children = sorted(os.listdir(node))
        except OSError:
            children = []
        for name in children:
            child = os.path.join(node, name)
            if not os.path.isdir(child):
                continue
            if classify_path(name) in (KIND_FLAT, KIND_DARK, KIND_BIAS,
                                       KIND_DARKFLAT):
                _add(child)
        parent = os.path.dirname(node)
        if parent == node:
            break
        node = parent
    if library:
        _add(library)
    return roots


def group_calibration(infos, want_filter: str = "") -> dict:
    """``{kind: [group, ...]}`` from frames whose headers were already read.

    A group is ``{"kind", "key", "files", "info"}`` -- every frame that may
    share one master, with the header of the first as the group's metadata.
    Darks and dark-flats are split by temperature, bias is not; see
    `calib_signature`.

    ``want_filter`` restricts FLATS to the filter the lights were taken
    through.  Flats are filter-specific and nothing else here is: a dark
    taken with the wheel in any position is still a dark.  A flat whose
    header names no filter is kept rather than dropped -- older capture
    programs omit the keyword, and refusing those would leave a rig with
    one filter unable to find its own flats.
    """
    groups: dict = {}
    for info in infos or []:
        kind = info.get("kind")
        if kind not in (KIND_FLAT, KIND_DARK, KIND_BIAS, KIND_DARKFLAT):
            continue
        if kind == KIND_FLAT and want_filter:
            got = (info.get("filter") or "").strip()
            if got and got.lower() != want_filter.strip().lower():
                continue
        key = (kind, calib_signature(
            info, with_temp=kind in (KIND_DARK, KIND_DARKFLAT)))
        grp = groups.get(key)
        if grp is None:
            grp = {"kind": kind, "key": key, "files": [], "info": info}
            groups[key] = grp
        grp["files"].append(info["path"])
    out: dict = {}
    for grp in groups.values():
        out.setdefault(grp["kind"], []).append(grp)
    for kind in out:
        out[kind].sort(key=lambda g: len(g["files"]), reverse=True)
    return out


def merge_calibration(*group_dicts) -> dict:
    """Fold several ``{kind: [group]}`` maps into one, joining equal keys.

    Frames of the same signature found in two places -- inside your
    selection and in the library -- are one group, not two competing ones.
    """
    merged: dict = {}
    for gd in group_dicts:
        for kind, groups in (gd or {}).items():
            for grp in groups:
                hit = None
                for have in merged.setdefault(kind, []):
                    if have["key"] == grp["key"]:
                        hit = have
                        break
                if hit is None:
                    merged[kind].append(dict(grp, files=list(grp["files"])))
                else:
                    for f in grp["files"]:
                        if f not in hit["files"]:
                            hit["files"].append(f)
    for kind in merged:
        for grp in merged[kind]:
            grp["files"].sort()
        merged[kind].sort(key=lambda g: len(g["files"]), reverse=True)
    return merged


def split_frames(infos, inside: bool = True) -> tuple:
    """``(lights, calibration, note)`` from a batch of inspected frames.

    A frame with no recognisable kind is a LIGHT when it came from the
    folder you selected -- you pointed at it, and older capture programs
    write no IMAGETYP -- and is DISCARDED when it came from a sibling or
    library folder, where an unlabelled frame is not something to guess
    about.

    Lights are then reduced to one coherent set: same filter, same
    exposure.  A light curve compares a star against itself over time, so a
    filter change or an exposure change mid-run is not a longer series, it
    is two series that must not be concatenated.  The largest set wins and
    the note names what was set aside.
    """
    lights, calib, unlabelled = [], [], 0
    for info in infos or []:
        kind = info.get("kind")
        if kind == KIND_LIGHT:
            lights.append(info)
        elif kind in (KIND_FLAT, KIND_DARK, KIND_BIAS, KIND_DARKFLAT):
            calib.append(info)
        elif kind is None:
            unlabelled += 1
            if inside:
                lights.append(info)
    if not lights:
        return [], calib, ("no light frames" if not unlabelled else "")

    # The same exposure cannot legitimately appear twice in one series, so
    # a repeated DATE-OBS is a copy: a stale working folder, a backup, a
    # second convert.  Found the hard way -- a leftover working folder from
    # an earlier run of this very script turned 178 subs into 534, and
    # every duplicate would have entered the light curve as an independent
    # point, shrinking every error bar by root-3 for nothing.
    #
    # Sorted-first wins, which is deterministic and, because a working
    # folder is normally named to sort after the frames it copied, usually
    # keeps the original.
    seen, unique, dupes = set(), [], 0
    for info in sorted(lights, key=lambda i: i["path"]):
        stamp = (info.get("date_obs") or "").strip()
        # A stamp coarser than the cadence (whole seconds on sub-second
        # exposures) is shared by REAL frames; only a stamp finer than
        # the exposure can name a copy.
        try:
            _exp = float(info.get("exp_s") or 0.0)
        except (TypeError, ValueError):
            _exp = 0.0
        if stamp and 0.0 < _exp < 1.0 and "." not in stamp[11:]:
            stamp = ""
        if stamp:
            if stamp in seen:
                dupes += 1
                continue
            seen.add(stamp)
        unique.append(info)
    lights = unique
    dupe_note = (f"{dupes} duplicate frame(s) dropped — same DATE-OBS as a "
                 f"frame already found, so a copy rather than an exposure. "
                 if dupes else "")

    buckets: dict = {}
    for info in lights:
        key = ((info.get("filter") or "").strip().upper(),
               round(float(info.get("exp_s") or 0.0), 3))
        buckets.setdefault(key, []).append(info)
    if len(buckets) == 1:
        note = dupe_note
        if unlabelled and inside:
            note += (f"{unlabelled} frame(s) carry no IMAGETYP and were "
                     f"taken as lights.")
        return lights, calib, note.strip()

    best = max(buckets.items(), key=lambda kv: len(kv[1]))
    dropped = sorted(((k, len(v)) for k, v in buckets.items() if k != best[0]),
                     key=lambda kv: -kv[1])
    def _name(key):
        filt, exp = key
        return f"{filt or 'no filter'} @ {exp:g}s"
    note = (dupe_note
            + f"{len(best[1])} frame(s) at {_name(best[0])} kept; set aside: "
            + ", ".join(f"{n} at {_name(k)}" for k, n in dropped)
            + ". A filter or exposure change mid-run is two series, not a "
              "longer one.")
    return best[1], calib, note


def scan_calibration(roots, want_filter: str = "", read=None) -> dict:
    """``{kind: [group, ...]}`` from the folders in ``roots``.

    A group is ``{"kind", "key", "files", "info"}`` -- every frame that may
    share one master, with the header of the first as the group's own
    metadata.  Darks and dark-flats are split by temperature, bias is not;
    see `calib_signature`.

    ``want_filter`` restricts FLATS to the filter the lights were taken
    through.  Flats are filter-specific and nothing else here is: a dark
    taken with the wheel in any position is still a dark.  A flat whose
    header names no filter is kept rather than dropped -- older capture
    programs omit the keyword, and refusing those would leave a rig with
    one filter unable to find its own flats.

    ``read`` is the header reader, injectable so the grouping can be
    tested without a disk full of FITS files.
    """
    reader = read or (lambda path: inspect_frame(path))
    infos = []
    for root in roots or []:
        for base, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(names):
                if _is_fits(name) and not name.startswith("."):
                    infos.append(reader(os.path.join(base, name)))
    return group_calibration(infos, want_filter)


def choose_masters(groups: dict, light_info: dict) -> tuple:
    """``(chosen, notes)`` -- which group to use for each kind, and why.

    ``chosen`` maps ``dark`` / ``flat`` / ``offset`` to a group.  ``notes``
    is one line per kind, including the ones that found nothing and the
    ones that found something and rejected it -- a master that was there
    and did not match is exactly the case where silence misleads, because
    the run then looks identical to one where no master existed.

    Two rules that are not obvious:

    * **Bias is never applied together with a dark.**  The dark already
      contains the offset, so subtracting both removes it twice.  The bias
      is still used, but for the FLATS: Lc = (L - D) / (F - O).
    * **The flat does not have to match the lights' exposure.**  A flat is
      a ratio; its own exposure says nothing about the lights.  Only its
      camera, size, binning and filter matter.
    """
    chosen, notes = {}, []

    dark = None
    for grp in groups.get(KIND_DARK, []):
        ok, why = signature_matches(grp["info"], light_info)
        if ok:
            dark = grp
            notes.append(f"dark: {len(grp['files'])} frame(s), {why}")
            break
        if "exposure" in why:
            # The terse signature reason is right but says nothing about the
            # consequence, and the consequence is the whole point.
            _ok, why = dark_exposure_note({"EXPTIME": grp["info"].get("exp_s")},
                                          {"EXPTIME": light_info.get("exp_s")})
        notes.append(f"dark REJECTED ({len(grp['files'])} frame(s)): {why}")
    if dark is None and not groups.get(KIND_DARK):
        notes.append("dark: none found")
    if dark is not None:
        chosen["dark"] = dark

    flat = None
    for grp in groups.get(KIND_FLAT, []):
        ok, why = signature_matches(grp["info"], light_info,
                                    check_exposure=False)
        if ok:
            flat = grp
            notes.append(f"flat: {len(grp['files'])} frame(s), {why}")
            break
        notes.append(f"flat REJECTED ({len(grp['files'])} frame(s)): {why}")
    if flat is None and not groups.get(KIND_FLAT):
        notes.append("flat: none found")
    if flat is not None:
        chosen["flat"] = flat

    # The flats' own offset: a dark-flat at the flats' exposure first, a
    # plain bias second.  Neither is applied to the lights.
    offset = None
    if flat is not None:
        for kind in (KIND_DARKFLAT, KIND_BIAS):
            for grp in groups.get(kind, []):
                ok, _why = signature_matches(
                    grp["info"], flat["info"],
                    check_exposure=(kind == KIND_DARKFLAT))
                if ok:
                    offset = grp
                    notes.append(f"flat offset: {kind}, "
                                 f"{len(grp['files'])} frame(s)")
                    break
            if offset is not None:
                break
        if offset is None:
            notes.append("flat offset: none found — Siril's synthetic "
                         "offset will be used")
        else:
            chosen["offset"] = offset
    if groups.get(KIND_BIAS) and dark is not None:
        notes.append("bias found but NOT applied to the lights: the dark "
                     "already contains the offset, subtracting both would "
                     "remove it twice")
    return chosen, notes


def calibration_args(seq: str, bias=None, dark=None, flat=None,
                     cfa: bool = False, prefix: str = CALIB_PREFIX):
    """Siril's ``calibrate`` command line, or ``None`` when there is none.

    Returns ``(args, used)`` where ``used`` is the list of
    ``(kind, path)`` actually passed, so the caller can report what it did
    rather than claiming a calibration it did not perform.  With no master
    at all this returns ``(None, [])`` -- an empty ``calibrate`` call would
    still rewrite every frame, cost the disk, and change nothing.

    ``cfa`` adds ``-cfa -debayer`` for a one-shot-colour sensor.  Without
    it a Bayer frame would be flat-fielded across its own mosaic, which
    puts the CFA pattern into the flat correction.
    """
    used = []
    args = ["calibrate", seq]
    for kind, path in (("bias", bias), ("dark", dark), ("flat", flat)):
        if path:
            # The WHOLE token is quoted, not just the path: Siril's parser
            # keeps quotes that start after the "=" as part of the file
            # name and then reports `"...fit".[any_allowed_extension] not
            # found`, which reads like a missing file rather than a
            # quoting bug.
            args.append(f'"-{kind}={path}"')
            used.append((kind, path))
    if not used:
        return None, []
    if cfa:
        args += ["-cfa", "-debayer"]
    args.append(f"-prefix={prefix}")
    return args, used


def frames_are_calibrated(header):
    """``(state, evidence)`` -- ``True``, ``False`` or ``None`` for unknown.

    Three states rather than two because the honest answer is often "no
    idea".  ``CALSTAT`` is written by several capture programs and settles
    it; a HISTORY card mentioning the step settles it; N.I.N.A. writes
    neither, so a raw N.I.N.A. light and a calibrated one that lost its
    provenance look the same.  Saying ``False`` there would be a claim the
    header does not support, and a warning that cries wolf is one the user
    learns to skip past.
    """
    if header is None:
        return None, "no readable header"
    stat = str(header.get("CALSTAT", "") or "").strip().upper()
    if stat:
        done = [CALSTAT_LETTERS[c] for c in stat if c in CALSTAT_LETTERS]
        if done:
            return True, "CALSTAT=" + stat + " (" + ", ".join(done) + ")"
        return None, "CALSTAT=" + stat + ", which this does not recognise"
    try:
        history = [str(h).lower() for h in header.get("HISTORY", [])]
    except Exception:                       # noqa: BLE001 -- odd header card
        history = []
    for line in history:
        for word in CALIB_HISTORY_WORDS:
            if word in line:
                return True, "HISTORY: " + line.strip()
    if str(header.get("IMAGETYP", "") or "").strip().upper().startswith("LIGHT"):
        return False, "IMAGETYP=LIGHT with no CALSTAT and no HISTORY"
    return None, "nothing in the header either way"


def dark_exposure_note(dark_header, light_header):
    """Whether a dark matches the lights, as ``(ok, message)``.

    ``ok`` is ``None`` when either exposure is missing -- unknown is not
    the same as fine.  Takes anything with ``.get``, so `choose_masters`
    can hand it the numbers it already read rather than the file again.

    `signature_matches` also rejects on exposure, and correctly, but its
    reason is one clause long.  This is the version that says what the
    mismatch DOES, which is the part that changes what you go and shoot.
    """
    def _exp(h):
        if h is None:
            return None
        for key in ("EXPTIME", "EXPOSURE"):
            if key in h:
                try:
                    return float(h[key])
                except (TypeError, ValueError):
                    return None
        return None

    d, l = _exp(dark_header), _exp(light_header)
    if d is None or l is None:
        return None, ("Could not read the exposure time of the master dark "
                      "or of the lights, so the two were not compared.")
    if l > 0 and abs(d - l) / l <= DARK_EXPTIME_TOLERANCE:
        return True, f"Master dark matches the lights at {l:.1f} s."
    return False, (
        f"The master dark is {d:.1f} s but the lights are {l:.1f} s. Siril "
        f"subtracts it as it is: that removes {d / l * 100:.0f}% of the dark "
        f"current if it scales linearly, leaves the rest in, and adds the "
        f"dark's own read noise to every frame. Shoot darks at the light "
        f"exposure, or leave the dark out and let the flat do the work.")


def drift_envelope(homs, ref_shift=(0.0, 0.0), width=0, height=0):
    """``(dx_min, dx_max, dy_min, dy_max)`` across a run, or ``None``.

    Siril's `light_curve` moves each measurement box by the registration
    data, so a star that is comfortably inside the reference frame can
    still leave the sensor later in the night.  When that happens to a
    COMPARISON star the whole command fails -- "generic error", after a
    warning about "heavy drifted images" that names one frame and does not
    say which star.

    Measured on EXOTIC's demo set: dx runs +52 to -218 px on a 650 px
    frame, and three of the five comparisons chosen from the reference
    frame spend part of the run outside it.  The target happened to
    survive, which is why the failure looked like a photometry bug rather
    than a geometry one.
    """
    if width and height:
        pts = [p for p in shift_list(homs, width, height) if p is not None]
        if not pts:
            return None
        rx, ry = ref_shift
        return (min(x for x, _ in pts) - rx, max(x for x, _ in pts) - rx,
                min(y for _, y in pts) - ry, max(y for _, y in pts) - ry)
    dxs, dys = [], []
    for h in homs or ():
        if h is None:
            continue
        # sirilpy hands back an OBJECT with h00..h22 attributes, not an
        # array.  Reading it as an array is what made this return None on
        # its first outing: the filter then did nothing at all, and the
        # only symptom was that the drift line never appeared.  The
        # rotation check next door reads h00/h10, so this reads h02/h12
        # the same way, with the array form as a fallback for anything
        # that does hand back a plain 3x3.
        dx = dy = None
        if hasattr(h, "h02") and hasattr(h, "h12"):
            try:
                dx, dy = float(h.h02), float(h.h12)
            except (TypeError, ValueError):
                dx = dy = None
        if dx is None:
            try:
                arr = np.asarray(h, dtype=float).reshape(3, 3)
                dx, dy = float(arr[0, 2]), float(arr[1, 2])
            except (ValueError, TypeError):
                continue
        if not (math.isfinite(dx) and math.isfinite(dy)):
            continue
        # The measured convention (see ref_to_frame): a stored (h02, h12)
        # moves a star by (-h02, +h12) in FITS coordinates.  The first
        # version appended the raw values and the filter judged every
        # star by the MIRROR of its true excursion -- it kept (222, 73),
        # which walks to x = 4, and light_curve then failed on it.
        dxs.append(-dx)
        dys.append(dy)
    if not dxs:
        return None
    # Relative to the reference Siril is ACTUALLY using.  When the
    # reference is re-centred (see `best_reference`) every stored
    # homography still points at the old one, so subtracting the new
    # reference's own shift is what turns them into the offsets the
    # measurement boxes really travel.
    rx, ry = ref_shift
    return (min(dxs) - rx, max(dxs) - rx, min(dys) - ry, max(dys) - ry)


def _homography(h):
    """A homography as nine floats, or ``None``.

    sirilpy hands back an OBJECT with h00..h22 attributes; a plain 3x3 is
    accepted as well so the maths can be exercised without sirilpy.
    """
    if h is None:
        return None
    names = ("h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22")
    if all(hasattr(h, n) for n in names):
        try:
            return [float(getattr(h, n)) for n in names]
        except (TypeError, ValueError):
            return None
    try:
        arr = np.asarray(h, dtype=float).reshape(3, 3)
    except (ValueError, TypeError):
        return None
    return [float(v) for v in arr.ravel()]


def shift_list(homs, width=0, height=0):
    """Where the IMAGE CENTRE of each frame lands, ``None`` where unset.

    Reading the homography's translation column instead was wrong, and a
    MERIDIAN FLIP is what exposes it.  A 180-degree rotation about the
    centre leaves every star on the same piece of sky and moves nothing
    off the sensor, but its translation column is the width and height of
    the frame: measured on a real 3008x3008 run, hypot(h02, h12) = 4253 px
    while the centre moves 13.7 px.  Reported as drift, that number said
    "no reference can rescue this run" about a run that had no drift
    problem at all, and the whole photometry was thrown away.

    Sending the centre through the full 3x3 is right in both cases: for a
    pure shift it returns exactly the translation, and for the flip it
    returns the truth.  Without a frame size there is no centre, so the
    translation column is the fallback -- correct whenever the field does
    not rotate, which is the ordinary case.
    """
    cx, cy = float(width) / 2.0, float(height) / 2.0
    out = []
    for h in homs or ():
        m = _homography(h)
        if m is None:
            out.append(None)
            continue
        if width and height:
            pos = ref_to_frame(m, cx, cy, width, height)
            if pos is None:
                out.append(None)
                continue
            x, y = pos
        else:
            # No frame size, no flip axis: the translation column with
            # the measured signs, right whenever the field does not
            # rotate.
            x, y = -m[2], m[5]
        if math.isfinite(x) and math.isfinite(y):
            out.append((x, y))
        else:
            out.append(None)
    return out


def worst_drift(shifts, ref_index):
    """Largest distance any frame travels from frame ``ref_index``.

    This is the number Siril tests against its own limit -- verified: it
    reported "163 pixels for image 103" where hypot(dx, dy) is 162.5.
    """
    ref = shifts[ref_index] if 0 <= ref_index < len(shifts) else None
    if ref is None:
        return None
    rx, ry = ref
    d = [math.hypot(x - rx, y - ry) for s in shifts if s
         for x, y in (s,)]
    return max(d) if d else None


def best_reference(shifts, quality=None, limit=None):
    """``(index, worst_drift)``: the BEST FRAME that Siril will accept.

    Two constraints, and getting either one alone is wrong.

    Siril picks its registration reference on IMAGE QUALITY, which is the
    right criterion for stacking and not sufficient here: a reference near
    one end of a drifting run puts the ENTIRE drift on one side, and
    `light_curve` refuses above 160 px.  Measured on EXOTIC's demo set,
    Siril chose image 35 of 142 -- 263 stars, weighted FWHM 1.80, and a
    worst drift of 218.9 px.  Refused every time.

    Choosing on drift ALONE is just as wrong, and it fails quietly rather
    than loudly.  The frame at the exact middle of that drift is image 72,
    and image 72 is the worst frame of the night: weighted FWHM 8.50, 110
    stars against 262.  The command ran and the result was rubbish -- the
    sky annulus came out at 24.7 px instead of 11.3, the target was
    matched 200 arcsec from its catalogue position, and 6 of 142 frames
    survived photometry.

    So: take every frame Siril will accept, and among those take the best
    one.  Image 71 -- 147.7 px, 262 stars, weighted FWHM 2.42 -- is within
    a whisker of Siril's own pick on quality while staying inside the
    limit.  ``quality`` is one number per frame, lower is better (weighted
    FWHM); frames without one fall back to drift order.
    """
    usable = [i for i, sh in enumerate(shifts) if sh is not None]
    if not usable:
        return None, None
    scored = []
    for i in usable:
        d = worst_drift(shifts, i)
        if d is None:
            continue
        scored.append((i, d))
    if not scored:
        return None, None
    if limit is not None:
        allowed = [(i, d) for i, d in scored if d <= limit]
        if not allowed:
            # Nothing qualifies.  Hand back the least-bad so the caller can
            # report the actual number instead of a bare "no".
            return min(scored, key=lambda r: r[1])
        scored = allowed
    if quality:
        def rank(item):
            i, d = item
            q = quality[i] if i < len(quality) else None
            if q is None or not math.isfinite(q) or q <= 0.0:
                return (1, d)            # unmeasured sorts after measured
            return (0, q)
        return min(scored, key=rank)
    return min(scored, key=lambda r: r[1])


# -- native photometry --------------------------------------------------
#
# Siril's `light_curve` command re-runs its own PSF pass per star, moving
# each measurement box by the REGISTRATION alone.  On a drifting run that
# loses half the frames ("not in area", "PSF fit failed") -- measured:
# 67 of 140 points on EXOTIC's demo set, then 45 with a dynamic aperture,
# which added "inner radius too small" 83 times.  Siril's own `seqpsf
# -followstar` measures the SAME star on the SAME sequence with ZERO
# failures out of 142 -- the engine exists, but `light_curve` does not use
# it, its results are reachable neither from a file nor from sirilpy, and
# `light_curve` does not reuse them (measured: it re-ran its own six PSF
# passes right after six seqpsf runs).
#
# So the measurement is done here, the way EXOTIC and HOPS do it: Siril
# keeps everything it is good at -- staging, calibration, two-pass
# registration, star detection, plate solve, frame quality -- and this
# script reads the registered-but-unresampled frames once each,
# re-centroids every star per frame (that is what "follow star" is), and
# sums flux in a subpixel-weighted circular aperture against a
# sigma-clipped annulus sky.  All apertures are measured in the same pass,
# the ensemble is normalised per comp so a missing frame cannot step the
# baseline, and comps are kept or dropped by their MEASURED scatter --
# EXOTIC's criterion, computed here on point-to-point differences so a
# real transit in the target cannot penalise a comp.

CENTROID_BOX = 10          # half-size of the re-centroid box, px
CENTROID_ITERS = 2
CENTROID_MAX_SHIFT = 6.0   # px; a centroid further than this from its
                           # seed has locked onto a neighbour, and a wrong
                           # star measured confidently is worse than a
                           # missing frame
SUBPIXEL_GRID = 16         # NxN subsamples per pixel for aperture edges: at 8 the
                           # area wobbled 0.6 % with sub-pixel centre at r = 1.5 px
# EXOTIC scans 1.5-6 sigma (about 0.6-2.5 FWHM); on the demo set the
# point-to-point noise kept falling to the top of a grid that stopped at
# 2.0, so the grid reaches 2.5.
APERTURE_FWHM_GRID = (0.9, 1.1, 1.35, 1.6, 2.0, 2.5)
COMP_REJECT_FACTOR = 3.0   # a comp this many times noisier than its peers
                           # writes its wobble, inverted, into the target
NATIVE_MIN_YIELD = 0.30    # below this fraction of frames measured, the
                           # native engine distrusts itself and the Siril
                           # fallback runs instead
SAT_FRACTION = 0.98        # of full scale: the same clip criterion the
                           # saturation verdict uses
COMP_CLIP_HEADROOM = 0.7   # of the clip level: a comp whose reference
                           # peak already sits above this is one good-
                           # seeing frame away from clipping, and
                           # INTERMITTENT clipping is indistinguishable
                           # from variability -- the comp gets dropped,
                           # then rejected as variable, and the frames
                           # where the whole ensemble clipped together
                           # vanish from the curve without a word.
                           # Found on the first flat-calibrated run:
                           # Siril clamps calibrated floats to [0, 1],
                           # so the flat division (norm 0.432) pushed
                           # corner stars into the ceiling that their
                           # raw frames never touched.


def invert_homography(m):
    """The inverse of a 3x3 homography given as nine floats, or ``None``."""
    try:
        inv = np.linalg.inv(np.asarray(m, dtype=float).reshape(3, 3))
    except (np.linalg.LinAlgError, ValueError):
        return None
    return [float(v) for v in inv.ravel()]


def apply_homography(m, x, y):
    """``(x, y)`` sent through a 3x3 homography given as nine floats."""
    den = m[6] * x + m[7] * y + m[8]
    if abs(den) < 1e-12:
        return None
    return ((m[0] * x + m[1] * y + m[2]) / den,
            (m[3] * x + m[4] * y + m[5]) / den)


def ref_to_frame(hom, x, y, width, height):
    """Where a star at reference position ``(x, y)`` sits in this frame.

    The convention was MEASURED, not read from documentation, because two
    plausible readings both failed on real data: the stored homography
    maps FRAME onto REFERENCE, in Siril's bottom-up row order -- which is
    upside down relative to what astropy reads from the same file.  So:
    flip y, apply the INVERSE, flip back.

    Anchored on EXOTIC's demo set by cross-correlating whole frames
    against the reference and then confirming on the target star itself:
    frame 1 stores (h02, h12) = (-52.0, -37.4) and the star sits at
    ref + (+52, -37); frame 140 stores (+218.2, -17.3) and the star sits
    at ref + (-218, -17).  Both match frame = flip(inv(H)(flip(ref)));
    neither matches applying H forwards in either row order -- the first
    attempt did exactly that, seeded half the centroids onto the wrong
    stars, and produced a light curve with 900 mmag of scatter.
    """
    inv = invert_homography(hom)
    if inv is None or not (width and height):
        return None
    pos = apply_homography(inv, float(x), float(height) - 1.0 - float(y))
    if pos is None:
        return None
    return pos[0], float(height) - 1.0 - pos[1]


def frame_to_ref(hom, x, y, width, height):
    """The inverse trip of `ref_to_frame`: frame position to reference.

    Needed because `setref` moves the frame stars are DETECTED on without
    rebasing the homographies -- measured: after ``setref 70`` the .seq
    still holds the identity at image 35.  Star positions read off the
    new reference are therefore in the wrong system for every stored
    homography until they are sent through the detection frame's own H.
    """
    if not (width and height):
        return None
    pos = apply_homography(hom, float(x), float(height) - 1.0 - float(y))
    if pos is None:
        return None
    return pos[0], float(height) - 1.0 - pos[1]


def refine_centroid(data, x, y, box=CENTROID_BOX, iters=CENTROID_ITERS):
    """Centre of light near ``(x, y)``, or ``None`` off-frame or starless.

    This is the "follow star" that `light_curve` lacks: the registration
    only has to land within ``box`` pixels, the centroid does the rest.
    Background is taken as the median of the box so sky gradients do not
    drag the centre; iterating re-centres the box itself, which matters
    when the seed is several pixels off.
    """
    h, w = data.shape[-2], data.shape[-1]
    cx, cy = float(x), float(y)
    for _ in range(max(1, int(iters))):
        x0, x1 = int(round(cx)) - box, int(round(cx)) + box + 1
        y0, y1 = int(round(cy)) - box, int(round(cy)) + box + 1
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
            return None
        cut = np.asarray(data[..., y0:y1, x0:x1], dtype=float)
        if cut.ndim > 2:
            cut = cut[0]
        sub = cut - np.median(cut)
        sub[sub < 0.0] = 0.0
        tot = float(sub.sum())
        if tot <= 0.0:
            return None
        ys, xs = np.mgrid[y0:y1, x0:x1]
        cx = float((sub * xs).sum() / tot)
        cy = float((sub * ys).sum() / tot)
    return cx, cy


def circle_weights(cut_shape, cx, cy, r, grid=SUBPIXEL_GRID):
    """Fractional pixel coverage of a circle over a cutout, in [0, 1].

    ``cx, cy`` are in CUTOUT coordinates.  Interior and exterior pixels
    are decided by their centre distance; only the boundary ring is
    subsampled ``grid x grid``, which bounds the area error per boundary
    pixel at 1/grid^2 -- far below the photon noise of any real frame,
    and orders of magnitude below the half-pixel steps a binary mask
    would take as the centroid moves between frames.
    """
    hgt, wid = cut_shape
    ys, xs = np.mgrid[0:hgt, 0:wid]
    d = np.hypot(xs - cx, ys - cy)
    wgt = (d <= r - 0.71).astype(float)          # wholly inside
    edge = (d < r + 0.71) & (wgt < 1.0)          # straddles the rim
    if np.any(edge):
        off = (np.arange(grid) + 0.5) / grid - 0.5
        oy, ox = np.meshgrid(off, off, indexing="ij")
        ex, ey = xs[edge], ys[edge]
        dd = np.hypot(ex[:, None] + ox.ravel()[None, :] - cx,
                      ey[:, None] + oy.ravel()[None, :] - cy)
        wgt[edge] = (dd <= r).mean(axis=1)
    return wgt


def aperture_photometry(data, x, y, radii, r_in, r_out,
                        gain_e_adu=1.0, sat_adu=None):
    """Sky-subtracted flux at each radius, with a measured error.

    Returns ``(rows, sky, sky_sigma, peak)`` where ``rows`` maps radius to
    ``(flux_adu, err_adu, n_pix)``, or ``None`` when the outer annulus
    leaves the frame or the sky cannot be estimated.

    The error is the CCD equation with every term measured, none assumed:
    star photons from the flux and the gain, background from the
    sigma-clipped scatter of the annulus itself -- which already contains
    read noise, sky photons and flat residuals, so no invented read-noise
    number can make it optimistic.
    """
    h, w = data.shape[-2], data.shape[-1]
    r_max = max(float(r_out), max(float(r) for r in radii))
    x0, x1 = int(math.floor(x - r_max - 1)), int(math.ceil(x + r_max + 2))
    y0, y1 = int(math.floor(y - r_max - 1)), int(math.ceil(y + r_max + 2))
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    cut = np.asarray(data[..., y0:y1, x0:x1], dtype=float)
    if cut.ndim > 2:
        cut = cut[0]
    cx, cy = x - x0, y - y0
    ys, xs = np.mgrid[0:cut.shape[0], 0:cut.shape[1]]
    d = np.hypot(xs - cx, ys - cy)
    ann = cut[(d >= r_in) & (d <= r_out)]
    if ann.size < 12:
        return None
    # Two MAD clips: one bright star in the annulus must not lift the sky.
    for _ in range(2):
        med = np.median(ann)
        mad = np.median(np.abs(ann - med))
        if mad <= 0.0:
            break
        ann = ann[np.abs(ann - med) < 4.0 * 1.4826 * mad]
        if ann.size < 12:
            return None
    sky = float(np.median(ann))
    sky_sigma = float(1.4826 * np.median(np.abs(ann - sky)))
    n_sky = int(ann.size)
    gain = max(float(gain_e_adu), 1e-6)
    rows = {}
    peak = 0.0
    for r in radii:
        wgt = circle_weights(cut.shape, cx, cy, float(r))
        n_ap = float(wgt.sum())
        flux = float((wgt * (cut - sky)).sum())
        pk = float(cut[wgt > 0.5].max()) if np.any(wgt > 0.5) else 0.0
        peak = max(peak, pk)
        var_e = (max(flux, 0.0) * gain
                 + (n_ap + n_ap * n_ap / max(n_sky, 1))
                 * (sky_sigma * gain) ** 2)
        rows[float(r)] = (flux, math.sqrt(max(var_e, 0.0)) / gain, n_ap)
    if sat_adu is not None and peak >= float(sat_adu):
        return rows, sky, sky_sigma, float("inf")
    return rows, sky, sky_sigma, peak


def point_to_point_sigma(mag):
    """Scatter from successive differences, blind to slow structure.

    A transit is slow; consecutive-point differences straddle it almost
    everywhere, so this measures NOISE where a plain standard deviation
    would measure noise plus depth -- and would then prefer whatever
    aperture washes the transit out.
    """
    m = np.asarray(mag, dtype=float)
    m = m[np.isfinite(m)]
    if m.size < 3:
        return float("inf")
    d = np.diff(m)
    return float(1.4826 * np.median(np.abs(d - np.median(d)))
                 / math.sqrt(2.0))


def ensemble_relative_mags(target_flux, comp_fluxes,
                           target_err=None, comp_errs=None):
    """Target magnitudes against a normalised comparison ensemble.

    Each comp is divided by its own median first, so a comp that misses a
    frame drops out of that frame's mean WITHOUT stepping the baseline --
    an ensemble built on raw sums steps by the missing star's whole flux,
    which is exactly the shape of an ingress.  Weights are median flux
    (Poisson: SNR^2).  Returns ``(mag, err)`` with NaN where the target
    or every comp is missing.
    """
    t = np.asarray(target_flux, dtype=float)
    comps = [np.asarray(c, dtype=float) for c in comp_fluxes]
    if not comps or t.size == 0:
        return (np.full(t.shape, np.nan), np.full(t.shape, np.nan))
    norm, wts = [], []
    for c in comps:
        good = np.isfinite(c) & (c > 0.0)
        if good.sum() < 3:
            continue
        med = float(np.median(c[good]))
        if med <= 0.0:
            continue
        norm.append(np.where(good, c / med, np.nan))
        wts.append(med)
    if not norm:
        return (np.full(t.shape, np.nan), np.full(t.shape, np.nan))
    stack = np.vstack(norm)
    wcol = np.asarray(wts, dtype=float)[:, None]
    wmask = np.isfinite(stack) * wcol
    ref = np.nansum(np.where(np.isfinite(stack), stack, 0.0) * wcol,
                    axis=0) / np.maximum(wmask.sum(axis=0), 1e-12)
    ref[wmask.sum(axis=0) <= 0.0] = np.nan
    good_t = np.isfinite(t) & (t > 0.0) & np.isfinite(ref) & (ref > 0.0)
    mag = np.full(t.shape, np.nan)
    mag[good_t] = -2.5 * np.log10(t[good_t] / ref[good_t])
    err = np.full(t.shape, np.nan)
    if target_err is not None:
        te = np.asarray(target_err, dtype=float)
        rel = np.zeros(t.shape)
        rel[good_t] = (te[good_t] / t[good_t]) ** 2
        if comp_errs is not None:
            # The ensemble's own noise, WEIGHTED the way the reference is.
            # The first version split every comp's variance by N^2 -- equal
            # weights -- while the reference itself weights by median flux.
            # Monte Carlo on comps of 100k/10k/2k ADU: empirical 8.1 mmag,
            # equal-split formula 11.8, this one 8.3.  With w_i = med_i the
            # reference variance collapses to sum(err_i^2) / (sum med_i)^2
            # over the members PRESENT in each frame -- the same error a
            # plain flux sum would carry, which is what Poisson weighting
            # is optimal for.
            num = np.zeros(t.shape)
            den = np.zeros(t.shape)
            for c, ce in zip(comps, comp_errs):
                cc = np.asarray(c, dtype=float)
                cee = np.asarray(ce, dtype=float)
                g = np.isfinite(cc) & (cc > 0.0) & np.isfinite(cee)
                if g.sum() < 3:
                    continue
                med = float(np.median(cc[g]))
                if med <= 0.0:
                    continue
                num[g] += cee[g] ** 2
                den[g] += med
            g_ref = den > 0.0
            rel[g_ref] += num[g_ref] / den[g_ref] ** 2
        err[good_t] = 1.0857 * np.sqrt(rel[good_t])
    return mag, err


def rank_comps_by_scatter(comp_fluxes):
    """Keep-mask over comps, judged against the ensemble of the OTHERS.

    EXOTIC's criterion re-measured here: each comp's light curve against
    its peers, scored by TOTAL robust scatter -- not point-to-point.  The
    distinction is the whole point: p2p is deliberately blind to slow
    structure so a transit cannot be punished, but a SLOWLY variable comp
    is exactly the danger, because slow structure written inverted into
    the target is what a fake transit looks like.  A comp curve has no
    transit to protect, so total scatter is the honest score there.

    Judged ITERATIVELY, worst first, and the floor is measured with the
    suspect left out of everyone's reference.  The one-pass version could
    not reject a variable comp carrying more than a third of the
    ensemble flux: its variability sat in every other comp's reference
    with weight w, every score rose with it, and the ratio converged to
    exactly 1/w whatever the amplitude -- a 20 mmag variable that
    happened to be the brightest comp (the usual case, since the
    selection ranks by brightness) was kept in every configuration
    tried.  With the suspect out of the references the floor is what the
    others show without it, and the ratio is what it claims to be.  A
    comp more than COMP_REJECT_FACTOR times that floor is variable or
    sick.  At least two always survive -- with one comp there is no
    ensemble, and zero would silently un-calibrate the run.
    """
    n = len(comp_fluxes)
    if n <= 2:
        return [True] * n, [float("nan")] * n

    def _score(i, pool):
        others = [comp_fluxes[j] for j in pool if j != i]
        mag, _ = ensemble_relative_mags(comp_fluxes[i], others)
        m = mag[np.isfinite(mag)]
        if m.size < 5:
            return float("inf")
        return float(1.4826 * np.median(np.abs(m - np.median(m))))

    active = list(range(n))
    scores = [float("nan")] * n
    while len(active) > 2:
        sc = {i: _score(i, active) for i in active}
        for i in active:
            scores[i] = sc[i]
        worst = max(active, key=lambda i: sc[i])
        rest = [i for i in active if i != worst]
        floor_scores = [_score(j, rest) for j in rest]
        finite = [v for v in floor_scores if math.isfinite(v)]
        if not finite:
            break
        floor = float(np.median(finite))
        if not (math.isfinite(sc[worst])
                and sc[worst] <= COMP_REJECT_FACTOR * floor):
            active = rest
            continue
        break
    keep = [i in active for i in range(n)]
    return keep, scores


def stays_in_frame(x, y, width, height, envelope, margin):
    """Whether ``(x, y)`` keeps its whole aperture on the sensor all run.

    ``margin`` is the measurement radius: a star whose CENTRE is still on
    the chip but whose annulus hangs over the edge measures a background
    that is half sky and half nothing.
    """
    if not envelope or not (width and height):
        return True
    dx0, dx1, dy0, dy1 = envelope
    return (x + dx0 - margin >= 0.0 and x + dx1 + margin < float(width)
            and y + dy0 - margin >= 0.0 and y + dy1 + margin < float(height))


def choose_comparison_stars(stars, target_xy, n_wanted: int,
                            fwhm_px: float, min_snr: float = MIN_COMP_SNR,
                            frame_wh=None, envelope=None):
    """Pick the comparison ensemble from Siril's detected stars.

    ``stars`` is what ``get_image_stars()`` returns.  Returns
    ``(chosen, reserves, rejected, note)`` where ``chosen`` is a list of
    ``(x, y, score)`` ordered brightest-first, ``reserves`` are the
    ``(x, y)`` of the stars that passed every filter and were simply not
    needed — still in ranked order, so a later guard that has to drop a
    chosen comp can promote the next best instead of running short —
    ``rejected`` is a list of ``(x, y, reason)``, and ``note`` says
    which brightness measure was used.  The reasons are not decoration: on the first real run every one
    of 865 stars was thrown away and the message said only "865 were
    rejected", which is indistinguishable from a field with no stars in
    it.  The caller now prints the tally.

    Four filters, each for a different failure:

    * **saturated** -- a clipped core does not scale with transparency, so a
      saturated comp turns every cloud into a fake transit.
    * **too faint** -- a comp contributes its own Poisson noise to the
      ensemble.  Below the floor it adds more scatter than reference.
    * **too close to the target** -- at the ``-autoring`` radii (6.3 x FWHM
      outer) two apertures within ten FWHM start sharing sky annulus and,
      worse, wings.  The contamination is a function of seeing, so it moves
      during the night and looks exactly like a slow trend.
    * **not isolated** -- the same argument as above, aimed at any neighbour
      rather than at the target.  A star inside the comp's own sky annulus
      puts part of its light in the aperture and the rest in the sky
      estimate, and its share moves with the seeing.  The radius comes from
      Siril's own geometry, not from taste: ``-autoring`` sets the outer
      ring to 6.3 x FWHM, so two annuli stop touching at twice that.

    On the brightness measure: ``PSFStar.SNR`` is the right quantity, but
    Siril fills it during PHOTOMETRY, not during ``findstar`` -- a plain
    detection pass leaves it at zero for every star.  Reading that as "every
    star is pure noise" rejects the whole field.  So when no star in the
    frame carries an SNR, this falls back to the instrumental magnitude,
    which ``findstar`` does fill, and says so rather than substituting
    quietly.
    """
    tx, ty = float(target_xy[0]), float(target_xy[1])
    min_sep = MIN_COMP_SEPARATION_FWHM * max(1.0, float(fwhm_px))
    pool = list(stars or [])

    def _snr(st):
        return float(getattr(st, "SNR", 0.0) or 0.0)

    def _mag(st):
        return float(getattr(st, "mag", 0.0) or 0.0)

    have_snr = any(_snr(st) > 0.0 for st in pool)
    if have_snr:
        note = f"ranked by SNR, floor {min_snr:.0f}"
    else:
        # Instrumental magnitudes: smaller is brighter.  Keep comps within
        # MAG_WINDOW of the target -- much brighter risks the saturation
        # the flag does not always catch, much fainter contributes noise
        # without signal (2 mag down is 16% of the flux).
        tmag = None
        for st in pool:
            if (abs(float(getattr(st, "xpos", 0.0) or 0.0) - tx) < 1e-6
                    and abs(float(getattr(st, "ypos", 0.0) or 0.0) - ty) < 1e-6):
                tmag = _mag(st)
                break
        if tmag is None:
            mags = sorted(_mag(st) for st in pool)
            tmag = mags[0] if mags else 0.0
        note = (f"no SNR from findstar — ranked by instrumental magnitude "
                f"within {COMP_MAG_WINDOW:.1f} mag of the target")

    # Neighbour geometry, once, for the whole field.
    px = np.array([float(getattr(st, "xpos", 0.0) or 0.0) for st in pool])
    py = np.array([float(getattr(st, "ypos", 0.0) or 0.0) for st in pool])
    outer = AUTORING_OUTER_FWHM * max(1.0, float(fwhm_px))

    scored = []
    rejected = []
    for idx, st in enumerate(pool):
        x = float(getattr(st, "xpos", 0.0) or 0.0)
        y = float(getattr(st, "ypos", 0.0) or 0.0)
        if abs(x - tx) < 1e-6 and abs(y - ty) < 1e-6:
            continue                                # the target itself
        sep = math.hypot(x - tx, y - ty)
        if frame_wh and envelope and not stays_in_frame(
                x, y, frame_wh[0], frame_wh[1], envelope,
                AUTORING_OUTER_FWHM * max(1.0, float(fwhm_px))):
            rejected.append((x, y, "leaves the frame as the field drifts"))
            continue
        if bool(getattr(st, "has_saturated", False)):
            rejected.append((x, y, "saturated"))
            continue
        if sep < min_sep:
            rejected.append((x, y, f"only {sep:.0f} px from the target"))
            continue
        nearest = float("inf")
        if px.size > 1:
            d = np.hypot(px - x, py - y)
            d[idx] = np.inf                         # not its own neighbour
            nearest = float(d.min())
        # The isolation cut is DEFERRED: how strict it can afford to be
        # depends on how many stars survive everything else, and that is
        # not known yet.  A wide field at 5 arcsec/px can have its stars
        # closer together than one annulus -- 164 of 261 fell here on
        # EXOTIC's demo set, leaving ONE comparison and no run at all.
        if have_snr:
            snr = _snr(st)
            if snr < min_snr:
                rejected.append((x, y, f"SNR {snr:.0f} below {min_snr:.0f}"))
                continue
            scored.append((x, y, snr, nearest))
        else:
            dm = _mag(st) - tmag
            if dm > COMP_MAG_WINDOW:
                rejected.append((x, y, f"{dm:.1f} mag fainter than the target"))
                continue
            if dm < -COMP_MAG_WINDOW:
                rejected.append((x, y, f"{-dm:.1f} mag brighter than the target"))
                continue
            scored.append((x, y, -dm, nearest))  # brighter first, as SNR

    # Now the isolation cut, at the strictest radius that still leaves
    # enough comparisons.  Strict first: a neighbour inside the sky
    # annulus corrupts the background, and that error moves with the
    # seeing -- the shape a transit fit looks for.  But refusing to run at
    # all is worse than running with a stated compromise, and the floor is
    # the APERTURE: a neighbour inside that is blended photometry, not a
    # background error, and no report can rescue it.
    # The target is the MINIMUM, not the wish.  Relaxing until the user's
    # requested count is met would trade isolation away in any field that
    # simply has fewer good stars than asked for -- five in a five-star
    # field.  Fewer clean comparisons beats more compromised ones; the
    # relaxation exists only so that a crowded field runs at all.
    want = MIN_COMPS
    ladder = [(COMP_ISOLATION_OUTER * outer, "clear of its own sky annulus"),
              (outer, "clear of the annulus edge"),
              (0.5 * outer, "clear of the inner annulus"),
              (COMP_APERTURE_FLOOR_FWHM * max(1.0, float(fwhm_px)),
               "clear of the aperture only")]
    chosen_r, chosen_why, survivors = ladder[0][0], ladder[0][1], []
    for radius, why in ladder:
        survivors = [c for c in scored if c[3] >= radius]
        chosen_r, chosen_why = radius, why
        if len(survivors) >= want:
            break
    if chosen_r < ladder[0][0]:
        note += (f"; isolation relaxed to {chosen_r:.0f} px ({chosen_why}) — "
                 f"at the full {ladder[0][0]:.0f} px only "
                 f"{len([c for c in scored if c[3] >= ladder[0][0]])} "
                 f"comparison(s) survived a field this crowded, and a "
                 f"neighbour in the sky annulus is a background error that "
                 f"moves with the seeing")
    for x, y, _sc, near in scored:
        if near < chosen_r:
            # Same two geometries as crowding_note, said apart: a run
            # printed "neighbour 30 px away, inside its own 15 px
            # annulus" — the full cut reaches TWICE the radius, where the
            # two annuli overlap rather than one containing the other.
            rejected.append(
                (x, y, (f"neighbour {near:.0f} px away, inside its own "
                        f"{outer:.0f} px annulus" if near < outer else
                        f"neighbour {near:.0f} px away, overlapping its "
                        f"{outer:.0f} px annulus")
                 if chosen_r >= ladder[0][0] else
                 f"neighbour {near:.0f} px away, closer than the "
                 f"{chosen_r:.0f} px this crowded field could afford"))
    # Sort on the 4-tuples FIRST: when findstar carried no SNR the score
    # is -Δmag, a RANKING key and nothing else.  Handing it onward would
    # print "SNR 2" in the Stars tab and the report — a ranking artefact
    # dressed as a measurement, on the very runs whose log just said "no
    # SNR from findstar".  Downstream a NaN already renders as "—".
    survivors.sort(key=lambda r: r[2], reverse=True)
    scored = [(x, y, sc if have_snr else float("nan"))
              for x, y, sc, near in survivors]
    keep = max(0, int(n_wanted))
    # The stars that passed every filter and were simply not needed are
    # listed too.  Without them the tally does not add up: a run reported
    # "6 chosen, 668 rejected" out of 864 detections and said nothing about
    # the other 189, which reads as a field that barely yielded a comp when
    # in fact it yielded 195 and the best 6 were taken.
    for x, y, _sc in scored[keep:]:
        rejected.append((x, y, f"usable, but only {keep} were needed"))
    reserves = [(x, y) for x, y, _sc in scored[keep:]]
    return scored[:keep], reserves, rejected, note


def crowding_note(stars, x: float, y: float, fwhm_px: float):
    """Whether the star at ``(x, y)`` has company, as ``(colour, message)``.

    A comparison star with a neighbour inside its own sky annulus is
    dropped.  The target cannot be dropped, so the same geometry is reported
    instead: the neighbour's light is in the aperture AND in the sky
    estimate, and its share moves with the seeing, which is a slow trend
    through the night -- the shape a transit fit is looking for.

    Returns ``None`` when the star is clear.
    """
    xs, ys = [], []
    for st in (stars or []):
        sx = float(getattr(st, "xpos", 0.0) or 0.0)
        sy = float(getattr(st, "ypos", 0.0) or 0.0)
        if abs(sx - x) < 1e-6 and abs(sy - y) < 1e-6:
            continue
        xs.append(sx)
        ys.append(sy)
    if not xs:
        return None
    outer = AUTORING_OUTER_FWHM * max(1.0, float(fwhm_px))
    d = np.hypot(np.array(xs) - float(x), np.array(ys) - float(y))
    near = float(d.min())
    if near < COMP_ISOLATION_OUTER * outer:
        # Two different geometries, said apart: inside the annulus the
        # neighbour's light is IN the sky estimate; further out (up to
        # twice the radius) the two annuli overlap and share sky.  The
        # old message called both "inside the annulus", which on a
        # 16 px neighbour with a 15 px annulus read as a contradiction.
        where = (f"inside the {outer:.0f} px sky annulus"
                 if near < outer else
                 f"close enough that its own {outer:.0f} px sky annulus "
                 f"overlaps the target's")
        return (LogColor.SALMON,
                f"Another star sits {near:.0f} px away, {where}. Its share "
                f"of the aperture changes with the seeing, which is a slow "
                f"trend through the night — do not read a shallow dip here "
                f"as a transit.")
    return None


def pick_target(stars, mode: str, want_xy=None, want_radec=None):
    """The target star, as ``(x, y, source)``, or ``None``.

    ``mode`` is ``"brightest"``, ``"pixel"`` or ``"radec"``.  The pixel and
    RA/Dec modes both snap to the NEAREST DETECTED star rather than using
    the typed position directly: a coordinate that lands two pixels off the
    centroid puts the aperture off-centre for the whole run, and the
    resulting flux loss varies with seeing.
    """
    cand = []
    for st in stars or []:
        cand.append((float(getattr(st, "xpos", 0.0) or 0.0),
                     float(getattr(st, "ypos", 0.0) or 0.0),
                     float(getattr(st, "SNR", 0.0) or 0.0),
                     float(getattr(st, "ra", 0.0) or 0.0),
                     float(getattr(st, "dec", 0.0) or 0.0)))
    if not cand:
        return None
    def _snap(dists, unit):
        """Nearest candidate, plus an honest word on whether it is the one.

        The absolute distance is not the question -- it says as much about
        how precisely the coordinates were typed as about the match.  The
        question is whether the RUNNER-UP is comparably close.  On a field
        with hundreds of stars the nearest neighbour to an arbitrary point
        is normally far away, so a close second means the two are
        genuinely confusable and the wrong one may have been picked.
        """
        order = sorted(dists, key=lambda t: t[0])
        d1, best = order[0]
        note = f"nearest detection, {d1:.1f}{unit} from the position you gave"
        if len(order) > 1:
            d2 = order[1][0]
            if d2 < TARGET_AMBIGUOUS_RATIO * d1:
                note += (f" — but the next star is only {d2:.1f}{unit} away, "
                         "so this match is AMBIGUOUS; give a pixel position "
                         "if it picked the wrong one")
        return (best[0], best[1], note)

    if mode == "pixel" and want_xy is not None:
        wx, wy = float(want_xy[0]), float(want_xy[1])
        return _snap([(math.hypot(c[0] - wx, c[1] - wy), c) for c in cand],
                     " px")
    if mode == "radec" and want_radec is not None:
        wr, wd = float(want_radec[0]), float(want_radec[1])
        solved = [c for c in cand if abs(c[3]) > 1e-9 or abs(c[4]) > 1e-9]
        if not solved:
            return None
        cosd = math.cos(math.radians(wd))
        return _snap([(math.hypot((c[3] - wr) * cosd, c[4] - wd) * 3600.0, c)
                      for c in solved], '"')
    best = max(cand, key=lambda c: c[2])
    return (best[0], best[1], "brightest star in the field")


# ---------------------------------------------------------------------------
# The run itself, off the UI thread
# ---------------------------------------------------------------------------
class _LdcComputeThread(QThread):
    """Archive lookup for Teff/log g, then the Phoenix computation --
    off the GUI thread, because the first call downloads model files."""
    done = pyqtSignal(object, str)
    progress = pyqtSignal(str)

    def __init__(self, name: str, band: str, parent=None):
        super().__init__(parent)
        self._name, self._band = name, band

    def run(self) -> None:
        # Anything that escapes here -- an IncompleteRead on a 21 MB
        # download, a malformed cached model -- would otherwise end the
        # thread without `done`, leaving the button grey and the status
        # line frozen on "Downloading model 2/4".
        try:
            self._compute()
        except Exception as exc:                 # noqa: BLE001
            _log_swallowed(exc)
            self.done.emit(None, f"Claret computation failed: "
                                 f"{type(exc).__name__}: {exc}")

    def _compute(self) -> None:
        eph, why = ((toi_lookup(self._name) if looks_like_toi(self._name)
                     else archive_lookup(self._name)))
        if not eph:
            self.done.emit(None, f"archive lookup failed: {why}")
            return
        teff, logg = eph.get("teff_k"), eph.get("logg")
        if not teff or not logg:
            self.done.emit(None, "the archive has no Teff/log g for "
                                 f"{eph.get('name', self._name)}")
            return
        vals, note = claret_from_phoenix(teff, logg, self._band,
                                         progress=self.progress.emit)
        if vals is None:
            self.done.emit(None, note)
            return
        self.done.emit(vals, note + f" — {eph.get('name', self._name)}")


class LightCurveWorker(QThread):
    """Drive Siril through link -> register -> light_curve, then analyse.

    Everything that touches Siril happens here; the window only reads the
    result.  The pixel work is Siril's, which is why this class is mostly
    command plumbing plus the decisions Siril has no opinion about: which
    star is the target, which stars are worth calibrating against, and
    whether the dip that comes out is real.
    """

    progress = pyqtSignal(int, str)
    log = pyqtSignal(str, object)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, siril, folder: str, opts: dict):
        super().__init__()
        self.siril = siril
        self.folder = folder
        self.opts = dict(opts)
        self._ext = ".fit"
        # Consecutive light_curve failures.  Twelve in a row on EXOTIC's
        # demo set ended with Siril's process gone and a "Broken pipe" the
        # script could only report as somebody else's crash.
        self._photometry_failures = 0
        self._drift = None
        self._ref_shift = (0.0, 0.0)
        self._ref_fwhm = 0.0
        self._frame_wh = None

    # -- plumbing ---------------------------------------------------------
    def _apply_hops_photometry(self, jd, mag, err):
        """HOPS mode measures what HOPS measures: the target over the raw
        sum of the comparison stars.  Replaces the ensemble series for
        everything downstream, or keeps it with the reason in the log."""
        hp = getattr(self, "_hops_photometry", None)
        self._hops_phot_note = ""
        if not hp or hp["rel"].size != np.asarray(jd).size:
            self._emit("  HOPS photometry unavailable (this script's own "
                       "photometry engine did not run) — the ensemble "
                       "series stands.", LogColor.SALMON)
            return jd, mag, err
        rel, rel_err = hp["rel"], hp["rel_err"]
        good = np.isfinite(rel) & (rel > 0) & np.isfinite(rel_err)
        n_lost = int(np.count_nonzero(~good))
        if int(np.count_nonzero(good)) < 5:
            self._emit("  HOPS photometry left fewer than 5 points — the "
                       "ensemble series stands.", LogColor.SALMON)
            return jd, mag, err
        mag_h = -2.5 * np.log10(rel[good])
        mag_h = mag_h - float(np.nanmedian(mag_h))
        err_h = (2.5 / math.log(10.0)) * rel_err[good] / rel[good]
        self._hops_phot_note = (
            f"target over the raw sum of {hp['n_comps']} comparison "
            f"star(s), errors propagated as HOPS does"
            + (f"; {n_lost} frame(s) dropped where a comparison star was "
               "missing" if n_lost else ""))
        self._emit("  HOPS photometry: " + self._hops_phot_note
                   + (" — HOPS's raw sum is not NaN-robust, and neither "
                      "is this one" if n_lost else "")
                   + ". Every number downstream — chart, CSV, results.txt "
                     "and the blind test — now stands on this series.",
                   LogColor.GREEN)
        return np.asarray(jd)[good], mag_h, err_h

    def _hops_mode(self, jd, mag, err, blind: dict, X, eph,
                   time_system: str, flip_bases=None):
        """The HOPS-compatible fit on the finished photometry.

        Returns a fit dict in the blind fit's vocabulary (so the chart,
        the report and the CSV need no second code path) with a ``hops``
        sub-dict carrying what only this mode knows, or None with the
        reason in the log -- the blind fit then stands.
        """
        S = LogColor.SALMON
        eph = eph if isinstance(eph, dict) else {}
        period = eph.get("period_d")
        if not period:
            self._emit("  HOPS mode needs the planet's period from the "
                       "archive — none is known for this target, so the "
                       "blind fit stands.", S)
            return None
        period = float(period)
        jd = np.asarray(jd, dtype=float)
        mag = np.asarray(mag, dtype=float)
        err = np.asarray(err, dtype=float)
        rp0, rp_src = eph.get("rprs_archive"), "the archive's Rp/R*"
        if not rp0 and eph.get("depth_pct"):
            rp0 = math.sqrt(float(eph["depth_pct"]) / 100.0)
            rp_src = "the archive's depth"
        if not rp0 and blind.get("rprs"):
            rp0, rp_src = float(blind["rprs"]), "the blind fit"
        if not rp0:
            rp0, rp_src = 0.1, "a default of 0.1"
        rp0 = float(rp0)
        a_rs, inc = eph.get("a_rs"), eph.get("inc_deg")
        ecc = float(eph.get("ecc") or 0.0)
        peri = float(eph["peri_deg"]) if eph.get("peri_deg") is not None \
            else 90.0
        geom_note = ("orbit (a/R*, inclination, eccentricity, periastron) "
                     "from the archive")
        if a_rs is None or inc is None:
            dur_h = eph.get("duration_h")
            sin_arg = (math.sin(math.pi * float(dur_h) / 24.0 / period)
                       if dur_h else 0.0)
            if sin_arg <= 0:
                self._emit("  HOPS mode needs the orbit (a/R* and "
                           "inclination) or at least a transit duration "
                           "from the archive — neither is known, so the "
                           "blind fit stands.", S)
                return None
            a_rs, inc, ecc, peri = (1.0 + rp0) / sin_arg, 90.0, 0.0, 90.0
            geom_note = (f"a/R* = {a_rs:.2f} derived from the archive's "
                         "duration assuming a central transit (b = 0), "
                         "because the archive lists no a/R* or "
                         "inclination for this planet")
        geom = {"period_d": period, "a_rs": float(a_rs), "ecc": ecc,
                "inc_deg": float(inc), "peri_deg": peri}
        ldc = self.opts.get("hops_ldc")
        if ldc and len(ldc) == 4:
            ldc = [float(c) for c in ldc]
            ldc_note = (self.opts.get("hops_ldc_note")
                        or "Claret a1..a4 as entered")
        else:
            u1 = float(self.opts.get("ld_u1", LD_U1))
            u2 = float(self.opts.get("ld_u2", LD_U2))
            ldc = quad_to_claret(u1, u2)
            ldc_note = (f"the quadratic law (u1 = {u1:.2f}, u2 = {u2:.2f}) "
                        "written as Claret coefficients")
        choice = str(self.opts.get("hops_detrend", "airmass")).lower()
        tmin = float(np.nanmin(jd))
        x_t = jd - tmin
        detrend_note = ""
        detrend = None
        if choice == "airmass":
            if X is None or not np.any(np.isfinite(np.asarray(X, float))):
                detrend_note = ("Airmass detrending was asked for but no "
                                "airmass series exists (site or target "
                                "position missing) — fell back to Linear.")
                choice = "linear"
            else:
                xa = np.asarray(X, dtype=float)
                detrend = {"airmass": xa - float(np.nanmin(xa))}
        if choice == "quadratic":
            detrend = {"time_time": x_t * x_t, "time": x_t}
        elif detrend is None:
            choice = "linear"
            detrend = {"time": x_t}
        # HOPS has no notion of a meridian flip; its fit on a run that
        # jumped 59 mmag at the flip walked the mid-time 76 min to the
        # step and called it an 84 mmag transit.  The same 0/1 step the
        # blind fit uses goes in as one more multiplicative coefficient.
        flip_jd = float(getattr(self, "_flip_jd_utc", float("nan")))
        if np.isfinite(flip_jd) and flip_bases is not None:
            step = np.asarray(flip_bases, dtype=float)
            if 5 <= int(step.sum()) <= step.size - 5:
                detrend["flip"] = step
                choice += "+flip"
        if detrend_note:
            self._emit("  " + detrend_note, S)
        t_center = 0.5 * (tmin + float(np.nanmax(jd)))
        if time_system == "BJD_TDB" and eph.get("t0_bjd"):
            epoch = int(round((t_center - float(eph["t0_bjd"])) / period))
            mid_guess = float(eph["t0_bjd"]) + epoch * period
            mid_note = f"the archive's predicted mid-time for epoch {epoch}"
            mid_from_archive = True
        else:
            mid_from_archive = False
            mid_guess = t_center
            mid_note = ("the run's centre (timestamps are not BJD_TDB, so "
                        "the archive epoch cannot be placed)")
        iterations = max(100, int(self.opts.get("hops_iterations", 2000)
                                  or 2000))
        n_walk = 3 * (len(detrend) + 3)
        info0 = (getattr(self, "_light_infos", None) or [{}])[0]
        try:
            exp_s = float(info0.get("exp_s") or 0.0)
        except (TypeError, ValueError):
            exp_s = 0.0
        sub_steps = int(exp_s / HOPS_SUB_EXPOSURE_S) + 1 if exp_s > 0 else 1
        self._emit(f"  HOPS mode: {geom_note}; limb darkening from "
                   f"{ldc_note}; detrending {choice} "
                   f"({' + '.join(detrend)}); Rp/R* starts from {rp_src}; "
                   f"mid-time prior ±0.2 d around {mid_note}; "
                   + (f"model averaged over {sub_steps} sub-steps of the "
                      f"{exp_s:g} s exposure; " if exp_s > 0 else
                      "no exposure time in the headers, model evaluated "
                      "at mid-exposure; ")
                   + f"{iterations} iterations of a {n_walk}-walker ensemble "
                   "sampler, first 20 % discarded.", LogColor.GREEN)

        def _prog(frac):
            self.progress.emit(int(72 + 14 * frac),
                               f"HOPS-mode sampling… {int(100 * frac)} %")

        try:
            res = hops_mode_fit(jd, mag, err, geom, ldc, detrend, mid_guess,
                                rp_initial=rp0, iterations=iterations,
                                progress=_prog, exp_s=exp_s)
        except Exception as exc:                   # noqa: BLE001
            _log_swallowed(exc)
            res = None
        if res is None:
            self._emit("  HOPS mode could not fit this run (the orbit "
                       "makes no transit, or too few points) — the blind "
                       "fit stands.", S)
            return None

        # Everything the chart and the report read, in magnitudes over
        # the FULL point list (outliers stay on the plot; only the fit
        # ignored them).
        mag_med = -2.5 * math.log10(res["flux_median"])
        xs_full = [np.asarray(detrend[k], dtype=float) for k in res["names"]]
        trend_flux = res["n"] * (1.0 + sum(c * x for c, x in
                                           zip(res["coeffs"], xs_full)))
        with np.errstate(invalid="ignore", divide="ignore"):
            trend_mag = mag_med - 2.5 * np.log10(
                np.where(trend_flux > 0, trend_flux, np.nan))
        tr_full = hops_transit_flux(jd, res["rp"], res["mid_time"], geom,
                                    "claret", ldc, LD_RADIAL_STEPS, exp_s)
        transit_mag = -2.5 * np.log10(np.clip(tr_full, 1e-9, None))
        model_mag = trend_mag + transit_mag
        detrended = mag - trend_mag
        rp, rp_sig = float(res["rp"]), 0.5 * (res["rp_m"] + res["rp_p"])
        mid, mid_sig = float(res["mid_time"]), 0.5 * (res["mid_m"]
                                                       + res["mid_p"])
        dur = float(res["duration_d"])
        rho = (1.0 - ecc * ecc) / (1.0 + ecc * math.sin(math.radians(peri)))
        b = geom["a_rs"] * rho * math.cos(math.radians(geom["inc_deg"]))
        depth_mag = -2.5 * math.log10(max(1.0 - res["depth_flux"], 1e-9))
        depth_sig_mag = depth_mag * 2.0 * rp_sig / rp if rp > 0 else 0.0
        kept = np.isin(jd, res["t"])
        resid_mag = (mag - model_mag)[kept]
        rms = float(np.std(resid_mag[np.isfinite(resid_mag)])) * 1000.0
        in_tr = np.abs(jd - mid) < 0.5 * dur
        n_fit = sum(1 for row in res["rows"] if row[1] == "fit")
        fe = np.asarray(res["flux_err"]) / res["scale_factor"]
        chi2 = float(np.sum(((res["flux"] - res["model_flux"]) / fe) ** 2))
        nu = max(1, res["t"].size - n_fit)
        slope = None
        if "airmass" in res["names"]:
            c_air = res["coeffs"][res["names"].index("airmass")]
            slope = -2.5 * math.log10(1.0 + c_air) if c_air > -1 else None

        fit = dict(blind)
        fit.update({
            "mode": "hops",
            "blind_depth_mmag": blind.get("depth_mmag"),
            "blind_duration_h": blind.get("duration_h"),
            "t0": mid, "t0_sigma_d": mid_sig, "t0_sigma_s": mid_sig * 86400.0,
            "duration_d": dur, "duration_h": dur * 24.0,
            "rp_over_rs": rp, "impact_b": float(b),
            "rprs": rp, "rprs_sigma": rp_sig,
            "depth_rprs2_pct": rp * rp * 100.0,
            "depth_rprs2_pct_sigma": 2.0 * rp * rp_sig * 100.0,
            "depth_mag": depth_mag, "depth_mmag": depth_mag * 1000.0,
            "depth_pct": res["depth_flux"] * 100.0,
            "depth_sigma_mmag": depth_sig_mag * 1000.0,
            "chi2_nu": chi2 / nu,
            "chi2_nu_sigma": math.sqrt(2.0 / nu),
            "chi2_nu_note": (
                f"with the errors BEFORE HOPS's rescaling (x "
                f"{res['scale_factor']:.3f}); results.txt quotes the "
                "rescaled value, ~1 by construction"),
            "baseline": 0.0,
            "basis_coeffs": [float(c) for c in res["coeffs"]],
            "coeff_sigmas": [0.5 * (m + p_) for m, p_ in
                             zip(res["m_err"][:1 + len(res["names"])],
                                 res["p_err"][:1 + len(res["names"])])],
            "bases": list(res["names"]),
            "base_note": f"HOPS {choice} detrending",
            "airmass_slope": slope,
            "trend": trend_mag, "detrended": detrended,
            "model_mag": model_mag,
            "template": res["template"],
            "rms_resid_mmag": rms,
            "n_in": int(np.count_nonzero(in_tr)),
            "n_out": int(np.count_nonzero(~in_tr)),
            "hops": {
                "rows": res["rows"], "names": res["names"],
                "outliers": res["outliers"],
                "scale_factor": res["scale_factor"],
                "acceptance": res["acceptance"],
                "iterations": res["iterations"], "walkers": res["walkers"],
                "burn_in": res["burn_in"],
                "exp_s": exp_s, "sub_steps": sub_steps,
                "photometry": getattr(self, "_hops_phot_note", "") or
                "ensemble series (HOPS photometry unavailable)",
                "geom": geom, "geom_note": geom_note, "impact_b": float(b),
                "ldc": ldc, "ldc_note": ldc_note,
                "detrend": choice, "detrend_note": detrend_note,
                "rp_source": rp_src,
                "mid_guess": mid_guess, "mid_note": mid_note,
                "rp_m": res["rp_m"], "rp_p": res["rp_p"],
                "mid_m": res["mid_m"], "mid_p": res["mid_p"],
                "depth_flux": res["depth_flux"],
                "t": res["t"], "flux": res["flux"],
                "flux_err": res["flux_err"],
                "model_flux": res["model_flux"],
                "trend_flux": res["trend_flux"],
                "transit_flux": res["transit_flux"],
                "blind_significance": blind.get("significance"),
            },
        })
        self._emit(
            f"  HOPS-mode result: Rp/R* = {rp:.4f} -{res['rp_m']:.4f} "
            f"+{res['rp_p']:.4f} → (Rp/R*)² = {rp * rp * 100:.2f} %; "
            f"mid-time {mid:.5f} -{res['mid_m'] * 86400:.0f} s "
            f"+{res['mid_p'] * 86400:.0f} s"
            + (f" (O−C {(mid - mid_guess) * 1440:+.1f} min against the "
               "archive)" if mid_from_archive else "")
            + f"; duration {dur * 24:.3f} h from the orbit; "
            f"{res['outliers']} outlier(s) removed; error bars scaled by "
            f"{res['scale_factor']:.3f}; acceptance "
            f"{res['acceptance']:.2f}.", LogColor.GREEN)
        if res.get("duration_note"):
            self._emit("  NOTE: " + res["duration_note"] + ".", S)
        if res.get("n_nonfinite"):
            self._emit(f"  {res['n_nonfinite']} point(s) dropped from the "
                       "HOPS fit for a non-finite detrending value "
                       "(airmass below the horizon).", S)
        self._emit(
            "  The blind detection test above still decides whether a "
            "transit is CLAIMED; HOPS mode measures the catalogue's "
            "planet, it does not test for one.", LogColor.GREEN
            if blind.get("detected") else S)
        # An ephemeris-locked fit whose transit runs past either end of
        # the data is degenerate with a baseline offset: on a TOI-4033
        # run it walked 76 min to a flip step and reported Rp/R* 0.25.
        # Said out loud, with the coverage in hours.
        t_lo, t_hi = float(np.nanmin(jd)), float(np.nanmax(jd))
        ing, egr = mid - 0.5 * dur, mid + 0.5 * dur
        if ing < t_lo or egr > t_hi:
            warn = (
                f"the fitted transit runs from "
                f"{(ing - t_lo) * 24:+.2f} h to {(egr - t_lo) * 24:+.2f} h "
                f"after the first point, but the data cover 0 to "
                f"{(t_hi - t_lo) * 24:.2f} h. With one contact outside the "
                "run, a transit and a baseline offset are the same "
                "curve — the HOPS-mode numbers do not measure this planet.")
            fit["hops"]["coverage_warning"] = warn
            self._emit("  WARNING: " + warn, S)
        return fit

    def _emit(self, msg: str, color=None) -> None:
        try:
            self.siril.log(f"[LightCurve] {msg}", color or LogColor.BLUE)
        except Exception:
            pass
        self.log.emit(msg, color)

    def _fail(self, msg: str) -> None:
        """Abort the run, and say so WHERE THE USER IS LOOKING.

        `failed` only reaches the script window.  On the first real run this
        left Siril's own log ending mid-sentence after the star detection,
        with no error anywhere in it -- the run had refused to continue and
        the only place that said so was a dialog behind the log window.
        Every abort now writes to Siril's log first, in red, and only then
        raises the signal.
        """
        try:
            self.siril.log(f"[LightCurve] {msg}", LogColor.RED)
        except Exception:
            pass
        self.failed.emit(msg)

    def _cmd(self, *args) -> None:
        self.siril.cmd(*args)

    def _q(self, path: str) -> str:
        """Quote a whole argument, flag included.

        Siril splits a command line on spaces before it parses the flags, so
        a path with a space in it has to sit inside quotes TOGETHER with the
        flag it belongs to -- ``"-out=/My Folder/x"``, never
        ``-out="/My Folder/x"``.
        """
        return f'"{path}"'

    # -- steps ------------------------------------------------------------
    def _stage_frames(self, work: str, files: list) -> int:
        """Symlink (or copy) the subs into the working folder.

        Symlinks by default: a transit run is a few hundred frames and
        copying them doubles the disk for no benefit.  The original folder
        is never written to either way.
        """
        lights = os.path.join(work, "lights")
        os.makedirs(lights, exist_ok=True)
        copy = bool(self.opts.get("copy_frames", False))
        n = 0
        staged = []
        for src in files:
            # numbered by what was STAGED, so the sequence index and the
            # header list keep step even when a frame fails to stage
            dst = os.path.join(lights,
                               f"{len(staged):05d}_{os.path.basename(src)}")
            try:
                if os.path.lexists(dst):
                    os.remove(dst)
                if copy:
                    shutil.copy2(src, dst)
                else:
                    try:
                        os.symlink(os.path.abspath(src), dst)
                    except (OSError, NotImplementedError):
                        shutil.copy2(src, dst)
                n += 1
            except OSError as exc:
                self._emit(f"  could not stage {os.path.basename(src)}: {exc}",
                           LogColor.SALMON)
                continue
            staged.append(src)
        return n, staged

    def _target_saturation(self, ref_path: str, x: float, y: float):
        """``(saturated, evidence)`` for the star at ``(x, y)``.

        Reads the reference frame's pixels.  Verified against this data set:
        the box lands on the target with plain ``[y, x]`` indexing -- the
        plate solve's "Flipping image" leaves the coordinates `findstar`
        reports consistent with the file on disk, which is also why
        `light_curve` finds the comparison stars where they were asked for.
        """
        try:
            from astropy.io import fits
            # memmap=False, and not for taste: astropy refuses to
            # memory-map a file carrying BZERO/BSCALE/BLANK, and Siril's
            # compressed frames carry them.  With memmap=True the read
            # raised, the pixel evidence was lost, and the saturation
            # verdict fell back to Siril's flag with no numbers behind it.
            with fits.open(ref_path, memmap=False) as hdul:
                data = None
                for hdu in hdul:
                    if getattr(hdu, "data", None) is not None:
                        data = hdu.data
                        break
                return saturation_verdict(data, x, y)
        except Exception as exc:            # noqa: BLE001 -- never abort
            _log_swallowed(exc)
            return None, f"could not read {os.path.basename(ref_path)}"

    # -- calibration ------------------------------------------------------
    def _master_name(self, kind: str, grp: dict) -> str:
        """A cache name that carries everything the grouping distinguishes.

        If two different masters could ever share a name the cache hands
        back the wrong one, silently, on the second run -- so every field
        that splits a group appears here.
        """
        i = grp["info"]
        bits = [f"master_{kind}"]
        if i.get("exp_s") is not None:
            bits.append(f"{float(i['exp_s']):g}s")
        if i.get("gain_v") is not None:
            bits.append(f"g{float(i['gain_v']):g}")
        if i.get("temp_v") is not None and kind in (KIND_DARK, KIND_DARKFLAT):
            bits.append(f"{round(float(i['temp_v'])):+d}C")
        bits.append(f"bin{i.get('binning', 1)}")
        if i.get("dims"):
            bits.append(f"{i['dims'][0]}x{i['dims'][1]}")
        return re.sub(r"[^A-Za-z0-9_.+-]", "_", "_".join(bits))

    def _find_produced(self, folder: str, stem: str):
        for ext in FITS_EXTS:
            cand = os.path.join(folder, stem + ext)
            if os.path.exists(cand):
                return cand
        return None

    def _build_master(self, kind: str, grp: dict, cache: str, work: str,
                      offset_master: str = ""):
        """Build (or reuse) one master; return its path or ``None``.

        A group of exactly one file is ADOPTED, not stacked -- a single
        frame either already is a master or is the only one there is, and
        stacking it would just copy it through Siril.

        Nothing here may abort the run.  Calibration that fails leaves the
        frames uncalibrated and says so; that is worse than calibrating and
        better than a traceback halfway through a night's photometry.
        """
        name = self._master_name(kind, grp)
        files = grp.get("files") or []
        dest = self._find_produced(cache, name)
        if dest:
            self._emit(f"    reusing {os.path.basename(dest)}",
                       LogColor.GREEN)
            return dest

        if len(files) == 1:
            dest = os.path.join(cache, name + os.path.splitext(files[0])[1])
            try:
                shutil.copy2(files[0], dest)
                self._emit(f"    {kind}: one frame, adopted as a ready-made "
                           f"master ({os.path.basename(files[0])})",
                           LogColor.BLUE)
                return dest
            except OSError as exc:
                self._emit(f"    {kind}: could not adopt it ({exc})",
                           LogColor.SALMON)
                return None
        if len(files) < CALIB_MIN_STACK:
            self._emit(f"    {kind}: no usable frames", LogColor.SALMON)
            return None

        stage = os.path.join(work, "calib", name, "src")
        shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
        os.makedirs(stage, exist_ok=True)
        staged = 0
        for i, src in enumerate(files):
            dst = os.path.join(stage, f"{i:04d}_{os.path.basename(src)}")
            try:
                os.symlink(os.path.abspath(src), dst)
            except (OSError, NotImplementedError):
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    continue
            staged += 1
        if staged < CALIB_MIN_STACK:
            self._emit(f"    {kind}: only {staged} frame(s) could be staged",
                       LogColor.SALMON)
            return None

        proc = os.path.join(os.path.dirname(stage), "process")
        try:
            self._cmd("cd", self._q(stage))
            self._cmd("link", kind, "-out=../process")
            self._cmd("cd", self._q(proc))
            seq = kind
            if kind == KIND_FLAT:
                # Flats carry the sensor pedestal, and dividing by an
                # uncorrected flat drags that pedestal into every light.
                if offset_master:
                    self._cmd("calibrate", kind,
                              f'"-bias={offset_master}"')
                    seq = CALIB_PREFIX + kind
                    self._emit("    flats offset-corrected with "
                               f"{os.path.basename(offset_master)}",
                               LogColor.BLUE)
                else:
                    try:
                        self._cmd("calibrate", kind, '-bias="=64*$OFFSET"')
                        seq = CALIB_PREFIX + kind
                        self._emit("    flats offset-corrected with Siril's "
                                   "synthetic offset (=64*$OFFSET)",
                                   LogColor.BLUE)
                    except Exception:       # noqa: BLE001 -- Siril refused it
                        self._emit("    no offset available — flats stacked "
                                   "uncorrected", LogColor.SALMON)
                norm = "-norm=mul"
            else:
                norm = "-nonorm"
            # Rejection is always on for a master, whatever the run does
            # elsewhere: a cosmic ray left in a master flat reaches every
            # single light that master calibrates.
            self._cmd("stack", seq, "rej", "w", "3", "3", norm,
                      "-out=" + name)
            produced = self._find_produced(proc, name)
            if not produced:
                self._emit(f"    {kind}: stacking produced no master",
                           LogColor.RED)
                return None
            dest = os.path.join(cache, os.path.basename(produced))
            shutil.copy2(produced, dest)
            self._emit(f"    built {kind} master from {staged} frames "
                       f"-> {os.path.basename(dest)}", LogColor.GREEN)
            return dest
        except Exception as exc:            # noqa: BLE001 -- never abort
            self._emit(f"    {kind}: master build failed ({exc})",
                       LogColor.RED)
            return None

    def _calibrate(self, seq: str, files, folder: str, out_dir: str,
                   work: str) -> str:
        """Find calibration frames, build the masters, calibrate the lights.

        Returns the sequence to carry on with -- the calibrated one when
        anything was applied, the original otherwise.  Every path out says
        what happened, because a calibration that silently did nothing is
        indistinguishable in the final plot from one that worked.

        This does NOT resample.  Bias, dark and flat are per-pixel
        arithmetic, so the promise the registration keeps is not broken
        here.  It does write a second copy of every frame.
        """
        light_header = _read_header(files[0]) if files else None
        light_info = inspect_frame(files[0], light_header) if files else {}
        state, evidence = frames_are_calibrated(light_header)

        if not self.opts.get("calibrate", True):
            self._calib_note = "switched off"
            self._emit("  Calibration is switched off.", LogColor.BLUE)
            return seq

        want = light_info.get("filter", "")
        # Calibration frames come from three places, and all three are
        # folded into one set of groups: inside the folder you selected
        # (already inspected, so no second header read), beside it in the
        # N.I.N.A. layout, and in your library.
        inside = group_calibration(getattr(self, "_inside_calib", []), want)
        if inside:
            self._emit("  Calibration frames found inside your selection: "
                       + ", ".join(f"{len(g['files'])} {k}"
                                   for k, gs in sorted(inside.items())
                                   for g in gs), LogColor.BLUE)
        lights_dir = os.path.dirname(files[0]) if files else folder
        library = self.opts.get("calib_library", "") or ""
        # Named apart, because "Also looking in: FLAT, LUMINOS" gave no way
        # to tell a folder the script found from one the user pointed at --
        # and the second is the one worth double-checking.
        siblings = calibration_roots(lights_dir, "")
        if siblings:
            self._emit("  Calibration folders found beside the lights: "
                       + ", ".join(os.path.relpath(r, os.path.dirname(
                           os.path.dirname(lights_dir))) for r in siblings),
                       LogColor.BLUE)
        if library:
            self._emit(f"  Library folder: {library}", LogColor.BLUE)
        roots = calibration_roots(lights_dir, library)
        outside = scan_calibration(roots, want) if roots else {}
        groups = merge_calibration(inside, outside)
        if not groups:
            self._calib_note = "no calibration frames found"
            self._no_calib_note(state, evidence)
            return seq
        chosen, notes = choose_masters(groups, light_info)
        for line in notes:
            self._emit("    " + line,
                       LogColor.SALMON if "REJECT" in line or "none" in line
                       else LogColor.BLUE)
        if not chosen:
            self._calib_note = "frames found but none matched"
            self._no_calib_note(state, evidence)
            return seq

        cache = os.path.join(out_dir, "calib")
        os.makedirs(cache, exist_ok=True)
        offset_path = ""
        if chosen.get("offset"):
            offset_path = self._build_master(
                chosen["offset"]["kind"], chosen["offset"], cache, work) or ""
        masters = {}
        if chosen.get("dark"):
            masters["dark"] = self._build_master(
                KIND_DARK, chosen["dark"], cache, work)
        if chosen.get("flat"):
            masters["flat"] = self._build_master(
                KIND_FLAT, chosen["flat"], cache, work, offset_path)
        masters = {k: v for k, v in masters.items() if v}

        # Back to the light sequence before calibrating it: the master
        # builds moved the working directory.
        self._cmd("cd", self._q(os.path.join(work, "process")))
        args, used = calibration_args(
            seq, dark=masters.get("dark"), flat=masters.get("flat"),
            cfa=bool(self.opts.get("cfa", False)))
        if args is None:
            self._calib_note = "masters could not be built"
            self._emit("  No master could be built — the frames stay "
                       "uncalibrated.", LogColor.SALMON)
            return seq
        if state is True:
            self._emit(f"  These frames already carry a calibration "
                       f"({evidence}) and are about to be calibrated a "
                       f"SECOND time. Check that this is what you want.",
                       LogColor.SALMON)
        self._cmd(*args)
        self._calib_note = ", ".join(
            f"{kind}={os.path.basename(path)}" for kind, path in used)
        self._emit("  Calibrated with " + self._calib_note
                   + ". Siril's own `calibrate` — no second implementation "
                     "here, and no resampling: per-pixel arithmetic.",
                   LogColor.GREEN)
        return CALIB_PREFIX + seq

    def _no_calib_note(self, state, evidence: str) -> None:
        """Say what an uncalibrated run means, once, in the right words."""
        if state is True:
            self._emit(f"  Nothing to calibrate with, and the frames already "
                       f"carry a calibration ({evidence}).", LogColor.GREEN)
        elif state is False:
            self._emit(
                "  These frames are RAW and no calibration frames were "
                "found, so nothing is being corrected. The flat is the one "
                "that matters most here: a star drifting across a dust "
                "shadow is a slow trend shaped exactly like a shallow "
                "transit, and after a meridian flip the target lands on a "
                "different patch of sensor entirely — that is a STEP in the "
                f"light curve, not a wobble. ({evidence})", LogColor.SALMON)
        else:
            self._emit(f"  No calibration frames found; whether these were "
                       f"already calibrated cannot be told from the header "
                       f"({evidence}).", LogColor.BLUE)

    def _register(self, seq: str) -> None:
        """Compute registration WITHOUT resampling the frames.

        `register -2pass` writes registration data and stops there.  That is
        deliberate and it matters more here than in a stacking script:
        `seqapplyreg` would interpolate every pixel, and interpolation
        correlates neighbouring noise and redistributes flux inside the
        aperture.  Siril's photometry follows the stars through the
        registration data instead, so the aperture lands on the star while
        the pixels stay exactly as the sensor recorded them.
        """
        try:
            self._cmd("register", seq, "-2pass")
            self._emit("  Registration computed (two-pass, no resampling — "
                       "the pixels stay as the sensor recorded them).",
                       LogColor.GREEN)
            return
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Two-pass registration failed ({exc}); trying the "
                       "single-pass form.", LogColor.SALMON)
        self._cmd("register", seq)
        self._emit("  Registration computed (single pass).", LogColor.GREEN)

    def _centre_reference(self, seq: str) -> None:
        """Move the registration reference to the middle of the DRIFT.

        Siril picks its reference on image quality, which is right for
        stacking and wrong here.  `light_curve` refuses outright when any
        frame sits more than 160 px from the reference, so a reference
        near one end of a drifting run puts the whole drift on one side
        and the command cannot run at all.

        Measured on EXOTIC's demo set (Siril 1.4.4): Siril chose image 35
        of 142, worst drift 218.9 px, "generic error" every time.  Moving
        the reference to image 72 -- the middle of the drift, not of the
        sequence -- gives 147.1 px and the same command produces a curve
        from all 142 frames.  `setref` must come AFTER `register`, which
        picks its own reference and overrides an earlier `setref`.

        Nothing here may abort the run: a reference that cannot be moved
        leaves the run exactly as it was.
        """
        try:
            self._cmd("load_seq", f'"{seq}_"')
            data = self.siril.get_seq()
            n = int(getattr(data, "number", 0) or 0)
            cur = int(getattr(data, "reference_image", 0) or 0)
            # From the SEQUENCE, not from a FITS read.  The FITS read is
            # what failed on a real run ("BZERO/BSCALE/BLANK header
            # keywords present. Set memmap=False") and the frame size
            # going missing takes the drift filter down with it.
            w = int(getattr(data, "rx", 0) or 0)
            hgt = int(getattr(data, "ry", 0) or 0)
            self._frame_wh = (w, hgt) if (w and hgt) else None
            homs, qual = [], []
            for i in range(n):
                reg = self.siril.get_seq_regdata(i, 0)
                homs.append(getattr(reg, "H", None) if reg else None)
                # Weighted FWHM is Siril's own frame-quality measure and
                # the one that separates image 71 (2.42) from image 72
                # (8.50) -- two frames five apart, one usable and one not.
                q = None
                for name in ("weighted_fwhm", "wfwhm", "fwhm"):
                    v = getattr(reg, name, None) if reg else None
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(v) and v > 0.0:
                        q = v
                        break
                qual.append(q)
            shifts = shift_list(homs, w, hgt)
        except Exception as exc:            # noqa: BLE001
            _log_swallowed(exc)
            return
        if not any(s is not None for s in shifts):
            return
        ceiling = SIRIL_DRIFT_LIMIT_PX * DRIFT_LIMIT_MARGIN
        now = worst_drift(shifts, cur)
        best_i, best_d = best_reference(shifts, qual, ceiling)
        if now is None or best_i is None or best_d is None:
            return
        if now <= ceiling:
            # Already inside Siril's limit with room to spare.  Leave the
            # reference alone -- it is the best-QUALITY frame, and that is
            # worth keeping when geometry is not forcing the issue.
            self._ref_shift = shifts[cur] or (0.0, 0.0)
            return
        if best_d > ceiling:
            self._emit(
                f"  The field drifts {now:.0f} px from Siril's reference "
                f"frame, and the best any frame can do is {best_d:.0f} px "
                f"— both over the {SIRIL_DRIFT_LIMIT_PX:.0f} px at which "
                "light_curve refuses to run. No choice of reference "
                "rescues this run; the drift itself is too large. Trim "
                "the run to the stretch where the field holds still, or "
                "apply the registration first (Siril: `seqapplyreg`) and "
                "point this script at the resampled sequence.",
                LogColor.SALMON)
            self._ref_shift = shifts[cur] or (0.0, 0.0)
            return
        try:
            self._cmd("setref", seq + "_", str(best_i + 1))
        except (CommandError, DataError, SirilError) as exc:
            _log_swallowed(exc)
            self._ref_shift = shifts[cur] or (0.0, 0.0)
            return
        self._ref_shift = shifts[best_i] or (0.0, 0.0)
        q_now = qual[cur] if cur < len(qual) else None
        q_new = qual[best_i] if best_i < len(qual) else None
        detail = ""
        if q_now and q_new:
            detail = (f" Its weighted FWHM is {q_new:.2f} px against "
                      f"{q_now:.2f} for the frame Siril chose — the new "
                      "reference is picked for QUALITY among the frames "
                      "that fit, not merely for sitting in the middle of "
                      "the drift.")
        self._emit(
            f"  Reference frame moved to image {best_i + 1} of {n}. Siril "
            f"picked image {cur + 1} on image quality, which left the "
            f"field drifting {now:.0f} px from it — over the "
            f"{SIRIL_DRIFT_LIMIT_PX:.0f} px at which light_curve refuses "
            f"to run at all. The new one drifts {best_d:.0f} px.{detail}",
            LogColor.GREEN)

    def _reference_frame(self, seq: str, proc: str) -> str:
        """Path of the frame Siril chose as its REGISTRATION reference.

        This is not frame 1.  ``register -2pass`` analyses the whole run and
        picks the frame with the best combination of FWHM, roundness and
        star count -- on the first real run it chose image 5 of 178.  That
        matters because ``light_curve``'s ``-at=`` coordinates are read in
        the reference frame, so detecting stars on frame 1 and handing the
        positions to ``light_curve`` mixes two coordinate systems.  Here
        frames 1 and 5 happened to agree to 0.6 px, which is why it worked;
        that is luck, not design, and a run whose reference lands on the
        far side of a meridian flip would be off by three thousand pixels.
        """
        names = sorted(n for n in os.listdir(proc)
                       if n.startswith(seq + "_") and _is_fits(n))
        if not names:
            raise RuntimeError(
                "the linked sequence produced no frames to detect stars on")
        idx = 0
        try:
            self._cmd("load_seq", f'"{seq}_"')
            data = self.siril.get_seq()
            idx = int(getattr(data, "reference_image", 0) or 0)
        except Exception as exc:
            _log_swallowed(exc)          # fall back to the first frame
        if not 0 <= idx < len(names):
            idx = 0
        return os.path.join(proc, names[idx])

    def _detect_reference_stars(self, seq: str, proc: str):
        """Detect stars on the registration reference frame.

        When the target is given as RA/Dec and the frames carry no
        astrometric solution, this plate-solves the reference frame first
        rather than sending the user away to do it by hand -- the script
        drives Siril for every other step, and the target's own
        coordinates are the ideal centre hint for the solve.
        """
        ref = self._reference_frame(seq, proc)
        self._cmd("load", self._q(ref))
        self._cmd("findstar")
        stars = self.siril.get_image_stars()
        if not stars:
            raise RuntimeError(
                "Siril found no stars in the reference frame. Check focus, "
                "and that the frames really are of the sky.")
        if (self.opts.get("target_mode") == "radec"
                and not _any_solved(stars)):
            solved = self._solve_reference(ref)
            if solved:
                stars = solved
        return stars, ref

    def _solve_reference(self, ref: str):
        """Plate-solve the loaded reference frame, then detect again.

        Returns the re-detected stars when they now carry sky
        coordinates, otherwise None -- a solve that "succeeds" without
        putting a WCS in the header is a failure for our purposes, and
        the only honest test is to look at the stars afterwards.
        """
        args = ["platesolve"]
        radec = self.opts.get("target_radec")
        if radec:
            # The target is not the field centre, but on any sensible
            # framing it is within a fraction of a degree of it -- far
            # inside the search radius, and enough to turn a blind solve
            # into a targeted one.
            args.append(f"{float(radec[0]):.6f},{float(radec[1]):.6f}")
        scale, where = image_scale_arcsec(_read_header(ref))
        scale_note = ""
        if scale:
            focal, pix = scale_to_focal_pixel(scale)
            args.append(f"-focal={focal:.2f}")
            args.append(f"-pixelsize={pix:.2f}")
            scale_note = (f" at {scale:.3f}\"/px from {where}")
        else:
            scale_note = f" — {where}"
        self._emit("  No astrometric solution in these frames — plate-solving "
                   "the reference frame" + (" around the target position"
                                            if radec else "")
                   + scale_note + "…",
                   LogColor.BLUE if scale else LogColor.SALMON)
        try:
            self._cmd(*args)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Plate solve failed: {exc}", LogColor.SALMON)
            return None
        try:
            self._cmd("findstar")
            stars = self.siril.get_image_stars()
        except Exception as exc:
            _log_swallowed(exc)
            return None
        if not _any_solved(stars):
            self._emit("  The solve reported success but left no sky "
                       "coordinates on the stars.", LogColor.SALMON)
            return None
        self._emit(f"  Solved — {len(stars)} star(s) now carry RA/Dec.",
                   LogColor.GREEN)
        return stars

    def _resolve_site(self, files) -> None:
        """Fill the observatory position from the frames when it is blank.

        The subs carry it -- SITELAT/SITELONG/SITEELEV are standard
        N.I.N.A. keywords -- and TWO things need it: the airmass detrend
        and the BJD_TDB conversion.  Before this, both switched themselves
        off whenever the user had not typed the coordinates in by hand,
        and the airmass one did so almost silently.  A value typed into
        the form still wins: it is the only way to correct a header that
        is wrong.
        """
        have = (self.opts.get("site_lat_deg") is not None
                and self.opts.get("site_lon_deg") is not None)
        if have:
            self._emit(f"  Site from the form: "
                       f"{float(self.opts['site_lat_deg']):+.4f}, "
                       f"{float(self.opts['site_lon_deg']):+.4f} "
                       "(east positive).", LogColor.BLUE)
            return
        for path in files[:5]:            # a header can be unreadable
            hdr = _read_header(path)
            site = site_from_header(hdr)
            if site is None:
                continue
            lat, lon, height, where = site
            lon, sign_note = longitude_sign_check(hdr, lat, lon)
            self.opts["site_lat_deg"] = lat
            self.opts["site_lon_deg"] = lon
            self.opts["site_height_m"] = height
            # The observatory's NAME rides along for the plot title —
            # the same SITENAME the log already quotes in "read from the
            # FITS header (…)".  Typed-in coordinates carry no name, and
            # the title simply drops that part.
            self.opts["site_name"] = str(
                (hdr or {}).get("SITENAME", "") or "").strip()
            self._emit(f"  Site read from the {where}: {lat:+.4f}, "
                       f"{lon:+.4f}, {height:.0f} m."
                       + (f" {sign_note}." if sign_note else ""),
                       LogColor.RED if "FLIPPED" in sign_note
                       else LogColor.BLUE)
            return
        self._emit("  No observatory position in the frames and none given "
                   "— the airmass detrend and the BJD_TDB conversion will "
                   "both be skipped.", LogColor.SALMON)

    def _check_for_flip(self, seq: str) -> float:
        """Measure the field rotation across the sequence and warn about it.

        Returns the spread in degrees (0.0 when it cannot be read).  This
        does not stop the run: Siril follows the stars through the
        registration data either way, so the photometry is still correct.
        What it cannot fix is that the star sits on a different piece of
        silicon before and after the flip, and the light curve therefore
        carries a step at that moment -- the same shape as an ingress.
        """
        # The same pass collects the per-frame quality Siril already
        # measured during registration and this script used to discard.
        # RegData carries fwhm, background_lvl, number_of_stars and
        # roundness alongside the homography -- four detrending bases for
        # free, no extra read of a single pixel.
        quality = {"fwhm": [], "sky": [], "n_stars": [], "roundness": []}
        try:
            self._cmd("load_seq", f'"{seq}_"')
            data = self.siril.get_seq()
            n = int(getattr(data, "number", 0) or 0)
            homs = []
            for i in range(n):
                reg = self.siril.get_seq_regdata(i, 0)
                homs.append(getattr(reg, "H", None) if reg else None)
                quality["fwhm"].append(
                    float(getattr(reg, "fwhm", float("nan")) or float("nan"))
                    if reg else float("nan"))
                quality["sky"].append(
                    float(getattr(reg, "background_lvl", float("nan"))
                          or float("nan")) if reg else float("nan"))
                quality["n_stars"].append(
                    float(getattr(reg, "number_of_stars", float("nan"))
                          or float("nan")) if reg else float("nan"))
                quality["roundness"].append(
                    float(getattr(reg, "roundness", float("nan"))
                          or float("nan")) if reg else float("nan"))
            self._frame_quality = {k: np.asarray(v, dtype=float)
                                   for k, v in quality.items()}
            wh = getattr(self, "_frame_wh", None) or (0, 0)
            self._drift = drift_envelope(homs, self._ref_shift, wh[0], wh[1])
            # WHEN the flip happened, not only THAT it happened: the
            # boundary frame's DATE-OBS (midpoint with its predecessor
            # when both are readable) becomes a marker in the chart, the
            # same "flip 00:55" flag the planning tool shows — so the
            # user can check with their own eyes whether a step or an
            # "ingress" coincides with it.
            self._flip_jd_utc = float("nan")
            idx = flip_boundary_index(homs)
            infos = getattr(self, "_light_infos", []) or []
            if idx is not None and idx < len(infos):
                def _mid(info):
                    return mid_exposure_jd(
                        info.get("date_obs") or "", info.get("exp_s") or 0.0,
                        info.get("date_avg") or "",
                        info.get("date_end") or "")[0]
                j_at = _mid(infos[idx])
                j_before = _mid(infos[idx - 1]) if idx > 0 else float("nan")
                if math.isfinite(j_at) and math.isfinite(j_before):
                    # Halfway between the two mid-exposure times, the same
                    # stamps the photometry uses -- so the marker lands
                    # between the two curve points whatever DATE-OBS
                    # means (start, mid or end of the exposure).
                    self._flip_jd_utc = 0.5 * (j_at + j_before)
                elif math.isfinite(j_at):
                    self._flip_jd_utc = j_at
        except Exception as exc:
            _log_swallowed(exc)
            return 0.0
        spread = rotation_spread_deg(homs)
        if spread is None:
            return 0.0
        if spread >= FLIP_ROTATION_DEG:
            self._emit(
                f"  The field rotates by {spread:.0f}° across this run — "
                "that is a meridian flip, not tracking drift. The "
                "photometry still follows the stars, but the target lands "
                "on a DIFFERENT patch of sensor after the flip: different "
                "flat-field response, different hot pixels, a different "
                "corner of the vignette. Expect a step in the light curve "
                "at that moment, and treat any 'transit' whose ingress "
                "coincides with it as unproven.", LogColor.SALMON)
        else:
            self._emit(f"  Field rotation across the run: {spread:.2f}° — "
                       "no flip.", LogColor.BLUE)
        return spread

    def _native_photometry(self, seq: str, proc: str, target_xy, comps,
                           fwhm: float, reserves=()):
        """Measure the run here, with Siril doing the geometry.

        Returns ``(jd, mag, err, n_unmeasured)`` or ``None``, in which
        case the caller falls back to Siril's `light_curve` -- the old
        path stays fully intact behind this one.

        Why this exists (all measured, Siril 1.4.4, EXOTIC's demo set):
        `light_curve` moves each box by the registration alone and lost
        half the frames of a drifting run; `seqpsf -followstar` measured
        the same star with zero failures but its numbers are reachable
        neither from a file nor from sirilpy, and `light_curve` does not
        reuse them.  So the frames are read once each and every star is
        re-centroided per frame -- the same follow-star idea, plus
        EXOTIC's two judgements: comps kept by measured scatter, aperture
        chosen by point-to-point noise of the finished curve.
        """
        try:
            from astropy.io import fits
        except ImportError:
            return None
        try:
            self._cmd("load_seq", f'"{seq}_"')
            data = self.siril.get_seq()
            n = int(getattr(data, "number", 0) or 0)
            exposure = float(getattr(data, "exposure", 0.0) or 0.0)
            frames = []
            for i in range(n):
                reg = self.siril.get_seq_regdata(i, 0)
                img = self.siril.get_seq_imgdata(i)
                hom = _homography(getattr(reg, "H", None) if reg else None)
                if img is None or hom is None or not getattr(img, "incl", True):
                    continue
                when = getattr(img, "date_obs", None)
                fnum = int(getattr(img, "filenum", i + 1) or (i + 1))
                path = None
                try:
                    path = self.siril.get_seq_frame_filename(i)
                except Exception as exc:        # noqa: BLE001
                    _log_swallowed(exc)
                if not path:
                    # Siril's output extension is configurable; probe the
                    # usual three rather than hard-coding one.
                    fixed = int(getattr(data, "fixed", 5) or 5)
                    stem = os.path.join(proc, f"{seq}_{fnum:0{fixed}d}")
                    for ext in (".fit", ".fits", ".fts"):
                        if os.path.exists(stem + ext):
                            path = stem + ext
                            break
                    if not path:
                        continue
                elif not os.path.isabs(path):
                    path = os.path.join(proc, path)
                frames.append((i, hom, when, path))
        except Exception as exc:                # noqa: BLE001
            _log_swallowed(exc)
            return None
        if len(frames) < 5:
            return None

        stars = [tuple(map(float, target_xy))] + \
                [(float(c[0]), float(c[1])) for c in comps]
        # The stars were detected on `reference_image` -- which `setref`
        # may have moved -- while every homography still points at the
        # ORIGINAL registration reference (measured: after `setref 70`
        # the .seq keeps the identity at image 35).  Send the positions
        # through the detection frame's own homography first, or every
        # seed is off by the full shift between the two frames.
        try:
            det = int(getattr(data, "reference_image", 0) or 0)
            wh = getattr(self, "_frame_wh", None)
            det_hom = None
            for i, hom, _w, _p in frames:
                if i == det:
                    det_hom = hom
                    break
            if det_hom is not None and wh and (
                    abs(det_hom[2]) > 0.5 or abs(det_hom[5]) > 0.5
                    or abs(det_hom[0] - 1.0) > 1e-3):
                moved = []
                for sx, sy in stars:
                    pos = frame_to_ref(det_hom, sx, sy, wh[0], wh[1])
                    if pos is None:
                        return None
                    moved.append(pos)
                stars = moved
        except Exception as exc:                # noqa: BLE001
            _log_swallowed(exc)
            return None
        radii = sorted({round(max(1.5, float(fwhm) * g), 2)
                        for g in APERTURE_FWHM_GRID})
        r_in = AUTORING_INNER_FWHM * max(float(fwhm), 1.0)
        r_out = AUTORING_OUTER_FWHM * max(float(fwhm), 1.0)
        gain = 1.0
        gain_hdr = 1.0
        gain_src = "assumed — no usable EGAIN in the header"
        sat_adu = None
        float_normalised = False
        try:
            with fits.open(frames[0][3], memmap=False) as hd:
                hdr = hd[0].header if hd[0].data is not None else hd[1].header
                # EGAIN is e-/ADU by convention.  GAIN is usually the
                # CAMERA SETTING (0-500, arbitrary units) and must not be
                # mistaken for a conversion factor: a GAIN of 100 read as
                # e-/ADU would multiply every error bar tenfold.  So GAIN
                # is only believed in the range real conversion factors
                # live in.
                for card, hi in (("EGAIN", 100.0), ("GAIN", 10.0)):
                    try:
                        v = float(hdr.get(card))
                        if 0.0 < v < hi:
                            gain = v
                            gain_hdr = v
                            gain_src = f"from the header ({card})"
                            break
                    except (TypeError, ValueError):
                        pass
                d0 = None
                for u in hd:
                    if getattr(u, "data", None) is not None:
                        d0 = u.data
                        break
            if d0 is not None and np.issubdtype(d0.dtype, np.integer):
                full = float(np.iinfo(d0.dtype).max)
                # A 12- or 14-bit camera whose driver does not shift to
                # 16 bit clips at 4095 / 16383 and never reaches the
                # dtype ceiling: the header's DATAMAX/SATURATE wins
                # when it has one, else a frame maximum sitting exactly
                # on such a ceiling is taken as the clip level.
                info0 = (getattr(self, "_light_infos", None) or [{}])[0]
                hdr_max = info0.get("datamax")
                frame_max = float(np.nanmax(d0))
                if hdr_max and 0 < float(hdr_max) < full:
                    full = float(hdr_max)
                    self._emit(f"  Clip level {full:g} ADU from the header "
                               "(DATAMAX/SATURATE).", LogColor.BLUE)
                elif frame_max in (4095.0, 16383.0) and frame_max < full:
                    full = frame_max
                    self._emit(f"  Clip level {full:g} ADU: the frame tops "
                               "out exactly there, a 12/14-bit camera "
                               "without a bit shift.", LogColor.BLUE)
                sat_adu = SAT_FRACTION * full
            elif d0 is not None and float(np.nanmax(d0)) <= 1.05:
                sat_adu = SAT_FRACTION
                # Siril's calibrated output is 16-bit ADU divided by
                # 65535.  A gain quoted in e-/ADU must scale with the
                # data, or "1 unit" is read as ONE electron and the
                # Poisson term of the CCD equation collapses by four
                # orders of magnitude -- the background term survives
                # (it is measured empirically in data units) but every
                # bright star's error bar comes out absurdly small.
                gain = gain * 65535.0
                gain_src += ", x65535 for normalised float data"
                float_normalised = True
        except Exception as exc:                # noqa: BLE001
            _log_swallowed(exc)
            return None

        # HEADROOM GUARD.  A comp whose reference peak already sits at
        # COMP_CLIP_HEADROOM of the clip level is one good-seeing frame
        # away from clipping, and intermittent clipping is
        # indistinguishable from variability: on the first
        # flat-calibrated run two such comps were kept, then rejected
        # as variable, and 73 frames where the ensemble clipped
        # together vanished from the curve without a word.  Dropped
        # only while at least two comps survive — a thin field keeps
        # its comps and relies on the per-frame accounting below.
        if sat_adu is not None and d0 is not None \
                and (len(stars) > 3 or reserves):
            arr0 = np.asarray(d0)
            if arr0.ndim > 2:
                arr0 = arr0[0]
            h0, w0 = arr0.shape[-2], arr0.shape[-1]
            hom0 = frames[0][1]
            # The peak is read on frame 0, but the clip happens on the
            # SHARPEST frame.  A star's peak scales as 1/FWHM^2 at fixed
            # flux, so frame 0's peak is scaled up by (FWHM_0/FWHM_min)^2
            # (capped at 4x) before the comparison — the guard used to
            # pass a comp that frame 0's poor seeing had flattened.
            peak_scale = 1.0
            q = getattr(self, "_frame_quality", None) or {}
            fw = np.asarray(q.get("fwhm", []), dtype=float)
            try:
                fw0 = float(fw[frames[0][0]])
                fw_min = float(np.nanmin(fw))
                if math.isfinite(fw0) and math.isfinite(fw_min) and fw_min > 0:
                    peak_scale = min(4.0, max(1.0, (fw0 / fw_min) ** 2))
            except (IndexError, ValueError, TypeError):
                pass

            def _peak_at(sx, sy):
                pos = ref_to_frame(hom0, sx, sy, w0, h0)
                if pos is None:
                    return float("nan")
                xi, yi = int(round(pos[0])), int(round(pos[1]))
                if not (0 <= xi < w0 and 0 <= yi < h0):
                    return float("nan")
                box = arr0[max(0, yi - SATURATION_BOX_PX):
                           yi + SATURATION_BOX_PX + 1,
                           max(0, xi - SATURATION_BOX_PX):
                           xi + SATURATION_BOX_PX + 1]
                return (float(np.nanmax(box)) * peak_scale if box.size
                        else float("nan"))

            n_want = len(stars) - 1
            kept_stars = [stars[0]]
            n_dropped = 0
            dropped_stars = []
            for sx, sy in stars[1:]:
                peak0 = _peak_at(sx, sy)
                if math.isfinite(peak0) \
                        and peak0 >= COMP_CLIP_HEADROOM * sat_adu:
                    n_dropped += 1
                    dropped_stars.append((peak0, (sx, sy)))
                    self._emit(
                        f"    comp ({sx:7.1f}, {sy:7.1f})  dropped up "
                        f"front: peak already at "
                        f"{100.0 * peak0 / sat_adu:.0f}% of the clip "
                        "level — one good-seeing frame from clipping, "
                        "and intermittent clipping reads as "
                        "variability.", LogColor.SALMON)
                else:
                    kept_stars.append((sx, sy))
            # PROMOTE from the reserve.  The selection ranked more
            # usable stars than it handed over ("532 x usable, but only
            # 5 were needed" on the run that motivated this) — dropping
            # a comp must not shrink the ensemble while that list has
            # candidates with headroom.  Walked in ranked order, so the
            # promotions are the best stars that clear the bar; on the
            # flat-calibrated run every ranked-brighter star sat AT the
            # clip ceiling, which is exactly why the walk starts at the
            # top and keeps going.
            n_promoted = 0
            if n_dropped:
                for sx, sy in reserves:
                    if len(kept_stars) - 1 >= n_want:
                        break
                    peak0 = _peak_at(sx, sy)
                    if not math.isfinite(peak0) \
                            or peak0 >= COMP_CLIP_HEADROOM * sat_adu:
                        continue
                    kept_stars.append((float(sx), float(sy)))
                    n_promoted += 1
                    self._emit(
                        f"    comp ({sx:7.1f}, {sy:7.1f})  promoted "
                        f"from the reserve: peak at "
                        f"{100.0 * peak0 / sat_adu:.0f}% of the clip "
                        "level — the next ranked star with headroom.",
                        LogColor.BLUE)
                if len(kept_stars) - 1 < n_want:
                    self._emit(
                        f"  Only {len(kept_stars) - 1} of {n_want} "
                        "comparison star(s) have headroom, and the "
                        f"reserve of {len(reserves)} is exhausted.",
                        LogColor.SALMON)
            if n_dropped and len(kept_stars) >= 3:
                stars = kept_stars
            elif n_dropped and n_promoted:
                # Too few for an ensemble even after promoting: keep the
                # promotions and refill with the least-clipped originals
                # rather than throwing the promotions away with the rest.
                for _pk, xy in sorted(dropped_stars):
                    if len(kept_stars) >= 3:
                        break
                    kept_stars.append(xy)
                stars = kept_stars
                self._emit(
                    "  The headroom guard left fewer than two comparison "
                    "stars — keeping the promoted one(s) and the least-"
                    "clipped original(s), counting their clipped frames.",
                    LogColor.SALMON)
            elif n_dropped:
                self._emit(
                    "  The headroom guard would leave fewer than two "
                    "comparison stars — keeping the originals and "
                    "counting their clipped frames instead.",
                    LogColor.SALMON)

        n_stars = len(stars)
        n_frames = len(frames)
        jd = np.full(n_frames, np.nan)
        flux = {r: np.full((n_stars, n_frames), np.nan) for r in radii}
        ferr = {r: np.full((n_stars, n_frames), np.nan) for r in radii}
        sat_dropped = 0
        unreadable = 0
        tgt_lost_cen = 0                 # target centroid failed/walked
        tgt_lost_ap = 0                  # target aperture unmeasurable
        comp_clips = np.zeros(n_stars, dtype=int)
        # The homography convention (frame->reference, as the drift filter
        # established on real data) gives the seed; the centroid does the
        # rest, and a seed that finds nothing is retried through the
        # inverse so a convention change in Siril degrades to a second
        # attempt instead of a silent empty run.
        for k, (_i, hom, when, path) in enumerate(frames):
            if self.isInterruptionRequested():
                return None
            try:
                with fits.open(path, memmap=False) as hd:
                    d = None
                    hdr = None
                    for u in hd:
                        if getattr(u, "data", None) is not None:
                            d = np.asarray(u.data)
                            hdr = u.header
                            break
            except Exception as exc:            # noqa: BLE001
                _log_swallowed(exc)
                unreadable += 1
                continue
            if d is None or d.ndim < 2:
                unreadable += 1
                continue
            # The time comes from the frame's OWN header, which is already
            # open -- not from sirilpy's ImgData.date_obs, which came back
            # empty on a real N.I.N.A. run: the engine then measured 83
            # good points, could stamp none of them, and fell back to
            # Siril without a word.  The header parser has survived every
            # timestamp this project has met (seven-digit fractions, UTC
            # offsets); sirilpy is the fallback, not the source.
            try:
                exp_s = float(hdr.get("EXPTIME", hdr.get("EXPOSURE", 0.0))
                              or 0.0) if hdr is not None else 0.0
            except (TypeError, ValueError):
                exp_s = 0.0
            if not exp_s:
                exp_s = exposure
            stamp = str(hdr.get("DATE-OBS", "") or "") if hdr is not None \
                else ""
            if not stamp and when is not None:
                try:
                    stamp = when.isoformat()
                except Exception:               # noqa: BLE001
                    stamp = ""
            if stamp:
                jd[k], _src = mid_exposure_jd(
                    stamp, exp_s,
                    str(hdr.get("DATE-AVG", hdr.get("DATE-MID", "")) or "")
                    if hdr is not None else "",
                    str(hdr.get("DATE-END", "") or "")
                    if hdr is not None else "")
            hgt, wid = d.shape[-2], d.shape[-1]
            target_hit = False
            for si, (sx, sy) in enumerate(stars):
                pos = ref_to_frame(hom, sx, sy, wid, hgt)
                cen = (refine_centroid(d, pos[0], pos[1])
                       if pos is not None else None)
                if cen is not None and math.hypot(
                        cen[0] - pos[0], cen[1] - pos[1]) > CENTROID_MAX_SHIFT:
                    # The centre of light walked to a NEIGHBOUR.  A wrong
                    # star measured confidently is worse than a missing
                    # frame -- it was most of the 900 mmag above.
                    cen = None
                if cen is None:
                    if si == 0:
                        tgt_lost_cen += 1
                    continue
                got = aperture_photometry(d, cen[0], cen[1], radii,
                                          r_in, r_out, gain, sat_adu)
                if got is None:
                    if si == 0:
                        tgt_lost_ap += 1
                    continue
                rows, _sky, _ssig, peak = got
                if math.isinf(peak):            # clipped core this frame
                    if si == 0:
                        sat_dropped += 1
                    else:
                        comp_clips[si] += 1
                    continue
                if si == 0:
                    target_hit = True
                for r, (fl, er, _npx) in rows.items():
                    flux[r][si, k] = fl
                    ferr[r][si, k] = er

        good_t = np.isfinite(flux[radii[0]][0])
        yield_frac = float(good_t.sum()) / max(n_frames, 1)
        if yield_frac < NATIVE_MIN_YIELD:
            self._emit(
                f"  This script measured only {int(good_t.sum())} of "
                f"{n_frames} frame(s) itself"
                + (f" ({unreadable} unreadable)" if unreadable else "")
                + (f" ({sat_dropped} with a clipped core)" if sat_dropped
                   else "")
                + (f" ({tgt_lost_cen} target centroid failures)"
                   if tgt_lost_cen else "")
                + (f" ({tgt_lost_ap} target apertures unmeasurable)"
                   if tgt_lost_ap else "")
                + " — below the bar for trusting its own result, so "
                "Siril's light_curve takes over.", LogColor.SALMON)
            return None

        # A frame where a comp clipped is a frame the ensemble may lose
        # — say WHO clipped and HOW OFTEN, because intermittent clipping
        # wears a variable star's costume in the scatter check below.
        for si in range(1, n_stars):
            if comp_clips[si]:
                cx, cy = stars[si]
                self._emit(
                    f"    comp ({cx:7.1f}, {cy:7.1f})  clipped in "
                    f"{int(comp_clips[si])} of {n_frames} frame(s).",
                    LogColor.SALMON)
        if float_normalised and (sat_dropped + int(comp_clips.sum())
                                 >= max(3, n_frames // 20)):
            self._emit(
                "  These frames are calibrated floats clamped to [0, 1] "
                "— the flat division can push stars into that ceiling "
                "that their raw frames never touched, costing headroom "
                "exactly where the flat was supposed to help. Fainter "
                "comps, or calibration that keeps values above 1, avoid "
                "it.", LogColor.SALMON)

        # Comps judged at the middle radius, kept or dropped by measured
        # scatter; the verdict is then reused for every radius.
        mid_r = radii[len(radii) // 2]
        comp_flux_mid = [flux[mid_r][i] for i in range(1, n_stars)]
        keep, scores = rank_comps_by_scatter(comp_flux_mid)
        comp_rows = []
        for i, (kp, sc) in enumerate(zip(keep, scores)):
            cx, cy = stars[i + 1]
            rms = 1000.0 * sc if math.isfinite(sc) else float("nan")
            verdict = ("kept" if kp
                       else "DROPPED — varies against its peers")
            comp_rows.append((cx, cy, rms, verdict))
            label = ("      —" if not math.isfinite(sc)
                     else f"{rms:6.1f} mmag")
            self._emit(f"    comp ({cx:7.1f}, {cy:7.1f})  {label}"
                       + ("" if kp else "  " + verdict),
                       LogColor.BLUE if kp else LogColor.SALMON)
        if not any(keep):
            self._emit("  Every comparison star failed its own scatter "
                       "check — Siril's light_curve takes over.",
                       LogColor.SALMON)
            return None

        best = None
        aper_rows = []
        for r in radii:
            cf = [flux[r][i + 1] for i in range(len(keep)) if keep[i]]
            ce = [ferr[r][i + 1] for i in range(len(keep)) if keep[i]]
            mag, err = ensemble_relative_mags(flux[r][0], cf,
                                             ferr[r][0], ce)
            p2p = point_to_point_sigma(mag)
            npts = int(np.isfinite(mag).sum())
            aper_rows.append((float(r), npts,
                              1000.0 * p2p if math.isfinite(p2p)
                              else float("nan")))
            self._emit(f"    aperture {r:5.2f} px  {npts:4d} point(s)  "
                       + ("     —" if not math.isfinite(p2p)
                          else f"{1000.0 * p2p:6.2f} mmag"), LogColor.BLUE)
            if math.isfinite(p2p) and (best is None or p2p < best[0]):
                best = (p2p, r, mag, err, npts)
        if best is None:
            self._emit("  No aperture produced a finite light curve — "
                       "Siril's light_curve takes over.", LogColor.SALMON)
            return None
        p2p, r_best, mag, err, npts = best
        # HOPS's light curve from the same fluxes at the same aperture:
        # target over the raw comp sum.  Kept for the HOPS-compatible
        # mode, which swaps it in downstream.
        _cf = [flux[r_best][i + 1] for i in range(len(keep)) if keep[i]]
        _ce = [ferr[r_best][i + 1] for i in range(len(keep)) if keep[i]]
        _rel, _rel_err = hops_relative_flux(flux[r_best][0], _cf,
                                            ferr[r_best][0], _ce)
        self._emit(
            f"  Aperture {r_best:.2f} px "
            f"({r_best / max(float(fwhm), 1e-9):.2f} x FWHM) chosen by "
            f"point-to-point noise; sky annulus {r_in:.1f}-{r_out:.1f} px; "
            f"gain {gain_hdr:g} e-/ADU {gain_src}.", LogColor.GREEN)
        # Centre the curve on its own median.  The raw value is
        # -2.5*log10(flux / a reference normalised to ~1) — an arbitrary
        # zero point near -10 that reads as broken in every plot, CSV and
        # report.  Subtracting a constant moves the baseline coefficient
        # and nothing else; depth, scatter and timing are differences.
        mag = mag - float(np.nanmedian(mag))
        ok = np.isfinite(jd) & np.isfinite(mag)
        n_unmeasured = int(n_frames - ok.sum())
        if int(ok.sum()) < 5:
            # Say WHICH ingredient is missing.  This exact exit once fired
            # silently with 83 good magnitudes and zero good time stamps,
            # and the only visible symptom was Siril's fallback running
            # after the aperture table had already been printed.
            n_t = int(np.isfinite(jd).sum())
            n_m = int(np.isfinite(mag).sum())
            self._emit(
                f"  This script measured {n_m} magnitude(s) but has "
                f"usable time stamps for only {n_t} frame(s) — a curve "
                "needs both, so Siril's light_curve takes over.",
                LogColor.SALMON)
            return None
        # Every missing frame is named.  73 frames once vanished from a
        # flat-calibrated run with no reason attached — the ensemble had
        # clipped, the log said nothing, and the count only surfaced by
        # comparing two runs by hand.
        ens_lost = int(np.sum(np.isfinite(flux[r_best][0])
                              & ~np.isfinite(mag)))
        loss_bits = []
        if sat_dropped:
            loss_bits.append(f"{sat_dropped} frame(s) dropped for a "
                             "clipped target core")
        if tgt_lost_cen:
            loss_bits.append(f"target centroid lost on {tgt_lost_cen}")
        if tgt_lost_ap:
            loss_bits.append(f"target aperture unmeasurable on "
                             f"{tgt_lost_ap}")
        if ens_lost:
            loss_bits.append(f"{ens_lost} frame(s) lost because every "
                             "kept comp was missing or clipped there")
        if unreadable:
            loss_bits.append(f"{unreadable} unreadable")
        self._emit(
            f"  {int(ok.sum())} photometric point(s) measured by this "
            f"script — every star re-centroided per frame, the follow-star "
            f"idea light_curve lacks"
            + ("; " + "; ".join(loss_bits) if loss_bits else "")
            + ".", LogColor.GREEN)
        e = np.where(np.isfinite(err[ok]), err[ok], np.nanmedian(err[ok]))
        self._hops_photometry = {"rel": _rel[ok], "rel_err": _rel_err[ok],
                                 "n_comps": len(_cf)}
        return jd[ok], mag[ok], e, n_unmeasured, comp_rows, aper_rows

    def _run_light_curve(self, seq: str, target_xy, comps,
                         autoring=None, quiet: bool = False) -> None:
        """Hand the positions to Siril's own aperture photometry."""
        ring = (bool(self.opts.get("autoring", True))
                if autoring is None else bool(autoring))
        if ring and self._ref_fwhm > 0.0:
            # What `-autoring` would have done, done here instead, because
            # the flag itself makes light_curve abort (see
            # `light_curve_args`).  Siril's own factors, its own
            # arithmetic: it logs "ring radii to 7.5 and 11.3 (FWHM is
            # 1.797542)" and 1.797542 x 4.2 = 7.55, x 6.3 = 11.32.
            try:
                self._cmd("setphot",
                          f"-inner={AUTORING_INNER_FWHM * self._ref_fwhm:.2f}",
                          f"-outer={AUTORING_OUTER_FWHM * self._ref_fwhm:.2f}")
            except (CommandError, DataError, SirilError) as exc:
                _log_swallowed(exc)
        args = light_curve_args(seq, self.opts.get("channel", 0),
                                ring, target_xy, comps)
        if not quiet:
            self._emit("  " + " ".join(args), LogColor.BLUE)
        self._cmd(*args)

    def _measure_curve(self, seq: str, target_xy, comps, autoring: bool,
                       proc: str):
        """Run Siril's photometry once and return ``(jd, mag, err)``.

        Any failure returns empty arrays rather than raising: this is a
        PROBE, called a dozen times by the comparison screen and the
        aperture scan, and one bad geometry should not end the run.

        But repeated identical failures are not independent trials.  A
        run on EXOTIC's demo set failed all twelve calls -- every one for
        the same reason, a reference star that drifts off the sensor --
        and Siril's process then died, leaving a "Broken pipe" the script
        could only report as somebody else's crash.  After
        MAX_PHOTOMETRY_FAILURES in a row the probes stop and say why,
        because the thirteenth call cannot succeed where twelve failed and
        each one is a chance to take Siril down with it.
        """
        if self._photometry_failures >= MAX_PHOTOMETRY_FAILURES:
            return np.empty(0), np.empty(0), np.empty(0)
        try:
            dat = self._run_light_curve(seq, target_xy, comps, autoring, proc)
            if dat is None:
                self._photometry_failures += 1
                self._note_photometry_failure()
                return np.empty(0), np.empty(0), np.empty(0)
            jd, mag, err = _parse_light_curve_dat(dat)
            self._photometry_failures = 0
            return jd, mag, err
        except Exception as exc:            # noqa: BLE001 -- probe only
            _log_swallowed(exc)
            self._photometry_failures += 1
            self._note_photometry_failure()
            return np.empty(0), np.empty(0), np.empty(0)

    def _note_photometry_failure(self) -> None:
        """Say it once, when the run of failures becomes a diagnosis."""
        if self._photometry_failures != MAX_PHOTOMETRY_FAILURES:
            return
        self._emit(
            f"  {MAX_PHOTOMETRY_FAILURES} photometry calls in a row failed. "
            "That is not a bad frame or an unlucky aperture — it is the "
            "same geometry failing every time, and the remaining probes "
            "are skipped. The usual cause is a measurement box that leaves "
            "the sensor as the field drifts; the drift and the stars "
            "dropped for it are listed above.", LogColor.RED)

    def _screen_comparisons(self, seq: str, comps, proc: str):
        """Drop comparison stars that are variable, by MEASURING them.

        Each candidate is photometered against the OTHERS -- exactly the
        differential measurement the target gets -- and judged on the
        robust scatter of its own curve.  A star that wobbles against its
        peers writes that wobble, inverted, into the target's curve, and
        nothing else in this script would ever notice.

        No catalogue and no network: a variability flag from VSX would be
        better where it exists, but the star has to be IN the catalogue,
        and the ones that ruin an amateur light curve usually are not.
        The measurement needs neither.

        Returns ``(kept, rows)``; ``rows`` is ``(x, y, rms_mmag, verdict)``
        for every candidate, so the report can show the ones that passed
        as well as the ones that did not.
        """
        rows = []
        if len(comps) < 3:
            return list(comps), rows
        scatters = []
        for i, comp in enumerate(comps):
            others = [c for j, c in enumerate(comps) if j != i]
            jd, mag, _e = self._measure_curve(seq, (comp[0], comp[1]), others,
                                              True, proc)
            rms = _mad_std(mag) * 1000.0 if jd.size >= 5 else float("nan")
            scatters.append(rms)
        finite = [r for r in scatters if np.isfinite(r)]
        if len(finite) < 3:
            return list(comps), [(c[0], c[1], scatters[i], "not measured")
                                 for i, c in enumerate(comps)]
        # The floor is the ensemble's own median scatter, not an absolute
        # number of millimagnitudes: a bright night and a poor one differ
        # by a factor, and a fixed threshold would reject everything on one
        # and nothing on the other.
        floor = float(np.median(finite))
        kept = []
        for i, comp in enumerate(comps):
            rms = scatters[i]
            if not np.isfinite(rms):
                kept.append(comp)
                rows.append((comp[0], comp[1], rms, "kept (not measured)"))
            elif rms > COMP_VARIABILITY_RATIO * floor:
                # No "keep at least N" clause here: the MIN_COMPS check
                # below reverts every drop when too few would remain,
                # and a running count made the last-listed comp immune
                # whenever the earlier ones were all kept.
                rows.append((comp[0], comp[1], rms,
                             f"DROPPED — {rms / floor:.1f}x the ensemble "
                             f"median of {floor:.1f} mmag"))
            else:
                kept.append(comp)
                rows.append((comp[0], comp[1], rms, "kept"))
        if len(kept) < MIN_COMPS:
            # Refusing to measure at all is worse than measuring with a
            # suspect comp, as long as the suspicion is on the record.
            return list(comps), rows + [(0.0, 0.0, float("nan"),
                                         "all drops reverted: fewer than "
                                         f"{MIN_COMPS} would have been left")]
        return kept, rows

    def _scan_aperture(self, seq: str, target_xy, comps, fwhm: float,
                       proc: str):
        """Find the aperture radius with the least scatter.

        The single most influential number in aperture photometry, and it
        was never chosen here: `-autoring` sets one pair of radii from the
        frame's FWHM and that was that.  Too small loses a
        seeing-dependent share of the star, which is a systematic that
        moves with the night; too large collects sky and neighbours.  The
        optimum sits between and depends on the data.

        The criterion is the robust scatter of the differential curve --
        but ONLY among candidates that measured a comparable number of
        frames.  Least-scatter alone rewards an aperture that drops the
        hard frames: with a 3x seeing swing and identical underlying
        noise, a candidate surviving on 7% of frames shows 3.81 mmag where
        the full sample shows 8.08.  The winner would be the one that
        measured the least, and its "low scatter" would be a selected
        sample rather than a better aperture.

        Returns ``(aperture_px, inner, outer, rows)`` or ``None`` to leave
        `-autoring` in charge.
        """
        fwhm = max(0.5, float(fwhm))
        rows = []
        for mult in APERTURE_SCAN_FWHM:
            aper = mult * fwhm
            inner, outer = APERTURE_INNER_RATIO * aper, APERTURE_OUTER_RATIO * aper
            try:
                self._cmd("setphot", f"-aperture={aper:.2f}",
                          f"-inner={inner:.2f}", f"-outer={outer:.2f}")
            except Exception as exc:        # noqa: BLE001
                _log_swallowed(exc)
                return None
            jd, mag, _e = self._measure_curve(seq, target_xy, comps, False,
                                              proc)
            # Point-to-point, never total scatter: total scatter counts
            # the transit itself, so an aperture that admits a neighbour
            # and halves the depth would win by "less scatter".
            rms = (point_to_point_sigma(mag) * 1000.0 if jd.size >= 5
                   else float("nan"))
            rows.append((aper, int(jd.size), rms))
        # Two passes, because eligibility depends on the best yield and that
        # is only known once every candidate has been measured.
        usable = [(a, n, r) for a, n, r in rows if n >= 5 and np.isfinite(r)]
        if not usable:
            return None
        top = max(n for _a, n, _r in usable)
        floor = APERTURE_MIN_YIELD_RATIO * top
        eligible = [(a, n, r) for a, n, r in usable if n >= floor]
        dropped = [(a, n) for a, n, _r in usable if n < floor]
        if dropped:
            self._emit(
                "    " + ", ".join(f"{a:.2f} px ({n} pt)" for a, n in dropped)
                + f" not compared — under {APERTURE_MIN_YIELD_RATIO:.0%} of "
                  f"the best yield ({top}). Fewer frames measured is a "
                  "seeing-selected sample, and its scatter reads low for "
                  "that reason alone.", LogColor.SALMON)
        aper, _n, _rms = min(eligible, key=lambda t: (t[2], -t[1]))
        return (aper, APERTURE_INNER_RATIO * aper,
                APERTURE_OUTER_RATIO * aper, rows)

    # -- analysis ---------------------------------------------------------
    def _resolve_from_name(self, infos):
        """Find the target without asking you to type coordinates.

        Two independent sources, and the ORDER matters.

        **The headers first.**  N.I.N.A. writes OBJCTRA/OBJCTDEC — the
        object's position, not the telescope's — and on this run all 178
        lights carry it identically, 5.7" x 0.2" from the archive.  Under
        three pixels, already on the disk, no network, and it cannot be
        wrong about which target the folder holds.  A lookup that has to
        reach the internet to learn something the file already says is the
        wrong default.

        **The archive second**, for the ephemeris the header cannot carry:
        period and epoch, which is what O-C needs and what makes a single
        night worth submitting.  It also cross-checks the position, and a
        disagreement is reported rather than silently resolved — the two
        describing different things is exactly what a wrong OBJECT looks
        like.

        Whatever comes out, `pick_target` still reports its separation
        from a real DETECTED star, so nothing here can mis-point quietly.
        """
        hdr_ra, hdr_dec, hdr_note = header_target_radec(infos)
        typed_radec = self.opts.get("target_radec")
        if hdr_ra is None:
            self._emit(f"  Target position not in the headers — {hdr_note}.",
                       LogColor.BLUE)
        elif not typed_radec:
            self.opts["target_radec"] = (hdr_ra, hdr_dec)
            self.opts["target_mode"] = "radec"
            self.opts["radec_auto"] = True
            self.opts["target_ra_deg"] = hdr_ra
            self.opts["target_dec_deg"] = hdr_dec
            self._emit(f"  Target from OBJCTRA/OBJCTDEC in your lights: RA "
                       f"{hdr_ra:.5f}°, Dec {hdr_dec:+.5f}° ({hdr_note}). "
                       "No lookup needed for the position.", LogColor.GREEN)
        else:
            # Saying nothing here would be the worst of the three: the
            # headers WERE read, they do carry a position, and the run
            # quietly used a different one.  A stored RA/Dec left over
            # from the previous target is exactly how that goes wrong.
            if self.opts.get("target_mode") == "auto":
                self.opts["target_mode"] = "radec"
                self.opts["radec_auto"] = True
            gap = angular_sep_arcsec(hdr_ra, hdr_dec,
                                     float(typed_radec[0]),
                                     float(typed_radec[1]))
            if gap > TARGET_DISAGREE_ARCSEC:
                self._emit(
                    f"  Using the RA/Dec in the form, but it is {gap:.0f}\" "
                    f"from what OBJCTRA/OBJCTDEC in your lights say ({hdr_ra:.5f}"
                    f"°, {hdr_dec:+.5f}°). Clear the fields to use the headers "
                    "— a coordinate left over from the previous target looks "
                    "exactly like this.", LogColor.RED)
            else:
                self._emit(f"  Using the RA/Dec in the form; your lights agree "
                           f"to {gap:.1f}\".", LogColor.BLUE)

        if not self.opts.get("resolve_target", True):
            return None
        typed = str(self.opts.get("target_name", "") or "").strip()
        from_hdr = ""
        for info in infos:
            kind = (info.get("kind") or "").strip().lower()
            if (not kind or kind == KIND_LIGHT.lower()) and info.get("object"):
                from_hdr = str(info["object"]).strip()
                break
        # The FRAMES first, the box second.  The box is restored from the
        # last session's settings, so after switching targets it holds the
        # PREVIOUS name — and that is exactly how a WASP-75b run got
        # HAT-P-32's ephemeris: the stale box outranked an OBJECT card
        # that was right all along.  OBJECT came with these frames and
        # cannot be about a different folder; the typed name stays as the
        # fallback for headers whose OBJECT is junk or unknown to the
        # archive.
        name = from_hdr or typed
        if not name:
            return None
        planet = normalise_planet_name(name)
        source = "OBJECT in the lights" if from_hdr else "the Target box"
        typed_planet = normalise_planet_name(typed)
        names_differ = (bool(from_hdr) and bool(typed_planet)
                        and target_key(typed) != target_key(from_hdr))
        if names_differ:
            self._emit(
                f"  The Target box says {typed_planet!r} but the lights "
                f"carry OBJECT = {planet!r}. The headers win — they came "
                "with these frames, and a box entry left over from the "
                "previous target looks exactly like this. Clear or retype "
                "the box to override.", LogColor.SALMON)

        def _lookup(pl, src):
            cache = self._target_cache()
            hit = cache.get(pl.upper())
            stale = None
            if hit and hit.get("schema") != TARGET_CACHE_SCHEMA:
                # Cached before the lookup fetched the orbit columns
                # (1.0.7): the entry is not wrong, it is incomplete, and
                # HOPS mode would derive a/R* from the duration with the
                # real value sitting one query away.
                stale, hit = hit, None
                self._emit(f"  {pl} — the cached ephemeris predates this "
                           "version (no orbit columns); refreshing from "
                           "the archive…", LogColor.BLUE)
            if hit:
                self._emit(f"  {pl} — ephemeris from the local cache "
                           f"(name from {src}).", LogColor.BLUE)
                # A cached false positive is still a false positive — the
                # warning must not be a first-run-only event.
                if str(hit.get("disposition") or "").upper() in ("FP",
                                                                 "FA"):
                    self._emit(
                        "  TFOPWG calls this signal a false positive: a "
                        "'transit' matching this ephemeris is most likely "
                        "NOT a planet.", LogColor.RED)
                return hit, ""
            self._emit(f"  Looking up {pl} at the NASA Exoplanet "
                       f"Archive for the ephemeris (name from {src})…",
                       LogColor.BLUE)
            found, why = archive_lookup(pl)
            if not found and looks_like_toi(pl):
                # TOI-XXXX.01 is a CANDIDATE designation — the confirmed-
                # planet table cannot know it, and losing the whole
                # ephemeris to that was a spelling nobody got wrong.
                self._emit(f"  {why} — but that is a TESS candidate "
                           "designation; asking the archive's TOI list "
                           "instead…", LogColor.BLUE)
                found, why = toi_lookup(pl)
                if found:
                    disp = str(found.get("disposition") or "").upper()
                    label = _TOI_DISPOSITIONS.get(disp, disp or "unknown")
                    bad = disp in ("FP", "FA")
                    self._emit(f"  Found in the TOI list — TFOPWG "
                               f"disposition: {disp or '—'} ({label}).",
                               LogColor.RED if bad else LogColor.BLUE)
                    if bad:
                        self._emit(
                            "  The working group calls this signal a "
                            "false positive: a 'transit' matching this "
                            "ephemeris is most likely NOT a planet. The "
                            "measurement below still stands as "
                            "photometry.", LogColor.RED)
            if found:
                found["schema"] = TARGET_CACHE_SCHEMA
                cache[pl.upper()] = found
                self._store_target_cache(cache)
            elif stale:
                self._emit("  The archive could not be reached — using "
                           "the older cached ephemeris (no orbit columns).",
                           LogColor.SALMON)
                return stale, ""
            return found, why

        eph, note = _lookup(planet, source)
        if not eph and names_differ:
            # OBJECT can be junk ("Target", a mosaic panel name) — that is
            # what the typed name is FOR, so a failed header name falls
            # back instead of ending the lookup.
            self._emit(f"  {note} — trying the Target box name instead.",
                       LogColor.SALMON)
            planet, source = typed_planet, "the Target box"
            eph, note = _lookup(planet, source)
        if not eph:
            self._emit(f"  {note}. The position above still stands; only "
                       "the O−C against a published ephemeris is lost.",
                       LogColor.SALMON)
            return None
        self.opts["resolved_target_name"] = str(eph.get("name") or planet)

        if hdr_ra is not None:
            sep = angular_sep_arcsec(hdr_ra, hdr_dec,
                                     eph["ra_deg"], eph["dec_deg"])
            if sep > TARGET_DISAGREE_ARCSEC:
                self._emit(
                    f"  The headers and the archive disagree by {sep:.0f}\" "
                    f"about where {planet} is. The headers win — they came "
                    "with these frames — but check the OBJECT name, because "
                    "that gap means the two are describing different things "
                    "and the ephemeris below may belong to another planet.",
                    LogColor.RED)
            else:
                self._emit(f"  Archive agrees with the headers to "
                           f"{sep:.1f}\".", LogColor.BLUE)
        else:
            # No position in the headers, but the archive has one for the
            # planet the frames NAME.  A coordinate already sitting in the
            # form outranked it here once — and it was the previous
            # target's, silently kept because these headers carry no
            # OBJCTRA/OBJCTDEC for the probe to correct it against.  The
            # archive position of the frames' own OBJECT is the better
            # authority; a form coordinate survives only when it agrees.
            typed_pos = self.opts.get("target_radec")
            gap = (angular_sep_arcsec(float(typed_pos[0]),
                                      float(typed_pos[1]),
                                      eph["ra_deg"], eph["dec_deg"])
                   if typed_pos else float("inf"))
            if typed_pos and np.isfinite(gap) \
                    and gap <= TARGET_DISAGREE_ARCSEC:
                if self.opts.get("target_mode") == "auto":
                    self.opts["target_mode"] = "radec"
                    self.opts["radec_auto"] = True
                self._emit(f"  The RA/Dec in the form agrees with the "
                           f"archive to {gap:.1f}\".", LogColor.BLUE)
            else:
                if typed_pos:
                    self._emit(
                        f"  The RA/Dec in the form is {gap:.0f}\" from "
                        f"where the archive puts {planet} — the OBJECT in "
                        "your lights. That form coordinate is the previous "
                        "target (these headers carry no position to correct "
                        "it against), so the archive position is used.",
                        LogColor.RED)
                self.opts["target_radec"] = (eph["ra_deg"], eph["dec_deg"])
                self.opts["target_mode"] = "radec"
                self.opts["radec_auto"] = True
                self.opts["target_ra_deg"] = eph["ra_deg"]
                self.opts["target_dec_deg"] = eph["dec_deg"]
                self._emit(f"  Target from the archive: RA "
                           f"{eph['ra_deg']:.5f}°, "
                           f"Dec {eph['dec_deg']:+.5f}° — the next step "
                           "reports how far that lands from a real "
                           "detection.", LogColor.GREEN)
        if eph.get("period_d") and eph.get("t0_bjd"):
            self._emit(f"  Ephemeris: P = {eph['period_d']:.6f} d, "
                       f"T0 = {eph['t0_bjd']:.5f} BJD"
                       + (f", depth {eph['depth_pct']:.3f} %"
                          if eph.get("depth_pct") else "") + ".",
                       LogColor.BLUE)
        return eph

    def _target_cache(self) -> dict:
        """Everything looked up so far, keyed by upper-case planet name."""
        try:
            raw = QSettings(SETTINGS_ORG, SETTINGS_APP).value(
                "target_cache", "") or ""
            got = json.loads(raw) if raw else {}
            return got if isinstance(got, dict) else {}
        except Exception as exc:                   # noqa: BLE001
            _log_swallowed(exc)
            return {}

    def _store_target_cache(self, cache: dict) -> None:
        try:
            QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(
                "target_cache", json.dumps(cache))
        except Exception as exc:                   # noqa: BLE001
            _log_swallowed(exc)

    def _airmass_series(self, jd):
        """Airmass per point, or ``(None, reason)`` when it cannot be had.

        Needs the target's sky position and the site.  Both are optional in
        the UI, and a missing one is a reason to skip the detrend and SAY
        so, not to invent a coordinate.
        """
        ra = self.opts.get("target_ra_deg")
        dec = self.opts.get("target_dec_deg")
        lat = self.opts.get("site_lat_deg")
        lon = self.opts.get("site_lon_deg")
        missing = [name for name, v in (("target RA/Dec", ra), ("target RA/Dec", dec),
                                        ("site latitude", lat), ("site longitude", lon))
                   if v is None or not np.isfinite(v)]
        if missing:
            uniq = []
            for m in missing:
                if m not in uniq:
                    uniq.append(m)
            return None, "no " + " and no ".join(uniq)
        alts = np.asarray([_altitude_deg(float(t), ra, dec, lat, lon) for t in jd])
        X = np.asarray([_airmass(a) for a in alts])
        if not np.any(np.isfinite(X)):
            return None, "the target is below the horizon for every frame"
        if float(np.nanmax(X) - np.nanmin(X)) < 0.01:
            return X, "the airmass barely moves across the run — nothing to remove"
        return X, ""

    # -- main -------------------------------------------------------------
    def run(self) -> None:
        try:
            self._run()
        except (CommandError, DataError, SirilError) as exc:
            # A broken pipe is not a refusal: Siril's process is GONE.
            # Reporting the errno verbatim sends the reader looking for a
            # bug in the command that happened to be in flight, which is
            # the one thing that cannot be at fault any more.
            drift = getattr(self, "_drift", None)
            if "light_curve" in str(exc) and drift:
                span = max(drift[1] - drift[0], drift[3] - drift[2])
                self._fail(
                    f"Siril would not measure this sequence: {exc}\n\n"
                    f"The field drifts {span:.0f} px across the run. Siril "
                    "moves every measurement box by the registration and "
                    "refuses outright when one of them cannot follow — the "
                    "warning it prints names a FRAME, never the star. Stars "
                    "that would leave the sensor are already excluded here, "
                    "so if this persists the drift is too large for "
                    "photometry on unresampled frames: apply the "
                    "registration first (Siril: `seqapplyreg`) and point "
                    "this script at the resampled sequence, or trim the run "
                    "to the stretch where the field holds still.")
            elif "broken pipe" in str(exc).lower() or "errno 32" in str(exc).lower():
                self._fail(
                    "Siril's process ended while this script was talking to "
                    "it — that is a crash on Siril's side, not a refused "
                    "command. Restart Siril and run again. The log above "
                    "shows how far it got; if the last lines are repeated "
                    "photometry failures, fix the geometry they name first, "
                    "because each retry is another chance to bring Siril "
                    "down.")
            else:
                self._fail(f"Siril refused a command: {exc}")
        except Exception as exc:                       # noqa: BLE001
            self._fail(f"{exc.__class__.__name__}: {exc}\n\n"
                             f"{traceback.format_exc()}")

    def _run(self) -> None:
        folder = self.folder
        self.progress.emit(2, "Reading headers…")
        found = _fits_files(folder)
        if not found:
            self._fail(f"No FITS files under {folder}.")
            return
        # One header read per file, here, and everything downstream works
        # from the result: which frames are lights, which are calibration,
        # and what the lights were taken with.
        infos = [inspect_frame(p) for p in found]
        files_info, inside_calib, split_note = split_frames(infos, inside=True)
        files_info, n_moved = chronological_frames(files_info)
        files = [i["path"] for i in files_info]
        if split_note:
            self._emit(split_note, LogColor.SALMON)
        ts_kind, ts_msg, ts_shift = timestamp_diagnosis(files_info)
        self._timestamp_kind = ts_kind
        self._timestamp_shift_s = float(ts_shift)
        self._emit("  " + ts_msg, LogColor.SALMON
                   if ts_kind in ("mid", "odd") else LogColor.BLUE)
        if n_moved:
            n_undated = sum(1 for i in files_info
                            if not math.isfinite(_jd_from_dateobs(
                                str(i.get("date_obs") or ""))))
            self._emit(
                f"  {n_moved} of {len(files)} light(s) were not in time order "
                "by file name; the sequence is built by DATE-OBS instead, so "
                "'next frame' means 'next exposure' everywhere below."
                + (f" {n_undated} frame(s) without a readable DATE-OBS were "
                   "placed last." if n_undated else ""),
                LogColor.SALMON)
        n_cal = len(inside_calib)
        if n_cal:
            self._emit(f"{len(found)} FITS found: {len(files)} light(s), "
                       f"{n_cal} calibration frame(s) inside your selection.",
                       LogColor.BLUE)
        if len(files) < 10:
            self._fail(
                f"Only {len(files)} light frame(s) under that folder "
                f"({len(found)} FITS in total). A light curve needs a time "
                "series — ten frames is the bare minimum and a real transit "
                "run is hundreds.")
            return
        self._inside_calib = inside_calib
        self._light_infos = files_info

        work = os.path.join(folder, WORK_DIRNAME)
        out_dir = os.path.join(folder, OUT_DIRNAME)
        proc = os.path.join(work, "process")
        if os.path.isdir(work):
            shutil.rmtree(work, ignore_errors=True)
        os.makedirs(proc, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        self.progress.emit(3, "Staging frames…")
        n_staged, staged = self._stage_frames(work, files)
        self._emit(f"{n_staged} of {len(files)} sub(s) staged for photometry.",
                   LogColor.GREEN)
        if n_staged < len(files):
            # The sequence index, the flip boundary and the quality arrays
            # all count staged frames; the header list must count the same.
            staged_set = set(staged)
            files_info = [i for i in files_info if i["path"] in staged_set]
            files = [i["path"] for i in files_info]
            self._light_infos = files_info

        seq = "lights"
        self.progress.emit(10, "Building the sequence…")
        self._cmd("cd", self._q(os.path.join(work, "lights")))
        self._cmd("link", seq, "-out=../process")
        self._cmd("cd", self._q(proc))

        self.progress.emit(15, "Calibrating…")
        seq = self._calibrate(seq, files, folder, out_dir, work)

        self.progress.emit(20, "Registering…")
        self._register(seq)
        self._centre_reference(seq)

        self.progress.emit(35, "Detecting stars on the reference frame…")
        eph = self._resolve_from_name(files_info)
        if self.opts.get("target_mode") == "auto":
            # "From the frames" found nothing usable.  Falling through to
            # brightest is the right behaviour, but it has to be SAID:
            # brightest is a guess, and a guess that looks like a
            # measurement is the failure this whole tool is against.
            self.opts["target_mode"] = "brightest"
            self._emit(
                "  Nothing in the frames names or places the target, so the "
                "BRIGHTEST star is used. That is a guess — it is right "
                "surprisingly often, because a transit host is usually why "
                "the field was framed that way, but check the position "
                "below, or type the planet's name in group 3.",
                LogColor.SALMON)
        stars, ref_path = self._detect_reference_stars(seq, proc)
        self._resolve_site(files)
        fwhm = _median([getattr(st, "fwhmx", 0.0) for st in stars]) or 3.0
        self._ref_fwhm = float(fwhm)
        self._emit(f"  {len(stars)} star(s) detected, median FWHM "
                   f"{fwhm:.2f} px.", LogColor.BLUE)
        flip = self._check_for_flip(seq)

        target = pick_target(
            stars,
            self.opts.get("target_mode", "brightest"),
            want_xy=self.opts.get("target_xy"),
            want_radec=self.opts.get("target_radec"),
        )
        if (target is None and self.opts.get("radec_auto")
                and self.opts.get("target_mode") == "radec"):
            # The RA/Dec came from the headers or the archive, not from the
            # user's own mode choice — so an unsolvable field falls back to
            # the guess it would have made anyway, instead of failing a run
            # the user never asked to plate-solve.
            self._emit(
                "  The sky position could not be matched to a detected star "
                "(these frames carry no plate solve and the reference could "
                "not be solved), so the BRIGHTEST star is used instead. "
                "That is a guess — said as one.", LogColor.SALMON)
            self.opts["target_mode"] = "brightest"
            target = pick_target(stars, "brightest")
        if target is None:
            # Name the actual cause rather than listing every possibility.
            # In RA/Dec mode the only way to get here is that no detected
            # star carries sky coordinates, and that has exactly one
            # meaning: the frames were never plate-solved.  Siril's
            # `findstar` fills ra/dec from the image WCS, so zeros across
            # 800+ stars is not a marginal solve, it is no solve at all.
            if self.opts.get("target_mode") == "radec" and not _any_solved(stars):
                self._fail(
                    "RA/Dec selection needs plate-solved subs. The run tried "
                    "to solve the reference frame itself and could not, and "
                    f"none of the {len(stars)} detected stars carries sky "
                    "coordinates. Either solve the frames first (Siril: "
                    "`seqplatesolve`), or switch the target mode to "
                    "'Brightest star in the field' or 'Pixel position'. The "
                    "RA/Dec fields still feed the airmass detrend either "
                    "way, so you can leave them filled in.")
            else:
                self._fail(
                    "Could not identify the target star among the "
                    f"{len(stars)} detected. Check the coordinates you gave, "
                    "or switch to the brightest-star mode for a first look.")
            return
        tx, ty, how = target
        self._emit(f"  Target at ({tx:.1f}, {ty:.1f}) — {how}.", LogColor.GREEN)

        # The frame's own size, read from the reference rather than
        # assumed: a comparison star is only usable if it stays ON the
        # sensor for the whole run, and that needs both edges.
        # Read from the SEQUENCE, which always carries it, rather than
        # from the reference file.  The file read failed on a real run
        # ("BZERO/BSCALE/BLANK header keywords present. Set memmap=False")
        # and silently switched the whole filter off.
        #
        # This check runs BEFORE the saturation and crowding reports so
        # that, when the brightest-star GUESS lands on a star the drift
        # carries off the sensor, the guess can move and every later
        # verdict describes the star actually measured.
        frame_wh = getattr(self, "_frame_wh", None)
        envelope = getattr(self, "_drift", None)
        if envelope and not frame_wh:
            # Silence here cost a run: the frame size failed to read, the
            # drift filter did nothing, and the only trace was a swallowed
            # NameError three lines earlier.  A guard that quietly does not
            # run is worse than no guard.
            self._emit(
                "  The frame size could not be read, so the drift filter is "
                "OFF for this run. Comparison stars that leave the sensor "
                "will not be caught, and light_curve fails outright when one "
                "does.", LogColor.SALMON)
        if envelope and frame_wh:
            dx0, dx1, dy0, dy1 = envelope
            span = max(dx1 - dx0, dy1 - dy0)
            if span > DRIFT_REPORT_PX:
                self._emit(
                    f"  The field drifts {span:.0f} px across the run "
                    f"(x {dx0:+.0f} to {dx1:+.0f}, y {dy0:+.0f} to "
                    f"{dy1:+.0f}) on a {frame_wh[0]}x{frame_wh[1]} frame. "
                    "Comparison stars that would leave the sensor part-way "
                    "through are dropped: Siril moves each measurement box "
                    "by the registration, and one box that walks off the "
                    "edge fails the WHOLE light_curve command, not just "
                    "that star.", LogColor.SALMON)
            margin = AUTORING_OUTER_FWHM * max(1.0, fwhm)
            if not stays_in_frame(tx, ty, frame_wh[0], frame_wh[1],
                                  envelope, margin):
                switched = None
                if self.opts.get("target_mode") == "brightest":
                    # A GUESS that walks off the chip is a bad guess, not a
                    # bad night: guess again among the stars that survive
                    # the drift.  A target the user actually named or
                    # placed stays a hard stop — swapping THAT star behind
                    # their back would measure the wrong object.
                    survivors = [
                        st for st in stars
                        if stays_in_frame(
                            float(getattr(st, "xpos", 0.0) or 0.0),
                            float(getattr(st, "ypos", 0.0) or 0.0),
                            frame_wh[0], frame_wh[1], envelope, margin)]
                    if survivors:
                        switched = pick_target(survivors, "brightest")
                if switched is None:
                    self._fail(
                        f"The TARGET at ({tx:.0f}, {ty:.0f}) leaves the "
                        f"frame as the field drifts {span:.0f} px. No "
                        "aperture can follow it off the sensor. Trim the "
                        "run to the frames where it is still on the chip, "
                        "or re-shoot with better guiding.")
                    return
                self._emit(
                    f"  The brightest star at ({tx:.0f}, {ty:.0f}) leaves "
                    f"the frame as the field drifts {span:.0f} px — and it "
                    "was only a guess, so the guess moves. If the star "
                    "that drifts off IS your target, trim the run to the "
                    "frames that hold it instead.", LogColor.SALMON)
                tx, ty = switched[0], switched[1]
                how = "brightest star that stays on the sensor all run"
                self._emit(f"  Target at ({tx:.1f}, {ty:.1f}) — {how}.",
                           LogColor.GREEN)

        # Saturation was only ever checked for the COMPARISON stars, on the
        # grounds that a clipped comp turns every cloud into a fake transit.
        # The target needs the same check for a blunter reason: a saturated
        # core carries no flux information at all, and Siril will simply
        # refuse most of the frames.
        #
        # Measured in the PIXELS rather than read from Siril's
        # `has_saturated`.  The flag is right on raw 16-bit frames and stops
        # firing once they have been calibrated to 32-bit float: same
        # saturation, no warning, and a 4% yield reported with no cause
        # attached.  The flag is still consulted as a second opinion, so a
        # frame this cannot read is not silently called clean.
        target_saturated, sat_why = self._target_saturation(ref_path, tx, ty)
        flagged = any(
            bool(getattr(st, "has_saturated", False))
            for st in stars
            if abs(float(getattr(st, "xpos", 0.0) or 0.0) - tx) < 1e-6
            and abs(float(getattr(st, "ypos", 0.0) or 0.0) - ty) < 1e-6)
        if target_saturated is None:
            target_saturated = flagged
            sat_why += f"; fell back to Siril's flag ({flagged})"
        elif flagged and not target_saturated:
            # Siril's flag disagrees with the pixels.  Near the threshold
            # the flag wins -- it knows things about the sensor that a peak
            # value does not.  Far below it does NOT: measured on
            # MicroObservatory data the flag fired on a star peaking at
            # 2.6% of full scale, 38x under the limit, and that false
            # positive is not harmless: it now blocks the AAVSO file and
            # tells the observer to re-shoot a perfectly good night.
            if _sat_fraction(sat_why) is None or \
                    _sat_fraction(sat_why) >= 0.5 * SATURATION_FRACTION:
                target_saturated = True
                sat_why += "; below the pixel threshold but Siril flagged it"
            else:
                sat_why += ("; Siril's saturation flag disagrees, but the "
                            "measured peak is far enough below the limit "
                            "that the pixels win")
        if target_saturated:
            self._emit(
                "  The target is SATURATED — " + sat_why + ". Its core no "
                "longer scales with flux, so the depth measured below is "
                "not trustworthy; shorten the sub-exposure and re-shoot.",
                LogColor.SALMON)

        crowd = crowding_note(stars, tx, ty, fwhm)
        if crowd:
            self._emit("  " + crowd[1], crowd[0])

        comps, comp_reserves, rejected, how_ranked = choose_comparison_stars(
            stars, (tx, ty), int(self.opts.get("n_comps", DEFAULT_N_COMPS)),
            fwhm, float(self.opts.get("min_comp_snr", MIN_COMP_SNR)),
            frame_wh=frame_wh, envelope=envelope)

        # Tally the reasons, not the stars.  865 individual rejection lines
        # is not a diagnosis; "865 x SNR 0 below 20" is one, and it is the
        # line that would have explained the first real run in one glance.
        # Group by the reason with its numbers masked out, but display each
        # group with the numbers put back as min-max ranges -- a literal
        # "607 x N mag fainter" tells nobody how much fainter.
        tally = {}
        for _x, _y, why in rejected:
            key = re.sub(r"[-+]?\d*\.?\d+", "N", why)
            tally.setdefault(key, []).append(why)
        summary = sorted(tally.items(), key=lambda kv: len(kv[1]),
                         reverse=True)

        def _group_label(whys):
            nums = [re.findall(r"[-+]?\d*\.?\d+", w) for w in whys]
            ranges = []
            for slot in zip(*nums):
                vals = sorted(float(v) for v in slot)
                lo, hi = vals[0], vals[-1]
                ranges.append(f"{lo:g}" if lo == hi else f"{lo:g}–{hi:g}")
            it = iter(ranges)
            return re.sub(r"[-+]?\d*\.?\d+", lambda _m: next(it), whys[0])

        if len(comps) < MIN_COMPS:
            lines = "; ".join(f"{len(whys)} x {_group_label(whys)}"
                              for _key, whys in summary[:4])
            self._fail(
                f"Only {len(comps)} usable comparison star(s) after filtering "
                f"(need at least {MIN_COMPS}). Of {len(rejected)} not used: "
                f"{lines}. Selection was {how_ranked}.")
            return
        self._emit(f"  {len(comps)} comparison star(s) chosen "
                   f"({how_ranked}), {len(rejected)} not used.",
                   LogColor.GREEN)
        for _key, whys in summary[:4]:
            self._emit(f"    {len(whys)} x {_group_label(whys)}",
                       LogColor.SALMON)

        # The measurement itself.  This script's own engine first -- it
        # re-centroids every star per frame (follow star), measures all
        # apertures in one pass over the pixels, keeps comps by measured
        # scatter and picks the aperture by point-to-point noise, so the
        # separate comp screen and aperture scan below become the Siril
        # FALLBACK, not the main path.
        native = None
        comp_rows, aper_rows = [], []
        # Everything the results dict reads must exist on BOTH paths.  The
        # native engine's first full run crashed exactly here: `aperture`
        # and `dat` were born inside the Siril fallback branch, and the
        # run died one line before writing its results -- after the fit
        # had already succeeded.
        aperture = None
        dat = None
        if self.opts.get("native_phot", True):
            self.progress.emit(
                42, "Aperture photometry (star-following)…")
            native = self._native_photometry(seq, proc, (tx, ty), comps,
                                             fwhm, comp_reserves)
        if native is not None:
            jd, mag, err, unmeasured, comp_rows, aper_rows = native
            if self.opts.get("fit_mode") == "hops":
                jd, mag, err = self._apply_hops_photometry(jd, mag, err)
            finite_rows = [(r, rms) for r, _n, rms in aper_rows
                           if np.isfinite(rms)]
            if finite_rows:
                aperture = min(finite_rows, key=lambda t: t[1])[0]
        else:
            # Screen the ensemble by measuring it.  Each candidate is
            # photometered against the others; one that wobbles against its
            # peers would write that wobble, inverted, into the target.
            comp_rows = []
            if self.opts.get("screen_comps", True):
                self.progress.emit(42, "Checking the comparison stars…")
                kept, comp_rows = self._screen_comparisons(seq, comps, proc)
                for x, y, rms, verdict in comp_rows:
                    self._emit(f"    ({x:7.1f}, {y:7.1f})  "
                               + ("      —" if not np.isfinite(rms)
                                  else f"{rms:6.1f} mmag")
                               + f"  {verdict}",
                               LogColor.SALMON if "DROP" in verdict
                               else LogColor.BLUE)
                if len(kept) != len(comps):
                    self._emit(f"  {len(comps) - len(kept)} comparison star(s) "
                               "dropped for their own variability.",
                               LogColor.SALMON)
                    comps = kept

            # The aperture is the most influential number in aperture
            # photometry and used to be whatever -autoring picked.  Try a few.
            aper_rows = []
            aperture = None
            if self.opts.get("scan_aperture", True):
                self.progress.emit(44, "Choosing the aperture…")
                got = self._scan_aperture(seq, (tx, ty), comps, fwhm, proc)
                if got:
                    aper, inner, outer, aper_rows = got
                    for a, n, rms in aper_rows:
                        self._emit(f"    aperture {a:5.2f} px  {n:4d} point(s)  "
                                   + ("     —" if not np.isfinite(rms)
                                      else f"{rms:6.2f} mmag")
                                   + ("   <-- chosen" if abs(a - aper) < 1e-9
                                      else ""), LogColor.BLUE)
                    self._cmd("setphot", f"-aperture={aper:.2f}",
                              f"-inner={inner:.2f}", f"-outer={outer:.2f}")
                    aperture = aper
                    self._emit(f"  Aperture {aper:.2f} px "
                               f"({aper / max(fwhm, 1e-9):.2f} x FWHM), sky "
                               f"annulus {inner:.2f}-{outer:.2f} px.",
                               LogColor.GREEN)
                else:
                    # Hand the aperture back to Siril.  Without this the run
                    # measures with the LAST APERTURE THE SCAN TRIED -- one it
                    # just rejected -- because `setphot -aperture=` forces the
                    # value and nothing unforces it.  Seen on a real run: the
                    # scan probed down to 4.7 px, found nothing usable, and the
                    # final photometry then ran at 4.7 anyway.  `-dyn_ratio`
                    # restores the dynamic aperture (radius / half-FWHM);
                    # verified against Siril 1.4.4, which then reports
                    # "dynamic aperture: 4.0 (times the half-FWHM)" instead of
                    # "aperture: 4.7 (forced)".
                    try:
                        self._cmd("setphot", f"-dyn_ratio={DYNAMIC_APERTURE_RATIO}")
                    except (CommandError, DataError, SirilError) as exc:
                        _log_swallowed(exc)
                    self._emit("  Aperture scan produced nothing usable; the "
                               "aperture goes back to Siril's dynamic one and "
                               "the FWHM-derived rings stay in charge.",
                               LogColor.SALMON)

            self.progress.emit(45, "Aperture photometry (Siril)…")
            self._run_light_curve(seq, (tx, ty), comps,
                                  autoring=(aperture is None))

            dat = os.path.join(proc, "light_curve.dat")
            if not os.path.exists(dat):
                self._fail(
                    "Siril's light_curve produced no light_curve.dat. The usual "
                    "cause is that one of the comparison stars could not be "
                    "measured in enough frames — Siril rejects the whole run in "
                    "that case. Try fewer comps or a higher SNR floor.")
                return
            jd, mag, err, unmeasured = _parse_light_curve_dat(dat)
            if jd.size == 0:
                self._fail(
                    f"light_curve.dat holds {unmeasured} row(s) but not one "
                    "carries a measurement — every V-C is nan. Siril wrote a "
                    "line per frame it attempted and could not photometer any "
                    "of them; with a saturated target that is the expected "
                    f"outcome. ({dat})" if unmeasured else
                    f"light_curve.dat exists but no data rows could be read from "
                    f"it ({dat}). This is a format the parser does not recognise "
                    "— please report it with the file.")
                return
            self._emit(f"  {jd.size} photometric point(s) from Siril"
                       + (f" ({unmeasured} further row(s) carried no measurement "
                          "and were dropped)." if unmeasured else "."),
                       LogColor.GREEN)
            # Siril stamps DATE-OBS + EXPTIME/2.  On a program that
            # stamps mid-exposure that is half an exposure late; the
            # header diagnosis measured the correction, so apply it here
            # and the Siril path lands on the same times as the native one.
            ts_shift = float(getattr(self, "_timestamp_shift_s", 0.0) or 0.0)
            if abs(ts_shift) >= 0.5:
                jd = jd + ts_shift / 86400.0
                self._emit(f"  Siril's times (DATE-OBS + EXPTIME/2) shifted by "
                           f"{ts_shift:+.1f} s to the mid-exposure convention "
                           "the headers established.", LogColor.SALMON)

        severity, note = photometry_yield_note(
            int(jd.size), len(files), target_saturated,
            engine="This script" if native is not None else "Siril")
        if note:
            self._emit("  " + note,
                       LogColor.RED if severity == "bad" else LogColor.SALMON)
        yield_note = note

        # Spike rejection, model-free, before anything is fitted.  A
        # satellite through the aperture is one frame; a transit is
        # hundreds.  Measured: a single 100 mmag point on a real 12 mmag
        # transit took the significance from 12.1 to 3.2 sigma, and
        # removing it puts it back at 12.1.
        keep, n_clipped, clip_note = sigma_clip_series(jd, mag)
        # The rejected points are KEPT for the plot, as red crosses: a
        # reader should see what was thrown away and judge for themselves
        # that it was a spike, not an egress.  They stay out of every
        # calculation.
        clip_jd = jd[~keep].copy() if n_clipped else np.empty(0)
        clip_mag = mag[~keep].copy() if n_clipped else np.empty(0)
        if n_clipped:
            jd, mag, err = jd[keep], mag[keep], err[keep]
            self._emit(f"  {clip_note}.", LogColor.SALMON)
        elif clip_note:
            self._emit(f"  No points removed — {clip_note}.", LogColor.SALMON)

        # Convert to BJD_TDB before anything is FITTED.  The airmass below
        # deliberately stays on JD_UTC -- it is a question about where the
        # Earth is pointing, not about the barycentre -- but T0 has to come
        # out in the system every published ephemeris uses, or it cannot be
        # compared with one at all.
        jd_utc = jd.copy()
        radec = self.opts.get("target_radec")
        bjd, time_note = to_bjd_tdb(
            jd_utc,
            radec[0] if radec else None, radec[1] if radec else None,
            self.opts.get("site_lat_deg"), self.opts.get("site_lon_deg"),
            self.opts.get("site_height_m", 0.0) or 0.0)
        if bjd is None:
            time_system = "JD_UTC"
            self._emit(f"  Times stay in JD_UTC — {time_note}. T0 below is "
                       "therefore NOT comparable with a published ephemeris, "
                       "which quotes BJD_TDB; the offset is up to 8 minutes.",
                       LogColor.SALMON)
            bjd = jd_utc
        else:
            time_system = "BJD_TDB"
            self._emit(f"  {time_note}.", LogColor.BLUE)
        # The clipped points ride along on the same axis: the mean offset
        # is exact to well under a second across one night, and they are
        # display-only marks, not measurements.
        if clip_jd.size and bjd is not None and jd_utc.size:
            clip_jd = clip_jd + float(np.mean(bjd - jd_utc))
        jd = bjd

        self.progress.emit(70, "Detrending and fitting…")
        raw_mag = mag.copy()
        # Enforce, once, the invariant every consumer downstream relies
        # on: jd, mag and err are the same length and finite.  The fit
        # filters internally by its own good-mask and returns arrays of
        # the FILTERED size; the writers then index them with the full
        # jd.  Both engines happen to deliver finite rows today, but a
        # single NaN would silently misalign every column after it — the
        # CSV would pair times with the wrong magnitudes and no one could
        # tell by looking.
        finite = np.isfinite(jd) & np.isfinite(mag)
        if not finite.all():
            self._emit(f"  {int((~finite).sum())} row(s) without a finite "
                       "time or magnitude dropped before analysis.",
                       LogColor.SALMON)
            jd, mag = jd[finite], mag[finite]
            err = err[finite] if err.size == finite.size else err
            # The UTC copy feeds the airmass, the flip step and the
            # quality pairing; left unfiltered it would be one row longer
            # than the curve on exactly the branch this guard exists for.
            jd_utc = jd_utc[finite] if jd_utc.size == finite.size else jd_utc
            raw_mag = raw_mag[finite] if raw_mag.size == finite.size else raw_mag
        # Centre on the median so the curve reads as a delta and the plot
        # does not depend on the arbitrary comp-ensemble zero point.  The
        # clipped points get the SAME shift, or their crosses would float
        # on the old zero point.
        _zero = _median(mag)
        mag = mag - _zero
        if clip_mag.size:
            clip_mag = clip_mag - _zero
        raw_rms = _mad_std(mag) * 1000.0

        X, airmass_note = self._airmass_series(jd_utc)

        # Every basis the fit may use, gathered in one place.  Airmass from
        # the sky position and the site; seeing, sky level and star count
        # from Siril's own per-frame registration data, paired to the rows
        # Siril managed to photometer by mid-exposure time.
        bases = {}
        multi_note = ""
        if X is not None and self.opts.get("detrend_airmass", True) \
                and not airmass_note:
            bases["airmass"] = X
        elif self.opts.get("detrend_airmass", True) and airmass_note:
            # The Result tab and the report carry this reason too, but the
            # log is where a run is read first — and a basis that was
            # promised by the checkbox and then vanishes without a word
            # looks like a bug, not a decision.  One real run sat exactly
            # there: site given, target below the horizon at those times
            # (wrong site for borrowed data), and the log showed three
            # bases where four were expected, commentless.
            self._emit(f"  Airmass basis skipped: {airmass_note}.",
                       LogColor.SALMON)
        quality = getattr(self, "_frame_quality", None)
        if quality and self.opts.get("detrend_quality", True):
            jd_frames = []
            for info in getattr(self, "_light_infos", []):
                # The same convention as the curve's own times: DATE-AVG
                # when present.  DATE-OBS + exp/2 here and DATE-AVG there
                # paired nothing on a mid-stamping program.
                jd_frames.append(mid_exposure_jd(
                    info.get("date_obs") or "", info.get("exp_s") or 0.0,
                    info.get("date_avg") or "", info.get("date_end") or "")[0])
            idx = match_frames_to_curve(jd_utc, np.asarray(jd_frames,
                                                           dtype=float))
            hit = int(np.count_nonzero(idx >= 0))
            if hit < MULTI_DETREND_MIN_ANCHOR:
                multi_note = (f"only {hit} of {jd.size} point(s) could be "
                              "paired with a frame")
            else:
                for name in ("fwhm", "sky", "n_stars"):
                    arr = quality.get(name)
                    if arr is None or arr.size == 0:
                        continue
                    col = np.full(jd.size, np.nan)
                    ok = idx >= 0
                    col[ok] = arr[idx[ok]]
                    bases[name] = col
        # A meridian flip lands the target on a different patch of the
        # sensor: different flat response, different vignette corner, a
        # STEP in the curve at that moment (59 mmag on a TOI-4033 run).
        # A 0/1 step basis lets the fit absorb the offset instead of
        # reading it as half a transit.  Fitted together with the
        # transit like every other basis, so a flip that coincides with
        # ingress shows up as a wide bar, not a silent bias.
        flip_jd = float(getattr(self, "_flip_jd_utc", float("nan")))
        if np.isfinite(flip_jd) and self.opts.get("detrend_quality", True):
            step = (np.asarray(jd_utc, dtype=float) > flip_jd).astype(float)
            n_after = int(step.sum())
            if 5 <= n_after <= jd.size - 5:
                bases["flip"] = step
                self._emit(f"  Flip step basis added: {jd.size - n_after} "
                           f"point(s) before the flip, {n_after} after — "
                           "the offset between the two sensor patches is "
                           "fitted with the transit.", LogColor.BLUE)

        # ONE fit.  The transit and the systematics are solved together, so
        # the transit cannot be absorbed into a basis that correlates with
        # it -- which is what the old three-pass detrend-fit-redetrend-refit
        # sequence had to guard against by anchoring on the out-of-transit
        # rows.  It also carries the baseline's uncertainty into the depth
        # and the mid-time instead of treating the baseline as exact.
        fit = fit_transit(jd, mag, bases=bases,
                          u1=float(self.opts.get("ld_u1", LD_U1)),
                          u2=float(self.opts.get("ld_u2", LD_U2)))
        if fit is not None and self.opts.get("fit_mode") == "hops":
            # The blind fit ran first and keeps the detection verdict;
            # HOPS mode replaces the MEASUREMENT (depth, mid-time, shape)
            # with the ephemeris-locked one.
            fit = self._hops_mode(jd, mag, err, fit, X, eph, time_system,
                                  bases.get("flip")) or fit
        multi_used = list(fit["bases"]) if fit else []
        if fit is not None:
            detrended = fit["detrended"]
            slope = fit["airmass_slope"]
            intercept = fit["baseline"]
            if not multi_note:
                multi_note = fit["base_note"]
            self._emit("  Fitted the transit and "
                       + (f"{len(multi_used)} systematic basis/bases "
                          f"({'+'.join(multi_used)}) " if multi_used
                          else "no systematics ")
                       + "together — the baseline's uncertainty ends up in "
                         "the depth and the mid-time instead of being "
                         "thrown away between passes.", LogColor.GREEN)
            if not fit.get("detected"):
                # The log used to fall silent here, and "the fit ran" with
                # no number after it read like a crash.
                self._emit(
                    f"  No transit claimed: the best template reaches "
                    f"{fit['significance']:.1f} sigma against a "
                    f"{MIN_DETECTION_SIGMA:.1f} sigma floor"
                    + (f" (red-noise beta {fit['red_noise_beta']:.2f}, "
                       f"{fit['significance_white']:.1f} sigma before it)"
                       if fit.get("red_noise_beta", 1.0) > 1.0 else "")
                    + f". It wanted "
                    f"{fit.get('blind_depth_mmag', fit['depth_mmag']):.1f} "
                    f"mmag over "
                    f"{fit.get('blind_duration_h', fit['duration_h']):.2f} h "
                    "— not a measurement, "
                    "printed so 'no detection' and 'nothing ran' look "
                    "different.", LogColor.SALMON)
            if fit.get("detected"):
                # The headline numbers, in the log rather than only the
                # report — and in BOTH depth conventions, labelled.
                self._emit(
                    f"  T0 = {fit['t0']:.5f} ± "
                    + (f"{fit['t0_sigma_s']:.0f} s"
                       if np.isfinite(fit.get("t0_sigma_s", float("nan")))
                       else "?")
                    + f"; central depth {fit['depth_mmag']:.1f} ± "
                      f"{fit['depth_sigma_mmag']:.1f} mmag"
                    + (f"; Rp/Rs = {fit['rprs']:.4f}"
                       + (f" ± {fit['rprs_sigma']:.4f}"
                          if fit.get("rprs_sigma") is not None else "")
                       + f" → (Rp/Rs)² = {fit['depth_rprs2_pct']:.2f} % "
                         "(the EXOTIC/HOPS/AIJ depth convention)"
                       if fit.get("rprs") is not None else "")
                    + f"; {fit['significance']:.1f} sigma.",
                    LogColor.GREEN)
        else:
            # No fit: the plot and the RMS still want a curve, so fall back
            # to the standalone airmass detrend for DISPLAY only.
            detrended, slope, intercept = (
                airmass_detrend(mag, X) if X is not None and not airmass_note
                else (mag, None, None))
            self._emit(
                f"  No transit fit attempted: {jd.size} usable point(s) "
                "cannot constrain a transit (T0, duration, shape, depth, "
                "baseline) plus a baseline on both sides of it. This is "
                "not 'no transit found' — nothing was tested.",
                LogColor.SALMON)
        refined = fit is not None

        self.progress.emit(88, "Writing results…")
        # One line of provenance for the plot title: what was observed,
        # when, how long each sub ran, through which filter.  Every piece
        # is optional — a missing header keyword drops its part, never
        # the title.
        info0 = (getattr(self, "_light_infos", None) or [{}])[0]
        bits = []
        eph_name = (eph or {}).get("name") if isinstance(eph, dict) else None
        name = eph_name or self.opts.get("target_name") or ""
        if name:
            bits.append(str(name))
        stamp = (info0.get("date_obs") or "")[:10]
        if stamp:
            bits.append(stamp)
        if jd.size > 1:
            span_h = (float(np.max(jd)) - float(np.min(jd))) * 24.0
            bits.append(f"{span_h:.1f} h run")
        if info0.get("exp_s"):
            bits.append(f"{float(info0['exp_s']):g} s subs")
        if (info0.get("filter") or "").strip():
            bits.append(f"filter {info0['filter'].strip()}")
        if self.opts.get("site_name"):
            bits.append(str(self.opts["site_name"]))
        result = {
            "title_bits": "  ·  ".join(bits),
            "clip_jd": clip_jd,
            "clip_mag": clip_mag,
            "calib_note": getattr(self, "_calib_note", ""),
            "multi_used": multi_used,
            "multi_note": multi_note,
            "n_clipped": n_clipped,
            "clip_note": clip_note,
            "comp_rows": comp_rows,
            "aper_rows": aper_rows,
            "aperture_px": aperture,
            "folder": folder,
            "out_dir": out_dir,
            "n_files": len(files),
            "n_points": int(jd.size),
            "jd": jd,
            "mag_raw": raw_mag,
            "mag": mag,
            "detrended": detrended,
            "err": err,
            "airmass": X,
            "airmass_note": airmass_note,
            "slope": slope,
            "intercept": intercept,
            "refined": refined,
            "raw_rms_mmag": raw_rms,
            "rms_mmag": _mad_std(detrended) * 1000.0,
            "target_xy": (tx, ty),
            "target_how": how,
            "comps": comps,
            "rejected": rejected,
            "fwhm_px": fwhm,
            "fit": fit,
            "flip_deg": flip,
            "flip_jd_utc": float(getattr(self, "_flip_jd_utc",
                                         float("nan"))),
            "utc_offset_h": utc_offset_hours(
                info0.get("date_obs") or "", info0.get("date_loc") or ""),
            "yield_note": yield_note,
            "yield_severity": severity,
            "target_saturated": bool(target_saturated),
            "ephemeris": eph,
            "filter": (info0.get("filter") or "").strip(),
            "jd_utc": jd_utc,
            "time_system": time_system,
            "time_note": time_note,
            "n_frames": len(files),
            "dat_path": dat,
            "ref_path": ref_path,
            "engine": "native" if native is not None else "siril",
        }
        result["site_lat_deg"] = self.opts.get("site_lat_deg")
        result["site_lon_deg"] = self.opts.get("site_lon_deg")
        self._write_csv(result)
        if self.opts.get("write_aavso", True):
            self._write_aavso(result)
        self.progress.emit(100, "Done.")
        self.finished_ok.emit(result)

    def _write_aavso(self, r: dict) -> None:
        """Write the AAVSO Exoplanet Watch submission file.

        The format is theirs, and every field in it was already being
        computed here -- the run produced a CSV, a plot and a report, and
        then stopped one short of the thing the numbers exist for.

        Written locally, and nothing is sent anywhere: submitting is a
        decision, and it is yours.  Without an observer code the file is
        still written, with the field marked, because the curve is worth
        keeping either way and the code can be filled in later.

        Refused outright when the times are not BJD_TDB.  The header
        declares DATE_TYPE=BJD_TDB, and writing JD_UTC under that label
        would hand a submission an eight-minute error with a straight face.
        """
        # A submission goes into a public database that other people fit
        # ephemerides from, so the bar is higher than for the local report:
        # the report may say "here is what the data allow", a submission may
        # not.  Measured on the run this was written for -- WASP-75, 11 of
        # 178 frames kept, target saturated -- the old gate checked only the
        # time system and wrote the file anyway.
        if r.get("target_saturated"):
            self._emit(
                "  No AAVSO file written: the target is SATURATED, so its "
                "core carries no flux information and the depth is not a "
                "measurement. The local report still shows what the data "
                "allow — a submission would not carry that caveat.",
                LogColor.SALMON)
            return
        if r.get("yield_severity") == "bad":
            self._emit(
                f"  No AAVSO file written: {r.get('n_points', 0)} of "
                f"{r.get('n_frames', 0)} frame(s) survived photometry. The "
                "frames that survive a marginal night are the ones seeing "
                "happened to favour, which is a selected sample, not a "
                "measured one.",
                LogColor.SALMON)
            return
        if r.get("time_system") != "BJD_TDB":
            self._emit("  No AAVSO file written: the times are "
                       f"{r.get('time_system')}, and that format declares "
                       "BJD_TDB. Submitting JD_UTC under that header would "
                       "be an 8 minute error nobody could see.",
                       LogColor.SALMON)
            return
        fit = r.get("fit")
        obscode = str(self.opts.get("obscode", "") or "").strip().upper()
        path = os.path.join(r["out_dir"], "AAVSO_exoplanet.txt")
        partial = path + ".partial"
        X = r["airmass"]
        detr = r["detrended"]
        err = r["err"]
        jd = r["jd"]
        try:
            with open(partial, "w", encoding="utf-8") as fh:
                fh.write("#TYPE=EXOPLANET\n")
                fh.write(f"#OBSCODE={obscode or 'PLEASE_FILL_IN'}\n")
                fh.write(f"#SOFTWARE=Svenesis LightCurve {VERSION}\n")
                fh.write("#DELIM=,\n")
                fh.write("#DATE_TYPE=BJD_TDB\n")
                fh.write(f"#OBSTYPE={self.opts.get('obstype', 'CCD')}\n")
                fh.write(f"#FILTER={self.opts.get('filter_name', '') or 'CV'}\n")
                # The RESOLVED name, not the box: the box can hold the
                # previous target's name, and a submission under the wrong
                # star is worse than one under 'UNKNOWN'.
                fh.write("#TARGET="
                         + (self.opts.get("resolved_target_name")
                            or self.opts.get("target_name", "")
                            or "UNKNOWN") + "\n")
                if r.get("site_lat_deg") is not None:
                    fh.write(f"#SITELAT={r['site_lat_deg']:.4f}\n")
                    fh.write(f"#SITELONG={r['site_lon_deg']:.4f}\n")
                fh.write(f"#COMPS={len(r['comps'])} ensemble, "
                         "instrumental\n")
                if r.get("aperture_px"):
                    fh.write(f"#APERTURE={r['aperture_px']:.2f} px\n")
                if fit is not None and fit.get("detected"):
                    fh.write(f"#TC={fit['t0']:.6f}\n")
                    if np.isfinite(fit.get("t0_sigma_d", float("nan"))):
                        fh.write(f"#TC_ERR={fit['t0_sigma_d']:.6f}\n")
                    fh.write(f"#DEPTH_MMAG={fit['depth_mmag']:.2f}\n")
                    fh.write(f"#DEPTH_ERR_MMAG={fit['depth_sigma_mmag']:.2f}\n")
                    # The convention EXOTIC, HOPS and AstroImageJ quote —
                    # DEPTH_MMAG above is the limb-darkened CENTRAL depth,
                    # ~20% deeper than (Rp/Rs)^2 on a solar-type star.
                    if fit.get("rprs") is not None:
                        fh.write(f"#RPRS={fit['rprs']:.4f}\n")
                        if fit.get("rprs_sigma") is not None:
                            fh.write(f"#RPRS_ERR={fit['rprs_sigma']:.4f}\n")
                        fh.write(f"#DEPTH_RPRS2_PCT="
                                 f"{fit['depth_rprs2_pct']:.3f}\n")
                    fh.write(f"#DURATION_H={fit['duration_h']:.4f}\n")
                # ONE #NOTES line.  The no-transit case used to write its
                # own and then fall through to the detrend line -- two
                # #NOTES keys in one header, and which one a parser keeps
                # is the parser's mood.
                fh.write("#NOTES="
                         + ("no transit claimed; photometry only; "
                            if not (fit is not None and fit.get("detected"))
                            else "")
                         + "Detrend 1 airmass"
                         + (", 2 " + "+".join(r.get("multi_used") or [])
                            if r.get("multi_used") else "")
                         + f"; red-noise beta "
                         + (f"{fit['red_noise_beta']:.2f}" if fit else "n/a")
                         + f"; false alarm at the {MIN_DETECTION_SIGMA:.1f} "
                           f"sigma floor {100 * MEASURED_FALSE_ALARM:.2f}%\n")
                fh.write("#DATE,DIFF,ERR,DETREND_1\n")
                for i in range(jd.size):
                    x = (f"{X[i]:.4f}" if X is not None
                         and np.isfinite(X[i]) else "NA")
                    e = (f"{err[i]:.6f}" if i < err.size
                         and np.isfinite(err[i]) else "NA")
                    fh.write(f"{jd[i]:.6f},{detr[i]:.6f},{e},{x}\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(partial, path)
            self._emit(f"  AAVSO submission file written to {path}"
                       + ("" if obscode else
                          " — fill in #OBSCODE before submitting."),
                       LogColor.GREEN)
        except OSError as exc:
            self._emit(f"  Could not write the AAVSO file: {exc}",
                       LogColor.SALMON)

    def _write_csv(self, r: dict) -> None:
        """Write the series to ``lightcurve/lightcurve.csv``, atomically.

        Atomically because the file is what survives the run: a crash
        halfway through a plain write leaves a truncated CSV that still
        looks like a light curve.  Written to ``.partial``, flushed, fsynced
        and only then moved into place.
        """
        path = os.path.join(r["out_dir"], "lightcurve.csv")
        partial = path + ".partial"
        X = r["airmass"]
        try:
            with open(partial, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["bjd_tdb" if r["time_system"] == "BJD_TDB"
                            else "jd_utc_no_bary",
                            "jd_utc", "diff_mag_raw", "diff_mag_centred",
                            "diff_mag_detrended", "err_mag", "airmass"])
                for i in range(r["n_points"]):
                    w.writerow([
                        f"{r['jd'][i]:.8f}",
                        f"{r['jd_utc'][i]:.8f}",
                        f"{r['mag_raw'][i]:.6f}",
                        f"{r['mag'][i]:.6f}",
                        f"{r['detrended'][i]:.6f}",
                        "" if not np.isfinite(r["err"][i]) else f"{r['err'][i]:.6f}",
                        "" if X is None or not np.isfinite(X[i]) else f"{X[i]:.4f}",
                    ])
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(partial, path)
            r["csv_path"] = path
            self._emit(f"  Light curve written to {path}", LogColor.GREEN)
        except OSError as exc:
            self._emit(f"  Could not write the CSV ({exc}).", LogColor.SALMON)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
class LightCurvePlot(FigureCanvas):
    """Light curve on top, fit residuals below, sharing the time axis.

    Magnitude axes are inverted, as they always are: up is brighter.  A
    transit therefore reads as a dip, which is what everybody expects to
    see and what every other tool in this field draws.
    """

    def __init__(self):
        self.fig = Figure(figsize=(8, 6), facecolor="#2b2b2b")
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self._blank("Run a folder of subs to see its light curve.")

    def _style(self, ax) -> None:
        ax.set_facecolor("#1e1e1e")
        for sp in ax.spines.values():
            sp.set_color("#555555")
        ax.tick_params(colors="#bbbbbb", labelsize=8)
        ax.grid(True, color="#3a3a3a", linewidth=0.5, alpha=0.7)
        ax.xaxis.label.set_color("#cccccc")
        ax.yaxis.label.set_color("#cccccc")
        ax.title.set_color("#88aaff")

    def _blank(self, msg: str) -> None:
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self._style(ax)
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                color="#888888", fontsize=11, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        self.draw()

    def render(self, r: dict, n_bins: int = 0,
               show_err: bool = False,
               show_expected: bool = True) -> None:
        self.fig.clear()
        # Constrained layout must be active BEFORE the figure legend is
        # created below — its "outside" placement is refused otherwise,
        # and only on the FIRST render, which is the worst kind of
        # sometimes.  fig.clear() keeps the engine, so this is
        # idempotent on every later call.
        try:
            self.fig.set_layout_engine("constrained")
        except AttributeError:
            pass
        jd = r["jd"]
        y = r["detrended"]
        fit = r.get("fit")
        t0_ref = float(np.floor(np.min(jd)))
        x = (jd - t0_ref) * 24.0            # hours from the start of that JD

        gs = self.fig.add_gridspec(3, 1, hspace=0.08)
        ax = self.fig.add_subplot(gs[:2, 0])
        axr = self.fig.add_subplot(gs[2, 0], sharex=ax)
        self._style(ax)
        self._style(axr)

        # The bridge from plot time back to the wall clock the user's
        # planning tool speaks.  Plot time is BJD_TDB when the run got
        # that far — the barycentric+TDB offset (several minutes, the
        # same quantity the log announces) must come OFF again before a
        # value may be printed as a clock reading, or every label would
        # be wrong by exactly the correction we were proud of.
        jd_utc_arr = r.get("jd_utc")
        bjd_off = 0.0
        if jd_utc_arr is not None and np.size(jd_utc_arr) == jd.size \
                and jd.size:
            bjd_off = float(np.mean(jd - np.asarray(jd_utc_arr)))
        utc_off = r.get("utc_offset_h")

        def _clock_at(hours):
            return clock_hhmm(t0_ref + hours / 24.0 - bjd_off, utc_off)

        # A second time axis across the top, in HH:MM — local when the
        # headers carried DATE-LOC, UTC otherwise, and the axis SAYS
        # which, because a clock that might be either is worse than no
        # clock.  This is what lets "start 21:50 … flip 00:55" from the
        # planning screenshot be found again on the measurement.
        secax = ax.secondary_xaxis("top")
        secax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _pos: _clock_at(v)))
        secax.set_xlabel(
            ("local clock (UTC%+g)" % utc_off) if utc_off is not None
            else "clock (UTC)", fontsize=8)
        secax.tick_params(colors="#bbbbbb", labelsize=7)
        secax.xaxis.label.set_color("#cccccc")
        for sp in secax.spines.values():
            sp.set_color("#555555")

        # The meridian flip as a vertical marker in BOTH panels, stamped
        # with its clock time — the planner shows "⚠ Flip 00:55" and now
        # the measurement shows the same line, so a step or an 'ingress'
        # can be checked against it by eye instead of by arithmetic.
        flip_jd = r.get("flip_jd_utc")
        if (r.get("flip_deg", 0.0) >= FLIP_ROTATION_DEG
                and flip_jd is not None and np.isfinite(flip_jd)):
            xf = (flip_jd + bjd_off - t0_ref) * 24.0
            for a in (ax, axr):
                a.axvline(xf, color="#ff8844", linewidth=1.0,
                          linestyle="--", alpha=0.75)
            ax.text(xf, 0.97, f" flip {_clock_at(xf)}",
                    transform=ax.get_xaxis_transform(), color="#ff8844",
                    fontsize=8, ha="left", va="top")

        # The same per-point sigma the fit weights with and the CSV
        # carries as err_mag — drawn as whiskers UNDER the points, thin
        # and translucent, so a long run does not turn into a picket
        # fence.  Off by default for exactly that reason.  Kept in mmag
        # here so the residual panel below can reuse it: subtracting the
        # model shifts a point, never its uncertainty.
        err_mmag = None
        if show_err:
            err = r.get("err")
            if err is not None and np.size(err) == jd.size:
                err_mmag = np.asarray(err) * 1000.0
                ax.errorbar(x, y * 1000.0, yerr=err_mmag,
                            fmt="none", ecolor="#7799cc", elinewidth=0.7,
                            alpha=0.35, capsize=0, zorder=1)

        ax.plot(x, y * 1000.0, ".", color="#7799cc", markersize=3,
                alpha=0.65, label=f"{jd.size} points")

        # The points the spike rejection removed, as crosses: the reader
        # should see WHAT was thrown away and judge for themselves that
        # it was a satellite, not an egress.  They are display-only —
        # nothing downstream ever reads them.
        cj, cm = r.get("clip_jd"), r.get("clip_mag")
        if cj is not None and np.size(cj):
            ax.plot((np.asarray(cj) - t0_ref) * 24.0,
                    np.asarray(cm) * 1000.0, "x", color="#dd5555",
                    markersize=7, markeredgewidth=1.4,
                    label=f"{np.size(cj)} outlier(s), not fitted")

        if n_bins > 0:
            bt, bm, be, _bn = bin_series(x, y * 1000.0, n_bins)
            if bt.size:
                ax.errorbar(bt, bm, yerr=be, fmt="o", color="#ffcc66",
                            markersize=4, linewidth=1, capsize=2,
                            label=f"binned ({n_bins})")

        if fit is not None:
            # The overlay is BASELINE + TRANSIT on a dense grid — not
            # fit["model_mag"], which also carries the systematics trend.
            # The plotted points are DETRENDED, so a model that still
            # contains the trend is paired with data that no longer does:
            # the line wiggled with the seeing, drooped where the trend
            # went, and the residual panel subtracted the trend TWICE —
            # its "autocorrelation" was largely that artefact.  The fit
            # itself was always consistent; only this pairing was not.
            tmpl_fit = fit.get("template") or ld_template(
                float(fit["rp_over_rs"]), float(fit.get("impact_b") or 0.0),
                float(fit.get("ld_u1", LD_U1)), float(fit.get("ld_u2", LD_U2)))
            tt_fit = np.linspace(float(np.min(jd)), float(np.max(jd)), 400)
            mx = (tt_fit - t0_ref) * 24.0
            my = (fit["baseline"] + fit["depth_mag"]
                  * ld_shape(tt_fit, float(fit["t0"]),
                             float(fit["duration_d"]), tmpl_fit)) * 1000.0
            colour = "#66dd88" if fit["detected"] else "#dd8866"
            if fit["detected"]:
                # The legend carries the numbers HOPS puts there too —
                # T0 and Rp/R★ with their errors — so a screenshot of
                # the chart is a complete result, not a teaser.
                label = f"transit model, {fit['significance']:.1f}σ"
                sig_s = fit.get("t0_sigma_s")
                if np.isfinite(fit.get("t0", np.nan)) and sig_s \
                        and np.isfinite(sig_s):
                    label += f"\nT0 {fit['t0']:.5f} ± {sig_s:.0f} s"
                if fit.get("rprs") is not None \
                        and fit.get("rprs_sigma") is not None:
                    label += (f"\nRp/R★ {fit['rprs']:.4f} "
                              f"± {fit['rprs_sigma']:.4f}")
                # Which systematics were solved alongside the transit —
                # HOPS states this on its best-fit line too, and a curve
                # detrended with airmass reads differently from one that
                # never had the chance.
                bases_used = fit.get("bases") or []
                label += ("\ndetrend: " + "+".join(bases_used)
                          if bases_used else "\ndetrend: none")
            else:
                label = (f"best fit, only {fit['significance']:.1f}σ "
                         "— not claimed")
            ax.plot(mx, my, "-", color=colour, linewidth=1.6, label=label)
            half = fit["duration_d"] * 24.0 / 2.0
            c = (fit["t0"] - t0_ref) * 24.0
            # Mid-transit line and window shading ONLY for a claimed
            # detection.  An unclaimed fit keeps its curve (honestly
            # labelled), but dressing its T0 in detection markers made a
            # 0.0σ fit that latched onto the meridian-flip step look
            # like a second flip line standing right beside the real
            # one — a dashed line in this chart must mean exactly one
            # thing.
            if fit["detected"]:
                ax.axvspan(c - half, c + half, color="#ffffff", alpha=0.04)
                ax.axvline(c, color=colour, linewidth=0.8,
                           linestyle="--", alpha=0.7)

            # The measured duration, as a double arrow spanning first to
            # last contact, parked a little BELOW the transit floor
            # (larger mmag — the axis is inverted) where no data sit.
            # Stated without an error bar on purpose: the duration comes
            # off the fit's search grid, and inventing a sigma for it
            # would dress a step size up as a measurement.
            y_arrow = float("nan")
            if fit["detected"] and np.isfinite(fit.get("duration_h",
                                                       np.nan)):
                y_arrow = ((fit["baseline"] + fit["depth_mag"]) * 1000.0
                           + max(3.0, 0.25 * float(fit["depth_mmag"])))
                ax.annotate("", xy=(c - half, y_arrow),
                            xytext=(c + half, y_arrow),
                            arrowprops=dict(arrowstyle="<->", color=colour,
                                            lw=1.0, alpha=0.8))
                dur_h = float(fit["duration_h"])
                ax.text(c, y_arrow + max(1.5, 0.08 * float(
                            fit["depth_mmag"])),
                        f"transit {dur_hhmm(dur_h)}", ha="center",
                        va="top", fontsize=8, color=colour, alpha=0.9)

            # The MEASURED first and last contact, as dashed lines in the
            # model's colour with their clock times — the same treatment
            # the predicted contacts get below, so the two sets can be
            # compared stamp by stamp.  Detection-only, like every other
            # marker the fit is allowed to wear; the stamps sit on a row
            # ABOVE the cyan predicted row, never on top of it.
            if fit["detected"]:
                x_lo = float(np.min(x))
                x_hi = float(np.max(x))
                for xc, tag in ((c - half, "start"), (c + half, "end")):
                    if x_lo <= xc <= x_hi:
                        ax.axvline(xc, color=colour, linewidth=0.7,
                                   linestyle="--", alpha=0.4)
                        ax.text(xc, 0.085, f"{tag} {_clock_at(xc)}",
                                transform=ax.get_xaxis_transform(),
                                color=colour, fontsize=7, ha="center",
                                va="bottom", alpha=0.9)

            # The EXPECTED transit, from the archive ephemeris: predicted
            # mid-time, catalogue depth ((Rp/Rs)^2 convention, mapped
            # through the same limb darkening), archive duration when it
            # has one.  Drawn only on BJD_TDB — against JD_UTC the
            # horizontal offset would be the 8-minute time-system error
            # wearing an O−C costume.  Drawn WHETHER OR NOT the fit
            # claimed a transit: on a detection the shift between the two
            # curves IS the O−C, and on a non-detection the prediction is
            # the more valuable half — it answers "was a transit even due
            # in this window?", which a TOI-3540.01 run asked and the
            # first cut could not answer.  The epoch comes from the
            # window's centre, not from the fitted T0, so a fit that
            # wandered off cannot drag the prediction with it.
            eph = r.get("ephemeris") or {}
            depth_pct = eph.get("depth_pct")
            # One switch hides the WHOLE prediction — curve, contact
            # stamps, duration arrow and Δ spans together.  Half a
            # comparison left on screen would look like a claim.
            if (show_expected
                    and r.get("time_system") == "BJD_TDB" and depth_pct
                    and eph.get("period_d") and eph.get("t0_bjd")):
                period = float(eph["period_d"])
                t_center = 0.5 * (float(np.min(jd)) + float(np.max(jd)))
                epoch = int(round((t_center - float(eph["t0_bjd"]))
                                  / period))
                t0_pred = float(eph["t0_bjd"]) + epoch * period
                dur_pred = ((float(eph["duration_h"]) / 24.0)
                            if eph.get("duration_h")
                            else float(fit["duration_d"]))
                # pscomppars' pl_trandep is (Rp/R*)^2 by construction, but the
                # TOI list's is the SPOC-measured, limb-darkened depth — a
                # sqrt of that overstates Rp/R* by ~9 % and the drawn dip by
                # ~18 %.  The archive's own Rp/R* wins whenever it has one;
                # without one the depth is INVERTED through the same
                # limb-darkened model that draws the curve, so a 1.42 %
                # TOI depth comes back as a 1.42 % dip, not 1.68 %.
                b = float(fit.get("impact_b") or 0.0)
                u1 = float(fit.get("ld_u1", LD_U1))
                u2 = float(fit.get("ld_u2", LD_U2))
                if eph.get("rprs_archive"):
                    rp_exp = float(eph["rprs_archive"])
                else:
                    rp_exp = rprs_from_depth(float(depth_pct) / 100.0, b, u1, u2)
                    if not rp_exp:
                        rp_exp = math.sqrt(float(depth_pct) / 100.0)
                dflux = ld_central_depth(rp_exp, b, u1, u2)
                if dflux and 0.0 < dflux < 1.0:
                    dmag = -2.5 * math.log10(1.0 - dflux)
                    tmpl = ld_template(rp_exp, b, u1, u2)
                    tt = np.linspace(float(np.min(jd)),
                                     float(np.max(jd)), 400)
                    em = (fit["baseline"]
                          + dmag * ld_shape(tt, t0_pred, dur_pred, tmpl))
                    in_window = (t0_pred + dur_pred / 2.0
                                 > float(np.min(jd))
                                 and t0_pred - dur_pred / 2.0
                                 < float(np.max(jd)))
                    if fit["detected"]:
                        drift, _ep = o_minus_c(float(fit["t0"]),
                                               float(eph["t0_bjd"]),
                                               period)
                        sig_min = (fit["t0_sigma_s"] / 60.0
                                   if np.isfinite(fit.get("t0_sigma_s",
                                                          np.nan))
                                   else float("nan"))
                        oc = (f"O−C {drift:+.1f} ± {sig_min:.1f} min"
                              if np.isfinite(sig_min)
                              else f"O−C {drift:+.1f} min")
                        label = ("expected (archive)\n"
                                 f"T0 {t0_pred:.5f}, "
                                 f"Rp/R★ {rp_exp:.4f}\n{oc}")
                    elif in_window:
                        # The prediction says a transit crossed this run;
                        # the fit could not claim one.  Both facts belong
                        # in the picture.
                        label = ("expected (archive)\n"
                                 f"T0 {t0_pred:.5f}, "
                                 f"Rp/R★ {rp_exp:.4f}\n"
                                 "(no transit claimed by the fit)")
                    else:
                        dh = (t0_pred - t_center) * 24.0
                        label = ("expected (archive): no transit "
                                 "predicted in this window\n"
                                 f"nearest mid-transit {t0_pred:.4f} "
                                 f"({dh:+.1f} h from this run)")
                    ax.plot((tt - t0_ref) * 24.0, em * 1000.0, "-",
                            color="#55bbcc", linewidth=1.2, alpha=0.9,
                            label=label)
                    # The predicted contact times as clock stamps along
                    # the bottom — start/mid/end, exactly the trio the
                    # planning tool prints under its transit dip.  Only
                    # the ones that fall inside the run are drawn: a
                    # label pinned to the axes edge would claim a time
                    # the chart does not cover.
                    xmin = (float(np.min(jd)) - t0_ref) * 24.0
                    xmax = (float(np.max(jd)) - t0_ref) * 24.0
                    for tc, tag in (
                            (t0_pred - dur_pred / 2.0, "start"),
                            (t0_pred, "mid"),
                            (t0_pred + dur_pred / 2.0, "end")):
                        xc = (tc - t0_ref) * 24.0
                        if xmin <= xc <= xmax:
                            ax.axvline(xc, color="#55bbcc",
                                       linewidth=0.7, linestyle=":",
                                       alpha=0.45)
                            ax.text(xc, 0.03,
                                    f"{tag} {_clock_at(xc)}",
                                    transform=ax.get_xaxis_transform(),
                                    color="#55bbcc", fontsize=7,
                                    ha="center", va="bottom", alpha=0.9)

                    # The predicted duration as its own double arrow —
                    # the twin of the measured one, in the expected
                    # curve's colour, nudged clear when the two floors
                    # nearly coincide.  With a detection the label also
                    # quotes Δduration (measured − predicted): the
                    # number the two arrows differ by should not have
                    # to be read off by eye.
                    if in_window:
                        xs_p = (t0_pred - dur_pred / 2.0 - t0_ref) * 24.0
                        xe_p = (t0_pred + dur_pred / 2.0 - t0_ref) * 24.0
                        y_exp = ((fit["baseline"] + dmag) * 1000.0
                                 + max(3.0, 0.25 * dmag * 1000.0))
                        if np.isfinite(y_arrow) and abs(y_exp
                                                        - y_arrow) < 4.0:
                            y_exp = y_arrow + 4.5
                        ax.annotate("", xy=(xs_p, y_exp),
                                    xytext=(xe_p, y_exp),
                                    arrowprops=dict(arrowstyle="<->",
                                                    color="#55bbcc",
                                                    lw=1.0, alpha=0.8))
                        exp_txt = f"expected {dur_hhmm(dur_pred * 24.0)}"
                        if fit["detected"] and np.isfinite(
                                fit.get("duration_h", np.nan)):
                            d_dur = (float(fit["duration_h"])
                                     - dur_pred * 24.0) * 60.0
                            exp_txt += f"  (Δ {d_dur:+.0f} min)"
                        ax.text(0.5 * (xs_p + xe_p),
                                y_exp + max(1.5, 0.08 * dmag * 1000.0),
                                exp_txt, ha="center", va="top",
                                fontsize=8, color="#55bbcc", alpha=0.9)

                    # Measured against predicted, contact by contact:
                    # a grey span from each predicted contact to its
                    # measured counterpart, labelled with the offset in
                    # minutes (measured − predicted, the O−C sign
                    # convention).  Only with a detection — without a
                    # fitted transit there is no second endpoint.
                    if fit["detected"] and in_window:
                        for xm, xp, tag in ((c - half, xs_p, "start"),
                                            (c + half, xe_p, "end")):
                            d_min = (xm - xp) * 60.0
                            tf = ax.get_xaxis_transform()
                            ax.annotate("", xy=(xp, 0.115),
                                        xytext=(xm, 0.115),
                                        xycoords=tf, textcoords=tf,
                                        arrowprops=dict(
                                            arrowstyle="<->",
                                            color="#aaaaaa", lw=0.8,
                                            alpha=0.8))
                            ax.text(0.5 * (xm + xp), 0.125,
                                    f"Δ{tag} {d_min:+.1f} min",
                                    transform=tf, color="#cccccc",
                                    fontsize=7, ha="center",
                                    va="bottom", alpha=0.9)
            # Same pairing as the overlay: y is detrended, so the model
            # subtracted here must be transit-only — baseline + shape,
            # never the trend a second time.
            resid = (y - (fit["baseline"] + fit["depth_mag"]
                          * ld_shape(jd, float(fit["t0"]),
                                     float(fit["duration_d"]),
                                     tmpl_fit))) * 1000.0
        else:
            resid = (y - float(np.median(y))) * 1000.0
        if err_mmag is not None:
            axr.errorbar(x, resid, yerr=err_mmag, fmt="none",
                         ecolor="#888888", elinewidth=0.7, alpha=0.35,
                         capsize=0, zorder=1)
        axr.plot(x, resid, ".", color="#888888", markersize=3, alpha=0.6)

        # What is left after the model: how big (STD) and whether it is
        # noise or structure.  The lag-1 autocorrelation is the red-noise
        # tell — white noise sits near 0, a leftover systematic (an
        # airmass ramp nobody removed, a step at a flip) pushes it up,
        # because neighbouring residuals then lean the same way.
        if resid.size > 3:
            rstd = float(np.std(resid, ddof=1))
            d0 = resid[:-1] - float(np.mean(resid[:-1]))
            d1 = resid[1:] - float(np.mean(resid[1:]))
            denom = float(np.sqrt(np.sum(d0 * d0) * np.sum(d1 * d1)))
            r1 = float(np.sum(d0 * d1) / denom) if denom > 0 else float("nan")
            verdict = ("white-noise-like" if abs(r1) < 0.15
                       else "mild structure" if abs(r1) < 0.4
                       else "structure left") if np.isfinite(r1) else ""
            note = f"STD {rstd:.2f} mmag"
            if np.isfinite(r1):
                note += f"  ·  lag-1 autocorr {r1:+.2f} ({verdict})"
            axr.text(0.01, 0.94, note, transform=axr.transAxes,
                     fontsize=8, color="#aaaaaa", va="top")

        ax.invert_yaxis()
        ax.set_ylabel("Δ magnitude [mmag]")
        # Two lines of provenance: WHAT was observed (target, night, subs,
        # filter — assembled by the worker from the headers) above HOW
        # well it went.  A screenshot then answers both questions.
        head = (f"{os.path.basename(r['folder'])}  ·  "
                f"RMS {r['rms_mmag']:.2f} mmag  ·  "
                f"{len(r['comps'])} comparison stars")
        if r.get("title_bits"):
            head = f"{r['title_bits']}\n{head}"
        ax.set_title(head, fontsize=10)
        # The legend lives ABOVE the plot, not inside it: "best" still
        # has to pick a corner, and on a transit that fills the run
        # every corner has data under it.  The "outside" location needs
        # constrained layout (matplotlib >= 3.7), which this figure
        # uses anyway; an older matplotlib falls back to the old
        # in-axes placement rather than losing the legend.
        handles, hlabels = ax.get_legend_handles_labels()
        try:
            leg = self.fig.legend(handles, hlabels,
                                  loc="outside upper right", ncols=3,
                                  fontsize=8, facecolor="#2b2b2b",
                                  edgecolor="#555555")
        except (ValueError, TypeError):
            leg = ax.legend(loc="best", fontsize=8, facecolor="#2b2b2b",
                            edgecolor="#555555")
        for txt in leg.get_texts():
            txt.set_color("#cccccc")
        ax.tick_params(labelbottom=False)

        axr.axhline(0.0, color="#555555", linewidth=0.8)
        axr.invert_yaxis()
        axr.set_ylabel("resid [mmag]")
        # Name the ACTUAL time system of the axis — the values are
        # BJD_TDB whenever the conversion ran, and now that a clock axis
        # sits on top, a bottom label claiming UTC for BJD values would
        # be a visible self-contradiction of about eight minutes.
        axr.set_xlabel(f"hours from JD {t0_ref:.0f} "
                       f"({(r.get('time_system') or 'UTC').replace('_', ' ')})")

        # constrained layout handles the shared-x subplots that
        # tight_layout warns about and lays out incorrectly.
        try:
            self.fig.set_layout_engine("constrained")
        except AttributeError:
            self.fig.tight_layout()
        self.draw()

    def save_png(self, path: str) -> bool:
        try:
            self.fig.savefig(path, dpi=150, facecolor="#2b2b2b")
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class SvenesisLightCurveWindow(QMainWindow):
    """Left panel: what to measure.  Right panel: what came out.

    The same shape as the other scripts in this collection, so somebody who
    has used one of them already knows where the folder picker and the Run
    button are.
    """

    def __init__(self, siril=None):
        super().__init__()
        self.siril = siril or s.SirilInterface()
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._folder = ""
        self._worker = None
        self._result = None
        self.init_ui()
        self._load_settings()
        self._update_target_fields()

    # -- layout -----------------------------------------------------------
    def init_ui(self) -> None:
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.addWidget(self._build_left_panel())
        layout.addWidget(self._build_right_panel(), 1)
        self.setWindowTitle(f"Svenesis LightCurve {VERSION}")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1400, 900)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(LEFT_PANEL_WIDTH)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        title = QLabel(f"Svenesis LightCurve {VERSION}")
        title.setStyleSheet("color:#88aaff;font-size:14pt;font-weight:bold;")
        layout.addWidget(title)
        sub = QLabel("Exoplanet light curve from a folder of subs")
        sub.setStyleSheet("color:#888888;font-size:9pt;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self._build_source_group(layout)
        self._build_calibration_group(layout)
        self._build_target_group(layout)
        self._build_photometry_group(layout)
        self._build_analysis_group(layout)
        self._build_export_group(layout)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        self._build_action_buttons(outer)
        return panel

    def _build_source_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("1 · Subs")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        self.btn_folder = QPushButton("Choose folder…")
        self.btn_folder.clicked.connect(self._on_pick_folder)
        row.addWidget(self.btn_folder)
        lay.addLayout(row)
        self.lbl_folder = QLabel("No folder chosen.")
        self.lbl_folder.setStyleSheet("color:#888888;font-size:9pt;")
        self.lbl_folder.setWordWrap(True)
        lay.addWidget(self.lbl_folder)
        self.chk_copy = QCheckBox("Copy frames instead of symlinking")
        self.chk_copy.setToolTip(
            "The subs are staged into a working folder before Siril sees "
            "them. Symlinks cost nothing; copies double the disk use.\n\n"
            "Tick this only if your drive does not allow symlinks. Either "
            "way the original folder is never written to.")
        lay.addWidget(self.chk_copy)
        parent.addWidget(box)

    def _build_calibration_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("2 · Calibration")
        lay = QVBoxLayout(box)

        self.chk_calibrate = QCheckBox("Apply calibration when frames exist")
        self.chk_calibrate.setChecked(True)
        self.chk_calibrate.setToolTip(
            "Lc = (L − D) / (F − O).\n\n"
            "Nothing has to be prepared: flats are found beside your lights "
            "(the N.I.N.A. LIGHT / FLAT layout), masters are stacked and "
            "cached automatically, and whatever is missing is simply "
            "skipped and named in the log.")
        lay.addWidget(self.chk_calibrate)

        row = QHBoxLayout()
        self.btn_library = QPushButton("📁  Library…")
        self.btn_library.setToolTip(
            "Folder holding your reusable DARK and BIAS frames — raw frames "
            "(they get stacked) or ready-made masters, either way.\n\n"
            "Flats are NOT taken from here: they belong to the session and "
            "are found next to your lights.\n\n"
            "Remembered between runs.")
        self.btn_library.clicked.connect(self._on_pick_library)
        row.addWidget(self.btn_library)
        self.btn_library_clear = QPushButton("✕")
        self.btn_library_clear.setFixedWidth(30)
        self.btn_library_clear.setToolTip("Forget the library folder.")
        self.btn_library_clear.clicked.connect(self._on_clear_library)
        row.addWidget(self.btn_library_clear)
        lay.addLayout(row)

        self._library = ""
        self.lbl_library = QLabel("No library folder set.")
        self.lbl_library.setStyleSheet("color:#888888;font-size:9pt;")
        self.lbl_library.setWordWrap(True)
        lay.addWidget(self.lbl_library)

        self.chk_cfa = QCheckBox("One-shot-colour sensor (CFA)")
        self.chk_cfa.setToolTip(
            "Adds -cfa -debayer. Without it a Bayer frame is flat-fielded "
            "across its own mosaic, which writes the CFA pattern into the "
            "correction. Leave off for a mono camera.")
        lay.addWidget(self.chk_cfa)

        self.lbl_calib_found = QLabel(
            "Choose a folder to see what calibration frames are found.")
        self.lbl_calib_found.setStyleSheet("color:#88aaff;font-size:9pt;")
        self.lbl_calib_found.setWordWrap(True)
        lay.addWidget(self.lbl_calib_found)
        parent.addWidget(box)

    def _on_pick_library(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Reusable DARK / BIAS library", self._library or "")
        if path:
            self._library = path
            self.lbl_library.setText(path)
            self._refresh_calib_preview()

    def _on_clear_library(self) -> None:
        self._library = ""
        self.lbl_library.setText("No library folder set.")
        self._refresh_calib_preview()

    def _refresh_calib_preview(self) -> None:
        """Say what WOULD be used, before the run rather than after it.

        The preview reads headers, so it is capped: the point is to tell
        you whether the flats were found at all, not to be the run.
        """
        if not self._folder:
            self.lbl_calib_found.setText(
                "Choose a folder to see what calibration frames are found.")
            return
        try:
            roots = calibration_roots(self._folder, self._library)
            names = sorted({os.path.basename(r.rstrip(os.sep)) or r
                            for r in roots})
            # Anything filed inside your own selection is picked up by the
            # recursive scan, so a FLAT folder in there needs no mention
            # here -- but saying only "nothing found" would read as "there
            # is nothing", which is a different claim.
            if names:
                self.lbl_calib_found.setText(
                    "Found beside your subs: " + ", ".join(names)
                    + ". Calibration frames inside the folder you chose are "
                      "picked up as well, and everything is matched against "
                      "the lights when you run.")
            else:
                self.lbl_calib_found.setText(
                    "No FLAT / DARK / BIAS folder beside these subs. Any "
                    "calibration frames INSIDE the folder you chose are "
                    "still found; otherwise set a library folder.")
        except Exception as exc:            # noqa: BLE001 -- preview only
            self.lbl_calib_found.setText(f"Could not scan: {exc}")

    def _build_target_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("3 · Target star")
        lay = QVBoxLayout(box)
        self.cmb_target = QComboBox()
        self.cmb_target.addItems([
            "From the frames — name or coordinates in the header",
            "Brightest star in the field",
            "Pixel position on the first frame",
            "RA / Dec (needs plate-solved subs)",
        ])
        self.cmb_target.setToolTip(
            "How to find the star whose light curve you want.\n\n"
            "FROM THE FRAMES is the one to leave it on. Your subs usually "
            "already say: OBJCTRA/OBJCTDEC give the target's position "
            "directly, and OBJECT gives its name, which the archive turns "
            "into coordinates AND an ephemeris. Whatever it finds is "
            "checked against a real detected star, and if it finds nothing "
            "it falls back to brightest and says so.\n\n"
            "Brightest is right surprisingly often — a transit host is "
            "usually the reason the field was framed that way. Pixel and "
            "RA/Dec both SNAP to the nearest detected star rather than "
            "using your number directly: a position two pixels off centre "
            "loses flux, and it loses a different amount every time the "
            "seeing changes.")
        self.cmb_target.currentIndexChanged.connect(self._update_target_fields)
        lay.addWidget(self.cmb_target)

        row_name = QHBoxLayout()
        self.lbl_tname = QLabel("Name")
        self.ed_target_name = QLineEdit()
        self.ed_target_name.setPlaceholderText(
            "e.g. HAT-P-32 b — OBJECT from the headers is preferred")
        self.ed_target_name.setToolTip(
            "The planet's name, as the NASA Exoplanet Archive spells it. "
            "WASP-75b becomes WASP-75 b on the way out, so either works.\n\n"
            "OBJECT from your light frames is preferred when it exists — "
            "it came with the data and cannot be about a different folder. "
            "This field is the fallback for headers whose OBJECT is junk "
            "or unknown to the archive. The resolved name also labels the "
            "AAVSO submission file.")
        row_name.addWidget(self.lbl_tname)
        row_name.addWidget(self.ed_target_name, 1)
        lay.addLayout(row_name)

        self.chk_resolve = QCheckBox(
            "Look the name up (NASA Exoplanet Archive)")
        self.chk_resolve.setChecked(True)
        self.chk_resolve.setToolTip(
            "Fetches RA/Dec and the published ephemeris for that name — so "
            "you do not type coordinates, and the report can say how far "
            "your measured mid-transit is from the prediction (O−C).\n\n"
            "The position is checked: the next step reports how far it "
            "lands from a real detected star, so a wrong name fails loudly "
            "instead of quietly mis-pointing.\n\n"
            "Cached after the first success, so a second run — or an "
            "offline machine — still has it. Off, or with no connection, "
            "the coordinates in your headers are still used; only the O−C "
            "is lost.")
        lay.addWidget(self.chk_resolve)

        grid = QGridLayout()
        self.lbl_x = QLabel("x:")
        self.ed_x = QLineEdit()
        self.ed_x.setPlaceholderText("1024")
        self.lbl_y = QLabel("y:")
        self.ed_y = QLineEdit()
        self.ed_y.setPlaceholderText("768")
        grid.addWidget(self.lbl_x, 0, 0)
        grid.addWidget(self.ed_x, 0, 1)
        grid.addWidget(self.lbl_y, 0, 2)
        grid.addWidget(self.ed_y, 0, 3)
        self.lbl_ra = QLabel("RA:")
        self.ed_ra = QLineEdit()
        self.ed_ra.setPlaceholderText("18:18:45  or  274.6875")
        self.lbl_dec = QLabel("Dec:")
        self.ed_dec = QLineEdit()
        self.ed_dec.setPlaceholderText("-13:47:31  or  -13.7919")
        grid.addWidget(self.lbl_ra, 1, 0)
        grid.addWidget(self.ed_ra, 1, 1, 1, 3)
        grid.addWidget(self.lbl_dec, 2, 0)
        grid.addWidget(self.ed_dec, 2, 1, 1, 3)
        lay.addLayout(grid)

        note = QLabel("RA in hours (12:34:56) or degrees (188.5) — the "
                      "colons decide.")
        note.setStyleSheet("color:#888888;font-size:8pt;")
        note.setWordWrap(True)
        lay.addWidget(note)
        parent.addWidget(box)

    def _build_photometry_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("4 · Photometry")
        lay = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Comparison stars:"))
        self.spin_comps = QSpinBox()
        self.spin_comps.setRange(MIN_COMPS, 20)
        self.spin_comps.setValue(DEFAULT_N_COMPS)
        self.spin_comps.setToolTip(
            "How many stars to calibrate the target against.\n\n"
            "More comps average down the ensemble's own noise, but each one "
            "added is fainter than the last, so the gain flattens quickly — "
            "five is a good default. Below two there is no ensemble at all: "
            "a single comparison star puts its own variability straight "
            "into your light curve.")
        row.addWidget(self.spin_comps)
        row.addStretch()
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Minimum comp SNR:"))
        self.spin_snr = QDoubleSpinBox()
        self.spin_snr.setRange(0.0, 500.0)
        self.spin_snr.setDecimals(0)
        self.spin_snr.setValue(MIN_COMP_SNR)
        self.spin_snr.setToolTip(
            "Comparison stars below this signal-to-noise are rejected.\n\n"
            "A faint comp contributes its own Poisson noise to the "
            "ensemble; below about 20 it adds more scatter than reference. "
            "Raise it if the curve is noisier than the target's own "
            "photon statistics say it should be.")
        row.addWidget(self.spin_snr)
        row.addStretch()
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel:"))
        self.spin_channel = QSpinBox()
        self.spin_channel.setRange(0, 2)
        self.spin_channel.setValue(0)
        self.spin_channel.setToolTip(
            "Which channel to measure. Mono cameras have only channel 0.\n\n"
            "On a colour camera, green (1) usually carries the most signal "
            "and the smallest chromatic differential-extinction error.")
        row.addWidget(self.spin_channel)
        row.addStretch()
        lay.addLayout(row)

        self.chk_scan_aper = QCheckBox("Search for the best aperture")
        self.chk_scan_aper.setChecked(True)
        self.chk_scan_aper.setToolTip(
            "Aperture size is the most influential number in aperture "
            "photometry, and without this it is whatever -autoring picks "
            "from the FWHM.\n\n"
            "Ticked, six radii from 0.75 to 2.5 FWHM are each photometered "
            "and the one with the least scatter wins, with the number of "
            "measured frames as the tie-breaker. Costs six extra passes.")
        lay.addWidget(self.chk_scan_aper)

        self.chk_screen = QCheckBox("Check comparison stars for variability")
        self.chk_screen.setChecked(True)
        self.chk_screen.setToolTip(
            "Each comparison star is photometered against the OTHERS and "
            "judged on its own scatter.\n\n"
            "A variable comparison writes its own curve, inverted, into "
            "the target's — and nothing else here would notice. Needs no "
            "catalogue and no network; costs one pass per comparison star.")
        lay.addWidget(self.chk_screen)

        self.chk_autoring = QCheckBox("Auto ring radii from the FWHM")
        self.chk_autoring.setChecked(True)
        self.chk_autoring.setToolTip(
            "Siril's -autoring: inner and outer sky-annulus radii at 4.2 "
            "and 6.3 times the measured FWHM.\n\n"
            "Leave it on unless you have a reason not to. Fixed radii tuned "
            "for one night's seeing are wrong on the next one, and an "
            "annulus that creeps onto the star wings biases every point in "
            "the same direction the seeing moved.")
        lay.addWidget(self.chk_autoring)
        parent.addWidget(box)

    def _build_analysis_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("5 · Analysis")
        lay = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Fit mode:"))
        self.cmb_fit_mode = QComboBox()
        self.cmb_fit_mode.addItems(["Svenesis — blind detection",
                                    "HOPS-compatible — ephemeris-locked"])
        self.cmb_fit_mode.setToolTip(
            "Blind detection asks whether there is a transit at all: "
            "mid-time, duration and shape are all free, and a calibrated "
            "significance test decides.\n\n"
            "HOPS-compatible locks the duration and shape to the planet's "
            "orbit from the archive (a/R*, inclination, eccentricity) as "
            "HOPS does, fits only Rp/R*, the mid-time and a normalisation "
            "with detrending, removes outliers and scales the error bars "
            "the way HOPS does, and samples the posterior with the same "
            "ensemble algorithm. results.txt then carries HOPS's own "
            "parameter table. The blind test still runs and still decides "
            "whether a transit is claimed.")
        self.cmb_fit_mode.currentIndexChanged.connect(self._on_fit_mode)
        row.addWidget(self.cmb_fit_mode)
        row.addStretch()
        lay.addLayout(row)

        hgrid = QGridLayout()
        hgrid.addWidget(QLabel("HOPS detrending:"), 0, 0)
        self.cmb_hops_detrend = QComboBox()
        self.cmb_hops_detrend.addItems(["Airmass", "Linear", "Quadratic"])
        self.cmb_hops_detrend.setToolTip(
            "HOPS's three detrending choices: a trend linear in airmass, "
            "linear in time, or quadratic in time — multiplied into the "
            "flux model as HOPS does, not subtracted in magnitude.")
        hgrid.addWidget(self.cmb_hops_detrend, 0, 1)
        hgrid.addWidget(QLabel("iterations:"), 0, 2)
        self.spin_hops_iter = QSpinBox()
        self.spin_hops_iter.setRange(200, 50000)
        self.spin_hops_iter.setSingleStep(500)
        self.spin_hops_iter.setValue(2000)
        self.spin_hops_iter.setToolTip(
            "Steps of the ensemble sampler (HOPS defaults to 5000). "
            "2000 gives bars stable to a few percent in well under a "
            "minute; the first 20 % are discarded as burn-in.")
        hgrid.addWidget(self.spin_hops_iter, 0, 3)
        hgrid.addWidget(QLabel("Claret a1..a4:"), 1, 0)
        self.ed_hops_ldc = QLineEdit()
        self.ed_hops_ldc.setPlaceholderText(
            "blank = quadratic law; e.g. 0.70, -0.50, 0.90, -0.40")
        # No minimum width of its own: the field takes what the panel
        # has.  With the button beside it the row was wider than the
        # panel and the whole left pane grew a horizontal scrollbar.
        self.ed_hops_ldc.setMinimumWidth(60)
        self.ed_hops_ldc.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self.ed_hops_ldc.setToolTip(
            "Four Claret limb-darkening coefficients for your filter, as "
            "HOPS takes them from ExoTETHyS. Leave blank and the "
            "quadratic law this script uses is written exactly as Claret "
            "coefficients (a2 = u1 + 2 u2, a4 = -u2).")
        hgrid.addWidget(self.ed_hops_ldc, 1, 1, 1, 3)
        self.btn_hops_ldc = QPushButton("Compute Claret (Phoenix)")
        self.btn_hops_ldc.setToolTip(
            "The coefficients HOPS would use, computed here: ExoTETHyS's "
            "method on the Phoenix 2018 model atmospheres for the planet "
            "named in group 3 (Teff and log g from the archive) and the "
            "filter in group 6 (transmission curve from the SVO Filter "
            "Profile Service).\n\n"
            "The first call per star downloads about four 21 MB model "
            "files into ~/.svenesis and takes a minute; later calls are "
            "seconds. Needs a network connection.")
        self.btn_hops_ldc.clicked.connect(self._on_compute_ldc)
        hgrid.addWidget(self.btn_hops_ldc, 2, 1, 1, 3,
                        Qt.AlignmentFlag.AlignLeft)
        hgrid.setColumnStretch(1, 1)
        lay.addLayout(hgrid)
        self._hops_widgets = [self.cmb_hops_detrend, self.spin_hops_iter,
                              self.ed_hops_ldc, self.btn_hops_ldc]
        self._hops_ldc_note = ""
        self._hops_filter_note = ""
        self._hops_ldc_text = ""
        self._ldc_thread = None
        self._on_fit_mode()

        self.chk_detrend = QCheckBox("Remove the airmass ramp")
        self.chk_detrend.setChecked(True)
        self.chk_detrend.setToolTip(
            "Differential photometry cancels most extinction, but not all "
            "of it: the target and the comps have different colours, so "
            "they dim at slightly different rates as the field sinks.\n\n"
            "Needs the target's RA/Dec and your site below. The baseline is "
            "anchored on the out-of-transit points, so a target setting "
            "through egress does not have its transit depth absorbed into "
            "the ramp.")
        lay.addWidget(self.chk_detrend)

        grid = QGridLayout()
        grid.addWidget(QLabel("Site lat:"), 0, 0)
        self.ed_lat = QLineEdit()
        self.ed_lat.setPlaceholderText("50.1  (north +)")
        grid.addWidget(self.ed_lat, 0, 1)
        grid.addWidget(QLabel("lon:"), 0, 2)
        self.ed_lon = QLineEdit()
        self.ed_lon.setPlaceholderText("8.7  (east +)")
        grid.addWidget(self.ed_lon, 0, 3)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.addWidget(QLabel("Bin the plot into:"))
        self.spin_bins = QSpinBox()
        self.spin_bins.setRange(0, 200)
        self.spin_bins.setValue(0)
        self.spin_bins.setSpecialValueText("off")
        self.spin_bins.setToolTip(
            "Draw binned points on top of the raw ones.\n\n"
            "Presentation only. The fit always sees every point — binning "
            "first would throw away the very scatter the significance test "
            "needs to be honest about itself.")
        self.spin_bins.valueChanged.connect(self._redraw)
        row.addWidget(self.spin_bins)
        self.chk_errbars = QCheckBox("Error bars")
        self.chk_errbars.setChecked(False)
        self.chk_errbars.setToolTip(
            "Draw each raw point's 1-sigma uncertainty as a whisker — the "
            "same per-point error the fit weights with and the CSV carries "
            "as err_mag (CCD equation: star + sky photon noise and read "
            "noise).\n\n"
            "Presentation only, like binning: on or off, the fit and the "
            "significance see the identical numbers. Off by default "
            "because a few hundred whiskers bury the transit shape.")
        self.chk_errbars.toggled.connect(self._redraw)
        row.addWidget(self.chk_errbars)
        row.addStretch()
        lay.addLayout(row)
        parent.addWidget(box)

    def _build_export_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("6 · Submission")
        lay = QVBoxLayout(box)
        self.chk_aavso = QCheckBox("Write an AAVSO Exoplanet Watch file")
        self.chk_aavso.setChecked(True)
        self.chk_aavso.setToolTip(
            "Writes AAVSO_exoplanet.txt beside the CSV. Nothing is sent "
            "anywhere — submitting is your decision.\n\n"
            "Refused when the times are not BJD_TDB: the format declares "
            "that, and JD_UTC under that header is an 8 minute error "
            "nobody could see.")
        lay.addWidget(self.chk_aavso)
        row = QHBoxLayout()
        row.addWidget(QLabel("Observer code"))
        self.ed_obscode = QLineEdit()
        self.ed_obscode.setText(DEFAULT_OBSCODE)
        self.ed_obscode.setPlaceholderText("e.g. ABC — optional")
        self.ed_obscode.setToolTip(
            "Your AAVSO observer code. Left empty the file is still "
            "written, with the field marked, and you can fill it in later.")
        row.addWidget(self.ed_obscode, 1)
        lay.addLayout(row)
        # The target NAME and the archive lookup live in group 3, where
        # they belong: they decide the target POSITION, not the submission.
        # Having them here meant the one control that spares you typing
        # coordinates sat in a group about filing the result.
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Filter"))
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("CV")
        self.ed_filter.setFixedWidth(70)
        row2.addWidget(self.ed_filter)
        lay.addLayout(row2)
        parent.addWidget(box)

    def _build_action_buttons(self, parent: QVBoxLayout) -> None:
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        parent.addWidget(self.progress)

        self.btn_run = QPushButton("Measure light curve")
        self.btn_run.setObjectName("RenderButton")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._on_run)
        parent.addWidget(self.btn_run)

        row2 = QHBoxLayout()
        self.btn_png = QPushButton("Save plot…")
        self.btn_png.setEnabled(False)
        self.btn_png.clicked.connect(self._on_save_png)
        row2.addWidget(self.btn_png)
        self.btn_report = QPushButton("Save results…")
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self._on_save_report)
        row2.addWidget(self.btn_report)
        parent.addLayout(row2)

        btn_coffee = QPushButton("☕  Buy me a Coffee")
        btn_coffee.setObjectName("CoffeeButton")
        btn_coffee.setToolTip("Support the development of this tool")
        btn_coffee.clicked.connect(self._show_coffee_dialog)
        parent.addWidget(btn_coffee)
        self.btn_help = QPushButton("Help")
        self.btn_help.clicked.connect(self._show_help)
        parent.addWidget(self.btn_help)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.clicked.connect(self.close)
        parent.addWidget(self.btn_close)

        self.lbl_status = QLabel("Choose a folder of sub-exposures.")
        self.lbl_status.setStyleSheet("color:#888888;font-size:9pt;")
        self.lbl_status.setWordWrap(True)
        parent.addWidget(self.lbl_status)

    def _build_right_panel(self) -> QWidget:
        self.tabs = QTabWidget()
        self.plot = LightCurvePlot()
        # The chart page is a small control bar ABOVE the canvas plus
        # the canvas itself — the place for switches that only change
        # what is drawn, right where the drawing is.
        self.plot_page = QWidget()
        pv = QVBoxLayout(self.plot_page)
        pv.setContentsMargins(4, 4, 4, 0)
        pv.setSpacing(2)
        prow = QHBoxLayout()
        self.chk_expected = QCheckBox("Expected curve (archive)")
        self.chk_expected.setChecked(True)
        self.chk_expected.setToolTip(
            "Draw the transit the archive ephemeris predicts for this "
            "window — the cyan curve with its contact stamps, duration "
            "arrow and the Δ spans against the measured contacts.\n\n"
            "Presentation only: on or off, the fit and the significance "
            "see the identical numbers.")
        self.chk_expected.toggled.connect(self._redraw)
        prow.addWidget(self.chk_expected)
        prow.addStretch()
        pv.addLayout(prow)
        pv.addWidget(self.plot)
        self.tabs.addTab(self.plot_page, "Light curve")

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setStyleSheet(
            "background-color:#1e1e1e;border:1px solid #444444;"
            f"border-radius:4px;font-family:'{fixed_font_family()}';"
            "font-size:9pt;")
        self.info.setHtml(
            "<p style='color:#888888'>No run yet. Pick a folder of subs on "
            "the left and press <b>Measure light curve</b>.</p>")
        self.tabs.addTab(self.info, "Result")

        self.tbl_comps = QTableWidget(0, 4)
        self.tbl_comps.setHorizontalHeaderLabels(["Star", "x", "y", "SNR"])
        self.tbl_comps.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.tbl_comps, "Stars")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background-color:#1e1e1e;border:1px solid #444444;"
            f"border-radius:4px;font-family:'{fixed_font_family()}';"
            "font-size:9pt;")
        self.tabs.addTab(self.log_view, "Log")
        return self.tabs

    # -- behaviour --------------------------------------------------------
    def _update_target_fields(self) -> None:
        """Show the pixel fields only in pixel mode; always show RA/Dec.

        The RA/Dec pair is NOT only a target selector -- the airmass detrend
        needs the target's sky position whichever way the star was picked.
        Hiding it outside RA/Dec mode would leave somebody who chose
        "brightest" wondering why the detrend never runs.
        """
        idx = self.cmb_target.currentIndex()
        for w in (self.lbl_x, self.ed_x, self.lbl_y, self.ed_y):
            w.setVisible(idx == 2)
        # The name and the lookup only do anything in "from the frames"
        # mode, but they stay VISIBLE in every mode, greyed: the lookup
        # also supplies the ephemeris for the O-C, and that is worth having
        # whichever way the star was picked.
        for w in (self.lbl_tname, self.ed_target_name, self.chk_resolve):
            w.setEnabled(True)

    def _log(self, msg: str, color=None) -> None:
        tint = {LogColor.GREEN: "#88cc88", LogColor.SALMON: "#ddaa88",
                LogColor.RED: "#dd8888"}.get(color, "#bbbbbb")
        self.log_view.append(f'<span style="color:{tint}">{msg}</span>')

    def _probe_target(self, files) -> None:
        """Read a few light headers now and fill in what they already say.

        The run does this anyway, but doing it at folder-choose time is
        the difference between a number you can check and a number that
        appears in the log after five minutes of registration.  You see
        what the frames claim, and you can correct it before starting.

        The fields FOLLOW the headers: they are restored from the last
        session's settings, so after switching targets they show the
        PREVIOUS target -- WASP-75 frames sat under a box still reading
        'HATP-32'.  When OBJECT names a DIFFERENT target than the name
        field, or OBJCTRA/OBJCTDEC sit more than TARGET_DISAGREE_ARCSEC
        from the coordinate fields, the fields are updated and every
        replacement is logged; a name that already keys to the same
        target (any spelling, with or without the planet letter) and
        coordinates that already agree are left exactly as typed.  To aim
        at a star that is NOT the headers' object, type it AFTER choosing
        the folder -- nothing re-probes, and the worker reports the
        disagreement loudly at run time.

        Capped at PROBE_HEADERS frames because this runs on the UI thread
        -- measured at 153 ms for 30 compressed N.I.N.A. subs, which is a
        click, while several hundred would be a freeze.
        """
        if not files:
            return
        infos = []
        for path in files[:PROBE_HEADERS]:
            try:
                infos.append(inspect_frame(path))
            except Exception as exc:               # noqa: BLE001
                _log_swallowed(exc)
        lights, _cal, _note = split_frames(infos, inside=True)
        if not lights:
            lights = infos
        found = []
        name = ""
        for info in lights:
            if info.get("object"):
                name = str(info["object"]).strip()
                break
        existing = self.ed_target_name.text().strip()
        name_switched = bool(name and existing
                             and target_key(existing) != target_key(name))
        if name and (not existing
                     or target_key(existing) != target_key(name)):
            self.ed_target_name.setText(name)
            found.append(f"OBJECT = {name!r}"
                         + (f" (replacing {existing!r} — left over from "
                            "another target)" if existing else ""))
        elif name:
            found.append(f"headers say OBJECT = {name!r}")

        ra, dec, note = header_target_radec(lights)
        if ra is not None:
            old_ra = self.ed_ra.text().strip()
            old_dec = self.ed_dec.text().strip()
            if not old_ra and not old_dec:
                self.ed_ra.setText(f"{ra:.6f}")
                self.ed_dec.setText(f"{dec:+.6f}")
                found.append(f"OBJCTRA/OBJCTDEC = {ra:.5f}, {dec:+.5f} ({note})")
            else:
                gap = angular_sep_arcsec(ra, dec, self._ra_deg(),
                                         _sexagesimal(self.ed_dec.text()))
                if np.isfinite(gap) and gap <= TARGET_DISAGREE_ARCSEC:
                    found.append(f"headers say {ra:.5f}, {dec:+.5f} "
                                 "(agrees with the fields)")
                else:
                    # Same rule as the name: the fields persist across
                    # sessions, so a coordinate this far off is the
                    # previous target, not a choice.  To aim at a star
                    # that is NOT the headers' object, type it AFTER
                    # choosing the folder — nothing re-probes.
                    self.ed_ra.setText(f"{ra:.6f}")
                    self.ed_dec.setText(f"{dec:+.6f}")
                    found.append(
                        f"OBJCTRA/OBJCTDEC = {ra:.5f}, {dec:+.5f} ({note}), "
                        f"replacing {old_ra or '?'}, {old_dec or '?'}"
                        + (f" — {gap:.0f}\" away, left over from another "
                           "target" if np.isfinite(gap)
                           else " — the fields did not parse"))
        elif name_switched and (self.ed_ra.text().strip()
                                or self.ed_dec.text().strip()):
            # The target changed but these headers carry no position to
            # replace the old one with — a coordinate describing the
            # PREVIOUS target left standing here sent a HAT-P-32 run to
            # the brightest-star guess.  Cleared, the worker fills the
            # position from the archive by the frames' own OBJECT name.
            self.ed_ra.setText("")
            self.ed_dec.setText("")
            found.append(
                "cleared the RA/Dec fields — they were the previous "
                "target's, and these headers carry no position to replace "
                "them with (the archive supplies one from the name)")
        if found:
            self._log("Read from the first "
                      f"{min(len(files), PROBE_HEADERS)} header(s): "
                      + "; ".join(found) + ".", LogColor.GREEN)
        else:
            self._log(
                "The headers name no target and carry no OBJCTRA/OBJCTDEC. "
                "Type the planet's name in group 3 and the archive will "
                "supply the coordinates, or pick another target mode.",
                LogColor.SALMON)

    def _on_pick_folder(self) -> None:
        start = self._folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Folder of sub-exposures", start)
        if not folder:
            return
        self._folder = folder
        files = _fits_files(folder)
        # The scan is recursive, so this count includes any calibration
        # frames filed under the same folder.  Which frames are lights is
        # decided from the headers when you run -- reading several hundred
        # of them here would freeze the window on every folder click.
        self.lbl_folder.setText(
            f"{folder}\n{len(files)} FITS file(s) found, including "
            f"sub-folders. Lights are sorted from calibration frames when "
            f"you run.")
        self._refresh_calib_preview()
        self._probe_target(files)
        self.btn_run.setEnabled(len(files) >= 10)
        if len(files) < 10:
            self.lbl_status.setText(
                f"Only {len(files)} frame(s) — a light curve needs a time "
                "series. Ten is the bare minimum.")
        else:
            self.lbl_status.setText("Ready.")

    def _target_mode(self) -> str:
        return ("auto", "brightest", "pixel",
                "radec")[self.cmb_target.currentIndex()]

    def _ra_deg(self) -> float:
        txt = self.ed_ra.text().strip()
        if not txt:
            return float("nan")
        val = _sexagesimal(txt)
        # Colons or spaces mean hours by convention; a bare decimal is
        # already degrees.  Guessing from the magnitude alone would put a
        # target at RA 12.5 either at 12.5 deg or at 187.5 deg, and both are
        # plausible-looking sky.
        if re.search(r"[\s:hm]", txt) and np.isfinite(val):
            val *= 15.0
        return val

    def _on_fit_mode(self, *_args) -> None:
        on = self.cmb_fit_mode.currentIndex() == 1
        for w in self._hops_widgets:
            w.setEnabled(on)

    def _on_compute_ldc(self) -> None:
        name = self.ed_target_name.text().strip()
        band = hops_filter_name(self.ed_filter.text())
        if not name:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                "Name the planet in group 3 first — the "
                                "star's temperature and gravity come from "
                                "the archive.")
            return
        if not band:
            if is_narrowband_filter(self.ed_filter.text()):
                QMessageBox.warning(
                    self, "Svenesis LightCurve",
                    "A narrowband filter has no limb-darkening table — "
                    "the Phoenix passband integral needs a broadband "
                    "transmission curve, and HOPS refuses these too. "
                    "Enter the four coefficients by hand, or leave the "
                    "field blank for the quadratic law.")
                return
            QMessageBox.warning(
                self, "Svenesis LightCurve",
                f"The filter '{self.ed_filter.text().strip()}' in group 6 "
                "is not one HOPS knows. Accepted: "
                + ", ".join(sorted(set(HOPS_FILTERS)))
                + "; also Red/Green/Blue (nearest standard passband), "
                "Johnson/Cousins/Sloan/SDSS/2MASS names, L-Pro and "
                "UV/IR-cut (as luminance).")
            return
        self._hops_filter_note = hops_filter_note(self.ed_filter.text())
        if not SVO_FILTER_IDS.get(band) and band not in PLC_PASSBANDS:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                f"No public transmission curve for the "
                                f"{band} passband — enter the four "
                                "coefficients by hand.")
            return
        self.btn_hops_ldc.setEnabled(False)
        self.lbl_status.setText("Computing the limb-darkening coefficients "
                                "from Phoenix models…")
        self._ldc_thread = _LdcComputeThread(name, band, self)
        self._ldc_thread.progress.connect(self.lbl_status.setText)
        self._ldc_thread.done.connect(self._on_hops_ldc_done)
        self._ldc_thread.start()

    def _on_hops_ldc_done(self, vals, note: str) -> None:
        self.btn_hops_ldc.setEnabled(self.cmb_fit_mode.currentIndex() == 1)
        if not vals:
            self.lbl_status.setText("HOPS coefficients: " + note)
            QMessageBox.warning(self, "Svenesis LightCurve", note)
            return
        text = ", ".join(f"{v:.5f}" for v in vals)
        self.ed_hops_ldc.setText(text)
        self._hops_ldc_text = text
        alias = getattr(self, "_hops_filter_note", "") or ""
        if alias:
            note = f"{note} ({alias})"
        self._hops_ldc_note = note
        self.lbl_status.setText("Claret coefficients: " + note)

    def _opts(self) -> dict:
        ra = self._ra_deg()
        dec = _sexagesimal(self.ed_dec.text())
        lat = _sexagesimal(self.ed_lat.text())
        lon = _sexagesimal(self.ed_lon.text())
        try:
            xy = (float(self.ed_x.text()), float(self.ed_y.text()))
        except (ValueError, TypeError):
            xy = None
        return {
            "copy_frames": self.chk_copy.isChecked(),
            "calibrate": self.chk_calibrate.isChecked(),
            "calib_library": self._library,
            "cfa": self.chk_cfa.isChecked(),
            "target_mode": self._target_mode(),
            "target_xy": xy,
            "target_radec": (ra, dec) if np.isfinite(ra) and np.isfinite(dec) else None,
            "target_ra_deg": ra if np.isfinite(ra) else None,
            "target_dec_deg": dec if np.isfinite(dec) else None,
            "site_lat_deg": lat if np.isfinite(lat) else None,
            "site_lon_deg": lon if np.isfinite(lon) else None,
            "n_comps": self.spin_comps.value(),
            "min_comp_snr": self.spin_snr.value(),
            "channel": self.spin_channel.value(),
            "autoring": self.chk_autoring.isChecked(),
            "scan_aperture": self.chk_scan_aper.isChecked(),
            "screen_comps": self.chk_screen.isChecked(),
            "write_aavso": self.chk_aavso.isChecked(),
            "obscode": self.ed_obscode.text().strip(),
            "resolve_target": self.chk_resolve.isChecked(),
            "target_name": self.ed_target_name.text().strip(),
            "filter_name": self.ed_filter.text().strip(),
            "detrend_airmass": self.chk_detrend.isChecked(),
            "fit_mode": ("hops" if self.cmb_fit_mode.currentIndex() == 1
                         else "blind"),
            "hops_detrend": ("airmass", "linear", "quadratic")[
                self.cmb_hops_detrend.currentIndex()],
            "hops_iterations": self.spin_hops_iter.value(),
            "hops_ldc": parse_claret_ldc(self.ed_hops_ldc.text()),
            "hops_ldc_note": (self._hops_ldc_note
                              if self.ed_hops_ldc.text().strip()
                              == self._hops_ldc_text else ""),
        }

    def _on_run(self) -> None:
        if not self._folder:
            return
        opts = self._opts()
        if (opts["fit_mode"] == "hops" and self.ed_hops_ldc.text().strip()
                and opts["hops_ldc"] is None):
            QMessageBox.warning(self, "Svenesis LightCurve",
                                "The Claret coefficients need exactly four "
                                "numbers (a1, a2, a3, a4), or leave the "
                                "field blank for the quadratic defaults.")
            return
        if opts["target_mode"] == "pixel" and opts["target_xy"] is None:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                "Pixel mode needs both an x and a y.")
            return
        if opts["target_mode"] == "radec" and opts["target_radec"] is None:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                "RA/Dec mode needs both coordinates.")
            return
        self._save_settings()
        self.log_view.clear()
        self._set_running(True)
        self._worker = LightCurveWorker(self.siril, self._folder, opts)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _set_running(self, busy: bool) -> None:
        self.btn_run.setEnabled(not busy and bool(self._folder))
        self.btn_folder.setEnabled(not busy)
        if busy:
            self.btn_png.setEnabled(False)
            self.btn_report.setEnabled(False)

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress.setValue(int(pct))
        self.lbl_status.setText(msg)

    def _on_failed(self, msg: str) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.lbl_status.setText("Failed — see the Log tab.")
        self._log(msg, LogColor.RED)
        self.tabs.setCurrentWidget(self.log_view)
        QMessageBox.critical(self, "Svenesis LightCurve", msg.split("\n\n")[0])

    def _on_done(self, r: dict) -> None:
        self._result = r
        self._set_running(False)
        self.btn_png.setEnabled(True)
        self.btn_report.setEnabled(True)
        self.lbl_status.setText(
            f"{r['n_points']} points · RMS {r['rms_mmag']:.2f} mmag")
        self._fill_comps(r)
        self.info.setHtml(self._result_html(r))
        self._redraw()
        self.tabs.setCurrentWidget(self.plot_page)

    def _fill_comps(self, r: dict) -> None:
        rows = [("Target", r["target_xy"][0], r["target_xy"][1], float("nan"))]
        for i, (x, y, snr) in enumerate(r["comps"], start=1):
            rows.append((f"Comp {i}", x, y, snr))
        self.tbl_comps.setRowCount(len(rows))
        for i, (name, x, y, snr) in enumerate(rows):
            self.tbl_comps.setItem(i, 0, QTableWidgetItem(name))
            self.tbl_comps.setItem(i, 1, QTableWidgetItem(f"{x:.1f}"))
            self.tbl_comps.setItem(i, 2, QTableWidgetItem(f"{y:.1f}"))
            self.tbl_comps.setItem(
                i, 3, QTableWidgetItem("—" if not np.isfinite(snr)
                                       else f"{snr:.0f}"))
            if i == 0:
                for c in range(4):
                    it = self.tbl_comps.item(i, c)
                    if it:
                        it.setForeground(QColor("#88aaff"))

    def _redraw(self) -> None:
        if self._result is not None:
            self.plot.render(self._result, self.spin_bins.value(),
                             self.chk_errbars.isChecked(),
                             self.chk_expected.isChecked())

    # -- reporting --------------------------------------------------------
    def _result_html(self, r: dict) -> str:
        fit = r.get("fit")
        p = [f'<div style="font-family:\'{fixed_font_family()}\';'
             'font-size:9pt;color:#dddddd">']
        p.append(f"<h3 style='color:#88aaff'>{os.path.basename(r['folder'])}</h3>")
        p.append("<b>Photometry</b><br>")
        p.append(f"&nbsp;{r['n_points']} of {r['n_files']} frames measured<br>")
        p.append(f"&nbsp;target at ({r['target_xy'][0]:.1f}, "
                 f"{r['target_xy'][1]:.1f}) — {r['target_how']}<br>")
        if r.get("n_clipped"):
            p.append(f"&nbsp;{r['clip_note']}<br>")
        if r.get("aperture_px"):
            p.append(f"&nbsp;aperture {r['aperture_px']:.2f} px chosen by "
                     f"scan ({r['aperture_px'] / max(r['fwhm_px'], 1e-9):.2f}"
                     " × FWHM)<br>")
        dropped = [row for row in r.get("comp_rows", []) if "DROP" in row[3]]
        if dropped:
            p.append(f"&nbsp;<span style='color:#ddaa88'>{len(dropped)} "
                     "comparison star(s) dropped for their own "
                     "variability</span><br>")
        p.append(f"&nbsp;{len(r['comps'])} comparison stars, "
                 f"{len(r['rejected'])} rejected<br>")
        p.append(f"&nbsp;median FWHM {r['fwhm_px']:.2f} px<br>")
        if r.get("yield_note"):
            p.append(f"&nbsp;<span style='color:#e08080'>"
                     f"{r['yield_note']}</span><br>")
        if r.get("flip_deg", 0.0) >= FLIP_ROTATION_DEG:
            p.append(f"&nbsp;<span style='color:#ddaa88'>meridian flip: the "
                     f"field rotates {r['flip_deg']:.0f}° across the run. The "
                     "target sits on a different patch of sensor after it, so "
                     "a step in the curve at that point is instrumental, not "
                     "astrophysical.</span><br>")
        p.append(f"&nbsp;scatter {r['raw_rms_mmag']:.2f} mmag before "
                 f"detrending, {r['rms_mmag']:.2f} mmag after<br><br>")

        p.append("<b>Airmass</b><br>")
        if r["slope"] is not None:
            p.append(f"&nbsp;ramp removed: {r['slope'] * 1000.0:+.1f} "
                     "mmag per airmass<br>")
            p.append("&nbsp;baseline anchored on the "
                     + ("fitted out-of-transit points (second pass)"
                        if r["refined"] else "trimmed brightest points")
                     + "<br>")
        else:
            why = r.get("airmass_note") or "not requested"
            p.append(f"&nbsp;not removed — {why}<br>")
        if r.get("multi_used"):
            p.append(f"&nbsp;quality detrend: {r['multi_note']}, anchored on "
                     "the out-of-transit points<br>")
        elif r.get("multi_note"):
            p.append(f"&nbsp;quality detrend not applied — "
                     f"{r['multi_note']}<br>")
        p.append("<br>")

        p.append("<b>Transit fit</b><br>")
        if fit is None:
            p.append("&nbsp;too few usable points to attempt a fit.<br>")
        elif not fit["detected"]:
            p.append(f"&nbsp;<span style='color:#dd8866'>No transit claimed."
                     f"</span> The best template reaches only "
                     f"{fit['significance']:.1f}σ against a "
                     f"{MIN_DETECTION_SIGMA:.1f}σ floor.<br>")
            p.append(f"&nbsp;(For the curious: it wanted "
                     f"{fit.get('blind_depth_mmag', fit['depth_mmag']):.1f} "
                     f"mmag over "
                     f"{fit.get('blind_duration_h', fit['duration_h']):.2f} h. "
                     "Do not quote that.)<br>")
        else:
            p.append(f"&nbsp;<span style='color:#66dd88'>Transit detected at "
                     f"{fit['significance']:.1f}σ.</span><br>")
            p.append(f"&nbsp;red-noise β {fit['red_noise_beta']:.2f} "
                     f"({fit['significance_white']:.1f}σ before the "
                     "correlated-noise correction)<br>")
            p.append("<span style='color:#888888'>&nbsp;false alarm "
                     f"{100 * MEASURED_FALSE_ALARM:.2f} % at the "
                     f"{MIN_DETECTION_SIGMA:.1f}σ floor — measured over "
                     f"{MEASURED_FALSE_ALARM_RUNS} transit-free noise runs "
                     "through this same ~40 000-node search, NOT the "
                     "Gaussian value for that σ.</span><br>")
            p.append(f"&nbsp;T0 &nbsp;&nbsp; {fit['t0']:.5f} ± "
                     + (f"{fit['t0_sigma_s']:.0f} s"
                        if np.isfinite(fit.get('t0_sigma_d', float('nan')))
                        else "(unconstrained)")
                     + f" &nbsp;{r['time_system']}, mid-exposure<br>")
            for line, _h in oc_lines(r, fit):
                p.append("&nbsp;" + line.strip().replace("O-C", "O−C")
                         + "<br>")
            p.append("&nbsp;χ²/ν&nbsp; "
                     + (f"{fit['chi2_nu']:.2f}" if np.isfinite(
                         fit.get('chi2_nu', float('nan'))) else "—")
                     + (f" ± {fit['chi2_nu_sigma']:.2f}" if np.isfinite(
                         fit.get('chi2_nu_sigma', float('nan'))) else "")
                     + " <span style='color:#888888'>("
                     + (fit.get("chi2_nu_note") or "~1 = the model "
                        "describes the data; the bar is the white-noise "
                        "scatter of the number itself")
                     + ")</span><br>")
            if r["time_system"] != "BJD_TDB":
                p.append("&nbsp;<span style='color:#e08080'>This T0 is NOT "
                         "comparable with a published ephemeris — those are "
                         "quoted in BJD_TDB and the offset reaches 8 minutes."
                         f" ({r['time_note']})</span><br>")
            p.append(f"&nbsp;depth&nbsp; {fit['depth_mmag']:.1f} ± "
                     f"{fit['depth_sigma_mmag']:.1f} mmag "
                     f"({fit['depth_pct']:.3f} % of the flux, at the "
                     "limb-darkened CENTRE of the transit)<br>")
            if fit.get("rprs") is not None:
                p.append(f"&nbsp;Rp/R★ {fit['rprs']:.4f}"
                         + (f" ± {fit['rprs_sigma']:.4f}"
                            if fit.get("rprs_sigma") is not None else "")
                         + f" → (Rp/R★)² = {fit['depth_rprs2_pct']:.2f}"
                         + (f" ± {fit['depth_rprs2_pct_sigma']:.2f}"
                            if fit.get("depth_rprs2_pct_sigma") is not None
                            else "") + " %<br>")
                p.append("<span style='color:#888888'>&nbsp;that is the "
                         "depth convention EXOTIC, HOPS and AstroImageJ "
                         "quote — with limb darkening the central depth "
                         "above is deeper than (Rp/R★)², so compare THIS "
                         "number with theirs and with the archive.</span>"
                         "<br>")
            p.append("<span style='color:#888888'>&nbsp;that ± carries the "
                     "same red-noise scaling as the significance, but "
                     "depth/error is NOT the significance: it uses the "
                     "fitted depth against one baseline, while the "
                     "significance uses the measured contrast against the "
                     "weaker of the two sides. Quote the "
                     "significance.</span><br>")
            p.append(f"&nbsp;length {fit['duration_h']:.2f} h, ingress "
                     f"shape rp/R★≈{fit['rp_over_rs']:.2f}, b≈"
                     f"{fit['impact_b']:.1f}<br>")
            p.append("<span style='color:#888888'>&nbsp;that rp/R★ is the "
                     "template that fitted best, NOT a measured planet "
                     "radius: with the duration free a smaller template "
                     "stretched fits nearly as well. The DEPTH is the "
                     "measurement.</span><br>")
            p.append(f"&nbsp;{fit['n_in']} points inside, {fit['n_out']} "
                     "outside<br>")
            p.append(f"&nbsp;residual scatter {fit['rms_resid_mmag']:.2f} "
                     "mmag<br>")
            if fit["duty_cycle"] > BLIND_DETREND_BREAKDOWN:
                # The depth comes from the simultaneous fit, whose bar
                # already carries the baseline's uncertainty; the old
                # advice to read the depth as a floor described the
                # trimmed detrend that is now display-only.
                p.append(f"<br>&nbsp;<span style='color:#ddaa88'>The event "
                         f"covers {fit['duty_cycle'] * 100:.0f} % of the run, "
                         "so the baseline and the systematics rest on few "
                         "out-of-transit points. The depth and the baseline "
                         "were fitted together and the bars include that, but "
                         "more baseline before ingress and after egress is "
                         "the only real fix.</span><br>")
        if r.get("csv_path"):
            p.append(f"<br><b>Written</b><br>&nbsp;{r['csv_path']}<br>")
        p.append("</div>")
        return "".join(p)

    def _report_text(self, r: dict) -> str:
        fit = r.get("fit")
        L = []
        A = L.append
        A(f"Svenesis LightCurve {VERSION} — light curve report")
        A(f"Generated {datetime.datetime.now().isoformat(timespec='seconds')}")
        A("")
        A(f"Folder            {r['folder']}")
        A(f"Calibration       {r.get('calib_note') or 'not recorded'}")
        A(f"Frames            {r['n_points']} measured of {r['n_files']} found")
        A(f"Target            ({r['target_xy'][0]:.2f}, {r['target_xy'][1]:.2f})"
          f"  [{r['target_how']}]")
        A(f"Comparison stars  {len(r['comps'])} used, {len(r['rejected'])} rejected")
        for x, y, rms, verdict in r.get("comp_rows", []):
            A(f"   variability    ({x:8.2f}, {y:8.2f})  "
              + ("     —" if not np.isfinite(rms) else f"{rms:6.1f} mmag")
              + f"  {verdict}")
        if r.get("aperture_px"):
            A(f"Aperture          {r['aperture_px']:.2f} px chosen by scan "
              f"({r['aperture_px'] / max(r['fwhm_px'], 1e-9):.2f} x FWHM)")
            for a, n, rms in r.get("aper_rows", []):
                A(f"   tried          {a:5.2f} px  {n:4d} point(s)  "
                  + ("     —" if not np.isfinite(rms) else f"{rms:6.2f} mmag")
                  + ("   <-- chosen" if abs(a - r["aperture_px"]) < 1e-9
                     else ""))
        if r.get("n_clipped"):
            A(f"Outliers          {r['clip_note']}")
        for i, (x, y, snr) in enumerate(r["comps"], start=1):
            A(f"   comp {i:<2d}       ({x:8.2f}, {y:8.2f})  "
              + ("SNR —" if not np.isfinite(snr) else f"SNR {snr:.0f}"))
        for x, y, why in r["rejected"]:
            A(f"   rejected       ({x:8.2f}, {y:8.2f})  {why}")
        A(f"Median FWHM       {r['fwhm_px']:.2f} px")
        A(f"Frames kept       {len(r['jd'])} of {r.get('n_frames', 0)}")
        if r.get("yield_note"):
            A(f"   <-- {r['yield_note']}")
        A(f"Field rotation    {r.get('flip_deg', 0.0):.2f} deg across the run"
          + ("   <-- MERIDIAN FLIP: expect an instrumental step"
             if r.get("flip_deg", 0.0) >= FLIP_ROTATION_DEG else ""))
        A("")
        A(f"Scatter           {r['raw_rms_mmag']:.2f} mmag raw, "
          f"{r['rms_mmag']:.2f} mmag detrended  (robust, MAD-based)")
        if r["slope"] is not None:
            A(f"Airmass ramp      {r['slope'] * 1000.0:+.2f} mmag/airmass, "
              + ("anchored on the fitted out-of-transit points"
                 if r["refined"] else "blind trimmed baseline"))
        if r.get("multi_used"):
            A(f"Quality detrend   {r['multi_note']}")
            A("                  (Siril's own per-frame registration "
              "measurements, anchored on the")
            A("                  out-of-transit points so the depth cannot "
              "be absorbed)")
        elif r.get("multi_note"):
            A(f"Quality detrend   not applied — {r['multi_note']}")
        else:
            A(f"Airmass ramp      not removed — {r.get('airmass_note') or 'not requested'}")
        A("")
        if fit is None:
            A("Transit fit       not attempted — too few usable points")
        elif not fit["detected"]:
            A(f"Transit fit       NOT CLAIMED — best template reaches only "
              f"{fit['significance']:.2f} sigma")
            A(f"                  (floor is {MIN_DETECTION_SIGMA:.1f} sigma; "
              "the fitted numbers below are not a measurement)")
            A(f"   depth          "
              f"{fit.get('blind_depth_mmag', fit['depth_mmag']):.2f} mmag")
            A(f"   duration       "
              f"{fit.get('blind_duration_h', fit['duration_h']):.3f} h")
        else:
            A(f"Transit fit       DETECTED at {fit['significance']:.2f} sigma")
            A(f"   Significance   {fit['significance']:.1f} sigma "
          f"(white-noise value {fit['significance_white']:.1f}, "
          f"red-noise beta {fit['red_noise_beta']:.2f})")
            # Everything below describes a CLAIMED fit: it used to sit one
            # indent too far out, so a run with no fit crashed the save
            # button on fit.get, and an unclaimed run printed T0, O-C and
            # chi2/nu under a caveat that said they were not a measurement.
            A(f"   False alarm    {100 * MEASURED_FALSE_ALARM:.2f} % at the "
              f"{MIN_DETECTION_SIGMA:.1f} sigma floor")
            A(f"                  (measured, {MEASURED_FALSE_ALARM_RUNS} "
              "transit-free noise runs through this same grid search;")
            A("                  the search is over ~40 000 nodes, so this is "
              "NOT the Gaussian value for that sigma)")
            for w, b, nb, k in fit.get("red_noise_rows", []):
                A(f"      bin {w * 24 * 60:5.1f} min  beta {b:4.2f}  "
                  f"{nb} bins of ~{k:.1f} points")
            A(f"   T0             {fit['t0']:.6f} +/- "
              + (f"{fit['t0_sigma_d']:.6f} d ({fit['t0_sigma_s']:.0f} s)"
                 if np.isfinite(fit.get('t0_sigma_d', float('nan')))
                 else "(unconstrained)")
              + f"  {r['time_system']}, mid-exposure")
            for line, _h in oc_lines(r, fit):
                A(line)
            A(f"   chi2/nu        "
              + (f"{fit['chi2_nu']:.2f}" if np.isfinite(
                  fit.get('chi2_nu', float('nan'))) else "—")
              + (f" +/- {fit['chi2_nu_sigma']:.2f}" if np.isfinite(
                  fit.get('chi2_nu_sigma', float('nan'))) else ""))
            if fit.get("chi2_nu_note"):
                A(f"                  ({fit['chi2_nu_note']})")
            else:
                A("                  (~1 = the model describes the data; the "
                  "bar is the white-noise scatter of the number itself;")
                A("                  well above 1 + bar means it does not, well "
                  "below means the noise floor is too large)")
            A(f"   Time system    {r['time_note']}")
            if r["time_system"] != "BJD_TDB":
                A("                  <-- NOT comparable with a published "
                  "ephemeris (those use BJD_TDB; the offset reaches 8 minutes)")
            # This block sat INSIDE the != BJD_TDB branch above — every run
            # with correct timestamps saved a report without its own depth.
            A(f"   depth          {fit['depth_mmag']:.2f} +/- "
              f"{fit['depth_sigma_mmag']:.2f} mmag "
              f"({fit['depth_pct']:.4f} % of flux, limb-darkened CENTRE)")
            A("                  the +/- carries the same red-noise scaling "
              "as the significance above, but")
            A("                  depth/error is NOT that significance — it "
              "uses the fitted depth against")
            A("                  one baseline, the significance the "
              "measured contrast against the weaker")
            A("                  of both sides. Quote the significance.")
            if fit.get("rprs") is not None:
                A(f"   Rp/Rs          {fit['rprs']:.4f}"
                  + (f" +/- {fit['rprs_sigma']:.4f}"
                     if fit.get("rprs_sigma") is not None else ""))
                A(f"   (Rp/Rs)^2      {fit['depth_rprs2_pct']:.2f}"
                  + (f" +/- {fit['depth_rprs2_pct_sigma']:.2f}"
                     if fit.get("depth_rprs2_pct_sigma") is not None else "")
                  + " %  <- the depth convention EXOTIC, HOPS and")
                A("                  AstroImageJ quote; compare THIS with "
                  "theirs and with the archive,")
                A("                  not the limb-darkened central depth "
                  "above")
            A(f"   duration       {fit['duration_h']:.3f} h")
            hops = fit.get("hops")
            if hops:
                g = hops["geom"]
                A(f"   shape          from the orbit: a/R* {g['a_rs']:.3f}, "
                  f"i {g['inc_deg']:.2f} deg, e {g['ecc']:.3f}, "
                  f"omega {g['peri_deg']:.1f} deg, b {hops['impact_b']:.2f}")
                A("                  limb darkening Claret a1..a4 = "
                  + ", ".join(f"{c:.4f}" for c in hops["ldc"]))
            else:
                A(f"   shape          rp/Rs ~ {fit['rp_over_rs']:.2f}, "
                  f"b ~ {fit['impact_b']:.1f}, limb darkening "
                  f"u1={fit['ld_u1']:.2f} u2={fit['ld_u2']:.2f}")
                A("                  (that rp/Rs is the best-fitting TEMPLATE, "
                  "not a measured planet radius:")
                A("                  with the duration free a smaller template "
                  "stretched fits nearly as well.")
                A("                  The depth is the measurement, and the "
                  "Rp/Rs above derives from it.)")
            A(f"   points         {fit['n_in']} in, {fit['n_out']} out")
            A(f"   residual RMS   {fit['rms_resid_mmag']:.2f} mmag")
            A(f"   duty cycle     {fit['duty_cycle'] * 100:.0f} % of the run")
            if hops:
                A("")
                A("HOPS-compatible mode (ephemeris-locked fit)")
                A(f"   photometry     {hops['photometry']}")
                A(f"   geometry       {hops['geom_note']}")
                A(f"   limb darkening {hops['ldc_note']}")
                A("   exposure       "
                  + (f"model averaged over {hops['sub_steps']} sub-steps of "
                     f"the {hops['exp_s']:g} s exposure, as HOPS does"
                     if hops.get("exp_s") else
                     "no exposure time known — model at mid-exposure"))
                A(f"   detrending     {hops['detrend']} "
                  f"({' + '.join(hops['names'])})"
                  + (f" — {hops['detrend_note']}" if hops.get("detrend_note")
                     else ""))
                for name, c, sg in zip(hops["names"], fit["basis_coeffs"],
                                       fit["coeff_sigmas"][1:]):
                    A(f"      {name:<12s} {c:+.5f} +/- {sg:.5f}")
                A(f"   Rp/R*          {fit['rprs']:.5f} -{hops['rp_m']:.5f} "
                  f"+{hops['rp_p']:.5f}  (started from {hops['rp_source']})")
                A(f"   mid-time       {fit['t0']:.6f} -{hops['mid_m']:.6f} "
                  f"+{hops['mid_p']:.6f} d  (prior +/- 0.2 d around "
                  f"{hops['mid_note']})")
                A(f"   outliers       {hops['outliers']} removed by HOPS's "
                  "iterative 3-sigma filter")
                A(f"   error scaling  x {hops['scale_factor']:.4f} so that "
                  "chi2/nu = 1 before sampling")
                A(f"   sampler        {hops['iterations']} iterations x "
                  f"{hops['walkers']} walkers, {hops['burn_in']} burn-in "
                  f"steps discarded, acceptance {hops['acceptance']:.2f}")
                A("                  (Goodman-Weare stretch move, the "
                  "algorithm emcee uses; seeded, so a rerun repeats)")
                A("                  values and bars are the 16/50/84 "
                  "percentiles of the posterior, as HOPS reports them")
                A("   NOTE           this mode MEASURES the catalogue's "
                  "planet; the detection verdict above")
                A("                  is still the blind test's, and only "
                  "that says whether a transit is claimed")
                if hops.get("coverage_warning"):
                    A("   WARNING        " + hops["coverage_warning"])
        A("")
        A("Method")
        if r.get("engine") == "native":
            A("   Aperture photometry by this script: every star re-centroided")
            A("   per frame (follow star), subpixel circular apertures, "
              "sigma-clipped")
            A("   annulus sky, aperture chosen by point-to-point noise, comps")
            A("   kept by measured scatter. Siril did detection, registration")
            A("   and calibration.")
        else:
            A("   Aperture photometry by Siril's own light_curve command")
        A("   Registration two-pass, NOT resampled — the aperture follows the")
        A("   star through the registration data while the pixels stay as the")
        A("   sensor recorded them.")
        A("   Limb-darkened template fit: grid over T0/duration, depth and")
        A("   baseline solved analytically at each node. Deterministic, no")
        A("   optimiser.")
        A("   Significance is the in/out contrast over its own standard error,")
        A("   measured empirically rather than taken from the fitted depth.")
        return "\n".join(L)

    def _on_save_png(self) -> None:
        if self._result is None:
            return
        default = os.path.join(self._result["out_dir"], "lightcurve.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save plot", default, "PNG image (*.png)")
        if not path:
            return
        if self.plot.save_png(path):
            self.lbl_status.setText(f"Plot saved to {path}")
        else:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                "The plot could not be written.")

    def _on_save_report(self) -> None:
        if self._result is None:
            return
        # `results.txt` matches HOPS's own filename and layout, so
        # anything that parses a HOPS fitting folder parses this file.
        # The full narrative report is written NEXT TO it as report.txt
        # in the same click — the HOPS table cannot carry the comps,
        # the rejections or the method, and losing those to a rename
        # would be a silent regression.
        default = os.path.join(self._result["out_dir"], "results.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save results", default, "Text file (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(hops_results_text(self._result))
            report_path = os.path.join(os.path.dirname(path), "report.txt")
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(self._report_text(self._result))
            self.lbl_status.setText(
                f"Results (HOPS format) saved to {path}; "
                f"full report to {report_path}")
        except OSError as exc:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                f"The results could not be written: {exc}")

    # -- settings ---------------------------------------------------------
    def _load_settings(self) -> None:
        st = self._settings
        self.ed_ra.setText(str(st.value("target_ra", "")))
        self.ed_dec.setText(str(st.value("target_dec", "")))
        self.ed_lat.setText(str(st.value("site_lat", "")))
        self.ed_lon.setText(str(st.value("site_lon", "")))
        try:
            self.spin_comps.setValue(int(st.value("n_comps", DEFAULT_N_COMPS)))
            self.spin_snr.setValue(float(st.value("min_snr", MIN_COMP_SNR)))
            self.spin_channel.setValue(int(st.value("channel", 0)))
        except (TypeError, ValueError):
            pass
        lib = str(st.value("calib_library", "") or "")
        if lib and os.path.isdir(lib):
            self._library = lib
            self.lbl_library.setText(lib)
        self.chk_calibrate.setChecked(
            str(st.value("calibrate", "true")) == "true")
        self.chk_cfa.setChecked(str(st.value("cfa", "false")) == "true")
        self.chk_scan_aper.setChecked(
            str(st.value("scan_aperture", "true")) == "true")
        self.chk_screen.setChecked(
            str(st.value("screen_comps", "true")) == "true")
        self.chk_aavso.setChecked(str(st.value("aavso", "true")) == "true")
        self.ed_obscode.setText(str(st.value("obscode", DEFAULT_OBSCODE)
                                    or DEFAULT_OBSCODE))
        self.ed_target_name.setText(str(st.value("target_name", "") or ""))
        self.chk_resolve.setChecked(
            str(st.value("resolve_target", "true")).lower() != "false")
        self.ed_filter.setText(str(st.value("filter_name", "") or ""))
        self.chk_autoring.setChecked(str(st.value("autoring", "true")) == "true")
        self.chk_detrend.setChecked(str(st.value("detrend", "true")) == "true")
        try:
            self.cmb_fit_mode.setCurrentIndex(
                1 if str(st.value("fit_mode", "blind")) == "hops" else 0)
            self.cmb_hops_detrend.setCurrentIndex(
                max(0, min(2, int(st.value("hops_detrend", 0)))))
            self.spin_hops_iter.setValue(int(st.value("hops_iterations",
                                                      2000)))
        except (TypeError, ValueError):
            pass
        self.ed_hops_ldc.setText(str(st.value("hops_ldc", "") or ""))
        self._on_fit_mode()

    def _save_settings(self) -> None:
        st = self._settings
        st.setValue("target_ra", self.ed_ra.text())
        st.setValue("target_dec", self.ed_dec.text())
        st.setValue("site_lat", self.ed_lat.text())
        st.setValue("site_lon", self.ed_lon.text())
        st.setValue("n_comps", self.spin_comps.value())
        st.setValue("min_snr", self.spin_snr.value())
        st.setValue("channel", self.spin_channel.value())
        st.setValue("calib_library", self._library)
        st.setValue("calibrate",
                    "true" if self.chk_calibrate.isChecked() else "false")
        st.setValue("cfa", "true" if self.chk_cfa.isChecked() else "false")
        st.setValue("scan_aperture",
                    "true" if self.chk_scan_aper.isChecked() else "false")
        st.setValue("screen_comps",
                    "true" if self.chk_screen.isChecked() else "false")
        st.setValue("aavso", "true" if self.chk_aavso.isChecked() else "false")
        st.setValue("obscode", self.ed_obscode.text().strip())
        st.setValue("target_name", self.ed_target_name.text().strip())
        st.setValue("resolve_target", self.chk_resolve.isChecked())
        st.setValue("filter_name", self.ed_filter.text().strip())
        st.setValue("autoring", "true" if self.chk_autoring.isChecked() else "false")
        st.setValue("detrend", "true" if self.chk_detrend.isChecked() else "false")
        st.setValue("fit_mode",
                    "hops" if self.cmb_fit_mode.currentIndex() == 1 else "blind")
        st.setValue("hops_detrend", self.cmb_hops_detrend.currentIndex())
        st.setValue("hops_iterations", self.spin_hops_iter.value())
        st.setValue("hops_ldc", self.ed_hops_ldc.text().strip())

    # -- coffee -----------------------------------------------------------
    def _show_coffee_dialog(self) -> None:
        BMC_URL = "https://buymeacoffee.com/sramuschkat"
        dlg = QDialog(self)
        dlg.setWindowTitle("☕ Support Svenesis LightCurve")
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
            "<b style='color:#e0e0e0;'>Enjoying Svenesis LightCurve?</b><br><br>"
            "This tool is free and open source. It's built with love for the "
            "astrophotography community by <b style='color:#88aaff;'>Sven Ramuschkat</b> "
            "(<span style='color:#88aaff;'>svenesis.org</span>).<br><br>"
            "If LightCurve turned a folder of subs into a transit you could "
            "actually measure — consider buying me a coffee to keep "
            "development going!<br><br>"
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

    # -- help -------------------------------------------------------------
    def _show_help(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Svenesis LightCurve {VERSION} — Help")
        dlg.setStyleSheet(DARK_STYLESHEET)
        dlg.resize(880, 720)
        lay = QVBoxLayout(dlg)
        tabs = QTabWidget()

        def _tab(title: str, html: str) -> None:
            view = QTextEdit()
            view.setReadOnly(True)
            view.setHtml(html)
            view.setStyleSheet(
                "background-color:#1e1e1e;border:1px solid #444444;"
                "border-radius:4px;padding:8px;")
            tabs.addTab(view, title)

        _tab("What it does", """
<h2 style='color:#88aaff'>From a folder of subs to a light curve</h2>
<p>Point this at the folder holding one night's sub-exposures of an
exoplanet host star. It measures how the star's brightness changed relative
to other stars in the same field, and tells you whether there is a transit
in the result.</p>
<h3 style='color:#88aaff'>Who does what</h3>
<p><b>Siril</b> does what it is demonstrably good at: staging,
calibration, two-pass registration, star detection, the plate solve and
per-frame quality.</p>
<p><b>This script</b> measures the flux itself, the way EXOTIC and HOPS
do: every star re-centroided per frame from its registration-predicted
position (the "follow star" Siril's <tt>light_curve</tt> lacks),
subpixel circular apertures against a sigma-clipped sky annulus, the
aperture chosen by point-to-point noise, comparison stars kept or
dropped by their measured scatter, errors from the CCD equation with
every term measured. Then the parts nobody's pixels decide: removing
the airmass ramp, fitting the transit — and, above all, deciding
whether the dip is real. Measured on the same drifting 142-frame run:
this engine keeps 140 points where <tt>light_curve</tt> kept 67 — and
<tt>light_curve</tt> remains intact as the loud fallback.</p>
<h3 style='color:#88aaff'>Why not Siril's own light-curve tool?</h3>
<p>Siril's native workflow produces a light curve; this script produces
a <i>measurement</i>. Natively you load the sequence, solve the
reference, pick the stars by hand or catalogue, and
<tt>light_curve</tt> writes a three-column file — the analysis ends
there. It also moves its measurement box by the registration but never
re-centroids, refuses outright above 160 px of total drift, and fails
the whole command when one star leaves the chip. This script
re-centroids every star, re-picks the reference, drops only the star
that drifts off — and adds everything after the curve: BJD_TDB, the
simultaneous limb-darkened fit, calibrated significance, O−C and the
AAVSO file. The full point-by-point comparison, with the Siril
documentation linked, is in the manual's FAQ — links below this
window.</p>
<h3 style='color:#88aaff'>The steps</h3>
<ol>
<li><b>Stage</b> — your subs are symlinked into a working folder. The
original folder is never written to.</li>
<li><b>Link + Calibrate</b> — Siril builds a sequence; calibration
frames found beside the lights become masters and are applied via
Siril's own <tt>calibrate</tt>.</li>
<li><b>Register (two-pass)</b> — registration data only, <i>no
resampling</i>. This matters more for photometry than for stacking:
interpolation correlates neighbouring pixel noise and moves flux around
inside the aperture. The aperture follows the star through the
registration data while the pixels stay exactly as the sensor recorded
them.</li>
<li><b>Detect + choose</b> — Siril finds the stars (plate-solving the
reference when the target needs sky coordinates); this script picks the
target and the comparison ensemble.</li>
<li><b>Measure</b> — this script's photometry engine, per frame, all
apertures in one pass. Siril's <tt>light_curve</tt> takes over only if
the engine measures under 30% of the frames, and says so.</li>
<li><b>Analyse</b> — detrend, fit, decide.</li>
</ol>
<h3 style='color:#88aaff'>What you get</h3>
<p><tt>lightcurve/lightcurve.csv</tt> with every point (raw, centred, detrended,
airmass), the plot as PNG — and, when the times are BJD_TDB, an AAVSO
Exoplanet Watch file with T0, both depth conventions (central and
(Rp/R★)²) and Rp/R★ in the header. The <b>Save results</b> button
writes two files in one click: <tt>results.txt</tt> in the exact
layout HOPS leaves in its fitting folder (the parameter table, then
#Filter/#Epoch, then two residual-statistics blocks — anything that
parses a HOPS results.txt parses this one; in HOPS-compatible mode
it is HOPS's own parameter table with posterior bars), and
<tt>report.txt</tt>,
the full narrative report with the comparison stars, every rejection
and the method, ready to attach to a submission or a forum post.</p>
""")

        _tab("Choosing stars", """
<h2 style='color:#88aaff'>The target</h2>
<p>Four ways, and all four end at a <i>detected</i> star:</p>
<ul>
<li><b>From the frames</b> — the default. <tt>OBJCTRA/OBJCTDEC</tt>
from the lights when present; otherwise the archive position of the
planet the frames NAME (<tt>OBJECT</tt>), with the reference frame
plate-solved around it. The frames outrank a value left in the form
from a previous target — that is said out loud, never resolved
silently. Only if nothing names or places the target does it fall to
the brightest star, labelled as the guess it is — and a guess that the
drift would carry off the sensor guesses again among the stars that
stay on it.</li>
<li><b>Brightest</b> — right more often than you would think. A transit
host is usually the reason the field was framed the way it was.</li>
<li><b>Pixel position</b> — from the first frame.</li>
<li><b>RA / Dec</b> — needs plate-solved subs (the run solves the
reference itself when it can).</li>
</ul>
<p>Pixel and RA/Dec both <b>snap to the nearest detected star</b> rather
than using your number directly. A position two pixels off the centroid
puts the aperture off-centre for the whole run, and the flux it loses
changes with the seeing — which is exactly the shape of a fake trend.</p>
<p><b>TESS candidates are a different table.</b> A target named
<tt>TOI-3540.01</tt> is a <i>candidate</i> designation the archive's
confirmed-planet table cannot know. When the planet lookup misses and
the name matches the TOI pattern, the archive's own <tt>toi</tt> list
is asked instead — ppm depth and hour duration converted to the units
the rest of the run speaks. The TFOPWG disposition is said, not
swallowed: PC/CP/KP/APC are informational, <b>FP/FA get a red
warning</b> that a "transit" matching this ephemeris is most likely
not a planet — repeated on cache hits, because a cached false positive
is still a false positive. A bare <tt>TOI-3540</tt> with several
candidates lists them and asks which one.</p>

<h2 style='color:#88aaff'>Calibration</h2>
<p><b>Nothing has to be prepared, and you need not navigate.</b> Point at
your subs — or at any folder above them — and, once, at the folder where
your reusable darks live. The scan is recursive: every FITS underneath is
read once and sorted into lights and calibration frames by its header, so
calibration frames filed anywhere inside your selection are found too.
N.I.N.A. files a night as
<tt>&lt;target&gt;/LIGHT/&lt;date&gt;/&lt;filter&gt;/</tt>, so the script
also walks UP and takes the <tt>FLAT</tt> folder sitting next to
<tt>LIGHT</tt>.</p>
<p>Three things the recursion made necessary: this script's own working and
output folders are never descended into; a repeated <tt>DATE-OBS</tt> is a
copy rather than an exposure and is dropped with a count; and the lights are
reduced to one filter and one exposure, because a change mid-run is two
series and not a longer one.</p>
<p>Two more things about time. The sequence is built in <tt>DATE-OBS</tt>
order, not file-name order: N.I.N.A. puts the sensor temperature in the
file name, <tt>-10.10C</tt> sorts after <tt>-10.00C</tt>, and five
mid-run frames once landed at the end and read as a second flip — the log
says how many frames moved. And the time-stamp convention is checked
rather than assumed: a <tt>DATE-AVG</tt> or <tt>DATE-END</tt> header
settles whether <tt>DATE-OBS</tt> is the exposure start, a program that
stamps mid-exposure gets no half-exposure added, and the log names the
stamps the times came from. A <tt>DATE-AVG</tt> more than an exposure
plus a minute away from <tt>DATE-OBS</tt> is not a mid-exposure stamp
and is ignored. When the photometry falls back to Siril's
<tt>light_curve</tt>, whose times are DATE-OBS + EXPTIME/2 by its own
convention, the correction the headers established is applied there too,
so both engines land on the same times.</p>
<p>Frames are grouped by what must agree before they can share a master —
exposure, gain, temperature, binning, image size, camera — then stacked and
cached under names carrying all of it, and reused on the next run. A group
of exactly one file is adopted as a ready-made master rather than stacked.
The pixel work is Siril's <tt>calibrate</tt>; there is no bias/dark/flat
arithmetic in this script, for the same reason there is no photometry in
it.</p>
<p>This does <b>not</b> break the no-resampling promise: bias, dark and
flat are per-pixel arithmetic. It does write a second copy of every frame,
so the working folder doubles.</p>
<p>What it refuses is said out loud — a master that was found and rejected
leaves a run that looks exactly like one where no master existed:</p>
<table cellpadding='5'>
<tr><td style='color:#88aaff'><b>Wrong exposure</b></td>
<td>A 3 s dark on 60 s lights removes 5% of the dark current, leaves the
rest in, and adds its own read noise to every frame. Named with both
numbers and with what it would have done.</td></tr>
<tr><td style='color:#88aaff'><b>Wrong temperature</b></td>
<td>Darks are grouped by temperature: a −10 °C and a −20 °C frame averaged
into one master is correct for neither. Bias is <i>not</i> split — it is
read noise only, and splitting it would just make each master
noisier.</td></tr>
<tr><td style='color:#88aaff'><b>Wrong camera or size</b></td>
<td>Two bodies of the same sensor format would otherwise calibrate each
other.</td></tr>
<tr><td style='color:#88aaff'><b>Bias next to a dark</b></td>
<td>Never both on the lights — the dark already contains the offset, and
subtracting both removes it twice. The bias still corrects the flats:
Lc = (L − D) / (F − O).</td></tr>
<tr><td style='color:#88aaff'><b>Already calibrated?</b></td>
<td>Read from <tt>CALSTAT</tt> or a HISTORY card, with three answers, not
two. N.I.N.A. writes neither, so a raw light and a calibrated one that lost
its provenance look the same; "no evidence" is reported as unknown rather
than as raw. A warning that cries wolf is one you learn to skip
past.</td></tr>
</table>

<h2 style='color:#88aaff'>The comparison ensemble</h2>
<p>Differential photometry works by dividing the target by other stars in
the same frame: clouds, transparency and extinction hit them all together,
so the ratio is clean where the raw flux is not. Four filters decide who
gets in:</p>
<table cellpadding='5'>
<tr><td style='color:#88aaff'><b>Saturated</b></td>
<td>A clipped core does not scale with transparency, so a saturated
comparison star turns every passing cloud into a fake transit.</td></tr>
<tr><td style='color:#88aaff'><b>Low SNR</b></td>
<td>A comparison star contributes its own Poisson noise to the ensemble.
Below roughly SNR 20 it adds more scatter than reference.</td></tr>
<tr><td style='color:#88aaff'><b>Too close</b></td>
<td>Within ten FWHM of the target the apertures start sharing sky annulus
and star wings. The contamination is a function of seeing, so it drifts
through the night and looks like a slow trend.</td></tr>
<tr><td style='color:#88aaff'><b>Not isolated</b></td>
<td>The same argument aimed at any neighbour rather than at the target. A
star inside the comparison star's own sky annulus puts part of its light in
the aperture and the rest in the sky estimate, and its share moves with the
seeing. The radius is Siril's own geometry, not taste: the outer ring is
6.3 × FWHM, so two annuli stop sharing sky at twice that — and the tally
says which of the two geometries it means, inside or overlapping.</td></tr>
<tr><td style='color:#88aaff'><b>Leaves the frame</b></td>
<td>The drift envelope is measured from the registration data. A star
that would walk off the sensor part-way through the run is dropped
up front, because a box off the edge is a hole in the curve — or, on
the Siril fallback, the failure of the whole command.</td></tr>
</table>
<p>Every rejection is listed in the Log and in the report, and the tally
accounts for every detected star — including the ones that passed every
filter and were merely surplus. The target cannot be dropped, so the same
geometry is reported for it instead.</p>
<p><b>And then they are measured.</b> The survivors are photometered
against each other and a comp that varies against its peers is DROPPED
with its scatter printed — a slowly variable comparison star is
precisely the one that writes a fake transit into the target.</p>
<p><b>Clipping is not variability.</b> A comp whose brightest pixel
already sits at 70% of the clip level in the reference frame is one
good-seeing frame from the ceiling — and a comp that clips
<i>intermittently</i> scatters exactly like a variable star. Such a
comp is dropped up front, and <b>the next ranked star with headroom is
promoted from the selection's reserve</b> in its place, so the
ensemble stays at full strength (never below two survivors even when
the reserve runs dry). Any comp that still clips is listed with its
clip count, and the "N points measured" line names every missing
frame with its reason — nothing vanishes from the curve unnamed. On
calibrated float data a pile-up of clipped cores gets its cause named
too: Siril clamps calibrated frames to [0, 1], so the flat division
can push stars into a ceiling their raw frames never touched.</p>
<p><b>How many?</b> More comparison stars average down the ensemble's own
noise, but each one added is fainter than the last, so the gain flattens
quickly. Five is a good default. Below two there is no ensemble at all:
one comparison star puts its own variability straight into your curve.</p>
""")

        _tab("Detrending", """
<h2 style='color:#88aaff'>Why an airmass ramp survives differential photometry</h2>
<p>Dividing by comparison stars cancels <i>most</i> extinction — but not
all of it. The target and the comparisons have different colours, so they
dim at slightly different rates as the field sinks. What is left is a
smooth ramp against airmass, typically a few tens of millimagnitudes
across a night.</p>

<h2 style='color:#88aaff'>Why the obvious fix is wrong</h2>
<p>Fit a line through every point and subtract it — and you have just
absorbed part of your transit depth. The standard evening-target case is a
star that sets during egress: airmass and dimming rise <i>together</i>, so
the line splits the difference between the ramp and the transit.</p>
<p>The usual repair, a sigma clip seeded from that same all-points line,
is a no-op in exactly the case that motivates it: the seed already tilts
into the dip, so no in-transit residual ever exceeds the threshold.</p>

<h2 style='color:#88aaff'>What this does instead</h2>
<p><b>Pass one</b> — a <i>one-sided least-trimmed</i> fit. The line is
iterated on the brightest 60 % of the residuals. The dip lives on the
faint side, so it falls into the discarded 40 % as soon as the line
straightens. A final pass re-admits every point within 2 MAD-σ of that
core, so the baseline ends up using all the genuine out-of-transit data
rather than only the brightest half.</p>
<p><b>Pass two</b> — once the fit has an estimate of the transit window,
the baseline is re-fitted <i>directly on the points outside it</i>. That is
exact, where pass one is only good.</p>
<p>Measured on synthetic runs carrying a known 30 mmag/airmass ramp and a
15 mmag transit, 15 noise realisations per point — mean error in the
recovered slope:</p>
<table cellpadding='5'>
<tr><td><b>duty cycle</b></td><td><b>plain fit</b></td>
    <td><b>pass 1 alone</b></td><td><b>with pass 2</b></td></tr>
<tr><td>25 %</td><td>6.2 %</td><td>0.9 %</td><td>0.8 %</td></tr>
<tr><td>50 %</td><td>10.1 %</td><td>1.0 %</td><td>1.0 %</td></tr>
<tr><td>60 %</td><td>10.7 %</td><td>2.3 %</td><td>0.9 %</td></tr>
<tr><td>75 %</td><td>10.8 %</td><td style='color:#ddaa88'>10.6 %</td>
    <td>2.7 %</td></tr>
</table>
<p>Read two things out of that. Pass one buys an order of magnitude over a
plain fit and holds to about 50 %, where it runs out of untouched baseline
to trim to — at 75 % coverage it is <i>no better than the fit it
replaces</i>. And pass two is what carries the result from there.</p>

<h2 style='color:#88aaff'>Where it breaks — said out loud</h2>
<p>Above 50 % duty cycle the report names which pass produced the baseline,
because at that coverage the two are no longer interchangeable. If the
second pass did not run — no transit found, so no window to anchor on —
the depth at high coverage rests on few out-of-transit points, and its
bar says so.</p>
<p>The fix is not a cleverer algorithm. It is more baseline: start earlier,
finish later.</p>
""")

        _tab("The fit", """
<h2 style='color:#88aaff'>What the sigma is, and what it is not</h2>
<p>The significance is the best of about <b>40 000</b> grid nodes — 121
mid-times x 41 durations x 8 ingress fractions. Nothing in the formula
knows that, so it is <b>not</b> a Gaussian sigma: a search that large finds
a contrast on pure noise that a single a-priori test never would.</p>
<p>So the floor is calibrated rather than chosen. Over 1200 transit-free
white-noise runs (150 points, 5 h, 4 mmag per point) through this same
search:</p>
<table cellpadding='5'>
<tr><td style='color:#88aaff'><b>floor</b></td>
<td style='color:#88aaff'><b>false alarm</b></td>
<td style='color:#88aaff'><b>4 mmag</b></td><td style='color:#88aaff'>
<b>6 mmag</b></td><td style='color:#88aaff'><b>8 mmag</b></td></tr>
<tr><td>3.0 σ</td><td>7.67 %</td><td>88 %</td><td>100 %</td><td>100 %</td></tr>
<tr><td>3.5 σ</td><td>1.92 %</td><td>70 %</td><td>97 %</td><td>100 %</td></tr>
<tr><td>4.0 σ</td><td>0.50 %</td><td>45 %</td><td>93 %</td><td>100 %</td></tr>
<tr><td><b>4.5 σ</b></td><td><b>0.25 %</b></td><td>29 %</td><td>89 %</td>
<td>100 %</td></tr>
</table>
<p>4.5 halves the false alarms against 4.0 for four points of detection at
6 mmag and none at 8. What it costs is the 4-5 mmag case, a dip at about
the per-point scatter, which was never safe to claim from one night. The
measured rate is printed next to every result.</p>
<p>The table has been re-measured three times. The T0 refinement pass
roughly doubled every rate — more search finds a deeper minimum in pure
noise. A robust post-fit scatter raised them again. The limb-darkened
model fitted simultaneously with the systematics brought them back down,
because a rounded shape matches noise less well than one with a free
corner. The rate at 4.5 came out 0.25 % before and after that last change:
coincidence, not stability. <b>A calibration table is only valid for the
search, the statistic and the model it was measured on.</b></p>

<h2 style='color:#88aaff'>A limb-darkened template, not a trapezoid</h2>
<p>A trapezoid fitted to a real limb-darkened transit comes out
<b>5–6 % too shallow, systematically</b> — and χ²/ν stays at 1.0, so
nothing in the output would ever say so. The shapes searched are now
real limb-darkened geometries (radius ratios crossed with impact
parameters), built once as templates so the model stays linear in
depth: the closed-form solve, the determinism and the no-optimiser
guarantee all survive. What the fit recovers is <b>depth, mid-time and
duration</b> — exactly what ExoClock and ETD consume — with airmass,
seeing, sky and star count fitted <i>simultaneously</i> in the same
design matrix.</p>

<h2 style='color:#88aaff'>Two depth conventions, both reported</h2>
<p>The fit measures the <b>limb-darkened central depth</b> — the deepest
point of the curve. EXOTIC, HOPS and AstroImageJ quote
<b>(Rp/R★)²</b>, which on a solar-type star is ~20 % <i>shallower</i>
than the centre. Both numbers appear in the log, the report and the
AAVSO header, each labelled — compare (Rp/R★)² with theirs and with the
archive, never the central depth. On EXOTIC's own HAT-P-32 sample set
this script reads Rp/R★ = 0.1525 ± 0.0064 against EXOTIC's
0.1541 ± 0.0033 — 0.2 σ apart.</p>

<h2 style='color:#88aaff'>A grid, not an optimiser</h2>
<p>The search walks a grid over <b>T0</b>, <b>duration</b> and
<b>shape</b>. At every node the depth, the baseline and every
systematic coefficient are solved <i>analytically</i> — the model is
linear in all of them, so one small linear system gives the exact best
set.</p>
<p>Why not an optimiser? Four strongly correlated parameters is precisely
where a local search walks into a noise minimum and gives a different
answer depending on where it started. The grid gives the same answer every
run, cannot fail to converge, and its resolution is a number you can read
rather than a tolerance nobody checks.</p>
<p>Depth is constrained positive — the star gets <i>fainter</i> — so the
fit cannot "detect" a brightening and call it a transit.</p>

<h2 style='color:#88aaff'>Deciding whether it is real</h2>
<p>The significance is the in/out contrast over its own standard error:</p>
<pre style='color:#aaddaa'>(mean_in − mean_out) / σ × √(N_in·N_out / (N_in+N_out))</pre>
<p>Three deliberate choices hide in there:</p>
<ul>
<li>The scale factor is <b>not √N_total</b>. Doubling your pre-ingress
baseline does not make a shallow dip twice as certain — the uncertainty is
dominated by how many points fall <i>inside</i> the event.</li>
<li>The contrast is <b>measured, not taken from the fitted depth</b>. The
template has no free baseline term, so on transit-free data the fitter
can always absorb a small offset as a wide shallow "dip" with a nonzero
depth. The data's own in/out contrast on such a run is about zero, so
noise-only runs get rejected where a depth-based test would pass them.</li>
<li>It is applied <b>separately to each side</b>, and the weaker of the two
counts. See below — this is the one that matters most.</li>
</ul>

<h2 style='color:#88aaff'>Why the baseline is checked on both sides</h2>
<p>A real transit <b>returns to the baseline it left</b>. A trend does
not.</p>
<p>Pool the two sides into one out-of-transit mean and you lose exactly
that distinction. On a monotonic ramp — uncorrected extinction, a drifting
cloud, focus creep — the fitter puts its window over the faint half, the
pooled contrast is genuinely large, and a <i>trend gets reported as a
transit</i>. On a synthetic ramp with no transit in it at all, the pooled
test reaches <b>+25σ</b>; the two-sided test returns <b>−10σ</b> and
refuses it.</p>
<p>The price is a slightly smaller number on a real detection: each side
carries about half the baseline, and the minimum of two noisy quantities
sits below either. On the synthetic runs above, 127σ became 110σ. That is
the right direction for a test whose only job is to refuse to
overclaim.</p>
<p><b>A transit clipped by the start or the end of your run returns zero
significance</b>, not a smaller one. Without baseline on both sides the
question cannot be answered by any method, and saying so is more use than
a number that looks like a measurement.</p>
<p><b>Below the calibrated floor nothing is claimed.</b> The report still prints what the
fitter wanted, clearly marked as not a measurement, because "no detection"
and "the tool crashed" should not look the same.</p>
<p>Three sigma is the textbook floor for claiming a detection. ExoClock and
AAVSO submissions want five or more — but that is a decision for the
submission, not for the fit.</p>
<h3 style='color:#88aaff'>HOPS-compatible mode</h3>
<p>The blind fit above asks <i>is there a transit?</i> HOPS (the
ExoWorldsSpies pipeline behind ExoClock) asks a different question:
<i>given the catalogue's planet, how deep and when?</i> Pick
<b>HOPS-compatible — ephemeris-locked</b> in the Analysis group and the
run answers that question the way HOPS does, on the same photometry:</p>
<ul>
<li><b>The orbit fixes the shape.</b> Period, a/R★, inclination,
eccentricity and periastron come from the archive, so the transit's
duration and its ingress/egress are physics, not free parameters. Only
Rp/R★, the mid-time (within ±0.2 d of the predicted epoch), a
normalisation and the detrending coefficients are fitted. If the archive
has no a/R★, it is derived from the archive duration with a central
transit — the log and the report say so.</li>
<li><b>HOPS's photometry.</b> The light curve is the target divided by
the raw sum of the comparison stars, errors propagated as HOPS does — from
the same per-star fluxes at the same aperture (the per-star error formula
was HOPS's already). A frame where a comparison star is missing drops out,
counted in the log, because a raw sum is not NaN-robust and neither is
HOPS. Everything downstream stands on this series.</li>
<li><b>Claret limb darkening.</b> HOPS takes four Claret coefficients
from ExoTETHyS: Phoenix model intensities integrated over the passband,
the spherical model's outer drop-off cut away, a weighted fit,
interpolated between the star's grid neighbours. <b>Compute Claret
(Phoenix)</b> does exactly that here, for the named planet's Teff and
log g from the archive and the filter in group 6, with the transmission
curve from the SVO Filter Profile Service. The filter name may be HOPS's
spelling (R, V, r', …), a Johnson/Cousins/Sloan/SDSS/2MASS name, or what
an RGB wheel writes (RED, GREEN, BLUE — taken as Cousins R, Johnson V,
Johnson B and labelled as an approximation beside the coefficients);
narrowband filters have no table and are refused with the reason. The
first call per star
downloads about four 21 MB model files from the links ExoTETHyS
publishes into <tt>~/.svenesis</tt>; nothing is bundled. Verified
against ExoTETHyS's own output. Or enter your own; blank means the
quadratic law this script uses, rewritten exactly as Claret
coefficients.</li>
<li><b>The exposure is integrated.</b> The model is averaged over each
exposure in 10 s sub-steps, exactly HOPS's rule, with the exposure time
from the headers.</li>
<li><b>HOPS's detrending, outlier filter and error scaling.</b> A
multiplicative trend in airmass, time or time² — plus the meridian-flip
step when one was detected, so the offset between the two sensor patches
is fitted with the transit rather than read as one — points beyond 3 σ of
the normalised residuals removed iteratively, and the error bars scaled so
that χ²/ν = 1 before the posterior is sampled.</li>
<li><b>The same sampler.</b> An affine-invariant ensemble sampler (the
Goodman–Weare stretch move that emcee implements), three walkers per
parameter, the first 20 % discarded, values and asymmetric bars at the
16/50/84 percentiles. It is seeded, so a rerun repeats its numbers.</li>
</ul>
<p>The orbit matches pylightcurve's to 1e-14; the occultation integral is
analytic (pylightcurve's formulation) and reproduces pylightcurve's own
function to 1e-15 at a quarter of the ring integration's cost; and the
whole mode was run head to head against
pylightcurve's own fitting class with emcee on the same data: outlier
count and scale factor identical, every parameter within 0.1 σ.
<b>What does not change:</b> the blind
significance test still runs and still decides whether a transit is
claimed — HOPS mode measures the catalogue's planet, it does not test for
one, and the "no transit claimed" line quotes the blind test's numbers.
When a fitted contact lies outside the run, the log, results.txt
(<tt>#WARNING:</tt>) and the report say that a transit and a baseline
offset are the same curve there — the numbers do not measure this planet.
results.txt carries HOPS's parameter table (n, the detrending
coefficients, a₁..a₄, rp_over_rs, period, sma_over_rs, eccentricity,
inclination, periastron, mid_time) with its outlier count and scale
factor.</p>
""")

        _tab("Reading the chart", """
<h2 style='color:#88aaff'>The chart carries the whole result</h2>
<p>The legend quotes <b>T0 and Rp/R★ with their errors</b> and names
the detrending bases, so a screenshot is a complete measurement.
Spike-rejected points appear as <b>red crosses</b> ("N outlier(s), not
fitted") instead of silently vanishing — judge for yourself that it
was a satellite, not an egress. Per-point <b>error bars</b> have an
on/off switch, off by default: a long run turns into a picket fence.
The residual panel's corner reports its STD and the <b>lag-1
autocorrelation</b> with a verdict (white-noise-like / mild structure /
structure left) — the red-noise tell that separates clean noise from a
leftover systematic.</p>

<h2 style='color:#88aaff'>The expected transit from the archive</h2>
<p>Beside the fitted model, the <b>expected transit</b> from the
archive ephemeris is drawn in cyan — <i>whether or not the fit claimed
anything</i>. Three cases, all in the legend:</p>
<ul>
<li><b>Detection</b> — the shift between the two curves IS the O−C,
quoted in minutes with its error.</li>
<li><b>No detection, transit due</b> — "(no transit claimed by the
fit)": both facts in one picture.</li>
<li><b>Its depth</b> — the archive's Rp/R★ where it has one; for a
TESS candidate, whose listed depth is SPOC's limb-darkened model depth,
that depth is inverted through the same limb-darkened model that draws
the curve. A square root would overstate Rp/R★ by ~9 % and the drawn
dip by ~18 %.</li>
<li><b>No detection, no transit due</b> — the nearest mid-transit is
named in hours from your run, so you know whether the night missed the
transit or the transit missed the night.</li>
</ul>
<p>Its epoch comes from the window's centre, never from the fitted T0,
so a fit that wandered off cannot drag the prediction with it. Drawn
only on BJD_TDB times — against JD_UTC the offset would be the
8-minute time-system error wearing an O−C costume.</p>

<h2 style='color:#88aaff'>Your planning tool's language</h2>
<p>A night is planned in wall-clock time ("start 21:50 … flip 00:55")
and measured in Julian Dates. The bridge: a <b>clock axis</b> across
the top in HH:MM — <i>local</i> time when the frames carry N.I.N.A.'s
<tt>DATE-LOC</tt> (the DATE-OBS/DATE-LOC pair yields the site's UTC
offset, daylight saving included), UTC otherwise, and the axis says
which. The predicted <b>start/mid/end contacts</b> are stamped along
the bottom in the same clock time, and the <b>meridian flip</b> is
drawn as a dashed marker in both panels at the moment the field
turned — check by eye whether a step or an "ingress" coincides with
it. Clock labels take the BJD_TDB correction off again first; a clock
reading in barycentric time would be minutes wrong.</p>
<p>One grammar throughout: <b>orange dashed is the flip, cyan dotted
are the predicted contacts, and coloured dashed lines — mid-transit,
first and last contact — exist only
for a claimed detection</b>. An unclaimed fit keeps its honestly
labelled curve but wears no detection markers — a 0.0σ fit that
latches onto the flip step must not stand a second dashed line beside
the real one.</p>
<p>On a detection the comparison is spelled out <b>contact by
contact</b>: the measured start/end get their own clock stamps on a
row above the cyan predicted ones, the expected dip carries its own
duration arrow with Δduration in its label, and grey Δ spans connect
each predicted contact to its measured counterpart ("Δstart
−16.4 min") — measured minus predicted throughout, the O−C sign
convention. A shifted ephemeris shows two equal Δs; a wrong duration
shows Δs of opposite sign.</p>
""")

        _tab("Getting good data", """
<h2 style='color:#88aaff'>What actually limits a transit run</h2>
<table cellpadding='6'>
<tr><td style='color:#88aaff'><b>Baseline</b></td>
<td>Start at least one transit duration <i>before</i> ingress and run the
same after egress. Everything on this page depends on having
out-of-transit data; without it the depth is a guess and the detrend
cannot work at all.</td></tr>
<tr><td style='color:#88aaff'><b>Do not saturate</b></td>
<td>Not the target, not the comparison stars. A clipped core is not
photometry. Keep the peak below about half of full well — check a sub
before committing the night.</td></tr>
<tr><td style='color:#88aaff'><b>Defocus slightly</b></td>
<td>Counter-intuitive but standard: spreading the star over more pixels
averages over flat-field errors and pixel-to-pixel response, and buys
headroom against saturation. A FWHM of 4–6 px is a good target.</td></tr>
<tr><td style='color:#88aaff'><b>Do not dither</b></td>
<td>The opposite of the stacking advice. Dithering moves the star onto
different pixels with different responses, which is noise you do not need
when the star never moves anyway.</td></tr>
<tr><td style='color:#88aaff'><b>Calibrate</b></td>
<td>Flats above all: a star drifting across a dust shadow is a slow trend
that looks exactly like a shallow transit, and after a meridian flip the
target lands on a different patch of sensor — that is a step, not a wobble.
Point <b>2 · Calibration</b> at your masters, or calibrate the frames
before pointing this script at them; either way, do it.</td></tr>
<tr><td style='color:#88aaff'><b>Same exposure throughout</b></td>
<td>Changing exposure mid-run changes the saturation margin and the
scintillation statistics at the same time.</td></tr>
</table>

<h2 style='color:#88aaff'>Reading the result</h2>
<p><b>RMS</b> is robust (MAD-based), so a single satellite streak does not
inflate it. Compare it to the depth you are hunting: a 15 mmag transit at
5 mmag scatter is comfortable, at 15 mmag it needs the whole night to
stack up.</p>
<p><b>Residual panel</b> — structure left in there after the fit is the
honest measure of what the model missed. Flat noise is what you want.</p>
<p><b>Binning</b> is presentation only. The fit always sees every point;
binning first would throw away the very scatter the significance test
needs in order to be honest about itself.</p>
""")

        lay.addWidget(tabs)

        # These tabs are the quick reference; the manual on GitHub goes
        # deeper — the measurements behind every design decision, per
        # section, in two languages.  QTextEdit does not open links, so
        # the pointer lives in a QLabel that does.
        docs = QLabel(
            "<div style='text-align:center;'>"
            "<span style='color:#888;'>Full manual: </span>"
            f"<a style='color:#88aaff;' href='{DOCS_URL_EN}'>English</a>"
            "<span style='color:#888;'> · </span>"
            f"<a style='color:#88aaff;' href='{DOCS_URL_DE}'>Deutsch</a>"
            "</div>")
        docs.setTextFormat(Qt.TextFormat.RichText)
        docs.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        docs.setOpenExternalLinks(True)
        lay.addWidget(docs)

        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

    def closeEvent(self, event) -> None:                    # noqa: N802
        w = self._worker
        if w is not None and w.isRunning():
            answer = QMessageBox.question(
                self, "Svenesis LightCurve",
                "A measurement is still running. Close anyway?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            w.requestInterruption()
            w.wait(3000)
        self._save_settings()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        try:
            siril.connect()
        except Exception:
            pass
        win = SvenesisLightCurveWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis LightCurve v{VERSION} loaded.", LogColor.GREEN)
        except Exception:
            pass
        return app.exec()
    except SirilConnectionError as exc:
        QMessageBox.critical(
            None, "Svenesis LightCurve",
            f"Could not connect to Siril: {exc}\n\n"
            "Start this script from Siril's Scripts menu.")
        return 1
    except Exception as exc:                                # noqa: BLE001
        QMessageBox.critical(
            None, "Svenesis LightCurve Error",
            f"{exc}\n\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
