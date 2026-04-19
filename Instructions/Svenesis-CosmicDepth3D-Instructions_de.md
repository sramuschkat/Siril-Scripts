# Svenesis CosmicDepth 3D — Benutzeranleitung

**Version 1.0.0** | Siril-Python-Skript zur 3D-Tiefenvisualisierung plate-gelöster Bilder

> *Sehen Sie Ihr Bild nicht mehr als flaches 2D-Foto, sondern als Fenster in ein dreidimensionales Universum — jedes katalogisierte Objekt schwebt in seiner tatsächlichen Entfernung hinter der Himmelsebene, auf einem „Stecknadel-Stiel", der genau auf dem Pixel landet, an dem Sie es fotografiert haben.*

---

## Inhaltsverzeichnis

1. [Was ist CosmicDepth 3D?](#1-was-ist-cosmicdepth-3d)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Skalierungsmodi & Sichtbereiche](#6-skalierungsmodi--sichtbereiche)
7. [Objekttypen & Farbcodierung](#7-objekttypen--farbcodierung)
8. [Filter & Datenquellen](#8-filter--datenquellen)
9. [Die 3D-Szene — Navigation & Interpretation](#9-die-3d-szene--navigation--interpretation)
10. [Entfernungsauflösung — Woher kommen die Distanzen?](#10-entfernungsauflösung--woher-kommen-die-distanzen)
11. [Export (HTML / PNG / CSV)](#11-export-html--png--csv)
12. [WebEngine-Reparaturdialog](#12-webengine-reparaturdialog)
13. [Anwendungsfälle & Arbeitsabläufe](#13-anwendungsfälle--arbeitsabläufe)
14. [Tastaturkürzel](#14-tastaturkürzel)
15. [Tipps & Empfehlungen](#15-tipps--empfehlungen)
16. [Fehlerbehebung](#16-fehlerbehebung)
17. [Häufige Fragen](#17-häufige-fragen)

---

## 1. Was ist CosmicDepth 3D?

Das **Svenesis CosmicDepth 3D**-Skript nimmt Ihr plate-gelöstes Astrofoto und jedes darin enthaltene katalogisierte Objekt, löst deren echte Entfernungen aus SIMBAD auf und rendert das gesamte Feld als interaktive, drehbare 3D-Szene.

- Ihr Bild sitzt als **flache „Himmelsebene"** vorne in der Szene — das Fenster, durch das Sie fotografiert haben.
- Jedes katalogisierte Objekt schwebt in seiner **echten Entfernung** hinter dem Fenster auf einem **Stecknadel-Tiefenstiel**, der genau auf dem Pixel landet, an dem das Objekt im Bild erscheint.
- Ziehen zum Drehen, Scrollen zum Zoomen, Hovern über Marker für Entfernung / Unsicherheit / Quelle pro Objekt.
- Export als interaktive HTML-Datei, als hochauflösendes PNG aus Ihrer aktuellen Blickrichtung oder als CSV-Tabelle aller Objekte mit Distanzen.

Das Ergebnis: Ein **Vordergrundnebel in 1 344 Lj** und eine **Hintergrundgalaxie in 30 Millionen Lj** sehen endlich so aus, wie sie tatsächlich sind — nicht wie zwei flache Bildelemente im selben Rahmen. Eine intuitive Art zu sehen, was Ihr Bild wirklich zeigt: einen Querschnitt durch ein Universum aus enorm unterschiedlichen Entfernungen, projiziert auf ein einziges 2D-Foto.

---

## 2. Hintergrundwissen für Einsteiger

### Warum „3D" aus einem 2D-Bild?

Ein Himmelsfoto bildet alles auf eine einzige Bildebene ab. Ihr Auge kann nicht unterscheiden, ob ein Nebel zehnmal oder zehn Millionen Mal weiter entfernt ist als ein benachbarter Stern. CosmicDepth 3D ergänzt die **Tiefenachse**, indem es für jedes katalogisierte Objekt die echte Entfernung in SIMBAD nachschlägt und die Objekte hinter dem Bild staffelt.

Was Sie in der 3D-Ansicht sehen:
- **X-Achse** — Entfernung von der Erde (Lichtjahre, standardmäßig gestreckte Log-Skala).
- **Y-Achse** — horizontale Pixelposition in Ihrem Bild.
- **Z-Achse** — vertikale Pixelposition in Ihrem Bild.

Die Himmelsebene ist flach wie ein Fenster. Jeder Tiefenstiel steht senkrecht auf diesem Fenster, verankert an genau dem Pixel, an dem das Objekt in Ihrem Foto zu sehen ist.

### Was bedeutet „plate-gelöst"?

**Plate Solving** ermittelt die exakten Himmelskoordinaten Ihres Bildes. Dabei wird das Sternmuster Ihres Fotos mit einem Sternkatalog abgeglichen, um zu bestimmen, wohin Ihr Teleskop gerichtet war.

Nach dem Plate Solving enthält Ihr Bild eine **WCS (World Coordinate System)**-Lösung im FITS-Header. Diese teilt Software mit: „Pixel (500, 300) entspricht RA 12h 30m, DEC +41° 20′." CosmicDepth 3D braucht das, um zu wissen, welche katalogisierten Objekte in Ihrem Bildfeld liegen und wo sie im Bild erscheinen.

| Konzept | Erklärung |
|---------|-----------|
| **RA / DEC** | Himmelslängen- und -breitengrade. Jeder Punkt am Himmel hat ein eindeutiges (RA, DEC). |
| **WCS** | Die Pixel-zu-Himmel-Zuordnung, die nach dem Plate Solving im FITS-Header gespeichert wird. |
| **SIMBAD** | Eine astronomische Online-Datenbank mit Positionen, Typen und Entfernungsmessungen für Millionen von Objekten. |
| **Parsec, Lichtjahr** | Entfernungseinheiten. 1 Parsec ≈ 3,26 Lichtjahre. Wir verwenden hier Lichtjahre. |
| **Rotverschiebung (z)** | Ein Maß dafür, wie weit entfernt (und wie schnell sich entfernend) eine Galaxie ist. Wird zur Entfernungsschätzung jenseits ~3 Mrd. Lj verwendet. |

### Warum eine gestreckte Log-Distanzachse?

Eine rein lineare Achse lässt Galaxien verschwinden — eine 30 Mio.-Lj-Galaxie ist 20 000× weiter als ein 1 500-Lj-Nebel, sodass der Nebel auf der Bildebene zu einem Punkt kollabiert. Eine reine Log-Achse behebt das, gibt aber jeder Dekade die gleiche Breite — damit wird der Galaxien-Fernbereich (100 Mio. Lj → 10 Mrd. Lj) am rechten Rand zusammengequetscht. Die Standardeinstellung **gestreckte Log-Achse** gibt dem Fernbereich dreimal mehr Platz, ohne die innere Milchstraße unleserlich zu machen. Siehe Abschnitt 6.

---

## 3. Voraussetzungen & Installation

### Voraussetzungen

| Komponente | Mindestversion | Hinweise |
|------------|----------------|----------|
| **Siril** | 1.4.0+ | Python-Skript-Unterstützung muss aktiviert sein |
| **sirilpy** | Gebündelt | Im Lieferumfang von Siril 1.4+ |
| **numpy** | Aktuell | Automatische Installation |
| **PyQt6** | 6.x | Automatische Installation |
| **matplotlib** | 3.x | Automatische Installation (für den PNG-Fallback) |
| **astropy** | Aktuell | Automatische Installation |
| **astroquery** | Aktuell | Automatische Installation — erforderlich für SIMBAD-Abfragen |
| **plotly** | Aktuell | Automatische Installation — der 3D-Szenen-Renderer |
| **kaleido** | Aktuell | Automatische Installation — Plotlys statischer PNG-Renderer |
| **PyQt6-WebEngine** | passend zu PyQt6 | Wird beim Start geprüft; falls fehlend oder ABI-inkompatibel, bietet das Skript einen Reparaturdialog in der Anwendung (Abschnitt 12) und fällt in der Zwischenzeit auf die Browser-Ansicht zurück |
| **Internetverbindung** | — | Erforderlich für die ersten SIMBAD-Abfragen; spätere Renders nutzen den lokalen Entfernungs-Cache |

### Installation

1. Laden Sie `Svenesis-CosmicDepth3D.py` aus dem [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts).
2. Legen Sie die Datei in Ihr Siril-Skriptverzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Processing → Scripts**.

Das Skript installiert fehlende Python-Abhängigkeiten beim ersten Start automatisch via `s.ensure_installed(...)`.

---

## 4. Erste Schritte

### Schritt 1: Plate-gelöstes Bild laden

CosmicDepth 3D benötigt ein **plate-gelöstes Bild**. Falls Ihr Bild noch nicht gelöst ist, verwenden Sie zuerst in Siril **Tools → Astrometry → Image Plate Solver…**.

### Schritt 2: Skript ausführen

Wählen Sie **Processing → Scripts → Svenesis CosmicDepth 3D**.

Das Fenster öffnet sich mit:
- Einer **linken Seitenleiste** mit Steuerelementen (Include Objects, View Mode & Scaling, Filters, Data Sources, Output, Actions).
- Einer **rechten Seitenleiste** mit drei Tabs: **3D Map**, **Objects**, **Log**.

### Schritt 3: Konfiguration

1. **Include Objects** — kreuzen Sie an, welche Objekttypen enthalten sein sollen (Galaxien, Nebel, Offene Sternhaufen usw.). **Select All** / **Deselect All** für schnelles Umschalten.
2. **View Mode & Scaling** — wählen Sie einen **Range** (Cosmic / Galactic) und eine **Scale** (Log / Linear / Hybrid). Aktivieren Sie **Show image as sky plane**, um das Foto als 3D-Fenster zu sehen; deaktivieren Sie es für eine abstrakte Punktwolke.
3. **Filters** — Helligkeitsgrenze, maximale Objektanzahl, Schalter „Only objects with known distance".
4. **Data Sources** — **Query SIMBAD online** für den ersten Render eingeschaltet lassen; **Clear Distance Cache** nach großen SIMBAD-Aktualisierungen.
5. **Output** — Basisdateiname und PNG-DPI (150 für Bildschirme, 300 für Druck).

### Schritt 4: Render

Klicken Sie **Render 3D Map** (oder drücken Sie **F5**).

Die Statusleiste zeigt den Fortschritt:
- **0–15 %** — Bild einlesen und Himmelsebene aufbauen.
- **15–40 %** — SIMBAD-Abfragen für Objekte im Feld (parallele Tiling-Abfragen).
- **40–70 %** — Entfernungsauflösung je Objekt.
- **70–100 %** — 3D-Figur bauen und in die eingebettete Ansicht laden.

### Schritt 5: Erkunden

- **Ziehen** im 3D-Map-Tab zum Drehen. **Scrollen** zum Zoomen. **Hovern** über einem Marker zeigt Entfernung, Unsicherheit und Quelle.
- Wechseln Sie zum **Objects**-Tab für die sortierbare Gesamttabelle.
- Wechseln Sie zum **Log**-Tab für einen detaillierten Diagnose-Trace.

### Schritt 6: Export

**Export HTML / PNG / CSV** speichert die Szene. **Drehen Sie das Bild zuerst** in den gewünschten Blickwinkel — der PNG-Export erfasst Ihre aktuelle Kamera-Position, sodass das gespeicherte Bild dem Bildschirm entspricht.

---

## 5. Die Benutzeroberfläche

### Linke Seitenleiste (Steuerung)

#### Include Objects
Farbcodierte Checkboxen für die 12 Objekttypen (Galaxien, Nebel, Planetarische Nebel, Offene Sternhaufen, Kugelsternhaufen, Benannte Sterne in der linken Spalte — alle standardmäßig EIN; Reflexionsnebel, Supernova-Überreste, Dunkelnebel, HII-Regionen, Asterismen, Quasare in der rechten Spalte — alle standardmäßig AUS). **Select All** / **Deselect All** darunter.

#### View Mode & Scaling
- **Range:** Cosmic (alle Entfernungen) oder Galactic (nur < 100 000 Lj).
- **Scale:** Log (Standard, gestreckt), Linear oder Hybrid.
- **Color by type** — Marker nach Objekttyp einfärben statt einheitlich hellgrau.
- **Show image as sky plane** — das Foto als flaches 3D-Fenster mit Tiefenstielen rendern; deaktiviert ergibt sich eine abstrakte Karte.

#### Filters
- **Mag limit** (1,0 – 20,0, Standard 12,0) — nur Objekte heller als diese Magnitude einbeziehen. Objekte ohne katalogisierte Magnitude (Dunkelnebel, große HII-Regionen) sind immer enthalten.
- **Max objects** (10 – 5 000, Standard 200) — Obergrenze für die Anzahl gerenderter Marker. Wenn die Grenze überschritten wird, werden die hellsten Objekte behalten.
- **Only objects with known distance** — lässt Objekte weg, die sonst eine Typ-Median-Fallback-Distanz verwenden würden.

#### Data Sources
- **Query SIMBAD online** — standardmäßig an. Ausschalten, um nur mit dem lokalen Cache zu arbeiten.
- **Clear Distance Cache** — verwirft den lokalen JSON-Cache, sodass der nächste Render alle Objekte neu abfragt. Das Label daneben zeigt die aktuelle Cache-Größe („Cache: 347 objects").

#### Output
- **Filename** (Standard `cosmic_depth_3d`) — Basisname für Exporte. Ein Zeitstempel wird automatisch angehängt.
- **PNG DPI** (72 – 300, Standard 150) — Auflösung des PNG-Exports.

#### Actions
- **Render 3D Map** — der Hauptbutton. Auch an **F5** gebunden.
- **Export HTML / PNG / CSV** — nach dem ersten erfolgreichen Render aktiv.
- **Open Output Folder / Open Rendered HTML** — nach einem PNG- oder HTML-Export aktiv.

Unten: **Buy me a Coffee**, **Help** und **Close**.

### Rechte Seitenleiste (Tabs)

- **3D Map** — die eingebettete, drehbare Plotly-Szene. Falls PyQt6-WebEngine nicht verfügbar ist, erscheint hier ein roter Banner mit einem **Repair WebEngine…**-Button.
- **Objects** — sortierbares `QTableWidget` mit den Spalten **Name**, **Type**, **Mag**, **Distance (ly)**, **± Uncertainty**, **Source**. Spaltenüberschrift anklicken für numerische Sortierung. Spaltenbreiten und Sortierreihenfolge bleiben zwischen Sitzungen erhalten.
- **Log** — Monospace-Diagnose-Trace: SIMBAD-Tile-Zahlen, Cache-Trefferquote, Fallback-Gründe, Exportpfade.

---

## 6. Skalierungsmodi & Sichtbereiche

Die Distanzachse ist die zentrale Designentscheidung des ganzen Tools. Ihre Nebel liegen bei einigen hundert bis einigen tausend Lichtjahren; Ihre Galaxien bei zig Millionen bis Milliarden. Das sind neun Größenordnungen in einer Szene — und keine einzelne Achsenwahl ist für alles ideal.

### Scale: Log (Standard — gestreckt)

Stückweise logarithmische Achse, die dem Galaxien-Fernbereich zusätzlichen Platz gibt:

- **Jede Dekade unter 100 Mio. Lj nimmt 1 Einheit Achsenlänge ein** (reines Log): 1 → 10 → 100 → 1k → 10k → 100k → 1M → 10M → 100M.
- **Jede Dekade ab 100 Mio. Lj nimmt 3 Einheiten ein**: 100M → 1B → 10B → 100B bekommen jeweils dreimal so viel Platz wie beim reinen Log.

Die Tick-Beschriftungen lesen sich weiterhin in echten Lichtjahren („1", „10", „100", „1k", …, „100M", „1B", „10B"). Die Streckung ist in den Beschriftungen unsichtbar — nur der Abstand ändert sich, sodass ferne Galaxien nicht mehr am rechten Rand eingequetscht werden. Empfohlen für **jedes Feld, das Milchstraßensterne/Nebel mit externen Galaxien mischt**.

### Scale: Linear

Echte proportionale Entfernungen. Ein 1 500-Lj-Nebel und eine 30-Mio.-Lj-Galaxie erhalten einen Abstand proportional zu ihrem tatsächlichen 20 000-fachen Unterschied. In der Praxis bedeutet das: **Galaxien verschwinden am Horizont** und Sie sehen nur nahe Strukturen. Nützlich für reine Sternfelder innerhalb der Milchstraße, wo lineare Abstände sinnvoll sind.

### Scale: Hybrid

Linear von 0 bis 10 000 Lj, logarithmisch darüber. Realistische Sonnennachbarschaft mit extragalaktischem Kontext. Ein Kompromiss, wenn nahe Sterne in proportionaler Entfernung erscheinen sollen, ferne Galaxien aber im selben Rahmen dargestellt werden müssen.

### Range: Cosmic vs. Galactic

- **Cosmic** (Standard) — alle Objekte im Feld, bis hin zu Quasaren in Milliarden Lichtjahren.
- **Galactic (< 100k ly)** — alles jenseits ~100 000 Lj wird weggelassen. Nützlich für reine Milchstraßenfelder, in denen Galaxien nur stören würden, oder wenn Sie gezielt Sterne, Nebel und Haufen innerhalb unserer Galaxie zeigen möchten.

### Welche Wahl passt wann?

| Ihr Bild | Empfehlung |
|----------|------------|
| Deep-Sky mit Galaxien (Galaxienfelder, Galaxienhaufen) | **Log + Cosmic** |
| Milchstraßen-Sternfeld / Nebel-only | **Hybrid + Galactic** (oder Log + Galactic) |
| Weitfeld-Milchstraßenpanorama mit einigen Hintergrundgalaxien | **Log + Cosmic** |
| Nahaufnahme eines einzelnen hellen Nebels | **Hybrid + Galactic** |
| Sonnennachbarschafts-Sternfeld (< ein paar kLj) | **Linear + Galactic** |

---

## 7. Objekttypen & Farbcodierung

Gleiches Farbschema wie Annotate Image, ergänzt um typische Entfernungsbereiche zum schnellen Plausibilitätscheck:

| Farbe | Typ | Typische Entfernung | Standard |
|-------|-----|---------------------|----------|
| Gold | Galaxien | 2 MLj – Milliarden Lj | EIN |
| Rot | Emissionsnebel | 500 – 10 000 Lj | EIN |
| Grün | Planetarische Nebel | 1 000 – 10 000 Lj | EIN |
| Hellblau | Offene Sternhaufen | 400 – 15 000 Lj | EIN |
| Orange | Kugelsternhaufen | 10 000 – 100 000 Lj | EIN |
| Weiß | Benannte Sterne | 10 – 5 000 Lj (meist < 1 000) | EIN |
| Hellrot | Reflexionsnebel | 400 – 1 500 Lj | AUS |
| Magenta | Supernova-Überreste | 500 – 30 000 Lj | AUS |
| Grau | Dunkelnebel | 400 – 2 000 Lj | AUS |
| Rot-Rosa | HII-Regionen | 1 000 – 30 000 Lj | AUS |
| Blassblau | Asterismen | verschieden (Typ-Median) | AUS |
| Violett | Quasare | Milliarden Lj | AUS |

**Color by type** (Standard EIN) färbt jeden Marker nach seinem Typ. Ausschalten für eine einfarbige Szene — manchmal übersichtlicher in sehr dichten Galaxienfeldern.

---

## 8. Filter & Datenquellen

### Magnitude-Grenze

Standard 12,0. Steuert die schwächsten berücksichtigten Objekte:
- **8–10** — saubere Szene, nur hellste Objekte.
- **12,0** — guter Standard.
- **14–16** — dichte Szene, inklusive vieler schwacher Galaxien.
- **18–20** — sehr dicht; der Filter **Max objects** wird dann zur primären Dichte-Steuerung.

Objekte ohne katalogisierte Magnitude (Dunkelnebel, einige HII-Regionen) sind unabhängig von der Grenze immer enthalten.

### Max objects

Standard 200. Harte Obergrenze für die Anzahl gerenderter Marker. Wenn mehr Objekte die Typ/Magnituden-Filter passieren als erlaubt, werden die hellsten behalten. Nützlich bei Galaxienhaufen-Feldern mit Hunderten von Kandidaten, wo die Marker sich sonst gegenseitig verdecken würden.

### Only objects with known distance

Standard AUS. Wenn EIN, werden Objekte ausgeschlossen, die eine Typ-Median-Fallback-Distanz verwenden (in der Objects-Tabelle als `Type median` gekennzeichnet). Für Publikationen, bei denen jeder Marker durch eine echte SIMBAD-Messung gestützt sein soll.

### Query SIMBAD online

Standard EIN. Ausschalten, um ausschließlich mit dem lokalen Entfernungs-Cache (`~/.config/svenesis/cosmic_depth_cache.json`, 90 Tage TTL) zu arbeiten. Nützlich, wenn Sie dasselbe Feld bereits einmal gerendert haben und nun offline Skalierung/Filter durchprobieren möchten.

### Clear Distance Cache

Ein-Klick-Button zum Verwerfen des Entfernungs-Caches. Das Label zeigt die aktuelle Cache-Größe. Nützlich nach größeren SIMBAD-Updates oder bei Verdacht auf eine falsche gecachte Entfernung.

---

## 9. Die 3D-Szene — Navigation & Interpretation

### Navigation

| Aktion | Maus / Tastatur |
|--------|-----------------|
| **Drehen** | Linke Maustaste gedrückt halten und ziehen |
| **Verschieben** | Shift + linke Maustaste + ziehen |
| **Zoomen** | Mausrad |
| **Ansicht zurücksetzen** | Doppelklick in die Szene |
| **Detailinfo** | Maus über Marker bewegen — zeigt Name, Entfernung, Unsicherheit, Quelle |

### Achsen

- **X (horizontale Tiefe)** — Entfernung von der Erde in Lichtjahren. Auf der Log-Skala die gestreckte Log-Achse (Abschnitt 6). Die Erde sitzt bei X = 0 (die Himmelsebene ist dort verankert, bzw. auf der Log-Achse sehr nahe daran).
- **Y (links-rechts)** — horizontale Pixelposition in Ihrem Bild. Gespiegelt, damit der Standard-Blickwinkel links/rechts genauso liest wie das Siril-Bild.
- **Z (oben-unten)** — vertikale Pixelposition in Ihrem Bild. FITS-Zeile 0 ist unten, passend zur Siril-Bilddarstellung.

### Himmelsebene vs. abstrakte Ansicht

- **Show image as sky plane EIN (Standard)** — Ihr Foto wird als flaches, nicht-transparentes Rechteck vorne in der Szene gerendert. Jedes Objekt sitzt dahinter auf einem Tiefenstiel, der genau auf dem Pixel landet, an dem das Objekt im Foto erscheint. Die „Fenster-ins-Universum"-Ansicht.
- **Show image as sky plane AUS** — das Foto wird ausgeblendet. Sie sehen nur die 3D-Wolke der Marker plus eine Referenzebene. Sauberer für Präsentationen; für Astrofotografen ist die Himmelsebene intuitiver.

### Was die Tiefenstiele aussagen

Jeder Stiel verläuft senkrecht von der Himmelsebene zum Marker des Objekts. Die **Stiellänge ist die echte Entfernung** des Objekts, auf der gewählten Skala. Ein Stiel, der kaum hinter die Ebene reicht, ist nah (einige hundert Lj); ein Stiel, der bis zur anderen Seite der Szenenbox reicht, ist eine ferne Galaxie (zig oder hunderte Mio. Lj).

---

## 10. Entfernungsauflösung — Woher kommen die Distanzen?

Die Entfernung jedes Objekts wird über eine **Prioritätskette** aufgelöst, das Ergebnis steht in der Spalte **Source** der Objects-Tabelle:

1. **Lokaler Cache-Treffer** (`svenesis cache`) — das Objekt wurde innerhalb der letzten 90 Tage in einem vorherigen Render aufgelöst.
2. **SIMBAD `mesDistance`-Tabelle** (`SIMBAD mesDistance`) — eine direkte, katalogisierte Entfernungsmessung. Höchste Qualität; wird für die meisten gut studierten Galaxien, Nebel und nahen Sterne verwendet.
3. **Rotverschiebung × Hubble-Gesetz** (`SIMBAD redshift`) — für Objekte mit Rotverschiebung (z), aber ohne direkte Distanz wird `d = cz / H₀` (H₀ = 70 km/s/Mpc) berechnet. Verwendet für Galaxien und Quasare mit z < 0,5.
4. **Typ-Median-Fallback** (`Type median`) — für Objekte, bei denen weder Entfernung noch Rotverschiebung in SIMBAD vorliegen, wird ein sinnvoller Median-Wert für den Objekttyp verwendet (z. B. ~1 500 Lj für Emissionsnebel, ~5 000 Lj für offene Haufen). Klar gekennzeichnet, damit Sie es nicht mit einer echten Messung verwechseln.

Die Spalte **± Uncertainty** spiegelt die Genauigkeit der Quelle wider. Typ-Median-Fallbacks haben große Unsicherheiten; direkte SIMBAD-Messungen kleine.

### Entfernungs-Cache

Der Cache liegt in `~/.config/svenesis/cosmic_depth_cache.json`. Er hat eine **90-Tage-TTL** — ältere Einträge werden ignoriert und neu abgefragt. Ein zweiter Render desselben Feldes ist nahezu sofort, weil alle Entfernungen aus dem Cache kommen.

---

## 11. Export (HTML / PNG / CSV)

Alle drei Export-Buttons werden nach dem ersten erfolgreichen Render aktiv.

### HTML-Export

Schreibt eine eigenständige `.html`-Datei mit der gesamten interaktiven Plotly-Szene (inklusive eingebettetem `plotly.min.js`). Öffnen Sie sie in jedem Browser und Sie haben dieselbe Dreh-, Zoom- und Hover-Erfahrung wie in der App. Ideal zum Teilen mit Leuten, die kein Siril haben.

### PNG-Export

Schreibt ein hochauflösendes PNG via Plotly + kaleido. Zwei wichtige Designentscheidungen:

1. **Das exportierte Bild entspricht Ihrem aktuellen Blickwinkel.** Bevor Sie Export PNG klicken, drehen Sie die Ansicht in den Winkel, den Sie im gespeicherten Bild haben möchten. Der Export liest die aktuelle Plotly-Kamera (eye/center/up) und wendet sie auf die Ausgabe an.
2. **Pixelgenaue Übereinstimmung mit der Live-Ansicht.** Das PNG wird von derselben Plotly-Engine gerendert wie die eingebettete Ansicht, mit einer DPI-abhängigen Auflösung (Basis 1400 × 1000, skaliert mit DPI/100). So stimmen gestreckte Log-Achse, Farben, Marker und Tiefenstiele mit der Bildschirmansicht überein.

Falls `kaleido` fehlt, fällt das Skript auf einen matplotlib-Snapshot zurück — das Log sagt das und schlägt `pip install --upgrade kaleido` vor.

### CSV-Export

Schreibt eine vollständige Objekttabelle mit den Spalten: `name`, `type`, `ra_deg`, `dec_deg`, `mag`, `size_arcmin`, `distance_ly`, `uncertainty_ly`, `source`, `confidence`, `pixel_x`, `pixel_y`.

Nützlich für:
- Archivierung der exakten Objektliste zu einem Render.
- Weiterverarbeitung der Entfernungen in anderen Werkzeugen (Tabellenkalkulation, andere Skripte).
- Peer-Review einer verdächtig wirkenden Distanz (`source` zeigt die verwendete Methode).

### Speicherort

Alle Exporte landen in Sirils Arbeitsverzeichnis mit angehängtem Zeitstempel:
```
cosmic_depth_3d_20250815_213012.html
cosmic_depth_3d_20250815_213012.png
cosmic_depth_3d_20250815_213012.csv
```

**Open Output Folder** und **Open Rendered HTML** (unter den Export-Buttons) springen direkt dorthin.

---

## 12. WebEngine-Reparaturdialog

Die interaktive 3D-Ansicht wird mit `QWebEngineView` gerendert, das aus dem separaten Paket `PyQt6-WebEngine` stammt. Auf manchen Systemen passt die installierte Version nicht zur gebündelten `PyQt6` von Siril, was einen Import-Fehler produziert:

```
ImportError: ... Symbol not found: _qt_version_tag_6_XX
```

Wenn das passiert, installiert CosmicDepth 3D **nicht stillschweigend** etwas im Hintergrund. Stattdessen:

1. Der 3D-Map-Tab zeigt einen **roten Banner** mit dem genauen Fehler und einem **Repair WebEngine…**-Button.
2. Ein Klick öffnet einen Dialog mit:
   - Dem exakten pip-Befehl, den der Dialog ausführen wird (markierbar, damit Sie ihn bei Bedarf in ein Terminal kopieren können).
   - Einer schreibgeschützten Live-Konsole, die pips stdout/stderr in Echtzeit streamt — Sie sehen Wheel-Auflösung, Download-Fortschritt, etwaige Proxy-Fehler.
   - **Run Repair** — führt `pip install --force-reinstall --no-deps 'PyQt6-WebEngine==MAJOR.MINOR.*' 'PyQt6-WebEngine-Qt6==MAJOR.MINOR.*'` aus, mit der Minor-Version passend zur laufenden PyQt6 (behebt die ABI-Inkompatibilität).
   - **Retry Import** — versucht den Import erneut, ohne Siril neu zu starten. Bei Erfolg verschwindet der Banner und der nächste Render nutzt die eingebettete Ansicht.
   - **Close** — Dialog ohne Änderungen schließen.
3. **PEP 668 / extern verwalteter Python-Interpreter** — wenn der laufende Interpreter als extern verwaltet gekennzeichnet ist (Debian-artige System-Pythons), ist **Run Repair** deaktiviert und der Grund wird erklärt. Die Lösung: Installieren Sie `PyQt6-WebEngine` selbst in Ihrer bevorzugten Methode (apt, venv, …) — das Skript weigert sich, einen system-verwalteten Interpreter zu beschädigen.

### In der Zwischenzeit können Sie trotzdem rendern

Wenn WebEngine nicht verfügbar ist, gelingen Renderings trotzdem — sie schreiben nur eine eigenständige HTML-Datei und öffnen sie im Standardbrowser (Sie bekommen also die volle Interaktivität, nur außerhalb des Siril-Fensters). PNG- und CSV-Export funktionieren normal.

---

## 13. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Galaxienfeld wirklich verstehen (3 Minuten)

**Szenario:** Sie haben das Leo-Triplett abgelichtet und möchten auf einen Blick sehen, wie weit M65, M66 und NGC 3628 wirklich entfernt sind im Vergleich zu den Vordergrundsternen.

1. Plate-gelöstes Bild in Siril laden, CosmicDepth 3D starten.
2. Standards beibehalten (Galaxien + Sterne + Haupttypen EIN, Log-Skala, Cosmic-Range, mag 12, 200 Objekte).
3. **Render 3D Map** klicken.
4. Die Ansicht so drehen, dass Sie seitlich auf die Bildebene blicken — die Galaxien liegen alle in ungefähr derselben gewaltigen Entfernung, Vordergrundsterne drängen sich nahe an der Ebene.

**Ergebnis:** Sie können visuell bestätigen, dass alle drei Galaxien bei ~30–35 MLj liegen, und sehen, dass die paar beschrifteten HD-Sterne weniger als ein Tausendstel dieser Entfernung haben.

### Anwendungsfall 2: Milchstraßen-Nebel mit Kontext

**Szenario:** Nahaufnahme von M42 (Orionnebel, 1 344 Lj) — Sie wollen eine 3D-Ansicht, die nur Milchstraßenstrukturen zeigt und schwache Hintergrundgalaxien ignoriert, die sonst die Log-Achse dominieren würden.

1. CosmicDepth 3D starten.
2. **Range = Galactic (< 100k ly)** setzen.
3. **Scale = Hybrid** setzen.
4. Dunkelnebel und HII-Regionen zusätzlich aktivieren.
5. Rendern.

**Ergebnis:** Alle Objekte innerhalb der Milchstraße, mit realistisch linearer Nähe für nahe Sterne und logarithmischer Kompression für Haufen-Entfernungen. Keine Galaxie in der Ferne, die die Achse verzerrt.

### Anwendungsfall 3: Galaxienhaufen — dichtes Feld

**Szenario:** Abell 2151 (Herkuleshaufen) mit 150+ Galaxien im Bild.

1. CosmicDepth 3D starten.
2. In Include Objects nur **Galaxies** ankreuzen — **Deselect All** drücken und dann nur Gal wieder aktivieren.
3. Magnitude-Grenze auf 16 anheben.
4. **Max objects** auf 500 anheben, damit der Haufen nicht abgeschnitten wird.
5. **Only objects with known distance** — EIN (Typ-Median-Fallbacks weglassen).
6. Rendern.

**Ergebnis:** Eine schöne 3D-Streuung eines echten Galaxienhaufens, die die charakteristische Radialgeschwindigkeitsstreuung in seiner Entfernung (~500 MLj) zeigt. Jeder Marker ist durch eine echte SIMBAD-Entfernung gestützt.

### Anwendungsfall 4: Eine interaktive Szene teilen

**Szenario:** Sie möchten die 3D-Ansicht in einem Forum posten oder einem Astrokumpel schicken.

1. Normal rendern.
2. Die Ansicht in einen gut lesbaren Winkel drehen.
3. **Export HTML** klicken. Die Datei ist eigenständig (~4 MB inklusive plotly.js).
4. In einen Filesharing-Dienst laden oder per E-Mail verschicken.

**Ergebnis:** Empfänger öffnet das HTML in jedem Browser und erhält die volle Interaktivität — kein Siril, kein Python, keine Installation nötig.

### Anwendungsfall 5: Publikationsreife Abbildung

1. Die Szene mit den gewünschten Filtern rendern.
2. In den endgültigen Winkel drehen, der in der Abbildung erscheinen soll.
3. **PNG DPI = 300** setzen.
4. **Export PNG** klicken.

**Ergebnis:** Ein statisches 4200 × 3000 Pixel PNG aus Ihrem exakten Blickwinkel, mit gestreckter Log-Achse und Lj-Beschriftung wie in der Live-Ansicht.

### Anwendungsfall 6: Objekttabellen-Audit

**Szenario:** Einer der Marker in der Szene wirkt falsch platziert.

1. Zum **Objects**-Tab wechseln.
2. Die Spalte **Source** anklicken, um nach Quelle zu sortieren.
3. Das Objekt finden — die Quelle ist `svenesis cache`, `SIMBAD mesDistance`, `SIMBAD redshift` oder `Type median`.
4. Bei `Type median` ist das ein Fallback — die echte Entfernung ist unbekannt. Entweder ausfiltern (**Only objects with known distance** aktivieren) oder als SIMBAD-Lücke melden.
5. Bei `SIMBAD mesDistance` und dennoch falsch: **Clear Distance Cache** klicken und neu rendern, um einen veralteten Cache-Eintrag auszuschließen.

---

## 14. Tastaturkürzel

| Taste | Aktion |
|-------|--------|
| `F5` | Render 3D Map |
| `Esc` | Fenster schließen |

Maus-Interaktionen in der eingebetteten 3D-Ansicht folgen Standard-Plotly-Konventionen (Ziehen, Scrollen, Doppelklick zum Zurücksetzen).

---

## 15. Tipps & Empfehlungen

1. **Mit Standards starten, dann anpassen.** Die Defaults (Haupttypen EIN, mag 12, 200 Objekte, Log + Cosmic, Himmelsebene EIN) liefern für die meisten plate-gelösten Bilder gute Ergebnisse. Einen Regler nach dem anderen ändern.
2. **Vor dem PNG-Export drehen.** Der Export nimmt Ihren aktuellen Blickwinkel auf. Zehn Sekunden für den passenden Winkel machen einen riesigen Unterschied für das finale Bild.
3. **Objects-Tab als Plausibilitätsprüfung nutzen.** Wenn ein Marker unplausibel platziert wirkt, Tabelle nach **Distance** sortieren und **Source** prüfen. Typ-Median-Fallbacks fallen sofort auf.
4. **Der Cache ist Ihr Freund.** Der erste Render eines Feldes ist langsam (SIMBAD-Abfragen), spätere sind nahezu sofort. Bei warmem Cache können Sie Skalierung und Filter frei durchprobieren.
5. **Galactic-Range + Hybrid-Skala für reine Milchstraßenfelder.** Sie bekommen realistische Abstände für nahe Strukturen und nichts „in der Unendlichkeit", das die Achse verzerrt.
6. **Stretched-Log-Parameter anpassen (fortgeschritten).** Die Form der Log-Achse wird durch zwei Konstanten oben im Skript gesteuert: `LOG_STRETCH_THRESHOLD_LY` (Standard `1e8`, der Lj-Wert, ab dem gestreckt wird) und `LOG_STRETCH_FACTOR` (Standard `3.0`, wie breit die Dekaden nach der Schwelle werden). Direkt im Skript anpassen — ohne UI-Änderung.
7. **Alle Einstellungen sind persistent.** Objekttypen, Filter, Skala/Range, DPI, Dateiname, Objects-Tabellen-Spaltenbreiten und Sortierreihenfolge — alles bleibt zwischen Sitzungen via QSettings erhalten.
8. **`Only objects with known distance` für Publikationen.** Niemand möchte eine Abbildung verteidigen, in der die Hälfte der Marker auf erfundenen Entfernungen sitzt.

---

## 16. Fehlerbehebung

### Fehler „Image is not plate-solved"

Das Bild zuerst über **Tools → Astrometry → Image Plate Solver…** in Siril plate-lösen und das Skript erneut starten.

### Keine Objekte im Feld gefunden

- Magnitude-Grenze erhöhen (14 oder 16 probieren).
- Weitere Objekttypen aktivieren — insbesondere **HII Regions** und **Dark Nebulae** für Milchstraßenfelder.
- Log-Tab prüfen — er zeigt die SIMBAD-Zahlen pro Tile. Nur Nullen bedeuten meist ein Netzwerkproblem.

### Banner „WebEngine import failed" im 3D-Map-Tab

Siehe Abschnitt 12. **Repair WebEngine…** öffnet den opt-in-Reparaturdialog. Bei PEP-668 / extern verwaltetem Python: `PyQt6-WebEngine` selbst passend zur PyQt6-Minor-Version installieren.

### 3D-Ansicht reagiert langsam bei riesigem Bild

Die Bildebene wird mit einem Raster proportional zur kürzeren Bildkante gesampelt (gedeckelt bei 400 × 400). Sehr große Mosaike erzeugen eine dichtere Ebene. Bei echter Trägheit vorübergehend **Show image as sky plane** ausschalten, um mit der abstrakten Punktwolke zu arbeiten.

### SIMBAD-Abfrage bricht mit Timeout ab

Internetverbindung prüfen. SIMBAD ist gelegentlich in Wartung — in 15 Minuten erneut versuchen. Der lokale Cache ist davon nicht betroffen.

### PNG-Export stimmt nicht mit der Live-Ansicht überein

- Sicherstellen, dass `kaleido` installiert ist: `pip install --upgrade kaleido`. Das Log meldet bei Erfolg „Exported PNG via Plotly/kaleido" bzw. bei Misserfolg „Plotly PNG export failed … falling back to matplotlib".
- Im matplotlib-Fallback stimmt das gespeicherte Bild nicht pixelgenau mit der eingebetteten Ansicht überein — es verwendet einen anderen Renderer. Kaleido-Installation löst das.

### Distanz für ein Objekt sieht falsch aus

Spalte **Source** im Objects-Tab prüfen:
- `Type median` = Fallback, echte Entfernung unbekannt.
- `SIMBAD redshift` = aus z per Hubble-Gesetz berechnet; Fehler von ~10–30 % sind bei verrauschten Rotverschiebungen normal.
- `SIMBAD mesDistance` = Direktmessung; falls dennoch falsch, **Clear Distance Cache** und neu rendern, um einen frischen Wert zu ziehen.

### Gestreckte Log-Achse wirkt trotzdem eng

Die beiden Konstanten oben im Skript anpassen:
```python
LOG_STRETCH_THRESHOLD_LY = 1.0e8   # ab hier wird gestreckt
LOG_STRETCH_FACTOR       = 3.0     # wie breit jede Dekade danach ist
```
Schwelle auf `1e7` senken, um früher zu strecken. Faktor auf `4` oder `5` erhöhen für noch mehr Platz im Fernbereich.

### Nach einem SIMBAD-Update ist alles an falschen Positionen

**Clear Distance Cache** klicken und neu rendern.

---

## 17. Häufige Fragen

**F: Verändert das Skript mein Bild?**
A: Nein. Es liest das Bild und den WCS-Header und schreibt Export-Dateien. Ihre FITS-Datei wird nicht verändert.

**F: Brauche ich Internet?**
A: Für den **ersten** Render eines Feldes ja — SIMBAD-Abfragen erfordern eine Verbindung. Spätere Renderings desselben Feldes nutzen den lokalen Entfernungs-Cache und funktionieren offline.

**F: Warum eine gestreckte Log-Skala statt einer reinen Log-Skala?**
A: Weil der interessante Galaxien-Fernbereich (> 100 Mio. Lj) unter einer reinen Log-Achse auf wenige Pixel zusammenschrumpft, obwohl dort die meisten Galaxien-Marker liegen. Die gestreckte Variante gibt diesem Bereich dreimal mehr Platz auf dem Bildschirm, ohne die nahe Struktur zu beeinträchtigen. Siehe Abschnitt 6.

**F: Kann ich exakte Entfernungen für jedes Objekt sehen?**
A: Ja — entweder den Marker im 3D-Fenster anhovern (Tooltip) oder in den **Objects**-Tab wechseln für die vollständige sortierbare Tabelle inklusive Unsicherheit und Quelle.

**F: Was, wenn SIMBAD keine Entfernung für ein Objekt hat?**
A: Die Prioritätskette weicht auf Rotverschiebung (falls vorhanden) und dann auf einen sinnvollen typbasierten Median aus. Typ-Median-Fallbacks sind klar gekennzeichnet (`Type median` in der Source-Spalte) und haben große Unsicherheiten. Um sie auszuschließen: **Only objects with known distance** aktivieren.

**F: Warum ist PyQt6-WebEngine ein separates Paket?**
A: Es ist eine große (~80 MB) native Bibliothek, die nicht jeder Nutzer braucht. Siril bündelt PyQt6 selbst, aber nicht WebEngine, daher prüft das Skript beim Start und bietet bei Bedarf eine opt-in-Installation an. Siehe Abschnitt 12.

**F: Kann ich eine rotierende Animation / GIF exportieren?**
A: Derzeit nicht. Der HTML-Export ist vollständig interaktiv, Sie können ihn nach dem Laden also selbst drehen; ein GIF-Export steht auf der To-do-Liste.

**F: Warum unterscheidet sich der PNG-Export manchmal von der eingebetteten Ansicht?**
A: Wenn `kaleido` nicht installiert ist, fällt der Export auf matplotlib zurück, das ein ähnliches, aber nicht pixelgleiches Bild rendert. Kaleido installieren (`pip install --upgrade kaleido`) für Pixelgleichheit.

**F: Kann ich eigene Entfernungsdaten statt SIMBAD verwenden?**
A: Derzeit nicht über die GUI. Fortgeschrittene Nutzer können die lokale Cache-JSON-Datei (`~/.config/svenesis/cosmic_depth_cache.json`) mit eigenen Entfernungen vorbefüllen — das Skript bevorzugt gecachte Werte gegenüber SIMBAD-Abfragen.

**F: Muss die Himmelsebene bei X = 0 sein?**
A: Ja, so designt. „Erde" sitzt bei X = 0 (bzw. genauer: die Bildebene ist dort auf der Log-Achse verankert, da log10(1) = 0). Jedes Objekt liegt dahinter. Das bewahrt die „Fenster-ins-Universum"-Metapher.

**F: Was ist der Unterschied zwischen Cosmic- und Galactic-Range?**
A: Cosmic enthält alles bis hin zu Quasaren in Milliarden Lj. Galactic schneidet hart bei 100 000 Lj (ungefährer Rand der Milchstraße). Galactic für reine Milchstraßenfelder; Cosmic für jedes Feld mit externen Galaxien.

---

## Credits

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die außerdem umfasst:
- Svenesis Annotate Image
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn Ihnen dieses Tool nützlich ist, unterstützen Sie die Entwicklung gerne über [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
