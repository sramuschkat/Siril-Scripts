"""
Svenesis ImageMono Train
Script Version: 1.4.0
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
- Recursive discovery: reads FITS headers, groups the LIGHT frames by
  optical filter across any number of dates / sessions, and collects the
  DARK / FLAT / DARK-FLAT / BIAS frames for calibration.
- Calibration (all of it optional and additive): session flats per filter,
  darks and bias from a reusable library folder, matched on header
  signature.  Masters are built, cached and reused automatically;
  Lc = (L - D) / (F - O), with bias applied only when no dark is used.
- A clear "here is what I found" report: every filter, its frame count,
  total integration time, exposure, gain and sensor temperature, shown
  before anything is stacked.
- Per-filter integration, following the proven Naztronomy Mono_PP command
  sequence: link/convert -> (optional calibration) ->
  (optional background extraction) ->
  2-pass star registration (or plate-solve registration) -> apply
  registration -> rejection integration, with the rejection algorithm
  chosen automatically from the frame count.
- Cross-filter alignment onto one common pixel grid, so the channels
  overlay exactly for colour combination.
- Colour composition with a palette picker: LRGB / RGB / SHO / HOO /
  HaRGB.  Narrowband channels are normalised to Ha first; for LRGB the
  luminance is kept separate so it can be combined after stretching
  (Siril's recommended order).
- Auto-finish on the composite: plate-solve, background extraction, colour
  calibration and SCNR -- leaving a calibrated, still-linear result.
- Sensor- and filter-aware colour calibration (SPCC), including a
  narrowband mode that calibrates SHO / HOO by emission-line wavelength;
  degrades step by step to plain PCC and a local Gaia catalog.
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
# Script Version: 1.4.0
# Siril Version: 1.4.0
# Python Module Version: 1.4.0
# Script Category: preprocessing
# Script Description: Point it at a N.I.N.A. target folder; it discovers the
#   light frames per optical filter, calibrates them with whatever darks,
#   flats and bias it finds, integrates one master stack for each filter
#   (mono, never debayered), aligns the channels onto a common grid
#   and combines them into a colour image (LRGB / RGB / SHO / HOO / HaRGB)
#   with background extraction and photometric colour calibration.  Writes a
#   Markdown processing report and a post-processing guide alongside.
# Script Author: Sven Ramuschkat

CHANGELOG:
1.4.0 - Per-palette stacking, and a report that matches the run
      - "Finish: calibrated composite saved" was printed unconditionally,
        two log entries after "colour calibration skipped for HaRGB
        (Ha-boosted Red)".  The same claim went into the report as "Saved
        the calibrated, still-LINEAR composite".  Both now key on the
        success line, so a skipped or failed calibration reads as
        "composite (uncalibrated)"
      - Switching "Normalize narrowband channels" off while narrowband
        SPCC is on is the recommended pairing, and `todo.md` was calling
        it a defect: "the channels were **not** normalized ... re-run with
        Normalize narrowband channels enabled" -- which would undo the
        calibration the reader had just been advised to get.  That branch
        now only fires when no narrowband SPCC ran.  Measured on two
        M 16 runs differing only in that option: R/G sigma 2.64 with it
        off against 2.73 with it on, and the fitted slope 1.209 against
        1.251 (closer to 1 = less correction needed).  Real, but far
        smaller than the alignment effect
      - The "try another palette in seconds" tip contradicted the line
        directly above it, which had just explained that the skipped
        filters were never stacked and that another palette therefore
        needs a full re-run.  It is now suppressed in exactly that case.
        The narrowband version also offered to "try HOO" at the end of a
        HOO run; it names the other narrowband palette instead
      - A run that produces no composite no longer reads as if it had.
        The report opened with "The script stacked each filter, aligned the
        channels, and combined them into a colour image" three sections
        above "No colour composite was produced this run", and section 4
        called that absent image "this image".  In `todo.md` the
        narrowband step told the reader to re-run with "Normalize
        narrowband channels" enabled -- an option that was already on and
        had nothing to do with it: normalization is part of the
        composition, and there was none
      - The stale-master warning no longer claims the leftovers share one
        grid.  After four palette-only runs, `masters/` held HA, LUMINOS
        and OIII from three different runs on three different canvases,
        and the warning said "that run's grid" as if there were one
      - Section 4 names the calibration that actually ran instead of
        always saying "PCC", which contradicted the "Colour calibration:
        SPCC" line three paragraphs above it
      - "Quick linear LRGB" is now carried into both documents, not just
        the log.  The report said "luminance baked in linearly" and then
        "Colour calibration: SPCC" with nothing connecting them, and
        todo.md claimed the script "keeps L separate automatically" --
        the exact opposite of what the option had just done -- and told
        the reader to leave the white balance alone.  Measured on two
        M 16 runs over the same R/G/B masters, differing only in that
        option: SPCC dropped 531 of 2597 stars as "pixel out of range"
        with L baked in, against 68 of 2603 without.  1057 stars carried
        the solution instead of 1484, and both fits came out worse
        (R/G sigma 1.33 against 1.15, B/G 0.35 against 0.32)
      - The stale-master warning is emitted after the LAST row of the
        folder table, not after the `output.md` row.  A blockquote between
        two rows ends a Markdown table, so `todo.md` and `qa/` were
        rendered as loose text below it
      - The skipped-filter messages agree in number.  A HaRGB run leaves
        out exactly one channel and reported "OIII are not read by this
        palette"; the log line, the report bullet, the stale-master
        warning and both todo tips hard-coded the plural
      - The two documents no longer describe work the palette skipped.
        `output.md` said "For **every filter**, the raw lights were turned
        into one master light" two lines above the note listing the four
        filters it had not touched, claimed "all masters were pooled" for
        an alignment over two of six, and credited plate-solving to every
        master.  Its file table promised that `masters/*.fit` share one
        grid while the folder still held four channels from an earlier
        alignment on a different one -- now flagged, with the reason and
        the way out.  `todo.md` told the reader to trust an SPCC baseline
        that `output.md` flags as self-defeating, and offered a palette
        swap "in seconds" from masters that were never built
      - Full master reuse is refused when the aligned masters are not all
        the same size.  `-framing=min` crops to the intersection of
        whatever was in the alignment sequence, so a run that aligns a
        subset (see the option below) leaves the other channels on the
        previous grid; reusing the mix would hand `rgbcomp` channels of
        different dimensions.  Partial reuse is unaffected -- the
        fullframe masters it keeps predate alignment
      - The run no longer opens with "Stacking N filter(s)" and then skips
        four of them one line later.  It reports what was discovered, and
        the worker -- the only part that knows -- reports what is stacked
      - New option "Stack only the filters this palette uses" (off by
        default).  An LRGB night processed as HOO stacked four masters the
        composite never opened.  Besides the time, it cost quality: the
        cross-filter alignment hands every master to Siril's two-pass
        registration, which picks the reference itself -- `setref` cannot
        override it, its help says -2pass exists to "find a good reference
        image" -- and a star-rich broadband master wins.  The narrowband
        channels then match a frame whose stars they do not share: on one
        M 16 run OIII aligned on 12 star pairs and Ha on 22, against
        188-476 for the broadband masters.  The set is derived from the
        channel mapping rather than the palette name, so it cannot
        disagree with what `_compose` reads; skipping is refused when the
        palette has an unfillable channel anyway, and when no composite is
        being made at all -- greying the box out with the rest of the
        compose group is cosmetic, a saved preset can still arrive with
        both set, and without a composite nothing reads a palette
      - `register -2pass` and `seqapplyreg` no longer share one `try`.
        They fail for unrelated reasons and only the first one is about
        two-pass support: a frame the cloud-sync folder had not finished
        materialising was reported as "2-pass registration unavailable"
        although registration had just succeeded on all six frames, and
        the retry then used a command that silently drops framing,
        drizzle and every quality filter -- `register` alone accepts
        neither -framing= nor any -filter-*.  Each failure now gets its
        own message and its own fallback, what could not be honoured is
        recorded per channel, and the report says which master was not
        built the way the options describe
      - SPCC sends the mono sensor in narrowband mode too.  Siril's help
        says -narrowband makes it ignore "the previous filter arguments"
        -- filters only -- and its usage grammar keeps -monosensor= in a
        separate group, because the sensor's quantum efficiency at 656 and
        501 nm is an independent factor.  Leaving it out never failed; it
        silently used whatever sensor Siril's own dialog last held, which
        on a fresh install is an OSC one.  The filter names are now
        omitted there on purpose, and the log says so, because Siril
        echoes its stored names on every run and they look like ours
      - "Normalize narrowband channels" and SPCC's narrowband mode are
        flagged when both are on.  They balance the same thing by opposite
        means: linear_match flattens the Ha / OIII flux ratio on purpose,
        and that ratio is precisely what SPCC measures against catalogue
        spectra.  Observed on one HOO run: R/G fit sigma 5.8, against 1.4
        for a broadband composite of the same night.  Log, report, tooltip
        and help now say which one to switch off

1.3.0 - Colour calibration, rejection and background modelling
      - SPCC (Spectrophotometric Colour Calibration) replaces PCC as the
        preferred method: it accounts for the sensor's and filters'
        response curves, which plain PCC cannot.  Optional sensor / filter
        names; blank falls back to Siril's own preferences
      - SHO and HOO are colour-calibrated for the first time, via SPCC's
        narrowband mode using each line's wavelength (Ha 656.3, OIII 500.7,
        SII 671.6 nm) and a configurable filter bandwidth.  PCC is never
        attempted there -- star photometry does not describe mapped
        emission lines
      - The whole chain degrades one step at a time and never aborts the
        finish: SPCC with details -> bare SPCC -> PCC -> PCC with a local
        Gaia catalog -> report it plainly.  HaRGB stays excluded (its Red
        channel carries blended Ha)
      - GESDT rejection from 50 frames, where Siril documents it as
        outperforming linear-fit clipping.  Its parameters are NOT sigmas
        (max rejected fraction / significance), and a build that does not
        know the token falls back to linear fit instead of losing the stack
      - Frame weighting is selectable: weighted FWHM (default), noise or
        star count.  Noise is the better choice for narrowband, where
        wFWHM penalises a sparse star field for the filter, not the frame
      - Optional RBF background model for the masters and the composite --
        it follows a gradient that changes direction across the frame,
        which a degree-1 polynomial cannot.  The per-sub pass stays
        polynomial, per Siril's guidance.  Falls back automatically
      - Drizzle now warns when it runs on fewer than 40 frames: it needs
        many dithered subs to fill the finer grid, and below that it adds
        noise instead of resolution
      - The report names the rejection algorithm that really ran, so a
        fallback cannot hide behind the preferred one
      - SPCC sensor and filter names are validated against the SPCC
        database Siril itself uses.  A wrong name is not an error for
        Siril -- it quietly substitutes something else, which is how a
        real run calibrated a mono filter-wheel rig as one-shot colour:
        "IMX533" exists only under osc_sensors, while the mono entry for
        the same chip is "Sony IMX411/455/461/533/571".  The script now
        reports a name that is missing from the mono table, names the OSC
        trap, lists candidates, and recognises a loose match as such.  A
        database it cannot find means "cannot check", never "invalid"
      - The rig defaults are seeded into the stored settings once, because
        a QSettings default only applies to a key that is ABSENT -- anyone
        who had already run the script had these saved as empty strings,
        so the new values would never have appeared.  Guarded by a flag, so
        clearing the fields afterwards still means "use Siril's own SPCC
        configuration"
      - The SPCC rig fields ship pre-filled for a Player One Ares-M Pro
        (IMX533 mono) with Antlia LRGB V-Pro and 4.5 nm Edge SHO filters,
        as DEFAULT_SPCC_* constants near the top of the script.  A test
        checks them against Siril's own database, so a typo there cannot
        ship silently
      - The narrowband bandwidth accepts fractional values.  It was an
        integer box, which made the common 3.5 / 4.5 / 6.5 nm filter specs
        impossible to enter -- an Antlia 4.5nm Edge set could not be
        described at all.  .json presets learned the new widget type
      - "Quick linear LRGB" is flagged when it runs into a photometric
        calibration: baking L in lifts the bright end, so more stars
        saturate and drop out of the fit (measured on one dataset:
        1107 -> 1531 stars excluded, 69 -> 522 of them saturated, R/G fit
        sigma 0.61 -> 0.77)
      - The palette warning is logged after the filter list it refers to,
        and no longer carries Markdown emphasis: the Log tab renders plain
        text, so "**LRGB**" showed up with its asterisks
      - A palette the discovered filters cannot fill is caught when it is
        CHOSEN, not after a full run: picking SHO without an SII filter
        used to stack, align and plate-solve everything and only then say
        "no aligned master mapped to the RED channel" -- baffling wording
        when a RED filter plainly exists, because SHO wants SII there.
        The message now names what the palette expects and which palette
        would work, and a run that was asked for a colour image and did
        not produce one no longer reports "All done ... 0 failed"
      - The SPCC database location is asked for via sirilpy
        (get_siril_userdatadir) instead of only guessing per-platform
        paths, which would miss a Flatpak / Snap / Store build entirely.
        The guesses remain as a fallback, the read stays read-only, and a
        database that cannot be found still means "cannot check"
      - Stopping a run now really stops it.  The abort only ended the
        stacking loop; alignment, plate-solving, colour composition and the
        auto-finish then ran on regardless -- up to half a minute of work,
        part of it against a photometry server, to build a colour image
        from an incomplete channel set, immediately after announcing that
        we were stopping.  Everything downstream is skipped, _work/ is
        never deleted, and log, report, status line and dialog say
        "stopped" instead of "All done"
      - Fixes from a further audit pass:
        * "did the quality filters fire?" is answered from what
          registration was actually told, recorded before it runs.  Once
          registration started dropping frames (see above), the report
          re-derived the answer from the survivor count and could claim
          they had not applied when they had -- 22 staged with filters,
          19 surviving, and the threshold is 20.  -filter-included had the
          same flaw
        * an SPCC name matching several database entries lists all of
          them instead of naming an arbitrary member of a set as "likely";
          the message was not even stable between runs
        * the Windows branch of the SPCC database search no longer builds
          a relative path when LOCALAPPDATA is unset
      - The report distinguishes an astrometric solution the composite
        INHERITED from the plate-solved masters (rgbcomp copies their
        header, so Siril's platesolve is then a no-op) from one that was
        computed here.  It used to claim "Plate-solved the composite" in
        both cases
      - SPCC arguments are quoted as a WHOLE, flag included:
        "-rfilter=Antlia R", not -rfilter="Antlia R".  sirilpy joins the
        arguments into one command line and Siril re-splits it shell-style,
        so quoting only the value splits inside it and the command aborts
        with "Invalid argument IMX411/455/461/533/571"".  The spcc command
        is echoed to the log, right above Siril's own line saying what it
        ended up using
      - Frames that REGISTRATION drops are now counted.  A sub without
        enough detectable stars (clouds, haze) simply fails to align and
        Siril excludes it -- the script kept using the staged count, so it
        picked the rejection algorithm for frames that were not there.  A
        real run lost 3 of 6 OIII frames and got winsorized sigma clipping
        on the surviving 3, which rejected 0.000%; percentile clipping is
        what 3 frames call for.  The count now comes from the files Siril
        actually exported, and the log says how many were lost and why
      - "Building calibration masters..." is no longer announced when no
        calibration frames were found: the payload always carries its four
        kind keys, so the old emptiness test was true even for an empty set
      - Fixes found while auditing the above:
        * the GESDT retry now fires for GESDT only.  As first written it
          triggered on ANY stack failure, swapping percentile or winsorized
          for linear fit on an unrelated error -- and, with rejection
          switched off, silently turning it back on
        * a palette that can only be calibrated by SPCC now reports
          "not attempted" when SPCC is switched off, instead of "FAILED",
          which blamed the tooling for a setting
        * a failed plate-solve is reported once, not twice
        * .json presets carry the SPCC sensor and filter names (they
          describe the rig, not the machine), and a widget type the loader
          cannot set counts as ignored instead of as applied
1.2.0 - Calibration: darks, flats, dark-flats and bias
      - Calibration frames are discovered alongside the lights instead of
        being discarded: flats grouped per filter, darks and bias grouped
        by signature (exposure, gain, temperature, binning, dimensions)
      - Reusable DARK / BIAS library folder, remembered between runs;
        session flats are found next to the lights, including the old
        N.I.N.A. layout where they sit beside the target folder
      - Masters are built automatically (a group of exactly one file is
        adopted as a ready-made master), cached in output/calib/ under
        descriptive header-derived names, and reused on later runs
      - Flats are offset-corrected before stacking: real bias / dark-flat,
        else Siril's synthetic offset, else raw -- never a hard failure
      - Matching runs on FITS headers with exact exposure/gain/binning/size
        and a +/-2 C temperature window; a non-matching dark is reported
        and skipped rather than applied
      - Bias is never applied together with a dark (the dark already
        contains the offset): Lc = (L - D) / (F - O)
      - Optional cosmetic correction (-cc=dark) and "match flats to the
        same night" for rigs that were rebuilt between sessions
      - The processing report lists every master used, per filter, and the
        "no calibration" note is now only printed when that is true
      - XISF files found during the scan are reported instead of silently
        vanishing; .fts.fz added to the recognised FITS extensions
      - Fixes found by auditing the calibration path:
        * darks are grouped by temperature as well, so a -10 C and a -20 C
          set can no longer be averaged into one physically wrong master
          (bias stays unsplit -- it is temperature-independent)
        * a library holding sets with and without a GAIN keyword no longer
          crashes the run when the signatures are sorted
        * master names now carry everything the grouping distinguishes
          (binning, flat date restriction), so the cache cannot hand back
          the wrong master; a remaining tie is broken and logged
        * "match flats to the same night" is no longer silently ignored on
          the second run
        * a filter mixing two exposures is reported -- the dark matches
          only one of them
      - Colour composition needs two masters again instead of three, so an
        Ha + OIII night can actually produce the HOO image it auto-detects
      - Calibration folders beside the target (the classic N.I.N.A. layout)
        are found again: the segment match was case-sensitive and never
        matched N.I.N.A.'s upper-case FLAT / DARK folders
      - Reporting and UI state, from a second audit pass:
        * reused filters are shown as "reused" instead of being given a
          frame count and a rejection algorithm from a run that never
          happened this time
        * frame counts the quality filters only predict are marked as
          estimates
        * clearing the library also drops what was found in it, instead of
          quietly keeping those darks in play
        * the library is scanned regardless of the "Apply calibration"
          switch, so toggling it after an analysis cannot leave the set of
          discovered masters incomplete
        * a failed analysis no longer leaves the previous folder's
          calibration frames and multiple-target warning behind
        * loading a .json preset now updates the calibration sub-options'
          enabled state
      - Only calibration frames are taken from outside the target folder:
        a light frame in the library or a neighbouring calibration folder
        used to be stacked into the target (and to trigger a bogus
        "several objects" warning).  It is now counted and reported
      - The analysis states how many files came from the target and how
        many from the library, instead of adding them all up under the
        target's path
      - The quality-filter spin boxes follow their mode: 1..100 for
        "% best", 1..10 for k-sigma.  A percentage left behind after a mode
        switch used to be read as a sigma multiple, which rejects nothing
        while the panel looks armed
      - The frame table in output.md only quotes a count for filters that
        really produced a master this run: one that was skipped for too few
        usable frames, that failed mid-pipeline, or that an abort never
        reached used to be listed as fully stacked, with a rejection
        algorithm that never ran.  A pipe inside a Siril error message no
        longer tears the table apart
      - k-sigma frame counts are marked as an upper bound (the number of
        frames beyond k sigma is Siril's call and cannot be predicted),
        instead of being printed as if nothing had been dropped
      - "Did the quality filters fire?" is answered from the arguments that
        were really emitted, not from a shrunken frame count: in k-sigma
        mode the report claimed they had not run at all, and when they were
        skipped because of the settings (100%, or too few frames left) it
        blamed the frame count instead
      - todo.md now describes what actually ran instead of the usual case:
        it no longer claims the colour is "already PCC-calibrated" when
        auto-finish was off or no photometry catalog was reachable, no
        longer claims narrowband channels were normalised when that option
        was off, and says plainly when no colour image was produced at all
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
import re
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
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QDialog,
    QLineEdit, QTextEdit, QTabWidget, QScrollArea, QProgressBar,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, pyqtSignal, QThread
from PyQt6.QtGui import QDesktopServices


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.4.0"
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
# Quality-assurance artefacts (rejection maps) that would otherwise be
# buried in _work/ and deleted with it.
QA_DIRNAME = "qa"
# Calibration masters built for / used by this run.
CALIB_DIRNAME = "calib"

# Recognised FITS containers.  ``.fz`` variants are Rice-compressed FITS.
FITS_EXTS = (".fit", ".fits", ".fts", ".fit.fz", ".fits.fz", ".fts.fz")

# Formats Siril could open but this script deliberately does not handle:
# astropy cannot read their headers, so exposure / gain / temperature -- and
# with them the whole calibration matching -- would be unavailable.  They are
# reported rather than silently ignored.
UNSUPPORTED_EXTS = (".xisf",)

# Header IMAGETYP values that mean "science frame".  N.I.N.A. writes
# "LIGHT"; some pipelines write "Light Frame".  Matched case-insensitively
# as a substring so both are covered.
LIGHT_TOKENS = ("light",)

# Frame types we must never treat as lights, even if a FILTER is present.
CALIB_TOKENS = ("dark", "flat", "bias", "offset")

# Frame kinds the calibration pipeline knows.  Order matters in _inspect:
# "dark flat" / "flatdark" must be tested before plain "dark" and "flat".
KIND_LIGHT = "light"
KIND_DARK = "dark"
KIND_FLAT = "flat"
KIND_DARKFLAT = "darkflat"
KIND_BIAS = "bias"

# How closely a library master must match the frames it calibrates.
# Exposure and gain must be exact; the cooled setpoint is allowed to drift a
# little, because CCD-TEMP is a measurement and wobbles by tenths of a degree.
CALIB_TEMP_TOLERANCE_C = 2.0

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

# From this many frames the Generalized Extreme Studentized Deviate Test
# outperforms linear-fit clipping (Siril's documentation puts the crossover
# at "more than 50 images").
GESDT_MIN_FRAMES = 50

# Drizzle redistributes each sub's flux onto a finer grid, so it needs many
# dithered frames to fill that grid evenly.  Below this count the coverage
# gets patchy and the result is noisier than the plain stack -- warn instead
# of silently producing a worse master.
DRIZZLE_MIN_FRAMES = 40

# Default rig description for SPCC, pre-filled into the UI.  These are the
# author's own filters and camera; change them here to match yours.  The
# names must exist in Siril's MONO tables -- see the Calibration help tab,
# and note that a chip is often listed under a different name there than in
# the OSC tables (the IMX533 mono entry is the family string below, while
# plain "IMX533" resolves to an OSC sensor and would make SPCC calibrate a
# filter-wheel rig as one-shot colour).
#   Camera:  Player One Ares-M Pro (IMX533 mono)
#   Filters: Antlia LRGB V-Pro  +  Antlia 4.5 nm Edge SHO
DEFAULT_SPCC_SENSOR = "Sony IMX411/455/461/533/571"
DEFAULT_SPCC_RFILTER = "Antlia R"
DEFAULT_SPCC_GFILTER = "Antlia G"
DEFAULT_SPCC_BFILTER = "Antlia B"
# Narrowband filters have no named entries in Siril's database, so the
# bandwidth plus the fixed line wavelengths below IS the whole description.
DEFAULT_NB_BANDWIDTH = 4.5

# Rest wavelengths of the narrowband lines, in nanometres.  These are
# physical constants, not settings -- SPCC's narrowband mode needs them to
# know what each mapped channel actually contains.
HA_NM = 656.3
OIII_NM = 500.7
SII_NM = 671.6

# UI label -> Siril's `-weight=` token.  Order is the combo box order.
WEIGHT_TOKENS = {
    "Weighted FWHM": "wfwhm",
    "Noise": "noise",
    "Number of stars": "nbstars",
}

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


def _has_wcs(path: str) -> bool:
    """True if the file already carries an astrometric solution.

    `rgbcomp` copies the header metadata of its inputs, so a composite
    built from plate-solved masters arrives already solved and Siril's
    `platesolve` answers "Nothing will be done".  The command succeeds
    either way, so the only way to report honestly which of the two
    happened is to look before calling it.

    Unreadable header -> False, i.e. "assume it needs solving": running
    platesolve unnecessarily costs a second, claiming a solution that is
    not there would mislead.
    """
    header = _read_header(path)
    if header is None:
        return False
    return any(k in header for k in ("CTYPE1", "CRVAL1", "CD1_1"))


def _clean_token(value) -> str:
    """Normalise a header string into a filesystem-friendly token."""
    if value is None:
        return ""
    txt = str(value).strip().strip("'\"").strip()
    return txt


def _object_key(name: str) -> str:
    """Comparison key for OBJECT names, ignoring spelling variations.

    "M 101", "M101" and "m-101" are the same target typed three ways --
    something that happens easily across nights, since the name is free text
    in N.I.N.A. and SIMBAD hands it out with a space.  Warning about those as
    "different objects" would be a false alarm; "M101" vs "M51" still is one.
    """
    return re.sub(r"[\s_-]+", "", (name or "").strip().lower())


def _classify_kind(imagetyp: str) -> str | None:
    """Map an IMAGETYP header value to a frame kind.

    Substring matching is right here: the keyword is a type name, so
    "Light Frame", "Flat Field" and "Dark Frame" must all be recognised.
    Order matters -- "DARKFLAT" / "FLATDARK" / "Dark Flat" contain both
    "dark" and "flat", so the combined form is tested first or a dark-flat
    would be mistaken for a plain dark.  Returns None for anything
    unrecognised, so odd files are skipped rather than guessed at.
    """
    h = (imagetyp or "").lower()
    if not h:
        return None
    has_dark = "dark" in h
    has_flat = "flat" in h
    if has_dark and has_flat:
        return KIND_DARKFLAT
    if has_flat:
        return KIND_FLAT
    if has_dark:
        return KIND_DARK
    if "bias" in h or "offset" in h:
        return KIND_BIAS
    if any(t in h for t in LIGHT_TOKENS):
        return KIND_LIGHT
    return None


def _classify_path(parts: list) -> str | None:
    """Fallback classification from the folder names, for files with no
    IMAGETYP keyword.

    Matches WHOLE path segments, never substrings: a target called
    "Dark-Nebula" or "Flaming-Star" must not turn its lights into darks.
    N.I.N.A. writes the image type as its own folder ("LIGHT", "FLAT",
    "DARKFLAT" ...), so an exact segment match is both safe and sufficient.
    """
    # Lower-cased: N.I.N.A. writes the type folder in capitals ("LIGHT",
    # "FLAT"), so a case-sensitive comparison would never match.
    seg = {p.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
           for p in parts}
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


_DATE_SEGMENT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _path_date(path: str) -> str:
    """The session date encoded in the path, or "" if there is none.

    N.I.N.A. writes a `YYYY-MM-DD` folder per night, which is what pairs a
    set of flats with the lights they belong to.  The deepest matching
    segment wins, so a date in a parent folder cannot mask a more specific
    one further down.
    """
    for seg in reversed(os.path.normpath(path).split(os.sep)):
        if _DATE_SEGMENT_RE.match(seg):
            return seg[:10]
    return ""


def _calib_signature(info: dict, with_temp: bool = False) -> tuple:
    """Grouping key for darks / bias: what must agree to share a master.

    ``with_temp`` splits the groups by sensor temperature as well, and is
    required for DARKS: dark current is a function of temperature, so
    averaging a -10 C and a -20 C frame into one master produces a dark that
    is correct for neither.  BIAS is read-noise only and essentially
    temperature-independent, so splitting it would just make each master
    noisier for nothing.

    The temperature is rounded to a whole degree.  Cooled setpoints are
    integers and CCD-TEMP wobbles by tenths, so a session lands in one
    bucket; two genuinely different setpoints land in two.
    """
    temp = info.get("temp_v")
    return (round(float(info.get("exp_s") or 0.0), 3),
            info.get("gain_v"),
            info.get("binning", 1),
            info.get("dims"),
            (round(float(temp)) if with_temp and temp is not None else None))


def _sig_sort_key(sig) -> tuple:
    """Total order over signature tuples, tolerating missing values.

    A signature carries ``None`` wherever the header said nothing, and
    ``sorted()`` cannot compare ``None`` with a number -- it raises
    TypeError, which would take down the whole run.  Missing values sort
    last; within a position the types are homogeneous, so the value itself
    is only ever compared against its own kind.
    """
    return tuple((v is None, 0 if v is None else v) for v in sig)


def _signature_matches(master: dict, target: dict) -> bool:
    """True if `master` may calibrate frames described by `target`.

    Exposure, gain, binning and image size must agree exactly; the cooled
    setpoint may drift a little because CCD-TEMP is a measurement.  A missing
    gain, temperature or size is treated as "unknown, don't block" -- refusing
    a usable master because a keyword is absent would be worse than using it.
    Exposure is the exception: `_inspect` reports an unreadable EXPTIME as
    0.0, and 0 s vs 120 s is exactly the mismatch that must not slip through,
    so an unknown exposure blocks the match.
    """
    if master.get("dims") and target.get("dims") \
            and master["dims"] != target["dims"]:
        return False
    if master.get("binning", 1) != target.get("binning", 1):
        return False
    for key in ("gain_v",):
        mv, tv = master.get(key), target.get(key)
        if mv is not None and tv is not None and mv != tv:
            return False
    me, te = master.get("exp_s"), target.get("exp_s")
    if me is not None and te is not None:
        if abs(float(me) - float(te)) > 0.01:
            return False
    mt, tt = master.get("temp_v"), target.get("temp_v")
    if mt is not None and tt is not None:
        if abs(float(mt) - float(tt)) > CALIB_TEMP_TOLERANCE_C:
            return False
    return True


def _mixed_grids(paths: dict) -> dict:
    """``{filter: (w, h)}`` when the aligned masters disagree on size.

    Empty when they all match, or when no size could be read -- an
    unreadable header is not evidence of a mismatch, and refusing reuse
    over one would be worse than the mismatch it is guarding against.
    """
    dims: dict = {}
    for filt, path in paths.items():
        header = _read_header(path)
        if header is None:
            continue
        try:
            dims[filt] = (int(header.get("NAXIS1", 0)),
                          int(header.get("NAXIS2", 0)))
        except (ValueError, TypeError):
            continue
    return dims if len(set(dims.values())) > 1 else {}


def _inspect(path: str) -> dict:
    """Read a FITS header ONCE and return everything discovery needs.

    Returns ``kind`` (light / dark / flat / darkflat / bias / None), the
    filter and object, the display fields (``exp`` / ``gain`` / ``temp``) and
    the *numeric* metadata used for calibration matching (``exp_s``,
    ``gain_v``, ``temp_v``, ``binning``, ``dims``).  Merging classification
    and summary into a single pass halves the header reads, which matters on
    a cloud-synced folder with hundreds of frames.

    ``is_light`` is kept as a convenience alias for ``kind == "light"``.
    """
    out = {"kind": None, "is_light": False, "filter": NO_FILTER, "object": "",
           "exp": "", "gain": "", "temp": "", "exp_s": 0.0,
           "gain_v": None, "temp_v": None, "binning": 1, "dims": None}
    header = _read_header(path)
    parts = [p.lower() for p in os.path.normpath(path).split(os.sep)]

    if header is None:
        return out

    out["object"] = _clean_token(header.get("OBJECT"))

    # A 3-channel (colour) image is never a mono frame — e.g. a colour
    # composite that ended up in the tree.  Reject it outright.
    try:
        if (int(header.get("NAXIS", 0)) >= 3
                and int(header.get("NAXIS3", 1)) > 1):
            out["filter"] = ""
            return out
    except (ValueError, TypeError):
        pass

    try:
        out["dims"] = (int(header.get("NAXIS1", 0)),
                       int(header.get("NAXIS2", 0)))
    except (ValueError, TypeError):
        pass
    for key in ("XBINNING", "BINNING", "XBIN"):
        if key in header:
            try:
                out["binning"] = int(float(header[key]))
            except (ValueError, TypeError):
                pass
            break

    # IMAGETYP is authoritative; the N.I.N.A. folder names are the fallback
    # for files that carry no type keyword.
    out["kind"] = (_classify_kind(_clean_token(header.get("IMAGETYP")))
                   or _classify_path(parts))
    out["is_light"] = out["kind"] == KIND_LIGHT

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
            out["gain_v"] = int(float(header["GAIN"]))
            out["gain"] = f"G{out['gain_v']}"
        except (ValueError, TypeError):
            pass
    for key in ("CCD-TEMP", "CCD_TEMP", "SET-TEMP"):
        if key in header:
            try:
                out["temp_v"] = float(header[key])
                out["temp"] = f"{out['temp_v']:.0f}C"
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

    def __init__(self, root: str, library: str = ""):
        super().__init__()
        self._root = root
        self._library = library

    def _scan(self, root: str) -> tuple[list, int]:
        """Collect FITS paths under `root`; also count unsupported files."""
        found, skipped = [], 0
        for dirpath, dirs, files in os.walk(root):
            # Prune our own output folder so previously-generated masters,
            # composites and work files are never re-ingested as lights.
            dirs[:] = [d for d in dirs if d != STACKS_DIRNAME]
            for name in files:
                if name.startswith("."):
                    continue
                if _is_fits(name):
                    found.append(os.path.join(dirpath, name))
                elif name.lower().endswith(UNSUPPORTED_EXTS):
                    skipped += 1
        return found, skipped

    def _sibling_calib_paths(self) -> list:
        """Find calibration frames stored BESIDE the target folder.

        Covers the classic N.I.N.A. layout `DATE\\IMAGETYPE\\TARGET\\FILTER`,
        where FLAT/DARKFLAT sit next to LIGHT rather than inside the selected
        target folder.  Walks up at most three levels and stops at the first
        level that actually holds a calibration folder, so it can never reach
        far enough to hoover up other nights or other targets wholesale.
        """
        out: list = []
        cur = os.path.normpath(self._root)
        for _ in range(3):
            parent = os.path.dirname(cur)
            if not parent or parent == cur:
                break
            try:
                entries = os.listdir(parent)
            except OSError:
                break
            hits = [os.path.join(parent, d) for d in entries
                    if _classify_path([d]) in
                    (KIND_FLAT, KIND_DARKFLAT, KIND_DARK, KIND_BIAS)
                    and os.path.isdir(os.path.join(parent, d))]
            if hits:
                for h in hits:
                    found, _ = self._scan(h)
                    out.extend(found)
                break               # first level with calibration wins
            cur = parent
        return out

    def run(self) -> None:
        try:
            all_fits, unsupported = self._scan(self._root)
            in_target = set(all_fits)

            # Calibration frames may live beside the target (old layout) and,
            # for darks / bias, in the central library.
            extra = self._sibling_calib_paths()
            if self._library and os.path.isdir(self._library):
                lib_found, lib_skipped = self._scan(self._library)
                extra += lib_found
                unsupported += lib_skipped
            # Frames from outside the target tree may ONLY contribute
            # calibration.  A library or sibling folder holding anything
            # tagged LIGHT would otherwise be stacked into this target --
            # and its OBJECT name would raise a bogus multiple-target
            # warning on top.
            outside = set()
            for p in extra:
                if p not in in_target:
                    all_fits.append(p)
                    outside.add(p)

            total = len(all_fits)
            if total == 0:
                self.failed.emit(
                    "No FITS files were found anywhere under the selected "
                    "folder.  Make sure the light frames have finished syncing.")
                return

            groups: dict[str, dict] = {}
            # Calibration frames, grouped so a master can be built per set:
            #   flats / darkflats -> by filter (they are filter-specific)
            #   darks / bias      -> by signature (exp, gain, binning, dims)
            calib: dict[str, dict] = {KIND_FLAT: {}, KIND_DARKFLAT: {},
                                      KIND_DARK: {}, KIND_BIAS: {}}
            objects: set[str] = set()
            target = ""
            stray_lights = 0
            for i, path in enumerate(sorted(all_fits)):
                if self.isInterruptionRequested():
                    return              # window is closing; drop the scan
                if i % 5 == 0 or i == total - 1:
                    self.progress.emit(
                        int(5 + 90 * (i + 1) / total),
                        f"Reading headers... {i + 1}/{total}")
                info = _inspect(path)          # one header read per file
                kind = info["kind"]

                if kind in calib:
                    # Flats belong to a filter; darks/bias to a signature --
                    # darks additionally split by temperature (see
                    # _calib_signature).
                    key = (info["filter"] if kind in (KIND_FLAT, KIND_DARKFLAT)
                           else _calib_signature(
                               info, with_temp=(kind == KIND_DARK)))
                    grp = calib[kind].setdefault(
                        key, {"files": [], "info": info,
                              "date": _path_date(path)})
                    grp["files"].append(path)
                    continue

                if kind != KIND_LIGHT:
                    continue
                if path in outside:
                    # A light frame in the library or a sibling calibration
                    # folder: not part of this target's data, so it is
                    # counted and dropped, never stacked.
                    stray_lights += 1
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
                    {"files": [], "sample": {}, "exp_total": 0.0,
                     "info": info, "dates": set(), "exps": set()})
                g["files"].append(path)
                g["exp_total"] = g.get("exp_total", 0.0) + info["exp_s"]
                g["dates"].add(_path_date(path))
                # Dark matching uses ONE representative frame per filter, so
                # a filter holding two different exposures has to be flagged.
                g["exps"].add(round(float(info["exp_s"]), 3))
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
            for g in groups.values():
                g["dates"] = sorted(d for d in g["dates"] if d)
                g["exps"] = sorted(g["exps"])

            self.progress.emit(100, "Analysis complete.")
            self.finished.emit(
                {"groups": groups, "target": target, "total": total,
                 "in_target": len(in_target), "outside": len(outside),
                 "stray_lights": stray_lights,
                 "objects": sorted(objects), "calib": calib,
                 "unsupported": unsupported})
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
                 out_dir: str, ext: str, opts: dict,
                 calib: dict | None = None):
        super().__init__()
        self.siril = siril
        self._groups = groups
        self._target = target
        self._out_dir = out_dir
        self._ext = ext or ".fit"
        self._opts = opts
        # Calibration frames found by the analysis, grouped by kind.
        self._calib = calib or {}
        # Built masters: {kind: {key: path}} plus a note of where each came
        # from, so the report can be honest about what was applied.
        self._masters: dict = {}
        # filter -> human-readable list of the masters applied to it.
        self._calib_notes: dict = {}
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
        # The rejection algorithm that really ran, per filter.  Recomputing
        # it in the report would hide a fallback (see _stack).
        self._rej_labels: dict = {}
        # filter -> (frame count the quality filters were decided on,
        # whether they were actually handed to seqapplyreg).  Recording it
        # is not optional: registration can drop frames afterwards, so the
        # count in _stacked_counts is no longer the one the decision was
        # made on, and re-deriving from it flips the answer.
        self._qf_decision: dict = {}
        # Filters left unstacked because the palette does not read them.
        self._skipped_by_palette: list = []
        # filter -> registration options that could not be honoured.
        # Empty is the normal case; a non-empty entry means the master
        # differs from what the options say, and the report must not
        # describe it as if they had run.
        self._reg_degraded: dict = {}
        # Set when drizzle ran on a set too small to fill its finer grid.
        self._drizzle_warned = False
        # Siril's data directory, asked for once (None = not asked yet).
        self._spcc_root_cache: str | None = None
        # Set when the user stopped the run.  Everything downstream of
        # stacking is then skipped: the channel set is incomplete, so a
        # colour image built from it would not be the image they asked for.
        self._aborted = False
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

    def _count_seq_frames(self, process_dir: str, seq: str) -> int:
        """How many frames a Siril sequence really holds on disk.

        Siril numbers its exports ``<seq>_00001.fit``, ``<seq>_00002.fit``
        ... and simply leaves out the ones it could not process, so counting
        the files is an exact answer where parsing the console output would
        be guesswork.  Returns 0 when the directory cannot be read, which
        callers must treat as "unknown", never as "none".
        """
        pat = re.compile(re.escape(seq) + r"_\d+" + re.escape(self._ext) + "$",
                         re.IGNORECASE)
        try:
            return sum(1 for f in os.listdir(process_dir) if pat.match(f))
        except OSError as exc:
            _log_swallowed(exc)
            return 0

    def _register(self, seq: str, filt: str) -> str:
        """Register the sequence; return the resulting sequence name."""
        drizzle = self._opts.get("drizzle", 1)
        # -framing=min keeps only the area covered by ALL sub-frames, so the
        # master has no ragged low-coverage border to crop later.  max keeps
        # the full field (with those partial edges) when the user prefers it.
        framing = "min" if self._opts.get("crop_edges", True) else "max"
        apply_args = ["seqapplyreg", seq, f"-framing={framing}"]
        if drizzle and drizzle > 1:
            # Documented order: -scale= is a top-level option and comes
            # BEFORE -drizzle, whose own sub-options are -pixfrac / -kernel /
            # -flat.  Passing -scale inside the drizzle group risks being
            # parsed as an unknown drizzle argument.
            apply_args += [f"-scale={drizzle}", "-drizzle",
                           "-pixfrac=1.0", "-kernel=square"]
        n_in = self._current_n_frames
        if drizzle and drizzle > 1 and n_in < DRIZZLE_MIN_FRAMES:
            # Drizzle spreads each sub's flux over a finer grid; without
            # enough dithered frames that grid stays unevenly filled and the
            # master ends up noisier than an undrizzled one.
            self._emit(
                f"  Drizzle {drizzle}x on only {n_in} frame(s): drizzle "
                f"wants roughly {DRIZZLE_MIN_FRAMES}+ *dithered* subs to "
                "fill the finer grid evenly.  Below that it usually adds "
                "noise instead of resolution — consider turning it off.",
                LogColor.SALMON)
            self._drizzle_warned = True
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

        # Star-based two-pass registration.  The two commands get their own
        # scopes because they fail for unrelated reasons, and only one of
        # those reasons has anything to do with two-pass support.  Sharing
        # one `try` diagnosed a frame that the cloud-sync folder had not
        # finished materialising as "2-pass registration unavailable" --
        # registration had in fact just succeeded on all six frames -- and
        # then retried with a command that quietly drops framing, drizzle
        # and every quality filter.
        try:
            self._cmd("register", seq, "-2pass")
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  2-pass registration unavailable ({exc}); "
                "using single-pass global registration.", LogColor.SALMON)
            self._single_pass(seq, filt, drizzle)
            return f"r_{seq}"
        try:
            self._cmd(*apply_args)
        except (CommandError, DataError, SirilError) as exc:
            # Registration succeeded, so this is not about two-pass.  Retry
            # without the optional extras -- an older Siril may not know
            # -framing= or a -filter- flag -- and only then give up.
            self._emit(
                f"  Applying the registration failed ({exc}); retrying "
                "without framing and quality filters.", LogColor.SALMON)
            extras = [a for a in apply_args[2:] if not a.startswith("-scale=")
                      and a not in ("-drizzle", "-pixfrac=1.0",
                                    "-kernel=square")]
            self._cmd(*[a for a in apply_args if a not in extras])
            self._note_reg_degraded(filt, extras)
        return f"r_{seq}"

    def _single_pass(self, seq: str, filt: str, drizzle: int) -> None:
        """Register and export in one step, when two-pass is unavailable.

        `register` carries -scale= and -drizzle but knows neither -framing=
        nor any -filter-* option, so this path cannot honour the crop or the
        quality filters however they are set.  It says so and records it,
        because a report that still claimed them would describe a master
        that was never built that way.
        """
        args = ["register", seq]
        if drizzle and drizzle > 1:
            args += [f"-scale={drizzle}", "-drizzle",
                     "-pixfrac=1.0", "-kernel=square"]
        self._cmd(*args)
        self._note_reg_degraded(
            filt, ["-framing=", "quality filters"],
            "single-pass `register` supports neither")

    def _note_reg_degraded(self, filt: str, dropped: list,
                           why: str = "this Siril rejected") -> None:
        """Record registration options that did not actually run.

        The quality-filter decision is rewritten to "did not fire" so the
        report cannot go on naming filters that never reached Siril.
        """
        if not dropped:
            return
        names = [d for d in dropped if not d.startswith("-scale=")]
        self._reg_degraded[filt] = names
        if any("filter" in d for d in names):
            n, _fired = self._qf_decision.get(filt,
                                              (self._current_n_frames, True))
            self._qf_decision[filt] = (n, False)
        self._emit(f"  {filt}: {why} {', '.join(names)} — the master was "
                   "built without them.", LogColor.SALMON)

    def _effective_frame_count(self, n_frames: int) -> int:
        """Frames expected to survive the quality filters.

        The rejection algorithm must be picked for the population that is
        actually integrated: filtering 21 frames down to the best 90% leaves
        18, which wants Winsorized sigma, not the linear fit that 21 frames
        would suggest.

        Derived from the arguments _quality_filter_args() really emits, so a
        filter that was dropped there (too few frames left, 100%, k-sigma)
        can never shrink the count here -- the two must not disagree.

        This is an UPPER bound, not a prediction.  With several percentage
        filters active the survivors are those that pass all of them, which
        is at most the strictest one alone -- hence `min`.  With k-sigma it
        returns the full count, because how many frames lie beyond k sigma
        is Siril's call.  Callers must present the result as a bound (the
        report marks it with a tilde or a <=), never as a measurement.
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

    def _stack(self, seq: str, out_name: str, n_frames: int,
               filt: str = "") -> None:
        # Choose rejection for the number of frames that will really be
        # integrated, not the number that was staged.
        n_eff = self._effective_frame_count(n_frames)
        rej_tokens, rej_label = _rejection_args(
            n_eff, self._opts.get("rejection", True))

        def _tail() -> list:
            """Everything after the rejection tokens (identical on retry)."""
            args = ["-norm=addscale"]
            if self._opts.get("output_norm", True):
                args += ["-output_norm"]
            # Frame weighting lifts the better subs -- only meaningful once
            # there are a few frames left to weight.
            if self._opts.get("weighting", True) and n_eff >= 3:
                args += [f"-weight={_weight_token(self._opts)}"]
            # Frame quality filtering already happened at registration time
            # (see _quality_filter_args), so the sequence handed to stack
            # only contains the frames that passed; -filter-included keeps
            # it that way.  Ask what registration was TOLD, not what
            # `n_frames` would imply -- registration may have dropped
            # frames since, and re-deriving would flip the answer.
            _n, fired = self._qf_decision.get(
                filt, (n_frames, bool(self._quality_filter_args(n_frames))))
            if fired:
                args += ["-filter-included"]
            if self._opts.get("rejmap", False):
                args += ["-rejmap"]
            return args + ["-32b", f"-out={out_name}"]

        args = ["stack", seq] + rej_tokens + _tail()
        n_txt = (f"n={n_frames}" if n_eff == n_frames
                 else f"n≈{n_eff} of {n_frames} after filtering")
        self._emit(f"  Rejection: {rej_label} ({n_txt})", LogColor.BLUE)
        self._emit("  " + " ".join(args), LogColor.BLUE)
        try:
            self._cmd(*args)
        except (CommandError, DataError, SirilError) as exc:
            # GESDT is the newest of the rejection algorithms, so a Siril
            # build that does not know the token would fail the whole
            # filter.  Retry once with the tier below rather than lose the
            # stack.  Every other failure re-raises untouched: it is far
            # more likely a real problem than an unknown token, and quietly
            # switching algorithms would hide it.
            fallback = _rejection_fallback(rej_tokens)
            if fallback is None:
                raise
            fb_tokens, fb_label = fallback
            self._emit(
                f"  Rejection '{rej_label}' was refused ({exc}); retrying "
                f"with {fb_label}.", LogColor.SALMON)
            rej_label = fb_label
            self._cmd(*(["stack", seq] + fb_tokens + _tail()))
        # The report must name the algorithm that really ran, not the one
        # that was preferred.
        if filt:
            self._rej_labels[filt] = rej_label

    # -- per-filter stacking ---------------------------------------------
    # -- calibration ------------------------------------------------------
    def _calib_dir(self) -> str:
        d = os.path.join(self._out_dir, CALIB_DIRNAME)
        os.makedirs(d, exist_ok=True)
        return d

    def _master_name(self, kind: str, info: dict, filt: str = "",
                     suffix: str = "") -> str:
        """Descriptive master filename, built from the frame's own header.

        The matching itself runs on headers, but a name like
        `M101_RED_-10C_120s_G100_flat` makes the folder readable at a glance
        -- borrowed from Naztronomy-Mono_PP, where it proved its worth.

        The name must distinguish everything the grouping distinguishes:
        two groups that collapse onto one name would make the second reuse
        the first one's cached file, i.e. calibrate with the wrong master.
        Binning is therefore part of the name whenever it is not 1, and
        `suffix` carries anything the caller needs to keep apart (the flat
        date restriction, or a tie-break between otherwise identical sets).
        """
        bits = [_safe(self._target)]
        if filt and filt != NO_FILTER:
            bits.append(_safe(filt))
        if info.get("temp"):
            bits.append(_safe(info["temp"]))
        if info.get("exp"):
            bits.append(_safe(info["exp"]))
        if info.get("gain"):
            bits.append(_safe(info["gain"]))
        if int(info.get("binning", 1) or 1) != 1:
            bits.append(f"bin{int(info['binning'])}")
        bits.append(kind)
        if suffix:
            bits.append(_safe(suffix))
        return "_".join(b for b in bits if b)

    def _stack_calib_group(self, kind: str, grp: dict, out_name: str,
                           bias_master: str = "") -> str | None:
        """Turn one calibration group into a master; return its path.

        Three shapes are handled:
          * exactly one file  -> it already IS the master (Naztronomy's rule);
            no stacking, just adopt it.
          * flats             -> calibrated against bias/dark-flat when one is
            available, then stacked with multiplicative normalisation.
          * darks / bias      -> plain stack, no normalisation.
        Returns None (and logs) if anything goes wrong -- calibration must
        never abort a run.
        """
        files = grp.get("files") or []
        dest = os.path.join(self._calib_dir(), out_name + self._ext)
        if os.path.exists(dest):
            self._emit(f"  Reusing master {kind}: {os.path.basename(dest)}",
                       LogColor.GREEN)
            return dest

        if len(files) == 1:
            # A single frame is a ready-made master, not something to stack.
            try:
                shutil.copy2(files[0], dest)
                self._emit(
                    f"  {kind}: single file treated as a ready master "
                    f"({os.path.basename(files[0])}).", LogColor.BLUE)
                return dest
            except OSError as exc:
                self._emit(f"  {kind}: could not copy master ({exc}).",
                           LogColor.SALMON)
                return None

        work = os.path.join(self._out_dir, WORK_DIRNAME, "calib", out_name)
        stage = os.path.join(work, kind)
        if os.path.isdir(work):
            shutil.rmtree(work, ignore_errors=True)
        os.makedirs(stage, exist_ok=True)
        staged = 0
        for i, src in enumerate(files):
            try:
                dst = os.path.join(stage, f"{i:04d}_{os.path.basename(src)}")
                if os.path.lexists(dst):
                    os.remove(dst)
                try:
                    os.symlink(os.path.abspath(src), dst)
                except (OSError, NotImplementedError):
                    shutil.copy2(src, dst)
                staged += 1
            except Exception as exc:
                _log_swallowed(exc)
        if staged < 2:
            self._emit(f"  {kind}: only {staged} usable frame(s), skipped.",
                       LogColor.SALMON)
            return None

        try:
            self._cmd("cd", f'"{stage}"')
            self._cmd("link", kind, "-out=../process")
            self._cmd("cd", "../process")
            seq = kind
            if kind in (KIND_FLAT,):
                # Flats must be offset-corrected before normalising, else the
                # division carries the sensor pedestal into the lights.
                if bias_master:
                    self._cmd("calibrate", kind, f"-bias={bias_master}")
                    seq = f"pp_{kind}"
                    self._emit("    flats offset-corrected with "
                               f"{os.path.basename(bias_master)}",
                               LogColor.BLUE)
                else:
                    # No bias / dark-flat: fall back to Siril's synthetic
                    # offset, and if even that is refused, stack raw.
                    try:
                        self._cmd("calibrate", kind, '-bias="=64*$OFFSET"')
                        seq = f"pp_{kind}"
                        self._emit("    flats offset-corrected with a "
                                   "synthetic bias (=64*$OFFSET)",
                                   LogColor.BLUE)
                    except (CommandError, DataError, SirilError):
                        self._emit("    no bias available — flats stacked "
                                   "uncorrected.", LogColor.SALMON)
                norm = "-norm=mul"
            else:
                norm = "-nonorm"
            self._cmd("stack", seq, "rej", "3", "3", norm,
                      "-out=" + out_name)
            produced = os.path.join(work, "process", out_name + self._ext)
            if not os.path.exists(produced):
                self._emit(f"  {kind}: stacking produced no master.",
                           LogColor.RED)
                return None
            shutil.copy2(produced, dest)
            self._emit(f"  Built master {kind} from {staged} frames -> "
                       f"{os.path.basename(dest)}", LogColor.GREEN)
            return dest
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  {kind}: master build failed ({exc}).", LogColor.RED)
            return None
        finally:
            try:
                self._cmd("cd", f'"{self._out_dir}"')
                self._cmd("close")
            except (CommandError, DataError, SirilError):
                pass

    def _build_calib_masters(self) -> None:
        """Build every master the run can use, once, before stacking starts."""
        if not self._opts.get("calibrate", True) or not any(
                (self._calib or {}).values()):
            return
        c = self._calib
        self._masters = {KIND_BIAS: None, KIND_DARKFLAT: None,
                         KIND_DARK: {}, KIND_FLAT: {}}

        # 1) Bias and dark-flat first: the flats need one of them.
        for kind in (KIND_BIAS, KIND_DARKFLAT):
            groups = c.get(kind) or {}
            if not groups:
                continue
            # Bias keys are signature tuples that may contain None, which
            # plain sorted() refuses to compare; dark-flat keys are filter
            # names.  _sig_sort_key handles both.
            key = sorted(groups, key=lambda k: _sig_sort_key(k)
                         if isinstance(k, tuple) else ((False, k),))[0]
            if len(groups) > 1:
                self._emit(
                    f"  {kind}: {len(groups)} sets found, using the first.",
                    LogColor.SALMON)
            grp = groups[key]
            self._masters[kind] = self._stack_calib_group(
                kind, grp, self._master_name(kind, grp["info"]))

        # Dark-flats are the better offset reference for flats; bias is the
        # fallback.  (Both carry the pedestal; the dark-flat also carries the
        # flat exposure's dark signal.)
        flat_offset = self._masters.get(KIND_DARKFLAT) or \
            self._masters.get(KIND_BIAS) or ""

        # 2) One master flat per filter.  Optionally restricted to the nights
        #    the lights of that filter were actually taken.
        by_date = self._opts.get("flats_by_date", False)
        for filt, grp in (c.get(KIND_FLAT) or {}).items():
            use = dict(grp)
            # The restriction must reach the master's NAME as well: without
            # it a per-night master and a pooled one share a filename, and
            # the cache would hand back the pooled one -- silently ignoring
            # the option the user just switched on.
            night_tag = ""
            if by_date:
                nights = set((self._groups.get(filt) or {}).get("dates") or [])
                if nights:
                    kept = [p for p in grp["files"] if _path_date(p) in nights]
                    dropped = len(grp["files"]) - len(kept)
                    if kept and dropped:
                        use = dict(grp, files=kept)
                        night_tag = "-".join(sorted(nights))
                        self._emit(
                            f"  {filt}: using {len(kept)} flat(s) from the "
                            f"matching night(s); {dropped} from other dates "
                            "ignored.", LogColor.BLUE)
                    elif not kept:
                        self._emit(
                            f"  {filt}: no flats from the same night — "
                            "falling back to all available flats.",
                            LogColor.SALMON)
            m = self._stack_calib_group(
                KIND_FLAT, use,
                self._master_name(KIND_FLAT, grp["info"], filt, night_tag),
                flat_offset)
            if m:
                self._masters[KIND_FLAT][filt] = m

        # 3) One master dark per signature.  Two signatures that render to
        #    the same filename would share a cache entry, so the collision is
        #    broken deterministically (sorted order) instead of silently.
        claimed: dict = {}
        for sig in sorted((c.get(KIND_DARK) or {}), key=_sig_sort_key):
            grp = c[KIND_DARK][sig]
            name = self._master_name(KIND_DARK, grp["info"])
            n = claimed.get(name, 0) + 1
            claimed[name] = n
            if n > 1:
                self._emit(
                    f"  dark: a second set shares the name {name} — storing "
                    f"it as {name}_{n}.", LogColor.SALMON)
                name = f"{name}_{n}"
            m = self._stack_calib_group(KIND_DARK, grp, name)
            if m:
                self._masters[KIND_DARK][sig] = (m, grp["info"])

    def _calibrate_args(self, filt: str, light_info: dict) -> list:
        """Build the `calibrate` arguments for one filter, or [] for none."""
        if not self._opts.get("calibrate", True) or not self._masters:
            return []
        args: list = []
        used: list = []

        dark = None
        for _sig, (path, info) in (self._masters.get(KIND_DARK) or {}).items():
            if _signature_matches(info, light_info):
                dark = path
                break
        if dark:
            args.append(f"-dark={dark}")
            used.append(f"dark={os.path.basename(dark)}")
            # The match was made against ONE representative light.  If the
            # filter mixes exposures, the dark is right for only some of
            # them -- say so rather than let it pass unnoticed.
            exps = (self._groups.get(filt) or {}).get("exps") or []
            if len(exps) > 1:
                self._emit(
                    f"  {filt}: frames use {len(exps)} different exposures "
                    f"({', '.join(f'{e:g}s' for e in exps)}); the dark "
                    f"matches {light_info.get('exp') or 'the first frame'} "
                    "only. Stack the exposures separately for a clean "
                    "result.", LogColor.SALMON)
            if self._opts.get("cosmetic", True):
                args += ["-cc=dark", "3", "3"]
        elif self._masters.get(KIND_DARK):
            self._emit(
                f"  {filt}: no dark matches these lights (exposure, gain, "
                "temperature, binning or image size differ) — continuing "
                "without one.", LogColor.SALMON)

        flat = (self._masters.get(KIND_FLAT) or {}).get(filt)
        if flat:
            args.append(f"-flat={flat}")
            used.append(f"flat={os.path.basename(flat)}")

        # Bias goes to the lights ONLY when no dark is used: a master dark
        # already contains the offset, so subtracting bias as well would
        # remove it twice.  Lc = (L - D) / (F - O).
        if not dark and self._masters.get(KIND_BIAS):
            bias = self._masters[KIND_BIAS]
            args.append(f"-bias={bias}")
            used.append(f"bias={os.path.basename(bias)}")

        if used:
            self._calib_notes[filt] = ", ".join(used)
        return args

    def _unused_by_palette(self, filters: list) -> set:
        """Filters to leave unstacked, when the user asked for that.

        Off by default, because a master that was never built cannot be
        reused for a different palette later.  Skipping is also refused
        whenever the palette has a channel it cannot fill: the composite
        stops there in any case, and the filters that would be left out
        are the only thing that lets the night be salvaged with a
        different palette.  That check doubles as the guarantee that at
        least two masters survive, which the cross-filter alignment needs
        -- one filter can fill at most two of R/G/B (OIII under HOO), so a
        palette with all three channels filled always names two or more.

        The side effect is the point as much as the time saved.  Siril's
        two-pass registration picks the alignment reference itself, from
        whatever is in the sequence -- `setref` cannot override it, its own
        help says -2pass "adds a preliminary pass ... to find a good
        reference image".  With every filter in that pool a broadband
        master usually wins, and the narrowband channels then have to match
        a spectrally unrelated frame: on one M 16 run OIII matched on 12
        star pairs and Ha on 22, against 188-476 for the broadband masters.
        Leaving the unused filters out puts only the composite's own
        channels in the pool, so the reference is one of them.
        """
        if not self._opts.get("palette_only", False):
            return set()
        if not self._opts.get("compose", False):
            # Greying the box out when composition is off is cosmetic; a
            # saved preset can still arrive with both set.  Without a
            # composite there is no palette reading anything, so skipping
            # would drop masters on behalf of a picture that is never made.
            self._emit(
                "  Stacking every filter: 'Stack only the filters this "
                "palette uses' needs a colour composite to have a palette "
                "to go by, and that is switched off.", LogColor.SALMON)
            return set()
        wanted = _palette_filters(self._opts, filters)
        if not wanted:
            self._emit(
                "  Stacking every filter: the channel mapping does not name "
                "any of the discovered filters, so there is nothing reliable "
                "to skip.", LogColor.SALMON)
            return set()
        skip = {f for f in filters if f not in wanted}
        if not skip:
            return set()
        # Refuse when the palette cannot be completed anyway.  Skipping
        # would then trade six usable masters for two and no picture --
        # the composite is going to stop at the empty channel either way,
        # and the filters left out are the only thing that would let the
        # user salvage the night with another palette.
        palette = self._opts.get("compose_palette", "RGB")
        if palette == "Auto":
            palette = _detect_palette(filters)
        empty = _unfillable_channels(sorted(wanted), palette)
        if empty:
            self._emit(
                f"  Stacking every filter: {palette} cannot fill "
                f"{', '.join(empty)} from the filters found, so the "
                "composite will stop there anyway — the other masters are "
                "worth more than the time saved.", LogColor.SALMON)
            return set()
        self._skipped_by_palette = sorted(skip)
        self._emit(
            f"Stacking {len(wanted)} of {len(filters)} filters: "
            f"{', '.join(sorted(wanted))}.  "
            f"{', '.join(sorted(skip))} "
            + _plural(skip, "is not read", "are not read")
            + " by this palette, and leaving "
            + _plural(skip, "it", "them")
            + " out also keeps the alignment reference among the channels "
            "that end up in the picture.", LogColor.BLUE)
        return skip

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
        skip = self._unused_by_palette(filters)
        if skip:
            filters = [f for f in filters if f not in skip]
        n_f = len(filters)

        for fi, filt in enumerate(filters):
            # Cooperative abort: a Siril command cannot be interrupted
            # mid-flight, so we stop between filters -- the last finished
            # master stays valid.
            if self.isInterruptionRequested():
                self._aborted = True
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
                # anything else needs convert.  Discovery only ever yields
                # FITS_EXTS today, so the convert branch is dead in practice
                # -- it is kept deliberately, so that widening FITS_EXTS to a
                # raw format does not silently produce a broken `link`.
                conv = "link" if _is_fits_like(_fits_ext(files[0])) \
                    else "convert"
                self._cmd(conv, "lights", "-out=../process")
                self._cmd("cd", "../process")

                seq = "lights"
                # Calibration comes first: everything downstream (background,
                # registration, stacking) should work on corrected pixels.
                cal_args = self._calibrate_args(
                    filt, self._groups[filt].get("info") or {})
                if cal_args:
                    self._emit("  Calibrating: calibrate lights "
                               + " ".join(cal_args), LogColor.BLUE)
                    self._cmd("calibrate", seq, *cal_args)
                    seq = f"pp_{seq}"

                if self._opts.get("bg_extract", False):
                    self._emit("  Extracting background gradient...",
                               LogColor.BLUE)
                    self._cmd("seqsubsky", seq, "1", "-samples=10")
                    seq = f"bkg_{seq}"

                self._current_n_frames = n_linked
                # Record what seqapplyreg is about to be told, before
                # registration can change the frame count under us.
                self._qf_decision[filt] = (
                    n_linked, bool(self._quality_filter_args(n_linked)))
                self._emit("  Registering frames...", LogColor.BLUE)
                seq = self._register(seq, filt)

                # Registration itself can drop frames -- a sub with no
                # detectable stars (clouds, a passing veil) simply fails to
                # match and Siril excludes it.  Counting the files it really
                # exported is the only reliable number: everything after
                # this point (rejection tier, weighting, the report) must be
                # based on what is actually going into the stack, not on
                # what went in at the top.
                n_reg = self._count_seq_frames(
                    os.path.join(work, "process"), seq)
                if n_reg and n_reg < n_linked:
                    lost = n_linked - n_reg
                    self._emit(
                        f"  Registration dropped {lost} of {n_linked} "
                        f"frame(s) — {n_reg} will be integrated. Frames "
                        "without enough detectable stars (clouds, haze) "
                        "cannot be aligned.", LogColor.SALMON)
                    if n_reg < MIN_STACK_FRAMES:
                        self._emit(
                            f"  Only {n_reg} frame(s) left for {filt}: too "
                            "few for outlier rejection to mean much. Treat "
                            "this channel as provisional.", LogColor.SALMON)
                n_stack = n_reg or n_linked
                self._stacked_counts[filt] = (
                    n_stack, self._effective_frame_count(n_stack))

                # Full-frame (uncropped) per-channel master.  Kept in
                # masters/ as *_fullframe; the aligned/cropped version is
                # produced later by _align_masters as TARGET_FILTER.fit.
                out_name = f"{_safe(self._target)}_{self._tok(filt)}_fullframe"
                self._emit("  Integrating...", LogColor.BLUE)
                self._stack(seq, out_name, n_stack, filt)

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
                    # Rescue the rejection maps: Siril writes them next to
                    # the stack output inside _work/, which the user never
                    # opens and which "Delete _work/" removes.
                    if self._opts.get("rejmap", False):
                        self._collect_rejmaps(
                            os.path.join(work, "process"), out_name)
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
          "frames. The script stacked each filter"
          + (", aligned the channels, and combined them into a colour image."
             if comp_name else
             " and aligned the channels; **no colour image was produced** "
             "this run \u2014 see 3.3 for why.")
          + " **Every image here is still _linear_** (not stretched) — the "
          "final, creative processing is up to you and is described in "
          "**[`todo.md`](todo.md)**.")
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
        # Only the channels THIS run aligned share a grid.  Aligned masters
        # of skipped filters are still on disk from an earlier run, and
        # -framing=min gave that run a different canvas -- so the folder
        # now holds two grids that must not be combined.
        stale = sorted(
            f for f in self._skipped_by_palette
            if os.path.exists(os.path.join(
                self._out_dir, MASTERS_DIRNAME,
                f"{_safe(self._target)}_{self._tok(f)}{self._ext}")))
        A("| `masters/…_<FILTER>_fullframe.fit` | The same channel at "
          "**full, uncropped** size. |")
        A("| `_work/` | All intermediate files. **Safe to delete** any "
          "time. |")
        A("| `output.md` | This report — what the script did, step by step. |")
        A("| `todo.md` | Step-by-step guide for the final image processing. |")
        if self._calib_notes:
            A(f"| `{CALIB_DIRNAME}/` | The calibration masters that were "
              "built and applied. |")
        if opts.get("rejmap"):
            A(f"| `{QA_DIRNAME}/` | Rejection maps — which pixels the "
              "integration threw away. |")
        # After the LAST row: a blockquote between two rows ends the table
        # and orphans everything below it.
        if stale:
            A("")
            A("> ⚠️ `masters/` also holds aligned "
              + ", ".join(stale)
              + _plural(stale, " from an **earlier run**.  That one "
                               "carries the grid of the run that wrote it",
                        " from **earlier runs**.  Each carries the grid of "
                        "the run that wrote it")
              + ", which need not be this one\u2019s or each "
              "other\u2019s — `-framing=min` crops to the intersection of "
              "whatever was aligned together, and every run aligns the set "
              "its palette asked for.  Combining them with the channels "
              "above would mismatch.  Re-run with *Stack only the filters "
              "this palette uses* switched **off** to put every channel back "
              "on one grid.")
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
        any_estimated = False
        # Filters whose master came from an earlier run: nothing was staged,
        # filtered or integrated for them THIS time, so quoting a frame count
        # and a rejection algorithm here would describe a run that did not
        # happen.
        reused_set = (set(self._groups) if reused
                      else set(partial_reuse or ()))
        # A filter only has a frame count worth quoting if it actually came
        # out of this run.  Filters that were skipped (too few usable
        # frames), that failed mid-pipeline, or that the abort never reached
        # leave no _stacked_counts entry -- and the old fallback then
        # reported them as fully stacked.
        produced = set(final_paths or ())
        k_sigma = opts.get("filter_mode") == "k-sigma"
        for filt in sorted(self._groups):
            g = self._groups[filt]
            n = len(g.get("files", []))
            total += n
            exp = g.get("exp_total", 0.0)
            if filt in reused_set:
                total_exp += exp
                A(f"| {filt} | {n} | _reused_ | {_format_duration(exp)} "
                  "| _(earlier run)_ |")
                continue
            if filt in self._skipped_by_palette:
                A(f"| {filt} | {n} | _not stacked_ | — | _the "
                  f"{opts.get('compose_palette', 'RGB')} palette does not "
                  "read this filter_ |")
                continue
            if filt not in produced:
                # A Siril message may contain a pipe, which would tear the
                # Markdown table apart.
                why = (errors.get(filt)
                       or "not reached — the run was stopped").replace(
                           "|", "\\|")
                A(f"| {filt} | {n} | _none_ | — | _{why}_ |")
                continue
            # Quote what was really integrated: blank frames and the quality
            # filters both shrink the set, and the rejection algorithm was
            # chosen for that smaller number.
            staged, effective = self._stacked_counts.get(filt, (n, n))
            # Prefer what _stack recorded: recomputing would hide a
            # rejection fallback.
            rej_label = self._rej_labels.get(filt)
            if not rej_label:
                _tok, rej_label = _rejection_args(
                    effective, opts.get("rejection", True))
            # Integration time must follow the frames that were really
            # integrated, not the ones that were merely found.
            exp_used = exp * effective / n if n else 0.0
            if k_sigma and self._quality_filter_args(staged):
                # k-sigma rejects "everything beyond k standard deviations":
                # how many frames that is only Siril knows, so the count is
                # an upper bound, never a measurement.
                any_reduced = True
                any_estimated = True
                used = f"**≤{effective}**"
            elif effective != n:
                any_reduced = True
                # Blank removal is a fact; what the quality filters keep is
                # Siril's call and may differ by a frame, so mark it as an
                # estimate rather than stating it as measured.
                est = effective < staged
                any_estimated = any_estimated or est
                used = f"**{'≈' if est else ''}{effective}**"
            else:
                used = str(effective)
            total_exp += exp_used
            A(f"| {filt} | {n} | {used} | {_format_duration(exp_used)} "
              f"| {rej_label} |")
        A("")
        A(f"**Total:** {total} light "
          + _plural(range(total), "frame", "frames") + " found across "
          + f"{len(self._groups)} "
          + _plural(self._groups, "filter", "filters") + " — "
          f"**{_format_duration(total_exp)}** integrated"
          + (" (reused masters counted with the frames they were built from)."
             if reused_set else "."))
        if any_reduced:
            A("")
            A("> The **Stacked** column is lower than **Found** where blank "
              "frames were dropped, **registration could not align a sub** "
              "(too few detectable stars — clouds or haze), or the quality "
              "filters removed frames.  The rejection algorithm was chosen "
              "for that smaller number."
              + ("  Rows reading *not stacked* were skipped on purpose — "
                 "see the note under 3.1." if self._skipped_by_palette
                 else ""))
        if any_estimated:
            A("")
            A("> Counts marked **≈** are what the quality filters are "
              "expected to keep; Siril decides frame by frame, so the real "
              "number can differ by one or two.  A **≤** marks a k-sigma "
              "filter, where how many frames fall outside k standard "
              "deviations is not predictable at all — that column is an "
              "upper bound, and so is the integration time beside it.")
        if self._blank_skipped:
            A("")
            A(f"> ⚠️ **{self._blank_skipped} blank/black frame(s)** were "
              "detected and left out of the stack (all-zero or dead-flat — "
              "e.g. a failed download or a closed flap).")
        if self._aborted:
            A("")
            A("> 🛑 **This run was stopped before it finished.** The masters "
              "listed above are complete and usable; the remaining filters "
              "were never stacked, and channel alignment, plate-solving and "
              "the colour image were skipped deliberately — combining an "
              "incomplete channel set would not have produced the image you "
              "asked for. Re-run with **Reuse existing masters** to stack "
              "only what is missing and then compose.")
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
            A(("For **every filter**, " if not self._skipped_by_palette
               else f"For the {len(produced)} filters that were stacked "
                    f"({', '.join(sorted(produced))}), ")
              + "the raw lights were turned into one master light:")
            A("")
            # The list of steps is conditional (calibration, per-sub
            # background), so the numbers come from a counter -- hard-coded
            # ones silently go wrong as soon as a step is added.
            _step = [0]

            def N() -> str:
                _step[0] += 1
                return f"{_step[0]}."

            if self._skipped_by_palette:
                A(N() + " **Filter selection** — *Stack only the filters "
                  "this palette uses* was on, so "
                  + ", ".join(self._skipped_by_palette)
                  + _plural(self._skipped_by_palette,
                            " was", " were")
                  + " left unstacked.  Besides the time saved, this "
                  "keeps the cross-filter alignment reference among the "
                  "channels that end up in the picture: Siril's two-pass "
                  "registration picks that reference itself, from whatever "
                  "masters are in the sequence, and a broadband one "
                  "normally wins — which leaves the narrowband channels "
                  "matching a spectrally unrelated frame.  Re-run with the "
                  "box off to build the missing masters for another "
                  "palette.")
            A(N() + " **Staging & linking** — the frames were linked into a "
              "Siril sequence (`link`). Compressed `.fits.fz` files are read "
              "directly, and nothing is ever debayered (this is a mono "
              "workflow)."
              + ((f" Blank / black frames were checked for — "
                  f"{self._blank_skipped} dropped."
                  if self._blank_skipped else
                  " Blank / black frames were checked for; none were found.")
                 if opts.get("skip_blank", True) else ""))
            if self._calib_notes:
                A(N() + " **Calibration** (`calibrate`) — the masters below "
                  "were applied to the lights, following "
                  "**Lc = (L − D) / (F − O)**. A master dark already contains "
                  "the bias, so bias is only subtracted separately when no "
                  "dark is used.")
                for filt in sorted(self._calib_notes):
                    A(f"    - **{filt}:** {self._calib_notes[filt]}")
                if opts.get("calib_library"):
                    A("    - Darks / bias were taken from the library "
                      f"`{opts['calib_library']}`; flats come from the "
                      "session next to the lights.")
                if opts.get("cosmetic", True):
                    A("    - Cosmetic correction (`-cc=dark 3 3`) was "
                      "requested — it only takes effect for filters that "
                      "actually got a matching dark.")
                if opts.get("flats_by_date"):
                    A("    - Flats were matched **per night** (only flats "
                      "from the same date folder as the lights were used).")
            if opts.get("bg_extract"):
                A(N() + " **Per-sub background** — a gradient was removed "
                  "from every individual sub before registration "
                  "(`seqsubsky`).")
            A(N()
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
                #
                # The test is "were arguments emitted for that channel",
                # i.e. the same source of truth seqapplyreg was given.
                # Inferring it from a shrunken frame count instead is wrong
                # in k-sigma mode, where the surviving count cannot be
                # predicted and therefore always equals the staged one.
                # _qf_decision records what registration was actually told,
                # and the count it was told it for.  _stacked_counts holds
                # what SURVIVED registration, which is a different number
                # and would give a different -- wrong -- answer here.
                qfd = self._qf_decision
                applied = [f for f, (_n, fired) in qfd.items() if fired]
                if applied:
                    where = (f"They applied to {', '.join(sorted(applied))} "
                             "(the filters with enough frames).")
                elif not qfd:
                    where = ("No channel was stacked this run, so they did "
                             "not run either.")
                elif all(n < FILTER_MIN_FRAMES
                         for n, _fired in qfd.values()):
                    where = (f"They did **not** apply this run — no filter "
                             f"reached {FILTER_MIN_FRAMES} frames, and on "
                             "shorter sets losing a sub costs more "
                             "signal-to-noise than the worst frame costs "
                             "sharpness.")
                else:
                    # Enough frames, yet nothing was emitted: the values
                    # themselves are the reason (100% keeps everything, and
                    # a setting that would leave fewer than
                    # MIN_STACK_FRAMES frames is refused).
                    where = ("They did **not** apply this run — at the "
                             "values above they would either keep every "
                             f"frame or leave fewer than {MIN_STACK_FRAMES} "
                             "frames to integrate.")
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
            A(N() + f" {frm}{drz_txt}")
            if self._reg_degraded:
                # Naming the channels matters: the others really were built
                # with the framing and filters described above, and lumping
                # them together would understate those.
                for f in sorted(self._reg_degraded):
                    A(f"    - \u26a0\ufe0f **{f}** was registered without "
                      + ", ".join(self._reg_degraded[f])
                      + ".  Siril refused the full argument set for this "
                      "channel and it fell back to a smaller one, so the "
                      "line above does not describe this master.")
            if self._drizzle_warned:
                A(f"    - ⚠️ Drizzle ran on fewer than {DRIZZLE_MIN_FRAMES} "
                  "frames. It spreads each sub's flux over a finer grid, so "
                  "it needs many *dithered* subs to fill that grid evenly — "
                  "below that it usually adds noise instead of resolution. "
                  "Compare against an undrizzled run before keeping this.")
            A(N() + " **Integration** (`stack`):")
            A("    - **Rejection** is chosen automatically from each filter's "
              "frame count (see the table above) — percentile clipping for "
              "few frames, Winsorized sigma for more, linear-fit beyond that, "
              f"and GESDT from {GESDT_MIN_FRAMES} frames, where the test has "
              "enough data to outperform the rest. Sigma-based methods need "
              "a population to work, so few-frame channels use gentler "
              "percentile clipping.")
            A("    - **Normalization:** additive + scaling — matches the "
              "background level and brightness of every sub before averaging.")
            if opts.get("weighting", True):
                wm = opts.get("weight_method", "Weighted FWHM")
                why = {
                    "Weighted FWHM": "sharpness scaled by the star count, so "
                                     "sharper subs contribute more",
                    "Noise": "measured background noise, so the cleanest subs "
                             "contribute more — the better choice for "
                             "star-poor narrowband fields",
                    "Number of stars": "detected star count, so the most "
                                       "transparent subs contribute more",
                }.get(wm, "sharper subs contribute more")
                A(f"    - **Weighting:** {wm} (`-weight="
                  f"{_weight_token(opts)}`) — {why}.")
            else:
                A("    - **Weighting:** off — every sub contributed equally.")
            A("    - **Bit depth:** 32-bit float"
              + (", output-normalized." if opts.get("output_norm", True)
                 else "."))
            if opts.get("bg_master", True):
                how = ("RBF" if opts.get("bg_rbf") else "polynomial, degree 1")
                A(N()
                  + f" **Background extraction** (`subsky`, {how}) — the sky "
                  "gradient was removed from each finished master while still "
                  "linear (gradients differ per filter, so this works better "
                  "per channel than once on the colour image)."
                  + (" RBF was used because it can follow a gradient that "
                     "changes direction across the frame, which a "
                     "first-degree polynomial cannot."
                     if opts.get("bg_rbf") else ""))
            A("")
            A("→ saved as `masters/<TARGET>_<FILTER>_fullframe.fit`.")
            A("")
            if did_align:
                A("### 3.2 · Aligning the channels to each other")
                A("")
                n_al = len(final_paths)
                A("Each filter is stacked against its *own* reference, so the "
                  "masters can sit on slightly different pixel grids — the "
                  "colour channels wouldn't line up. To fix that, "
                  + (f"the {n_al} stacked masters were"
                     if self._skipped_by_palette else "all masters were")
                  + " pooled and re-registered onto **one common grid** "
                  "(`seqapplyreg -framing=min`), producing **pixel-identical** "
                  "channels:")
                A("")
                A("→ `masters/<TARGET>_<FILTER>.fit` (these feed the colour "
                  "image).")
                A("")
        if opts.get("platesolve_master"):
            A(("The per-filter masters were also"
               if not self._skipped_by_palette else
               f"The {len(final_paths)} masters this run produced were "
               "also")
              + " **plate-solved** (a WCS / sky coordinate solution was "
              "written into each).")
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
                if any(s.startswith("Colour calibration: SPCC")
                       for s in self._finish_steps):
                    A("    - ⚠️ SPCC also calibrated this image. The two "
                      "overlap: normalisation flattens the line ratio on "
                      "purpose, and SPCC's narrowband mode calibrates that "
                      "very ratio against catalogue spectra. Switch "
                      "**Normalize narrowband channels** off to let SPCC "
                      "work on the physical ratio.")
            if palette == "HaRGB":
                A(f"- **Blended Ha into Red** at "
                  f"{int(opts.get('ha_strength', 50))}% (a PixelMath screen "
                  "blend) for stronger emission-nebula detail.")
            baked = palette == "LRGB" and opts.get("quick_lrgb")
            A("- **Combined** the channels with `rgbcomp`"
              + (" (luminance baked in linearly — the *quick* mode)." if baked
                 else "."))
            if baked and any(s.startswith("Colour calibration: SPCC")
                             or s.startswith("Colour calibration: PCC")
                             for s in self._finish_steps):
                # Same shape as the narrowband note above: an option that
                # works against the calibration that follows it.
                A("    - ⚠️ The colour was calibrated **after** that.  "
                  "Baking L in linearly lifts the star cores over the top "
                  "of the range, and photometry can only use stars it can "
                  "still measure — Siril reports the count it dropped as "
                  "*pixel out of range*.  Untick **Quick linear LRGB** to "
                  "calibrate the RGB alone and combine L after stretching "
                  "(`todo.md` walks through it).")
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
        A("## 4 · Important — "
          + ("this image is" if comp_name else "these masters are")
          + " still _linear_")
        A("")
        which = ("SPCC" if any(s.startswith("Colour calibration: SPCC")
                               for s in self._finish_steps) else "PCC")
        A("A linear image looks almost black: the faint galaxy / nebula "
          "signal sits just above the background. Colour calibration "
          f"({which}) **must** run on linear data, which is why "
          + ("the script stops here" if comp_name else
             "the masters are handed over untouched \u2014 combine them "
             "first, then calibrate, and only then stretch")
          + ". The next step — **stretching** — is creative and best done "
          "by eye.")
        A("")
        A("👉 Open **[`todo.md`](todo.md)** for a step-by-step guide.")
        A("")

        # 5 · Good to know ---------------------------------------------------
        A("## 5 · Good to know")
        A("")
        if reused:
            # Nothing was stacked this run, so nothing was calibrated either
            # -- but the reused masters may well be calibrated.  Saying "no
            # calibration was used" here would be plain wrong.
            A("- The masters were **reused**, so no calibration ran this "
              "time. Whether they are calibrated is recorded in the report "
              "of the run that produced them.")
        elif not self._calib_notes:
            A("- **No calibration frames** (darks / flats / bias) were used. "
              "Without flats you may see some vignetting and dust shadows — "
              "shoot flats for each filter and re-run for the cleanest "
              "result.")
        else:
            # Filters that were reused weren't calibrated this run either,
            # so they can't be judged here -- only the freshly stacked ones.
            skip = set(partial_reuse or ())
            missing = [f for f in sorted(self._groups)
                       if f not in skip
                       and "flat=" not in self._calib_notes.get(f, "")]
            if missing:
                one = len(missing) == 1
                A(f"- **No flat was applied to {', '.join(missing)}** — "
                  + ("that channel" if one else "those channels")
                  + " may still show vignetting and dust shadows. Flats are "
                  "filter-specific, so each filter needs its own set.")
            A("- The calibration masters that were used are kept in "
              f"`{CALIB_DIRNAME}/` — delete that folder to force a rebuild on "
              "the next run.")
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
        # What the finish step REALLY did.  Telling the user "the colour is
        # already calibrated" when auto-finish was off, or when PCC could not
        # reach a catalog, would make them skip a step they still need.
        steps = self._finish_steps
        # Only the success line starts with "Colour calibration: " -- the
        # FAILED and skipped variants must not read as done.
        pcc_done = any(s.startswith("Colour calibration: ") for s in steps)
        bg_done = any(s.startswith("Extracted the background gradient")
                      for s in steps)
        nb_done = bool(composite and palette in ("SHO", "HOO")
                       and self._opts.get("nb_normalize", True))
        # Narrowband SPCC ran instead of the normalization -- the intended
        # pairing, and the reason the advice below must not be "switch
        # normalization back on".
        nb_spcc = bool(composite and palette in ("SHO", "HOO")
                       and any(s.startswith("Colour calibration: SPCC")
                               and "narrowband" in s for s in steps))
        S: list[str] = []
        A = S.append

        A(f"# 🎨 Final Processing — {target} ({palette})")
        A("")
        if not composite:
            A("**No colour image was produced this run** — what you have is "
              "one linear master per filter in `masters/`. Combine them "
              "yourself (Siril: *Image Processing → RGB composition*), or "
              "re-run with **Compose colour image** enabled. The steps below "
              "assume a combined image and apply from that point on.")
            A("")
        A("Everything the script produced is **linear**"
          + (" and colour-calibrated." if pcc_done else
             ", and the colour is **not** calibrated yet (see step 2).")
          + " The steps below are the *creative*, non-linear part — they're "
          "yours to taste. Do them in **Siril** (or PixInsight / Photoshop / "
          "Affinity Photo).")
        A("")
        A("> 💡 **Work on a copy**, and keep the linear masters in `masters/` "
          "so you can always redo from any step.")
        A("")
        A("> 📖 New to this? The three stages are always: **(1) flatten the "
          "background → (2) calibrate colour"
          + (" (already done for you)" if pcc_done else " (still to do)")
          + " → (3) stretch**, and only *then* the artistic touches. "
          "Stretching before calibrating ruins the colour, which is why the "
          "script hands the image over still linear.")
        A("")
        A("---")
        A("")

        if palette in ("LRGB", "RGB", "HaRGB"):
            A(f"## Part A — Colour (open `{comp}`)")
            A("")
            A("1. **Background check.** "
              + ("A gradient was already removed; if one still shows, run "
                 if bg_done else
                 "No background extraction was run on the colour image, so "
                 "do it now: ")
              + "*Image Processing → Background Extraction* (degree 1, "
              "**Subtract**). A flat background is essential before "
              "stretching.")
            if pcc_done and palette == "LRGB" and self._opts.get(
                    "quick_lrgb"):
                A("2. **White balance.** The colour was "
                  "**photometrically calibrated**, but *Quick linear LRGB* "
                  "had already baked the luminance in, so the brightest "
                  "stars were clipped and could not be measured.  Treat the "
                  "balance as good-but-approximate, and re-run with that "
                  "option off if the colour looks off.")
            elif pcc_done:
                A("2. **White balance.** The colour is already "
                  "**photometrically calibrated** — leave the white balance "
                  "as it is.")
            elif palette == "HaRGB":
                A("2. **White balance.** PCC was **not** applied (the Red "
                  "channel carries Ha, so star photometry is invalid). Set the "
                  "balance by hand: *Image Processing → Color Calibration*, "
                  "pick a neutral background reference.")
            else:
                A("2. **White balance — still to do.** Photometric Colour "
                  "Calibration did **not** run (auto-finish was off, or no "
                  "photometry catalog was reachable). Plate-solve the image "
                  "and run *Image Processing → Photometric Color "
                  "Calibration*, or balance it by hand against a neutral "
                  "background.")
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
            if self._separate_lum:
                A("- To reuse an existing luminance next time, keep the "
                  "palette on **LRGB** — the script keeps L separate "
                  "automatically.")
            elif palette == "LRGB" and self._opts.get("quick_lrgb"):
                A("- L was **baked into** this composite, not kept separate: "
                  "that is what *Quick linear LRGB* does.  Untick it to get "
                  "a calibrated RGB plus a separate luminance, which is the "
                  "order Siril recommends.")
            if self._skipped_by_palette:
                A("- The "
                  + _plural(self._skipped_by_palette, "filter", "filters")
                  + " this palette skipped "
                  + _plural(self._skipped_by_palette, "was", "were")
                  + " never stacked, so another palette needs a full re-run "
                  "— untick *Stack only the filters this palette uses* "
                  "first.")
            if not self._skipped_by_palette:
                A("- Re-run with **Reuse existing masters** ticked to try "
                  "another palette in seconds (no re-stacking).")
            return "\n".join(S) + "\n"

        # Narrowband SHO / HOO
        A(f"## Narrowband (open `{comp}`)")
        A("")
        if nb_done:
            A("1. **Starting point.** The channels were already normalized to "
              "Ha, so the image is balanced — not the pure-green you'd get "
              "from a raw SHO combine.")
        elif not composite:
            # Telling the reader to switch on an option that may already be
            # on would send them looking in the wrong place: nothing was
            # normalized because nothing was composed.
            A("1. **Starting point.** No composite was made, so no "
              "normalization ran either — it is part of the composition "
              "step. When you combine the channels yourself, match them "
              "first (Siril: `linear_match` against the Ha master), or "
              "the strong Ha will dominate and push the image green.")
        elif nb_spcc:
            # Normalization off AND narrowband SPCC on is the recommended
            # pairing, not a gap: SPCC measures the physical line ratio and
            # corrects it: normalizing first would have flattened the very
            # quantity it reads.  Telling the reader to switch the option
            # back on would undo the calibration they just got.
            A("1. **Starting point.** The channels were deliberately **not** "
              "normalized: SPCC's narrowband mode measured the real Ha / "
              "OIII line ratio against catalogue spectra and corrected it "
              "from there. That is the physically grounded starting point — "
              "leave *Normalize narrowband channels* off while SPCC is "
              "doing the calibration.")
        else:
            A("1. **Starting point.** The channels were **not** normalized to "
              "a common reference, so expect one channel — usually the strong "
              "Ha — to dominate and push the image green. Fix that first with "
              "per-channel *Curves*, or re-run with **Normalize narrowband "
              "channels** enabled.")
        A("2. **Background check**"
          + (" *(optional)*" if bg_done else "")
          + " — *Image Processing → Background Extraction* (degree 1) if a "
          "gradient remains.")
        if pcc_done:
            A("   - The channels were additionally **colour-calibrated with "
              "SPCC in narrowband mode**, using each line's wavelength — so "
              "the starting balance is physical, not just normalized."
              + (" Trust it as your baseline before you start pushing the "
                 "palette." if not nb_done else
                 "  ⚠️ But the channels were **also** normalized to Ha "
                 "first, which flattens the very line ratio SPCC then "
                 "measured — so treat this baseline as approximate, and see "
                 "the note in `output.md` for which of the two to switch "
                 "off."))
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
        if self._skipped_by_palette:
            A("- The "
              + _plural(self._skipped_by_palette, "filter", "filters")
              + " this palette skipped "
              + _plural(self._skipped_by_palette, "was", "were")
              + " never stacked, so another palette needs a full re-run — "
              "untick *Stack only the filters this palette uses* first.")
        if not self._skipped_by_palette:
            # Naming the palette that was just built would be circular.
            other = "SHO" if palette == "HOO" else "HOO"
            A(f"- Re-run with **Reuse existing masters** ticked to try "
              f"{other} (or LRGB) on the same data in seconds.")
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
            mixed = ({} if missing_aligned or not want_reuse
                     else _mixed_grids(aligned_paths))
            reusable_full = {f: p for f, p in full_paths.items()
                             if os.path.exists(p)}
            reuse_ok = bool(want_reuse and filters
                            and not missing_aligned and not mixed)
            if mixed:
                # Aligned masters only overlay if they came out of the SAME
                # alignment run: -framing=min crops to the intersection of
                # whatever was in the sequence, so a later run over a subset
                # (see "Stack only the filters this palette uses") leaves the
                # others on the previous grid.  Reusing the mix would hand
                # rgbcomp channels of different sizes.
                shown = ", ".join(
                    f"{f} {w}\u00d7{h}" for f, (w, h) in sorted(mixed.items()))
                self._emit(
                    "Full reuse not possible — the aligned masters are not "
                    f"on one grid ({shown}). They come from different "
                    "alignment runs; re-aligning them now.", LogColor.SALMON)
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
                # Calibration masters are built once for the whole run, not
                # per filter -- darks and bias are shared across channels.
                # `_calib` always carries the four kind keys, so it is
                # truthy even when every group is empty -- test the groups,
                # or the run announces a calibration step it never takes.
                if (self._opts.get("calibrate", True)
                        and any(self._calib.values())):
                    self.progress.emit(4, "Building calibration masters...")
                    self._emit("Building calibration masters…", LogColor.GREEN)
                    self._build_calib_masters()
                results, errors, last_result = self._stack_all_filters(
                    reuse={f: reusable_full[f] for f in skip})

                # Cross-filter alignment: register the per-filter masters to a
                # common grid so LRGB / SHO channels overlay pixel-for-pixel.
                # Composition needs one identical grid, so it implies
                # alignment even if the user left that box unchecked.
                final_paths = dict(results)
                want_compose = self._opts.get("compose", False)
                # After an abort, only some channels exist.  Aligning and
                # composing them would spend another half-minute -- part of
                # it on a photometry server -- to produce a colour image
                # that is missing filters, right after telling the user we
                # were stopping.  Keep the finished masters and stop.
                do_align = (not self._aborted
                            and (self._opts.get("align_filters", True)
                                 or want_compose))
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
            if (self._opts.get("platesolve_master", False)
                    and not self._aborted):
                n_m = max(1, len(final_paths))
                for i, (filt, path) in enumerate(list(final_paths.items())):
                    self.progress.emit(
                        int(84 + 6 * i / n_m),
                        f"Plate-solving masters ({i + 1}/{n_m})...")
                    self._platesolve_file(path)

            # Optional: combine the aligned masters into a colour composite.
            composite = None
            composite_load = None
            # Two masters are enough: HOO feeds the same OIII master into
            # both Green and Blue.  Demanding three filters here would
            # refuse the most common narrowband pair outright -- _compose
            # validates the actual channel mapping and says what is missing.
            if want_compose and len(final_paths) >= 2 and not self._aborted:
                self.progress.emit(90, "Composing colour image...")
                composite = self._compose(final_paths)
                composite_load = composite
                if composite and self._opts.get("finish", True):
                    self.progress.emit(
                        94, "Finishing composite (background + colour)...")
                    composite_load = self._finish_composite(composite)
            elif want_compose and self._aborted:
                self._emit(
                    "Colour composition skipped — the run was stopped, so "
                    "the channel set is incomplete. The masters that "
                    "finished are in masters/; re-run with 'Reuse existing "
                    "masters' to stack only what is missing.",
                    LogColor.SALMON)
            elif want_compose:
                self._emit(
                    "Colour composition skipped: a colour image needs at "
                    "least two filters (three for R/G/B).", LogColor.SALMON)

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
            if (self._opts.get("cleanup_work", False) and final_paths
                    and not self._aborted):
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

            self.progress.emit(100, "Stopped." if self._aborted else "Done.")
            self.finished.emit(
                {"results": final_paths, "errors": errors,
                 "aligned": did_align, "aborted": self._aborted,
                 "compose_wanted": bool(self._opts.get("compose", False)),
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
            if fname and fname in paths:
                continue
            wants = _PALETTE_SOURCE.get(palette, {}).get(role, "a filter")
            if fname:
                why = (f"'{fname}' is mapped to it, but no aligned master "
                       "of that name was produced")
            else:
                why = f"{palette} takes it from {wants}, and none is mapped"
            better = _detect_palette(sorted(paths))
            # Plain text: the Log tab escapes what it is given, so Markdown
            # emphasis would show up as literal asterisks.
            hint = ("" if better == palette else
                    f"  With the filters you have, {better} would work; "
                    "or map the channel by hand in the dropdowns.")
            self._emit(
                f"  Colour composition skipped: the {role.upper()} channel "
                f"has no master — {why}.{hint}", LogColor.SALMON)
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

    def _collect_rejmaps(self, process_dir: str, out_name: str) -> None:
        """Copy any rejection maps out of _work/ into the qa/ folder.

        ``stack -rejmap`` writes its map(s) beside the stack output, i.e.
        deep inside _work/ where nobody looks -- and "Delete _work/ when
        finished" would remove them.  The exact file names differ between
        Siril versions (low/high maps), so match on the output name plus
        "rejmap" rather than guessing a fixed suffix.
        """
        try:
            names = [f for f in os.listdir(process_dir)
                     if "rejmap" in f.lower() and f.startswith(out_name)]
        except OSError as exc:
            _log_swallowed(exc)
            return
        if not names:
            self._emit("  Rejection map requested but none was written.",
                       LogColor.SALMON)
            return
        qa_dir = os.path.join(self._out_dir, QA_DIRNAME)
        os.makedirs(qa_dir, exist_ok=True)
        for name in names:
            dst = os.path.join(qa_dir, name)
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.copy2(os.path.join(process_dir, name), dst)
            except OSError as exc:
                _log_swallowed(exc)
        self._emit(f"  Rejection map(s) -> {QA_DIRNAME}/"
                   f"{', '.join(sorted(names))}", LogColor.GREEN)

    def _spcc_args(self, palette: str) -> list:
        """Build the `spcc` arguments for this palette.

        SPCC is sensor- and filter-aware, which is exactly what a mono rig
        behind a filter wheel needs -- and its narrowband mode is the only
        way to colour-calibrate an SHO / HOO composite at all, because
        ordinary star photometry is meaningless once the "colours" are
        mapped emission lines.

        Names must come from Siril's MONO tables.  They are easy to get
        wrong in a way that produces no error at all: "IMX533" exists only
        under osc_sensors, so Siril matched it there and calibrated the
        image as one-shot colour -- the wrong spectral model for a filter
        wheel.  The mono entry for the same chip is called
        "Sony IMX411/455/461/533/571".  Every name is therefore checked
        against the local SPCC database and mismatches are reported with
        the candidates, instead of failing silently at run time.

        Quoting rule, learned the hard way: the quotes go around the WHOLE
        argument, flag included -- `"-rfilter=Antlia R"`, not
        `-rfilter="Antlia R"`.  sirilpy joins the arguments with spaces into
        one command line, and Siril re-splits it shell-style; with the
        quotes around the value only, the split happens at the space inside
        it and the run dies on `Invalid argument IMX411/455/461/533/571"`.

        The sensor is sent in every mode, narrowband included -- see the
        comment below for why leaving it out is the same class of silent
        error as naming the OSC entry.
        """
        args: list = []
        sensor = (self._opts.get("spcc_sensor") or "").strip()
        if sensor:
            self._check_spcc_name(sensor, "mono_sensors", "sensor")
            args.append(f'"-monosensor={sensor}"')
        if palette in ("SHO", "HOO"):
            # The sensor belongs here too.  Siril's own help says
            # -narrowband makes it ignore "the previous FILTER arguments"
            # -- filters only; its usage grammar keeps -monosensor= in a
            # separate optional group.  That is physics, not a quirk: the
            # narrowband arguments describe the filter passbands, while the
            # sensor's quantum efficiency at 656/501 nm is an independent
            # factor in the same product.  Omitting it does not fail, it
            # silently falls back to whatever sits in Siril's saved SPCC
            # preferences -- an OSC sensor, on a fresh install.
            #
            # Wavelengths are physics, not preference.  Bandwidth depends on
            # the user's filter set, so that one is configurable.
            bw = float(self._opts.get("nb_bandwidth", 7))
            r, g, b = ((SII_NM, HA_NM, OIII_NM) if palette == "SHO"
                       else (HA_NM, OIII_NM, OIII_NM))
            args += ["-narrowband",
                     f"-rwl={r:g}", f"-gwl={g:g}", f"-bwl={b:g}",
                     f"-rbw={bw:g}", f"-gbw={bw:g}", f"-bbw={bw:g}"]
            if not sensor:
                self._emit(
                    "  SPCC: no sensor name given, so Siril will use "
                    "whichever sensor its own SPCC dialog last had -- "
                    "possibly an OSC one, which is the wrong spectral "
                    "model for a filter wheel. Narrowband mode does not "
                    "replace the sensor, only the filters.",
                    LogColor.SALMON)
            elif any((self._opts.get(k) or "").strip() for k in
                     ("spcc_rfilter", "spcc_gfilter", "spcc_bfilter")):
                # Siril prints its stored filter names on every SPCC run,
                # narrowband or not.  Seeing "Antlia R, Antlia G, Antlia B"
                # under a narrowband command looks like the filters were
                # sent and ignores the wavelengths; say which one wins.
                self._emit(
                    "  SPCC: the filter names are not used here -- "
                    "narrowband mode replaces them with the wavelengths "
                    "and bandwidths above. Siril still echoes the stored "
                    "names in its own log; the wavelengths are what it "
                    "calibrates with.", LogColor.BLUE)
            return args
        if not sensor:
            return args
        filters = [(self._opts.get(k) or "").strip()
                   for k in ("spcc_rfilter", "spcc_gfilter", "spcc_bfilter")]
        for flag, val in zip(("-rfilter", "-gfilter", "-bfilter"), filters):
            if val:
                self._check_spcc_name(val, "mono_filters", "filter")
                args.append(f'"{flag}={val}"')
        if not all(filters):
            self._emit(
                "  SPCC: no filter transmission curves given, so only the "
                "sensor response is modelled. Filling in all three filter "
                "names describes the rig completely.", LogColor.SALMON)
        return args

    def _spcc_root(self) -> str:
        """Siril's own data directory, or "" if it will not say.

        Asking beats guessing: a packaged build (Flatpak, Snap, Microsoft
        Store) puts its data somewhere none of the hard-coded paths would
        find.  Cached because the answer cannot change mid-run, and wrapped
        because an older sirilpy may not have the call at all -- in which
        case the guesses still apply.
        """
        if self._spcc_root_cache is None:
            try:
                self._spcc_root_cache = str(
                    self.siril.get_siril_userdatadir() or "")
            except Exception as exc:
                _log_swallowed(exc)
                self._spcc_root_cache = ""
        return self._spcc_root_cache

    def _check_spcc_name(self, name: str, table: str, what: str) -> None:
        """Warn if `name` is not in Siril's local SPCC table.

        A wrong name is not an error for Siril -- it just quietly uses
        something else, which is how a mono rig ends up calibrated as
        one-shot colour.  Checking against the database it will consult
        turns that into a message before the run rather than a puzzle
        afterwards.
        """
        names = _spcc_catalog(table, self._spcc_root())
        if not names or name in names:
            return                      # unknown DB, or an exact hit
        # Siril matches loosely, so a substring hit will probably work.
        # Sort them: `names` is a set, and naming an arbitrary member as
        # "the" match would be a different answer on a different run.  With
        # several candidates the choice is Siril's, not ours -- list them
        # instead of picking one and calling it likely.
        near = sorted(n for n in names if name.lower() in n.lower())
        if len(near) == 1:
            self._emit(
                f"  SPCC: {what} '{name}' is not an exact entry; Siril "
                f"should resolve it to '{near[0]}'.", LogColor.BLUE)
            return
        if near:
            self._emit(
                f"  SPCC: {what} '{name}' matches {len(near)} entries "
                f"({', '.join(near)}) — Siril picks one of them, and which "
                "is up to it. Enter the full name to be sure.",
                LogColor.SALMON)
            return
        sample = ", ".join(sorted(names)[:6])
        self._emit(
            f"  SPCC: {what} '{name}' is not in Siril's {table} table — it "
            "will be ignored, and a name that only exists in the OSC tables "
            "makes SPCC calibrate as one-shot colour. Known entries include: "
            f"{sample}…", LogColor.SALMON)

    def _colour_calibrate(self, palette: str) -> None:
        """Colour-calibrate the loaded composite, best method first.

        The chain degrades one step at a time and never aborts the finish:
        SPCC with sensor/filter details -> bare SPCC (Siril's configured
        defaults) -> PCC -> PCC against a local Gaia catalog -> give up and
        say so.  HaRGB is excluded from photometric methods entirely: its
        Red channel carries blended Ha, so the star colours are no longer
        physical.
        """
        if palette == "HaRGB":
            self._finish_steps.append(
                "Colour calibration skipped (HaRGB: the Red channel carries "
                "blended Ha, so star photometry is invalid) — balance the "
                "colour manually.")
            self._emit(
                "  Finish: colour calibration skipped for HaRGB (Ha-boosted "
                "Red); balance the channels manually.", LogColor.BLUE)
            return

        if palette == "LRGB" and self._opts.get("quick_lrgb"):
            # Baking L in linearly lifts the bright end, so more stars
            # saturate and drop out of the photometric fit.  Measured on one
            # dataset: excluded stars 1107 -> 1531, of which "pixel out of
            # range" 69 -> 522, and the R/G fit sigma 0.61 -> 0.77.
            self._emit(
                "  Note: 'Quick linear LRGB' bakes the luminance in before "
                "this calibration, which pushes stars into saturation and "
                "measurably weakens the colour solution. Turning it off "
                "calibrates the RGB alone and combines L after stretching.",
                LogColor.SALMON)

        narrowband = palette in ("SHO", "HOO")
        if (narrowband and self._opts.get("use_spcc", True)
                and self._opts.get("nb_normalize", True)):
            # These two balance the same thing by opposite means.
            # linear_match forces the channels onto a common histogram,
            # i.e. it deliberately removes the Ha/OIII flux ratio -- which
            # is the very quantity SPCC's narrowband mode then measures
            # against catalogue spectra to calibrate.  Observed on one
            # HOO run: the R/G fit came out with sigma 5.8, against 1.4 for
            # a broadband composite of the same night.
            self._emit(
                "  Note: 'Normalize narrowband channels' already forced the "
                "channels onto a common level, so SPCC is now measuring a "
                "ratio that was flattened on purpose. Turning that option "
                "off leaves the physical line ratio intact for SPCC to "
                "calibrate; keep it on only when you are not calibrating.",
                LogColor.SALMON)

        attempts: list = []
        if self._opts.get("use_spcc", True):
            detailed = self._spcc_args(palette)
            if detailed:
                # Name only what was really passed, so a mismatch between
                # what we sent and what Siril reports using is visible.
                what = ("narrowband mode" if narrowband
                        else "mono sensor + filters")
                attempts.append((["spcc"] + detailed, f"SPCC ({what})"))
            # Bare SPCC still beats PCC -- but only if SPCC has been run
            # from Siril's own dialog before, because that is where those
            # defaults come from ("not ... guessable from previous use").
            # On a fresh install it simply fails and the chain moves on.
            attempts.append((["spcc"], "SPCC (Siril's configured defaults)"))
        if not narrowband:
            # PCC assumes broadband R/G/B star colours; on a narrowband
            # palette it would "calibrate" against photometry that does not
            # describe these channels at all.
            attempts.append((["pcc"], "PCC (NOMAD catalog)"))
            attempts.append((["pcc", "-catalog=localgaia"],
                             "PCC (local Gaia catalog)"))

        last = None
        for cmd, label in attempts:
            # Echo the exact command.  Siril's own log reports which sensor
            # and filters it ENDED UP using, so having ours next to it is
            # what turns "SPCC ran" into "SPCC ran with what I asked for".
            self._emit("  " + " ".join(cmd), LogColor.BLUE)
            try:
                self._cmd(*cmd)
            except (CommandError, DataError, SirilError) as exc:
                last = exc
                self._emit(f"  Finish: {label} did not run ({exc}).",
                           LogColor.SALMON)
                continue
            self._finish_steps.append(f"Colour calibration: {label}.")
            self._emit(f"  Finish: colour calibration done — {label}.",
                       LogColor.GREEN)
            return

        if not attempts:
            # Nothing was even tried: SPCC is switched off and this palette
            # has no valid non-SPCC method.  Saying "FAILED" would blame the
            # tooling for what is simply a setting.
            self._finish_steps.append(
                f"Colour calibration not attempted — {palette} can only be "
                "calibrated by SPCC (narrowband mode), and SPCC is switched "
                "off.  The colour is NOT calibrated.")
            self._emit(
                f"  Finish: no colour calibration for {palette} — it needs "
                "SPCC's narrowband mode, which is switched off.",
                LogColor.SALMON)
            return

        why = (" — narrowband calibration needs SPCC with a Gaia "
               "spectrophotometry catalog" if narrowband else "")
        self._finish_steps.append(
            f"Colour calibration FAILED{why} — the colour is NOT calibrated; "
            "set the white balance manually.")
        self._emit(
            f"  Finish: no colour calibration succeeded ({last}){why}; "
            "composite left uncalibrated.", LogColor.SALMON)

    def _subsky(self, where: str) -> str:
        """Run subsky on the loaded image; return what was used, for the log.

        RBF models a gradient that changes direction across the frame far
        better than a first-degree polynomial, which is why it is offered
        for the finished masters and the composite.  It is NOT offered for
        the individual subs: Siril's guidance is a degree-1 polynomial
        there, and that is what seqsubsky keeps doing.

        Falls back to the polynomial if RBF is refused, so an older build
        cannot cost the user the background extraction altogether.
        """
        if self._opts.get("bg_rbf", False):
            smooth = float(self._opts.get("bg_smooth", 50)) / 100.0
            try:
                self._cmd("subsky", "-rbf", "-samples=20",
                          f"-smooth={smooth:g}")
                return f"RBF (smoothing {smooth:g})"
            except (CommandError, DataError, SirilError) as exc:
                self._emit(
                    f"  {where}: RBF background extraction was refused "
                    f"({exc}); using the degree-1 polynomial instead.",
                    LogColor.SALMON)
        self._cmd("subsky", "1", "-samples=20")
        return "polynomial, degree 1"

    def _bg_extract_master(self, path: str) -> None:
        """Background-extract a single linear per-filter master, in place."""
        ext = self._ext
        base = path[:-len(ext)] if path.lower().endswith(ext.lower()) else path
        try:
            self._cmd("load", f'"{path}"')
            how = self._subsky("master")
            self._cmd("save", f'"{base}"')
            self._emit(f"  Background extracted ({how}, per-channel master).",
                          LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Per-channel background extraction skipped ({exc}).",
                LogColor.SALMON)

    def _finish_composite(self, path: str) -> str:
        """Background-extract + colour-calibrate the composite in place.

        Runs, all resiliently (a failing step logs and is skipped, never
        aborts): plate-solve (every colour calibration method needs a WCS),
        background extraction, colour calibration and SCNR green removal.
        The calibrated *linear* result is saved over the composite.  If a
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

        # Plate-solve: every colour calibration method needs astrometry, and
        # rgbcomp output may carry no WCS.  When "Plate-solve final masters"
        # was on, rgbcomp copies their solution into the composite and this
        # call is a no-op -- worth distinguishing, because "we solved it
        # here" and "it arrived solved" are different facts.
        inherited = _has_wcs(path)
        solved = True
        try:
            self._cmd("platesolve")
            if inherited:
                self._finish_steps.append(
                    "Astrometry (WCS) was inherited from the plate-solved "
                    "masters via rgbcomp — no new solve was needed.")
                self._emit(
                    "  Finish: composite already carries the masters' "
                    "astrometry; plate-solve skipped.", LogColor.BLUE)
            else:
                self._finish_steps.append("Plate-solved the composite.")
        except (CommandError, DataError, SirilError) as exc:
            # Only note the failure here; the consequence is reported once,
            # below, so the two do not say the same thing twice.
            solved = False
            self._finish_steps.append("Plate-solve failed.")
            self._emit(
                f"  Finish: plate-solve failed ({exc}); skipping colour "
                "calibration.", LogColor.SALMON)

        # Background / gradient extraction on the COMBINED image, before the
        # colour calibration.  Even with per-channel extraction, the freshly
        # combined RGB carries its own residual gradient, and the photometric
        # methods explicitly want a flat background ("correct the image
        # gradient first") -- so this runs regardless of the per-channel pass.
        try:
            how = self._subsky("composite")
            self._finish_steps.append(
                f"Extracted the background gradient (subsky, {how}).")
            self._emit(f"  Finish: composite background extracted ({how}, "
                          "before colour calibration).", LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Finish: composite background extraction skipped ({exc}).",
                LogColor.SALMON)

        palette = self._opts.get("compose_palette", "RGB")
        if solved:
            self._colour_calibrate(palette)
        else:
            self._finish_steps.append(
                "Colour calibration skipped — the composite could not be "
                "plate-solved, and every method needs astrometry.")

        # SCNR green removal (mono-narrowband / RGB both benefit).
        try:
            self._cmd("rmgreen")
            self._finish_steps.append("Removed the green cast (SCNR).")
        except (CommandError, DataError, SirilError) as exc:
            _log_swallowed(exc)

        # Save the LINEAR composite over the original.  "Calibrated" is
        # only true when a calibration actually ran: HaRGB skips it on
        # purpose (Ha in the Red channel invalidates star photometry), and
        # claiming it here contradicted the line two entries above.
        calibrated = any(s.startswith("Colour calibration: ")
                         for s in self._finish_steps)
        try:
            self._cmd("save", f'"{base}"')
            self._finish_steps.append(
                "Saved the " + ("calibrated, " if calibrated else "")
                + "still-LINEAR composite.")
            self._emit(
                "  Finish: "
                + ("calibrated composite" if calibrated
                   else "composite (uncalibrated)")
                + f" saved ({os.path.basename(base)}{ext}).",
                LogColor.GREEN)
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
            # Siril appends its own extension, so strip the existing one --
            # via _fits_ext, which knows the compound forms (.fits.fz ...)
            # and cannot fall out of step with FITS_EXTS.
            ext = _fits_ext(path)
            base = path[:-len(ext)] if ext else path
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
    and general practice -- is percentile clipping for small sets,
    winsorized / linear-fit for medium ones, and GESDT once the stack is
    large enough for the test to have power.  Returns ``(tokens, label)``.
    """
    if not enabled:
        return ["rej", "none"], "no rejection"
    if n <= 4:
        # Percentile clipping -- params are fractions, not sigmas.
        return ["rej", "percentile", "0.2", "0.1"], "percentile 0.2/0.1"
    if n <= 20:
        return ["rej", "winsorized", "3", "3"], "winsorized 3/3"
    if n < GESDT_MIN_FRAMES:
        # Linear fit handles residual gradients between subs well.
        return ["rej", "linear", "3", "3"], "linear fit 3/3"
    # Generalized Extreme Studentized Deviate Test.  Siril documents it as
    # performing excellently past ~50 frames.  Its two parameters are NOT
    # sigmas: the first caps the fraction of the stack that may be
    # rejected, the second is the significance threshold.
    return (["rej", "g", "0.3", "0.05"],
            "GESDT 0.3 max-reject / 0.05 significance")


_SPCC_CACHE: dict = {}


def _spcc_catalog(table: str, hint: str = "") -> set:
    """Names in one of Siril's local SPCC tables, or an empty set.

    Siril keeps its SPCC data as a checked-out git repository of JSON
    files, one per filter set or sensor family, each holding entries with a
    ``name``.  This reads it READ-ONLY and for one purpose: telling the
    user that a name is wrong *before* SPCC silently substitutes something
    else -- the failure mode that made a mono rig calibrate as one-shot
    colour.  The calibration itself never uses these names; they go to
    Siril, which does its own lookup.

    ``hint`` is Siril's own data directory, asked for via sirilpy.  It is
    tried first because it is the only authoritative answer; the paths
    below are guesses that break if Siril moves its data or the user runs
    a packaged build.

    An empty set means "database not found", which callers must treat as
    "cannot check", never as "name is invalid".
    """
    key = (table, hint)
    if key in _SPCC_CACHE:
        return _SPCC_CACHE[key]
    home = os.path.expanduser("~")
    roots = []
    if hint:
        # The database sits either directly in Siril's data directory or
        # one level up, depending on the platform's layout.
        roots += [os.path.join(hint, "siril-spcc-database"),
                  os.path.join(os.path.dirname(hint.rstrip(os.sep)),
                               "siril-spcc-database")]
    roots += [
        # macOS
        os.path.join(home, "Library", "Application Support",
                     "org.siril.Siril", "siril-spcc-database"),
        # Linux / XDG
        os.path.join(home, ".local", "share", "siril-spcc-database"),
        os.path.join(home, ".config", "siril", "siril-spcc-database"),
    ]
    # Windows -- only when the variable is actually set: joining onto ""
    # would yield a RELATIVE path and probe whatever happens to sit beside
    # the current working directory.
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        roots.append(os.path.join(appdata, "siril", "siril-spcc-database"))
    names: set = set()
    for root in roots:
        d = os.path.join(root, table)
        if not os.path.isabs(d) or not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.lower().endswith(".json"):
                continue
            try:
                with open(os.path.join(d, fn), "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError) as exc:
                _log_swallowed(exc)
                continue
            for item in (data if isinstance(data, list) else [data]):
                if isinstance(item, dict) and item.get("name"):
                    names.add(str(item["name"]))
        if names:
            break
    _SPCC_CACHE[key] = names
    return names


def _weight_token(opts: dict) -> str:
    """Siril's ``-weight=`` value for the chosen weighting method.

    wFWHM is FWHM *scaled by the star count*, which is the right default
    for broadband but systematically penalises a sparse narrowband field;
    noise weighting is the usual answer there.  Unknown labels fall back to
    wFWHM rather than emitting an argument Siril would reject.
    """
    return WEIGHT_TOKENS.get(opts.get("weight_method", ""), "wfwhm")


def _rejection_fallback(tokens: list) -> tuple[list[str], str] | None:
    """A retry for a rejection Siril may not know, or None.

    ONLY GESDT qualifies: its `g` token is newer than the rest, so an older
    build can refuse it outright.  Every other tier -- including "no
    rejection" -- must be returned unchanged, because a stack can fail for
    a hundred unrelated reasons (bad sequence, full disk) and silently
    retrying with a *different algorithm* would both mask the real error
    and, with rejection switched off, re-enable something the user
    deliberately turned off.
    """
    if tokens[:2] != ["rej", "g"]:
        return None
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


# What each palette feeds into a colour channel, in words.  Used to explain
# a channel that cannot be filled: "no master for RED" is baffling when a
# RED filter plainly exists and the palette is SHO, which wants SII there.
_PALETTE_SOURCE = {
    "LRGB": {"red": "a Red filter", "green": "a Green filter",
             "blue": "a Blue filter"},
    "RGB": {"red": "a Red filter", "green": "a Green filter",
            "blue": "a Blue filter"},
    "HaRGB": {"red": "a Red filter", "green": "a Green filter",
              "blue": "a Blue filter"},
    "SHO": {"red": "an SII filter", "green": "an Ha filter",
            "blue": "an OIII filter"},
    "HOO": {"red": "an Ha filter", "green": "an OIII filter",
            "blue": "an OIII filter"},
}


def _unfillable_channels(filters: list, palette: str) -> list:
    """Colour channels this palette cannot fill from these filters.

    Answers the question before a run rather than after it: the filter
    list is known as soon as the folder is analysed, so choosing SHO
    without an SII filter can be reported immediately instead of after
    stacking, aligning and plate-solving everything.
    """
    m = _auto_channel_map(list(filters), palette)
    return [r for r in ("red", "green", "blue") if not m.get(r)]


def _first_with_role(filters: list[str], role: str) -> str:
    for f in filters:
        if _filter_role(f) == role:
            return f
    return ""


def _plural(items, one: str, many: str) -> str:
    """Pick a wording for a list of one versus several.

    The skipped-filter set is usually several but is routinely one, and a
    hard-coded plural reads as a bug in text the user is meant to trust:
    "OIII are not read by this palette".
    """
    return one if len(items) == 1 else many


def _palette_filters(opts: dict, filters: list) -> set:
    """Filters whose masters this palette's composite will actually read.

    Deliberately derived from the channel mapping rather than from the
    palette name: the dropdowns are what `_compose` reads, so anything
    else could disagree with them.  Luminance counts only for LRGB /
    HaRGB, matching `_compose` -- a stale L still showing in the combo
    under HOO is ignored there and must be ignored here too.  HaRGB finds
    its Ha master by role instead of through a dropdown, so that one is
    added back explicitly.

    Returns an empty set when the mapping names nothing usable; callers
    treat that as "cannot tell" and stack everything.
    """
    palette = opts.get("compose_palette", "RGB")
    if palette == "Auto":
        palette = _detect_palette(filters)
    keys = ["map_red", "map_green", "map_blue"]
    if palette in ("LRGB", "HaRGB"):
        keys.append("map_lum")
    used = {(opts.get(k) or "").strip() for k in keys}
    if palette == "HaRGB":
        used.add(_first_with_role(filters, "ha") or "")
    used.discard("")
    return {f for f in filters if f in used}


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
        # Calibration library folder (darks / bias) and the last scan result.
        self._library = ""
        self._calib: dict = {}

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
        self._build_calibration_group(layout)
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

    def _build_calibration_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Calibration")
        layout = QVBoxLayout(group)

        self.chk_calibrate = QCheckBox("Apply calibration when frames exist")
        self.chk_calibrate.setChecked(True)
        self.chk_calibrate.setToolTip(
            "Calibrate the lights before stacking:  Lc = (L − D) / (F − O).\n"
            "Everything is optional and additive — whatever is found is used, "
            "the rest is skipped.  Harmless when nothing is there.")
        _nofocus(self.chk_calibrate)
        self.chk_calibrate.toggled.connect(self._on_calibrate_toggled)
        layout.addWidget(self.chk_calibrate)

        lrow = QHBoxLayout()
        self.btn_library = QPushButton("\U0001F4C1  Library…")
        _nofocus(self.btn_library)
        self.btn_library.setToolTip(
            "Folder holding your reusable DARK and BIAS frames — either raw "
            "frames (the script stacks them) or ready-made masters.\n"
            "Flats are NOT taken from here: they belong to the session and "
            "are found next to your lights.")
        self.btn_library.clicked.connect(self._pick_library)
        lrow.addWidget(self.btn_library)
        self.btn_library_clear = QPushButton("✕")
        self.btn_library_clear.setFixedWidth(30)
        self.btn_library_clear.setToolTip("Forget the library folder.")
        _nofocus(self.btn_library_clear)
        self.btn_library_clear.clicked.connect(self._clear_library)
        lrow.addWidget(self.btn_library_clear)
        layout.addLayout(lrow)

        self.lbl_library = QLabel("No library folder set.")
        self.lbl_library.setWordWrap(True)
        self.lbl_library.setStyleSheet("color:#888888;font-size:9pt;")
        layout.addWidget(self.lbl_library)

        self.lbl_calib_found = QLabel("Analyze a folder to see what is found.")
        self.lbl_calib_found.setWordWrap(True)
        self.lbl_calib_found.setStyleSheet("color:#88aaff;font-size:9pt;")
        layout.addWidget(self.lbl_calib_found)

        self.chk_cosmetic = QCheckBox("Cosmetic correction (hot pixels)")
        self.chk_cosmetic.setChecked(True)
        self.chk_cosmetic.setToolTip(
            "Adds -cc=dark 3 3, which finds hot/cold pixels from the master "
            "dark's statistics and repairs them.\n"
            "Needs a matching dark — without one this has no effect.")
        _nofocus(self.chk_cosmetic)
        layout.addWidget(self.chk_cosmetic)

        self.chk_flats_by_date = QCheckBox("Match flats to the same night")
        self.chk_flats_by_date.setChecked(False)
        self.chk_flats_by_date.setToolTip(
            "OFF: all flats of a filter are pooled into one master — correct "
            "for a permanently mounted rig, and less noisy.\n"
            "ON: only flats from the same date folder as the lights are used "
            "— pick this if the optical train was changed between nights.")
        _nofocus(self.chk_flats_by_date)
        layout.addWidget(self.chk_flats_by_date)

        parent_layout.addWidget(group)

    def _on_filter_mode_changed(self, mode: str) -> None:
        """Make the quality-filter spin boxes mean what the mode says.

        '% best' takes 1..100 (share of frames kept), 'k-sigma' takes a
        sigma multiple where anything past ~5 already rejects nothing.  A
        value left over from the other mode is replaced by that mode's
        sensible default rather than silently reinterpreted.
        """
        k_sigma = mode == "k-sigma"
        hi, default = (10, 3) if k_sigma else (100, 90)
        changed = False
        for spin in getattr(self, "_filter_spins", ()):
            old = spin.value()
            spin.setRange(1, hi)
            if old > hi:
                spin.setValue(default)
                changed = True
            spin.setSuffix(" σ" if k_sigma else " %")
        # This also runs once during construction, before the Log tab
        # exists -- and there is nothing to report at that point anyway.
        if changed and hasattr(self, "log_text"):
            self._log(
                f"Filter mode is now '{mode}' — the values were reset to "
                f"{default}{'σ' if k_sigma else '%'}; they were percentages."
                if k_sigma else
                f"Filter mode is now '{mode}' — the values were reset to "
                f"{default}%; they were sigma multiples.", LogColor.BLUE)

    def _on_calibrate_toggled(self, on: bool) -> None:
        for w in (self.btn_library, self.btn_library_clear,
                  self.chk_cosmetic, self.chk_flats_by_date):
            w.setEnabled(on)
        # The summary line states what will be applied, so it has to follow
        # the switch -- otherwise it keeps advertising masters that the run
        # will now ignore (or claims calibration is off after it was
        # switched back on).
        if self._groups:
            self._show_calib_summary()

    def _set_library(self, path: str) -> None:
        self._library = path or ""
        self.lbl_library.setText(self._library or "No library folder set.")

    def _clear_library(self) -> None:
        """Forget the library AND drop what was found in it.

        Without the re-scan the darks and bias from the old library stay in
        `self._calib` and would still be applied -- while the panel says
        "No library folder set."
        """
        if not self._library:
            return
        self._set_library("")
        self._log("Calibration library cleared.", LogColor.BLUE)
        if self._root:
            self._on_analyze()

    def _pick_library(self) -> None:
        start = self._library or self._root or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, "Select the calibration library folder", start)
        if path:
            self._set_library(path)
            self._log(f"Calibration library: {path}", LogColor.BLUE)
            if self._root:
                self._on_analyze()      # re-scan so the library is included

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

        self.chk_weighting = QCheckBox("Frame weighting")
        self.chk_weighting.setChecked(True)
        self.chk_weighting.setToolTip(
            "Weight the better sub-exposures higher during integration.  "
            "Improves SNR when frame quality varies.")
        _nofocus(self.chk_weighting)
        layout.addWidget(self.chk_weighting)

        wrow = QHBoxLayout()
        wrow.addWidget(QLabel("by:"))
        self.cmb_weight = QComboBox()
        self.cmb_weight.addItems(list(WEIGHT_TOKENS.keys()))
        self.cmb_weight.setToolTip(
            "• Weighted FWHM — sharpness scaled by the star count.  The best "
            "default for broadband (L R G B).\n"
            "• Noise — weights by measured background noise.  Better for "
            "narrowband (Ha / OIII / SII): those fields hold far fewer "
            "stars, so wFWHM penalises them for the filter, not the "
            "frame.\n"
            "• Number of stars — weights purely by detected stars; useful "
            "when transparency varied a lot during the night.")
        _nofocus(self.cmb_weight)
        self.chk_weighting.toggled.connect(self.cmb_weight.setEnabled)
        wrow.addWidget(self.cmb_weight, 1)
        layout.addLayout(wrow)

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
        # The spin boxes below carry a different quantity per mode -- a
        # percentage (1..100) or a sigma multiple (1..10).  Without the
        # range following the mode, "90" silently becomes "reject beyond
        # 90 sigma", i.e. no filtering at all, while the UI looks armed.
        self._filter_spins: list = []
        self.cmb_filter_mode.currentTextChanged.connect(
            self._on_filter_mode_changed)

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
            self._filter_spins.append(spin)
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
        # The handler only fires on a CHANGE, so the unit suffix has to be
        # applied once here -- otherwise the boxes show bare numbers until
        # the mode is toggled for the first time.
        self._on_filter_mode_changed(self.cmb_filter_mode.currentText())

        self.chk_output_norm = QCheckBox("Output normalization")
        self.chk_output_norm.setChecked(True)
        self.chk_output_norm.setToolTip(
            "Normalise the final integrated frame's background level.")
        _nofocus(self.chk_output_norm)
        layout.addWidget(self.chk_output_norm)

        self.chk_rejmap = QCheckBox("Save rejection map (QA)")
        self.chk_rejmap.setChecked(False)
        self.chk_rejmap.setToolTip(
            "Also write a map showing which pixels the integration rejected "
            "— handy for checking that rejection behaved (satellite trails "
            "should show up, the target should not).\n"
            f"The maps are collected into the {QA_DIRNAME}/ folder next to "
            "the masters.")
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

        self.chk_bg_rbf = QCheckBox("     use RBF instead of a polynomial")
        self.chk_bg_rbf.setChecked(False)
        self.chk_bg_rbf.setToolTip(
            "Model the background with radial basis functions rather than a "
            "first-degree polynomial.\n"
            "RBF follows gradients that change direction or strength across "
            "the frame (several light domes, a moon gradient crossing a "
            "light-pollution one); a degree-1 polynomial can only tilt the "
            "whole frame one way.\n"
            "Applies to the per-channel masters and the colour composite. "
            "The per-sub pass stays polynomial — that is Siril's "
            "recommendation for individual frames.\n"
            "Falls back to the polynomial automatically if your Siril "
            "refuses it.")
        _nofocus(self.chk_bg_rbf)
        self.chk_bg_master.toggled.connect(self.chk_bg_rbf.setEnabled)
        layout.addWidget(self.chk_bg_rbf)

        srow = QHBoxLayout()
        srow.addWidget(QLabel("     RBF smoothing:"))
        self.spin_bg_smooth = QSpinBox()
        self.spin_bg_smooth.setRange(0, 100)
        self.spin_bg_smooth.setValue(50)
        self.spin_bg_smooth.setSuffix(" %")
        self.spin_bg_smooth.setFixedWidth(80)
        self.spin_bg_smooth.setToolTip(
            "How rigid the RBF surface is.  Higher = smoother, follows only "
            "the large-scale gradient (safer around nebulosity); "
            "lower = follows smaller local variations.  50% is Siril's "
            "default.")
        _nofocus(self.spin_bg_smooth)
        self.chk_bg_rbf.toggled.connect(self.spin_bg_smooth.setEnabled)
        self.spin_bg_smooth.setEnabled(False)
        srow.addWidget(self.spin_bg_smooth)
        srow.addStretch()
        layout.addLayout(srow)

        self.chk_bg_extract = QCheckBox("Background extraction per sub-frame")
        self.chk_bg_extract.setChecked(False)
        self.chk_bg_extract.setToolTip(
            "Run seqsubsky (degree 1) on every individual light before "
            "registration.  Rarely needed — prefer 'per channel' above.  "
            "Off by default.")
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

        self.chk_palette_only = QCheckBox(
            "Stack only the filters this palette uses")
        self.chk_palette_only.setToolTip(
            "Skips the filters the composite never reads.  On an LRGB + "
            "Ha/OIII night set to HOO that is four of six channels, so the "
            "run takes about half as long.\n\n"
            "It also improves the colour image: Siril picks the "
            "cross-filter alignment reference itself from whatever masters "
            "are present, and a broadband one usually wins.  The narrowband "
            "channels then have to match a spectrally unrelated frame — "
            "measured on one M 16 run: OIII aligned on 12 star pairs and Ha "
            "on 22, against 188–476 for the broadband masters.  Leaving the "
            "unused filters out keeps the reference among the channels that "
            "end up in the picture.\n\n"
            "Off by default: a master that was never built cannot be reused "
            "when you switch palette later.")
        _nofocus(self.chk_palette_only)
        layout.addWidget(self.chk_palette_only)

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
            "reference so no single channel — usually the strong Ha — "
            "dominates and turns the result green.\n"
            "Turn this OFF when SPCC is doing the colour calibration: this "
            "flattens the Ha/OIII ratio on purpose, and that ratio is "
            "exactly what SPCC's narrowband mode measures against "
            "catalogue spectra. Doing both makes SPCC calibrate a "
            "difference that was already removed.\n"
            "Keep it ON when you are NOT calibrating (SPCC off, or no "
            "Gaia spectrophotometry catalog available).")
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
            lambda _on: self._on_compose_toggled(
                self.chk_compose.isChecked()))
        layout.addWidget(self.chk_finish)

        self.chk_spcc = QCheckBox("     use SPCC (sensor- and filter-aware)")
        self.chk_spcc.setChecked(True)
        self.chk_spcc.setToolTip(
            "Spectrophotometric Colour Calibration takes your sensor's and "
            "filters' response curves into account, which plain PCC cannot "
            "— Siril's documentation calls SPCC the more accurate method "
            "and PCC obsolete.\n"
            "It also brings the only colour calibration that works for "
            "SHO / HOO at all (narrowband mode, using each line's "
            "wavelength).\n"
            "Falls back to plain PCC automatically if SPCC is unavailable.")
        _nofocus(self.chk_spcc)
        self.chk_spcc.toggled.connect(
            lambda _on: self._on_compose_toggled(
                self.chk_compose.isChecked()))
        layout.addWidget(self.chk_spcc)

        self.lbl_spcc = QLabel(
            "     Mono sensor and filters (pre-filled; clear them to use "
            "Siril's own SPCC settings):")
        self.lbl_spcc.setStyleSheet("color:#888888;font-size:9pt;")
        self.lbl_spcc.setWordWrap(True)
        layout.addWidget(self.lbl_spcc)

        self.edit_spcc_sensor = QLineEdit()
        self.edit_spcc_sensor.setText(DEFAULT_SPCC_SENSOR)
        self.edit_spcc_sensor.setPlaceholderText(
            "Mono sensor, e.g. Sony IMX411/455/461/533/571")
        self.edit_spcc_sensor.setToolTip(
            "Pre-filled for a Player One Ares-M Pro (IMX533 mono).\n"
            "Your sensor as named in Siril's MONO table.  Watch out: many "
            "chips appear under a different name there than in the OSC "
            "table.  The IMX533 mono entry is\n"
            "    Sony IMX411/455/461/533/571\n"
            "while plain 'IMX533' only exists as an OSC sensor — entering "
            "that makes SPCC calibrate as one-shot colour, silently and "
            "with no error.\n"
            "The script checks your entry against the database Siril "
            "actually uses and says in the Log if it does not match.\n"
            "Leave everything blank to use Siril's own SPCC configuration.")
        layout.addWidget(self.edit_spcc_sensor)

        frow = QHBoxLayout()
        self.edit_spcc_r = QLineEdit(DEFAULT_SPCC_RFILTER)
        self.edit_spcc_r.setPlaceholderText("R filter, e.g. Baader R")
        self.edit_spcc_g = QLineEdit(DEFAULT_SPCC_GFILTER)
        self.edit_spcc_g.setPlaceholderText("G filter")
        self.edit_spcc_b = QLineEdit(DEFAULT_SPCC_BFILTER)
        self.edit_spcc_b.setPlaceholderText("B filter")
        for w in (self.edit_spcc_r, self.edit_spcc_g, self.edit_spcc_b):
            w.setToolTip(
                "Pre-filled with the Antlia LRGB V-Pro set.\n"
                "Filter names from Siril's mono table, e.g.:\n"
                "  Antlia R / G / B · Baader R / G / B\n"
                "  Chroma Red / Green / Blue · Optolong Red / Green / Blue\n"
                "  Astronomik Typ 2 c Red / Green / Blue\n"
                "  ZWO Optimized for CMOS Red / Green / Blue\n"
                "  Astrodon Red (E series) / Red (I series) / ...\n"
                "Give all three to describe the rig completely; the script "
                "checks each one against Siril's database.\n"
                "Ignored for narrowband palettes, which are described by "
                "wavelength instead.")
            frow.addWidget(w, 1)
        layout.addLayout(frow)

        nrow = QHBoxLayout()
        nrow.addWidget(QLabel("     Narrowband filter bandwidth:"))
        # Fractional bandwidths are the norm, not the exception: 3.5, 4.5
        # and 6.5 nm are all common filter specs, so an integer box would
        # make them unenterable.
        self.spin_nb_bw = QDoubleSpinBox()
        self.spin_nb_bw.setDecimals(1)
        self.spin_nb_bw.setSingleStep(0.5)
        self.spin_nb_bw.setRange(0.5, 50.0)
        self.spin_nb_bw.setValue(DEFAULT_NB_BANDWIDTH)
        self.spin_nb_bw.setSuffix(" nm")
        self.spin_nb_bw.setFixedWidth(85)
        self.spin_nb_bw.setToolTip(
            "The bandwidth of your Ha / OIII / SII filters, used by SPCC's "
            "narrowband mode.  Typical values are 3, 3.5, 4.5, 6 or 7 nm — "
            "take it from your filter's spec sheet.  Pre-filled with 4.5 "
            "for the Antlia Edge SHO set.\n"
            "Siril has no named entries for narrowband filters, so this "
            "number plus the fixed line wavelengths (Ha 656.3, OIII 500.7, "
            "SII 671.6 nm) IS the whole filter description.")
        _nofocus(self.spin_nb_bw)
        nrow.addWidget(self.spin_nb_bw)
        nrow.addStretch()
        layout.addLayout(nrow)

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

        Used by the .json preset export/import so a saved preset covers every
        option, not just the handful a built-in profile sets.  Filesystem
        paths are deliberately absent: the calibration library lives on one
        machine, and baking it into a shared preset would point someone
        else's run at a folder that does not exist.  Rig descriptions (the
        SPCC sensor and filter names) are included -- those travel with the
        recipe, not with the machine.
        """
        w = {
            "filter_mode": self.cmb_filter_mode,
            "f_wfwhm_val": self.spin_keep,
            "f_round_val": self.spin_f_round,
            "f_stars_val": self.spin_f_stars,
            "f_bkg_val": self.spin_f_bkg,
            "calibrate": self.chk_calibrate,
            "cosmetic": self.chk_cosmetic,
            "flats_by_date": self.chk_flats_by_date,
            "crop_edges": self.chk_crop_edges,
            "palette_only": self.chk_palette_only,
            "output_norm": self.chk_output_norm,
            "rejmap": self.chk_rejmap,
            "bg_extract": self.chk_bg_extract,
            "platesolve_reg": self.chk_platesolve_reg,
            "disto_master": self.chk_disto,
            "drizzle": self.cmb_drizzle,
            "weight_method": self.cmb_weight,
            "bg_rbf": self.chk_bg_rbf,
            "bg_smooth": self.spin_bg_smooth,
            "use_spcc": self.chk_spcc,
            "nb_bandwidth": self.spin_nb_bw,
            # Rig-specific, not machine-specific: exactly what someone would
            # want to hand over together with the rest of the recipe.
            "spcc_sensor": self.edit_spcc_sensor,
            "spcc_rfilter": self.edit_spcc_r,
            "spcc_gfilter": self.edit_spcc_g,
            "spcc_bfilter": self.edit_spcc_b,
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
            elif isinstance(w, QDoubleSpinBox):
                data["settings"][key] = float(w.value())
            elif isinstance(w, QSpinBox):
                data["settings"][key] = int(w.value())
            elif isinstance(w, QComboBox):
                data["settings"][key] = w.currentText()
            elif isinstance(w, QLineEdit):
                data["settings"][key] = w.text().strip()
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
            # The filter mode sets the spin boxes' range, so it has to be
            # applied before their values -- JSON key order is whatever the
            # file happens to carry.
            ordered = sorted(settings.items(),
                             key=lambda kv: kv[0] != "filter_mode")
            for key, value in ordered:
                w = widgets.get(key)
                if w is None:
                    unknown += 1
                    continue
                try:
                    if isinstance(w, QCheckBox):
                        w.setChecked(bool(value))
                    elif isinstance(w, QDoubleSpinBox):
                        w.setValue(float(value))
                    elif isinstance(w, QSpinBox):
                        w.setValue(int(value))
                    elif isinstance(w, QComboBox):
                        # Ignore values this version doesn't offer.
                        if w.findText(str(value)) >= 0:
                            w.setCurrentText(str(value))
                        else:
                            unknown += 1
                            continue
                    elif isinstance(w, QLineEdit):
                        w.setText(str(value).strip())
                    else:
                        # A widget type this loader cannot set.  Counting it
                        # as applied would report a setting as restored that
                        # was silently dropped.
                        unknown += 1
                        continue
                    applied += 1
                except (TypeError, ValueError):
                    unknown += 1
            # Every dependent enable-state has to follow the loaded values,
            # or a preset that switches calibration off leaves its sub-options
            # clickable and the panel lying about what will run.
            self._on_compose_toggled(self.chk_compose.isChecked())
            self._on_palette_changed()
            self._on_calibrate_toggled(self.chk_calibrate.isChecked())
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
        for w in (self.cmb_palette, self.chk_palette_only,
                  self.cmb_map_lum, self.cmb_map_red,
                  self.cmb_map_green, self.cmb_map_blue, self.chk_nb_norm,
                  self.chk_quick_lrgb, self.chk_finish):
            w.setEnabled(on)
        # Everything below auto-finish only means anything while it runs.
        fin = on and self.chk_finish.isChecked()
        self.chk_finish_stretch.setEnabled(fin)
        self.chk_spcc.setEnabled(fin)
        spcc = fin and self.chk_spcc.isChecked()
        for w in (self.lbl_spcc, self.edit_spcc_sensor, self.edit_spcc_r,
                  self.edit_spcc_g, self.edit_spcc_b, self.spin_nb_bw):
            w.setEnabled(spcc)

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
        # Say it NOW, not after a full stack: the filter list is already
        # known, so a palette that cannot be filled is knowable here.
        missing = [r for r in ("red", "green", "blue") if not mapping.get(r)]
        if missing and self.chk_compose.isChecked():
            wants = ", ".join(
                f"{r.upper()} ← {_PALETTE_SOURCE.get(palette, {}).get(r, '?')}"
                for r in missing)
            better = _detect_palette(filters)
            self._log(
                f"{palette} cannot be built from these filters — {wants}. "
                + (f"Choose {better}, " if better != palette else "")
                + "map the channel by hand, or the run will stack the "
                "masters and then skip the colour image.", LogColor.SALMON)

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
    def _seed_rig_defaults(self) -> None:
        """Write the shipped rig description into the stored settings once.

        A QSettings default only applies to a key that is ABSENT.  Anyone
        who ran an earlier version already has these keys saved -- as empty
        strings, and with the old 7 nm bandwidth -- so the new defaults
        would never appear no matter what fallback is passed.

        Seeding is guarded by a flag, so it happens exactly once: after
        that the fields are the user's to change, and clearing them keeps
        working as "use Siril's own SPCC configuration".
        """
        st = self._settings
        if st.value("spcc_seeded", False, type=bool):
            return
        for key, val in (("spcc_sensor", DEFAULT_SPCC_SENSOR),
                         ("spcc_rfilter", DEFAULT_SPCC_RFILTER),
                         ("spcc_gfilter", DEFAULT_SPCC_GFILTER),
                         ("spcc_bfilter", DEFAULT_SPCC_BFILTER),
                         ("nb_bandwidth", DEFAULT_NB_BANDWIDTH)):
            st.setValue(key, val)
        st.setValue("spcc_seeded", True)

    def _load_settings(self) -> None:
        st = self._settings
        self._seed_rig_defaults()
        self.chk_skip_blank.setChecked(st.value("skip_blank", True, type=bool))
        self.chk_rejection.setChecked(st.value("rejection", True, type=bool))
        self.chk_weighting.setChecked(st.value("weighting", True, type=bool))
        self.cmb_weight.setCurrentText(
            str(st.value("weight_method", "Weighted FWHM")))
        self.chk_bg_rbf.setChecked(st.value("bg_rbf", False, type=bool))
        self.spin_bg_smooth.setValue(int(st.value("bg_smooth", 50)))
        self.chk_spcc.setChecked(st.value("use_spcc", True, type=bool))
        self.edit_spcc_sensor.setText(
            str(st.value("spcc_sensor", DEFAULT_SPCC_SENSOR)))
        self.edit_spcc_r.setText(
            str(st.value("spcc_rfilter", DEFAULT_SPCC_RFILTER)))
        self.edit_spcc_g.setText(
            str(st.value("spcc_gfilter", DEFAULT_SPCC_GFILTER)))
        self.edit_spcc_b.setText(
            str(st.value("spcc_bfilter", DEFAULT_SPCC_BFILTER)))
        self.spin_nb_bw.setValue(
            float(st.value("nb_bandwidth", DEFAULT_NB_BANDWIDTH)))
        # Mode BEFORE the values: it decides the spin boxes' range, and a
        # percentage restored into a k-sigma range would be clamped to 10.
        self.cmb_filter_mode.setCurrentText(
            str(st.value("filter_mode", "% best")))
        self.spin_keep.setValue(int(st.value("f_wfwhm_val", 90)))
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
        self.chk_palette_only.setChecked(
            st.value("palette_only", False, type=bool))
        self.chk_bg_master.setChecked(st.value("bg_master", True, type=bool))
        self.chk_bg_extract.setChecked(st.value("bg_extract", False, type=bool))
        self.chk_platesolve_reg.setChecked(
            st.value("platesolve_reg", False, type=bool))
        self.chk_copy.setChecked(st.value("copy", False, type=bool))
        self.chk_align_filters.setChecked(
            st.value("align_filters", True, type=bool))
        self.chk_platesolve_master.setChecked(
            st.value("platesolve_master", False, type=bool))
        self.chk_calibrate.setChecked(st.value("calibrate", True, type=bool))
        self.chk_cosmetic.setChecked(st.value("cosmetic", True, type=bool))
        self.chk_flats_by_date.setChecked(
            st.value("flats_by_date", False, type=bool))
        self._set_library(str(st.value("calib_library", "")))
        self._on_calibrate_toggled(self.chk_calibrate.isChecked())
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
        st.setValue("weight_method", self.cmb_weight.currentText())
        st.setValue("bg_rbf", self.chk_bg_rbf.isChecked())
        st.setValue("bg_smooth", int(self.spin_bg_smooth.value()))
        st.setValue("use_spcc", self.chk_spcc.isChecked())
        st.setValue("spcc_sensor", self.edit_spcc_sensor.text().strip())
        st.setValue("spcc_rfilter", self.edit_spcc_r.text().strip())
        st.setValue("spcc_gfilter", self.edit_spcc_g.text().strip())
        st.setValue("spcc_bfilter", self.edit_spcc_b.text().strip())
        st.setValue("nb_bandwidth", float(self.spin_nb_bw.value()))
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
        st.setValue("palette_only", self.chk_palette_only.isChecked())
        st.setValue("bg_master", self.chk_bg_master.isChecked())
        st.setValue("bg_extract", self.chk_bg_extract.isChecked())
        st.setValue("platesolve_reg", self.chk_platesolve_reg.isChecked())
        st.setValue("copy", self.chk_copy.isChecked())
        st.setValue("align_filters", self.chk_align_filters.isChecked())
        st.setValue("platesolve_master", self.chk_platesolve_master.isChecked())
        st.setValue("calibrate", self.chk_calibrate.isChecked())
        st.setValue("cosmetic", self.chk_cosmetic.isChecked())
        st.setValue("flats_by_date", self.chk_flats_by_date.isChecked())
        st.setValue("calib_library", self._library)
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
        # Drop everything the previous scan produced.  If this analysis fails
        # (_on_analyze_done never runs), leftovers would otherwise describe
        # the old folder -- stale calibration masters and a stale
        # multiple-target warning.
        self._groups = {}
        self._calib = {}
        self._multi_target = []
        self.tbl_filters.setRowCount(0)
        self._set_left_enabled(False)
        self.lbl_header.setText(f"Analyzing: {self._root}")
        self._set_status("Scanning for light frames…")
        self._log(f"Analyzing folder: {self._root}", LogColor.BLUE)

        # The library is scanned regardless of the "Apply calibration" switch:
        # that switch decides whether the masters are USED, and tying
        # discovery to it means toggling it after an analysis leaves _calib
        # silently incomplete.  Reading a few extra headers is cheap.
        self._analyze_worker = AnalyzeWorker(self._root, self._library)
        self._analyze_worker.progress.connect(self._on_progress)
        self._analyze_worker.finished.connect(self._on_analyze_done)
        self._analyze_worker.failed.connect(self._on_worker_failed)
        self._analyze_worker.start()

    def _show_calib_summary(self, unsupported: int = 0) -> None:
        """Report what calibration material the scan turned up."""
        if unsupported:
            self._log(
                f"{unsupported} XISF file(s) found and skipped — that format "
                "is not supported (its headers cannot be read).",
                LogColor.SALMON)
        if not self.chk_calibrate.isChecked():
            self.lbl_calib_found.setText("Calibration is switched off.")
            return
        c = self._calib or {}
        bits = []
        for kind, label in ((KIND_FLAT, "flats"),
                            (KIND_DARKFLAT, "dark-flats"),
                            (KIND_DARK, "darks"), (KIND_BIAS, "bias")):
            groups = c.get(kind) or {}
            if not groups:
                continue
            frames = sum(len(g["files"]) for g in groups.values())
            unit = "filter" if kind in (KIND_FLAT, KIND_DARKFLAT) else "set"
            plural = "" if len(groups) == 1 else "s"
            bits.append(f"{label}: {len(groups)} {unit}{plural} "
                        f"({frames} frames)")
        if bits:
            self.lbl_calib_found.setText(" · ".join(bits))
            self._log("Calibration found — " + " · ".join(bits),
                      LogColor.GREEN)
        else:
            hint = ("" if self._library
                    else "  Set a Library folder for darks / bias.")
            self.lbl_calib_found.setText(
                "No calibration frames found." + hint)

    def _on_analyze_done(self, payload: dict) -> None:
        self._groups = payload["groups"]
        self._target = payload["target"]
        total = payload["total"]
        objects = payload.get("objects", [])
        self._calib = payload.get("calib", {}) or {}
        self._show_calib_summary(payload.get("unsupported", 0))
        if payload.get("stray_lights"):
            self._log(
                f"{payload['stray_lights']} light frame(s) in the library / "
                "neighbouring calibration folders were ignored — only "
                "calibration frames are taken from outside the target "
                "folder.", LogColor.SALMON)

        self._set_left_enabled(True)

        self.lbl_target.setText(f"Target: {self._target}")

        # Frames from two different objects must never be pooled into one
        # stack -- that silently produces garbage.  Warn loudly.  Compared
        # normalised, so "M 101" and "M101" don't raise a false alarm.
        distinct = {_object_key(o) for o in objects if _object_key(o)}
        self._multi_target = objects if len(distinct) > 1 else []
        if self._multi_target:
            names = ", ".join(objects)
            self._log(
                f"WARNING: {len(distinct)} different targets found ({names}). "
                "Their frames would be stacked together!", LogColor.RED)
            QMessageBox.warning(
                self, "More than one target in this folder",
                f"The selected folder contains frames of {len(distinct)} "
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
            f"<p>Scanned <b>{payload.get('in_target', total)}</b> "
            "FITS file(s) under:<br>"
            f"<span style='color:#888;'>{self._root}</span>"
            + (f"<br>plus <b>{payload['outside']}</b> calibration file(s) "
               "from the library / neighbouring folders."
               if payload.get("outside") else "")
            + "</p>"
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
        # Last, so that a "this palette cannot be built from these filters"
        # warning appears BELOW the list of filters it is talking about.
        self._populate_compose_combos()

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
            "calibrate": self.chk_calibrate.isChecked(),
            "cosmetic": self.chk_cosmetic.isChecked(),
            "flats_by_date": self.chk_flats_by_date.isChecked(),
            "calib_library": self._library,
            "skip_blank": self.chk_skip_blank.isChecked(),
            "rejection": self.chk_rejection.isChecked(),
            "weighting": self.chk_weighting.isChecked(),
            "weight_method": self.cmb_weight.currentText(),
            "bg_rbf": self.chk_bg_rbf.isChecked(),
            "bg_smooth": int(self.spin_bg_smooth.value()),
            "use_spcc": self.chk_spcc.isChecked(),
            "spcc_sensor": self.edit_spcc_sensor.text().strip(),
            "spcc_rfilter": self.edit_spcc_r.text().strip(),
            "spcc_gfilter": self.edit_spcc_g.text().strip(),
            "spcc_bfilter": self.edit_spcc_b.text().strip(),
            "nb_bandwidth": float(self.spin_nb_bw.value()),
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
            "palette_only": self.chk_palette_only.isChecked(),
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
        # Says "discovered", not "stacking": the palette may leave some
        # of them out, and the worker is the one that knows which.
        self._log(f"Starting run — {len(self._groups)} filter(s) discovered, "
                  f"output to {out_dir}", LogColor.GREEN)

        self._stack_worker = StackWorker(
            self.siril, self._groups, self._target, out_dir,
            self._ext, self._current_opts(), self._calib)
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
        aborted = payload.get("aborted", False)
        compose_wanted = payload.get("compose_wanted", False)
        self._set_left_enabled(True)
        self.progress.setValue(100)

        n_ok = len(results)
        n_err = len(errors)
        self.lbl_header.setText(
            ("Stopped: " if aborted
             else "Masters only: " if compose_wanted and not composite
             else "Done: ")
            + f"{n_ok} master(s) written"
            + (", cross-filter aligned" if aligned else "")
            + (", colour composite" if composite else "")
            + (f", {n_err} filter(s) failed." if n_err else "."))
        self._set_status(
            (f"Stopped: {n_ok} master(s) finished before the abort."
             if aborted else f"Finished: {n_ok} ok, {n_err} failed."))

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

        if aborted:
            # "All done" after the user pressed stop would be a plain lie.
            self._log(
                f"Stopped by request: {n_ok} master(s) were finished and "
                "kept. Re-run with 'Reuse existing masters' to stack the "
                "rest and compose.", LogColor.SALMON)
        elif compose_wanted and not composite:
            # The colour image was the point of the run; "0 failed" would
            # read as success when the requested result is missing.
            self._log(
                f"Finished with {n_ok} master(s), but NO colour image — see "
                "the reason above. The masters are usable; fix the palette "
                "or the channel mapping and re-run with 'Reuse existing "
                "masters' to compose in seconds.", LogColor.SALMON)
        else:
            self._log(f"All done: {n_ok} master(s) written, {n_err} failed."
                      + (f" Composite: {os.path.basename(composite)}"
                         if composite else ""), LogColor.GREEN)
        if results:
            QMessageBox.information(
                self, "ImageMono Train",
                (f"Stopped after {n_ok} filter(s).\n\n"
                 "Those masters are complete and kept. The remaining "
                 "filters were not stacked, and alignment and the colour "
                 "image were skipped.\n\nRe-run with 'Reuse existing "
                 "masters' to continue where this left off.\n"
                 if aborted else
                 f"Stacked {n_ok} filter(s) successfully.\n\n"
                 + ("Cross-filter aligned masters are in masters/.\n"
                    if aligned else "")
                 + (f"Colour composite: {os.path.basename(composite)} "
                    "(loaded in Siril).\n" if composite else ""))
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
            "fallback.  Frames whose type is dark / flat / dark-flat / bias "
            "are collected separately and used for <b>calibration</b> (see "
            "the <i>Calibration</i> tab).  The same filter spread across "
            "several nights is pooled into a single stack.</p>"
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
            "<tr><td><b>calibrate</b> <i>(optional)</i></td>"
            "<td>Subtracts the master dark and divides by the master flat "
            "(plus cosmetic correction).  Runs only for the masters that "
            "were actually found — see the <i>Calibration</i> tab.</td></tr>"
            "<tr><td><b>seqsubsky</b> <i>(optional)</i></td>"
            "<td>Background / gradient extraction on every sub before "
            "registration.  Off by default.</td></tr>"
            "<tr><td><b>register −2pass</b></td>"
            "<td>Two-pass star registration picks the best reference and "
            "aligns all frames (or plate-solve registration if enabled; it "
            "falls back to star alignment automatically).<br>"
            "Note that <b>-2pass chooses that reference itself</b>, from "
            "whatever is in the sequence — that is the whole point of the "
            "preliminary pass, and <tt>setref</tt> cannot override it.  It "
            "is why <i>Stack only the filters this palette uses</i> improves "
            "the colour image and not just the runtime (see "
            "<i>Palettes</i>).<br>"
            "If this step fails, the run falls back to single-pass "
            "registration — which knows neither <tt>-framing=</tt> nor any "
            "<tt>-filter-</tt> option, so the crop and the quality filters "
            "cannot be honoured there.  What was given up is recorded per "
            "channel and named in the report, never silently dropped.  A "
            "failure of <tt>seqapplyreg</tt> is handled separately, because "
            "by then registration has already succeeded and it says nothing "
            "about two-pass support.</td></tr>"
            "<tr><td><b>seqapplyreg</b></td>"
            "<td>Applies the registration.  <i>min</i> framing (default) "
            "crops the ragged stacking edges; <i>max</i> keeps the full "
            "field.  Drizzle when selected.<br>"
            "A sub without enough detectable stars (clouds, haze) cannot be "
            "matched and Siril leaves it out here.  The script counts the "
            "frames Siril really exported, so everything downstream — the "
            "rejection tier, the weighting, the report — follows the number "
            "that is actually integrated, and the log says how many were "
            "lost and why.</td></tr>"
            "<tr><td><b>stack</b></td>"
            "<td>Rejection integration with additive+scaling normalisation, "
            "your chosen frame weighting and 32-bit output.</td></tr>"
            "<tr><td><b>subsky</b> (per channel)</td>"
            "<td>Background / gradient removed from each linear master "
            "before the channels are combined — degree-1 polynomial, or RBF "
            "when you enable it.</td></tr>"
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
            f"<li><b>21 – {GESDT_MIN_FRAMES - 1} frames</b> → linear-fit "
            "clipping (3σ / 3σ) — handles gradients between subs well</li>"
            f"<li><b>≥ {GESDT_MIN_FRAMES} frames</b> → <b>GESDT</b> "
            "(Generalized Extreme Studentized Deviate Test), which Siril "
            "documents as excelling on large stacks.  Its two numbers are "
            "<i>not</i> sigmas: <tt>0.3</tt> caps the fraction of the stack "
            "that may be rejected, <tt>0.05</tt> is the significance "
            "threshold.  If your Siril build does not know it, the run "
            "falls back to linear fit and says so.</li>"
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
            "<li><b>Frame weighting</b> — lets the better subs contribute "
            "more, for better SNR.  Pick the criterion in the <b>by:</b> "
            "box: <i>Weighted FWHM</i> (sharpness scaled by star count — "
            "the right default for L R G B), <i>Noise</i> (measured "
            "background noise — the better choice for <b>narrowband</b>, "
            "where a sparse star field would otherwise be penalised for the "
            "filter rather than for the frame), or <i>Number of stars</i> "
            "(when transparency varied a lot).</li>"
            "<li><b>Frame quality filters</b> — drop bad subs "
            "<i>before</i> they are registered.  Tick any of "
            "<b>Weighted FWHM</b> (softness), <b>Roundness</b> (guiding "
            "errors / wind), <b>Star count</b> (clouds, haze) or "
            "<b>Background level</b> (moonlight, twilight).  "
            "<b>Mode</b> decides how the numbers are read: "
            "<i>% best</i> keeps that share of the best frames (1–100), "
            "<i>k-sigma</i> rejects beyond k standard deviations (1–10).  "
            "Switching the mode re-ranges the boxes, and a value left over "
            "from the other meaning is reset — 90 as a sigma multiple would "
            "reject nothing at all.  "
            f"Applied only from <b>{FILTER_MIN_FRAMES} frames</b> per "
            "filter: every dropped sub costs signal-to-noise (noise scales "
            "with 1/√n), and on a short run that loss outweighs what "
            "removing the worst frame gains — a real 8→6 frame test raised "
            "the background noise by 19%.  Above the threshold the log warns "
            "when the filters drop more than 15% of a set.</li>"
            "<li><b>Crop stacking edges (min framing)</b> — keep only the "
            "area every sub covers, so the master has no ragged, "
            "low-signal border.  Dithering offsets the subs by a few "
            "pixels, so this costs a thin strip (a real run: 3008&nbsp;px "
            "→ 2991&nbsp;px).  Off keeps the full field with partly "
            "exposed edges.  This is a framing choice inside "
            "<tt>seqapplyreg</tt>, not a crop applied afterwards — the "
            "script never trims to taste, that belongs in "
            "<tt>todo.md</tt>.</li>"
            "<li><b>Output normalization</b> — normalises the final "
            "frame's background level.</li>"
            "<li><b>Save rejection map</b> — QA artifact of what was "
            "rejected.</li>"
            "<li><b>Background extraction per channel</b> — flattens the "
            "gradient on each finished, still-linear master.  Tick <b>use "
            "RBF instead of a polynomial</b> when the gradient changes "
            "direction or strength across the frame (several light domes, a "
            "moon gradient crossing a light-pollution one): a degree-1 "
            "polynomial can only tilt the whole frame one way, RBF follows "
            "the shape.  <b>RBF smoothing</b> sets how rigid that surface "
            "is — higher stays on the large scale and is safer around "
            "nebulosity.  Falls back to the polynomial if your Siril "
            "refuses RBF.</li>"
            "<li><b>Background extraction per sub-frame</b> — flattens "
            "gradients on every light before registration.  Stays a "
            "degree-1 polynomial deliberately: that is Siril's "
            "recommendation for individual frames.</li>"
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
            "<li><b>Drizzle</b> — 2× / 3× upsampling.  It redistributes each "
            "sub's flux onto a finer grid, which only works if the subs were "
            "<b>dithered</b> during acquisition and there are enough of "
            f"them: below about <b>{DRIZZLE_MIN_FRAMES} frames</b> the grid "
            "stays unevenly filled and the master usually comes out noisier "
            "than an undrizzled one.  The log and the report warn when that "
            "happens.  Also makes much larger files.</li>"
            "<li><b>Copy frames</b> — copy instead of symlink, for "
            "drives where symlinks are not permitted.</li>"
            "<li><b>Align filters (LRGB)</b> — put all masters on one "
            "shared grid; writes the aligned masters to masters/.</li>"
            "<li><b>Plate-solve final masters</b> — tag each master with "
            "a WCS solution, for later annotation or mosaicking.  "
            "<tt>rgbcomp</tt> then copies that solution into the colour "
            "image, so the finish step finds it already solved and skips "
            "its own plate-solve; the report says which of the two "
            "happened.</li>"
            "<li><b>Load final stack into Siril</b> — open the result when "
            "the run ends (the colour image if one was made, otherwise the "
            "last master).  Turn it off for unattended batches.</li>"
            "<li><b>Clear log before each run</b> — empty the Log tab when "
            "stacking starts, so what you see belongs to this run only.  "
            "Siril's own console keeps everything either way.</li>"
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
            "<h3 style='color:#88aaff;'>Stack only the filters this "
            "palette uses</h3>"
            "<p>An LRGB night that you process as HOO stacks four masters "
            "the composite never opens.  With this box ticked they are "
            "skipped, which roughly halves the run \u2014 and, less "
            "obviously, improves the picture.</p>"
            "<p>The cross-filter alignment puts every master into one "
            "sequence and lets Siril\u2019s two-pass registration choose "
            "the reference; <span style='font-family:monospace;"
            "color:#aaddaa;'>setref</span> cannot override that, because "
            "<b>-2pass</b> exists precisely to \u201cfind a good reference "
            "image\u201d of its own.  A star-rich broadband master normally "
            "wins, and the narrowband channels then have to match a frame "
            "whose stars they largely do not share.  Measured on one "
            "M\u00a016 run: OIII matched on <b>12</b> star pairs and Ha on "
            "<b>22</b>, "
            "against <b>188\u2013476</b> for the broadband masters.  A fit "
            "resting on twelve points carries its scale term poorly, which "
            "is what puts colour fringes in the corners.</p>"
            "<p>Leaving the unused filters out puts only the composite\u2019s "
            "own channels in that pool, so the reference is one of them.  "
            "The box is <b>off</b> by default: a master that was never built "
            "cannot be reused when you switch palette later, and the run "
            "refuses to skip anything that would leave fewer than two "
            "channels.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Narrowband (SHO / HOO) order</h3>"
            "<p>Following Siril's guidance for narrowband, the channels are "
            "<b>normalized before combining</b> — each is linear-matched to "
            "the Ha reference (<tt>linear_match</tt>) so the strong Ha "
            "doesn't dominate and turn the result green.  Then they are "
            "combined <b>linearly</b>; you stretch and fine-tune colour "
            "afterwards.  Normalized copies (<span style='font-family:"
            "monospace;color:#aaddaa;'>*_nbnorm</span>) are written under "
            "<tt>_work/helpers/</tt> so the masters stay untouched.</p>"
            "<p style='color:#ffb0a0;'><b>Do not combine it with SPCC.</b>  "
            "Normalisation flattens the Ha / OIII flux ratio on purpose — "
            "and that ratio is precisely what SPCC's narrowband mode "
            "measures against catalogue spectra in order to calibrate it.  "
            "Running both makes SPCC correct a difference that was already "
            "removed; on one HOO run the R/G fit came out at sigma 5.8, "
            "against 1.4 for a broadband composite of the same night.  "
            "Switch <b>Normalize narrowband channels</b> off when SPCC is "
            "calibrating, and on when it is not.  The script says so in the "
            "Log and in the report when it sees both.</p>"
            "<p>PCC is "
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
            "<li><b>Plate-solve</b> the colour image — every colour "
            "calibration method needs astrometry.</li>"
            "<li><b>Background extraction</b> (subsky) to flatten "
            "gradients.</li>"
            "<li><b>Colour calibration</b> — see the chain below.</li>"
            "<li><b>SCNR</b> green-cast removal.</li>"
            "</ol>"
            "<h3 style='color:#88aaff;'>Colour calibration: SPCC, then PCC"
            "</h3>"
            "<p><b>SPCC</b> (Spectrophotometric Colour Calibration) takes "
            "your <i>sensor's and filters' response curves</i> into account; "
            "Siril's own documentation calls it the more accurate method and "
            "PCC obsolete.  For a mono rig behind a filter wheel that "
            "distinction matters — plain PCC assumes generic broadband "
            "R/G/B.</p>"
            "<p><b>Narrowband gets calibrated too.</b>  With SHO or HOO the "
            "script runs SPCC in <b>narrowband mode</b>, describing each "
            "mapped channel by its emission line — Ha 656.3, OIII 500.7, "
            "SII 671.6 nm — plus the bandwidth you set.  Ordinary star "
            "photometry is meaningless there, so PCC is never attempted for "
            "these palettes; without SPCC they stay uncalibrated, as "
            "before.</p>"
            "<p>The <b>sensor name is sent in narrowband mode too</b>.  "
            "Siril\u2019s own help says <tt>-narrowband</tt> makes it ignore "
            "\u201cthe previous <i>filter</i> arguments\u201d — filters "
            "only.  "
            "That is physics, not a quirk: the wavelengths describe the "
            "filter passbands, while the sensor\u2019s quantum efficiency at "
            "656 and 501 nm is an independent factor in the same product.  "
            "The filter <i>names</i> are deliberately left out there, and "
            "the log says so, because Siril echoes its stored names on every "
            "run and they look as if they had been used.</p>"
            "<p>The chain degrades one step at a time and never aborts the "
            "finish:</p>"
            "<ol>"
            "<li><b>SPCC</b> with your sensor / filter names (or the "
            "narrowband wavelengths)</li>"
            "<li><b>SPCC</b> bare — uses whatever is configured in Siril's "
            "own preferences</li>"
            "<li><b>PCC</b> (NOMAD catalog) — broadband palettes only</li>"
            "<li><b>PCC</b> against a local Gaia catalog — works offline</li>"
            "<li>give up, and say so plainly in the report and in "
            "<tt>todo.md</tt></li>"
            "</ol>"
            "<p>The sensor and filter fields are optional, but the names "
            "must come from Siril's <b>mono</b> tables — and several chips "
            "are listed there under a different name than in the OSC "
            "tables.  The IMX533 is the classic trap: the mono entry is "
            "<tt>Sony IMX411/455/461/533/571</tt>, while plain "
            "<tt>IMX533</tt> exists <i>only</i> as an OSC sensor, so "
            "entering that makes SPCC calibrate your filter-wheel data as "
            "though it came from a colour camera — silently, with no "
            "error.</p>"
            "<p><b>Quoting matters.</b>  Siril re-splits the command line "
            "shell-style, so the quotes have to wrap the <i>whole</i> "
            "argument — <tt>\"-rfilter=Antlia R\"</tt>, not "
            "<tt>-rfilter=\"Antlia R\"</tt>, which aborts with "
            "<i>Invalid argument</i>.  The script does this for you; the "
            "exact line it sends is printed in the Log.</p>"
            "<p>Bare <tt>spcc</tt> without any arguments only works once "
            "you have run SPCC from Siril's own dialog at least once — that "
            "is where those defaults come from.  On a fresh install it "
            "fails and the chain falls through to PCC.</p>"
            "<p>The script reads the SPCC database Siril actually uses and "
            "reports in the Log when a name does not match, listing "
            "candidates.  Leave the fields blank to use your own Siril SPCC "
            "configuration.</p>"
            "<p>Three outcomes, all before the run reaches SPCC:</p>"
            "<ul>"
            "<li><b>exact hit</b> — nothing is said, the name goes through "
            "as typed;</li>"
            "<li><b>one partial match</b> — the Log names what Siril should "
            "resolve it to (<tt>IMX411</tt> → "
            "<tt>Sony IMX411/455/461/533/571</tt>);</li>"
            "<li><b>several matches or none</b> — the candidates are listed, "
            "or you are told the name is absent from the mono table.  The "
            "script never picks one for you: which of several Siril takes "
            "is Siril's decision.</li>"
            "</ul>"
            "<p style='color:#888;'>The check reads Siril's own SPCC "
            "database, read-only, at the location sirilpy reports.  If it "
            "cannot be found the check is simply skipped — a database the "
            "script cannot see means <i>cannot check</i>, never <i>invalid "
            "name</i>.  The calibration itself never uses this data: the "
            "names go to Siril, which does its own lookup.</p>"
            "<p>The fields come <b>pre-filled</b> for the rig this script "
            "was written on — a <b>Player One Ares-M Pro</b> (IMX533 mono) "
            "with <b>Antlia LRGB V-Pro</b> and <b>Antlia 4.5&nbsp;nm Edge "
            "SHO</b> filters:</p>"
            "<pre style='color:#aaddaa'>sensor  Sony IMX411/455/461/533/571\n"
            "R G B   Antlia R · Antlia G · Antlia B\n"
            "NB bw   4.5 nm</pre>"
            "<p>Different kit?  Overwrite them — your entries are "
            "remembered — or change the <tt>DEFAULT_SPCC_*</tt> constants "
            "near the top of the script.  Either way the names are checked "
            "against Siril's database before the run.</p>"
            "<p><b>HaRGB is excluded</b> from photometric calibration "
            "entirely: its Red channel carries blended Ha, so the star "
            "colours are no longer physical.  Balance it by hand.</p>"
            "<p>The result stays <b>linear</b> — saved over the composite, "
            "ready for your own stretch.  Tick <b>+ save stretched "
            "preview</b> to also get an autostretched "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_PALETTE_preview</span> for a quick look; the linear "
            "file is left untouched for serious processing.</p>")
        tabs.addTab(tab2, "The Pipeline")

        tab_cal = QTextEdit()
        tab_cal.setReadOnly(True)
        tab_cal.setHtml(
            "<h2 style='color:#88aaff;'>Calibration — Darks, Flats, Bias</h2>"
            "<p>Calibration removes what the <i>camera and optics</i> add to "
            "every frame, before any stacking happens.  Siril computes</p>"
            "<p style='font-family:monospace;color:#aaddaa;"
            "text-align:center;'>"
            "Lc = (L − D) / (F − O)</p>"
            "<p>L = light, D = master dark, F = master flat, O = master "
            "offset (bias).  Everything is <b>optional and additive</b>: the "
            "script uses whatever it finds and silently skips the rest — with "
            "no calibration frames at all it behaves exactly as before.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Which frame belongs where</h3>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='width:110px'><b>FLAT</b></td>"
            "<td><b>Session</b>, one set <i>per filter</i>.  Depends on "
            "focus, rotation, dust and spacing, so it is only valid until "
            "the next teardown.  Found next to your lights.</td></tr>"
            "<tr><td><b>DARK-FLAT</b></td>"
            "<td><b>Session</b> (library as fallback).  Same exposure and "
            "gain as the flats; used to offset-correct them.</td></tr>"
            "<tr><td><b>DARK</b></td>"
            "<td><b>Library</b>.  Must match exposure, gain, binning and "
            "temperature — with a cooled camera on a fixed setpoint it stays "
            "valid for months.</td></tr>"
            "<tr><td><b>BIAS</b></td>"
            "<td><b>Library</b>.  Depends only on gain and binning; "
            "essentially permanent.</td></tr>"
            "</table>"
            "<p>The <b>Library…</b> button points at the folder holding your "
            "reusable darks and bias.  It may contain <i>raw frames</i> (they "
            "get stacked into masters) or <i>ready-made masters</i> — a group "
            "of exactly one file is adopted as a master as-is.  Flats are "
            "never taken from the library; they are session data.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>How frames are matched</h3>"
            "<p>Matching runs on <b>FITS headers</b>, not on file names, so "
            "any naming scheme works.  A master is only used when exposure, "
            "gain, binning and image dimensions match exactly and the "
            f"temperature is within <b>±{CALIB_TEMP_TOLERANCE_C:g} °C</b>.  A "
            "non-matching dark is reported in the log and skipped rather than "
            "applied — a 60&nbsp;s dark on 300&nbsp;s lights would do real "
            "damage.  Values missing from a header never block a match.</p>"
            "<h3 style='color:#88aaff;'>Two rules worth knowing</h3>"
            "<ul>"
            "<li><b>Bias is never applied together with a dark.</b>  A master "
            "dark already contains the offset; subtracting bias as well would "
            "remove it twice.  <tt>-bias=</tt> is only added when no dark is "
            "used.</li>"
            "<li><b>Flats are offset-corrected before stacking.</b>  Real "
            "bias / dark-flat first; if none exists, Siril's synthetic offset "
            "<tt>=64*$OFFSET</tt>; and if that is refused too, the flats are "
            "stacked raw.  Calibration never aborts a run.</li>"
            "</ul>"
            "<h3 style='color:#88aaff;'>Options</h3>"
            "<ul>"
            "<li><b>Apply calibration when frames exist</b> — master switch.  "
            "Harmless to leave on when there is nothing to apply.</li>"
            "<li><b>Cosmetic correction (hot pixels)</b> — adds "
            "<tt>-cc=dark 3 3</tt>, which locates hot and cold pixels from "
            "the master dark's own statistics.  Needs a matching dark; "
            "without one it has no effect.</li>"
            "<li><b>Match flats to the same night</b> — <i>off</i> pools all "
            "flats of a filter into one, less noisy master (right for a "
            "permanently mounted rig); <i>on</i> uses only the flats from the "
            "same date folder as the lights (right if the optical train was "
            "changed between nights).</li>"
            "</ul>"
            "<h3 style='color:#88aaff;'>Masters and reuse</h3>"
            f"<p>Every master built is written to <b>output/{CALIB_DIRNAME}/"
            "</b> with a descriptive name such as "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "M101_RED_-10C_3s_G100_flat</span>, and reused on the next run.  "
            "Delete that folder to force a rebuild.  The report "
            "(<tt>output.md</tt>) always lists which master went into which "
            "filter.</p>"
            "<h3 style='color:#88aaff;'>How many to shoot</h3>"
            "<table cellpadding='6' style='width:100%'>"
            "<tr><td style='width:110px'><b>Bias</b></td>"
            "<td>50–100, shortest exposure, cap on, per gain.  Once.</td></tr>"
            "<tr><td><b>Darks</b></td>"
            "<td>25–30 per exposure × gain × setpoint.  Refresh every few "
            "months.</td></tr>"
            "<tr><td><b>Flats</b></td>"
            "<td>20–40 <i>per filter</i>, after each session and before "
            "teardown, ~50% histogram.</td></tr>"
            "<tr><td><b>Dark-flats</b></td>"
            "<td>20–30, same exposure and gain as the flats, cap on.</td></tr>"
            "</table>"
            "<p style='color:#888;'>On a modern low-dark-current sensor "
            "(e.g. IMX533, no amp glow) flats give by far the biggest "
            "improvement; darks mainly earn their keep through the cosmetic "
            "correction.</p>")
        tabs.addTab(tab_cal, "Calibration")

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
            "skips stacking + alignment and re-composes in seconds, as long "
            "as every channel it needs was stacked and the aligned masters "
            "still share one grid (see <i>Output &amp; Tips</i>).</p>")
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
            "├─ calib/                master dark / flat / bias (reused)\n"
            "├─ qa/                   rejection maps (if enabled)\n"
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
            "<li><b>calib/</b> keeps the calibration masters that were built "
            "(dark, flat per filter, bias).  They are reused by later runs — "
            "delete the folder to rebuild them.</li>"
            "<li>Everything else lives under <b>_work/</b> — you can delete "
            "that whole folder any time without losing a result.</li>"
            "</ul>"
            "<hr>"
            "<h3 style='color:#88aaff;'>Tips</h3>"
            "<ul>"
            "<li>A filter needs at least <b>2</b> light frames to register "
            "and stack; single-frame filters are skipped.</li>"
            "<li><b>Flats matter most.</b>  Without them expect vignetting "
            "and dust shadows, and PCC will keep complaining about a "
            "gradient.  Shoot 20–40 per filter after each session and drop "
            "them next to your lights — see the <b>Calibration</b> tab.</li>"
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
            "skipped and why.<br>Two things stop full reuse, both on "
            "purpose.  A master that was never built cannot be reused, so a "
            "run made with <b>Stack only the filters this palette uses</b> "
            "has to be repeated in full for a palette that needs the "
            "others.  And the aligned masters must all be the same size: "
            "<tt>-framing=min</tt> crops to the intersection of whatever was "
            "aligned together, so a run over a subset leaves the remaining "
            "channels on the previous grid.  Mixing those would hand "
            "<tt>rgbcomp</tt> channels of different dimensions, so the "
            "script re-aligns instead and names the leftovers in the "
            "report.</li>"
            "<li>Re-running is safe: existing outputs are overwritten.  Turn "
            "reuse OFF after changing stacking options or adding frames.</li>"
            "<li><b>Stopping really stops.</b>  Closing the window mid-run "
            "asks first, then finishes the current filter and stops there.  "
            "Channel alignment, plate-solving, the colour image and the "
            "<tt>_work/</tt> cleanup are all skipped — a composite built "
            "from half the channels is not the image you asked for, and the "
            "intermediates of an interrupted run are exactly what you want "
            "to keep.  The finished masters stay; log, report and dialog "
            "say <i>stopped</i>, not <i>done</i>.  Re-run with <b>Reuse "
            "existing masters</b> to carry on from there.</li>"
            "<li><b>The report only claims what happened.</b>  A filter that "
            "was skipped, failed, or that the abort never reached gets no "
            "invented frame count; a predicted count is marked <b>≈</b> "
            "(quality filters) or <b>≤</b> (k-sigma, where the number is "
            "unknowable in advance); the rejection algorithm named is the "
            "one that really ran; and <tt>todo.md</tt> only calls the "
            "colour calibrated when a calibration actually succeeded.</li>"
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
