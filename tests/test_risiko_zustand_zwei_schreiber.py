"""Zwei Schreiber auf einer Zustandsdatei -- und warum ein Halt dabei gewinnt.

DER BEFUND, DEN DIESE DATEI FESTNAGELT
--------------------------------------
Die vorige Reparatur schloss das Loch nur im **ungebundenen** Schreibzweig. Der
gebundene schrieb ``RiskManager._lage()`` weiter ohne Neulesen ueber die Datei. Damit
galt: Lauf A startet frueh und haelt einen Altstand ohne Halt im Speicher; Lauf B
latcht einen Drawdown-Halt und schreibt ihn; sobald A **eine einzige** Autorisierung
faehrt, bindet es sich, schreibt seinen Altstand -- und der Halt ist weg. Weil sich ein
Live-Prozess mit seiner ersten Order dauerhaft bindet, war der geschuetzte Zustand der
kurze und der ungeschuetzte der Dauerzustand.

Gemessen am Stand 651c752, mit genau der Abfolge aus
``test_der_gebundene_schreibpfad_loescht_keinen_fremden_halt``: ``A approved: True``,
``Platte halt danach: False``, und der Neustart danach handelte frei.

WAS HIER GEPRUEFT WIRD -- UND WAS AUSDRUECKLICH NICHT
-----------------------------------------------------
Geprueft wird die **Regel**: lesen, vereinigen, schreiben; je Abschnitt die strenge
Richtung; und ein gesetzter Halt verschwindet nur durch eine ausdrueckliche Freigabe.
Nicht geprueft (und auch nicht behauptet) wird gegenseitiger Ausschluss: zwischen dem
frischen Lesen und ``os.replace`` bleibt ein Fenster von der Dauer eines
Schreibvorgangs. Ein Test, der ein Millisekundenfenster zu treffen versucht, waere
flatterhaft und bewiese nichts; die Grenze steht darum im Modul-Docstring und nicht
hier.

Kein Test dieser Datei haengt an der Rechneruhr, an einer Umgebungsvariablen, an einem
MT5-Terminal oder am Netz: alle Zeitpunkte sind feste Konstanten, jede Datei liegt
unter ``tmp_path``, und der Speicher wird ueber ``zustand=`` uebergeben.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from mt5_trading_ai.execution.risiko_zustand import (
    RISIKO_ZUSTAND_SCHEMA,
    DateiZustand,
    RisikoLage,
    lage_vereinen,
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
WAEHRUNG = "USD"


# --- Werkzeug (bewusst eigenstaendig, kein Import aus einer anderen Testdatei) --


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


def _konto(
    equity: str = "10000", *, konto: str = KONTO, waehrung: str = WAEHRUNG
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


def _order() -> OrderRequest:
    return OrderRequest(
        client_order_id="c-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("1.09000"),
    )


def _autorisiere(
    rm: RiskManager,
    *,
    account: AccountState | None = None,
    now: datetime = NOW,
) -> RiskAuthorization:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=_order(),
        account=account if account is not None else _konto(),
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def _lauf(pfad: Path, politik: RiskPolicy | None = None, **kw: Any) -> RiskManager:
    """Ein „Prozessstart": ein frischer Manager auf derselben Zustandsdatei."""
    return RiskManager(politik, zustand=DateiZustand(pfad), **kw)


def _lies(pfad: Path) -> dict[str, Any]:
    daten: dict[str, Any] = json.loads(pfad.read_text(encoding="utf-8"))
    return daten


def _blockiere(pfad: Path) -> None:
    """Jeder Schreibvorgang scheitert -- die Nebendatei wird zum Verzeichnis.

    Auf Windows ``PermissionError``, auf POSIX ``IsADirectoryError``; beides
    ``OSError``. Kein ``chmod``, kein Plattformzweig, kein Rechtemodell.
    """
    pfad.with_name(pfad.name + ".neu").mkdir(parents=True, exist_ok=True)


def _entsperre(pfad: Path) -> None:
    pfad.with_name(pfad.name + ".neu").rmdir()


# --- Der schwerste Fall: der gebundene Schreibpfad ------------------------------


def test_der_gebundene_schreibpfad_loescht_keinen_fremden_halt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Befund, wortgetreu nachgestellt -- und in allen drei Wirkungen geprueft.

    Lauf A schaut seit Stunden zu (ungebunden, Altstand ohne Halt im Speicher). Lauf B
    latcht bei 16,7 % Drawdown (Peak 12000, Equity 10000 -> 2000/12000 = 1/6 = 16,67 %
    gegen die Vorgabe von 10 %) und schreibt den Halt. Dann faehrt A **eine**
    Autorisierung und bindet sich dabei.

    Drei Zusicherungen, weil drei verschiedene Dinge schiefgehen koennen:

    1. Der Halt steht danach immer noch auf der Platte (der Schreibpfad hat ihn nicht
       mitgenommen).
    2. A selbst ist angehalten -- und zwar mit ``drawdown_halt_gelatcht``. A faehrt
       dafuer mit **voll erholter** Equity (12000 gegen Peak 12000, Drawdown 0): eine
       frische Limit-Auswertung faende hier nichts, die Ablehnung kann also nur aus
       dem uebernommenen Latch kommen.
    3. Ein Neustart danach ist ebenfalls angehalten.

    Gemessen am Stand 651c752: 1. ``False``, 2. ``approved=True``, 3. ``True``.
    """
    pfad = tmp_path / "z.json"
    zuschauer = _lauf(pfad)  # laedt: keine Datei, kein Halt
    zuschauer.observe_equity(NOW - timedelta(hours=3), Decimal("10000"))

    handelnder = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    handelnder.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(handelnder, account=_konto("10000")).latch_halt is True
    assert _lies(pfad)["halt"]["aktiv"] is True

    auth = _autorisiere(
        zuschauer, account=_konto("12000"), now=NOW + timedelta(minutes=1)
    )

    assert _lies(pfad)["halt"]["aktiv"] is True
    assert auth.approved is False
    assert auth.latch_halt is True
    assert auth.reason == "risk_drawdown_halt_gelatcht"

    neustart = _autorisiere(
        _lauf(pfad), account=_konto("12000"), now=NOW + timedelta(minutes=2)
    )
    assert neustart.approved is False
    assert neustart.reason == "risk_drawdown_halt_gelatcht"


def test_der_zweite_lauf_holt_den_fremden_halt_in_den_eigenen_speicher(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Die Platte zu schuetzen genuegt nicht -- dieser Lauf muss selbst anhalten.

    Ohne das Nachziehen waere die Reparatur halb: der Halt bliebe stehen, aber der
    zuschauende Lauf wuesste nichts davon und eroeffnete munter weiter, waehrend der
    Halt-Latch unter ihm auf der Platte liegt.

    Der Nachweis haengt an einer einzigen Beobachtung: die Ablehnung traegt
    ``drawdown_halt_gelatcht`` (der uebernommene Latch), nicht
    ``drawdown_limit_reached`` (eine frische Auswertung). Bei Equity 12000 gegen einen
    Peak von 12000 ist der Drawdown 0 -- eine frische Auswertung faende hier gar
    nichts.
    """
    pfad = tmp_path / "z.json"
    zuschauer = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    zuschauer.observe_equity(NOW - timedelta(hours=3), Decimal("12000"))

    handelnder = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    assert _autorisiere(handelnder, account=_konto("10000")).latch_halt is True

    # Nur ein Takt des Zuschauers -- keine Order, keine Bindungsaenderung.
    zuschauer.observe_equity(NOW + timedelta(minutes=1), Decimal("12000"))

    auth = _autorisiere(
        zuschauer, account=_konto("12000"), now=NOW + timedelta(minutes=2)
    )
    assert auth.approved is False
    assert auth.reason == "risk_drawdown_halt_gelatcht"


def test_die_tageskappe_eines_zweiten_laufs_wird_nicht_zurueckgesetzt(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der gemessene Schaden dieses Repos, eine Ebene tiefer: zwei Laeufe statt zwei
    Neustarts.

    Kappe 2 je Konto und Tag. Lauf B eroeffnet zwei Mal. Lauf A hat den Stand von
    vorher (null Trades) im Speicher -- schriebe er ihn zurueck, waere die Kappe
    geleert und A duerfte zwei weitere Eroeffnungen fahren: vier statt zwei.

    Von Hand gerechnet: 2 (B) + 0 (A) -> vereinigt 2; die Kappe von 2 ist damit
    erreicht, und ``select_one`` weist mit ``account_daily_cap`` ab.
    """
    pfad = tmp_path / "z.json"
    politik = RiskPolicy(
        throttle=ThrottlePolicy(
            max_trades_per_account_per_day=2,
            max_trades_per_instrument_per_day=99,
            cooldown_per_instrument=timedelta(0),
            min_hold=timedelta(0),
        )
    )
    lauf_a = _lauf(pfad, politik, konto_id=KONTO, waehrung=WAEHRUNG)

    lauf_b = _lauf(pfad, politik, konto_id=KONTO, waehrung=WAEHRUNG)
    for versuch in range(2):
        zeit = NOW + timedelta(minutes=versuch)
        assert _autorisiere(lauf_b, now=zeit).approved is True
        lauf_b.record_open_fill("EURUSD", zeit)
    assert _lies(pfad)["tageszaehler"]["je_konto"] == 2

    auth = _autorisiere(lauf_a, now=NOW + timedelta(minutes=5))
    assert auth.approved is False
    assert auth.reason == "throttle_account_daily_cap"
    assert _lies(pfad)["tageszaehler"]["je_konto"] == 2


def test_ein_vorgestellter_tag_auf_der_platte_senkt_die_eigene_zaehlung_nicht(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der Filter beim Nachziehen ist kein Zierrat -- hier greift er wirklich.

    Bei **verschiedenen** Handelstagen nimmt ``lage_vereinen`` den spaeteren Tag
    mitsamt seinen Zaehlern; die koennen niedriger sein als die eigenen. Genau dann
    darf das Nachziehen den eigenen Zaehler nicht mitziehen: der Handelstag dieses
    Laufs kommt aus SEINER Uhr, und eine vorgestellte Uhr auf der Platte (zweiter
    Runner, falsch gestellte Maschine) waere sonst der bequemste Weg, eine
    ausgeschoepfte Tageskappe zu leeren.

    Von Hand: Kappe 2 je Konto und Tag. Lauf A eroeffnet am 13.08. zwei Mal auf EURUSD
    (Zaehler 2, Kappe erreicht). Lauf B eroeffnet am 14.08. ein Mal auf GBPUSD und
    schreibt Tag 14.08. mit Zaehler 1. Lauf A rechnet weiter im 13.08. -- sein Zaehler
    muss 2 bleiben und die naechste Eroeffnung an derselben Kappe scheitern.

    B handelt bewusst ein **anderes** Symbol: sonst zoege A den spaeteren
    ``letzter_trade_at`` nach und die Abklingzeit meldete sich vor der Kappe. Das
    waere ebenfalls eine Ablehnung, aber sie prueft nicht, was hier geprueft werden
    soll.
    """
    pfad = tmp_path / "z.json"
    politik = RiskPolicy(
        throttle=ThrottlePolicy(
            max_trades_per_account_per_day=2,
            max_trades_per_instrument_per_day=99,
            cooldown_per_instrument=timedelta(0),
            min_hold=timedelta(0),
            max_concurrent_positions=9,
        )
    )
    lauf_a = _lauf(pfad, politik, konto_id=KONTO, waehrung=WAEHRUNG)
    for versuch in range(2):
        lauf_a.record_open_fill("EURUSD", NOW + timedelta(minutes=versuch))

    morgen = NOW + timedelta(days=1)
    lauf_b = _lauf(pfad, politik, konto_id=KONTO, waehrung=WAEHRUNG)
    lauf_b.record_open_fill("GBPUSD", morgen)
    assert _lies(pfad)["tageszaehler"]["tag"] == morgen.date().isoformat()
    assert _lies(pfad)["tageszaehler"]["je_konto"] == 1

    auth = _autorisiere(lauf_a, now=NOW + timedelta(minutes=5))
    assert auth.approved is False
    assert auth.reason == "throttle_account_daily_cap"


# --- Die Regel selbst ----------------------------------------------------------


def _t(stunden: int) -> datetime:
    return NOW + timedelta(hours=stunden)


def test_lage_vereinen_nimmt_je_abschnitt_die_strenge_seite() -> None:
    """Die Tabelle aus dem Modul-Docstring, Wert fuer Wert von Hand gerechnet.

    Platte und eigener Stand sind absichtlich so gebaut, dass **jeder** Abschnitt eine
    andere Seite gewinnen laesst -- sonst koennte eine vertauschte Zeile unbemerkt
    bleiben.
    """
    platte = RisikoLage(
        halt=True,
        halt_grund="drawdown_halt_gelatcht",
        halt_seit=_t(0),
        handelstag=NOW.date(),
        zaehler_gesperrt=False,
        trades_je_instrument={"EURUSD": 3, "XAUUSD": 1},
        trades_konto=4,
        letzter_trade_at={"EURUSD": _t(0)},
        equity_tag=NOW.date(),
        tagesstart_equity=Decimal("10000"),
        equity_fenster=[(_t(0), Decimal("12000"))],
        offene_positionen=[("EURUSD", _t(0))],
    )
    eigen = RisikoLage(
        halt=False,
        handelstag=NOW.date(),
        zaehler_gesperrt=True,
        trades_je_instrument={"EURUSD": 1, "GBPUSD": 5},
        trades_konto=2,
        letzter_trade_at={"EURUSD": _t(1), "GBPUSD": _t(0)},
        equity_tag=NOW.date(),
        tagesstart_equity=Decimal("9000"),
        equity_fenster=[(_t(0), Decimal("11000")), (_t(1), Decimal("13000"))],
        offene_positionen=[("EURUSD", _t(2)), ("GBPUSD", _t(0))],
    )

    vereint = lage_vereinen(platte, eigen)

    # Halt: ODER. Nur die Platte haelt -> ihr Grund und ihr Beginn kommen mit.
    assert vereint.halt is True
    assert vereint.halt_grund == "drawdown_halt_gelatcht"
    assert vereint.halt_seit == _t(0)
    # Zaehlersperre: ODER -- hier gewinnt der eigene Stand.
    assert vereint.zaehler_gesperrt is True
    # Zaehler: Hoechstwert je Schluessel. EURUSD max(3,1)=3, XAUUSD nur Platte=1,
    # GBPUSD nur eigen=5; Konto max(4,2)=4.
    assert vereint.trades_je_instrument == {"EURUSD": 3, "XAUUSD": 1, "GBPUSD": 5}
    assert vereint.trades_konto == 4
    # Letzter Trade: der spaetere Zeitpunkt sperrt laenger.
    assert vereint.letzter_trade_at == {"EURUSD": _t(1), "GBPUSD": _t(0)}
    # Tagesstart: hoeher heisst groesserer Tagesverlust -- (10000-E)/10000 ist fuer
    # jedes E < 10000 groesser als (9000-E)/9000. Also 10000.
    assert vereint.tagesstart_equity == Decimal("10000")
    assert vereint.equity_tag == NOW.date()
    # Fenster: je Korb der Hoechststand. Korb 12:00 max(12000,11000)=12000,
    # Korb 13:00 nur eigen=13000.
    assert vereint.equity_fenster == [
        (_t(0), Decimal("12000")),
        (_t(1), Decimal("13000")),
    ]
    # Positionen: Vereinigung, je Symbol die SPAETERE Eroeffnung (juenger =
    # Mindesthaltedauer sperrt laenger).
    assert vereint.offene_positionen == [("EURUSD", _t(2)), ("GBPUSD", _t(0))]


def test_bei_verschiedenen_tagen_gewinnt_der_spaetere_tag_ganz() -> None:
    """Nicht der Hoechstwert -- sonst waere die Tageskappe keine TAGESkappe mehr.

    Gestern liefen 9 Trades, heute 1. Der Hoechstwert waere 9 und die Kappe von 10
    waere heute nach einem einzigen Trade fast erschoepft. Richtig ist 1.
    """
    gestern = RisikoLage(
        handelstag=NOW.date() - timedelta(days=1),
        trades_je_instrument={"EURUSD": 9},
        trades_konto=9,
        zaehler_gesperrt=True,
    )
    heute = RisikoLage(
        handelstag=NOW.date(),
        trades_je_instrument={"EURUSD": 1},
        trades_konto=1,
        zaehler_gesperrt=False,
    )
    for platte, eigen in ((gestern, heute), (heute, gestern)):
        vereint = lage_vereinen(platte, eigen)
        assert vereint.handelstag == NOW.date()
        assert vereint.trades_konto == 1
        assert vereint.trades_je_instrument == {"EURUSD": 1}
        # Auch die Zaehlersperre von gestern laeuft mit dem Tag ab.
        assert vereint.zaehler_gesperrt is False


def test_die_zaehlersperre_gewinnt_aus_beiden_richtungen() -> None:
    """ODER heisst ODER -- sonst prueft die Zeile nur eine Haelfte.

    Die Sperre entsteht aus einem unlesbaren Zaehlerabschnitt und gilt fuer den
    laufenden Tag. Faende sie nur von der einen Seite statt, koennte ein zweiter Lauf
    sie mit einem sauberen Stand ausknipsen -- und der Tag, an dem 22 Eroeffnungen
    gegen eine Kappe von 10 liefen, waere wieder moeglich.
    """
    gesperrt = RisikoLage(handelstag=NOW.date(), zaehler_gesperrt=True)
    frei = RisikoLage(handelstag=NOW.date(), zaehler_gesperrt=False)
    assert lage_vereinen(gesperrt, frei).zaehler_gesperrt is True
    assert lage_vereinen(frei, gesperrt).zaehler_gesperrt is True
    assert lage_vereinen(frei, frei).zaehler_gesperrt is False


def test_die_zaehlersperre_eines_zweiten_laufs_greift_auch_hier(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Dieselbe Regel am ganzen Weg: Platte lesen, vereinen, in den Speicher ziehen.

    Lauf B findet einen unlesbaren Zaehlerabschnitt vor und sperrt den Tag. Lauf A hat
    einen sauberen Stand im Speicher -- er darf die Sperre weder von der Platte
    loeschen noch selbst weiterhandeln.
    """
    pfad = tmp_path / "z.json"
    lauf_a = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    assert _autorisiere(lauf_a).approved is True

    daten = _lies(pfad)
    daten["tageszaehler"] = "kaputt"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    lauf_b = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    assert (
        _autorisiere(lauf_b, now=NOW + timedelta(minutes=1)).reason
        == "throttle_tageszaehler_unlesbar"
    )
    assert _lies(pfad)["tageszaehler"]["gesperrt"] is True

    auth = _autorisiere(lauf_a, now=NOW + timedelta(minutes=2))
    assert auth.reason == "throttle_tageszaehler_unlesbar"
    assert _lies(pfad)["tageszaehler"]["gesperrt"] is True


def test_nur_eine_ausdrueckliche_freigabe_loescht_den_halt_der_platte() -> None:
    """Die Kernregel des Auftrags, an der reinen Funktion festgenagelt.

    Drei Faelle, und der dritte ist der, den man beim naechsten Eingriff vergisst:
    eine Freigabe loescht **den Halt, den der Mensch gesehen hat** -- nicht einen, den
    dieser Lauf inzwischen selbst gesetzt hat.
    """
    platte = RisikoLage(halt=True, halt_grund="drawdown_halt_gelatcht")
    frei = RisikoLage(halt=False)
    neuer_halt = RisikoLage(halt=True, halt_grund="zustand_halt_unlesbar[halt.aktiv]")

    assert lage_vereinen(platte, frei).halt is True
    assert lage_vereinen(platte, frei, freigabe=True).halt is False
    assert lage_vereinen(platte, neuer_halt, freigabe=True).halt is True

    # Und andersherum: ein eigener Halt ueberlebt eine Platte, die frei aussieht.
    assert lage_vereinen(frei, neuer_halt).halt is True


def test_von_zwei_haltgruenden_gewinnt_der_frueher_begonnene() -> None:
    """Der erste Halt ist der urspruengliche; der zweite ist seine Wiederholung.

    Ohne diese Richtung stuende im Protokoll der spaeteste Zeitpunkt, und die Frage
    „seit wann haelt das System?" waere mit jedem Takt neu beantwortet.
    """
    frueh = RisikoLage(halt=True, halt_grund="drawdown_halt_gelatcht", halt_seit=_t(0))
    spaet = RisikoLage(halt=True, halt_grund="zustand_kein_json", halt_seit=_t(2))
    for platte, eigen in ((frueh, spaet), (spaet, frueh)):
        vereint = lage_vereinen(platte, eigen)
        assert vereint.halt_seit == _t(0)
        assert vereint.halt_grund == "drawdown_halt_gelatcht"


# --- Die Freigabe als einmalige, begruendete Geste ------------------------------


def _gebundene_datei(pfad: Path, lage: RisikoLage) -> None:
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(KONTO, WAEHRUNG) is None
    assert speicher.sichern(lage) is None


def test_die_freigabe_gilt_einmal_und_erst_nach_gelungenem_schreiben(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Drei Zusicherungen an einer Geste -- und alle drei koennen einzeln brechen.

    1. Ein **gescheiterter** Schreibvorgang verbraucht die Freigabe nicht. Sonst waere
       sie bei voller Platte still verloren und der Mensch glaubte, freigegeben zu
       haben.
    2. Der naechste gelungene loescht den Halt.
    3. Danach ist sie verbraucht: ein Halt, den ein zweiter Lauf spaeter setzt, faellt
       nicht noch einmal derselben Geste zum Opfer.
    """
    pfad = tmp_path / "z.json"
    _gebundene_datei(pfad, RisikoLage(halt=True, halt_grund="drawdown_halt_gelatcht"))

    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(KONTO, WAEHRUNG) is None
    speicher.freigabe_vormerken()

    _blockiere(pfad)
    assert speicher.sichern(RisikoLage(halt=False)) is not None
    assert _lies(pfad)["halt"]["aktiv"] is True

    _entsperre(pfad)
    assert speicher.sichern(RisikoLage(halt=False)) is None
    assert _lies(pfad)["halt"]["aktiv"] is False

    # Ein zweiter Lauf setzt einen NEUEN Halt ...
    _gebundene_datei(pfad, RisikoLage(halt=True, halt_grund="drawdown_halt_gelatcht"))
    # ... und derselbe Speicher darf ihn nicht ein zweites Mal wegschreiben.
    assert speicher.sichern(RisikoLage(halt=False)) is None
    assert _lies(pfad)["halt"]["aktiv"] is True


def test_die_freigabe_am_manager_traegt_bis_auf_die_platte(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Die Gegenprobe zur Strenge: der Halt hat einen bedienbaren Ausgang.

    Ohne sie waere die Vereinigungsregel eine Sperre ohne Ausgang -- und die wird im
    Betrieb ausgebaut statt bedient. Geprueft wird der volle Weg: Freigabe im
    laufenden Prozess, Halt von der Platte weg, und ein **fremder** Neustart darf
    danach handeln.
    """
    pfad = tmp_path / "z.json"
    lauf1 = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(lauf1, account=_konto("10000")).latch_halt is True
    assert _lies(pfad)["halt"]["aktiv"] is True

    lauf2 = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    lauf2.release_drawdown("ops-2026-08-13")
    assert _lies(pfad)["halt"]["aktiv"] is False

    lauf3 = _lauf(pfad)
    assert (
        _autorisiere(
            lauf3, account=_konto("12000"), now=NOW + timedelta(minutes=5)
        ).approved
        is True
    )


# --- Positionen: Vereinigen ohne Ratsche ---------------------------------------


def test_eine_geschlossene_position_kommt_nicht_von_der_platte_zurueck(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Ohne die ausdrueckliche Schliessung waere die Vereinigung eine Ratsche.

    Der Positionsdeckel steht bei 3. Wuerde jede einmal geschriebene Position auf der
    Platte bleiben, waere er nach drei Eroeffnungen dauerhaft voll -- eine Sperre ohne
    Ausgang, egal wie oft der Betrieb wirklich schliesst.
    """
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    for symbol in ("GBPUSD", "USDCHF", "AUDUSD"):
        rm.record_open_fill(symbol, NOW - timedelta(hours=2))
    assert len(_lies(pfad)["offene_positionen"]) == 3

    rm.record_close("AUDUSD")
    assert [p["instrument"] for p in _lies(pfad)["offene_positionen"]] == [
        "GBPUSD",
        "USDCHF",
    ]
    assert _lauf(pfad).open_position_count == 2


def test_die_position_eines_zweiten_laufs_bleibt_beim_schliessen_stehen(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Die andere Haelfte: die Schliessung raeumt nur das eigene Symbol ab.

    Ohne diese Gegenprobe waere „ausdrueckliche Schliessung" die bequeme Tuer, durch
    die der ganze Positionsabschnitt eines zweiten Laufs verschwindet -- und der
    Positionsdeckel rechnete wieder zu niedrig, also in die milde Richtung.
    """
    pfad = tmp_path / "z.json"
    lauf_a = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    lauf_a.record_open_fill("GBPUSD", NOW - timedelta(hours=2))

    lauf_b = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    lauf_b.record_open_fill("USDCHF", NOW - timedelta(hours=1))

    lauf_a.record_close("GBPUSD")

    assert [p["instrument"] for p in _lies(pfad)["offene_positionen"]] == ["USDCHF"]
    assert _lauf(pfad).open_position_count == 1


# --- Wem die Datei beim Schreiben gehoert --------------------------------------


def test_eine_inzwischen_fremde_datei_wird_nicht_ueberschrieben(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwei Konten in einer Datei sind schlimmer als ein ungesicherter Takt.

    Der Fall ist real: der Betreiber setzt ``MT5_RISIKO_ZUSTAND`` fuer den zweiten
    Runner nicht um, und der bindet dieselbe Datei an sein Konto. Der erste Lauf darf
    dann nicht einfach weiterschreiben -- er naehme den Halt und die Zaehler des
    anderen Kontos mit.
    """
    pfad = tmp_path / "z.json"
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(KONTO, WAEHRUNG) is None
    assert speicher.sichern(RisikoLage(trades_konto=1)) is None

    # Ein fremdes Konto uebernimmt die Datei: sie wird von Hand geloescht (die Geste,
    # die der Modul-Docstring als das Gegenteil einer Freigabe beschreibt), und der
    # naechste Lauf bindet sie an ein anderes Konto.
    pfad.unlink()
    fremd = DateiZustand(pfad)
    fremd.laden()
    assert fremd.binde("99887766", WAEHRUNG) is None
    assert fremd.sichern(RisikoLage(halt=True, halt_grund="fremd")) is None
    vorher = pfad.read_text(encoding="utf-8")

    grund = speicher.sichern(RisikoLage(trades_konto=2))
    assert grund == "zustand_fremdes_konto_beim_sichern"
    assert pfad.read_text(encoding="utf-8") == vorher
    assert speicher.schreibfehler_text


def test_dieselbe_kontonummer_mit_anderem_salz_ist_kein_fremdes_konto(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Sonst waere die Sperre oben eine Dauerbremse fuer den haeufigsten Fall.

    Zwei Prozesse starten gleichzeitig, beide finden keine Datei und ziehen je ein
    eigenes Salz. Der Abdruck unterscheidet sich dann, das Konto nicht. Geprueft wird
    darum mit dem Salz DER PLATTE nachgerechnet -- und ihre Bindung uebernommen, damit
    die Datei nicht zwischen zwei Bindungen springt.
    """
    pfad = tmp_path / "z.json"
    a = DateiZustand(pfad)
    a.laden()
    assert a.binde(KONTO, WAEHRUNG) is None
    b = DateiZustand(pfad)
    b.laden()
    assert b.binde(KONTO, WAEHRUNG) is None

    assert a.sichern(RisikoLage(trades_konto=1)) is None
    salz_von_a = _lies(pfad)["bindung"]["salz"]

    assert b.sichern(RisikoLage(trades_konto=2)) is None
    assert _lies(pfad)["schema"] == RISIKO_ZUSTAND_SCHEMA
    assert _lies(pfad)["bindung"]["salz"] == salz_von_a
    assert _lies(pfad)["tageszaehler"]["je_konto"] == 2


def test_ein_inzwischen_defekter_zustand_wird_nicht_durch_einen_freien_ersetzt(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Unlesbar heisst Halt -- auch fuer den, der die Datei gerade schreiben will.

    Ein Lauf, der die Datei sauber geladen hat und erst danach den Defekt vorfindet,
    traegt diesen Halt nicht: er wuerde ihn durch einen freien Stand ersetzen und
    damit genau die stille Freigabe schreiben, gegen die das Modul gebaut ist.

    Die Gegenprobe steht daneben: wer den Defekt SELBST gelesen hat, traegt den Halt
    und darf ersetzen -- sonst gaebe es aus einem Defekt keinen Weg heraus ausser dem
    Loeschen der Datei.
    """
    pfad = tmp_path / "z.json"
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(KONTO, WAEHRUNG) is None
    assert speicher.sichern(RisikoLage(trades_konto=1)) is None

    pfad.write_bytes(b"{ inzwischen kaputt")
    grund = speicher.sichern(RisikoLage(trades_konto=2))
    assert grund == "zustand_defekt_auf_der_platte"
    assert pfad.read_bytes() == b"{ inzwischen kaputt"

    # Gegenprobe: ein Lauf, der den Defekt selbst liest, traegt den Halt (``laden``
    # loest ihn dazu auf) und darf die Datei ersetzen.
    traeger = DateiZustand(pfad)
    befund = traeger.laden()
    assert befund.lage.halt is True
    assert traeger.binde(KONTO, WAEHRUNG) is None
    assert traeger.sichern(befund.lage) is None
    assert _lies(pfad)["halt"]["aktiv"] is True


def test_ein_defekt_unter_dem_laufenden_prozess_haelt_ihn_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Defekt IST der Halt -- auch fuer den Lauf, der ihn erst beim Schreiben sieht.

    Ohne das Nachziehen bliebe nur die Schreibmarke. Die faellt aber, sobald irgendwer
    die Datei „repariert" -- und die naheliegende Reparatur ist das Loeschen, also
    genau die Geste, die der Modul-Docstring als das Gegenteil einer Freigabe
    beschreibt. Der Halt muss darum im Speicher stehen und einen Menschen verlangen.

    Zwei Zusicherungen und eine Gegenprobe: die Ablehnung traegt einen Halt-Grund mit
    Latch (nicht nur ``zustand_nicht_gesichert``), sie ueberlebt das Aufraeumen der
    Datei -- und eine echte Freigabekennung loest sie.

    Die Freigabe loest dabei **nur den Halt**, nicht die Zaehlersperre. Das ist
    dieselbe Asymmetrie wie beim Laden (siehe ``test_risiko_zustand.py``): eine
    Freigabe ist eine Aussage ueber den Drawdown, keine darueber, wie viele Trades
    heute schon liefen. Die Zaehlersperre braucht darum keinen Menschen -- sie laeuft
    um Mitternacht ab.
    """
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    assert _autorisiere(rm).approved is True

    pfad.write_bytes(b"{ inzwischen kaputt")
    auth = _autorisiere(rm, now=NOW + timedelta(minutes=1))
    assert auth.approved is False
    assert auth.latch_halt is True
    assert auth.reason == "risk_zustand_kein_json"

    # Die Datei wird weggeraeumt -- der Halt bleibt trotzdem.
    pfad.unlink()
    weiter = _autorisiere(rm, now=NOW + timedelta(minutes=2))
    assert weiter.approved is False
    assert weiter.latch_halt is True

    # Gegenprobe: er hat einen Ausgang, und der ist eine menschliche Geste.
    rm.release_drawdown("ops-2026-08-13")
    nach_freigabe = _autorisiere(rm, now=NOW + timedelta(minutes=3))
    assert nach_freigabe.latch_halt is False  # der Halt ist geloest ...
    assert nach_freigabe.reason == "throttle_tageszaehler_unlesbar"  # ... die Tages-
    # sperre nicht, und sie laeuft von selbst ab.
    assert _autorisiere(rm, now=NOW + timedelta(days=1)).approved is True
