# Stufe 9 — Tote Tore verdrahten oder löschen

*Gefahren am 2026-08-20 auf Anweisung des Auftraggebers („stufe 9"). Belege in
[`belege/`](belege/), fünf Dateien. Bestätigt durch Ausführung — jede Ausgabe liegt bei.*

---

## 0. Zur Zulässigkeit — unverändert die Entscheidung des Auftraggebers

Es gilt weiter, was in [Stufe 4](../04-risikokern/bericht.md) §0 steht: §1 schließt die
Stufen 4–10 für den Ausgang (B) aus, der Auftraggeber hat sie angewiesen (E-009).
**Diese Stufe misst keinen Vorteil und behauptet keinen.**

---

## 1. Was gemessen wurde

Beleg [`01-messung-vorher.txt`](belege/01-messung-vorher.txt), gegen einen eigenen
Arbeitsbaum auf Commit `00420a9`.

| # | Forderung | vorher |
|---|---|---|
| A1/A2 | Ohne Zwischenzustand: für jede gelesene Größe ein Schreiber oder kein Leser | **12 Funktionen ohne Aufrufer** |
| A3 | Typprüfungstor vom unbenutzten Code auf den Auftragspfad umhängen | **16 × `Any` auf dem Auftragspfad** |
| A4 | Ein Werkzeug, das Tore ohne Auslösung im Betrieb meldet | **fehlte ganz** |
| B | Für jedes verbliebene Tor ein Test, der es auslöst | **11 Gründe ohne Auslöser** |

**Die unangenehmste Einzelheit:** unter den zwölf verwaisten Funktionen stand
`entscheide_erkundung` — der Erkundungspfad, den ich **eine Stufe zuvor selbst gebaut
und nie verdrahtet hatte**. Genau die Krankheit, die §0 des Auftrags benennt, begangen
im Auftrag selbst.

**Zur Typprüfung.** mypy läuft `--strict` über Paket und Werkzeuge; auf dem Auftragspfad
stand **kein einziges** `type: ignore`. Die Lücke war eine andere: **16 Parameter und
Rückgaben als `Any`** — darunter der Kontoschnappschuss aus Stufe 4 (`konto_maengel`,
`_konto_pflicht`) und der Risikoanteil (`size_position`). `Any` schaltet die Prüfung ab;
das Tor stand also formal über allem und wirkte an den zentralen Größen des Orderpfads
nicht.

---

## 2. Was geändert wurde

### 2.1 Zwölf verwaiste Funktionen: fünf verdrahtet, sieben gelöscht

| Funktion | Entscheidung | wohin / warum |
|---|---|---|
| `entscheide_erkundung` | **verdrahtet** | `execution/runner.py`, an der Zulassung |
| `evaluate_llm_gate` | **verdrahtet** | `tools/modelllauf.py` — dort, wo ein Modell überhaupt in den Pfad käme |
| `validate_proposal` | **verdrahtet** | `tools/modelllauf.py`, vor dem Bau des Herausforderers |
| `check_integrity` | **verdrahtet** | `tools/edge_test.py`, **vor** dem Registereintrag |
| `trade_rate` | **verdrahtet** | `tools/auswertung.py` — es ist die Zahl aus Stufe 7 |
| `annualise_sharpe` | **verdrahtet** | `backtest/engine.py`, ersetzt die zweite Formel |
| `find_weaknesses` | **verdrahtet** | `tools/modelllauf.py` |
| `utc_zu_server` | gelöscht | kein Aufrufer, kein Platz |
| `purged_kfold_embargo_indices` | gelöscht | der Stand fährt `purged_walk_forward_indices` |
| `walk_forward_indices` | gelöscht | dito |
| `render_markdown` | gelöscht | kein Berichtspfad, der ihn ruft |
| `assumed_cost_bps` | gelöscht | `stop_budget` liest die Tabelle **direkt** — zwei Lesearten, eine ohne Aufrufer |
| `propose_parameter_sets` | gelöscht | siehe §4 |
| `build_report` | gelöscht | rief nur die beiden Vorigen |
| `observed_trade_rate` | gelöscht | **dieselbe Zahl** wie `gates/evaluation.trade_rate` |

**Der Unterschied zu meiner Weigerung in Stufe 6** ist benennbar und bleibt bestehen:
dort hätte ein Aufrufpunkt für `evaluate_llm_gate` *erfunden* werden müssen. Jetzt gibt
es den Trainingslauf — die Stelle, an der ein Modell tatsächlich in den Pfad käme. Der
Aufruf ist substantiell, und das Tor lehnt mit den Eingaben des LLM-freien Standes ab:
**„kein LLM zugelassen" ist eine Aussage, „das Tor wurde nie gefragt" ist keine.**

**Ein Fund beim Zusammenlegen:** `annualise_sharpe` und die im Backtest ausgeschriebene
Formel waren **nicht identisch**. Die Inline-Fassung schluckte null Trades still
(`sqrt(0) = 0`), die Funktion weist sie ab. Das Verhalten bleibt unverändert (0,0), aber
die Ausnahme steht jetzt sichtbar an einer Stelle statt verdeckt in einer zweiten Formel.

### 2.2 Das Typprüfungstor auf den Auftragspfad

| | vorher | nachher |
|---|---:|---:|
| `Any` auf dem Auftragspfad | **16** | **12** |
| davon in der Entscheidungslogik | 4 | **0** |
| davon an der Grenze zum untypisierten MT5-Modul | 12 | 12 |

`konto_maengel(acc)` und `normalise_risk_fraction(value)`/`size_position(risk_fraction)`
nehmen jetzt `object` statt `Any`, `_konto_pflicht()` gibt `Mt5Account` zurück. Der
Unterschied ist keine Formsache: `Any` schaltet die Prüfung für jeden Zugriff ab,
`object` zwingt sie durch `getattr`/`isinstance` — und genau das soll eine Funktion tun,
die unvollständige Daten prüfen soll.

Die verbliebenen zwölf sitzen an der Grenze zum MetaTrader5-Modul, das keine
Typinformation liefert. Sie sind **einzeln aufgezählt**, nicht per Muster erlaubt; eine
neue Stelle fällt auf.

### 2.3 `tools/torzaehlung.py` — das Werkzeug

Zwei Spalten, die nicht dasselbe sagen:

- **Test** — löst irgendein Testfall diesen Grund aus? Fehlt er, ist das Tor nirgends
  nachgewiesen. **Das blockiert.**
- **Betrieb** — ist der Grund je in einem echten Journal aufgetaucht? Fehlt er, ist das
  eine **Auskunft**, kein Mangel: ein Not-Aus, der nie ausgelöst hat, ist ein gutes
  Zeichen.

Die beiden zu verwechseln wäre der naheliegende Fehler.

**Betriebszählung, gemessen** ([`03-torzaehlung.txt`](belege/03-torzaehlung.txt)):
41 Ablehnungsgründe im Code, **2** je im Betrieb ausgelöst. Dazu **10 durchgereichte
Brokertexte**, die keinen Code tragen, an dem eine Auswertung sie zählen könnte —
darunter `Trade disabled (retcode=10017)` mit 753 Fällen.

---

## 3. Ein Muster, dreimal gefunden: Wächter hinter strengeren Wächtern

Beim Schreiben der auslösenden Tests stellte sich dreimal dasselbe heraus: der Wächter
**kann nicht auslösen**, weil eine frühere Prüfung strenger ist.

| Grund | vorgelagerter Wächter | Nachweis |
|---|---|---|
| `invalid_notional` | `order_roundturn_cost` | `contract_size=0`, `volume=0`, `ask=0` → alle drei `cost_unverifiable` |
| `stop_price_nonpositive` (1. Stelle) | Budgetklammer | ein negativer Stop bräuchte 10.000 bp; `margin_ceiling_bps` lässt höchstens 1.666,7 bp zu |
| `margin_below_min_volume` | Hebel-Preflight | `margin_free=1` → `insufficient_margin` |

**Zwei davon sind gelöscht** (`invalid_notional`, die erste `stop_price_nonpositive`-
Stelle). Ein Zweig hinter einem strengeren Zweig ist kein Tor, sondern eine Zusicherung
ohne Fall.

**Drei bleiben stehen und sind freigestellt** — mit dem gemessenen Grund und, wichtiger,
**mit je einem Test auf die vorgelagerte Klammer**. Wird die Klammer gelockert, fällt die
Freistellung sofort auf. Eine Freistellungsliste ohne diese Gegenprobe wäre ein
Ablagefach; ein Dauertor hält sie bei höchstens fünf Einträgen und verlangt, dass jeder
seine Klammer benennt.

**Das ist die ehrliche Grenze dieser Stufe:** für drei Gründe gibt es keinen Test, der
sie auslöst — weil sie nicht auslösen können. Das steht so im Werkzeug, im Test und hier.

---

## 4. Was die Löschungen kosten — benannt, nicht verschwiegen

**`propose_parameter_sets` trug „Grenze 3" der Lernphase:** keine Optimierung ohne
Ledger-Eintrag. Die Funktion hatte keinen Aufrufer; der Auftrag verlangt an dieser Stelle
„ohne Zwischenzustand". Sie ist entfernt, und der Modul-Docstring nennt jetzt **drei**
Grenzen statt vier.

**Was das heißt:** Wer künftig einen Suchlauf über einen Parameterraum baut, muss den
Registereintrag selbst herstellen — er entsteht nicht mehr nebenbei. Der Versuchszähler
selbst ist nicht aufgeweicht: jeder `edge_test`-Lauf schreibt weiter, und
`check_integrity` prüft das Register seit dieser Stufe **vor** jedem Lauf. Es ist eine
Sperre weniger für einen Weg, den es heute nicht gibt.

**Zwei gelöschte Wächter** (§3): fällt eine der beiden vorgelagerten Klammern weg, fehlt
der nachgelagerte Schutz. Ein Test hält beide Klammern fest und wird rot, wenn sie sich
lockern.

---

## 5. Was schiefging

**F-013 — ich habe den Erkundungswürfel auf die Wanduhr gesetzt.** Beim Verdrahten des
Erkundungspfads lautete der Schlüssel `f"{symbol}|{side}|{now.isoformat()}"`. `now` ist
im Betrieb `datetime.now(UTC)`; derselbe Schlüssel wiederholt sich also nie.

Das widerspricht genau der Eigenschaft, für die ich den Hash in Stufe 7 gewählt hatte —
der dortige Docstring sagt wörtlich: *„derselbe Schlüssel ergibt in jedem Lauf dieselbe
Entscheidung … eine unreproduzierbare Auswertung belegt nichts."* Eine Stufe später habe
ich die Begründung des eigenen Entwurfs ausgehebelt.

Aufgefallen an **einem einzelnen** Fehlschlag unter `coverage`, der sich in zwölf
Wiederholungen nicht reproduzieren ließ. Die Versuchung war, ihn als Ausrutscher
abzulegen. Die richtige Frage war nicht „war das ein Ausrutscher", sondern „was von dem,
was ich gerade gebaut habe, würfelt". Behoben: der Schlüssel ist jetzt die
Auftragskennung. Vollständig in [`../../fehler.md`](../../fehler.md), F-013.

---

## 6. Abnahme

**`tests/test_stufe9_tote_tore.py`, 17 Fälle**, Beleg
[`04-abnahme.txt`](belege/04-abnahme.txt). Darunter:

- **kein Leser ohne Schreiber** — 0 öffentliche Funktionen ohne Aufrufer (vorher 12),
- **`Any` nur an der untypisierten Grenze** — die erlaubten Stellen einzeln aufgezählt,
- **sechs Tore, die vorher kein Test auslöste**, jetzt ausgelöst: `no_tick`,
  `volume_above_max`, `invalid_price`, `price_missing`, `venue_unavailable`,
  `account_unavailable`, `risk_price_missing`,
- **drei Tests auf die vorgelagerten Klammern** der freigestellten Gründe,
- **ein Nachweis der Unerreichbarkeit** für die beiden gelöschten Wächter,
- **ein roter Eichfall am Werkzeug selbst**: die erste Fassung von `torzaehlung` suchte
  nur `reason=`-Schlüsselwörter und lief damit an `cost_unverifiable` vorbei — dem mit
  2.258 Fällen häufigsten Grund überhaupt, weil er positional übergeben wird.

**Torlauf** ([`05-torlauf.txt`](belege/05-torlauf.txt)): **zehn** Tore je **Exit 0** —
neu darunter die Torzählung. `pytest` **1.546 bestanden, 0 fehlgeschlagen**;
Tötungsrate 1,000 (16/16); Zweigdeckung Paket 88,0 %, jede Geldpfad-Datei über 80 %.

---

## 7. Was diese Stufe ausdrücklich nicht behauptet

**„Kein toter Code" heißt hier: keine öffentliche Modulfunktion ohne Aufrufer.** Private
Helfer, Klassenmethoden und Zweige innerhalb einer Funktion sind davon nicht erfasst. Die
Zweigdeckung aus Stufe 8 misst das andere Ende; zwischen beiden bleibt Raum.

**Die Betriebszählung steht auf einem einzigen Demolauf.** 2 von 41 Gründen ausgelöst
sagt mehr über die Zahl der Betriebstage aus als über die Tore.

**Drei Gründe haben keinen auslösenden Test** (§3), und das ist eine Freistellung mit
Nachweis, keine erfüllte Forderung. Wer die vorgelagerten Klammern ändert, muss sie neu
bewerten — dafür steht je ein Test bereit.
