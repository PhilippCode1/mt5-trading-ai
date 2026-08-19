# Stufe 2 — Zeitschranken schließen

*Erhoben 2026-08-19. Rohausgaben in `belege/`. Alle Mutationen wurden wirklich gefahren
und zurückgenommen.*

**Auftrag (§7, Stufe 2):** Alle Querabfragen, die „neuester Datenbankzustand" statt
„Zustand zum Zeitpunkt des Bars" lesen, bekommen eine obere Zeitgrenze.
Bestätigungszeitstempel auf Schlusszeit statt Startzeit. Feature-Verbund darf nie in die
zum Entscheidungszeitpunkt laufende Kerze greifen.
**Abnahme:** ein Determinismus-Tor, das denselben Kursabschnitt zweimal verarbeitet, und
der Nachweis, dass es rot wird, sobald eine Zeitschranke wieder entfernt wird.

---

## 1. Die Vorgabe ist an einem anderen Stand formuliert — was sie hier bedeutet

Die drei genannten Punkte stammen aus dem Prüfbericht zum **verworfenen** Stand
`bitget-btc-ai`: `fetch_features_near`, die `drawing-engine`, `confirmed_ts_ms`. Der
gewählte Stand hat weder Datenbank noch Feature-, Struktur- oder Zeichendienste. Die
Vorgabe ist deshalb nicht abzuarbeiten, sondern zu **übersetzen**. Gemessen, nicht
angenommen:

| Vorgabe | Entsprechung in diesem Stand | Befund |
|---|---|---|
| Querabfragen ohne obere Zeitgrenze | direkte Leser von `terminal.rates(...)` mit `ende = jetzt` | **5 Stellen**, alle ungesichert |
| „Feature-Verbund greift in die laufende Kerze" | Verbraucher, die `Bar.is_closed` ignorieren | **1 von 2** Verbrauchern |
| Bestätigungszeitstempel auf Schlusszeit | `Bar.ts` ist ausdrücklich der **Beginn** des Intervalls, und `is_closed` trägt die Schlussfrage separat | bereits richtig gelöst, nichts zu ändern |

Der dritte Punkt entfällt also nicht aus Bequemlichkeit: `venue/protocol.py:258`
kommentiert `ts` als „Beginn des Intervalls (open time), UTC" und stellt die Frage, ob das
Intervall vorbei ist, als eigenes Pflichtfeld ohne Vorgabewert daneben. Das ist genau die
Trennung, die der Vorgabepunkt herstellen will.

---

## 2. Der Befund

### 2.1 Eine Regel, die an einer Stelle steht und an fünf fehlt

`venue/mt5.py::get_bars` beantwortet die Frage sauber und ausführlich begründet: eine Bar
gilt als abgeschlossen, wenn `ts + dauer <= jetzt`, und `jetzt` kommt vom **Tick-Stempel
des Platzes**, nicht von der Rechneruhr — mit einer nachgemessenen Begründung, warum die
Systemzeit je nach Serverzone in beide Richtungen falsch liegt.

Nur: fünf Stellen gehen an dieser Tür vorbei (Beleg: `belege/01-bestandsaufnahme.txt`).
Sie lesen `terminal.rates(...)` direkt, bekommen deshalb **gar kein** `is_closed` und
setzen alle `ende = datetime.now(UTC)`:

| Stelle | Wozu die Zahlen dienten |
|---|---|
| `tools/atr_messung.py:87` | die ATR-Reihe in `config/atr_measurements.json` — Eingabe des Kostentors M1 |
| `tools/atr_messung.py:156` | `rates[-1].close` als **Umrechnungskurs** für Kommissionen in fremder Währung |
| `tools/aufloesung.py:162` | erzeugt die 15 Reihen-Manifeste |
| `tools/aufloesung.py:522` | Gegenprobe gegen eine Fremddatei |
| `tools/ereignisstudie.py:211` | die sieben Einträge in `TRIALS.jsonl` |

### 2.2 Der Nachweis, dass es nicht theoretisch ist

Die unfertige Kerze steckt **nachweislich in den eingecheckten Manifesten**. Gerechnet aus
den Manifesten selbst — `last` plus Zeitrahmenlänge gegen `retrieved_at`
(Beleg: `belege/02-unfertige-kerze.txt`):

**12 von 15 Reihen enden auf einer Bar, die zum Abrufzeitpunkt noch offen war.**

Beispiel EURUSD H1: `last = 2026-08-17T13:00`, `retrieved_at = 2026-08-17T13:14` — die
Stundenkerze von 13:00 schließt erst um 14:00. Die drei Ausnahmen sind die NVDA-Reihen;
dort war der US-Markt geschlossen und die letzte Bar lag drei Tage zurück.

**Folge:** Die `checksum` dieser Manifeste deckt eine Bar, die sich noch ändert. Ein
zweiter Abruf ergibt eine andere Zahl — die Reihen sind auch **unabhängig vom
Quellenproblem aus Stufe 1** nicht reproduzierbar. Und dieselbe `checksum` steht als
`data_checksum` in den sieben Einträgen von `TRIALS.jsonl`.

### 2.3 Ein Verbraucher, der den Vermerk bekommt und ignoriert

`is_closed` hat genau zwei Verbraucher. `tools/live_betrieb.py:251` filtert
(`fertig = [b for b in bars if b.is_closed]`). `tools/live_konsole.py::_signal` filterte
**nicht** — sie baute ihre Reihe aus *allen* Bars und legte `MarketView` auf die letzte,
also auf die laufende Kerze, deren `close` der Momentankurs ist.

Die Konsole kann nichts auslösen (`allow_write` ist fest verdrahtet, kein Schalter). Sie
verspricht im Modulkopf aber zu zeigen, „was das System … entscheiden würde", und tat das
auf einem anderen Barsatz als der wirkliche Treiber. Zwei Anzeigen desselben Signals, die
auseinanderlaufen — und die Konsole ist die, der der Betreiber glaubt. Ausgerechnet ihr
eigener Kommentar sagte: „die Strategie soll genau das sehen, was sie im Backtest sähe,
und nichts darüber hinaus."

---

## 3. Was geändert wurde

**Die Regel steht jetzt einmal, mit Namen:** `venue/protocol.py::ist_abgeschlossen(ts,
timeframe, jetzt)`. `get_bars` ruft sie statt den Ausdruck zu wiederholen; die fünf
Umgehungen rufen sie ebenfalls; die Konsole filtert auf `is_closed`.

Bei allen fünf Werkzeugen kommt `jetzt` vom **Tick des Symbols**, nicht von der
Rechneruhr — Kerzen- und Tick-Stempel laufen durch dieselbe Umrechnung des Terminals, die
Rechneruhr nicht. Fehlt der Tick, wird **nicht geraten**: `aufloesung` liefert eine leere
Reihe mit Begründung im Protokoll, `ereignisstudie` wirft, `atr_messung` meldet „nicht
gemessen". Das ist V3 — ein fehlender Messwert sperrt und erzeugt keinen Vorgabewert.

**Ehrlich benannter Rest.** Für D1 und H4 liegt die echte Intervallgrenze an der
Server-Mitternacht statt bei `ts + duration`; über eine Zeitumstellung weichen beide um
eine Stunde ab. Der Mangel ist im Stand bekannt, begründet und mit einem eigenen Testfall
festgenagelt. Für die fünf Stellen ist die Änderung trotzdem ein Fortschritt: sie nahmen
die unfertige Kerze **immer** mit, künftig nur noch möglicherweise an zwei Tagen im Jahr
eine Stunde lang.

---

## 4. Abnahme — das Determinismus-Tor

`tests/test_zeitschranken.py`, neun Fälle auf zwei Ebenen.

**Ebene 1 — die Kerze.** Dieselbe Reihe, zwei Verarbeitungszeitpunkte: 30 Minuten nach
Beginn der letzten Kerze (4 von 5 Bars) und genau auf ihrer Grenze (5 von 5). Der
überlappende Teil ist **prüfsummengleich**.

**Ebene 2 — die Auswertung.** Derselbe Kursabschnitt zweimal durch `run_backtest`: einmal
allein (`bars[:n]`), einmal als Anfang der vollen Reihe (`bars[:N]`, also **mit bereits
vorhandenen späteren Zeilen**). Verglichen wird der kanonisch serialisierte Trade-Log
aller vor dem Schnitt abgeschlossenen Trades — **zeichenweise gleich**. Ein eigener Fall
verhindert, dass das Tor leer läuft: `assert a != "[]"`.

Gefahren auf `tests/fixtures/smoke_eurusd_h1.csv` (420 Bars), **nicht** auf den Daten aus
Stufe 1 — die liegen unter `daten/` und sind gitignoriert. Ein Tor, das im Prüfstand
mangels Datei stillschweigend übersprungen wird, ist keins.

### 4.1 Die roten Eichfälle — wirklich gefahren

Beleg: `belege/03-eichfaelle.txt`.

| Mutation | Ergebnis |
|---|---|
| grün, unverändert | `9 passed` |
| Zeitschranke aus `ereignisstudie.py::_lade_kerzen` entfernt | **`1 failed, 8 passed`** |
| `is_closed`-Filter aus `live_konsole.py` entfernt | **`1 failed, 8 passed`** |
| gebündelte Regel in `get_bars` auf `is_closed=True` entwaffnet | **`8 failed, 15 passed`** |
| alle drei zurückgenommen | `23 passed` |

### 4.2 Ein eigener Fehler, den erst die Mutation gefunden hat

Die **erste** Fassung des Wächters, der prüft, ob ein direkter Kerzenleser die Schranke
kennt, suchte die Zeichenkette `ist_abgeschlossen` im Quelltext. Mutation 1 lief damit
**grün durch** — das Wort stand noch im Docstring („Begründung bei
``protocol.ist_abgeschlossen``"). Die Prüfung las Prosa und hielt sie für Code: genau die
Sorte Wächter, die dieses Repository an anderer Stelle als Tautologie führt, und ich hatte
sie selbst gebaut.

Berichtigt: der Fall parst jetzt den Syntaxbaum und verlangt einen echten **Aufruf**
(`ast.Call` auf `ist_abgeschlossen`). Danach färbt Mutation 1 rot. Ohne den Eichfall wäre
der Mangel nicht aufgefallen — das ist der Grund, warum §7 ihn verlangt.

---

## 5. Abnahme

| Forderung aus §7, Stufe 2 | Erfüllt | Belegstelle |
|---|---|---|
| Querabfragen ohne obere Zeitgrenze bekommen eine | ja — 5 von 5 Stellen | `belege/01-bestandsaufnahme.txt`, Gegenkontrolle in Abschnitt 3 |
| Bestätigungszeitstempel auf Schlusszeit | entfällt begründet — `ts` ist Intervallbeginn, die Schlussfrage steht als eigenes Pflichtfeld daneben | `venue/protocol.py:258-271` |
| Kein Griff in die laufende Kerze | ja — `live_konsole.py` filtert jetzt, `live_betrieb.py` tat es schon | Abschnitt 2.3 |
| Determinismus-Tor, zweimal derselbe Abschnitt, Byte-Gleichheit | ja — 9 Fälle, zwei Ebenen | `tests/test_zeitschranken.py` |
| **Roter Eichfall** bei entfernter Zeitschranke | ja — drei Mutationen wirklich gefahren | `belege/03-eichfaelle.txt` |

**Stufe 2 ist abgenommen.**

### 5.1 Was diese Abnahme ausdrücklich nicht deckt

1. **Die 12 betroffenen Manifeste werden nicht neu erzeugt.** Dafür bräuchte es ein
   laufendes, angemeldetes Terminal, das hier nicht vorliegt. Sie bleiben liegen und
   bleiben unbrauchbar — wie schon in Stufe 1 festgehalten. Der Fix wirkt auf **künftige**
   Läufe.
2. **Die drei Werkzeuge sind nicht end-zu-end gefahren.** `atr_messung`, `aufloesung` und
   `ereignisstudie` verlangen ein Terminal. Geprüft sind ruff, mypy und die Testfälle;
   der Lauf gegen ein echtes Terminal ist der Schritt des Betreibers. Bis dahin gilt für
   diese drei Pfade: **gelesen, nicht ausgeführt**.
3. **Der D1/H4-Zeitumstellungsmangel bleibt.** Bekannt, begründet, festgenagelt — und
   durch diese Stufe erstmals überhaupt relevant für `aufloesung.py`, weil das Werkzeug
   die Schranke vorher gar nicht benutzte. Der Netto-Effekt bleibt trotzdem positiv
   (siehe Abschnitt 3).
4. **Das Tor prüft eine Strategie, nicht alle.** Gefahren wird
   `moving_average_crossover(5, 20)` über 420 Fixture-Bars. Eine zustandsbehaftete
   Strategie mit längerem Gedächtnis könnte anders reagieren.

---

## 6. Was unterwegs dazukam — und warum

### 6.1 Die fremde Arbeit musste eingecheckt werden

Stufe 0 hatte 13 fremde, nicht eingecheckte Dateien (+1.162/−52) gemessen und bewusst
liegen lassen. Stufe 2 musste `tools/ereignisstudie.py` anfassen — eine dieser 13 —, und
damit war der eigene Anteil vom fremden nicht mehr trennbar, ohne einen der beiden zu
verlieren.

Gelöst durch Trennung statt Vermischung: die Fremdarbeit wurde exakt rekonstruiert (die
gemessene Differenz stimmt mit dem Stufe-0-Befund überein: **+1.162/−52 über 13 Dateien**)
und als **eigener Commit** `cc0d340` gesichert, ausdrücklich als nicht meine Arbeit
gekennzeichnet. Erst danach ist die Stufe-2-Arbeit darauf aufgesetzt worden.

Damit ist auch die Empfehlung aus Stufe 0 erledigt („die offene Welle 4 abschließen oder
verwerfen"). Der Inhalt ist unverändert übernommen und von mir **nicht geprüft**.

### 6.2 Eine Regression, die meine Änderung verursacht hat

Der Tick-Aufruf ist ein neuer Anspruch an das Terminal — und **15 bestehende Testfälle**
in drei Dateien fielen daran um, weil ihre Attrappen nur `rates` konnten. Das ist kein
Argument gegen die Änderung: eine Attrappe, die nicht sagen kann, welche Zeit am Platz
ist, ist unvollständig, seit die Frage gestellt wird.

Behoben, indem jede der drei Attrappen eine `tick`-Methode bekam. Ihre Uhr steht bewusst
weit voraus (Jahr 2999), damit diese Fälle weiter messen, wofür sie geschrieben sind —
Scheibenbildung und Zeitdrehung —, und nicht versehentlich zur Kantenprüfung werden. Die
Kante misst `tests/test_zeitschranken.py`.

### 6.3 Drei Zahlen und eine Zeile nachgezogen

Der Zustand nach `cc0d340` und meiner Arbeit ließ vier Tore rot stehen. Alle vier sind
behoben, keines durch Absenken einer Schwelle:

| Rot | Ursache | Behebung |
|---|---|---|
| `ruff` F841 | unbenutzte Variable in **meinem** Eichfall | entfernt |
| `ruff` E501 | zu lange Zeile in `execution/risiko_zustand.py`, aus `cc0d340` geerbt | umgebrochen |
| `gen_docs --check` | `MODULES.md` veraltet | neu erzeugt |
| `check_doc_numbers` | README-Kennzahlen und eine „17 Fälle"-Angabe in `ABSCHLUSS-3a/01-AUFLOESUNG.md` | 1198→1229, 15319→15415, 17→18 mit Berichtigungsvermerk |

**Schlussstand** (Beleg: `belege/04-schlusspruefung.txt`): `check_docs_claims`,
`check_doc_numbers`, `gen_docs --check`, `ruff` und `mypy` je **Exit 0**; `pytest`
**1.400 bestanden, 1 fehlgeschlagen**.

Der eine rote Fall ist der in Stufe 0 gefundene Defekt: `tools/live_betrieb.py:604`
schreibt ein rohes `datetime` ins Journal und wirft `TypeError` — auf dem
risikoreduzierenden Pfad. Er liegt seit `6cf80a6` im eingecheckten Code; der ihn zeigende
Test kam mit `cc0d340` dazu. **Er wird hier nicht behoben:** das ist Stufe 4 (V5), und der
Auftrag verlangt genau eine Stufe.
