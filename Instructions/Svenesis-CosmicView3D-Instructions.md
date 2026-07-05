# Svenesis GalacticView 3D — User Instructions

**Version 1.0.0** | Siril Python Script for Visualizing Where Your Photo Points in the Universe

> *Your photo is not just anywhere. It is a window into one specific direction of the universe — and now you can see exactly where. GalacticView 3D places Earth in the Orion Arm, hangs your plate-solved image along its true line of sight, and lets you fly the light path from Earth to the target.*

---

## Table of Contents

1. [What Is GalacticView 3D?](#1-what-is-galacticview-3d)
2. [Background for Beginners](#2-background-for-beginners)
3. [Prerequisites & Installation](#3-prerequisites--installation)
4. [Getting Started](#4-getting-started)
5. [The User Interface](#5-the-user-interface)
6. [View Modes — Galactic vs. Cosmic](#6-view-modes--galactic-vs-cosmic)
7. [Story vs. Explorer View Styles](#7-story-vs-explorer-view-styles)
8. [The Story Card](#8-the-story-card)
9. [Journey Mode & the Opening Pull-Back](#9-journey-mode--the-opening-pull-back)
10. [Navigating the 3D Scene](#10-navigating-the-3d-scene)
11. [Reading the Scene — What Every Element Means](#11-reading-the-scene--what-every-element-means)
12. [Distance Resolution — Where the Numbers Come From](#12-distance-resolution--where-the-numbers-come-from)
13. [The Distance-Metric Toggle](#13-the-distance-metric-toggle)
14. [The Target Picker](#14-the-target-picker)
15. [Export (HTML / PNG / CSV)](#15-export-html--png--csv)
16. [Keyboard Shortcuts](#16-keyboard-shortcuts)
17. [Tips & Best Practices](#17-tips--best-practices)
18. [Troubleshooting](#18-troubleshooting)
19. [FAQ](#19-faq)
20. [Scientific Background & Accuracy](#20-scientific-background--accuracy)

---

## 1. What Is GalacticView 3D?

The **Svenesis GalacticView 3D** is a Siril Python script that answers a question no other astrophotography tool answers:

> *"My photo is not just anywhere — it is a window into one specific direction of the universe. Where exactly?"*

It reads your currently loaded, **plate-solved** image from Siril, identifies the main astronomical object via SIMBAD, and renders an interactive 3D scene in which:

- **Earth sits in the Orion Arm** of the Milky Way, at its correct position ~26,000 light-years from the Galactic Center.
- **Your astrophoto** is placed as a textured rectangle in 3D space, pointing along the exact viewing direction that produced it.
- A **viewing ray** runs from Earth to the photo, showing literally where your telescope was aimed.
- The target's **distance is made tangible** through a story card, scale rings, and a cinematic **Journey** flight from Earth all the way out to the object.

Where the sibling tool **CosmicDepth 3D** shows the *depth* of everything *inside* one photo, GalacticView 3D zooms out to show *where that whole photo sits* in the structure of the galaxy and the universe.

---

## 2. Background for Beginners

### Why "3D" from a 2D photo?

A photograph is a flat projection: everything in it lies along one direction from Earth, but at wildly different distances. A single plate-solved image gives us two crucial facts — the **direction** it points (precisely, from the WCS solution) and the **distance** to its main subject (from SIMBAD). With those two, we can place the whole photo at its true position in a 3D model of the galaxy.

### What does "plate-solved" mean?

Plate-solving matches the star pattern in your image against a catalog and writes a **WCS** (World Coordinate System) solution into the file. This lets the script convert any pixel into a precise sky coordinate (right ascension / declination). GalacticView 3D **requires** a plate-solved image — without WCS, it cannot know which way your photo points.

In Siril: **Tools → Astrometry → Image Plate Solver…**

### Galactic vs. cosmic scale

The Milky Way is ~100,000 light-years across. The nearest large galaxy, Andromeda, is 2.5 *million* light-years away. Distant galaxies are *billions*. No single linear ruler can show a 500-light-year nebula and a 2-billion-light-year quasar in the same frame. GalacticView 3D solves this with two modes and a log-compressed cosmic scale (explained in §6).

### What is the Orion Arm?

Our Sun sits in a minor spiral arm called the **Orion Arm** (or Orion Spur), between the larger Sagittarius and Perseus arms. GalacticView 3D highlights it because that is *your* address in the galaxy — every photo you take is taken from here.

---

## 3. Prerequisites & Installation

### Requirements

- **Siril 1.4+** with Python script support
- **sirilpy** (bundled with Siril)
- A **plate-solved** image loaded in Siril
- **Internet connection** for the first SIMBAD query of a target (results are cached afterward)
- Python packages, installed automatically on first run via `s.ensure_installed`:
  `numpy`, `PyQt6`, `matplotlib`, `astropy`, `astroquery`, `plotly`, `Pillow`, `kaleido`, `requests`
- **PyQt6-WebEngine** — for the interactive in-window 3D view. Probed at startup; if missing or ABI-mismatched against Siril's bundled PyQt6, the script falls back to a static matplotlib view (no live rotation).

### Installation

1. Place `Svenesis-GalacticView3D.py` in a folder named **Utility** inside one of Siril's Script Storage Directories.
2. Restart Siril (or refresh the scripts menu).
3. The script appears under **Scripts** in Siril's menu.

The first run installs any missing Python packages — this can take a minute. Subsequent runs are fast.

---

## 4. Getting Started

### Step 1 — Load and plate-solve an image

Open any deep-sky image in Siril and plate-solve it (**Tools → Astrometry → Image Plate Solver…**). A single-object subject — a galaxy, nebula, or cluster — works best.

### Step 2 — Run the script

**Processing → Scripts → Svenesis GalacticView 3D**. The window opens maximized.

### Step 3 — Render

Click **Render 3D Map** (or press **F5**). The script:

1. Reads the image and its WCS.
2. Queries SIMBAD for the main object and nearby candidates.
3. Opens the **Target Picker** — confirm the auto-detected subject or choose another candidate.
4. Resolves the distance and builds the scene.

### Step 4 — Watch the reveal

The view opens at **Earth's point of view** — the sky as you actually photographed it — then pulls back to reveal the full galactic map (the *opening pull-back*). A **story card** fades in over the scene, telling you where you pointed and how old the light is.

### Step 5 — Take the Journey

Press the **🚀 Journey** button (or the **J** key) to fly the light path from Earth all the way to your target, with a live counter showing distance and the light's age.

### Step 6 — Explore and export

Drag to rotate, mouse-wheel to zoom, hover any marker for details. Use **Export HTML / PNG / CSV** to share or archive.

---

## 5. The User Interface

### Left Panel (Controls)

- **View Mode** — Auto (default) / Galactic / Cosmic override.
- **Scene Elements:**
  - **View style** — Story (default) vs. Explorer (see §7).
  - **Opening pull-back animation** — on/off (plays once per target).
  - **Spiral arms**, **Disk stars**, **Neighbor galaxies (cosmic mode)**, **Photo rectangle + viewing ray**.
  - **Photo resolution (px)** — texture detail of the photo rectangle (auto-capped in cosmic mode for performance).
  - **Distance metric (cosmic mode)** — Light-travel / Comoving / Angular-diameter (see §13).
- **Main Object** — Name, Type, Distance of the identified subject.
- **Data Sources** — SIMBAD online toggle + cache-clear button.
- **Output** — export filename base and PNG DPI.
- **Actions** — Render, exports, Help.

### Right Panel (Tabs)

- **3D Map** — the interactive scene, with the camera button row below it (trackball, zoom, presets, 🚀 Journey, Spin).
- **Info** — a full scene overview: the story card, object data, and the Milky Way model parameters.
- **Log** — a timestamped event log (renders, SIMBAD queries, camera actions) — safe to paste into a bug report.

---

## 6. View Modes — Galactic vs. Cosmic

The mode is chosen automatically from the target's distance and SIMBAD type. You can override it any time.

### Galactic mode (< 150,000 ly)

- **Scale:** linear, 1 scene unit = 1,000 light-years.
- **Shows:** the five spiral arms, disk stars, central bulge, Sgr A* at the Galactic Center, Earth in the Orion Arm with its orbital-motion arrow, distance rings, and (for in-galaxy targets) the constellation stick figure and arm membership.
- **Answers:** *"Where inside our galaxy am I looking?"*

### Cosmic mode (≥ 150,000 ly)

- **Scale:** linear out to 1 Mly (1 unit = 100,000 ly), then **logarithmically compressed** beyond, so a 2-million-ly and a 2-billion-ly object both fit on screen. The transition is marked by a faint orange ring at **1 Mly**.
- **Shows:** neighbor galaxies (M31, M33, LMC, SMC, …), and in Explorer view: galaxy-cluster halos, cosmic landmarks, and the CMB observable-universe boundary.
- **Answers:** *"How tiny is the Milky Way, and where does my target sit among the galaxies?"*

### How the mode is decided

1. If SIMBAD's object type is extragalactic (Galaxy, Quasar, AGN, …) → **Cosmic**.
2. If it's an in-galaxy type (nebula, cluster, star, …) → **Galactic**.
3. Otherwise, by distance: ≥ 150,000 ly → **Cosmic**, else **Galactic**.

---

## 7. Story vs. Explorer View Styles

A single switch at the top of Scene Elements controls how much the scene shows.

| | **Story** (default) | **Explorer** |
|---|---|---|
| Goal | Clean, cinematic, legible | Complete reference map |
| Shows | Earth, viewing ray, photo, target, galaxy structure, distance rings | Everything Story shows **plus** all overlays |
| Extra overlays | — | Landmark catalogs, galaxy-cluster halos, CMB boundary, Local Bubble / Local Group spheres |

**Story** keeps only the narrative thread — the journey from your backyard to the target. **Explorer** turns the scene into a full atlas of the surrounding structure. Within Explorer, each overlay is individually toggleable from the plot legend.

Your chosen style persists across sessions.

---

## 8. The Story Card

The most human-facing feature. After each render, a short auto-generated paragraph tells you, in plain language:

- **Where you pointed** — galactic longitude, and whether you were looking into the disk or up toward the halo.
- **How old the light is** — anchored to Earth's history: *"…about 38.7 million years ago, when the ancestors of whales still walked on land."*
- **Which arm the target sits in** (for in-galaxy objects).
- **A scale analogy** — *"If the Milky Way were a dinner plate (25 cm across), your target would be another plate about 97 metres down the street."*

The story appears in three places: as a dismissible **toast** over the 3D view (fades after ~18 s, click to dismiss), permanently in the **Info tab**, and it is included in **CSV** exports and baked as a caption band into **PNG** exports.

The Earth-history anchors are chosen honestly: if no historical epoch is genuinely close (within a factor of ~2.5 of the light's age), the analogy is simply omitted rather than forced.

---

## 9. Journey Mode & the Opening Pull-Back

### The opening pull-back

The first render of a target starts the camera **at Earth's point of view** — looking out along your line of sight, the photo ahead of you, the sky as you saw it. After a beat, it pulls back smoothly to reveal the full 3D map. This is the "Powers of Ten" move: it grounds the abstract map in your actual vantage point.

It plays **once per target** (re-rendering the same object skips it) and can be disabled in Scene Elements. Any click, scroll, or key press cancels it.

### Journey mode

Press **🚀 Journey** (or **J**) to fly the camera from Earth along the viewing ray, all the way out to your target — an ~11-second cinematic tracking shot. A live HUD shows:

> **38.7 Mly from Earth**
> *the light in your photo passed this point 38.7 million years ago*
> ✦ *leaving the Local Group*

Waypoint callouts fire as you cross recognizable boundaries — leaving the Local Bubble, leaving the Milky Way's disk, passing Andromeda's distance, crossing the 1 Mly scale boundary, leaving the Local Group, passing Virgo. Only the waypoints actually on the route to your target appear.

Because the camera moves at constant speed through *scene* units, the light-year counter visibly **accelerates** past the 1 Mly boundary — you *feel* the logarithmic compression rather than just reading about it.

Any deliberate input (click, scroll, key) aborts the journey. Press **R** afterward to fly back home.

**Note:** the Journey button is greyed out when the render lacks a projected photo or a resolved distance — both are needed for the flight.

---

## 10. Navigating the 3D Scene

### Mouse

- **Drag** — orbit the camera.
- **Mouse-wheel** — zoom.
- **Hover** a marker — read its details.
- **Double-click** a spiral-arm entry in the legend — fly the camera to that arm.

### Camera button row (below the 3D view)

| Control | Action |
|---|---|
| **Trackball** | Drag to orbit (diagonals supported); wheel zooms. |
| **+ / −** | Zoom in / out. Past the camera limit, **magnifier mode** engages — the view keeps magnifying around the photo without limit; distant content falls out of the window. |
| **⟲** | Reset the camera and any magnifier zoom. |
| **Earth POV** | Fly to Earth's viewpoint, looking along the line of sight. The viewing ray pulses on arrival. |
| **Top / Side / Iso** | Orthogonal preset views; Iso is the default 3/4 perspective. |
| **🚀 Journey** | Fly the light path from Earth to the target (§9). |
| **Spin** | Toggle slow auto-rotation. |

### Rescue keys

Lost the scene? Press **R**, **Home**, or **Escape** to reset. Auto-rotate also kicks in after 10 seconds of inactivity as an ambient cue; any input cancels it.

---

## 11. Reading the Scene — What Every Element Means

### Always present

- **Earth** — a "you are here" target reticle at the origin (0, 0, 0). Hover it for your galactic coordinates and distance to the Galactic Center.
- **Your photo** — a textured rectangle at the target's distance, oriented along the true viewing direction.
- **Viewing ray** — the dotted amber line from Earth to the photo center: literally where you pointed.
- **Distance rings** — dotted circles marking scale. They fade with distance (nearer = brighter). Drawn flat like a radar screen, **except** the one ring nearest your target's distance, which becomes a spherical shell — *"your photo sits at this depth."*

### Galactic mode

- **Spiral arms** — five logarithmic-spiral curves (Norma, Scutum-Centaurus, Sagittarius, Orion, Perseus). They fade out as you zoom close to a nearby target so they don't clutter the view.
- **Disk stars + bulge** — a sense of the galaxy's shape.
- **Sgr A*** — the Galactic Center, a warm diamond at ~26,000 ly along +X.
- **Earth's orbital arrow** — a small cyan arrow showing our ~220 km/s motion around the galaxy.
- **Constellation stick figure** — the IAU constellation containing your target, drawn at the target's distance.
- **Local Bubble** (Explorer, targets ≤ 2 kly) — the supernova-carved cavity around the Solar System.
- **Galactic landmarks** (Explorer) — a catalog of famous objects (Pleiades, M42, M13, Veil, …) grouped by type.

### Cosmic mode

- **Neighbor galaxies** — M31, M33, LMC, SMC, M81/82, M51, Centaurus A, and more, with rich hover descriptions.
- **1 Mly scale boundary** — the orange ring marking where linear scale becomes logarithmic.
- **Galaxy clusters** (Explorer) — translucent halos for Virgo, Coma, Perseus, Shapley, and others.
- **Cosmic landmarks** (Explorer) — famous extragalactic objects (Sombrero, Cartwheel, 3C 273, …).
- **CMB boundary** (Explorer) — a faint wireframe globe at 13.8 billion light-years: the edge of the observable universe.

### Background depth sticks

When SIMBAD finds objects *behind* your target within the same photo, they are drawn at their true distance and connected by a thin line to their exact pixel position on your photo — showing you what else is in your frame, and how far away.

---

## 12. Distance Resolution — Where the Numbers Come From

The distance to your target is resolved through a priority chain — the first source that yields a value wins:

1. **Local cache** — a 90-day store in `~/.config/siril/svenesis_galacticview_cache.json`. Re-rendering a known target is instant and offline.
2. **SIMBAD `mesDistance`** — direct distance measurements from the literature (the most authoritative source). When several measurements exist, the one with the smallest uncertainty (compared in light-years) is chosen.
3. **Redshift → distance** — for distant galaxies, converted to light-travel distance via `astropy.cosmology.Planck18` (H₀ ≈ 67.4 km/s/Mpc). A linear-Hubble fallback is used only if the cosmology package is unavailable.
4. **Parallax** — for nearby stars, when reliable. A consistency check rejects SIMBAD's noise parallaxes on extragalactic objects (a galaxy with a spurious sub-milliarcsecond parallax is caught by its redshift).
5. **Type-based median** — a last-resort estimate from the object's SIMBAD type, **clearly labeled as an estimate** in the Info tab and CSV export.

Cone-search candidate lists are cached separately for 7 days, so re-renders of a known field need no network at all. A SIMBAD health probe shortens query timeouts during service outages, and all network calls run off the UI thread so the window never freezes.

---

## 13. The Distance-Metric Toggle

In cosmic mode, "distance" is not a single number — at high redshift, different definitions diverge significantly. The Scene Elements panel offers three:

| Metric | Meaning | Best for |
|---|---|---|
| **Light-travel** (default) | c × lookback time — how far the light travelled to reach us. Matches SIMBAD's redshift-derived distances. | *"How old is this image?"* |
| **Comoving** | The object's proper distance *now*, accounting for cosmic expansion since the light left. Always ≥ light-travel. | *"Where is it in the universe right now?"* |
| **Angular-diameter** | Comoving ÷ (1+z) — the distance that determines apparent angular size. | *"Why do high-z objects look deceptively close?"* |

Switching the metric **physically reorganizes** the 3D scene — every object's position updates. The HUD label at the bottom always states which metric is active. The underlying cosmology is `astropy.cosmology.Planck18`.

At the low redshifts of typical amateur targets the three metrics are nearly identical; the difference becomes dramatic only for distant quasars and the deep field.

---

## 14. The Target Picker

After the SIMBAD cone-search, a dialog lists every candidate object found in your image's field, with:

- **Name**, **Type**, **V magnitude**
- **Distance** with a source hint: `(z)` redshift, `(π)` parallax, `~` type estimate
- **Size in photo** and **offset from center**

The auto-detected main subject is pre-selected, but you can pick any candidate — useful for wide fields with several bright objects, or when you photographed a specific galaxy in a group. You can also export the full candidate list as JSON.

---

## 15. Export (HTML / PNG / CSV)

| Format | Contents |
|---|---|
| **HTML** | A standalone, fully interactive Plotly scene — including the story toast and Journey mode (press **J**). Self-contained (Plotly bundled inline), works offline, opens in any browser. |
| **PNG** | A snapshot of your current camera angle, with the story text appended as a caption band under the image. Captured from the live view when possible; falls back to kaleido / matplotlib. |
| **CSV** | Full scene metadata: object name, type, distance, galactic coordinates, viewing direction, redshift, lookback time, distance metric, cosmology used, arm membership, the story text, and the four photo-rectangle corners in 3D units. |

Two convenience buttons — **Open Output Folder** and **Open Exported HTML** — appear after an export.

---

## 16. Keyboard Shortcuts

| Key | Action |
|---|---|
| **F5** | Render the 3D map |
| **R** / **Home** / **Escape** | Reset the camera (and magnifier zoom) |
| **J** | Start the Journey (also works in exported HTML) |
| **Double-click** an arm in the legend | Fly the camera to that spiral arm |

---

## 17. Tips & Best Practices

- **Scene feels sluggish?** Lower the **Photo resolution** in Scene Elements — the textured photo is the biggest single GPU cost. 240 px renders far faster than 480 px with only mild quality loss (cosmic mode auto-caps it).
- **Scene too busy?** Switch to the **Story** view style. For finer control, toggle individual overlays from the plot legend (click to hide, double-click to isolate).
- **Zoom feels limited?** Keep pressing **+** — past the camera limit it enters **magnifier mode** and keeps diving toward the photo. Press **R** to return.
- **Best subjects:** a single dominant object (galaxy, nebula, cluster) gives the cleanest story. Very wide fields with many bright objects work too, but you'll pick the subject in the Target Picker.
- **Re-rendering is fast:** the distance and cone-search caches make repeat renders of the same target near-instant and offline-capable.
- **Read the story aloud.** It's designed to be the sentence you screenshot and share.

---

## 18. Troubleshooting

**"The image is not plate-solved."**
GalacticView 3D needs a WCS solution. Plate-solve first: **Tools → Astrometry → Image Plate Solver…**

**SIMBAD is slow or times out.**
The CDS SIMBAD service occasionally has outages. The script logs *SIMBAD tile timeout* and proceeds with whatever it retrieved; the health probe shortens timeouts automatically. Re-renders of cached targets stay fast and offline.

**The Journey button is greyed out.**
It needs both a projected photo rectangle and a resolved distance. Ensure **Photo rectangle + viewing ray** is enabled and the target has a known distance.

**The 3D view is blank / static.**
`PyQt6-WebEngine` may be missing or ABI-mismatched against Siril's PyQt6. The script falls back to a static matplotlib image. Check the Log tab for the WebEngine status line.

**The photo rectangle is tiny or invisible.**
Astrophoto fields of view (typically < 1°) project to a sub-pixel rectangle at galactic scale, so the script enlarges it around its center for visibility — orientation and aspect ratio are preserved. If it's still hard to see, use the **Face-on**-style presets or zoom in.

**Distances look wrong after an update.**
Cached distances persist for 90 days. If you suspect a stale value, use **Clear Distance Cache** in the Data Sources panel and re-render.

---

## 19. FAQ

**Q: Are the object positions physically accurate?**
The *directions* are exact (from your plate-solve and astropy's coordinate transforms). The *distances* come from the best available source (measurement → redshift → parallax → estimate). In cosmic mode, distances beyond 1 Mly are logarithmically compressed for display, so on-screen separations are not to scale — see §20.

**Q: Is the redshift-to-distance conversion correct?**
Yes — it uses the modern Planck18 cosmology (light-travel distance), not the old linear Hubble approximation. See §20.

**Q: Can I use this offline?**
After the first render of a target, yes — both the distance and the candidate list are cached. The interactive scene and all exports work without a network.

**Q: Why is my galaxy in "Cosmic" mode but a nebula in "Galactic"?**
Mode follows the object's SIMBAD type and distance. Galaxies and quasars are extragalactic (Cosmic); nebulae, clusters and stars are inside the Milky Way (Galactic). You can override this at any time.

**Q: What's the difference from CosmicDepth 3D?**
CosmicDepth 3D shows the depth of *everything inside one photo*. GalacticView 3D shows *where that whole photo sits* in the galaxy and universe, from Earth's viewpoint.

**Q: Does the Journey represent real travel time?**
No — nothing travels faster than light. The Journey is a visualization of *distance and the age of the light*. The counter shows how far each point is and how long ago the light in your photo passed it.

---

## 20. Scientific Background & Accuracy

### What is exact

- **Sky directions.** Right ascension / declination come from your plate-solve; the galactic-coordinate transform uses astropy. Every object is in exactly the right *direction* from Earth.
- **Earth's position.** Placed at the correct heliocentric distance (~26,000 ly) from the Galactic Center, in the Orion Arm.
- **Cosmology.** Redshift → distance uses `astropy.cosmology.Planck18` (H₀ ≈ 67.4 km/s/Mpc, Ωm ≈ 0.315, ΩΛ ≈ 0.685), computing light-travel distance from the lookback-time integral. This is significantly more accurate than the linear Hubble law at moderate redshift.

### Deliberate approximations (disclosed in-app)

- **Log compression beyond 1 Mly.** Directions and radial ordering are exact, but on-screen distances between objects are not proportional to reality. Marked by the 1 Mly boundary ring and the HUD label.
- **Photo rectangle enlargement.** Center and orientation are exact; the rectangle is scaled up for visibility.
- **Spiral arms are schematic.** They use a uniform logarithmic-spiral model (after Hou & Han 2014), accurate to within a few thousand light-years — so arm membership is *indicative*, not authoritative.
- **Constellation figures** sit on the target's distance shell; the real stars are at various distances. They are a sky-shape reference.
- **Type-median distances** can be far off; they are always labeled as estimates.

### A note on honesty

Where the tool estimates or approximates, it says so — in the Info tab, the CSV export, the source hints in the Target Picker, and the story card's honesty gate (which omits a historical analogy rather than force a wrong one). The goal is a beautiful visualization that never quietly misleads.

### Reference

Spiral-arm model after Hou, L. G. & Han, J. L. 2014, *The observed spiral structure of the Milky Way*, Astronomy & Astrophysics, 569, A125. Cosmology: Planck Collaboration 2018 (Planck18), via `astropy.cosmology`.

---

*Made by [Svenesis](https://www.svenesis.org). [Buy me a coffee ☕](https://buymeacoffee.com/sramuschkat) if this helped you see where your photos live in the universe.*
