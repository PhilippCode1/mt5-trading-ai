"""Rote Eichfaelle: der Risikozustand ueberdauert einen Neustart.

Diese Datei war bis D8 absichtlich frei von jedem Import des Zustandsmoduls und
schaltete die Dauerhaftigkeit ueber die Umgebungsvariable ``MT5_RISIKO_ZUSTAND`` ein,
damit sie gegen den Stand 5e7c4f7 an einer **Zusicherung** fiel und nicht an einem
``ImportError``. Seit D8 (E-005) gibt es die Variable nicht mehr: der Ort ist ein
Konstruktorargument (``zustand=DateiZustand(...)`` in ``tmp_path``), und die Messungen
unten gelten fuer den Stand, an dem sie gemacht wurden.

Gemessen gegen HEAD (``git archive 5e7c4f7`` schreibfrei in einen Temp-Ordner
ausgepackt, diese Datei hineinkopiert, dort ``pytest`` gefahren): **9 failed,
1 passed**. Jeder rote Fall reisst an einer Zusicherung (``assert True is False``,
``assert 24 == 10``, ``DID NOT RAISE ValueError``), keiner am Sammeln. Der eine gruene
ist die Gegenprobe zur Freigabe -- sie ist gegen HEAD per Konstruktion gruen, weil dort
ueberhaupt nichts haelt, was freigegeben werden muesste, und steht hier nur, damit die
neue Sperre einen belegten Ausgang hat.

Die Eichfaelle 4 bis 7 gehoeren zur **Reparaturwelle** danach: sie halten die fuenf
Befunde der Gegenprobe fest (leere Freigabe, Ort der Datei, Peak vor der ersten Order,
Schreibfehler im Order-Pfad). Sie sind darum ein zweites Mal gemessen worden -- gegen
denselben HEAD-Auszug, in den zusaetzlich die **unreparierten** Fassungen von
``execution/risiko_zustand.py`` und ``execution/risk_manager.py`` kopiert wurden: dort
**5 failed, 5 passed**, und die fuenf roten sind genau diese vier neuen Faelle samt
ihrer Gegenprobe. Die vier alten Eichfaelle sind dort gruen. Das trennt die beiden
Wellen sauber: die alten Faelle messen die Zustandshaltung, die neuen ihre Reparatur.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.execution.risiko_zustand import (
    DateiZustand,
    FluechtigerZustand,
    zustandsordner_pruefen,
)
from mt5_trading_ai.execution.risk_manager import (
    RiskAuthorization,
    RiskManager,
    RiskPolicy,
)
from mt5_trading_ai.gates.evaluation import ThrottlePolicy
from mt5_trading_ai.venue.protocol import (
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
KONTO = "50123456"


def _instrument() -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="mt5",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        fees=FeeSchedule(
            commission_per_lot_round_turn=Decimal("7"),
            typical_spread_points=Decimal("6"),
            swap_long_per_lot_per_night=Decimal("-2"),
            swap_short_per_lot_per_night=Decimal("-1"),
            triple_swap_weekday=2,
            currency="USD",
        ),
        sessions=(),
    )


def _account(
    equity: str = "10000", *, waehrung: str = "USD", konto: str = KONTO
) -> AccountState:
    return AccountState(
        account_id=konto,
        currency=waehrung,
        balance=Decimal(equity),
        equity=Decimal(equity),
        margin_used=Decimal("0"),
        margin_free=Decimal(equity),
        is_demo=True,
        ts=NOW,
    )


def _request() -> OrderRequest:
    return OrderRequest(
        client_order_id="c-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("1.09000"),
    )


def _autorisiere(
    rm: RiskManager, *, account: AccountState, now: datetime = NOW
) -> RiskAuthorization:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=_request(),
        account=account,
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def _zustand(tmp_path) -> DateiZustand:  # type: ignore[no-untyped-def]
    """Die Dauerhaftigkeit auf eine Datei im Temp-Verzeichnis -- je Aufruf ein
    frischer ``DateiZustand`` auf derselben Datei, also ein Prozessstart.

    Ausdruecklich ueber ``tmp_path``: kein Test dieses Repos darf an einer Datei
    haengen, die nicht versioniert ist -- weder an ``TRIALS.jsonl`` noch an
    ``betrieb/*.jsonl`` noch am Zustandsverzeichnis des Benutzers (A10).
    """
    return DateiZustand(tmp_path / "risikozustand.json")


# --- Eichfall 1: der Drawdown-Halt ueberdauert den Neustart ---------------------


def test_eichfall_drawdown_halt_ueberdauert_den_neustart(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD: dort war ``a2.approved is True``.

    Lauf 1 haelt bei 16,7 % Drawdown an. Lauf 2 ist ein **neuer Prozess** und sieht
    eine voll erholte Equity -- ohne dauerhaften Halt waere der Drawdown dort null und
    die Order ginge durch. Genau das ist „ein System, das sich nach einem
    Drawdown-Halt selbst wieder freischaltet" (``risk/limits.py``).
    """
    lauf1 = RiskManager(zustand=_zustand(tmp_path))
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    a1 = _autorisiere(lauf1, account=_account("10000"))
    assert a1.approved is False
    assert a1.latch_halt is True

    # --- Neustart: neuer Prozess, gleiche Zustandsdatei, erholte Equity ---
    lauf2 = RiskManager(zustand=_zustand(tmp_path))
    a2 = _autorisiere(lauf2, account=_account("12000"), now=NOW + timedelta(minutes=5))
    assert a2.approved is False
    assert a2.latch_halt is True
    assert a2.reason == "risk_drawdown_halt_gelatcht"


def test_eichfall_freigabe_hebt_den_ueberdauernden_halt(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Gegenprobe zum Eichfall: der Halt ist loesbar -- nur eben von einem Menschen.

    Gegen HEAD ist dieser Test **gruen**, und das ist kein Mangel: dort haelt nichts,
    also gibt es nichts freizugeben. Er steht hier, weil eine Sperre ohne belegten
    Ausgang im Betrieb ausgebaut statt bedient wird.
    """
    lauf1 = RiskManager(zustand=_zustand(tmp_path))
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(lauf1, account=_account("10000")).latch_halt is True

    lauf2 = RiskManager(zustand=_zustand(tmp_path))
    lauf2.release_drawdown("ops-2026-08-13")
    a2 = _autorisiere(lauf2, account=_account("12000"), now=NOW + timedelta(minutes=5))
    assert a2.approved is True

    # Und die Freigabe steht nicht in der Datei: ein dritter Lauf ohne Freigabe
    # handelt trotzdem, weil der HALT geloescht wurde -- nicht, weil eine Freigabe
    # ueberdauert haette. Der Unterschied wird sichtbar, sobald der Drawdown erneut
    # reisst (siehe ``test_risiko_zustand.py``).
    lauf3 = RiskManager(zustand=_zustand(tmp_path))
    assert (
        _autorisiere(
            lauf3, account=_account("12000"), now=NOW + timedelta(minutes=6)
        ).approved
        is True
    )


# --- Eichfall 2: die Tageskappe ueberdauert den Neustart ------------------------


def test_eichfall_tageskappe_ueberdauert_den_neustart(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD: dort war ``a2.approved is True``."""
    politik = RiskPolicy(throttle=ThrottlePolicy(max_trades_per_account_per_day=1))

    lauf1 = RiskManager(politik, zustand=_zustand(tmp_path))
    assert _autorisiere(lauf1, account=_account()).approved is True
    lauf1.record_open_fill("EURUSD", NOW)

    # --- Neustart: die Kappe ist fuer HEUTE erschoepft, auch im neuen Prozess ---
    lauf2 = RiskManager(politik, zustand=_zustand(tmp_path))
    a2 = _autorisiere(lauf2, account=_account(), now=NOW + timedelta(hours=2))
    assert a2.approved is False
    assert a2.reason == "throttle_account_daily_cap"

    # Am Folgetag laeuft die Kappe ab -- sonst waere sie keine TAGESkappe.
    lauf3 = RiskManager(politik, zustand=_zustand(tmp_path))
    a3 = _autorisiere(lauf3, account=_account(), now=NOW + timedelta(days=1))
    assert a3.approved is True


def test_eichfall_zweiundzwanzig_eroeffnungen_gegen_eine_kappe_von_zehn(  # noqa: E501
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der gemessene Schaden, nachgestellt. ROT gegen HEAD: dort waren es **24**.

    Aus den Betriebsjournalen: 22 Eroeffnungen an einem Konto-Tag gegen eine Kappe von
    10, weil jeder Neustart bei null anfing. Hier zwoelf Neustarts mit je zwei
    Versuchen am selben Tag; mit dauerhaftem Zaehler kommen genau 10 durch.
    """
    politik = RiskPolicy(
        throttle=ThrottlePolicy(
            max_trades_per_account_per_day=10,
            max_trades_per_instrument_per_day=99,
            cooldown_per_instrument=timedelta(0),
            min_hold=timedelta(0),
        )
    )

    eroeffnet = 0
    zeit = NOW
    for _neustart in range(12):
        rm = RiskManager(
            politik, zustand=_zustand(tmp_path)
        )  # jeder Durchgang ist ein Prozessstart
        for _versuch in range(2):
            if _autorisiere(rm, account=_account(), now=zeit).approved:
                rm.record_open_fill("EURUSD", zeit)
                eroeffnet += 1
            zeit += timedelta(minutes=1)

    assert eroeffnet == 10


# --- Eichfall 3: der Halt latcht auch ohne Zustandsdatei -----------------------


def test_eichfall_halt_latcht_auch_im_selben_prozess(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD: dort war ``a2.approved is True``.

    Ohne Zustandsdatei -- die Umgebungsvariable ist ausdruecklich geloescht. Der Halt
    muss auch im laufenden Prozess latchen, sonst waere ein Neustart **strenger** als
    kein Neustart: die Platte wuesste vom Halt, der laufende Prozess nicht.
    """
    rm = RiskManager(zustand=FluechtigerZustand())
    rm.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    a1 = _autorisiere(rm, account=_account("10000"))  # 16,7 % -> HALT
    assert a1.latch_halt is True

    # Equity voll erholt -- der Halt loest sich trotzdem nicht von selbst.
    a2 = _autorisiere(rm, account=_account("12000"), now=NOW + timedelta(minutes=5))
    assert a2.approved is False
    assert a2.latch_halt is True


# --- Eichfall 4: eine leere Kennung ist keine Freigabe --------------------------


def test_eichfall_leere_freigabe_loest_den_halt_nicht(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD an ZWEI Zusicherungen: DID NOT RAISE, dann ``approved is True``.

    Der Halt latcht und ueberdauert -- also ist die Frage „was ist eine Freigabe?"
    nicht mehr rhetorisch. ``release_drawdown('   ')`` prueft nichts und setzte den
    Latch zurueck; derselbe menschliche Akt am Konstruktor verlangte ``.strip()``, und
    ``risk/limits.py`` ebenfalls. Zwei Massstaebe fuer eine Geste, und der laxere sass
    auf dem Not-Aus. Gemessen am Arbeitsstand vor der Reparatur: nach
    ``release_drawdown('   ')`` war ``approved=True``.
    """
    lauf1 = RiskManager(zustand=_zustand(tmp_path))
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(lauf1, account=_account("10000")).latch_halt is True

    lauf2 = RiskManager(zustand=_zustand(tmp_path))
    for keine_freigabe in ("", "   ", "\t\n"):
        with pytest.raises(ValueError):
            lauf2.release_drawdown(keine_freigabe)

    # Und der Halt steht danach unveraendert -- auch bei voll erholter Equity.
    a2 = _autorisiere(lauf2, account=_account("12000"), now=NOW + timedelta(minutes=5))
    assert a2.approved is False
    assert a2.latch_halt is True
    assert a2.reason == "risk_drawdown_halt_gelatcht"

    # Gegenprobe: eine echte Kennung loest ihn. Sonst waere die Strenge nur eine
    # Sperre ohne Ausgang.
    lauf2.release_drawdown("ops-2026-08-13")
    assert (
        _autorisiere(
            lauf2, account=_account("12000"), now=NOW + timedelta(minutes=6)
        ).approved
        is True
    )


# --- Eichfall 5: der Ort der Zustandsdatei wird erzwungen -----------------------


def test_eichfall_relativer_zustandspfad_wird_abgewiesen(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD: dort wurde der genannte Ort gar nicht geprueft (kein Wurf).

    Ein relativer Pfad wird gegen das Arbeitsverzeichnis aufgeloest -- die Datei mit
    dem Drawdown-Halt laege damit im Arbeitsbaum, wo ``git clean -xdf`` sie loescht und
    der naechste Start sie als „neu" und damit als „frei" liest. Der Wurf faellt beim
    **Bau**, also vor der ersten Order.

    ``ValueError`` statt der genauen Klasse: diese Datei importiert absichtlich nichts
    aus dem neuen Modul (siehe Modul-Docstring). ``ZustandsortFehler`` ist ein
    ``ValueError``.
    """
    for relativ in ("betrieb/risikozustand.json", "betrieb"):
        with pytest.raises(ValueError):
            zustandsordner_pruefen(relativ)

    # Gegenprobe: ein absoluter Pfad geht durch -- die Sperre trifft nur den Fall,
    # den sie treffen soll.
    assert zustandsordner_pruefen(tmp_path) == tmp_path
    assert RiskManager(zustand=_zustand(tmp_path)).zustand_dauerhaft is True


# --- Eichfall 6: der Peak ueberdauert einen Neustart OHNE Order -----------------


def test_eichfall_peak_ueberdauert_neustart_ohne_order(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ROT gegen HEAD **und** gegen den Arbeitsstand vor der Reparatur.

    Der eigentliche Betriebsweg: ``RiskManager`` ohne Konto (so bauen ihn
    ``tools/live_betrieb.py``, ``tools/paper_run.py``, ``tools/live_konsole.py`` und
    ``tools/mt5_smoke.py``), Dauerhaftigkeit ueber die Zustandsdatei. Der Scheduler
    beobachtet Equity je Takt, autorisiert wird seltener -- ein Neustart VOR der ersten
    Order darf den Fenster-Hoechststand nicht verlieren.

    Gemessen vor der Reparatur: nach sechs Takten mit Hoch 12000 und ohne Order
    existierte die Zustandsdatei nicht; nach dem Neustart war der Drawdown gegen 10000
    wieder null und ``approved=True``.
    """
    lauf1 = RiskManager(zustand=_zustand(tmp_path))
    for takt in range(6):
        lauf1.observe_equity(NOW - timedelta(hours=6 - takt), Decimal("12000"))
    assert (tmp_path / "risikozustand.json").exists()

    lauf2 = RiskManager(zustand=_zustand(tmp_path))
    a2 = _autorisiere(lauf2, account=_account("10000"), now=NOW)
    assert a2.approved is False
    assert a2.latch_halt is True
    assert a2.reason == "risk_drawdown_limit_reached"


# --- Eichfall 7: eine unschreibbare Platte stuerzt nicht ab, sie sperrt ---------


def test_eichfall_unschreibbarer_zustand_sperrt_statt_abzustuerzen(  # noqa: E501
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """ROT gegen HEAD (dort ``approved is True``) und gegen den Stand vor der Reparatur
    (dort ``PermissionError`` aus ``record_open_fill``).

    Das Zielverzeichnis ist eine **Datei**; jeder Schreibversuch scheitert damit auf
    jeder Plattform mit einem ``OSError``. Zwei Zusicherungen: es wird nichts Neues
    mehr eroeffnet (der Zustand ist unsicher), und der Order-Pfad stuerzt trotzdem
    nicht ab -- ``record_open_fill`` laeuft in ``venue/mt5.py`` NACH dem Fill.
    """
    sperre = tmp_path / "sperre"
    sperre.write_text("kein Verzeichnis", encoding="utf-8")
    rm = RiskManager(zustand=DateiZustand(sperre / "risikozustand.json"))
    auth = _autorisiere(rm, account=_account("10000"))
    assert auth.approved is False
    assert auth.reason.startswith("risk_zustand_nicht_gesichert")  # type: ignore[union-attr]
    # Kein Latch: die Aussage betrifft die Platte, nicht den Markt -- sie faellt mit
    # dem naechsten gelungenen Schreibvorgang und braucht keinen Menschen.
    assert auth.latch_halt is False

    # Und der Weg NACH dem Fill traegt: keine Ausnahme, wo der Aufrufer sein
    # OrderResult erwartet.
    rm.record_open_fill("EURUSD", NOW)
    rm.record_close("EURUSD")
    rm.observe_equity(NOW, Decimal("10000"))


def test_eichfall_marke_faellt_mit_dem_naechsten_gelungenen_schreiben(  # noqa: E501
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Die Gegenprobe: die Sperre ist keine Dauerbremse.

    Sie loest sich durch einen **Beweis** (ein gelungener Schreibvorgang), nicht durch
    Zeitablauf und nicht durch einen Neustart. Ohne diese Gegenprobe waere sie eine
    Sperre ohne Ausgang -- und die wird im Betrieb ausgebaut statt bedient.
    """
    ordner = tmp_path / "zustand"
    ziel = ordner / "risikozustand.json"
    ordner.write_text("kein Verzeichnis", encoding="utf-8")

    rm = RiskManager(zustand=DateiZustand(ziel))
    assert _autorisiere(rm, account=_account("10000")).approved is False

    # Die Platte wird wieder schreibbar -- ohne Neustart, ohne Freigabe.
    Path(ordner).unlink()
    ordner.mkdir()
    assert (
        _autorisiere(
            rm, account=_account("10000"), now=NOW + timedelta(minutes=1)
        ).approved
        is True
    )
    assert ziel.exists()
