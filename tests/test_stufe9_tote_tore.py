"""Stufe 9 — Tote Tore verdrahten oder löschen. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Woertlich::

    Ohne Zwischenzustand. Fuer jede gelesene Groesse entweder einen Schreiber schaffen
    oder den Leser entfernen. Typpruefungstor vom unbenutzten Code auf den Auftragspfad
    umhaengen. Ein Werkzeug, das Tore ohne Ausloesung im Betrieb meldet.

    Abnahme: fuer jedes verbliebene Tor existiert ein Test, der es ausloest, und eine
    Betriebszaehlung je Ablehnungsgrund.

WAS DIE MESSUNG GEFUNDEN HAT
----------------------------
* **12 oeffentliche Modulfunktionen ohne jeden Aufrufer** in Paket und Werkzeugen --
  nur von Tests gerufen. Darunter ``entscheide_erkundung``, das ich eine Stufe zuvor
  selbst gebaut und nie verdrahtet hatte.
* **11 Ablehnungsgruende ohne Test, der sie ausloest.** Ein Tor ohne solchen Test ist
  eine Behauptung.
* **16 Stellen auf dem Auftragspfad mit ``Any``** -- darunter der Kontoschnappschuss
  aus Stufe 4, also genau die Groesse, deren Vollstaendigkeit dort geprueft wird.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.execution.cost_gate import CostGate, evaluate_cost_gate
from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
from mt5_trading_ai.venue.protocol import (
    OrderRejectedError,
    OrderSide,
    VenueUnavailableError,
)

from test_mt5_venue import _order, _venue

ROOT = Path(__file__).resolve().parents[1]
PAKET = ROOT / "mt5_trading_ai"

#: Die Dateien des Auftragspfads. ``Any`` schaltet die Typpruefung dort ab, wo sie am
#: noetigsten ist -- deshalb wird es hier gezaehlt und nicht nur gemieden.
AUFTRAGSPFAD = (
    "venue/mt5.py",
    "execution/risk_manager.py",
    "execution/runner.py",
    "risk/sizing.py",
    "risk/stop_budget.py",
    "risk/limits.py",
    "costs/model.py",
    "execution/cost_gate.py",
)

#: Funktionen, an denen ``Any`` bleiben darf: die Grenze zum untypisierten
#: MetaTrader5-Modul und zu einem entenartig getippten Einstellungsobjekt. Sie sind
#: **aufgezaehlt**, nicht per Muster erlaubt -- eine neue Stelle faellt auf.
ANY_AN_DER_GRENZE = frozenset(
    {
        "_erfolgscodes",
        "_ohne_fehlercode",
        "_send_gefuellt",
        "_send_angenommen",
        "_fuellart",
        "_d",
        "_utc",
        "_to_symbol",
        "__init__",
    }
)


# =====================================================================
# A1/A2 — kein Zwischenzustand: kein Leser ohne Schreiber
# =====================================================================
def _oeffentliche_funktionen() -> list[tuple[Path, str]]:
    aus = []
    for pfad in sorted(PAKET.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        for knoten in ast.parse(pfad.read_text(encoding="utf-8")).body:
            if isinstance(knoten, ast.FunctionDef) and not knoten.name.startswith("_"):
                aus.append((pfad, knoten.name))
    return aus


def _aufrufe(name: str, dateien: list[Path]) -> int:
    """Wie oft wird ``name`` im Ausfuehrungspfad benutzt -- direkt ODER als Verweis.

    Der direkte Aufruf ``f(...)`` ist der Normalfall. Er reicht aber nicht: eine
    Funktion kann auch als **Wert** in den Pfad kommen, etwa als Eintrag einer
    Verteilertabelle::

        METRIKEN = {"buchtreue": buchtreue, ...}
        return {name: fn(saetze) for name, fn in METRIKEN.items()}

    Hier steht nirgends ``buchtreue(...)``, und trotzdem laeuft sie bei jedem Erheben.
    Der Scan zaehlte anfangs nur ``ast.Call`` und meldete genau diese drei Metriken als
    verwaist (Stufe 10). Ein Tor, das zu einer schlechteren Verdrahtung draengt -- drei
    Funktionen in eine zu giessen, nur damit ein Zaehler steigt -- misst das Falsche.

    **Grenze, ausdruecklich:** ein blosser Verweis belegt nicht, dass die Tabelle
    selbst erreichbar ist. Der Fall bleibt damit etwas milder als der Aufrufzaehler.
    Was er weiterhin faengt, ist der Fall, um den es geht: eine Funktion, die im ganzen
    Paket und in allen Werkzeugen **kein einziges Mal vorkommt** -- siehe
    ``test_rot_eine_nirgends_erwaehnte_funktion_gilt_als_verwaist``.
    """
    n = 0
    for pfad in dateien:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Call):
                f = knoten.func
                if (isinstance(f, ast.Name) and f.id == name) or (
                    isinstance(f, ast.Attribute) and f.attr == name
                ):
                    n += 1
            elif isinstance(knoten, ast.Name) and isinstance(knoten.ctx, ast.Load):
                # Der Verweis: die Funktion wird weitergereicht statt gerufen.
                if knoten.id == name:
                    n += 1
    return n


def test_keine_oeffentliche_funktion_ohne_aufrufer_im_ausfuehrungspfad() -> None:
    """„Ohne Zwischenzustand" -- woertlich der Auftrag.

    Vor dieser Stufe hatten **12** oeffentliche Modulfunktionen keinen einzigen
    Aufrufer in Paket oder Werkzeugen; sie wurden nur von Tests gerufen. Sieben sind
    entfernt, fuenf verdrahtet worden. Dieser Fall haelt fest, dass keine neue
    dazukommt -- die Krankheit, die §0 des Auftrags beim Namen nennt.
    """
    paket = [p for p in PAKET.rglob("*.py") if "__pycache__" not in p.parts]
    werkzeuge = sorted((ROOT / "tools").glob("*.py"))
    verwaist = sorted(
        f"{pfad.relative_to(PAKET).as_posix()}::{name}"
        for pfad, name in _oeffentliche_funktionen()
        if _aufrufe(name, paket) == 0 and _aufrufe(name, werkzeuge) == 0
    )
    assert verwaist == [], (
        f"Ohne Aufrufer im Ausfuehrungspfad: {verwaist}. Entweder einen Schreiber "
        "schaffen oder den Leser entfernen."
    )


def test_rot_eine_nirgends_erwaehnte_funktion_gilt_als_verwaist(tmp_path: Path) -> None:
    """Roter Eichfall fuer den Zaehler, seit er auch Verweise mitzaehlt (Stufe 10).

    Ohne ihn koennte die Lockerung den Fall oben still leerlaufen lassen. Gemessen
    wird beides: die nirgends erwaehnte Funktion bleibt bei 0, die als Tabellenwert
    weitergereichte kommt auf mehr.
    """
    modul = tmp_path / "probe.py"
    modul.write_text(
        "def nie_erwaehnt() -> None: ...\n"
        "def nur_verwiesen() -> None: ...\n"
        "TABELLE = {'x': nur_verwiesen}\n",
        encoding="utf-8",
    )
    assert _aufrufe("nie_erwaehnt", [modul]) == 0
    assert _aufrufe("nur_verwiesen", [modul]) == 1


def test_die_pruefung_findet_ihren_gegenstand() -> None:
    """Laut scheitern: eine Erhebung ohne Gegenstand ist kein Beleg."""
    assert len(_oeffentliche_funktionen()) > 100


# =====================================================================
# A3 — Typpruefungstor auf dem Auftragspfad
# =====================================================================
def test_auf_dem_auftragspfad_steht_any_nur_an_der_untypisierten_grenze() -> None:
    """``Any`` schaltet die Typpruefung ab -- ``object`` zwingt sie durch isinstance.

    Vor dieser Stufe standen 16 ``Any`` auf dem Auftragspfad, darunter der
    Kontoschnappschuss (``konto_maengel``, ``_konto_pflicht``) und der Risikoanteil
    (``size_position``). Das sind Groeszen, deren Vollstaendigkeit genau dort geprueft
    werden soll -- und ``Any`` nimmt dem Pruefer sein Werkzeug aus der Hand.

    Was bleibt, ist die Grenze zum MetaTrader5-Modul: es liefert keine Typinformation,
    und ein ``object`` dort waere eine Behauptung ueber fremden Code. Diese Stellen
    sind einzeln aufgezaehlt.
    """
    verstoesse = []
    for rel in AUFTRAGSPFAD:
        baum = ast.parse((PAKET / rel).read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if knoten.name in ANY_AN_DER_GRENZE:
                continue
            for arg in list(knoten.args.args) + list(knoten.args.kwonlyargs):
                if isinstance(arg.annotation, ast.Name) and arg.annotation.id == "Any":
                    verstoesse.append(f"{rel}::{knoten.name}({arg.arg})")
            if isinstance(knoten.returns, ast.Name) and knoten.returns.id == "Any":
                verstoesse.append(f"{rel}::{knoten.name}() -> Any")
    assert verstoesse == [], (
        f"``Any`` auf dem Auftragspfad ausserhalb der untypisierten Grenze: "
        f"{verstoesse}"
    )


def test_der_kontoschnappschuss_wird_als_object_geprueft_nicht_als_any() -> None:
    """Der Fall, der die eine Stelle festhaelt, um die es geht."""
    from mt5_trading_ai.venue.mt5 import konto_maengel

    quelle = ast.parse((PAKET / "venue" / "mt5.py").read_text(encoding="utf-8"))
    for knoten in ast.walk(quelle):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "konto_maengel":
            annot = knoten.args.args[0].annotation
            assert isinstance(annot, ast.Name) and annot.id == "object"
            break
    else:  # pragma: no cover - laut scheitern
        pytest.fail("konto_maengel nicht gefunden")
    assert konto_maengel(None) is not None


# =====================================================================
# A4 — das Werkzeug, das Tore ohne Ausloesung meldet
# =====================================================================
def test_die_torzaehlung_laeuft_und_verlangt_je_tor_einen_test() -> None:
    """Bestaetigt durch Ausfuehrung. Der Abnahmesatz des Auftrags."""
    lauf = subprocess.run(
        [sys.executable, "tools/torzaehlung.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "jedes Tor hat einen Test" in lauf.stdout


def test_die_torzaehlung_findet_die_positionalen_gruende() -> None:
    """Der rote Eichfall zum Werkzeug selbst.

    Die erste Fassung suchte nur ``reason=``-Schluesselwoerter und lief damit an
    ``cost_unverifiable`` vorbei -- dem mit 2.258 Faellen haeufigsten Grund ueberhaupt,
    weil er als zweites Positionsargument uebergeben wird. Eine Pruefung, die ihren
    Gegenstand nur halb findet, meldet Vollzug.
    """
    from tools.torzaehlung import gruende_im_code

    fest, _ = gruende_im_code()
    assert "cost_unverifiable" in fest
    assert "global_halt" in fest, "Die Schluesselwort-Form muss weiter gefunden werden."


def test_die_torzaehlung_meldet_die_zusammengesetzten_gruende_getrennt() -> None:
    """``reason=f"risk_{...}"`` ist nicht aufzaehlbar -- und das gehoert gesagt."""
    from tools.torzaehlung import gruende_im_code

    _, zusammengesetzt = gruende_im_code()
    assert zusammengesetzt, (
        "Der Stand baut Gruende zur Laufzeit zusammen; sie stillschweigend nicht zu "
        "melden waere die bequeme Auslassung."
    )


def test_die_freistellungsliste_bleibt_kurz_und_begruendet() -> None:
    """Eine Freistellungsliste ist ein Ablagefach, sobald sie waechst."""
    from tools.torzaehlung import OHNE_TESTPFLICHT

    assert len(OHNE_TESTPFLICHT) <= 5, (
        "Die Freistellungsliste ist ein Ablagefach, sobald sie waechst."
    )
    assert all(len(grund) > 60 for grund in OHNE_TESTPFLICHT.values()), (
        "Jede Freistellung nennt die vorgelagerte Klammer, an der sie haengt."
    )


# =====================================================================
# Abnahme — je ein Test, der das Tor tatsaechlich AUSLOEST
# =====================================================================
def test_kein_kurs_loest_no_tick_aus() -> None:
    venue, terminal = _venue(is_demo=True)
    terminal.tick = lambda symbol: None  # type: ignore[method-assign]
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="t-no-tick"))
    assert ex.value.reason in ("no_tick", "no_market_stamp")


def test_ein_volumen_ueber_dem_maximum_loest_volume_above_max_aus() -> None:
    venue, terminal = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="t-max", volume=Decimal("1000")))
    assert ex.value.reason == "volume_above_max"


def test_ein_preis_von_null_loest_risk_price_missing_aus() -> None:
    """Die Risikoschicht rechnet den Stopabstand als Anteil des Preises."""
    from mt5_trading_ai.execution.risk_manager import RiskManager

    venue, _t = _venue(is_demo=True)
    auth = RiskManager(zustand=FluechtigerZustand()).authorize_opening(
        instrument=venue.get_instrument("EURUSD"),
        request=_order(volume=Decimal("0.01")),
        account=venue.get_account(),
        price=Decimal("0"),
        spread_bps=Decimal("1"),
        leverage=5,
        now=venue.get_account().ts,
    )
    assert auth.approved is False
    assert auth.reason == "risk_price_missing"


def test_ein_konto_ohne_auskunft_latcht_account_unavailable() -> None:
    """Der Scheduler laesst die Ausnahme nicht durch -- er latcht den Halt.

    Sonst bliebe der Halt in der Risikokonfiguration ungesetzt, waehrend der Takt
    durchlaeuft.
    """
    from datetime import timedelta

    from mt5_trading_ai.execution.risk_manager import RiskManager
    from mt5_trading_ai.execution.scheduler import SyncScheduler

    import test_paper_runner as R

    venue = R._venue()

    def wirft():
        raise VenueUnavailableError("Konto nicht lesbar")

    venue.get_account = wirft  # type: ignore[method-assign]
    scheduler = SyncScheduler(
        venue,
        max_silence=timedelta(minutes=5),
        started_at=R.TS,
        risk_manager=RiskManager(zustand=FluechtigerZustand()),
    )
    scheduler.tick(R.TS)
    assert venue.is_halted() is True
    assert venue.halt_reason == "account_unavailable"


def test_ein_preis_von_null_loest_invalid_price_aus() -> None:
    venue, _terminal = _venue(is_demo=True)
    instrument = venue.get_instrument("EURUSD")
    preflight = evaluate_leverage_preflight(
        instrument=instrument,
        request=_order(volume=Decimal("0.01")),
        account=venue.get_account(),
        price=Decimal("0"),
        requested_leverage=5,
        margin_to_account_rate=Decimal("1"),
    )
    assert preflight.approved is False
    assert preflight.reason == "invalid_price"


def test_ein_referenzpreis_von_null_loest_price_missing_aus() -> None:
    """Der Runner braucht einen Referenzpreis > 0; sonst ist die Lage nicht bewertbar."""
    import test_paper_runner as R

    venue = R._venue()
    echt = venue.get_quote

    def null_quote(symbol: str):
        return replace(echt(symbol), bid=Decimal("0"), ask=Decimal("0"))

    venue.get_quote = null_quote  # type: ignore[method-assign]
    bericht = R._run(venue=venue)
    assert bericht.reject_reason == "price_missing"


def test_ein_unerreichbarer_handelsplatz_loest_venue_unavailable_aus() -> None:
    """Der Handelsplatz antwortet nicht -- der Runner haelt an, statt zu raten."""
    import test_paper_runner as R

    venue = R._venue()

    def wirft(symbol: str):
        raise VenueUnavailableError("Sitzung weg")

    venue.get_instrument = wirft  # type: ignore[method-assign]
    bericht = R._run(venue=venue)
    assert bericht.reject_reason == "venue_unavailable"


def test_die_beiden_entfernten_waechter_waren_unerreichbar() -> None:
    """Der Beleg fuer zwei Loeschungen -- gerechnet, nicht behauptet.

    ``invalid_notional`` sasz hinter ``order_roundturn_cost``, das Kontraktgroesse,
    Volumen und Kurs einzeln als „endlich und positiv" abweist: jede Eingabe, die ein
    Nominal von 0 ergaebe, endet dort mit ``cost_unverifiable``.

    ``stop_price_nonpositive`` sasz hinter der Budgetklammer: ein Stop unterhalb von
    null braeuchte eine Distanz von 10.000 bp, und ``margin_ceiling_bps`` laesst
    hoechstens 1.666,7 bp zu (Hebel 1).

    Aendert jemand eine der beiden Klammern, wird dieser Fall rot -- und dann gehoeren
    die Waechter zurueck.
    """
    from mt5_trading_ai.risk.stop_budget import margin_ceiling_bps

    assert float(margin_ceiling_bps(1)) < 10_000, (
        "Die Budgetklammer laesst jetzt eine Stopdistanz ueber 100 % zu -- ein Stop "
        "unterhalb von null ist wieder moeglich."
    )

    venue, _t = _venue(is_demo=True)
    instrument = venue.get_instrument("EURUSD")
    for name, kw in (
        (
            "contract_size=0",
            {"instrument": replace(instrument, contract_size=Decimal("0"))},
        ),
        ("volume=0", {"volume": Decimal("0")}),
        ("ask=0", {"bid": Decimal("0"), "ask": Decimal("0")}),
    ):
        basis = dict(
            gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
            instrument=instrument,
            fees=instrument.fees,
            side=OrderSide.BUY,
            volume=Decimal("0.01"),
            bid=Decimal("1.0999"),
            ask=Decimal("1.1001"),
        )
        basis.update(kw)
        entscheidung = evaluate_cost_gate(**basis)  # type: ignore[arg-type]
        assert entscheidung.reason == "cost_unverifiable", (
            f"{name}: erwartet cost_unverifiable, bekommen {entscheidung.reason} -- "
            "der Waechter davor ist nicht mehr strenger."
        )


def test_die_vorgelagerte_klammer_des_margendeckels_haelt() -> None:
    """Ohne gemeldeten Kontohebel gibt der Margendeckel des Runners auf, und eine
    freie Marge, die kein Mindestvolumen traegt, faellt am Hebel-Preflight mit
    ``insufficient_margin``.

    Bis zur Gegenlese T10 hing an dieser Klammer die Freistellung von
    ``margin_below_min_volume``. Sie galt nur fuer Konten OHNE Hebel: meldet das
    Konto einen, rechnet der Deckel VOR dem Preflight und lehnt selbst ab -- seit E15
    mit eigenem Test (``tests/test_orderpfad_zweige_e15.py``), die Freistellung ist
    gestrichen. Dieser Fall bleibt als Nachweis fuer die Konten ohne Hebel.
    """
    import test_paper_runner as R

    venue = R._venue()
    echt = venue.get_account

    def knappe_marge():
        return replace(echt(), margin_free=Decimal("1"))

    venue.get_account = knappe_marge  # type: ignore[method-assign]
    bericht = R._run(venue=venue)
    assert bericht.reject_reason == "insufficient_margin", (
        f"Erwartet war der vorgelagerte Waechter, bekommen: {bericht.reject_reason}"
    )
