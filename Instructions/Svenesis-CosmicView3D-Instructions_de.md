# Svenesis CosmicView 3D — Benutzeranleitung

**Version 1.0.0** | Siril-Python-Skript zur Visualisierung, wohin Ihr Foto im Universum zeigt

> *Ihr Foto ist nicht einfach irgendwo. Es ist ein Fenster in eine ganz bestimmte Richtung des Universums — und jetzt können Sie genau sehen, wohin. CosmicView 3D setzt die Erde in den Orion-Arm, hängt Ihr plate-gelöstes Bild entlang seiner echten Sichtlinie auf und lässt Sie den Weg des Lichts von der Erde bis zum Ziel abfliegen.*

---

## Inhaltsverzeichnis

1. [Was ist CosmicView 3D?](#1-was-ist-cosmicview-3d)
2. [Hintergrundwissen für Einsteiger](#2-hintergrundwissen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
4. [Erste Schritte](#4-erste-schritte)
5. [Die Benutzeroberfläche](#5-die-benutzeroberfläche)
6. [Ansichtsmodi — Galaktisch vs. Kosmisch](#6-ansichtsmodi--galaktisch-vs-kosmisch)
7. [Ansichtsstile: Story vs. Explorer](#7-ansichtsstile-story-vs-explorer)
8. [Die Story-Karte](#8-die-story-karte)
9. [Reise-Modus & die Eröffnungs-Rückfahrt](#9-reise-modus--die-eröffnungs-rückfahrt)
10. [Navigation in der 3D-Szene](#10-navigation-in-der-3d-szene)
11. [Die Szene lesen — Was jedes Element bedeutet](#11-die-szene-lesen--was-jedes-element-bedeutet)
12. [Entfernungsauflösung — Woher die Zahlen kommen](#12-entfernungsauflösung--woher-die-zahlen-kommen)
13. [Der Entfernungsmetrik-Umschalter](#13-der-entfernungsmetrik-umschalter)
14. [Die Zielauswahl](#14-die-zielauswahl)
15. [Export (HTML / PNG / CSV)](#15-export-html--png--csv)
16. [Tastaturkürzel](#16-tastaturkürzel)
17. [Tipps & Empfehlungen](#17-tipps--empfehlungen)
18. [Fehlerbehebung](#18-fehlerbehebung)
19. [FAQ](#19-faq)
20. [Wissenschaftlicher Hintergrund & Genauigkeit](#20-wissenschaftlicher-hintergrund--genauigkeit)

---

## 1. Was ist CosmicView 3D?

**Svenesis CosmicView 3D** ist ein Siril-Python-Skript, das eine Frage beantwortet, die kein anderes Astrofotografie-Werkzeug beantwortet:

> *„Mein Foto ist nicht einfach irgendwo — es ist ein Fenster in eine ganz bestimmte Richtung des Universums. Wohin genau?"*

Es liest Ihr aktuell geladenes, **plate-gelöstes** Bild aus Siril, identifiziert das astronomische Hauptobjekt über SIMBAD und rendert eine interaktive 3D-Szene, in der:

- **die Erde im Orion-Arm** der Milchstraße sitzt, an ihrer korrekten Position ~26.000 Lichtjahre vom Galaktischen Zentrum entfernt.
- **Ihr Astrofoto** als texturiertes Rechteck im 3D-Raum platziert wird und genau in die Blickrichtung zeigt, aus der es entstand.
- ein **Sichtstrahl** von der Erde zum Foto verläuft und buchstäblich zeigt, wohin Ihr Teleskop gerichtet war.
- die **Entfernung des Ziels greifbar** wird — durch eine Story-Karte, Skalenringe und einen filmischen **Reise**-Flug von der Erde bis zum Objekt.

Während das Schwesterwerkzeug **CosmicDepth 3D** die *Tiefe* aller Objekte *innerhalb* eines Fotos zeigt, zoomt CosmicView 3D heraus und zeigt, *wo dieses ganze Foto* in der Struktur der Galaxie und des Universums sitzt.

---

## 2. Hintergrundwissen für Einsteiger

### Warum „3D" aus einem 2D-Foto?

Ein Foto ist eine flache Projektion: Alles darin liegt in einer Richtung von der Erde aus, aber in völlig unterschiedlichen Entfernungen. Ein einzelnes plate-gelöstes Bild liefert uns zwei entscheidende Fakten — die **Richtung**, in die es zeigt (präzise aus der WCS-Lösung), und die **Entfernung** zum Hauptobjekt (aus SIMBAD). Mit beidem können wir das ganze Foto an seiner wahren Position in einem 3D-Modell der Galaxie platzieren.

### Was bedeutet „plate-gelöst"?

Plate-Solving vergleicht das Sternmuster in Ihrem Bild mit einem Katalog und schreibt eine **WCS**-Lösung (World Coordinate System) in die Datei. Damit kann das Skript jedes Pixel in eine präzise Himmelskoordinate (Rektaszension / Deklination) umrechnen. CosmicView 3D **benötigt** ein plate-gelöstes Bild — ohne WCS kann es nicht wissen, wohin Ihr Foto zeigt.

In Siril: **Werkzeuge → Astrometrie → Bild-Plate-Solver…**

### Galaktische vs. kosmische Skala

Die Milchstraße ist ~100.000 Lichtjahre groß. Die nächste große Galaxie, Andromeda, ist 2,5 *Millionen* Lichtjahre entfernt. Ferne Galaxien sind *Milliarden* Lichtjahre weit. Kein einzelnes lineares Lineal kann einen 500 Lichtjahre großen Nebel und einen 2 Milliarden Lichtjahre entfernten Quasar im selben Bild zeigen. CosmicView 3D löst das mit zwei Modi und einer logarithmisch komprimierten kosmischen Skala (siehe §6).

### Was ist der Orion-Arm?

Unsere Sonne sitzt in einem kleineren Spiralarm namens **Orion-Arm** (oder Orion-Sporn), zwischen den größeren Sagittarius- und Perseus-Armen. CosmicView 3D hebt ihn hervor, weil das *Ihre* Adresse in der Galaxie ist — jedes Foto, das Sie machen, entsteht von hier aus.

---

## 3. Voraussetzungen & Installation

### Anforderungen

- **Siril 1.4+** mit Python-Skript-Unterstützung
- **sirilpy** (in Siril enthalten)
- Ein **plate-gelöstes** Bild in Siril geladen
- **Internetverbindung** für die erste SIMBAD-Abfrage eines Ziels (Ergebnisse werden danach zwischengespeichert)
- Python-Pakete, beim ersten Start automatisch installiert über `s.ensure_installed`:
  `numpy`, `PyQt6`, `matplotlib`, `astropy`, `astroquery`, `plotly`, `Pillow`, `kaleido`, `requests`
- **PyQt6-WebEngine** — für die interaktive 3D-Ansicht im Fenster. Wird beim Start geprüft; fehlt es oder passt es nicht zur Siril-eigenen PyQt6-Version, greift das Skript auf eine statische matplotlib-Ansicht zurück (ohne Live-Rotation).

### Installation

1. Legen Sie `Svenesis-CosmicView3D.py` in einen Ordner namens **Utility** in einem von Sirils Skript-Speicherverzeichnissen ab.
2. Starten Sie Siril neu (oder aktualisieren Sie das Skript-Menü).
3. Das Skript erscheint unter **Skripte** in Sirils Menü.

Der erste Start installiert fehlende Python-Pakete — das kann eine Minute dauern. Nachfolgende Starts sind schnell.

---

## 4. Erste Schritte

### Schritt 1 — Bild laden und plate-lösen

Öffnen Sie ein beliebiges Deep-Sky-Bild in Siril und plate-lösen Sie es (**Werkzeuge → Astrometrie → Bild-Plate-Solver…**). Ein Motiv mit einem einzelnen Objekt — eine Galaxie, ein Nebel oder ein Sternhaufen — funktioniert am besten.

### Schritt 2 — Skript ausführen

**Verarbeitung → Skripte → Svenesis CosmicView 3D**. Das Fenster öffnet sich maximiert.

### Schritt 3 — Rendern

Klicken Sie auf **3D-Karte rendern** (oder drücken Sie **F5**). Das Skript:

1. Liest das Bild und seine WCS-Lösung.
2. Fragt SIMBAD nach dem Hauptobjekt und nahen Kandidaten ab.
3. Öffnet die **Zielauswahl** — bestätigen Sie das automatisch erkannte Motiv oder wählen Sie einen anderen Kandidaten.
4. Ermittelt die Entfernung und baut die Szene auf.

### Schritt 4 — Die Enthüllung betrachten

Die Ansicht öffnet sich aus **Erdperspektive** — der Himmel, wie Sie ihn tatsächlich fotografiert haben — und fährt dann zurück, um die vollständige galaktische Karte zu enthüllen (die *Eröffnungs-Rückfahrt*). Eine **Story-Karte** blendet sich über der Szene ein und erzählt Ihnen, wohin Sie gezielt haben und wie alt das Licht ist.

### Schritt 5 — Die Reise antreten

Drücken Sie die Schaltfläche **🚀 Reise** (oder die Taste **J**), um den Weg des Lichts von der Erde bis zu Ihrem Ziel abzufliegen — mit einem Live-Zähler für Entfernung und Alter des Lichts.

### Schritt 6 — Erkunden und exportieren

Ziehen zum Drehen, Mausrad zum Zoomen, über jeden Marker fahren für Details. Mit **HTML / PNG / CSV exportieren** teilen oder archivieren.

---

## 5. Die Benutzeroberfläche

### Linkes Panel (Steuerung)

- **Ansichtsmodus** — Auto (Standard) / Galaktisch / Kosmisch überschreiben.
- **Szenenelemente:**
  - **Ansichtsstil** — Story (Standard) vs. Explorer (siehe §7).
  - **Eröffnungs-Rückfahrt-Animation** — an/aus (spielt einmal pro Ziel).
  - **Spiralarme**, **Scheibensterne**, **Nachbargalaxien (kosmischer Modus)**, **Fotorechteck + Sichtstrahl**.
  - **Fotoauflösung (px)** — Texturdetail des Fotorechtecks (im kosmischen Modus aus Performance-Gründen automatisch begrenzt).
  - **Entfernungsmetrik (kosmischer Modus)** — Lichtlaufzeit / Mitbewegt / Winkeldurchmesser (siehe §13).
- **Hauptobjekt** — Name, Typ, Entfernung des identifizierten Motivs.
- **Datenquellen** — SIMBAD-Online-Schalter + Cache-Löschen-Schaltfläche.
- **Ausgabe** — Basis-Dateiname für Exporte und PNG-DPI.
- **Aktionen** — Rendern, Exporte, Hilfe.

### Rechtes Panel (Reiter)

- **3D-Karte** — die interaktive Szene, mit der Kamera-Schaltflächenleiste darunter (Trackball, Zoom, Voreinstellungen, 🚀 Reise, Rotation).
- **Info** — eine vollständige Szenenübersicht: die Story-Karte, Objektdaten und die Milchstraßen-Modellparameter.
- **Log** — ein Ereignisprotokoll mit Zeitstempeln (Renderings, SIMBAD-Abfragen, Kameraaktionen) — gefahrlos in einen Fehlerbericht einfügbar.

---

## 6. Ansichtsmodi — Galaktisch vs. Kosmisch

Der Modus wird automatisch aus Entfernung und SIMBAD-Typ des Ziels gewählt. Sie können ihn jederzeit überschreiben.

### Galaktischer Modus (< 150.000 Lj)

- **Skala:** linear, 1 Szeneneinheit = 1.000 Lichtjahre.
- **Zeigt:** die fünf Spiralarme, Scheibensterne, den zentralen Bulge, Sgr A* im Galaktischen Zentrum, die Erde im Orion-Arm mit ihrem Bewegungspfeil, Entfernungsringe und (bei Zielen innerhalb der Galaxie) die Sternbild-Strichfigur und die Arm-Zugehörigkeit.
- **Beantwortet:** *„Wohin innerhalb unserer Galaxie blicke ich?"*

### Kosmischer Modus (≥ 150.000 Lj)

- **Skala:** linear bis 1 Mio. Lj (1 Einheit = 100.000 Lj), dann **logarithmisch komprimiert** darüber hinaus, sodass ein 2-Millionen-Lj- und ein 2-Milliarden-Lj-Objekt beide auf den Bildschirm passen. Der Übergang ist durch einen blassen orangefarbenen Ring bei **1 Mio. Lj** markiert.
- **Zeigt:** Nachbargalaxien (M31, M33, LMC, SMC, …) und im Explorer-Stil: Galaxienhaufen-Hüllen, kosmische Wahrzeichen und die Grenze des beobachtbaren Universums (CMB).
- **Beantwortet:** *„Wie winzig ist die Milchstraße, und wo sitzt mein Ziel unter den Galaxien?"*

### Wie der Modus entschieden wird

1. Ist SIMBADs Objekttyp extragalaktisch (Galaxie, Quasar, AGN, …) → **Kosmisch**.
2. Ist es ein Typ innerhalb der Galaxie (Nebel, Sternhaufen, Stern, …) → **Galaktisch**.
3. Sonst nach Entfernung: ≥ 150.000 Lj → **Kosmisch**, sonst **Galaktisch**.

---

## 7. Ansichtsstile: Story vs. Explorer

Ein einzelner Schalter oben in den Szenenelementen steuert, wie viel die Szene zeigt.

| | **Story** (Standard) | **Explorer** |
|---|---|---|
| Ziel | Aufgeräumt, filmisch, lesbar | Vollständige Referenzkarte |
| Zeigt | Erde, Sichtstrahl, Foto, Ziel, Galaxienstruktur, Entfernungsringe | Alles aus Story **plus** alle Overlays |
| Zusätzliche Overlays | — | Wahrzeichen-Kataloge, Galaxienhaufen-Hüllen, CMB-Grenze, Lokale-Blase- / Lokale-Gruppe-Kugeln |

**Story** behält nur den erzählerischen Faden — die Reise von Ihrem Garten zum Ziel. **Explorer** macht aus der Szene einen vollständigen Atlas der umgebenden Struktur. Innerhalb von Explorer lässt sich jedes Overlay einzeln über die Diagramm-Legende ein-/ausblenden.

Ihr gewählter Stil bleibt über Sitzungen hinweg erhalten.

---

## 8. Die Story-Karte

Die menschlichste Funktion. Nach jedem Rendern erzählt Ihnen ein kurzer, automatisch erzeugter Absatz in einfacher Sprache:

- **Wohin Sie gezielt haben** — galaktische Länge und ob Sie in die Scheibe hinein oder zum Halo hinauf geblickt haben.
- **Wie alt das Licht ist** — verankert an der Erdgeschichte: *„…vor etwa 38,7 Millionen Jahren, als die Vorfahren der Wale noch an Land gingen."*
- **In welchem Arm** das Ziel sitzt (bei Objekten innerhalb der Galaxie).
- **Ein Größenvergleich** — *„Wäre die Milchstraße ein Essteller (25 cm), läge Ihr Ziel als weiterer Teller etwa 97 Meter die Straße hinunter."*

Die Story erscheint an drei Stellen: als schließbare **Einblendung** über der 3D-Ansicht (verschwindet nach ~18 s, zum Schließen anklicken), dauerhaft im **Info-Reiter**, und sie ist in **CSV**-Exporten enthalten und als Bildunterschrift in **PNG**-Exporte eingebrannt.

Die erdgeschichtlichen Anker werden ehrlich gewählt: Ist keine historische Epoche wirklich nahe (innerhalb eines Faktors von ~2,5 des Lichtalters), wird der Vergleich einfach weggelassen, statt einen falschen zu erzwingen.

---

## 9. Reise-Modus & die Eröffnungs-Rückfahrt

### Die Eröffnungs-Rückfahrt

Das erste Rendern eines Ziels startet die Kamera **aus Erdperspektive** — den Blick entlang Ihrer Sichtlinie gerichtet, das Foto vor sich, der Himmel, wie Sie ihn gesehen haben. Nach einem Moment fährt sie sanft zurück und enthüllt die vollständige 3D-Karte. Das ist die „Powers-of-Ten"-Bewegung: Sie verankert die abstrakte Karte in Ihrem tatsächlichen Standpunkt.

Sie spielt **einmal pro Ziel** (erneutes Rendern desselben Objekts überspringt sie) und kann in den Szenenelementen deaktiviert werden. Jeder Klick, jedes Scrollen oder jeder Tastendruck bricht sie ab.

### Reise-Modus

Drücken Sie **🚀 Reise** (oder **J**), um die Kamera von der Erde entlang des Sichtstrahls bis zu Ihrem Ziel zu fliegen — eine etwa 11-sekündige filmische Verfolgungsfahrt. Ein Live-HUD zeigt:

> **38,7 Mio. Lj von der Erde**
> *das Licht in Ihrem Foto passierte diesen Punkt vor 38,7 Millionen Jahren*
> ✦ *verlasse die Lokale Gruppe*

Wegpunkt-Ansagen erscheinen beim Überqueren erkennbarer Grenzen — Verlassen der Lokalen Blase, Verlassen der Milchstraßenscheibe, Passieren der Andromeda-Entfernung, Überqueren der 1-Mio.-Lj-Skalengrenze, Verlassen der Lokalen Gruppe, Passieren von Virgo. Nur die Wegpunkte, die tatsächlich auf der Route zu Ihrem Ziel liegen, erscheinen.

Da sich die Kamera mit konstanter Geschwindigkeit durch *Szenen*-Einheiten bewegt, **beschleunigt** der Lichtjahr-Zähler sichtbar hinter der 1-Mio.-Lj-Grenze — Sie *spüren* die logarithmische Kompression, statt nur darüber zu lesen.

Jede bewusste Eingabe (Klick, Scrollen, Taste) bricht die Reise ab. Drücken Sie danach **R**, um nach Hause zurückzufliegen.

**Hinweis:** Die Reise-Schaltfläche ist ausgegraut, wenn dem Rendering ein projiziertes Foto oder eine ermittelte Entfernung fehlt — beides wird für den Flug benötigt.

---

## 10. Navigation in der 3D-Szene

### Maus

- **Ziehen** — Kamera umkreisen.
- **Mausrad** — zoomen.
- **Über** einen Marker fahren — seine Details lesen.
- **Doppelklick** auf einen Spiralarm in der Legende — die Kamera zu diesem Arm fliegen.

### Kamera-Schaltflächenleiste (unter der 3D-Ansicht)

| Bedienelement | Aktion |
|---|---|
| **Trackball** | Ziehen zum Umkreisen (Diagonalen möglich); Rad zoomt. |
| **+ / −** | Hinein- / Herauszoomen. Jenseits der Kameragrenze setzt der **Lupen-Modus** ein — die Ansicht vergrößert grenzenlos um das Foto herum; entferntere Inhalte fallen aus dem Fenster. |
| **⟲** | Kamera und Lupen-Zoom zurücksetzen. |
| **Erdperspektive** | Zur Erdperspektive fliegen, Blick entlang der Sichtlinie. Der Sichtstrahl pulsiert bei Ankunft. |
| **Oben / Seite / Iso** | Orthogonale Voreinstellungen; Iso ist die Standard-3/4-Perspektive. |
| **🚀 Reise** | Den Weg des Lichts von der Erde zum Ziel fliegen (§9). |
| **Rotation** | Langsame automatische Drehung ein-/ausschalten. |

### Rettungstasten

Szene verloren? Drücken Sie **R**, **Home** oder **Escape** zum Zurücksetzen. Die automatische Drehung setzt nach 10 Sekunden Inaktivität als dezenter Hinweis ein; jede Eingabe bricht sie ab.

---

## 11. Die Szene lesen — Was jedes Element bedeutet

### Immer vorhanden

- **Erde** — ein „Sie sind hier"-Fadenkreuz im Ursprung (0, 0, 0). Fahren Sie darüber für Ihre galaktischen Koordinaten und die Entfernung zum Galaktischen Zentrum.
- **Ihr Foto** — ein texturiertes Rechteck in der Entfernung des Ziels, ausgerichtet entlang der wahren Blickrichtung.
- **Sichtstrahl** — die gepunktete bernsteinfarbene Linie von der Erde zur Fotomitte: buchstäblich, wohin Sie gezielt haben.
- **Entfernungsringe** — gepunktete Kreise, die die Skala markieren. Sie verblassen mit der Entfernung (näher = heller). Flach wie ein Radarschirm gezeichnet — **außer** dem Ring, der der Entfernung Ihres Ziels am nächsten ist, der zu einer Kugelschale wird: *„Ihr Foto sitzt in dieser Tiefe."*

### Galaktischer Modus

- **Spiralarme** — fünf logarithmische Spiralkurven (Norma, Scutum-Centaurus, Sagittarius, Orion, Perseus). Sie verblassen, wenn Sie nah an ein nahes Ziel heranzoomen, um die Ansicht nicht zu überladen.
- **Scheibensterne + Bulge** — ein Eindruck der Galaxienform.
- **Sgr A*** — das Galaktische Zentrum, ein warmer Diamant bei ~26.000 Lj entlang +X.
- **Erdbewegungspfeil** — ein kleiner cyanfarbener Pfeil, der unsere ~220 km/s-Bewegung um die Galaxie zeigt.
- **Sternbild-Strichfigur** — das IAU-Sternbild, das Ihr Ziel enthält, in der Entfernung des Ziels gezeichnet.
- **Lokale Blase** (Explorer, Ziele ≤ 2.000 Lj) — der von Supernovae ausgehöhlte Hohlraum um das Sonnensystem.
- **Galaktische Wahrzeichen** (Explorer) — ein Katalog berühmter Objekte (Plejaden, M42, M13, Cirrusnebel, …), nach Typ gruppiert.

### Kosmischer Modus

- **Nachbargalaxien** — M31, M33, LMC, SMC, M81/82, M51, Centaurus A und mehr, mit ausführlichen Hover-Beschreibungen.
- **1-Mio.-Lj-Skalengrenze** — der orangefarbene Ring, der markiert, wo die lineare Skala logarithmisch wird.
- **Galaxienhaufen** (Explorer) — durchscheinende Hüllen für Virgo, Coma, Perseus, Shapley und andere.
- **Kosmische Wahrzeichen** (Explorer) — berühmte extragalaktische Objekte (Sombrero, Cartwheel, 3C 273, …).
- **CMB-Grenze** (Explorer) — ein blasser Gitterglobus bei 13,8 Milliarden Lichtjahren: der Rand des beobachtbaren Universums.

### Hintergrund-Tiefenstiele

Findet SIMBAD Objekte *hinter* Ihrem Ziel innerhalb desselben Fotos, werden sie in ihrer wahren Entfernung gezeichnet und durch eine dünne Linie mit ihrer genauen Pixelposition auf Ihrem Foto verbunden — so sehen Sie, was sonst noch in Ihrem Bild ist und wie weit entfernt.

---

## 12. Entfernungsauflösung — Woher die Zahlen kommen

Die Entfernung zu Ihrem Ziel wird über eine Prioritätskette ermittelt — die erste Quelle, die einen Wert liefert, gewinnt:

1. **Lokaler Cache** — ein 90-Tage-Speicher in `~/.config/siril/svenesis_cosmicview_cache.json`. Erneutes Rendern eines bekannten Ziels ist sofort und offline möglich.
2. **SIMBAD `mesDistance`** — direkte Entfernungsmessungen aus der Fachliteratur (die maßgeblichste Quelle). Existieren mehrere Messungen, wird die mit der kleinsten Unsicherheit (in Lichtjahren verglichen) gewählt.
3. **Rotverschiebung → Entfernung** — für ferne Galaxien, umgerechnet in Lichtlaufzeit-Entfernung über `astropy.cosmology.Planck18` (H₀ ≈ 67,4 km/s/Mpc). Eine lineare Hubble-Näherung wird nur verwendet, wenn das Kosmologie-Paket nicht verfügbar ist.
4. **Parallaxe** — für nahe Sterne, wenn zuverlässig. Eine Konsistenzprüfung verwirft SIMBADs Rausch-Parallaxen bei extragalaktischen Objekten (eine Galaxie mit einer falschen Sub-Millibogensekunden-Parallaxe wird durch ihre Rotverschiebung entlarvt).
5. **Typ-basierter Median** — eine Notfall-Schätzung aus dem SIMBAD-Typ des Objekts, **klar als Schätzung gekennzeichnet** im Info-Reiter und CSV-Export.

Kandidatenlisten aus der Umkreissuche werden separat 7 Tage lang zwischengespeichert, sodass erneutes Rendern eines bekannten Feldes gar kein Netzwerk benötigt. Eine SIMBAD-Zustandsprüfung verkürzt die Abfrage-Zeitlimits bei Dienstausfällen, und alle Netzwerkaufrufe laufen außerhalb des UI-Threads, sodass das Fenster nie einfriert.

---

## 13. Der Entfernungsmetrik-Umschalter

Im kosmischen Modus ist „Entfernung" keine einzelne Zahl — bei hoher Rotverschiebung weichen verschiedene Definitionen deutlich voneinander ab. Das Szenenelemente-Panel bietet drei:

| Metrik | Bedeutung | Am besten für |
|---|---|---|
| **Lichtlaufzeit** (Standard) | c × Rückblickzeit — wie weit das Licht gereist ist, um uns zu erreichen. Entspricht SIMBADs aus der Rotverschiebung abgeleiteten Entfernungen. | *„Wie alt ist dieses Bild?"* |
| **Mitbewegt** | Die Eigenentfernung des Objekts *jetzt*, unter Berücksichtigung der kosmischen Expansion seit dem Aussenden des Lichts. Immer ≥ Lichtlaufzeit. | *„Wo ist es jetzt im Universum?"* |
| **Winkeldurchmesser** | Mitbewegt ÷ (1+z) — die Entfernung, die die scheinbare Winkelgröße bestimmt. | *„Warum wirken Objekte hoher Rotverschiebung täuschend nah?"* |

Das Umschalten der Metrik **reorganisiert die 3D-Szene physisch** — die Position jedes Objekts aktualisiert sich. Die HUD-Beschriftung unten zeigt stets die aktive Metrik. Die zugrunde liegende Kosmologie ist `astropy.cosmology.Planck18`.

Bei den geringen Rotverschiebungen typischer Amateurziele sind die drei Metriken nahezu identisch; der Unterschied wird erst bei fernen Quasaren und im Deep Field dramatisch.

---

## 14. Die Zielauswahl

Nach der SIMBAD-Umkreissuche listet ein Dialog jedes im Feld Ihres Bildes gefundene Kandidatenobjekt auf, mit:

- **Name**, **Typ**, **V-Helligkeit**
- **Entfernung** mit Quellenhinweis: `(z)` Rotverschiebung, `(π)` Parallaxe, `~` Typ-Schätzung
- **Größe im Foto** und **Abstand vom Zentrum**

Das automatisch erkannte Hauptmotiv ist vorausgewählt, aber Sie können jeden Kandidaten wählen — nützlich bei Weitfeldern mit mehreren hellen Objekten oder wenn Sie eine bestimmte Galaxie in einer Gruppe fotografiert haben. Sie können die vollständige Kandidatenliste auch als JSON exportieren.

---

## 15. Export (HTML / PNG / CSV)

| Format | Inhalt |
|---|---|
| **HTML** | Eine eigenständige, voll interaktive Plotly-Szene — inklusive der Story-Einblendung und des Reise-Modus (Taste **J**). Selbstständig (Plotly inline eingebettet), funktioniert offline, öffnet in jedem Browser. |
| **PNG** | Eine Momentaufnahme Ihres aktuellen Kamerawinkels, mit dem Story-Text als Bildunterschrift unter dem Bild. Nach Möglichkeit aus der Live-Ansicht erfasst; greift auf kaleido / matplotlib zurück. |
| **CSV** | Vollständige Szenen-Metadaten: Objektname, Typ, Entfernung, galaktische Koordinaten, Blickrichtung, Rotverschiebung, Rückblickzeit, Entfernungsmetrik, verwendete Kosmologie, Arm-Zugehörigkeit, der Story-Text und die vier Ecken des Fotorechtecks in 3D-Einheiten. |

Zwei Komfort-Schaltflächen — **Ausgabeordner öffnen** und **Exportiertes HTML öffnen** — erscheinen nach einem Export.

---

## 16. Tastaturkürzel

| Taste | Aktion |
|---|---|
| **F5** | 3D-Karte rendern |
| **R** / **Home** / **Escape** | Kamera zurücksetzen (und Lupen-Zoom) |
| **J** | Reise starten (funktioniert auch im exportierten HTML) |
| **Doppelklick** auf einen Arm in der Legende | Kamera zu diesem Spiralarm fliegen |

---

## 17. Tipps & Empfehlungen

- **Szene ruckelt?** Verringern Sie die **Fotoauflösung** in den Szenenelementen — das texturierte Foto ist der größte einzelne GPU-Aufwand. 240 px rendern deutlich schneller als 480 px bei nur geringem Qualitätsverlust (im kosmischen Modus automatisch begrenzt).
- **Szene zu voll?** Wechseln Sie zum **Story**-Ansichtsstil. Für feinere Kontrolle einzelne Overlays über die Diagramm-Legende umschalten (Klick zum Ausblenden, Doppelklick zum Isolieren).
- **Zoom wirkt begrenzt?** Drücken Sie weiter **+** — jenseits der Kameragrenze geht er in den **Lupen-Modus** über und taucht weiter zum Foto hinab. **R** bringt Sie zurück.
- **Beste Motive:** Ein einzelnes dominantes Objekt (Galaxie, Nebel, Sternhaufen) ergibt die sauberste Story. Sehr weite Felder mit vielen hellen Objekten funktionieren ebenfalls, aber Sie wählen das Motiv in der Zielauswahl.
- **Erneutes Rendern ist schnell:** Die Entfernungs- und Umkreissuche-Caches machen wiederholte Renderings desselben Ziels nahezu sofort und offline-fähig.
- **Lesen Sie die Story laut vor.** Sie ist als der Satz gedacht, den Sie als Screenshot festhalten und teilen.

---

## 18. Fehlerbehebung

**„Das Bild ist nicht plate-gelöst."**
CosmicView 3D benötigt eine WCS-Lösung. Zuerst plate-lösen: **Werkzeuge → Astrometrie → Bild-Plate-Solver…**

**SIMBAD ist langsam oder überschreitet das Zeitlimit.**
Der CDS-SIMBAD-Dienst hat gelegentlich Ausfälle. Das Skript protokolliert *SIMBAD tile timeout* und fährt mit dem Abgerufenen fort; die Zustandsprüfung verkürzt Zeitlimits automatisch. Renderings zwischengespeicherter Ziele bleiben schnell und offline.

**Die Reise-Schaltfläche ist ausgegraut.**
Sie benötigt sowohl ein projiziertes Fotorechteck als auch eine ermittelte Entfernung. Stellen Sie sicher, dass **Fotorechteck + Sichtstrahl** aktiviert ist und das Ziel eine bekannte Entfernung hat.

**Die 3D-Ansicht ist leer / statisch.**
`PyQt6-WebEngine` fehlt möglicherweise oder passt nicht zur PyQt6-Version von Siril. Das Skript greift auf ein statisches matplotlib-Bild zurück. Prüfen Sie den Log-Reiter auf die WebEngine-Statuszeile.

**Das Fotorechteck ist winzig oder unsichtbar.**
Sichtfelder von Astrofotos (typisch < 1°) projizieren auf ein Sub-Pixel-Rechteck bei galaktischer Skala, daher vergrößert das Skript es um seinen Mittelpunkt herum zur Sichtbarkeit — Ausrichtung und Seitenverhältnis bleiben erhalten. Ist es weiterhin schwer zu sehen, nutzen Sie die Voreinstellungen oder zoomen Sie hinein.

**Entfernungen wirken nach einem Update falsch.**
Zwischengespeicherte Entfernungen bleiben 90 Tage bestehen. Vermuten Sie einen veralteten Wert, verwenden Sie **Entfernungs-Cache leeren** im Datenquellen-Panel und rendern Sie neu.

---

## 19. FAQ

**F: Sind die Objektpositionen physikalisch korrekt?**
Die *Richtungen* sind exakt (aus Ihrem Plate-Solve und astropys Koordinatentransformationen). Die *Entfernungen* stammen aus der besten verfügbaren Quelle (Messung → Rotverschiebung → Parallaxe → Schätzung). Im kosmischen Modus werden Entfernungen jenseits von 1 Mio. Lj zur Darstellung logarithmisch komprimiert, sodass Bildschirmabstände nicht maßstabsgetreu sind — siehe §20.

**F: Ist die Umrechnung von Rotverschiebung zu Entfernung korrekt?**
Ja — sie verwendet die moderne Planck18-Kosmologie (Lichtlaufzeit-Entfernung), nicht die alte lineare Hubble-Näherung. Siehe §20.

**F: Kann ich das offline nutzen?**
Nach dem ersten Rendern eines Ziels ja — sowohl die Entfernung als auch die Kandidatenliste werden zwischengespeichert. Die interaktive Szene und alle Exporte funktionieren ohne Netzwerk.

**F: Warum ist meine Galaxie im „Kosmisch"-Modus, ein Nebel aber im „Galaktisch"?**
Der Modus folgt SIMBAD-Typ und Entfernung des Objekts. Galaxien und Quasare sind extragalaktisch (Kosmisch); Nebel, Sternhaufen und Sterne liegen innerhalb der Milchstraße (Galaktisch). Sie können dies jederzeit überschreiben.

**F: Was ist der Unterschied zu CosmicDepth 3D?**
CosmicDepth 3D zeigt die Tiefe *aller Objekte innerhalb eines Fotos*. CosmicView 3D zeigt, *wo dieses ganze Foto* in der Galaxie und im Universum sitzt, aus Sicht der Erde.

**F: Stellt die Reise eine echte Reisezeit dar?**
Nein — nichts reist schneller als Licht. Die Reise ist eine Visualisierung von *Entfernung und Alter des Lichts*. Der Zähler zeigt, wie weit jeder Punkt entfernt ist und vor wie langer Zeit das Licht in Ihrem Foto ihn passierte.

---

## 20. Wissenschaftlicher Hintergrund & Genauigkeit

### Was exakt ist

- **Himmelsrichtungen.** Rektaszension / Deklination stammen aus Ihrem Plate-Solve; die galaktische Koordinatentransformation nutzt astropy. Jedes Objekt liegt in genau der richtigen *Richtung* von der Erde aus.
- **Erdposition.** Platziert in der korrekten heliozentrischen Entfernung (~26.000 Lj) vom Galaktischen Zentrum, im Orion-Arm.
- **Kosmologie.** Rotverschiebung → Entfernung nutzt `astropy.cosmology.Planck18` (H₀ ≈ 67,4 km/s/Mpc, Ωm ≈ 0,315, ΩΛ ≈ 0,685) und berechnet die Lichtlaufzeit-Entfernung aus dem Rückblickzeit-Integral. Das ist bei moderater Rotverschiebung deutlich genauer als das lineare Hubble-Gesetz.

### Bewusste Näherungen (in der App offengelegt)

- **Log-Kompression jenseits 1 Mio. Lj.** Richtungen und radiale Reihenfolge sind exakt, aber Bildschirmabstände zwischen Objekten sind nicht proportional zur Realität. Markiert durch den 1-Mio.-Lj-Grenzring und die HUD-Beschriftung.
- **Vergrößerung des Fotorechtecks.** Mittelpunkt und Ausrichtung sind exakt; das Rechteck wird zur Sichtbarkeit vergrößert.
- **Spiralarme sind schematisch.** Sie nutzen ein einheitliches logarithmisches Spiralmodell (nach Hou & Han 2014), genau bis auf einige tausend Lichtjahre — die Arm-Zugehörigkeit ist daher *richtungsweisend*, nicht maßgeblich.
- **Sternbildfiguren** sitzen auf der Entfernungsschale des Ziels; die realen Sterne stehen in unterschiedlichen Entfernungen. Sie sind eine Himmelsform-Referenz.
- **Typ-Median-Entfernungen** können stark abweichen; sie sind stets als Schätzungen gekennzeichnet.

### Eine Anmerkung zur Ehrlichkeit

Wo das Werkzeug schätzt oder nähert, sagt es das — im Info-Reiter, im CSV-Export, in den Quellenhinweisen der Zielauswahl und über die Ehrlichkeitsschwelle der Story-Karte (die einen historischen Vergleich weglässt, statt einen falschen zu erzwingen). Das Ziel ist eine schöne Visualisierung, die nie stillschweigend in die Irre führt.

### Referenz

Spiralarm-Modell nach Hou, L. G. & Han, J. L. 2014, *The observed spiral structure of the Milky Way*, Astronomy & Astrophysics, 569, A125. Kosmologie: Planck Collaboration 2018 (Planck18), über `astropy.cosmology`.

---

*Erstellt von [Svenesis](https://www.svenesis.org). [Spendieren Sie mir einen Kaffee ☕](https://buymeacoffee.com/sramuschkat), wenn Ihnen das geholfen hat zu sehen, wo Ihre Fotos im Universum leben.*
