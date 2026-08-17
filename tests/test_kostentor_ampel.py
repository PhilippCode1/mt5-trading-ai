"""Tests fuer das M1-Urteil aus ``tools/kostentor.py``.

Diese Datei existiert, weil die Berichtigung von Abbruchbedingung 1 monatelang **nur im
Dokument** stand: ``ABBRUCH.md`` erklaerte die ROT-Schwelle auf "alle bewertbaren,
mindestens vier" umgestellt, ``tools/kostentor.py`` pruefte weiter gegen alle sechs.
Kein Test konnte den Unterschied bemerken, weil das Urteil nur als Nebenwirkung einer
``print``-Kaskade entstand.

Der wichtigste Fall hier ist darum ``test_rot_ist_ueberhaupt_erreichbar``: er haette
gegen die alte Fassung rot geleuchtet und ist der eigentliche Beleg, dass die Ampel
nicht mehr per Konstruktion gruen ist.
"""

from __future__ import annotations

from tools.kostentor import (
    M1_MIN_BEWERTBAR,
    M1_MIN_INSTRUMENTE_GRUEN,
    UNIVERSUM,
    m1_ampel,
)

#: Die fuenf bewertbaren Instrumente am Stand 2026-08-17 (BTCUSD ist nicht bewertbar).
BEWERTBAR = ("EURUSD", "GBPJPY", "XAUUSD", "DE40", "NVDA")


def test_stand_2026_08_17_ist_gruen() -> None:
    """Die gemessene Lage: vier gruen, ein Broker traegt drei davon."""
    ampel, satz = m1_ampel(
        bewertbar=BEWERTBAR,
        gruen=("EURUSD", "XAUUSD", "DE40", "NVDA"),
        rot=(),
        bester_broker=("ic_markets_eu", ["XAUUSD", "DE40", "NVDA"]),
    )
    assert ampel == "GRUEN"
    assert "ic_markets_eu" in satz


def test_rot_ist_ueberhaupt_erreichbar() -> None:
    """Der Eichfall, um den es geht.

    Ein Instrument (BTCUSD) ist dauerhaft nicht bewertbar. Die alte Fassung verlangte
    fuer ROT ``len(rot) == len(UNIVERSUM)`` -- also alle sechs -- und konnte damit nie
    ausloesen. Gegen die bewertbaren gerechnet loest sie aus.
    """
    ampel, satz = m1_ampel(
        bewertbar=BEWERTBAR,
        gruen=(),
        rot=BEWERTBAR,
        bester_broker=("-", []),
    )
    assert ampel == "ROT", "ROT muss mit einem nicht bewertbaren Instrument erreichbar sein"
    assert str(len(BEWERTBAR)) in satz
    # Und der Gegenbeweis zur alten Regel, damit der Unterschied festgeschrieben ist:
    assert len(BEWERTBAR) < len(UNIVERSUM)


def test_zu_duenne_datenlage_gilt_als_ausgeloest() -> None:
    """Weniger als vier bewertbare Instrumente: fail-closed, kein Urteil."""
    ampel, satz = m1_ampel(
        bewertbar=("EURUSD", "XAUUSD", "DE40"),
        gruen=("EURUSD", "XAUUSD", "DE40"),
        rot=(),
        bester_broker=("ic_markets_eu", ["EURUSD", "XAUUSD", "DE40"]),
    )
    assert ampel == "AUSGELOEST"
    assert str(M1_MIN_BEWERTBAR) in satz


def test_duenne_datenlage_schlaegt_gruen() -> None:
    """Die Reihenfolge der Zweige ist der eigentliche Schutz.

    Drei bewertbare, alle gruen, ein Broker traegt alle drei -- nach der Gruen-Regel
    allein waere das GRUEN. Es darf nicht GRUEN sein: die halbe Pruefmenge ist
    unbewertet, und eine fehlende Messung gilt als nicht erfuellt.
    """
    ampel, _ = m1_ampel(
        bewertbar=("EURUSD", "XAUUSD", "DE40"),
        gruen=("EURUSD", "XAUUSD", "DE40"),
        rot=(),
        bester_broker=("ic_markets_eu", ["EURUSD", "XAUUSD", "DE40"]),
    )
    assert ampel != "GRUEN"


def test_gelb_wenn_weder_gruen_noch_durchgehend_rot() -> None:
    ampel, _ = m1_ampel(
        bewertbar=BEWERTBAR,
        gruen=("EURUSD",),
        rot=("GBPJPY",),
        bester_broker=("ic_markets_eu", ["EURUSD"]),
    )
    assert ampel == "GELB"


def test_gruen_verlangt_einen_einzelnen_broker_der_traegt() -> None:
    """M1 sagt "bei mindestens einem Broker" -- nicht je Instrument der guenstigste.

    Vier gruene Instrumente, aber kein Anbieter traegt mehr als zwei: das waere ein
    Konto, das es nicht gibt.
    """
    ampel, _ = m1_ampel(
        bewertbar=BEWERTBAR,
        gruen=("EURUSD", "XAUUSD", "DE40", "NVDA"),
        rot=(),
        bester_broker=("ic_markets_eu", ["XAUUSD", "DE40"]),
    )
    assert ampel != "GRUEN"
    assert M1_MIN_INSTRUMENTE_GRUEN == 3


def test_rot_verlangt_wirklich_alle_bewertbaren() -> None:
    """Ein einziges nicht-rotes bewertbares Instrument verhindert ROT."""
    ampel, _ = m1_ampel(
        bewertbar=BEWERTBAR,
        gruen=(),
        rot=BEWERTBAR[:-1],
        bester_broker=("-", []),
    )
    assert ampel == "GELB"
