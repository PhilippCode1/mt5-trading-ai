"""Roter Eichfall des Demo-Reifetors AM ORDER-PFAD (E7, zweite Ebene).

Der Befund: ``venue/demo_run.py`` rechnete die Laufzeit inzwischen selbst, aber
``Mt5Venue`` nahm weiter ein **fertiges** ``DemoReadiness`` als Konstruktorargument
entgegen und las nur dessen Ja/Nein. Damit war das 180-Tage-Tor am Order-Pfad
unveraendert mit einer Zeile auf::

    Mt5Venue(..., demo_readiness=DemoReadiness(True, ()))

Der freie ``elapsed_days`` war also nicht verschwunden, sondern eine Ebene hoeher
gewandert. Diese Datei misst das an der Stelle, an der es zaehlt: an einer
eroeffnenden **Live**-Order.

WARUM DIESE DATEI ANDERS GESCHRIEBEN IST ALS DER REST
-----------------------------------------------------
Sie soll gegen die **alte** Fassung laufen (``git archive`` in einen Temp-Ordner,
Testdatei hineinkopieren) und dort ehrlich mit einer *Assertion* fehlschlagen -- nicht
schon beim Import oder an einem ``TypeError`` zerbrechen. Ein Sammelfehler waere kein
Nachweis, dass die alte Fassung das Loch HAT, sondern nur, dass sie die neue API nicht
kennt. Darum werden dem Konstruktor per ``inspect.signature`` nur die Argumente
gereicht, die seine Fassung annimmt: die alte bekommt das fertige Urteil (so, wie ihr
Aufrufer es baute), die neue den Registrierungsbeleg. Beide Fassungen laufen durch
denselben Aufruf -- und geben verschiedene Antworten.

Die Bauteile (Fake-Terminal, Katalog, freigegebene Settings, Standard-Order) kommen aus
``test_mt5_venue`` und heissen in beiden Fassungen gleich.

Erwartung: alle drei Faelle hier sind gegen die alte Fassung ROT und gegen die neue
GRUEN.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue import demo_run
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.protocol import OrderRejectedError

from test_mt5_venue import (
    _LENIENT_COST_GATE,
    TS,
    FakeMt5Terminal,
    _catalog,
    _fresh_risk,
    _order,
    _released_settings,
)

#: Kontonummer des Fake-Terminals (in beiden Fassungen "123").
LIVE_KONTO = "123"


def _bestanden() -> EdgeVerdict:
    """Ein bestandener Edge -- damit NUR die Laufzeit entscheidet."""
    return EdgeVerdict(passed=True, checks=(), unmet=())


def _konto(nummer: str, *, ist_demo: bool = True) -> Any:
    """Kontoidentitaet, sofern die Fassung eine kennt. Die alte kennt keine."""
    typ = getattr(demo_run, "DemoAccount", None)
    return None if typ is None else typ(nummer, "Demo-Broker", ist_demo)


def _beleg(
    *,
    tage_alt: int,
    konto: str = "demo-9001",
    broker: str = "Demo-Broker",
    ist_demo: bool = True,
    strategy_id: str = "eurusd",
    version: str = "v1",
) -> Any:
    """Ein Registrierungsbeleg von vor ``tage_alt`` Tagen -- in beiden Fassungen
    baubar, weil die Felder aus dem Datentyp selbst gelesen werden."""
    felder = {f.name for f in dataclasses.fields(demo_run.DemoRegistration)}
    args: dict[str, Any] = {
        "strategy_id": strategy_id,
        "version": version,
        "registered_on": (TS - timedelta(days=tage_alt)).date(),
    }
    if "account" in felder:
        typ = demo_run.DemoAccount
        args["account"] = typ(konto, broker, ist_demo)
    return demo_run.DemoRegistration(**args)


def _altes_urteil(beleg: Any) -> Any:
    """Das Urteil, das die ALTE Fassung sich ausrechnen liess: mit frei behaupteter
    Laufzeit. Genau so stand es in ihrem einzigen Aufrufer."""
    erlaubt = inspect.signature(demo_run.evaluate_demo_progress).parameters
    angebot = {
        "registration": beleg,
        "elapsed_days": 400,
        "live_verdict": _bestanden(),
        "observed_account": _konto(LIVE_KONTO),
        "clock": lambda: TS,
    }
    return demo_run.evaluate_demo_progress(
        **{name: wert for name, wert in angebot.items() if name in erlaubt}
    )


def _demo_argumente(beleg: Any) -> dict[str, Any]:
    """Reiche dem Konstruktor, was seine Fassung annimmt."""
    params = inspect.signature(Mt5Venue.__init__).parameters
    if "demo_registration" in params:
        return {"demo_registration": beleg, "demo_live_verdict": _bestanden()}
    if "demo_readiness" in params:
        return {"demo_readiness": _altes_urteil(beleg)}
    return {}


def _live_venue(**demo_argumente: Any) -> tuple[Mt5Venue, FakeMt5Terminal]:
    terminal = FakeMt5Terminal(is_demo=False)
    venue = Mt5Venue(
        name="mt5-live",
        terminal=terminal,
        catalog=_catalog(),
        settings=_released_settings(),  # Live-Freigabe vollstaendig
        cost_gate=_LENIENT_COST_GATE,
        risk_manager=_fresh_risk(),
        clock=lambda: TS,
        **demo_argumente,
    )
    venue.connect()
    return venue, terminal


def _live_eroeffnung(venue: Mt5Venue) -> Any:
    return venue.submit_order(_order(volume=Decimal("0.01")))


def test_ein_behauptetes_ja_oeffnet_keine_live_order() -> None:
    """DER Eichfall: das Tor bekommt ein fertiges ``DemoReadiness(True, ())`` --
    kein Datum, keine verstrichene Zeit, nur eine Behauptung. Die alte Fassung glaubte
    sie und liess die Live-Order durch."""
    params = inspect.signature(Mt5Venue.__init__).parameters
    argumente: dict[str, Any] = {}
    if "demo_readiness" in params:
        argumente["demo_readiness"] = demo_run.DemoReadiness(
            ready_for_live_question=True, reasons=()
        )
    venue, terminal = _live_venue(**argumente)
    with pytest.raises(OrderRejectedError) as ex:
        _live_eroeffnung(venue)
    assert ex.value.reason == "demo_not_ready", (
        "ein behauptetes Reifeurteil hat die Live-Eroeffnung geoeffnet"
    )
    assert terminal.order_send_calls == 0


def test_eine_registrierung_von_heute_oeffnet_keine_live_order() -> None:
    """Dieselbe Frage einen Schritt frueher: der Beleg ist von HEUTE -- null Tage
    Demo-Betrieb. Die alte Fassung liess sich daraus (ueber ``elapsed_days=400``) ein
    reifes Urteil bauen und oeffnete."""
    venue, terminal = _live_venue(**_demo_argumente(_beleg(tage_alt=0)))
    with pytest.raises(OrderRejectedError) as ex:
        _live_eroeffnung(venue)
    assert ex.value.reason == "demo_not_ready", (
        "eine Registrierung von heute hat die Live-Eroeffnung geoeffnet"
    )
    assert terminal.order_send_calls == 0


@pytest.mark.parametrize(
    ("maengel", "erwarteter_grund"),
    [
        ({"strategy_id": "  "}, "strategie_id_fehlt"),
        ({"version": ""}, "strategie_version_fehlt"),
        ({"konto": " "}, "kontonummer_fehlt_im_beleg"),
        ({"broker": ""}, "broker_fehlt_im_beleg"),
        ({"ist_demo": False}, "registrierung_nicht_auf_demokonto"),
    ],
)
def test_ein_unvollstaendiger_beleg_oeffnet_keine_live_order(
    maengel: dict[str, Any], erwarteter_grund: str
) -> None:
    """Die Frist allein macht keinen Beleg. Ein Zeugnis ohne Strategie passt auf jede
    Strategie, eines ohne Konto auf jedes Konto, und ein Demo-Zeugnis, das auf einem
    Echtgeldkonto ausgestellt wurde, ist keins. 400 Tage aendern daran nichts -- die
    alte Fassung liess trotzdem oeffnen, weil sie von der Registrierung ueberhaupt
    nichts las."""
    venue, terminal = _live_venue(
        **_demo_argumente(_beleg(tage_alt=400, **maengel))
    )
    with pytest.raises(OrderRejectedError) as ex:
        _live_eroeffnung(venue)
    assert ex.value.reason == "demo_not_ready", (
        f"ein Beleg ohne {erwarteter_grund} hat die Live-Eroeffnung geoeffnet"
    )
    # Der Grund steht in der Meldung -- eine Ablehnung ohne nachpruefbaren Grund
    # wird im Betrieb weggeklickt. (Die alte Fassung kennt den Namen nicht; sie
    # scheitert schon eine Zeile hoeher.)
    assert erwarteter_grund in str(ex.value)
    assert terminal.order_send_calls == 0


def test_ein_beleg_auf_das_livekonto_oeffnet_keine_live_order() -> None:
    """Der Beleg behauptet, das Livekonto sei ein Demokonto, auf dem 400 Tage gelaufen
    sind. Das ist ein Widerspruch in sich -- und der naechstliegende Griff, wenn jemand
    einen Beleg passend machen will."""
    beleg = _beleg(tage_alt=400, konto=LIVE_KONTO)
    venue, terminal = _live_venue(**_demo_argumente(beleg))
    with pytest.raises(OrderRejectedError) as ex:
        _live_eroeffnung(venue)
    assert ex.value.reason == "demo_not_ready", (
        "ein Demo-Beleg auf das Livekonto hat die Live-Eroeffnung geoeffnet"
    )
    assert terminal.order_send_calls == 0
