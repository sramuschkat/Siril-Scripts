# Svenesis ImageMono Train — Benutzeranleitung

**Version 1.7.11** | Siril Python-Skript für Mono-Filterrad-Stacking und Farbkomposition

> *Einen N.I.N.A.-Zielordner auswählen und mit fertigen Kanal-Mastern und einem kalibrierten Farbbild zurückkommen — Kalibrierung, Stacking, Kanalausrichtung, Palettenkomposition und Farbkalibrierung in einem Durchgang.*

---

## Inhaltsverzeichnis

1. [Was ist ImageMono Train?](#1-was-ist-imagemono-train)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Daten vorbereiten](#4-daten-vorbereiten)
5. [Erste Schritte — der erste Lauf](#5-erste-schritte--der-erste-lauf)
6. [Die Benutzeroberfläche](#6-die-benutzeroberfläche)
7. [Kalibrierung](#7-kalibrierung)
8. [Stacking-Optionen](#8-stacking-optionen)
9. [Paletten & Kanalzuordnung](#9-paletten--kanalzuordnung)
10. [Farbkalibrierung](#10-farbkalibrierung)
11. [Ausgabedateien](#11-ausgabedateien)
12. [Master wiederverwenden](#12-master-wiederverwenden)
13. [Empfohlene Arbeitsabläufe](#13-empfohlene-arbeitsabläufe)
14. [Fehlerbehebung](#14-fehlerbehebung)
15. [Tipps & Empfehlungen](#15-tipps--empfehlungen)
16. [Häufige Fragen](#16-häufige-fragen)
17. [Neu in 1.7.11](#17-neu-in-1711)

---

## 1. Was ist ImageMono Train?

**Svenesis ImageMono Train** nimmt eine Nacht (oder mehrere Nächte) monochromer Subs durch ein Filterrad und erzeugt daraus:

- ein **lineares Master pro Filter**, kalibriert und gestackt,
- alle Master **auf einem gemeinsamen Pixelraster ausgerichtet**, sodass die Kanäle exakt übereinanderliegen,
- ein **Farbkomposit** in der Palette deiner Wahl, hintergrundbereinigt und farbkalibriert,
- einen **Verarbeitungsbericht** (`output.md`), der beschreibt, was tatsächlich passiert ist, und
- eine **Nachbearbeitungsanleitung** (`todo.md`) für die verbleibenden kreativen Schritte.

Du tippst keinen einzigen Siril-Befehl. Du wählst einen Ordner und drückst einen Knopf.

Das Skript ist gezielt für eine **Monochrom-Kamera hinter einem Filterrad** gebaut. Frames werden nie debayert, und jede Entscheidung — welcher Rejection-Algorithmus, welche Gewichtung, welche Farbkalibrierung — fällt pro Filter, denn ein 30-Minuten-Ha-Kanal und ein 3-Minuten-Blau-Kanal sind nicht dasselbe Problem.

### Was es *nicht* tut

Es hört beim **linearen** Bild auf. Strecken, Sternreduktion, Sättigung und die finale Luminanz-Kombination sind gestalterische Entscheidungen, und `todo.md` führt dich mit konkreten Siril-Menüpfaden hindurch. Diese Grenze ist Absicht: Farbkalibrierung muss auf linearen Daten laufen, also übergibt das Skript genau dort, wo der Geschmack anfängt.

---

## 2. Hintergrundwissen für Einsteiger

### Warum Mono + Filterrad anders ist

Eine One-Shot-Color-Kamera (OSC) hat eine Bayer-Matrix fest auf dem Sensor: jedes Pixel ist dauerhaft rot, grün oder blau. Ein **Monochrom**-Sensor hat keine — jedes Pixel sammelt alles Licht, das es bekommt. Die Farbe kommt vom **Filterrad** davor: du nimmst einen Satz Frames durch Rot auf, dann durch Grün, dann durch Blau (oder Luminanz), und kombinierst sie hinterher.

Die Vorteile sind real — keine Interpolation, volle Auflösung pro Kanal, und die Freiheit, dreimal so lange auf den schwachen Kanal zu halten. Der Preis: du hast jetzt drei bis sechs getrennte Datensätze, die einzeln gestackt und dann **pixelgenau** zur Deckung gebracht werden müssen. Genau daran scheitern die meisten manuellen Arbeitsabläufe, und genau das automatisiert dieses Skript am sorgfältigsten.

### Breitband vs. Schmalband

| Typ | Filter | Was durchkommt | Typischer Einsatz |
|---|---|---|---|
| **Breitband** | L, R, G, B | Breite Ausschnitte des sichtbaren Spektrums | Galaxien, Sternhaufen, natürliche Farbe |
| **Schmalband** | Ha, OIII, SII | Wenige Nanometer um eine Emissionslinie | Nebel, lichtverschmutzter Himmel, Mondnächte |

Schmalband-Frames sind deutlich dunkler und enthalten weit weniger Sterne, weil ein 4,5-nm-Filter fast alles Kontinuumslicht blockiert. Diese eine Tatsache treibt mehrere Entscheidungen dieses Skripts — welche Frames sich registrieren lassen, welche Gewichtung passt, und welche Farbkalibrierung überhaupt sinnvoll ist.

### Kalibrierungsframes

Siril berechnet jedes kalibrierte Light so:

```
Lc = (L − D) / (F − O)
```

- **L** — dein Light-Frame
- **D** — Master-Dark: das Eigensignal des Sensors (thermisches Rauschen, Hotpixel) bei gleicher Belichtung, Gain und Temperatur
- **F** — Master-Flat: was deine Optik mit einem gleichmäßig ausgeleuchteten Feld macht (Vignettierung, Staubschatten)
- **O** — Offset/Bias: der elektronische Sockel, den die Kamera jedem Auslesevorgang hinzufügt

**Flats sind am wichtigsten.** Ohne sie überleben Vignettierung und Staubschatten bis ins Endbild — und, für dieses Skript besonders relevant, sie hinterlassen einen Helligkeitsgradienten, der die photometrische Farbkalibrierung messbar ungenauer macht. Wenn du nur eine Sorte Kalibrierungsframes aufnimmst, nimm Flats auf.

Beachte: Das Master-Dark enthält den Bias bereits. Beides abzuziehen würde ihn doppelt entfernen, deshalb wendet das Skript Bias auf die Lights **nur dann** an, wenn kein Dark verwendet wird.

### Linear vs. gestreckt

Direkt aus der Kamera und aus dem Stacker ist ein Astrofoto **linear**: die Pixelwerte sind proportional zum gesammelten Licht. Es sieht fast schwarz aus, weil das interessante Signal knapp über dem Hintergrund liegt.

**Strecken** komprimiert diesen riesigen Dynamikumfang auf etwas, das ein Bildschirm zeigen kann. Für Messzwecke ist es zugleich unumkehrbar — nach dem Strecken verhalten sich Sternhelligkeiten nicht mehr linear zum echten Fluss, und die photometrische Farbkalibrierung wird ungültig. Deshalb ist jedes Bild, das dieses Skript schreibt, linear, und deshalb passiert die Kalibrierung, bevor du ein Histogramm anfasst.

---

## 3. Voraussetzungen & Installation

### Anforderungen

- **Siril 1.4** oder neuer, mit Python-Skript-Unterstützung
- **sirilpy** (liegt Siril bei)
- **PyQt6, astropy, numpy** — werden beim ersten Start automatisch über `s.ensure_installed` installiert
- Für die Farbkalibrierung: eine Internetverbindung **oder** ein lokaler Gaia-Katalog. Ohne beides entsteht das Komposit trotzdem, nur eben unkalibriert.

### Installation

1. `Svenesis-ImageMono-Train.py` in deinen Siril-Skriptordner kopieren.
2. In Siril: **Skripte → Skripte aktualisieren** (oder Siril neu starten).
3. Über **Bildverarbeitung → Skripte → Svenesis ImageMono Train** starten. Es muss kein Bild geladen sein.

### Hinweis zu Cloud-Ordnern

Sirils `link`-Befehl legt **symbolische Links** auf deine Frames an. Cloud-Clients (Dropbox, OneDrive, iCloud Drive, Google Drive) schreiben synchronisierte Symlinks aktiv um — ein verlinkter Frame kann dadurch zwischen zwei Siril-Befehlen verschwinden, mitten im Lauf, ohne Warnung des Cloud-Clients.

**Wenn das Log meldet, dass Funktionen zurückgefallen sind.** Ein Teil dessen, was dieses Skript tut, braucht Aufrufe, die erst neuere Versionen von Sirils Python-Modul (`sirilpy`) mitbringen: gemessene Frame-Zahlen, das Komposit im Speicher, das Lesen von Sirils eigenem Log. Jeder davon ist abgesichert, ein fehlender Aufruf kostet also nichts — der Lauf nimmt den einfacheren Weg. Was er bisher kostete, war eine *Erklärung*, denn der Rückfall war stumm und dauerhaft.

Das Skript startet jetzt nicht mehr unterhalb von **sirilpy 1.0.0** (das mit Siril 1.4 ausgeliefert wird), und oberhalb dieser Schwelle prüft es jeden optionalen Aufruf einzeln — indem es fragt, ob es ihn gibt, nicht indem es Versionsnummern vergleicht. Was fehlt, wird einmal beim Start und noch einmal in `output.md` benannt, samt seiner Folge. Ein Siril-Update stellt sie wieder her.

**Plattenplatz während eines Laufs.** Jeder Schritt — Kalibrieren, Hintergrund, Registrieren — schreibt eine vollständige Kopie jedes Frames. Mit gesetztem **Delete _work/ when finished** wird jede Generation freigegeben, sobald die nächste fertig ist; der Spitzenbedarf bleibt damit bei etwa zwei statt vier Generationen — rund 3,6 GB pro Generation bei hundert 3008×3008-Subs in 32 bit. Ohne den Haken bleibt jede Zwischenstufe liegen, und genau das will man, wenn etwas untersucht werden muss. (Die Idee stammt aus **Storage Friendly Stacking** von Quark-Coder, das den Ordner überwacht; ein fester Schritt nach jedem Kommando leistet dasselbe ohne Dateiwächter.)

Halte den Arbeitsbaum auf einer **lokalen Platte**. Wenn deine Rohdaten in der Cloud liegen, kopiere den Zielordner vorher lokal, oder nimm den Ordner `output/_work/` von der Synchronisation aus.

---

## 4. Daten vorbereiten

### Was das Skript liest

Maßgeblich ist der **FITS-Header**, nicht der Ordnername:

| Schlüsselwort | Wofür |
|---|---|
| `FILTER` | Gruppierung der Frames zu Kanälen |
| `IMAGETYP` | Unterscheidung Lights / Darks / Flats / Dark-Flats / Bias |
| `OBJECT` | Erkennen, dass versehentlich ein Ordner mit mehreren Zielen gewählt wurde |
| `INSTRUME`, `EXPTIME`, `GAIN`, `CCD-TEMP`, `XBINNING`, `NAXIS1/2` | Zuordnung der Kalibrierungsmaster zu den Lights |

Manche Aufnahmesoftware schreibt **gar kein `IMAGETYP`**. Ein solcher Frame wird dann über seinen *Inhalt* gelesen: kein Filter, kein Objekt und die Montierung auf RA = DEC = 0 geparkt heißt geschlossener Verschluss → **Dark**; ein Filter *und* ein Objekt heißt, es wurde auf etwas gezielt → **Light**. Flat und Bias werden bewusst nie geraten — nichts in einem gewöhnlichen Header trennt sie zuverlässig, und ein Fehlgriff dort würde die Kalibrierung verderben statt sie nur zu überspringen.

Das N.I.N.A.-Ordnerschema `DATE\IMAGETYPE\TARGETNAME\FILTER\…` dient nur als **Rückfallebene**, wenn ein Schlüsselwort fehlt. Praktisch heißt das: das Skript kommt mit fast jedem Ordnerlayout zurecht — auch mit der klassischen N.I.N.A.-Anordnung, bei der `FLAT/` *neben* dem Zielordner liegt statt darin.

### Unterstützte Formate

- `.fit`, `.fits`, `.fts` — und ihre Rice-komprimierten `.fz`-Varianten, direkt lesbar
- **XISF wird nicht unterstützt.** Solche Dateien werden gezählt und gemeldet, nie stillschweigend übergangen: astropy kann XISF-Header nicht lesen, damit fehlten Belichtung, Gain und Temperatur, und die Kalibrierungszuordnung könnte gar nicht funktionieren.

### Mehrere Nächte

Derselbe Filter über mehrere Nächte verteilt wird automatisch **zu einem Stack zusammengefasst**. Zeige einfach auf einen Ordner, der alle enthält.

### Empfohlenes Ordnerlayout

```
M16/
├─ LIGHT/2026-07-25/{LUMINOS,RED,GREEN,BLUE,HA,OIII}/…
├─ LIGHT/2026-08-14/{…}/…          ← zweite Nacht, gleiches Ziel
└─ FLAT/2026-07-25/{…}/…           ← Session-Flats, pro Filter
```

Darks und Bias gehören in einen separaten **Library**-Ordner (siehe §7), weil sie monatelang wiederverwendbar sind.

---

## 5. Erste Schritte — der erste Lauf

1. **Skript starten.** Es muss kein Bild geladen sein.
2. **Select Target Folder…** — den Wurzelordner **eines** Ziels wählen.
3. Optional einen **Library…**-Ordner mit deinen wiederverwendbaren Darks und Bias setzen. Er wird zwischen Läufen gemerkt.
4. Die Ordnerauswahl analysiert sofort — **Re-scan Folder** ist für danach da, wenn Frames dazukommen oder die Library wechselt. Die Tabelle **Discovered Filters** listet jeden Filter mit Frameanzahl, **womit seine Lights kalibriert werden**, und der Gesamtbelichtung.

   Die Spalte **Calibration** beantwortet die Frage, für die die Tabelle da ist: *was passiert mit diesen Lights?* Sie liest `Dark + Flat ×3`, `Flat`, `Bias + Flat` oder `none` — die Master, die diesen Filter wirklich erreichen, in der Reihenfolge, in der `Lc = (L − D) / (F − O)` sie anwendet; `×3` heißt ein Master-Flat pro Nacht. Sie folgt jedem Schalter darunter: *Match flats to the same night* umlegen, und das `×3` erscheint oder verschwindet.

   Ein **`⚠` in Warnfarbe heißt: kein Dark passt zu diesen Lights.** Das ist die größte Qualitätslücke, die ein Lauf haben kann, und sie tauchte bisher erst auf, wenn der Lauf schon lief — eine Library mit 442 Darks liest sich beim Überfliegen als „Darks werden angewendet", auch wenn alle 442 drei Sekunden lang sind und die Lights 300 s. Der Tooltip nennt die Belichtungszeiten, die tatsächlich vorliegen, warum sie abgelehnt wurden, und was helfen würde. Belichtungszeit, Gain und Sensortemperatur wandern in eine Zeile unter die Tabelle, solange alle Filter sie teilen, und kehren als Spalte zurück, sobald sie sich unterscheiden.
5. **Palette** prüfen. *Auto* schlägt eine aus den gefundenen Filtern vor, und immer nur eine, deren drei Kanäle sich tatsächlich füllen lassen.
6. Unter **Auto-finish** die **SPCC**-Felder prüfen. Sie sind für ein bestimmtes Rig vorbelegt — trage deinen eigenen Sensor- und Filternamen ein (siehe §10).
7. **Stack All Filters** drücken und den **Log**-Tab beobachten.
8. Am Ende öffnet sich `output/`, das Farbbild ist in Siril geladen. Lies **`todo.md`** für den Rest.

Eine Nacht mit sechs Filtern und vierzig Frames dauert auf einem aktuellen Laptop rund 20 Sekunden.

---

## 6. Die Benutzeroberfläche

Das Fenster hat ein **linkes Panel** für Eingaben und Optionen und ein **rechtes Panel** mit zwei Tabs.

### Rechtes Panel

| Tab | Inhalt |
|---|---|
| **Overview** | Was die Analyse gefunden hat: Filter, Frameanzahlen, Belichtungszeiten, Kalibrierungsframes, Warnungen |
| **Log** | Alles, was der Lauf tut, in der Reihenfolge — inklusive der exakten Siril-Befehle |

Im Log erklärt das Skript seine Entscheidungen. Wenn es etwas überspringt, auf eine Rückfallebene ausweicht oder eine Konfiguration bemerkt, die gegen sich selbst arbeitet, steht es dort — und wiederholt im Bericht.

### Linkes Panel, von oben nach unten

1. **Zielordner** — *Select Target Folder…* und *Analyze Folder*
2. **Kalibrierung** — Library-Pfad und die Kalibrierungsschalter (§7)
3. **Stacking** — Rejection, Gewichtung, Qualitätsfilter, Beschnitt, Hintergrund (§8)
4. **Farbe** — Palette, Kanalzuordnung, Komposition und Auto-finish (§9, §10)
5. **Aktionen** — Ausrichtung, Plate-Solving, Wiederverwendung, Aufräumen und **Stack All Filters**

### Vorlagen (Presets)

Drei Vorlagen setzen den gesamten Optionsblock auf einmal:

| Vorlage | Zweck |
|---|---|
| **Quick look** | „Sehen die Daten gut aus?" — keine QA-Extras, keine Farbkalibrierung, alle Frames behalten, gestreckte Vorschau |
| **Balanced** | Der sinnvolle Standard für eine normale Nacht: Blank-Erkennung, Gewichtung, Hintergrundextraktion pro Kanal, volles Auto-finish |
| **Final** | Alles an: Qualitätsfilter (gewichtete FWHM + Rundheit), Rejection-Maps, plate-solvte Master |

Eigene vollständige Konfigurationen lassen sich außerdem als `.json` speichern und laden.

---

## 7. Kalibrierung

Alles hier ist **optional und additiv**. Das Skript nutzt, was es findet, und überspringt den Rest; ganz ohne Kalibrierungsframes verhält es sich exakt wie vor der Kalibrierungs-Unterstützung.

### Woher die Frames kommen

- **Flats** werden neben deinen Lights erwartet, pro Filter, pro Session. Beide Layouts funktionieren: im Zielordner oder daneben in einem Geschwister-Verzeichnis `FLAT/`.
- **Darks und Bias** kommen aus dem **Library**-Ordner — einmal gesetzt und monatelang genutzt. Er darf Rohframes enthalten (die werden zu Mastern gestackt) oder fertige Master; eine Gruppe mit genau einer Datei wird als fertiger Master übernommen.

Eine Library soll wachsen, deshalb werden **nur die Darks gestackt, die dieser Lauf auch verwenden kann** — beurteilt nach derselben Regel, die später eines auswählt. Fünf Belichtungszeiten bei drei Setpoints sind fünfzehn Master; vierzehn davon zu bauen, um eines zu öffnen, kostet Minuten und liest hunderte Frames für nichts.

Nur Kalibrierung wird von außerhalb des Zielordners geholt. Ein *Light*-Frame, das in der Library oder einem Nachbarordner liegt, wird gezählt und gemeldet, aber nie in dein Ziel gestackt.

### Wie Master zugeordnet werden

Die Zuordnung läuft über **FITS-Header, nicht über Dateinamen**:

| Eigenschaft | Toleranz |
|---|---|
| Kamera (`INSTRUME`) | exakt, sofern beide Header sie nennen |
| Belichtungszeit | innerhalb 5 % — das nächstgelegene gewinnt |
| Gain | exakt |
| Binning | exakt |
| Bildmaße | exakt |
| Sensortemperatur | ±2 °C |

Die **Kamera** gehört zum Schlüssel, weil Bildgröße und Binning nur ein Indiz sind: zwei Bodies mit demselben Sensorformat würden sich sonst gegenseitig kalibrieren. Ein fehlender Header-Wert blockiert eine Zuordnung nie — außer der Belichtungszeit: ein unlesbares `EXPTIME` liest sich als 0 s, und 0 gegen 120 ist genau die Fehlpaarung, die nicht durchrutschen darf.

**Die Belichtungszeit ist eine Toleranz, keine Identität.** Das thermische Signal skaliert mit der Belichtung, ein 290-s-Dark entfernt also nahezu das, was ein 300-s-Dark entfernen würde — es abzulehnen ließe die Lights unkalibriert, und das ist das schlechtere Ergebnis. Das nächstgelegene Dark innerhalb des Bandes wird verwendet und **im Log benannt**, mit der Bestätigung, dass alles andere übereinstimmt. Darüber hinaus läuft der Lauf ohne Dark weiter und sagt das auch: ein 60-s-Dark auf 300-s-Lights liegt 80 % daneben und wird nie angewendet.

**Ein Filter mit gemischten Belichtungszeiten — oder Nächten — wird in Teilen kalibriert.** Zwei Master binden jeweils nur einen Teil der Frames, und jeder steuert eine Dimension bei. Ein Dark entfernt nur das thermische Signal, das während *seiner eigenen* Belichtung entstanden ist — ein einzelnes Dark auf 120-s- und 300-s-Subs ist also für keine der beiden richtig. Ein Flat beschreibt nur den Strahlengang, durch den es aufgenommen wurde — ist *Match flats to the same night* an, will also jede Nacht ihr eigenes.

Beide sind unabhängig voneinander, die Teile sind daher ihr Kreuzprodukt, und eine Dimension mit nur einem Wert fällt heraus: ohne Darks wird nie nach Belichtung geteilt, mit nur einem Master-Flat nie nach Nacht. Jeder Teil wird separat bereitgestellt, mit seinen eigenen Mastern kalibriert, und die kalibrierten Teile werden vor der Registrierung wieder zusammengeführt (`merge`) — der Kanal endet damit weiterhin als **ein** Master, und genau das braucht das Farbkomposit. Der Report nennt jeden Kanal, bei dem das passiert ist, und welche Dimension ihn geteilt hat.

**Über Nächte gepoolte Flats werden gegeneinander geprüft.** Kein Header sagt, ob der optische Aufbau zwischen zwei Sessions verändert wurde — die Division der Flats einer Nacht durch die einer anderen sagt es: ein passendes Paar ergibt ein gleichförmiges Bild, ein unpassendes zeigt die Vignettierung oder den Staub, der sich verschoben hat. Jede Nacht wird zuerst durch ihren eigenen Median geteilt, ein helleres Panel oder eine abklingende Dämmerung zählt also nicht als Abweichung; übrig bleibt die Form.

Vor der Messung passieren zwei Dinge, ohne die die Schwellen unten bedeutungslos sind. Alle Frames einer Nacht werden **gemittelt** und vertreten so das Master-Flat, das es an dieser Stelle des Laufs noch nicht gibt; und die Karte wird auf etwa 250 px an der langen Seite **geblockt**. Vignettierung und Staub sind Hunderte Pixel groß und überstehen beides unverändert — Photonenrauschen, das an einem einzelnen 24 000-ADU-Sub 1,8 % erreicht und damit das Sechsfache der Grenze unten, nicht.

| Streuung des Verhältnisses | Bedeutung |
|---|---|
| unter 0,15 % | die Nächte passen zusammen — Poolen ist richtig |
| 0,15 % – 0,30 % | brauchbar, wird im Report vermerkt |
| über 0,30 % | am Aufbau wurde vermutlich etwas verändert; der Report nennt die Nächte und verweist auf *Match flats to the same night* |

Die Prüfung misst außerdem ihren eigenen **Rauschboden**: Die Referenznacht wird halbiert und mit sich selbst verglichen, und da zwei Hälften derselben Nacht sich um nichts als Rauschen unterscheiden, ist das Ergebnis die Fehlergrenze der Zahl darüber. Ein Unterschied, der den Boden nicht überschreitet, wird als „kein Formunterschied nachweisbar" gemeldet statt als Zahl. Jede Hälfte mittelt weniger Frames als die Karten im echten Vergleich, deshalb wird die rohe Hälften-Streuung zuerst auf die tatsächlichen Frame-Zahlen skaliert — unskaliert überschätzte sie das wahre Vergleichsrauschen um gemessene √2 bei gleichen Zahlen, und „nicht nachweisbar" deckte dann echte Unterschiede bis zur Größe des Rauschens selbst.

Die Prüfung schweigt, wenn es nur eine Nacht gibt oder wenn die Frames nicht lesbar sind. Ist *Match flats to the same night* an, läuft sie weiter und wird weiter berichtet — die Zahl zeigt ja, dass die Aufteilung ihren zusätzlichen Stack wert ist — aber sie ist keine Warnung mehr, und sie rät nie dazu, etwas einzuschalten, das schon an ist. Verfahren und Schwellen stammen aus dem **Flat On Flat Analyzer** von Carlo Mollicone im offiziellen Siril-Skript-Repository, samt Mittelung und Blockung.

**Ein Master-Flat pro Nacht.** Ist *Match flats to the same night* an, bekommt jede Nacht, die Flats **und** Lights eines Filters hat, ihr eigenes Master-Flat, und nur die Lights dieser Nacht werden dadurch geteilt. Die kalibrierten Nächte werden vor der Registrierung wieder zusammengeführt (`merge`), der Filter endet also weiterhin als **ein** Master — die Aufteilung ist eine Sache der Kalibrierung, nicht des Stackens.

Zwei Bedingungen müssen für eine eigene Nacht erfüllt sein: Flats **und** Lights dieses Filters. Flats aus einer Nacht, in der der Filter nie belichtet hat, ergäben ein Master, das niemand öffnet; eine Nacht mit Lights, aber ohne Flats, fällt auf ein gepooltes Master zurück — Log und Report nennen sie, statt sie stillschweigend zu schlucken. Weniger als zwei geeignete Nächte heißt: es gibt nichts zu trennen, und das gewohnte gepoolte Master wird verwendet.

Das gepoolte Master wird auch dann gebaut, wenn jede Nacht ihr eigenes hat. Es ist die Rückfallebene für zwei Wege, die an einer Stelle erreicht werden, an der ein Stack nicht mehr gefahrlos möglich ist — eine Light-Nacht ohne eigene Flats, und eine Teilkalibrierung, die scheitert und auf einen einzelnen Durchgang zurückfällt.

**Die Aufteilung tauscht Flat-Rauschen gegen Flat-Genauigkeit.** Ein gepooltes Master mittelt die Frames aller Nächte, ein Nacht-Master nur die dieser einen. Unter zehn Flats pro Nacht sagt das Log es, denn dort beginnt der Tausch ins Gewicht zu fallen — lohnend, wenn am Strahlengang wirklich etwas verändert wurde, verschenkt, wenn nicht. Wer mit einem Panel jede Nacht Flats aufnimmt, behält mit zehn bis zwanzig pro Filter und Nacht beide Eigenschaften.

**Darks werden zusätzlich nach Temperatur gruppiert**, damit ein −10-°C- und ein −20-°C-Satz niemals zu einem Master gemittelt werden, das für keines von beiden stimmt. Bias wird nicht so aufgeteilt — er ist temperaturunabhängig.

### Die Optionen

| Option | Wirkung |
|---|---|
| **Apply calibration when frames exist** | Hauptschalter. Aus = rohe Lights stacken, wie früher. |
| **Cosmetic correction (hot pixels)** | `-cc=dark` — entfernt Hot- und Coldpixel anhand der Statistik des Darks. Setzt ein Dark voraus. |
| **Match flats to the same night** | Baut **pro Nacht** ein eigenes Master-Flat und teilt die Lights jeder Nacht durch ihr eigenes; die kalibrierten Nächte werden vor der Registrierung wieder zusammengeführt. Einschalten, wenn zwischen den Sessions am Strahlengang etwas verändert wurde; auslassen, um Flats für ein rauschärmeres Master zu poolen. |

### Die Offset-Kette der Flats

Flats müssen ihren eigenen Offset loswerden, bevor sie irgendetwas normieren können. Das Skript weicht in vier Stufen aus und bricht nie ab:

1. ein echtes **Dark-Flat** oder **Bias**-Master, wenn eines passt,
2. ein gewöhnliches **DARK mit der Belichtungszeit der Flats** (innerhalb 20 %) — ein Dark mit der Flat-Belichtung *ist* ein Dark-Flat, ganz gleich, was `IMAGETYP` behauptet, und Flat-Belichtungen sind kurz genug, dass der Unterschied vernachlässigbar bleibt,
3. Sirils **synthetischer Bias** `=64*$OFFSET`,
4. gar keine Offset-Korrektur — das Flat wird direkt gestackt.

Master werden in `calib/` unter lesbaren, aus dem Header abgeleiteten Namen wie `M101_RED_-10C_3s_G100_flat` zwischengespeichert und von späteren Läufen wiederverwendet.

---

## 8. Stacking-Optionen

### Rejection — pro Filter, aus der Frameanzahl gewählt

Ausreißer-Rejection entfernt Satelliten, kosmische Strahlung und Flugzeuge. Welcher Algorithmus funktioniert, hängt vollständig davon ab, wie viele Frames zur Verfügung stehen — deshalb wählt das Skript pro Kanal:

| Frames | Algorithmus | Warum |
|---|---|---|
| ≤ 4 | **Percentile Clipping** 0.2 / 0.1 | Sigma-Verfahren brauchen eine Population; bei drei Frames sagt eine Standardabweichung nichts |
| 5 – 10 | **Sigma Clipping** 3 / 3 | Das Einfachste, das greift, sobald es mehr als eine Handvoll sind |
| 11 – 30 | **Winsorized Sigma** 3 / 3 | Robust, das Arbeitspferd für eine normale Nacht |
| 31 – 300 | **GESDT** 0.3 / 0.05 | Generalized Extreme Studentized Deviate Test |
| > 300 | **Linear Fit** 5 / 4 | Modelliert einen Trend *über* den Stack — dafür muss er lang sein |

Diese Bandgrenzen stammen von **Cyril Richard**, aus [AMSP](https://gitlab.com/free-astro/siril-scripts/-/blob/main/preprocessing/AMSP.py) im offiziellen Siril-Skript-Repository. Er hat Siril geschrieben und diese Algorithmen implementiert, seine Schwellen wiegen also schwerer als unsere eigene Herleitung.

Die beiden GESDT-Zahlen sind **keine** Sigmas — es sind der maximal verworfene Anteil und ein Signifikanzniveau. Ein Siril-Build, das den Parameter nicht kennt, fällt auf Linear Fit zurück, und der Bericht nennt den Algorithmus, der *wirklich* gelaufen ist — eine Rückfallebene kann sich also nicht hinter der bevorzugten verstecken.

Die Stufe wird für die Frames gewählt, die **tatsächlich integriert** werden, nicht für die gefundenen. Ein Sub ohne genügend erkennbare Sterne lässt sich nicht registrieren und wird von Siril ausgeschlossen; das Skript zählt, was Siril wirklich exportiert hat. In einer realen Nacht gingen 3 von 6 OIII-Frames durch Wolken verloren — die verbliebenen 3 bekamen Percentile Clipping, während die naive Zählung Sigma Clipping auf drei Frames angewendet und damit gar nichts verworfen hätte.

**Die Master-Flats, -Darks und -Bias laufen durch dieselbe Tabelle.** Sie wurden bisher mit einem nackten `rej 3 3` gestapelt — und ein nacktes `rej` wählt Sirils Vorgabe, also winsorized: die Stufe für 11–30 Frames, angewendet auf ein Nacht-Master-Flat aus fünf Frames ebenso wie auf ein Bibliotheks-Dark aus vierhundert. Beim M-16-Lauf heißt das jetzt Sigma Clipping für die Fünf- und Zehn-Frame-Flats und Linear Fit für den 442-Frame-Darkflat-Satz — beides bekamen sie vorher nicht.

Für Kalibriermaster bleibt die Rejection **an**, auch wenn der Schalter für die Light-Stacks aus ist. Der Schalter betrifft das Integrieren deiner eigenen Frames; ein kosmischer Treffer, der in einem Master-Flat stehenbleibt, erreicht jedes Light, das durch dieses Master geteilt wird.

**Die Zahl ist gemessen, nicht geschätzt.** Nach der Registrierung fragt das Skript Siril nach der erzeugten Sequenz — `get_seq()` liefert zurück, welche Frames noch enthalten sind, und für jeden davon FWHM, Rundheit und Sternzahl, wie Siril sie gemessen hat. Diese Werte stehen im Report als Messungen, in einer eigenen Tabelle.

Das reicht über den Report hinaus: die Qualitätsfilter laufen zum *Registrierungs*zeitpunkt, die exportierte Anzahl hat sie also bereits berücksichtigt. Ihren Anteil ein zweites Mal abzuziehen — wie es das Skript bisher tat, sowohl für den Report als auch für die Rejection-Stufe — wählte den Algorithmus für eine kleinere Population als die tatsächlich integrierte. Ein Kanal mit 34 exportierten Frames wurde als 30 behandelt, und das ist eine andere Stufe. Eine Schätzung springt jetzt nur noch ein, wenn die Sequenz gar nicht lesbar ist, und der Report kennzeichnet sie mit `≈`.

Was Siril zurückgibt, landet zusätzlich als eigene Tabelle in `output.md`:

| Filter | Integriert | Mediane FWHM | Rundheit | Sterne |
|---|---:|---:|---:|---:|
| HA | 29 von 31 | 3,14 px | 0,88 | 412 |
| OIII | 12 von 12 | 3,90 px | — | — |

Die Rundheit ist 1,00 bei perfekt runden Sternen; deutlich darunter heißt Trailing. Die Sternzahl ist Sirils eigene Detektion auf der Referenzebene — ein Kanal weit unter den anderen bedeutet meist einfach, dass der Filter weniger Licht durchlässt, nicht dass etwas schiefging. Ein Wert, den Siril **nicht** aufgezeichnet hat, erscheint als `—`, nie als `0,00`: eine Null dort läse sich als katastrophales Trailing oder als leeres Feld, während die Wahrheit schlicht „nicht gemessen" ist.

Das Verfahren stammt aus **RegistrationInspector** von Cecile Melis und dem **Sequence Statistics Analyzer** von Carlo Mollicone.

### Frame-Gewichtung

| Methode | Am besten für |
|---|---|
| **Weighted FWHM** (Standard) | Breitband — Schärfe skaliert mit der Sternzahl |
| **Noise** | **Schmalband** — ein sternarmes Feld würde sonst für den Filter bestraft, nicht für den Frame |
| **Number of stars** | Nächte mit stark schwankender Transparenz |

### Qualitätsfilter

Vier Filter — **Weighted FWHM**, **Roundness**, **Star count**, **Background level** — in zwei Modi:

- **% best** (1–100): den entsprechenden Anteil der besten Frames behalten. `90` verwirft das schlechteste Zehntel.
- **k-sigma** (1–10): Frames verwerfen, die weiter als *k* Standardabweichungen vom Mittel entfernt sind.

Die Wertefelder folgen dem Modus, damit ein Prozentwert nie stillschweigend als Sigma-Vielfaches umgedeutet wird.

Sie greifen zum **Registrierungszeitpunkt**, damit verworfene Frames gar nicht erst neu projiziert werden — und erst ab **20 Frames** pro Filter. Darunter kostet der Verlust eines Subs mehr Signal-Rausch-Abstand, als der schlechteste Frame an Schärfe kostet. Das Log warnt, wenn die Filter mehr als 15 % eines Satzes verwerfen, samt daraus folgendem Rauschanstieg.

### Beschnitt, Hintergrund und der Rest

| Option | Hinweise |
|---|---|
| **Crop stacking edges (min framing)** | Behält nur die Fläche, die jeder Sub abdeckt. Dithering kostet einen schmalen Streifen (realer Lauf: 3008 px → 2991 px). Das ist eine Rahmenwahl innerhalb von `seqapplyreg`, kein nachträglicher Beschnitt. |
| **Background extraction per channel** | Entfernt den Himmelsgradienten aus jedem fertigen Master, solange es linear ist. Gradienten unterscheiden sich je Filter, deshalb wirkt das pro Kanal besser als einmal auf dem Farbbild. Optional mit **RBF**-Modell, das einem Gradienten folgt, der über das Feld die Richtung wechselt — ein Polynom vom Grad 1 kann ihn nur in eine Richtung kippen. |
| **Background extraction per sub-frame** | Langsamer; der Sub-Durchgang bleibt polynomiell, gemäß Sirils Empfehlung. |
| **Skip blank / black frames** | Verwirft komplett schwarze, flache oder defekte Frames, bevor sie die Registrierung sprengen. |
| **Save rejection map (QA)** | Schreibt pro Kanal nach `qa/`, was verworfen wurde. |
| **Drizzle** | Braucht **geditherte** Subs, und genügend davon. Unter etwa 40 Frames warnen Log und Bericht, dass es eher Rauschen als Auflösung hinzufügt. |
| **Register via plate solving** | Optional mit Distortion-Master; fällt automatisch auf Sternausrichtung zurück. |
| **Output normalization** | Skaliert den fertigen Master nach `[0, 1]`. Siehe unten — sie tut mehr, als der Name vermuten lässt. |

### Output-Normalisierung ist affin, und pro Kanal

Bei 32-Bit-Ausgabe setzt Siril sie so um:

```c
fit->fdata[i] = (fit->fdata[i] - mini) / (maxi - mini);   /* median_and_mean.c */
```

`mini` und `maxi` sind das dunkelste und das hellste Pixel **dieses** Masters. Daraus folgen zwei Dinge, die der Optionsname nicht verrät:

- Sie **zieht auch einen Offset ab**, ist also eine affine Abbildung, keine Verstärkung.
- Die beiden Zahlen stammen aus **einzelnen Extrempixeln**, und jeder Filter bekommt sein eigenes Paar. Die Kanäle verlassen den Stack damit auf drei zusammenhanglosen Skalen.

Für ein Bild ist das harmlos — gestreckt wird ohnehin, und SPCC passt je Kanal einen Faktor an und schluckt es. Es zählt, wenn die **absoluten Pegel** zählen: Photometrie, oder der Vergleich des Ha/OIII-Verhältnisses zwischen Läufen. Dann abschalten — und wissen, dass *Normalize narrowband channels* nicht das Einzige ist, was zwischen dir und dem physikalischen Linienverhältnis steht.

### Wenn die Registrierung nicht alles kann

`register -2pass` und `seqapplyreg` scheitern aus unabhängigen Gründen, deshalb werden sie getrennt behandelt — nur das erste sagt überhaupt etwas über Two-Pass-Unterstützung aus.

Scheitert die Two-Pass-Registrierung, weicht der Lauf auf einfaches `register` aus, das weder `-framing=` noch irgendeine `-filter-`-Option kennt. Beschnitt und Qualitätsfilter können auf diesem Kanal also nicht eingehalten werden. Was aufgegeben wurde, wird **pro Kanal festgehalten und im Bericht benannt**, nie stillschweigend fallengelassen.

---

## 9. Paletten & Kanalzuordnung

### Zuerst: was die vier Dropdowns sind

Das Panel zeigt **L / R / G / B** — das ist die *Kanalzuordnung*: welches gestackte Master in welchem Farbkanal landet. Es ist **keine** Liste „Filter, die diese Palette verwendet". Zwei Dinge liest man deshalb leicht falsch:

- **Nicht jede Palette füllt alle vier.** RGB, SHO und HOO lassen **L** leer, weil sie keinen Luminanzkanal haben. Ein aufgenommener Luminanz-Filter wird dann schlicht nicht gelesen.
- **Ein Filter kann verwendet werden, ohne zugeordnet zu sein.** Genau hier beißt HaRGB: Ha wird ins Rot *eingemischt* statt einem Kanal zugewiesen — und hat deshalb überhaupt kein Dropdown (siehe unten).

Alles, was die Dropdowns *zeigen*, lässt sich von Hand überschreiben.

---

### LRGB — die Standard-Breitbandpalette

| | |
|---|---|
| **Zuordnung** | R = Rot · G = Grün · B = Blau · **L = Luminanz** |
| **Braucht** | Rot, Grün, Blau. Luminanz optional — aber sie ist der Sinn von LRGB |
| **Ausgabedatei** | `TARGET_RGB.fit` — plus das getrennt gehaltene L-Master |

Die Luminanz ist bewusst **nicht** Teil des Komposits. Sirils empfohlene Reihenfolge lautet: nur R/G/B komponieren, dieses lineare RGB farbkalibrieren, strecken, L separat strecken und beides **zuletzt** kombinieren. Deshalb heißt die Datei `_RGB`, obwohl du LRGB gewählt hast — der Name gibt wieder, was tatsächlich drinsteckt. `todo.md` hat dann einen Teil B (Luminanz) und einen Teil C (Kombination).

Schalte **Quick linear LRGB** ein, um L stattdessen schon bei der Komposition einzubacken. Die Datei heißt dann `_LRGB`, und §10 erklärt, was dich das an Farbgenauigkeit kostet.

---

### RGB — Breitband ohne Luminanz

| | |
|---|---|
| **Zuordnung** | R = Rot · G = Grün · B = Blau (**L bleibt leer**) |
| **Braucht** | Rot, Grün, Blau |
| **Ausgabedatei** | `TARGET_RGB.fit` |

Identisch mit LRGB, nur ohne die Luminanz-Behandlung. Hast du einen Luminanz-Filter und wählst RGB, wird dieser Filter gar nicht gelesen — und mit *Stack only the filters this palette uses* nicht einmal gestackt. Nimm diese Palette, wenn du kein L hast oder das RGB für sich willst.

---

### SHO — die Hubble-Palette

| | |
|---|---|
| **Zuordnung** | **R = SII** · **G = Ha** · **B = OIII** (L bleibt leer) |
| **Braucht** | alle drei Schmalbandfilter |
| **Ausgabedatei** | `TARGET_SHO.fit` |

Alle drei Kanäle sind normal zugeordnet — in dieser Hinsicht ist SHO die geradlinigste Palette. Es ist zugleich die, die am häufigsten ohne die passenden Daten gewählt wird: **ohne SII-Filter hat der Rot-Kanal keine Quelle**, und das Skript sagt das im Moment der Auswahl, nicht erst nach einem vollen Lauf.

Ha ist bei den meisten Objekten weit stärker als SII und OIII, die rohe Kombination wird also grün. Zwei Mechanismen fangen das ab, und §10 erklärt, warum du immer nur einen davon nutzen solltest: **Normalize narrowband channels** oder SPCC im Narrowband-Modus.

---

### HOO — zwei Filter, drei Kanäle

| | |
|---|---|
| **Zuordnung** | **R = Ha** · **G = OIII** · **B = OIII** (L bleibt leer) |
| **Braucht** | Ha und OIII — mehr nicht |
| **Ausgabedatei** | `TARGET_HOO.fit` |

Beachte, dass **OIII zweimal vorkommt**: es speist Grün und Blau. Deshalb genügen zwei Filter, und deshalb liest der Kompositionsschritt dasselbe Master dreimal.

Eine Folge davon sollte man kennen, weil sie im Log alarmierend aussieht — SPCC meldet den Blau/Grün-Fit als:

```
Image B/G = 1.000000 + 0.000000 * Catalog B/G (sigma: 0.000000)
```

Das ist kein Fehlschlag. Blau und Grün *sind* dasselbe Bild, ihr Verhältnis ist also überall exakt 1, und es gibt nichts zu fitten. Aussagekräftig ist bei einem HOO-Komposit allein die **R/G**-Zeile.

---

### HaRGB — Breitband mit Ha-Beimischung

| | |
|---|---|
| **Zuordnung** | R = Rot · G = Grün · B = Blau · L = Luminanz |
| **Zusätzlich** | das **Ha-Master wird ins Rot eingemischt**, mit der Stärke **Ha → Rot** |
| **Braucht** | Rot, Grün, Blau — *und* einen Ha-Filter, der nicht zugeordnet wird |
| **Ausgabedatei** | `TARGET_HaRGB.fit` (oder `TARGET_RGB.fit`, wenn kein Ha gefunden wurde) |

**Das ist die Palette, bei der die Dropdowns in die Irre führen.** HaRGB behält die gewöhnliche Breitbandzuordnung — R, G, B, L genau wie bei LRGB — und mischt Ha *obendrauf* ins Rot:

```
R' = 1 − (1 − R) · (1 − k · Ha)        k = „Ha → Rot" / 100
```

Eine gewichtete Summe: Rot gewinnt Ha hinzu, ohne je über 1 hinauszugehen und ohne aufzuhören, linear zu sein. Weil Ha keinen Kanal *ersetzt*, hat es kein eigenes Dropdown — das Skript findet es automatisch über die Filterrolle unter den ausgerichteten Mastern, und das Log nennt das gewählte:

```
HaRGB will blend HA into Red — Ha is an admixture, not a mapped channel.
HaRGB: blending HA into Red at 50% (PixelMath).
```

Trägt keiner deiner Filter eine Ha-Rolle, sagt die Auswahl von HaRGB das jetzt sofort; ohne diese Prüfung liefe der Durchgang komplett durch und erzeugte stillschweigend ein einfaches RGB.

Zwei weitere Besonderheiten:

- **Für HaRGB entfällt die Farbkalibrierung.** Mit Ha im Rot-Kanal beschreibt die Sternphotometrie diesen Kanal nicht mehr, jede photometrische Kalibrierung würde also das Falsche messen. Das gespeicherte Komposit wird als *unkalibriert* gekennzeichnet — gleiche es von Hand ab.
- **Die Luminanz bleibt trotzdem getrennt**, genau wie bei LRGB, und wird nach dem Strecken kombiniert.

**Wie viel Ha tatsächlich hineingeht.** Die Beimischung lautet `(R + k·Ha) / (1+k)` — eine gewichtete Summe. Bei 0 % ist der Kanal reines R, bei 100 % R und Ha zu gleichen Teilen. Sie überschreitet nie 1, verwirft R nie, und — darum geht es — sie ist **linear**, und genau so wird jedes Komposit dieses Skripts übergeben.

Bis 1.7.9 war es ein Screen-Blend, `1-(1-R)·(1-k·Ha)`. Ausmultipliziert `R + k·Ha − k·R·Ha`, und der Kreuzterm ist quadratisch im Fluss. Am schwachen Ende ist er unsichtbar, deshalb stand er so lange:

| R | Ha | Screen-Blend | gewichtete Summe `(R+k·Ha)/(1+k)`, k=1 |
|---|---|---|---|
| 0,002 | 0,003 | 0,003497 | 0,002500 |
| 0,02 | 0,03 | 0,034700 | 0,025000 |
| 0,8 | 0,8 | 0,960000 | 0,800000 |

Am schwachen Ende stimmen Screen-Blend und einfache Summe auf besser als 0,1 % überein. Am hellen Ende nicht: bei R = 0,8 und k·Ha = 0,4 liefert die Screen-Form 0,88 statt 1,2 — 27 % Kompression genau der Sterne und Nebelkerne, die du danach streckst. Derselbe Einwand, der `rmgreen` in 1.7.4 aus dem Finish geworfen hat, gilt hier, also wurde die Beimischung in 1.7.10 zur gewichteten Summe.

Wer die Lichterkompression eines Screen-Blends will, wiederholt die Beimischung **nach** dem Strecken, wo sie hingehört.

---

### Die übrigen Schmalband-Zuordnungen

SHO und HOO kennt jeder. Der Rest ist dieselbe Idee mit den Linien an anderen Plätzen — durchweg **reine Zuordnungen**, bei denen ein Kanal kopiert und nicht berechnet wird:

| Palette | Rot | Grün | Blau |
|---|---|---|---|
| SHO | SII | Ha | OIII |
| HOO | Ha | OIII | OIII |
| HSO | Ha | SII | OIII |
| HOS | Ha | OIII | SII |
| OSS | OIII | SII | SII |
| OHH | OIII | Ha | Ha |
| OSH | OIII | SII | Ha |
| OHS | OIII | Ha | SII |
| SOH | SII | OIII | Ha |
| HSS | Ha | SII | SII |
| HHO | Ha | Ha | OIII |
| OOS | OIII | OIII | SII |
| SHH | SII | Ha | Ha |
| SOO | SII | OIII | OIII |

Das sind alle **sechs** Arten, drei verschiedene Linien auf drei Kanäle zu verteilen, dazu acht Zweilinien-Varianten. Jede bekommt dieselbe Behandlung wie SHO: Schmalband-Normalisierung, wenn eingeschaltet, und SPCC im Narrowband-Modus mit den Wellenlängen der Linien, die *diese* Palette in den jeweiligen Kanal gelegt hat — dieselbe Tabelle steuert beides, eine Palette kann also nicht mit falschen Wellenlängen bei SPCC ankommen.

Der Satz über SHO/HOO hinaus stammt aus **Cyril Richards PalettePicker** im offiziellen Siril-Skript-Repository und wurde gegen dessen Quelle geprüft, Franklin Mareks **Perfect Palette Picker** in der Seti Astro Suite Pro. Dieser Vergleich hat `SOH`, `HHO`, `OOS`, `SHH` und `SOO` ergänzt: `SOH` war die eine Permutation, die in unserer eigenen Tabelle fehlte, ohne dass etwas dahinterstand.

---

### Realistic1 / Realistic2 — gewichtete Mischungen

Diese *mischen* die Linien, statt sie zuzuordnen:

| Palette | Rot | Grün | Blau |
|---|---|---|---|
| Realistic1 | 50 % Ha + 50 % SII | 30 % Ha + 70 % OIII | 90 % OIII + 10 % Ha |
| Realistic2 | 70 % Ha + 30 % SII | 30 % SII + 70 % OIII | 100 % OIII |

Gemischt wird mit Sirils `pm`, und die **Farbkalibrierung entfällt**: ein Kanal aus 70 % Ha und 30 % SII hat kein einzelnes Durchlassband, das SPCC modellieren könnte — derselbe Grund, aus dem HaRGB ausgeschlossen ist.

---

### Warum die Palettenliste hier endet

Jede Palette oben ist entweder eine Zuordnung oder eine gewichtete Summe. Das ist kein Zufall, sondern das, was eine **lineare** Pipeline ehrlich anbieten kann:

- **Zuordnungen** verschieben ganze Kanäle. Linear oder gestreckt — das Ergebnis ist dasselbe.
- **Gewichtete Summen** sind Linearkombinationen, vertauschen also ebenfalls mit dem Stretch.
- **Dynamische Paletten** — Foraxx und Verwandte — mischen mit einem Faktor wie `t^(1-t)`, wobei `t = Ha·OIII`. Auf gestreckten Daten läuft `t` über [0,1] und der Faktor leistet etwas. Auf linearen Daten liegt `t` bei etwa 1e-6, `t^(1-t)` fällt gegen null, und die Palette degeneriert zu „alles OIII". Sie fehlen hier **bewusst**.

  Der Perfect Palette Picker entscheidet das von seiner Seite aus genauso. Sein Gate lautet `np.clip(x, 1e-6, 1.0) ** (1.0 - x)` — und sein Haken **Linear Input Data** bringt diesem Gate nicht bei, lineare Daten zu lesen. Er **streckt vorher**, `stretch_mono_image(img, target_median=0.25)`, und baut die Palette aus der gestreckten Kopie. Median 0,25 ist genau dort, wo das Gate Steigung hat: `0,25^0,75 = 0,35`, `0,5^0,5 = 0,71`. Bei linearen 0,01 liefert es 0,0105 — das ist `t ≈ x` und damit dasselbe wie gar kein Gate. Der Haken existiert, weil die Palette ohne das Strecken nicht funktioniert.

Cyril Richards PalettePicker zieht dieselbe Grenze von der anderen Seite: er hat die Fähigkeit, *lineare* Bilder zusammenzusetzen, bewusst aufgegeben, weil das einen automatischen Stretch erzwungen hätte. Dieses Skript behält die lineare Stufe — dort gehört die Farbkalibrierung hin — und überlässt die dynamischen Paletten dem Werkzeug, das für die gestreckte Stufe gebaut ist.

---

### Synthetische Luminanz

Eine Schmalbandnacht hat keinen Luminanzfilter, und das Detail verteilt sich auf zwei oder drei Kanäle. **Build a synthetic luminance master** mittelt die Emissionslinien-Master zu `masters/TARGET_SynthL.fit`, das ihr gemeinsames Signal-Rausch-Verhältnis trägt.

**Das Mittel ist ungewichtet, und das ist eine Einschränkung.** Ein ungewichteter Mittelwert ist nur dann SNR-optimal, wenn alle Kanäle vergleichbares Signal tragen, und in SHO tun sie das nicht: SII liegt regelmäßig eine Größenordnung unter Ha. Bei Signalen 20, 2 und 1 mit gleichem Rauschen ergibt das Mittel SNR 13,3, der stärkste Kanal allein 20. Halte `SynthL` also gegen deinen besten Einzelkanal, bevor du darauf aufbaust — dominiert eine Linie das Feld, ist dieser Kanal womöglich die bessere Luminanz.

Eine gewichtete Fassung wurde geschrieben und in 1.7.8 wieder entfernt; die Gründe sind es wert, sie zu kennen, bevor man es selbst versucht. Die SNR-maximierenden Gewichte w ∝ Signal / Rauschen² sind **nicht invariant gegen eine kanalweise Skalierung** — und an dieser Stelle ist jeder Master durch `-output_norm` gegangen, das jeden einzeln affin nach seinen *eigenen* Extremen skaliert, ggf. gefolgt von `linear_match`. Die Gewichte würden diesen willkürlichen Faktoren folgen statt dem Himmel. Dazu kommt, dass die Rauschmessung ein eigenes Problem ist: ein außerhalb von Siril berechnetes Hintergrund-Sigma wich von Sirils eigenem `bgnoise` um das 1,1- bis 4,0-fache ab, am stärksten genau dort, wo Nebel den Frame füllt. Quadriert ergab das Ha mit 3,7 % einer M-16-SHO-Luminanz. Eine skaleninvariante Regel (w ∝ Signal / Rauschen) mit Sirils eigenem `bgnoise` wäre vertretbar; sie ist nicht gebaut.

Es wird bewusst **nicht** ins Farbbild kombiniert. Eine Luminanz-Kombination auf linearen Daten hebt das helle Ende vor der Farbkalibrierung an — derselbe Fehler, den *Quick linear LRGB* macht, an echten Daten gemessen mit 531 geclippten Sternen gegen 68. `todo.md` nimmt die Datei als Teil B auf und kombiniert sie nach dem Strecken, wo sie hingehört.

---

### Auto

**Auto** schlägt eine Palette aus den gefundenen Filtern vor, und immer nur eine, deren drei Kanäle sich tatsächlich füllen lassen:

| Gefundene Filter | Auto wählt |
|---|---|
| R, G, B **und** L | LRGB |
| R, G, B | RGB |
| SII, Ha, OIII | SHO |
| Ha, OIII | HOO |
| weniger | RGB, und der Kompositionsschritt benennt, was fehlt |

Breitband gewinnt, wenn es vollständig ist, weil es natürliche Farbe liefert. HaRGB wird nie automatisch vorgeschlagen — es verändert den Rot-Kanal absichtlich und bleibt deshalb immer eine bewusste Wahl. Für den gemappten Look manuell auf SHO / HOO / HaRGB wechseln.

Wählst du eine Palette, die deine Filter nicht füllen können, sagt das Skript das **bei der Auswahl**, nicht erst nach einem vollen Lauf. Es weigert sich in dieser Lage außerdem, Filter zu überspringen, damit du am Ende trotzdem verwertbare Master hast.

### Kanalübergreifende Ausrichtung

Jeder Filter wird gegen seinen *eigenen* Referenzframe gestackt, die Master können also auf leicht verschiedenen Pixelrastern liegen. Zur Korrektur werden alle Master in eine kleine Sequenz gelegt, neu registriert und mit `-framing=min` neu projiziert — das Ergebnis sind Kanäle, die **pixelidentisch** groß sind und exakt übereinanderliegen.

**Das kostet eine zweite Interpolation.** `seqapplyreg` läuft auf dem Weg zu einem Kanal zweimal: einmal über die Subframes dieses Filters, einmal über die drei fertigen Master. Beide Male mit begrenzter Interpolation, und jedes Resampling weicht das Bild ein wenig auf. Die Alternative mit nur einem Resampling — alle Frames *aller* Filter vor dem Stacken gegen eine gemeinsame Referenz registrieren — bräuchte eine Referenz mit genug Sternen für den sternärmsten Schmalbandkanal, also ausgerechnet den Frame, der am wenigsten davon hat, und gäbe die filtereigene Referenz auf, die jeden Stack so scharf macht, wie es seine beste Nacht erlaubt. Der Kompromiss ist bewusst gewählt; ob der zweite Durchgang genug Material hatte, zeigt die Sternpaar-Tabelle in `output.md`.

### Wie das Komposit zusammengesetzt wird

Die drei Kanäle werden aus Siril zurückgelesen, im Speicher gestapelt und als ein RGB-Bild übergeben (`new` + Pixeldaten), dann gespeichert. Sirils `rgbcomp` bleibt als Rückfallebene und ist weiterhin der einzige Weg für die `-lum=`-Kombination von *Quick linear LRGB* — das ist Sirils eigene Luminanzübertragung und keine Kanalkopie.

Der Grund ist prosaisch: `rgbcomp` behandelt gequotete Pfade nicht so wie `cd` / `load` / `save`, ein Leerzeichen im Ordnernamen zerlegte also den Dateinamen. Die Komposition hat das bisher umgangen, indem sie in den Master-Ordner wechselte und nackte Basisnamen übergab. Das Zurücklesen über Siril klärt nebenbei die Orientierungsfrage konstruktiv — welche Zeilenreihenfolge Siril herausgibt, bekommt es auch zurück, niemand muss `ROWORDER` interpretieren.

Der Report nennt, welcher der beiden Wege tatsächlich gelaufen ist.

### Stack only the filters this palette uses

**Standardmäßig aus.** Eingeschaltet werden Filter, die das Komposit nie liest, vollständig übersprungen.

Bei einer LRGB-Nacht, die als HOO verarbeitet wird, sind das vier von sechs Kanälen — der Lauf dauert also etwa halb so lange. Der größere Effekt betrifft aber das Bild selbst, und es lohnt sich zu verstehen, warum.

Sirils Two-Pass-Registrierung **wählt die Ausrichtungsreferenz selbst**, aus dem, was in der Sequenz liegt. Genau dafür existiert der Vorlauf, und `setref` kann ihn nicht überstimmen. Ein sternreiches Breitband-Master gewinnt in der Regel — und dann müssen die Schmalband-Kanäle sich an einem Frame ausrichten, dessen Sterne sie kaum teilen.

Gemessen an einer M-16-Nacht, gleiche Frames, gleiche Einstellungen:

| | Alle sechs Master im Pool | Nur Ha + OIII |
|---|---:|---:|
| Ausrichtungsreferenz | Luminanz | Ha |
| Gematchte Sternpaare für OIII | **12** | **1165** |
| SPCC R/G-Fit-Sigma | **5.76** | **2.73** |

Eine auf zwölf Punkten gefittete Transformation trägt ihren Maßstabsterm schlecht — und das erzeugt die Farbsäume in den Ecken.

Zwei Situationen bringen das Skript dazu, nichts zu überspringen (und zu sagen warum):

- die Palette hat ohnehin einen Kanal, den sie nicht füllen kann — das Komposit bricht dort so oder so ab, und die anderen Master sind mehr wert als die gesparte Zeit;
- es wird gar kein Komposit gebaut — ohne eines liest nichts eine Palette.

Der Kompromiss: **ein nie gebautes Master lässt sich später nicht wiederverwenden.** Wenn du mehrere Paletten aus einer Nacht probieren willst, lass die Option beim ersten Lauf aus.

---

## 10. Farbkalibrierung

### SPCC statt PCC

**Spectrophotometric Colour Calibration** berücksichtigt die Empfindlichkeitskurven deines Sensors und deiner Filter. Sirils eigene Dokumentation nennt sie die genauere Methode und PCC überholt — und für ein Mono-Rig hinter einem Filterrad ist dieser Unterschied bedeutsam, weil einfaches PCC generisches Breitband-R/G/B unterstellt.

An echten Daten zeigt sich das im Fit selbst: die Steigung Katalog gegen Bild ging von ~3,0 unter OSC-Annahmen auf ~0,95, sobald Mono-Sensor und Filter beschrieben waren.

### Den Fit lesen — was der Weißabgleich wert ist

Siril vergleicht die gemessene Farbe jedes Sterns mit derjenigen, die aus seinem Katalogspektrum vorhergesagt wird, und gibt das **Sigma** dieses Vergleichs aus. `output.md` führt es jetzt mit, zusammen mit der Sternzahl und den herausgekommenen Weißabgleichsfaktoren — denn „colour calibration done" liest sich gleich, ob die Sterne dem Katalog eng folgten oder wild darum streuten.

| Sigma eines Verhältnis-Fits | Bedeutung |
|---|---|
| deutlich unter 1 | die gemessenen Farben folgen dem Katalog; der Weißabgleich ist eine Messung |
| über 1 | ⚠️ die Lösung ist schwach — sie wurde angewendet, ist aber ein Startpunkt |

Sirils eigene Warnung *„imprecise solution"* trennt diese Fälle **nicht**: bei zwei Läufen derselben 94 Frames erschien sie in beiden, während sich die Sigmas um den Faktor vierzig unterschieden.

**Sigmas nur zwischen Läufen vergleichen, deren Kanäle dieselben Linien tragen.** Zwei Kanäle auf benachbarten Wellenlängen — etwa Ha bei 656,3 nm und SII bei 671,6 nm — ergeben für jeden Stern ein Verhältnis nahe 1; der Fit hat dann kaum Hebel, und sein Sigma fällt klein aus, weil die Messung *unempfindlich* ist, nicht weil die Lösung gut wäre. Die Zahl vergleicht Läufe einer Palette, sie rangiert keine Paletten.

Im Schmalband ist die übliche Ursache eines wirklich großen Sigmas *Normalize narrowband channels*: die Option ebnet genau das Linienverhältnis ein, das SPCC danach kalibrieren soll. Ein Kanal, der auf wenigen Sternpaaren ausgerichtet wurde, tut es ebenfalls — siehe die Sternpaar-Tabelle im selben Report.

### Die Namen richtig treffen

Ein Sensor- oder Filtername, den Siril nicht kennt, ist für Siril **kein Fehler** — es setzt still etwas anderes ein. Die klassische Falle:

> `IMX533` existiert **nur** in den OSC-Tabellen. Trägst du das ein, wird dein Filterrad-Rig stillschweigend als One-Shot-Color-Kamera kalibriert. Der Mono-Eintrag für denselben Chip heißt **`Sony IMX411/455/461/533/571`**.

Das Skript liest die SPCC-Datenbank, die Siril selbst verwendet (nur lesend, über sirilpy lokalisiert), und meldet einen Namen, der fehlt, mehrdeutig ist oder nur teilweise passt — bevor der Lauf so weit kommt. Eine Datenbank, die es nicht findet, bedeutet *nicht prüfbar*, nie *ungültig*.

Die gültigen Namen kannst du dir auch in Sirils Befehlszeile ausgeben lassen:

```
spcc_list monosensor
spcc_list redfilter
```

Die Felder sind **für das Rig des Autors vorbelegt** — Player One Ares-M Pro (IMX533 mono) mit Antlia LRGB V-Pro und 4,5-nm-Edge-SHO-Filtern. Überschreibe sie für deine Ausrüstung; sie werden gemerkt. Bleiben sie leer, greift die Konfiguration aus Sirils eigenem SPCC-Dialog.

### Schmalband wird auch kalibriert

Bei SHO oder HOO läuft SPCC im **Narrowband-Modus**: jeder gemappte Kanal wird über seine Emissionslinie beschrieben — Ha 656,3, OIII 500,7, SII 671,6 nm — plus der von dir gesetzten Bandbreite (Nachkommastellen wie 4,5 nm werden unterstützt). Gewöhnliche Sternphotometrie ist für gemappte Emissionslinien bedeutungslos, deshalb wird PCC für diese Paletten nie versucht.

Zwei Details, die man kennen sollte:

- **Der Sensorname geht mit.** Sirils Hilfe sagt, `-narrowband` lasse es „die vorangehenden *Filter*-Argumente" ignorieren — nur die Filter. Das ist Physik, keine Marotte: die Wellenlängen beschreiben die Filterdurchlässe, während die Quanteneffizienz des Sensors bei 656 und 501 nm ein davon unabhängiger Faktor im selben Produkt ist.
- **Die Filternamen bleiben dort bewusst weg**, und das Log sagt es — denn Siril echot seine gespeicherten Namen bei jedem Lauf, und sie sehen aus, als wären sie verwendet worden.

### Normalisierung und SPCC arbeiten gegeneinander

**Normalize narrowband channels** gleicht die SHO/HOO-Kanäle per Linear Match an die Ha-Referenz an, damit ein Hubble-Palettenstack nicht grün wird. Das ist nützlich — aber nicht, während SPCC kalibriert.

`linear_match` plättet das Ha/OIII-Flussverhältnis *absichtlich*, und genau dieses Verhältnis misst SPCCs Narrowband-Modus gegen Katalogspektren. Beides gleichzeitig heißt: die Kalibrierung liest eine Größe, die zuvor bewusst gelöscht wurde.

Gemessen an zwei Läufen derselben Daten, die sich nur in dieser Option unterscheiden:

| | Normalisierung an | Normalisierung aus |
|---|---:|---:|
| R/G-Fit-Sigma | 2,730 | **2,641** |
| Steigung des Fits | 1,251 | **1,209** (näher an 1 = weniger Korrektur nötig) |

Der Effekt ist real, aber moderat — deutlich kleiner als der Ausrichtungseffekt weiter oben. **Empfehlung:** Normalisierung *aus*, wenn SPCC kalibriert, und *an*, wenn nicht. Log, Bericht und `todo.md` nennen jeweils, was für deinen Lauf gilt.

### Die Rückfallkette

Die Farbkalibrierung weicht Stufe für Stufe aus und bricht das Auto-finish nie ab:

1. **SPCC** mit deinen Sensor-/Filternamen (bzw. den Narrowband-Wellenlängen)
2. **SPCC** blank — mit dem, was in Sirils Voreinstellungen steht
3. **PCC** (NOMAD-Katalog) — nur Breitband-Paletten
4. **PCC** gegen einen lokalen Gaia-Katalog — funktioniert offline
5. aufgeben, und das im Bericht und in `todo.md` klar sagen

### HaRGB ist bewusst ausgenommen

Sein Rot-Kanal trägt beigemischtes Ha, wodurch die Sternphotometrie ungültig wird. Das Skript überspringt die Farbkalibrierung dort, sagt es, und das gespeicherte Komposit wird als **unkalibriert** bezeichnet — gleiche es von Hand ab.

### Quick linear LRGB

Standardmäßig bleibt die **Luminanz getrennt**: das RGB wird für sich kalibriert, und L wird *nach* dem Strecken kombiniert. Das ist Sirils empfohlene Reihenfolge.

**Quick linear LRGB** backt L stattdessen schon bei der Komposition ein. Das ist schneller und manchmal bequem, hebt aber das obere Ende an — mehr Sterne sättigen und fallen aus dem photometrischen Fit. Gemessen an zwei Läufen über dieselben R/G/B-Master:

| | L getrennt | L eingebacken |
|---|---:|---:|
| Als *pixel out of range* verworfene Sterne | 68 von 2603 | **531 von 2597** |
| Sterne in der Lösung | 1484 | 1057 |
| R/G-Fit-Sigma | 1,148 | 1,334 |

Wenn du sie nutzt, vermerken Bericht und `todo.md`, dass der resultierende Weißabgleich brauchbar, aber nur näherungsweise ist.

### Was Auto-finish tut — und das eine, was es bewusst nicht tut

```
platesolve → subsky → SPCC (oder PCC) → speichern, weiterhin linear
```

**Die Grünentfernung (SCNR) gehört nicht dazu.** Siril rechnet sie als

```
green = min(green, (red + blue) / 2)
```

Für ein Breitbandbild ist das genau richtig — nichts am Himmel ist wirklich grün, ein Grünstich ist also Farbrauschen. Bei einer **Zuordnungspalette ist es das nicht**: der Grünkanal trägt eine echte Emissionslinie. Bei SHO ist das Ha, das stärkste Signal der meisten Nebel, und der Ausdruck stutzt es überall dort auf den Mittelwert von SII und OIII, wo es dominiert. Das ist gemessener Fluss, kein Stich. Bei einem M-16-Lauf waren es im Mittel rund 3 % des Ha und in den hellen Säulen erheblich mehr.

Sie ist außerdem **nichtlinear und pixelweise**, würde also genau die Eigenschaft zerstören, mit der das Komposit übergeben wird. Dieselbe Begründung galt schon für das Gegenmittel gegen Magentasterne (`invert` → `rmgreen` → `invert`) und gilt jetzt durchgängig: `todo.md` führt die Grünentfernung als deinen eigenen Schritt nach dem Strecken, wo du siehst, was sie kostet.

---

## 11. Ausgabedateien

```
output/
├─ TARGET_RGB.fit        das fertige Farbbild (linear, kalibriert)
├─ TARGET_RGB_preview.fit gestreckte Vorschau, falls aktiviert
├─ masters/
│   ├─ TARGET_FILTER.fit            ausgerichtet — diese zum Kombinieren nutzen
│   └─ TARGET_FILTER_29x300s_G100_-10C_fullframe.fit
│                                   voller, unbeschnittener Stack
├─ output.md             was das Skript getan hat, Schritt für Schritt
├─ todo.md               Anleitung für die finale Bearbeitung
├─ calib/                Master-Dark / -Flat / -Bias — beim nächsten Lauf wiederverwendet
├─ qa/                   Rejection-Maps (falls aktiviert)
└─ _work/                Zwischendateien — jederzeit löschbar
```

**`masters/` enthält zwei Fassungen pro Kanal.** Die `_fullframe`-Datei ist der Stack in seiner eigenen Geometrie; die schlichte wurde auf das gemeinsame Raster neu projiziert und ist die, die man zum Kanalkombinieren nimmt.

Der Name der Vollformat-Datei trägt das Rezept: **integrierte Frames × Belichtung, Gain, Sensortemperatur** — `M16_HA_29x300s_G100_-10C_fullframe.fit`. Die Frame-Zahl ist die, die die Registrierung überlebt hat, nicht die eingestellte — der Name kann also nie mehr versprechen, als in der Datei steckt. Ein Kanal mit gemischten Belichtungen bekommt schlicht `40subs` statt eines `NxT`, das für keine der beiden Hälften stimmen würde. Der ausgerichtete Master behält den kurzen Namen `TARGET_FILTER.fit`, weil `rgbcomp` und *Reuse existing masters* genau danach suchen.

### Die beiden Dokumente

**`output.md`** ist ein vollständiger Verarbeitungsbericht: gefundene Filter, Frames *gefunden vs. tatsächlich gestackt*, Belichtungszeit, der pro Kanal verwendete Rejection-Algorithmus, welches Kalibrierungsmaster in welchen Filter ging, jede wirksam gewordene Option und die tatsächlich gelaufenen Auto-finish-Schritte.

**`todo.md`** ist eine palettenspezifische Anleitung für den kreativen Teil — Strecken, Farbabgleich und bei LRGB die abschließende Luminanz-Kombination, mit konkreten Siril-Menüpfaden.

### Beide Dokumente beschreiben, was tatsächlich passiert ist

Das ist das Leitprinzip hinter der Berichterstattung, und es ist erwähnenswert, denn ein Bericht, der den *Normalfall* beschreibt, ist schlechter als kein Bericht:

- Ein Filter, der übersprungen wurde, der fehlgeschlagen ist oder den ein Abbruch nie erreicht hat, wird als solcher gezeigt, statt eine Frameanzahl zu bekommen. Ein Filter, den die Palette nicht liest, steht als *not stacked* mit genau diesem Grund da — nicht als „der Lauf wurde gestoppt".
- Vorhergesagte Anzahlen sind als Schätzung (`≈`) oder Obergrenze (`≤`, k-Sigma) markiert, nie als gemessen ausgegeben.
- Der genannte Rejection-Algorithmus ist der, der wirklich lief.
- „Haben die Qualitätsfilter gegriffen?" wird daraus beantwortet, was der Registrierung tatsächlich übergeben wurde — nicht nachträglich aus einer Frameanzahl abgeleitet, die die Registrierung verändert haben kann.
- Eine astrometrische Lösung, die das Komposit von plate-solvten Mastern *geerbt* hat, wird von einer eigens berechneten unterschieden.
- Ein Komposit, das nie entstanden ist, wird nicht beschrieben, als gäbe es eines.
- Das gespeicherte Komposit heißt nur dann *kalibriert*, wenn wirklich kalibriert wurde.
- Es wird nie zu einer Option geraten, die nicht die Ursache war, und kein Tipp gegeben, den der Lauf unmöglich gemacht hat.

---

## 12. Master wiederverwenden

**Reuse existing masters** erlaubt es, eine andere Palette ohne erneutes Stacken zu probieren:

- **Volle Wiederverwendung** — alle ausgerichteten Master existieren: Stacking *und* Ausrichtung entfallen, du zahlst nur die Komposition (Sekunden).
- **Teilweise Wiederverwendung** — einige Master existieren: das Skript behält diese und stackt nur die fehlenden Filter.

Was übersprungen wird und warum, steht immer im Log.

### Zwei Dinge verhindern die volle Wiederverwendung — beide mit Absicht

1. **Ein nie gebautes Master lässt sich nicht wiederverwenden.** Ein Lauf mit *Stack only the filters this palette uses* muss für eine Palette, die die anderen braucht, vollständig wiederholt werden.
2. **Die ausgerichteten Master müssen alle dieselbe Größe haben.** `-framing=min` schneidet auf die Schnittmenge dessen zu, was zusammen ausgerichtet wurde — ein Lauf über eine Teilmenge lässt die übrigen Kanäle also auf dem vorherigen Raster zurück. Sie zu mischen würde `rgbcomp` Kanäle unterschiedlicher Maße übergeben, deshalb richtet das Skript stattdessen neu aus und benennt die Überbleibsel im Bericht.

Schalte die Wiederverwendung **aus**, nachdem du Stacking-Optionen geändert oder Frames hinzugefügt hast. Ansonsten ist ein erneuter Lauf gefahrlos: vorhandene Ausgaben werden überschrieben.

---

## 13. Empfohlene Arbeitsabläufe

### Eine normale LRGB-Nacht

1. Vorlage **Balanced**, Palette **Auto** (sie wird LRGB wählen).
2. *Stack only the filters this palette uses* **aus** lassen, falls du später eine andere Palette möchtest.
3. *Quick linear LRGB* **aus** lassen — SPCC soll das RGB allein kalibrieren.
4. Laufen lassen. Dann `todo.md` folgen: RGB strecken, Luminanz getrennt strecken, zuletzt kombinieren.

### Eine Schmalband-Nacht, bestmögliche Farbe

1. Palette **HOO** oder **SHO**.
2. **Stack only the filters this palette uses** *an* — hier zahlt es sich am meisten aus.
3. **Normalize narrowband channels** *aus* — SPCC soll das echte Linienverhältnis messen.
4. Filter-**Bandbreite** setzen (z. B. 4,5 nm) und den Sensornamen prüfen.
5. Laufen lassen, dann `todo.md` folgen.

### Mehrere Looks aus einer Nacht

1. Erster Lauf: alles an, *Stack only the filters this palette uses* **aus**, damit alle Master gebaut und gemeinsam ausgerichtet werden.
2. Folgeläufe: Palette wechseln, **Reuse existing masters** anhaken, in Sekunden neu komponieren.

### Nur mal in die Daten schauen

Vorlage **Quick look** mit *save stretched preview*. Keine Farbkalibrierung, keine QA-Artefakte — in wenigen Sekunden ein Blick auf die Nacht.

---

## 14. Fehlerbehebung

### „Colour composition skipped: the RED channel has no master"

Die Palette will einen Filter, den du nicht hast — SHO nimmt Rot aus einem **SII**-Filter, und keiner ist zugeordnet. Die Meldung nennt, was die Palette erwartet und welche Palette mit deinen Filtern funktionieren würde. Entweder die Palette wechseln oder den Kanal in den Dropdowns von Hand zuordnen.

Die Master sind da und brauchbar; der Lauf meldet *„Finished with N master(s), but NO colour image"* statt Erfolg zu behaupten.

### Die Farbe wirkt falsch, und SPCC meldet „imprecise solution"

Zwei übliche Ursachen, nach Wirkung sortiert:

1. **Keine Flats.** Vignettierung hinterlässt einen Helligkeitsgradienten über dem Feld, und Siril wird weiter *„consider correcting the image gradient first"* melden. Das ist die wirksamste Stellschraube, und keine Skripteinstellung ersetzt sie.
2. **Ein falscher Sensorname.** Siehe §10 — im Log nach einem Namen suchen, der nicht zu Sirils Mono-Tabellen passte.

### Ein Kanal hat die meisten Frames verloren

```
Registration dropped 3 of 6 frame(s) — 3 will be integrated.
Only 3 frame(s) left for OIII: too few for outlier rejection to mean much.
```

Frames ohne genügend erkennbare Sterne — Wolken, Dunst, ein durchziehender Schleier — lassen sich nicht ausrichten, und Siril schließt sie aus. Das sind Daten, kein Fehler. Behandle den Kanal als vorläufig und nimm mehr davon auf.

### „FITS error: failed to find or open the following file"

Fast immer ein **Cloud-synchronisierter Arbeitsordner**. Sirils `link` legt Symlinks an, und Dropbox & Co. schreiben sie mitten im Lauf um. Verschiebe den Arbeitsbaum auf eine lokale Platte oder nimm `output/_work/` von der Synchronisation aus. Siehe §3.

### „2-pass registration unavailable"

Erscheint das *zusammen mit* einem Datei-nicht-gefunden-Fehler, ist es das Cloud-Problem von oben, keine Frage der Siril-Version. Die beiden Fehlerarten werden genau deshalb getrennt gemeldet, damit man sie auseinanderhalten kann.

### Nach dem Bearbeiten des Skripts hat sich nichts geändert

Siril hält das geladene Skript im Speicher. Schließe das Skriptfenster und starte es neu aus dem Skripte-Menü.

### Im masters-Ordner haben die Dateien unterschiedliche Größen

Du hast mit *Stack only the filters this palette uses* gearbeitet, es wurden also nur einige Kanäle neu ausgerichtet. Der Bericht benennt die Überbleibsel. Ein Lauf mit ausgeschalteter Option bringt alle Kanäle zurück auf ein Raster.

---

## 15. Tipps & Empfehlungen

- **Nimm Flats auf.** Pro Filter, pro Session, bevor du das Rig abbaust. Nichts anderes auf dieser Liste kommt in der Wirkung nahe heran.
- **Baue einmal eine Dark- und Bias-Library.** Auf festen Sollwert gekühlt bleiben Darks monatelang gültig. Library-Ordner setzen und vergessen.
- **Gib Schmalband mehr Zeit, als du denkst.** Ein 4,5-nm-Filter ist dunkel. Sechs Subs reichen, um etwas zu sehen; für sinnvolle Rejection reichen sie nicht.
- **Rausch-Gewichtung für Schmalband**, gewichtete FWHM für Breitband.
- **Nicht vor der Kalibrierung strecken.** Das Skript übergibt aus gutem Grund linear.
- **Lies das Log, wenn dich etwas überrascht.** Jede Rückfallebene, jeder übersprungene Schritt und jede sich selbst widersprechende Kombination wird dort in einem Satz erklärt.
- **Behalte `masters/`.** Von dort aus lässt sich der gesamte Farbprozess ohne erneutes Stacken wiederholen — das macht Paletten-Experimente billig.
- **Magentafarbene Sterne sind bei Drei-Linien-Paletten normal.** Sterne sind Kontinuumsquellen: sie landen im Rot- und im Blaukanal, aber nicht in dem, der Ha trägt — SHO und Verwandte färben sie deshalb lila. Das übliche Gegenmittel läuft *nach* dem Strecken: `invert` → `rmgreen` (SCNR) → `invert`. Das Skript macht das nicht für dich, weil das Invertieren linearer Daten nicht dasselbe bedeutet wie das Invertieren gestreckter Daten; `todo.md` erinnert an der richtigen Stelle daran.
- **Benenne deine Ziele über die Nächte hinweg einheitlich** (`M16`, nicht einmal `M 16` und in der nächsten Session `Adlernebel`) — das Skript vergleicht Namen normalisiert, aber Einheitlichkeit hält die Ordner sauber.

---

## 16. Häufige Fragen

**Funktioniert es mit einer Farbkamera (OSC)?**
Nein, und das bewusst. Frames werden nie debayert. Dies ist ein Mono-Filterrad-Arbeitsablauf.

**Brauche ich Kalibrierungsframes?**
Nein. Alles ist optional und additiv: ganz ohne stackt das Skript rohe Lights genau so, wie es das vor der Kalibrierungs-Unterstützung getan hat. Flats bringen die größte Verbesserung.

**Kann ich mehrere Nächte kombinieren?**
Ja — leg sie unter einen Zielordner. Derselbe Filter aus verschiedenen Nächten wird automatisch zu einem Stack zusammengefasst.

**Warum ist mein Bild fast schwarz?**
Es ist linear, und das ist richtig so. Öffne `todo.md` und folge den Streckschritten, oder aktiviere *save stretched preview* für einen schnellen Blick.

**Warum hat HaRGB keine Farbkalibrierung?**
Sein Rot-Kanal trägt beigemischtes Ha, die Sternphotometrie beschreibt ihn also nicht mehr. Jede photometrische Kalibrierung würde das Falsche messen. Gleiche ihn von Hand ab.

**Was passiert, wenn ich das Fenster mitten im Lauf schließe?**
Es fragt zuerst nach, beendet dann den aktuellen Filter und hört dort auf. Ausrichtung, Plate-Solving, das Farbbild und das Aufräumen von `_work/` entfallen — ein Komposit aus der Hälfte der Kanäle ist nicht das Bild, das du wolltest. Die fertigen Master bleiben erhalten, und Log, Bericht und Dialog sagen *gestoppt*, nicht *fertig*. Mit **Reuse existing masters** machst du weiter.

**Kann ich es ohne Internetverbindung nutzen?**
Ja. Installiere einen lokalen Gaia-Katalog in Siril, dann erreicht ihn die Kalibrierungskette. Ohne beides entsteht das Komposit trotzdem — nur unkalibriert, und der Bericht sagt das.

**Verändert es meine Rohframes?**
Nein. Alles wird unter `output/` geschrieben, die Rohframes werden nur gelesen.

---

## 17. Neu in 1.7.11

- **Der Rauschboden der Flat-Prüfung wird auf den Vergleich skaliert, den er beurteilt.** Der Boden entsteht durch Halbieren der Referenznacht — aber jede Hälfte mittelt *weniger* Frames als die Karten im echten Nacht-zu-Nacht-Vergleich, die rohe Hälften-Streuung überschätzte das wahre Vergleichsrauschen also um gemessene **√2** (1,415 über 300 simulierte Läufe) bei gleichen Frame-Zahlen. „Kein Formunterschied nachweisbar" deckte damit echte Flat-Unterschiede bis zur Größe des Rauschens selbst. Die Hälften-Streuung wird jetzt auf die tatsächlichen Frame-Zahlen abgebildet (Varianz pro Karte ∝ 1/n, Ratio-Varianzen addieren sich); stoßen beide Hälften bereits an die Frame-Obergrenze pro Nacht, ist der Faktor 1, denn dann tragen die Hälften dasselbe Rauschen wie die vollen Karten.
- **`_rebin_mean` hält seinen Vertrag „Langseite höchstens target" ein.** Floor-Division ließ ein 650-px-Frame bei 325 px stehen und alles zwischen target und dem Doppelten ganz ungebinnt — kleine Sensoren verglichen auf feinerem, rauschigerem Raster gegen Schwellen, die für die ~250-px-Skala kalibriert sind. Der Faktor ist jetzt das Ceiling.
- **Flats abweichender Bildgröße werden benannt statt still verworfen.** Eine Nacht mit gemischtem Binning ging bisher in den Vergleich ein, als wäre sie sauber — auf einer Karte, die still aus einem Bruchteil ihrer Frames gebaut war; die Prüfung meldet jetzt, wie viele Frames außen vor blieben und warum.
- **Keine falsche „Werte wurden zurückgesetzt"-Zeile mehr beim Start.** Mit gespeichertem k-sigma wendet die Wiederherstellung zuerst den Modus an (er setzt die Spin-Bereiche), und der Modus-Handler behauptete dann, die ersetzten Konstruktor-Defaults „waren Prozente" — einen Moment bevor die echten Sigmas wiederhergestellt wurden. Während Settings oder ein Preset angewandt werden, ist die Meldung stumm; ein Live-Moduswechsel meldet sie weiterhin.

## Was in 1.7.10 neu war

- **Die HaRGB-Beimischung ist jetzt linear.** Sie mischte Ha per Screen-Blend in Rot, `1-(1-R)·(1-k·Ha)`, dessen `R·Ha`-Kreuzterm quadratisch im Fluss ist. Am schwachen Ende unsichtbar — die Handbücher haben das sogar nachgemessen — aber bei R = 0,8 und k·Ha = 0,4 liefert er 0,88 statt 1,2, also **27 % Kompression** genau der Sterne und Nebelkerne, die du danach streckst. Nicht linear, und Linearität ist die eine Eigenschaft, mit der hier jedes Komposit übergeben wird — derselbe Einwand, der `rmgreen` in 1.7.4 entfernt hat. Es ist jetzt `(R + k·Ha) / (1+k)`: eine gewichtete Summe, ohne Rescale in [0,1], die R nie verwirft. Der Regler geht von reinem R bei 0 % bis zu einer gleichen Mischung bei 100 %, und das Log nennt die beiden verwendeten Gewichte. §9 rechnet es durch.
- **Der Hilfe-Tab mit den Ausgabedateien behauptet nicht mehr, `_HaRGB` sei kalibriert.** Er nannte alle Komposite „calibrated and linear", während ein zweiter Tab korrekt sagte, HaRGB werde von der photometrischen Kalibrierung ausgenommen. Für diese eine Datei war beides falsch; die Ausnahme steht jetzt dort, wo die Dateien aufgezählt werden.
- **Die `MIN_STACK_FRAMES`-Sperre gilt für die Kombination der Qualitätsfilter, nicht für jeden einzeln.** Siril behält die Frames, die *alle* Filter passieren — die Überlebenden sind eine Schnittmenge. Vier 60-%-Schnitte auf 20 Frames kamen einzeln durch und projizierten zusammen auf **2** Überlebende gegen einen Boden von 4. Die laufende Schätzung multipliziert die Anteile; das unterstellt eine Unabhängigkeit, die die Metriken nicht haben, also irrt sie in Richtung „Frames behalten", und das ist für diesen Boden die richtige Richtung. Normale Einstellungen bleiben unberührt: drei 90-%-Schnitte auf 30 Frames greifen weiterhin alle. Für k-sigma lässt sich gar nichts projizieren, dort wird stattdessen die Zahl kombinierter Schnitte gedeckelt (zwei).
- **Die Integrationszeit eines Kanals mit gemischten Belichtungen ist als Schätzung markiert.** Die Skalierung über das Frame-Verhältnis unterstellt gleich lange Frames, und es ist nirgends festgehalten, *welche* verworfen wurden — bei 20×300 s + 10×120 s bis zu acht Minuten Abweichung. Die Zahl trägt jetzt ein **~**, und der Report sagt warum.
- **Geprüft und bewusst nicht geändert:** die Qualitätsmediane lassen Nullen per Wahrheitswert-Test weg. Das sieht nach einem statistischen Fehler aus und ist keiner — sirilpy dokumentiert roundness als „0 when uninit, ]0, 1] when set", eine FWHM von null gibt es nicht, und ein Frame ohne Sterne ist nicht registrierbar und erreicht die Stichprobe nie. Die naheliegende Reparatur würde die Zahl verschlechtern. Die Begründung steht jetzt im Code.

## Was in 1.7.9 neu war

- **Die Log-Auswertungen hängen nicht mehr an einer Diagnose.** 1.7.8 hat eine Art repariert, auf die die Sternpaar-Zahlen verschwinden; der nächste Lauf ließ denselben Leser aus dem *anderen* Grund scheitern — das Log kam sauber zurück, der Anker war nur nicht darin. Sirils Log ist nicht der reine Anhänge-Strom, den beide Schnappschuss-Wege unterstellen: stderr anderer Prozesse landet ebenfalls darin, und bei diesem Lauf schrieb ein neu gestarteter Multiprocessing-Resource-Tracker einen `PermissionError`-Traceback mitten in den gemessenen Schritt. Die Leser fallen jetzt auf eine **Marke zurück, die der Schritt selbst schreibt**: die Ausrichtung auf das Verzeichnis, das `register` nennt, die Farbkalibrierung auf `Running command: <cmd>` — aus der Kommandoliste genommen, nicht aus einem Anzeigetext geschnitten, der jederzeit umformuliert werden darf. Gegen das echte Log nachgespielt, Tracebacks inklusive, holen beide 1376 und 1392 Sternpaare mit OIII als Referenz zurück: genau die Zahlen, die zwei Zeilen über der Fehlermeldung standen. Gibt Siril gar nichts heraus, wird weiterhin nichts gemeldet — die einzige ehrliche Antwort, die dann bleibt.
- **Die Einmal-Warnung gilt pro Diagnose, nicht pro Lauf.** Ein gemeinsames Flag hieß, dass der erste scheiternde Leser auch die Meldung des zweiten verschluckte — bei diesem Lauf einen SPCC-Fit mit σ 5,5 und 6,7 gegen eine Grenze von 1,0, also genau die Zahl, die man sehen will.
- **Die Rejection-Änderung für Kalibriermaster aus 1.7.7 ist an echten Daten bestätigt.** Dafür musste `output/calib` erst gelöscht werden: die Läufe davor haben jeden gecachten Master wiederverwendet und sie nie ausgeführt. Mit geleertem Cache echot Siril alle vier Stufen — Linear Fit 5/4 für den 442-Frame-Darkflat-Satz, Sigma 3/3 für die Fünf- und Zehn-Frame-Nacht-Flats, Winsorized 3/3 für das gepoolte 20-Frame-Master.

## Was in 1.7.8 neu war

- **Die gewichtete synthetische Luminanz aus 1.7.7 ist zurückgenommen.** Sie lief nie: `get_image_stats` liefert für ein frisch geladenes Bild nichts, wenn Siril dafür keine Statistik gecacht hat — die Messung las ein Rauschen von null, lehnte es ab, und jeder Lauf fiel auf das ungewichtete Mittel zurück. Die Messung zu reparieren hätte nicht geholfen, denn die Formel ist für diese Eingaben falsch: w ∝ Signal/Rauschen² ist **nicht invariant gegen eine kanalweise Skalierung**, und an dieser Stelle ist jeder Master durch `-output_norm` gegangen (affin, pro Kanal, nach seinen *eigenen* Extremen) und ggf. durch `linear_match`. Die Gewichte würden diesen willkürlichen Faktoren folgen statt dem Himmel. Gemessen statt argumentiert: ein hier berechnetes Hintergrund-Sigma wich von Sirils eigenem `bgnoise` um das 1,1- bis 4,0-fache ab, am stärksten genau dort, wo Nebel den Frame füllt — quadriert ergab das Ha mit 3,7 % einer SHO-Luminanz. Ha ist in M 16 die stärkste Linie.
- **Das Mittel ist zurück und wird jetzt beschrieben, statt als optimal ausgegeben zu werden.** Tooltip, Log-Zeile, `output.md` und §9 sagen *ungewichtetes Mittel*, sagen, dass ein deutlich schwächerer Kanal das Ergebnis herunterzieht, und sagen, es vor dem Weiterarbeiten gegen den stärksten Kanal zu halten. Eine skaleninvariante Regel (w ∝ Signal/Rauschen) mit Sirils eigenem `bgnoise` wäre vertretbar; sie ist nicht gebaut, und der Code hält fest, was sie bräuchte.
- **Der Log-Leser ist an der Wurzel repariert, nicht erneut geflickt.** `get_siril_log()` liefert auf zwei Pfaden in sirilpy nichts zurück, *ohne zu werfen* — ein NONE-Status und eine Antwort, die zu kurz ist, um den Shared-Memory-Handle zu tragen; beides heißt, Siril hat den Transfer verweigert. Drei Aufrufstellen machten daraus einen leeren String, was weiter unten wie ein erfolgreich geholtes, zufällig leeres Log aussieht; die Delta-Suche fand dann nichts, und der Lauf meldete einen übergelaufenen Puffer. Der war nicht übergelaufen: beim M-16-Lauf standen die beiden Sternpaar-Zahlen, 1393 und 1377, zwei Zeilen über genau dieser Meldung in Sirils eigener Konsole. Es war überhaupt nichts gelesen worden. „Leer" heißt jetzt überall „unlesbar", der Schnappschuss versucht es einmal erneut (die Verweigerung ist momentan — der vorige Aufruf im selben Schritt war erfolgreich), und die Warnung benennt, welches der drei Dinge schiefging, statt für alle dieselbe Vermutung zu drucken.
- **Die Rejection-Änderung für Kalibriermaster aus 1.7.7 bleibt unangetastet** — aber gecachte Master werden wiederverwendet, ein vorhandenes `output/calib` muss also gelöscht werden, damit die neuen Stufen greifen. Der erste Lauf nach 1.7.7 hat jeden Master wiederverwendet und sie nie ausgeführt.

## Was in 1.7.7 neu war

- **Kalibriermaster laufen jetzt durch dieselbe Rejection-Tabelle wie die Light-Stacks.** Sie wurden mit einem nackten `rej 3 3` gestapelt, und ein nacktes `rej` wählt Sirils Vorgabe — winsorized, die Stufe für 11–30 Frames. Sie traf beide Enden des Bereichs gleichzeitig: ein Nacht-Master-Flat aus fünf Frames, wo Winsorizing Sigma aus fünf Punkten schätzt und Ausreißer durch ihre eigenen Nachbarn ersetzt, und ein Bibliotheks-Dark aus vierhundert, wo ein Linear Fit den Trend über den Stack modelliert, den Winsorizing nicht sieht. Beim M-16-Lauf gehen die Fünf- und Zehn-Frame-Flats auf Sigma 3/3, der 442-Frame-Darkflat-Satz auf Linear Fit 5/4. Für Kalibriermaster bleibt die Rejection an, unabhängig davon, was den Light-Stacks gesagt wurde — der Schalter betrifft das Integrieren deiner eigenen Frames, und ein kosmischer Treffer in einem Master-Flat erreicht jedes Light, das dadurch geteilt wird. Details in §8.
- **Die synthetische Luminanz wird gewichtet, nicht gemittelt.** Sie versprach „das gemeinsame Signal-Rausch-Verhältnis" und bildete dabei ein ungewichtetes Mittel — optimal nur, wenn die Kanäle vergleichbares Signal tragen, was in SHO nicht der Fall ist. Bei Signalen 20 / 2 / 1 mit gleichem Rauschen ergibt das Mittel SNR 13,3, Ha *allein* aber 20: die Luminanz kam schlechter heraus als der beste Kanal in ihr, und die Schmalband-Normalisierung verschärfte das noch, weil sie das Rauschen des schwachen Kanals vorher mit seinem Signal hochskaliert. Jetzt gelten die Matched-Filter-Gewichte w ∝ Signal / Rauschen², an jedem Master über Sirils eigene Statistik gemessen. Dieselben drei Kanäle: 87 % / 9 % / 4 %, SNR 20,1. Log und Report nennen die Anteile, ein Kanal über 80 % wird ausdrücklich genannt, und das ungewichtete Mittel bleibt als benannter Rückfall, wenn die Statistik nicht lesbar ist. Details in §9.

## Was in 1.7.6 neu war

- **Die Flat-auf-Flat-Prüfung hat Photonenrauschen gemessen, nicht die Optik.** Sie teilte *ein* Flat der einen Nacht durch *ein* Flat der anderen, Pixel für Pixel, und las die Standardabweichung. Zwei Subs **derselben** Nacht — deren Formunterschied konstruktionsbedingt null ist — ergeben an einem echten 24 000-ADU-Flat **1,78 %**, bei einer Grenze von 0,30 %. Die Prüfung meldete also „a real mismatch", um das Sechsfache darüber, bei jedem Datensatz, den sie je gesehen hat, und riet dazu, eine Option gegen einen Unterschied einzuschalten, den es nicht gab. War die Option schon an, druckte sie dieselbe Zahl als Begründung der Aufteilung.
- **Die Ursache war, Schwellen ohne ihr Verfahren zu übernehmen.** Die 0,15 % / 0,30 % stammen aus dem *Flat On Flat Analyzer*, der zwei **Master**-Flats vergleicht und die Karte vor der Messung auf ~250 px an der langen Seite **blockmittelt**. An einem 3008-px-Frame ist das 12×12; zusammen mit dem Stacken nehmen beide Schritte rund den Faktor 27 aus dem Rauschen. Beides passiert jetzt auch hier: Eine ganze Nacht wird gemittelt und vertritt so den Master, und die Blockung bildet die des Referenzwerkzeugs nach.
- **Die Prüfung misst jetzt ihren eigenen Rauschboden.** Die Referenznacht wird halbiert und mit sich selbst verglichen; zwei Hälften derselben Nacht unterscheiden sich um nichts als Rauschen, diese Zahl ist also die Fehlergrenze. Darunter meldet der Lauf „kein Formunterschied nachweisbar" statt einer Zahl ohne Bedeutung. §5 erklärt beide Schritte.
- **Beim M-16-Lauf kippen damit alle drei Filter von „a real mismatch" bei 1,78 % auf Übereinstimmung bei 0,06–0,08 %**, gegen einen Boden von 0,06 %. Die Master derselben Nächte stimmen auf 0,027 % überein. Die Flat-Kalibrierung pro Nacht ist davon unberührt und weiterhin sinnvoll — sie schützt gegen einen Aufbau, der sich wirklich verändert hat. Geändert hat sich, dass ihr Report sich die Belege dafür nicht mehr selbst erfindet.

## Was in 1.7.5 neu war

- **Die Output-Normalisierung ist dokumentiert, wie sie wirklich arbeitet.** Aus Sirils Quelltext gelesen: bei 32-Bit-Ausgabe ist sie `(x − min) / (max − min)` mit den *eigenen* Extremwerten des Masters — eine affine Abbildung pro Kanal, getrieben von einzelnen Pixeln, keine gemeinsame Skala. Der Tooltip behauptete, sie normalisiere „den Hintergrundpegel", und ein Hinweis im Lauf behauptete, das Abschalten von *Normalize narrowband channels* lasse das physikalische Linienverhältnis unangetastet. Beides stimmte nicht, solange diese Option an war. §8 erklärt es jetzt, und der Hinweis nennt beide Optionen.
- **Die zweite Interpolation steht jetzt da.** `seqapplyreg` läuft auf dem Weg zu einem Kanal zweimal — einmal über die Subframes, einmal über die fertigen Master — und jedes Resampling weicht das Bild ein wenig auf. §9 sagt das und sagt, warum die Alternative mit nur einem Resampling nicht gewählt wurde: sie bräuchte eine gemeinsame Referenz mit genug Sternen für den sternärmsten Schmalbandkanal.

## Was in 1.7.4 neu war

- **SCNR (Grünentfernung) läuft nicht mehr auf dem Komposit.** Siril rechnet sie als `green = min(green, (red + blue) / 2)`. Bei einem Breitbandbild ist das die richtige Kur gegen Farbrauschen; bei einer Zuordnungspalette trägt der Grünkanal eine **echte Emissionslinie** — bei SHO das Ha — und der Ausdruck beschneidet gemessenen Fluss überall dort, wo diese Linie dominiert. Bei einem M-16-Lauf im Mittel rund 3 % des Ha, in den hellen Säulen erheblich mehr. Sie ist außerdem nichtlinear und zerstörte damit genau die Eigenschaft, mit der das Komposit übergeben wird. `todo.md` führt die Grünentfernung jetzt als deinen eigenen Schritt nach dem Strecken, in beiden Zweigen, und nennt, was sie rechnet.
- **Die Farbzusammenführung selbst wurde gegen beide Referenzimplementierungen geprüft** — Cyril Richards PalettePicker und Franklin Mareks Perfect Palette Picker. Beide setzen das RGB genauso zusammen wie dieses Skript (`new` + `set_image_pixeldata`), und beide arbeiten auf **gestreckten** Daten, weshalb keine von beiden farbkalibrieren kann. Genau das ist der Unterschied — und die Reihenfolge (ausrichten → normieren → kombinieren → platesolve → Hintergrund → kalibrieren) stimmt. SCNR führt auch keine der beiden aus.
- **Behoben: die SPCC-Namensprüfung hatte denselben Log-Lesefehler** wie die beiden in 1.7.2 reparierten Leser — eine dritte Stelle, die annahm, Sirils Log wachse nur. Sie geht jetzt über `_log_delta`, ein falscher Filtername wird also auch spät in einer langen Sitzung noch erkannt, statt dass die Prüfung stillschweigend „Datenbank nicht gefunden" meldet.

## Was in 1.7.3 neu war

- **Behoben: mit *Delete `_work/` when finished* scheiterte jeder Filter an der Registrierung.** Sirils `merge` kopiert seine Quellframes nicht, es verlinkt sie symbolisch — 30 Frames in 4 ms sind keine Kopie von 30 × 36 MB. Die kalibrierten Teile direkt nach dem Merge freizugeben machte die gemergte Sequenz damit zu toten Links, und die Registrierung starb auf allen drei Kanälen mit *failed to find or open merged_HA_00001.fit*. Die Teile werden jetzt erst freigegeben, wenn die Registrierung eigene Frames geschrieben hat.
- Der Fehler war so lange latent, wie es den Teil-Pfad gibt, wurde aber nur ausgelöst, wenn ein Filter Belichtungszeiten mischte **und** die Aufräum-Option an war. Da 1.6.0 jeden Mehrnacht-Lauf nach Nacht aufteilt, wurde er allgemein — für jeden, der dieses Häkchen setzt.

## Was in 1.7.2 neu war

- **Die beiden Log-Auswertungen hatten stillschweigend aufgehört zu arbeiten.** Die Sternpaar-Zahlen und die neuen Farbfit-Werte werden aus Sirils Log gelesen, indem ein Schnappschuss vor einem Schritt mit einem danach verglichen wird. Dieser Vergleich unterstellte, das Log wachse nur — sein Puffer ist aber begrenzt, und bei einem vollen Drei-Filter-Lauf fallen die ältesten Zeilen vorne heraus; danach ist kein früherer Schnappschuss mehr ein Präfix. Beide Leser kehrten dann wortlos zurück, eine ausgefallene Diagnose sah also genauso aus wie eine, die nichts zu sagen hat.
- **Die Differenz wird jetzt am Ende des Schnappschusses verankert** statt an seinem Anfang; das übersteht ein abgeschnittenes Vorderende. Ist auch dieser Anker weg, sagt der Lauf es einmal und nennt die Folge — am Bild ändert sich nichts, es sind Diagnosen.

## Was in 1.7.1 neu war

- **`output.md` sagt jetzt, wie gut die Farblösung gepasst hat.** Siril gibt das Sigma jedes Verhältnis-Fits aus — wie weit die gemessenen Sternfarben um die aus Katalogspektren vorhergesagten streuen — und das Skript hat es verworfen; „colour calibration done" las sich damit für eine solide und eine hoffnungslose Lösung gleich. Der Report führt Sigmas, Sternzahlen und Weißabgleichsfaktoren, und ein Sigma über 1 wird markiert. Siehe §10.
- **Sirils eigene Warnung „imprecise solution" trennt diese Fälle nicht**: bei zwei Läufen derselben 94 Frames erschien sie in beiden, während sich die Sigmas um den Faktor vierzig unterschieden. Das Sigma trennt sie.
- **Mit einem Vorbehalt, den der Report selbst nennt:** zwei Kanäle auf benachbarten Wellenlängen ergeben für jeden Stern ein Verhältnis nahe 1; das Sigma dieses Fits ist klein, weil die Messung unempfindlich ist, nicht weil die Lösung gut wäre. Sigmas innerhalb einer Palette vergleichen, nicht zwischen Paletten.

## Was in 1.7.0 neu war

- **Fünf weitere Schmalband-Paletten: `SOH`, `HHO`, `OOS`, `SHH`, `SOO`.** Die Tabelle wurde Zeile für Zeile gegen Franklin Mareks **Perfect Palette Picker** in der Seti Astro Suite Pro geprüft — die Quelle, aus der Cyril Richards PalettePicker übernommen hat. `SOH` erwies sich als die eine Permutation dreier verschiedener Linien, die in unserer eigenen Tabelle fehlte, ohne dass etwas dahinterstand. Jetzt sind alle sechs Permutationen und acht Zweilinien-Varianten da, und die Suite schlägt fehl, wenn wieder eine verschwindet.
- **Die Koeffizienten von Realistic1 / Realistic2 wurden gegen dieselbe Quelle geprüft** und stimmen exakt überein, Ziffer für Ziffer — eine Tabelle, die wir bisher nur aus zweiter Hand hatten.
- **Die Darstellung der dynamischen Paletten in §9 ist von der anderen Seite bestätigt.** Der Haken *Linear Input Data* im Perfect Palette Picker bringt dessen Gate `x^(1-x)` nicht bei, lineare Daten zu lesen: er streckt zuerst auf `target_median=0.25` und baut die Palette aus der gestreckten Kopie. Der Haken existiert, weil die Palette ohne das Strecken nicht funktioniert.

## Was in 1.6.2 neu war

- **Die Tabelle Discovered Filters ist auf ihre Zeilen bemessen.** Ihre Höhe kam vom Idealmaß des Inhalts statt von den Zeilen selbst, drei Filter wurden deshalb anderthalb Zeilen zu kurz abgeschnitten — hinter einem Scrollbalken über einer Tabelle, die nichts zu scrollen hatte. Das Ausblenden der Details-Spalte versteckte außerdem die *dehnende* Spalte mit, sodass rechts eine leere Fläche stehen blieb.
- **Die Kalibrierungs-Zusammenfassung sagt, woher die Frames kommen** — `Next to the lights: 60 flats` / `From the library: 442 darks at 3s`. Die Wahl eines Library-Ordners erzeugte bisher einen Pfad und keine sichtbare Folge; eine Library, die nichts beitrug, sah aus wie eine, die alles beitrug. Ein gewählter Ordner, der nichts geliefert hat, sagt das jetzt in Warnfarbe.

## Was in 1.6.1 neu war

- **Die Tabelle Discovered Filters sagt, was passieren wird — nicht, was gefunden wurde.** Die Spalte Flats zählte Flats im Ordner; bei einem Rig mit automatischem Panel ist das für jeden Filter dieselbe Zahl, während das Entscheidende unsichtbar blieb: diese 300-s-Lights bekommen **überhaupt kein Dark**. Die Spalte **Calibration** nennt jetzt die Master, die den Filter wirklich erreichen (`Dark + Flat ×3`, `Flat`, `none`), und ein `⚠` in Warnfarbe markiert einen Filter ohne Dark. Der Tooltip nennt die Belichtungszeiten, die die Library tatsächlich hat, und was helfen würde.
- **Die Kalibrierungs-Zusammenfassung steht jetzt unter den Schaltern, die sie beschreibt**, und ist von vier Zeilen auf eine geschrumpft. Pro-Filter-Text, der die Tabelle Zeile für Zeile wiederholte, geht ins Log, wo Länge nichts kostet; die Zeile trägt Library-Fakten und die Dark-Lücke.
- **Die Tabelle passt ihre Höhe an die Zeilen an**, und die Details-Spalte (Belichtung / Gain / Sollwert) tritt unter die Tabelle, solange alle Filter denselben Wert teilen.
- **Aus „Analyze Folder" wurde „Re-scan Folder"** — die Ordnerauswahl analysiert schon länger selbst, zwei gestapelte Buttons sahen also aus wie zwei Schritte, von denen einer bereits gelaufen war.

## Was in 1.6.0 neu war

- **Der Offset der Flats wird pro Filter gewählt.** Ein automatisches Flat-Panel setzt die Belichtung je Filter; der Offset passt jetzt zu *dieser* Zeit — ein Dark-Flat des Filters, sonst ein Dark innerhalb von 20 % seiner Flat-Belichtung, sonst der Bias. Bisher galt ein Offset für den ganzen Lauf, und zwei Filter mit verschiedenen Flat-Zeiten ließen ihn für **alle** auf den synthetischen Offset zurückfallen.
- **Das Kalibrierungs-Panel zeigt diese Entscheidung vorab**: pro Filter, wie viele Flats bei welcher Belichtung und womit sie offset-korrigiert werden. Ein Filter, den die Library nicht bedienen kann, wird benannt.
- **„Match flats to the same night" baut ein Master-Flat pro Nacht.** Bisher verwarf die Option nur Flats aus Nächten ohne Lights — was nichts ändert, wenn jede Nacht beides hat, und genau das ist der Normalfall bei einem automatischen Panel. Jetzt bekommt jede Nacht mit Flats *und* Lights ihr eigenes Master, die Lights dieser Nacht werden dadurch geteilt, und die kalibrierten Nächte werden vor der Registrierung wieder zusammengeführt — der Filter endet weiterhin als ein Master.
- **Eine Nacht ohne eigene Flats wird benannt, nicht geschluckt.** Sie fällt auf ein gepooltes Master zurück, und Log, Kalibrierungs-Panel und `output.md` sagen, welche Nacht und warum.
- **Die Übereinstimmungsprüfung misst weiter, wenn die Option an ist.** Die Zahl zeigt, dass die Aufteilung ihren zusätzlichen Stack wert ist; sie ist nur keine Warnung mehr. Und wenn die Option an ist, aber nicht helfen kann — nur eine der aufgenommenen Nächte hat eigene Flats — sagt sie das, statt zum Einschalten von etwas zu raten, das schon an ist.
- **Der Report nennt, welche Dimension einen Kanal geteilt hat** — Belichtungen, Nächte oder beides — und listet das Master-Flat jeder Nacht.

## Was in 1.5.0 neu war

- **Elf Paletten mehr** — die Schmalband-Zuordnungen HSO, HOS, OSS, OHH, OSH, OHS und HSS sowie die gewichteten Mischungen Realistic1 und Realistic2. Eine Tabelle steuert Zuordnung, Dropdown, Kanalmeldungen, SPCC-Wellenlängen und dieses Handbuch — auseinanderlaufen können sie damit nicht. Siehe §9.
- **Die dynamischen Paletten fehlen bewusst**, und §9 sagt warum: ihr Blendfaktor `t^(1-t)` fällt auf linearen Daten in sich zusammen. Dieselbe Rechnung steht jetzt für den Ha→Rot-Regler, der bei linearen Helligkeiten einen Anteil Ha addiert und sonst nichts.
- **Das Komposit wird im Speicher zusammengesetzt**, `rgbcomp` ist Rückfallebene — damit entfällt die Umgehung für seinen Umgang mit Leerzeichen in Pfaden. Für die Luminanzübertragung von *Quick linear LRGB* bleibt es der einzige Weg. Der Report nennt den tatsächlich gelaufenen.
- **Optionale synthetische Luminanz** für Schmalbandnächte: die Emissionslinien-Master gemittelt zu `masters/TARGET_SynthL.fit`, bewusst nicht ins Farbbild kombiniert.
- **Ein Filter mit gemischten Belichtungszeiten wird in Teilen kalibriert** — jede Belichtung mit ihrem eigenen Dark, vor der Registrierung wieder zusammengeführt. Ein Dark entfernt nur das thermische Signal seiner eigenen Belichtungszeit.
- **Der Name des Vollformat-Masters trägt das Rezept**: `M16_HA_29x300s_G100_-10C_fullframe.fit`, mit der Frame-Zahl, die die Registrierung überlebt hat.
- **Die Ausrichtungsqualität wird berichtet.** Wie viele Sternpaare jeder Kanal getroffen hat, wird aus Sirils Log gelesen; ein Kanal weit unter seinen Geschwistern wird benannt.
- **Kalibrierungsmaster werden nach Bedarf gebaut**, die Kamera gehört zum Zuordnungsschlüssel, ein Dark innerhalb von 5 % der Belichtungszeit wird verwendet und benannt, und ein gewöhnliches DARK mit der Flat-Belichtung wird als deren Offset akzeptiert.
- **Die integrierte Frame-Zahl wird gemessen**, zurückgelesen aus Sirils eigenen Registrierungsdaten — was nebenbei aufdeckte, dass die Qualitätsfilter doppelt abgezogen wurden. Der Report bekommt eine gemessene Tabelle mit FWHM, Rundheit und Sternzahl.
- **Zwischendateien werden generationsweise freigegeben**, der Spitzenbedarf bleibt bei etwa zwei statt vier Generationen.
- **Über Nächte gepoolte Flats werden vor dem Kombinieren gegeneinander geprüft.**
- **Eine sirilpy-Untergrenze und ein Fähigkeitsbericht.** Das Skript startet nicht mehr unterhalb von sirilpy 1.0.0 (was Siril 1.4 mitliefert) und sagt das in einem Satz; oberhalb benennt es jeden optionalen Aufruf, den dieses Modul nicht hat — beim Start und in `output.md` — samt seiner Folge.
- **Die SPCC-Namensfelder vervollständigen beim Tippen**, aus Sirils eigener Datenbank.

## Was in 1.4.0 neu war

- **Stack only the filters this palette uses** (standardmäßig aus) — halbiert einen typischen Lauf und hält vor allem die kanalübergreifende Ausrichtungsreferenz unter den Kanälen, die im Bild landen. Die Messwerte stehen in §9.
- **Der SPCC-Sensor geht auch im Narrowband-Modus mit.** `-narrowband` lässt Siril nur die *Filter*-Argumente ignorieren; ihn wegzulassen scheiterte nie, es nahm still, was der SPCC-Dialog zuletzt enthielt.
- **Schmalband-Normalisierung und SPCC** werden markiert, wenn beide aktiv sind — und die empfohlene Kombination wird als solche erkannt, statt als Mangel gemeldet zu werden.
- **Registrierungsfehler werden diagnostiziert, nicht geraten.** `register -2pass` und `seqapplyreg` werden getrennt behandelt, und Optionen, die die Rückfallebene nicht einhalten konnte, werden pro Kanal festgehalten.
- **Die volle Master-Wiederverwendung wird verweigert, wenn die ausgerichteten Master nicht alle dieselbe Größe haben** — was nach einem Palette-only-Lauf vorkommt.
- **Eine lange Reihe von Berichtskorrekturen** — ein Lauf ohne Komposit liest sich nicht mehr, als hätte er eines, eine übersprungene Kalibrierung heißt nicht mehr *kalibriert*, und es wird nie zu einer Option geraten, die nicht die Ursache war.

---

## Credits

**Entwickelt von** Sven Ramuschkat
**Website:** [www.svenesis.org](https://www.svenesis.org)
**GitHub:** [github.com/sramuschkat/Siril-Scripts](https://github.com/sramuschkat/Siril-Scripts)
**Lizenz:** GPL-3.0-or-later

Teil der **Svenesis Siril Scripts**-Sammlung, zu der außerdem gehören:
- Svenesis Gradient Analyzer
- Svenesis Blink Comparator
- Svenesis Annotate Image
- Svenesis Image Advisor
- Svenesis Multiple Histogram Viewer
- Svenesis Satellite Trail Cleaner
- Svenesis Script Security Scanner

---

*Wenn dir dieses Werkzeug nützt, unterstütze die Entwicklung gern über [Buy me a Coffee](https://buymeacoffee.com/svenesis).*
