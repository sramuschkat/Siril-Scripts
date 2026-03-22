# Svenesis Blink Comparator — Benutzeranleitung

**Version 1.2.3** | Siril Python-Skript zur Bildauswahl & Qualitätsanalyse

> *Vergleichbar mit PixInsight's Blink + SubframeSelector — aber kostenlos, quelloffen und eng in Siril integriert.*

---

## Inhaltsverzeichnis

1. [Was ist der Blink Comparator?](#1-was-ist-der-blink-comparator)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Die Messwerte verstehen](#6-die-messwerte-verstehen)
7. [Anzeigemodi](#7-anzeigemodi)
8. [Methoden zur Bildauswahl](#8-methoden-zur-bildauswahl)
9. [Das Rückgängig-System](#9-das-rückgängig-system)
10. [Änderungen an Siril übertragen](#10-änderungen-an-siril-übertragen)
11. [Exportoptionen](#11-exportoptionen)
12. [Anwendungsfälle & Arbeitsabläufe](#12-anwendungsfälle--arbeitsabläufe)
13. [Tastaturkürzel](#13-tastaturkürzel)
14. [Tipps & Empfehlungen](#14-tipps--empfehlungen)
15. [Fehlerbehebung](#15-fehlerbehebung)
16. [Häufige Fragen](#16-häufige-fragen)

---

## 1. Was ist der Blink Comparator?

Der **Svenesis Blink Comparator** ist ein Siril Python-Skript, das alle Bilder einer Astrofotografie-Sequenz schnell hintereinander abspielt („blinkt"), damit Sie diese visuell prüfen, fehlerhafte Bilder erkennen und vor dem Stacken aussortieren können.

Stellen Sie ihn sich als **Qualitätskontrolleur** für Ihre Einzelbilder vor. Er kombiniert:

- **Visuelle Prüfung** — betrachten Sie Ihre Bilder wie einen Film, um Probleme zu erkennen
- **Statistische Analyse** — sehen Sie FWHM, Rundheit, Sternanzahl und Hintergrund für jedes Bild
- **Bildaussortierung per Mausklick** — markieren Sie fehlerhafte Bilder und teilen Sie Siril mit, welche vom Stacken ausgeschlossen werden sollen

Das Ergebnis: ein saubereres, schärferes Endergebnis, weil die Bilder entfernt wurden, die die Qualität herabgezogen hätten.

---

## 2. Hintergrundwissen für Einsteiger

### Warum müssen wir Bilder auswählen?

Wenn Sie den Nachthimmel fotografieren, nehmen Sie viele einzelne Belichtungen auf (sogenannte „Subframes" oder „Subs"). Diese werden ausgerichtet und zu einem Endbild gestackt. Aber nicht jedes Einzelbild ist gleich gut. Während einer typischen Aufnahmesession können verschiedene Dinge schiefgehen:

| Problem | Was passiert | Wie es aussieht |
|---------|-------------|-----------------|
| **Wolken** | Dünne Wolken ziehen durch Ihr Bildfeld | Hintergrund wird heller, Sterne verblassen |
| **Satellitenspuren** | Ein Satellit kreuzt Ihr Bild | Heller Streifen quer über das Bild |
| **Nachführfehler** | Ihre Montierung ruckelt | Sterne werden zu länglichen Strichen |
| **Fokusdrift** | Temperaturänderungen verschieben den Fokus | Sterne blähen sich auf und werden unscharf |
| **Windböen** | Wind erschüttert Ihr Teleskop | Sterne werden für einige Bilder aufgebläht |
| **Flugzeuglichter** | Ein Flugzeug blinkt durch | Heller blinkender Fleck |
| **Tau / Frost** | Feuchtigkeit bildet sich auf der Optik | Sterne zeigen Halos, Hintergrund steigt, Sternanzahl sinkt |

Wenn Sie diese fehlerhaften Bilder in Ihren Stack einbeziehen, **verschlechtern** sie Ihr Endergebnis: unschärfere Sterne, höheres Rauschen, Nachführartefakte. Bereits das Entfernen von 5–10 % der schlechtesten Bilder kann Ihr Ergebnis dramatisch verbessern.

### Was ist „Blinken"?

Ein **Blink Comparator** ist eine astronomische Technik aus den 1920er Jahren (so wurde Pluto entdeckt!). Man wechselt schnell zwischen Bildern hin und her, sodass alles, was sich ändert — ein sich bewegendes Objekt, eine Helligkeitsänderung, eine Fokusverschiebung — dem menschlichen Auge sofort auffällt.

In der Astrofotografie macht das Blinken durch Ihre Einzelbilder Probleme **offensichtlich**, die Sie beim Betrachten einzelner Bilder nie bemerken würden.

### Was ist FWHM?

**FWHM** (Full Width at Half Maximum) misst die Sternschärfe in Pixeln. Stellen Sie sich einen Stern als Glockenkurve der Helligkeit vor — FWHM ist die Breite dieser Glocke auf halber Höhe ihres Maximums.

- **Niedrigerer FWHM = schärfere Sterne** (gut)
- **Höherer FWHM = aufgeblähte Sterne** (schlecht — Fokus-, Seeing- oder Nachführprobleme)
- Typischer Bereich: 2–6 Pixel je nach Ausrüstung und Bedingungen

### Was ist Rundheit?

**Rundheit** misst, wie kreisförmig Ihre Sterne sind, auf einer Skala von 0 bis 1:

- **1,0 = perfekter Kreis** (ideal)
- **0,0 = eine Linie** (starke Nachführfehler)
- Über 0,75 ist generell gut
- Unter 0,6 deutet meist auf Nachführ- oder Windprobleme hin

Verwandt mit der **Exzentrizität** (in PixInsight verwendet): `eccentricity ≈ 1 − roundness`.

### Was ist der Hintergrundpegel?

Der **Hintergrundpegel** ist die mittlere Helligkeit des Himmels in Ihrem Bild. Er sollte über alle Bilder hinweg konsistent sein.

- **Spitze nach oben** = Wolken, Lichtverschmutzung, Flugzeug, Mond
- **Ansteigender Trend** = Morgendämmerung naht, Wolken verdichten sich
- **Konstant** = gute Aufnahmebedingungen

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweise |
|------------|---------------|----------|
| **Siril** | 1.4.0+ | Python-Skriptunterstützung muss aktiviert sein |
| **sirilpy** | Mitgeliefert | Im Lieferumfang von Siril 1.4+ enthalten |
| **numpy** | Beliebig aktuell | Wird vom Skript automatisch installiert |
| **PyQt6** | 6.x | Wird vom Skript automatisch installiert |
| **matplotlib** | 3.x | Wird vom Skript automatisch installiert |
| **Pillow** | Beliebig | *Optional* — wird nur für den GIF-Export benötigt |

### Installation

1. Laden Sie `Svenesis-BlinkComparator.py` vom [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Legen Sie die Datei in Ihr Siril-Skriptverzeichnis:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Verarbeitung → Skripte**.

Das Skript installiert fehlende Python-Abhängigkeiten (`numpy`, `PyQt6`, `matplotlib`) automatisch beim ersten Start.

---

## 4. Erste Schritte

### Schritt 1: Eine registrierte Sequenz laden

Das Skript arbeitet mit einer in Siril geladenen **Sequenz** — nicht mit einem einzelnen Bild. Sie benötigen mindestens 2 Bilder, aber eine echte Aufnahmesession hat typischerweise 50–500+.

**Wenn Sie bereits eine registrierte Sequenz haben:**
1. Setzen Sie das Arbeitsverzeichnis auf den Ordner, der Ihre `.seq`-Datei und `.fit`-Dateien enthält.
2. Siril erkennt automatisch die Sequenz und zeigt sie in der Bildliste unten an.

**Wenn Sie unverarbeitete FITS-Dateien haben:**
```
# In der Siril-Konsole:
cd /path/to/your/lights
convert light -out=./process
cd process
register pp_light
```
Dies erstellt eine registrierte Sequenz `r_pp_light_`, mit der der Blink Comparator arbeiten kann.

**Wenn Sie ein Vorverarbeitungsskript verwendet haben (z. B. SeeStar):**
Ihr Skript hat wahrscheinlich bereits eine registrierte Sequenz erstellt. Setzen Sie das Arbeitsverzeichnis auf den Ausgabeordner — Siril erkennt die `.seq`-Datei automatisch.

### Schritt 2: Das Skript ausführen

Gehen Sie zu **Verarbeitung → Skripte → Svenesis Blink Comparator**.

Das Skript wird:
1. Die Sequenz-Metadaten laden (Bildanzahl, Dimensionen, Kanäle)
2. Die Statistiken pro Bild laden (FWHM, Rundheit, Hintergrund, Sterne, Median, Sigma)
3. Das Hauptfenster mit dem ersten Bild öffnen

### Schritt 3: Sternerkennung ausführen (falls nötig)

Wenn die Spalten FWHM, Rundheit, Sterne und Gewicht leer sind, erscheint ein **gelbes Banner** oben:

> ⚠️ Keine Sternerkennungsdaten. Klicken Sie, um die Sternerkennung auszuführen...

Klicken Sie auf das Banner. Dies führt Sirils Befehl `register <seq> -2pass` aus, der in jedem Bild Sterne erkennt und FWHM, Rundheit, Hintergrundpegel und Sternanzahl berechnet. Je nach Bildanzahl dauert dies einige Sekunden bis wenige Minuten.

**Hinweis:** Median und Sigma sind *immer* verfügbar — sie erfordern keine Sternerkennung.

### Schritt 4: Prüfen und auswählen

Jetzt können Sie:
- **Die Animation abspielen** (Space), um Probleme visuell zu erkennen
- **Die Statistiktabelle sortieren** nach FWHM (schlechteste Bilder oben)
- **Stapel-Aussortierung verwenden**, um die schlechtesten 10 % automatisch zu entfernen
- **Einzelne Bilder markieren** mit G (gut) oder B (schlecht)

### Schritt 5: Anwenden und Stacken

Klicken Sie auf **Änderungen an Siril übertragen**, um Ihre Bildauswahl zu senden. Stacken Sie dann wie gewohnt in Siril — ausgeschlossene Bilder werden übersprungen.

---

## 5. Die Benutzeroberfläche

Das Fenster ist in mehrere Bereiche unterteilt:

### Linkes Panel (Steuerungsbereich)

Die linke Seite (340px breit) enthält alle Steuerungselemente, organisiert in aufklappbaren Abschnitten:

- **Wiedergabesteuerung:** Abspielen/Pause, Bildnavigation, Geschwindigkeitsregler, Schleifenmodus
- **Anzeigemodus:** Normal, Differenz, Nur eingeschlossene, Nebeneinander
- **Anzeigeoptionen:** Verknüpfte Streckung, Überblendung, Bild-Overlay, Vorschaubildgröße, Histogramm
- **Bildauswahl:** Behalten/Aussortieren-Schaltflächen, automatisches Weiterschalten, Zähler ausstehender Änderungen, Übernehmen-Schaltfläche
- **Stapelauswahl:** Schwellenwertfilter, schlechteste N %, Freigabeausdrücke
- **Export:** Ausschlussliste, CSV, GIF, Zwischenablage

### Rechtes Panel (Tab-Bereich)

Der Hauptbereich hat vier Tabs:

#### Betrachter-Tab
Die Bildanzeigefläche. Zeigt das aktuelle Bild mit angewandter Autostreckung.
- **Scrollrad** zum Zoomen (0,1x bis 20x)
- **Rechtsklick-Ziehen** zum Schwenken
- **Z** zum Zurücksetzen des Zooms auf Fensterpassung
- **1:1-Schaltfläche** für pixelgenauen Zoom
- **ROI-Modus:** Zeichnen Sie ein Rechteck, um nur diesen Bereich zu blinken

#### Statistiktabelle-Tab
Alle Bilder in einer sortierbaren Tabelle mit 10 Spalten:
- Bild-Nr., Gewicht, FWHM, Rundheit, Hintergrundpegel, Sterne, Median, Sigma, Datum, Status
- **Klick auf Spaltenüberschrift** zum Sortieren (erneuter Klick kehrt die Richtung um)
- **Klick auf eine Zeile** springt zu diesem Bild im Betrachter
- **Ctrl+Klick** oder **Shift+Klick** zur Mehrfachauswahl von Zeilen
- **Rechtsklick** auf ausgewählte Zeilen → „Ausgewählte aussortieren"
- Ausgeschlossene Zeilen haben einen rot getönten Hintergrund
- Die aktuelle Bildzeile ist blau hervorgehoben

#### Statistikdiagramm-Tab
Liniendiagramme, die Messwerte über alle Bilder zeigen:
- Umschaltbar: FWHM, Hintergrund, Rundheit (Kontrollkästchen über dem Diagramm)
- **Dünne Linie** = unbearbeitete Werte pro Bild
- **Fette Linie** = gleitender Durchschnitt über 7 Bilder (zeigt Trends)
- **Rote Punkte** = ausgeschlossene Bilder
- **Weiße gestrichelte Linie** = Position des aktuellen Bildes
- Ideal zum Erkennen von: Fokusdrift (FWHM-Anstieg), Wolken (Hintergrundspitze), Nachführverschlechterung (Rundheitsabfall)

#### Streudiagramm-Tab
2D-Streudiagramm zweier beliebiger Messwerte:
- X- und Y-Achse über Dropdown-Menüs auswählen
- **Blaue Punkte** = eingeschlossene Bilder
- **Rotes ✕** = ausgeschlossene Bilder
- **Roter Stern** = aktuelles Bild
- **Klick auf einen Punkt** springt zu diesem Bild
- Beste Kombinationen: **FWHM vs. Rundheit** (Sternqualität), **FWHM vs. Hintergrund** (Wolken + Seeing)

### Untere Leiste (Filmstreifen)

Ein horizontal scrollbarer Streifen mit Bildvorschauen (immer sichtbar):
- **Grüner Rand** = eingeschlossen
- **Roter Rand** = ausgeschlossen
- **Blauer Rand** = aktuelles Bild
- Klick auf eine Vorschau springt zu diesem Bild
- Vorschauen werden verzögert geladen, wenn Sie scrollen
- Größe über den Schieberegler in den Anzeigeoptionen anpassbar (40–160px)

---

## 6. Die Messwerte verstehen

### FWHM (Full Width at Half Maximum)

| Aspekt | Details |
|--------|---------|
| **Was** | Sterndurchmesser bei halber Maximalhelligkeit, in Pixeln |
| **Quelle** | Siril-Registrierungsdaten (`get_seq_regdata`) |
| **Gute Werte** | Niedriger ist besser. Typisch: 2–6 px |
| **Erfordert** | Sternerkennung muss durchgeführt worden sein |

**Interpretation:** Plötzlicher Anstieg = Fokusdrift, Wind oder schlechtes Seeing. Allmählicher Anstieg = thermische Fokusverschiebung. Einzelne Spitze = Windstoß.

### Rundheit

| Aspekt | Details |
|--------|---------|
| **Was** | Kreisförmigkeit der Sterne, 0 (Linie) bis 1 (perfekter Kreis) |
| **Quelle** | Siril-Registrierungsdaten |
| **Gute Werte** | Über 0,75. Unter 0,6 = Probleme |
| **Erfordert** | Sternerkennung muss durchgeführt worden sein |

**Interpretation:** Niedrige Rundheit = Nachführfehler, Wind oder optische Verkippung. Gruppe von Bildern mit niedriger Rundheit = Montierungsruckler oder Windstoß.

### Hintergrundpegel (BG Level)

| Aspekt | Details |
|--------|---------|
| **Was** | Mittlere Himmelshelligkeit, normalisiert auf [0, 1] |
| **Quelle** | Registrierungsdaten (`background_lvl`) oder `stats.median` als Rückfalloption |
| **Gute Werte** | Konstant über alle Bilder |
| **Erfordert** | Immer verfügbar (Rückfalloption nutzt Basisstatistiken) |

**Interpretation:** Spitze = Wolken, Flugzeug oder Mond. Ansteigender Trend = Morgendämmerung oder zunehmende Lichtverschmutzung.

### Sterne (Sternanzahl)

| Aspekt | Details |
|--------|---------|
| **Was** | Anzahl der im Bild erkannten Sterne |
| **Quelle** | Siril-Registrierungsdaten (`number_of_stars`) |
| **Gute Werte** | Konstante Anzahl; höher ist generell besser |
| **Erfordert** | Sternerkennung muss durchgeführt worden sein |

**Interpretation:** Plötzlicher Abfall = Wolken, Tau oder starke Defokussierung. Allmählicher Rückgang = dünne Wolken oder steigende Luftfeuchtigkeit.

### Gewicht (Zusammengesetzter Qualitätswert)

| Aspekt | Details |
|--------|---------|
| **Was** | Einzelner Qualitätswert von 0 (schlechtester) bis 1 (bester) |
| **Quelle** | Vom Skript berechnet aus FWHM, Rundheit, Hintergrund, Sternen |
| **Erfordert** | Mindestens einige der obigen Messwerte müssen verfügbar sein |

**Formel:**
```
w_fwhm  = 1 − (fwhm − min) / (max − min)        [niedrigerer FWHM = besser]
w_round = roundness                                [höher = besser]
w_bg    = 1 − (bg − min) / (max − min)            [niedrigerer BG = besser]
w_stars = sqrt(stars) / sqrt(max_stars)            [mehr = besser]
Weight  = mean of available factors
```

**Interpretation:** Nach Gewicht aufsteigend sortieren, um die schlechtesten Bilder zuerst zu sehen. „Schlechteste N % aussortieren" mit Gewicht verwenden, um die qualitativ niedrigsten Einzelbilder zu entfernen.

### Median

| Aspekt | Details |
|--------|---------|
| **Was** | Medianpixelwert des gesamten Bildes, normalisiert auf [0, 1] |
| **Quelle** | Siril-Kanalstatistiken (`get_seq_stats`) |
| **Immer verfügbar** | Ja — keine Sternerkennung erforderlich |

**Interpretation:** Nahezu identisch mit dem Hintergrundpegel bei Astroaufnahmen, bei denen der Himmel dominiert. Nützlich als universelle Rückfallmetrik.

### Sigma (σ)

| Aspekt | Details |
|--------|---------|
| **Was** | Standardabweichung der Pixelwerte — misst die Streuung |
| **Quelle** | Siril-Kanalstatistiken |
| **Immer verfügbar** | Ja — keine Sternerkennung erforderlich |

**Interpretation:** Hohes Sigma + hoher Hintergrund = Rauschen durch Wolken (schlecht). Hohes Sigma + niedriger Hintergrund = echtes Deep-Sky-Signal (gut).

### Datum

| Aspekt | Details |
|--------|---------|
| **Was** | Beobachtungszeitstempel aus dem FITS-Header (`DATE-OBS`) |
| **Quelle** | FITS-Metadaten über `get_seq_imgdata` |
| **Hinweis** | Nicht alle Kameras schreiben dieses Feld (z. B. SeeStar S50) |

### Status

Zeigt **Eingeschlossen** (grün) oder **Ausgeschlossen** (rot). Änderungen sind lokal, bis Sie „Änderungen an Siril übertragen" klicken.

---

## 7. Anzeigemodi

### Normalmodus (Standard)

Standard-Autostreckungsansicht. Jedes Bild wird mit einer Mittelton-Transferfunktion (STF) gestreckt, die den Autostreckungsalgorithmus von Siril/PixInsight nachbildet. Gut für die allgemeine visuelle Prüfung.

**Verknüpfte Streckung** (Kontrollkästchen):
- **AN:** Gleiche Streckungsparameter für alle Bilder. Helligkeitsunterschiede zwischen Bildern werden sichtbar (Wolken, Hintergrundänderungen). Empfohlen zum Vergleichen von Bildern.
- **AUS:** Jedes Bild erhält seine eigene optimale Streckung. Zeigt die meisten Details in jedem einzelnen Bild, aber Bilder können hell/dunkel zu flackern scheinen.

### Differenzmodus (D-Taste)

Zeigt `|aktuelles_Bild − Referenzbild| × 5` — alles, was sich zwischen Bildern ändert, leuchtet als heller Fleck auf dunklem Hintergrund auf.

**Am besten geeignet zum Erkennen von:**
- Satellitenspuren (heller Streifen)
- Sich bewegenden Objekten (Asteroiden, Flugzeuge)
- Wolken (diffuses Leuchten)
- Nachführversatz

### Nur-Eingeschlossene-Modus

Die Wiedergabe überspringt alle ausgeschlossenen Bilder. Verwenden Sie diesen Modus nach dem Markieren, um zu überprüfen, ob die verbleibenden Bilder sauber aussehen.

### Nebeneinander-Modus

Zeigt das aktuelle Bild links und das Referenzbild rechts, mit synchronisiertem Zoom und Schwenken. Nützlich für direkten A/B-Vergleich.

### Zusätzliche Anzeigefunktionen

- **Überblendung:** Sanfte 200ms-Überblendung zwischen Bildern statt hartem Schnitt. Macht Bewegungsartefakte besser sichtbar.
- **Bild-Info-Overlay:** Zeigt Bildnummer, FWHM, Rundheit und Gewicht in der oberen linken Ecke. Ein-/ausschaltbar.
- **A/B-Umschalter (T-Taste):** Pinnen Sie das aktuelle Bild an, dann drücken Sie T, um zwischen dem angepinnten Bild und dem jeweiligen Navigationsbild hin und her zu wechseln.
- **ROI-Blinken:** Klicken Sie auf „ROI auswählen", zeichnen Sie ein Rechteck auf dem Bild, und der Betrachter zoomt in diesen Bereich. Perfekt zur Überprüfung von Sternformen in einer bestimmten Ecke.

---

## 8. Methoden zur Bildauswahl

### Methode 1: Manuelles Markieren (G / B-Tasten)

Der einfachste Ansatz — scrollen Sie durch Ihre Sequenz und markieren Sie jedes Bild:

1. Drücken Sie **Space** zum Abspielen oder verwenden Sie **←/→** zum schrittweisen Vor- und Zurückgehen
2. Drücken Sie **B**, wenn Sie ein schlechtes Bild sehen (ausschließen)
3. Drücken Sie **G**, um ein zuvor ausgeschlossenes Bild wieder einzuschließen
4. Bei aktiviertem **automatischen Weiterschalten** (Standard) springt der Betrachter nach dem Markieren zum nächsten Bild

**Am besten geeignet für:** Kleine Sequenzen (< 100 Bilder) oder die Überprüfung einzelner Bilder, die durch andere Methoden markiert wurden.

### Methode 2: Stapel-Aussortierung nach Schwellenwert

Alle Bilder aussortieren, die einen bestimmten Messwert überschreiten:

1. Wählen Sie im Abschnitt **Stapelauswahl** einen Messwert (FWHM, Hintergrund, Rundheit)
2. Wählen Sie einen Operator (>, <, >=, <=)
3. Geben Sie einen Schwellenwert ein
4. Die **Vorschau** zeigt, wie viele Bilder betroffen sind
5. Klicken Sie auf **„Übereinstimmende aussortieren"**

**Beispiel:** Alle Bilder mit FWHM > 4,5 aussortieren → entfernt alle Bilder mit aufgeblähten Sternen.

### Methode 3: Schlechteste N % aussortieren

Automatisch den unteren Prozentsatz der Bilder aussortieren:

1. Wählen Sie den Modus **„Schlechteste N %"**
2. Wählen Sie einen Messwert (FWHM, Hintergrund, Rundheit, Gewicht)
3. Legen Sie den Prozentsatz fest (z. B. 10 %)
4. Klicken Sie auf **„Übereinstimmende aussortieren"**

Für FWHM und Hintergrund bedeutet „schlechteste" = höchster Wert. Für Rundheit und Gewicht bedeutet „schlechteste" = niedrigster Wert.

**Beispiel:** Schlechteste 10 % nach Gewicht aussortieren → entfernt die 9 qualitativ niedrigsten Bilder aus einer 90-Bilder-Sequenz.

### Methode 4: Freigabeausdrücke (Mehrfachkriterien)

Definieren Sie mehrere Bedingungen, die gute Bilder gleichzeitig erfüllen müssen:

1. Klicken Sie auf **„+ Bedingung hinzufügen"**
2. Wählen Sie Messwert, Operator und Wert für jede Bedingung
3. Fügen Sie bei Bedarf weitere Bedingungen hinzu (UND-Logik)
4. Die Vorschau zeigt, wie viele Bilder durchfallen
5. Klicken Sie auf **„Nicht-Übereinstimmende aussortieren"**, um alle Bilder auszuschließen, die eine Bedingung nicht erfüllen

**Beispiel:**
```
FWHM < 4.5  AND  Roundness > 0.7  AND  Stars > 50
```
Dies behält nur Bilder mit scharfen, runden Sternen und guter Sternanzahl.

**Vergleichbar mit** den Freigabeausdrücken von PixInsight's SubframeSelector.

### Methode 5: Mehrfachauswahl in der Tabelle

Für die gezielte Entfernung bestimmter identifizierter Bilder:

1. Wechseln Sie zum Tab **Statistiktabelle**
2. **Ctrl+Klick** auf einzelne Zeilen oder **Shift+Klick** für einen Bereich
3. **Rechtsklick** auf die Auswahl → „N ausgewählte Bild(er) aussortieren"

**Am besten geeignet für:** Das Entfernen bestimmter Ausreißer, die Sie im Streudiagramm oder Diagramm identifiziert haben.

---

## 9. Das Rückgängig-System

Jede Markierungsaktion kann mit **Ctrl+Z** rückgängig gemacht werden:

- **Einzelne Markierungen** (G/B auf einem Bild) werden einzeln rückgängig gemacht
- **Stapeloperationen** (Schwellenwert-Aussortierung, schlechteste N %, Freigabeausdruck, Mehrfachauswahl) werden **komplett** mit einem einzigen Ctrl+Z rückgängig gemacht
- Tiefe des Rückgängig-Stapels: 500 Operationen

**Beispiel:** Sie sortieren die schlechtesten 15 % aus (13 Bilder). Sie bemerken, dass das zu aggressiv war. Ein Ctrl+Z stellt alle 13 Bilder wieder her.

---

## 10. Änderungen an Siril übertragen

Alle Markierungen sind **lokal**, bis Sie sie explizit übernehmen:

1. Der Zähler **„Ausstehend: N Änderungen"** im linken Panel zeigt, wie viele Bilder vom aktuellen Zustand in Siril abweichen
2. Klicken Sie auf **„Änderungen an Siril übertragen"**, um alle Änderungen zu senden
3. Ein Bestätigungsdialog zeigt die genauen Änderungen, die vorgenommen werden
4. Nach dem Übernehmen wird Sirils Sequenz aktualisiert — ausgeschlossene Bilder werden beim Stacken übersprungen

**Wenn Sie das Fenster mit nicht gespeicherten Änderungen schließen,** fragt ein Dialog, ob die Änderungen übernommen oder verworfen werden sollen.

---

## 11. Exportoptionen

### Ausgeschlossene Bilder exportieren (.txt)

Speichert eine Textdatei mit allen ausgeschlossenen Bildindizes. Enthält einen Header mit Sequenzname, Gesamtbildanzahl und Aussortierungsanzahl.

### Statistiken als CSV exportieren (.csv)

Exportiert die vollständige Statistiktabelle als CSV-Datei mit den Spalten:
`Frame, Weight, FWHM, Roundness, Background, Stars, Median, Sigma, Date, Included`

Nützlich für externe Analysen in Tabellenkalkulationen, Python-Notebooks oder anderen Werkzeugen.

### Animiertes GIF exportieren (.gif)

Erstellt ein animiertes GIF der Blinkanimation:
- Nur eingeschlossene Bilder (ausgeschlossene Bilder werden übersprungen)
- Skaliert auf maximal 480px Abmessung
- Verwendet die aktuelle Wiedergabegeschwindigkeit (FPS)
- Erfordert die Pillow-Bibliothek (`pip install Pillow`)

Ideal zum Teilen in Foren, sozialen Medien oder Beobachtungsberichten.

### Bild in Zwischenablage kopieren (Ctrl+C)

Kopiert das aktuelle Bild (wie angezeigt, mit angewandter Streckung) in die Systemzwischenablage. Direkt in einen Forenbeitrag, Bildbearbeitungsprogramm oder eine Präsentation einfügbar.

---

## 12. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Schnelle Sitzungsprüfung (5 Minuten)

**Szenario:** Sie haben gerade eine Aufnahmesession mit 120 Einzelbildern beendet und möchten eine schnelle Qualitätsprüfung vor dem Stacken.

**Arbeitsablauf:**
1. Laden Sie die registrierte Sequenz in Siril
2. Starten Sie den Blink Comparator
3. Führen Sie bei Bedarf die Sternerkennung aus (klicken Sie auf das gelbe Banner)
4. Wechseln Sie zum Tab **Statistiktabelle**, sortieren Sie nach **FWHM absteigend** — die schlechtesten Bilder stehen nun oben
5. Klicken Sie auf **„Schlechteste 10 % aussortieren"** nach FWHM
6. Überprüfen Sie das **Statistikdiagramm** — suchen Sie nach verbliebenen Ausreißern
7. Änderungen übernehmen → in Siril stacken

**Zeitaufwand:** ~5 Minuten für 120 Bilder.

### Anwendungsfall 2: Von Wolken betroffene Sitzung

**Szenario:** Während Ihrer Sitzung zogen Wolken durch. Einige Bilder sind teilweise bewölkt.

**Arbeitsablauf:**
1. Öffnen Sie den Blink Comparator
2. Wechseln Sie zum Tab **Statistikdiagramm**, aktivieren Sie das Kontrollkästchen **Hintergrund**
3. Suchen Sie nach Spitzen — das sind die bewölkten Bilder
4. Verwenden Sie **Stapel-Aussortierung**: Hintergrund > [Schwellenwert aus dem Spitzenpegel]
5. Prüfen Sie auch **Sterne** — bewölkte Bilder haben weniger erkannte Sterne
6. Überprüfen Sie im **Differenzmodus** (D-Taste) — Wolkenflecken leuchten hell auf

### Anwendungsfall 3: Diagnose von Nachführproblemen

**Szenario:** Einige Bilder zeigen längliche Sterne. Sie möchten diese finden und entfernen und verstehen, wann das Problem aufgetreten ist.

**Arbeitsablauf:**
1. Öffnen Sie den Blink Comparator
2. Gehen Sie zum **Statistikdiagramm**, aktivieren Sie **Rundheit**
3. Suchen Sie nach Einbrüchen — das sind Bilder mit Nachführfehlern
4. Verwenden Sie einen **Freigabeausdruck**: `Roundness > 0.75`
5. „Nicht-Übereinstimmende aussortieren" entfernt alle Bilder mit länglichen Sternen
6. Prüfen Sie das **Streudiagramm** (FWHM vs. Rundheit) — Ausreißer-Bilder liegen weit vom Cluster entfernt
7. Klicken Sie auf Ausreißer-Punkte, um einzelne Bilder zu untersuchen
8. Wenn sich die Nachführfehler in einem Zeitraum häufen, haben Sie möglicherweise einen periodischen Fehler in Ihrer Montierung

### Anwendungsfall 4: Sitzung mit Fokusdrift

**Szenario:** Ihr FWHM beginnt gut, steigt aber im Laufe der Sitzung allmählich an, da die Temperatur sinkt und sich der Fokus verschiebt.

**Arbeitsablauf:**
1. Öffnen Sie den Blink Comparator
2. **Statistikdiagramm** → FWHM zeigt einen ansteigenden Verlauf
3. Der **gleitende Durchschnitt** (fette Linie) zeigt den Trend deutlich
4. Verwenden Sie **Stapel-Aussortierung**: FWHM > [Ihr Schwellenwert, z. B. 4,5]
5. Oder verwenden Sie **„Schlechteste 20 % aussortieren"** nach FWHM — dies entfernt automatisch die Bilder vom Ende der Sitzung
6. Tipp: Verwenden Sie in zukünftigen Sitzungen einen Autofokussierer oder fokussieren Sie alle 30 Minuten nach

### Anwendungsfall 5: Satellitenspuren-Suche

**Szenario:** Sie fotografieren nahe des Himmelsäquators, wo Satellitenspuren häufig sind.

**Arbeitsablauf:**
1. Öffnen Sie den Blink Comparator
2. Drücken Sie **D** für den **Differenzmodus** — Satelliten erscheinen als helle Streifen vor dunklem Hintergrund
3. Drücken Sie **Space** zum Abspielen mit 3–5 FPS — Spuren blitzen sichtbar auf
4. Wenn Sie eine entdecken, drücken Sie **B**, um dieses Bild auszuschließen
5. Spielen Sie weiter ab, um alle Spuren zu finden
6. Der Differenzmodus macht Spuren **viel** sichtbarer als der Normalmodus

### Anwendungsfall 6: Datengestützte Auswahl (Ersatz für PI SubframeSelector)

**Szenario:** Sie möchten einen quantitativen, PixInsight-artigen Auswahlprozess basierend auf mehreren Kriterien.

**Arbeitsablauf:**
1. Führen Sie die Sternerkennung aus, um alle Messwerte zu befüllen
2. Gehen Sie zur **Statistiktabelle**, sortieren Sie nach **Gewicht aufsteigend** (schlechteste Bilder zuerst)
3. Überprüfen Sie die unteren 10–20 % — sehen sie sichtbar schlechter aus?
4. Richten Sie einen **Freigabeausdruck** ein:
   ```
   FWHM < 4.0 AND Roundness > 0.75 AND Background < 0.012 AND Stars > 40
   ```
5. Die Vorschau zeigt, dass N Bilder aussortiert würden
6. Klicken Sie auf „Nicht-Übereinstimmende aussortieren"
7. Überprüfen Sie im **Streudiagramm** (FWHM vs. Rundheit) — der verbleibende Cluster sollte kompakt sein
8. **CSV exportieren** für Ihre Aufzeichnungen
9. Änderungen übernehmen → stacken

### Anwendungsfall 7: Vorher-Nachher-Vergleich

**Szenario:** Sie möchten überprüfen, ob Ihre Bildauswahl die verbleibende Menge tatsächlich verbessert hat.

**Arbeitsablauf:**
1. Notieren Sie nach dem Markieren der Bilder die **Sitzungszusammenfassungs-Statistiken** (mittlerer FWHM, Anzahl eingeschlossener Bilder)
2. Wechseln Sie zum Anzeigemodus **„Nur eingeschlossene"**
3. Abspielen — überprüfen Sie, dass die Animation flüssig aussieht, ohne Flackern oder Artefakte
4. Prüfen Sie das **Statistikdiagramm** — die roten Punkte (ausgeschlossen) sollten an den Spitzen liegen
5. Die verbleibende blaue Linie sollte gleichmäßiger verlaufen
6. **GIF exportieren** der sauberen Sequenz für Ihr Aufnahmeprotokoll

### Anwendungsfall 8: Sternformprüfung in den Ecken

**Szenario:** Sie vermuten optische Verkippung oder Koma in einer Ecke und möchten dies über alle Bilder prüfen.

**Arbeitsablauf:**
1. Klicken Sie auf **„ROI auswählen"** in den Anzeigeoptionen
2. Zeichnen Sie ein Rechteck über die problematische Ecke
3. Klicken Sie auf **1:1** Zoom für pixelgenaue Ansicht
4. Spielen Sie die Animation ab — Sternformen in dieser Ecke blinken schnell durch
5. Bilder, in denen die Ecksterne schlechter als üblich sind, könnten Biegungs- oder Kippungsänderungen aufweisen
6. Markieren Sie diese Bilder mit B
7. Klicken Sie auf „ROI löschen", um zur Vollbildansicht zurückzukehren

---

## 13. Tastaturkürzel

### Wiedergabe

| Taste | Aktion |
|-------|--------|
| `Space` | Abspielen / Pause |
| `←` | Vorheriges Bild |
| `→` | Nächstes Bild |
| `Home` | Erstes Bild |
| `End` | Letztes Bild |
| `1`–`9` | FPS direkt einstellen |
| `+` | Beschleunigen (FPS erhöhen) |
| `-` | Verlangsamen (FPS verringern) |

### Bildmarkierung

| Taste | Aktion |
|-------|--------|
| `G` | Als gut markieren (einschließen) |
| `B` | Als schlecht markieren (ausschließen) |
| `Ctrl+Z` | Letzte Markierung rückgängig machen (einzeln oder Stapel) |

### Anzeige

| Taste | Aktion |
|-------|--------|
| `D` | Differenzmodus umschalten |
| `Z` | Zoom auf Fensterpassung zurücksetzen |
| `T` | Aktuelles Bild anpinnen / A/B-Vergleich umschalten |
| `Ctrl+C` | Aktuelles Bild in die Zwischenablage kopieren |

### Sonstiges

| Taste | Aktion |
|-------|--------|
| `Esc` | Fenster schließen |

---

## 14. Tipps & Empfehlungen

### Allgemeiner Arbeitsablauf

1. **Beginnen Sie mit Daten, dann prüfen Sie visuell.** Sortieren Sie zuerst nach FWHM oder Gewicht, um fehlerhafte Bilder numerisch zu identifizieren. Wechseln Sie dann zum Betrachter, um zu bestätigen, dass sie tatsächlich schlecht aussehen.

2. **Sortieren Sie nicht zu viel aus.** Mehr Bilder = weniger Rauschen im Stack. Sortieren Sie nur Bilder aus, die eindeutig fehlerhaft sind. Ein Bild mit FWHM 4,2, wenn Ihr bestes 3,0 hat, trägt immer noch Signal bei — erwägen Sie, es zu behalten, es sei denn, es ist ein Ausreißer.

3. **Nutzen Sie den gleitenden Durchschnitt.** Im Statistikdiagramm zeigt die fette Trendlinie Muster (Fokusdrift, Wolken), die in der verrauschten Rohdatenlinie unsichtbar sind.

4. **Prüfen Sie das Streudiagramm.** FWHM vs. Rundheit ist die informativste Einzelkombination. Der Hauptcluster repräsentiert Ihre „normalen" Bilder. Ausreißer weit vom Cluster entfernt sind Ihre Aussortierungskandidaten.

5. **Verwenden Sie immer den Differenzmodus für Satelliten.** Sie sind manchmal im Normalmodus unsichtbar, leuchten aber im Differenzmodus wie Neonreklamen.

### Leistungstipps

6. **Der erste Durchlauf ist langsam, nachfolgende sind schnell.** Das Skript speichert Statistiken und Vorschauen im Cache. Die Navigation zwischen Bildern ist nach dem Caching sofort.

7. **Große Sequenzen (500+ Bilder):** Das Laden der Statistiken kann eine Minute dauern. Haben Sie Geduld — es passiert nur einmal pro Sitzung.

8. **Wiedergabegeschwindigkeit:** Wenn die Wiedergabe bei hohen FPS ruckelt, reduzieren Sie die Geschwindigkeit. Der Bild-Cache lädt voraus, aber sehr hohe FPS bei großen Bildern können den Cache überholen.

### Siril-Integration

9. **Immer zuerst registrieren.** Der Blink Comparator funktioniert mit jeder Sequenz, aber am besten mit registrierten (ausgerichteten) Sequenzen. Der Differenzmodus und der Nebeneinander-Modus erfordern eine Ausrichtung, um aussagekräftig zu sein.

10. **Sternerkennung ist unabhängig von der Registrierung.** Ihr Vorverarbeitungsskript kann die Sequenz registrieren, ohne den FWHM pro Bild zu berechnen. Deshalb erscheint das Banner „Sternerkennung ausführen". Das Anklicken ist sicher — es verändert Ihre Dateien nicht.

11. **Änderungen sind nicht-destruktiv.** „Änderungen übernehmen" setzt nur das Ein-/Ausschlussflag in der .seq-Datei. Ihre FITS-Dateien werden niemals verändert oder gelöscht.

---

## 15. Fehlerbehebung

### Fehler „Keine Sequenz geladen"

**Ursache:** Keine Sequenz ist in Siril aktiv.
**Lösung:** Setzen Sie das Arbeitsverzeichnis auf den Ordner, der Ihre `.seq`-Datei und `.fit`-Dateien enthält. Siril sollte die Sequenz automatisch erkennen.

### FWHM / Rundheit / Sterne-Spalten sind leer

**Ursache:** Die Sternerkennung wurde für diese Sequenz nicht ausgeführt.
**Lösung:** Klicken Sie auf das gelbe Banner „Sternerkennung ausführen". Dies führt `register <seq> -2pass` aus, das alle Sternmetriken berechnet, ohne neue Dateien zu erstellen.

### Sternerkennung wurde ausgeführt, aber Spalten sind weiterhin leer

**Ursache:** Bei RGB-Bildern speichert Siril die Registrierungsdaten im grünen Kanal (Kanal 1). Ältere Versionen des Skripts haben möglicherweise nur Kanal 0 geprüft.
**Lösung:** Aktualisieren Sie auf die neueste Version des Skripts. Es durchsucht alle Kanäle.

### Schriftart-Warnung: „Sans-serif"

**Meldung:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"...`
**Auswirkung:** Nur kosmetisch, keine Auswirkung auf die Funktionalität.

### Skript stürzt beim Schließen mit SortOrder-Fehler ab

**Meldung:** `TypeError: int() argument must be a string... not 'SortOrder'`
**Lösung:** Aktualisieren Sie auf die neueste Version (behoben in v1.2.3+).

### GIF-Export schlägt fehl

**Ursache:** Die Pillow-Bibliothek ist nicht installiert.
**Lösung:** Im Terminal: `pip install Pillow` (oder Installation über Sirils Python-Umgebung).

### Wiedergabe ist langsam / ruckelt

**Ursache:** Große Bildabmessungen oder unzureichender Arbeitsspeicher für den Bild-Cache.
**Lösung:**
- Reduzieren Sie die Wiedergabegeschwindigkeit (verwenden Sie 3–5 FPS statt 30)
- Der Cache hält standardmäßig 80 Bilder — ausreichend für die meisten Sequenzen
- Schließen Sie andere speicherintensive Anwendungen

---

## 16. Häufige Fragen

**F: Ersetzt dies PixInsight's Blink + SubframeSelector?**
A: Für visuelle Prüfung und grundlegende Bildauswahl ja — es bietet tatsächlich mehr Visualisierungsfunktionen als PI Blink (Differenzmodus, Nebeneinander, A/B-Umschalter, ROI-Blinken, Überblendung, Filmstreifen). Auf der statistischen Seite deckt es die meisten Funktionen von SubframeSelector ab (sortierbare Tabelle, Stapel-Aussortierung, Freigabeausdrücke, Streudiagramm), aber PI hat SNR und die proprietäre PSFSignalWeight-Metrik, die wir nicht nachbilden.

**F: Kann ich dies auf nicht-registrierten Sequenzen verwenden?**
A: Ja, aber der Differenzmodus und der Nebeneinander-Modus sind dann nicht sinnvoll, da die Bilder nicht ausgerichtet sind. Visuelles Blinken im Normalmodus funktioniert weiterhin.

**F: Verändert „Änderungen übernehmen" meine FITS-Dateien?**
A: Nein. Es aktualisiert nur das Ein-/Ausschlussflag in der `.seq`-Datei. Ihre FITS-Dateien werden niemals verändert.

**F: Wie stark verbessert das Aussortieren von Bildern den Stack?**
A: Das hängt von Ihren Daten ab. Das Entfernen von 5–10 % der schlechtesten Bilder verbessert den Stack oft merklich — schärfere Sterne, weniger Rauschen im Hintergrund. Das Entfernen von mehr als 20–30 % bringt meist abnehmende Erträge (Sie verlieren mehr Signal als Sie an Qualität gewinnen).

**F: Was ist der Unterschied zwischen „verknüpfter" und „unabhängiger" Streckung?**
A: **Verknüpft** verwendet die gleiche Streckung für alle Bilder — Helligkeitsunterschiede zwischen Bildern werden sichtbar (gut zum Erkennen von Wolken). **Unabhängig** optimiert jedes Bild einzeln — Sie sehen die meisten Details in jedem Bild, aber die Animation kann zu flackern scheinen.

**F: Kann ich ausgeschlossene Bilder wieder einschließen?**
A: Ja. Drücken Sie **G** auf einem ausgeschlossenen Bild, um es wieder einzuschließen. Oder verwenden Sie **Ctrl+Z**, um die letzte Markierungsoperation rückgängig zu machen.

**F: Warum zeigt die Gewicht-Spalte für alle Bilder 0 an?**
A: Das Gewicht erfordert FWHM-, Rundheit-, Hintergrund- und Sterne-Daten. Wenn die Sternerkennung nicht durchgeführt wurde, sind alle Eingabewerte 0, also ist auch das Gewicht 0. Führen Sie zuerst die Sternerkennung aus.

**F: Kann ich dies für Planetenaufnahmen verwenden?**
A: Das Werkzeug ist für die Deep-Sky-Bildauswahl konzipiert. Planetenaufnahmen (Lucky Imaging) verwenden andere Qualitätsmetriken und verarbeiten typischerweise Tausende sehr kurzer Belichtungen. Werkzeuge wie AutoStakkert oder Planetary System Stacker sind für Planetenaufnahmen besser geeignet.

---

## Danksagung

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die außerdem enthält:
- Svenesis Gradient Analyzer
- Svenesis Annotate Image
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn Sie dieses Werkzeug nützlich finden, unterstützen Sie die Entwicklung gerne über [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
