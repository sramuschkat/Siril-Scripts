# Svenesis LightCurve — Anleitung

**Version 1.0.4** | Siril Python-Skript für Exoplaneten-Transitphotometrie

> *Ein Ordner Subs hinein, eine Lichtkurve heraus — und eine ehrliche Antwort auf die einzige Frage, die zählt: steckt da ein Transit drin?*

---

## Inhalt

1. [Was ist Svenesis LightCurve?](#1-was-ist-svenesis-lightcurve)
2. [Grundlagen für Einsteiger](#2-grundlagen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
3a. [Kalibrierung](#3a-kalibrierung)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Oberfläche](#5-die-oberfläche)
6. [Den Zielstern wählen](#6-den-zielstern-wählen)
7. [Die Vergleichssterne](#7-die-vergleichssterne)
8. [Die Airmass-Rampe entfernen](#8-die-airmass-rampe-entfernen)
9. [Der Transit-Fit](#9-der-transit-fit)
10. [Ist es echt?](#10-ist-es-echt)
11. [Die Ausgabe lesen](#11-die-ausgabe-lesen)
12. [Gute Daten aufnehmen](#12-gute-daten-aufnehmen)
13. [Fehlersuche](#13-fehlersuche)
14. [FAQ](#14-faq)

---

## 1. Was ist Svenesis LightCurve?

Richte **Svenesis LightCurve** auf den Ordner mit den Subs einer Nacht auf einen Exoplaneten-Wirtsstern. Das Skript misst, wie sich dessen Helligkeit relativ zu anderen Sternen im selben Feld verändert hat, entfernt die systematischen Trends, die es verantworten kann, fittet einen Transit — und sagt dir, ob die Delle echt ist oder ob du eine Wolke ansiehst.

### Wer macht was

Die Arbeitsteilung ist bewusst gewählt und erklärt den größten Teil des Designs.

**Siril macht, was es nachweislich gut kann:** Bereitstellen, Kalibrieren, Zwei-Pass-Registrierung, Sternerkennung, Plate Solve und die Qualität pro Frame.

**Dieses Skript misst den Fluss selbst**, so wie EXOTIC und HOPS es tun — jeder Stern pro Frame neu zentriert, Subpixel-Aperturen, sigma-geclippter Himmel, die Apertur nach Punkt-zu-Punkt-Rauschen gewählt, Vergleichssterne nach ihrer *gemessenen* Streuung behalten (§4a erklärt jedes Teil samt der Messung dahinter). Sirils `light_curve` bleibt als lauter Fallback intakt: misst die Engine unter 30 % der Frames, sagt sie es und übergibt. Und das Skript macht, worüber keine Pixel entscheiden: welcher Stern das Ziel ist, wie man die Airmass-Rampe entfernt, ohne die Transittiefe mitzunehmen, wie man das Ereignis fittet — und vor allem, ob überhaupt etwas behauptet werden darf.

**Gegen EXOTIC an dessen eigenen Beispieldaten validiert** (HAT-P-32 b): Rp/R★ = 0,1525 ± 0,0064 gegen EXOTICs publizierte 0,1541 ± 0,0033 — 0,2 σ auseinander, bei gleicher Residuenstreuung (0,58 % vs 0,55 %).

### Der Ablauf

| Schritt | Was passiert | Warum so |
|---|---|---|
| **Bereitstellen** | Subs werden nach `_lightcurve/` verlinkt | Kostet nichts; der Originalordner wird nie beschrieben |
| **Link** | Siril baut eine Sequenz | |
| **Kalibrieren** | Kalibrierframes werden gefunden, zu Mastern gestapelt und über Sirils `calibrate` angewandt | Optional und *delegiert* — in diesem Skript steckt keine Bias-/Dark-/Flat-Arithmetik, aus demselben Grund, aus dem keine Photometrie darin steckt. Reine Pixelrechnung, das Versprechen „kein Resampling" bleibt also unberührt; es wird allerdings eine zweite Kopie jedes Frames geschrieben |
| **Registrieren** | `register -2pass` — nur Daten, **kein Resampling** | Interpolation korreliert Nachbarrauschen und verschiebt Fluss innerhalb der Apertur. Die Apertur folgt dem Stern über die Registrierungsdaten, die Pixel bleiben, wie der Sensor sie aufgezeichnet hat |
| **Erkennen** | Siril findet die Sterne (und löst das Referenzframe astrometrisch, wenn das Ziel Himmelskoordinaten braucht); das Skript wählt Ziel + Vergleiche | |
| **Photometrie** | Die eigene Engine dieses Skripts — Follow-Star, Subpixel-Aperturen, Apertur nach Rauschen gewählt. Sirils `light_curve` als angekündigter Fallback | Am selben driftenden Lauf gemessen: 140 Punkte gegen 67 von `light_curve` |
| **Analyse** | Detrend → Fit → Entscheidung | |

---

## 2. Grundlagen für Einsteiger

**Was ist ein Transit?** Ein Planet, der vor seinem Stern vorbeizieht, blockiert einen Bruchteil des Lichts. Bei einem heißen Jupiter sind das etwa 1–2 % — zehn bis zwanzig **Millimagnituden** — über zwei bis vier Stunden. Eine kleine, langsame Delle. Und alles an ihrer Messung ist ein Kampf gegen Dinge, die ebenfalls kleine, langsame Dellen erzeugen.

**Warum „differentiell"?** Die absolute Helligkeit zu messen ist aussichtslos: Wolken, Transparenzschwankungen und die dünner werdende Atmosphäre beim Aufgang überdecken ein 1-%-Signal um Größenordnungen. Aber sie treffen *alle Sterne im Feld gemeinsam*. Teilt man das Ziel durch mehrere Vergleichssterne, kürzt sich das weg. Übrig bleibt die Eigenvariation des Sterns — der Transit.

**Was ist Airmass?** Wie viel Atmosphäre im Strahlengang liegt. Senkrecht oben 1,0; nahe am Horizont 3 oder mehr, und der Stern wird entsprechend schwächer. Differentielle Photometrie kürzt das größtenteils weg — aber nicht ganz: Ziel und Vergleichssterne haben unterschiedliche Farben und dimmen daher unterschiedlich schnell. Übrig bleibt eine glatte Rampe, und sie zu entfernen, ohne den Transit mitzunehmen, ist ein großer Teil dessen, was dieses Skript tut (§8).

**Was ist eine Magnitude?** Eine logarithmische Helligkeitsskala, bei der *größer schwächer bedeutet*. Eine Millimagnitude (mmag) ist ein Tausendstel. Alle Diagramme hier haben eine invertierte y-Achse, damit oben heller heißt — deshalb liest sich ein Transit als Delle.

---

## 3. Voraussetzungen & Installation

- **Siril 1.4** oder neuer mit Python-Modul
- Beim ersten Start automatisch installiert: `numpy`, `PyQt6`, `matplotlib`, `astropy`

Lege `Svenesis-LightCurve.py` in einen Ordner namens **Utility** in einem von Sirils Skript-Verzeichnissen (*Einstellungen → Skripte*) und starte es über **Bildverarbeitung → Skripte**.

**Kalibrieren.** Vor allem Flats: ein Stern, der über einen Staubschatten wandert, erzeugt einen langsamen Trend in genau der Form eines flachen Transits. Entweder du zeigst **2 · Calibration** auf deine Master (siehe [3a](#3a-kalibrierung)) oder du kalibrierst vorher wie gewohnt — auslassen ist keine Option.

---

## 3a. Kalibrierung

**Nichts muss vorbereitet werden, und du musst dich nicht durchklicken.** Zeig auf deine Subs — oder auf irgendeinen Ordner darüber — und einmalig auf den Ordner mit deinen wiederverwendbaren Darks. Alles Weitere wird gefunden.

### Wo gesucht wird

Der Scan ist **rekursiv**. Jedes FITS unter dem gewählten Ordner wird einmal gelesen und anhand seines Headers in Lights und Kalibrierframes einsortiert — du kannst also auf die Projektwurzel zeigen:

```
WASP-75b/                       ← hierauf zeigen…
├── LIGHT/2026-08-14/LUMINOS/   ← …die Subs liegen drei Ebenen tiefer
└── FLAT/2026-08-14/LUMINOS/    ← diese auch
_CALIB/DARK/60.00s_G125/        ← dein Library-Ordner, einmal gesetzt
```

Oder direkt auf `LIGHT/2026-08-14/LUMINOS/` — dann werden die Flats trotzdem gefunden, weil das Skript zusätzlich **nach oben** geht und dort jedes Kind eines Vorfahren nimmt, das ein `FLAT`- / `DARK`- / `BIAS`- / `DARKFLAT`-Ordner ist. Nach oben werden nur Kalibrierordner durchsucht, nie ein ganzer Vorfahre: vier Ebenen über einem Sub-Ordner kann ein Verzeichnis mit sämtlichen Projekten der Platte liegen.

### Drei Dinge, die die Rekursion nötig gemacht hat

| Absicherung | Warum |
|---|---|
| **Eigene Ordner ausgespart** | In `_lightcurve/` und `lightcurve/` wird nie hineingegangen — ein zweiter Lauf würde sonst die gestagten Symlinks und konvertierten Frames des ersten wieder als Subs einlesen |
| **Doppelte Aufnahmen verworfen** | Ein wiederholtes `DATE-OBS` ist eine Kopie, keine Aufnahme. Auf die harte Tour gefunden: ein liegengebliebener Arbeitsordner machte aus 178 Subs 534 — jede Dublette wäre als eigenständiger Punkt in die Kurve eingegangen und hätte jeden Fehlerbalken grundlos um √3 geschrumpft. Wird mit Anzahl gemeldet, nie stillschweigend |
| **Ein Filter, eine Belichtungszeit** | Ein Filter- oder Belichtungswechsel mitten im Lauf sind *zwei* Serien, keine längere. Die größte Menge wird behalten, der Rest benannt |

**Flats gehören zur Session**, werden also innerhalb deiner Auswahl und neben den Lights gesucht und auf deren Filter eingeschränkt. **Darks und Bias sind wiederverwendbar** und kommen aus dem Library-Ordner, der zwischen Läufen gemerkt wird. Rohframes oder fertige Master, beides geht: eine Gruppe aus genau einer Datei wird als fertiger Master übernommen statt gestapelt.

### Was übereinstimmen muss

Frames teilen sich einen Master nur, wenn **Belichtungszeit, Gain, Temperatur, Binning, Bildgröße und Kamera** übereinstimmen. Master werden in `lightcurve/calib/` unter Namen gecacht, die all das tragen — könnten zwei verschiedene Master denselben Namen haben, gäbe der Cache beim zweiten Lauf stillschweigend den falschen zurück.

Was abgelehnt wird, wird ausgesprochen. Ein Master, der gefunden und dann verworfen wurde, hinterlässt einen Lauf, der *genau* so aussieht wie einer ohne jeden Master:

| Abgelehnt | Warum |
|---|---|
| **Falsche Belichtungszeit** (Dark) | Ein 3-s-Dark auf 60-s-Lights entfernt 5 % des Dunkelstroms, lässt den Rest stehen und legt sein eigenes Ausleserauschen auf jeden Frame. Wird mit beiden Zahlen gemeldet — und damit, was es angerichtet hätte |
| **Falsche Temperatur** | Darks werden nach Temperatur gruppiert: ein −10 °C und ein −20 °C zusammengemittelt ist für keines von beiden richtig. Bias wird *nicht* getrennt — es ist reines Ausleserauschen, eine Trennung machte jeden Master nur verrauschter |
| **Falsche Kamera oder Größe** | Zwei Gehäuse mit demselben Sensorformat würden sich sonst gegenseitig kalibrieren |
| **Bias zusammen mit einem Dark** | Nie beides auf den Lights: das Dark enthält den Offset bereits, beides abzuziehen entfernt ihn doppelt. Das Bias korrigiert weiterhin die Flats — Lc = (L − D) / (F − O) |

Ein Flat muss die Belichtungszeit der Lights **nicht** treffen. Ein Flat ist ein Verhältnis; seine eigene Belichtungszeit sagt nichts über die Lights.

### Was es nicht tut

Die Pixelarbeit macht Sirils `calibrate`. In diesem Skript steckt keine Bias-/Dark-/Flat-Arithmetik, aus demselben Grund, aus dem keine Photometrie darin steckt. Und es **resampelt nicht** — Bias, Dark und Flat sind reine Pixelrechnung, das Versprechen der Registrierung bleibt unberührt. Es wird allerdings eine zweite Kopie jedes Frames geschrieben, der Arbeitsordner verdoppelt sich also.

**One-shot-colour sensor (CFA)** ankreuzen bei Bayer-Kameras. Ohne das wird der Frame über sein eigenes Mosaik geflatfieldet, was das CFA-Muster in die Korrektur schreibt.

## 4. Erste Schritte

1. **Ordner wählen** — der Ordner mit den kalibrierten Subs. Zehn Frames sind das absolute Minimum, ein echter Transitlauf hat Hunderte.
2. **Zielstern** — für den ersten Blick auf *Hellster* stehen lassen.
3. **Standortkoordinaten** — Breite und Länge, falls die Airmass-Rampe entfernt werden soll. Ohne sie entfällt der Detrend, und der Report sagt es.
4. **Measure light curve.**

Der erste Lauf dauert einige Minuten; das Registrieren einiger hundert Subs ist der langsame Teil.

---

## 4a. Koordinaten musst du nicht mehr eintippen

**Der Ordnerdialog füllt es schon aus.** Sobald du einen Ordner wählst, werden die ersten 30 Light-Header gelesen, und was dort steht, landet in den Feldern:

> *Read from the first 30 header(s): OBJECT = 'WASP-75b'; OBJCTRA/OBJCTDEC = 342.38750, −10.67556 (25 light frames agree to 0.0").*

**Die Felder folgen den Frames.** Sie werden aus der letzten Sitzung wiederhergestellt, zeigen nach einem Zielwechsel also noch das *vorige* Ziel — genau so lief ein WASP-75-b-Datensatz einmal unter HAT-P-32s Ephemeride. Deshalb: Ein Name, der ein *anderes* Ziel bezeichnet als `OBJECT`, wird ersetzt (jede Schreibweise *desselben* Ziels — `WASP-75b`, `wasp75`, mit oder ohne Planetenbuchstaben — bleibt exakt wie getippt), Koordinaten weiter als ~2′ von den Headern werden durch die Header-Position ersetzt, und wechselt der Zielname, während die neuen Header keine Position tragen, werden die veralteten Koordinaten geleert, damit das Archiv sie liefern kann. Jede Ersetzung wird geloggt; nichts wird still getauscht. Um einen Stern anzupeilen, der *nicht* das Header-Objekt ist: **nach** der Ordnerwahl eintippen — nichts liest erneut. Kalibrierframes werden vorher aussortiert, ein Ordner voller Flats kann das Ziel also nicht von einer geparkten Montierung vorbelegen. Auch Header, die nichts sagen, bekommen eine Zeile: Schweigen liest sich dort als *nichts zu tun*, gemeint ist *tipp den Namen ein*.

Alles, was über *welchen Stern* entscheidet, liegt jetzt an einer Stelle — **Gruppe 3 · Target star** — und der erste Modus **From the frames** ist die Vorgabe:

| Modus | woraus |
|---|---|
| **From the frames** | `OBJCTRA`/`OBJCTDEC` für die Position, wenn vorhanden; sonst die **Archiv-Position des Planeten, den die Frames benennen** (`OBJECT`), mit dem Referenzframe darum herum gelöst. Fällt nur dann auf „hellster" zurück, wenn nichts das Ziel benennt oder platziert — als der Tipp beschriftet, der es ist, und ein Tipp, den der Drift vom Sensor tragen würde, rät neu unter den Sternen, die drauf bleiben. |
| Brightest star | die hellste Detektion |
| Pixel position | dein x/y, auf den nächsten Stern gerastet |
| RA / Dec | deine Koordinaten, auf den nächsten Stern gerastet |

Das **Namensfeld** und die **Archivabfrage** stehen ebenfalls dort und nicht mehr bei der Einreichung: sie entscheiden über die *Position* des Ziels, und die eine Bedienung, die dir das Tippen von Koordinaten erspart, gehört dorthin, wo du das Ziel wählst. Der Name beschriftet weiterhin die AAVSO-Datei — ein Feld, zwei Aufgaben.

Deine Frames wissen längst, wo das Ziel steht. N.I.N.A. schreibt **`OBJCTRA` / `OBJCTDEC`** — die Position des *Objekts*, nicht des Teleskops — und der Lauf liest das direkt aus den Lights:

> *Target from OBJCTRA/OBJCTDEC in your lights: RA 342.38750°, Dec −10.67556° (178 light frames agree to 0.0"). No lookup needed for the position.*

Gegen die NASA Exoplanet Archive gemessen: **5,7″ × 0,2″**, unter drei Pixeln bei 2″/px und bequem innerhalb von Sirils eigenem ±19-px-Suchfenster. Kein Netz, kein Tippen.

### Zwei Karten, die richtig aussehen und es nicht sind

| Karte | in diesem Lauf | was es ist |
|---|---|---|
| **`OBJCTRA` / `OBJCTDEC`** | `22 49 33` / `−10 40 32` | **das Ziel** — wird benutzt |
| `RA` / `DEC` | 342,24 / −10,30 | das **Teleskop-Pointing** — ein Viertelgrad daneben, weil das Ziel nicht die Feldmitte ist |
| `OBJCTRA` in einem **Flat** | `00 00 00`, dazu `RA/DEC` = 359,10 / **+89,85** | die **geparkte Montierung nahe dem Pol** — ein Platzhalter, keine Position |

Beide Fallen sind zu: es werden nur **LIGHT**-Frames gelesen, und der Platzhalter `0 0 0` wird verworfen. Widersprechen sich die Frames eines Ordners über die Zielposition, sagt der Lauf das und benutzt keine davon — das sind mehrere Ziele in einem Ordner, keine Position.

### Die Frames schlagen ein veraltetes Formular — und der Lauf sagt es

Die RA/Dec-Felder werden benutzt, wenn sie mit dem *übereinstimmen*, was die Frames (oder, ohne Header-Koordinaten, das Archiv) über deren eigenes Ziel sagen — und der Lauf nennt immer seine Quelle:

> *Using the RA/Dec in the form; your lights agree to 0.0".*

Eine Koordinate, die weiter als etwa zwei Bogenminuten davon entfernt ist, ist das vorige Ziel, keine Absicht — die Felder überdauern Sitzungen, und **eine Koordinate, die vom vorigen Ziel stehengeblieben ist, sieht exakt aus wie eine absichtliche**. Sie wird ersetzt, in Rot, mit beiden Werten im Log. Einen Stern anzupeilen, der *nicht* das Header-Objekt ist, geht weiterhin: nach der Ordnerwahl eintippen — zur Laufzeit wird die Abweichung gemeldet statt übersteuert.

### Die Namensabfrage bringt, was der Header nicht tragen kann

Die Schreibweise ist nicht dein Problem: Bindestriche und Leerzeichen werden auf **beiden** Seiten entfernt, `HATP-32`, `HAT-P-32`, `hatp32b` und `HAT-P-32 b` landen also beim selben Eintrag — und der **Hostname** wird mitgesucht, denn ein Name ohne Planetenbuchstaben ist das, was ein Header üblicherweise trägt. Ein System mit mehreren bekannten Planeten wird abgelehnt und die Auswahl genannt, weil sich ihre Ephemeriden unterscheiden.

Gib dem Planeten einen **Namen** — aus `OBJECT` in den Lights oder aus dem Feld *Target* in Gruppe 6 — und der Lauf holt die veröffentlichte **Ephemeride** von der NASA Exoplanet Archive. `WASP-75b` wird unterwegs zu `WASP-75 b`; ein fehlendes Leerzeichen ist der ganze Unterschied zwischen Treffer und stillem Danebengreifen.

Sie ist außerdem die **Gegenprobe** zur Position. Übereinstimmung wird gemeldet; ein Widerspruch wird *gemeldet, nicht aufgelöst*:

> *The headers and the archive disagree by 340" about where WASP-75 b is. The headers win — they came with these frames — but check the OBJECT name.*

**TESS-Kandidaten stehen in einer anderen Tabelle.** Ein Ziel namens `TOI-3540.01` ist eine *Kandidaten*-Bezeichnung — die Tabelle der bestätigten Planeten kann sie nicht kennen, und daran die ganze Ephemeride zu verlieren (Expected-Kurve, O−C, Transitfenster) war ein Rechtschreibfehler, den niemand gemacht hat. Wenn der Planeten-Lookup leer ausgeht und der Name dem TOI-Muster entspricht, wird stattdessen die `toi`-Liste des Archivs gefragt; ihre ppm-Tiefe und Stunden-Dauer werden in die Einheiten übersetzt, die der Rest des Laufs spricht. Die **TFOPWG-Disposition wird gesagt, nicht verschluckt**: PC/CP/KP/APC sind informativ, FP/FA bekommen eine rote Warnung, dass ein „Transit" auf dieser Ephemeride höchstwahrscheinlich *kein* Planet ist — und diese Warnung wiederholt sich bei Cache-Treffern, denn ein gecachter False Positive ist immer noch ein False Positive. Ein bloßes `TOI-3540` mit mehreren Kandidaten listet sie auf und fragt, welcher gemeint ist — derselbe Vertrag wie bei einem Mehrplanetensystem.

Ohne Verbindung verlierst du das O−C und sonst nichts. Die Position kam aus deinen Dateien.

### Wenn die Frames der Konvention widersprechen

Zwei Header-Fallen, hier gemessen statt angenommen.

**Das Längenvorzeichen.** FITS hat ost- gegen westpositiv nie festgelegt, und ein falsches Vorzeichen spiegelt den Standort um die halbe Erde — es scheitert nicht, es detrendet die Luftmasse nur für den falschen Ort. Eine Höhe im Header sagt zusammen mit Pointing und Zeit, wo das Teleskop tatsächlich stand:

> *SIGN FLIPPED to −110.8800: the header value would put the target 73° from the TELALT=62.59° it records, the flipped one reproduces it to 0.01°. This header is WEST-positive.*

Ein korrekter Header wird **bestätigt**, nicht gedreht. Ohne Höhe zum Prüfen bleibt alles, wie es ist, und die Annahme wird ausgesprochen.

**Das Feld, das vom Sensor wandert.** Siril verschiebt jedes Messfenster mit den Registrierungsdaten. Ein Vergleichsstern, der im Referenzbild bequem drinliegt, kann später den Chip verlassen — und wenn das passiert, scheitert der *ganze* `light_curve`-Befehl mit `generic error`, nach einer Warnung, die ein Bild nennt und nie den Stern. Der Driftbereich wird aus der Registrierung gemessen, und Sterne, die hinauswandern würden, fallen mit genau dieser Begründung raus. Verlässt das **Ziel** das Bild, hält der Lauf an: keine Blende folgt einem Stern vom Sensor.

**Wie der Fluss gemessen wird.** Die Arbeitsteilung folgt dem, was jede Seite nachweislich gut kann. Siril übernimmt Staging, Kalibrierung, Zwei-Pass-Registrierung, Sternerkennung, Plate-Solve und die Frame-Qualität — die Flussmessung macht dieses Skript selbst, so wie EXOTIC und HOPS es tun: Jedes Frame wird einmal gelesen, jeder Stern von seiner registrierungs-vorhergesagten Position aus **neu zentriert** (das „Follow Star", das Sirils `light_curve` fehlt — ein Zentroid, das weiter als 6 px wandert, hat sich auf einen Nachbarn eingerastet und wird verworfen), und der Fluss in einer subpixel-gewichteten Kreisblende gegen einen sigma-geclippten Himmelsring summiert. Mehrere Blenden werden im selben Durchgang gemessen; es gewinnt die mit dem geringsten **Punkt-zu-Punkt**-Rauschen — ein Maß, das ein Transit kaum bewegt, während eine gewöhnliche Standardabweichung sich verdreifachen würde: Eine nach Standardabweichung gewählte Blende bevorzugt, was den Transit auswäscht. Vergleichssterne werden je auf ihren eigenen Median normiert (einer, der ein Frame verpasst, kann das Ensemble so nicht stufen — die Stufe einer rohen Summe ist exakt die Form eines Ingress) und nach ihrer **Gesamt**-Streuung gegen ihre Nachbarn behalten oder verworfen, denn gerade ein langsam veränderlicher Vergleichsstern schreibt dem Ziel einen falschen Transit hinein. Die Fehler kommen aus der CCD-Gleichung, jeder Term gemessen, keiner angenommen.

An demselben driftenden 142-Frame-Lauf gemessen: Dieser Kern behält 140 Punkte bei 7,2 mmag Punkt-zu-Punkt, wo Sirils `light_curve` 67 behielt. Misst der Kern weniger als 30 % der Frames, sagt er es, und Sirils `light_curve` übernimmt — der ganze alte Weg bleibt als Rückfall intakt, einschließlich allem Folgenden.

**Die 160-Pixel-Wand.** Siril verweigert `light_curve` rundheraus, sobald ein Frame mehr als 160 px vom Referenzbild entfernt liegt. Es druckt eine Zeile, die es „Warning" nennt — „heavy drifted images" — und liefert dann einen generischen Fehler. Die Warnung *ist* der Abbruch, und sie nennt ein Frame, nie einen Stern. Die Schwelle wurde gegen Siril 1.4.4 eingegrenzt: 159,6 px laufen, 160,7 px nicht.

Das ist deshalb wichtig, weil Siril sein Referenzbild nach **Bildqualität** wählt — FWHM, Rundheit, Sternzahl. Fürs Stacken ist das richtig, hier ist es falsch. Bei EXOTICs HAT-P-32-Demodaten fiel die Wahl auf Bild 35 von 142, womit die gesamte Drift auf einer Seite lag: 218,9 px, jedes Mal abgelehnt. Die Referenz wandert jetzt. Wohin, ist genauso wichtig wie dass: Wählt man rein nach Drift, landet man beim Bild in der exakten Mitte — und das ist bei diesen Daten Bild 72, das schlechteste der Nacht: gewichtete FWHM 8,50 gegen 2,42 beim Nachbarn, 110 erkannte Sterne gegen 262. Der Befehl *läuft* dann, und das ist die gefährliche Art von falsch: der Himmelsring geriet mehr als doppelt zu groß, das Ziel wurde 200 Bogensekunden neben seiner Katalogposition zugeordnet, und 6 von 142 Frames überlebten die Photometrie.

Die Regel lautet deshalb: unter den Bildern, die Siril akzeptiert, das beste nehmen. Hier ist das Bild 70 — 149,1 px Drift, 261 Sterne, gewichtete FWHM 2,41 — und der Lauf liefert 67 gemessene Punkte, kalibriert gegen 5 Vergleichssterne. Das Qualitätsmaß ist Sirils eigene gewichtete FWHM aus den Registrierungsdaten; ohne Driftgrenze wählt dieselbe Regel Bild 35 — genau das, was Siril wählt. Der Lauf nennt beide Zahlen, wenn er die Referenz verschiebt.

Bleibt auch die beste Referenz über der Grenze, ist die Drift selbst zu groß: den Lauf auf den Abschnitt kürzen, in dem das Feld stillhält, oder die Registrierung zuerst anwenden (`seqapplyreg`) und dieses Skript auf die resampelte Sequenz richten. Das kostet eine Interpolation — deshalb ist es nicht die Vorgabe.

**Ein Meridian-Flip ist keine Drift.** Sirils Registrierung legt jedes Frame als 3×3-Homographie ab, und deren Translationsspalte ist *nicht* die Strecke, die das Feld gewandert ist, sobald das Frame zusätzlich gedreht ist. Ein 180°-Flip um die Mitte lässt jeden Stern auf demselben Stück Himmel, aber seine Translationsspalte ist Breite und Höhe des Bildes selbst — an einem echten 3008×3008-Lauf gemessen: 4253 px über die Spalte gegen 13,7 px über die Mitte. Die Drift wird deshalb gemessen, indem der Bildmittelpunkt durch die ganze Matrix geschickt wird: für eine reine Verschiebung ergibt das genau die Translation, für den Flip die Wahrheit.

**`-autoring`.** Sirils Option, die Ringradien aus der FWHM des Bildes abzuleiten, lässt `light_curve` mit „The given coordinates are not in the image" abbrechen — bei Koordinaten, die nachweislich darin liegen. Derselbe Befehl ohne die Option, auf derselben Sequenz und denselben Sternen, liefert die Kurve. Die Radien werden deshalb vorher mit `setphot` gesetzt, mit Sirils eigenen Faktoren 4,2 und 6,3 mal FWHM. Die geben seine Rechnung genau wieder: für FWHM 1,797542 protokolliert Siril 7,5 und 11,3, die Faktoren ergeben 7,55 und 11,32. An der Messung ändert sich nichts, nur am Weg, auf dem die Zahlen zu Siril gelangen.

**Sirils Prozess, der endet.** Zwölf hintereinander scheiternde `light_curve`-Aufrufe haben Siril einmal mitgerissen, übrig blieb `[Errno 32] Broken pipe`. Die Proben brechen jetzt nach einer Handvoll gleichartiger Fehlschläge ab und benennen das Muster, und ein Broken Pipe wird als Absturz auf Sirils Seite gemeldet — neu starten — statt als abgelehnter Befehl.

**Die Bildskala.** Siril liest sie aus `FOCALLEN` und `XPIXSZ`; fehlt beides, greift es auf den zuletzt *gespeicherten* Wert zurück — das Teleskop des vorigen Ziels. Bei 5,21″/px hieß das: Suche nach einem 0,46°-Feld, wo 0,94° richtig wäre, und der Solve scheiterte mit *Generic error*, was nach kaputtem Solve klingt statt nach falschem Maßstab. `IM_SCALE`, `SECPIX` und Verwandte werden jetzt direkt gelesen, sonst aus der Optik abgeleitet, und auf der Kommandozeile übergeben.

**Zeitstempel.** N.I.N.A. schreibt sieben Nachkommastellen, MicroObservatory schreibt *Ortszeit* mit `−0700`-Versatz. Beides ergab vorher stilles NaN — das zweite ist ein Sieben-Stunden-Fehler in einer Größe, die in Minuten interessiert, das erste kostete bei jedem Lauf die Basen Seeing, Himmel und Sternzahl.

### O−C: der eigentliche Beitrag einer Nacht

```
O-C            +4.20 min +/- 5.0 min  (consistent with the prediction)
               epoch 2114 of WASP-75 b, P = 2.484193 d
```

Genau diese Zahl sammeln ExoClock und ETD. Bisher maß der Fit T0 mit kalibriertem Fehlerbalken und hatte nichts, wogegen er das halten konnte.

Zwei Sicherungen: **verweigert**, wenn die Zeiten nicht BJD_TDB sind — die Epoche des Archivs ist BJD_TDB, eine JD_UTC davon abzuziehen legte acht Minuten Versatz in eine Größe, die in Minuten interessiert — und die **Epoche steht immer neben der Abweichung**, weil sich eine veraltete Periode über Tausende Epochen irgendwann im Transit vergreift.

Woher die Position auch kam, der nächste Schritt meldet weiterhin, wie weit sie von einer echten *Detektion* entfernt landet:

> *Target at (1503.4, 1505.6) — nearest detection, 0.9" from the position you gave.*

Still danebenzielen kann hier nichts.

---

## 5. Die Oberfläche

**Linkes Panel**, vier nummerierte Gruppen in der Reihenfolge der Benutzung:

| Gruppe | Inhalt |
|---|---|
| **1 · Subs** | Ordnerwahl, Symlink/Kopie |
| **3 · Zielstern** | Auswahlmodus (startet auf *From the frames*), Planetenname, Archivabfrage, Pixel- oder RA/Dec-Felder |
| **3 · Photometry** | Anzahl Vergleiche, SNR-Grenze, Kanal, automatische Ringradien |
| **4 · Analysis** | Airmass-Detrend, Standort, Binning |

**Rechtes Panel**, vier Reiter: **Light curve** (Kurve, Fit, Residuen), **Result** (alles in Worten), **Stars** (Ziel und Vergleiche mit SNR), **Log** (jedes Kommando und jede Ablehnung).

---

## 6. Den Zielstern wählen

Drei Modi, und alle drei enden bei einem **erkannten** Stern:

- **Hellster Stern im Feld** — häufiger richtig, als man denkt. Ein Transit-Wirtsstern ist meist der Grund, warum das Feld so eingerahmt wurde.
- **Pixelposition** — vom ersten Frame abgelesen.
- **RA / Dec** — braucht plate-solvte Subs.

Pixel und RA/Dec **rasten beide auf den nächstgelegenen erkannten Stern ein**, und das Log nennt die Distanz. Eine Position zwei Pixel neben dem Schwerpunkt setzt die Apertur für den ganzen Lauf außermittig, und der Flussverlust ändert sich mit dem Seeing — genau die Form eines falschen Trends.

RA wird als **Stunden** gelesen, wenn Doppelpunkte oder Leerzeichen vorkommen (`18:18:45`), und als **Grad** bei einer bloßen Dezimalzahl (`274.6875`). Das Skript rät nicht anhand der Größe: RA 12,5 ist so oder so plausibler Himmel.

---

## 7. Die Vergleichssterne

Vier Filter entscheiden, jeder gegen ein anderes Versagen:

| Filter | Warum |
|---|---|
| **Gesättigt** | Ein abgeschnittener Kern skaliert nicht mit der Transparenz — ein gesättigter Vergleichsstern macht aus jeder Wolke einen falschen Transit |
| **SNR unter der Grenze** | Ein Vergleichsstern bringt sein eigenes Photonenrauschen ins Ensemble. Unter etwa 20 fügt er mehr Streuung hinzu als Referenz |
| **Näher als 10 × FWHM** | Die Aperturen teilen sich Himmels-Annulus und Sternflügel. Die Kontamination hängt vom Seeing ab, wandert also durch die Nacht und sieht aus wie ein langsamer Trend |
| **Nicht isoliert** | Dasselbe Argument, gerichtet auf jeden Nachbarn statt auf das Ziel. Ein Stern im eigenen Himmels-Annulus des Vergleichssterns legt einen Teil seines Lichts in die Apertur und den Rest in die Himmelsschätzung, und sein Anteil wandert mit dem Seeing. Der Radius ist Sirils eigene Geometrie, kein Geschmack: `-autoring` setzt den Außenring auf 6,3 × FWHM, zwei Annuli berühren sich also ab dem Doppelten nicht mehr |

Jede Ablehnung steht im Log und im Report, und die Aufstellung erfasst **jeden** erkannten Stern — auch die, die alle vier Filter bestanden haben und schlicht nicht gebraucht wurden. Ohne diese letzte Zeile liest sich „6 gewählt, 668 abgelehnt" bei 864 Erkennungen wie ein Feld, das kaum einen Vergleichsstern hergab — dabei gab es 195 her, und die besten 6 wurden genommen.

Das Ziel lässt sich nicht verwerfen, deshalb wird dieselbe Geometrie für es *gemeldet*: ein Nachbar im Annulus wird genannt, bevor die Photometrie läuft.

> **Eine offene Frage, festgehalten, damit sie nicht überrascht.** Sirils Logzeile `Photometry for star at X, Y in image 0` stimmt nicht immer mit dem `-refat=` überein, das sie erzeugt hat — in einem Lauf kamen drei von sechs Vergleichssternen 16, 33 und 63 px daneben zurück. Die naheliegende Lesart, `-refat` sei ein Suchhinweis und Siril habe einen Nachbarn erwischt, hält Sirils eigenem Log nicht stand: die Zeilen `No star found in the area … around X,Y` setzen das Suchfenster auf `angefordert − 19` in beiden Achsen, und zwei dieser drei gemeldeten Positionen liegen *außerhalb* ihres eigenen 38-px-Fensters. Ein Fit kann nicht außerhalb des Fensters landen, in dem er lief — die Zeile meldet also vermutlich eine andere Größe und keine Fehlmessung. Solange das nicht geklärt ist, wird kein Filter darauf gebaut.

**Wie viele?** Mehr Vergleichssterne mitteln das Ensemble-Rauschen herunter, aber jeder weitere ist schwächer als der vorige, der Gewinn flacht schnell ab. Fünf ist eine gute Vorgabe. Unter zwei gibt es kein Ensemble: ein einzelner Vergleichsstern schreibt seine eigene Variabilität direkt in deine Kurve.

---

## 8. Die Airmass-Rampe entfernen

### Warum die naheliegende Lösung falsch ist

Eine Gerade durch alle Punkte legen und abziehen — und schon ist ein Teil der Transittiefe mit weg. Der Standardfall am Abendhimmel: der Stern geht während des Egress unter, Airmass und Abdunkelung steigen *gemeinsam*, die Gerade teilt die Differenz.

Die übliche Reparatur, ein Sigma-Clip mit derselben Gerade als Startwert, ist in genau dem Fall wirkungslos, der sie motiviert: der Startwert kippt bereits in die Delle, also überschreitet kein In-Transit-Residuum je die Schwelle.

### Was hier stattdessen passiert

**Durchgang 1** ist ein *einseitig getrimmter* Fit. Die Gerade wird auf den hellsten 60 % der Residuen iteriert. Die Delle liegt auf der schwachen Seite und fällt damit in die verworfenen 40 %, sobald sich die Gerade aufrichtet. Ein Abschlussdurchgang nimmt alle Punkte innerhalb von 2 MAD-σ wieder auf, damit die Baseline alle echten Out-of-Transit-Daten nutzt.

**Durchgang 2** fittet die Baseline *direkt auf den Punkten außerhalb des gefitteten Transitfensters*. Exakt, wo Durchgang 1 nur gut ist.

### Gemessen, nicht behauptet

Synthetische Läufe mit bekannter 30-mmag/Airmass-Rampe und 15-mmag-Transit, 15 Rauschrealisierungen je Punkt — mittlerer Fehler der rekonstruierten Steigung:

| Duty Cycle | einfacher Fit | nur Durchgang 1 | mit Durchgang 2 |
|---|---|---|---|
| 25 % | 6,2 % | 0,9 % | 0,8 % |
| 50 % | 10,1 % | 1,0 % | 1,0 % |
| 60 % | 10,7 % | 2,3 % | 0,9 % |
| 75 % | 10,8 % | **10,6 %** | 2,7 % |

Durchgang 1 gewinnt eine Größenordnung gegenüber dem einfachen Fit und hält bis etwa 50 %, wo ihm die unberührte Baseline zum Trimmen ausgeht. Bei 75 % Abdeckung ist er *nicht besser als der Fit, den er ersetzt* — und Durchgang 2 trägt das Ergebnis von dort.

Über 50 % **nennt der Report, welcher Durchgang die Baseline geliefert hat**, denn ab dort sind die beiden nicht mehr austauschbar. Lief Durchgang 2 nicht (kein Transit gefunden, also kein Fenster zum Verankern), ist die Tiefe bei hoher Abdeckung eine **Untergrenze**, keine Messung.

Die Lösung ist kein besserer Algorithmus, sondern mehr Baseline: früher anfangen, später aufhören.

---

### Mehr als Luftmasse: was Siril ohnehin misst

Die Luftmasse ist nicht das Einzige, was durch die Nacht driftet. Drei weitere Größen tun es, und Siril misst alle drei für jeden Frame bei der Registrierung — dieses Skript las sie für die Meridian-Flip-Prüfung und warf sie weg:

| Basis | Warum sie die Kurve bewegt |
|---|---|
| **FWHM** | Schlechteres Seeing zieht den Stern auseinander, eine feste Apertur fängt dann einen kleineren Anteil seines Lichts. Am stärksten bei untersampelten Sternen |
| **Himmelspegel** | Mond, Dämmerung und Lichtverschmutzung ändern, was der Annulus abzieht — der Fehler skaliert mit der Aperturfläche |
| **Sternzahl** | Selbst keine Systematik — sondern das, wonach eine durchziehende Wolke *in den Daten aussieht* |

Sie werden gemeinsam in einer Ausgleichsrechnung gefittet, jede Basis zentriert und skaliert, damit Luftmasse (1–3), FWHM (2–5 px) und Himmel (Hunderte ADU) in eine Matrix passen.

**Verankert auf den Out-of-Transit-Zeilen — und ohne sie verweigert es die Arbeit.** Alle drei driften monoton durch die Nacht, mindestens eine korreliert also meist mit der Delle; ein Fit über alle Punkte würde die Tiefe darin aufsaugen. Dieselbe Falle, gegen die der Luftmassen-Detrend bereits absichert, und der Grund, warum das als *dritter* Durchgang läuft — nach dem Transitfenster.

Gemessen an einem synthetischen Lauf mit eingespieltem Seeing- und Himmelstrend: Streuung außerhalb des Transits **20,8 → 3,9 mmag** gegen einen Rauschboden von 4,0 mmag, Tiefe am flachen Boden unangetastet.

`light_curve.dat` enthält keine Framenummer, Zeilen werden also über die Belichtungsmitte zugeordnet. Über die Reihenfolge wäre falsch — die von Siril verworfenen Frames liegen verstreut im Lauf.

---

## 9. Der Transit-Fit

### Ein randverdunkeltes Modell — und warum das Trapez weichen musste

Das Trapez wurde hier damit verteidigt, dass beide bei Amateurpräzision ununterscheidbar seien. **Das war falsch, und zwar messbar.** An einen echten randverdunkelten Transit gefittet:

| Rp/R★ | wahre Tiefe | Trapez | **Bias** | χ²/ν |
|---|---|---|---|---|
| 0,08 | 8,27 mmag | 7,76 | **−6,2 %** | 1,05 |
| 0,10 | 12,95 mmag | 12,23 | **−5,6 %** | 1,02 |
| 0,15 | 29,34 mmag | 27,89 | **−4,9 %** | 1,11 |

Systematisch 5–6 % zu flach — und **χ²/ν bleibt bei 1,0**, nichts in der Ausgabe hätte es je gesagt. Ein echter Stern ist am Rand dunkler, ein Transit hat also einen *runden* Boden; ein Trapez teilt die Differenz und verliert dabei Tiefe.

Die gesuchten Formen sind jetzt echte Geometrien: vier Planet-Stern-Radienverhältnisse mal zwei Stoßparameter — genau die acht Varianten, die vorher die acht Ingress-Anteile lieferten. Der Bias beträgt **+0,6 / −0,0 / −0,2 / +0,1 %**.

**Sonst ändert sich nichts.** Jede Form ist eine *Schablone* auf normierter Phase, einmal gebaut und pro Knoten interpoliert — das Modell bleibt **linear in der Tiefe**, der geschlossene Löser, der Determinismus und die Zusicherung „kein Optimierer" überleben alle drei. Ein physikalisch freies Rp/R★ würde Tiefe und Form koppeln und alle drei kosten. (Die Bedeckung wird *radial* integriert — der vom Planeten überdeckte Bogen bei Radius r hat eine geschlossene Form — also keine elliptischen Integrale, keine neue Abhängigkeit, und gegen eine unabhängige 2-D-Integration verifiziert.)

> **Das Rp/R★ der Schablone ist ein Formindex, kein Planetenradius.** Bei freier Dauer passt eine kleinere Schablone gestreckt fast genauso gut, dieser Wert liegt also systematisch unter der Wahrheit. Die **Tiefe** ist die Messung, und beide Reports sagen das.

### Zwei Tiefen-Konventionen, beide gemeldet

Der Fit misst die **randverdunkelte zentrale Tiefe** — den tiefsten Punkt der Kurve. EXOTIC, HOPS und AstroImageJ geben alle **(Rp/R★)²** an, und mit Randverdunkelung ist die Sternmitte heller als der Mittelwert, die zentrale Tiefe bei einem sonnenähnlichen Stern also ~20 % *tiefer* als (Rp/R★)². Zwei korrekte Werkzeuge, die diese zwei Zahlen vergleichen, sehen aus wie ein Widerspruch — genau so wurde es gefunden, gegen EXOTICs eigenes Referenzergebnis für seine Beispieldaten.

Die gemessene Tiefe wird deshalb zusätzlich **durch dasselbe randverdunkelte Modell, mit dem gefittet wurde**, in ein *gemessenes* Rp/R★ (nicht der Schablonen-Index oben) und dessen Quadrat übersetzt. Alle drei Zahlen stehen im Log, in beiden Report-Formen und im AAVSO-Kopf, jeweils beschriftet:

```
depth      30.23 ± 2.55 mmag  (randverdunkeltes ZENTRUM)
Rp/Rs      0.1525 ± 0.0064
(Rp/Rs)^2  2.33 ± 0.19 %      <- DIESE Zahl mit EXOTIC/HOPS/AIJ und dem Archiv vergleichen
```

An EXOTICs HAT-P-32-Beispieldaten liest sich das als 0,1525 ± 0,0064 gegen EXOTICs 0,1541 ± 0,0033 — 0,2 σ auseinander.

### Alles wird gleichzeitig gefittet

Die alte Abfolge war: detrenden, fitten, auf dem gefitteten Fenster neu detrenden, neu fitten. Drei Durchgänge, jeder behandelte die vorige Baseline als *exakt bekannt*. Ist sie nicht — die Baseline hat eine Unsicherheit, und ein sequenzieller Fit wirft sie weg, statt sie in Tiefe und Mittelzeit zu tragen.

Luftmasse, Seeing, Himmelspegel und Sternzahl stehen jetzt in **derselben Designmatrix** wie der Transit, an jedem Gitterknoten gemeinsam gelöst. Zwei Folgen:

- **Der Transit kann nicht mehr in eine korrelierte Basis aufgesogen werden.** Genau dafür existierte die Out-of-Transit-Verankerung, und sie wird nicht mehr gebraucht: der Transit ist seine eigene Spalte. Geprüft gegen eine Basis, die absichtlich *wie der Transit geformt* ist — die Tiefe überlebt mit 11,2 von 12,0 mmag, wo ein sequenzieller Detrend sie gefressen hätte.
- **Die Unsicherheit der Baseline landet dort, wo sie hingehört**, in Tiefe und Mittelzeit.

Und es ist **schneller**. Von Knoten zu Knoten ändert sich nur die Transitspalte, die Gram-Matrix des Rests wird einmal berechnet: 11,1 µs pro Knoten gegen vorher 13,8, ein ganzer Fit in 0,56 s statt 1,0.

### Ein Gitter, kein Optimierer

Die Suche läuft über **T0**, **Dauer** und **Form**. An jedem Knoten werden Tiefe, Baseline und jeder Systematik-Koeffizient *analytisch* gelöst — das Modell ist in allen linear, ein kleines lineares System liefert den exakten besten Satz.

Stark korrelierte Parameter sind genau die Stelle, an der ein lokaler Optimierer in ein Rauschminimum läuft und je nach Startpunkt etwas anderes liefert. Das Gitter liefert bei jedem Lauf dasselbe, kann nicht scheitern zu konvergieren, und seine Auflösung ist eine Zahl zum Nachlesen statt einer Toleranz, die niemand prüft.

Die Tiefe ist **positiv erzwungen** — der Stern wird schwächer — der Fit kann also keine Aufhellung „nachweisen" und Transit nennen.

---

### T0 mit Fehlerbalken

Die Transitmitte ist die Zahl, für die ExoClock und ETD existieren. Sie wird aus der **Krümmung** der χ²-Fläche entlang T0 gemessen, mit bei jedem Schritt neu gelöster Tiefe und Baseline und neu minimierter Dauer, anschließend mit dem Rotrausch-β skaliert.

Zwei Entwürfe wurden vorher gemessen und verworfen, beide Fehlschläge sind lehrreich:

- **Nach außen laufen bis Δχ² = 1** blieb bei jeder Tiefe unter 12 mmag bei 86 s stehen — 0,7 Abtastintervalle. Ein Trapez auf abgetasteten Daten hat eine *holprige* χ²-Fläche: eine T0-Verschiebung unter einer Kadenz ändert, welche Punkte ins Fenster fallen. Der Lauf maß die lokale Delle, nicht die Einhüllende.
- **Ein breiteres Parabelfenster** (0,3 Dauern) überschätzte den Balken bei jeder Tiefe um das 1,5- bis 1,75-fache.

Fünf Abtastintervalle treffen die Wahrheit. Gemeldet gegen die tatsächlich wiedergefundene Streuung, 50 Läufe je Tiefe bei 4 mmag pro Punkt:

| Tiefe | σ(T0) gemeldet | Streuung gemessen |
|---|---|---|
| 20 mmag | 53 s | 47 s |
| 12 mmag | 91 s | 90 s |
| 8 mmag | 134 s | 136 s |
| 6 mmag | 173 s | 191 s |

Diese Messung deckte noch etwas auf. Das grobe Suchgitter quantisierte T0 auf (0,7 × Spanne) / 120 — **105 s bei einem Fünf-Stunden-Lauf**. Über 60 Läufe eines 20-mmag-Transits lieferte *jeder* Fit denselben T0, und bei jeder geringeren Tiefe war der MAD der gefundenen Zeiten exakt 1,4826 × ein Gitterschritt: die Daten wurden auf die Suche gerundet. Der Gewinnerknoten bekommt jetzt einen lokalen Durchgang mit 1/20 des T0-Schritts.

### χ²/ν: passt das Modell überhaupt?

Um 1 heißt, das Modell beschreibt die Daten. Deutlich über 1 heißt, es tut es nicht — Systematik oder eine Form, die die Schablonenfamilie nicht kann. Deutlich unter 1 heißt, die Rauschschätzung ist zu groß, meist weil im Out-of-Transit-Fenster noch ein Teil des Ereignisses steckt.

Der Rauschboden ist bewusst **modellunabhängig**: die Residuenstreuung eines Fits kann diesen Fit nicht beurteilen — teilt man Residuen durch ihr eigenes RMS, kommt 1 heraus, egal ob das Modell stimmt. Er kommt daher aus dem MAD der Out-of-Transit-Residuen, ersatzweise aus dem MAD der ersten Differenzen ÷ √2. Gemessen: 1,0 auf reinem Rauschen, 3,1 mit einem nicht modellierten 20-mmag-Buckel.

---

## 10. Ist es echt?

Die Signifikanz ist der In/Out-Kontrast über seinem eigenen Standardfehler:

```
(Mittel_in − Mittel_out) / σ × √(N_in·N_out / (N_in+N_out))
```

Drei bewusste Entscheidungen stecken darin.

**Der Skalenfaktor ist nicht √N_gesamt.** Die Baseline vor dem Ingress zu verdoppeln macht eine flache Delle nicht doppelt so sicher — die Unsicherheit wird davon dominiert, wie viele Punkte *innerhalb* des Ereignisses liegen.

**Der Kontrast wird gemessen, nicht der gefitteten Tiefe entnommen.** Das Trapez hat keinen freien Baseline-Term, also kann der Fitter auf transitfreien Daten immer einen kleinen Versatz als breite flache „Delle" mit von null verschiedener Tiefe absorbieren. Der eigene In/Out-Kontrast der Daten ist dort etwa null — reine Rauschläufe werden abgelehnt, wo ein tiefenbasierter Test sie durchließe.

**Er wird auf jede Seite getrennt angewandt, und die schwächere zählt.** Das ist die wichtigste.

### Warum beide Seiten

Ein echter Transit **kehrt zur Baseline zurück, die er verlassen hat**. Ein Trend nicht.

Fasst man beide Seiten zu einem Out-of-Transit-Mittel zusammen, geht genau dieser Unterschied verloren. Auf einer monotonen Rampe — unkorrigierte Extinktion, ziehende Wolke, Fokusdrift — legt der Fitter sein Fenster über die schwache Hälfte, der gepoolte Kontrast ist echt groß, und ein *Trend wird als Transit gemeldet*. Auf einer synthetischen Rampe ganz ohne Transit erreicht der gepoolte Test **+25σ**; der zweiseitige liefert **−10σ** und lehnt ab.

Der Preis ist eine etwas kleinere Zahl bei echter Detektion: jede Seite trägt etwa die halbe Baseline, und das Minimum zweier verrauschter Größen liegt unter beiden. In den obigen Läufen wurden aus 127σ genau 110σ. Das ist die richtige Richtung für einen Test, dessen einzige Aufgabe es ist, nicht zu überziehen.

Ein Transit, der **vom Anfang oder Ende des Laufs abgeschnitten** ist, liefert Signifikanz null — nicht einfach weniger. Ohne Baseline auf beiden Seiten lässt sich die Frage mit keiner Methode beantworten.

### Die Nachweisschwelle ist kalibriert, nicht gewählt

Die Signifikanz ist die beste aus rund **40 000** Gitterpunkten — 121 Mittelzeiten × 41 Dauern × 8 Ingress-Anteile. Die Formel weiß davon nichts, also **ist es kein gaußsches σ**: eine derart große Suche findet auf reinem Rauschen einen Kontrast, den ein einzelner vorab festgelegter Test nie fände.

Deshalb wurde die Schwelle gemessen. 1200 transitfreie Weißrausch-Läufe (150 Punkte, 5 h, 4 mmag pro Punkt) durch dieselbe Suche, daneben die Nachweisraten für eingespielte Transits:

| Schwelle | Falschalarm | 4 mmag | 5 mmag | 6 mmag | 8 mmag | 12 mmag |
|---|---|---|---|---|---|---|
| 3,0 σ | **7,67 %** | 88 % | 95 % | 100 % | 100 % | 100 % |
| 3,5 σ | 1,92 % | 70 % | 91 % | 97 % | 100 % | 100 % |
| 4,0 σ | 0,50 % | 45 % | 77 % | 93 % | 100 % | 100 % |
| **4,5 σ** | **0,25 %** | 29 % | 57 % | **89 %** | **100 %** | **100 %** |
| 5,0 σ | 0,00 % | 15 % | 40 % | 78 % | 100 % | 100 % |

Eine 3σ-Schwelle lässt **jeden zehnten** reinen Rauschlauf durch — wo „3σ" allgemein als einer von 750 gelesen wird. **4,5σ** halbiert den Falschalarm gegenüber 4,0 für vier Prozentpunkte Nachweis bei 6 mmag und keinen bei 8, und kostet den Fall 4–5 mmag: eine Delle in der Größe der Punktstreuung, die aus einer einzelnen Nacht ohnehin nie belastbar war.

> **Die Tabelle wurde dreimal neu gemessen.** Die T0-Verfeinerung (~2700 zusätzliche Knoten pro Fit) hat jede Rate etwa verdoppelt — mehr Suche findet im reinen Rauschen ein tieferes Minimum. Die robuste Streuung hat sie erneut angehoben, weil ein MAD ein kleinerer Nenner ist als eine von Ausreißern aufgeblähte RMS. Das randverdunkelte Modell, gemeinsam mit der Systematik gefittet, hat sie wieder gesenkt: eine runde Form passt schlechter auf Rauschen als eine mit freier Ecke. Die Rate bei 4,5σ kam **vor und nach dieser letzten Änderung auf 0,25 % — Zufall, nicht Stabilität**. Eine Kalibriertabelle gilt nur für die Suche, die Statistik *und* das Modell, an dem sie gemessen wurde.
>
> Gemessen *ohne* den Spike-Clip, was die konservative Richtung ist: auf reinem gaußschem Rauschen entfernt der Clip etwa 0,2 Punkte pro Lauf und stutzt genau die Flanke, um die es in dieser Tabelle geht.

---

### Die Apertur wird gewählt, nicht angenommen

Die Aperturgröße ist die wirksamste Zahl der Aperturphotometrie, und bisher war sie das, was `-autoring` aus der FWHM ableitete. Zu klein verliert einen *seeingabhängigen* Anteil des Sterns — eine Systematik, die mit der Nacht wandert. Zu groß sammelt Himmel und Nachbarn. Das Optimum liegt dazwischen und hängt von den Daten ab.

Sechs Radien von **0,75 bis 2,5 × FWHM** werden je einmal über Sirils eigenes `setphot` + `light_curve` photometriert, und der mit der geringsten robusten Streuung gewinnt. Die Zahl der gemessenen Frames entscheidet bei Gleichstand: eine Apertur, die gut abschneidet, weil sie weniger Frames misst, hat nichts gewonnen.

Kostet sechs zusätzliche Durchgänge. Unter **4 · Photometry** abschaltbar, wenn dir Tempo wichtiger ist.

### Vergleichssterne werden gemessen, nicht nur gefiltert

Jeder Kandidat wird **gegen die anderen** photometriert — dieselbe Differenzmessung, die das Ziel bekommt — und an der robusten Streuung seiner eigenen Kurve beurteilt. Ein Stern, der gegen seine Kollegen schwankt, schreibt dieses Schwanken invertiert in die Zielkurve, und nichts sonst in diesem Skript würde es je bemerken.

Die Schwelle ist ein **Verhältnis zum Ensemble-Median**, keine absolute Millimagnitude: eine gute und eine schlechte Nacht unterscheiden sich um einen Faktor, eine feste Grenze würde in der einen alles und in der anderen nichts verwerfen. Verworfen wird nie so weit, dass weniger als zwei Vergleichssterne bleiben — mit einem verdächtigen Vergleich zu messen ist besser als gar nicht, solange der Verdacht aktenkundig ist, und das ist er.

Kein Katalog, kein Netz. Ein Veränderlichkeits-Flag aus dem AAVSO-VSX wäre besser, wo es existiert — aber der Stern muss *im* Katalog stehen, und die, die eine Amateur-Lichtkurve ruinieren, stehen meist nicht drin.

### Ein Satellit darf nicht den Nachweis kosten

Es gab überhaupt keine Ausreißer-Rejektion, und das wog schwerer, als es aussieht. Gemessen an einem echten 12-mmag-Transit bei 4 mmag pro Punkt:

| Ausreißer | Tiefe | T0-Versatz | **Signifikanz** | χ²/ν |
|---|---|---|---|---|
| keiner | 12,0 mmag | 47 s | **12,1σ** | 1,03 |
| 50 mmag | 11,9 mmag | 92 s | 7,5σ | 2,00 |
| 100 mmag | 12,5 mmag | 55 s | **3,2σ** | 4,99 |

Die *Parameter* bewegten sich kaum — ein Trapez über 150 Punkte steckt einen Punkt weg. Kaputt ging der **Nenner**: die Streuung hinter der Signifikanz war eine gewöhnliche RMS, und ein Ausreißer bläht sie auf. Ein gemessener Transit wurde als *nicht behauptet* gemeldet.

Zwei Änderungen beheben es, und beide waren nötig:

1. **Die Streuung ist jetzt der MAD**, wie jede andere Streuung in dieser Datei. Das allein holt 3,2σ → 6,9σ zurück, auf sauberen Daten sind beide auf 1 % gleich.
2. **Der Ausreißer wird entfernt.** Referenz ist ein gleitender Median über neun Punkte — weit kürzer als jeder Transit — eine glatte mehrpunktige Delle geht also unangetastet durch (geprüft bei 12, 30 und 60 mmag: kein einziger Punkt verloren), während eine Ein-Frame-Spitze gegen ihre eigenen Nachbarn heraussticht. Das bringt den Rest, zurück auf 11,9σ.

Es entfernt nie mehr als **5 %** eines Laufs. Darüber *sind* die Ausreißer die Daten, und der Lauf sagt das stattdessen:

> 49 point(s) exceed 4 sigma, more than 5% of the run — that is a noisy night, not an outlier population, and nothing was removed

### Die AAVSO-Datei

`AAVSO_exoplanet.txt` landet neben der CSV, im Format von Exoplanet Watch: `#TYPE=EXOPLANET`, Beobachtercode, Filter, `#DATE_TYPE=BJD_TDB`, der **aufgelöste** Zielname (nie ein veralteter Formulareintrag), dann `DATE,DIFF,ERR,DETREND_1`. Transitmitte samt Fehler, die zentrale Tiefe samt Fehler, **`#RPRS`, `#RPRS_ERR` und `#DEPTH_RPRS2_PCT`** (die Konvention, die EXOTIC und AIJ angeben — siehe §9), Dauer und das Rotrausch-β stehen im Kopf.

**Verweigert, solange die Zeiten nicht BJD_TDB sind.** Der Kopf deklariert dieses System; JD_UTC darunter zu schreiben hieße, einer Einreichung einen Acht-Minuten-Fehler mitzugeben, den niemand sehen kann.

Es wird nichts irgendwohin geschickt. Einreichen ist deine Entscheidung — die Datei sorgt nur dafür, dass der Lauf nicht einen Schritt vor dem Zweck stehen bleibt.

---

## 11. Die Ausgabe lesen

Alles landet in einem Ordner `lightcurve/` neben deinen Subs:

| Datei | Inhalt |
|---|---|
| `lightcurve.csv` | Jeder Punkt: JD, roh, zentriert, detrended, Fehler, Airmass |
| `lightcurve.png` | Das Diagramm, wenn du es speicherst |
| `report.txt` | Der ganze Lauf als Text — Vergleiche, Ablehnungen, Methode, Ergebnis |

**RMS** ist robust (MAD-basiert), eine einzelne Satellitenspur bläht ihn also nicht auf. Vergleiche ihn mit der gesuchten Tiefe: 15 mmag Transit bei 5 mmag Streuung ist komfortabel, bei 15 mmag braucht es die ganze Nacht.

**Das Residuenfeld** zeigt, was das Modell verfehlt hat. Flaches Rauschen ist das Ziel; Struktur heißt, da ist noch etwas drin. In seiner Ecke stehen die Residuen-STD und die **Lag-1-Autokorrelation** mit Urteil (white-noise-like / mild structure / structure left) — der Rot-Rausch-Indikator, der sauberes Rauschen von einer übrig gebliebenen Systematik trennt.

![Svenesis LightCurve — eine ehrlich erzählte Nicht-Detektion](https://github.com/sramuschkat/Siril-Scripts/raw/main/screenshots/Svenesis_LightCurve_1_0_4.jpg)

*Alles Folgende in einem Bild (TOI-3540.01, eine Nicht-Detektion): die Uhrzeit-Achse oben, der türkise erwartete Transit mit seinen Kontaktzeiten, der Flip-Marker bei 00:57 — und der nicht beanspruchte 0,0σ-Fit, der sich an die Flip-Stufe klammert, ohne Detektionsmarker, die ihn aufhübschen.*

**Das Diagramm trägt das ganze Ergebnis.** Die Legende nennt T0 und Rp/R★ mit Fehlern und die Detrending-Basen — ein Screenshot ist damit eine vollständige Messung, kein Appetithappen. Vom Spike-Filter verworfene Punkte erscheinen als rote Kreuze („N outlier(s), not fitted"), statt still zu verschwinden — du beurteilst selbst, dass es ein Satellit war und kein Egress. Die **Fehlerbalken** pro Punkt haben einen Ein/Aus-Schalter (aus als Vorgabe; ein langer Lauf wird sonst zum Lattenzaun). Neben dem gefitteten Modell wird der **erwartete Transit aus der Archiv-Ephemeride** in Türkis gezeichnet — *ob der Fit etwas behauptet oder nicht*. Bei einer Detektion **ist** der Versatz zwischen beiden Kurven das O−C, in der Legende in Minuten mit Fehler beziffert. Bei einer Nicht-Detektion ist die Vorhersage die wertvollere Hälfte: Eine Vorhersage im Fenster sagt „(no transit claimed by the fit)" — beide Fakten in einem Bild —, und eine Vorhersage außerhalb nennt den nächsten Transitmittelpunkt in Stunden Abstand zu deinem Lauf. So weißt du, ob die Nacht den Transit verpasst hat oder der Transit die Nacht. Die Epoche kommt aus der Fenstermitte, nie aus dem gefitteten T0 — ein davongelaufener Fit kann die Vorhersage nicht mitziehen.

**Das Diagramm spricht die Sprache deines Planungstools.** Eine Nacht wird in Uhrzeit geplant („Start 21:50 … Flip 00:55"), aber in Julianischen Daten gemessen — deshalb zeigt eine zweite Zeitachse oben HH:MM: in *Lokalzeit*, wenn deine Frames N.I.N.A.s `DATE-LOC`-Keyword tragen (das Paar `DATE-OBS`/`DATE-LOC` liefert den UTC-Versatz des Standorts, Sommerzeit inklusive, nichts zu konfigurieren), sonst in UTC — und die Achse sagt, was von beidem. Die vorhergesagten Kontaktzeiten des Transits (Start/Mitte/Ende) stehen unten als Uhrzeiten, und ein Meridian-Flip wird als gestrichelte Markierung in beiden Feldern genau dort gezeichnet, wo das Feld gedreht hat — so prüfst du mit bloßem Auge, ob eine Stufe oder ein „Ingress" mit ihm zusammenfällt. Die Uhrzeit-Beschriftungen ziehen zuerst die BJD_TDB-Korrektur wieder ab; eine Uhrzeit in baryzentrischer Zeit wäre um Minuten falsch. Die vertikalen Linien folgen einer Grammatik: **Orange gestrichelt ist der Flip, türkis gepunktet sind die vorhergesagten Kontakte, und eine farbige gestrichelte Mittransit-Linie gibt es nur bei einer beanspruchten Detektion** — ein nicht beanspruchter Fit behält seine ehrlich beschriftete Kurve, trägt aber keine Detektionsmarker, weil ein 0,0σ-Fit, der sich an die Flip-Stufe klammert, sonst eine zweite gestrichelte Linie direkt neben die echte stellen würde.

**Binning ist nur Darstellung.** Der Fit sieht immer jeden Punkt — vorher zu binnen würde genau die Streuung wegwerfen, die der Signifikanztest braucht, um ehrlich über sich selbst zu sein.

---

## 12. Gute Daten aufnehmen

| | |
|---|---|
| **Baseline** | Mindestens eine Transitdauer *vor* dem Ingress anfangen und ebenso lange nach dem Egress weiterlaufen |
| **Nicht sättigen** | Weder Ziel noch Vergleiche. Spitze unter etwa halbem Full-Well halten |
| **Leicht defokussieren** | Gegenintuitiv, aber Standard: den Stern über mehr Pixel zu verteilen mittelt Flatfield-Fehler weg und schafft Sättigungsreserve. FWHM 4–6 px ist ein guter Zielwert |
| **Nicht dithern** | Das Gegenteil des Stacking-Rats. Dithern schiebt den Stern auf Pixel mit anderer Empfindlichkeit — Rauschen, das man nicht braucht, wenn der Stern ohnehin stillsteht |
| **Durchgehend gleiche Belichtung** | Ein Wechsel mitten im Lauf ändert Sättigungsreserve und Szintillationsstatistik gleichzeitig |
| **Kalibrieren** | Vor allem Flats |

---

## 13. Fehlersuche

**„Only N FITS file(s) in that folder"** — eine Lichtkurve braucht eine Zeitreihe. Zeig auf die Subs, nicht auf ein Stack.

**„Siril found no stars in the reference frame"** — Fokus prüfen, und ob die Frames wirklich Himmel zeigen.

**„Only N usable comparison star(s) after filtering"** — das Log nennt jede Ablehnung mit Grund. SNR-Grenze senken oder ein weiteres Feld nutzen.

**„light_curve produced no light_curve.dat"** — Siril verwirft den ganzen Lauf, wenn ein Vergleichsstern in zu wenigen Frames messbar ist. Weniger Vergleiche oder höhere SNR-Grenze.

**Kein Transit gemeldet, obwohl erwartet** — Signifikanz im Reiter *Result* ansehen. Nahe der 4,5σ-Schwelle fehlt schlicht die Präzision; ist sie negativ, hat der Fit eine Aufhellung gefunden, meist ein vom Detrend nicht entfernter Trend.

---

## 14. FAQ

**Warum nicht einfach Sirils eigenes [Lichtkurven-Werkzeug](https://siril.readthedocs.io/de/stable/photometry/lightcurves.html)?** Sirils nativer Weg erzeugt eine Lichtkurve — dieses Skript erzeugt ein Messergebnis. Nativ lädst du die kalibrierte Sequenz, löst die Referenz, wählst Ziel und Vergleichssterne per Hand oder Katalogabfrage, und `light_curve` schreibt eine Drei-Spalten-Datei (JD, V−C, Fehler) für Plot oder Export; dort endet die Analyse. Dieses Skript unterscheidet sich auf drei Ebenen, jede gemessen statt vermutet. *Der Workflow:* ein Ordner rein, die ganze Kette läuft — Kalibrierung, Registrierung, Erkennung und Plate Solve macht weiterhin Siril. *Die Messung:* `light_curve` verschiebt seine Box per Registrierung, zentriert aber nie nach (kein Follow-Star), verweigert oberhalb von 160 px Gesamtdrift komplett und lässt das *ganze* Kommando scheitern, wenn ein Stern den Chip verlässt; dieses Skript zentriert jeden Stern pro Frame neu, wählt die Referenz um, verwirft nur den Stern, der hinauswandert, wählt die Apertur nach gemessenem Rauschen und prüft die Vergleichssterne gegeneinander — 140 von 142 Punkten, wo `light_curve` am selben Lauf 67 behielt. *Die Analyse:* BJD_TDB, ein randverdunkelter Fit simultan mit der Systematik, kalibrierte Fehlerbalken, ein zweiseitiger Signifikanztest mit gemessener Fehlalarmrate, O−C, beide Tiefen-Konventionen — nichts davon existiert im nativen Werkzeug. Und `light_curve` bleibt als angekündigter Fallback eingebaut.

**Verändert es meine Subs?** Nein. Alles wird unter `_lightcurve/` und `lightcurve/` geschrieben, die Quellframes werden nur gelesen.

**Auch für veränderliche Sterne?** Photometrie und Detrend gelten unverändert. Der *Fit* ist transitförmig, ein pulsierender Veränderlicher wird davon nicht gut beschrieben — aber die CSV liegt für deine eigene Auswertung bereit.

**Warum ist meine Signifikanz niedriger als bei anderen Werkzeugen?** Vermutlich wegen des zweiseitigen Baseline-Tests (§10). Er ist bewusst konservativ.

**Warum wird ein Transit am Rand des Laufs abgelehnt?** Weil sich ohne Baseline auf beiden Seiten eine Delle nicht von einem Trend unterscheiden lässt. Das ist eine Eigenschaft der Daten, nicht des Skripts.

**Soll ich das bei ExoClock einreichen?** Tiefe, T0 und Dauer liegen in der richtigen Form vor. Ziele auf 5σ oder besser und lies deren Einreichungshinweise — die Schwelle hier gilt fürs Behaupten einer Detektion, nicht fürs Publizieren.
