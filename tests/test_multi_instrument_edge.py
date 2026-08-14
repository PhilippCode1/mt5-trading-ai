"""``tools/multi_instrument_edge.py`` (Paket 5/6) -- Einheits- und Verhaltenstest.

Prueft die beiden Naehte des Harness auf einer committeten Mini-Fixture: ``_run_one``
faehrt ein Instrument durch die ganze Kette und faellt ein **echtes** Urteil; ``main``
faehrt den Rahmen darum. Zugleich gilt dieselbe Register-Disziplin wie im Edge-Test: nur
die echten Laeufe (5 Fenster + OoS) zaehlen, die Kontrollen (``rnd``/``leak``) bleiben
draussen. Auf synthetischem Rauschen ist das ehrliche Urteil "kein Edge".
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.gates import trials as trials_ledger

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
FIXTURE = Path(__file__).parent / "fixtures" / "smoke_eurusd_h1.csv"
PINNED_CHECKSUM = "944fd2409a403e517f92548151cc42cd2c64ee322ab4618cfc6b0a5855321be2"
COMMIT = "multiedge0commit0fix"
STRATEGY_ID = "mean_reversion_eurusd_h1"
CONTROL_IDS = {"rnd", "leak", "stress"}


def _load() -> object:
    spec = importlib.util.spec_from_file_location(
        "multi_instrument_edge_cli", _TOOLS / "multi_instrument_edge.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_one_delivers_real_verdict_and_registers(tmp_path: Path) -> None:
    module = _load()
    ledger = str(tmp_path / "TRIALS.jsonl")
    verdict, trades, net, dsr = module._run_one(  # type: ignore[attr-defined]
        "EURUSD", FIXTURE, ledger, PINNED_CHECKSUM, COMMIT, 6  # ein Instrument -> 6
    )
    # Ein ECHTES Urteil aus der Kette (run_walk_forward -> run_registered_backtest ->
    # deflated_sharpe -> evaluate_edge), kein handgesetztes Flag.
    assert isinstance(verdict, EdgeVerdict)
    assert len(verdict.checks) == 6
    assert verdict.passed is False          # synthetisches Rauschen -> kein Edge
    assert trades >= 2                      # die Kette hat wirklich gehandelt
    assert 0.0 <= dsr <= 1.0
    assert isinstance(net, float)

    entries = list(trials_ledger.iter_trials(ledger))
    ids = {e.strategy_id for e in entries}
    assert ids == {STRATEGY_ID}             # 5 Fenster + OoS, eine ID
    assert len(entries) == 6
    assert ids.isdisjoint(CONTROL_IDS)      # Kontrollen NICHT im Register
    for e in entries:
        assert e.data_checksum.strip() and e.code_commit == COMMIT


def test_main_runs_single_instrument_and_keeps_discipline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    ledger = tmp_path / "TRIALS.jsonl"
    argv = [
        "multi_instrument_edge.py",
        "--instrument", "EURUSD", str(FIXTURE),
        "--ledger", str(ledger),
        "--data-checksum", PINNED_CHECKSUM,
        "--code-commit", COMMIT,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert int(module.main()) == 0  # type: ignore[attr-defined]

    ids = {e.strategy_id for e in trials_ledger.iter_trials(ledger)}
    assert ids == {STRATEGY_ID}
    assert ids.isdisjoint(CONTROL_IDS)


def test_run_one_uses_expected_trials_for_deflation(tmp_path: Path) -> None:
    # Die Deflation nutzt die deklarierte Kampagnenzahl: gleiche Fixture, getrennte
    # Ledger, groessere expected_trials -> strengere (kleiner-gleich) DSR. Beweist, dass
    # _run_one expected_trials wirklich durchreicht (nicht order-gameable).
    module = _load()
    _v1, _t1, _n1, dsr_small = module._run_one(  # type: ignore[attr-defined]
        "EURUSD", FIXTURE, str(tmp_path / "a.jsonl"), PINNED_CHECKSUM, COMMIT, 6)
    _v2, _t2, _n2, dsr_big = module._run_one(  # type: ignore[attr-defined]
        "EURUSD", FIXTURE, str(tmp_path / "b.jsonl"), PINNED_CHECKSUM, COMMIT, 600)
    # STRIKT: ohne die Durchreichung waeren beide gleich (actual=6 in beiden) -> der
    # Test faellt bei deaktiviertem Fix rot, statt falsch-gruen durchzugehen.
    assert dsr_big < dsr_small
