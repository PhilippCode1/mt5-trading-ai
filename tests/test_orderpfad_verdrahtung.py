"""Dauertor gegen den Rueckfall: zaehlt die Sperren am echten Order-Pfad (A3.4).

WARUM ES DIESES TOR GIBT
------------------------
Die Risiko- und Bewertungsschicht war dreimal in Folge gebaut, getestet -- und am
Order-Pfad nicht oder nur halb aufgerufen (die 7/75-Hebeldefaults, A0.2, und zuletzt
eine Risikoschicht, die es nur am Live-Konto gab und damit an keinem erreichbaren).
Ein Modul mit gruenen Eigentests belegt nicht, dass es je laeuft. Dieses Tor belegt es,
und wird rot, sobald die Zahl unter die Sollzahl faellt.

DIE ZWEI ZAHLEN
---------------
* ``SOLL_EINTRITTSPUNKTE`` -- wie viele Stellen im Paket eine **eroeffnende** Order
  entstehen lassen. Wird per Quellcode-Suche ermittelt, nicht geschaetzt. Kommt eine
  hinzu, wird das Tor rot, bis jemand sie bewertet und die Zahl bewusst zieht.
* ``SOLLSPERREN`` -- die fuenf Sperren aus A3.2, jede als **Modulfunktion**, damit sie
  zaehlbar ist. 4 von 5 ist rot, nicht „fast fertig".

LAUT SCHEITERN, NIE STILL
-------------------------
Das Tor prueft **zuerst**, dass es seinen Gegenstand ueberhaupt findet: die Datei, die
Klasse, die Methode, die Aufrufstellen. Findet es nichts, ist das ein Fehlschlag --
nicht ein bestandener Test ohne Befund. Genau diese Sorte Test (findet nichts, ist
deshalb gruen) ist der Fehler, den dieses Paket schliesst.

Der Nachweis laeuft auf zwei Ebenen, weil jede fuer sich taeuschbar ist:
1. **dynamisch** -- eine echte Order laeuft durch den echten Pfad, und jede der fuenf
   Sperren wird beim Aufruf gezaehlt. Das belegt, dass sie laufen.
2. **statisch** -- der Quelltext wird gelesen und auf die Wiederkehr des alten Fehlers
   geprueft (Konto-abhaengige Ausstiege vor den Sperren). Das belegt, dass sie auch
   dann laufen, wenn der dynamische Fall sie zufaellig nicht erreicht.
"""

from __future__ import annotations

import ast
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import (  # noqa: E402
    TS,
    FakeMt5Terminal,
    _mt5_position,
    _venue,
)

PKG = ROOT / "mt5_trading_ai"
MT5_QUELLE = PKG / "venue" / "mt5.py"

#: Die fuenf Sollsperren aus A3.2, in der Reihenfolge des Auftrags.
#: (Anzeigename, Modulpfad der Definition, Modulpfad der Benutzung, Funktionsname)
SOLLSPERREN: tuple[tuple[str, str, str, str], ...] = (
    (
        "1 Frische-Latch",
        "mt5_trading_ai.execution.freshness",
        "mt5_trading_ai.venue.mt5",
        "evaluate_account_freshness",
    ),
    (
        "2 Verlustgrenzen",
        "mt5_trading_ai.risk.limits",
        "mt5_trading_ai.execution.risk_manager",
        "evaluate_limits",
    ),
    (
        "3 Stop-Budget",
        "mt5_trading_ai.risk.stop_budget",
        "mt5_trading_ai.execution.risk_manager",
        "stop_budget",
    ),
    (
        "4 Positionsgroesse",
        "mt5_trading_ai.risk.sizing",
        "mt5_trading_ai.execution.risk_manager",
        "size_position",
    ),
    (
        "5 Bewertungstor",
        "mt5_trading_ai.gates.evaluation",
        "mt5_trading_ai.execution.risk_manager",
        "select_one",
    ),
)

SOLL_SPERRENZAHL = 5

#: Eroeffnende Eintrittspunkte, per Quellcode-Suche ermittelt (A3.1).
#: Jede Stelle, an der eine eroeffnende Order ENTSTEHT. ``emergency_flatten`` ist
#: nicht dabei: es erzeugt ausschliesslich reduce-only-Schliessungen und ist gegen
#: den eroeffnenden Zweig doppelt gesperrt (Global-Halt + Stop 0). Belegt von
#: ``test_emergency_flatten_kann_nicht_eroeffnen``.
EINTRITTSPUNKTE: tuple[tuple[str, str, str], ...] = (
    ("mt5_trading_ai/venue/mt5.py", "Mt5Venue", "submit_order"),
    ("mt5_trading_ai/execution/runner.py", None, "run_signal"),  # type: ignore[list-item]
    ("mt5_trading_ai/venue/smoke.py", None, "_write_probe"),  # type: ignore[list-item]
)

SOLL_EINTRITTSPUNKTE = 3


# --------------------------------------------------------------------------- #
# Werkzeug: Quelltext lesen, laut scheitern, wenn der Gegenstand fehlt.        #
# --------------------------------------------------------------------------- #
def _lade_baum(pfad: Path) -> ast.Module:
    if not pfad.is_file():
        pytest.fail(
            f"Dauertor findet seinen Gegenstand nicht: {pfad} existiert nicht. "
            "Ein Tor, das nichts findet und deshalb gruen ist, ist der Fehler selbst."
        )
    return ast.parse(pfad.read_text(encoding="utf-8"))


def _finde_funktion(
    baum: ast.Module, klasse: str | None, name: str, wo: str
) -> ast.FunctionDef:
    kandidaten: list[ast.FunctionDef] = []
    if klasse is None:
        kandidaten = [
            node
            for node in baum.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
    else:
        for node in baum.body:
            if isinstance(node, ast.ClassDef) and node.name == klasse:
                kandidaten = [
                    child
                    for child in node.body
                    if isinstance(child, ast.FunctionDef) and child.name == name
                ]
    if not kandidaten:
        ziel = f"{klasse}.{name}" if klasse else name
        pytest.fail(
            f"Dauertor findet seinen Gegenstand nicht: {ziel} in {wo}. "
            "Wurde er umbenannt oder entfernt, ist die Verdrahtung neu zu belegen."
        )
    return kandidaten[0]


def _aufgerufene_namen(knoten: ast.AST) -> set[str]:
    namen: set[str] = set()
    for kind in ast.walk(knoten):
        if not isinstance(kind, ast.Call):
            continue
        ziel = kind.func
        if isinstance(ziel, ast.Name):
            namen.add(ziel.id)
        elif isinstance(ziel, ast.Attribute):
            namen.add(ziel.attr)
    return namen


def _rufname(knoten: ast.Call) -> str | None:
    ziel = knoten.func
    if isinstance(ziel, ast.Name):
        return ziel.id
    if isinstance(ziel, ast.Attribute):
        return ziel.attr
    return None


def _selbstgestempelte_terminalmethoden(baum: ast.Module) -> set[str]:
    """Welche ``RealMt5Terminal``-Methoden setzen ihr ``ts`` aus der EIGENEN Uhr?

    Nicht als Liste hinterlegt, sondern am Quelltext **gemessen**: ein
    ``ts=``-Argument, dessen Ausdruck ``now`` erwaehnt, stammt aus der Systemuhr des
    eigenen Prozesses. Ein solcher Stempel taugt nicht als Frischequelle -- gegen die
    Systemuhr gehalten ergibt er per Konstruktion das Alter null.

    Gemessen statt hinterlegt, weil eine Liste veraltet, sobald jemand eine weitere
    Methode selbst stempelt. Die Messung findet auch die.
    """
    treffer: set[str] = set()
    for node in baum.body:
        if not (isinstance(node, ast.ClassDef) and node.name == "RealMt5Terminal"):
            continue
        for child in node.body:
            if not isinstance(child, ast.FunctionDef):
                continue
            for kind in ast.walk(child):
                if (
                    isinstance(kind, ast.keyword)
                    and kind.arg == "ts"
                    and "now" in ast.unparse(kind.value)
                ):
                    treffer.add(child.name)
    return treffer


def _terminalherkunft(funktion: ast.FunctionDef) -> dict[str, str]:
    """Welche lokale Variable stammt aus welchem ``self._terminal.<methode>()``?"""
    herkunft: dict[str, str] = {}
    for kind in ast.walk(funktion):
        if not (isinstance(kind, ast.Assign) and isinstance(kind.value, ast.Call)):
            continue
        ziel = kind.value.func
        if not (
            isinstance(ziel, ast.Attribute)
            and isinstance(ziel.value, ast.Attribute)
            and ziel.value.attr == "_terminal"
        ):
            continue
        for name in kind.targets:
            if isinstance(name, ast.Name):
                herkunft[name.id] = ziel.attr
    return herkunft


# --------------------------------------------------------------------------- #
# A3.1 -- die Sollzahl der Eintrittspunkte, gegen den Quelltext geprueft.      #
# --------------------------------------------------------------------------- #
def test_alle_eintrittspunkte_existieren_und_zahl_stimmt() -> None:
    """Die Sollzahl aus A3.1 ist gegen den Quelltext belegt, nicht behauptet."""
    assert len(EINTRITTSPUNKTE) == SOLL_EINTRITTSPUNKTE, (
        f"Sollzahl {SOLL_EINTRITTSPUNKTE}, aufgezaehlt {len(EINTRITTSPUNKTE)}"
    )
    for rel, klasse, name in EINTRITTSPUNKTE:
        baum = _lade_baum(ROOT / rel)
        _finde_funktion(baum, klasse, name, rel)


def test_kein_unbemerkter_neuer_eintrittspunkt() -> None:
    """Jede Stelle, die einen ``OrderRequest`` baut, ist bewertet.

    Die Suche laeuft ueber das ganze Paket. Taucht eine neue Bau-Stelle auf, wird das
    Tor rot -- sie muss dann entweder in ``EINTRITTSPUNKTE`` aufgenommen (und
    verdrahtet) oder als nicht-eroeffnend begruendet werden.
    """
    bekannt = {
        ("mt5_trading_ai/execution/runner.py", "run_signal"),
        ("mt5_trading_ai/venue/smoke.py", "_write_probe"),
        # Nicht eroeffnend: erzeugt nur reduce-only-Schliessungen (Stop 0, Global-Halt
        # steht bereits). Belegt von test_emergency_flatten_kann_nicht_eroeffnen.
        ("mt5_trading_ai/venue/mt5.py", "emergency_flatten"),
    }
    gefunden: set[tuple[str, str]] = set()
    for pfad in sorted(PKG.rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        rel = pfad.relative_to(ROOT).as_posix()
        for node in ast.walk(baum):
            if not isinstance(node, ast.FunctionDef):
                continue
            for kind in ast.walk(node):
                if (
                    isinstance(kind, ast.Call)
                    and isinstance(kind.func, ast.Name)
                    and kind.func.id == "OrderRequest"
                ):
                    gefunden.add((rel, node.name))

    assert gefunden, (
        "Dauertor findet keine einzige OrderRequest-Bau-Stelle im Paket. "
        "Das ist ein Fehlschlag des Tors, kein bestandener Test."
    )
    neu = gefunden - bekannt
    assert not neu, (
        f"Neue Stelle(n), die eine Order bauen, ohne bewertet zu sein: {sorted(neu)}. "
        f"Bekannt sind {len(bekannt)}, gefunden {len(gefunden)}."
    )


# --------------------------------------------------------------------------- #
# A3.4 -- dynamisch: laufen alle fuenf Sperren an einer echten Eroeffnung?     #
# --------------------------------------------------------------------------- #
class _Zaehler:
    """Zaehlt Aufrufe je Sollsperre, ohne das Verhalten zu aendern."""

    def __init__(self) -> None:
        self.treffer: dict[str, int] = {name: 0 for name, _, _, _ in SOLLSPERREN}

    @property
    def quote(self) -> int:
        return sum(1 for anzahl in self.treffer.values() if anzahl > 0)


def _spitzel(monkeypatch: pytest.MonkeyPatch) -> _Zaehler:
    """Haengt an jede der fuenf Sollsperren einen Zaehler -- an der BENUTZUNGSstelle.

    An der Benutzungsstelle und nicht an der Definition: nur so faellt auf, wenn der
    Aufrufer die Sperre gar nicht mehr importiert.
    """
    zaehler = _Zaehler()
    for anzeige, definition, benutzung, funktion in SOLLSPERREN:
        modul = __import__(benutzung, fromlist=["_"])
        if not hasattr(modul, funktion):
            pytest.fail(
                f"Dauertor findet seinen Gegenstand nicht: {benutzung} importiert "
                f"{funktion!r} nicht (definiert in {definition}). Die Sperre "
                f"{anzeige!r} ist am Order-Pfad abgehaengt."
            )
        original = getattr(modul, funktion)

        def gezaehlt(
            *args: Any, _orig: Any = original, _name: str = anzeige, **kwargs: Any
        ) -> Any:
            zaehler.treffer[_name] += 1
            return _orig(*args, **kwargs)

        monkeypatch.setattr(modul, funktion, gezaehlt)
    return zaehler


def _eroeffnende_order(**over: object) -> OrderRequest:
    base: dict[str, object] = {
        "client_order_id": "verdrahtung-1",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "volume": Decimal("0.01"),
        "stop_loss": Decimal("1.09000"),
        "meta": {"requested_leverage": 5},
    }
    base.update(over)
    return OrderRequest(**base)  # type: ignore[arg-type]


def test_demo_eroeffnung_faehrt_alle_fuenf_sperren(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Fall, der frueher 0 von 5 war: eine Eroeffnung auf dem **Demo**-Konto."""
    zaehler = _spitzel(monkeypatch)
    venue, terminal = _venue(is_demo=True)
    ergebnis = venue.submit_order(_eroeffnende_order())
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1
    fehlend = [name for name, anzahl in zaehler.treffer.items() if anzahl == 0]
    assert zaehler.quote == SOLL_SPERRENZAHL, (
        f"Verdrahtungsquote {zaehler.quote} von {SOLL_SPERRENZAHL} auf Demo. "
        f"Nicht gelaufen: {fehlend}"
    )


def test_live_eroeffnung_faehrt_alle_fuenf_sperren(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Derselbe Nachweis am **Live**-Konto mit vollstaendiger Freigabe."""
    from test_mt5_venue import (
        _LENIENT_COST_GATE,
        _freigabedatei,
        _fresh_risk,
        _reifer_demo_beleg,
    )

    zaehler = _spitzel(monkeypatch)
    venue, terminal = _venue(
        is_demo=False,
        freigabedatei=_freigabedatei(tmp_path),
        cost_gate=_LENIENT_COST_GATE,
        risk_manager=_fresh_risk(),
        demo_registration=_reifer_demo_beleg(),
    )
    ergebnis = venue.submit_order(_eroeffnende_order())
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1
    fehlend = [name for name, anzahl in zaehler.treffer.items() if anzahl == 0]
    assert zaehler.quote == SOLL_SPERRENZAHL, (
        f"Verdrahtungsquote {zaehler.quote} von {SOLL_SPERRENZAHL} auf Live. "
        f"Nicht gelaufen: {fehlend}"
    )


def test_ohne_risikoschicht_keine_eroeffnung_auch_auf_demo() -> None:
    """Fehlt der Manager, wird fail-closed abgelehnt -- auf JEDEM Konto."""
    from mt5_trading_ai.venue.catalog import CatalogEntry  # noqa: F401
    from mt5_trading_ai.venue.mt5 import Mt5Venue

    from test_mt5_venue import _catalog

    terminal = FakeMt5Terminal(is_demo=True)
    venue = Mt5Venue(
        name="ohne-risiko",
        terminal=terminal,
        catalog=_catalog(),
        risk_manager=None,
        clock=lambda: TS,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "risk_unconfigured"
    assert terminal.order_send_calls == 0


def test_reduce_only_bleibt_frei(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reduce-Only faehrt die fuenf Sperren NICHT -- und das ist Absicht.

    Eine Sperre, die das Schliessen verhindert, erhoeht das Risiko. Der Test haelt die
    Ausnahme fest, damit sie nicht versehentlich zugezogen wird.
    """
    zaehler = _spitzel(monkeypatch)
    venue, terminal = _venue(
        is_demo=True,
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),),
    )
    ergebnis = venue.submit_order(
        _eroeffnende_order(
            client_order_id="reduce-1",
            side=OrderSide.SELL,
            reduce_only=True,
            position_ticket="t1",
            stop_loss=Decimal("0"),
        )
    )
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1
    assert zaehler.quote == 0, (
        f"Reduce-Only hat {zaehler.quote} Sperren gefahren, erwartet 0: "
        f"{zaehler.treffer}"
    )


def test_emergency_flatten_kann_nicht_eroeffnen() -> None:
    """Der Not-Aus baut nur ab. Eine Eroeffnung ist dort doppelt gesperrt."""
    venue, terminal = _venue(
        is_demo=True,
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),),
    )
    ergebnisse = venue.emergency_flatten()
    assert venue.is_halted() is True
    assert len(ergebnisse) == 1
    assert terminal.order_send_calls == 1
    # Nach dem Not-Aus ist jede Eroeffnung gesperrt -- der Latch klaert nicht selbst.
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order(client_order_id="nach-flatten"))
    assert ex.value.reason == "global_halt"


# --------------------------------------------------------------------------- #
# A3.4 -- statisch: der alte Fehler darf nicht zurueckkehren.                  #
# --------------------------------------------------------------------------- #
def test_risikoschicht_hat_keinen_konto_abhaengigen_ausstieg() -> None:
    """``_enforce_risk`` darf nicht wieder ``if account.is_demo: return`` bekommen.

    Das war die Form, in der die Risikoschicht formal verdrahtet und praktisch tot war.
    """
    baum = _lade_baum(MT5_QUELLE)
    funktion = _finde_funktion(baum, "Mt5Venue", "_enforce_risk", "venue/mt5.py")
    quelle = ast.unparse(funktion)
    assert "is_demo" not in quelle, (
        "_enforce_risk prueft wieder auf is_demo. Eine Sperre, die nur am Live-Konto "
        "laeuft, laeuft an keinem erreichbaren Konto -- genau der Rueckfall, den "
        "dieses Tor verhindern soll.\n" + quelle
    )


def test_frische_latch_hat_keinen_konto_abhaengigen_ausstieg() -> None:
    baum = _lade_baum(MT5_QUELLE)
    funktion = _finde_funktion(
        baum, "Mt5Venue", "_enforce_account_freshness", "venue/mt5.py"
    )
    quelle = ast.unparse(funktion)
    assert "is_demo" not in quelle, (
        "_enforce_account_freshness prueft auf is_demo. Ein veralteter Kontostand ist "
        "auf Demo genauso wenig bewertbar wie auf Live."
    )
    assert "evaluate_account_freshness" in quelle, (
        "_enforce_account_freshness ruft die Sperrfunktion nicht mehr auf."
    )


def test_frische_misst_nicht_gegen_die_eigene_uhr() -> None:
    """E9: der Melder darf seinen Stempel nicht aus der Uhr ziehen, gegen die er misst.

    Der bisherige Test dieses Tors prueft per AST nur, **dass**
    ``evaluate_account_freshness`` gerufen wird -- nicht, dass der Aufruf ablehnen
    kann. Genau darunter versteckte sich E9: die Sperre holte
    ``self._terminal.account()`` und hielt dessen ``ts`` gegen ``self._clock()``,
    waehrend ``RealMt5Terminal.account`` diesen Stempel im selben Aufruf auf
    ``datetime.now(UTC)`` setzt. Alter per Konstruktion Mikrosekunden, Frist fuenf
    Sekunden, in 21 Betriebsjournalen kein einziges ``snapshot_stale``.

    Dieser Test macht die Bedingung strukturell nachpruefbar, ohne eine Namensliste zu
    pflegen: er misst am Quelltext, welche Terminal-Methoden ihren Zeitstempel selbst
    setzen, und verlangt, dass ``snapshot_ts`` aus keiner von ihnen stammt.
    """
    baum = _lade_baum(MT5_QUELLE)
    selbst = _selbstgestempelte_terminalmethoden(baum)
    assert selbst, (
        "Dauertor findet keine einzige selbstgestempelte Terminal-Methode. Das ist "
        "ein Fehlschlag des Tors: solange ``RealMt5Terminal.account`` seinen "
        "Zeitstempel selbst setzt, MUSS diese Messung etwas finden."
    )
    funktion = _finde_funktion(
        baum, "Mt5Venue", "_enforce_account_freshness", "venue/mt5.py"
    )
    aufrufe = [
        knoten
        for knoten in ast.walk(funktion)
        if isinstance(knoten, ast.Call)
        and _rufname(knoten) == "evaluate_account_freshness"
    ]
    if not aufrufe:
        pytest.fail(
            "Dauertor findet seinen Gegenstand nicht: _enforce_account_freshness ruft "
            "evaluate_account_freshness nicht."
        )
    kw = {k.arg: ast.unparse(k.value) for k in aufrufe[0].keywords if k.arg is not None}
    for name in ("snapshot_ts", "now"):
        assert name in kw, (
            f"{name} wird nicht benannt uebergeben -- der Melder ist nicht pruefbar."
        )
    assert kw["snapshot_ts"] != kw["now"], (
        f"snapshot_ts und now sind derselbe Ausdruck ({kw['now']}). Das Alter ist "
        "damit immer null und die Sperre kann nicht ausloesen."
    )

    herkunft = _terminalherkunft(funktion)
    wurzel = kw["snapshot_ts"].split(".")[0]
    assert wurzel in herkunft, (
        f"snapshot_ts={kw['snapshot_ts']!r} stammt aus keinem Terminal-Aufruf. Ein "
        "Frischestempel muss von der anderen Seite der Leitung kommen; alles andere "
        f"ist die eigene Uhr. Aus dem Terminal kamen: {sorted(herkunft)}."
    )
    quelle = herkunft[wurzel]
    assert quelle not in selbst, (
        f"Der Frische-Latch misst gegen {quelle}(), und {quelle}() setzt seinen "
        f"Zeitstempel selbst aus der Systemuhr (gemessen am Quelltext: "
        f"{sorted(selbst)}). Damit wird die eigene Uhr gegen die eigene Uhr gehalten: "
        "das Alter ist per Konstruktion null, die Sperre kann nicht ausloesen. "
        "Zulaessig ist nur ein Stempel vom Broker, etwa der Kursstempel."
    )


def test_roter_eichfall_frische_gegen_den_brokerstempel() -> None:
    """E9 dynamisch: frischer Kontostempel, alter Kurs -- die Order faellt.

    Der statische Test darueber belegt den Bauplan, dieser die Wirkung. Er braucht ein
    Terminal, das sich wie das echte verhaelt: Kontostempel aus der eigenen Uhr,
    Kursstempel vom Broker (``tests/test_frische_am_orderpfad.py``). Gegen die alte
    Fassung lief diese Order durch.
    """
    from mt5_trading_ai.venue.mt5 import Mt5Venue

    from test_frische_am_orderpfad import SelbstgestempeltesTerminal
    from test_mt5_venue import _catalog, _fresh_risk

    terminal = SelbstgestempeltesTerminal(
        uhr=lambda: TS, kursalter={"EURUSD": timedelta(minutes=5)}, is_demo=True
    )
    venue = Mt5Venue(
        name="eichfall-frische",
        terminal=terminal,
        catalog=_catalog(),
        risk_manager=_fresh_risk(),
        clock=lambda: TS,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    # Vorbedingung: nach der ALTEN Rechnung waere hier alles gruen gewesen.
    assert terminal.account().ts == TS
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "snapshot_stale"
    assert terminal.order_send_calls == 0


def test_frische_laeuft_vor_allem_was_den_kontozustand_liest() -> None:
    """Die Reihenfolge aus A3.2: Frische zuerst, dann alles Kontoabhaengige."""
    baum = _lade_baum(MT5_QUELLE)
    funktion = _finde_funktion(baum, "Mt5Venue", "submit_order", "venue/mt5.py")
    reihenfolge = [
        knoten.func.attr
        for knoten in ast.walk(funktion)
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute)
    ]
    for name in (
        "_enforce_account_freshness",
        "_require_live_release_for_opening",
        "_enforce_risk",
    ):
        assert name in reihenfolge, f"{name} wird in submit_order nicht aufgerufen"
    assert reihenfolge.index("_enforce_account_freshness") < reihenfolge.index(
        "_require_live_release_for_opening"
    ), "Frische-Latch laeuft nach der Live-Freigabe -- die liest is_demo aus genau "
    "dem Schnappschuss, dessen Frische noch nicht geprueft ist."
    assert reihenfolge.index("_enforce_account_freshness") < reihenfolge.index(
        "_enforce_risk"
    ), "Frische-Latch laeuft nach der Risikoschicht."


def test_alle_sollsperren_sind_am_benutzungsort_importiert() -> None:
    """Statischer Gegenbeleg zum dynamischen Zaehler: der Import steht wirklich da."""
    for anzeige, definition, benutzung, funktion in SOLLSPERREN:
        modul = __import__(benutzung, fromlist=["_"])
        assert hasattr(modul, funktion), (
            f"{anzeige}: {benutzung} importiert {funktion!r} nicht "
            f"(definiert in {definition})."
        )


def test_eintrittspunkte_ausser_dem_venue_laufen_ueber_den_flaschenhals() -> None:
    """E2 und E3 erben die fuenf Sperren, weil sie ueber ``submit_order`` gehen."""
    for rel, klasse, name in EINTRITTSPUNKTE:
        if rel.endswith("venue/mt5.py"):
            continue  # der Flaschenhals selbst
        baum = _lade_baum(ROOT / rel)
        funktion = _finde_funktion(baum, klasse, name, rel)
        assert "submit_order" in _aufgerufene_namen(funktion), (
            f"{rel}:{name} baut eine eroeffnende Order, ruft aber nicht "
            "submit_order -- damit laeuft sie an allen fuenf Sperren vorbei."
        )


def test_realterminal_schreibpfad_ist_auf_demo_geklammert() -> None:
    """E5: der direkte Terminalzugriff liegt unter dem Flaschenhals."""
    baum = _lade_baum(MT5_QUELLE)
    funktion = _finde_funktion(
        baum, "RealMt5Terminal", "_require_write", "venue/mt5.py"
    )
    quelle = ast.unparse(funktion)
    assert "_allow_write" in quelle
    assert "_require_demo" in quelle and "is_demo" in quelle, (
        "RealMt5Terminal._require_write klammert den Schreibpfad nicht mehr an ein "
        "Demokonto. Er liegt unter dem Order-Pfad und umginge alle fuenf Sperren."
    )


# --------------------------------------------------------------------------- #
# A3.3 -- roter Eichfall je Sperre: absichtlich beschaedigen, Rot belegen.     #
# --------------------------------------------------------------------------- #
def test_roter_eichfall_frische_latch() -> None:
    """Sperre 1 rot: der Kontozustand ist aelter als die Frist."""
    venue, terminal = _venue(is_demo=True, clock=lambda: TS + timedelta(minutes=5))
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "snapshot_stale"
    assert terminal.order_send_calls == 0


def test_roter_eichfall_frische_latch_zukunft() -> None:
    """Sperre 1 rot: der Stempel liegt in der Zukunft -- ebenso wenig bewertbar."""
    venue, terminal = _venue(is_demo=True, clock=lambda: TS - timedelta(minutes=5))
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "snapshot_from_future"
    assert terminal.order_send_calls == 0


def test_gruener_eichfall_frische_latch() -> None:
    """Sperre 1 gruen: ein frischer Zustand laesst dieselbe Order durch."""
    venue, terminal = _venue(is_demo=True, clock=lambda: TS + timedelta(seconds=1))
    assert venue.submit_order(_eroeffnende_order()).accepted is True
    assert terminal.order_send_calls == 1


def test_roter_eichfall_verlustgrenzen() -> None:
    """Sperre 2 rot: Drawdown ueber der Grenze -> Halt, mit Latch."""
    from mt5_trading_ai.execution.risk_manager import RiskManager

    rm = RiskManager(zustand=FluechtigerZustand())
    rm.observe_equity(TS - timedelta(hours=1), Decimal("12000"))
    venue, terminal = _venue(is_demo=True, risk_manager=rm)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "risk_drawdown_limit_reached"
    assert venue.is_halted() is True
    assert terminal.order_send_calls == 0


def test_roter_eichfall_stop_budget() -> None:
    """Sperre 3 rot: Sicherheitsfaktor 100 drueckt die Obergrenze unter den Floor."""
    from mt5_trading_ai.execution.risk_manager import RiskManager, RiskPolicy

    venue, terminal = _venue(
        is_demo=True,
        risk_manager=RiskManager(
            RiskPolicy(safety=Decimal("100")), zustand=FluechtigerZustand()
        ),
    )
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "risk_sizing_stop_floor_exceeds_budget"
    assert terminal.order_send_calls == 0


def test_roter_eichfall_positionsgroesse() -> None:
    """Sperre 4 rot: 0,10 Lot reissen das Risikobudget von 0,25 %."""
    venue, terminal = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order(volume=Decimal("0.10")))
    assert ex.value.reason == "volume_exceeds_risk_budget"
    assert terminal.order_send_calls == 0


def test_roter_eichfall_bewertungstor() -> None:
    """Sperre 5 rot: die Drossel sperrt den zu schnellen zweiten Trade."""
    venue, terminal = _venue(is_demo=True)
    assert venue.submit_order(_eroeffnende_order(client_order_id="d-1")).accepted
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order(client_order_id="d-2"))
    assert ex.value.reason.startswith("throttle_")
    assert terminal.order_send_calls == 1


def test_gruener_eichfall_alle_sperren() -> None:
    """Alle fuenf gruen: dieselbe Order geht durch, wenn nichts beschaedigt ist."""
    venue, terminal = _venue(is_demo=True)
    ergebnis = venue.submit_order(_eroeffnende_order())
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


# --------------------------------------------------------------------------- #
# A3.5 -- der Kill-Switch: wo er wirklich liegt, gegen den Code belegt.        #
# --------------------------------------------------------------------------- #
def test_kill_switch_kriterium_liegt_in_limits() -> None:
    """``risk/limits.py`` traegt Kriterium und Zustaende -- inklusive Reduce-Only."""
    from mt5_trading_ai.risk.limits import AccountSnapshot, TradingState

    assert {zustand.value for zustand in TradingState} >= {
        "normal",
        "reduce_only",
        "halted",
    }
    assert "manual_release_id" in AccountSnapshot.__dataclass_fields__, (
        "Die Freigabe-Kante des Kill-Switch fehlt im Kontozustand."
    )


def test_kill_switch_griff_und_latch_liegen_am_venue() -> None:
    """Ein Halt, der sich nicht selbst loest, braucht einen Halter: das Venue."""
    from mt5_trading_ai.venue.mt5 import Mt5Venue

    for name in ("latch_halt", "clear_halt", "is_halted", "emergency_flatten"):
        assert hasattr(Mt5Venue, name), (
            f"Mt5Venue.{name} fehlt -- der Kill-Switch haette keinen Griff."
        )


def test_kill_switch_latch_haelt_und_loest_nur_von_hand() -> None:
    """Der Latch ist das, was einen Halt von einer Ablehnung unterscheidet."""
    venue, terminal = _venue(is_demo=True)
    venue.latch_halt(reason="pruefung")
    assert venue.is_halted() is True
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_eroeffnende_order())
    assert ex.value.reason == "global_halt"
    assert terminal.order_send_calls == 0
    # Er loest sich nicht von selbst -- eine zweite Order faellt genauso.
    with pytest.raises(OrderRejectedError):
        venue.submit_order(_eroeffnende_order(client_order_id="nochmal"))
    venue.clear_halt()
    assert venue.is_halted() is False
    assert venue.submit_order(_eroeffnende_order()).accepted is True


def test_kill_switch_freigabe_liegt_am_risikomanager() -> None:
    from mt5_trading_ai.execution.risk_manager import RiskManager

    assert hasattr(RiskManager, "release_drawdown")


def test_die_quote_ist_fuenf_von_fuenf() -> None:
    """Die Zahl, um die es in M3 geht -- ausdruecklich, mit Bezugsgroesse."""
    assert len(SOLLSPERREN) == SOLL_SPERRENZAHL
    namen = [name for name, _, _, _ in SOLLSPERREN]
    assert len(set(namen)) == SOLL_SPERRENZAHL, f"Doppelte Sollsperre: {namen}"
