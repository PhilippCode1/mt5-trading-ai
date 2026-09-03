# Gelöscht und stehengelassen

*Was entfernt wurde und warum. Und — für Stufe 0 wichtiger — was stehenbleibt, ohne
gepflegt zu werden.*

---

## In Stufe 0 gelöscht

**Nichts.** Stufe 0 ist eine Bestandsaufnahme. Sie bewegt keinen Code.

Das ist ausdrücklich festgehalten, weil Sperre V1 („Kein Code ohne Wirkung") beim Abschluss
jeder Stufe greift: In Stufe 0 ist kein neuer Code entstanden, für den ein Importpfad
nachzuweisen wäre. Entstanden sind ausschließlich Dokumente unter `AUFTRAG/`.

---

## Stehengelassen, nicht gepflegt

Nach §2.4 des Auftrags: *„Der aufgegebene Stand wird nicht gepflegt, nicht mitgeschleppt
und nicht ‚für später' behalten."*

### 1. `C:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai`

**Umfang:** 101.323 Zeilen Produktions-Python in 15 Diensten, rund 100.000 Zeilen
TypeScript, 93 SQL-Migrationen, 121 Commits.

**Warum aufgegeben.** Der Handelsplatz wird im Wirtschaftsraum des Auftraggebers nicht
betrieben — nach §9.2 des Auftrags eine harte Grenze, die kein Umbau aufhebt. Dazu:
gemessen kein Simulator mit Kostenmodell (0 Treffer für `fee|slippage|funding|commission|spread`
in `runner_replay.py`).

**Wird nicht gelöscht, weil:** dort liegen Zugangsdaten im Klartext, deren Widerruf nur der
Auftraggeber veranlassen kann (→ `haltepunkte.md`, H-003). Ein Verzeichnis zu löschen,
bevor die darin liegenden Schlüssel widerrufen sind, beseitigt die Kopie und nicht die
Gültigkeit — es macht die Lage unübersichtlicher, nicht sicherer. Die Löschung ist nach
H-003 fällig, nicht davor.

**Was daraus nicht übernommen wird und warum nicht:**

| Baustein | Warum er nicht mitkommt |
|---|---|
| 15 Dienste, Ereignisbus, Datenmodell | Der gewählte Stand ist bewusst ein einzelnes Paket ohne Dienst, Server, Container und Datenbank. Ein Dienstschnitt für ein System, das nie gehandelt hat, ist Aufwand ohne Wirkung. |
| Dashboard (~100.000 Zeilen TypeScript) | §8 des Auftrags: „Keine zusätzliche Oberflächenfläche." Der gewählte Stand hat eine nur lesende Oberfläche aus der Standardbibliothek (`tools/oberflaeche.py`). |
| Bitget-REST/WS-Anbindung (445 Dateien mit `bitget`) | Handelsplatz nicht erreichbar. §8: „Keine weiteren Broker-Adapter." |
| Signal-Engine mit sechs Scoring-Schichten | Die Gewichte sind gesetzt, nicht hergeleitet (0,22/0,20/0,22/0,10/0,18/0,08). Übernahme hieße, mehrere hundert freie Parameter zu importieren, für die kein Vorteilsnachweis existiert. §8: „Keine weiteren Entscheidungsschichten." |

### 2. `C:\Users\Acer\OneDrive\Documents\Cursor1\strategy-validation`

**Umfang:** 871 Zeilen eigener Code, 3.577 Zeilen vendoriert, 10 Commits.

**Warum aufgegeben.** Die eingefrorene Vorregistrierung prüft den Composite-Score des
verworfenen Standes auf Krypto-Daten von Binance. Beides — Score und Anlageklasse — handelt
der gewählte Stand nicht. Die Maschine, für die die Vorregistrierung geschrieben wurde,
existiert gemessen nicht (0 Simulator-Definitionen, 0 Ergebnisartefakte).

**Wird nicht gelöscht, weil:** es ist ein eigenes Git-Repository mit einer Datei, die
ausdrücklich als unveränderlich gekennzeichnet ist (`PREREGISTRATION.md`, „Status:
eingefroren"). Eine eingefrorene Vorregistrierung zu löschen, deren Lauf nie stattfand, ist
das Gegenteil dessen, wozu sie da ist: sie belegt, was **vorher** gedacht wurde. Sie bleibt
als Beleg liegen, nicht als Arbeitsstand.

**Was daraus nicht übernommen wird:** die neun Kriterien K1–K9. Nicht, weil sie schlecht
wären — sie sind der methodisch beste Teil aller drei Stände —, sondern weil der gewählte
Stand bereits eine gleichwertige, an den Simulator verdrahtete Fassung trägt
(`gates/criteria.py`, `ABBRUCH.md` §2 mit 60 vorregistrierten Versuchen). Zwei
Vorregistrierungen für dieselbe Frage wären der Fehler, den Sperre V6 verbietet.

### 3. Ohne Prüfung stehengelassen

| Pfad | Warum keine Messung |
|---|---|
| `Cursor1/HelioswarmTrading-Ai` | 25 Dateien, kein `.git` — keine tragende Substanz |
| `Cursor1/Ki Trading` | 0 Dateien |
| `bitget-btc-ai.zip`, `bitget-btc-ai.7z` (~1,4 GB) | Archive des verworfenen Standes. **Nicht geöffnet.** Sie enthalten nach Lage der Dinge dieselben Zugangsdaten wie das Arbeitsverzeichnis; das Öffnen zum Zweck der Ausgabe wäre ein Verstoß gegen V7. Sie gehören zu H-003. |

---

## In Stufe 1 gelöscht

**Nichts.** Stufe 1 hat beschafft, nicht entfernt. Die 15 vom Handelsplatz stammenden
Reihen-Manifeste unter `config/reihen/` bleiben ausdrücklich liegen, obwohl sie für
diesen Auftrag unbrauchbar sind: sie sind der Beleg dessen, was am 2026-08-17 gemessen
wurde, und dieselbe `checksum` steht als `data_checksum` in sieben Einträgen von
`TRIALS.jsonl`. Sie zu löschen hieße, die Herkunft von sieben gezählten Versuchen zu
kappen.

## In Stufe 2 gelöscht

**Nichts.** Stufe 2 hat eine Regel gebündelt, die es an einer Stelle gab und an fünf
fehlte — und dabei nur Code hinzugefügt und Aufrufe umgehängt.

## In Stufe 3 gelöscht

**`pruefe_sharpe_je_beobachtung` samt der Konstante `MAX_PLAUSIBLE_SHARPE_JE_BEOBACHTUNG`
in `gates/criteria.py`** — von mir gebaut und im selben Lauf wieder entfernt.

Grund: die Sperre brach 18 bestehende Testfälle, weil die synthetischen Prüfreihen des
Standes fast keine Streuung haben und Sharpes von 23,98 bis 3,06 × 10¹³ erzeugen — ein
Streuungsartefakt, kein Einheitenfehler. Nach der Rücknahme hatte der Helfer keinen
Aufrufer im Ausführungspfad mehr, und V1 verlangt dann die Löschung: „Neuer oder
geänderter Code, für den du beim Abschluss der Stufe keinen Importpfad von einem
Diensteinstiegspunkt bis zur Funktion nachweisen kannst, wird vor dem Abschluss
gelöscht." Ein Helfer, der nur noch in Tests lebt, ist genau das.

Vollständige Ursachenanalyse: `fehler.md`, F-007. Was an seiner Stelle geblieben ist —
die Feldwahl per Syntaxbaum festgenagelt — steht in `stufen/03-simulator/bericht.md` §1.3.

## In Stufe 4 gelöscht

**Nichts.** Die Stufe hat zwei Lücken geschlossen und dabei nur eine Prüfung **verschoben**
(`_validate_volume` aus dem gemeinsamen Pfad in den Eröffnungszweig) und eine
**hinzugefügt** (`konto_maengel` samt der beiden Lesestellen, die sie benutzen).

Zur Sperre V1: der neue Code hat einen Aufrufer im Ausführungspfad. `konto_maengel` wird
von `Mt5Venue._konto_pflicht` und `Mt5Venue.get_account` gerufen, `_konto_pflicht` von
den drei Toren des Orderpfads (Live-Freigabe, Kostentor, Risikoschicht). Ein Dauertor am
Syntaxbaum hält fest, dass daneben keine ungeprüfte Lesestelle entsteht.

---

## In Stufe 5 gelöscht

**Nichts aus dem Repository.** Die Stufe hat einen Speicher hinzugefügt
(`execution/schwebende_auftraege.py`), eine Sperre in den Orderpfad gehängt, ein
Redigierwerkzeug gebaut und eine Aufzeichnung eingecheckt.

**Entfernt wurde eine Datei außerhalb des Repositoriums:**
`%LOCALAPPDATA%\mt5_trading_ai
isiko\schwebende_auftraege.json`. Sie war ein Rückstand
meines eigenen Testlaufs — die erste Fassung der Akte griff ohne Umgebungsvariable auf den
Standardpfad zu, und der Testlauf legte dort synthetische Kennungen ab, die anschließend
87 fremde Testfälle sperrten. Inhalt vor dem Entfernen angesehen: ausschließlich
Kennungen aus `tests/` (`o-timeout`, `fl-…`), kein Betriebsdatum. Die Ursache ist behoben
(Persistenz nur auf Ansage, `stufen/05-ausfuehrung/bericht.md` §3.4).

Zur Sperre V1: der neue Code hat Aufrufer im Ausführungspfad — `SchwebeAkte` wird von
`Mt5Venue` gerufen (Vermerk beim Sendeversuch, Prüfung vor jeder Eröffnung, Auflösung),
`tools/aufzeichnung_redigieren.py` ist ein Werkzeug mit eigenem Dauertor.

---

## In Stufe 6 gelöscht

**Nichts.** Die Stufe hat ein Modul hinzugefügt (`gates/herausforderer.py`), ein Werkzeug
(`tools/modelllauf.py`) und 30 Eichfälle.

Zur Sperre V1: `gates/herausforderer.py` wird von `tools/modelllauf.py` gerufen, und das
Werkzeug hat ein Dauertor, das es als Unterprozess fährt. Kein Modul ohne Aufrufer.

**Ausdrücklich nicht gelöscht, obwohl V1 es verlangen würde:**
`backtest/llm_compare.py::evaluate_llm_gate` hat keinen Aufrufer im Ausführungspfad, nur
Tests. Begründung, warum das eine Entscheidung des Auftraggebers ist und keine
Aufräumarbeit: [`stufen/06-modellpfad/bericht.md`](stufen/06-modellpfad/bericht.md) §8.
Der Widerspruch zu V1 steht damit offen und ist nicht stillschweigend ausgesessen.

---

## In Stufe 7 gelöscht

**Nichts — im Gegenteil: eine Auslassung wurde zurückgenommen.** Die eingecheckte
Aufzeichnung enthielt die 4.311 abgelehnten Signale nicht; ich hatte sie in Stufe 5 als
Messrauschen weggelassen (F-012). Sie sind wieder drin. Stattdessen fällt jetzt ein
**Feld** weg (`schritte`), begründet nach Aussagekraft und im Kopf der Datei
ausgewiesen.

Hinzugekommen: `gates/erkundung.py`, `tools/auswertung.py`, `KOSTENPRAEMISSE_BPS` in
`risk/stop_budget.py`, 37 Eichfälle.

Zur Sperre V1: `gates/erkundung.py` wird von `tools/auswertung.py` und
`tools/modelllauf.py` gerufen, `kostenpraemisse_bps` von
`execution/risk_manager.py::_kostenbasis` im Orderpfad. Kein Modul ohne Aufrufer.

---

## In Stufe 8 gelöscht

**Nichts.** Hinzugekommen: `tools/mutationstor.py` (16 Sonden, Tötungsrate 1,0 als
blockierende Schwelle), `tools/zweigdeckung.py` (80 % je Datei), 34 Eichfälle und die
Zweigdeckungs-Konfiguration in `pyproject.toml`.

**Ein verwaistes Modul wurde verdrahtet statt gelöscht:** `gates/learning_phase.py` war
von keinem Diensteinstiegspunkt aus erreichbar. V1 hätte die Löschung erlaubt; der
Trainingslauf ranglistet jetzt über `rank_strategies`, was er gesehen hat, bevor er
vorschlägt. Das ist ein substantieller Aufruf, kein Feigenblatt — die Begründung und die
Abgrenzung zu `evaluate_llm_gate` stehen in
[`stufen/08-testwirkung/bericht.md`](stufen/08-testwirkung/bericht.md) §2.3.

---

## In Stufe 9 gelöscht

**Zum ersten Mal in diesem Auftrag umfangreich.** Zwölf öffentliche Modulfunktionen
hatten keinen Aufrufer im Ausführungspfad; sieben davon sind entfernt, fünf verdrahtet
worden (dazu `find_weaknesses`; `observed_trade_rate` als Doppel von `trade_rate`).

**Entfernte Funktionen:** `backtest/kalender.py::utc_zu_server`,
`backtest/splits.py::purged_kfold_embargo_indices` und `::walk_forward_indices`,
`data/quality.py::render_markdown`, `risk/stop_budget.py::assumed_cost_bps`,
`gates/learning_phase.py::propose_parameter_sets`, `::build_report` und
`::observed_trade_rate`. Dazu 12 Testfälle, die nur sie prüften.

**Zwei entfernte Wächter, mit Nachweis der Unerreichbarkeit:**
`execution/cost_gate.py::invalid_notional` (jede Eingabe, die ein Nominal von 0 ergäbe,
endet vorher mit `cost_unverifiable` — gemessen an drei Fällen) und die erste
`stop_price_nonpositive`-Stelle in `execution/runner.py` (ein negativer Stop bräuchte
10.000 bp, die Budgetklammer lässt höchstens 1.666,7 bp zu). Ein Zweig hinter einem
strengeren Zweig ist kein Tor.

**Was die Löschungen kosten, benannt:** `propose_parameter_sets` trug „Grenze 3" der
Lernphase (keine Optimierung ohne Ledger-Eintrag); der Modul-Docstring nennt jetzt drei
Grenzen statt vier. Die beiden Wächter hingen an vorgelagerten Klammern; je ein Test hält
diese fest und wird rot, wenn sie sich lockern. Vollständig in
[`stufen/09-tote-tore/bericht.md`](stufen/09-tote-tore/bericht.md) §4.

---

## Was nach dem Ergebnistor **nicht** gelöscht wurde, obwohl es naheläge

Befund (B) heißt nach §1: *„Es wird zurückgebaut oder aufgegeben."* Beides ist eine
Entscheidung des Auftraggebers (H-004), und beide Wege sind noch offen. **Ich habe
deshalb nichts entfernt** — 58 % des Pakets (8.889 von 15.440 Zeilen, gemessen am
2026-08-19 vor dem Halal-Rückbau; danach 8.760 von 15.248, also 57 %) sind
Handelsstrecke und stünden bei Option 2 zur Disposition, aber ein Rückbau, der die Wahl
vorwegnimmt, wäre keine Ausführung des Vertrags, sondern ihre Umgehung.

Was an jeder der drei Optionen hängt, ist beziffert in
[`rueckbau-bestandsaufnahme.md`](rueckbau-bestandsaufnahme.md).

---

## Am 2026-08-19 gelöscht — der Halal-Strang

Auf Anweisung des Auftraggebers (E-006), nach dem Ergebnistor. Gemessen, nicht geschätzt:
**Python +117/−425 Zeilen, Markdown +236/−579 Zeilen** über 35 Dateien.

### Ganz entfernte Dateien

| Datei | Was sie war |
|---|---|
| `mt5_trading_ai/costs/halal.py` | swapfreie Finanzierungspolitik ohne Zins |
| `mt5_trading_ai/venue/halal.py` | der mechanische Screen samt Urteilsobjekt |
| `tests/test_halal.py` | die Testfälle beider Module |
| `HALAL-VORFRAGE.md` | die Vorlage für die Anfrage |
| `ABSCHLUSS/05-HALAL-VORFRAGE.md` | ihre wortgleiche Kopie im Abschlussordner |

### Aus bestehenden Dateien entfernt

| Ort | Was |
|---|---|
| `venue/mt5.py` | Methode `_enforce_halal` (40 Zeilen) **und ihr Aufruf** in `submit_order` |
| `execution/runner.py` | Schritt 3 der Kette; die Folgeschritte sind lückenlos neu nummeriert |
| `execution/runner.py` | `RunnerConfig.account_swap_free` / `.interest_bearing_margin` / `.scholar_review_id` |
| `costs/model.py` | Parameter `financing_policy`; die Swap-Rechnung läuft jetzt unbedingt |
| `backtest/engine.py` | Feld `MarketSpec.financing_policy` samt Durchreichung |
| `tools/edge_test.py` | Schalter `--halal` |
| `tools/live_betrieb.py`, `tools/live_konsole.py`, `tools/paper_run.py` | die drei Konfigurationswerte an den Aufrufstellen |
| `tests/test_mt5_venue.py` | drei Fälle (57 → 54) |
| `tests/test_paper_runner.py` | zwei Fälle; die Naht `halal` aus der Nahtliste |
| `tests/test_stop_budget_kostenbasis.py` | zwei Aufrufstellen |

### Was der Wegfall am Orderpfad ändert — und was nicht

`_enforce_halal` war ein **fail-closed-Tor auf jeder eröffnenden Live-Order**. Es ist weg;
der Live-Pfad hat eine Sperre weniger. Es ist **kein** Ersatz gebaut worden, weil kein
Ersatz gefordert war.

Was den Orderpfad weiterhin sperrt, gezählt an einer echten Order von
`tests/test_orderpfad_verdrahtung.py`: Idempotenz, Global-Halt-Latch, Stop-Pflicht,
Frische-Latch, vierteilige Live-Freigabe, Hebel-Preflight, Kostentor, Verlustgrenzen,
Drossel, Stop-Budget, Positionsgröße — darunter `allow_write=False` und die Demo-Pflicht
am Terminal. Die fünf zählenden Sollsperren aus Paket 2 A3.2 sind unverändert fünf.

### Was **nicht** gelöscht wurde, obwohl es „Halal" sagt

`ABSCHLUSS/`, `ABSCHLUSS-3a/`, `docs/audit/` und `PROGRESS.md` weisen sich selbst als
eingefrorene bzw. angehängte Belege aus. Sie sind ergänzt, nicht umgeschrieben (E-007):
Nachtrag am Kopf des jeweiligen Ordners, Schlusseintrag in `PROGRESS.md`, tote Verweise auf
gelöschte Dateien entschärft. Wer auch dort bereinigt haben will, muss es anweisen.

---

## Zum Altbestand `bitget-btc-ai` — Stand 2026-08-19

Die Anweisung, ihn vollständig zu entfernen, liegt vor. **Ausgeführt ist sie nicht.** Zwei
getrennte Gründe, beide unverändert:

1. **Das Verzeichnis und die Archive liegen außerhalb dieses Repositoriums** — unter
   `C:\Users\Acer\OneDrive\Documents\Cursor1\` — und enthalten Zugangsdaten im Klartext
   (H-003). Eine Löschung vor dem Widerruf beseitigt die Kopie, nicht die Gültigkeit der
   Schlüssel. Widerrufen kann sie nur der Kontoinhaber.
2. **Ich lösche keine Daten des Auftraggebers unwiderruflich.** Gemessen am 2026-08-19:
   das Verzeichnis **2,0 GB** (mit einem `.git` von 121 Commits), dazu die Archive
   `bitget-btc-ai.7z` **693.431.340 Bytes** und `bitget-btc-ai.zip` **742.253.246 Bytes**
   = 1,44 GB. Zusammen rund **3,4 GB**, über keinen Papierkorb dieser Größenordnung
   wiederherstellbar. Die Befehle stehen im Schlussbericht; ausführen muss sie der
   Auftraggeber.

**In diesem Repositorium** trägt der Name nur noch Herkunftsangaben: `MASTERBERICHT.md` §1
(woraus der Kern gelöst wurde), `VERLUST.md` (was dabei bewusst zurückblieb), `PROGRESS.md`
und `docs/audit/` (Chronik) sowie die Berichte unter `AUFTRAG/stufen/` (die Messung, auf
der die Wahl des Standes beruht). **Kein Produktionscode, kein Test, kein Import.** Diese
Angaben bleiben: Ein Paket, das nicht mehr sagen kann, woraus es gelöst wurde, ist nicht
sauberer, sondern herkunftslos.

---

## Stufe 10 — nichts gelöscht

Diese Stufe hat **keine Zeile Produktionscode entfernt.** Das ist kein Versäumnis, sondern
das Ergebnis der Prüfung: die vier Forderungen der Stufe waren vier Lücken, keine
Altlasten. Es gab nichts, was verdrahtet oder entfernt hätte werden müssen — es gab
schlicht keine Alarmschicht, keine Handlungsanweisungen und keine Dienstgüteziele.

Der einzige Fall, in dem V1 (neuer Code ohne Aufrufer wird gelöscht) hätte greifen können,
war der eigene Neubau: `betrieb/dienstguete.py`. Er ist verdrahtet — `tools/dienstguete.py`
ruft `erhebe`, `pruefe_alarme` und `stelle_zu`, die drei Metriken hängen über `METRIKEN` an
`erhebe`. Dass der Stufe-9-Zähler das zunächst nicht sah, ist in F-015 und E-011
festgehalten; die Antwort war, den Zähler zu korrigieren, nicht den Code zu verbiegen.
