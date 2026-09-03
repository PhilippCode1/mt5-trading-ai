"""Trials-Ledger: anhaengend, vollstaendig, ehrlich."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mt5_trading_ai.gates import trials as ledger

START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)


def _trial(outcome: str = "completed", minute: int = 0, **overrides: object):
    kwargs: dict[str, object] = {
        "strategy_id": "smc-v1",
        "version": "1.0.0",
        "instruments": ["EURUSD"],
        "period_start": START,
        "period_end": END,
        "leverage": 5,
        "parameters": {"threshold": 70},
        "outcome": outcome,
        "data_checksum": "abcdef0123456789",
        "code_commit": "deadbeefcafef00d",
        "ts": datetime(2026, 8, 6, 12, minute, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return ledger.new_trial(**kwargs)  # type: ignore[arg-type]


def test_empty_provenance_is_rejected(tmp_path: Path) -> None:
    # Paket 6: kein Versuch geht mit leerer Herkunft (Pruefsumme/Commit) ins Register.
    with pytest.raises(ledger.TrialsLedgerError):
        _trial(data_checksum="")
    with pytest.raises(ledger.TrialsLedgerError):
        _trial(code_commit="   ")


def test_every_run_counts_including_failures(tmp_path: Path) -> None:
    """Ein Zaehler, der nur Erfolge zaehlt, macht die Deflated Sharpe wertlos."""
    path = tmp_path / "TRIALS.jsonl"
    for index, outcome in enumerate(["completed", "aborted", "error", "completed"]):
        ledger.append(_trial(outcome, minute=index), path)
    assert ledger.total_trials(path) == 4
    assert ledger.trial_count("smc-v1", path=path) == 4


def test_count_filters_by_version_when_asked(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    ledger.append(_trial(minute=0), path)
    ledger.append(_trial(minute=1, version="1.1.0"), path)
    assert ledger.trial_count("smc-v1", path=path) == 2
    assert ledger.trial_count("smc-v1", version="1.1.0", path=path) == 1
    assert ledger.trial_count("andere", path=path) == 0


def test_append_never_rewrites(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    ledger.append(_trial(minute=0), path)
    first = path.read_text(encoding="utf-8")
    ledger.append(_trial(minute=1), path)
    second = path.read_text(encoding="utf-8")
    assert second.startswith(first), "der bestehende Inhalt wurde veraendert"
    assert len(second.splitlines()) == 2


def test_module_offers_no_way_to_delete_or_edit() -> None:
    forbidden = {"delete", "remove", "update", "rewrite", "truncate", "clear", "prune"}
    exported = {name.lower() for name in dir(ledger) if not name.startswith("_")}
    assert not (exported & forbidden), (
        f"verbotene Operation im Modul: {exported & forbidden}"
    )


def test_missing_ledger_is_zero_not_an_error(tmp_path: Path) -> None:
    path = tmp_path / "nicht_da.jsonl"
    assert ledger.total_trials(path) == 0
    assert ledger.check_integrity(path).ok is True


def test_lines_are_stable_json(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    ledger.append(_trial(minute=0), path)
    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    for key in (
        "ts",
        "strategy_id",
        "version",
        "instruments",
        "period_start",
        "period_end",
        "leverage",
        "parameters",
        "outcome",
    ):
        assert key in payload


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    original = _trial(minute=0, sharpe=1.42, net_expectancy=0.07, trades=612)
    ledger.append(original, path)
    read_back = list(ledger.iter_trials(path))
    assert len(read_back) == 1
    assert read_back[0] == original


def test_integrity_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    ledger.append(_trial(minute=5), path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"outcome": "schoengerechnet", "ts": "2000-01-01"}\n')
    report = ledger.check_integrity(path)
    assert report.ok is False
    assert any("outcome" in problem for problem in report.problems)
    assert any("rueckwaerts" in problem for problem in report.problems)


def test_broken_json_raises_instead_of_being_skipped(tmp_path: Path) -> None:
    path = tmp_path / "TRIALS.jsonl"
    ledger.append(_trial(minute=0), path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{kaputt\n")
    with pytest.raises(ledger.TrialsLedgerError):
        list(ledger.iter_trials(path))


@pytest.mark.parametrize(
    "overrides",
    [
        {"outcome": "erfolgreich"},
        {"instruments": []},
        {"strategy_id": "  "},
        {"version": ""},
    ],
)
def test_invalid_entries_are_rejected_at_construction(overrides: dict) -> None:
    with pytest.raises(ledger.TrialsLedgerError):
        _trial(**overrides)
