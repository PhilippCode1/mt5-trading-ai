# Stufe 0 — Bestand und Wahl des Stands

*Erhoben 2026-08-19. Jede Zahl in diesem Bericht ist gemessen; die Rohausgaben liegen in
`belege/`. Wo eine Aussage nur gelesen und nicht ausgeführt wurde, steht das dabei.*

---

## 1. Welche Stände liegen tatsächlich vor

Gesucht wurde über das gesamte Benutzerverzeichnis nach Verzeichnissen mit `.git` (Tiefe 3)
und nach Verzeichnisnamen mit `mt5`, `mastertrade` oder `trading` (Tiefe 4). Gefunden
wurden fünf Kandidaten, davon drei mit Versionsverwaltung.

**Verworfen ohne Messung, weil keine Substanz:**

| Verzeichnis | Grund |
|---|---|
| `Cursor1/HelioswarmTrading-Ai` | 25 Dateien, kein `.git` |
| `Cursor1/Ki Trading` | 0 Dateien |

Beleg: `belege/01-kandidaten-git.txt`.

---

## 2. Die geforderte Tabelle

| | `mt5_trading_ai` | `bitget-btc-ai` | `strategy-validation` |
|---|---|---|---|
| **Pfad** | `C:\Users\Acer\mt5_trading_ai` | `…\Cursor1\bitget-btc-ai` | `…\Cursor1\strategy-validation` |
| **Letzter Commit** | `6cf80a6` — **2026-08-18** | `5c39ebb` — 2026-08-11 | `8aca814` — 2026-08-06 |
| **Alter des Standes** | **1 Tag** | 8 Tage | 13 Tage |
| **Commits gesamt** | 79 | 121 | 10 |
| **Commits letzte 30 Tage** | 79 (100 %) | 85 (70 % von 121) | 10 (100 %) |
| **Zeilen Produktionscode** | **15.376** in 49 Dateien | 101.323 in `services/*/src` | 871 eigen + 3.577 vendoriert |
| **Anzahl Dienste** | **0** — ein Python-Paket, kein Server, kein Container | 15 unter `services/` | 0 |
| **Handelsplatz-Adapter** | **MT5** (76 Dateien mit `MetaTrader5`/`mt5`, **0** mit `bitget`) | **Bitget** (445 Dateien mit `bitget` unter `services/*/src`) | keiner — Offline-Validierung, Datenquelle Binance |
| **Simulator mit Kostenmodell** | **ja** — `backtest/engine.py`, 2.492 Zeilen im Paket, `order_roundturn_cost` in Zeile 292 verdrahtet, 6 × `LookAheadError` | **nein** — `runner_replay.py` enthält **0** Treffer für `fee\|slippage\|funding\|commission\|spread` | **nein** — 0 Treffer für Simulator-/Engine-/Backtest-Definitionen im eigenen `src/`, 0 Ergebnisartefakte |
| **Ausführungsstrecke** | **ja** — `venue/` 4.089 + `execution/` 4.161 Zeilen | ja, aber auf Bitget | nein |
| **Testsuite** | **1.384 gesammelt, 1.381 grün, 3 rot** (bestätigt durch Ausführung, `belege/04-testsuite.txt`) | 2.050 gesammelt, 2 Sammelfehler (Vorbericht) | 4 Testdateien, 610 Zeilen (gelesen, nicht ausgeführt) |
| **Versuchsregister** | **ja** — `TRIALS.jsonl`, 7 Einträge | nein — `TRIALS.jsonl` existiert nicht | nein |
| **Historie** | D1/H4 bis 33,3 J, H1 bis 17,1 J über 15 Reihen mit SHA-256-Manifesten (gelesen aus `ABSCHLUSS-3a/00-UEBERSICHT.md`, in Stufe 1 nachzumessen) | 300 Bars je Zeitrahmen, kein Backfill (Vorbericht) | keine geladen (`PREREGISTRATION.md`: „Keine Marktdaten geladen") |

Belege: `belege/01-kandidaten-git.txt`, `belege/02-codeumfang.txt`,
`belege/03-simulator-und-venue.txt`, `belege/04-testsuite.txt`.

---

## 3. Die Prüfung des Haltefalls aus §2.4

Der Auftrag verlangt anzuhalten, **wenn beide Stände tragende, nicht ineinander
überführbare Substanz enthalten — etwa wenn in dem einen ein funktionierender Simulator
und in dem anderen die aktuelle Ausführungsstrecke liegt.**

Genau diese Konstellation wurde geprüft. Sie liegt **nicht** vor:

- **Simulator und Ausführungsstrecke liegen im selben Stand.** `mt5_trading_ai` trägt
  beides: `backtest/engine.py` (2.492 Zeilen im Paket `backtest/`) und `venue/` +
  `execution/` (8.250 Zeilen zusammen). Es gibt nichts zusammenzuführen.
- **`strategy-validation` hat keinen Simulator.** Gemessen: 0 Treffer für
  `def run_backtest|simulate|run_engine` oder `class *Engine|Simulator|Backtest` im
  eigenen `src/` und `scripts/`; 0 Ergebnisartefakte (`.jsonl`, `.parquet`, `.csv`) im
  ganzen Baum. Vorhanden sind 871 Zeilen Zubringer: `costs.py`, `splits.py`, `spread.py`,
  `data/bars.py`, `data/binance.py`, `bootstrap.py`, `config.py`. Die eigene `PROGRESS.md`
  endet mit „Danach: … -> Engine -> Metriken/DSR -> …" — die Maschine war der **nächste**
  Schritt, nicht der erledigte.
- **`bitget-btc-ai` hat keinen Simulator.** Der einzige verbliebene Läufer,
  `runner_replay.py`, enthält gemessen **0** Vorkommen von Gebühren, Spread, Slippage,
  Finanzierung oder Kommission.

Es gibt damit **keine** nicht überführbare Substanz. Der Lauf wird nicht angehalten;
die Wahl ist zulässig.

---

## 4. Was in den verworfenen Ständen liegt und ob es verloren geht

Diese Prüfung gehört zur Wahl, nicht zur Rechtfertigung danach.

| Stand | Was darin steckt | Überführbar? |
|---|---|---|
| `bitget-btc-ai` | 15 Dienste, Dashboard (~100 k Zeilen TypeScript), Bitget-REST/WS, Datenmodell mit 93 Migrationen | **Gegenstandslos**: der Handelsplatz ist im Wirtschaftsraum des Auftraggebers nicht verfügbar. Nach §9.2 des Auftrags eine harte Grenze, kein Umbaufall. Der Stand ist zugleich der, den der Prüfbericht vom 2026-08-19 mit einem Gesamtbefund von 2/10 bewertet hat. |
| `strategy-validation` | **Eingefrorene Vorregistrierung** mit neun Kriterien (K1–K9), Kostenmodell `fees.json`, `costs.py`, gepurgte Splits, Binance-Lader, Datenqualitätsbericht | **Teilweise überführbar, aber gegenstandslos für das Ziel**: die Vorregistrierung prüft ausdrücklich den *Bitget*-Composite-Score (Gewichte 0,22/0,20/0,22/0,10/0,18/0,08, Quelle `signal-engine/config.py:91-100`) auf *Krypto*-Daten. Der gewählte Stand handelt weder diesen Score noch diese Anlageklasse. Der **methodische** Gehalt — neun vorab bezifferte Kriterien, „ein knapp verfehltes Kriterium ist ein verfehltes" — ist bereits im gewählten Stand vorhanden (`gates/criteria.py`, `ABBRUCH.md` §2 mit 60 vorregistrierten Versuchen). |

---

## 5. Der Zustand des gewählten Stands, gemessen

**Testsuite:** 1.384 gesammelt, **1.381 grün, 3 rot** in 56 s (bestätigt durch Ausführung,
`belege/04-testsuite.txt`). Die drei roten Fälle im Einzelnen:

| Test | Art | Befund |
|---|---|---|
| `test_readme_source_lines_matches_code` | Doku-Drift-Tor | README nennt 15.319 Zeilen, gemessen sind **15.376**. Differenz **57 Zeilen**. Das Tor arbeitet wie gebaut — es meldet, dass die Kennzahl dem Code nachhinkt. |
| `test_readme_test_function_count_matches_code` | Doku-Drift-Tor | dieselbe Ursache |
| `test_die_hoechsthaltedauer_greift_genau_auf_der_grenze` | **sachlicher Defekt** | siehe unten |

**Der sachliche Defekt** (Beleg: `belege/05-defekt-journal-datetime.txt`):
`tools/live_betrieb.py:604` schreibt in `journal.schreib(...)` eine Zeile, die ein rohes
`datetime`-Objekt enthält; `tools/live_betrieb.py:173` gibt das an `json.dumps` weiter und
erhält `TypeError: Object of type datetime is not JSON serializable`.

Das ist kein Testfehler, sondern Produktionscode. Getroffen wird der Pfad genau dann, wenn
eine Position die Höchsthaltedauer erreicht — also auf dem **risikoreduzierenden** Pfad.
Nach Sperre V5 des Auftrags („Keine Sperre blockiert den Risikoabbau") ist das der
empfindlichste Ort, den ein solcher Fehler treffen kann. Er gehört nach Stufe 4; er wird
hier **gemeldet, nicht behoben**, weil Stufe 0 nicht in fremde Stufen greift.

> **Berichtigung 2026-08-19:** Die hier als Produktionsdefekt geführte Stelle war keiner.
> Der rote Fall entstand allein aus dem Testaufbau (ausgetauschte Uhr, geteilter Modulname
> für Uhr und Typ). Vollständige Ursachenanalyse: [`fehler.md`, F-008](../../fehler.md#f-008--ich-habe-einen-testfehler-drei-stufen-lang-als-produktionsdefekt-geführt).
> Behoben am 2026-08-19.

**Was ich ausdrücklich nicht gemessen habe:** ob die 15 Reihen-Manifeste vollständig und
prüfsummengedeckt sind, ob der Simulator gegen echte Historie läuft, ob die Kostenzahlen
tragen. Das ist Stufe 1 und 3. Alle Aussagen dazu in diesem Bericht sind mit „gelesen,
nicht ausgeführt" gekennzeichnet.

---

## 5a. Der Arbeitsbaum ist nicht der eingecheckte Stand

Diese Feststellung gehört in Stufe 0, weil sie die Bezugsgröße aller Messungen oben ändert.

**Gemessen** (Beleg: `belege/06-arbeitsbaum.txt`): Neben `AUFTRAG/` trägt der Arbeitsbaum
**13 geänderte, nicht eingecheckte Dateien mit 1.162 hinzugefügten und 52 entfernten
Zeilen** — darunter zwei Produktionsdateien (`execution/risiko_zustand.py` +53,
`execution/risk_manager.py` +46) und acht Testdateien. Der letzte Commit `6cf80a6` trägt
die Nachricht „Welle 3 — Testschicht für die Beweiswerkzeuge, 29 Defekte gefunden"; die
offene Arbeit sieht nach deren Fortsetzung aus.

**Folge für Beleg 4.** Das Ergebnis „1.381 grün, 3 rot" ist am **Arbeitsbaum** gemessen,
nicht an `6cf80a6`. Das ist die richtige Bezugsgröße für die Frage „welcher Stand lebt",
muss aber benannt werden.

**Folge für den sachlichen Defekt.** Er wird dadurch **schwerer**, nicht leichter. Gemessen:

- Der rote Test `test_die_hoechsthaltedauer_greift_genau_auf_der_grenze` kommt in
  `HEAD:tests/test_live_betrieb_sperren.py` **0 ×** vor, im Arbeitsbaum **1 ×** — er ist
  neu und nicht eingecheckt.
- `git diff --stat -- tools/live_betrieb.py` ist **leer** — die defekte Stelle ist seit
  `6cf80a6` unverändert.

Ein früherer Lauf hat also einen Test geschrieben, der einen **bereits eingecheckten**
Defekt im Produktionscode freilegt. Der Test ist nicht falsch; der Code ist es. Genau so
soll ein roter Eichfall wirken.

**Was ich damit nicht tue.** Ich checke diese fremde, halbfertige Arbeit nicht ein. Ein
Commit unter meiner Stufen-Nachricht würde 1.162 Zeilen fremder Arbeit falsch zuordnen.
Der Stufe-0-Commit umfasst ausschließlich `AUFTRAG/`.

**Empfehlung an den nächsten Lauf:** die offene „Welle 4" abschließen oder verwerfen, bevor
Stufe 1 beginnt — 1.162 uncommittete Zeilen sind ein Verlustrisiko und machen jede spätere
Messung mehrdeutig.

**Doku-Wächter des Standes gegen den neuen Ordner geprüft** (bestätigt durch Ausführung):
`python tools/check_docs_claims.py` → `ok - 32/32 Markdown-Dateien, keine Zusicherung ohne
Beleg`, Exit 0. `AUFTRAG/` bricht kein bestehendes Tor.

> **Berichtigung vom 2026-08-19 (Stufe 1), alter Stand bleibt oben stehen.**
> Der letzte Satz war schon beim Schreiben überholt. Die Messung lag **vor** dem Commit,
> und beide Doku-Tore zählen `git ls-files` — `AUFTRAG/` war zu diesem Zeitpunkt untracked
> und wurde gar nicht mitgezählt. Nach dem Commit meldete `check_docs_claims` Exit 1
> („41 Markdown-Dateien, erlaubt sind 32") und `check_doc_numbers` Exit 1 (zwei Treffer in
> `AUFTRAG/`). Zwei weitere Pflicht-Tore hatte ich vor dem Push gar nicht gefahren.
> Ursache und Behebung: `fehler.md` F-004, `entscheidungen.md` E-004,
> Beleg `stufen/01-historie/belege/05-doku-tore.txt`. Die Zahlen der Bestandsaufnahme
> selbst sind davon nicht berührt.

---

## 6. Abnahme dieser Stufe

| Forderung aus §7, Stufe 0 | Erfüllt | Belegstelle |
|---|---|---|
| Tabelle über alle Kandidaten mit gemessenen Zahlen | ja | Abschnitt 2 dieses Berichts |
| Letzter Commit mit Datum je Kandidat | ja | `belege/01-kandidaten-git.txt` |
| Commits der letzten 30 Tage je Kandidat | ja | `belege/01-kandidaten-git.txt` |
| Zeilen Produktionscode je Kandidat | ja | `belege/02-codeumfang.txt` |
| Anzahl Dienste je Kandidat | ja | `belege/03-simulator-und-venue.txt` |
| Handelsplatz-Adapter Bitget oder MT5 je Kandidat | ja | `belege/03-simulator-und-venue.txt` |
| Begründete Wahl in `entscheidungen.md` | ja | `../../entscheidungen.md`, Eintrag E-001 |
| Haltefall §2.4 geprüft | ja | Abschnitt 3 dieses Berichts |
| Verworfenes in `geloescht.md` | ja | `../../geloescht.md` |

**Stufe 0 ist abgenommen.**
