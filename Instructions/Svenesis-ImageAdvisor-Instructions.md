# Svenesis Image Advisor — User Instructions

**Version 1.3.0** | Siril Python Script for Image Diagnostics & Workflow Planning

> *A "second opinion" diagnostic tool — analyzes your stacked image, identifies issues, and generates a prioritized processing workflow with concrete Siril commands.*

---

## Table of Contents

1. [What Is the Image Advisor?](#1-what-is-the-image-advisor)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [What Gets Analyzed](#6-what-gets-analyzed)
7. [Understanding the Report](#7-understanding-the-report)
8. [Severity Levels](#8-severity-levels)
9. [The Recommended Workflow](#9-the-recommended-workflow)
10. [Export Options](#10-export-options)
11. [Use Cases & Workflows](#11-use-cases--workflows)
12. [Smart Behaviors](#12-smart-behaviors)
13. [Tips & Best Practices](#13-tips--best-practices)
14. [Troubleshooting](#14-troubleshooting)
15. [FAQ](#15-faq)

---

## 1. What Is the Image Advisor?

The **Svenesis Image Advisor** is a Siril Python script that analyzes your stacked, linear (unprocessed) image and produces a prioritized list of recommended processing steps — complete with concrete Siril commands, suggested parameters, and reasoning for each recommendation.

Think of it as a **processing coach** sitting next to you. It combines:

- **Diagnostic analysis** — noise/SNR, gradients, star quality, calibration status, color balance, nebulosity, clipping, and more
- **Prioritized workflow** — tells you exactly what to do first, second, third, with specific Siril commands
- **Context-aware advice** — adjusts recommendations based on your image type (broadband, narrowband, mono, OSC), integration time, star quality, and what processing has already been done
- **Siril script export** — generates a ready-to-run `.ssf` script file with all recommended commands

The Image Advisor does **not** modify your image. It is purely diagnostic — it reads the image, analyzes it, and tells you what it found and what to do. You execute the steps yourself, keeping full control.

---

## 2. Background for Beginners

### The Processing Challenge

You've captured your subframes, calibrated them (darks, flats, biases), registered them, and stacked them. Now you have a single stacked image — and it looks... dark, grey, and unimpressive. That's normal! The image is in its **linear** state, meaning the pixel values haven't been transformed to reveal the faint detail hidden in the data.

The challenge is: **what do you do next?** Astrophotography processing involves many steps, and the order matters. Do the wrong thing first and you can permanently damage your data. Skip a step and you leave quality on the table.

Here's the typical linear processing workflow:

```
Crop borders → Remove gradients → Plate-solve → Color calibrate →
Remove green noise → Denoise → Deconvolve → Remove stars →
STRETCH → Fine-tune → Recompose stars → Export
```

Each step has specific tools, settings, and conditions. The Image Advisor automates the analysis and decision-making, telling you which steps your image needs and which it can skip.

### What Is Linear vs. Stretched Data?

This is the single most important concept in astrophotography processing:

| State | What It Means | What It Looks Like |
|-------|--------------|-------------------|
| **Linear** | Pixel values are proportional to the number of photons received | Very dark, grey image — faint objects invisible |
| **Stretched (non-linear)** | A mathematical transformation has been applied to reveal faint detail | Visible nebulae, galaxies, stars on dark background |

**The golden rule:** Do everything possible while the data is still linear. Gradient removal, color calibration, denoising, and deconvolution all work best on linear data. Once you stretch, many of these operations become less effective or can introduce artifacts.

The Image Advisor checks whether your image is linear by examining the FITS processing history for stretch commands (like `ght`, `autostretch`, `mtf`, `asinh`, `clahe`). If it finds any, it warns you.

### What Is SNR (Signal-to-Noise Ratio)?

**Signal** is the light from your target (nebula, galaxy, stars). **Noise** is random variation from photon statistics, sensor readout, thermal current, and sky background.

**SNR = signal ÷ noise.** Higher is better.

| SNR | Quality | What It Means |
|-----|---------|--------------|
| > 10 | Excellent | Rich data, aggressive processing possible, deconvolution works well |
| 5–10 | Good | Solid data, standard processing, moderate deconvolution |
| 2–5 | Noisy | Limited data, careful processing needed, skip deconvolution |
| < 2 | Photon-starved | Very faint target or short integration, heavy denoising needed |

The Image Advisor measures SNR using the **MAD (Median Absolute Deviation)** method, which is robust against outliers like stars and cosmic rays.

### What Is FWHM?

**FWHM (Full Width at Half Maximum)** measures how "fat" your stars are in pixels (or arcseconds if the image is plate-solved).

| FWHM | Quality | Typical Cause |
|------|---------|---------------|
| < 2" | Excellent | Great seeing, precise focus, good tracking |
| 2–4" | Good | Average conditions, acceptable for most targets |
| 4–6" | Soft | Poor seeing, slight defocus, or wind |
| > 6" | Very soft | Significant defocus, bad seeing, or optical issues |

Tight, round stars allow more aggressive deconvolution and produce sharper final images. The Image Advisor also checks for **elongation** (oval stars from tracking errors) and **field curvature** (stars fatter at edges than center).

### What Is Nebulosity Fraction?

The percentage of pixels in your image that contain extended faint emission (nebulae, galaxy arms) above the background noise floor. The Image Advisor uses this to decide:

- **Whether to recommend starless processing** (StarNet) — only useful if there's significant nebulosity
- **How to adjust gradient extraction** — more sample points in nebulosity-rich images to avoid fitting the nebula

### What Is Plate-Solving?

Plate-solving determines the exact sky coordinates of your image by matching the star pattern against a catalogue. It's important because:

- **SPCC (Spectrophotometric Color Calibration)** requires plate-solving to identify stars for color reference
- **FWHM can be measured in arcseconds** instead of just pixels, making the assessment resolution-independent
- **Geographic LP direction** can be computed from the WCS data

---

## 3. Prerequisites & Installation

### Requirements

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| **Siril** | 1.4.1+ | For full command support (denoise -mod=, etc.) |
| **sirilpy** | Bundled | Comes with Siril 1.4+ |
| **numpy** | Any recent | Auto-installed by the script |
| **PyQt6** | 6.x | Auto-installed by the script |

### Installation

1. Download `Svenesis-ImageAdvisor.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script automatically installs missing Python dependencies (`numpy`, `PyQt6`) on first run.

---

## 4. Getting Started

### Step 1: Load Your Stacked Image

Load your stacked FITS image in Siril. For best results:
- Use a **linear** (unstretched) image — the Advisor is designed for the linear processing stage
- Use a **calibrated and stacked** image (not a single subframe)
- Any type works: RGB broadband, mono, narrowband, dual-narrowband OSC

### Step 2: Run the Script

Go to **Processing → Scripts → Svenesis Image Advisor**.

The script opens its window and **immediately starts analyzing** — no button click needed. You'll see status updates as it works through three phases:

1. **Phase 1:** Collecting image data (pixel statistics, FITS headers, gradient analysis, star detection)
2. **Phase 2:** Running analysis modules (18+ diagnostic checks)
3. **Phase 3:** Generating the report

The whole analysis typically takes 5–15 seconds.

### Step 3: Read the Report

The right panel fills with a comprehensive HTML report containing:
- Image summary and key statistics
- Processing state (linear? calibrated?)
- Per-channel noise table (for color images)
- Background heatmap (8×8 gradient visualization)
- Prioritized findings with severity levels
- Recommended workflow with Siril commands
- Post-processing roadmap (stretching and beyond)

### Step 4: Follow the Workflow

The recommended workflow section lists your processing steps in priority order. Each step includes:
- **What** to do and **why**
- **Severity** (how important it is)
- **The exact Siril command** to run

Work through the steps top to bottom. After making changes, click **"Re-Analyse"** to refresh the assessment.

### Step 5: Export (Optional)

- **Export Report (.txt)** — saves the full report as a text file for documentation
- **Export Script (.ssf)** — generates a Siril script file with all recommended commands, ready to run

---

## 5. The User Interface

### Left Panel (Control Panel)

The left side (340px wide) contains:

#### Title
"Svenesis Image Advisor 1.3.0" in blue.

#### Status Group
- **Status label** — shows the current analysis phase ("Phase 1: Collecting image data...", "Analysis complete.", etc.)
- **Progress bar** — animated during analysis, filled to 100% when done

#### Image Info Group
After analysis, shows a quick summary:
- Image type (e.g., "OSC Broadband (RGB)")
- Dimensions (e.g., "4656 × 3520 px")
- Frame count and star count
- Number of recommended processing steps

#### Actions Group
- **Re-Analyse** — re-runs the full analysis on the current Siril image (useful after you've applied a processing step)
- **Export Report (.txt)** — saves the report as plain text
- **Export Script (.ssf)** — generates a Siril script with recommended commands

#### Bottom Buttons
- **Buy me a Coffee** — support link
- **Help** — opens a detailed help dialog with 8 sections
- **Close** — exits the script

### Right Panel (Report)

A read-only HTML display containing the full analysis report. Scrollable, with color-coded sections, tables, and the background heatmap. You can select and copy text from the report.

---

## 6. What Gets Analyzed

The Image Advisor runs 18+ diagnostic modules across every aspect of your image. Here's what it checks:

### Image Identity
| Check | What It Measures |
|-------|-----------------|
| **Image type** | OSC broadband, mono, narrowband, dual-narrowband, luminance — detected from filter name, Bayer pattern, and channel count |
| **Dimensions** | Width, height, channels, bit depth — flags non-astronomical sizes (phone/screen resolutions) |
| **Stacking info** | Frame count (STACKCNT), total integration time (LIVETIME), per-sub exposure (EXPOSURE) |

### Processing State
| Check | What It Measures |
|-------|-----------------|
| **Linear state** | Scans FITS history for stretch commands (ght, autostretch, mtf, asinh, clahe, etc.) |
| **Calibration** | Detects darks, flats, biases from FITS history keywords — distinguishes "not applied" from "unknown" when no history exists |
| **Plate-solve** | Checks for WCS keywords or `pltsolvd` flag in FITS header |

### Background & Gradients
| Check | What It Measures |
|-------|-----------------|
| **Gradient spread** | Divides image into 8×8 tiles, sigma-clips each tile, computes spread of median values as percentage |
| **Gradient pattern** | Classifies as: vignetting (dark corners, bright center), linear LP (one side brighter), corner amp glow (one corner bright), or no pattern |
| **Stacking borders** | Scans edges for near-zero pixel rows/columns from dithered/rotated stacking |

### Signal Quality
| Check | What It Measures |
|-------|-----------------|
| **Noise / SNR** | MAD-based noise estimate from darkest 25% of pixels; SNR = median / noise |
| **Dynamic range** | Peak (99.5th percentile) to noise floor ratio, expressed in binary stops |
| **Clipping** | Percentage of pixels near black (< 0.001) and near white (> 0.999) |

### Color
| Check | What It Measures |
|-------|-----------------|
| **Channel balance** | R/G and B/G median ratios — flags strong imbalance |
| **Per-channel noise** | Individual R, G, B noise levels — highlights the noisiest channel |
| **Green residual** | Advisory to check for green noise after SPCC calibration |

### Stars
| Check | What It Measures |
|-------|-----------------|
| **Star count** | Number of detected stars (via Siril's findstar) |
| **FWHM** | Average star width in pixels (and arcseconds if plate-solved) |
| **Elongation** | Star roundness — mean fwhmmax/fwhmmin ratio (1.0 = perfectly round) |
| **Field variation** | FWHM and elongation at center vs. edges — detects coma, tilt, field curvature |
| **Saturated stars** | Count of stars with clipped/saturated cores |

### Content Analysis
| Check | What It Measures |
|-------|-----------------|
| **Nebulosity fraction** | Percentage of pixels with extended emission above the noise floor |
| **Deconvolution suitability** | SNR threshold check — is the data clean enough for Richardson-Lucy? |
| **Sanity check** | Flags extreme clipping with no signal content (broken stacks, phone photos, screenshots) |

---

## 7. Understanding the Report

The HTML report in the right panel contains 8 sections:

### Image Summary

A table showing the basics: image type, size, channels, stack count, exposure, resolution, filter, and plate-solve status.

### Key Statistics

The core metrics at a glance:

| Metric | Example | What It Tells You |
|--------|---------|------------------|
| SNR Estimate (MAD) | 8.3 | How clean your signal is (higher = better) |
| Background Noise (σ) | 0.000142 | Absolute noise floor |
| Gradient Spread | 4.2% | How uneven the background is |
| Dynamic Range | 7.8 stops | How much signal range you have to work with |
| Nebulosity | 12.3% | How much extended emission is present |
| Stars Detected | 2,847 | Star count from findstar |
| Mean FWHM | 3.2 px (2.4") | Star sharpness (smaller = sharper) |
| Mean Elongation | 1.08 | Star roundness (1.0 = perfect) |

### Processing State

Shows whether the image is linear (green "Linear (good)") or stretched (red "STRETCHED" with the detected commands). Also shows calibration status — darks, flats, and biases each marked with a green checkmark or orange cross. If no processing history exists in the FITS header, it shows "Unknown" instead of false negatives.

### Per-Channel Statistics (Color Images Only)

A table showing each R, G, B channel's median value, noise level (σ), and relative noise (×). The noisiest channel is highlighted in bold orange — this is often the blue channel in broadband imaging.

### Background Heatmap

An 8×8 ASCII grid showing the relative brightness of 64 tiles across the image. Darker tiles appear as dots or lower characters; brighter tiles appear as higher characters. Below the grid, the gradient **pattern classification** is shown:

| Pattern | What It Means |
|---------|--------------|
| **Vignetting** | Centre brighter than all four corners — residual optical vignetting |
| **Linear** | One side brighter than the opposite — light pollution or moonlight |
| **Corner (amp glow)** | One corner significantly brighter — camera amplifier glow |
| *(no pattern)* | No dominant gradient structure detected |

### Findings

The heart of the report. Each finding shows:
- **Severity icon** — [ℹ] info, [✓] minor, [⚠] moderate, [✗] critical
- **Color-coded severity** — blue, green, orange, or red
- **Category** — what aspect was analyzed (gradient, noise, stars, etc.)
- **Finding** — what was detected, with specific numbers
- **Recommendation** — what to do about it
- **Siril command** — the exact command to run (if applicable)

### Recommended Workflow

A numbered, priority-sorted list of actionable steps. This is the "do this first, then this, then this" guide. Each step has a clear description and the Siril command.

### Post-Processing Roadmap

After completing the linear-stage workflow and stretching, this section outlines the remaining steps:
- **Stretching** — tool recommendation (VeraLux HMS) with dynamic range advice and background pedestal warnings
- **Fine-tuning** — contrast, color saturation, local detail (Revela, Curves, Vectra)
- **Star Recomposition** — StarComposer (only if starless processing was recommended)
- **Signature & Export** — final TIFF/PNG/JPEG

---

## 8. Severity Levels

Every finding is tagged with one of four severity levels:

| Icon | Level | Color | Meaning |
|------|-------|-------|---------|
| ℹ | **Info** | Blue | Purely informational — no action required |
| ✓ | **Minor** | Green | Optional improvement — worth doing but not critical |
| ⚠ | **Moderate** | Orange | Recommended action — significant quality improvement |
| ✗ | **Critical** | Red | Serious issue — must address before proceeding |

**How severity maps to action:**

- **Info:** Read and understand, but no processing step needed. Example: "Stars detected: 2,847" or "Linear data confirmed."
- **Minor:** An optional step that improves quality. Example: "Green noise may be visible after SPCC — check and apply removal if needed."
- **Moderate:** A recommended step you should do. Example: "Gradient spread 8.2% — run subsky 2 for background extraction."
- **Critical:** A problem that must be fixed. Example: "Image is already stretched — analysis is less accurate, ideally use the unstretched original."

---

## 9. The Recommended Workflow

The Image Advisor generates a prioritized workflow based on what it finds. The priority order follows the golden rule: **do everything possible in the linear stage.**

### Linear Processing Order

| Priority | Step | Condition | Typical Command |
|----------|------|-----------|-----------------|
| 1 | **Crop stacking borders** | Dark edges detected | `boxselect X Y W H` then `crop` |
| 2 | **Background extraction** | Gradient spread > 2% | `subsky 1` (mild) / `subsky 2` (moderate) / `subsky 3` (severe) |
| 3 | **Plate-solve** | Not yet plate-solved | `platesolve` |
| 4 | **Color calibration (SPCC)** | Color image, plate-solved | `spcc` |
| 5 | **Green noise removal** | After SPCC on color images | Check and apply if visible |
| 6 | **Denoising** | Always (adjusted by SNR) | `denoise -mod=0.8` / `denoise -mod=1.0 -vst` |
| 7 | **Deconvolution** | SNR > 5 and stars detected | `makepsf manual -gaussian -fwhm=X` then `rl -loadpsf=psf.fits -iters=N` |
| 8 | **Starless extraction** | Nebulosity > 1% | `starnet [-stretch]` |

### Context-Aware Adjustments

The workflow adapts to your specific image:

- **Gradient + nebulosity:** `subsky` gets `-samples=25` when nebulosity > 5% (more sample points avoid fitting the nebula as background)
- **Denoise before deconvolution:** Denoising is promoted in priority when deconvolution is recommended (cleaner input = better deconvolution)
- **StarNet stretch flag:** Uses `-stretch` only on linear images (avoids double-stretching)
- **Deconvolution iterations:** 10 for SNR > 10, 5 for marginal SNR (5–10)
- **Integration-aware noise advice:** Different messaging for short vs. long integrations ("more integration time would help" vs. "long integration but noisy — faint target")
- **Narrowband nebulosity:** Uses a 3σ detection floor instead of 5σ for broadband, because narrowband emission is more diffuse

### Suppressed Workflow

If the image fails sanity checks (e.g., extreme black clipping with no detectable content), the script **suppresses all processing recommendations** and shows only the warning. This prevents suggesting complex processing steps on a broken or non-astronomical image.

---

## 10. Export Options

### Export Report (.txt)

Saves the full analysis report as a plain-text file. Contains all the same information as the HTML report, but formatted for text editors, forum posts, or email.

- **Default filename:** `image_advisor_report.txt`
- **Encoding:** UTF-8
- **Sections:** Image summary, key statistics, processing state, per-channel stats, heatmap, findings, workflow, roadmap

### Export Script (.ssf)

Generates a Siril Script File containing all recommended commands in the correct order.

**Features:**
- **Auto-generated header** with script version and timestamp
- **`requires 1.4.1` directive** (ensures compatible Siril version)
- **Save checkpoints** between major steps (e.g., `save image_after_crop.fits`)
- **Correct command syntax** for Siril 1.4.x

**Example generated script:**
```
# Svenesis Image Advisor — Generated Workflow
# Generated by v1.3.0
requires 1.4.1

# Step 1: Crop stacking borders
boxselect 12 8 4632 3504
crop
save image_crop.fits

# Step 2: Background extraction
subsky 2 -samples=15
save image_subsky.fits

# Step 3: Plate-solve
platesolve
save image_platesolve.fits

# Step 4: Color calibration
spcc
save image_spcc.fits

# Step 5: Denoise
denoise -mod=0.8
save image_denoise.fits

# Step 6: Deconvolution
makepsf manual -gaussian -fwhm=3.2
rl -loadpsf=psf.fits -iters=10
save image_decon.fits

# Step 7: Star removal
starnet -stretch
save image_starless.fits
```

**Important:** The script is a starting point. Review each step before running — some commands may need parameter tweaking based on visual inspection.

---

## 11. Use Cases & Workflows

### Use Case 1: First-Time Processor (5 minutes)

**Scenario:** You've just stacked your first image in Siril and have no idea what to do next.

**Workflow:**
1. Load the stacked image in Siril
2. Run the Image Advisor (**Processing → Scripts → Svenesis Image Advisor**)
3. Read the **Image Summary** to understand what you're working with
4. Read the **Processing State** — confirm it says "Linear (good)"
5. Follow the **Recommended Workflow** top to bottom, running each Siril command in the console
6. After the linear steps, follow the **Post-Processing Roadmap** for stretching and fine-tuning

The Advisor replaces hours of tutorial-watching with concrete, image-specific guidance.

### Use Case 2: Quick Health Check (2 minutes)

**Scenario:** You've processed many images before, but want a quick assessment of a new stack.

**Workflow:**
1. Load the stacked image
2. Run the Image Advisor
3. Scan the **Key Statistics** table — check SNR, gradient, FWHM, nebulosity
4. Check the **severity icons** in Findings — anything orange or red needs attention
5. Note any **critical warnings** (stretched data, missing calibration, sanity issues)
6. Proceed with your usual workflow, incorporating any flags

### Use Case 3: Diagnosing Soft Stars

**Scenario:** Your final image has bloated, soft stars and you want to understand why.

**Workflow:**
1. Load the stacked (linear) image
2. Run the Image Advisor
3. Check the **Stars** findings:
   - **Mean FWHM** — is it above 4" (arcseconds) or 5 px? That's soft.
   - **Centre vs. edge FWHM** — if edges are much worse, you have field curvature or tilt
   - **Elongation** — if > 1.3, stars are oval (tracking issue or coma)
   - **Elongation spatial** — if edges are worse than center, it's optical (coma/tilt), not tracking
4. The Advisor tells you what's fixable in processing (deconvolution can help with mild softness) and what isn't (field curvature needs mechanical adjustment)

### Use Case 4: Narrowband Image Processing

**Scenario:** You've stacked an Ha (Hydrogen-alpha) narrowband image and need processing guidance.

**Workflow:**
1. Load the narrowband stack
2. Run the Image Advisor — it automatically detects the filter from the FITS header
3. The report shows "Narrowband (Mono)" or "Narrowband (Colour)" as the image type
4. Adjustments the Advisor makes for narrowband:
   - **Nebulosity detection** uses a 3σ floor (more sensitive than broadband's 5σ)
   - **Color calibration (SPCC)** is skipped for mono narrowband
   - **Gradient extraction** accounts for the typically lower gradient spread
5. Follow the recommended workflow — it's tailored for narrowband data

### Use Case 5: Checking Calibration Quality

**Scenario:** You want to verify that your darks, flats, and biases were properly applied.

**Workflow:**
1. Load the stacked image
2. Run the Image Advisor
3. Check the **Processing State** section:
   - **Darks ✓ / ✗** — were dark frames applied?
   - **Flats ✓ / ✗** — were flat frames applied?
   - **Bias ✓ / ✗** — were bias/offset frames applied?
   - **Unknown** — if no processing history exists in the FITS header (common with some stacking tools)
4. If flats are missing, the **gradient analysis** will likely show vignetting
5. If darks are missing, noise may be elevated and amp glow may appear in the heatmap

### Use Case 6: Is My Integration Time Enough?

**Scenario:** You've stacked 2 hours of data and wonder if you need more.

**Workflow:**
1. Load the stacked image
2. Run the Image Advisor
3. Check the **SNR** in Key Statistics:
   - **SNR > 10:** Excellent — you have plenty of data
   - **SNR 5–10:** Good — standard processing possible, more data always helps
   - **SNR 2–5:** Noisy — more integration time would significantly improve the result
   - **SNR < 2:** Photon-starved — this target needs much more integration time
4. The noise finding contextualizes the result against your total integration time:
   - Short integration + low SNR → "More integration time would help"
   - Long integration + low SNR → "This is a faint target — long exposure but still noisy"

### Use Case 7: Generating a Processing Script

**Scenario:** You want to run the recommended processing steps as an automated Siril script.

**Workflow:**
1. Load the stacked image
2. Run the Image Advisor
3. Review the recommended workflow in the report
4. Click **"Export Script (.ssf)"**
5. Save the file (default: `image_advisor_workflow.ssf`)
6. In Siril, run the script via **Processing → Scripts** or the command line
7. The script includes save checkpoints between major steps, so you can inspect intermediate results

**Note:** Always review the generated script before running. Some steps may need parameter adjustment based on visual inspection (e.g., gradient extraction degree, denoise modulation).

### Use Case 8: Forum Help Request

**Scenario:** You're stuck on processing and want to ask for help on an astrophotography forum.

**Workflow:**
1. Load the stacked image
2. Run the Image Advisor
3. Click **"Export Report (.txt)"**
4. Paste the report into your forum post
5. Forum members can see exactly what the Advisor found: SNR, gradient, star quality, calibration status, and recommended workflow
6. This gives helpers a complete diagnostic picture without them having to download your image

### Use Case 9: Before/After Processing Check

**Scenario:** You've applied background extraction and want to verify it worked.

**Workflow:**
1. After applying `subsky`, click **"Re-Analyse"**
2. Compare the new **Gradient Spread** with what it was before
3. Check if the gradient finding severity dropped (e.g., from "moderate" to "info")
4. The heatmap should show a more uniform pattern
5. Continue to the next step in the workflow

---

## 12. Smart Behaviors

The Image Advisor includes several intelligent adaptations that go beyond simple threshold checks:

### Nebulosity-Aware Gradient Extraction

When the Advisor recommends `subsky` for gradient removal, it checks the nebulosity fraction:
- **Nebulosity > 5%:** Adds `-samples=25` (more sample points help the algorithm avoid fitting the nebula as part of the background)
- **Nebulosity 1–5%:** Adds `-samples=15`
- **Nebulosity < 1%:** Default sample count

### Denoise Promotion Before Deconvolution

If deconvolution is recommended (SNR > 5, stars detected), the denoising step is promoted in priority. Deconvolution amplifies noise, so denoising first produces better results.

### StarNet Stretch Awareness

When recommending StarNet for star removal:
- **Linear image:** Uses `starnet -stretch` (StarNet needs stretched data to work properly)
- **Already stretched:** Uses `starnet` without `-stretch` (avoids double-stretching)

### Integration-Time Context

The noise advice adapts to how much data you have:
- **SNR ≤ 5 + < 1 hour integration:** "More integration time would help" — you may not have enough data yet
- **SNR ≤ 5 + > 4 hours integration:** "Long integration but still noisy — this is likely a faint target" — the issue is target brightness, not integration time

### Narrowband Nebulosity Detection

For narrowband filters (Ha, OIII, SII), the nebulosity detection floor drops from 5σ to 3σ above background. Narrowband emission is often more diffuse and fainter relative to the noise, so a lower threshold catches it correctly.

### Background Pedestal Warning

During stretch recommendations, the Advisor checks the background median:
- **> 15% of full range:** Strong warning to set the black point carefully
- **> 8% of full range:** Mild warning about elevated background
- This prevents the common mistake of stretching with a high background, resulting in a washed-out grey sky

### Workflow Suppression

If the image fails basic sanity checks (extreme black clipping with no stars, no signal, and no nebulosity), the Advisor suppresses all processing recommendations. Instead, it shows only the critical warning explaining what might be wrong (screenshot, phone photo, broken stack, heavily masked export).

---

## 13. Tips & Best Practices

### When to Run the Advisor

1. **Run it on your linear stack, before any processing.** This is the ideal point — the Advisor is designed for this moment.

2. **Run it after each major step.** Click "Re-Analyse" after gradient extraction, after color calibration, etc. to verify each step worked.

3. **Run it on individual subframes** if you want to check a single frame's quality (though the Blink Comparator is better for multi-frame comparison).

### Reading the Report Efficiently

4. **Start with the severity icons.** Scan for orange [⚠] and red [✗] — those are the issues that matter most.

5. **Trust the workflow order.** The priority system is designed around the golden rule (linear first). Don't skip ahead to deconvolution before extracting gradients.

6. **Pay attention to "already stretched" warnings.** If you accidentally analyze a stretched image, the gradient, noise, and other measurements may be inaccurate. Re-do the analysis on the linear version.

### Practical Workflow Tips

7. **Use the exported .ssf script as a starting point**, not as gospel. Review each command and adjust parameters if your visual inspection suggests different settings.

8. **The heatmap reveals gradient patterns at a glance.** A bowl shape = vignetting. A tilt = LP. One hot corner = amp glow. This tells you what kind of extraction to apply.

9. **Per-channel noise table shows which channel limits your image.** In broadband imaging, blue is often noisiest. In narrowband, the filter and sensor QE determine which is worst.

10. **Check calibration status early.** If darks/flats/biases show as missing or unknown, fix your calibration before spending time on processing.

11. **Don't skip plate-solving.** Many downstream steps (SPCC, arcsecond FWHM, geographic LP direction in other tools) require it. The Advisor reminds you.

12. **The nebulosity percentage helps decide starless processing.** If it's < 1%, StarNet won't add much value — you're imaging a star field. If > 5%, starless processing is strongly recommended.

---

## 14. Troubleshooting

### "No image loaded" Error

**Cause:** No image is open in Siril.
**Fix:** Load a FITS image before running the script.

### "Connection timed out" Error

**Cause:** The sirilpy connection to Siril timed out, usually because Siril is busy.
**Fix:** Wait for Siril to finish any current operation, then try again.

### Analysis Takes a Long Time

**Cause:** Star detection (findstar) on very large images or images with thousands of stars can be slow.
**Fix:** This is normal — the progress bar will show activity. Star detection is the slowest phase.

### "Already stretched" Warning When Image Is Linear

**Cause:** The script detected stretch-related keywords in the FITS processing history. Some software writes history entries that trigger false positives.
**Fix:** If you're certain the image is linear, you can ignore this warning. The analysis is still valid — the warning is a precaution.

### "Unknown" Calibration Status

**Cause:** The FITS file has no processing history entries. This happens with some stacking software or when history is not written to headers.
**Fix:** This is not an error — it means the Advisor can't verify calibration from the file. If you know you applied darks/flats/biases, proceed normally.

### Report Shows No Stars

**Cause:** Star detection failed — possible reasons: the image is too dark, heavily clipped, or not astronomical content.
**Fix:** Check that the image is loaded correctly in Siril. If it's a narrowband image with very few stars, this can be normal.

### Exported Script Fails in Siril

**Cause:** The script requires Siril 1.4.1+ (specified by the `requires` directive). Older versions may not support all commands.
**Fix:** Update Siril to 1.4.1 or newer.

### "Extreme Black Clipping" Warning

**Cause:** More than 50% of pixels are near zero, and no stars or signal were detected. The Advisor suspects this isn't a normal astronomical image.
**Fix:** Check if:
- The image is a screenshot or phone photo (not a FITS stack)
- The stacking produced a mostly empty result (alignment issue)
- The image is heavily cropped with large black borders
- If the image is legitimate but unusual, the Advisor may be overly cautious — the linear background of a well-calibrated stack sits near zero naturally (but should still have detectable stars)

---

## 15. FAQ

**Q: Does the Image Advisor modify my image?**
A: No — it is purely diagnostic. It reads the image, analyzes it, and generates recommendations. You execute the processing steps yourself using Siril's console or the exported script.

**Q: Should I run this before or after stacking?**
A: After stacking. The Advisor is designed for stacked images in their linear state. For individual subframe quality assessment, use the Svenesis Blink Comparator instead.

**Q: Can I use this on stretched images?**
A: You can, but the results will be less accurate. The Advisor will detect the stretched state and warn you. Gradient, noise, and dynamic range measurements are most meaningful on linear data.

**Q: What's the difference between this and the Gradient Analyzer?**
A: The **Image Advisor** is a broad diagnostic tool that checks everything (noise, gradients, stars, calibration, color, etc.) and generates a complete processing workflow. The **Gradient Analyzer** is a deep-dive specialist focused exclusively on background gradients, with 9 visualization tabs, 30+ gradient-specific metrics, and detailed gradient extraction guidance. Use the Advisor for an overall assessment; use the Gradient Analyzer when you need detailed gradient diagnostics.

**Q: Why does it recommend plate-solving? I just want to process my image.**
A: Plate-solving unlocks SPCC (accurate color calibration) and allows FWHM to be measured in arcseconds (resolution-independent). It takes seconds and significantly improves downstream processing. The Advisor strongly recommends it.

**Q: Can I run the exported .ssf script automatically?**
A: Yes — in Siril, go to **Processing → Scripts** and select the exported script, or use the command line. However, review the script first. Some steps (like gradient extraction degree or denoise modulation) may benefit from visual inspection and parameter adjustment.

**Q: What does "nebulosity fraction" actually measure?**
A: It counts pixels that are above the background noise floor but below the star brightness threshold. These intermediate-brightness pixels represent extended emission — nebulae, galaxy arms, reflection nebulae. A high percentage (> 5%) means significant extended objects; a low percentage (< 1%) means you're imaging mostly stars.

**Q: Why is the blue channel always the noisiest?**
A: In most camera sensors, the blue photosites have lower quantum efficiency — they convert fewer photons into signal. Combined with the fact that night sky background is often warmer (reddish from LP), blue receives the least signal and the most relative noise. This is normal and expected.

**Q: Can I run this on mono narrowband data?**
A: Yes. The Advisor automatically detects mono narrowband from the FITS filter keyword. It adjusts the nebulosity threshold, skips color-specific recommendations (SPCC, green removal), and tailors the workflow for narrowband processing.

**Q: What Siril version do I need?**
A: Siril 1.4.1 or newer for full functionality. The exported scripts include a `requires 1.4.1` directive. Older versions may not support commands like `denoise -mod=` or newer `rl` syntax.

**Q: How accurate is the SNR estimate?**
A: The MAD-based SNR is robust and reliable for comparing images, but it's an estimate — it measures background SNR, not target SNR. The actual signal from your target object (nebula, galaxy) may be stronger or weaker than the background-based measurement suggests. Use it as a relative guide, not an absolute number.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
