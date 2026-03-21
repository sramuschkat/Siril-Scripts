# Svenesis Siril Scripts

A collection of Python scripts for [Siril](https://www.siril.org/) (astronomical image processing).

## Author and links

- **Author:** Sven Ramuschkat — [www.svenesis.org](https://www.svenesis.org)
- **Repository:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)

## License

GPL-3.0-or-later

## Scripts

| Script | Description |
|--------|-------------|
| [Gradient Analyzer](#gradient-analyzer) | Analyze background gradients with heatmaps, diagnostics, and tool recommendations. |
| [Image Advisor](#image-advisor) | Analyze a stacked linear image and get a prioritized processing workflow with concrete Siril commands. |
| [Multiple Histogram Viewer](#multiple-histogram-viewer) | View linear and stretched images with RGB histograms, 3D surface plots, and detailed statistics. |
| [Script Security Scanner](#script-security-scanner) | Scan Siril Python scripts for malicious patterns across 10 threat categories. |

---

## Gradient Analyzer

**File:** `GradientAnalyzer.py` (v1.8.4)

Reads the current image from Siril, divides it into a configurable grid of tiles, computes sigma-clipped median background levels per tile, and renders a color-coded heatmap. It helps you assess background gradients (e.g. from light pollution), decide whether background extraction is needed, and choose the right tool and parameters for the job.

### Screenshots

![Gradient Analyzer — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/GradientAnalyzer-1.jpg)

*Main window: heatmap with sample point guidance, 3D surface view, gradient strength gauge, and quadrant analysis. Nine visualization tabs with context-sensitive descriptions.*

### Features

#### Beginner-friendly UI

- **"What is a gradient?" introduction:** Getting Started tab explains gradients with a visual analogy and common causes (light pollution, vignetting, sensor artifacts) before any technical details.
- **Beginner Glossary:** Technical Reference tab includes 25+ plain-language definitions (gradient, flat/dark/bias frames, linear/stretched, polynomial degree, R², FWHM, SNR, tool names).
- **Self-explaining action plan:** Each step explains *what the term means*, *why it matters*, and *how to do it in Siril* (including menu paths and Console instructions).
- **Tiered Analysis Results:** Summary & Actions tab with color-coded verdict, plain-English explanation, and prioritized action plan. Detailed Metrics tab with inline jargon explanations. Before/After delta tab when re-analyzing.
- **Tiered Recommendations:** Quick Guide tab with styled, categorized suggestions (critical issues, tools, workflow). Full Details tab with raw diagnostic output.
- **Organized Help dialog:** Six tabs — Getting Started, Tabs, Tools, Options, Warnings, Reference — with expanded beginner-friendly explanations throughout.
- **Tool descriptions with workflow:** Each tool (AutoBGE, subsky, GraXpert, VeraLux Nox) includes what it does, when to use it, how to install/run it, and pros/cons.
- **Contextual tooltips:** Every checkbox, gauge, and widget explains *why* you'd use it, not just what it does.
- **Single Analyze button (F5):** Always loads the current Siril image and runs the full analysis. No separate Refresh button needed.
- **Compact Siril log:** Only essential information (strength, assessment, critical warnings) is logged to the Siril console. Full details are in the Analysis Results and Recommendations dialogs.
- **Context-sensitive tab descriptions:** Plain-language descriptions above the visualization area with "what to look for" guidance.

#### Analysis & diagnostics

- **Configurable grid:** 4–64 rows/cols with iterative sigma-clipping (1.5–4.0σ, sample std) to exclude stars and bright objects.
- **Gradient metrics:** Robust P95-P5 percentile strength (%), brightest-side direction, uniformity, and confidence indicator (P95-P5 SNR-based). Resists outlier tiles from hotspots and artifacts.
- **Visual strength gauge:** Color-coded severity bar (green → yellow → orange → red) with configurable threshold presets (Broadband 1.5/4/12%, Narrowband 0.8/2.5/6%, Fast optics 3/6/16%).
- **Quadrant analysis:** NW/NE/SW/SE median values with brightest/darkest highlighting.
- **Gradient complexity:** Polynomial fits (degree 1/2/3) with R² comparison to determine optimal subsky degree.
- **Vignetting detection:** Radial vs. linear model fitting and edge-to-center ratio; symmetry analysis for flat calibration quality.
- **Extended object detection:** Flags tiles containing nebulae/galaxies that could bias the gradient fit.
- **Mosaic panel boundary detection:** Identifies sharp linear discontinuities from stitched panels.
- **Hotspot detection:** Outlier tiles (satellite trails, artifacts) flagged at > 3σ from neighbors.
- **Residual pattern detection:** Moran's I spatial autocorrelation to check if polynomial degree is sufficient.
- **Improvement prediction:** Estimates post-extraction gradient strength from P95-P5 of model residuals (consistent with main metric).
- **Light pollution color:** Characterizes LP type from per-channel gradient strengths (sodium, LED, mercury, broadband) with 1.5x dominance threshold to avoid OSC false positives.
- **Linear data detection:** Uses median level and mean/median ratio (skewness) to distinguish stretched data from linear narrowband/nebula images.
- **Star density warning:** Flags dense star fields that may bias background estimates.
- **Dew/frost detection:** Cross-correlates radial FWHM increase with center brightness for corrector plate dew detection.
- **Amplifier glow detection:** Detects exponential corner brightness profile characteristic of CCD/CMOS amp glow.
- **Banding/sensor bias detection:** FFT-based detection of periodic row/column patterns from sensor readout artifacts.
- **Normalization detection:** Warns when background-normalized data may underestimate true gradient (requires 2+ evidence pieces to avoid false positives).
- **FITS calibration check:** Reads FLATCOR/CALSTAT/DARKCOR from FITS headers to verify flat/dark/bias calibration was applied.
- **Geographic LP direction:** Converts gradient direction to real-world compass bearing via WCS rotation.
- **Photometric sky brightness:** Rough mag/arcsec² and Bortle class estimate from SPCC-calibrated images (approximate — uses assumed zeropoint, not a substitute for SQM measurements).
- **Cos^4 vignetting correction:** Separates natural optical falloff from true gradients, especially for fast optics (f/2–f/4).
- **FWHM/eccentricity map:** Star shape variation across the field with sensor tilt and field curvature detection. Minimum 1.5 px FWHM filter rejects hot pixels.

#### Visualizations (9 tabs)

- **2D heatmap & 3D surface:** Color-coded tile map with optional gradient direction arrow overlay, plus interactive 3D surface view. Colorblind-friendly colormap option (cividis).
- **Gradient profiles:** Horizontal and vertical cross-section plots showing where the gradient ramps across the image.
- **Tile distribution histogram:** Background value distribution — tight peak = uniform, broad/bimodal = gradient.
- **Per-channel (RGB) analysis:** Separate heatmaps per channel for detecting chromaticity in light pollution. Auto-disabled for mono images.
- **Background model preview:** Fitted polynomial surface (what subsky would subtract) and residuals.
- **Gradient magnitude map:** Rate-of-change visualization highlighting the steepest gradient transitions.
- **Subtraction preview:** Side-by-side before/after comparison of gradient removal at full pixel resolution.
- **FWHM / Eccentricity map:** Star shape metrics across the field.
- **Residual/exclusion mask:** Polynomial fit residuals alongside red-overlaid exclusion mask showing which tiles were excluded.

#### Tool recommendations

- **Actionable suggestions:** Suggests subsky (positional syntax `subsky degree samples`), AutoBGE, GraXpert, or VeraLux Nox based on gradient characteristics, with step-by-step workflow guidance.
- **Priority-based workflow:** Critical hardware/calibration issues are flagged before extraction recommendations.
- **Sample point guidance:** Heatmap overlay (green = good sample regions, red = avoid) to guide manual sample placement.

#### Export & persistence

- **Report export:** Plain-text analysis report derived from the same content as the Analysis Results and Recommendations dialogs — single source of truth.
- **PNG export:** Heatmap image with key metrics burned in (annotated export).
- **JSON sidecar:** Persist analysis results including tile medians array for cross-session comparison and overlay.
- **Persistent settings:** Grid size, sigma, checkboxes, colormap, and preset saved between sessions via QSettings.
- **Colorbar locking:** Consistent heatmap scale across re-analyses for meaningful visual comparison.
- **Keyboard shortcut:** F5 = Analyze (loads current image from Siril and runs analysis).

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, matplotlib, scipy (installed automatically via `s.ensure_installed`)
- Optional: astropy (for FITS header reading)

### Usage

1. Load an image in Siril (linear data recommended for best accuracy).
2. Run **Gradient Analyzer** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Adjust grid resolution and sigma in the left panel, select a threshold preset, then click **Analyze** (or press F5).
4. Review the heatmap, profiles, and metrics across the 9 tabs. Check the recommendations for the suggested tool and parameters.
5. Apply the recommended extraction in Siril, then click **Analyze** (F5) again to re-analyze and compare before/after.

---

## Image Advisor

**File:** `ImageAdvisor.py` (v1.3.0)

Analyses a stacked, linear FITS image loaded in Siril and generates a prioritised list of processing recommendations — including concrete Siril commands, suggested parameters, and reasoning. The script does **not** modify the image; it only diagnoses and advises. Think of it as a second opinion from an experienced astrophotographer before you start processing.

### Features

- **Full linear-stage workflow:** Recommendations follow the correct processing order — Crop → Background Extraction → Platesolving → SPCC → SCNR → Denoise → Deconvolution → Starless — with post-processing roadmap (stretch, fine-tune, star recomposition, export).
- **Linear state detection:** Warns if the image is already stretched (scans FITS HISTORY for GHT, autostretch, MTF, asinh, etc. using word-boundary matching to avoid false positives).
- **Calibration detection:** Checks HISTORY for dark/flat/bias calibration; shows "Unknown" when no history is present (e.g. stacked in another app) instead of false negatives.
- **Background gradient analysis:** 8×8 sigma-clipped tile grid with gradient spread percentage, colour-coded heatmap, and pattern classification:
  - **Vignetting** — corners dark, centre bright (needs flats, not subsky)
  - **Linear gradient** — one side bright (light pollution, subsky appropriate)
  - **Amp glow** — single corner bright (may need masking)
  - Pattern classification is suppressed when gradient is below the action threshold to avoid noise-fitting.
- **Calibration-aware gradient advice:** When flats are missing, gradient recommendations note that the gradient may be vignetting that subsky cannot fully correct.
- **Nebulosity-aware subsky:** Adds `-samples=15/25` to `subsky` commands when nebulosity is present, preventing polynomial overcorrection on nebula regions.
- **Noise & SNR estimation:** MAD-based noise on the darkest 25% of pixels; integration-time-aware advice (short integration → "add more subs" vs long integration → "faint target, denoise essential").
- **Smart denoise ordering:** Denoise is promoted to an actionable step before deconvolution even at high SNR, because Richardson-Lucy amplifies noise.
- **Narrowband-adjusted nebulosity:** Lower detection threshold (3σ) for narrowband/dual-narrowband images to catch diffuse low-contrast emission.
- **Image type classification:** Detects OSC Broadband, Mono, Narrowband, Luminance, and Dual-Narrowband OSC (L-eNhance, L-Extreme, NBZ, etc.) — adjusts SPCC and colour balance advice accordingly.
- **Star quality diagnostics:** FWHM (pixels and arcsec when plate-solved), elongation, centre-vs-edge spatial analysis, saturated star count, field curvature/coma detection. Soft stars and elongation are elevated as acquisition warnings near the top of the report.
- **Deconvolution guidance:** Richardson-Lucy recommendation with `makepsf manual -gaussian` + `rl -loadpsf=psf.fits` commands when SNR allows; suggests GUI deconvolution tool for interactive control.
- **Starless recommendation:** Only when nebulosity warrants it; `starnet -stretch` for linear images, bare `starnet` for already-stretched; autostretch preview tip included.
- **Dynamic range:** Usable DR in stops (peak / noise floor), informs stretch aggressiveness advice with background pedestal warnings for high-background images.
- **Clipping detection:** Black and white clipping percentages with cause suggestions. Extreme black clipping (>50%) with no detected signal triggers a critical warning and suppresses the workflow. Normal linear data (background near zero with real content) is correctly identified.
- **Crop detection:** Scans edges for stacking borders and generates `boxselect`/`crop` commands. Warns when scan limits are hit and borders may extend further.
- **Per-channel noise table:** R/G/B noise levels with noisiest channel highlighted. Notes when channels are unusually well-balanced (may already be colour-calibrated).
- **Image sanity checks:** Flags common phone/screen resolutions (1080×1920, etc.) as unusual for astro cameras. Suppresses processing workflow when the image fails basic sanity checks.
- **Verified Siril commands:** All command syntax verified against Siril 1.4.x binary (`subsky`, `denoise -mod=`, `makepsf manual -gaussian`, `rl -loadpsf= -iters=`, `starnet -stretch`, `platesolve`, `spcc`).
- **Script export (.ssf):** Generates an executable Siril script with save checkpoints after key stages (`requires 1.4.1`).
- **Report export (.txt):** Full plain-text report for archiving or sharing.
- **PyQt6 dark-themed GUI:** Left panel with controls and image info, right panel with scrollable HTML report including heatmap, per-channel table, findings, and workflow.

### Requirements

- Siril 1.4.1+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6 (installed automatically via `s.ensure_installed`)

### Usage

1. Load a stacked, linear FITS image in Siril.
2. Run **Image Advisor** from Siril: **Processing → Scripts** (or your Scripts menu).
3. The analysis runs automatically on launch. Review findings, statistics, heatmap, and the recommended workflow in the report panel.
4. Use **Re-Analyse** after making changes in Siril to get updated recommendations.
5. Use **Export Script (.ssf)** to save the workflow as a runnable Siril script, or **Export Report (.txt)** to save the full analysis.

---

## Multiple Histogram Viewer

**File:** `MultipleHistogramViewer.py` (v1.0.1)

Reads the current linear image from Siril (or a linear FITS file), applies a 2%–98% percentile autostretch for preview, and displays **Linear** and **Auto-Stretched** views side by side with combined RGB histograms or 3D surface plots. You can also load up to **2 additional stretched FITS** files for comparison. Compressed FITS (e.g. `.fz`, `.gz`) are supported.

### Screenshots

![Multiple Histogram Viewer — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-1.jpg)

*Main window: Linear and Auto-Stretched columns with histogram view, controls, and statistics.*

![Multiple Histogram Viewer — 3D and stats](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-2.jpg)

*3D surface plot option and statistical data (Size, Min/Max, Mean, Median, Std, IQR, MAD, P2/P98, Range, Near-black/Near-white).*

### Features

- **Image sources:** Current image from Siril, or load a linear FITS directly (including compressed `.fz`/`.gz`); up to 2 stretched FITS for comparison.
- **Views:** Histogram (2D) or 3D surface plot (X/Y = pixel position, Z = channel value).
- **Histogram:** Combined RGB and per-channel (R, G, B, L) with Normal or Logarithmic Y-axis; X-axis in ADU.
- **Statistics:** Size, Pixels, Min/Max, Mean, Median, Std, IQR, MAD, P2/P98 (2nd/98th percentile), Range (P2–P98), Near-black/Near-white %. Tooltip explains each metric; “(subsampled)” when stats are from a subset of pixels.
- **Enlarge Diagram:** Button under each histogram/3D plot opens a larger modal with the same diagram and a channel legend.
- **Help:** Modal help with author info, usage, and control descriptions.
- **Image zoom:** −, Fit, 1:1, + per column; after loading, all images are fitted to their windows.
- **Click on image:** Shows pixel R, G, B, I (ADU) in the stats area and a vertical line in the histogram.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, Pillow, astropy (installed automatically via `s.ensure_installed`)
- matplotlib (for 3D surface plot only)

### Usage

1. Load an image in Siril (or use **Load linear FITS...** in the script).
2. Run **Multiple Histogram Viewer** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Use the left panel for view type (Histogram / 3D), Data-Mode (Normal / Log), channels, and image/source options. Use **Enlarge Diagram** for a larger histogram or 3D view.

---

## Script Security Scanner

**File:** `Script-Security-Scanner.py` (v2.0.0)

Scans all Python scripts in your configured Siril script folders for potentially dangerous patterns across **10 threat categories**. Siril scripts run with full user-level OS permissions, so a malicious script can do virtually anything on your machine. This tool gives you a first-pass analysis before you run any script you did not write yourself.

### ⚠️ A word of caution before you scan

Siril Python scripts are powerful — and that power cuts both ways. A script can do **virtually anything your user account can do** on this machine: delete files and folders, download and execute additional programs, exfiltrate data, modify system settings … everything you can imagine a bad actor might want to do.

We are a friendly and welcoming astronomy community — but *you never truly know* where a script came from or who really wrote it. **Be careful about where you load scripts from.**

This tool gives you an impression of what a script is doing under the hood — potentially dangerous calls, obfuscated code, network access, file deletions, and more. It is a genuine help for spotting suspicious behaviour.

**However:** this is a cat-and-mouse game (as we say in German: *„Hase und Igel"* — hare and hedgehog). A determined bad actor who knows this scanner exists will adapt their script to avoid triggering the rules. **No automated tool can give you a 100 % guarantee.** Use your own judgement, only run scripts from sources you trust, and keep backups of your data.

Stay safe — and clear skies. 🌠

### ⚠️ Important — Why you should always do an AI check

This scanner performs **static analysis based on pattern matching** — it looks for known dangerous signatures in the source code. A clever attacker can evade these patterns. **ChatGPT and Claude understand code semantically**, like a human expert would, and can catch threats that pattern-based tools miss entirely. Paste the script into either AI with the prompt below — it takes 30 seconds and could save you from serious harm:

> *"You are an expert Python developer and cybersecurity specialist. Analyze the following Python script designed for the astrophotography program Siril. The script can access Siril data via its API but runs with full user-level OS permissions. Review the code for any malicious, harmful, or risky behavior — including but not limited to: file system access, network calls, data exfiltration, privilege escalation, obfuscated code, or destructive operations. Provide a security risk assessment and a clear recommendation on whether the script is safe to run."*

### Screenshots

![Script Security Scanner — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Security-Scanner-1.jpg)

*Main window: script directories, category selection, scan results grouped by file with severity indicators.*

### Features

- **10 threat categories:** File System — Destructive, File System — Data Theft, Network — Exfiltration, Network — Inbound/Backdoor, Code Execution — Escalation, Persistence, Obfuscation, Denial of Service, Social Engineering, Supply Chain.
- **Severity levels:** HIGH (red) — likely dangerous; MEDIUM (orange) — suspicious; LOW (blue) — informational.
- **Script directory discovery:** Automatically reads configured Siril script paths from the OS-specific Siril config file; falls back to well-known default locations.
- **Anti-evasion measures:** Multi-line continuation joins, triple-quoted string awareness, import alias expansion, comment-line filtering.
- **Detailed findings:** Click any finding for a full explanation; double-click to open the file in your default text editor.
- **Export:** Save a full plain-text report of all findings with explanations.
- **Startup warning:** Explains the limitations of static analysis and reminds you to also use AI-assisted review.
- **AI-assisted analysis tip:** Includes a ready-to-use prompt for ChatGPT or Claude to perform a semantic review that can catch threats pattern-based tools miss.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- PyQt6 (installed automatically when the script runs)

### Usage

1. Run **Script Security Scanner** from Siril: **Processing → Scripts** (or your Scripts menu).
2. The scanner auto-discovers your Siril script directories. Use **Add Directory…** or **Paste Paths** to add more.
3. Select the threat categories you want to scan, then press **Scan Now**.
4. Review findings grouped by file. Click a finding for details; double-click to open the file.
5. Use **Export Report…** to save the results as a plain-text file.
