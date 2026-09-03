# VERLUST.md — was zurueckblieb, und was das bedeutet

*Der gefaehrliche Fehler dieses Auftrags ist nicht, zu viel zurueckzulassen, sondern
etwas Gebrauchtes zurueckzulassen und es nicht zu merken (Teil 7). Diese Datei ordnet
jede Faehigkeit und jede Sperre des Altbestands ein: **mitgekommen**, **neu zu schreiben**
oder **bewusst entfallen**. Bei „entfallen" steht in einem Satz, warum der Wegfall die
Freigabe **nicht** erleichtert.*

**Methode:** Die nicht umgezogenen Faehigkeiten und Sperren sind vollstaendig aus dem Code
des Altbestands enumeriert (15 Dienste unter `services/`, dazu `shared/python/src/shared_py/`
und `config/`). Anker stehen als `pfad:zeile`. Gemessen, nicht angenommen.

---

## 1. Fähigkeiten

### 1a. Mitgekommen (im Kern, mit Datei und Test)

| Faehigkeit | Datei im Kern | Test |
| --- | --- | --- |
| Hebelklammer `min(want, 10, Klassendeckel)`, unbekannte Klasse → no_trade | `mt5_trading_ai/risk/leverage.py` | `test_asset_class_leverage.py` (rot-geprueft) |
| Tagesverlust, Drawdown-Halt (kein Selbst-Reset), Positionsdeckel | `mt5_trading_ai/risk/limits.py` | `test_loss_limits.py` |
| Risikoanteil, Stop-Floor, Positionsgroesse | `mt5_trading_ai/risk/sizing.py` | `test_risk_sizing.py` |
| Stop-Budget je Anlageklasse | `mt5_trading_ai/risk/stop_budget.py` | `test_stop_budget.py` |
| Mehrteilige Live-Freigabe (4 Schalter + Kennung, Fail-Closed) | `mt5_trading_ai/execution/release.py` | `test_live_release.py` (rot-geprueft) |
| Bewertungstor: Schwelle, Haltedauer, Abklingzeit, Korrelationsdeckel | `mt5_trading_ai/gates/evaluation.py` | `test_evaluation_gate.py` |
| Vorregistrierte Kriterien, Deflated Sharpe | `mt5_trading_ai/gates/criteria.py` | `test_strategy_criteria.py` |
| Versuchsregister `TRIALS.jsonl` (anhaengend) | `mt5_trading_ai/gates/trials.py` | `test_trials_ledger.py` |
| Lernphase: Rangliste, Schwaechenbefunde, Grenzen | `mt5_trading_ai/gates/learning_phase.py` | `test_learning_phase.py` |
| Datenqualitaet: Lueckenquote, Zeitstempel, Ausreisser, Handelszeiten | `mt5_trading_ai/data/quality.py` | `test_data_quality.py` |
| `TradingVenue`-Protokoll | `mt5_trading_ai/venue/protocol.py` | Vertragstest inzwischen vorhanden (`tests/test_mt5_venue.py`: der Adapter erfüllt das Protokoll, statisch + gegen ein Fake-Terminal geprüft) |
| Zeitreihen-Splits mit Purge/Embargo, Walk-Forward bis Datenende | `mt5_trading_ai/backtest/splits.py` | `test_splits.py` (Fold-Fix rot-geprueft) |

### 1b. Neu zu schreiben (wird gebraucht → `FEHLT.md`)

Fachlogik, die im Altbestand an Bitget, Redis, Postgres oder einem Ereignisfluss hing.
Nicht mitgekommen; wird gebraucht, sobald ein Ausfuehrungspfad entsteht. Aufwand grob
(S/M/L), keine Zusage.

| Faehigkeit (Herkunftsdienst) | Warum nicht mitgekommen | Schaetzung |
| --- | --- | --- |
| Orderbuch-CRC32-Pruefsumme, Sequenzluecken-Erkennung, REST-Nachzug, Feed-Health (`market-stream`) | haengt am Venue-WS/Feed | M |
| Swing-/BOS-/CHOCH-/Kompressions-Erkennung (`structure-engine`) | Fachlogik am Marktdatenfluss | L |
| Zeichnungen/Level/Liquiditaetszonen (`drawing-engine`) | am Strukturfluss | M |
| Feature-Berechnung, Korrelationsgraph, Microstructure (`feature-engine`) | am Candle-/Tick-Fluss | L |
| Signal-/Entscheidungskern, Ensemble, Scoring-Stack (`signal-engine`) | am Ereignisfluss + Modelle | L |
| Family-aware Fee/Funding/Slippage/Liquidation (`paper-broker`) | am Instrumentenkatalog | M |
| Order-/Execution-Service, Reconcile, Private-WS/REST (`live-broker`) | am echten Venue-Konto | L |
| Instrumentenkatalog mit Fail-Closed-Pruefungen | Venue-/Katalogdaten | M |
| Hash-verkettetes Audit-Ledger + Regulatorik-Export (`audit-ledger`) | fuer Live-Audit noetig | M |
| Health-Monitoring / Incident-RCA (`monitor-engine`) | am Dienstverbund | M |
| **Anschluss der Hebelklammer an einen realen Order-Pfad** | siehe Befund 2 | S |

### 1c. Bewusst entfallen (Begruendung je Zeile — Wegfall erleichtert keine Freigabe)

| Faehigkeit | Begruendung |
| --- | --- |
| Kommerz-/Abrechnungsschicht (`SUBSCRIPTION_BILLING_*`, Prepaid) | Der Kern verkauft nichts; die alten Kommerzgates blockierten Live-Orders zufaellig ueber einen fehlenden Vertrag, nicht ueber Sicherheit — ersetzt durch die echte Sperre `execution/release.py`, nicht geoeffnet. |
| Dashboard / TypeScript-Werkzeugkette | Der Kern ist eine lokale Bibliothek ohne Oberflaeche; keine Sperre haengt daran. |
| Docker / Compose / Infra / DB-Migrationen | Kein Dienst, kein Server, keine DB im Kern. |
| Telegram-Betreiberkommandos (`alert-engine`) | Der Betreiberkanal entfaellt; die eigentliche **Not-Aus-Faehigkeit** ist als „Kill-Switch" unter 2b (neu zu schreiben) erfasst — es geht also keine Stopp-Moeglichkeit verloren. |
| LLM-Orchestrierung, Agenten, News/Social (`llm-orchestrator`, `news-engine`) | Nicht sicherheitstragend; falls spaeter gewuenscht, neu und **unter Teil 3 VII** (kein LLM schreibt Produktionscode zur Laufzeit). |
| Single-Admin-/Service-Auth | Mehrbenutzer-/Dienst-Auth ist in einer lokalen Ein-Personen-Bibliothek gegenstandslos; keine Handels-Sperre haengt daran. |

---

## 2. Sperren — jede einzeln (der Kern dieser Datei)

Eine Sperre ersatzlos zu streichen erleichtert **immer** die Freigabe. Deshalb steht jede
einzeln, mit Anker und Einordnung.

### 2a. Mitgekommen (im Kern, geprueft)

| Sperre | Nachweis im Kern |
| --- | --- |
| Hebelklammer (Deckel 10, nicht konfigurierbar darueber) | rot-geprueft; ersetzt den alten 7/75-Deckel (siehe Befund 2) |
| Live-Freigabe (4 Schalter + Kennung, „nicht bewertbar = nicht erfuellt") | rot-geprueft (Teilmengen-Test) |
| Verlustgrenzen (Tagesverlust, Drawdown-Halt ohne Selbst-Reset, Positionsdeckel) | `test_loss_limits.py` |
| Bewertungstor (Schwelle/Haltedauer/Abklingzeit/Korrelationsdeckel) | `test_evaluation_gate.py` |
| Datenqualitaets-Tor (Fail-Closed bei schlechten Daten) | `test_data_quality.py` |
| Splits-Leckage-Sperre (Purge/Embargo, kein Default 0 mehr) | Fold-Fix rot-geprueft; Default korrigiert |

### 2b. Neu zu schreiben (Sicherheitsapparat des Ausfuehrungspfads)

Der Altbestand trug einen umfangreichen Fail-Closed-Apparat am **Live-Order-Pfad**. Keiner
davon kommt mit (er haengt am echten Konto/Feed), aber **jeder muss stehen, bevor ein
Ausfuehrungspfad entsteht** — sonst waere „nicht mitgekommen" eine geoeffnete Tuer. Alle
gehoeren in `FEHLT.md`.

| Sperre | schuetzt/blockiert | Anker (Altbestand) |
| --- | --- | --- |
| **Kill-Switch** (arm/release, reduce-only-Pfad) | neue Orders unter gezogenem Schalter | `live-broker/api/routes_ops.py:232,203` |
| **Global-Halt-Latch** (`system:global_halt`) | jede Order bei systemweitem Halt | `live-broker/global_halt_latch.py:22` |
| **Runtime-Safety-Oracle** (Axiom-Checks → Global-Halt) | „letzte Verteidigungslinie" | `shared_py/bitget/runtime_safety_oracle.py:120` |
| **Exchange-Readiness** (`WRITE_ORDER_ALLOWED_DEFAULT=False`, Zeitversatz) | Schreib-Orders ohne Bereitschaft | `shared_py/bitget/exchange_readiness.py` |
| **Live-Preflight** (Owner-Freigabe, Execution-Mode) | Submit ohne Preflight | `shared_py/live_preflight.py:102,208` |
| VPIN-Hard-Halt (`VPIN_HARD_HALT_THRESHOLD`) | Handel bei toxischem Fluss | `live-broker/execution/risk_adapter.py:355` |
| Liquiditaets-/Slippage-Guard | Market-Order ohne Liquiditaet | `live-broker/execution/liquidity_guard.py:166` |
| Strategie-Config-Pruefsumme | falsche/unbekannte Strategie-Version | `live-broker/strategy_config_guard.py:20` |
| Positions-Drift-Halt (Notional-Drift → Global-Halt) | Divergenz Konto/Buch | `live-broker/reconcile/position_drift.py:59` |
| Reconcile-Snapshot / Public-Probe Fail-Closed | Submit ohne frischen Abgleich | `live-broker/orders/service.py:2078,2120` |
| Instrumentenkatalog-Fail-Closed (Katalog/Metadaten/Family/Product-Type/Margin-Coin) | Order ohne gueltige Instrumentendaten | `live-broker/orders/service.py:2658–2748` |
| exit_safety (Reduce-Only-Durchsetzung) | Blockade des Schliessens erhoeht Risiko | `shared_py/exit_safety.py:19` |
| portfolio_risk_controls (RiskState: halt_new_entries/reduce_only/global_halt) | Portfolio-weite Sperrzustaende | `shared_py/portfolio_risk_controls.py` |
| uncertainty_gates (Lane: live<paper<shadow<do_not_trade) | Handel bei zu hoher Unsicherheit | `shared_py/uncertainty_gates.py` |
| rejection_rules (hart/weich → do_not_trade) | strukturelle Ablehnung | `signal-engine/scoring/rejection_rules.py:28` |
| pipeline_gates / health_map (ok/analytics_only/do_not_trade) | Handel bei ungesundem Zustand | `shared_py/analysis/pipeline_gates.py` |
| secret_leak_guard (Redaction in Logs/Audit) | Geheimnis-/PII-Leck in Protokollen | `shared_py/observability/secret_leak_guard.py` |

### 2c. Zu bewerten / bewusst entfallen

| Sperre | Einordnung | Begruendung |
| --- | --- | --- |
| inference_governance (TSFM-Timeout Fail-Closed) | **neu zu schreiben, falls Inferenz kommt** | Der Kern hat keine Inferenz; entfaellt heute, muss aber vor jeder Modell-Inferenz stehen. |
| survival_kernel (autonomer Survival-Modus, Rust-FFI) | **zu bewerten** | Komplex und an Regime/FFI gebunden; vor Uebernahme einzeln pruefen — kein stiller Wegfall. |
| single_admin_access / service_auth | **entfallen** | Kein Mehrbenutzer-/Dienstkontext im Kern; erleichtert keine Handels-Freigabe. |

---

## 3. Zwei Befunde, ausdruecklich zu uebernehmen (Teil 7 Punkt 4 → `FEHLT.md`)

**Befund 1 — `portfolio_risk_state_unknown_or_stale`: BESTAETIGT.**
Der Guard liest im Order-Trace `portfolio_risk_check_fresh`
(`live-broker/orders/service.py:2437`) und wirft bei fehlendem/falschem Wert
`portfolio_risk_state_unknown_or_stale` (`:2444`). Eine Suche zeigt: der Schluessel wird
**nirgends im Produktionscode gesetzt** — der einzige Setzer ist ein Unit-Test
(`tests/unit/live_broker/test_private_rest_client.py:468`). Damit blockierte der Guard
**jede eroeffnende Order**. Sichere Richtung — aber es bedeutet, dass der
Ausfuehrungspfad nie durchgelaufen ist. Vom Altbestand selbst bestaetigt
(`PROGRESS.md:824`). → offene Frage in `FEHLT.md`.

**Befund 2 — Hebelklammer 7/75: Zahlen BESTAETIGT, „nicht angeschlossen" KORRIGIERT.**
Die Defaults und Validatoren stimmen: `config/settings.py:347/349` (7/75, Bereich 7..75),
`paper-broker/config.py:50/51` (7/75, Validatoren 7..75). **Aber:** die alte Behauptung
„nicht angeschlossen" gilt nur fuer den **Live-Broker-Order-Pfad** — dort taucht
`risk_allowed_leverage_min/max` nicht auf. In `signal-engine`, `paper-broker` und
`shared_py` ist der 7/75-Deckel sehr wohl **aktiv verdrahtet**
(`signal-engine/risk_governor.py:558`, `hybrid_decision.py:157`,
`paper-broker/strategy/sizing.py:81`, `shared_py/unified_leverage_allocator.py:102` u. a.).
Zwei Konsequenzen: (a) der Live-Pfad war ungeklammert, ist aber ohnehin durch Befund 1
blockiert; (b) der **Kern ersetzt 7/75 durch den ESMA-Deckel ≤ 10** — die Extraktion hat
die Obergrenze also von 75 auf 10 gesenkt, und die alten 7/75-Defaults sind bewusst
zurueckgeblieben. Der **Anschluss** der Kern-Klammer an einen realen Order-Pfad ist neu zu
schreiben. → `FEHLT.md`.

---

## Abnahme U5

- [x] Faehigkeiten vollstaendig eingeordnet (mitgekommen / neu / entfallen), aus dem Code enumeriert.
- [x] Jede Sperre einzeln, mit Anker und Einordnung; bei „entfallen" begruendet.
- [x] Die zwei Pflicht-Befunde uebernommen; Befund 2 gegen die Messung korrigiert.
- [x] **Philipp vorgelegt, bevor U6 beginnt** — entschieden und in `PROGRESS.md` (U6)
  protokolliert: 2b/2c bleiben fuer den naechsten Auftrag in `FEHLT.md`.
