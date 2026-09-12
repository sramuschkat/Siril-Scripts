"""
Svenesis ImageMono Train
Script Version: 1.7.18
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
  calibration -- leaving a calibrated, still-linear result.
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
# Script Version: 1.7.18
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: preprocessing
# Script Description: Point it at a N.I.N.A. target folder; it discovers the
#   light frames per optical filter, calibrates them with whatever darks,
#   flats and bias it finds, integrates one master stack for each filter
#   (mono, never debayered), aligns the channels onto a common grid
#   and combines them into a colour image (LRGB / RGB / SHO / HOO / HaRGB)
#   with background extraction and photometric colour calibration.  Writes a
#   Markdown processing report and a post-processing guide alongside.
# Script Author: Sven Ramuschkat
#
# Acknowledgements:
#   The stacking-rejection thresholds in _rejection_args() are taken from
#   AMSP (Automatic Multi-Session Processing) by Cyril Richard, the
#   author of Siril, GPL-3.0-or-later:
# https://gitlab.com/free-astro/siril-scripts/-/blob/main/preprocessing/AMSP.py
#   Reading AMSP alongside this script also contributed the noon-to-noon
#   observing-night key, the per-group disk cleanup, the INSTRUME check,
#   the wider set of CCD-temperature keywords, the closest-exposure dark
#   fallback and the content-based IMAGETYP inference.  Thank you.

CHANGELOG:
1.7.18 - Two records that described something other than what happened
      - COMMANDS.SSF SAID IT COULD BE REPLAYED, AND IT CANNOT.  The
        header promised "Replay headless: siril-cli -s commands.ssf"
        with GUI-ONLY lines as the single caveat.  Three larger
        obstacles went unsaid.  The raw frames are put into the work
        folders by the script (shutil.copy2 / os.symlink), so `link bias
        -out=../process` reads a directory Siril never filled; the same
        holds for the PixelMath inputs pm_R/pm_Ha, staged under names
        without hyphens, and for every master copied out of
        _work/.../process into masters/.  _work/ is then deleted by the
        run that wrote the file.  And the worst of the three fails
        SILENTLY: the composite's `load, load, load, new W H 3 RGB,
        save` reads like a composition, but the three loads feed
        get_image_pixeldata() into numpy, `new` makes an EMPTY canvas
        and set_image_pixeldata() fills it through sirilpy -- replaying
        those five lines writes a blank colour image under the right
        name.  The header now says what the file is, and every step the
        script performs itself is marked in place with a `#` line
        carrying the frame count and the folder: staging, the PixelMath
        copies, the masters copied in and out of the alignment, and the
        canvas that only looks like a composition.  The record stays
        complete and stops claiming what it cannot do.  Writing moved
        out of _record_command into _write_commands so a note reaches
        disk the same way a command does.

      - ALIGNMENT ADVICE IS NOW DERIVED FROM THE RUN'S OWN PALETTE.
        When a channel aligned on very few star pairs, the warning always
        closed with the same remedy: "Stack only the filters this palette
        uses" keeps the reference among the channels that end up in the
        picture.  That sentence is a no-op under HaRGB.  The palette
        reads L, R, G and B through the dropdowns and finds Ha by role,
        so every discovered filter is already one of its own and the
        option has nothing to leave out -- and the reference Siril picked
        is one of the composite's channels too.  On an NGC 6946 run the
        Ha master matched on 318 pairs against 1176-1741 for broadband,
        and the script answered by pointing at a control that could not
        change the outcome.  _align_ref_advice now asks _palette_filters
        what THIS palette reads and says one of five things: which master
        the switch would drop (the case it was written for), that the
        pool is already restricted, that there is no composite to have a
        palette, that the mapping names no discovered filter, or -- the
        HaRGB case -- that no master can be left out, naming the
        reference as one of the composite's own, and that only more
        exposure on the weak channel moves the number.

1.7.17 - Lessons taken from the Starloch Batch Preprocessor, and three
        audits of this script's own arithmetic against Siril's
        documentation and against Siril's own log output
      - DISABLED COLOURS MOVED FROM THE STYLESHEET TO THE PALETTE.
        1.7.16 made setEnabled(False) visible by adding six `:disabled`
        rules -- one per widget class that happened to be affected.  That
        is the wrong shape: a CSS rule reaches only the classes it names,
        so the next widget added is invisible again, and the seven other
        Svenesis scripts (86 further setEnabled calls) would each need
        the same block.  QPalette.ColorGroup.Disabled reaches every
        widget there is, in three lines.  DISABLED_STYLESHEET stays for
        dark mode only, where the shared sheet hard-codes backgrounds on
        the input widgets and a sheet beats the palette.
      - AND THE WINDOW NOW FOLLOWS SIRIL'S THEME.  It is launched from
        Siril's Python menu and was fixed dark whatever Siril was set to.
        `get_siril_config("gui", "theme")` decides; light mode drops the
        dark sheet entirely rather than carrying a second, hand-written
        copy of it, because Fusion's standard palette already is a
        complete light theme.  An unreadable setting stays dark.  The
        console panes keep their dark background in both modes -- they
        are a terminal, and the coloured log lines are written for a dark
        ground.
      - EVERY RUN NOW WRITES commands.ssf.  A verbatim record of every
        Siril command the run issued, next to the output, rewritten after
        each one and recorded BEFORE the call -- the command that kills a
        run is the interesting line, so it must not be the missing one.
        Until now a defect was reproduced by scraping commands out of a
        pasted GUI log by hand; now the run replays headless with
        `siril-cli -s commands.ssf`.  It carries the `requires` line a
        script needs, and marks `load_seq` as GUI-ONLY instead of
        silently rewriting it: a record that quietly differs from what
        ran is worse than no record.
      - A CLEANUP THAT FAILED WAS SILENT, AND FOUR OF THEM WERE
        DANGEROUS.  All seven `shutil.rmtree(..., ignore_errors=True)`
        calls ignored failure.  Four of them clear a working directory
        that is about to be REFILLED with freshly staged frames under
        index-based names -- so a leftover `lights_00050.fit` from a
        longer previous run would be linked into the new sequence and
        stacked into the master without a word.  Those four now re-check
        the directory and fail the run.  The three that merely free space
        warn and carry on, because nothing reads them again.
      - AND A STAGE THAT WROTE NOTHING NOW FAILS WHERE IT HAPPENED.  The
        stack output was checked; the master is then written a SECOND
        time by the background extraction, through Siril, whose `save`
        can fail without raising.  `_verify_outputs` checks the master
        after that rewrite and each aligned channel before it becomes a
        colour, counting a zero-byte file as missing.
      - THE HOT-PIXEL THRESHOLD NOW FOLLOWS THE STACK SIZE.  `-cc=dark
        3 3` went to every filter regardless.  But stacking only removes
        a hot pixel because DITHERING puts it on a different sky pixel in
        every frame, leaving it a minority at each one -- and that
        argument needs frames.  At four, rejection is percentile clipping
        over four samples: it discards a fixed share by rank, and a
        defect present in two of the four is not a minority at all.
        Measured on IC 1805, SII stacked 4 frames with 19.3-31.1%
        rejection, the weakest channel of the set.  A channel of
        SIGMA_MAX_FRAMES or fewer now gets a tightened hot threshold (2.5
        instead of 3).  The cold side is untouched: every calibration in
        those runs reported "0 + N", so it never fires and changing it
        would be a guess.  The count is passed as an argument --
        `_current_n_frames` is only set AFTER calibration runs -- and the
        split path passes the filter's TOTAL, since the parts are merged
        again before stacking.
      - AND EQUAL SIZE WAS BEING TAKEN FOR OVERLAY.  After the
        cross-filter alignment the run checked that the masters came out
        the same size and that the star matcher found enough pairs.
        Neither proves the channels describe the same sky pixel -- four
        masters of 2942x2876 can sit pixels apart, and a healthy pair
        count says the fit converged, not that it converged on the right
        solution.  Five points of the first master now go to the sky
        through its own solution and back to pixels through each other
        master's; anything past a whole pixel is said BEFORE the channels
        are combined.  Headers only.  A master without a usable solution
        is "cannot tell" and stays silent.

        --- and then three audits of the arithmetic itself ---

      - THE FRAME-LOSS WARNING COULD NOT FIRE.  It read
        `_effective_frame_count`, which takes min() of the percentages
        and is an UPPER bound on the survivors -- therefore a LOWER bound
        on the loss, the wrong direction for a warning about losing too
        much.  Survivors must pass EVERY filter, so the real count is the
        intersection.  Measured on one NGC 6946 run with 90% / 87%:
        predicted 13-14% dropped against 21-23% really dropped, on all
        four channels, so the note fired on NONE of them while 88 of 400
        frames went.  It now reads `_projected_frame_count`, which
        multiplies the shares and comes within a frame of the truth
        (57/54/148/51 against 57/55/148/52).  The docstring's
        justification went with it: it argued the metrics are correlated
        so the product keeps a margin, and three of those four channels
        came out BELOW the product.
      - A QUALITY FILTER THAT NEVER REACHED SIRIL WAS SILENT.  The spin
        boxes accept 1-100.  Asking for the best 15% of 25 frames leaves
        3, under MIN_STACK_FRAMES, so the filter was dropped -- and the
        one message for that case only covers "too few frames", which 25
        is not.  The user got the FULL stack and no word about the cut
        they asked for.  `_quality_filter_plan` now returns what was
        skipped and why.
      - THE SHORT-CHANNEL WARNING HUNG ON THE WRONG CONSTANT.  "Too few
        for outlier rejection to mean much" tested `n_reg <
        MIN_STACK_FRAMES` -- but that is the floor the quality FILTERS
        may not cross, not a statement about rejection.  Two meanings on
        one number, and a channel of exactly four frames -- percentile
        clipping, the weakest case there is -- fell through in silence.
        It now tests PERCENTILE_MAX_FRAMES, shared with `_rejection_args`
        so the two cannot drift.
      - AND THE DARK TOLERANCE WAS SYMMETRIC WHERE THE PHYSICS IS NOT.
        `abs(have - want)` treated a 630 s dark on 600 s lights like a
        570 s one.  Dark current grows with exposure: the longer dark
        OVER-subtracts, the background goes negative, and Siril clamps
        calibrated 32-bit data to [0, 1] -- those pixels land on zero and
        their faint signal is gone for good.  The shorter dark
        under-subtracts, leaving a pedestal the background extraction
        removes anyway.  A longer dark now needs
        DARK_OVERSHOOT_TOLERANCE (2%) against the usual 5%, ties go to
        the shorter one, and the message names the direction.
      - A STAR COUNT ON SIRIL'S CEILING IS NOT A MEASUREMENT.  The manual
        gives `-maxstars` as "must be between 100 and 2000".  On a
        star-rich field every frame hits it: of 400 frames in one NGC
        6946 run, 395 reported exactly 2000.  `-weight=nbstars` then
        gives all of them the SAME weight, so a setting offered as
        "Improves SNR when frame quality varies" does almost nothing --
        and the registration line printed "2000 stars" as if it had
        measured a rich field.  The cap is now recognised in the log and
        the report, and star-count weighting on saturated data is called
        out, naming Noise and wFWHM, which still separate those frames.
      - THE FLAT NOISE FLOOR STRADDLED TIME.  It compared the first half
        of a night's flats against the second.  The file list is sorted
        by path and a flat run is named by timestamp, so those halves are
        separated in TIME, and any drift in the flats' SHAPE -- dew, a
        twilight gradient -- was measured as "noise".  Pure LEVEL drift
        was already immune (each map is divided by its own median); shape
        drift was not.  Simulated at 0.2% shape drift over eight flats
        the floor came out 2.1x too high, and an inflated error bar hides
        the very difference it exists to find.  The halves now
        INTERLEAVE (1.15x at the same drift), and `_spread_sample` takes
        the eight at an even stride instead of from the head of a
        twenty-flat run.
      - THE REJECTION FALLBACK IGNORED THE QUALITY FILTERS.  When the
        registered count cannot be read, `n_stack` fell back to
        `n_linked` -- the full STAGED count, as if no filter had run: 74
        staged frames chose the algorithm for 74 where 57 were
        integrated, and only 31 frames separate winsorized from GESDT.
        It now falls back to `_projected_frame_count`, so the error is
        towards the gentler algorithm.  `effective` keeps the optimistic
        estimate, because the report quotes it as "<=N used".
      - DRIZZLE WARNED ABOUT SOMETHING ITS OWN SETTINGS PREVENT.  The
        message blamed a "grid unevenly filled" below 40 frames -- the
        failure mode of pixfrac < 1.  At the shipped pixfrac of 1.0 every
        output pixel is covered by every frame.  What is really missing
        on a short run is sub-pixel sampling, and the message now says
        so, along with what you get instead.  DRIZZLE_PIXFRAC sits beside
        the threshold so the two cannot drift apart; it stays at 1.0
        because lowering it changes everyone's images.
      - AND CALIB_TEMP_TOLERANCE_C CARRIES ITS REASONING NOW.  It sat
        there as a bare 2.0, in a file whose neighbouring constant
        explains at length why the EXPOSURE tolerance must be a fraction.
        Dark current doubles every ~6 C, so 2 C is up to ~26% of the dark
        signal -- negligible at a cooled set point, not negligible on an
        uncooled camera.
      - RBF BACKGROUND EXTRACTION EATS LINE EMISSION.  Measured with
        siril-cli on a synthetic frame -- a nebula covering 95% of the
        field plus a known linear sky gradient, decomposed by least
        squares into [nebula, x, y, 1]:

            subsky 1 (degree 1)       99.9% of the nebula kept
            subsky 2 (degree 2)       32.1% kept
            subsky -rbf -smooth=0.5   17.8% kept   <- what ran
            subsky -rbf -smooth=1.0   48.1% kept   (1.0 is the maximum)

        RBF is the most destructive option available on a target that
        fills the frame, and no RBF setting is safe there.  The per-sub
        pass was already right (degree 1, Siril's own guidance); the
        per-master and composite passes ran RBF unconditionally, and the
        tooltip described the benefit without the cost.  It cannot be
        detected from the pixels: the fraction above median + MAD is
        26.0% for plain sky, 26.0% for the frame-filling nebula and
        27.5-30.3% for a compact galaxy on real masters.  A smooth nebula
        IS statistically sky, which is why the model removes it.  The
        reliable signal is the FILTER, so a narrowband master and a
        narrowband palette now say so, with the measured figures.  It
        WARNS rather than overriding: swapping the user's background
        model silently would change images unasked.
      - A CALIBRATION PART TOO SMALL TO BE A SEQUENCE TOOK THE WHOLE
        SPLIT DOWN.  Siril cannot build a sequence from one file, so a
        night holding a single light failed `calibrate` and the run fell
        back to one pooled pass -- after having stacked a master flat per
        night that nothing then read.  Seen on IC 1805: OIII arrived as
        8 frames on one night and 1 on the next, two per-night flats were
        built, both thrown away, and the log carried an error that looks
        like a defect.  The condition is knowable before the parts are
        built, so `_calib_split` now refuses there, and the run says so
        -- discovery had ANNOUNCED per-night calibration, and that
        announcement must not be left standing.
      - AND THE TIGHTENED-COSMETIC NOTE IS SAID ONCE PER FILTER.  A split
        calls `_calibrate_args` per part, so OIII said the same sentence
        three times in one run.  The arguments are still built every
        time; only the message is gated.
      - AND THE COLOUR-FIT THRESHOLD COMPARED A SCALED NUMBER TO AN
        ABSOLUTE ONE.  Siril's sigma is the scatter of *Image* R/G, so it
        carries whatever scale those channels are on -- and with
        `-output_norm` (on by default) each master is divided by its own
        brightest pixel, which is not a photometric quantity and differs
        per filter.  Confirmed on real masters: every channel ends at
        max = 1.000017..1.000021.  Scaling the ratio by k scales the
        slope and the sigma alike, so sigma/|slope| is what a fixed
        threshold may be compared against.  Two runs of the SAME IC 1805
        data, one with narrowband normalisation and one without, gave raw
        sigma 0.323 and 0.216 -- 50% apart -- and 0.2748 against 0.2750
        once scaled out.  The white-balance factors carry the same
        scaling: the calibrated image is right, but K0/K1/K2 are not a
        measurement of the filters or the sensor, and the run says so
        where they are printed.

1.7.16 - Three places that described the wrong thing, a greying that
        never greyed, and an import nobody used
      - THE FRAME-DROP MESSAGE NAMED THE WRONG CAUSE.  A run with the
        quality filters on reported "Registration dropped 15 of 74
        frame(s) ... Frames without enough detectable stars (clouds,
        haze) cannot be aligned" -- while the same log said "74 images
        successfully platesolved out of 74 included".  Nothing had
        failed to align.  The 15 were removed by `-filter-wfwhm=90%
        -filter-round=90%`, which the user had switched on, on frames
        that were fine.  `n_reg` counts what seqapplyreg exported, and
        that is already after the filters -- the comment under the
        message said so, the message did not.  `_qf_decision` already
        records whether the filters fired, so the two causes are now
        told apart, and the filtered case names the flags it was given.
        Measured on one NGC 6946 run: 41 of 210 frames across three
        filters, every one of them reported as weather.
      - AND THE SHORT-CHANNEL WARNING COULD NOT FIRE FOR THE CASE IT
        WAS WRITTEN FOR.  "Only N frame(s) ... too few for outlier
        rejection to mean much" sat INSIDE the drop message, so it
        needed frames to have been lost.  A filter that STARTED below
        MIN_STACK_FRAMES and lost none was never warned, while one that
        fell to the same count was -- the same diagnosis hanging off the
        wrong condition as the bullet above.  It is now its own check on
        the number going into the stack, and "left" is gone from the
        wording with the nesting.  Found on an IC 1805 run: SII stacked
        4 frames, one above the floor, in silence.
      - AND THE SPCC PANEL SHOWED THE HALF IT DOES NOT USE.  On a SHO
        run the three broadband filter boxes sat there enabled and
        filled with "Antlia R / G / B", while `_spcc_args` calibrated by
        wavelength and ignored them entirely -- and said so only in the
        Log, after the start.  Which mode applies is not a choice the
        user makes: the palette decides it, so a switch of its own would
        just be a second place to disagree with that table.  The panel
        now follows the palette.  Broadband names grey out for a
        narrowband palette and the bandwidth greys out for a broadband
        one, and the narrowband half spells out what will really be
        sent, read from the same table `_spcc_args` builds its command
        line from: "Ha 656.3 nm -> G", "OIII 500.7 nm -> B", "SII
        671.6 nm -> R" for SHO.  Greyed rather than hidden, for the
        reason the calibration tables already do it.  "Auto" leaves both
        halves live: which one applies is not knowable before the
        filters are found, and guessing would be the same mistake one
        step earlier.
      - ONE BANDWIDTH BECAME THREE, ONE PER LINE.  Siril's own SPCC
        dialog offers a bandwidth per COLOUR CHANNEL, and this script
        offered a single one for all three -- both are wrong for the
        same reason.  Bandwidth is a property of the FILTER: HOO maps
        one OIII filter to green AND blue, so a per-channel box lets one
        piece of glass be given two different passbands, and one shared
        box cannot describe a mixed set (3 nm Ha with 6.5 nm OIII is a
        normal rig).  The rows are keyed by emission line, and the
        palette decides which channels each one feeds -- HOO sends the
        OIII width to `-gbw` and `-bbw` both.  A line the palette does
        not use greys out.  Wavelengths stay derived rather than
        editable, which is where Siril's dialog cannot help itself: it
        does not know which line is in which channel, and this does.
        The old single `nb_bandwidth` setting seeds all three on first
        load, so an upgrade keeps sending what it sent before.
      - AND THE GREYING ITSELF WAS INVISIBLE.  A Qt stylesheet rule
        that names `color` applies in EVERY state unless a :disabled
        rule overrides it, and the shared dark theme has one only for
        QPushButton.  So all nineteen setEnabled(False) calls in this
        file changed nothing on screen -- the calibration tables that
        1.7.15 describes as turning grey when a kind is switched off,
        and the SPCC panel one bullet up, included.  The theme is
        EXTENDED rather than edited, because it is copied verbatim
        between the Svenesis scripts: DISABLED_STYLESHEET adds the
        missing states for QLabel, QCheckBox, QLineEdit, QComboBox and
        the spin boxes, in the palette the button rule already used.
        The eight hint labels needed a second fix: a per-widget
        stylesheet naming `color` outranks the global :disabled rule, so
        they now carry both states (HINT_STYLE).  The other seven
        scripts in the suite have the same gap -- 86 further
        setEnabled calls -- and are not touched here.
      - The unused `QSizePolicy` import is gone.  It was the only thing
        pyflakes still had to say about this file.

1.7.15 - A logic audit, what a real run said, and the solution the
        colour calibration asked for
      The full entries, with the measurements behind them, are
      section 17 of both manuals in Instructions/.
      - The composite is re-solved with distortions before the
        photometric calibration: `platesolve -force -noflip -order=3`.
        Siril asks for it twice per finish, and the registered frames
        carry a linear WCS by construction (`seqapplyreg` undistorts).
        It does NOT fix the weak colour fit: sigma(R/G) 2.2497 ->
        2.2481.  Still open -- sigma(B/G) is 0.17 on the same stars,
        apertures and WCS, so the cause is specific to that ratio.
      - `-framing=min` was accepted and never applied on the
        astrometric path: 3008x3008 subs, master 3060x3128 -- the
        union, not the intersection.  The exported frames are now
        measured directly, and a channel without its crop says so in
        the log and in the report, with the two causes told apart.
      - An inherited astrometric solution is no longer logged as new
        work: the header is asked before `platesolve` is credited.
      - Calibration panel rebuilt.  Darks and flats are separate
        switches; what is switched off stays listed and turns grey;
        the Dark-Flats column shows the job, not the IMAGETYP keyword;
        the master switch is gone; session and library have a box
        each; the Lights table gained a NIGHTS column.  A switch now
        changes the label and not the record, and "100 biass" is
        "100 bias".
      - Logic audit, eleven findings: the quality-filter value resets
        in both directions, the presets name the mode their numbers
        are in, the observing night is the frame's own (noon-to-noon
        from DATE-OBS), the flat map uses the size most of the night
        agrees on, GESDT falls back to the band below it, a channel
        dropped by the alignment says why, the grid check reads the
        files rather than a flag, and four smaller guards.
1.7.12 - Two silent failures the first 1.7.11 run exposed
      - FITS READS SURVIVE ASTROPY'S MEMMAP REFUSAL.  astropy declines
        to memory-map an image whose header carries BZERO/BSCALE/BLANK
        -- every N.I.N.A. integer sub -- and raises "Cannot load a
        memory-mapped image ... Set memmap=False." at `.data` access
        time.  One run swallowed that ~130 times, and worse than the
        noise: the flat consistency check read no frame at all and
        silently skipped, and the blank-frame check silently kept
        everything.  All readers now go through `_with_fits`, which
        reopens the file unmapped on that specific refusal and repeats
        the read; unrelated errors still propagate.
      - The multiprocessing resource tracker is started at import time,
        while the environment is clean.  sirilpy's shared-memory
        transfers spawn it lazily mid-run, where (on macOS, inside
        Siril's process) it dies with PermissionError and is relaunched,
        spraying tracebacks into Siril's log.  1.7.9 hardened the log
        readers against those tracebacks; this removes them at the
        source.  Same fix as in Svenesis LightCurve.
      - A DEAD SIRIL FAILS THE RUN ONCE, NOT EVERY FALLBACK IN TURN.
        When Siril crashed mid-run, the broken pipe matched every
        fallback's `except (CommandError, DataError, SirilError)` and
        the log blamed plate solving, star alignment and single-pass
        registration in turn, for both filters -- four diagnoses for one
        dead process.  `_cmd`, the single funnel every command uses, now
        tells a transport death (broken pipe, connection closed/reset,
        SirilConnectionError) apart from a refusal and raises
        SirilGoneError, which no fallback catches; the worker's top
        level reports it once, with the recovery spelled out: restart
        Siril, run again, finished masters are picked up by 'Reuse
        existing masters'.
1.7.11 - and earlier: section 17 of both manuals (Instructions/) carries
        every entry back to 1.4.0, and `git log` has all of them.  They
        were dropped from this docstring in 1.7.15, where it had grown
        to 1581 lines -- an eighth of the file.
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

# Start multiprocessing's resource tracker NOW, while the interpreter
# still has a clean environment.  sirilpy's shared-memory transfers spawn
# it lazily on first use -- mid-run, on macOS from inside Siril's
# sandboxed process, where it dies with `PermissionError: Operation not
# permitted` during importlib's path scan and is relaunched, spraying
# tracebacks into Siril's log.  1.7.9 made the log READERS survive those
# tracebacks; this removes them at the source.  Harmless either way: the
# run completes identically, but a traceback that means nothing trains
# people to ignore the ones that do.  If it cannot start at all, nothing
# is lost -- Python relaunches it on demand exactly as before.
try:
    from multiprocessing import resource_tracker as _resource_tracker
    _resource_tracker.ensure_running()
except Exception:                                     # noqa: BLE001
    pass

# Siril 1.4 ships sirilpy 1.0.x, and everything this script needs to run
# at all is in 1.0.0.  Checked before anything else -- before the imports
# below, which the floor is what guarantees -- so a too-old module gives
# one clear sentence instead of an ImportError or an AttributeError from
# deep inside a worker thread.  Features that need MORE than the floor are
# listed in OPTIONAL_API and reported individually; see
# `_missing_capabilities`.
SIRILPY_MIN_VERSION = "1.0.0"

_version_ok = getattr(s, "check_module_version", None)
if _version_ok is None or not _version_ok(f">={SIRILPY_MIN_VERSION}"):
    # A module without check_module_version() is far older than the floor,
    # so the answer is the same either way -- and asking for the function
    # rather than calling it keeps the answer a sentence instead of a
    # traceback.
    print(f"Svenesis ImageMono Train needs sirilpy "
          f"{SIRILPY_MIN_VERSION} or newer (Siril 1.4). "
          "Update Siril, or its Python module from the Scripts menu.")
    sys.exit(1)

# Guaranteed by the floor above.  These used to fall back to locally
# defined stand-ins for "older sirilpy" -- which was worse than no
# handling at all: a locally defined CommandError is never what sirilpy
# raises, so every `except CommandError` in this file would have missed,
# and a Siril error would have escaped as an unhandled exception.
from sirilpy import LogColor, NoImageError
from sirilpy.exceptions import (
    SirilError, SirilConnectionError, CommandError, DataError,
)

s.ensure_installed("PyQt6", "astropy", "numpy")

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QMessageBox, QGroupBox,
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QDialog,
    QLineEdit, QTextEdit, QTextBrowser, QTabWidget, QScrollArea,
    QProgressBar,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCompleter,
)
from PyQt6.QtCore import Qt, QSettings, QUrl, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QDesktopServices, QPalette


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.7.18"
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
#                                 aligned; *_fullframe.fit = uncropped,
#                                 named <N>x<EXP>_G<gain>_<temp>C)
#     _work/                      all intermediates -- safe to delete
#       sequences/<filter>/       Siril sequences per filter
#       align/                    cross-filter alignment work
#       helpers/                  compose helpers (_nbnorm, _RED_Ha)
MASTERS_DIRNAME = "masters"
# Verbatim record of every Siril command a run issued, written beside the
# output so a run can be replayed headless instead of reconstructed from
# a pasted log.
COMMANDS_FILENAME = "commands.ssf"
# The `requires` line that record carries.  Matches the "Siril Version"
# in this file's header: older builds lack commands this script uses.
SIRIL_MIN_VERSION = "1.4.0"
# Commands Siril accepts interactively but refuses inside a script, so
# the record marks them rather than pretending the file runs as-is.
_SCRIPT_FORBIDDEN_COMMANDS = frozenset({"load_seq"})
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
# How far a dark's exposure may be from the lights' before it stops
# helping.  A fraction, not seconds: the thermal signal scales with
# exposure, so 5% of 300s is a different thing than 5% of 30s.
DARK_EXPOSURE_TOLERANCE = 0.05

# ...and a LONGER dark is not the same mistake as a shorter one, so it
# gets its own, tighter bound.  Dark current grows with exposure, so a
# dark longer than the lights OVER-subtracts: the background goes
# negative, and Siril clamps calibrated 32-bit data to [0, 1], so those
# pixels land hard on zero and the faint signal in them is gone for good.
# A shorter dark UNDER-subtracts, which leaves a positive pedestal that
# the background extraction removes anyway, plus hot pixels that the
# cosmetic map and the stacking rejection are there for.  Same |delta|,
# two different outcomes -- one recoverable, one not.
DARK_OVERSHOOT_TOLERANCE = 0.02

# Wider for the flats' offset: a flat exposure is short, so the same share
# is a much smaller absolute difference -- and so is the dark signal it
# corrects.
DARKFLAT_EXPOSURE_TOLERANCE = 0.20

# How far the cooled set point may drift before a master stops matching.
# Absolute degrees, unlike the exposure tolerances above, because that is
# what the header records and what a set-point camera actually holds.
#
# The consequence is not linear: dark current roughly DOUBLES every ~6 C,
# so 2 C is up to ~26% error in the dark signal being subtracted.  That
# sounds worse than it is at a cooled set point -- at -10 C and 600 s the
# dark signal of a modern CMOS sensor is a few electrons, and a quarter
# of that disappears under the read noise.  It would NOT be harmless on
# an uncooled camera or at long exposures in summer, which is why the
# number is written down here with its reasoning rather than left as the
# one calibration constant nobody justified.
CALIB_TEMP_TOLERANCE_C = 2.0

# SIP polynomial order for the plate solve that precedes photometric colour
# calibration.  Siril asks for one in so many words -- "Found linear plate
# solve data, you may need to solve your image with distortions to ensure
# correct calibration of stars near image corners" -- and the order it
# would otherwise use comes from its astrometry preferences, which is not
# a setting this run can see.  Three describes a refractor's field
# curvature without inventing structure a few thousand stars cannot
# support; Siril accepts 1 to 5.
SPCC_SIP_ORDER = 3

# Placeholder for frames without a FILTER keyword (e.g. an OSC-style
# capture accidentally dropped in, or a broadband run with no wheel).
NO_FILTER = "NOFILTER"

# Never let the quality filters shrink a stack below this many frames --
# outlier rejection needs a population, and a sharp 2-frame stack is worse
# than a slightly softer 6-frame one.
MIN_STACK_FRAMES = 4

# Top of the percentile-clipping band (see `_rejection_args`).  At or
# below this, rejection has almost nothing to work with: Siril's own
# manual calls percentile clipping the choice for small sets, and on four
# samples it discards a fixed share by rank -- a defect present in two of
# the four is not an outlier at all.  Shared with the ladder rather than
# written twice, because the two must not drift apart: the warning that
# says "too few for outlier rejection to mean much" used MIN_STACK_FRAMES
# instead, which is the floor the quality FILTERS may not cross.  Two
# meanings on one number, and a 4-frame channel -- the exact case the
# sentence describes -- fell through it in silence.
PERCENTILE_MAX_FRAMES = 4

# Quality filters only pay off once a channel has enough frames.  Dropping
# subs always costs signal-to-noise (noise scales with 1/sqrt(n)), and on a
# short run that loss outweighs whatever removing the worst frame gains.
# Measured on real data: filtering 8 luminance frames down to 6 raised the
# background noise by 19% -- almost exactly the sqrt(8/6) you would predict
# from the frame count alone, i.e. the dropped frames were not actually bad.
FILTER_MIN_FRAMES = 20

# Warn when the quality filters throw away more than this share of a set.
FILTER_WARN_FRACTION = 0.15

# How many k-sigma cuts may be combined.  In percentage mode the survivors
# can be projected and the MIN_STACK_FRAMES floor does the limiting; with
# k-sigma they cannot -- how many frames lie beyond k sigma is a property
# of the data.  Two cuts still leave a stack recognisable; four applied
# blind is how a channel quietly ends up with three frames in it.
FILTER_MAX_KSIGMA = 2

# Rejection band edges, taken from AMSP by Cyril Richard (the author of
# Siril) -- see the acknowledgement in the header.  They carry more weight
# than our own reasoning because the same person implemented these
# algorithms in Siril.
SIGMA_MAX_FRAMES = 10
GESDT_MIN_FRAMES = 31
LINEAR_MIN_FRAMES = 300

# `-cc=dark <cold> <hot>` sigmas.  LOWER is MORE aggressive: the value is a
# threshold above the master dark's own noise, so a smaller one flags more
# pixels as defective.
COSMETIC_COLD_SIGMA = "3"
COSMETIC_HOT_SIGMA = "3"
# Stacking only removes a hot pixel because DITHERING puts it on a
# different sky pixel in every frame, leaving it a minority at each one.
# That argument needs frames.  At four, rejection is percentile clipping
# over four samples -- it discards a fixed share by rank, and a defect
# present in two of the four is not a minority at all.  Below this count
# the cosmetic map has to catch at source what rejection will not catch
# later, so its hot threshold is tightened.  Measured across this
# session's runs, the cold side never fires at all (every calibration
# reported "0 + N"), so it is left where it is rather than changed blind.
COSMETIC_TIGHT_MAX_FRAMES = SIGMA_MAX_FRAMES
COSMETIC_TIGHT_HOT_SIGMA = "2.5"

# How much of its own footprint each input pixel keeps when it is dropped
# onto the finer grid.  1.0 = the full pixel, which is the SAFE end of the
# scale and the reason the frame-count warning below had to be reworded:
# at 1.0 every output pixel is covered by every input frame, so the
# "patchy coverage" that drizzle is warned about cannot occur -- that is
# the failure mode of pixfrac < 1.
#
# The price is that drizzle's actual purpose goes with it.  The
# sub-pixel resolution it recovers comes from shrinking the drop below
# one pixel; at 1.0 the result is close to a smoothed upsample, with
# twice the pixels, neighbouring output pixels correlated, and little
# real detail gained.  Lowering this is what makes drizzle worth running
# -- and it is exactly then that many well-dithered frames start to
# matter.  Left at 1.0 because changing it changes everyone's images.
# Siril's hard ceiling on detected stars per frame: the manual gives
# `-maxstars` as "must be between 100 and 2000".  On a star-rich field
# every frame hits it, and then the star COUNT stops being a measurement
# -- it is the constant.  That matters twice: `-weight=nbstars` gives
# every saturated frame the same weight, so the weighting does nothing;
# and the registration line reported "2000 stars" as if it had measured
# something.  wFWHM is unaffected (it scales FWHM, which still varies)
# and so is noise weighting.
SIRIL_MAX_STARS = 2000

# How much of a FRAME-FILLING smooth emission signal each background model
# leaves behind.  Measured with siril-cli on a synthetic frame: a Gaussian
# nebula covering 95% of the field plus a known linear sky gradient, then
# decomposed by least squares into [nebula, x, y, 1].
#
#     subsky 1  (degree 1)         99.9% of the nebula kept, 86% of the
#                                  gradient removed
#     subsky 2  (degree 2)         32.1% kept, 96% removed
#     subsky -rbf -smooth=0.5      17.8% kept, 99% removed
#     subsky -rbf -smooth=1.0      48.1% kept, 95% removed  (1.0 is the
#                                  maximum; Siril refuses 2.0)
#
# RBF is therefore the most destructive option available on a target that
# fills the frame, and NO RBF setting is safe there -- only the degree-1
# polynomial is.  On a compact target (a galaxy in a wide field) the
# opposite holds and RBF is clearly better, which is why it stays on
# offer rather than being removed.
#
# There is no way to tell the two cases apart from the pixels: measured on
# real masters, the fraction of the frame above median + MAD is 26.0% for
# plain sky, 26.0% for the frame-filling nebula and 27.5-30.3% for the
# compact galaxy.  A smooth nebula IS statistically sky, which is exactly
# why the model removes it.  The reliable signal is the FILTER: a
# narrowband channel is emission, and emission is what fills the frame.
RBF_NARROWBAND_KEPT = 0.18
POLY1_NARROWBAND_KEPT = 0.999

DRIZZLE_PIXFRAC = 1.0

# Dithered frames wanted before drizzle earns its cost.  NOT about patchy
# coverage while DRIZZLE_PIXFRAC is 1.0 (see above); about whether there
# is enough sub-pixel sampling for the finer grid to carry information
# the plain stack does not already have.
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
# The full manual, in both languages.  Linked from the Help dialog --
# the tabs there are a quick reference and deliberately stay shorter.
_DOCS_BASE = ("https://github.com/sramuschkat/Siril-Scripts/blob/main/"
              "Instructions/Svenesis-ImageMono-Train-Instructions")
DOCS_URL_EN = f"{_DOCS_BASE}.md"
DOCS_URL_DE = f"{_DOCS_BASE}_de.md"

# The source of the rejection bands -- see the acknowledgement in the
# header.  Named here so the help can link it rather than describe it.
AMSP_URL = ("https://gitlab.com/free-astro/siril-scripts/-/blob/main"
            "/preprocessing/AMSP.py")

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
#
# Every profile names `filter_mode` even though all three agree on it.  The
# quality-filter values below are PERCENTAGES, and a preset that set them
# without the mode handed a 90 to spin boxes that were in k-sigma range
# (1..10), where Qt clamped it to 10 -- "reject beyond 10 sigma", which
# rejects nothing.  Silently, and with the box reading a plausible number.
# The mode is applied before the values (see `_apply_preset`), for the same
# reason `_load_settings` does it in that order: the mode sets the ranges.
PRESETS = {
    "Quick look": {
        # Fastest path to "does this data look good?" -- no QA extras, no
        # colour calibration, no frame filtering, keep every frame.
        "skip_blank": False, "rejection": True, "weighting": False,
        "filter_mode": "% best",
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
        "filter_mode": "% best",
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
        "filter_mode": "% best",
        "f_wfwhm_val": 90, "f_wfwhm_on": True, "f_round_on": True,
        "f_stars_on": False, "f_bkg_on": False,
        "bg_master": True, "bg_extract": False,
        "rejmap": True, "platesolve_master": True, "compose": True,
        "finish": True, "finish_stretch": False, "nb_normalize": True,
        "cleanup_work": False,
    },
}


def _atomic_write_text(path: str, text: str) -> None:
    """Write a small text file without ever leaving a truncated one.

    The command record is rewritten after every command, so a crash mid
    write is not hypothetical -- and a half-written record of the run
    that crashed is exactly the file someone would go on to trust.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


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


class SirilGoneError(RuntimeError):
    """The connection to Siril is dead -- no further command can succeed.

    Raised by the worker's `_cmd` when a command fails at the transport
    level (broken pipe, connection closed/reset) rather than being
    refused.  Nothing below the worker's top level catches it ON
    PURPOSE: every fallback chain in this file exists to try a different
    COMMAND, and no command survives a dead socket.  One real run
    cascaded through plate-solve -> star alignment -> single-pass,
    blamed each in turn, then repeated the dance for the next filter --
    four misleading diagnoses for one crashed Siril.
    """


_CONNECTION_DEAD_MARKS = ("broken pipe", "connection closed",
                          "connection reset", "connection refused")


def _connection_dead(exc: BaseException) -> bool:
    """True when an error means the Siril link itself is gone.

    By type where sirilpy says so (SirilConnectionError); by message
    otherwise -- sirilpy wraps socket deaths into CommandError with the
    OS text preserved ("[Errno 32] Broken pipe", "Connection closed
    during data transfer"), so the type alone does not identify them.
    """
    if isinstance(exc, SirilConnectionError):
        return True
    text = str(exc).lower()
    return any(mark in text for mark in _CONNECTION_DEAD_MARKS)


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

# Extends the shared theme instead of editing it: DARK_STYLESHEET is copied
# verbatim between the Svenesis scripts, so a rule added inside it would
# drift the moment one of them is updated on its own.
#
# Without these, setEnabled(False) is INVISIBLE.  A stylesheet rule that
# names `color` applies in every state unless a :disabled rule overrides
# it, and the shared theme has one only for QPushButton -- so nineteen
# places in this file greyed nothing out, including the "what is switched
# off stays listed and turns grey" tables of 1.7.15.  Same palette as the
# button rule, so the two states look like one decision.
DISABLED_STYLESHEET = """
QLabel:disabled{color:#666666}
QCheckBox:disabled{color:#666666}
QCheckBox::indicator:disabled{background:#333333;border-color:#444444}
QLineEdit:disabled{background-color:#333333;color:#666666;border-color:#444444}
QComboBox:disabled{background-color:#333333;color:#666666;border-color:#444444}
QSpinBox:disabled,QDoubleSpinBox:disabled{background-color:#333333;color:#666666;border-color:#444444}
"""



# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
# Set once in main() from Siril's own preference, before the window exists.
_THEME_MODE = "dark"

# Accent, warning and hint tones per mode.  The dark values are the ones
# that were hard-coded through the file; the light ones are darkened to
# keep the same contrast against a pale window.
_THEME_COLORS = {
    "dark":  {"accent": "#88aaff", "warn": "#ffaa88",
              "hint": "#888888", "hint_off": "#555555"},
    "light": {"accent": "#2a5db0", "warn": "#a04a10",
              "hint": "#5c5c5c", "hint_off": "#aaaaaa"},
}


def _tc(role: str) -> str:
    """One themed colour by role."""
    table = _THEME_COLORS.get(_THEME_MODE) or _THEME_COLORS["dark"]
    return table.get(role, "#888888")


def _hint_style() -> str:
    """Stylesheet for a hint line under a control.

    BOTH states are spelled out because a per-widget stylesheet naming
    `color` beats every global rule, the :disabled one included -- which
    is how eight of these stayed fully lit while the control they
    describe went grey.
    """
    return (f"QLabel{{color:{_tc('hint')};font-size:9pt}}"
            f"QLabel:disabled{{color:{_tc('hint_off')}}}")


def _window_stylesheet() -> str:
    """The main window's own sheet.

    Dark mode keeps the sheet shared verbatim with the rest of the suite.
    Light mode deliberately uses NONE: Fusion's standard palette already
    is a complete, consistent light theme, and a hand-written parallel
    sheet would be a second thing to keep in step with seven other
    scripts for no gain.
    """
    if _THEME_MODE == "dark":
        return DARK_STYLESHEET + DISABLED_STYLESHEET
    return ""


def _siril_theme_mode(siril) -> str:
    """Siril's active theme as 'dark', 'light' or 'system'.

    Siril 1.4 documents 0 = dark and 1 = light.  Unknown or future values
    are handed to Qt's system appearance rather than guessed at.
    """
    try:
        value = int(siril.get_siril_config("gui", "theme"))
    except Exception as exc:
        _log_swallowed(exc)
        return "dark"
    return {0: "dark", 1: "light"}.get(value, "system")


def _apply_theme(app, siril) -> str:
    """Paint the application in Siril's theme.  Returns the mode used.

    The disabled colours are set on the PALETTE, not in the stylesheet.
    A `:disabled` CSS rule only reaches the widget classes it names --
    which is why the 1.7.16 fix had to list six of them by hand, and why
    the seven other Svenesis scripts still grey nothing out.  The
    palette's Disabled colour group reaches EVERY widget, including the
    ones added after this was written.  DISABLED_STYLESHEET stays as
    well: in dark mode the shared sheet hard-codes backgrounds on the
    input widgets, and a stylesheet background beats the palette.
    """
    global _THEME_MODE
    # Resolve FIRST and use only the resolved value below.  "system" maps
    # to dark here, and deciding the palette on the unresolved answer put
    # the dark stylesheet over a light palette -- with the light disabled
    # tones underneath it.
    _THEME_MODE = "light" if _siril_theme_mode(siril) == "light" else "dark"
    app.setStyle("Fusion")
    dark = _THEME_MODE == "dark"

    palette = QPalette() if dark else app.style().standardPalette()
    if dark:
        for role, color in (
                (QPalette.ColorRole.Window, "#2b2b2b"),
                (QPalette.ColorRole.WindowText, "#e0e0e0"),
                (QPalette.ColorRole.Base, "#3c3c3c"),
                (QPalette.ColorRole.AlternateBase, "#333333"),
                (QPalette.ColorRole.Text, "#e0e0e0"),
                (QPalette.ColorRole.Button, "#444444"),
                (QPalette.ColorRole.ButtonText, "#dddddd"),
                (QPalette.ColorRole.ToolTipBase, "#333333"),
                (QPalette.ColorRole.ToolTipText, "#ffffff"),
                (QPalette.ColorRole.Highlight, "#285299"),
                (QPalette.ColorRole.HighlightedText, "#ffffff"),
                (QPalette.ColorRole.PlaceholderText, "#909090")):
            palette.setColor(role, QColor(color))
    off = "#666666" if dark else "#a0a0a0"
    off_bg = "#333333" if dark else "#ececec"
    for role in (QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(off))
    for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Button):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(off_bg))
    app.setPalette(palette)
    return _THEME_MODE


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


def _has_sip(path: str) -> bool:
    """True if the file's astrometry carries SIP distortion terms.

    A WCS and a *distortion-aware* WCS are different facts, and only the
    second is what SPCC asks for.  Siril writes the SIP convention, so the
    order keywords are the honest test; the CTYPE suffix is checked too
    because a header may carry "RA---TAN-SIP" from another writer.

    Unreadable header -> False, i.e. "assume it is linear": re-solving an
    image that was already solved with distortions costs seconds, while
    skipping the solve on one that needs it costs the colour calibration.
    """
    header = _read_header(path)
    if header is None:
        return False
    if any(k in header for k in ("A_ORDER", "B_ORDER")):
        return True
    return "-SIP" in str(header.get("CTYPE1", "")).upper()


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


def _infer_kind_from_content(header) -> str:
    """Guess light vs dark from the header when IMAGETYP is missing.

    Some capture software never writes IMAGETYP.  Falling back to folder
    names only helps inside a N.I.N.A.-shaped tree; this works anywhere,
    from signals that are unambiguous:

      * no FILTER, no OBJECT and the telescope parked at RA=DEC=0 -- the
        shutter was closed, so it is a dark;
      * a FILTER *and* an OBJECT -- it was pointed at something, so it is
        a light.

    Bias and flat are deliberately NOT guessed: nothing in an ordinary
    header separates them reliably, and a wrong guess there corrupts the
    calibration instead of merely skipping it.  Returns "" for "no idea".
    """
    flt = _clean_token(header.get("FILTER"))
    obj = _clean_token(header.get("OBJECT"))
    try:
        ra = abs(float(header.get("RA", 0) or 0))
        dec = abs(float(header.get("DEC", 0) or 0))
    except (ValueError, TypeError):
        ra = dec = 0.0
    if not flt and not obj and ra < 1e-6 and dec < 1e-6:
        return KIND_DARK
    if flt and obj:
        return KIND_LIGHT
    return ""


def _with_fits(path: str, reader, **open_kw):
    """Open a FITS file and hand the HDU list to `reader`, surviving
    astropy's memmap refusal.

    astropy declines to memory-map an image whose header carries
    BZERO/BSCALE/BLANK -- integer camera frames, i.e. every N.I.N.A.
    sub -- and raises "Cannot load a memory-mapped image ... Set
    memmap=False." at `.data` access time, AFTER the open succeeded.  So
    a retry has to repeat the whole read, not just the open.  One run
    swallowed that error ~130 times and, worse than the noise, the flat
    consistency check read no frame at all and silently skipped, and the
    blank-frame check silently kept everything.  Mapped first (cheap for
    our own float intermediates, whose sampling reads a fraction of the
    file); on that specific refusal, reopened unmapped and read again.
    """
    try:
        with fits.open(path, memmap=True, **open_kw) as hdul:
            return reader(hdul)
    except ValueError as exc:
        if "memmap=False" not in str(exc):
            raise
    with fits.open(path, memmap=False, **open_kw) as hdul:
        return reader(hdul)


def _header_string(path: str) -> str:
    """A FITS header as text, for `set_image_metadata_from_header_string`.

    Carries the source metadata -- WCS above all -- onto an image built in
    memory, which starts with none.  Returns "" when the file cannot be
    read: a composite without a WCS can still be plate-solved, so this is
    never worth failing over.
    """
    def read(hdul):
        for hdu in hdul:
            if getattr(hdu, "data", None) is not None:
                return hdu.header.tostring(sep="\n")
        return ""

    try:
        return _with_fits(path, read, ignore_missing_simple=True)
    except Exception as exc:
        _log_swallowed(exc)
    return ""


def _fits_filter(path: str) -> str:
    """The FILTER keyword of a FITS file, or "" when it cannot be read.

    Used to confirm that a registered frame really is the channel the
    caller believes it is.  "" means "could not tell", never "wrong": a
    master whose header lost the keyword must not be thrown away over it.
    """
    def read(hdul):
        for hdu in hdul:
            token = _clean_token((hdu.header or {}).get("FILTER"))
            if token:
                return token
        return ""

    try:
        return _with_fits(path, read, ignore_missing_simple=True)
    except Exception as exc:
        _log_swallowed(exc)
    return ""


# How far two flats of the same filter may disagree before pooling them
# stops being right.  From the Flat On Flat Analyzer by Carlo Mollicone in
# the official Siril script repository: it divides one flat by another --
# a perfect pair gives a uniform image -- and reads the spread of the
# result.  Below 0.15% the pair is excellent, up to 0.3% still usable,
# beyond that something in the optical train moved.
#
# These numbers are only meaningful together with the two noise-suppressing
# steps the reference tool takes before it measures, and taking the numbers
# without the steps is how this check spent several versions reporting shot
# noise as a mismatch.  It (a) compares two flat MASTERS, not two subs, and
# (b) block-averages the map down to ~250 px on the long side first.  On a
# 3008 px frame that is 12x12 binning: together the two steps divide the
# per-pixel noise by roughly sqrt(n_frames) * 12 -- a factor of ~27 for a
# five-frame set.  Measured on a real 24 000 ADU flat, the per-pixel spread
# between two subs of the SAME night -- where the shape difference is zero
# by construction -- is 1.78%, six times the limit below.  Rebinned masters
# of two different nights of the same run give 0.03%.
FLAT_MATCH_GOOD = 0.0015
FLAT_MATCH_LIMIT = 0.0030

# Long side of the map the spread is read from, in pixels.  The reference
# tool's own figure, and the reason its thresholds are what they are.
FLAT_COMPARE_TARGET = 250
# Frames averaged per night to stand in for that night's master.  The
# master itself does not exist yet when this check runs, and past a handful
# of frames the noise is already far below the shape difference being
# looked for, so reading more only costs time on a cloud-synced folder.
FLAT_COMPARE_MAX_FRAMES = 8

# Below this many frames, a master flat carries enough of its own noise to
# be worth mentioning.  It is not a refusal -- a thin flat that describes
# the right optical train still beats a thick one that describes the wrong
# one -- so it only ever produces a note when the nights are split.
FLAT_THIN_SET = 10

# The lights box names its target, so the box and the run cannot disagree
# about which one is being stacked.  The name is appended to this.
DISCOVERED_TITLE = "Lights, Flats, Dark-Flats for Target: "

# Observing nights named individually in the Lights table before it gives
# the count instead.  The left panel is a fixed 380 px: two ISO dates are
# already 160 px of it, and at three the Details column beside them was
# squeezed to a strip too narrow to read.  Hence two, and without the
# year while they share one -- the full dates stay in the tooltip.
NIGHTS_NAMED = 2

# Rows each discovery table shows before it starts scrolling.
# Eight covers every filter wheel worth the name; beyond that the table
# would push the rest of the panel out of the window.
FILTER_TABLE_MAX_ROWS = 8

# Above this, the measured star colours no longer follow the ones the
# catalogue predicts and the white balance is a starting point rather than
# a measurement.  Read from Siril's own SPCC output; it is a REPORTING
# threshold, nothing is decided by it.  Observed on this rig: 0.15 for a
# solid narrowband fit, 6.2 for one whose channels had been flattened by
# narrowband normalisation first.
SPCC_SIGMA_LIMIT = 1.0

# How much of a log snapshot's tail identifies where it ended.  Long enough
# to be unique against a few thousand lines of Siril output, short enough
# that a bounded log buffer still holds it after the step that follows.
LOG_ANCHOR_CHARS = 400


def _spread_sample(items: list, limit: int) -> list:
    """At most `limit` items, spread EVENLY over `items`.

    `items[:limit]` takes the head, and a flat list is in acquisition
    order -- so capping at eight looked only at the start of a twenty-flat
    run and never saw whether the panel drifted afterwards.  An even
    stride keeps the same sample size and the same cost while covering
    the whole session.

    Order is preserved, which matters: the caller splits the result into
    interleaved halves and both must stay comparable.
    """
    n = len(items)
    if limit <= 0 or n <= limit:
        return list(items)
    step = n / float(limit)
    picked, seen = [], set()
    for i in range(limit):
        j = min(n - 1, int(i * step))
        if j not in seen:
            seen.add(j)
            picked.append(items[j])
    return picked


def _rebin_mean(arr, target: int = FLAT_COMPARE_TARGET):
    """Block-average a 2-D array until its long side is at most `target`.

    An integer factor, the remainder trimmed off, plain block means, as
    in the reference tool's `_rebin`.  Averaging is what makes the
    measurement possible -- a k*k block divides the noise by k while
    leaving vignetting and dust, which are hundreds of pixels across,
    exactly where they were.

    The factor is the CEILING of long_side/target, not the floor.  Floor
    division quietly violated the contract in this docstring: a 650 px
    frame came back at 325 px, and anything between `target` and
    2*target came back untouched -- so small sensors were compared on a
    finer grid with correspondingly more noise per pixel, against
    thresholds (FLAT_MATCH_GOOD/LIMIT) that assume the ~250 px scale.
    """
    long_side = max(arr.shape[-2:])
    factor = -(-long_side // max(1, target))
    if factor <= 1:
        return arr
    h = (arr.shape[0] // factor) * factor
    w = (arr.shape[1] // factor) * factor
    return (arr[:h, :w]
            .reshape(h // factor, factor, w // factor, factor)
            .mean(axis=(1, 3)))


def _flat_shape(paths: list, limit: int = FLAT_COMPARE_MAX_FRAMES,
                stats: dict | None = None):
    """One night's flats as a normalised shape map, or None.

    The frames are AVERAGED before anything else, which is what makes
    this stand in for the master that does not exist yet.  Then the map
    is block-averaged (see `_rebin_mean`) and divided by its own median,
    so a difference in illumination level -- twilight fading, a panel at
    another brightness -- does not count as disagreement.  What is left
    is the SHAPE: vignetting, dust, spacing.

    A frame whose image size differs from the MAJORITY is left out (mixed
    binning or a second sensor inside one filter's flats).  Majority, not
    "differs from the first one read": with the odd frame at the head of
    the list, that rule made the outlier the reference and discarded every
    ordinary frame behind it, so an eight-frame night was compared on a
    map built from the one frame that did not belong.  Ties go to the
    larger image, which is the unbinned one.

    Pass ``stats`` to learn about it: the dict comes back with ``used`` and
    ``skipped`` counts, so the caller can say a map was built from fewer
    frames than were offered -- silently thinning the sample was how a
    two-frame map once posed as an eight-frame one.
    """
    def read(hdul):
        data = next((h.data for h in hdul
                     if getattr(h, "data", None) is not None), None)
        if data is None:
            return None
        # float32 throughout the heavy part: a flat sits near
        # 24 000 ADU and eight of them sum to under 200 000, which
        # a 24-bit mantissa holds exactly.  The map is a few
        # hundred pixels across by the time precision could matter.
        # Converted INSIDE the read: a memmapped array does not survive
        # the file being closed.
        return np.asarray(data, dtype=np.float32)

    # One running sum PER image size, rather than a list of frames.  The
    # majority cannot be known until every frame has been read, but
    # keeping them all to find it would hold eight 3008x3008 float32
    # planes at once -- ~290 MB inside Siril's own process, for a map a
    # few hundred pixels across.  There is one accumulator in the normal
    # case and two on the mixed night this rule exists for.
    sums: dict = {}
    read_total = 0
    for path in _spread_sample(paths, limit):
        try:
            frame = _with_fits(path, read, ignore_missing_simple=True)
            if frame is None:
                continue
        except Exception as exc:
            _log_swallowed(exc)
            continue
        while frame.ndim > 2:               # (C, H, W) -> one plane
            frame = frame.mean(axis=0)
        read_total += 1
        have = sums.get(frame.shape)
        sums[frame.shape] = (frame if have is None else have[0] + frame,
                             1 if have is None else have[1] + 1)
    if stats is not None:
        stats["used"], stats["skipped"] = 0, 0
    if not sums:
        return None
    # The size most of the night agrees on -- not "the first one read".
    # With the odd frame at the head of the list that rule made the
    # outlier the reference and skipped every ordinary frame behind it.
    # Ties go to the larger image, i.e. the unbinned one.
    shape = max(sums, key=lambda sh: (sums[sh][1], sh[0] * sh[1]))
    stack, used = sums[shape]
    skipped = read_total - used
    if stats is not None:
        stats["used"], stats["skipped"] = used, skipped
    if stack is None or not used:
        return None
    return _flat_normalise(stack / used)


def _flat_normalise(frame):
    """Bin a summed flat down and divide it by its own median, or None.

    The whole array side of the measurement, kept free of file reading so
    it can be checked against input with a known answer -- including the
    one that matters, a pair that differs by NOTHING but noise.
    """
    shape = np.asarray(_rebin_mean(frame), dtype=np.float64)
    median = float(np.median(shape))
    return shape / median if median > 0 else None


def _flat_ratio_spread(sa, sb) -> float | None:
    """Standard deviation of one shape map divided by the other.

    Kept apart from the reading so the number itself can be checked
    against arrays with a known answer, without a FITS file in sight.
    """
    if sa is None or sb is None or sa.shape != sb.shape:
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = sa / np.where(sb <= 0, np.nan, sb)
        spread = float(np.nanstd(ratio))
    return spread if np.isfinite(spread) else None


def _floor_rescale(n_half_a: int, n_half_b: int,
                   n_base: int, n_other: int) -> float:
    """Scale a half-vs-half spread onto the night-vs-night comparison.

    The noise floor is measured by splitting the reference night in half
    and comparing the halves -- but each half averages FEWER frames than
    the maps in the real comparison, so its noise is higher.  Left
    unscaled, the floor overstated the true comparison noise by a
    measured factor of 1.415 (sqrt 2) at equal frame counts, and "no
    shape difference detectable" then covered real differences as large
    as the noise itself -- the opposite of what an error bar is for.

    Per-map variance goes as 1/n (each map is a mean of n frames of
    similar per-frame noise), and the spread of a ratio of two maps adds
    their variances.  So the measured half spread relates to the wanted
    night spread by the ratio of those sums:

        floor_true = floor_half * sqrt((1/n_base + 1/n_other)
                                       / (1/n_half_a + 1/n_half_b))

    All four counts must be the counts `_flat_shape` actually AVERAGED
    (its `limit` caps them) -- when both halves already hit the cap the
    factor correctly comes out 1, because then the halves carry the same
    noise as the full maps.
    """
    h = 1.0 / max(1, n_half_a) + 1.0 / max(1, n_half_b)
    t = 1.0 / max(1, n_base) + 1.0 / max(1, n_other)
    return math.sqrt(t / h)


# Everything the script uses BEYOND the floor, and what happens without
# it.  A missing call is caught by the try/except around every one of
# these -- which is exactly the problem: the feature would fall back
# silently, for the whole life of the installation, and nobody would know
# why the report keeps saying "estimated".  Naming them once at startup
# turns that into an answerable question.
OPTIONAL_API = (
    ("Measured frame counts and registration statistics",
     ("get_seq",),
     "the frame count is estimated from the files instead, and the "
     "report marks it"),
    ("Colour composition in memory",
     ("get_image_pixeldata", "set_image_pixeldata", "image_lock",
      "is_image_loaded"),
     "rgbcomp composes instead, which cannot take a path containing a "
     "space"),
    ("Metadata (WCS) on the composite",
     ("set_image_metadata_from_header_string",),
     "the composite is written without the source WCS; plate-solving "
     "still works"),
    ("Reading Siril's log",
     ("get_siril_log",),
     "alignment star-pair counts are not reported, and SPCC names are "
     "checked against the local database only"),
    ("Finding Siril's data directory",
     ("get_siril_userdatadir",),
     "the SPCC database is looked for in the usual places instead"),
)


def _missing_capabilities(siril) -> list:
    """``[(feature, missing calls, consequence)]`` for this sirilpy.

    Asked with `hasattr`, not by version number: what matters is whether
    the call exists, and a version table would be one more thing to keep
    true.
    """
    out = []
    for feature, calls, consequence in OPTIONAL_API:
        absent = [c for c in calls if not hasattr(siril, c)]
        if absent:
            out.append((feature, absent, consequence))
    return out


def _median(values: list) -> float:
    """True median, including the average of the middle two on even counts.

    Written out rather than imported: `statistics.median` would do, but
    this file already keeps its numeric helpers together and the even
    case is exactly the one that gets hand-rolled wrongly.
    """
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return 0.0
    mid = n // 2
    return (ordered[mid] if n % 2
            else (ordered[mid - 1] + ordered[mid]) / 2.0)


def _exp_tag(exp: float) -> str:
    """A Siril-safe sequence-name token for an exposure, e.g. 1.5 -> "1p5s".

    Sequence names end up in filenames and in Siril command lines, where a
    dot would start what looks like an extension.  The digits are written
    out rather than formatted with "g": at 1e6 and above (and below 1e-5)
    "g" switches to exponent notation, and "1e+09" carries a plus that no
    amount of dot-replacing removes.  Real exposures never reach that, but
    a token generator that is safe only for plausible input is not safe.
    """
    try:
        value = float(exp)
    except (ValueError, TypeError):
        return "0s"
    if not math.isfinite(value):
        return "0s"
    text = f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return text.replace(".", "p").replace("-", "m") + "s"


def _night_key(date_obs: str) -> str:
    """The observing night a frame belongs to, as ``YYYY-MM-DD``.

    Subtracting twelve hours puts the whole dark period under one date:
    a session from 21:00 to 03:00 is one night, not two.  That is the
    problem a folder-per-calendar-date layout cannot express, and it is
    why the flats of a session can otherwise end up paired with only half
    of its lights.

    Returns "" when DATE-OBS is missing or unparseable, so callers can
    fall back to the path.
    """
    txt = (date_obs or "").strip().replace("Z", "")
    if not txt:
        return ""
    try:
        return (datetime.datetime.fromisoformat(txt)
                - datetime.timedelta(hours=12)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


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


def _short_nights(nights: list) -> list:
    """ISO dates with a shared year dropped: 2026-09-05 -> 09-05.

    The table lives in a fixed 380 px panel, where the year is four
    characters of width repeated on every row and carrying nothing: a
    target is not imaged across a new year often, and when it is, the
    year comes back because it is no longer shared.  The tooltip always
    holds the dates in full.
    """
    years = {n[:4] for n in nights if len(n) >= 10 and n[4] == "-"}
    if len(years) != 1 or len(nights) != len([n for n in nights
                                              if len(n) >= 10]):
        return list(nights)
    return [n[5:] for n in nights]


def _night_of(path: str, nights: dict | None = None) -> str:
    """The observing night a frame belongs to, best source first.

    `_night_key` (noon-to-noon, from the frame's own DATE-OBS) is the
    answer that survives a session running past midnight; `_path_date`
    is the folder name, which splits exactly that session in two.  For
    several releases the header key was computed for every frame during
    discovery and then never read: every night decision in the run --
    which flats belong to which lights, whether a filter is calibrated
    per night, what the flat-consistency check compares -- went through
    the folder date alone, so the fix `_night_key` exists for was inert.

    Discovery records the header answer per path in `nights`; anything
    it could not read (no DATE-OBS, unparseable, a file discovery never
    inspected) falls back to the folder.  Both sides of every comparison
    go through this function, so a mixed set degrades to the old
    behaviour rather than to a mismatch.
    """
    if nights:
        night = nights.get(path)
        if night:
            return night
    return _path_date(path)


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

    The camera is part of the key.  Without it, two bodies of the same
    model -- same size, same gain, same binning -- share a group and get
    averaged into one master, and the INSTRUME test in
    `_signature_matches` then checks a group that is already mixed.
    """
    temp = info.get("temp_v")
    return (round(float(info.get("exp_s") or 0.0), 3),
            info.get("gain_v"),
            info.get("binning", 1),
            info.get("dims"),
            (round(float(temp)) if with_temp and temp is not None else None),
            info.get("instrument") or None)


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

    The camera must be the same one where both headers name it: image size
    and binning are only a proxy, and two cameras sharing a sensor format
    would otherwise calibrate each other.  Exposure, gain, binning and
    image size must agree exactly; the cooled setpoint may drift a little
    because CCD-TEMP is a measurement.  A missing
    gain, temperature or size is treated as "unknown, don't block" -- refusing
    a usable master because a keyword is absent would be worse than using it.
    Exposure is the exception: `_inspect` reports an unreadable EXPTIME as
    0.0, and 0 s vs 120 s is exactly the mismatch that must not slip through,
    so an unknown exposure blocks the match.
    """
    mi, ti = master.get("instrument"), target.get("instrument")
    if mi and ti and mi != ti:
        return False        # a dark from a different camera, never
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


# Above this the channels are not describing the same sky pixel any
# more.  Registration works to well under a pixel, so anything past one
# whole pixel is not tolerance, it is a different solution.
OVERLAY_MAX_PX = 1.0


def _overlay_error_px(paths: list) -> tuple[float, str] | None:
    """Worst distance, in pixels, between what two channels call one point.

    Equal image sizes do NOT prove the channels overlay -- four masters of
    2942x2876 can still sit pixels apart, and `_mixed_grids` cannot see
    it.  This takes five points of the first master (corners and centre),
    converts them to sky through ITS solution and back to pixels through
    each other master's, and reports the largest displacement.

    Header-only: no pixel data is read.  Returns None when any master
    lacks a usable celestial solution, which means "cannot tell" and must
    never be reported as agreement.  The returned name is the channel
    that sat furthest out.
    """
    if len(paths) < 2:
        return (0.0, "")
    try:
        heads = [(name, fits.getheader(path, ext=0)) for name, path in paths]
        ref = WCS(heads[0][1]).celestial
        if not ref.has_celestial:
            return None
        w = min(int(h.get("NAXIS1", 0)) for _n, h in heads)
        h_px = min(int(h.get("NAXIS2", 0)) for _n, h in heads)
        if w <= 1 or h_px <= 1:
            return None
        xs = np.asarray([0.0, w - 1.0, 0.0, w - 1.0, (w - 1.0) / 2.0])
        ys = np.asarray([0.0, 0.0, h_px - 1.0, h_px - 1.0, (h_px - 1.0) / 2.0])
        worst, who = 0.0, ""
        for name, head in heads[1:]:
            other = WCS(head).celestial
            if not other.has_celestial:
                return None
            sky = other.all_pix2world(xs, ys, 0)
            back = ref.all_world2pix(*sky, 0)
            off = np.hypot(back[0] - xs, back[1] - ys)
            if not np.all(np.isfinite(off)):
                return None
            if float(np.max(off)) > worst:
                worst, who = float(np.max(off)), name
        return (worst, who)
    except Exception as exc:
        _log_swallowed(exc)
        return None


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
    # IMAGETYP first, then the folder layout, then the content itself.
    # Content last on purpose: it is the only one that can be wrong about a
    # frame whose keyword and folder both said something sensible.
    out["kind"] = (_classify_kind(_clean_token(header.get("IMAGETYP")))
                   or _classify_path(parts)
                   or _infer_kind_from_content(header))
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
    # Six spellings in the wild.  AMSP, Siril's own multi-session script,
    # reads all of these; missing one means the temperature silently counts
    # as "unknown" and a dark from another setpoint slips through.
    for key in ("CCD-TEMP", "CCD_TEMP", "CCDTEMP", "TEMPERAT",
                "CAMTCCD", "SET-TEMP"):
        if key in header:
            try:
                out["temp_v"] = float(header[key])
                out["temp"] = f"{out['temp_v']:.0f}C"
            except (ValueError, TypeError):
                pass
            break
    # The camera, so a dark from a DIFFERENT one cannot be matched to these
    # lights.  Image size and binning are only a proxy: two cameras sharing
    # a sensor format pass that test and would calibrate each other.
    out["instrument"] = _clean_token(header.get("INSTRUME"))
    # The observing night, computed from when the frame was taken rather
    # than from a folder name.  Noon-to-noon, so a session that runs past
    # midnight stays ONE night -- the folder-per-date layout splits it in
    # two and pairs half the lights with the wrong flats.
    out["night"] = _night_key(str(header.get("DATE-OBS", "")))
    return out


def _is_blank_frame(path: str) -> bool:
    """True if a frame carries no usable signal (black / blank / stuck).

    Cloud outages, a closed flap, a failed download or a dropped exposure
    leave frames that are all-zero or perfectly flat.  They poison
    registration ("no stars found") and drag the stack down, so they are
    skipped.  Only a sample is examined -- eight rows spread evenly down
    the frame where astropy offers `.section` (which decompresses just
    those tiles of a Rice-compressed sub), otherwise every 8th pixel in
    each axis.  Either way it is a fraction of a percent of the data:
    enough to tell "black" from "sky", and fast on a cloud-synced folder.
    On any doubt the frame is KEPT (returns False): dropping a good frame
    is worse than keeping a marginal one.
    """
    def read(hdul):
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
        return None if image_hdu is None else _sample_pixels(image_hdu)

    try:
        sample = _with_fits(path, read)
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
    """Human-friendly integration time: 4560 -> '1h 16m'.

    Every unusable input becomes an em-dash rather than an exception.
    Infinity needs saying separately: `int(round(inf))` raises
    OverflowError, which is neither ValueError nor TypeError, and a
    corrupt EXPTIME reaching the report would have taken the whole
    document down with it.
    """
    try:
        value = float(seconds)
    except (ValueError, TypeError):
        return "—"
    if not math.isfinite(value):
        return "—"
    secs = int(round(value))
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
            # path -> observing night, from the frame's OWN DATE-OBS
            # (noon-to-noon).  The header is read once here anyway, and
            # this is what lets every later night decision use it instead
            # of the folder name -- see `_night_of`.
            nights: dict[str, str] = {}
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
                if info.get("night"):
                    nights[path] = info["night"]

                if kind in calib:
                    # Flats belong to a filter; darks/bias to a signature --
                    # darks additionally split by temperature (see
                    # _calib_signature).
                    key = (info["filter"] if kind in (KIND_FLAT, KIND_DARKFLAT)
                           else _calib_signature(
                               info, with_temp=(kind == KIND_DARK)))
                    grp = calib[kind].setdefault(
                        key, {"files": [], "info": info,
                              "date": _night_of(path, nights)})
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
                     "info": info, "dates": set(), "exps": set(),
                     "by_exp": {}})
                g["files"].append(path)
                g["exp_total"] = g.get("exp_total", 0.0) + info["exp_s"]
                # Through `_night_of` like every other night decision --
                # one rule in one place, so the lights' nights and the
                # flats' nights can never be derived differently.
                g["dates"].add(_night_of(path, nights))
                exp_key = round(float(info["exp_s"]), 3)
                g["exps"].add(exp_key)
                # Keep the frames of each exposure together.  A dark is only
                # valid for the exposure it was shot at, so a filter that
                # mixes exposures has to be calibrated in parts -- see
                # `_exposure_split`.
                g["by_exp"].setdefault(exp_key, []).append(path)
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
                 "nights": nights, "unsupported": unsupported})
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
                 calib: dict | None = None, nights: dict | None = None):
        super().__init__()
        self.siril = siril
        self._groups = groups
        # path -> observing night, taken from each frame's own DATE-OBS
        # during discovery.  Every night decision below goes through
        # `_night_of` with this map, so a session that runs past midnight
        # stays ONE night instead of being split by the date folder.
        self._nights = nights or {}
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
        # Built offset masters, keyed by their source group, so two filters
        # sharing a flat exposure stack it once.
        self._offset_cache: dict = {}
        # filter -> what its flats were offset-corrected with, for the report.
        self._flat_offset_note: dict = {}
        # {filter: (spread, other_night, reference_night, noise_floor)}
        # for flats that disagree across nights -- the report has to name
        # them.  The floor is the fourth member and may be None when it
        # could not be measured; `_write_docs` unpacks all four.
        self._flat_warn: dict = {}
        # {filter: {night: master path}} when the flats are kept per night.
        # Empty means one pooled master per filter, the historical shape.
        self._flat_nights: dict = {}
        # {filter: [(night, n_lights, what)]} -- what each night's lights
        # were really flat-corrected with, for the log and the report.
        self._night_notes: dict = {}
        # Written by _synthetic_luminance; the report and todo.md name it.
        self._synth_lum: str = ""
        # How the composite was actually assembled -- in memory or through
        # rgbcomp.  The report states the route that ran, not the usual one.
        self._compose_how: str = ""
        # {filter: why} for filters whose frames were calibrated in parts
        # and merged again -- recorded so the report can say so, since
        # nothing in the finished master reveals it.
        self._split_filters: dict = {}
        # {filter: (process dir, sequences, staged dirs)} that a merged
        # sequence still symlinks to, freed once registration has written
        # frames of its own.
        self._part_cleanup: dict = {}
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
        # filter -> (frames staged, frames actually integrated).  The
        # second is measured from the registered sequence wherever that
        # can be read; see _measured for which of the two it was.
        self._stacked_counts: dict = {}
        # Was the integrated count MEASURED (from the registered sequence)
        # or estimated?  The report must not present one as the other.
        self._measured: dict = {}
        # Per-channel registration statistics, when Siril would hand them
        # over: median FWHM / roundness / star count.
        self._reg_stats: dict = {}
        # The rejection algorithm that really ran, per filter.  Recomputing
        # it in the report would hide a fallback (see _stack).
        self._rej_labels: dict = {}
        # filter -> (frame count the quality filters were decided on,
        # whether they were actually handed to seqapplyreg).  Recording it
        # is not optional: registration can drop frames afterwards, so the
        # count in _stacked_counts is no longer the one the decision was
        # made on, and re-deriving from it flips the answer.
        self._qf_decision: dict = {}
        # filter -> star pairs its cross-filter alignment was fitted on,
        # and which filter Siril chose as the reference.  Empty when the
        # log could not be read or its format was not recognised.
        self._align_pairs: dict = {}
        self._align_ref = None
        # How well the photometric colour solution fitted, read back from
        # Siril's own log.  Empty when nothing was calibrated or the
        # output could not be parsed -- the report then stays silent.
        self._spcc_fit: dict = {}
        # Said once per run, not once per reader.
        self._log_read_warned: set = set()
        # Filters left unstacked because the palette does not read them.
        self._skipped_by_palette: list = []
        # filter -> registration options that could not be honoured.
        # Empty is the normal case; a non-empty entry means the master
        # differs from what the options say, and the report must not
        # describe it as if they had run.
        self._reg_degraded: dict = {}
        # filter -> WHY those options did not reach the master.  There are
        # two causes and they need different words: Siril REFUSED the
        # argument set (and a smaller retry ran), or Siril ACCEPTED it and
        # did not apply it.  One shared sentence would be wrong for one of
        # them.  Missing entry = the refusal, which is the older case.
        self._reg_degraded_why: dict = {}
        # Set when drizzle ran on a set too small to fill its finer grid.
        self._drizzle_warned = False
        # {filter: why} for channels that STACKED but did not survive the
        # cross-filter alignment.  Without this the report fell through to
        # "not reached -- the run was stopped" for a filter whose master is
        # sitting complete in masters/, which is the opposite of true.
        self._align_dropped: dict = {}
        # Did the alignment really re-project onto the shared -framing=min
        # grid?  The single-pass fallback registers without it, and the
        # composition guard must not take "alignment ran" as "one grid".
        self._align_framing_min = False
        # Siril's data directory, asked for once (None = not asked yet).
        self._spcc_root_cache: str | None = None
        # Every Siril command this run issued, in order, mirrored to
        # commands.ssf beside the output.  Written for replay: the run can
        # be repeated headless with siril-cli, which is how a command-level
        # defect gets bisected without the GUI in the way.
        self._commands: list[str] = []
        # filter -> [(part, frames)] for a split refused because a part
        # was too small to be a sequence.  The run has to say so: it had
        # announced per-night calibration during discovery.
        self._split_refused: dict = {}
        # filter -> the `-cc=dark` pair already announced, so three
        # `calibrate` calls for one filter do not say it three times.
        self._cc_said: dict = {}
        # Where the narrowband/RBF mismatch has already been said, so
        # four channels do not repeat one sentence four times.
        self._rbf_warned: set = set()
        # Filters whose star detection hit Siril's ceiling, so their
        # star count is the cap rather than a property of the frame.
        self._stars_capped: set = set()
        # Worst channel-to-channel astrometric disagreement, in pixels,
        # or None when it could not be told.  The report quotes it.
        self._overlay_px = None
        # filter -> the `-cc=dark` pair actually handed to Siril, so the
        # report quotes what ran instead of the constant in the tooltip.
        self._cc_used: dict = {}
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
        """Run one Siril command, telling a dead link apart from a refusal.

        A refusal (bad arguments, unusable frames) raises CommandError
        and the callers' fallback chains are the right response.  A dead
        transport matches the very same `except` tuples and would send
        the run cascading through fallbacks that cannot work; it becomes
        SirilGoneError here, at the single funnel every command uses,
        and fails the RUN with one honest message instead.
        """
        self._record_command(*args)
        try:
            self.siril.cmd(*args)
        except Exception as exc:
            if _connection_dead(exc):
                raise SirilGoneError(str(exc)) from exc
            raise

    def _verify_outputs(self, paths, stage: str) -> None:
        """Fail the run when a stage reported success but wrote nothing.

        A Siril command that returns without raising has not necessarily
        produced its file -- a full disk, a refused path or a silently
        skipped save all look like success from here.  Checking at the
        stage boundary names the stage that failed; noticing three steps
        later names the wrong one.
        """
        missing = [str(p) for p in paths
                   if not (p and os.path.isfile(p)
                           and os.path.getsize(p) > 0)]
        if missing:
            raise RuntimeError(
                f"{stage} finished without writing its output: "
                + ", ".join(os.path.basename(m) for m in missing))

    def _clear_stale_dir(self, path: str, what: str) -> None:
        """Empty a working directory BEFORE it is refilled.

        Not cosmetic.  The run stages fresh frames into this same place
        under index-based names, so anything a failed delete leaves
        behind is picked up by the next `link` as if it belonged to this
        run -- a leftover frame from a longer previous run would be
        stacked into the master without a word.  Silence here is the one
        outcome that must not happen, so this raises.
        """
        if not os.path.isdir(path):
            return
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path):
            return
        try:
            left = len(os.listdir(path))
        except OSError:
            left = -1
        raise RuntimeError(
            f"Could not clear the {what} working directory before "
            f"refilling it ({path}"
            + (f", {left} entr{'y' if left == 1 else 'ies'} left" if left >= 0
               else "")
            + "). Frames from an earlier run would be stacked into this "
            "one, so the run stopped instead. Close anything holding "
            "those files open, or delete the folder by hand.")

    def _discard_dir(self, path: str, what: str) -> bool:
        """Delete a directory that is no longer needed.

        The opposite case to `_clear_stale_dir`: nothing reads this path
        again, so a failure costs disk space and nothing else.  It is
        still SAID -- `ignore_errors=True` on its own turned a folder
        that quietly survived into a folder the user believes is gone.
        """
        if not os.path.isdir(path):
            return True
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path):
            return True
        self._emit(
            f"  Could not delete the {what} ({path}) — it is still there "
            "and still takes up space. Processing continues; nothing "
            "downstream reads it.", LogColor.SALMON)
        return False

    def _record_command(self, *args) -> None:
        """Append one command to commands.ssf beside the output.

        Recorded BEFORE the call, so a command that kills the run is in
        the file rather than missing from it -- that one is usually the
        interesting line.

        The file is a faithful record, not a certified script: `load_seq`
        is GUI-only and Siril refuses it in a script, so a headless replay
        has to drop those lines.  They are marked in place instead of
        being silently rewritten, because a record that quietly differs
        from what ran is worse than none.
        """
        self._commands.append(" ".join(str(a) for a in args))
        self._write_commands()

    def _note_command(self, text: str) -> None:
        """Record, in place, a step Siril never saw.

        The gaps this fills are not cosmetic.  Staging frames into the
        work folders, copying a master to masters/, pushing composed
        pixels through sirilpy -- none of it issues a Siril command, so
        the record read back looks like a complete recipe when it is
        not: `link bias` over a directory nothing filled, and a `new`
        that appears to compose the three masters loaded before it when
        it only makes the blank canvas they are written into.  That last
        one fails SILENTLY on a replay, saving an empty colour image
        under the right name.  A comment costs one line and turns each
        of those into a gap the reader can see.
        """
        self._commands.append(f"# {text}")
        self._write_commands()

    def _here(self, path: str) -> str:
        """A path as the record shows it: relative to the output folder."""
        try:
            return os.path.relpath(path, self._out_dir)
        except ValueError:                   # another drive, on Windows
            return path

    def _write_commands(self) -> None:
        """Rewrite commands.ssf from scratch.

        Rewritten per line rather than appended to, so the file on disk
        is always a complete, well-formed document -- including its
        header -- however the run ends.
        """
        try:
            path = os.path.join(self._out_dir, COMMANDS_FILENAME)
            body = [
                "# Siril commands issued by Svenesis ImageMono Train "
                f"v{VERSION}",
                f"# Target: {self._target}",
                f"# Written: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
                "#",
                "# A RECORD of what Siril was asked to do, in order.  It is "
                "not a script that",
                "# reproduces this run on its own: the steps the script "
                "performs ITSELF issue no",
                "# Siril command, and every one of them is marked below "
                "with a '#' line.  Replayed",
                "# as it stands, this file would find the work folders "
                "empty -- and would save a",
                "# BLANK colour image, because `new` only makes the canvas "
                "and the pixels arrive",
                "# through sirilpy.",
                "#",
                "# Two more things stand between this file and a replay: "
                "lines marked GUI-ONLY,",
                "# which Siril refuses in a script, and " + WORK_DIRNAME
                + "/, which this run deletes when it",
                "# finishes.  What it is good for: reading back what ran, "
                "bisecting a failure with",
                "# siril-cli -s, and as the starting point for a script "
                "built by hand.",
                "",
                f"requires {SIRIL_MIN_VERSION}",
                "",
            ]
            for cmd in self._commands:
                if cmd.split(" ", 1)[0] in _SCRIPT_FORBIDDEN_COMMANDS:
                    body.append(f"{cmd}    # GUI-ONLY")
                else:
                    body.append(cmd)
            _atomic_write_text(path, "\n".join(body) + "\n")
        except OSError as exc:
            _log_swallowed(exc)

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

        The ``MIN_STACK_FRAMES`` floor is applied to the COMBINATION, not
        to each filter on its own.  Siril keeps the frames that pass every
        filter given, so the survivors are an intersection: three 60%
        filters on eight frames each clear a per-filter check (int(4.8)=4)
        while their intersection can be one or two.  The guard then
        promised a floor it had no way to hold.

        The running estimate multiplies the shares, which is what
        independence predicts.  The comment here used to argue that the
        metrics are correlated -- a bad frame being bad on several at
        once -- and that the true count is therefore HIGHER, leaving the
        guard a margin.  Four channels of one NGC 6946 run say otherwise:
        57 against a predicted 58, 55 against 55.8, 148 against 149.4, 52
        against 51.9.  The two metrics are independent to within a frame
        here, and three of the four came out slightly BELOW the product.
        There is no margin, so the estimate is floored with int() rather
        than rounded, and the claim of one has been removed instead of
        being left to justify a guard it does not support.

        k-sigma has no estimate at all: how many frames lie beyond k sigma
        is a property of the data, not of the setting.  Rather than invent
        a number, that mode caps how many k-sigma filters are stacked up
        (see ``FILTER_MAX_KSIGMA``) and the report marks its counts as
        upper bounds.
        """
        return self._quality_filter_plan(n_frames)[0]

    def _projected_frame_count(self, n_frames: int) -> int:
        """Frames expected to survive -- the PESSIMISTIC estimate.

        The counterpart to `_effective_frame_count`, and the two must be
        used in opposite places.  Survivors pass EVERY filter, so:

          * the product of the shares is what independence predicts;
          * `min(shares)` is what perfect correlation predicts, and is an
            upper bound on the survivors.

        An upper bound on survivors is a LOWER bound on the loss, which
        is the wrong direction for a warning about losing too much.  Four
        channels of one NGC 6946 run: the min-bound predicted 13-14%
        dropped against 21-23% really dropped, so the "you are losing a
        lot of frames" note stayed silent on all four.

        Measured, the product is accurate to about one frame and can sit
        a frame OPTIMISTIC (57 against 58, 55 against 55.8, 148 against
        149.4) -- so it is floored, never rounded up.

        k-sigma returns the full count: how many frames lie beyond k
        sigma is a property of the data, and inventing a number would be
        worse than declining to warn.
        """
        _args, _skipped, share = self._quality_filter_plan(n_frames)
        if share >= 1.0:
            return n_frames
        return max(1, int(n_frames * share))

    def _quality_filter_plan(self, n_frames: int) -> tuple[list, list, float]:
        """``(args, skipped, share)`` -- the arguments AND what was dropped.

        `skipped` carries ``(flag, value, why)`` for every filter the user
        switched on that does not reach Siril.  It exists because there
        was no way to tell: a filter refused by the MIN_STACK_FRAMES
        floor simply vanished, and the caller could only see that the
        argument list was shorter than the tick boxes suggested.  With
        the spin boxes accepting 1-100, asking for the best 15% of 25
        frames produced NO filter and NO message -- the full stack, and
        nothing said.

        `share` is the projected survivor fraction, the product of the
        percentages.  See `_projected_frame_count` for which direction it
        errs in and where that is safe to use.
        """
        args: list = []
        skipped: list = []
        share = 1.0                 # projected survivors, as a fraction
        if n_frames < FILTER_MIN_FRAMES:
            return args, skipped, share
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
                    continue                 # 100% keeps everything, silently
                left = int(n_frames * share * value / 100)
                if left < MIN_STACK_FRAMES:
                    skipped.append((
                        flag, f"{value}%",
                        f"would leave about {left} frame(s), under the "
                        f"floor of {MIN_STACK_FRAMES}"))
                    continue
                share *= value / 100.0
            elif len(args) >= FILTER_MAX_KSIGMA:
                # Nothing here can predict the survivors, so the only
                # honest brake is on how many cuts are combined.
                skipped.append((
                    flag, f"{value}k",
                    f"more than {FILTER_MAX_KSIGMA} k-sigma cuts at once, "
                    "and how many frames each one takes cannot be "
                    "predicted"))
                continue
            args.append(f"{flag}={value}{suffix}")
        return args, skipped, share

    def _seq_quality(self, process_dir: str, seq: str, filt: str,
                     expect: int = 0) -> dict | None:
        """Ask Siril for the registration data of a finished sequence.

        `get_seq()` hands back what Siril itself recorded per frame:
        which frames are still included, and for each of them the FWHM,
        the roundness and the number of stars it detected.  That turns
        three numbers this script used to ESTIMATE into measurements --
        the frame count above all, which decides the rejection algorithm
        and is quoted in the report.

        The sequence has to be loaded for the API to answer, so this runs
        `load_seq` first.  Siril names the file with a trailing underscore
        (`r_pp_lights_`) even though `stack` and friends take the bare
        stem, so the underscored form is tried FIRST -- asking for the
        bare name first made every filter log a failed command and a
        swallowed error before the second attempt succeeded.  The bare
        name stays as the fallback: scripts in the wild load it both
        ways, and an older Siril may yet write it without.

        `expect` is the frame count taken from the files on disk.  If a
        load quietly leaves an EARLIER sequence current, `get_seq()`
        answers about that one instead -- and its count would then drive
        the rejection band.  A mismatch is therefore treated as "wrong
        sequence, cannot tell", not as data.

        Returns None on any failure -- an unreadable sequence is "cannot
        tell", never "nothing there", and the file count remains as the
        fallback it always was.
        """
        data = None
        for name in (f"{seq}_", seq):
            try:
                self._cmd("load_seq", f'"{name}"')
                data = self.siril.get_seq()
            except Exception as exc:
                _log_swallowed(exc)
                continue
            if data is not None:
                break
        if data is None or not getattr(data, "imgparam", None):
            return None
        if expect and getattr(data, "number", 0) != expect:
            self._emit(
                f"  Registration data skipped: Siril reports "
                f"{getattr(data, 'number', 0)} frame(s) where the folder "
                f"holds {expect} — that is not this sequence.",
                LogColor.SALMON)
            return None
        try:
            included = [i for i, p in enumerate(data.imgparam)
                        if getattr(p, "incl", True)]
            out = {"included": len(included), "total": data.number}
            regs = getattr(data, "regparam", None) or []
            layer = next((r for r in regs
                          if r and any(x is not None for x in r)), None)
            if layer:
                for key, attr in (("fwhm", "fwhm"),
                                  ("roundness", "roundness"),
                                  ("stars", "number_of_stars")):
                    # The trailing `and getattr(...)` is a TRUTHINESS test,
                    # so a zero is dropped from the sample.  That looks
                    # like a statistical bug -- a real measurement of zero
                    # would flatter the median by vanishing -- and it is
                    # not, for all three fields:
                    #
                    #   roundness  sirilpy documents the field itself as
                    #              "0 when uninit, ]0, 1] when set", so a
                    #              zero is BY DEFINITION not a measurement;
                    #   fwhm       a star with a full width of zero does
                    #              not exist; the struct simply defaults
                    #              the field to 0.0;
                    #   stars      a frame Siril found no stars in cannot
                    #              be registered, so it is never `incl`
                    #              and never reaches `included` here.
                    #
                    # Written out because the fix for the apparent bug --
                    # `is not None` -- would pull uninitialised frames into
                    # the median and make the number worse.
                    vals = [float(getattr(layer[i], attr))
                            for i in included
                            if i < len(layer) and layer[i] is not None
                            and getattr(layer[i], attr, None)]
                    if vals:
                        out[key] = _median(vals)
        except (AttributeError, TypeError, ValueError, IndexError) as exc:
            _log_swallowed(exc)
            return None
        if out.get("fwhm"):
            self._reg_stats[filt] = out
            # A value Siril did not record is "unknown", and printing it
            # as 0.00 would read as catastrophic trailing / zero stars.
            parts = [f"median FWHM {out['fwhm']:.2f} px"]
            if out.get("roundness") is not None:
                parts.append(f"roundness {out['roundness']:.2f}")
            capped = (out.get("stars") is not None
                      and int(out["stars"]) >= SIRIL_MAX_STARS)
            if out.get("stars") is not None:
                parts.append(f"{int(out['stars'])} stars"
                             + (" (Siril's cap — not a measurement)"
                                if capped else ""))
            self._emit(
                f"  Registration data: {out['included']} of {out['total']} "
                f"frame(s) included, " + ", ".join(parts) + ".",
                LogColor.BLUE)
            if capped:
                self._stars_capped.add(filt)
                if (self._opts.get("weighting", True)
                        and _weight_token(self._opts) == "nbstars"):
                    # Said once per filter, where the number that proves
                    # it has just been printed.
                    self._emit(
                        f"  {filt}: frame weighting is set to 'Number of "
                        f"stars', but the median frame already hits "
                        f"Siril's ceiling of {SIRIL_MAX_STARS} — every "
                        "such frame gets the SAME weight, so the "
                        "weighting does almost nothing here. 'Noise' or "
                        "'Weighted FWHM' still separate these frames.",
                        LogColor.SALMON)
        return out

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

    def _reg_frame_sizes(self, process_dir: str, seq: str) -> set:
        """Image sizes of the frames a registration exported.

        `-framing=min` re-projects every frame onto the shared
        intersection, so ONE size means it applied and several mean it
        did not.  Headers only (NAXIS1/NAXIS2), and it stops at the
        first disagreement -- which is the answer worth having, and
        makes the bad case cost two reads instead of two hundred.
        """
        pat = re.compile(re.escape(seq) + r"_\d+" + re.escape(self._ext)
                         + "$", re.IGNORECASE)
        try:
            names = sorted(f for f in os.listdir(process_dir)
                           if pat.match(f))
        except OSError as exc:
            _log_swallowed(exc)
            return set()
        sizes: set = set()
        for name in names:
            header = _read_header(os.path.join(process_dir, name))
            if header is None:
                continue
            try:
                sizes.add((int(header.get("NAXIS1", 0)),
                           int(header.get("NAXIS2", 0))))
            except (ValueError, TypeError):
                continue
            if len(sizes) > 1:
                break                   # already answered
        return sizes

    def _check_framing(self, filt: str, process_dir: str, seq: str) -> None:
        """Did ``-framing=min`` really put the frames on one canvas?

        It does on the star-registration path.  On the ASTROMETRIC one
        (`seqplatesolve` + `seqapplyreg`, i.e. "Register by plate
        solving") Siril accepts the argument, raises nothing, and exports
        frames of differing sizes anyway; `stack` then says so in its own
        log -- "The sequence has different image sizes and registration
        data. Forcing to maximize framing" -- and the master comes out
        LARGER than any sub.  That is the union, not the intersection:
        exactly the ragged, partly-exposed border `-framing=min` exists
        to remove.  Measured on one NGC 6946 run: 3008x3008 subs,
        registered frames from 3007x3008 to 3013x3014, master 3060x3128.

        Nothing raised, so `_note_reg_degraded` never fired and the report
        went on promising a crop that had not happened.  The frames are
        therefore asked directly, and a channel that did not get its crop
        says so -- in the log and in the report.

        A filter already recorded as degraded is left alone: its cause is
        the refusal, which is the more specific story and already told.
        """
        if filt in self._reg_degraded:
            return
        sizes = self._reg_frame_sizes(process_dir, seq)
        if len(sizes) < 2:
            return                      # one size, or nothing readable
        shown = ", ".join(f"{w}\u00d7{h}" for w, h in sorted(sizes))
        self._reg_degraded[filt] = ["-framing=min"]
        self._reg_degraded_why[filt] = (
            "Siril accepted the argument, raised nothing, and exported "
            f"frames of different sizes anyway ({shown}…), so `stack` "
            "fell back to maximising the framing")
        self._emit(
            f"  {filt}: -framing=min did not apply — the registered frames "
            f"came back in different sizes ({shown}…), so `stack` will "
            "maximise the framing and the master keeps the ragged, "
            "partly-exposed edges the crop exists to remove.  This is the "
            "plate-solve registration path; star alignment ('Register by "
            "plate solving' off) does apply the crop.", LogColor.SALMON)

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
                           f"-pixfrac={DRIZZLE_PIXFRAC:g}",
                           "-kernel=square"]
        n_in = self._current_n_frames
        if drizzle and drizzle > 1 and n_in < DRIZZLE_MIN_FRAMES:
            # The old wording blamed patchy coverage, which cannot
            # happen at pixfrac 1.0 -- every output pixel is covered by
            # every frame.  What is actually missing on a short run is
            # sub-pixel sampling: without it the finer grid carries no
            # information the plain stack does not already have.
            self._emit(
                f"  Drizzle {drizzle}x on only {n_in} frame(s): recovering "
                "detail on a finer grid needs many *dithered* subs to "
                f"sample between the pixels — roughly "
                f"{DRIZZLE_MIN_FRAMES}+. Below that you get "
                f"{drizzle}x the pixels and correlated neighbours, with "
                "little real resolution for them — consider turning it "
                "off.", LogColor.SALMON)
            self._drizzle_warned = True
        qfilters, qskipped, _share = self._quality_filter_plan(n_in)
        for flag, value, why in qskipped:
            # A filter the user ticked that never reaches Siril.  Without
            # this it simply vanished: the run kept every frame and said
            # nothing about the cut that was asked for.
            self._emit(
                f"  {flag}={value} was NOT applied — {why}. The frames it "
                "would have removed are all still in the stack.",
                LogColor.SALMON)
        if qfilters:
            apply_args += qfilters
            self._emit("  Quality filters: " + " ".join(qfilters),
                       LogColor.BLUE)
            # Dropping frames always costs SNR; say so when it is a lot.
            # The PESSIMISTIC count, on purpose: survivors pass every
            # filter, so the optimistic bound understated both the loss
            # and the noise and the note never fired (see
            # `_projected_frame_count`).
            n_eff = self._projected_frame_count(n_in)
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
        actually integrated: filtering 33 frames down to the best 90% leaves
        29, which wants Winsorized sigma, not the GESDT that 33 frames would
        suggest.

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
        """Integrate `seq`.  `n_frames` is the count that will REALLY be
        integrated -- measured from the registered sequence where that is
        possible, estimated only when it is not.  Applying the quality
        filters' share here as well would count them twice."""
        rej_tokens, rej_label = _rejection_args(
            n_frames, self._opts.get("rejection", True))

        def _tail() -> list:
            """Everything after the rejection tokens (identical on retry)."""
            args = ["-norm=addscale"]
            if self._opts.get("output_norm", True):
                args += ["-output_norm"]
            # Frame weighting lifts the better subs -- only meaningful once
            # there are a few frames left to weight.
            if self._opts.get("weighting", True) and n_frames >= 3:
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
        self._emit(f"  Rejection: {rej_label} (n={n_frames}"
                   + (", measured" if self._measured.get(filt) else "")
                   + ")", LogColor.BLUE)
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
        Either way the rejection algorithm comes from `_rejection_args`,
        the same frame-count bands the light stacks use.
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
        self._clear_stale_dir(work, f"{kind} calibration")
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
            self._note_command(
                f"{staged} {kind} frame(s) staged into "
                f"{self._here(stage)} by the script — `link` below reads "
                "what this step put there")
            self._cmd("cd", f'"{stage}"')
            self._cmd("link", kind, "-out=../process")
            self._cmd("cd", "../process")
            seq = kind
            if kind in (KIND_FLAT,):
                # Flats must be offset-corrected before normalising, else the
                # division carries the sensor pedestal into the lights.
                if bias_master:
                    self._cmd("calibrate", kind,
                              f'"-bias={bias_master}"')
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
            # The rejection algorithm follows the SAME frame-count bands as
            # the light stacks (`_rejection_args`).  This used to send a
            # bare `rej 3 3`, and a bare `rej` is Siril's default --
            # winsorized ("If omitted, the default Winsorized is used").
            # That is the band meant for 11-30 frames, and it was applied
            # to both ends of the range: a per-night master flat of five
            # frames, where winsorizing estimates sigma from five points
            # and replaces outliers with their neighbours, and a library
            # dark of four hundred, where a linear fit models the trend
            # across the stack that winsorizing cannot see.
            #
            # Rejection is always ON here whatever the light stacks were
            # told.  The option in front of the user is about integrating
            # HIS frames; a cosmic ray left in a master flat reaches every
            # light that master calibrates, which is a different trade.
            rej_tokens, rej_label = _rejection_args(staged, True)
            tail = [norm, "-out=" + out_name]
            try:
                self._cmd(*(["stack", seq] + rej_tokens + tail))
            except (CommandError, DataError, SirilError) as exc:
                # Same reasoning as `_stack`: only GESDT is new enough for
                # an older build to refuse the token outright, and only
                # that case may retry with another algorithm.
                fallback = _rejection_fallback(rej_tokens)
                if fallback is None:
                    raise
                fb_tokens, rej_label = fallback
                self._emit(
                    f"    rejection '{rej_tokens[1]}' was refused ({exc}); "
                    f"retrying with {rej_label}.", LogColor.SALMON)
                self._cmd(*(["stack", seq] + fb_tokens + tail))
            produced = os.path.join(work, "process", out_name + self._ext)
            if not os.path.exists(produced):
                self._emit(f"  {kind}: stacking produced no master.",
                           LogColor.RED)
                return None
            shutil.copy2(produced, dest)
            self._emit(f"  Built master {kind} from {staged} frames "
                       f"({rej_label}) -> {os.path.basename(dest)}",
                       LogColor.GREEN)
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
        self._masters = {KIND_BIAS: None, KIND_DARK: {}, KIND_FLAT: {}}
        # The two kinds are switched independently: flats and darks fail
        # for unrelated reasons, and a session with good flats and a
        # library of darks that fit nothing (or the reverse) used to be an
        # all-or-nothing choice.  A master that will not be applied is not
        # stacked either -- the cost of one is minutes and hundreds of
        # reads, and it is the whole point of switching it off.
        use_flats = self._opts.get("use_flats", True)
        use_darks = self._opts.get("use_darks", True)
        if not use_flats:
            self._emit("  Flats and dark-flats are switched off — no flat "
                       "master is stacked, and the lights keep their "
                       "vignetting.", LogColor.SALMON)
        if not use_darks:
            self._emit("  Darks and bias are switched off — no dark master "
                       "is stacked, and dark current and hot pixels stay in "
                       "the lights.", LogColor.SALMON)

        # 1) The bias first -- it is the last resort for every filter's
        #    flats, so it has to exist before the flat loop.  Dark-flats
        #    are NOT built here: `_flat_offset_for` picks and stacks the
        #    right one per filter, because the flat exposure differs per
        #    filter as soon as a panel sets it automatically.
        #
        #    It serves two roles, and only one of them is "darks and bias":
        #    reaching the LIGHTS where no dark does, which `_calib_args`
        #    gates.  As the flats' own offset it belongs to the flats, so
        #    switching the darks off must not quietly downgrade every flat
        #    to a synthetic offset.  Hence either switch can call for it.
        groups = (c.get(KIND_BIAS) or {}) if (use_darks or use_flats) else {}
        if groups and not use_darks:
            self._emit("  bias: stacked as the flats' offset only — with "
                       "darks and bias off it does not reach the lights.",
                       LogColor.BLUE)
        if groups:
            key = sorted(groups, key=_sig_sort_key)[0]
            if len(groups) > 1:
                self._emit(
                    f"  bias: {len(groups)} sets found, using the first.",
                    LogColor.SALMON)
            grp = groups[key]
            self._masters[KIND_BIAS] = self._stack_calib_group(
                KIND_BIAS, grp, self._master_name(KIND_BIAS, grp["info"]))

        # 2) The master flats.  With "Match flats to the same night" on,
        #    every night that has BOTH flats and lights gets its OWN master
        #    and only that night's lights are calibrated with it.  Off, one
        #    pooled master per filter covers the whole run.
        by_date = self._opts.get("flats_by_date", False)
        for filt, grp in ((c.get(KIND_FLAT) or {}) if use_flats else {}).items():
            if filt not in self._groups:
                # A flat set for a filter this run has no lights for.
                # Stacking it costs the same as a useful one and produces
                # a master nothing will open.
                self._emit(
                    f"  flat {filt}: no lights use this filter — not "
                    "stacked.", LogColor.BLUE)
                continue
            lit = set((self._groups.get(filt) or {}).get("dates") or [])
            per_night = (self._flats_per_night(grp, lit, self._nights)
                         if by_date else {})
            self._check_flat_consistency(filt, grp["files"], bool(per_night))
            # Per filter, because the panel gives each filter its own flat
            # exposure and the offset has to match THAT one.  The offset is
            # a library set, so it is the same for every night.
            offset = self._flat_offset_for(filt, grp, c)

            built: dict = {}
            for night in sorted(per_night):
                m = self._stack_calib_group(
                    KIND_FLAT, dict(grp, files=per_night[night]),
                    self._master_name(KIND_FLAT, grp["info"], filt, night),
                    offset)
                if m:
                    built[night] = m
            if built:
                self._flat_nights[filt] = built
                self._emit(
                    f"  {filt}: {len(built)} master flat(s), one per night "
                    "— " + ", ".join(f"{n} x{len(per_night[n])}"
                                     for n in sorted(built))
                    + ".", LogColor.GREEN)
                # Splitting trades flat NOISE for flat ACCURACY: a pooled
                # master averages every night's frames, a per-night one
                # only that night's.  Worth it when the train moved,
                # wasteful when it did not -- and the user can only weigh
                # that if the thin sets are named.
                thin = sorted(n for n in built
                              if len(per_night[n]) < FLAT_THIN_SET)
                if thin:
                    few = ", ".join(f"{n} ({len(per_night[n])})"
                                    for n in thin)
                    self._emit(
                        f"  {filt}: only {few}"
                        f" — under {FLAT_THIN_SET} flats a per-night master "
                        "carries visibly more noise than a pooled one. Worth "
                        "it when the optical train really moved; otherwise "
                        "pooling is the better trade.", LogColor.SALMON)

            # The pooled master is built even when every night has its own.
            # It is the fallback on two paths that are reached at a point
            # where stacking one is no longer safe: a light night whose
            # flats are missing, and a per-part calibration that fails and
            # drops back to a single pass.  One extra stack of a few dozen
            # flats is cheap; discovering mid-run that the fallback does
            # not exist means calibrating with no flat at all.
            uncovered = lit - set(built)
            use = dict(grp)
            # A restricted pool must not share a filename with the full
            # one -- the cache is keyed by name, and would hand back
            # whichever was stacked first.
            night_tag = ""
            if by_date and lit:
                kept = [p for p in grp["files"]
                        if _night_of(p, self._nights) in lit]
                dropped = len(grp["files"]) - len(kept)
                if kept and dropped:
                    use = dict(grp, files=kept)
                    night_tag = "-".join(sorted(lit))
                    self._emit(
                        f"  {filt}: using {len(kept)} flat(s) from the "
                        f"matching night(s); {dropped} from other dates "
                        "ignored.", LogColor.BLUE)
                elif not kept:
                    self._emit(
                        f"  {filt}: no flats from the same night — "
                        "falling back to all available flats.",
                        LogColor.SALMON)
            if built and uncovered:
                self._emit(
                    f"  {filt}: no flats for {', '.join(sorted(uncovered))} "
                    "— those night(s) fall back to a master pooled from the "
                    "others.", LogColor.SALMON)
            m = self._stack_calib_group(
                KIND_FLAT, use,
                self._master_name(KIND_FLAT, grp["info"], filt, night_tag),
                offset)
            if m:
                self._masters[KIND_FLAT][filt] = m

        # 3) One master dark per signature.  Two signatures that render to
        #    the same filename would share a cache entry, so the collision is
        #    broken deterministically (sorted order) instead of silently.
        claimed: dict = {}
        darks = (c.get(KIND_DARK) or {}) if use_darks else {}
        wanted = self._darks_in_demand(darks)
        for sig in sorted(darks, key=_sig_sort_key):
            if sig not in wanted:
                continue
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

    def _closest_dark(self, light_info: dict, filt: str):
        """The nearest usable dark when none matches exactly.

        Refusing every dark whose exposure is not identical leaves the
        lights uncalibrated, which is worse than a small mismatch: the
        thermal signal scales with exposure, so a 290 s dark on 300 s
        lights removes most of what a 300 s one would.  A 60 s dark on
        300 s lights does not -- which is why the tolerance is a FRACTION
        of the target rather than a fixed number of seconds.

        Everything except exposure still has to agree: camera, gain,
        binning, size, temperature.  This loosens only the one dimension
        that degrades gracefully, and always says so, because a silently
        substituted dark is exactly what this script exists to surface.

        The looseness is NOT symmetric.  |delta| alone treats a 630 s dark
        on 600 s lights like a 570 s one, and they are not alike: the
        longer dark over-subtracts into the clamp at zero and takes faint
        signal with it, while the shorter one leaves a pedestal the
        background extraction removes anyway.  A shorter dark therefore
        wins ties, and a longer one has to be closer to qualify at all
        (DARK_OVERSHOOT_TOLERANCE against DARK_EXPOSURE_TOLERANCE).
        """
        want = light_info.get("exp_s")
        if not want:
            return None
        want_f = float(want)
        best = best_key = best_exp = None
        for _sig, (path, info) in (self._masters.get(KIND_DARK) or {}).items():
            have = info.get("exp_s")
            if not have:
                continue
            probe = dict(info, exp_s=want)     # judge everything BUT exposure
            if not _signature_matches(probe, light_info):
                continue
            have_f = float(have)
            share = abs(have_f - want_f) / want_f
            longer = have_f > want_f
            if share > (DARK_OVERSHOOT_TOLERANCE if longer
                        else DARK_EXPOSURE_TOLERANCE):
                continue
            # Sorted on (distance, is-longer): at equal distance the
            # shorter dark wins, because under-subtraction is the
            # recoverable half of the mistake.
            key = (share, 1 if longer else 0)
            if best_key is None or key < best_key:
                best, best_key, best_exp = path, key, have_f
        if best is None:
            # Report against the LOOSER bound: naming the tighter one
            # would read as the rule for every dark, and it is not.
            self._emit(
                f"  {filt}: no dark within "
                f"{DARK_EXPOSURE_TOLERANCE * 100:.0f}% of "
                f"{want_f:g}s lights (a LONGER dark has to be within "
                f"{DARK_OVERSHOOT_TOLERANCE * 100:.0f}%, because it "
                "over-subtracts into the clamp at zero) — continuing "
                "without one.", LogColor.SALMON)
            return None
        share = best_key[0]
        if share <= 0.0:
            return best
        self._emit(
            f"  {filt}: no dark matches {want_f:g}s exactly; using the "
            f"closest at {best_exp:g}s ({share * 100:.0f}% "
            + ("longer — it slightly over-subtracts"
               if best_exp > want_f
               else "shorter — it slightly under-subtracts")
            + ").  Everything else — camera, gain, binning, size, "
              "temperature — does match.", LogColor.SALMON)
        return best

    @staticmethod
    def _flats_per_night(grp: dict, lit: set, nights: dict | None = None
                         ) -> dict:
        """``{night: flat files}`` for the nights worth keeping apart.

        A night qualifies only when it holds flats AND lights of this
        filter.  Flats from a night this filter never imaged would build
        a master nothing opens, and a light night without flats has to
        fall back to a pooled master whatever we do here.

        Returns ``{}`` when fewer than two nights qualify: with one, the
        per-night master and the pooled one would hold the same frames,
        so splitting the run would buy nothing and cost a merge.

        ``nights`` is discovery's path -> observing-night map (see
        `_night_of`).  Both this and the caller's ``lit`` set must come
        from it, or a session that ran past midnight is split by its date
        folders and half its lights are paired with the wrong flats --
        which is exactly what happened while `_night_key` was computed
        and never read.
        """
        by_night: dict = {}
        for path in grp.get("files") or []:
            night = _night_of(path, nights)
            if night and night in lit:
                by_night.setdefault(night, []).append(path)
        return by_night if len(by_night) > 1 else {}

    def _check_flat_consistency(self, filt: str, files: list,
                                handled: bool = False) -> None:
        """Warn when the flats of one filter come from different optics.

        Pooling flats across nights is right for a rig that never moves
        and wrong the moment the train is touched -- and nothing in the
        headers says which happened.  Dividing one night's flat by
        another's does say it: a matching pair gives a uniform result, a
        mismatched one shows the vignetting or dust that moved.

        Every frame of a night is used, not one of them: a single sub
        carries enough shot noise to swamp the difference being looked
        for (see `FLAT_MATCH_GOOD`).  Silent when there is only one night
        or when the frames cannot be read.

        A measurement without its own error bar cannot be judged, so the
        noise floor is measured too, by splitting the reference night in
        half and comparing it with itself -- two halves of one night have
        no shape difference by construction, so whatever that comparison
        returns is noise.  Each half averages fewer frames than the real
        comparison does, so the raw half spread is scaled onto the
        night-vs-night frame counts (see `_floor_rescale`) -- unscaled it
        overstated the true noise by a measured sqrt(2) at equal counts,
        and "no shape difference detectable" then covered real
        differences as large as the noise itself.

        ``handled`` says the nights are already being calibrated apart.
        The measurement still runs and is still reported -- it is the
        evidence that the option is earning its keep -- but it stops
        being a warning, and it must not advise switching on something
        that is on.
        """
        by_night: dict = {}
        for path in files:
            by_night.setdefault(
                _night_of(path, self._nights) or "?", []).append(path)
        if len(by_night) < 2:
            return
        # "?" (undated) sorts AFTER every digit, so a plain sort would
        # make an undated flat the ruler -- and the message would name
        # "?" as a night.  Dated nights rule; "?" only ever compares.
        dated = sorted(n for n in by_night if n != "?")
        if not dated:
            return                      # nothing to anchor a comparison on
        ruler = dated[-1]               # the most recent dated night
        nights = [n for n in sorted(by_night) if n != ruler] + [ruler]
        base = by_night[ruler]
        # Each night is read and averaged ONCE.  A helper taking two file
        # lists would re-read the reference night for every comparison, and
        # these are the largest files the run touches.
        base_stats: dict = {}
        base_shape = _flat_shape(base, stats=base_stats)
        skipped_total = base_stats.get("skipped", 0)
        worst = worst_night = None
        worst_used = 0
        for night in nights[:-1]:
            night_stats: dict = {}
            spread = _flat_ratio_spread(
                base_shape, _flat_shape(by_night[night], stats=night_stats))
            skipped_total += night_stats.get("skipped", 0)
            if spread is None:
                continue
            if worst is None or spread > worst:
                worst, worst_night = spread, night
                worst_used = night_stats.get("used", 0)
        if skipped_total:
            # A map built from fewer frames than were offered must not
            # pose as the full sample -- silently thinning it was how a
            # mixed-binning night once compared as if it were clean.
            self._emit(
                f"  flat {filt}: {skipped_total} frame(s) of a different "
                "image size were left out of the night comparison — mixed "
                "binning or a second sensor inside this filter's flats.",
                LogColor.SALMON)
        if worst is None:
            return
        # The reference night against itself: the noise floor of the
        # number just measured, in the same units and the same pipeline --
        # then scaled onto the frame counts of the real comparison, since
        # each half averages fewer frames than the full maps do.
        floor = None
        if len(base) > 1:
            # INTERLEAVED, not the first half against the second.  The
            # file list is sorted by path and a flat run is named by
            # timestamp, so contiguous halves are separated in TIME: any
            # drift across the run -- twilight fading, the panel warming,
            # dew -- landed in the "noise floor" as if it were noise.
            # That inflates the floor, and an inflated error bar hides
            # exactly the night-to-night difference this measurement
            # exists to find.  Alternate frames share the drift instead
            # of straddling it.
            half_a, half_b = {}, {}
            floor = _flat_ratio_spread(
                _flat_shape(base[0::2], stats=half_a),
                _flat_shape(base[1::2], stats=half_b))
            if floor is not None:
                floor *= _floor_rescale(
                    half_a.get("used", len(base[0::2])) or 1,
                    half_b.get("used", len(base[1::2])) or 1,
                    base_stats.get("used", len(base)) or 1,
                    worst_used or 1)
        bar = (f" (noise floor {floor * 100:.3f}%)"
               if floor is not None else "")
        # Agreement, in two grades: inside the error bar, where naming a
        # figure would be naming noise, and merely small.  What the split
        # option changes here is only the closing clause -- it must not turn
        # agreement into a difference it is then credited with preventing,
        # which is the whole reason this measurement was rebuilt.
        if (floor is not None and worst <= floor) or worst <= FLAT_MATCH_GOOD:
            if floor is not None and worst <= floor:
                found = (f"agree to within the measurement limit "
                         f"({worst * 100:.3f}% against a noise floor of "
                         f"{floor * 100:.3f}%), with no shape difference "
                         "detectable")
            else:
                found = f"agree to {worst * 100:.3f}%{bar}"
            self._emit(
                f"  flat {filt}: {len(nights)} nights {found}"
                + (" — keeping them apart costs an extra stack and changes "
                   "nothing here, but it stays right if the train moves."
                   if handled else ", so pooling them is right."),
                LogColor.BLUE)
            return
        if handled:
            # Kept apart already: the number is the reason the split is
            # worth its extra stack, not something to act on.
            self._emit(
                f"  flat {filt}: {len(nights)} nights differ by up to "
                f"{worst * 100:.3f}%{bar} ({worst_night} vs {nights[-1]}) "
                "— each night is calibrated with its own flats, so the "
                "difference never reaches the lights.", LogColor.GREEN)
            return
        level = "usable" if worst <= FLAT_MATCH_LIMIT else "a real mismatch"
        self._flat_warn[filt] = (worst, worst_night, nights[-1], floor)
        # The advice has to fit what is actually switched on.  Telling a
        # user to enable an option they enabled is how a report loses its
        # authority -- and here it would be enabled and simply unable to
        # help, which is a different problem with a different fix.
        if self._opts.get("flats_by_date", False):
            fix = ("Only one of the imaged nights has flats of its own, so "
                   "they cannot be kept apart — shoot flats for each night, "
                   "or expect this residual.")
        else:
            fix = ("Switch on 'Match flats to the same night' to calibrate "
                   "each night with its own flats.")
        self._emit(
            f"  flat {filt}: the set from {worst_night} differs from "
            f"{nights[-1]} by {worst * 100:.3f}%{bar} — {level}. "
            + ("Above " if worst > FLAT_MATCH_LIMIT else "Under ")
            + f"{FLAT_MATCH_LIMIT * 100:.1f}% usually means the optical "
            "train was touched between the nights, and one pooled master "
            "then corrects neither. " + fix,
            LogColor.SALMON if worst > FLAT_MATCH_LIMIT else LogColor.BLUE)

    def _offset_fits(self, grp: dict, flat_info: dict, filt: str,
                     what: str) -> bool:
        """Is this offset set shot with the same camera state as the flats?

        Matching on exposure alone is not enough.  An offset for flats is
        a dark for the flats: it has to agree in CAMERA, GAIN, BINNING,
        SIZE and TEMPERATURE, exactly like any other dark -- a panel that
        sets a different gain per filter would otherwise be offset with a
        set shot at another gain, and the pedestal it removes would be the
        wrong one.

        Only the exposure is judged separately, by the caller, because
        that one carries a deliberate tolerance.  The probe overrides it
        so `_signature_matches` does not weigh it twice.
        """
        probe = dict(grp.get("info") or {}, exp_s=flat_info.get("exp_s"))
        if _signature_matches(probe, flat_info):
            return True
        self._emit(
            f"  {filt}: a {what} set matches the flat exposure but not the "
            "camera state (gain, binning, size or temperature) — not used "
            "as their offset.", LogColor.SALMON)
        return False

    def _flat_offset_for(self, filt: str, flat_grp: dict, c: dict) -> str:
        """The offset master to calibrate ONE filter's flats against.

        Chosen per filter, because an automatic flat panel adjusts the
        exposure per filter to hit the same level: a narrowband flat runs
        seconds where a Luminance flat runs a fraction of one.  A single
        offset for all of them is right only by accident, and the previous
        code gave up entirely ("flats of mixed exposure: no single right
        answer") the moment two filters differed -- silently falling back
        to the synthetic offset for every one of them.

        Order, best first:
          1. a real DARK-FLAT set for this filter,
          2. a DARK set at this filter's flat exposure (within
             DARKFLAT_EXPOSURE_TOLERANCE) -- a dark at the flat exposure
             IS a dark-flat, whatever IMAGETYP calls it, and it carries
             that exposure's dark current and hot pixels, which a bias
             does not,
          3. the master bias,
          4. "" -- the caller then uses Siril's synthetic offset.

        Masters are cached per source group, so two filters sharing an
        exposure stack it once.
        """
        want = float((flat_grp.get("info") or {}).get("exp_s") or 0.0)

        # 1) a dark-flat shot for this very filter
        info = flat_grp.get("info") or {}
        df = (c.get(KIND_DARKFLAT) or {}).get(filt)
        if df and not self._offset_fits(df, info, filt, "dark-flat"):
            df = None
        if df:
            key = (KIND_DARKFLAT, filt)
            if key not in self._offset_cache:
                self._offset_cache[key] = self._stack_calib_group(
                    KIND_DARKFLAT, df,
                    self._master_name(KIND_DARKFLAT, df["info"], filt)) or ""
            if self._offset_cache[key]:
                self._flat_offset_note[filt] = (
                    f"dark-flat set for {filt}")
                return self._offset_cache[key]

        # 2) a dark at this filter's flat exposure
        if want > 0:
            best = best_delta = None
            for sig, grp in (c.get(KIND_DARK) or {}).items():
                have = (grp.get("info") or {}).get("exp_s")
                if not have:
                    continue
                delta = abs(float(have) - want)
                if delta / want > DARKFLAT_EXPOSURE_TOLERANCE:
                    continue
                if not self._offset_fits(grp, info, filt, f"{have:g}s dark"):
                    continue
                if best_delta is None or delta < best_delta:
                    best, best_delta = sig, delta
            if best is not None:
                key = (KIND_DARK, best)
                grp = c[KIND_DARK][best]
                if key not in self._offset_cache:
                    self._offset_cache[key] = self._stack_calib_group(
                        KIND_DARKFLAT, grp,
                        self._master_name(KIND_DARKFLAT, grp["info"])) or ""
                if self._offset_cache[key]:
                    got = float(grp["info"]["exp_s"])
                    self._flat_offset_note[filt] = (
                        f"{got:g}s dark set (flats are {want:g}s)")
                    self._emit(
                        f"  {filt}: flats at {want:g}s are offset-corrected "
                        f"with a {got:g}s dark set — a dark at the flat "
                        "exposure IS a dark-flat, whatever IMAGETYP calls "
                        "it.", LogColor.BLUE)
                    return self._offset_cache[key]

        # 3) the bias
        bias = self._masters.get(KIND_BIAS) or ""
        if bias:
            self._flat_offset_note[filt] = "master bias"
            if want > 0:
                self._emit(
                    f"  {filt}: no dark-flat and no dark near {want:g}s — "
                    "using the master bias as the flats' offset.",
                    LogColor.BLUE)
            return bias

        self._flat_offset_note[filt] = "synthetic offset"
        return ""

    def _darks_in_demand(self, groups: dict) -> set:
        """Dark signatures some part of this run can actually use.

        A library is meant to grow: darks for five exposures at three
        setpoints are fifteen signatures, and stacking all of them to use
        one costs minutes and reads hundreds of frames for masters nothing
        opens.  Only the ones a filter's lights could match are built --
        judged with the SAME rule that will later pick one, so a signature
        cannot be skipped here and then wanted there.

        The exposure test is deliberately the loose one: `_closest_dark`
        may reach for a neighbouring exposure, so a signature within that
        tolerance has to exist as a master by then.

        Returns every signature when nothing can be judged (no lights
        analysed yet), because building too much is a cost and building
        too little is a defect.
        """
        infos = [g.get("info") or {} for g in self._groups.values()]
        infos = [i for i in infos if i]
        if not infos:
            return set(groups)
        wanted = set()
        for sig, grp in groups.items():
            di = grp.get("info") or {}
            for li in infos:
                probe = dict(di, exp_s=li.get("exp_s"))
                if not _signature_matches(probe, li):
                    continue        # camera / gain / size / temp rule it out
                want, have = li.get("exp_s"), di.get("exp_s")
                if not want or not have:
                    wanted.add(sig)
                    break
                share = abs(float(have) - float(want)) / float(want)
                if share <= DARK_EXPOSURE_TOLERANCE:
                    wanted.add(sig)
                    break
        # A set can be unwanted HERE and still have been stacked.  A dark
        # at a flat's exposure is consumed as that filter's dark-flat
        # (`_flat_offset`, case 2), and flats are built before darks, so its
        # master already exists and sits in `_offset_cache`.  Counting it as
        # "not stacked" would deny a master the log printed moments earlier
        # -- 160 frames the run plainly used.  It stays out of `wanted`
        # (stacking it again as a dark master would be the redundant one)
        # and out of the count; why it is not in the dark list was already
        # said, per filter, where the choice was made.
        as_offset = [sig for sig in groups
                     if sig not in wanted
                     and self._offset_cache.get((KIND_DARK, sig))]
        skipped = len(groups) - len(wanted) - len(as_offset)
        if skipped:
            self._emit(
                f"  {skipped} dark set(s) do not match any filter's lights "
                "(exposure, gain, temperature, camera or size) — not "
                "stacked.", LogColor.BLUE)
        return wanted

    def _flat_for(self, filt: str, night: str = "") -> str:
        """The master flat for one filter, for one night's frames.

        With the nights kept apart this returns that night's own master.
        A night whose flats are missing falls back to the pooled one --
        stated in the log, because a silent fallback would make a run
        look per-night when half of it was not.
        """
        nights = self._flat_nights.get(filt) or {}
        if night and nights:
            own = nights.get(night)
            if own:
                self._night_notes.setdefault(filt, []).append(
                    (night, os.path.basename(own)))
                return own
            self._emit(
                f"  {filt} {night}: no flats from this night — using the "
                "pooled master.", LogColor.SALMON)
        return (self._masters.get(KIND_FLAT) or {}).get(filt) or ""

    def _calibrate_args(self, filt: str, light_info: dict, n_frames: int = 0,
                        warn_mixed: bool = True, night: str = "") -> list:
        """Build the `calibrate` arguments for one filter, or [] for none.

        ``warn_mixed`` is False when the caller has already split the
        filter by exposure (`_calib_split`): the warning about a dark
        that fits only some of the frames would then be describing a
        problem that was just solved.

        ``night`` selects that night's master flat when the flats are
        being kept per night; empty means the pooled one.
        """
        if not self._opts.get("calibrate", True) or not self._masters:
            return []
        args: list = []
        used: list = []

        dark = None
        for _sig, (path, info) in (self._masters.get(KIND_DARK) or {}).items():
            if _signature_matches(info, light_info):
                dark = path
                break
        if dark is None:
            dark = self._closest_dark(light_info, filt)
        if dark:
            args.append(f'"-dark={dark}"')
            used.append(f"dark={os.path.basename(dark)}")
            # The match was made against ONE representative light.  If the
            # filter mixes exposures, the dark is right for only some of
            # them -- say so rather than let it pass unnoticed.
            exps = (self._groups.get(filt) or {}).get("exps") or []
            if warn_mixed and len(exps) > 1:
                self._emit(
                    f"  {filt}: frames use {len(exps)} different exposures "
                    f"({', '.join(f'{e:g}s' for e in exps)}); the dark "
                    f"matches {light_info.get('exp') or 'the first frame'} "
                    "only. Stack the exposures separately for a clean "
                    "result.", LogColor.SALMON)
            if self._opts.get("cosmetic", True):
                cc, cc_label = _cosmetic_args(n_frames)
                args += cc
                if (cc_label != _cosmetic_args(0)[1]
                        and self._cc_said.get(filt) != cc_label):
                    self._cc_said[filt] = cc_label
                    # Said out loud: the run is about to correct this
                    # filter harder than the others, and the reason is the
                    # frame count, which is visible two lines above.  Once
                    # per filter -- a split calls this per part, and OIII
                    # said the same sentence three times.
                    self._emit(
                        f"  {filt}: {n_frames} frame(s) — hot-pixel "
                        f"threshold tightened to {cc_label}. Rejection "
                        "needs dithered frames to take a hot pixel out, "
                        "and this few cannot.", LogColor.BLUE)
                self._cc_used[filt] = cc_label
        elif self._masters.get(KIND_DARK):
            self._emit(
                f"  {filt}: no dark matches these lights (exposure, gain, "
                "temperature, binning or image size differ) — continuing "
                "without one.", LogColor.SALMON)

        flat = self._flat_for(filt, night)
        if flat:
            args.append(f'"-flat={flat}"')
            used.append(f"flat={os.path.basename(flat)}")

        # Bias goes to the lights ONLY when no dark is used: a master dark
        # already contains the offset, so subtracting bias as well would
        # remove it twice.  Lc = (L - D) / (F - O).
        if (not dark and self._masters.get(KIND_BIAS)
                and self._opts.get("use_darks", True)):
            bias = self._masters[KIND_BIAS]
            args.append(f'"-bias={bias}"')
            used.append(f"bias={os.path.basename(bias)}")

        if used:
            self._calib_notes[filt] = ", ".join(used)
        return args

    def _find_fullframe(self, mdir: str, filt: str):
        """An existing full-frame master for this filter, or None.

        The name carries the recipe (frames, exposure, gain, temperature),
        so it changes whenever the run does -- matching it exactly would
        make reuse depend on stacking the very same frames again.  The
        stable part is the ``<TARGET>_<FILTER>_`` prefix; the trailing
        underscore is what keeps ``R`` from matching ``RED``.  Among
        several the newest wins, and the bare
        ``<TARGET>_<FILTER>_fullframe`` written by earlier versions still
        matches the same rule.
        """
        pre = f"{_safe(self._target)}_{self._tok(filt)}_"
        tail = f"_fullframe{self._ext}"
        try:
            hits = [os.path.join(mdir, f) for f in os.listdir(mdir)
                    if f.startswith(pre) and f.lower().endswith(tail.lower())]
        except OSError as exc:
            _log_swallowed(exc)
            return None
        if not hits:
            return None
        return max(hits, key=lambda f: os.path.getmtime(f))

    def _master_stem(self, filt: str, n_stack: int) -> str:
        """``<TARGET>_<FILTER>_<recipe>_fullframe`` -- e.g.
        ``M16_HA_29x300s_G100_-10C_fullframe``.

        What a stack is worth depends on how it was made, and a bare
        ``M16_HA_fullframe`` hides every bit of that.  The frame count is
        the one that was actually integrated (after registration dropped
        what it could not align), so the name cannot promise more than the
        file contains.  A filter that mixes exposures gets a plain count
        instead of ``NxT``: no single exposure would be true for it.

        Missing header values are left out rather than guessed, so the
        name is always shorter than it is wrong.
        """
        grp = self._groups.get(filt) or {}
        info = grp.get("info") or {}
        exps = grp.get("exps") or []
        parts = [f"{_safe(self._target)}_{self._tok(filt)}"]
        if len(exps) == 1 and exps[0]:
            parts.append(f"{n_stack}x{float(exps[0]):g}s")
        else:
            parts.append(f"{n_stack}subs")
        gain = info.get("gain_v")
        if gain is not None:
            parts.append(f"G{float(gain):g}")
        temp = info.get("temp_v")
        if temp is not None:
            parts.append(f"{float(temp):.0f}C")
        parts.append("fullframe")
        return "_".join(parts)

    def _calib_split(self, filt: str) -> list:
        """``[(tag, exposure, night, files)]`` when a filter needs
        calibrating in parts, or ``[]`` when one pass over all its frames
        is right.

        Two masters bind a part of the frames rather than all of them,
        and each contributes one dimension:

        * the DARK is valid only for the exposure it was shot at -- the
          thermal signal it removes grew for exactly that long, so a
          filter holding 120 s and 300 s subs cannot take one dark;
        * the FLAT is valid only for the optical train it was shot
          through.  With the nights kept apart, each night's lights want
          that night's flats.

        The dimensions are independent, so the parts are their cross
        product, and a dimension with one value collapses out of it: no
        darks means the exposure never splits, one flat master means the
        night never does.  Each part is calibrated with its own masters
        and they are merged again before registration, so the channel
        still ends as ONE master -- splitting is a calibration concern,
        not a stacking one.
        """
        if not self._opts.get("calibrate", True):
            return []
        by_exp = (self._groups.get(filt) or {}).get("by_exp") or {}
        split_exp = bool(self._masters.get(KIND_DARK)) and len(by_exp) > 1
        split_night = len(self._flat_nights.get(filt) or {}) > 1
        if not split_exp and not split_night:
            return []

        base = ((self._groups.get(filt) or {}).get("info") or {}).get("exp_s")
        parts: dict = {}
        for exp, files in by_exp.items():
            for path in files:
                key = (exp if split_exp else base,
                       _night_of(path, self._nights) if split_night else "")
                parts.setdefault(key, []).append(path)
        # Siril cannot build a sequence from a single file, so a part of
        # one frame fails `calibrate` and takes the WHOLE split down with
        # it -- the run then falls back to one pooled pass, after having
        # already stacked a master flat per night that nothing now reads.
        # Seen on IC 1805: OIII arrived as 8 frames on one night and 1 on
        # the next, two per-night flats were built, and both were thrown
        # away by an error in the log that looks like a defect.
        #
        # The condition is knowable here, so it is decided here.  Refusing
        # the split costs the smaller night its own flat; attempting it
        # costs every night theirs, plus the error.
        thin = {k: len(v) for k, v in parts.items() if len(v) < 2}
        if thin:
            self._split_refused[filt] = sorted(
                (self._part_label(exp, night, split_exp, split_night), n)
                for (exp, night), n in thin.items())
            return []

        out = []
        for (exp, night), files in sorted(
                parts.items(), key=lambda kv: (kv[0][1], kv[0][0] or 0.0)):
            out.append((self._part_tag(exp, night, split_exp, split_night),
                        exp, night, files))
        return out

    @staticmethod
    def _part_tag(exp, night, split_exp: bool, split_night: bool) -> str:
        """Sequence-name token for one calibration part."""
        bits = []
        if split_exp:
            bits.append(_exp_tag(exp))
        if split_night:
            # A night that never made it into a flat master still gets its
            # own part -- it is calibrated with the pooled flat, and
            # keeping it separate is what lets the log say so.
            bits.append("n" + (_safe(night).replace("-", "") or "undated"))
        return "_".join(bits)

    @staticmethod
    def _part_label(exp, night, split_exp: bool, split_night: bool) -> str:
        """How that part reads in a message, rather than in a filename."""
        bits = []
        if split_exp and exp:
            bits.append(f"{float(exp):g}s")
        if split_night:
            bits.append(str(night) or "undated")
        return " ".join(bits) or "the group"

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
            self._clear_stale_dir(work, f"{filt} sequence")
            # A dark is only valid for the exposure it was shot at and a
            # flat only for the night it was shot on, so a filter that
            # mixes either is staged in parts and merged again after
            # calibration.
            splits = self._calib_split(filt)
            if filt in self._split_refused:
                # Discovery announced per-night calibration for this
                # filter.  It is not happening, and saying nothing would
                # leave that announcement standing.
                shown = ", ".join(
                    f"{lbl} ({n} frame{'' if n == 1 else 's'})"
                    for lbl, n in self._split_refused[filt])
                self._emit(
                    f"  {filt}: calibrating in parts was NOT attempted — "
                    f"{shown} cannot form a Siril sequence, and one "
                    "unusable part fails the whole split. All frames are "
                    "calibrated in one pass with the pooled master "
                    "instead.", LogColor.SALMON)
            staged: list = []
            n_linked = 0
            blank_mark = self._blank_skipped
            for tag, exp, night, sub in splits:
                d = os.path.join(work, f"lights_{tag}")
                k = self._link_frames(sub, d)
                if k:
                    staged.append((tag, exp, night, d, k))
                    n_linked += k
            if splits and len(staged) < 2:
                # Only one part survived staging (the rest were blank or
                # unreadable): there is nothing left to split, so take the
                # ordinary path -- and undo the blank tally, which the
                # single pass is about to count again.
                self._clear_stale_dir(work, f"{filt} sequence")
                self._blank_skipped = blank_mark
                staged = []
            if staged:
                self._emit(
                    f"  Staged {n_linked} frame(s) in "
                    f"{len(staged)} calibration group(s): "
                    + ", ".join(
                        f"{t} x{k}" for t, _e, _n, _d, k in staged),
                    LogColor.BLUE)
            else:
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
                # FITS (incl. Rice-compressed .fits.fz) -> link is instant;
                # anything else needs convert.  Discovery only ever yields
                # FITS_EXTS today, so the convert branch is dead in practice
                # -- it is kept deliberately, so that widening FITS_EXTS to a
                # raw format does not silently produce a broken `link`.
                conv = "link" if _is_fits_like(_fits_ext(files[0])) \
                    else "convert"

                seq = None
                if staged:
                    try:
                        seq = self._calibrate_in_parts(filt, staged, conv)
                    except (CommandError, DataError, SirilError) as exc:
                        # One pass with a dark that fits some of the frames
                        # is still better than no master at all -- but it is
                        # a step down, so it is said out loud.
                        self._emit(
                            f"  {filt}: calibrating per exposure failed "
                            f"({exc}); falling back to one pass over all "
                            "frames.", LogColor.SALMON)
                        staged = []
                        blank_mark = self._blank_skipped
                        n_linked = self._link_frames(files, lights_dir)
                        self._blank_skipped = blank_mark
                        if n_linked < 2:
                            # The "need at least 2" guard is above, and it
                            # passed on the count of the PARTS.  Re-staging
                            # can come back with fewer (a frame that went
                            # missing since, a symlink that could not be
                            # made), and running on into `link` would turn a
                            # clean skip into a Siril error nobody can read.
                            msg = (f"only {n_linked} usable frame(s) after "
                                   "falling back from per-part calibration; "
                                   "need at least 2 to register and stack.")
                            self._emit(f"  Skipping {filt}: {msg}",
                                       LogColor.SALMON)
                            errors[filt] = msg
                            continue
                if seq is None:
                    self._note_command(
                        f"{n_linked} {filt} light frame(s) staged into "
                        f"{self._here(lights_dir)} by the script")
                    self._cmd("cd", f'"{lights_dir}"')
                    self._cmd(conv, "lights", "-out=../process")
                    self._cmd("cd", "../process")

                    seq = "lights"
                    # Calibration comes first: everything downstream
                    # (background, registration, stacking) should work on
                    # corrected pixels.
                    cal_args = self._calibrate_args(
                        filt, self._groups[filt].get("info") or {},
                        n_frames=n_linked)
                    if cal_args:
                        self._emit("  Calibrating: calibrate lights "
                                   + " ".join(cal_args), LogColor.BLUE)
                        self._cmd("calibrate", seq, *cal_args)
                        previous = seq
                        seq = f"pp_{seq}"
                        # pp_ frames are complete files; nothing reads the
                        # staged originals or their sequence again.
                        self._drop_generation(
                            os.path.join(work, "process"), previous)
                        self._drop_staged(lights_dir)

                proc_dir = os.path.join(work, "process")
                if self._opts.get("bg_extract", False):
                    self._emit("  Extracting background gradient...",
                               LogColor.BLUE)
                    previous = seq
                    self._cmd("seqsubsky", seq, "1", "-samples=10")
                    seq = f"bkg_{seq}"
                    self._drop_generation(proc_dir, previous)

                self._current_n_frames = n_linked
                # Record what seqapplyreg is about to be told, before
                # registration can change the frame count under us.
                self._qf_decision[filt] = (
                    n_linked, bool(self._quality_filter_args(n_linked)))
                self._emit("  Registering frames...", LogColor.BLUE)
                previous = seq
                seq = self._register(seq, filt)
                if seq != previous:
                    # -2pass writes its data into the SAME sequence, so
                    # only a renaming step (seqapplyreg) leaves a
                    # predecessor behind to delete.
                    self._drop_generation(proc_dir, previous)
                    # And only now the parts the merge still pointed at:
                    # registration has written real frames of its own, so
                    # nothing references the symlinked originals any more.
                    self._drop_parts(filt)

                # Registration itself can drop frames -- a sub with no
                # detectable stars (clouds, a passing veil) simply fails to
                # match and Siril excludes it -- and so can the quality
                # filters, which run inside seqapplyreg.  Both land in the
                # same count.  Counting the files it really
                # exported is the only reliable number: everything after
                # this point (rejection tier, weighting, the report) must be
                # based on what is actually going into the stack, not on
                # what went in at the top.
                n_reg = self._count_seq_frames(
                    os.path.join(work, "process"), seq)
                # ...and, while those frames are there, whether the crop
                # that was asked for actually reached them.  Siril accepts
                # -framing=min on the astrometric path and ignores it, so
                # only the frames themselves can answer this.
                if self._opts.get("crop_edges", True):
                    self._check_framing(
                        filt, os.path.join(work, "process"), seq)
                if n_reg and n_reg < n_linked:
                    lost = n_linked - n_reg
                    # Which of the two causes it was decides the
                    # sentence.  Blaming cloud for a filter the user
                    # switched on describes a data problem where there is
                    # none -- and with the filters on that is the common
                    # case, so it is the one that has to be right.
                    _n, fired = self._qf_decision.get(
                        filt, (n_linked, False))
                    flags = (" ".join(self._quality_filter_args(n_linked))
                             if fired else "")
                    if flags:
                        self._emit(
                            f"  {lost} of {n_linked} frame(s) removed by "
                            f"the quality filters ({flags}) — {n_reg} will "
                            "be integrated. A frame that could not be "
                            "aligned would count here too.", LogColor.SALMON)
                    else:
                        self._emit(
                            f"  Registration dropped {lost} of {n_linked} "
                            f"frame(s) — {n_reg} will be integrated. Frames "
                            "without enough detectable stars (clouds, haze) "
                            "cannot be aligned.", LogColor.SALMON)
                # A channel can be short without having lost anything.
                # This check used to sit INSIDE the drop message above, so a
                # filter that STARTED below the floor was never warned while
                # one that fell to the same count was -- the same diagnosis
                # hanging off the wrong condition.  What matters is how many
                # frames go into the stack, not how it got to that number.
                # "left" is gone with the nesting: nothing need have been
                # lost for this to fire.
                # PERCENTILE_MAX_FRAMES, not MIN_STACK_FRAMES: the
                # sentence is about what rejection can still do, and that
                # is the percentile band, not the floor the quality
                # filters may not cross.  With `<` against the floor, a
                # channel of exactly four frames -- percentile clipping,
                # the weakest case there is -- said nothing at all.
                if n_reg and n_reg <= PERCENTILE_MAX_FRAMES:
                    self._emit(
                        f"  Only {n_reg} frame(s) for {filt}: too few for "
                        "outlier rejection to mean much. Treat this "
                        "channel as provisional.", LogColor.SALMON)
                # `n_reg` counts what seqapplyreg EXPORTED, which is
                # already after the quality filters -- they run there, not
                # at stack time.  Passing it through
                # _effective_frame_count would subtract the same
                # percentage a second time, choosing the rejection
                # algorithm for a population smaller than the one being
                # integrated.  The estimate is for the case where the
                # count could not be read at all.
                # The two fallbacks pull in OPPOSITE directions on
                # purpose.  `n_stack` picks the rejection algorithm, and
                # falling back to `n_linked` ignored the quality filters
                # altogether: 74 staged frames chose the algorithm for 74
                # where 57 were integrated, and the bands are close
                # together (31 separates winsorized from GESDT).  The
                # conservative error is to pick the gentler algorithm for
                # a smaller population, so this takes the pessimistic
                # estimate.  `effective` is quoted in the report as
                # "<=N used", where an upper bound is the honest
                # direction -- hence the optimistic one.
                n_stack = n_reg or self._projected_frame_count(n_linked)
                effective = n_reg or self._effective_frame_count(n_linked)
                self._measured[filt] = bool(n_reg)
                quality = self._seq_quality(
                    os.path.join(work, "process"), seq, filt, n_reg)
                if quality and quality.get("included"):
                    effective = quality["included"]
                    n_stack = effective
                    # Siril's own answer is a measurement even when the
                    # file count was not available to confirm it.
                    self._measured[filt] = True
                self._stacked_counts[filt] = (n_linked, effective)

                # Full-frame (uncropped) per-channel master.  Kept in
                # masters/ as *_fullframe; the aligned/cropped version is
                # produced later by _align_masters as TARGET_FILTER.fit.
                out_name = self._master_stem(filt, n_stack)
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
                    self._note_command(
                        f"{os.path.basename(final)} copied by the script "
                        f"from {self._here(produced)}, where Siril wrote "
                        f"it, into {self._here(masters_dir)} — every path "
                        "named below is the copy")
                    # Per-channel background extraction on the linear master --
                    # gradients differ per filter, so removing them before the
                    # channels are combined works better than one pass on the
                    # finished colour image.
                    if self._opts.get("bg_master", True):
                        self._bg_extract_master(final, filt)
                    # Rescue the rejection maps: Siril writes them next to
                    # the stack output inside _work/, which the user never
                    # opens and which "Delete _work/" removes.
                    if self._opts.get("rejmap", False):
                        self._collect_rejmaps(
                            os.path.join(work, "process"), out_name)
                    # The stack output was checked above, but the master is
                    # written a second time by the background extraction --
                    # through Siril, whose `save` can fail without raising.
                    self._verify_outputs([final], f"{filt} master")
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
                # ...and give the disk back now that the master is safe in
                # masters/.  Keeping every filter's registered frames until
                # the end makes peak usage the SUM of all channels: six
                # filters of 3000x3000 32-bit subs is over a gigabyte that
                # nothing reads again.  Only on success -- a failed filter
                # keeps its intermediates for inspection.
                if filt in results:
                    self._release_work(work, filt)
            except (CommandError, DataError, SirilError) as exc:
                errors[filt] = str(exc)
                self._emit(f"  {filt} failed: {exc}", LogColor.RED)

        return results, errors, last_result

    def _calibrate_in_parts(self, filt: str, staged: list,
                            conv: str) -> str:
        """Calibrate each part with its own masters, then merge them.

        Returns the merged sequence name, with Siril left in the filter's
        `process` directory -- the same state the single-pass branch
        leaves behind, so registration and stacking are unchanged.  The
        channel therefore still becomes ONE master: splitting is a
        calibration concern, not a stacking one.

        The merged name carries no trailing underscore because Siril
        appends ``_00001`` itself; a trailing one would give the double
        underscore that `_count_seq_frames` then fails to match.
        """
        base = (self._groups.get(filt) or {}).get("info") or {}
        # The note is what the report prints under "Calibration".  It stays
        # empty until something is really applied: a filter whose every
        # exposure went uncalibrated must not put a calibration step into
        # a report where none happened.
        self._calib_notes.pop(filt, None)
        # The parts are merged again before stacking, so what decides the
        # cosmetic threshold is the filter's TOTAL -- a 4-frame part of a
        # 60-frame filter is not a small stack.
        n_total = sum(k for _t, _e, _n, _d, k in staged)
        notes: list = []
        seqs: list = []
        applied = 0
        for tag, exp, night, d, _k in staged:
            self._note_command(
                f"{_k} {filt} light frame(s) staged into "
                f"{self._here(d)} by the script")
            self._cmd("cd", f'"{d}"')
            self._cmd(conv, f"lights_{tag}", "-out=../process")
            self._cmd("cd", "../process")
            # Everything else is shared: same filter, same camera.  Only
            # the dark (exposure) and the flat (night) lookups change.
            info = dict(base, exp_s=exp, exp=f"{exp:g}s")
            args = self._calibrate_args(filt, info, n_frames=n_total,
                                        warn_mixed=False, night=night)
            what = " ".join(x for x in (f"{exp:g}s" if exp else "", night)
                            if x) or tag
            if args:
                self._emit(f"  {what}: calibrate lights_{tag} "
                           + " ".join(args), LogColor.BLUE)
                self._cmd("calibrate", f"lights_{tag}", *args)
                seqs.append(f"pp_lights_{tag}")
                notes.append(f"{what}: {self._calib_notes.get(filt, '')}")
                applied += 1
            else:
                # No master fits this part.  Its frames still belong in
                # the stack -- uncalibrated, and named as such in the log.
                self._emit(
                    f"  {what}: no calibration master matches these "
                    "frames; they go in uncalibrated.",
                    LogColor.SALMON)
                seqs.append(f"lights_{tag}")
                notes.append(f"{what}: uncalibrated")
        if applied:
            self._calib_notes[filt] = " | ".join(notes)
        else:
            self._calib_notes.pop(filt, None)
        merged = f"merged_{self._tok(filt)}"
        self._cmd("merge", *seqs, merged)
        # The merge copied every frame, so each part is now a duplicate.
        # The parts CANNOT be deleted here.  `merge` writes its sequence in
        # milliseconds -- 30 frames in 4 ms, where a real copy of 30 x
        # 36 MB could not be -- because it SYMLINKS the source frames
        # instead of copying them.  Dropping the parts at this point left
        # `merged_<filt>` a set of dangling links, and registration then
        # failed with "failed to find or open merged_HA_00001.fit" on
        # every filter.  They are recorded and dropped once registration
        # has written real frames of its own.
        proc_dir = os.path.dirname(staged[0][3].rstrip(os.sep))
        proc_dir = os.path.join(proc_dir, "process")
        self._part_cleanup[filt] = (
            proc_dir,
            [n for tag, _e, _n, _d, _k in staged
             for n in (f"pp_lights_{tag}", f"lights_{tag}")],
            [d for _t, _e, _n, d, _k in staged])
        # Only now, and only if a master was really applied: a merge that
        # raised sends the caller down the single-pass path, and a split
        # that calibrated nothing is not a calibration story to tell.
        if applied:
            # Name the dimension that actually split, so the report says
            # which master the parts were kept apart FOR.
            why = []
            if len({e for _t, e, _n, _d, _k in staged}) > 1:
                why.append("exposures")
            if len({n for _t, _e, n, _d, _k in staged if n}) > 1:
                why.append("nights")
            self._split_filters[filt] = " and ".join(why) or "parts"
        self._emit(
            f"  Merged {len(seqs)} sequence(s) into {merged} "
            f"({applied} calibrated).", LogColor.GREEN)
        return merged

    def _drop_parts(self, filt: str) -> None:
        """Free the calibrated parts a merged sequence pointed at.

        Deferred out of `_calibrate_in_parts` because Siril's `merge`
        symlinks its sources rather than copying them: deleting the parts
        while `merged_<filt>` was the current sequence turned it into
        dangling links, and registration failed on every filter.  Safe
        the moment registration has written frames of its own.
        """
        proc_dir, seqs, staged = self._part_cleanup.pop(filt, (None, [], []))
        if not proc_dir:
            return
        for name in seqs:
            self._drop_generation(proc_dir, name)
        for d in staged:
            self._drop_staged(d)

    def _drop_generation(self, process_dir: str, seq: str) -> None:
        """Delete one sequence's frames now that its successor exists.

        The chain is lights -> pp_ -> bkg_ -> r_, and every step writes a
        full copy of every frame.  Keeping all of them until the master is
        written makes peak disk usage the SUM of the generations: a
        hundred 3008x3008 32-bit subs are about 3.6 GB per generation, so
        four of them is most of a laptop's free space for one channel.

        Deleting the predecessor the moment its successor is complete
        keeps the peak at roughly two.  Bounded by the same option that
        governs `_work/` as a whole -- someone who unticks "Delete _work/
        when finished" wants those intermediates, and taking them away
        one step earlier would be taking exactly what they asked to keep.

        Never touches the sequence it is given if that is also the one
        still needed: callers pass the OLD name, after the new one exists.
        """
        if not self._opts.get("cleanup_work", False):
            return
        # `_\d*` rather than `_\d+`: Siril's own sequence file is
        # "<seq>_.seq" -- underscore, no number -- and requiring a digit
        # left it behind while its frames were deleted.
        pat = re.compile(re.escape(seq) + r"(_\d*)?\.(fit|fits|fts|seq)$",
                         re.IGNORECASE)
        freed = 0
        try:
            names = os.listdir(process_dir)
        except OSError as exc:
            _log_swallowed(exc)
            return
        for name in names:
            if not (pat.match(name) or name == f"{seq}_conversion.txt"):
                continue
            path = os.path.join(process_dir, name)
            try:
                # lstat, not getsize: the staged frames are symlinks by
                # default, and following them would report the originals'
                # size as space this run had freed.
                freed += os.lstat(path).st_size
                os.remove(path)
            except OSError as exc:
                _log_swallowed(exc)
        if freed > 50e6:          # below that it was a set of symlinks
            self._emit(
                f"  Freed {freed / 1e9:.2f} GB — {seq} is no longer needed.",
                LogColor.BLUE)

    def _drop_staged(self, staged_dir: str) -> None:
        """Delete a staging folder once its calibrated copy exists.

        In copy mode this is a full second copy of the light frames; in
        the default symlink mode it costs nothing and goes away with the
        rest of `_work/`.  Same option gate as `_drop_generation`.
        """
        if not self._opts.get("cleanup_work", False):
            return
        self._discard_dir(staged_dir, "staged copy of the light frames")

    def _release_work(self, work: str, filt: str) -> None:
        """Delete one filter's working tree once its master is written.

        Bounded by the option that governs the whole `_work/` folder: a
        user who unticks "Delete _work/ when finished" wants the
        intermediates, and deleting them per filter would take exactly
        what they asked to keep.
        """
        if not self._opts.get("cleanup_work", False):
            return
        self._discard_dir(work, f"{filt} working tree")

    def _write_stub_report(self) -> None:
        """Write a brief output.md (replaced by the full report when done)."""
        txt = (
            "# Svenesis ImageMono Train — output\n\n"
            "Processing is running… the **full report** is written to this "
            "file when the run finishes.\n\n"
            "**Folder layout**\n\n"
            "- `TARGET_<palette>.fit` — the finished colour image (linear)\n"
            "- `masters/` — per-channel masters "
            "(`*_fullframe` = full field, named after the frames, "
            "exposure, gain and temperature that made it; the others are "
            "aligned)\n"
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
        A("| `masters/…_<FILTER>_<N>x<EXP>_G<gain>_<temp>C_fullframe.fit` "
          "| The same channel at **full, uncropped** size.  The name is "
          "the recipe: frames integrated, exposure, gain, sensor "
          "temperature. |")
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
            #
            # Scaling by the FRAME ratio silently assumes every frame of
            # this filter is the same length.  When it mixes exposures --
            # which this script supports on purpose, see `_calib_split` --
            # that is an approximation: nothing here records WHICH frames
            # were dropped, so the average length is the only estimate
            # available.  On 20x300s + 10x120s it can be eight minutes out.
            # It is used anyway, and marked, rather than quietly presented
            # as measured.
            exp_used = exp * effective / n if n else 0.0
            mixed_exp = len(g.get("by_exp") or {}) > 1 and effective != n
            if mixed_exp:
                any_estimated = True
            if self._measured.get(filt):
                # Counted from the sequence Siril actually exported, so
                # every filter it applied is already in this number.  No
                # hedge belongs on a measurement.
                if effective != n:
                    any_reduced = True
                used = f"**{effective}**" if effective != n else str(effective)
            elif k_sigma and self._quality_filter_args(staged):
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
            A(f"| {filt} | {n} | {used} | "
              + ("~" if mixed_exp else "")
              + f"{_format_duration(exp_used)} | {rej_label} |")
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
              "upper bound, and so is the integration time beside it.  A "
              "**~** on an integration time marks a channel that mixes "
              "exposure lengths and lost frames: which ones were dropped "
              "is not recorded, so their average length stands in.")
        if self._reg_stats:
            A("")
            A("**Registration quality**, read back from the sequences Siril "
              "registered — measured, not estimated:")
            A("")
            A("| Filter | Integrated | Median FWHM | Roundness | Stars |")
            A("|---|---:|---:|---:|---:|")
            def _stat(q, key, spec):
                # "not recorded" must not render as a zero that reads
                # like a measurement of a disastrous value.
                v = q.get(key)
                return format(v, spec) if v is not None else "—"

            for filt in sorted(self._reg_stats):
                q = self._reg_stats[filt]
                # A count sitting on Siril's ceiling is the ceiling, not
                # a property of the frame.  Marked rather than printed
                # plain, which read as a measurement of a rich field.
                star_txt = _stat(q, "stars", ".0f")
                if filt in self._stars_capped:
                    star_txt += " †"
                A(f"| {filt} | {q['included']} of {q['total']} "
                  f"| {_stat(q, 'fwhm', '.2f')} px | "
                  f"{_stat(q, 'roundness', '.2f')} | {star_txt} |")
            A("")
            if self._stars_capped:
                A(f"> † Star detection hit Siril's ceiling of "
                  f"{SIRIL_MAX_STARS} on these filters, so the count is "
                  "that limit and not a measurement.  Weighting frames "
                  "*by number of stars* cannot separate frames that all "
                  "report the cap; *Noise* or *Weighted FWHM* still can.")
                A("")
            A("> Roundness is 1.00 for perfectly round stars; a value well "
              "below that means trailing. The star count is Siril's own "
              "detection on the reference layer — a channel far below the "
              "others usually means the filter simply passes less light, "
              "not that anything went wrong.")
        gaps = opts.get("missing_api") or []
        if gaps:
            A("")
            A("> ℹ️ **Siril's Python module is older than this script "
              f"expects**, so {len(gaps)} "
              + _plural(gaps, "feature took", "features took")
              + " a simpler route. This is not an error and nothing was "
              "skipped — but it is why some of the numbers above are "
              "estimates rather than measurements. Updating Siril "
              "restores "
              + _plural(gaps, "it", "them") + ":")
            for feature, calls, consequence in gaps:
                A(f">   - **{feature}** — needs `"
                  + "`, `".join(calls)
                  + f"`; without it, {consequence}.")
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
                for why in sorted(set(self._split_filters.values())):
                    which = ", ".join(sorted(
                        f for f, w in self._split_filters.items() if w == why))
                    one = which.count(",") == 0
                    A(f"    - **{which}** span several {why}, so "
                      + ("that channel was" if one else "those channels were")
                      + " calibrated in parts and the parts merged again "
                      "before registration (`merge`), which is why "
                      + ("it still ends" if one else "they still end")
                      + " as one master per filter."
                      + (" A dark only removes the thermal signal that grew "
                         "during ITS exposure, so one dark for two exposures "
                         "is right for neither." if "exposures" in why else "")
                      + (" A flat only describes the optical train it was "
                         "shot through, so each night's lights were divided "
                         "by that night's own master flat."
                         if "nights" in why else ""))
                for filt, notes in sorted(self._night_notes.items()):
                    seen = sorted(set(notes))
                    A(f"    - **{filt}** per night: "
                      + "; ".join(f"{n} → `{m}`" for n, m in seen))
                for filt, (spread, other, ref, floor) in sorted(
                        self._flat_warn.items()):
                    A(f"    - ⚠️ **{filt}: the flats of {other} and {ref} "
                      f"differ by {spread * 100:.3f}%.** They were pooled "
                      "into one master anyway, which is right only if the "
                      "optical train did not move between those nights. "
                      + ("That is above the "
                         f"{FLAT_MATCH_LIMIT * 100:.1f}% where a pooled "
                         "master stops correcting either night properly — "
                         "re-run with **Match flats to the same night**."
                         if spread > FLAT_MATCH_LIMIT else
                         "It is still inside the usable range, so this is "
                         "a note rather than a problem.")
                      + " (Measured by averaging each night's flats, binning "
                      f"them to ~{FLAT_COMPARE_TARGET} px and dividing one "
                      "by the other — a matching pair gives a uniform "
                      "result."
                      + (f"  The noise floor of that measurement is "
                         f"{floor * 100:.3f}%." if floor is not None else "")
                      + ")")
                if opts.get("calib_library"):
                    A("    - Darks / bias were taken from the library "
                      f"`{opts['calib_library']}`; flats come from the "
                      "session next to the lights.")
                if opts.get("cosmetic", True):
                    used = sorted(set(self._cc_used.values()))
                    if len(used) == 1:
                        A(f"    - Cosmetic correction (`{used[0]}`) was "
                          "applied.")
                    elif used:
                        # Two thresholds in one run is the normal case for a
                        # target with one short channel; naming only one of
                        # them would describe the other filters wrongly.
                        A("    - Cosmetic correction ran with a **per-filter**"
                          " threshold — a channel with "
                          f"{COSMETIC_TIGHT_MAX_FRAMES} frames or fewer is "
                          "corrected harder, because stacking rejection "
                          "cannot take a hot pixel out of that few dithered "
                          "frames:")
                        for _f, _c in sorted(self._cc_used.items()):
                            A(f"        - {_f}: `{_c}`")
                    else:
                        A("    - Cosmetic correction was requested — it only "
                          "takes effect for filters that actually got a "
                          "matching dark, and none did.")
                if opts.get("flats_by_date"):
                    A("    - Flats were matched **per night** (only flats "
                      "from the same observing night as the lights were "
                      "used).  The night is taken from each frame's own "
                      "`DATE-OBS`, counted noon to noon, so a session "
                      "running past midnight stays one night instead of "
                      "being split by its date folders; frames without a "
                      "readable `DATE-OBS` fall back to the folder name.")
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
                # and the count it was told it for.  _stacked_counts pairs
                # the staged count with what SURVIVED, and the survivor is
                # a different number that would give a wrong answer here.
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
                    why = self._reg_degraded_why.get(
                        f, "Siril refused the full argument set for this "
                           "channel and it fell back to a smaller one")
                    A(f"    - \u26a0\ufe0f **{f}** was registered without "
                      + ", ".join(self._reg_degraded[f])
                      + f".  {why} — the line above does not describe this "
                      "master.")
            if self._drizzle_warned:
                A(f"    - ⚠️ Drizzle ran on fewer than {DRIZZLE_MIN_FRAMES} "
                  "frames. It spreads each sub's flux over a finer grid, so "
                  "it needs many *dithered* subs to fill that grid evenly — "
                  "below that it usually adds noise instead of resolution. "
                  "Compare against an undrizzled run before keeping this.")
            A(N() + " **Integration** (`stack`):")
            A("    - **Rejection** is chosen automatically from each "
              "filter's frame count (see the table above) — percentile "
              f"clipping up to 4, plain sigma to {SIGMA_MAX_FRAMES}, "
              f"Winsorized to {GESDT_MIN_FRAMES - 1}, **GESDT** to "
              f"{LINEAR_MIN_FRAMES}, and linear fit beyond that.  Sigma-based "
              "methods need a population to work, so few-frame channels use "
              "gentler percentile clipping; linear fit sits at the top "
              "because it models a trend across the stack and needs a long "
              "one to define it.  These band edges are Cyril Richard\u2019s, "
              "taken from **AMSP** in the official Siril script "
              "repository — he wrote Siril and implemented these "
              "algorithms.")
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
              + (", output-normalized — each master was rescaled into "
                 "[0, 1] as `(x − min) / (max − min)` from its **own** "
                 "extremes, so the channels are no longer on one absolute "
                 "scale. Harmless for a picture; switch it off when the "
                 "levels matter."
                 if opts.get("output_norm", True) else "."))
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
            A("→ saved as `masters/<TARGET>_<FILTER>_<N>x<EXP>_G<gain>"
              "_<temp>C_fullframe.fit` — e.g. "
              "`M16_HA_29x300s_G100_-10C_fullframe.fit`, so the file says "
              "what went into it without opening it.")
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
                if self._align_pairs:
                    weak = _align_pairs_warn(self._align_pairs)
                    A("How many stars each channel was matched on — the "
                      "number the transform was fitted from:")
                    A("")
                    A("| Channel | Star pairs | |")
                    A("| --- | ---: | --- |")
                    for f in sorted(self._align_pairs):
                        if f == self._align_ref:
                            continue      # listed as the reference below
                        A(f"| {f} | {self._align_pairs[f]} | "
                          + ("⚠️ |" if f in weak else " |"))
                    if self._align_ref:
                        A(f"| {self._align_ref} | — | _reference_ |")
                    A("")
                    if weak:
                        A("> ⚠️ A scale term fitted on that few points is "
                          "carried badly, and that is what puts colour "
                          "fringing towards the edges.  Siril's two-pass "
                          "registration picks the reference itself from "
                          "whatever is in the sequence, so a narrowband "
                          "channel having to match a star-rich broadband "
                          "reference is the usual cause — *Stack only the "
                          "filters this palette uses* keeps the reference "
                          "among the channels that end up in the picture.")
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
            if _is_nb_palette(palette) and opts.get("nb_normalize", True):
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
            if palette in _MIX_PALETTES:
                A("- **Mixed** the channels with `pm`: "
                  + "; ".join(
                      f"{ch.upper()} = {_mix_words(mix)}"
                      for ch, mix in _MIX_PALETTES[palette].items())
                  + ".  Colour calibration is skipped for a mixed "
                  "channel — it has no single passband.")
            baked = palette == "LRGB" and opts.get("quick_lrgb")
            A("- **Combined** the channels "
              + ("with `rgbcomp` (luminance baked in linearly — the "
                 "*quick* mode)." if baked else
                 f"{self._compose_how or 'with `rgbcomp`'}."))
            if self._synth_lum:
                A(f"- **Synthetic luminance** → "
                  f"`{MASTERS_DIRNAME}/"
                  f"{os.path.basename(self._synth_lum)}`, the **equal-weight "
                  "average** of the emission-line masters.  That is not the "
                  "SNR-optimal combination when the lines differ in strength "
                  "— a much fainter channel pulls the result down, so hold "
                  "it against your strongest channel before building on it. "
                  " It was **not** combined into the colour image: that "
                  "belongs after the stretch (see `todo.md`).")
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
            if self._spcc_fit:
                fit = self._spcc_fit
                sig = fit.get("sigma") or {}
                worst = max(sig.values(), default=0.0)
                A("**How well the colour solution fitted.** Siril compares "
                  "each star's measured colour with the one predicted from "
                  "its catalogue spectrum; **sigma** is how far the two "
                  "disagree. The white balance was applied either way — "
                  "this says how much it is worth.")
                A("")
                A("| Quantity | Value | |")
                A("| --- | ---: | --- |")
                for ratio in sorted(sig):
                    A(f"| σ of the {ratio} fit | {sig[ratio]:.3f} | "
                      + ("⚠️ |" if sig[ratio] > SPCC_SIGMA_LIMIT else " |"))
                if fit.get("stars"):
                    A(f"| Stars in the solution | {fit['stars']} | |")
                if fit.get("excluded"):
                    A(f"| Stars excluded | {fit['excluded']} | |")
                for i in sorted(fit.get("k") or {}):
                    A(f"| White balance K{i} | {fit['k'][i]:.3f} | |")
                A("")
                if worst > SPCC_SIGMA_LIMIT:
                    A(f"> ⚠️ **A sigma of {worst:.2f} means the measured "
                      "star colours barely follow the catalogue.** Treat "
                      "the white balance as a starting point, not a "
                      "measurement. On narrowband the usual cause is "
                      "*Normalize narrowband channels*, which flattens the "
                      "very line ratio SPCC then tries to calibrate; a "
                      "channel aligned on few star pairs does it too.")
                    A("")
                A("> Compare sigmas only between runs whose channels carry "
                  "the same lines. Two channels on neighbouring "
                  "wavelengths give a ratio near 1 for every star, so its "
                  "sigma is small because the measurement is insensitive, "
                  "not because the solution is good.")
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
               if self._separate_lum else
               (f"masters/{os.path.basename(self._synth_lum)}"
                if self._synth_lum else None))
        synth = bool(self._synth_lum and not self._separate_lum)
        # What the finish step REALLY did.  Telling the user "the colour is
        # already calibrated" when auto-finish was off, or when PCC could not
        # reach a catalog, would make them skip a step they still need.
        steps = self._finish_steps
        # Only the success line starts with "Colour calibration: " -- the
        # FAILED and skipped variants must not read as done.
        pcc_done = any(s.startswith("Colour calibration: ") for s in steps)
        bg_done = any(s.startswith("Extracted the background gradient")
                      for s in steps)
        nb_done = bool(composite and _is_nb_palette(palette)
                       and self._opts.get("nb_normalize", True))
        # Narrowband SPCC ran instead of the normalization -- the intended
        # pairing, and the reason the advice below must not be "switch
        # normalization back on".
        nb_spcc = bool(composite and palette in _NB_PALETTES
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
            A("4. **SCNR** (remove green) *(optional)* — *Image Processing "
              "→ Remove Green Noise*, or `rmgreen`. Nothing in a broadband "
              "sky is genuinely green, so a green cast is colour noise "
              "and this is its usual cure. It runs here rather than in "
              "the script because it is non-linear, and the composite is "
              "handed over linear on purpose.")
            A("5. **Denoise** *(optional)* — reduce colour noise now while "
              "it's easy.")
            A("6. **Saturation** *(optional)* — boost gently for richer "
              "colour.")
            A("")
            if lum:
                A(f"## Part B — Luminance (open `{lum}`)")
                A("")
                if synth:
                    A("This luminance is **synthetic** — the average of the "
                      "emission-line masters, so it carries their combined "
                      "signal-to-noise. It was deliberately not combined "
                      "into the colour image: doing that on linear data "
                      "lifts the bright end before colour calibration, "
                      "which is the same mistake *Quick linear LRGB* makes.")
                    A("")
                A("7. **Sharpen while linear** *(optional)* — deconvolution or "
                  "a tool like BlurXTerminator. The luminance carries all the "
                  "fine detail, so this is where sharpening pays off most.")
                A("8. **Stretch L** to taste — this defines the contrast and "
                  "detail of the final image.")
                A("9. **Denoise, then sharpen** *(optional)*.")
                A("")
                A("## Part C — Combine L + RGB  *(do this LAST)*")
                A("")
                A("10. With **both already stretched**, combine them: in "
                  "Siril use *Image Processing → RGB composition* with the "
                  "**luminance** slot, or the command "
                  "`rgbcomp -lum=<stretched L> <stretched RGB>`. The luminance "
                  "supplies detail, the RGB supplies colour.")
                A("11. **Final touches** — curves, local contrast, star "
                  "reduction, crop the edges.")
                A("12. **Export** a 16-bit TIFF or PNG.")
            else:
                A("## Part B — Finish")
                A("")
                A("7. **Final touches** — curves, local contrast, star "
                  "reduction, crop the edges.")
                A("8. **Export** a 16-bit TIFF or PNG.")
            A("")
            A("---")
            A("")
            A("### Tips")
            if _is_nb_palette(palette) and "sii" in _palette_roles(palette):
                A("- **Magenta / purple stars** are the classic artefact of "
                  "a three-line palette: stars are continuum sources, so "
                  "they land in Red and Blue but not in the Green channel. "
                  "The usual remedy, *after stretching*: `invert` → "
                  "`rmgreen` (SCNR) → `invert`. It is not done here because "
                  "inverting linear data does not mean what it means after "
                  "a stretch.")
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
        A("5. **SCNR** (remove green) — *Image Processing → Remove Green "
          "Noise*, or `rmgreen`. Do it **here**, on the stretched image, "
          "and judge it by eye: Siril computes `green = min(green, "
          "(red + blue) / 2)`, and in this palette the green channel "
          "carries a real emission line, so too much of it cuts measured "
          "signal rather than a cast. The script does not do it for you "
          "for that reason.")
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
            # Only when reuse is actually on.  `reusable_full` below is
            # consumed solely through `skip`, which stays empty without
            # `want_reuse`, so on a fresh run this scan is work nothing
            # reads -- and its one visible effect is a swallowed
            # FileNotFoundError per filter for a masters/ directory that
            # does not exist yet: four alarming lines before the run has
            # done anything at all.
            full_paths = ({filt: self._find_fullframe(mdir, filt)
                           for filt in filters} if want_reuse else {})
            missing_aligned = [f for f, p in aligned_paths.items()
                               if not os.path.exists(p)]
            mixed = ({} if missing_aligned or not want_reuse
                     else _mixed_grids(aligned_paths))
            reusable_full = {f: p for f, p in full_paths.items() if p}
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
                # `reuse_ok` already required `_mixed_grids` to be empty,
                # so these came off one grid -- otherwise the composition
                # guard below would explain a mismatch that cannot occur
                # here with the single-pass fallback's wording.
                self._align_framing_min = True
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
                        # A channel that stacked but did not survive the
                        # alignment has to say so.  Without an entry here
                        # the report falls through to "not reached -- the
                        # run was stopped", which describes neither what
                        # happened nor the finished master in masters/.
                        for filt in results:
                            if filt not in aligned:
                                errors.setdefault(
                                    filt,
                                    self._align_dropped.get(filt)
                                    or "excluded during cross-filter "
                                       "alignment; the full-frame master "
                                       "in masters/ is intact, but it is "
                                       "not on the common grid and is not "
                                       "in the composite")
                        final_paths = aligned
                        did_align = True

            want_compose = self._opts.get("compose", False)
            if want_compose and len(final_paths) >= 2:
                # _compose states that its inputs are identical in size.
                # -framing=min guarantees that -- but only when it really
                # ran: the single-pass fallback inside _align_masters
                # registers without it, and `did_align` is set either way.
                # Gating this check on that flag therefore trusted a
                # promise the fallback never made, so the sizes are read
                # from the files instead.  A proper alignment run passes
                # this in silence; it costs a header read per channel.
                off = _mixed_grids(final_paths)
                if off:
                    shown = ", ".join(f"{f} {w}\u00d7{h}"
                                      for f, (w, h) in sorted(off.items()))
                    why = ("alignment ran, but without the -framing=min "
                           "re-projection that puts them on one grid"
                           if did_align and not self._align_framing_min
                           else "alignment did not run" if not did_align
                           else "they came out of the alignment on "
                                "different grids")
                    self._emit(
                        "Colour composition skipped: the masters are not on "
                        f"one pixel grid ({shown}) — {why}. Combining them "
                        "would misregister the channels. The per-filter "
                        "masters are complete and can be composed after a "
                        "successful alignment.", LogColor.SALMON)
                    want_compose = False

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
                # `_discard_dir` also returns True for a folder that was
                # never there (full master reuse writes no _work/), and
                # announcing a cleanup that had nothing to clean is the
                # kind of sentence this report exists to avoid.
                if (os.path.isdir(work_root)
                        and self._discard_dir(work_root, "_work/ folder")):
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
        except SirilGoneError as exc:
            # One message for one cause.  The traceback would only point
            # at whichever command happened to die first, which is noise:
            # the cause is that Siril itself went away.
            msg = ("The connection to Siril was lost mid-run "
                   f"({exc}).  Siril has crashed or was closed; no further "
                   "command can succeed, so the run stopped at the first "
                   "dead reply instead of blaming each step in turn.  "
                   "Restart Siril and run this script again — finished "
                   "masters are picked up by 'Reuse existing masters'.")
            self._write_failure_report(exc, msg)
            self.failed.emit(msg)
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
    def _pm_stage(self, src: str, helpers: str, tag: str) -> str:
        """Copy a master into the helper folder under a PixelMath-safe name.

        PixelMath refers to an image by its file name, inside an
        arithmetic expression.  A hyphen in that name -- the sensor
        temperature in a full-frame master (`-10C`), or a target called
        NGC-7000 -- would sit in the middle of a subtraction.  Rather than
        guess how Siril's parser resolves that, the inputs are staged
        under names made of letters, digits and underscores only.
        """
        name = f"pm_{tag}"
        shutil.copy2(src, os.path.join(helpers, name + self._ext))
        self._note_command(
            f"{name}{self._ext} copied from {os.path.basename(src)} by the "
            "script — PixelMath names the file inside the expression, and "
            "the original carries hyphens")
        return name

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

        # All mapped masters live in one directory; `_rgbcomp` needs it to
        # build the relative names that command insists on.
        in_dir = os.path.dirname(paths[m_red])
        # Compose helpers (_nbnorm / _RED_Ha / _mix) are written under
        # _work/helpers so masters/ stays clean.
        helpers = os.path.join(self._out_dir, WORK_DIRNAME, "helpers")
        os.makedirs(helpers, exist_ok=True)
        try:
            self._cmd("cd", f'"{in_dir}"')
            # The channel PATHS are absolute from here on, so nothing
            # downstream depends on the working directory; `_rgbcomp`
            # makes the relative names it needs where it needs them.
            # (`_norm` below still reads by basename -- see its docstring.)
            #
            # `use_path` is what every later step reads: the aligned
            # master, or its normalised copy once that has been made.
            use_path = dict(paths)
            red_basename = paths[m_red]
            green_basename = paths[m_green]
            blue_basename = paths[m_blue]

            # Narrowband normalization (Siril's recommendation): before
            # combining SHO/HOO, linear-match each channel to the Ha
            # reference so the strong Ha doesn't dominate and turn the
            # result green.  Matched copies (*_nbnorm) are written so the
            # original aligned masters stay untouched.
            # Which masters this palette actually reads.  An assignment
            # reads the three mapped ones; a weighted mix reads every
            # filter its weights name, which the dropdowns do NOT cover --
            # they can only show one source per channel.
            if palette in _MIX_PALETTES:
                needed = [f for f in paths
                          if _filter_role(f) in _palette_roles(palette)]
            else:
                needed = [m_red, m_green, m_blue]

            if (_is_nb_palette(palette)
                    and self._opts.get("nb_normalize", True)):
                ref_filter = next(
                    (f for f in needed
                     if _filter_role(f) == "ha"), m_green)
                ref_base = os.path.basename(paths[ref_filter])
                # 32-bit images live in [0,1]; ignore near-saturated stars.
                low, high = "0", "0.92"
                norm_cache: dict = {}

                def _norm(fname):
                    """The channel to use, as an ABSOLUTE path.

                    The RESULT is absolute; the inputs are not.  Both
                    `load` and `linear_match` take a file name that Siril
                    resolves against the working directory, which is
                    `in_dir` here -- the folder holding every master.
                    Only `save` gets an absolute path, because the
                    normalised copy belongs in the helper folder.
                    """
                    if fname == ref_filter:
                        return paths[fname]                     # reference
                    if fname in norm_cache:
                        return norm_cache[fname]
                    src = os.path.basename(paths[fname])
                    out = os.path.join(
                        helpers, os.path.splitext(src)[0] + "_nbnorm")
                    self._cmd("load", src)
                    self._cmd("linear_match", ref_base, low, high)
                    self._cmd("save", f'"{out}"')
                    norm_cache[fname] = out + self._ext
                    return norm_cache[fname]

                self._emit(
                    f"  {out_label}: normalizing channels to {ref_filter} "
                    "(linear_match).", LogColor.BLUE)
                # Every master this palette reads, not just the three the
                # dropdowns name: a mixed channel pulls in a filter that
                # has no dropdown, and leaving it unnormalised would put
                # the raw Ha level back into the mix.
                for fname in needed:
                    use_path[fname] = _norm(fname)
                red_basename = use_path[m_red]
                green_basename = use_path[m_green]
                blue_basename = use_path[m_blue]

            # HaRGB: blend the Ha master into the Red channel first, then
            # compose as usual.  Ha is located by filter role among the
            # aligned masters.
            #
            # A WEIGHTED SUM, not the screen blend this used to run.
            # `1-(1-R)*(1-k*Ha)` expands to `R + k*Ha - k*R*Ha`, and that
            # cross term is quadratic in flux: at R=0.8 with k*Ha=0.4 it
            # returns 0.88 where the sum gives 1.2, a 27% compression of
            # the bright end.  Non-linear, in other words -- the one
            # property this file promises about every composite it writes,
            # and the same objection that took `rmgreen` out in 1.7.4.
            #
            # `(R + k*Ha)/(1+k)` is linear, stays in [0,1] without a
            # rescale (numerator <= 1+k), and never discards R: it is the
            # weighted mean (1-w)*R + w*Ha with w = k/(1+k).  The slider
            # therefore runs from "pure R" at 0% to an even mix at 100%,
            # where the screen blend's 100% was an unbounded-looking
            # brightening whose actual strength depended on the data.
            if palette == "HaRGB":
                ha_filter = next(
                    (f for f in paths if _filter_role(f) == "ha"), None)
                if ha_filter and ha_filter in paths:
                    k = max(0, min(100,
                                   int(self._opts.get("ha_strength", 50)))) / 100.0
                    r_var = self._pm_stage(paths[m_red], helpers, "R")
                    ha_var = self._pm_stage(paths[ha_filter], helpers, "Ha")
                    enhanced = os.path.join(
                        helpers, f"{_safe(self._target)}_RED_Ha")
                    expr = (f"(${r_var}$+{k:g}*${ha_var}$)/{1.0 + k:g}"
                            if k else f"${r_var}$")
                    self._emit(
                        f"  HaRGB: blending {ha_filter} into Red — "
                        f"{1.0 / (1.0 + k):.2f}·{m_red} + "
                        f"{k / (1.0 + k):.2f}·{ha_filter}, a weighted sum so "
                        "the composite stays linear (PixelMath).",
                        LogColor.BLUE)
                    # PixelMath resolves a variable against the working
                    # directory, so the staged copies decide the names.
                    self._cmd("cd", f'"{helpers}"')
                    self._cmd("pm", f'"{expr}"')
                    self._cmd("save", f'"{enhanced}"')
                    self._cmd("cd", f'"{in_dir}"')
                    red_basename = enhanced + self._ext
                else:
                    self._emit(
                        "  HaRGB: no Ha master found; composing plain RGB.",
                        LogColor.SALMON)
                    out_label = "RGB"

            if (self._opts.get("synth_lum", False)
                    and _is_nb_palette(palette)
                    and not self._separate_lum):
                self._synthetic_luminance(palette, use_path, helpers)

            chan = {"red": red_basename, "green": green_basename,
                    "blue": blue_basename}
            if palette in _MIX_PALETTES:
                mixed = self._mix_planes(palette, use_path, helpers)
                if mixed is None:
                    return None
                chan = mixed

            out_path = os.path.join(
                self._out_dir, f"{_safe(self._target)}_{_safe(out_label)}")
            self._emit(
                f"  Composing {out_label}: "
                + (f"L={m_lum} " if use_lum else "")
                + (_mix_words(_MIX_PALETTES[palette]["red"]) + " -> R, …"
                   if palette in _MIX_PALETTES
                   else f"R={m_red} G={m_green} B={m_blue}")
                + ("  (L kept separate for post-stretch combine)"
                   if self._separate_lum else ""), LogColor.BLUE)

            result = None
            if not use_lum:
                # Assemble in memory.  `rgbcomp` stays as the fallback --
                # and it is the ONLY way to do the -lum= combine, which is
                # Siril's own luminance transfer, not a channel copy.
                result = self._push_composite(chan, out_path)
            if result is None:
                result = self._rgbcomp(chan, out_path, in_dir,
                                       paths[m_lum] if use_lum else "")
            return result
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Colour composition failed: {exc}", LogColor.RED)
            return None

    def _mix_planes(self, palette: str, paths: dict,
                    helpers: str) -> dict | None:
        """Build the R/G/B planes of a weighted palette with PixelMath.

        A weighted sum is the one kind of channel mixing that means the
        same thing on linear data as on stretched data, which is why these
        palettes are offered here and the dynamic ones (Foraxx and
        friends) are not.  The arithmetic is left to Siril rather than
        done in numpy, so every pixel operation in this script goes
        through the same engine.

        Returns None -- and says which line is missing -- when the palette
        needs a filter this run does not have.
        """
        out: dict = {}
        for ch, mix in _MIX_PALETTES[palette].items():
            terms = []
            for role, share in mix.items():
                src = next((f for f in paths if _filter_role(f) == role),
                           None)
                if src is None:
                    self._emit(
                        f"  {palette} needs {_ROLE_WORDS.get(role, role)} "
                        f"for the {ch.upper()} channel, and none was "
                        "produced — composition skipped.", LogColor.SALMON)
                    return None
                var = self._pm_stage(paths[src], helpers, f"{ch}_{role}")
                terms.append(f"{share:g}*${var}$")
            expr = "+".join(terms)
            dst = os.path.join(helpers, f"{_safe(self._target)}_{ch}_mix")
            self._emit(f"  {ch.upper()} = {expr}", LogColor.BLUE)
            self._cmd("cd", f'"{helpers}"')
            self._cmd("pm", f'"{expr}"')
            self._cmd("save", f'"{dst}"')
            out[ch] = dst + self._ext
        return out

    def _synthetic_luminance(self, palette: str, paths: dict,
                             helpers: str) -> None:
        """Average the emission-line masters into a luminance master.

        A narrowband night has no L filter, and the detail is spread over
        two or three channels.  Averaging them gives a master with the
        combined signal-to-noise, which is what a luminance layer is for.

        The average is UNWEIGHTED, and that is a limitation, not an
        oversight.  An equal-weight mean is only SNR-optimal when the
        channels carry comparable signal, and in SHO they do not: with
        signals 20 / 2 / 1 at equal noise the mean gives SNR 13.3 where
        the strongest channel alone gives 20.  A weighted combination
        would be better -- and was tried here, and taken back out:

          * the weights that maximise SNR, w ~ s/n**2, are NOT invariant
            under a per-channel rescale (scaling a channel by `a` divides
            its weight by `a`), and by the time this runs every master
            has been through `-output_norm`, which rescales each one
            affinely by its OWN extremes, and possibly `linear_match` on
            top.  Those scale factors are arbitrary, so the weights would
            follow them rather than the sky;
          * measuring the noise well enough is its own problem.  A
            k-sigma-clipped background sigma computed here disagreed with
            Siril's own `bgnoise` by 1.1x to 4.0x across three masters of
            one M 16 run -- worst exactly where nebulosity fills the
            frame -- and w ~ s/n**2 squares that error.  It put Ha at
            3.7% of an M 16 SHO luminance.

        A scale-invariant rule (w ~ s/n) fed by Siril's own `bgnoise`
        would be defensible; it needs a measurement this file does not
        have yet.  Until then the average is what is offered, and the
        report says what it is rather than implying it is optimal.

        It is deliberately NOT combined into the colour image here.  A
        luminance combine done on linear data lifts the bright end before
        colour calibration -- the same mistake "Quick linear LRGB" makes,
        measured at 531 clipped stars against 68.  The file is written,
        named in the report, and todo.md says where it belongs.
        """
        srcs: dict = {}
        for role in sorted(_palette_roles(palette)):
            filt = next((f for f in paths if _filter_role(f) == role), None)
            if filt and filt not in srcs:
                srcs[filt] = paths[filt]
        if len(srcs) < 2:
            self._emit(
                "  Synthetic luminance needs at least two distinct "
                "channels; skipped.", LogColor.SALMON)
            return
        terms = [f"${self._pm_stage(path, helpers, f'L{i}')}$"
                 for i, path in enumerate(srcs.values())]
        expr = f"({'+'.join(terms)})/{len(terms)}"
        out = os.path.join(self._out_dir, MASTERS_DIRNAME,
                           f"{_safe(self._target)}_SynthL")
        try:
            self._cmd("cd", f'"{helpers}"')
            self._cmd("pm", f'"{expr}"')
            self._cmd("save", f'"{out}"')
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  Synthetic luminance failed: {exc}",
                       LogColor.SALMON)
            return
        self._synth_lum = out + self._ext
        self._emit(
            f"  Synthetic luminance ({' + '.join(sorted(srcs))}) / "
            f"{len(terms)} -> {os.path.basename(self._synth_lum)}. An equal"
            "-weight average: a channel much fainter than the others pulls "
            "it down, so check it against the strongest channel before you "
            "build on it. It is not combined into the colour image: that "
            "belongs after the stretch (see todo.md).", LogColor.GREEN)

    def _push_composite(self, chan: dict, out_path: str) -> str | None:
        """Assemble the three channels in memory and hand them to Siril.

        Replaces `rgbcomp`, which cannot be given a path containing a
        space: its arguments are split on spaces before they reach the
        parser, which is why composition used to `cd` into the masters
        folder and pass bare basenames.

        Orientation needs no assumption here.  The planes are READ back
        through `get_image_pixeldata` and written with
        `set_image_pixeldata` unchanged, so whatever row order Siril uses
        internally is the row order it gets back -- a round trip, not a
        conversion.  Reading the files with astropy instead would mean
        deciding what ROWORDER means, and getting it wrong flips the
        image.

        `new` creates the RGB image rather than reusing a loaded mono
        master as a template: Siril stays in its single-layer display
        state after loading a mono image, and the pushed result then
        renders as monochrome (observed in PalettePicker, whose comment
        documents it).  Returns None on any failure, leaving the caller to
        fall back to rgbcomp.
        """
        try:
            planes = []
            for key in ("red", "green", "blue"):
                self._cmd("load", f'"{chan[key]}"')
                arr = np.squeeze(np.asarray(
                    self.siril.get_image_pixeldata(), dtype=np.float32))
                if arr.ndim != 2:
                    self._emit(
                        f"  In-memory composition: the {key} channel is "
                        f"not a single-layer image ({arr.ndim}D); using "
                        "rgbcomp instead.", LogColor.SALMON)
                    return None
                planes.append(arr)
            if len({p.shape for p in planes}) != 1:
                self._emit(
                    "  In-memory composition: the channels differ in size "
                    f"({', '.join(str(p.shape) for p in planes)}); using "
                    "rgbcomp instead.", LogColor.SALMON)
                return None
            height, width = planes[0].shape
            data = np.stack(planes)            # (3, H, W), channels-first
            header = _header_string(chan["red"])
            self._note_command(
                "the three masters above were read into memory by the "
                "script; `new` only makes an EMPTY RGB canvas and the "
                "pixels are written into it through sirilpy — replaying "
                "these lines saves a blank image")
            self._cmd("new", str(width), str(height), "3", "RGB")
            if not self.siril.is_image_loaded():
                self._emit("  In-memory composition: Siril did not create "
                           "the RGB image; using rgbcomp instead.",
                           LogColor.SALMON)
                return None
            with self.siril.image_lock():
                self.siril.set_image_pixeldata(data)
                if header:
                    try:
                        self.siril.set_image_metadata_from_header_string(
                            header)
                    except Exception as exc:
                        # Losing the WCS is a blemish; losing the image
                        # over it would not be.
                        _log_swallowed(exc)
                        self._emit(
                            "  Composite written without the source "
                            "metadata (WCS); plate-solving still works.",
                            LogColor.SALMON)
            self._cmd("save", f'"{out_path}"')
            result = out_path + self._ext
            if os.path.exists(result):
                self._compose_how = ("in memory (`new` + pixel data), so "
                                     "no path had to survive `rgbcomp`'s "
                                     "argument splitting")
                self._emit(
                    f"  Colour composite -> {os.path.basename(result)}",
                    LogColor.GREEN)
                return result
            return None
        except (CommandError, DataError, SirilError, NoImageError,
                AttributeError, ValueError, OSError) as exc:
            self._emit(
                f"  In-memory composition unavailable ({exc}); using "
                "rgbcomp instead.", LogColor.SALMON)
            return None

    def _rgbcomp(self, chan: dict, out_path: str, in_dir: str,
                 lum: str) -> str | None:
        """Compose with Siril's `rgbcomp`, the fallback and the LRGB path.

        rgbcomp does NOT honour quoted paths the way cd / load / save do,
        so a space in the folder name splits the filename.  The way around
        it is to `cd` into the folder holding the masters and pass bare,
        space-free basenames with a relative -out; helper files reached
        through `..` work the same way.
        """
        def rel(path: str) -> str:
            return os.path.relpath(path, in_dir)

        args = ["rgbcomp"]
        if lum:
            args.append(f"-lum={rel(lum)}")
        args += [rel(chan["red"]), rel(chan["green"]), rel(chan["blue"]),
                 f"-out={rel(out_path)}"]
        try:
            self._cmd("cd", f'"{in_dir}"')
            self._emit("  " + " ".join(args), LogColor.BLUE)
            self._cmd(*args)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(f"  rgbcomp failed: {exc}", LogColor.RED)
            return None
        result = out_path + self._ext
        if os.path.exists(result):
            self._compose_how = "with `rgbcomp`"
            self._emit(f"  Colour composite -> {os.path.basename(result)}",
                       LogColor.GREEN)
            return result
        self._emit("  rgbcomp produced no output file.", LogColor.RED)
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
        if palette in _NB_PALETTES:
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
            # Which line sits in which colour channel is exactly what
            # the palette table says -- so a new palette cannot be added
            # with the wrong wavelengths sent to SPCC.  The bandwidth is
            # looked up by LINE for the same reason it is entered that
            # way: HOO maps OIII to two channels, and both must carry
            # that one filter's passband.
            bws = self._opts.get("nb_bandwidths") or {}

            def _bw(role: str) -> float:
                return float(bws.get(role) or DEFAULT_NB_BANDWIDTH)

            rr, gg, bb = _NB_PALETTES[palette]
            args += ["-narrowband",
                     f"-rwl={_LINE_NM[rr]:g}", f"-gwl={_LINE_NM[gg]:g}",
                     f"-bwl={_LINE_NM[bb]:g}",
                     f"-rbw={_bw(rr):g}", f"-gbw={_bw(gg):g}",
                     f"-bbw={_bw(bb):g}"]
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

    def _photometry_planned(self, palette: str) -> bool:
        """Will a *photometric* colour calibration actually run?

        The distortion-aware solve exists to serve one, and costs seconds
        on a palette where `_colour_calibrate` gives up before measuring a
        single star.  It lives next to that method so the two cannot drift:
        the palettes named here are the ones it refuses outright, and a
        narrowband palette with SPCC switched off leaves no attempt at all,
        because PCC assumes broadband star colours.
        """
        if palette == "HaRGB" or palette in _MIX_PALETTES:
            return False
        return bool(self._opts.get("use_spcc", True)
                    or palette not in _NB_PALETTES)

    def _colour_calibrate(self, palette: str) -> None:
        """Colour-calibrate the loaded composite, best method first.

        The chain degrades one step at a time and never aborts the finish:
        SPCC with sensor/filter details -> bare SPCC (Siril's configured
        defaults) -> PCC -> PCC against a local Gaia catalog -> give up and
        say so.  HaRGB is excluded from photometric methods entirely: its
        Red channel carries blended Ha, so the star colours are no longer
        physical.
        """
        if palette == "HaRGB" or palette in _MIX_PALETTES:
            why = ("the Red channel carries blended Ha"
                   if palette == "HaRGB" else
                   "each channel is a weighted mixture of two emission "
                   "lines, which no single passband describes")
            self._finish_steps.append(
                f"Colour calibration skipped ({palette}: {why}, so star "
                "photometry is invalid) — balance the colour manually.")
            self._emit(
                f"  Finish: colour calibration skipped for {palette} "
                f"({why}); balance the channels manually.", LogColor.BLUE)
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

        narrowband = palette in _NB_PALETTES
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
                "ratio that was flattened on purpose. Switch it off while "
                "calibrating."
                + (" 'Output normalization' rescales each master by its "
                   "own min and max as well, so the line ratio is not "
                   "untouched either way — switch that off too if you "
                   "want SPCC to see the physical one."
                   if self._opts.get("output_norm", True) else ""),
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
            before = self._log_snapshot()
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
            self._read_spcc_fit(before, label, cmd[0])
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

    def _subsky(self, where: str, narrowband: bool = False) -> str:
        """Run subsky on the loaded image; return what was used, for the log.

        RBF models a gradient that changes direction across the frame far
        better than a first-degree polynomial, which is why it is offered
        for the finished masters and the composite.  It is NOT offered for
        the individual subs: Siril's guidance is a degree-1 polynomial
        there, and that is what seqsubsky keeps doing.

        `narrowband` says the image is line emission, which is the one
        case where RBF is the WRONG choice: emission fills the frame, and
        a model flexible enough to follow a gradient that changes
        direction is flexible enough to follow the nebula.  Measured, it
        keeps 18% of it where the degree-1 polynomial keeps 99.9% (see
        RBF_NARROWBAND_KEPT).  It is said rather than overridden -- the
        setting is the user's, and switching their model out from under
        them would change images without being asked.

        Falls back to the polynomial if RBF is refused, so an older build
        cannot cost the user the background extraction altogether.
        """
        if self._opts.get("bg_rbf", False):
            smooth = float(self._opts.get("bg_smooth", 50)) / 100.0
            if narrowband and where not in self._rbf_warned:
                self._rbf_warned.add(where)
                self._emit(
                    f"  This {where} is line emission, and RBF cannot tell "
                    "nebulosity from gradient: measured on a nebula filling "
                    f"95% of the frame it keeps about "
                    f"{RBF_NARROWBAND_KEPT:.0%} of it, where the degree-1 "
                    f"polynomial keeps {POLY1_NARROWBAND_KEPT:.0%}. The "
                    "gradient does come out cleaner — but on a target this "
                    "size most of what it removes is your signal. Untick "
                    "'use RBF instead of a polynomial' for narrowband.",
                    LogColor.SALMON)
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

    def _bg_extract_master(self, path: str, filt: str = "") -> None:
        """Background-extract a single linear per-filter master, in place."""
        ext = self._ext
        base = path[:-len(ext)] if path.lower().endswith(ext.lower()) else path
        nb = _filter_role(filt) in _LINE_NM if filt else False
        try:
            self._cmd("load", f'"{path}"')
            how = self._subsky("master", narrowband=nb)
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
        background extraction and colour calibration.
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
        # An inherited solution is astrometry the image ALREADY carries.
        # `solved` therefore starts from that fact, not from the outcome
        # of the call below: a platesolve that refuses an image which is
        # already solved used to set solved=False and skip the colour
        # calibration -- over a WCS that was sitting in the header the
        # whole time.
        solved = inherited
        try:
            self._cmd("platesolve")
            solved = True
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
            if inherited:
                self._finish_steps.append(
                    "Plate-solve was refused, but the composite already "
                    "carried the masters' astrometry (WCS) — colour "
                    "calibration went ahead on that solution.")
                self._emit(
                    f"  Finish: plate-solve was refused ({exc}), but the "
                    "composite already carries the masters' astrometry — "
                    "continuing with colour calibration.", LogColor.BLUE)
            else:
                self._finish_steps.append("Plate-solve failed.")
                self._emit(
                    f"  Finish: plate-solve failed ({exc}); skipping colour "
                    "calibration.", LogColor.SALMON)

        # A WCS and a DISTORTION-AWARE WCS are different facts, and the
        # photometric methods want the second: they measure each catalogue
        # star through the solution, so a linear one is furthest from the
        # truth exactly where the field is widest -- the corners.  Siril
        # says so itself, twice per run: "Found linear plate solve data,
        # you may need to solve your image with distortions to ensure
        # correct calibration of stars near image corners."
        #
        # And linear is what the composite inherits, by construction:
        # `seqapplyreg` undistorts every frame, so the registered frames
        # carry a linear WCS, and the cross-filter alignment on top is a
        # homography with no distortion model at all.  Inheriting a
        # solution is still worth doing -- it is what makes the plate-solve
        # above a no-op -- it is simply not the solution SPCC asked for.
        #
        # `-force` because the image is already solved and Siril would
        # otherwise answer "Nothing will be done"; `-noflip` because a
        # forced solve is allowed to flip an image it reads as upside-down,
        # and the composite has to stay on the masters' grid.
        palette = self._opts.get("compose_palette", "RGB")
        if solved and not _has_sip(path) and self._photometry_planned(palette):
            try:
                self._cmd("platesolve", "-force", "-noflip",
                          f"-order={SPCC_SIP_ORDER}")
                self._finish_steps.append(
                    "Re-solved the composite with distortions (SIP order "
                    f"{SPCC_SIP_ORDER}) — the inherited solution is linear, "
                    "and photometric colour calibration reads star positions "
                    "through it.")
                self._emit(
                    "  Finish: re-solved with distortions (SIP order "
                    f"{SPCC_SIP_ORDER}); the inherited solution was linear, "
                    "which is what the colour calibration warns about.",
                    LogColor.GREEN)
            except (CommandError, DataError, SirilError) as exc:
                self._finish_steps.append(
                    "The distortion-aware solve was refused; colour "
                    "calibration ran on the solution the image still "
                    "carried.")
                self._emit(
                    f"  Finish: distortion-aware solve refused ({exc}); "
                    "continuing with the solution the image still carries.",
                    LogColor.SALMON)

        # Background / gradient extraction on the COMBINED image, before the
        # colour calibration.  Even with per-channel extraction, the freshly
        # combined RGB carries its own residual gradient, and the photometric
        # methods explicitly want a flat background ("correct the image
        # gradient first") -- so this runs regardless of the per-channel pass.
        try:
            how = self._subsky(
                "composite",
                narrowband=bool(_NB_PALETTES.get(
                    self._opts.get("compose_palette", ""))))
            self._finish_steps.append(
                f"Extracted the background gradient (subsky, {how}).")
            self._emit(f"  Finish: composite background extracted ({how}, "
                          "before colour calibration).", LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Finish: composite background extraction skipped ({exc}).",
                LogColor.SALMON)

        if solved:
            self._colour_calibrate(palette)
        else:
            self._finish_steps.append(
                "Colour calibration skipped — the composite could not be "
                "plate-solved, and every method needs astrometry.")

        # SCNR is deliberately NOT run here.  Siril computes it as
        # `green = min(green, 0.5 * (red + blue))` (src/filters/scnr.c),
        # which on an ASSIGNMENT palette clips a real emission line: in
        # SHO the green channel IS Ha, so the strongest measured line gets
        # cut back to the mean of the other two wherever it dominates.  On
        # one M 16 run that was about 3% of Ha on average and far more in
        # the bright pillars.
        #
        # It is also non-linear and per-pixel, so running it would break
        # the one property this whole file promises two steps later: that
        # the composite handed over is still linear.  The manual already
        # argues exactly this for the magenta-star remedy -- inverting
        # linear data is not inverting stretched data -- and the same
        # reasoning applies to plain SCNR.  todo.md owns it, after the
        # stretch, where the user can see what it costs.

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
    def _log_snapshot(self):
        """Siril's whole log right now, or None if it cannot be read.

        `get_siril_log()` returns everything, so a step's own output is
        the DELTA against a snapshot taken just before it.  Optional API:
        an older sirilpy simply yields None and the readers stay quiet.

        It also yields None WITHOUT raising, on two paths inside sirilpy:
        a NONE status, and a response too short to carry the shared-memory
        handle.  Both mean "Siril declined the transfer this time", and
        this used to be laundered into "" by an `or ""` -- which reads
        downstream as a log that was fetched successfully and happens to
        be empty.  `_log_delta` then anchored on an empty string, could
        not find anything in it, and the run reported that the log had
        scrolled past its buffer.  It had not; nothing had been read at
        all.  Siril's log is never empty while a run is in progress, so
        falsy means unreadable, full stop.

        One retry, because a refused transfer is a momentary condition
        rather than a property of the session -- the previous call in the
        same step usually succeeded.  Whether that is enough is not
        something this code can know; what it must not do is guess in the
        message it prints.
        """
        for _attempt in (1, 2):
            try:
                text = self.siril.get_siril_log()
            except Exception as exc:                 # noqa: BLE001
                _log_swallowed(exc)
                return None
            if text:
                return text
        return None

    def _log_delta_or_warn(self, log_before, what: str, scope: str = ""):
        """The step's own log output, or None -- and never in silence.

        Both readers used to give up without a word when the delta could
        not be established, so a diagnostic that had quietly stopped
        working was indistinguishable from one that had nothing to say.

        The message names WHICH of the two things went wrong, because
        they have different causes and only one of them was ever true.
        A single guess ("the log has scrolled past its buffer") was
        printed for both, and on the run that prompted this it was the
        wrong one: the log had not scrolled, it had not been handed over.
        """
        after = self._log_snapshot()
        delta = _log_delta(log_before, after, scope)
        if delta is not None:
            return delta
        # Per diagnostic, not per run.  One shared flag meant the first
        # reader to fail silenced the second one's message as well --
        # and on one run that swallowed an SPCC fit with sigma 5.5/6.7
        # against a limit of 1.0, which is exactly what the user needed
        # to see.
        if what not in self._log_read_warned:
            self._log_read_warned.add(what)
            if after is None:
                why = ("Siril handed back no log at all — the transfer "
                       "was refused, not the log emptied")
            elif log_before is None:
                why = ("the log before this step could not be read, so "
                       "there is nothing to measure this step against")
            else:
                why = ("the log was read, but this step's own lines could "
                       "no longer be isolated in it — it has scrolled past "
                       "what its buffer holds")
            self._emit(
                f"  {what.capitalize()} are not reported: {why}."
                # One phrase, one line: a test asserts this sentence is
                # here, and splitting it across string literals hides it
                # from the only reader that checks the note still reassures.
                " Nothing about the image changes — these are diagnostics.",
                LogColor.SALMON)
        return None

    def _read_spcc_fit(self, log_before, label: str,
                       command: str = "") -> None:
        """Record how well the colour solution fitted, and say it out loud.

        Siril prints the fit and the script used to drop it: the report
        said "colour calibration done" whether the measured star colours
        followed the catalogue closely or scattered wildly around it.
        Both look identical from outside, and Siril's own "imprecise
        solution" warning does not separate them either -- it fired on
        two runs of this data whose sigmas differed by a factor of 40.

        Diagnostic only; nothing downstream reads it.
        """
        # Siril echoes every command it runs, and this one is the first
        # thing the step logs.  The marker comes from the COMMAND that
        # was issued, not from the human label beside it -- the label is
        # free to be reworded, and a marker that quietly stops matching
        # is the failure mode being repaired here.
        delta = self._log_delta_or_warn(
            log_before, "the colour fit",
            scope=f"Running command: {command}" if command else "")
        if delta is None:
            return
        fit = _parse_spcc_fit(delta)
        if not fit:
            return          # format not recognised -- say nothing
        fit["method"] = label
        self._spcc_fit = fit
        sig = fit.get("sigma") or {}
        rel = _spcc_relative_sigma(fit)
        fit["relative_sigma"] = rel
        bits = [f"σ({k}) {v:.3f}" for k, v in sorted(sig.items())]
        if fit.get("stars"):
            bits.append(f"{fit['stars']} stars")
        self._emit("  Colour fit: " + " · ".join(bits), LogColor.BLUE)
        # Judged on sigma/|slope|, not sigma.  Sigma is the scatter of
        # *Image* R/G, so it carries the scale that channel pair happens
        # to be on -- and with `-output_norm` each master was divided by
        # its own brightest pixel, a number with no photometric meaning
        # and a different one in every filter.  Scaling the ratio by k
        # scales the slope and the sigma alike, so the quotient is what
        # a fixed threshold may be compared against.
        worst_key, worst = "", 0.0
        for key, value in sorted((rel or sig).items()):
            if value > worst:
                worst_key, worst = key, value
        if worst > SPCC_SIGMA_LIMIT:
            raw = sig.get(worst_key)
            self._emit(
                f"  The colour solution is weak: {worst_key} scatters by "
                f"{worst:.2f} of its own slope around the catalogue "
                f"prediction (good is well under {SPCC_SIGMA_LIMIT:g})"
                + (f"; Siril printed it as σ {raw:.2f} on the scale the "
                   "channels happen to be on" if raw is not None
                   and rel else "")
                + ". The white balance was still applied — treat it as a "
                "starting point, not a measurement.", LogColor.SALMON)
        if self._opts.get("output_norm", True):
            # Said once, where the numbers are: with output normalisation
            # on, these factors are NOT a property of the sensor.
            self._emit(
                "  Note: 'Output normalization' scaled every channel to "
                "its own brightest pixel before this fit, so the white-"
                "balance factors and slopes above carry that scaling too "
                "— the calibrated image is right, but the numbers are not "
                "a measurement of the filters or the sensor.",
                LogColor.BLUE)

    def _read_align_pairs(self, log_before, index_to_filter: dict,
                          scope: str = "") -> None:
        """Record how many star pairs each channel aligned on.

        Diagnostic only -- it changes nothing about the image.  It makes
        visible the one number that predicts colour fringing at the edges
        and that the script used to throw away: the user had to find it in
        Siril's own log, among several hundred lines.
        """
        # `register` announces the directory it is working in, and the
        # cross-filter alignment is the only step that uses this one --
        # the per-filter registrations run under sequences/<FILTER>.
        delta = self._log_delta_or_warn(
            log_before, "the star-pair counts", scope=scope)
        if delta is None:
            return
        pairs, ref = _parse_align_pairs(delta, index_to_filter)
        if not pairs:
            return          # format not recognised -- say nothing
        self._align_pairs, self._align_ref = pairs, ref
        weak = _align_pairs_warn(pairs)
        shown = ", ".join(f"{f} {pairs[f]}" for f in sorted(pairs))
        self._emit(f"  Alignment matched on: {shown} star pair(s)"
                   + (f"; {ref} was the reference." if ref else "."),
                   LogColor.BLUE)
        if weak:
            # The remedy is worked out from THIS run's palette, not stated
            # as a general rule: the switch it used to name unconditionally
            # is a no-op whenever the composite already reads every filter.
            self._emit(
                "  " + ", ".join(sorted(weak))
                + " aligned on very few stars.  A scale term fitted on "
                "that many "
                "points is carried badly, which shows up as colour fringing "
                "towards the edges.  "
                + _align_ref_advice(self._opts, sorted(pairs), ref or ""),
                LogColor.SALMON)

    def _check_overlay(self, aligned: dict) -> None:
        """Do the aligned channels really describe the same sky pixel?

        The run already checks that they came out the same SIZE
        (`_mixed_grids`) and that the star matcher found enough pairs.
        Neither proves overlay: identical crops can sit pixels apart, and
        a healthy pair count says the fit converged, not that it
        converged on the right solution.  This compares the astrometric
        solutions the masters carry, which is independent of both.

        Expected to be ~0 -- these frames were re-projected onto one
        grid.  A non-zero answer therefore means the assumption the
        composite rests on is not true, and it is said before the
        channels are combined rather than found in the finished colour.
        """
        if len(aligned) < 2:
            return
        result = _overlay_error_px(sorted(aligned.items()))
        if result is None:
            # No warning: a master without a usable solution is "cannot
            # tell", and the run has never promised one.
            return
        worst, who = result
        self._overlay_px = worst
        if worst <= OVERLAY_MAX_PX:
            self._emit(
                f"  Channel overlay verified: worst disagreement "
                f"{worst:.2f} px across {len(aligned)} channel(s).",
                LogColor.GREEN)
            return
        self._emit(
            f"  {who} sits {worst:.1f} px away from the other channels "
            "where their astrometry says the same point should be — they "
            "are the same size but they do not overlay. A composite built "
            "from these will show colour fringes that no colour "
            "calibration can fix. Re-run the alignment, or check that "
            "this master came from THIS run.", LogColor.SALMON)

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
            self._clear_stale_dir(work, "cross-filter alignment")
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
                    self._align_dropped[filt] = (
                        "excluded from the cross-filter alignment — its "
                        "master file was gone by the time alignment ran")
                    continue
                seq_idx += 1
                dst = os.path.join(
                    lights, f"{seq_idx:02d}_{self._tok(filt)}{self._ext}")
                shutil.copy2(path, dst)
                index_to_filter[seq_idx] = filt

            if len(index_to_filter) < 2:
                return {}

            self._note_command(
                f"{len(index_to_filter)} master(s) copied into "
                f"{self._here(lights)} by the script: "
                + ", ".join(f"{i:02d}={f}"
                            for i, f in sorted(index_to_filter.items())))
            self._cmd("cd", f'"{lights}"')
            self._cmd("link", "masters", "-out=../process")
            self._cmd("cd", "../process")
            # Snapshot the log so the registration output can be read back
            # afterwards.  get_siril_log() returns the WHOLE log, so only
            # the delta belongs to this step -- and only if nothing else
            # wrote in between, which the prefix check below verifies.
            log_before = self._log_snapshot()
            self._align_framing_min = False
            try:
                self._cmd("register", "masters", "-2pass")
                # -framing=min (intersection) so every aligned master comes
                # out PIXEL-IDENTICAL in size and free of ragged missing-data
                # edges -- required for direct LRGB / SHO channel combination.
                # (max framing leaves per-channel canvases a few px apart.)
                self._cmd("seqapplyreg", "masters", "-framing=min")
                self._align_framing_min = True
            except (CommandError, DataError, SirilError):
                # Fall back to single-pass global registration.  It knows
                # no -framing=, so nothing here guarantees the shared grid
                # this step exists to produce -- recorded, because the
                # composition guard used to trust "alignment ran" instead
                # of checking the sizes it was promised.
                self._cmd("register", "masters")
                self._emit(
                    "  Alignment: two-pass re-projection was refused; the "
                    "single-pass fallback registered the masters but "
                    "cannot apply -framing=min. The channel sizes are "
                    "checked before composition.", LogColor.SALMON)
            self._read_align_pairs(
                log_before, index_to_filter,
                scope="Checking sequences in the directory: "
                      + os.path.join(work, "process"))

            aligned: dict[str, str] = {}
            for idx, filt in index_to_filter.items():
                src = os.path.join(
                    work, "process", f"r_masters_{idx:05d}{self._ext}")
                if not os.path.exists(src):
                    continue
                # The index map is only as good as Siril's numbering.  The
                # file's own FILTER keyword is independent of it, so ask
                # the frame what it is before writing its name on it: a
                # channel saved under the wrong name is the one error in
                # this whole pipeline that nothing downstream can catch.
                # An unreadable keyword proves nothing and is let through.
                stamped = _fits_filter(src)
                if stamped and self._tok(stamped) != self._tok(filt):
                    self._emit(
                        f"  Alignment: frame {idx} says FILTER={stamped} "
                        f"but was expected to be {filt} — excluding it "
                        "rather than saving a mislabelled channel.",
                        LogColor.RED)
                    self._align_dropped[filt] = (
                        f"excluded during cross-filter alignment — the "
                        f"aligned frame carried FILTER={stamped}, so writing "
                        f"it as {filt} would have mislabelled the channel. "
                        "The full-frame master in masters/ is intact")
                    continue
                out = os.path.join(
                    adir, f"{_safe(self._target)}_{self._tok(filt)}{self._ext}")
                if os.path.exists(out):
                    os.remove(out)
                shutil.copy2(src, out)
                self._verify_outputs([out], f"{filt} alignment")
                aligned[filt] = out
                self._emit(
                    f"  Aligned {filt} -> {os.path.basename(out)}",
                    LogColor.GREEN)

            if aligned:
                self._note_command(
                    "aligned frame(s) copied out by the script, from the "
                    "r_masters_NN Siril wrote, as "
                    + ", ".join(os.path.basename(aligned[f])
                                for f in sorted(aligned)))
            self._check_overlay(aligned)
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
        """Load a master, plate-solve it, and save the WCS back in place.

        A master registered through the plate-solve path already carries a
        solution, and Siril answers "Image is already plate solved. Nothing
        will be done." -- successfully.  Reporting that as "plate-solved"
        credits this step with astrometry it inherited; the header is asked
        first so the log says which of the two happened, the same
        distinction `_finish_composite` makes for the composite.

        The command still runs either way.  Whether an existing solution is
        good enough is Siril's call, not this function's, and skipping on
        the strength of three keywords would be second-guessing it.
        """
        inherited = _has_wcs(path)
        try:
            self._cmd("load", f'"{path}"')
            self._cmd("platesolve")
            # Siril appends its own extension, so strip the existing one --
            # via _fits_ext, which knows the compound forms (.fits.fz ...)
            # and cannot fall out of step with FITS_EXTS.
            ext = _fits_ext(path)
            base = path[:-len(ext)] if ext else path
            self._cmd("save", f'"{base}"')
            if inherited:
                self._emit(
                    f"  {os.path.basename(path)} already carried an "
                    "astrometric solution from registration — nothing to "
                    "solve.", LogColor.BLUE)
            else:
                self._emit(f"  Plate-solved {os.path.basename(path)}",
                           LogColor.GREEN)
        except (CommandError, DataError, SirilError) as exc:
            self._emit(
                f"  Plate-solve of {os.path.basename(path)} failed: {exc}",
                LogColor.SALMON)


def _safe(token: str) -> str:
    """Filesystem-safe version of a filter / target token."""
    keep = "".join(c if (c.isalnum() or c in "-_") else "_" for c in token)
    return keep.strip("_") or "X"


def _cosmetic_args(n_frames: int) -> tuple[list[str], str]:
    """`-cc=dark` arguments for a stack of ``n_frames``, plus a label.

    One threshold for 4 frames and for 190 is the wrong shape: the
    smaller the stack, the less of the detector's own defects the
    rejection downstream can still take out, and the more the cosmetic
    map has to do on its own.  See COSMETIC_TIGHT_MAX_FRAMES.

    ``n_frames`` of 0 means "not known here" and takes the standard
    pair -- never the tighter one, which would then be applied on a
    guess.
    """
    if 0 < n_frames <= COSMETIC_TIGHT_MAX_FRAMES:
        return (["-cc=dark", COSMETIC_COLD_SIGMA, COSMETIC_TIGHT_HOT_SIGMA],
                f"-cc=dark {COSMETIC_COLD_SIGMA} {COSMETIC_TIGHT_HOT_SIGMA}")
    return (["-cc=dark", COSMETIC_COLD_SIGMA, COSMETIC_HOT_SIGMA],
            f"-cc=dark {COSMETIC_COLD_SIGMA} {COSMETIC_HOT_SIGMA}")


def _rejection_args(n: int, enabled: bool) -> tuple[list[str], str]:
    """Pick a stacking rejection algorithm suited to the frame count.

    Sigma-based methods need enough frames to estimate a reliable
    per-pixel distribution; with only a handful of subs they reject poorly
    or over-aggressively.

    The band edges are Cyril Richard's, taken from AMSP (Automatic
    Multi-Session Processing) in the official Siril script repository.  He
    wrote Siril and implemented these algorithms, so his thresholds carry
    more weight than our own reasoning did: adopting them moved GESDT from
    50 frames down to 31, and moved linear fit out of the middle of the
    range to the top, where a long stack gives its trend model enough data
    to work with.  Returns ``(tokens, label)``.

    Source (GPL-3.0-or-later):
    gitlab.com/free-astro/siril-scripts/-/blob/main/preprocessing/AMSP.py
    """
    if not enabled:
        return ["rej", "none"], "no rejection"
    if n <= PERCENTILE_MAX_FRAMES:
        # Percentile clipping -- params are fractions, not sigmas.
        return ["rej", "percentile", "0.2", "0.1"], "percentile 0.2/0.1"
    if n <= SIGMA_MAX_FRAMES:
        # Plain sigma clipping: cheapest thing that works once there are
        # more than a handful, before winsorizing earns its cost.
        return ["rej", "sigma", "3", "3"], "sigma 3/3"
    if n < GESDT_MIN_FRAMES:
        return ["rej", "winsorized", "3", "3"], "winsorized 3/3"
    if n > LINEAR_MIN_FRAMES:
        # Linear fit models a trend ACROSS the stack, so it belongs where
        # the stack is long enough to define one.
        return ["rej", "linear", "5", "4"], "linear fit 5/4"
    # Generalized Extreme Studentized Deviate Test.  Its two parameters are
    # NOT sigmas: the first caps the fraction of the stack that may be
    # rejected, the second is the significance threshold.
    return (["rej", "g", "0.3", "0.05"],
            "GESDT 0.3 max-reject / 0.05 significance")


_SPCC_CACHE: dict = {}


# Below this, a similarity fit (scale + rotation + shift) rests on so few
# points that its scale term stops being trustworthy.  A judgement call,
# not a measurement -- set from what a fit needs, not from a dataset.
ALIGN_PAIRS_FLOOR = 30
# ...and a channel far below the rest of the same run is suspect even when
# it clears the floor: the others prove how many pairs were available.
ALIGN_PAIRS_FRACTION = 0.25


def _log_delta(before, after, scope: str = ""):
    """What was logged between two snapshots, or None if it cannot be told.

    The obvious test -- ``after.startswith(before)`` -- assumes Siril's log
    only ever grows.  It does not: the buffer is bounded, and on a run long
    enough to fill it the oldest lines drop off the front, after which no
    snapshot is a prefix of a later one again.  Both readers then returned
    in silence, which is why the alignment star-pair counts never appeared
    on a full three-filter run and looked like a format the parser did not
    recognise.

    So the delta is found by ANCHORING on the tail of the snapshot instead
    of its head.  That survives a trimmed front, and fails only when the
    step logged more than the whole buffer holds -- in which case the
    honest answer is None and the caller says so out loud.

    ``None`` on either side means "that snapshot could not be read", and
    it propagates: no delta can be derived from a log nobody has.  Callers
    must pass the reader's answer through UNCHANGED -- an `or ""` here
    turns an unreadable log into an empty one, and an empty `after` then
    fails the anchor search for a reason that has nothing to do with the
    buffer.  That is exactly how one run reported a scrolled log while the
    numbers it wanted sat two lines above in Siril's console.

    `scope` is the last resort, and the only path that does not depend on
    the earlier snapshot at all: a line the STEP ITSELF logs before
    anything worth reading.  Everything after its last occurrence is that
    step's output by construction.

    That matters because the two snapshot-based paths have now failed for
    two DIFFERENT reasons on two consecutive runs of the same data -- once
    with an unreadable `after`, once with an `after` that simply did not
    contain the anchor.  Siril's log is not the clean append-only stream
    both paths assume: stderr from other processes lands in it too (a
    relaunched multiprocessing resource tracker wrote a traceback into the
    middle of the very step being measured).  Rather than keep diagnosing
    the buffer, anchor on something this script can point at.
    """
    if after is None:
        return None
    if before is not None:
        if not before:
            return after                # nothing preceded; it is all delta
        if after.startswith(before):
            return after[len(before):]  # the ordinary, cheap case
        anchor = before[-LOG_ANCHOR_CHARS:]
        cut = after.rfind(anchor)
        if cut >= 0:
            return after[cut + len(anchor):]
    if scope:
        cut = after.rfind(scope)
        if cut >= 0:
            return after[cut + len(scope):]
    return None


def _spcc_relative_sigma(fit: dict) -> dict:
    """``{ratio: sigma/|slope|}`` -- the scale-free form of the fit scatter.

    Siril reports sigma in the units of *Image* R/G, which is whatever
    scale the two channels are on.  With `-output_norm` that scale is set
    by each master's brightest pixel, so the same data normalised
    differently produces a different sigma and can fall on either side of
    a fixed threshold.  Dividing by the slope removes it: both are
    proportional to the same factor.

    Ratios whose slope is missing or ~0 are left out rather than guessed
    at -- a slope near zero means the fit found no relationship at all,
    and a quotient by it would be a very large number that says nothing.
    """
    sig, slope = fit.get("sigma") or {}, fit.get("slope") or {}
    out = {}
    for key, value in sig.items():
        k = slope.get(key)
        if k is not None and abs(k) > 1e-6:
            out[key] = value / abs(k)
    return out


def _parse_spcc_fit(delta: str) -> dict:
    """How well the photometric colour solution actually fitted.

    Siril prints the fit and then throws it away as far as this script is
    concerned: the report said "colour calibration done" and nothing about
    whether the solution was worth having.  The numbers that matter are
    the SIGMA of each ratio fit -- how far the measured star colours
    scatter around the ones predicted from catalogue spectra -- the star
    count behind them, and the white-balance factors that came out.

    Read only, never acted on: this changes no pixel.  An unrecognised
    format yields {} and the report stays silent, because a number nobody
    measured is worse than no number.
    """
    out: dict = {}
    for raw in delta.splitlines():
        line = re.sub(r"^\d{2}:\d{2}:\d{2}:\s*", "", raw).strip()
        # The SLOPE is read as well as the sigma, and the two must be
        # used together: sigma is the scatter of *Image* R/G, so it
        # carries whatever scale that channel pair happens to be on --
        # and with `-output_norm` each master was divided by its own
        # brightest pixel, which is not a photometric quantity.  Scaling
        # the ratio by k scales BOTH the slope and the sigma by k, so
        # sigma/slope is the scale-free number and a bare sigma against a
        # fixed threshold is not.
        m = re.match(r"^Image ([RGB])/([RGB]) = \s*([\d.eE+-]+)\s*\+\s*"
                     r"([\d.eE+-]+)\s*\* Catalog [RGB]/[RGB]\s*"
                     r"\(sigma:\s*([\d.eE+-]+)\)", line)
        if m:
            key = f"{m.group(1)}/{m.group(2)}"
            try:
                out.setdefault("sigma", {})[key] = float(m.group(5))
                out.setdefault("slope", {})[key] = float(m.group(4))
                out.setdefault("intercept", {})[key] = float(m.group(3))
            except ValueError:
                pass
            continue
        m = re.match(r"^Found a solution for color calibration using "
                     r"(\d+) stars", line)
        if m:
            out["stars"] = int(m.group(1))
            continue
        m = re.match(r"^(\d+) stars excluded from the calculation", line)
        if m:
            out["excluded"] = int(m.group(1))
            continue
        m = re.match(r"^K(\d):\s*([\d.eE+-]+)$", line)
        if m:
            try:
                out.setdefault("k", {})[int(m.group(1))] = float(m.group(2))
            except ValueError:
                pass
            continue
        if "imprecise solution" in line:
            out["imprecise"] = True
    # The white-balance block is printed TWICE, before and after
    # renormalisation, and the second one is what was applied.  Keeping
    # the last of each key is enough; the dict already does that.
    return out if out.get("sigma") or out.get("k") else {}


def _parse_align_pairs(delta: str, index_to_filter: dict) -> tuple:
    """Star-pair counts per channel from Siril's registration output.

    Siril reports, for the cross-filter alignment, which image it chose as
    the reference and how many star pairs each other image matched against
    it.  That count is the best early warning for colour fringing at the
    edges: a scale term fitted on twelve points is carried badly, and on
    one M 16 run the twelve-pair channel produced an SPCC R/G sigma of
    5.76 against 2.73 for the same data aligned among its own kind.

    Returns ``(pairs, reference_filter)``.  Anything unparseable yields an
    empty dict -- the report then says nothing, because a number nobody
    measured is worse than no number.
    """
    pairs, ref, pending = {}, None, None
    for raw in delta.splitlines():
        line = re.sub(r"^\d{2}:\d{2}:\d{2}:\s*", "", raw).strip()
        m = re.match(r"^.*choosing image (\d+) as new reference", line)
        if m:
            ref = index_to_filter.get(int(m.group(1)))
            continue
        m = re.match(r"^Matching stars in image (\d+):", line)
        if m:
            pending = index_to_filter.get(int(m.group(1)))
            continue
        m = re.match(r"^Initial pair matches:\s*(\d+)", line)
        if m and pending:
            pairs[pending] = int(m.group(1))
            pending = None
    return pairs, ref


def _align_pairs_warn(pairs: dict) -> set:
    """Channels whose alignment rests on too few stars.

    Two rules, because either alone misses a real case: an absolute floor
    (a fit needs points regardless of what the run achieved elsewhere) and
    a relative one (a channel far below its siblings had the stars
    available and still did not match them -- the spectral mismatch this
    is meant to catch).

    The relative rule compares against the median, so it assumes MOST
    channels aligned well.  When the majority is weak the median is weak
    too and only the floor fires -- which is the other reason the floor
    exists.
    """
    if not pairs:
        return set()
    mid = _median(list(pairs.values()))
    return {f for f, n in pairs.items()
            if n < ALIGN_PAIRS_FLOOR or n < mid * ALIGN_PAIRS_FRACTION}


def _spcc_names_via_command(siril, what: str) -> set:
    """Ask Siril itself for an SPCC name list, via ``spcc_list``.

    The JSON tables are the primary source -- reading them costs nothing
    and stays out of the user's log.  This is the fallback for a packaged
    build (Flatpak / Snap / Store) where the database is somewhere the
    path guesses cannot reach: `spcc_list` is Siril's own answer and
    therefore always right, but it PRINTS the whole list, so it is only
    worth those log lines when the cheap route already failed.

    The output is a header line naming the list followed by one name per
    line, so the header is dropped and the rest kept.  Read back through
    get_siril_log(), which returns the entire log -- hence the snapshot
    and the delta.  Returns an empty set on any failure: "cannot ask" is
    never "the name is invalid".
    """
    try:
        before = siril.get_siril_log()
        siril.cmd("spcc_list", what)
        after = siril.get_siril_log()
    except Exception as exc:
        _log_swallowed(exc)
        return set()
    # Through `_log_delta`, not `startswith`: this was the third place
    # making the same wrong assumption -- that Siril's log only grows.
    # Its buffer is bounded, and once the front has been trimmed no
    # earlier snapshot is a prefix again, after which the name check
    # silently reported "database not found" for the rest of the session.
    #
    # And NOT `or ""` on either snapshot.  get_siril_log() returns None
    # without raising when Siril declines the transfer; turning that into
    # "" claims a successful read of an empty log, and an empty log is
    # something this function can never legitimately see while it is the
    # thing writing to it.  `_log_delta` refuses a None outright.
    delta = _log_delta(before, after)
    if delta is None:
        return set()
    names, header_seen = set(), False
    for raw in delta.splitlines():
        line = re.sub(r"^\d{2}:\d{2}:\d{2}:\s*", "", raw).strip()
        if not line or line.startswith("Running command"):
            continue
        if not header_seen:          # "Mono Sensors", "Red Filters", ...
            header_seen = True
            continue
        names.add(line)
    return names


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

    The retry is WINSORIZED, the band immediately below GESDT.  It used to
    be linear fit, which contradicted both callers' own comments ("retry
    with the tier below") and `_rejection_args`: GESDT covers 31-300
    frames, and linear fit is the band ABOVE it, reserved for >300 because
    that is where a trend across the stack has enough points to be modelled.
    Handing a 35-frame stack to linear fit was reaching past the answer in
    the wrong direction; winsorized is what `_rejection_args` itself gives
    the frames just short of GESDT, and every Siril that refuses `g` knows
    it.
    """
    if tokens[:2] != ["rej", "g"]:
        return None
    return ["rej", "winsorized", "3", "3"], "winsorized 3/3"


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


# Narrowband palettes are pure channel ASSIGNMENTS: which emission line
# feeds Red, Green and Blue.  One table drives the mapping, the dropdown,
# the "which filter does this channel want" message and the manuals, so a
# palette cannot exist in one of them and be missing from another.
#
# The set beyond SHO / HOO is Cyril Richard's, from PalettePicker in the
# official Siril script repository (adapted there from Seti Astro Suite
# Pro).  Assignments carry over to LINEAR data unchanged -- they move
# pixels between channels without arithmetic.
_NB_PALETTES = {
    "SHO": ("sii", "ha", "oiii"),      # Hubble
    "HOO": ("ha", "oiii", "oiii"),     # bicolour
    "HSO": ("ha", "sii", "oiii"),
    "HOS": ("ha", "oiii", "sii"),
    "OSS": ("oiii", "sii", "sii"),
    "OHH": ("oiii", "ha", "ha"),
    "OSH": ("oiii", "sii", "ha"),
    "OHS": ("oiii", "ha", "sii"),
    "SOH": ("sii", "oiii", "ha"),
    "HSS": ("ha", "sii", "sii"),
    "HHO": ("ha", "ha", "oiii"),
    "OOS": ("oiii", "oiii", "sii"),
    "SHH": ("sii", "ha", "ha"),
    "SOO": ("sii", "oiii", "oiii"),
}

# Weighted palettes MIX the lines instead of assigning them.  A weighted
# sum is linear, so these are the only mixed palettes that mean the same
# thing before and after a stretch -- see `_compose_planes`.  Foraxx and
# the other dynamic palettes are deliberately absent: their blend factor
# is t**(1-t) with t = Ha*OIII, and on linear data t is ~1e-6, which
# collapses the whole expression to zero.  They belong in a post-stretch
# tool, and PalettePicker is that tool.
_MIX_PALETTES = {
    "Realistic1": {"red": {"ha": 0.5, "sii": 0.5},
                   "green": {"ha": 0.3, "oiii": 0.7},
                   "blue": {"oiii": 0.9, "ha": 0.1}},
    "Realistic2": {"red": {"ha": 0.7, "sii": 0.3},
                   "green": {"sii": 0.3, "oiii": 0.7},
                   "blue": {"oiii": 1.0}},
}

# The emission line each narrowband role stands for, in nanometres.
_LINE_NM = {"ha": HA_NM, "oiii": OIII_NM, "sii": SII_NM}

# Short forms for the help tables, where "an Ha filter" reads as noise.
_ROLE_LABEL = {"ha": "Ha", "oiii": "OIII", "sii": "SII", "red": "R",
               "green": "G", "blue": "B", "lum": "L"}

def _nb_line_targets(palette: str) -> dict:
    """Which colour channels each emission line feeds, for this palette.

    SHO gives ``{"ha": "G", "oiii": "B", "sii": "R"}``; HOO puts the same
    OIII filter in two, ``{"ha": "R", "oiii": "G, B", "sii": ""}``.  An
    empty string means the palette does not use that line.

    Line-first on purpose.  Bandwidth is a property of the FILTER, not of
    the channel: HOO sends one OIII passband to both `-gbw` and `-bbw`,
    and per-channel boxes -- which is how Siril's own dialog does it --
    would let one filter be given two different widths.  Read from
    `_NB_PALETTES`, the table `_spcc_args` builds its command line from,
    so the panel cannot describe a mapping the run will not use.
    """
    roles = _NB_PALETTES.get(palette) or ()
    return {line: ", ".join(ch for ch, role in zip("RGB", roles)
                            if role == line)
            for line in _LINE_NM}


_ROLE_WORDS = {"ha": "an Ha filter", "oiii": "an OIII filter",
               "sii": "an SII filter", "red": "a Red filter",
               "green": "a Green filter", "blue": "a Blue filter",
               "lum": "a Luminance filter"}


def _is_nb_palette(palette: str) -> bool:
    """True for every palette built from emission lines.

    Both kinds qualify: the assignments and the weighted mixes.  What
    separates them is only how a channel is filled, and everything that
    asks this question -- narrowband normalisation, the synthetic
    luminance, the magenta-star note -- cares about the lines, not about
    the arithmetic.  SPCC is the exception and tests `_NB_PALETTES`
    directly: a mixed channel has no single passband to model.
    """
    return palette in _NB_PALETTES or palette in _MIX_PALETTES


def _palette_roles(palette: str) -> set:
    """Every emission line a palette reads, mixed channels included."""
    if palette in _NB_PALETTES:
        return set(_NB_PALETTES[palette])
    return {r for chans in _MIX_PALETTES.get(palette, {}).values()
            for r in chans}


def _mix_words(mix: dict) -> str:
    """"70% of an Ha filter + 30% of an SII filter" -- for the UI."""
    return " + ".join(
        f"{share:.0%} of {_ROLE_WORDS.get(role, role)}"
        for role, share in mix.items())


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
}
_PALETTE_SOURCE.update({
    name: dict(zip(("red", "green", "blue"),
                   (_ROLE_WORDS[r] for r in roles)))
    for name, roles in _NB_PALETTES.items()})
_PALETTE_SOURCE.update({
    name: {ch: _mix_words(mix) for ch, mix in chans.items()}
    for name, chans in _MIX_PALETTES.items()})

# Every palette the UI offers, in the order it offers them.
PALETTES = (["Auto", "LRGB", "RGB", "HaRGB"]
            + list(_NB_PALETTES) + list(_MIX_PALETTES))


def _unfillable_channels(filters: list, palette: str) -> list:
    """Colour channels this palette cannot fill from these filters.

    Answers the question before a run rather than after it: the filter
    list is known as soon as the folder is analysed, so choosing SHO
    without an SII filter can be reported immediately instead of after
    stacking, aligning and plate-solving everything.
    """
    if palette in _MIX_PALETTES:
        # The dropdown shows one source per channel, so a channel can look
        # filled while a line it mixes in is missing.  Judging by the
        # weights instead is what keeps the pre-run answer and the run
        # itself from disagreeing -- the failure mode HaRGB had.
        return [ch for ch in ("red", "green", "blue")
                if any(not _first_with_role(list(filters), role)
                       for role in _MIX_PALETTES[palette][ch])]
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
    if palette in _MIX_PALETTES:
        # A mixed channel reads every line its weights name, and the
        # dropdown can only show one of them.  Leaving the others out
        # here would let "stack only the filters this palette uses" skip
        # a master the composite then asks for.
        for role in _palette_roles(palette):
            used.add(_first_with_role(filters, role) or "")
    used.discard("")
    return {f for f in filters if f in used}


def _align_ref_advice(opts: dict, filters: list, ref: str) -> str:
    """What to actually suggest when a channel aligned on few stars.

    Siril picks the alignment reference itself, so the only lever the
    script has is which masters are in the sequence at all -- and that
    lever exists only when the composite leaves a filter out.  Naming
    "Stack only the filters this palette uses" unconditionally sent the
    user to a switch that, under HaRGB, cannot change a thing: that
    palette reads L, R, G and B through the dropdowns and Ha by role, so
    every discovered filter is already one of its own and the option
    would drop nothing.  Worse, the reference is then one of the
    composite's own channels already -- the few pairs are the narrowband
    master being shallower, not a bad choice of anchor.
    """
    here = [f for f in dict.fromkeys(list(filters) + [ref]) if f]
    if opts.get("palette_only", False):
        return ("Only this palette's own channels were stacked, so the "
                "reference pool is already as small as that switch makes "
                "it — what is left is the gap in star count between a "
                "narrowband master and the broadband one it matched.")
    if not opts.get("compose", False):
        return ("Siril picks the reference itself from whatever is in the "
                "sequence, and the switch that would shrink that pool — "
                "'Stack only the filters this palette uses' — needs a "
                "colour composite to have a palette to go by.")
    wanted = _palette_filters(opts, here)
    if not wanted:
        # The option refuses on exactly this condition, so it is no
        # remedy here -- and claiming the palette reads every filter
        # would be the opposite of what an unrecognised mapping means.
        return ("Siril picks the reference itself from whatever is in the "
                "sequence, and 'Stack only the filters this palette uses' "
                "— the switch that would shrink that pool — cannot help "
                "while the channel mapping names none of the discovered "
                "filters.")
    spare = [f for f in here if f not in wanted]
    if spare:
        return ("Siril picks the reference itself from whatever is in the "
                "sequence, so a narrowband channel matching a broadband "
                "reference is the usual cause — 'Stack only the filters "
                "this palette uses' would leave " + ", ".join(spare)
                + " out of that pool and keep the reference among the "
                "channels that end up in the picture.")
    return ("Every filter of this run is one the composite reads, so there "
            "is no master to leave out of the reference pool"
            + (f" and {ref} is itself one of them" if ref else "")
            + ": a narrowband master matched against a broadband one shows "
            "fewer stars whatever the settings say.  Only more exposure on "
            "the weak channel moves this number.")


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
    elif palette in _NB_PALETTES:
        for ch, role in zip(("red", "green", "blue"),
                            _NB_PALETTES[palette]):
            m[ch] = _first_with_role(filters, role)
    elif palette in _MIX_PALETTES:
        # A mixed channel has no single source filter.  The dropdown shows
        # the dominant one so the UI is not blank, but composition reads
        # the weights, not the dropdown -- exactly as HaRGB finds its Ha.
        for ch, mix in _MIX_PALETTES[palette].items():
            lead = max(mix.items(), key=lambda kv: kv[1])[0]
            m[ch] = _first_with_role(filters, lead)
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
        # [(feature, missing calls, consequence)] for optional Siril calls
        # this module does not have; reported once and carried into the
        # run so output.md can say why a step took the simpler route.
        self._missing_api: list = []
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
        # path -> observing night, filled by the analysis from each frame's
        # own DATE-OBS.  The previews and the run both read it through
        # `_night_of`, so they cannot disagree about which night a frame
        # belongs to.
        self._nights: dict = {}

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
        self.setStyleSheet(_window_stylesheet())
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
            "font-size: 15pt; font-weight: bold; "
            f"color: {_tc('accent')}; margin-top: 5px;")
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
        self.lbl_folder.setStyleSheet(_hint_style())
        layout.addWidget(self.lbl_folder)

        # Picking a folder analyses it, so this button is only ever the
        # repeat -- naming it "Analyze Folder" made two stacked buttons
        # look like two steps of a sequence, one of which had already run.
        self.btn_analyze = QPushButton("Re-scan Folder")
        _nofocus(self.btn_analyze)
        self.btn_analyze.setToolTip(
            "Read every FITS header again and regroup the LIGHT frames by "
            "filter.  Selecting a folder already does this; use it after "
            "adding frames or changing the Library.")
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_analyze.setEnabled(False)
        layout.addWidget(self.btn_analyze)

        parent_layout.addWidget(group)

    @staticmethod
    def _new_table(headers: list) -> QTableWidget:
        """A read-only table built the way all three of them are built.

        The lights, the flats and the darks are three views of one scan,
        and a user comparing them should not have to notice that they were
        written at different times.  The last column stretches; the rest
        take the width their content needs.
        """
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hdr = tbl.horizontalHeader()
        for i in range(len(headers) - 1):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(len(headers) - 1,
                                 QHeaderView.ResizeMode.Stretch)
        return tbl

    def _build_filters_group(self, parent_layout: QVBoxLayout) -> None:
        """Everything the SESSION produced: lights, and the flats beside them.

        One box, because they come from the same nights and the same
        folder -- a flat belongs to the session that shot the lights, and
        is never taken from the library.  The darks and bias, which are
        library material reused across sessions, are the box below.

        The target sits in the title rather than on a line of its own:
        the box is about one target, and a label repeating it underneath
        was a second place to keep in step.

        Both flat switches sit UNDER their table.  The table is what the
        eye reads first -- it is the finding -- and the switches are what
        you do about it; put above, they separated the lights table from
        the flats table it has nothing to do with.
        """
        self.grp_discovered = QGroupBox(DISCOVERED_TITLE + "—")
        group = self.grp_discovered
        layout = QVBoxLayout(group)

        self.tbl_filters = self._new_table(
            ["Filter", "Lights", "Nights", "Integration", "Details"])
        self._fit_table_height()
        layout.addWidget(self.tbl_filters)

        # Carries the Details column's value while every filter shares it.
        self.lbl_uniform = QLabel("")
        self.lbl_uniform.setStyleSheet(_hint_style())
        self.lbl_uniform.setVisible(False)
        layout.addWidget(self.lbl_uniform)


        self.tbl_flats = self._new_table(
            ["Filter", "Flats", "Dark-Flats", "Offset", "Nights"])
        self._fit_table_height(self.tbl_flats)
        layout.addWidget(self.tbl_flats)

        self.lbl_flats_none = QLabel(
            "Analyze a folder to see the flats found next to the lights.")
        self.lbl_flats_none.setWordWrap(True)
        self.lbl_flats_none.setStyleSheet(_hint_style())
        layout.addWidget(self.lbl_flats_none)

        self.chk_use_flats = QCheckBox("Use flats and dark-flats")
        self.chk_use_flats.setChecked(True)
        self.chk_use_flats.setToolTip(
            "Divide the lights by the master flat:  Lc = (L − D) / (F − O).\n"
            "Corrects vignetting and dust shadows.  The dark-flat (or bias) "
            "is the flat's own offset and follows this switch — it exists "
            "only to calibrate the flats.\n"
            "Off: no flat master is stacked at all, and the lights keep "
            "their vignetting.")
        _nofocus(self.chk_use_flats)
        self.chk_use_flats.toggled.connect(self._on_calib_kind_toggled)
        layout.addWidget(self.chk_use_flats)

        self.chk_flats_by_date = QCheckBox("Match flats to the same night")
        self.chk_flats_by_date.setChecked(False)
        self.chk_flats_by_date.setToolTip(
            "OFF: all flats of a filter are pooled into one master — correct "
            "for a permanently mounted rig, and less noisy.\n"
            "ON: every night gets its OWN master flat, and that night's "
            "lights are divided by it. The calibrated nights are merged "
            "again before registration, so the filter still ends as one "
            "master.\n"
            "Pick this when the optical train was touched between nights — "
            "the log measures how far the nights disagree and says so.\n"
            "A night whose flats are missing falls back to a pooled master, "
            "and the log names it.")
        _nofocus(self.chk_flats_by_date)
        # It changes the flats table directly -- how many masters, from
        # which nights -- so that table has to be redrawn with it.
        self.chk_flats_by_date.toggled.connect(self._on_calib_kind_toggled)
        layout.addWidget(self.chk_flats_by_date)

        parent_layout.addWidget(group)

    def _build_calibration_group(self, parent_layout: QVBoxLayout) -> None:
        # Named for what it now holds.  Flats moved out to their own group
        # above; what is left is the material that comes from the library
        # and is reused across sessions.
        group = QGroupBox("Calibration with Darks and Bias")
        layout = QVBoxLayout(group)

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
        self.lbl_library.setStyleSheet(_hint_style())
        layout.addWidget(self.lbl_library)

        self.chk_use_darks = QCheckBox("Use darks and bias")
        self.chk_use_darks.setChecked(True)
        self.chk_use_darks.setToolTip(
            "Subtract the master dark from the lights, and use the master "
            "bias where no dark applies:  Lc = (L − D) / (F − O).\n"
            "Removes dark current, hot pixels and amp glow.  Bias reaches "
            "the lights only when no dark does — a master dark already "
            "carries the offset.\n"
            "Off: no dark or bias master is stacked, and cosmetic "
            "correction has nothing to read.")
        _nofocus(self.chk_use_darks)
        self.chk_use_darks.toggled.connect(self._on_calib_kind_toggled)
        layout.addWidget(self.chk_use_darks)

        self.tbl_darks = self._new_table(
            ["Type", "Frames", "Exposure", "Details", "Applies to"])
        self._fit_table_height(self.tbl_darks)
        layout.addWidget(self.tbl_darks)

        # Sits under the table it qualifies: a filter with no matching dark
        # has no row up there, and silence is the one thing that must not
        # stand for "nothing is wrong".
        self.lbl_dark_gap = QLabel("")
        self.lbl_dark_gap.setWordWrap(True)
        self.lbl_dark_gap.setStyleSheet(
            f"color:{_tc('warn')};font-size:9pt;")
        self.lbl_dark_gap.setVisible(False)
        layout.addWidget(self.lbl_dark_gap)

        self.chk_cosmetic = QCheckBox("Cosmetic correction (hot pixels)")
        self.chk_cosmetic.setChecked(True)
        self.chk_cosmetic.setToolTip(
            "Adds -cc=dark, which finds hot/cold pixels from the master "
            "dark's statistics and repairs them.\n"
            "Needs a matching dark — without one this has no effect.\n"
            f"A channel of {COSMETIC_TIGHT_MAX_FRAMES} frames or fewer is "
            "corrected harder (hot threshold "
            f"{COSMETIC_TIGHT_HOT_SIGMA} instead of {COSMETIC_HOT_SIGMA}): "
            "stacking rejection cannot take a hot pixel out of that few "
            "dithered frames, so the map has to.")
        _nofocus(self.chk_cosmetic)
        layout.addWidget(self.chk_cosmetic)


        # Last, because it describes the result of every switch above it.
        # It used to sit over them, so flipping a box rewrote a sentence
        # the eye had already left behind.
        self.lbl_calib_found = QLabel("Analyze a folder to see what is found.")
        self.lbl_calib_found.setWordWrap(True)
        self.lbl_calib_found.setStyleSheet(
            f"color:{_tc('accent')};font-size:9pt;")
        layout.addWidget(self.lbl_calib_found)

        parent_layout.addWidget(group)

    def _on_filter_mode_changed(self, mode: str) -> None:
        """Make the quality-filter spin boxes mean what the mode says.

        '% best' takes 1..100 (share of frames kept), 'k-sigma' takes a
        sigma multiple where anything past ~5 already rejects nothing.  A
        value left over from the other mode is replaced by that mode's
        sensible default rather than silently reinterpreted.

        The reset follows the MODE SWITCH, not the range.  Keying it on
        "the old value no longer fits" only ever fired in one direction:
        90 % does not fit 1..10, so % -> k-sigma reset correctly, while
        k-sigma -> % left a 3 sitting in a box now labelled "3 %" -- a
        filter that keeps the best three percent of the frames.  On a
        200-frame set that is six survivors, and `_quality_filter_args`
        emits it happily because six clears MIN_STACK_FRAMES; on a short
        set the same value falls under the floor and the filter silently
        does nothing at all.  Both readings are wrong, and neither is
        what the box says.
        """
        k_sigma = mode == "k-sigma"
        hi, default = (10, 3) if k_sigma else (100, 90)
        previous = getattr(self, "_filter_mode_applied", None)
        self._filter_mode_applied = mode
        # None means this is the constructor's own call: there is no
        # previous mode to have carried a value over from, and the
        # defaults already belong to the mode being set.
        changed = previous is not None and previous != mode
        for spin in getattr(self, "_filter_spins", ()):
            # Range first: Qt clamps the current value into the new range,
            # so setting the value afterwards is what actually sticks.
            spin.setRange(1, hi)
            if changed:
                spin.setValue(default)
            spin.setSuffix(" σ" if k_sigma else " %")
        # This also runs once during construction, before the Log tab
        # exists -- and there is nothing to report at that point anyway.
        # It is also silenced while stored settings or a preset are being
        # applied: the mode arrives first (it sets the ranges), the real
        # values right after, so what gets "reset" here is only the
        # constructor defaults.  On every startup with k-sigma stored,
        # this line used to claim the user's values "were percentages"
        # a moment before their actual sigmas were restored.
        if (changed and hasattr(self, "log_text")
                and not getattr(self, "_applying_preset", False)
                and not getattr(self, "_restoring_settings", False)):
            self._log(
                f"Filter mode is now '{mode}' — the values were reset to "
                f"{default}{'σ' if k_sigma else '%'}; they were percentages."
                if k_sigma else
                f"Filter mode is now '{mode}' — the values were reset to "
                f"{default}%; they were sigma multiples.", LogColor.BLUE)

    def _calibration_on(self) -> bool:
        """Is any calibration going to happen?

        There used to be a third switch above these two, "Apply
        calibration when frames exist".  Every one of its four gates was
        about darks, flats or bias, so it said exactly what these two say
        together -- and it could contradict them: off with both of these
        on was a reachable state in which the panel showed two armed
        switches and the run calibrated nothing.  The answer is derived
        now, so it cannot disagree with the boxes it is derived from.
        """
        return self.chk_use_flats.isChecked() or self.chk_use_darks.isChecked()

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
            "frame count: percentile (≤4), sigma (5–10), winsorized "
            "(11–30), GESDT (31–300), linear fit above.  Recommended.\n\n"
            "Applies to the light stacks.  Master flats, darks and bias "
            "are always rejected — through the same bands — because one "
            "cosmic left in a master reaches every light it calibrates.")
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
        lbl_f.setStyleSheet(f"color:{_tc('accent')};margin-top:4px;")
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
            "Rescales the finished master into [0, 1].  On 32-bit output "
            "Siril does this as (x − min) / (max − min) using that "
            "master's OWN extremes, so it is an affine transform per "
            "channel, not a shared one.\n"
            "Harmless for a picture. Switch it OFF when the absolute "
            "levels matter — SPCC on narrowband, or any photometry — "
            "because each filter is then scaled by two numbers that come "
            "from its own darkest and brightest pixel.")
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
        self.cmb_palette.addItems(PALETTES)
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
        self.lbl_ha.setToolTip(
            "How strongly the Ha master is mixed into the Red channel: "
            "(R + k·Ha) / (1+k), a weighted sum.  0% is plain R, 100% "
            "is an even mix of R and Ha — never more Ha than R, and "
            "never a channel thrown away.\n\n"
            "A weighted sum, not the screen blend up to 1.7.9, because "
            "the screen blend is NON-LINEAR (its R·Ha cross term "
            "compresses the bright end by ~27% at typical values) and "
            "every composite this script writes is handed over "
            "linear.\n\n"
            "Ha does not appear in the four channel dropdowns because it "
            "does not replace a channel — HaRGB keeps the ordinary "
            "R/G/B/L mapping and mixes Ha into Red on top of it.  The Ha "
            "master is found automatically by filter role; the Log names "
            "which one it picked.")
        self.row_ha.addWidget(self.lbl_ha)
        self.spin_ha = QSpinBox()
        self.spin_ha.setRange(0, 100)
        self.spin_ha.setSingleStep(10)
        self.spin_ha.setValue(50)
        self.spin_ha.setSuffix(" %")
        self.spin_ha.setToolTip(
            "HaRGB only: how strongly the Ha master is mixed into the "
            "Red channel.  0% = plain RGB, 100% = R and Ha in equal "
            "parts.  A weighted sum, so the result stays linear.")
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

        self.chk_synth_lum = QCheckBox("Build a synthetic luminance master")
        self.chk_synth_lum.setChecked(False)
        self.chk_synth_lum.setToolTip(
            "Narrowband only, and only when there is no Luminance filter: "
            "averages the emission-line masters into "
            "masters/TARGET_SynthL.fit.\n"
            "The average is UNWEIGHTED: a strong Ha averaged with a much "
            "fainter SII can come out worse than the Ha alone.  Compare "
            "it against your strongest channel before building on it.\n"
            "It is NOT combined into the colour image here. A luminance "
            "combine belongs after the stretch — todo.md walks you "
            "through it — and doing it linearly is the same mistake as "
            "'Quick linear LRGB'.")
        _nofocus(self.chk_synth_lum)
        layout.addWidget(self.chk_synth_lum)

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
        self.lbl_spcc.setStyleSheet(_hint_style())
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

        # Which half of this panel is live follows the PALETTE, not a
        # switch of its own -- see _refresh_spcc_mode for why.
        self.lbl_spcc_bb = QLabel("     Broadband filter names:")
        self.lbl_spcc_bb.setStyleSheet(_hint_style())
        self.lbl_spcc_bb.setWordWrap(True)
        layout.addWidget(self.lbl_spcc_bb)

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

        self.lbl_spcc_nb = QLabel("")
        self.lbl_spcc_nb.setStyleSheet(_hint_style())
        self.lbl_spcc_nb.setWordWrap(True)
        layout.addWidget(self.lbl_spcc_nb)

        # One row per emission LINE, not per colour channel.  Bandwidth
        # belongs to the FILTER: HOO maps OIII to both G and B, and the
        # one filter has one passband -- per-channel boxes (which is how
        # Siril's own dialog does it) would let it be given two widths.
        # Fractional values are the norm, not the exception: 3.5, 4.5 and
        # 6.5 nm are all common specs, so an integer box would make them
        # unenterable.
        self._nb_bw: dict = {}
        self.lbl_nb_line: dict = {}
        for _role in _LINE_NM:
            _row = QHBoxLayout()
            _lab = QLabel("")
            _lab.setStyleSheet(_hint_style())
            _lab.setMinimumWidth(260)
            self.lbl_nb_line[_role] = _lab
            _row.addWidget(_lab)
            _sp = QDoubleSpinBox()
            _sp.setDecimals(1)
            _sp.setSingleStep(0.5)
            _sp.setRange(0.5, 50.0)
            _sp.setValue(DEFAULT_NB_BANDWIDTH)
            _sp.setSuffix(" nm")
            _sp.setFixedWidth(85)
            _sp.setToolTip(
                f"The bandwidth of your {_ROLE_LABEL[_role]} filter, used "
                "by SPCC's narrowband mode.  Typical values are 3, 3.5, "
                "4.5, 6 or 7 nm — take it from the spec sheet.  "
                "Pre-filled with 4.5 for the Antlia Edge set.\n"
                "Siril has no named entries for narrowband filters, so "
                "this number plus the fixed line wavelength "
                f"({_ROLE_LABEL[_role]} {_LINE_NM[_role]:g} nm) IS the "
                "whole filter description.\n"
                "Entered per line rather than per channel because that is "
                "what it describes: a palette that maps one line to two "
                "channels sends this same number to both.")
            _nofocus(_sp)
            self._nb_bw[_role] = _sp
            _row.addWidget(_sp)
            _row.addStretch()
            layout.addLayout(_row)
        # Named attributes as well: the preset export maps a settings key
        # to one widget and type-switches on it.
        (self.spin_nb_bw_ha, self.spin_nb_bw_oiii,
         self.spin_nb_bw_sii) = (self._nb_bw["ha"], self._nb_bw["oiii"],
                                 self._nb_bw["sii"])

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
            "filter_mode": self.cmb_filter_mode,
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
            if isinstance(w, QComboBox):
                w.currentTextChanged.connect(self._mark_custom_preset)
            elif isinstance(w, QCheckBox):
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
            "use_flats": self.chk_use_flats,
            "use_darks": self.chk_use_darks,
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
            "nb_bw_ha": self.spin_nb_bw_ha,
            "nb_bw_oiii": self.spin_nb_bw_oiii,
            "nb_bw_sii": self.spin_nb_bw_sii,
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
            "synth_lum": self.chk_synth_lum,
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
                if key == "calibrate":
                    # The master switch this key named is gone; the two
                    # kind switches say the same thing.  Only the OFF case
                    # carries information -- "on" is what they already are
                    # unless the file also names them.
                    if not value:
                        self.chk_use_flats.setChecked(False)
                        self.chk_use_darks.setChecked(False)
                    applied += 1
                    continue
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
            self._on_calib_kind_toggled()
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
        """Set every option a preset defines (without tripping 'Custom').

        The combo boxes go FIRST, because one of them is the quality-filter
        mode and that decides the spin boxes' range: a percentage applied
        into a k-sigma range is clamped to 10, and the preset then silently
        arms a filter that rejects nothing.  Same ordering rule as
        `_load_settings`, for the same reason.
        """
        preset = PRESETS.get(name)
        if not preset:
            return
        widgets = self._preset_widgets()
        self._applying_preset = True
        try:
            ordered = sorted(
                preset.items(),
                key=lambda kv: 0 if isinstance(widgets.get(kv[0]), QComboBox)
                else 1)
            for key, value in ordered:
                w = widgets.get(key)
                if isinstance(w, QComboBox):
                    w.setCurrentText(str(value))
                elif isinstance(w, QCheckBox):
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
        for w in (self.lbl_spcc, self.edit_spcc_sensor):
            w.setEnabled(spcc)
        # The sensor applies in both modes; everything below it does not.
        self._refresh_spcc_mode()

    def _refresh_spcc_mode(self) -> None:
        """Enable only the half of the SPCC panel the palette actually uses.

        Which mode applies is not a choice the user makes: `_spcc_args`
        sends filter NAMES for a broadband palette and WAVELENGTHS for a
        narrowband one, and the palette alone decides which.  A separate
        "narrowband" checkbox here would be a second place to disagree
        with that table.

        Until now the block was enabled as a whole, so a SHO run showed
        three filled-in RGB filter boxes that the run then ignored -- and
        said so only in the Log, after the start.  The same class of
        defect as a message naming the wrong cause: the panel stated
        something that was not true for the chosen palette.

        Greying rather than hiding, for the reason the calibration tables
        already do it: a field that vanishes raises the question whether
        the setting still exists.

        "Auto" leaves both halves live.  Which one will apply is not
        knowable before the filters are found, and guessing here would be
        the same mistake one step earlier.
        """
        palette = self.cmb_palette.currentText()
        spcc = self.chk_spcc.isEnabled() and self.chk_spcc.isChecked()
        nb = palette in _NB_PALETTES
        auto = palette == "Auto"
        for w in (self.lbl_spcc_bb, self.edit_spcc_r, self.edit_spcc_g,
                  self.edit_spcc_b):
            w.setEnabled(spcc and (auto or not nb))
        self.lbl_spcc_nb.setEnabled(spcc and (auto or nb))
        # A line the palette does not use greys out on its own: with HOO
        # there is no SII filter in the recipe, so asking for its
        # bandwidth would be asking about equipment this run never reads.
        targets = _nb_line_targets(palette)
        for _role, _sp in self._nb_bw.items():
            _live = spcc and (auto or nb) and (bool(targets[_role]) or not nb)
            _sp.setEnabled(_live)
            _lab = self.lbl_nb_line[_role]
            _lab.setEnabled(_live)
            if nb and not targets[_role]:
                _lab.setText(f"        {_ROLE_LABEL[_role]} — not used "
                             f"by {palette}")
            else:
                _arrow = f"  →  {targets[_role]}" if nb else ""
                _lab.setText(f"        {_ROLE_LABEL[_role]} "
                             f"{_LINE_NM[_role]:g} nm{_arrow}")
        self.lbl_spcc_bb.setText(
            f"     Broadband filter names — not used by {palette}:"
            if nb else "     Broadband filter names:")
        if nb:
            self.lbl_spcc_nb.setText(
                f"     Narrowband — {palette} calibrates by wavelength, "
                "not by filter name:")
        elif auto:
            self.lbl_spcc_nb.setText(
                "     Narrowband — applies only once the filters found "
                "give a narrowband palette.")
        else:
            self.lbl_spcc_nb.setText(
                f"     Narrowband — not used by {palette}.")

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
        # The palette decides which half of the SPCC panel is live.
        self._refresh_spcc_mode()

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
        # Ha is what makes HaRGB HaRGB, but it is blended into Red rather
        # than mapped to a channel -- so the check above, which only looks
        # at R/G/B, cannot notice that it is missing.  Without this, the
        # run would go all the way through and quietly produce plain RGB.
        if (palette == "HaRGB" and self.chk_compose.isChecked()
                and not _first_with_role(filters, "ha")):
            self._log(
                "HaRGB has no Ha filter to blend — none of the discovered "
                "filters carries an Ha role, so the run would compose plain "
                "RGB and name the file accordingly.  Ha is mixed into Red "
                "at the strength above; it is not one of the four channel "
                "dropdowns.", LogColor.SALMON)
        elif palette == "HaRGB" and self.chk_compose.isChecked():
            self._log(
                f"HaRGB will blend {_first_with_role(filters, 'ha')} into "
                "Red — Ha is an admixture, not a mapped channel, which is "
                "why it has no dropdown of its own.", LogColor.BLUE)

    def _build_output_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        self.lbl_out = QLabel("Output: <target folder>/output")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet(_hint_style())
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
        self.lbl_status.setStyleSheet(
            f"color: {_tc('hint')}; font-size: 9pt;")
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
    def _attach_spcc_completers(self) -> None:
        """Offer Siril's own SPCC names while the user types.

        The fields stay free text on purpose -- clearing them means "use
        Siril's own SPCC configuration", and a name from a Siril version
        whose database differs from this one must remain typeable.  A
        completer adds discovery without taking that away, which an
        editable combo box would not: the preset loader drops a combo
        value it cannot find in the list, and a hand-entered filter name
        would vanish on the next load.

        Names come from the JSON tables, which cost nothing to read and
        stay out of the user's log.  Only when that finds nothing -- a
        packaged build whose database the path guesses cannot reach -- is
        `spcc_list` asked, because it prints the whole list into the log.
        """
        hint = self._spcc_root()
        pairs = ((self.edit_spcc_sensor, "mono_sensors", "monosensor"),
                 (self.edit_spcc_r, "mono_filters", "redfilter"),
                 (self.edit_spcc_g, "mono_filters", "greenfilter"),
                 (self.edit_spcc_b, "mono_filters", "bluefilter"))
        asked = False
        for widget, table, list_arg in pairs:
            names = _spcc_catalog(table, hint)
            if not names and self.siril is not None:
                names = _spcc_names_via_command(self.siril, list_arg)
                asked = asked or bool(names)
            if not names:
                continue
            comp = QCompleter(sorted(names), widget)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            comp.setCompletionMode(
                QCompleter.CompletionMode.UnfilteredPopupCompletion)
            widget.setCompleter(comp)
        if asked:
            self._log(
                "SPCC name lists read from Siril via spcc_list — the local "
                "database was not where this script looks.  That is what "
                "the lines above are.", LogColor.BLUE)

    def _spcc_root(self) -> str:
        """Siril's own data directory, or "" if it will not say."""
        try:
            return str(self.siril.get_siril_userdatadir() or "")
        except Exception as exc:
            _log_swallowed(exc)
            return ""

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
                         ("nb_bw_ha", DEFAULT_NB_BANDWIDTH),
                         ("nb_bw_oiii", DEFAULT_NB_BANDWIDTH),
                         ("nb_bw_sii", DEFAULT_NB_BANDWIDTH)):
            st.setValue(key, val)
        st.setValue("spcc_seeded", True)

    def _load_settings(self) -> None:
        # The stored filter MODE is applied before the stored values
        # (it sets the spin ranges), and the mode handler must not
        # announce a "reset" of what are only constructor defaults
        # about to be overwritten -- see _on_filter_mode_changed.
        self._restoring_settings = True
        try:
            st = self._settings
            self._seed_rig_defaults()
            self._attach_spcc_completers()
            self.chk_skip_blank.setChecked(
                st.value("skip_blank", True, type=bool))
            self.chk_rejection.setChecked(
                st.value("rejection", True, type=bool))
            self.chk_weighting.setChecked(
                st.value("weighting", True, type=bool))
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
            # One box became three in 1.7.16.  A settings file written
            # before that has only the old key, so it seeds all three --
            # the value the user last entered, not a default that would
            # silently change what their next run sends.
            _legacy = float(st.value("nb_bandwidth", DEFAULT_NB_BANDWIDTH))
            self.spin_nb_bw_ha.setValue(float(st.value("nb_bw_ha", _legacy)))
            self.spin_nb_bw_oiii.setValue(
                float(st.value("nb_bw_oiii", _legacy)))
            self.spin_nb_bw_sii.setValue(
                float(st.value("nb_bw_sii", _legacy)))
            # Mode BEFORE the values: it decides the spin boxes' range, and a
            # percentage restored into a k-sigma range would be clamped to 10.
            self.cmb_filter_mode.setCurrentText(
                str(st.value("filter_mode", "% best")))
            self.spin_keep.setValue(int(st.value("f_wfwhm_val", 90)))
            self.chk_f_wfwhm.setChecked(
                st.value("f_wfwhm_on", False, type=bool))
            self.chk_f_round.setChecked(
                st.value("f_round_on", False, type=bool))
            self.spin_f_round.setValue(int(st.value("f_round_val", 90)))
            self.chk_f_stars.setChecked(
                st.value("f_stars_on", False, type=bool))
            self.spin_f_stars.setValue(int(st.value("f_stars_val", 90)))
            self.chk_f_bkg.setChecked(st.value("f_bkg_on", False, type=bool))
            self.spin_f_bkg.setValue(int(st.value("f_bkg_val", 90)))
            self.chk_disto.setChecked(
                st.value("disto_master", False, type=bool))
            self.chk_cleanup.setChecked(
                st.value("cleanup_work", False, type=bool))
            self.chk_output_norm.setChecked(
                st.value("output_norm", True, type=bool))
            self.chk_rejmap.setChecked(st.value("rejmap", False, type=bool))
            self.chk_crop_edges.setChecked(
                st.value("crop_edges", True, type=bool))
            self.chk_palette_only.setChecked(
                st.value("palette_only", False, type=bool))
            self.chk_bg_master.setChecked(
                st.value("bg_master", True, type=bool))
            self.chk_bg_extract.setChecked(
                st.value("bg_extract", False, type=bool))
            self.chk_platesolve_reg.setChecked(
                st.value("platesolve_reg", False, type=bool))
            self.chk_copy.setChecked(st.value("copy", False, type=bool))
            self.chk_align_filters.setChecked(
                st.value("align_filters", True, type=bool))
            self.chk_platesolve_master.setChecked(
                st.value("platesolve_master", False, type=bool))
            # A settings file written before the master switch was
            # removed can still say "calibrate": false.  Honouring the two
            # new keys alone would turn calibration back ON for anyone who
            # had switched it off -- silently, on the next start.
            legacy_off = not st.value("calibrate", True, type=bool)
            self.chk_use_flats.setChecked(
                False if legacy_off
                else st.value("use_flats", True, type=bool))
            self.chk_use_darks.setChecked(
                False if legacy_off
                else st.value("use_darks", True, type=bool))
            self.chk_cosmetic.setChecked(st.value("cosmetic", True, type=bool))
            self.chk_flats_by_date.setChecked(
                st.value("flats_by_date", False, type=bool))
            self._set_library(str(st.value("calib_library", "")))
            self._on_calib_kind_toggled()
            self.chk_reuse.setChecked(
                st.value("reuse_masters", False, type=bool))
            self.chk_load_result.setChecked(
                st.value("load_result", True, type=bool))
            self.chk_clear_log.setChecked(
                st.value("clear_log", True, type=bool))
            # Restore the preset label last: the individual options above were
            # already restored, so just reflect what was saved (no re-apply).
            self.cmb_preset.setCurrentText(str(st.value("preset", "Balanced")))
            self.cmb_drizzle.setCurrentText(str(st.value("drizzle", "Off")))
            self.chk_compose.setChecked(st.value("compose", True, type=bool))
            self.cmb_palette.setCurrentText(str(st.value("palette", "Auto")))
            self.chk_nb_norm.setChecked(
                st.value("nb_normalize", True, type=bool))
            self.chk_synth_lum.setChecked(
                st.value("synth_lum", False, type=bool))
            self.chk_quick_lrgb.setChecked(
                st.value("quick_lrgb", False, type=bool))
            self.spin_ha.setValue(int(st.value("ha_strength", 50)))
            self._on_palette_changed()
            self.chk_finish.setChecked(st.value("finish", True, type=bool))
            self.chk_finish_stretch.setChecked(
                st.value("finish_stretch", False, type=bool))
            self._on_compose_toggled(self.chk_compose.isChecked())
            last = str(st.value("last_folder", ""))
            if last and os.path.isdir(last):
                self._set_root(last)
        finally:
            self._restoring_settings = False

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
        st.setValue("nb_bw_ha", float(self.spin_nb_bw_ha.value()))
        st.setValue("nb_bw_oiii", float(self.spin_nb_bw_oiii.value()))
        st.setValue("nb_bw_sii", float(self.spin_nb_bw_sii.value()))
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
        # Still written, so an older build of this script reading these
        # settings keeps behaving as the two switches say.
        st.setValue("calibrate", self._calibration_on())
        st.setValue("use_flats", self.chk_use_flats.isChecked())
        st.setValue("use_darks", self.chk_use_darks.isChecked())
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
        st.setValue("synth_lum", self.chk_synth_lum.isChecked())
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
        self._nights = {}
        self._multi_target = []
        self.tbl_filters.setRowCount(0)
        self._refresh_flats_table()
        self._refresh_darks_table()
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

    def _flat_offset_preview(self) -> list:
        """``[(filter, flats, exposure, offset)]`` -- what the run WOULD use.

        The same rule `_flat_offset_for` applies at run time, evaluated on
        the scan alone: no file is read, nothing is stacked.  With a panel
        setting the flat exposure per filter, "is there something to
        offset-correct MY flats with" is the question the calibration
        panel has to answer before the run, not after it.
        """
        flats = (self._calib or {}).get(KIND_FLAT) or {}
        out = []
        for filt in sorted(flats):
            grp = flats[filt]
            want = float((grp.get("info") or {}).get("exp_s") or 0.0)
            label, _grp = self._flat_offset_pick(filt)
            out.append((filt, len(grp["files"]), want, label))
        return out

    def _flat_offset_pick(self, filt: str):
        """``(label, group)`` — what will offset-correct this filter's flats.

        The same order `_flat_offset_for` applies at run time: a real
        DARK-FLAT set for this filter, then a DARK set at the flat
        exposure, then the bias, then Siril's synthetic offset.

        The GROUP is returned as well as the label, because a table that
        only had the label could not say how much material is behind it.
        The second case is the one that matters: a dark at the flat
        exposure IS a dark-flat, whatever IMAGETYP calls it, and reading
        the keyword instead of applying this rule made a filter with 160
        usable frames look as though it had none.
        """
        c = self._calib or {}
        grp = (c.get(KIND_FLAT) or {}).get(filt)
        if not grp:
            return "—", None
        info = grp.get("info") or {}
        want = float(info.get("exp_s") or 0.0)
        df = (c.get(KIND_DARKFLAT) or {}).get(filt)
        if df and _signature_matches(
                dict(df.get("info") or {}, exp_s=info.get("exp_s")), info):
            return "dark-flat", df
        # The same rule the run applies, camera state included -- a
        # preview that promised a match the run then refuses would be
        # worse than no preview.
        near = [g for g in (c.get(KIND_DARK) or {}).values()
                if (g.get("info") or {}).get("exp_s")
                and want > 0
                and abs(float(g["info"]["exp_s"]) - want) / want
                <= DARKFLAT_EXPOSURE_TOLERANCE
                and _signature_matches(
                    dict(g["info"], exp_s=info.get("exp_s")), info)]
        if near:
            best = min(near, key=lambda g: abs(float(g["info"]["exp_s"])
                                               - want))
            return f"{float(best['info']['exp_s']):g}s dark", best
        bias = c.get(KIND_BIAS) or {}
        if bias:
            return "bias", bias[sorted(bias, key=_sig_sort_key)[0]]
        return "synthetic", None

    def _refresh_filter_table(self) -> tuple:
        """Draw the Discovered Lights table; return (lights, seconds).

        Lights only: what was shot, per filter.  What those frames will
        be GIVEN is two tables further down, each next to the switch that
        decides it — the Calibration column that used to sit here had to
        be redrawn whenever one of those switches moved, and still could
        not say which half of the answer the user had just changed.
        """
        filters = sorted(self._groups.keys())
        self.tbl_filters.setRowCount(len(filters))
        total_lights = 0
        total_exp = 0.0
        details = []
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
            details.append(detail)
            # The observing nights these lights came from -- noon-to-noon,
            # so a session running past midnight counts once.  Named while
            # there are few enough to read; beyond that the count is the
            # fact worth having, and the tooltip keeps the dates.
            nights = sorted((g.get("dates") or set()))
            n_text = (", ".join(_short_nights(nights))
                      if 0 < len(nights) <= NIGHTS_NAMED
                      else (f"{len(nights)} nights" if nights else "—"))
            self.tbl_filters.setItem(r, 0, QTableWidgetItem(filt))
            self.tbl_filters.setItem(r, 1, QTableWidgetItem(str(n)))
            item = QTableWidgetItem(n_text)
            if nights:
                item.setToolTip("\n".join(nights))
            self.tbl_filters.setItem(r, 2, item)
            self.tbl_filters.setItem(
                r, 3, QTableWidgetItem(_format_duration(exp_total)))
            self.tbl_filters.setItem(r, 4, QTableWidgetItem(detail))

        # A column that repeats one value per row spends width on nothing.
        # It moves under the table until a run actually mixes exposures,
        # gains or setpoints -- which is exactly when it earns its place.
        uniform = details[0] if details and len(set(details)) == 1 else ""
        # Details was the stretching section.  Hiding it left its share of
        # the width belonging to nobody, so the table ended in a blank
        # panel -- the stretch has to move to whatever column is last.
        hdr = self.tbl_filters.horizontalHeader()
        keep, drop = (3, 4) if uniform else (4, 3)
        hdr.setSectionResizeMode(drop, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(keep, QHeaderView.ResizeMode.Stretch)
        self.tbl_filters.setColumnHidden(4, bool(uniform))
        self.lbl_uniform.setText(f"All filters: {uniform}" if uniform else "")
        self.lbl_uniform.setVisible(bool(uniform))
        self._fit_table_height()
        return total_lights, total_exp

    def _fit_table_height(self, tbl=None) -> None:
        """Give the table the height its rows need, and no more.

        A fixed minimum left a hand's width of empty grid under a
        three-filter run, pushing everything below it off the panel.
        Capped, because a filter wheel with more slots than the cap is
        better scrolled than allowed to fill the window.
        """
        tbl = tbl or self.tbl_filters
        rows = tbl.rowCount()
        shown = min(max(rows, 1), FILTER_TABLE_MAX_ROWS)
        vh = tbl.verticalHeader()
        # The rows' OWN heights, not sizeHintForRow: the hint is the
        # content's ideal and ignores the grid line and cell padding, so
        # three rows came out a row and a half short -- with a scroll bar
        # over a table that had nothing to scroll.
        body = (sum(vh.sectionSize(i) for i in range(shown)) if rows
                else vh.defaultSectionSize())
        tbl.setFixedHeight(tbl.horizontalHeader().height() + body
                           + 2 * tbl.frameWidth())

    @staticmethod
    def _fill_table(tbl, rows: list, off: bool) -> None:
        """Put `rows` into `tbl`; grey the lot when the switch is off.

        The last element of a row is its tooltip, not a column.
        """
        tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            tip = row[-1]
            for col, text in enumerate(row[:-1]):
                item = QTableWidgetItem(str(text))
                item.setToolTip(tip)
                if off:
                    # Switched off is not a defect, so it is not a warning
                    # colour -- but a table that looks identical either way
                    # is how "found" came to be read as "used".
                    item.setForeground(QColor("#888888"))
                tbl.setItem(r, col, item)

    def _refresh_flats_table(self) -> None:
        """Draw the Flats and Dark-Flats table and its note."""
        on = self.chk_use_flats.isChecked()
        rows = self._flat_rows() if self._groups else []
        self._fill_table(self.tbl_flats, rows, not on)
        self.tbl_flats.setVisible(bool(rows))
        self._fit_table_height(self.tbl_flats)
        if not self._groups:
            note = "Analyze a folder to see the flats found next to the lights."
        elif not rows:
            note = ("No flats or dark-flats found next to the lights. "
                    "Vignetting and dust shadows will stay in every channel.")
        elif not on:
            note = ("Flats and dark-flats are switched off — found, listed, "
                    "and not applied.")
        else:
            note = ""
        self.lbl_flats_none.setText(note)
        self.lbl_flats_none.setVisible(bool(note))

    def _refresh_darks_table(self) -> None:
        """Draw the darks-and-bias table and the missing-dark note."""
        on = self.chk_use_darks.isChecked()
        rows = self._dark_rows() if self._groups else []
        self._fill_table(self.tbl_darks, rows, not on)
        self.tbl_darks.setVisible(bool(rows))
        self._fit_table_height(self.tbl_darks)
        gaps = self._dark_gaps() if (self._groups and on) else []
        if gaps:
            first = gaps[0][1]
            names = ", ".join(f for f, _ in gaps)
            self.lbl_dark_gap.setText(
                f"⚠ No dark for {names} — {first}")
        elif self._groups and on and not rows:
            self.lbl_dark_gap.setText(
                "⚠ No darks or bias reach these lights.")
        else:
            self.lbl_dark_gap.setText("")
        self.lbl_dark_gap.setVisible(bool(self.lbl_dark_gap.text()))

    def _on_calib_kind_toggled(self, _on: bool = False) -> None:
        """Either kind switch moved: both tables state what changed.

        Both, not just the one that moved: the bias is listed under the
        darks and is also the flats' offset, so switching the darks off
        changes what the flats row says as well.

        The dependent controls follow their OWN kind, which the removed
        master switch could not do -- it greyed all of them together, so
        "Match flats to the same night" went dead because the darks were
        unusable.
        """
        darks, flats = (self.chk_use_darks.isChecked(),
                        self.chk_use_flats.isChecked())
        # The library holds darks and bias; cosmetic correction reads a
        # master dark's statistics.  Neither means anything without them.
        for w in (self.btn_library, self.btn_library_clear,
                  self.chk_cosmetic):
            w.setEnabled(darks)
        self.chk_flats_by_date.setEnabled(flats)
        self._refresh_flats_table()
        self._refresh_darks_table()
        if self._groups:
            self._show_calib_summary(quiet=True)
            self._refresh_filter_table()

    def _count_from(self, files: list, where: str) -> int:
        """How many of these frames sit inside the library ("lib") or
        beside the lights ("near").

        Path-based rather than recorded at discovery, because discovery
        pools both sources into one group the moment they share a camera
        state -- which is the point of a library, and also the reason
        the counts alone could not tell the user whether picking one had
        done anything.
        """
        lib = self._library
        root = (os.path.normpath(lib) + os.sep) if lib else ""
        inside = (0 if not root else
                  sum(1 for f in files
                      if os.path.normpath(f).startswith(root)))
        return inside if where == "lib" else len(files) - inside

    def _dark_preview(self, filt: str) -> tuple:
        """``(applies, note)`` — will this filter's lights get a dark?

        Mirrors the run exactly: `_signature_matches` first, then the one
        loosened dimension `_closest_dark` allows, the exposure, inside
        DARK_EXPOSURE_TOLERANCE.  Everything else — camera, gain,
        binning, size, temperature — still has to agree.

        The note is written for the case that matters most: a library
        full of darks that fit nothing.  "442 darks" reads like the
        lights are dark-corrected; naming the exposures says why they
        are not.
        """
        sig, note = self._dark_for_filter(filt)
        return sig is not None, note

    @staticmethod
    def _calib_detail(info: dict) -> str:
        """Gain and setpoint of a calibration set, for the Details column."""
        bits = []
        gain = info.get("gain_v")
        if gain is not None:
            bits.append(f"gain {gain:g}" if isinstance(gain, (int, float))
                        else f"gain {gain}")
        temp = info.get("temp_v")
        if temp is not None:
            bits.append(f"{float(temp):g} °C")
        binning = info.get("binning")
        if binning and binning != 1:
            bits.append(f"bin {binning}")
        return ", ".join(bits) or "—"

    def _flat_files(self, filt: str):
        """``(files, per_night, lit)`` — the flats this filter WILL use.

        The restriction "Match flats to the same night" applies, in one
        place, so the count in the table, the nights beside it and the
        tooltip cannot drift apart.
        """
        grp = ((self._calib or {}).get(KIND_FLAT) or {}).get(filt)
        if not grp:
            return [], {}, set()
        files = grp["files"]
        lit = set((self._groups.get(filt) or {}).get("dates") or [])
        # The identical rule the run uses, called on the run's own code --
        # a preview that promised a per-night split the run then refuses
        # would be worse than no preview.
        per_night = (StackWorker._flats_per_night(grp, lit, self._nights)
                     if self.chk_flats_by_date.isChecked() else {})
        if per_night:
            files = [p for n in per_night for p in per_night[n]]
        elif self.chk_flats_by_date.isChecked() and lit:
            kept = [p for p in files if _night_of(p, self._nights) in lit]
            if kept:
                files = kept
        return files, per_night, lit

    def _flat_rows(self) -> list:
        """Rows for the Flats and Dark-Flats table.

        ``(filter, flats, dark-flats, offset, nights, tooltip)``, one per
        filter that has either -- a filter with neither has nothing to
        show and would only pad the table with dashes.
        """
        c = self._calib or {}
        flats, dflats = c.get(KIND_FLAT) or {}, c.get(KIND_DARKFLAT) or {}
        offsets = dict((f, off) for f, _n, _e, off
                       in self._flat_offset_preview())
        rows = []
        for filt in sorted(self._groups):
            fg, dg = flats.get(filt), dflats.get(filt)
            if not fg and not dg:
                continue
            if fg:
                text, tip = self._flats_cell(filt)
                files, _pn, _lit = self._flat_files(filt)
                nights = ", ".join(
                    sorted({_night_of(p, self._nights) or "?" for p in files}))
                # The set that will be STACKED as this filter's dark-flat,
                # which is not always the one IMAGETYP labels DARKFLAT: a
                # dark at the flat exposure does the job and is what the
                # run reaches for.  Reading the keyword instead left this
                # column empty for a session holding 160 usable frames,
                # while the Offset column beside it named them.
                label, off_grp = self._flat_offset_pick(filt)
                if off_grp is not None and label != "bias":
                    n_df = len(off_grp.get("files") or [])
                    df_exp = float((off_grp.get("info") or {}).get("exp_s")
                                   or 0.0)
                    df_text = (f"{n_df} × {df_exp:g}s" if n_df and df_exp
                               else (str(n_df) if n_df else "—"))
                    if label != "dark-flat":
                        tip += (f"\nThe dark-flat is a {label} set — a dark "
                                "at the flat exposure IS a dark-flat, "
                                "whatever IMAGETYP calls it, and it carries "
                                "that exposure's dark current, which a bias "
                                "does not.")
                else:
                    df_text = "—"
                    tip += ("\nNo dark-flat and no dark at the flat "
                            "exposure: the flats are offset-corrected with "
                            f"the {label} offset.")
            else:
                text, tip, nights = "—", (
                    f"Dark-flats for {filt} but no flats to apply them to — "
                    "a dark-flat only ever calibrates a flat."), "—"
                n_df = len(dg.get("files") or []) if dg else 0
                df_exp = float((dg.get("info") or {}).get("exp_s") or 0.0) \
                    if dg else 0.0
                df_text = (f"{n_df} × {df_exp:g}s" if n_df and df_exp
                           else (str(n_df) if n_df else "—"))
            rows.append((filt, text, df_text, offsets.get(filt, "—"),
                         nights or "—", tip))
        return rows

    def _dark_for_filter(self, filt: str):
        """``(signature, note)`` — the dark set these lights will get.

        The single place the rule lives: `_signature_matches` first, then
        the one loosened dimension `_closest_dark` allows, the exposure,
        inside DARK_EXPOSURE_TOLERANCE.  Everything else -- camera, gain,
        binning, size, temperature -- still has to agree.  `None` when
        nothing fits, with a note that says why.
        """
        darks = (self._calib or {}).get(KIND_DARK) or {}
        info = (self._groups.get(filt) or {}).get("info") or {}
        want = float(info.get("exp_s") or 0.0)
        if not darks:
            return None, ("No darks in the library — dark current, hot "
                          "pixels and amp glow stay in this channel.")
        for sig, grp in darks.items():
            if _signature_matches(grp.get("info") or {}, info):
                return sig, f"Dark: {len(grp.get('files') or [])} frame(s)."
        best = None
        for sig, grp in darks.items():
            d = grp.get("info") or {}
            have = d.get("exp_s")
            if not have or not want:
                continue
            # Judge everything BUT the exposure, then the exposure alone.
            if not _signature_matches(dict(d, exp_s=want), info):
                continue
            share = abs(float(have) - want) / want
            if share <= DARK_EXPOSURE_TOLERANCE and (
                    best is None or share < best[0]):
                best = (share, sig, float(have), len(grp.get("files") or []))
        if best:
            return best[1], (f"Dark: closest set at {best[2]:g}s against "
                             f"{want:g}s lights ({best[0] * 100:.0f}% off), "
                             f"{best[3]} frame(s).")
        have = sorted({float((g.get("info") or {}).get("exp_s") or 0.0)
                       for g in darks.values()})
        total = sum(len(g.get("files") or []) for g in darks.values())
        return None, (
            f"{total} dark(s) in the library, at "
            + ", ".join(f"{e:g}s" for e in have if e)
            + f" — none matches {want:g}s lights (or the camera state "
              "differs). They will NOT be dark-corrected. A set at "
            + (f"{want:g}s" if want else "the light exposure")
            + " with the same gain and temperature would fix this.")

    def _dark_rows(self) -> list:
        """Rows for the darks-and-bias table: only what reaches the lights.

        ``(type, frames, exposure, details, applies to, tooltip)``.  A
        library is meant to grow, and listing all fifteen signatures of a
        well-stocked one would bury the two this run will open.  Bias is
        listed because it always does something: it reaches lights no
        dark covers, and where a dark covers them all it is still the
        flats' offset.
        """
        c = self._calib or {}
        darks = c.get(KIND_DARK) or {}
        serves: dict = {}
        for filt in sorted(self._groups):
            sig, _note = self._dark_for_filter(filt)
            if sig is not None:
                serves.setdefault(sig, []).append(filt)
        rows = []
        for sig in sorted(serves, key=_sig_sort_key):
            grp = darks[sig]
            info = grp.get("info") or {}
            exp = float(info.get("exp_s") or 0.0)
            n = len(grp.get("files") or [])
            rows.append(("Dark", str(n), f"{exp:g}s" if exp else "—",
                         self._calib_detail(info),
                         ", ".join(serves[sig]),
                         "\n".join(self._dark_for_filter(f)[1]
                                    for f in serves[sig][:1])))
        bias = c.get(KIND_BIAS) or {}
        if bias:
            key = sorted(bias, key=_sig_sort_key)[0]
            grp = bias[key]
            info = grp.get("info") or {}
            n = len(grp.get("files") or [])
            uncovered = [f for f in sorted(self._groups)
                         if self._dark_for_filter(f)[0] is None]
            exp = float(info.get("exp_s") or 0.0)
            rows.append((
                "Bias", str(n), f"{exp:g}s" if exp else "—",
                self._calib_detail(info),
                ", ".join(uncovered) if uncovered else "flats' offset only",
                "Bias reaches the lights only where no dark does — a master "
                "dark already carries the offset. It is always available as "
                "the flats' own offset."
                + (f"  {len(bias)} bias sets found; the first is used."
                   if len(bias) > 1 else "")))
        return rows

    def _dark_gaps(self) -> list:
        """``[(filter, why)]`` for every channel that gets no dark.

        A filter with no matching dark has no row in the table above, and
        an empty table is exactly what "everything is fine" looks like.
        This is the single largest quality gap a run can have, so it is
        said in words underneath rather than left to an absence.
        """
        gaps = []
        for filt in sorted(self._groups):
            sig, note = self._dark_for_filter(filt)
            if sig is None:
                gaps.append((filt, note))
        return gaps

    def _flats_cell(self, filt: str) -> tuple:
        """``(text, tooltip)`` describing the flats this filter WILL use.

        The same restriction the run applies: with "Match flats to the
        same night" on, only the flats from the nights this filter's
        lights were taken count -- so the number in the table is the
        number that will be stacked, not the number that happens to lie
        in the folder.

        Feeds the tooltip of the Calibration column rather than a column
        of its own: the count was identical for every filter on a rig
        with an automatic panel, so it earned no width.  The master
        switch is NOT read here -- `_calib_cell` owns that decision, and
        two places deciding it is how "none found" and "switched off"
        came to look alike in the first place.
        """
        grp = ((self._calib or {}).get(KIND_FLAT) or {}).get(filt)
        if not grp:
            return "—", (f"No flats found for {filt}. Vignetting and dust "
                         "shadows will stay in this channel.")
        files, per_night, lit = self._flat_files(filt)
        nights = sorted({_night_of(p, self._nights) or "?" for p in files})
        exp = float((grp.get("info") or {}).get("exp_s") or 0.0)
        text = f"{len(files)} × {exp:g}s" if exp else str(len(files))
        offset = dict((f, off) for f, _n, _e, off
                      in self._flat_offset_preview()).get(filt, "—")
        tip = [f"{len(files)} flat(s) for {filt}"
               + (f" at {exp:g}s" if exp else ""),
               "From: " + ", ".join(nights),
               f"Offset-corrected with: {offset}"]
        if per_night:
            tip.append("One master per night — "
                       + ", ".join(f"{n} ×{len(per_night[n])}"
                                   for n in sorted(per_night))
                       + ". Each night's lights are divided by its own, and "
                       "the results merged back into one master.")
            missing = sorted(lit - set(per_night))
            if missing:
                tip.append("No flats for " + ", ".join(missing)
                           + " — those nights fall back to a pooled master.")
        elif len(nights) > 1 and not self.chk_flats_by_date.isChecked():
            tip.append("Pooled across nights — right for a rig that was not "
                       "touched in between. 'Match flats to the same night' "
                       "gives each night its own master.")
        elif self.chk_flats_by_date.isChecked() and len(lit) > 1:
            # The lights span nights; the flats do not.  Keyed on the LIT
            # nights, because that is what the user is being told cannot
            # be separated -- the flats have already been narrowed to one.
            tip.append("Only one of the imaged nights has flats of its own, "
                       "so they cannot be kept apart — pooled.")
        return text, "\n".join(tip)

    def _show_calib_summary(self, unsupported: int = 0,
                            quiet: bool = False) -> None:
        """Report what calibration material the scan turned up.

        `quiet` updates the LABEL without writing to Siril's log.  The
        label has to follow every switch -- it describes what will be
        used -- but the log is a record of the run, and re-logging the
        same three paragraphs on each click buried it: eleven repetitions
        of "Flat offset — …" in seventeen seconds of someone deciding
        which boxes to tick.
        """
        log = (lambda *_a, **_k: None) if quiet else self._log
        if unsupported:
            log(
                f"{unsupported} XISF file(s) found and skipped — that format "
                "is not supported (its headers cannot be read).",
                LogColor.SALMON)
        if not self._calibration_on():
            c = self._calib or {}
            found = sum(len(g["files"]) for kind in
                        (KIND_FLAT, KIND_DARKFLAT, KIND_DARK, KIND_BIAS)
                        for g in (c.get(kind) or {}).values())
            self.lbl_calib_found.setText(
                "Calibration is switched off."
                + (f"  {found} calibration frame(s) were found and will "
                   "NOT be used." if found else ""))
            if found:
                log(
                    f"Calibration is switched off, so the {found} "
                    "calibration frame(s) that were found stay unused. "
                    "Tick 'Use flats and dark-flats' or 'Use darks and "
                    "bias' to use them.", LogColor.SALMON)
            return
        c = self._calib or {}
        # What is left for this line to say, now that both tables answer
        # "what will each filter be given": WHERE the material physically
        # came from.  No table shows that, and it is the one question a
        # library folder raises -- picking one otherwise produced a path
        # and no visible consequence.  It also counts sets no table
        # lists, such as a 600s dark that matches nothing here.
        #
        # What each FILTER will be given is one row per filter in the
        # tables, and repeating it here as prose made four lines of 9pt
        # blue in which nothing stood out -- three times "→ 3s dark",
        # three times "3 master(s)".
        # Split by WHERE it came from.  Picking a library folder otherwise
        # produced a path and no visible consequence: the counts went up
        # somewhere in a single line, and a library that contributed
        # nothing looked exactly like one that contributed everything.
        near, lib = [], []
        # Plural spelled out per kind: appending "s" to every label read
        # "100 biass".  Bias is its own plural here -- "biases" is correct
        # English but reads as a second word next to "darks" and "flats".
        for kind, one, many in ((KIND_FLAT, "flat", "flats"),
                                (KIND_DARKFLAT, "dark-flat", "dark-flats"),
                                (KIND_DARK, "dark", "darks"),
                                (KIND_BIAS, "bias", "bias")):
            groups = c.get(kind) or {}
            for where, files in ((near, "near"), (lib, "lib")):
                n = sum(self._count_from(g["files"], files)
                        for g in groups.values())
                if not n:
                    continue
                exps = sorted({float((g.get("info") or {}).get("exp_s") or 0.0)
                               for g in groups.values()
                               if self._count_from(g["files"], files)})
                at = ("" if kind in (KIND_FLAT, KIND_BIAS) or not any(exps)
                      else " at " + ", ".join(f"{e:g}s" for e in exps if e))
                where.append(f"{n} {one if n == 1 else many}{at}")
        bits = []
        if near:
            bits.append("Next to the lights: " + " · ".join(near))
        if lib:
            bits.append("From the library: " + " · ".join(lib))
        elif self._library:
            # The one case worth colouring: a folder was chosen and it
            # gave the run nothing.
            bits.append("<span style='color:#ffaa88;'>From the library: "
                        "nothing usable found</span>")
            log(
                f"The library folder {self._library} holds no calibration "
                "frames this run can use — check that it contains DARK or "
                "BIAS frames for this camera.", LogColor.SALMON)
        preview = self._flat_offset_preview()
        if preview:
            # Log only: which offset each filter's flats get.  "synthetic"
            # is the one worth noticing -- it means the library has
            # nothing that matches THIS filter's flat exposure.
            log(
                "Flat offset — " + ", ".join(
                    f"{f} {n}×{exp:g}s → {off}"
                    for f, n, exp, off in preview), LogColor.BLUE)
            weak = [f for f, _n, _e, off in preview if off == "synthetic"]
            if weak:
                log(
                    "No dark-flat or bias matches the flat exposure of "
                    + ", ".join(weak)
                    + " — Siril's synthetic offset will be used there. A "
                    "dark set at that exposure in the Library would be "
                    "better.", LogColor.SALMON)
        # Per-night calibration changes how many masters get built and
        # which lights each one touches, so it belongs in the summary
        # rather than only in the run log -- by then it is too late to
        # reconsider it.
        if self.chk_flats_by_date.isChecked():
            split = {}
            for filt, grp in (c.get(KIND_FLAT) or {}).items():
                if filt not in (self._groups or {}):
                    continue
                lit = set((self._groups.get(filt) or {}).get("dates") or [])
                per_night = StackWorker._flats_per_night(
                    grp, lit, self._nights)
                if per_night:
                    split[filt] = (sorted(per_night),
                                   sorted(lit - set(per_night)))
            if split:
                log(
                    "Flats are kept per night: "
                    + "; ".join(f"{f} → {', '.join(n)}"
                                for f, (n, _m) in sorted(split.items()))
                    + ". Each night's lights are divided by its own master "
                    "and the results merged before registration.",
                    LogColor.GREEN)
                gaps = {f: m for f, (_n, m) in split.items() if m}
                if gaps:
                    log(
                        "No flats of their own for "
                        + "; ".join(f"{f} {', '.join(m)}"
                                    for f, m in sorted(gaps.items()))
                        + " — those nights fall back to a pooled master.",
                        LogColor.SALMON)
            elif any(len((self._groups.get(f) or {}).get("dates") or []) > 1
                     for f in (c.get(KIND_FLAT) or {})
                     if f in (self._groups or {})):
                log(
                    "'Match flats to the same night' is on, but no filter "
                    "has flats from two of its imaged nights — there is "
                    "nothing to keep apart, so one pooled master is used.",
                    LogColor.SALMON)
        # The gap that used to be invisible until the run was already
        # going: a library full of darks that fit nothing still reads
        # "442 darks" to anyone glancing at this line.
        no_dark, why = [], {}
        for filt in sorted(self._groups or {}):
            ok, note = self._dark_preview(filt)
            if not ok:
                no_dark.append(filt)
                why.setdefault(note, []).append(filt)
        if bits:
            head = "<br>".join(bits)
            log("Calibration found — "
                      + " | ".join(re.sub(r"<[^>]+>", "", b) for b in bits),
                      LogColor.GREEN)
        else:
            head = "No calibration frames found." + (
                "" if self._library else "  Set a Library folder for "
                "darks / bias.")
        if no_dark:
            # The WARNING belongs under the darks table, where the filter
            # that lacks one is missing from the rows -- `_refresh_darks_
            # _table` writes it there.  Repeating it here put the same
            # sentence twice on one screen, and a fact stated twice reads
            # as two facts.  The log still records it once per reason.
            for note, which in sorted(why.items()):
                log(f"{', '.join(which)}: {note}", LogColor.SALMON)
        self.lbl_calib_found.setText(head)

    def _on_analyze_done(self, payload: dict) -> None:
        self._groups = payload["groups"]
        self._target = payload["target"]
        total = payload["total"]
        objects = payload.get("objects", [])
        self._calib = payload.get("calib", {}) or {}
        # The night each frame really belongs to (noon-to-noon, from its
        # own DATE-OBS).  The previews below must judge nights by the same
        # rule the run does, or the table promises a per-night split the
        # run then refuses -- or hides one it is about to make.
        self._nights = payload.get("nights", {}) or {}
        self._show_calib_summary(payload.get("unsupported", 0))
        if payload.get("stray_lights"):
            self._log(
                f"{payload['stray_lights']} light frame(s) in the library / "
                "neighbouring calibration folders were ignored — only "
                "calibration frames are taken from outside the target "
                "folder.", LogColor.SALMON)

        self._set_left_enabled(True)

        self.grp_discovered.setTitle(DISCOVERED_TITLE + (self._target or "—"))

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
        total_lights, total_exp = self._refresh_filter_table()
        self._refresh_flats_table()
        self._refresh_darks_table()
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
            "calibrate": self._calibration_on(),
            "use_flats": self.chk_use_flats.isChecked(),
            "use_darks": self.chk_use_darks.isChecked(),
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
            "nb_bandwidths": {r: float(s.value())
                              for r, s in self._nb_bw.items()},
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
            # Not an option: what this Siril's Python module cannot do, so
            # the report can name the reason a step took the simpler route.
            "missing_api": list(self._missing_api),
            "compose": self.chk_compose.isChecked(),
            "compose_palette": palette,
            "reuse_masters": self.chk_reuse.isChecked(),
            "quick_lrgb": self.chk_quick_lrgb.isChecked(),
            "nb_normalize": self.chk_nb_norm.isChecked(),
            "synth_lum": self.chk_synth_lum.isChecked(),
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
            self._ext, self._current_opts(), self._calib, self._nights)
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
    def report_capabilities(self) -> None:
        """Say once which optional Siril calls this module does not have.

        Every use of them is wrapped, so a missing one costs nothing at
        run time -- it just degrades, quietly, forever.  Stating it at
        startup is the difference between "the report always says
        estimated" being a mystery and being an answerable question.
        """
        missing = _missing_capabilities(self.siril)
        if not missing:
            return
        self._missing_api = missing
        self._log(
            "This Siril's Python module is older than this script "
            f"expects: {len(missing)} "
            + _plural(missing, "feature falls", "features fall")
            + " back to a simpler route. Updating Siril restores "
            + _plural(missing, "it", "them") + ".", LogColor.SALMON)
        for feature, calls, consequence in missing:
            names = ", ".join(f"{c}()" for c in calls)
            self._log(f"  - {feature} — needs {names}; "
                      f"without it, {consequence}.", LogColor.SALMON)

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

        tab1 = QTextBrowser()
        tab1.setOpenExternalLinks(True)
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
            "<li>The script <b>analyzes</b> the tree and fills three "
            "tables.  <b>Discovered Lights</b> lists every filter with its "
            "frame count, integration time and camera state — what was "
            "shot.  <b>Flats and Dark-Flats</b> and <b>Calibration with "
            "Darks and Bias</b> then say what those lights will be "
            "<i>given</i>: the sets that will actually be opened, the "
            "offset each flat is corrected with, and which filters each "
            "dark covers.  Every filter that gets <b>no dark</b> is named "
            "in warning colour under that table, with the exposures the "
            "library does hold and what would fix it — a gap that used to "
            "surface only once the run was already going.</li>"
            "<li>Each of the two calibration tables has its own switch, so "
            "good flats can be used with unusable darks, or the reverse.  "
            "What is switched off stays listed and turns grey: found is "
            "never the same as applied.</li>"
            "<li>Review the three tables and the "
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
            "<p>Some capture software writes <b>no IMAGETYP at all</b>.  "
            "Such a frame is then read from its <i>content</i>: no filter, "
            "no object and the mount parked at RA=DEC=0 means the shutter "
            "was closed → <b>dark</b>; a filter <i>and</i> an object means "
            "it was pointed at something → <b>light</b>.  Flat and bias are "
            "deliberately never guessed: nothing in an ordinary header "
            "separates them reliably, and a wrong guess there would "
            "corrupt the calibration instead of merely skipping it.</p>"
            "<p><b>Pick the folder of ONE target.</b>  If the folder holds "
            "frames of several objects (e.g. you picked the date or LIGHT "
            "folder), their frames would end up in the same stack — so the "
            "script detects that from the <tt>OBJECT</tt> keyword, warns you "
            "after the analysis, and asks again before stacking.</p>"
            "<p>Its own results folder (<b>output/</b>) is skipped while "
            "scanning, so a second run never re-reads the masters it wrote "
            "as if they were new light frames.</p>")
        tabs.addTab(tab1, "Getting Started")

        tab2 = QTextBrowser()
        tab2.setOpenExternalLinks(True)
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
            "The report names <b>how many star pairs each channel was "
            "matched on</b>, read back from Siril's own registration "
            "output, and flags the ones fitted on too few — that count is "
            "the earliest warning for colour fringing towards the edges.  "
            "If the format is not recognised, the report stays silent "
            "rather than guess.<br>"
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
            f"<li><b>5 – {SIGMA_MAX_FRAMES} frames</b> → sigma clipping "
            "(3σ / 3σ)</li>"
            f"<li><b>{SIGMA_MAX_FRAMES + 1} – {GESDT_MIN_FRAMES - 1} "
            "frames</b> → Winsorized sigma (3σ / 3σ)</li>"
            f"<li><b>{GESDT_MIN_FRAMES} – {LINEAR_MIN_FRAMES} frames</b> → "
            "<b>GESDT</b> (Generalized Extreme Studentized Deviate Test).  "
            "Its two numbers are <i>not</i> sigmas: <tt>0.3</tt> caps the "
            "fraction of the stack that may be rejected, <tt>0.05</tt> is "
            "the significance threshold.  If your Siril build does not know "
            "it, the run falls back to linear fit and says so.</li>"
            f"<li><b>&gt; {LINEAR_MIN_FRAMES} frames</b> → linear-fit "
            "clipping (5 / 4).  It models a trend <i>across</i> the stack, "
            "so it belongs where the stack is long enough to define one — "
            "not in the middle of the range, where this script used to put "
            "it.</li>"
            "</ul>"
            "<p>The measurements go into <tt>output.md</tt> as a table of "
            "their own — integrated count, median FWHM, roundness, star "
            "count per channel.  A value Siril did <b>not</b> record shows "
            "as an em-dash, never as <tt>0.00</tt>: a zero there would "
            "read as catastrophic trailing, when the truth is that the "
            "measurement is absent.</p>"
            "<p>The frame count that picks the band is <b>measured</b>, "
            "not estimated: after registration the script asks Siril for "
            "the sequence it produced and reads which frames are still "
            "included, together with their median FWHM, roundness and star "
            "count.  Those numbers go into the report as measurements.  "
            "The quality filters run at registration time, so the exported "
            "count already reflects them — subtracting their share again "
            "would pick the band for a smaller population than the one "
            "being integrated.  Only when the sequence cannot be read at "
            "all does an estimate stand in, and the report marks it.</p>"
            "<p>These band edges are <b>Cyril Richard\u2019s</b>, taken "
            "from <b>AMSP</b> (Automatic Multi-Session Processing) in "
            "the official Siril script repository — "
            f"<a style='color:#88aaff;' href='{AMSP_URL}'>"
            "AMSP.py</a>, GPL-3.0-or-later.  He wrote Siril and "
            "implemented these algorithms, so his thresholds carry more "
            "weight than our own reasoning did.  Only the numbers were "
            "adopted; no code was copied.</p>"
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
            "mixed into Red as a weighted sum (adjustable "
            "<b>Ha → Red</b> strength) "
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
            "<p>The <b>sensor and filter fields auto-complete</b> from that "
            "same list: type <tt>anti</tt> and every Antlia filter Siril "
            "knows is offered, spelled exactly as Siril spells it.  You can "
            "still type anything you like — the field is free text, the "
            "list is only a suggestion.</p>"
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
            "<p style='color:#888;'>The names come from Siril's own SPCC "
            "database, read-only, at the location sirilpy reports.  On a "
            "packaged build (Flatpak / Snap / Store) that database can sit "
            "where no path guess reaches it; the script then asks Siril "
            "itself with <tt>spcc_list</tt>, whose answer is by definition "
            "right.  That route prints the whole list into the Log, which "
            "is why it is only taken when reading the files failed.  If "
            "neither works the check is simply skipped — a database the "
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

        tab_cal = QTextBrowser()
        tab_cal.setOpenExternalLinks(True)
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
            "<p>A library is meant to grow, so <b>only the darks this run "
            "can actually use are stacked</b> — judged by the same rule that "
            "will later pick one.  Five exposures at three setpoints are "
            "fifteen masters; building fourteen of them to open one would "
            "cost minutes and read hundreds of frames for nothing.</p>"
            "<hr>"
            "<h3 style='color:#88aaff;'>How frames are matched</h3>"
            "<p>Matching runs on <b>FITS headers</b>, not on file names, so "
            "any naming scheme works.  A master is only used when the "
            "<b>camera</b> (INSTRUME), gain, binning and image dimensions "
            "match exactly and the temperature is within "
            f"<b>±{CALIB_TEMP_TOLERANCE_C:g} °C</b>.  Two bodies of the same "
            "sensor format would otherwise calibrate each other, which size "
            "alone cannot rule out.  Values missing from a header never "
            "block a match — except the exposure, where an unreadable "
            "EXPTIME reads as 0&nbsp;s and 0 against 120 is exactly the "
            "mismatch that must not slip through.</p>"
            f"<p><b>Exposure is matched within {DARK_EXPOSURE_TOLERANCE:.0%}"
            "</b>, not exactly.  The thermal signal scales with exposure, so "
            "a 290&nbsp;s dark removes very nearly what a 300&nbsp;s one "
            "would, while refusing it would leave the lights uncalibrated — "
            "the worse outcome.  The nearest dark inside that band is used "
            "and <i>named in the Log</i>, with everything else confirmed to "
            "agree; beyond it the run continues without a dark and says so.  "
            "A 60&nbsp;s dark on 300&nbsp;s lights is 80% off and is never "
            "applied.</p>"
            "<h3 style='color:#88aaff;'>Two rules worth knowing</h3>"
            "<ul>"
            "<li><b>Flats pooled across nights are checked against each "
            "other.</b>  Dividing one night's flats by another's gives a "
            "uniform image when the optical train did not move, and shows "
            "the vignetting or dust that did.  Each night is normalised by "
            "its own median first, so a brighter panel is not counted as "
            f"disagreement.  Under {FLAT_MATCH_GOOD:.2%} the nights agree; "
            f"up to {FLAT_MATCH_LIMIT:.2%} is still usable; beyond that the "
            "report names the nights and points at <i>Match flats to the "
            "same night</i>.  With that option on the measurement still "
            "runs and is still reported — it is what shows the split is "
            "earning its extra stack — but it stops being a warning.<br>"
            "Those thresholds only hold if the noise is taken out first, "
            "so a whole night is averaged rather than one frame picked, "
            f"and the map is binned to about {FLAT_COMPARE_TARGET} px "
            "before the spread is read.  Both steps come from the tool the "
            "thresholds come from.  The check also measures its own noise "
            "floor, by comparing one night with itself, and stays quiet "
            "when the difference between nights does not clear it.</li>"
            "<li><b>A filter that mixes exposures, or nights, is calibrated "
            "in parts.</b>  A dark only removes the thermal signal that grew "
            "during <i>its own</i> exposure, so one dark for 120&nbsp;s and "
            "300&nbsp;s subs is right for neither; a flat only describes the "
            "optical train it was shot through, so with <i>Match flats to "
            "the same night</i> on, each night wants its own.  The two are "
            "independent, so the parts are their cross product and a "
            "dimension with one value drops out.  Each part is staged and "
            "calibrated with its own masters, and the calibrated parts are "
            "merged again (<tt>merge</tt>) before registration — the channel "
            "still becomes <b>one</b> master, which is what the composite "
            "needs.  With no darks in the run the exposure never splits, and "
            "with one master flat the night never does.</li>"
            "<li><b>Bias is never applied together with a dark.</b>  A master "
            "dark already contains the offset; subtracting bias as well would "
            "remove it twice.  <tt>-bias=</tt> is only added when no dark is "
            "used.</li>"
            "<li><b>Flats are offset-corrected before stacking.</b>  Real "
            "bias / dark-flat first; failing that a plain <b>DARK shot at "
            "the flats' exposure</b> — a dark at the flat exposure IS a "
            "dark-flat, whatever IMAGETYP calls it, and it is accepted "
            f"within {DARKFLAT_EXPOSURE_TOLERANCE:.0%} because flat "
            "exposures are short enough for the difference to stay "
            "negligible; then Siril's synthetic offset "
            "<tt>=64*$OFFSET</tt>; and if that is refused too, the flats are "
            "stacked raw.  Calibration never aborts a run.</li>"
            "</ul>"
            "<h3 style='color:#88aaff;'>Options</h3>"
            "<ul>"
            "<li>There is no separate master switch.  Every gate one would "
            "hold is about darks, flats or bias, so the two boxes below say "
            "it together — and a third could contradict them: switched off "
            "with both of these on was a state in which the panel showed "
            "two armed switches and the run calibrated nothing.  Both off "
            "is \u201cunchecked\u201d for the whole group, and stacks raw lights.</li>"
            "<li><b>Use flats and dark-flats</b> — divide the lights by the "
            "master flat.  The dark-flat (or, failing that, the bias) is the "
            "flat's own offset and follows this switch: it exists only to "
            "calibrate the flats.  Switched off, no flat master is stacked "
            "at all — the frames are listed in the table above, greyed, so "
            "\u201cfound\u201d can never be mistaken for "
            "\u201capplied\u201d.</li>"
            "<li><b>Use darks and bias</b> — subtract the master dark, and "
            "use the master bias where no dark applies.  Bias reaches the "
            "lights <i>only</i> where no dark does, because a master dark "
            "already carries the offset.  Switched off, neither master is "
            "stacked and cosmetic correction has nothing to read — but the "
            "bias is still built when flats need it as their offset, so "
            "turning the darks off cannot quietly downgrade every flat to a "
            "synthetic one.  The two kinds are separate switches because "
            "they fail for unrelated reasons: a session can have perfect "
            "flats and a library of darks that fit nothing.</li>"
            "<li><b>Cosmetic correction (hot pixels)</b> — adds "
            "<tt>-cc=dark 3 3</tt>, which locates hot and cold pixels from "
            "the master dark's own statistics.  Needs a matching dark; "
            "without one it has no effect.</li>"
            "<li><b>Match flats to the same night</b> — <i>off</i> pools all "
            "flats of a filter into one, less noisy master (right for a "
            "permanently mounted rig); <i>on</i> builds one master flat "
            "<b>per night</b> and divides each night's lights by its own, "
            "then merges the calibrated nights again before registration, so "
            "the filter still ends as one master.  Right whenever the "
            "optical train was touched between nights — focus, rotation, a "
            "cleaned corrector.  A night whose flats are missing falls back "
            "to a pooled master, and the log names it.</li>"
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

        # Built before setHtml so the document below stays one flat string
        # of literals -- a table assembled inside the call would be
        # invisible to anything that reads the help without running it.
        nb_rows = "".join(
            f"<tr><td><b>{name}</b></td>"
            + "".join(f"<td>{_ROLE_LABEL[r]}</td>" for r in roles)
            + "</tr>" for name, roles in _NB_PALETTES.items())
        mix_rows = "".join(
            f"<tr><td style='width:90px'><b>{name}</b></td>"
            + "".join(
                "<td>" + " + ".join(
                    f"{share:.0%}&nbsp;{_ROLE_LABEL[role]}"
                    for role, share in chans[ch].items()) + "</td>"
                for ch in ("red", "green", "blue"))
            + "</tr>" for name, chans in _MIX_PALETTES.items())

        tab_ref = QTextBrowser()
        tab_ref.setOpenExternalLinks(True)
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
            "background → (PCC) → save linear.</p>"

            "<hr><h3 style='color:#88aaff;'>First: what the four dropdowns "
            "are</h3>"
            "<p>The <b>L / R / G / B</b> fields are the <i>channel "
            "mapping</i> — which stacked master ends up in which colour "
            "channel.  They are not a list of \u201cfilters this palette "
            "uses\u201d, and two things follow from that:</p>"
            "<ul>"
            "<li><b>Not every palette fills all four.</b>  RGB, SHO and HOO "
            "leave <b>L</b> empty — they have no luminance channel, so a "
            "Luminance filter you shot is simply not read (and with "
            "<i>Stack only the filters this palette uses</i> not even "
            "stacked).</li>"
            "<li><b>A filter can be used without being mapped.</b>  HaRGB is "
            "the case: Ha is blended <i>into</i> Red rather than assigned to "
            "a channel, so it has no dropdown at all.  The Log names the Ha "
            "master it picked.</li>"
            "</ul>"

            "<hr><h3 style='color:#88aaff;'>LRGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(default, broadband + luminance)</span></h3>"
            "<p><b>Mapping:</b> R=Red&nbsp; G=Green&nbsp; B=Blue&nbsp; "
            "L=Luminance <i>(kept separate)</i></p>"
            "<p>RGB is composed and colour-calibrated on its own; the L "
            "master is <b>not</b> baked in (that would skew PCC and give weak "
            "colour).  You add L after stretching.</p>"
            "<pre style='color:#aaddaa'>rgbcomp  R  G  B  -out=TARGET_RGB\n"
            "platesolve → subsky → pcc → save   (linear)</pre>"
            "<p><b>Output:</b> <tt>TARGET_RGB.fit</tt> (calibrated, linear) "
            "&nbsp;+&nbsp; <tt>masters/…_LUMINOS.fit</tt> kept separate.<br>"
            "<b>You finish:</b> stretch RGB and L, then combine luminance "
            "last (RGB Composition → luminance, or <tt>rgbcomp -lum</tt>).</p>"

            "<hr><h3 style='color:#88aaff;'>RGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(broadband, no luminance)</span></h3>"
            "<p><b>Mapping:</b> R=Red&nbsp; G=Green&nbsp; B=Blue</p>"
            "<pre style='color:#aaddaa'>rgbcomp  R  G  B  -out=TARGET_RGB\n"
            "platesolve → subsky → pcc → save   (linear)</pre>"
            "<p><b>Output:</b> <tt>TARGET_RGB.fit</tt>. Just stretch it.</p>"

            "<hr><h3 style='color:#88aaff;'>Quick linear LRGB &nbsp;"
            "<span style='color:#888;font-weight:normal'>(option, off by "
            "default)</span></h3>"
            "<p>Bakes L in linearly in one step — a single file, but less "
            "accurate colour (PCC runs on the L-mixed image).  For a fast "
            "look only.</p>"
            "<pre style='color:#aaddaa'>rgbcomp -lum=L  R  G  B  "
            "-out=TARGET_LRGB\n"
            "platesolve → subsky → pcc → save   (linear)</pre>"
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
            "platesolve → subsky → (PCC skipped) → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_SHO.fit</tt> (linear).<br>"
            "<b>You finish:</b> stretch, then colour-balance / saturation to "
            "taste (Ha often still leans green).</p>"

            "<hr><h3 style='color:#88aaff;'>HOO &nbsp;<span style='color:#888;"
            "font-weight:normal'>(bicolour)</span></h3>"
            "<p><b>Mapping:</b> R=Ha&nbsp; G=OIII&nbsp; B=OIII</p>"
            "<pre style='color:#aaddaa'>linear_match Ha 0 0.92   → OIII_nbnorm\n"
            "rgbcomp  Ha  OIII_nbnorm  OIII_nbnorm  -out=TARGET_HOO\n"
            "platesolve → subsky → (PCC skipped) → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_HOO.fit</tt> (linear).</p>"
            "<p><b>OIII feeds Green and Blue</b>, which is why two filters "
            "are enough — and why SPCC reports "
            "<tt>B/G = 1.000000 + 0.000000 … sigma 0.000000</tt>.  That is "
            "not a failure: Blue and Green <i>are</i> the same image, so "
            "their ratio is exactly 1 everywhere and there is nothing to "
            "fit.  Only the <b>R/G</b> line carries information here.</p>"

            "<hr><h3 style='color:#88aaff;'>HaRGB &nbsp;<span style='color:#888;"
            "font-weight:normal'>(Ha-enhanced broadband)</span></h3>"
            "<p><b>Mapping:</b> R=Red <i>(+Ha blended in)</i>&nbsp; G=Green"
            "&nbsp; B=Blue&nbsp; L=Luminance <i>(separate)</i></p>"
            "<p>The Ha master is <b>mixed into Red</b> as a weighted sum, "
            "<tt>(R + k·Ha) / (1+k)</tt>, at the <b>Ha → Red</b> strength "
            "you set, then composed like RGB.  A weighted sum keeps the "
            "composite linear and stays in [0,1] without a rescale.  PCC "
            "is skipped (the Red channel is no longer photometric).</p>"
            "<p><b>Why is Ha not in the filter fields?</b>  Because it does "
            "not replace a channel.  HaRGB keeps the ordinary R/G/B/L "
            "mapping and mixes Ha in on top of it, so there is nothing to "
            "map.  The Ha master is found by filter role among the aligned "
            "masters; selecting the palette tells you which one it will use, "
            "or that none of your filters carries an Ha role — in which case "
            "the run would compose plain RGB.</p>"
            "<pre style='color:#aaddaa'>pm \"1-(1-$R$)*(1-k*$Ha$)\"  → "
            "TARGET_RED_Ha      (k = Ha→Red %)\n"
            "rgbcomp  TARGET_RED_Ha  G  B  -out=TARGET_HaRGB\n"
            "platesolve → subsky → (PCC skipped) → save</pre>"
            "<p><b>Output:</b> <tt>TARGET_HaRGB.fit</tt> + L separate.<br>"
            "<b>Note:</b> classic HaRGB is refined <i>after</i> stretching; "
            "this is a linear starting point — tune the strength, or redo the "
            "blend post-stretch for full control.</p>"

            "<hr><h3 style='color:#88aaff;'>The other narrowband "
            "assignments</h3>"
            "<p>SHO and HOO are the two everyone knows; the rest are the "
            "same idea with the lines in different places.  All of them are "
            "pure <b>assignments</b> — a channel is copied, not computed — "
            "so they behave identically before and after a stretch.</p>"
            "<table cellpadding='5' style='width:100%'>"
            "<tr><td style='width:90px'><b>Palette</b></td><td><b>Red</b>"
            "</td><td><b>Green</b></td><td><b>Blue</b></td></tr>"
            f"{nb_rows}"
            "</table>"
            "<p>Each of them gets the same treatment as SHO: narrowband "
            "normalisation if enabled, and SPCC in narrowband mode with the "
            "wavelengths of the lines <i>this</i> palette put in each "
            "channel.</p>"

            "<hr><h3 style='color:#88aaff;'>Realistic1 / Realistic2 &nbsp;"
            "<span style='color:#888;font-weight:normal'>(weighted "
            "mixes)</span></h3>"
            "<p>These <i>mix</i> the lines instead of assigning them:</p>"
            "<table cellpadding='5' style='width:100%'>"
            f"{mix_rows}"
            "</table>"
            "<p>The mixing is done with <tt>pm</tt>, and colour calibration "
            "is skipped: a channel that is 70% Ha and 30% SII has no single "
            "passband for SPCC to model.</p>"

            "<hr><h3 style='color:#88aaff;'>Why the list stops here</h3>"
            "<p>Everything above is either an assignment or a weighted sum "
            "— operations that mean the same thing before and after a "
            "stretch, which is what a linear pipeline can offer.  The "
            "<b>dynamic</b> palettes (Foraxx and relatives) blend with a "
            "factor like <tt>t<sup>(1-t)</sup></tt>, <tt>t = Ha·OIII</tt>: "
            "on linear data <tt>t</tt> is around 1e-6 and the expression "
            "collapses.  Stretch first and use Siril's own <b>Palette "
            "Picker</b> for those.</p>"
            "<p><b>Ha → Red</b> used to be a screen blend, "
            "<tt>1-(1-R)(1-k·Ha)</tt>.  On faint nebulosity that agrees "
            "with a plain sum to better than 0.1%, which is why it stood "
            "for so long — but its <tt>R·Ha</tt> cross term is quadratic, "
            "and on the bright end it bites: R=0.8 with k·Ha=0.4 gives "
            "0.88 against 1.2, a 27% compression of exactly the stars and "
            "nebula cores you stretch afterwards.  Since 1.7.10 it is a "
            "weighted sum, and the composite is linear everywhere.</p>"

            "<hr><h3 style='color:#88aaff;'>Synthetic luminance</h3>"
            "<p><b>Build a synthetic luminance master</b> averages the "
            "emission-line masters into "
            "<tt>masters/TARGET_SynthL.fit</tt> — the detail of a "
            "narrowband night sits spread over its channels, and the "
            "average carries their combined signal-to-noise.  It is "
            "<b>not</b> combined into the colour image: that belongs after "
            "the stretch, and <tt>todo.md</tt> picks it up there.</p>"

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

        tab3 = QTextBrowser()
        tab3.setOpenExternalLinks(True)
        tab3.setHtml(
            "<h2 style='color:#88aaff;'>Output &amp; Tips</h2>"
            "<p>Results go into an <b>output</b> folder inside your "
            "target folder, with a tidy, self-explaining layout:</p>"
            "<pre style='color:#aaddaa'>output/\n"
            "├─ TARGET_RGB.fit        the finished colour image(s)\n"
            "├─ masters/\n"
            "│   ├─ TARGET_FILTER.fit            aligned (use to combine)\n"
            "│   └─ TARGET_FILTER_29x300s_G100_-10C_fullframe.fit\n"
            "│                                   full, uncropped stack\n"
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
            "_SHO / _HOO / _HaRGB / _LRGB</span> — <b>linear</b>, loaded "
            "into Siril automatically.  All of them are colour-calibrated "
            "except <tt>_HaRGB</tt>: its Red carries blended Ha, so the "
            "star colours are no longer physical and photometric "
            "calibration is skipped for it (see <i>The Pipeline</i>).  "
            "Balance that one by hand.</li>"
            "<li><b>masters/</b> holds two versions per channel: "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_FILTER.fit</span> (aligned to a common grid — combine "
            "these) and "
            "<span style='font-family:monospace;color:#aaddaa;'>"
            "TARGET_FILTER_29x300s_G100_-10C_fullframe.fit</span> — the "
            "full, uncropped stack, named after what went into it: frames "
            "integrated, exposure, gain, sensor temperature.</li>"
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
            "<li><b>If the Log says features fell back.</b>  Some of what "
            "this script does needs calls that only newer versions of "
            "Siril's Python module have — measured frame counts, "
            "composing in memory, reading Siril's log.  Every one of them "
            "is wrapped, so a missing call costs nothing: the run takes a "
            "simpler route instead.  What it used to cost was an "
            "explanation, because the fallback was silent.  Missing calls "
            "are now named once at startup and again in "
            "<tt>output.md</tt>, with what each one changes.  Updating "
            "Siril restores them.</li>"
            "<li><b>Disk while a run is going.</b>  Each step — calibrate, "
            "background, register — writes a full copy of every frame.  "
            "With <b>Delete _work/ when finished</b> ticked, each "
            "generation is freed as soon as the next one is complete, so "
            "the peak is about two generations instead of four (roughly "
            "3.6&nbsp;GB per generation for a hundred 3008×3008 subs).  "
            "Untick it and every intermediate is kept, which is what you "
            "want when something needs inspecting.</li>"
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

        # These tabs are the quick reference; the manual goes deeper (per
        # palette, per option, troubleshooting).  QTextEdit does not open
        # links, so the pointer lives in a QLabel that does.
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
        layout.addWidget(docs)

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
        _apply_theme(app, siril)
        win = ImageMonoTrainWindow(siril)
        win.showMaximized()
        try:
            siril.log(f"Svenesis ImageMono Train v{VERSION} loaded.")
        except (SirilError, OSError, RuntimeError):
            pass
        win.report_capabilities()
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
