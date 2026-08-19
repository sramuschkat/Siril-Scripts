# Svenesis LightCurve — User Instructions

**Version 1.0.0** | Siril Python Script for Exoplanet Transit Photometry

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
15. [What's New in 1.0.0](#15-whats-new-in-100)

---

## 1. What Is Svenesis LightCurve?

Point **Svenesis LightCurve** at the folder holding one night's sub-exposures of an exoplanet host star. It measures how that star's brightness changed relative to other stars in the same field, removes the systematic trends it can account for, fits a transit — and tells you whether the dip is real or whether you are looking at a cloud.

### Who does what

The division of labour is deliberate and worth understanding, because it explains most of the design.

**Siril does the pixel work.** `light_curve` is Siril's own aperture photometry — the same code behind its Photometry tool. It already handles the sky annulus, the FWHM-scaled ring radii, saturation rejection and the per-frame star matching. Re-implementing that inside a script would give you a *second* photometry engine that has to be kept in step with the first, and would be worse at it.

**This script does the parts Siril has no opinion about:** which star is the target, which stars are worth calibrating against, how to remove the airmass ramp without eating the transit depth, how to fit the event — and, above all, whether to claim anything at all.

### The pipeline

| Step | What happens | Why it is done this way |
|---|---|---|
| **Stage** | Subs are symlinked into `_lightcurve/` | Costs nothing; the original folder is never written to |
| **Link** | Siril builds a sequence | |
| **Calibrate** | Calibration frames are found, stacked into masters and applied via Siril's `calibrate` | Optional and *delegated* — there is no bias/dark/flat arithmetic in this script, for the same reason there is no photometry in it. Per-pixel arithmetic, so it does not break the no-resampling promise; it does write a second copy of every frame |
| **Register** | `register -2pass` — data only, **no resampling** | Interpolation correlates neighbouring pixel noise and moves flux inside the aperture. The aperture follows the star through the registration data while the pixels stay exactly as the sensor recorded them |
| **Detect** | Siril finds the stars; the script picks target + comps | |
| **Photometry** | Siril's `light_curve` | |
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

## 5. The User Interface

**Left panel**, four numbered groups in the order you use them:

| Group | Contents |
|---|---|
| **1 · Subs** | Folder picker, symlink/copy toggle |
| **2 · Target star** | Selection mode, pixel or RA/Dec fields |
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

## 9. The Transit Fit

### A trapezoid, not a limb-darkened model

At amateur precision the two are indistinguishable — a 10 mmag dip measured at 3 mmag per point does not constrain a limb-darkening coefficient. What the trapezoid recovers is **depth, mid-time and duration**, which is exactly what ExoClock and ETD consume. Its ingress fraction is free, so it also handles the grazing case: at 0.5 the trapezoid degenerates into a triangle.

### A grid, not an optimiser

The search walks a grid over **T0**, **duration** and **ingress fraction**. At every node the depth and the baseline are solved *analytically*: for a fixed shape the model is `baseline + depth × shape(t)`, which is linear in both, so a 2×2 solve gives the exact best pair.

Four strongly correlated parameters is precisely where a local optimiser walks into a noise minimum and gives a different answer depending on where it started. The grid gives the same answer every run, cannot fail to converge, and its resolution is a number you can read rather than a tolerance nobody checks.

Depth is constrained **positive** — the star gets fainter — so the fit cannot "detect" a brightening and call it a transit.

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
| 3.0 σ | **4.42 %** | 91 % | 94 % | 100 % | 100 % | 100 % |
| 3.5 σ | 0.83 % | 79 % | 89 % | 98 % | 100 % | 100 % |
| **4.0 σ** | **0.17 %** | 53 % | 81 % | **98 %** | **100 %** | **100 %** |
| 4.5 σ | 0.08 % | 33 % | 70 % | 96 % | 100 % | 100 % |
| 5.0 σ | 0.00 % | 19 % | 53 % | 86 % | 99 % | 100 % |

The old 3σ floor let **one run in 23** of pure noise through — 33× the 0.13 % that "3σ" is universally read to mean. **4.0σ** is where the measured rate reaches that 0.13 %, and it costs nothing above 6 mmag. What it costs is the 4–5 mmag case: a dip at about the per-point scatter, which was never safe to claim from a single night.

The measured rate is printed next to every result, so the number can be weighed rather than trusted. ExoClock and AAVSO submissions want more still — but that is a decision for the submission, not for the fit.

Below the floor nothing is claimed. The report still prints what the fitter wanted, clearly marked as not a measurement, because "no detection" and "the tool crashed" should not look the same.

---

## 11. Reading the Output

Everything lands in a `lightcurve/` folder next to your subs:

| File | Contents |
|---|---|
| `lightcurve.csv` | Every point: JD, raw, centred, detrended, error, airmass |
| `lightcurve.png` | The plot, if you save it |
| `report.txt` | The full run in plain text — comps, rejections, method, result |

**RMS** is robust (MAD-based), so a single satellite streak does not inflate it. Compare it to the depth you are hunting: a 15 mmag transit at 5 mmag scatter is comfortable; at 15 mmag it needs the whole night to stack up.

**The residual panel** shows what the model missed. Flat noise is what you want; structure means something is left in there.

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

**No transit claimed but you expected one** — check the significance in the Result tab. If it is close to the 4.0σ floor you may simply not have the precision; if it is negative, the fit found a brightening, which usually means a trend the detrend did not remove.

---

## 14. FAQ

**Does it modify my subs?** No. Everything is written under `_lightcurve/` and `lightcurve/`; the source frames are only read.

**Can I use it for variable stars?** The photometry and detrending apply unchanged. The *fit* is transit-shaped, so a pulsating variable will not be described well by it — but the CSV is there for you to analyse elsewhere.

**Why is my significance lower than another tool's?** Probably the two-sided baseline test (§10). It is deliberately conservative.

**Why is a transit at the edge of my run refused?** Because without baseline on both sides a dip cannot be distinguished from a trend. That is a property of the data, not of the script.

**Should I submit this to ExoClock?** The depth, T0 and duration are in the right form. Aim for 5σ or better, and read their submission guidance — the floor here is for claiming a detection, not for publishing one.

---

## 15. What's New in 1.0.0

- Initial release: differential photometry of a sub-exposure folder via Siril's own `light_curve`, with the comparison ensemble picked from Siril's star detection and filtered on SNR, saturation, separation and isolation
- Airmass detrending with a one-sided least-trimmed baseline and an out-of-transit-anchored second pass; the breakdown figure is **measured**, not asserted (§8)
- Trapezoid fit on a deterministic grid with depth and baseline solved analytically
- **The significance test is two-sided.** The first version pooled the out-of-transit points, and the test suite caught what that costs: on a monotonic ramp with no transit in it the pooled contrast reaches +25σ, where the two-sided test returns −10σ. Uncorrected extinction, a drifting cloud and focus creep all produce that ramp, so this was not a corner case
- CSV, PNG and plain-text report export
