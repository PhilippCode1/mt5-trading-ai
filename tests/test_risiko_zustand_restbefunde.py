"""Die drei kleineren Restbefunde am Risikozustand -- je einer je Abschnitt.

1. **Ein Halt, den ein Plattenausfall verschluckt hat.** Die Schreibmarke wurde VOR
   der Limit-Auswertung geprueft; waehrend eines Ausfalls wurde der Drawdown also gar
   nicht erst bewertet. Erholten sich Platte und Equity, war der Not-Aus spurlos weg.
2. **Die Ortsgarantie deckte die Stelle nicht ab, mit der sie begruendet wird.**
   ``betrieb/`` steht als disqualifiziert im Modul-Docstring -- als absoluter Pfad
   ging es glatt durch.
3. **Unsichtbare Freigabekennungen.** ``U+200B`` ueberlebt ``.strip()`` und loeste
   einen dauerhaften Halt mit einer Kennung, die niemand sieht und niemand
   wiederfindet.

Alle drei sind am Stand 651c752 nachgestellt worden; die gemessenen Werte stehen in
den einzelnen Docstrings. Nichts hier haengt an der Rechneruhr, an einer
Umgebungsvariablen, an MetaTrader5 oder am Netz.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.execution.risiko_zustand import (
    DateiZustand,
    ZustandsortFehler,
    standard_zustandsdatei,
    verbotene_baeume,
)
from mt5_trading_ai.execution.risk_manager import (
    RiskAuthorization,
    RiskManager,
    freigabe_gueltig,
)
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

#: Zeichen ohne Bildflaeche, die ``str.isspace()`` NICHT meldet und die deshalb jedes
#: ``.strip()`` ueberleben: ZERO WIDTH SPACE, ZERO WIDTH NO-BREAK SPACE (BOM), WORD
#: JOINER, ZERO WIDTH NON-JOINER.
UNSICHTBAR = tuple(chr(nr) for nr in (0x200B, 0xFEFF, 0x2060, 0x200C))


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


def _konto(equity: str = "10000") -> AccountState:
    return AccountState(
        account_id=KONTO,
        currency=WAEHRUNG,
        balance=Decimal(equity),
        equity=Decimal(equity),
        margin_used=Decimal("0"),
        margin_free=Decimal(equity),
        is_demo=True,
        ts=NOW,
    )


def _autorisiere(
    rm: RiskManager, *, account: AccountState | None = None, now: datetime = NOW
) -> RiskAuthorization:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=OrderRequest(
            client_order_id="c-1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=Decimal("0.01"),
            stop_loss=Decimal("1.09000"),
        ),
        account=account if account is not None else _konto(),
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def _lies(pfad: Path) -> dict[str, Any]:
    daten: dict[str, Any] = json.loads(pfad.read_text(encoding="utf-8"))
    return daten


# --- 1) Der Halt waehrend eines Plattenausfalls ---------------------------------


def test_ein_halt_waehrend_eines_plattenausfalls_ueberlebt_die_erholung(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der schwerste der drei: ein Not-Aus, den ein Plattenproblem verschluckt hat.

    Von Hand gerechnet: Fenster-Peak 12000, Equity 10000 -> Drawdown
    (12000-10000)/12000 = 1/6 = 16,67 % gegen die Vorgabe ``max_drawdown_fraction``
    von 10 %. Das ist ein Halt, und zwar unabhaengig davon, ob die Platte gerade
    mitspielt: ``evaluate_limits`` rechnet aus dem Speicher.

    Gemessen am Stand 651c752, mit genau dieser Abfolge:
    ``waehrend Ausfall: risk_zustand_nicht_gesichert, latch=False``, danach
    ``_halt is False`` -- und nach der Erholung von Platte UND Equity
    ``approved=True``. Der Halt war also nie da; die Ablehnung kam allein aus der
    Schreibmarke und fiel mit ihr.

    Drei Zusicherungen: der Halt greift schon waehrend des Ausfalls (mit Latch, nicht
    als Plattenmeldung), er ueberlebt die Erholung, und er steht danach auf der
    Platte -- also auch ueber einen Neustart.
    """
    pfad = tmp_path / "z.json"
    rm = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    rm.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))

    pfad.with_name(pfad.name + ".neu").mkdir()  # jeder Schreibvorgang scheitert
    waehrend = _autorisiere(rm, account=_konto("10000"))
    assert waehrend.approved is False
    assert waehrend.latch_halt is True
    assert waehrend.reason == "risk_drawdown_limit_reached"

    # Die Platte erholt sich, die Equity ebenfalls -- ein Latch loest sich davon nicht.
    pfad.with_name(pfad.name + ".neu").rmdir()
    danach = _autorisiere(
        rm, account=_konto("12000"), now=NOW + timedelta(minutes=5)
    )
    assert danach.approved is False
    assert danach.latch_halt is True
    assert danach.reason == "risk_drawdown_halt_gelatcht"
    assert _lies(pfad)["halt"]["aktiv"] is True


def test_die_schreibmarke_bleibt_die_meldung_ohne_halt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Gegenprobe: ohne Drawdown meldet weiterhin die Platte, nicht der Not-Aus.

    Ohne sie waere die neue Reihenfolge womoeglich damit erkauft, dass jeder
    Plattenfehler als Drawdown-Halt erscheint -- eine Sperre, die einen Menschen
    verlangt, wo die Platte selbst antwortet.
    """
    pfad = tmp_path / "z.json"
    rm = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    pfad.with_name(pfad.name + ".neu").mkdir()
    rm.observe_equity(NOW, Decimal("10000"))

    auth = _autorisiere(rm, account=_konto("10000"))
    assert auth.approved is False
    assert auth.latch_halt is False
    assert auth.reason is not None
    assert auth.reason.startswith("risk_zustand_nicht_gesichert")

    # Und sie faellt weiterhin mit dem naechsten gelungenen Schreibvorgang.
    pfad.with_name(pfad.name + ".neu").rmdir()
    assert _autorisiere(
        rm, account=_konto("10000"), now=NOW + timedelta(minutes=1)
    ).approved is True


# --- 2) Die Ortsgarantie --------------------------------------------------------


def test_die_ortsgarantie_deckt_auch_betrieb_und_die_arbeitskopie() -> None:
    """Genau der Ort, mit dem der Docstring die Ortswahl begruendet.

    Der Modul-Docstring nennt ``betrieb/`` ausdruecklich als disqualifiziert
    („``git clean -xdf`` -- ein Alltagsbefehl -- loescht dort alles. Ein Halt, den ein
    Aufraeumbefehl aufhebt, ist kein Halt"). Geprueft wurde bis hierher nur gegen
    ``mt5_trading_ai/``; gemessen am Stand 651c752 wurden
    ``<arbeitskopie>/betrieb/z.json``, ``<arbeitskopie>/z.json`` und
    ``<arbeitskopie>/tests/z.json`` alle drei **angenommen**.

    Der Pfad wird hier aus dem Modul selbst abgeleitet, nicht getippt -- ein fester
    Pfad haette an einer anderen Arbeitskopie nichts geprueft.
    """
    import mt5_trading_ai.execution.risiko_zustand as modul

    baum = Path(modul.__file__).resolve().parents[2]
    for ort in ("betrieb/z.json", "z.json", "tests/z.json"):
        ziel = baum.joinpath(*ort.split("/"))
        with pytest.raises(ZustandsortFehler):
            standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": str(ziel)})
        with pytest.raises(ZustandsortFehler):
            standard_zustandsdatei(
                umgebung={"MT5_RISIKO_ZUSTAND_ORDNER": str(ziel.parent)}
            )


def test_die_ortsgarantie_nennt_genau_zwei_baeume() -> None:
    """Paketbaum und der Baum, der ihn enthaelt -- beide abgeleitet, keiner geraten.

    Die zweite Grenze ist der Kern der Reparatur: sie deckt ``betrieb/``, ``tests/``
    und die Wurzel ab. Weiter reicht die Zusage nicht, und sie behauptet es auch
    nicht -- „irgendein anderer Arbeitsbaum" liesse sich nur raten.
    """
    import mt5_trading_ai.execution.risiko_zustand as modul

    paket = Path(modul.__file__).resolve().parents[1]
    assert verbotene_baeume() == (paket, paket.parent)


def test_ausserhalb_des_baums_geht_ein_absoluter_pfad_durch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Die Gegenprobe: die Sperre trifft nur den Fall, den sie treffen soll.

    Ohne sie waere „verbotene Baeume" womoeglich eine Regel, die jeden Pfad abweist --
    ein Melder, der immer ausloest, ist so wenig wert wie einer, der nie ausloest.
    Zusaetzlich geprueft: ein Anker an anderer Stelle verschiebt die Grenze wirklich,
    die Regel haengt also am Ort des Pakets und nicht an einer festen Zeichenkette.
    """
    ziel = tmp_path / "risikozustand.json"
    assert standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": str(ziel)}) == ziel

    anker = tmp_path / "irgendwo" / "paket"
    anker.mkdir(parents=True)
    assert verbotene_baeume(anker=anker) == (anker, tmp_path / "irgendwo")
    assert tmp_path not in verbotene_baeume(anker=anker)


# --- 3) Unsichtbare Freigabekennungen -------------------------------------------


def test_eine_unsichtbare_kennung_ist_keine_freigabe() -> None:
    """``.strip()`` genuegt nicht: U+200B und Verwandte sind nicht ``isspace()``.

    Gemessen am Stand 651c752: ``freigabe_gueltig("\\u200b")`` war ``True``. Eine
    Freigabe traegt eine Kennung, an der man den Menschen spaeter findet -- ein
    Zeichen ohne Bildflaeche findet niemand, und niemand bemerkt es beim Lesen.

    Die Gegenprobe steht daneben: kurze SICHTBARE Kennungen bleiben gueltig. Sie sind
    schlechte Kennungen, aber sie stehen im Protokoll und ein Mensch sieht sie -- die
    Grenze verlaeuft an der Sichtbarkeit, nicht an der Laenge.
    """
    for zeichen in UNSICHTBAR:
        assert zeichen.isspace() is False  # deshalb reichte ``.strip()`` nicht
        assert zeichen.strip() == zeichen
        assert freigabe_gueltig(zeichen) is False
        assert freigabe_gueltig(f"  {zeichen}\t") is False
    for leer in (None, "", "   ", '\t\n', '\xa0', chr(0x3000)):
        assert freigabe_gueltig(leer) is False
    for echt in ("ops-2026-08-13", "0", "-", f"ops-1{UNSICHTBAR[0]}"):
        assert freigabe_gueltig(echt) is True


def test_release_drawdown_weist_eine_unsichtbare_kennung_ab(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Not-Aus faellt nicht auf ein Zeichen herein, das niemand sieht.

    Zwei Zusicherungen: der Wurf kommt, BEVOR etwas geaendert ist (der Halt steht
    danach unveraendert auf der Platte), und eine echte Kennung loest ihn weiterhin.
    """
    pfad = tmp_path / "z.json"
    lauf1 = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(lauf1, account=_konto("10000")).latch_halt is True

    lauf2 = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    for zeichen in UNSICHTBAR:
        with pytest.raises(ValueError):
            lauf2.release_drawdown(zeichen)
    assert _lies(pfad)["halt"]["aktiv"] is True

    lauf2.release_drawdown("ops-2026-08-13")
    assert _lies(pfad)["halt"]["aktiv"] is False


def test_eine_unsichtbare_kennung_erreicht_die_limit_pruefung_nicht(  # noqa: E501
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Der eigentliche Schaden sass eine Ebene tiefer, in ``risk/limits.py``.

    ``evaluate_limits`` prueft nur ``manual_release_id and .strip()``. Wuerde diese
    Schicht eine unsichtbare Kennung mitfuehren, waere sie dort eine gueltige
    Freigabe: der Zustand ginge auf ``drawdown_limit_manually_released`` statt auf
    ``HALTED``, und die Order waere angenommen -- ein Not-Aus, den ein unsichtbares
    Zeichen aufhebt.

    Von Hand gerechnet: Peak 12000, Equity 10000 -> Drawdown 1/6 = 16,67 % gegen 10 %.
    Ohne jede Freigabe ist das ``drawdown_limit_reached`` mit Latch. Genau das muss
    auch mit der unsichtbaren Kennung herauskommen.

    Die Beobachtung liegt bewusst **26 Stunden** zurueck: damit faellt der Peak in das
    30-Tage-Fenster, der Tagesstart wird aber beim Tageswechsel auf 10000 neu gesetzt.
    Der Tagesverlust ist dann 0 und kann die Aussage nicht mit verdecken -- geprueft
    wird genau ein Tor.

    Ohne Zustandsdatei (die Umgebung wird geraeumt): geprueft wird die Weitergabe der
    Kennung, nicht die Platte.
    """
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)

    for zeichen in UNSICHTBAR:
        rm = RiskManager(manual_release_id=zeichen)
        rm.observe_equity(NOW - timedelta(hours=26), Decimal("12000"))
        auth = _autorisiere(rm, account=_konto("10000"))
        assert auth.approved is False, zeichen
        assert auth.latch_halt is True, zeichen
        assert auth.reason == "risk_drawdown_limit_reached", zeichen

    # Gegenprobe: eine echte Kennung kommt bei ``evaluate_limits`` an und macht aus
    # demselben Drawdown ``drawdown_limit_manually_released`` -- kein Halt, kein
    # Latch, Order zulaessig. Die Strenge trifft nur die unsichtbare Kennung.
    echt = RiskManager(manual_release_id="ops-2026-08-13")
    echt.observe_equity(NOW - timedelta(hours=26), Decimal("12000"))
    assert _autorisiere(echt, account=_konto("10000")).approved is True


def test_die_freigabe_deckt_nur_die_episode_die_der_mensch_gesehen_hat(  # noqa: E501
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Zwei Wege, auf denen eine Freigabe verfaellt -- beide muessen begehbar sein.

    Eine Freigabe ist die Aussage eines Menschen ueber eine Lage, die er gesehen hat.
    Sie darf nicht zur Dauerlizenz werden, sonst haette ein einziges ``ops-1`` den
    Kill-Switch fuer den Rest des Prozesslebens abgeschaltet.

    Von Hand gerechnet, Peak durchgehend 12000 (die Beobachtung liegt 26 Stunden
    zurueck, der Tagesstart wird beim Tageswechsel auf die jeweils erste Equity des
    Tages gesetzt -- der Tagesverlust ist damit ueberall 0 und verdeckt nichts):

    * **Erholung.** 10000 -> 16,67 % (freigegeben, zulaessig); 12000 -> 0 % (unter der
      Grenze von 10 %, die Episode ist vorbei); wieder 10000 -> 16,67 %, jetzt ohne
      Freigabe: HALT.
    * **Vertiefung.** 10000 -> 16,67 % (freigegeben, Niveau festgehalten); 9000 ->
      3000/12000 = 25 % > 16,67 %: eine andere Lage als die freigegebene, also HALT.
    """
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)

    erholung = RiskManager(manual_release_id="ops-2026-08-13")
    erholung.observe_equity(NOW - timedelta(hours=26), Decimal("12000"))
    assert _autorisiere(erholung, account=_konto("10000")).approved is True
    assert (
        _autorisiere(
            erholung, account=_konto("12000"), now=NOW + timedelta(minutes=1)
        ).approved
        is True
    )
    wieder = _autorisiere(
        erholung, account=_konto("10000"), now=NOW + timedelta(minutes=2)
    )
    assert wieder.approved is False
    assert wieder.latch_halt is True
    assert wieder.reason == "risk_drawdown_limit_reached"

    vertiefung = RiskManager(manual_release_id="ops-2026-08-13")
    vertiefung.observe_equity(NOW - timedelta(hours=26), Decimal("12000"))
    assert _autorisiere(vertiefung, account=_konto("10000")).approved is True
    tiefer = _autorisiere(
        vertiefung, account=_konto("9000"), now=NOW + timedelta(minutes=1)
    )
    assert tiefer.approved is False
    assert tiefer.latch_halt is True
    assert tiefer.reason == "risk_drawdown_limit_reached"
