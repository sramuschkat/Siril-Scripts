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
| [Multiple Histogram Viewer](#multiple-histogram-viewer) | View linear and stretched images with RGB histograms, 3D surface plots, and detailed statistics. |

---

## Multiple Histogram Viewer

**File:** `MultipleHistogramViewer.py`

Reads the current linear image from Siril (or a linear FITS file), applies a 2%–98% percentile autostretch for preview, and displays **Linear** and **Auto-Stretched** views side by side with combined RGB histograms or 3D surface plots. You can also load up to **2 additional stretched FITS** files for comparison.

### Screenshots

![Multiple Histogram Viewer — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-1.jpg)

*Main window: Linear and Auto-Stretched columns with histogram view, controls, and statistics.*

![Multiple Histogram Viewer — 3D and stats](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/MultipleHistogramViewer-2.jpg)

*3D surface plot option and statistical data (Size, Min/Max, Mean, Median, Std, IQR, MAD, P2/P98, Range, Near-black/Near-white).*

### Features

- **Image sources:** Current image from Siril, or load a linear FITS directly; up to 2 stretched FITS for comparison.
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
