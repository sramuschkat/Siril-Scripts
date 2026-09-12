# Svenesis ImageMono Train — User Instructions

**Version 1.7.19** | Siril Python Script for Monochrome Filter-Wheel Stacking and Colour Composition

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
17. [What's New in 1.7.19](#17-whats-new-in-1719)

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
4. Selecting the folder analyses it straight away — **Re-scan Folder** is there for afterwards, once you add frames or change the Library. Three tables follow. **Discovered Lights** lists every filter with its frame count, total integration and camera state — what was shot. **Flats and Dark-Flats** and **Calibration with Darks and Bias** say what those lights will be *given*: the sets that will really be opened, the offset each flat is corrected with, and which filters each dark covers. Each of the two calibration tables carries its own switch, so a session with good flats and a library of darks that fit nothing is no longer an all-or-nothing choice. What is switched off stays listed and turns grey — found is never the same as applied — and a filter that gets **no dark** is named in warning colour under its table.

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

The check also measures its own **noise floor**: the reference night is split in half and compared with itself, and since two halves of one night differ by nothing but noise, whatever that returns is the error bar on the number above it. A difference that does not clear the floor is reported as "no shape difference is detectable" rather than as a figure. Each half averages fewer frames than the maps in the real comparison, so the raw half spread is scaled onto the actual frame counts first — unscaled it overstated the true comparison noise by a measured √2 at equal counts, and "not detectable" then covered real differences as large as the noise itself.

The check is silent when there is only one night or when the frames cannot be read. With *Match flats to the same night* on it still runs and is still reported — the number is what shows the split is earning its extra stack — but it stops being a warning, and it never advises switching on something that is already on. Method and thresholds come from the **Flat On Flat Analyzer** by Carlo Mollicone in the official Siril script repository, including the averaging and the binning.

**One master flat per night.** With *Match flats to the same night* on, every night that has both flats and lights of a filter gets its own master flat, and only that night's lights are divided by it. The calibrated nights are merged again (`merge`) before registration, so the filter still ends as **one** master — splitting is a calibration concern, not a stacking one.

**What counts as a night.** Not the date folder — the frame's own `DATE-OBS`, counted noon to noon. A session running from 21:00 to 03:00 is therefore *one* night, and its dusk flats stay paired with the lights taken after midnight; the folder-per-calendar-date layout splits exactly that session in two. Frames whose `DATE-OBS` cannot be read fall back to the folder name individually, so a mixed set degrades gracefully rather than mismatching.

Two conditions have to hold for a night to get its own master: it must have flats **and** lights of that filter. Flats from a night the filter never imaged would build a master nothing opens; a night with lights but no flats has to fall back to a pooled master, and the log and the report name it rather than absorbing it silently. Fewer than two qualifying nights means there is nothing to keep apart, and the ordinary pooled master is used.

The pooled master is built even when every night has its own. It is the fallback on two paths reached at a point where stacking one is no longer safe — a light night whose flats are missing, and a per-part calibration that fails and drops back to a single pass.

**The split trades flat noise for flat accuracy.** A pooled master averages every night's frames; a per-night master averages only that night's. Below ten flats in a night the log says so, because that is where the trade starts to matter — worth it when the optical train really moved, wasteful when it did not. If you shoot flats every night through a panel, ten to twenty per filter per night keeps both properties.

**Darks are also grouped by temperature**, so a −10 °C and a −20 °C set can never be averaged into a single master that is correct for neither. Bias is not split that way — it is temperature-independent.

### The options

| Option | What it does |
|---|---|
| **Use flats and dark-flats** | Divide the lights by the master flat. The dark-flat (or bias) is the flat's own offset and follows this switch. Off = no flat master is stacked at all. |
| **Use darks and bias** | Subtract the master dark, and use the bias where no dark applies. Off = neither master is stacked — but the bias is still built when the flats need it as their offset. |
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

A weighted sum, so the Red channel gains Ha without ever exceeding 1 and without ceasing to be linear. Because Ha does not *replace* a channel, it has no dropdown of its own — the script finds it automatically by filter role among the aligned masters, and the Log names the one it picked:

```
HaRGB will blend HA into Red — Ha is an admixture, not a mapped channel.
HaRGB: blending HA into Red at 50% (PixelMath).
```

If none of your filters carries an Ha role, selecting HaRGB now says so immediately; without that check the run would go all the way through and quietly produce plain RGB.

Two further specifics:

- **Colour calibration is skipped for HaRGB.** With Ha blended into Red, star photometry no longer describes that channel, so any photometric calibration would be measuring the wrong thing. The saved composite is labelled *uncalibrated* — balance it by hand.
- **The luminance is still kept separate**, exactly as in LRGB, and combined after stretching.

**How much Ha actually goes in.** The blend is `(R + k·Ha) / (1+k)` — a weighted sum. At 0 % the channel is plain R; at 100 % it is R and Ha in equal parts. It never exceeds 1, never discards R, and — the point — it is **linear**, which is what every composite this script writes is handed over as.

Up to 1.7.9 it was a screen blend, `1-(1-R)·(1-k·Ha)`. That expands to `R + k·Ha − k·R·Ha`, and the cross term is quadratic in flux. On faint nebulosity it is invisible, which is why it stood so long:

| R | Ha | screen blend | weighted sum `(R+k·Ha)/(1+k)`, k=1 |
|---|---|---|---|
| 0,002 | 0,003 | 0,003497 | 0,002500 |
| 0,02 | 0,03 | 0,034700 | 0,025000 |
| 0,8 | 0,8 | 0,960000 | 0,800000 |

At the faint end the screen blend and a plain sum agree to better than 0,1 %. At the bright end they do not: with R = 0,8 and k·Ha = 0,4 the screen form returns 0,88 where the sum gives 1,2 — a 27 % compression of exactly the stars and nebula cores you stretch afterwards. The same objection that removed `rmgreen` from the finish in 1.7.4 applies here, so the blend became a weighted sum in 1.7.10.

If you want the highlight compression a screen blend gives, repeat the blend **after** the stretch, where it belongs.

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

Three usual causes, in order of impact:

1. **No flats.** Vignetting leaves a brightness gradient across the frame, and Siril will keep saying *"consider correcting the image gradient first"*. This is the single most effective thing you can fix, and no script setting substitutes for it.
2. **_Quick linear LRGB_ left on.** The luminance is baked in before the calibration, so the brightest stars saturate and drop out of the photometric fit — the Log names the option itself when it runs. See §10: leave it off and combine L after the stretch.
3. **A wrong sensor name.** See §10 — check the Log for a name that did not match Siril's mono tables.

**Do not read too much into the gradient sentence.** *"Consider correcting the image gradient first"* is Siril's standard advice attached to any imprecise fit — it is not a measurement of your background. It appeared on a run whose finished composite measured flat to **0.06 × the pixel noise**, after all three background-extraction passes had done their work. If you have flats and the run reports a background extraction, the gradient is not the thing to chase; compare the σ values in the report instead.

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

## 17. What's New in 1.7.19

The narrowband warning claimed to know the size of your target.

**It named a size it never measured.** When a narrowband master reached the background extraction with RBF switched on, the run said: *measured on a nebula filling 95 % of the frame it keeps about 18 % of it … on a target **this size** most of what it removes is your signal. Untick 'use RBF instead of a polynomial' for narrowband.* Nothing had measured that size. The narrowband flag is decided by the **filter** alone, and the comment block above the constants has stated both halves of the truth since 1.7.17: *"On a compact target (a galaxy in a wide field) the opposite holds and RBF is clearly better"*, and *"There is no way to tell the two cases apart from the pixels"*. So an NGC 6946 run — an 11′ galaxy in a 101′ field, its Ha covering perhaps one percent of the area — was told to switch off the model that suited it, and a figure measured at 95 % frame fill arrived dressed as a finding about that image.

  Same fault as the few-stars advice in 1.7.18, same cure. The message now states the measurement **together with the condition it was measured under**, names both cases, says outright that the pixels cannot separate them, and hands over the one piece of geometry the image really does carry:

```
This master is line emission, and RBF is flexible enough to follow emission
that fills the frame: measured on a nebula covering 95% of the field, RBF
keeps 18% of it where the degree-1 polynomial keeps 99.9%.  On a COMPACT
target in a wide field that order reverses and RBF is the better model, and
the pixels cannot tell the two apart -- so the script does not know which this
is.  This master spans about 101' across, and how much of that your emission
covers is the question.  Untick 'use RBF instead of a polynomial' if the
emission fills much of the frame; leave it on if the target is small within
it.
```

  That field of view is read from the astrometric solution the master already holds — `CDELT1`, or the length of the `CD` matrix's first column, so a rotated field is not understated — and failing that from `FOCALLEN` with the pixel pitch. When neither is present the sentence says so rather than guessing. The choice stays yours, which it always was. The polynomial figure also stopped rounding 99.9 % up to 100 %.

## What was new in 1.7.18

Two records described something other than what happened.

**`commands.ssf` promised a replay it cannot deliver.** The header read *Replay headless: `siril-cli -s commands.ssf`*, with GUI-ONLY lines as the only caveat. Three larger obstacles went unsaid. The raw frames are placed into the work folders **by the script**, so `link bias -out=../process` reads a directory Siril never filled; the same holds for the PixelMath inputs `pm_R`/`pm_Ha`, staged under names free of hyphens, and for every master copied out of `_work/.../process` into `masters/`. `_work/` is then deleted by the very run that wrote the file. And the third fails **silently** — these five lines read like a composition:

```
load ".../NGC_6946_RED_Ha.fit"
load ".../NGC_6946_GREEN.fit"
load ".../NGC_6946_BLUE.fit"
new 2937 2879 3 RGB
save ".../NGC_6946_HaRGB"
```

  They are not one. Each `load` feeds `get_image_pixeldata()` into memory, `new` makes an **empty** RGB canvas, and the pixels are written into it through sirilpy. Replayed, those lines save a blank colour image under the right name. The header now says what the file is — a record of what Siril was asked to do — and every step the script performs itself is marked in place with a `#` line carrying the frame count and the folder, in the same spirit as the existing GUI-ONLY marks. The record stays complete and stops claiming what it cannot do.

**The few-stars advice is now worked out from the run's own palette.** When a channel aligns on very few star pairs the scale term is carried badly, which shows up as colour fringing towards the edges — and the message always closed with the same remedy: *Stack only the filters this palette uses* keeps the reference among the channels that end up in the picture. Under **HaRGB** that is a no-op. The palette reads L, R, G and B through the dropdowns and finds Ha by role, so every discovered filter is already one of its own and the option has nothing to leave out; the reference Siril picked is one of the composite's channels too. On an NGC 6946 run the Ha master matched on **318** pairs against 1176–1741 for the broadband channels, and the script answered by naming a switch that could not change the outcome. The advice now asks what *this* palette actually reads and says one of five things: which master the switch would drop — the case it was written for, and still the common one under SHO with a spare L — that the pool is already restricted, that there is no composite to have a palette, that the channel mapping names no discovered filter, or, the HaRGB case, that no master can be left out, naming the reference as one of the composite's own and saying that only more exposure on the weak channel moves the number.

## What was new in 1.7.17

Lessons taken from reading the Starloch Batch Preprocessor, plus three audits of the script's own arithmetic against [Siril's documentation](https://siril.readthedocs.io/en/stable/preprocessing/stacking.html) and against Siril's own log output. One of these costs real signal; the rest cost **confidence** — messages that were quieter, or more certain, than the data justified.

**From the Starloch Batch Preprocessor**

- **Disabled colours moved from the stylesheet to the palette.** 1.7.16 made `setEnabled(False)` visible by adding six `:disabled` rules — one per widget class that happened to be affected. A CSS rule reaches only the classes it names, so the next widget added would be invisible again, and the seven other Svenesis scripts (86 further `setEnabled` calls) would each need the same block copied in. `QPalette.ColorGroup.Disabled` reaches **every** widget, in three lines. And the window now follows Siril's theme via `get_siril_config("gui", "theme")` instead of being fixed dark; light mode drops the dark sheet entirely, because Fusion's standard palette already is a complete light theme. The Overview and Log panes stay dark in both modes — they are a terminal.
- **Every run now writes `commands.ssf`.** A verbatim record of every Siril command the run issued, next to the output, written **before** each call — the command that kills a run must not be the missing one. A run replays headless with `siril-cli -s commands.ssf`. It carries the `requires` line a script needs and marks `load_seq` as `# GUI-ONLY` rather than silently rewriting it.
- **A cleanup that failed was silent, and four of them were dangerous.** Four of the seven `rmtree` calls clear a directory that is about to be **refilled** with freshly staged frames under index-based names — a leftover `lights_00050.fit` from a longer previous run would have been linked into the new sequence and stacked in without a word. Those four now stop the run. The three that merely free disk space warn and carry on. And a stage that reported success but wrote nothing now fails where it happened: the master is checked after the background extraction rewrites it, each aligned channel before it becomes a colour, with a zero-byte file counting as missing.
- **The hot-pixel threshold now follows the stack size.** `-cc=dark 3 3` went to every filter regardless. But stacking only removes a hot pixel because **dithering** puts it on a different sky pixel each frame; at four frames, rejection is percentile clipping over four samples and a defect present in two of them is no minority at all. A channel of 10 frames or fewer now gets `-cc=dark 3 2.5`. The cold side is untouched — every calibration observed reported `0 + N`, so it never fires here.
- **And equal size was being taken for overlay.** Four masters of 2942×2876 can still sit pixels apart, and a healthy star-pair count says the fit *converged*, not that it converged rightly. Five points of the first master now go to the sky through its own solution and back to pixels through each other master's; anything past a whole pixel is said before the channels are combined. Headers only.

**Audit of the arithmetic**

- **The frame-loss warning could not fire.** It read an estimate that is an **upper** bound on the surviving frames — and therefore a *lower* bound on the loss, the wrong direction for a warning about losing too much. On one NGC 6946 run with `-filter-wfwhm=90% -filter-round=87%` it predicted 13–14 % dropped where 21–23 % really went, on all four channels, so the note fired on **none** of them while 88 of 400 frames were removed. It now uses the pessimistic estimate, which lands within a frame of reality. The docstring's justification went with it: it argued the metrics are correlated so the product keeps a margin, and three of those four channels came out *below* the product.
- **A quality filter that never reached Siril said nothing.** The percentage boxes accept 1–100; asking for the best 15 % of 25 frames leaves 3, under the floor of 4, so the filter was silently dropped — and the one message for that situation only covers *"too few frames to filter at all"*. You ticked a box, got the full stack, and were told nothing. Every refused filter is now named, with its reason and the consequence.
- **The short-channel warning hung on the wrong constant.** *"Too few for outlier rejection to mean much"* tested against `MIN_STACK_FRAMES`, which is the floor the quality **filters** may not cross — not a statement about rejection. A channel of exactly **four** frames fell straight through it in silence. That is your IC 1805 SII channel. It now tests the top of the percentile band, shared with the rejection ladder.
- **And the dark tolerance was symmetric where the physics is not.** A 630 s dark on 600 s lights counted the same as a 570 s one. The **longer** dark over-subtracts: the background goes negative and Siril clamps calibrated 32-bit data to [0, 1], so those pixels land on zero and their faint signal is gone. The **shorter** one leaves a pedestal the background extraction removes anyway. A longer dark now has to be within 2 % where a shorter one may be 5 % out, ties go to the shorter, and the message says which way it went.
- **A star count on Siril's ceiling is not a measurement.** `-maxstars` is documented as *"must be between 100 and 2000"*. On a star-rich field every frame hits it — of 400 frames in one NGC 6946 run, **395 reported exactly 2000** — so `-weight=nbstars` hands them all the same weight and does almost nothing, while the log printed *"2000 stars"* as though it had measured a rich field. The cap is now marked in the log and footnoted in the report, and star-count weighting on saturated data is called out, naming **Noise** and **Weighted FWHM**, which still tell those frames apart.
- **The flat noise floor straddled time.** It compared the first half of a night's flats against the second, and since the list is in acquisition order, any drift in the flats' *shape* (dew, a twilight gradient) was measured as "noise". Pure *level* drift was already immune. Simulated at 0.2 % shape drift the floor came out **2.1× too high**, and an inflated error bar hides the very night-to-night difference the measurement exists to find — on your data the two sit within a thousandth of a percent of each other. The halves now **interleave** (1.15× at the same drift), and the eight-flat sample is taken at an even stride rather than from the head of a twenty-flat run.
- **The rejection fallback ignored the quality filters entirely.** When the registered count cannot be read, the number that picks the rejection algorithm fell back to the **staged** count — 74 frames choosing the algorithm for 74 where 57 are integrated, with only 31 frames separating winsorized from GESDT. It now falls back to the pessimistic estimate, erring towards the gentler algorithm.
- **Drizzle warned about something its own settings prevent.** The message blamed a *"grid unevenly filled"* below 40 frames — the failure mode of `pixfrac < 1`. At the shipped `pixfrac=1.0` every output pixel is covered by every frame. What is actually missing on a short run is **sub-pixel sampling**, and the message now says that, along with what you get instead. `pixfrac` sits beside the threshold as a named constant; it stays at 1.0 because lowering it would change everyone's images.
- **And `CALIB_TEMP_TOLERANCE_C` carries its reasoning.** It was a bare `2.0` in a file whose neighbouring constant explains at length why the *exposure* tolerance must be a fraction. Dark current doubles roughly every 6 °C, so 2 °C is up to ~26 % of the dark signal — negligible at a cooled set point, not negligible on an uncooled camera.

- **A calibration part too small to be a sequence took the whole split down.** Siril cannot build a sequence from a single file, so a night holding one light fails `calibrate` — and the run then falls back to one pooled pass **after** having stacked a master flat per night that nothing goes on to read. Seen on IC 1805: OIII arrived as 8 frames on one night and 1 on the next, two per-night flats were built, both were thrown away, and the log carried an error that reads like a defect. The condition is knowable before the parts are built, so the split is now refused there — and the run says so, because discovery had *announced* per-night calibration and that announcement must not be left standing. The tightened hot-pixel note is now also said once per filter rather than once per part.

**And the one that costs signal**

- **RBF background extraction eats line emission.** Measured with `siril-cli` on a synthetic frame — a nebula covering 95 % of the field plus a known linear sky gradient, decomposed by least squares into [nebula, x, y, 1]:

| `subsky` parameters | nebula kept | gradient removed |
|---|---:|---:|
| `1 -samples=20` (degree 1) | **99.9 %** | 85.6 % |
| `2 -samples=20` (degree 2) | 32.1 % | 96.2 % |
| `-rbf -samples=20 -smooth=0.5` | **17.8 %** | 99.1 % |
| `-rbf -samples=20 -smooth=1.0` | 48.1 % | 94.5 % |

  RBF is the **most destructive** option available on a target that fills the frame, and none of its settings are safe there — `smooth=1.0` is the maximum Siril accepts and still loses half. The per-sub pass was already right (degree 1, Siril's own guidance for individual frames); the per-channel master and the composite ran RBF unconditionally, and the option described its benefit without its cost. On a **compact** target the opposite holds and RBF is clearly better, which is why it stays on offer. It cannot be detected from the pixels: the fraction of the frame above *median + MAD* is 26.0 % for plain sky, 26.0 % for the frame-filling nebula and 27.5–30.3 % for a compact galaxy on real masters. A smooth nebula **is** statistically sky — which is precisely why the model removes it. The reliable signal is the **filter**, so a narrowband master and a narrowband palette now say so with the measured figures. It warns rather than overriding: swapping your background model out silently would change images without being asked.
- **And the colour-fit threshold compared a scaled number against an absolute one.** Siril's sigma is the scatter of *Image* R/G, so it carries whatever scale those channels are on — and with **Output normalization** (on by default) each master is divided by its own brightest pixel, which is not a photometric quantity and differs per filter. Confirmed on your real masters: every channel ends at max = 1.000017…1.000021. Scaling the ratio by *k* scales the slope and the sigma alike, so **σ/|slope|** is the number a fixed threshold may be compared against. Two runs of the *same* IC 1805 data, one with narrowband normalisation and one without, reported raw σ 0.323 and 0.216 — 50 % apart — and **0.2748 against 0.2750** once the scale is divided out. The white-balance factors carry the same scaling: the calibrated image is correct, but K0/K1/K2 are **not** a measurement of the filters or the sensor, and the run now says so where they are printed.

## What was new in 1.7.16

Five things real runs turned up — four of them messages or controls that described something other than what was actually happening, and the last complaint pyflakes had about the file.

- **The frame-drop message named the wrong cause.** A run with the quality filters on reported *"Registration dropped 15 of 74 frame(s) … Frames without enough detectable stars (clouds, haze) cannot be aligned"* — while the same log, four seconds earlier, said *"74 images successfully platesolved out of 74 included"*. **Nothing had failed to align.** The 15 were removed by `-filter-wfwhm=90% -filter-round=90%`, switched on deliberately, on frames that were fine. `n_reg` counts what `seqapplyreg` exported, and that is already after the filters — the comment directly under the message said exactly that; the message did not. `_qf_decision` already records whether the filters fired, so the two causes are now told apart, and the filtered case names the flags it was given. Measured on one NGC 6946 run: 41 of 210 frames across three filters, every one of them reported as weather.
- **And the short-channel warning could not fire for the case it was written for.** *"Only N frame(s) … too few for outlier rejection to mean much"* sat **inside** the drop message, so it needed frames to have been lost. A filter that **started** below `MIN_STACK_FRAMES` and lost none was never warned, while one that fell to the same count was — the same diagnosis hanging off the wrong condition as the bullet above. It is now its own check on the number going into the stack, and *"left"* is gone from the wording along with the nesting. Found on an IC 1805 run: SII stacked 4 frames, one above the floor, in silence.
- **And the SPCC panel showed the half it does not use.** On a SHO run the three broadband filter boxes sat there enabled and filled with *Antlia R / G / B*, while the run calibrated by wavelength and ignored them entirely — and said so only in the Log, after the start. Which mode applies is not a choice you make: the palette decides it, so a *narrowband* switch of its own would just be a second place to disagree with that. The panel now follows the palette. For SHO it reads:

```
Broadband filter names — not used by SHO:      (greyed)
Narrowband — SHO calibrates by wavelength, not by filter name:
    Ha    656.3 nm  →  G          [ 4.5 nm ]
    OIII  500.7 nm  →  B          [ 4.5 nm ]
    SII   671.6 nm  →  R          [ 4.5 nm ]
```

  **The bandwidth is entered per emission line, not per colour channel** — and here the script deliberately differs from Siril's own SPCC dialog, which offers one per channel. Bandwidth describes the *filter*: HOO maps one OIII filter to green **and** blue, so a per-channel box would let one piece of glass be given two different passbands. A single shared box, which this script had until now, cannot describe a mixed set either (3 nm Ha with 6.5 nm OIII is a normal rig). A line the palette does not use greys out. Wavelengths stay derived rather than editable — Siril must make them editable because it does not know which line sits in which channel; this script does. An older settings file seeds all three boxes from its single old value, so an upgrade keeps sending what it sent before.

  The mapping is read from the same two tables the command line is built from, so the panel cannot promise a wavelength the run will not send. Greyed rather than hidden, for the reason the calibration tables already are. *Auto* leaves both halves live — which one applies is not knowable before the filters are found.
- **And the greying itself was invisible.** A Qt stylesheet rule that names `color` applies in **every** state unless a `:disabled` rule overrides it — and the shared dark theme has one only for `QPushButton`. All nineteen `setEnabled(False)` calls in this file therefore changed nothing on screen, the calibration tables that §17 of 1.7.15 describes as *turning grey* included. The theme is **extended, not edited**, because it is copied verbatim between the Svenesis scripts. The eight grey hint lines needed a second fix on top: a per-widget stylesheet naming `color` outranks the global rule, so they now spell out both states. The other seven scripts in the suite have the same gap — 86 further `setEnabled` calls — and are untouched.
- **The unused `QSizePolicy` import is gone.** It was the only thing pyflakes still had to say about this file.

## What was new in 1.7.15

The composite is given the astrometric solution the colour calibration asks for — which turned out **not** to be what was wrong with the colour fit.

- **A photometric calibration reads star positions through the WCS.** Siril says so twice in every finish: *"Found linear plate solve data, you may need to solve your image with distortions to ensure correct calibration of stars near image corners."* SPCC and PCC measure every catalogue star **through** the astrometric solution, so a linear one is furthest from the truth exactly where the field is widest — the corners, which is where most of the stars are. The composite now carries a distortion-aware solution, and the warning stops.
- **What it does not do is fix the weak colour fit.** Measured as an A/B on one finished composite — same pixels, same filters, only the solve differing: **σ(R/G) 2.2497 linear → 2.2481** with SIP order 3. Two controlled runs had already ruled out the calibration itself: flats only and darks only came back with σ(R/G) 1.944 and 1.931. So it is neither the calibration nor the astrometry — and the asymmetry says where to look instead. σ(B/G) is **0.17** on the *same* stars, the same apertures and the same WCS, so whatever inflates R/G is specific to that ratio, not to the geometry both share. Still open.
- **And linear is what the composite inherits, by construction.** `seqapplyreg` undistorts every frame, so the registered frames carry a linear WCS, and the cross-filter alignment on top of it is a homography with no distortion model at all. Inheriting that solution is still right — it is what makes the finish's plate-solve an honest no-op (below) — it is simply not the solution the colour calibration asked for.
- **So the composite is re-solved with distortions first:** `platesolve -force -noflip -order=3`. `-force` because Siril answers *"Nothing will be done"* to a plain `platesolve` on a solved image; `-noflip` because a forced solve is allowed to flip an image it reads as upside-down, and the composite has to stay on the masters' grid; `-order=` explicitly, because the order Siril would otherwise use comes from its astrometry preferences, which the run cannot see. It runs only when a photometric method really will — not for HaRGB, not for the weighted palettes, not for narrowband with SPCC switched off — and a refusal is logged and stepped over like every other finish step. The report names it either way, and carries the σ values, so the next run can be compared against these two.

What a real run said and the report did not — and a panel rebuilt so it says the same thing before the run starts.

- **A crop that was asked for and did not happen.** `-framing=min` works on the star-registration path — the cross-filter alignment hands back every master at exactly the same size. On the **astrometric** one (*Register by plate solving*) Siril accepts the same argument, raises nothing, and exports frames of differing sizes anyway; `stack` then says so itself — *"The sequence has different image sizes and registration data. Forcing to maximize framing"* — and the master comes out **larger than any sub**. Measured on one NGC 6946 run: 3008×3008 subs, registered frames from 3007×3008 to 3013×3014, master 3060×3128. That is the union, not the intersection — precisely the ragged, partly-exposed border the option exists to remove. Because nothing raised, nothing was recorded, and the report went on promising *"no ragged, low-signal edges"* about a master built the opposite way. The exported frames are now asked directly (headers only, stopping at the first disagreement), and a channel that did not get its crop says so in the log and in the report.
- **The report tells the two causes apart.** *"Registered without `-framing=min`"* can mean Siril **refused** the argument set and a smaller retry ran, or that it **accepted** it and did not apply it. One shared sentence was wrong for whichever case it was not written for; each now carries its own.
- **An inherited solution is not claimed as new work.** A master registered through the plate-solve path already carries astrometry, and `platesolve` answers *"Image is already plate solved. Nothing will be done."* — successfully. The run logged *"Plate-solved …"* four times for four no-ops. The header is asked first and the log says which of the two happened — the same distinction the composite makes. The command still runs either way: whether an existing solution is good enough is Siril's call.
- **Two smaller things the same run showed.** A fresh run opened with four `swallowed FileNotFoundError` lines for an `output/masters` that cannot exist yet: the scan for reusable masters ran once per filter *before* **Reuse existing masters** was consulted, and its result is read only when that switch is on. It is now gated on the switch, so a run with reuse off stays quiet.
- **A dark used as a dark-flat is no longer reported as unused.** *"2 dark set(s) do not match any filter's lights — not stacked"* counted a set that **was** stacked: a dark at a flat's exposure is consumed as that filter's dark-flat (§5), and flats are built before darks, so its master already existed. One run built its 3 s dark-flat master from 160 frames, used it for all four filters, and then called those frames unused. Sets already spent as a flat offset are out of the count — and stay out of the darks that get stacked, since building them a second time as a dark master is the redundant one.
- **The panel separates what was shot from what it will be given.** One table answered both questions: *Discovered Filters* carried a **Calibration** column that had to be redrawn whenever a calibration switch moved, and still could not say which half of its answer had just changed. It is now three. **Discovered Lights** holds the lights alone — filter, frames, integration, camera state. **Flats and Dark-Flats** lists, per filter, the flats that will really be stacked, the dark-flats beside them, the offset each is corrected with and the nights they come from. **Calibration with Darks and Bias** lists the dark sets that *match* these lights — not the fifteen signatures a grown library holds — with the filters each covers, and the bias with what it is still for when every filter already has a dark.
- **Flats and darks can be switched off separately.** They fail for unrelated reasons: a session can have perfect flats and a library of darks that fit nothing, and the only answer used to be the master switch, which drops both. A master that will not be applied is no longer stacked either — that is minutes and hundreds of reads, and it is the whole point of switching it off. The bias is the exception: it reaches the **lights** only while darks are on, but it is still built when the flats need it as their offset, so turning the darks off cannot quietly downgrade every flat to a synthetic one.
- **What is switched off stays listed, and turns grey.** The summary line names which half of the find is going unused. A table that looked identical either way is how *found* came to be read as *used*. And a filter that gets no dark has no row in the darks table at all — an empty table being exactly what "everything is fine" looks like — so it is named underneath in warning colour, with the exposures the library does hold.
- **The Dark-Flats column shows the job, not the keyword.** Found in use: a session with 160 darks at the flat exposure and no frame labelled `DARKFLAT` read as having none — while the **Offset** column beside it named those very frames as `3s dark`. The column asked `IMAGETYP`; the run asks which set will be *stacked* as the dark-flat, and a dark at the flat exposure **is** one — it carries that exposure's dark current, which a bias does not. Both columns now come from one rule, so they can no longer disagree about a single set. A bias is still named as an offset and **not** counted as a dark-flat: it corrects no dark current, and counting it would promise a correction that is not happening.
- **And the master switch is gone.** *Apply calibration when frames exist* held four gates, every one about darks, flats or bias — exactly what the two kind switches now say together. It could also contradict them: off with both of those on was a reachable state showing two armed switches over a run that calibrated nothing. The run's flag is derived from the two boxes, so it cannot drift from them. Each dependent control now follows its **own** kind, too: the master switch greyed the library, cosmetic correction and per-night flats together, so per-night flats went dead because the *darks* were unusable. A settings file or preset that switched calibration off still switches both boxes off.
- **A switch changes the label, not the record.** The calibration summary sets the blue line under the tables *and* writes it to Siril's log, and it now follows three switches instead of one. Seventeen seconds of someone deciding which boxes to tick produced eleven repetitions of *"Flat offset — …"* and *"Calibration found — …"* in the log of a run that had not started. The label still follows every click; the log is written once, by the analysis it documents.
- **"100 biass".** The count line built every plural by appending an *s* to the label. Bias is its own plural here.

Eleven findings from a logic audit of the whole script.

- **The quality-filter value is reset in both directions.** The reset was keyed on "the old value no longer fits the new range", which only ever fired one way: 90 does not fit 1–10, so *% best* → *k-sigma* was correct, while *k-sigma* → *% best* left a **3** sitting in a box now reading **"3 %"** — a filter that keeps the best three percent of the frames. On 200 frames it really does emit `-filter-wfwhm=3%` and integrate six of them; on a short set it falls under the four-frame floor and silently does nothing while looking armed. The reset now follows the *mode switch*, so switching back and forth can no longer smuggle a number across.
- **The one-click presets say which mode their numbers are in.** All three carry a 90 — a percentage — and none named the mode. Applied while the spin boxes were in k-sigma range, Qt clamped that 90 to 10: *"reject beyond 10 sigma"*, which rejects nothing, from a box showing a plausible number. Presets now set the mode, and it is applied *before* the values, the same ordering the settings restore and the `.json` preset loader already used.
- **The observing night is actually used.** The noon-to-noon night key — taken from each frame's own `DATE-OBS`, so a session running from 21:00 to 03:00 counts as *one* night — was computed for every frame during discovery and then read by nothing. Every real night decision went through the date *folder* instead: which flats belong to which lights, whether a filter is split per night, what the flat-consistency check compares, and both previews in the window. So the fix that key exists for had never once run, and a session crossing midnight was still split in two with half its lights paired against the wrong flats. Discovery now hands the map on and every one of those places reads it, falling back to the folder name per frame — a set without `DATE-OBS` behaves exactly as before. See §5.
- **A channel dropped by the cross-filter alignment says so.** Alignment excludes a master whose file went missing, or whose `FILTER` keyword contradicts its position in the sequence (the guard against saving a mislabelled channel). Neither was recorded, and the report's fallback then called it *"not reached — the run was stopped"* — about a filter whose finished master is sitting in `masters/`. Both exclusions now carry their reason into the report.
- **The pixel-grid check before composition reads the files, not a flag.** It ran only when alignment had *not* run — but "alignment ran" is set even when the two-pass re-projection failed and the single-pass fallback registered the masters **without** `-framing=min`. The one path where the shared grid is not guaranteed was exactly the path that skipped the check. The channel sizes are now read from the files whenever a composite is about to be built; a proper alignment passes in silence, for the cost of one header read per channel.
- **GESDT falls back to winsorized, the band below it.** It fell back to linear fit, which is the band *above* — reserved for stacks over 300 frames, where a trend across the stack has enough points to be modelled. An older Siril refusing the newer `g` token handed a 35-frame stack to a trend model with nothing to fit. The code's own comments had said "the tier below" all along.
- **The flat comparison averages the frames most of the night agrees on.** The reference image size came from the first frame read, so a single mixed-binning frame at the *head* of the list made the outlier the reference and skipped all seven ordinary frames behind it — the night was then compared on a map built from the one frame that did not belong. The warning fired either way, which is how it looked handled.
- **An inherited WCS is no longer thrown away.** When the composite already carried the masters' astrometry, a `platesolve` that refused it set "not solved" and skipped the colour calibration — over a solution sitting in the header the whole time.
- **The narrowband bandwidth falls back to 4.5 nm**, the documented default, instead of a hard-coded 7 that agreed with nothing.
- **The "at least two frames" guard is re-checked** after a failed per-part calibration falls back to a single pass: the guard above it ran on the count of the *parts*, and re-staging can come back with fewer.
- **The flat-warning record names the noise floor** it has carried since 1.7.11.

## What was new in 1.7.12

- **FITS reads survive astropy's memmap refusal.** astropy declines to memory-map an image whose header carries BZERO/BSCALE/BLANK — every N.I.N.A. integer sub — and raises *"Cannot load a memory-mapped image … Set memmap=False."* at data-access time. One run swallowed that ~130 times, and worse than the noise: the flat consistency check read no frame at all and silently skipped, and the blank-frame check silently kept everything. Every reader now retries the file unmapped on that specific refusal; unrelated errors still propagate.
- **No more resource-tracker tracebacks in Siril's log.** sirilpy's shared-memory transfers spawn Python's resource tracker lazily mid-run, where (on macOS, inside Siril's process) it dies with `PermissionError` and is relaunched, spraying tracebacks into the log. 1.7.9 hardened the log readers against those; the tracker is now started at import time, while the environment is clean — removing them at the source.
- **A dead Siril fails the run once, not every fallback in turn.** When Siril crashed mid-run, the broken pipe matched every fallback's error handling: the log blamed plate solving, star alignment and single-pass registration in turn, for both filters — four diagnoses for one dead process. A transport death (broken pipe, connection closed) is now told apart from a command refusal at the single funnel every command uses; the run stops at the first dead reply with one honest message and the recovery spelled out: restart Siril, run again, finished masters are picked up by *Reuse existing masters*.

## What was new in 1.7.11

- **The flat-check noise floor is scaled to the comparison it judges.** The floor comes from splitting the reference night in half — but each half averages *fewer* frames than the maps in the real night-vs-night comparison, so the raw half spread overstated the true comparison noise by a measured **√2** (1.415 over 300 simulated runs) at equal frame counts. "No shape difference detectable" then covered real flat differences as large as the noise itself. The half spread is now mapped onto the actual frame counts (per-map variance ∝ 1/n, ratio variances add); when both halves already hit the per-night frame cap the factor is 1, because then the halves carry the same noise as the full maps.
- **`_rebin_mean` honours its "long side at most target" contract.** Floor division left a 650 px frame at 325 px and anything between the target and twice the target entirely unbinned — small sensors were compared on a finer, noisier grid against thresholds calibrated for the ~250 px scale. The factor is now the ceiling.
- **Flats of a different image size are named, not silently dropped.** A mixed-binning night used to enter the comparison as if it were clean, on a map quietly built from a fraction of its frames; the check now reports how many frames were left out and why.
- **No more false "your values were reset" line on startup.** With k-sigma stored, restoring the settings applies the mode first (it sets the spin ranges), and the mode handler then claimed the constructor defaults it replaced "were percentages" — one moment before the real sigmas were restored. Silenced while settings or a preset are being applied; a live mode switch still reports it.

## What was new in 1.7.10

- **The HaRGB blend is linear now.** It screen-blended Ha into Red, `1-(1-R)·(1-k·Ha)`, whose `R·Ha` cross term is quadratic in flux. Invisible on faint nebulosity — the manuals even measured that — but at R = 0,8 with k·Ha = 0,4 it returns 0,88 against 1,2, a **27 % compression** of exactly the stars and nebula cores you stretch afterwards. Non-linear, in other words: the one property every composite here is handed over with, and the same objection that removed `rmgreen` in 1.7.4. It is now `(R + k·Ha) / (1+k)` — a weighted sum, bounded in [0,1] without a rescale, never discarding R. The slider runs from plain R at 0 % to an even mix at 100 %, and the log prints the two weights it used. §9 works it through.
- **The help tab listing the output files no longer claims `_HaRGB` is calibrated.** It said all composites were "calibrated and linear" while a second tab correctly said HaRGB is excluded from photometric calibration. Wrong on both counts for that one file; the exception is now named where the files are listed.
- **The `MIN_STACK_FRAMES` floor applies to the combination of quality filters, not to each one alone.** Siril keeps the frames that pass *every* filter, so the survivors are an intersection — four 60 % cuts on 20 frames each cleared a per-filter check while projecting to **2** survivors against a floor of 4. The running estimate multiplies the shares; that assumes an independence the metrics do not have, so it errs towards keeping frames, which is the right direction for this floor. Ordinary settings are untouched: three 90 % cuts on 30 frames still all apply. k-sigma cannot be projected at all, so that mode instead caps how many cuts combine (two).
- **A mixed-exposure channel's integration time is marked as an estimate.** Scaling by the frame ratio assumes every frame is the same length, and nothing records *which* frames were dropped — on 20×300 s + 10×120 s that can be eight minutes out. The figure carries a **~** and the report says why.
- **Checked and deliberately not changed:** the quality medians drop zeros with a truthiness test. That looks like a statistical bug and is not — sirilpy documents roundness as "0 when uninit, ]0, 1] when set", an FWHM of zero does not exist, and a frame with no stars cannot be registered so it never reaches the sample. The obvious repair would make the number worse. The reasoning now sits in the code.

## What was new in 1.7.9

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
