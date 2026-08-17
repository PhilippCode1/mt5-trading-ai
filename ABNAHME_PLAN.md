# ABNAHME-PLAN — von getesteten Inseln zum verdrahteten Gesamtsystem

*Grundlage: Multi-Agenten-Bewertung von Paket 1–5 + der Verdrahtung (7 Prüf-Agenten, hoher
Effort, Kennzahlen selbst nachgerechnet). Dieser Plan wird später Paket für Paket abgearbeitet.
Er erhebt keine neue Strategie-Behauptung — das „kein Edge"-Urteil aus `BERICHT_TEIL3.md` bleibt
unberührt. Es geht ausschließlich um **Härtung + Verdrahtung**, bis die Abnahme-Bedingungen
aus §2 belegt erfüllt sind.*

---

## 1. Gesamtstand (ehrlich)

Der Forschungs-/Backtest-Kern ist stark und **echt verdrahtet**: bitgenaue Reproduktion, das
Sechs-Bedingungen-Tor greift real bis zum Edge, Leckageschutz per `LookAheadError`, das
Kostenmodell ist die einzige Kostenquelle im Backtest, Halal-Financing ist durchgereicht.

Die **Live-Ausführungsseite** dagegen ist eine Sammlung getesteter, aber **nicht verdrahteter
Inseln**. Der zentrale Order-Pfad `Mt5Venue.submit_order` sendet heute eine eröffnende Order
- **ohne Kostentor** (`order_roundturn_cost` hat 0 Aufrufe in `venue/`/`execution/`),
- **ohne Positionsgrößen-/Stop-Floor-Berechnung** (`risk/sizing.py` verwaist),
- **ohne Verlust-/Drawdown-Halt** (`risk/limits.py` nicht im Pfad),
- **ohne Frequenzdrossel** (`gates/evaluation.py` verwaist),
- **ohne Halal-Screen** (`venue/halal.py` screent keine reale Order).

Ebenso läuft das **Datenqualitätstor am Backtest-Rand fail-OPEN**: die Backtest-Treiber laden
per `from_csv` und gehen ohne `assess_or_raise` direkt in den Lauf; Prüfsumme/Manifest werden
nicht erzwungen. Im Backtest sind Purge/Embargo strukturell vorhanden, aber **funktional inert**
(kein Walk-Forward-Fit), und die Deflated Sharpe deflationiert die zu optimistische Bar-Sharpe
statt der Trade-Sharpe.

### Urteil je Teil

| Teil | Abnahme-fertig | Kern-Lücke |
|---|---|---|
| **Paket 1 — Kostenmodell** | fast | kein Pre-Trade-Kostentor im Live-Pfad; `hurdle_rate()` verwaist |
| **Paket 2 — Datenfundament** | **nein** | Qualitätstor läuft nicht am Backtest-Rand; Manifest write-only; S6 Kalender fehlt |
| **Paket 3 — Backtest-Maschine** | fast | Walk-Forward-Fit fehlt (S7); Deflation auf Bar- statt Trade-Sharpe (S8) |
| **Paket 4 — Edge-Test-Apparat** | fast | `main()` ohne Verhaltenstest; kein E2E-Fixture; Provenienz nicht erzwungen |
| **Paket 5 + Halal** | **nein** | Compliance-Tore (Halal/Demo/LLM) nicht am Order-/Live-Pfad durchgesetzt |
| **Verdrahtung/Integration** | **nein** | Risikoschicht verwaist (S1); kein Ende-zu-Ende-Runner; kein Treiber-Loop (S2) |

Drei Teile stehen auf „fast", drei auf „nein/Blocker". Der Weg zur vollständigen Abnahme ist
reine Verdrahtung + Härtung, keine neue Strategie.

---

## 2. Der 7-Paket-Plan

Reihenfolge: **Fundament und Verdrahtung zuerst, Integration + Ende-zu-Ende-Abnahme zuletzt.**
Jedes Paket wird — wie in Teil 3 — negativ gefahren, adversarial gegengeprüft und einzeln
abgenommen, bevor das nächste beginnt.

### Paket 1 — Datenfundament fail-closed schließen + Kalender-Härtung  *(groß)*

**Ziel:** Kein Backtest läuft auf ungeprüften oder manipulierten Bars; das Qualitätstor ist am
eigentlichen Backtest-Rand erzwungen, der Herkunftsnachweis ist integriert statt operator-abhängig.

**Inhalt:**
- Genau **ein** erzwungener Tor-Punkt am Backtest-Rand: entweder ruft `from_csv` `assess_or_raise`
  (bricht bei Tor-Versagen ab), oder die Backtest-Treiber (`tools/edge_test.py`,
  `tools/multi_instrument_edge.py`) rufen es vor `run_walk_forward`/`run_backtest`. Entscheidung
  dokumentieren.
- `data_checksum` in `run_backtest`/`run_walk_forward`/`run_registered_backtest` intern aus
  `bars_checksum(bars)` ableiten und gegen ein optionales Erwartungs-Argument prüfen; Mismatch →
  Abbruch. Keine fest leeren `data_checksum=''` mehr in den Treibern.
- `from_csv` liest das `manifest.json` neben der CSV und prüft `manifest_checksum` gegen die
  tatsächlich geladenen Bars (Divisor/Herkunft/Urteil); Abweichung → Abbruch. Das Manifest
  verliert seinen Write-only-Status.
- **S6:** Feiertags-/Intraday-Sitzungskalender statt nur `WeekdaySession` — Wochentags-Feiertage
  nicht als erwartete Slots zählen; FX-Sonntagsöffnung (~22:00 UTC) für Intraday-TFs korrekt als
  in-session.
- Loader-/Quality-Docstrings an den realen, jetzt fail-closed Datenfluss angleichen; SPAETER **S6**
  als erledigt markieren.

**Abnahme:** Neue Tests: (a) eine hand-editierte / nie durchs Tor gelaufene CSV fällt beim
Backtest-Einstieg fail-closed durch; (b) `data_checksum != bars_checksum(bars)` wirft; (c) eine
nachträglich veränderte CSV wird über das Manifest gefangen; (d) Wochentags-Feiertag treibt
`gap_ratio` nicht, Intraday-Sonntagsbars sind nicht `bars_outside_session`. Alle Suiten + CI grün.

### Paket 2 — Backtest-Integrität scharf stellen (Leckage, Kriterien, Deflation)  *(groß)*

**Ziel:** Der Leckageschutz gatet faktisch, die schärfsten Freigabe-Kriterien laufen im
Produktivpfad statt als Insel, und die Deflated Sharpe überzeichnet die Evidenz nicht mehr.

**Inhalt:**
- **Walk-Forward-Fit-Schritt (S7):** `run_walk_forward` nutzt `_train_idx` statt es zu verwerfen —
  Strategie/Parameter werden auf dem Trainingsfenster (außerhalb des Purge/Embargo-Bands)
  bestimmt, dann zustandsbehaftet auf `test_idx` getestet. Erst dadurch werden Purge/Embargo aus
  `splits.py` wirksam.
- **Deflation (S8):** `deflated_sharpe_for_report` auf die **Trade**-Sharpe umstellen (`per_obs`
  aus `report.trade_sharpe`, `observations` = Trade-Zahl) — konsistent zum Gate-Input
  `oos_sharpe = trade_sharpe`.
- Vollständige `evaluate_criteria` an die Backtest-Ausgabe binden (`BacktestEvidence` /
  `Preregistration` aus dem realen Lauf füllen und neben `evaluate_edge` auswerten).
- **Stress-Kosten-Backtest** als Produzent für `net_expectancy_at_stressed_cost` (zweiter Lauf mit
  erhöhtem Kostenfaktor); das `cost_stress`-Kriterium liefert dann echte Werte statt
  `not_evaluable`.
- Unit-Tests für `count_scope='total'` und den `ValueError`-Zweig — der real gefahrene
  Produktivzweig.

**Abnahme:** Test belegt, dass das Trainingsfenster das Fold-Ergebnis beeinflusst (Purge/Embargo
wirksam, keine Fassade). DSR-Test rechnet mit Trade-Zahl. `cost_stress` liefert im Kampagnenlauf
erfüllt/nicht-erfüllt statt `not_evaluable`. `count_scope='total'` + Fehlerzweig getestet. SPAETER
**S7/S8** erledigt. CI grün.

### Paket 3 — Pre-Trade-Kostentor an den Order-Pfad + `hurdle_rate` bereinigen  *(mittel)*

**Ziel:** Kein Live-Trade wird eröffnet, dessen Roundturn-Kosten den Backtest-Annahmen nie
gegengeprüft wurden; die Kosten-Doku ist widerspruchsfrei und tot-code-frei.

**Inhalt:**
- **Pre-Trade-Kostentor** in `submit_order`: vor dem Terminal-Send `order_roundturn_cost` für
  Instrument+Volumen rechnen und gegen eine konfigurierte Kosten-/Hürdenschwelle prüfen;
  Überschreitung → `OrderRejectedError(reason='cost_gate')` fail-closed. Falls bewusst **kein**
  Live-Kostentor gewollt ist, diese Entscheidung explizit dokumentieren (kein stiller Verzicht).
- `hurdle_rate()` auflösen: entweder im Backtest-Bericht verdrahten (die dortige Inline-Formel
  ersetzen, **eine** Quelle) oder Funktion samt Docstring-Zusage entfernen. Zwei parallele
  Hürdenformeln beseitigen.
- **S5** (Aktien-CFD ad valorem) bewusst als später dokumentieren: `load_cost_fees` lehnt `EQUITY`
  weiter fail-closed ab, der Katalog enthält kein `EQUITY` — Vermerk, dass das Tor erst bei
  Einzelaktien im Backtest nötig wird (nicht in diesem Plan gebaut).

**Abnahme:** Test: `submit_order` lehnt eine Order ab, deren Roundturn-Kosten die Schwelle reißen
(bzw. dokumentierte, begründete Nicht-Verdrahtung). `hurdle_rate` hat einen realen Aufrufer **oder**
ist entfernt; kein Doppel-Formel-Befund, keine widersprüchliche Docstring. CI grün.

### Paket 4 — Risikoschicht in den Order-Pfad verdrahten (S1) — der große Block  *(groß)*

**Ziel:** Die vorgeschriebene Reihenfolge **Stop-Floor → Budget → Größe → Hebel** und die
Verlust-/Frequenzgrenzen sind zur Laufzeit wirksam; kein Trade läuft über Budget oder Limit hinaus.
Die Risikoschicht ist real, nicht Insel. *(Das ist genau der Fehler aus dem Altbestand: getestet,
aber am Live-Pfad nie aufgerufen — „mitgekommen ≠ verdrahtet".)*

**Inhalt:**
- **`risk/sizing.py`** in `submit_order` verdrahten: statt `request.volume`/`stop_loss` als gegeben
  zu nehmen, die Reihenfolge Stop-Floor → Budget → Größe → Hebel durchlaufen; berechnetes/
  validiertes Volumen gegen das Risikobudget prüfen, Überschreitung → Ablehnung.
- **`risk/stop_budget.py`** wirksam machen: Stop-Budget je Anlageklasse im Order-Pfad vergleichen
  (`no_trade`, wenn Floor > Budget) — nicht mehr nur über `sizing` erreichbar.
- **`risk/limits.py`** zur Laufzeit rechnen: Tagesverlust, Drawdown-Halt, Max-Positionen, Gap-Regel
  bei jeder eröffnenden Order auswerten und bei Verletzung über den bestehenden `_halted`-Latch
  halten — statt nur des menschlich gesetzten `live_release_risk_limits_configured`-Flags.
- **`gates/evaluation.py`** verdrahten: Throttle / Mindesthaltedauer / Cooldown / Trade-Obergrenze /
  ein-Gewinner-je-Durchlauf zwischen Bewertungstakt und `submit_order` schalten — „Bewerten ≠
  Handeln" erzwungen.
- Docstrings von `risk/limits.py` und `risk/sizing.py` an den nun verdrahteten Zustand angleichen;
  Insel-Vermerke entfernen.

**Abnahme:** Order-Pfad-Tests: (a) Volumen über Risikobudget → Ablehnung; (b) Stop-Floor > Budget →
`no_trade`; (c) überschrittenes Tagesverlust-/Drawdown-Limit setzt `_halted` und blockt weitere
Eröffnung; (d) zu schneller zweiter Bewertungstakt wird von der Drossel abgewiesen. Jedes der vier
Module hat mindestens einen Aufrufer im Order-Pfad (nachweisbar), nicht nur Tests. SPAETER **S1**
erledigt. CI grün.

### Paket 5 — Compliance-Tore an den Live-/Demo-Pfad (Halal, Demo, LLM)  *(mittel)*

**Ziel:** Halal-Screen, Demo-Reife und LLM-Zulassung sind als **Tore wirksam** statt als Funktionen —
keine reale Order / kein Live-Schritt ohne bestandenes Tor. *Die fiqh-Bewertung selbst bleibt beim
Gelehrten (Kernregel 16).*

**Inhalt:**
- **`screen_halal`** in `submit_order` aufrufen: jede eröffnende reale Order wird gegen
  Instrument/Kontokonfiguration gescreent, `requires_scholar_review` bleibt fail-closed wahr;
  Nicht-Bestehen → Ablehnung. Kernregel 16 systemseitig durchgesetzt.
- **Demo-Fortschritts-Tor binden:** `venue/smoke.py` (echte Demo-Harness) füttert
  `register_for_demo`/`evaluate_demo_progress` mit realen Edge-Verdicts, und das Live-Freigabe-Tor
  fragt `DemoReadiness` ab → keine Live-Frage vor ≥ 180 Tagen + weiter bestandenem Edge.
- **`evaluate_llm_gate`** verankern: entweder einen Durchsetzungspunkt schaffen, bevor je ein Modell
  in den Entscheidungspfad käme, oder dokumentiert festhalten, dass der Pfad LLM-frei ist und dieses
  Tor die einzige Zulassungsstelle bleibt.
- Fiqh-Inhalt bewusst ausklammern: kein Engineering an der religiösen Bewertung; Verweis, dass die
  scholar-review-Frage an einen Gelehrten geht (S4).

**Abnahme:** Test: `submit_order` lehnt ein nicht-halal-Instrument fail-closed ab (Screen im
Order-Pfad, nachweisbar außerhalb Tests). Test: Live-Freigabe scheitert, solange `DemoReadiness`
< 180 Tage oder Edge nicht bestanden; besteht mit realem `run_backtest → evaluate_edge →
register_for_demo`-Fluss. LLM-Tor hat einen verankerten Aufrufpunkt **oder** einen dokumentierten
Frei-Vermerk. CI grün.

### Paket 6 — Werkzeug-Härtung (Verhaltens-Tests, CSV-Fixture, erzwungene Provenienz)  *(mittel)*

**Ziel:** Die Forschungs-Werkzeuge sind regressionsfest auf ihrem real gefahrenen Pfad, ein
Mini-Fixture beweist die Kette in der CI, und kein registrierter Versuch geht mit leerer Herkunft
ins Ledger.

**Inhalt:**
- Verhaltens-Test für `edge_test.main()`: belegt die Register-Disziplin — Zufalls-/Leckagelauf
  bekommt **kein** `ledger_path`, WF-Folds + der eine OoS-Lauf schon; ein versehentliches
  `ledger_path` am Kontrolllauf fällt rot durch.
- Mini-CSV-Fixture ins Repo + End-to-End-Smoke: `from_csv → run_walk_forward →
  run_registered_backtest → deflated_sharpe_for_report → Tor` als **ein** zusammenlaufender Lauf in
  der Test-/CI-Grenze.
- **Provenienz erzwingen:** Datenprüfsumme automatisch aus den CSV-Bytes, Codestand aus git — ein
  registrierter Versuch mit leerer Provenienz ist nicht mehr möglich (passt zur Checksum-Bindung
  aus Paket 1).
- Unit-Test für `tools/multi_instrument_edge.py` (`_run_one`/`main`): Walk-Forward,
  `run_registered_backtest`, Deflation `count_scope='total'`, Leckage-/Zufallsreferenz, `argparse`.
- `demo_run` End-to-End-Test mit **echtem** Verdict: `EdgeVerdict` aus einem realen
  `run_backtest → evaluate_edge`-Lauf statt handgebautem `passed`-Flag.

**Abnahme:** CI führt den E2E-Smoke auf dem Fixture aus und ist grün. Register-Disziplin-Test rot
bei falschem `ledger_path` am Kontrolllauf. Ein Lauf ohne ableitbare checksum/commit wird abgelehnt.
`multi_instrument_edge` und `demo_run` haben eigene, in CI laufende Tests mit echtem Verdict.

### Paket 7 — Ende-zu-Ende-Runner + Treiber-Loop + Abnahme-Checkliste  *(groß)*

**Ziel:** Alle verdrahteten Einzelteile spielen in **einem** beweisbaren Lauf zusammen, die Drift-/
Frische-Prüfungen laufen getaktet statt passiv, und eine Checkliste stellt die vollständige Abnahme
fest.

**Inhalt:**
- **Integrierender Runner** mit `main()`: `Signal → Halal-Screen → Sizing → Stop-Budget → Limits →
  Evaluation-Gate → submit_order` als ein Paper-/Dry-Run-Kommando, das die in Paket 3–5 verdrahteten
  Nähte in einem Durchlauf zusammenführt (heute existiert kein solcher Runner außer der
  Forschungs-Kette `edge_test`).
- **Treiber-Loop/Scheduler** für `check_sync` und `reconcile`: periodische Frische-/Stille-/
  Drift-Prüfung, die den Halt taktgetrieben setzt — Frische-Latch am Halt (**S2**) geschlossen.
- Gesamt-Doku angleichen: `MASTERBERICHT`/`MODULES`/`SPAETER` auf den verdrahteten Endzustand
  bringen; keine Kill-Switch-/Risikoschicht-Zusage ohne realen Aufrufer, keine Insel-Restvermerke.
- **Abnahme-Checkliste** gegen den Runner abarbeiten: jede Naht (Daten-Tor, Kostentor, Sizing,
  Budget, Limits, Evaluation, Halal, Demo-Freigabe, Provenienz, Deflation) einmal im integrierten
  Lauf grün quittiert; SPAETER **S1/S2** erledigt.
- Vollständigen Testlauf + CI grün bestätigen (Baseline plus alle neuen Naht-Tests).

**Abnahme:** Ein Kommando führt die volle Kette `Signal → … → Order` auf dem Fixture/Paper-Terminal
aus, und die Checkliste ist Punkt für Punkt grün. Der Scheduler taktet `check_sync`/`reconcile`
nachweisbar (Test mit simulierter Drift setzt den Halt automatisch). Gesamt-Testsuite und CI grün,
keine Doku-Zusage mehr ohne Aufrufer im Pfad.
~~**System komplett abnahmefertig.**~~ — **WIDERRUFEN am 2026-08-17 (Paket 2).**
Der Satz war unwahr: die Risikoschicht war zwar am Order-Pfad aufgerufen, stieg aber
bei einem Demokonto sofort wieder aus (`Mt5Venue._enforce_risk`, `if account.is_demo:
return`) — und ein Live-Konto gab es nicht. Sie lief damit an keinem erreichbaren
Konto. Eine Abnahme, die das nicht bemerkt, ist keine Abnahme. Paket 2 hat den
Ausstieg entfernt und ein zaehlendes Dauertor dagegen gestellt.

---

## 3. Was NICHT zu diesem Plan gehört

- **Keine neue Strategie, kein neuer Edge-Versuch.** Die Edge-Frage ist dreifach, reproduzierbar und
  ehrlich mit „kein Edge" beantwortet (`BERICHT_TEIL3.md`). Weiter zu bauen jagt einen bewiesenen
  Negativbefund.
- **Keine fiqh-Bewertung.** Ob gehebelte CFDs grundsätzlich zulässig sind (gharar), entscheidet ein
  Gelehrter + Philipp, nicht der Code (S4). Der Code erzwingt nur das mechanisch Prüfbare.
- **Kein Echtgeld.** Der ganze Plan bleibt Backtest/Paper/Demo; die vierteilige Live-Freigabe bleibt
  unberührt und geschlossen.

## 4. Reihenfolge und Abhängigkeiten

```
P1 Daten-Tor ─┐
P2 Backtest   ─┼─► P6 Werkzeug-Härtung ─► P7 Ende-zu-Ende + Abnahme
P3 Kostentor ─┤                            ▲
P4 Risiko(S1)─┤                            │
P5 Compliance─┘────────────────────────────┘
```

P1–P5 schließen je eine Naht (Fundament + Verdrahtung) und sind weitgehend unabhängig; **P4 (S1)
ist der größte und wichtigste Block**. P6 härtet die Werkzeuge, sobald die Nähte stehen. P7 führt
alles in einem Runner zusammen und stellt per Checkliste die komplette Abnahme fest. Jedes Paket
wird einzeln negativ gefahren, §9-gegengeprüft und abgenommen, bevor das nächste beginnt.
