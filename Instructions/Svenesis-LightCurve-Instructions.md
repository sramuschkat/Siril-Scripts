# Svenesis LightCurve — User Instructions

**Version 1.0.5** | Siril Python Script for Exoplanet Transit Photometry

> *A folder of sub-exposures in, a light curve out — and an honest answer to the only question that matters: is there a transit in it?*

---

## Table of Contents

1. [What Is Svenesis LightCurve?](#1-what-is-svenesis-lightcurve)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
3a. [Calibration](#3a-calibration)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Choosing the Target](#6-choosing-the-target)
7. [The Comparison Ensemble](#7-the-comparison-ensemble)
8. [Detrending the Airmass Ramp](#8-detrending-the-airmass-ramp)
9. [The Transit Fit](#9-the-transit-fit)
10. [Deciding Whether It Is Real](#10-deciding-whether-it-is-real)
11. [Reading the Output](#11-reading-the-output)
12. [Capturing Good Data](#12-capturing-good-data)
13. [Troubleshooting](#13-troubleshooting)
14. [FAQ](#14-faq)

---

## 1. What Is Svenesis LightCurve?

Point **Svenesis LightCurve** at the folder holding one night's sub-exposures of an exoplanet host star. It measures how that star's brightness changed relative to other stars in the same field, removes the systematic trends it can account for, fits a transit — and tells you whether the dip is real or whether you are looking at a cloud.

### Who does what

The division of labour is deliberate and worth understanding, because it explains most of the design.

**Siril does what it is demonstrably good at:** staging, calibration, two-pass registration, star detection, the plate solve and per-frame quality.

**This script measures the flux itself**, the way EXOTIC and HOPS do — every star re-centroided per frame, subpixel apertures, sigma-clipped sky, the aperture chosen by point-to-point noise, comparison stars kept by their *measured* scatter (§4a explains each piece, with the measurement that motivated it). Siril's `light_curve` remains intact as the loud fallback: if the engine measures under 30 % of the frames it says so and hands over. And the script does the parts nobody's pixels decide: which star is the target, how to remove the airmass ramp without eating the transit depth, how to fit the event — and, above all, whether to claim anything at all.

**Validated against EXOTIC on its own sample data** (HAT-P-32 b): Rp/R★ = 0.1525 ± 0.0064 against EXOTIC's published 0.1541 ± 0.0033 — 0.2 σ apart, at the same residual scatter (0.58 % vs 0.55 %).

### The pipeline

| Step | What happens | Why it is done this way |
|---|---|---|
| **Stage** | Subs are symlinked into `_lightcurve/` | Costs nothing; the original folder is never written to |
| **Link** | Siril builds a sequence | |
| **Calibrate** | Calibration frames are found, stacked into masters and applied via Siril's `calibrate` | Optional and *delegated* — there is no bias/dark/flat arithmetic in this script, for the same reason there is no photometry in it. Per-pixel arithmetic, so it does not break the no-resampling promise; it does write a second copy of every frame |
| **Register** | `register -2pass` — data only, **no resampling** | Interpolation correlates neighbouring pixel noise and moves flux inside the aperture. The aperture follows the star through the registration data while the pixels stay exactly as the sensor recorded them |
| **Detect** | Siril finds the stars (and plate-solves the reference when the target needs sky coordinates); the script picks target + comps | |
| **Photometry** | This script's own engine — follow-star, subpixel apertures, aperture chosen by noise. Siril's `light_curve` as the fallback, announced | Measured on the same drifting run: 140 points against `light_curve`'s 67 |
| **Analyse** | Detrend → fit → decide | |

---

## 2. Background for Beginners

**What is a transit?** A planet passing in front of its star blocks a fraction of the light. For a hot Jupiter that is roughly 1–2 % — ten to twenty **millimagnitudes** — lasting two to four hours. It is a small, slow dip, and everything about measuring it is a fight against things that also produce small, slow dips.

**Why "differential"?** Measuring the star's raw brightness is hopeless: clouds, transparency changes and the atmosphere thinning as the star rises all swamp a 1 % signal. But those affect *every star in the frame together*. Divide the target by a set of comparison stars and they cancel. What is left is the star's own variation — the transit.

**What is airmass?** How much atmosphere you are looking through. Straight up is 1.0; near the horizon it is 3 or more, and the star dims accordingly. Differential photometry cancels most of this, but not all: the target and the comparisons have different colours, so they dim at slightly different rates. What survives is a smooth ramp — and removing it without eating the transit is a large part of what this script does (§8).

**What is a magnitude?** A logarithmic brightness scale where *bigger means fainter*. A millimagnitude (mmag) is one thousandth. All the plots here have an inverted y-axis so that up means brighter, which is why a transit reads as a dip.

---

## 3. Prerequisites & Installation

- **Siril 1.4** or newer with the Python module
- Automatically installed on first run: `numpy`, `PyQt6`, `matplotlib`, `astropy`

Place `Svenesis-LightCurve.py` in a folder named **Utility** inside one of Siril's Script Storage Directories (*Preferences → Scripts*), then run it from **Processing → Scripts**.

**Calibrate.** Flats especially: a star drifting across a dust shadow is a slow trend that looks exactly like a shallow transit. Either point **2 · Calibration** at your masters (see [3a](#3a-calibration)) or run the frames through your usual calibration beforehand — but do not skip it.

---

## 3a. Calibration

**Nothing has to be prepared, and you need not navigate.** Point at your subs — or at any folder above them — and, once, at the folder where your reusable darks live. Everything else is found.

### Where it looks

The scan is **recursive**. Every FITS under the folder you chose is read once and sorted by its header into lights and calibration frames, so you can point at the project root:

```
WASP-75b/                       ← point here…
├── LIGHT/2026-08-14/LUMINOS/   ← …and the subs are found three levels down
└── FLAT/2026-08-14/LUMINOS/    ← so are these
_CALIB/DARK/60.00s_G125/        ← your Library folder, set once
```

Or point straight at `LIGHT/2026-08-14/LUMINOS/` — then the flats are still found, because the script also walks **up** and takes any child of an ancestor that is a `FLAT` / `DARK` / `BIAS` / `DARKFLAT` folder. Going up, only calibration folders are scanned, never a whole ancestor: four levels above a subs folder can reach a directory holding every project on the disk.

### Three things the recursion made necessary

| Guard | Why |
|---|---|
| **Own folders pruned** | `_lightcurve/` and `lightcurve/` are never descended into — a second run would otherwise re-ingest the first run's staged symlinks and converted frames as if they were subs |
| **Duplicate exposures dropped** | A repeated `DATE-OBS` is a copy, not an exposure. Found the hard way: a leftover working folder turned 178 subs into 534, and every duplicate would have entered the curve as an independent point, shrinking every error bar by √3 for nothing. Reported with a count, never silent |
| **One filter, one exposure** | A filter or exposure change mid-run is *two* series, not a longer one. The largest set is kept and what was set aside is named |

**Flats are session frames**, so they are looked for inside your selection and beside the lights, filtered to the lights' filter. **Darks and bias are reusable**, so they come from the Library folder, remembered between runs. Raw frames or ready-made masters, either way: a group of exactly one file is adopted as a master rather than stacked.

### What must agree

Frames share a master only when their **exposure, gain, temperature, binning, image size and camera** agree. Masters are cached in `lightcurve/calib/` under names carrying all of it — if two different masters could share a name, the cache would hand back the wrong one on the second run, silently.

What gets refused is said out loud. A master that was found and then rejected leaves a run that looks *exactly* like one where no master existed:

| Refused | Why |
|---|---|
| **Wrong exposure** (dark) | A 3 s dark on 60 s lights removes 5 % of the dark current, leaves the rest in, and adds its own read noise to every frame. Reported with both numbers and with what it would have done |
| **Wrong temperature** | Darks are grouped by temperature — a −10 °C and a −20 °C frame averaged together is correct for neither. Bias is *not* split: it is read noise only, and splitting it would just make each master noisier |
| **Wrong camera or size** | Two bodies of the same sensor format would otherwise calibrate each other |
| **Bias together with a dark** | Never both on the lights: the dark already contains the offset, subtracting both removes it twice. The bias still corrects the flats — Lc = (L − D) / (F − O) |

A flat does **not** have to match the lights' exposure. A flat is a ratio; its own exposure says nothing about the lights.

### What it does not do

The pixel work is Siril's `calibrate`. There is no bias/dark/flat arithmetic in this script, for the same reason there is no photometry in it. And it does **not** resample — bias, dark and flat are per-pixel arithmetic, so the promise the registration keeps is untouched. It does write a second copy of every frame, so the working folder doubles.

Tick **One-shot-colour sensor (CFA)** for a Bayer camera. Without it the frame is flat-fielded across its own mosaic, which writes the CFA pattern into the correction.

## 4. Getting Started

1. **Choose folder** — the folder with your calibrated subs. Ten frames is the bare minimum; a real transit run is hundreds.
2. **Target star** — leave it on *Brightest* for a first look.
3. **Site coordinates** — latitude and longitude, if you want the airmass ramp removed. Without them the detrend is skipped and the report says so.
4. **Measure light curve.**

The first run takes a few minutes: registering a few hundred subs is the slow part.

---

## 4a. You do not have to type coordinates

**Choosing the folder already fills it in.** The first 30 light headers are read the moment you pick a folder, and what they say lands in the fields:

> *Read from the first 30 header(s): OBJECT = 'WASP-75b'; OBJCTRA/OBJCTDEC = 342.38750, −10.67556 (25 light frames agree to 0.0").*

**The fields follow the frames.** They are restored from your last session, so after switching targets they still show the *previous* target — and a WASP-75 b run was once analysed under HAT-P-32's ephemeris exactly that way. So: a name that keys to a *different* target than `OBJECT` is replaced (any spelling of the *same* target — `WASP-75b`, `wasp75`, with or without the planet letter — stays exactly as you typed it), coordinates further than ~2′ from the headers are replaced with the header position, and when the target name switches but the new headers carry no position, the stale coordinates are cleared so the archive can supply them. Every replacement is logged; nothing is swapped silently. To aim at a star that is *not* the headers' object, type it **after** choosing the folder — nothing re-probes. Calibration frames are sorted out first, so a folder of flats cannot prefill the target from a parked mount. Headers that say nothing get a line too, because silence there reads as *nothing to do* when it means *type the name*.

Everything that decides *which star* now lives in one place — **group 3 · Target star** — and its first mode, **From the frames**, is where it starts:

| Mode | What it uses |
|---|---|
| **From the frames** | `OBJCTRA`/`OBJCTDEC` for the position when present; otherwise the **archive position of the planet the frames name** (`OBJECT`), with the reference frame plate-solved around it. Falls back to brightest only when nothing names or places the target — labelled as the guess it is, and a guess the drift would carry off the sensor guesses again among the stars that stay on it. |
| Brightest star | the brightest detection |
| Pixel position | your x/y, snapped to the nearest star |
| RA / Dec | your coordinates, snapped to the nearest star |

The **name** box and the **archive lookup** sit there too, not in the submission group: they decide the target's *position*, and the one control that spares you typing coordinates belongs where you choose the target. The name still labels the AAVSO file — one field, both jobs.

Your frames already know where the target is. N.I.N.A. writes **`OBJCTRA` / `OBJCTDEC`** — the position of the *object*, not of the telescope — and the run reads it straight out of the light frames:

> *Target from OBJCTRA/OBJCTDEC in your lights: RA 342.38750°, Dec −10.67556° (178 light frames agree to 0.0"). No lookup needed for the position.*

Measured against the NASA Exoplanet Archive: **5.7" × 0.2"**, under three pixels at 2 arcsec/px and comfortably inside Siril's own ±19 px search box. No network, no typing.

### Two cards that look right and are not

| Card | On this run | What it is |
|---|---|---|
| **`OBJCTRA` / `OBJCTDEC`** | `22 49 33` / `−10 40 32` | **the target** — used |
| `RA` / `DEC` | 342.24 / −10.30 | the **telescope pointing** — a quarter of a degree off, because the target is not the field centre |
| `OBJCTRA` in a **flat** | `00 00 00`, with `RA/DEC` = 359.10 / **+89.85** | the mount **parked near the pole** — a sentinel, not a position |

Both traps are closed: only **LIGHT** frames are read, and the `0 0 0` sentinel is discarded. If the frames in one folder disagree about where the target is, the run says so and uses neither — that is more than one target in a folder, not one position.

### The frames outrank a stale form — and the run says so

The RA/Dec fields are used when they *agree* with what the frames (or, failing header coordinates, the archive) say about the frames' own target — and the run always names its source:

> *Using the RA/Dec in the form; your lights agree to 0.0".*

A coordinate further than about two arcminutes from that is the previous target, not a choice — the fields persist across sessions, and **a coordinate left over from the previous target looks exactly like a deliberate one**. It is replaced, in red, with both values printed. Aiming at a star that is *not* the headers' object still works: type it after choosing the folder, and at run time the disagreement is reported rather than overridden.

### The name lookup adds what the header cannot carry

Spelling is not your problem: hyphens and spaces are stripped from **both** sides, so `HATP-32`, `HAT-P-32`, `hatp32b` and `HAT-P-32 b` all reach the same entry — and the **host name** is searched as well, because a name with no planet letter is what a header usually carries. A system with several known planets is a refusal that lists them, since their ephemerides differ.

Give the planet a **name** — from `OBJECT` in the lights, or the *Target* box in group 6 — and the run fetches the published **ephemeris** from the NASA Exoplanet Archive. `WASP-75b` becomes `WASP-75 b` on the way out; one missing space is the whole difference between a hit and a silent miss.

It also **cross-checks** the position. Agreement is reported; a disagreement is *reported, not resolved*:

> *The headers and the archive disagree by 340" about where WASP-75 b is. The headers win — they came with these frames — but check the OBJECT name, because that gap means the two are describing different things.*

**TESS candidates are a different table.** A target named `TOI-3540.01` is a *candidate* designation — the archive's confirmed-planet table cannot know it, and losing the whole ephemeris (expected curve, O−C, transit window) to that was a spelling nobody got wrong. When the planet lookup misses and the name matches the TOI pattern, the archive's own `toi` list is asked instead; its ppm depth and hour duration are converted to the units the rest of the run speaks. The **TFOPWG disposition is said, not swallowed**: PC/CP/KP/APC are informational, FP/FA get a red warning that a "transit" matching this ephemeris is most likely *not* a planet — and that warning repeats on cache hits, because a cached false positive is still a false positive. A bare `TOI-3540` with several candidates lists them and asks which one, the same contract as a multi-planet system.

Without a connection you lose the O−C and nothing else. The position came from your files.

### When the frames disagree with the convention

Two header traps handled by measurement rather than assumption.

**The longitude sign.** FITS never settled east- versus west-positive, and getting it wrong mirrors the site across the globe — it does not fail, it just detrends the airmass for the wrong place. An altitude in the header, with the pointing and the time, says where the telescope actually was:

> *SIGN FLIPPED to −110.8800: the header value would put the target 73° from the TELALT=62.59° it records, the flipped one reproduces it to 0.01°. This header is WEST-positive.*

A correct header is **confirmed**, not flipped. With no altitude to check against, nothing is changed and the assumption is stated.

**The field drifting off the sensor.** Siril moves each measurement box by the registration data, so a comparison star that sits comfortably in the reference frame can leave the chip later — and when one does, the *whole* `light_curve` command fails with `generic error` after a warning that names a frame and never says which star. The drift envelope is measured from the registration and stars that would walk off are dropped with that reason. If the **target** is the one that leaves, the run stops: no aperture follows a star off the sensor.

**How the flux is measured.** The division of labour follows what each side is demonstrably good at. Siril does the staging, calibration, two-pass registration, star detection, plate solve and per-frame quality — and this script does the flux measurement itself, the way EXOTIC and HOPS do: each frame is read once, every star is **re-centroided** from its registration-predicted position (the "follow star" that Siril's `light_curve` lacks — a centroid that walks more than 6 px has locked onto a neighbour and is discarded), and the flux is summed in a subpixel-weighted circular aperture against a sigma-clipped sky annulus. Several apertures are measured in the same pass; the one with the lowest **point-to-point** noise wins, a measure a transit barely moves while a plain standard deviation would triple — an aperture chosen on standard deviation prefers whatever washes the transit out. Comparison stars are each normalised to their own median (so one that misses a frame cannot step the ensemble — the step of a raw sum is the exact shape of an ingress) and are kept or dropped by their **total** scatter against their peers, because a slowly variable comp is precisely the one that writes a fake transit into the target. Errors come from the CCD equation with every term measured, none assumed.

Measured on the same 142-frame drifting run: this engine keeps 140 points at 7.2 mmag point-to-point where Siril's `light_curve` kept 67. If the engine measures fewer than 30% of the frames it says so and Siril's `light_curve` takes over — the whole old path remains intact as the fallback, including everything below.

**The 160-pixel wall.** Siril refuses `light_curve` outright when any frame's registration shift exceeds 160 px from the reference. It prints a line it calls a "Warning" about "heavy drifted images" and then returns a generic error — the warning *is* the abort, and it names a frame, never a star. The threshold was found by bisection against Siril 1.4.4: 159.6 px runs, 160.7 px does not.

This matters because Siril chooses its registration reference on **image quality** — FWHM, roundness, star count — which is the right criterion for stacking and the wrong one here. On EXOTIC's HAT-P-32 demo set it picked image 35 of 142, which put the entire drift on one side: 218.9 px, refused every time. The reference is now moved. Which frame it moves to matters as much as that it moves: choosing purely on drift takes the frame at the exact centre, and on this data set that frame — image 72 — is the worst of the night, weighted FWHM 8.50 against 2.42 for its neighbour, 110 detected stars against 262. The command then *runs*, which is the dangerous kind of wrong: the sky annulus came out more than twice too large, the target was matched 200 arcsec from its catalogue position, and 6 frames of 142 survived photometry.

So the rule is: among the frames Siril will accept, take the best one. On this data that is image 70 — 149.1 px of drift, 261 stars, weighted FWHM 2.41 — and the run yields 67 measured points calibrated against 5 comparison stars. The quality measure is Siril's own weighted FWHM, read from the registration data; with no drift limit to satisfy, the same rule picks image 35, exactly what Siril picked. The run reports both numbers when it moves the reference.

If even the best reference stays over the limit, the drift itself is too large: trim the run to the stretch where the field holds still, or apply the registration first (`seqapplyreg`) and point this script at the resampled sequence. That costs one interpolation, which is why it is not the default.

**A meridian flip is not drift.** Siril's registration stores each frame as a 3×3 homography, and its translation column is *not* the distance the field moved when the frame is also rotated. A 180° flip about the centre leaves every star on the same piece of sky, but its translation column is the frame's own width and height — measured on a real 3008×3008 run, 4253 px by the column against 13.7 px by the centre. The drift is therefore measured by sending the image centre through the whole matrix: that returns exactly the translation for a pure shift, and the truth for a flip.

**`-autoring`.** Siril's flag for deriving the sky-annulus radii from the frame's FWHM makes `light_curve` abort with "The given coordinates are not in the image" — on coordinates that are demonstrably inside it. The same command without the flag, on the same sequence and the same stars, produces the curve. The radii are therefore set with `setphot` beforehand, using Siril's own factors of 4.2 and 6.3 times the FWHM. Those reproduce its arithmetic exactly: for FWHM 1.797542 Siril logs 7.5 and 11.3, and the factors give 7.55 and 11.32. Nothing about the measurement changes; only the way the numbers reach Siril.

**Siril's process ending.** Twelve failing `light_curve` calls in a row once took Siril down with them, leaving only `[Errno 32] Broken pipe`. The probes now stop after a handful of identical failures and name the pattern, and a broken pipe is reported as a crash on Siril's side — restart it — rather than as a refused command.

**The plate scale.** Siril reads it from `FOCALLEN` and `XPIXSZ`; with neither it falls back to whatever it last *saved* — the previous target's telescope. On a 5.21″/px frame that meant looking for a 0.46° field where the truth is 0.94°, and the solve failed with *Generic error*, which reads like a broken solve rather than a wrong scale. `IM_SCALE`, `SECPIX` and friends are now read directly, derived from the optics when absent, and passed on the command line.

**Time stamps.** N.I.N.A. writes seven fractional digits; MicroObservatory writes *local* time with a `−0700` offset. Both were silent NaN before — the second is a seven-hour error in a quantity measured in minutes, and the first cost the seeing, sky and star-count bases on every run.

### O−C: what a single night is worth contributing

```
O-C            +4.20 min +/- 5.0 min  (consistent with the prediction)
               epoch 2114 of WASP-75 b, P = 2.484193 d
```

This is the number ExoClock and ETD collect. Until now the fit measured T0 with a calibrated error bar and had nothing to compare it against.

Two guards: **refused** unless the times are BJD_TDB — the archive's epoch is BJD_TDB, and subtracting a JD_UTC from it would put an 8-minute offset into a quantity measured in minutes — and the **epoch is always printed beside the drift**, because over thousands of epochs a stale period eventually mislabels which transit this was.

Whatever the position came from, the next step still reports how far it lands from a real *detected* star:

> *Target at (1503.4, 1505.6) — nearest detection, 0.9" from the position you gave.*

Nothing here can mis-point quietly.

---

## 5. The User Interface

**Left panel**, four numbered groups in the order you use them:

| Group | Contents |
|---|---|
| **1 · Subs** | Folder picker, symlink/copy toggle |
| **3 · Target star** | Selection mode (starts on *From the frames*), planet name, archive lookup, pixel or RA/Dec fields |
| **3 · Photometry** | Comparison count, SNR floor, channel, auto ring radii |
| **4 · Analysis** | Airmass detrend, site, plot binning |

**Right panel**, four tabs:

| Tab | Shows |
|---|---|
| **Light curve** | The curve, the fit, and a residual panel underneath |
| **Result** | Everything the run measured, in words |
| **Stars** | Target and each comparison star with its SNR |
| **Log** | Every command sent to Siril and every rejection |

---

## 6. Choosing the Target

Three modes, and all three end at a **detected** star:

- **Brightest star in the field** — right more often than you would think. A transit host is usually the reason the field was framed the way it was.
- **Pixel position** — read off the first frame.
- **RA / Dec** — needs plate-solved subs.

Pixel and RA/Dec both **snap to the nearest detected star** rather than using your number directly, and the log says how far it moved. A position two pixels off the centroid puts the aperture off-centre for the whole run, and the flux it loses changes with the seeing — which is exactly the shape of a fake trend.

RA is read as **hours** when it contains colons or spaces (`18:18:45`) and as **degrees** when it is a bare decimal (`274.6875`). The script does not guess from the magnitude: RA 12.5 is plausible sky either way.

---

## 7. The Comparison Ensemble

Four filters decide who gets in, each for a different failure:

| Filter | Why |
|---|---|
| **Saturated** | A clipped core does not scale with transparency, so a saturated comparison star turns every passing cloud into a fake transit |
| **SNR below the floor** | A comparison star contributes its own Poisson noise to the ensemble. Below roughly 20 it adds more scatter than reference |
| **Within 10 × FWHM of the target** | The apertures start sharing sky annulus and star wings. The contamination is a function of seeing, so it drifts through the night and looks like a slow trend |
| **Not isolated** | The same argument aimed at any neighbour rather than at the target. A star inside the comparison star's own sky annulus puts part of its light in the aperture and the rest in the sky estimate, and its share moves with the seeing. The radius is Siril's own geometry, not taste: `-autoring` sets the outer ring to 6.3 × FWHM, so two annuli stop touching at twice that |

Every rejection is listed in the Log and in the report, and the tally accounts for **every** detected star — including the ones that passed all four filters and were simply not needed. Without that last line, "6 chosen, 668 rejected" out of 864 detections reads as a field that barely yielded a comparison star, when in fact it yielded 195 and the best 6 were taken.

The target cannot be dropped, so the same geometry is *reported* for it instead: a neighbour inside its annulus is called out before the photometry runs.

> **An open question, recorded so you are not surprised by it.** Siril's log line `Photometry for star at X, Y in image 0` does not always agree with the `-refat=` that produced it — on one run three of six comparison stars came back 16, 33 and 63 px away. The obvious reading, that `-refat` is a search hint and Siril locked onto a neighbour, does not survive Siril's own log: the `No star found in the area … around X,Y` lines put the search box at `requested − 19` in both axes, and two of those three reported positions fall *outside* their own 38 px box. A fit cannot land outside the box it ran in, so the line is probably reporting a different quantity rather than a mismeasurement. No filter is built on it until that is settled.

**How many?** More comparison stars average down the ensemble's own noise, but each one added is fainter than the last, so the gain flattens quickly. Five is a good default. Below two there is no ensemble at all — one comparison star puts its own variability straight into your curve.

---

## 8. Detrending the Airmass Ramp

### Why the obvious fix is wrong

Fit a line through every point and subtract it, and you have just absorbed part of your transit depth. The standard evening-target case is a star that sets during egress: airmass and dimming rise *together*, so the line splits the difference.

The usual repair — a sigma clip seeded from that same all-points line — is a no-op in exactly the case that motivates it. The seed already tilts into the dip, so no in-transit residual ever exceeds the threshold.

### What this does instead

**Pass one** is a *one-sided least-trimmed* fit. The line is iterated on the brightest 60 % of the residuals. The dip lives on the faint side, so it falls into the discarded 40 % as soon as the line straightens. A final pass re-admits every point within 2 MAD-σ of that core, so the baseline ends up using all the genuine out-of-transit data.

**Pass two** re-fits the baseline *directly on the points outside the fitted transit window*. Exact, where pass one is only good.

### Measured, not asserted

Synthetic runs carrying a known 30 mmag/airmass ramp and a 15 mmag transit, 15 noise realisations per point — mean error in the recovered slope:

| Duty cycle | Plain fit | Pass 1 alone | With pass 2 |
|---|---|---|---|
| 25 % | 6.2 % | 0.9 % | 0.8 % |
| 50 % | 10.1 % | 1.0 % | 1.0 % |
| 60 % | 10.7 % | 2.3 % | 0.9 % |
| 75 % | 10.8 % | **10.6 %** | 2.7 % |

Pass one buys an order of magnitude over a plain fit and holds to about 50 %, where it runs out of untouched baseline to trim to. At 75 % coverage it is *no better than the fit it replaces* — and pass two is what carries the result from there.

Above 50 % the report **names which pass produced the baseline**, because at that coverage the two are no longer interchangeable. If pass two did not run (no transit found, so no window to anchor on) the depth at high coverage is a **lower bound**, not a measurement.

The fix is not a cleverer algorithm. It is more baseline: start earlier, finish later.

---

### Beyond airmass: what Siril already measured

Airmass is not the only thing that drifts through a night. Three more do, and Siril measures all three for every frame during registration — this script was reading them for the meridian-flip check and throwing them away:

| Basis | Why it moves the light curve |
|---|---|
| **FWHM** | Worse seeing spreads the star, and a fixed aperture then holds a smaller share of its light. Strongest on an undersampled star |
| **Sky level** | Moon, twilight and light pollution change what the annulus subtracts, and the error scales with the aperture area |
| **Star count** | Not a systematic itself — it is what a passing cloud *looks like* from inside the data |

They are fitted together with one least-squares solve, each basis centred and scaled so airmass (1–3), FWHM (2–5 px) and sky (hundreds of ADU) can share a matrix.

**Anchored on the out-of-transit rows, and it refuses to run without them.** All three drift monotonically through a night, so at least one usually correlates with the dip; a plain fit over every point would absorb the depth into it. That is the same trap the airmass detrend already guards against, and it is the reason this runs as a *third* pass, after the transit window is known.

Measured on a synthetic run with a seeing and a sky trend injected: out-of-transit scatter **20.8 → 3.9 mmag** against a 4.0 mmag noise floor, with the depth at the flat bottom untouched.

`light_curve.dat` carries no frame number, so rows are paired with frames by mid-exposure time. Matching on order would be wrong — the frames Siril drops are scattered through the run.

---

## 9. The Transit Fit

### A limb-darkened model, and why the trapezoid had to go

The trapezoid was defended here on the grounds that at amateur precision the two are indistinguishable. **That was wrong, and measurably so.** Fitted to a real limb-darkened transit:

| Rp/R★ | true depth | trapezoid | **bias** | χ²/ν |
|---|---|---|---|---|
| 0.08 | 8.27 mmag | 7.76 | **−6.2 %** | 1.05 |
| 0.10 | 12.95 mmag | 12.23 | **−5.6 %** | 1.02 |
| 0.15 | 29.34 mmag | 27.89 | **−4.9 %** | 1.11 |

Systematically 5–6 % too shallow — and **χ²/ν stays at 1.0**, so nothing in the output would ever have said so. A real star is darker at its limb, so a transit has a *rounded* bottom; a trapezoid splits the difference and loses depth doing it.

The shapes searched are now real geometries: four planet-to-star radius ratios crossed with two impact parameters — exactly the eight variants the eight ingress fractions used to provide. The bias comes to **+0.6 / −0.0 / −0.2 / +0.1 %**.

**Nothing else changed.** Each shape is a *template* on normalised phase, built once and interpolated at each node, so the model stays **linear in depth** — the closed-form solve, the determinism and the no-optimiser guarantee all survive. A physically free Rp/R★ would couple depth and shape and cost all three. (The occultation is integrated *radially* — the arc a planet covers at radius r has a closed form — so there are no elliptic integrals, no new dependency, and it is verified against an independent 2-D integration.)

> **The template's Rp/R★ is a shape index, not a planet radius.** With the duration free, a smaller template stretched fits nearly as well, so that value sits systematically below the truth. The **depth** is the measurement, and both reports say so.

### Two depth conventions, both reported

The fit measures the **limb-darkened central depth** — the deepest point of the curve. EXOTIC, HOPS and AstroImageJ all quote **(Rp/R★)²**, and with limb darkening the centre of the star is brighter than its mean, so the central depth is ~20 % *deeper* than (Rp/R★)² on a solar-type star. Two correct tools comparing those two numbers look like a disagreement — which is exactly how this was found, against EXOTIC's own reference result for its sample data.

So the measured depth is also inverted **through the same limb-darkened model the fit used** into a *measured* Rp/R★ (distinct from the template index above) and its square. All three numbers appear in the log, both report forms and the AAVSO header, each labelled:

```
depth      30.23 ± 2.55 mmag  (limb-darkened CENTRE)
Rp/Rs      0.1525 ± 0.0064
(Rp/Rs)^2  2.33 ± 0.19 %      <- compare THIS with EXOTIC/HOPS/AIJ and the archive
```

On EXOTIC's HAT-P-32 sample set that reads 0.1525 ± 0.0064 against EXOTIC's 0.1541 ± 0.0033 — 0.2 σ apart.

### Everything is fitted at once

The old sequence was: detrend, fit, re-detrend on the fitted window, re-fit. Three passes, each treating the previous baseline as *exactly known*. It is not — the baseline has an uncertainty, and a sequential fit throws it away instead of carrying it into the depth and the mid-time.

Airmass, seeing, sky level and star count now sit in the **same design matrix** as the transit, solved together at every grid node. Two consequences:

- **The transit cannot be absorbed into a correlated basis.** That is what the out-of-transit anchoring existed to prevent, and it is no longer needed: the transit is its own column. Verified against a basis deliberately *shaped like the transit* — the depth survives at 11.2 mmag of 12.0, where a sequential detrend would have eaten it.
- **The baseline's uncertainty ends up where it belongs**, in the depth and the mid-time.

It is also **faster**. Only the transit column changes from node to node, so the Gram matrix of everything else is computed once: 11.1 µs per node against the old 13.8, and a whole fit in 0.56 s against 1.0.

### A grid, not an optimiser

The search walks a grid over **T0**, **duration** and **shape**. At every node the depth, the baseline and every systematic coefficient are solved *analytically* — the model is linear in all of them, so one small linear system gives the exact best set.

Strongly correlated parameters are precisely where a local optimiser walks into a noise minimum and gives a different answer depending on where it started. The grid gives the same answer every run, cannot fail to converge, and its resolution is a number you can read rather than a tolerance nobody checks.

Depth is constrained **positive** — the star gets fainter — so the fit cannot "detect" a brightening and call it a transit.

---

### T0 comes with an error bar

The mid-transit time is the number ExoClock and ETD exist for. It is measured from the **curvature** of the χ² surface along T0, with depth and baseline re-solved and the duration re-minimised at every step, then scaled by the red-noise β.

Two designs were tried and rejected first, and both failures are instructive:

- **Walking outward to Δχ² = 1** plateaued at 86 s for every depth below 12 mmag — 0.7 of one sampling interval. A trapezoid on sampled data has a *bumpy* χ² surface: shifting T0 by less than one cadence changes which points fall inside the window. The walk was measuring the local dell, not the envelope the fit explores.
- **A wider parabola window** (0.3 durations) over-stated the bar by 1.5× to 1.75× at every depth.

Five sampling intervals tracks the truth. Reported against the run-to-run scatter actually recovered, 50 runs per depth at 4 mmag per point:

| Depth | σ(T0) reported | scatter recovered |
|---|---|---|
| 20 mmag | 53 s | 47 s |
| 12 mmag | 91 s | 90 s |
| 8 mmag | 134 s | 136 s |
| 6 mmag | 173 s | 191 s |

That measurement exposed something else. The coarse search grid quantised T0 to (0.7 × span) / 120 — **105 s on a five-hour run**. Over 60 runs of a 20 mmag transit every single fit returned the *same* T0, and at every lower depth the MAD of the recovered times was exactly 1.4826 × one grid step: the data were being rounded to the search. The winning node now gets a local pass at 1/20th the T0 step.

### χ²/ν: does the model actually fit?

Around 1 means the model describes the data. Well above 1 means it does not — systematics, or a shape the template family cannot make. Well below 1 means the noise estimate is too large, usually because the out-of-transit window still holds part of the event.

The noise floor is deliberately **model-independent**: a fit's own residual scatter cannot judge that fit, because dividing residuals by their own RMS gives 1 whether the model is right or nonsense. So it comes from the MAD of the out-of-transit residuals, or failing that from the MAD of first differences ÷ √2. Measured 1.0 on pure noise and 3.1 with an unmodelled 20 mmag lump.

---

## 10. Deciding Whether It Is Real

The significance is the in/out contrast over its own standard error:

```
(mean_in − mean_out) / σ × √(N_in·N_out / (N_in+N_out))
```

Three deliberate choices hide in there.

**The scale factor is not √N_total.** Doubling your pre-ingress baseline does not make a shallow dip twice as certain — the uncertainty is dominated by how many points fall *inside* the event.

**The contrast is measured, not taken from the fitted depth.** The trapezoid has no free baseline term, so on transit-free data the fitter can always absorb a small offset as a wide shallow "dip" with a nonzero depth. The data's own in/out contrast on such a run is about zero, so noise-only runs get rejected where a depth-based test would pass them.

**It is applied separately to each side, and the weaker of the two counts.** This is the one that matters most.

### Why both sides

A real transit **returns to the baseline it left**. A trend does not.

Pool the two sides into one out-of-transit mean and you lose exactly that distinction. On a monotonic ramp — uncorrected extinction, a drifting cloud, focus creep — the fitter puts its window over the faint half, the pooled contrast is genuinely large, and a *trend gets reported as a transit*. On a synthetic ramp with no transit in it at all, the pooled test reaches **+25σ**; the two-sided test returns **−10σ** and refuses it.

The price is a slightly smaller number on a real detection: each side carries about half the baseline, and the minimum of two noisy quantities sits below either. On the synthetic runs above, 127σ became 110σ. That is the right direction for a test whose only job is to refuse to overclaim.

A transit **clipped by the start or the end of your run returns zero significance**, not a smaller one. Without baseline on both sides the question cannot be answered by any method.

### The detection floor is calibrated, not chosen

The significance is the best of about **40 000** grid nodes — 121 mid-times × 41 durations × 8 ingress fractions. Nothing in the formula knows that, so **it is not a Gaussian σ**: a search that large finds a contrast on pure noise that a single a-priori test never would.

So the floor was measured. 1200 transit-free white-noise runs (150 points, 5 h, 4 mmag per point) through this same search, with detection rates on injected transits beside them:

| Floor | False alarm | 4 mmag | 5 mmag | 6 mmag | 8 mmag | 12 mmag |
|---|---|---|---|---|---|---|
| 3.0 σ | **7.67 %** | 88 % | 95 % | 100 % | 100 % | 100 % |
| 3.5 σ | 1.92 % | 70 % | 91 % | 97 % | 100 % | 100 % |
| 4.0 σ | 0.50 % | 45 % | 77 % | 93 % | 100 % | 100 % |
| **4.5 σ** | **0.25 %** | 29 % | 57 % | **89 %** | **100 %** | **100 %** |
| 5.0 σ | 0.00 % | 15 % | 40 % | 78 % | 100 % | 100 % |

A 3σ floor lets **one run in ten** of pure noise through — where "3σ" is universally read as one in 750. **4.5σ** halves the false alarms against 4.0 for four points of detection at 6 mmag and none at 8, and costs the 4–5 mmag case: a dip at about the per-point scatter, which was never safe to claim from a single night.

> **The table has been re-measured three times.** The T0 refinement pass (~2700 more nodes per fit) roughly doubled every rate — more search finds a deeper minimum in pure noise. A robust post-fit scatter raised them again, because a MAD is a smaller divisor than an RMS an outlier has inflated. The limb-darkened model, fitted simultaneously with the systematics, brought them back down: a rounded shape matches noise less well than one with a free corner did. The rate at 4.5σ came out **0.25 % before and after that last change — coincidence, not stability**. A calibration table is only valid for the search, the statistic *and* the model it was measured on.
>
> Measured *without* the spike clip, which is the conservative direction: on pure Gaussian noise the clip removes about 0.2 points per run, trimming exactly the tail this table is about.

---

### The aperture is chosen, not assumed

Aperture size is the most influential number in aperture photometry, and until now it was whatever `-autoring` derived from the frame's FWHM. Too small loses a *seeing-dependent* share of the star — a systematic that moves with the night. Too large collects sky and neighbours. The optimum sits between and depends on the data.

Six radii from **0.75 to 2.5 × FWHM** are each photometered through Siril's own `setphot` + `light_curve`, and the one with the least robust scatter wins. The number of measured frames is the tie-breaker: an aperture that scores well by measuring fewer frames has not won anything.

Costs six extra passes. Switch it off under **4 · Photometry** if you would rather have the speed.

### Comparison stars are measured, not just filtered

Each candidate is photometered **against the others** — the same differential measurement the target gets — and judged on the robust scatter of its own curve. A star that wobbles against its peers writes that wobble, inverted, into the target's curve, and nothing else in this script would ever notice.

The threshold is a **ratio to the ensemble median**, not an absolute millimagnitude: a good night and a poor one differ by a factor, and a fixed limit would reject everything on one and nothing on the other. A drop is never taken if it would leave fewer than two comparison stars — measuring with a suspect comparison beats not measuring, as long as the suspicion is on the record, and it is.

No catalogue and no network. A variability flag from AAVSO's VSX would be better where it exists, but the star has to *be* in the catalogue, and the ones that ruin an amateur light curve usually are not.

### One satellite must not cost the detection

There was no outlier rejection at all, and it mattered more than it looks. Measured on a real 12 mmag transit at 4 mmag per point:

| Outlier | Depth | T0 shift | **Significance** | χ²/ν |
|---|---|---|---|---|
| none | 12.0 mmag | 47 s | **12.1σ** | 1.03 |
| 50 mmag | 11.9 mmag | 92 s | 7.5σ | 2.00 |
| 100 mmag | 12.5 mmag | 55 s | **3.2σ** | 4.99 |

The *parameters* barely moved — a trapezoid over 150 points shrugs off one point. What broke was the **divisor**: the post-fit scatter behind the significance was a plain RMS, and one spike inflates it. A measured transit was being reported as *not claimed*.

Two changes fix it, and both were needed:

1. **The post-fit scatter is now the MAD**, like every other scatter in this file. That alone recovers 3.2σ → 6.9σ, and on clean data the two agree to 1 %.
2. **The spike is removed.** The reference is a running median over nine points — far shorter than any transit — so a smooth multi-point dip passes through untouched (verified at 12, 30 and 60 mmag: not one point lost) while a one-frame spike stands out against its own neighbours. That takes it the rest of the way, back to 11.9σ.

It never removes more than **5 %** of a run. Past that the outliers *are* the data, and the run says so instead:

> 49 point(s) exceed 4 sigma, more than 5% of the run — that is a noisy night, not an outlier population, and nothing was removed

### The AAVSO file

`AAVSO_exoplanet.txt` lands beside the CSV, in Exoplanet Watch's own format: `#TYPE=EXOPLANET`, observer code, filter, `#DATE_TYPE=BJD_TDB`, the **resolved** target name (never a stale form entry), then `DATE,DIFF,ERR,DETREND_1`. Mid-transit time and its error, the central depth and its error, **`#RPRS`, `#RPRS_ERR` and `#DEPTH_RPRS2_PCT`** (the convention EXOTIC and AIJ quote — see §9), duration and the red-noise β travel in the header.

**Refused unless the times are BJD_TDB.** The header declares that system; writing JD_UTC under it would hand a submission an eight-minute error nobody could see.

Nothing is sent anywhere. Submitting is your decision — the file just stops the run one step short of being useless.

---

## 11. Reading the Output

Everything lands in a `lightcurve/` folder next to your subs:

| File | Contents |
|---|---|
| `lightcurve.csv` | Every point: JD, raw, centred, detrended, error, airmass |
| `lightcurve.png` | The plot, if you save it |
| `report.txt` | The full run in plain text — comps, rejections, method, result |

**RMS** is robust (MAD-based), so a single satellite streak does not inflate it. Compare it to the depth you are hunting: a 15 mmag transit at 5 mmag scatter is comfortable; at 15 mmag it needs the whole night to stack up.

**The residual panel** shows what the model missed. Flat noise is what you want; structure means something is left in there. Its corner reports the residual STD and the **lag-1 autocorrelation** with a verdict (white-noise-like / mild structure / structure left) — the red-noise tell that separates clean noise from a leftover systematic.

![Svenesis LightCurve — a non-detection told honestly](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Svenesis_LightCurve_1_0_4.jpg)

*Everything below in one picture (TOI-3540.01, a non-detection): the wall-clock axis on top, the cyan expected transit with its contact stamps, the flip marker at 00:57 — and the unclaimed 0.0σ fit that latched onto the flip step, with no detection markers to dress it up.*

**The chart carries the whole result.** The legend quotes T0 and Rp/R★ with their errors and names the detrending bases, so a screenshot is a complete measurement, not a teaser. Spike-rejected points appear as red crosses ("N outlier(s), not fitted") instead of silently vanishing — you judge for yourself that it was a satellite, not an egress. Per-point **error bars** have an on/off switch (off by default; a long run turns into a picket fence). Beside the fitted model, the **expected transit from the archive ephemeris** is drawn in cyan — *whether or not the fit claimed anything*. On a detection the shift between the two curves **is** the O−C, quoted in the legend in minutes with its error. On a non-detection the prediction is the more valuable half: an in-window prediction says "(no transit claimed by the fit)" — both facts in one picture — and a prediction outside the window names the nearest mid-transit in hours from your run, so you know whether the night missed the transit or the transit missed the night. Its epoch comes from the window's centre, never from the fitted T0, so a fit that wandered off cannot drag the prediction with it.

**The chart speaks your planning tool's language.** A night is planned in wall-clock time ("start 21:50 … flip 00:55") but measured in Julian Dates, so a second time axis across the top shows HH:MM — in *local* time when your frames carry N.I.N.A.'s `DATE-LOC` keyword (the `DATE-OBS`/`DATE-LOC` pair yields the site's UTC offset, daylight saving included, nothing to configure), in UTC otherwise, and the axis says which. The predicted transit's start/mid/end contacts are stamped along the bottom in the same clock time, and a meridian flip is drawn as a dashed marker in both panels at the moment the field turned — so you can check by eye whether a step or an "ingress" coincides with it. Clock labels take the BJD_TDB correction off again first; a clock reading in barycentric time would be minutes wrong. The vertical lines follow one grammar: **orange dashed is the flip, cyan dotted are the predicted contacts, and a coloured dashed mid-transit line exists only for a claimed detection** — an unclaimed fit keeps its honestly-labelled curve but wears no detection markers, because a 0.0σ fit that latches onto the flip step would otherwise stand a second dashed line right beside the real one.

**Binning is presentation only.** The fit always sees every point — binning first would throw away the very scatter the significance test needs in order to be honest about itself.

---

## 12. Capturing Good Data

| | |
|---|---|
| **Baseline** | Start at least one transit duration *before* ingress and run the same after egress. Everything on this page depends on out-of-transit data |
| **Do not saturate** | Not the target, not the comparisons. Keep the peak below about half of full well |
| **Defocus slightly** | Counter-intuitive but standard: spreading the star over more pixels averages over flat-field errors and buys saturation headroom. FWHM 4–6 px is a good target |
| **Do not dither** | The opposite of the stacking advice. Dithering moves the star onto different pixels with different responses — noise you do not need when the star never moves anyway |
| **Same exposure throughout** | Changing it mid-run changes the saturation margin and the scintillation statistics at once |
| **Calibrate** | Flats above all |

---

## 13. Troubleshooting

**"Only N FITS file(s) in that folder"** — a light curve needs a time series. Point it at the subs, not at a stack.

**"Siril found no stars in the reference frame"** — check focus, and that the frames really are of the sky.

**"Only N usable comparison star(s) after filtering"** — the Log lists every rejection with its reason. Lower the SNR floor, or use a wider field.

**"light_curve produced no light_curve.dat"** — Siril rejects the whole run when a comparison star cannot be measured in enough frames. Try fewer comps or a higher SNR floor.

**No transit claimed but you expected one** — check the significance in the Result tab. If it is close to the 4.5σ floor you may simply not have the precision; if it is negative, the fit found a brightening, which usually means a trend the detrend did not remove.

---

## 14. FAQ

**Why not just use Siril's own [light-curve tool](https://siril.readthedocs.io/en/stable/photometry/lightcurves.html)?** Siril's native workflow produces a light curve — this script produces a measurement. Natively you load the calibrated sequence, solve the reference, pick the target and comparison stars by hand or catalogue query, and `light_curve` writes a three-column file (JD, V−C, error) for plotting or export; the analysis ends there. This script differs in three layers, each measured rather than assumed. *The workflow:* one folder in, the whole chain runs — Siril still does the calibration, registration, detection and plate solve. *The measurement:* `light_curve` moves its box by the registration but never re-centroids (no follow-star), refuses outright above 160 px of total drift, and fails the *whole* command when one star leaves the chip; this script re-centroids every star per frame, re-picks the reference, drops only the star that drifts off, chooses the aperture by measured noise, and screens the comparison stars against each other — 140 of 142 points where `light_curve` kept 67 on the same run. *The analysis:* BJD_TDB, a limb-darkened fit simultaneous with the systematics, calibrated error bars, a two-sided significance test with a measured false-alarm rate, O−C, both depth conventions — none of which exists in the native tool. And `light_curve` remains built in as the announced fallback.

**Does it modify my subs?** No. Everything is written under `_lightcurve/` and `lightcurve/`; the source frames are only read.

**Can I use it for variable stars?** The photometry and detrending apply unchanged. The *fit* is transit-shaped, so a pulsating variable will not be described well by it — but the CSV is there for you to analyse elsewhere.

**Why is my significance lower than another tool's?** Probably the two-sided baseline test (§10). It is deliberately conservative.

**Why is a transit at the edge of my run refused?** Because without baseline on both sides a dip cannot be distinguished from a trend. That is a property of the data, not of the script.

**Should I submit this to ExoClock?** The depth, T0 and duration are in the right form. Aim for 5σ or better, and read their submission guidance — the floor here is for claiming a detection, not for publishing one.
