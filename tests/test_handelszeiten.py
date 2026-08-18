"""E8 -- der Handelszeitfilter war eine vereinfachte FX-Woche fuer alle Klassen.

WARUM DIESER TEST
-----------------
``Mt5Venue.is_trading_open`` bestand aus elf Zeilen mit vier Maengeln:

1. Die Wanduhr wurde ohne Zonenpruefung gelesen. Ein naiver ``at`` lieferte einen
   geratenen Wochentag und eine geratene Stunde -- und ein Ergebnis, das aussieht wie
   eine Marktaussage.
2. ``open_min <= x < close_min`` innerhalb EINES Wochentags. Eine Sitzung ueber
   Mitternacht ist so nicht ausdrueckbar; die Bedingung ``22:00 <= x < 06:00`` ist
   fuer kein ``x`` wahr.
3. EURUSD, GBPUSD, USDJPY, EURGBP, XAUUSD **und US500** teilten im Katalog dieselbe
   Zeile Mo-Fr 00:00-21:00.
4. Feiertage kamen nicht vor.

Die harmlose Fehlrichtung ist, dass der Filter reale Handelszeit wegschneidet. Die
gefaehrliche ist die andere: **"offen", waehrend der Platz zu ist** -- US500 nachts,
alles an Weihnachten.

WAS ANSTELLE DESSEN GEPRUEFT WIRD
---------------------------------
Zwei Bedingungen, beide notwendig: das Sitzungsfenster aus dem Katalog (das darf nur
verengen, weil es unbelegt ist) UND ein frischer Kursstempel des Brokers (der ist die
Messung: ein geschlossener Platz druckt keine Preise). Damit ist die gefaehrliche
Richtung geschlossen, ohne dass irgendwo eine Handelszeit erfunden oder ein
Feiertagskalender gepflegt werden muesste.

MESSUNG GEGEN HEAD
------------------
Die Datei importiert nur Namen, die es in BEIDEN Fassungen gibt, damit sie gegen HEAD
sammelt und mit echten Assertions faellt statt mit einem ImportError.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.venue.catalog import CatalogEntry  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AssetClass,
    FeeSchedule,
    Timeframe,
    TradingSession,
)

#: Ein Dienstag, 12:00 UTC -- mitten in jeder denkbaren Sitzung.
DIENSTAG = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
#: Der erste Weihnachtsfeiertag 2026 faellt auf einen Freitag. Ein Werktag im
#: Sitzungsfenster, an dem trotzdem kein Platz handelt -- genau die Kante, die eine
#: Wochentagstabelle nicht kennen kann.
WEIHNACHTEN = datetime(2026, 12, 25, 12, 0, tzinfo=UTC)


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _symbol(name: str) -> Mt5Symbol:
    return Mt5Symbol(
        name=name,
        digits=5,
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        contract_size=Decimal("100000"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency=name[:3],
        quote_currency=name[3:],
        stop_level_points=10,
        freeze_level_points=0,
        visible=True,
    )


class _Terminal:
    """Ein Terminal, dessen Kursstempel je Symbol frei setzbar ist.

    Der Stempel ist die einzige Groesse, um die es hier geht: er kommt von der anderen
    Seite der Leitung und ist das einzige Lebenszeichen, das nicht im eigenen Prozess
    entsteht.
    """

    def __init__(self, stempel: dict[str, datetime | None]) -> None:
        self._stempel = stempel
        self._verbunden = False

    def initialize(self) -> bool:
        self._verbunden = True
        return True

    def shutdown(self) -> None:
        self._verbunden = False

    def is_connected(self) -> bool:
        return self._verbunden

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return tuple(_symbol(name) for name in self._stempel)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return _symbol(name) if name in self._stempel else None

    def tick(self, name: str) -> Mt5Tick | None:
        ts = self._stempel.get(name)
        if ts is None:
            return None
        return Mt5Tick(ts=ts, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return ()

    def order_send(self, request: object) -> Mt5SendResult:
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
            ts=DIENSTAG,
        )


def _venue(
    *,
    sessions: tuple[TradingSession, ...] | None = None,
    stempel: dict[str, datetime | None] | None = None,
    clock: Callable[[], datetime] | None = None,
    jetzt: datetime | None = None,
) -> Mt5Venue:
    """Ein Venue mit gestellten Kursstempeln.

    ``jetzt`` ist die Uhr DES VENUES -- die Gegenwart, gegen die der Kursstempel
    gemessen wird. Sie ist bewusst getrennt vom ``at`` des Aufrufers: die Tabelle
    beantwortet eine Frage ueber ``at``, die Messung eine ueber jetzt. Wer beides
    gleichsetzt, kann den Befund nicht sehen, an dem der Eintrittspfad gestorben ist.
    """
    fenster = (
        sessions
        if sessions is not None
        else tuple(
            TradingSession(weekday=tag, open_utc="00:00", close_utc="21:00")
            for tag in range(5)
        )
    )
    stempel = stempel if stempel is not None else {"EURUSD": DIENSTAG}
    katalog: dict[str, CatalogEntry] = {
        name: CatalogEntry(AssetClass.FX_MAJOR, _fees(), fenster) for name in stempel
    }
    terminal = _Terminal(stempel)
    if clock is None:
        uhr = jetzt if jetzt is not None else DIENSTAG
        clock = lambda: uhr  # noqa: E731 - eine feste Uhr, kein Verhalten
    venue = Mt5Venue(
        name="mt5-test",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=katalog,
        clock=clock,
    )
    venue.connect()
    return venue


# =========================================================================== #
# Die gefaehrliche Richtung: "offen", waehrend der Platz zu ist                #
# =========================================================================== #
def test_stehender_kursstrom_ist_nicht_offen() -> None:
    """DER ROTE EICHFALL VON E8.

    Ein Werktag mitten im Sitzungsfenster -- und ein Kursstempel von vor zwei
    Stunden. Der Platz handelt nicht; die Tabelle kann das nicht wissen, weil in ihr
    nur Wochentage stehen. Gegen HEAD lautete die Antwort ``True``, weil ueberhaupt
    nur die Tabelle gefragt wurde.
    """
    venue = _venue(stempel={"EURUSD": DIENSTAG - timedelta(hours=2)})
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is False, (
        "Der letzte Kurs ist zwei Stunden alt -- der Platz druckt keine Preise. "
        "'Offen' ist hier die gefaehrlichste Antwort, die der Filter geben kann."
    )


def test_feiertag_faellt_am_kursstrom_auf() -> None:
    """Weihnachten auf einem Werktag -- die Wochentagstabelle sagt offen.

    Der Filter kennt keinen Feiertagskalender und soll auch keinen bekommen: ein
    geschlossener Platz druckt keine Preise, und das ist die genauere Messung. Gegen
    HEAD war der 25.12. ein Freitag wie jeder andere.
    """
    venue = _venue(
        stempel={"EURUSD": WEIHNACHTEN - timedelta(hours=12)}, jetzt=WEIHNACHTEN
    )
    assert venue.is_trading_open("EURUSD", at=WEIHNACHTEN) is False


def test_ohne_kurs_kein_offener_platz() -> None:
    """Kein Tick = kein Beleg = zu. Nicht bewertbar heisst nicht erfuellt."""
    venue = _venue(stempel={"EURUSD": None})
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is False


def test_getrennte_leitung_ist_kein_offener_platz() -> None:
    """Ueber eine tote Leitung ist ueber den Zustand des Platzes nichts auszusagen."""
    venue = _venue()
    venue.disconnect()
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is False


def test_kurs_aus_der_zukunft_belegt_nichts() -> None:
    """Ein Stempel jenseits der Toleranz in der Zukunft ist ebenso wenig bewertbar.

    Er entsteht durch einen Uhrensprung oder durch einen Serverversatz, den niemand
    kennt -- und dann ist das Alter des Kurses nicht messbar.
    """
    venue = _venue(stempel={"EURUSD": DIENSTAG + timedelta(minutes=5)})
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is False


def test_fremdes_symbol_haelt_den_platz_nicht_offen() -> None:
    """Gemessen wird der Strom DES gefragten Symbols, nicht irgendeiner.

    Ein frischer EURUSD-Tick sagt nichts ueber einen eingefrorenen US500-Strom -- und
    genau diese beiden teilten sich im Katalog dieselbe Sitzungszeile.
    """
    venue = _venue(
        stempel={"EURUSD": DIENSTAG, "US500": DIENSTAG - timedelta(hours=6)}
    )
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is True
    assert venue.is_trading_open("US500", at=DIENSTAG) is False


# =========================================================================== #
# Die Zonenkante                                                              #
# =========================================================================== #
def test_naiver_zeitpunkt_wird_nicht_geraten() -> None:
    """Ein naiver Stempel macht Wochentag und Stunde zu geratenen Groessen.

    Gegen HEAD lief ``at.weekday()`` und ``at.hour`` klaglos durch -- das Ergebnis
    sah aus wie eine Marktaussage und war eine Wette auf die Zone des Aufrufers.
    Ein stilles ``False`` waere hier die schlechtere Antwort als ein Fehler:
    "geschlossen" ist eine gueltige Marktaussage, und ein Aufruferfehler, der sich
    als dauerhaft geschlossener Markt tarnt, findet sich nie.
    """
    venue = _venue()
    with pytest.raises(ValueError):
        venue.is_trading_open("EURUSD", at=DIENSTAG.replace(tzinfo=None))


def test_zeitpunkt_in_fremder_zone_wird_umgerechnet() -> None:
    """Eine Zone mit Versatz wird gerechnet, nicht verworfen.

    Gegenprobe zur Zonenkante: der Filter darf nicht einfach alles ablehnen, was
    nicht UTC ist. 21:30 in UTC+9 ist 12:30 UTC -- mitten in der Sitzung.
    """
    tokio = DIENSTAG.astimezone(timezone(timedelta(hours=9))).replace(
        hour=21, minute=30
    )
    venue = _venue(
        stempel={"EURUSD": tokio.astimezone(UTC)}, jetzt=tokio.astimezone(UTC)
    )
    assert venue.is_trading_open("EURUSD", at=tokio) is True


# =========================================================================== #
# Zwei Zeiten, zwei Fragen -- die Uhr der Messung gehoert dem Venue            #
# =========================================================================== #
def test_der_eingefrorene_zeitpunkt_des_aufrufers_bremst_nicht() -> None:
    """DER ROTE EICHFALL DER ZWEITEN FASSUNG -- die Sperre schloss IMMER.

    So faehrt der reale Aufrufer: ``tools/live_betrieb.py`` friert
    ``jetzt = datetime.now(UTC)`` am Kopf des Taktes ein und fragt erst danach
    ``is_trading_open(symbol, at=jetzt)``. Dazwischen liegen ein Kontoabruf, eine
    Positionsliste, ein ``get_quote`` je Symbol, der Buchabgleich, die Notbremse und
    je offener Position ein ``get_bars`` ueber 360 Stunden -- Sekunden, keine
    Millisekunden.

    Der Tick dagegen wird in diesem Aufruf frisch geholt. Gemessen gegen den
    eingefrorenen Zeitpunkt ist er damit ein Stempel aus der ZUKUNFT, und jenseits
    von ``FUTURE_TOLERANCE`` (1 s) lautete das Urteil ``snapshot_from_future``.
    Gegen HEAD steht hier ``False``: der Eintrittspfad war still, aus einem Grund,
    der mit dem Zustand des Marktes nichts zu tun hat.

    Eine Sperre, die immer schliesst, ist genauso kaputt wie eine, die nie
    schliesst -- sie wird nur nicht bemerkt, sondern abgeschaltet.
    """
    drei_sekunden_vorher = DIENSTAG - timedelta(seconds=3)
    venue = _venue(stempel={"EURUSD": DIENSTAG}, jetzt=DIENSTAG)

    assert venue.is_trading_open("EURUSD", at=drei_sekunden_vorher) is True, (
        "Der Aufrufer hat seinen Zeitpunkt drei Sekunden vorher genommen, der Kurs "
        "ist taufrisch -- und der Platz gilt als geschlossen. Das ist keine "
        "Marktaussage, das ist eine Dauerbremse."
    )


def test_ein_alter_kurs_bleibt_zu_auch_bei_frischem_at() -> None:
    """Gegenprobe zur Uhr: die Messung wird dadurch nicht weicher.

    Der Aufrufer reicht die Gegenwart ein, der Kurs ist zehn Minuten alt. Waere die
    Uhr des Aufrufers massgeblich, koennte er mit einem alten ``at`` einen alten Kurs
    frisch rechnen -- die Sperre haette einen Ausgang, den der Aufrufer stellt.
    """
    venue = _venue(
        stempel={"EURUSD": DIENSTAG - timedelta(minutes=10)}, jetzt=DIENSTAG
    )
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is False
    assert (
        venue.is_trading_open("EURUSD", at=DIENSTAG - timedelta(minutes=10)) is False
    ), (
        "Ein zum Kursstempel passend gewaehltes ``at`` darf die Frischemessung nicht "
        "gruen rechnen -- gemessen wird gegen die Uhr des Venues."
    )


def test_die_frist_ist_dieselbe_wie_am_frische_latch() -> None:
    """Die Zusage im Docstring: was hier durchgeht, wird zwei Zeilen spaeter geprueft.

    Sie haelt nur, wenn beide gegen dieselbe Uhr messen. Vorher rechnete
    ``is_trading_open`` gegen ``at`` und ``_enforce_account_freshness`` gegen
    ``self._clock()`` -- gleiche Frist, verschiedene Uhr, also genau die
    auseinanderlaufende Kopie, deren Vermeidung die Begruendung ist.
    """
    from mt5_trading_ai.execution.freshness import MAX_SNAPSHOT_AGE

    knapp_drin = DIENSTAG - MAX_SNAPSHOT_AGE + timedelta(seconds=1)
    knapp_drueber = DIENSTAG - MAX_SNAPSHOT_AGE - timedelta(seconds=1)

    assert (
        _venue(stempel={"EURUSD": knapp_drin}, jetzt=DIENSTAG).is_trading_open(
            "EURUSD", at=DIENSTAG
        )
        is True
    )
    assert (
        _venue(stempel={"EURUSD": knapp_drueber}, jetzt=DIENSTAG).is_trading_open(
            "EURUSD", at=DIENSTAG
        )
        is False
    )


# =========================================================================== #
# Die Sitzung ueber Mitternacht                                               #
# =========================================================================== #
def test_sitzung_ueber_mitternacht_ist_ausdrueckbar() -> None:
    """DER ROTE EICHFALL DER SITZUNGSGRENZE.

    Ein Fenster Montag 22:00 bis Dienstag 06:00. Gegen HEAD war die Bedingung
    ``22:00 <= x < 06:00`` fuer KEIN ``x`` wahr -- die Sitzung existierte schlicht
    nicht, und der Filter meldete rund um die Uhr geschlossen.
    """
    fenster = (TradingSession(weekday=0, open_utc="22:00", close_utc="06:00"),)
    nachts = datetime(2026, 8, 11, 3, 0, tzinfo=UTC)  # Dienstag 03:00
    venue = _venue(sessions=fenster, stempel={"EURUSD": nachts}, jetzt=nachts)
    assert venue.is_trading_open("EURUSD", at=nachts) is True


def test_sitzung_ueber_mitternacht_endet_auch_wieder() -> None:
    """Gegenprobe: das Fenster darf nicht einfach bis in alle Ewigkeit gelten."""
    fenster = (TradingSession(weekday=0, open_utc="22:00", close_utc="06:00"),)
    danach = datetime(2026, 8, 11, 6, 30, tzinfo=UTC)  # Dienstag 06:30
    venue = _venue(sessions=fenster, stempel={"EURUSD": danach}, jetzt=danach)
    assert venue.is_trading_open("EURUSD", at=danach) is False


def test_sitzung_ueber_die_wochengrenze_deckt_den_montagmorgen() -> None:
    """Sonntag 22:00 bis Montag 06:00 -- das Fenster laeuft ueber den Wochenwechsel.

    Genau so oeffnet die FX-Woche. Gegen HEAD war auch das nicht ausdrueckbar.
    """
    fenster = (TradingSession(weekday=6, open_utc="22:00", close_utc="06:00"),)
    montag = datetime(2026, 8, 10, 2, 0, tzinfo=UTC)  # Montag 02:00
    venue = _venue(sessions=fenster, stempel={"EURUSD": montag}, jetzt=montag)
    assert venue.is_trading_open("EURUSD", at=montag) is True


def test_tagesschluss_um_vierundzwanzig_uhr_laesst_kein_loch() -> None:
    """``24:00`` schliesst den Tag ab, ohne die letzte Minute zu verlieren.

    Der Katalog fuehrte BTCUSD mit ``23:59`` als Tagesschluss -- eine Minute Loch
    pro Nacht in einem Strom, der laut derselben Zeile sieben Tage laeuft. Das war
    kein Datenstand, sondern ein Ausdrucksmangel.
    """
    fenster = (TradingSession(weekday=1, open_utc="00:00", close_utc="24:00"),)
    kurz_vor_zwoelf = datetime(2026, 8, 11, 23, 59, 30, tzinfo=UTC)
    venue = _venue(
        sessions=fenster, stempel={"EURUSD": kurz_vor_zwoelf}, jetzt=kurz_vor_zwoelf
    )
    assert venue.is_trading_open("EURUSD", at=kurz_vor_zwoelf) is True


# =========================================================================== #
# Gegenproben: der Filter darf keine Dauerbremse werden                       #
# =========================================================================== #
def test_frischer_kurs_im_fenster_ist_offen() -> None:
    """Der Normalfall bleibt offen -- sonst waere die Reparatur nur ein Dauer-Nein."""
    venue = _venue()
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is True


def test_ausserhalb_des_fensters_bleibt_zu_trotz_frischem_kurs() -> None:
    """Die Tabelle verengt weiterhin: ein frischer Kurs oeffnet kein zu-Fenster.

    Beide Bedingungen sind notwendig. Waere der Kursstrom allein massgeblich, haette
    die Reparatur eine Sperre ENTFERNT statt eine hinzugefuegt.
    """
    spaet = datetime(2026, 8, 11, 21, 30, tzinfo=UTC)  # nach 21:00
    venue = _venue(stempel={"EURUSD": spaet}, jetzt=spaet)
    assert venue.is_trading_open("EURUSD", at=spaet) is False


def test_wochenende_bleibt_zu() -> None:
    samstag = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    venue = _venue(stempel={"EURUSD": samstag}, jetzt=samstag)
    assert venue.is_trading_open("EURUSD", at=samstag) is False


def test_unbekanntes_symbol_wirft_weiter() -> None:
    """Ein Symbol ohne Katalogeintrag bleibt ein Fehler, kein stilles ``False``."""
    from mt5_trading_ai.venue.protocol import UnknownInstrumentError

    venue = _venue()
    with pytest.raises(UnknownInstrumentError):
        venue.is_trading_open("XAUUSD", at=DIENSTAG)


# =========================================================================== #
# Der Katalog als belegpflichtige Datei                                       #
# =========================================================================== #
def test_katalog_lehnt_unsinnige_sitzungszeiten_ab(tmp_path: Path) -> None:
    """DER ROTE EICHFALL DES KATALOGS.

    ``"25:99"`` ergab gegen HEAD klaglos 1599 Minuten, ein Wochentag 9 ein Fenster,
    das der Filter nie erreichte. Beides ist ein Loch in einer Datei, die als Beleg
    gilt -- und ein Fenster, das nie greift, ist eine Sperre, die nicht sperrt.
    """
    import json

    from mt5_trading_ai.venue.catalog import (
        InstrumentCatalogError,
        load_instrument_catalog,
    )

    for kaputt in (
        {"weekday": 0, "open_utc": "00:00", "close_utc": "25:99"},
        {"weekday": 9, "open_utc": "00:00", "close_utc": "21:00"},
        {"weekday": 0, "open_utc": "9", "close_utc": "21:00"},
        {"weekday": 0, "open_utc": "24:00", "close_utc": "06:00"},
        {"weekday": 0, "open_utc": "08:00", "close_utc": "08:00"},
    ):
        pfad = tmp_path / "katalog.json"
        pfad.write_text(
            json.dumps(
                {
                    "catalog_id": "test",
                    "valid_from": "2026-01-01",
                    "verified_on": "2026-01-01",
                    "instruments": {
                        "EURUSD": {
                            "asset_class": "fx_major",
                            "fees": {
                                "commission_per_lot_round_turn": "7",
                                "typical_spread_points": "6",
                                "swap_long_per_lot_per_night": "-2",
                                "swap_short_per_lot_per_night": "-1",
                                "triple_swap_weekday": 2,
                                "currency": "USD",
                            },
                            "sessions": [kaputt],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(InstrumentCatalogError):
            load_instrument_catalog(pfad)


def test_ausgelieferter_katalog_laedt_weiter() -> None:
    """Gegenprobe zur neuen Strenge: die echte Datei muss durchgehen."""
    from mt5_trading_ai.venue.catalog import load_instrument_catalog

    katalog = load_instrument_catalog()
    assert "EURUSD" in katalog
    assert katalog["BTCUSD"].sessions[0].close_utc == "24:00"


# =========================================================================== #
# Benannter Mangel -- ausdruecklich KEINE Zusicherung                          #
# =========================================================================== #
def test_stehende_indikative_kurse_gelten_als_offen() -> None:
    """BEKANNTER MANGEL, festgenagelt.

    Ein Broker, der auf einem geschlossenen Platz weiter indikative Kurse stellt --
    etwa eine Kursstellung ohne Ausfuehrbarkeit --, laesst den Filter offen melden.
    Der Kursstempel ist frisch, gehandelt wird trotzdem nichts.

    Warum das hier steht statt behoben zu sein: die saubere Gegenprobe ist
    ``symbol_info(...).trade_mode`` bzw. ``symbol_info_sessions_trade`` -- die
    Auskunft des Brokers darueber, ob dieses Symbol gerade handelbar ist. Beides
    gehoert an die Naht ``Mt5Terminal``, und jede Erweiterung dieses Protokolls zieht
    saemtliche Fake-Terminals des Repos mit; das ist eine eigene Welle.

    Der Schaden ist begrenzt: die Order laeuft danach in die Ablehnung des Brokers
    ("Market closed"), sie wird nicht etwa zu einem falschen Preis gefuellt. Wer den
    Mangel behebt, macht diesen Test rot -- das ist beabsichtigt.
    """
    venue = _venue(stempel={"EURUSD": DIENSTAG})
    # Richtig waere hier eine Rueckfrage beim Broker, ob das Symbol handelbar ist.
    assert venue.is_trading_open("EURUSD", at=DIENSTAG) is True
