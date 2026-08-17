"""Ein fehlgeschlagener Positionsabruf ist kein leeres Buch.

WARUM DIESER TEST
-----------------
``MetaTrader5.positions_get()`` gibt bei einem **Fehler** ``None`` zurueck und bei
wirklich flachem Konto ein leeres Tupel. Ein ``or ()`` macht aus beidem dasselbe.

Das ist die gefaehrlichste Verwechslung im ganzen Betriebspfad, weil sie in der
schmeichelnden Richtung liegt: eine Dauerschleife, die offene Positionen mit dem
Broker abgleicht, verbucht bei jeder Verbindungsstoerung **alle** Positionen als
geschlossen. Sie schreibt eine Falschaussage ins Betriebsjournal (die einzige
Beweisdatei des Laufs), entfernt sie aus dem Positionszaehler der Risikoschicht --
der Deckel zaehlt dann zu niedrig, also fail-open -- und wuerde beim naechsten
``adopt_book()`` das lokale Buch auf leer setzen, waehrend real Positionen laufen.

Gefunden von einem Rotteam-Durchgang vor dem ersten unbeaufsichtigten Tageslauf.
"""

from __future__ import annotations

from typing import Any

import pytest
from mt5_trading_ai.venue.mt5 import RealMt5Terminal
from mt5_trading_ai.venue.protocol import VenueUnavailableError


class _Mt5Attrappe:
    """Nur so viel MetaTrader5, wie ``positions()`` anfasst."""

    POSITION_TYPE_BUY = 0

    def __init__(self, antwort: Any) -> None:
        self._antwort = antwort
        self.aufrufe = 0

    def positions_get(self) -> Any:
        self.aufrufe += 1
        return self._antwort


def _terminal_mit(antwort: Any) -> RealMt5Terminal:
    terminal = RealMt5Terminal(allow_write=False)
    terminal._mt5 = _Mt5Attrappe(antwort)  # type: ignore[assignment]
    return terminal


def test_none_ist_ein_fehler_und_kein_leeres_buch() -> None:
    """Der eigentliche Befund: ``None`` darf nicht zu ``()`` werden."""
    terminal = _terminal_mit(None)
    with pytest.raises(VenueUnavailableError, match="positions_get"):
        terminal.positions()


def test_die_fehlermeldung_benennt_die_verwechslung() -> None:
    """Wer den Fehler liest, soll den Unterschied sofort sehen."""
    terminal = _terminal_mit(None)
    with pytest.raises(VenueUnavailableError) as fehler:
        terminal.positions()
    text = str(fehler.value)
    assert "leeres Buch" in text, (
        "Die Meldung muss sagen, dass dies NICHT dasselbe wie ein leeres Buch ist -- "
        f"sonst wird sie wieder verwechselt. Bekommen: {text!r}"
    )


def test_wirklich_leeres_buch_bleibt_leer() -> None:
    """Die Gegenprobe: ein flaches Konto ist kein Fehler.

    Ohne sie koennte man den Test oben bestehen, indem man immer wirft.
    """
    terminal = _terminal_mit(())
    assert terminal.positions() == ()


def test_leere_liste_ist_ebenfalls_kein_fehler() -> None:
    """MetaTrader5 liefert je nach Aufruf Tupel oder Liste."""
    terminal = _terminal_mit([])
    assert terminal.positions() == ()
