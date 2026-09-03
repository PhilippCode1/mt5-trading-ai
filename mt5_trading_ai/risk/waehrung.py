"""Geldbetraege tragen ihre Waehrung; ein Kurs ist ein Messwert oder eine Sperre.

WARUM (D3, E-005)
-----------------
Die Positionsgroesse rechnete ``Risikobetrag / (Stopabstand * Kontraktgroesse)``: der
Zaehler in Kontowaehrung, der Nenner in Notierungswaehrung, dazwischen kein Kurs.
Fuer EURGBP auf einem USD-Konto lag der Verlust am Stop damit 26 % ueber dem Budget,
fuer USDJPY wurde die Marge tausendfach falsch gerechnet (Bewertung 3.3, nachgestellt
in PROGRAMM/auftrag-01-fundament/belege/03-nachstellung, V3/V3c). Der Fehler ist keine
Stelle, sondern eine Klasse: eine Zahl ohne Waehrung laesst sich mit jeder anderen
Zahl multiplizieren.

Darum tragen Betraege hier ihre Waehrung als Typ. Zwei Betraege verschiedener
Waehrung lassen sich nicht addieren; ein Betrag wird nur mit einem **gegebenen**
Kurs umgerechnet, und ein fehlender Kurs ist keine 1, sondern ``WaehrungsFehler`` --
der Orderpfad sperrt dann mit ``fx_unverifiable`` (fehlender Wert sperrt, Regel 7).

Kursquelle ist das Terminal: der Mittelkurs des Paars ``VONNACH`` oder der Kehrwert
von ``NACHVON`` (:func:`kurs_aus_ticks`). Gleich lautende Waehrungen haben den Kurs 1.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class WaehrungsFehler(ValueError):
    """Zwei Waehrungen ohne Kurs -- oder ein Kurs, der keiner ist."""


@dataclass(frozen=True)
class Betrag:
    """Ein Geldbetrag mit Waehrung. Rechnen nur innerhalb derselben Waehrung."""

    wert: Decimal
    waehrung: str

    def __post_init__(self) -> None:
        if not self.waehrung or not self.waehrung.strip():
            raise WaehrungsFehler("Betrag ohne Waehrung")

    def _gleich(self, anderer: Betrag) -> None:
        if anderer.waehrung != self.waehrung:
            raise WaehrungsFehler(
                f"{self.waehrung} und {anderer.waehrung} lassen sich nicht ohne Kurs "
                "verrechnen"
            )

    def __add__(self, anderer: Betrag) -> Betrag:
        self._gleich(anderer)
        return Betrag(self.wert + anderer.wert, self.waehrung)

    def __sub__(self, anderer: Betrag) -> Betrag:
        self._gleich(anderer)
        return Betrag(self.wert - anderer.wert, self.waehrung)

    def mal(self, faktor: Decimal) -> Betrag:
        return Betrag(self.wert * faktor, self.waehrung)

    def umgerechnet(self, nach: str, kurs: Decimal | None) -> Betrag:
        """Dieser Betrag in ``nach``; ``kurs`` ist der Wert EINER Einheit dieser
        Waehrung in ``nach``. Fehlt er bei ungleicher Waehrung, ist das eine Sperre."""
        if nach == self.waehrung:
            return self
        if kurs is None or kurs <= 0:
            raise WaehrungsFehler(
                f"fx_unverifiable: kein Kurs {self.waehrung}->{nach} "
                f"(Betrag {self.wert} {self.waehrung})"
            )
        return Betrag(self.wert * kurs, nach)


class Kursquelle(Protocol):
    """Liefert den Wert einer Einheit ``von`` in ``nach`` -- oder ``None``."""

    def kurs(self, von: str, nach: str) -> Decimal | None: ...


def kurs_aus_ticks(von: str, nach: str, tick: Callable[[str], Any]) -> Decimal | None:
    """Kurs aus Ticks: Mittelkurs von ``VONNACH``, sonst Kehrwert von ``NACHVON``.

    ``tick(symbol)`` liefert ein Objekt mit ``bid``/``ask`` oder ``None``. Ein Kurs
    von 0 oder ein verschraenkter Tick zaehlt als nicht messbar.
    """
    if von == nach:
        return Decimal("1")
    direkt = tick(f"{von}{nach}")
    if direkt is not None:
        mid = (Decimal(str(direkt.bid)) + Decimal(str(direkt.ask))) / Decimal("2")
        if mid > 0:
            return mid
    kehr = tick(f"{nach}{von}")
    if kehr is not None:
        mid = (Decimal(str(kehr.bid)) + Decimal(str(kehr.ask))) / Decimal("2")
        if mid > 0:
            return Decimal("1") / mid
    return None
