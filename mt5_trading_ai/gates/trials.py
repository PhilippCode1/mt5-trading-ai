"""Trials-Ledger (Phase 9.4) — ``TRIALS.jsonl``, ausschliesslich anhaengend.

Jeder Lauf zaehlt: abgeschlossene, fehlgeschlagene und abgebrochene. Der Zaehler
geht in die Deflated Sharpe Ratio ein. Wer hundert Varianten testet, findet
zufaellig eine mit Sharpe 1,5 — dieser Ledger macht das sichtbar.

Bei einer Strategien-Bibliothek ist das die wichtigste Datei im Projekt. Deshalb
kennt dieses Modul **keine** Funktion zum Loeschen oder Aendern eines Eintrags,
und ``append`` oeffnet die Datei ausschliesslich im Modus ``"a"``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRIALS_LEDGER_VERSION = "trials-ledger-v1"
DEFAULT_LEDGER_NAME = "TRIALS.jsonl"

_OUTCOMES = frozenset({"completed", "aborted", "error"})


class TrialsLedgerError(RuntimeError):
    """Der Ledger ist unbrauchbar. Fail-closed: keine Strategiefreigabe."""


@dataclass(frozen=True)
class Trial:
    """Ein Lauf. Alle Felder sind Pflicht ausser den Ergebniswerten."""

    ts: str
    strategy_id: str
    version: str
    instruments: tuple[str, ...]
    period_start: str
    period_end: str
    leverage: int
    parameters: dict[str, Any]
    outcome: str
    #: Herkunft (Paket 6): Datenpruefsumme + Codestand. Pflicht -- kein Versuch geht
    #: mit leerer Herkunft ins Register.
    data_checksum: str
    code_commit: str
    sharpe: float | None = None
    net_expectancy: float | None = None
    trades: int | None = None
    notes: str = ""
    ledger_version: str = TRIALS_LEDGER_VERSION

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise TrialsLedgerError(
                f"outcome muss eines von {sorted(_OUTCOMES)} sein, "
                f"nicht {self.outcome!r}"
            )
        if not self.strategy_id.strip() or not self.version.strip():
            raise TrialsLedgerError("strategy_id und version sind Pflicht")
        if not self.instruments:
            raise TrialsLedgerError("instruments darf nicht leer sein")
        # Fail-closed: ein Lauf ohne ableitbare Herkunft (Datenpruefsumme + Codestand)
        # kommt nicht ins Register -- sonst ist der Eintrag beweisfrei.
        if not self.data_checksum.strip():
            raise TrialsLedgerError("data_checksum ist Pflicht (leere Herkunft)")
        if not self.code_commit.strip():
            raise TrialsLedgerError("code_commit ist Pflicht (leere Herkunft)")

    def to_json_line(self) -> str:
        payload = asdict(self)
        payload["instruments"] = list(self.instruments)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def new_trial(
    *,
    strategy_id: str,
    version: str,
    instruments: Sequence[str],
    period_start: datetime,
    period_end: datetime,
    leverage: int,
    parameters: dict[str, Any],
    outcome: str,
    data_checksum: str,
    code_commit: str,
    sharpe: float | None = None,
    net_expectancy: float | None = None,
    trades: int | None = None,
    notes: str = "",
    ts: datetime | None = None,
) -> Trial:
    stamp = (ts or datetime.now(UTC)).astimezone(UTC)
    return Trial(
        ts=stamp.isoformat(),
        strategy_id=strategy_id,
        version=version,
        instruments=tuple(instruments),
        period_start=period_start.astimezone(UTC).isoformat(),
        period_end=period_end.astimezone(UTC).isoformat(),
        leverage=int(leverage),
        parameters=dict(parameters),
        outcome=outcome,
        data_checksum=data_checksum,
        code_commit=code_commit,
        sharpe=sharpe,
        net_expectancy=net_expectancy,
        trades=trades,
        notes=notes,
    )


def default_ledger_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / ".git").exists():
            return parent / DEFAULT_LEDGER_NAME
    return Path.cwd() / DEFAULT_LEDGER_NAME


def append(trial: Trial, path: Path | str | None = None) -> Path:
    """Haenge einen Lauf an. Der einzige schreibende Zugriff dieses Moduls."""
    ledger = Path(path) if path is not None else default_ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = trial.to_json_line()
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def iter_trials(path: Path | str | None = None) -> Iterator[Trial]:
    ledger = Path(path) if path is not None else default_ledger_path()
    if not ledger.is_file():
        return
    for number, raw in enumerate(
        ledger.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise TrialsLedgerError(
                f"{ledger}:{number} ist kein gueltiges JSON: {exc}"
            ) from exc
        payload["instruments"] = tuple(payload.get("instruments") or ())
        payload.pop("ledger_version", None)
        # Rueckwaertskompatibel: Eintraege vor Paket 6 tragen keine Herkunft; sie als
        # ``legacy`` lesen, ohne die Schreib-Pflicht (non-empty) aufzuweichen.
        payload.setdefault("data_checksum", "legacy")
        payload.setdefault("code_commit", "legacy")
        yield Trial(ledger_version=TRIALS_LEDGER_VERSION, **payload)


def trial_count(
    strategy_id: str,
    *,
    version: str | None = None,
    path: Path | str | None = None,
) -> int:
    """Ehrlicher Versuchszaehler. **Jeder** Lauf zaehlt, auch Fehlversuche.

    Genau deshalb filtert diese Funktion nicht nach ``outcome``: ein
    abgebrochener Lauf ist ein Versuch, und ein Zaehler, der nur die
    erfolgreichen zaehlt, macht die Deflated Sharpe Ratio wertlos.
    """
    count = 0
    for trial in iter_trials(path):
        if trial.strategy_id != strategy_id:
            continue
        if version is not None and trial.version != version:
            continue
        count += 1
    return count


def total_trials(path: Path | str | None = None) -> int:
    """Wie viele Zeilen stehen im Register. Fehlt die Datei, sind es null.

    Fuer die Deflation ist diese Funktion die falsche: null wird beim Aufrufer zur
    eins, und bei einem Versuch deflationiert nichts. Dafuer gibt es
    :func:`deflation_trials`.
    """
    return sum(1 for _ in iter_trials(path))


def deflation_trials(
    path: Path | str | None = None,
    *,
    include_running: bool = True,
) -> int:
    """Versuchszahl fuer die Deflation — aus dem Register, fail-closed.

    Warum das nicht ``total_trials`` sein darf: ein fehlendes Register liefert dort
    null, und der uebliche Aufruf ``max(1, ...)`` macht daraus eins. Bei einem
    Versuch ist ``expected_max_sharpe`` exakt null — die Mehrfachvergleichs-Korrektur
    ist dann vollstaendig aufgehoben, und zwar lautlos. Gemessen an einem echten Fall
    dieses Repos (Sharpe 0,2759 auf 64 Out-of-Sample-Ereignissen): mit dem
    Registerstand acht ergibt sich eine DSR von 0,755, ueber die stille Eins dagegen
    0,984 — dieselbe Messung faellt einmal durch und besteht einmal die Schwelle
    0,95. Ein fehlendes Register ist deshalb hier ein Fehler und kein Vorgabewert.

    ``include_running`` zaehlt den gerade laufenden Versuch mit. Das Register ist
    anhaengend und wird erst **nach** der Messung geschrieben; ohne diesen Zuschlag
    saehe ein Lauf sich selbst nicht, und untertreiben heisst hier schmeicheln.

    Ein leeres Register ist kein Fehler: dann ist dies der erste Versuch, die DSR ist
    die Probabilistic Sharpe Ratio, und es gibt nichts zu deflationieren. Dass daraus
    niemand durch Loeschen des Registers wieder eins macht, sichert die Anhaenge-Regel
    dieses Moduls samt :func:`check_integrity` — nicht diese Funktion.
    """
    ledger = Path(path) if path is not None else default_ledger_path()
    if not ledger.is_file():
        raise TrialsLedgerError(
            f"Register {ledger} fehlt. Ohne Register ist die Versuchszahl unbekannt, "
            "und unbekannt ist nicht eins: bei einem Versuch deflationiert nichts. "
            "Fail-closed — kein Vorgabewert."
        )
    return total_trials(ledger) + (1 if include_running else 0)


@dataclass(frozen=True)
class LedgerIntegrity:
    ok: bool
    lines: int
    problems: tuple[str, ...] = field(default_factory=tuple)


def check_integrity(path: Path | str | None = None) -> LedgerIntegrity:
    """Der Ledger darf nur wachsen. Diese Pruefung meldet, was ihn unbrauchbar macht."""
    ledger = Path(path) if path is not None else default_ledger_path()
    problems: list[str] = []
    lines = 0
    if not ledger.is_file():
        return LedgerIntegrity(ok=True, lines=0)
    previous_ts: str | None = None
    for number, raw in enumerate(
        ledger.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw.strip()
        if not stripped:
            continue
        lines += 1
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            problems.append(f"Zeile {number}: kein gueltiges JSON ({exc})")
            continue
        outcome = payload.get("outcome")
        if outcome not in _OUTCOMES:
            problems.append(f"Zeile {number}: unbekanntes outcome {outcome!r}")
        ts = payload.get("ts")
        if previous_ts is not None and isinstance(ts, str) and ts < previous_ts:
            problems.append(f"Zeile {number}: Zeitstempel laeuft rueckwaerts")
        if isinstance(ts, str):
            previous_ts = ts
    return LedgerIntegrity(ok=not problems, lines=lines, problems=tuple(problems))
