"""Stufe 5 — Ausfuehrungserfahrung. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Woertlich::

    Gegen die Demoumgebung: Platzierung, Abbruch, doppelte Auftragskennung, falsche
    Signatur, abweichende Uhr — als redigierte Aufzeichnungen einchecken.
    Nicht-endgueltigen Zustand „Antwort blieb aus, Auftrag koennte leben" einfuehren,
    der sichtbar bleibt und vor der naechsten Eroeffnung aufgeloest werden muss.

    Abnahme: mindestens eine echte, aufgezeichnete Antwort des Handelsplatzes liegt im
    Repo; drei Testfaelle sichern Datenbankzustand, genau einen Auftrag beim Gegenueber
    und den Riegelzustand zu.

Die drei namentlich verlangten Faelle stehen unten unter ihren Ueberschriften. Jeder
hat einen roten und einen gruenen Eichfall -- ein Tor, das nur gruen gefahren wird, ist
behauptet und nicht nachgewiesen.

WAS DIESE STUFE GEFUNDEN HAT
----------------------------
Der Zustand „Antwort blieb aus" existierte, aber als ``dict`` im Prozessgedaechtnis.
Zwei Messungen (``archiv/AUFTRAG/stufen/05-ausfuehrung/belege/``):

* Nach ``clear_halt()`` ging die naechste Eroeffnung durch, **waehrend der ungeklaerte
  Eintrag noch stand** -- der Auftrag verlangt das Gegenteil.
* Ein frisch gebautes Venue meldete eine leere Arbeitsliste. Ein Neustart loeschte also
  gerade die Kenntnis davon, dass moeglicherweise Geld am Markt steht.
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.execution.schwebende_auftraege import (
    FORMATFASSUNG,
    SchwebeAkte,
    SchwebenderAuftrag,
)
from mt5_trading_ai.venue.protocol import OrderRejectedError, OrderSide

from test_mt5_venue import _mt5_position, _order, _venue

ROOT = Path(__file__).resolve().parents[1]
AUFZEICHNUNG = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"


def _wirft(_request: Any) -> Any:
    raise RuntimeError("Zeitablauf -- keine Antwort vom Broker")


def _venue_mit_akte(tmp_path: Path, **kw: Any):
    return _venue(
        is_demo=True, schwebeakte=SchwebeAkte(tmp_path / "schwebe.json"), **kw
    )


# =====================================================================
# Abnahmefall 1 — DATENBANKZUSTAND
# =====================================================================
def test_datenbankzustand_ueberdauert_den_neustart(tmp_path: Path) -> None:
    """Roter Eichfall: vor dieser Stufe war die Liste nach einem Neustart leer.

    Der Fall baut ein **zweites** Venue auf derselben Akte -- das ist der Neustart. Ohne
    die Akte auf der Platte findet es nichts und eroeffnet froehlich weiter.
    """
    akte = tmp_path / "schwebe.json"
    venue, terminal = _venue(is_demo=True, schwebeakte=SchwebeAkte(akte))
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="db-1"))

    zweites, _ = _venue(is_demo=True, schwebeakte=SchwebeAkte(akte))
    kennungen = [e.client_order_id for e in zweites.schwebende_auftraege()]
    assert kennungen == ["db-1"], "Der Neustart hat die Akte nicht gefunden."


def test_datenbankzustand_ist_ohne_zwischenfall_leer(tmp_path: Path) -> None:
    """Gruener Gegenfall: eine fehlende Akte heisst „nichts schwebt", nicht „Sperre".

    Ohne ihn bestuende der rote Fall auch an einer Akte, die immer etwas meldet -- dann
    waere jede Eroeffnung dauerhaft gesperrt und der Nachweis wertlos.
    """
    venue, _ = _venue_mit_akte(tmp_path)
    assert venue.schwebende_auftraege() == ()
    assert not (tmp_path / "schwebe.json").exists()


def test_datenbankzustand_sperrt_wenn_die_akte_unlesbar_ist(tmp_path: Path) -> None:
    """Die Irrtumsrichtung: unbeantwortet gilt als „ja, es schwebt etwas"."""
    akte = tmp_path / "schwebe.json"
    akte.write_text("{kein json", encoding="utf-8")
    venue, terminal = _venue(is_demo=True, schwebeakte=SchwebeAkte(akte))
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="db-defekt"))
    assert ex.value.reason == "schwebender_auftrag"
    assert terminal.order_send_calls == 0


def test_datenbankzustand_sperrt_bei_unbekannter_fassung(tmp_path: Path) -> None:
    """Eine spaetere Fassung koennte Felder tragen, deren Fehlen hier harmlos aussaehe."""
    akte = tmp_path / "schwebe.json"
    akte.write_text(
        json.dumps({"fassung": FORMATFASSUNG + 1, "eintraege": []}), encoding="utf-8"
    )
    venue, _ = _venue(is_demo=True, schwebeakte=SchwebeAkte(akte))
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="db-fassung"))
    assert ex.value.reason == "schwebender_auftrag"


def test_fluechtige_akte_ist_als_fluechtig_ablesbar(tmp_path: Path) -> None:
    """„Fluechtig" verhaelt sich bis zum Neustart wie „dauerhaft" -- also muss man es sehen.

    Dieselbe Begruendung wie bei ``RiskManager.zustand_dauerhaft``. Wer es erst am
    Neustart merkt, merkt es an dem Tag, an dem es zaehlt.
    """
    assert SchwebeAkte(None).dauerhaft is False
    assert SchwebeAkte(tmp_path / "a.json").dauerhaft is True


def test_fluechtige_akte_haelt_innerhalb_des_prozesses(tmp_path: Path) -> None:
    """Fluechtig heisst nicht wirkungslos: innerhalb des Laufs sperrt sie genauso."""
    venue, terminal = _venue(is_demo=True, schwebeakte=SchwebeAkte(None))
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="fl-1"))
    assert [e.client_order_id for e in venue.schwebende_auftraege()] == ["fl-1"]


# =====================================================================
# Abnahmefall 2 — GENAU EIN AUFTRAG BEIM GEGENUEBER
# =====================================================================
def test_dieselbe_kennung_erzeugt_genau_einen_auftrag(tmp_path: Path) -> None:
    """Doppelte Auftragskennung: der zweite Ruf sendet NICHT ein zweites Mal.

    Der Auftrag nennt „doppelte Auftragskennung" ausdruecklich als aufzuzeichnenden
    Fall. Gemessen wird am Zaehler des Terminals -- an der einzigen Stelle, an der
    „beim Gegenueber" ueberhaupt beobachtbar ist.
    """
    venue, terminal = _venue_mit_akte(tmp_path)
    erste = venue.submit_order(_order(client_order_id="doppelt-1"))
    zweite = venue.submit_order(_order(client_order_id="doppelt-1"))

    assert terminal.order_send_calls == 1, "Zwei Auftraege beim Gegenueber."
    assert erste.accepted is True
    assert zweite.idempotent_replay is True
    assert zweite.venue_order_id == erste.venue_order_id


def test_zwei_verschiedene_kennungen_erzeugen_zwei_auftraege(tmp_path: Path) -> None:
    """Gruener Gegenfall. Ohne ihn bestuende der rote auch an einem Venue, das nach dem
    ersten Auftrag ueberhaupt nichts mehr sendet.

    Die Drossel steht dem entgegen -- sie weist die zweite Eroeffnung ab. Der Fall
    fuehrt sie deshalb bewusst als **Abbau** durch: eine reduzierende Order geht an den
    Toren vorbei und ist die saubere Gegenprobe darauf, dass ueberhaupt noch gesendet
    wird.
    """
    positionen = (
        _mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10"), ticket="t1"),
    )
    venue, terminal = _venue(
        is_demo=True,
        positions=positionen,
        schwebeakte=SchwebeAkte(tmp_path / "schwebe.json"),
    )
    for nr in (1, 2):
        ergebnis = venue.submit_order(
            _order(
                client_order_id=f"verschieden-{nr}",
                side=OrderSide.SELL,
                volume=Decimal("0.01"),
                reduce_only=True,
                position_ticket="t1",
                stop_loss=Decimal("0"),
            )
        )
        assert ergebnis.accepted is True
        assert ergebnis.idempotent_replay is False
    assert terminal.order_send_calls == 2


# =====================================================================
# Abnahmefall 3 — RIEGELZUSTAND
# =====================================================================
def test_ein_schwebender_auftrag_sperrt_die_naechste_eroeffnung(tmp_path: Path) -> None:
    """Der Kern der Stufe: „muss vor der naechsten Eroeffnung aufgeloest werden"."""
    venue, terminal = _venue_mit_akte(tmp_path)
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="riegel-1"))

    terminal.order_send = type(terminal).order_send.__get__(terminal, type(terminal))  # type: ignore[method-assign]
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="riegel-2"))
    assert ex.value.reason == "schwebender_auftrag"


def test_clear_halt_allein_gibt_die_eroeffnung_nicht_frei(tmp_path: Path) -> None:
    """DER rote Eichfall der Stufe -- genau so war es gemessen worden.

    Der Sendeversuch latcht den Global-Halt UND vermerkt die Kennung. ``clear_halt()``
    loest nur den Halt. Wer nur den Halt sieht, gibt ihn frei und eroeffnet weiter --
    an einer Order vorbei, die beim Broker liegen koennte.
    """
    venue, terminal = _venue_mit_akte(tmp_path)
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="riegel-3"))
    terminal.order_send = type(terminal).order_send.__get__(terminal, type(terminal))  # type: ignore[method-assign]

    venue.clear_halt()
    assert venue.is_halted() is False, "Der Halt selbst ist frei."
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order(client_order_id="riegel-4"))
    assert ex.value.reason == "schwebender_auftrag"


def test_aufloesung_ohne_befund_wird_abgewiesen(tmp_path: Path) -> None:
    """Die Aufloesung ist die Behauptung, beim Broker nachgesehen zu haben."""
    venue, terminal = _venue_mit_akte(tmp_path)
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="riegel-5"))

    with pytest.raises(ValueError, match="Befund"):
        venue.sendeversuch_aufloesen("riegel-5", befund="   ")
    assert [e.client_order_id for e in venue.schwebende_auftraege()] == ["riegel-5"]


def test_aufloesung_mit_befund_gibt_die_eroeffnung_frei(tmp_path: Path) -> None:
    """Der gruene Gegenfall: die Sperre hat einen Ausgang, und er fuehrt ueber einen
    Menschen.

    Eine Sperre ohne Ausgang wird im Betrieb ausgebaut -- das steht in diesem Repo
    schon einmal, an den offenen Positionen in ``risiko_zustand.py``.
    """
    venue, terminal = _venue_mit_akte(tmp_path)
    terminal.order_send = _wirft  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        venue.submit_order(_order(client_order_id="riegel-6"))
    terminal.order_send = type(terminal).order_send.__get__(terminal, type(terminal))  # type: ignore[method-assign]
    venue.clear_halt()

    assert venue.sendeversuch_aufloesen(
        "riegel-6", befund="Broker kennt die Kennung nicht; keine Position offen"
    )
    assert venue.schwebende_auftraege() == ()
    assert venue.submit_order(_order(client_order_id="riegel-7")).accepted is True


def test_der_erste_grund_bleibt_stehen(tmp_path: Path) -> None:
    """Ein zweiter Versuch derselben Kennung ueberschreibt den ersten Grund nicht.

    Der erste Grund sagt, wonach beim Broker zu sehen ist -- ein Zeitablauf liest sich
    anders als ein gesperrter Schreibpfad.
    """
    akte = SchwebeAkte(tmp_path / "schwebe.json")
    from datetime import UTC, datetime

    ts = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    akte.vermerken(SchwebenderAuftrag("k-1", "Zeitablauf", ts, "EURUSD"))
    akte.vermerken(SchwebenderAuftrag("k-1", "etwas anderes", ts, "EURUSD"))
    eintraege = akte.laden().eintraege
    assert len(eintraege) == 1
    assert eintraege[0].grund == "Zeitablauf"


# =====================================================================
# Abnahme — "mindestens eine echte, aufgezeichnete Antwort liegt im Repo"
# =====================================================================
def test_die_aufzeichnung_liegt_im_repo_und_traegt_echte_antworten() -> None:
    """Nicht „es gibt Journale", sondern: sie sind eingecheckt und tragen Antworten."""
    assert AUFZEICHNUNG.is_file(), (
        f"{AUFZEICHNUNG.relative_to(ROOT).as_posix()} fehlt. "
        "Erzeugen mit: python tools/aufzeichnung_redigieren.py"
    )
    saetze = [
        json.loads(z)
        for z in AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    kopf, rest = saetze[0], saetze[1:]
    assert kopf["art"] == "_kopf"
    arten = {s["art"] for s in rest}

    # Eine Platzierung mit Einstiegspreis ist eine Antwort des Handelsplatzes.
    eroeffnet = [s for s in rest if s["art"] == "eroeffnet"]
    assert eroeffnet, "Keine einzige aufgezeichnete Eroeffnung."
    assert all(s.get("einstiegspreis") for s in eroeffnet)

    # Und ein Abbruch: der Handelsplatz hat abgelehnt, im Wortlaut.
    assert "schliessen_fehlgeschlagen" in arten, "Kein aufgezeichneter Abbruch."


def test_die_aufzeichnung_traegt_keine_unredigierten_kennungen() -> None:
    """Der Fall, ohne den die Aufzeichnung nicht eingecheckt bleiben duerfte.

    Geprueft wird auf das, was in den Originaljournalen stand: Kontonummern, Pfade mit
    Benutzernamen und die Original-Kennungen des Laufs.
    """
    import re

    text = AUFZEICHNUNG.read_text(encoding="utf-8")
    verstoesse: dict[str, list[str]] = {}
    for name, muster in {
        "Ziffernfolge (Kontonummer/Ticket)": r"\b\d{6,12}\b",
        "Windows-Pfad": r"[A-Za-z]:\\\\",
        "Original-Kennung": r'"(?:open|fl)-[^"]+"',
    }.items():
        treffer = re.findall(muster, text)
        if treffer:
            verstoesse[name] = treffer[:3]
    assert verstoesse == {}, f"Unredigierte Werte in der Aufzeichnung: {verstoesse}"


def test_die_aufzeichnung_weist_aus_was_weggelassen_wurde() -> None:
    """Eine stille Verkleinerung waere eine Aufzeichnung, die vollstaendig aussieht.

    98 % der Saetze sind Messrauschen und fehlen bewusst. Die Zahl steht je Art im
    Kopf -- sonst waere aus der Datei nicht ablesbar, dass sie eine Auswahl ist.
    """
    kopf = json.loads(AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()[0])
    assert kopf["weggelassen_gesamt"] > 0
    assert kopf["saetze_weggelassen"], "Die weggelassenen Arten sind nicht benannt."
    assert kopf["behalten_gesamt"] == sum(kopf["saetze_behalten"].values())


def test_das_redigierwerkzeug_laeuft_und_bestaetigt_die_aufzeichnung() -> None:
    """Bestaetigt durch Ausfuehrung, nicht durch Zusicherung.

    Faellt ``betrieb/`` weg (frischer Klon, ``git clean``), meldet das Werkzeug das und
    besteht -- die eingecheckte Aufzeichnung ist dann nicht nachziehbar, aber auch
    nicht falsch.
    """
    lauf = subprocess.run(
        [sys.executable, "tools/aufzeichnung_redigieren.py", "--pruefen"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
