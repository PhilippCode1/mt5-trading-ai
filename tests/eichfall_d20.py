"""Eichfall D20 (MP01 Tabelle; Bewertung 2026-09-02 Z. 112): Serverversatz gemessen,
nicht angenommen.

ROT gegen 306bbaa (belege/06-d20-rot.txt): das Terminal drehte seine Zeitstempel ueber
``ZoneInfo("Europe/Helsinki")`` (EU-Sommerzeittermin). Ein Server, der nach US-Termin
umschaltet, liegt im Fenster 2026-03-08 (US-Beginn) bis 2026-03-29 (EU-Beginn) eine
Stunde vor der Zone: ``_utc`` liefert 13:00 fuer einen Tick von 12:00 UTC, und
``Mt5Venue._enforce_account_freshness`` sperrt einen taufrischen Tick als
``snapshot_from_future``. Kein Eintritt, still, 2-4 Wochen im Jahr.

GRUEN gegen HEAD (belege/06-d20-gruen.txt): ``RealMt5Terminal.messe_serverversatz``
misst 3 h am Tick, ``_utc`` trifft, die Frische ist gruen. Zweiter Fall: ein 40 min
alter Tick rueckt nicht vor -> ``ServerversatzFehler``, nichts gesetzt, die
Eroeffnung bleibt abgewiesen (nicht bewertbar = nicht erfuellt).

Die Datei baut das Terminal so, wie es der Betrieb baut -- HEAD: ohne Zone, Versatz
gemessen (``tools/live_betrieb.py``, Kopf des Taktes); 306bbaa: mit
``server_tz=SERVER_TZ_NAME`` (``tools/live_betrieb.py:988`` dort). Nur der zweite
Fall importiert Namen, die es erst in HEAD gibt (im Test, nicht am Modulkopf).
"""

from __future__ import annotations

import inspect
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import OrderRejectedError  # noqa: E402

#: US-Sommerzeit 2026: Beginn Sonntag 08.03. 02:00 Ortszeit (07:00 UTC an der
#: Ostkueste), Ende Sonntag 01.11. Die EU schaltet am 29.03. und am 25.10.
US_SOMMER_BEGINN = datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
US_SOMMER_ENDE = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
#: Montag im Fenster: US schon Sommer, EU noch Winter.
IM_FENSTER = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
#: Montag ausserhalb des Fensters: beide Regeln sagen Winter (+2 h).
AUSSERHALB = datetime(2026, 2, 2, 12, 0, tzinfo=UTC)


def _us_versatz(jetzt: datetime) -> timedelta:
    """Wanduhr eines Servers mit Basis UTC+2, der nach US-Termin auf +3 h schaltet."""
    if US_SOMMER_BEGINN <= jetzt < US_SOMMER_ENDE:
        return timedelta(hours=3)
    return timedelta(hours=2)


class _Uhr:
    def __init__(self, jetzt: datetime) -> None:
        self.jetzt = jetzt

    def __call__(self) -> datetime:
        return self.jetzt

    def schlaf(self, sekunden: float) -> None:
        self.jetzt += timedelta(seconds=sekunden)


class _Tick:
    def __init__(self, wanduhr: datetime) -> None:
        self.time = int(wanduhr.timestamp())
        self.time_msc = int(wanduhr.timestamp() * 1000)
        self.bid = 1.0999
        self.ask = 1.1


class _Mt5Attrappe:
    """Ein Server mit US-Sommerzeitregel; der Tick ist ``alter`` alt (druckt), oder
    er steht seit ``steht`` (echte UTC-Zeit des letzten Ticks)."""

    def __init__(
        self,
        uhr: _Uhr,
        *,
        alter: timedelta = timedelta(0),
        steht: datetime | None = None,
    ) -> None:
        self.uhr = uhr
        self.alter = alter
        self.steht = steht

    def symbol_info_tick(self, symbol: str) -> Any:
        if self.steht is not None:
            return _Tick(self.steht + _us_versatz(self.steht))
        echt = self.uhr.jetzt - self.alter
        return _Tick(echt + _us_versatz(echt))

    def terminal_info(self) -> Any:
        return SimpleNamespace(connected=True)

    def account_info(self) -> Any:
        return object()


def _terminal_wie_im_betrieb(uhr: _Uhr, attrappe: _Mt5Attrappe) -> RealMt5Terminal:
    """HEAD: Versatz am Terminal gemessen. 306bbaa: feste Zone wie live_betrieb.py:988."""
    if hasattr(RealMt5Terminal, "messe_serverversatz"):
        terminal = RealMt5Terminal(allow_write=False, uhr=uhr, schlaf=uhr.schlaf)
        terminal._mt5 = attrappe  # type: ignore[assignment]
        terminal.messe_serverversatz("EURUSD")
        return terminal
    from mt5_trading_ai.backtest.kalender import SERVER_TZ_NAME

    terminal = RealMt5Terminal(allow_write=False, server_tz=SERVER_TZ_NAME)  # type: ignore[call-arg]
    terminal._mt5 = attrappe  # type: ignore[assignment]
    return terminal


def _ablagen() -> dict[str, Any]:
    """Fluechtige Ablagen -- aber nur, wo es sie gibt. Gegen 306bbaa (roter Lauf)
    kennt das Paket weder ``FluechtigeSchwebeAkte`` noch ``FluechtigesPositionsbuch``;
    ein Sammel- oder Importfehler waere kein Befund, sondern ein Werkzeugfehler.
    """
    felder = inspect.signature(Mt5Venue.__init__).parameters
    ablagen: dict[str, Any] = {}
    try:
        from mt5_trading_ai.execution.schwebende_auftraege import (
            FluechtigeSchwebeAkte,
        )

        if "schwebeakte" in felder:
            ablagen["schwebeakte"] = FluechtigeSchwebeAkte()
    except ImportError:
        pass
    try:
        from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch

        if "positionsbuch" in felder:
            ablagen["positionsbuch"] = FluechtigesPositionsbuch()
    except ImportError:
        pass
    return ablagen


def _venue(terminal: RealMt5Terminal, uhr: _Uhr) -> Mt5Venue:
    return Mt5Venue(
        name="mt5-d20",
        terminal=terminal,
        catalog={},
        clock=uhr,
        **_ablagen(),
    )


def test_im_us_sommer_eu_winter_fenster_trifft_der_tickstempel_die_echte_utc() -> None:
    """ROT gegen 306bbaa: 13:00 statt 12:00 -- die Zone rechnet noch Winter."""
    uhr = _Uhr(IM_FENSTER)
    terminal = _terminal_wie_im_betrieb(uhr, _Mt5Attrappe(uhr))
    tick = terminal.tick("EURUSD")
    assert tick is not None
    assert tick.ts == uhr.jetzt, f"Tickstempel {tick.ts} liegt neben {uhr.jetzt}"


def test_der_frische_latch_sperrt_im_fenster_keinen_taufrischen_tick() -> None:
    """ROT gegen 306bbaa: ``snapshot_from_future`` (Alter -1 h) fuer einen Tick von
    gerade eben -- der Eintrittspfad steht still, obwohl der Platz druckt."""
    uhr = _Uhr(IM_FENSTER)
    terminal = _terminal_wie_im_betrieb(uhr, _Mt5Attrappe(uhr))
    venue = _venue(terminal, uhr)
    venue._enforce_account_freshness("EURUSD")  # keine Ausnahme = bewertbar


def test_ausserhalb_des_fensters_stimmen_zone_und_messung_ueberein() -> None:
    """Gegenprobe: im Februar sagen beide +2 h -- der rote Fall ist das Fenster, nicht
    die Attrappe."""
    uhr = _Uhr(AUSSERHALB)
    terminal = _terminal_wie_im_betrieb(uhr, _Mt5Attrappe(uhr))
    tick = terminal.tick("EURUSD")
    assert tick is not None
    assert tick.ts == uhr.jetzt
    _venue(terminal, uhr)._enforce_account_freshness("EURUSD")


def test_ein_alter_tick_setzt_keinen_versatz_und_die_eroeffnung_bleibt_abgewiesen() -> (
    None
):
    """HEAD-Fall (Namen erst seit D20): 40 min alter Tick -> ``ServerversatzFehler``,
    ``server_versatz`` bleibt ``None``, der Frische-Latch lehnt ab."""
    from mt5_trading_ai.venue.mt5 import ServerversatzFehler

    uhr = _Uhr(IM_FENSTER)
    attrappe = _Mt5Attrappe(uhr, steht=IM_FENSTER - timedelta(minutes=40))
    terminal = RealMt5Terminal(allow_write=False, uhr=uhr, schlaf=uhr.schlaf)
    terminal._mt5 = attrappe  # type: ignore[assignment]
    with pytest.raises(ServerversatzFehler):
        terminal.messe_serverversatz("EURUSD")
    assert terminal.server_versatz is None
    with pytest.raises(OrderRejectedError) as abgelehnt:
        _venue(terminal, uhr)._enforce_account_freshness("EURUSD")
    # ungedreht (3 h in der Zukunft) und alt (40 min): beides ist nicht bewertbar
    assert abgelehnt.value.reason in {"snapshot_from_future", "snapshot_stale"}
