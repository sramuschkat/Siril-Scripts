"""
Svenesis LightCurve
Script Version: 1.0.0
=====================================

Author: Svenesis-Siril-Scripts project.
Contact and support: See repository README and Siril forum / scripts repository.

This script turns a folder of sub-exposures of an exoplanet host star into a
differential light curve, and then tells you whether there is a transit in it.

The division of labour is deliberate:

  * SIRIL does the pixel work.  `light_curve` is Siril's own aperture
    photometry -- the same code the Photometry tool uses -- and it already
    handles the annulus sky estimate, the FWHM-scaled ring radii, saturation
    rejection and the per-frame star matching.  Re-implementing that here
    would produce a second, worse photometry engine that has to be kept in
    step with the first.  So the script drives `light_curve` and reads its
    `light_curve.dat`.
  * THIS SCRIPT does the analysis Siril does not do: airmass detrending,
    the transit fit, and -- most importantly -- the honest question of
    whether the dip is real.

Features:
- Folder of subs in, light curve out: link -> calibrate -> register ->
  light_curve -> fit
- Point at any folder above the subs: the scan is recursive, sorts lights
  from calibration frames by header, and drops duplicate exposures
- Calibration finds its own frames: inside your selection, beside the
  lights in the N.I.N.A. LIGHT/FLAT layout, and in a library folder you set
  once.  Masters are stacked and cached automatically; a dark that does not
  match the lights is reported and skipped rather than applied
- Comparison-star ensemble chosen from Siril's own star detection, filtered
  by SNR, saturation, distance from the target, and isolation -- a neighbour
  inside the sky annulus is a seeing-driven trend, not a comparison star
- Target by pixel position, by RA/Dec (plate-solved sequences), or automatic
  (brightest star in the field)
- Mid-exposure times from DATE-OBS + EXPTIME/2, optionally converted to
  BJD_TDB via astropy, from the site position and the target direction
      - Red-noise (beta) correction on every reported significance
- Airmass detrending anchored on the out-of-transit baseline, with a
  one-sided least-trimmed fit so a setting target's ramp is not mistaken
  for -- or absorbed into -- the transit depth
- Trapezoid transit fit: grid over (T0, duration, ingress fraction) with
  depth and baseline solved analytically at each node.  No optimiser to get
  stuck, no random seed, the same answer every run
- Stacked detection significance with the correct standard error, checked
  against the baseline on BOTH sides of the event so a monotonic trend
  cannot be reported as a transit, and a refusal to claim anything below a
  CALIBRATED floor: the grid search spans ~40 000 nodes, so the number is
  not a Gaussian sigma.  Measured over 1200 transit-free noise runs, 4.0
  gives 0.17% false alarms -- what "3 sigma" was always read to mean -- and
  the measured rate is printed next to every result
- Binned overlay, residual panel, per-point scatter and the measured RMS
- CSV export of the full series, PNG export of the plot, plain-text report
- Every number that is an estimate is marked as one

Run from Siril via Processing -> Scripts.  Place Svenesis-LightCurve.py inside a
folder named Utility in one of Siril's Script Storage Directories
(Preferences -> Scripts).

(c) 2026
SPDX-License-Identifier: GPL-3.0-or-later


CHANGELOG:
1.0.0 - Initial release
      - Differential photometry of a sub-exposure folder via Siril's own
        `light_curve` command, with comparison stars picked from Siril's
        star detection and filtered on SNR, saturation, separation and
        isolation.  A comp is dropped when another star sits inside its own
        sky annulus (2 x the 6.3 x FWHM outer ring `-autoring` sets): that
        star's light is in the aperture and in the sky estimate at once, and
        its share breathes with the seeing, which is a slow trend through
        the night.  The target cannot be dropped, so the same geometry is
        reported for it instead.  The not-used tally now accounts for every
        detection, including the ones that passed every filter and were
        merely surplus.
      - Calibration, driven through Siril's `calibrate` rather than
        reimplemented -- the same division of labour as `light_curve`.  The
        user-facing shape is Svenesis ImageMono-Train's, because asking for
        three ready-made masters was the wrong question: it demanded work
        the script is better placed to do.  Point at the lights and, once,
        at wherever your reusable darks live; flats belong to the session
        and are found beside the lights by walking up to the N.I.N.A.
        LIGHT/FLAT layout.  Frames are grouped by signature (exposure,
        gain, temperature, binning, size, camera), masters are stacked and
        cached under header-derived names and reused on later runs, and a
        group of exactly one file is adopted as a ready-made master
      - What the matching refuses is said out loud, because a master that
        was found and rejected leaves a run that looks identical to one
        where no master existed.  Darks are split by temperature (a -10 C
        and a -20 C average is correct for neither) and bias is not (it is
        temperature-independent).  A dark at the wrong exposure is named
        with what the mismatch would have done, not just that two numbers
        differ.  Bias is never applied together with a dark -- the dark
        already carries the offset -- but it still corrects the flats:
        Lc = (L - D) / (F - O)
      - Discovery is recursive and classifies rather than assumes.  Only
        the files directly inside the chosen folder were read before, which
        meant navigating to the exact leaf folder AND left calibration
        frames filed anywhere inside your own selection invisible -- the
        thing Svenesis ImageMono-Train had right and this did not.  Every
        FITS under the folder is now inspected once and sorted by kind;
        lights become the sequence, calibration frames join the groups
      - Three guards came with the recursion, because a recursive scan
        picks up what a flat one could not reach:
        * this script's own working and output folders are pruned,
          including the names it used before it was renamed -- a run that
          walks its own previous output re-ingests staged symlinks and
          converted frames as subs
        * a repeated DATE-OBS is a copy, not an exposure, and is dropped
          with a count.  Found the hard way: a leftover working folder
          turned 178 subs into 534, and every duplicate would have entered
          the curve as an independent point, shrinking every error bar by
          root-3 for nothing
        * lights are reduced to one filter and one exposure.  A filter or
          exposure change mid-run is two series, not a longer one; the
          largest set wins and the rest is named
      - Audit of the arithmetic, every finding measured rather than read:
        * the detection floor was a Gaussian-looking 3 sigma on a number
          that is the best of ~40 000 grid nodes.  Measured over 1200
          transit-free white-noise runs through that same search: 4.42%
          false alarms, 33x the 0.13% the label implies.  The floor is now
          4.0, where the measured rate is 0.17%, and the rate itself is
          printed next to every result.  Detection above 6 mmag is
          unchanged at 98-100%; the 4-5 mmag case is what it costs, and a
          dip at the per-point scatter was never safe from one night
        * the red-noise beta used `np.std` for the unbinned scatter -- the
          one non-robust scatter in the file.  Three 50 mmag outliers on a
          4 mmag curve inflate it 2.1x, which DIVIDES beta by 2.1 and
          switches the correction off exactly when the data need it.  Now
          `_mad_std`, while the binned scatter stays a plain std on
          purpose: an outlier then raises beta instead of lowering it
        * the expected bin-mean scatter used sigma/sqrt(mean(k)) where the
          variance of bin i is sigma^2/k_i, so the right form is
          sigma*sqrt(mean(1/k)).  Identical on equal bins -- which is why
          it hid -- and 55% out on [2,4,8,16,32], 86% on [2,2,2,30]
        * the depth uncertainty was NOT scaled by beta while the
          significance next to it in the report was.  At beta 2.56 one fit
          read "1.6 sigma" and "depth/error 9.5" three lines apart.  Both
          carry the same noise model now, and the report says which of the
          two to quote and why they still differ
        * binned error bars used numpy's default ddof=0: 29% too small at
          two points per bin, 11% at five
        * `fit_transit` carried a `weights` argument no caller passed, and
          the path was inconsistent -- chi-square weighted, sigma and the
          depth error not.  Removed rather than fixed: Siril's formal error
          describes photon and sky noise, not the scintillation and
          transparency that actually limit the curve
        * `_mid_exposure_jd` was defined and never called.  Removed, and
          the reason recorded where the times are read: Siril already
          writes mid-exposure.  Checked against 178 raw headers of a 60 s
          run -- 0.02 s from DATE-OBS + EXPTIME/2, 30.00 s from DATE-OBS.
          Calling the helper would have put every mid-transit time 30 s late
        * the altitude docstring claimed "a few arcminutes" and "the fourth
          decimal" of airmass.  Measured against astropy: 21 arcminutes and
          0.044.  The approximation is still right for a detrending basis
          and the docstring now says so with the numbers
      - Target saturation is measured in the PIXELS, not read from Siril's
        `has_saturated`.  The flag is right on raw 16-bit frames and stops
        firing once calibration turns them into 32-bit float: same
        saturation, no warning, and a run reporting a 4% yield with no
        cause attached.  Measured on the real pair -- raw peak 65532 of
        65535 inside the box, calibrated peak 1.000 of 1.0, flag set only
        in the first case.  The threshold is 98% of full scale because this
        camera clips at 65532, not 65535; the flag is still consulted, so a
        frame that cannot be read is not silently called clean
      - Whether the frames were already calibrated is a three-state answer,
        since N.I.N.A. writes neither CALSTAT nor a HISTORY card and "no
        evidence" is not "not calibrated"
      - `_log_swallowed` was called from three exception handlers and
        defined nowhere.  All three are fallbacks for cases that had not
        come up; the first one to fire would have raised NameError over the
        top of the error it existed to absorb.  Defined, and the suite now
        checks statically that every name in every method resolves
      - NOT taken, and recorded so it is not re-derived: Siril's
        "Photometry for star at X, Y in image 0" disagreed with the
        `-refat=` that produced it by 16, 33 and 63 px on three comps.  A
        rule dropping comps with a brighter neighbour was written for that
        and then removed -- Siril's own "No star found in the area ...
        around X,Y" lines put the search box at `requested - 19` in both
        axes, and two of those three positions fall outside their own 38 px
        box, so a search-box snap cannot be the cause.  The rule cost 28% of
        a real field and changed none of the three
      - Airmass detrend, trapezoid transit fit, stacked significance gate
      - CSV / PNG / report export, light-curve and residual plots
      - Meridian-flip detection.  The first real run -- 178 subs of
        WASP-75b -- flipped after frame 21, putting 157 frames at 179.88
        degrees to the rest.  Siril follows the stars through the
        registration either way, so the photometry stays correct, but the
        target then sits on a DIFFERENT patch of sensor: different
        flat-field response, different hot pixels, a different corner of
        the vignette.  The light curve carries a step at that moment, and
        a step mid-run is the shape of an ingress.  The run now measures
        the field rotation and says so
      - Aborts reach Siril's log.  On that same run the log ended
        mid-sentence after the star detection with no error in it
        anywhere: `failed` only reached the script window, and the reason
        the run stopped was sitting in a dialog behind it
      - Significance is corrected for CORRELATED noise before it is
        reported.  Every sigma in this file scaled as sqrt(N), which is
        only valid for independent points, and ground-based photometry
        rarely delivers them: seeing, transparency and flat-field error
        as the star drifts all vary on minutes-to-hours -- the timescale
        a transit lives on.  The excess is measured from the fit
        residuals with the Pont/Zucker/Queloz beta factor (bin on a
        ladder of timescales tied to the fitted duration; for white noise
        the bin means fall as sigma/sqrt(n), so the observed-to-expected
        ratio is 1) and the significance is divided by it.  On synthetic
        data: pure correlated noise with NO transit produced 5.4 sigma
        before the correction -- a detection that would have been
        reported -- and 2.7 sigma after, correctly refused.  Clean data
        pay nothing: over 60 realisations with a genuine transit, not one
        was pushed below the floor.  The idea came from HOPS, which flags
        residual autocorrelation; beta is the quantitative form of the
        same question
      - Siril's ``light_curve.dat`` is parsed correctly at last, and it
        had TWO traps.  The header line ``#JD_UT (+ 2461267)`` is a plot
        LABEL, not a subtraction -- the column underneath already holds
        the full Julian Date -- so adding the declared offset doubled it
        and put the WASP-75b run at JD 4922534, the year 8600.  astropy
        had been saying so all along, in a warning that read "date
        outside the range 1900-2100 AD" and was easy to mistake for a
        leap-second complaint.  The offset is now applied only when the
        column is not already absolute.  Second, ``nan`` parses as a
        perfectly good float: Siril writes a row per frame it attempted
        and sets V-C to nan where the photometry failed, so 4 real
        measurements were being reported as "35 photometric points".
        Unmeasured rows are dropped and counted separately
      - The observatory position is read from the FITS header
        (SITELAT/SITELONG/SITEELEV) instead of being demanded from the
        user.  The first run that reached the time conversion refused it
        for want of a latitude that was sitting in all 178 subs, under
        SITENAME "Starfront Building 8".  Two things need that position --
        the airmass detrend and the BJD_TDB conversion -- and both had
        been quietly switching themselves off.  A value typed into the
        form still wins, since that is the only way to correct a wrong
        header, and the resolved position is echoed to the log with the
        east-positive convention spelled out
      - Times are converted to BJD_TDB before anything is fitted.  The
        header had promised this from the first draft and nothing
        implemented it -- a claim in the documentation with no code behind
        it, which is worse than the missing feature.  It matters because
        every published ephemeris (ExoClock, ETD, the NASA archive) quotes
        T0 in BJD_TDB, and two corrections separate that from the camera
        clock: barycentric light travel, up to 8.3 minutes, and TDB-UTC,
        about 69 s.  On the WASP-75b run the total is +550 s -- nine and a
        half minutes, against a timing precision one would want inside a
        minute.  The correction drifts only 0.26 s across the night, so
        the transit SHAPE is untouched and only the absolute T0 moves.
        The airmass detrend deliberately stays on JD_UTC: that is a
        question about where the Earth is pointing, not about the
        barycentre.  When the conversion cannot be done the run says so
        and marks T0 as not comparable, instead of quietly reporting a
        number in the wrong system
      - A target picked as "nearest detection" is judged by its RUNNER-UP,
        not by its distance.  The absolute separation says as much about
        how precisely the coordinates were typed as about the match; what
        makes a match wrong is a second star at a comparable distance.
        The real run matched 9.4" off with nothing else nearby -- fine,
        and now stated as fine rather than left for the reader to weigh
      - The TARGET is checked for saturation, not only the comparison
        stars.  On the first real run Siril dropped 143 of 178 frames with
        "pixel out of range" -- which is PSF_ERR_INVALID_PIX_VALUE, a
        saturated pixel inside the aperture, not a positioning failure.
        The run now says so before spending the photometry pass, and the
        yield verdict names the cause: a saturated core carries no flux
        information, and the frames that survive are the ones where seeing
        spread the star out, which is a seeing-selected subset rather than
        a fair sample of the night
      - The frame yield is judged, not just counted.  "35 photometric
        points" reads like a result; "Siril kept 35 of 178 frames (20%)"
        reads like the warning it is
      - ``light_curve`` gets INTEGER coordinates.  Siril parses
        ``-at=``/``-refat=`` with an integer reader that stops at the
        first character which is neither digit nor comma, so
        ``-at=1503.646,1505.257`` was rejected on the decimal point --
        after ``-autoring`` had already been read, which is why the log
        showed the ring radii being set and then a bare "invalid
        arguments" pointing at the wrong end of the command
      - Comparison selection no longer hangs on a field Siril may not
        have filled.  ``PSFStar.SNR`` is populated during PHOTOMETRY, not
        during ``findstar``, so a plain detection pass leaves it at zero
        for every star -- read as "every star is noise", that rejected all
        865 of them and killed the run.  When no star in the frame carries
        an SNR the ranking falls back to instrumental magnitude, within
        two magnitudes of the target in BOTH directions, and says which
        measure it used
      - Rejections are reported as a tally by reason, in the failure path
        too.  "865 were rejected" is indistinguishable from an empty
        field; "865 x SNR N below N" is the diagnosis
      - RA/Dec target selection now plate-solves the frames itself when
        they carry no astrometric solution, using the target's own
        coordinates as the centre hint, instead of sending the user away
        to do it by hand.  Only when that solve fails does it say so --
        and it says which of the possibilities actually applies, checked
        against the stars, rather than listing all three
      - Stars are detected on the frame Siril chose as its REGISTRATION
        reference, not on frame 1.  ``light_curve`` reads its ``-at=``
        coordinates in the reference frame, so the two have to be the
        same frame.  On the first real run ``register -2pass`` picked
        image 5 of 178; frames 1 and 5 agreed to 0.6 px there, which is
        why nothing broke, but a reference on the far side of a meridian
        flip would have been off by three thousand pixels
      - The significance test is two-sided.  The first version of it
        pooled the out-of-transit points, and the test suite caught what
        that costs: on a monotonic ramp with no transit in it the fitter
        puts its window over the faint half and the pooled contrast
        reaches +25 sigma.  Comparing each side separately and taking the
        weaker returns -10 sigma on the same data.  Uncorrected
        extinction, a drifting cloud and focus creep all produce that
        ramp, so this was not a corner case
      - The airmass breakdown figure is measured rather than asserted: the
        blind first pass holds to 50 percent duty cycle and is no better
        than a plain fit at 75 percent, where the out-of-transit anchor
        still lands within 3 percent.  The table is at the constant
"""
from __future__ import annotations

import os
import re
import sys
import csv
import math
import shutil
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

import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QFileDialog, QMessageBox, QTabWidget, QTextEdit,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtCore import QUrl

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from sirilpy import LogColor

VERSION = "1.0.0"

SETTINGS_ORG = "Svenesis"
SETTINGS_APP = "LightCurve"

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
# Two stars whose outer annuli touch share sky.  A neighbour inside this
# multiple of the outer radius contaminates the aperture AND the sky
# estimate, and the contamination breathes with the seeing -- which reads
# as a slow trend, the same shape a transit has.
COMP_ISOLATION_OUTER = 2.0
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
#           3.0         4.42% |  91%    94%   100%   100%    100%
#           3.5         0.83% |  79%    89%    98%   100%    100%
#           4.0         0.17% |  53%    81%    98%   100%    100%
#           4.5         0.08% |  33%    70%    96%   100%    100%
#           5.0         0.00% |  19%    53%    86%    99%    100%
#
# 4.0 is where the false-alarm rate reaches the 0.13% that "3 sigma" was
# always taken to mean, and it costs nothing above 6 mmag.  What it costs
# is the 4-5 mmag case -- a dip at or just above the per-point scatter --
# and those were never safe to claim from a single night anyway.
MIN_DETECTION_SIGMA = 4.0
# The false-alarm rate measured AT that threshold, reported next to every
# claim.  A threshold without its own calibration is a number the reader
# has to trust; with it, they can weigh it.
MEASURED_FALSE_ALARM = 0.0017
MEASURED_FALSE_ALARM_RUNS = 1200
# Grid resolution of the trapezoid fit.  The parameters are strongly
# correlated, so a dense grid beats a local optimiser that can walk into a
# noise minimum -- and it is deterministic.
FIT_T0_STEPS = 121
FIT_DURATION_STEPS = 41
FIT_INGRESS_FRACTIONS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
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
    return float(jdn) - 0.5 + day_frac


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
    parts = [p for p in re.split(r"[\s:hdm\'\"]+", txt) if p not in ("", "s")]
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


# ---------------------------------------------------------------------------
# Transit fit
# ---------------------------------------------------------------------------
def trapezoid_shape(t, t0: float, duration: float, ingress_frac: float):
    """Normalised trapezoid: 0 outside the event, 1 at the flat bottom.

    A trapezoid rather than a limb-darkened Mandel-Agol curve because the
    two are indistinguishable at amateur precision -- a 10 mmag dip measured
    at 3 mmag per point does not constrain a limb-darkening coefficient --
    and because the trapezoid has no external dependency, no optimiser and
    no failure mode.  What it recovers is depth, mid-time and duration,
    which is exactly what ExoClock and ETD consume.

    ``ingress_frac`` is the share of the total duration spent in ingress
    (and, symmetrically, in egress).  At 0.5 the trapezoid degenerates to a
    triangle -- the correct shape for a grazing transit.
    """
    t = np.asarray(t, dtype=float)
    half = 0.5 * duration
    ing = max(1e-9, ingress_frac * duration)
    dt = np.abs(t - t0)
    shape = np.zeros_like(t)
    flat = dt <= max(0.0, half - ing)
    shape[flat] = 1.0
    ramp = (~flat) & (dt < half)
    if np.any(ramp):
        shape[ramp] = (half - dt[ramp]) / ing
    return np.clip(shape, 0.0, 1.0)


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
    trapezoid has no free baseline term, so on transit-free data the fitter
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


def fit_transit(t, mag):
    """Fit a trapezoid to a differential light curve in MAGNITUDES.

    Returns a dict, or ``None`` when there is not enough data to try.

    The search is a grid over ``(T0, duration, ingress fraction)`` with the
    depth and the baseline solved ANALYTICALLY at every node: for a fixed
    shape the model is ``baseline + depth * shape(t)``, which is linear in
    both free parameters and therefore has a closed-form least-squares
    solution.  Three nested loops and one 2x2 solve replace an optimiser.

    That is a deliberate trade.  A local optimiser on four strongly
    correlated parameters walks into noise minima and gives a different
    answer depending on where it started; this grid gives the same answer
    every run, cannot fail to converge, and its resolution is a stated
    number rather than a tolerance nobody reads.

    Depth is constrained to be POSITIVE -- the star gets fainter -- so the
    fit cannot "detect" a brightening and call it a transit.

    UNWEIGHTED, deliberately.  This carried a `weights` argument that no
    caller ever passed, and the path was inconsistent: chi-square would
    have been weighted while `sigma` and `depth_sigma` stayed unweighted,
    so switching it on would have produced quietly wrong error bars.  Siril
    writes a per-point error into `light_curve.dat` and this script keeps
    it in the CSV, but does not fit against it -- a formal error from
    aperture photometry describes photon and sky noise only, and the
    scatter that actually limits a ground-based light curve is scintillation
    and transparency, which it does not see.  The post-fit residual scatter
    is measured instead, and that one does include everything.
    """
    t = np.asarray(t, dtype=float)
    mag = np.asarray(mag, dtype=float)
    good = np.isfinite(t) & np.isfinite(mag)
    if good.sum() < 10:
        return None
    t = t[good]
    mag = mag[good]

    span = float(t.max() - t.min())
    if span <= 0:
        return None

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

    ones = np.ones_like(t)
    sw = ones
    best = None
    for dur in dur_grid:
        for ing in FIT_INGRESS_FRACTIONS:
            for t0 in t0_grid:
                shape = trapezoid_shape(t, t0, dur, ing)
                n_in = float(np.count_nonzero(shape > 0.5))
                if n_in < 3:
                    continue
                # Weighted normal equations for  mag ~ base * 1 + depth * shape
                s11 = float(np.sum(sw * ones * ones))
                s12 = float(np.sum(sw * ones * shape))
                s22 = float(np.sum(sw * shape * shape))
                b1 = float(np.sum(sw * ones * mag))
                b2 = float(np.sum(sw * shape * mag))
                det = s11 * s22 - s12 * s12
                if abs(det) < 1e-30:
                    continue
                base = (b1 * s22 - b2 * s12) / det
                depth = (s11 * b2 - s12 * b1) / det
                if depth <= 0:
                    # Brightening, not a transit.  Skip rather than clamp:
                    # a clamped zero-depth node would win the chi-square
                    # race on noise and mask a real shallow dip elsewhere.
                    continue
                resid = mag - (base + depth * shape)
                chi2 = float(np.sum(sw * resid * resid))
                if best is None or chi2 < best["chi2"]:
                    best = {"chi2": chi2, "t0": float(t0), "duration": float(dur),
                            "ingress_frac": float(ing), "depth": float(depth),
                            "baseline": float(base)}
    if best is None:
        return None

    shape = trapezoid_shape(t, best["t0"], best["duration"], best["ingress_frac"])
    model = best["baseline"] + best["depth"] * shape
    resid = mag - model
    n_free = 4                      # t0, duration, ingress, depth (+baseline)
    dof = max(1, t.size - n_free - 1)
    sigma = float(np.sqrt(np.sum(resid * resid) / dof))
    rms_resid = _mad_std(resid)

    sig = stacked_significance(t, mag, best["t0"], best["duration"], sigma)

    # Correct that significance for correlated noise before anyone reads
    # it.  sig assumes independent points; ground-based photometry rarely
    # delivers them, and the excess is measured directly from the fit
    # residuals rather than assumed.
    resid = mag - (best["baseline"] + best["depth"] * shape)
    beta, beta_rows = red_noise_beta(t, resid, best["duration"])
    sig_white = sig
    sig = sig / beta

    # Depth uncertainty from the curvature of the chi-square surface in the
    # one direction that has a closed form.  The other three are correlated
    # with it and with each other; quoting a covariance matrix from a grid
    # search would be a number with no error bar of its own.
    #
    # SCALED BY THE SAME beta as the significance.  It was not, and the two
    # numbers sit three lines apart in the report: at beta 2.56 the
    # significance read 1.6 sigma while depth/depth_sigma read 9.5, so the
    # report said "not detected" and "detected at 9 sigma" about one fit.
    # Measured ratios across a dozen correlated-noise runs: 2.3x to 6.0x.
    inside = shape > 0.5
    n_in = int(np.count_nonzero(inside))
    n_out = int(np.count_nonzero(~inside))
    if n_in > 0 and n_out > 0 and sigma > 0:
        depth_sigma = beta * sigma * math.sqrt(1.0 / n_in + 1.0 / n_out)
    else:
        depth_sigma = float("nan")

    return {
        "t0": best["t0"],
        "duration_d": best["duration"],
        "duration_h": best["duration"] * 24.0,
        "ingress_frac": best["ingress_frac"],
        "depth_mag": best["depth"],
        "depth_mmag": best["depth"] * 1000.0,
        "depth_pct": (1.0 - 10.0 ** (-0.4 * best["depth"])) * 100.0,
        "depth_sigma_mmag": depth_sigma * 1000.0,
        "baseline": best["baseline"],
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
    if lat_deg is None or lon_deg is None:
        return None, "no site latitude/longitude"
    try:
        from astropy import units as u
        from astropy.coordinates import EarthLocation, SkyCoord
        from astropy.time import Time
    except Exception as exc:                          # pragma: no cover
        return None, f"astropy unavailable ({exc})"
    try:
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
                 "(barycentric light travel + TDB-UTC)")


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
    the number readable.  Measured over 60 noise realisations of 240
    points with a genuine transit present: median beta 1.00, 90th
    percentile 1.16, worst draw 1.53, and 8% of runs above 1.2.  A single
    beta near 1.4 on visibly clean data is therefore a fluctuation, not a
    verdict.  What matters is that across those same 60 runs NOT ONE real
    transit was pushed below the 3-sigma floor by this correction, while
    a false positive on pure noise was.  The correction costs detections
    nothing and removes claims that should not have been made.

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
        idx = np.floor((tt - tt.min()) / width).astype(int)
        means, counts = [], []
        for b in np.unique(idx):
            sel = idx == b
            k = int(sel.sum())
            if k >= 2:                     # a one-point "bin" is not a mean
                means.append(float(r[sel].mean()))
                counts.append(k)
        n_bins = len(means)
        if n_bins < RED_NOISE_MIN_BINS:
            continue
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
        # sqrt(M/(M-1)) is the small-sample correction for estimating the
        # scatter of M bin means; without it every short ladder rung reads
        # low and beta is biased toward "the noise is fine".
        expected = sigma1 * math.sqrt(float(np.mean(1.0 / np.asarray(
            counts, dtype=float)))) * math.sqrt(n_bins / float(n_bins - 1))
        if expected > 0:
            rows.append((width, observed / expected, n_bins, n_mean))
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


def photometry_yield_note(n_points: int, n_frames: int,
                          target_saturated: bool):
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
    lines = [f"Siril kept {n_points} of {n_frames} frames "
             f"({100.0 * frac:.0f}%)."]
    if target_saturated:
        lines.append(
            "The target is SATURATED in the reference frame. Siril drops a "
            "frame whose aperture holds a saturated pixel (\"pixel out of "
            "range\"), and a saturated core carries no flux information "
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
            "detection statistics below are optimistic. Check Siril's own "
            "reasons above — \"pixel out of range\" means saturation, "
            "\"not in area\" means the star left the search box.")
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
        args.append("-autoring")
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
           "filter": "", "date_obs": ""}
    h = header if header is not None else _read_header(path)
    if h is None:
        out["kind"] = classify_path(path)
        return out
    out["kind"] = (classify_kind(str(h.get("IMAGETYP", "") or ""))
                   or classify_path(path))
    out["filter"] = str(h.get("FILTER", "") or "").strip()
    out["date_obs"] = str(h.get("DATE-OBS", h.get("DATE_OBS", "")) or "").strip()
    out["instrument"] = str(h.get("INSTRUME", "") or "").strip() or None
    for key in ("EXPTIME", "EXPOSURE"):
        if key in h:
            try:
                out["exp_s"] = float(h[key])
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


def choose_comparison_stars(stars, target_xy, n_wanted: int,
                            fwhm_px: float, min_snr: float = MIN_COMP_SNR):
    """Pick the comparison ensemble from Siril's detected stars.

    ``stars`` is what ``get_image_stars()`` returns.  Returns
    ``(chosen, rejected, note)`` where ``chosen`` is a list of
    ``(x, y, score)`` ordered brightest-first, ``rejected`` is a list of
    ``(x, y, reason)``, and ``note`` says which brightness measure was
    used.  The reasons are not decoration: on the first real run every one
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
    r_iso = COMP_ISOLATION_OUTER * outer

    scored = []
    rejected = []
    for idx, st in enumerate(pool):
        x = float(getattr(st, "xpos", 0.0) or 0.0)
        y = float(getattr(st, "ypos", 0.0) or 0.0)
        if abs(x - tx) < 1e-6 and abs(y - ty) < 1e-6:
            continue                                # the target itself
        sep = math.hypot(x - tx, y - ty)
        if bool(getattr(st, "has_saturated", False)):
            rejected.append((x, y, "saturated"))
            continue
        if sep < min_sep:
            rejected.append((x, y, f"only {sep:.0f} px from the target"))
            continue
        if px.size > 1:
            d = np.hypot(px - x, py - y)
            d[idx] = np.inf                         # not its own neighbour
            nearest = float(d.min())
            if nearest < r_iso:
                rejected.append(
                    (x, y, f"neighbour {nearest:.0f} px away, inside its own "
                           f"{outer:.0f} px annulus"))
                continue
        if have_snr:
            snr = _snr(st)
            if snr < min_snr:
                rejected.append((x, y, f"SNR {snr:.0f} below {min_snr:.0f}"))
                continue
            scored.append((x, y, snr))
        else:
            dm = _mag(st) - tmag
            if dm > COMP_MAG_WINDOW:
                rejected.append((x, y, f"{dm:.1f} mag fainter than the target"))
                continue
            if dm < -COMP_MAG_WINDOW:
                rejected.append((x, y, f"{-dm:.1f} mag brighter than the target"))
                continue
            scored.append((x, y, -dm))      # brighter first, same as SNR
    scored.sort(key=lambda r: r[2], reverse=True)
    keep = max(0, int(n_wanted))
    # The stars that passed every filter and were simply not needed are
    # listed too.  Without them the tally does not add up: a run reported
    # "6 chosen, 668 rejected" out of 864 detections and said nothing about
    # the other 189, which reads as a field that barely yielded a comp when
    # in fact it yielded 195 and the best 6 were taken.
    for x, y, _sc in scored[keep:]:
        rejected.append((x, y, f"usable, but only {keep} were needed"))
    return scored[:keep], rejected, note


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
        return (LogColor.SALMON,
                f"Another star sits {near:.0f} px away, inside the "
                f"{outer:.0f} px sky annulus. Its share of the aperture "
                f"changes with the seeing, which is a slow trend through "
                f"the night — do not read a shallow dip here as a transit.")
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

    # -- plumbing ---------------------------------------------------------
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
        for i, src in enumerate(files):
            dst = os.path.join(lights, f"{i:05d}_{os.path.basename(src)}")
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
        return n

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
            with fits.open(ref_path, memmap=True) as hdul:
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
        self._emit("  No astrometric solution in these frames — plate-solving "
                   "the reference frame" + (" around the target position"
                                            if radec else "") + "…",
                   LogColor.BLUE)
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
            site = site_from_header(_read_header(path))
            if site is None:
                continue
            lat, lon, height, where = site
            self.opts["site_lat_deg"] = lat
            self.opts["site_lon_deg"] = lon
            self.opts["site_height_m"] = height
            self._emit(f"  Site read from the {where}: {lat:+.4f}, "
                       f"{lon:+.4f}, {height:.0f} m. Longitude is EAST "
                       "positive — check the sign if the airmass looks "
                       "mirrored.", LogColor.BLUE)
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
        try:
            self._cmd("load_seq", f'"{seq}_"')
            data = self.siril.get_seq()
            n = int(getattr(data, "number", 0) or 0)
            homs = []
            for i in range(n):
                reg = self.siril.get_seq_regdata(i, 0)
                homs.append(getattr(reg, "H", None) if reg else None)
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

    def _run_light_curve(self, seq: str, target_xy, comps) -> None:
        """Hand the positions to Siril's own aperture photometry."""
        args = light_curve_args(seq, self.opts.get("channel", 0),
                                bool(self.opts.get("autoring", True)),
                                target_xy, comps)
        self._emit("  " + " ".join(args), LogColor.BLUE)
        self._cmd(*args)

    # -- analysis ---------------------------------------------------------
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
        files = [i["path"] for i in files_info]
        if split_note:
            self._emit(split_note, LogColor.SALMON)
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

        work = os.path.join(folder, WORK_DIRNAME)
        out_dir = os.path.join(folder, OUT_DIRNAME)
        proc = os.path.join(work, "process")
        if os.path.isdir(work):
            shutil.rmtree(work, ignore_errors=True)
        os.makedirs(proc, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        self.progress.emit(3, "Staging frames…")
        n_staged = self._stage_frames(work, files)
        self._emit(f"{n_staged} of {len(files)} sub(s) staged for photometry.",
                   LogColor.GREEN)

        seq = "lights"
        self.progress.emit(10, "Building the sequence…")
        self._cmd("cd", self._q(os.path.join(work, "lights")))
        self._cmd("link", seq, "-out=../process")
        self._cmd("cd", self._q(proc))

        self.progress.emit(15, "Calibrating…")
        seq = self._calibrate(seq, files, folder, out_dir, work)

        self.progress.emit(20, "Registering…")
        self._register(seq)

        self.progress.emit(35, "Detecting stars on the reference frame…")
        stars, ref_path = self._detect_reference_stars(seq, proc)
        self._resolve_site(files)
        fwhm = _median([getattr(st, "fwhmx", 0.0) for st in stars]) or 3.0
        self._emit(f"  {len(stars)} star(s) detected, median FWHM "
                   f"{fwhm:.2f} px.", LogColor.BLUE)
        flip = self._check_for_flip(seq)

        target = pick_target(
            stars,
            self.opts.get("target_mode", "brightest"),
            want_xy=self.opts.get("target_xy"),
            want_radec=self.opts.get("target_radec"),
        )
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
            target_saturated = True
            sat_why += "; below the pixel threshold but Siril flagged it"
        if target_saturated:
            self._emit(
                "  The target is SATURATED — " + sat_why + ". Its core no "
                "longer scales with flux, so the depth measured below is "
                "not trustworthy; shorten the sub-exposure and re-shoot.",
                LogColor.SALMON)

        crowd = crowding_note(stars, tx, ty, fwhm)
        if crowd:
            self._emit("  " + crowd[1], crowd[0])

        comps, rejected, how_ranked = choose_comparison_stars(
            stars, (tx, ty), int(self.opts.get("n_comps", DEFAULT_N_COMPS)),
            fwhm, float(self.opts.get("min_comp_snr", MIN_COMP_SNR)))

        # Tally the reasons, not the stars.  865 individual rejection lines
        # is not a diagnosis; "865 x SNR 0 below 20" is one, and it is the
        # line that would have explained the first real run in one glance.
        tally = {}
        for _x, _y, why in rejected:
            key = re.sub(r"[-+]?\d*\.?\d+", "N", why)
            tally[key] = tally.get(key, 0) + 1
        summary = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)

        if len(comps) < MIN_COMPS:
            lines = "; ".join(f"{n} x {why}" for why, n in summary[:4])
            self._fail(
                f"Only {len(comps)} usable comparison star(s) after filtering "
                f"(need at least {MIN_COMPS}). Of {len(rejected)} not used: "
                f"{lines}. Selection was {how_ranked}.")
            return
        self._emit(f"  {len(comps)} comparison star(s) chosen "
                   f"({how_ranked}), {len(rejected)} not used.",
                   LogColor.GREEN)
        for why, n in summary[:4]:
            self._emit(f"    {n} x {why}", LogColor.SALMON)

        self.progress.emit(45, "Aperture photometry (Siril)…")
        self._run_light_curve(seq, (tx, ty), comps)

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
        severity, note = photometry_yield_note(int(jd.size), len(files),
                                               target_saturated)
        if note:
            self._emit("  " + note,
                       LogColor.RED if severity == "bad" else LogColor.SALMON)
        yield_note = note

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
        jd = bjd

        self.progress.emit(70, "Detrending and fitting…")
        raw_mag = mag.copy()
        # Centre on the median so the curve reads as a delta and the plot
        # does not depend on the arbitrary comp-ensemble zero point.
        mag = mag - _median(mag)
        raw_rms = _mad_std(mag) * 1000.0

        X, airmass_note = self._airmass_series(jd_utc)
        slope = intercept = None
        detrended = mag
        if X is not None and self.opts.get("detrend_airmass", True) \
                and not airmass_note:
            detrended, slope, intercept = airmass_detrend(mag, X)

        fit = fit_transit(jd, detrended)
        if fit is None:
            # The fit refuses below ten points, and silence there reads as
            # "no transit found" rather than "nothing was attempted".  The
            # trapezoid has four free parameters plus a baseline; four
            # points cannot constrain five numbers, and the two-sided
            # significance test needs samples before, inside AND after the
            # window on top of that.
            self._emit(
                f"  No transit fit attempted: {jd.size} usable point(s) "
                f"cannot constrain a trapezoid (T0, duration, ingress, "
                "depth, baseline) plus a baseline on both sides of it. "
                "This is not 'no transit found' — nothing was tested.",
                LogColor.SALMON)
        # Second pass: with a first estimate of the transit window the
        # airmass baseline can be anchored on the points that are genuinely
        # out of transit, which is exact where the blind trim is only good.
        refined = False
        if (fit is not None and X is not None and slope is not None
                and self.opts.get("detrend_airmass", True)):
            d2, s2, i2 = airmass_detrend(mag, X, fit["oot_mask"])
            f2 = fit_transit(jd, d2)
            if f2 is not None:
                detrended, slope, intercept, fit = d2, s2, i2, f2
                refined = True

        self.progress.emit(88, "Writing results…")
        result = {
            "calib_note": getattr(self, "_calib_note", ""),
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
            "yield_note": yield_note,
            "jd_utc": jd_utc,
            "time_system": time_system,
            "time_note": time_note,
            "n_frames": len(files),
            "dat_path": dat,
            "ref_path": ref_path,
        }
        self._write_csv(result)
        self.progress.emit(100, "Done.")
        self.finished_ok.emit(result)

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

    def render(self, r: dict, n_bins: int = 0) -> None:
        self.fig.clear()
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

        ax.plot(x, y * 1000.0, ".", color="#7799cc", markersize=3,
                alpha=0.65, label=f"{jd.size} points")

        if n_bins > 0:
            bt, bm, be, _bn = bin_series(x, y * 1000.0, n_bins)
            if bt.size:
                ax.errorbar(bt, bm, yerr=be, fmt="o", color="#ffcc66",
                            markersize=4, linewidth=1, capsize=2,
                            label=f"binned ({n_bins})")

        if fit is not None:
            order = np.argsort(fit["model_t"])
            mx = (fit["model_t"][order] - t0_ref) * 24.0
            my = fit["model_mag"][order] * 1000.0
            colour = "#66dd88" if fit["detected"] else "#dd8866"
            label = (f"trapezoid, {fit['significance']:.1f}σ"
                     if fit["detected"] else
                     f"best fit, only {fit['significance']:.1f}σ — not claimed")
            ax.plot(mx, my, "-", color=colour, linewidth=1.6, label=label)
            half = fit["duration_d"] * 24.0 / 2.0
            c = (fit["t0"] - t0_ref) * 24.0
            ax.axvspan(c - half, c + half, color="#ffffff", alpha=0.04)
            ax.axvline(c, color=colour, linewidth=0.8, linestyle="--", alpha=0.7)
            axr.plot(x, (y - np.interp(jd, fit["model_t"], fit["model_mag"]))
                     * 1000.0, ".", color="#888888", markersize=3, alpha=0.6)
        else:
            axr.plot(x, (y - float(np.median(y))) * 1000.0, ".",
                     color="#888888", markersize=3, alpha=0.6)

        ax.invert_yaxis()
        ax.set_ylabel("Δ magnitude [mmag]")
        ax.set_title(f"{os.path.basename(r['folder'])}  ·  "
                     f"RMS {r['rms_mmag']:.2f} mmag  ·  "
                     f"{len(r['comps'])} comparison stars")
        leg = ax.legend(loc="best", fontsize=8, facecolor="#2b2b2b",
                        edgecolor="#555555")
        for txt in leg.get_texts():
            txt.set_color("#cccccc")
        ax.tick_params(labelbottom=False)

        axr.axhline(0.0, color="#555555", linewidth=0.8)
        axr.invert_yaxis()
        axr.set_ylabel("resid [mmag]")
        axr.set_xlabel(f"hours from JD {t0_ref:.0f} (UTC)")

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

        title = QLabel("Svenesis LightCurve")
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
            "Brightest star in the field",
            "Pixel position on the first frame",
            "RA / Dec (needs plate-solved subs)",
        ])
        self.cmb_target.setToolTip(
            "How to find the star whose light curve you want.\n\n"
            "Brightest is right surprisingly often — a transit host is "
            "usually the reason the field was framed that way. Pixel and "
            "RA/Dec both SNAP to the nearest detected star rather than "
            "using your number directly: a position two pixels off centre "
            "loses flux, and it loses a different amount every time the "
            "seeing changes.")
        self.cmb_target.currentIndexChanged.connect(self._update_target_fields)
        lay.addWidget(self.cmb_target)

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
        row.addStretch()
        lay.addLayout(row)
        parent.addWidget(box)

    def _build_action_buttons(self, parent: QVBoxLayout) -> None:
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        parent.addWidget(self.progress)

        row = QHBoxLayout()
        self.btn_run = QPushButton("Measure light curve")
        self.btn_run.setObjectName("RenderButton")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._on_run)
        row.addWidget(self.btn_run, 2)
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedWidth(34)
        self.btn_help.clicked.connect(self._show_help)
        row.addWidget(self.btn_help)
        parent.addLayout(row)

        row2 = QHBoxLayout()
        self.btn_png = QPushButton("Save plot…")
        self.btn_png.setEnabled(False)
        self.btn_png.clicked.connect(self._on_save_png)
        row2.addWidget(self.btn_png)
        self.btn_report = QPushButton("Save report…")
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self._on_save_report)
        row2.addWidget(self.btn_report)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.clicked.connect(self.close)
        row2.addWidget(self.btn_close)
        parent.addLayout(row2)

        self.lbl_status = QLabel("Choose a folder of sub-exposures.")
        self.lbl_status.setStyleSheet("color:#888888;font-size:9pt;")
        self.lbl_status.setWordWrap(True)
        parent.addWidget(self.lbl_status)

    def _build_right_panel(self) -> QWidget:
        self.tabs = QTabWidget()
        self.plot = LightCurvePlot()
        self.tabs.addTab(self.plot, "Light curve")

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setStyleSheet(
            "background-color:#1e1e1e;border:1px solid #444444;"
            "border-radius:4px;font-family:monospace;font-size:9pt;")
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
            "border-radius:4px;font-family:monospace;font-size:9pt;")
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
        pixel_mode = self.cmb_target.currentIndex() == 1
        for w in (self.lbl_x, self.ed_x, self.lbl_y, self.ed_y):
            w.setVisible(pixel_mode)

    def _log(self, msg: str, color=None) -> None:
        tint = {LogColor.GREEN: "#88cc88", LogColor.SALMON: "#ddaa88",
                LogColor.RED: "#dd8888"}.get(color, "#bbbbbb")
        self.log_view.append(f'<span style="color:{tint}">{msg}</span>')

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
        self.btn_run.setEnabled(len(files) >= 10)
        if len(files) < 10:
            self.lbl_status.setText(
                f"Only {len(files)} frame(s) — a light curve needs a time "
                "series. Ten is the bare minimum.")
        else:
            self.lbl_status.setText("Ready.")

    def _target_mode(self) -> str:
        return ("brightest", "pixel", "radec")[self.cmb_target.currentIndex()]

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
            "detrend_airmass": self.chk_detrend.isChecked(),
        }

    def _on_run(self) -> None:
        if not self._folder:
            return
        opts = self._opts()
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
        self.tabs.setCurrentWidget(self.plot)

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
            self.plot.render(self._result, self.spin_bins.value())

    # -- reporting --------------------------------------------------------
    def _result_html(self, r: dict) -> str:
        fit = r.get("fit")
        p = ['<div style="font-family:monospace;font-size:9pt;color:#dddddd">']
        p.append(f"<h3 style='color:#88aaff'>{os.path.basename(r['folder'])}</h3>")
        p.append("<b>Photometry</b><br>")
        p.append(f"&nbsp;{r['n_points']} of {r['n_files']} frames measured<br>")
        p.append(f"&nbsp;target at ({r['target_xy'][0]:.1f}, "
                 f"{r['target_xy'][1]:.1f}) — {r['target_how']}<br>")
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
                     + "<br><br>")
        else:
            why = r.get("airmass_note") or "not requested"
            p.append(f"&nbsp;not removed — {why}<br><br>")

        p.append("<b>Transit fit</b><br>")
        if fit is None:
            p.append("&nbsp;too few usable points to attempt a fit.<br>")
        elif not fit["detected"]:
            p.append(f"&nbsp;<span style='color:#dd8866'>No transit claimed."
                     f"</span> The best trapezoid reaches only "
                     f"{fit['significance']:.1f}σ against a "
                     f"{MIN_DETECTION_SIGMA:.1f}σ floor.<br>")
            p.append(f"&nbsp;(For the curious: it wanted "
                     f"{fit['depth_mmag']:.1f} mmag over "
                     f"{fit['duration_h']:.2f} h. Do not quote that.)<br>")
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
            p.append(f"&nbsp;T0 &nbsp;&nbsp; {fit['t0']:.5f} "
                     f"{r['time_system']}, mid-exposure<br>")
            if r["time_system"] != "BJD_TDB":
                p.append("&nbsp;<span style='color:#e08080'>This T0 is NOT "
                         "comparable with a published ephemeris — those are "
                         "quoted in BJD_TDB and the offset reaches 8 minutes."
                         f" ({r['time_note']})</span><br>")
            p.append(f"&nbsp;depth&nbsp; {fit['depth_mmag']:.1f} ± "
                     f"{fit['depth_sigma_mmag']:.1f} mmag "
                     f"({fit['depth_pct']:.3f} % of the flux)<br>")
            p.append("<span style='color:#888888'>&nbsp;that ± carries the "
                     "same red-noise scaling as the significance, but "
                     "depth/error is NOT the significance: it uses the "
                     "fitted depth against one baseline, while the "
                     "significance uses the measured contrast against the "
                     "weaker of the two sides. Quote the "
                     "significance.</span><br>")
            p.append(f"&nbsp;length {fit['duration_h']:.2f} h, ingress "
                     f"{fit['ingress_frac'] * 100:.0f} % of it<br>")
            p.append(f"&nbsp;{fit['n_in']} points inside, {fit['n_out']} "
                     "outside<br>")
            p.append(f"&nbsp;residual scatter {fit['rms_resid_mmag']:.2f} "
                     "mmag<br>")
            if fit["duty_cycle"] > BLIND_DETREND_BREAKDOWN and r["slope"] is not None:
                p.append(f"<br>&nbsp;<span style='color:#ddaa88'>The event "
                         f"covers {fit['duty_cycle'] * 100:.0f} % of the run"
                         + (", so the airmass baseline rests entirely on the "
                            "out-of-transit anchor — the blind first pass has "
                            "no untouched baseline left to trim to at that "
                            "coverage."
                            if r["refined"] else
                            ", and the second pass did not run, so the "
                            "baseline came from the blind trim alone. At that "
                            "coverage the trim is no better than a plain fit: "
                            "treat the depth as a lower bound.")
                         + " More baseline before ingress and after egress is "
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
        for i, (x, y, snr) in enumerate(r["comps"], start=1):
            A(f"   comp {i:<2d}       ({x:8.2f}, {y:8.2f})  SNR {snr:.0f}")
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
        else:
            A(f"Airmass ramp      not removed — {r.get('airmass_note') or 'not requested'}")
        A("")
        if fit is None:
            A("Transit fit       not attempted — too few usable points")
        elif not fit["detected"]:
            A(f"Transit fit       NOT CLAIMED — best trapezoid reaches only "
              f"{fit['significance']:.2f} sigma")
            A(f"                  (floor is {MIN_DETECTION_SIGMA:.1f} sigma; "
              "the fitted numbers below are not a measurement)")
            A(f"   depth          {fit['depth_mmag']:.2f} mmag")
            A(f"   duration       {fit['duration_h']:.3f} h")
        else:
            A(f"Transit fit       DETECTED at {fit['significance']:.2f} sigma")
            A(f"   Significance   {fit['significance']:.1f} sigma "
          f"(white-noise value {fit['significance_white']:.1f}, "
          f"red-noise beta {fit['red_noise_beta']:.2f})")
        A(f"   False alarm    {100 * MEASURED_FALSE_ALARM:.2f} % at the "
          f"{MIN_DETECTION_SIGMA:.1f} sigma floor")
        A(f"                  (measured, {MEASURED_FALSE_ALARM_RUNS} "
          "transit-free noise runs through this same grid search;")
        A("                  the search is over ~40 000 nodes, so this is "
          "NOT the Gaussian value for that sigma)")
        for w, b, nb, k in fit.get("red_noise_rows", []):
            A(f"      bin {w * 24 * 60:5.1f} min  beta {b:4.2f}  "
              f"{nb} bins of ~{k:.1f} points")
        A(f"   T0             {fit['t0']:.6f} {r['time_system']}, "
          "mid-exposure")
        A(f"   Time system    {r['time_note']}")
        if r["time_system"] != "BJD_TDB":
            A("                  <-- NOT comparable with a published "
              "ephemeris (those use BJD_TDB; the offset reaches 8 minutes)")
            A(f"   depth          {fit['depth_mmag']:.2f} +/- "
              f"{fit['depth_sigma_mmag']:.2f} mmag "
              f"({fit['depth_pct']:.4f} % of flux)")
            A("                  the +/- carries the same red-noise scaling "
              "as the significance above, but")
            A("                  depth/error is NOT that significance — it "
              "uses the fitted depth against")
            A("                  one baseline, the significance the "
              "measured contrast against the weaker")
            A("                  of both sides. Quote the significance.")
            A(f"   duration       {fit['duration_h']:.3f} h")
            A(f"   ingress        {fit['ingress_frac'] * 100:.0f} % of the duration")
            A(f"   points         {fit['n_in']} in, {fit['n_out']} out")
            A(f"   residual RMS   {fit['rms_resid_mmag']:.2f} mmag")
            A(f"   duty cycle     {fit['duty_cycle'] * 100:.0f} % of the run")
        A("")
        A("Method")
        A("   Aperture photometry by Siril's own light_curve command")
        A("   Registration two-pass, NOT resampled — the aperture follows the")
        A("   star through the registration data while the pixels stay as the")
        A("   sensor recorded them.")
        A("   Trapezoid fit: grid over T0/duration/ingress, depth and baseline")
        A("   solved analytically at each node. Deterministic, no optimiser.")
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
        default = os.path.join(self._result["out_dir"], "report.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save report", default, "Text file (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._report_text(self._result))
            self.lbl_status.setText(f"Report saved to {path}")
        except OSError as exc:
            QMessageBox.warning(self, "Svenesis LightCurve",
                                f"The report could not be written: {exc}")

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
        self.chk_autoring.setChecked(str(st.value("autoring", "true")) == "true")
        self.chk_detrend.setChecked(str(st.value("detrend", "true")) == "true")

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
        st.setValue("autoring", "true" if self.chk_autoring.isChecked() else "false")
        st.setValue("detrend", "true" if self.chk_detrend.isChecked() else "false")

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
<p><b>Siril</b> does the pixel work. <tt>light_curve</tt> is Siril's own
aperture photometry — the same code behind its Photometry tool — and it
already handles the sky annulus, the FWHM-scaled ring radii, saturation
and per-frame star matching. Re-implementing that here would give you a
second, worse photometry engine that has to be kept in step with the
first.</p>
<p><b>This script</b> does the parts Siril has no opinion about: which star
is the target, which stars are worth calibrating against, removing the
airmass ramp, fitting the transit — and, above all, deciding whether the
dip is real.</p>
<h3 style='color:#88aaff'>The steps</h3>
<ol>
<li><b>Stage</b> — your subs are symlinked into a working folder. The
original folder is never written to.</li>
<li><b>Link</b> — Siril builds a sequence from them.</li>
<li><b>Register (two-pass)</b> — registration data only, <i>no
resampling</i>. This matters more for photometry than for stacking:
interpolation correlates neighbouring pixel noise and moves flux around
inside the aperture. The aperture follows the star through the
registration data while the pixels stay exactly as the sensor recorded
them.</li>
<li><b>Detect + choose</b> — Siril finds the stars, this script picks the
target and the comparison ensemble.</li>
<li><b>light_curve</b> — Siril's aperture photometry, writing
<tt>light_curve.dat</tt>.</li>
<li><b>Analyse</b> — detrend, fit, decide.</li>
</ol>
<h3 style='color:#88aaff'>What you get</h3>
<p><tt>lightcurve/lightcurve.csv</tt> with every point (raw, centred, detrended,
airmass), the plot as PNG, and a plain-text report you can attach to a
submission or a forum post.</p>
""")

        _tab("Choosing stars", """
<h2 style='color:#88aaff'>The target</h2>
<p>Three ways, and all three end at a <i>detected</i> star:</p>
<ul>
<li><b>Brightest</b> — right more often than you would think. A transit
host is usually the reason the field was framed the way it was.</li>
<li><b>Pixel position</b> — from the first frame.</li>
<li><b>RA / Dec</b> — needs plate-solved subs.</li>
</ul>
<p>Pixel and RA/Dec both <b>snap to the nearest detected star</b> rather
than using your number directly. A position two pixels off the centroid
puts the aperture off-centre for the whole run, and the flux it loses
changes with the seeing — which is exactly the shape of a fake trend.</p>

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
seeing. The radius is Siril's own geometry, not taste: <tt>-autoring</tt>
sets the outer ring to 6.3 × FWHM, so two annuli stop touching at twice
that.</td></tr>
</table>
<p>Every rejection is listed in the Log and in the report, and the tally
accounts for every detected star — including the ones that passed all four
filters and were merely surplus. The target cannot be dropped, so the same
geometry is reported for it instead.</p>
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
the depth at high coverage is a <b>lower bound</b>, not a measurement.</p>
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
<tr><td>3.0 σ</td><td>4.42 %</td><td>91 %</td><td>100 %</td><td>100 %</td></tr>
<tr><td><b>4.0 σ</b></td><td><b>0.17 %</b></td><td>53 %</td><td>98 %</td>
<td>100 %</td></tr>
<tr><td>5.0 σ</td><td>0.00 %</td><td>19 %</td><td>86 %</td><td>99 %</td></tr>
</table>
<p>4.0 is where the false-alarm rate reaches the 0.13 % that "3 sigma" was
always read to mean. It costs nothing above 6 mmag; what it costs is the
4-5 mmag case, a dip at about the per-point scatter, which was never safe
to claim from one night. The measured rate is printed next to every
result.</p>

<h2 style='color:#88aaff'>A trapezoid, not a limb-darkened model</h2>
<p>At amateur precision the two are indistinguishable — a 10 mmag dip
measured at 3 mmag per point does not constrain a limb-darkening
coefficient. What the trapezoid recovers is <b>depth, mid-time and
duration</b>, which is exactly what ExoClock and ETD consume.</p>
<p>Its ingress fraction is free, so it also handles the grazing case: at
0.5 the trapezoid degenerates into a triangle.</p>

<h2 style='color:#88aaff'>A grid, not an optimiser</h2>
<p>The search walks a grid over <b>T0</b>, <b>duration</b> and <b>ingress
fraction</b>. At every node the depth and the baseline are solved
<i>analytically</i>: for a fixed shape the model is
<tt>baseline + depth × shape(t)</tt>, which is linear in both, so a 2×2
solve gives the exact best pair.</p>
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
trapezoid has no free baseline term, so on transit-free data the fitter
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
