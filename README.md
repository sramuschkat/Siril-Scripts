# Siril Histogram Viewer

A Siril Python script that reads the current linear image from Siril, applies autostretch, and displays a combined RGB histogram with normal/log modes, axis scaling, and a "Fit Histogram" button.

## Features

- **Read linear image**: Gets the current image loaded in Siril via `get_image_pixeldata(preview=False)`
- **Autostretch**: Applies percentile-based autostretch (2%-98%) for display
- **Combined RGB histogram**: Flattens all R, G, B channel pixels into one distribution
- **Y-axis mode**: Toggle between Normal (linear count) and Logarithmic (log10(count+1))
- **Axis scaling**: X Min, X Max, Y Min, Y Max spinboxes for manual view control
- **Fit Histogram**: Auto-adjusts axes so the histogram data fits visually

## Requirements

- Siril 1.4+ with Python script support
- sirilpy module (bundled with Siril)
- numpy, PyQt6, Pillow, astropy (installed automatically via `s.ensure_installed`)

## Testing

Run unit tests for image processing (requires numpy):

```bash
python -m unittest tests.test_image_processing -v
# or: python -m pytest tests/ -v
```

## Usage

1. Load an image in Siril
2. Run the script from Siril: **Processing → Scripts** (or your script menu)
3. The script will load the image, apply autostretch, and display the image plus histogram

## Script menu section (e.g. Utility)

Siril uses the **parent folder name** of the script as the menu section. By default, if the script lives in a folder named `Siril-Histogram-Viewer`, it appears under **Siril-Histogram-Viewer** in the Scripts menu. To have it appear under **Utility** instead:

1. In Siril: **Preferences → Scripts** and note your **Script Storage Directories**.
2. In one of those directories, create a folder named **Utility** (if it does not exist).
3. Move `HistogramViewer.py` into that folder (e.g. `…/Utility/HistogramViewer.py`).
4. In Siril, use **Preferences → Scripts → Refresh** (or the `reloadscripts` command).

The script will then show under **Utility** in the Scripts menu.

## Controls

- **Refresh from Siril**: Reload the current image
- **Normal / Logarithmic**: Switch Y-axis scale
- **X Min, X Max, Y Min, Y Max**: Manual axis limits (0-1 for X)
- **Fit Histogram**: Auto-fit view to data extent
- **-, Fit, 1:1, +**: Zoom controls for the image

## License

GPL-3.0-or-later
