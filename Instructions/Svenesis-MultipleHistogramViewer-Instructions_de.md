# Svenesis Multiple Histogram Viewer — Benutzeranleitung

**Version 1.1.0** | Siril Python-Skript für Histogramm-Vergleich & Bildinspektion

> *Histogramme und Bilder nebeneinander vergleichen — betrachten Sie Ihre linearen, automatisch gestretchten und manuell gestretchten Bilder gemeinsam mit interaktiver Pixelinspektion.*

---

## Inhaltsverzeichnis

1. [Was ist der Multiple Histogram Viewer?](#1-was-ist-der-multiple-histogram-viewer)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Die vier Spalten](#6-die-vier-spalten)
7. [Histogramm-Anzeige](#7-histogramm-anzeige)
8. [3D-Oberflächendiagramm](#8-3d-oberflächendiagramm)
9. [Kanalauswahl](#9-kanalauswahl)
10. [Datenmodi (Linear / Logarithmisch)](#10-datenmodi-linear--logarithmisch)
11. [Bildzoom & Navigation](#11-bildzoom--navigation)
12. [Interaktive Pixelinspektion](#12-interaktive-pixelinspektion)
13. [Statistik-Panel](#13-statistik-panel)
14. [Anwendungsfälle & Arbeitsabläufe](#14-anwendungsfälle--arbeitsabläufe)
15. [Tipps & Empfehlungen](#15-tipps--empfehlungen)
16. [Fehlerbehebung](#16-fehlerbehebung)
17. [Häufige Fragen](#17-häufige-fragen)

---

## 1. Was ist der Multiple Histogram Viewer?

Der **Svenesis Multiple Histogram Viewer** ist ein Siril Python-Skript, das das Histogramm Ihres Bildes zusammen mit dem Bild selbst in bis zu vier nebeneinander angeordneten Spalten zum direkten Vergleich anzeigt. Es liest das aktuelle lineare Bild aus Siril, führt einen automatischen Stretch durch und ermöglicht das Laden von bis zu zwei zusätzlichen gestretchten FITS-Dateien zum Vergleich.

Stellen Sie sich das Werkzeug als eine **visuelle Vergleichswerkbank** vor. Es kombiniert:

- **Nebeneinander-Darstellung** — betrachten Sie Ihr lineares Bild, die automatisch gestretchte Version und bis zu zwei manuell gestretchte Versionen gleichzeitig
- **Kanal-Histogramme** — zeigen Sie RGB (Luminanz), R, G, B und L-Kanäle einzeln oder überlagert an
- **3D-Oberflächendiagramme** — visualisieren Sie Ihr Bild als 3D-Höhenkarte, bei der die Pixelhelligkeit die Erhebung darstellt
- **Interaktive Pixelinspektion** — klicken Sie auf eine beliebige Stelle im Bild, um die exakten Pixelwerte in ADU zu sehen und die Position im Histogramm zu markieren
- **Umfassende Statistiken** — Min, Max, Mittelwert, Median, Standardabweichung, IQR, MAD, Perzentile und Clipping-Prozentsätze

Das Werkzeug arbeitet rein lesend — es verändert Ihr Bild nicht. Es hilft Ihnen, Ihre Daten zu verstehen und verschiedene Stretch-Ergebnisse zu vergleichen.

---

## 2. Hintergrundwissen für Einsteiger

### Was ist ein Histogramm?

Ein Histogramm ist ein Diagramm, das zeigt, **wie viele Pixel in Ihrem Bild jeden Helligkeitswert haben**. Die horizontale Achse (X) stellt die Pixelhelligkeit von Schwarz (links) bis Weiß (rechts) dar. Die vertikale Achse (Y) zeigt, wie viele Pixel diesen Helligkeitswert haben.

In der Astrofotografie sind Histogramme essentiell für das Verständnis Ihrer Daten:

| Histogrammform | Bedeutung |
|----------------|-----------|
| **Hohe Spitze ganz links** | Die meisten Pixel sind sehr dunkel — das ist normal für ein lineares (ungestretchtes) Bild |
| **Glatte Glockenkurve in der Mitte** | Gut gestretchtes Bild mit gutem Tonwertumfang |
| **Spitze am rechten Rand** | Überbelichtete Lichter — einige Sterne oder helle Bereiche haben Detail verloren |
| **Spitze am linken Rand** | Abgeschnittene Schatten — einige dunkle Bereiche haben Detail verloren |
| **Breite, ausgedehnte Kurve** | Guter Dynamikumfang — viele Tonwertdetails zur Bearbeitung |
| **Schmale, komprimierte Kurve** | Geringer Dynamikumfang — begrenzter Tonwertumfang |

### Was ist ADU?

**ADU (Analog-to-Digital Units)** ist der rohe numerische Wert, den Ihr Kamerasensor für jedes Pixel aufzeichnet. Er repräsentiert die Helligkeit dieses Pixels in den nativen Einheiten der Kamera.

| Kamera-Bittiefe | ADU-Bereich | Bedeutung |
|-----------------|-------------|-----------|
| 8-bit | 0–255 | 256 mögliche Helligkeitsstufen (JPEG, Webcam) |
| 14-bit | 0–16.383 | 16.384 Stufen (die meisten modernen Astrokameras) |
| 16-bit | 0–65.535 | 65.536 Stufen (gängiges FITS-Format, höchste Präzision) |

Der Histogram Viewer zeigt Pixelwerte in ADU, damit Sie die tatsächlichen Zahlen sehen können, die Ihre Kamera aufgezeichnet hat. Die X-Achse reicht von 0 bis zum maximalen ADU-Wert Ihres Bildes.

### Was bedeutet Linear vs. Gestretcht?

Ein **lineares** Bild ist eines, bei dem die Pixelwerte direkt proportional zur Anzahl der empfangenen Photonen sind. Dies ist die Rohausgabe von Kalibrierung und Stacking — es sieht sehr dunkel aus, weil die meisten Details in die unteren wenigen Prozent des Helligkeitsbereichs komprimiert sind.

Ein **gestretchtes** Bild wurde mathematisch transformiert, um die schwachen Details sichtbar zu machen. Die Transformation dehnt die Schatten aus und komprimiert gleichzeitig die Lichter, wodurch Nebel und schwache Strukturen sichtbar werden.

| Zustand | Histogrammform | Bilderscheinung |
|---------|----------------|-----------------|
| **Linear** | Hohe Spitze ganz links, fast nichts anderes | Sehr dunkel, grau, detaillos |
| **Gestretcht** | Breitere Kurve, Spitze nach rechts verschoben | Sichtbare Nebel, Sterne, Hintergrund |

Der Histogram Viewer zeigt beide Versionen nebeneinander, damit Sie genau sehen können, wie der Stretch die Daten transformiert.

### Was ist Autostretch?

**Autostretch** ist ein schneller, automatischer Stretch, der das 2. Perzentil (dunkler Referenzpunkt) auf Schwarz und das 98. Perzentil (heller Referenzpunkt) auf Weiß abbildet. Es handelt sich um eine einfache perzentilbasierte Neuzuordnung:

```
stretched_value = (original_value - P2) / (P98 - P2)
```

Dies ist nicht dasselbe wie Sirils GHT- oder MTF-Stretches — es ist eine lineare Neuzuordnung zur schnellen Visualisierung. Der Histogram Viewer wendet dies automatisch auf Ihr lineares Bild an, damit Sie sehen können, was in den Daten steckt.

### Was ist ein 3D-Oberflächendiagramm?

Anstatt Ihr Bild flach zu betrachten, behandelt ein 3D-Oberflächendiagramm die Helligkeit jedes Pixels als **Höhe**. Helle Bereiche werden zu Gipfeln; dunkle Bereiche werden zu Tälern. Dies macht Gradienten, Vignettierung und Helligkeitsmuster sofort sichtbar:

- **Eine geneigte Ebene** = Gradient (Lichtverschmutzung von einer Seite)
- **Eine Schalenform** = Vignettierung (dunkle Ecken, helle Mitte)
- **Scharfe Spitzen** = helle Sterne
- **Sanftes Plateau** = Nebulosität

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweise |
|------------|---------------|----------|
| **Siril** | 1.4.0+ | Python-Skriptunterstützung muss aktiviert sein |
| **sirilpy** | Mitgeliefert | Wird mit Siril 1.4+ ausgeliefert |
| **numpy** | Beliebig aktuell | Wird vom Skript automatisch installiert |
| **PyQt6** | 6.x | Wird vom Skript automatisch installiert |
| **Pillow** | Beliebig aktuell | Automatisch installiert; wird für hochwertige Bildskalierung verwendet |
| **astropy** | Beliebig aktuell | Automatisch installiert; wird zum Lesen von FITS-Dateien verwendet (einschließlich komprimierter .fz/.gz) |
| **matplotlib** | 3.x | Automatisch installiert; wird für 3D-Oberflächendiagramme verwendet |

### Installation

1. Laden Sie `Svenesis-MultipleHistogramViewer.py` aus dem [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Legen Sie die Datei in Ihr Siril-Skriptverzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Verarbeitung → Skripte**.

Das Skript installiert fehlende Python-Abhängigkeiten beim ersten Start automatisch.

---

## 4. Erste Schritte

### Schritt 1: Ein Bild in Siril laden

Laden Sie ein beliebiges FITS-Bild in Siril. Der Histogram Viewer ist für **lineare** (ungestretchte) gestackte Bilder konzipiert, funktioniert aber mit jedem FITS-Bild.

### Schritt 2: Das Skript ausführen

Gehen Sie zu **Verarbeitung → Skripte → Svenesis Multiple Histogram Viewer**.

Das Skript öffnet sein Fenster und lädt sofort das aktuelle Bild aus Siril. Sie sehen zwei Spalten:

- **Linear** — Ihre ursprünglichen Bilddaten (können sehr dunkel erscheinen)
- **Auto-Stretched** — dieselben Daten mit einem perzentilbasierten Autostretch zur besseren Sichtbarkeit

Jede Spalte zeigt das Bild, sein Histogramm (oder 3D-Oberflächendiagramm) und Statistiken.

### Schritt 3: Die Daten erkunden

- **Kanäle wechseln** — verwenden Sie die Kontrollkästchen (Histogramm) oder Optionsfelder (3D-Diagramm), um einzelne R, G, B-Kanäle oder die Luminanz anzuzeigen
- **In den Log-Modus wechseln** — schalten Sie „Logarithmisch" um, um die schwachen Ausläufer des Histogramms zu sehen
- **Auf das Bild klicken** — klicken Sie auf ein beliebiges Pixel, um seinen exakten ADU-Wert zu sehen und die Position im Histogramm zu markieren
- **Hineinzoomen** — verwenden Sie die Zoom-Schaltflächen (-, Einpassen, 1:1, +), um Details zu untersuchen

### Schritt 4: Vergleichsbilder laden (Optional)

Um verschiedene Stretch-Ergebnisse zu vergleichen:

1. Klicken Sie auf **„Load stretched FITS 1"** und wählen Sie eine gestretchte Version desselben Bildes
2. Eine dritte Spalte erscheint mit diesem Bild, seinem Histogramm und seinen Statistiken
3. Optional können Sie ein zweites gestretchtes FITS über **„Load stretched FITS 2"** für eine vierte Spalte laden

Jetzt können Sie alle Versionen nebeneinander sehen — linear, automatisch gestretcht und Ihre eigenen Stretches.

---

## 5. Die Benutzeroberfläche

### Linkes Panel (Steuerungsbereich)

Die linke Seite (320px breit) enthält alle Steuerungselemente:

#### Titel
„Svenesis Multiple Histogram Viewer 1.0.1" in Blau.

#### Ansichtsgruppe (Optionsfelder)
- **Histogram** — zeigt das 2D-Histogramm unter jedem Bild (Standard)
- **3D Surface Plot** — zeigt eine 3D-Höhenkarten-Visualisierung unter jedem Bild

#### Datenmodus-Gruppe (Optionsfelder)
- **Normal** — lineare Y-Achse für Histogramme, lineare Z-Achse für 3D-Diagramme (Standard)
- **Logarithmic** — log₁₀(Anzahl + 1) für Histogramme, log₁₀(ADU + 1) für 3D-Diagramme

#### Histogramm-Kanäle-Gruppe (Kontrollkästchen)
Steuert, welche Kanäle im 2D-Histogramm angezeigt werden:
- **RGB** — kombinierte Luminanz (Rec.709: 0.2126R + 0.7152G + 0.0722B), dargestellt als gefüllte weiße Fläche
- **R** — Rotkanal, dargestellt als rote Linie
- **G** — Grünkanal, dargestellt als grüne Linie
- **B** — Blaukanal, dargestellt als blaue Linie
- **L** — Luminanz (gleiche Rec.709-Formel), dargestellt als gelbe Linie

Alle Kanäle außer L sind standardmäßig aktiviert. Mehrere Kanäle können gleichzeitig angezeigt werden.

#### 3D-Diagramm-Kanäle-Gruppe (Optionsfelder)
Wählt aus, welcher Kanal die Z-Achse (Höhe) des 3D-Oberflächendiagramms bestimmt:
- **RGB** — Luminanz (Standard)
- **R**, **G**, **B** — einzelne Kanäle
- **L** — Luminanz

Im 3D-Modus kann jeweils nur ein Kanal angezeigt werden (Optionsfelder, keine Kontrollkästchen).

#### Bildgruppe (Schaltflächen)
- **Refresh from Siril** — lädt das aktuelle Bild aus Siril neu (nützlich nach Verarbeitungsschritten)
- **Load linear FITS...** — öffnet einen Dateidialog zum Laden einer linearen FITS-Datei von der Festplatte (anstatt aus Siril)

#### Gestretche-Vergleiche-Gruppe
Zwei Plätze zum Laden externer gestretchter FITS-Dateien:
- **Load stretched FITS 1** / **Load stretched FITS 2** — öffnet einen Dateidialog zum Laden eines gestretchten Bildes
- **Clear** — entfernt das geladene Vergleichsbild und blendet seine Spalte aus

Unterstützte Formate: `.fit`, `.fits`, `.fts`, `.fz` (komprimiert), `.gz` (gzip-komprimiert).

#### Untere Schaltflächen
- **Buy me a Coffee** — Unterstützungs-Link
- **Help** — ausführlicher Hilfedialog mit 13 Abschnitten
- **Close** — beendet das Skript

### Rechtes Panel (Spalten)

Die rechte Seite zeigt 2–4 nebeneinander angeordnete Spalten (siehe Abschnitt 6).

---

## 6. Die vier Spalten

Das rechte Panel enthält bis zu vier Spalten, die jeweils eine Version des Bildes zeigen:

### Spalte 1: Linear

Immer sichtbar. Zeigt Ihre **ursprünglichen linearen Bilddaten** — Pixelwerte genau so, wie sie aus Kalibrierung und Stacking hervorgegangen sind.

Das Bild kann sehr dunkel erscheinen, da lineare Daten den Großteil ihrer Informationen nahe dem unteren Ende des Helligkeitsbereichs komprimiert haben. Dies ist normal.

### Spalte 2: Auto-Stretched

Immer sichtbar. Zeigt **dieselben linearen Daten mit einem automatischen Perzentil-Stretch**. Der Stretch bildet das 2. Perzentil auf Schwarz und das 98. Perzentil auf Weiß ab, wodurch schwache Strukturen sichtbar werden.

Dies ist ein schneller Vorschau-Stretch — nicht dasselbe wie Sirils GHT oder andere fortgeschrittene Stretch-Methoden. Er hilft Ihnen zu sehen, was in den Daten steckt, ohne das Original zu verändern.

### Spalte 3: Stretched FITS 1 (Optional)

Erscheint, wenn Sie eine gestretchte FITS-Datei über die Schaltfläche „Load stretched FITS 1" laden. Zeigt das geladene Bild mit eigenem Histogramm und eigenen Statistiken.

### Spalte 4: Stretched FITS 2 (Optional)

Erscheint, wenn Sie eine zweite gestretchte FITS-Datei laden. Ermöglicht den Vergleich zweier verschiedener Stretch-Ansätze nebeneinander.

### Was jede Spalte enthält

Jede Spalte hat von oben nach unten dieselbe Struktur:

| Element | Beschreibung |
|---------|-------------|
| **Spaltentitel** | „Linear", „Auto-Stretched" oder der Dateiname der geladenen FITS-Datei |
| **Zoom-Werkzeugleiste** | Vier Schaltflächen: − (herauszoomen), Fit (an Ansicht anpassen), 1:1 (100%), + (hineinzoomen) |
| **Bildansicht** | Das Bild in einem scrollbaren, zoombaren Anzeigebereich |
| **Histogramm oder 3D-Diagramm** | Die in der Ansichtsgruppe ausgewählte Visualisierung |
| **Schaltfläche „Enlarge Diagram"** | Öffnet das Histogramm oder 3D-Diagramm in einem großen, maximierbaren Dialogfenster |
| **Statistiken** | Festbreitentext mit Min, Max, Mittelwert, Median, Std, IQR, MAD, Perzentilen, Clipping |

---

## 7. Histogramm-Anzeige

### Wie das Histogramm berechnet wird

1. Das Bild wird in einzelne Kanäle aufgeteilt (oder zu Luminanz kombiniert)
2. Bei großen Bildern (> 5 Millionen Pixel) wird eine gleichmäßige Teilstichprobe für die Leistung genommen
3. `numpy.histogram()` berechnet 256 Bins über den normalisierten Bereich [0, 1]
4. Die Bin-Anzahlen werden auf der Y-Achse angezeigt; die Bin-Positionen werden auf der X-Achse in ADU abgebildet

### Das Histogramm lesen

**X-Achse: Pixelwert (ADU 0–max)**
Die horizontale Achse zeigt die Helligkeit in ADU-Einheiten, von 0 (Schwarz) bis zum maximalen ADU-Wert Ihres Bildes (z.B. 65535 für 16-bit-Daten). Fünf Markierungen werden bei 0%, 25%, 50%, 75% und 100% des ADU-Bereichs angezeigt.

**Y-Achse: Pixelanzahl**
Die vertikale Achse zeigt, wie viele Pixel jeden Helligkeitswert haben. Im Normal-Modus ist dies eine direkte Anzahl. Im logarithmischen Modus ist es log₁₀(Anzahl + 1).

**Kanalfarben:**

| Kanal | Darstellungsart | Farbe |
|-------|----------------|-------|
| **RGB** | Gefüllte Fläche (halbtransparent) mit Umriss | Weiß |
| **R** | Dünne Linie | Rot |
| **G** | Dünne Linie | Grün |
| **B** | Dünne Linie | Blau |
| **L** | Dünne Linie | Gelb/Gold |

Mehrere Kanäle können gleichzeitig überlagert werden. Die gefüllte RGB-Fläche erscheint hinter den einzelnen Kanallinien.

### Gitterlinien

Gepunktete Gitterlinien erscheinen bei 25%, 50% und 75% auf beiden Achsen und helfen Ihnen bei der Beurteilung der Verteilung der Pixelwerte.

### Diagramm vergrößern

Klicken Sie auf die Schaltfläche **„Enlarge Diagram"** unter dem Histogramm einer beliebigen Spalte, um es in einem großen, maximierbaren Dialogfenster zu öffnen. Dies ist nützlich für die detaillierte Untersuchung subtiler Histogramm-Merkmale.

---

## 8. 3D-Oberflächendiagramm

### Was es zeigt

Das 3D-Oberflächendiagramm stellt Ihr Bild als Landschaft dar, wobei:
- **X- und Y-Achsen** = Pixelposition (Zeile und Spalte)
- **Z-Achse** = Pixelhelligkeit (ADU-Wert oder log₁₀(ADU + 1))

Helle Bereiche erheben sich; dunkle Bereiche sinken ab. Dies macht räumliche Helligkeitsmuster (Gradienten, Vignettierung) sofort sichtbar.

### Wie es berechnet wird

Das Bild wird auf maximal 100×100 Gitterpunkte herunterskaliert (die Konstante `SURFACE_PLOT_MAX_SIDE`) für eine gute Leistung. Der ausgewählte Kanal (RGB-Luminanz, R, G, B oder L) bestimmt die Z-Achsen-Werte.

Eine Viridis-Farbskala wird auf die Oberfläche angewendet (dunkles Violett → Blau → Grün → Gelb).

### Interaktion

Das 3D-Diagramm wird über matplotlib gerendert und als statisches Bild angezeigt. Verwenden Sie die Schaltfläche **„Enlarge Diagram"**, um es in größerer Darstellung zu sehen.

Wenn Sie auf das Bild in derselben Spalte klicken, erscheinen eine vertikale Linie und ein Markierungspunkt auf der 3D-Oberfläche an der entsprechenden Position, wobei der Z-Wert als Beschriftung angezeigt wird.

### Normal vs. Logarithmisch

Im **Normal**-Modus zeigt die Z-Achse den rohen ADU-Wert — nützlich, um den vollen Dynamikumfang zu sehen, aber helle Sterne können dominieren.

Im **Logarithmischen** Modus zeigt die Z-Achse log₁₀(ADU + 1) — komprimiert den Bereich, sodass Sie sowohl schwachen Hintergrund als auch helle Objekte sehen können.

---

## 9. Kanalauswahl

### Histogramm-Kanäle (Kontrollkästchen)

Sie können jede beliebige Kombination von Kanälen im Histogramm ein- oder ausblenden:

| Kanal | Formel | Verwendungszweck |
|-------|--------|------------------|
| **RGB** | 0.2126 × R + 0.7152 × G + 0.0722 × B | Gesamthelligkeitsverteilung betrachten (häufigste Ansicht) |
| **R** | Nur Rotkanal | Rotsignalstärke, rote Lichtverschmutzung, Ha-Emission prüfen |
| **G** | Nur Grünkanal | Grünrauschen, OIII-Emission, Farbbalance prüfen |
| **B** | Nur Blaukanal | Blausignal prüfen (oft am rauschesten), OIII-Emission |
| **L** | Gleiche Formel wie RGB (Rec.709-Luminanz) | Wie RGB, aber als dünne gelbe Linie statt als gefüllte Fläche dargestellt |

**Typische Kombinationen:**
- **Nur RGB** — schneller Überblick über die Gesamtform des Histogramms
- **R + G + B** — einzelne Kanalverteilungen vergleichen (Farbbalance-Prüfung)
- **RGB + R + G + B** — alle Kanäle überlagert für umfassende Ansicht
- **Nur L** — saubere Luminanz-Ansicht ohne die gefüllte Fläche

### 3D-Diagramm-Kanäle (Optionsfelder)

Nur ein Kanal kann die 3D-Oberflächenhöhe gleichzeitig bestimmen. Wählen Sie den Kanal, den Sie visualisieren möchten:

- **RGB/L** — Gesamthelligkeit als Höhe darstellen
- **R, G oder B** — räumliche Verteilung eines einzelnen Kanals betrachten

---

## 10. Datenmodi (Linear / Logarithmisch)

### Normal-Modus (Linear)

| Achse | Darstellung |
|-------|------------|
| Histogramm Y-Achse | Direkte Pixelanzahl |
| 3D-Diagramm Z-Achse | ADU-Wert (0 bis max) |

Ideal für: Die dominanten Merkmale des Histogramms erkennen (Hauptspitze, Gesamtform). Die hellsten/häufigsten Werte dominieren die Anzeige.

### Logarithmischer Modus

| Achse | Darstellung |
|-------|------------|
| Histogramm Y-Achse | log₁₀(Anzahl + 1) |
| 3D-Diagramm Z-Achse | log₁₀(ADU + 1) |

Ideal für: Schwache Ausläufer und Details auf niedrigem Niveau sichtbar machen, die auf einer linearen Skala unsichtbar wären. Wenn die Hauptspitze tausendmal höher als die Ausläufer ist, macht der logarithmische Modus die Ausläufer sichtbar.

**Wann logarithmisch verwenden:**
- Das Histogramm Ihres linearen Bildes sieht wie eine einzelne Spitze ohne sichtbare weitere Details aus
- Sie möchten den schwachen Stern-/Nebelausläufer auf der rechten Seite des Histogramms sehen
- Das 3D-Oberflächendiagramm wird von wenigen hellen Sternen dominiert und der Hintergrund ist flach

---

## 11. Bildzoom & Navigation

Jede Spalte hat vier Zoom-Schaltflächen in einer Werkzeugleiste über dem Bild:

| Schaltfläche | Aktion | Verwendungszweck |
|-------------|--------|------------------|
| **−** | Herauszoomen (÷ 1,2) | Zurückziehen, um mehr vom Bild zu sehen |
| **Fit** | Gesamtes Bild an den Anzeigebereich anpassen, Seitenverhältnis beibehalten | Nach dem Hineinzoomen zur Übersicht zurückkehren |
| **1:1** | 100% Zoom (1 Bildschirmpixel = 1 Bildpixel) | Feine Details in nativer Auflösung untersuchen |
| **+** | Hineinzoomen (× 1,2) | Näher an einen bestimmten Bereich herangehen |

**Leistungshinweis:** Bei Bildern, die auf einer Seite größer als 4096 Pixel sind, wird die Anzeigeversion mit hochwertigem Lanczos-Resampling (über Pillow) herunterskaliert. Die originalen Daten in voller Auflösung bleiben für Statistiken und Pixelinspektion erhalten — nur das angezeigte Bild wird skaliert.

Die Zoomstufe ist pro Spalte unabhängig, sodass Sie in denselben Bereich verschiedener Spalten hineinzoomen können, um Stretch-Ergebnisse auf derselben Detailstufe zu vergleichen.

---

## 12. Interaktive Pixelinspektion

### Auf ein Bild klicken

Klicken Sie auf eine beliebige Stelle in einem beliebigen Bild in jeder Spalte, um dieses Pixel zu untersuchen:

1. Die exakten Pixelkoordinaten werden berechnet (unter Berücksichtigung etwaiger Anzeige-Herunterskalierung)
2. Die R-, G-, B-Werte des Pixels werden aus den Bilddaten entnommen
3. Ein Intensitätswert (Luminanz) wird berechnet
4. Alle Werte werden in ADU unter Verwendung des ADU-Bereichs des Bildes umgerechnet

### Was erscheint

**Im Statistik-Panel** der angeklickten Spalte wird eine neue Zeile angehängt:

```
Click (x=1234, y=567): R=1023 G=987 B=876  I=974
```

Dabei bedeutet:
- `x`, `y` = Pixelkoordinaten im Originalbild
- `R`, `G`, `B` = ADU-Werte für jeden Kanal
- `I` = Luminanz-Intensität in ADU

**Im Histogramm** erscheint eine vertikale gestrichelte Markierungslinie am Intensitätswert des angeklickten Pixels mit folgender Beschriftung:

```
Value: 974   Count: 1,234
```

Dies zeigt Ihnen genau, wo im Histogramm dieses Pixel liegt und wie viele andere Pixel dieselbe Helligkeit haben.

**Im 3D-Oberflächendiagramm** erscheinen eine vertikale Linie und ein Markierungspunkt an der angeklickten Position, wobei der Z-Wert angezeigt wird.

**Wichtig:** Das Klicken auf das Bild einer Spalte setzt die Markierung nur im Histogramm dieser Spalte. Markierungen in anderen Spalten werden automatisch gelöscht, um Verwirrung zu vermeiden.

---

## 13. Statistik-Panel

Unter dem Histogramm/3D-Diagramm jeder Spalte zeigt ein Statistik-Panel umfassende numerische Daten über das Bild.

### Angezeigte Statistiken

| Metrik | Beschreibung |
|--------|-------------|
| **Size** | Bildabmessungen (Breite × Höhe) |
| **Pixels** | Gesamte Pixelanzahl (kann „subsampled" anzeigen bei Bildern > 5M Pixel) |
| **Min / Max** | Minimale und maximale Pixelwerte in ADU |
| **Mean** | Durchschnittlicher Pixelwert in ADU |
| **Median** | Mittlerer Pixelwert in ADU (50. Perzentil) |
| **Std** | Standardabweichung in ADU — misst die Streuung der Werte |
| **IQR** | Interquartilsabstand (P75 − P25) in ADU — robustes Streuungsmaß |
| **MAD** | Median der absoluten Abweichungen in ADU — ein weiteres robustes Streuungsmaß |
| **P2 / P98** | 2. und 98. Perzentilwerte in ADU — die Autostretch-Referenzpunkte |
| **Range** | P98 − P2 in ADU — der „nutzbare" Dynamikumfang |
| **Near-black** | Prozentsatz und Anzahl der Pixel mit Wert ≤ 1/255 des Gesamtbereichs |
| **Near-white** | Prozentsatz und Anzahl der Pixel mit Wert ≥ 254/255 des Gesamtbereichs |

### Die Statistiken interpretieren

**Für ein lineares Bild (Linear-Spalte):**
- Min nahe 0, Max deutlich höher → normale lineare Daten
- P2 sehr nahe an P98 → die meisten Daten in einem schmalen Bereich komprimiert (normal für linear)
- Hoher Near-black-Prozentsatz → normal (die meisten Pixel sind Hintergrund nahe Null)

**Für ein automatisch gestretchtes Bild:**
- P2 nahe 0, P98 nahe Maximum → guter Stretch, der den Bereich ausfüllt
- Std und IQR zeigen die Tonwertspreizung an
- Near-white > 0 → etwas Clipping am hellen Ende

**Für gestretchte Vergleichsbilder:**
- Vergleichen Sie Std, IQR und MAD zwischen verschiedenen Stretches
- Prüfen Sie Near-black und Near-white, um zu sehen, welcher Stretch stärker clippt
- Der P2/P98-Bereich zeigt, wie viel des Tonwertbereichs jeder Stretch nutzt

### Pixelinspektions-Zeilen

Wenn Sie auf ein Bild klicken, werden die Pixelwerte dem Statistik-Panel dieser Spalte angehängt. Mehrere Klicks akkumulieren sich, sodass Sie mehrere Pixel abtasten und deren Werte vergleichen können.

---

## 14. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Ihre linearen Daten verstehen (2 Minuten)

**Szenario:** Sie haben gerade ein Bild gestackt und möchten verstehen, womit Sie arbeiten, bevor Sie mit der Bearbeitung beginnen.

**Arbeitsablauf:**
1. Laden Sie das gestackte Bild in Siril
2. Starten Sie den Multiple Histogram Viewer
3. Betrachten Sie die **Linear-Spalte**:
   - Ist das Histogramm eine schmale Spitze nahe dem linken Rand? Das sind normale lineare Daten.
   - Wie weit erstrecken sich die Daten nach rechts? Mehr = mehr Signal.
4. Betrachten Sie die **Auto-Stretched-Spalte**:
   - Können Sie Nebulosität, Galaxien oder andere Strukturen erkennen? Wenn ja, gibt es Signal zum Bearbeiten.
   - Ist der Hintergrund glatt oder von Gradienten betroffen?
5. Wechseln Sie in den **logarithmischen Modus**, um den schwachen Ausläufer des linearen Histogramms zu sehen — dieser enthüllt Signal von schwachen Objekten, das im Normal-Modus unsichtbar ist.

### Anwendungsfall 2: Stretch-Methoden vergleichen (5 Minuten)

**Szenario:** Sie haben verschiedene Stretch-Methoden angewendet (GHT, Asinh, AutoStretch) und als separate FITS-Dateien gespeichert. Sie möchten die Ergebnisse vergleichen.

**Arbeitsablauf:**
1. Laden Sie das **lineare** Bild in Siril und starten Sie den Histogram Viewer
2. Klicken Sie auf **„Load stretched FITS 1"** und wählen Sie Ihre GHT-gestretchte Version
3. Klicken Sie auf **„Load stretched FITS 2"** und wählen Sie Ihre Asinh-gestretchte Version
4. Jetzt haben Sie vier Spalten: Linear, Auto-Stretched, GHT und Asinh
5. Vergleichen Sie:
   - **Histogramme:** Welcher Stretch ergibt die glatteste, breiteste Verteilung?
   - **Near-white %:** Welcher Stretch clippt die wenigsten Lichter?
   - **Bilder:** Zoomen Sie auf 1:1 und vergleichen Sie feine Details, Sterngrößen und Rauschen
6. Klicken Sie denselben Stern in jeder Spalte an, um seinen ADU-Wert über die Stretches hinweg zu vergleichen

### Anwendungsfall 3: Farbbalance prüfen (3 Minuten)

**Szenario:** Sie haben SPCC angewendet und möchten die Farbbalance überprüfen.

**Arbeitsablauf:**
1. Laden Sie das farbkalibrierte Bild
2. Starten Sie den Histogram Viewer
3. Aktivieren Sie die **R, G, B**-Kanäle im Histogramm (deaktivieren Sie RGB und L für Übersichtlichkeit)
4. Betrachten Sie die drei Kanal-Histogramme:
   - **Gut ausbalanciert:** R-, G-, B-Spitzen liegen ungefähr an derselben Position
   - **Farbstich:** Die Spitze eines Kanals ist deutlich nach links oder rechts verschoben
5. Prüfen Sie die **Kanal-Statistiken**: Vergleichen Sie die R-, G-, B-Medianwerte
6. Wenn ein Kanal merklich versetzt ist, muss die Farbkalibrierung möglicherweise angepasst werden

### Anwendungsfall 4: Clipping erkennen (2 Minuten)

**Szenario:** Sie möchten prüfen, ob Ihr Bild überbelichtete Lichter oder abgeschnittene Schatten hat.

**Arbeitsablauf:**
1. Laden Sie das Bild und starten Sie den Histogram Viewer
2. Prüfen Sie das **Statistik-Panel** für jede Spalte:
   - **Near-black > 0%:** Etwas Schatten-Clipping (normal für lineare Daten; bedenklich für gestretchte Daten)
   - **Near-white > 0%:** Lichter-Clipping (Sternkerne, helle Nebelregionen)
3. Wechseln Sie in den **logarithmischen Modus**, um zu sehen, ob das Histogramm die Ränder berührt
4. Klicken Sie auf verdächtig helle Sterne, um ihre ADU-Werte zu prüfen — Werte nahe dem Maximum deuten auf Sättigung hin

### Anwendungsfall 5: Gradienten / Vignettierung prüfen

**Szenario:** Sie vermuten einen Hintergrundgradienten und möchten ihn visualisieren.

**Arbeitsablauf:**
1. Laden Sie das gestackte (lineare) Bild
2. Starten Sie den Histogram Viewer
3. Wechseln Sie zur Ansicht **3D Surface Plot**
4. Die 3D-Oberfläche der **Linear**-Spalte enthüllt die Topografie des Hintergrunds:
   - **Geneigte Ebene** = gerichteter Gradient (Lichtverschmutzung)
   - **Schalen-/Kuppelform** = Vignettierung
   - **Spitzen** = helle Sterne
5. Wechseln Sie in den **logarithmischen** 3D-Modus, wenn helle Sterne das Diagramm dominieren — die Log-Komprimierung enthüllt die Hintergrundform darunter
6. Vergleichen Sie die linearen und automatisch gestretchten 3D-Diagramme — der Autostretch kann Gradienten übertreiben und dadurch sichtbarer machen

### Anwendungsfall 6: Vorher/Nachher-Verarbeitungsvergleich

**Szenario:** Sie haben eine Hintergrundextraktion durchgeführt und möchten sehen, wie sich das Histogramm verändert hat.

**Arbeitsablauf:**
1. Vor der Extraktion: Speichern Sie das Bild als FITS-Datei (z.B. `before_subsky.fits`)
2. Führen Sie die Hintergrundextraktion in Siril durch
3. Starten Sie den Histogram Viewer — er lädt das aktuelle (nachextrahierte) Bild
4. Klicken Sie auf **„Load stretched FITS 1"** und laden Sie Ihre gespeicherte `before_subsky.fits`
5. Vergleichen Sie nun:
   - Die Linear-Spalte zeigt Ihre nachextrahierten Daten
   - Die Stretched FITS 1-Spalte zeigt Ihre vorextrahierten Daten
   - Vergleichen Sie die Histogramme: das nachextrahierte Histogramm sollte schmaler sein (weniger Gradientenspreizung)
   - Vergleichen Sie die Statistiken: niedrigere Std und IQR deuten auf einen gleichmäßigeren Hintergrund hin

### Anwendungsfall 7: Ha- / Schmalbandsignal prüfen

**Szenario:** Sie haben ein Schmalband-Bild (Ha) und möchten sehen, wo das Signal liegt.

**Arbeitsablauf:**
1. Laden Sie den Schmalband-Stack
2. Starten Sie den Histogram Viewer
3. Da es sich um ein Monobild handelt, zeigen die RGB/R/G/B-Kanäle alle dieselben Daten
4. Wechseln Sie in den **logarithmischen** Modus, um den schwachen Emissionsausläufer zu sehen
5. Wechseln Sie zum **3D Surface Plot** — die Emissionsregionen erscheinen als erhöhte Plateaus über dem Hintergrund
6. Klicken Sie auf helle Emissionsregionen und vergleichen Sie deren ADU-Werte mit dem Hintergrund

---

## 15. Tipps & Empfehlungen

### Histogramm lesen

1. **Prüfen Sie immer den logarithmischen Modus.** Der Normal-Modus zeigt die dominante Spitze deutlich, aber der schwache Signalausläufer (wo Ihr Nebel lebt) ist oft unsichtbar, bis Sie in den Log-Modus wechseln.

2. **Vergleichen Sie dieselben Kanäle spaltenübergreifend.** Beim Vergleichen von Stretches halten Sie dieselbe Kanalauswahl über alle Spalten hinweg für einen fairen Vergleich bei.

3. **Die Lücke zwischen der Hauptspitze und dem rechten Ausläufer ist Ihr Signal.** In einem linearen Histogramm ist die Hauptspitze Hintergrundrauschen. Alles rechts davon ist Signal von Ihrem Zielobjekt.

### 3D-Oberflächendiagramme

4. **Verwenden Sie 3D-Diagramme zur Gradientenerkennung.** Gradienten sind in 3D viel offensichtlicher als in einem flachen Bild oder Histogramm. Ein Gradient, der im Bild unsichtbar ist, wird zu einer offensichtlichen Neigung im 3D-Diagramm.

5. **Log-Modus in 3D bändigt helle Sterne.** Wenn wenige helle Sterne hohe Spitzen erzeugen, die alles andere flach erscheinen lassen, wechseln Sie in den logarithmischen Modus.

### Pixelinspektion

6. **Klicken Sie entsprechende Positionen spaltenübergreifend an.** Klicken Sie denselben Stern oder dieselbe Region in jeder Spalte an, um zu vergleichen, wie verschiedene Stretches dieses spezifische Pixel beeinflussen.

7. **Nutzen Sie Pixelklicks zum Verständnis des Histogramms.** Das Klicken auf ein Pixel setzt eine Markierung im Histogramm — dies lehrt Sie, welche Histogrammbereiche welchen Bildmerkmalen entsprechen.

### Bildvergleich

8. **Verwenden Sie dieselbe Zoomstufe spaltenübergreifend.** Zoomen Sie in allen Spalten auf 1:1, scrollen Sie dann zur selben Region für einen fairen visuellen Vergleich.

9. **Der Autostretch ist eine Basislinie.** Er ist kein optimaler Stretch — er ist eine schnelle Perzentil-Neuzuordnung. Vergleichen Sie Ihre eigenen Stretches damit, um zu sehen, wie viel besser Ihre Technik ist.

10. **Prüfen Sie Near-black- und Near-white-Prozentsätze.** Ein guter Stretch maximiert den Tonwertumfang, ohne an beiden Enden zu clippen. Vergleichen Sie diese Zahlen zwischen verschiedenen Stretches.

### Leistung

11. **Große Bilder werden automatisch unterabgetastet** für Statistiken und Histogramme (> 5M Pixel). Die Werte sind dennoch genau — die Unterabtastung erhält die statistische Verteilung.

12. **Bilder größer als 4096px** werden für die Anzeige mit hochwertigem Lanczos-Resampling herunterskaliert. Die Statistiken und die Pixelinspektion verwenden die Daten in voller Auflösung.

---

## 16. Fehlerbehebung

### Fehler „No image loaded"

**Ursache:** In Siril ist kein Bild geöffnet.
**Lösung:** Laden Sie ein FITS-Bild in Siril, bevor Sie das Skript starten, oder verwenden Sie „Load linear FITS...", um direkt von der Festplatte zu laden.

### Fehler „Connection timed out"

**Ursache:** Die sirilpy-Verbindung zu Siril hat das Zeitlimit überschritten.
**Lösung:** Stellen Sie sicher, dass Siril reagiert. Klicken Sie auf „Refresh from Siril", um es erneut zu versuchen.

### Spalten sind zu schmal

**Ursache:** Mit 4 Spalten kann jede Spalte auf kleineren Bildschirmen schmal sein.
**Lösung:** Das Fenster wird maximiert geöffnet. Jede Spalte hat eine Mindestbreite von 280px. Verwenden Sie die Schaltfläche „Enlarge Diagram", um Histogramme in voller Größe zu sehen. Erwägen Sie, weniger Vergleichsbilder zu laden, wenn der Bildschirmplatz begrenzt ist.

### 3D-Oberflächendiagramm ist leer

**Ursache:** matplotlib ist möglicherweise nicht installiert oder hat ein Rendering-Problem.
**Lösung:** Das Skript installiert matplotlib automatisch, aber falls dies fehlschlägt, installieren Sie es manuell: `pip install matplotlib`. Starten Sie das Skript neu.

### Lineares Bild erscheint komplett schwarz

**Ursache:** Normal — lineare Astrofotografie-Bilder haben die meisten Pixelwerte nahe Null. Der Hintergrund sitzt nahe dem unteren Ende des ADU-Bereichs.
**Lösung:** Dies ist zu erwarten. Betrachten Sie die Auto-Stretched-Spalte, um zu sehen, was in den Daten steckt. Die Linear-Spalte zeigt die Rohwerte, die für Statistiken nützlich sind, aber nicht für die visuelle Inspektion.

### Histogramm zeigt nur eine einzelne Spitze

**Ursache:** Dies ist das normale Erscheinungsbild eines linearen Bild-Histogramms — alle Hintergrundpixel sind in eine schmale Spitze nahe Null komprimiert.
**Lösung:** Wechseln Sie in den **logarithmischen** Modus, um den schwachen Ausläufer nach rechts zu sehen. Dieser Ausläufer ist Ihr Signal (Sterne, Nebel).

### Komprimierte FITS-Dateien lassen sich nicht laden

**Ursache:** Ältere astropy-Versionen unterstützen möglicherweise keine `.fz` (fpack) oder `.gz` (gzip) komprimierten FITS-Dateien.
**Lösung:** Aktualisieren Sie astropy: `pip install --upgrade astropy`. Version 1.0.1 des Histogram Viewers hat die Unterstützung komprimierter FITS-Dateien hinzugefügt.

### Pixelklick zeigt falsche Koordinaten

**Ursache:** Bei Bildern größer als 4096px wird die Anzeige herunterskaliert. Die Koordinatenzuordnung sollte dies berücksichtigen, aber in Randfällen kann es gelegentlich um ein Pixel abweichen.
**Lösung:** Die Statistiken zeigen dennoch die korrekten ADU-Werte aus den Originaldaten. Verwenden Sie die Koordinaten bei großen herunterskalierten Bildern als Näherungswerte.

---

## 17. Häufige Fragen

**F: Verändert dieses Werkzeug mein Bild?**
A: Nein — es arbeitet vollständig im Lesemodus. Es liest Pixeldaten aus Siril (oder aus FITS-Dateien) und zeigt Histogramme und Statistiken an. Ihr Bild wird niemals verändert.

**F: Was ist der Unterschied zwischen der „Auto-Stretched"-Spalte und meinem eigenen Stretch?**
A: Der Autostretch ist eine einfache Perzentil-Neuzuordnung (2. bis 98. Perzentil auf [0, 1] abgebildet). Er ist ein schnelles Visualisierungswerkzeug, kein optimaler Stretch. Ihr eigener Stretch (GHT, Asinh, usw.) sollte bessere Ergebnisse mit mehr Kontrolle über die Tonwertverteilung liefern.

**F: Warum gibt es zwei Luminanz-Optionen (RGB und L)?**
A: Sie berechnen denselben Rec.709-Luminanzwert. Der Unterschied liegt in der Darstellung — **RGB** wird als gefüllte, halbtransparente Fläche gezeichnet (gut, um die Gesamtform zu erkennen), während **L** als dünne gelbe Linie gezeichnet wird (gut zum Überlagern über einzelne Kanallinien, ohne diese zu verdecken).

**F: Kann ich mehr als zwei Vergleichsbilder laden?**
A: Nein — die aktuelle Version unterstützt zwei gestretchte Vergleichsplätze. Um mehr Versionen zu vergleichen, schließen Sie das Werkzeug und öffnen Sie es mit anderen Dateien erneut.

**F: Warum ist die X-Achse in ADU statt normalisiert auf 0–1?**
A: ADU-Werte sind das, was Ihre Kamera tatsächlich aufgezeichnet hat. Sie sind intuitiver für das Verständnis Ihrer Daten — Sie können sie mit der Bittiefe und dem Sättigungspunkt Ihrer Kamera in Beziehung setzen. Das Histogramm wird intern auf normalisierten [0, 1]-Daten berechnet, aber zur besseren Lesbarkeit in ADU angezeigt.

**F: Kann ich das Werkzeug mit Mono-Bildern (Graustufen) verwenden?**
A: Ja. Bei Mono-Bildern zeigen alle Kanäle (R, G, B, RGB, L) dieselben Daten. Das Histogramm wird überlappende identische Linien haben.

**F: Was bedeutet „subsampled" in den Statistiken?**
A: Bei Bildern mit mehr als 5 Millionen Pixeln wird eine gleichmäßige Teilstichprobe für die Statistik- und Histogrammberechnung verwendet. Dies hält die Leistung reaktionsfähig, ohne die Genauigkeit wesentlich zu beeinträchtigen — die Teilstichprobe erhält die statistische Verteilung des Gesamtbildes.

**F: Warum sieht der Autostretch anders aus als Sirils Autostretch?**
A: Der Histogram Viewer verwendet einen einfachen linearen Perzentil-Stretch (P2 bis P98), während Sirils Autostretch möglicherweise andere Algorithmen (Mitteltontransferfunktion, generalisiert hyperbolisch, usw.) mit anderen Parametern verwendet. Der Autostretch des Viewers ist bewusst einfach gehalten — er ist eine schnelle Vorschau, kein Verarbeitungsschritt.

**F: Kann ich das Histogramm als Bild exportieren?**
A: Nicht direkt — die aktuelle Version hat keine Exportfunktion. Sie können die Schaltfläche „Enlarge Diagram" verwenden, um das Histogramm in voller Größe anzuzeigen, und dann ein Bildschirmfoto mit dem Screenshot-Werkzeug Ihres Betriebssystems aufnehmen.

**F: Was ist der Zusammenhang zwischen dem Histogram Viewer und dem Gradient Analyzer?**
A: Der **Histogram Viewer** zeigt die Gesamthelligkeitsverteilung und ermöglicht den Vergleich verschiedener Bildversionen nebeneinander. Der **Gradient Analyzer** ist ein Spezialwerkzeug für die Hintergrundgradienten-Diagnostik mit 9 spezialisierten Visualisierungsreitern. Verwenden Sie den Histogram Viewer, um Ihre Datenverteilung zu verstehen; verwenden Sie den Gradient Analyzer, um Gradientenprobleme zu diagnostizieren und zu beheben.

---

## Danksagung

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die außerdem umfasst:
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Image Advisor
- Svenesis Annotate Image
- Svenesis Script Security Scanner

---

*Wenn Sie dieses Werkzeug nützlich finden, erwägen Sie eine Unterstützung der Entwicklung über [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
