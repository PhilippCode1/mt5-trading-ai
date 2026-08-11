"""Vorregistrierte Kriterien: alle, kein 'fast'."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from mt5_trading_ai.gates.criteria import (
    BacktestEvidence,
    Preregistration,
    annualise_sharpe,
    deflated_sharpe_ratio,
    evaluate_criteria,
    expected_max_sharpe,
    percentile_against_random,
)

PASSING = BacktestEvidence(
    net_expectancy=0.12,
    annualised_sharpe=1.4,
    deflated_sharpe=0.97,
    positive_folds=5,
    positive_instruments=4,
    random_percentile=0.99,
    max_drawdown=0.18,
    trades=800,
    net_expectancy_at_stressed_cost=0.03,
    trial_count=40,
)

CRITERION_FIELDS = {
    "net_expectancy": 0.0,
    "annualised_sharpe": 0.9,
    "deflated_sharpe": 0.94,
    "positive_folds": 3,
    "positive_instruments": 2,
    "random_percentile": 0.94,
    "max_drawdown": 0.26,
    "trades": 499,
    "net_expectancy_at_stressed_cost": -0.01,
}


def test_complete_evidence_passes() -> None:
    verdict = evaluate_criteria(PASSING, Preregistration())
    assert verdict.passed is True
    assert verdict.unmet == ()


@pytest.mark.parametrize("field,failing_value", sorted(CRITERION_FIELDS.items()))
def test_a_single_missed_criterion_is_a_no(field: str, failing_value: object) -> None:
    """Kein 'fast'. Ein Kriterium genuegt zum Nein."""
    evidence = replace(PASSING, **{field: failing_value})
    verdict = evaluate_criteria(evidence, Preregistration())
    assert verdict.passed is False
    assert len(verdict.unmet) >= 1


def test_empty_evidence_fails_everything_and_is_not_skipped() -> None:
    """Nicht bewertbar gilt als nicht erfuellt."""
    verdict = evaluate_criteria(BacktestEvidence(), Preregistration())
    assert verdict.passed is False
    assert len(verdict.unmet) == len(verdict.results)
    assert all(r.reason == "not_evaluable" for r in verdict.results)


def test_missing_trial_count_blocks() -> None:
    """Ohne ehrlichen Versuchszaehler kein Ja."""
    verdict = evaluate_criteria(replace(PASSING, trial_count=None), Preregistration())
    assert verdict.passed is False
    assert "trial_count_honest" in verdict.unmet


def test_there_is_no_aggregate_score_to_optimise_against() -> None:
    payload = evaluate_criteria(PASSING, Preregistration()).as_dict()
    assert set(payload) == {"passed", "version", "unmet", "results"}
    assert isinstance(payload["passed"], bool)


# --- Deflated Sharpe -------------------------------------------------------


def test_more_trials_lower_the_deflated_sharpe() -> None:
    """Wer hundert Varianten testet, findet zufaellig eine gute. Das muss sichtbar sein."""
    values = [
        deflated_sharpe_ratio(observed_sharpe=0.10, observations=500, trials=n)
        for n in (1, 10, 100, 1000, 10000)
    ]
    assert values == sorted(values, reverse=True)
    assert values[0] > 0.9
    assert values[-1] < 0.2


def test_expected_max_sharpe_grows_with_trials() -> None:
    previous = expected_max_sharpe(2, 0.01)
    for trials in (10, 100, 1000):
        current = expected_max_sharpe(trials, 0.01)
        assert current > previous
        previous = current
    assert expected_max_sharpe(1, 0.01) == 0.0


def test_deflated_sharpe_is_a_probability() -> None:
    for sharpe in (-0.5, 0.0, 0.05, 0.3):
        value = deflated_sharpe_ratio(
            observed_sharpe=sharpe, observations=250, trials=25
        )
        assert 0.0 <= value <= 1.0


def test_annualise_sharpe() -> None:
    assert annualise_sharpe(0.1, 252) == pytest.approx(0.1 * math.sqrt(252))
    with pytest.raises(ValueError):
        annualise_sharpe(0.1, 0)


def test_percentile_against_random() -> None:
    randoms = [float(i) / 100.0 for i in range(100)]
    assert percentile_against_random(0.5, randoms) == pytest.approx(0.5)
    assert percentile_against_random(1.0, randoms) == 1.0
    assert percentile_against_random(-1.0, randoms) == 0.0
    with pytest.raises(ValueError):
        percentile_against_random(0.5, [])


def test_bad_inputs_raise_instead_of_guessing() -> None:
    with pytest.raises(ValueError):
        deflated_sharpe_ratio(observed_sharpe=0.1, observations=1, trials=10)
    with pytest.raises(ValueError):
        deflated_sharpe_ratio(observed_sharpe=0.1, observations=100, trials=0)
