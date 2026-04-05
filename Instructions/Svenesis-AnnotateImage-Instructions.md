# Svenesis Annotate Image — User Instructions

**Version 1.1.0** | Siril Python Script for Plate-Solved Image Annotation

> *Comparable to PixInsight's AnnotateImage script — but free, open-source, and tightly integrated with Siril.*

---

## Table of Contents

1. [What Is Annotate Image?](#1-what-is-annotate-image)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [Understanding the Catalogs](#6-understanding-the-catalogs)
7. [Object Types & Color Coding](#7-object-types--color-coding)
8. [Display Options](#8-display-options)
9. [Extras (Overlays)](#9-extras-overlays)
10. [Output Options](#10-output-options)
11. [Use Cases & Workflows](#11-use-cases--workflows)
12. [Keyboard Shortcuts](#12-keyboard-shortcuts)
13. [Tips & Best Practices](#13-tips--best-practices)
14. [Troubleshooting](#14-troubleshooting)
15. [FAQ](#15-faq)

---

## 1. What Is Annotate Image?

The **Svenesis Annotate Image** script takes your plate-solved astrophotography image and creates a beautiful annotated version with labeled deep-sky objects, named stars, coordinate grids, and field information — ready to share on social media, forums, or print.

Think of it as a **labeling machine** for your astrophotos. It combines:

- **Automatic object identification** — finds galaxies, nebulae, clusters, stars, and more in your field of view by querying 5 online data sources in parallel via live VizieR and SIMBAD queries
- **Publication-quality rendering** — color-coded markers, ellipses scaled to actual object size, and clean label placement with collision avoidance
- **Rich overlays** — coordinate grid, info box, compass rose, and color legend
- **One-click export** — saves annotated images as PNG, TIFF, or JPEG at configurable DPI

The result: a professional-looking annotated image that shows exactly what objects are in your field — perfect for sharing, learning, or documenting your imaging sessions.

---

## 2. Background for Beginners

### What Is Plate Solving?

**Plate solving** is the process of determining the exact sky coordinates of your image. It matches the star pattern in your photo against a star catalog to figure out where your telescope was pointing.

After plate solving, your image has a **WCS (World Coordinate System)** solution embedded in its FITS header. This tells software: "pixel (500, 300) corresponds to RA 12h 30m, DEC +41° 20'" — and so on for every pixel.

| Concept | Explanation |
|---------|-------------|
| **RA (Right Ascension)** | The "longitude" of the sky, measured in hours (0h – 24h). Think of it like an east-west position on the celestial sphere. |
| **DEC (Declination)** | The "latitude" of the sky, measured in degrees (-90° to +90°). The celestial equator is 0°, the north celestial pole is +90°. |
| **WCS** | World Coordinate System — the mathematical mapping between pixel coordinates and sky coordinates stored in the FITS header. |
| **FOV (Field of View)** | How much sky your image covers, measured in arcminutes or degrees. Depends on your focal length and sensor size. |
| **Pixel Scale** | How many arcseconds of sky each pixel covers (arcsec/pixel). Smaller values = higher resolution. |

### Why Annotate Your Images?

Annotating your astrophotos serves several purposes:

1. **Learning** — Discover what objects are hiding in your field of view. Many imagers are surprised to find faint galaxies or nebulae they didn't know were there.
2. **Sharing** — When you post an image on social media or a forum, an annotated version helps viewers understand what they're looking at.
3. **Documentation** — Keep a record of what you've imaged, with precise coordinates and field information.
4. **Planning** — By seeing what's in your field, you can decide whether to crop, reframe, or image the area again with a different focal length.

### What Are Deep-Sky Objects?

Deep-sky objects (DSOs) are anything beyond our solar system. They come in many types:

| Type | What It Is | Example |
|------|-----------|---------|
| **Galaxy** | A vast collection of billions of stars, gas, and dust | M31 (Andromeda), M51 (Whirlpool) |
| **Emission Nebula** | A cloud of gas that glows when energized by nearby hot stars | M42 (Orion Nebula), NGC 7000 (North America) |
| **Reflection Nebula** | A dust cloud that reflects light from nearby stars (bluish) | M78, NGC 7023 (Iris Nebula) |
| **Planetary Nebula** | A shell of gas expelled by a dying star (nothing to do with planets!) | M57 (Ring), M27 (Dumbbell) |
| **Open Cluster** | A loose group of young stars born together | M45 (Pleiades), NGC 869 (Double Cluster) |
| **Globular Cluster** | A dense, ancient ball of hundreds of thousands of stars | M13, NGC 5139 (Omega Centauri) |
| **Supernova Remnant** | The expanding debris from an exploded star | M1 (Crab Nebula), NGC 6960 (Veil Nebula) |
| **Dark Nebula** | An opaque dust cloud that blocks light from objects behind it | B33 (Horsehead), B78 (Pipe Nebula) |
| **HII Region** | A large region of ionized hydrogen — essentially a giant emission nebula | Sh2-155 (Cave Nebula), Sh2-240 (Simeis 147) |
| **Asterism** | A star pattern that is not a true cluster | Coathanger, Kemble's Cascade |
| **Quasar** | A quasi-stellar object or active galactic nucleus | 3C 273, Markarian 421 |

### What Is Magnitude?

**Magnitude** measures how bright an object appears. The scale is inverted and logarithmic:

- **Lower numbers = brighter** (Sirius, the brightest star, is magnitude -1.5)
- **Higher numbers = fainter** (the faintest objects your camera can capture might be magnitude 15+)
- Each step of 1 magnitude is about 2.5× in brightness

The magnitude limit slider in Annotate Image controls the faintest objects that get labeled. A limit of 12.0 catches most visually interesting objects. Go higher (14–16) to label fainter galaxies; go lower (8–10) for a cleaner, less cluttered annotation.

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
| **astropy** | Any recent | Auto-installed by the script |
| **astroquery** | Any recent | Auto-installed by the script — required for all catalog queries |
| **Internet connection** | — | Required for live VizieR and SIMBAD catalog queries |

### Installation

1. Download `Svenesis-AnnotateImage.py` from the [GitHub repository](https://github.com/sramuschkat/Siril-Scripts).
2. Place it in your Siril scripts directory:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Restart Siril. The script appears under **Processing → Scripts**.

The script automatically installs missing Python dependencies (`numpy`, `PyQt6`, `matplotlib`, `astropy`, `astroquery`) on first run.

---

## 4. Getting Started

### Step 1: Load a Plate-Solved Image

The script requires a **plate-solved image** loaded in Siril. This means your FITS image must have WCS coordinates in its header.

**If your image is already plate-solved:**
1. Open the image in Siril (File → Open, or drag and drop).
2. You're ready to go!

**If your image is NOT plate-solved:**
1. Load the image in Siril.
2. Go to **Tools → Astrometry → Image Plate Solver...**
3. Enter the approximate coordinates of your target (or let Siril auto-detect).
4. Click **Solve**. Siril will match your star field to a catalog and compute the WCS solution.
5. Save the image (the WCS is stored in the FITS header).

**How do I know if my image is plate-solved?**
- In Siril, plate-solved images show coordinate information in the status bar at the bottom.
- The Annotate Image script checks this automatically and tells you if the image is not plate-solved.

### Step 2: Run the Script

Go to **Processing → Scripts → Svenesis Annotate Image**.

The script opens a window with:
- A **left panel** with all configuration controls
- A **right panel** with a preview area and log output
- An info bar showing the image dimensions and plate-solve status

### Step 3: Configure Your Annotation

1. **Select object types** — Check or uncheck which kinds of objects to annotate (Galaxies, Nebulae, Stars, etc.)
2. **Set the magnitude limit** — Controls how faint objects can be. 12.0 is a good default.
3. **Adjust display settings** — Font size, marker size, common names, etc.
4. **Choose overlays** — Coordinate grid, info box, compass, legend
5. **Set output format** — PNG (recommended), TIFF, or JPEG, with DPI setting

### Step 4: Annotate!

Click **"Annotate Image"** (or press **F5**).

The script will:
1. Load the image and WCS data from Siril
2. Search all online catalogs for objects in your field of view (VizieR and SIMBAD queried in parallel)
3. Deduplicate results across catalogs
4. Resolve label collisions so labels don't overlap
5. Render the annotated image with all selected overlays
6. Save the output file to Siril's working directory

A progress bar shows the current step. When done, the annotated image appears in the **Preview** tab.

### Step 5: View Your Result

- Click **"Open Annotated Image"** to view the full-resolution output in your default image viewer
- Click **"Open Output Folder"** to navigate to the output directory
- Check the **Log** tab for details about which catalogs were searched, how many objects were found, and the output file path

---

## 5. The User Interface

The window is divided into two main areas:

### Left Panel (Control Panel)

The left side (360px wide) contains all configuration controls, organized in collapsible sections:

- **Annotate Objects:** Object type checkboxes with color-coded labels in a two-column layout. The left column contains common types that are ON by default (Galaxies, Nebulae, Planetary Nebulae, Open Clusters, Globular Clusters, Stars). The right column contains specialized types that are OFF by default (Reflection Nebulae, Supernova Remnants, Dark Nebulae, HII Regions, Asterisms, Quasars). Select All / Deselect All buttons at the bottom.
- **Display:** Font size, marker size, magnitude limit (all with sliders). Checkboxes in a two-column layout below the sliders for ellipses, magnitude labels, type labels, common names, and color-by-type.
- **Extras:** Checkboxes in a two-column layout for coordinate grid, info box, compass, color legend, and leader lines.
- **Output:** Format selector (PNG/TIFF/JPEG), DPI slider (72–300), base filename
- **Actions:** "Annotate Image" button, progress bar, status label

At the bottom: **Buy me a Coffee**, **Help**, and **Close** buttons.

### Right Panel (Preview & Log)

The main area has two tabs:

#### Preview Tab
Displays the annotated output image after rendering. The preview scales to fit the window and updates its aspect ratio when the window is resized. Before annotation, it shows "Preview will appear here after annotation."

#### Log Tab
A monospace text area showing detailed progress and diagnostic information:
- Image dimensions and plate-solve status
- WCS detection strategy used
- Center coordinates and pixel scale
- Per-catalog object counts
- Each annotated object with name, type, and magnitude
- Output file path and size

### Info Bar

Above the tabs, a status bar shows:
- Image dimensions (e.g., "4656 × 3520 px")
- Color mode ("RGB" or "Mono")
- Plate-solve status ("plate-solved ✓" or "NOT plate-solved ✗")

### Output Buttons

Below the tabs:
- **Open Output Folder** — opens the directory containing the output file
- **Open Annotated Image** — opens the annotated image in your default viewer

---

## 6. Understanding the Catalogs

The script queries **5 online data sources** in parallel via live VizieR and SIMBAD queries. There are no embedded catalogs — all object data comes from the internet at annotation time.

| Data Source | Catalog ID | What It Contains |
|-------------|-----------|-----------------|
| **VizieR VII/118** | NGC 2000.0 | NGC, IC, and Messier objects — the core deep-sky catalogs covering galaxies, nebulae, and clusters |
| **VizieR VII/20** | Sharpless (1959) | HII regions — ionized hydrogen emission complexes, best for wide-field Milky Way images |
| **VizieR VII/220A** | Barnard (1927) | Dark nebulae — opaque dust clouds that block background light |
| **VizieR V/50** | Yale Bright Star Catalogue (BSC) | Named bright stars for field identification |
| **SIMBAD** | TAP query | UGC, Abell, Arp, Hickson, Markarian, vdB, PGC, MCG objects, plus common name resolution for all objects |

### How Catalogs Work

All 5 data sources are **always queried** in parallel using a ThreadPoolExecutor — the object type checkboxes control *which kinds* of objects are displayed, not which catalogs are searched. For example, if you check only "Galaxies," the script queries all 5 sources but only shows galaxy-type objects from any of them.

This means:
- **M31** comes from VizieR NGC 2000.0 as a Galaxy
- **NGC 7000** comes from VizieR NGC 2000.0 as an Emission Nebula
- **Sh2-240** comes from VizieR Sharpless as an HII Region
- **B33** comes from VizieR Barnard as a Dark Nebula
- **Vega** comes from the Yale BSC
- **UGC 12345** comes from SIMBAD

### Deduplication

Objects that appear in multiple data sources (e.g., M42 is also NGC 1976) are automatically deduplicated by name and spatial proximity. When two results refer to the same object, the more commonly known designation takes priority — so Messier designations take priority over NGC, which takes priority over IC.

### SIMBAD

SIMBAD is **always queried automatically** alongside the VizieR catalogs. It provides:

- Faint galaxies (UGC, MCG, PGC catalogs)
- Abell galaxy clusters
- Arp peculiar galaxies and Hickson compact groups
- Markarian galaxies
- vdB reflection nebulae
- Common name resolution for all objects
- Additional NGC/IC objects not in the VizieR VII/118 selection

**Requirements:** Internet connection and the `astroquery` Python package. Junk entries from survey catalogs (SDSS, 2MASS, WISE, FAUST, IRAS, etc.) are automatically filtered out.

---

## 7. Object Types & Color Coding

Each object type has a unique color for easy identification:

| Color | Type | Description | Examples |
|-------|------|-------------|----------|
| **Gold** | Galaxies | Spiral, elliptical, irregular galaxies | M31, M51, M81, NGC 4565 |
| **Red** | Emission Nebulae | Glowing gas clouds (HII, star-forming regions) | M42 (Orion), M8 (Lagoon), M16 (Eagle) |
| **Light Red** | Reflection Nebulae | Dust clouds reflecting starlight | M78, NGC 7023 (Iris), Witch Head |
| **Green** | Planetary Nebulae | Dying star shells | M57 (Ring), M27 (Dumbbell), Helix |
| **Light Blue** | Open Clusters | Young star groups | M45 (Pleiades), Double Cluster |
| **Orange** | Globular Clusters | Ancient dense star balls | M13, Omega Centauri, 47 Tucanae |
| **Magenta** | Supernova Remnants | Explosion debris | M1 (Crab), Veil Nebula, Simeis 147 |
| **Grey** | Dark Nebulae | Opaque dust clouds | B33 (Horsehead), B78 (Pipe) |
| **Red-Pink** | HII Regions | Sharpless ionized hydrogen regions | Heart, Soul, Barnard's Loop |
| **Pale Blue** | Asterisms | Star patterns, not true clusters | Coathanger, Kemble's Cascade |
| **Violet** | Quasars | QSOs and AGN | 3C 273, Markarian 421 |
| **White** | Named Stars | Bright stars from Yale BSC and SIMBAD | Vega, Deneb, Polaris, Betelgeuse |

### Default Settings

By default, the **left column** types are **enabled** (ON): Galaxies, Emission Nebulae, Planetary Nebulae, Open Clusters, Globular Clusters, Named Stars.

By default, the **right column** types are **disabled** (OFF): Reflection Nebulae, Supernova Remnants, Dark Nebulae, HII Regions, Asterisms, Quasars. (These can produce a lot of labels on wide-field images or are specialized types; enable them when relevant.)

### Magnitude Limit

The magnitude limit (default: 12.0) controls the faintest objects that get annotated. Objects brighter than the limit are shown; fainter objects are hidden.

**Exception:** Dark nebulae from the Barnard catalog have no magnitude and are always shown regardless of the magnitude limit.

**Guidelines:**
- **8–10:** Very clean annotation — only the brightest, most prominent objects
- **12.0:** Good default — catches most visually interesting objects
- **14–16:** Dense annotation — includes many faint galaxies and nebulae
- **18–20:** Very dense — may be cluttered on wide-field images

---

## 8. Display Options

### Font Size (6–24 pt)

Controls the text size of object labels. Default: 10 pt.
- **Larger (14–18):** Good for social media sharing where the image will be viewed at reduced size
- **Smaller (8–10):** Good for high-resolution prints or when there are many objects in the field

### Marker Size (8–60 px)

Controls the size of crosshair markers for point-like objects. Default: 20 px.
- Only affects objects that don't have catalog angular size data (or when ellipses are disabled)

### Show Object Size as Ellipse

When **enabled** (default): Extended objects (galaxies, nebulae) are drawn as ellipses proportional to their cataloged angular size. This gives a visual sense of how large each object really is.

When **disabled**: All objects get simple crosshair markers, regardless of size. Produces a cleaner, more uniform look.

### Show Magnitude in Label

When enabled, appends the visual magnitude to each label:
- `M31 3.4m` instead of just `M31`
- Useful for understanding relative brightness of objects in the field

### Show Object Type in Label

When enabled, appends the type designation:
- `M31 [Galaxy]` instead of just `M31`
- Helpful for viewers unfamiliar with catalog designations

### Show Common Names

When **enabled** (default): Shows popular names where available. Common names are resolved via a SIMBAD TAP query and filtered to exclude catalog-like identifiers (FAUST, IRAS, 2MASS, SDSS, etc.) so only recognizable names are displayed:
- `M31 (Andromeda Galaxy)` instead of just `M31`
- `NGC 7000 (North America Nebula)`

When **disabled**: Shows only the catalog designation for a more compact look.

### Color by Object Type

When **enabled** (default): Uses the color scheme from Section 7 — different colors for different object types.

When **disabled**: All annotations use a uniform light grey color. Produces a more uniform look but makes it harder to distinguish object types at a glance.

---

## 9. Extras (Overlays)

### Coordinate Grid (RA/DEC)

**Default: ON**

Overlays a semi-transparent equatorial coordinate grid with RA and DEC labels. Grid spacing is chosen automatically based on your field of view:

| FOV | Grid Spacing |
|-----|-------------|
| < 15' | 3' (0.05°) |
| 15'–30' | 6' (0.1°) |
| 30'–1.5° | 15' (0.25°) |
| 1.5°–3° | 30' (0.5°) |
| 3°–6° | 1° |
| > 6° | 2°–5° |

The grid aims for approximately 5 lines across the field. RA labels are in hours/minutes/seconds format; DEC labels are in degrees/arcminutes/arcseconds format.

### Info Box

**Default: ON**

A semi-transparent box in the top-left corner displaying:
- **Object name** (from FITS header, if available)
- **Center coordinates** (RA and DEC of the image center)
- **Field of view** (width × height in arcminutes)
- **Pixel scale** (arcseconds per pixel)
- **Rotation angle** (degrees, from the WCS CD matrix)
- **Objects annotated** (total count)

### Compass (N/E Arrows)

**Default: OFF**

Shows North and East direction arrows in the bottom-right corner. The arrows are computed from the WCS solution, so they accurately reflect image orientation, rotation, and mirroring.

Useful when your image is rotated or flipped — the compass shows which way is "up" (North) and "left" (East) in astronomical convention.

### Color Legend

**Default: ON**

An auto-generated legend box in the bottom-left corner showing color swatches for each object type present in the annotation. Only types that actually appear in the annotated image are listed — so if your field has no planetary nebulae, that color won't appear in the legend.

### Leader Lines

**Default: ON**

Thin connecting lines drawn from each label to its object marker. These are essential in crowded fields where labels have been offset by the collision avoidance algorithm — they show which label belongs to which object.

Can be disabled for a cleaner look on sparse fields where the connection between label and object is obvious.

---

## 10. Output Options

### Format

| Format | Compression | Best For |
|--------|------------|----------|
| **PNG** (default) | Lossless | Sharing online, forums, social media. Recommended default. |
| **TIFF** | Lossless | Further editing in image editors. Larger files. |
| **JPEG** | Lossy | Web uploads, email attachments. Smallest file size. |

### DPI (72–300)

Controls the output resolution (dots per inch):
- **72 DPI:** Smallest file size, good for quick previews
- **150 DPI (default):** Good balance for screens and social media
- **300 DPI:** Print quality. Produces large files but maximum detail.

### Filename

The base name for the output file (default: `annotated`). A timestamp is appended automatically to prevent overwriting:
```
annotated_20250315_221430.png
```

### Output Location

The annotated image is saved in **Siril's working directory** — the same folder as your image files.

---

## 11. Use Cases & Workflows

### Use Case 1: Quick Social Media Post (2 minutes)

**Scenario:** You just finished processing an image of the Orion region and want to share an annotated version on Instagram or a forum.

**Workflow:**
1. Load your plate-solved, processed image in Siril
2. Run Annotate Image
3. Leave defaults (all major object types enabled, magnitude 12.0, PNG, 150 DPI)
4. Click **Annotate Image** (F5)
5. Click **Open Annotated Image** to preview
6. Share the output file directly

**Result:** A clean annotation with Messier and NGC objects labeled, coordinate grid, info box, and legend.

### Use Case 2: Wide-Field Milky Way Annotation

**Scenario:** You have a wide-field image of a Milky Way region and want to label all the nebulae and HII regions.

**Workflow:**
1. Load the plate-solved wide-field image
2. Run Annotate Image
3. Enable **HII Regions** and **Dark Nebulae** (disabled by default)
4. Increase the magnitude limit to 14 or higher
5. Consider increasing font size to 12–14 for readability at reduced viewing size
6. Click **Annotate Image**

**Result:** A richly annotated image showing Sharpless HII regions, Barnard dark nebulae, and all the usual DSOs — perfect for identifying structures in a Milky Way panorama.

### Use Case 3: Galaxy Field Identification

**Scenario:** You've imaged a field in Virgo or Coma Berenices and want to identify all the galaxies.

**Workflow:**
1. Load the plate-solved image
2. Run Annotate Image
3. Deselect all types except **Galaxies**
4. Increase magnitude limit to 14–16
5. Disable common names for a cleaner look (many faint galaxies don't have common names anyway)
6. Click **Annotate Image**

**Result:** Every galaxy in the field is labeled with its catalog designation, including faint background galaxies discovered via SIMBAD.

### Use Case 4: Print-Quality Annotated Image

**Scenario:** You want a high-resolution annotated image for printing or publishing.

**Workflow:**
1. Load your best plate-solved image
2. Run Annotate Image
3. Set **DPI to 300** for maximum resolution
4. Set **Format to TIFF** for lossless output
5. Increase font size to 12–14 (labels need to be readable at print size)
6. Enable all overlays: grid, info box, compass, legend
7. Click **Annotate Image**

**Result:** A publication-ready annotated image at full resolution.

### Use Case 5: Star Identification Only

**Scenario:** You want to identify the bright stars in your field to understand the constellation context.

**Workflow:**
1. Load the plate-solved image
2. Run Annotate Image
3. Deselect all types except **Named Stars**
4. Set magnitude limit to 5 or 6 (only naked-eye-visible stars)
5. Disable the coordinate grid and info box for a cleaner look
6. Click **Annotate Image**

**Result:** A clean annotation showing only named stars from the Yale Bright Star Catalogue and SIMBAD HD stars — Vega, Deneb, Altair, constellation stars, etc.

### Use Case 6: Minimal Clean Annotation

**Scenario:** You want a subtle annotation that doesn't overwhelm your beautifully processed image.

**Workflow:**
1. Load the image and run Annotate Image
2. Reduce font size to 8
3. Disable: magnitude labels, type labels, leader lines
4. Disable: coordinate grid, compass
5. Keep: common names, info box, color legend
6. Set magnitude limit to 10 (only the brightest objects)
7. Click **Annotate Image**

**Result:** A tasteful, minimal annotation with just the main objects labeled — the image remains the star of the show.

### Use Case 7: Educational / Presentation Annotation

**Scenario:** You're preparing a presentation or educational material and want a maximally informative annotation.

**Workflow:**
1. Load the plate-solved image
2. Enable all object types including HII Regions, Dark Nebulae, Asterisms, and Quasars
3. Enable: magnitude labels, type labels, common names
4. Enable all extras: grid, info box, compass, legend
5. Set font size to 12 for readability
6. Click **Annotate Image**

**Result:** A densely labeled, maximally informative annotation showing everything in the field with type designations, magnitudes, and all overlays.

### Use Case 8: Comparing Different Annotation Settings

**Scenario:** You want to create multiple versions of the same image with different annotation styles.

**Workflow:**
1. Load the image once
2. Create a "busy" version with all types, high magnitude limit, all extras
3. Change the base filename to `annotated_full`
4. Click **Annotate Image**
5. Create a "clean" version: deselect HII/Dark Nebulae, lower magnitude limit to 10, disable grid
6. Change filename to `annotated_clean`
7. Click **Annotate Image** again

The timestamp in the filename ensures you never overwrite a previous output. All versions are saved in the working directory.

---

## 12. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F5` | Run annotation (same as clicking "Annotate Image") |
| `Esc` | Close the window |

---

## 13. Tips & Best Practices

### Image Preparation

1. **Always plate-solve first.** The script cannot annotate without a WCS solution. If plate solving fails, check that your image has enough stars and your focal length is approximately correct.

2. **Use your processed (stretched) image.** The script uses Siril's autostretch preview, but starting with a well-processed image gives the best-looking background for the annotation.

3. **Save your image before annotating.** If the WCS data was just computed but the FITS file wasn't saved, the script may have difficulty reading the WCS. Saving ensures the header is complete.

### Annotation Settings

4. **Start with defaults, then adjust.** The default settings (magnitude 12.0, main object types enabled, grid + info box + legend) produce good results for most images. Customize from there.

5. **Match font size to intended viewing size.** For images that will be viewed full-screen on a monitor, 10 pt is fine. For images that will be viewed as thumbnails on social media, increase to 14–16 pt.

6. **The magnitude limit is your primary control for annotation density.** Lower it to reduce clutter; raise it to find hidden objects. This is the single most effective way to tune how busy or clean your annotation looks. Experiment with different values to find the sweet spot for your image.

7. **Dark nebulae and HII regions are best for wide-field images.** On narrow-field images (small FOV), these large structures often extend beyond the frame edges, producing labels for objects you can't really see.

### Output

9. **PNG is the best all-around format.** Lossless compression, reasonable file size, and universal compatibility. Use TIFF only if you plan to edit the annotated image further.

10. **150 DPI is sufficient for screen viewing.** Only increase to 300 DPI if you need print quality — it quadruples the file size.

11. **All settings are persistent.** The script remembers your last-used settings (object types, display options, DPI, format) between sessions via QSettings. You don't need to reconfigure every time.

---

## 14. Troubleshooting

### "Image is not plate-solved" error

**Cause:** The current image in Siril doesn't have a WCS solution in its FITS header.
**Fix:** Plate-solve the image first: **Tools → Astrometry → Image Plate Solver...** Then run the script again.

### "No image loaded" error

**Cause:** No image is currently loaded in Siril.
**Fix:** Open a FITS image in Siril before running the script.

### WCS appears plate-solved but "could not be read"

**Cause:** The WCS data is present in Siril's memory but not fully written to the FITS header.
**Fix:** Save the image as FITS first (File → Save), then reload it and run the script again. The script uses a 6-step fallback strategy to read WCS data, but sometimes a fresh save is needed.

### No objects found in the field

**Cause:** The field of view may not contain any catalog objects above the magnitude limit, or the magnitude limit is too restrictive.
**Fix:**
- Increase the magnitude limit (e.g., from 12 to 15)
- Enable additional object types (HII Regions, Dark Nebulae, Asterisms)
- Check the Log tab — it shows exactly which catalogs were searched and how many objects were found

### Annotation is too cluttered

**Cause:** Too many object types enabled, or magnitude limit too high.
**Fix:**
- Lower the magnitude limit (e.g., from 15 to 10)
- Disable HII Regions and Dark Nebulae
- Disable Named Stars if star labels aren't needed
- Reduce font size
- Disable magnitude and type labels

### Annotation is slow

**Cause:** All 5 data sources are queried over the internet in parallel. Wide-field images may trigger tiled queries to cover the full field.
**Fix:**
- This is normal for the first annotation of a given field — subsequent runs benefit from caching
- Wide-field mosaics require more queries to cover the larger sky area
- Check your internet connection if queries are timing out
- The Log tab shows the progress of each catalog query

### SIMBAD query fails

**Cause:** SIMBAD is always queried automatically. A failure may be caused by no internet connection, SIMBAD server maintenance, or a timeout.
**Fix:** The script handles SIMBAD failures gracefully — it falls back to VizieR-only results. You will still get annotations from the NGC 2000.0, Sharpless, Barnard, and Yale BSC catalogs. Check the Log tab for the specific error. If SIMBAD is temporarily down, try again later.

### Output file is very large

**Cause:** High DPI setting (300) with TIFF format on a large sensor image.
**Fix:** Reduce DPI to 150, or switch to PNG format. A 4656×3520 image at 300 DPI in TIFF can be 50+ MB; at 150 DPI in PNG it's typically 5–15 MB.

### Font warning: "Sans-serif"

**Message:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"...`
**Impact:** Cosmetic only, no effect on functionality. Can be safely ignored.

### Labels overlapping despite collision avoidance

**Cause:** In very crowded fields (galaxy clusters, dense Milky Way regions), the 32-candidate placement algorithm may not find a collision-free position for every label.
**Fix:** Reduce the number of labeled objects by lowering the magnitude limit or disabling some object types. The collision avoidance works best with fewer than ~50 objects.

---

## 15. FAQ

**Q: Does this replace PixInsight's AnnotateImage script?**
A: For most purposes, yes. It offers the same core functionality — catalog object labeling on plate-solved images — with additional features like a graphical interface, live online catalog queries, and persistent settings. PixInsight's script supports a few additional catalog sources, but Annotate Image's 5 online data sources cover the vast majority of interesting objects.

**Q: Can I annotate non-plate-solved images?**
A: No. The script requires WCS coordinates to know where each pixel points on the sky. Without plate solving, it cannot determine which objects are in your field. Plate solving in Siril is quick and free — there's no reason not to do it.

**Q: Does the script modify my original image?**
A: No. The script reads your image for display purposes and creates a **new** file with the annotations. Your original FITS file is never modified.

**Q: Does the script need an internet connection?**
A: Yes. All catalog data comes from live VizieR and SIMBAD queries over the internet. Without a connection, the script cannot retrieve object data and annotation will fail.

**Q: Can I annotate color (RGB) and mono images?**
A: Yes. The script handles both RGB and single-channel (mono) images. Mono images are automatically converted to 3-channel for the annotated output.

**Q: Why are some objects drawn as ellipses and others as crosshairs?**
A: Objects with known angular sizes in the catalog (most galaxies, large nebulae) are drawn as ellipses scaled to their real size. Objects without size data, or when the "Show object size as ellipse" option is disabled, get simple crosshair markers.

**Q: Why don't I see any Barnard (dark nebulae) objects?**
A: Dark Nebulae are **disabled by default** to keep annotations clean. Enable the "Dark Nebulae" checkbox in the Annotate Objects section. Note that dark nebulae bypass the magnitude limit — they're always shown when enabled.

**Q: Why don't I see any Sharpless (HII region) objects?**
A: HII Regions are also **disabled by default**. Enable the "HII Regions" checkbox. Sharpless objects are large-scale structures best seen on wide-field images.

**Q: How does the script handle large mosaic images?**
A: The script includes automatic display downscaling, DPI capping, and memory management to handle large mosaics. Very large images are downscaled internally for rendering to avoid excessive memory usage, while the output maintains appropriate quality for the selected DPI setting.

**Q: Can I customize the colors?**
A: Not through the GUI currently. The color scheme is defined in the script source code (`DEFAULT_COLORS` dictionary). Advanced users can edit the script to change colors.

**Q: Where is the output file saved?**
A: In Siril's working directory (the same folder as your image files). The full path is shown in the Log tab after annotation.

**Q: Can I run the script multiple times on the same image?**
A: Yes! Each run creates a new output file with a timestamp in the filename. You can experiment with different settings without overwriting previous results.

**Q: How does the WCS detection work?**
A: The script uses a 6-step fallback strategy to extract WCS data from Siril:
1. FITS header as dictionary → build WCS directly
2. FITS header as string → parse into WCS
3. Check Siril keywords for plate-solve flag
4. Build WCS by sampling `pix2radec` at three points
5. Try `pix2radec` even without plate-solve flag
6. Read the FITS file from disk as last resort

This ensures compatibility with different Siril versions and plate-solving methods.

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
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*If you find this tool useful, consider supporting development via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
