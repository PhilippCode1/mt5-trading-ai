"""Der Adapter dreht Serverzeit in echtes UTC -- oder er sagt, dass er es nicht tut.

WARUM DIESER TEST
-----------------
MetaTrader liefert Balken- und Positionszeiten so, dass sie **als UTC gelesen die
Server-Ortszeit ergeben**. ``RealMt5Terminal._utc`` haengte darum bis 2026-08-17 das
Etikett ``UTC`` an eine Zeit, die keine ist.

Das ist im Betrieb aufgeflogen, nicht in der Theorie: die Hoechsthaltedauer rechnete
mit Serverzeit und meldete fuer eine 0,77 h alte Position ein Alter von **-2,23 h**.
Die Vier-Stunden-Grenze haette erst nach sieben realen Stunden gefeuert.

Zwei Richtungen sind zu sichern:

* Mit ``server_tz`` **muss** gedreht werden -- und zwar sommerzeitrichtig, weil der
  Versatz zwischen 2 h und 3 h wechselt.
* Ohne ``server_tz`` darf **nicht** gedreht werden. Ein stiller Standardwert waere
  fuer jeden anderen Broker falsch, und ein falscher Versatz ist schlimmer als ein
  bekannter fehlender.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_trading_ai.venue.mt5 import RealMt5Terminal

#: 15.01.2024, 12:00 nach der Wanduhr des Servers.
WINTER = datetime(2024, 1, 15, 12, 0, tzinfo=UTC).timestamp()
#: 15.07.2024, 12:00 nach der Wanduhr des Servers.
SOMMER = datetime(2024, 7, 15, 12, 0, tzinfo=UTC).timestamp()


def test_ohne_serverzone_wird_nicht_gedreht() -> None:
    """Kein stiller Standardwert -- unbekannt bleibt unbekannt."""
    terminal = RealMt5Terminal(allow_write=False)
    assert terminal._utc(WINTER) == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)


def test_mit_serverzone_wird_im_winter_um_zwei_stunden_gedreht() -> None:
    terminal = RealMt5Terminal(allow_write=False, server_tz="Europe/Helsinki")
    assert terminal._utc(WINTER) == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)


def test_mit_serverzone_wird_im_sommer_um_drei_stunden_gedreht() -> None:
    """Derselbe Wanduhrwert ist im Juli eine andere UTC-Zeit. Genau das ist die Falle."""
    terminal = RealMt5Terminal(allow_write=False, server_tz="Europe/Helsinki")
    assert terminal._utc(SOMMER) == datetime(2024, 7, 15, 9, 0, tzinfo=UTC)


def test_die_drehung_folgt_der_eu_umstellung_nicht_der_amerikanischen() -> None:
    """Gemessen: am 10.03.2024 (US) aendert sich nichts, am 31.03.2024 (EU) springt es."""
    terminal = RealMt5Terminal(allow_write=False, server_tz="Europe/Helsinki")
    vor_us = terminal._utc(datetime(2024, 3, 8, 12, 0, tzinfo=UTC).timestamp())
    nach_us = terminal._utc(datetime(2024, 3, 15, 12, 0, tzinfo=UTC).timestamp())
    assert vor_us.hour == nach_us.hour == 10
    nach_eu = terminal._utc(datetime(2024, 4, 2, 12, 0, tzinfo=UTC).timestamp())
    assert nach_eu.hour == 9


def test_das_ergebnis_traegt_immer_utc() -> None:
    """Gedreht oder nicht -- heraus kommt ein zeitzonenbehafteter Stempel in UTC."""
    for tz in (None, "Europe/Helsinki"):
        terminal = RealMt5Terminal(allow_write=False, server_tz=tz)
        assert terminal._utc(SOMMER).tzinfo is UTC


def test_eine_falsche_zone_faellt_beim_bauen_auf_und_nicht_spaeter() -> None:
    """Fail-closed: ein Tippfehler in der Zone darf nicht bis zur ersten Order warten."""
    from zoneinfo import ZoneInfoNotFoundError

    import pytest

    with pytest.raises((ZoneInfoNotFoundError, ValueError, KeyError)):
        RealMt5Terminal(allow_write=False, server_tz="Europa/Helsinki")
