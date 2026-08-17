# Das Urteil (A4)

> **Gibt es einen belegten Grund, dieses Vorhaben fortzusetzen?**

**Nein — jedenfalls keinen, der aus diesem Paket kommt.** Sieben Studien, sieben negative
Nettoeffekte, keine bestandene Prüfung. Die Zwangslagen sind belegt und benennbar; sie
tragen ihre Kosten nicht, und der Abstand ist kein knapper.

---

## 1. Die Ampeln

### M5 — die Vorfrage, vier Zeilen

| Zeile | Frage | Befund | |
|---|---|---|---|
| a | Wer steht auf der Gegenseite? | Benannt für alle fünf Kandidaten: Indexfonds und Abrechnungspflichtige (K1, K3), japanische Importeure und Exporteure (K2), Halter über den Finanzierungsstichtag (K4), Schlusskurs-Abrechner (K5) | ✅ |
| b | Warum muss sie? | Zwang von außen in allen fünf Fällen: Abrechnungspflicht gegen einen Referenzkurs, Finanzierungsstichtag, Bewertungsstichtag | ✅ |
| c | Warum hört sie nicht auf? | Der Zwang ist Regel, nicht Absicht — er besteht fort, auch wenn alle ihn kennen | ✅ |
| d | Woran ist es zu sehen? | Zeitpunkt im Voraus bestimmbar: ja, alle fünf als Code. Auflösung nach M6.0: ja für K1–K4, **nein für K5** (1,36 mit der messbaren Ereigniszahl) | ⚠️ |

**M5 = GELB.** Mindestens ein Kandidat erfüllt a–d und scheitert an M6.1 — tatsächlich
sechs von sieben Studien. Gelb heißt nach §5 des Auftrags: **keine Strategiearbeit**, die
Zwangslage ist belegt, trägt aber die Kosten nicht, und Abbruchbedingung 6 bleibt
ausgelöst.

### M6 je Kandidat

| Kandidat | Instr. | M6.0 Auflösung | M6.1 Brutto ≥ 3×K | M6.2 (3 Prüfungen) |
|---|---|---|---|---|
| K1 London-Fixing | EURUSD | 0,17 ✅ | 0,53 < 3,30 ❌ | 0/3 ❌ |
| K1 London-Fixing | GBPJPY | 0,13 ✅ | 0,55 < 5,51 ❌ | 0/3 ❌ |
| K2 Tokioter TTM | GBPJPY | 0,13 ✅ | 0,14 < 5,51 ❌ | 0/3 ❌ |
| K3 Monatsende | GBPJPY | 0,62 ✅ | 1,36 < 5,51 ❌ | 0/3 ❌ |
| K4 Rollover | EURUSD | 0,17 ✅ | 0,36 < 3,30 ❌ | 0/3 ❌ |
| K4 Rollover | GBPJPY | 0,13 ✅ | 0,74 < 5,51 ❌ | 0/3 ❌ |
| K5 NASDAQ-Schluss | NVDA | **1,36 ❌** | 0,00 < 12,56 ❌ | 0/3 ❌ |

Von 21 Prüfungen (7 Studien × M6.0/M6.1/M6.2) sind **6 bestanden**, alle davon M6.0.

---

## 2. Bei welchem K würde es tragen?

Gelb verlangt diese Gegenrechnung. Sie ist kurz.

| Kandidat | Instr. | Brutto | nötiges K (= Brutto/3) | bestes K am Markt | Faktor |
|---|---|---:|---:|---:|---:|
| K3 Monatsende | GBPJPY | 1,36 bp | **0,45 bp** | 1,84 bp | 4,1 × |
| K4 Rollover | GBPJPY | 0,74 bp | 0,25 bp | 1,84 bp | 7,5 × |
| K1 London | GBPJPY | 0,55 bp | 0,18 bp | 1,84 bp | 10,0 × |
| K1 London | EURUSD | 0,53 bp | 0,18 bp | 1,10 bp | 6,2 × |
| K4 Rollover | EURUSD | 0,36 bp | 0,12 bp | 1,10 bp | 9,2 × |
| K2 Tokio | GBPJPY | 0,14 bp | 0,05 bp | 1,84 bp | 39,4 × |

**Erreicht ein Broker das?** Nein, und zwar nicht knapp. Der beste Fall ist K3: nötig
wären 0,45 bp Round-Turn-Kosten insgesamt. Allein der veröffentlichte Spread des
günstigsten Brokers (IC Markets, GBPJPY) liegt bei 0,31 bp, die Kommission bei 0,44 bp —
zusammen schon 0,75 bp, **ohne jede Slippage**. Die bezifferte Slippage-Annahme beträgt
1,00 bp. Es gibt keinen Broker und keine Verhandlung, die 0,45 bp erreichen; die Zahl
liegt unter den reinen Gebühren.

Und selbst wenn: die Randomisierung sagt, dass derselbe Effekt an beliebig verschobenen
Zeitpunkten genauso auftritt. Ein Kostenvorteil würde also nicht die Zwangslage
handelbar machen, sondern das allgemeine Rauschen.

---

## 3. Der Zustand aller sechs Abbruchbedingungen

| # | Bedingung | Gemessener Wert | Stand |
|---|---|---|---|
| 1 | Kostentor rot | M1 grün (alle sechs Instrumente unter 50 %, knappster Wert XAUUSD 51,0 % → siehe Paket 2), **M2 gerissen**: 13 von 18 Kostenzeilen über 50 % bei 4 RT/Tag und Hebel 5 | **nicht ausgelöst** (Bedingung verlangt M1) |
| 2 | Kein Kandidat übersteht die Deflation | Höchster Deflated Sharpe über alle sieben Studien: **0,686** (K4/GBPJPY, Out-of-Sample), Schwelle 0,95 | **ausgelöst** |
| 3 | Realisierte Kosten weichen ab | Nicht messbar — kein Handelsbetrieb, keine realisierten Kosten. Nach der Regel des Dokuments gilt eine fehlende Messung als ausgelöst | **ausgelöst (mangels Messung)** |
| 4 | Halal-Vorfrage negativ | Unverändert offen; drei getrennte Fragen in `HALAL-VORFRAGE.md`, keine beantwortet | **offen** |
| 5 | Aufwandsgrenze 12 Monate | Frist bis 2027-08-17. Heute 2026-08-17, also **12 Monate verbleibend**. Kein grünes Bewertungstor erreicht | **nicht ausgelöst, Uhr läuft** |
| 6 | Keine benennbare Vorteilsquelle | Fünf Zwangslagen benannt und gemessen; **keine trägt die Kosten**. Die Quelle ist benennbar, aber nicht verwertbar | **bleibt ausgelöst** |

Bedingung 2 ist mit diesem Paket erstmals **gemessen** statt angenommen: sieben Studien,
höchster DSR 0,686 gegen die Schwelle 0,95, gerechnet auf dem Out-of-Sample-Drittel gegen
T = 12 Versuche.

---

## 4. Die Empfehlung

**Bedingtes Halten (M5 gelb).** Keine Strategiearbeit. Die Zwangslagen sind belegt und
ihre Zeitpunkte im Voraus bestimmbar — die Vorfrage aus `ALPHA.md` ist damit nicht mit
Nein beantwortet, sondern mit „ja, und es reicht trotzdem nicht". Der Effekt, den diese
Zwangslagen hinterlassen, ist um den Faktor 4 bis 39 zu klein, um die Kosten zu tragen,
und er ist nach der Randomisierung nicht einmal an die Ereigniszeitpunkte gebunden.

**Paket 3b wird nicht geschrieben.** Es setzte ein grünes M5 voraus.

Verbleibendes Versuchsbudget: **5 von 12**. Sie bleiben ungenutzt, solange keine neue
Zwangslage mit eigener Begründungstiefe vorliegt — nicht als Vorrat für weitere Anläufe
auf dieselben fünf.

---

## 5. Was mit dem Gebauten geschieht

Nichts wird gelöscht. Was dieses Paket gebaut hat, ist von der Frage unabhängig, an der es
gescheitert ist:

| Baustein | Wert unabhängig vom Urteil |
|---|---|
| `backtest/resolution.py` | Sondert blinde Studien **vor** der Messung aus. Hätte die Vorgängerfassung von Paket 3 in 17 von 20 Fällen gestoppt |
| `backtest/kalender.py` | Die gemessene Serverzeitzone und die einzige Stelle, an der gedreht wird. Jede künftige Arbeit mit Uhrzeiten hängt daran |
| `backtest/ereignisstudie.py` | Misst Brutto **und** Netto, mit Selbsttest und Gegenprobe |
| `config/reihen/` | 15 Reihen-Manifeste mit Prüfsummen — die `data_checksum` für jeden künftigen Versuch |
| Der Befund zur Serverzeit | Der wichtigste Einzelbefund des Pakets, und er gilt für **jede** spätere Arbeit an diesem Terminal |

Für die anderen drei Ausgänge, die nicht eingetreten sind: bei *Go* wäre all das die
Grundlage von Paket 3b gewesen; bei *Orange* wäre die Datenlücke zu beziffern gewesen
(sie ist es für K5: 867 statt 472 messbare Ereignisse); bei *Rot* wäre die
Alternativkonstruktion aus `HALAL-VORFRAGE.md` §3 zu benennen, aber nicht zu beginnen
gewesen.

---

## 6. Werden die vier Demokonten noch gebraucht?

**Nein.** Ausdrücklich nein.

Die Konten bei IC Markets, Tickmill, Admirals und Pepperstone waren für die
Slippage-Messung aus Paket 3b gedacht — zwei Wochen Messbetrieb, um die bezifferte Annahme
von 0,5 bis 1,0 bp durch eine Messung zu ersetzen. Diese Messung würde jetzt eine Zahl
verbessern, die ohnehin um ein Vielfaches zu groß ist: selbst bei **Slippage null** bliebe
K für GBPJPY bei 0,84 bp gegen die nötigen 0,45 bp. Der Messbetrieb kann das Urteil nicht
drehen.

Die Konten bleiben bestehen und kosten nichts; sie werden nur nicht bemessen. Niemand
sollte zwei Wochen Betrieb auf eine Frage verwenden, die vorher entschieden ist.

---

## 7. Was dieses Paket über sich selbst gelernt hat

Sechs eigene Fehler, alle beim Nachrechnen der jeweils vorigen Fassung gefunden, fünf
davon in der Richtung, die schmeichelt (vollständig in
[`01-AUFLOESUNG.md`](01-AUFLOESUNG.md) §3 und [`04-EREIGNISSTUDIE.md`](04-EREIGNISSTUDIE.md) §3):

1. N war die Fenster- statt der Ereigniszahl — Faktor 6 zu groß.
2. K ohne Währungsumrechnung — der Nachbau einer vorhandenen Rechnung verlor `_fx`.
3. Die Historie zu kurz abgefragt — H1 reicht 16,1 statt 2,0 Jahre.
4. Vier Jahrzehnte EURUSD vor der Euro-Einführung, zurückgerechnet und nie handelbar.
5. Die Elfjahresgrenze war die Größe **einer Abfrage**, nicht die der Historie.
6. M6.0 lief gegen die geplante statt die messbare Ereigniszahl — K5 hätte nie laufen
   dürfen und hat einen Versuch gekostet.

Der gemeinsame Nenner von 3, 4 und 5: **eine Grenze, die man selbst gesetzt hat, sieht in
der Ausgabe genauso aus wie eine Grenze der Daten.** Dreimal stand dort eine glatte Zahl —
„2,0 Jahre", „25,0 Jahre", „11,0 Jahre" —, und dreimal war sie mein Echo. Geholfen hat
nicht schärferes Hinsehen, sondern eine Probe, die **gegen** die eigene Annahme gebaut
war: nicht „geht mehr?", sondern „was liegt an einer Stelle, an der nach meiner Annahme
nichts liegen darf?".

---

## 8. Unterschrift

Die Zahlen in diesem Dokument stammen aus den Läufen in
[`07-AUSGABEN/`](07-AUSGABEN/) und sind mit den dort abgelegten Rohausgaben nachprüfbar.
Die sieben Versuche stehen im anhängenden Register `docs/trials.jsonl`.

| | |
|---|---|
| Erstellt | 2026-08-17, Paket 3a |
| Ausführung | Claude Opus 5 |
| Vorgelegt | Philipp |
| Gegengezeichnet | ............................................ |
| Datum | ............................................ |
