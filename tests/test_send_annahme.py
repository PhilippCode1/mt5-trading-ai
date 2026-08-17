"""Wann gilt eine Order als angenommen -- und wann darf sie es NICHT.

WARUM DIESER TEST
-----------------
Die MetaTrader5-Dokumentation nennt ``TRADE_RETCODE_DONE`` (10009) als Erfolg. Der am
2026-08-17 gemessene Broker liefert bei einem **ausgefuehrten** Marktauftrag jedoch
``retcode=0`` mit ``comment='Done'`` -- samt gueltiger Order- und Deal-Kennung,
Volumen 0,11 und Preis 1,15878.

Eine Pruefung allein auf 10009 haelt eine ausgefuehrte Order fuer abgelehnt. Das ist
die gefaehrlichste Fehlrichtung im ganzen Betriebspfad: die Position steht beim
Broker, das System weiss nichts davon, das lokale Buch bleibt leer, der naechste
Reconcile sieht die volle Position als Drift und latcht den Global-Halt. Genau so
endete der erste scharfe Lauf -- nach einem Takt.

Die Gegenrichtung ist ebenso wichtig: ``retcode=0`` allein darf nicht genuegen. Es
muss etwas zugeteilt worden sein.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from mt5_trading_ai.venue.mt5 import _send_angenommen


class _Konstanten:
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_DONE_PARTIAL = 10010


@dataclass
class _Ergebnis:
    retcode: int
    order: int = 0
    deal: int = 0
    volume: float = 0.0
    comment: str = ""


MT5: Any = _Konstanten()


# --- Angenommen ------------------------------------------------------------
@pytest.mark.parametrize("code", [10009, 10008, 10010])
def test_dokumentierte_erfolgscodes_gelten(code: int) -> None:
    assert _send_angenommen(MT5, _Ergebnis(retcode=code, order=1, volume=0.1))


def test_der_gemessene_fall_retcode_null_mit_zuteilung() -> None:
    """Der reale Fall vom 2026-08-17: ausgefuehrt, aber retcode 0."""
    res = _Ergebnis(retcode=0, order=10057432438, deal=9759135343,
                    volume=0.11, comment="Done")
    assert _send_angenommen(MT5, res), (
        "Eine ausgefuehrte Order mit Order- und Deal-Kennung und Volumen 0,11 muss "
        "als angenommen gelten -- sonst weiss das System nichts von seiner Position."
    )


def test_retcode_null_mit_nur_deal_kennung_genuegt() -> None:
    assert _send_angenommen(MT5, _Ergebnis(retcode=0, deal=42, volume=0.05))


# --- Nicht angenommen ------------------------------------------------------
def test_retcode_null_ohne_zuteilung_ist_keine_annahme() -> None:
    """„Kein Fehlercode" allein genuegt nicht -- sonst gilt jede Leerantwort als Fill."""
    assert not _send_angenommen(MT5, _Ergebnis(retcode=0))


def test_retcode_null_mit_kennung_aber_ohne_volumen_ist_keine_annahme() -> None:
    assert not _send_angenommen(MT5, _Ergebnis(retcode=0, order=1, volume=0.0))


@pytest.mark.parametrize("code", [10004, 10006, 10013, 10019, 10027, 10030])
def test_echte_fehlercodes_bleiben_ablehnungen(code: int) -> None:
    """Requote, Rejected, Invalid request, No money, AutoTrading aus, Invalid fill.

    Auch mit zugeteilter Kennung: ein benannter Fehlercode ist ein Fehler.
    """
    assert not _send_angenommen(MT5, _Ergebnis(retcode=code, order=1, volume=0.1))


def test_keine_antwort_ist_keine_annahme() -> None:
    assert not _send_angenommen(MT5, None)


def test_fehlendes_retcode_feld_ist_keine_annahme() -> None:
    """Ein Objekt ohne ``retcode`` ist kein Ergebnis, das man deuten darf."""

    class _Leer:
        pass

    assert not _send_angenommen(MT5, _Leer())
