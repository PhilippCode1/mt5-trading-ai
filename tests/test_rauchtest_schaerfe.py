"""Der Rauchtest meldete, dass er gelaufen ist -- jetzt meldet er, was er gesehen hat.

Fuenf Schritte von ``run_smoke`` trugen ein hart gesetztes ``True``: ``account``,
``get_instrument``, ``get_bars``, ``is_trading_open`` und ``adopt_book``. Sie konnten
per Konstruktion nicht rot werden. Ein Rauchtest, dessen Schritte immer gruen sind, ist
keine Vorbedingung fuer ``allow_write``, sondern eine Quittung.

Dazu zwei Stellen, an denen die Harness bisher etwas verschwieg:

* ``list_instruments`` schluckte jeden Katalogeintrag, den der Adapter nicht aufloest
  (``except UnknownInstrumentError: continue``). Das Universum schrumpfte lautlos.
* Die Schreib-Probe lief in den Doppelorder-Riegel, wenn auf dem Probesymbol schon ein
  Long stand -- und meldete das als ``doppelte_eroeffnung``, also wie einen Fehler des
  Adapters statt wie die Kontolage, die es ist.

Jeder Fall unten misst BEIDE Richtungen: die Sperre loest aus, und im gesunden Lauf
loest sie nicht aus (``test_der_gesunde_lauf_bleibt_gruen``).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.mt5 import (
    CatalogEntry,
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5Symbol,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    Timeframe,
    UnknownInstrumentError,
)
from mt5_trading_ai.venue.smoke import run_smoke

from test_mt5_venue import (
    TS,
    FakeMt5Terminal,
    _catalog,
    _fees,
    _mt5_position,
)

#: TS ist Dienstag, der 2026-08-11. Von Hand vier Tage weiter: 12. Mi, 13. Do, 14. Fr,
#: 15. Sa. Der Katalog des Vertragstests fuehrt Sitzungen fuer die Wochentage 0..4
#: (Mo-Fr), also deckt er den Samstag nicht.
SAMSTAG = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _venue(terminal: FakeMt5Terminal, *, catalog: object | None = None) -> Mt5Venue:
    return Mt5Venue(
        name="mt5-demo",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=catalog if catalog is not None else _catalog(),  # type: ignore[arg-type]
        risk_manager=RiskManager(zustand=FluechtigerZustand()),
        clock=lambda: TS,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )


def _schritt(report: object, name: str) -> object:
    return next(s for s in report.steps if s.name == name)  # type: ignore[attr-defined]


def test_der_gesunde_lauf_bleibt_gruen() -> None:
    """Die Gegenprobe zu allem Folgenden: die geschaerften Schritte sind keine
    Dauerbremse. Ein sauberes Demokonto am offenen Markt faehrt durch."""
    report = run_smoke(_venue(FakeMt5Terminal(is_demo=True)), symbol="EURUSD", now=TS)
    assert report.ok is True
    for name in (
        "account",
        "get_instrument",
        "get_bars",
        "is_trading_open",
        "adopt_book",
    ):
        assert _schritt(report, name).ok is True  # type: ignore[attr-defined]


# --- account: ein leergelaufenes Konto ist kein Beweisplatz ---------------


class _LeeresKonto(FakeMt5Terminal):
    def account(self) -> Mt5Account:
        konto = super().account()
        return Mt5Account(
            account_id=konto.account_id,
            currency=konto.currency,
            balance=Decimal("0"),
            equity=Decimal("0"),
            margin_used=Decimal("0"),
            margin_free=Decimal("0"),
            is_demo=konto.is_demo,
            ts=konto.ts,
        )


def test_ein_konto_ohne_eigenkapital_faellt_auf() -> None:
    """Equity 0 heisst: hier laesst sich nichts mehr eroeffnen und nichts beweisen.
    Der Schritt trug frueher ``True`` und meldete die Null nur im Klartext daneben."""
    report = run_smoke(_venue(_LeeresKonto(is_demo=True)), symbol="EURUSD", now=TS)
    assert _schritt(report, "account").ok is False  # type: ignore[attr-defined]
    assert report.ok is False


# --- get_instrument: was die Schreib-Probe braucht ------------------------


class _UnsichtbaresSymbol(FakeMt5Terminal):
    def symbol(self, name: str) -> Mt5Symbol | None:
        roh = super().symbol(name)
        if roh is None or name != "EURUSD":
            return roh
        return Mt5Symbol(
            name=roh.name,
            digits=roh.digits,
            tick_size=roh.tick_size,
            pip_size=roh.pip_size,
            contract_size=roh.contract_size,
            volume_min=roh.volume_min,
            volume_step=roh.volume_step,
            volume_max=roh.volume_max,
            base_currency=roh.base_currency,
            quote_currency=roh.quote_currency,
            stop_level_points=roh.stop_level_points,
            freeze_level_points=roh.freeze_level_points,
            visible=False,
        )


def test_ein_symbol_ausserhalb_des_marketwatch_faellt_auf() -> None:
    """Ein Symbol, das der Broker nicht sichtbar fuehrt, ist nicht handelbar -- und
    genau darauf soll der Rauchtest die Schreibfreigabe stuetzen."""
    report = run_smoke(
        _venue(_UnsichtbaresSymbol(is_demo=True)), symbol="EURUSD", now=TS
    )
    assert _schritt(report, "get_instrument").ok is False  # type: ignore[attr-defined]
    assert report.ok is False


# --- get_bars: null Bars ist eine Fehlanzeige -----------------------------


class _OhneBars(FakeMt5Terminal):
    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return ()


def test_drei_tage_ohne_eine_einzige_kerze_faellt_auf() -> None:
    """Ueber drei Tage H1 muss mindestens eine Kerze kommen. Null Bars meldete der
    Schritt frueher als Erfolg -- mit ``0 Bars`` im Klartext daneben."""
    report = run_smoke(_venue(_OhneBars(is_demo=True)), symbol="EURUSD", now=TS)
    bars = _schritt(report, "get_bars")
    assert bars.ok is False  # type: ignore[attr-defined]
    assert "0 Bars" in bars.detail  # type: ignore[attr-defined]
    assert report.ok is False


# --- is_trading_open: der Schritt traegt die Antwort ----------------------


def test_ein_lauf_am_geschlossenen_platz_ist_nicht_gruen() -> None:
    """Am Samstag ist der Platz zu, und ein Lauf am zu-en Platz belegt die
    Schreibfaehigkeit nicht. Vorher stand ``True`` im Schritt und ``False`` im Text
    daneben -- der Bericht war gruen und sagte das Gegenteil.

    Die Uhr des Venues bleibt bei TS, der Kursstempel ist also frisch: rot wird der
    Schritt allein am Sitzungsfenster, nicht an der Frische.

    Seit 2026-09-05 darf der Text hinter dem ``False`` den Grund nennen (Wochenende
    statt haengendes Terminal, siehe ``_platz_geschlossen``). Die Zusicherung ist
    unveraendert und steht hier ausdruecklich: der Schritt ist rot, der Lauf ist rot,
    und der Text beginnt mit derselben Antwort -- er darf ihr nie widersprechen.
    """
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True)), symbol="EURUSD", now=SAMSTAG
    )
    offen = _schritt(report, "is_trading_open")
    assert offen.ok is False  # type: ignore[attr-defined]
    assert offen.detail.startswith("False")  # type: ignore[attr-defined]
    assert "True" not in offen.detail  # type: ignore[attr-defined]
    assert report.ok is False


# --- adopt_book: das Buch muss die Meldung abbilden -----------------------


def test_eine_gegenlaeufige_paarung_verschwindet_nicht_still_aus_dem_buch() -> None:
    """Ein Long und ein gleich grosser Short im selben Symbol (Hedging-Konto).

    ``positions_to_net`` wirft Symbole mit Nettomenge null weg -- das uebernommene Buch
    ist danach leer, obwohl der Broker zwei offene Tickets meldet. Auch ``reconcile``
    sieht nichts, weil es beide Seiten gleich netzt. Der Rauchtest ist die einzige
    Stelle, die die beiden Sichten nebeneinanderlegt; frueher trug sie ein hartes
    ``True`` und meldete "0 Symbole im Buch" als Erfolg.
    """
    positionen: tuple[Mt5Position, ...] = (
        _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.01"), ticket="t1"),
        _mt5_position("EURUSD", is_buy=False, volume=Decimal("0.01"), ticket="t2"),
    )
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True, positions=positionen)),
        symbol="EURUSD",
        now=TS,
    )
    buch = _schritt(report, "adopt_book")
    assert buch.ok is False  # type: ignore[attr-defined]
    assert "0 Symbole im Buch, 1 gemeldet" in buch.detail  # type: ignore[attr-defined]
    assert report.ok is False


def test_eine_einseitige_position_landet_sehr_wohl_im_buch() -> None:
    """Gegenprobe: der Abgleich ist keine Dauerbremse."""
    positionen: tuple[Mt5Position, ...] = (
        _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.01"), ticket="t1"),
    )
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True, positions=positionen)),
        symbol="EURUSD",
        now=TS,
    )
    assert _schritt(report, "adopt_book").ok is True  # type: ignore[attr-defined]


# --- list_instruments: kein stiller Abgang aus dem Universum --------------


def _katalog_mit_fremdsymbol() -> dict[str, CatalogEntry]:
    """Der Katalog fuehrt ein Symbol, das dieses Terminal nicht kennt -- der Alltagsfall
    einer Broker-Umstellung (Suffixe je Kontotyp, fehlender MarketWatch-Eintrag)."""
    katalog = _catalog()
    katalog["GBPUSD"] = CatalogEntry(
        AssetClass.FX_MAJOR, _fees(), _catalog()["EURUSD"].sessions
    )
    return katalog


def test_ein_unaufloesbarer_katalogeintrag_verschwindet_nicht_still() -> None:
    """Frueher lieferte ``list_instruments`` schweigend zwei statt drei Instrumente.

    Der Rueckgabetyp hat keinen Platz fuer eine Nebenmeldung -- also gibt es nur die
    vollstaendige Liste oder einen Fehler. Der Name des fehlenden Symbols muss in der
    Meldung stehen, sonst ist die Ablehnung nicht bedienbar.
    """
    venue = _venue(FakeMt5Terminal(is_demo=True), catalog=_katalog_mit_fremdsymbol())
    venue.connect()
    with pytest.raises(UnknownInstrumentError) as ex:
        venue.list_instruments()
    assert "GBPUSD" in str(ex.value)


def test_der_vollstaendige_katalog_wird_weiterhin_geliefert() -> None:
    """Gegenprobe: der Vertragstest-Katalog fuehrt EURUSD und BTCUSD, beide kennt das
    Fake-Terminal -- also kommen genau zwei Instrumente heraus."""
    venue = _venue(FakeMt5Terminal(is_demo=True))
    venue.connect()
    instrumente = venue.list_instruments()
    assert {i.symbol for i in instrumente} == {"EURUSD", "BTCUSD"}


def test_der_rauchtest_meldet_den_fehlenden_katalogeintrag() -> None:
    """Und derselbe Befund kommt im Bericht an, statt in einer stillen Zahl."""
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), catalog=_katalog_mit_fremdsymbol()),
        symbol="EURUSD",
        now=TS,
    )
    assert report.ok is False
    fehler = _schritt(report, "error")
    assert "GBPUSD" in fehler.detail  # type: ignore[attr-defined]


# --- Schreib-Probe: die Vorbedingung wird vorher gesagt -------------------


def test_die_schreibprobe_sagt_den_bestand_vorher_statt_in_den_riegel_zu_laufen() -> (
    None
):
    """Steht auf dem Probesymbol schon ein Long, waere die Probe eine zweite
    gleichgerichtete Position -- der Doppelorder-Riegel lehnt sie ab.

    Der Fall ist nicht konstruiert: der Live-Treiber faehrt auf demselben Demokonto,
    und ein ``smoke-close``, der einmal nicht durchkam, hinterlaesst genau diesen
    Bestand. Beide Wege sind rot -- an der Sperre wird nichts gelockert --, aber nur
    dieser sagt dem Betreiber, was zu tun ist. Und es wird **gar nichts gesendet**.
    """
    positionen: tuple[Mt5Position, ...] = (
        _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.01"), ticket="t1"),
    )
    terminal = FakeMt5Terminal(is_demo=True, positions=positionen)
    report = run_smoke(_venue(terminal), symbol="EURUSD", allow_write=True, now=TS)

    probe = _schritt(report, "write_probe")
    assert probe.ok is False  # type: ignore[attr-defined]
    assert "t1" in probe.detail  # type: ignore[attr-defined]
    assert "glattstellen" in probe.detail  # type: ignore[attr-defined]
    assert "doppelte_eroeffnung" not in probe.detail  # type: ignore[attr-defined]
    assert terminal.order_send_calls == 0
    assert "write_open" not in [s.name for s in report.steps]
    assert report.ok is False


def test_ein_gegenlaeufiger_bestand_haelt_die_schreibprobe_nicht_auf() -> None:
    """Gegenprobe: die Vorpruefung fragt nach der Seite, nicht nach dem Symbol.

    Ein offener Short auf dem Probesymbol ist fuer den Doppelorder-Riegel kein Grund,
    also darf er es auch fuer die Vorpruefung nicht sein -- sonst waere die Harness
    strenger als das Tor, das sie abbilden soll, und niemand fuende heraus, warum.
    """
    positionen: tuple[Mt5Position, ...] = (
        _mt5_position("EURUSD", is_buy=False, volume=Decimal("0.50"), ticket="t9"),
    )
    terminal = FakeMt5Terminal(is_demo=True, positions=positionen)
    report = run_smoke(_venue(terminal), symbol="EURUSD", allow_write=True, now=TS)

    namen = [s.name for s in report.steps]
    assert "write_open" in namen
    assert terminal.order_send_calls > 0


def test_ohne_schreibfreigabe_wird_der_bestand_nicht_geprueft() -> None:
    """Ein rein lesender Lauf darf an einem offenen Long nicht scheitern -- er
    eroeffnet ja nichts."""
    positionen: tuple[Mt5Position, ...] = (
        _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.01"), ticket="t1"),
    )
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True, positions=positionen)),
        symbol="EURUSD",
        now=TS,
    )
    probe = _schritt(report, "write_probe")
    assert probe.ok is True  # type: ignore[attr-defined]
    assert "uebersprungen" in probe.detail  # type: ignore[attr-defined]


def test_das_sitzungsfenster_deckt_den_samstag_wirklich_nicht() -> None:
    """Die Rechnung hinter ``SAMSTAG``, damit der Fall oben nicht auf einer falsch
    abgezaehlten Konstante steht: TS ist ein Dienstag (weekday 1), SAMSTAG vier Tage
    spaeter ein Samstag (weekday 5), und der Katalog fuehrt nur 0..4."""
    assert TS.weekday() == 1
    assert SAMSTAG - TS == timedelta(days=4)
    assert SAMSTAG.weekday() == 5
    assert {s.weekday for s in _catalog()["EURUSD"].sessions} == {0, 1, 2, 3, 4}


# --- geschlossener Platz vs. haengendes Terminal --------------------------


class _StehenderStrom(FakeMt5Terminal):
    """Der Kursstrom steht: derselbe Tick, beliebig alt (Wochenende oder Defekt)."""

    def __init__(self, *, alter: timedelta, **kw: object) -> None:
        super().__init__(**kw)  # type: ignore[arg-type]
        self._alter = alter

    def tick(self, name: str) -> object:
        roh = super().tick(name)
        if roh is None:
            return None
        return dataclasses.replace(roh, ts=TS - self._alter)


def test_der_geschlossene_platz_steht_im_text_und_bleibt_trotzdem_rot() -> None:
    """A9 am Wochenende: der Kursstrom steht, und das ist die richtige Antwort des
    Marktes -- kein Defekt am Terminal. Gruen wird der Lauf davon NICHT: ein Lauf am
    geschlossenen Platz belegt den Platz nicht (siehe
    ``test_ein_lauf_am_geschlossenen_platz_ist_nicht_gruen``). Was sich aendert, ist
    der Text: er nennt beide Belege, damit ein Wochenende nicht wie ein haengendes
    Terminal aussieht.
    """
    venue = _venue(_StehenderStrom(alter=timedelta(hours=16), is_demo=True))

    report = run_smoke(venue, symbol="EURUSD", now=SAMSTAG)

    offen = _schritt(report, "is_trading_open")
    assert offen.ok is False  # type: ignore[attr-defined]
    assert "Sitzungstabelle deckt" in offen.detail  # type: ignore[attr-defined]
    assert "h alt" in offen.detail  # type: ignore[attr-defined]
    assert report.ok is False


def test_am_offenen_platz_nennt_der_text_keinen_geschlossenen_platz() -> None:
    """Die Gegenprobe, ohne die der Text eine Ausrede waere: dieselbe stehende Lage,
    aber die Sitzungstabelle sagt offen -- dann ist der Grund NICHT 'geschlossen'.
    """
    venue = _venue(_StehenderStrom(alter=timedelta(hours=16), is_demo=True))

    report = run_smoke(venue, symbol="EURUSD", now=TS)

    offen = _schritt(report, "is_trading_open")
    assert offen.ok is False  # type: ignore[attr-defined]
    assert offen.detail == "False", offen.detail  # type: ignore[attr-defined]
