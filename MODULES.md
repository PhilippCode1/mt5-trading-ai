<!-- GENERIERT von tools/gen_docs.py — nicht von Hand bearbeiten -->

# MODULES — oeffentliche API je Modul (generiert aus dem Code)

## `mt5_trading_ai/backtest/edge.py`

Das Sechs-Bedingungen-Tor des Edge-Tests (Paket 4, §7.2).

- `class EdgeThresholds`
- `class EdgeCheck`
- `class EdgeVerdict`
- `def max_consecutive_positive`
- `def evaluate_edge`

## `mt5_trading_ai/backtest/engine.py`

Backtest-Maschine: fuehrt Splits, Daten und Kostenmodell zusammen.

- `class Signal`
- `class LookAheadError`
- `class MarketView`
- `def random_signal_strategy`
- `class MarketSpec`
- `class TradeRecord`
- `class BacktestReport`
- `def run_backtest`
- `class WalkForwardResult`
- `def run_walk_forward`
- `def deflated_sharpe_for_report`
- `def run_registered_backtest`

## `mt5_trading_ai/backtest/llm_compare.py`

Paket 5: das Tor fuer ein LLM im Entscheidungspfad (§8.2-8.4).

- `class LlmGateInputs`
- `class LlmGateDecision`
- `def evaluate_llm_gate`

## `mt5_trading_ai/backtest/splits.py`

Zeitreihen-Splits mit Purge und Embargo — herausgeloest aus learning_engine.

- `class Range`
- `def purged_walk_forward_indices`
- `def purged_kfold_embargo_indices`
- `def walk_forward_indices`

## `mt5_trading_ai/backtest/strategies.py`

Einfache, ernsthafte Signallogiken fuer den Edge-Test -- ohne Optimierung.

- `def moving_average_crossover`
- `def mean_reversion_zscore`
- `def volatility_breakout`

## `mt5_trading_ai/costs/model.py`

Kostenmodell: die realen Kosten einer Order, gemessen statt angenommen.

- `class CostModelError`
- `class CostBreakdown`
- `def order_roundturn_cost`
- `def load_cost_fees`
- `def hurdle_rate`

## `mt5_trading_ai/data/loader.py`

Lader fuer historische Bars -- an das Datenqualitaetstor gekettet.

- `def dukascopy_price_divisor`
- `class DataLoadError`
- `class WeekdaySession`
- `def decode_dukascopy_candles`
- `def parse_yahoo_daily`
- `def filter_to_weekdays`
- `def assess_or_raise`
- `def to_csv`
- `def from_csv`
- `def bars_checksum`
- `def dataset_manifest`
- `def manifest_checksum`

## `mt5_trading_ai/data/quality.py`

Datenqualitaet als Gate (Phase 7.2).

- `class BarRow`
- `class QualityReport`
- `def expected_bar_count`
- `class SessionPredicate`
- `def assess_bars`
- `def render_markdown`

## `mt5_trading_ai/execution/leverage_preflight.py`

Anschluss der Hebelklammer an den Order-Pfad.

- `class LeveragePreflight`
- `def evaluate_leverage_preflight`

## `mt5_trading_ai/execution/private_sync.py`

Private Ereignis-Synchronisation: der Kontostrom haelt das Buch aktuell.

- `class PrivateEventKind`
- `class PrivateEvent`
- `class PrivateSync`

## `mt5_trading_ai/execution/reconcile.py`

Order-Lebenszyklus und Reconcile: Konto gegen Buch.

- `class PositionBook`
- `def positions_to_net`
- `class SymbolDrift`
- `class ReconcileResult`
- `def reconcile_positions`

## `mt5_trading_ai/execution/release.py`

Mehrteilige Freigabe fuer Order-Submit an einen echten Markt.

- `class LiveReleaseDecision`
- `def evaluate_live_release`
- `def live_release_blocks_opening_order`

## `mt5_trading_ai/gates/criteria.py`

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

Trials-Ledger (Phase 9.4) — ``TRIALS.jsonl``, ausschliesslich anhaengend.

- `class TrialsLedgerError`
- `class Trial`
- `def new_trial`
- `def default_ledger_path`
- `def append`
- `def iter_trials`
- `def trial_count`
- `def total_trials`
- `class LedgerIntegrity`
- `def check_integrity`

## `mt5_trading_ai/risk/leverage.py`

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

Verlustgrenzen und Kill-Switch (Phase 6.4).

- `class TradingState`
- `class LossLimits`
- `class AccountSnapshot`
- `class LimitDecision`
- `def evaluate_limits`

## `mt5_trading_ai/risk/sizing.py`

Risiko je Trade, ausfuehrbarer Stop-Floor und Positionsgroesse (Phase 6.2/6.3).

- `class RiskSizingError`
- `class StopFloorInputs`
- `class StopFloor`
- `class SizingResult`
- `def normalise_risk_fraction`
- `def executable_stop_floor`
- `def size_position`

## `mt5_trading_ai/risk/stop_budget.py`

Stop-Budget je Anlageklasse — hergeleitet, nicht uebertragen (Phase 6.5).

- `class StopBudget`
- `def cost_floor_bps`
- `def margin_ceiling_bps`
- `def stop_budget`
- `def breakeven_hit_rate`

## `mt5_trading_ai/venue/catalog.py`

Instrumentenkatalog — die Metadaten, die MT5 nicht liefert.

- `class InstrumentCatalogError`
- `class CatalogEntry`
- `def default_catalog_path`
- `def load_instrument_catalog`

## `mt5_trading_ai/venue/demo_run.py`

Paket 5: Registrierung und Fortschritts-Tor des Demo-Betriebs (§8.5).

- `class DemoGateError`
- `class DemoRegistration`
- `def register_for_demo`
- `class DemoReadiness`
- `def evaluate_demo_progress`

## `mt5_trading_ai/venue/mt5.py`

MT5-Anbindung an das ``TradingVenue``-Protokoll.

- `class Mt5Symbol`
- `class Mt5Tick`
- `class Mt5Rate`
- `class Mt5Position`
- `class Mt5Account`
- `class Mt5SendResult`
- `class Mt5Terminal`
- `class Mt5Venue`
- `class RealMt5Terminal`

## `mt5_trading_ai/venue/protocol.py`

Plattformunabhaengiger Handelsplatz-Vertrag.

- `class AssetClass`
- `class OrderSide`
- `class OrderType`
- `class Timeframe`
- `class VenueError`
- `class VenueUnavailableError`
- `class UnknownInstrumentError`
- `class OrderRejectedError`
- `class TradingSession`
- `class FeeSchedule`
- `class Instrument`
- `class Quote`
- `class Bar`
- `class OrderRequest`
- `class OrderResult`
- `class Position`
- `class AccountState`
- `class TradingVenue`

## `mt5_trading_ai/venue/smoke.py`

Demo-Smoke-Test der MT5-Bindung — die Orchestrierung, terminalunabhaengig.

- `class SmokeStep`
- `class SmokeReport`
- `def run_smoke`
