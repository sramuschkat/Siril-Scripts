# Svenesis Siril Scripts

A collection of Python scripts for [Siril](https://www.siril.org/) (astronomical image processing).

## Author and links

- **Author:** Sven Ramuschkat — [www.svenesis.org](https://www.svenesis.org)
- **Repository:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)

## License

GPL-3.0-or-later

## Official Siril Script Repository

✨ The following scripts are **available in the official Siril Script Repository** and can be installed directly from within Siril via **Scripts → Get Scripts**:

- Svenesis Annotate Image
- Svenesis Blink Comparator
- Svenesis CosmicDepth 3D
- Svenesis Gradient Analyzer
- Svenesis Multiple Histogram Viewer

## Scripts

| Script | Description | Instructions | Siril Repo |
|--------|-------------|:------------:|:----------:|
| [Svenesis Annotate Image](#svenesis-annotate-image) | Annotate plate-solved images with catalog objects, coordinate grids, and export as PNG/TIFF/JPEG. | [Guide](Instructions/Svenesis-AnnotateImage-Instructions.md) · [DE](Instructions/Svenesis-AnnotateImage-Instructions_de.md) | ✨ |
| [Svenesis Blink Comparator](#svenesis-blink-comparator) | Animate a folder of FITS frames for rapid visual inspection and data-driven frame selection — statistics table, scatter plot, batch reject, file-based rejection workflow. | [Guide](Instructions/Svenesis-BlinkComparator-Instructions.md) · [DE](Instructions/Svenesis-BlinkComparator-Instructions_de.md) | ✨ |
| [Svenesis CosmicDepth 3D](#svenesis-cosmicdepth-3d) | Render catalogued objects from a plate-solved image as a rotatable 3D scene — image plane with push-pin depth sticks, SIMBAD distances, stretched-log/linear/hybrid scaling, HTML/PNG/CSV export. | [Guide](Instructions/Svenesis-CosmicDepth3D-Instructions.md) · [DE](Instructions/Svenesis-CosmicDepth3D-Instructions_de.md) | ✨ |
| [Svenesis GalacticView 3D](#svenesis-galacticview-3d) | Place your astrophoto inside an interactive 3D Milky Way — Earth in the Orion Arm, the photo as a textured rectangle pointing in the exact viewing direction, automatic Galactic / Cosmic mode based on object distance. | — | — |
| [Svenesis Gradient Analyzer](#svenesis-gradient-analyzer) | Analyze background gradients with heatmaps, diagnostics, and tool recommendations. | [Guide](Instructions/Svenesis-GradientAnalyzer-Instructions.md) · [DE](Instructions/Svenesis-GradientAnalyzer-Instructions_de.md) | ✨ |
| [Svenesis Multiple Histogram Viewer](#svenesis-multiple-histogram-viewer) | View linear and stretched images with RGB histograms, 3D surface plots, and detailed statistics. | [Guide](Instructions/Svenesis-MultipleHistogramViewer-Instructions.md) · [DE](Instructions/Svenesis-MultipleHistogramViewer-Instructions_de.md) | ✨ |

---

## Svenesis Annotate Image

**File:** `Svenesis-AnnotateImage.py` (v1.1.0) — **[Detailed Instructions](Instructions/Svenesis-AnnotateImage-Instructions.md)** · **[Deutsche Anleitung](Instructions/Svenesis-AnnotateImage-Instructions_de.md)**

> ✨ Available in the official Siril Script Repository.

Renders catalog annotations (deep-sky objects, named stars, coordinate grid, compass, info box) onto a plate-solved image and exports it as a shareable PNG, TIFF, or JPEG. All object data comes from live online VizieR and SIMBAD queries — no hardcoded or embedded catalogs. Parallel queries via ThreadPoolExecutor keep annotation fast even with multiple catalog sources. Inspired by PixInsight's AnnotateImage script. Unlike Siril's built-in overlay annotations, this script burns the annotations into an exportable image — ready to post on social media, forums, or include in observation reports.

### Screenshots

![Annotate Image — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Annotate_Image-1.jpg)

*Main window: catalog annotations with object type filtering, coordinate grid, compass rose, info box, and color-coded legend. Preview tab shows the annotated result.*

### Features

#### Object selection by type

Instead of choosing catalogs, you select **which types of objects** to annotate. All online catalog sources are queried in parallel — objects are filtered by your type selection:

| Color | Type | Examples |
|-------|------|----------|
| Gold | Galaxies | M31, M51, M81, NGC 4565, Centaurus A |
| Red | Emission Nebulae | Orion, Lagoon, Eagle, Rosette, Carina |
| Light red | Reflection Nebulae | M78, Witch Head, Iris, Rho Ophiuchi |
| Green | Planetary Nebulae | Ring (M57), Dumbbell (M27), Helix, Owl |
| Light blue | Open Clusters | Pleiades (M45), Double Cluster, Wild Duck |
| Orange | Globular Clusters | M13, Omega Centauri, 47 Tucanae |
| Magenta | Supernova Remnants | Crab (M1), Veil Nebula, Simeis 147 |
| Grey | Dark Nebulae | Horsehead (B33), Pipe, Snake, Coalsack |
| Red-pink | HII Regions | Heart, Soul, Barnard's Loop, Cave Nebula |
| White | Named Stars | ~275 IAU-named stars to mag ~5.5 |
| Pale blue | Asterisms | Coathanger, Kemble's Cascade |
| Violet | Quasars | QSOs and AGN from SIMBAD |

Select All / Deselect All buttons for quick toggling.

#### Online catalog sources

- **VizieR VII/118 (NGC 2000.0)** — NGC, IC, and Messier objects
- **VizieR VII/20 (Sharpless 1959)** — HII regions
- **VizieR VII/220A (Barnard 1927)** — Dark nebulae
- **VizieR V/50 (Yale BSC)** — Named bright stars
- **SIMBAD** — Supplementary objects (UGC, Abell, Arp, Hickson, Markarian, vdB, PGC, MCG, etc.) plus common name resolution

All data from live online queries — no hardcoded object data. Survey catalog junk (SDSS, 2MASS, GPM, Gaia, etc.) is automatically filtered out. Requires `astroquery` package and internet connection.

#### Annotation overlays

- **Leader lines:** Thin connecting lines from each label to its object marker — essential in crowded fields to see which label belongs to which object.
- **Color legend:** Auto-generated legend box (bottom-left) showing only the object types present in the current annotation.
- **Coordinate grid:** RA/DEC grid with auto-spaced lines and labeled coordinates.
- **Info box:** Semi-transparent box (top-left) with center RA/DEC, field of view, pixel scale, rotation, and object count.
- **Compass rose:** North/East direction arrows derived from WCS.

#### Display options

- Configurable font size, marker size, and magnitude limit
- Object size rendered as scaled ellipses (from catalog angular size)
- Common names display (e.g. "M31 (Andromeda Galaxy)")
- Optional magnitude and type labels
- Color coding by object type (configurable)
- Label collision avoidance (32-candidate greedy algorithm with spatial grid scoring)

#### Output

- **Formats:** PNG (recommended), TIFF, JPEG
- **DPI:** 72–300 (150 default for screens, 300 for print)
- **Auto-timestamped filenames** prevent overwriting
- **Preview tab** shows the result immediately after annotation
- **Open output folder / Open image** buttons for quick access

#### WCS detection

Robust plate-solve detection with 6 fallback strategies:
1. FITS header as dict (primary — same approach as Galaxy_Annotations.py)
2. FITS header as string (astropy parsing)
3. Keywords `pltsolvd` / `wcsdata` flag check
4. `pix2radec` sampling to build WCS from Siril's coordinate transform
5. `pix2radec` probe without plate-solve flag
6. FITS file on disk

Coordinate transforms use `siril.radec2pix()` for maximum compatibility.

#### Other features

- **Persistent settings:** All checkboxes, sliders, and options saved between sessions via QSettings
- **Keyboard shortcut:** F5 = Annotate
- **Progress bar** with status feedback during annotation
- **Log tab** with detailed diagnostic output
- **Dark-themed PyQt6 GUI** matching Gradient Analyzer style
- **Buy me a Coffee** support dialog
- **Parallel catalog queries** via ThreadPoolExecutor
- **Thread-safe siril coordinate access**
- **Large mosaic support** (display downscaling, DPI capping, memory management)
- **Common names from SIMBAD** with catalog-name filtering
- **Two-column checkbox layout** for all option groups

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, matplotlib, astropy, astroquery (installed automatically via `s.ensure_installed`)

### Usage

1. Load an image in Siril and **plate-solve** it (Tools → Astrometry → Image Plate Solver).
2. Run **Svenesis Annotate Image** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Select which **object types** to annotate using the color-coded checkboxes.
4. Adjust font size, marker size, magnitude limit, and extras (grid, info box, compass, legend, leader lines).
5. Click **Annotate Image** (or press F5).
6. Review the result in the Preview tab. Use **Open Annotated Image** to view it full-size.

---

## Svenesis Blink Comparator

**File:** `Svenesis-BlinkComparator.py` (v1.2.8) — **[Detailed Instructions](Instructions/Svenesis-BlinkComparator-Instructions.md)** · **[Deutsche Anleitung](Instructions/Svenesis-BlinkComparator-Instructions_de.md)**

> ✨ Available in the official Siril Script Repository.

Picks a folder of FITS frames, builds a temporary `svenesis_blink` sequence in Siril, and animates it as a blink animation for rapid visual inspection and data-driven frame selection. Comparable to PixInsight's Blink + SubframeSelector — identify satellite trails, clouds, tracking errors, focus drift, and bad frames, then reject them with a single click. Rejections are collected locally and, on close, written as `rejected_frames.txt` next to your files (with the physical FITS moved into a `rejected/` subfolder). Your original frames are never modified.

### Screenshots

![Blink Comparator — main window](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Blink_Comparator-1.jpg)

*Main window: viewer with frame info overlay, sortable statistics table, statistics graph with running average, scatter plot, thumbnail filmstrip, batch selection, and approval expressions.*

### Features

#### Folder-based workflow

- At startup the script always prompts for a **folder of FITS files** (recurses one level) and builds a temporary `svenesis_blink` FITSEQ sequence via `convert -fitseq` (and optional `register -2pass` for star stats).
- The temp sequence is automatically cleaned up when you close the window.
- Rejections write a plain-text `rejected_frames.txt` audit file and move rejected FITS into a `rejected/` subfolder — reversible by simply dragging the files back.
- Completely non-destructive: original frames are never overwritten.

#### Animated playback

- **Configurable speed** (1–30 FPS) with loop option and Play/Pause (Space key)
- **Frame navigation:** First, Previous, Next, Last buttons + draggable color-coded slider
- **Only included** filter (checkbox) to skip rejected frames during playback
- **Color-coded slider:** Red tick marks at excluded frame positions for instant overview

#### Two display modes

- **Normal:** Single-frame autostretched view. Default. Used for visual inspection, satellite/cloud hunting (play at 3–5 FPS — changing pixels jump out to the eye), and focus/tracking review.
- **Side by Side (vs. reference):** Current frame on left, reference (first frame) on right, synchronized zoom/pan. For direct A/B comparison.

#### Autostretch presets

- **Conservative** — darker background, preserves dim detail.
- **Default** — PixInsight-style STF (shadows_clip = -2.8, target median = 0.25).
- **Aggressive** — brighter, higher contrast.
- **Linear** — no stretch, raw data clipped to 0–255.
- Switching presets invalidates caches and re-renders; the choice is persisted across sessions via QSettings. Autostretch is always *globally linked* — every frame uses the same median/MAD so brightness differences (clouds, haze) stay visible.

#### Statistics table (sortable)

- All frames listed with **Weight, FWHM, Roundness, Background, Stars, Date, Status**
- Click any **column header to sort** — sort by FWHM to instantly find the worst frames
- Click a **row to jump** to that frame in the viewer
- **Multi-select** (Ctrl+click, Shift+click) → right-click → "Reject selected"

#### Composite quality weight

- Each frame gets a normalized quality score (0–1) based on FWHM (lower=better), roundness (higher=better), background (lower=better), and star count (more=better)
- Sort by Weight to see best and worst frames at a glance

#### Statistics graph

- **FWHM, Background, Roundness** plotted as line charts across all frames
- **Running average** (7-frame moving average) for trend detection
- Excluded frames shown as **red dots**, current frame as **white dashed line**
- Instantly reveals focus drift, clouds rolling in, or tracking degradation over time

#### Scatter plot

- **2D scatter** of any two metrics (FWHM vs Roundness, FWHM vs Background, etc.)
- Outlier frames immediately visible as dots far from the cluster
- **Click a dot** to jump to that frame
- Axis-normalized click detection (both axes contribute equally to nearest-point selection)

#### Frame selection

- **Manual marking:** G = include, B = exclude (with auto-advance to next frame)
- **Batch reject by threshold:** Reject all frames where FWHM > 4.5 (or any metric/operator/value combination) with live preview count
- **Reject worst N%:** Reject the worst 10% by FWHM, Background, Roundness, or Weight
- **Approval expressions:** Multi-criteria AND filter (e.g., FWHM < 4.5 AND Roundness > 0.7 AND Stars > 50) — rejects frames that fail any condition
- **Multi-select in table:** Ctrl+click or Shift+click rows, right-click → "Reject selected"
- **Reset All Rejections:** One-click button to mark every frame as Included again (baseline + pending) — useful when you want to start the selection over
- **Undo (Ctrl+Z):** Single undo for individual marks, grouped undo for batch operations (one Ctrl+Z undoes the entire batch)
- **Pending changes** shown in the left panel — only committed on close via "Apply Rejections && Close"

#### Thumbnail filmstrip

- Horizontal scrollable strip with **color-coded borders:** green = included, red = excluded, blue = current
- Click any thumbnail to jump to that frame
- **Lazy loading:** Thumbnails loaded on demand as you scroll
- **Adjustable size:** Slider in the viewer toolbar (40–160 px)
- Thumbnail cache reuses the main frame cache's already-stretched display data to avoid redundant disk I/O

#### Zoom & pan

- **Scroll wheel** zoom (0.1x–20x), **right-click drag** pan
- **Fit-in-Window** button (or `Z`) to return to full-frame view
- Live zoom-percentage readout that updates during scroll-wheel zoom

#### Frame info overlay

- Frame number, FWHM, roundness, and quality weight **burned into the image corner** during playback
- Toggleable via the **Overlay** checkbox in the viewer toolbar

#### Export

- **Statistics CSV** (full table with all metrics + inclusion status)
- **Animated GIF** of the blink animation (included frames, scaled to 480 px)
- **Copy to clipboard** (Ctrl+C) — captures the composite canvas (side-by-side layout + overlay, not just the raw pixmap)

#### Other features

- **A/B frame toggle (T key):** Pin the current frame, press T to toggle between the pinned frame and the current one
- **Session summary on close:** Frames viewed, excluded count, mean/best/worst FWHM
- **Persistent settings:** FPS, loop, auto-advance, overlay, autostretch preset, thumbnail size, display mode, table sort column, graph metric visibility
- **Post-mark refresh debouncing:** Rapid G/B marking collapses slider-exclusions repaint, scatter-plot rebuild, and statistics-graph rebuild into a single coalesced 150 ms refresh — hotkeys stay snappy even on 2000-frame sequences
- **Dark-themed PyQt6 GUI** matching Gradient Analyzer style
- **Buy me a Coffee** support dialog

#### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Previous / Next frame |
| `Home` / `End` | First / Last frame |
| `G` | Mark frame as good (include) |
| `B` | Mark frame as bad (exclude) |
| `Z` | Fit-in-window (reset zoom) |
| `T` | Pin / toggle A/B frame comparison |
| `Ctrl+Z` | Undo last marking (single or batch) |
| `Ctrl+C` | Copy current frame to clipboard |
| `1`–`9` | Set playback speed (FPS) |
| `+` / `-` | Speed up / slow down |
| `Esc` | Close (with "apply / discard / cancel" prompt if changes are pending) |

1–9 are handled through `keyPressEvent` instead of `QShortcut`, so digits typed into focused spinboxes/line-edits still reach the widget for multi-digit entry.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, matplotlib (installed automatically via `s.ensure_installed`)
- Optional: Pillow (for GIF export)

### Usage

1. Run **Svenesis Blink Comparator** from Siril: **Processing → Scripts** (or your Scripts menu).
2. A folder picker opens — select a folder containing your FITS frames (registered or unregistered). The script builds a temporary `svenesis_blink` sequence and loads all frame statistics.
3. If the FWHM / Roundness / Stars columns are empty, click the yellow **"Run Star Detection"** banner (runs `register -2pass` — non-destructive).
4. Use the **Statistics Table** tab to sort by FWHM and identify bad frames, or play the sequence at 3–5 FPS in **Normal** mode and mark frames with **B** (auto-advances).
5. Use **Batch Selection** (threshold / worst N%) or **Approval Expression** for bulk rejection.
6. Review in the **Statistics Graph** and **Scatter Plot** tabs to verify your selection.
7. Click **Apply Rejections && Close** — the script writes `rejected_frames.txt` next to your FITS files and moves rejected frames into a `rejected/` subfolder, then closes. Drag files out of `rejected/` to undo a decision after the fact.

### Changes Since v1.2.3

The last officially published release was v1.2.3. Summary of what has changed since then (see the script's `CHANGELOG` block for one-line bullets per release):

- **v1.2.4 — Folder-only workflow.** The script now always prompts for a folder of FITS files and builds its own temp sequence. Rejected frames move to a `rejected/` subfolder alongside a `rejected_frames.txt` audit file. Added an autostretch preset dropdown (Conservative / Default / Aggressive / Linear). Removed the ROI feature, the per-frame histogram widget, and the "use currently loaded sequence" path.
- **v1.2.5 — Simplified display modes.** Removed the Difference display mode and the `D` shortcut (playing at 3–5 FPS in Normal mode catches the same artifacts). Removed the Linked-stretch toggle — globally-linked autostretch is now the only mode.
- **v1.2.6 — Performance pass.** Thumbnails reuse the main frame cache's already-stretched image, `mtf()` runs in-place, RGB autostretch is a single pass, and preload pacing follows FPS.
- **v1.2.7 — Marking responsiveness.** Rapid G/B marking coalesces slider / scatter / graph refreshes through a single 150 ms timer; filmstrip and table skip no-op styling work.
- **v1.2.8 — Cross-platform polish & stability.** UTF-8 for `rejected_frames.txt` and CSV export (fixes Windows non-ASCII paths). 1–9 FPS presets moved to `keyPressEvent` so focused spinboxes accept digits natively. Folder paths with spaces are now quoted in Siril commands. `Apply` moves files first, then writes an audit list of only what actually moved. Star detection rebinds caches/stats and advances the progress bar through post-register phases. View-state (filter, display mode, graph metrics, scatter axes) now persists across sessions.

---

## Svenesis CosmicDepth 3D

**File:** `Svenesis-CosmicDepth3D.py` (v1.0.1) — **[Detailed Instructions](Instructions/Svenesis-CosmicDepth3D-Instructions.md)** · **[Deutsche Anleitung](Instructions/Svenesis-CosmicDepth3D-Instructions_de.md)**

> ✨ Available in the official Siril Script Repository.

Takes every catalogued object in your plate-solved image, resolves their distances from SIMBAD (mesDistance, redshift/Hubble law, type-median fallback) and renders them as a rotatable 3D scene. Your image sits as a flat "window" at the front; each object hovers at its actual distance behind the window on a push-pin depth stick that lands on the exact pixel of the feature in the sky plane. A foreground nebula at 1,344 ly and a background galaxy at 30 million ly finally look like what they are.

### Screenshots

![Svenesis CosmicDepth 3D](https://raw.githubusercontent.com/sramuschkat/Siril-Scripts/main/screenshots/Svenesis-CosmicDepth3D.jpg)

### Features

#### 3D scene layout

- **Image plane** rendered as a flat, non-transparent rectangle at the front of the scene, with the same orientation as the Siril image (FITS row 0 at the bottom, pixel-X mirrored so the default camera angle reads left/right like Siril).
- **Depth sticks** from each object marker straight back to its exact image pixel — the "push-pin through a window" view.
- **Embedded rotatable view** via `QWebEngineView` + Plotly: drag to rotate, scroll to zoom, hover any marker for distance, uncertainty and source. Falls back to a static PNG plus opening the interactive HTML in the browser if WebEngine is unavailable.
- **Viewer-from-Earth perspective** — X = depth (scaled ly), Y = pixel-X (mirrored), Z = pixel-Y (direct). Axis proportions follow the image aspect so the scene box matches the frame.

#### Scaling & view ranges

- **Stretched-log** (default) — piecewise-log distance axis: each decade below 100 M ly takes 1 unit, each decade beyond takes 3 units, so the far-galaxy tail gets ~3× more room on screen than a plain log would give it. Tick labels read in real light-years (1, 10, 100, 1k, …, 100M, 1B, 10B). Recommended for most fields.
- **Linear** — true proportional distances. Useful for star-only fields inside the Milky Way (galaxies disappear to the horizon).
- **Hybrid** — linear up to 10,000 ly, log beyond. Realistic solar-neighbourhood spacing with extragalactic context preserved.
- **View ranges:** **Cosmic** (everything) or **Galactic** (< 100,000 ly, i.e. inside the Milky Way only).

#### Distance resolution

- **Priority chain:** local JSON cache (90-day TTL) → SIMBAD `mesDistance` table → redshift × Hubble law (z < 0.5) → type-based median fallback (clearly labelled as *Type median*).
- **Distance cache** in `~/.config/svenesis/cosmic_depth_cache.json` — a second render of the same field is near-instant.
- **Clear Distance Cache** button to force a full re-query (useful after SIMBAD updates).

#### Object selection by type

Same colour-coded type system as Annotate Image:

| Color | Type | Typical distance range |
|-------|------|-----------------------|
| Gold | Galaxies | 2 Mly – billions of ly |
| Red | Emission Nebulae | 500 – 10,000 ly |
| Light red | Reflection Nebulae | 400 – 1,500 ly |
| Green | Planetary Nebulae | 1,000 – 10,000 ly |
| Light blue | Open Clusters | 400 – 15,000 ly |
| Orange | Globular Clusters | 10,000 – 100,000 ly |
| Magenta | Supernova Remnants | 500 – 30,000 ly |
| Grey | Dark Nebulae | 400 – 2,000 ly |
| White | Named Stars | 10 – 5,000 ly |
| Red-pink | HII Regions | 1,000 – 30,000 ly |
| Pale blue | Asterisms | various |
| Violet | Quasars | billions of ly |

#### Performance

- **Parallel SIMBAD tiling** — wide fields are split into ≤ 0.75° tiles and queried with up to 8 concurrent TAP requests, with live per-tile progress feedback in the status bar.
- **Cached `plotly.min.js`** — written once to your temp directory and referenced from each render, so refreshes reload only the (small) scene data rather than the ~3.5 MB Plotly bundle.
- **Opt-in WebEngine repair** — if the installed `PyQt6-WebEngine` wheel doesn't match Siril's bundled `PyQt6` Qt version (symptom: `Symbol not found: _qt_version_tag_6_XX`), the embedded view shows a red banner with a "Repair WebEngine…" button. Clicking it opens a dialog with the exact pip command, live stdout/stderr, and a Retry button. The repair is skipped automatically on PEP 668 / externally-managed Python interpreters; no silent force-reinstalls.

#### UI

- **3D Map tab** — embedded rotatable Plotly scene (or static PNG fallback with a banner if WebEngine is unavailable).
- **Objects tab** — sortable `QTableWidget` with Name, Type, Mag, Distance (ly), ± uncertainty, Source. Click any column header to sort numerically; column widths and sort order persist between sessions.
- **Log tab** — detailed diagnostic output (SIMBAD tile counts, cache hit rate, fallback reasons).
- **Help dialog** — 4 tabs (Getting Started, Object Types, Scaling & Display, Exports & Performance) matching the Annotate Image help style.
- **Dark-themed PyQt6 GUI** consistent with the rest of the suite.

#### Export

- **HTML** — standalone, fully interactive Plotly scene (shareable, opens in any browser).
- **PNG** — high-resolution static export via Plotly + kaleido, captured from your current 3D camera angle and zoom so the saved image matches what you see on screen (including the stretched-log axis with ly labels). Falls back to a matplotlib snapshot if kaleido isn't installed.
- **CSV** — full object table: name, type, RA/Dec, magnitude, size, distance, uncertainty, source, confidence, image pixel (x, y).

All exports are written to Siril's working directory with a timestamp appended to the base filename.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, matplotlib, astropy, astroquery, plotly, kaleido (installed automatically via `s.ensure_installed`)
- PyQt6-WebEngine — probed at startup; if missing or ABI-mismatched the script offers an explicit in-app repair dialog and falls back to a static view + browser HTML in the meantime
- Internet connection for the initial SIMBAD queries (subsequent renders use the local distance cache)

### Usage

1. Load an image in Siril and **plate-solve** it (Tools → Astrometry → Image Plate Solver).
2. Run **Svenesis CosmicDepth 3D** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Select which **object types** to include (left-panel checkboxes), set the magnitude limit, and pick a **scaling mode** and **view range**.
4. Click **Render 3D Map** (or press F5).
5. Drag in the scene to rotate, scroll to zoom, hover markers for details. Toggle **Show image as sky plane** to switch between the pixel-mapped "window" layout and a pure abstract 3D map.
6. Review the **Objects** tab for the full distance table; use **Export HTML / PNG / CSV** for sharing or archiving. The PNG export captures your current camera angle, so rotate first to the view you want.

---

## Svenesis GalacticView 3D

**File:** `Svenesis-GalacticView3D.py` (v0.9.0)

> ⚠️ Pre-release (0.9.0) — public preview, not yet submitted to the official Siril Script Repository.

Reads the current plate-solved image from Siril, identifies the main astronomical object via SIMBAD, and renders the Milky Way as an interactive 3D model — with Earth physically positioned in the Orion Arm and the astrophoto itself placed as a textured rectangle pointing in the exact viewing direction in space. GalacticView 3D answers a question that no other tool answers: *"My photo is not just anywhere — it is a window into one specific direction of the universe. Where exactly?"*

### Screenshots

![GalacticView 3D — Milky Way scene with photo as a window in space](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/GalacticView3D_Image-1.jpg)

*Main view: 5-arm Milky Way with galactic disk stars, Earth in the Orion Arm, and the plate-solved astrophoto rendered as a textured rectangle pointing in its actual viewing direction. Drag to rotate, scroll to zoom.*

### Features

#### Two automatic view modes

- **Galactic mode** (object distance < 150,000 ly): 1 unit = 1,000 ly. Shows the Milky Way's spiral arms, galactic disk, central bulge, and Earth in the Orion Arm — answering *"where inside our galaxy am I looking?"*
- **Cosmic mode** (object distance ≥ 150,000 ly): 1 unit = 100,000 ly. Adds neighbouring galaxies (LMC, SMC, M31, M33, …) with compressed log scaling beyond 1 Mly so the far-galaxy tail stays readable.
- Mode is selected automatically from the resolved object distance and SIMBAD type — no manual toggling required.

#### Photo placement in 3D space

- **Plate-solved WCS ingestion** with the same 6-strategy WCS detection used by CosmicDepth 3D (FITS dict, header string, `pix2radec` sampling, file-on-disk fallback).
- **Photo as a textured rectangle:** the four image corners are converted from RA/Dec to galactic coordinates and the FITS data is auto-stretched and applied as a Plotly surface texture.
- **Viewing ray** drawn from Earth to the photo centre — the line literally shows where you were pointing your telescope.
- **Photo distance** is the resolved distance to the main object identified in the image.

#### Distance resolution

- **Priority chain:** local JSON cache (90-day TTL) → SIMBAD `mesDistance` table → redshift × Hubble law (H₀ = 70 km/s/Mpc) → SIMBAD object-type median fallback (clearly labelled as *Type median*).
- **Distance cache** in `~/.config/siril/svenesis_galacticview_cache.json` — re-rendering the same field is near-instant.
- **Cosmological corrections** — for distant galaxies the redshift → distance conversion accounts for lookback time so cosmic-mode positions are physically meaningful.

#### Galactic scene composition

- **5 spiral arms** (Perseus, Sagittarius, Scutum-Centaurus, Norma, and the Orion Spur) rendered as smooth 3D curves with name labels in galactic mode.
- **Galactic disk** populated with ~500 stars and a central bulge (~180 stars) for depth perception.
- **Earth in the Orion Arm** — placed at the correct heliocentric position (~26,000 ly from the galactic centre).
- **Distance rings** around the galactic centre and around Earth as scale references.
- **Compass rose** anchored to the scene showing galactic north and the direction towards the galactic centre.
- **Constellation lines** for the relevant region around the photo centre (galactic mode).
- **Neighbour galaxies** in cosmic mode — embedded LMC/SMC/M31/M33/etc. as labelled markers.

#### Interactive 3D rendering

- **Plotly-in-QWebEngineView** with full drag-to-rotate, scroll-to-zoom, hover-for-details — the same embedded 3D approach as CosmicDepth 3D.
- **Matplotlib 3D fallback** if `PyQt6-WebEngine` is not available (or ABI-mismatched against Siril's bundled PyQt6); the app keeps working but drops the live rotation.
- **Dark-themed PyQt6 GUI** matching the rest of the Svenesis suite.
- **Persistent settings** via `QSettings` — view mode, last target, render preferences are remembered across sessions.

#### Target picker

- When the main object cannot be uniquely identified (e.g. wide field with multiple bright SIMBAD candidates), a **target picker dialog** lists the candidates with type, magnitude, and distance so you can choose the actual photographic subject.

#### Export

- **HTML** — standalone, fully interactive Plotly scene (shareable, opens in any browser).
- **PNG** — high-resolution snapshot of the current camera angle.
- **CSV** — coordinate table of all scene elements (Earth, photo corners, identified object, neighbour galaxies) in galactic XYZ.

### Requirements

- Siril 1.4+ with Python script support
- sirilpy (bundled with Siril)
- numpy, PyQt6, matplotlib, astropy, astroquery, plotly, kaleido (installed automatically via `s.ensure_installed`)
- PyQt6-WebEngine — probed at startup; if missing or ABI-mismatched the script falls back to a static matplotlib view
- Internet connection for the initial SIMBAD queries (subsequent renders use the local distance cache)

### Usage

1. Load an image in Siril and **plate-solve** it (Tools → Astrometry → Image Plate Solver).
2. Run **Svenesis GalacticView 3D** from Siril: **Processing → Scripts** (or your Scripts menu).
3. The script identifies the main object and resolves its distance; if it asks, pick the correct target from the dialog.
4. The scene renders automatically — Galactic or Cosmic mode is chosen for you. Drag to rotate, scroll to zoom.
5. Use **Export HTML / PNG / CSV** to share or archive the view.

---

## Svenesis Gradient Analyzer

**File:** `Svenesis-GradientAnalyzer.py` (v1.8.4) — **[Detailed Instructions](Instructions/Svenesis-GradientAnalyzer-Instructions.md)** · **[Deutsche Anleitung](Instructions/Svenesis-GradientAnalyzer-Instructions_de.md)**

> ✨ Available in the official Siril Script Repository.

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
2. Run **Svenesis Gradient Analyzer** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Adjust grid resolution and sigma in the left panel, select a threshold preset, then click **Analyze** (or press F5).
4. Review the heatmap, profiles, and metrics across the 9 tabs. Check the recommendations for the suggested tool and parameters.
5. Apply the recommended extraction in Siril, then click **Analyze** (F5) again to re-analyze and compare before/after.

---

## Svenesis Multiple Histogram Viewer

**File:** `Svenesis-MultipleHistogramViewer.py` (v1.1.0) — **[Detailed Instructions](Instructions/Svenesis-MultipleHistogramViewer-Instructions.md)** · **[Deutsche Anleitung](Instructions/Svenesis-MultipleHistogramViewer-Instructions_de.md)**

> ✨ Available in the official Siril Script Repository.

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
2. Run **Svenesis Multiple Histogram Viewer** from Siril: **Processing → Scripts** (or your Scripts menu).
3. Use the left panel for view type (Histogram / 3D), Data-Mode (Normal / Log), channels, and image/source options. Use **Enlarge Diagram** for a larger histogram or 3D view.
