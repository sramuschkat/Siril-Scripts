# Svenesis Gradient Analyzer — Benutzeranleitung

**Version 1.8.4** | Siril Python-Skript zur Analyse und Diagnostik von Hintergrundgradienten

> *Ein umfassendes Diagnose-Werkzeug für Gradienten — analysiert, visualisiert und empfiehlt Korrekturen für Hintergrundgradienten, Vignettierung und Hardware-Artefakte in Astrofotografie-Bildern.*

---

## Inhaltsverzeichnis

1. [Was ist der Gradient Analyzer?](#1-was-ist-der-gradient-analyzer)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Die Messwerte verstehen](#6-die-messwerte-verstehen)
7. [Visualisierungs-Tabs](#7-visualisierungs-tabs)
8. [Rastereinstellungen & Vorlagen](#8-rastereinstellungen--vorlagen)
9. [Optionen & Kontrollkästchen](#9-optionen--kontrollkästchen)
10. [Ergebnisse & Empfehlungen](#10-ergebnisse--empfehlungen)
11. [Warnungen & Erkennungen](#11-warnungen--erkennungen)
12. [Exportoptionen](#12-exportoptionen)
13. [Anwendungsfälle & Arbeitsabläufe](#13-anwendungsfälle--arbeitsabläufe)
14. [Tastaturkürzel](#14-tastaturkürzel)
15. [Tipps & Empfehlungen](#15-tipps--empfehlungen)
16. [Fehlerbehebung](#16-fehlerbehebung)
17. [Häufige Fragen](#17-häufige-fragen)

---

## 1. Was ist der Gradient Analyzer?

Der **Svenesis Gradient Analyzer** ist ein Siril Python-Skript, das den Hintergrund Ihres Astrofotografie-Bildes analysiert, um Gradienten, Vignettierung und Hardware-Artefakte zu erkennen. Es sagt Ihnen, *was nicht stimmt*, *wie schlimm es ist* und *was genau zu tun ist*.

Stellen Sie es sich als einen **Diagnosearzt** für Ihren Bildhintergrund vor. Es kombiniert:

- **Visuelle Analyse** — Heatmaps, 3D-Oberflächen, Profildiagramme und 9 spezialisierte Visualisierungs-Tabs
- **Quantitative Messwerte** — Gradientenstärke, Richtung, Komplexität, Gleichmäßigkeit und über 30 diagnostische Messungen
- **Intelligente Empfehlungen** — spezifische Siril-Befehle und Werkzeugvorschläge, zugeschnitten auf die Probleme Ihres Bildes
- **Vorher/Nachher-Vergleich** — führen Sie die Analyse zweimal durch, um genau zu sehen, wie stark sich Ihre Gradientenextraktion verbessert hat

Das Ergebnis: Sie verstehen genau, welche Gradienten und Artefakte in Ihrem Bild vorhanden sind, und kennen die beste Strategie, um diese vor dem Stacken oder Stretchen zu entfernen.

---

## 2. Hintergrundwissen für Einsteiger

### Was ist ein Hintergrundgradient?

In einem perfekten Astrofoto wäre der Himmelshintergrund vollkommen gleichmäßig — überall die gleiche Helligkeit. In der Realität ist der Hintergrund fast nie gleichmäßig. Er variiert über das Bild hinweg aus verschiedenen Gründen:

| Ursache | Was passiert | Muster |
|---------|-------------|--------|
| **Lichtverschmutzung (LP)** | Künstliches Licht erhellt eine Seite des Himmels stärker als die andere | Gerichteter Gradient — eine Seite heller |
| **Vignettierung** | Ihre Optik verdunkelt die Bildecken im Vergleich zur Mitte | Radiales Muster — dunkle Ecken, helle Mitte |
| **Mond** | Mondlicht erzeugt ein Leuchten aus einer Richtung | Ähnlich wie LP — gerichtete Aufhellung |
| **Dämmerung / Morgengrauen** | Der Himmel wird vom Horizont her heller, wenn der Sonnenaufgang naht | Starker Gradient von einer Kante |
| **Airglow** | Natürliches atmosphärisches Leuchten variiert über den Himmel | Breiter, sanfter Gradient |
| **Sensorartefakte** | Verstärkerleuchten, Banding, Dunkelstrom | Eckenleuchten, horizontale/vertikale Streifen |
| **Schlechte Flat-Kalibrierung** | Das Flat-Frame korrigiert die optische Vignettierung nicht vollständig | Restliches radiales Muster |

Diese Gradienten **beeinträchtigen Ihr Endbild**. Wenn Sie das Bild stretchen, um schwache Details sichtbar zu machen, werden Gradienten verstärkt und erzeugen hässliche Helligkeitsschwankungen, Farbverschiebungen und Banding. Das Entfernen von Gradienten vor dem Stretchen ist einer der wichtigsten Verarbeitungsschritte.

### Was ist Vignettierung?

**Vignettierung** ist die Abdunklung der Bildecken, verursacht durch Ihr optisches System. Alle Teleskope und Kameraobjektive vignettieren bis zu einem gewissen Grad — Licht am Rand des Gesichtsfeldes muss durch mehr Glas hindurch und trifft den Sensor in einem steileren Winkel.

- **Natürliche Vignettierung** folgt einem mathematischen cos⁴-Gesetz — sie ist proportional zur vierten Potenz des Winkels von der Mitte
- **Mechanische Vignettierung** entsteht, wenn Teile Ihres Aufnahmezuges (Adapter, Filterräder, Reducer) am Rand physisch Licht blockieren
- **Flat-Frames** sind dafür konzipiert, Vignettierung zu korrigieren. Wenn Ihre Flats gut sind, sollte die Vignettierung weitgehend verschwunden sein, bevor Sie den Gradient Analyzer verwenden

Der Gradient Analyzer unterscheidet zwischen Vignettierung (radial, zentriert) und Lichtverschmutzung (gerichtet, einseitig), da sie unterschiedliche Werkzeuge zur Korrektur benötigen.

### Was ist Sigma-Clipping?

Wenn Sie die Hintergrundhelligkeit einer Kachel (eines kleinen Bildbereichs) messen, möchten Sie nur den *Himmel* messen — nicht die Sterne, Nebel oder kosmischen Strahlen in diesem Bereich.

**Sigma-Clipping** ist eine statistische Technik, die iterativ Ausreißer-Pixel entfernt:

1. Berechnung von Median und Standardabweichung aller Pixel in der Kachel
2. Entfernung aller Pixel, die um mehr als σ (Sigma) Standardabweichungen vom Median abweichen
3. Neuberechnung von Median und Standardabweichung aus den verbleibenden Pixeln
4. Wiederholung von Schritt 2–3

Nach dem Clipping repräsentieren die verbleibenden Pixel den reinen Himmelshintergrund — Sterne und helle Objekte wurden aus der Messung ausgeschlossen.

- **Niedriger Sigma-Wert (2,0–2,5):** Aggressiveres Clipping — entfernt mehr Pixel, besser beim Ausschließen von Sternen, kann aber in dichten Feldern den Himmel selbst beschneiden
- **Höherer Sigma-Wert (3,0–3,5):** Sanfteres Clipping — behält mehr Pixel bei, robuster in dichten Sternfeldern, kann aber schwache Sternhalos einschließen

### Was ist eine Polynomanpassung?

Um einen Gradienten zu entfernen, passt die Software eine mathematische Oberfläche an Ihren Hintergrund an und subtrahiert sie. Die Komplexität dieser Oberfläche wird durch den **Polynomgrad** gesteuert:

| Grad | Oberflächenform | Am besten geeignet für |
|------|----------------|----------------------|
| **1 (Linear)** | Eine flache, geneigte Ebene | Einfache eingerichtete Gradienten (LP von einer Seite) |
| **2 (Quadratisch)** | Eine gekrümmte Schüssel oder Sattelform | Vignettierung + LP kombiniert, sanfte Kurven |
| **3 (Kubisch)** | Eine S-förmige oder komplexe Kurve | Komplexe Gradienten mit mehreren Quellen |

Der Gradient Analyzer schätzt, welchen Grad Ihr Bild benötigt, und empfiehlt spezifische `subsky`-Parameter.

### Welche Werkzeuge entfernen Gradienten?

Es gibt mehrere Werkzeuge zum Entfernen von Hintergrundgradienten in der Astrofotografie:

| Werkzeug | Typ | Am besten geeignet für |
|----------|-----|----------------------|
| **AutoBGE** | Siril integriert | Schnelle, automatische Extraktion — gut für milde Gradienten |
| **subsky** | Siril-Befehl | Konfigurierbare Polynom-Extraktion — Sie wählen Grad und Abtastanzahl |
| **GraXpert** | Extern (KI-basiert) | Komplexe Gradienten aus mehreren Quellen — nutzt KI zur Modellierung beliebiger Hintergründe |
| **VeraLux Nox** | Siril-Skript | Chromatische Lichtverschmutzung — unterschiedlicher Gradient pro Farbkanal |

Der Gradient Analyzer empfiehlt das richtige Werkzeug basierend auf der Komplexität Ihres Gradienten.

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweise |
|------------|---------------|----------|
| **Siril** | 1.4.0+ | Python-Skript-Unterstützung muss aktiviert sein |
| **sirilpy** | Mitgeliefert | Wird mit Siril 1.4+ ausgeliefert |
| **numpy** | Beliebig aktuell | Wird vom Skript automatisch installiert |
| **PyQt6** | 6.x | Wird vom Skript automatisch installiert |
| **matplotlib** | 3.x | Wird vom Skript automatisch installiert |
| **scipy** | Beliebig aktuell | Wird vom Skript automatisch installiert |
| **astropy** | Beliebig | *Optional* — wird für FITS-Header-Analyse verwendet (Kalibrierungsprüfung, WCS) |

### Installation

1. Laden Sie `Svenesis-GradientAnalyzer.py` aus dem [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Platzieren Sie die Datei in Ihrem Siril-Skriptverzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Verarbeitung → Skripte**.

Das Skript installiert beim ersten Start automatisch fehlende Python-Abhängigkeiten (`numpy`, `PyQt6`, `matplotlib`, `scipy`).

---

## 4. Erste Schritte

### Schritt 1: Ein Bild laden

Laden Sie ein beliebiges FITS-Bild in Siril. Der Gradient Analyzer funktioniert mit:
- **Einzelnen gestackten Bildern** (der häufigste Anwendungsfall — vor dem Stretchen analysieren)
- **Einzelnen Subframes** (um Gradienten pro Frame zu überprüfen)
- **RGB- oder Mono**-Bildern

**Wichtig:** Für beste Ergebnisse analysieren Sie Ihr Bild **vor dem Stretchen**. Das Skript erkennt gestretchte (nichtlineare) Bilder und warnt Sie, da Gradientenmessungen an gestretchten Daten weniger genau sind.

### Schritt 2: Das Skript starten

Gehen Sie zu **Verarbeitung → Skripte → Svenesis Gradient Analyzer**.

Das Skript öffnet sein Fenster. Das linke Panel zeigt alle Einstellungen; das rechte Panel ist für Visualisierungen bereit.

### Schritt 3: Auf „Analyze" klicken (oder F5 drücken)

Das Skript wird:
1. Das aktuelle Bild aus Siril laden
2. Es in ein Raster aus Kacheln unterteilen (Standard: 16×16)
3. Jede Kachel per Sigma-Clipping von Sternen bereinigen
4. Hintergrund-Mediane für jede Kachel berechnen
5. Über 30 diagnostische Analysen durchführen
6. Alle 9 Visualisierungs-Tabs rendern
7. Ergebnisse mit Messwerten, Warnungen und Empfehlungen anzeigen

Ein Fortschrittsbalken zeigt jeden Schritt. Die gesamte Analyse dauert typischerweise 5–30 Sekunden, abhängig von Bildgröße und Rasterauflösung.

### Schritt 4: Die Ergebnisse lesen

Nach der Analyse zeigen Ihnen drei Dinge, was zu tun ist:

1. **Die Gradientenstärke-Anzeige** — ein visuelles Messgerät, das die Schwere des Gradienten anzeigt (grün = in Ordnung, rot = muss behoben werden)
2. **Der „Analysis Results"-Button** — öffnet einen detaillierten Bericht mit einem einsteigerfreundlichen Aktionsplan
3. **Der „Recommendations"-Button** — zeigt spezifische Werkzeugvorschläge und Siril-Befehle

### Schritt 5: Korrigieren und erneut analysieren

1. Wenden Sie die empfohlene Gradientenextraktion an (z.B. führen Sie `subsky 2 16` in Sirils Konsole aus)
2. Drücken Sie **F5**, um dasselbe Bild erneut zu analysieren
3. Das Skript zeigt einen **Vorher/Nachher-Vergleich** — die Anzeige, Messwerte und Delta-Werte sagen Ihnen genau, wie viel sich verbessert hat

---

## 5. Die Benutzeroberfläche

### Linkes Panel (Steuerungsbereich)

Die linke Seite (340px breit) enthält alle Steuerelemente in einem scrollbaren Panel:

#### Titel
„Svenesis Gradient Analyzer 1.8.4" oben.

#### Rastereinstellungs-Gruppe
- **Spalten / Zeilen:** SpinBox + Schieberegler (je 4–64). Steuert, in wie viele Kacheln das Bild unterteilt wird. Standard: 16×16.
- **Sigma-Clip:** SpinBox (1,5–4,0, Schrittweite 0,1). Steuert, wie aggressiv Sterne ausgeschlossen werden. Standard: 2,5.
- **Sigma-Hinweis:** Dynamischer gelber Text mit empfohlenen Sigma-Anpassungen basierend auf Ihren Daten.
- **Vorlagen-Dropdown:** Schnellvorlagen für verschiedene Bildtypen — Broadband (Standard), Narrowband (streng), Fast optics (tolerant).

#### Optionsgruppe
Acht Kontrollkästchen zur Steuerung des Analyseverhaltens und der Ausgabe:
- Glättung (bilineare Interpolation)
- 3D-Ansicht
- Kanäle separat analysieren (RGB)
- Abtastpunkt-Hilfsanzeige
- Bild unter Heatmap anzeigen
- Heatmap als PNG speichern
- Analyse-JSON speichern
- Farbenblindfreundliche Farbskala

#### Aktionsgruppe
- **Analyze**-Button (grün, groß) — die Hauptaktion. Auch ausgelöst durch **F5**.
- **Fortschrittsbalken** — wird während der Analyse angezeigt.

#### Gradientenstärke-Anzeige
Ein visuelles Messgerät-Widget, das den Gradientenstärke-Prozentsatz mit farbcodierten Zonen anzeigt:
- **Grün (0–1,5%):** Sehr gleichmäßig — keine Extraktion nötig
- **Gelb (1,5–4%):** Leichter Gradient — sanfte Extraktion empfohlen
- **Orange (4–12%):** Deutlicher Gradient — Extraktion dringend empfohlen
- **Rot (>12%):** Starker Gradient — aggressive Extraktion erforderlich

#### Quadranten-Widget
Ein 2×2-Raster, das die Median-Hintergrundwerte für NW, NO, SW, SO anzeigt. Der hellste Quadrant erhält einen roten Rand (Richtung der Lichtverschmutzung); der dunkelste einen grünen Rand. Beim Überfahren mit der Maus erscheint ein Tooltip, der erklärt, was die Quadrantenwerte bedeuten.

#### Untere Buttons
- **Buy me a Coffee** — Unterstützungslink
- **Help** — umfassender Hilfe-Dialog mit 6 Tabs
- **Close** — beendet das Skript

### Rechtes Panel (Visualisierungen)

#### Bildinformationsleiste
Zeigt Bildabmessungen, Kanalanzahl und Status (z.B. „Image: 4656 × 3520 px, 3 channel(s)").

#### Tab-Widget (9 Tabs)
Das Herzstück des Werkzeugs — 9 spezialisierte Visualisierungs-Tabs (siehe Abschnitt 7 für Details).

#### Tab-Informationstext
Unterhalb der Tabs wird eine kontextsensitive Beschreibung aktualisiert, wenn Sie die Tabs wechseln, und erklärt in verständlicher Sprache, was Sie gerade betrachten.

#### Untere Buttons
- **Analysis Results** — öffnet ein Dialogfenster mit den Tabs Zusammenfassung, Messwerte und Vorher/Nachher
- **Recommendations** — öffnet ein Dialogfenster mit den Tabs Kurzanleitung und Vollständige Details
- **Export Report** — speichert einen konsolidierten Textbericht und kopiert ihn in die Zwischenablage

---

## 6. Die Messwerte verstehen

### Gradientenstärke (%)

Der primäre Messwert. Misst, wie stark der Hintergrund über das Bild variiert.

| Aspekt | Details |
|--------|---------|
| **Was** | (P95 − P5) ÷ Median × 100, wobei P95/P5 das 95. und 5. Perzentil der Kachel-Mediane sind |
| **Warum P95-P5?** | Robuster als Max-Min — ignoriert Ausreißer-Kacheln, die durch Artefakte verursacht werden |
| **Gute Werte** | Unter 1,5% (Broadband) |
| **Schlechte Werte** | Über 12% — starker Gradient, der das Stretchen ruiniert |

**Interpretation nach Vorlage:**

| Vorlage | Gleichmäßig | Leicht | Deutlich | Stark |
|---------|------------|--------|----------|-------|
| Broadband | < 1,5% | 1,5–4% | 4–12% | > 12% |
| Narrowband | < 0,8% | 0,8–2,5% | 2,5–6% | > 6% |
| Fast optics | < 3% | 3–6% | 6–16% | > 16% |

### Gradientenrichtung (°)

Der Kompasswinkel von der dunkelsten Region zur hellsten, gemessen in Grad (0° = Norden, 90° = Osten). Zeigt an, woher die Lichtverschmutzung oder der Mond kommt.

Wenn das Bild plattengelöst ist (WCS im FITS-Header), konvertiert das Skript dies in eine reale **geografische Kompasspeilung** — so können Sie prüfen, ob sie mit der Position Ihrer Stadtbeleuchtung übereinstimmt.

### Gleichmäßigkeit (%)

Standardabweichung ÷ Median × 100. Ein empfindlicheres Maß für die Gesamtvariation des Hintergrunds. Niedrigere Werte sind besser.

### Vignettierung vs. Lichtverschmutzung

Das Skript passt zwei Modelle an Ihr Gradientenmuster an:

| Modell | Was es erkennt | Bedeutung von R² |
|--------|---------------|-----------------|
| **Radial (Vignettierung)** | Symmetrische Eckabdunklung, zentriert auf das Bild | Höheres R² = Vignettierung dominiert |
| **Linear (LP)** | Gerichtete Helligkeitsänderung über das Bild | Höheres R² = Lichtverschmutzung dominiert |

Wenn radiales R² deutlich höher ist → der Gradient ist Vignettierung. Wenn lineares R² deutlich höher ist → es ist Lichtverschmutzung. Wenn beide ähnlich sind → es ist eine Mischung.

### Kanten/Mitte-Verhältnis

Vergleicht die durchschnittliche Kantenhelligkeit mit der Mittenhelligkeit. Werte unter 0,85 deuten auf deutliche Vignettierung hin (Kanten sind viel dunkler als die Mitte). Werte nahe 1,0 bedeuten keine Vignettierung.

### Gradientenkomplexität (Polynomgrad)

Das Skript passt Polynomoberflächen der Grade 1, 2 und 3 an und zeigt Ihnen, welche am besten zu Ihrem Gradienten passt:

| Grad | Bedeutung | Typische Ursache |
|------|-----------|-----------------|
| **1 (Linear)** | Einfache Neigung | LP aus einer Richtung |
| **2 (Quadratisch)** | Gekrümmt, schüsselförmig | Vignettierung + LP kombiniert |
| **3 (Kubisch)** | Komplexe S-Kurve | Mehrere LP-Quellen, optische Effekte |

Wenn keine der Polynomanpassungen gut ist (alle R² < 0,5), empfiehlt das Skript **GraXpert** (KI-basierte Extraktion), da der Gradient zu komplex für traditionelle Polynomanpassung ist.

### Konfidenz

Ein SNR-basierter Wert, der die Zuverlässigkeit der Gradientenmessung misst:

| Stufe | Wert | Bedeutung |
|-------|------|-----------|
| **Niedrig** | < 30% | Das Gradientensignal liegt kaum über dem Kachelrauschen — Ergebnisse sind unsicher |
| **Mittel** | 30–70% | Moderate Konfidenz — Gradient ist real, aber die Messung hat eine gewisse Unsicherheit |
| **Hoch** | > 70% | Hohe Konfidenz — der Gradient ist gut gemessen und eindeutig vorhanden |

### Quadrantenanalyse

Teilt das Bild in vier Quadranten (NW, NO, SW, SO) und berichtet den Median-Hintergrund jedes Quadranten. Der **hellste Quadrant** zeigt die Richtung der Lichtverschmutzung an; der **dunkelste Quadrant** ist der sauberste Teil des Himmels.

---

## 7. Visualisierungs-Tabs

### Tab 1: Heatmap / 3D

Die primäre Visualisierung. Eine farbcodierte Karte der Hintergrundhelligkeit über das Bild.

- **Grüne/blaue Kacheln** = dunklerer Hintergrund (gut)
- **Gelbe/rote Kacheln** = hellerer Hintergrund (Gradient oder LP)
- **Cyanfarbener Pfeil** = Gradientenrichtung (vom dunkelsten zum hellsten Bereich)
- **Grüne Kreise** = vorgeschlagene Abtastpunkte für `subsky` (dunkelste, gleichmäßigste Bereiche)
- **Rotes ✕** = zu vermeidende Bereiche bei der Platzierung von Abtastpunkten (hell, gradientenbetroffen)

Wenn die **3D-Ansicht** aktiviert ist, erscheint neben der Heatmap ein drehbares 3D-Oberflächendiagramm. Die „Höhe" repräsentiert die Hintergrundhelligkeit — Gipfel sind die hellsten Bereiche, Täler die dunkelsten.

### Tab 2: Profile

Zwei Liniendiagramme, die Querschnitte des Hintergrunds zeigen:

- **Horizontales Profil (links → rechts):** Der Median-Hintergrund jeder Kachelspalte. Zeigt Links-Rechts-Gradienten.
- **Vertikales Profil (unten → oben):** Der Median-Hintergrund jeder Kachelzeile. Zeigt Oben-Unten-Gradienten.

Gestrichelte Linien zeigen das Gesamtminimum und -maximum. Eine perfekt flache Linie bedeutet keinen Gradienten in dieser Richtung.

### Tab 3: Kachelverteilung

Ein Histogramm aller Kachel-Medianwerte. Zeigt, wie die Hintergrundwerte verteilt sind.

- **Schmales Histogramm mit einem Gipfel** = gleichmäßiger Hintergrund (gut)
- **Breites oder mehrgipfliges Histogramm** = Gradient oder Artefakte vorhanden
- **Orange gestrichelte Linie** = Median aller Kacheln
- **Blau gepunktete Linie** = Mittelwert aller Kacheln

### Tab 4: RGB-Kanäle

Drei nebeneinander liegende Heatmaps, die den Gradienten separat für jeden R-, G-, B-Kanal zeigen. Nur verfügbar, wenn „Kanäle separat analysieren" aktiviert ist.

Dies zeigt **chromatische Lichtverschmutzung** — wenn der Gradient in einem Farbkanal stärker ist. Typische Muster:
- **Rot dominant:** Natriumdampflampen (ältere Straßenbeleuchtung)
- **Blau dominant:** LED- oder Quecksilberdampfleuchten
- **Gleichmäßig über alle Kanäle:** Breitband-LP, Mondlicht oder Vignettierung

### Tab 5: Hintergrundmodell

Zeigt die an Ihren Gradienten angepasste Polynomoberfläche:

- **Links:** Das angepasste Modell — was das Gradientenextraktionswerkzeug subtrahieren würde
- **Rechts:** Residuen (Original − Modell) — was nach der Subtraktion übrig bleiben würde

Bei den Residuen bedeutet **zufällige Färbung** eine gute Anpassung (das Modell hat den Gradienten erfasst). **Sichtbare Muster** bedeuten, dass der Polynomgrad zu niedrig ist oder der Gradient zu komplex ist.

### Tab 6: Gradientenmagnitude

Eine Karte, die die **Änderungsrate** des Hintergrunds zeigt — wo der Gradient am steilsten ist.

- **Kühle Farben (blau/schwarz)** = flache Bereiche (kein Gradient)
- **Heiße Farben (gelb/rot)** = steile Übergänge (starker Gradient oder Kante)

Scharfe Linien in dieser Karte können auf **Mosaik-Panelgrenzen** (zusammengesetzte Bilder) oder **Stacking-Ränder** (vom Dithering) hinweisen.

### Tab 7: Subtraktionsvorschau

Nebeneinander-Vergleich:

- **Links:** Ihr Originalbild (automatisch gestretchte Luminanz)
- **Rechts:** Das Bild nach Subtraktion des angepassten Polynommodells (automatisch gestretcht)

Dies ist eine Vorschau dessen, was die Gradientenextraktion bewirken würde. Die rechte Seite sollte einen gleichmäßigeren Hintergrund zeigen.

### Tab 8: FWHM / Exzentrizität

Variation der Sternform über das Gesichtsfeld:

- **Links (FWHM-Karte):** Wie „breit" die Sterne in jeder Kachel sind. Gleichmäßige FWHM = gute Optik/Fokussierung. Zunehmende FWHM zu den Rändern = Feldkrümmung oder Verkippung.
- **Rechts (Exzentrizitätskarte):** Wie elongiert die Sterne in jeder Kachel sind. Niedrige Exzentrizität überall = gute Nachführung und Optik. Hohe Exzentrizität in den Ecken = optische Verkippung oder Koma.

Leere Kacheln (NaN) bedeuten, dass zu wenige Sterne in diesem Bereich gefunden wurden (z.B. nebeldominierte Bereiche).

### Tab 9: Residuen / Maske

Zeigt die Qualität der Polynomanpassung:

- **Links:** Residuen des Hintergrundmodells (blau = Modell zu hoch, rot = Modell zu niedrig)
- **Rechts:** Gleiche Residuen mit einer **roten Überlagerung**, die hervorhebt, welche Kacheln von der Anpassung ausgeschlossen wurden

Ausgeschlossene Kacheln sind solche, die als: ausgedehnte Objekte (Nebel/Galaxien), Hotspots, Stacking-Ränder oder extrem sterndichte Regionen markiert wurden. Das Ausschließen dieser Kacheln stellt sicher, dass die Polynomanpassung den wahren Himmelshintergrund verfolgt.

---

## 8. Rastereinstellungen & Vorlagen

### Rasterauflösung (Spalten × Zeilen)

Steuert, in wie viele Kacheln das Bild unterteilt wird. Standard: 16×16 (256 Kacheln).

| Auflösung | Kacheln | Am besten geeignet für |
|-----------|---------|----------------------|
| **8×8** | 64 | Schneller Überblick, sehr große Bilder |
| **16×16** | 256 | Guter Standard für die meisten Bilder |
| **24×24** | 576 | Detaillierte Analyse, Erkennung lokalisierter Merkmale |
| **32×32** | 1024 | Hochauflösende Gradientenkartierung |
| **48×48+** | 2304+ | Für Experten — sehr langsam, sehr detailliert |

**Warnung:** Das Skript warnt Sie, wenn Ihr Raster für die Bildgröße zu fein ist. Jede Kachel benötigt mindestens 50 Pixel pro Seite für zuverlässiges Sigma-Clipping. Wenn Sie 64×64 bei einem 2000 Pixel breiten Bild einstellen, wäre jede Kachel nur 31 Pixel breit — zu klein.

### Sigma-Clip-Wert

Steuert, wie aggressiv Sterne aus den Hintergrundmessungen entfernt werden. Standard: 2,5.

| Wert | Verhalten | Am besten geeignet für |
|------|-----------|----------------------|
| **1,5–2,0** | Sehr aggressiv — beschneidet auch schwache Sternhalos | Spärliche Sternfelder mit wenigen hellen Sternen |
| **2,5** | Ausgewogener Standard — funktioniert gut für die meisten Bilder | Allgemeine Verwendung |
| **3,0–3,5** | Sanft — behält mehr Pixel bei | Dichte Sternfelder (Milchstraße, Kugelsternhaufen) |
| **4,0** | Sehr sanft — minimales Clipping | Sehr dichte Felder oder wenn 2,5 zu viel beschneidet |

Das Skript bietet einen **adaptiven Sigma-Vorschlag** in gelbem Text unterhalb der Einstellung, basierend auf der Sterndichte (Ablehnungsrate) in Ihrem Bild.

### Schwellenwert-Vorlagen

Das Dropdown wählt Schwellenwert-Kalibrierungen für verschiedene Bildtypen:

| Vorlage | Schwellenwerte | Warum |
|---------|---------------|-------|
| **Broadband (Standard)** | 1,5% / 4% / 12% | Standard für Breitband-RGB-Aufnahmen. Typische Gradienten durch LP und Vignettierung. |
| **Narrowband (streng)** | 0,8% / 2,5% / 6% | Schmalbandfilter unterdrücken bereits die meiste LP, daher ist jeder verbleibende Gradient bedenklicher. Strengere Schwellenwerte. |
| **Fast optics (tolerant)** | 3% / 6% / 16% | Schnelle Optiken (f/2–f/4) vignettieren naturgemäß stärker. Lockerere Schwellenwerte vermeiden Fehlalarme durch natürlichen cos⁴-Abfall. |

---

## 9. Optionen & Kontrollkästchen

### Glättung (Standard: EIN)

Wendet bilineare Interpolation auf die Heatmap an, für eine glatte, kontinuierliche Visualisierung statt blockiger Kacheln. Rein kosmetisch — beeinflusst die Messwerte nicht. Deaktivieren für eine rohe, kachelgenaue Ansicht.

### 3D-Ansicht (Standard: EIN)

Fügt ein drehbares 3D-Oberflächendiagramm neben der Heatmap hinzu. Zeigt den Gradienten als „Landschaft", die Sie durch Ziehen drehen können. Deaktivieren, um Bildschirmplatz zu sparen oder das Rendering zu beschleunigen.

### Kanäle separat analysieren (Standard: AUS)

Wenn aktiviert, wird die vollständige Analyse unabhängig auf jedem R-, G-, B-Kanal durchgeführt und der RGB-Kanäle-Tab befüllt. Zeigt chromatische Lichtverschmutzung und Gradientenunterschiede pro Kanal auf.

Wird bei Mono-Bildern automatisch deaktiviert.

**Wann aktivieren:** Wenn Sie vermuten, dass Ihre Lichtverschmutzung einen Farbstich hat, oder wenn Sie VeraLux Nox verwenden und Gradientendaten pro Kanal benötigen.

### Abtastpunkt-Hilfsanzeige (Standard: EIN)

Blendet grüne Kreise (gute Abtastpositionen) und rote Kreuze (zu vermeidende Positionen) auf der Heatmap ein. Die Abtastpunkte werden in den dunkelsten, gleichmäßigsten Bereichen platziert — genau dort, wo Sie subsky-Abtastpunkte setzen möchten.

### Bild unter Heatmap anzeigen (Standard: AUS)

Zeigt Ihr tatsächliches Bild (automatisch gestretcht) unter der Heatmap als halbtransparente Überlagerung an. Hilft, Gradientenmerkmale mit dem tatsächlichen Bildinhalt zu korrelieren (z.B. „dieser helle Fleck ist tatsächlich ein Nebel, kein Gradient").

### Heatmap als PNG speichern (Standard: AUS)

Wenn aktiviert, wird die Heatmap-Visualisierung nach jeder Analyse automatisch als PNG-Datei im Siril-Arbeitsverzeichnis gespeichert. Nützlich für Dokumentation oder Forenbeiträge.

Kann eine **annotierte** Version mit eingebrannten Schlüsselmetriken am unteren Bildrand speichern.

### Analyse-JSON speichern (Standard: AUS)

Wenn aktiviert, werden alle Messwerte und Kachel-Mediane als JSON-Begleitdatei (`gradient_analysis.json`) gespeichert. Verwendet für:
- **Sitzungsübergreifender Vergleich:** Wenn eine vorherige JSON-Datei existiert, berechnet das Skript Deltas (wie stark sich der Gradient seit der letzten Analyse geändert hat)
- **Dokumentation:** Maschinenlesbare Aufzeichnung Ihrer Gradientendiagnostik

### Farbenblindfreundliche Farbskala (Standard: AUS)

Wechselt von der Standard-Rot-Grün-Farbskala zu **cividis**, die wahrnehmungsmäßig gleichmäßig und für Menschen mit Farbsehschwächen zugänglich ist.

---

## 10. Ergebnisse & Empfehlungen

### Analysis Results (Button)

Öffnet ein Dialogfenster mit drei Tabs:

#### Tab Zusammenfassung
Ein einsteigerfreundlicher **Aktionsplan** in verständlicher Sprache:
- Was die Gradientenstärke bedeutet
- Ob Kalibrierungsprobleme erkannt wurden (fehlende Flats, Verstärkerleuchten, Banding)
- Ob die Daten linear oder gestretcht sind
- Spezifische Schritte, die zu unternehmen sind, in Prioritätsreihenfolge
- Konkrete Siril-Befehle (z.B. `subsky 2 16`)

#### Tab Messwerte
Detaillierte Zahlen für fortgeschrittene Benutzer:
- Gradientenstärke, Richtung, Bereich, Gleichmäßigkeit
- Vignettierung vs. LP-Analyse (R²-Werte)
- Polynomkomplexität (Grad, R² pro Grad)
- Kanten/Mitte-Verhältnis
- Konfidenzwert und SNR
- Sterndichtestatistiken
- Prozentsatz der gradientenfreien Abdeckung
- Anzahl ausgedehnter Objekte
- Anzahl der Hotspots
- Alle Warnungen und Erkennungen

#### Tab Vorher/Nachher
Wenn Sie die Analyse mehr als einmal auf demselben Bild durchgeführt haben (z.B. vor und nach der Gradientenextraktion), zeigt dieser Tab:
- Vorherige vs. aktuelle Gradientenstärke
- Delta mit Pfeil (↓ = verbessert, ↑ = verschlechtert)
- Prozentuale Verbesserung

### Recommendations (Button)

Öffnet ein Dialogfenster mit zwei Tabs:

#### Tab Kurzanleitung
Eine knappe Zusammenfassung:
- Kritische Warnungen (falls vorhanden)
- Empfohlenes Werkzeug mit kurzer Erklärung
- Spezifischer auszuführender Befehl
- Workflow-Priorität (Hardware-/Kalibrierungsprobleme zuerst beheben, dann extrahieren)

#### Tab Vollständige Details
Umfassende Empfehlungen:
- Werkzeugvergleich für Ihre spezifische Situation (AutoBGE vs. subsky vs. GraXpert vs. VeraLux Nox)
- Warum jedes Werkzeug geeignet oder ungeeignet ist
- Schritt-für-Schritt-Workflow mit geordneten Prioritäten
- Erinnerung zur erneuten Analyse

---

## 11. Warnungen & Erkennungen

Der Gradient Analyzer erkennt viele Probleme über einfache Gradienten hinaus. Jede Warnung erscheint in den Ergebnissen mit einer Erklärung und Lösung.

### Tau / Frost erkannt

**Was es bedeutet:** Das Skript hat eine Kombination aus radialem FWHM-Anstieg (Sterne werden von der Mitte zum Rand hin breiter) und einem Helligkeitsmuster mit heller Mitte gefunden. Dies deutet darauf hin, dass sich während der Aufnahmesitzung Feuchtigkeit auf Ihrer Optik gebildet hat.

**Wie beheben:** Überprüfen Sie Ihre Tauheizung. Verwerfen Sie betroffene Aufnahmen. Erwägen Sie eine Taukappe oder aggressivere Heizung.

### Verstärkerleuchten erkannt

**Was es bedeutet:** Eine Ecke des Sensors zeigt exponentiell zunehmende Helligkeit — das „Verstärkerleuchten" der Kameraelektronik, die Wärme erzeugt, die der Sensor aufnimmt.

**Wie beheben:** Wenden Sie korrekte Dark-Frames an. Dark-Frames, die bei gleicher Temperatur und Belichtungszeit aufgenommen wurden, enthalten das gleiche Verstärkerleuchten-Muster und subtrahieren es.

### Sensor-Banding erkannt

**Was es bedeutet:** Die FFT-Analyse der Residual-Zeilen/Spalten-Profile hat periodische Muster gefunden — horizontale oder vertikale Streifen von der Sensorausleseelektronik.

**Wie beheben:** Wenden Sie Bias- und Dark-Frames an. Wenn das Banding bestehen bleibt, versuchen Sie erneutes Stacken mit anderen Rejection-Methoden. Einige Kameras sind bekannt für Banding (bestimmte CMOS-Sensoren).

### Warnung: Fehlendes Flat-Frame

**Was es bedeutet:** Der FITS-Header zeigt nicht an, dass ein Flat-Frame angewendet wurde (kein `FLATCOR`- oder `CALSTAT`-Schlüsselwort). Erhebliche Vignettierung ist wahrscheinlich.

**Wie beheben:** Wenden Sie ein Master-Flat-Frame an. In Siril: **Bildverarbeitung → Kalibrierung** oder verwenden Sie den Befehl `calibrate -flat=master_flat.fit`.

### Nichtlineare (gestretchte) Daten

**Was es bedeutet:** Das Bild scheint gestretcht worden zu sein (Histogrammtransformation angewendet). Gradientenmessungen an gestretchten Daten sind verstärkt und weniger genau.

**Wie beheben:** Analysieren Sie stattdessen das ursprüngliche, ungestretchte (lineare) Bild. Wenn Sie bereits gestretcht haben, ist die Analyse immer noch nützlich, aber die Prozentwerte können überhöht sein.

### Hintergrundnormalisierung erkannt

**Was es bedeutet:** Die Hintergründe der einzelnen Kanäle sind verdächtig ähnlich, was darauf hindeutet, dass die Daten während des Stackens hintergrundnormalisiert wurden. Dies kann echte Gradienten maskieren.

**Wie beheben:** Wenn möglich, stacken Sie ohne Hintergrundnormalisierung neu, analysieren Sie, extrahieren Sie Gradienten, und stacken Sie dann normal.

### Warnung: Dichtes Sternfeld

**Was es bedeutet:** Viele Kacheln haben sehr hohe Sigma-Clip-Ablehnungsraten (>40%), was bedeutet, dass das Feld so dicht mit Sternen gepackt ist, dass die Hintergrundmessung beeinträchtigt sein könnte.

**Wie beheben:** Erhöhen Sie den Sigma-Clip-Wert (z.B. von 2,5 auf 3,0 oder 3,5), um weniger aggressiv zu sein, oder reduzieren Sie die Rasterauflösung für größere Kacheln.

### Stacking-Ränder erkannt

**Was es bedeutet:** Randkacheln sind deutlich dunkler als innere Kacheln — ein verräterisches Zeichen von geditherten oder rotierten Stackings, bei denen Randbereiche weniger beitragende Frames haben.

**Wie beheben:** Beschneiden Sie die Ränder. Verwenden Sie in Siril das Auswahlwerkzeug, um einen Beschneidungsbereich zu definieren, oder fügen Sie Ihrem Workflow einen Beschneidungsschritt hinzu.

### Hotspots erkannt

**Was es bedeutet:** Einzelne Kacheln weichen um mehr als 3σ von ihren Nachbarn ab — wahrscheinlich Artefakte wie Satellitenspuren, kosmische Strahlen oder Sensordefekte.

**Wie beheben:** Untersuchen Sie die spezifischen Stellen. Diese Kacheln werden automatisch von der Polynom-Hintergrundanpassung ausgeschlossen, um zu verhindern, dass sie das Modell verzerren.

### Vignettierungs-Asymmetrie

**Was es bedeutet:** Das Vignettierungsmuster ist nicht symmetrisch (z.B. ist die linke Seite dunkler als die rechte). Dies deutet darauf hin, dass die Flat-Frames nicht perfekt zur Aufnahmeoptik passen oder der Sensor verkippt ist.

**Wie beheben:** Überprüfen Sie die Qualität Ihrer Flat-Frames. Stellen Sie sicher, dass Flats mit der gleichen optischen Zugkonfiguration aufgenommen werden. Erwägen Sie, die Sensorverkippung zu überprüfen.

### Warnung: Ausgedehntes Objekt

**Was es bedeutet:** Einige Kacheln enthalten helle Objekte (Nebel, Galaxien) mit geringer Sternablehnungsrate — dies sind echte Objekte, keine Gradienten. Sie werden automatisch von der Polynomanpassung ausgeschlossen.

**Keine Korrektur nötig** — dies ist informativ. Ihr Zielobjekt wird korrekt identifiziert und vom Hintergrundmodell ausgeschlossen.

---

## 12. Exportoptionen

### Heatmap-PNG-Export

Wenn „Heatmap als PNG speichern" aktiviert ist, wird die Heatmap nach jeder Analyse im Siril-Arbeitsverzeichnis gespeichert. Zwei Varianten:
- **Einfach:** Nur die matplotlib-Abbildung
- **Annotiert:** Schlüsselmetriken als Text am unteren Bildrand eingebrannt (Gradient %, Richtung, Bewertung, Version)

### JSON-Begleitdatei

Wenn „Analyse-JSON speichern" aktiviert ist, wird eine Datei namens `gradient_analysis.json` gespeichert mit:
- Zeitstempel und Skriptversion
- Bildabmessungen und Rastereinstellungen
- Allen Gradientenmetriken (Stärke, Winkel, Bereich, Gleichmäßigkeit)
- Komplexitätsanalyse (Grad, R²-Werte)
- Vignettierungsanalyse (radiale/lineare R², Diagnose)
- Datenqualitätsflags (lineare Daten, Sterndichte, Normalisierung)
- Kachel-Mediane-Array (für sitzungsübergreifenden Vergleich)
- Erkennungen von ausgedehnten Objekten, Hotspots, Panelgrenzen
- Verbesserungsvorhersage

Wenn beim Ausführen der Analyse eine vorherige JSON-Datei existiert, berechnet das Skript automatisch **Deltas** — und zeigt, wie sich jeder Messwert seit dem letzten Durchlauf verändert hat.

### Konsolidierter Textbericht

Klicken Sie auf **„Export Report"**, um einen umfassenden Klartextbericht zu erstellen, der enthält:
- Kopfzeile (Version, Zeitstempel, Bildinformationen)
- Zusammenfassung und Aktionsplan
- Detaillierte Messwerte
- Vorher/Nachher-Vergleich (falls zutreffend)
- Werkzeugempfehlungen
- Vollständige Workflow-Anleitung

Der Bericht wird:
- Als `gradient_report_{timestamp}.txt` im Siril-Arbeitsverzeichnis gespeichert
- Automatisch in Ihre Zwischenablage kopiert (zum Einfügen in Foren, E-Mails oder Dokumentation)

---

## 13. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Schnelle Prüfung vor dem Stretchen (2 Minuten)

**Szenario:** Sie haben gerade Ihre Subframes gestackt und möchten wissen, ob Sie vor dem Stretchen eine Gradientenextraktion benötigen.

**Workflow:**
1. Laden Sie das gestackte Bild in Siril
2. Starten Sie den Gradient Analyzer
3. Drücken Sie **F5** zur Analyse
4. Prüfen Sie die **Anzeige** — grün bedeutet, Sie können die Extraktion überspringen; gelb/orange/rot bedeutet, Sie brauchen sie
5. Klicken Sie auf **Recommendations** für spezifische Werkzeugvorschläge

**Dauer:** ~2 Minuten einschließlich Analysezeit.

### Anwendungsfall 2: Geführte Gradientenextraktion (5 Minuten)

**Szenario:** Die Anzeige zeigt „Deutlicher Gradient." Sie möchten eine Schritt-für-Schritt-Anleitung.

**Workflow:**
1. Analysieren Sie das Bild (F5)
2. Klicken Sie auf **Analysis Results** → lesen Sie die Zusammenfassung / den Aktionsplan
3. Notieren Sie den empfohlenen Polynomgrad (z.B. Grad 2)
4. Öffnen Sie Sirils Konsole (**Fenster → Konsole**)
5. Geben Sie den vorgeschlagenen Befehl ein, z.B.: `subsky 2 16`
6. Drücken Sie **F5** erneut zur Neuanalyse
7. Prüfen Sie den **Vorher/Nachher**-Tab — die Stärke sollte deutlich gesunken sein
8. Wenn die Anzeige jetzt grün ist, sind Sie fertig. Falls noch gelb, versuchen Sie einen höheren Grad oder GraXpert.

### Anwendungsfall 3: Diagnose, warum Ihr Gradient nicht verschwindet

**Szenario:** Sie haben eine Hintergrundextraktion durchgeführt, aber der Gradient ist immer noch da.

**Workflow:**
1. Analysieren Sie das Bild nach der Extraktion (F5)
2. Prüfen Sie den **Hintergrundmodell**-Tab — zeigen die Residuen Muster? Falls ja, war der Polynomgrad zu niedrig.
3. Prüfen Sie den **Residuen / Maske**-Tab — werden wichtige Kacheln ausgeschlossen? Die Maske zeigt, was bei der Anpassung ignoriert wurde.
4. Prüfen Sie die **Warnungen** — gibt es Banding, Verstärkerleuchten oder Stacking-Ränder? Diese sind keine echten Gradienten und werden durch Polynom-Extraktion nicht entfernt.
5. Klicken Sie auf **Recommendations** — wenn der Gradient zu komplex für Polynome ist, schlägt das Skript GraXpert vor.

### Anwendungsfall 4: Farbanalyse der Lichtverschmutzung

**Szenario:** Sie fotografieren von einem lichtverschmutzten Standort und möchten die LP-Eigenschaften für eine kanalweise Korrektur verstehen.

**Workflow:**
1. Laden Sie das gestackte (lineare) Bild
2. Aktivieren Sie **„Kanäle separat analysieren (RGB)"**
3. Drücken Sie F5
4. Prüfen Sie den **RGB-Kanäle**-Tab — sehen Sie, welcher Kanal den stärksten Gradienten hat
5. Lesen Sie die **LP-Farbcharakterisierung** in den Ergebnissen — das Skript identifiziert die dominante LP-Wellenlänge
6. Wenn die Kanäle deutlich unterschiedliche Gradienten aufweisen, empfiehlt das Skript **VeraLux Nox** für die kanalweise Extraktion

### Anwendungsfall 5: Überprüfung Ihrer Flat-Frames

**Szenario:** Sie möchten überprüfen, ob Ihre Flat-Frames die Vignettierung ordnungsgemäß korrigiert haben.

**Workflow:**
1. Laden Sie ein flat-kalibriertes gestacktes Bild (vor der Hintergrundextraktion)
2. Analysieren Sie mit F5
3. Prüfen Sie das **Vignettierung vs. LP**-Ergebnis:
   - Wenn radiales R² hoch ist → erhebliche Rest-Vignettierung → Ihre Flats funktionieren nicht gut
   - Wenn radiales R² niedrig ist → Flats haben ihre Aufgabe erfüllt
4. Prüfen Sie die **Vignettierungs-Symmetrie**-Warnung — asymmetrische Vignettierung bedeutet, dass das Flat nicht zur Aufnahmekonfiguration passt
5. Prüfen Sie die **FITS-Header-Kalibrierungsprüfung** — das Skript liest `FLATCOR` aus dem Header, um zu bestätigen, dass ein Flat angewendet wurde

### Anwendungsfall 6: Vorher/Nachher-Vergleich

**Szenario:** Sie möchten exakt quantifizieren, wie stark Ihre Verarbeitung den Hintergrund verbessert hat.

**Workflow:**
1. Laden Sie das Bild **vor** der Gradientenextraktion
2. Aktivieren Sie **„Analyse-JSON speichern"**
3. Drücken Sie F5 — Messwerte und Kacheldaten werden in `gradient_analysis.json` gespeichert
4. Führen Sie die Gradientenextraktion in Siril durch
5. Drücken Sie erneut F5 — das Skript lädt die vorherige JSON-Datei und berechnet Deltas
6. Prüfen Sie den **Vorher/Nachher**-Tab in Analysis Results — sehen Sie die genaue prozentuale Verbesserung
7. Die Heatmap verwendet den **gleichen Farbbalkenbereich** wie beim ersten Durchlauf, sodass der visuelle Vergleich aussagekräftig ist

### Anwendungsfall 7: Schmalband-Bildanalyse

**Szenario:** Sie verarbeiten ein Schmalband-Bild (Ha, OIII, SII) und möchten Gradienten überprüfen.

**Workflow:**
1. Laden Sie das Schmalband-Bild
2. Wechseln Sie die Vorlage auf **„Narrowband (streng)"** im Dropdown
3. Drücken Sie F5
4. Die strengeren Schwellenwerte markieren Gradienten, die für Breitband als „normal" gelten würden, aber für Schmalband problematisch sind
5. Hinweis: Schmalbandbilder haben oft niedrigere absolute Gradienten, aber die Schwellenwerte berücksichtigen dies

### Anwendungsfall 8: Vignettierungsbewertung bei schneller Optik

**Szenario:** Sie verwenden ein schnelles Teleskop (f/2–f/4) und möchten die natürliche Vignettierung von externen Gradienten unterscheiden.

**Workflow:**
1. Laden Sie das Bild
2. Wechseln Sie die Vorlage auf **„Fast optics (tolerant)"**
3. Drücken Sie F5
4. Prüfen Sie die **cos⁴-Analyse** in den detaillierten Messwerten — das Skript schätzt den natürlichen optischen Helligkeitsabfall für Ihr Öffnungsverhältnis und trennt ihn von externen Gradienten
5. Die toleranten Schwellenwerte vermeiden Fehlalarme durch den erwarteten cos⁴-Abfall

### Anwendungsfall 9: Dokumentation für Forenhilfe

**Szenario:** Sie posten in einem Astrofotografie-Forum und bitten um Hilfe bei Ihrem Gradienten und möchten diagnostische Daten beifügen.

**Workflow:**
1. Analysieren Sie das Bild (F5)
2. Aktivieren Sie **„Heatmap als PNG speichern"** — gibt Ihnen ein Bild zum Posten
3. Klicken Sie auf **„Export Report"** — der Textbericht wird in Ihre Zwischenablage kopiert
4. Fügen Sie den Bericht in Ihren Forenbeitrag ein und hängen Sie die Heatmap-PNG an
5. Forenmitglieder können genau sehen, wie Ihr Gradient aussieht und was das Werkzeug empfiehlt

---

## 14. Tastaturkürzel

| Taste | Aktion |
|-------|--------|
| `F5` | Analyse starten (entspricht dem Klick auf „Analyze") |
| `Esc` | Fenster schließen |

---

## 15. Tipps & Empfehlungen

### Wann analysieren

1. **Vor dem Stretchen analysieren.** Dies ist die wichtigste Regel. Gradientenmessungen an linearen (ungestretchten) Daten sind genau und vergleichbar. Bei gestretchten Daten werden Gradienten verstärkt und die Prozentwerte sind überhöht.

2. **Nach der Kalibrierung, aber vor der Extraktion analysieren.** Der ideale Zeitpunkt ist: Bias/Dark/Flat kalibriert → registriert → gestackt → **Gradient Analyzer** → Extraktion → Stretchen.

3. **Nach der Extraktion erneut analysieren.** Überprüfen Sie immer, ob Ihre Gradientenentfernung tatsächlich gewirkt hat. Der Vorher/Nachher-Vergleich ist das wertvollste Feature.

### Raster- und Sigma-Einstellungen

4. **16×16 ist ein hervorragender Standard.** Erhöhen Sie nur, wenn Sie lokalisierte Merkmale finden müssen. Verringern Sie nur, wenn Ihr Bild sehr klein ist.

5. **Vertrauen Sie dem Sigma-Vorschlag.** Die adaptive Empfehlung (gelber Text) basiert auf Ihrer tatsächlichen Sterndichte. Wenn dort „try 3.0" steht, probieren Sie es aus.

6. **Verwenden Sie die richtige Vorlage.** Narrowband, Broadband und Fast optics haben grundlegend unterschiedliche Gradientencharakteristiken. Die falsche Vorlage übersieht entweder echte Probleme oder erzeugt Fehlalarme.

### Ergebnisse lesen

7. **Die Anzeige ist Ihre Kurzfassung.** Grün = keine Sorge. Gelb = mild, optionale Korrektur. Orange = definitiv korrigieren. Rot = muss korrigiert werden.

8. **Warnungen zuerst prüfen.** Wenn das Skript Banding, Verstärkerleuchten, fehlende Flats oder Tau erkennt, beheben Sie diese *bevor* Sie die Gradientenextraktion durchführen. Die Warnungen sind in den Empfehlungen nach Priorität geordnet.

9. **Die Heatmap erzählt die Geschichte.** Eine gleichmäßige Heatmap mit einer hellen Ecke = LP. Ein Muster mit dunklen Ecken und heller Mitte = Vignettierung. Streifen = Banding. Zufällige heiße Kacheln = Artefakte.

10. **Nutzen Sie die 3D-Ansicht für Intuition.** Die 3D-Oberfläche macht die Gradienten-„Landschaft" sofort offensichtlich. Eine geneigte Ebene = LP. Eine Schüsselform = Vignettierung. Spitzen = Hotspots.

### Praktische Tipps

11. **Die Abtastpunkt-Hilfe spart Zeit.** Wenn Sie `subsky` verwenden, platzieren Sie Ihre Abtastpunkte in den grün eingekreisten Bereichen der Heatmap. Vermeiden Sie die rot durchkreuzten Bereiche.

12. **Aktivieren Sie die RGB-Einzelanalyse bei farbiger LP.** Wenn Sie in einem städtischen Gebiet mit gemischter Beleuchtung (LED + Natrium) sind, zeigt die chromatische LP-Analyse, welche Kanäle die meiste Korrektur benötigen.

13. **Der JSON-Vergleich ist mächtig.** Aktivieren Sie JSON-Speicherung, analysieren Sie, extrahieren Sie, analysieren Sie erneut — die Delta-Werte geben Ihnen ein objektives Maß der Verbesserung, das zuverlässiger ist als visuelle Beurteilung.

14. **Nicht überextrahieren.** Wenn die Anzeige grün zeigt (< 1,5%), hören Sie auf. Weitere Extraktion riskiert, echtes Signal zu entfernen (schwache Nebulosität, schwache Galaxienhalos). Das Ziel ist „gleichmäßig genug", nicht „perfekt flach."

---

## 16. Fehlerbehebung

### Fehler „Kein Bild geladen"

**Ursache:** Kein Bild ist in Siril geöffnet.
**Lösung:** Laden Sie ein FITS-Bild, bevor Sie das Skript starten.

### Fehler „Keine Verbindung zu Siril möglich"

**Ursache:** Die sirilpy-Verbindung ist abgelaufen.
**Lösung:** Stellen Sie sicher, dass Siril vollständig geladen und reaktionsfähig ist. Versuchen Sie, das Skript zu schließen und erneut zu öffnen.

### Analyse ist sehr langsam

**Ursache:** Hohe Rasterauflösung (32×32 oder mehr) bei einem großen Bild, oder FWHM-Analyse bei einem großen Bild.
**Lösung:** Reduzieren Sie die Rasterauflösung. Die FWHM-Analyse (Tab 8) ist der langsamste Schritt — sie misst Sternformen in jeder Kachel. Bei großen Bildern kann dies Minuten dauern. Andere Tabs erscheinen schnell.

### Warnung „Gestretchte Daten" obwohl Daten linear sind

**Ursache:** Das Skript verwendet statistische Heuristiken (Mittelwert/Median-Verhältnis) zur Erkennung gestretchter Daten. Einige natürlich schiefe Daten können ein falsch-positives Ergebnis auslösen.
**Lösung:** Wenn Sie wissen, dass Ihre Daten linear sind, können Sie diese Warnung ignorieren. Die Analyse ist weiterhin gültig, nur zur Vorsicht gekennzeichnet.

### Gradientenstärke scheint zu hoch / zu niedrig

**Ursache:** Falsche Vorlage ausgewählt. Broadband-Schwellenwerte auf Schmalband-Daten zeigen alles als „gleichmäßig" an. Narrowband-Schwellenwerte auf Breitband-Daten markieren normale Gradienten als schwerwiegend.
**Lösung:** Wählen Sie die korrekte Vorlage im Dropdown.

### Heatmap zeigt Artefakte statt Gradienten

**Ursache:** Hotspots (Satellitenspuren, kosmische Strahlen, helle Sterne, die durch Sigma-Clipping durchkommen) können die Heatmap verzerren.
**Lösung:** Das Skript erkennt und schließt Hotspots automatisch von der Polynomanpassung aus. Prüfen Sie den **Residuen / Maske**-Tab, um zu sehen, welche Kacheln ausgeschlossen wurden. Wenn das Sigma-Clipping nicht aggressiv genug ist, versuchen Sie, den Sigma-Wert zu senken.

### Vorher/Nachher-Vergleich zeigt keine Änderung

**Ursache:** Die JSON-Datei vom vorherigen Durchlauf wurde nicht gespeichert, oder Sie haben ein anderes Bild geladen.
**Lösung:** Aktivieren Sie „Analyse-JSON speichern" vor dem ersten Durchlauf. Stellen Sie sicher, dass Sie dasselbe Bild (im selben Arbeitsverzeichnis) beide Male analysieren.

### FWHM / Exzentrizitäts-Tab ist leer

**Ursache:** Zu wenige Sterne pro Kachel erkannt, oder das Bild ist sehr klein.
**Lösung:** Es werden mindestens 3 Sterne pro Kachel mit FWHM > 1,5 px benötigt. Dichte Nebel oder sehr kleine Kacheln haben möglicherweise nicht genug Sterne. Reduzieren Sie die Rasterauflösung für größere Kacheln.

### RGB-Kanäle-Tab ist leer

**Ursache:** „Kanäle separat analysieren" ist nicht aktiviert, oder das Bild ist mono.
**Lösung:** Aktivieren Sie das Kontrollkästchen „Kanäle separat analysieren" vor der Analyse. Diese Option wird für Mono-Bilder automatisch deaktiviert.

---

## 17. Häufige Fragen

**F: Muss ich das bei jedem Bild ausführen?**
A: Am nützlichsten ist es beim ersten Stack einer Sitzung oder wenn Sie Aufnahmeort, Zielobjekt oder Ausrüstung wechseln. Sobald Sie das typische Gradientenmuster Ihres Setups kennen, können Sie es bei ähnlichen Bildern überspringen. Aber eine Überprüfung lohnt sich immer — Bedingungen ändern sich.

**F: Entfernt dieses Werkzeug tatsächlich Gradienten?**
A: Nein — der Gradient Analyzer ist rein diagnostisch. Er *analysiert* Gradienten und *empfiehlt* Werkzeuge, aber er verändert Ihr Bild nicht. Sie wenden die empfohlene Extraktion separat in Siril an (z.B. `subsky`, `autobackgroundextraction`) oder in externen Werkzeugen wie GraXpert.

**F: Kann ich das auf ungestackten Subframes verwenden?**
A: Ja, es funktioniert mit jedem FITS-Bild. Die Analyse einzelner Subframes kann helfen, zu identifizieren, welche Frames die schlimmsten Gradienten haben, oder Probleme wie Verstärkerleuchten oder Banding vor dem Stacken zu erkennen.

**F: Was ist der Unterschied zwischen diesem Tool und dem einfachen Ausführen von AutoBGE?**
A: AutoBGE entfernt blind *irgendetwas* vom Hintergrund. Der Gradient Analyzer sagt Ihnen *was zuerst vorhanden ist* — Vignettierung, LP, Banding, Verstärkerleuchten, Stacking-Ränder — damit Sie die richtige Lösung für jedes Problem anwenden können. AutoBGE auf einem Bild mit Verstärkerleuchten auszuführen verteilt das Problem nur; zu wissen, dass es Verstärkerleuchten ist, sagt Ihnen, stattdessen Dark-Frames anzuwenden.

**F: Warum ändert sich die Gradientenstärke, wenn ich die Rasterauflösung ändere?**
A: Die P95-P5-Metrik wird aus Kachel-Medianen berechnet. Mehr Kacheln = mehr räumliche Abtastung = leicht unterschiedliche P95/P5-Werte. Die Änderung ist normalerweise gering (innerhalb von 0,5%). Für Konsistenz verwenden Sie bei Vorher/Nachher-Vergleichen dieselbe Rasterauflösung.

**F: Was ist die minimale Bildgröße?**
A: Technisch funktioniert jedes Bild, aber für aussagekräftige Ergebnisse benötigen Sie mindestens 400×400 Pixel, damit die Kacheln beim Standard-16×16-Raster jeweils 25+ Pixel groß sind. Größere Bilder liefern bessere Ergebnisse.

**F: Kann ich das mit OSC-Kameras (One-Shot-Color) verwenden?**
A: Ja. OSC-Bilder werden von Siril zu RGB debayert, sodass der Gradient Analyzer sie als normale 3-Kanal-Bilder sieht. Die kanalweise Analyse funktioniert korrekt.

**F: Warum empfiehlt das Skript GraXpert für mein Bild?**
A: Wenn die Qualität der Polynomanpassung schlecht ist (alle R² < 0,5), können traditionelle Polynomoberflächen Ihren Gradienten nicht gut modellieren. Dies geschieht bei komplexen Gradienten aus mehreren Quellen. GraXpert verwendet KI, um beliebige Hintergrundmuster zu modellieren, die Polynome nicht erfassen können.

**F: Wie genau ist die Schätzung der Himmelshelligkeit / des Bortle-Werts?**
A: Es ist eine grobe Annäherung (±1–2 Magnituden). Sie erfordert ein SPCC-kalibriertes Bild mit bekanntem Bildmaßstab und Belichtungszeit. Verwenden Sie sie als allgemeinen Indikator, nicht als präzise Messung. Für seriöse Himmelsqualitätsüberwachung verwenden Sie ein dediziertes SQM-Messgerät.

**F: Was bedeuten die Farben in der Gradientenstärke-Anzeige?**
A: Grün = sehr gleichmäßig, keine Aktion nötig. Gelb = leichter Gradient, sanfte Extraktion ist optional. Orange = deutlicher Gradient, Extraktion wird empfohlen. Rot = starker Gradient, aggressive Extraktion ist erforderlich. Die Schwellenwerte hängen von der gewählten Vorlage ab.

---

## Danksagung

**Entwickelt von** Sven Ramuschkat
**Webseite:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die auch umfasst:
- Svenesis Blink Comparator
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn Sie dieses Werkzeug nützlich finden, erwägen Sie, die Entwicklung über [Buy me a Coffee](https://buymeacoffee.com/svenesis) zu unterstützen.*
