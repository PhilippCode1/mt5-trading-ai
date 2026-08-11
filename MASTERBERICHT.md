# MASTERBERICHT — MT5 Trading AI

*Bismillah. Ein einziger, langer Bericht über das gesamte Paket: was es ist, woher es kommt,
wie jeder Ordner aufgebaut ist, was heute nachweislich steht, wo die bewusst gezogenen
Grenzen liegen und welches Potenzial darauf aufbaut. Jede Zahl in diesem Bericht ist
gemessen, nicht behauptet (Stand der Messung: 2026-08-11).*

---

## 0. In einem Satz

`mt5_trading_ai` ist der aus einem großen, teils unfertigen Handels-Monorepo **herausgelöste,
geprüfte Kern** — die Risiko-, Sperr- und Validierungsschicht — plus ein darauf aufgesetztes,
**venue-unabhängiges Handelsplatz-Gerüst** für MT4/MT5, dessen Sicherheitslogik gegen
Test-Doubles nachgewiesen ist. Der Kern handelt heute **nicht** autonom mit Echtgeld; er ist
das sichere Fundament, hinter dem ein Handel erst durch eine mehrteilige menschliche Freigabe
möglich wird.

- **Ort:** `C:\Users\Acer\mt5_trading_ai`
- **GitHub:** `PhilippCode1/mt5-trading-ai` (privat), Branch `master`, 16 Commits
- **Umfang:** 18 Module / 4.112 Zeilen Kerncode · 190 Testfunktionen / 2.628 Zeilen Tests ·
  3 Werkzeuge / 276 Zeilen
- **Prüfstand:** 244 Tests grün · `ruff` sauber · `mypy --strict` sauber (28 Quelldateien) ·
  zwei Doku-Tore grün

---

## 1. Herkunft — woraus dieser Kern gelöst wurde

Der Ursprung ist das Monorepo `bitget-btc-ai` mit **15 Diensten** (Marktdatenstrom,
Struktur-/Feature-Engines, Signal-/News-/LLM-Dienste, Live- und Paper-Broker, Monitoring,
Audit-Ledger u. a.). Der Auftrag war, **nur den bewiesenen Kern** additiv herauszulösen —
nichts zu erfinden, nichts unfertiges mitzuschleppen — und alles Zurückgelassene nachweisbar
zu machen.

Drei Dokumente halten diese Herkunft ehrlich:

- **`VERLUST.md`** — was zurückblieb, **jede Fähigkeit und jede Sperre einzeln** eingeordnet:
  mitgekommen / neu zu schreiben / bewusst entfallen, mit `pfad:zeile`-Ankern in den
  Altbestand. Der gefährliche Fehler wäre nicht, zu viel zurückzulassen, sondern etwas
  Gebrauchtes zurückzulassen und es nicht zu merken.
- **`FEHLT.md`** — die Leerstellen und die harte Reihenfolge-Regel: **kein Ausführungspfad,
  bevor der Fail-Closed-Apparat und die menschlichen Tore stehen.**
- **`PROGRESS.md`** — ein angehängtes, nie überschriebenes Protokoll je Arbeitsschritt, mit
  Befehlen, Ausgaben, eigenen Fehlern und Entscheidungen.

Der Altbaum ist per Tag `archive/pre-extraction` gesichert; die Isolation ist nachgewiesen
(`import mt5_trading_ai` zeigt in den neuen Baum, `import signal_engine` scheitert).

---

## 2. Ordnerstruktur — der ganze Baum

```
mt5_trading_ai/
├── README.md              Einstieg + geprüfte Kennzahlen (Zahlen-Wächter)
├── MASTERBERICHT.md       dieser Bericht
├── PROGRESS.md            angehängtes Arbeitsprotokoll
├── VERLUST.md             was zurückblieb (mit Ankern)
├── FEHLT.md               die Leerstellen / nächster Auftrag
├── MODULES.md             AUS DEM CODE generierte Modulübersicht (Doku-Tor)
├── pyproject.toml         Ruff/Mypy/Pytest — Konfiguration identisch zum Altbestand
├── .env.example           Beispiel-Konfiguration (echte .env ist ignoriert)
│
├── config/
│   ├── asset_class_leverage.json     ESMA-Hebeldeckel je Anlageklasse
│   └── instrument_catalog.json       versionierter Instrumentenkatalog
│
├── mt5_trading_ai/        DAS PAKET (18 Module)
│   ├── risk/       Hebelklammer, Verlustgrenzen, Positionsgröße, Stop-Budget
│   ├── gates/      Bewertungstor, Kriterien+Deflated Sharpe, Versuchsregister, Lernphase
│   ├── data/       Datenqualitäts-Tor
│   ├── backtest/   Zeitreihen-Splits (Purge/Embargo, Walk-Forward)
│   ├── execution/  Live-Freigabe, Hebel-Preflight, Reconcile, Private-Sync
│   └── venue/      TradingVenue-Protokoll, MT5-Adapter, Katalog-Lader, Demo-Smoke
│
├── tests/          18 Testdateien, 190 Testfunktionen
└── tools/          Doku-Generator, Doku-Tor, Demo-Smoke-CLI
```

---

## 3. Die Schichten im Detail

### 3.1 `risk/` — Risiko- und Sperrschicht (das Herz)

| Modul | Zeilen | Aufgabe |
| --- | --- | --- |
| `risk/leverage.py` | 276 | **Hebelklammer**: `min(Wunsch, 10, Klassendeckel)`; unbekannte Klasse oder Deckel unter Betriebsminimum → `no_trade`. Nicht über 10 konfigurierbar. |
| `risk/limits.py` | 145 | **Verlustgrenzen**: Tagesverlust, Drawdown-Halt (kein Selbst-Reset), Positionsdeckel. |
| `risk/sizing.py` | 220 | Positionsgröße aus Risikoanteil und Stop-Abstand; Stop-Floor. |
| `risk/stop_budget.py` | 160 | Stop-Budget je Anlageklasse. |

Belegt durch `test_asset_class_leverage.py`, `test_loss_limits.py`, `test_risk_sizing.py`,
`test_stop_budget.py`. Die Hebelklammer und die Verlustgrenzen wurden **negativ gefahren**
(absichtlich beschädigt, liefen rot, Schaden zurückgenommen).

### 3.2 `gates/` — Bewertung, Kriterien, Register, Lernphase

| Modul | Zeilen | Aufgabe |
| --- | --- | --- |
| `gates/evaluation.py` | 202 | **Bewertungstor**: „evaluating ≠ trading" — Schwelle, Mindesthaltedauer, Abklingzeit, Korrelationsdeckel. |
| `gates/criteria.py` | 348 | Vorregistrierte Kriterien und **Deflated Sharpe** (Schutz gegen Überanpassung durch viele Versuche). |
| `gates/trials.py` | 204 | **Versuchsregister** `TRIALS.jsonl` (anhängend, kein Überschreiben). |
| `gates/learning_phase.py` | 292 | Lernphase: Rangliste, Schwächenbefunde, Grenzen. |

Belegt durch `test_evaluation_gate.py`, `test_strategy_criteria.py`, `test_trials_ledger.py`,
`test_learning_phase.py`.

### 3.3 `data/` und `backtest/` — Validierungsschicht

| Modul | Zeilen | Aufgabe |
| --- | --- | --- |
| `data/quality.py` | 228 | **Datenqualitäts-Tor**: Lückenquote, Zeitstempel-Ordnung, Ausreißer, Handelszeiten — fail-closed bei schlechten Daten. |
| `backtest/splits.py` | 190 | **Zeitreihen-Splits** mit Purge/Embargo und Walk-Forward bis Datenende. Purge/Embargo sind jetzt **pflichtige** Parameter (kein stiller Null-Default, der wie eine Sperre aussähe). |

Belegt durch `test_data_quality.py`, `test_splits.py` (der Fold-Fix bis zum Datenende ist
negativ gefahren).

### 3.4 `venue/` — der Handelsplatz (venue-unabhängig)

| Modul | Zeilen | Aufgabe |
| --- | --- | --- |
| `venue/protocol.py` | 274 | **`TradingVenue`-Protokoll**: der plattformunabhängige Vertrag (Verbindung, Instrumente, Marktdaten, Ausführung, Zustand). Fail-closed **als Vertrag**: jede Methode, die keine sichere Antwort geben kann, wirft. Kein Modul außerhalb `venue/` kennt einen Plattformnamen. |
| `venue/mt5.py` | 818 | **`Mt5Venue`** (erfüllt das Protokoll, statisch geprüft) über die injizierbare Naht **`Mt5Terminal`**; dazu **`RealMt5Terminal`** — die dünne MetaTrader5-Bindung mit fail-closed Schreibpfad (`allow_write=False`). |
| `venue/catalog.py` | 159 | **Instrumentenkatalog-Lader**: Anlageklasse, Kosten, Handelszeiten aus versionierter Datei; jeder Defekt ist ein Fehler, kein Default. |
| `venue/smoke.py` | 162 | **Demo-Smoke-Orchestrierung** (`run_smoke`): feste Prüffolge gegen einen Venue, harter Demo-Abbruch, optionale abgesicherte Schreib-Probe. |

Belegt durch `test_mt5_venue.py` (30 Fälle — der Vertragstest), `test_instrument_catalog.py`
(13 Fälle, davon 9 Fail-closed), `test_mt5_smoke.py` (5 Fälle).

### 3.5 `execution/` — die Tore am Order-Pfad

| Modul | Zeilen | Aufgabe |
| --- | --- | --- |
| `execution/release.py` | 128 | **Live-Freigabe**: vier unabhängige Schalter **und** eine nichtleere Freigabekennung; „nicht bewertbar = nicht erfüllt". |
| `execution/leverage_preflight.py` | 91 | **Hebelklammer-Anschluss**: verbindet die Klammer mit Instrument/Konto/Auftrag (Klasse handelbar? Hebel geklammert? Marge frei?). |
| `execution/reconcile.py` | 113 | **Buch ↔ Konto**: lokales Nettobuch + Notional-Drift-Vergleich → Global-Halt; plus **Buch-Adoption** beim Neustart. |
| `execution/private_sync.py` | 89 | **Private Ereignis-Sync**: der autoritative Kontostrom führt das Buch; fail-closed bei Sequenzlücke oder Stille. |

Belegt durch `test_live_release.py`, das Hebel-/Reconcile-/Sync-Verhalten in
`test_mt5_venue.py`, `test_reconcile.py`, `test_private_sync.py`.

---

## 4. Der Order-Pfad und seine Tore

Eine **eröffnende** Order durchläuft in `Mt5Venue.submit_order` mehrere Sperren in Folge.
Fällt eine, wird nicht gesendet. Reduce-Only (Risikoabbau) bleibt bewusst freier.

```
Eröffnende Order
  → Idempotenz (dieselbe Kennung erzeugt keine zweite Order)
  → Global-Halt-Latch  (Reconcile-Drift ODER Private-Sync-Desync → gesperrt)
  → Stop-Pflicht       (ohne gültigen Stop wird nicht eröffnet)
  → Live-Freigabe      (nur Live-Konto: vier Schalter + Kennung, sonst abgelehnt)
  → Hebel-Preflight    (Klasse handelbar? Hebel ≤ 10 geklammert? Marge frei?)
  → an das Terminal    (RealMt5Terminal: Schreibpfad zusätzlich allow_write=False)
```

Drei unabhängige Sperren stehen so **hintereinander** gegen einen ungewollten Schreibzugriff
auf ein Live-Konto: die Live-Freigabe im Adapter, `allow_write` im Terminal und der harte
Demo-Abbruch im Smoke-Runner. Diese Redundanz ist beabsichtigt — beim Demo-Smoke wurde sie
negativ gefahren: selbst mit ausgehebeltem Demo-Abbruch blockiert die Live-Freigabe.

**Fail-closed-Zustände, die sich nicht selbst lösen** (wie der Drawdown-Halt): der
Reconcile-Drift-Halt und der Private-Sync-Desync-Halt rasten und werden nur durch einen
bewussten Schritt gelöst — Buch adoptieren, dann `clear_halt()`.

---

## 5. Die Prüf-Disziplin — warum den Zahlen zu trauen ist

Der Kern lebt von einer bewussten Prüfkultur, nicht von Zusicherungen:

1. **Grün heißt dasselbe wie im Altbestand.** Die `ruff`/`mypy`-Konfiguration ist absichtlich
   identisch übernommen; „grün im Alt" und „grün im Neu" bedeuten dasselbe.
2. **Negativ fahren.** Jede neue Sperre wurde absichtlich beschädigt, lief rot, und der
   Schaden wurde zurückgenommen — so ist bewiesen, dass der Test die Sperre wirklich prüft und
   nicht hohl ist (Hebelklammer, Live-Freigabe, Splits, Hebel-Anschluss, Reconcile-Halt,
   Demo-Abbruch, Tick-Rundung, Sequenzlücke).
3. **Doku-Tore.** `MODULES.md` wird **aus dem Code** erzeugt und per `--check` geprüft; ein
   Zahlen-Test hält die README-Kennzahlen ehrlich; ein Claims-Tor blockiert
   Reifegrad-Phrasen ohne ausführbaren Beleg und begrenzt die Doku-Menge.
4. **Adversariale Review.** Für drei sicherheitsnahe Bausteine (Buch-Adoption, Demo-Smoke,
   Private-Sync) lief eine mehrperspektivische Prüfung mit Gegenkontrolle jedes Befunds. Zwei
   davon fanden **reale** Fehler im untestbaren Schreibpfad (ein Stop neben dem Tick-Raster;
   ein Reduce-Only-Close ohne Positions-Ticket) — beide sind eingearbeitet und getestet.

---

## 6. Aktueller Stand — gemessen

| Kennzahl | Wert |
| --- | --- |
| Kernmodule (ohne `__init__`) | 18 |
| Kerncode (Zeilen `.py`) | 4.112 |
| Testfunktionen | 190 (in 18 Dateien) |
| Testfälle (parametrisiert) | 244 grün |
| `ruff check .` | keine Beanstandung |
| `mypy --strict mt5_trading_ai tools` | keine Beanstandung (28 Quelldateien) |
| `gen_docs.py --check` | `MODULES.md` aktuell |
| `check_docs_claims.py` | keine Zusicherung ohne Beleg |
| Commits | 16 (privat auf GitHub) |

**Was heute nachweislich funktioniert:** die gesamte Risiko-/Sperr-/Validierungsschicht; das
`TradingVenue`-Protokoll mit einem MT5-Adapter, dessen Marktdaten-, Konto-, Positions-,
Reconcile-, Adoptions- und Sync-Logik gegen ein Fake-Terminal geprüft ist; der versionierte
Instrumentenkatalog; die menschliche Live-Freigabe; und ein abgesicherter Demo-Smoke-Runner.

**Was heute bewusst noch nicht läuft** (siehe §7): der Handel mit einem echten Konto. Der
Kern ist an **keinen** realen Order-Pfad angeschlossen, der ohne menschliche Freigabe
auslösen könnte.

---

## 7. Die bewusst gezogenen Grenzen (aus `FEHLT.md`)

Nichts hiervon ist ein Mangel des Kerns — es ist die Grenze, an der der nächste Auftrag
beginnt. Die harte Regel bleibt: **kein Ausführungspfad, bevor der Fail-Closed-Apparat und
die menschlichen Tore stehen.**

1. **Die konkrete Terminal-/Feed-Bindung.** `RealMt5Terminal` und die Ereignis-**Quelle** für
   den Private-Sync (MT5-Deal-Abfrage bzw. ein Börsen-WS) brauchen ein laufendes Terminal und
   sind hier nicht ausführbar. Der **Demo-Smoke** ist der erste Schritt, sie gegen ein echtes
   Demo-MT5 zu prüfen.
2. **Marktdaten & Struktur/Signal.** Orderbuch-Prüfsumme, Sequenzlücken, Feed-Health;
   Swing-/BOS-/CHOCH-Erkennung; der Signal-/Entscheidungskern — all das blieb im Altbestand
   und ist neu zu schreiben, geführt durch die schon vorhandenen Kriterien und das
   Versuchsregister.
3. **Kosten- und Kontraktmodell** (Fee/Funding/Slippage/Liquidation) für den Papierhandel.
4. **Der restliche Fail-Closed-Apparat**, den der Altbestand am Live-Pfad trug: Kill-Switch,
   Global-Halt-Latch, Runtime-Safety-Oracle, Exchange-Readiness (`WRITE_ORDER_ALLOWED_DEFAULT
   =False`), VPIN-Halt, Liquiditäts-Guard, Positions-Drift-Halt.
5. **Zwei konkrete offene Befunde** aus `VERLUST.md`: der frühere `portfolio_risk_check_fresh`
   (ein frischer Risikocheck, den heute der Reconcile beantwortet, sobald ein Portfolio-
   Risikozustand existiert) und das Setzen des geklammerten Hebels am Terminal je Symbol.

---

## 8. Potenzial — worauf dieses Fundament trägt

Der Wert des Kerns liegt darin, dass die **schwer nachrüstbaren** Teile — die Sicherheit und
die Prüfdisziplin — zuerst und geprüft dastehen. Was darauf aufbauen kann:

- **Ein autonomer MT4/MT5-Handel hinter der Freigabe.** Das Protokoll, die Tore und der
  Reconcile-Kreis stehen; es fehlt die Fachlogik (Signal/Struktur) und die reale Bindung.
  Weil die Sicherheit zuerst gebaut wurde, kann die Strategie darauf **gefahrlos** iterieren:
  jede Idee läuft erst als Demo/Paper, geführt durch Bewertungstor, Kriterien und
  Versuchsregister, bevor die vierfache Freigabe sie überhaupt live lässt.
- **Ein intelligentes Modell-/Agenten-Ensemble.** Der Signal-Pfad spricht nur gegen das
  `TradingVenue`-Protokoll — mehrere Strategien/Modelle können nebeneinander vorschlagen,
  während Hebelklammer, Verlustgrenzen und Global-Halt unabhängig darüber wachen. Ein
  wichtiger Grundsatz bleibt: **kein Modell schreibt Produktionscode zur Laufzeit.**
- **Mehrere Handelsplätze aus einem Kern.** Weil kein Kernmodul einen Plattformnamen kennt,
  ist ein zweiter Adapter (eine Börse, ein anderer Broker) eine neue `venue/`-Implementierung
  gegen denselben Vertrag — die gesamte Risiko-/Sperrschicht gilt sofort mit.
- **Nachprüfbare Forschung.** Purge/Embargo-Splits, Deflated Sharpe und das anhängende
  Versuchsregister sind die Bausteine, um Strategien ehrlich zu bewerten statt zu
  überanpassen — die Grundlage, damit „es funktioniert" gemessen und nicht behauptet wird.
- **Betrieb mit klaren Not-Aus-Pfaden.** Sobald Kill-Switch, Safety-Oracle und
  Exchange-Readiness aus `FEHLT.md` nachgezogen sind, entsteht ein Betrieb, in dem jeder
  gefährliche Zustand einen definierten, manuell zu lösenden Halt hat.

Der rote Faden: **erst die Sicherheit, dann die Fähigkeit.** Dieses Fundament macht den
nächsten, ambitionierten Ausbau möglich, ohne die Sperren nachträglich schwächen zu müssen.

---

## 9. Bedienung — die wichtigsten Befehle

```bash
# Alles prüfen (aus dem Repo-Ordner)
python -m pytest -q
python -m ruff check .
python -m mypy --strict mt5_trading_ai tools
python tools/gen_docs.py --check
python tools/check_docs_claims.py

# Modulübersicht neu erzeugen
python tools/gen_docs.py

# Demo-Smoke gegen ein echtes MT5 (auf der MT5-Maschine, im Demokonto angemeldet):
pip install MetaTrader5
python tools/mt5_smoke.py                 # nur lesend
python tools/mt5_smoke.py --allow-write    # winzige Demo-Order, sofort geschlossen
```

---

## 10. Abschluss

Dieser Baum ist der **sichere Anfang** eines MT5-Handelssystems: die Risiko- und Sperrschicht
ist herausgelöst und geprüft, ein venue-unabhängiges Gerüst mit MT5-Adapter, Katalog,
Reconcile und Ereignis-Sync steht darauf, und jede Sperre wurde negativ gefahren. Der Handel
mit Echtgeld bleibt bewusst hinter der mehrteiligen menschlichen Freigabe — und der nächste
Auftrag füllt die klar benannten Leerstellen, ohne das Fundament aufweichen zu müssen.

*Alhamdulillah.*
