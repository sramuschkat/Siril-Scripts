# Svenesis Image Advisor — Benutzeranleitung

**Version 1.3.1** | Siril-Python-Skript für Bilddiagnose & Workflow-Planung

> *Ein diagnostisches „Zweitmeinungs"-Werkzeug — analysiert Ihr gestacktes Bild, identifiziert Probleme und erstellt einen priorisierten Bearbeitungs-Workflow mit konkreten Siril-Befehlen.*

---

## Inhaltsverzeichnis

1. [Was ist der Image Advisor?](#1-was-ist-der-image-advisor)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Was wird analysiert](#6-was-wird-analysiert)
7. [Den Bericht verstehen](#7-den-bericht-verstehen)
8. [Schweregrade](#8-schweregrade)
9. [Der empfohlene Workflow](#9-der-empfohlene-workflow)
10. [Exportoptionen](#10-exportoptionen)
11. [Anwendungsfälle & Arbeitsabläufe](#11-anwendungsfälle--arbeitsabläufe)
12. [Intelligente Verhaltensweisen](#12-intelligente-verhaltensweisen)
13. [Tipps & Empfehlungen](#13-tipps--empfehlungen)
14. [Fehlerbehebung](#14-fehlerbehebung)
15. [Häufige Fragen](#15-häufige-fragen)

---

## 1. Was ist der Image Advisor?

Der **Svenesis Image Advisor** ist ein Siril-Python-Skript, das Ihr gestacktes, lineares (unbearbeitetes) Bild analysiert und eine priorisierte Liste empfohlener Bearbeitungsschritte erstellt — inklusive konkreter Siril-Befehle, vorgeschlagener Parameter und Begründungen für jede Empfehlung.

Betrachten Sie ihn als einen **Bearbeitungs-Coach**, der neben Ihnen sitzt. Er kombiniert:

- **Diagnostische Analyse** — Rauschen/SNR, Gradienten, Sternqualität, Kalibrierungsstatus, Farbbalance, Nebulosität, Clipping und mehr
- **Priorisierter Workflow** — sagt Ihnen genau, was Sie zuerst, zweitens, drittens tun sollen, mit spezifischen Siril-Befehlen
- **Kontextbewusste Beratung** — passt Empfehlungen an Ihren Bildtyp an (Breitband, Schmalband, Mono, OSC), Integrationszeit, Sternqualität und bereits durchgeführte Bearbeitung
- **Siril-Skript-Export** — erzeugt eine sofort ausführbare `.ssf`-Skriptdatei mit allen empfohlenen Befehlen

Der Image Advisor verändert Ihr Bild **nicht**. Er ist rein diagnostisch — er liest das Bild, analysiert es und teilt Ihnen mit, was er gefunden hat und was zu tun ist. Sie führen die Schritte selbst aus und behalten die volle Kontrolle.

---

## 2. Hintergrundwissen für Einsteiger

### Die Herausforderung der Bildbearbeitung

Sie haben Ihre Einzelaufnahmen aufgenommen, sie kalibriert (Darks, Flats, Biases), registriert und gestackt. Jetzt haben Sie ein einzelnes gestacktes Bild — und es sieht... dunkel, grau und unspektakulär aus. Das ist normal! Das Bild befindet sich in seinem **linearen** Zustand, was bedeutet, dass die Pixelwerte noch nicht transformiert wurden, um die feinen Details in den Daten sichtbar zu machen.

Die Herausforderung ist: **Was tun Sie als Nächstes?** Die Astrofotografie-Bearbeitung umfasst viele Schritte, und die Reihenfolge ist entscheidend. Machen Sie das Falsche zuerst, können Sie Ihre Daten dauerhaft beschädigen. Überspringen Sie einen Schritt, verschenken Sie Qualität.

Hier ist der typische lineare Bearbeitungs-Workflow:

```
Ränder beschneiden → Gradienten entfernen → Plate-Solve → Farbkalibrierung →
Grünrauschen entfernen → Entrauschen → Dekonvolution → Sterne entfernen →
STRETCHEN → Feinabstimmung → Sterne wieder einsetzen → Exportieren
```

Jeder Schritt hat spezifische Werkzeuge, Einstellungen und Bedingungen. Der Image Advisor automatisiert die Analyse und Entscheidungsfindung und sagt Ihnen, welche Schritte Ihr Bild benötigt und welche es überspringen kann.

### Was ist linear vs. gestretcht?

Dies ist das wichtigste Konzept in der Astrofotografie-Bearbeitung:

| Zustand | Bedeutung | Aussehen |
|---------|-----------|----------|
| **Linear** | Pixelwerte sind proportional zur Anzahl der empfangenen Photonen | Sehr dunkles, graues Bild — schwache Objekte unsichtbar |
| **Gestretcht (nicht-linear)** | Eine mathematische Transformation wurde angewendet, um schwache Details sichtbar zu machen | Sichtbare Nebel, Galaxien, Sterne vor dunklem Hintergrund |

**Die goldene Regel:** Erledigen Sie alles Mögliche, solange die Daten noch linear sind. Gradientenentfernung, Farbkalibrierung, Entrauschung und Dekonvolution funktionieren am besten mit linearen Daten. Sobald Sie stretchen, werden viele dieser Operationen weniger effektiv oder können Artefakte erzeugen.

Der Image Advisor prüft, ob Ihr Bild linear ist, indem er die FITS-Bearbeitungshistorie nach Stretch-Befehlen durchsucht (wie `ght`, `autostretch`, `mtf`, `asinh`, `clahe`). Falls er welche findet, warnt er Sie.

### Was ist SNR (Signal-Rausch-Verhältnis)?

**Signal** ist das Licht Ihres Zielobjekts (Nebel, Galaxie, Sterne). **Rauschen** ist zufällige Variation durch Photonenstatistik, Sensorauslesung, Dunkelstrom und Himmelshintergrund.

**SNR = Signal ÷ Rauschen.** Höher ist besser.

| SNR | Qualität | Bedeutung |
|-----|----------|-----------|
| > 10 | Ausgezeichnet | Reichhaltige Daten, aggressive Bearbeitung möglich, Dekonvolution funktioniert gut |
| 5–10 | Gut | Solide Daten, Standardbearbeitung, moderate Dekonvolution |
| 2–5 | Verrauscht | Begrenzte Daten, vorsichtige Bearbeitung nötig, Dekonvolution überspringen |
| < 2 | Photonenmangel | Sehr schwaches Ziel oder kurze Integrationszeit, starke Entrauschung nötig |

Der Image Advisor misst SNR mit der **MAD-Methode (Median Absolute Deviation)**, die robust gegen Ausreißer wie Sterne und kosmische Strahlung ist.

### Was ist FWHM?

**FWHM (Full Width at Half Maximum)** misst, wie „breit" Ihre Sterne in Pixeln sind (oder in Bogensekunden, wenn das Bild plate-solved ist).

| FWHM | Qualität | Typische Ursache |
|------|----------|------------------|
| < 2" | Ausgezeichnet | Gutes Seeing, präziser Fokus, gute Nachführung |
| 2–4" | Gut | Durchschnittliche Bedingungen, akzeptabel für die meisten Ziele |
| 4–6" | Weich | Schlechtes Seeing, leichte Defokussierung oder Wind |
| > 6" | Sehr weich | Erhebliche Defokussierung, schlechtes Seeing oder optische Probleme |

Enge, runde Sterne ermöglichen aggressivere Dekonvolution und ergeben schärfere Endbilder. Der Image Advisor prüft auch die **Elongation** (ovale Sterne durch Nachführfehler) und die **Feldkrümmung** (Sterne am Rand breiter als in der Mitte).

### Was ist die Nebulosität?

Der Prozentsatz der Pixel in Ihrem Bild, die ausgedehnte schwache Emission (Nebel, Galaxienarme) oberhalb des Hintergrundrauschens enthalten. Der Image Advisor nutzt dies, um zu entscheiden:

- **Ob sternlose Bearbeitung empfohlen wird** (StarNet) — nur sinnvoll bei signifikanter Nebulosität
- **Wie die Gradientenextraktion angepasst wird** — mehr Stützpunkte bei nebulosreichen Bildern, um zu vermeiden, dass der Nebel als Hintergrund modelliert wird

### Was ist Plate-Solving?

Plate-Solving bestimmt die exakten Himmelskoordinaten Ihres Bildes, indem das Sternmuster mit einem Katalog abgeglichen wird. Es ist wichtig, weil:

- **SPCC (Spectrophotometric Color Calibration)** Plate-Solving benötigt, um Sterne zur Farbreferenz zu identifizieren
- **FWHM in Bogensekunden gemessen werden kann** statt nur in Pixeln, was die Bewertung auflösungsunabhängig macht
- **Die Richtung der Lichtverschmutzung** aus den WCS-Daten berechnet werden kann

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweise |
|------------|---------------|----------|
| **Siril** | 1.4.1+ | Für volle Befehlsunterstützung (denoise -mod=, etc.) |
| **sirilpy** | Mitgeliefert | Im Lieferumfang von Siril 1.4+ enthalten |
| **numpy** | Beliebig aktuell | Wird vom Skript automatisch installiert |
| **PyQt6** | 6.x | Wird vom Skript automatisch installiert |

### Installation

1. Laden Sie `Svenesis-ImageAdvisor.py` vom [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Platzieren Sie die Datei in Ihrem Siril-Skriptverzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Bildbearbeitung → Skripte**.

Das Skript installiert fehlende Python-Abhängigkeiten (`numpy`, `PyQt6`) beim ersten Start automatisch.

---

## 4. Erste Schritte

### Schritt 1: Gestacktes Bild laden

Laden Sie Ihr gestacktes FITS-Bild in Siril. Für beste Ergebnisse:
- Verwenden Sie ein **lineares** (ungestretchtes) Bild — der Advisor ist für die lineare Bearbeitungsphase konzipiert
- Verwenden Sie ein **kalibriertes und gestacktes** Bild (kein einzelnes Subframe)
- Jeder Typ funktioniert: RGB-Breitband, Mono, Schmalband, Dual-Schmalband-OSC

### Schritt 2: Skript ausführen

Gehen Sie zu **Bildbearbeitung → Skripte → Svenesis Image Advisor**.

Das Skript öffnet sein Fenster und **beginnt sofort mit der Analyse** — kein Klick nötig. Sie sehen Statusmeldungen, während es drei Phasen durchläuft:

1. **Phase 1:** Bilddaten sammeln (Pixelstatistiken, FITS-Header, Gradientenanalyse, Sternerkennung)
2. **Phase 2:** Analysemodule ausführen (18+ diagnostische Prüfungen)
3. **Phase 3:** Bericht erstellen

Die gesamte Analyse dauert typischerweise 5–15 Sekunden.

### Schritt 3: Bericht lesen

Das rechte Panel füllt sich mit einem umfassenden HTML-Bericht, der enthält:
- Bildzusammenfassung und wichtige Statistiken
- Bearbeitungsstatus (linear? kalibriert?)
- Kanalweise Rauschtabelle (für Farbbilder)
- Hintergrund-Heatmap (8×8-Gradientenvisualisierung)
- Priorisierte Befunde mit Schweregraden
- Empfohlener Workflow mit Siril-Befehlen
- Nachbearbeitungs-Fahrplan (Stretching und darüber hinaus)

### Schritt 4: Dem Workflow folgen

Der Abschnitt mit dem empfohlenen Workflow listet Ihre Bearbeitungsschritte in Prioritätsreihenfolge auf. Jeder Schritt enthält:
- **Was** zu tun ist und **warum**
- **Schweregrad** (wie wichtig es ist)
- **Den genauen Siril-Befehl** zum Ausführen

Arbeiten Sie die Schritte von oben nach unten ab. Nach Änderungen klicken Sie auf **„Re-Analyse"**, um die Bewertung zu aktualisieren.

### Schritt 5: Exportieren (optional)

- **Bericht exportieren (.txt)** — speichert den vollständigen Bericht als Textdatei zur Dokumentation
- **Skript exportieren (.ssf)** — erzeugt eine Siril-Skriptdatei mit allen empfohlenen Befehlen, sofort ausführbar

---

## 5. Die Benutzeroberfläche

### Linkes Panel (Steuerungsbereich)

Die linke Seite (340px breit) enthält:

#### Titel
„Svenesis Image Advisor 1.3.0" in Blau.

#### Statusgruppe
- **Statusanzeige** — zeigt die aktuelle Analysephase („Phase 1: Bilddaten werden gesammelt...", „Analyse abgeschlossen.", etc.)
- **Fortschrittsbalken** — animiert während der Analyse, bei Abschluss zu 100% gefüllt

#### Bildinformationsgruppe
Nach der Analyse wird eine Kurzzusammenfassung angezeigt:
- Bildtyp (z.B. „OSC Broadband (RGB)")
- Abmessungen (z.B. „4656 × 3520 px")
- Bildanzahl und Sternanzahl
- Anzahl der empfohlenen Bearbeitungsschritte

#### Aktionsgruppe
- **Re-Analyse** — führt die vollständige Analyse am aktuellen Siril-Bild erneut durch (nützlich, nachdem Sie einen Bearbeitungsschritt angewendet haben)
- **Bericht exportieren (.txt)** — speichert den Bericht als Klartext
- **Skript exportieren (.ssf)** — erzeugt ein Siril-Skript mit empfohlenen Befehlen

#### Untere Schaltflächen
- **Buy me a Coffee** — Unterstützungslink
- **Hilfe** — öffnet einen detaillierten Hilfedialog mit 8 Abschnitten
- **Schließen** — beendet das Skript

### Rechtes Panel (Bericht)

Eine schreibgeschützte HTML-Anzeige mit dem vollständigen Analysebericht. Scrollbar, mit farbcodierten Abschnitten, Tabellen und der Hintergrund-Heatmap. Sie können Text aus dem Bericht auswählen und kopieren.

---

## 6. Was wird analysiert

Der Image Advisor führt 18+ Diagnosemodule über jeden Aspekt Ihres Bildes aus. Hier ist, was geprüft wird:

### Bildidentifikation
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Bildtyp** | OSC-Breitband, Mono, Schmalband, Dual-Schmalband, Luminanz — erkannt aus Filtername, Bayer-Muster und Kanalanzahl |
| **Abmessungen** | Breite, Höhe, Kanäle, Bittiefe — markiert nicht-astronomische Größen (Handy-/Bildschirmauflösungen) |
| **Stacking-Informationen** | Bildanzahl (STACKCNT), Gesamtintegrationszeit (LIVETIME), Belichtung pro Einzelaufnahme (EXPOSURE) |

### Bearbeitungsstatus
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Linearer Zustand** | Durchsucht FITS-Historie nach Stretch-Befehlen (ght, autostretch, mtf, asinh, clahe, etc.) |
| **Kalibrierung** | Erkennt Darks, Flats, Biases aus FITS-Historie-Schlüsselwörtern — unterscheidet „nicht angewendet" von „unbekannt", wenn keine Historie existiert |
| **Plate-Solve** | Prüft auf WCS-Schlüsselwörter oder `pltsolvd`-Flag im FITS-Header |

### Hintergrund & Gradienten
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Gradientenstärke** | Teilt das Bild in 8×8 Kacheln, wendet Sigma-Clipping auf jede Kachel an, berechnet die Streuung der Medianwerte als Prozentsatz |
| **Gradientenmuster** | Klassifiziert als: Vignettierung (dunkle Ecken, helle Mitte), linearer LP-Gradient (eine Seite heller), Ecken-Amp-Glow (eine Ecke hell) oder kein Muster |
| **Stacking-Ränder** | Scannt Kanten nach nahezu null Pixelzeilen/-spalten von geditherten/rotierten Stackings |

### Signalqualität
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Rauschen / SNR** | MAD-basierte Rauschschätzung aus den dunkelsten 25% der Pixel; SNR = Median / Rauschen |
| **Dynamikumfang** | Verhältnis von Spitzenwert (99,5. Perzentil) zum Rauschboden, ausgedrückt in Binärstufen |
| **Clipping** | Prozentsatz der Pixel nahe Schwarz (< 0,001) und nahe Weiß (> 0,999) |

### Farbe
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Kanalbalance** | R/G- und B/G-Medianverhältnisse — markiert starkes Ungleichgewicht |
| **Kanalweises Rauschen** | Individuelle R-, G-, B-Rauschniveaus — hebt den verrauschtesten Kanal hervor |
| **Grünrückstand** | Hinweis, nach der SPCC-Kalibrierung auf Grünrauschen zu prüfen |

### Sterne
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Sternanzahl** | Anzahl erkannter Sterne (über Sirils findstar) |
| **FWHM** | Durchschnittliche Sternbreite in Pixeln (und Bogensekunden, wenn plate-solved) |
| **Elongation** | Sternrundheit — mittleres fwhmmax/fwhmmin-Verhältnis (1,0 = perfekt rund) |
| **Feldvariation** | FWHM und Elongation in der Mitte vs. an den Rändern — erkennt Koma, Verkippung, Feldkrümmung |
| **Gesättigte Sterne** | Anzahl der Sterne mit abgeschnittenen/gesättigten Kernen |

### Inhaltsanalyse
| Prüfung | Was gemessen wird |
|---------|-------------------|
| **Nebulosität** | Prozentsatz der Pixel mit ausgedehnter Emission oberhalb des Rauschbodens |
| **Dekonvolutionseignung** | SNR-Schwellenwertprüfung — sind die Daten sauber genug für Richardson-Lucy? |
| **Plausibilitätsprüfung** | Markiert extremes Clipping ohne Signalinhalt (fehlerhafte Stacks, Handyfotos, Screenshots) |

---

## 7. Den Bericht verstehen

Der HTML-Bericht im rechten Panel enthält 8 Abschnitte:

### Bildzusammenfassung

Eine Tabelle mit den Grunddaten: Bildtyp, Größe, Kanäle, Stack-Anzahl, Belichtung, Auflösung, Filter und Plate-Solve-Status.

### Wichtige Statistiken

Die Kernmetriken auf einen Blick:

| Metrik | Beispiel | Was sie aussagt |
|--------|----------|-----------------|
| SNR-Schätzung (MAD) | 8,3 | Wie sauber Ihr Signal ist (höher = besser) |
| Hintergrundrauschen (σ) | 0,000142 | Absoluter Rauschboden |
| Gradientenstärke | 4,2% | Wie ungleichmäßig der Hintergrund ist |
| Dynamikumfang | 7,8 Stufen | Wie viel Signalbereich zur Verfügung steht |
| Nebulosität | 12,3% | Wie viel ausgedehnte Emission vorhanden ist |
| Erkannte Sterne | 2.847 | Sternanzahl von findstar |
| Mittlerer FWHM | 3,2 px (2,4") | Sternschärfe (kleiner = schärfer) |
| Mittlere Elongation | 1,08 | Sternrundheit (1,0 = perfekt) |

### Bearbeitungsstatus

Zeigt an, ob das Bild linear ist (grünes „Linear (gut)") oder gestretcht (rotes „GESTRETCHT" mit den erkannten Befehlen). Zeigt auch den Kalibrierungsstatus — Darks, Flats und Biases jeweils mit grünem Häkchen oder orangem Kreuz markiert. Wenn keine Bearbeitungshistorie im FITS-Header existiert, wird „Unbekannt" statt falscher Negativmeldungen angezeigt.

### Kanalstatistiken (nur bei Farbbildern)

Eine Tabelle, die für jeden R-, G-, B-Kanal den Medianwert, das Rauschniveau (σ) und das relative Rauschen (×) zeigt. Der verrauschteste Kanal wird fett und orange hervorgehoben — bei Breitbandbildern ist dies oft der Blaukanal.

### Hintergrund-Heatmap

Ein 8×8-ASCII-Raster, das die relative Helligkeit von 64 Kacheln über das Bild zeigt. Dunklere Kacheln erscheinen als Punkte oder niedrigere Zeichen; hellere Kacheln als höhere Zeichen. Unter dem Raster wird die **Musterklassifikation** des Gradienten angezeigt:

| Muster | Bedeutung |
|--------|-----------|
| **Vignettierung** | Mitte heller als alle vier Ecken — restliche optische Vignettierung |
| **Linear** | Eine Seite heller als die gegenüberliegende — Lichtverschmutzung oder Mondlicht |
| **Ecke (Amp-Glow)** | Eine Ecke deutlich heller — Verstärker-Glow der Kamera |
| *(kein Muster)* | Keine dominante Gradientenstruktur erkannt |

### Befunde

Das Herzstück des Berichts. Jeder Befund zeigt:
- **Schweregrad-Symbol** — [ℹ] Info, [✓] Gering, [⚠] Mittel, [✗] Kritisch
- **Farbcodierter Schweregrad** — Blau, Grün, Orange oder Rot
- **Kategorie** — welcher Aspekt analysiert wurde (Gradient, Rauschen, Sterne, etc.)
- **Befund** — was erkannt wurde, mit konkreten Zahlen
- **Empfehlung** — was dagegen zu tun ist
- **Siril-Befehl** — der genaue auszuführende Befehl (falls zutreffend)

### Empfohlener Workflow

Eine nummerierte, nach Priorität sortierte Liste umsetzbarer Schritte. Dies ist die „Machen Sie zuerst dies, dann das, dann jenes"-Anleitung. Jeder Schritt hat eine klare Beschreibung und den Siril-Befehl.

### Nachbearbeitungs-Fahrplan

Nach Abschluss des linearen Workflows und dem Stretching beschreibt dieser Abschnitt die verbleibenden Schritte:
- **Stretching** — Werkzeugempfehlung (VeraLux HMS) mit Dynamikumfang-Hinweisen und Warnungen zum Hintergrund-Pedestal
- **Feinabstimmung** — Kontrast, Farbsättigung, lokale Details (Revela, Curves, Vectra)
- **Stern-Rekomposition** — StarComposer (nur wenn sternlose Bearbeitung empfohlen wurde)
- **Signatur & Export** — finales TIFF/PNG/JPEG

---

## 8. Schweregrade

Jeder Befund wird mit einem von vier Schweregraden versehen:

| Symbol | Stufe | Farbe | Bedeutung |
|--------|-------|-------|-----------|
| ℹ | **Info** | Blau | Rein informativ — keine Aktion erforderlich |
| ✓ | **Gering** | Grün | Optionale Verbesserung — lohnenswert, aber nicht kritisch |
| ⚠ | **Mittel** | Orange | Empfohlene Aktion — deutliche Qualitätsverbesserung |
| ✗ | **Kritisch** | Rot | Ernstes Problem — muss vor dem Fortfahren behoben werden |

**Wie Schweregrade zu Aktionen führen:**

- **Info:** Lesen und verstehen, aber kein Bearbeitungsschritt nötig. Beispiel: „Sterne erkannt: 2.847" oder „Lineare Daten bestätigt."
- **Gering:** Ein optionaler Schritt, der die Qualität verbessert. Beispiel: „Grünrauschen kann nach SPCC sichtbar sein — prüfen und bei Bedarf entfernen."
- **Mittel:** Ein empfohlener Schritt, den Sie durchführen sollten. Beispiel: „Gradientenstärke 8,2% — führen Sie subsky 2 zur Hintergrundextraktion aus."
- **Kritisch:** Ein Problem, das behoben werden muss. Beispiel: „Bild ist bereits gestretcht — Analyse ist weniger genau, idealerweise das ungestretchte Original verwenden."

---

## 9. Der empfohlene Workflow

Der Image Advisor erstellt einen priorisierten Workflow basierend auf seinen Befunden. Die Prioritätsreihenfolge folgt der goldenen Regel: **Erledigen Sie alles Mögliche in der linearen Phase.**

### Reihenfolge der linearen Bearbeitung

| Priorität | Schritt | Bedingung | Typischer Befehl |
|-----------|---------|-----------|-------------------|
| 1 | **Stacking-Ränder beschneiden** | Dunkle Ränder erkannt | `boxselect X Y W H` dann `crop` |
| 2 | **Hintergrundextraktion** | Gradientenstärke > 2% | `subsky 1` (mild) / `subsky 2` (mittel) / `subsky 3` (stark) |
| 3 | **Plate-Solve** | Noch nicht plate-solved | `platesolve` |
| 4 | **Farbkalibrierung (SPCC)** | Farbbild, plate-solved | `spcc` |
| 5 | **Grünrauschen entfernen** | Nach SPCC bei Farbbildern | Prüfen und bei Bedarf anwenden |
| 6 | **Entrauschung** | Immer (angepasst nach SNR) | `denoise -mod=0.8` / `denoise -mod=1.0 -vst` |
| 7 | **Dekonvolution** | SNR > 5 und Sterne erkannt | `makepsf manual -gaussian -fwhm=X` dann `rl -loadpsf=psf.fits -iters=N` |
| 8 | **Sternlose Extraktion** | Nebulosität > 1% | `starnet [-stretch]` |

### Kontextbewusste Anpassungen

Der Workflow passt sich Ihrem spezifischen Bild an:

- **Gradient + Nebulosität:** `subsky` erhält `-samples=25`, wenn die Nebulosität > 5% beträgt (mehr Stützpunkte helfen dem Algorithmus, den Nebel nicht als Hintergrund zu modellieren)
- **Entrauschung vor Dekonvolution:** Die Entrauschung wird in der Priorität hochgestuft, wenn Dekonvolution empfohlen wird (sauberere Eingabe = bessere Dekonvolution)
- **StarNet Stretch-Flag:** Verwendet `-stretch` nur bei linearen Bildern (vermeidet doppeltes Stretching)
- **Dekonvolutions-Iterationen:** 10 bei SNR > 10, 5 bei grenzwertigem SNR (5–10)
- **Integrationszeit-bewusste Rauschhinweise:** Unterschiedliche Meldungen für kurze vs. lange Integrationen („Mehr Integrationszeit würde helfen" vs. „Lange Integration, aber verrauscht — schwaches Ziel")
- **Schmalband-Nebulosität:** Verwendet einen 3σ-Erkennungsboden statt 5σ bei Breitband, weil Schmalband-Emission diffuser ist

### Unterdrückter Workflow

Wenn das Bild die Plausibilitätsprüfungen nicht besteht (z.B. extremes Schwarz-Clipping ohne erkennbaren Inhalt), **unterdrückt das Skript alle Bearbeitungsempfehlungen** und zeigt nur die Warnung an. Dies verhindert, dass komplexe Bearbeitungsschritte für ein defektes oder nicht-astronomisches Bild vorgeschlagen werden.

---

## 10. Exportoptionen

### Bericht exportieren (.txt)

Speichert den vollständigen Analysebericht als Klartextdatei. Enthält alle gleichen Informationen wie der HTML-Bericht, aber formatiert für Texteditoren, Forenbeiträge oder E-Mail.

- **Standard-Dateiname:** `image_advisor_report.txt`
- **Kodierung:** UTF-8
- **Abschnitte:** Bildzusammenfassung, wichtige Statistiken, Bearbeitungsstatus, Kanalstatistiken, Heatmap, Befunde, Workflow, Fahrplan

### Skript exportieren (.ssf)

Erzeugt eine Siril-Skriptdatei mit allen empfohlenen Befehlen in der richtigen Reihenfolge.

**Funktionen:**
- **Automatisch generierter Header** mit Skriptversion und Zeitstempel
- **`requires 1.4.1`-Direktive** (stellt kompatible Siril-Version sicher)
- **Speicher-Checkpoints** zwischen größeren Schritten (z.B. `save image_after_crop.fits`)
- **Korrekte Befehlssyntax** für Siril 1.4.x

**Beispiel eines generierten Skripts:**
```
# Svenesis Image Advisor — Generated Workflow
# Generated by v1.3.0
requires 1.4.1

# Step 1: Crop stacking borders
boxselect 12 8 4632 3504
crop
save image_crop.fits

# Step 2: Background extraction
subsky 2 -samples=15
save image_subsky.fits

# Step 3: Plate-solve
platesolve
save image_platesolve.fits

# Step 4: Color calibration
spcc
save image_spcc.fits

# Step 5: Denoise
denoise -mod=0.8
save image_denoise.fits

# Step 6: Deconvolution
makepsf manual -gaussian -fwhm=3.2
rl -loadpsf=psf.fits -iters=10
save image_decon.fits

# Step 7: Star removal
starnet -stretch
save image_starless.fits
```

**Wichtig:** Das Skript ist ein Ausgangspunkt. Überprüfen Sie jeden Schritt vor dem Ausführen — einige Befehle benötigen möglicherweise Parameteranpassungen basierend auf visueller Inspektion.

---

## 11. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Erstmalige Bearbeitung (5 Minuten)

**Szenario:** Sie haben gerade Ihr erstes Bild in Siril gestackt und haben keine Ahnung, was als Nächstes zu tun ist.

**Ablauf:**
1. Laden Sie das gestackte Bild in Siril
2. Führen Sie den Image Advisor aus (**Bildbearbeitung → Skripte → Svenesis Image Advisor**)
3. Lesen Sie die **Bildzusammenfassung**, um zu verstehen, womit Sie arbeiten
4. Lesen Sie den **Bearbeitungsstatus** — bestätigen Sie, dass „Linear (gut)" angezeigt wird
5. Folgen Sie dem **empfohlenen Workflow** von oben nach unten und führen Sie jeden Siril-Befehl in der Konsole aus
6. Nach den linearen Schritten folgen Sie dem **Nachbearbeitungs-Fahrplan** für Stretching und Feinabstimmung

Der Advisor ersetzt stundenlange Tutorial-Videos durch konkrete, bildspezifische Anleitung.

### Anwendungsfall 2: Schneller Gesundheitscheck (2 Minuten)

**Szenario:** Sie haben schon viele Bilder bearbeitet, möchten aber eine schnelle Bewertung eines neuen Stacks.

**Ablauf:**
1. Laden Sie das gestackte Bild
2. Führen Sie den Image Advisor aus
3. Überfliegen Sie die Tabelle **Wichtige Statistiken** — prüfen Sie SNR, Gradient, FWHM, Nebulosität
4. Prüfen Sie die **Schweregrad-Symbole** bei den Befunden — alles Orange oder Rot erfordert Aufmerksamkeit
5. Beachten Sie alle **kritischen Warnungen** (gestretchte Daten, fehlende Kalibrierung, Plausibilitätsprobleme)
6. Fahren Sie mit Ihrem üblichen Workflow fort und berücksichtigen Sie die Hinweise

### Anwendungsfall 3: Weiche Sterne diagnostizieren

**Szenario:** Ihr fertiges Bild hat aufgeblähte, weiche Sterne und Sie möchten verstehen, warum.

**Ablauf:**
1. Laden Sie das gestackte (lineare) Bild
2. Führen Sie den Image Advisor aus
3. Prüfen Sie die **Sterne**-Befunde:
   - **Mittlerer FWHM** — ist er über 4" (Bogensekunden) oder 5 px? Das ist weich.
   - **Mitte vs. Rand FWHM** — wenn die Ränder deutlich schlechter sind, haben Sie Feldkrümmung oder Verkippung
   - **Elongation** — wenn > 1,3, sind die Sterne oval (Nachführproblem oder Koma)
   - **Elongation räumlich** — wenn die Ränder schlechter als die Mitte sind, ist es optisch (Koma/Verkippung), nicht die Nachführung
4. Der Advisor sagt Ihnen, was in der Bearbeitung korrigierbar ist (Dekonvolution kann bei leichter Weichheit helfen) und was nicht (Feldkrümmung erfordert mechanische Anpassung)

### Anwendungsfall 4: Schmalband-Bildbearbeitung

**Szenario:** Sie haben ein Ha (Wasserstoff-Alpha) Schmalbandbild gestackt und benötigen Bearbeitungshinweise.

**Ablauf:**
1. Laden Sie den Schmalband-Stack
2. Führen Sie den Image Advisor aus — er erkennt automatisch den Filter aus dem FITS-Header
3. Der Bericht zeigt „Narrowband (Mono)" oder „Narrowband (Colour)" als Bildtyp an
4. Anpassungen, die der Advisor für Schmalband vornimmt:
   - **Nebulosität-Erkennung** verwendet einen 3σ-Boden (empfindlicher als die 5σ bei Breitband)
   - **Farbkalibrierung (SPCC)** wird bei Mono-Schmalband übersprungen
   - **Gradientenextraktion** berücksichtigt die typischerweise geringere Gradientenstärke
5. Folgen Sie dem empfohlenen Workflow — er ist auf Schmalbanddaten zugeschnitten

### Anwendungsfall 5: Kalibrierungsqualität prüfen

**Szenario:** Sie möchten überprüfen, ob Ihre Darks, Flats und Biases korrekt angewendet wurden.

**Ablauf:**
1. Laden Sie das gestackte Bild
2. Führen Sie den Image Advisor aus
3. Prüfen Sie den Abschnitt **Bearbeitungsstatus**:
   - **Darks ✓ / ✗** — wurden Dark-Frames angewendet?
   - **Flats ✓ / ✗** — wurden Flat-Frames angewendet?
   - **Bias ✓ / ✗** — wurden Bias-/Offset-Frames angewendet?
   - **Unbekannt** — wenn keine Bearbeitungshistorie im FITS-Header existiert (häufig bei manchen Stacking-Programmen)
4. Wenn Flats fehlen, wird die **Gradientenanalyse** wahrscheinlich Vignettierung zeigen
5. Wenn Darks fehlen, kann das Rauschen erhöht sein und Amp-Glow kann in der Heatmap erscheinen

### Anwendungsfall 6: Ist meine Integrationszeit ausreichend?

**Szenario:** Sie haben 2 Stunden an Daten gestackt und fragen sich, ob Sie mehr benötigen.

**Ablauf:**
1. Laden Sie das gestackte Bild
2. Führen Sie den Image Advisor aus
3. Prüfen Sie den **SNR** in den wichtigen Statistiken:
   - **SNR > 10:** Ausgezeichnet — Sie haben reichlich Daten
   - **SNR 5–10:** Gut — Standardbearbeitung möglich, mehr Daten helfen immer
   - **SNR 2–5:** Verrauscht — mehr Integrationszeit würde das Ergebnis deutlich verbessern
   - **SNR < 2:** Photonenmangel — dieses Ziel braucht deutlich mehr Integrationszeit
4. Der Rausch-Befund setzt das Ergebnis in Bezug zu Ihrer Gesamtintegrationszeit:
   - Kurze Integration + niedriger SNR → „Mehr Integrationszeit würde helfen"
   - Lange Integration + niedriger SNR → „Dies ist ein schwaches Ziel — lange Belichtung, aber dennoch verrauscht"

### Anwendungsfall 7: Bearbeitungsskript generieren

**Szenario:** Sie möchten die empfohlenen Bearbeitungsschritte als automatisiertes Siril-Skript ausführen.

**Ablauf:**
1. Laden Sie das gestackte Bild
2. Führen Sie den Image Advisor aus
3. Überprüfen Sie den empfohlenen Workflow im Bericht
4. Klicken Sie auf **„Skript exportieren (.ssf)"**
5. Speichern Sie die Datei (Standard: `image_advisor_workflow.ssf`)
6. Führen Sie in Siril das Skript über **Bildbearbeitung → Skripte** oder die Kommandozeile aus
7. Das Skript enthält Speicher-Checkpoints zwischen den größeren Schritten, sodass Sie Zwischenergebnisse inspizieren können

**Hinweis:** Überprüfen Sie das generierte Skript immer vor dem Ausführen. Einige Schritte benötigen möglicherweise Parameteranpassungen basierend auf visueller Inspektion (z.B. Gradientenextraktionsgrad, Entrauschungs-Modulation).

### Anwendungsfall 8: Forum-Hilfeanfrage

**Szenario:** Sie kommen bei der Bearbeitung nicht weiter und möchten in einem Astrofotografie-Forum um Hilfe bitten.

**Ablauf:**
1. Laden Sie das gestackte Bild
2. Führen Sie den Image Advisor aus
3. Klicken Sie auf **„Bericht exportieren (.txt)"**
4. Fügen Sie den Bericht in Ihren Forenbeitrag ein
5. Forenmitglieder können genau sehen, was der Advisor gefunden hat: SNR, Gradient, Sternqualität, Kalibrierungsstatus und empfohlenen Workflow
6. Dies gibt Helfern ein vollständiges diagnostisches Bild, ohne dass sie Ihr Bild herunterladen müssen

### Anwendungsfall 9: Vorher/Nachher-Prüfung

**Szenario:** Sie haben die Hintergrundextraktion angewendet und möchten überprüfen, ob sie funktioniert hat.

**Ablauf:**
1. Klicken Sie nach dem Anwenden von `subsky` auf **„Re-Analyse"**
2. Vergleichen Sie die neue **Gradientenstärke** mit dem vorherigen Wert
3. Prüfen Sie, ob der Schweregrad des Gradienten-Befunds gesunken ist (z.B. von „Mittel" auf „Info")
4. Die Heatmap sollte ein gleichmäßigeres Muster zeigen
5. Fahren Sie mit dem nächsten Schritt im Workflow fort

---

## 12. Intelligente Verhaltensweisen

Der Image Advisor enthält mehrere intelligente Anpassungen, die über einfache Schwellenwertprüfungen hinausgehen:

### Nebulosität-bewusste Gradientenextraktion

Wenn der Advisor `subsky` zur Gradientenentfernung empfiehlt, prüft er den Nebulosität-Anteil:
- **Nebulosität > 5%:** Fügt `-samples=25` hinzu (mehr Stützpunkte helfen dem Algorithmus, den Nebel nicht als Hintergrund zu modellieren)
- **Nebulosität 1–5%:** Fügt `-samples=15` hinzu
- **Nebulosität < 1%:** Standard-Stützpunktanzahl

### Entrauschungs-Priorisierung vor Dekonvolution

Wenn Dekonvolution empfohlen wird (SNR > 5, Sterne erkannt), wird der Entrauschungsschritt in der Priorität hochgestuft. Dekonvolution verstärkt Rauschen, daher erzielt vorheriges Entrauschen bessere Ergebnisse.

### StarNet Stretch-Erkennung

Bei der Empfehlung von StarNet zur Sternentfernung:
- **Lineares Bild:** Verwendet `starnet -stretch` (StarNet benötigt gestretchte Daten, um korrekt zu arbeiten)
- **Bereits gestretcht:** Verwendet `starnet` ohne `-stretch` (vermeidet doppeltes Stretching)

### Integrationszeit-Kontext

Der Rauschhinweis passt sich an die verfügbare Datenmenge an:
- **SNR ≤ 5 + < 1 Stunde Integration:** „Mehr Integrationszeit würde helfen" — möglicherweise reichen die Daten noch nicht aus
- **SNR ≤ 5 + > 4 Stunden Integration:** „Lange Integration, aber dennoch verrauscht — wahrscheinlich ein schwaches Ziel" — das Problem ist die Zielhelligkeit, nicht die Integrationszeit

### Schmalband-Nebulosität-Erkennung

Für Schmalbandfilter (Ha, OIII, SII) sinkt der Nebulosität-Erkennungsboden von 5σ auf 3σ über dem Hintergrund. Schmalband-Emission ist oft diffuser und schwächer relativ zum Rauschen, sodass ein niedrigerer Schwellenwert sie korrekt erfasst.

### Hintergrund-Pedestal-Warnung

Bei Stretch-Empfehlungen prüft der Advisor den Hintergrund-Median:
- **> 15% des Gesamtbereichs:** Starke Warnung, den Schwarzpunkt sorgfältig zu setzen
- **> 8% des Gesamtbereichs:** Milde Warnung über erhöhten Hintergrund
- Dies verhindert den häufigen Fehler, mit hohem Hintergrund zu stretchen, was zu einem ausgewaschenen, grauen Himmel führt

### Workflow-Unterdrückung

Wenn das Bild die grundlegenden Plausibilitätsprüfungen nicht besteht (extremes Schwarz-Clipping ohne Sterne, kein Signal und keine Nebulosität), unterdrückt der Advisor alle Bearbeitungsempfehlungen. Stattdessen zeigt er nur die kritische Warnung an, die erklärt, was möglicherweise falsch ist (Screenshot, Handyfoto, fehlerhafter Stack, stark maskierter Export).

---

## 13. Tipps & Empfehlungen

### Wann den Advisor ausführen

1. **Führen Sie ihn auf Ihrem linearen Stack aus, vor jeder Bearbeitung.** Dies ist der ideale Zeitpunkt — der Advisor ist für diesen Moment konzipiert.

2. **Führen Sie ihn nach jedem wichtigen Schritt aus.** Klicken Sie nach der Gradientenextraktion, nach der Farbkalibrierung usw. auf „Re-Analyse", um jeden Schritt zu überprüfen.

3. **Führen Sie ihn auf einzelnen Subframes aus**, wenn Sie die Qualität eines Einzelbilds prüfen möchten (obwohl der Blink Comparator für den Vergleich mehrerer Bilder besser geeignet ist).

### Den Bericht effizient lesen

4. **Beginnen Sie mit den Schweregrad-Symbolen.** Suchen Sie nach Orange [⚠] und Rot [✗] — das sind die Probleme, die am meisten zählen.

5. **Vertrauen Sie der Workflow-Reihenfolge.** Das Prioritätssystem basiert auf der goldenen Regel (linear zuerst). Springen Sie nicht zur Dekonvolution, bevor die Gradienten extrahiert sind.

6. **Achten Sie auf „bereits gestretcht"-Warnungen.** Wenn Sie versehentlich ein gestretchtes Bild analysieren, können Gradient-, Rausch- und andere Messungen ungenau sein. Führen Sie die Analyse erneut mit der linearen Version durch.

### Praktische Workflow-Tipps

7. **Verwenden Sie das exportierte .ssf-Skript als Ausgangspunkt**, nicht als unumstößliche Wahrheit. Überprüfen Sie jeden Befehl und passen Sie Parameter an, wenn Ihre visuelle Inspektion andere Einstellungen nahelegt.

8. **Die Heatmap zeigt Gradientenmuster auf einen Blick.** Eine Schalenform = Vignettierung. Eine Neigung = LP. Eine helle Ecke = Amp-Glow. Dies zeigt Ihnen, welche Art der Extraktion anzuwenden ist.

9. **Die kanalweise Rauschtabelle zeigt, welcher Kanal Ihr Bild begrenzt.** Bei Breitband-Aufnahmen ist Blau oft am verrauschtesten. Bei Schmalband bestimmen Filter und Sensor-QE, welcher am schlechtesten ist.

10. **Prüfen Sie den Kalibrierungsstatus früh.** Wenn Darks/Flats/Biases als fehlend oder unbekannt angezeigt werden, korrigieren Sie Ihre Kalibrierung, bevor Sie Zeit in die Bearbeitung investieren.

11. **Überspringen Sie das Plate-Solving nicht.** Viele nachgelagerte Schritte (SPCC, FWHM in Bogensekunden, geografische LP-Richtung in anderen Werkzeugen) benötigen es. Der Advisor erinnert Sie daran.

12. **Der Nebulosität-Prozentsatz hilft bei der Entscheidung über sternlose Bearbeitung.** Wenn er < 1% ist, bringt StarNet nicht viel — Sie fotografieren ein Sternfeld. Wenn > 5%, wird sternlose Bearbeitung dringend empfohlen.

---

## 14. Fehlerbehebung

### Fehler „Kein Bild geladen"

**Ursache:** Kein Bild ist in Siril geöffnet.
**Lösung:** Laden Sie ein FITS-Bild, bevor Sie das Skript ausführen.

### Fehler „Verbindung abgelaufen"

**Ursache:** Die sirilpy-Verbindung zu Siril ist abgelaufen, normalerweise weil Siril beschäftigt ist.
**Lösung:** Warten Sie, bis Siril die aktuelle Operation abgeschlossen hat, und versuchen Sie es erneut.

### Analyse dauert lange

**Ursache:** Die Sternerkennung (findstar) kann bei sehr großen Bildern oder Bildern mit Tausenden von Sternen langsam sein.
**Lösung:** Das ist normal — der Fortschrittsbalken zeigt Aktivität an. Die Sternerkennung ist die langsamste Phase.

### Warnung „Bereits gestretcht", obwohl Bild linear ist

**Ursache:** Das Skript hat Stretch-bezogene Schlüsselwörter in der FITS-Bearbeitungshistorie erkannt. Manche Software schreibt Historie-Einträge, die Fehlalarme auslösen.
**Lösung:** Wenn Sie sicher sind, dass das Bild linear ist, können Sie diese Warnung ignorieren. Die Analyse ist trotzdem gültig — die Warnung ist eine Vorsichtsmaßnahme.

### Kalibrierungsstatus „Unbekannt"

**Ursache:** Die FITS-Datei hat keine Einträge in der Bearbeitungshistorie. Dies geschieht bei mancher Stacking-Software oder wenn die Historie nicht in die Header geschrieben wird.
**Lösung:** Dies ist kein Fehler — es bedeutet, dass der Advisor die Kalibrierung nicht aus der Datei verifizieren kann. Wenn Sie wissen, dass Sie Darks/Flats/Biases angewendet haben, fahren Sie normal fort.

### Bericht zeigt keine Sterne

**Ursache:** Sternerkennung fehlgeschlagen — mögliche Gründe: das Bild ist zu dunkel, stark abgeschnitten oder kein astronomischer Inhalt.
**Lösung:** Prüfen Sie, ob das Bild korrekt in Siril geladen ist. Bei einem Schmalbandbild mit sehr wenigen Sternen kann dies normal sein.

### Exportiertes Skript schlägt in Siril fehl

**Ursache:** Das Skript erfordert Siril 1.4.1+ (angegeben durch die `requires`-Direktive). Ältere Versionen unterstützen möglicherweise nicht alle Befehle.
**Lösung:** Aktualisieren Sie Siril auf 1.4.1 oder neuer.

### Warnung „Extremes Schwarz-Clipping"

**Ursache:** Mehr als 50% der Pixel liegen nahe Null, und es wurden keine Sterne oder Signal erkannt. Der Advisor vermutet, dass es sich nicht um ein normales astronomisches Bild handelt.
**Lösung:** Prüfen Sie, ob:
- Das Bild ein Screenshot oder Handyfoto ist (kein FITS-Stack)
- Das Stacking ein größtenteils leeres Ergebnis erzeugt hat (Ausrichtungsproblem)
- Das Bild stark beschnitten ist mit großen schwarzen Rändern
- Wenn das Bild legitim, aber ungewöhnlich ist, kann der Advisor übervorsichtig sein — der lineare Hintergrund eines gut kalibrierten Stacks liegt natürlich nahe Null (sollte aber dennoch erkennbare Sterne haben)

---

## 15. Häufige Fragen

**F: Verändert der Image Advisor mein Bild?**
A: Nein — er ist rein diagnostisch. Er liest das Bild, analysiert es und erstellt Empfehlungen. Sie führen die Bearbeitungsschritte selbst über Sirils Konsole oder das exportierte Skript aus.

**F: Sollte ich ihn vor oder nach dem Stacking ausführen?**
A: Nach dem Stacking. Der Advisor ist für gestackte Bilder in ihrem linearen Zustand konzipiert. Für die Qualitätsbewertung einzelner Subframes verwenden Sie stattdessen den Svenesis Blink Comparator.

**F: Kann ich ihn auf gestretchten Bildern verwenden?**
A: Ja, aber die Ergebnisse werden weniger genau sein. Der Advisor erkennt den gestretchten Zustand und warnt Sie. Gradient-, Rausch- und Dynamikumfangsmessungen sind bei linearen Daten am aussagekräftigsten.

**F: Was ist der Unterschied zwischen diesem und dem Gradient Analyzer?**
A: Der **Image Advisor** ist ein breites Diagnose-Werkzeug, das alles prüft (Rauschen, Gradienten, Sterne, Kalibrierung, Farbe usw.) und einen vollständigen Bearbeitungs-Workflow erstellt. Der **Gradient Analyzer** ist ein Tiefenanalyse-Spezialist, der sich ausschließlich auf Hintergrundgradienten konzentriert, mit 9 Visualisierungs-Tabs, 30+ gradientenspezifischen Metriken und detaillierter Anleitung zur Gradientenextraktion. Verwenden Sie den Advisor für eine Gesamtbewertung; verwenden Sie den Gradient Analyzer, wenn Sie detaillierte Gradientendiagnosen benötigen.

**F: Warum empfiehlt er Plate-Solving? Ich möchte nur mein Bild bearbeiten.**
A: Plate-Solving ermöglicht SPCC (genaue Farbkalibrierung) und erlaubt die Messung des FWHM in Bogensekunden (auflösungsunabhängig). Es dauert Sekunden und verbessert die nachgelagerte Bearbeitung erheblich. Der Advisor empfiehlt es nachdrücklich.

**F: Kann ich das exportierte .ssf-Skript automatisch ausführen?**
A: Ja — gehen Sie in Siril zu **Bildbearbeitung → Skripte** und wählen Sie das exportierte Skript, oder verwenden Sie die Kommandozeile. Überprüfen Sie das Skript jedoch vorher. Einige Schritte (wie Gradientenextraktionsgrad oder Entrauschungs-Modulation) profitieren möglicherweise von visueller Inspektion und Parameteranpassung.

**F: Was misst die „Nebulosität" tatsächlich?**
A: Sie zählt Pixel, die oberhalb des Hintergrundrauschbodens, aber unterhalb der Sternhelligkeitsschwelle liegen. Diese Pixel mittlerer Helligkeit repräsentieren ausgedehnte Emission — Nebel, Galaxienarme, Reflexionsnebel. Ein hoher Prozentsatz (> 5%) bedeutet signifikante ausgedehnte Objekte; ein niedriger Prozentsatz (< 1%) bedeutet, dass Sie hauptsächlich Sterne fotografieren.

**F: Warum ist der Blaukanal immer am verrauschtesten?**
A: Bei den meisten Kamerasensoren haben die blauen Photosites eine niedrigere Quanteneffizienz — sie wandeln weniger Photonen in Signal um. Kombiniert mit der Tatsache, dass der Nachthimmelshintergrund oft wärmer ist (rötlich durch Lichtverschmutzung), empfängt Blau das wenigste Signal und das meiste relative Rauschen. Das ist normal und zu erwarten.

**F: Kann ich ihn auf Mono-Schmalbanddaten anwenden?**
A: Ja. Der Advisor erkennt automatisch Mono-Schmalband aus dem FITS-Filter-Schlüsselwort. Er passt den Nebulosität-Schwellenwert an, überspringt farbspezifische Empfehlungen (SPCC, Grünentfernung) und passt den Workflow für die Schmalbandbearbeitung an.

**F: Welche Siril-Version brauche ich?**
A: Siril 1.4.1 oder neuer für volle Funktionalität. Die exportierten Skripte enthalten eine `requires 1.4.1`-Direktive. Ältere Versionen unterstützen möglicherweise Befehle wie `denoise -mod=` oder neuere `rl`-Syntax nicht.

**F: Wie genau ist die SNR-Schätzung?**
A: Der MAD-basierte SNR ist robust und zuverlässig für den Vergleich von Bildern, aber es ist eine Schätzung — er misst das Hintergrund-SNR, nicht das Ziel-SNR. Das tatsächliche Signal Ihres Zielobjekts (Nebel, Galaxie) kann stärker oder schwächer sein, als die hintergrundbasierte Messung nahelegt. Verwenden Sie ihn als relativen Richtwert, nicht als absolute Zahl.

---

## Danksagung

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die auch enthält:
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn Sie dieses Werkzeug nützlich finden, unterstützen Sie die Entwicklung gerne über [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
