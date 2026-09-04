"""Zweigdeckung ``venue/mt5.py`` (A15): die 54 Zweige, die die Suite nicht lief.

Gemessen vor diesen Tests (Beleg ``06-zweigdeckung-nach-t6.txt``): 83,0 % Zweigdeckung,
54 fehlende Zweige; danach 100,0 %, 0 fehlende (Beleg
``06-zweigdeckung-mt5-messung.txt``, Schwelle A15 = 90 %). Es sind fast durchweg die
**ablehnenden** Zweige des Adapters und die des realen Terminals, also die, wegen derer
beide existieren:

* 270->271, 276->277, 280->281  ``_sitzungsfenster``: Wochentag ausserhalb 0..6,
  Sitzungsbeginn am Tagesende, Beginn gleich Ende -- die drei Pruefungen, die nur an
  einem handgebauten ``TradingSession`` feuern (der Katalog-Lader faengt sie vorher).
* 498->499    ``konto_maengel``: eine Pflichtzahl des Kontoschnappschusses fehlt.
* 642->643    ``connect``: das Terminal laesst sich nicht aufbauen.
* 1178->1192  ``submit_order``: ein Abbau laeuft ohne Risiko-Manager durch.
* 1293->1294  ``_reduces_position``: kein Positionsticket -> kein Abbau.
* 1478->1479  ``kurs``: leere Waehrung -> kein Kurs.
* 1486->1487, 1526->1527, 1574->1575  Hebeltor, Kostentor, Risikotor ohne Kurs.
* 1622->Ausgang  ``_validate_volume``: Schrittweite 0 -> keine Rasterpruefung.
* 1845->Ausgang  ``_halt_grund_ergaenzen``: derselbe Grund steht schon.
* 1862->1863, 1870->1872  ``_halt_reason``-Setter: ``None`` loescht; ein neuer Grund
  ohne die Kette im Text wird angehaengt.
* 1945->1946  ``reconcile``: Symbol ohne Kurs -> keine Bewertung der Drift.
* 1985->1990  ``adopt_book``: kein Risiko-Manager -> keine Geister des Zaehlers.
* 2053->2058  ``_positionsbuch_fortschreiben``: Fill ohne Ticket -> Halt + Platzhalter.
* 2084->2085  ``apply_private_event`` ohne konfigurierten Strom.
* 2253->2254  ``_ohne_fehlercode``: kein Ergebnis.
* 2297->2298  ``_send_gefuellt``: ein benannter Fehlercode ist keine Fuellung.
* 2424->2426, 2426->2427, 2426->2428, 2428->2429, 2428->2430  ``_fuellart``: die
  Bitmaske des Symbols entscheidet, und eine leere Maske wird nicht geraten.
* 2587->2588 .. 2593->2595  ``RealMt5Terminal.initialize``: jedes der vier
  Zugangsfelder geht nur mit, wenn es gesetzt ist.
* 2598->Ausgang, 2598->2599  ``shutdown`` ohne und mit Sitzung.
* 2791->2792, 2796->2797, 2800->2801  ``_require_write``: die drei Sperren des
  Schreibpfads (Freigabe, Sitzung, Demokonto).
* 2845->2846  ``tick``: kein Tick vom Terminal.
* 2858->2859, 2858->2860, 2862->2863, 2862->2877  ``rates``: kein Ergebnis bzw. Zeilen.
* 2893->2894  ``positions``: die Schleife ueber gemeldete Positionen.
* 2912->2913  ``account``: kein Konto-Info.
* 2995->2996, 2997->3002, 3028->3029, 3043->3044, 3101->3107  ``order_send``: kein
  Tick, der Limit-Zweig, ein mitgeschickter Take-Profit, unabfragbarer
  Positionsbestand, kein Ergebnis vom Server.
* 3252->3253, 3256->3257, 3267->3268  ``_stops_stehen``: Position weg, kein
  ``symbol_info``, kein gemeldeter Stop -- dreimal "nicht messbar heisst nicht belegt".

Jeder Test prueft die **Aussage** des Zweigs (Fehlertyp, ``reason``, gesendeter
Auftrag, gefuehrter Zustand), nicht seine Beruehrung. Der ablehnenden Richtung steht
die annehmende gegenueber -- meist im selben Test; wo das die Lage verwischen wuerde,
traegt sie ein eigener Bezugspunkt
(``test_ein_gesundes_sitzungsfenster_wird_nicht_beanstandet``,
``test_die_frist_des_venues_gilt_auch_fuer_den_kursstrom``,
``test_ein_verschobener_stop_wird_nachgelesen_und_belegt``,
``test_die_geliehenen_bezugsgroessen_sind_die_erwarteten``). Faellt ein Zweig weg oder
kippt sein Vergleich, wird der Test rot: 15 Gegenproben ueber 15 Familien dieser Datei
belegen es, 15 von 15 machen einen Fall rot (Beleg
``06-zweigdeckung-mt5-gegenproben.txt``).

Kein echtes Terminal: ``Mt5Venue`` bekommt das Fake aus ``tests/test_mt5_venue.py``,
``RealMt5Terminal`` die Attrappe ``_Mt5`` aus ``tests/eichfall_d2.py`` ueber
``t._mt5 = ...``. ``MetaTrader5.initialize()`` wird nirgends gerufen -- der einzige
Test, der ``RealMt5Terminal.initialize`` faehrt, legt ein Attrappenmodul in
``sys.modules``. Nichts ausserhalb ``tmp_path``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from mt5_trading_ai.execution.cost_gate import CostGate
from mt5_trading_ai.execution.private_sync import PrivateEvent, PrivateEventKind
from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.catalog import CatalogEntry, InstrumentCatalogError
from mt5_trading_ai.venue.mt5 import (
    Mt5SendResult,
    Mt5Symbol,
    Mt5Venue,
    RealMt5Terminal,
    _fuellart,
    _ohne_fehlercode,
    _send_gefuellt,
    konto_maengel,
)
from mt5_trading_ai.venue.protocol import (
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    TradingSession,
    VenueUnavailableError,
)

from eichfall_d2 import DONE, _Ergebnis, _Mt5
from test_mt5_venue import (
    TS,
    FakeMt5Terminal,
    _bestandener_edge,
    _catalog,
    _eurusd_symbol,
    _fees,
    _fresh_risk,
    _mt5_position,
    _order,
)

#: Platzhalter, kein Geheimnis: er geht ausschliesslich in die Attrappe.
ZUGANG_PLATZHALTER = "platzhalter"

#: Grosszuegiges Kostentor -- die Testorder (~2,45 bp) laeuft durch. Der Zweig, der
#: hier gemessen wird, liegt VOR der Rechnung (kein Kurs), nicht in ihr.
_KOSTENTOR = CostGate(max_roundturn_cost_fraction=Decimal("0.0005"))


# --------------------------------------------------------------------------- #
# Attrappen: das Vertrags-Fake mit drei Schaltern, die der Vertragstest nicht    #
# braucht, und die Terminal-Attrappe aus eichfall_d2 mit Antwortfolgen.          #
# --------------------------------------------------------------------------- #
class _Terminal(FakeMt5Terminal):
    """``FakeMt5Terminal`` (tests/test_mt5_venue.py) mit vier zusaetzlichen Schaltern.

    ``stumme`` nennt Symbole, fuer die das Terminal keinen Tick liefert;
    ``stumm_ab_aufruf`` die laufende Nummer des Tick-Aufrufs, ab der ueberhaupt keiner
    mehr kommt (der Kursstrom bricht MITTEN im Orderpfad ab -- genau so erreicht der
    Test das zweite Tick-Tor, ohne dass der Frische-Latch davor schon antwortet);
    ``zusatzsymbole`` weitere Symbole am Terminal (fuer Faelle, in denen der Katalog
    ein Symbol nicht kennt); ``sende`` eine feste Antwort auf ``order_send``;
    ``initialisiert=False`` ein Terminal, das sich nicht aufbauen laesst.
    """

    def __init__(
        self,
        *,
        is_demo: bool = True,
        margin_free: Decimal = Decimal("10000"),
        positions: tuple[Any, ...] = (),
        jetzt: datetime = TS,
        stumme: frozenset[str] = frozenset(),
        stumm_ab_aufruf: int | None = None,
        zusatzsymbole: tuple[Mt5Symbol, ...] = (),
        sende: Mt5SendResult | None = None,
        initialisiert: bool = True,
    ) -> None:
        super().__init__(
            is_demo=is_demo,
            margin_free=margin_free,
            positions=positions,
            jetzt=jetzt,
        )
        for zusatz in zusatzsymbole:
            self._symbols[zusatz.name] = zusatz
        self._stumme = stumme
        self._stumm_ab_aufruf = stumm_ab_aufruf
        self._sende = sende
        self._initialisiert = initialisiert
        self.tick_aufrufe = 0

    def initialize(self) -> bool:
        if not self._initialisiert:
            return False
        return super().initialize()

    def tick(self, name: str) -> Any:
        self.tick_aufrufe += 1
        if name in self._stumme:
            return None
        if self._stumm_ab_aufruf is not None and self.tick_aufrufe >= (
            self._stumm_ab_aufruf
        ):
            return None
        return super().tick(name)

    def order_send(self, request: object) -> Mt5SendResult:
        if self._sende is None:
            return super().order_send(request)
        self.order_send_calls += 1
        return self._sende


def _venue_mit(
    terminal: FakeMt5Terminal,
    *,
    katalog: dict[str, CatalogEntry] | None = None,
    cost_gate: CostGate | None = None,
    risk_manager: RiskManager | None = None,
    ohne_risiko: bool = False,
    jetzt: datetime = TS,
    verbinden: bool = True,
) -> Mt5Venue:
    """Ein Venue ueber einem mitgebrachten Terminal -- sonst wie ``_venue()``.

    ``_venue()`` aus dem Vertragstest baut sein Fake selbst; hier braucht jeder Fall
    ein anders geschaltetes. Die Vorgaben sind dieselben: Risikoschicht gesetzt (sie
    ist fuer jede Eroeffnung Pflicht, auch auf Demo), Uhr auf ``TS``, beide Ablagen
    fluechtig (nichts ausserhalb des Prozesses, A10/A18).
    """
    venue = Mt5Venue(
        name="mt5-zweige",
        terminal=terminal,
        catalog=katalog if katalog is not None else _catalog(),
        cost_gate=cost_gate,
        risk_manager=(None if ohne_risiko else (risk_manager or _fresh_risk())),
        demo_registration=None,
        demo_live_verdict=_bestandener_edge(),
        clock=lambda: jetzt,
        schwebeakte=FluechtigeSchwebeAkte(),
        positionsbuch=FluechtigesPositionsbuch(),
    )
    if verbinden:
        venue.connect()
    return venue


def _katalog_mit_sitzung(session: TradingSession) -> dict[str, CatalogEntry]:
    """Der Standardkatalog, dessen EURUSD-Eintrag genau dieses Fenster fuehrt."""
    eintrag = _catalog()["EURUSD"]
    return {"EURUSD": replace(eintrag, sessions=(session,))}


# --------------------------------------------------------------------------- #
# _sitzungsfenster: die drei Pruefungen am handgebauten TradingSession          #
# --------------------------------------------------------------------------- #
def test_ein_gesundes_sitzungsfenster_wird_nicht_beanstandet() -> None:
    """Bezugspunkt: ohne ihn bewiese ein Fehler unten nur ein kaputtes Geruest.

    ``TS`` ist ein Dienstag 12:00 UTC; das Fenster Di 08:00-22:00 deckt ihn, und der
    Tick des Fakes traegt denselben Stempel wie die Uhr des Venues.
    """
    venue = _venue_mit(
        _Terminal(),
        katalog=_katalog_mit_sitzung(
            TradingSession(weekday=1, open_utc="08:00", close_utc="22:00")
        ),
    )
    assert venue.is_trading_open("EURUSD", at=TS) is True


def test_sitzung_mit_wochentag_sieben_ist_ein_katalogfehler() -> None:
    """270->271: ``weekday`` ausserhalb 0..6 ist kein Fenster, sondern ein Defekt.

    Ohne die Pruefung liefe ``anfang = 7 * 1440 + auf`` schweigend ueber das Wochenende
    hinaus: ein Fenster, das per Konstruktion nie deckt.
    """
    venue = _venue_mit(
        _Terminal(),
        katalog=_katalog_mit_sitzung(
            TradingSession(weekday=7, open_utc="08:00", close_utc="22:00")
        ),
    )
    with pytest.raises(InstrumentCatalogError, match="Wochentag 7"):
        venue.is_trading_open("EURUSD", at=TS)


def test_sitzungsbeginn_am_tagesende_ist_ein_katalogfehler() -> None:
    """276->277: ``"24:00"`` als Oeffnung ist eine Sitzung des Folgetags, kein Fenster."""
    venue = _venue_mit(
        _Terminal(),
        katalog=_katalog_mit_sitzung(
            TradingSession(weekday=1, open_utc="24:00", close_utc="06:00")
        ),
    )
    with pytest.raises(InstrumentCatalogError, match="liegt am Tagesende"):
        venue.is_trading_open("EURUSD", at=TS)


def test_sitzung_mit_gleichem_beginn_und_ende_ist_mehrdeutig() -> None:
    """280->281: ``08:00-08:00`` heisst "nie" oder "immer" -- beides wird nicht geraten."""
    venue = _venue_mit(
        _Terminal(),
        katalog=_katalog_mit_sitzung(
            TradingSession(weekday=1, open_utc="08:00", close_utc="08:00")
        ),
    )
    with pytest.raises(InstrumentCatalogError, match="ist mehrdeutig"):
        venue.is_trading_open("EURUSD", at=TS)


# --------------------------------------------------------------------------- #
# konto_maengel: eine fehlende Pflichtzahl                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("feld", ["balance", "equity", "margin_used", "margin_free"])
def test_eine_fehlende_pflichtzahl_sperrt_mit_namen(feld: str) -> None:
    """498->499: ein fehlender Messwert wird benannt, nicht durch eine Null ersetzt.

    Die annehmende Richtung steht daneben: der vollstaendige Schnappschuss ergibt
    ``None``. Kippte der Vergleich, meldete gerade er einen Mangel.
    """
    vollstaendig = _Terminal().account()
    assert konto_maengel(vollstaendig) is None
    luecke = replace(vollstaendig, **{feld: None})
    assert konto_maengel(luecke) == f"Pflichtzahl '{feld}' fehlt"


# --------------------------------------------------------------------------- #
# connect / disconnect                                                          #
# --------------------------------------------------------------------------- #
def test_ein_terminal_das_sich_nicht_aufbaut_ist_kein_venue() -> None:
    """642->643: ``initialize()`` false -> Fehler statt einer Sitzung, die es nicht gibt."""
    terminal = _Terminal(initialisiert=False)
    venue = _venue_mit(terminal, verbinden=False)
    with pytest.raises(VenueUnavailableError, match="nicht initialisierbar"):
        venue.connect()
    assert venue.is_healthy() is False
    # Gegenrichtung im selben Test: ein Terminal, das sich aufbaut, ergibt eine Sitzung.
    gesund = _venue_mit(_Terminal())
    assert gesund.is_healthy() is True


# --------------------------------------------------------------------------- #
# submit_order / _reduces_position                                              #
# --------------------------------------------------------------------------- #
def _abbau(ticket: str = "t1", volume: str = "0.10") -> OrderRequest:
    return _order(
        client_order_id=f"close-{ticket}",
        side=OrderSide.SELL,
        volume=Decimal(volume),
        stop_loss=Decimal("0"),
        reduce_only=True,
        position_ticket=ticket,
    )


def test_ein_abbau_laeuft_auch_ohne_risiko_manager_durch() -> None:
    """1178->1192: Sperre V5 -- reduzierende Auftraege blockiert keine Sperre.

    Ohne Risiko-Manager wird jede EROEFFNUNG fail-closed abgelehnt; der Abbau nicht.
    Traefe die Buchung des Fills trotzdem den Manager, endete der Aufruf in einem
    ``AttributeError`` auf ``None``.
    """
    terminal = _Terminal(
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),)
    )
    venue = _venue_mit(terminal, ohne_risiko=True)
    assert venue.risk_manager is None
    # Das Buch MUSS die Gegenposition kennen: nur dann ist pre_net + Fill == 0, und
    # nur dann liefe der Aufruf record_close() ueberhaupt an. Ohne diesen Schritt
    # bleibt das Buch leer, der Zweig ist beruehrt und nichts unterscheidet ihn
    # (Gegenlese T6, S2).
    venue.adopt_book()
    assert venue.book_snapshot()["EURUSD"] == Decimal("0.10")
    ergebnis = venue.submit_order(_abbau())
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0.10")
    assert venue.book_snapshot().get("EURUSD", Decimal("0")) == Decimal("0")
    # Und die Gegenrichtung: eine Eroeffnung bleibt ohne Manager gesperrt.
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    assert fehler.value.reason == "risk_unconfigured"


def test_ohne_positionsticket_baut_nichts_ab() -> None:
    """1293->1294: ohne Ticket ist die Order keine Schliessung -- fail-closed.

    Erreichbar nur ueber den direkten Aufruf: ``OrderRequest`` weist ein
    ``reduce_only`` ohne Ticket schon im Konstruktor ab (D2), und ``submit_order``
    ruft die Methode ausschliesslich fuer ``reduce_only``-Auftraege. Die Zusicherung
    stellt beide Richtungen gegenueber: mit passendem Ticket ist es ein Abbau.
    """
    terminal = _Terminal(
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),)
    )
    venue = _venue_mit(terminal)
    ohne = _order(volume=Decimal("0.10"), side=OrderSide.SELL, position_ticket=None)
    assert venue._reduces_position(ohne) is False
    mit = _order(volume=Decimal("0.10"), side=OrderSide.SELL, position_ticket="t1")
    assert venue._reduces_position(mit) is True


def test_ein_fill_ohne_ticket_latcht_den_halt_und_bucht_einen_platzhalter() -> None:
    """2053->2058: eine Position, die dieses Haus nicht per Ticket schliessen kann.

    Gebucht wird sie trotzdem (sonst wuesste niemand von ihr), aber unter
    ``"unbekannt"`` und mit stehendem Halt. Daneben die annehmende Richtung: mit
    Ticket steht kein Halt und das Buch traegt das echte Ticket.
    """
    ohne_ticket = Mt5SendResult(
        accepted=True,
        venue_order_id=None,
        filled_volume=Decimal("0.01"),
        average_price=Decimal("1.10000"),
        ts=TS,
        reason="done",
    )
    venue = _venue_mit(_Terminal(sende=ohne_ticket))
    ergebnis = venue.submit_order(_order())
    assert ergebnis.accepted is True
    assert venue.is_halted() is True
    assert "positionsbuch_ohne_ticket:c-1" in venue.halt_gruende
    assert [b.ticket for b in venue.positionsbuch.laden()] == ["unbekannt"]

    sauber = _venue_mit(_Terminal())
    sauber.submit_order(_order())
    assert sauber.is_halted() is False
    assert [b.ticket for b in sauber.positionsbuch.laden()] == ["V-1"]


# --------------------------------------------------------------------------- #
# kurs, Hebeltor, Kostentor, Risikotor: die vier Stellen ohne Kurs               #
# --------------------------------------------------------------------------- #
def test_eine_leere_waehrung_hat_keinen_kurs() -> None:
    """1478->1479: ohne Waehrungsnamen gibt es nichts umzurechnen -- ``None`` sperrt.

    Die annehmende Richtung daneben: zwei gefuellte Namen liefern den Mittelkurs.
    """
    venue = _venue_mit(_Terminal())
    assert venue.kurs("", "USD") is None
    assert venue.kurs("EUR", "") is None
    assert venue.kurs("EUR", "USD") == Decimal("1.099950")


def test_zwei_leere_waehrungen_sind_kein_paar_und_kein_kurs_eins() -> None:
    """Zeile 1478, die Stelle, an der der Wachposten die Antwort AENDERT: ohne ihn
    liefe ``kurs("", "")`` in ``kurs_aus_ticks``, dort gilt ``von == nach`` und das
    Ergebnis waere ``Decimal(1)`` -- ein Kurs aus dem Nichts. Die beiden anderen
    Eingaben (eine Seite leer) antworten auch ohne Wachposten ``None``; sie
    unterscheiden ihn nicht (Gegenlese T6, S2).
    """
    terminal = _Terminal()
    venue = _venue_mit(terminal)

    assert venue.kurs("", "") is None
    assert terminal.tick_aufrufe == 0, (
        "eine leere Waehrung darf das Terminal nicht einmal fragen"
    )


def test_ohne_kurs_faellt_die_hebelpruefung_aus() -> None:
    """1486->1487: der Kursstrom bricht NACH dem Frische-Latch ab.

    Der erste Tick-Aufruf im Orderpfad gehoert dem Frische-Latch, der zweite dem
    Hebeltor (Reihenfolge festgenagelt in ``test_orderpfad_verdrahtung.py``). Das
    Terminal verstummt ab dem zweiten -- so antwortet das Hebeltor und nicht der
    Latch davor. Es wird nichts gesendet.
    """
    terminal = _Terminal(stumm_ab_aufruf=2)
    venue = _venue_mit(terminal)
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    assert fehler.value.reason == "no_tick"
    assert "Hebelpruefung" in str(fehler.value)
    assert terminal.order_send_calls == 0


def test_ohne_kurs_faellt_das_kostentor_aus() -> None:
    """1526->1527: das Kostentor rechnet nicht ohne Bid/Ask.

    Direkt gerufen, weil der Frische-Latch am Orderpfad denselben Tick liest und
    dasselbe Terminal schon eine Sperre frueher antworten liesse. Beide Richtungen:
    ohne Tick ``no_tick``, mit Tick keine Ablehnung.
    """
    stumm = _venue_mit(
        _Terminal(is_demo=False, stumme=frozenset({"EURUSD"})), cost_gate=_KOSTENTOR
    )
    with pytest.raises(OrderRejectedError) as fehler:
        stumm._enforce_cost_gate(stumm.get_instrument("EURUSD"), _order())
    assert fehler.value.reason == "no_tick"
    assert "Kostentor" in str(fehler.value)

    gesund = _venue_mit(_Terminal(is_demo=False), cost_gate=_KOSTENTOR)
    gesund._enforce_cost_gate(gesund.get_instrument("EURUSD"), _order())


def test_ohne_kurs_faellt_die_risikopruefung_aus() -> None:
    """1574->1575: die Risikoschicht rechnet nicht ohne Preis.

    Direkt gerufen, aus demselben Grund wie beim Kostentor. Beide Richtungen.
    """
    stumm = _venue_mit(_Terminal(stumme=frozenset({"EURUSD"})))
    with pytest.raises(OrderRejectedError) as fehler:
        stumm._enforce_risk(stumm.get_instrument("EURUSD"), _order(), 5)
    assert fehler.value.reason == "no_tick"
    assert "Risikopruefung" in str(fehler.value)

    gesund = _venue_mit(_Terminal())
    gesund._enforce_risk(gesund.get_instrument("EURUSD"), _order(), 5)


def test_ohne_schrittweite_wird_das_volumen_nicht_gerastert() -> None:
    """1622->Ausgang: ``volume_step <= 0`` ist kein Raster, also gibt es keine Rasterpruefung.

    Ohne den Zweig teilte die Rechnung durch null. Die annehmende Richtung steht
    daneben: mit Schrittweite 0,01 wird 0,015 abgewiesen.
    """
    venue = _venue_mit(_Terminal())
    instrument = venue.get_instrument("EURUSD")
    with pytest.raises(OrderRejectedError) as fehler:
        venue._validate_volume(instrument, Decimal("0.015"))
    assert fehler.value.reason == "volume_off_step"
    ohne_raster = replace(instrument, volume_step=Decimal("0"))
    venue._validate_volume(ohne_raster, Decimal("0.015"))


# --------------------------------------------------------------------------- #
# Halt-Gruende (D4): nichts wird ueberschrieben, nichts doppelt gefuehrt        #
# --------------------------------------------------------------------------- #
def test_derselbe_halt_grund_wird_nicht_zweimal_gefuehrt() -> None:
    """1845->Ausgang: ein zweiter Latch mit demselben Grund haengt nichts an.

    Die Gegenrichtung im selben Test: ein ANDERER Grund kommt hinzu, er ersetzt
    nichts (D4).
    """
    venue = _venue_mit(_Terminal())
    venue.latch_halt(reason="tagesverlust")
    venue.latch_halt(reason="tagesverlust")
    assert venue.halt_gruende == ("tagesverlust",)
    venue.latch_halt(reason="reconcile_drift:x")
    assert venue.halt_gruende == ("tagesverlust", "reconcile_drift:x")


def test_halt_reason_auf_none_loescht_alle_gruende() -> None:
    """1862->1863: die eine Zuweisung, die die Liste raeumt."""
    venue = _venue_mit(_Terminal())
    venue.latch_halt(reason="tagesverlust")
    venue.latch_halt(reason="reconcile_drift:x")
    assert venue.halt_reason == "reconcile_drift:x (zuvor: tagesverlust)"
    venue._halt_reason = None
    assert venue.halt_gruende == ()
    assert venue.halt_reason is None


def test_ein_neuer_halt_grund_wird_angehaengt_und_die_kette_nicht_verdoppelt() -> None:
    """1870->1872: ein Grund OHNE die Kette im Text wird unveraendert angehaengt.

    Die Gegenrichtung (1870->1871) steht daneben: traegt der Text die aktuelle Kette
    als ``" (zuvor: ...)"``, wird genau dieser Anhang abgeschnitten -- sonst stuende
    die Kette zweimal in der Liste.
    """
    venue = _venue_mit(_Terminal())
    venue.latch_halt(reason="a")
    venue._halt_reason = "b"
    assert venue.halt_gruende == ("a", "b")
    venue._halt_reason = "c (zuvor: b (zuvor: a))"
    assert venue.halt_gruende == ("a", "b", "c")


# --------------------------------------------------------------------------- #
# reconcile / adopt_book / Privatstrom                                          #
# --------------------------------------------------------------------------- #
def test_eine_position_ohne_kurs_ist_eine_unbewertbare_drift() -> None:
    """1945->1946: kein Tick -> kein Notional -> ``unpriced_drift`` und Halt.

    Ohne den Zweig liefe die Bewertung in ``tick.bid`` auf ``None``. Die annehmende
    Richtung steht daneben: mit Kurs wird dieselbe Drift bewertet.
    """
    stumm = _Terminal(
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),),
        stumme=frozenset({"EURUSD"}),
    )
    ergebnis = _venue_mit(stumm).reconcile()
    assert ergebnis.halt is True
    assert ergebnis.reason == "unpriced_drift"
    assert [d.notional_drift for d in ergebnis.drifts] == [None]

    mit_kurs = _Terminal(
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),)
    )
    bewertet = _venue_mit(mit_kurs).reconcile()
    assert bewertet.reason == "notional_drift_exceeds_limit"
    assert bewertet.drifts[0].notional_drift is not None


def test_eine_position_ausserhalb_des_katalogs_ist_eine_unbewertbare_drift() -> None:
    """1949->1950: ein Symbol mit Kurs, aber ohne Katalogeintrag, wird nicht bewertet.

    Die Kontraktgroesse kommt aus dem Katalog; ohne Eintrag gibt es keine, und eine
    geratene waere eine erfundene Bewertung.
    """
    fremd = replace(_eurusd_symbol(), name="GBPUSD")
    terminal = _Terminal(
        positions=(_mt5_position("GBPUSD", is_buy=True, volume=Decimal("0.10")),),
        zusatzsymbole=(fremd,),
    )
    assert terminal.tick("GBPUSD") is not None  # Kurs ja, Katalog nein
    ergebnis = _venue_mit(terminal).reconcile()
    assert ergebnis.halt is True
    assert ergebnis.reason == "unpriced_drift"


def test_der_startabgleich_kennt_ohne_risiko_manager_keine_geister() -> None:
    """1985->1990: ohne Zaehler gibt es keine Geister des Zaehlers -- und keinen Absturz.

    Die annehmende Richtung daneben: mit Manager laeuft der Austrag wirklich.
    """
    positionen = (_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),)
    ohne = _venue_mit(_Terminal(positions=positionen), ohne_risiko=True)
    ohne.adopt_book()
    abgleich = ohne.startabgleich
    assert abgleich is not None
    assert abgleich.geister_zaehler == ()
    assert abgleich.offen_beim_broker == ("EURUSD",)

    mit = _venue_mit(_Terminal(positions=positionen))
    mit.adopt_book()
    assert mit.startabgleich is not None
    assert mit.startabgleich.geister_zaehler == ()


def test_ohne_konfigurierten_privatstrom_gibt_es_kein_ereignis() -> None:
    """2084->2085: ein Ereignis ohne Strom ist keine Buchung, sondern ein Fehler."""
    venue = _venue_mit(_Terminal())
    assert venue.has_private_stream is False
    ereignis = PrivateEvent(
        seq=1,
        ts=TS,
        kind=PrivateEventKind.FILL,
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=Decimal("0.10"),
    )
    with pytest.raises(VenueUnavailableError, match="Kein PrivateSync"):
        venue.apply_private_event(ereignis)


# --------------------------------------------------------------------------- #
# Die Antwortlese des Servers: _ohne_fehlercode, _send_gefuellt, _fuellart      #
# --------------------------------------------------------------------------- #
def test_ohne_ergebnis_gibt_es_keinen_erfolgscode() -> None:
    """2253->2254: ``None`` ist keine Auskunft -- also keine bestandene Pruefung."""
    mt5 = _Mt5()
    assert _ohne_fehlercode(mt5, None) is False
    assert _ohne_fehlercode(mt5, _Ergebnis(retcode=DONE)) is True
    assert _ohne_fehlercode(mt5, _Ergebnis(retcode=0)) is True
    assert _ohne_fehlercode(mt5, _Ergebnis(retcode=10004)) is False


def test_ein_benannter_fehlercode_ist_keine_fuellung() -> None:
    """2297->2298: Volumen und Kennung genuegen nicht, wenn der Server einen Fehler nennt.

    ``retcode=10004`` (Requote) mit Volumen und Order-Kennung: nichts ausgefuehrt.
    Die annehmende Richtung daneben -- der an diesem Broker gemessene Erfolgsfall
    ``retcode=0`` mit Kennung und Volumen.
    """
    mt5 = _Mt5()
    requote = _Ergebnis(retcode=10004, order=555, deal=556, volume=0.1)
    assert _send_gefuellt(mt5, requote) is False
    erfolg = _Ergebnis(retcode=0, order=555, deal=556, volume=0.1)
    assert _send_gefuellt(mt5, erfolg) is True


@dataclass
class _Mt5Fuellart(_Mt5):
    """``_Mt5`` mit frei gesetzter Bitmaske; ``maske=None`` meldet gar kein Symbol."""

    maske: int | None = 1

    def symbol_info(self, name: str) -> Any:
        if self.maske is None:
            return None
        return SimpleNamespace(filling_mode=self.maske, point=0.00001)


def test_die_fuellart_folgt_der_maske_des_symbols() -> None:
    """2424->2426, 2426->2427, 2426->2428, 2428->2429: Maske ist nicht Konstante.

    1 = FOK, 2 = IOC, 4 = RETURN; bei 3 (FOK und IOC) gewinnt FOK -- ganz oder gar
    nicht. Eine fest gesetzte Art traefe nur zufaellig.
    """
    assert _fuellart(_Mt5Fuellart(maske=1), "EURUSD") == _Mt5.ORDER_FILLING_FOK
    assert _fuellart(_Mt5Fuellart(maske=2), "US500") == _Mt5.ORDER_FILLING_IOC
    assert _fuellart(_Mt5Fuellart(maske=4), "XAUUSD") == _Mt5.ORDER_FILLING_RETURN
    assert _fuellart(_Mt5Fuellart(maske=3), "XAUUSD") == _Mt5.ORDER_FILLING_FOK


def test_ohne_gemeldete_fuellart_wird_nicht_geraten() -> None:
    """2428->2430: leere Maske und fehlendes Symbol enden beide fail-closed."""
    with pytest.raises(VenueUnavailableError, match="filling_mode=0"):
        _fuellart(_Mt5Fuellart(maske=0), "EURUSD")
    with pytest.raises(VenueUnavailableError, match="filling_mode=0"):
        _fuellart(_Mt5Fuellart(maske=None), "EURUSD")


# --------------------------------------------------------------------------- #
# RealMt5Terminal: Sitzungsaufbau, Schreibsperre, Lesepfade                      #
# --------------------------------------------------------------------------- #
class _Modul:
    """So viel ``MetaTrader5``-Modul, wie ``initialize``/``shutdown`` anfassen.

    Es liegt fuer die Dauer eines Tests in ``sys.modules``; das echte Paket wird
    dadurch nicht geladen und ``MetaTrader5.initialize()`` nie gerufen.
    """

    def __init__(self, *, erfolg: bool = True) -> None:
        self.kwargs: dict[str, Any] | None = None
        self.erfolg = erfolg
        self.shutdowns = 0

    def initialize(self, **kwargs: Any) -> bool:
        self.kwargs = dict(kwargs)
        return self.erfolg

    def shutdown(self) -> None:
        self.shutdowns += 1


def test_initialize_reicht_genau_die_gesetzten_zugangsfelder_weiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2587->2588, 2589->2590, 2591->2592, 2593->2594: jedes gesetzte Feld geht mit."""
    modul = _Modul()
    monkeypatch.setitem(sys.modules, "MetaTrader5", modul)
    terminal = RealMt5Terminal(
        login=4242,
        password=ZUGANG_PLATZHALTER,
        server="probe",
        path="C:/probe/terminal64.exe",
    )
    assert terminal.initialize() is True
    assert modul.kwargs == {
        "path": "C:/probe/terminal64.exe",
        "login": 4242,
        "password": ZUGANG_PLATZHALTER,
        "server": "probe",
    }


def test_initialize_ohne_zugangsfelder_reicht_nichts_weiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2587->2589, 2589->2591, 2591->2593, 2593->2595: nichts gesetzt, nichts gesendet.

    Ein leeres ``kwargs`` heisst: das Terminal nimmt die angemeldete Sitzung, die es
    schon hat. Ein durchgereichtes ``None`` waere ein anderer Aufruf.
    """
    modul = _Modul(erfolg=False)
    monkeypatch.setitem(sys.modules, "MetaTrader5", modul)
    assert RealMt5Terminal().initialize() is False
    assert modul.kwargs == {}


def test_ohne_installiertes_paket_scheitert_der_aufbau_laut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Import haengt am Verbindungsaufbau, nicht am Modulimport -- und er ist laut."""
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    with pytest.raises(VenueUnavailableError, match="nicht installiert"):
        RealMt5Terminal().initialize()


def test_shutdown_ohne_sitzung_tut_nichts_mit_sitzung_schliesst_es() -> None:
    """2598->Ausgang und 2598->2599: beide Richtungen derselben Frage."""
    ohne = RealMt5Terminal()
    ohne.shutdown()  # keine Sitzung: kein Aufruf, keine Ausnahme
    modul = _Modul()
    mit = RealMt5Terminal()
    mit._mt5 = modul
    mit.shutdown()
    assert modul.shutdowns == 1


def _echt(mt5: Any, *, allow_write: bool = True, require_demo: bool = True) -> Any:
    """``RealMt5Terminal`` mit einer Attrappe statt einer Sitzung (kein ``initialize``)."""
    terminal = RealMt5Terminal(allow_write=allow_write, require_demo=require_demo)
    terminal._mt5 = mt5
    return terminal


def test_der_schreibpfad_ist_ohne_freigabe_gesperrt() -> None:
    """2791->2792: fail-closed -- erst gegen ein Demo-Terminal pruefen, dann freigeben."""
    mt5 = _Mt5()
    with pytest.raises(VenueUnavailableError, match="Schreibpfad gesperrt"):
        _echt(mt5, allow_write=False).order_send(_terminal_auftrag())
    assert mt5.gesendet == []


def test_der_schreibpfad_braucht_eine_sitzung() -> None:
    """2796->2797: freigegeben, aber ohne Sitzung ist nichts zu senden."""
    terminal = RealMt5Terminal(allow_write=True)
    with pytest.raises(VenueUnavailableError, match="keine Sitzung"):
        terminal.order_send(_terminal_auftrag())


@dataclass
class _Mt5Live(_Mt5):
    """``_Mt5`` mit einem Konto, das KEIN Demokonto ist (``trade_mode`` != Demo)."""

    def account_info(self) -> Any:
        return SimpleNamespace(
            login=4242,
            currency="USD",
            balance=1e4,
            equity=1e4,
            margin=0.0,
            margin_free=1e4,
            trade_mode=2,
            leverage=30,
        )


def test_der_schreibpfad_des_terminals_bleibt_auf_dem_demokonto() -> None:
    """2800->2801: der direkte Terminalzugriff liegt unter allen fuenf Sperren.

    Die annehmende Richtung daneben: dasselbe Konto mit ``require_demo=False`` ist
    eine bewusste, getrennte Entscheidung und sendet.
    """
    mt5 = _Mt5Live(positionen=(SimpleNamespace(ticket=777, type=0, symbol="EURUSD"),))
    with pytest.raises(VenueUnavailableError, match="nur auf einem Demokonto"):
        _echt(mt5).order_send(_terminal_auftrag())
    assert mt5.gesendet == []
    _echt(mt5, require_demo=False).order_send(_terminal_auftrag())
    assert len(mt5.gesendet) == 1


def _terminal_auftrag(**ueberschreibung: Any) -> dict[str, Any]:
    """Ein Auftrag in der Form, die ``Mt5Venue._to_terminal_request`` erzeugt."""
    basis: dict[str, Any] = {
        "client_order_id": "open-EURUSD-zweig",
        "symbol": "EURUSD",
        "side": "buy",
        "order_type": "market",
        "volume": Decimal("0.10"),
        "stop_loss": Decimal("1.09"),
        "take_profit": None,
        "limit_price": None,
        "reduce_only": False,
        "position_ticket": None,
        "comment": "zweig",
    }
    basis.update(ueberschreibung)
    return basis


@dataclass
class _Mt5OhneTick(_Mt5):
    """``_Mt5``, das keinen Tick liefert -- der Kursstrom steht."""

    def symbol_info_tick(self, name: str) -> Any:
        return None


def test_ohne_tick_meldet_das_terminal_keinen_kurs() -> None:
    """2845->2846: kein Tick ist ``None``, nicht ein Kurs von null.

    Die annehmende Richtung daneben: mit Tick kommt ein ``Mt5Tick`` heraus.
    """
    assert _echt(_Mt5OhneTick()).tick("EURUSD") is None
    kurs = _echt(_Mt5()).tick("EURUSD")
    assert kurs is not None
    assert (kurs.bid, kurs.ask) == (Decimal("1.0999"), Decimal("1.1"))


class _Zeilen:
    """So viel ``numpy``-Strukturfeld, wie ``rates`` anfasst: ``dtype.names`` + Zeilen."""

    def __init__(
        self, zeilen: tuple[dict[str, Any], ...], namen: tuple[str, ...]
    ) -> None:
        self._zeilen = zeilen
        self.dtype = SimpleNamespace(names=namen)

    def __iter__(self) -> Any:
        return iter(self._zeilen)


@dataclass
class _Mt5Kerzen(_Mt5):
    """``_Mt5`` mit einer festen Antwort auf ``copy_rates_range``."""

    zeilen: Any = None
    abfragen: list[Any] = field(default_factory=list)
    TIMEFRAME_H1 = 16385

    def copy_rates_range(self, name: str, tf: int, start: Any, end: Any) -> Any:
        self.abfragen.append((name, tf, start, end))
        return self.zeilen


def _kerze(ts: int, **ueberschreibung: Any) -> dict[str, Any]:
    zeile: dict[str, Any] = {
        "time": ts,
        "open": 1.1,
        "high": 1.2,
        "low": 1.0,
        "close": 1.15,
        "tick_volume": 100,
        "real_volume": 7,
        "spread": 6,
    }
    zeile.update(ueberschreibung)
    return zeile


def test_ohne_kerzen_liefert_rates_ein_leeres_tupel() -> None:
    """2858->2859: ``copy_rates_range`` gibt ``None`` -- daraus wird kein Balken."""
    mt5 = _Mt5Kerzen(zeilen=None)
    terminal = _echt(mt5)
    start = datetime(2026, 8, 11, 10, tzinfo=UTC)
    assert terminal.rates("EURUSD", Timeframe.H1, start, start) == ()
    assert mt5.abfragen[0][:2] == ("EURUSD", 16385)


def test_rates_bildet_jede_gemeldete_zeile_ab() -> None:
    """2858->2860, 2862->2863, 2862->2877: die Schleife laeuft und laeuft aus.

    Zwei Zeilen mit allen Feldern, danach dieselbe Abfrage ohne ``real_volume`` und
    ``spread`` -- die beiden Felder, die nicht jeder Broker meldet.
    """
    voll = _Zeilen(
        (_kerze(1786000000), _kerze(1786003600, close=1.16)),
        (
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "real_volume",
            "spread",
        ),
    )
    start = datetime(2026, 8, 11, 10, tzinfo=UTC)
    balken = _echt(_Mt5Kerzen(zeilen=voll)).rates("EURUSD", Timeframe.H1, start, start)
    assert len(balken) == 2
    assert balken[0].ts == datetime.fromtimestamp(1786000000, tz=UTC)
    assert balken[0].close == Decimal("1.15")
    assert balken[1].close == Decimal("1.16")
    assert balken[0].real_volume == Decimal("7")
    assert balken[0].spread_points == Decimal("6")

    schmal = _Zeilen(
        (_kerze(1786000000),),
        ("time", "open", "high", "low", "close", "tick_volume"),
    )
    knapp = _echt(_Mt5Kerzen(zeilen=schmal)).rates("EURUSD", Timeframe.H1, start, start)
    assert knapp[0].real_volume is None
    assert knapp[0].spread_points is None


def _rohposition(**ueberschreibung: Any) -> Any:
    felder: dict[str, Any] = {
        "ticket": 777,
        "symbol": "EURUSD",
        "type": 0,
        "volume": 0.1,
        "price_open": 1.1,
        "sl": 1.09,
        "tp": 1.12,
        "time": 1786000000,
        "profit": 3.5,
        "swap": -0.25,
    }
    felder.update(ueberschreibung)
    return SimpleNamespace(**felder)


def test_positions_bildet_jede_gemeldete_position_ab() -> None:
    """2893->2894: die Schleife ueber den Bestand -- bisher lief nur der leere Fall.

    Die Richtung des Bestands haengt am ``POSITION_TYPE_BUY`` des Terminals, nicht an
    einer geratenen Null: die zweite Position traegt ``type=1`` und ist ein Verkauf.
    """
    mt5 = _Mt5(
        positionen=(_rohposition(), _rohposition(ticket=778, type=1, sl=0.0, tp=0.0))
    )
    bestand = _echt(mt5).positions()
    assert [p.ticket for p in bestand] == ["777", "778"]
    assert [p.is_buy for p in bestand] == [True, False]
    assert bestand[0].volume == Decimal("0.1")
    assert bestand[0].stop_loss == Decimal("1.09")
    assert bestand[0].opened_at == datetime.fromtimestamp(1786000000, tz=UTC)
    assert bestand[1].stop_loss is None  # sl=0 heisst "kein Stop", nicht "Stop bei 0"


@dataclass
class _Mt5OhneKonto(_Mt5):
    """``_Mt5`` ohne Kontositzung."""

    def account_info(self) -> Any:
        return None


def test_ohne_konto_info_ist_das_terminal_nicht_verfuegbar() -> None:
    """2912->2913: kein Konto ist kein Konto mit Nullen.

    Die annehmende Richtung daneben: mit Konto kommt ein vollstaendiger Schnappschuss.
    """
    with pytest.raises(VenueUnavailableError, match="Kein Konto-Info"):
        _echt(_Mt5OhneKonto()).account()
    konto = _echt(_Mt5()).account()
    assert konto.is_demo is True
    assert konto.equity == Decimal("10000.0")


# --------------------------------------------------------------------------- #
# RealMt5Terminal.order_send: die Zweige des Sendens                            #
# --------------------------------------------------------------------------- #
def test_order_send_ohne_tick_meldet_no_tick() -> None:
    """2995->2996: ohne Preis wird nicht gesendet, und die Antwort sagt warum."""
    mt5 = _Mt5OhneTick()
    ergebnis = _echt(mt5).order_send(_terminal_auftrag())
    assert ergebnis.accepted is False
    assert ergebnis.reason == "no_tick"
    assert mt5.gesendet == []
    # Ohne Preis gibt es auch nichts zu buchen (Gegenlese T6, S3).
    assert ergebnis.filled_volume == Decimal("0")
    assert ergebnis.venue_order_id is None


def test_eine_limitorder_geht_als_pending_mit_wunschpreis_raus() -> None:
    """2997->3002 und 3028->3029: der Limit-Zweig und der mitgeschickte Take-Profit.

    Die annehmende Richtung daneben: die Marktorder nimmt den Ask und traegt keinen
    ``tp``, wenn keiner gewollt ist.
    """
    mt5 = _Mt5()
    _echt(mt5).order_send(
        _terminal_auftrag(
            order_type="limit",
            limit_price=Decimal("1.0900"),
            take_profit=Decimal("1.1200"),
        )
    )
    limit = mt5.gesendet[0]
    assert limit["action"] == _Mt5.TRADE_ACTION_PENDING
    assert limit["type"] == _Mt5.ORDER_TYPE_BUY_LIMIT
    assert limit["price"] == pytest.approx(1.09)
    assert limit["tp"] == pytest.approx(1.12)

    markt = _Mt5()
    _echt(markt).order_send(_terminal_auftrag())
    gesendet = markt.gesendet[0]
    assert gesendet["action"] == _Mt5.TRADE_ACTION_DEAL
    assert gesendet["price"] == pytest.approx(1.1)  # der Ask
    assert "tp" not in gesendet


@dataclass
class _Mt5BestandUnlesbar(_Mt5):
    """``_Mt5``, dessen Bestand nur MIT Ticket unlesbar ist.

    Die Frage vor dem Senden (``_bereits_beim_broker``) laeuft ohne Ticket und wird
    beantwortet; die Frage "welche Position schliesse ich?" laeuft mit Ticket und
    bleibt offen. Genau diese Trennung soll der Zweig treffen.
    """

    def positions_get(self, **kw: Any) -> Any:
        return None if "ticket" in kw else ()


def test_ein_unabfragbarer_bestand_verhindert_die_schliessung() -> None:
    """3043->3044: unbekannt heisst nicht senden -- sonst wird die Schliessung zur
    Gegenposition."""
    mt5 = _Mt5BestandUnlesbar()
    auftrag = _terminal_auftrag(
        side="sell", reduce_only=True, position_ticket="777", stop_loss=Decimal("0")
    )
    with pytest.raises(VenueUnavailableError, match="nicht abfragbar"):
        _echt(mt5).order_send(auftrag)
    assert mt5.gesendet == []


@dataclass
class _Mt5OhneErgebnis(_Mt5):
    """``_Mt5``, dessen ``order_send`` gar nichts zurueckgibt."""

    def order_send(self, req: Any) -> Any:
        self.gesendet.append(dict(req))
        return None


def test_ohne_ergebnis_lautet_der_grund_no_result() -> None:
    """3101->3107: der Server antwortet nicht -- das ist kein Fill und kein Kommentar.

    Die annehmende Richtung daneben: mit Ergebnis traegt der Grund den Kommentar und
    den Rueckgabecode.
    """
    mt5 = _Mt5OhneErgebnis()
    ergebnis = _echt(mt5).order_send(_terminal_auftrag())
    assert len(mt5.gesendet) == 1
    assert ergebnis.accepted is False
    assert ergebnis.reason == "no_result"
    assert ergebnis.venue_order_id is None
    assert ergebnis.filled_volume == Decimal("0")

    gut = _echt(_Mt5()).order_send(_terminal_auftrag())
    assert gut.accepted is True
    assert gut.reason == "done"
    # Die Kennung der Order gehoert zur annehmenden Richtung: ohne sie findet der
    # Abgleich die Order beim Broker nicht wieder (Gegenlese T6, S3).
    assert gut.venue_order_id == "555"

    # Der dritte Arm (angenommen=False, aber ein Ergebnis da): Kommentar UND
    # Rueckgabecode. Ohne den Code steht im Protokoll nur "Done" -- auch bei
    # Fehlschlaegen.
    class _Abgelehnt(_Mt5):
        def order_send(self, req: Any) -> Any:
            self.gesendet.append(dict(req))
            return _Ergebnis(retcode=10004, comment="Requote", order=0, volume=0.0)

    schlecht = _echt(_Abgelehnt()).order_send(_terminal_auftrag())
    assert schlecht.accepted is False
    assert schlecht.reason == "Requote (retcode=10004)"
    assert schlecht.venue_order_id is None


# --------------------------------------------------------------------------- #
# _stops_stehen: dreimal "nicht messbar heisst nicht belegt"                     #
# --------------------------------------------------------------------------- #
@dataclass
class _Mt5Nachlese(_Mt5):
    """``_Mt5`` mit einer Folge von Antworten auf ``positions_get``.

    ``modify_stops`` fragt zweimal: einmal vor dem Senden (der aktuelle Stand, aus
    dem ``sl``/``tp`` uebernommen werden) und einmal danach als Gegenprobe
    (``_stops_stehen``). ``kein_symbol_info=True`` laesst zusaetzlich ``symbol_info``
    leer laufen.
    """

    antworten: tuple[Any, ...] = ()
    kein_symbol_info: bool = False
    lesungen: int = 0

    def positions_get(self, **kw: Any) -> Any:
        nummer = self.lesungen
        self.lesungen += 1
        if nummer < len(self.antworten):
            return self.antworten[nummer]
        return ()

    def symbol_info(self, name: str) -> Any:
        if self.kein_symbol_info:
            return None
        return SimpleNamespace(filling_mode=1, point=0.00001)


def test_ein_verschobener_stop_wird_nachgelesen_und_belegt() -> None:
    """Bezugspunkt fuer die drei Ablehnungen: steht der Stop, ist die Antwort ``True``."""
    steht = _rohposition(sl=1.095)
    mt5 = _Mt5Nachlese(antworten=((_rohposition(),), (steht,)))
    assert _echt(mt5).modify_stops("777", Decimal("1.095"), None) is True


def test_eine_verschwundene_position_belegt_keinen_stop() -> None:
    """3252->3253: beim Nachlesen ist die Position weg -- "der Stop steht bei X" ist
    dann nicht mehr wahr."""
    mt5 = _Mt5Nachlese(antworten=((_rohposition(),), ()))
    assert _echt(mt5).modify_stops("777", Decimal("1.095"), None) is False


def test_ohne_symbol_info_ist_der_stop_nicht_belegbar() -> None:
    """3256->3257: ohne bekannte Preisstufe gibt es keinen Vergleich, also keinen Beleg."""
    mt5 = _Mt5Nachlese(
        antworten=((_rohposition(),), (_rohposition(sl=1.095),)),
        kein_symbol_info=True,
    )
    assert _echt(mt5).modify_stops("777", Decimal("1.095"), None) is False


def test_ein_nicht_gemeldeter_stop_ist_kein_beleg() -> None:
    """3267->3268: gewuenscht, aber vom Broker nicht gemeldet -- das ist kein Stop."""
    mt5 = _Mt5Nachlese(antworten=((_rohposition(),), (_rohposition(sl=None),)))
    assert _echt(mt5).modify_stops("777", Decimal("1.095"), None) is False


def test_die_frist_des_venues_gilt_auch_fuer_den_kursstrom() -> None:
    """Die zweite Bedingung von ``is_trading_open`` -- ohne sie waere der Bezugspunkt leer.

    ``test_ein_gesundes_sitzungsfenster_wird_nicht_beanstandet`` sagt ``True``. Das
    ist nur dann eine Aussage, wenn dasselbe Fenster mit einem alten Tick ``False``
    ergibt: sonst koennte die Sitzungstabelle allein antworten, und die Messung waere
    ein totes Tor. Hier ist der Tick eine Stunde alt, das Fenster unveraendert.
    """
    alt = _Terminal(jetzt=TS - timedelta(hours=1))
    venue = _venue_mit(
        alt,
        katalog=_katalog_mit_sitzung(
            TradingSession(weekday=1, open_utc="08:00", close_utc="22:00")
        ),
    )
    assert venue.is_trading_open("EURUSD", at=TS) is False


def test_die_geliehenen_bezugsgroessen_sind_die_erwarteten() -> None:
    """Kein Zweig, sondern die drei Annahmen, auf denen die Tests oben ruhen.

    * Der Katalog fuehrt GENAU EURUSD und BTCUSD. Kaeme GBPUSD hinzu, pruefte
      ``test_eine_position_ausserhalb_des_katalogs_ist_eine_unbewertbare_drift``
      nichts mehr -- das Symbol waere dann bekannt.
    * ``OrderType.MARKET`` heisst woertlich ``"market"``. ``_terminal_auftrag`` stellt
      diese Zeichenkette von Hand her, und ``RealMt5Terminal.order_send`` vergleicht
      gegen sie; liefe der Name auseinander, liefe jeder Auftrag oben in den
      Limit-Zweig, ohne dass ein Test es merkte.
    * Die Gebuehren stehen in USD wie das Fake-Konto -- sonst rechnete das Kostentor
      in ``test_ohne_kurs_faellt_das_kostentor_aus`` ueber eine Umrechnung.
    """
    assert set(_catalog()) == {"EURUSD", "BTCUSD"}
    assert OrderType.MARKET.value == "market"
    assert _fees().currency == "USD"
