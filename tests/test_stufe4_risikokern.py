"""Stufe 4 — der Risikokern, fail-closed. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Wörtlich, Stufe 4::

    Sicherheitsriegel in eine eigene Zustandstabelle statt in ein Protokoll. Jede
    fehlende Pflichtkennzahl blockiert, statt uebersprungen zu werden. Portfoliozustand
    serverseitig aus den eigenen Bestaenden ableiten, nie aus der Anfrage. Reduzierende
    Auftraege von allen Sperren ausnehmen. Genau eine Groessenberechnung und ein
    Stopbudget behalten.

    Abnahme: zwei aufeinanderfolgende Eroeffnungsauftraege werden beide abgelehnt;
    leere Kontodaten erzeugen eine Ablehnung mit Grund; bei erzwungenem Halt scheitert
    die Eroeffnung und der Ausstieg laeuft trotzdem. Je Tor ein roter und ein gruener
    Eichfall.

WAS DIESE DATEI IST -- UND WAS NICHT
------------------------------------
Sie prueft **nicht** noch einmal, was ``test_mt5_venue.py`` und
``test_orderpfad_verdrahtung.py`` bereits pruefen. Sie haelt genau die fuenf Forderungen
und die drei Abnahmefaelle oben fest, und zwar so, dass jede von ihnen einen roten
Gegenfall hat: ein Tor, das nur gruen gefahren wird, ist nicht nachgewiesen, sondern
behauptet.

Zwei der Faelle sind aus einer echten Luecke entstanden, die die Messung dieser Stufe
gefunden hat (``archiv/AUFTRAG/stufen/04-risikokern/bericht.md``):

* Eine Gegenposition **unter** dem Mindestvolumen liess sich nicht schliessen --
  ``_validate_volume`` stand vor der Reduce-Weiche. Eine Sperre auf dem Risikoabbau,
  also ein Verstoss gegen V5.
* Ein fehlender Kontoschnappschuss endete in einem ``AttributeError`` statt in einer
  Ablehnung mit Grund -- gegen die Abnahme dieser Stufe und gegen V3.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.venue import mt5 as mt5_modul
from mt5_trading_ai.venue.mt5 import konto_maengel
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    OrderRejectedError,
    OrderSide,
    VenueUnavailableError,
)

from test_mt5_venue import _mt5_position, _order, _venue

ROOT = Path(__file__).resolve().parents[1]

#: Eine Gegenposition, die groesser ist als jedes Volumen, das hier abgebaut wird.
_GROSZE_LONG = (
    _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10"), ticket="t-gross"),
)

#: Eine Gegenposition UNTER dem Mindestvolumen des Pruefstands (0,01). Erreichbar ueber
#: ``adopt_book`` (der Broker meldet, was er hat), ueber eine Teilschliessung von aussen
#: und ueber jede spaetere Aenderung der Kontraktspezifikation.
_WINZIGE_LONG = (
    _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.005"), ticket="t-winzig"),
)


def _abbau(**overrides: Any):
    """Ein reduzierender Auftrag. Ohne Stop -- ein Abbau braucht keinen."""
    base: dict[str, Any] = {
        "side": OrderSide.SELL,
        "volume": Decimal("0.01"),
        "reduce_only": True,
        "position_ticket": "t-gross",  # D2: Ticket der Standard-Gegenposition
        "stop_loss": Decimal("0"),
    }
    base.update(overrides)
    return _order(**base)


# =====================================================================
# A4 / V5 — "Reduzierende Auftraege werden von keiner Sperre blockiert."
# =====================================================================
def test_abbau_einer_position_unter_dem_mindestvolumen_geht_durch() -> None:
    """DER rote Eichfall der Stufe: er war vor dieser Stufe rot.

    Gegenposition 0,005 Lot, Mindestvolumen 0,01. Der volle Abbau wurde mit
    ``volume_below_min`` abgewiesen -- die Position liess sich nicht schliessen. Eine
    Sperre auf dem Risikoabbau ist genau das, was V5 verbietet.

    Wird ``_validate_volume`` wieder vor die Reduce-Weiche gezogen, ist dieser Fall
    sofort wieder rot.
    """
    venue, terminal = _venue(is_demo=True, positions=_WINZIGE_LONG)
    ergebnis = venue.submit_order(
        _abbau(
            position_ticket="t-winzig",
            client_order_id="v5-winzig",
            volume=Decimal("0.005"),
        )
    )
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


def test_abbau_geht_auch_bei_gelatchtem_global_halt_durch() -> None:
    """Der gruene Gegenfall: der Halt sperrt die Eroeffnung, nicht den Ausstieg."""
    venue, terminal = _venue(is_demo=True, positions=_GROSZE_LONG)
    venue._halted = True
    venue._halt_reason = "eichfall"
    ergebnis = venue.submit_order(_abbau(client_order_id="v5-halt"))
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


def test_abbau_ohne_volumen_wird_abgelehnt() -> None:
    """Die eine Bedingung, die auf dem Abbau bleibt -- und sie ist keine Sperre.

    „Baue null ab" ist kein Abbau, sondern ein leerer Auftrag. Das ist eine Definition,
    keine Risikoentscheidung, und sie traegt einen eigenen Grund.
    """
    venue, terminal = _venue(is_demo=True, positions=_GROSZE_LONG)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_abbau(client_order_id="v5-null", volume=Decimal("0")))
    assert ex.value.reason == "volume_not_positive"
    assert terminal.order_send_calls == 0


def test_reduce_flag_ohne_gegenposition_ist_eine_eroeffnung_und_geht_durch_alle_tore() -> (
    None
):
    """Der rote Gegenfall zur Ausnahme selbst.

    Ohne die Pruefung ``_reduces_position`` waere ``reduce_only=True`` ein Freifahrt-
    schein an allen Toren vorbei. Ein Flag ohne offene Gegenposition ist eine
    Eroeffnung und muss vollstaendig geprueft werden -- hier scheitert sie am fehlenden
    Stop, den ein Abbau nicht braucht.
    """
    venue, terminal = _venue(is_demo=True, positions=())
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_abbau(client_order_id="v5-leer"))
    assert ex.value.reason == "missing_stop_loss"
    assert terminal.order_send_calls == 0


def test_abbau_ueber_die_gegenposition_hinaus_ist_eine_eroeffnung() -> None:
    """Ein Abbau, der die Position reisst, dreht sie -- und Drehen ist Eroeffnen."""
    venue, terminal = _venue(is_demo=True, positions=_WINZIGE_LONG)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(
            _abbau(
                position_ticket="t-winzig",
                client_order_id="v5-flip",
                volume=Decimal("0.01"),
            )
        )
    assert ex.value.reason == "missing_stop_loss"
    assert terminal.order_send_calls == 0


# =====================================================================
# A2 / Abnahme — "leere Kontodaten erzeugen eine Ablehnung mit Grund"
# =====================================================================
def test_fehlender_kontoschnappschuss_wird_mit_grund_abgelehnt() -> None:
    """Vor dieser Stufe: ``AttributeError`` mitten im Freigabe-Tor.

    Ein ``AttributeError`` nennt den Ort, nicht die Ursache, traegt keinen ``reason``,
    an dem der Betrieb ihn zaehlen koennte, und sieht im Protokoll aus wie ein
    Programmfehler statt wie eine Sperre, die getan hat, was sie soll.
    """
    venue, terminal = _venue(is_demo=True)
    terminal.account = lambda: None  # type: ignore[method-assign]
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="a2-kein-konto"))
    assert ex.value.reason == "account_unevaluable"
    assert terminal.order_send_calls == 0


@pytest.mark.parametrize("feld", ["account_id", "currency", "is_demo", "ts"])
def test_jedes_fehlende_pflichtfeld_des_kontos_sperrt(feld: str) -> None:
    """Ueber ALLE Pflichtfelder gemessen, nicht am Vertreter (Belegregel des Auftrags).

    ``ts`` ist der Fall, der vor dieser Stufe in einem ``AttributeError`` endete: der
    Kontostempel geht als ``now`` in die Risikoschicht, die daraus ``now.date()``
    bildet.
    """
    venue, terminal = _venue(is_demo=True)
    echt = terminal.account()
    terminal.account = lambda: replace(echt, **{feld: None})  # type: ignore[method-assign,arg-type]
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id=f"a2-{feld}"))
    assert ex.value.reason == "account_unevaluable"
    assert feld in str(ex.value)
    assert terminal.order_send_calls == 0


@pytest.mark.parametrize("feld", ["balance", "equity", "margin_used", "margin_free"])
def test_jede_nicht_endliche_geldzahl_des_kontos_sperrt(feld: str) -> None:
    """``NaN`` ueberlebt jeden Vergleich klaglos -- und faerbt ihn in die milde Richtung.

    ``NaN > limit`` ist ``False``: der Kill-Switch schweigt gerade dann, wenn die Zahl
    unbrauchbar ist. Darum ist „nicht endlich" hier derselbe Befund wie „fehlt".
    """
    venue, terminal = _venue(is_demo=True)
    echt = terminal.account()
    terminal.account = lambda: replace(echt, **{feld: Decimal("NaN")})  # type: ignore[method-assign,arg-type]
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id=f"a2-nan-{feld}"))
    assert ex.value.reason == "account_unevaluable"
    assert terminal.order_send_calls == 0


def test_vollstaendiges_konto_geht_durch() -> None:
    """Der gruene Gegenfall. Ohne ihn wuerde eine Sperre, die IMMER ablehnt, bestehen."""
    venue, terminal = _venue(is_demo=True)
    ergebnis = venue.submit_order(_order(client_order_id="a2-gruen"))
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


def test_lesende_kontoabfrage_wirft_venue_unavailable_statt_attributeerror() -> None:
    """Dieselbe Regel, der Lage angemessener Ausgang.

    An einer lesenden Abfrage gibt es keine Order, die abgelehnt werden koennte. Ein
    unvollstaendiger Schnappschuss heisst dort, dass der Handelsplatz keine Auskunft
    gibt -- und genau das sagt ``VenueUnavailableError``.
    """
    venue, terminal = _venue(is_demo=True)
    terminal.account = lambda: None  # type: ignore[method-assign]
    with pytest.raises(VenueUnavailableError):
        venue.get_account()


def test_konto_maengel_meldet_vollstaendigkeit_als_none() -> None:
    """Die Regel selbst, ohne Venue drumherum: vollstaendig heisst ``None``."""
    venue, terminal = _venue(is_demo=True)
    assert konto_maengel(terminal.account()) is None


# =====================================================================
# Abnahme B1 — "zwei aufeinanderfolgende Eroeffnungsauftraege, beide abgelehnt"
# =====================================================================
def test_zwei_aufeinanderfolgende_eroeffnungen_werden_beide_abgelehnt() -> None:
    """Eine Sperre, die beim zweiten Versuch nicht mehr greift, ist keine Sperre.

    Das ist der Kern des Latch-Gedankens: der Halt loest sich nicht dadurch, dass man
    es noch einmal versucht. Geprueft wird zusaetzlich, dass **kein einziger**
    Sendeversuch beim Terminal ankam -- eine Ablehnung, die trotzdem sendet, waere die
    schlimmere Variante.
    """
    venue, terminal = _venue(is_demo=True)
    venue._halted = True
    venue._halt_reason = "eichfall_latch"

    gruende = []
    for nr in (1, 2):
        with pytest.raises(OrderRejectedError) as ex:
            venue.submit_order(_order(client_order_id=f"b1-{nr}"))
        gruende.append(ex.value.reason)

    assert gruende == ["global_halt", "global_halt"]
    assert terminal.order_send_calls == 0


def test_ohne_halt_geht_die_erste_eroeffnung_durch() -> None:
    """Der gruene Gegenfall: der Latch ist ein Latch, keine Dauerablehnung.

    Ohne ihn bestuende der rote Fall oben auch an einem Venue, das ueberhaupt nichts
    mehr durchlaesst -- dann belegte er nur, dass etwas kaputt ist.
    """
    venue, terminal = _venue(is_demo=True)
    ergebnis = venue.submit_order(_order(client_order_id="b1-gruen"))
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


def test_die_zweite_eroeffnung_faellt_auch_ohne_halt_an_der_drossel() -> None:
    """Gemessen, nicht erwartet: B1 haelt aus ZWEI unabhaengigen Gruenden.

    Die erste Fassung dieses Falls unterstellte, ohne Halt gingen zwei Eroeffnungen
    hintereinander durch. Sie gingen nicht -- die Drossel (``gates/evaluation.py``)
    weist die zweite mit ``throttle_cooldown_active`` ab. Das ist richtiges Verhalten
    und gehoert festgehalten, statt die Erwartung stillschweigend anzupassen:

    Die Abnahme verlangt, dass zwei aufeinanderfolgende Eroeffnungsauftraege **beide**
    abgelehnt werden. Am gelatchten Halt tun sie das, weil der Halt latcht. Ohne Halt
    tun sie es, weil die Mindestpause zwischen zwei Eroeffnungen nicht eingehalten ist.
    Zwei voneinander unabhaengige Linien -- die zweite faellt nicht mit dem Latch.
    """
    venue, terminal = _venue(is_demo=True)
    erste = venue.submit_order(_order(client_order_id="b1-drossel-1"))
    assert erste.accepted is True

    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="b1-drossel-2"))
    assert ex.value.reason == "throttle_cooldown_active"
    assert terminal.order_send_calls == 1, "Die zweite ging nicht an das Terminal."


# =====================================================================
# Abnahme B3 — "bei erzwungenem Halt scheitert die Eroeffnung, der Ausstieg laeuft"
# =====================================================================
def test_bei_halt_scheitert_die_eroeffnung_und_der_ausstieg_laeuft_trotzdem() -> None:
    """Beide Haelften in EINEM Fall -- weil erst zusammen sie die Aussage tragen.

    Getrennt gefahren belegen sie zwei Dinge, die auch beide von einem kaputten Venue
    kaemen (alles ablehnen; alles durchlassen). Nur am selben Venue, im selben Halt,
    hintereinander, zeigt sich der Unterschied, auf den es ankommt.
    """
    venue, terminal = _venue(is_demo=True, positions=_GROSZE_LONG)
    venue._halted = True
    venue._halt_reason = "eichfall_b3"

    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="b3-auf"))
    assert ex.value.reason == "global_halt"
    assert terminal.order_send_calls == 0

    ergebnis = venue.submit_order(_abbau(client_order_id="b3-zu"))
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1
    assert venue.is_halted() is True, "Der Ausstieg hebt den Halt nicht auf."


# =====================================================================
# A5 — "Genau eine Groessenberechnung und ein Stopbudget behalten."
# =====================================================================
def _definitionen(pfad: Path, name: str) -> int:
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    return sum(
        1
        for k in ast.walk(baum)
        if isinstance(k, ast.FunctionDef | ast.AsyncFunctionDef) and k.name == name
    )


@pytest.mark.parametrize(
    ("name", "datei"),
    [("size_position", "risk/sizing.py"), ("stop_budget", "risk/stop_budget.py")],
)
def test_es_gibt_genau_eine_definition_je_rechnung(name: str, datei: str) -> None:
    """Am Syntaxbaum gezaehlt, nicht am Wort.

    Die Lehre aus F-005 dieses Auftrags: eine Suche nach der Zeichenkette findet den
    Namen auch im Docstring und besteht dann eine Mutation, die die Sache selbst
    entfernt hat.
    """
    paket = ROOT / "mt5_trading_ai"
    gefunden = {
        p.relative_to(paket).as_posix(): _definitionen(p, name)
        for p in paket.rglob("*.py")
        if "__pycache__" not in p.parts and _definitionen(p, name)
    }
    assert gefunden == {datei: 1}, (
        f"'{name}' ist genau einmal definiert -- gefunden: {gefunden}. "
        "Zwei Rechnungen fuer dieselbe Groesse laufen auseinander, und die "
        "mildere bleibt uebrig."
    )


@pytest.mark.parametrize("name", ["size_position", "stop_budget"])
def test_jede_rechnung_hat_genau_eine_aufrufstelle_im_paket(name: str) -> None:
    """Eine Definition genuegt nicht -- zwei Aufrufer mit eigenen Vorgaben auch nicht.

    Gezaehlt werden ``ast.Call``-Knoten, keine Vorkommen des Wortes: die Docstrings
    dieses Pakets nennen beide Namen mehrfach.
    """
    paket = ROOT / "mt5_trading_ai"
    aufrufe: dict[str, int] = {}
    for p in paket.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        baum = ast.parse(p.read_text(encoding="utf-8"))
        n = sum(
            1
            for k in ast.walk(baum)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == name
        )
        if n:
            aufrufe[p.relative_to(paket).as_posix()] = n
    assert sum(aufrufe.values()) == 1, (
        f"'{name}' wird {sum(aufrufe.values())}-mal aufgerufen: {aufrufe}. "
        "Der Auftrag verlangt genau eine Groessenberechnung und ein Stopbudget."
    )


# =====================================================================
# A2-Sonderfall — der fehlende Hebelwunsch ist KEIN fehlender Messwert
# =====================================================================
def test_der_rueckfall_ohne_hebelwunsch_ist_in_keiner_klasse_der_mildere() -> None:
    """Ueber ALLE Anlageklassen gemessen, nicht an einer Stichprobe.

    Der fehlende Hebelwunsch ist der eine Fall, in dem der Orderpfad ohne Angabe
    weiterlaeuft. Das ist zulaessig, weil ein Wunsch kein Messwert ist -- aber nur,
    solange der Rueckfall nie die gefaehrlichere Wahl trifft. Genau das prueft dieser
    Fall, und er wird rot, sobald irgendeine Klasse ohne Wunsch mehr Hebel bekaeme als
    mit dem hoechstmoeglichen.
    """
    from mt5_trading_ai.risk.leverage import clamp_leverage

    milder = []
    for klasse in AssetClass:
        ohne = clamp_leverage(requested=None, asset_class=klasse.value)
        maximal = clamp_leverage(requested=10**6, asset_class=klasse.value)
        if ohne.no_trade or maximal.no_trade:
            continue
        assert ohne.leverage is not None and maximal.leverage is not None
        if ohne.leverage > maximal.leverage:
            milder.append(klasse.value)
    assert milder == [], (
        f"In diesen Klassen waere der Rueckfall ohne Hebelwunsch der gefaehrlichere: "
        f"{milder}. Dann ist er ein Standardwert fuer einen fehlenden Messwert (V3) "
        "und keine konservative Voreinstellung mehr."
    )


# =====================================================================
# A1 — "Sicherheitsriegel in eine eigene Zustandstabelle statt in ein Protokoll"
# =====================================================================
def test_der_kontoschnappschuss_wird_im_orderpfad_nirgends_ungeprueft_gelesen() -> None:
    """Am Syntaxbaum: ausser in den beiden gepruefenden Methoden kein ``account()``.

    Ohne diesen Fall waere die naechste ungepruefte Lesestelle wieder still moeglich --
    und genau so ist die Luecke entstanden, die diese Stufe gefunden hat.
    """
    quelle = Path(inspect.getsourcefile(mt5_modul) or "")
    baum = ast.parse(quelle.read_text(encoding="utf-8"))

    erlaubt = {"_konto_pflicht", "get_account"}
    verstoesse = []
    for klasse in ast.walk(baum):
        if not isinstance(klasse, ast.ClassDef) or klasse.name != "Mt5Venue":
            continue
        for methode in klasse.body:
            if not isinstance(methode, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if methode.name in erlaubt:
                continue
            for knoten in ast.walk(methode):
                if (
                    isinstance(knoten, ast.Call)
                    and isinstance(knoten.func, ast.Attribute)
                    and knoten.func.attr == "account"
                    and isinstance(knoten.func.value, ast.Attribute)
                    and knoten.func.value.attr == "_terminal"
                ):
                    verstoesse.append(f"{methode.name}:{knoten.lineno}")
    assert verstoesse == [], (
        f"Ungeprueftes ``self._terminal.account()`` in: {verstoesse}. "
        "Jede Lesestelle im Orderpfad geht ueber ``_konto_pflicht``."
    )
