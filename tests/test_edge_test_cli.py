"""Register-Disziplin von ``tools/edge_test.py`` (Paket 6, Item 3) -- Verhaltenstest.

Das Werkzeug faehrt zwei SORTEN Laeufe: die **echten** Hypothesen-Laeufe (Walk-Forward-
Fenster + der OoS-Abschluss) und die **Kontroll**-Laeufe (Zufalls-Referenz, Leckage-
Probe, Stress-Kosten). Nur die echten duerfen ins Versuchsregister -- sonst blaeht eine
Kontrolle die Multiple-Testing-Zahl auf und macht die Deflated Sharpe unehrlich.

Dieser Test faehrt ``main()`` auf einer committeten Mini-Fixture und prueft am Register:
die echten Laeufe stehen drin (5 Fenster + 1 OoS, alle unter der Strategie-ID), die
Kontrollen (``rnd``/``leak``/``stress``) stehen NICHT drin. Wuerde ein Kontroll-Lauf je
faelschlich ein ``ledger_path`` bekommen, taucht seine ID hier auf -- und der Test wird
rot. Genau das ist die Absicht.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from mt5_trading_ai.gates import trials as trials_ledger

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
FIXTURE = Path(__file__).parent / "fixtures" / "smoke_eurusd_h1.csv"
PINNED_CHECKSUM = "944fd2409a403e517f92548151cc42cd2c64ee322ab4618cfc6b0a5855321be2"
COMMIT = "edgecli0commit0fixed"
STRATEGY_ID = "mean_reversion_eurusd_h1"
CONTROL_IDS = {"rnd", "leak", "stress"}


def _load_edge_test() -> object:
    spec = importlib.util.spec_from_file_location(
        "edge_test_cli", _TOOLS / "edge_test.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(ledger: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    module = _load_edge_test()
    argv = [
        "edge_test.py",
        "--csv",
        str(FIXTURE),
        "--ledger",
        str(ledger),
        "--strategy",
        "mean_reversion",
        "--data-checksum",
        PINNED_CHECKSUM,  # zugleich Drift-Wache der Fixture
        "--code-commit",
        COMMIT,  # hermetisch, ohne git im Test
    ]
    monkeypatch.setattr(sys, "argv", argv)
    return int(module.main())  # type: ignore[attr-defined]


def test_only_real_runs_reach_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "TRIALS.jsonl"
    assert _run_main(ledger, monkeypatch) == 0

    entries = list(trials_ledger.iter_trials(ledger))
    ids = {e.strategy_id for e in entries}

    # Die echten Laeufe: 5 Walk-Forward-Fenster + 1 OoS-Abschluss, alle unter EINER ID.
    assert ids == {STRATEGY_ID}, f"fremde IDs im Register: {ids - {STRATEGY_ID}}"
    assert len(entries) == 6

    # Die Kontrollen bleiben DRAUSSEN -- wuerde eine hier auftauchen, ist die Deflation
    # kompromittiert. Diese Assertion wird rot, sobald ein Kontroll-Lauf ein ledger_path
    # bekaeme.
    assert ids.isdisjoint(CONTROL_IDS)


def test_ledger_entries_carry_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "TRIALS.jsonl"
    assert _run_main(ledger, monkeypatch) == 0
    for entry in trials_ledger.iter_trials(ledger):
        # Herkunft faellt durch die ganze Kette (Paket 6, Item 3): jeder Eintrag traegt
        # eine nicht-leere, abgeleitete Pruefsumme UND den weitergereichten Commit.
        assert entry.data_checksum.strip()
        assert entry.code_commit == COMMIT
