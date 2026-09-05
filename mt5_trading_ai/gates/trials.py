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
    """Das Register ohne Pfadangabe: ``TRIALS.jsonl`` im Anwendungsordner des Benutzers.

    Bis Auftrag 1 lag es in der Wurzel des Repos (gitignoriert). Das verletzte A18
    (keine Laufzeitdaten im Arbeitsbaum): die Datei waechst mit jedem Lauf, und ein
    Beleg, der nur auf einer Platte im Arbeitsbaum liegt, ist keiner (Gegenlese T10,
    E14; E-021). Jetzt liegt es neben dem Zustandsordner -- unter Windows
    ``%LOCALAPPDATA%/mt5_trading_ai/TRIALS.jsonl`` -- ausserhalb jedes Klons, und ein
    Klon findet es nicht "zufaellig" ueber ``Path.cwd()``. Wer es woanders fuehrt,
    gibt den Pfad an (``--register``, ``--ledger``).
    """
    from mt5_trading_ai.execution.risiko_zustand import standard_zustandsordner

    return standard_zustandsordner().parent / DEFAULT_LEDGER_NAME


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


@dataclass(frozen=True)
class Kampagne:
    """Eine VORREGISTRIERTE Studienreihe: Kennungspraefix und Zahl ihrer Laeufe.

    ``praefix`` trennt die Laeufe dieser Reihe von allem anderen im Register -- eine
    ``strategy_id`` gehoert zur Reihe, wenn sie damit beginnt. ``groesse`` ist die Zahl
    der Laeufe, die die Reihe **vor ihrem Beginn** angemeldet hat; sie steht im Code
    der Reihe und ist damit versioniert, nicht aus dem Register geraten.
    """

    praefix: str
    groesse: int

    def __post_init__(self) -> None:
        if not self.praefix.strip():
            raise TrialsLedgerError(
                "Kampagne ohne Praefix -- dann liesse sich die eigene Reihe nicht von "
                "fremden Laeufen trennen"
            )
        if self.groesse < 1:
            raise TrialsLedgerError(
                f"Kampagnengroesse muss >= 1 sein, nicht {self.groesse}"
            )


def deflation_trials(kampagne: Kampagne, path: Path | str | None = None) -> int:
    """Versuchszahl fuer die Deflation -- aufrufzeit-UNABHAENGIG und fail-closed.

    Warum das nicht ``total_trials`` sein darf: ein fehlendes Register liefert dort
    null, und der uebliche Aufruf ``max(1, ...)`` macht daraus eins. Bei einem
    Versuch ist ``expected_max_sharpe`` exakt null -- die Mehrfachvergleichs-Korrektur
    ist dann vollstaendig aufgehoben, und zwar lautlos. Gemessen an einem echten Fall
    dieses Repos (Sharpe 0,2759 auf 64 Out-of-Sample-Ereignissen): mit dem
    Registerstand acht ergibt sich eine DSR von 0,755, ueber die stille Eins dagegen
    0,984 -- dieselbe Messung faellt einmal durch und besteht einmal die Schwelle
    0,95. Ein fehlendes Register ist deshalb hier ein Fehler und kein Vorgabewert.

    WARUM DIE ZAHL NICHT DER REGISTERSTAND SEIN DARF
    ------------------------------------------------
    Das Register ist anhaengend und waechst waehrend der Reihe: jede Studie schreibt
    unmittelbar nach ihrer Messung an. Wer den Stand zur Aufrufzeit liest, bekommt
    darum eine Zahl, die von der Schleifenposition abhaengt. Nachgemessen an sieben
    Studien bei Registerstand sieben: die erste saehe acht Versuche (DSR 0,7550), die
    siebte vierzehn (DSR 0,6594) -- gleiche Daten, gleiches Verfahren, anderes Urteil,
    und wer zuerst laeuft, wird am mildesten geprueft. Dieselbe Falle beschreibt
    ``backtest/engine.py::deflated_sharpe_for_report`` unter ``expected_trials``.

    Gezaehlt wird deshalb in **ganzen Kampagnen**::

        versuche = fremde Zeilen + (eigene Zeilen // groesse + 1) * groesse

    Waehrend einer ganz durchlaufenden Reihe waechst ``eigene`` von ``q*groesse``
    bis ``q*groesse + groesse - 1``; die ganzzahlige Division liefert dort durchweg
    ``q``, also fuer jede Studie derselbe Wert. Ein zweiter Durchlauf derselben Reihe
    zaehlt eine Kampagne mehr -- zweimal suchen ist zweimal suchen. Die Zahl ist nie
    kleiner als der schlichte Registerstand plus eins (Beweis: mit
    ``eigene = q*groesse + r`` und ``0 <= r < groesse`` ist ``(q+1)*groesse >=
    eigene + 1``), untertreibt also nie -- und untertreiben hiesse hier schmeicheln.

    Grenze der Zusage, ausdruecklich: exakt konstant ist die Zahl nur fuer Reihen, die
    ganz durchlaufen. Bricht eine Reihe nach drei von sieben Laeufen ab, liegt die
    Kampagnengrenze fortan schief, und die naechste Reihe springt an einer Stelle um
    ``groesse`` nach oben. Der Sprung geht nur nach oben, also in die strenge Richtung.

    Ein leeres Register ist kein Fehler: dann laeuft die erste Kampagne, und die Zahl
    ist ihre angemeldete Groesse. Dass niemand durch **Loeschen** des Registers wieder
    bei eins landet, sichert nicht :func:`check_integrity` -- die meldet eine fehlende
    wie eine leere Datei als ``ok`` (und das ist dort richtig, sie zaehlt Zeilen und
    beurteilt sie, sie kennt keinen Sollstand). Es sichert die angemeldete
    Kampagnengroesse: sie ist die Untergrenze, die ein verlorenes Register ueberlebt.
    Vollstaendig ist dieser Schutz nicht -- Laeufe FREMDER Reihen sind nach einem
    Registerverlust verloren, und die Wiederherstellung ist der versionierte Abzug
    (``archiv/ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl``), nicht dieses Modul.
    """
    ledger = Path(path) if path is not None else default_ledger_path()
    if not ledger.is_file():
        raise TrialsLedgerError(
            f"Register {ledger} fehlt. Ohne Register ist die Versuchszahl unbekannt, "
            "und unbekannt ist nicht eins: bei einem Versuch deflationiert nichts. "
            "Fail-closed -- kein Vorgabewert."
        )
    fremd = 0
    eigen = 0
    for trial in iter_trials(ledger):
        if trial.strategy_id.startswith(kampagne.praefix):
            eigen += 1
        else:
            fremd += 1
    return fremd + (eigen // kampagne.groesse + 1) * kampagne.groesse


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
