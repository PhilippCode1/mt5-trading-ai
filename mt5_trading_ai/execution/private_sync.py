"""Private Ereignis-Synchronisation: der Kontostrom haelt das Buch aktuell.

Ein privater Strom (Order-/Positionsereignisse des Kontos) fuehrt das Nettobuch, statt
es zu pollen. Jedes Ereignis traegt eine fortlaufende Sequenznummer. ``PrivateSync``
erkennt zwei Stoerungen und geht in beiden **fail-closed** (Desync):

* **Sequenzluecke** (oder Reihenfolge/Duplikat): eine Nummer fehlt — das Buch koennte
  falsch sein, also nicht weiterhandeln, bis ein Mensch via Reconcile/Adoption aufloest.
* **Stille**: kommt laenger als ``max_silence`` kein Ereignis, ist der Strom evtl. tot.

Der Konsument ist gegen eine Ereignisliste testbar. Die konkrete **Quelle** (ein
Krypto-WS oder MT5-Deal-Abfrage) ist die boersenspezifische Bindung und gehoert an den
realen Lauf — wie ``RealMt5Terminal``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from mt5_trading_ai.execution.reconcile import PositionBook
from mt5_trading_ai.venue.protocol import OrderSide


class PrivateEventKind(str, Enum):
    FILL = "fill"
    HEARTBEAT = "heartbeat"


@dataclass(frozen=True)
class PrivateEvent:
    """Ein normalisiertes Kontoereignis. ``seq`` ist fortlaufend je Strom."""

    seq: int
    ts: datetime
    kind: PrivateEventKind
    #: Nur bei ``FILL`` gesetzt.
    symbol: str | None = None
    side: OrderSide | None = None
    volume: Decimal | None = None


class PrivateSync:
    """Konsumiert den privaten Strom und fuehrt das Buch. Fail-closed bei Desync."""

    def __init__(self) -> None:
        self.book = PositionBook()
        self.last_seq: int | None = None
        self.last_event_ts: datetime | None = None
        self.desync = False
        self.desync_reason: str | None = None

    def apply(self, event: PrivateEvent) -> None:
        self.last_event_ts = event.ts
        if self.desync:
            return  # fail-closed, bis clear_desync
        if self.last_seq is not None and event.seq != self.last_seq + 1:
            self._flag("sequence_gap")
            return
        if event.kind is PrivateEventKind.FILL:
            if event.symbol is None or event.side is None or event.volume is None:
                self._flag("malformed_fill")
                return
            self.book.apply_fill(event.symbol, event.side, event.volume)
        self.last_seq = event.seq

    def _flag(self, reason: str) -> None:
        self.desync = True
        self.desync_reason = reason

    def clear_desync(self) -> None:
        """Nach aufgeloester Divergenz (Reconcile/Adoption). Das naechste Ereignis
        setzt die Sequenz-Basis neu."""
        self.desync = False
        self.desync_reason = None
        self.last_seq = None

    def is_stale(self, now: datetime, max_silence: timedelta) -> bool:
        if self.last_event_ts is None:
            return False
        return now - self.last_event_ts > max_silence

    def healthy(self, now: datetime, max_silence: timedelta) -> bool:
        return not self.desync and not self.is_stale(now, max_silence)

    def snapshot(self) -> dict[str, Decimal]:
        return self.book.snapshot()
