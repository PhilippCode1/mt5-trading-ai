"""Die GRENZE des Demo-Reifetors, festgenagelt -- damit sie keine Dichtigkeit wird.

Das Reifetor am Order-Pfad rechnet die 180 Tage selbst, aus ``registered_on`` und der
Uhr des Venues. Was es damit belegt, ist genau eines: das im Beleg **genannte**
Anfangsdatum liegt weit genug zurueck. Was es nicht belegt: dass an diesem Tag
irgendetwas begonnen hat. ``DemoRegistration`` ist ein offener frozen-dataclass, und wer
ihn selbst baut, setzt das Datum frei.

Diese Datei sagt beides in Tests, weil ein Docstring allein verrottet:

* ``test_ein_selbst_gebauter_beleg_oeffnet_die_live_order`` haelt die Grenze fest. Wird
  er eines Tages rot, ist ein Zeuge dazugekommen -- dann gehoert der Abschnitt
  "DIE GRENZE DIESER STUFE" in ``venue/demo_run.py`` umgeschrieben, nicht dieser Test
  angepasst.
* die uebrigen halten fest, was das Tor sehr wohl faengt, und jeder einzelne ist gegen
  eine Verfaelschung der geprueften Stelle rot.

Alle Daten sind von Hand vorgerechnet und stehen als Rechnung im Test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue.demo_run import (
    MIN_DEMO_DAYS,
    DemoAccount,
    DemoRegistration,
    pruefe_demo_beleg,
)
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

#: Kontonummer des Fake-Terminals. Ein Demo-Beleg auf DIESE Nummer waere ein
#: Widerspruch und faellt an einer eigenen Sperre -- die Belege hier tragen eine andere.
LIVE_KONTO = "123"

#: TS ist der 2026-08-11. Von Hand: 2026-08-11 minus 365 Tage = 2025-08-11, minus
#: weitere 35 Tage (24 Resttage im Juli + 11) = 2025-07-07. Also 400 Tage vor TS.
VOR_400_TAGEN = date(2025, 7, 7)

#: Von Hand: 2026-08-11 - 11 = 2026-07-31 (11), -31 = 2026-06-30 (42), -30 =
#: 2026-05-31 (72), -31 = 2026-04-30 (103), -30 = 2026-03-31 (133), -31 =
#: 2026-02-28 (164), -16 = 2026-02-12 (180). Genau MIN_DEMO_DAYS vor TS.
VOR_180_TAGEN = date(2026, 2, 12)


def _bestanden() -> EdgeVerdict:
    return EdgeVerdict(passed=True, checks=(), unmet=())


def _demokonto(nummer: str = "demo-9001") -> DemoAccount:
    return DemoAccount(account_id=nummer, broker="Demo-Broker", is_demo=True)


def _selbst_gebaut(registered_on: Any, *, konto: str = "demo-9001") -> Any:
    """Ein Beleg aus zwei Konstruktorzeilen -- ``register_for_demo`` nie gerufen."""
    return DemoRegistration(
        strategy_id="eurusd",
        version="v1",
        registered_on=registered_on,
        account=_demokonto(konto),
    )


def _live_venue(beleg: Any) -> tuple[Mt5Venue, FakeMt5Terminal]:
    terminal = FakeMt5Terminal(is_demo=False)
    venue = Mt5Venue(
        name="mt5-live",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=_catalog(),
        settings=_released_settings(),
        cost_gate=_LENIENT_COST_GATE,
        risk_manager=_fresh_risk(),
        demo_registration=beleg,
        demo_live_verdict=_bestanden(),
        clock=lambda: TS,
    )
    venue.connect()
    return venue, terminal


def test_die_vorgerechneten_daten_stimmen() -> None:
    """Erst die Rechnung pruefen, dann mit ihr messen.

    Ohne diesen Fall koennte eine falsch abgezaehlte Konstante oben die Aussage aller
    folgenden Faelle still verschieben.
    """
    assert (TS.date() - VOR_400_TAGEN).days == 400
    assert (TS.date() - VOR_180_TAGEN).days == MIN_DEMO_DAYS == 180


def test_ein_selbst_gebauter_beleg_oeffnet_die_live_order() -> None:
    """DIE GRENZE, ausgesprochen: zwei Konstruktorzeilen reichen.

    Kein ``register_for_demo``, keine verstrichene Zeit, nur ein Datum. Das Tor laesst
    die Live-Eroeffnung durch, weil es das Datum nicht pruefen kann -- ein Zeuge dafuer
    muesste von der anderen Seite der Leitung kommen, und dort steht das Livekonto.

    Wird dieser Fall rot, ist genau das nicht mehr wahr. Dann ist der Docstring in
    ``venue/demo_run.py`` (Abschnitt "DIE GRENZE DIESER STUFE") falsch geworden und
    gehoert umgeschrieben -- der Test ist die Meldung, nicht der Fehler.
    """
    venue, terminal = _live_venue(_selbst_gebaut(VOR_400_TAGEN))
    ergebnis = venue.submit_order(_order(volume=Decimal("0.01")))
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1, (
        "Wenn hier nichts mehr gesendet wird, traegt der Beleg inzwischen seine "
        "Herkunft -- dann ist die Grenze im Modul-Docstring nachzuziehen."
    )


def test_ein_zeitpunkt_statt_eines_tages_ist_kein_beleg() -> None:
    """Ein ``datetime`` in ``registered_on`` wird abgelehnt, nicht durchgereicht.

    ``datetime`` ist eine Unterklasse von ``date``; der Typ haelt das nicht ab. Vorher
    zerbrach die Zeitrechnung deshalb an ``date - datetime`` mit einem nackten
    ``TypeError`` mitten im Order-Pfad -- eine Ausnahme, die kein Aufrufer als
    Ablehnungsgrund lesen kann.

    Gewaehlt ist bewusst ein Zeitpunkt, der als Tag laengst reif WAERE (400 Tage, siehe
    ``test_die_vorgerechneten_daten_stimmen``): abgelehnt wird also die Form, nicht das
    Alter.
    """
    zeitpunkt = datetime(2025, 7, 7, 12, 0, tzinfo=UTC)
    assert (TS.date() - zeitpunkt.date()).days == 400  # als Tag waere er reif
    venue, terminal = _live_venue(_selbst_gebaut(zeitpunkt))
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(volume=Decimal("0.01")))
    assert ex.value.reason == "demo_not_ready"
    assert "registrierungsdatum_ist_kein_kalendertag" in str(ex.value)
    assert terminal.order_send_calls == 0


def test_der_kalendertag_melder_ist_keine_dauerbremse() -> None:
    """Gegenprobe zum Fall darueber: derselbe Tag als ``date`` kommt durch.

    Ein Melder, der immer ausloest, sagt so wenig wie einer, der nie ausloest.
    """
    venue, terminal = _live_venue(_selbst_gebaut(date(2025, 7, 7)))
    assert venue.submit_order(_order(volume=Decimal("0.01"))).accepted is True
    assert terminal.order_send_calls == 1


def test_die_frist_faellt_genau_zwischen_179_und_180_tagen() -> None:
    """Die Kante, von Hand gerechnet -- an beiden Seiten gemessen.

    180 Tage vor dem 2026-08-11 ist der 2026-02-12 (Rechnung oben bei
    ``VOR_180_TAGEN``); einen Tag spaeter, am 2026-02-13, sind es 179.
    """
    reif, reif_terminal = _live_venue(_selbst_gebaut(VOR_180_TAGEN))
    assert reif.submit_order(_order(volume=Decimal("0.01"))).accepted is True
    assert reif_terminal.order_send_calls == 1

    knapp, knapp_terminal = _live_venue(_selbst_gebaut(date(2026, 2, 13)))
    with pytest.raises(OrderRejectedError) as ex:
        knapp.submit_order(_order(volume=Decimal("0.01")))
    assert ex.value.reason == "demo_not_ready"
    assert "demo_zu_kurz_179_von_180_tagen" in str(ex.value)
    assert knapp_terminal.order_send_calls == 0


@pytest.mark.parametrize(
    "beginn",
    [
        pytest.param(datetime(2025, 7, 7, 12, 0, tzinfo=UTC), id="zonenbewusst"),
        pytest.param(datetime(2025, 7, 7, 0, 0), id="naiv"),
    ],
)
def test_der_melder_nennt_die_form_und_rechnet_nicht_weiter(beginn: Any) -> None:
    """Auch im schmalen Rechner: ein Zeitpunkt liefert einen Grund, keine Ausnahme.

    Und er liefert **nur** diesen Grund zur Zeit -- es wird nicht zusaetzlich eine
    Laufzeit gemeldet, die sich gar nicht bilden liess.
    """
    urteil = pruefe_demo_beleg(
        registration=_selbst_gebaut(beginn),
        live_verdict=_bestanden(),
        clock=lambda: TS,
    )
    assert urteil.ready_for_live_question is False
    assert "registrierungsdatum_ist_kein_kalendertag" in urteil.reasons
    assert not [g for g in urteil.reasons if g.startswith("demo_zu_kurz")]
    assert not [g for g in urteil.reasons if g.startswith("registrierung_in_der")]


def test_ein_datum_von_morgen_reift_nichts() -> None:
    """Die Zukunftskante, die verhindert, dass "zu kurz" die einzige Frage bleibt."""
    urteil = pruefe_demo_beleg(
        registration=_selbst_gebaut(TS.date() + timedelta(days=1)),
        live_verdict=_bestanden(),
        clock=lambda: TS,
    )
    assert urteil.ready_for_live_question is False
    assert "registrierung_in_der_zukunft_1_tage" in urteil.reasons
