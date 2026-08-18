# Svenesis LightCurve — Anleitung

**Version 1.0.0** | Siril Python-Skript für Exoplaneten-Transitphotometrie

> *Ein Ordner Subs hinein, eine Lichtkurve heraus — und eine ehrliche Antwort auf die einzige Frage, die zählt: steckt da ein Transit drin?*

---

## Inhalt

1. [Was ist Svenesis LightCurve?](#1-was-ist-svenesis-lightcurve)
2. [Grundlagen für Einsteiger](#2-grundlagen-für-einsteiger)
3. [Voraussetzungen & Installation](#3-voraussetzungen--installation)
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
15. [Neu in 1.0.0](#15-neu-in-100)

---

## 1. Was ist Svenesis LightCurve?

Richte **Svenesis LightCurve** auf den Ordner mit den Subs einer Nacht auf einen Exoplaneten-Wirtsstern. Das Skript misst, wie sich dessen Helligkeit relativ zu anderen Sternen im selben Feld verändert hat, entfernt die systematischen Trends, die es verantworten kann, fittet einen Transit — und sagt dir, ob die Delle echt ist oder ob du eine Wolke ansiehst.

### Wer macht was

Die Arbeitsteilung ist bewusst gewählt und erklärt den größten Teil des Designs.

**Siril macht die Pixelarbeit.** `light_curve` ist Sirils eigene Aperturphotometrie — derselbe Code wie hinter dem Photometrie-Werkzeug. Er behandelt bereits den Himmels-Annulus, die FWHM-skalierten Ringradien, die Sättigungsprüfung und das Sternmatching pro Frame. Das in einem Skript nachzubauen ergäbe eine *zweite* Photometrie-Engine, die man mit der ersten synchron halten müsste — und die schlechter wäre.

**Dieses Skript macht das, wozu Siril keine Meinung hat:** welcher Stern das Ziel ist, gegen welche Sterne sich kalibrieren lohnt, wie man die Airmass-Rampe entfernt, ohne die Transittiefe mitzunehmen, wie man das Ereignis fittet — und vor allem, ob überhaupt etwas behauptet werden darf.

### Der Ablauf

| Schritt | Was passiert | Warum so |
|---|---|---|
| **Bereitstellen** | Subs werden nach `_lightcurve/` verlinkt | Kostet nichts; der Originalordner wird nie beschrieben |
| **Link** | Siril baut eine Sequenz | |
| **Registrieren** | `register -2pass` — nur Daten, **kein Resampling** | Interpolation korreliert Nachbarrauschen und verschiebt Fluss innerhalb der Apertur. Die Apertur folgt dem Stern über die Registrierungsdaten, die Pixel bleiben, wie der Sensor sie aufgezeichnet hat |
| **Erkennen** | Siril findet die Sterne, das Skript wählt Ziel + Vergleiche | |
| **Photometrie** | Sirils `light_curve` | |
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

**Kalibriere die Subs vorher.** Vor allem Flats: ein Stern, der über einen Staubschatten wandert, erzeugt einen langsamen Trend, der genau wie ein flacher Transit aussieht.

---

## 4. Erste Schritte

1. **Ordner wählen** — der Ordner mit den kalibrierten Subs. Zehn Frames sind das absolute Minimum, ein echter Transitlauf hat Hunderte.
2. **Zielstern** — für den ersten Blick auf *Hellster* stehen lassen.
3. **Standortkoordinaten** — Breite und Länge, falls die Airmass-Rampe entfernt werden soll. Ohne sie entfällt der Detrend, und der Report sagt es.
4. **Measure light curve.**

Der erste Lauf dauert einige Minuten; das Registrieren einiger hundert Subs ist der langsame Teil.

---

## 5. Die Oberfläche

**Linkes Panel**, vier nummerierte Gruppen in der Reihenfolge der Benutzung:

| Gruppe | Inhalt |
|---|---|
| **1 · Subs** | Ordnerwahl, Symlink/Kopie |
| **2 · Target star** | Auswahlmodus, Pixel- oder RA/Dec-Felder |
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

## 9. Der Transit-Fit

### Ein Trapez, kein randverdunkeltes Modell

Bei Amateurpräzision sind die beiden nicht unterscheidbar — eine 10-mmag-Delle bei 3 mmag pro Punkt bestimmt keinen Randverdunkelungskoeffizienten. Das Trapez liefert **Tiefe, Mittelzeit und Dauer**, und genau das verarbeiten ExoClock und ETD. Seine Ingress-Fraktion ist frei, damit deckt es auch den streifenden Fall ab: bei 0,5 entartet das Trapez zum Dreieck.

### Ein Raster, kein Optimierer

Die Suche läuft über ein Raster in **T0**, **Dauer** und **Ingress-Fraktion**. An jedem Knoten werden Tiefe und Baseline *analytisch* gelöst: bei fester Form ist das Modell `Baseline + Tiefe × Form(t)`, linear in beiden — ein 2×2-System liefert das exakte Optimum.

Vier stark korrelierte Parameter sind genau die Situation, in der ein lokaler Optimierer in ein Rauschminimum läuft und je nach Startpunkt etwas anderes liefert. Das Raster gibt bei jedem Lauf dieselbe Antwort, kann nicht divergieren, und seine Auflösung ist eine Zahl, die man nachlesen kann, statt einer Toleranz, die niemand prüft.

Die Tiefe ist **positiv** erzwungen — der Stern wird schwächer — der Fit kann also keine Aufhellung „entdecken" und Transit nennen.

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

### Die 3σ-Schwelle

Darunter wird nichts behauptet. Der Report druckt trotzdem, was der Fitter wollte, klar als Nicht-Messung markiert — denn „keine Detektion" und „das Werkzeug ist abgestürzt" sollen nicht gleich aussehen.

Drei Sigma ist die Lehrbuchgrenze für eine Detektionsbehauptung. ExoClock und AAVSO wollen fünf oder mehr — das ist aber eine Entscheidung der Einreichung, nicht des Fits.

---

## 11. Die Ausgabe lesen

Alles landet in einem Ordner `lightcurve/` neben deinen Subs:

| Datei | Inhalt |
|---|---|
| `lightcurve.csv` | Jeder Punkt: JD, roh, zentriert, detrended, Fehler, Airmass |
| `lightcurve.png` | Das Diagramm, wenn du es speicherst |
| `report.txt` | Der ganze Lauf als Text — Vergleiche, Ablehnungen, Methode, Ergebnis |

**RMS** ist robust (MAD-basiert), eine einzelne Satellitenspur bläht ihn also nicht auf. Vergleiche ihn mit der gesuchten Tiefe: 15 mmag Transit bei 5 mmag Streuung ist komfortabel, bei 15 mmag braucht es die ganze Nacht.

**Das Residuenfeld** zeigt, was das Modell verfehlt hat. Flaches Rauschen ist das Ziel; Struktur heißt, da ist noch etwas drin.

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

**Kein Transit gemeldet, obwohl erwartet** — Signifikanz im Reiter *Result* ansehen. Nahe 3σ fehlt schlicht die Präzision; ist sie negativ, hat der Fit eine Aufhellung gefunden, meist ein vom Detrend nicht entfernter Trend.

---

## 14. FAQ

**Verändert es meine Subs?** Nein. Alles wird unter `_lightcurve/` und `lightcurve/` geschrieben, die Quellframes werden nur gelesen.

**Auch für veränderliche Sterne?** Photometrie und Detrend gelten unverändert. Der *Fit* ist transitförmig, ein pulsierender Veränderlicher wird davon nicht gut beschrieben — aber die CSV liegt für deine eigene Auswertung bereit.

**Warum ist meine Signifikanz niedriger als bei anderen Werkzeugen?** Vermutlich wegen des zweiseitigen Baseline-Tests (§10). Er ist bewusst konservativ.

**Warum wird ein Transit am Rand des Laufs abgelehnt?** Weil sich ohne Baseline auf beiden Seiten eine Delle nicht von einem Trend unterscheiden lässt. Das ist eine Eigenschaft der Daten, nicht des Skripts.

**Soll ich das bei ExoClock einreichen?** Tiefe, T0 und Dauer liegen in der richtigen Form vor. Ziele auf 5σ oder besser und lies deren Einreichungshinweise — die Schwelle hier gilt fürs Behaupten einer Detektion, nicht fürs Publizieren.

---

## 15. Neu in 1.0.0

- Erstveröffentlichung: differentielle Photometrie eines Sub-Ordners über Sirils eigenes `light_curve`, mit Vergleichsensemble aus Sirils Sternerkennung, gefiltert nach SNR, Sättigung, Abstand und Isolation
- Airmass-Detrend mit einseitig getrimmter Baseline und einem auf Out-of-Transit verankerten zweiten Durchgang; die Zusammenbruchsgrenze ist **gemessen**, nicht behauptet (§8)
- Trapez-Fit auf einem deterministischen Raster, Tiefe und Baseline analytisch gelöst
- **Der Signifikanztest ist zweiseitig.** Die erste Fassung poolte die Out-of-Transit-Punkte, und die Testsuite hat gefangen, was das kostet: auf einer monotonen Rampe ganz ohne Transit erreicht der gepoolte Kontrast +25σ, der zweiseitige Test −10σ. Unkorrigierte Extinktion, ziehende Wolken und Fokusdrift erzeugen alle diese Rampe — das war kein Randfall
- Export als CSV, PNG und Textreport
