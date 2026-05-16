# Svenesis Satellite Trail Cleaner — User Instructions

**Version 0.8.9** | Siril Python Script for Per-Frame Satellite Trail Removal

> *Bridges the gap between Siril's sigma-clip stack rejection (needs 8+ subs) and the all-or-nothing decision of throwing a trail-affected frame away. Cleans each affected sub individually, before stacking.*

---

## Table of Contents

1. [What Is the Satellite Trail Cleaner?](#1-what-is-the-satellite-trail-cleaner)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Detection: How findsat_mrt Works](#6-detection-how-findsat_mrt-works)
7. [Inpaint Methods — Which Should I Pick?](#7-inpaint-methods--which-should-i-pick)
8. [The Recommendation Banner](#8-the-recommendation-banner)
9. [File Format Support](#9-file-format-support)
10. [The Apply Workflow](#10-the-apply-workflow)
11. [The Audit Report](#11-the-audit-report)
12. [Tips & Best Practices](#12-tips--best-practices)
13. [Troubleshooting](#13-troubleshooting)
14. [FAQ](#14-faq)
15. [Scientific Background — Why We Inpaint](#15-scientific-background--why-we-inpaint)

---

## 1. What Is the Satellite Trail Cleaner?

The **Svenesis Satellite Trail Cleaner** is a Siril Python script that detects linear features (satellite trails, aircraft contrails, tumbling debris) in your individual astrophotography sub-exposures and **paints them out** using the local sky background — **before** stacking.

Think of it as a **dedicated trail-removal preprocessor** that runs once per session, on every affected sub, so your stacking step sees clean frames instead of having to filter trails statistically.

The result: a final stack free of residual trail streaks, even when you only have 4–6 subs and Siril's normal sigma-clip rejection isn't statistically powerful enough to remove a trail on its own.

---

## 2. Background for Beginners

### What Is a Satellite Trail?

When you take a long-exposure photograph of the night sky, satellites or aircraft passing through your field of view leave **bright linear streaks** across the frame. With Starlink and similar mega-constellations, this is no longer rare — most multi-hour imaging sessions catch at least one trail.

| Source | Visual signature |
|--------|------------------|
| **LEO satellite** | Long thin straight line, uniform brightness |
| **Geostationary satellite** | Short or absent (matches sidereal tracking) |
| **Tumbling rocket body** | "String of pearls" — periodic bright flashes along the line |
| **Aircraft** | Often slightly curved, sometimes with red/green strobe flashes |
| **Iridium flare** | Short bright spike, often only on 1–2 frames |

### Why Not Just Use Siril's Stack Rejection?

Siril (and PixInsight, and every other modern stacker) supports **sigma-clipped stacking**: when combining N exposures, each pixel's value is compared across the stack, and outliers (typically > 3σ from the median) are rejected. A satellite trail visible in only one of, say, 12 frames is statistically an outlier — it gets rejected, and the final stack shows clean sky there.

**This works when you have ~8 or more well-distributed exposures.** For shorter sequences:

- With **5 subs**, a trail in one frame represents 20% of the sample. Sigma-clipping needs ≥5 surviving samples on either side of the trail value to reject confidently. Marginal.
- With **3 subs**, sigma-clipping is statistically not possible — the trail will leave a faint streak in the final stack.
- With **LRGB filters**, each per-filter sub-stack might only have 4–6 frames, well into the danger zone.

This tool fills that gap by **removing the trail from each affected frame individually** before stacking. The remaining sigma clip then runs on already-clean frames.

### Why Not Just Throw the Affected Frame Away?

Two reasons:

1. **You lose 100% of the signal** in that frame — for short sessions, every sub matters.
2. The trail might cross **only a small fraction** of the frame. Throwing away the whole frame to remove a 50,000-pixel trail in a 24-megapixel image is wasteful. Spatial inpainting only modifies the trail region (~0.2% of the pixels), preserving the other 99.8%.

### What Is "Inpainting"?

In image processing, **inpainting** means filling in a region of an image using the surrounding pixels as context, so the filled region blends naturally. We define a **mask** (the trail pixels) and replace those pixels with values estimated from the unmasked neighbourhood.

For astronomical sky regions, this is well-suited: the sky has uniform statistical properties (mean, σ) over scales of tens to hundreds of pixels, so a 15-pixel-wide trail crossing a uniform sky region can be reconstructed nearly perfectly.

---

## 3. Prerequisites & Installation

### Requirements

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| **Siril** | 1.4.0+ | Must have Python script support |
| **sirilpy** | Bundled | Comes with Siril 1.4+ |
| **numpy** | Any recent | Auto-installed |
| **PyQt6** | 6.x | Auto-installed |
| **astropy** | 5.x+ | Auto-installed |
| **opencv-python-headless** | 4.x | Auto-installed |
| **photutils** | 1.x+ | Auto-installed |
| **scikit-image** | Recent | Auto-installed |
| **acstools** | 3.7+ | Auto-installed (provides `findsat_mrt`) |
| **xisf** | 0.9+ | Auto-installed (XISF read/write) |
| **tifffile** | Recent | Auto-installed (TIFF read/write) |

### Installation

1. Download `Svenesis-SatelliteTrailCleaner.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

On first run, the script automatically installs every missing dependency via `sirilpy.ensure_installed()`. This may take a minute (acstools brings in several packages).

---

## 4. Getting Started

### The 5-Step Workflow

A guided walkthrough dialog appears automatically the first time you launch the tool. It can be re-opened from **Help → Show Quick Workflow** any time. Here's the workflow in compact form:

1. **Find a frame with a visible trail.** Use the slider or `←`/`→` keys to navigate. Set the View dropdown to **Stretched** for faint trails.
2. **Click 🛰 Detect Trails on Current.** Detected lines are drawn as **green** (will be removed) or **grey** (kept) overlays. Click any line to toggle. Tighten **SNR threshold** / **Min length** / **Max width** if you see false positives.
3. **Follow the 💡 Recommendation banner** under the Method dropdown. The tool analyses your specific frame (cross-trail gradient, pearl pattern, mask compactness) and suggests the best inpaint method. Click **Apply** to use it, or pick another method manually.
4. **Switch View to Cleaned Preview** to verify. Tune **Mask dilation** / **Strip width** / **Match sky noise** if needed — the preview re-renders live.
5. **Click ▶ Apply to All Frames.** Current settings are frozen and applied to every sub. Originals move to `originals/`, cleaned files replace them. Progress dialog shows running Cleaned / Skipped / Errors + ETA.

### Why Tune on One Frame?

Detection thresholds and inpaint settings are global across the batch. So you find ONE good test frame (visible trail, representative of the rest of the session), get it perfect, then "Apply to All" runs the same recipe across the folder. Frames without trails are automatically skipped.

---

## 5. The User Interface

### Left Panel — Parameters

| Group | Controls |
|-------|----------|
| **Detection (MRT)** | Scan mode (Quick / Normal / Deep), SNR threshold, Min length, Max width, Persistence check + parameters, Processes (auto-tuned per scan mode), Mask dilation, RGB reduce |
| **Star Protection (Inpaint)** | Protect detected stars (off by default), Sigma, Star halo |
| **Inpainting** | Method dropdown (6 options + 💡 Recommendation banner), Strip width, Match sky noise |
| **Apply** | Confirm each frame before writing, ✓ Apply to Current, Skip, ▶ Apply to All Frames |
| **Footer** | Buy me a Coffee, Help, Close |

### Top Bar

- **View:** Stretched / Mask Overlay / Cleaned Preview
- **🛰 Detect Trails on Current** button
- Status line with detection results, halo growth diagnostics, inpaint statistics (full text on hover)

### Selection Bar (after detection)

- "N of M line(s) marked for removal — ~XXX,XXX px to inpaint"
- **Select All** / **Select None** / **Invert** buttons
- "Click a line to toggle remove / keep" hint

### Canvas

- Image with overlay (lines / mask / cleaned preview depending on View)
- Mouse wheel: zoom; click+drag: pan

### Navigation Bar (bottom)

- First / Previous / Next / Last buttons
- Frame slider
- Frame counter + filename

---

## 6. Detection: How `findsat_mrt` Works

### The Algorithm

The detection backend is **STScI's `findsat_mrt.TrailFinder`** — the same Median Radon Transform pipeline used to find satellite trails in Hubble Space Telescope ACS images (Stark, Avila, Anderson et al. 2022, ACS ISR 2022-08).

The classical Hough/Radon transform projects an image onto a (rho, theta) parameter space by summing pixels along each line. This is fundamentally fragile in star-rich fields: bright stars contribute a "fan of false positives" — every line passing through a bright star gets a boosted sum, so the detector produces many spurious lines.

The **Median Radon Transform** replaces the sum with the *median*. A real satellite trail has roughly constant brightness along its length, so the median equals the per-pixel signal. A bright star occupies < 1% of any line's pixel sample, and the median treats it as an outlier — *it is ignored*. This eliminates the false-positive fan that breaks classical detectors.

### Pipeline Steps

1. **Preprocessing** — subtract median background.
2. **Optional downsampling** for speed (Quick: 4×, Normal: 2×, Deep: 1×).
3. **MRT computation** — for every (rho, theta) compute the median of pixels along that line. Multi-process parallel across angles.
4. **Peak detection in MRT space** with three precomputed kernels (3, 7, 15 px line width).
5. **Per-candidate image-space validation:**
   - Rotate strip around the candidate, fit Gaussian across trail width
   - Reject if width > `max_width` (kills comet tails)
   - Optional persistence test: chunk along trail, require majority of chunks to show consistent SNR (kills non-uniform features)
6. **Endpoint extension** to image boundary, mask construction, bright-halo mask growth.

### Detection Parameters

| Parameter | Effect | Typical |
|-----------|--------|---------|
| **SNR threshold** | Min signal-to-noise for trail acceptance | 5.0 (sensitive) – 8.0 (strict) |
| **Min length** | Min trail length in pixels | 50 (default) |
| **Max width** | Max trail width in pixels (kills comet tails) | 75 (default) |
| **Check persistence** | Demand uniform brightness along trail | On (kills comets) / Off (catches faint trails) |
| **Min persistence** | Fraction of chunks that must pass SNR | 0.5 |
| **Chunk size** | Pixel length of each persistence chunk | 100 |
| **Processes** | MRT worker count | Auto from scan mode (2 / cores/2 / all) |
| **Mask dilation** | Half-width (px) of inpaint mask around each line | 7 (default) |
| **RGB reduce** | How to collapse colour channels into mono for detection | Mean / Max per pixel |

### Scan Mode Presets

| Mode | Downsample | Theta | Persistence | Processes | When to use |
|------|------------|-------|-------------|-----------|-------------|
| **Quick** | 4× | 1.0° | Off | 2–4 | Fast preview, obvious trails |
| **Normal** | 2× | 0.5° | On | cores/2 | Default for most cases |
| **Deep** | 1× | 0.5° | On | all cores | Faint trails, maximum sensitivity |

### Bright-Halo Mask Growth

After the standard dilation, the mask is grown iteratively into any bright pixel (> sky + 3σ) adjacent to it, bounded at 25 hops. This **automatically absorbs the PSF halos** around the bright pearls of a flashing satellite, so no bright ring survives outside a fixed-width mask. The status note reports `halo growth: +N px in K hops`.

---

## 7. Inpaint Methods — Which Should I Pick?

After Detection, the **💡 Recommendation banner** under the Method dropdown picks one for you. But here's the manual decision tree:

| Method | Best when | Speed |
|--------|-----------|-------|
| **Perpendicular Strip Median** | Default safe choice; works on flashing satellites, pearl trails, gradients | Fast |
| **Harmonic / Laplace** | Uniform sky, no pearls — gives the smoothest mathematically optimal fill | Medium |
| **Nearest Neighbor + Smooth** | Fast preview, fallback when the others don't work | Fast |
| **cv2 Fast Marching (Telea)** | Fastest option, good for quick A/B testing | Fastest |
| **cv2 Navier-Stokes** | Same speed class as Telea, slightly better edge propagation | Fastest |
| **Biharmonic (experimental)** | Short isolated masks only — long thin masks produce "string of pearls" ringing | Slow |

### Detailed Explanations

#### Perpendicular Strip Median (recommended default)

Rotates the image so the trail is horizontal. For each column in rotated space, replaces masked pixels with the **median** of `strip_width` unmasked pixels above and below the masked stripe. Then rotates back.

**Strengths:**
- **Preserves sky gradient** running perpendicular to the trail (vignetting, light-pollution slope) — PDE methods would average it away.
- **Robust on flashing satellite trails** — the median naturally rejects pearl peaks at the centreline as outliers; PDE methods overshoot them.
- Vectorised, fast (~0.5 s on 60 MP).

**Tunable:** `Strip width` — number of pixels per side sampled (default 15). Wider strips smooth more but bridge longer gradients.

#### Harmonic / Laplace (∇²u = 0)

Solves the Laplace equation inside the mask with the surrounding sky as Dirichlet boundary. Implementation: bbox-cropped iterative 5-point Laplace smoothing with a nearest-neighbour warm start. Convergence in ~150–400 iterations.

**Strengths:**
- **Maximum principle**: the inpainted values are mathematically bounded by the boundary minima/maxima — no overshoot, no ringing.
- Combined with **Match sky noise**: produces a smooth physical fill PLUS realistic noise on top, **statistically indistinguishable** from real sky.

**Weakness:** Doesn't preserve a cross-trail gradient (averages it). For uniform-sky frames this doesn't matter.

#### Nearest Neighbor + Smooth (fast)

For each masked pixel, finds the nearest unmasked pixel via `scipy.ndimage.distance_transform_edt` and copies its value. Then smooths the filled region with a Gaussian whose σ adapts to mask thickness (σ ≈ half-thickness × 0.75) — softens any visible centreline ridge where the two perpendicular fills meet.

Sub-second per frame. Good fallback if other methods misbehave.

#### cv2 Fast Marching / Telea

OpenCV's C++ Telea (2004) algorithm via `cv2.inpaint(INPAINT_TELEA)`. Internally routes through uint8 with percentile scaling (to handle 16-bit + float inputs that some macOS OpenCV builds silently no-op on). Each masked pixel is filled as a normalised weighted sum of its known neighbours, with weights depending on geometric distance and surface direction. Fastest of the cv2 methods.

#### cv2 Navier-Stokes

Bertalmio et al. 2001: models the inpaint region as a fluid and propagates isophotes (level curves of intensity) into the masked area while preserving local image smoothness. Conceptually cleaner than Telea, identical performance class, slightly better edge behaviour. For sky-dominated regions essentially identical to Telea.

#### Biharmonic (experimental)

`skimage.restoration.inpaint_biharmonic` solves the biharmonic PDE ∇⁴u = 0 on a chunked bbox crop. Mathematically very smooth.

**⚠️ Warning:** The biharmonic equation has **no maximum principle**, so on long thin masks (typical 5000×15 px satellite trail) the solver overshoots/undershoots periodically, producing the classic "string of pearls" dark-spot artefact. A modal warning appears the first time you select this method, with a "Don't show again" option.

Use only on **short, compact masks** (single isolated blobs) where the geometry stays well-conditioned.

### Match Sky Noise

After any inpaint method runs, this post-process adds Gaussian noise inside the mask with σ taken robustly (via sigma-clipped MAD) from a 30-px halo of unmasked sky around the trail. The cleaned region is now **statistically a sky sample** — stack-rejection algorithms cannot distinguish it from real sky.

On by default. Adds ~50 ms per frame. Turn off only for fast A/B testing.

### Star Protection

Optional. When on, detects stars in the image and excludes them from the inpaint mask so they survive cleanup. Smart filter ignores "stars" that lie *inside* the trail mask (those are misclassified trail-pixel peaks, not real stars).

Default off because the naive peak detector misclassifies pearl peaks as stars, which then prevents the inpaint from touching the trail. Turn on manually when you have a known real star sitting in the trail's halo that you want to preserve.

---

## 8. The Recommendation Banner

After every Detect, a blue banner appears under the Method dropdown:

> **💡 Recommendation: Perpendicular Strip Median** *(currently selected)*
> Strong sky gradient (2.4σ) across the trail — Perpendicular Strip Median preserves it. PDE methods would average it away.

If your currently-selected method matches the recommendation, the **Apply** button is greyed out and labelled "✓ in use". Otherwise click **Apply** to switch.

The recommendation is based on three measurements of *your specific frame*:

| Feature | Detection | Recommendation |
|---------|-----------|----------------|
| **Cross-trail gradient ≥ 2σ** | Sample parallel strips ±30 px on each side of the longest trail; compare medians | → Perpendicular Strip Median (preserves gradient) |
| **5+ bright peaks along trail axis** | Sample profile along centreline at sky + 5σ threshold; count connected runs | → Perpendicular Strip Median (median rejects pearls) |
| **Compact mask** (< 8% of diagonal, < 4000 px) | Trail length + mask area | → Harmonic + Match-sky-noise (smooth physical fill) |
| **Uniform sky, no pearls** | Default case | → Harmonic + Match-sky-noise |
| Mixed conditions | Fallback | → Perpendicular Strip Median |

You can always override manually. The recommendation re-runs after every Detect.

---

## 9. File Format Support

### FITS (`.fit`, `.fits`, `.fts`)

The native astrophotography format. Cleaned output is FITS with the **original header preserved verbatim** — WCS, `DATE-OBS`, `BSCALE`/`BZERO`, all instrument keywords. Cleaning operations are appended as `HISTORY` lines. Plate-solving information stays intact.

### XISF (`.xisf`)

PixInsight's native format. Cleaned output stays XISF with **all `FITSKeywords` AND `XISFProperties` preserved** — including PixInsight-style astrometric solutions (`PCL:AstrometricSolution` matrices), camera/filter/exposure metadata. Cleaning operations are appended as `HISTORY` keywords. Output compression matches the source file's compression (so a NINA-saved uncompressed XISF stays uncompressed; a PixInsight LZ4HC-with-shuffle XISF stays the same). Implementation via the [`xisf`](https://pypi.org/project/xisf/) Python package.

### TIFF (`.tif`, `.tiff`, v0.8.0+)

Direct read/write via `tifffile`, bypassing Siril for bit-exact dtype control. The original **dtype** (uint8 / uint16 / uint32 / float32) is preserved. **Compression** (LZW / ZSTD / Deflate / none) is matched. **Photometric interpretation** (mono / RGB) is preserved. **PlanarConfiguration** tag is honoured. RGBA alpha channels are stripped with a log warning.

The `ImageDescription` TIFF tag is carried forward with the cleaning history appended — Siril / ASTAP / NINA all use this tag for plate-solve and processing notes, so the round-trip preserves those.

### RAW (CR2 / CR3 / NEF / ARW / DNG / etc.)

Loaded and debayered via Siril/libraw. Cleaned RAW output is always **FITS** since trail removal on raw CFA data would corrupt the Bayer pattern. The cleaned file is written as `<name>.fit` and the original RAW is preserved in `originals/`.

### `originals/` Subfolder

Every modified file's original is moved to `<source-folder>/originals/<filename>` before the cleaned version is written. **Recovery is always a simple file move back.** The script never deletes anything.

---

## 10. The Apply Workflow

### Apply to Current

Applies the current detection + inpaint settings to the current frame only. Useful for spot-cleaning specific frames manually.

### Apply to All Frames

Confirms with a dialog, then loops through every frame in the folder:

1. **Load** the frame (Siril for FITS/RAW, direct for TIFF/XISF)
2. **Detect** trails (uses the same parameters as your test frame)
3. If no trail detected → skip, file untouched
4. (Optional, if **Confirm each frame** is checked) show preview, ask user Yes/No/Cancel
5. **Inpaint** with the chosen method
6. **Move** the original to `originals/`
7. **Write** the cleaned file under the original filename

### Parallel Batch Pipeline (v0.8.8+)

Without Confirm-each, the batch runs a **2-stage pipeline**: while frame N is being inpainted + written by the main thread, frame N+1 is being loaded + detected by a worker thread. Effective wall-clock speedup: ~1.5–2× on batches of 20+ frames.

### Progress Dialog (v0.8.9+)

Three-line status:

```
Frame 17/50: Lum__LIGHT_017.fit
Cleaned: 12   Skipped: 4   Errors: 1
Elapsed: 4:32   ETA: 9:15
```

Refreshed every frame. **Cancel** is safe — the currently-processing frame finishes (no half-written files), then the loop exits.

### Confirm Each Frame Mode

Useful for the cautious first run, or when you want to manually review every detection in a mixed folder. Disables the parallel pipeline (user reaction time dominates).

### Frames Without Trails Are Skipped

The script never touches a frame where Detect found no trail. The original stays in place, no `originals/` move, no audit entry beyond the skip status.

### Rollback on Error

If the write step fails (disk full, permission denied, corrupted source), the moved original is automatically restored to its location. Full stacktrace goes to the log for diagnostics.

---

## 11. The Audit Report

### `trail_cleanup_report.txt`

Human-readable TSV in the source folder. One line per processed file:

```
# Svenesis Satellite Trail Cleaner -- per-file audit
# Folder: /Users/me/Astro-Images/Comet-PANSTARRS
# A machine-readable JSON twin lives next to this file: trail_cleanup_report.json
# timestamp	status	lines	pixels_replaced	file	note
2026-05-16 17:30:12	cleaned	1	50543	Lum__LIGHT_001.fit	1 trail(s) detected; halo growth: +129 px...
2026-05-16 17:30:34	skipped_no_trail	0	0	Lum__LIGHT_002.fit	No candidates above threshold
2026-05-16 17:30:58	cleaned	1	49872	Lum__LIGHT_003.fit	1 trail(s) detected; halo growth: +98 px...
```

### `trail_cleanup_report.json` (v0.8.9+)

Machine-readable structured twin. Same data, parseable by Excel / pandas / any JSON consumer:

```json
{
  "folder": "/Users/me/Astro-Images/Comet-PANSTARRS",
  "records": [
    {
      "timestamp": "2026-05-16 17:30:12",
      "file": "Lum__LIGHT_001.fit",
      "path": "/Users/me/Astro-Images/Comet-PANSTARRS/Lum__LIGHT_001.fit",
      "status": "cleaned",
      "lines": 1,
      "pixels_replaced": 50543,
      "inpaint_method": "perp_strip",
      "mask_dilation": 7,
      "match_sky_noise": true,
      "scan_mode": "normal",
      "mono_mode": "mean",
      "cleaned_path": "/Users/me/Astro-Images/Comet-PANSTARRS/Lum__LIGHT_001.fit",
      "note": "1 trail(s) detected; halo growth: +129 px in 6 hops...",
      "tool_version": "0.8.9"
    }
  ]
}
```

The JSON write is **atomic** (tempfile + rename) so a crash mid-write doesn't corrupt the audit.

### Status Values

| Status | Meaning |
|--------|---------|
| `cleaned` | Trail detected and successfully inpainted |
| `skipped_no_trail` | No trail detected, file not modified |
| `skipped_user` | User pressed No in Confirm-each dialog |
| `error` | Loading, detection, inpaint, or write failed |

---

## 12. Tips & Best Practices

### Tune on a Good Test Frame

The very first thing: navigate to the frame with the **clearest, brightest, most representative** trail. Get detection and inpaint perfect there. Apply-to-All uses those settings on every frame.

### Use the Recommendation Banner

After Detect, the 💡 banner shows the per-frame-optimal method with a one-sentence rationale. Click Apply unless you have a specific reason to override.

### Verify in Cleaned Preview Before Apply

Switch View → Cleaned Preview. If you can still see *anything* where the trail was — pearls, dark spots, residual streak — fix it before clicking Apply. Often the answer is **increase Mask dilation** (the bright halo around pearls extends beyond the default 7 px).

### Choose the Right Scan Mode

- Quick — fast preview only; may miss faint trails
- Normal — daily driver; covers 95% of cases
- Deep — last resort for very faint trails; uses all CPU cores

### Stack First, Run Cleaner Second (When Unsure)

If you have 10+ subs: stack first **without** the cleaner. If you still see a residual streak in the result, *then* run the cleaner and re-stack. For ≤6 subs, run the cleaner first.

### Watch Out For Comet Tails / Nebulae

The persistence test should reject comet tails (non-uniform brightness along the line), but on very long bright comets it can fail. If Detect picks up the comet tail as a "trail" — turn **persistence check** ON (it usually kills these) or tighten **max width**.

### The Originals Folder Is Your Safety Net

If you ever realize the cleaned files are wrong (bad settings, wrong method), the originals are untouched in `originals/`. Move them back manually, or wait — a future version will add a "Restore originals" button.

### Use Confirm-Each on the First Real Run

If you're new to the tool, enable **Confirm each frame before writing** for your first session. You'll see every detection visually before any file changes. After 5–10 frames you'll know what to expect and can disable it.

### Star Protection: Off Unless Needed

The default is OFF because the naive peak detector mis-identifies pearl peaks as stars and then refuses to inpaint them. Turn it ON manually only when you have a verified bright star sitting in the trail halo that you specifically want to preserve.

---

## 13. Troubleshooting

### "No trails detected" — but I can see one!

Try, in this order:

1. Lower **SNR threshold** (5.0 → 3.0)
2. Lower **Min length** (50 → 20)
3. Increase **Max width** if it looks bloated (75 → 150)
4. Disable **Check persistence** (faint trails may fail the uniform-SNR test)
5. Switch **Scan mode** to **Deep**
6. As a last resort, switch **RGB reduce** to **Max per pixel** (helps when the trail is bright in only one channel)

### Cleaned Preview shows dotted dark spots where the trail was

This is the classic "string of pearls" symptom. Two causes:

1. **You're using Biharmonic.** Switch to Perpendicular Strip Median or Harmonic. The biharmonic equation has no maximum principle and produces this overshoot artefact on long thin masks. The recommendation banner won't pick Biharmonic on long trails for this reason.
2. **Mask dilation too small for bright pearl halos.** Increase Mask dilation from 7 to 10–15. The bright-halo growth step *should* absorb this automatically, but in some cases the explicit dilation helps.

### Cleaned Preview shows a smooth patch with no noise

You probably have **Match sky noise OFF**. Turn it on — the noise injection is what makes the cleaned region statistically indistinguishable from real sky.

### Detection finds 33 candidates instead of 1

False positives. Tighten in this order:

1. **SNR threshold** up (5.0 → 8.0)
2. **Min length** up (50 → 100)
3. Enable **Check persistence** if off
4. **Max width** down if the false positives are wide (75 → 30)

### Comet head/tail gets detected as a trail

1. Enable **Check persistence** — the comet's gradient brightness fails the uniform-SNR test
2. Lower **Max width** to 30–40 px (comet tails are wider than satellite trails)
3. Manually deselect the false-positive line in the canvas before Apply

### Window appears tiny, controls cut off

`win.showMaximized()` is called on launch. If your window manager ignores this (some tiling WMs), manually maximise.

### Help shows the workflow dialog every launch

Click the **Don't show again** checkbox in the workflow dialog. To re-enable: **Help → Reset dismissed dialogs**.

### "Apply to All" is slow

- Check **Scan mode** — if you set it to Deep on 50 frames, expect several minutes
- Confirm-each is on → disable for batch runs (parallel pipeline is bypassed when Confirm-each is on)
- **Processes** spinner — if you manually set it low, restore the auto-tuned value (re-pick the scan mode in the dropdown)

### Cleaned XISF file is half the size of the original

`tifffile` writes use efficient compression. If the original was uncompressed, the cleaned version is now zlib-compressed by default. This is fine for storage and PixInsight reads both transparently.

### `acstools` import error

The script auto-installs `acstools` on first run via `s.ensure_installed`. If it fails, install manually in the Siril Python environment: pip install acstools.

---

## 14. FAQ

**Q: Is the cleaned region "real data" or "fake"?**
A: It's *synthetic* — interpolated from surrounding sky pixels. The Match-sky-noise step adds Gaussian noise so the result is statistically indistinguishable from real sky for stack-rejection algorithms. For photometric work, treat inpainted pixels as missing data: if your science target is *under* the trail, reject the frame entirely instead of cleaning it. The cleaner is for frames where the trail passes through empty sky.

**Q: Why don't you use AI / deep learning?**
A: Deep-learning inpainting models (LaMa, DeepFill, Stable Diffusion) are trained on natural photographs and **hallucinate features** that don't exist — invented stars, galaxies, Bahtinov spikes. That's fabrication, not interpolation, and incompatible with the scientific posture of the underlying STScI detection algorithm. This tool only uses methods that fill from real surrounding pixels.

**Q: Does this preserve plate-solving information?**
A: Yes. FITS headers are preserved verbatim; XISF FITSKeywords + XISFProperties (including AstrometricSolution matrices) are preserved; TIFF ImageDescription is carried forward. Cleaning operations are appended as HISTORY entries.

**Q: Can I undo an Apply?**
A: Manually: move the files from `originals/` back to the source folder, replacing the cleaned versions. A built-in "Restore originals" button is on the roadmap.

**Q: Why is the default inpaint method "Perpendicular Strip Median" and not the "highest quality" Biharmonic?**
A: Biharmonic sounds good but the biharmonic equation has *no maximum principle*, so on long thin satellite trails it overshoots/undershoots periodically and produces visible dark dots ("string of pearls"). Perpendicular Strip Median is robust on real-world data including flashing satellites. The recommendation banner picks the right one per frame.

**Q: How does the multiprocessing scale?**
A: The MRT computation is embarrassingly parallel over theta angles. Deep mode uses all CPU cores → ~Nx speedup on detection. Apply-to-All also runs a 2-stage pipeline (load+detect overlaps with inpaint+write) for another ~1.5–2× wall-clock speedup.

**Q: Does the tool work with mono (luminance-only) data?**
A: Yes, this is the most common case. The RGB-reduce option only matters for actual colour FITS / XISF / TIFF with 3 channels.

**Q: Can I share the cleaned files with PixInsight / Photoshop / Affinity / DeepSkyStacker?**
A: Yes. FITS / XISF / TIFF round-trips preserve all standard headers and metadata. Any tool that reads these formats will read the cleaned versions.

**Q: My subs are 60 MP each. Will the tool run out of memory?**
A: No. The tool processes one frame at a time (plus one in the prefetch worker during batch). Peak memory per frame is ~1 GB on 60 MP RGB; ~250 MB on 60 MP mono. The parallel pipeline adds ~1 extra frame's worth.

**Q: Is the recommendation banner perfect?**
A: It's a heuristic based on three measurements (cross-trail gradient, pearl count, mask compactness). It picks the right method in maybe 90% of cases. For edge cases (very faint trails, strong nebulosity nearby), override manually.

---

## 15. Scientific Background — Why We Inpaint

### What STScI Does (and Doesn't Do)

The detection backend in this tool is **STScI's `findsat_mrt.TrailFinder`** — the same Median Radon Transform algorithm published in Stark, Avila, Anderson et al. (ACS ISR 2022-08) and used to find satellite trails in HST/ACS images.

Importantly, the original paper does **NOT** recommend any specific inpainting algorithm. It treats the output mask as a Data Quality flag for the downstream HST pipeline (`AstroDrizzle`), which combines multiple exposures and simply **rejects** the masked pixels — the sky information for the trail region comes from the *other* exposures in the stack, not from spatial interpolation. That is the cleanest possible approach: every output pixel is a real measurement from some sub, never an estimate.

### Why We Deviate

STScI's mask-and-reject approach requires **enough exposures** for the rejection to leave a clean sky in the trail region. HST programmes typically have 8–16+ well-dithered sub-exposures — the trail in a single sub is, statistically, an outlier the σ-clip rejects cleanly.

Amateur astrophotography usually has 4–6 subs (often fewer on rare targets). At n=5, σ-clipping a single outlier doesn't have enough surviving population to leave a confident sky estimate; below n=4 it is statistically not possible. The trail residual survives the stack and degrades the final image.

**That gap is what this tool fills.** Spatial inpainting per-frame, *before* stacking, lets the σ-clip in Siril's stacker work on already-clean inputs.

### How We Stay HST-Faithful in Spirit

Even though spatial inpainting introduces synthetic data, the HST tradition of **not hallucinating structure** guides our defaults:

- The default method, **Perpendicular Strip Median**, copies the median of the local sky perpendicular to the trail — no model, no learned prior, no invented stars.
- **Match-sky-noise** adds Gaussian noise with σ matching the local sky. The inpainted region is statistically a sky sample.
- **Star Protection** excludes detected stars from the mask so we never replace a real star with sky.
- We **refuse to ship deep-learning inpainting** because those models hallucinate stars, galaxies and Bahtinov-spike-like structure that is not in the original data. That is fabrication, not interpolation, and incompatible with the scientific posture of the underlying STScI algorithm.

### When To Skip This Tool

If your stack has **8 or more well-dithered subs** and the trail does not repeat across multiple of them, Siril's built-in σ-clip / Winsorized / Linear-Fit rejection during `Stacking → Image stacking` is mathematically the correct choice. It uses real measurements, not estimates. This tool is most useful for the regime where σ-clip cannot reach a clean result: few subs, repeating trails, or trails crossing science targets where you want to preserve the frame.

### Reference

> Stark, D., Avila, R. J., Anderson, J., et al. 2022, *findsat_mrt: A New Algorithm for Detecting Linear Features in Astronomical Images*, ACS Instrument Science Report 2022-08, STScI.

---

*Made by [Svenesis](https://www.svenesis.org). [Buy me a coffee ☕](https://buymeacoffee.com/sramuschkat) if this saved your stack.*
