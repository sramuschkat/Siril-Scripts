# Svenesis ImageMono Train — User Instructions

**Version 1.4.0** | Siril Python Script for Monochrome Filter-Wheel Stacking and Colour Composition

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
17. [What's New in 1.4.0](#17-whats-new-in-140)

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
| `EXPTIME`, `GAIN`, `CCD-TEMP`, `XBINNING`, `NAXIS1/2` | Matching calibration masters to lights |

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
4. Press **Analyze Folder**. The Overview tab now lists every filter with its frame count, total integration, exposure, gain and sensor temperature — plus whatever calibration frames were found.
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

Only calibration is taken from outside the target folder. A *light* frame sitting in the library or a neighbouring folder is counted and reported, never stacked into your target.

### How masters are matched

Matching runs on **FITS headers, not filenames**:

| Property | Tolerance |
|---|---|
| Exposure time | exact |
| Gain | exact |
| Binning | exact |
| Image dimensions | exact |
| Sensor temperature | ±2 °C |

A dark that does not match is **reported and skipped**, not applied. A 60-second dark on 300-second lights would do real damage, and silently using it would be worse than using none.

**Darks are also grouped by temperature**, so a −10 °C and a −20 °C set can never be averaged into a single master that is correct for neither. Bias is not split that way — it is temperature-independent.

### The options

| Option | What it does |
|---|---|
| **Apply calibration when frames exist** | Master switch. Off = stack raw lights, as before. |
| **Cosmetic correction (hot pixels)** | `-cc=dark` — removes hot and cold pixels using the dark's own statistics. Requires a dark. |
| **Match flats to the same night** | Uses only flats from the same date folder as the lights. Turn this on if the rig was rebuilt between sessions; leave it off to pool flats for a lower-noise master. |

### The flat offset chain

Flats need their own offset removed before they can normalise anything. The script degrades in three steps and never aborts:

1. a real **dark-flat** or **bias** master, if one matches,
2. Siril's **synthetic bias** `=64*$OFFSET`,
3. no offset correction at all — the flat is stacked directly.

Masters are cached in `calib/` under readable, header-derived names such as `M101_RED_-10C_3s_G100_flat` and reused by later runs.

---

## 8. Stacking Options

### Rejection — chosen per filter, from the frame count

Outlier rejection removes satellites, cosmic rays and aircraft. Which algorithm works depends entirely on how many frames it has to work with, so the script picks per channel:

| Frames | Algorithm | Why |
|---|---|---|
| ≤ 4 | **Percentile clipping** 0.2 / 0.1 | Sigma methods need a population; with three frames a standard deviation means nothing |
| 5 – 20 | **Winsorized sigma** 3 / 3 | Robust, the workhorse for a normal night |
| 21 – 49 | **Linear fit** 3 / 3 | Handles a gradient that changes across the stack |
| ≥ 50 | **GESDT** 0.3 / 0.05 | Siril documents it as outperforming linear fit on large stacks |

GESDT's two numbers are **not** sigmas — they are the maximum rejected fraction and a significance level. A Siril build that does not know the token falls back to linear fit, and the report names the algorithm that *really* ran, so a fallback cannot hide behind the preferred one.

The tier is chosen for the frames that are **actually integrated**, not the ones that were found. A sub without enough detectable stars cannot be registered, and Siril excludes it; the script counts what Siril really exported. On one real night, 3 of 6 OIII frames were lost to cloud — the surviving 3 got percentile clipping, where the naive count would have applied Winsorized sigma to three frames and rejected nothing at all.

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

### When registration cannot do everything

`register -2pass` and `seqapplyreg` fail for unrelated reasons, so they are handled separately — only the first says anything about two-pass support.

If two-pass registration fails, the run falls back to single-pass `register`, which knows neither `-framing=` nor any `-filter-` option. The crop and the quality filters therefore cannot be honoured on that channel. What was given up is **recorded per channel and named in the report**, never silently dropped.

---

## 9. Palettes & Channel Mapping

### The palettes

| Palette | Mapping | Notes |
|---|---|---|
| **LRGB** | R=Red, G=Green, B=Blue, L=Luminance | L is combined *after* stretching by default (see §10) |
| **RGB** | R=Red, G=Green, B=Blue | No luminance |
| **SHO** | R=SII, G=Ha, B=OIII | The Hubble palette |
| **HOO** | R=Ha, G=OIII, B=OIII | Two filters are enough — OIII feeds both Green and Blue |
| **HaRGB** | R=Red + Ha blend, G=Green, B=Blue | Adjustable **Ha → Red** strength; colour calibration is skipped (see §10) |

**Auto** proposes a palette from the filters found, and only ever one whose three channels can actually be filled. Broadband wins when it is complete, because it gives natural colour — switch to SHO / HOO / HaRGB manually for the mapped look. Every channel can be overridden with the dropdowns.

If you pick a palette the filters cannot fill — SHO without an SII filter is the classic case — the script says so **when you choose it**, not after a full run. It also refuses to skip filters in that situation, so you still end up with usable masters.

### Cross-filter alignment

Each filter is stacked against its *own* reference frame, so the masters can sit on slightly different pixel grids. To fix that, all masters are pooled into one small sequence, re-registered, and re-projected with `-framing=min`, producing channels that are **pixel-identical** in size and overlay exactly.

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

---

## 11. Output Files

```
output/
├─ TARGET_RGB.fit        the finished colour image (linear, calibrated)
├─ TARGET_RGB_preview.fit stretched preview, if enabled
├─ masters/
│   ├─ TARGET_FILTER.fit            aligned — use these to combine channels
│   └─ TARGET_FILTER_fullframe.fit  full, uncropped stack
├─ output.md             what the script did, step by step
├─ todo.md               step-by-step final-processing guide
├─ calib/                master dark / flat / bias — reused next run
├─ qa/                   rejection maps (if enabled)
└─ _work/                intermediates — safe to delete
```

**`masters/` holds two versions per channel.** The `_fullframe` file is the stack in its own geometry; the plain one has been re-projected onto the common grid and is the one to use for channel combination.

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

## 17. What's New in 1.4.0

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
