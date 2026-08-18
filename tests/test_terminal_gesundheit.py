"""Ein laufender Prozess ist keine stehende Leitung (E10.1).

WARUM DIESER TEST
-----------------
Der Vertrag in ``venue/protocol.py`` verlangt von ``is_healthy`` ein Rot bei
**fehlendem Terminal oder fehlender Sitzung** -- zwei Faelle.
``RealMt5Terminal.is_connected`` pruefte davon genau einen:

    return self._mt5.terminal_info() is not None

Das beantwortet allein die Frage, ob der Terminal-**Prozess** laeuft. Ein
MetaTrader, das offen auf dem Bildschirm steht und die Verbindung zum Handelsserver
verloren hat, antwortet darauf mit ja. Das Feld ``terminal_info().connected``, das
genau diese Frage beantwortet, wurde im gesamten Adapter nirgends gelesen.

Der Zustand ist der gefaehrliche, weil er in die schmeichelnde Richtung faellt: das
Terminal liefert weiter Zahlen, sie sind nur alt, und ``is_healthy`` sagt gruen dazu.
Am Kopf fast jeder Methode des Venues steht ``_require_healthy()`` -- die Sperre war
also ueberall verdrahtet und nirgends wirksam. Hausfehlerklasse.

WAS HIER JETZT GEPRUEFT WIRD
----------------------------
1. Laeuft ein Terminal? (``terminal_info()``)
2. Steht die Leitung zum Handelsserver? (``terminal_info().connected``)
3. Gibt es eine Kontositzung? (``account_info()``)

Die getrennt gefuehrte Vertragspflicht -- das Alter der Daten -- braucht einen
Kursstempel je Symbol und wird am Order-Pfad gestellt; siehe
``test_frische_am_orderpfad.py`` und die praezisierte Vertragszusage in
``venue/protocol.py``. Sie stand frueher als dritter Fall in DIESER Zusage; dass sie
dort keine Umsetzung je geprueft hat, ist der Grund fuer die Praezisierung. Der Text
hier ist mit dem Vertrag nachgezogen -- ein Zitat, das seiner Quelle widerspricht,
ist schlimmer als kein Zitat.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mt5_trading_ai.venue.mt5 import RealMt5Terminal

ROOT = Path(__file__).resolve().parents[1]
MT5_QUELLE = ROOT / "mt5_trading_ai" / "venue" / "mt5.py"


class _Mt5Attrappe:
    """Nur so viel MetaTrader5, wie ``is_connected()`` anfasst."""

    def __init__(self, *, terminal: Any, konto: Any) -> None:
        self._terminal = terminal
        self._konto = konto
        self.terminal_abfragen = 0
        self.konto_abfragen = 0

    def terminal_info(self) -> Any:
        self.terminal_abfragen += 1
        return self._terminal

    def account_info(self) -> Any:
        self.konto_abfragen += 1
        return self._konto


#: Irgendein Objekt ungleich ``None`` -- steht fuer "es gibt eine Kontositzung".
#: Der Inhalt ist unerheblich; geprueft wird allein, ob ``account_info()`` etwas gibt.
_KONTO_DA = object()


def _terminal_mit(*, terminal: Any, konto: Any = _KONTO_DA) -> RealMt5Terminal:
    echt = RealMt5Terminal(allow_write=False)
    echt._mt5 = _Mt5Attrappe(terminal=terminal, konto=konto)  # type: ignore[assignment]
    return echt


# --- Rot, und schon vorher rot --------------------------------------------
def test_ohne_bindung_ist_rot() -> None:
    """``initialize()`` nicht gelaufen: es gibt gar kein Paket, das man fragen koennte."""
    assert RealMt5Terminal(allow_write=False).is_connected() is False


def test_ohne_terminal_info_ist_rot() -> None:
    """Der Fall, den die alte Fassung schon fing: kein Prozess."""
    assert _terminal_mit(terminal=None).is_connected() is False


# --- Rot, und vorher gruen (die eigentlichen Eichfaelle) -------------------
def test_prozess_laeuft_aber_leitung_ist_weg_ist_rot() -> None:
    """Der Befund E10.1: Terminal offen, Handelsserver getrennt.

    Gegen die alte Fassung war das gesund -- und der ganze Risikoapparat rechnete
    weiter auf den letzten Zahlen, die noch im Speicher standen.
    """
    echt = _terminal_mit(terminal=SimpleNamespace(connected=False))
    assert echt.is_connected() is False


def test_ohne_kontositzung_ist_rot() -> None:
    """Terminal verbunden, aber kein Konto angemeldet.

    ``account_info()`` ist genau dann ``None`` -- und aus genau diesem Aufruf zieht
    die Risikoschicht Equity und freie Marge. Ohne Konto gibt es keine Zahlen, auf
    denen eine Sperre rechnen koennte.
    """
    echt = _terminal_mit(terminal=SimpleNamespace(connected=True), konto=None)
    assert echt.is_connected() is False


def test_fehlendes_feld_connected_ist_rot() -> None:
    """Eine Bindung, die das Feld gar nicht kennt, gilt als nicht verbunden.

    Fail-closed: eine unbeantwortbare Frage ist keine bestandene Pruefung. Die
    Gegenrichtung (``getattr(..., True)``) haette die Sperre fuer jede fremde oder
    aeltere Bindung stillschweigend abgeschaltet.
    """

    class _OhneFeld:
        pass

    assert _terminal_mit(terminal=_OhneFeld()).is_connected() is False


# --- Gruen, damit "immer rot" nicht als Loesung durchgeht ------------------
def test_verbunden_und_angemeldet_ist_gruen() -> None:
    """Gegenprobe. Ohne sie liesse sich jeder Test oben durch ein ``return False``
    bestehen -- der Spiegelfehler zum Melder, der nie ausloest."""
    echt = _terminal_mit(terminal=SimpleNamespace(connected=True), konto=_KONTO_DA)
    assert echt.is_connected() is True


def test_beide_abfragen_laufen_wirklich() -> None:
    """Belegt, dass die zwei neuen Fragen nicht bloss im Quelltext stehen."""
    attrappe = _Mt5Attrappe(terminal=SimpleNamespace(connected=True), konto=_KONTO_DA)
    echt = RealMt5Terminal(allow_write=False)
    echt._mt5 = attrappe  # type: ignore[assignment]
    assert echt.is_connected() is True
    assert attrappe.terminal_abfragen == 1
    assert attrappe.konto_abfragen == 1


def test_kontoabfrage_entfaellt_bei_toter_leitung() -> None:
    """Kurzschluss in der richtigen Reihenfolge: ohne Leitung wird nicht weiter
    gefragt. Das haelt den Aufruf billig -- er steht am Kopf fast jeder Methode."""
    attrappe = _Mt5Attrappe(terminal=SimpleNamespace(connected=False), konto=_KONTO_DA)
    echt = RealMt5Terminal(allow_write=False)
    echt._mt5 = attrappe  # type: ignore[assignment]
    assert echt.is_connected() is False
    assert attrappe.konto_abfragen == 0


# --- Struktur: die Pruefung darf nicht still verschwinden -----------------
def test_is_connected_liest_die_beiden_felder_wirklich() -> None:
    """Dauertor gegen den Rueckfall auf ``terminal_info() is not None``."""
    baum = ast.parse(MT5_QUELLE.read_text(encoding="utf-8"))
    quelle: str | None = None
    for node in baum.body:
        if isinstance(node, ast.ClassDef) and node.name == "RealMt5Terminal":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "is_connected":
                    quelle = ast.unparse(child)
    if quelle is None:
        pytest.fail(
            "Dauertor findet seinen Gegenstand nicht: RealMt5Terminal.is_connected "
            "in venue/mt5.py. Ein Tor, das nichts findet und deshalb gruen ist, ist "
            "der Fehler selbst."
        )
    for feld in ("connected", "account_info"):
        assert feld in quelle, (
            f"RealMt5Terminal.is_connected liest {feld!r} nicht mehr. Damit prueft es "
            "wieder nur, ob der Prozess laeuft -- ein Terminal ohne Leitung zum "
            f"Handelsserver gaelte als gesund.\n{quelle}"
        )
