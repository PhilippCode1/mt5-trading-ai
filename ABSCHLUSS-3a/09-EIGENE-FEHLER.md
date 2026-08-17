# Eigene Fehler in Paket 3a

Sechs Fehler, alle von mir, alle beim Nachrechnen der jeweils vorigen Fassung gefunden.
**Fünf von sechs zeigten in die Richtung, die schmeichelt** — sie hätten das Ergebnis
günstiger aussehen lassen oder einen Kandidaten aus dem falschen Grund getötet.

Diese Liste steht hier, weil ein Befund ohne die Fehler, die zu ihm geführt haben, nur
die halbe Wahrheit ist. Die ausführliche Fassung steht in
[`01-AUFLOESUNG.md`](01-AUFLOESUNG.md) §3 und
[`04-EREIGNISSTUDIE.md`](04-EREIGNISSTUDIE.md) §3.

---

## 1. N war die Fensterzahl statt der Ereigniszahl

**Was.** Der erste Lauf der Auflösungsrechnung setzte für das 4h-Fenster N = 38.882 ein:
die Zahl aller Fenster der Reihe. Richtig ist die Zahl der **Ereignisse** — ein tägliches
Ereignis liefert je Handelstag eines, auch wenn der Tag sechs Vier-Stunden-Fenster hat.

**Richtung.** Schmeichelnd. N um Faktor 6 zu groß senkt die nötige Sharpe um √6 ≈ 2,4 und
ließ blinde Kombinationen auflösbar aussehen.

**Wie gefunden.** Beim Durchsehen der ersten Ergebnistabelle fiel auf, dass die
Ereigniszahl für „täglich" größer war als die Zahl der Handelstage.

**Behoben.** Ereigniszahl = Frequenz × Historientiefe, getrennt von der Fensterzahl.

---

## 2. K ohne Währungsumrechnung

**Was.** Die Funktion, die K je Instrument holt, hatte die Kostenformel aus
`tools/kostentor.py` **nachgebaut** und dabei die Umrechnung der Kommission verloren. Bei
GBPJPY steht das Nominal in JPY und die Kommission in USD; ohne `_fx` fiel sie von 0,44 auf
0,003 bp, K von 1,84 auf 1,31 bp.

**Richtung.** Gegen den Kandidaten. Ein kleineres K senkt die nachzuweisende Wirkung 3 × K,
und GBPJPY/4h/monatlich wanderte dadurch auf 1,52 statt 1,03 — K3 wäre aus dem falschen
Grund gestorben.

**Wie gefunden.** Beim Vergleich der gemessenen K-Werte mit denen aus §1 des Auftrags: vier
von fünf stimmten auf die Stelle, GBPJPY wich um 29 % ab. Eine Kommission von 0,003 bp ist
für einen ECN-Broker unmöglich.

**Behoben.** Der Nachbau wurde **gelöscht**. `_kosten_bps` ruft jetzt
`tools/kostentor.py::_zeile` auf — dieselbe Funktion, die das Kostentor aus Paket 2 führt.
Dafür wurde `tools/` zum Paket.

**Lehre.** Dieselbe wie beim NVDA-Kommissionsfehler aus Paket 2
([`../ABSCHLUSS/09-EIGENE-FEHLER.md`](../ABSCHLUSS/09-EIGENE-FEHLER.md)): eine zweite
Umsetzung derselben Rechnung ist keine Bequemlichkeit, sondern eine zweite Fehlerquelle.

---

## 3. Die Historie zu kurz abgefragt

**Was.** Der Abruf stand auf 25 Jahren für D1/H4 und **zwei** Jahren für H1. Die zwei Jahre
waren eine Notlösung, weil ein 25-Jahre-Abruf auf H1 leer zurückkam — und sie wurden nie
nachgeprüft. Tatsächlich liefert das Terminal auf H1 bis mindestens elf Jahre.

**Richtung.** Gegen die Kandidaten. N für jedes 1h-Fenster war um Faktor 5,5 zu klein.

**Wie gefunden.** Eine Treppenprobe über 3, 5, 8, 9, 10, 11 Jahre. Der Anstoß stand im
Auftrag selbst: „Eine leere Antwort heißt ‚noch nicht geladen', nicht ‚gibt es nicht.'"

**Behoben.** Abrufzeitraum je Zeitrahmen abgetastet statt gesetzt.

---

## 4. Vier Jahrzehnte EURUSD, die es nie gab

**Was.** Der tiefere Abruf brachte EURUSD-Tageskerzen ab 1981-08-18 zutage, nahtlos an die
echte Reihe angesetzt (Schluss 1,17240 am 31.12.1998, Eröffnung 1,18010 am 04.01.1999).
Den Euro gibt es seit dem 01.01.1999. Alles davor ist eine zurückgerechnete Korbreihe.

**Richtung.** Schmeichelnd. 4.480 zusätzliche Kerzen hätten N um 71 % aufgebläht — mit
einer Tagesrendite-Streuung von 67,1 gegen 58,1 bp danach, also aus einem anderen Regime.

**Wie gefunden.** Die Anfangsdaten der tieferen Abfrage gelesen, statt nur die Kerzenzahl.
1981 für ein Instrument, das 1999 eingeführt wurde, fällt auf, sobald man hinsieht.

**Behoben.** Schnitt in `tools/aufloesung.py::FRUEHESTE_KERZE`, gesichert durch
`tests/test_resolution.py::test_eurusd_reihe_beginnt_nicht_vor_dem_euro`.

---

## 5. Die Grenze war die der Abfrage, nicht die der Historie

**Was.** Nach Fehler 3 stand der H1-Abruf auf elf Jahren, weil zwölf Jahre zweimal leer
zurückkamen. Auch das war zu kurz: es gibt H1-Historie bis **2010-07-07**. Leer kommt nur
eine **einzelne Abfrage** über mehr als rund 70.000 Kerzen zurück — und zwar leer, nicht
als Fehler.

**Richtung.** Gegen die Kandidaten. N für die täglichen 1h-Studien stieg nach der Korrektur
von 2.769 auf 4.060, für K3 von 131 auf 193.

**Wie gefunden.** Es fiel auf, dass **alle fünf** Instrumente ihre H1-Reihe auf den Tag
genau an meiner Abfragegrenze begannen — dasselbe Muster wie in Fehler 3. Die Probe, die es
klärte, war gegen die eigene Annahme gebaut: ein *kleines* Fenster *tief* in der
Vergangenheit. Der Abruf 2013–2016 liefert 18.505 Kerzen, der Abruf 2005–2006 klemmt auf
den 07.07.2010.

**Behoben.** `_hole()` holt die Reihe in Fünfjahresscheiben und setzt sie zusammen.

---

## 6. M6.0 lief gegen die geplante statt die messbare Ereigniszahl

**Was.** Die Auflösungsrechnung setzte für K5 (NASDAQ-Schlussauktion, NVDA) 5.777
Ereignisse ein — die Zahl der Kalendereinträge. Messbar waren **472**, knapp 8 %. NVDA
handelt bis 16:00 New Yorker Zeit; **nach der Schlussauktion gibt es am selben Tag keine
handelbare Stunde**, die nächste Kerze kommt am Folgetag um 09:30.

**Richtung.** Schmeichelnd. Mit N = 5.777 galt K5 als auflösbar (0,39); mit N = 472 ist er
blind (1,36) und hätte **vor** der Messung ausgesondert gehört — kostenfrei, wie M6.0 es
vorsieht.

**Wie gefunden.** In der Ergebnistabelle der Studie stand „472 von 5.983". Die Zahl war zu
auffällig, um sie stehen zu lassen; die Stundenverteilung der NVDA-Kerzen erklärte sie
sofort.

**Kosten.** Ein Versuch von zwölf, verbraucht für eine Messung, die nichts sehen konnte.
Er wird **nicht** stillschweigend gestrichen: das Register ist anhängend, und ein Versuch,
der aus meinem Fehler entstand, bleibt gezählt.

**Nicht behoben, sondern benannt.** Die Korrektur — M6.0 gegen die Zahl der Ereignisse
laufen zu lassen, für die es Kurse im Fenster gibt — gehört in ein Folgepaket. Für die
sechs übrigen Studien ändert sie nichts: dort wurden 78 % bis 99,5 % der geplanten
Ereignisse gemessen.

---

## Der gemeinsame Nenner

Fehler 3, 4 und 5 sind derselbe Fehler in drei Anläufen: **eine Grenze, die man selbst
gesetzt hat, sieht in der Ausgabe genauso aus wie eine Grenze der Daten.** Dreimal stand in
der Tabelle eine glatte Zahl — „2,0 Jahre", „25,0 Jahre", „11,0 Jahre" —, und dreimal war
sie mein Echo, nicht die Antwort des Terminals.

Geholfen hat nicht schärferes Hinsehen auf dieselbe Zahl, sondern eine Probe, die **gegen**
die eigene Annahme gebaut war: nicht „geht mehr?", sondern „was liegt an einer Stelle, an
der nach meiner Annahme nichts liegen darf?". Dieselbe Bewegung führte auch zu Fehler 6 und
zum Serverzeit-Befund.

Eine falsche Zwischendiagnose gehört ebenfalls hierher, auch wenn sie keine Zahl verfälscht
hat: der Freitagseffekt in der D1-Gegenprobe wurde als Beleg **gegen** einen Stundenversatz
gelesen, obwohl er mit beidem vereinbar ist. Aus einer Beobachtung, die zwei Erklärungen
zulässt, wurde eine ausgeschlossen — und ausgerechnet die richtige
([`02-DATENLAGE.md`](02-DATENLAGE.md) §3.2).
