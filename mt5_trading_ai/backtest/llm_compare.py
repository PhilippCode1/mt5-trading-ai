"""Paket 5: das Tor fuer ein LLM im Entscheidungspfad (§8.2-8.4).

Ein LLM kommt **nur** in den Entscheidungspfad, wenn belegt ist, dass die Variante
MIT LLM die Variante OHNE LLM gegen dieselben sechs Bedingungen schlaegt -- und nur
auf Daten **nach** dem Trainingsstichtag (Leckage, §8.3), mit protokollierter
Modellversion (Drift, §8.4). Fehlt der Beleg, kommt kein Modell in den Pfad.

Dieses Modul trifft **keine** Handelsentscheidung und ruft **kein** LLM -- es ist
nur das Tor davor (Kernregel 17: kein Modell fuehrt ungeprueften Code aus; §12.3:
kein LLM im Entscheidungspfad ohne den belegten Vergleich).

**Status (Paket 5):** Der Entscheidungspfad ist heute **LLM-frei** (regelbasierte
Strategien) -- per Regressionstest verankert (``test_decision_path_is_llm_free`` scannt
JEDE Modul-Datei des Pakets auf statische LLM-Bibliotheks-Importe, nicht nur eine
Auswahl). ``evaluate_llm_gate`` ist damit die einzige Zulassungsstelle: kaeme je ein
Modell in den Pfad, muss es zuvor diesen fail-closed-Vergleich bestehen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

LLM_GATE_VERSION = "llm-gate-v1"


@dataclass(frozen=True)
class LlmGateInputs:
    """Die Belege, die ein LLM in den Entscheidungspfad lassen -- oder eben nicht."""

    baseline_passed: bool    # Nicht-LLM-Variante: alle sechs Bedingungen erfuellt?
    baseline_score: float    # OoS-Sharpe nach Kosten (ohne LLM)
    llm_passed: bool               # LLM-Variante: alle sechs Bedingungen erfuellt?
    llm_score: float               # OoS-Sharpe nach Kosten (mit LLM)
    model_version: str             # exakte Modellversion (Drift, §8.4)
    model_training_cutoff: date    # Wissensstichtag des Modells
    backtest_start: date           # muss strikt NACH dem Cutoff liegen (Leckage, §8.3)


@dataclass(frozen=True)
class LlmGateDecision:
    allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    version: str = LLM_GATE_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reasons": list(self.reasons),
                "version": self.version}


def evaluate_llm_gate(inputs: LlmGateInputs) -> LlmGateDecision:
    """Darf das LLM in den Entscheidungspfad? Nur wenn **alle** Belege stimmen.

    Fail-closed: jede fehlende Bedingung schliesst das Modell aus. Ein LLM, das die
    Nicht-LLM-Variante nicht schlaegt, oder auf Trainingsdaten getestet wurde, oder ohne
    Versionsstempel, kommt nicht in den Pfad.
    """
    reasons: list[str] = []
    if not inputs.llm_passed:
        reasons.append("llm_variant_failed_six_conditions")
    if not inputs.llm_score > inputs.baseline_score:
        # §8.2: die Variante MIT muss die Variante OHNE schlagen -- strikt.
        reasons.append("llm_does_not_beat_baseline")
    if inputs.backtest_start <= inputs.model_training_cutoff:
        # §8.3: Backtest ausschliesslich auf Daten NACH dem Trainingsstichtag.
        reasons.append("backtest_overlaps_training_data_leakage")
    if not inputs.model_version.strip():
        # §8.4: exakte Modellversion je Lauf, sonst ist die Versuchszaehlung blind.
        reasons.append("model_version_missing")
    return LlmGateDecision(allowed=not reasons, reasons=tuple(reasons))
