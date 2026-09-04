"""Order-Lebenszyklus und Reconcile: Konto gegen Buch.

Der Handelsplatz fuehrt ein lokales **Buch** der Nettopositionen je Symbol (was das
System zu halten glaubt, aus den angenommenen Fills). Reconcile vergleicht das Buch mit
dem, was der Handelsplatz tatsaechlich meldet.

Weicht beides ueber die Toleranz ab, ist der sichere Zustand ein **Halt**: keine neuen
Eroeffnungen, bis ein Mensch die Divergenz aufloest. Fail-closed in zwei Richtungen:
eine Notional-Drift ueber der Grenze haelt an, und eine **nicht bewertbare** Drift (kein
Preis fuers Symbol) haelt ebenfalls an — Unwissen ist kein Grund weiterzuhandeln.

ZWEI BUECHER, ZWEI FRAGEN (D7/D8, E-005)
---------------------------------------
``PositionBook`` ist das **Netto**-Buch je Symbol, das ``reconcile`` gegen die
Broker-Meldung haelt; es lebt im Prozess und wird beim Start per ``adopt_book`` aus
der Meldung uebernommen. ``Positionsbuch`` ist das **persistierte** Buch der eigenen
Absicht: je Eroeffnung Kennung, Ticket, Symbol, Richtung, Menge, Eroeffnungszeit
und Stop, atomar in ``positionsbuch.json`` im Zustandsordner. Der Broker traegt die
Wahrheit ueber Offenes, das Buch die Absicht; beim Start werden beide abgeglichen
(``Mt5Venue.adopt_book``): was im Buch steht und beim Broker fehlt, ist ein
**Geist** -- er wird mit Journalsatz ausgetragen, nicht stillschweigend. Bis D8 wurde
das Buch nie geschrieben (``tools/wiederanlaufprobe.py`` sicherte das sogar zu); nach
einem Neustart war damit nicht unterscheidbar, ob eine Broker-Position die eigene
ist.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mt5_trading_ai.execution.risiko_zustand import ZustandsortFehler
from mt5_trading_ai.venue.protocol import OrderSide, Position

#: Fassung des Buchformats; eine fremde Fassung ist ein Defekt, kein leeres Buch.
POSITIONSBUCH_FASSUNG = 1


class PositionBook:
    """Lokales Buch der Nettopositionen je Symbol (long positiv, short negativ)."""

    def __init__(self) -> None:
        self._net: dict[str, Decimal] = {}

    def apply_fill(self, symbol: str, side: OrderSide, volume: Decimal) -> None:
        signed = volume if side is OrderSide.BUY else -volume
        self._net[symbol] = self._net.get(symbol, Decimal("0")) + signed

    def net(self, symbol: str) -> Decimal:
        return self._net.get(symbol, Decimal("0"))

    def snapshot(self) -> dict[str, Decimal]:
        return {symbol: net for symbol, net in self._net.items() if net != 0}

    def adopt(self, net_by_symbol: Mapping[str, Decimal]) -> None:
        """Ersetze das Buch durch die gegebenen Nettopositionen (Neustart-Adoption)."""
        self._net = {symbol: net for symbol, net in net_by_symbol.items() if net != 0}


def positions_to_net(positions: Iterable[Position]) -> dict[str, Decimal]:
    """Fasse gemeldete Positionen zu einer Nettomenge je Symbol zusammen."""
    net: dict[str, Decimal] = {}
    for pos in positions:
        signed = pos.volume if pos.side is OrderSide.BUY else -pos.volume
        net[pos.symbol] = net.get(pos.symbol, Decimal("0")) + signed
    return {symbol: value for symbol, value in net.items() if value != 0}


@dataclass(frozen=True)
class SymbolDrift:
    symbol: str
    expected: Decimal
    actual: Decimal
    volume_drift: Decimal
    #: ``None`` heisst: nicht bewertbar (kein Preis) — fail-closed.
    notional_drift: Decimal | None


@dataclass(frozen=True)
class ReconcileResult:
    matched: bool
    halt: bool
    reason: str | None
    drifts: tuple[SymbolDrift, ...]
    total_notional_drift: Decimal


def reconcile_positions(
    *,
    expected: Mapping[str, Decimal],
    actual: Mapping[str, Decimal],
    notional_per_unit: Mapping[str, Decimal],
    max_notional_drift: Decimal,
    volume_tolerance: Decimal = Decimal("0"),
) -> ReconcileResult:
    """Vergleiche Buch (``expected``) mit Meldung (``actual``).

    ``notional_per_unit`` bewertet eine Volumeneinheit je Symbol (Kontraktgroesse mal
    Preis). Eine Drift ueber ``max_notional_drift`` oder eine nicht bewertbare Drift
    fuehrt zu ``halt=True``.
    """
    drifts: list[SymbolDrift] = []
    total = Decimal("0")
    unpriced = False
    for symbol in sorted(set(expected) | set(actual)):
        exp = expected.get(symbol, Decimal("0"))
        act = actual.get(symbol, Decimal("0"))
        volume_drift = act - exp
        if abs(volume_drift) <= volume_tolerance:
            continue
        per_unit = notional_per_unit.get(symbol)
        if per_unit is None:
            drifts.append(SymbolDrift(symbol, exp, act, volume_drift, None))
            unpriced = True
            continue
        notional = abs(volume_drift) * per_unit
        total += notional
        drifts.append(SymbolDrift(symbol, exp, act, volume_drift, notional))

    if not drifts:
        return ReconcileResult(True, False, None, (), Decimal("0"))
    if unpriced:
        return ReconcileResult(False, True, "unpriced_drift", tuple(drifts), total)
    if total > max_notional_drift:
        return ReconcileResult(
            False, True, "notional_drift_exceeds_limit", tuple(drifts), total
        )
    return ReconcileResult(False, False, "within_notional_limit", tuple(drifts), total)


# --- Das persistierte Buch der eigenen Absicht -----------------------------------


class PositionsbuchDefekt(ValueError):
    """Das Buch auf der Platte ist nicht lesbar. Der Aufrufer sperrt Eroeffnungen."""


@dataclass(frozen=True)
class Buchposition:
    """Eine eroeffnete Position, wie dieses Haus sie gewollt und gebucht hat."""

    kennung: str
    #: Ticket der eroeffnenden Order, wie der Handelsplatz es meldete. Das Positions-
    #: ticket meldet der Broker in ``positions_get``; der Startabgleich laeuft je
    #: Symbol, weil auf einem Netting-Konto beide Tickets auseinanderfallen koennen.
    ticket: str
    symbol: str
    #: ``"kauf"`` oder ``"verkauf"``.
    richtung: str
    menge: Decimal
    eroeffnet_am: datetime
    stop: Decimal | None

    @property
    def side(self) -> OrderSide:
        return OrderSide.BUY if self.richtung == "kauf" else OrderSide.SELL

    def as_dict(self) -> dict[str, Any]:
        return {
            "kennung": self.kennung,
            "ticket": self.ticket,
            "symbol": self.symbol,
            "richtung": self.richtung,
            "menge": str(self.menge),
            "eroeffnet_am": self.eroeffnet_am.isoformat(timespec="seconds"),
            "stop": None if self.stop is None else str(self.stop),
        }


def _buchposition_lesen(satz: Any, index: int) -> Buchposition:
    if not isinstance(satz, dict):
        raise PositionsbuchDefekt(f"positionsbuch_defekt: Eintrag {index} kein Objekt")
    try:
        kennung = satz["kennung"]
        ticket = satz["ticket"]
        symbol = satz["symbol"]
        richtung = satz["richtung"]
        menge = Decimal(str(satz["menge"]))
        eroeffnet = datetime.fromisoformat(satz["eroeffnet_am"])
        stop_roh = satz.get("stop")
        stop = None if stop_roh is None else Decimal(str(stop_roh))
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise PositionsbuchDefekt(
            f"positionsbuch_defekt: Eintrag {index} unvollstaendig ({exc})"
        ) from exc
    if not all(isinstance(x, str) and x for x in (kennung, ticket, symbol)):
        raise PositionsbuchDefekt(f"positionsbuch_defekt: Eintrag {index} ohne Text")
    if richtung not in ("kauf", "verkauf"):
        raise PositionsbuchDefekt(
            f"positionsbuch_defekt: Eintrag {index} Richtung {richtung!r}"
        )
    return Buchposition(kennung, ticket, symbol, richtung, menge, eroeffnet, stop)


class Positionsbuch:
    """Das persistierte Buch der eigenen offenen Positionen (D8, E-005).

    Nur mit Pfad konstruierbar; ``Positionsbuch(None)`` wirft ``ZustandsortFehler``.
    Ein Buch nur im Prozess heisst :class:`FluechtigesPositionsbuch` und ist ein
    Testtyp. Jede Aenderung geht sofort und atomar (Nebendatei + ``os.replace``) auf
    die Platte -- zwischen Fill und Absturz liegt sonst genau die Position, die der
    naechste Start nicht mehr kennt.

    ``laden`` liest fail-closed: eine unlesbare Datei ist :class:`PositionsbuchDefekt`,
    kein leeres Buch. Der Aufrufer (``Mt5Venue.adopt_book``) latcht daraufhin den
    Halt; Schliessungen bleiben frei.
    """

    def __init__(self, pfad: Path) -> None:
        if pfad is None:
            raise ZustandsortFehler(
                "Positionsbuch ohne Pfad ist nicht konstruierbar (D8, E-005). Ein "
                "Buch nur im Prozessgedaechtnis heisst FluechtigesPositionsbuch und "
                "ist ein Testtyp; der Betrieb nennt den Zustandsordner."
            )
        self._pfad: Path | None = Path(pfad)

    @property
    def pfad(self) -> Path | None:
        return self._pfad

    @property
    def dauerhaft(self) -> bool:
        return self._pfad is not None

    # --- Platte ------------------------------------------------------------
    def _roh_lesen(self) -> list[Any]:
        assert self._pfad is not None
        try:
            roh = self._pfad.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise PositionsbuchDefekt(f"positionsbuch_unlesbar: {exc}") from exc
        if not roh.strip():
            return []
        try:
            daten = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise PositionsbuchDefekt(f"positionsbuch_defekt: {exc}") from exc
        if not isinstance(daten, dict) or daten.get("fassung") != POSITIONSBUCH_FASSUNG:
            raise PositionsbuchDefekt("positionsbuch_defekt: Fassung oder Objekt")
        liste = daten.get("positionen")
        if not isinstance(liste, list):
            raise PositionsbuchDefekt("positionsbuch_defekt: 'positionen' fehlt")
        return list(liste)

    def _schreiben(self, positionen: list[Buchposition]) -> None:
        assert self._pfad is not None
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        inhalt = json.dumps(
            {
                "fassung": POSITIONSBUCH_FASSUNG,
                "positionen": [p.as_dict() for p in positionen],
            },
            ensure_ascii=False,
            indent=2,
        )
        neben = self._pfad.with_suffix(self._pfad.suffix + ".neu")
        neben.write_text(inhalt, encoding="utf-8")
        os.replace(neben, self._pfad)

    # --- Lesen und Fortschreiben --------------------------------------------
    def laden(self) -> tuple[Buchposition, ...]:
        return tuple(_buchposition_lesen(s, i) for i, s in enumerate(self._roh_lesen()))

    def eintragen(self, position: Buchposition) -> None:
        """Eine Eroeffnung buchen. Dieselbe Kennung wird nicht doppelt gefuehrt."""
        bestand = [p for p in self.laden() if p.kennung != position.kennung]
        self._schreiben([*bestand, position])

    def austragen(self, kennung: str) -> Buchposition | None:
        """Eine Position ueber ihre Kennung ausbuchen; ``None``, wenn unbekannt."""
        bestand = list(self.laden())
        weg = next((p for p in bestand if p.kennung == kennung), None)
        if weg is None:
            return None
        self._schreiben([p for p in bestand if p.kennung != kennung])
        return weg

    def austragen_symbol(self, symbol: str) -> tuple[Buchposition, ...]:
        """Alle Positionen eines Symbols ausbuchen (netto glattgestellt)."""
        bestand = list(self.laden())
        weg = tuple(p for p in bestand if p.symbol == symbol)
        if weg:
            self._schreiben([p for p in bestand if p.symbol != symbol])
        return weg

    def abgleichen(self, offen_beim_broker: Iterable[str]) -> tuple[Buchposition, ...]:
        """Startabgleich (D7): Geister austragen, die Ausgetragenen zurueckgeben.

        Ein Geist ist eine gebuchte Position, deren Symbol beim Broker nicht mehr
        offen ist -- etwa ein Stop, der im Stillstand ueber das Wochenende gefeuert
        hat. Er wird hier ausgetragen; der Aufrufer schreibt den Journalsatz.
        """
        offen = set(offen_beim_broker)
        bestand = list(self.laden())
        geister = tuple(p for p in bestand if p.symbol not in offen)
        if geister:
            self._schreiben([p for p in bestand if p.symbol in offen])
        return geister


class FluechtigesPositionsbuch(Positionsbuch):
    """Das Buch nur im Prozessgedaechtnis -- der ausdrueckliche Testtyp (D8)."""

    def __init__(self) -> None:
        self._pfad = None
        self._speicher: list[Buchposition] = []

    def _roh_lesen(self) -> list[Any]:
        return [p.as_dict() for p in self._speicher]

    def _schreiben(self, positionen: list[Buchposition]) -> None:
        self._speicher = list(positionen)
