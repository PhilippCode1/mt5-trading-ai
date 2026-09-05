"""Die Grenzfaelle, an denen der Geldpfad kippt -- je einer je ueberlebender Sonde.

WARUM DIESE DATEI
-----------------
Das Mutationstor (``tools/mutationstor.py``, Katalog A4/A17) baut Defekte in den
Geldpfad ein und fragt, ob ein Test sie bemerkt. Im Lauf vom 2026-09-04 ueberlebten
zwoelf erzeugte Sonden (Toetungsrate 0,836 bei Schwelle 0,90). Alle zwoelf sind
Grenzwerte: ``>`` wird ``>=``, ``<`` wird ``<=``, ``or`` wird ``and``, ``0`` wird ``1``.
Genau dort entscheidet sich, ob eine Order bei *exakt* dem Grenzwert noch durchgeht --
die Stelle, an der ein Fehler auf einem Handelskonto Geld kostet und beim Testen mit
runden Zahlen nie auffaellt.

Ein dreizehnter Fall kam aus dem Lauf danach dazu (``risk_manager.py:605``: das
Nachziehen des juengeren Zeitstempels).

Jeder Fall hier setzt den Wert **auf** die Grenze und sichert die Antwort zu, die nur
das unveraenderte Programm gibt. Belegt: jede Zusicherung wurde gegen ihren Mutanten
gefahren (Beleg ``06-mutationsgrenzen.txt``); ohne sie bleibt die Sonde gruen.

ZWEI SONDEN SIND NICHT ZU TOETEN -- UND DAS IST KEIN LOCH
--------------------------------------------------------
* ``execution/risk_manager.py:601`` ``if lage.trades_konto > self._trades_today_account:
  self._trades_today_account = lage.trades_konto``. Bei Gleichheit weist der Rumpf den
  Wert zu, den das Feld schon traegt. ``>`` und ``>=`` sind verhaltensgleich.
* ``risk/leverage.py:248`` ``if value is None or value == "":`` in ``_as_int``. Mit
  ``and`` faellt ``None`` in den ``try``-Block, ``int(float(None))`` wirft ``TypeError``,
  und der ``except``-Zweig liefert dasselbe ``None``. Ebenfalls verhaltensgleich.

Beides ist gemessen -- jede Sonde einzeln gegen die volle Suite, mit Basislauf derselben
Kopie (``belege/06-mutationsgrenzen.txt``, 2026-09-05) -- und in ``tools/mutationstor.py``
als ``AEQUIVALENT`` eingetragen: eine Mutation, die das Verhalten nicht aendern **kann**, ist kein
Testloch. Sie wird nicht mehr gezogen -- die Schwelle bleibt bei 0,90.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from mt5_trading_ai.execution.handelspause import wochenbloecke
from mt5_trading_ai.execution.reconcile import PositionBook
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand, RisikoLage
from mt5_trading_ai.execution.risk_manager import RiskManager, RiskPolicy
from mt5_trading_ai.gates.erkundung import entscheide_erkundung
from mt5_trading_ai.risk.limits import AccountSnapshot, LossLimits, evaluate_limits
from mt5_trading_ai.risk.sizing import StopFloorInputs, executable_stop_floor
from mt5_trading_ai.risk.stop_budget import stop_budget
from mt5_trading_ai.venue.mt5 import _ablage_waehlen, _send_gefuellt
from mt5_trading_ai.venue.protocol import TradingSession

JETZT = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# venue/mt5.py:377 -- 'or' -> 'and': eine Ablage allein reicht nicht            #
# --------------------------------------------------------------------------- #
def test_eine_ablage_allein_ist_kein_zustand() -> None:
    """Ohne Zustandsordner muessen BEIDE Ablagen genannt sein (D8).

    Mit ``and`` verlangte die Sperre nur, dass nicht beide fehlen: ein Venue mit
    Schwebeakte, aber ohne Positionsbuch entstuende -- und stuerzte beim ersten Fill
    ab, statt beim Bauen zu sagen, was fehlt.
    """
    from mt5_trading_ai.execution.risiko_zustand import ZustandsortFehler
    from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte

    with pytest.raises(ZustandsortFehler, match="beide Ablagen"):
        _ablage_waehlen(
            zustandsordner=None,
            schwebeakte=FluechtigeSchwebeAkte(),
            positionsbuch=None,
        )
    with pytest.raises(ZustandsortFehler, match="beide Ablagen"):
        _ablage_waehlen(zustandsordner=None, schwebeakte=None, positionsbuch=None)


# --------------------------------------------------------------------------- #
# venue/mt5.py:2299 -- 'or' -> 'and': eine Kennung genuegt als Beleg            #
# --------------------------------------------------------------------------- #
def test_eine_ordernummer_ohne_abschlussnummer_gilt_als_ausgefuehrt() -> None:
    """``_send_gefuellt`` bei ``retcode == 0``: EINE der beiden Nummern genuegt.

    Mit ``and`` muessten Order- UND Abschlussnummer gesetzt sein. Ein Broker, der bei
    Erfolg nur die Ordernummer fuellt (Pending-Storno, Teilausfuehrung ohne Deal),
    saehe dann aus wie ein Fehlschlag -- und der Auftrag liefe doppelt.
    """
    mt5 = SimpleNamespace(TRADE_RETCODE_DONE=10009, TRADE_RETCODE_PLACED=10008)

    # ``volume > 0`` ist die Vorbedingung der Funktion; sie steht vor dieser Zeile.
    nur_order = SimpleNamespace(retcode=0, order=555, deal=0, volume=0.1)
    nur_deal = SimpleNamespace(retcode=0, order=0, deal=556, volume=0.1)
    nichts = SimpleNamespace(retcode=0, order=0, deal=0, volume=0.1)

    assert _send_gefuellt(mt5, nur_order) is True
    assert _send_gefuellt(mt5, nur_deal) is True
    assert _send_gefuellt(mt5, nichts) is False, (
        "ohne jede Kennung belegt retcode=0 keine Ausfuehrung"
    )


# --------------------------------------------------------------------------- #
# risk/sizing.py:114 -- '<' -> '<=': die Tiefenschwelle liegt AUF 0,35          #
# --------------------------------------------------------------------------- #
def test_die_tiefe_genau_auf_der_schwelle_zaehlt_als_mittlere_tiefe() -> None:
    """``depth_ratio == 0.35`` ist nicht mehr "duenn": der Aufschlag faellt 15 -> 8.

    Mit ``<=`` bliebe der Aufschlag der duennen Tiefe stehen. Der Stop laege dann
    weiter weg als noetig, die Position kleiner -- ein stiller Verlust an Groesse an
    genau der Kante, an der die Tabelle wechselt.
    """

    def tiefe(ratio: float) -> Decimal:
        floor = executable_stop_floor(
            StopFloorInputs(
                spread_bps=Decimal("0"),
                tick_size_bps=Decimal("0"),
                volatility_bps=Decimal("0"),
                broker_stop_level_bps=Decimal("0"),
                depth_ratio=ratio,
            )
        )
        return floor.components["depth"]

    assert tiefe(0.34) == Decimal("15")
    assert tiefe(0.35) == Decimal("8"), "auf der Schwelle gilt die naechste Stufe"
    assert tiefe(0.55) == Decimal("0")


# --------------------------------------------------------------------------- #
# risk/stop_budget.py:329 -- '>' -> '>=': Boden GLEICH Decke ist handelbar      #
# --------------------------------------------------------------------------- #
def test_kostenboden_genau_auf_der_margendecke_bleibt_handelbar() -> None:
    """Boden == Decke laesst genau eine Stopdistanz zu -- das ist eine Spanne.

    Mit ``>=`` waere dieselbe Lage ``cost_floor_above_margin_ceiling`` und damit
    nicht handelbar: eine Order, die die Regel erfuellt, wuerde abgewiesen.
    """
    budget = stop_budget(
        asset_class="fx_major",
        leverage=20,
        measured_cost_bps=Decimal("5.000"),
        safety=Decimal("5"),
    )

    assert budget.lower_bps == budget.upper_bps == Decimal("50.0")
    assert budget.tradeable is True
    assert budget.reason != "cost_floor_above_margin_ceiling"


# --------------------------------------------------------------------------- #
# risk/limits.py:160 -- '<=' -> '<': das Gap-Ereignis JETZT sperrt              #
# --------------------------------------------------------------------------- #
def test_ein_gap_ereignis_genau_jetzt_sperrt_die_eroeffnung() -> None:
    """Abstand null ist der kleinste Abstand, nicht "kein Ereignis".

    Mit ``<`` liefe die Sperre erst ab einer Sekunde Abstand -- und der Takt, der das
    Ereignis genau trifft, eroeffnete hinein.
    """

    def urteil(abstand: timedelta) -> tuple[str, ...]:
        schnappschuss = AccountSnapshot(
            now=JETZT,
            equity=Decimal("10000"),
            day_start_equity=Decimal("10000"),
            window_peak_equity=Decimal("10000"),
            open_positions=0,
            trading_day=date(2026, 9, 4),
            upcoming_gap_events=(JETZT + abstand,),
        )
        return evaluate_limits(snapshot=schnappschuss, limits=LossLimits()).reasons

    assert "gap_blackout" in urteil(timedelta(0)), "das Ereignis jetzt sperrt"
    assert "gap_blackout" in urteil(timedelta(hours=4))
    assert "gap_blackout" not in urteil(timedelta(hours=4, seconds=1))
    assert "gap_blackout" not in urteil(timedelta(seconds=-1)), "vorbei ist vorbei"


# --------------------------------------------------------------------------- #
# gates/erkundung.py:183 -- '<' -> '<=': der Wurf GLEICH der Rate verliert      #
# --------------------------------------------------------------------------- #
def test_ein_wurf_genau_auf_der_rate_erkundet_nicht() -> None:
    """``wurf < rate``: bei Gleichheit wird NICHT erkundet.

    Der Wurf ist der Hash des Schluessels auf [0, 1). Mit ``<=`` waere die
    Erkundungswahrscheinlichkeit um genau einen Wurf groesser als die protokollierte
    Rate -- die Auswertung gewichtete dann mit einer Zahl, die nicht stimmt.
    """
    schluessel = "EURUSD|BUY|2026-09-04T10:00:00+00:00"
    roh = hashlib.sha256(schluessel.encode("utf-8")).digest()[:8]
    wurf = int.from_bytes(roh, "big") / float(1 << 64)
    assert 0.0 < wurf < 1.0

    auf_der_kante = entscheide_erkundung(
        ist_papierkonto=True,
        ablehnungsgrund="strategy_not_admitted",
        schluessel=schluessel,
        rate=wurf,
    )
    assert auf_der_kante.erkunden is False, "gleich ist nicht kleiner"
    assert auf_der_kante.wahrscheinlichkeit == wurf

    knapp_darueber = entscheide_erkundung(
        ist_papierkonto=True,
        ablehnungsgrund="strategy_not_admitted",
        schluessel=schluessel,
        rate=wurf + 1e-9,
    )
    assert knapp_darueber.erkunden is True


# --------------------------------------------------------------------------- #
# execution/handelspause.py:119 -- '>' -> '>=': das Fenster endet AUF der Woche #
# --------------------------------------------------------------------------- #
def test_ein_fenster_das_genau_am_wochenende_endet_wird_nicht_umgebrochen() -> None:
    """Sonntag 00:00-24:00 endet exakt am Wochenende -- ein Stueck, nicht zwei.

    Mit ``>=`` entstuende zusaetzlich das leere Stueck ``(0, 0)`` am Wochenanfang.
    Ein Fenster ohne Dauer ist keine Handelszeit, und die Pausenrechnung stolpert
    darueber: sie sucht das Ende des laufenden Fensters.
    """
    genau = wochenbloecke(
        (TradingSession(weekday=6, open_utc="00:00", close_utc="24:00"),)
    )
    assert genau == ((6 * 1440, 7 * 1440),), genau

    ueber = wochenbloecke(
        (TradingSession(weekday=6, open_utc="22:00", close_utc="06:00"),)
    )
    assert ueber == ((0, 360), (6 * 1440 + 1320, 7 * 1440)), ueber


# --------------------------------------------------------------------------- #
# execution/reconcile.py:63 -- '0' -> '1': eine Position mit Menge 1 zaehlt     #
# --------------------------------------------------------------------------- #
def test_eine_position_der_groesse_eins_ueberlebt_die_adoption() -> None:
    """``net != 0`` wirft nur die glattgestellten Symbole weg.

    Mit ``!= 1`` fiele ausgerechnet die Position mit Menge 1,0 aus dem Buch -- sie
    laege beim Broker, und der Deckel zaehlte sie nicht mehr.
    """
    buch = PositionBook()
    buch.adopt(
        {
            "EURUSD": Decimal("1"),
            "XAUUSD": Decimal("0.5"),
            "US500": Decimal("0"),
            "GBPUSD": Decimal("-1"),
        }
    )

    assert buch.snapshot() == {
        "EURUSD": Decimal("1"),
        "XAUUSD": Decimal("0.5"),
        "GBPUSD": Decimal("-1"),
    }
    assert buch.net("EURUSD") == Decimal("1")
    assert buch.net("US500") == Decimal("0")


# --------------------------------------------------------------------------- #
# execution/risk_manager.py:918 -- '>' -> '>=': derselbe Drawdown verbraucht    #
# die Freigabe NICHT                                                            #
# --------------------------------------------------------------------------- #
def _konto(equity: str, peak: str = "10000") -> AccountSnapshot:
    return AccountSnapshot(
        now=JETZT,
        equity=Decimal(equity),
        day_start_equity=Decimal(peak),
        window_peak_equity=Decimal(peak),
        open_positions=0,
        trading_day=date(2026, 9, 4),
    )


def test_derselbe_drawdown_verbraucht_die_manuelle_freigabe_nicht() -> None:
    """Die Freigabe gilt fuer die Lage, ueber die entschieden wurde -- und fuer die
    gleich tiefe danach. Erst eine TIEFERE Lage ist eine andere.

    Mit ``>=`` verfiele die Freigabe beim naechsten Takt mit demselben Drawdown; der
    Betrieb stuende, obwohl der Mensch gerade freigegeben hat.
    """
    kern = RiskManager(zustand=FluechtigerZustand(), policy=RiskPolicy())

    kern.release_drawdown("freigabe-1")
    kern._freigabe_episode_pflegen(Decimal("0.12"))  # erste Lage: Decke gesetzt
    assert kern._manual_release_id == "freigabe-1"

    kern._freigabe_episode_pflegen(Decimal("0.12"))  # gleich tief: bleibt
    assert kern._manual_release_id == "freigabe-1", "gleich tief ist dieselbe Lage"

    kern._freigabe_episode_pflegen(Decimal("0.13"))  # tiefer: verbraucht
    assert kern._manual_release_id is None


# --------------------------------------------------------------------------- #
# venue/mt5.py:1582 -- '0' -> '1': der Spread eines Symbols unter 1             #
# --------------------------------------------------------------------------- #
def test_der_spread_eines_symbols_unter_eins_erreicht_die_risikoschicht() -> None:
    """``mid > 0`` heisst: es gibt einen Preis. Mit ``mid > 1`` waere fuer jeden Kurs
    unter 1,0 (EURGBP 0,85, USDCHF 0,89) der Spread 0 -- die Risikoschicht saehe ein
    kostenloses Instrument und liesse jede Order durch.

    Gefahren wird die echte Zeile in ``Mt5Venue._enforce_risk``; der Spread wird an
    der Naht abgegriffen, an der er ankommt (Gegenlese: eine nachgebaute Rechnung im
    Test toetet den Mutanten nicht -- sie prueft den Nachbau).
    """
    from test_zweige_mt5 import _order, _Terminal, _venue_mit

    gesehen: list[Decimal] = []

    class _RisikoSpion:
        """Faengt den Spread ab und weist danach ab -- weiter muss der Pfad nicht."""

        def authorize_opening(self, **kwargen: Any) -> Any:
            gesehen.append(kwargen["spread_bps"])
            raise AssertionError("abgegriffen")

    class _UnterEins(_Terminal):
        """Ein Kurs unter 1,0 -- wie EURGBP oder USDCHF am echten Terminal."""

        def tick(self, name: str) -> Any:
            roh = super().tick(name)
            if roh is None:
                return None
            return dataclasses.replace(
                roh, bid=Decimal("0.8499"), ask=Decimal("0.8501")
            )

    venue = _venue_mit(_UnterEins(), risk_manager=_RisikoSpion())  # type: ignore[arg-type]

    with pytest.raises(AssertionError, match="abgegriffen"):
        venue.submit_order(_order())

    assert gesehen, "die Risikoschicht wurde nicht erreicht"
    assert gesehen[0] == pytest.approx(Decimal("2.3529"), abs=Decimal("0.001")), (
        f"Spread bei mid 0,85: {gesehen[0]} -- mit dem Mutanten waere er 0"
    )


# --------------------------------------------------------------------------- #
# execution/risk_manager.py:605 -- 'not' davor: der juengere Zeitstempel gewinnt #
# --------------------------------------------------------------------------- #
def test_der_juengere_letzte_trade_gewinnt_beim_nachziehen() -> None:
    """``_nachziehen`` holt den Stand eines zweiten Prozesses in den Speicher --
    ausschliesslich in die strenge Richtung. Fuer den letzten Trade heisst streng:
    der JUENGERE Zeitstempel, denn er haelt die Drossel laenger geschlossen.

    Mit einem ``not`` vor der Bedingung uebernaehme der Lauf den AELTEREN Stempel und
    liesse ein Symbol ohne Eintrag ganz aus -- die Abkuehlzeit liefe dann zu frueh ab,
    und der naechste Auftrag ginge vor der Zeit raus.
    """
    kern = RiskManager(zustand=FluechtigerZustand(), policy=RiskPolicy())
    kern._last_trade_at["EURUSD"] = JETZT
    kern._last_trade_at["XAUUSD"] = JETZT

    kern._nachziehen(
        RisikoLage(
            letzter_trade_at={
                "EURUSD": JETZT + timedelta(minutes=5),  # juenger: gewinnt
                "XAUUSD": JETZT - timedelta(minutes=5),  # aelter: verliert
                "US500": JETZT,  # noch unbekannt: wird uebernommen
            }
        )
    )

    assert kern._last_trade_at == {
        "EURUSD": JETZT + timedelta(minutes=5),
        "XAUUSD": JETZT,
        "US500": JETZT,
    }


# --- venue/mt5.py:1066  ``if request.stop_loss <= 0``  ('0' -> '1' ueberlebte) ----


def test_ein_stop_zwischen_null_und_eins_ist_ein_gueltiger_stop() -> None:
    """Gegenlese T10, E16: die Sonde ``stop_loss <= 1`` ueberlebte am HEAD (CI-Lauf
    33977291625). Kein Test eroeffnete mit einem Stop unter 1,0 -- der Kurs von
    EURGBP, USDCHF oder AUDUSD. Mit der Sonde waere jede Eroeffnung in diesen
    Instrumenten "ohne Stop" abgewiesen, und die Suite haette es nicht bemerkt.

    Der Stop 0,99 muss AN DIESEM TOR vorbei (was spaetere Tore sagen, ist hier
    gleichgueltig); der Stop 0 und ein negativer Stop bleiben genau hier stehen.
    """
    from mt5_trading_ai.venue.protocol import OrderRejectedError

    from test_mt5_venue import _order
    from test_zweige_mt5 import _Terminal, _venue_mit

    for stop, erwartet_missing in (
        (Decimal("0.99"), False),
        (Decimal("0.00001"), False),
        (Decimal("0"), True),
        (Decimal("-1"), True),
    ):
        venue = _venue_mit(_Terminal())
        grund: str | None = "angenommen"
        try:
            venue.submit_order(_order(stop_loss=stop))
        except OrderRejectedError as abgelehnt:
            grund = abgelehnt.reason
        if erwartet_missing:
            assert grund == "missing_stop_loss", (stop, grund)
        else:
            assert grund != "missing_stop_loss", (
                f"Stop {stop} wurde als fehlender Stop abgewiesen -- das Tor prueft "
                "gegen 1 statt gegen 0"
            )
