# Stufe 1 — Historie beschaffen

*Erhoben 2026-08-19. Rohausgaben in `belege/`. Was gelesen und nicht ausgeführt wurde,
ist so gekennzeichnet.*

**Auftrag (§7, Stufe 1):** Mindestens drei Jahre feiner Kursdaten aus einer **vom
Handelsplatz unabhängigen** Quelle, versioniert und gehasht, mit Lücken- und
Ausreißerbericht. Kaltstartmenge und Aufbewahrungsfrist so ändern, dass Historie nicht
laufend gelöscht wird.

---

## 1. Der Ausgangsbefund: die vorhandene Historie erfüllt Stufe 1 nicht

`AUFTRAG/zustand.md` hat diese Stufe mit „erst nachmessen, dann über Beschaffung
entscheiden" begonnen. Die Nachmessung ergibt zwei Befunde, die beide gegen die
vorhandenen Reihen sprechen — und keiner davon betrifft die Tiefe.

### 1.1 Alle 15 Reihen stammen vom Handelsplatz

Gemessen über alle 15 Manifeste in `config/reihen/` (Beleg: `belege/01-manifeste.txt`):

| Instrument | D1 | H1 | H4 | Zeitraum | Quelle |
|---|---:|---:|---:|---|---|
| DE40 | 3.537 | 60.450 | 16.739 | 2012-08-06 → 2026-08-17 (14,0 J) | `mt5-terminal-read-only` |
| EURUSD | 7.181 | **99.998** | 43.012 | 1999-01-04 → 2026-08-17 (27,6 J) | `mt5-terminal-read-only` |
| GBPJPY | 8.658 | **99.998** | 44.470 | 1993-04-19 → 2026-08-17 (33,3 J) | `mt5-terminal-read-only` |
| NVDA | 5.760 | 40.566 | 11.539 | 2003-09-10 → 2026-08-14 (22,9 J) | `mt5-terminal-read-only` |
| XAUUSD | 5.699 | **99.998** | 33.976 | 2004-06-11 → 2026-08-17 (22,2 J) | `mt5-terminal-read-only` |

**Reihen aus einer vom Handelsplatz unabhängigen Quelle: 0 von 15.**

Das ist nicht nur ein formaler Verstoß gegen die Stufenvorgabe. Der Lader des Standes
begründet im eigenen Modulkopf, warum: *„Broker-interne CFD-Feeds sind synthetische
Hauspreise; ein Backtest darauf misst die Eigenheiten eines Brokers, nicht den Markt."*
(`mt5_trading_ai/data/loader.py`, Zeilen 5–8). Die Regel steht im Code — die Daten, mit
denen gearbeitet wurde, verletzen sie.

**Nebenbefund zur Tiefe:** drei H1-Reihen stehen auf **exakt 99.998** Bars. Eine
natürliche Reihe endet nicht dreimal auf derselben Zahl. Das ist die Bar-Obergrenze des
Terminals, nicht das Ende der Historie — die H1-Tiefe von 16–17 Jahren ist also
abgeschnitten, nicht erschöpft. *(Gemessene Zahl; die Zuordnung zur Terminal-Einstellung
ist eine Schlussfolgerung, keine Messung.)*

### 1.2 Die Bars liegen überhaupt nicht vor

Gemessen (Beleg: `belege/02-bars-fehlen.txt`): Im gesamten Repository und Arbeitsbaum
existieren **0** Bar-Dateien außerhalb von `tests/fixtures/` — dort liegen zwei kleine
Smoke-Fixtures. Gesucht wurde nach `*.csv`, `*.bi5`, `*.parquet`.

Der Grund steht in `tools/ereignisstudie.py:200-218`: `_lade_kerzen` öffnet bei **jedem
Lauf** `RealMt5Terminal(allow_write=False)` und liest die Reihe live aus dem Terminal.
Persistiert wird nur das Manifest.

**Folge:** Die 15 Prüfsummen sind nicht nachprüfbar. Wer sie prüfen will, braucht ein
laufendes, angemeldetes Terminal desselben Brokers — und selbst dann liefert der Broker
möglicherweise eine andere Reihe als am 2026-08-17. Die Reproduzierbarkeit, die der
Simulator im Kopf zusichert („zwei gleiche Läufe ergeben denselben Bericht"), ist auf der
Datenseite nicht gedeckt.

Damit hängt auch die `data_checksum` in allen sieben Einträgen von `TRIALS.jsonl` an
Reihen, die nicht mehr vorliegen.

### 1.3 Was die Kaltstart-/Aufbewahrungs-Vorgabe hier bedeutet

Gemessen: In `mt5_trading_ai/` und `tools/` gibt es **keine** Aufbewahrungsfrist, keinen
Löschlauf und keine Kappung, die Historie entfernt (Suche über `retention|aufbewahr|purge|
loesch|delete|unlink|rmtree`; alle Treffer betreffen Purge/Embargo der Zeitreihen-Splits,
also Leckageschutz, nicht Datenlöschung).

Die Vorgabe stammt aus einem Stand mit Datenbank und 45-Tage-Frist. **Hier ist sie
gegenstandslos — aber aus dem umgekehrten Grund als erhofft:** es wird nichts gelöscht,
weil nichts gespeichert wird. Die wirksame Kappung ist die Terminal-Obergrenze aus 1.1.

Die richtige Umsetzung der Vorgabe in diesem Stand ist deshalb nicht „Frist verlängern",
sondern **Reihen überhaupt persistieren**. Das ist Gegenstand von Abschnitt 2.

---

## 2. Beschaffung aus unabhängiger Quelle

### 2.1 Quellenwahl

Der Stand trägt bereits ein Beschaffungswerkzeug für eine unabhängige Quelle:
`tools/fetch_data.py` lädt **Dukascopy** (institutionell, keyless, kostenlos, Bid-Seite).
Es ist damit ausdrücklich **kein Haltepunkt nach §4 („Geld")** — die freie Quelle ist
vorhanden und ausgeschöpft, bevor über eine kostenpflichtige gesprochen würde.

Unabhängigkeit: Dukascopy (Schweizer Bank) ist nicht der Handelsplatz, gegen den
gehandelt würde (IC Markets EU laut `config/broker_costs.json`). Die Anforderung ist
damit erfüllt.

**Abdeckungsgrenze, gemessen:** `DUKASCOPY_PRICE_DIVISORS` in
`mt5_trading_ai/data/loader.py` deckt **10 FX-Paare** ab. Von den fünf Instrumenten des
Prüfuniversums sind damit **2 erreichbar** (EURUSD, GBPJPY); XAUUSD, DE40 und NVDA sind
es nicht. Sie über dieselbe Quelle zu holen, verlangt eine Erweiterung der Divisor-Tabelle
und der Symbolnamen — neue Wirkung an bestehendem Code, gehört begründet und mit rotem
Eichfall gemacht, nicht nebenbei.

### 2.2 Netzlage in dieser Umgebung — gemessen

Dukascopy drosselt hier hart. Gemessen:

- Ein roher Abruf ohne Browser-Kennung: **HTTP 429 Too Many Requests**.
- Der erste Lauf von `tools/fetch_data.py --timeframe H1` (36 Monatsdateien) brach nach
  **1 von 36** Monaten mit `TimeoutError: The read operation timed out` ab — trotz des
  eingebauten Backoffs (6 Versuche, 2–12 s).
- Tageskerzen liegen bei Dukascopy **jahresweise** (3 Abrufe für 3 Jahre) statt
  monatsweise (36 Abrufe). Dieser Weg lief in einem Zug durch.

**Daraus die Reihenfolge dieser Stufe:** zuerst D1 (wenige Abrufe, sofort prüfbares
Artefakt), parallel H1 mit geduldigem Vorwärmen des `.bi5`-Zwischenspeichers, den
`tools/fetch_data.py --cache` ohnehin nutzt. Für das Vorwärmen wurde **kein zweites
Abrufwerkzeug ins Repo gelegt** — ein Wegwerf-Skript im Ablagebereich legt nur die
Rohdateien an den Ort, an dem das vorhandene Werkzeug sie sucht. Dekodierung,
Qualitätstor und Manifest macht ausschließlich `tools/fetch_data.py`.

### 2.3 Ergebnis D1 — bestanden

Bestätigt durch Ausführung (Beleg: `belege/03-abruf-d1.txt`):

| | |
|---|---|
| Instrument / Zeitrahmen | EURUSD D1 |
| Quelle | `dukascopy-bid-day` — **unabhängig vom Handelsplatz** |
| Zeitraum | 2022-01-03 … 2024-12-31 (**3,0 Jahre**) |
| Bars | **782** (erwartet 779) |
| Lücke | **0,000 %** |
| Ausreißer / ungültige OHLC / Duplikate | **0 / 0 / 0** |
| Qualitätstor | **BESTANDEN** |
| Bars-Prüfsumme | `78683f92b090b99c9204ebbb0e700efd0abeebd87cf03b63e2089f7ae2cc8602` |
| Manifest-Prüfsumme | `0b3b8b5c2a433298e7d62aaacf58fac5f7caff3ff90671456ae08bf20c238a1c` |

**Reproduzierbarkeit gegengeprüft:** dieselbe Bars-Prüfsumme `78683f92…` war schon in
einem früheren, unabhängig gefahrenen Abruf desselben Zeitraums entstanden. Zwei
getrennte Läufe, dieselbe Zahl.

**Ende-zu-Ende am Backtest-Rand** (Beleg: `belege/04-backtestrand.txt`):
`load_verified_csv` liest die Reihe an, Lader- und Manifest-Prüfsumme sind identisch, und
das Qualitätstor liefert **Zahlen statt „unbekannt"** — genau das Abnahmekriterium:
`expected_bars=781, present_bars=782, gap_ratio=0.0, duplicate=0, unaligned=0,
non_monotonic=0, naive=0, outlier=0, zero_volume=0, outside_session=0, invalid_ohlc=0,
passed=True, reasons=()`.

*Zu `present_bars > expected_bars`:* keine Lücke, sondern die Gegenrichtung — die
Feiertagsliste zieht einen Tag von der Erwartung ab, den Dukascopy liefert. Die Erwartung
ist an dieser Stelle konservativ.

**Gegenprobe gegen eine zweite Quelle (Yahoo), gemessen:** über 766 vergleichbare Tage
Median **28,20 bps**, Mittel 37,00 bps, max 209,45 bps Abweichung Close-zu-Close; 16 von
782 Yahoo-Bars waren OHLC-ungültig und wurden verworfen. Das ist **kein** Beleg für einen
Fehler bei Dukascopy — Yahoo trägt bekanntermaßen abweichende Schlusszeiten und
DST-Artefakte —, aber es ist die gemessene Größenordnung, um die zwei freie Quellen
auseinanderliegen, und sie gehört in jede spätere Kostenrechnung als Unsicherheit.

### 2.4 Ergebnis H1 — bestanden

Vor dem Volllauf wurde die Kette am vollständig zwischengespeicherten Jahr 2022 erprobt,
ohne Netz (Beleg: `belege/06-h1-vorprobe.txt`): 8.760 Rohkerzen → 2.520 handelsfreie
Füllkerzen verworfen → 6.240 Bars, Lücke 0,000 %, bestanden. Erst danach der Volllauf.

Bestätigt durch Ausführung (Beleg: `belege/07-h1-volllauf.txt`):

| | |
|---|---|
| Instrument / Zeitrahmen | **EURUSD H1** |
| Quelle | `dukascopy-bid-hour` — **unabhängig vom Handelsplatz** |
| Session-Anker | `fx-ny17` (New York 17:00, sommerzeitfest) |
| Zeitraum | 2022-01-02T22:00Z … 2024-12-31T21:00Z (**3,0 Jahre**) |
| Rohkerzen | 8.760 + 8.760 + 8.784 = 26.304 |
| davon handelsfreie Füllkerzen verworfen | 7.589 |
| **Bars** | **18.715** (erwartet 18.692) |
| Lücke | **0,016 %** |
| Ausreißer | **3** |
| Duplikate / unausgerichtet / nicht-monoton / naive Zeitstempel | **0 / 0 / 0 / 0** |
| ungültige OHLC / Null-Volumen / außerhalb Session | **0 / 0 / 0** |
| Qualitätstor | **BESTANDEN**, `reasons = ()` |
| Bars-Prüfsumme | `8cdebf057bce1ffc7489904d61f2fbb7d7d62b8658927e5c69574c9fb4247daa` |
| Manifest-Prüfsumme | `9e64a3ff2088264ba9b1ac33b274f4953029d5820b3474922138453916d7a480` |

**Reproduzierbarkeit gegengeprüft, zum zweiten Mal:** die Barzahl **18.715** ist exakt die,
die ein früherer Lauf des Vorhabens auf demselben Zeitraum erhalten hat. Zusammen mit der
D1-Prüfsumme sind das zwei unabhängige Übereinstimmungen.

**Ende-zu-Ende am Backtest-Rand:** `load_verified_csv` liest die Reihe an, Lader- und
Manifest-Prüfsumme sind identisch, `passed=True`, `reasons=()`.

**Zwei Lückenzahlen, und welche gilt.** Das Werkzeug meldet 0,016 % (Erwartung 18.692),
ein Direktaufruf von `assess_bars` 0,277 % (Erwartung 18.767). Der Unterschied ist **nicht**
die Reihe, sondern die Feiertagsliste: `assess_or_raise` setzt
`holidays=DEFAULT_FX_HOLIDAYS` als Vorgabe, `assess_bars` dagegen `frozenset()`. Maßgeblich
ist die Zahl des Werkzeugs, weil der Backtest-Rand denselben Vorgabewert benutzt. Die 75
Bars Unterschied sind die FX-Feiertage der drei Jahre.

**Die drei Ausreißer** liegen auf 2022-09-13 12:00, 2022-09-26 00:00 und 2022-11-10 13:00
UTC — alle im Großbewegungsjahr 2022. Dass es sich um echte Volatilität und nicht um
Datenfehler handelt, ist aus der Datumslage **eingeordnet, nicht gemessen**; ein Abgleich
gegen eine Ereignisliste hat nicht stattgefunden.

### 2.5 Was die Vorgabe „Kaltstartmenge und Aufbewahrungsfrist" hier konkret wurde

Nicht „Frist verlängern" (es gibt keine), sondern **persistieren**: die Reihen liegen jetzt
als Datei vor, mit Prüfsumme und Manifest, und werden nicht mehr bei jedem Lauf aus dem
Terminal neu gelesen. `daten/` ist gitignoriert — die Lizenz erlaubt nur private Nutzung
und Backtest —, eingecheckt wird der Datensatzverweis in `config/reihen_unabhaengig/`.

---

## 3. Abnahme

Das Abnahmekriterium aus §7, Stufe 1 lautet: *„ein eingecheckter Datensatzverweis mit Hash,
Zeitraum, Zeilenzahl je Zeitrahmen und Qualitätsbericht; die Datenqualitätsprüfung liefert
eine Zahl statt ‚unbekannt'."*

| Forderung | Erfüllt | Belegstelle |
|---|---|---|
| Mindestens drei Jahre | ja — 2022-01-02 … 2024-12-31, **3,0 Jahre** | `belege/03-abruf-d1.txt`, `belege/07-h1-volllauf.txt` |
| **Feine** Kursdaten | ja — H1, 18.715 Bars | `belege/07-h1-volllauf.txt` |
| Vom Handelsplatz **unabhängige** Quelle | ja — `dukascopy-bid-hour` / `-day`; der Handelsplatz wäre IC Markets EU | `config/reihen_unabhaengig/*.manifest.json` |
| Versioniert und gehasht | ja — `loader_version`, `bars_checksum`, `price_divisor`, `session` je Reihe | `config/reihen_unabhaengig/` |
| Lücken- und Ausreißerbericht | ja — H1: Lücke 0,016 %, 3 Ausreißer; D1: 0,000 %, 0 Ausreißer | `belege/04-backtestrand.txt`, `belege/07-h1-volllauf.txt` |
| **Eingecheckter** Datensatzverweis mit Hash, Zeitraum, Zeilenzahl je Zeitrahmen | ja — zwei Manifeste, D1 und H1 | `config/reihen_unabhaengig/EURUSD_D1.manifest.json`, `…_H1.manifest.json` |
| Qualitätsprüfung liefert **eine Zahl** statt „unbekannt" | ja — elf bezifferte Felder je Reihe, `reasons = ()` | `belege/04-backtestrand.txt`, `belege/07-h1-volllauf.txt` |
| Historie wird nicht laufend gelöscht | ja — nichts löscht; die Reihen sind jetzt persistiert statt live gelesen | Abschnitt 2.5, `belege/02-bars-fehlen.txt` |

**Stufe 1 ist abgenommen.**

### 3.1 Was diese Abnahme ausdrücklich **nicht** deckt

Damit die nächste Stufe nicht mehr voraussetzt, als hier belegt ist:

1. **Ein Instrument, nicht fünf.** Beschafft ist EURUSD (D1 und H1). Das Prüfuniversum des
   Standes umfasst fünf Instrumente. Über Dukascopy sind davon nur die FX-Paare erreichbar
   — `DUKASCOPY_PRICE_DIVISORS` deckt 10 FX-Paare ab, also EURUSD und GBPJPY; XAUUSD, DE40
   und NVDA nicht. Für sie wäre die Divisor-Tabelle und die Symbolzuordnung zu erweitern:
   eine echte Änderung mit rotem Eichfall, keine Nebensache.
2. **Drei Jahre, nicht sechzehn.** Der Handelsplatz-Bestand reichte nominell 14–33 Jahre
   zurück. Die unabhängige Reihe reicht drei Jahre. Wer mehr will, verlängert den Abruf —
   das ist Rechenzeit und Geduld, kein neues Werkzeug.
3. **Die 15 alten Manifeste bleiben liegen und bleiben unbrauchbar.** Sie werden nicht
   gelöscht (sie sind der Beleg dessen, was am 2026-08-17 gemessen wurde), aber keine
   spätere Stufe darf auf ihnen aufbauen. Damit hängt auch die `data_checksum` der sieben
   Einträge in `TRIALS.jsonl` an Reihen, die nicht mehr vorliegen — das ist für die
   Deflationsrechnung in Stufe 3 zu berücksichtigen.
4. **Kein Kostenbezug.** Diese Stufe hat Kursdaten beschafft, sonst nichts. Ob die
   Kostenannahmen des Standes zu diesen Daten passen, ist Stufe 3.

### 3.2 Zustand der Tore am Ende der Stufe

`check_docs_claims` und `check_doc_numbers` waren nach dem Stufe-0-Commit rot — **meine
Regression**, siehe `fehler.md` F-004 und `entscheidungen.md` E-004. Behoben, ohne eine
Schwelle zu senken, mit rotem und grünem Eichfall und acht neuen Testfällen
(`tests/test_auftrag_doku_tore.py`).

Im Arbeitsbaum bleiben die Tore dennoch rot — vollständig wegen der 13 fremden, nicht
eingecheckten Dateien aus „Welle 4" (`gen_docs --check`: MODULES.md veraltet;
`check_doc_numbers`: README-Kennzahlen 1190→1215 und 15319→15376). Gegenprobe mit
beiseitegelegter Fremdarbeit: alle drei Tore **EXIT 0** (Beleg: `belege/05-doku-tore.txt`).
