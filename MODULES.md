<!-- GENERIERT von tools/gen_docs.py — nicht von Hand bearbeiten -->

# MODULES — oeffentliche API je Modul (generiert aus dem Code)

## `mastertrade/backtest/splits.py`

Zeitreihen-Splits mit Purge und Embargo — herausgeloest aus learning_engine.

- `class Range`
- `def purged_walk_forward_indices`
- `def purged_kfold_embargo_indices`
- `def walk_forward_indices`

## `mastertrade/data/quality.py`

Datenqualitaet als Gate (Phase 7.2).

- `class BarRow`
- `class QualityReport`
- `def expected_bar_count`
- `class SessionPredicate`
- `def assess_bars`
- `def render_markdown`

## `mastertrade/execution/release.py`

Mehrteilige Freigabe fuer Order-Submit an einen echten Markt.

- `class LiveReleaseDecision`
- `def evaluate_live_release`
- `def live_release_blocks_opening_order`

## `mastertrade/gates/criteria.py`

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

## `mastertrade/gates/evaluation.py`

Bewerten ist nicht handeln (Phase 8.3).

- `class ThrottlePolicy`
- `class Candidate`
- `class OpenPosition`
- `class GateState`
- `class GateDecision`
- `class GateResult`
- `def select_one`
- `def trade_rate`

## `mastertrade/gates/learning_phase.py`

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

## `mastertrade/gates/trials.py`

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

## `mastertrade/risk/leverage.py`

Gesetzlicher Hebeldeckel je Anlageklasse — geladen aus einer versionierten Datei.

- `class LeveragePolicyError`
- `class AssetClassCap`
- `class LeveragePolicy`
- `class LeverageDecision`
- `def default_policy_path`
- `def load_policy`
- `def get_policy`
- `def clamp_leverage`

## `mastertrade/risk/limits.py`

Verlustgrenzen und Kill-Switch (Phase 6.4).

- `class TradingState`
- `class LossLimits`
- `class AccountSnapshot`
- `class LimitDecision`
- `def evaluate_limits`

## `mastertrade/risk/sizing.py`

Risiko je Trade, ausfuehrbarer Stop-Floor und Positionsgroesse (Phase 6.2/6.3).

- `class RiskSizingError`
- `class StopFloorInputs`
- `class StopFloor`
- `class SizingResult`
- `def normalise_risk_fraction`
- `def executable_stop_floor`
- `def size_position`

## `mastertrade/risk/stop_budget.py`

Stop-Budget je Anlageklasse — hergeleitet, nicht uebertragen (Phase 6.5).

- `class StopBudget`
- `def cost_floor_bps`
- `def margin_ceiling_bps`
- `def stop_budget`
- `def breakeven_hit_rate`

## `mastertrade/venue/protocol.py`

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
