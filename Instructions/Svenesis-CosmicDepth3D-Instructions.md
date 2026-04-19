# Svenesis CosmicDepth 3D — User Instructions

**Version 1.0.1** | Siril Python Script for 3D Depth Visualization of Plate-Solved Images

> *See your image not as a flat 2D frame but as a window onto a 3D universe — every catalogued object floats at its real distance behind the sky plane, on a push-pin stick that lands on the exact pixel where you photographed it.*

---

## Table of Contents

1. [What Is CosmicDepth 3D?](#1-what-is-cosmicdepth-3d)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Scaling Modes & View Ranges](#6-scaling-modes--view-ranges)
7. [Object Types & Color Coding](#7-object-types--color-coding)
8. [Filters & Data Sources](#8-filters--data-sources)
9. [The 3D Scene — Navigation & Reading the View](#9-the-3d-scene--navigation--reading-the-view)
10. [Distance Resolution — How Distances Are Determined](#10-distance-resolution--how-distances-are-determined)
11. [Exports (HTML / PNG / CSV)](#11-exports-html--png--csv)
12. [WebEngine Repair Dialog](#12-webengine-repair-dialog)
13. [Use Cases & Workflows](#13-use-cases--workflows)
14. [Keyboard Shortcuts](#14-keyboard-shortcuts)
15. [Tips & Best Practices](#15-tips--best-practices)
16. [Troubleshooting](#16-troubleshooting)
17. [FAQ](#17-faq)

---

## 1. What Is CosmicDepth 3D?

The **Svenesis CosmicDepth 3D** script takes your plate-solved astrophoto and every catalogued object it contains, resolves their real distances from SIMBAD, and renders the whole field as an interactive, rotatable 3D scene.

- Your image sits as a **flat "sky plane"** at the front of the scene — the window through which you were photographing.
- Each catalogued object floats at its **real distance** behind the window on a **push-pin depth stick** that lands on the exact pixel of the feature in the sky plane.
- Drag to rotate, scroll to zoom, hover markers for per-object distance / uncertainty / source.
- Export the scene as an interactive HTML file, a high-resolution PNG captured from your current viewing angle, or a CSV table of every object and its distance.

The result: a **foreground nebula at 1,344 ly** and a **background galaxy at 30 million ly** finally look like what they actually are — not like two flat sprites in the same frame. It's an intuitive way to see what your image is really showing you: a slice through a universe of vastly different distances, projected onto a single 2D photograph.

---

## 2. Background for Beginners

### Why "3D" from a 2D image?

A photograph of the sky flattens everything onto one image plane. Your eye has no way to tell whether a nebula is ten times or ten million times farther away than a star next to it. CosmicDepth 3D adds the **depth axis** by looking up each catalogued object's real distance in SIMBAD and stacking them behind the image.

What you see in the 3D view is:
- **X axis** — distance from Earth (light-years, with a stretched-log scale by default).
- **Y axis** — horizontal pixel position in your image.
- **Z axis** — vertical pixel position in your image.

The sky plane is flat, like a window. Every depth stick is perpendicular to that window, anchored at the exact pixel where the object appears in your photograph.

### What does "plate-solved" mean?

**Plate solving** is the process of determining the exact sky coordinates of your image. It matches the star pattern in your photo against a star catalog to figure out where your telescope was pointing.

After plate solving, your image has a **WCS (World Coordinate System)** solution embedded in its FITS header. This tells software: "pixel (500, 300) corresponds to RA 12h 30m, DEC +41° 20′." CosmicDepth 3D needs this to know which catalogued objects fall into your frame and where in the image they appear.

| Concept | Explanation |
|---------|-------------|
| **RA / DEC** | Sky longitude and latitude. Every point on the sky has a unique (RA, DEC). |
| **WCS** | The pixel-to-sky mapping stored in the FITS header after plate solving. |
| **SIMBAD** | An online astronomical database with positions, types and distance measurements for millions of objects. |
| **Parsec, light-year** | Distance units. 1 parsec ≈ 3.26 light-years. We use light-years here. |
| **Redshift (z)** | A measure of how far away (and how fast-receding) a galaxy is. Used to estimate distances to objects beyond ~3 billion ly. |

### Why a stretched-log distance axis?

A plain linear axis makes galaxies disappear — a 30 Mly galaxy is 20,000× further than a 1,500 ly nebula, so the nebula collapses to a dot on the image plane. A plain log axis fixes that, but it gives every decade of distance the same width, so the far-galaxy tail (100 M ly → 10 B ly) gets cramped at the right edge. The **stretched-log** default gives the far tail three times more visual room while keeping the inner Milky Way readable. See Section 6.

---

## 3. Prerequisites & Installation

### Requirements

| Component | Minimum Version | Notes |
|-----------|-----------------|-------|
| **Siril** | 1.4.0+ | Must have Python script support enabled |
| **sirilpy** | Bundled | Comes with Siril 1.4+ |
| **numpy** | Any recent | Auto-installed |
| **PyQt6** | 6.x | Auto-installed |
| **matplotlib** | 3.x | Auto-installed (used for the PNG fallback) |
| **astropy** | Any recent | Auto-installed |
| **astroquery** | Any recent | Auto-installed — required for SIMBAD queries |
| **plotly** | Any recent | Auto-installed — the 3D scene renderer |
| **kaleido** | Any recent | Auto-installed — Plotly's static PNG backend |
| **PyQt6-WebEngine** | matching Qt of PyQt6 | Probed at startup; if missing or ABI-mismatched, the script offers an in-app repair dialog (see Section 12) and falls back to a browser view in the meantime |
| **Internet connection** | — | Required for the initial SIMBAD queries; subsequent renders use the local distance cache |

### Installation

1. Download `Svenesis-CosmicDepth3D.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script auto-installs missing Python dependencies on first run via `s.ensure_installed(...)`.

---

## 4. Getting Started

### Step 1: Load a plate-solved image

CosmicDepth 3D requires a **plate-solved image**. If your image isn't solved yet, use **Tools → Astrometry → Image Plate Solver…** in Siril first.

### Step 2: Run the script

Go to **Processing → Scripts → Svenesis CosmicDepth 3D**.

The window opens with:
- A **left panel** of configuration controls (Include Objects, View Mode & Scaling, Filters, Data Sources, Output, Actions).
- A **right panel** with three tabs: **3D Map**, **Objects**, **Log**.

### Step 3: Configure the render

1. **Include Objects** — tick which types of objects to include (Galaxies, Nebulae, Open Clusters, etc.). Use **Select All** / **Deselect All** for quick toggling.
2. **View Mode & Scaling** — pick a **Range** (Cosmic / Galactic) and a **Scale** (Log / Linear / Hybrid). Enable **Show image as sky plane** to see the photograph as a 3D window; disable it for an abstract, points-only map.
3. **Filters** — magnitude limit, max number of objects, "only known distances" toggle.
4. **Data Sources** — leave **Query SIMBAD online** on for the first render; use **Clear Distance Cache** if you've had SIMBAD updates you want to pull fresh.
5. **Output** — base filename and PNG DPI (150 for screens, 300 for print).

### Step 4: Render

Click **Render 3D Map** (or press **F5**).

The status bar shows progress:
- **0–15 %** — reading the image and building the sky plane.
- **15–40 %** — querying SIMBAD for objects in your field (parallel tiled queries).
- **40–70 %** — resolving per-object distances.
- **70–100 %** — building the 3D figure and loading it into the embedded view.

### Step 5: Explore

- **Drag** in the 3D Map tab to rotate. **Scroll** to zoom. **Hover** over any marker to see its distance, uncertainty and source.
- Switch to the **Objects** tab for the full sortable table.
- Switch to the **Log** tab for a detailed diagnostic trace.

### Step 6: Export

Use **Export HTML / PNG / CSV** to save the scene. **Rotate the view first** to the angle you want — the PNG export captures your current camera position so the saved image matches what you see on screen.

---

## 5. The User Interface

### Left Panel (Control Panel)

#### Include Objects
Color-coded checkboxes for the 12 object types (Galaxies, Nebulae, Planetary Nebulae, Open Clusters, Globular Clusters, Named Stars in the left column — all ON by default; Reflection Nebulae, Supernova Remnants, Dark Nebulae, HII Regions, Asterisms, Quasars in the right column — all OFF by default). **Select All** / **Deselect All** buttons below.

#### View Mode & Scaling
- **Range:** Cosmic (all distances) or Galactic (< 100,000 ly only).
- **Scale:** Log (default, stretched-log), Linear, or Hybrid.
- **Color by type** — color each marker by object type instead of uniform light grey.
- **Show image as sky plane** — render your photograph as a flat 3D window with depth sticks, or disable for an abstract map.

#### Filters
- **Mag limit** (1.0 – 20.0, default 12.0) — only include objects brighter than this. Objects without a catalogued magnitude (dark nebulae, large HII regions) are always included.
- **Max objects** (10 – 5,000, default 200) — cap on the number of rendered markers. Bright-first selection when the cap is hit.
- **Only objects with known distance** — drop any object that would otherwise use a type-median fallback distance.

#### Data Sources
- **Query SIMBAD online** — on by default. Disable to work from the local cache only.
- **Clear Distance Cache** — discards the local distance JSON so the next render re-queries every object. The label next to it shows the current cache size ("Cache: 347 objects").

#### Output
- **Filename** (default `cosmic_depth_3d`) — base name for exports. A timestamp is appended automatically.
- **PNG DPI** (72 – 300, default 150) — resolution for the PNG export.

#### Actions
- **Render 3D Map** — the main button. Also bound to **F5**.
- **Export HTML / PNG / CSV** — enabled after the first successful render.
- **Open Output Folder / Open Rendered HTML** — enabled after a PNG or HTML export.

Below the control panel: **Buy me a Coffee**, **Help**, and **Close** buttons.

### Right Panel (Tabs)

- **3D Map** — the embedded, rotatable Plotly scene. If PyQt6-WebEngine is unavailable, a red banner appears here with a **Repair WebEngine…** button.
- **Objects** — sortable `QTableWidget` with columns **Name**, **Type**, **Mag**, **Distance (ly)**, **± Uncertainty**, **Source**. Click any header to sort numerically. Column widths and sort order persist across sessions.
- **Log** — monospace diagnostic trace: SIMBAD tile counts, cache hit rate, fallback reasons, export paths.

---

## 6. Scaling Modes & View Ranges

The distance axis is the key design decision of the whole tool. Your nebulae sit at a few hundred to a few thousand light-years; your galaxies at tens of millions to billions. That's nine orders of magnitude in one scene — and no single axis choice is right for everything.

### Scale: Log (default — stretched-log)

Piecewise logarithmic axis that gives extra room to the far-galaxy tail:

- **Each decade below 100 M ly takes 1 unit of axis space** (plain log): 1 → 10 → 100 → 1k → 10k → 100k → 1M → 10M → 100M.
- **Each decade at/beyond 100 M ly takes 3 units**: 100M → 1B → 10B → 100B each get three times as much space as a plain log would give them.

Tick labels still read in real light-years ("1", "10", "100", "1k", …, "100M", "1B", "10B"). The stretching is invisible in the labels — only the spacing changes, so far galaxies are no longer cramped into the right edge. Recommended for **any field that mixes Milky Way stars/nebulae with external galaxies**.

### Scale: Linear

True proportional distances. A 1,500 ly nebula and a 30 Mly galaxy get spacing proportional to their actual 20,000× difference. In practice this means **galaxies disappear to the horizon** and you only see nearby structure. Useful for star-only fields inside the Milky Way where linear spacing is meaningful.

### Scale: Hybrid

Linear from 0 to 10,000 ly, log beyond. Realistic solar-neighbourhood spacing with extragalactic context preserved. A compromise when you want nearby stars to appear at proportional distances but still want to show distant galaxies in the same frame.

### Range: Cosmic vs. Galactic

- **Cosmic** (default) — include everything in the field, out to quasars at billions of light-years.
- **Galactic (< 100k ly)** — drop everything beyond ~100,000 ly. Useful for pure Milky Way fields where galaxies would just clutter the picture, or when you deliberately want to focus on stars, nebulae and clusters inside our own galaxy.

### Which should I pick?

| Your image | Recommendation |
|------------|----------------|
| Deep sky with galaxies (any galaxy field, galaxy clusters) | **Log + Cosmic** |
| Milky Way star field / nebula only | **Hybrid + Galactic** (or Log + Galactic) |
| Wide Milky Way panorama with a couple of background galaxies | **Log + Cosmic** |
| Single bright nebula close-up | **Hybrid + Galactic** |
| Solar neighbourhood star field (< a few kly) | **Linear + Galactic** |

---

## 7. Object Types & Color Coding

Same color scheme as Annotate Image, with typical distance ranges added so you can sanity-check distance resolution at a glance:

| Color | Type | Typical distance | Default state |
|-------|------|------------------|---------------|
| Gold | Galaxies | 2 Mly – billions of ly | ON |
| Red | Emission Nebulae | 500 – 10,000 ly | ON |
| Green | Planetary Nebulae | 1,000 – 10,000 ly | ON |
| Light blue | Open Clusters | 400 – 15,000 ly | ON |
| Orange | Globular Clusters | 10,000 – 100,000 ly | ON |
| White | Named Stars | 10 – 5,000 ly (mostly < 1,000) | ON |
| Light red | Reflection Nebulae | 400 – 1,500 ly | OFF |
| Magenta | Supernova Remnants | 500 – 30,000 ly | OFF |
| Grey | Dark Nebulae | 400 – 2,000 ly | OFF |
| Red-pink | HII Regions | 1,000 – 30,000 ly | OFF |
| Pale blue | Asterisms | various (type median) | OFF |
| Violet | Quasars | billions of ly | OFF |

Enable **Color by type** (on by default) to color each marker by its type. Disable it for a monochrome scene — sometimes clearer on very crowded galaxy fields.

---

## 8. Filters & Data Sources

### Magnitude limit

Default 12.0. Controls the faintest objects included:
- **8–10** — clean scene, brightest objects only.
- **12.0** — good default.
- **14–16** — dense scene, includes many faint galaxies.
- **18–20** — very dense; the **Max objects** cap becomes your main density control.

Objects with no catalogued magnitude (dark nebulae, some HII regions) are always included regardless of the limit.

### Max objects

Default 200. Hard cap on the number of rendered markers. When more objects pass the type/magnitude filters than the cap allows, the brightest are kept. Useful when you have a galaxy cluster field with hundreds of candidate objects and the markers would otherwise cover each other.

### Only objects with known distance

Default OFF. When ON, any object that would use a type-median fallback distance (labelled `Type median` in the Objects table's Source column) is dropped. Use this for publications where you want every marker backed by a real SIMBAD measurement.

### Query SIMBAD online

Default ON. Disable to work entirely from the local distance cache (`~/.config/svenesis/cosmic_depth_cache.json`, 90-day TTL). Useful when you've already rendered the same field once and want to iterate on scaling/filters offline.

### Clear Distance Cache

One-click button to discard the cached distance JSON. The label shows the current cache size. Useful after large SIMBAD updates or if you suspect a cached distance is wrong.

---

## 9. The 3D Scene — Navigation & Reading the View

### Navigation

| Action | Mouse / Keyboard |
|--------|------------------|
| **Rotate** | Left-drag in the 3D view |
| **Pan** | Shift + left-drag |
| **Zoom** | Scroll wheel |
| **Reset view** | Double-click the plot |
| **Hover details** | Move mouse over any marker — shows name, distance, uncertainty, source |

### Axes

- **X (horizontal depth)** — distance from Earth in light-years. On the Log scale this is the stretched-log axis (Section 6). Earth is at X = 0 (the "sky plane" is anchored there in the image-plane view, or very close for the abstract view).
- **Y (left-right)** — horizontal pixel position in your image. Mirrored so the default camera angle reads left/right the same way as your Siril image.
- **Z (up-down)** — vertical pixel position in your image. FITS row 0 is at the bottom to match Siril's image display.

### Sky plane vs. abstract view

- **Show image as sky plane ON (default)** — your photograph is rendered as a flat, non-transparent rectangle at the front of the scene. Each object sits behind it on a push-pin depth stick that lands exactly on the pixel where that object appears in your photo. This is the "window onto a 3D universe" layout.
- **Show image as sky plane OFF** — the photograph is hidden. You just see the 3D cloud of markers plus a reference plane. Cleaner for presentations; sky-plane view is more intuitive for astrophotographers.

### What the push-pin depth sticks tell you

Each stick runs perpendicular from the sky plane straight back to the object's marker. The **stick length is the object's real distance**, on whatever scale you've chosen. A stick that barely reaches behind the plane is nearby (a few hundred ly); a stick that reaches to the other side of the scene box is a distant galaxy (tens or hundreds of millions of ly).

---

## 10. Distance Resolution — How Distances Are Determined

Each object's distance is resolved via a **priority chain**, with the result recorded in the **Source** column of the Objects table:

1. **Local cache hit** (`svenesis cache`) — the object was looked up in a previous render within the last 90 days.
2. **SIMBAD `mesDistance` table** (`SIMBAD mesDistance`) — a direct, catalogued distance measurement. Highest-quality source; used for most well-studied galaxies, nebulae and nearby stars.
3. **Redshift × Hubble law** (`SIMBAD redshift`) — for objects with a redshift (z) but no direct distance, distance is computed as `d = cz / H₀` (H₀ = 70 km/s/Mpc). Used for galaxies and quasars with z < 0.5.
4. **Type-median fallback** (`Type median`) — for objects where neither distance nor redshift are in SIMBAD, a sensible median distance for that object type is used (e.g. ~1,500 ly for emission nebulae, ~5,000 ly for open clusters). Clearly labelled so you don't mistake it for a real measurement.

The **± Uncertainty** column reflects the precision of the source. Type-median fallbacks have large uncertainties; direct SIMBAD measurements have small ones.

### Distance cache

The cache lives in `~/.config/svenesis/cosmic_depth_cache.json`. It has a **90-day TTL** — older entries are ignored and re-queried. A second render of the same field is near-instant because every object distance comes from the cache.

---

## 11. Exports (HTML / PNG / CSV)

All three export buttons enable after the first successful render.

### HTML export

Writes a standalone `.html` file containing the full interactive Plotly scene (with `plotly.min.js` embedded). Open it in any browser and you get the same drag-rotate, scroll-zoom, hover-details experience as the in-app view. Great for sharing with people who don't have Siril.

### PNG export

Writes a high-resolution PNG via Plotly + kaleido. Two important design choices:

1. **The exported image matches your current camera angle.** Before you click Export PNG, rotate the view to whatever angle you want in the saved image. The export reads the live Plotly camera (eye / center / up) and applies it to the output.
2. **Pixel-parity with the live view.** The PNG is rendered by the same Plotly engine as the embedded view, at a resolution scaled by your DPI setting (base 1400 × 1000, scaled by DPI/100). So the stretched-log axis, colours, markers and depth sticks all match the on-screen scene.

If `kaleido` is missing, the script falls back to a matplotlib snapshot — the log says so and suggests `pip install --upgrade kaleido`.

### CSV export

Writes a full object table with columns: `name`, `type`, `ra_deg`, `dec_deg`, `mag`, `size_arcmin`, `distance_ly`, `uncertainty_ly`, `source`, `confidence`, `pixel_x`, `pixel_y`.

Useful for:
- Archiving the exact object list that produced a given render.
- Feeding the distances into other tools (spreadsheets, other scripts).
- Peer-reviewing a suspicious-looking distance (`source` tells you which method was used).

### Output location

All exports go to Siril's working directory with a timestamp appended:
```
cosmic_depth_3d_20250815_213012.html
cosmic_depth_3d_20250815_213012.png
cosmic_depth_3d_20250815_213012.csv
```

Use **Open Output Folder** and **Open Rendered HTML** (under the export buttons) to jump straight to them.

---

## 12. WebEngine Repair Dialog

The interactive 3D view is rendered with `QWebEngineView`, which lives in the separate `PyQt6-WebEngine` package. On some systems the installed `PyQt6-WebEngine` version doesn't match Siril's bundled `PyQt6`, producing an import error like:

```
ImportError: ... Symbol not found: _qt_version_tag_6_XX
```

When that happens CosmicDepth 3D does **not** auto-install anything silently. Instead:

1. The 3D Map tab shows a **red banner** with the exact error and a **Repair WebEngine…** button.
2. Clicking the button opens a dialog with:
   - The exact pip command the dialog is about to run (selectable so you can copy-paste it into a terminal if you prefer).
   - A live read-only console that streams pip's stdout/stderr in real time — you'll see wheel resolution, download progress, any proxy errors, etc.
   - **Run Repair** — executes `pip install --force-reinstall --no-deps 'PyQt6-WebEngine==MAJOR.MINOR.*' 'PyQt6-WebEngine-Qt6==MAJOR.MINOR.*'` with the minor version pinned to match the running PyQt6 (which fixes the ABI mismatch).
   - **Retry Import** — re-attempts the import without restarting Siril. If it succeeds, the banner disappears and the next render uses the embedded view.
   - **Close** — dismiss the dialog without changes.
3. **PEP 668 / externally-managed Python** — if the running interpreter is marked externally-managed (Debian-style system Python), the **Run Repair** button is disabled with an explanation. In that case the fix is to install `PyQt6-WebEngine` yourself in your preferred manner (apt, venv, etc.) — the script refuses to damage a system-managed interpreter.

### Meanwhile, you can still render

If WebEngine is unavailable, renders still succeed — they just write a static HTML file and open it in your default browser (so you still get the full interactive experience, just outside the Siril window). PNG and CSV export both work normally.

---

## 13. Use Cases & Workflows

### Use Case 1: Understanding what a galaxy field really shows (3 minutes)

**Scenario:** You imaged the Leo Triplet and want to see at a glance how far M65, M66 and NGC 3628 really are compared with the foreground stars.

1. Load the plate-solved image in Siril, run CosmicDepth 3D.
2. Leave defaults (Galaxies + Stars + main types ON, Log scale, Cosmic range, mag 12, 200 objects).
3. Click **Render 3D Map**.
4. Rotate the view so you're looking sideways at the image plane — the galaxies all sit at roughly the same enormous distance, foreground stars crowd near the plane.

**Result:** You can visually confirm all three galaxies are at ~30–35 Mly, and see how the handful of labelled HD stars sit at less than a thousandth of that distance.

### Use Case 2: Milky Way nebula with context

**Scenario:** Close-up of M42 (Orion Nebula, 1,344 ly) — you want a 3D view that shows only structure inside the Milky Way, ignoring any faint background galaxies that would otherwise dominate the log axis.

1. Run CosmicDepth 3D.
2. Set **Range = Galactic (< 100k ly)**.
3. Set **Scale = Hybrid**.
4. Enable Dark Nebulae and HII Regions for the extra context.
5. Render.

**Result:** All objects are inside the Milky Way, spaced with realistic linear proximity for nearby stars and logarithmic compression for cluster-range distances. No galaxy at infinity to skew the axis.

### Use Case 3: Galaxy cluster — dense field

**Scenario:** Abell 2151 (Hercules Cluster) with 150+ galaxies in frame.

1. Run CosmicDepth 3D.
2. Check **Galaxies** only in Include Objects, **Deselect All** then re-check just Gal.
3. Raise the magnitude limit to 16.
4. Raise **Max objects** to 500 so the cluster isn't truncated.
5. **Only objects with known distance** — ON (drop type-median fallbacks).
6. Render.

**Result:** A beautiful 3D scatter of a real galaxy cluster, showing the characteristic radial velocity spread at its distance (~500 Mly). Each marker is backed by a real SIMBAD distance.

### Use Case 4: Sharing an interactive scene

**Scenario:** You want to post the 3D view on a forum or send it to an imaging friend.

1. Render normally.
2. Rotate the view to an angle that reads well.
3. Click **Export HTML**. The file is standalone (~4 MB including plotly.js).
4. Upload it to a file-sharing service or attach to email.

**Result:** Recipient opens the HTML in any browser and gets the full interactive experience — no Siril, no Python, nothing to install.

### Use Case 5: Publication-ready figure

1. Render the scene with your preferred filters.
2. Rotate to the final angle you want in the figure.
3. Set **PNG DPI = 300**.
4. Click **Export PNG**.

**Result:** A 4200 × 3000 pixel static PNG captured from your exact viewing angle, with the stretched-log axis and ly-labelled ticks matching the live view.

### Use Case 6: Object-table audit

**Scenario:** One of the markers in your scene looks wrongly placed.

1. Switch to the **Objects** tab.
2. Click the **Source** column header to group by source.
3. Find the object — its source will be one of `svenesis cache`, `SIMBAD mesDistance`, `SIMBAD redshift`, or `Type median`.
4. If it's `Type median`, that's a fallback — the real distance is unknown for this object. Either filter it out (enable **Only objects with known distance**) or report it as a SIMBAD gap.
5. If it's `SIMBAD mesDistance` and still looks wrong, click **Clear Distance Cache** and re-render to rule out a stale cache entry.

---

## 14. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F5` | Render 3D Map |
| `Esc` | Close the window |

Mouse interactions in the embedded 3D view follow standard Plotly conventions (drag, scroll, double-click to reset).

---

## 15. Tips & Best Practices

1. **Start with defaults, then refine.** The defaults (main types ON, mag 12, 200 objects, Log + Cosmic, sky plane ON) produce good results for most plate-solved images. Adjust one knob at a time.
2. **Rotate before exporting PNG.** The export captures your current camera angle. Setting up the view you want takes ten seconds and makes a huge difference to the final image.
3. **Use the Objects tab as a sanity check.** If a marker looks implausibly placed, sort the table by **Distance** and check the **Source** column. Type-median fallbacks stick out immediately.
4. **The cache is your friend.** First render of a field is slow (SIMBAD queries), subsequent renders are near-instant. Experiment freely with scaling and filters once the cache is warm.
5. **Galactic range + Hybrid scale for pure Milky Way fields.** You get realistic spacing for nearby structure and nothing at "infinity" warping the axis.
6. **Adjust the stretched-log parameters (advanced).** The shape of the log axis is controlled by two constants at the top of the script: `LOG_STRETCH_THRESHOLD_LY` (default `1e8`, the ly value where stretching kicks in) and `LOG_STRETCH_FACTOR` (default `3.0`, how much wider each post-threshold decade is). Edit the script to reshape without touching the UI.
7. **All settings are persistent.** Object types, filters, scale/range, DPI, filename, Objects table column widths and sort order — all remembered across sessions via QSettings.
8. **Use `Only objects with known distance` for publications.** Nobody wants to defend a figure where half the markers are on a made-up distance.

---

## 16. Troubleshooting

### "Image is not plate-solved" error

Plate-solve the image first via **Tools → Astrometry → Image Plate Solver…** in Siril, then re-run the script.

### No objects found in the field

- Increase the magnitude limit (try 14 or 16).
- Enable more object types — particularly **HII Regions** and **Dark Nebulae** for Milky Way fields.
- Check the Log tab — it shows per-tile SIMBAD counts. Zero across all tiles usually means a network issue.

### "WebEngine import failed" banner in the 3D Map tab

See Section 12. Click **Repair WebEngine…** to open the opt-in repair dialog. If your Python is PEP 668 / externally managed, install `PyQt6-WebEngine` yourself matching your `PyQt6` minor version.

### 3D view is slow to respond on a huge image

The image plane is sampled at a grid proportional to the shorter image edge (capped at 400 × 400 samples). Very large mosaics naturally render a denser plane. If it's genuinely sluggish, temporarily turn off **Show image as sky plane** to work with just the abstract point cloud.

### SIMBAD query times out

Check your internet connection. SIMBAD is occasionally under maintenance — try again in 15 minutes. The local cache is unaffected.

### PNG export doesn't match the live view

- Make sure `kaleido` is installed: `pip install --upgrade kaleido`. The Log tab says "Exported PNG via Plotly/kaleido" on success or "Plotly PNG export failed … falling back to matplotlib" on failure.
- If you see the matplotlib fallback, the saved image won't pixel-match the embedded view — it uses a different renderer. Installing kaleido fixes this.

### Distance looks wrong for one object

Check the **Source** column in the Objects tab:
- `Type median` = fallback, real distance unknown.
- `SIMBAD redshift` = computed from z via Hubble law; errors of ~10–30 % are normal for galaxies with noisy redshifts.
- `SIMBAD mesDistance` = direct measurement; if this looks wrong, click **Clear Distance Cache** and re-render to pull a fresh value.

### Stretched-log axis still feels cramped

Tune the two constants at the top of the script:
```python
LOG_STRETCH_THRESHOLD_LY = 1.0e8   # where stretching kicks in
LOG_STRETCH_FACTOR       = 3.0     # how much wider each post-threshold decade is
```
Drop the threshold to `1e7` to start stretching earlier. Bump the factor to `4` or `5` for even more room in the far tail.

### Everything is in the wrong place after a SIMBAD update

Click **Clear Distance Cache** and re-render.

---

## 17. FAQ

**Q: Does the script modify my image?**
A: No. It reads the image and its WCS header, and writes export files. Your FITS file is never touched.

**Q: Do I need internet?**
A: For the **first** render of a field, yes — SIMBAD queries require a connection. Subsequent renders of the same field use the local distance cache and work offline.

**Q: Why is there a stretched-log scale instead of a plain log?**
A: Because the interesting far-galaxy tail (> 100 M ly) gets compressed to a few pixels under a plain log axis, even though that's where most of your galaxy markers end up. The stretched variant gives that tail three times more room on screen with no cost to the nearby structure. See Section 6.

**Q: Can I see exact distances for each object?**
A: Yes — hover any marker in the 3D view for a tooltip, or switch to the **Objects** tab for the full sortable table including uncertainty and source.

**Q: What if SIMBAD has no distance for an object?**
A: The priority chain falls back to redshift (if available), then to a sensible type-based median. Type-median fallbacks are labelled clearly (`Type median` in the Source column) and have large uncertainties. If you want to exclude them, enable **Only objects with known distance**.

**Q: Why is PyQt6-WebEngine a separate install?**
A: It's a large (~80 MB) native shared library that not every user needs. Siril bundles PyQt6 itself but not WebEngine, so the script probes it at startup and offers an opt-in install if it's missing or the ABI doesn't match. See Section 12.

**Q: Can I export a rotating animation / GIF?**
A: Not currently. The HTML export is fully interactive, so you can rotate it yourself after loading; a GIF export is on the backlog.

**Q: Why is the PNG export different from the embedded view in some cases?**
A: If `kaleido` isn't installed the export falls back to matplotlib, which renders a broadly similar but not pixel-identical image. Install kaleido (`pip install --upgrade kaleido`) for pixel parity.

**Q: Can I use my own distance data instead of SIMBAD?**
A: Not through the GUI currently. Advanced users can pre-populate the local cache JSON (`~/.config/svenesis/cosmic_depth_cache.json`) with their own distances — the script will prefer cached values over SIMBAD queries.

**Q: Does the sky plane have to be at X = 0?**
A: Yes, by design. "Earth" sits at X = 0 (or more precisely, the image plane is anchored there on the log axis, since log10(1) = 0). Every object is behind it. This preserves the "window onto the universe" metaphor.

**Q: What's the difference between Cosmic and Galactic range?**
A: Cosmic includes everything out to quasars at billions of ly. Galactic hard-cuts at 100,000 ly (the rough edge of the Milky Way). Use Galactic for pure Milky Way fields; use Cosmic for any field with external galaxies.

---

## Credits

**Developed by** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**License:** GPL-3.0-or-later

Part of the **Svenesis Siril Scripts** collection, which also includes:
- Svenesis Annotate Image
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
