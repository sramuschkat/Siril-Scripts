# Svenesis Blink Comparator — Benutzeranleitung

**Version 1.2.8** | Siril Python-Skript zur Bildauswahl & Qualitätsanalyse

> *Vergleichbar mit PixInsight's Blink + SubframeSelector — aber kostenlos, quelloffen und eng in Siril integriert.*

---

## Inhaltsverzeichnis

1. [Was ist der Blink Comparator?](#1-was-ist-der-blink-comparator)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Die Messwerte verstehen](#6-die-messwerte-verstehen)
7. [Anzeigemodi & Autostretch-Presets](#7-anzeigemodi--autostretch-presets)
8. [Methoden zur Bildauswahl](#8-methoden-zur-bildauswahl)
9. [Das Rückgängig-System](#9-das-rückgängig-system)
10. [Verwerfen anwenden (Datei-Verschiebung)](#10-verwerfen-anwenden-datei-verschiebung)
11. [Exportoptionen](#11-exportoptionen)
12. [Anwendungsfälle & Arbeitsabläufe](#12-anwendungsfälle--arbeitsabläufe)
13. [Tastaturkürzel](#13-tastaturkürzel)
14. [Tipps & Empfehlungen](#14-tipps--empfehlungen)
15. [Fehlerbehebung](#15-fehlerbehebung)
16. [Häufige Fragen](#16-häufige-fragen)
17. [Änderungen seit v1.2.3](#17-änderungen-seit-v123)

---

## 1. Was ist der Blink Comparator?

Der **Svenesis Blink Comparator** ist ein Siril-Python-Skript, das alle Bilder einer Astrofotografie-Sequenz schnell animiert („blinkt"), damit du sie visuell inspizieren, schlechte Bilder erkennen und sie vor dem Stacken verwerfen kannst.

Stell dir das Tool als **Qualitätskontroll-Inspektor** für deine Einzelbilder vor. Es kombiniert:

- **Visuelle Inspektion** — deine Bilder laufen wie ein Film ab, Probleme springen ins Auge
- **Statistische Analyse** — FWHM, Rundheit, Sternanzahl und Hintergrund für jedes Bild
- **Verwerfen per Klick** — markiere schlechte Bilder; beim Schließen schreibt das Skript eine `rejected_frames.txt`-Audit-Datei und verschiebt die verworfenen FITS in einen Unterordner `rejected/` neben deinen Originalen

Das Ergebnis: ein saubereres, schärferes Endbild, weil du die Bilder entfernt hast, die die Qualität heruntergezogen hätten — und weil das Verwerfen nur eine einfache Dateiverschiebung ist, kannst du jede Entscheidung rückgängig machen, indem du die Datei einfach aus `rejected/` zurückziehst.

---

## 2. Hintergrundwissen für Einsteiger

### Warum müssen wir Bilder auswählen?

Beim Fotografieren des Nachthimmels machst du viele Einzelaufnahmen (sogenannte „Subframes" oder „Subs"). Diese werden ausgerichtet und zu einem finalen Bild gestackt. Aber nicht jedes Subframe ist gleich gut. Während einer typischen Session kann einiges schiefgehen:

| Problem | Was passiert | Wie es aussieht |
|---------|-------------|-----------------|
| **Wolken** | Dünne Wolken ziehen durch dein Bildfeld | Hintergrund wird heller, Sterne verblassen |
| **Satellitenspuren** | Ein Satellit kreuzt dein Bild | Heller Streifen über das Bild |
| **Tracking-Fehler** | Deine Montierung hat einen Aussetzer | Sterne werden zu länglichen Linien |
| **Fokusdrift** | Temperaturänderungen verschieben den Fokus | Sterne werden aufgedunsen und unscharf |
| **Windböen** | Wind schüttelt dein Teleskop | Sterne sind für einige Bilder aufgedunsen |
| **Flugzeuglichter** | Ein Flugzeug blinkt durch | Heller blinkender Punkt |
| **Tau / Frost** | Feuchtigkeit bildet sich auf der Optik | Sterne bekommen Halos, Hintergrund steigt, Sternzahl fällt |

Wenn du diese schlechten Bilder in deinen Stack aufnimmst, **verschlechtern** sie dein Endergebnis: unschärfere Sterne, höheres Rauschen, Spurenartefakte. Schon 5–10 % der schlechtesten Bilder zu entfernen kann das Ergebnis spürbar verbessern.

### Was ist „Blinken"?

Ein **Blink Comparator** ist eine Astronomie-Technik aus den 1920ern (so wurde Pluto entdeckt!). Du wechselst schnell zwischen Bildern, damit alles, was sich ändert — ein bewegtes Objekt, eine Helligkeitsänderung, eine Fokusverschiebung — dem menschlichen Auge sofort auffällt.

In der Astrofotografie macht das Blinken durch deine Subframes Probleme **offensichtlich**, die du in einem einzelnen Bild nie bemerken würdest.

### Was ist FWHM?

**FWHM** (Full Width at Half Maximum, Halbwertsbreite) misst die Sternschärfe in Pixeln. Stell dir einen Stern als Glockenkurve der Helligkeit vor — FWHM ist die Breite dieser Glocke auf halber Höhe.

- **Niedrige FWHM = scharfe Sterne** (gut)
- **Hohe FWHM = aufgedunsene Sterne** (schlecht — Fokus, Seeing oder Tracking)
- Typischer Bereich: 2–6 Pixel, je nach Setup und Bedingungen

### Was ist Rundheit?

**Rundheit** misst, wie kreisförmig deine Sterne sind, auf einer Skala von 0 bis 1:

- **1,0 = perfekter Kreis** (ideal)
- **0,0 = eine Linie** (starkes Trailing)
- Über 0,75 ist allgemein gut
- Unter 0,6 deutet meist auf Tracking- oder Windprobleme hin

Verwandt mit **Exzentrizität** (in PixInsight): `Exzentrizität ≈ 1 − Rundheit`.

### Was ist der Hintergrundpegel?

Der **Hintergrundpegel** ist die mittlere Helligkeit des Himmels in deinem Bild. Er sollte über alle Bilder hinweg konstant sein.

- **Ausreißer nach oben** = Wolken, Lichtverschmutzung, Flugzeug, Mond
- **Ansteigender Trend** = Morgendämmerung, zunehmende Wolken
- **Konstant** = gute Bedingungen

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweis |
|-----------|----------------|---------|
| **Siril** | 1.4.0+ | Muss Python-Skript-Unterstützung aktiviert haben |
| **sirilpy** | Gebündelt | Kommt mit Siril 1.4+ |
| **numpy** | aktuelle Version | Wird automatisch installiert |
| **PyQt6** | 6.x | Wird automatisch installiert |
| **matplotlib** | 3.x | Wird automatisch installiert |
| **Pillow** | beliebig | *Optional* — nur für GIF-Export |

### Installation

1. Lade `Svenesis-BlinkComparator.py` aus dem [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Lege es in das Siril-Scripts-Verzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starte Siril neu. Das Skript erscheint unter **Processing → Scripts**.

Das Skript installiert fehlende Abhängigkeiten (`numpy`, `PyQt6`, `matplotlib`) beim ersten Start automatisch.

---

## 4. Erste Schritte

Seit v1.2.4 arbeitet der Blink Comparator **ordnerbasiert**: Du zeigst ihm ein Verzeichnis mit FITS-Dateien, und er baut sich daraus seine eigene temporäre Sequenz. Du musst in Siril nichts vorher registrieren oder laden.

### Schritt 1: Skript starten

Gehe zu **Processing → Scripts → Svenesis Blink Comparator**.

Ein Ordner-Auswahldialog öffnet sich. Wähle den Ordner mit deinen FITS-Bildern (`.fit`, `.fits`, `.fts` — die Endungen werden ohne Berücksichtigung der Groß-/Kleinschreibung erkannt, also funktionieren auch `.FIT` / `.Fits`). Komprimierte FITS (`.fz`, `.gz`) werden **nicht** unterstützt — vorher dekomprimieren. Das Skript durchsucht nur eine Verzeichnisebene.

### Schritt 2: Sequenzaufbau abwarten

Im Hintergrund führt das Skript folgendes aus:

1. `cd <ordner>` + `convert svenesis_blink -fitseq` baut eine einzelne FITSEQ-Datei namens `svenesis_blink.fits`.
2. `load_seq svenesis_blink` lädt die Sequenz.
3. Bildmetadaten werden geprüft (Abmessungen, Kanäle, Anzahl).
4. Statistiken pro Bild (FWHM, Rundheit, Hintergrund, Sterne, Median, Sigma) werden aus Sirils Registrierungsdaten geladen, falls vorhanden.

Ein Fortschrittsbalken zeigt die Statistik-Ladephase. Die Temp-Sequenz wird beim Schließen des Fensters automatisch aufgeräumt.

### Schritt 3: Sterndetektion ausführen (falls nötig)

Falls FWHM, Rundheit, Sterne und Gewicht leer sind, erscheint oben ein **gelber Banner**:

> ⚠️ Keine Sterndetektionsdaten. Klicke, um Sterndetektion zu starten…

Klicke auf den Banner. Dies führt `register svenesis_blink -2pass` aus, erkennt Sterne in jedem Bild und berechnet FWHM, Rundheit, Hintergrundpegel und Sternanzahl. Dauert je nach Bildanzahl einige Sekunden bis Minuten. Der Fortschrittsbalken begleitet die Detektion und den anschließenden Stretch-/Referenz-Rebind.

**Hinweis:** Median und Sigma sind *immer* verfügbar — sie benötigen keine Sterndetektion.

### Schritt 4: Inspizieren und auswählen

Jetzt kannst du:

- **Die Animation abspielen** (Leertaste) mit 3–5 FPS, um Probleme visuell zu erkennen — was sich ändert (Satelliten, Wolken) springt dem Auge sofort ins Gesicht
- **Die Statistiktabelle nach FWHM sortieren** (schlechteste Bilder oben)
- **Batch-Verwerfen** die schlechtesten 10 % automatisch entfernen
- **Einzelne Bilder markieren** mit G (gut) oder B (schlecht)

### Schritt 5: Anwenden und schließen

Klicke auf **Verwerfen übernehmen && Schließen** (oder drücke Esc — du wirst gefragt, ob anwenden, verwerfen oder abbrechen). Das Skript:

1. Erstellt einen Unterordner `rejected/` innerhalb deines Quellordners (falls Verwerfen anstehen).
2. **Verschiebt** jede verworfene FITS in `rejected/` (die Dateinamen bleiben unverändert).
3. Schreibt `rejected_frames.txt` neben deine Originale mit einem Header (Sequenzname, Zeitstempel, Anzahl) und einer Datei pro Zeile — nur die Dateien, die tatsächlich in `rejected/` gelandet sind.

Behaltene Bilder bleiben exakt dort, wo sie waren — nichts wird umgeschrieben, umbenannt oder modifiziert. Wenn du das Skript später auf demselben Ordner erneut ausführst, tauchen bereits verworfene Dateien nicht mehr auf, weil der Scan nur die oberste Ebene erfasst.

---

## 5. Die Benutzeroberfläche

Das Fenster ist in drei Hauptbereiche unterteilt.

### Linkes Panel (Steuerungsbereich)

Die linke Seite (340 px breit) enthält alle Bedienelemente in Gruppen:

- **Wiedergabe:** Play/Pause, Bildnavigation, Geschwindigkeits-Slider, Loop-Schalter, „Nur eingeschlossene Bilder"-Filter
- **Anzeigemodus:** Normal, Nebeneinander (vs. Referenz)
- **Bildmarkierung:** Behalten (G) / Verwerfen (B), Alle Verwerfen zurücksetzen, Auto-Weiter, Anzeige ausstehender Änderungen
- **Batch-Auswahl:** Schwellwert-Filter + Schlechteste N %-Modus
- **Freigabeausdruck:** Mehrkriterien-UND-Filter
- **CSV exportieren / GIF exportieren** am unteren Ende
- **Buy me a Coffee · Hilfe · Verwerfen übernehmen && Schließen**

### Rechtes Panel (Reiterbereich)

Der Hauptbereich hat vier Reiter.

#### Viewer-Reiter

Die Bild-Anzeigefläche. Zeigt das aktuelle Bild mit dem gewählten Autostretch-Preset.

- **Scrollrad** zum Zoomen (0,1× bis 20×) — die Zoom-Prozentanzeige in der Werkzeugleiste aktualisiert sich live
- **Rechtsklick-Ziehen** zum Verschieben
- **Z** (oder **Fit-in-Window**-Knopf) für Ansicht einpassen
- Eine Werkzeugleiste unter der Leinwand enthält: Zoom-Anzeige, **Fit-in-Window**, **Kopieren (Strg+C)**, **Overlay**-Checkbox, **Stretch**-Preset-Auswahl, **Thumbs** (Thumbnail-Größe)-Slider und eine Shortcut-Legende.

#### Statistiktabellen-Reiter

Alle Bilder in einer sortierbaren Tabelle mit 10 Spalten:

- Bild #, Gewicht, FWHM, Rundheit, BG-Level, Sterne, Median, Sigma, Datum, Status
- **Spaltenkopf klicken** zum Sortieren (erneut klicken kehrt Reihenfolge um)
- **Zeile klicken** springt im Viewer zu diesem Bild
- **Pfeiltasten** navigieren die Zeilen
- **Strg+Klick** oder **Umschalt+Klick** für Mehrfachauswahl
- **Rechtsklick** auf markierte Zeilen → „N ausgewählte Bild(er) verwerfen"
- Ausgeschlossene Zeilen haben einen rötlichen Hintergrund
- Das aktuelle Bild ist blau hervorgehoben

#### Statistikgraph-Reiter

Liniengraphen für Kennzahlen über alle Bilder hinweg:

- Umschaltbar: FWHM, Hintergrund, Rundheit (Checkboxen über dem Diagramm)
- **Dünne Linie** = Rohwerte pro Bild
- **Dicke Linie** = 7-Bild-Gleitmittel (zeigt Trends)
- **Rote Punkte** = ausgeschlossene Bilder
- **Weiße gestrichelte Linie** = aktuelle Bildposition
- Ideal zum Erkennen von: Fokusdrift (FWHM-Rampe), Wolken (Hintergrund-Spike), Tracking-Degradation (Rundheitsabfall)

#### Scatterplot-Reiter

2D-Punktdiagramm zweier Kennzahlen:

- X- und Y-Achse per Dropdown auswählbar (FWHM, Rundheit, Hintergrund, Sterne, Gewicht)
- **Grüne Punkte** = eingeschlossene Bilder
- **Rotes ✕** = ausgeschlossene Bilder
- **Gelber/goldener Stern** = aktuelles Bild (immer im Vordergrund)
- **Punkt klicken** springt zu diesem Bild
- Achsen-normalisierte Klick-Erkennung — beide Achsen tragen gleich zur Nähe-Berechnung bei, unabhängig von ihren Zahlenbereichen
- Beste Kombinationen: **FWHM vs Rundheit** (Sternqualität), **FWHM vs Hintergrund** (Wolken + Seeing)

### Unterer Bereich (Filmstreifen)

Ein horizontal scrollbarer Streifen mit Bildminiaturen (immer sichtbar):

- **Grüner Rand** = eingeschlossen
- **Roter Rand** = ausgeschlossen
- **Blauer Rand** = aktuelles Bild
- Klicke auf eine Miniatur, um zu diesem Bild zu springen
- Miniaturen werden beim Scrollen bedarfsgesteuert geladen
- Größe über den **Thumbs**-Slider in der Viewer-Werkzeugleiste einstellbar (40–160 px)
- Der Miniatur-Cache verwendet die bereits gestretchten Anzeigedaten aus dem Haupt-Cache wieder — ein Bild, das bereits im Haupt-Cache liegt, verursacht für seine Miniatur keinen zweiten Festplatten-Zugriff

---

## 6. Die Messwerte verstehen

### FWHM (Full Width at Half Maximum)

| Aspekt | Details |
|--------|---------|
| **Was** | Sterndurchmesser auf halber Spitzenhelligkeit, in Pixeln |
| **Quelle** | Siril-Registrierungsdaten (`get_seq_regdata`) |
| **Gute Werte** | Niedriger ist besser. Typisch: 2–6 px |
| **Benötigt** | Sterndetektion muss gelaufen sein |

**Interpretation:** Plötzlicher Anstieg = Fokusdrift, Wind oder schlechtes Seeing. Langsamer Anstieg = thermische Fokusverschiebung. Einzelner Spike = Windböe.

### Rundheit

| Aspekt | Details |
|--------|---------|
| **Was** | Sternkreisform, 0 (Linie) bis 1 (perfekter Kreis) |
| **Quelle** | Siril-Registrierungsdaten |
| **Gute Werte** | Über 0,75. Unter 0,6 = Probleme |
| **Benötigt** | Sterndetektion muss gelaufen sein |

**Interpretation:** Niedrige Rundheit = Tracking-Fehler, Wind oder optischer Tilt. Gruppe niedriger Werte = Montierungs-Hiccup oder Wind-Burst.

### Hintergrundpegel (BG-Level)

| Aspekt | Details |
|--------|---------|
| **Was** | Mediane Himmelshelligkeit, normalisiert auf [0, 1] |
| **Quelle** | Registrierungsdaten (`background_lvl`) oder `stats.median` als Fallback |
| **Gute Werte** | Konstant über Bilder hinweg |
| **Benötigt** | Immer verfügbar (Fallback nutzt Basisstatistik) |

**Interpretation:** Spike = Wolken, Flugzeug oder Mond. Anstieg = Dämmerung oder zunehmende Lichtverschmutzung.

### Sterne (Sternanzahl)

| Aspekt | Details |
|--------|---------|
| **Was** | Anzahl erkannter Sterne im Bild |
| **Quelle** | Siril-Registrierungsdaten (`number_of_stars`) |
| **Gute Werte** | Konstante Anzahl; höher ist meist besser |
| **Benötigt** | Sterndetektion muss gelaufen sein |

**Interpretation:** Plötzlicher Abfall = Wolken, Tau oder starker Defokus. Langsame Abnahme = dünne Wolken oder steigende Luftfeuchtigkeit.

### Gewicht (Zusammengesetzter Qualitätsscore)

| Aspekt | Details |
|--------|---------|
| **Was** | Einzelner Qualitätsscore von 0 (schlechtester) bis 1 (bester) |
| **Quelle** | Vom Skript aus FWHM, Rundheit, Hintergrund, Sternen berechnet |
| **Benötigt** | Mindestens einige der obigen Kennzahlen |

**Formel:**
```
w_fwhm  = 1 − (fwhm − min) / (max − min)        [niedrigere FWHM = besser]
w_round = roundness                              [höher = besser]
w_bg    = 1 − (bg − min) / (max − min)          [niedriger BG = besser]
w_stars = sqrt(stars) / sqrt(max_stars)          [mehr = besser]
Gewicht = Mittelwert der verfügbaren Faktoren
```

**Interpretation:** Sortiere aufsteigend nach Gewicht, um schlechteste Bilder oben zu sehen. Nutze „Schlechteste N % verwerfen" mit Gewicht, um die qualitativ niedrigsten Subframes auszusortieren.

### Median

| Aspekt | Details |
|--------|---------|
| **Was** | Median-Pixelwert des gesamten Bildes, normalisiert auf [0, 1] |
| **Quelle** | Siril-Statistik pro Kanal (`get_seq_stats`) |
| **Immer verfügbar** | Ja — keine Sterndetektion nötig |

**Interpretation:** Nahezu identisch zum Hintergrundpegel bei himmelsdominierten Astrofotos. Nützlich als universelle Fallback-Kennzahl.

### Sigma (σ)

| Aspekt | Details |
|--------|---------|
| **Was** | Standardabweichung der Pixelwerte — misst Streuung |
| **Quelle** | Siril-Statistik pro Kanal |
| **Immer verfügbar** | Ja — keine Sterndetektion nötig |

**Interpretation:** Hohes Sigma + hoher Hintergrund = Rauschen durch Wolken (schlecht). Hohes Sigma + niedriger Hintergrund = echtes Deep-Sky-Signal (gut).

### Datum

| Aspekt | Details |
|--------|---------|
| **Was** | Beobachtungszeitstempel aus FITS-Header (`DATE-OBS`) |
| **Quelle** | FITS-Metadaten via `get_seq_imgdata` |
| **Hinweis** | Nicht alle Kameras schreiben dieses Feld (z. B. SeeStar S50) |

### Status

Zeigt **Eingeschlossen** (grün) oder **Ausgeschlossen** (rot). Statusänderungen bleiben lokal, bis du das Fenster über **Verwerfen übernehmen && Schließen** schließt (siehe §10).

---

## 7. Anzeigemodi & Autostretch-Presets

### Normal-Modus (Standard)

Einzelbild-Autostretch-Ansicht. Jedes Bild wird mit einer Midtone-Transfer-Funktion (STF) gestretcht, die Siril/PixInsights Autostretch-Algorithmus nachbildet — mit **global verknüpftem** Median/MAD, sodass Helligkeitsunterschiede zwischen Bildern sichtbar bleiben. Genau das lässt bewölkte oder diesige Bilder während der Wiedergabe ins Auge springen.

Nutze **Normal-Modus bei 3–5 FPS** für die Jagd auf Satelliten, Flugzeuge und Tracking-Fehler. Alles, was sich *ändert* — eine Spur, eine wandernde Wolke, ein Tracking-Ruck — ist für das Auge sofort offensichtlich. Einen separaten „Difference"-Modus gibt es in dieser Version nicht mehr; die Wiedergabe im Normal-Modus liefert dasselbe Ergebnis ohne den Overhead der pro-Bild-Subtraktion.

### Nebeneinander (vs. Referenz)-Modus

Aktuelles Bild links, Referenzbild (das erste Bild der Sequenz) rechts, mit synchronisiertem Zoom und Pan. Nützlich für direkten A/B-Vergleich — insbesondere für Sternformänderungen oder lokale Artefakte, die du gegen eine bekannte gute Referenz prüfen willst.

### Autostretch-Presets

Das **Stretch**-Dropdown in der Viewer-Werkzeugleiste steuert, wie jedes Bild auf Anzeigehelligkeit abgebildet wird. Vier Presets stehen zur Verfügung:

| Preset | `shadows_clip` | `target_median` | Charakter |
|--------|----------------|-----------------|-----------|
| Conservative | −3,5 σ | 0,20 | Dunklerer Hintergrund, bewahrt schwache Details |
| **Default** | −2,8 σ | 0,25 | PixInsight-Style STF, ausgewogen |
| Aggressive | −1,5 σ | 0,35 | Heller, höherer Kontrast |
| Linear | — | — | Kein Stretch — Rohdaten auf 0–255 beschnitten |

Wechsel des Presets invalidiert den Bild- und Miniatur-Cache, rendert das aktuelle Bild neu und baut sichtbare Miniaturen wieder auf. Deine Wahl wird per QSettings über Sessions hinweg gespeichert.

**Tipp:** Conservative für Nebel (bewahrt schwache Strukturen), Default für generische Inspektion, Aggressive zum Aufspüren subtiler Helligkeitsanomalien (Wolken, Dunst) und Linear, wenn du sehen willst, was der Sensor tatsächlich aufgezeichnet hat, ohne Stretch-Artefakte.

### Weitere Anzeigefunktionen

- **Bild-Info-Overlay:** Zeigt Bildnummer, FWHM, Rundheit und Gewicht in der oberen linken Ecke an. Über die **Overlay**-Checkbox in der Viewer-Werkzeugleiste umschaltbar; der Overlay-Zustand wird in die Ausgabe von **Kopieren in Zwischenablage** und **GIF-Export** eingebrannt.
- **A/B-Umschaltung (Taste T):** Fixiere das aktuelle Bild, drücke dann T, um zwischen dem fixierten Bild und dem aktuell navigierten zu wechseln.

---

## 8. Methoden zur Bildauswahl

### Methode 1: Manuelle Markierung (G / B-Tasten)

Der einfachste Ansatz — scrolle durch deine Sequenz und markiere jedes Bild:

1. Drücke **Leertaste** zum Abspielen, oder nutze **←/→** für Einzelbild-Navigation
2. Drücke **B**, wenn du ein schlechtes Bild siehst (ausschließen)
3. Drücke **G**, um ein zuvor ausgeschlossenes Bild wieder einzuschließen
4. Mit **Auto-Weiter nach Markierung** (Standard) springt der Viewer nach Markierung zum nächsten Bild

**Am besten für:** Kleine Sequenzen (< 100 Bilder) oder Einzelbildprüfung von Kandidaten aus anderen Methoden.

### Methode 2: Batch-Verwerfen per Schwellwert

Verwirf alle Bilder, die einen bestimmten Kennzahl-Wert überschreiten:

1. Wähle im Bereich **Batch-Auswahl** eine Kennzahl (FWHM, Hintergrund, Rundheit)
2. Wähle einen Operator (>, <, >=, <=)
3. Gib einen Schwellwert ein
4. Die **Vorschau** zeigt, wie viele Bilder passen
5. Klicke **„Passende verwerfen"**

**Beispiel:** Alle Bilder mit FWHM > 4,5 verwerfen → entfernt alle aufgedunsenen.

### Methode 3: Schlechteste N % verwerfen

Verwirf automatisch den untersten Prozentsatz:

1. Wähle **„Schlechteste N %"**-Modus
2. Wähle eine Kennzahl (FWHM, Hintergrund, Rundheit, Gewicht)
3. Setze den Prozentsatz (z. B. 10 %)
4. Klicke **„Passende verwerfen"**

Für FWHM und Hintergrund bedeutet „schlechteste" = höchste Werte. Für Rundheit und Gewicht = niedrigste.

**Beispiel:** Schlechteste 10 % nach Gewicht verwerfen → entfernt die 9 niedrigsten Bilder aus 90.

### Methode 4: Freigabeausdrücke (Mehrkriterien)

Definiere mehrere Bedingungen, die gute Bilder gleichzeitig erfüllen müssen:

1. Klicke **„+ Bedingung hinzufügen"**
2. Wähle Kennzahl, Operator und Wert pro Bedingung
3. Füge weitere Bedingungen hinzu (UND-Logik)
4. Die Vorschau zeigt, wie viele Bilder scheitern
5. Klicke **„Nicht-passende verwerfen"**, um alle Bilder auszuschließen, die eine Bedingung verletzen

**Beispiel:**
```
FWHM < 4,5  UND  Rundheit > 0,7  UND  Sterne > 50
```
Das behält nur Bilder mit scharfen, runden Sternen und guter Sternzahl.

**Vergleichbar mit** PixInsights SubframeSelector-Freigabeausdrücken.

### Methode 5: Mehrfachauswahl in der Tabelle

Für chirurgische Entfernung identifizierter Einzelbilder:

1. Wechsle in den **Statistiktabellen**-Reiter
2. **Strg+Klick** für Einzelzeilen, **Umschalt+Klick** für Bereich
3. **Rechtsklick** auf die Auswahl → „N ausgewählte Bild(er) verwerfen"

**Am besten für:** Einzelne Ausreißer, die du im Scatterplot oder Graphen entdeckt hast.

### Alle Verwerfen zurücksetzen

Der Knopf **Alle Verwerfen zurücksetzen** in der Bildmarkierungs-Gruppe löscht jeden Ausschluss — sowohl die Baseline (was Siril beim Start hatte) als auch alle ausstehenden Markierungen — und markiert jedes Bild wieder als eingeschlossen. Nützlich, wenn du die Auswahl komplett neu starten willst. Diese Aktion ist nicht über Strg+Z rückgängig machbar.

---

## 9. Das Rückgängig-System

Jede Markierungsaktion kann mit **Strg+Z** rückgängig gemacht werden:

- **Einzelmarkierungen** (G/B auf einem Bild) werden einzeln rückgängig gemacht
- **Batch-Operationen** (Schwellwert, schlechteste N %, Freigabeausdruck, Mehrfachauswahl) werden mit einem einzigen Strg+Z als **gesamte Batch** zurückgenommen — du musst nicht N-mal drücken
- **Alle Verwerfen zurücksetzen** ist *nicht* auf dem Undo-Stack (bewusst als nukleare Option gedacht)
- Undo-Stack-Tiefe: 500 Operationen

**Beispiel:** Du verwirfst die schlechtesten 15 % (13 Bilder). Zu aggressiv. Ein Strg+Z stellt alle 13 wieder her.

Schnelles Strg+Z-Hämmern wird entprellt — Statistikgraph, Scatterplot und Filmstreifen/Slider bündeln sich zu einem einzigen Refresh nach ~150 ms, damit das Hotkey auch bei langen Sequenzen flüssig bleibt.

---

## 10. Verwerfen anwenden (Datei-Verschiebung)

Der Blink Comparator ist **ordnerbasiert**: Verwerfen werden als tatsächliche Dateiverschiebungen im Dateisystem angewendet, nicht als Metadaten-Flags in einer `.seq`-Datei. Das hält den Workflow transparent und vollständig rückgängig machbar.

### Wann Änderungen angewendet werden

Markierungen bleiben lokal, bis du das Fenster schließt. Schließen über:

- **„Verwerfen übernehmen && Schließen"**-Knopf, oder
- **Esc** / Fenster schließen mit ausstehenden Markierungen → Ja/Nein/Abbrechen-Dialog, ob angewendet werden soll.

### Was beim Anwenden passiert

Ein Bestätigungsdialog zeigt die Anzahl und den Zielpfad, dann:

1. Ein Unterordner `rejected/` wird in deinem Quellordner angelegt (falls nicht vorhanden).
2. Jede verworfene FITS wird in `rejected/` **verschoben** (nicht kopiert). Dateinamen bleiben unverändert — kein Umbenennen.
3. Eine Textdatei `rejected_frames.txt` wird neben deine Originale geschrieben. Sie enthält einen Header (Sequenzname, Zeitstempel, Anzahl) und eine Datei pro Zeile — aufgeführt sind nur die Dateien, die tatsächlich in `rejected/` gelandet sind.
4. Das Skript meldet verschobene vs. fehlgeschlagene Anzahl im Siril-Log.

### Teilweise Fehler

Falls einige Verschiebungen scheitern (OS-Dateisperre, Rechte, voller Datenträger), tut das Skript folgendes:

- Es committet nur die Bilder, deren Verschiebung erfolgreich war (sie fallen aus der Pending-Liste).
- Gescheiterte Bilder bleiben in der Pending-Menge — der Close-Confirm-Dialog weist beim nächsten Schließversuch erneut darauf hin.
- In `rejected_frames.txt` stehen nur die tatsächlich verschobenen Dateien.

So lässt ein teilweiser Fehler dein Dateisystem nie in einem inkonsistenten Zustand — die Audit-Datei spiegelt immer exakt wider, was physisch in `rejected/` ist.

### Ein Verwerfen nach dem Schließen rückgängig machen

Weil es nur Dateiverschiebungen sind, ist der Workflow reversibel. Ziehe einfach die Datei aus `rejected/` zurück in den Quellordner. Die Audit-Datei `rejected_frames.txt` kannst du löschen oder ignorieren — sie wird beim nächsten Lauf sowieso überschrieben.

### Originale werden nie verändert

Behaltene Bilder werden überhaupt nicht angefasst. Das Skript schreibt keine Header, speichert nicht erneut, berührt die Originalbytes nie.

---

## 11. Exportoptionen

### Statistik-CSV exportieren (.csv)

Exportiert die vollständige Statistiktabelle als CSV mit Spalten:
`Frame, Weight, FWHM, Roundness, Background, Stars, Median, Sigma, Date, Included`

Nützlich für externe Analyse in Tabellenkalkulationen, Python-Notebooks oder anderen Tools.

### Animiertes GIF exportieren (.gif)

Erstellt ein animiertes GIF der Blink-Animation:

- Nur eingeschlossene Bilder (ausgeschlossene werden übersprungen)
- Skaliert auf maximal 480 px
- Nutzt aktuelle Wiedergabegeschwindigkeit (FPS) und Autostretch-Preset
- Respektiert die Overlay-Checkbox — Bild-Info-Badges werden ins GIF eingebrannt, wenn sichtbar
- Benötigt Pillow (`pip install Pillow`)

Ideal zum Teilen in Foren, sozialen Medien oder Beobachtungsberichten.

### Bild in Zwischenablage kopieren (Strg+C)

Kopiert das aktuelle Bild (wie angezeigt, mit Stretch und Overlay) in die Zwischenablage. Im **Nebeneinander**-Modus wird die vollständige Kompositansicht erfasst, nicht nur das linke rohe Pixmap. Direkt in einen Forenbeitrag, Bildeditor oder eine Präsentation einfügen.

---

## 12. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Schnelle Session-Prüfung (5 Minuten)

**Szenario:** Du hast gerade eine Session mit 120 Subframes abgeschlossen und willst vor dem Stacken eine schnelle Qualitätsprüfung.

**Ablauf:**
1. Blink Comparator starten → Ordner mit den FITS wählen
2. Sterndetektion ausführen, falls nötig (gelber Banner)
3. In den **Statistiktabellen**-Reiter, absteigend nach **FWHM** sortieren — schlechteste oben
4. **„Schlechteste 10 % verwerfen"** nach FWHM klicken
5. **Statistikgraph** prüfen — noch verbleibende Ausreißer?
6. **Verwerfen übernehmen && Schließen** → in Siril stacken (der `rejected/`-Unterordner bleibt von jedem nachfolgenden `convert`/Stacking-Schritt ausgeschlossen, weil er eine Ebene unter deinem Lights-Ordner liegt)

**Zeit:** ~5 Minuten für 120 Bilder.

### Anwendungsfall 2: Wolkenbeeinflusste Session

**Szenario:** Wolken zogen während deiner Session durch. Einige Bilder sind teilweise bewölkt.

**Ablauf:**
1. Blink Comparator öffnen und Ordner wählen
2. **Statistikgraph**-Reiter, Checkbox **Hintergrund** aktivieren
3. Nach Spikes suchen — das sind die bewölkten Bilder
4. **Batch-Verwerfen**: Hintergrund > [Schwellwert aus dem Spike]
5. Auch **Sterne** prüfen — bewölkte Bilder haben weniger erkannte Sterne
6. Bei 3–5 FPS im Normal-Modus prüfen — Wolkenflecken wackeln sichtbar gegen das statische Sternfeld

### Anwendungsfall 3: Tracking-Problem-Diagnose

**Szenario:** Einige Bilder zeigen längliche Sterne. Du willst sie finden, entfernen und verstehen, wann das Problem auftrat.

**Ablauf:**
1. Blink Comparator öffnen
2. **Statistikgraph**, **Rundheit** aktivieren
3. Dips suchen — das sind Bilder mit Tracking-Fehlern
4. **Freigabeausdruck**: `Rundheit > 0,75`
5. **Nicht-passende verwerfen** entfernt alle Bilder mit länglichen Sternen
6. **Scatterplot** (FWHM vs Rundheit) prüfen — Ausreißer sind weit vom Cluster entfernt
7. Ausreißer-Punkte klicken, um Einzelbilder zu inspizieren
8. Konzentrieren sich Tracking-Fehler auf einen Zeitraum? → Periodischer Fehler deiner Montierung

### Anwendungsfall 4: Fokusdrift-Session

**Szenario:** Deine FWHM beginnt gut, steigt aber während der Session an, weil die Temperatur fällt und sich der Fokus verschiebt.

**Ablauf:**
1. Blink Comparator öffnen
2. **Statistikgraph** → FWHM zeigt eine Aufwärtsrampe
3. Der **Gleitmittelwert** (dicke Linie) zeigt den Trend klar
4. **Batch-Verwerfen**: FWHM > [dein Schwellwert, z. B. 4,5]
5. Oder **„Schlechteste 20 % verwerfen"** nach FWHM — entfernt automatisch die End-of-Session-Bilder
6. Für zukünftige Sessions: Autofocuser oder alle 30 Minuten refokussieren

### Anwendungsfall 5: Satelliten-Jagd

**Szenario:** Du fotografierst nahe dem Himmelsäquator, wo Satellitenspuren häufig sind.

**Ablauf:**
1. Blink Comparator öffnen
2. Im **Normal**-Modus bleiben
3. **Leertaste** zum Abspielen bei 3–5 FPS — Satellitenspuren blinken sichtbar von Bild zu Bild auf, weil die Sterne stationär bleiben, die Spurenpixel aber wandern
4. Wenn du eine Spur siehst, **B** drücken, um das Bild auszuschließen
5. Weiterspielen, um alle Spuren zu erwischen
6. Optional zum **Aggressive**-Autostretch-Preset wechseln, damit schwache Spuren deutlicher hervortreten

### Anwendungsfall 6: Datengetriebene Auswahl (PI-SubframeSelector-Ersatz)

**Szenario:** Du willst einen quantitativen, PixInsight-artigen Auswahlprozess basierend auf mehreren Kriterien.

**Ablauf:**
1. Sterndetektion ausführen, um alle Kennzahlen zu füllen
2. **Statistiktabelle**, aufsteigend nach **Gewicht** sortieren (schlechteste oben)
3. Die untersten 10–20 % prüfen — sehen sie wirklich schlechter aus?
4. **Freigabeausdruck** aufsetzen:
   ```
   FWHM < 4,0 UND Rundheit > 0,75 UND Hintergrund < 0,012 UND Sterne > 40
   ```
5. Vorschau zeigt, dass N Bilder verworfen würden
6. „Nicht-passende verwerfen" klicken
7. Im **Scatterplot** (FWHM vs Rundheit) prüfen — verbleibendes Cluster sollte eng sein
8. **CSV exportieren** fürs Archiv
9. Verwerfen übernehmen && Schließen

### Anwendungsfall 7: Vorher-Nachher-Vergleich

**Szenario:** Du willst prüfen, ob deine Bildauswahl tatsächlich den verbleibenden Satz verbessert hat.

**Ablauf:**
1. Nach dem Markieren die **Session-Zusammenfassung** im Close-Dialog notieren (mittlere FWHM, Anzahl)
2. **„Nur eingeschlossene Bilder"**-Checkbox in der Wiedergabe aktivieren und Leertaste drücken
3. Abspielen — die Animation sollte glatt laufen, ohne Blinken oder Artefakte
4. **Statistikgraph** prüfen — die roten Punkte (ausgeschlossen) sollten auf den Spikes liegen
5. Die verbleibende blaue Linie sollte gleichmäßiger sein
6. **GIF exportieren** der sauberen Sequenz fürs Beobachtungslog

### Anwendungsfall 8: Zweiter Durchgang / Neuauswahl

**Szenario:** Du hast den Blink Comparator einmal laufen lassen, Verwerfen angewendet und willst später einige Entscheidungen überdenken.

**Ablauf:**
1. Quellordner im Finder/Explorer öffnen und Bilder aus `rejected/` zurück in den Hauptordner ziehen.
2. Alte `rejected_frames.txt` löschen (oder belassen — der nächste Lauf überschreibt sie).
3. Blink Comparator auf demselben Ordner erneut starten. Er nimmt nur die oberste Ebene auf (die in `rejected/` bleiben dort).
4. Neue Auswahlen treffen und **Verwerfen übernehmen && Schließen** — eine neue `rejected_frames.txt` wird geschrieben, neu verworfene Bilder werden in `rejected/` verschoben, neben die, die du dort belassen hast.

---

## 13. Tastaturkürzel

### Wiedergabe

| Taste | Aktion |
|-------|--------|
| `Leertaste` | Play / Pause |
| `←` | Vorheriges Bild |
| `→` | Nächstes Bild |
| `Pos1` | Erstes Bild |
| `Ende` | Letztes Bild |
| `1`–`9` | FPS direkt setzen |
| `+` | Schneller (FPS erhöhen) |
| `-` | Langsamer (FPS verringern) |

`1`–`9` werden über `QMainWindow.keyPressEvent` verteilt (nicht über `QShortcut`), sodass Ziffern bei fokussierter Spinbox oder LineEdit wie gewohnt ins Widget gelangen und das FPS-Preset unterdrückt wird — mehrstellige Eingaben in Schwellwert-Spinboxen funktionieren normal. `Strg+Z` / `Strg+C` feuern überall.

### Bildmarkierung

| Taste | Aktion |
|-------|--------|
| `G` | Als gut markieren (einschließen) |
| `B` | Als schlecht markieren (ausschließen) |
| `Strg+Z` | Letzte Markierung rückgängig (einzeln oder Batch) |

### Anzeige

| Taste | Aktion |
|-------|--------|
| `Z` | Fit-in-Window (Zoom zurücksetzen) |
| `T` | Aktuelles Bild fixieren / A/B-Vergleich umschalten |
| `Strg+C` | Aktuelles Bild in Zwischenablage kopieren |

### Sonstiges

| Taste | Aktion |
|-------|--------|
| `Esc` | Fenster schließen (mit Anwenden/Verwerfen/Abbrechen-Dialog bei ausstehenden Änderungen) |

---

## 14. Tipps & Empfehlungen

### Allgemeiner Ablauf

1. **Mit Daten beginnen, dann visuell verifizieren.** Sortiere zuerst nach FWHM oder Gewicht, um schlechte Bilder numerisch zu identifizieren. Dann in den Viewer wechseln und bestätigen, dass sie wirklich schlecht aussehen.

2. **Nicht überverwerfen.** Mehr Bilder = weniger Rauschen im Stack. Verwirf nur Bilder, die klar defekt sind. Ein Bild mit FWHM 4,2, wenn dein bestes 3,0 hat, trägt immer noch Signal bei — behalte es, wenn es kein Ausreißer ist.

3. **Nutze das Gleitmittel.** Im Statistikgraph offenbart die dicke Trendlinie Muster (Fokusdrift, Wolken), die in der verrauschten Rohdatenlinie unsichtbar sind.

4. **Prüfe den Scatterplot.** FWHM vs Rundheit ist die einzelne informativste Kombination. Das Haupt-Cluster repräsentiert deine „normalen" Bilder. Ausreißer weit vom Cluster sind deine Verwerfens-Kandidaten.

5. **Blinken im Normal-Modus bei 3–5 FPS für Satelliten-Jagd.** Wechselnde Pixel springen dem Auge ins Gesicht — einen dedizierten „Difference"-Modus brauchst du nicht.

### Autostretch-Presets

6. **Default ist meist fein.** Conservative ist gut, wenn der Hintergrund schwache Nebel enthält, die du beim Defekt-Scan erhalten willst. Aggressive lässt bewölkte Bilder hervortreten. Linear zeigt, was der Sensor tatsächlich aufgezeichnet hat.

### Performance-Tipps

7. **Erster Lauf auf einem Ordner ist langsam, folgende Läufe sind schnell.** Das Skript cached Statistiken und Miniaturen. Bildnavigation ist nach dem Caching sofort.

8. **Große Sequenzen (500+ Bilder):** Das Laden der Statistiken kann eine Minute dauern. Geduld — es passiert nur einmal pro Session. Sterndetektion skaliert etwa mit der Bildanzahl.

9. **Wiedergabegeschwindigkeit:** Wenn die Wiedergabe bei hoher FPS stottert, Geschwindigkeit senken. Der Bild-Cache lädt im Voraus mit wiedergabe-aware Lookahead (`max(10, FPS × 2)`), aber sehr hohe FPS auf sehr großen Bildern können den einen Preload-Thread überrennen.

### Ordnerhygiene

10. **Halte deinen Lights-Ordner sauber.** Lösche alte `rejected/`-Unterordner oder `rejected_frames.txt`-Dateien, die du nicht mehr brauchst. Der Blink Comparator scannt nur eine Verzeichnisebene, aber dein Stacking-Skript ist vielleicht weniger vorsichtig.

11. **Die Temp-Sequenz ist flüchtig.** `svenesis_blink.fits` + `.seq` werden beim Schließen immer aufgeräumt. Falls ein früherer Lauf abgestürzt ist und sie hinterlassen hat, erkennt das der nächste Start und führt `close` + Cleanup vor `convert` aus.

---

## 15. Fehlerbehebung

### Ordner-Auswahl zeigt keine FITS-Dateien

**Ursache:** Du hast auf einen Ordner gezeigt, der keine `.fit/.fits/.fts`-Dateien auf oberster Ebene enthält (das Skript geht nicht tiefer, und komprimierte `.fz/.gz`-FITS werden nicht erkannt).
**Lösung:** In den tatsächlichen Lights-Ordner navigieren. Liegen deine Dateien in `session/lights/night1/`, wähle `night1/`, nicht `session/`. Sind die Frames fpack- oder gzip-komprimiert, vorher dekomprimieren (z. B. `funpack *.fz` oder `gunzip *.gz`).

### „destination already exists" beim Sequenzaufbau

**Ursache:** Ein früherer Lauf ist abgestürzt, ohne die Temp-Sequenz aufzuräumen.
**Lösung:** Das Skript führt jetzt `close` + Cleanup vor `convert` aus, also sollte einfach erneutes Ausführen klappen. Falls der Fehler manuell erscheint, `svenesis_blink.fits` und `svenesis_blink.seq` aus dem Ordner löschen und neu starten.

### FWHM / Rundheit / Sterne-Spalten sind leer

**Ursache:** Auf dieser Sequenz wurde keine Sterndetektion gestartet.
**Lösung:** Auf den gelben „Sterndetektion starten"-Banner klicken. Das führt `register svenesis_blink -2pass` aus, das alle Sternkennzahlen berechnet, ohne neue Dateien zu erzeugen.

### Sterndetektion gelaufen, aber Spalten bleiben leer

**Ursache:** Die Registrierung schrieb Daten in einen Kanal, den das Skript nicht prüfte (selten — das Skript prüft jetzt alle Kanäle und verwendet das Ergebnis wieder).
**Lösung:** Auf die neueste Skriptversion aktualisieren. Sie erkennt den Kanal auf Bild 0 automatisch und verwendet ihn für die gesamte Sequenz.

### Fortschrittsbalken friert während der Sterndetektion ein

**Ursache:** Der Post-Register-Rebind (globalen Stretch berechnen → Referenzbild laden) lief früher still auf dem Haupt-Thread. In v1.2.8 rücken diese Phasen den Fortschrittsbalken durch 30 % → 50 % mit `processEvents()`-Pumping voran.
**Lösung:** Auf v1.2.8 oder neuer aktualisieren. Wenn der Balken bei sehr großen Sequenzen trotzdem zu stehen scheint, eine Minute warten — jede Phase kann pro tausend Bildern legitim einige Sekunden brauchen.

### 1–9-Ziffern ändern Wiedergabegeschwindigkeit statt in eine Schwellwert-Spinbox zu gehen

**Ursache (vor 1.2.8):** Die 1–9-FPS-Presets waren als window-scope `QShortcut`s registriert, die Ziffern verschlangen, bevor sie das fokussierte Kind-Widget erreichen konnten.
**Lösung:** Auf v1.2.8 aktualisieren. Die Presets leben nun in `keyPressEvent` und feuern nur, wenn kein Kind-Widget die Taste absorbiert.

### Schriftart-Warnung: „Sans-serif"

**Meldung:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"…`
**Auswirkung:** Nur kosmetisch, keine Funktionsbeeinträchtigung.

### GIF-Export schlägt fehl

**Ursache:** Pillow ist nicht installiert.
**Lösung:** Im Terminal: `pip install Pillow` (oder über Sirils Python-Umgebung installieren).

### Wiedergabe ist langsam / stottert

**Ursache:** Große Bildabmessungen oder zu wenig Speicher für den Bild-Cache.
**Lösung:**
- Wiedergabegeschwindigkeit senken (3–5 FPS statt 30)
- Der Cache hält standardmäßig 80 Bilder — reicht für die meisten Sequenzen
- Andere speicherhungrige Anwendungen schließen

### Skript stürzt mit „'BlinkComparatorWindow' object has no attribute 'cache'" ab

**Ursache:** Signal-Reihenfolgen-Bug in früheren 1.2.x-Builds, bei dem die Anzeigemodus-Radios `idToggled` vor dem Cache-Aufbau emittierten.
**Lösung:** Behoben in v1.2.8. Auf aktuelle Version aktualisieren.

---

## 16. Häufige Fragen

**F: Ersetzt das PixInsights Blink + SubframeSelector?**
A: Für visuelle Inspektion und datengetriebene Bildauswahl ja — du bekommst eine sortierbare Statistiktabelle, Batch-Schwellwerte, Freigabeausdrücke, Scatterplot, Statistikgraph mit Gleitmittel und einen Miniatur-Filmstreifen. Was fehlt: PIs SNR/PSFSignalWeight-Proprietärmetriken und ein dedizierter „Difference"-Modus (Normal-Modus-Wiedergabe bei 3–5 FPS deckt dasselbe ab).

**F: Muss ich meine Sequenz vorher registrieren?**
A: Nein — das Skript baut sich über `convert -fitseq` seine eigene temporäre FITSEQ-Sequenz aus dem, worauf du es richtest. Willst du FWHM/Rundheit/Sterne-Kennzahlen, klickst du auf den „Sterndetektion starten"-Banner, der `register -2pass` ausführt.

**F: Wo sind meine verworfenen Bilder?**
A: Beim Schließen werden sie physisch in einen Unterordner `rejected/` neben deinen Quelldateien verschoben. Eine Klartext-`rejected_frames.txt`-Audit-Datei wird ebenfalls neben die Originale geschrieben. Um die Ablehnung rückgängig zu machen, die Datei aus `rejected/` zurück in den Quellordner ziehen.

**F: Modifiziert „Verwerfen übernehmen" meine FITS-Dateien?**
A: Nein. Behaltene Bilder werden gar nicht angefasst. Verworfene Bilder werden in einen `rejected/`-Unterordner *verschoben* (nicht umgeschrieben, nicht umbenannt) — jederzeit reversibel.

**F: Wie stark verbessert das Verwerfen den Stack?**
A: Hängt von deinen Daten ab. 5–10 % der schlechtesten zu entfernen verbessert den Stack meist spürbar — schärfere Sterne, weniger Hintergrund-Rauschen. Mehr als 20–30 % bringt oft abnehmenden Ertrag (du verlierst mehr Signal, als du an Qualität gewinnst).

**F: Was ist aus dem Difference-Anzeigemodus geworden?**
A: In v1.2.5 entfernt. Praktisch fängt die Wiedergabe bei 3–5 FPS im Normal-Modus mit global-verknüpftem Autostretch dieselben Artefakte (Satelliten, Wolken, Tracking-Sprünge) ein, weil das Auge an alles andockt, was sich ändert. Der Subtract-+-Absolute-+-Skalieren-+-Clip-Pfad des Difference-Modus bezahlte für Arbeit, die die Wiedergabe bereits visuell leistet.

**F: Was ist aus dem Linked/Independent-Stretch-Umschalter geworden?**
A: In v1.2.5 entfernt. Global-verknüpfter Autostretch ist jetzt der einzige Modus — sinnvoller Default für einen Blink Comparator, weil er die Helligkeitsunterschiede bewahrt, die bewölkte Bilder sichtbar machen. Für verschiedene Stretch-Geschmäcker gibt es das Autostretch-Preset-Dropdown (Conservative/Default/Aggressive/Linear).

**F: Kann ich ausgeschlossene Bilder wieder einschließen?**
A: Ja. Drücke **G** auf einem ausgeschlossenen Bild. Oder nutze **Strg+Z**, um die letzte Markierung (einzeln oder Batch) rückgängig zu machen. Nach dem Schließen einfach die Datei im Dateimanager aus `rejected/` zurückziehen.

**F: Warum zeigt die Gewichtsspalte 0 für alle Bilder?**
A: Gewicht braucht FWHM-, Rundheits-, Hintergrund- und Sterne-Daten. Wurde keine Sterndetektion ausgeführt, sind alle Eingaben 0, also ist das Gewicht 0. Erst Sterndetektion starten.

**F: Kann ich das für Planetenfotografie nutzen?**
A: Das Tool ist für Deep-Sky-Subframe-Auswahl konzipiert. Planetenfotografie (Lucky Imaging) nutzt andere Qualitätsmetriken und verarbeitet typischerweise tausende sehr kurze Belichtungen. Tools wie AutoStakkert oder Planetary System Stacker sind für Planetenaufnahmen besser geeignet.

---

## 17. Änderungen seit v1.2.3

Die letzte offiziell veröffentlichte Version war **v1.2.3**. Die folgende Übersicht fasst kompakt zusammen, was sich von dort bis zur aktuellen **v1.2.8** geändert hat — Einzeiler pro Release stehen im `CHANGELOG`-Block des Skripts.

- **v1.2.4 — Ordner-only-Workflow.** Das Skript fragt beim Start immer nach einem FITS-Ordner und baut sich daraus seine eigene temporäre `svenesis_blink`-Sequenz. Verworfene Bilder wandern in einen `rejected/`-Unterordner, begleitet von einer `rejected_frames.txt`-Audit-Datei. Neues Autostretch-Preset-Dropdown (Conservative / Default / Aggressive / Linear). Entfernt: ROI-Feature, Pro-Bild-Histogramm-Widget und der „aktuell geladene Sequenz"-Pfad.
- **v1.2.5 — Reduzierte Anzeigemodi.** Difference-Modus und `D`-Shortcut entfernt — die Wiedergabe bei 3–5 FPS im Normal-Modus fängt dieselben Artefakte ein. Linked-Stretch-Toggle entfernt; global verknüpfter Autostretch ist jetzt der einzige Modus.
- **v1.2.6 — Performance-Pass.** Thumbnails wiederverwenden das bereits gestreckte Bild des Haupt-Frame-Cache, `mtf()` läuft in-place, RGB-Autostretch ist ein einziger Durchlauf, und das Preload-Tempo richtet sich nach der FPS.
- **v1.2.7 — Markier-Responsiveness.** Schnelles G/B-Markieren bündelt Slider-/Scatter-/Graph-Refreshes über einen einzigen 150-ms-Timer; Filmstrip und Tabelle überspringen No-Op-Styling-Aufrufe. Außerdem: Absturz-Fix bei `mtf()`-Kwarg und automatische Bereinigung einer stehengebliebenen Temp-Sequenz nach einem Absturz.
- **v1.2.8 — Plattform-Politur & Stabilität.** UTF-8 für `rejected_frames.txt` und CSV-Export (behebt Windows-Pfade mit Nicht-ASCII-Zeichen). 1–9-FPS-Presets liegen jetzt in `keyPressEvent`, damit fokussierte Spinboxes Ziffern nativ entgegennehmen. Ordnerpfade mit Leerzeichen werden in Siril-Kommandos jetzt korrekt gequotet. Apply verschiebt die Dateien zuerst und schreibt die Audit-Liste erst danach — nur das, was wirklich bewegt wurde. Sterndetektion rebindet Caches/Stats und lässt den Fortschrittsbalken durch die Post-Register-Phasen laufen. View-State (Filter, Anzeigemodus, Graph-Metriken, Scatter-Achsen) wird jetzt sitzungsübergreifend gespeichert.

Beim Upgrade von **v1.2.3** in der Praxis: Zeig dem Skript deinen FITS-Ordner (statt vorher eine Sequenz in Siril zu laden) und erwarte, dass der Verwerfen-Flow einen `rejected/`-Unterordner plus `rejected_frames.txt` erzeugt, anstatt Sirils Inclusion-Flags in der Sequenz zu togglen.

---

## Credits

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die außerdem enthält:
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn du dieses Tool nützlich findest, unterstütze gerne die Entwicklung via [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
