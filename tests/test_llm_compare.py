"""Test des LLM-Entscheidungspfad-Tors (Paket 5, §8.2-8.4). Fail-closed, negativ gefahren."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from mt5_trading_ai.backtest.llm_compare import LlmGateInputs, evaluate_llm_gate

#: Bekannte LLM-Bibliotheken/-Anbieter -- keine davon darf das Paket statisch importieren.
_LLM_LIBS = (
    "openai", "anthropic", "langchain", "transformers", "llama_cpp", "cohere",
    "litellm", "ollama", "google.generativeai", "mistralai", "groq", "vertexai",
    "huggingface", "sentence_transformers", "torch", "tensorflow",
)


def _ok() -> LlmGateInputs:
    return LlmGateInputs(
        baseline_passed=True, baseline_score=1.1,
        llm_passed=True, llm_score=1.4,
        model_version="claude-x-2026-01",
        model_training_cutoff=date(2024, 1, 1),
        backtest_start=date(2025, 1, 1),
    )


def test_llm_gate_all_ok_allows() -> None:
    decision = evaluate_llm_gate(_ok())
    assert decision.allowed
    assert decision.reasons == ()


def test_llm_gate_blocks_when_llm_fails_conditions() -> None:
    decision = evaluate_llm_gate(replace(_ok(), llm_passed=False))
    assert not decision.allowed
    assert "llm_variant_failed_six_conditions" in decision.reasons


def test_llm_gate_blocks_when_llm_does_not_beat_baseline() -> None:
    # Gleichstand reicht nicht -- §8.2 verlangt schlagen, strikt.
    decision = evaluate_llm_gate(replace(_ok(), llm_score=1.1, baseline_score=1.1))
    assert not decision.allowed
    assert "llm_does_not_beat_baseline" in decision.reasons


def test_llm_gate_blocks_on_training_data_leakage() -> None:
    # Backtest beginnt vor dem Trainingsstichtag -> Leckage.
    decision = evaluate_llm_gate(
        replace(_ok(), backtest_start=date(2023, 6, 1),
                model_training_cutoff=date(2024, 1, 1))
    )
    assert not decision.allowed
    assert "backtest_overlaps_training_data_leakage" in decision.reasons


def test_llm_gate_blocks_without_model_version() -> None:
    decision = evaluate_llm_gate(replace(_ok(), model_version="  "))
    assert not decision.allowed
    assert "model_version_missing" in decision.reasons


def test_decision_path_is_llm_free() -> None:
    # Verankerung (Paket 5, §12.3): das GANZE Paket ist LLM-frei, und ``evaluate_llm_gate``
    # ist die EINZIGE Zulassungsstelle. Der Scan liest JEDE Modul-Datei (nicht nur eine
    # Auswahl -- so faellt auch ein indirekter Pfad ueber ein Hilfsmodul) und prueft die
    # STATISCHEN ``import``/``from``-Zeilen. Zieht je ein Modul eine LLM-Bibliothek, faellt
    # dieser Test -- der Weg ins Modell geht dann nur ueber das (fail-closed) Tor.
    # (Bewusst statisch: ein dynamischer ``importlib``-Import eines LLM waere ein
    # gesonderter, absichtlicher Akt und ist nicht Ziel dieses Regressions-Ankers.)
    pkg = Path(__file__).resolve().parents[1] / "mt5_trading_ai"
    offenders: list[str] = []
    for path in sorted(pkg.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            low = stripped.lower()
            if any(lib in low for lib in _LLM_LIBS):
                offenders.append(f"{path.relative_to(pkg)}: {stripped}")
    assert offenders == [], f"LLM-Abhaengigkeit im Paket: {offenders}"
