"""Die in Bildung befindliche Kerze muss als solche erkennbar sein (Auftrag K4).

Der Befund: ``copy_rates_range`` liefert bei ``end=jetzt`` die LAUFENDE Kerze mit.
Ihr ``close`` ist der momentane Kurs, kein Schlusskurs. Bis hierher gab es kein Feld,
das den Unterschied ausgedrueckt haette -- der Live-Treiber rechnete seinen gleitenden
Durchschnitt genau auf diesem letzten Element, waehrend der Backtest abgeschlossene
Kerzen aus Dateien liest. Live-Signal und getestetes Signal waren damit nicht dieselbe
Strategie.

Diese Datei fixiert fuenf Dinge:

1. Die laufende Kerze ist ``is_closed=False`` (der rote Eichfall).
2. Eine abgeschlossene Kerze ist ``is_closed=True`` -- sonst waere hier nur alles
   auf False gedreht und der Melder waere per Konstruktion nie gruen.
3. Die Gegenwart kommt vom PLATZ, nicht von der Rechneruhr -- und zwar in BEIDEN
   Versatzrichtungen. Welche Richtung ein Broker erzeugt, haengt an seiner
   Serverzone; ein Eichfall, der nur eine davon kennt, prueft die halbe Aussage.
4. Ohne Platzzeit wird geworfen, und die laufende Kerze wird nicht still entfernt.
5. Eine Zeitebene ohne hinterlegte Intervalllaenge wirft im Vertrag, nicht daneben.

Ein bekannter, bewusst NICHT behobener Mangel ist ebenfalls festgenagelt:
``Timeframe.duration`` ist kalenderblind, D1/H4 gelten ueber einen
Zeitumstellungstag eine Stunde zu frueh als fertig.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from mt5_trading_ai.data.quality import TIMEFRAME_SECONDS
from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.catalog import CatalogEntry
from mt5_trading_ai.venue.mt5 import (
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Terminal,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    Bar,
    FeeSchedule,
    Timeframe,
    TradingSession,
    UnknownInstrumentError,
    VenueError,
    VenueUnavailableError,
)

#: Zeit des letzten Ticks -- die Gegenwart, wie der PLATZ sie kennt. Mitten in der
#: 11:00-Stundenkerze: die 10:00er steht, die 11:00er bildet sich noch.
PLATZZEIT = datetime(2026, 8, 11, 11, 30, tzinfo=UTC)

#: Rechneruhr, die der Platzzeit drei Stunden VORAUS ist. Diese Richtung entsteht bei
#: einem Broker, dessen Server HINTER UTC steht (etwa UTC-3): die Kerzenstempel laufen
#: ungedreht mit dem Etikett UTC durch ``RealMt5Terminal._utc``, tragen also die
#: Serverwanduhr und liegen damit hinter der echten UTC-Systemzeit. Eine Fassung, die
#: ``datetime.now()`` befragt, haelt dann die laufende 11:00-Kerze fuer abgeschlossen
#: (11:00 + 1 h <= 14:30) -- fail-open, unbemerkt. Das ist die gefaehrliche Richtung.
RECHNERUHR_VORAUS = PLATZZEIT + timedelta(hours=3)

#: Rechneruhr, die der Platzzeit drei Stunden NACHGEHT. Das ist die Richtung DIESES
#: Brokers, nachgerechnet: die Serverzone ist ``Europe/Helsinki``
#: (backtest/kalender.py), im Sommer UTC+3, der Server steht also VOR UTC. Ohne
#: ``server_tz`` gibt ``RealMt5Terminal._utc`` die Serverwanduhr unter dem Etikett
#: UTC zurueck -- bei echter UTC 11:30 ist das der Stempel 14:30. Platz- und
#: Kerzenstempel liegen damit drei Stunden VOR der Rechneruhr, nicht dahinter. Eine
#: ``datetime.now()``-Fassung haelt hier umgekehrt jede laengst fertige Kerze fuer
#: laufend und der Live-Takt bliebe stehen: fail-closed statt fail-open. Auch
#: falsch, nur anders herum -- und welche der beiden Richtungen man bekommt,
#: entscheidet der Broker, nicht der Code.
RECHNERUHR_NACHGEHEND = PLATZZEIT - timedelta(hours=3)

#: Serverzone dieses Brokers. Nur fuer die Nachrechnung des Zeitumstellungstags.
SERVER_ZONE = ZoneInfo("Europe/Helsinki")

#: Beginn der D1-Kerze des Rueckstelltags 25.10.2026 (Server-Mitternacht) in echtem
#: UTC. An diesem Tag schaltet Helsinki von EEST auf EET zurueck, der Servertag hat
#: 25 Stunden -- die starren 86400 Sekunden aus ``TIMEFRAME_SECONDS`` reichen nicht.
UMSTELLKERZE_TS = datetime(2026, 10, 24, 21, 0, tzinfo=UTC)


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _symbol() -> Mt5Symbol:
    return Mt5Symbol(
        name="EURUSD",
        digits=5,
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        contract_size=Decimal("100000"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        visible=True,
    )


def _catalog() -> dict[str, CatalogEntry]:
    sessions = tuple(
        TradingSession(weekday=d, open_utc="00:00", close_utc="22:00") for d in range(5)
    )
    return {"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions)}


#: Die drei Kerzen des Regelfalls: 09:00, 10:00 (beide fertig) und die laufende 11:00.
STUNDEN = tuple(datetime(2026, 8, 11, h, 0, tzinfo=UTC) for h in (9, 10, 11))


def _rate(ts: datetime) -> Mt5Rate:
    return Mt5Rate(
        ts=ts,
        open=Decimal("1.10000"),
        high=Decimal("1.10500"),
        low=Decimal("1.09500"),
        close=Decimal("1.10200"),
        tick_volume=100,
    )


class FakeTerminal:
    """Terminal-Naht fuer diesen Test. Nur die Lesepfade sind gefuellt.

    ``tick_ts`` ist der Hebel des Tests: er ist die Zeit, die der PLATZ meldet. Ein
    ``None`` steht fuer den Fall "kein Tick" -- der muss werfen, nicht raten.
    """

    def __init__(
        self,
        *,
        tick_ts: datetime | None = PLATZZEIT,
        zeiten: tuple[datetime, ...] = STUNDEN,
    ) -> None:
        self._connected = False
        self._tick_ts = tick_ts
        self._zeiten = zeiten
        self.tick_calls = 0
        self.symbol_calls = 0

    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (_symbol(),)

    def symbol(self, name: str) -> Mt5Symbol | None:
        self.symbol_calls += 1
        return _symbol() if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        self.tick_calls += 1
        if self._tick_ts is None:
            return None
        return Mt5Tick(ts=self._tick_ts, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        # Absteigend geliefert -- der Adapter sortiert selbst.
        return tuple(_rate(ts) for ts in reversed(self._zeiten))

    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def cancel(self, venue_order_id: str) -> bool:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def positions(self) -> tuple[Mt5Position, ...]:
        return ()

    def account(self) -> Mt5Account:
        return Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=Decimal("10000"),
            is_demo=True,
            ts=PLATZZEIT,
        )


def _venue(terminal: FakeTerminal, *, uhr: datetime = RECHNERUHR_VORAUS) -> Mt5Venue:
    """Ein verbundenes Venue, dessen Rechneruhr bewusst NEBEN der Platzzeit liegt.

    ``clock`` bleibt hier nicht zufaellig ungleich ``PLATZZEIT``: waeren beide gleich,
    liesse sich nicht mehr unterscheiden, welche der beiden Uhren das Urteil traegt.
    """
    venue = Mt5Venue(
        name="mt5-test",
        terminal=terminal,
        catalog=_catalog(),
        clock=lambda: uhr,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    return venue


def _bars(
    terminal: FakeTerminal,
    timeframe: Timeframe = Timeframe.H1,
    *,
    uhr: datetime = RECHNERUHR_VORAUS,
    start: datetime = datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
    end: datetime = datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
) -> tuple[Bar, ...]:
    return _venue(terminal, uhr=uhr).get_bars("EURUSD", timeframe, start=start, end=end)


# --- Roter Eichfall -------------------------------------------------------


def test_laufende_kerze_ist_nicht_abgeschlossen() -> None:
    """DER Eichfall. Gegen die alte Fassung: ``Bar`` hatte kein ``is_closed``.

    Die 11:00-Stundenkerze endet um 12:00, die Platzzeit steht auf 11:30. Ihr
    ``close`` ist der momentane Kurs -- kein Schlusskurs.
    """
    bars = _bars(FakeTerminal())
    assert bars[-1].ts == datetime(2026, 8, 11, 11, 0, tzinfo=UTC)
    assert bars[-1].is_closed is False


def test_abgeschlossene_kerze_gilt_als_abgeschlossen() -> None:
    """Gegenprobe: waere hier nur alles auf False gedreht, faellt dieser Test.

    Die 09:00er und die 10:00er sind um 11:30 vorbei.
    """
    bars = _bars(FakeTerminal())
    assert [bar.is_closed for bar in bars] == [True, True, False]


def test_grenze_zaehlt_als_abgeschlossen() -> None:
    """Genau auf der Intervallgrenze laeuft bereits die naechste Kerze.

    Platzzeit exakt 12:00 -> die 11:00er ist fertig. ``<`` statt ``<=`` haette hier
    eine fertige Kerze eine volle Stunde lang als laufend gefuehrt.
    """
    bars = _bars(FakeTerminal(tick_ts=datetime(2026, 8, 11, 12, 0, tzinfo=UTC)))
    assert [bar.is_closed for bar in bars] == [True, True, True]


def test_platzzeit_entscheidet_nicht_die_vorauseilende_rechneruhr() -> None:
    """Der zweite Eichfall -- gegen die naheliegende falsche Reparatur.

    Die Rechneruhr steht auf 14:30, die Platzzeit auf 11:30. Wer ``datetime.now()``
    oder ``self._clock`` nimmt, rechnet 11:00 + 1 h <= 14:30 und meldet die laufende
    Kerze als abgeschlossen. Genau diese Fehlerklasse -- eine Pruefung, die per
    Konstruktion die falsche Uhr befragt -- hat dieses Repo schon einmal getroffen.

    Diese Versatzrichtung gehoert zu einem Server HINTER UTC. Sie ist die
    gefaehrliche: die laufende Kerze gaelte als fertig, fail-open und unbemerkt.
    """
    terminal = FakeTerminal()
    bars = _bars(terminal, uhr=RECHNERUHR_VORAUS)
    # Rechneruhr saehe: fertig.
    assert RECHNERUHR_VORAUS > bars[-1].ts + Timeframe.H1.duration
    assert bars[-1].is_closed is False  # der Platz sagt: laeuft noch
    assert terminal.tick_calls >= 1  # die Platzzeit wurde wirklich abgefragt


def test_platzzeit_entscheidet_auch_nicht_die_nachgehende_rechneruhr() -> None:
    """Dieselbe Aussage in der Versatzrichtung DIESES Brokers -- der andere Eichfall.

    Der erste Fall allein deckt nur Server hinter UTC ab. Hier steht der Server VOR
    UTC (``Europe/Helsinki``, im Sommer +3 h): ohne ``server_tz`` tragen Kerzen- und
    Tickstempel die Serverwanduhr unter dem Etikett UTC und liegen damit VOR der
    Rechneruhr. Eine ``self._clock``-Fassung rechnet dann ``09:00 + 1 h <= 08:30``,
    haelt also selbst die laengst fertige 09:00-Kerze fuer laufend und liefert
    ``[False, False, False]``. Der Live-Treiber bekaeme nie genug abgeschlossene
    Kerzen und stuende dauerhaft auf FLAT.

    Fail-closed ist die harmlosere Richtung, aber sie ist genauso falsch -- und
    welche der beiden ein Betrieb bekommt, entscheidet der Broker. Ein Eichfall, der
    nur eine Richtung kennt, beweist die halbe Aussage.
    """
    terminal = FakeTerminal()
    bars = _bars(terminal, uhr=RECHNERUHR_NACHGEHEND)
    # Rechneruhr saehe: sogar die erste, laengst fertige Kerze laeuft noch.
    assert RECHNERUHR_NACHGEHEND < bars[0].ts + Timeframe.H1.duration
    assert [bar.is_closed for bar in bars] == [True, True, False]
    assert terminal.tick_calls >= 1


def test_ohne_platzzeit_wird_geworfen_statt_geraten() -> None:
    """Fail-closed. Alte Fassung: lieferte drei Bars, ohne je einen Tick zu brauchen.

    Ohne Tick ist nicht entscheidbar, welche Kerze steht. Nicht entscheidbar faellt
    nicht auf einen Vorgabewert zurueck.
    """
    with pytest.raises(VenueUnavailableError):
        _bars(FakeTerminal(tick_ts=None))


def test_vorpruefung_steht_genau_einmal() -> None:
    """Sitzung und Symbol werden einmal geprueft, nicht zweimal -- ohne Nachlass.

    ``get_bars`` holt die Platzzeit ueber ``get_quote``, und ``get_quote`` prueft
    Sitzung und Symbol bereits selbst, in genau dieser Reihenfolge. Der zusaetzliche
    Vorlauf war dieselbe Regel ein zweites Mal: ein zweiter Terminal-Umlauf je Aufruf
    und zwei Fassungen, die auseinanderlaufen koennen. Gegen die Vorfassung ist die
    Zaehlung rot (zwei Symbolabfragen).

    Weggefallen ist nur die Wiederholung, nicht die Pruefung: beide Sperren muessen
    weiter greifen, darum stehen sie hier mit im Fall.
    """
    terminal = FakeTerminal()
    _bars(terminal)
    assert terminal.symbol_calls == 1

    with pytest.raises(UnknownInstrumentError):
        _venue(FakeTerminal()).get_bars(
            "XAUUSD",
            Timeframe.H1,
            start=datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
            end=datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
        )

    getrennt = _venue(FakeTerminal())
    getrennt.disconnect()
    with pytest.raises(VenueUnavailableError):
        getrennt.get_bars(
            "EURUSD",
            Timeframe.H1,
            start=datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
            end=datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
        )


def test_laufende_kerze_wird_nicht_still_entfernt() -> None:
    """Kennzeichnen, nicht abschneiden.

    Ein stilles Abschneiden der letzten Kerze wuerde die Entscheidung an einen
    zweiten Ort legen, und der naechste Verbraucher wuesste wieder nicht, was er vor
    sich hat. Alle drei Kerzen kommen heraus -- eine davon markiert.
    """
    bars = _bars(FakeTerminal())
    assert len(bars) == 3
    assert [bar.ts.hour for bar in bars] == [9, 10, 11]
    assert sum(1 for bar in bars if not bar.is_closed) == 1


def test_dauer_folgt_der_zeitebene() -> None:
    """Die Intervalllaenge kommt aus der Zeitebene, nicht aus einer festen Stunde.

    Dieselbe 11:00-Kerze bei Platzzeit 11:30: als H1 laeuft sie noch, als M15 ist sie
    laengst vorbei. Eine fest verdrahtete Stunde faellt hier durch.
    """
    assert _bars(FakeTerminal(), Timeframe.H1)[-1].is_closed is False
    assert _bars(FakeTerminal(), Timeframe.M15)[-1].is_closed is True


# --- Der Vertrag selbst ---------------------------------------------------


def test_bar_verlangt_die_auskunft() -> None:
    """``is_closed`` ist Pflichtfeld ohne Vorgabewert.

    Alte Fassung: derselbe Aufruf baute klaglos eine Bar -- und niemand konnte ihr
    ansehen, ob sie steht. Ein Vorgabewert ``True`` waere die schmeichelnde Richtung
    (jede vergessliche Bauweise saehe geprueft aus), ein Vorgabewert ``False`` wuerde
    echte Schlusskerzen falsch etikettieren. Also: keiner.
    """
    felder = {
        "symbol": "EURUSD",
        "timeframe": Timeframe.H1,
        "ts": datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
        "open": Decimal("1.1"),
        "high": Decimal("1.2"),
        "low": Decimal("1.0"),
        "close": Decimal("1.15"),
        "tick_volume": 100,
    }
    with pytest.raises(TypeError):
        Bar(**felder)  # type: ignore[arg-type]
    gebaut = Bar(**felder, is_closed=True)  # type: ignore[arg-type]
    assert gebaut.is_closed is True


def test_jede_zeitebene_hat_eine_dauer() -> None:
    """Eine neue Zeitebene ohne Eintrag wuerde sonst erst live auffallen.

    ``Timeframe.duration`` zieht aus derselben Tabelle, aus der das Qualitaetstor die
    erwartete Bar-Zahl zieht. Dieser Test haelt die beiden zusammen.
    """
    for timeframe in Timeframe:
        assert timeframe.duration > timedelta(0)
    assert Timeframe.H1.duration == timedelta(hours=1)
    assert Timeframe.D1.duration == timedelta(days=1)


def test_fehlende_dauer_bleibt_im_vertrag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roter Eichfall: die Wartungssperre warf ``ValueError`` -- am Vertrag vorbei.

    ``protocol.py`` haelt fest, dass aus dem Handelsplatz ausschliesslich Ableitungen
    von ``VenueError`` kommen, und beide Live-Treiber fangen genau das
    (``except VenueError`` -> Signal FLAT). ``Timeframe.duration`` wird mitten in
    ``get_bars`` ausgewertet: ein ``ValueError`` von dort haette den Live-Takt nicht
    heruntergefahren, sondern abgerissen -- eine Wartungssperre, die den Vertrag
    bricht, den sie schuetzen soll.

    Geprueft wird beides: die Eigenschaft selbst und der Weg durch ``get_bars``, weil
    nur dort der Verbraucher steht.
    """
    monkeypatch.delitem(TIMEFRAME_SECONDS, Timeframe.H1.value)
    with pytest.raises(VenueError):
        _ = Timeframe.H1.duration
    with pytest.raises(VenueError):
        _bars(FakeTerminal())


def test_d1_ueber_die_zeitumstellung_gilt_zu_frueh_als_fertig() -> None:
    """BEKANNTER MANGEL, festgenagelt -- ausdruecklich KEINE Zusicherung.

    ``TIMEFRAME_SECONDS['D1']`` sind starre 86400 Sekunden, die echte Grenze einer
    Tageskerze liegt aber an der Mitternacht des Handelsservers. Am Rueckstelltag
    (25.10.2026, ``Europe/Helsinki``) dauert der Servertag 25 Stunden: die Kerze
    beginnt 21:00 UTC und endet 22:00 UTC am Folgetag. Eine halbe Stunde vor ihrem
    echten Ende sind die starren 24 h laengst abgelaufen -- die noch laufende
    Tageskerze wird als abgeschlossen gemeldet, also in die schmeichelnde Richtung.

    Warum das hier steht statt behoben zu sein: die kalenderbewusste Rechnung braucht
    die Serverzone, und die gehoert nicht in den plattformunabhaengigen Vertrag
    ``venue/protocol.py`` (Modulkopf: kein Plattformname ausserhalb von ``venues/``).
    Sie muesste vom Terminal bis in ``Mt5Venue`` durchgereicht werden. Heute ist kein
    Verbraucher betroffen -- beide Live-Treiber und der Rauchtest holen nur H1, und
    H1 ist immun, weil die Umstellung ein ganzes Vielfaches einer Stunde ist.

    Wer den Mangel behebt, macht diesen Test rot. Das ist beabsichtigt: dann sind
    der Docstring bei ``Timeframe.duration`` und dieser Fall gemeinsam zu loeschen.
    """
    echtes_ende = datetime(2026, 10, 26, 0, 0, tzinfo=SERVER_ZONE).astimezone(UTC)
    assert echtes_ende - UMSTELLKERZE_TS == timedelta(hours=25)  # kein 24-h-Tag
    assert UMSTELLKERZE_TS + Timeframe.D1.duration < echtes_ende  # eine Stunde zu kurz

    kurz_vor_schluss = echtes_ende - timedelta(minutes=30)
    bars = _bars(
        FakeTerminal(tick_ts=kurz_vor_schluss, zeiten=(UMSTELLKERZE_TS,)),
        Timeframe.D1,
        start=UMSTELLKERZE_TS,
        end=kurz_vor_schluss,
    )
    # Richtig waere hier False: die Kerze laeuft noch dreissig Minuten.
    assert bars[-1].is_closed is True


def test_fake_erfuellt_die_terminal_naht() -> None:
    assert isinstance(FakeTerminal(), Mt5Terminal)
