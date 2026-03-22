# Svenesis Gradient Analyzer — User Instructions

**Version 1.8.4** | Siril Python Script for Background Gradient Analysis & Diagnostics

> *A comprehensive gradient diagnostic tool — analyzes, visualizes, and recommends fixes for background gradients, vignetting, and hardware artifacts in astrophotography images.*

---

## Table of Contents

1. [What Is the Gradient Analyzer?](#1-what-is-the-gradient-analyzer)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Understanding the Metrics](#6-understanding-the-metrics)
7. [Visualization Tabs](#7-visualization-tabs)
8. [Grid Settings & Presets](#8-grid-settings--presets)
9. [Options & Checkboxes](#9-options--checkboxes)
10. [Results & Recommendations](#10-results--recommendations)
11. [Warnings & Detections](#11-warnings--detections)
12. [Export Options](#12-export-options)
13. [Use Cases & Workflows](#13-use-cases--workflows)
14. [Keyboard Shortcuts](#14-keyboard-shortcuts)
15. [Tips & Best Practices](#15-tips--best-practices)
16. [Troubleshooting](#16-troubleshooting)
17. [FAQ](#17-faq)

---

## 1. What Is the Gradient Analyzer?

The **Svenesis Gradient Analyzer** is a Siril Python script that analyzes the background of your astrophotography image to detect gradients, vignetting, and hardware artifacts. It tells you *what's wrong*, *how bad it is*, and *exactly what to do about it*.

Think of it as a **diagnostic doctor** for your image background. It combines:

- **Visual analysis** — heatmaps, 3D surfaces, profile plots, and 9 specialized visualization tabs
- **Quantitative metrics** — gradient strength, direction, complexity, uniformity, and 30+ diagnostic measurements
- **Smart recommendations** — specific Siril commands and tool suggestions tailored to your image's problems
- **Before/After tracking** — run it twice to see exactly how much your gradient extraction improved

The result: you understand exactly what gradients and artifacts are in your image, and you know the best strategy to remove them before stacking or stretching.

---

## 2. Background for Beginners

### What Is a Background Gradient?

In a perfect astrophoto, the sky background would be perfectly uniform — the same brightness everywhere. In reality, the background is almost never uniform. It varies across the image due to several causes:

| Cause | What Happens | Pattern |
|-------|-------------|---------|
| **Light pollution (LP)** | Artificial light brightens one side of the sky more than the other | Directional gradient — one side brighter |
| **Vignetting** | Your optics darken the image corners compared to the center | Radial pattern — dark corners, bright center |
| **Moon** | Moonlight adds a glow from one direction | Similar to LP — directional brightening |
| **Twilight / dawn** | Sky brightens from the horizon as sunrise approaches | Strong gradient from one edge |
| **Airglow** | Natural atmospheric glow varies across the sky | Broad, gentle gradient |
| **Sensor artifacts** | Amplifier glow, banding, dark current | Corner glow, horizontal/vertical stripes |
| **Poor flat calibration** | Flat frame doesn't fully correct the optical vignetting | Residual radial pattern |

These gradients **hurt your final image**. When you stretch the image to reveal faint detail, gradients get amplified, creating ugly brightness variations, color shifts, and banding. Removing gradients before stretching is one of the most important processing steps.

### What Is Vignetting?

**Vignetting** is the darkening of image corners caused by your optical system. All telescopes and camera lenses vignette to some degree — light at the edge of the field has to travel through more glass and hits the sensor at a steeper angle.

- **Natural vignetting** follows a mathematical "cos⁴" law — it's proportional to the fourth power of the angle from center
- **Mechanical vignetting** happens when parts of your imaging train (adapters, filter wheels, reducers) physically block light at the edges
- **Flat frames** are designed to correct vignetting. If your flats are good, vignetting should be mostly gone before you reach the Gradient Analyzer

The Gradient Analyzer distinguishes between vignetting (radial, centered) and light pollution (directional, one-sided), because they need different tools to fix.

### What Is Sigma-Clipping?

When measuring the background brightness of a tile (a small region of your image), you want to measure only the *sky* — not the stars, nebulae, or cosmic rays in that region.

**Sigma-clipping** is a statistical technique that iteratively removes outlier pixels:

1. Compute the median and standard deviation of all pixels in the tile
2. Remove any pixel that deviates by more than σ (sigma) standard deviations from the median
3. Recompute median and standard deviation from the remaining pixels
4. Repeat 2–3 times

After clipping, the remaining pixels represent the pure sky background — stars and bright objects have been excluded from the measurement.

- **Lower sigma (2.0–2.5):** More aggressive clipping — removes more pixels, better at excluding stars, but may clip the sky itself in dense fields
- **Higher sigma (3.0–3.5):** Gentler clipping — keeps more pixels, more robust in dense star fields, but may include faint star halos

### What Is a Polynomial Fit?

To remove a gradient, software fits a mathematical surface to your background and subtracts it. The complexity of this surface is controlled by the **polynomial degree**:

| Degree | Surface Shape | Best For |
|--------|--------------|----------|
| **1 (Linear)** | A flat, tilted plane | Simple one-directional gradients (LP from one side) |
| **2 (Quadratic)** | A curved bowl or saddle | Vignetting + LP combined, gentle curves |
| **3 (Cubic)** | An S-shaped or complex curve | Complex gradients with multiple sources |

The Gradient Analyzer estimates which degree your image needs and recommends specific `subsky` parameters.

### What Tools Remove Gradients?

Several tools exist for removing background gradients in astrophotography:

| Tool | Type | Best For |
|------|------|----------|
| **AutoBGE** | Siril built-in | Quick, automatic extraction — good for mild gradients |
| **subsky** | Siril command | Configurable polynomial extraction — you choose the degree and sample count |
| **GraXpert** | External (AI-based) | Complex, multi-source gradients — uses AI to model arbitrary backgrounds |
| **VeraLux Nox** | Siril script | Chromatic light pollution — different gradient per color channel |

The Gradient Analyzer recommends the right tool based on your gradient's complexity.

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
| **scipy** | Any recent | Auto-installed by the script |
| **astropy** | Any | *Optional* — used for FITS header parsing (calibration check, WCS) |

### Installation

1. Download `Svenesis-GradientAnalyzer.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script automatically installs missing Python dependencies (`numpy`, `PyQt6`, `matplotlib`, `scipy`) on first run.

---

## 4. Getting Started

### Step 1: Load an Image

Load any FITS image in Siril. The Gradient Analyzer works on:
- **Single stacked images** (the most common use case — analyze before stretching)
- **Individual subframes** (to check gradients per frame)
- **RGB or mono** images

**Important:** For best results, analyze your image **before stretching**. The script detects stretched (non-linear) images and warns you, because gradient measurements on stretched data are less accurate.

### Step 2: Run the Script

Go to **Processing → Scripts → Svenesis Gradient Analyzer**.

The script opens its window. The left panel shows all settings; the right panel is ready for visualizations.

### Step 3: Click "Analyze" (or press F5)

The script will:
1. Load the current image from Siril
2. Divide it into a grid of tiles (default: 16×16)
3. Sigma-clip each tile to exclude stars
4. Compute background medians for every tile
5. Run 30+ diagnostic analyses
6. Render all 9 visualization tabs
7. Display results with metrics, warnings, and recommendations

A progress bar shows each step. The whole analysis typically takes 5–30 seconds depending on image size and grid resolution.

### Step 4: Read the Results

After analysis, three things tell you what to do:

1. **The Gradient Strength Gauge** — a visual meter showing how severe the gradient is (green = fine, red = needs fixing)
2. **The "Analysis Results" button** — opens a detailed report with a beginner-friendly action plan
3. **The "Recommendations" button** — shows specific tool suggestions and Siril commands

### Step 5: Fix and Re-Analyze

1. Apply the recommended gradient extraction (e.g., run `subsky 2 16` in Siril's console)
2. Press **F5** to re-analyze the same image
3. The script shows a **before/after comparison** — the gauge, metrics, and delta values tell you exactly how much improved

---

## 5. The User Interface

### Left Panel (Control Panel)

The left side (340px wide) contains all controls in a scrollable panel:

#### Title
"Svenesis Gradient Analyzer 1.8.4" at the top.

#### Grid Settings Group
- **Columns / Rows:** SpinBox + Slider (4–64 each). Controls how many tiles the image is divided into. Default: 16×16.
- **Sigma-Clip:** SpinBox (1.5–4.0, step 0.1). Controls how aggressively stars are excluded. Default: 2.5.
- **Sigma hint:** Dynamic yellow text showing recommended sigma adjustments based on your data.
- **Preset dropdown:** Quick presets for different image types — Broadband (default), Narrowband (strict), Fast optics (tolerant).

#### Options Group
Eight checkboxes controlling analysis behavior and output:
- Smoothing (bilinear interpolation)
- 3D view
- Analyze channels separately (RGB)
- Show sample point guidance
- Show image under heatmap
- Save heatmap as PNG
- Save analysis JSON
- Colorblind-friendly colormap

#### Actions Group
- **Analyze** button (green, large) — the main action. Also triggered by **F5**.
- **Progress bar** — shows during analysis.

#### Gradient Strength Gauge
A visual meter widget showing the gradient strength percentage with color-coded zones:
- **Green (0–1.5%):** Very uniform — no extraction needed
- **Yellow (1.5–4%):** Slight gradient — gentle extraction recommended
- **Orange (4–12%):** Significant gradient — extraction strongly recommended
- **Red (>12%):** Strong gradient — aggressive extraction required

#### Quadrant Widget
A 2×2 grid showing NW, NE, SW, SE median background values. The brightest quadrant gets a red border (light pollution direction); the darkest gets a green border. Hovering shows a tooltip explaining what the quadrant values mean.

#### Bottom Buttons
- **Buy me a Coffee** — support link
- **Help** — comprehensive 6-tab help dialog
- **Close** — exits the script

### Right Panel (Visualizations)

#### Image Info Bar
Shows image dimensions, channel count, and status (e.g., "Image: 4656 × 3520 px, 3 channel(s)").

#### Tab Widget (9 Tabs)
The heart of the tool — 9 specialized visualization tabs (see Section 7 for details).

#### Tab Info Label
Below the tabs, a context-sensitive description updates as you switch tabs, explaining what you're looking at in plain language.

#### Bottom Buttons
- **Analysis Results** — opens a modal with Summary, Metrics, and Before/After tabs
- **Recommendations** — opens a modal with Quick Guide and Full Details tabs
- **Export Report** — saves a consolidated text report and copies it to the clipboard

---

## 6. Understanding the Metrics

### Gradient Strength (%)

The primary metric. Measures how much the background varies across the image.

| Aspect | Details |
|--------|---------|
| **What** | (P95 − P5) ÷ median × 100, where P95/P5 are the 95th and 5th percentile of tile medians |
| **Why P95-P5?** | More robust than max-min — ignores outlier tiles caused by artifacts |
| **Good values** | Below 1.5% (broadband) |
| **Bad values** | Above 12% — strong gradient that will ruin stretching |

**Interpretation by preset:**

| Preset | Uniform | Slight | Significant | Strong |
|--------|---------|--------|-------------|--------|
| Broadband | < 1.5% | 1.5–4% | 4–12% | > 12% |
| Narrowband | < 0.8% | 0.8–2.5% | 2.5–6% | > 6% |
| Fast optics | < 3% | 3–6% | 6–16% | > 16% |

### Gradient Direction (°)

The compass angle from the darkest region to the brightest, measured in degrees (0° = North, 90° = East). Indicates where light pollution or the moon is coming from.

If the image is plate-solved (WCS in FITS header), the script converts this to a real-world **geographic compass bearing** — so you can check if it matches where your city lights are.

### Uniformity (%)

Standard deviation ÷ median × 100. A more sensitive measure of overall background variation. Lower is better.

### Vignetting vs. Light Pollution

The script fits two models to your gradient pattern:

| Model | What It Detects | R² Meaning |
|-------|----------------|------------|
| **Radial (vignetting)** | Symmetric corner darkening centered on the image | Higher R² = vignetting dominates |
| **Linear (LP)** | Directional brightness change across the image | Higher R² = light pollution dominates |

When radial R² is much higher → the gradient is vignetting. When linear R² is much higher → it's light pollution. When both are similar → it's a mix.

### Edge/Center Ratio

Compares average edge brightness to center brightness. Values below 0.85 suggest significant vignetting (edges are much darker than center). Values near 1.0 mean no vignetting.

### Gradient Complexity (Polynomial Degree)

The script fits polynomial surfaces of degree 1, 2, and 3, and tells you which one best matches your gradient:

| Degree | Meaning | Typical Cause |
|--------|---------|---------------|
| **1 (Linear)** | Simple tilt | LP from one direction |
| **2 (Quadratic)** | Curved, bowl-shaped | Vignetting + LP combined |
| **3 (Cubic)** | Complex S-curve | Multiple LP sources, optical effects |

If none of the polynomials fit well (all R² < 0.5), the script recommends **GraXpert** (AI-based extraction) because the gradient is too complex for traditional polynomial fitting.

### Confidence

An SNR-based score measuring how reliable the gradient measurement is:

| Level | Score | Meaning |
|-------|-------|---------|
| **Low** | < 30% | The gradient signal is barely above tile noise — results are uncertain |
| **Medium** | 30–70% | Moderate confidence — gradient is real but measurement has some uncertainty |
| **High** | > 70% | Strong confidence — the gradient is well-measured and clearly present |

### Quadrant Analysis

Divides the image into four quadrants (NW, NE, SW, SE) and reports the median background of each. The **brightest quadrant** indicates the direction of light pollution; the **darkest quadrant** is the cleanest part of the sky.

---

## 7. Visualization Tabs

### Tab 1: Heatmap / 3D

The primary visualization. A color-coded map of background brightness across the image.

- **Green/blue tiles** = darker background (good)
- **Yellow/red tiles** = brighter background (gradient or LP)
- **Cyan arrow** = gradient direction (from darkest to brightest)
- **Green circles** = suggested sample points for `subsky` (darkest, most uniform areas)
- **Red ✕** = areas to avoid when placing samples (bright, gradient-affected)

When **3D view** is enabled, a rotatable 3D surface plot appears alongside the heatmap. The "elevation" represents background brightness — peaks are the brightest regions, valleys are the darkest.

### Tab 2: Profiles

Two line plots showing cross-sections of the background:

- **Horizontal profile (left → right):** The median background of each column of tiles. Reveals left-right gradients.
- **Vertical profile (bottom → top):** The median background of each row of tiles. Reveals top-bottom gradients.

Dashed lines show the overall minimum and maximum. A perfectly flat line means no gradient in that direction.

### Tab 3: Tile Distribution

A histogram of all tile median values. Shows how the background values are distributed.

- **Narrow, single-peaked histogram** = uniform background (good)
- **Wide or multi-peaked histogram** = gradient or artifacts present
- **Orange dashed line** = median of all tiles
- **Blue dotted line** = mean of all tiles

### Tab 4: RGB Channels

Three side-by-side heatmaps showing the gradient separately for each R, G, B channel. Only available when "Analyze channels separately" is enabled.

This reveals **chromatic light pollution** — when the gradient is stronger in one color channel. Typical patterns:
- **Red dominant:** Sodium vapor lamps (older street lights)
- **Blue dominant:** LED or mercury vapor lights
- **Equal across channels:** Broadband LP, moonlight, or vignetting

### Tab 5: Background Model

Shows the polynomial surface fitted to your gradient:

- **Left:** The fitted model — what the gradient extraction tool would subtract
- **Right:** Residuals (original − model) — what would remain after subtraction

In the residuals, **random coloring** means a good fit (the model captured the gradient). **Visible patterns** mean the polynomial degree is too low or the gradient is too complex.

### Tab 6: Gradient Magnitude

A map showing the **rate of change** of the background — where the gradient is steepest.

- **Cool colors (blue/black)** = flat regions (no gradient)
- **Hot colors (yellow/red)** = steep transitions (strong gradient or edge)

Sharp lines in this map may indicate **mosaic panel boundaries** (stitched images) or **stacking edges** (from dithering).

### Tab 7: Subtraction Preview

Side-by-side comparison:

- **Left:** Your original image (auto-stretched luminance)
- **Right:** The image after subtracting the fitted polynomial model (auto-stretched)

This is a preview of what gradient extraction would do. The right side should show a more uniform background.

### Tab 8: FWHM / Eccentricity

Star shape variation across the field:

- **Left (FWHM map):** How "fat" the stars are in each tile. Uniform FWHM = good optics/focus. Increasing FWHM toward edges = focus curvature or tilt.
- **Right (Eccentricity map):** How elongated stars are in each tile. Low eccentricity everywhere = good tracking and optics. High eccentricity in corners = optical tilt or coma.

Empty tiles (NaN) mean too few stars were found in that region (e.g., nebula-dominated areas).

### Tab 9: Residuals / Mask

Shows the quality of the polynomial fit:

- **Left:** Residuals from the background model (blue = model too high, red = model too low)
- **Right:** Same residuals with a **red overlay** highlighting which tiles were excluded from the fit

Excluded tiles are those flagged as: extended objects (nebulae/galaxies), hotspots, stacking edges, or extremely star-dense regions. Excluding these ensures the polynomial fit tracks the true sky background.

---

## 8. Grid Settings & Presets

### Grid Resolution (Columns × Rows)

Controls how many tiles the image is divided into. Default: 16×16 (256 tiles).

| Resolution | Tiles | Best For |
|-----------|-------|----------|
| **8×8** | 64 | Quick overview, very large images |
| **16×16** | 256 | Good default for most images |
| **24×24** | 576 | Detailed analysis, detecting localized features |
| **32×32** | 1024 | High-resolution gradient mapping |
| **48×48+** | 2304+ | Expert use — very slow, very detailed |

**Warning:** The script will alert you if your grid is too fine for the image size. Each tile needs at least 50 pixels on each side for reliable sigma-clipping. If you set 64×64 on a 2000-pixel-wide image, each tile would only be 31 pixels wide — too small.

### Sigma-Clip Value

Controls how aggressively stars are removed from background measurements. Default: 2.5.

| Value | Behavior | Best For |
|-------|----------|----------|
| **1.5–2.0** | Very aggressive — clips even faint star halos | Sparse star fields with few bright stars |
| **2.5** | Balanced default — works well for most images | General use |
| **3.0–3.5** | Gentle — keeps more pixels | Dense star fields (Milky Way, globular clusters) |
| **4.0** | Very gentle — minimal clipping | Very dense fields or when 2.5 clips too much |

The script provides an **adaptive sigma suggestion** in yellow text below the setting, based on the star density (rejection rate) in your image.

### Threshold Presets

The dropdown selects threshold calibrations for different image types:

| Preset | Thresholds | Why |
|--------|-----------|-----|
| **Broadband (default)** | 1.5% / 4% / 12% | Standard for broadband RGB imaging. Typical gradients from LP and vignetting. |
| **Narrowband (strict)** | 0.8% / 2.5% / 6% | Narrowband filters already reject most LP, so any remaining gradient is more concerning. Stricter thresholds. |
| **Fast optics (tolerant)** | 3% / 6% / 16% | Fast optics (f/2–f/4) inherently vignette more. Looser thresholds avoid false alarms from natural cos⁴ falloff. |

---

## 9. Options & Checkboxes

### Smoothing (Default: ON)

Applies bilinear interpolation to the heatmap for a smooth, continuous visualization instead of blocky tiles. Purely cosmetic — does not affect the metrics. Disable for a raw, tile-accurate view.

### 3D View (Default: ON)

Adds a rotatable 3D surface plot next to the heatmap. Shows the gradient as a "landscape" you can drag to rotate. Disable to save screen space or speed up rendering.

### Analyze Channels Separately (Default: OFF)

When enabled, runs the full analysis independently on each R, G, B channel and populates the RGB Channels tab. Reveals chromatic light pollution and per-channel gradient differences.

Auto-disabled for mono images.

**When to enable:** If you suspect your light pollution has a color cast, or if you're using VeraLux Nox and need per-channel gradient data.

### Show Sample Point Guidance (Default: ON)

Overlays green circles (good sample locations) and red crosses (locations to avoid) on the heatmap. The sample points are placed in the darkest, most uniform regions — exactly where you'd want to place subsky sample points.

### Show Image Under Heatmap (Default: OFF)

Displays your actual image (auto-stretched) underneath the heatmap as a semi-transparent overlay. Helps correlate gradient features with the actual image content (e.g., "that bright patch is actually a nebula, not a gradient").

### Save Heatmap as PNG (Default: OFF)

When enabled, automatically saves the heatmap visualization as a PNG file in Siril's working directory after each analysis. Useful for documentation or forum posts.

Can save an **annotated** version with key metrics burned into the bottom of the image.

### Save Analysis JSON (Default: OFF)

When enabled, saves all metrics and tile medians as a JSON sidecar file (`gradient_analysis.json`). Used for:
- **Cross-session comparison:** If a previous JSON exists, the script computes deltas (how much the gradient changed since last analysis)
- **Documentation:** Machine-readable record of your gradient diagnostics

### Colorblind-Friendly Colormap (Default: OFF)

Switches from the default red-green colormap to **cividis**, which is perceptually uniform and accessible to people with color vision deficiencies.

---

## 10. Results & Recommendations

### Analysis Results (Button)

Opens a modal dialog with three tabs:

#### Summary Tab
A beginner-friendly **action plan** in plain language:
- What the gradient strength means
- Whether calibration issues were detected (missing flats, amp glow, banding)
- Whether the data is linear or stretched
- Specific steps to take, in priority order
- Concrete Siril commands (e.g., `subsky 2 16`)

#### Metrics Tab
Detailed numbers for advanced users:
- Gradient strength, direction, range, uniformity
- Vignetting vs. LP analysis (R² values)
- Polynomial complexity (degree, R² per degree)
- Edge/center ratio
- Confidence score and SNR
- Star density statistics
- Gradient-free coverage percentage
- Extended object count
- Hotspot count
- All warnings and detections

#### Before/After Tab
If you've run the analysis more than once on the same image (e.g., before and after gradient extraction), this tab shows:
- Previous vs. current gradient strength
- Delta with arrow (↓ = improved, ↑ = worsened)
- Percentage improvement

### Recommendations (Button)

Opens a modal with two tabs:

#### Quick Guide Tab
A concise summary:
- Critical warnings (if any)
- Recommended tool with brief explanation
- Specific command to run
- Workflow priority (fix hardware/calibration issues first, then extract)

#### Full Details Tab
Comprehensive recommendations:
- Tool comparison for your specific situation (AutoBGE vs. subsky vs. GraXpert vs. VeraLux Nox)
- Why each tool is or isn't suitable
- Step-by-step workflow with ordered priorities
- Re-analysis reminder

---

## 11. Warnings & Detections

The Gradient Analyzer detects many issues beyond simple gradients. Each warning appears in the results with an explanation and fix.

### Dew / Frost Detected

**What it means:** The script found a combination of radial FWHM increase (stars getting fatter from center to edge) and a bright-center brightness pattern. This indicates moisture forming on your optics during the imaging session.

**How to fix:** Check your dew heater. Discard affected frames. Consider a dew shield or more aggressive heating.

### Amplifier Glow Detected

**What it means:** A corner of the sensor shows exponentially increasing brightness — the "amp glow" from the camera's readout electronics, which generates heat that the sensor picks up.

**How to fix:** Apply proper dark frames. Dark frames captured at the same temperature and exposure time will contain the same amp glow pattern and subtract it.

### Sensor Banding Detected

**What it means:** The FFT analysis of residual row/column profiles found periodic patterns — horizontal or vertical stripes from the sensor readout electronics.

**How to fix:** Apply bias and dark frames. If banding persists, try re-stacking with different rejection methods. Some cameras are known for banding (certain CMOS sensors).

### Missing Flat Frame Warning

**What it means:** The FITS header doesn't indicate that a flat frame was applied (no `FLATCOR` or `CALSTAT` keyword). Significant vignetting is likely.

**How to fix:** Apply a master flat frame. In Siril: **Image Processing → Calibration** or use the `calibrate -flat=master_flat.fit` command.

### Non-Linear (Stretched) Data

**What it means:** The image appears to have been stretched (histogram transformation applied). Gradient measurements on stretched data are amplified and less accurate.

**How to fix:** Analyze the original, unstretched (linear) image instead. If you've already stretched, the analysis is still useful but the percentage values may be inflated.

### Background Normalization Detected

**What it means:** The per-channel backgrounds are suspiciously similar, suggesting the data was background-normalized during stacking. This can mask real gradients.

**How to fix:** If possible, re-stack without background normalization, analyze, extract gradients, then re-stack normally.

### Dense Star Field Warning

**What it means:** Many tiles have very high sigma-clip rejection rates (>40%), meaning the field is so packed with stars that the background measurement may be compromised.

**How to fix:** Increase the sigma-clip value (e.g., from 2.5 to 3.0 or 3.5) to be less aggressive, or reduce the grid resolution for larger tiles.

### Stacking Edges Detected

**What it means:** Edge tiles are significantly darker than interior tiles — a telltale sign of dithered or rotated stacking, where edge regions have fewer contributing frames.

**How to fix:** Crop the borders. In Siril, use the selection tool to define a crop region, or add a crop step to your processing.

### Hotspots Detected

**What it means:** Individual tiles deviate by more than 3σ from their neighbors — likely artifacts such as satellite trails, cosmic rays, or sensor defects.

**How to fix:** Inspect the specific locations. These tiles are automatically excluded from the polynomial background fit to prevent them from biasing the model.

### Vignetting Asymmetry

**What it means:** The vignetting pattern is not symmetric (e.g., the left side is darker than the right). This suggests the flat frames don't perfectly match the imaging optics, or there's a tilted sensor.

**How to fix:** Check your flat frame quality. Ensure flats are taken with the same optical train configuration. Consider checking your sensor tilt.

### Extended Object Warning

**What it means:** Some tiles contain bright objects (nebulae, galaxies) with low star rejection — these are real objects, not gradients. They are excluded from the polynomial fit automatically.

**No fix needed** — this is informational. Your target object is being correctly identified and excluded from the background model.

---

## 12. Export Options

### Heatmap PNG Export

When "Save heatmap as PNG" is enabled, the heatmap is saved to Siril's working directory after each analysis. Two variants:
- **Plain:** Just the matplotlib figure
- **Annotated:** Key metrics burned into the bottom of the image as text (gradient %, direction, assessment, version)

### JSON Sidecar

When "Save analysis JSON" is enabled, a file called `gradient_analysis.json` is saved with:
- Timestamp and script version
- Image dimensions and grid settings
- All gradient metrics (strength, angle, range, uniformity)
- Complexity analysis (degree, R² values)
- Vignetting analysis (radial/linear R², diagnosis)
- Data quality flags (linear data, star density, normalization)
- Tile medians array (for cross-session comparison)
- Extended object, hotspot, panel boundary detections
- Improvement prediction

If a previous JSON exists when you run the analysis, the script automatically computes **deltas** — showing how each metric changed since the last run.

### Consolidated Text Report

Click **"Export Report"** to generate a comprehensive plain-text report containing:
- Header (version, timestamp, image info)
- Summary and action plan
- Detailed metrics
- Before/after comparison (if applicable)
- Tool recommendations
- Full workflow guidance

The report is:
- Saved as `gradient_report_{timestamp}.txt` in Siril's working directory
- Automatically copied to your clipboard (paste into forums, emails, or documentation)

---

## 13. Use Cases & Workflows

### Use Case 1: Quick Pre-Stretch Check (2 minutes)

**Scenario:** You've just stacked your subframes and want to know if you need gradient extraction before stretching.

**Workflow:**
1. Load the stacked image in Siril
2. Run Gradient Analyzer
3. Press **F5** to analyze
4. Check the **gauge** — green means you can skip extraction; yellow/orange/red means you need it
5. Click **Recommendations** for specific tool suggestions

**Time:** ~2 minutes including analysis time.

### Use Case 2: Guided Gradient Extraction (5 minutes)

**Scenario:** The gauge shows "Significant gradient." You want step-by-step guidance.

**Workflow:**
1. Analyze the image (F5)
2. Click **Analysis Results** → read the Summary / Action Plan
3. Note the recommended polynomial degree (e.g., degree 2)
4. Open Siril's console (**Windows → Console**)
5. Type the suggested command, e.g.: `subsky 2 16`
6. Press **F5** again to re-analyze
7. Check the **Before/After** tab — strength should have dropped dramatically
8. If the gauge is now green, you're done. If still yellow, try a higher degree or GraXpert.

### Use Case 3: Diagnosing Why Your Gradient Won't Go Away

**Scenario:** You've run background extraction but the gradient is still there.

**Workflow:**
1. Analyze the image after extraction (F5)
2. Check the **Background Model** tab — do the residuals show patterns? If yes, the polynomial degree was too low.
3. Check the **Residuals / Mask** tab — are important tiles being excluded? The mask shows what was ignored during fitting.
4. Check **Warnings** — is there banding, amp glow, or stacking edges? These aren't true gradients and won't be removed by polynomial extraction.
5. Click **Recommendations** — if the gradient is too complex for polynomials, the script will suggest GraXpert.

### Use Case 4: Light Pollution Color Analysis

**Scenario:** You image from a light-polluted site and want to understand the LP characteristics for per-channel correction.

**Workflow:**
1. Load the stacked (linear) image
2. Enable **"Analyze channels separately (RGB)"**
3. Press F5
4. Check the **RGB Channels** tab — see which channel has the strongest gradient
5. Read the **LP color characterization** in the results — the script identifies the dominant LP wavelength
6. If the channels have significantly different gradients, the script recommends **VeraLux Nox** for per-channel extraction

### Use Case 5: Checking Your Flat Frames

**Scenario:** You want to verify that your flat frames properly corrected vignetting.

**Workflow:**
1. Load a flat-calibrated stacked image (before background extraction)
2. Analyze with F5
3. Check the **vignetting vs. LP** result:
   - If radial R² is high → significant residual vignetting → your flats aren't working well
   - If radial R² is low → flats did their job
4. Check the **Vignetting Symmetry** warning — asymmetric vignetting means the flat doesn't match the imaging configuration
5. Check the **FITS header calibration check** — the script reads `FLATCOR` from the header to confirm a flat was applied

### Use Case 6: Before/After Comparison

**Scenario:** You want to quantify exactly how much your processing improved the background.

**Workflow:**
1. Load the image **before** gradient extraction
2. Enable **"Save analysis JSON"**
3. Press F5 — metrics and tile data are saved to `gradient_analysis.json`
4. Apply gradient extraction in Siril
5. Press F5 again — the script loads the previous JSON and computes deltas
6. Check the **Before/After** tab in Analysis Results — see the exact percentage improvement
7. The heatmap uses the **same colorbar range** as the first run, so visual comparison is meaningful

### Use Case 7: Narrowband Image Analysis

**Scenario:** You're processing a narrowband (Ha, OIII, SII) image and want to check gradients.

**Workflow:**
1. Load the narrowband image
2. Switch the preset to **"Narrowband (strict)"** in the dropdown
3. Press F5
4. The stricter thresholds will flag gradients that would be considered "normal" for broadband but problematic for narrowband
5. Note: narrowband images often have lower absolute gradients, but the thresholds account for this

### Use Case 8: Fast Optics Vignetting Assessment

**Scenario:** You're using a fast telescope (f/2–f/4) and want to assess the natural vignetting vs. external gradients.

**Workflow:**
1. Load the image
2. Switch preset to **"Fast optics (tolerant)"**
3. Press F5
4. Check the **Cos⁴ analysis** in the detailed metrics — the script estimates the natural optical falloff for your focal ratio and separates it from any external gradient
5. The tolerant thresholds avoid false alarms from the expected cos⁴ falloff

### Use Case 9: Documenting for Forum Help

**Scenario:** You're posting on an astrophotography forum asking for help with your gradient, and want to include diagnostic data.

**Workflow:**
1. Analyze the image (F5)
2. Enable **"Save heatmap as PNG"** — gives you a visual to post
3. Click **"Export Report"** — the text report is copied to your clipboard
4. Paste the report into your forum post, and attach the heatmap PNG
5. Forum members can see exactly what your gradient looks like and what the tool recommends

---

## 14. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F5` | Run analysis (same as clicking "Analyze") |
| `Esc` | Close the window |

---

## 15. Tips & Best Practices

### When to Analyze

1. **Analyze before stretching.** This is the most important rule. Gradient measurements on linear (unstretched) data are accurate and comparable. On stretched data, gradients are amplified and the percentages are inflated.

2. **Analyze after calibration but before extraction.** The ideal point is: bias/dark/flat calibrated → registered → stacked → **Gradient Analyzer** → extraction → stretching.

3. **Re-analyze after extraction.** Always check that your gradient removal actually worked. The before/after comparison is the most valuable feature.

### Grid and Sigma Settings

4. **16×16 is a great default.** Only increase if you need to find localized features. Only decrease if your image is very small.

5. **Trust the sigma suggestion.** The adaptive recommendation (yellow text) is based on your actual star density. If it says "try 3.0," try it.

6. **Use the right preset.** Narrowband, broadband, and fast optics have genuinely different gradient characteristics. The wrong preset will either miss real problems or create false alarms.

### Reading the Results

7. **The gauge is your TL;DR.** Green = don't worry. Yellow = mild, optional fix. Orange = definitely fix. Red = must fix.

8. **Check warnings first.** If the script detects banding, amp glow, missing flats, or dew, fix those *before* doing gradient extraction. The warnings are priority-ordered in the recommendations.

9. **The heatmap tells the story.** A uniform heatmap with one bright corner = LP. A dark-corners-bright-center pattern = vignetting. Stripes = banding. Random hot tiles = artifacts.

10. **Use the 3D view for intuition.** The 3D surface makes the gradient "landscape" immediately obvious. A tilted plane = LP. A bowl shape = vignetting. Spikes = hotspots.

### Practical Tips

11. **The sample point guidance saves time.** When using `subsky`, place your sample points in the green-circled regions shown on the heatmap. Avoid the red-crossed regions.

12. **Enable RGB separate when LP is colorful.** If you're in an urban area with mixed lighting (LED + sodium), chromatic LP analysis reveals which channels need the most correction.

13. **The JSON comparison is powerful.** Enable JSON saving, analyze, extract, re-analyze — the delta values give you an objective measure of improvement that's more reliable than visual judgment.

14. **Don't over-extract.** If the gauge shows green (< 1.5%), stop. Further extraction risks removing real signal (faint nebulosity, faint galaxy halos). The goal is "uniform enough," not "perfectly flat."

---

## 16. Troubleshooting

### "No image loaded" error

**Cause:** No image is open in Siril.
**Fix:** Load a FITS image before running the script.

### "Could not connect to Siril" error

**Cause:** The sirilpy connection timed out.
**Fix:** Make sure Siril is fully loaded and responsive. Try closing and reopening the script.

### Analysis is very slow

**Cause:** High grid resolution (32×32 or more) on a large image, or FWHM analysis on a large image.
**Fix:** Reduce grid resolution. FWHM analysis (Tab 8) is the slowest step — it measures star shapes in every tile. On large images, this can take minutes. Other tabs appear quickly.

### "Stretched data" warning when data is linear

**Cause:** The script uses statistical heuristics (mean/median ratio) to detect stretched data. Some naturally skewed data may trigger a false positive.
**Fix:** If you know your data is linear, you can ignore this warning. The analysis is still valid, just flagged for caution.

### Gradient strength seems too high / too low

**Cause:** Wrong preset selected. Broadband thresholds on narrowband data will show everything as "uniform." Narrowband thresholds on broadband data will flag normal gradients as severe.
**Fix:** Select the correct preset in the dropdown.

### Heatmap shows artifacts, not gradients

**Cause:** Hotspots (satellite trails, cosmic rays, bright stars leaking through sigma-clip) can distort the heatmap.
**Fix:** The script automatically detects and excludes hotspots from the polynomial fit. Check the **Residuals / Mask** tab to see which tiles were excluded. If sigma-clipping isn't aggressive enough, try lowering the sigma value.

### Before/After comparison shows no change

**Cause:** The JSON file from the previous run wasn't saved, or you loaded a different image.
**Fix:** Enable "Save analysis JSON" before the first run. Make sure you're analyzing the same image (in the same working directory) both times.

### FWHM / Eccentricity tab is empty

**Cause:** Too few stars detected per tile, or the image is very small.
**Fix:** This requires at least 3 stars per tile with FWHM > 1.5 px. Dense nebulae or very small tiles may not have enough stars. Reduce grid resolution for larger tiles.

### RGB Channels tab is empty

**Cause:** "Analyze channels separately" is not enabled, or the image is mono.
**Fix:** Check the "Analyze channels separately" checkbox before analyzing. This option is auto-disabled for mono images.

---

## 17. FAQ

**Q: Do I need to run this on every image?**
A: It's most useful on your first stack from a session or whenever you change imaging location, target, or gear. Once you know the typical gradient pattern for your setup, you can skip it for similar images. But it's always worth checking — conditions change.

**Q: Does this tool actually remove gradients?**
A: No — the Gradient Analyzer is purely diagnostic. It *analyzes* gradients and *recommends* tools, but it doesn't modify your image. You apply the recommended extraction separately in Siril (e.g., `subsky`, `autobackgroundextraction`) or in external tools like GraXpert.

**Q: Can I use this on unstacked subframes?**
A: Yes, it works on any FITS image. Analyzing individual subframes can help identify which frames have the worst gradients, or spot issues like amp glow or banding before stacking.

**Q: What's the difference between this and just running AutoBGE?**
A: AutoBGE blindly removes *something* from the background. The Gradient Analyzer tells you *what's there first* — vignetting, LP, banding, amp glow, stacking edges — so you can apply the right fix for each problem. Running AutoBGE on an image with amp glow just spreads the problem; knowing it's amp glow tells you to apply dark frames instead.

**Q: Why does the gradient strength change when I change the grid resolution?**
A: The P95-P5 metric is computed from tile medians. More tiles = more spatial sampling = slightly different P95/P5 values. The change is usually small (within 0.5%). For consistency, stick with the same grid resolution when doing before/after comparisons.

**Q: What's the minimum image size?**
A: Technically any image works, but for meaningful results you need at least 400×400 pixels so that tiles at the default 16×16 grid are 25+ pixels each. Larger images give better results.

**Q: Can I use this with OSC (one-shot color) cameras?**
A: Yes. OSC images are debayered into RGB by Siril, so the Gradient Analyzer sees them as normal 3-channel images. The per-channel analysis works correctly.

**Q: Why does the script recommend GraXpert for my image?**
A: When the polynomial fit quality is poor (all R² < 0.5), traditional polynomial surfaces can't model your gradient well. This happens with complex, multi-source gradients. GraXpert uses AI to model arbitrary background patterns that polynomials can't capture.

**Q: How accurate is the sky brightness / Bortle estimate?**
A: It's a rough approximation (±1–2 magnitudes). It requires an SPCC-calibrated image with a known plate scale and exposure time. Use it as a general indicator, not a precise measurement. For serious sky quality monitoring, use a dedicated SQM meter.

**Q: What do the colors in the gradient strength gauge mean?**
A: Green = very uniform, no action needed. Yellow = slight gradient, gentle extraction is optional. Orange = significant gradient, extraction is recommended. Red = strong gradient, aggressive extraction is required. The thresholds depend on the selected preset.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Blink Comparator
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
