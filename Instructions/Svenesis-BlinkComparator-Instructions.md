# Svenesis Blink Comparator — User Instructions

**Version 1.2.3** | Siril Python Script for Frame Selection & Quality Analysis

> *Comparable to PixInsight's Blink + SubframeSelector — but free, open-source, and tightly integrated with Siril.*

---

## Table of Contents

1. [What Is the Blink Comparator?](#1-what-is-the-blink-comparator)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Understanding the Metrics](#6-understanding-the-metrics)
7. [Display Modes](#7-display-modes)
8. [Frame Selection Methods](#8-frame-selection-methods)
9. [The Undo System](#9-the-undo-system)
10. [Applying Changes to Siril](#10-applying-changes-to-siril)
11. [Export Options](#11-export-options)
12. [Use Cases & Workflows](#12-use-cases--workflows)
13. [Keyboard Shortcuts](#13-keyboard-shortcuts)
14. [Tips & Best Practices](#14-tips--best-practices)
15. [Troubleshooting](#15-troubleshooting)
16. [FAQ](#16-faq)

---

## 1. What Is the Blink Comparator?

The **Svenesis Blink Comparator** is a Siril Python script that rapidly animates ("blinks") through all frames of an astrophotography sequence so you can visually inspect them, identify bad frames, and reject them before stacking.

Think of it as a **quality control inspector** for your subframes. It combines:

- **Visual inspection** — watch your frames play like a movie to spot problems
- **Statistical analysis** — see FWHM, roundness, star count, and background for every frame
- **One-click frame rejection** — mark bad frames and tell Siril which to exclude from stacking

The result: a cleaner, sharper final stack because you removed the frames that would have dragged the quality down.

---

## 2. Background for Beginners

### Why Do We Need to Select Frames?

When you image the night sky, you take many individual exposures (called "subframes" or "subs"). These get aligned and stacked into one final image. But not every subframe is equally good. During a typical imaging session, several things can go wrong:

| Problem | What Happens | How It Looks |
|---------|-------------|--------------|
| **Clouds** | Thin clouds drift through your field | Background brightens, stars fade |
| **Satellite trails** | A satellite crosses your image | Bright streak across the frame |
| **Tracking errors** | Your mount hiccups | Stars become elongated lines |
| **Focus drift** | Temperature changes shift focus | Stars bloat and become fuzzy |
| **Wind gusts** | Wind shakes your scope | Stars become bloated for a few frames |
| **Airplane lights** | A plane blinks through | Bright flashing spot |
| **Dew / frost** | Moisture forms on the optics | Stars halo, background rises, star count drops |

If you include these bad frames in your stack, they **degrade** your final image: blurrier stars, higher noise, trailing artifacts. Removing even 5–10% of the worst frames can dramatically improve your result.

### What Is "Blinking"?

A **blink comparator** is an astronomy technique dating back to the 1920s (it's how Pluto was discovered!). You rapidly switch between images so that anything that changes — a moving object, a brightness change, a focus shift — immediately jumps out to the human eye.

In astrophotography, blinking through your subframes makes problems **obvious** that you'd never notice looking at individual frames.

### What Is FWHM?

**FWHM** (Full Width at Half Maximum) measures star sharpness in pixels. Imagine a star as a bell curve of brightness — FWHM is the width of that bell at half its peak height.

- **Lower FWHM = sharper stars** (good)
- **Higher FWHM = bloated stars** (bad — focus, seeing, or tracking issues)
- Typical range: 2–6 pixels depending on your setup and conditions

### What Is Roundness?

**Roundness** measures how circular your stars are, on a scale of 0 to 1:

- **1.0 = perfect circle** (ideal)
- **0.0 = a line** (severe trailing)
- Above 0.75 is generally good
- Below 0.6 usually indicates tracking or wind problems

Related to **eccentricity** (used by PixInsight): `eccentricity ≈ 1 − roundness`.

### What Is Background Level?

The **background level** is the median brightness of the sky in your frame. It should be consistent across all frames.

- **Spike up** = clouds, light pollution, airplane, moon
- **Rising trend** = dawn approaching, clouds thickening
- **Consistent** = good imaging conditions

---

## 3. Prerequisites & Installation

### Requirements

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| **Siril** | 1.4.0+ | Must have Python script support enabled |
| **sirilpy** | Bundled | Comes with Siril 1.4+ |
| **numpy** | Any recent | Auto-installed by the script |
| **PyQt6** | 6.x | Auto-installed by the script |
| **matplotlib** | 3.x | Auto-installed by the script |
| **Pillow** | Any | *Optional* — only needed for GIF export |

### Installation

1. Download `Svenesis-BlinkComparator.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script automatically installs missing Python dependencies (`numpy`, `PyQt6`, `matplotlib`) on first run.

---

## 4. Getting Started

### Step 1: Load a Registered Sequence

The script works on a **sequence** loaded in Siril — not a single image. You need at least 2 frames, but a real session typically has 50–500+.

**If you already have a registered sequence:**
1. Set the working directory to the folder containing your `.seq` file and `.fit` files.
2. Siril automatically detects and shows the sequence in the Frame List at the bottom.

**If you have raw FITS files that haven't been processed:**
```
# In the Siril console:
cd /path/to/your/lights
convert light -out=./process
cd process
register pp_light
```
This creates a registered sequence `r_pp_light_` that the Blink Comparator can work with.

**If you used a preprocessing script (e.g., SeeStar):**
Your script likely already created a registered sequence. Set the working directory to the output folder — Siril will detect the `.seq` file.

### Step 2: Run the Script

Go to **Processing → Scripts → Svenesis Blink Comparator**.

The script will:
1. Load the sequence metadata (frame count, dimensions, channels)
2. Load per-frame statistics (FWHM, roundness, background, stars, median, sigma)
3. Open the main window with the first frame displayed

### Step 3: Run Star Detection (If Needed)

If the FWHM, Roundness, Stars, and Weight columns are empty, a **yellow banner** appears at the top:

> ⚠️ No star detection data. Click to run star detection...

Click the banner. This runs Siril's `register <seq> -2pass` command, which detects stars in every frame and computes FWHM, roundness, background level, and star count. It takes a few seconds to a few minutes depending on the number of frames.

**Note:** Median and Sigma are *always* available — they don't require star detection.

### Step 4: Inspect and Select

Now you can:
- **Play the animation** (Space) to visually spot problems
- **Sort the Statistics Table** by FWHM (worst frames at top)
- **Use Batch Reject** to remove the worst 10% automatically
- **Mark individual frames** with G (good) or B (bad)

### Step 5: Apply and Stack

Click **Apply Changes to Siril** to send your frame selections. Then stack in Siril as usual — excluded frames will be skipped.

---

## 5. The User Interface

The window is divided into several areas:

### Left Panel (Control Panel)

The left side (340px wide) contains all controls, organized in collapsible sections:

- **Playback Controls:** Play/Pause, frame navigation, speed slider, loop toggle
- **Display Mode:** Normal, Difference, Only Included, Side by Side
- **Display Options:** Linked stretch, crossfade, frame overlay, thumbnail size, histogram
- **Frame Selection:** Keep/Reject buttons, auto-advance, pending changes counter, Apply button
- **Batch Selection:** Threshold filter, worst N%, approval expressions
- **Export:** Rejected list, CSV, GIF, clipboard

### Right Panel (Tabbed Area)

The main area has four tabs:

#### Viewer Tab
The frame display canvas. Shows the current frame with autostretch applied.
- **Scroll wheel** to zoom (0.1x to 20x)
- **Right-click drag** to pan
- **Z** to reset zoom to fit-to-window
- **1:1 button** for pixel-perfect zoom
- **ROI mode:** Draw a rectangle to blink only that region

#### Statistics Table Tab
All frames listed in a sortable table with 10 columns:
- Frame #, Weight, FWHM, Roundness, BG Level, Stars, Median, Sigma, Date, Status
- **Click a column header** to sort (click again to reverse direction)
- **Click a row** to jump to that frame in the Viewer
- **Ctrl+click** or **Shift+click** to multi-select rows
- **Right-click** selected rows → "Reject selected"
- Excluded rows have a red-tinted background
- The current frame row is highlighted in blue

#### Statistics Graph Tab
Line charts showing metrics across all frames:
- Toggleable: FWHM, Background, Roundness (checkboxes above the chart)
- **Thin line** = raw per-frame values
- **Bold line** = 7-frame running average (reveals trends)
- **Red dots** = excluded frames
- **White dashed line** = your current frame position
- Great for spotting: focus drift (FWHM ramp), clouds (background spike), tracking degradation (roundness drop)

#### Scatter Plot Tab
2D scatter plot of any two metrics:
- Select X and Y axes from dropdown menus
- **Blue dots** = included frames
- **Red ✕** = excluded frames
- **Red star** = current frame
- **Click any dot** to jump to that frame
- Best combinations: **FWHM vs Roundness** (star quality), **FWHM vs Background** (clouds + seeing)

### Bottom Bar (Filmstrip)

A horizontal scrollable strip of frame thumbnails (always visible):
- **Green border** = included
- **Red border** = excluded
- **Blue border** = current frame
- Click any thumbnail to jump to that frame
- Thumbnails load lazily as you scroll
- Adjust size with the slider in Display Options (40–160px)

---

## 6. Understanding the Metrics

### FWHM (Full Width at Half Maximum)

| Aspect | Details |
|--------|---------|
| **What** | Star diameter at half peak brightness, in pixels |
| **Source** | Siril registration data (`get_seq_regdata`) |
| **Good values** | Lower is better. Typical: 2–6 px |
| **Requires** | Star detection must have been run |

**Interpretation:** Sudden increase = focus drift, wind, or bad seeing. Gradual ramp = thermal focus shift. Isolated spike = wind gust.

### Roundness

| Aspect | Details |
|--------|---------|
| **What** | Star circularity, 0 (line) to 1 (perfect circle) |
| **Source** | Siril registration data |
| **Good values** | Above 0.75. Below 0.6 = problems |
| **Requires** | Star detection must have been run |

**Interpretation:** Low roundness = tracking error, wind, or optical tilt. Group of low-roundness frames = mount hiccup or wind burst.

### Background Level (BG Level)

| Aspect | Details |
|--------|---------|
| **What** | Median sky brightness, normalized to [0, 1] |
| **Source** | Registration data (`background_lvl`) or `stats.median` as fallback |
| **Good values** | Consistent across frames |
| **Requires** | Always available (fallback uses basic stats) |

**Interpretation:** Spike = clouds, airplane, or moon. Rising trend = dawn or increasing light pollution.

### Stars (Star Count)

| Aspect | Details |
|--------|---------|
| **What** | Number of stars detected in the frame |
| **Source** | Siril registration data (`number_of_stars`) |
| **Good values** | Consistent count; higher is generally better |
| **Requires** | Star detection must have been run |

**Interpretation:** Sudden drop = clouds, dew, or severe defocus. Gradual decline = thin clouds or rising humidity.

### Weight (Composite Quality Score)

| Aspect | Details |
|--------|---------|
| **What** | Single quality score from 0 (worst) to 1 (best) |
| **Source** | Computed by the script from FWHM, Roundness, Background, Stars |
| **Requires** | At least some of the above metrics available |

**Formula:**
```
w_fwhm  = 1 − (fwhm − min) / (max − min)        [lower FWHM = better]
w_round = roundness                                [higher = better]
w_bg    = 1 − (bg − min) / (max − min)            [lower BG = better]
w_stars = sqrt(stars) / sqrt(max_stars)            [more = better]
Weight  = mean of available factors
```

**Interpretation:** Sort by Weight ascending to see worst frames first. Use "Reject worst N%" with Weight to cull the lowest-quality subframes.

### Median

| Aspect | Details |
|--------|---------|
| **What** | Median pixel value of the entire frame, normalized to [0, 1] |
| **Source** | Siril per-channel statistics (`get_seq_stats`) |
| **Always available** | Yes — no star detection needed |

**Interpretation:** Nearly identical to Background Level for astro images where sky dominates. Useful as a universal fallback metric.

### Sigma (σ)

| Aspect | Details |
|--------|---------|
| **What** | Standard deviation of pixel values — measures spread |
| **Source** | Siril per-channel statistics |
| **Always available** | Yes — no star detection needed |

**Interpretation:** High sigma + high background = noise from clouds (bad). High sigma + low background = genuine deep-sky signal (good).

### Date

| Aspect | Details |
|--------|---------|
| **What** | Observation timestamp from FITS header (`DATE-OBS`) |
| **Source** | FITS metadata via `get_seq_imgdata` |
| **Note** | Not all cameras write this field (e.g. SeeStar S50) |

### Status

Shows **Included** (green) or **Excluded** (red). Changes are local until you click "Apply Changes to Siril".

---

## 7. Display Modes

### Normal Mode (Default)

Standard autostretch view. Each frame is stretched using a Midtone Transfer Function (STF) that replicates Siril/PixInsight's autostretch algorithm. Good for general visual inspection.

**Linked Stretch** (checkbox):
- **ON:** Same stretch parameters for all frames. Brightness differences between frames become visible (clouds, background changes). Recommended for comparing frames.
- **OFF:** Each frame gets its own optimal stretch. Shows the most detail in each frame individually, but frames may appear to flash bright/dark.

### Difference Mode (D key)

Shows `|current_frame − reference_frame| × 5` — anything that changes between frames lights up as a bright spot on a dark background.

**Best for detecting:**
- Satellite trails (bright streak)
- Moving objects (asteroids, aircraft)
- Clouds (diffuse glow)
- Tracking shifts

### Only Included Mode

Playback skips all excluded frames. Use this after marking to verify that the remaining frames look clean.

### Side by Side Mode

Shows the current frame on the left and the reference frame on the right, with synchronized zoom and pan. Useful for direct A/B comparison.

### Additional Display Features

- **Crossfade Transition:** Smooth 200ms blend between frames instead of a hard cut. Makes motion artifacts more visible.
- **Frame Info Overlay:** Shows frame number, FWHM, roundness, and weight in the top-left corner. Toggleable.
- **A/B Toggle (T key):** Pin the current frame, then press T to flip between the pinned frame and whatever frame you navigate to.
- **ROI Blink:** Click "Select ROI", draw a rectangle on the image, and the viewer zooms into that region. Perfect for checking star shapes in a specific corner.

---

## 8. Frame Selection Methods

### Method 1: Manual Marking (G / B Keys)

The simplest approach — scrub through your sequence and mark each frame:

1. Press **Space** to play, or use **←/→** to step frame by frame
2. Press **B** when you see a bad frame (exclude)
3. Press **G** to re-include a frame you previously excluded
4. With **Auto-advance** enabled (default), the viewer jumps to the next frame after marking

**Best for:** Small sequences (< 100 frames), or reviewing individual frames flagged by other methods.

### Method 2: Batch Reject by Threshold

Reject all frames that exceed a specific metric value:

1. In the **Batch Selection** section, choose a metric (FWHM, Background, Roundness)
2. Choose an operator (>, <, >=, <=)
3. Enter a threshold value
4. The **preview** shows how many frames match
5. Click **"Reject Matching"**

**Example:** Reject all frames with FWHM > 4.5 → removes all frames with bloated stars.

### Method 3: Reject Worst N%

Automatically reject the bottom percentage of frames:

1. Select **"Worst N%"** mode
2. Choose a metric (FWHM, Background, Roundness, Weight)
3. Set the percentage (e.g., 10%)
4. Click **"Reject Matching"**

For FWHM and Background, "worst" = highest value. For Roundness and Weight, "worst" = lowest value.

**Example:** Reject worst 10% by Weight → removes the 9 lowest-quality frames from a 90-frame sequence.

### Method 4: Approval Expressions (Multi-Criteria)

Define multiple conditions that good frames must satisfy simultaneously:

1. Click **"+ Add Condition"**
2. Choose metric, operator, and value for each condition
3. Add more conditions as needed (AND logic)
4. The preview shows how many frames fail
5. Click **"Reject Non-Matching"** to exclude all frames that fail any condition

**Example:**
```
FWHM < 4.5  AND  Roundness > 0.7  AND  Stars > 50
```
This keeps only frames with sharp, round stars and good star count.

**Comparable to** PixInsight's SubframeSelector approval expressions.

### Method 5: Multi-Select in Table

For surgical removal of specific frames you've identified:

1. Switch to the **Statistics Table** tab
2. **Ctrl+click** individual rows, or **Shift+click** for a range
3. **Right-click** the selection → "Reject N selected frame(s)"

**Best for:** Removing specific outliers you've identified in the scatter plot or graph.

---

## 9. The Undo System

Every marking action can be undone with **Ctrl+Z**:

- **Single marks** (G/B on one frame) undo one at a time
- **Batch operations** (threshold reject, worst N%, approval expression, multi-select) undo the **entire batch** with a single Ctrl+Z
- Undo stack depth: 500 operations

**Example:** You reject the worst 15% (13 frames). You realize that was too aggressive. One Ctrl+Z restores all 13 frames.

---

## 10. Applying Changes to Siril

All marks are **local** until you explicitly apply them:

1. The **"Pending: N changes"** counter in the left panel shows how many frames differ from Siril's current state
2. Click **"Apply Changes to Siril"** to send all changes
3. A confirmation dialog shows the exact changes that will be made
4. Once applied, Siril's sequence is updated — excluded frames will be skipped during stacking

**If you close the window with unsaved changes,** a dialog asks whether to apply or discard them.

---

## 11. Export Options

### Export Rejected Frame List (.txt)

Saves a text file listing all excluded frame indices. Includes a header with sequence name, total frames, and rejection count.

### Export Statistics CSV (.csv)

Exports the full statistics table as a CSV file with columns:
`Frame, Weight, FWHM, Roundness, Background, Stars, Median, Sigma, Date, Included`

Useful for external analysis in spreadsheets, Python notebooks, or other tools.

### Export Animated GIF (.gif)

Creates an animated GIF of the blink animation:
- Only included frames (excluded frames are skipped)
- Scaled to 480px maximum dimension
- Uses the current playback speed (FPS)
- Requires the Pillow library (`pip install Pillow`)

Great for sharing on forums, social media, or observation reports.

### Copy Frame to Clipboard (Ctrl+C)

Copies the current frame (as displayed, with stretch applied) to the system clipboard. Paste directly into a forum post, image editor, or presentation.

---

## 12. Use Cases & Workflows

### Use Case 1: Quick Session Review (5 minutes)

**Scenario:** You just finished an imaging session with 120 subframes and want a quick quality check before stacking.

**Workflow:**
1. Load the registered sequence in Siril
2. Run the Blink Comparator
3. Run star detection if needed (click the yellow banner)
4. Go to the **Statistics Table** tab, sort by **FWHM descending** — the worst frames are now at the top
5. Click **"Reject worst 10%"** by FWHM
6. Review the **Statistics Graph** — check for any remaining outliers
7. Apply changes → stack in Siril

**Time:** ~5 minutes for 120 frames.

### Use Case 2: Cloud-Affected Session

**Scenario:** Clouds rolled through during your session. Some frames are partially clouded.

**Workflow:**
1. Open the Blink Comparator
2. Go to the **Statistics Graph** tab, enable **Background** checkbox
3. Look for spikes — these are the cloudy frames
4. Use **Batch Reject**: Background > [threshold from the spike level]
5. Also check **Stars** — cloudy frames have fewer detected stars
6. Verify with **Difference Mode** (D key) — cloud patches glow bright

### Use Case 3: Tracking Problem Diagnosis

**Scenario:** Some frames show elongated stars. You want to find and remove them, and understand when the problem occurred.

**Workflow:**
1. Open the Blink Comparator
2. Go to the **Statistics Graph**, enable **Roundness**
3. Look for dips — these are frames with tracking errors
4. Use **Approval Expression**: `Roundness > 0.75`
5. "Reject Non-Matching" removes all frames with elongated stars
6. Check the **Scatter Plot** (FWHM vs Roundness) — outlier frames are far from the cluster
7. Click outlier dots to inspect individual frames
8. If tracking errors are concentrated in a time range, you may have a periodic error in your mount

### Use Case 4: Focus Drift Session

**Scenario:** Your FWHM starts good but gradually increases throughout the session as temperature drops and focus shifts.

**Workflow:**
1. Open the Blink Comparator
2. **Statistics Graph** → FWHM shows an upward ramp
3. The **running average** (bold line) clearly shows the trend
4. Use **Batch Reject**: FWHM > [your threshold, e.g., 4.5]
5. Or use **"Reject worst 20%"** by FWHM — this removes the end-of-session frames automatically
6. Consider: in future sessions, use an autofocuser or refocus every 30 minutes

### Use Case 5: Satellite Trail Hunting

**Scenario:** You're imaging near the celestial equator where satellite trails are frequent.

**Workflow:**
1. Open the Blink Comparator
2. Press **D** for **Difference Mode** — satellites appear as bright streaks against a dark background
3. Press **Space** to play at 3–5 FPS — trails flash visibly
4. When you spot one, press **B** to exclude that frame
5. Continue playing to catch all trails
6. Difference mode makes trails **much** more visible than normal mode

### Use Case 6: Data-Driven Selection (PI SubframeSelector Replacement)

**Scenario:** You want a quantitative, PixInsight-style selection process based on multiple criteria.

**Workflow:**
1. Run star detection to populate all metrics
2. Go to **Statistics Table**, sort by **Weight** ascending (worst frames first)
3. Review the bottom 10–20% — do they look visibly worse?
4. Set up an **Approval Expression**:
   ```
   FWHM < 4.0 AND Roundness > 0.75 AND Background < 0.012 AND Stars > 40
   ```
5. Preview shows N frames would be rejected
6. Click "Reject Non-Matching"
7. Verify in the **Scatter Plot** (FWHM vs Roundness) — the remaining cluster should be tight
8. **Export CSV** for your records
9. Apply changes → stack

### Use Case 7: Before vs. After Comparison

**Scenario:** You want to verify that your frame selection actually improved the remaining set.

**Workflow:**
1. After marking frames, note the **session summary** statistics (mean FWHM, included count)
2. Switch to **"Only Included"** display mode
3. Play — verify the animation looks smooth with no flashing or artifacts
4. Check the **Statistics Graph** — the red dots (excluded) should be at the spikes
5. The remaining blue line should be more consistent
6. **Export GIF** of the clean sequence for your imaging log

### Use Case 8: Corner Star Shape Inspection

**Scenario:** You suspect optical tilt or coma in one corner and want to check across all frames.

**Workflow:**
1. Click **"Select ROI"** in the display options
2. Draw a rectangle over the problematic corner
3. Click **1:1** zoom for pixel-perfect view
4. Play the animation — star shapes in that corner blink through rapidly
5. Frames where corner stars are worse than usual may have had flexure or tilt changes
6. Mark those frames with B
7. Click "Clear ROI" to return to full-frame view

---

## 13. Keyboard Shortcuts

### Playback

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` | Previous frame |
| `→` | Next frame |
| `Home` | First frame |
| `End` | Last frame |
| `1`–`9` | Set FPS directly |
| `+` | Speed up (increment FPS) |
| `-` | Slow down (decrement FPS) |

### Frame Marking

| Key | Action |
|-----|--------|
| `G` | Mark as good (include) |
| `B` | Mark as bad (exclude) |
| `Ctrl+Z` | Undo last marking (single or batch) |

### Display

| Key | Action |
|-----|--------|
| `D` | Toggle Difference mode |
| `Z` | Reset zoom to fit-to-window |
| `T` | Pin current frame / toggle A/B comparison |
| `Ctrl+C` | Copy current frame to clipboard |

### Other

| Key | Action |
|-----|--------|
| `Esc` | Close window |

---

## 14. Tips & Best Practices

### General Workflow

1. **Start with data, then verify visually.** Sort by FWHM or Weight first to identify bad frames numerically. Then switch to the Viewer to confirm they actually look bad.

2. **Don't over-reject.** More frames = lower noise in the stack. Reject only frames that are clearly defective. A frame with FWHM 4.2 when your best is 3.0 is still contributing signal — consider keeping it unless it's an outlier.

3. **Use the running average.** In the Statistics Graph, the bold trend line reveals patterns (focus drift, clouds) that are invisible in the noisy raw data line.

4. **Check the Scatter Plot.** FWHM vs Roundness is the single most informative combination. The main cluster represents your "normal" frames. Outliers far from the cluster are your rejection candidates.

5. **Always use Difference Mode for satellites.** They're sometimes invisible in Normal mode but glow like neon signs in Difference mode.

### Performance Tips

6. **First run is slow, subsequent runs are fast.** The script caches statistics and thumbnails. Navigating frames is instant once cached.

7. **Large sequences (500+ frames):** The statistics loading may take a minute. Be patient — it only happens once per session.

8. **Playback speed:** If playback stutters at high FPS, lower the speed. The frame cache preloads ahead, but very high FPS on large frames can outrun the cache.

### Siril Integration

9. **Always register first.** The Blink Comparator works on any sequence, but it works best on registered (aligned) sequences. Difference mode and side-by-side mode require alignment to be meaningful.

10. **Star detection is separate from registration.** Your preprocessing script may register the sequence without computing per-frame FWHM. That's why the "Run Star Detection" banner appears. Clicking it is safe — it doesn't modify your files.

11. **Changes are non-destructive.** "Apply Changes" only sets the include/exclude flag in the .seq file. Your FITS files are never modified or deleted.

---

## 15. Troubleshooting

### "No sequence loaded" error

**Cause:** No sequence is active in Siril.
**Fix:** Set the working directory to the folder containing your `.seq` file and `.fit` files. Siril should detect the sequence automatically.

### FWHM / Roundness / Stars columns are empty

**Cause:** Star detection hasn't been run on this sequence.
**Fix:** Click the yellow "Run Star Detection" banner. This runs `register <seq> -2pass` which computes all star metrics without creating new files.

### Star detection ran but columns are still empty

**Cause:** For RGB images, Siril stores registration data on the green channel (channel 1). Older versions of the script may have only checked channel 0.
**Fix:** Update to the latest version of the script. It scans all channels.

### Font warning: "Sans-serif"

**Message:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"...`
**Impact:** Cosmetic only, no effect on functionality.

### Script crashes on close with SortOrder error

**Message:** `TypeError: int() argument must be a string... not 'SortOrder'`
**Fix:** Update to the latest version (fixed in v1.2.3+).

### GIF export fails

**Cause:** The Pillow library is not installed.
**Fix:** In a terminal: `pip install Pillow` (or install via Siril's Python environment).

### Playback is slow / stutters

**Cause:** Large image dimensions or insufficient memory for the frame cache.
**Fix:**
- Reduce playback speed (use 3–5 FPS instead of 30)
- The cache holds 80 frames by default — sufficient for most sequences
- Close other memory-intensive applications

---

## 16. FAQ

**Q: Does this replace PixInsight's Blink + SubframeSelector?**
A: For visual inspection and basic frame selection, yes — it actually offers more visualization features than PI Blink (difference mode, side-by-side, A/B toggle, ROI blink, crossfade, filmstrip). For the statistical side, it covers most of SubframeSelector's features (sortable table, batch reject, approval expressions, scatter plot) but PI has SNR and the proprietary PSFSignalWeight metric that we don't replicate.

**Q: Can I use this on unregistered sequences?**
A: Yes, but Difference mode and Side-by-Side mode won't be useful because the frames aren't aligned. Visual blinking in Normal mode still works.

**Q: Does "Apply Changes" modify my FITS files?**
A: No. It only updates the include/exclude flag in the `.seq` file. Your FITS files are never touched.

**Q: How much does rejecting frames improve the stack?**
A: It depends on your data. Removing 5–10% of the worst frames often improves the stack noticeably — sharper stars, lower noise in the background. Removing more than 20–30% usually means diminishing returns (you're losing more signal than you're gaining in quality).

**Q: What's the difference between "Linked" and "Independent" stretch?**
A: **Linked** uses the same stretch for all frames — brightness differences between frames are visible (good for spotting clouds). **Independent** optimizes each frame separately — you see the most detail in each frame, but the animation may appear to flash.

**Q: Can I re-include frames I've excluded?**
A: Yes. Press **G** on an excluded frame to re-include it. Or use **Ctrl+Z** to undo the last marking operation.

**Q: Why is the Weight column showing 0 for all frames?**
A: Weight requires FWHM, Roundness, Background, and Stars data. If star detection hasn't been run, all inputs are 0, so the weight is 0. Run star detection first.

**Q: Can I use this for planetary imaging?**
A: The tool is designed for deep-sky subframe selection. Planetary imaging (lucky imaging) uses different quality metrics and typically processes thousands of very short exposures. Tools like AutoStakkert or Planetary System Stacker are better suited for planetary work.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
