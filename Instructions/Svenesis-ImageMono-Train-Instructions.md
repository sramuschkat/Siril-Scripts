# Svenesis ImageMono Train — User Instructions

**Version 1.7.9** | Siril Python Script for Monochrome Filter-Wheel Stacking and Colour Composition

> *Point it at one N.I.N.A. target folder and walk away with per-channel masters and a calibrated colour image — calibration, stacking, cross-filter alignment, palette composition and colour calibration in one pass.*

---

## Table of Contents

1. [What Is ImageMono Train?](#1-what-is-imagemono-train)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Preparing Your Data](#4-preparing-your-data)
5. [Getting Started — Your First Run](#5-getting-started--your-first-run)
6. [The User Interface](#6-the-user-interface)
7. [Calibration](#7-calibration)
8. [Stacking Options](#8-stacking-options)
9. [Palettes & Channel Mapping](#9-palettes--channel-mapping)
10. [Colour Calibration](#10-colour-calibration)
11. [Output Files](#11-output-files)
12. [Master Reuse](#12-master-reuse)
13. [Recommended Workflows](#13-recommended-workflows)
14. [Troubleshooting](#14-troubleshooting)
15. [Tips & Best Practices](#15-tips--best-practices)
16. [FAQ](#16-faq)
17. [What's New in 1.7.9](#17-whats-new-in-179)

---

## 1. What Is ImageMono Train?

**Svenesis ImageMono Train** takes a single night (or several nights) of monochrome subs shot through a filter wheel and produces:

- one **linear master per filter**, calibrated and stacked,
- all masters **aligned onto one common pixel grid**, so the channels overlay exactly,
- a **colour composite** in the palette of your choice, background-extracted and colour-calibrated,
- a **processing report** (`output.md`) describing what actually happened, and
- a **post-processing guide** (`todo.md`) for the creative steps that remain.

You never type a Siril command. You pick a folder and press one button.

The script is built specifically for a **monochrome camera behind a filter wheel**. Frames are never debayered, and every decision — which rejection algorithm, which weighting, which colour calibration — is made per filter, because a 30-minute Ha channel and a 3-minute Blue channel are not the same problem.

### What it does *not* do

It stops at the **linear** image. Stretching, star reduction, saturation and the final luminance combine are creative choices, and `todo.md` walks you through them with the concrete Siril menu paths. That boundary is deliberate: colour calibration must run on linear data, so the script hands over exactly at the point where taste takes over.

---

## 2. Background for Beginners

### Why mono + filter wheel is different

A one-shot-colour (OSC) camera has a Bayer matrix glued to the sensor: every pixel is permanently red, green or blue. A **monochrome** sensor has none — every pixel collects all the light it is given. Colour comes from the **filter wheel** in front of it: you shoot a set of frames through Red, then Green, then Blue (or Luminance), and combine them afterwards.

The advantages are real — no interpolation, full resolution per channel, and the freedom to spend three times as long on the faint channel. The cost is that you now have three to six separate datasets that must be stacked separately and then made to line up **pixel for pixel**. That last part is where most manual workflows go wrong, and it is the part this script automates most carefully.

### Broadband vs. narrowband

| Type | Filters | What passes | Typical use |
|---|---|---|---|
| **Broadband** | L, R, G, B | Wide slices of the visible spectrum | Galaxies, star clusters, natural colour |
| **Narrowband** | Ha, OIII, SII | A few nanometres around one emission line | Nebulae, light-polluted skies, moonlit nights |

Narrowband frames are much darker and contain far fewer stars, because a 4.5 nm filter blocks almost all continuum light. That single fact drives several of this script's decisions — which frames can be registered, which weighting is appropriate, and which colour calibration is even meaningful.

### Calibration frames

Siril computes each calibrated light as:

```
Lc = (L − D) / (F − O)
```

- **L** — your light frame
- **D** — master dark: the sensor's own signal (thermal noise, hot pixels) at the same exposure, gain and temperature
- **F** — master flat: what your optics do to an evenly lit field (vignetting, dust shadows)
- **O** — offset/bias: the electronic pedestal the camera adds to every readout

**Flats matter most.** Without them, vignetting and dust shadows survive into the final image, and — importantly for this script — they leave a brightness gradient that makes photometric colour calibration measurably less accurate. If you shoot only one kind of calibration frame, shoot flats.

Note that the master dark already contains the bias. Subtracting both would remove it twice, so the script applies bias to the lights **only** when no dark is used.

### Linear vs. stretched

Straight out of the camera and the stacker, an astrophoto is **linear**: pixel values are proportional to the light collected. It looks almost black, because the interesting signal sits just above the background.

**Stretching** compresses that huge dynamic range into something a screen can show. It is also irreversible for the purpose of measurement — once you stretch, star brightnesses no longer relate linearly to real flux, and photometric colour calibration becomes invalid. That is why every image this script writes is linear, and why calibration happens before you touch a histogram.

---

## 3. Prerequisites & Installation

### Requirements

- **Siril 1.4** or newer, with Python script support
- **sirilpy** (bundled with Siril)
- **PyQt6, astropy, numpy** — installed automatically on first run via `s.ensure_installed`
- For colour calibration: an internet connection **or** a local Gaia catalogue. Without either, the composite is still produced, just uncalibrated.

### Installation

1. Copy `Svenesis-ImageMono-Train.py` into your Siril scripts folder.
2. In Siril: **Scripts → Refresh scripts** (or restart Siril).
3. Run it from **Processing → Scripts → Svenesis ImageMono Train**. No image needs to be loaded first.

### A note on cloud-synced folders

Siril's `link` command creates **symbolic links** to your frames. Cloud clients (Dropbox, OneDrive, iCloud Drive, Google Drive) actively rewrite symlinks they sync, which can make a linked frame vanish between two Siril commands — mid-run, with no warning from the cloud client.

**If the Log says features fell back.** Part of what this script does needs calls that only newer versions of Siril's Python module (`sirilpy`) provide: measured frame counts, composing the colour image in memory, reading Siril's own log. Every one of them is wrapped, so a missing call costs nothing — the run takes a simpler route. What it used to cost was an *explanation*, because the fallback was silent and permanent.

The script now refuses to start below **sirilpy 1.0.0** (which ships with Siril 1.4), and above that floor it checks each optional call individually — by asking whether the call exists, not by comparing version numbers. Anything missing is named once at startup and again in `output.md`, together with what it changes. Updating Siril restores them.

**Disk while a run is going.** Each step — calibrate, background, register — writes a full copy of every frame. With **Delete _work/ when finished** ticked, each generation is freed as soon as the next one is complete, so the peak stays at about two generations instead of four: roughly 3.6 GB per generation for a hundred 3008×3008 32-bit subs. Untick it and every intermediate is kept, which is what you want when something needs inspecting. (The idea comes from **Storage Friendly Stacking** by Quark-Coder, which watches the folder; a deterministic step after each command does the same job without a file watcher.)

Keep the working tree on a **local disk**. If your raw data lives in the cloud, either copy the target folder locally before processing, or exclude the `output/_work/` folder from syncing.

---

## 4. Preparing Your Data

### What the script reads

The **FITS header is the source of truth**, not the folder name:

| Keyword | Used for |
|---|---|
| `FILTER` | Grouping frames into channels |
| `IMAGETYP` | Telling lights from darks / flats / dark-flats / bias |
| `OBJECT` | Detecting that you accidentally picked a folder with several targets |
| `INSTRUME`, `EXPTIME`, `GAIN`, `CCD-TEMP`, `XBINNING`, `NAXIS1/2` | Matching calibration masters to lights |

Some capture software writes **no `IMAGETYP` at all**. Such a frame is then read from its *content*: no filter, no object and the mount parked at RA = DEC = 0 means the shutter was closed → **dark**; a filter *and* an object means it was pointed at something → **light**. Flat and bias are deliberately never guessed — nothing in an ordinary header separates them reliably, and a wrong guess there would corrupt the calibration instead of merely skipping it.

The N.I.N.A. folder schema `DATE\IMAGETYPE\TARGETNAME\FILTER\…` is used only as a **fallback** when a keyword is missing. In practice this means the script works with almost any folder layout — including the classic N.I.N.A. arrangement where `FLAT/` sits *beside* the target folder rather than inside it.

### Supported formats

- `.fit`, `.fits`, `.fts` — and their Rice-compressed `.fz` variants, read directly
- **XISF is not supported.** Files are counted and reported, never silently ignored: astropy cannot read XISF headers, so exposure, gain and temperature would be unavailable and calibration matching could not work.

### Multiple nights

The same filter spread across several nights is **pooled into one stack** automatically. Just point the script at a folder that contains all of them.

### Recommended folder layout

```
M16/
├─ LIGHT/2026-07-25/{LUMINOS,RED,GREEN,BLUE,HA,OIII}/…
├─ LIGHT/2026-08-14/{…}/…          ← a second night, same target
└─ FLAT/2026-07-25/{…}/…           ← session flats, per filter
```

Darks and bias belong in a separate **Library** folder (see §7), because they are reusable for months.

---

## 5. Getting Started — Your First Run

1. **Run the script.** No image needs to be loaded.
2. **Select Target Folder…** — pick the root folder of **one** target.
3. Optionally set a **Library…** folder holding your reusable darks and bias. It is remembered between runs.
4. Selecting the folder analyses it straight away — **Re-scan Folder** is there for afterwards, once you add frames or change the Library. The **Discovered Filters** table lists every filter with its frame count, **what its lights will be calibrated with**, and total integration.

   The **Calibration** column answers the question the table exists for: *what will happen to these lights?* It reads `Dark + Flat ×3`, `Flat`, `Bias + Flat` or `none` — the masters that will actually reach that filter, in the order `Lc = (L − D) / (F − O)` applies them, with `×3` meaning one master flat per night. It follows every switch below it: flip *Match flats to the same night* and the `×3` appears or goes.

   A **`⚠` in warning colour means no dark fits these lights.** That is the largest quality gap a run can have, and it used to surface only once the run was already going — a library holding 442 darks reads as "darks are applied" to anyone glancing at it, even when all 442 are 3-second flat-darks and the lights are 300 s. The tooltip names the exposures the library does hold, why they were refused, and what would fix it. The exposure, gain and sensor temperature move to a line under the table while every filter shares them, and return as a column the moment they differ.
5. Check the **Palette**. *Auto* proposes one from the filters found and only ever proposes one whose three channels can actually be filled.
6. Under **Auto-finish**, check the **SPCC** fields. They ship pre-filled for one particular rig — replace them with your own sensor and filter names (see §10).
7. Press **Stack All Filters** and watch the **Log** tab.
8. When it finishes, `output/` opens with the colour image loaded in Siril. Read **`todo.md`** for the rest.

A six-filter, forty-frame night takes roughly 20 seconds on a modern laptop.

---

## 6. The User Interface

The window has a **left panel** for input and options and a **right panel** with two tabs.

### Right panel

| Tab | Contents |
|---|---|
| **Overview** | What the analysis found: filters, frame counts, integration times, calibration frames, warnings |
| **Log** | Everything the run does, in order, including the exact Siril commands |

The Log is where the script explains its decisions. When it skips something, degrades to a fallback, or notices a configuration that works against itself, it says so there — and repeats it in the report.

### Left panel, top to bottom

1. **Target folder** — *Select Target Folder…* and *Analyze Folder*
2. **Calibration** — library path and the calibration switches (§7)
3. **Stacking** — rejection, weighting, quality filters, framing, background (§8)
4. **Colour** — palette, channel mapping, composition and auto-finish (§9, §10)
5. **Actions** — alignment, plate-solving, reuse, cleanup, and **Stack All Filters**

### Presets

Three presets set the whole option block at once:

| Preset | Intent |
|---|---|
| **Quick look** | "Does this data look good?" — no QA extras, no colour calibration, keeps every frame, saves a stretched preview |
| **Balanced** | The sensible default for a normal night: blank-frame detection, weighting, per-channel background extraction, full auto-finish |
| **Final** | Everything on: quality filtering (weighted FWHM + roundness), rejection maps, plate-solved masters |

You can also save and load your own complete configuration as a `.json` file.

---

## 7. Calibration

Everything here is **optional and additive**. The script uses whatever it finds and skips the rest; with no calibration frames at all it behaves exactly as it did before calibration support existed.

### Where frames come from

- **Flats** are expected next to your lights, per filter, per session. Both layouts work: inside the target folder, or beside it in a sibling `FLAT/` directory.
- **Darks and bias** come from the **Library** folder — a place you set once and reuse for months. It may hold raw frames (which get stacked into masters) or ready-made masters; a group of exactly one file is adopted as-is.

A library is meant to grow, so **only the darks this run can actually use are stacked** — judged by the same rule that will later pick one. Five exposures at three setpoints are fifteen masters; building fourteen of them to open one would cost minutes and read hundreds of frames for nothing.

Only calibration is taken from outside the target folder. A *light* frame sitting in the library or a neighbouring folder is counted and reported, never stacked into your target.

### How masters are matched

Matching runs on **FITS headers, not filenames**:

| Property | Tolerance |
|---|---|
| Camera (`INSTRUME`) | exact, where both headers name it |
| Exposure time | within 5 % — nearest wins |
| Gain | exact |
| Binning | exact |
| Image dimensions | exact |
| Sensor temperature | ±2 °C |

The **camera** is part of the key because image size and binning are only a proxy: two bodies sharing a sensor format would otherwise calibrate each other. A value missing from a header never blocks a match — except the exposure, where an unreadable `EXPTIME` reads as 0 s, and 0 against 120 is exactly the mismatch that must not slip through.

**Exposure is a tolerance, not an identity.** The thermal signal scales with exposure, so a 290-second dark removes very nearly what a 300-second one would, while refusing it would leave the lights uncalibrated — the worse outcome. The nearest dark inside the band is used and **named in the log**, with everything else confirmed to agree. Beyond it the run continues without a dark and says so: a 60-second dark on 300-second lights is 80 % off and is never applied.

**A filter that mixes exposures, or nights, is calibrated in parts.** Two masters bind a part of the frames rather than all of them, and each contributes one dimension. A dark only removes the thermal signal that grew during *its own* exposure, so a single dark applied to 120-second and 300-second subs is right for neither. A flat only describes the optical train it was shot through, so with *Match flats to the same night* on, each night wants its own.

The two are independent, so the parts are their cross product, and a dimension with a single value drops out of it: no darks means the exposure never splits, one master flat means the night never does. Each part is staged separately, calibrated with its own masters, and the calibrated parts are merged again (`merge`) before registration — so the channel still ends as **one** master, which is what the colour composite needs. The report names every channel this happened to, and which dimension split it.

**Flats pooled across nights are checked against each other.** Nothing in the headers says whether the optical train moved between two sessions — but dividing one night's flats by another's does: a matching pair gives a uniform image, a mismatched one shows the vignetting or dust that shifted. Each night is normalised by its own median first, so a brighter panel or a fading twilight sky is not counted as disagreement; what remains is the shape.

Two steps happen before the spread is read, and the thresholds below are meaningless without them. Every frame of a night is **averaged**, standing in for the master flat that does not exist yet at this point in the run; and the map is **binned** to about 250 px on the long side. Vignetting and dust are hundreds of pixels across and survive both untouched, while photon noise — which on a single 24 000 ADU sub runs to 1.8 %, six times the limit below — does not.

| Spread of the ratio | Reading |
|---|---|
| under 0.15 % | the nights agree — pooling is right |
| 0.15 % – 0.30 % | usable, noted in the report |
| above 0.30 % | the train was probably touched; the report names the nights and points at *Match flats to the same night* |

The check also measures its own **noise floor**: the reference night is split in half and compared with itself, and since two halves of one night differ by nothing but noise, whatever that returns is the error bar on the number above it. A difference that does not clear the floor is reported as "no shape difference is detectable" rather than as a figure — each half averages half as many frames as the night-to-night comparison, so the floor is a deliberately conservative bound.

The check is silent when there is only one night or when the frames cannot be read. With *Match flats to the same night* on it still runs and is still reported — the number is what shows the split is earning its extra stack — but it stops being a warning, and it never advises switching on something that is already on. Method and thresholds come from the **Flat On Flat Analyzer** by Carlo Mollicone in the official Siril script repository, including the averaging and the binning.

**One master flat per night.** With *Match flats to the same night* on, every night that has both flats and lights of a filter gets its own master flat, and only that night's lights are divided by it. The calibrated nights are merged again (`merge`) before registration, so the filter still ends as **one** master — splitting is a calibration concern, not a stacking one.

Two conditions have to hold for a night to get its own master: it must have flats **and** lights of that filter. Flats from a night the filter never imaged would build a master nothing opens; a night with lights but no flats has to fall back to a pooled master, and the log and the report name it rather than absorbing it silently. Fewer than two qualifying nights means there is nothing to keep apart, and the ordinary pooled master is used.

The pooled master is built even when every night has its own. It is the fallback on two paths reached at a point where stacking one is no longer safe — a light night whose flats are missing, and a per-part calibration that fails and drops back to a single pass.

**The split trades flat noise for flat accuracy.** A pooled master averages every night's frames; a per-night master averages only that night's. Below ten flats in a night the log says so, because that is where the trade starts to matter — worth it when the optical train really moved, wasteful when it did not. If you shoot flats every night through a panel, ten to twenty per filter per night keeps both properties.

**Darks are also grouped by temperature**, so a −10 °C and a −20 °C set can never be averaged into a single master that is correct for neither. Bias is not split that way — it is temperature-independent.

### The options

| Option | What it does |
|---|---|
| **Apply calibration when frames exist** | Master switch. Off = stack raw lights, as before. |
| **Cosmetic correction (hot pixels)** | `-cc=dark` — removes hot and cold pixels using the dark's own statistics. Requires a dark. |
| **Match flats to the same night** | Builds one master flat **per night** and divides each night's lights by its own, then merges the calibrated nights again before registration. Turn this on if the optical train was touched between sessions; leave it off to pool flats for a lower-noise master. |

### The flat offset chain

Flats need their own offset removed before they can normalise anything. The script degrades in four steps and never aborts:

1. a real **dark-flat** or **bias** master, if one matches,
2. a plain **DARK shot at the flats' exposure** (within 20 %) — a dark at the flat exposure *is* a dark-flat, whatever `IMAGETYP` calls it, and flat exposures are short enough for the difference to stay negligible,
3. Siril's **synthetic bias** `=64*$OFFSET`,
4. no offset correction at all — the flat is stacked directly.

Masters are cached in `calib/` under readable, header-derived names such as `M101_RED_-10C_3s_G100_flat` and reused by later runs.

---

## 8. Stacking Options

### Rejection — chosen per filter, from the frame count

Outlier rejection removes satellites, cosmic rays and aircraft. Which algorithm works depends entirely on how many frames it has to work with, so the script picks per channel:

| Frames | Algorithm | Why |
|---|---|---|
| ≤ 4 | **Percentile clipping** 0.2 / 0.1 | Sigma methods need a population; with three frames a standard deviation means nothing |
| 5 – 10 | **Sigma clipping** 3 / 3 | The cheapest thing that works once there are more than a handful |
| 11 – 30 | **Winsorized sigma** 3 / 3 | Robust, the workhorse for a normal night |
| 31 – 300 | **GESDT** 0.3 / 0.05 | Generalized Extreme Studentized Deviate Test |
| > 300 | **Linear fit** 5 / 4 | Models a trend *across* the stack, so it needs a long one to define |

These band edges are **Cyril Richard's**, taken from [AMSP](https://gitlab.com/free-astro/siril-scripts/-/blob/main/preprocessing/AMSP.py) in the official Siril script repository. He wrote Siril and implemented these algorithms, so his thresholds carry more weight than our own reasoning did.

GESDT's two numbers are **not** sigmas — they are the maximum rejected fraction and a significance level. A Siril build that does not know the token falls back to linear fit, and the report names the algorithm that *really* ran, so a fallback cannot hide behind the preferred one.

The tier is chosen for the frames that are **actually integrated**, not the ones that were found. A sub without enough detectable stars cannot be registered, and Siril excludes it; the script counts what Siril really exported. On one real night, 3 of 6 OIII frames were lost to cloud — the surviving 3 got percentile clipping, where the naive count would have applied sigma clipping to three frames and rejected nothing at all.

**The master flats, darks and bias go through the same table.** They used to be stacked with a bare `rej 3 3` — and a bare `rej` selects Siril's default, which is winsorized: the band meant for 11–30 frames, applied to a per-night master flat of five and to a library dark of four hundred alike. On one M 16 run that meant sigma clipping for the five- and ten-frame flats and a linear fit for the 442-frame dark set, neither of which they were getting.

Rejection stays **on** for calibration masters even when the switch is off for the light stacks. That switch is about integrating your own frames; a cosmic ray left in a master flat reaches every light that master divides.

**The count is measured, not estimated.** After registration the script asks Siril for the sequence it produced — `get_seq()` hands back which frames are still included and, for each of them, the FWHM, roundness and star count Siril measured. Those numbers stand in the report as measurements, in their own table.

This matters beyond the report: the quality filters run at *registration* time, so the exported count already has them applied. Subtracting their share a second time — as the script used to, for both the report and the rejection band — chose the algorithm for a smaller population than the one being integrated. A channel of 34 exported frames was treated as 30, which is a different band. An estimate now stands in only when the sequence cannot be read at all, and the report marks it with `≈`.

What Siril hands back also goes into `output.md` as a table of its own:

| Filter | Integrated | Median FWHM | Roundness | Stars |
|---|---:|---:|---:|---:|
| HA | 29 of 31 | 3.14 px | 0.88 | 412 |
| OIII | 12 of 12 | 3.90 px | — | — |

Roundness is 1.00 for perfectly round stars; well below that means trailing. The star count is Siril's own detection on the reference layer — a channel far below the others usually means the filter simply passes less light, not that anything went wrong. A value Siril did **not** record shows as `—`, never as `0.00`: a zero there would read as catastrophic trailing or an empty field, when the truth is that the measurement is absent.

The technique comes from **RegistrationInspector** by Cecile Melis and the **Sequence Statistics Analyzer** by Carlo Mollicone.

### Frame weighting

| Method | Best for |
|---|---|
| **Weighted FWHM** (default) | Broadband — sharpness scaled by star count |
| **Noise** | **Narrowband** — a sparse star field would otherwise be penalised for the filter rather than for the frame |
| **Number of stars** | Nights where transparency varied a lot |

### Frame quality filters

Four filters — **Weighted FWHM**, **Roundness**, **Star count**, **Background level** — in two modes:

- **% best** (1–100): keep that percentage of the best frames. `90` drops the worst tenth.
- **k-sigma** (1–10): reject frames further than *k* standard deviations from the mean.

The value boxes follow the mode, so a percentage can never be silently reinterpreted as a sigma multiple.

They are applied at **registration time**, so rejected frames are never even re-projected — and only from **20 frames** per filter. Below that, losing a sub costs more signal-to-noise than the worst frame costs sharpness. The log warns when the filters drop more than 15 % of a set, with the resulting noise increase.

### Framing, background and the rest

| Option | Notes |
|---|---|
| **Crop stacking edges (min framing)** | Keeps only the area every sub covers. Dithering costs a thin strip (a real run: 3008 px → 2991 px). This is a framing choice inside `seqapplyreg`, not a crop applied afterwards. |
| **Background extraction per channel** | Removes the sky gradient from each finished master while still linear. Gradients differ per filter, so this works better per channel than once on the colour image. Optionally with an **RBF** model, which follows a gradient that changes direction across the frame where a degree-1 polynomial can only tilt it one way. |
| **Background extraction per sub-frame** | Slower; the per-sub pass stays polynomial, per Siril's guidance. |
| **Skip blank / black frames** | Drops all-zero, dead-flat or corrupt frames before they break registration. |
| **Save rejection map (QA)** | Writes what was rejected, per channel, into `qa/`. |
| **Drizzle** | Needs **dithered** subs and enough of them. Below ~40 frames the log and the report warn that it will likely add noise instead of resolution. |
| **Register via plate solving** | With optional distortion master; falls back to star alignment automatically. |
| **Output normalization** | Rescales the finished master into `[0, 1]`. See below — it does more than the name suggests. |

### Output normalization is affine, and per channel

On 32-bit output Siril implements it as

```c
fit->fdata[i] = (fit->fdata[i] - mini) / (maxi - mini);   /* median_and_mean.c */
```

where `mini` and `maxi` are **that master's own** darkest and brightest pixel. Two things follow, and neither is obvious from the option's name:

- It **subtracts an offset** as well as scaling, so it is an affine transform, not a gain.
- The two numbers come from **single extreme pixels**, and each filter gets its own pair. The channels therefore leave the stack on three unrelated scales.

For a picture that is harmless — you are going to stretch anyway, and SPCC fits one factor per channel and absorbs it. It matters when the **absolute levels** do: photometry, or comparing the Ha/OIII ratio between runs. If that is what you are after, switch it off — and note that *Normalize narrowband channels* is not the only thing standing between you and the physical line ratio.

### When registration cannot do everything

`register -2pass` and `seqapplyreg` fail for unrelated reasons, so they are handled separately — only the first says anything about two-pass support.

If two-pass registration fails, the run falls back to single-pass `register`, which knows neither `-framing=` nor any `-filter-` option. The crop and the quality filters therefore cannot be honoured on that channel. What was given up is **recorded per channel and named in the report**, never silently dropped.

---

## 9. Palettes & Channel Mapping

### First: what the four dropdowns are

The panel shows **L / R / G / B** — that is the *channel mapping*: which stacked master ends up in which colour channel. It is not a list of "filters this palette uses". Two things are therefore easy to misread:

- **Not every palette fills all four.** RGB, SHO and HOO leave **L** empty, because they have no luminance channel. A Luminance filter you shot is then simply not read.
- **A filter can be used without being mapped.** HaRGB is the case where this bites: it is blended into Red rather than assigned to a channel, so it has no dropdown at all (see below).

Everything the dropdowns *do* show can be overridden by hand.

---

### LRGB — the standard broadband palette

| | |
|---|---|
| **Mapping** | R = Red · G = Green · B = Blue · **L = Luminance** |
| **Needs** | Red, Green, Blue. Luminance optional but that is the point of LRGB |
| **Output file** | `TARGET_RGB.fit` — plus the L master, kept separate |

The luminance is deliberately **not** part of the composite. Siril's recommended order is: compose R/G/B only, colour-calibrate that linear RGB, stretch it, stretch L on its own, and combine them **last**. That is why the file is called `_RGB` even though you selected LRGB — the name reflects what is actually inside it. `todo.md` then has a Part B (luminance) and a Part C (combine).

Switch **Quick linear LRGB** on to bake L in during composition instead. The file is then called `_LRGB`, and §10 explains what it costs you in colour accuracy.

---

### RGB — broadband without luminance

| | |
|---|---|
| **Mapping** | R = Red · G = Green · B = Blue (**L stays empty**) |
| **Needs** | Red, Green, Blue |
| **Output file** | `TARGET_RGB.fit` |

Identical to LRGB minus the luminance handling. If you have a Luminance filter and pick RGB, that filter is not read at all — and with *Stack only the filters this palette uses* on, it is not even stacked. Choose this when you have no L, or when you want the RGB alone.

---

### SHO — the Hubble palette

| | |
|---|---|
| **Mapping** | **R = SII** · **G = Ha** · **B = OIII** (L stays empty) |
| **Needs** | all three narrowband filters |
| **Output file** | `TARGET_SHO.fit` |

All three channels are mapped normally — SHO is the most straightforward palette in that sense. It is also the one people most often select without the data for it: **without an SII filter the Red channel has no source**, and the script says so the moment you pick the palette rather than after a full run.

Ha is far stronger than SII and OIII in most objects, so the raw combination comes out green. Two mechanisms deal with that, and §10 explains why you should use only one at a time: **Normalize narrowband channels**, or SPCC in narrowband mode.

---

### HOO — two filters, three channels

| | |
|---|---|
| **Mapping** | **R = Ha** · **G = OIII** · **B = OIII** (L stays empty) |
| **Needs** | Ha and OIII — that is all |
| **Output file** | `TARGET_HOO.fit` |

Note that **OIII appears twice**: it feeds Green and Blue. That is why two filters are enough, and why the composition step reads the same master three times.

One consequence is worth knowing, because it looks alarming in the log: SPCC reports the Blue/Green fit as

```
Image B/G = 1.000000 + 0.000000 * Catalog B/G (sigma: 0.000000)
```

That is not a failure. Blue and Green *are* the same image, so their ratio is exactly 1 everywhere and there is nothing to fit. Only the **R/G** line carries information for a HOO composite.

---

### HaRGB — broadband with an Ha admixture

| | |
|---|---|
| **Mapping** | R = Red · G = Green · B = Blue · L = Luminance |
| **Plus** | the **Ha master is blended into Red**, at the **Ha → Red** strength |
| **Needs** | Red, Green, Blue — *and* an Ha filter, which is not mapped |
| **Output file** | `TARGET_HaRGB.fit` (or `TARGET_RGB.fit` if no Ha was found) |

**This is the palette where the dropdowns mislead.** HaRGB keeps the ordinary broadband mapping — R, G, B, L exactly as in LRGB — and mixes Ha into the Red channel *on top of it*:

```
R' = 1 − (1 − R) · (1 − k · Ha)        k = "Ha → Red" / 100
```

A screen blend, so it brightens the Red channel where Ha is strong without ever exceeding 1. Because Ha does not *replace* a channel, it has no dropdown of its own — the script finds it automatically by filter role among the aligned masters, and the Log names the one it picked:

```
HaRGB will blend HA into Red — Ha is an admixture, not a mapped channel.
HaRGB: blending HA into Red at 50% (PixelMath).
```

If none of your filters carries an Ha role, selecting HaRGB now says so immediately; without that check the run would go all the way through and quietly produce plain RGB.

Two further specifics:

- **Colour calibration is skipped for HaRGB.** With Ha blended into Red, star photometry no longer describes that channel, so any photometric calibration would be measuring the wrong thing. The saved composite is labelled *uncalibrated* — balance it by hand.
- **The luminance is still kept separate**, exactly as in LRGB, and combined after stretching.

**How much Ha actually goes in.** The blend is `1-(1-R)·(1-k·Ha)` — a screen blend, and on *stretched* data that is a meaningfully different thing from adding. On **linear** data it is not. At typical linear brightness (0,001–0,01) the two agree to better than 0,1 %:

| R | Ha | screen blend | R + k·Ha |
|---|---|---|---|
| 0,002 | 0,003 | 0,003497 | 0,003500 |
| 0,02 | 0,03 | 0,034700 | 0,035000 |
| 0,4 | 0,6 | 0,580000 | 0,700000 |

So the slider adds a fraction of Ha to Red, and nothing more subtle than that. The screen form still earns its place — it can never exceed 1,0, so a bright star core cannot be pushed into clipping — but the highlight compression a screen blend gives *after* a stretch is simply not happening here. Redo the blend post-stretch if you want that behaviour.

---

### The other narrowband assignments

SHO and HOO are the two everyone knows. The rest are the same idea with the lines in other places — all of them **pure assignments**, where a channel is copied rather than computed:

| Palette | Red | Green | Blue |
|---|---|---|---|
| SHO | SII | Ha | OIII |
| HOO | Ha | OIII | OIII |
| HSO | Ha | SII | OIII |
| HOS | Ha | OIII | SII |
| OSS | OIII | SII | SII |
| OHH | OIII | Ha | Ha |
| OSH | OIII | SII | Ha |
| OHS | OIII | Ha | SII |
| SOH | SII | OIII | Ha |
| HSS | Ha | SII | SII |
| HHO | Ha | Ha | OIII |
| OOS | OIII | OIII | SII |
| SHH | SII | Ha | Ha |
| SOO | SII | OIII | OIII |

That is all **six** ways to give three different lines to three channels, plus eight two-line variants. Each gets the same treatment as SHO: narrowband normalisation if enabled, and SPCC in narrowband mode with the wavelengths of the lines *this* palette put in each channel — the same table drives both, so a palette cannot be added with the wrong wavelengths sent to SPCC.

The set beyond SHO/HOO comes from **Cyril Richard's PalettePicker** in the official Siril script repository, and was checked against its source, Franklin Marek's **Perfect Palette Picker** in Seti Astro Suite Pro. That comparison is what added `SOH`, `HHO`, `OOS`, `SHH` and `SOO`: `SOH` was the one permutation missing from our own table, with nothing behind its absence.

---

### Realistic1 / Realistic2 — weighted mixes

These *mix* the lines instead of assigning them:

| Palette | Red | Green | Blue |
|---|---|---|---|
| Realistic1 | 50 % Ha + 50 % SII | 30 % Ha + 70 % OIII | 90 % OIII + 10 % Ha |
| Realistic2 | 70 % Ha + 30 % SII | 30 % SII + 70 % OIII | 100 % OIII |

The mixing runs through Siril's `pm`, and **colour calibration is skipped**: a channel that is 70 % Ha and 30 % SII has no single passband for SPCC to model — the same reason HaRGB is excluded.

---

### Why the palette list stops here

Every palette above is either an assignment or a weighted sum. That is not a coincidence, it is what a **linear** pipeline can honestly offer:

- **Assignments** move whole channels around. Linear or stretched, the result is identical.
- **Weighted sums** are linear combinations, so they too commute with the stretch.
- **Dynamic palettes** — Foraxx and its relatives — blend with a factor like `t^(1-t)` where `t = Ha·OIII`. On stretched data `t` spans [0,1] and the factor does real work. On linear data `t` is around 1e-6, `t^(1-t)` collapses towards zero, and the palette degenerates into "all OIII". They are **deliberately absent**.

  Perfect Palette Picker settles this from its own side. Its gate is `np.clip(x, 1e-6, 1.0) ** (1.0 - x)` — and its **Linear Input Data** checkbox does not teach that gate to read linear data. It *stretches first*, `stretch_mono_image(img, target_median=0.25)`, and builds the palette from the stretched copy. Median 0.25 is where the gate has slope: `0.25^0.75 = 0.35`, `0.5^0.5 = 0.71`. At a linear 0.01 it returns 0.0105 — that is `t ≈ x`, which is the same thing as no gate at all. The checkbox exists because the palette cannot work without the stretch.

Cyril Richard's PalettePicker states the same boundary from the other side: it dropped the ability to assemble *linear* images, because doing so would have forced an automatic stretch on the user. This script keeps the linear stage — which is where colour calibration belongs — and leaves the dynamic palettes to the tool built for the stretched stage.

---

### Synthetic luminance

A narrowband night has no Luminance filter, and the detail sits spread across two or three channels. **Build a synthetic luminance master** combines the emission-line masters into `masters/TARGET_SynthL.fit`, which carries their combined signal-to-noise.

**The average is unweighted, and that is a limitation.** An equal-weight mean is only SNR-optimal when the channels carry comparable signal, and in SHO they do not: SII regularly runs an order of magnitude below Ha. With signals 20, 2 and 1 at equal noise the mean gives SNR 13.3 where the strongest channel alone gives 20. So hold `SynthL` against your best single channel before you build on it — if one line dominates the field, that channel may simply be the better luminance.

A weighted version was written and taken back out in 1.7.8, for reasons worth knowing before you try it yourself. The weights that maximise SNR, w ∝ signal/noise², are **not invariant under a per-channel rescale** — and by this point every master has been through `-output_norm`, which rescales each one affinely by its *own* extremes, and possibly `linear_match` on top. The weights would follow those arbitrary factors rather than the sky. On top of that, measuring the noise well enough is its own problem: a background sigma computed outside Siril disagreed with Siril's own `bgnoise` by 1.1× to 4.0× across three masters of one M 16 run, worst exactly where nebulosity fills the frame. Squaring that error put Ha at 3.7 % of an M 16 SHO luminance. A scale-invariant rule (w ∝ signal/noise) fed by Siril's own `bgnoise` would be defensible; it is not built.

It is deliberately **not** combined into the colour image. A luminance combine on linear data lifts the bright end before colour calibration — the same mistake *Quick linear LRGB* makes, measured on real data at 531 clipped stars against 68. `todo.md` picks the file up as Part B and combines it after the stretch, where it belongs.

---

### Auto

**Auto** proposes a palette from the filters found, and only ever one whose three channels can actually be filled:

| Filters found | Auto picks |
|---|---|
| R, G, B **and** L | LRGB |
| R, G, B | RGB |
| SII, Ha, OIII | SHO |
| Ha, OIII | HOO |
| anything less | RGB, and the composition step names what is missing |

Broadband wins when it is complete, because it gives natural colour. HaRGB is never proposed automatically — it changes the Red channel deliberately, so it is always an explicit choice. Switch to SHO / HOO / HaRGB by hand for the mapped look.

If you pick a palette the filters cannot fill, the script says so **when you choose it**, not after a full run. It also refuses to skip filters in that situation, so you still end up with usable masters.

### Cross-filter alignment

Each filter is stacked against its *own* reference frame, so the masters can sit on slightly different pixel grids. To fix that, all masters are pooled into one small sequence, re-registered, and re-projected with `-framing=min`, producing channels that are **pixel-identical** in size and overlay exactly.

**This costs a second interpolation.** `seqapplyreg` runs twice on the way to a channel: once over the sub-frames of that filter, once over the three finished masters. Both use clamped interpolation, and each resampling softens the image a little. The single-resample alternative — registering the frames of *every* filter against one shared reference before stacking — would need that reference to carry enough stars for the sparsest narrowband channel, which is exactly the frame least likely to have them, and it gives up the per-filter reference that makes each stack as sharp as its own best night allows. The trade was made knowingly; the star-pair table in `output.md` is where you can see whether the second pass had enough to work with.

### How the composite is assembled

The three channels are read back out of Siril, stacked in memory and handed over as one RGB image (`new` + pixel data), then saved. Siril's `rgbcomp` remains as the fallback and is still the only route for the *Quick linear LRGB* `-lum=` combine, which is Siril's own luminance transfer rather than a channel copy.

The reason for the change is prosaic: `rgbcomp` does not honour quoted paths the way `cd` / `load` / `save` do, so a folder name containing a space split the filename. Composition used to work around that by changing into the masters folder and passing bare basenames. Reading the planes back through Siril also settles the orientation question by construction — whatever row order Siril hands out is the row order it gets back, so nothing has to interpret `ROWORDER`.

The report names which of the two routes actually ran.

### Stack only the filters this palette uses

**Off by default.** When on, filters the composite never reads are skipped entirely.

On an LRGB night processed as HOO that is four of six channels, so the run takes about half as long. But the bigger effect is on the picture itself, and it is worth understanding why.

Siril's two-pass registration **picks the alignment reference itself**, from whatever is in the sequence. That is the entire purpose of the preliminary pass, and `setref` cannot override it. A star-rich broadband master normally wins — which leaves the narrowband channels having to match a frame whose stars they barely share.

Measured on one M 16 night, same frames, same settings:

| | All six masters pooled | Only Ha + OIII |
|---|---:|---:|
| Alignment reference | Luminance | Ha |
| Star pairs matched for OIII | **12** | **1165** |
| SPCC R/G fit sigma | **5.76** | **2.73** |

A transform fitted on twelve points carries its scale term poorly, and that is what puts colour fringes in the corners.

Two situations make the script refuse to skip anything, and say why:

- the palette has a channel it cannot fill anyway — the composite will stop there regardless, and the other masters are worth more than the saved time;
- no composite is being made at all — without one, nothing reads a palette.

The trade-off: **a master that was never built cannot be reused later.** If you want to try several palettes from one night, leave this off for the first run.

---

## 10. Colour Calibration

### SPCC instead of PCC

**Spectrophotometric Colour Calibration** accounts for your sensor's and your filters' response curves. Siril's own documentation calls it the more accurate method and PCC obsolete — and for a mono rig behind a filter wheel that distinction matters, because plain PCC assumes generic broadband R/G/B.

On real data the difference shows up in the fit itself: the catalogue-vs-image slope went from ~3.0 under OSC assumptions to ~0.95 once the mono sensor and filters were described.

### Reading the fit — how much the white balance is worth

Siril compares each star's measured colour with the one predicted from its catalogue spectrum, and prints the **sigma** of that comparison. `output.md` now carries it, together with the star count and the white-balance factors that came out, because "colour calibration done" reads the same whether the stars followed the catalogue closely or scattered wildly around it.

| Sigma of a ratio fit | Reading |
|---|---|
| well under 1 | the measured colours follow the catalogue; the white balance is a measurement |
| above 1 | ⚠️ the solution is weak — it was still applied, but treat it as a starting point |

Siril prints its own *"imprecise solution"* warning, and that one does **not** separate these cases: on two runs of the same 94 frames it fired on both, while the sigmas differed by a factor of forty.

**Compare sigmas only between runs whose channels carry the same lines.** Two channels on neighbouring wavelengths — Ha at 656.3 nm and SII at 671.6 nm, say — give a ratio near 1 for every star, so the fit has almost no lever arm and its sigma comes out small because the measurement is *insensitive*, not because the solution is good. The number is a comparison tool between runs of one palette, not a ranking of palettes.

On narrowband the usual cause of a genuinely large sigma is *Normalize narrowband channels*: it flattens the very line ratio SPCC then tries to calibrate. A channel aligned on few star pairs does it too — see the star-pair table in the same report.

### Getting the names right

A sensor or filter name Siril does not recognise is **not an error for Siril** — it quietly substitutes something else. The classic trap:

> `IMX533` exists only in the **OSC** tables. Enter it, and your filter-wheel rig gets calibrated as a one-shot-colour camera, silently. The mono entry for the same chip is **`Sony IMX411/455/461/533/571`**.

The script reads the SPCC database Siril itself uses (read-only, located via sirilpy) and reports a name that is missing, ambiguous or only a partial match — before the run gets that far. A database it cannot find means *cannot check*, never *invalid*.

You can also list the valid names from Siril's own command line:

```
spcc_list monosensor
spcc_list redfilter
```

The fields ship **pre-filled for the author's rig** — Player One Ares-M Pro (IMX533 mono) with Antlia LRGB V-Pro and 4.5 nm Edge SHO filters. Overwrite them for your own kit; they are remembered. Leaving them blank falls back to whatever is configured in Siril's own SPCC dialog.

### Narrowband gets calibrated too

With SHO or HOO the script runs SPCC in **narrowband mode**, describing each mapped channel by its emission line — Ha 656.3, OIII 500.7, SII 671.6 nm — plus the bandwidth you set (fractional values like 4.5 nm are supported). Ordinary star photometry is meaningless for mapped emission lines, so PCC is never attempted for these palettes.

Two details worth knowing:

- **The sensor name goes with it.** Siril's help says `-narrowband` makes it ignore "the previous *filter* arguments" — filters only. That is physics, not a quirk: the wavelengths describe the filter passbands, while the sensor's quantum efficiency at 656 and 501 nm is an independent factor in the same product.
- **The filter names are deliberately left out** in narrowband mode, and the log says so — because Siril echoes its stored names on every run, and they look as if they had been used.

### Normalisation and SPCC work against each other

**Normalize narrowband channels** linear-matches the SHO/HOO channels to the Ha reference, so a Hubble-palette stack does not come out green. It is useful — but not while SPCC is calibrating.

`linear_match` flattens the Ha/OIII flux ratio *on purpose*, and that ratio is exactly what SPCC's narrowband mode measures against catalogue spectra. Running both means the calibration is reading a quantity that was deliberately erased.

Measured on two runs of the same data, differing only in that option:

| | Normalisation on | Normalisation off |
|---|---:|---:|
| R/G fit sigma | 2.730 | **2.641** |
| Fitted slope | 1.251 | **1.209** (closer to 1 = less correction needed) |

The effect is real but modest — much smaller than the alignment effect above. **Recommendation:** leave normalisation *off* when SPCC is doing the calibration, and *on* when it is not. The log, the report and `todo.md` all say which one applies to your run.

### The fallback chain

Colour calibration degrades one step at a time and never aborts the finish:

1. **SPCC** with your sensor / filter names (or the narrowband wavelengths)
2. **SPCC** bare — whatever is configured in Siril's own preferences
3. **PCC** (NOMAD catalogue) — broadband palettes only
4. **PCC** against a local Gaia catalogue — works offline
5. give up, and say so plainly in the report and in `todo.md`

### HaRGB is excluded on purpose

Its Red channel carries blended Ha, which makes star photometry invalid. The script skips colour calibration there, says so, and the saved composite is described as **uncalibrated** — balance it by hand.

### Quick linear LRGB

By default, **luminance stays separate** for LRGB: the RGB is calibrated on its own, and L is combined *after* stretching. That is Siril's recommended order.

**Quick linear LRGB** bakes L in during composition instead. It is faster and sometimes convenient, but it lifts the bright end, so more stars saturate and drop out of the photometric fit. Measured on two runs over the same R/G/B masters:

| | L kept separate | L baked in |
|---|---:|---:|
| Stars rejected as *pixel out of range* | 68 of 2603 | **531 of 2597** |
| Stars carrying the solution | 1484 | 1057 |
| R/G fit sigma | 1.148 | 1.334 |

If you use it, the report and `todo.md` both note that the resulting white balance is good-but-approximate.

### What auto-finish does — and the one thing it deliberately does not

```
platesolve → subsky → SPCC (or PCC) → save, still linear
```

**Green removal (SCNR) is not part of it.** Siril computes it as

```
green = min(green, (red + blue) / 2)
```

which is exactly right for a broadband image — nothing in the sky is genuinely green, so a green cast is colour noise. On an **assignment palette it is not**: the green channel carries a real emission line. In SHO that line is Ha, the strongest signal in most nebulae, and the expression cuts it back to the mean of SII and OIII wherever it dominates. That is measured flux, not a cast. On one M 16 run it came to about 3 % of Ha on average, and considerably more in the bright pillars.

It is also **non-linear and per-pixel**, so running it would break the one property the composite is handed over with. The script applies the same reasoning to the magenta-star remedy (`invert` → `rmgreen` → `invert`) and now applies it consistently: `todo.md` carries green removal as a step of your own, after the stretch, where you can see what it costs.

---

## 11. Output Files

```
output/
├─ TARGET_RGB.fit        the finished colour image (linear, calibrated)
├─ TARGET_RGB_preview.fit stretched preview, if enabled
├─ masters/
│   ├─ TARGET_FILTER.fit            aligned — use these to combine channels
│   └─ TARGET_FILTER_29x300s_G100_-10C_fullframe.fit
│                                   full, uncropped stack
├─ output.md             what the script did, step by step
├─ todo.md               step-by-step final-processing guide
├─ calib/                master dark / flat / bias — reused next run
├─ qa/                   rejection maps (if enabled)
└─ _work/                intermediates — safe to delete
```

**`masters/` holds two versions per channel.** The `_fullframe` file is the stack in its own geometry; the plain one has been re-projected onto the common grid and is the one to use for channel combination.

The full-frame name carries the recipe: **frames integrated × exposure, gain, sensor temperature** — `M16_HA_29x300s_G100_-10C_fullframe.fit`. The frame count is the one that survived registration, not the number staged, so the name can never promise more than the file holds. A channel that mixed exposures gets a plain `40subs` instead of an `NxT` that would be true for neither half. The aligned master keeps the short `TARGET_FILTER.fit` name because it is what `rgbcomp` and *Reuse existing masters* look for.

### The two documents

**`output.md`** is a full processing report: filters found, frames *found vs. actually stacked*, integration time, the rejection algorithm used per channel, which calibration master went into which filter, every option that took effect, and the auto-finish steps that really ran.

**`todo.md`** is a palette-specific guide for the creative part — stretching, colour balance, and for LRGB the final luminance combine, with concrete Siril menu paths.

### Both documents describe what actually happened

This is the design principle behind the reporting, and it is worth stating explicitly, because a report that describes the *usual* case is worse than no report:

- A filter that was skipped, that failed, or that an abort never reached is shown as such instead of being given a frame count. A filter the palette does not read says *not stacked* with that reason — not "the run was stopped".
- Predicted counts are marked as estimates (`≈`) or upper bounds (`≤`, k-sigma), never printed as if they had been measured.
- The rejection algorithm named is the one that really ran.
- "Did the quality filters apply?" is answered from what registration was actually told, not re-derived afterwards from a frame count that registration may have changed.
- An astrometric solution the composite *inherited* from plate-solved masters is distinguished from one computed for it.
- A composite that was never produced is not described as if it had been.
- The saved composite is called *calibrated* only when a calibration actually ran.
- Advice is never given for an option that was not the cause, and a tip is not offered when the run made it impossible.

---

## 12. Master Reuse

**Reuse existing masters** lets you try another palette without re-stacking:

- **Full reuse** — every aligned master exists: stacking *and* alignment are skipped, so you only pay for the composition (seconds).
- **Partial reuse** — some masters exist: the script keeps those and stacks only the missing filters.

What is skipped, and why, is always logged.

### Two things stop full reuse, both on purpose

1. **A master that was never built cannot be reused.** A run made with *Stack only the filters this palette uses* has to be repeated in full for a palette that needs the others.
2. **The aligned masters must all be the same size.** `-framing=min` crops to the intersection of whatever was aligned together, so a run over a subset leaves the remaining channels on the previous grid. Mixing those would hand `rgbcomp` channels of different dimensions — so the script re-aligns instead, and names the leftovers in the report.

Turn reuse **off** after changing stacking options or adding frames. Re-running is otherwise safe: existing outputs are overwritten.

---

## 13. Recommended Workflows

### A normal LRGB night

1. Preset **Balanced**, palette **Auto** (it will pick LRGB).
2. Leave *Stack only the filters this palette uses* **off** if you might want another palette later.
3. Leave *Quick linear LRGB* **off** — let SPCC calibrate the RGB alone.
4. Run. Then follow `todo.md`: stretch the RGB, stretch the luminance separately, combine them last.

### A narrowband night, best possible colour

1. Palette **HOO** or **SHO**.
2. Turn **Stack only the filters this palette uses** *on* — this is where it pays off most.
3. Turn **Normalize narrowband channels** *off* — let SPCC measure the real line ratio.
4. Set your filter **bandwidth** (e.g. 4.5 nm) and check the sensor name.
5. Run, then follow `todo.md`.

### Several looks from one night

1. First run: everything on, *Stack only the filters this palette uses* **off**, so all masters get built and aligned together.
2. Following runs: change the palette, tick **Reuse existing masters**, and re-compose in seconds.

### Just checking the data

Preset **Quick look** with *save stretched preview*. No colour calibration, no QA artifacts — you get a look at the night in a few seconds.

---

## 14. Troubleshooting

### "Colour composition skipped: the RED channel has no master"

The palette wants a filter you do not have — SHO takes Red from an **SII** filter, and none is mapped. The message names what the palette expects and which palette would work with your filters. Either switch palette, or map the channel by hand in the dropdowns.

The masters are still there and still usable; the run says *"Finished with N master(s), but NO colour image"* rather than reporting success.

### The colour looks wrong, and SPCC "found an imprecise solution"

Two usual causes, in order of impact:

1. **No flats.** Vignetting leaves a brightness gradient across the frame, and Siril will keep saying *"consider correcting the image gradient first"*. This is the single most effective thing you can fix, and no script setting substitutes for it.
2. **A wrong sensor name.** See §10 — check the Log for a name that did not match Siril's mono tables.

### A channel lost most of its frames

```
Registration dropped 3 of 6 frame(s) — 3 will be integrated.
Only 3 frame(s) left for OIII: too few for outlier rejection to mean much.
```

Frames without enough detectable stars — cloud, haze, a passing veil — cannot be aligned, and Siril excludes them. This is data, not a bug. Treat that channel as provisional, and shoot more of it.

### "FITS error: failed to find or open the following file"

Almost always a **cloud-synced working folder**. Siril's `link` creates symlinks, and Dropbox & co. rewrite them mid-run. Move the working tree to a local disk, or exclude `output/_work/` from syncing. See §3.

### "2-pass registration unavailable"

If this appears *together with* a missing-file error, it is the cloud-sync problem above, not a Siril version issue. The two failures are reported separately precisely so they can be told apart.

### Nothing changed after I edited the script

Siril keeps the loaded script in memory. Close the script window and start it again from the Scripts menu.

### The masters folder has files of different sizes

You ran with *Stack only the filters this palette uses* on, so only some channels were re-aligned. The report names the leftovers. Re-run with the option off to put every channel back on one grid.

---

## 15. Tips & Best Practices

- **Shoot flats.** Per filter, per session, before you take the rig apart. Nothing else in this list comes close in impact.
- **Build a dark and bias library once.** Cooled to a fixed setpoint, darks stay valid for months. Point the Library at a folder you keep, and forget about it.
- **Give narrowband more time than you think.** A 4.5 nm filter is dark. Six subs is enough to see something; it is not enough for rejection to mean anything.
- **Use noise weighting for narrowband**, weighted FWHM for broadband.
- **Do not stretch before calibrating.** The script hands over linear for a reason.
- **Read the Log when something surprises you.** Every fallback, every skipped step and every self-defeating combination is explained there in one sentence.
- **Keep `masters/`.** You can redo the whole colour process from those files without re-stacking, and they are what makes palette experiments cheap.
- **Magenta stars in a three-line palette are expected.** Stars are continuum sources: they land in the Red and Blue channels but not in the one carrying Ha, so SHO and its relatives turn them purple. The usual remedy runs *after* stretching — `invert` → `rmgreen` (SCNR) → `invert`. The script does not do it for you, because inverting linear data does not mean what inverting stretched data means; `todo.md` reminds you where it belongs.
- **Name your targets consistently** across nights (`M16`, not `M 16` in one session and `Eagle Nebula` in the next) — the script compares names normalised, but consistency keeps the folders tidy.

---

## 16. FAQ

**Does it work with a colour (OSC) camera?**
No, and deliberately so. Frames are never debayered. This is a mono filter-wheel workflow.

**Do I need calibration frames?**
No. Everything is optional and additive: with none at all, the script stacks raw lights exactly as it would have before calibration support existed. Flats give the biggest improvement.

**Can I combine several nights?**
Yes — put them under one target folder. The same filter from different nights is pooled into one stack automatically.

**Why is my image almost black?**
It is linear, which is correct. Open `todo.md` and follow the stretching steps, or enable *save stretched preview* for a quick look.

**Why does HaRGB have no colour calibration?**
Its Red channel carries blended Ha, so star photometry no longer describes it. Any photometric calibration would be measuring the wrong thing. Balance it manually.

**What happens if I close the window mid-run?**
It asks first, then finishes the current filter and stops there. Alignment, plate-solving, the colour image and the `_work/` cleanup are all skipped — a composite built from half the channels is not the image you asked for. The finished masters are kept, and log, report and dialog say *stopped*, not *done*. Re-run with **Reuse existing masters** to continue.

**Can I use it without an internet connection?**
Yes. Install a local Gaia catalogue in Siril, and the calibration chain will reach it. Without either, the composite is still produced — just uncalibrated, and the report says so.

**Does it modify my raw frames?**
No. Everything is written under `output/`, and the raw frames are only read.

---

## 17. What's New in 1.7.9

- **The log readers stop depending on a diagnosis.** 1.7.8 repaired one way the star-pair counts go missing; the very next run failed the same reader for the *other* reason — the log came back fine, the anchor simply was not in it. Siril's log is not the clean append-only stream both snapshot paths assume: stderr from other processes lands in it too, and on that run a relaunched multiprocessing resource tracker wrote a `PermissionError` traceback into the middle of the step being measured. So the readers now fall back to a **marker the step itself logs**: alignment anchors on the directory `register` announces, colour calibration on `Running command: <cmd>` — taken from the command list, not split out of a display label that is free to be reworded. Replayed against the real log, tracebacks included, both recover 1376 and 1392 star pairs with OIII as the reference: the numbers that sat two lines above the failure message. A log Siril hands back empty still reports nothing, which is the one honest answer left.
- **The warn-once flag is per diagnostic, not per run.** One shared boolean meant the first reader to fail silenced the second one's message too — on that run it swallowed an SPCC fit with σ 5.5 and 6.7 against a limit of 1.0, which is exactly the number worth seeing.
- **The calibration-rejection change from 1.7.7 is confirmed on real data.** It needed `output/calib` cleared first: the runs before that reused every cached master and never exercised it. With the cache cleared Siril echoes all four bands — linear fit 5/4 for the 442-frame darkflat set, sigma 3/3 for the five- and ten-frame per-night flats, winsorized 3/3 for the twenty-frame pooled one.

## What was new in 1.7.8

- **The weighted synthetic luminance from 1.7.7 is taken back out.** It never actually ran: `get_image_stats` returns nothing for a freshly loaded image when Siril has no statistics cached for it, so the measurement read a noise of zero, refused it, and every run fell back to the equal-weight average. Repairing that would not have helped, because the formula is wrong for these inputs — w ∝ signal/noise² is **not invariant under a per-channel rescale**, and by that point every master has been through `-output_norm` (affine, per channel, from its *own* extremes) and possibly `linear_match`. The weights would follow those arbitrary factors instead of the sky. Measured rather than argued: a background sigma computed here disagreed with Siril's own `bgnoise` by 1.1× to 4.0× across three masters of one M 16 run, worst exactly where nebulosity fills the frame, and squaring that error put Ha at 3.7 % of an SHO luminance — Ha being the strongest line in M 16.
- **The average is back, and now it is described instead of implied to be optimal.** The tooltip, the log line, `output.md` and §9 all say *equal-weight average*, say that a much fainter channel pulls the result down, and say to hold it against your strongest channel before building on it. A scale-invariant rule (w ∝ signal/noise) fed by Siril's own `bgnoise` would be defensible; it is not built, and the code records what it would take.
- **The log reader is fixed at its root, not patched again.** `get_siril_log()` returns nothing *without raising* on two paths inside sirilpy — a NONE status, and a response too short to carry the shared-memory handle — both meaning Siril declined the transfer. Three call sites turned that into an empty string, which reads downstream as a log fetched successfully that happens to be empty; the delta search then found nothing and the run announced a scrolled buffer. It had not scrolled: on the M 16 run the two star-pair counts, 1393 and 1377, sat two lines above that very message in Siril's own console. Nothing had been read at all. Falsy now means unreadable everywhere, the snapshot retries once (the refusal is momentary — the previous call in the same step had succeeded), and the warning names which of the three things went wrong instead of printing one guess for all of them.
- **The calibration-rejection change from 1.7.7 is untouched** — but note that cached masters are reused, so an existing `output/calib` has to be cleared before the new bands take effect. The first run after 1.7.7 reused every master and never exercised them.

## What was new in 1.7.7

- **Calibration masters now use the same rejection table as the light stacks.** They were stacked with a bare `rej 3 3`, and a bare `rej` selects Siril's default — winsorized, the band reserved for 11–30 frames. It was going to both ends of the range at once: a per-night master flat of five frames, where winsorizing estimates sigma from five points and replaces outliers with their own neighbours, and a library dark of four hundred, where a linear fit models the trend across the stack that winsorizing cannot see. On the M 16 run the five- and ten-frame flats move to sigma 3/3 and the 442-frame darkflat set to linear fit 5/4. Rejection stays on for calibration masters whatever the light stacks were told — that switch is about integrating your own frames, and one cosmic left in a master flat reaches every light it divides. §8 has the detail.
- **The synthetic luminance is weighted, not averaged.** It claimed "the combined signal-to-noise" while taking an equal-weight mean, which is optimal only when the channels carry comparable signal — and in SHO they do not. With signals 20 / 2 / 1 at equal noise the average gives SNR 13.3 where Ha *alone* gives 20: the luminance was coming out worse than the best channel inside it, and narrowband normalisation made it worse again by scaling the weak channel's noise up with its signal first. It now uses the matched-filter weights, w ∝ signal / noise², measured on each master through Siril's own statistics. Same three channels: 87 % / 9 % / 4 %, SNR 20.1. The log and the report name the shares, a channel over 80 % is called out, and an equal-weight average survives as a stated fallback when the statistics cannot be read. §9 has the detail.

## What was new in 1.7.6

- **The flat-on-flat check was measuring shot noise, not the optics.** It divided *one* flat of one night by *one* flat of another, pixel by pixel, and read the standard deviation. Two subs of the **same** night — where the shape difference is zero by construction — come out at **1.78 %** on a real 24 000 ADU flat, against a limit of 0.30 %. The check therefore reported "a real mismatch", six times over, on every dataset it has ever seen, and advised switching on an option to cure a difference that was not there. With that option already on, it printed the same number as the justification for the split.
- **The cause was borrowing thresholds without their method.** The 0.15 % / 0.30 % figures come from the *Flat On Flat Analyzer*, which compares two **master** flats and **block-averages** the map to ~250 px on the long side before it measures. On a 3008 px frame that is 12×12 binning; together with the stacking, the two steps take a factor of roughly 27 out of the noise. Both are now done here: a whole night is averaged to stand in for the master, and the binning reproduces the reference tool's.
- **The check now measures its own noise floor.** The reference night is split in half and compared with itself; two halves of one night differ by nothing but noise, so that number is the error bar. Below it the run reports "no shape difference is detectable" instead of a figure that means nothing. §5 explains both steps.
- **On the M 16 run this moves all three filters from "a real mismatch" at 1.78 % to agreement at 0.06–0.08 %**, against a floor of 0.06 %. The per-night masters of that same run agree to 0.027 %. Per-night flat calibration is unaffected and still worth using — it guards against a train that really did move. What changed is that its report no longer invents evidence for itself.

## What was new in 1.7.5

- **Output normalization is documented for what it actually does.** Read from Siril's source: on 32-bit output it is `(x − min) / (max − min)` with that master's *own* extremes — an affine transform per channel, driven by single pixels, not a shared scale. The tooltip claimed it normalised "the background level", and a run note claimed that switching off *Normalize narrowband channels* left the physical line ratio intact. Neither was true while this option was on. §8 now explains it, and the note names both options.
- **The second interpolation is stated.** `seqapplyreg` runs twice on the way to a channel — once over the sub-frames, once over the finished masters — and each resampling softens the image a little. §9 says so, and says why the single-resample alternative was not taken: it needs one shared reference carrying enough stars for the sparsest narrowband channel.

## What was new in 1.7.4

- **SCNR (green removal) no longer runs on the composite.** Siril computes it as `green = min(green, (red + blue) / 2)`. On a broadband image that is the right cure for colour noise; on an assignment palette the green channel carries a **real emission line** — Ha in SHO — and the expression cuts measured flux wherever that line dominates. About 3 % of Ha on average on one M 16 run, and considerably more in the bright pillars. It is also non-linear, so it broke the one property the composite is handed over with. `todo.md` now carries green removal as your own step, after the stretch, in both the broadband and the narrowband branch, and states what it computes.
- **The colour combination itself was checked against both reference implementations** — Cyril Richard's PalettePicker and Franklin Marek's Perfect Palette Picker. Both assemble the RGB the same way this script does (`new` + `set_image_pixeldata`), and both work on **stretched** input, which is why neither can colour-calibrate. Doing it linear, with SPCC and background extraction, is the difference — and the order (align → normalise → combine → plate-solve → background → calibrate) is right. Neither reference runs SCNR either.
- **Fixed: the SPCC name check had the same log-reading bug** as the two readers repaired in 1.7.2 — a third place assuming Siril's log only grows. It now goes through `_log_delta`, so a wrong filter name is still caught late in a long session instead of the check silently reporting "database not found".

## What was new in 1.7.3

- **Fixed: with *Delete `_work/` when finished* on, every filter failed at registration.** Siril's `merge` does not copy its source frames, it symlinks them — 30 frames written in 4 ms is not a copy of 30 × 36 MB. Freeing the calibrated parts right after the merge therefore turned the merged sequence into dangling links, and registration died with *failed to find or open merged_HA_00001.fit* on all three channels. The parts are now freed after registration has written frames of its own.
- The fault was latent for as long as the per-part path existed, but it only fired when a filter mixed exposures **and** the cleanup option was on. Since 1.6.0 splits every multi-night run by night, it became universal — for anyone who ticks that box.

## What was new in 1.7.2

- **The two log-reading diagnostics had quietly stopped working.** The star-pair counts and the new colour-fit numbers are read from Siril's own log by comparing a snapshot taken before a step with one taken after. That comparison assumed the log only ever grows — but its buffer is bounded, and on a full three-filter run the oldest lines drop off the front, after which no earlier snapshot is a prefix any more. Both readers then returned without a word, so a diagnostic that had stopped working looked exactly like one with nothing to say.
- **The delta is now anchored on the tail of the snapshot** instead of its head, which survives a trimmed front. If even that anchor is gone, the run says so once and names the consequence — nothing about the image changes, these are diagnostics.

## What was new in 1.7.1

- **`output.md` now says how well the colour solution fitted.** Siril prints the sigma of each ratio fit — how far the measured star colours scatter around the ones predicted from catalogue spectra — and the script used to drop it, so "colour calibration done" read the same for a solid solution and a hopeless one. The report carries the sigmas, the star counts and the white-balance factors, and a sigma above 1 is flagged. See §10.
- **Siril's own "imprecise solution" warning does not separate those cases**: on two runs of the same 94 frames it fired on both, while the sigmas differed by a factor of forty. The sigma does separate them.
- **With a caveat the report states itself:** two channels on neighbouring wavelengths give a ratio near 1 for every star, so that fit's sigma is small because the measurement is insensitive, not because the solution is good. Compare sigmas within a palette, not across palettes.

## What was new in 1.7.0

- **Five more narrowband palettes: `SOH`, `HHO`, `OOS`, `SHH`, `SOO`.** The table was checked line by line against Franklin Marek's **Perfect Palette Picker** in Seti Astro Suite Pro, the source Cyril Richard's PalettePicker adapted. `SOH` turned out to be the one permutation of three different lines our own table was missing, with nothing behind its absence. All six permutations and eight two-line variants are offered now, and the suite fails if one goes missing again.
- **The Realistic1 / Realistic2 coefficients were verified against that same source** and match it exactly, digit for digit — a table we had only second-hand until now.
- **§9's account of the dynamic palettes is confirmed from the other side.** Perfect Palette Picker's *Linear Input Data* checkbox does not teach its `x^(1-x)` gate to read linear data: it stretches to `target_median=0.25` first and builds the palette from the stretched copy. The checkbox exists because the palette cannot work without the stretch.

## What was new in 1.6.2

- **The Discovered Filters table is sized for the rows it has.** Its height came from the content's ideal rather than the rows' own, so three filters were clipped a row and a half short — behind a scroll bar over a table with nothing to scroll. Hiding the Details column also hid the *stretching* column with it, leaving a blank panel on the right.
- **The calibration summary says where the frames came from** — `Next to the lights: 60 flats` / `From the library: 442 darks at 3s`. Choosing a Library folder used to produce a path and no visible consequence, so a library that contributed nothing looked exactly like one that contributed everything. A chosen folder that gave the run nothing now says so in warning colour.

## What was new in 1.6.1

- **The Discovered Filters table says what will happen, not what was found.** The Flats column counted flats in the folder — on a rig with an automatic panel that is the same number for every filter, while the fact that mattered was invisible: those 300-second lights get **no dark at all**. The **Calibration** column now names the masters that will really reach each filter (`Dark + Flat ×3`, `Flat`, `none`), and a `⚠` in warning colour marks a filter with no dark. The tooltip names the exposures the library does hold and what would fix it.
- **The calibration summary moved below the switches it describes**, and shrank from four lines to one. Per-filter prose that repeated the table row by row now goes to the log, where length is free; the label carries library-level facts and the no-dark gap.
- **The table sizes itself to its rows**, and the Details column (exposure / gain / setpoint) steps out from under the table while every filter shares one value.
- **"Analyze Folder" is now "Re-scan Folder"** — selecting a folder has analysed it for some time, so two stacked buttons looked like two steps of a sequence, one of which had already run.

## What was new in 1.6.0

- **The flats' offset is chosen per filter.** An automatic flat panel sets the exposure per filter; the offset now matches *that* exposure — a dark-flat for the filter, else a dark within 20 % of its flat exposure, else the bias. Previously one offset served the whole run, and two filters with different flat exposures made it fall back to the synthetic offset for **all** of them.
- **The calibration panel previews that decision** before the run: per filter, how many flats at what exposure and what they will be offset-corrected with. A filter the library cannot serve is named.
- **"Match flats to the same night" builds one master flat per night.** It used to drop flats from nights that had no lights — which changes nothing when every night has both, the ordinary case for an automatic panel. Now each night with flats *and* lights gets its own master, that night's lights are divided by it, and the calibrated nights are merged again before registration, so the filter still ends as one master.
- **A night whose flats are missing is named, not absorbed.** It falls back to a pooled master, and the log, the calibration panel and `output.md` all say which night and why.
- **The agreement check keeps measuring when the option is on.** The number is what shows the split is worth its extra stack; it simply stops being a warning. When the option is on but cannot help — only one imaged night has flats of its own — it says that instead of advising you to switch on what is already on.
- **The report names which dimension split a channel** — exposures, nights or both — and lists the master flat each night received.

## What was new in 1.5.0

- **Eleven more palettes** — the narrowband assignments HSO, HOS, OSS, OHH, OSH, OHS and HSS, plus the weighted mixes Realistic1 and Realistic2. One table drives the mapping, the dropdown, the channel messages, the SPCC wavelengths and this manual, so none of them can drift apart. See §9.
- **The dynamic palettes are deliberately absent**, and §9 says why: their `t^(1-t)` blend factor collapses on linear data. The same arithmetic is now stated for the Ha→Red slider, which at linear levels adds a fraction of Ha and nothing more.
- **The composite is assembled in memory** and `rgbcomp` became the fallback — which removes the workaround for its handling of paths containing spaces. It remains the only route for the *Quick linear LRGB* luminance transfer. The report names the route that ran.
- **Optional synthetic luminance** for narrowband nights: the emission-line masters averaged into `masters/TARGET_SynthL.fit`, deliberately not combined into the colour image.
- **A filter that mixes exposures is calibrated in parts** — each exposure with its own dark, merged again before registration. A dark only removes the thermal signal that grew during its own exposure.
- **The full-frame master's name carries the recipe**: `M16_HA_29x300s_G100_-10C_fullframe.fit`, with the frame count that survived registration.
- **Alignment quality is reported.** The number of star pairs each channel matched on is read from Siril's log, and a channel far below its siblings is named.
- **Calibration masters are built on demand**, the camera is part of the matching key, a dark within 5 % of the exposure is used and named, and a plain DARK at the flats' exposure is accepted as their offset.
- **The integrated frame count is measured**, read back from Siril's own registration data — which also uncovered the quality filters being subtracted twice. The report gains a measured FWHM / roundness / star-count table.
- **Intermediates are freed one generation at a time**, holding peak disk usage at about two generations instead of four.
- **Flats pooled across nights are checked against each other** before they are combined.
- **A sirilpy floor and a capability report.** The script refuses to start below sirilpy 1.0.0 (what Siril 1.4 ships) with one clear sentence, and above that floor it names any optional call this module lacks — at startup and in `output.md` — together with what it changes.
- **The SPCC name fields complete as you type**, from Siril's own database.

## What was new in 1.4.0

- **Stack only the filters this palette uses** (off by default) — halves a typical run and, more importantly, keeps the cross-filter alignment reference among the channels that end up in the picture. See §9 for the measurements.
- **The SPCC sensor is sent in narrowband mode too.** `-narrowband` makes Siril ignore the *filter* arguments only; leaving the sensor out never failed, it silently used whatever the SPCC dialog last held.
- **Narrowband normalisation and SPCC** are flagged when both are on, and the recommended pairing is recognised as such instead of being reported as a gap.
- **Registration failures are diagnosed, not guessed at.** `register -2pass` and `seqapplyreg` are handled separately, and options the fallback could not honour are recorded per channel.
- **Full master reuse is refused when the aligned masters are not all the same size**, which can happen after a palette-only run.
- **A long list of reporting corrections** — a run without a composite no longer reads as if it had one, a skipped calibration is no longer called *calibrated*, and advice is never given for an option that was not the cause.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Gradient Analyzer
- Svenesis Blink Comparator
- Svenesis Annotate Image
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Satellite Trail Cleaner
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
