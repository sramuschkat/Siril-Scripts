# Svenesis Satellite Trail Cleaner — Benutzeranleitung

**Version 1.0.0** | Siril Python-Skript zur Entfernung von Satellitenspuren pro Einzelbild

> *Schließt die Lücke zwischen Sirils σ-Clip-Stack-Rejection (benötigt 8+ Subs) und der Alles-oder-Nichts-Entscheidung, ein spurkontaminiertes Bild zu verwerfen. Bereinigt jedes betroffene Sub einzeln, **vor** dem Stacken.*

---

## Inhaltsverzeichnis

1. [Was ist der Satellite Trail Cleaner?](#1-was-ist-der-satellite-trail-cleaner)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Detection: Wie findsat_mrt funktioniert](#6-detection-wie-findsat_mrt-funktioniert)
7. [Inpaint-Methoden — welche soll ich nehmen?](#7-inpaint-methoden--welche-soll-ich-nehmen)
8. [Die Empfehlungs-Anzeige](#8-die-empfehlungs-anzeige)
9. [Unterstützte Dateiformate](#9-unterstützte-dateiformate)
10. [Der Apply-Workflow](#10-der-apply-workflow)
11. [Das Audit-Protokoll](#11-das-audit-protokoll)
12. [Tipps & Empfehlungen](#12-tipps--empfehlungen)
13. [Fehlerbehebung](#13-fehlerbehebung)
14. [Häufige Fragen](#14-häufige-fragen)
15. [Wissenschaftlicher Hintergrund — Warum wir inpainten](#15-wissenschaftlicher-hintergrund--warum-wir-inpainten)

---

## 1. Was ist der Satellite Trail Cleaner?

Der **Svenesis Satellite Trail Cleaner** ist ein Siril-Python-Skript, das lineare Strukturen (Satellitenspuren, Flugzeug-Kondensstreifen, taumelnde Raketenkörper) in deinen einzelnen astrofotografischen Einzelaufnahmen erkennt und **mit dem lokalen Sky-Hintergrund übermalt** — **vor** dem Stacken.

Stell es dir als **dedizierten Spur-Entfernungs-Preprocessor** vor, der einmal pro Session über jedes betroffene Sub läuft, sodass dein Stacking-Schritt nur saubere Bilder sieht statt Spuren statistisch herausfiltern zu müssen.

Ergebnis: ein finaler Stack ohne Spur-Reste, selbst wenn du nur 4–6 Subs hast und Sirils normale σ-Clip-Rejection statistisch nicht mächtig genug ist, eine Spur allein zu entfernen.

---

## 2. Hintergrundwissen für Einsteiger

### Was ist eine Satellitenspur?

Wenn du eine Langzeitbelichtung vom Nachthimmel machst, hinterlassen Satelliten oder Flugzeuge, die durch dein Bildfeld ziehen, **helle lineare Streifen** quer durchs Bild. Mit Starlink und ähnlichen Mega-Konstellationen ist das nicht mehr selten — die meisten mehrstündigen Imaging-Sessions fangen mindestens eine Spur ein.

| Quelle | Visuelle Signatur |
|--------|-------------------|
| **LEO-Satellit** | Lange dünne gerade Linie, gleichmäßige Helligkeit |
| **Geostationärer Satellit** | Kurz oder unsichtbar (folgt der siderischen Nachführung) |
| **Taumelnder Raketenkörper** | „String of Pearls" — periodische helle Blitze entlang der Linie |
| **Flugzeug** | Oft leicht gebogen, manchmal mit roten/grünen Strobe-Blitzen |
| **Iridium-Flare** | Kurzer heller Spitzenwert, oft nur auf 1–2 Bildern |

### Warum nicht einfach Sirils Stack-Rejection nutzen?

Siril (und PixInsight und jeder andere moderne Stacker) unterstützt **σ-Clip-Stacking**: Beim Kombinieren von N Belichtungen wird der Wert jedes Pixels über den Stack verglichen, und Ausreißer (typisch > 3σ vom Median) werden verworfen. Eine Satellitenspur, die nur in einem von z. B. 12 Frames sichtbar ist, ist statistisch ein Ausreißer — sie wird verworfen, der finale Stack zeigt dort sauberen Sky.

**Das funktioniert, wenn du ca. 8 oder mehr gut verteilte Belichtungen hast.** Bei kürzeren Sequenzen:

- Mit **5 Subs** sind 20 % der Stichprobe von der Spur betroffen. σ-Clipping braucht ≥5 überlebende Samples auf jeder Seite des Spur-Werts für sichere Rejection. Grenzwertig.
- Mit **3 Subs** ist σ-Clipping statistisch nicht möglich — die Spur hinterlässt eine schwache Spur im finalen Stack.
- Mit **LRGB-Filtern** hat jeder Pro-Filter-Substack vielleicht nur 4–6 Frames, deutlich in der Gefahrenzone.

Dieses Tool schließt die Lücke, indem es die Spur **aus jedem betroffenen Frame einzeln entfernt** vor dem Stacken. Der nachgelagerte σ-Clip läuft dann auf bereits sauberen Frames.

### Warum nicht das betroffene Frame einfach wegwerfen?

Zwei Gründe:

1. **Du verlierst 100 % des Signals** in diesem Frame — bei kurzen Sessions zählt jedes Sub.
2. Die Spur kreuzt vielleicht **nur einen kleinen Teil** des Bildes. Den ganzen Frame wegzuwerfen, um eine 50.000-Pixel-Spur in einem 24-Megapixel-Bild zu entfernen, ist verschwenderisch. Spatial Inpainting modifiziert nur die Spur-Region (~0,2 % der Pixel), die restlichen 99,8 % bleiben unangetastet.

### Was ist „Inpainting"?

In der Bildverarbeitung bedeutet **Inpainting**, eine Region eines Bildes anhand der umliegenden Pixel als Kontext aufzufüllen, sodass der gefüllte Bereich natürlich übergeht. Wir definieren eine **Maske** (die Spur-Pixel) und ersetzen diese Pixel durch Werte, die aus der unmaskierten Nachbarschaft geschätzt werden.

Für astronomische Sky-Regionen ist das gut geeignet: Der Sky hat einheitliche statistische Eigenschaften (Mittelwert, σ) über Skalen von Dutzenden bis Hunderten Pixeln, also kann eine 15-px-breite Spur, die durch eine einheitliche Sky-Region läuft, nahezu perfekt rekonstruiert werden.

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweis |
|------------|----------------|---------|
| **Siril** | 1.4.0+ | Python-Script-Support muss aktiviert sein |
| **sirilpy** | Mitgeliefert | Kommt mit Siril 1.4+ |
| **numpy** | Aktuell | Auto-installiert |
| **PyQt6** | 6.x | Auto-installiert |
| **astropy** | 5.x+ | Auto-installiert |
| **opencv-python-headless** | 4.x | Auto-installiert |
| **photutils** | 1.x+ | Auto-installiert |
| **scikit-image** | Aktuell | Auto-installiert |
| **acstools** | 3.7+ | Auto-installiert (liefert `findsat_mrt`) |
| **xisf** | 0.9+ | Auto-installiert (XISF read/write) |
| **tifffile** | Aktuell | Auto-installiert (TIFF read/write) |

### Installation

1. Lade `Svenesis-SatelliteTrailCleaner.py` aus dem [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Lege es im Siril-Scripts-Verzeichnis ab:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Siril neu starten. Das Skript erscheint unter **Processing → Scripts**.

Beim ersten Start installiert das Skript fehlende Abhängigkeiten automatisch via `sirilpy.ensure_installed()`. Das kann eine Minute dauern (acstools zieht mehrere Pakete nach).

---

## 4. Erste Schritte

### Der 5-Schritte-Workflow

Beim allerersten Start erscheint automatisch ein geführtes Walkthrough-Dialog. Er kann jederzeit über **Hilfe → Show Quick Workflow** wieder geöffnet werden. Hier in kompakter Form:

1. **Finde ein Frame mit sichtbarer Spur.** Navigiere mit dem Slider oder `←`/`→`-Tasten. Setze die View-Auswahl auf **Stretched**, damit schwache Spuren sichtbar werden.
2. **Klicke 🛰 Detect Trails on Current.** Erkannte Linien werden **grün** (werden entfernt) oder **grau** (bleiben) overlay'd. Klicke eine Linie, um zu togglen. Schraube an **SNR threshold** / **Min length** / **Max width**, wenn du False Positives siehst.
3. **Folge der 💡 Empfehlungs-Anzeige** unter dem Method-Dropdown. Das Tool analysiert dein konkretes Frame (Cross-Trail-Gradient, Pearl-Pattern, Mask-Kompaktheit) und schlägt die beste Inpaint-Methode vor. Klick **Apply**, um sie zu übernehmen, oder wähle manuell.
4. **Schalte View auf Cleaned Preview** zur Kontrolle. Justiere **Mask dilation** / **Strip width** / **Match sky noise** bei Bedarf — die Vorschau aktualisiert sich live.
5. **Klicke ▶ Apply to All Frames.** Die aktuellen Einstellungen werden eingefroren und auf jedes Sub angewandt. Originale wandern nach `originals/`, gecleante Files ersetzen sie. Progress-Dialog zeigt laufende Cleaned / Skipped / Errors + ETA.

### Warum auf einem Frame justieren?

Detection-Schwellen und Inpaint-Einstellungen sind global für den Batch. Du suchst dir also EIN gutes Test-Frame (sichtbare Spur, repräsentativ für den Rest der Session), perfektionierst es, dann läuft „Apply to All" mit demselben Rezept über den Ordner. Frames ohne Spur werden automatisch übersprungen.

---

## 5. Die Benutzeroberfläche

### Linkes Panel — Parameter

| Gruppe | Steuerelemente |
|--------|----------------|
| **Detection (MRT)** | Scan mode (Quick / Normal / Deep), SNR threshold, Min length, Max width, Persistence-Check + Parameter, Processes (auto-getuned pro Scan-Mode), Mask dilation, RGB reduce |
| **Star Protection (Inpaint)** | Protect detected stars (default aus), Sigma, Star halo |
| **Inpainting** | Method-Dropdown (6 Optionen + 💡 Empfehlungs-Anzeige), Strip width, Match sky noise |
| **Apply** | Confirm each frame before writing, ✓ Apply to Current, Skip, ▶ Apply to All Frames |
| **Footer** | Buy me a Coffee, Help, Close |

### Top-Bar

- **View:** Stretched / Mask Overlay / Cleaned Preview
- **🛰 Detect Trails on Current** Button
- Status-Zeile mit Detection-Ergebnis, Halo-Growth-Diagnose, Inpaint-Statistik (voller Text per Hover)

### Auswahl-Bar (nach Detection)

- „N of M line(s) marked for removal — ~XXX,XXX px to inpaint"
- **Select All** / **Select None** / **Invert** Buttons
- „Click a line to toggle remove / keep" Hinweis

### Canvas

- Bild mit Overlay (Linien / Maske / Cleaned Preview je nach View)
- Mausrad: Zoom; Klick+Drag: Schieben

### Navigations-Bar (unten)

- First / Previous / Next / Last Buttons
- Frame-Slider
- Frame-Zähler + Filename

---

## 6. Detection: Wie `findsat_mrt` funktioniert

### Der Algorithmus

Das Detection-Backend ist **STScI's `findsat_mrt.TrailFinder`** — dieselbe Median-Radon-Transform-Pipeline, die zur Spur-Erkennung in Hubble-Space-Telescope-ACS-Bildern verwendet wird (Stark, Avila, Anderson et al. 2022, ACS ISR 2022-08).

Die klassische Hough/Radon-Transformation projiziert ein Bild in einen (rho, theta)-Parameter-Raum, indem sie Pixel entlang jeder Linie aufsummiert. Das ist in sternreichen Feldern fundamental fragil: helle Sterne tragen einen „Fan von False Positives" bei — jede Linie, die durch einen hellen Stern verläuft, kriegt eine erhöhte Summe, der Detektor produziert viele falsche Linien.

Die **Median-Radon-Transformation** ersetzt die Summe durch den *Median*. Eine echte Satellitenspur hat etwa konstante Helligkeit über ihre Länge, also entspricht der Median dem Pro-Pixel-Signal. Ein heller Stern besetzt < 1 % der Pixel jeder Linie, und der Median behandelt ihn als Ausreißer — *er wird ignoriert*. Das eliminiert den False-Positive-Fan, der klassische Detektoren zerlegt.

### Pipeline-Schritte

1. **Preprocessing** — Median-Hintergrund subtrahieren.
2. **Optionales Downsampling** für Geschwindigkeit (Quick: 4×, Normal: 2×, Deep: 1×).
3. **MRT-Berechnung** — für jede (rho, theta) der Median der Pixel entlang dieser Linie. Multi-Process parallel über Winkel.
4. **Peak-Detection im MRT-Space** mit drei vorberechneten Kerneln (3, 7, 15 px Linien-Breite).
5. **Per-Kandidat-Bildraum-Validierung:**
   - Strip um den Kandidaten rotieren, Gauss über die Spur-Breite fitten
   - Verwerfen, wenn Breite > `max_width` (killt Kometen-Schweife)
   - Optionaler Persistence-Test: Spur in Chunks teilen, Mehrheit muss konsistente SNR zeigen (killt nicht-uniforme Features)
6. **Endpunkt-Erweiterung** zum Bildrand, Mask-Konstruktion, Bright-Halo-Growth der Maske.

### Detection-Parameter

| Parameter | Effekt | Typisch |
|-----------|--------|---------|
| **SNR threshold** | Min Signal-zu-Rauschen für Annahme | 5.0 (empfindlich) – 8.0 (streng) |
| **Min length** | Min Spur-Länge in Pixeln | 50 (Default) |
| **Max width** | Max Spur-Breite in Pixeln (killt Kometen-Schweife) | 75 (Default) |
| **Check persistence** | Verlangt gleichmäßige Helligkeit entlang Spur | An (killt Kometen) / Aus (fängt schwache Spuren) |
| **Min persistence** | Anteil der Chunks, die SNR-Test bestehen müssen | 0.5 |
| **Chunk size** | Pixel-Länge jedes Persistence-Chunks | 100 |
| **Processes** | MRT-Worker-Anzahl | Auto je Scan-Mode (2 / cores/2 / alle) |
| **Mask dilation** | Halb-Breite (px) der Inpaint-Mask um jede Linie | 7 (Default) |
| **RGB reduce** | Wie Farb-Kanäle in Mono kollabieren | Mean / Max per pixel |

### Scan-Mode-Presets

| Mode | Downsample | Theta | Persistence | Processes | Wann nutzen |
|------|------------|-------|-------------|-----------|-------------|
| **Quick** | 4× | 1.0° | Aus | 2–4 | Schnelle Vorschau, offensichtliche Spuren |
| **Normal** | 2× | 0.5° | An | cores/2 | Default für die meisten Fälle |
| **Deep** | 1× | 0.5° | An | alle Cores | Schwache Spuren, maximale Empfindlichkeit |

### Bright-Halo-Mask-Growth

Nach der Standard-Dilation wird die Maske iterativ in jedes helle Pixel (> sky + 3σ) hineinwachsen lassen, das ihr direkt benachbart ist, gedeckelt bei 25 Hops. Das **absorbiert automatisch die PSF-Halos** um die hellen Pearls eines flackernden Satelliten, sodass kein heller Ring außerhalb einer Fixbreite-Maske überlebt. Die Status-Notiz meldet `halo growth: +N px in K hops`.

---

## 7. Inpaint-Methoden — welche soll ich nehmen?

Nach Detection wählt die **💡 Empfehlungs-Anzeige** unter dem Method-Dropdown eine für dich. Hier der manuelle Entscheidungsbaum:

| Methode | Wann am besten | Geschwindigkeit |
|---------|----------------|-----------------|
| **Perpendicular Strip Median** | Sichere Default-Wahl; funktioniert bei flackernden Satelliten, Pearl-Spuren, Gradienten | Schnell |
| **Harmonic / Laplace** | Einheitlicher Sky, keine Pearls — mathematisch optimal glatte Füllung | Mittel |
| **Nearest Neighbor + Smooth** | Schnelle Vorschau, Fallback wenn andere nicht funktionieren | Schnell |
| **cv2 Fast Marching (Telea)** | Schnellste Option, gut für A/B-Tests | Am schnellsten |
| **cv2 Navier-Stokes** | Gleiche Geschwindigkeit wie Telea, leicht bessere Kanten-Propagation | Am schnellsten |
| **Biharmonic (experimentell)** | Nur für kurze isolierte Masken — lange dünne Masken ergeben „string of pearls" Ringing | Langsam |

### Detailerklärungen

#### Perpendicular Strip Median (empfohlener Default)

Rotiert das Bild so, dass die Spur horizontal liegt. Für jede Spalte im rotierten Raum werden die maskierten Pixel durch den **Median** von `strip_width` unmaskierten Pixeln darüber und darunter ersetzt. Dann zurückrotieren.

**Stärken:**
- **Erhält Sky-Gradienten** senkrecht zur Spur (Vignettierung, Lichtverschmutzungs-Verlauf) — PDE-Methoden würden sie wegmitteln.
- **Robust bei flackernden Satellitenspuren** — der Median verwirft die Pearl-Peaks an der Mittelachse als Ausreißer; PDE-Methoden übersteuern sie.
- Vektorisiert, schnell (~0,5 s auf 60 MP).

**Einstellbar:** `Strip width` — Anzahl der Pixel pro Seite, die sampled werden (Default 15). Breitere Strips glätten mehr, überbrücken längere Gradienten.

#### Harmonic / Laplace (∇²u = 0)

Löst die Laplace-Gleichung innerhalb der Maske mit dem umgebenden Sky als Dirichlet-Rand. Implementierung: Bbox-Crop mit iterativem 5-Punkt-Laplace-Smoothing und Nearest-Neighbour-Warm-Start. Konvergenz in ~150–400 Iterationen.

**Stärken:**
- **Maximum-Prinzip**: Die gefüllten Werte sind mathematisch durch die Boundary-Minima/Maxima begrenzt — kein Überschwingen, kein Ringing.
- Kombiniert mit **Match sky noise**: ergibt eine glatte physikalische Füllung PLUS realistisches Rauschen drauf, **statistisch nicht unterscheidbar** von echtem Sky.

**Schwäche:** Erhält keinen Cross-Trail-Gradient (mittelt ihn weg). Für einheitliche-Sky-Frames egal.

#### Nearest Neighbor + Smooth (schnell)

Für jeden maskierten Pixel findet `scipy.ndimage.distance_transform_edt` den nächsten unmaskierten Pixel und kopiert dessen Wert. Dann wird die gefüllte Region mit einem Gauss geglättet, dessen σ sich der Mask-Dicke anpasst (σ ≈ Halb-Dicke × 0,75) — glättet jeden sichtbaren Mittelachsen-Grat, an dem zwei senkrechte Füllungen aufeinandertreffen.

Sub-Sekunde pro Frame. Gute Fallback-Option, wenn andere Methoden Probleme machen.

#### cv2 Fast Marching / Telea

OpenCV's C++ Telea (2004) via `cv2.inpaint(INPAINT_TELEA)`. Intern über uint8 mit Perzentil-Skalierung (um 16-Bit + Float-Eingaben zu unterstützen, bei denen einige macOS-OpenCV-Builds still no-op'en). Jeder maskierte Pixel wird als normalisierte gewichtete Summe seiner bekannten Nachbarn gefüllt, mit Gewichten abhängig von geometrischer Distanz und Oberflächen-Richtung. Schnellste der cv2-Methoden.

#### cv2 Navier-Stokes

Bertalmio et al. 2001: modelliert die Inpaint-Region als Flüssigkeit und propagiert Isophoten (Niveaulinien der Intensität) in den maskierten Bereich, während lokale Bild-Glätte erhalten bleibt. Konzeptionell sauberer als Telea, gleiche Performance-Klasse, leicht bessere Kanten. Bei Sky-dominierten Regionen praktisch identisch zu Telea.

#### Biharmonic (experimentell)

`skimage.restoration.inpaint_biharmonic` löst die biharmonische PDE ∇⁴u = 0 auf einem gechunkten Bbox-Crop. Mathematisch sehr glatt.

**⚠️ Warnung:** Die biharmonische Gleichung hat **kein Maximum-Prinzip**, also übersteuert der Solver bei langen dünnen Masken (typisch 5000 × 15 px Satellitenspur) periodisch — der klassische „string of pearls"-Dunkelpunkt-Artefakt. Beim ersten Auswählen erscheint ein modaler Warn-Dialog mit „Don't show again"-Option.

Nur für **kurze, kompakte Masken** (einzelne isolierte Blobs), wo die Geometrie gut konditioniert bleibt.

### Match Sky Noise

Nach jeder Inpaint-Methode fügt dieser Post-Process Gauss-Rauschen innerhalb der Maske hinzu, mit σ robust (via sigma-clipped MAD) aus einem 30-px-Halo unmaskierten Skys um die Spur entnommen. Die gefüllte Region ist nun **statistisch ein Sky-Sample** — Stack-Rejection-Algorithmen können sie nicht von echtem Sky unterscheiden.

Default an. ~50 ms Overhead pro Frame. Nur für schnelle A/B-Tests ausschalten.

### Star Protection

Optional. Wenn an, detektiert Sterne im Bild und schließt sie aus der Inpaint-Maske aus, sodass sie die Reinigung überleben. Smart-Filter ignoriert „Sterne", die *innerhalb* der Trail-Maske liegen (das sind missklassifizierte Trail-Pixel-Peaks, keine echten Sterne).

Default aus, weil der naive Peak-Detektor Pearl-Peaks als Sterne misklassifiziert, was dann das Inpainten der Spur verhindert. Nur manuell anschalten, wenn du einen bekannten echten Stern im Spur-Halo hast, den du erhalten willst.

---

## 8. Die Empfehlungs-Anzeige

Nach jedem Detect erscheint eine blaue Anzeige unter dem Method-Dropdown:

> **💡 Recommendation: Perpendicular Strip Median** *(currently selected)*
> Strong sky gradient (2.4σ) across the trail — Perpendicular Strip Median preserves it. PDE methods would average it away.

Wenn deine aktuell gewählte Methode der Empfehlung entspricht, ist der **Apply**-Button ausgegraut und beschriftet „✓ in use". Andernfalls klick **Apply**, um zu wechseln.

Die Empfehlung basiert auf drei Messungen *deines konkreten Frames*:

| Feature | Detection | Empfehlung |
|---------|-----------|------------|
| **Cross-Trail-Gradient ≥ 2σ** | Parallele Strips ±30 px auf beiden Seiten der längsten Spur sampeln; Mediane vergleichen | → Perpendicular Strip Median (erhält Gradient) |
| **5+ helle Peaks entlang Spur-Achse** | Profil entlang Mittelachse sampeln bei sky + 5σ Schwelle; zusammenhängende Runs zählen | → Perpendicular Strip Median (Median verwirft Pearls) |
| **Kompakte Maske** (< 8 % der Diagonale, < 4000 px) | Spur-Länge + Mask-Fläche | → Harmonic + Match-sky-noise (glatter physikalischer Fill) |
| **Einheitlicher Sky, keine Pearls** | Default-Fall | → Harmonic + Match-sky-noise |
| Gemischte Bedingungen | Fallback | → Perpendicular Strip Median |

Du kannst immer manuell überstimmen. Die Empfehlung läuft nach jedem Detect neu.

---

## 9. Unterstützte Dateiformate

### FITS (`.fit`, `.fits`, `.fts`)

Das native Astrofotografie-Format. Cleaned Output ist FITS mit dem **Original-Header verbatim erhalten** — WCS, `DATE-OBS`, `BSCALE`/`BZERO`, alle Instrument-Keywords. Cleaning-Operationen werden als `HISTORY`-Zeilen angehängt. Plate-Solving-Info bleibt erhalten.

### XISF (`.xisf`)

PixInsights natives Format. Cleaned Output bleibt XISF mit **allen `FITSKeywords` UND `XISFProperties` erhalten** — inkl. PixInsight-style astrometrische Lösungen (`PCL:AstrometricSolution`-Matrizen), Kamera/Filter/Belichtungs-Metadaten. Cleaning-Operationen werden als `HISTORY`-Keywords angehängt. Output-Kompression matcht die Quell-Datei (NINA-saved unkomprimiertes XISF bleibt unkomprimiert; PixInsight LZ4HC-with-Shuffle bleibt gleich). Implementierung via [`xisf`](https://pypi.org/project/xisf/) Python-Paket.

### TIFF (`.tif`, `.tiff`, v0.8.0+)

Direkt-Read/Write via `tifffile`, bypasst Siril für bit-exakte Dtype-Kontrolle. Das Original-**Dtype** (uint8 / uint16 / uint32 / float32) bleibt erhalten. **Kompression** (LZW / ZSTD / Deflate / keine) wird gematcht. **Photometric Interpretation** (mono / RGB) bleibt erhalten. **PlanarConfiguration**-Tag wird beachtet. RGBA-Alpha-Kanäle werden mit Log-Warnung entfernt.

Das `ImageDescription`-TIFF-Tag wird mit angehängter Cleaning-History weitergegeben — Siril / ASTAP / NINA nutzen alle dieses Tag für Plate-Solve- und Processing-Notizen, also bleibt der Round-Trip erhalten.

### RAW (CR2 / CR3 / NEF / ARW / DNG / etc.)

Geladen und debayered via Siril/libraw. Cleaned RAW-Output ist immer **FITS**, weil Spur-Entfernung auf rohen CFA-Daten das Bayer-Pattern zerstören würde. Die gecleante Datei wird als `<name>.fit` geschrieben, das Original-RAW bleibt in `originals/`.

### `originals/` Unterordner

Jedes modifizierte Datei-Original wird vor dem Schreiben der gecleanten Version nach `<Quell-Ordner>/originals/<filename>` verschoben. **Wiederherstellung ist immer ein einfaches File-Move zurück.** Das Skript löscht nie etwas.

---

## 10. Der Apply-Workflow

### Apply to Current

Wendet die aktuelle Detection- + Inpaint-Einstellungen nur auf das aktuelle Frame an. Nützlich für gezieltes manuelles Cleanen einzelner Frames.

### Apply to All Frames

Bestätigt mit Dialog, dann Schleife über jedes Frame im Ordner:

1. **Laden** des Frames (Siril für FITS/RAW, direkt für TIFF/XISF)
2. **Detect** Spuren (nutzt dieselben Parameter wie dein Test-Frame)
3. Wenn keine Spur erkannt → skip, Datei unangetastet
4. (Optional, wenn **Confirm each frame** aktiv) Preview zeigen, User Yes/No/Cancel fragen
5. **Inpaint** mit der gewählten Methode
6. **Move** Original nach `originals/`
7. **Schreibe** gecleante Datei unter dem Original-Filename

### Parallele Batch-Pipeline (v0.8.8+)

Ohne Confirm-each läuft der Batch als **2-Stufen-Pipeline**: Während Frame N vom Main-Thread inpainted + geschrieben wird, wird Frame N+1 von einem Worker-Thread geladen + detected. Effektiver Wall-Clock-Speedup: ~1,5–2× bei Batches von 20+ Frames.

### Progress-Dialog (v0.8.9+)

3-zeiliger Status:

```
Frame 17/50: Lum__LIGHT_017.fit
Cleaned: 12   Skipped: 4   Errors: 1
Elapsed: 4:32   ETA: 9:15
```

Jeden Frame aktualisiert. **Cancel** ist sicher — der aktuell laufende Frame wird zu Ende verarbeitet (keine halb-geschriebenen Dateien), dann beendet sich die Schleife.

### Confirm-Each-Modus

Nützlich für den vorsichtigen ersten Lauf, oder wenn du jede Detection in einem gemischten Ordner manuell prüfen willst. Deaktiviert die parallele Pipeline (User-Reaktionszeit dominiert).

### Frames ohne Spur werden übersprungen

Das Skript fasst nie ein Frame an, bei dem Detect keine Spur fand. Original bleibt, kein `originals/`-Move, kein Audit-Eintrag außer dem Skip-Status.

### Rollback bei Fehler

Wenn der Schreib-Schritt fehlschlägt (Disk voll, Berechtigung verweigert, korrupte Quelle), wird das verschobene Original automatisch an seinen Platz zurückgelegt. Voller Stacktrace wandert ins Log zur Diagnose.

---

## 11. Das Audit-Protokoll

### `trail_cleanup_report.txt`

Menschenlesbares TSV im Quell-Ordner. Eine Zeile pro verarbeiteter Datei:

```
# Svenesis Satellite Trail Cleaner -- per-file audit
# Folder: /Users/me/Astro-Bilder/Komet-PANSTARRS
# A machine-readable JSON twin lives next to this file: trail_cleanup_report.json
# timestamp	status	lines	pixels_replaced	file	note
2026-05-16 17:30:12	cleaned	1	50543	Lum__LIGHT_001.fit	1 trail(s) detected; halo growth: +129 px...
2026-05-16 17:30:34	skipped_no_trail	0	0	Lum__LIGHT_002.fit	No candidates above threshold
2026-05-16 17:30:58	cleaned	1	49872	Lum__LIGHT_003.fit	1 trail(s) detected; halo growth: +98 px...
```

### `trail_cleanup_report.json` (v0.8.9+)

Maschinenlesbarer strukturierter Zwilling. Gleiche Daten, parsbar von Excel / pandas / jedem JSON-Konsument:

```json
{
  "folder": "/Users/me/Astro-Bilder/Komet-PANSTARRS",
  "records": [
    {
      "timestamp": "2026-05-16 17:30:12",
      "file": "Lum__LIGHT_001.fit",
      "path": "/Users/me/Astro-Bilder/Komet-PANSTARRS/Lum__LIGHT_001.fit",
      "status": "cleaned",
      "lines": 1,
      "pixels_replaced": 50543,
      "inpaint_method": "perp_strip",
      "mask_dilation": 7,
      "match_sky_noise": true,
      "scan_mode": "normal",
      "mono_mode": "mean",
      "cleaned_path": "/Users/me/Astro-Bilder/Komet-PANSTARRS/Lum__LIGHT_001.fit",
      "note": "1 trail(s) detected; halo growth: +129 px in 6 hops...",
      "tool_version": "0.8.9"
    }
  ]
}
```

Der JSON-Write ist **atomar** (Tempfile + Rename), sodass ein Crash mitten im Schreiben das Audit nicht korrumpiert.

### Status-Werte

| Status | Bedeutung |
|--------|-----------|
| `cleaned` | Spur erkannt und erfolgreich inpainted |
| `skipped_no_trail` | Keine Spur erkannt, Datei nicht modifiziert |
| `skipped_user` | User klickte No im Confirm-each-Dialog |
| `error` | Laden, Detection, Inpaint oder Schreiben fehlgeschlagen |

---

## 12. Tipps & Empfehlungen

### Auf einem guten Test-Frame justieren

Das Allererste: navigiere zum Frame mit der **klarsten, hellsten, repräsentativsten** Spur. Detection und Inpaint dort perfektionieren. Apply-to-All nutzt diese Einstellungen auf jedem Frame.

### Die Empfehlungs-Anzeige nutzen

Nach Detect zeigt die 💡-Anzeige die für dieses Frame optimale Methode mit One-Liner-Begründung. Klick Apply, außer du hast einen spezifischen Grund zu überstimmen.

### Im Cleaned Preview vor Apply prüfen

Schalte View → Cleaned Preview. Wenn du noch *irgendwas* an der Spur-Position sehen kannst — Pearls, dunkle Punkte, Spur-Reste — fixe es vor Apply. Oft die Lösung: **Mask dilation erhöhen** (heller Halo um Pearls reicht über die Default-7-px hinaus).

### Den richtigen Scan-Mode wählen

- Quick — nur schnelle Vorschau; kann schwache Spuren verpassen
- Normal — Alltags-Pferd; deckt 95 % der Fälle ab
- Deep — letzter Ausweg für sehr schwache Spuren; nutzt alle CPU-Cores

### Erst stacken, dann Cleaner laufen lassen (im Zweifel)

Wenn du 10+ Subs hast: erst **ohne** Cleaner stacken. Wenn du noch eine Rest-Spur im Ergebnis siehst, *dann* Cleaner laufen lassen und neu stacken. Bei ≤6 Subs: Cleaner zuerst.

### Vorsicht bei Kometen-Schweifen / Nebeln

Der Persistence-Test sollte Kometen-Schweife verwerfen (nicht-uniform entlang Linie), aber bei sehr langen hellen Kometen kann er versagen. Wenn Detect einen Kometen-Schweif als „Spur" aufnimmt — Persistence-Check ANSCHALTEN (verwirft sie meistens), oder **Max width** verschärfen.

### Der Originals-Ordner ist dein Sicherheitsnetz

Falls du je merkst, dass die gecleanten Dateien falsch sind (schlechte Einstellungen, falsche Methode), bleiben die Originale unangetastet in `originals/`. Manuell zurückschieben, oder warten — eine zukünftige Version bekommt einen „Restore originals"-Button.

### Confirm-each beim ersten echten Lauf

Wenn du neu mit dem Tool bist, aktiviere **Confirm each frame before writing** für deine erste Session. Du siehst jede Detection visuell, bevor Datei-Änderungen passieren. Nach 5–10 Frames weißt du, was zu erwarten ist, und kannst es deaktivieren.

### Star Protection: aus, außer wenn nötig

Default ist AUS, weil der naive Peak-Detektor Pearl-Peaks als Sterne misklassifiziert und dann das Inpainten verhindert. Nur manuell anschalten, wenn du einen verifizierten hellen Stern im Spur-Halo hast, den du gezielt erhalten willst.

---

## 13. Fehlerbehebung

### „No trails detected" — aber ich sehe eine!

Versuche, in dieser Reihenfolge:

1. **SNR threshold** senken (5,0 → 3,0)
2. **Min length** senken (50 → 20)
3. **Max width** erhöhen, falls sie aufgebläht aussieht (75 → 150)
4. **Check persistence** deaktivieren (schwache Spuren können den uniform-SNR-Test nicht bestehen)
5. **Scan mode** auf **Deep** umschalten
6. Als letztes: **RGB reduce** auf **Max per pixel** umstellen (hilft bei nur-ein-Kanal-Spuren)

### Cleaned Preview zeigt punktierte dunkle Punkte wo die Spur war

Klassisches „string of pearls"-Symptom. Zwei Ursachen:

1. **Du nutzt Biharmonic.** Wechsle zu Perpendicular Strip Median oder Harmonic. Die biharmonische Gleichung hat kein Maximum-Prinzip und produziert dieses Übersteuerungs-Artefakt bei langen dünnen Masken. Die Empfehlungs-Anzeige wird Biharmonic bei langen Spuren auch nicht vorschlagen.
2. **Mask dilation zu klein für helle Pearl-Halos.** Mask dilation von 7 auf 10–15 erhöhen. Der Bright-Halo-Growth-Schritt *sollte* das automatisch absorbieren, aber in manchen Fällen hilft die explizite Dilation.

### Cleaned Preview zeigt einen glatten Fleck ohne Rauschen

Du hast vermutlich **Match sky noise AUS**. Anschalten — die Rauschinjektion ist es, was die gecleante Region statistisch ununterscheidbar von echtem Sky macht.

### Detection findet 33 Kandidaten statt 1

False Positives. Schrittweise verschärfen:

1. **SNR threshold** hoch (5,0 → 8,0)
2. **Min length** hoch (50 → 100)
3. **Check persistence** anschalten, falls aus
4. **Max width** runter, falls die False Positives breit sind (75 → 30)

### Kometen-Kopf/Schweif wird als Spur erkannt

1. **Check persistence** anschalten — der Helligkeits-Gradient des Kometen besteht den uniform-SNR-Test nicht
2. **Max width** auf 30–40 px senken (Kometen-Schweife sind breiter als Satellitenspuren)
3. Die False-Positive-Linie im Canvas vor Apply manuell deselektieren

### Fenster erscheint winzig, Bedienelemente abgeschnitten

`win.showMaximized()` wird beim Start aufgerufen. Wenn dein Window-Manager das ignoriert (manche Tiling-WMs), maximiere manuell.

### Help zeigt den Workflow-Dialog bei jedem Start

Klick die **Don't show again** Checkbox im Workflow-Dialog. Zum Re-Aktivieren: **Help → Reset dismissed dialogs**.

### „Apply to All" ist langsam

- **Scan mode** prüfen — wenn du Deep auf 50 Frames gesetzt hast, mehrere Minuten sind normal
- Confirm-each ist an → für Batch-Läufe deaktivieren (parallele Pipeline wird umgangen, wenn Confirm-each an ist)
- **Processes**-Spinner — wenn du manuell niedrig gesetzt hast, den auto-getuneten Wert wiederherstellen (Scan-Mode im Dropdown neu wählen)

### Gecleantes XISF-File ist halb so groß wie Original

`tifffile`-Schreibvorgänge nutzen effiziente Kompression. Wenn Original unkomprimiert war, ist die gecleante Version jetzt zlib-komprimiert per Default. Das ist OK für Storage und PixInsight liest beide transparent.

### `acstools` Import-Fehler

Das Skript installiert `acstools` automatisch beim ersten Start via `s.ensure_installed`. Wenn das fehlschlägt, manuell im Siril-Python-Environment installieren: pip install acstools.

---

## 14. Häufige Fragen

**F: Sind die gecleanten Pixel „echte Daten" oder „Fake"?**
A: Sie sind *synthetisch* — interpoliert aus umliegenden Sky-Pixeln. Der Match-Sky-Noise-Schritt fügt Gauss-Rauschen hinzu, sodass das Ergebnis statistisch ununterscheidbar von echtem Sky ist für Stack-Rejection-Algorithmen. Für photometrische Arbeit behandle inpaintete Pixel als fehlende Daten: Wenn dein Science-Ziel *unter* der Spur liegt, verwirf den Frame komplett statt zu cleanen. Der Cleaner ist für Frames, wo die Spur durch leeren Sky läuft.

**F: Warum nutzt ihr nicht KI / Deep Learning?**
A: Deep-Learning-Inpainting-Modelle (LaMa, DeepFill, Stable Diffusion) sind auf natürliche Fotos trainiert und **halluzinieren Features**, die nicht existieren — erfundene Sterne, Galaxien, Bahtinov-Spikes. Das ist Fabrikation, keine Interpolation, und inkompatibel mit der wissenschaftlichen Haltung des zugrundeliegenden STScI-Detection-Algorithmus. Dieses Tool nutzt nur Methoden, die aus echten umliegenden Pixeln füllen.

**F: Bleibt Plate-Solving-Information erhalten?**
A: Ja. FITS-Header werden verbatim erhalten; XISF-FITSKeywords + XISFProperties (inkl. AstrometricSolution-Matrizen) werden erhalten; TIFF-ImageDescription wird weitergegeben. Cleaning-Operationen werden als HISTORY-Einträge angehängt.

**F: Kann ich ein Apply rückgängig machen?**
A: Manuell: die Files aus `originals/` zurück in den Quell-Ordner verschieben, gecleante Versionen ersetzen. Ein eingebauter „Restore originals"-Button steht auf der Roadmap.

**F: Warum ist die Default-Inpaint-Methode „Perpendicular Strip Median" und nicht das „höchste Qualität" Biharmonic?**
A: Biharmonic klingt gut, aber die biharmonische Gleichung hat *kein* Maximum-Prinzip, also übersteuert sie bei langen dünnen Satellitenspuren periodisch und produziert sichtbare dunkle Punkte („string of pearls"). Perpendicular Strip Median ist robust auf realen Daten inkl. flackernder Satelliten. Die Empfehlungs-Anzeige wählt die richtige pro Frame.

**F: Wie skaliert das Multiprocessing?**
A: Die MRT-Berechnung ist embarrassingly parallel über Theta-Winkel. Deep-Mode nutzt alle CPU-Cores → ~Nx Speedup bei Detection. Apply-to-All läuft zusätzlich als 2-Stufen-Pipeline (Load+Detect überlappt mit Inpaint+Write) für weitere ~1,5–2× Wall-Clock-Speedup.

**F: Funktioniert das Tool mit Mono- (Luminanz-only) Daten?**
A: Ja, das ist der häufigste Fall. Die RGB-Reduce-Option spielt nur eine Rolle bei echten Farb-FITS / XISF / TIFF mit 3 Kanälen.

**F: Kann ich die gecleanten Files mit PixInsight / Photoshop / Affinity / DeepSkyStacker teilen?**
A: Ja. FITS / XISF / TIFF Round-Trips erhalten alle Standard-Header und Metadaten. Jedes Tool, das diese Formate liest, liest auch die gecleanten Versionen.

**F: Meine Subs sind 60 MP je. Geht dem Tool der Speicher aus?**
A: Nein. Das Tool verarbeitet ein Frame zur Zeit (plus ein zusätzliches im Prefetch-Worker während Batch). Peak-Memory pro Frame: ~1 GB auf 60 MP RGB; ~250 MB auf 60 MP Mono. Die parallele Pipeline addiert ~1 zusätzliches Frame-Äquivalent.

**F: Ist die Empfehlungs-Anzeige perfekt?**
A: Sie ist eine Heuristik basierend auf drei Messungen (Cross-Trail-Gradient, Pearl-Count, Mask-Kompaktheit). Sie wählt die richtige Methode in vielleicht 90 % der Fälle. Bei Edge-Cases (sehr schwache Spuren, starke Nebel-Nähe), manuell überstimmen.

---

## 15. Wissenschaftlicher Hintergrund — Warum wir inpainten

### Was STScI macht (und nicht macht)

Das Detection-Backend in diesem Tool ist **STScI's `findsat_mrt.TrailFinder`** — derselbe Median-Radon-Transform-Algorithmus, der in Stark, Avila, Anderson et al. (ACS ISR 2022-08) veröffentlicht und zur Satellitenspur-Erkennung in HST/ACS-Bildern eingesetzt wird.

Wichtig: Die Original-Arbeit empfiehlt **KEINEN** spezifischen Inpainting-Algorithmus. Sie behandelt die Output-Maske als Data-Quality-Flag für die downstream HST-Pipeline (`AstroDrizzle`), die mehrere Belichtungen kombiniert und einfach die maskierten Pixel **verwirft** — die Sky-Information für die Spur-Region kommt aus den *anderen* Belichtungen im Stack, nicht aus räumlicher Interpolation. Das ist der sauberste mögliche Ansatz: jedes Output-Pixel ist eine echte Messung aus einem Sub, niemals eine Schätzung.

### Warum wir abweichen

STScI's Mask-and-Reject-Ansatz erfordert **genügend Belichtungen**, damit die Rejection einen sauberen Sky in der Spur-Region hinterlässt. HST-Programme haben typisch 8–16+ gut-dithered Sub-Belichtungen — die Spur in einem einzelnen Sub ist statistisch ein Ausreißer, den der σ-Clip sauber verwirft.

Amateur-Astrofotografie hat meist 4–6 Subs (oft weniger bei seltenen Zielen). Bei n=5 hat σ-Clipping eines einzelnen Ausreißers nicht genug überlebende Population, um einen konfidenten Sky-Schätzer zu hinterlassen; unter n=4 ist es statistisch nicht möglich. Die Spur überlebt den Stack und verschlechtert das Endbild.

**Diese Lücke füllt dieses Tool.** Räumliches Inpainting pro Frame, *vor* dem Stacken, sorgt dafür, dass der σ-Clip in Sirils Stacker auf bereits sauberen Inputs läuft.

### Wie wir HST-treu im Geist bleiben

Auch wenn räumliches Inpainting synthetische Daten einführt, leitet die HST-Tradition, **keine Strukturen zu halluzinieren**, unsere Defaults:

- Die Default-Methode, **Perpendicular Strip Median**, kopiert den Median des lokalen Skys senkrecht zur Spur — kein Modell, kein gelernter Prior, keine erfundenen Sterne.
- **Match-sky-noise** fügt Gauss-Rauschen mit σ entsprechend dem lokalen Sky hinzu. Die gefüllte Region ist statistisch ein Sky-Sample.
- **Star Protection** schließt erkannte Sterne aus der Maske aus, damit wir nie einen echten Stern durch Sky ersetzen.
- Wir **liefern bewusst kein Deep-Learning-Inpainting**, weil diese Modelle Sterne, Galaxien und Bahtinov-Spike-artige Strukturen halluzinieren, die nicht in den Originaldaten sind. Das wäre Fabrikation, keine Interpolation, und inkompatibel mit der wissenschaftlichen Haltung des zugrundeliegenden STScI-Algorithmus.

### Wann das Tool nicht nötig ist

Wenn dein Stack **8 oder mehr gut-dithered Subs** hat und die Spur nicht in mehreren davon wiederholt vorkommt, ist Sirils eingebauter σ-Clip / Winsorized / Linear-Fit Rejection im `Stacking → Image stacking` mathematisch die richtige Wahl. Er nutzt echte Messungen, keine Schätzungen. Dieses Tool ist am nützlichsten im Regime, wo σ-Clip kein sauberes Ergebnis erreichen kann: wenige Subs, wiederholte Spuren, oder Spuren, die durch Science-Ziele laufen und du den Frame erhalten willst.

### Referenz

> Stark, D., Avila, R. J., Anderson, J., et al. 2022, *findsat_mrt: A New Algorithm for Detecting Linear Features in Astronomical Images*, ACS Instrument Science Report 2022-08, STScI.

---

*Erstellt von [Svenesis](https://www.svenesis.org). [Spendier mir einen Kaffee ☕](https://buymeacoffee.com/sramuschkat), wenn das dein Stack gerettet hat.*
