"""Tests fuer die Zustandshaltung der Risikoschicht (``execution/risiko_zustand.py``).

Der Schwerpunkt liegt auf der **fail-closed-Leiter**: was ein fehlender, leerer,
beschaedigter oder fremder Zustand bedeutet. Zu jedem Zweig gehoert hier ein Test, der
ihn wirklich betritt -- die Hausfehlerklasse dieses Repos ist der Melder, der per
Konstruktion nie ausloesen kann, und eine Sperre, die nur im Docstring steht, gehoert
dazu.

Die roten Eichfaelle (Halt und Tageskappe ueberdauern den Neustart) stehen in
``tests/test_risikozustand_eichfaelle.py``; sie kommen ohne Import dieses Moduls aus,
damit sie gegen HEAD an einer Zusicherung reissen und nicht am Sammeln.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest
from mt5_trading_ai.execution.risiko_zustand import (
    FENSTER_KORB,
    RISIKO_ZUSTAND_SCHEMA,
    RISIKO_ZUSTAND_SCHEMA_FENSTER,
    DateiZustand,
    FluechtigerZustand,
    RisikoLage,
    ZustandsortFehler,
    fenster_fortschreiben,
    korb_start,
    standard_zustandsdatei,
    standard_zustandsordner,
    zustandsordner_pruefen,
    zustandsordner_waehlen,
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


# --- Werkzeug -----------------------------------------------------------------


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


def _gueltige_datei(pfad: Path) -> None:
    """Lege eine sauber gebundene, vollstaendige Zustandsdatei an."""
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    rm.observe_equity(NOW, Decimal("10000"))
    rm.record_open_fill("EURUSD", NOW)


def _lies(pfad: Path) -> dict[str, Any]:
    daten: dict[str, Any] = json.loads(pfad.read_text(encoding="utf-8"))
    return daten


def _schreib(pfad: Path, daten: dict[str, Any]) -> None:
    pfad.write_text(json.dumps(daten), encoding="utf-8")


# --- Der Ort ------------------------------------------------------------------


def test_standardpfad_liegt_ausserhalb_des_arbeitsbaums(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Weder im Paketbaum (git) noch unter ``betrieb/`` (``git clean -xdf``).

    Gefahren auf der Plattform, auf der der Test gerade laeuft -- die Umgebung wird
    dafuer geraeumt, damit nicht eine gesetzte Variable die Aussage traegt.
    """
    pfad = standard_zustandsdatei()
    assert pfad.is_absolute()
    repo = Path(__file__).resolve().parents[1]
    assert repo not in pfad.resolve().parents
    teile = {teil.lower() for teil in pfad.parts}
    assert "betrieb" not in teile
    assert "mt5_trading_ai" in teile  # eigener Unterordner, nicht lose im Profil


def test_localappdata_wird_nur_unter_windows_gefragt() -> None:
    """Sonst laege die Zustandsdatei auf der CI (ubuntu-latest) IM Arbeitsbaum.

    Ein Windows-Pfad ist unter POSIX ein einziges **relatives** Namensstueck:
    ``Path("C:\\\\Users\\\\<konto>\\\\AppData\\\\Local")`` hat dort weder Wurzel noch
    Laufwerk. ``resolve()`` haengt das Arbeitsverzeichnis davor -- und damit landet die
    Datei mit dem Drawdown-Halt im Repo, wo ``git clean -xdf`` sie loescht und der
    naechste Start sie als „neu" und damit als „frei" liest.

    Beide Plattformen werden hier **explizit** gefahren, nicht die des Testlaeufers:
    die Regel muss auf beiden gelten, und ``os.name`` laesst sich nicht umbiegen, ohne
    ``pathlib`` mitzureissen.

    Bis T6 fiel dieser Test auf ubuntu-latest (CI-Lauf 4d02db3, Beleg
    ``00-ci-nach-t0.txt``): ``standard_zustandsordner`` pruefte den Windows-Kandidaten
    mit dem ``Path`` der laufenden Plattform, und ``PurePosixPath("C:\\\\...")`` ist
    nicht absolut -- der Windows-Zweig nahm dort den Heimatpfad. Seitdem entscheidet
    die Pfadregel der GEFRAGTEN Plattform (``PureWindowsPath`` bzw. ``PurePosixPath``),
    und dieser Test gibt jedem Zweig einen Pfad, der in dessen Regeln absolut ist, und
    vergleicht in denselben Regeln -- so prueft er auf beiden Rechnern dasselbe. Die
    fruehere Fassung nahm ``Path.home()`` als XDG-Wert; der ist nur auf dem Rechner
    absolut, auf dem der Test gerade laeuft.
    """
    lokal = r"C:\Users\<konto>\AppData\Local"  # absolut nur in Windows-Regeln
    xdg = "/home/test/eigener-zustand"  # absolut nur in POSIX-Regeln
    umgebung = {"LOCALAPPDATA": lokal, "XDG_STATE_HOME": xdg}
    windows = standard_zustandsordner(umgebung=umgebung, ist_windows=True)
    posix = standard_zustandsordner(umgebung=umgebung, ist_windows=False)

    # Der Grund des frueheren Fehlschlags, auf jedem Rechner nachrechenbar: die
    # POSIX-Sicht haelt den Windows-Pfad fuer relativ, die Windows-Sicht fuer absolut.
    assert PurePosixPath(lokal).is_absolute() is False
    assert PureWindowsPath(lokal).is_absolute() is True

    # Unter Windows zaehlt LOCALAPPDATA -- verglichen in Windows-Pfadregeln, in denen
    # ``/`` und ``\\`` gleichermassen trennen; so gilt die Aussage auch dort, wo das
    # zurueckgegebene ``Path`` ein PosixPath mit einem Windows-Namensstueck ist.
    assert PureWindowsPath(str(windows)) == PureWindowsPath(
        lokal, "mt5_trading_ai", "risiko"
    )
    assert PureWindowsPath(str(windows)).is_absolute()
    # ... unter POSIX zaehlt XDG, und der Windows-Pfad taucht nirgends auf -- auch
    # nicht als relatives Stueck, das ``resolve()`` ins Repo haengen wuerde.
    assert PurePosixPath(posix.as_posix()) == PurePosixPath(
        xdg, "mt5_trading_ai", "risiko"
    )
    assert PurePosixPath(posix.as_posix()).is_absolute()
    assert "AppData" not in str(posix)


def test_eine_unbrauchbare_systemvariable_wird_uebergangen() -> None:
    """Relativ oder leer heisst „nicht gesetzt", nicht „dann eben relativ".

    ``LOCALAPPDATA``/``XDG_STATE_HOME`` sind keine Anweisung des Betreibers, sondern
    eine Auskunft der Plattform. Ist sie unbrauchbar, gilt der naechste Kandidat -- und
    der ist immer absolut.
    """
    for umgebung in ({"LOCALAPPDATA": "relativ/lokal"}, {"LOCALAPPDATA": ""}):
        ordner = standard_zustandsordner(umgebung=umgebung, ist_windows=True)
        assert ordner.is_absolute()
        assert Path.home() in ordner.parents


def test_relativer_zustandsordner_wird_abgewiesen() -> None:
    """Der Betreiber hat einen Ort GENANNT -- ein stiller anderer waere schlimmer.

    Zurechtbiegen hiesse: der Halt liegt woanders, als der Betreiber denkt. Also ein
    Wurf, und zwar beim Waehlen des Ordners (``--zustandsordner``, D8) -- vor dem Bau
    des ``RiskManager`` und vor der ersten Order.
    """
    for relativ in ("betrieb", "betrieb/risikozustand.json", "."):
        with pytest.raises(ZustandsortFehler):
            zustandsordner_pruefen(relativ)
    # Gegenprobe: absolut geht durch.
    absolut = Path.home() / "eigener-zustand"
    assert zustandsordner_pruefen(str(absolut)) == absolut


def test_ein_pfad_im_paketbaum_wird_abgewiesen() -> None:
    """Dort landete der Halt in git -- und ein ``git checkout`` waere die Freigabe.

    Das ist die zweite Haelfte der Ortsgarantie: absolut allein genuegt nicht, wenn
    der absolute Pfad ins Paket zeigt. Die Grenze ist hier exakt bekannt und muss
    nicht geraten werden.
    """
    import mt5_trading_ai.execution.risiko_zustand as modul

    im_paket = Path(modul.__file__).resolve().parents[1]
    with pytest.raises(ZustandsortFehler):
        zustandsordner_pruefen(im_paket)


def test_der_genannte_ordner_schlaegt_den_standardordner(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwei Konten = zwei Ordner; der Betreiber nennt ihn je Lauf (``--zustandsordner``).
    Keine Umgebungsvariable entscheidet mehr (D8, E-005)."""
    assert zustandsordner_waehlen(tmp_path / "ordner") == tmp_path / "ordner"
    assert zustandsordner_waehlen(None) == standard_zustandsordner()
    assert standard_zustandsdatei(ordner=tmp_path / "ordner") == (
        tmp_path / "ordner" / "risikozustand.json"
    )


def test_ohne_zustand_ist_der_riskmanager_nicht_konstruierbar() -> None:
    """D8: ``RiskManager(zustand=FluechtigerZustand())`` gibt es nicht mehr; fluechtig heisst so und ist ablesbar."""
    ohne_zustand = RiskManager
    with pytest.raises(TypeError):
        ohne_zustand()  # der Konstruktor verlangt zustand=
    assert RiskManager(zustand=FluechtigerZustand()).zustand_dauerhaft is False


def test_mit_datei_ist_die_schicht_dauerhaft(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert (
        RiskManager(zustand=DateiZustand(tmp_path / "z.json")).zustand_dauerhaft is True
    )


# --- Die fail-closed-Leiter ---------------------------------------------------


def test_fehlende_datei_ist_neu_und_kein_halt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der erste Start einer Maschine hat nichts verloren -- also kein Halt.

    Diese Richtung traegt nur, weil die Datei ausserhalb des Arbeitsbaums liegt (siehe
    ``test_standardpfad_liegt_ausserhalb_des_arbeitsbaums``): sie kann nicht durch
    einen Routinebefehl verschwinden.
    """
    befund = DateiZustand(tmp_path / "fehlt.json").laden()
    assert befund.herkunft == "neu"
    assert befund.sperrgrund is None
    assert befund.lage.halt is False
    assert befund.lage.zaehler_gesperrt is False
    assert _autorisiere(_lauf(tmp_path / "fehlt.json")).approved is True


def test_leere_datei_haelt_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pfad = tmp_path / "z.json"
    pfad.write_text("", encoding="utf-8")
    befund = DateiZustand(pfad).laden()
    assert befund.sperrgrund == "zustand_datei_leer"
    assert befund.lage.halt is True


def test_beschaedigte_datei_haelt_an_und_latcht(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Unlesbar heisst angehalten -- sonst waere Beschaedigen der Weg an der
    Freigabe vorbei."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    pfad.write_bytes(b"{ das ist kein json")

    auth = _autorisiere(_lauf(pfad))
    assert auth.approved is False
    assert auth.latch_halt is True
    assert auth.reason == "risk_zustand_kein_json"


def test_fremdes_schema_haelt_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Eine Marke, die wir nicht kennen, koennte einen Halt anders benannt haben."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["schema"] = "risiko-zustand-v99"
    _schreib(pfad, daten)
    assert DateiZustand(pfad).laden().sperrgrund == "zustand_fremdes_schema"


def test_unlesbare_bindung_haelt_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ohne lesbare Bindung ist nicht feststellbar, ZU WEM der Zustand gehoert."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["bindung"]["salz"] = "keine hexziffern"
    _schreib(pfad, daten)
    assert DateiZustand(pfad).laden().sperrgrund == "zustand_bindung_unlesbar"


def test_kaputter_halt_abschnitt_haelt_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["halt"]["aktiv"] = "vielleicht"
    _schreib(pfad, daten)
    befund = DateiZustand(pfad).laden()
    assert befund.lage.halt is True
    assert befund.sperrgrund is not None
    assert befund.sperrgrund.startswith("zustand_halt_unlesbar")


def test_kaputtes_equity_fenster_haelt_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Nicht bewertbar heisst nicht null -- sonst waere der Peak die aktuelle Equity.

    Genau das ist der reparierte Fehler: ein leeres Fenster laesst
    ``_window_peak`` auf die aktuelle Equity fallen und den Drawdown auf null.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["equity"]["fenster"] = [["2026-08-13T12:00:00+00:00", "nicht zahl"]]
    _schreib(pfad, daten)
    befund = DateiZustand(pfad).laden()
    assert befund.lage.halt is True
    assert befund.sperrgrund is not None
    assert befund.sperrgrund.startswith("zustand_equity_unlesbar")


def test_naiver_zeitstempel_ist_unlesbar(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ohne Zone unlesbar, nicht „vermutlich UTC".

    Raten waere doppelt falsch: ein falsch geratener Korb wandert aus dem Fenster,
    der Peak sinkt und der Halt wird milder. Und im Order-Pfad wuerde der Vergleich
    mit dem zonenbehafteten ``now`` einen ``TypeError`` werfen statt abzulehnen.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["equity"]["fenster"] = [["2026-08-13T12:00:00", "10000"]]
    _schreib(pfad, daten)
    assert DateiZustand(pfad).laden().lage.halt is True


def test_kaputte_offene_positionen_halten_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Sie zaehlen gegen den Positionsdeckel; „leer" waere die milde Richtung."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["offene_positionen"] = [{"instrument": "EURUSD"}]  # ohne Eroeffnungszeit
    _schreib(pfad, daten)
    befund = DateiZustand(pfad).laden()
    assert befund.lage.halt is True
    assert befund.sperrgrund is not None
    assert befund.sperrgrund.startswith("zustand_positionen_unlesbar")


# --- Der Tageszaehler: die andere Irrtumsrichtung ------------------------------


def test_kaputter_zaehler_sperrt_den_tag_ohne_zu_halten(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Die zweite, ausdruecklich ANDERE Richtung: ausgeschoepft, aber kein Halt.

    Belegt zugleich, dass die Abschnitte einzeln aufgeloest werden -- waere der
    Zaehlerdefekt ebenfalls ein Halt, koennte dieser Zweig nie beobachtet werden.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["tageszaehler"]["je_konto"] = "drei"
    _schreib(pfad, daten)

    befund = DateiZustand(pfad).laden()
    assert befund.lage.halt is False  # KEIN Halt
    assert befund.sperrgrund is None
    assert befund.lage.zaehler_gesperrt is True

    auth = _autorisiere(_lauf(pfad))
    assert auth.approved is False
    assert auth.reason == "throttle_tageszaehler_unlesbar"
    assert auth.latch_halt is False  # keine menschliche Freigabe noetig


def test_zaehlersperre_ueberlebt_den_ersten_takt_und_faellt_am_folgetag(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der Hausfehler waere hier: die Sperre loest sich beim ersten Takt selbst auf.

    Der Zaehlerabschnitt kommt ohne lesbaren Tag herein. Der erste ``authorize``
    setzt den Handelstag -- wuerde ``_roll_trade_day`` die Sperre schon bei diesem
    Setzen loeschen, koennte sie per Konstruktion nie greifen.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["tageszaehler"] = "kaputt"
    _schreib(pfad, daten)

    rm = _lauf(pfad)
    assert _autorisiere(rm).reason == "throttle_tageszaehler_unlesbar"
    # Noch derselbe Tag, zweiter Takt -- die Sperre haelt.
    zweiter = _autorisiere(rm, now=NOW + timedelta(minutes=1))
    assert zweiter.reason == "throttle_tageszaehler_unlesbar"
    # Folgetag -- sie verfaellt, ohne dass ein Mensch etwas tun muss.
    assert _autorisiere(rm, now=NOW + timedelta(days=1)).approved is True


def test_zaehlersperre_ueberdauert_den_neustart(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Sonst waere die Sperre nach dem naechsten Start weg -- am selben Tag."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    daten = _lies(pfad)
    daten["tageszaehler"] = "kaputt"
    _schreib(pfad, daten)

    assert _autorisiere(_lauf(pfad)).reason == "throttle_tageszaehler_unlesbar"
    # Neustart am selben Tag: immer noch gesperrt.
    zweiter = _autorisiere(_lauf(pfad), now=NOW + timedelta(hours=3))
    assert zweiter.reason == "throttle_tageszaehler_unlesbar"
    # Neustart am Folgetag: frei.
    assert _autorisiere(_lauf(pfad), now=NOW + timedelta(days=1)).approved is True


# --- Kontobindung -------------------------------------------------------------


def test_fremdes_konto_wird_nicht_stillschweigend_uebernommen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Betraege eines fremden Kontos machen den Drawdown beliebig -- also Ablehnung."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)

    auth = _autorisiere(_lauf(pfad), account=_konto(konto="99887766"))
    assert auth.approved is False
    assert auth.reason == "risk_zustand_fremdes_konto"
    assert auth.latch_halt is True


def test_fremde_waehrung_wird_nicht_stillschweigend_uebernommen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)

    auth = _autorisiere(_lauf(pfad), account=_konto(waehrung="EUR"))
    assert auth.approved is False
    assert auth.reason == "risk_zustand_fremde_waehrung"
    assert auth.latch_halt is True


def test_richtiges_konto_darf_weiterhandeln(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Gegenprobe: die Bindung sperrt nicht einfach alles."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    assert _autorisiere(_lauf(pfad), now=NOW + timedelta(hours=2)).approved is True


def test_kontowechsel_mitten_im_lauf_wird_erkannt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der zweite Weg in denselben Fehler: nicht die Datei, sondern der Aufrufer."""
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad)
    assert _autorisiere(rm).approved is True
    auth = _autorisiere(
        rm, account=_konto(konto="11223344"), now=NOW + timedelta(hours=2)
    )
    assert auth.reason == "risk_zustand_fremdes_konto"
    # Und die Ablehnung bleibt -- auch fuer das urspruenglich richtige Konto. Wer die
    # Verdrahtung mitten im Lauf wechselt, bekommt keinen halb gefuehrten Zustand,
    # sondern einen neuen Prozess.
    weiter = _autorisiere(rm, now=NOW + timedelta(hours=3))
    assert weiter.reason == "risk_zustand_fremdes_konto"


def test_fremder_zugriff_vergiftet_die_datei_des_richtigen_kontos_nicht(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Der Fehlgriff eines Aufrufers darf kein fremdes Konto anhalten."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    vorher = pfad.read_text(encoding="utf-8")

    _autorisiere(_lauf(pfad), account=_konto(konto="99887766"))
    assert pfad.read_text(encoding="utf-8") == vorher

    # Und das richtige Konto handelt danach weiter.
    assert _autorisiere(_lauf(pfad), now=NOW + timedelta(hours=2)).approved is True


# --- Halt und Freigabe --------------------------------------------------------


def test_freigabe_ueberdauert_den_neustart_nicht(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Halt ueberdauert, die Freigabe nicht -- die Asymmetrie ist Absicht.

    Nach der Freigabe ist der Latch geloescht. Reisst der Drawdown danach erneut,
    haelt es wieder an, statt auf einer Freigabe weiterzulaufen, die ein Mensch fuer
    eine andere Lage erteilt hat.
    """
    pfad = tmp_path / "z.json"
    lauf1 = _lauf(pfad)
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(lauf1, account=_konto("10000")).latch_halt is True

    lauf2 = _lauf(pfad)
    lauf2.release_drawdown("ops-1")
    assert (
        _autorisiere(
            lauf2, account=_konto("12000"), now=NOW + timedelta(minutes=1)
        ).approved
        is True
    )

    # Neustart, und der Drawdown reisst erneut: keine ueberdauernde Freigabe.
    lauf3 = _lauf(pfad)
    auth = _autorisiere(lauf3, account=_konto("9000"), now=NOW + timedelta(minutes=2))
    assert auth.approved is False
    assert auth.latch_halt is True


def test_freigabe_am_konstruktor_loest_einen_unlesbaren_halt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ein Halt ohne Ausgang wird im Betrieb ausgebaut statt bedient.

    Der Ausgang ist derselbe menschliche Akt wie sonst: eine Freigabekennung. Nicht
    „Datei loeschen" -- das naehme den Beweis mit.

    Die Freigabe loest dabei **nur den Halt**, nicht die Zaehlersperre. Das ist kein
    Versehen: ein unlesbarer Zustand hat auch die Tageszaehler verloren, und eine
    Freigabe ist eine Aussage ueber den Drawdown, keine ueber die Frage, wie viele
    Trades heute schon liefen. Die Zaehlersperre braucht darum keinen Menschen -- sie
    laeuft um Mitternacht ab.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    pfad.write_bytes(b"kaputt")

    ohne = _autorisiere(_lauf(pfad))
    assert ohne.approved is False
    assert ohne.latch_halt is True  # ohne Freigabe: Halt mit Latch

    pfad.write_bytes(b"kaputt")
    mit = _autorisiere(_lauf(pfad, manual_release_id="ops-2026-08-13"))
    assert mit.approved is False
    assert mit.latch_halt is False  # der Halt ist geloest ...
    assert mit.reason == "throttle_tageszaehler_unlesbar"  # ... die Tagessperre nicht
    # ... und sie laeuft von selbst ab, ohne dass jemand etwas tun muss.
    assert _autorisiere(_lauf(pfad), now=NOW + timedelta(days=1)).approved is True

    # Eine LEERE Kennung ist keine Freigabe -- sonst waere der Ausgang ein Tippfehler.
    pfad.write_bytes(b"kaputt")
    leer = _autorisiere(_lauf(pfad, manual_release_id="   "))
    assert leer.approved is False
    assert leer.latch_halt is True


def test_kaputte_datei_wird_zur_beweissicherung_beiseite_gelegt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ein Halt, dessen Grund niemand mehr nachpruefen kann, wird weggeklickt."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    pfad.write_bytes(b"{ kaputt")

    _autorisiere(_lauf(pfad))  # bindet und schreibt -> Beweis wird gezogen
    beiseite = list(tmp_path.glob("z.json.unlesbar-*"))
    assert len(beiseite) == 1
    assert beiseite[0].read_bytes() == b"{ kaputt"


def test_beweissicherung_nimmt_den_halt_nicht_mit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwischen Lesen und erstem Schreiben darf keine Luecke ohne Datei entstehen.

    Die kaputte Datei gleich beim Laden beiseitezuschieben waere bequem und waere ein
    Loch: stuerbe der Prozess vor der ersten Order, faende der naechste Start gar
    keine Datei mehr -- laese das als „neu" und damit als „frei". Hier wird genau das
    nachgestellt: laden, nichts weiter tun, neu starten.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    pfad.write_bytes(b"{ kaputt")

    _lauf(pfad)  # nur laden -- kein authorize, keine Bindung, kein Schreiben
    assert pfad.exists()
    assert pfad.read_bytes() == b"{ kaputt"

    # Der naechste Start haelt weiterhin an.
    zweiter = _autorisiere(_lauf(pfad))
    assert zweiter.approved is False
    assert zweiter.latch_halt is True


def test_bindung_erkennt_einen_waehrungswechsel_im_laufenden_speicher(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Auch der zweite Zweig in ``binde`` muss greifen, nicht nur der erste.

    Ist ein Speicher einmal gebunden, prueft er weiter -- gegen Kontonummer UND
    Waehrung. Ohne diesen Test waere der Waehrungszweig hinter der bereits
    gesetzten Bindung eine Zeile, die nie ausgefuehrt wird.
    """
    speicher = DateiZustand(tmp_path / "z.json")
    assert speicher.binde(KONTO, "USD") is None
    assert speicher.binde(KONTO, "USD") is None
    assert speicher.binde(KONTO, "EUR") == "zustand_fremde_waehrung"
    assert speicher.binde("99887766", "USD") == "zustand_fremdes_konto"


# --- Das Equity-Fenster -------------------------------------------------------


def test_korbhoechststand_senkt_den_peak_nie(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Die Kornung darf den Drawdown nur ueber-, nie unterschaetzen."""
    fenster: list[tuple[datetime, Decimal]] = []
    roh: list[Decimal] = []
    for minute in range(180):
        ts = NOW + timedelta(minutes=minute)
        equity = Decimal(10000 + (minute * 37) % 500)
        roh.append(equity)
        fenster = fenster_fortschreiben(fenster, ts, equity, timedelta(days=30))
    assert max(eq for _korb, eq in fenster) == max(roh)


def test_fenster_bleibt_beschraenkt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """30 Tage Sekundentakt duerfen keine Hunderttausende Eintraege werden."""
    fenster: list[tuple[datetime, Decimal]] = []
    for stunde in range(24 * 40):  # 40 Tage bei einem 30-Tage-Fenster
        ts = NOW + timedelta(hours=stunde)
        fenster = fenster_fortschreiben(
            fenster, ts, Decimal("10000"), timedelta(days=30)
        )
    # 30 Tage Koerbe plus der eine Korb, der wegen des Schnitts am Korb-ENDE noch
    # mitlaeuft, plus der laufende.
    assert len(fenster) <= 24 * 30 + 2


def test_schnitt_am_korbende_nicht_am_korbanfang() -> None:
    """Am Anfang zu schneiden wuerfe bis zu eine Stunde zu frueh -- Peak zu tief."""
    fenster_dauer = timedelta(hours=5)
    alt = NOW
    fenster = fenster_fortschreiben([], alt, Decimal("12000"), fenster_dauer)
    # Genau am Rand: der Korbanfang liegt schon ausserhalb, das Korbende nicht.
    spaeter = korb_start(alt) + fenster_dauer + FENSTER_KORB - timedelta(minutes=1)
    fenster = fenster_fortschreiben(fenster, spaeter, Decimal("10000"), fenster_dauer)
    assert max(eq for _korb, eq in fenster) == Decimal("12000")


# --- Schreiben ----------------------------------------------------------------


def test_ohne_bindung_wird_nur_das_fenster_geschrieben(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Halt, Zaehler und Positionen ohne geprueftes Konto waeren eine Vermischung.

    Das Equity-Fenster ist die eine Ausnahme, und zwar mit Rechnung: der Peak ist ein
    Maximum, ein fremder Korb kann ihn nur **heben** -- also den Drawdown nur
    vergroessern, also nur eher halten. Alles andere kann in der milden Richtung irren
    und wartet deshalb auf den Kontobeweis.
    """
    pfad = tmp_path / "z.json"
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.gebunden is False
    assert (
        speicher.sichern(
            RisikoLage(
                halt=True,
                halt_grund="drawdown_halt_gelatcht",
                zaehler_gesperrt=True,
                trades_konto=7,
                trades_je_instrument={"EURUSD": 7},
                tagesstart_equity=Decimal("9000"),
                equity_tag=NOW.date(),
                offene_positionen=[("EURUSD", NOW)],
                equity_fenster=[(NOW, Decimal("12000"))],
            )
        )
        is None
    )
    daten = _lies(pfad)
    assert daten["schema"] == RISIKO_ZUSTAND_SCHEMA_FENSTER
    assert set(daten) == {"schema", "geschrieben_am", "equity"}
    assert daten["equity"] == {"fenster": [[NOW.isoformat(), "12000"]]}

    # Und mit Bindung steht wieder alles da.
    assert speicher.binde(KONTO, WAEHRUNG) is None
    assert speicher.gebunden is True
    speicher.sichern(RisikoLage(halt=True))
    voll = _lies(pfad)
    assert voll["schema"] == RISIKO_ZUSTAND_SCHEMA
    assert voll["halt"]["aktiv"] is True


def test_die_ungebundene_datei_haelt_nicht_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Unvollstaendig **und zwar absichtlich** -- das ist kein verlorener Zustand.

    Waere sie ein Halt, haette jeder Neustart nach einem Lauf ohne Order angehalten,
    und die Reparatur waere schlimmer als der Fehler.
    """
    pfad = tmp_path / "z.json"
    schreiber = DateiZustand(pfad)
    schreiber.laden()
    schreiber.sichern(RisikoLage(equity_fenster=[(NOW, Decimal("10000"))]))

    befund = DateiZustand(pfad).laden()
    assert befund.herkunft == "fenster"
    assert befund.sperrgrund is None
    assert befund.lage.halt is False
    assert befund.lage.zaehler_gesperrt is False
    assert befund.lage.equity_fenster == [(NOW, Decimal("10000"))]


def test_eine_kaputte_ungebundene_datei_haelt_sehr_wohl_an(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Absichtlich unvollstaendig heisst nicht beliebig."""
    pfad = tmp_path / "z.json"
    _schreib(
        pfad,
        {
            "schema": RISIKO_ZUSTAND_SCHEMA_FENSTER,
            "equity": {"fenster": [["2026-08-13T12:00:00+00:00", "keine zahl"]]},
        },
    )
    befund = DateiZustand(pfad).laden()
    assert befund.lage.halt is True
    assert befund.sperrgrund is not None
    assert befund.sperrgrund.startswith("zustand_fenster_unlesbar")


def test_der_peak_ueberdauert_einen_neustart_ohne_order(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Betriebsweg: ``RiskManager(zustand=FluechtigerZustand())`` ohne Konto, Dauerhaftigkeit ueber die Datei.

    Der Scheduler beobachtet Equity je Takt, autorisiert wird seltener. Ginge das
    Fenster bis zur ersten Order verloren, faende der naechste Start einen niedrigeren
    Peak, einen kleineren Drawdown und keinen Halt -- der reparierte Fehler, eine
    Ebene tiefer.
    """
    pfad = tmp_path / "z.json"
    lauf1 = _lauf(pfad)
    lauf1.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert pfad.exists()

    auth = _autorisiere(_lauf(pfad), account=_konto("10000"))
    assert auth.approved is False
    assert auth.latch_halt is True
    assert auth.reason == "risk_drawdown_limit_reached"


def test_eine_vorhandene_gebundene_datei_wird_nur_am_fenster_fortgeschrieben(  # noqa: E501
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Ohne Kontobeweis wird nichts ersetzt -- nur der eine unbedenkliche Abschnitt.

    Der Fall ist der haeufige: eine Datei aus frueheren Laeufen liegt da, der neue
    Prozess beobachtet Equity, hat aber noch keine Order gesehen. Bindung, Halt,
    Zaehler und Positionen des Kontos muessen dabei Wert fuer Wert stehen bleiben.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    vorher = _lies(pfad)

    lauf = _lauf(pfad)  # kein konto_id -> ungebunden
    lauf.observe_equity(NOW + timedelta(hours=1), Decimal("12345"))

    nachher = _lies(pfad)
    for abschnitt in (
        "schema",
        "waehrung",
        "bindung",
        "halt",
        "tageszaehler",
        "letzter_trade_at",
        "offene_positionen",
    ):
        assert nachher[abschnitt] == vorher[abschnitt], abschnitt
    assert nachher["equity"]["tag"] == vorher["equity"]["tag"]
    assert nachher["equity"]["tagesstart"] == vorher["equity"]["tagesstart"]
    assert ["2026-08-13T13:00:00+00:00", "12345"] in nachher["equity"]["fenster"]

    # Und der Peak ist damit fuer den naechsten Start da.
    auth = _autorisiere(
        _lauf(pfad), account=_konto("10000"), now=NOW + timedelta(hours=2)
    )
    assert auth.approved is False
    assert auth.latch_halt is True


def test_ungebunden_wird_kein_fremder_halt_ueberschrieben(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ein Prozess, der nur zuschaut, darf keinen Halt loeschen.

    Der gefaehrliche Fall am ungebundenen Schreiben: Lauf A schaut seit Stunden zu
    (ungebunden, Stand von damals im Speicher), Lauf B handelt und setzt einen Halt.
    Schriebe A dann seinen alten Schnappschuss zurueck, waere der Halt weg -- und die
    Reparatur haette ein neues Loch derselben Art aufgemacht. Also wird unmittelbar
    vor dem Schreiben neu gelesen und nur das Fenster ersetzt.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    zuschauer = _lauf(pfad)  # laedt den Stand OHNE Halt

    # Inzwischen setzt ein zweiter Lauf den Halt (und schreibt ihn).
    handelnder = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    handelnder.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    assert _autorisiere(handelnder, account=_konto("10000")).latch_halt is True
    assert _lies(pfad)["halt"]["aktiv"] is True

    zuschauer.observe_equity(NOW + timedelta(hours=1), Decimal("11000"))

    assert _lies(pfad)["halt"]["aktiv"] is True
    # Und das Fenster ist vereinigt, nicht ersetzt: der hoehere Korb bleibt.
    fenster = {korb: wert for korb, wert in _lies(pfad)["equity"]["fenster"]}
    assert fenster["2026-08-13T10:00:00+00:00"] == "12000"
    assert fenster["2026-08-13T13:00:00+00:00"] == "11000"


def test_ein_unlesbarer_zustand_wird_ungebunden_nicht_ueberschrieben(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Dort steht ein Halt -- und der Beweis gehoert vor seine Ersetzung."""
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    pfad.write_bytes(b"{ kaputt")

    lauf = _lauf(pfad)
    lauf.observe_equity(NOW, Decimal("12000"))
    assert pfad.read_bytes() == b"{ kaputt"
    assert list(tmp_path.glob("z.json.unlesbar-*")) == []

    # Und derselbe Schutz, wenn die Datei erst NACH dem Laden kaputtgeht: gelesen
    # wird unmittelbar vor dem Schreiben, und ein unlesbarer Stand wird nicht
    # ersetzt -- sonst naehme ein Zuschauer den Beweis mit.
    zweiter = tmp_path / "z2.json"
    _gueltige_datei(zweiter)
    zuschauer = _lauf(zweiter)
    zweiter.write_bytes(b"{ inzwischen kaputt")
    zuschauer.observe_equity(NOW + timedelta(hours=1), Decimal("12000"))
    assert zweiter.read_bytes() == b"{ inzwischen kaputt"


# --- Wenn die Platte nicht mitspielt ------------------------------------------


def _blockiere(pfad: Path) -> None:
    """Mache jeden Schreibvorgang auf ``pfad`` unmoeglich -- auf jeder Plattform.

    Die Nebendatei wird zum **Verzeichnis**; ``write_text`` scheitert damit unter
    Windows mit ``PermissionError`` und unter POSIX mit ``IsADirectoryError`` -- beides
    ``OSError``. Kein ``chmod``, keine Rechteakrobatik, kein Plattformzweig.
    """
    pfad.with_name(pfad.name + ".neu").mkdir(parents=True, exist_ok=True)


def test_ein_schreibfehler_wirft_nicht_sondern_meldet(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ein Wurf naehme dem Aufrufer sein OrderResult, waehrend die Position steht."""
    pfad = tmp_path / "z.json"
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(KONTO, WAEHRUNG) is None
    _blockiere(pfad)

    grund = speicher.sichern(RisikoLage(halt=True))
    assert grund is not None
    assert grund.startswith("zustand_nicht_gesichert")
    assert speicher.schreibfehler_text  # der Klartext steht fuer das Protokoll bereit


def test_der_order_pfad_stuerzt_nach_dem_fill_nicht_ab(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """``record_open_fill`` laeuft in ``venue/mt5.py`` NACH dem Fill.

    Wirft es, bekommt der Aufrufer statt des ``OrderResult`` eine Ausnahme, die er
    nicht erwartet -- und weiss nicht, dass er eine Position hat. Aus einem
    Plattenproblem wuerde eine unbeaufsichtigte offene Position.
    """
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    rm.record_open_fill("EURUSD", NOW)
    _blockiere(pfad)

    rm.record_open_fill("GBPUSD", NOW)  # kein Wurf
    rm.record_close("GBPUSD")
    rm.observe_equity(NOW, Decimal("10000"))


def test_ein_unsicherer_zustand_sperrt_die_naechste_eroeffnung(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Nichts Neues eroeffnen, solange nicht gesichert werden kann.

    Die milde Richtung waere: weiterhandeln und den Zaehler vergessen -- also genau
    der Fehler, gegen den diese Schicht gebaut ist. Kein Latch: die Aussage betrifft
    die Platte, nicht den Markt.
    """
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    assert _autorisiere(rm).approved is True
    _blockiere(pfad)
    rm.record_open_fill("EURUSD", NOW)

    auth = _autorisiere(rm, now=NOW + timedelta(hours=1))
    assert auth.approved is False
    assert auth.reason is not None
    assert auth.reason.startswith("risk_zustand_nicht_gesichert")
    assert auth.latch_halt is False
    assert auth.detail["zustandsdatei"] == str(pfad)
    assert auth.detail["schreibfehler"]


def test_die_marke_faellt_nur_durch_einen_gelungenen_schreibvorgang(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ein Beweis, keine Hoffnung -- aber auch keine Sperre ohne Ausgang."""
    pfad = tmp_path / "z.json"
    rm = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    _blockiere(pfad)
    rm.observe_equity(NOW, Decimal("10000"))
    assert _autorisiere(rm).approved is False

    # Zeitablauf allein heilt nichts.
    assert _autorisiere(rm, now=NOW + timedelta(days=1)).approved is False

    # Die Platte wird wieder schreibbar -- ohne Freigabe, ohne Neustart.
    pfad.with_name(pfad.name + ".neu").rmdir()
    assert _autorisiere(rm, now=NOW + timedelta(days=1, minutes=1)).approved is True
    assert _lies(pfad)["schema"] == RISIKO_ZUSTAND_SCHEMA


def test_schreiben_laesst_keine_nebendatei_liegen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Atomar per ``os.replace``: kein Fenster, in dem die Datei fehlt.

    Ein solches Fenster hiesse nach der Leiter oben „neu" und damit „frei" -- ein
    Halt, den ein unglueckliches Timing aufhebt.
    """
    pfad = tmp_path / "z.json"
    _gueltige_datei(pfad)
    assert {p.name for p in tmp_path.iterdir()} == {"z.json"}
    assert _lies(pfad)["schema"] == RISIKO_ZUSTAND_SCHEMA


def test_der_fill_wird_sofort_gesichert(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwischen Fill und Absturz liegt sonst genau der Trade, den niemand mehr zaehlt."""
    pfad = tmp_path / "z.json"
    politik = RiskPolicy(throttle=ThrottlePolicy(max_trades_per_account_per_day=2))
    rm = _lauf(pfad, politik, konto_id=KONTO, waehrung=WAEHRUNG)
    rm.record_open_fill("EURUSD", NOW)
    assert _lies(pfad)["tageszaehler"]["je_konto"] == 1


def test_offene_positionen_ueberdauern_den_neustart(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Positionsdeckel ist sonst nach jedem Neustart wieder leer."""
    pfad = tmp_path / "z.json"
    lauf1 = _lauf(pfad, konto_id=KONTO, waehrung=WAEHRUNG)
    for symbol in ("GBPUSD", "USDCHF", "AUDUSD"):
        lauf1.record_open_fill(symbol, NOW - timedelta(hours=2))

    lauf2 = _lauf(pfad)
    assert lauf2.open_position_count == 3
    auth = _autorisiere(lauf2)
    assert auth.approved is False
    assert auth.reason == "risk_concurrent_position_cap"

    # Und ein Schluss gibt den Platz wieder frei -- ueber den Neustart hinweg.
    lauf2.record_close("AUDUSD")
    assert _autorisiere(_lauf(pfad), now=NOW + timedelta(minutes=1)).approved is True
