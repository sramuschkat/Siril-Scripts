# Konzept: AnnotateImage — Bildfeld-Beschriftung mit Katalog-Objekten

**Siril Python Script (sirilpy) — Technisches Konzept für die Implementierung**

---

## 1. Zielsetzung

Ein Siril-Python-Script, das ein plate-gesolvtes Bild mit Katalog-Annotationen versieht und als **exportierbares PNG/TIFF** rendert. Inspiriert von PixInsights `AnnotateImage`-Script.

### Was Siril bereits kann (und was NICHT nachgebaut werden muss)

Siril hat seit Version 1.2 ein eingebautes Annotations-System:
- Overlay-Anzeige von Deep-Sky-Objekten (Messier, NGC, IC) im Viewer
- Koordinatengitter-Overlay
- Kompass-Overlay
- Annotation-Button in der Toolbar
- Benutzerdefinierte Annotationen via `annotate_object` Kommando
- Sonnenssystem-Objekte via Miriade-Ephemerides
- Annotationen werden in **Grün** (vordefinierte Kataloge) und **Orange** (User-Katalog) angezeigt

### Was Siril NICHT kann (= unser Script-Scope)

1. **Exportierbares Bild**: Siril rendert Annotationen nur als Viewer-Overlay — sie werden nicht in ein exportierbares Bild eingebrannt. Man kann keinen Screenshot als "annotiertes Bild" teilen.
2. **Konfigurierbare Darstellung**: Schriftgröße, Farben pro Katalog, Marker-Stil, Label-Platzierung sind nicht konfigurierbar.
3. **Mehrere Katalog-Layer gleichzeitig mit unterschiedlichen Stilen**: z.B. Galaxien in Gelb, Nebel in Rot, Sternhaufen in Blau.
4. **Koordinatengitter mit RA/DEC-Beschriftung im exportierten Bild**.
5. **Bildfeld-Informationsbox**: Zentrum-Koordinaten, Bildfeld-Größe, Orientierung, Maßstab.
6. **Social-Media-taugliche Ausgabe**: Bild mit Annotationen + optionalem Autostretch als PNG, bereit zum Teilen.

---

## 2. Voraussetzungen

### Bild muss plate-gelöst sein

Das Script prüft zu Beginn, ob das geladene Bild eine WCS-Lösung hat:

```python
fit = siril.get_image()
kw = fit.keywords

if not kw.pltsolvd:
    siril.log("FEHLER: Bild ist nicht plate-gelöst. Bitte zuerst Plate Solving durchführen.")
    siril.log("  → Tools > Astrometry > Image Plate Solver...")
    return
```

### Verfügbare WCS-Daten aus dem FITS-Header

Nach dem Plate Solving stehen im Header:

| Keyword    | Beschreibung                         | Zugriff via sirilpy                |
|-----------|--------------------------------------|-------------------------------------|
| `CRVAL1`  | RA des Referenzpunkts (Grad)         | `fit.header` (String parsen)       |
| `CRVAL2`  | DEC des Referenzpunkts (Grad)        | `fit.header` (String parsen)       |
| `CRPIX1`  | Referenzpixel X                      | `fit.header`                       |
| `CRPIX2`  | Referenzpixel Y                      | `fit.header`                       |
| `CD1_1`   | WCS Transformationsmatrix            | `fit.header`                       |
| `CD1_2`   | WCS Transformationsmatrix            | `fit.header`                       |
| `CD2_1`   | WCS Transformationsmatrix            | `fit.header`                       |
| `CD2_2`   | WCS Transformationsmatrix            | `fit.header`                       |
| `CTYPE1`  | Projektionstyp (z.B. RA---TAN-SIP)  | `fit.header`                       |
| `CTYPE2`  | Projektionstyp (z.B. DEC--TAN-SIP)  | `fit.header`                       |
| `OBJCTRA` | Objekt-RA                            | `kw.objctra`                       |
| `OBJCTDEC`| Objekt-DEC                           | `kw.objctdec`                      |
| `PLTSOLVD`| Plate Solved Flag                    | `kw.pltsolvd` (Bool)               |

### Pixel ↔ WCS Konvertierung

sirilpy bietet eine direkte Methode:

```python
# Pixel → RA/DEC
ra, dec = siril.pix2wcs(x, y)

# RA/DEC → Pixel
x, y = siril.wcs2pix(ra, dec)
```

Alternativ (empfohlen für Batch-Konvertierung vieler Punkte) via astropy:

```python
from astropy.wcs import WCS
from astropy.io import fits

# WCS aus dem FITS-Header extrahieren
header_str = fit.header
hdr = fits.Header.fromstring(header_str, sep='\n')
wcs = WCS(hdr)

# Batch: RA/DEC Arrays → Pixel Arrays
x_pixels, y_pixels = wcs.all_world2pix(ra_array, dec_array, 0)
```

---

## 3. Abhängigkeiten

```python
import sirilpy as s
s.ensure_installed("astropy")
s.ensure_installed("matplotlib")
s.ensure_installed("astroquery")  # Optional: für Online-Katalogabfragen
s.ensure_installed("ttkthemes")
```

| Modul          | Zweck                                          | Pflicht? |
|----------------|------------------------------------------------|----------|
| `sirilpy`      | Siril-Interface, Bildzugriff, WCS-Konvertierung | Ja       |
| `numpy`        | Array-Operationen                               | Ja (Dependency) |
| `astropy`      | WCS-Handling, FITS-Header, Katalogformate       | Ja       |
| `matplotlib`   | Bild-Rendering, Annotationen, Text, Grid        | Ja       |
| `astroquery`   | Online-Katalogabfragen (SIMBAD, VizieR)         | Optional |
| `tkinter`      | GUI                                              | Ja (stdlib) |
| `ttkthemes`    | GUI-Theming                                      | Ja       |

---

## 4. Katalog-Strategie

### 4.1 Offline-Kataloge (bevorzugt — kein Internet nötig)

Siril bringt eigene Annotationskataloge mit, die als CSV-Dateien vorliegen. Diese können direkt gelesen werden:

**Standardpfade der Siril-Kataloge:**
- Linux: `~/.local/share/siril/` oder `/usr/share/siril/`
- macOS: `~/Library/Application Support/siril/`
- Windows: `%APPDATA%\siril\`

Die Katalogdateien enthalten typischerweise: Name, RA, DEC, Typ, Magnitude, Größe.

**Alternativ: Eingebetteter Minimal-Katalog**

Für maximale Portabilität kann ein kompakter Katalog direkt ins Script eingebettet werden:

```python
# Messier-Katalog (110 Objekte) als Dictionary
MESSIER_CATALOG = [
    {"name": "M1",   "ra": 83.6331, "dec": 22.0145, "type": "SNR",  "mag": 8.4, "size_arcmin": 6.0},
    {"name": "M2",   "ra": 323.3626,"dec": -0.8233, "type": "GC",   "mag": 6.5, "size_arcmin": 16.0},
    {"name": "M31",  "ra": 10.6847, "dec": 41.2687, "type": "Gal",  "mag": 3.4, "size_arcmin": 178.0},
    # ... alle 110 Messier-Objekte
]

# NGC/IC-Katalog: Größere Datei, extern laden
# OpenNGC Projekt (Public Domain): https://github.com/mattiaverga/OpenNGC
```

**Empfohlene Offline-Katalogquellen:**

| Katalog     | Objekte  | Quelle                                          | Lizenz         |
|------------|----------|--------------------------------------------------|----------------|
| Messier     | 110      | Eingebettet ins Script                           | Public Domain  |
| OpenNGC     | ~13.900  | github.com/mattiaverga/OpenNGC (CSV)             | CC BY-SA 4.0   |
| Named Stars | ~900     | IAU-Liste / Hipparcos-Subset                     | Public Domain  |
| Sharpless   | 313      | Sharpless HII regions (CSV online verfügbar)     | Public Domain  |
| Barnard     | 349      | Dark Nebulae (CSV online verfügbar)              | Public Domain  |

### 4.2 Online-Kataloge (optional, via astroquery)

```python
from astroquery.simbad import Simbad
from astroquery.vizier import Vizier

# Alle bekannten Objekte im Bildfeld abfragen
# center = Bildzentrum RA/DEC, radius = halbe Diagonale des Bildfelds
result = Simbad.query_region(center, radius=fov_radius)
```

### 4.3 Katalog-Filterung: Nur Objekte IM Bildfeld

```python
def filter_objects_in_fov(catalog, wcs, image_width, image_height, margin=50):
    """
    Filtert Katalog-Objekte auf diejenigen, die tatsächlich im Bildfeld liegen.
    margin: Pixel-Rand nach innen (Labels nicht am äußersten Rand platzieren)
    """
    visible = []
    for obj in catalog:
        x, y = wcs.all_world2pix([[obj['ra'], obj['dec']]], 0)[0]
        if margin < x < image_width - margin and margin < y < image_height - margin:
            obj['pixel_x'] = x
            obj['pixel_y'] = y
            visible.append(obj)
    return visible
```

---

## 5. Rendering-Architektur

### 5.1 Bild-Basis: Autostretch-Preview oder Originaldaten

```python
# Option A: Autostretch-Preview von Siril holen (8-bit, gestreckt)
preview_data = siril.get_image_pixeldata(preview=True, linked=True)

# Option B: Lineare Daten holen und selbst stretchen (mehr Kontrolle)
with siril.image_lock():
    fit = siril.get_image()
    fit.ensure_data_type(np.float32)
    data = fit.data.copy()  # (channels, height, width)
```

Empfehlung: **Option A** (preview=True), da Siril den Autostretch bereits optimiert hat und der Nutzer das Bild so sieht, wie er es kennt.

### 5.2 Matplotlib-Rendering-Pipeline

```python
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Circle
from matplotlib.offsetbox import AnnotationBbox, TextArea
import matplotlib.patheffects as pe

def render_annotated_image(image_data, objects, wcs, config, output_path):
    """
    Rendert das annotierte Bild als PNG.
    
    image_data: numpy array (H, W, 3) uint8 — das Vorschaubild
    objects:    Liste der sichtbaren Katalog-Objekte mit pixel_x, pixel_y
    wcs:        astropy WCS Objekt
    config:     Konfigurationsdict (Farben, Schriftgröße, etc.)
    output_path: Pfad für die PNG-Ausgabe
    """
    # DPI so wählen, dass 1 Bild-Pixel ≈ 1 PNG-Pixel
    dpi = 100
    fig_w = image_data.shape[1] / dpi
    fig_h = image_data.shape[0] / dpi
    
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_position([0, 0, 1, 1])  # Kein Rand
    
    # Hintergrundbild
    ax.imshow(image_data, origin='lower', aspect='equal')
    ax.set_xlim(0, image_data.shape[1])
    ax.set_ylim(0, image_data.shape[0])
    ax.axis('off')
    
    # --- Annotationen rendern ---
    for obj in objects:
        render_object_annotation(ax, obj, config)
    
    # --- Optionales Koordinatengitter ---
    if config.get('show_grid', False):
        render_coordinate_grid(ax, wcs, image_data.shape, config)
    
    # --- Optionale Info-Box ---
    if config.get('show_info_box', True):
        render_info_box(ax, wcs, image_data.shape, config)
    
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0,
                facecolor='black', edgecolor='none')
    plt.close()
```

### 5.3 Objekt-Annotation-Rendering

```python
# Farbschema pro Objekttyp (konfigurierbar)
DEFAULT_COLORS = {
    'Gal':  '#FFD700',  # Gold — Galaxien
    'Neb':  '#FF4444',  # Rot — Emissionsnebel
    'PN':   '#44FF44',  # Grün — Planetarische Nebel
    'OC':   '#44AAFF',  # Hellblau — Offene Sternhaufen
    'GC':   '#FF8800',  # Orange — Kugelsternhaufen
    'SNR':  '#FF44FF',  # Magenta — Supernovaüberreste
    'DN':   '#888888',  # Grau — Dunkelnebel
    'Star': '#FFFFFF',  # Weiß — Benannte Sterne
    'Other':'#CCCCCC',  # Hellgrau — Sonstiges
}

def render_object_annotation(ax, obj, config):
    """
    Zeichnet Marker + Label für ein einzelnes Objekt.
    """
    x, y = obj['pixel_x'], obj['pixel_y']
    color = config['colors'].get(obj.get('type', 'Other'), '#CCCCCC')
    font_size = config.get('font_size', 10)
    marker_size = config.get('marker_size', 20)
    
    # --- Marker ---
    # Kreis oder Ellipse, Größe basierend auf Objekt-Ausdehnung
    if 'size_arcmin' in obj and obj['size_arcmin'] > 0:
        # Objektgröße in Pixel umrechnen (über Pixel-Scale)
        size_px = obj['size_arcmin'] * 60.0 / config['pixel_scale_arcsec']
        size_px = max(size_px, marker_size)  # Mindestgröße
        ellipse = Ellipse((x, y), size_px, size_px, 
                          fill=False, edgecolor=color, linewidth=1.5, alpha=0.8)
        ax.add_patch(ellipse)
    else:
        ax.plot(x, y, '+', color=color, markersize=marker_size * 0.5, 
                markeredgewidth=1.5, alpha=0.8)
    
    # --- Label ---
    label = obj['name']
    if config.get('show_magnitude', False) and 'mag' in obj:
        label += f" ({obj['mag']:.1f}m)"
    if config.get('show_type', False) and 'type' in obj:
        label += f" [{obj['type']}]"
    
    # Text mit Outline für Lesbarkeit auf dunklem UND hellem Hintergrund
    text = ax.text(
        x + marker_size * 0.4, y + marker_size * 0.4,
        label, fontsize=font_size, color=color, fontweight='bold',
        ha='left', va='bottom',
        path_effects=[
            pe.withStroke(linewidth=2, foreground='black'),  # Schwarze Outline
        ]
    )
```

### 5.4 Koordinatengitter

```python
def render_coordinate_grid(ax, wcs, image_shape, config):
    """
    Zeichnet ein RA/DEC-Gitter über das Bild.
    """
    height, width = image_shape[:2]
    grid_color = config.get('grid_color', '#334455')
    grid_alpha = config.get('grid_alpha', 0.4)
    
    # Bildfeld-Eckpunkte in WCS
    corners_ra_dec = []
    for px, py in [(0,0), (width,0), (width,height), (0,height)]:
        ra, dec = wcs.all_pix2world([[px, py]], 0)[0]
        corners_ra_dec.append((ra, dec))
    
    ra_min = min(c[0] for c in corners_ra_dec)
    ra_max = max(c[0] for c in corners_ra_dec)
    dec_min = min(c[1] for c in corners_ra_dec)
    dec_max = max(c[1] for c in corners_ra_dec)
    
    # Gitter-Intervall automatisch wählen basierend auf Bildfeld-Größe
    fov_size = max(ra_max - ra_min, dec_max - dec_min)
    grid_step = choose_grid_step(fov_size)  # z.B. 0.5° für ~3° FOV
    
    # RA-Linien zeichnen
    ra_values = np.arange(
        np.floor(ra_min / grid_step) * grid_step,
        np.ceil(ra_max / grid_step) * grid_step + grid_step,
        grid_step
    )
    for ra in ra_values:
        dec_range = np.linspace(dec_min, dec_max, 100)
        ra_arr = np.full_like(dec_range, ra)
        x_px, y_px = wcs.all_world2pix(
            np.column_stack([ra_arr, dec_range]), 0
        ).T
        mask = (x_px >= 0) & (x_px < width) & (y_px >= 0) & (y_px < height)
        if np.any(mask):
            ax.plot(x_px[mask], y_px[mask], '-', color=grid_color, 
                    alpha=grid_alpha, linewidth=0.5)
            # Label am Rand
            idx = np.where(mask)[0][0]
            ra_hms = degrees_to_hms(ra)
            ax.text(x_px[idx], y_px[idx], ra_hms, fontsize=7, 
                    color=grid_color, alpha=grid_alpha + 0.2)
    
    # DEC-Linien analog...
```

### 5.5 Info-Box

```python
def render_info_box(ax, wcs, image_shape, config):
    """
    Zeichnet eine Info-Box mit Bildfeld-Metadaten in eine Ecke.
    """
    height, width = image_shape[:2]
    
    # Bildzentrum in WCS
    center_ra, center_dec = wcs.all_pix2world([[width/2, height/2]], 0)[0]
    
    # Bildfeld-Größe
    corner1_ra, corner1_dec = wcs.all_pix2world([[0, 0]], 0)[0]
    corner2_ra, corner2_dec = wcs.all_pix2world([[width, height]], 0)[0]
    fov_w = abs(corner2_ra - corner1_ra) * np.cos(np.radians(center_dec))
    fov_h = abs(corner2_dec - corner1_dec)
    
    # Pixel Scale
    pixel_scale = config.get('pixel_scale_arcsec', 0)
    
    # Rotation
    # CD-Matrix → Rotationswinkel
    rotation = np.degrees(np.arctan2(wcs.wcs.cd[0, 1], wcs.wcs.cd[0, 0]))
    
    info_lines = [
        f"Center: {degrees_to_hms(center_ra)}  {degrees_to_dms(center_dec)}",
        f"FOV: {fov_w*60:.1f}' × {fov_h*60:.1f}'",
        f"Scale: {pixel_scale:.2f}\"/px",
        f"Rotation: {rotation:.1f}°",
    ]
    if config.get('object_name'):
        info_lines.insert(0, config['object_name'])
    
    info_text = '\n'.join(info_lines)
    
    # Semi-transparente Box
    ax.text(
        width * 0.02, height * 0.98, info_text,
        fontsize=9, color='white', fontfamily='monospace',
        va='top', ha='left',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.6),
        path_effects=[pe.withStroke(linewidth=1, foreground='black')]
    )
```

---

## 6. GUI-Entwurf (tkinter)

```
╔═══════════════════════════════════════════════════════════╗
║  AnnotateImage                                     [x]   ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  Kataloge                                                 ║
║  ┌───────────────────────────────────────────────────┐    ║
║  │  [✓] Messier           Farbe: [████] Gold         │    ║
║  │  [✓] NGC (hell, <12m)  Farbe: [████] Cyan         │    ║
║  │  [ ] NGC (alle)        Farbe: [████] Cyan         │    ║
║  │  [ ] IC                Farbe: [████] Hellblau     │    ║
║  │  [✓] Benannte Sterne   Farbe: [████] Weiß        │    ║
║  │  [ ] Sharpless (HII)   Farbe: [████] Rot          │    ║
║  │  [ ] Barnard (Dunkel)  Farbe: [████] Grau         │    ║
║  └───────────────────────────────────────────────────┘    ║
║                                                           ║
║  Darstellung                                              ║
║  ┌───────────────────────────────────────────────────┐    ║
║  │  Schriftgröße:  [=====●==============] 10 pt      │    ║
║  │  Marker-Größe:  [=====●==============] 20 px      │    ║
║  │  Magnitude-Limit: [========●=========] 12.0 mag   │    ║
║  │                                                    │    ║
║  │  [✓] Objektgröße als Ellipse anzeigen              │    ║
║  │  [✓] Magnitude im Label anzeigen                   │    ║
║  │  [ ] Objekttyp im Label anzeigen                   │    ║
║  │  [✓] Farben nach Objekttyp                         │    ║
║  └───────────────────────────────────────────────────┘    ║
║                                                           ║
║  Extras                                                   ║
║  ┌───────────────────────────────────────────────────┐    ║
║  │  [✓] Koordinatengitter                             │    ║
║  │  [✓] Info-Box (Zentrum, FOV, Scale)                │    ║
║  │  [ ] Kompass (N/E-Pfeile)                          │    ║
║  │  [ ] Online-Katalogabfrage (SIMBAD)                │    ║
║  └───────────────────────────────────────────────────┘    ║
║                                                           ║
║  Ausgabe                                                  ║
║  ┌───────────────────────────────────────────────────┐    ║
║  │  Format:  (●) PNG    ( ) TIFF    ( ) JPEG          │    ║
║  │  DPI:     [==========●==========] 150              │    ║
║  │  [ ] Bild vorher Auto-Stretchen                    │    ║
║  │  Dateiname: [annotated_M31_20260321       ]        │    ║
║  └───────────────────────────────────────────────────┘    ║
║                                                           ║
║  ┌─────────────────────────┐ ┌─────────────────────────┐  ║
║  │   🖼️  Annotieren        │ │   ❌ Schließen          │  ║
║  └─────────────────────────┘ └─────────────────────────┘  ║
║                                                           ║
║  Status: Bereit — Bild plate-gelöst ✓                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

---

## 7. Programmablauf

```
Start des Scripts
        │
        ▼
┌─────────────────────────┐
│ sirilpy verbinden        │
│ Prüfen: Bild geladen?   │
│ Prüfen: Plate-gelöst?   │
└────────┬────────────────┘
         │ Nein → Fehlermeldung + Abbruch
         │ Ja ↓
         ▼
┌─────────────────────────┐
│ WCS aus Header extrahieren│
│ Bildfeld berechnen        │
│ (Zentrum, FOV, Scale)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ GUI anzeigen              │
│ Nutzer wählt:             │
│  - Kataloge               │
│  - Darstellungsoptionen   │
│  - Ausgabeformat          │
└────────┬────────────────┘
         │ Klick "Annotieren"
         ▼
┌─────────────────────────┐
│ Kataloge laden            │
│ (eingebettet oder Datei)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Objekte im Bildfeld       │
│ filtern (WCS → Pixel)     │
│ Magnitude-Filter anwenden  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Vorschaubild von Siril    │
│ holen (autostretch/preview)│
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Matplotlib-Rendering      │
│  - Hintergrundbild        │
│  - Objekt-Marker + Labels │
│  - Koordinatengitter      │
│  - Info-Box               │
│  - Kompass                │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ PNG/TIFF speichern        │
│ Log-Ausgabe in Siril      │
│ (Anzahl Objekte, Pfad)    │
└─────────────────────────┘
```

---

## 8. Datei- und Projektstruktur

```
annotate_image/
├── AnnotateImage.py              # Hauptscript (Siril Entry Point)
├── catalogs/
│   ├── messier.csv               # Messier-Katalog (110 Objekte)
│   ├── ngc_bright.csv            # NGC hell (<12 mag, ~2000 Objekte)
│   ├── ic_bright.csv             # IC hell (<12 mag)
│   ├── named_stars.csv           # Benannte Sterne (~300 hellste)
│   ├── sharpless.csv             # Sharpless HII Regions
│   └── barnard.csv               # Barnard Dark Nebulae
├── README.md
└── examples/
    └── example_annotated.png
```

**Wichtig für Siril-Repository-Kompatibilität:**
Da Siril Scripts als einzelne .py-Datei erwartet werden, sollte eine **Standalone-Version** existieren, die die Katalogdaten entweder:
- Als eingebettetes Python-Dictionary enthält (für Messier + hellste NGCs)
- Oder zur Laufzeit den OpenNGC-Katalog via `ensure_installed("opengc")` nachlädt

Empfehlung: **Zwei Versionen** anbieten:
1. `AnnotateImage_Lite.py` — Nur Messier + 300 hellste NGC, alles eingebettet, keine externen Dateien
2. `AnnotateImage_Full.py` — Alle Kataloge, benötigt `catalogs/`-Verzeichnis

---

## 9. Katalog-Datenformat (CSV)

```csv
name,ra,dec,type,mag,size_arcmin,common_name
M1,83.6331,22.0145,SNR,8.4,6.0,Crab Nebula
M31,10.6847,41.2687,Gal,3.4,178.0,Andromeda Galaxy
M42,83.8221,-5.3911,Neb,4.0,85.0,Orion Nebula
M45,56.601,24.1153,OC,1.6,110.0,Pleiades
NGC7000,314.6802,44.3117,Neb,4.0,120.0,North America Nebula
```

Objekttypen (Kurzform):

| Kürzel | Bedeutung               |
|--------|--------------------------|
| Gal    | Galaxie                  |
| Neb    | Emissionsnebel           |
| RN     | Reflexionsnebel          |
| PN     | Planetarischer Nebel     |
| DN     | Dunkelnebel              |
| OC     | Offener Sternhaufen      |
| GC     | Kugelsternhaufen         |
| SNR    | Supernovaüberrest        |
| Star   | Benannter Stern          |
| Ast    | Asterismus               |
| QSO    | Quasar                   |
| Other  | Sonstiges                |

---

## 10. Metadaten-Header

```python
"""
# SPDX-License-Identifier: GPL-3.0-or-later
# Script Name: Annotate Image
# Script Version: 1.0.0
# Siril Version: 1.4.0
# Python Module Version: 1.0.0
# Script Category: processing
# Script Description: Renders catalog annotations (Messier, NGC, IC,
#   named stars) onto a plate-solved image and exports it as PNG/TIFF.
#   Similar to PixInsight's AnnotateImage script. Requires a plate-solved image.
# Script Author: [dein Name]
"""
```

---

## 11. Log-Ausgabe

```
[AnnotateImage] Bild geladen: 4656 x 3520 px, plate-gelöst ✓
[AnnotateImage] WCS: Zentrum RA=05h 35m 17.3s  DEC=-05° 23' 28"
[AnnotateImage] Bildfeld: 128.4' × 97.1' (2.14° × 1.62°)
[AnnotateImage] Pixel Scale: 1.66"/px, Rotation: -12.3°
[AnnotateImage] ──────────────────────────────────────
[AnnotateImage] Kataloge geladen: Messier, NGC (hell), Named Stars
[AnnotateImage] Magnitude-Limit: 12.0
[AnnotateImage] Gefundene Objekte im Bildfeld:
[AnnotateImage]   Messier:      3  (M42, M43, M78)
[AnnotateImage]   NGC:          7  (NGC 1973, NGC 1975, NGC 1977, ...)
[AnnotateImage]   Named Stars:  4  (Alnitak, Alnilam, Mintaka, ...)
[AnnotateImage]   Gesamt:       14 Objekte annotiert
[AnnotateImage] ──────────────────────────────────────
[AnnotateImage] Ausgabe: /pfad/annotated_Orion_20260321_143022.png (3.2 MB)
```

---

## 12. Edge Cases und Fehlerbehandlung

| Situation                              | Handling                                                        |
|----------------------------------------|------------------------------------------------------------------|
| Bild nicht geladen                      | Fehlermeldung + Abbruch                                          |
| Bild nicht plate-gelöst                 | Fehlermeldung mit Hinweis auf Plate Solver                       |
| Keine Objekte im Bildfeld              | Info-Meldung, trotzdem Grid + Info-Box rendern                   |
| Sehr kleines FOV (<10')                | Automatisch nur helle Sterne annotieren, kein Messier            |
| Sehr großes FOV (>10°)                 | Magnitude-Limit automatisch anheben, nur hellste Objekte         |
| WCS mit SIP-Distortions               | astropy.WCS unterstützt SIP nativ — kein Problem                 |
| FITS-Header fehlt Teile (kein OBJECT)  | Graceful degradation — Info-Box ohne Objektnamen                 |
| Matplotlib nicht installiert            | `ensure_installed()` installiert automatisch                     |
| Überlappende Labels                    | Einfache Kollisionserkennung, Labels leicht verschieben          |

---

## 13. Label-Kollisionsvermeidung

```python
def resolve_label_collisions(objects, min_distance_px=60):
    """
    Verschiebt Labels, die sich überlappen, leicht nach außen.
    Einfacher Greedy-Algorithmus.
    """
    placed = []
    for obj in objects:
        x, y = obj['pixel_x'], obj['pixel_y']
        offset_x, offset_y = 15, 15  # Default: rechts oben
        
        # Prüfe Kollision mit bereits platzierten Labels
        for placed_obj in placed:
            dx = abs(x - placed_obj['label_x'])
            dy = abs(y - placed_obj['label_y'])
            if dx < min_distance_px and dy < min_distance_px:
                # Alternatives Placement: links oben, rechts unten, links unten
                offset_x, offset_y = try_alternative_placement(
                    x, y, placed, min_distance_px
                )
                break
        
        obj['label_x'] = x + offset_x
        obj['label_y'] = y + offset_y
        placed.append(obj)
    
    return objects
```

---

## 14. Erweiterungsmöglichkeiten (spätere Versionen)

| Feature                               | Beschreibung                                                    |
|--------------------------------------|------------------------------------------------------------------|
| **Interaktive Vorschau**             | tkinter-Canvas mit Live-Preview vor dem Export                   |
| **Siril-Overlay statt nur PNG**      | Annotationen als Siril-Polygone via `overlay_add_polygon()`      |
| **Sonnensystem-Objekte**             | Planeten, Asteroiden, Kometen basierend auf DATE-OBS             |
| **Eigene Objekt-Liste**              | Import einer CSV mit eigenen Objekten (z.B. Beobachtungsliste)  |
| **Batch-Mode**                       | Mehrere Bilder auf einmal annotieren (CLI-Modus)                |
| **Legende**                          | Farblegende mit Objekttyp-Zuordnung im Bild                     |
| **Stern-Magnitudes als Punktgröße**  | Hellere Sterne als größere Punkte darstellen                     |

---

## 15. Technische Hinweise für die Implementierung

- **FITS-Orientierung**: Siril speichert Bilder bottom-up. `origin='lower'` in matplotlib verwenden. Die sirilpy `pix2wcs()` / `wcs2pix()` Methoden berücksichtigen das automatisch.
- **Performance**: Der WCS-Transform für alle Katalogobjekte (`all_world2pix`) ist mit astropy für 10.000+ Objekte in <100ms erledigt. Kein Bottleneck.
- **Preview-Daten**: `get_image_pixeldata(preview=True)` liefert 8-bit RGB-Daten, die direkt an matplotlib übergeben werden können. Kein manuelles Stretching nötig.
- **Schriftart**: matplotlib's Default-Font funktioniert gut. Für bessere Lesbarkeit optional `'DejaVu Sans Mono'` für die Info-Box verwenden.
- **Kompatibilität**: Alle drei OS (Linux, macOS, Windows). Pfade mit `os.path` oder `pathlib` handhaben. Katalog-Dateien relativ zum Script-Verzeichnis suchen.
- **Speicher**: Das Vorschaubild ist 8-bit, also selbst ein 60-MP-Bild braucht nur ~180 MB RAM. Kein Problem.
