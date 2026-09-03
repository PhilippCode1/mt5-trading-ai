# Stufe 7 — Kaltstart öffnen

*Gefahren am 2026-08-19 auf Anweisung des Auftraggebers („Stufe 7"). Belege in
[`belege/`](belege/), fünf Dateien. Bestätigt durch Ausführung — jede Ausgabe liegt bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 schließt die
Stufen 4–10 für den Ausgang (B) aus, der Auftraggeber hat sie angewiesen (E-009).
**Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Der Kreis, in einer Zahl

Gemessen an den echten Betriebsjournalen dieses Standes
([`01-messung-vorher.txt`](belege/01-messung-vorher.txt)):

| | |
|---|---:|
| Eröffnungsversuche protokolliert | **4.343** |
| davon eröffnet | **32** (0,74 %) |
| davon **abgelehnt, mit Grund** | **4.311** (99,26 %) |

Über 99,26 % aller Signale weiß dieses System nichts — nicht, weil sie schlecht waren,
sondern weil sie nie gefahren wurden. **Ein Tor, das zu streng ist, sieht dabei genauso
aus wie eines, das richtig liegt.** Das ist der Kreis, den die Stufe aufbrechen soll,
und er ist hier keine Theorie, sondern ein Verhältnis von 32 zu 4.311.

Die Ablehnungsgründe, wie sie in den Journalen stehen:

| Grund | Zahl |
|---|---:|
| `cost_unverifiable` | 2.258 |
| `throttle_instrument_daily_cap` | 828 |
| `Trade disabled (retcode=10017)` | 753 |
| `risk_concurrent_position_cap` | 376 |
| `throttle_cooldown_active` | 58 |
| `strategy_not_admitted` | 21 |
| übrige (Broker-Meldungen, Marge, Füllart) | 17 |

---

## 2. Was gemessen wurde

| # | Forderung | vorher |
|---|---|---|
| A1 | Erkundungspfad im Papierkonto mit mitgeschriebenen Ablehnungsgründen | **halb** — Gründe ja, Erkundung nein |
| A2 | Gewichtung nach Auswahlwahrscheinlichkeit im Training | **Lücke** |
| A3 | Herkunftsspalte in den Auswertungen | **Lücke** |
| A4 | Schwellen von der Ersatzheuristik entkoppeln | **Lücke** |
| B1 | Auswertungstabelle enthält gekennzeichnete Zeilen aus abgelehnten Signalen | **Lücke** |
| B2 | Ein Trainingslauf weist den Anteil erkundender Beobachtungen aus | **Lücke** |

**A1 halb:** Die Gründe *werden* mitgeschrieben — 4.311 davon. Was fehlte, war der
Erkundungspfad: 0 Treffer für Erkundung/Exploration im gesamten Paket. Ein System, das
nur seine Zusagen beobachtet, kann seine Absagen nie überprüfen.

**A4 — der konkreteste Befund.** `risk_manager.py:829` lautete:

```python
praemisse = kampagne if kampagne is not None else assumed_cost_bps(klasse)
```

Dieselbe Zahl in zwei Rollen: **Rückfallwert**, wenn nichts gemessen wurde, **und
Schwelle**, unter der eine gemessene Zahl verworfen wird. Durchgerechnet für fx_major
(Annahme 0,65 bp):

| gemessene Kosten | Urteil | gerechnet wird mit |
|---:|---|---:|
| 0,30 bp | **verworfen** | 0,65 bp |
| 0,64 bp | **verworfen** | 0,65 bp |
| 0,65 bp | gilt | 0,65 bp |
| 1,68 bp | gilt | 1,68 bp |

**Ein Handelsplatz, der wirklich billiger ist, konnte nicht erkannt werden.** Seine
Messung wurde gegen die Annahme verworfen, und danach galt die Annahme — die Schwelle
maß ihre eigene Ausgabe (Sperre V2). Der Fall fiel bisher nicht auf, weil die in Stufe 3
gemessene Zahl (1,6756 bp) über der Annahme lag.

---

## 3. Ein verdächtig guter Befund, der sich nicht bestätigt hat

Bei der ersten Rechnung sah es so aus, als sei für `crypto` und `equity` das zulässige
Stopfenster **leer** — die Kostenuntergrenze (400 bzw. 200 bp) lag über der
Margenobergrenze (166,67 bp), womit die Klassen unhandelbar gewesen wären.

Das war mein Fehler: ich hatte alle Klassen gegen Hebel 10 gerechnet. Gegen **ihren
jeweils geklammerten** Hebel (Krypto 2, Aktie 5) ist kein Fenster leer:

| Klasse | Hebel | Untergrenze | Obergrenze | Fenster |
|---|---:|---:|---:|---|
| crypto | 2 | 400,0 | 833,3 | ok |
| equity | 5 | 200,0 | 333,3 | ok |
| fx_major | 5 | 6,5 | 333,3 | ok |

§6 des Auftrags verlangt genau das: ein überraschendes Ergebnis ist ein Verdachtsfall,
und zuerst wird der eigene Fehler gesucht. Er lag vor.

---

## 4. Was geändert wurde

### 4.1 `gates/erkundung.py` — der Erkundungspfad

Eine **Positivliste** von vier erkundbaren Ablehnungsgründen
(`strategy_not_admitted`, `throttle_cooldown_active`, `throttle_instrument_daily_cap`,
`risk_concurrent_position_cap`). Alle vier sind Auswahlentscheidungen — keine schützt
vor einem Verlust, den man nicht wieder einholen kann.

**Was ausdrücklich nicht erkundbar ist:** Global-Halt, fehlender Stop, schwebender
Auftrag, unbewertbarer Kontostand, Kostentor, Marge, Hebel. Eine Sperre zur Erkundung zu
übergehen hieße, genau das aufzuweichen, was die Stufen 4 und 5 dichtgemacht haben. Die
Liste ist eine **Positivliste, kein Filter**: ein unbekannter Grund gilt als nicht
erkundbar, und jeder künftig eingebaute Riegel ist damit ab seinem ersten Tag geschützt.

**Nur Papier.** Auf allem anderen ist die Antwort `kein_papierkonto`.

**Gesät und reproduzierbar.** Die Entscheidung fällt per Hash über die Kennung der
Gelegenheit, nicht aus einem Zustandsgenerator. Ein Zustandsgenerator hinge an der
Reihenfolge der Aufrufe (ein übersprungener Takt verschiebt alles danach) und wäre nach
einem Neustart nicht wiederherstellbar — beides macht eine Auswertung unreproduzierbar.
Gemessen: 0,0500 Trefferquote über 4.000 Gelegenheiten bei Sollrate 0,05, und derselbe
Schlüssel ergibt dieselbe Entscheidung.

### 4.2 Die Gewichtung

Erkundete Beobachtungen entstehen mit Wahrscheinlichkeit `p`, reguläre mit 1. Gleich
gezählt trägt jede erkundete Zeile das `1/p`-fache ihres Rechts. Gewichtet wird deshalb
invers (Horvitz-Thompson):

| Zeile | Gewicht |
|---|---:|
| regulär | 1,0 |
| erkundet, p = 0,5 | 2,0 |
| erkundet, p = 0,1 | 10,0 |
| erkundet, p = 0,05 | 20,0 |

An einem Fall, der von Hand nachzurechnen ist: eine reguläre Zeile mit +1 und eine
erkundete mit −1 bei p = 0,05 ergeben ungewichtet 0,0 — **gewichtet −0,9048**.

**Die Grenze, ausdrücklich:** Die Gewichtung heilt die Auswahl, nicht die
Beobachtungszahl. Zwanzig erkundete Zeilen bei p = 0,05 stehen für vierhundert
Gelegenheiten — sie bleiben zwanzig Beobachtungen, und `gates/herausforderer.py` zählt
sie auch so.

Eine erkundete Zeile **ohne** brauchbares `p` lässt sich nicht gewichten und wirft; sie
wird nicht stillschweigend mit 1 gerechnet (V3).

### 4.3 Die Herkunftsspalte und die Auswertungstabelle

`tools/auswertung.py` baut die Tabelle mit `herkunft ∈ {gefahren, erkundet, abgelehnt}`.
**Die Absagen stehen darin** — gekennzeichnet, mit Grund, ohne Ergebnis. Das fehlende
Ergebnis ist keine Lücke der Tabelle, sondern ihr Befund.

Gegen die eingecheckte Aufzeichnung:

```
Zeilen : 4343
  gefahren         32  ( 0.74 %)
  erkundet          0  ( 0.00 %)
  abgelehnt      4311  (99.26 %)
Zeilen MIT Ergebnis          : 11
Gewichteter Mittelwert       : 2.5950
```

### 4.4 Die Entkopplung der Schwelle

Neu: `KOSTENPRAEMISSE_BPS` — ein **getrennt gepflegter Plausibilitätsboden**, hergeleitet
aus dem halben typischen Roh-Spread ohne Kommission und Slippage. Er weist Unsinn ab
(0 bp), nicht eine bessere Ausführung:

| Klasse | Annahme | Boden |
|---|---:|---:|
| fx_major | 0,65 | 0,05 |
| gold / index_major | 1,5 | 0,10 |
| fx_minor | 4,0 | 0,30 |
| index_minor | 5,0 | 0,40 |
| commodity_non_gold | 7,0 | 0,50 |
| equity | 20,0 | 1,00 |
| crypto | 40,0 | 2,00 |

Ein Dauertor über **alle acht** Klassen hält fest, dass jeder Boden echt unter seiner
Annahme liegt. Wer beide Tabellen gleichsetzt, stellt die Kopplung wieder her — und der
Fall ist sofort rot.

---

## 5. Was schiefging — und es betrifft meine eigene Stufe 5

**Die eingecheckte Aufzeichnung enthielt die abgelehnten Signale nicht.** In Stufe 5
habe ich `eroeffnungsversuch` als Messrauschen weggelassen, weil er 4.343 der 17.166
Sätze ausmachte. Das war falsch, und zwar auf eine Weise, die erst eine Stufe später
auffiel: die Abnahme dieser Stufe verlangt ausdrücklich Zeilen aus abgelehnten Signalen
— genau diese Sätze tragen sie.

**Der Fehler hat einen Namen: ich habe nach Umfang beurteilt statt nach Aussagekraft.**
Eine Verkleinerung, die das Häufige für Rauschen hält, wirft das Seltene weg und behält
das Laute.

Korrigiert: `eroeffnungsversuch` ist wieder drin. Statt der Sätze fällt jetzt ein
**Feld** weg (`schritte`, die Naht-für-Naht-Liste), und zwar nach Aussagekraft: die erste
rote Naht steht bereits als `grund` im selben Satz, die übrigen Einträge sind die grünen
davor. Dass das zugleich 72 % des Umfangs spart (4,15 → 1,18 MB), ist ein Nebeneffekt und
ausdrücklich nicht die Begründung. Der Feldwegfall steht im Kopf der Datei, wie die
Satzwegfälle auch.

**Zweiter Befund derselben Art:** Die Auswertungstabelle lieferte zunächst **null** Zeilen
mit Ergebnis. Ich habe nachgesehen statt es stehenzulassen — der Abschluss trägt **nicht**
die Kennung der Eröffnung (`open-EURUSD-…` gegen `close-EURUSD-…`, Schnittmenge **0**).
Verbunden werden muss über die Positionskennung, und die steht in einem dritten Satz:
`eroeffnungsversuch → eroeffnet → geschlossen`. Über diesen Weg treffen sich alle 16
gefahrenen Signale mit ihrem Abschluss; 11 davon tragen einen Ausstiegspreis.

---

## 6. Abnahme

**`tests/test_stufe7_kaltstart.py`, 37 Fälle**, je Tor rot und grün, Beleg
[`04-abnahme.txt`](belege/04-abnahme.txt).

**Mutationsprobe** ([`03-mutationsprobe.txt`](belege/03-mutationsprobe.txt)):

| Mutation | rote Fälle |
|---|---:|
| M1 Positivliste zum Filter gemacht | **8** |
| M2 Erkundung auf dem Echtgeldkonto zugelassen | **1** |
| M3 Gewichtung ausgeschaltet | **2** |
| M4 Schwelle wieder auf die Ersatzheuristik gesetzt | **9** |

Nach jeder Mutation aus einer **vor** dem Eingriff angelegten Kopie zurückgestellt
(F-010); beide Prüfsummen danach identisch.

**Torlauf** ([`05-torlauf.txt`](belege/05-torlauf.txt)): sieben Tore je **Exit 0**;
`pytest` **1.516 bestanden, 0 fehlgeschlagen**.

---

## 7. Was diese Stufe ausdrücklich nicht behauptet

**Es ist noch nichts erkundet worden.** Der Pfad ist gebaut, die Rate steht, die
Gewichtung rechnet — aber `erkundet` ist in der Auswertung **0,00 %**, weil der einzige
vorhandene Betriebslauf vor dieser Stufe lief. Die Zahl wird erst dann von null
verschieden, wenn der Betrieb wieder läuft. Das gehört so gesagt und nicht als Erfolg
verkauft.

**Die Erkundungsrate ist gesetzt, nicht hergeleitet** — 5 % ist eine Wahl gegen den
gemessenen Missstand, keine aus einer Bandit-Theorie abgeleitete Größe. Sie steht als
benannte Konstante im Code.

**Die Verdrahtung in den Betrieb steht aus.** `gates/erkundung.py` und
`tools/auswertung.py` sind gebaut und geprüft; der Aufruf aus `tools/live_betrieb.py`
heraus — also das tatsächliche Fahren eines erkundeten Signals samt Journalfeld
`erkundet`/`erkundung_p` — ist **nicht** Teil dieser Stufe. Er verlangt einen Lauf gegen
ein Demokonto, und dafür liegt keine Terminal-Konfiguration vor (siehe Stufe 5, §7). Die
Auswertung liest das Feld bereits, sobald es da ist.
