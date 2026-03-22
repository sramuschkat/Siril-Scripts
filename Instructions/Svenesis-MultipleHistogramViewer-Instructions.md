# Svenesis Multiple Histogram Viewer — User Instructions

**Version 1.0.1** | Siril Python Script for Histogram Comparison & Image Inspection

> *Side-by-side histogram and image comparison — see your linear, auto-stretched, and custom-stretched images together with interactive pixel inspection.*

---

## Table of Contents

1. [What Is the Multiple Histogram Viewer?](#1-what-is-the-multiple-histogram-viewer)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [The Four Columns](#6-the-four-columns)
7. [Histogram Display](#7-histogram-display)
8. [3D Surface Plot](#8-3d-surface-plot)
9. [Channel Selection](#9-channel-selection)
10. [Data Modes (Linear / Logarithmic)](#10-data-modes-linear--logarithmic)
11. [Image Zoom & Navigation](#11-image-zoom--navigation)
12. [Interactive Pixel Inspection](#12-interactive-pixel-inspection)
13. [Statistics Panel](#13-statistics-panel)
14. [Use Cases & Workflows](#14-use-cases--workflows)
15. [Tips & Best Practices](#15-tips--best-practices)
16. [Troubleshooting](#16-troubleshooting)
17. [FAQ](#17-faq)

---

## 1. What Is the Multiple Histogram Viewer?

The **Svenesis Multiple Histogram Viewer** is a Siril Python script that displays your image's histogram alongside the image itself, in up to four side-by-side columns for direct comparison. It reads the current linear image from Siril, auto-stretches it, and lets you load up to two additional stretched FITS files for comparison.

Think of it as a **visual comparison workbench**. It combines:

- **Side-by-side display** — see your linear image, its auto-stretched version, and up to two custom-stretched versions simultaneously
- **Per-channel histograms** — view RGB (luminance), R, G, B, and L channels individually or overlaid
- **3D surface plots** — visualize your image as a 3D height map where pixel brightness is the elevation
- **Interactive pixel inspection** — click anywhere on an image to see the exact pixel values in ADU and mark the position on the histogram
- **Comprehensive statistics** — min, max, mean, median, standard deviation, IQR, MAD, percentiles, and clipping percentages

The tool is purely read-only — it does not modify your image. It helps you understand your data and compare different stretching results.

---

## 2. Background for Beginners

### What Is a Histogram?

A histogram is a chart that shows **how many pixels in your image have each brightness value**. The horizontal axis (X) represents pixel brightness from black (left) to white (right). The vertical axis (Y) represents how many pixels have that brightness.

In astrophotography, histograms are essential for understanding your data:

| Histogram Shape | What It Means |
|----------------|--------------|
| **Tall spike on the far left** | Most pixels are very dark — this is normal for a linear (unstretched) image |
| **Smooth bell curve in the middle** | Well-stretched image with good tonal range |
| **Spike touching the right edge** | Clipped highlights — some stars or bright regions have lost detail |
| **Spike touching the left edge** | Clipped shadows — some dark areas have lost detail |
| **Wide, spread-out curve** | Good dynamic range — lots of tonal detail to work with |
| **Narrow, compressed curve** | Low dynamic range — limited tonal detail |

### What Is ADU?

**ADU (Analog-to-Digital Units)** is the raw numerical value that your camera sensor records for each pixel. It represents the brightness of that pixel in the camera's native units.

| Camera Bit Depth | ADU Range | Meaning |
|-----------------|-----------|---------|
| 8-bit | 0–255 | 256 possible brightness levels (JPEG, webcam) |
| 14-bit | 0–16,383 | 16,384 levels (most modern astro cameras) |
| 16-bit | 0–65,535 | 65,536 levels (common FITS format, highest precision) |

The Histogram Viewer shows pixel values in ADU so you can see the actual numbers your camera recorded. The X-axis ranges from 0 to your image's maximum ADU value.

### What Is Linear vs. Stretched?

A **linear** image is one where pixel values are directly proportional to the number of photons received. This is the raw output of calibration and stacking — it looks very dark because most detail is compressed into the bottom few percent of the brightness range.

A **stretched** image has been mathematically transformed to reveal the faint detail. The transformation expands the shadows while compressing the highlights, making nebulae and faint structures visible.

| State | Histogram Shape | Image Appearance |
|-------|----------------|-----------------|
| **Linear** | Tall spike at far left, almost nothing else | Very dark, grey, featureless |
| **Stretched** | Broader curve, peak shifted right | Visible nebulae, stars, background |

The Histogram Viewer shows both side-by-side so you can see exactly how stretching transforms the data.

### What Is Autostretch?

**Autostretch** is a quick, automatic stretch that maps the 2nd percentile (dark reference) to black and the 98th percentile (bright reference) to white. It's a simple percentile-based remapping:

```
stretched_value = (original_value - P2) / (P98 - P2)
```

This is not the same as Siril's GHT or MTF stretches — it's a linear remap for quick visualization. The Histogram Viewer applies this automatically to your linear image so you can see what's in the data.

### What Is a 3D Surface Plot?

Instead of viewing your image flat, a 3D surface plot treats each pixel's brightness as **height**. Bright areas become peaks; dark areas become valleys. This makes gradients, vignetting, and brightness patterns immediately obvious:

- **A tilted plane** = gradient (light pollution from one side)
- **A bowl shape** = vignetting (dark corners, bright center)
- **Sharp spikes** = bright stars
- **Gentle plateau** = nebulosity

---

## 3. Prerequisites & Installation

### Requirements

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| **Siril** | 1.4.0+ | Must have Python script support enabled |
| **sirilpy** | Bundled | Comes with Siril 1.4+ |
| **numpy** | Any recent | Auto-installed by the script |
| **PyQt6** | 6.x | Auto-installed by the script |
| **Pillow** | Any recent | Auto-installed; used for high-quality image resizing |
| **astropy** | Any recent | Auto-installed; used for FITS file reading (including compressed .fz/.gz) |
| **matplotlib** | 3.x | Auto-installed; used for 3D surface plots |

### Installation

1. Download `Svenesis-MultipleHistogramViewer.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script automatically installs missing Python dependencies on first run.

---

## 4. Getting Started

### Step 1: Load an Image in Siril

Load any FITS image in Siril. The Histogram Viewer is designed for **linear** (unstretched) stacked images, but works on any FITS image.

### Step 2: Run the Script

Go to **Processing → Scripts → Svenesis Multiple Histogram Viewer**.

The script opens its window and immediately loads the current image from Siril. You'll see two columns:

- **Linear** — your original image data (may appear very dark)
- **Auto-Stretched** — the same data with a percentile-based autostretch applied for visibility

Each column shows the image, its histogram (or 3D surface plot), and statistics.

### Step 3: Explore the Data

- **Switch channels** — use the checkboxes (histogram) or radio buttons (3D plot) to view individual R, G, B channels or luminance
- **Switch to log mode** — toggle "Logarithmic" to see the histogram's faint tails
- **Click on the image** — click any pixel to see its exact ADU value and mark the position on the histogram
- **Zoom in** — use the zoom buttons (-, Fit, 1:1, +) to inspect details

### Step 4: Load Comparison Images (Optional)

To compare different stretching results:

1. Click **"Load stretched FITS 1"** and select a stretched version of the same image
2. A third column appears showing that image with its histogram and statistics
3. Optionally load a second stretched FITS via **"Load stretched FITS 2"** for a fourth column

Now you can see all versions side-by-side — linear, auto-stretched, and your custom stretches.

---

## 5. The User Interface

### Left Panel (Control Panel)

The left side (320px wide) contains all controls:

#### Title
"Svenesis Multiple Histogram Viewer 1.0.1" in blue.

#### View Group (Radio Buttons)
- **Histogram** — shows the 2D histogram below each image (default)
- **3D Surface Plot** — shows a 3D height-map visualization below each image

#### Data-Mode Group (Radio Buttons)
- **Normal** — linear Y-axis for histograms, linear Z-axis for 3D plots (default)
- **Logarithmic** — log₁₀(count + 1) for histograms, log₁₀(ADU + 1) for 3D plots

#### Histogram Channels Group (Checkboxes)
Controls which channels appear on the 2D histogram:
- **RGB** — combined luminance (Rec.709: 0.2126R + 0.7152G + 0.0722B), shown as a filled white area
- **R** — red channel, shown as a red line
- **G** — green channel, shown as a green line
- **B** — blue channel, shown as a blue line
- **L** — luminance (same Rec.709 formula), shown as a yellow line

All channels except L are enabled by default. Multiple channels can be displayed simultaneously.

#### 3D Plot Channels Group (Radio Buttons)
Selects which channel determines the Z-axis (height) of the 3D surface plot:
- **RGB** — luminance (default)
- **R**, **G**, **B** — individual channels
- **L** — luminance

Only one channel can be shown at a time in 3D (radio buttons, not checkboxes).

#### Image Group (Buttons)
- **Refresh from Siril** — reloads the current image from Siril (useful after processing steps)
- **Load linear FITS...** — opens a file dialog to load a linear FITS file from disk (instead of from Siril)

#### Stretched Comparisons Group
Two slots for loading external stretched FITS files:
- **Load stretched FITS 1** / **Load stretched FITS 2** — opens file dialog to load a stretched image
- **Clear** — removes the loaded comparison image and hides its column

Supported formats: `.fit`, `.fits`, `.fts`, `.fz` (compressed), `.gz` (gzip-compressed).

#### Bottom Buttons
- **Buy me a Coffee** — support link
- **Help** — detailed 13-section help dialog
- **Close** — exits the script

### Right Panel (Columns)

The right side shows 2–4 columns arranged side-by-side (see Section 6).

---

## 6. The Four Columns

The right panel contains up to four columns, each showing one version of the image:

### Column 1: Linear

Always visible. Shows your **original linear image data** — pixel values exactly as they came from calibration and stacking.

The image may appear very dark because linear data has most of its information compressed near the bottom of the brightness range. This is normal.

### Column 2: Auto-Stretched

Always visible. Shows the **same linear data with an automatic percentile stretch applied**. The stretch maps the 2nd percentile to black and the 98th percentile to white, making faint structures visible.

This is a quick preview stretch — not the same as Siril's GHT or other advanced stretching methods. It helps you see what's in the data without modifying the original.

### Column 3: Stretched FITS 1 (Optional)

Appears when you load a stretched FITS file via the "Load stretched FITS 1" button. Shows the image you loaded with its own histogram and statistics.

### Column 4: Stretched FITS 2 (Optional)

Appears when you load a second stretched FITS file. Allows comparing two different stretching approaches side-by-side.

### What Each Column Contains

Every column has the same structure from top to bottom:

| Element | Description |
|---------|------------|
| **Column title** | "Linear", "Auto-Stretched", or the filename of the loaded FITS |
| **Zoom toolbar** | Four buttons: − (zoom out), Fit (fit to view), 1:1 (100%), + (zoom in) |
| **Image view** | The image displayed in a scrollable, zoomable viewport |
| **Histogram or 3D plot** | The visualization selected in the View group |
| **"Enlarge Diagram" button** | Opens the histogram or 3D plot in a large, maximizable modal dialog |
| **Statistics** | Monospace text showing min, max, mean, median, std, IQR, MAD, percentiles, clipping |

---

## 7. Histogram Display

### How the Histogram Is Computed

1. The image is divided into individual channels (or combined into luminance)
2. For large images (> 5 million pixels), a uniform subsample is taken for performance
3. `numpy.histogram()` computes 256 bins across the [0, 1] normalized range
4. Bin counts are displayed on the Y-axis; bin positions are mapped to ADU on the X-axis

### Reading the Histogram

**X-axis: Pixel Value (ADU 0–max)**
The horizontal axis shows brightness in ADU units, from 0 (black) to your image's maximum ADU value (e.g., 65535 for 16-bit data). Five tick marks are shown at 0%, 25%, 50%, 75%, and 100% of the ADU range.

**Y-axis: Pixel Count**
The vertical axis shows how many pixels have each brightness value. In Normal mode, this is a direct count. In Logarithmic mode, it's log₁₀(count + 1).

**Channel colors:**

| Channel | Display Style | Color |
|---------|--------------|-------|
| **RGB** | Filled area (semi-transparent) with outline | White |
| **R** | Thin line | Red |
| **G** | Thin line | Green |
| **B** | Thin line | Blue |
| **L** | Thin line | Yellow/gold |

Multiple channels can be overlaid simultaneously. The RGB filled area appears behind the individual channel lines.

### Grid Lines

Dotted grid lines appear at 25%, 50%, and 75% on both axes, helping you judge the distribution of pixel values.

### Enlarge Diagram

Click the **"Enlarge Diagram"** button below any column's histogram to open it in a large, maximizable modal dialog. This is useful for detailed inspection of subtle histogram features.

---

## 8. 3D Surface Plot

### What It Shows

The 3D surface plot represents your image as a landscape where:
- **X and Y axes** = pixel position (row and column)
- **Z axis** = pixel brightness (ADU value or log₁₀(ADU + 1))

Bright areas rise up; dark areas sink down. This makes spatial brightness patterns (gradients, vignetting) immediately visible.

### How It's Computed

The image is downsampled to a maximum of 100×100 grid (the `SURFACE_PLOT_MAX_SIDE` constant) for performance. The selected channel (RGB luminance, R, G, B, or L) determines the Z-axis values.

A viridis colormap is applied to the surface (dark purple → blue → green → yellow).

### Interaction

The 3D plot is rendered via matplotlib and displayed as a static image. Use the **"Enlarge Diagram"** button to see it at a larger size.

When you click on the image in the same column, a vertical line and marker dot appear on the 3D surface at the corresponding position, showing the Z-value label.

### Normal vs. Logarithmic

In **Normal** mode, the Z-axis shows the raw ADU value — useful for seeing the full dynamic range but bright stars can dominate.

In **Logarithmic** mode, the Z-axis shows log₁₀(ADU + 1) — compresses the range so you can see both faint background and bright features.

---

## 9. Channel Selection

### Histogram Channels (Checkboxes)

You can show or hide any combination of channels on the histogram:

| Channel | Formula | When to Use |
|---------|---------|-------------|
| **RGB** | 0.2126 × R + 0.7152 × G + 0.0722 × B | See the overall brightness distribution (most common view) |
| **R** | Red channel only | Check red signal strength, red LP, Ha emission |
| **G** | Green channel only | Check green noise, OIII emission, color balance |
| **B** | Blue channel only | Check blue signal (often noisiest), OIII emission |
| **L** | Same formula as RGB (Rec.709 luminance) | Same as RGB but drawn as a thin yellow line instead of a filled area |

**Typical combinations:**
- **RGB only** — quick overview of the overall histogram shape
- **R + G + B** — compare individual channel distributions (color balance check)
- **RGB + R + G + B** — all channels overlaid for comprehensive view
- **L only** — clean luminance view without the filled area

### 3D Plot Channels (Radio Buttons)

Only one channel can drive the 3D surface height at a time. Select the channel you want to visualize:

- **RGB/L** — see overall brightness as height
- **R, G, or B** — see a single channel's spatial distribution

---

## 10. Data Modes (Linear / Logarithmic)

### Normal (Linear) Mode

| Axis | Display |
|------|---------|
| Histogram Y-axis | Direct pixel count |
| 3D plot Z-axis | ADU value (0 to max) |

Best for: Seeing the dominant features of the histogram (the main peak, the overall shape). The brightest/most-common values dominate the display.

### Logarithmic Mode

| Axis | Display |
|------|---------|
| Histogram Y-axis | log₁₀(count + 1) |
| 3D plot Z-axis | log₁₀(ADU + 1) |

Best for: Seeing faint tails and low-level features that would be invisible on a linear scale. When the main peak is thousands of times higher than the tails, logarithmic mode reveals the tails.

**When to use logarithmic:**
- Your linear image's histogram looks like a single spike with nothing else visible
- You want to see the faint star/nebula tail on the right side of the histogram
- The 3D surface plot is dominated by a few bright stars and the background is flat

---

## 11. Image Zoom & Navigation

Each column has four zoom buttons in a toolbar above the image:

| Button | Action | When to Use |
|--------|--------|-------------|
| **−** | Zoom out (÷ 1.2) | Pull back to see more of the image |
| **Fit** | Fit entire image to the viewport, maintaining aspect ratio | Reset to overview after zooming in |
| **1:1** | 100% zoom (1 screen pixel = 1 image pixel) | Inspect fine detail at native resolution |
| **+** | Zoom in (× 1.2) | Get closer to a specific area |

**Performance note:** For images larger than 4096 pixels on any side, the display version is downscaled using high-quality Lanczos resampling (via Pillow). The original full-resolution data is preserved for statistics and pixel inspection — only the displayed image is resized.

The zoom level is independent per column, so you can zoom into the same region on different columns to compare stretching results at the same detail level.

---

## 12. Interactive Pixel Inspection

### Clicking on an Image

Click anywhere on any image in any column to inspect that pixel:

1. The exact pixel coordinates are computed (accounting for any display downscaling)
2. The pixel's R, G, B values are sampled from the image data
3. An intensity value (luminance) is calculated
4. All values are converted to ADU using the image's ADU range

### What Appears

**In the statistics panel** of the clicked column, a new line is appended:

```
Click (x=1234, y=567): R=1023 G=987 B=876  I=974
```

Where:
- `x`, `y` = pixel coordinates in the original image
- `R`, `G`, `B` = ADU values for each channel
- `I` = luminance intensity in ADU

**On the histogram**, a vertical dashed marker line appears at the clicked pixel's intensity value, with a label showing:

```
Value: 974   Count: 1,234
```

This shows you exactly where on the histogram that pixel falls and how many other pixels share that brightness.

**On the 3D surface plot**, a vertical line and marker dot appear at the clicked position, showing the Z-value.

**Important:** Clicking on one column's image sets the marker on that column's histogram only. Markers on other columns are automatically cleared to avoid confusion.

---

## 13. Statistics Panel

Below each column's histogram/3D plot, a statistics panel shows comprehensive numerical data about the image.

### Statistics Displayed

| Metric | Description |
|--------|------------|
| **Size** | Image dimensions (width × height) |
| **Pixels** | Total pixel count (may show "subsampled" for images > 5M pixels) |
| **Min / Max** | Minimum and maximum pixel values in ADU |
| **Mean** | Average pixel value in ADU |
| **Median** | Middle pixel value in ADU (50th percentile) |
| **Std** | Standard deviation in ADU — measures the spread of values |
| **IQR** | Interquartile range (P75 − P25) in ADU — robust spread measure |
| **MAD** | Median Absolute Deviation in ADU — another robust spread measure |
| **P2 / P98** | 2nd and 98th percentile values in ADU — the autostretch reference points |
| **Range** | P98 − P2 in ADU — the "useful" dynamic range |
| **Near-black** | Percentage and count of pixels with value ≤ 1/255 of full range |
| **Near-white** | Percentage and count of pixels with value ≥ 254/255 of full range |

### Interpreting the Statistics

**For a linear image (Linear column):**
- Min near 0, Max much higher → normal linear data
- P2 very close to P98 → most data compressed in a narrow range (normal for linear)
- High near-black % → normal (most pixels are background near zero)

**For an auto-stretched image:**
- P2 near 0, P98 near maximum → good stretch filling the range
- Std and IQR indicate the tonal spread
- Near-white > 0 → some clipping at the bright end

**For stretched comparison images:**
- Compare Std, IQR, and MAD between different stretches
- Check near-black and near-white to see which stretch clips more
- P2/P98 range shows how much of the tonal range each stretch uses

### Pixel Inspection Lines

When you click on an image, the pixel values are appended to that column's statistics panel. Multiple clicks accumulate, so you can sample several pixels and compare their values.

---

## 14. Use Cases & Workflows

### Use Case 1: Understanding Your Linear Data (2 minutes)

**Scenario:** You've just stacked an image and want to understand what you're working with before processing.

**Workflow:**
1. Load the stacked image in Siril
2. Run the Multiple Histogram Viewer
3. Look at the **Linear column**:
   - Is the histogram a narrow spike near the left? That's normal linear data.
   - How much data extends to the right? More = more signal.
4. Look at the **Auto-Stretched column**:
   - Can you see nebulosity, galaxies, or other structures? If yes, there's signal to work with.
   - Is the background smooth or gradient-affected?
5. Switch to **Logarithmic mode** to see the faint tail of the linear histogram — this reveals signal from faint objects that's invisible in Normal mode.

### Use Case 2: Comparing Stretching Methods (5 minutes)

**Scenario:** You've applied different stretching methods (GHT, Asinh, AutoStretch) and saved them as separate FITS files. You want to compare the results.

**Workflow:**
1. Load the **linear** image in Siril and run the Histogram Viewer
2. Click **"Load stretched FITS 1"** and select your GHT-stretched version
3. Click **"Load stretched FITS 2"** and select your Asinh-stretched version
4. Now you have four columns: Linear, Auto-Stretched, GHT, and Asinh
5. Compare:
   - **Histograms:** Which stretch gives the smoothest, widest distribution?
   - **Near-white %:** Which stretch clips the fewest highlights?
   - **Images:** Zoom to 1:1 and compare fine detail, star sizes, and noise
6. Click the same star in each column to compare its ADU value across stretches

### Use Case 3: Checking Color Balance (3 minutes)

**Scenario:** You've applied SPCC and want to verify the color balance.

**Workflow:**
1. Load the color-calibrated image
2. Run the Histogram Viewer
3. Enable **R, G, B** channels on the histogram (disable RGB and L for clarity)
4. Look at the three channel histograms:
   - **Well-balanced:** R, G, B peaks align roughly at the same position
   - **Color cast:** One channel's peak is shifted significantly left or right
5. Check the **Per-channel statistics**: Compare the R, G, B median values
6. If one channel is noticeably offset, color calibration may need adjustment

### Use Case 4: Detecting Clipping (2 minutes)

**Scenario:** You want to check if your image has clipped highlights or crushed shadows.

**Workflow:**
1. Load the image and run the Histogram Viewer
2. Check the **statistics panel** for each column:
   - **Near-black > 0%:** Some shadow clipping (normal for linear data; concerning for stretched data)
   - **Near-white > 0%:** Highlight clipping (star cores, bright nebula regions)
3. Switch to **Logarithmic mode** to see if the histogram touches the edges
4. Click on suspect bright stars to check their ADU values — values near the maximum indicate saturation

### Use Case 5: Checking Gradient / Vignetting

**Scenario:** You suspect a background gradient and want to visualize it.

**Workflow:**
1. Load the stacked (linear) image
2. Run the Histogram Viewer
3. Switch to **3D Surface Plot** view
4. The 3D surface of the **Linear** column reveals the background topography:
   - **Tilted plane** = directional gradient (light pollution)
   - **Bowl/dome shape** = vignetting
   - **Spikes** = bright stars
5. Switch to **Logarithmic** 3D mode if bright stars dominate the plot — log compression reveals the background shape underneath
6. Compare the Linear and Auto-Stretched 3D plots — the autostretch can exaggerate gradients, making them more visible

### Use Case 6: Before/After Processing Comparison

**Scenario:** You've applied background extraction and want to see how the histogram changed.

**Workflow:**
1. Before extraction: save the image as a FITS file (e.g., `before_subsky.fits`)
2. Apply background extraction in Siril
3. Run the Histogram Viewer — it loads the current (post-extraction) image
4. Click **"Load stretched FITS 1"** and load your saved `before_subsky.fits`
5. Now compare:
   - The Linear column shows your post-extraction data
   - The Stretched FITS 1 column shows your pre-extraction data
   - Compare histograms: the post-extraction histogram should be narrower (less gradient spread)
   - Compare statistics: lower Std and IQR indicate more uniform background

### Use Case 7: Checking Ha / Narrowband Signal

**Scenario:** You have a narrowband (Ha) image and want to see where the signal is.

**Workflow:**
1. Load the narrowband stack
2. Run the Histogram Viewer
3. Since it's mono, the RGB/R/G/B channels all show the same data
4. Switch to **Logarithmic** mode to see the faint emission tail
5. Switch to **3D Surface Plot** — the emission regions appear as elevated plateaus above the background
6. Click on bright emission regions vs. background to compare their ADU values

---

## 15. Tips & Best Practices

### Histogram Reading

1. **Always check logarithmic mode.** Normal mode shows the dominant peak clearly, but the faint signal tail (where your nebula lives) is often invisible until you switch to log mode.

2. **Compare the same channels across columns.** When comparing stretches, keep the same channel selection across all columns for a fair comparison.

3. **The gap between the main peak and the right tail is your signal.** In a linear histogram, the main peak is background noise. Everything to the right is signal from your target.

### 3D Surface Plots

4. **Use 3D plots for gradient detection.** Gradients are much more obvious in 3D than in a flat image or histogram. A gradient that's invisible in the image becomes an obvious tilt in the 3D plot.

5. **Log mode in 3D tames bright stars.** If a few bright stars create tall spikes that flatten everything else, switch to logarithmic mode.

### Pixel Inspection

6. **Click corresponding positions across columns.** Click the same star or region in each column to compare how different stretches affect that specific pixel.

7. **Use pixel clicks to understand the histogram.** Clicking a pixel places a marker on the histogram — this teaches you which histogram regions correspond to which image features.

### Image Comparison

8. **Use the same zoom level across columns.** Zoom to 1:1 in all columns, then scroll to the same region for a fair visual comparison.

9. **The autostretch is a baseline.** It's not an optimal stretch — it's a quick percentile remap. Compare your custom stretches against it to see how much better your technique is.

10. **Check near-black and near-white percentages.** A good stretch maximizes tonal range without clipping either end. Compare these numbers across different stretches.

### Performance

11. **Large images are automatically subsampled** for statistics and histograms (> 5M pixels). The values are still accurate — subsampling preserves the statistical distribution.

12. **Images larger than 4096px** are downscaled for display using high-quality Lanczos resampling. The statistics and pixel inspection use the full-resolution data.

---

## 16. Troubleshooting

### "No image loaded" Error

**Cause:** No image is open in Siril.
**Fix:** Load a FITS image in Siril before running the script, or use "Load linear FITS..." to load directly from disk.

### "Connection timed out" Error

**Cause:** The sirilpy connection to Siril timed out.
**Fix:** Make sure Siril is responsive. Click "Refresh from Siril" to retry.

### Columns Are Too Narrow

**Cause:** With 4 columns, each column may be narrow on smaller screens.
**Fix:** The window opens maximized. Each column has a minimum width of 280px. Use the "Enlarge Diagram" button to see histograms at full size. Consider loading fewer comparison images if screen space is limited.

### 3D Surface Plot Is Blank

**Cause:** matplotlib may not be installed or may have a rendering issue.
**Fix:** The script auto-installs matplotlib, but if it fails, install it manually: `pip install matplotlib`. Restart the script.

### Linear Image Appears Completely Black

**Cause:** Normal — linear astrophotography images have most pixel values near zero. The background sits near the bottom of the ADU range.
**Fix:** This is expected. Look at the Auto-Stretched column to see what's in the data. The Linear column shows the raw values, which are useful for statistics but not for visual inspection.

### Histogram Shows Only a Single Spike

**Cause:** This is the normal appearance of a linear image histogram — all the background pixels are compressed into one narrow peak near zero.
**Fix:** Switch to **Logarithmic** mode to see the faint tail extending to the right. That tail is your signal (stars, nebulae).

### Compressed FITS Files Won't Load

**Cause:** Older astropy versions may not support `.fz` (fpack) or `.gz` (gzip) compressed FITS.
**Fix:** Update astropy: `pip install --upgrade astropy`. Version 1.0.1 of the Histogram Viewer added compressed FITS support.

### Pixel Click Shows Wrong Coordinates

**Cause:** For images larger than 4096px, the display is downscaled. Coordinate mapping should account for this, but edge cases may occasionally be off by a pixel.
**Fix:** The statistics still show the correct ADU values from the original data. Use the coordinates as approximate for large downscaled images.

---

## 17. FAQ

**Q: Does this tool modify my image?**
A: No — it is completely read-only. It reads pixel data from Siril (or from FITS files) and displays histograms and statistics. Your image is never altered.

**Q: What's the difference between the "Auto-Stretched" column and my own stretch?**
A: The auto-stretch is a simple percentile remap (2nd to 98th percentile mapped to [0, 1]). It's a quick visualization tool, not an optimal stretch. Your custom stretch (GHT, Asinh, etc.) should produce better results with more control over tonal distribution.

**Q: Why are there two luminance options (RGB and L)?**
A: They compute the same Rec.709 luminance value. The difference is how they're displayed — **RGB** is drawn as a filled semi-transparent area (good for seeing the overall shape), while **L** is drawn as a thin yellow line (good for overlaying on top of individual channel lines without obscuring them).

**Q: Can I load more than two comparison images?**
A: No — the current version supports two stretched comparison slots. For comparing more versions, close and reopen with different files.

**Q: Why is the X-axis in ADU instead of normalized 0–1?**
A: ADU values are what your camera actually recorded. They're more intuitive for understanding your data — you can relate them to your camera's bit depth and saturation point. The histogram is computed on normalized [0, 1] data internally but displayed in ADU for readability.

**Q: Can I use this with mono (grayscale) images?**
A: Yes. For mono images, all channels (R, G, B, RGB, L) show the same data. The histogram will have overlapping identical lines.

**Q: What does "subsampled" mean in the statistics?**
A: For images with more than 5 million pixels, a uniform subsample is used for statistics and histogram computation. This keeps performance responsive without meaningfully affecting accuracy — the subsample preserves the statistical distribution of the full image.

**Q: Why does the auto-stretch look different from Siril's autostretch?**
A: The Histogram Viewer uses a simple linear percentile stretch (P2 to P98), while Siril's autostretch may use different algorithms (midtone transfer function, generalized hyperbolic, etc.) with different parameters. The Viewer's autostretch is intentionally simple — it's a quick preview, not a processing step.

**Q: Can I export the histogram as an image?**
A: Not directly — the current version doesn't have an export feature. You can use the "Enlarge Diagram" button to view the histogram at full size and take a screenshot using your operating system's screenshot tool.

**Q: What's the relationship between the Histogram Viewer and the Gradient Analyzer?**
A: The **Histogram Viewer** shows the overall brightness distribution and lets you compare different image versions side-by-side. The **Gradient Analyzer** is a deep-dive tool specifically for background gradient diagnostics with 9 specialized visualization tabs. Use the Histogram Viewer to understand your data distribution; use the Gradient Analyzer to diagnose and fix gradient problems.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Image Advisor
- Svenesis Annotate Image
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
