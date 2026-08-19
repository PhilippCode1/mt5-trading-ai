<!-- GENERIERT von tools/gen_docs.py — nicht von Hand bearbeiten -->

# MODULES — oeffentliche API je Modul (generiert aus dem Code)

Diese Datei ist die **einzige** Stelle, an der die Zeilenzahl je Modul steht.
Sie wird erzeugt, nicht gepflegt. Andere Dokumente verweisen hierher; das
Zahlen-Tor (`tools/check_doc_numbers.py`) blockt eine Wiederholung, weil eine
von Hand gefuehrte Zeilenzahl mit dem naechsten Commit driftet.

## `mt5_trading_ai/backtest/edge.py`

Zeilen: 113

Das Sechs-Bedingungen-Tor des Edge-Tests (Paket 4, §7.2).

- `class EdgeThresholds`
- `class EdgeCheck`
- `class EdgeVerdict`
- `def max_consecutive_positive`
- `def evaluate_edge`

## `mt5_trading_ai/backtest/engine.py`

Zeilen: 677

Backtest-Maschine: fuehrt Splits, Daten und Kostenmodell zusammen.

- `class Signal`
- `class LookAheadError`
- `class DataProvenanceError`
- `class MarketView`
- `def random_signal_strategy`
- `class MarketSpec`
- `class TradeRecord`
- `class BacktestReport`
- `def run_backtest`
- `class WalkForwardResult`
- `def run_walk_forward`
- `def deflated_sharpe_for_report`
- `def stressed_spec`
- `def criteria_evidence`
- `def run_registered_backtest`

## `mt5_trading_ai/backtest/ereignisstudie.py`

Zeilen: 469

Ereignisstudie — traegt eine bekannte Zwangslage mehr als ihre Kosten?

- `class StudienError`
- `class Kerze`
- `class Ereigniswert`
- `class Bestaetigung`
- `class Ergebnis`
- `def reihen_pruefsumme`
- `def kampagne`
- `def messe_ereignis`
- `def balkenstunden`
- `def studie`
- `def bestaetige`

## `mt5_trading_ai/backtest/kalender.py`

Zeilen: 372

Ereigniskalender — wann genau ist das Ereignis, in echtem UTC?

- `class KalenderError`
- `def server_zu_utc`
- `def utc_zu_server`
- `def verlange_echtes_utc`
- `class Kandidat`
- `def ereignisse`
- `def kandidat`
- `class Ereigniskalender`
- `def default_calendar_path`
- `def load_ereigniskalender`

## `mt5_trading_ai/backtest/llm_compare.py`

Zeilen: 71

Paket 5: das Tor fuer ein LLM im Entscheidungspfad (§8.2-8.4).

- `class LlmGateInputs`
- `class LlmGateDecision`
- `def evaluate_llm_gate`

## `mt5_trading_ai/backtest/provenance.py`

Zeilen: 117

Herkunft eines Backtest-Laufs: der Codestand aus git (Paket 6).

- `class ProvenanceError`
- `def code_commit_from_git`

## `mt5_trading_ai/backtest/resolution.py`

Zeilen: 360

Aufloesung einer Ereignisstudie — kann sie den Effekt ueberhaupt sehen?

- `class ResolutionError`
- `class DeflationUnreachableError`
- `class ResolutionVerdict`
- `def deflation_observations`
- `def required_sharpe`
- `def window_returns_bps`
- `def dispersion_bps`
- `def assess`
- `def min_events_for_resolution`

## `mt5_trading_ai/backtest/splits.py`

Zeilen: 190

Zeitreihen-Splits mit Purge und Embargo — herausgeloest aus learning_engine.

- `class Range`
- `def purged_walk_forward_indices`
- `def purged_kfold_embargo_indices`
- `def walk_forward_indices`

## `mt5_trading_ai/backtest/strategies.py`

Zeilen: 123

Einfache, ernsthafte Signallogiken fuer den Edge-Test -- ohne Optimierung.

- `def moving_average_crossover`
- `def mean_reversion_zscore`
- `def volatility_breakout`

## `mt5_trading_ai/betrieb/journal.py`

Zeilen: 596

Betriebsjournale lesen -- die eine Stelle, an der aus Zeilen Aussagen werden.

- `class JournalError`
- `class Satz`
- `class Trade`
- `class Lauf`
- `def lies_journal`
- `def lies_alle`
- `def durchgehende_equity`
- `class Bilanz`
- `def bilanz`
- `class Geldbilanz`
- `def geldbilanz`

## `mt5_trading_ai/costs/broker_costs.py`

Zeilen: 454

Broker-Kostentabelle — versioniert, belegt, fail-closed.

- `class BrokerCostsError`
- `class InstrumentCost`
- `class Broker`
- `class BrokerCosts`
- `def default_costs_path`
- `def load_broker_costs`

## `mt5_trading_ai/costs/halal.py`

Zeilen: 50

Der Halal-Pfad: swapfreie Finanzierung ohne Zins (S4, Kernregel 16).

- `class HalalFinancingPolicy`
- `def halal_financing`

## `mt5_trading_ai/costs/model.py`

Zeilen: 238

Kostenmodell: die realen Kosten einer Order, gemessen statt angenommen.

- `class CostModelError`
- `class CostBreakdown`
- `def order_roundturn_cost`
- `def load_cost_fees`

## `mt5_trading_ai/costs/volatility.py`

Zeilen: 385

Gemessene Volatilitaet je Instrument — ATR(14) und die Ablage dafuer.

- `class AtrMeasurementError`
- `class Candle`
- `class AtrMeasurement`
- `def percentile`
- `def true_ranges`
- `def gap_count`
- `def wilder_atr`
- `def atr_series_bps`
- `def not_measured`
- `def default_measurements_path`
- `def load_atr_measurements`
- `def load_fx_rates`

## `mt5_trading_ai/data/loader.py`

Zeilen: 452

Lader fuer historische Bars -- an das Datenqualitaetstor gekettet.

- `def dukascopy_price_divisor`
- `class DataLoadError`
- `class WeekdaySession`
- `class FxSession`
- `def decode_dukascopy_candles`
- `def parse_yahoo_daily`
- `def filter_to_weekdays`
- `def assess_or_raise`
- `def to_csv`
- `def from_csv`
- `def bars_checksum`
- `def manifest_path_for`
- `def load_verified_csv`
- `def dataset_manifest`
- `def manifest_checksum`

## `mt5_trading_ai/data/quality.py`

Zeilen: 246

Datenqualitaet als Gate (Phase 7.2).

- `class BarRow`
- `class QualityReport`
- `def expected_bar_count`
- `class SessionPredicate`
- `def assess_bars`
- `def render_markdown`

## `mt5_trading_ai/execution/cost_gate.py`

Zeilen: 130

Pre-Trade-Kostentor am Order-Pfad.

- `class CostGate`
- `class CostGateDecision`
- `def evaluate_cost_gate`

## `mt5_trading_ai/execution/freshness.py`

Zeilen: 246

Frische-Latch fuer den Kontozustand — S2 aus Paket 0.

- `class FreshnessVerdict`
- `def evaluate_account_freshness`

## `mt5_trading_ai/execution/leverage_preflight.py`

Zeilen: 106

Anschluss der Hebelklammer an den Order-Pfad.

- `class LeveragePreflight`
- `def evaluate_leverage_preflight`

## `mt5_trading_ai/execution/private_sync.py`

Zeilen: 89

Private Ereignis-Synchronisation: der Kontostrom haelt das Buch aktuell.

- `class PrivateEventKind`
- `class PrivateEvent`
- `class PrivateSync`

## `mt5_trading_ai/execution/reconcile.py`

Zeilen: 113

Order-Lebenszyklus und Reconcile: Konto gegen Buch.

- `class PositionBook`
- `def positions_to_net`
- `class SymbolDrift`
- `class ReconcileResult`
- `def reconcile_positions`

## `mt5_trading_ai/execution/release.py`

Zeilen: 128

Mehrteilige Freigabe fuer Order-Submit an einen echten Markt.

- `class LiveReleaseDecision`
- `def evaluate_live_release`
- `def live_release_blocks_opening_order`

## `mt5_trading_ai/execution/risiko_zustand.py`

Zeilen: 1596

Der Risikozustand, der einen Neustart ueberdauert -- und wie er fail-closed liest.

- `class ZustandsortFehler`
- `def verbotene_baeume`
- `def standard_zustandsordner`
- `def standard_zustandsdatei`
- `def korb_start`
- `def fenster_fortschreiben`
- `def fenster_vereinen`
- `class RisikoLage`
- `def lage_vereinen`
- `class Zustandsbefund`
- `class DateiZustand`

## `mt5_trading_ai/execution/risk_manager.py`

Zeilen: 1183

Risikoschicht am Order-Pfad: die vier Grenzen als letzte Verteidigungslinie.

- `class RiskPolicy`
- `class RiskAuthorization`
- `def freigabe_gueltig`
- `def measured_cost_from_meta`
- `class RiskManager`

## `mt5_trading_ai/execution/runner.py`

Zeilen: 448

Integrierender Paper/Dry-Run-Runner (Paket 7): die eine beweisbare Kette.

- `class RunnerConfig`
- `class SeamStep`
- `class RunnerReport`
- `def run_signal`

## `mt5_trading_ai/execution/scheduler.py`

Zeilen: 123

Treiber-Loop/Scheduler (Paket 7): Frische, Drift und Drawdown-Peak getaktet pruefen.

- `class TickResult`
- `class SyncScheduler`

## `mt5_trading_ai/gates/criteria.py`

Zeilen: 393

Vorregistrierte Kriterien und ihre Auswertung (Phase 9.3).

- `class Preregistration`
- `class BacktestEvidence`
- `class CriterionResult`
- `class CriteriaVerdict`
- `def evaluate_criteria`
- `def expected_max_sharpe`
- `def deflated_sharpe_ratio`
- `def annualise_sharpe`
- `def percentile_against_random`

## `mt5_trading_ai/gates/evaluation.py`

Zeilen: 207

Bewerten ist nicht handeln (Phase 8.3).

- `class ThrottlePolicy`
- `class Candidate`
- `class OpenPosition`
- `class GateState`
- `class GateDecision`
- `class GateResult`
- `def select_one`
- `def trade_rate`

## `mt5_trading_ai/gates/learning_phase.py`

Zeilen: 302

Lernphase: bewerten und ordnen (Phase 9.5).

- `class LearningPhaseError`
- `class TradeRow`
- `class EvaluationRow`
- `class Ranking`
- `class Weakness`
- `class Proposal`
- `class LearningReport`
- `def rank_strategies`
- `def find_weaknesses`
- `def observed_trade_rate`
- `def validate_proposal`
- `def propose_parameter_sets`
- `def build_report`

## `mt5_trading_ai/gates/trials.py`

Zeilen: 319

Trials-Ledger (Phase 9.4) — ``TRIALS.jsonl``, ausschliesslich anhaengend.

- `class TrialsLedgerError`
- `class Trial`
- `def new_trial`
- `def default_ledger_path`
- `def append`
- `def iter_trials`
- `def trial_count`
- `def total_trials`
- `class Kampagne`
- `def deflation_trials`
- `class LedgerIntegrity`
- `def check_integrity`

## `mt5_trading_ai/risk/leverage.py`

Zeilen: 253

Gesetzlicher Hebeldeckel je Anlageklasse — geladen aus einer versionierten Datei.

- `class LeveragePolicyError`
- `class AssetClassCap`
- `class LeveragePolicy`
- `class LeverageDecision`
- `def default_policy_path`
- `def load_policy`
- `def get_policy`
- `def clamp_leverage`

## `mt5_trading_ai/risk/limits.py`

Zeilen: 173

Verlustgrenzen und das **Kriterium** des Kill-Switch (Phase 6.4).

- `class TradingState`
- `class LossLimits`
- `class AccountSnapshot`
- `class LimitDecision`
- `def evaluate_limits`

## `mt5_trading_ai/risk/sizing.py`

Zeilen: 224

Risiko je Trade, ausfuehrbarer Stop-Floor und Positionsgroesse (Phase 6.2/6.3).

- `class RiskSizingError`
- `class StopFloorInputs`
- `class StopFloor`
- `class SizingResult`
- `def normalise_risk_fraction`
- `def executable_stop_floor`
- `def size_position`

## `mt5_trading_ai/risk/stop_budget.py`

Zeilen: 325

Stop-Budget je Anlageklasse — hergeleitet, nicht uebertragen (Phase 6.5).

- `class StopBudget`
- `def assumed_cost_bps`
- `def cost_bps_from_fraction`
- `def cost_floor_bps`
- `def margin_ceiling_bps`
- `def stop_budget`
- `def breakeven_hit_rate`

## `mt5_trading_ai/venue/catalog.py`

Zeilen: 260

Instrumentenkatalog — die Metadaten, die MT5 nicht liefert.

- `class InstrumentCatalogError`
- `class CatalogEntry`
- `def default_catalog_path`
- `def load_instrument_catalog`
- `def session_minutes`

## `mt5_trading_ai/venue/demo_run.py`

Zeilen: 372

Paket 5: Registrierung und Fortschritts-Tor des Demo-Betriebs (§8.5).

- `class DemoGateError`
- `class DemoAccount`
- `class DemoRegistration`
- `def register_for_demo`
- `class DemoReadiness`
- `def pruefe_demo_beleg`
- `def evaluate_demo_progress`

## `mt5_trading_ai/venue/halal.py`

Zeilen: 64

Der Halal-Screen: das mechanisch Pruefbare erzwingen, die fiqh-Grenze benennen (S4).

- `class HalalVerdict`
- `def screen_halal`

## `mt5_trading_ai/venue/mt5.py`

Zeilen: 2561

MT5-Anbindung an das ``TradingVenue``-Protokoll.

- `class NotAusUnvollstaendig`
- `class Mt5Symbol`
- `class Mt5Tick`
- `class Mt5Rate`
- `class Mt5Position`
- `class Mt5Account`
- `class Mt5SendResult`
- `class Mt5Terminal`
- `def stop_level_in_tickschritten`
- `class Mt5Venue`
- `def kennmarke`
- `class RealMt5Terminal`

## `mt5_trading_ai/venue/protocol.py`

Zeilen: 531

Plattformunabhaengiger Handelsplatz-Vertrag.

- `class AssetClass`
- `class OrderSide`
- `class OrderType`
- `class Timeframe`
- `class VenueError`
- `class VenueUnavailableError`
- `class UnknownInstrumentError`
- `class UnknownTimeframeError`
- `class OrderRejectedError`
- `class TradingSession`
- `class FeeSchedule`
- `class Instrument`
- `class Quote`
- `class Bar`
- `def ist_abgeschlossen`
- `class OrderRequest`
- `class OrderResult`
- `class Position`
- `class AccountState`
- `class TradingVenue`

## `mt5_trading_ai/venue/smoke.py`

Zeilen: 339

Demo-Smoke-Test der MT5-Bindung — die Orchestrierung, terminalunabhaengig.

- `class DemoRunInputs`
- `class SmokeStep`
- `class SmokeReport`
- `def run_smoke`
