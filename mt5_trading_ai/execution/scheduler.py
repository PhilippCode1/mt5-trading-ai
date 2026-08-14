"""Treiber-Loop/Scheduler (Paket 7): Frische, Drift und Drawdown-Peak getaktet pruefen.

Die Naehte ``check_sync`` (Stille/Desync) und ``reconcile`` (Positions-Drift) setzen den
Global-Halt am Venue -- aber nur, wenn sie **gefahren** werden. Passiv (nur je Order)
reichte nicht: Frische, Drift und der Drawdown-Fenster-Hoechststand muessen auch dann
bewertet werden, wenn gerade kein Auftrag laeuft. Dieser Scheduler taktet sie auf festem
Intervall, unabhaengig vom Signal-Pfad.

**S2 -- die geschlossene Frische-Kante:** ``PrivateSync.is_stale`` gibt ``False``,
solange NIE ein Ereignis ankam (``last_event_ts is None``) -- ein Strom, der nie
startet, gilt so nicht als tot (fail-open). Der Scheduler schliesst das: liefert ein
konfigurierter Strom
bis ``started_at + max_silence`` kein einziges Ereignis, wird der Halt gelatcht
(``stream_never_started``). Nach dem ersten Ereignis uebernimmt ``check_sync`` die
Stille-Ueberwachung regulaer.

Fail-closed: jeder erkannte Defekt (Stille, nie gestartet, Desync, Drift) latcht den
Halt; der loest nur menschlich (``clear_halt``) nach aufgeloester Ursache.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from mt5_trading_ai.execution.private_sync import PrivateEvent
from mt5_trading_ai.execution.reconcile import ReconcileResult
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.protocol import VenueError

SCHEDULER_VERSION = "sync-scheduler-v1"


@dataclass(frozen=True)
class TickResult:
    """Ergebnis eines Takts -- der Nachweis, dass Frische/Drift gefahren wurden."""

    now: datetime
    halted: bool
    halt_reason: str | None
    sync_healthy: bool
    stream_never_started: bool
    reconcile: ReconcileResult | None
    events_applied: int
    version: str = SCHEDULER_VERSION


class SyncScheduler:
    """Faehrt je Takt observe_equity -> Ereignisse -> check_sync -> S2 -> reconcile.

    ``max_silence`` ist das S2-Budget (Strom laenger stumm -> Halt). ``started_at`` ist
    der Bezug fuer die Nie-gestartet-Kante. ``risk_manager`` (optional) bekommt je Takt
    eine
    Equity-Beobachtung, damit der Drawdown-Fenster-Hoechststand auch ohne Order waechst.
    """

    def __init__(
        self,
        venue: Mt5Venue,
        *,
        max_silence: timedelta,
        started_at: datetime,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self._venue = venue
        self._max_silence = max_silence
        self._started_at = started_at
        self._rm = risk_manager

    def tick(
        self, now: datetime, *, events: Sequence[PrivateEvent] = ()
    ) -> TickResult:
        """Ein Takt. ``events`` sind die seit dem letzten Takt eingetroffenen
        Kontoereignisse (in Sequenzreihenfolge). Setzt den Halt bei jedem Defekt."""
        # 1) Equity-Beobachtung ZUERST -- sonst bleibt der Fenster-Peak ~ aktuelle
        # Equity und der Drawdown-Halt feuert nie. get_account() prueft die Sitzung und
        # wirft bei Abbruch -- fail-closed latchen (klebrig, nur via clear_halt loesbar)
        # UND weiterlaufen, statt die Ausnahme aus tick() propagieren zu lassen (sonst
        # bliebe der Halt in der rm-Konfiguration ungesetzt -- §9-Blocker).
        if self._rm is not None:
            try:
                self._rm.observe_equity(now, self._venue.get_account().equity)
            except VenueError:
                self._venue.latch_halt(reason="account_unavailable")

        # 2) Eingetroffene Ereignisse in Reihenfolge einspeisen (Desync -> Halt intern).
        for event in events:
            self._venue.apply_private_event(event)

        # 3) Stromgesundheit: Stille (nach erstem Ereignis) ODER Desync -> Halt.
        healthy = self._venue.check_sync(now, max_silence=self._max_silence)

        # 4) S2-Kante: ein konfigurierter Strom, der bis started_at+max_silence NIE ein
        # Ereignis lieferte, ist fuer check_sync unsichtbar -> hier fail-closed latchen.
        never_started = (
            self._venue.has_private_stream
            and self._venue.stream_last_event_ts is None
            and now - self._started_at > self._max_silence
        )
        if never_started:
            self._venue.latch_halt(reason="stream_never_started")
            healthy = False

        # 5) Positions-Drift gegen frischen Boersen-Query; Drift ueber Grenze -> Halt.
        recon: ReconcileResult | None
        try:
            recon = self._venue.reconcile()
        except VenueError:
            # Reconcile nicht fahrbar (Sitzung weg) ist selbst ein Grund fuer den Halt.
            self._venue.latch_halt(reason="reconcile_unavailable")
            recon = None

        return TickResult(
            now=now,
            halted=self._venue.is_halted(),
            halt_reason=self._venue.halt_reason,
            sync_healthy=healthy,
            stream_never_started=never_started,
            reconcile=recon,
            events_applied=len(events),
        )
