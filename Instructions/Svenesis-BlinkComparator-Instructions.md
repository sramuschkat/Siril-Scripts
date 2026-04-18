# Svenesis Blink Comparator — User Instructions

**Version 1.2.8** | Siril Python Script for Frame Selection & Quality Analysis

> *Comparable to PixInsight's Blink + SubframeSelector — but free, open-source, and tightly integrated with Siril.*

---

## Table of Contents

1. [What Is the Blink Comparator?](#1-what-is-the-blink-comparator)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Understanding the Metrics](#6-understanding-the-metrics)
7. [Display Modes & Autostretch Presets](#7-display-modes--autostretch-presets)
8. [Frame Selection Methods](#8-frame-selection-methods)
9. [The Undo System](#9-the-undo-system)
10. [Applying Rejections (File Moves)](#10-applying-rejections-file-moves)
11. [Export Options](#11-export-options)
12. [Use Cases & Workflows](#12-use-cases--workflows)
13. [Keyboard Shortcuts](#13-keyboard-shortcuts)
14. [Tips & Best Practices](#14-tips--best-practices)
15. [Troubleshooting](#15-troubleshooting)
16. [FAQ](#16-faq)
17. [Changes Since v1.2.3](#17-changes-since-v123)

---

## 1. What Is the Blink Comparator?

The **Svenesis Blink Comparator** is a Siril Python script that rapidly animates ("blinks") through all frames of an astrophotography sequence so you can visually inspect them, identify bad frames, and reject them before stacking.

Think of it as a **quality control inspector** for your subframes. It combines:

- **Visual inspection** — watch your frames play like a movie to spot problems
- **Statistical analysis** — see FWHM, roundness, star count, and background for every frame
- **One-click frame rejection** — mark bad frames; on close the script writes a `rejected_frames.txt` audit file and moves the rejected FITS into a `rejected/` subfolder next to your originals

The result: a cleaner, sharper final stack because you removed the frames that would have dragged the quality down — and because rejection is a simple file move, you can reverse any decision by dragging the file back out of `rejected/`.

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

Starting in v1.2.4, the Blink Comparator is **folder-based**: you point it at a directory of FITS files, and it builds its own temporary sequence. You never need to pre-register or pre-load anything in Siril.

### Step 1: Run the Script

Go to **Processing → Scripts → Svenesis Blink Comparator**.

A folder picker opens. Select the folder containing your FITS frames (`.fit`, `.fits`, `.fts` — extensions are matched case-insensitively, so `.FIT` / `.Fits` work too). Compressed FITS (`.fz`, `.gz`) are **not** supported — decompress first if needed. The script scans one directory level deep.

### Step 2: Wait for Sequence Building

Behind the scenes the script:

1. Runs Siril's `cd <folder>` + `convert svenesis_blink -fitseq` to build a single-file FITSEQ temp sequence named `svenesis_blink.fits`.
2. Loads the sequence (`load_seq svenesis_blink`).
3. Probes frame metadata (dimensions, channels, count).
4. Loads per-frame statistics (FWHM, roundness, background, stars, median, sigma) from Siril's registration data if present.

A progress bar shows the stats-loading phase. The temp sequence is cleaned up automatically when you close the window.

### Step 3: Run Star Detection (If Needed)

If the FWHM, Roundness, Stars, and Weight columns are empty, a **yellow banner** appears at the top:

> ⚠️ No star detection data. Click to run star detection…

Click the banner. This runs Siril's `register svenesis_blink -2pass` command, which detects stars in every frame and computes FWHM, roundness, background level, and star count. It takes a few seconds to a few minutes depending on the number of frames. The progress bar tracks through the detection and the follow-up stretch/reference rebind.

**Note:** Median and Sigma are *always* available — they don't require star detection.

### Step 4: Inspect and Select

Now you can:

- **Play the animation** (Space) at 3–5 FPS to visually spot problems — changing pixels (satellites, clouds) jump out to the eye
- **Sort the Statistics Table** by FWHM (worst frames at top)
- **Use Batch Reject** to remove the worst 10% automatically
- **Mark individual frames** with G (good) or B (bad)

### Step 5: Apply and Close

Click **Apply Rejections && Close** (or press Esc — you'll be prompted whether to apply, discard, or cancel). The script:

1. Creates a `rejected/` subfolder inside your source folder (if any frames are rejected).
2. Moves each rejected FITS into `rejected/`.
3. Writes `rejected_frames.txt` next to your originals, listing the names of the files that actually landed in `rejected/`.

Original kept frames stay exactly where they were — nothing is rewritten, renamed, or modified. Re-run the script later on the same folder and the already-rejected files (now in `rejected/`) simply won't appear, because the scan only picks up the top level.

---

## 5. The User Interface

The window is divided into three main areas.

### Left Panel (Control Panel)

The left side (340 px wide) contains all controls, organized into collapsible sections:

- **Playback:** Play/Pause, frame navigation, speed slider, loop toggle, "Only included frames" playback filter
- **Display Mode:** Normal, Side by Side (vs. reference)
- **Frame Marking:** Keep (G) / Reject (B) buttons, Reset All Rejections, auto-advance, pending-changes label
- **Batch Selection:** Threshold filter + worst N% mode
- **Approval Expression:** Multi-criteria AND filter
- **Export CSV / Export GIF** at the bottom
- **Buy me a Coffee · Help · Apply Rejections && Close**

### Right Panel (Tabbed Area)

The main area has four tabs.

#### Viewer Tab

The frame display canvas. Shows the current frame with the chosen autostretch preset applied.

- **Scroll wheel** to zoom (0.1× to 20×) — zoom percentage updates live in the toolbar
- **Right-click drag** to pan
- **Z** (or **Fit-in-Window** button) to return to the fit-to-window view
- A toolbar below the canvas holds: live zoom readout, **Fit-in-Window**, **Copy (Ctrl+C)**, **Overlay** checkbox, **Stretch** preset dropdown, **Thumbs** (thumbnail size) slider, and a shortcut legend.

#### Statistics Table Tab

All frames listed in a sortable table with 10 columns:

- Frame #, Weight, FWHM, Roundness, BG Level, Stars, Median, Sigma, Date, Status
- **Click a column header** to sort (click again to reverse direction)
- **Click a row** to jump to that frame in the Viewer
- **Arrow keys** navigate rows
- **Ctrl+click** or **Shift+click** to multi-select rows
- **Right-click** selected rows → "Reject N selected frame(s)"
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

- Select **X** and **Y** axes from dropdown menus (FWHM, Roundness, Background, Stars, Weight)
- **Green dots** = included frames
- **Red ✕** = excluded frames
- **Yellow/gold star** = current frame (always on top)
- **Click any dot** to jump to that frame
- Axis-normalized click detection — both axes contribute equally to nearest-point selection, regardless of their numeric ranges
- Best combinations: **FWHM vs Roundness** (star quality), **FWHM vs Background** (clouds + seeing)

### Bottom Bar (Filmstrip)

A horizontal scrollable strip of frame thumbnails (always visible):

- **Green border** = included
- **Red border** = excluded
- **Blue border** = current frame
- Click any thumbnail to jump to that frame
- Thumbnails load lazily as you scroll (only the visible range is materialized)
- Adjust size with the **Thumbs** slider in the viewer toolbar (40–160 px)
- The thumbnail cache reuses the main frame cache's already-stretched display data — a frame that is already in the main cache no longer costs a second disk read when its thumbnail is built

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
w_round = roundness                              [higher = better]
w_bg    = 1 − (bg − min) / (max − min)          [lower BG = better]
w_stars = sqrt(stars) / sqrt(max_stars)          [more = better]
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

Shows **Included** (green) or **Excluded** (red). Status changes stay local until you close the window with **Apply Rejections && Close** (see §10).

---

## 7. Display Modes & Autostretch Presets

### Normal Mode (Default)

Single-frame autostretched view. Each frame is stretched using a Midtone Transfer Function (STF) that replicates Siril/PixInsight's autostretch algorithm, with a **globally linked** median/MAD — so brightness differences between frames stay visible. This is what makes cloudy frames or hazy frames jump out during playback.

Use **Normal mode at 3–5 FPS** for satellite/airplane/tracking hunting. Anything that *changes* between frames — a trail, a cloud patch moving through, a tracking jerk — is instantly obvious to the eye. There is no separate "Difference" mode in this version; playback in Normal mode delivers the same result without the overhead of per-frame subtraction.

### Side by Side (vs. reference) Mode

Current frame on the left, reference frame (the first frame of the sequence) on the right, with synchronized zoom and pan. Useful for direct A/B comparison — especially for star shape changes or local artifacts you want to verify against a known-good baseline.

### Autostretch Presets

The **Stretch** dropdown in the viewer toolbar controls how each frame is mapped to display brightness. Four presets are available:

| Preset | `shadows_clip` | `target_median` | Character |
|--------|----------------|-----------------|-----------|
| Conservative | −3.5 σ | 0.20 | Darker background, preserves dim detail |
| **Default** | −2.8 σ | 0.25 | PixInsight-style STF, balanced |
| Aggressive | −1.5 σ | 0.35 | Brighter, higher contrast |
| Linear | — | — | No stretch — raw data clipped to 0–255 |

Changing the preset invalidates the frame cache + thumbnail cache, re-renders the current frame, and rebuilds visible thumbnails. Your choice is remembered across sessions via QSettings.

**Tip:** Use Conservative for nebulae (preserves faint structure), Default for generic inspection, Aggressive to hunt subtle brightness anomalies (clouds, haze), and Linear if you want to see what the sensor actually recorded without stretch artifacts.

### Additional Display Features

- **Frame Info Overlay:** Shows frame number, FWHM, roundness, and weight in the top-left corner. Toggleable via the **Overlay** checkbox in the viewer toolbar; overlay state is burned into the output of **Copy to clipboard** and **Export GIF**.
- **A/B Toggle (T key):** Pin the current frame, then press T to flip between the pinned frame and whatever frame you navigate to.

---

## 8. Frame Selection Methods

### Method 1: Manual Marking (G / B Keys)

The simplest approach — scrub through your sequence and mark each frame:

1. Press **Space** to play, or use **←/→** to step frame by frame
2. Press **B** when you see a bad frame (exclude)
3. Press **G** to re-include a frame you previously excluded
4. With **Auto-advance after marking** enabled (default), the viewer jumps to the next frame after marking

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
3. Set the percentage (e.g., 10 %)
4. Click **"Reject Matching"**

For FWHM and Background, "worst" = highest value. For Roundness and Weight, "worst" = lowest value.

**Example:** Reject worst 10 % by Weight → removes the 9 lowest-quality frames from a 90-frame sequence.

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

**Best for:** Removing specific outliers you've spotted in the scatter plot or graph.

### Reset All Rejections

The **Reset All Rejections** button in the Frame Marking group clears every exclusion — both the baseline (what Siril had at startup) and any pending marks — and marks every frame as Included again. Useful when you want to start the selection over. This action cannot be undone through Ctrl+Z.

---

## 9. The Undo System

Every marking action can be undone with **Ctrl+Z**:

- **Single marks** (G/B on one frame) undo one at a time
- **Batch operations** (threshold reject, worst N%, approval expression, multi-select) undo the **entire batch** with a single Ctrl+Z — you don't have to press Ctrl+Z N times
- **Reset All Rejections** is *not* on the undo stack (it's a deliberate nuclear option)
- Undo stack depth: 500 operations

**Example:** You reject the worst 15 % (13 frames). You realize that was too aggressive. One Ctrl+Z restores all 13 frames.

Rapid Ctrl+Z hammering is debounced — the statistics graph, scatter plot, and filmstrip/slider repaint coalesce into a single refresh after ~150 ms, so the hotkey stays snappy even on long sequences.

---

## 10. Applying Rejections (File Moves)

The Blink Comparator is **folder-based**: rejections are applied as actual file moves in your filesystem, not as metadata flags in a `.seq` file. This keeps the workflow transparent and fully reversible.

### When Changes Are Applied

Marks stay local until you close the window. Closing via:

- **"Apply Rejections && Close"** button, or
- **Esc** / window-close with pending rejections → Yes/No/Cancel dialog asking whether to apply.

### What Happens When You Apply

A confirmation dialog shows the rejection count and the target folder path, then:

1. A `rejected/` subfolder is created inside your source folder (if it doesn't already exist).
2. Each rejected FITS file is **moved** (not copied) into `rejected/`. The file naming is preserved — no renaming.
3. A text file `rejected_frames.txt` is written next to your originals. It contains a header (sequence name, timestamp, count) and one filename per line, listing only the files that actually landed in `rejected/`.
4. The script reports moved vs. failed counts in the Siril log.

### Partial Failures

If some moves fail (OS file lock, permissions, disk full), the script:

- Commits only the frames whose moves succeeded (they drop from the pending list).
- Leaves the failed frames in the pending set — so the close-confirm dialog still mentions them on the next close attempt.
- Lists only the actually-moved files in `rejected_frames.txt`.

This means a partial failure never leaves your filesystem in a lying state — the audit file always matches what's physically in `rejected/`.

### Undoing a Rejection After Close

The workflow is reversible because it's just file moves. To restore a rejected frame, drag the file out of `rejected/` back into the source folder. Delete or ignore the `rejected_frames.txt` audit file as you prefer.

### Original Frames Are Never Modified

Kept frames stay exactly where they were. The script never rewrites headers, never re-saves, never touches the original bytes.

---

## 11. Export Options

### Export Statistics CSV (.csv)

Exports the full statistics table as a CSV file with columns:
`Frame, Weight, FWHM, Roundness, Background, Stars, Median, Sigma, Date, Included`

Useful for external analysis in spreadsheets, Python notebooks, or other tools.

### Export Animated GIF (.gif)

Creates an animated GIF of the blink animation:

- Only included frames (excluded frames are skipped)
- Scaled to 480 px maximum dimension
- Uses the current playback speed (FPS) and autostretch preset
- Respects the Overlay checkbox — frame-info badges are burned into the GIF if the overlay is visible
- Requires the Pillow library (`pip install Pillow`)

Great for sharing on forums, social media, or observation reports.

### Copy Frame to Clipboard (Ctrl+C)

Copies the current frame (as displayed, with stretch and overlay applied) to the system clipboard. In **Side by Side** mode the full composite view is grabbed, not just the left raw pixmap. Paste directly into a forum post, image editor, or presentation.

---

## 12. Use Cases & Workflows

### Use Case 1: Quick Session Review (5 minutes)

**Scenario:** You just finished an imaging session with 120 subframes and want a quick quality check before stacking.

**Workflow:**
1. Run the Blink Comparator → pick the folder with your FITS files
2. Run star detection if needed (click the yellow banner)
3. Go to the **Statistics Table** tab, sort by **FWHM descending** — the worst frames are now at the top
4. Click **"Reject worst 10 %"** by FWHM
5. Review the **Statistics Graph** — check for any remaining outliers
6. **Apply Rejections && Close** → stack in Siril (the `rejected/` subfolder is excluded from any subsequent `convert` / stacking step because it's one level below your lights folder)

**Time:** ~5 minutes for 120 frames.

### Use Case 2: Cloud-Affected Session

**Scenario:** Clouds rolled through during your session. Some frames are partially clouded.

**Workflow:**
1. Open the Blink Comparator and pick the folder
2. Go to the **Statistics Graph** tab, enable **Background** checkbox
3. Look for spikes — these are the cloudy frames
4. Use **Batch Reject**: Background > [threshold from the spike level]
5. Also check **Stars** — cloudy frames have fewer detected stars
6. Verify by playing at 3–5 FPS in Normal mode — cloud patches wobble visibly against the static starfield

### Use Case 3: Tracking Problem Diagnosis

**Scenario:** Some frames show elongated stars. You want to find and remove them, and understand when the problem occurred.

**Workflow:**
1. Open the Blink Comparator
2. Go to the **Statistics Graph**, enable **Roundness**
3. Look for dips — these are frames with tracking errors
4. Use **Approval Expression**: `Roundness > 0.75`
5. **Reject Non-Matching** removes all frames with elongated stars
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
5. Or use **"Reject worst 20 %"** by FWHM — this removes the end-of-session frames automatically
6. Consider: in future sessions, use an autofocuser or refocus every 30 minutes

### Use Case 5: Satellite Trail Hunting

**Scenario:** You're imaging near the celestial equator where satellite trails are frequent.

**Workflow:**
1. Open the Blink Comparator
2. Stay in **Normal** mode
3. Press **Space** to play at 3–5 FPS — satellite trails flash visibly from frame to frame because the stars are stationary while the trail pixel positions change
4. When you spot a trail, press **B** to exclude that frame
5. Continue playing to catch all trails
6. Optionally switch to the **Aggressive** autostretch preset to make faint trails pop more

### Use Case 6: Data-Driven Selection (PI SubframeSelector Replacement)

**Scenario:** You want a quantitative, PixInsight-style selection process based on multiple criteria.

**Workflow:**
1. Run star detection to populate all metrics
2. Go to **Statistics Table**, sort by **Weight** ascending (worst frames first)
3. Review the bottom 10–20 % — do they look visibly worse?
4. Set up an **Approval Expression**:
   ```
   FWHM < 4.0 AND Roundness > 0.75 AND Background < 0.012 AND Stars > 40
   ```
5. Preview shows N frames would be rejected
6. Click "Reject Non-Matching"
7. Verify in the **Scatter Plot** (FWHM vs Roundness) — the remaining cluster should be tight
8. **Export CSV** for your records
9. Apply Rejections && Close

### Use Case 7: Before vs. After Comparison

**Scenario:** You want to verify that your frame selection actually improved the remaining set.

**Workflow:**
1. After marking frames, note the **session summary** numbers (mean FWHM, included count) shown in the close dialog
2. Check the **"Only included frames"** checkbox in Playback and hit Space
3. Play — verify the animation looks smooth with no flashing or artifacts
4. Check the **Statistics Graph** — the red dots (excluded) should be at the spikes
5. The remaining blue line should be more consistent
6. **Export GIF** of the clean sequence for your imaging log

### Use Case 8: Second-Pass Reselection

**Scenario:** You ran the Blink Comparator once, applied rejections, and later want to reconsider some of the moves.

**Workflow:**
1. Open your source folder in Finder / Explorer and drag frames from `rejected/` back into the main folder.
2. Delete the old `rejected_frames.txt` (or leave it — the next run overwrites it).
3. Re-run the Blink Comparator on the same folder. It picks up only the top-level files (the ones in `rejected/` stay in `rejected/`).
4. Make fresh selections and **Apply Rejections && Close** — a new `rejected_frames.txt` is written, and newly-rejected frames are moved into `rejected/` alongside the ones you decided to leave there.

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

`1`–`9` are dispatched through `QMainWindow.keyPressEvent` (not `QShortcut`), so when a spinbox or line-edit has keyboard focus the digits are delivered to the widget as usual and the FPS preset is suppressed — multi-digit entry in threshold spinboxes works normally. `Ctrl+Z` / `Ctrl+C` fire everywhere.

### Frame Marking

| Key | Action |
|-----|--------|
| `G` | Mark as good (include) |
| `B` | Mark as bad (exclude) |
| `Ctrl+Z` | Undo last marking (single or batch) |

### Display

| Key | Action |
|-----|--------|
| `Z` | Fit-in-window (reset zoom) |
| `T` | Pin current frame / toggle A/B comparison |
| `Ctrl+C` | Copy current frame to clipboard |

### Other

| Key | Action |
|-----|--------|
| `Esc` | Close window (with apply/discard/cancel prompt if changes are pending) |

---

## 14. Tips & Best Practices

### General Workflow

1. **Start with data, then verify visually.** Sort by FWHM or Weight first to identify bad frames numerically. Then switch to the Viewer to confirm they actually look bad.

2. **Don't over-reject.** More frames = lower noise in the stack. Reject only frames that are clearly defective. A frame with FWHM 4.2 when your best is 3.0 is still contributing signal — consider keeping it unless it's an outlier.

3. **Use the running average.** In the Statistics Graph, the bold trend line reveals patterns (focus drift, clouds) that are invisible in the noisy raw data line.

4. **Check the Scatter Plot.** FWHM vs Roundness is the single most informative combination. The main cluster represents your "normal" frames. Outliers far from the cluster are your rejection candidates.

5. **Blink in Normal mode at 3–5 FPS for satellite hunting.** Changing pixels jump out to the eye — you don't need a dedicated "Difference" mode.

### Autostretch Presets

6. **Default is usually fine.** Conservative is good when the background has faint nebulosity you want to preserve while scanning for defects. Aggressive makes cloudy frames stand out. Linear is for when you want to see what the sensor actually recorded.

### Performance Tips

7. **First run on a folder is slow, subsequent runs are fast.** The script caches statistics and thumbnails. Navigating frames is instant once cached.

8. **Large sequences (500+ frames):** The statistics loading may take a minute. Be patient — it only happens once per session. Star detection scales roughly with frame count.

9. **Playback speed:** If playback stutters at high FPS, lower the speed. The frame cache preloads ahead with a playback-aware lookahead (`max(10, fps × 2)`), but very high FPS on very large frames can outrun the single preload thread.

### Folder Hygiene

10. **Keep your lights folder clean.** Delete old `rejected/` subfolders or `rejected_frames.txt` files you no longer need. The Blink Comparator only scans one directory level, but your stacking script may not be so careful.

11. **The temp sequence is ephemeral.** `svenesis_blink.fits` + `.seq` are always cleaned up on close. If a previous run crashed and left them behind, the next launch detects that and runs a `close` + cleanup before `convert`.

---

## 15. Troubleshooting

### Folder picker shows no FITS files

**Cause:** You pointed at a folder that contains no `.fit/.fits/.fts` files at the top level (the script does not recurse deeper, and compressed `.fz/.gz` FITS are not recognized).
**Fix:** Navigate into the actual lights folder. If your files live in `session/lights/night1/`, pick `night1/`, not `session/`. If your frames are fpack- or gzip-compressed, decompress them first (e.g. `funpack *.fz` or `gunzip *.gz`).

### "destination already exists" during sequence building

**Cause:** A previous run crashed without cleaning up the temp sequence.
**Fix:** The script now runs `close` + cleanup before `convert`, so simply re-running should work. If you see this manually, delete `svenesis_blink.fits` and `svenesis_blink.seq` from the folder and relaunch.

### FWHM / Roundness / Stars columns are empty

**Cause:** Star detection hasn't been run on this sequence.
**Fix:** Click the yellow "Run Star Detection" banner. This runs `register svenesis_blink -2pass` which computes all star metrics without creating new files.

### Star detection ran but columns are still empty

**Cause:** Registration wrote data to a channel the script didn't probe (rare — the script now probes all channels and reuses the result).
**Fix:** Update to the latest version of the script. It auto-detects the channel on frame 0 and reuses it for the whole sequence.

### Progress bar freezes during star detection

**Cause:** The post-register rebind (compute global stretch → load reference frame) used to run silently on the main thread. In v1.2.8 those phases advance the progress bar through 30 % → 50 % with `processEvents()` pumping.
**Fix:** Update to v1.2.8 or newer. If the bar still appears stuck on very large sequences, give it a minute — each phase can legitimately take several seconds per thousand frames.

### 1–9 digits change playback speed instead of going into a threshold spinbox

**Cause (pre-1.2.8):** The 1–9 FPS presets were registered as window-scope `QShortcut`s, which consumed digit keystrokes before they could reach a focused child widget.
**Fix:** Update to v1.2.8. The presets now live in `keyPressEvent` and only fire when no child widget absorbs the key.

### Font warning: "Sans-serif"

**Message:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"…`
**Impact:** Cosmetic only, no effect on functionality.

### GIF export fails

**Cause:** The Pillow library is not installed.
**Fix:** In a terminal: `pip install Pillow` (or install via Siril's Python environment).

### Playback is slow / stutters

**Cause:** Large image dimensions or insufficient memory for the frame cache.
**Fix:**
- Reduce playback speed (use 3–5 FPS instead of 30)
- The cache holds 80 frames by default — sufficient for most sequences
- Close other memory-intensive applications

### Script crashes with "'BlinkComparatorWindow' object has no attribute 'cache'"

**Cause:** A signal-ordering bug in earlier 1.2.x builds where the display-mode radios emitted `idToggled` before the cache was constructed.
**Fix:** Fixed in v1.2.8. Update to the current release.

---

## 16. FAQ

**Q: Does this replace PixInsight's Blink + SubframeSelector?**
A: For visual inspection and data-driven frame selection, yes — you get a sortable statistics table, batch thresholds, approval expressions, scatter plot, statistics graph with running average, and a thumbnail filmstrip. What you trade is PI's SNR / PSFSignalWeight proprietary metrics, and there's no dedicated "Difference" mode (Normal-mode playback at 3–5 FPS covers the same ground).

**Q: Do I need to pre-register my sequence?**
A: No — the script builds its own temporary FITSEQ sequence via `convert -fitseq` from whatever you point it at. If you want FWHM/Roundness/Stars metrics you click the "Run Star Detection" banner, which runs `register -2pass` in place.

**Q: Where are my rejected frames?**
A: On close, they are physically moved into a `rejected/` subfolder next to your source files. A plain-text `rejected_frames.txt` audit file is also written alongside the originals. To un-reject, drag the file out of `rejected/` back into the source folder.

**Q: Does "Apply Rejections" modify my FITS files?**
A: No. Kept frames are not touched at all. Rejected frames are *moved* (not rewritten, not renamed) into a `rejected/` subfolder — reversible at any time.

**Q: How much does rejecting frames improve the stack?**
A: It depends on your data. Removing 5–10 % of the worst frames often improves the stack noticeably — sharper stars, lower noise in the background. Removing more than 20–30 % usually means diminishing returns (you're losing more signal than you're gaining in quality).

**Q: What happened to the Difference display mode?**
A: Removed in v1.2.5. In practice, playing the sequence at 3–5 FPS in Normal mode with globally-linked autostretch catches the same artifacts (satellites, clouds, tracking jumps) because the eye latches onto whatever is changing. The Difference mode's per-frame subtract + absolute + scale + clip path was paying for work that playback already does visually.

**Q: What happened to the Linked / Independent stretch toggle?**
A: Removed in v1.2.5. Globally-linked autostretch is now the only mode — it's the sensible default for a blink comparator because it preserves the brightness differences that make cloudy frames visible. If you want different stretch flavors, use the autostretch preset dropdown (Conservative / Default / Aggressive / Linear).

**Q: Can I re-include frames I've excluded?**
A: Yes. Press **G** on an excluded frame to re-include it. Or use **Ctrl+Z** to undo the last marking operation (single or batch). After close, just drag the file out of `rejected/` in your file manager.

**Q: Why is the Weight column showing 0 for all frames?**
A: Weight requires FWHM, Roundness, Background, and Stars data. If star detection hasn't been run, all inputs are 0, so the weight is 0. Run star detection first.

**Q: Can I use this for planetary imaging?**
A: The tool is designed for deep-sky subframe selection. Planetary imaging (lucky imaging) uses different quality metrics and typically processes thousands of very short exposures. Tools like AutoStakkert or Planetary System Stacker are better suited for planetary work.

---

## 17. Changes Since v1.2.3

The last officially published release was **v1.2.3**. Everything below summarizes what changed between that baseline and the current **v1.2.8** — short bullets only; the script's `CHANGELOG` block has the one-liners per release.

- **v1.2.4 — Folder-only workflow.** The script now always prompts for a folder of FITS files and builds its own temporary `svenesis_blink` sequence. Rejected frames move to a `rejected/` subfolder with a `rejected_frames.txt` audit file. Added an autostretch preset dropdown (Conservative / Default / Aggressive / Linear). Removed: ROI feature, per-frame histogram widget, and the "use currently loaded sequence" path.
- **v1.2.5 — Simplified display modes.** Removed the Difference display mode and the `D` shortcut — playing at 3–5 FPS in Normal mode catches the same artifacts. Removed the Linked-stretch toggle; globally-linked autostretch is now the only mode.
- **v1.2.6 — Performance pass.** Thumbnails reuse the main frame cache's already-stretched image, `mtf()` runs in-place, RGB autostretch is a single pass, and preload pacing follows FPS.
- **v1.2.7 — Marking responsiveness.** Rapid G/B marking coalesces slider / scatter / graph refreshes through a single 150 ms timer; filmstrip and table skip no-op styling work. Also: `mtf()` kwarg crash fix and stale-temp-sequence recovery on restart.
- **v1.2.8 — Cross-platform polish & stability.** UTF-8 for `rejected_frames.txt` and CSV export (fixes Windows non-ASCII paths). 1–9 FPS presets moved to `keyPressEvent` so focused spinboxes accept digits natively. Folder paths with spaces are now quoted in Siril commands. Apply moves files first, then writes an audit list of only what actually moved. Star detection rebinds caches/stats and advances the progress bar through post-register phases. View-state (filter, display mode, graph metrics, scatter axes) persists across sessions.

Upgrading from **v1.2.3** in practice: point the script at your FITS folder (instead of loading a sequence in Siril first), and expect the rejection flow to produce a `rejected/` subfolder and `rejected_frames.txt` rather than toggling Siril's in-sequence inclusion flags.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
