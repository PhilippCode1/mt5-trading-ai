"""Die ablehnenden Zweige von ``execution/reconcile.py`` -- Buch gegen Broker (D7/D8).

Gemessen wurde ``execution/reconcile.py`` mit **79,4 % Zweigdeckung, 7 fehlende
Zweige** (``tools/zweigdeckung.py --messen``, Schwelle 90 %, Katalog A15). Was fehlte,
waren genau die Ausgaenge, wegen derer das Modul existiert: die, die ein Buch fuer
**defekt** erklaeren, statt es als leer zu lesen, und der, der bei einer unbekannten
Kennung die Platte in Ruhe laesst.

WARUM DIE ZUSICHERUNG NICHT AM RUECKGABEWERT HAENGT
---------------------------------------------------
Ein ``pytest.raises(PositionsbuchDefekt)`` beruehrt die Zeile und sagt nichts darueber,
ob das Haus danach noch eroeffnet. Der Zweck dieser Zweige ist eine **Folge**, und die
steht bei den Aufrufern: ``Mt5Venue.adopt_book`` latcht den Global-Halt mit Grund
(``positionsbuch_defekt:...``), jede eroeffnende Order faellt danach an ``global_halt``,
eine Schliessung bleibt frei, und ``tools/live_betrieb.py`` schreibt den Befund als
``startabgleich``-Satz ins Journal. Genau das steht hier in den Zusicherungen -- dazu
die Platte selbst: ein defektes oder fremdes Buch wird **nicht** ueberschrieben.

Zur Abgrenzung laeuft jeder Fall gegen seinen Nachbarn: die leere Datei (Absturz
zwischen ``open`` und ``write``) ist KEIN Defekt und sperrt nichts; die Fassung 2 ist
einer und wird nicht als leeres Buch weggelesen.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.execution.reconcile import (
    POSITIONSBUCH_FASSUNG,
    Buchposition,
    FluechtigesPositionsbuch,
    Positionsbuch,
    PositionsbuchDefekt,
)
from mt5_trading_ai.execution.risiko_zustand import (
    POSITIONSBUCH_DATEI,
    RISIKOZUSTAND_DATEI,
    DateiZustand,
)
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.mt5 import Mt5Position, Mt5Venue
from mt5_trading_ai.venue.protocol import (
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_mt5_venue import TS, FakeMt5Terminal, _catalog  # noqa: E402

#: Der Zeitstempel im Rohtext des Buches -- zwei Tage vor der Uhr des Venues.
EROEFFNET = (TS - timedelta(days=2)).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Werkzeug
# ---------------------------------------------------------------------------
def _satz(**abweichung: Any) -> dict[str, Any]:
    """Ein vollstaendiger Buchsatz als Rohtext-Objekt; ``abweichung`` verbiegt ihn."""
    satz: dict[str, Any] = {
        "kennung": "open-EURUSD-1",
        "ticket": "4711",
        "symbol": "EURUSD",
        "richtung": "kauf",
        "menge": "0.01",
        "eroeffnet_am": EROEFFNET,
        "stop": "1.09000",
    }
    satz.update(abweichung)
    return satz


def _ohne(feld: str, **abweichung: Any) -> dict[str, Any]:
    """Ein Buchsatz, dem ``feld`` fehlt (der Fall ``KeyError``)."""
    satz = _satz(**abweichung)
    del satz[feld]
    return satz


def _buch_schreiben(ordner: Path, inhalt: str) -> Path:
    """Rohtext an den Ort, an dem der Betrieb sein Buch sucht."""
    pfad = ordner / POSITIONSBUCH_DATEI
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def _buchtext(*saetze: Any, fassung: int = POSITIONSBUCH_FASSUNG) -> str:
    return json.dumps({"fassung": fassung, "positionen": list(saetze)})


def _buchposition(kennung: str, symbol: str, richtung: str) -> Buchposition:
    return Buchposition(
        kennung=kennung,
        ticket="4711",
        symbol=symbol,
        richtung=richtung,
        menge=Decimal("0.01"),
        eroeffnet_am=TS - timedelta(days=2),
        stop=Decimal("1.09000"),
    )


def _brokerposition() -> Mt5Position:
    """Eine Position, die der Broker wirklich fuehrt (Ticket B-1, long 0,02)."""
    return Mt5Position(
        ticket="B-1",
        symbol="EURUSD",
        is_buy=True,
        volume=Decimal("0.02"),
        entry_price=Decimal("1.10000"),
        stop_loss=None,
        take_profit=None,
        opened_at=TS - timedelta(days=1),
        unrealised_pnl=Decimal("0"),
        swap=Decimal("0"),
    )


def _venue(ordner: Path, positionen: tuple[Mt5Position, ...] = ()) -> Mt5Venue:
    """Ein verbundenes Venue auf dem Zustandsordner ``ordner`` (Demokonto, Fake)."""
    rm = RiskManager(zustand=DateiZustand(ordner / RISIKOZUSTAND_DATEI))
    venue = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True, positions=positionen),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=rm,
        clock=lambda: TS,
        zustandsordner=ordner,
    )
    venue.connect()
    return venue


def _eroeffnung(kennung: str = "open-EURUSD-neu") -> OrderRequest:
    return OrderRequest(
        kennung,
        "EURUSD",
        OrderSide.BUY,
        OrderType.MARKET,
        Decimal("0.01"),
        Decimal("1.09"),
    )


def _abgewiesene_eroeffnung(venue: Mt5Venue) -> str:
    """Der Grund, mit dem die naechste Eroeffnung faellt -- die Folge des Halts."""
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_eroeffnung())
    return fehler.value.reason


def _defekt_ergibt_halt(ordner: Path, erwartet: str) -> Mt5Venue:
    """Startabgleich auf einem defekten Buch: Befund, Halt, gesperrte Eroeffnung.

    Die drei Zusicherungen, die zusammen den Zweck jedes Defekt-Zweiges ausmachen:
    der Befund benennt ihn, der Halt-Latch steht mit genau diesem Grund, und die
    naechste Eroeffnung faellt daran.
    """
    venue = _venue(ordner)
    venue.adopt_book()

    abgleich = venue.startabgleich
    assert abgleich is not None
    assert abgleich.defekt is not None, "das defekte Buch blieb unbenannt"
    assert abgleich.defekt.startswith(erwartet), abgleich.defekt
    assert abgleich.auffaellig is True
    assert abgleich.geister_buch == (), (
        "aus einem defekten Buch wird nichts ausgetragen"
    )
    assert venue.is_halted() is True, "das defekte Buch latchte keinen Halt"
    assert f"positionsbuch_defekt:{abgleich.defekt}" in venue.halt_gruende
    assert _abgewiesene_eroeffnung(venue) == "global_halt"
    return venue


# ---------------------------------------------------------------------------
# Zweig 241->242: die leere Datei ist ein leeres Buch, kein Defekt
# ---------------------------------------------------------------------------
def test_ein_leeres_buch_auf_der_platte_sperrt_nichts(tmp_path: Path) -> None:
    """Genau diese Datei hinterlaesst ein Absturz zwischen ``open`` und ``write``.

    Ohne den Zweig liefe der leere Text in ``json.loads``, und der Start stuende mit
    einem Halt, den niemand aufloesen kann. Der Gegenpol steht darunter: dasselbe
    Ergebnis, wenn ueberhaupt keine Datei da ist.
    """
    pfad = _buch_schreiben(tmp_path, "   \n\t")

    assert Positionsbuch(pfad).laden() == ()
    assert Positionsbuch(tmp_path / "gibt-es-nicht.json").laden() == ()

    venue = _venue(tmp_path)
    venue.adopt_book()

    abgleich = venue.startabgleich
    assert abgleich is not None
    assert abgleich.defekt is None, abgleich.defekt
    assert venue.is_halted() is False, venue.halt_reason
    # Die Folge: der Betrieb eroeffnet weiter, und der leere Text ist danach ein Buch.
    ergebnis = venue.submit_order(_eroeffnung("open-EURUSD-nach-leer"))
    assert ergebnis.accepted is True
    assert [p.kennung for p in Positionsbuch(pfad).laden()] == ["open-EURUSD-nach-leer"]


# ---------------------------------------------------------------------------
# Zweig 239->240: nicht lesbar ist etwas anderes als nicht vorhanden
# ---------------------------------------------------------------------------
def test_ein_unlesbares_buch_latcht_den_halt(tmp_path: Path) -> None:
    """Ein Ordner an der Stelle der Datei: ``read_text`` wirft ``OSError``.

    ``FileNotFoundError`` heisst 'noch nichts gebucht' und ist harmlos; jeder andere
    ``OSError`` heisst 'ich weiss nicht, was gebucht ist' -- und Unwissen ist kein
    Grund weiterzuhandeln. Der Befund traegt darum ein anderes Wort
    (``positionsbuch_unlesbar``) als der defekte Inhalt.
    """
    (tmp_path / POSITIONSBUCH_DATEI).mkdir()

    with pytest.raises(PositionsbuchDefekt) as fehler:
        Positionsbuch(tmp_path / POSITIONSBUCH_DATEI).laden()
    assert str(fehler.value).startswith("positionsbuch_unlesbar:")

    _defekt_ergibt_halt(tmp_path, "positionsbuch_unlesbar:")
    # Und der Ordner steht noch: nichts hat ihn stillschweigend 'repariert'.
    assert (tmp_path / POSITIONSBUCH_DATEI).is_dir()


# ---------------------------------------------------------------------------
# Zweige 245->246, 247->248, 250->251: der Rahmen der Datei
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("inhalt", "erwartet"),
    [
        pytest.param(
            '{"fassung": 1, "positionen": [',
            # Gemessen unter CPython 3.11.7: "Expecting value: line 1 column 31".
            "positionsbuch_defekt: Expecting",
            id="245-zerrissenes-json",
        ),
        pytest.param(
            json.dumps([_satz()]),
            "positionsbuch_defekt: Fassung oder Objekt",
            id="247-liste-statt-objekt",
        ),
        pytest.param(
            _buchtext(_satz(), fassung=POSITIONSBUCH_FASSUNG + 1),
            "positionsbuch_defekt: Fassung oder Objekt",
            id="247-fremde-fassung",
        ),
        pytest.param(
            json.dumps({"fassung": POSITIONSBUCH_FASSUNG}),
            "positionsbuch_defekt: 'positionen' fehlt",
            id="250-ohne-positionen",
        ),
        pytest.param(
            json.dumps({"fassung": POSITIONSBUCH_FASSUNG, "positionen": {"a": 1}}),
            "positionsbuch_defekt: 'positionen' fehlt",
            id="250-positionen-kein-liste",
        ),
    ],
)
def test_ein_buch_mit_fremdem_rahmen_sperrt_die_eroeffnung(
    tmp_path: Path, inhalt: str, erwartet: str
) -> None:
    """Fassung 2 ist kein leeres Buch, und ein Objekt ohne ``positionen`` auch nicht.

    Die Folge steht in :func:`_defekt_ergibt_halt`. Dazu die Platte: der fremde Text
    bleibt **Zeichen fuer Zeichen** stehen. Ein Buch der naechsten Fassung, das dieser
    Stand stillschweigend mit seiner eigenen Fassung ueberschreibt, waere derselbe
    Datenverlust wie ein Buch, das nach einem Neustart leer ist.
    """
    pfad = _buch_schreiben(tmp_path, inhalt)

    with pytest.raises(PositionsbuchDefekt) as fehler:
        Positionsbuch(pfad).laden()
    assert str(fehler.value).startswith(erwartet), str(fehler.value)

    _defekt_ergibt_halt(tmp_path, erwartet)

    assert pfad.read_text(encoding="utf-8") == inhalt, "der fremde Rahmen wurde ersetzt"
    assert not list(tmp_path.glob("*.neu")), "eine Nebendatei blieb liegen"


# ---------------------------------------------------------------------------
# Zweige 177->178, 188->189, 192->193, 194->195: der einzelne Satz
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("positionen", "erwartet"),
    [
        pytest.param(
            [_satz(), "EURUSD 0.01"],
            "positionsbuch_defekt: Eintrag 1 kein Objekt",
            id="177-eintrag-kein-objekt",
        ),
        pytest.param(
            [_ohne("ticket")],
            "positionsbuch_defekt: Eintrag 0 unvollstaendig (",
            id="188-ticket-fehlt",
        ),
        pytest.param(
            [_satz(menge="viel")],
            "positionsbuch_defekt: Eintrag 0 unvollstaendig (",
            id="188-menge-keine-zahl",
        ),
        pytest.param(
            [_satz(eroeffnet_am="gestern")],
            "positionsbuch_defekt: Eintrag 0 unvollstaendig (",
            id="188-zeit-kein-datum",
        ),
        pytest.param(
            [_satz(eroeffnet_am=20260809)],
            "positionsbuch_defekt: Eintrag 0 unvollstaendig (",
            id="188-zeit-keine-zeichenkette",
        ),
        pytest.param(
            [_satz(), _satz(kennung="open-XAUUSD-2", ticket=4711)],
            "positionsbuch_defekt: Eintrag 1 ohne Text",
            id="192-ticket-ist-zahl",
        ),
        pytest.param(
            [_satz(symbol="")],
            "positionsbuch_defekt: Eintrag 0 ohne Text",
            id="192-symbol-leer",
        ),
        pytest.param(
            [_satz(richtung="long")],
            "positionsbuch_defekt: Eintrag 0 Richtung 'long'",
            id="194-richtung-unbekannt",
        ),
    ],
)
def test_ein_defekter_buchsatz_sperrt_die_eroeffnung(
    tmp_path: Path, positionen: list[Any], erwartet: str
) -> None:
    """Jeder Defekt nennt SEINEN Eintrag und seinen Grund, und dann steht der Halt.

    Der Index ist kein Zierrat: er ist die einzige Angabe, mit der ein Mensch die
    Zeile findet, die er von Hand richten muss. Ein ``richtung`` ausserhalb von
    ``kauf``/``verkauf`` ist besonders heikel -- ohne diesen Zweig ergaebe
    ``Buchposition.side`` fuer jedes fremde Wort stillschweigend ``SELL``, und die
    glattstellende Order liefe in die falsche Richtung.
    """
    pfad = _buch_schreiben(tmp_path, _buchtext(*positionen))

    with pytest.raises(PositionsbuchDefekt) as fehler:
        Positionsbuch(pfad).laden()
    assert str(fehler.value).startswith(erwartet), str(fehler.value)

    _defekt_ergibt_halt(tmp_path, erwartet)

    assert json.loads(pfad.read_text(encoding="utf-8"))["positionen"] == positionen
    assert not list(tmp_path.glob("*.neu"))


def test_der_defekte_satz_steht_im_journal_des_betriebs(tmp_path: Path) -> None:
    """Die zweite Folge (D7): ``tools/live_betrieb.py`` schreibt den Befund fort.

    Ein Buch, das stillschweigend schrumpft, ist so wenig nachvollziehbar wie eines,
    das ewig waechst -- und ein Buch, das stillschweigend unlesbar ist, erst recht.
    """
    from tools.live_betrieb import Journal, _startabgleich_journalisieren

    _buch_schreiben(tmp_path, _buchtext(_satz(richtung="long")))
    venue = _defekt_ergibt_halt(
        tmp_path, "positionsbuch_defekt: Eintrag 0 Richtung 'long'"
    )
    journal = Journal(tmp_path / "journale" / "j.jsonl", lauf="zweige", version="t")

    _startabgleich_journalisieren(venue, journal)

    saetze = [
        json.loads(z)
        for z in journal.pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    assert [s["art"] for s in saetze] == ["startabgleich"]
    assert saetze[0]["defekt"] == "positionsbuch_defekt: Eintrag 0 Richtung 'long'"
    assert saetze[0]["geister_buch"] == []


def test_ein_defektes_buch_sperrt_die_eroeffnung_und_laesst_die_schliessung(
    tmp_path: Path,
) -> None:
    """Fail-closed in eine Richtung: der Halt sperrt Eroeffnungen, nicht den Ausstieg.

    Waere es andersherum, haette ein unlesbares Buch das Haus mit einer offenen
    Position eingeschlossen. Der Plattenfehler beim Austragen nimmt dem Aufrufer sein
    ``OrderResult`` nicht -- er haengt einen zweiten Halt-Grund an.
    """
    _buch_schreiben(tmp_path, "{kein json")
    venue = _venue(tmp_path, positionen=(_brokerposition(),))
    venue.adopt_book()

    assert venue.is_halted() is True
    assert _abgewiesene_eroeffnung(venue) == "global_halt"

    ergebnis = venue.submit_order(
        OrderRequest(
            "close-EURUSD-1",
            "EURUSD",
            OrderSide.SELL,
            OrderType.MARKET,
            Decimal("0.02"),
            Decimal("0"),
            reduce_only=True,
            position_ticket="B-1",
        )
    )

    assert ergebnis.accepted is True, "der Halt sperrte auch die Schliessung"
    assert "positionsbuch_nicht_gesichert:PositionsbuchDefekt" in venue.halt_gruende


# ---------------------------------------------------------------------------
# Zweig 282->283: eine unbekannte Kennung ruehrt die Platte nicht an
# ---------------------------------------------------------------------------
def test_austragen_einer_unbekannten_kennung_schreibt_nicht(tmp_path: Path) -> None:
    """``austragen`` einer Kennung, die nicht im Buch steht, ist ein Nichts-Tun.

    Am Rueckgabewert allein ist das nicht zu erkennen: ohne den Zweig kaeme ebenfalls
    ``None`` zurueck -- nur haette das Buch dabei eine volle Neuschrift erlebt, samt
    Nebendatei und ``os.replace``, fuer nichts. Gemessen wird darum die Platte: die
    handgesetzte Formatierung (Einzug 4, Schlusszeile) ueberlebt genau dann, wenn
    nicht geschrieben wurde -- ``_schreiben`` setzt Einzug 2 und keine Schlusszeile.
    """
    inhalt = (
        json.dumps(
            {
                "fassung": POSITIONSBUCH_FASSUNG,
                "positionen": [
                    _satz(),
                    _satz(kennung="open-XAUUSD-2", symbol="XAUUSD"),
                ],
            },
            indent=4,
        )
        + "\n"
    )
    pfad = _buch_schreiben(tmp_path, inhalt)
    buch = Positionsbuch(pfad)

    assert buch.austragen("open-GBPUSD-9") is None
    assert pfad.read_text(encoding="utf-8") == inhalt, "das Buch wurde neu geschrieben"
    assert [p.kennung for p in buch.laden()] == ["open-EURUSD-1", "open-XAUUSD-2"]
    assert not list(tmp_path.glob("*.neu"))

    # Die Gegenprobe: eine bekannte Kennung wird ausgetragen -- und dann wird auch
    # geschrieben, atomar, ohne dass die Nebendatei liegen bleibt.
    weg = buch.austragen("open-EURUSD-1")
    assert weg is not None and weg.symbol == "EURUSD"
    assert pfad.read_text(encoding="utf-8") != inhalt
    assert [p.kennung for p in buch.laden()] == ["open-XAUUSD-2"]
    assert not list(tmp_path.glob("*.neu"))


# ---------------------------------------------------------------------------
# Zeile 162: die Richtung im Text bestimmt die Seite der glattstellenden Order
# ---------------------------------------------------------------------------
def test_die_richtung_im_buch_bestimmt_die_seite(tmp_path: Path) -> None:
    """``kauf`` -> BUY, ``verkauf`` -> SELL -- ueber die Platte hinweg.

    Die Seite ist die Angabe, mit der ein Geist von Hand glattgestellt wird; sie
    ueberlebt als Wort im Text und wird erst beim Lesen wieder zur Seite. Ein
    vertauschter Vergleich macht aus jedem Ausstieg einen Einstieg.
    """
    pfad = tmp_path / POSITIONSBUCH_DATEI
    buch = Positionsbuch(pfad)
    buch.eintragen(_buchposition("open-EURUSD-1", "EURUSD", "kauf"))
    buch.eintragen(_buchposition("open-XAUUSD-2", "XAUUSD", "verkauf"))

    gelesen = {p.kennung: p for p in Positionsbuch(pfad).laden()}
    assert gelesen["open-EURUSD-1"].side is OrderSide.BUY
    assert gelesen["open-XAUUSD-2"].side is OrderSide.SELL
    roh = json.loads(pfad.read_text(encoding="utf-8"))["positionen"]
    assert [p["richtung"] for p in roh] == ["kauf", "verkauf"]

    # Die Folge (D7): der Geist wird ausgetragen und mit seiner Seite benannt.
    geister = Positionsbuch(pfad).abgleichen(offen_beim_broker=("EURUSD",))
    assert [(g.kennung, g.side) for g in geister] == [("open-XAUUSD-2", OrderSide.SELL)]
    assert [p.kennung for p in Positionsbuch(pfad).laden()] == ["open-EURUSD-1"]


# ---------------------------------------------------------------------------
# Zeile 226: das Buch nennt seinen Ort -- ausserhalb des Arbeitsbaums (A18)
# ---------------------------------------------------------------------------
def test_das_buch_nennt_seinen_ort_im_zustandsordner(tmp_path: Path) -> None:
    """``pfad`` ist die Angabe, mit der ``tools/zustand.py`` das Buch findet.

    ``None`` heisst: dieses Buch ueberlebt keinen Neustart -- der Betrieb weist es ab
    (``zustand_abweisen``). Beide Antworten muessen unterscheidbar sein, sonst
    entscheidet ``dauerhaft`` ins Blaue.
    """
    venue = _venue(tmp_path)

    assert venue.positionsbuch.pfad == tmp_path / POSITIONSBUCH_DATEI
    assert venue.positionsbuch.dauerhaft is True
    assert venue.zustand_dauerhaft is True
    assert FluechtigesPositionsbuch().pfad is None
    assert FluechtigesPositionsbuch().dauerhaft is False


# ---------------------------------------------------------------------------
# Gegenlese T6 (S2): fuenf Stellen waren beruehrt, aber nicht geprueft.
# ---------------------------------------------------------------------------
def test_eine_kennung_die_kein_text_ist_ist_ein_defekt(tmp_path: Path) -> None:
    """Zeile 192 prueft Kennung, Ticket UND Symbol auf Text. Ohne die Kennung in der
    Pruefmenge liesse sich ein Buchsatz mit ``"kennung": 4711`` lesen; ``austragen``
    vergleicht dann Zahl gegen Text und findet ihn nie -- die Position bliebe fuer immer
    im Buch stehen. Gegenlese T6 (S2): kein Fall setzte die Kennung auf eine Zahl."""
    for falsch in (4711, ""):
        pfad = _buch_schreiben(tmp_path, _buchtext(_satz(kennung=falsch)))
        with pytest.raises(PositionsbuchDefekt) as fehler:
            Positionsbuch(pfad).laden()
        assert str(fehler.value).startswith("positionsbuch_defekt: Eintrag 0 ohne Text")


def test_der_index_nennt_den_defekten_satz_und_nicht_den_ersten(tmp_path: Path) -> None:
    """Zeile 190: der Index ist die einzige Angabe, mit der ein Mensch die Zeile findet.
    Gegenlese T6 (S2): alle vier Faelle legten den Defekt auf Index 0, ein
    festgeschriebener Index waere darum nicht aufgefallen."""
    heil = [_satz(kennung=f"open-EURUSD-{i}", ticket=str(4700 + i)) for i in range(3)]
    pfad = _buch_schreiben(
        tmp_path, _buchtext(*heil, _ohne("menge", kennung="open-X-3"))
    )

    with pytest.raises(PositionsbuchDefekt) as fehler:
        Positionsbuch(pfad).laden()
    assert str(fehler.value).startswith(
        "positionsbuch_defekt: Eintrag 3 unvollstaendig"
    )


def test_der_grund_des_unlesbaren_buches_traegt_die_ursache(tmp_path: Path) -> None:
    """Zeile 240: ``positionsbuch_unlesbar`` ohne die Systemmeldung ist fuer den, der den
    Halt aufloesen soll, wertlos -- er sieht nicht, ob die Datei gesperrt, ein Ordner
    oder rechtlos ist. Gegenlese T6 (S2): nur das Praefix war zugesichert."""
    pfad = tmp_path / POSITIONSBUCH_DATEI
    pfad.mkdir()  # ein Ordner an der Stelle der Datei: OSError beim Lesen

    with pytest.raises(PositionsbuchDefekt) as fehler:
        Positionsbuch(pfad).laden()
    text = str(fehler.value)
    assert text.startswith("positionsbuch_unlesbar: ")
    assert text.rstrip() != "positionsbuch_unlesbar:", "die Ursache fehlt"
    assert POSITIONSBUCH_DATEI in text, text


def test_dieselbe_kennung_wird_nicht_doppelt_gefuehrt(tmp_path: Path) -> None:
    """Zeile 275: ``eintragen`` entdoppelt ueber die Kennung. Ohne das stuenden nach
    einem Wiederanlauf zwei Saetze derselben Order im Buch, und der Deckel
    ``risk_concurrent_position_cap`` zaehlte sie doppelt. Gegenlese T6 (S2)."""
    buch = Positionsbuch(tmp_path / POSITIONSBUCH_DATEI)
    buch.eintragen(_buchposition("open-EURUSD-1", "EURUSD", "kauf"))
    buch.eintragen(_buchposition("open-EURUSD-1", "EURUSD", "verkauf"))

    gefuehrt = buch.laden()
    assert [p.kennung for p in gefuehrt] == ["open-EURUSD-1"]
    assert gefuehrt[0].richtung == "verkauf", "der zweite Eintrag ersetzt den ersten"


def test_austragen_symbol_raeumt_genau_das_genannte_symbol(tmp_path: Path) -> None:
    """Zeile 290: umgekehrt gaebe die Methode die falschen Positionen als ausgetragen
    zurueck und schriebe die glattgestellte ins Buch zurueck. Gegenlese T6 (S2): die
    Zeile war gedeckt und trug keine Zusicherung."""
    buch = Positionsbuch(tmp_path / POSITIONSBUCH_DATEI)
    buch.eintragen(_buchposition("open-EURUSD-1", "EURUSD", "kauf"))
    buch.eintragen(_buchposition("open-XAUUSD-2", "XAUUSD", "verkauf"))
    buch.eintragen(_buchposition("open-EURUSD-3", "EURUSD", "verkauf"))

    weg = buch.austragen_symbol("EURUSD")

    assert sorted(p.kennung for p in weg) == ["open-EURUSD-1", "open-EURUSD-3"]
    assert [p.kennung for p in buch.laden()] == ["open-XAUUSD-2"]


def test_die_eroeffnungszeit_ueberlebt_den_rundlauf_auf_die_sekunde(
    tmp_path: Path,
) -> None:
    """Zeile 171 schreibt mit ``timespec="seconds"``. Mit ``hours`` gingen Minute und
    Sekunde verloren, und ``fromisoformat`` laese den gekuerzten Text anstandslos
    zurueck -- die Haltedauer rechnete dann bis zu einer Stunde daneben (S3)."""
    buch = Positionsbuch(tmp_path / POSITIONSBUCH_DATEI)
    position = _buchposition("open-EURUSD-1", "EURUSD", "kauf")
    genau = position.eroeffnet_am.replace(minute=37, second=19, microsecond=0)
    buch.eintragen(dataclasses.replace(position, eroeffnet_am=genau))

    assert buch.laden()[0].eroeffnet_am == genau
