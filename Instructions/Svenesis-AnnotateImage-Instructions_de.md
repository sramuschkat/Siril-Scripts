# Svenesis Annotate Image — Benutzeranleitung

**Version 1.1.0** | Siril-Python-Skript zur Beschriftung von Plate-Solved-Bildern

> *Vergleichbar mit PixInsights AnnotateImage-Skript — aber kostenlos, quelloffen und eng in Siril integriert.*

---

## Inhaltsverzeichnis

1. [Was ist Annotate Image?](#1-was-ist-annotate-image)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Die Kataloge im Überblick](#6-die-kataloge-im-überblick)
7. [Objekttypen & Farbcodierung](#7-objekttypen--farbcodierung)
8. [Anzeigeoptionen](#8-anzeigeoptionen)
9. [Extras (Overlays)](#9-extras-overlays)
10. [Ausgabeoptionen](#10-ausgabeoptionen)
11. [Anwendungsfälle & Arbeitsabläufe](#11-anwendungsfälle--arbeitsabläufe)
12. [Tastaturkürzel](#12-tastaturkürzel)
13. [Tipps & Empfehlungen](#13-tipps--empfehlungen)
14. [Fehlerbehebung](#14-fehlerbehebung)
15. [Häufige Fragen](#15-häufige-fragen)

---

## 1. Was ist Annotate Image?

Das **Svenesis Annotate Image**-Skript nimmt Ihr Plate-Solved-Astrofoto und erstellt eine ansprechend beschriftete Version mit benannten Deep-Sky-Objekten, benannten Sternen, Koordinatengittern und Feldinformationen — fertig zum Teilen in sozialen Medien, Foren oder zum Drucken.

Stellen Sie es sich als eine **Beschriftungsmaschine** für Ihre Astrofotos vor. Es kombiniert:

- **Automatische Objekterkennung** — findet Galaxien, Nebel, Sternhaufen, Sterne und mehr in Ihrem Bildfeld durch parallele Abfrage von 5 Online-Datenquellen via VizieR und SIMBAD
- **Darstellung in Publikationsqualität** — farbcodierte Markierungen, Ellipsen skaliert auf die tatsächliche Objektgröße und saubere Labelplatzierung mit Kollisionsvermeidung
- **Umfangreiche Overlays** — Koordinatengitter, Infobox, Kompassrose und Farblegende
- **Export mit einem Klick** — speichert beschriftete Bilder als PNG, TIFF oder JPEG mit konfigurierbarer DPI

Das Ergebnis: ein professionell aussehendes, beschriftetes Bild, das genau zeigt, welche Objekte sich in Ihrem Bildfeld befinden — perfekt zum Teilen, Lernen oder Dokumentieren Ihrer Aufnahmesitzungen.

---

## 2. Hintergrundwissen für Einsteiger

### Was ist Plate Solving?

**Plate Solving** ist der Prozess, bei dem die exakten Himmelskoordinaten Ihres Bildes bestimmt werden. Dabei wird das Sternmuster in Ihrem Foto mit einem Sternkatalog abgeglichen, um herauszufinden, wohin Ihr Teleskop gerichtet war.

Nach dem Plate Solving hat Ihr Bild eine **WCS (World Coordinate System)**-Lösung in seinem FITS-Header eingebettet. Diese teilt der Software mit: „Pixel (500, 300) entspricht RA 12h 30m, DEC +41° 20'" — und so weiter für jeden Pixel.

| Konzept | Erklärung |
|---------|-----------|
| **RA (Right Ascension)** | Die „Längengrad"-Koordinate des Himmels, gemessen in Stunden (0h – 24h). Entspricht einer Ost-West-Position auf der Himmelskugel. |
| **DEC (Declination)** | Die „Breitengrad"-Koordinate des Himmels, gemessen in Grad (-90° bis +90°). Der Himmelsäquator liegt bei 0°, der nördliche Himmelspol bei +90°. |
| **WCS** | World Coordinate System — die mathematische Zuordnung zwischen Pixelkoordinaten und Himmelskoordinaten, gespeichert im FITS-Header. |
| **FOV (Field of View)** | Wie viel Himmel Ihr Bild abdeckt, gemessen in Bogenminuten oder Grad. Hängt von Ihrer Brennweite und Sensorgröße ab. |
| **Pixelskala** | Wie viele Bogensekunden des Himmels jeder Pixel abdeckt (arcsec/pixel). Kleinere Werte = höhere Auflösung. |

### Warum sollten Sie Ihre Bilder beschriften?

Das Beschriften Ihrer Astrofotos dient mehreren Zwecken:

1. **Lernen** — Entdecken Sie, welche Objekte sich in Ihrem Bildfeld verbergen. Viele Astrofotografen sind überrascht, schwache Galaxien oder Nebel zu finden, von deren Existenz sie nichts wussten.
2. **Teilen** — Wenn Sie ein Bild in sozialen Medien oder einem Forum veröffentlichen, hilft eine beschriftete Version den Betrachtern zu verstehen, was sie sehen.
3. **Dokumentation** — Führen Sie Aufzeichnungen über Ihre Aufnahmen mit präzisen Koordinaten und Feldinformationen.
4. **Planung** — Wenn Sie sehen, was in Ihrem Bildfeld ist, können Sie entscheiden, ob Sie zuschneiden, den Bildausschnitt ändern oder das Gebiet erneut mit einer anderen Brennweite aufnehmen möchten.

### Was sind Deep-Sky-Objekte?

Deep-Sky-Objekte (DSOs) sind alle Objekte jenseits unseres Sonnensystems. Sie kommen in vielen Typen vor:

| Typ | Was ist das? | Beispiel |
|-----|-------------|----------|
| **Galaxie** | Eine riesige Ansammlung von Milliarden von Sternen, Gas und Staub | M31 (Andromeda), M51 (Whirlpool) |
| **Emissionsnebel** | Eine Gaswolke, die leuchtet, wenn sie von nahen heißen Sternen angeregt wird | M42 (Orionnebel), NGC 7000 (Nordamerikanebel) |
| **Reflexionsnebel** | Eine Staubwolke, die Licht naher Sterne reflektiert (bläulich) | M78, NGC 7023 (Irisnebel) |
| **Planetarischer Nebel** | Eine Gashülle, die von einem sterbenden Stern ausgestoßen wird (hat nichts mit Planeten zu tun!) | M57 (Ringnebel), M27 (Hantelnebel) |
| **Offener Sternhaufen** | Eine lockere Gruppe junger Sterne, die gemeinsam entstanden sind | M45 (Plejaden), NGC 869 (Doppelsternhaufen) |
| **Kugelsternhaufen** | Eine dichte, uralte Kugel aus Hunderttausenden von Sternen | M13, NGC 5139 (Omega Centauri) |
| **Supernova-Überrest** | Die sich ausbreitenden Trümmer eines explodierten Sterns | M1 (Krebsnebel), NGC 6960 (Schleiernebel) |
| **Dunkelnebel** | Eine undurchsichtige Staubwolke, die das Licht dahinterliegender Objekte blockiert | B33 (Pferdekopfnebel), B78 (Pfeifennebel) |
| **HII-Region** | Ein großes Gebiet aus ionisiertem Wasserstoff — im Wesentlichen ein riesiger Emissionsnebel | Sh2-155 (Höhlennebel), Sh2-240 (Simeis 147) |
| **Asterismus** | Ein Sternmuster, das kein echter Sternhaufen ist | Kleiderbügel, Kembles Kaskade |
| **Quasar** | Ein quasistellares Objekt oder aktiver Galaxienkern | 3C 273, Markarian 421 |

### Was ist Helligkeit (Magnitude)?

Die **Magnitude** misst, wie hell ein Objekt erscheint. Die Skala ist invertiert und logarithmisch:

- **Niedrigere Zahlen = heller** (Sirius, der hellste Stern, hat Magnitude -1,5)
- **Höhere Zahlen = schwächer** (die schwächsten Objekte, die Ihre Kamera erfassen kann, können Magnitude 15+ haben)
- Jeder Schritt von 1 Magnitude entspricht etwa dem 2,5-fachen an Helligkeit

Der Grenzhelligkeitsregler in Annotate Image steuert die schwächsten Objekte, die beschriftet werden. Ein Grenzwert von 12,0 erfasst die meisten visuell interessanten Objekte. Gehen Sie höher (14–16), um schwächere Galaxien zu beschriften; gehen Sie niedriger (8–10) für eine sauberere, weniger überladene Beschriftung.

---

## 3. Voraussetzungen & Installation

### Anforderungen

| Komponente | Mindestversion | Hinweise |
|------------|---------------|----------|
| **Siril** | 1.4.0+ | Python-Skriptunterstützung muss aktiviert sein |
| **sirilpy** | Mitgeliefert | Wird mit Siril 1.4+ ausgeliefert |
| **numpy** | Beliebig aktuell | Wird automatisch vom Skript installiert |
| **PyQt6** | 6.x | Wird automatisch vom Skript installiert |
| **matplotlib** | 3.x | Wird automatisch vom Skript installiert |
| **astropy** | Beliebig aktuell | Wird automatisch vom Skript installiert |
| **astroquery** | Beliebig aktuell | Wird automatisch vom Skript installiert — erforderlich für alle Katalogabfragen |
| **Internetverbindung** | — | Erforderlich für die Live-Abfragen von VizieR und SIMBAD |

### Installation

1. Laden Sie `Svenesis-AnnotateImage.py` vom [GitHub-Repository](https://github.com/sramuschkat/Siril-Scripts) herunter.
2. Legen Sie die Datei in Ihrem Siril-Skriptverzeichnis ab:
   - **macOS:** `~/Library/Application Support/org.siril.Siril/siril/scripts/`
   - **Linux:** `~/.local/share/siril/scripts/`
   - **Windows:** `%APPDATA%\Siril\scripts\`
3. Starten Sie Siril neu. Das Skript erscheint unter **Verarbeitung → Skripte**.

Das Skript installiert fehlende Python-Abhängigkeiten (`numpy`, `PyQt6`, `matplotlib`, `astropy`, `astroquery`) automatisch beim ersten Start.

---

## 4. Erste Schritte

### Schritt 1: Ein Plate-Solved-Bild laden

Das Skript benötigt ein **Plate-Solved-Bild**, das in Siril geladen ist. Das bedeutet, Ihr FITS-Bild muss WCS-Koordinaten in seinem Header enthalten.

**Wenn Ihr Bild bereits Plate-Solved ist:**
1. Öffnen Sie das Bild in Siril (Datei → Öffnen oder per Drag & Drop).
2. Sie können loslegen!

**Wenn Ihr Bild NICHT Plate-Solved ist:**
1. Laden Sie das Bild in Siril.
2. Gehen Sie zu **Werkzeuge → Astrometrie → Bild-Plate-Solver...**
3. Geben Sie die ungefähren Koordinaten Ihres Ziels ein (oder lassen Sie Siril sie automatisch erkennen).
4. Klicken Sie auf **Lösen**. Siril gleicht Ihr Sternfeld mit einem Katalog ab und berechnet die WCS-Lösung.
5. Speichern Sie das Bild (die WCS-Daten werden im FITS-Header gespeichert).

**Woher weiß ich, ob mein Bild Plate-Solved ist?**
- In Siril zeigen Plate-Solved-Bilder Koordinateninformationen in der Statusleiste am unteren Rand.
- Das Annotate Image-Skript überprüft dies automatisch und informiert Sie, wenn das Bild nicht Plate-Solved ist.

### Schritt 2: Das Skript ausführen

Gehen Sie zu **Verarbeitung → Skripte → Svenesis Annotate Image**.

Das Skript öffnet ein Fenster mit:
- Einem **linken Bereich** mit allen Konfigurationsoptionen
- Einem **rechten Bereich** mit einer Vorschau und Protokollausgabe
- Einer Infoleiste mit Bildabmessungen und Plate-Solve-Status

### Schritt 3: Ihre Beschriftung konfigurieren

1. **Objekttypen auswählen** — Aktivieren oder deaktivieren Sie, welche Objektarten beschriftet werden sollen (Galaxien, Nebel, Sterne usw.)
2. **Grenzwert für Helligkeit festlegen** — Steuert, wie schwach Objekte sein dürfen. 12,0 ist ein guter Standardwert.
3. **Anzeigeeinstellungen anpassen** — Schriftgröße, Markierungsgröße, gebräuchliche Namen usw.
4. **Overlays wählen** — Koordinatengitter, Infobox, Kompass, Legende
5. **Ausgabeformat festlegen** — PNG (empfohlen), TIFF oder JPEG mit DPI-Einstellung

### Schritt 4: Beschriften!

Klicken Sie auf **„Annotate Image"** (oder drücken Sie **F5**).

Das Skript wird:
1. Das Bild und die WCS-Daten aus Siril laden
2. Alle Online-Kataloge parallel nach Objekten in Ihrem Bildfeld abfragen (VizieR und SIMBAD werden gleichzeitig abgefragt)
3. Ergebnisse über alle Kataloge hinweg deduplizieren
4. Labelkollisionen auflösen, damit sich Beschriftungen nicht überlappen
5. Das beschriftete Bild mit allen ausgewählten Overlays rendern
6. Die Ausgabedatei im Arbeitsverzeichnis von Siril speichern

Ein Fortschrittsbalken zeigt den aktuellen Schritt an. Nach Abschluss erscheint das beschriftete Bild in der **Vorschau**-Registerkarte.

### Schritt 5: Ihr Ergebnis ansehen

- Klicken Sie auf **„Beschriftetes Bild öffnen"**, um die Ausgabe in voller Auflösung in Ihrem Standard-Bildbetrachter anzuzeigen
- Klicken Sie auf **„Ausgabeordner öffnen"**, um zum Ausgabeverzeichnis zu navigieren
- Überprüfen Sie die **Protokoll**-Registerkarte für Details darüber, welche Kataloge durchsucht wurden, wie viele Objekte gefunden wurden und den Pfad der Ausgabedatei

---

## 5. Die Benutzeroberfläche

Das Fenster ist in zwei Hauptbereiche unterteilt:

### Linker Bereich (Steuerungspanel)

Die linke Seite (360px breit) enthält alle Konfigurationsoptionen, organisiert in aufklappbaren Abschnitten:

- **Objekte beschriften:** Objekttyp-Kontrollkästchen mit farbcodierten Labels im Zwei-Spalten-Layout. Die linke Spalte enthält häufige Typen, die standardmäßig EIN sind (Galaxien, Nebel, Planetarische Nebel, Offene Sternhaufen, Kugelsternhaufen, Sterne). Die rechte Spalte enthält spezialisierte Typen, die standardmäßig AUS sind (Reflexionsnebel, Supernova-Überreste, Dunkelnebel, HII-Regionen, Asterismen, Quasare). Alle auswählen / Alle abwählen-Schaltflächen am unteren Rand.
- **Anzeige:** Schriftgröße, Markierungsgröße, Grenzwert für Helligkeit (alle mit Schiebereglern). Kontrollkästchen im Zwei-Spalten-Layout unter den Schiebereglern für Ellipsen, Helligkeitslabels, Typlabels, gebräuchliche Namen und Farbcodierung nach Typ.
- **Extras:** Koordinatengitter, Infobox, Kompass, Farblegende, Verbindungslinien
- **Ausgabe:** Formatauswahl (PNG/TIFF/JPEG), DPI-Schieberegler (72–300), Basisdateiname
- **Aktionen:** „Annotate Image"-Schaltfläche, Fortschrittsbalken, Statusanzeige

Am unteren Rand: **Buy me a Coffee**-, **Hilfe**- und **Schließen**-Schaltflächen.

### Rechter Bereich (Vorschau & Protokoll)

Der Hauptbereich hat zwei Registerkarten:

#### Vorschau-Registerkarte
Zeigt das beschriftete Ausgabebild nach dem Rendern an. Die Vorschau skaliert passend zum Fenster und passt ihr Seitenverhältnis an, wenn das Fenster vergrößert oder verkleinert wird. Vor der Beschriftung wird „Vorschau erscheint hier nach der Beschriftung" angezeigt.

#### Protokoll-Registerkarte
Ein Textbereich in Festbreitenschrift mit detaillierten Fortschritts- und Diagnoseinformationen:
- Bildabmessungen und Plate-Solve-Status
- Verwendete WCS-Erkennungsstrategie
- Zentrumskoordinaten und Pixelskala
- Objektanzahl pro Katalog
- Jedes beschriftete Objekt mit Name, Typ und Helligkeit
- Pfad und Größe der Ausgabedatei

### Infoleiste

Über den Registerkarten zeigt eine Statusleiste:
- Bildabmessungen (z. B. „4656 × 3520 px")
- Farbmodus („RGB" oder „Mono")
- Plate-Solve-Status („plate-solved ✓" oder „NOT plate-solved ✗")

### Ausgabe-Schaltflächen

Unter den Registerkarten:
- **Ausgabeordner öffnen** — öffnet das Verzeichnis mit der Ausgabedatei
- **Beschriftetes Bild öffnen** — öffnet das beschriftete Bild in Ihrem Standard-Bildbetrachter

---

## 6. Die Kataloge im Überblick

Das Skript fragt **5 Online-Datenquellen** parallel über Live-VizieR- und SIMBAD-Abfragen ab. Es gibt keine eingebetteten Kataloge — alle Objektdaten kommen zum Zeitpunkt der Beschriftung aus dem Internet.

| Datenquelle | Katalog-ID | Inhalt |
|-------------|-----------|--------|
| **VizieR VII/118** | NGC 2000.0 | NGC-, IC- und Messier-Objekte — die wichtigsten Deep-Sky-Kataloge für Galaxien, Nebel und Sternhaufen |
| **VizieR VII/20** | Sharpless (1959) | HII-Regionen — ionisierte Wasserstoff-Emissionskomplexe, am besten für Weitfeld-Milchstraßenbilder |
| **VizieR VII/220A** | Barnard (1927) | Dunkelnebel — undurchsichtige Staubwolken, die Hintergrundlicht blockieren |
| **VizieR V/50** | Yale Bright Star Catalogue (BSC) | Benannte helle Sterne zur Feldidentifikation |
| **SIMBAD** | TAP-Abfrage | UGC-, Abell-, Arp-, Hickson-, Markarian-, vdB-, PGC-, MCG-Objekte, plus Auflösung gebräuchlicher Namen für alle Objekte |

### Wie die Kataloge funktionieren

Alle 5 Datenquellen werden **immer parallel** über einen ThreadPoolExecutor abgefragt — die Objekttyp-Kontrollkästchen steuern, *welche Arten* von Objekten angezeigt werden, nicht welche Kataloge durchsucht werden. Wenn Sie beispielsweise nur „Galaxien" aktivieren, fragt das Skript alle 5 Quellen ab, zeigt aber nur Galaxien-Typ-Objekte aus allen Quellen an.

Das bedeutet:
- **M31** stammt aus VizieR NGC 2000.0 als Galaxie
- **NGC 7000** stammt aus VizieR NGC 2000.0 als Emissionsnebel
- **Sh2-240** stammt aus VizieR Sharpless als HII-Region
- **B33** stammt aus VizieR Barnard als Dunkelnebel
- **Vega** stammt aus dem Yale BSC
- **UGC 12345** stammt aus SIMBAD

### Deduplizierung

Objekte, die in mehreren Datenquellen vorkommen (z. B. M42 ist auch NGC 1976), werden automatisch nach Name und räumlicher Nähe dedupliziert. Wenn sich zwei Ergebnisse auf dasselbe Objekt beziehen, hat die bekanntere Bezeichnung Vorrang — Messier-Bezeichnungen haben also Priorität vor NGC, und NGC hat Priorität vor IC.

### SIMBAD

SIMBAD wird **immer automatisch** zusammen mit den VizieR-Katalogen abgefragt. Es liefert:

- Schwache Galaxien (UGC-, MCG-, PGC-Kataloge)
- Abell-Galaxienhaufen
- Arp-Galaxien und Hickson Kompaktgruppen
- Markarian-Galaxien
- vdB-Reflexionsnebel
- Auflösung gebräuchlicher Namen für alle Objekte
- Zusätzliche NGC/IC-Objekte, die nicht in der VizieR VII/118-Auswahl enthalten sind

**Voraussetzungen:** Internetverbindung und das Python-Paket `astroquery`. Störeinträge aus Durchmusterungskatalogen (SDSS, 2MASS, WISE, FAUST, IRAS usw.) werden automatisch herausgefiltert.

---

## 7. Objekttypen & Farbcodierung

Jeder Objekttyp hat eine eigene Farbe zur einfachen Identifikation:

| Farbe | Typ | Beschreibung | Beispiele |
|-------|-----|-------------|----------|
| **Gold** | Galaxien | Spiral-, elliptische, irreguläre Galaxien | M31, M51, M81, NGC 4565 |
| **Rot** | Emissionsnebel | Leuchtende Gaswolken (HII, Sternentstehungsgebiete) | M42 (Orion), M8 (Lagune), M16 (Adler) |
| **Hellrot** | Reflexionsnebel | Staubwolken, die Sternlicht reflektieren | M78, NGC 7023 (Iris), Hexenkopf |
| **Grün** | Planetarische Nebel | Gashüllen sterbender Sterne | M57 (Ring), M27 (Hantel), Helix |
| **Hellblau** | Offene Sternhaufen | Junge Sterngruppen | M45 (Plejaden), Doppelsternhaufen |
| **Orange** | Kugelsternhaufen | Uralte, dichte Sternkugeln | M13, Omega Centauri, 47 Tucanae |
| **Magenta** | Supernova-Überreste | Explosionstrümmer | M1 (Krebs), Schleiernebel, Simeis 147 |
| **Grau** | Dunkelnebel | Undurchsichtige Staubwolken | B33 (Pferdekopf), B78 (Pfeife) |
| **Rot-Rosa** | HII-Regionen | Sharpless ionisierte Wasserstoffregionen | Herznebel, Seelennebel, Barnards Schleife |
| **Hellblau** | Asterismen | Sternmuster, keine echten Sternhaufen | Kleiderbügel, Kembles Kaskade |
| **Violett** | Quasare | QSOs und AGN | 3C 273, Markarian 421 |
| **Weiß** | Benannte Sterne | Helle Sterne aus Yale BSC und SIMBAD | Vega, Deneb, Polaris, Beteigeuze |

### Standardeinstellungen

Standardmäßig sind die Typen der **linken Spalte aktiviert** (EIN): Galaxien, Emissionsnebel, Planetarische Nebel, Offene Sternhaufen, Kugelsternhaufen, Benannte Sterne.

Standardmäßig sind die Typen der **rechten Spalte deaktiviert** (AUS): Reflexionsnebel, Supernova-Überreste, Dunkelnebel, HII-Regionen, Asterismen, Quasare. (Diese können bei Weitfeldbildern viele Beschriftungen erzeugen oder sind spezialisierte Typen; aktivieren Sie sie, wenn es relevant ist.)

### Grenzwert für Helligkeit

Der Grenzwert für die Helligkeit (Standard: 12,0) steuert die schwächsten Objekte, die beschriftet werden. Objekte, die heller als der Grenzwert sind, werden angezeigt; schwächere Objekte werden ausgeblendet.

**Ausnahme:** Dunkelnebel aus dem Barnard-Katalog haben keine Helligkeitsangabe und werden unabhängig vom Grenzwert immer angezeigt.

**Richtwerte:**
- **8–10:** Sehr saubere Beschriftung — nur die hellsten, auffälligsten Objekte
- **12,0:** Guter Standardwert — erfasst die meisten visuell interessanten Objekte
- **14–16:** Dichte Beschriftung — enthält viele schwache Galaxien und Nebel
- **18–20:** Sehr dicht — kann bei Weitfeldbildern überladen wirken

---

## 8. Anzeigeoptionen

### Schriftgröße (6–24 pt)

Steuert die Textgröße der Objektbeschriftungen. Standard: 10 pt.
- **Größer (14–18):** Gut zum Teilen in sozialen Medien, wenn das Bild in verkleinerter Größe betrachtet wird
- **Kleiner (8–10):** Gut für hochauflösende Drucke oder wenn sich viele Objekte im Feld befinden

### Markierungsgröße (8–60 px)

Steuert die Größe der Fadenkreuz-Markierungen für punktförmige Objekte. Standard: 20 px.
- Betrifft nur Objekte, die keine katalogisierten Winkeldaten haben (oder wenn Ellipsen deaktiviert sind)

### Objektgröße als Ellipse anzeigen

Wenn **aktiviert** (Standard): Ausgedehnte Objekte (Galaxien, Nebel) werden als Ellipsen proportional zu ihrer katalogisierten Winkelgröße dargestellt. Dies gibt einen visuellen Eindruck davon, wie groß jedes Objekt tatsächlich ist.

Wenn **deaktiviert**: Alle Objekte erhalten einfache Fadenkreuz-Markierungen, unabhängig von der Größe. Erzeugt ein saubereres, einheitlicheres Erscheinungsbild.

### Helligkeit im Label anzeigen

Wenn aktiviert, wird die visuelle Helligkeit an jedes Label angehängt:
- `M31 3.4m` statt nur `M31`
- Nützlich, um die relative Helligkeit von Objekten im Feld zu verstehen

### Objekttyp im Label anzeigen

Wenn aktiviert, wird die Typbezeichnung angehängt:
- `M31 [Galaxy]` statt nur `M31`
- Hilfreich für Betrachter, die mit Katalogbezeichnungen nicht vertraut sind

### Gebräuchliche Namen anzeigen

Wenn **aktiviert** (Standard): Zeigt populäre Namen an, wo verfügbar. Gebräuchliche Namen werden über eine SIMBAD-TAP-Abfrage aufgelöst und gefiltert, um katalogähnliche Bezeichner (FAUST, IRAS, 2MASS, SDSS usw.) auszuschließen, sodass nur erkennbare Namen angezeigt werden:
- `M31 (Andromeda Galaxy)` statt nur `M31`
- `NGC 7000 (North America Nebula)`

Wenn **deaktiviert**: Zeigt nur die Katalogbezeichnung für ein kompakteres Erscheinungsbild.

### Farbcodierung nach Objekttyp

Wenn **aktiviert** (Standard): Verwendet das Farbschema aus Abschnitt 7 — unterschiedliche Farben für unterschiedliche Objekttypen.

Wenn **deaktiviert**: Alle Beschriftungen verwenden die gleiche Farbe. Erzeugt ein einheitlicheres Erscheinungsbild, macht es aber schwieriger, Objekttypen auf einen Blick zu unterscheiden.

---

## 9. Extras (Overlays)

### Koordinatengitter (RA/DEC)

**Standard: EIN**

Überlagert ein halbtransparentes äquatoriales Koordinatengitter mit RA- und DEC-Beschriftungen. Der Gitterabstand wird automatisch basierend auf Ihrem Bildfeld gewählt:

| FOV | Gitterabstand |
|-----|--------------|
| < 15' | 3' (0,05°) |
| 15'–30' | 6' (0,1°) |
| 30'–1,5° | 15' (0,25°) |
| 1,5°–3° | 30' (0,5°) |
| 3°–6° | 1° |
| > 6° | 2°–5° |

Das Gitter strebt ungefähr 5 Linien über das gesamte Feld an. RA-Beschriftungen sind im Format Stunden/Minuten/Sekunden; DEC-Beschriftungen im Format Grad/Bogenminuten/Bogensekunden.

### Infobox

**Standard: EIN**

Eine halbtransparente Box in der oberen linken Ecke mit folgenden Informationen:
- **Objektname** (aus dem FITS-Header, falls verfügbar)
- **Zentrumskoordinaten** (RA und DEC des Bildzentrums)
- **Bildfeld** (Breite × Höhe in Bogenminuten)
- **Pixelskala** (Bogensekunden pro Pixel)
- **Rotationswinkel** (Grad, aus der WCS-CD-Matrix)
- **Beschriftete Objekte** (Gesamtanzahl)

### Kompass (N/O-Pfeile)

**Standard: AUS**

Zeigt Nord- und Ost-Richtungspfeile in der unteren rechten Ecke. Die Pfeile werden aus der WCS-Lösung berechnet und spiegeln somit genau die Bildausrichtung, Rotation und Spiegelung wider.

Nützlich, wenn Ihr Bild gedreht oder gespiegelt ist — der Kompass zeigt, welche Richtung in astronomischer Konvention „oben" (Norden) und „links" (Osten) ist.

### Farblegende

**Standard: EIN**

Eine automatisch generierte Legendenbox in der unteren linken Ecke, die Farbmuster für jeden im Bild vorkommenden Objekttyp zeigt. Nur Typen, die tatsächlich im beschrifteten Bild vorkommen, werden aufgeführt — wenn Ihr Bildfeld keine planetarischen Nebel enthält, erscheint diese Farbe nicht in der Legende.

### Verbindungslinien

**Standard: EIN**

Dünne Verbindungslinien von jedem Label zu seiner Objektmarkierung. Diese sind in dicht besiedelten Feldern unverzichtbar, in denen Labels durch den Kollisionsvermeidungsalgorithmus versetzt wurden — sie zeigen, welches Label zu welchem Objekt gehört.

Können für ein saubereres Erscheinungsbild bei spärlich besiedelten Feldern deaktiviert werden, in denen die Zuordnung zwischen Label und Objekt offensichtlich ist.

---

## 10. Ausgabeoptionen

### Format

| Format | Komprimierung | Ideal für |
|--------|--------------|-----------|
| **PNG** (Standard) | Verlustfrei | Teilen online, Foren, soziale Medien. Empfohlener Standard. |
| **TIFF** | Verlustfrei | Weitere Bearbeitung in Bildbearbeitungsprogrammen. Größere Dateien. |
| **JPEG** | Verlustbehaftet | Web-Uploads, E-Mail-Anhänge. Kleinste Dateigröße. |

### DPI (72–300)

Steuert die Ausgabeauflösung (Punkte pro Zoll):
- **72 DPI:** Kleinste Dateigröße, gut für schnelle Vorschauen
- **150 DPI (Standard):** Gute Balance für Bildschirme und soziale Medien
- **300 DPI:** Druckqualität. Erzeugt große Dateien, aber maximale Detailschärfe.

### Dateiname

Der Basisname für die Ausgabedatei (Standard: `annotated`). Ein Zeitstempel wird automatisch angehängt, um Überschreiben zu verhindern:
```
annotated_20250315_221430.png
```

### Ausgabeort

Das beschriftete Bild wird im **Arbeitsverzeichnis von Siril** gespeichert — demselben Ordner wie Ihre Bilddateien.

---

## 11. Anwendungsfälle & Arbeitsabläufe

### Anwendungsfall 1: Schneller Social-Media-Post (2 Minuten)

**Szenario:** Sie haben gerade ein Bild der Orion-Region fertig bearbeitet und möchten eine beschriftete Version auf Instagram oder einem Forum teilen.

**Ablauf:**
1. Laden Sie Ihr Plate-Solved, bearbeitetes Bild in Siril
2. Starten Sie Annotate Image
3. Belassen Sie die Standardeinstellungen (alle wichtigen Objekttypen aktiviert, Helligkeit 12,0, PNG, 150 DPI)
4. Klicken Sie auf **Annotate Image** (F5)
5. Klicken Sie auf **Beschriftetes Bild öffnen** zur Vorschau
6. Teilen Sie die Ausgabedatei direkt

**Ergebnis:** Eine saubere Beschriftung mit Messier- und NGC-Objekten, Koordinatengitter, Infobox und Legende.

### Anwendungsfall 2: Weitfeld-Milchstraßen-Beschriftung

**Szenario:** Sie haben ein Weitfeldbild einer Milchstraßenregion und möchten alle Nebel und HII-Regionen beschriften.

**Ablauf:**
1. Laden Sie das Plate-Solved-Weitfeldbild
2. Starten Sie Annotate Image
3. Aktivieren Sie **HII-Regionen** und **Dunkelnebel** (standardmäßig deaktiviert)
4. Erhöhen Sie den Grenzwert für Helligkeit auf 14 oder höher
5. Erwägen Sie, die Schriftgröße auf 12–14 zu erhöhen, damit sie bei verkleinerter Ansicht lesbar bleibt
6. Klicken Sie auf **Annotate Image**

**Ergebnis:** Ein reich beschriftetes Bild mit Sharpless HII-Regionen, Barnard-Dunkelnebeln und allen üblichen DSOs — perfekt zur Identifikation von Strukturen in einem Milchstraßenpanorama.

### Anwendungsfall 3: Galaxienfeld-Identifikation

**Szenario:** Sie haben ein Feld in der Jungfrau oder im Haar der Berenike aufgenommen und möchten alle Galaxien identifizieren.

**Ablauf:**
1. Laden Sie das Plate-Solved-Bild
2. Starten Sie Annotate Image
3. Deaktivieren Sie alle Typen außer **Galaxien**
4. Erhöhen Sie den Grenzwert für Helligkeit auf 14–16
5. Deaktivieren Sie gebräuchliche Namen für ein saubereres Erscheinungsbild (viele schwache Galaxien haben ohnehin keine gebräuchlichen Namen)
6. Klicken Sie auf **Annotate Image**

**Ergebnis:** Jede Galaxie im Feld ist mit ihrer Katalogbezeichnung beschriftet, einschließlich schwacher Hintergrundgalaxien, die über SIMBAD entdeckt werden.

### Anwendungsfall 4: Beschriftetes Bild in Druckqualität

**Szenario:** Sie möchten ein hochauflösendes beschriftetes Bild zum Drucken oder Veröffentlichen.

**Ablauf:**
1. Laden Sie Ihr bestes Plate-Solved-Bild
2. Starten Sie Annotate Image
3. Setzen Sie **DPI auf 300** für maximale Auflösung
4. Setzen Sie **Format auf TIFF** für verlustfreie Ausgabe
5. Erhöhen Sie die Schriftgröße auf 12–14 (Labels müssen in Druckgröße lesbar sein)
6. Aktivieren Sie alle Overlays: Gitter, Infobox, Kompass, Legende
7. Klicken Sie auf **Annotate Image**

**Ergebnis:** Ein publikationsreifes beschriftetes Bild in voller Auflösung.

### Anwendungsfall 5: Nur Sternidentifikation

**Szenario:** Sie möchten die hellen Sterne in Ihrem Feld identifizieren, um den Sternbild-Kontext zu verstehen.

**Ablauf:**
1. Laden Sie das Plate-Solved-Bild
2. Starten Sie Annotate Image
3. Deaktivieren Sie alle Typen außer **Benannte Sterne**
4. Setzen Sie den Grenzwert für Helligkeit auf 5 oder 6 (nur mit bloßem Auge sichtbare Sterne)
5. Deaktivieren Sie das Koordinatengitter und die Infobox für ein saubereres Erscheinungsbild
6. Klicken Sie auf **Annotate Image**

**Ergebnis:** Eine saubere Beschriftung, die nur benannte Sterne zeigt — Vega, Deneb, Altair, Sternbildsterne usw.

### Anwendungsfall 6: Minimale, dezente Beschriftung

**Szenario:** Sie möchten eine zurückhaltende Beschriftung, die Ihr schön bearbeitetes Bild nicht überwältigt.

**Ablauf:**
1. Laden Sie das Bild und starten Sie Annotate Image
2. Reduzieren Sie die Schriftgröße auf 8
3. Deaktivieren Sie: Helligkeitslabels, Typlabels, Verbindungslinien
4. Deaktivieren Sie: Koordinatengitter, Kompass
5. Behalten Sie: Gebräuchliche Namen, Infobox, Farblegende
6. Setzen Sie den Grenzwert für Helligkeit auf 10 (nur die hellsten Objekte)
7. Klicken Sie auf **Annotate Image**

**Ergebnis:** Eine geschmackvolle, minimale Beschriftung mit nur den wichtigsten Objekten — das Bild bleibt der Star der Show.

### Anwendungsfall 7: Bildungs- / Präsentations-Beschriftung

**Szenario:** Sie bereiten eine Präsentation oder Lehrmaterial vor und möchten eine maximal informative Beschriftung.

**Ablauf:**
1. Laden Sie das Plate-Solved-Bild
2. Aktivieren Sie alle Objekttypen einschließlich HII-Regionen, Dunkelnebel, Asterismen und Quasare
3. Aktivieren Sie: Helligkeitslabels, Typlabels, gebräuchliche Namen
4. Aktivieren Sie alle Extras: Gitter, Infobox, Kompass, Legende
5. Setzen Sie die Schriftgröße auf 12 für gute Lesbarkeit
6. Klicken Sie auf **Annotate Image**

**Ergebnis:** Eine dicht beschriftete, maximal informative Beschriftung, die alles im Feld mit Typbezeichnungen, Helligkeiten und allen Overlays zeigt.

### Anwendungsfall 8: Verschiedene Beschriftungseinstellungen vergleichen

**Szenario:** Sie möchten mehrere Versionen desselben Bildes mit unterschiedlichen Beschriftungsstilen erstellen.

**Ablauf:**
1. Laden Sie das Bild einmal
2. Erstellen Sie eine „volle" Version mit allen Typen, hohem Grenzwert für Helligkeit, allen Extras
3. Ändern Sie den Basisdateinamen zu `annotated_full`
4. Klicken Sie auf **Annotate Image**
5. Erstellen Sie eine „saubere" Version: deaktivieren Sie HII/Dunkelnebel, senken Sie den Grenzwert auf 10, deaktivieren Sie das Gitter
6. Ändern Sie den Dateinamen zu `annotated_clean`
7. Klicken Sie erneut auf **Annotate Image**

Der Zeitstempel im Dateinamen stellt sicher, dass Sie eine vorherige Ausgabe nie überschreiben. Alle Versionen werden im Arbeitsverzeichnis gespeichert.

---

## 12. Tastaturkürzel

| Taste | Aktion |
|-------|--------|
| `F5` | Beschriftung ausführen (entspricht dem Klick auf „Annotate Image") |
| `Esc` | Fenster schließen |

---

## 13. Tipps & Empfehlungen

### Bildvorbereitung

1. **Immer zuerst Plate Solving durchführen.** Das Skript kann ohne WCS-Lösung nicht beschriften. Wenn das Plate Solving fehlschlägt, überprüfen Sie, ob Ihr Bild genügend Sterne enthält und Ihre Brennweite ungefähr korrekt angegeben ist.

2. **Verwenden Sie Ihr bearbeitetes (gestrecktes) Bild.** Das Skript nutzt Sirils Autostretch-Vorschau, aber ein gut bearbeitetes Bild als Ausgangspunkt liefert den besten Hintergrund für die Beschriftung.

3. **Speichern Sie Ihr Bild vor dem Beschriften.** Wenn die WCS-Daten gerade erst berechnet, aber die FITS-Datei noch nicht gespeichert wurde, kann das Skript Schwierigkeiten beim Lesen der WCS-Daten haben. Das Speichern stellt sicher, dass der Header vollständig ist.

### Beschriftungseinstellungen

4. **Beginnen Sie mit den Standardeinstellungen, dann passen Sie an.** Die Standardeinstellungen (Helligkeit 12,0, wichtigste Objekttypen aktiviert, Gitter + Infobox + Legende) liefern gute Ergebnisse für die meisten Bilder. Passen Sie von dort aus an.

5. **Passen Sie die Schriftgröße an die beabsichtigte Anzeigegröße an.** Für Bilder, die im Vollbildmodus auf einem Monitor betrachtet werden, sind 10 pt ausreichend. Für Bilder, die als Miniaturansichten in sozialen Medien betrachtet werden, erhöhen Sie auf 14–16 pt.

6. **Der Grenzwert für Helligkeit ist Ihre mächtigste Steuerung.** Senken Sie ihn, um Unordnung zu reduzieren; erhöhen Sie ihn, um versteckte Objekte zu finden. Dies ist der effektivste Weg, um die Dichte Ihrer Beschriftung zu steuern. Experimentieren Sie mit verschiedenen Werten, um den optimalen Wert für Ihr Bild zu finden.

7. **Dunkelnebel und HII-Regionen eignen sich am besten für Weitfeldbilder.** Bei Bildern mit engem Bildfeld (kleinem FOV) erstrecken sich diese großen Strukturen oft über die Bildränder hinaus und erzeugen Beschriftungen für Objekte, die man nicht wirklich sehen kann.

### Ausgabe

9. **PNG ist das beste Allround-Format.** Verlustfreie Komprimierung, akzeptable Dateigröße und universelle Kompatibilität. Verwenden Sie TIFF nur, wenn Sie das beschriftete Bild weiter bearbeiten möchten.

10. **150 DPI sind für die Bildschirmanzeige ausreichend.** Erhöhen Sie nur auf 300 DPI, wenn Sie Druckqualität benötigen — es vervierfacht die Dateigröße.

11. **Alle Einstellungen werden gespeichert.** Das Skript merkt sich Ihre zuletzt verwendeten Einstellungen (Objekttypen, Anzeigeoptionen, DPI, Format) zwischen den Sitzungen über QSettings. Sie müssen nicht jedes Mal neu konfigurieren.

---

## 14. Fehlerbehebung

### Fehler „Bild ist nicht Plate-Solved"

**Ursache:** Das aktuelle Bild in Siril hat keine WCS-Lösung in seinem FITS-Header.
**Lösung:** Führen Sie zuerst ein Plate Solving durch: **Werkzeuge → Astrometrie → Bild-Plate-Solver...** Dann starten Sie das Skript erneut.

### Fehler „Kein Bild geladen"

**Ursache:** Kein Bild ist derzeit in Siril geladen.
**Lösung:** Öffnen Sie ein FITS-Bild in Siril, bevor Sie das Skript starten.

### WCS erscheint als Plate-Solved, aber „konnte nicht gelesen werden"

**Ursache:** Die WCS-Daten sind im Siril-Speicher vorhanden, aber nicht vollständig in den FITS-Header geschrieben.
**Lösung:** Speichern Sie das Bild zuerst als FITS (Datei → Speichern), laden Sie es dann erneut und starten Sie das Skript nochmals. Das Skript verwendet eine 6-stufige Rückfallstrategie zum Lesen der WCS-Daten, aber manchmal ist ein erneutes Speichern nötig.

### Keine Objekte im Feld gefunden

**Ursache:** Das Bildfeld enthält möglicherweise keine Katalogobjekte oberhalb des Helligkeitsgrenzwerts, oder der Grenzwert ist zu restriktiv.
**Lösung:**
- Erhöhen Sie den Grenzwert für Helligkeit (z. B. von 12 auf 15)
- Aktivieren Sie zusätzliche Objekttypen (HII-Regionen, Dunkelnebel, Asterismen)
- Überprüfen Sie die Protokoll-Registerkarte — sie zeigt genau, welche Kataloge durchsucht wurden und wie viele Objekte gefunden wurden

### Beschriftung ist zu überladen

**Ursache:** Zu viele Objekttypen aktiviert oder Grenzwert für Helligkeit zu hoch.
**Lösung:**
- Senken Sie den Grenzwert für Helligkeit (z. B. von 15 auf 10)
- Deaktivieren Sie HII-Regionen und Dunkelnebel
- Deaktivieren Sie Benannte Sterne, wenn Sternbeschriftungen nicht benötigt werden
- Reduzieren Sie die Schriftgröße
- Deaktivieren Sie Helligkeits- und Typlabels

### SIMBAD-Abfrage schlägt fehl

**Ursache:** SIMBAD wird immer automatisch abgefragt. Ein Fehler kann durch fehlende Internetverbindung, SIMBAD-Serverwartung oder einen Timeout verursacht werden.
**Lösung:** Das Skript behandelt SIMBAD-Fehler elegant — es fällt auf reine VizieR-Ergebnisse zurück. Sie erhalten weiterhin Beschriftungen aus den NGC 2000.0-, Sharpless-, Barnard- und Yale BSC-Katalogen. Überprüfen Sie die Protokoll-Registerkarte für den spezifischen Fehler. Wenn SIMBAD vorübergehend nicht verfügbar ist, versuchen Sie es später erneut.

### Beschriftung ist langsam

**Ursache:** Alle 5 Datenquellen werden parallel über das Internet abgefragt. Weitfeldbilder können gekachelte Abfragen auslösen, um das gesamte Feld abzudecken.
**Lösung:**
- Dies ist normal für die erste Beschriftung eines bestimmten Feldes — nachfolgende Durchläufe profitieren von Caching
- Weitfeld-Mosaike erfordern mehr Abfragen, um die größere Himmelsfläche abzudecken
- Überprüfen Sie Ihre Internetverbindung, wenn Abfragen einen Timeout haben
- Die Protokoll-Registerkarte zeigt den Fortschritt jeder Katalogabfrage

### Ausgabedatei ist sehr groß

**Ursache:** Hohe DPI-Einstellung (300) mit TIFF-Format bei einem großen Sensorbild.
**Lösung:** Reduzieren Sie DPI auf 150 oder wechseln Sie zum PNG-Format. Ein 4656×3520-Bild bei 300 DPI im TIFF-Format kann über 50 MB groß sein; bei 150 DPI im PNG-Format sind es typischerweise 5–15 MB.

### Schriftart-Warnung: „Sans-serif"

**Meldung:** `qt.qpa.fonts: Populating font family aliases took 121 ms. Replace uses of missing font family "Sans-serif"...`
**Auswirkung:** Nur kosmetisch, keine Auswirkung auf die Funktionalität. Kann sicher ignoriert werden.

### Labels überlappen sich trotz Kollisionsvermeidung

**Ursache:** In sehr dichten Feldern (Galaxienhaufen, dichte Milchstraßenregionen) findet der 32-Kandidaten-Platzierungsalgorithmus mit Raumgitter-Bewertung möglicherweise nicht für jedes Label eine kollisionsfreie Position.
**Lösung:** Reduzieren Sie die Anzahl der beschrifteten Objekte, indem Sie den Grenzwert für Helligkeit senken oder einige Objekttypen deaktivieren. Die Kollisionsvermeidung funktioniert am besten mit weniger als ca. 50 Objekten.

---

## 15. Häufige Fragen

**F: Ersetzt dies PixInsights AnnotateImage-Skript?**
A: Für die meisten Zwecke ja. Es bietet die gleiche Kernfunktionalität — Katalogobjekt-Beschriftung auf Plate-Solved-Bildern — mit zusätzlichen Funktionen wie einer grafischen Oberfläche, Live-Online-Katalogabfragen und persistenten Einstellungen. PixInsights Skript unterstützt einige zusätzliche Katalogquellen, aber die 5 Online-Datenquellen von Annotate Image decken die überwiegende Mehrheit der interessanten Objekte ab.

**F: Kann ich nicht Plate-Solved-Bilder beschriften?**
A: Nein. Das Skript benötigt WCS-Koordinaten, um zu wissen, wohin jeder Pixel am Himmel zeigt. Ohne Plate Solving kann es nicht bestimmen, welche Objekte sich in Ihrem Feld befinden. Plate Solving in Siril ist schnell und kostenlos — es gibt keinen Grund, es nicht zu tun.

**F: Verändert das Skript mein Originalbild?**
A: Nein. Das Skript liest Ihr Bild zur Darstellung und erstellt eine **neue** Datei mit den Beschriftungen. Ihre originale FITS-Datei wird nie verändert.

**F: Benötigt das Skript eine Internetverbindung?**
A: Ja. Alle Katalogdaten stammen aus Live-VizieR- und SIMBAD-Abfragen über das Internet. Ohne Verbindung kann das Skript keine Objektdaten abrufen und die Beschriftung schlägt fehl.

**F: Wie geht das Skript mit großen Mosaikbildern um?**
A: Das Skript beinhaltet automatische Anzeige-Verkleinerung, DPI-Begrenzung und Speicherverwaltung für große Mosaike. Sehr große Bilder werden intern für das Rendering verkleinert, um übermäßigen Speicherverbrauch zu vermeiden, während die Ausgabe die angemessene Qualität für die gewählte DPI-Einstellung beibehält.

**F: Kann ich Farb- (RGB) und Mono-Bilder beschriften?**
A: Ja. Das Skript verarbeitet sowohl RGB- als auch Einzelkanal- (Mono-) Bilder. Mono-Bilder werden automatisch in 3-Kanal-Bilder für die beschriftete Ausgabe konvertiert.

**F: Warum werden manche Objekte als Ellipsen und andere als Fadenkreuze dargestellt?**
A: Objekte mit bekannten Winkelgrößen im Katalog (die meisten Galaxien, große Nebel) werden als Ellipsen skaliert auf ihre tatsächliche Größe dargestellt. Objekte ohne Größendaten oder wenn die Option „Objektgröße als Ellipse anzeigen" deaktiviert ist, erhalten einfache Fadenkreuz-Markierungen.

**F: Warum sehe ich keine Barnard- (Dunkelnebel-) Objekte?**
A: Dunkelnebel sind **standardmäßig deaktiviert**, um Beschriftungen sauber zu halten. Aktivieren Sie das Kontrollkästchen „Dunkelnebel" im Abschnitt „Objekte beschriften". Beachten Sie, dass Dunkelnebel den Helligkeitsgrenzwert umgehen — sie werden immer angezeigt, wenn sie aktiviert sind.

**F: Warum sehe ich keine Sharpless- (HII-Region-) Objekte?**
A: HII-Regionen sind ebenfalls **standardmäßig deaktiviert**. Aktivieren Sie das Kontrollkästchen „HII-Regionen". Sharpless-Objekte sind großräumige Strukturen, die am besten auf Weitfeldbildern zu sehen sind.

**F: Kann ich die Farben anpassen?**
A: Derzeit nicht über die Benutzeroberfläche. Das Farbschema ist im Quellcode des Skripts definiert (`DEFAULT_COLORS`-Dictionary). Fortgeschrittene Benutzer können das Skript bearbeiten, um die Farben zu ändern.

**F: Wo wird die Ausgabedatei gespeichert?**
A: Im Arbeitsverzeichnis von Siril (derselbe Ordner wie Ihre Bilddateien). Der vollständige Pfad wird nach der Beschriftung in der Protokoll-Registerkarte angezeigt.

**F: Kann ich das Skript mehrmals auf demselben Bild ausführen?**
A: Ja! Jeder Durchlauf erstellt eine neue Ausgabedatei mit einem Zeitstempel im Dateinamen. Sie können mit verschiedenen Einstellungen experimentieren, ohne vorherige Ergebnisse zu überschreiben.

**F: Wie funktioniert die WCS-Erkennung?**
A: Das Skript verwendet eine 6-stufige Rückfallstrategie zum Extrahieren der WCS-Daten aus Siril:
1. FITS-Header als Dictionary → WCS direkt erstellen
2. FITS-Header als Zeichenkette → in WCS parsen
3. Siril-Schlüsselwörter auf Plate-Solve-Flag prüfen
4. WCS durch Abtasten von `pix2radec` an drei Punkten erstellen
5. `pix2radec` auch ohne Plate-Solve-Flag versuchen
6. Die FITS-Datei von der Festplatte lesen als letzter Ausweg

Dies stellt die Kompatibilität mit verschiedenen Siril-Versionen und Plate-Solving-Methoden sicher.

---

## Danksagung

**Entwickelt von** Sven Ramuschkat
**Webseite:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, die auch umfasst:
- Svenesis Blink Comparator
- Svenesis Gradient Analyzer
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Script Security Scanner

---

*Wenn Sie dieses Werkzeug nützlich finden, erwägen Sie, die Entwicklung über [Buy me a Coffee](https://buymeacoffee.com/svenesis) zu unterstützen.*
