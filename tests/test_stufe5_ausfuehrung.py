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
import re
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.execution.schwebende_auftraege import (
    FORMATFASSUNG,
    FluechtigeSchwebeAkte,
    SchwebeAkte,
    SchwebenderAuftrag,
)
from mt5_trading_ai.venue.protocol import OrderRejectedError, OrderSide
from tools.aufzeichnung_redigieren import (
    journale,
    pruefe_aufzeichnung,
    redigiere,
    schreibform,
)

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
    assert FluechtigeSchwebeAkte().dauerhaft is False
    assert SchwebeAkte(tmp_path / "a.json").dauerhaft is True


def test_fluechtige_akte_haelt_innerhalb_des_prozesses(tmp_path: Path) -> None:
    """Fluechtig heisst nicht wirkungslos: innerhalb des Laufs sperrt sie genauso."""
    venue, terminal = _venue(is_demo=True, schwebeakte=FluechtigeSchwebeAkte())
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


def _aufzeichnung() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(Kopf, Saetze) der eingecheckten Aufzeichnung. Fehlt sie: rot, nicht skip."""
    assert AUFZEICHNUNG.is_file(), (
        f"{AUFZEICHNUNG.relative_to(ROOT).as_posix()} fehlt. "
        "Erzeugen mit: python tools/aufzeichnung_redigieren.py"
    )
    zeilen = [
        json.loads(z)
        for z in AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    assert zeilen and zeilen[0]["art"] == "_kopf"
    return zeilen[0], zeilen[1:]


def test_die_aufzeichnung_traegt_keine_unredigierten_kennungen() -> None:
    """Der Fall, ohne den die Aufzeichnung nicht eingecheckt bleiben duerfte.

    Geprueft wird auf das, was in den Originaljournalen stand: Kontonummern, Tickets
    (auch in der Positionsliste der Takte), Pfade mit Benutzernamen, die
    Original-Auftragskennungen und die Hex-Laufkennungen. Die Muster stehen hier
    unabhaengig von denen des Werkzeugs -- ein Pruefer, der nur sich selbst prueft,
    prueft nichts.
    """
    text = AUFZEICHNUNG.read_text(encoding="utf-8")
    verstoesse: dict[str, int] = {}
    for name, muster in {
        "Ziffernfolge (Kontonummer/Ticket)": r"\b\d{6,12}\b",
        "Windows-Pfad": r"[A-Za-z]:\\\\",
        "Original-Kennung": r'"(?:open|close|fl)-[^"]+"',
        "Hex-Laufkennung": r"\b[0-9a-f]{32}\b",
        "Kontoname": r"\\Users\\",
    }.items():
        treffer = re.findall(muster, text)
        if treffer:
            verstoesse[name] = len(treffer)
    assert verstoesse == {}, f"Unredigierte Werte in der Aufzeichnung: {verstoesse}"
    assert pruefe_aufzeichnung(text) == []


def test_die_aufzeichnung_weist_aus_was_weggelassen_wurde() -> None:
    """Eine stille Verkleinerung waere eine Aufzeichnung, die vollstaendig aussieht.

    Zwei Drittel der Saetze sind Messrauschen (``kurs``, ``signal``) und fehlen
    bewusst. Die Zahl steht je Art im Kopf -- und der Kopf muss zum Inhalt passen,
    sonst ist er eine Behauptung.
    """
    kopf, rest = _aufzeichnung()
    assert kopf["weggelassen_gesamt"] > 0
    assert kopf["saetze_weggelassen"], "Die weggelassenen Arten sind nicht benannt."
    assert kopf["behalten_gesamt"] == sum(kopf["saetze_behalten"].values())
    assert kopf["behalten_gesamt"] == len(rest)
    gezaehlt = Counter(s["art"] for s in rest)
    assert dict(gezaehlt) == kopf["saetze_behalten"]
    assert not set(kopf["saetze_behalten"]) & set(kopf["saetze_weggelassen"])
    assert kopf["quelle"]["saetze"] == (
        kopf["behalten_gesamt"] + kopf["weggelassen_gesamt"]
    )
    assert kopf["quelle"]["journale"] == len(kopf["laeufe"]) == 21


def test_die_aufzeichnung_traegt_die_takte_mit_den_feldern_der_metriken() -> None:
    """Kopf-Fassung 2 (Auftrag 1, T6, Befund T): die ``takt``-Saetze sind da.

    Die erste Fassung liess sie weg (1.360 von 17.166 Saetzen) -- und damit alles,
    woraus Buchtreue (``halt``), Ausstiegsdeckung (``positionen``) und die
    Equity-Reihe (``equity``) gerechnet werden. Die Positionsliste ist redigiert: das
    Ticket einer Position heisst dort wie im ``eroeffnet``-Satz ``POSITION-nn``.
    """
    kopf, rest = _aufzeichnung()
    takte = [s for s in rest if s["art"] == "takt"]
    assert len(takte) == kopf["saetze_behalten"]["takt"] == 1360
    assert "takt" not in kopf["saetze_weggelassen"]
    assert all("halt" in s and "equity" in s for s in takte)
    positionen = [p for s in takte for p in (s.get("positionen") or [])]
    assert positionen, "kein einziger Takt mit Positionsliste"
    assert all(re.fullmatch(r"POSITION-\d+", p["position_id"]) for p in positionen)
    im_takt = {p["position_id"] for p in positionen}
    eroeffnet = {s["position_id"] for s in rest if s["art"] == "eroeffnet"}
    assert eroeffnet & im_takt, "Takt und eroeffnet-Satz nennen keine Position gleich"


def test_jeder_satz_traegt_eine_stabile_laufkennung() -> None:
    """``LAUF-nn`` ist die laufende Nummer des Journals in Zeitreihenfolge -- an jedem
    Satz, auch an denen der 17 Journale, die selbst keine Kennung schrieben.

    Stabil heisst: dieselbe Kennung bei jeder Erzeugung, weil sie aus der Reihenfolge
    der Journale folgt und nicht aus dem ersten Auftreten eines Werts. Der Kopf bildet
    sie auf den Journalnamen ab, und der Name traegt den Startzeitstempel des Laufs.
    """
    kopf, rest = _aufzeichnung()
    erwartet = [f"LAUF-{n:02d}" for n in range(1, 22)]
    assert list(kopf["laeufe"]) == erwartet
    kennungen = [s.get("lauf") for s in rest]
    assert all(isinstance(k, str) and re.fullmatch(r"LAUF-\d{2}", k) for k in kennungen)
    assert list(dict.fromkeys(kennungen)) == erwartet  # Reihenfolge des Auftretens
    erster_ts: dict[str, str] = {}
    for s in rest:
        erster_ts.setdefault(s["lauf"], s["ts"])
    stempel = [erster_ts[k] for k in erwartet]
    assert stempel == sorted(stempel), "Laufkennungen nicht in Zeitreihenfolge"
    for kennung, name in kopf["laeufe"].items():
        kurz = erster_ts[kennung].replace("-", "").replace(":", "")[:15]
        assert name == f"journal-{kurz}.jsonl", (kennung, name, kurz)


def test_das_redigierwerkzeug_laeuft_und_bestaetigt_die_aufzeichnung() -> None:
    """Bestaetigt durch Ausfuehrung, nicht durch Zusicherung.

    Mit ``betrieb/`` (nur auf dem Rechner, auf dem die Journale liegen) vergleicht das
    Werkzeug Byte fuer Byte; ohne ``betrieb/`` (frischer Klon) faehrt es die
    Eigenpruefung -- Kopf gegen Inhalt, Laufkennung an jedem Satz, keine
    unredigierten Muster -- und besteht nur, wenn die stimmt.
    """
    lauf = subprocess.run(
        [sys.executable, "tools/aufzeichnung_redigieren.py", "--pruefen"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    assert lauf.stdout.startswith("ok")


# =====================================================================
# Eichfaelle des Redigierwerkzeugs -- an erfundenen Journalen in tmp_path
# =====================================================================
KONTO_ROH = "12345678"
TICKET_ROH = "987654321"
ORDER_ROH = "555444333"
KENNUNG_ROH = "open-EURUSD-0123456789"
LAUF_ROH = "0123456789abcdef0123456789abcdef"
# Der Pfad ist Pruefgegenstand der Redaktion und wird darum zur Laufzeit gebaut:
# stuende er als Muster im Quelltext, meldete ihn der Geheimnis-Scan als Kontonamen
# in einer lebenden Datei (Katalog A5).
PFAD_ROH = (
    "C:"
    + chr(92)
    + "Users"
    + chr(92)
    + "jemand"
    + chr(92)
    + "repo"
    + chr(92)
    + "betrieb"
    + chr(92)
    + "STOP"
)


def _fake_journal(pfad: Path, *, minute: int, lauf: str | None) -> None:
    """Ein Journal mit allem, was die Redaktion treffen muss."""

    def ts(m: int) -> str:
        return f"2026-08-17T12:{minute + m:02d}:00+00:00"

    basis: dict[str, Any] = {} if lauf is None else {"lauf": lauf}
    saetze: list[dict[str, Any]] = [
        {
            "ts": ts(0),
            "art": "start",
            "konto": KONTO_ROH,
            "demo": True,
            "equity": "50000.0",
            "scharf": False,
            "symbole": ["EURUSD"],
        },
        {"ts": ts(1), "art": "signal", "symbol": "EURUSD", "signal": "LONG"},
        {
            "ts": ts(1),
            "art": "eroeffnungsversuch",
            "eroeffnet": True,
            "grund": None,
            "symbol": "EURUSD",
            "signal": "LONG",
            "client_order_id": KENNUNG_ROH,
            "order_id": ORDER_ROH,
            "schritte": [{"naht": "senden", "ok": True, "detail": f"t {TICKET_ROH}"}],
        },
        {
            "ts": ts(1),
            "art": "eroeffnet",
            "client_order_id": KENNUNG_ROH,
            "position_id": TICKET_ROH,
            "symbol": "EURUSD",
            "signal": "LONG",
            "volumen": "0.1",
            "einstiegspreis": "1.1",
        },
        {
            "ts": ts(2),
            "art": "takt",
            "nr": 1,
            "halt": False,
            "equity": "50000.0",
            "positionen": [
                {"position_id": TICKET_ROH, "symbol": "EURUSD", "volumen": "0.1"}
            ],
        },
        {"ts": ts(3), "art": "stoppdatei", "pfad": PFAD_ROH},
        {
            "ts": ts(4),
            "art": "ende",
            "equity": "50000.0",
            "equity_start": "50000.0",
            "offen_geblieben": [],
        },
    ]
    pfad.write_text(
        "\n".join(json.dumps({**s, **basis}) for s in saetze) + "\n", encoding="utf-8"
    )


def test_rot_die_redaktion_laesst_nichts_vom_original_durch(tmp_path: Path) -> None:
    """Roter Eichfall: Kontonummer, Ticket (auch in takt.positionen), Order-Kennung,
    Auftragskennung, Pfad und Hex-Laufkennung stehen im Journal -- und in der
    Aufzeichnung steht keines davon. Die Journale sind absichtlich so benannt, dass
    die Namensreihenfolge der Zeitreihenfolge widerspricht: LAUF-01 ist der
    FRUEHERE Lauf, nicht der alphabetisch erste."""
    _fake_journal(tmp_path / "journal-b.jsonl", minute=0, lauf=LAUF_ROH)
    _fake_journal(tmp_path / "journal-a.jsonl", minute=30, lauf=None)
    dateien = journale(tmp_path)
    assert [d.name for d in dateien] == ["journal-b.jsonl", "journal-a.jsonl"]
    ergebnis = redigiere(dateien)
    text = schreibform(ergebnis)
    for roh in (KONTO_ROH, TICKET_ROH, ORDER_ROH, KENNUNG_ROH, LAUF_ROH, "jemand"):
        assert roh not in text, f"{roh!r} steht im Klartext in der Aufzeichnung"
    assert pruefe_aufzeichnung(text) == []
    assert ergebnis.laeufe == {
        "LAUF-01": "journal-b.jsonl",
        "LAUF-02": "journal-a.jsonl",
    }
    saetze = [json.loads(z) for z in text.splitlines()[1:]]
    assert all(s["lauf"] in ("LAUF-01", "LAUF-02") for s in saetze)
    assert [s["lauf"] for s in saetze if s["art"] == "start"] == ["LAUF-01", "LAUF-02"]
    # Dieselbe Position heisst im Takt wie im eroeffnet-Satz gleich.
    takt = next(s for s in saetze if s["art"] == "takt")
    eroeffnet = next(s for s in saetze if s["art"] == "eroeffnet")
    assert takt["positionen"][0]["position_id"] == eroeffnet["position_id"]
    assert eroeffnet["position_id"] == "POSITION-01"
    assert next(s for s in saetze if s["art"] == "stoppdatei")["pfad"] == "<entfernt>"
    assert dict(ergebnis.weggelassen) == {"signal": 2}
    assert dict(ergebnis.felder_weggelassen) == {"schritte": 2}
    assert dict(ergebnis.felder_entfernt) == {"pfad": 2}
    assert ergebnis.felder_ersetzt == {
        "konto": 1,
        "order_id": 1,
        "position_id": 1,
        "client_order_id": 1,
        "lauf": 2,
    }


def test_rot_die_eigenpruefung_findet_einen_unredigierten_wert() -> None:
    """Roter Eichfall des Pruefers selbst: ein achtstelliger Wert in einem Feld, das
    die Redaktion nicht kennt, faellt an der Aufzeichnung auf -- am Text, nicht am
    Feldnamen. Und die Meldung nennt den Wert nicht."""
    ergebnis = redigiere([])
    ergebnis.laeufe = {"LAUF-01": "journal-x.jsonl"}
    ergebnis.saetze = [
        {"ts": "2026-08-17T12:00:00+00:00", "art": "start", "lauf": "LAUF-01"},
        {
            "ts": "2026-08-17T12:00:20+00:00",
            "art": "takt",
            "lauf": "LAUF-01",
            "ticket_roh": 12345678,
        },
    ]
    ergebnis.behalten.update({"start": 1, "takt": 1})
    ergebnis.felder_weggelassen.update({"schritte": 0})
    befunde = pruefe_aufzeichnung(schreibform(ergebnis))
    assert len(befunde) == 1, befunde
    assert "Ziffernfolge" in befunde[0] and "Zeile 3" in befunde[0]
    assert "12345678" not in befunde[0]


def test_rot_das_werkzeug_schreibt_keine_aufzeichnung_die_es_nicht_besteht(
    tmp_path: Path,
) -> None:
    """Fail-closed: ein Journal mit einem unbekannten Feld voller Ziffern ergibt
    KEINE Datei und Rueckgabe 1 -- nicht eine Datei mit Warnung."""
    _fake_journal(tmp_path / "journal-a.jsonl", minute=0, lauf=None)
    zeile = json.dumps(
        {
            "ts": "2026-08-17T12:05:00+00:00",
            "art": "takt",
            "nr": 2,
            "halt": False,
            "equity": "50000.0",
            "ticket_roh": 12345678,
        }
    )
    with (tmp_path / "journal-a.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(zeile + "\n")
    ziel = tmp_path / "aus" / "aufzeichnung.jsonl"
    lauf = subprocess.run(
        [
            sys.executable,
            "tools/aufzeichnung_redigieren.py",
            "--quelle",
            str(tmp_path),
            "--ziel",
            str(ziel),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "Eigenpruefung" in lauf.stderr
    assert not ziel.exists()


def test_gruen_und_rot_pruefen_gegen_die_journale(tmp_path: Path) -> None:
    """``--pruefen`` gruen bei Wortgleichheit, rot bei einer veraenderten Zeile; ohne
    Quelle faehrt es die Eigenpruefung und sagt das."""
    quelle = tmp_path / "betrieb"
    quelle.mkdir()
    _fake_journal(quelle / "journal-a.jsonl", minute=0, lauf=None)
    ziel = tmp_path / "aufzeichnung.jsonl"
    befehl = [
        sys.executable,
        "tools/aufzeichnung_redigieren.py",
        "--quelle",
        str(quelle),
        "--ziel",
        str(ziel),
    ]
    assert (
        subprocess.run(befehl, cwd=ROOT, capture_output=True, text=True).returncode == 0
    )
    gruen = subprocess.run(
        [*befehl, "--pruefen"], cwd=ROOT, capture_output=True, text=True
    )
    assert gruen.returncode == 0, gruen.stderr
    assert "wortgleich" in gruen.stdout

    ohne_quelle = subprocess.run(
        [*befehl[:3], str(tmp_path / "gibtsnicht"), "--ziel", str(ziel), "--pruefen"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert ohne_quelle.returncode == 0, ohne_quelle.stderr
    assert "eigengeprueft" in ohne_quelle.stdout
    assert "Abgleich gegen die Journale ist hier nicht moeglich" in ohne_quelle.stdout

    # Rot: eine Zeile weniger -- der Kopf zaehlt noch die alte Zahl.
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    ziel.write_text("\n".join(zeilen[:-1]) + "\n", encoding="utf-8")
    rot = subprocess.run(
        [*befehl, "--pruefen"], cwd=ROOT, capture_output=True, text=True
    )
    assert rot.returncode == 1
    assert "Eigenpruefung nicht" in rot.stderr
    # Rot ohne Quelle ebenso -- die Eigenpruefung braucht die Journale nicht.
    rot2 = subprocess.run(
        [*befehl[:3], str(tmp_path / "gibtsnicht"), "--ziel", str(ziel), "--pruefen"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert rot2.returncode == 1
