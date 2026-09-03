"""Die Kacheln der Oberflaeche -- was der Betreiber wirklich abliest.

WARUM DIESE DATEI NEBEN ``test_oberflaeche_seite.py`` STEHT
-----------------------------------------------------------
Die vorhandene Datei prueft, dass die Seite **entsteht**: ohne Terminal, ohne Journal,
mit defektem Journal. Ungeprueft blieb, was auf ihr **steht**. Das ist die
gefaehrlichere Haelfte: eine Seite, die gar nicht baut, faellt sofort auf. Eine
Kachel, die eine falsche Zahl zeigt, faellt nie auf -- sie sieht aus wie eine Messung.

DER BEFUND, DER DIESE DATEI AUSGELOEST HAT
-------------------------------------------
Der Trefferanteil lief ueber ``ergebnis_bps``, also nur ueber Trades mit **zwei
gemessenen Preisen**. Ein broker-seitiger Schluss hat keinen Fuellpreis; er traegt
sein Ergebnis in Kontowaehrung. Er fiel damit aus der Kachel heraus -- und weil
broker-seitige Schluesse ueberwiegend Stop-Outs sind, fielen genau die Verlierer
heraus. Das ist derselbe blinde Fleck, gegen den ``betrieb/journal.py`` mit ``bilanz``
gebaut wurde und den ``betrieb_auswerten.py`` laengst richtig zeigt: die Oberflaeche
war die dritte, nicht angeschlossene Umsetzung derselben Einteilung, und sie zeigte
als einzige zu gut.

WAS HIER BEWUSST NICHT GEPRUEFT WIRD
-------------------------------------
Nichts, was ein MT5-Terminal braucht. Die Journale werden als echte JSONL-Dateien
geschrieben und ueber den echten Leser (``betrieb/journal.py``) eingelesen -- eine
Abkuerzung an dieser Stelle prueefte ein Format, das der Schreiber nie erzeugt.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.betrieb.journal import lies_journal
from mt5_trading_ai.venue.protocol import AccountState, OrderSide, Position, Quote
from tools import oberflaeche as OB

T0 = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


# --- Journale bauen --------------------------------------------------------
def _schreib(
    tmp_path: Path, *saetze: dict[str, Any], name: str = "journal-a.jsonl"
) -> Path:
    """Ein echtes Journal aus echten Saetzen. ``ts`` laeuft je Satz eine Minute weiter."""
    ziel = tmp_path / name
    zeilen = []
    for i, satz in enumerate(saetze):
        zeile = {
            "ts": (T0 + timedelta(minutes=i)).isoformat(timespec="seconds"),
            "lauf": "lauf-t",
            "version": "abc1234",
        }
        zeile.update(satz)
        zeilen.append(json.dumps(zeile, ensure_ascii=False))
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return ziel


def _takt(nr: int, equity: str, *, halt: bool = False) -> dict[str, Any]:
    return {"art": "takt", "nr": nr, "equity": equity, "halt": halt}


#: Ein Trade mit ZWEI gemessenen Preisen -- er gewinnt.
#: Von Hand: (1,10110 - 1,10000) / 1,10000 * 10 000 = +10,00 bp, Kaufrichtung.
GEWINNER: tuple[dict[str, Any], ...] = (
    {
        "art": "eroeffnet",
        "symbol": "EURUSD",
        "signal": "LONG",
        "position_id": "P1",
        "volumen": "0.10",
        "einstiegspreis": "1.10000",
        "seit": T0.isoformat(timespec="seconds"),
    },
    {
        "art": "geschlossen",
        "symbol": "EURUSD",
        "grund": "signalwechsel",
        "position_id": "P1",
        "volumen": "0.10",
        "war_kauf": True,
        "einstiegspreis": "1.10000",
        "ausstiegspreis": "1.10110",
        "ergebnis_geld": "11.00",
        "ergebnis_geld_waehrung": "EUR",
        "ergebnis_geld_quelle": "zuletzt_beobachtet",
    },
)

#: Ein Stop-Out. KEIN Fuellpreis -- nur der zuletzt beobachtete Buchwert, und der ist
#: negativ. Genau dieser Trade fehlte in der Kachel.
STOP_OUT: tuple[dict[str, Any], ...] = (
    {
        "art": "eroeffnet",
        "symbol": "XAUUSD",
        "signal": "LONG",
        "position_id": "P2",
        "volumen": "0.01",
        "einstiegspreis": "4415.18",
        "seit": T0.isoformat(timespec="seconds"),
    },
    {
        "art": "vom_broker_geschlossen",
        "symbol": "XAUUSD",
        "position_id": "P2",
        "volumen": "0.01",
        "war_kauf": True,
        "einstiegspreis": "4415.18",
        "ergebnis_geld": "-2.68",
        "ergebnis_geld_waehrung": "EUR",
        "ergebnis_geld_quelle": "zuletzt_beobachtet",
    },
)


def _stand(pfad: Path, **zusatz: Any) -> dict[str, Any]:
    lauf = lies_journal(pfad)
    stand: dict[str, Any] = {
        "jetzt": T0,
        "fehler": None,
        "lauf": lauf,
        "alle_laeufe": [lauf],
    }
    stand.update(zusatz)
    return stand


# --- Der Trefferanteil -----------------------------------------------------
def test_der_trefferanteil_zaehlt_den_stop_out_mit(tmp_path: Path) -> None:
    """DER EICHFALL. Gegen die alte Fassung stand hier ``100 %``.

    Von Hand: zwei geschlossene Trades. Der eine hat beide Preise und gewinnt
    (+10,00 bp), der andere ist ein Stop-Out ohne Fuellpreis und verliert (-2,68 EUR
    Buchwert). Beurteilbar sind **beide**, gewonnen hat **einer** -- 1/2 = 50 %.

    Die alte Fassung rechnete ``rechenbar = [t.ergebnis_bps for t ...]``, sah also nur
    den Gewinner und zeigte ``100 % aus 1 rechenbaren Trades``. Ein Betreiber, der auf
    diese Kachel sieht, laese seinen Verlierer nicht -- und zwar dauerhaft, weil
    Stop-Outs ueberwiegend die Verlierer sind.

    Mutationsprobe: den Anteil wieder ueber ``b.preis`` gerechnet -- dieser Fall
    faellt mit ``100 %`` statt ``50 %``.
    """
    pfad = _schreib(tmp_path, *GEWINNER, *STOP_OUT, _takt(1, "50000"))
    aus = OB._kennzahlen(_stand(pfad))
    assert ">50 %<" in aus
    assert "aus 2 beurteilbaren Trades, 1 davon ohne Preis" in aus


def test_ohne_beurteilbaren_trade_steht_ein_strich(tmp_path: Path) -> None:
    """Kein Trade heisst UNBEKANNT und nicht null.

    Eine geratene Null zoege jeden Trefferanteil nach unten und saehe aus wie eine
    Messung. Der Strich sagt, dass nichts dasteht.
    """
    pfad = _schreib(tmp_path, _takt(1, "50000"))
    aus = OB._kennzahlen(_stand(pfad))
    assert "aus 0 beurteilbaren Trades" in aus
    assert ">—<" in aus


def test_der_schlechteste_trade_bleibt_am_gemessenen_preis(tmp_path: Path) -> None:
    """Die Kachel steht in Basispunkten -- ein Geldbetrag gehoert nicht hinein.

    Der Stop-Out traegt -2,68 EUR. Waere er hier mitgezaehlt, stuende ``-2.68 bp`` da,
    und das ist keine Preisdifferenz, sondern eine Kontowaehrung mit falschem Etikett.
    Uebrig bleibt der einzige gemessene Preis: +10,00 bp.
    """
    pfad = _schreib(tmp_path, *GEWINNER, *STOP_OUT, _takt(1, "50000"))
    aus = OB._kennzahlen(_stand(pfad))
    assert "+10.00 bp" in aus


def test_der_drawdown_misst_vom_laufenden_hoechststand(tmp_path: Path) -> None:
    """Von Hand: 100 -> 110 -> 99. Der Hoechststand ist 110.

    Der Ruecksetzer ist ``(99 - 110) / 110 * 100 = -10,000 %``. Gegen den ANFANGSWERT
    gerechnet waeren es nur -1 %, und genau das ist der Fehler, den ein Drawdown-Mass
    nicht machen darf: er misst vom Gipfel, nicht vom Start.

    Mutationsprobe: die Spitze auf dem Anfangswert eingefroren -- dann steht hier
    ``-1.000 %``.
    """
    pfad = _schreib(tmp_path, _takt(1, "100"), _takt(2, "110"), _takt(3, "99"))
    aus = OB._kennzahlen(_stand(pfad))
    assert "-10.000 %" in aus
    assert 'class="wert krit"' in aus, "Ein Drawdown ueber 1 % muss auffallen"


def test_ein_kleiner_ruecksetzer_faerbt_nicht_rot(tmp_path: Path) -> None:
    """Die Gegenprobe -- sonst waere die Farbe eine Dauerwarnung und damit blind.

    Von Hand: 100 -> 110 -> 109,45 sind ``(109,45 - 110) / 110 * 100 = -0,500 %``.
    """
    pfad = _schreib(tmp_path, _takt(1, "100"), _takt(2, "110"), _takt(3, "109.45"))
    aus = OB._kennzahlen(_stand(pfad))
    assert "-0.500 %" in aus
    assert 'class="wert krit">-0.500' not in aus


def test_die_zeit_im_halt_wird_ausgezaehlt(tmp_path: Path) -> None:
    """Von Hand: vier Takte, einer davon im Halt -> 1/4 = 25 %.

    Und: jeder Halt faerbt rot. Ein einziger Takt im Halt heisst, dass die Maschine
    eine Zeit lang nicht handeln konnte -- das gehoert nicht in gruen.
    """
    pfad = _schreib(
        tmp_path,
        _takt(1, "100"),
        _takt(2, "100", halt=True),
        _takt(3, "100"),
        _takt(4, "100"),
    )
    aus = OB._kennzahlen(_stand(pfad))
    assert ">25 %<" in aus
    assert "von 4 Takten" in aus
    assert 'class="wert krit">25 %' in aus


def test_ohne_halt_bleibt_die_kachel_gruen(tmp_path: Path) -> None:
    pfad = _schreib(tmp_path, _takt(1, "100"), _takt(2, "100"))
    aus = OB._kennzahlen(_stand(pfad))
    assert 'class="wert gut">0 %' in aus


def _mit_preis(nummer: int, symbol: str) -> tuple[dict[str, Any], ...]:
    """Ein Trade mit ZWEI gemessenen Preisen -- er gehoert in den Preis-Topf.

    Gleiche Bauart wie ``GEWINNER``, nur mit eigener Kennung und eigenem Symbol, damit
    mehrere davon nebeneinander stehen koennen.
    """
    return (
        {
            "art": "eroeffnet",
            "symbol": symbol,
            "signal": "LONG",
            "position_id": f"Q{nummer}",
            "volumen": "0.10",
            "einstiegspreis": "1.10000",
            "seit": T0.isoformat(timespec="seconds"),
        },
        {
            "art": "geschlossen",
            "symbol": symbol,
            "grund": "signalwechsel",
            "position_id": f"Q{nummer}",
            "volumen": "0.10",
            "war_kauf": True,
            "einstiegspreis": "1.10000",
            "ausstiegspreis": "1.10110",
            "ergebnis_geld": "11.00",
            "ergebnis_geld_waehrung": "EUR",
            "ergebnis_geld_quelle": "zuletzt_beobachtet",
        },
    )


def _stummer(nummer: int, symbol: str) -> tuple[dict[str, Any], ...]:
    """Ein Schluss OHNE jede Zahl -- weder Fuellpreis noch Buchwert.

    Er bleibt UNBEKANNT und geht in keine einzige Kennzahl ein. Genau er sah in der
    alten Fassung aus wie ein Stop-Out.
    """
    return (
        {
            "art": "eroeffnet",
            "symbol": symbol,
            "signal": "SHORT",
            "position_id": f"S{nummer}",
            "volumen": "0.1",
            "seit": T0.isoformat(timespec="seconds"),
        },
        {
            "art": "geschlossen",
            "symbol": symbol,
            "grund": "lauf_beendet",
            "position_id": f"S{nummer}",
            "volumen": "0.1",
            "war_kauf": False,
        },
    )


def test_der_betriebsabschnitt_trennt_die_toepfe(tmp_path: Path) -> None:
    """Dieselbe Einteilung wie in ``betrieb_auswerten.py`` -- und sie steht daneben.

    Die alte Fassung zaehlte nur ``t.vollstaendig`` und schrieb ``1 rechenbar`` -- der
    stumme Trade und der Stop-Out sahen darin gleich aus, obwohl der eine beurteilbar
    ist und der andere nicht.

    DIE DREI TOEPFE HABEN ABSICHTLICH VERSCHIEDENE MAECHTIGKEITEN. Der Fall stand
    vorher auf je genau einem Trade je Topf und schrieb ``1 · 1 · 1``: eine
    Vertauschung zweier Toepfe -- etwa ``{len(b.stumm)} stumm`` zu
    ``{len(b.nur_geld)} stumm`` -- erzeugte damit eine ZEICHENGLEICHE Ausgabe und blieb
    unbemerkt. Ausgerechnet der Fall, der die Trennung beweisen soll, konnte seine
    eigenen Toepfe nicht auseinanderhalten.

    Von Hand: zwei Trades mit beiden Preisen, ein Stop-Out mit Buchwert ohne Fuellpreis,
    drei Schluesse ohne jede Zahl. Also ``2 mit Preis · 1 nur Geld · 3 stumm``, Summe
    sechs geschlossene Trades. Die drei Zahlen sind paarweise verschieden; jede
    Vertauschung faellt auf.
    """
    pfad = _schreib(
        tmp_path,
        *GEWINNER,
        *_mit_preis(1, "GBPUSD"),
        *STOP_OUT,
        *_stummer(1, "DE40"),
        *_stummer(2, "USDJPY"),
        *_stummer(3, "NAS100"),
        _takt(1, "50000"),
    )
    aus = OB._abschnitt_lauf(_stand(pfad))
    assert "2 mit Preis" in aus
    assert "1 nur Geld" in aus
    assert "3 stumm" in aus
    # Die Kopfzahl der Kachel: die drei Toepfe teilen die geschlossenen Trades
    # vollstaendig auf, 2 + 1 + 3 = 6. Ohne sie liesse sich ein Topf verdoppeln, ohne
    # dass es auffiele.
    assert '<span class="wert">6</span>' in aus


# --- Woran Eroeffnungen scheiterten ---------------------------------------
def _versuch(symbol: str, schritte: list[dict[str, Any]], grund: str) -> dict[str, Any]:
    return {
        "art": "eroeffnungsversuch",
        "symbol": symbol,
        "signal": "LONG",
        "eroeffnet": False,
        "grund": grund,
        "schritte": schritte,
    }


def test_die_ablehnungen_werden_je_naht_gezaehlt(tmp_path: Path) -> None:
    """Von Hand: zweimal dieselbe Naht, einmal eine andere -> ``2×`` und ``1×``.

    Ohne diese Zaehlung sieht der Betreiber nur, DASS nichts eroeffnet wurde. Die
    Frage, die er beantworten muss, ist aber immer dieselbe: haengt es an der
    Zulassung (dann ist es erwartet) oder am Kostentor (dann ist etwas anders als
    gedacht)?
    """
    zul = [{"naht": "zulassung", "ok": False, "detail": "nicht erfuellt"}]
    kost = [
        {"naht": "daten-tor", "ok": True, "detail": "ref=1.1"},
        {"naht": "kostentor", "ok": False, "detail": "zu teuer"},
    ]
    pfad = _schreib(
        tmp_path,
        _versuch("EURUSD", zul, "strategy_not_admitted"),
        _versuch("XAUUSD", zul, "strategy_not_admitted"),
        _versuch("DE40", kost, "cost_gate_failed"),
        _takt(1, "50000"),
    )
    aus = OB._abschnitt_lauf(_stand(pfad))
    assert "2×" in aus
    assert "zulassung — strategy_not_admitted" in aus
    assert "1×" in aus
    assert "kostentor — cost_gate_failed" in aus


def test_genannt_wird_die_LETZTE_gerissene_naht(tmp_path: Path) -> None:
    """Die Kette laeuft von vorn nach hinten -- die letzte Ablehnung ist die, an der
    sie wirklich stehen blieb.

    Hier reissen zwei Naehte. Wuerde die erste genannt, schickte die Anzeige den
    Betreiber an die falsche Stelle -- und zwar an eine, die er womoeglich gerade
    repariert hat.

    Mutationsprobe: ``reversed(...)`` entfernt -- dann steht ``frueh`` statt
    ``spaet`` da, und dieser Fall faellt.
    """
    zwei = [
        {"naht": "frueh", "ok": False, "detail": "a"},
        {"naht": "spaet", "ok": False, "detail": "b"},
    ]
    pfad = _schreib(tmp_path, _versuch("EURUSD", zwei, "abgelehnt"), _takt(1, "50000"))
    aus = OB._abschnitt_lauf(_stand(pfad))
    assert "spaet — abgelehnt" in aus
    assert "frueh — abgelehnt" not in aus


def test_ohne_ablehnung_steht_es_da(tmp_path: Path) -> None:
    """Eine leere Tabelle ist keine Auskunft. „keine Ablehnungen" ist eine."""
    pfad = _schreib(tmp_path, _takt(1, "50000"))
    assert "keine Ablehnungen" in OB._abschnitt_lauf(_stand(pfad))


# --- Die Orderkette, Naht fuer Naht ---------------------------------------
def test_die_sperrenliste_zeigt_den_JUENGSTEN_durchlauf(tmp_path: Path) -> None:
    """Eine alte Checkliste ist schlimmer als keine: sie beschreibt einen Zustand,
    den es nicht mehr gibt.

    Zwei Durchlaeufe, der zweite ist der aktuelle -- gezeigt wird er.
    """
    alt = [{"naht": "zulassung", "ok": False, "detail": "alte-lage"}]
    neu = [
        {"naht": "zulassung", "ok": True, "detail": "neue-lage"},
        {"naht": "kostentor", "ok": False, "detail": "zu teuer"},
    ]
    pfad = _schreib(
        tmp_path,
        _versuch("EURUSD", alt, "a"),
        _versuch("XAUUSD", neu, "b"),
        _takt(1, "50000"),
    )
    aus = OB._abschnitt_sperren(_stand(pfad))
    assert "neue-lage" in aus
    assert "alte-lage" not in aus
    assert "XAUUSD" in aus


def test_eine_gerissene_naht_heisst_HALT_und_nicht_OK(tmp_path: Path) -> None:
    """Die Marke ist die eigentliche Auskunft der Zeile.

    Mutationsprobe: die Bedingung ``x['ok']`` verneint -- dann steht ueber der
    bestandenen Naht HALT und ueber der gerissenen OK. Die Seite saehe voll aus und
    behauptete das Gegenteil dessen, was passiert ist.
    """
    schritte = [
        {"naht": "zulassung", "ok": True, "detail": "bestanden"},
        {"naht": "kostentor", "ok": False, "detail": "zu teuer"},
    ]
    pfad = _schreib(
        tmp_path, _versuch("EURUSD", schritte, "cost_gate"), _takt(1, "50000")
    )
    aus = OB._abschnitt_sperren(_stand(pfad))
    assert 'class="marke gut">\n              OK' in aus
    assert 'class="marke krit">\n              HALT' in aus


def test_ohne_durchlauf_sagt_die_seite_das(tmp_path: Path) -> None:
    pfad = _schreib(tmp_path, _takt(1, "50000"))
    assert "Noch kein Durchlauf" in OB._abschnitt_sperren(_stand(pfad))


# --- Die Trade-Tabelle -----------------------------------------------------
def test_ein_verkauf_gewinnt_bei_fallendem_kurs(tmp_path: Path) -> None:
    """Von Hand: Einstieg 1,10000, Ausstieg 1,09890, VERKAUF.

    Roh sind das ``(1,09890 - 1,10000) / 1,10000 * 10 000 = -10,00 bp``; fuer einen
    Verkauf dreht das Vorzeichen: ``+10,00 bp``. Wer die Richtung nicht beruecksichtigt,
    baut sich eine Statistik, in der jeder Verkauf falsch herum zaehlt -- und bei einer
    Trendfolge ist ungefaehr die Haelfte aller Trades ein Verkauf.

    Mutationsprobe: das ``-roh`` in ``Trade.ergebnis_bps`` durch ``roh`` ersetzt --
    dieser Fall faellt mit ``-10.00 bp``.
    """
    saetze = (
        {
            "art": "eroeffnet",
            "symbol": "EURUSD",
            "signal": "SHORT",
            "position_id": "P9",
            "volumen": "0.10",
            "einstiegspreis": "1.10000",
            "seit": T0.isoformat(timespec="seconds"),
        },
        {
            "art": "geschlossen",
            "symbol": "EURUSD",
            "grund": "signalwechsel",
            "position_id": "P9",
            "volumen": "0.10",
            "war_kauf": False,
            "einstiegspreis": "1.10000",
            "ausstiegspreis": "1.09890",
        },
    )
    pfad = _schreib(tmp_path, *saetze)
    aus = OB._abschnitt_trades(lies_journal(pfad).trades())
    assert "+10.00 bp" in aus
    assert "SELL" in aus


def test_ein_trade_ohne_ausstiegspreis_heisst_unvollstaendig_und_nicht_null(
    tmp_path: Path,
) -> None:
    """„Unvollstaendig" heisst, dass ein Preis fehlt; es heisst nicht null.

    Eine gezeigte Null waere die schmeichelnde Richtung: sie zoege jede Bestenliste
    zur Mitte, und man saehe der Zahl nicht an, dass sie geraten ist.
    """
    pfad = _schreib(tmp_path, *STOP_OUT)
    aus = OB._abschnitt_trades(lies_journal(pfad).trades())
    assert "unvollständig" in aus
    assert "0.00 bp" not in aus


# --- Kurse gegen das Kostenmodell -----------------------------------------
def _preis(gemessen: str | None, modell: str | None) -> dict[str, Any]:
    return {
        "symbol": "EURUSD",
        "bid": Decimal("1.1000"),
        "ask": Decimal("1.1002"),
        "gemessen": None if gemessen is None else Decimal(gemessen),
        "modell": None if modell is None else Decimal(modell),
        "ts": T0,
    }


def test_ein_spread_auf_der_schwelle_gilt_noch_als_passend() -> None:
    """Von Hand: gemessen 2,4 bp gegen Modell 2,0 bp sind genau ``1,2x`` -- gruen.

    Die Schwelle ist die Stelle, an der die Anzeige umschlaegt, und sie gehoert
    geprueft: ein Spread, der dauerhaft ueber dem Modell liegt, entwertet das
    Kostentor, ohne dass irgendwo ein Fehler auftaucht.
    """
    aus = OB._abschnitt_preise({"preise": [_preis("2.4", "2.0")]})
    assert "1.2× Modell" in aus
    assert "class='gut'" in aus


def test_ein_spread_ueber_der_schwelle_wird_gewarnt() -> None:
    """Von Hand: 2,6 gegen 2,0 sind ``1,3x`` -- und das ist eine Warnung.

    Mutationsprobe: ``faktor <= 1.2`` zu ``faktor <= 1.5`` geweitet -- dieser Fall
    faellt. Die Richtung ist Absicht: ein zu enger Melder loest oefter aus, ein zu
    weiter gar nicht mehr.
    """
    aus = OB._abschnitt_preise({"preise": [_preis("2.6", "2.0")]})
    assert "1.3× Modell" in aus
    assert "class='warn'" in aus


def test_ohne_kostenzeile_wird_kein_urteil_erfunden() -> None:
    """Kein Modellwert heisst: die Frage ist nicht beantwortbar, nicht „passt"."""
    aus = OB._abschnitt_preise({"preise": [_preis("2.6", None)]})
    assert "keine Kostenzeile" in aus
    assert "Modell</span>" not in aus


def test_ein_kursfehler_steht_in_der_zeile() -> None:
    aus = OB._abschnitt_preise(
        {"preise": [{"symbol": "NVDA", "fehler": "symbol_unknown"}]}
    )
    assert "symbol_unknown" in aus


# --- Konto und Kursfrische -------------------------------------------------
def _konto(*, demo: bool = True) -> AccountState:
    return AccountState(
        account_id="DEMO-1",
        currency="EUR",
        balance=Decimal("50000"),
        equity=Decimal("50000"),
        margin_used=Decimal("0"),
        margin_free=Decimal("50000"),
        is_demo=demo,
        ts=T0,
    )


def test_die_frischekachel_kann_rot_werden(tmp_path: Path) -> None:
    """DER Grund, warum diese Kachel ueberhaupt am Kursstempel haengt.

    Die erste Fassung rechnete ``snapshot_ts=jetzt, now=jetzt``. Das Alter war per
    Konstruktion null, die Kachel stand IMMER auf gruen -- eine Sicherheitsanzeige,
    die nicht rot werden kann, ist schlimmer als keine.

    Von Hand: der juengste Kursstempel ist 60 s alt, die Grenze steht bei 5 s
    (``MAX_SNAPSHOT_AGE``). Also nicht bewertbar, Grund ``snapshot_stale``.
    """
    stand = {
        "jetzt": T0,
        "konto": _konto(),
        "preise": [{"symbol": "EURUSD", "ts": T0 - timedelta(seconds=60)}],
    }
    aus = OB._abschnitt_konto(stand)
    assert "snapshot_stale" in aus
    assert "60.0 s alt" in aus
    assert "Grenze 5 s" in aus


def test_ein_frischer_kurs_faerbt_die_kachel_gruen() -> None:
    """Die Gegenprobe -- sonst waere die Kachel eine Dauerwarnung.

    Von Hand: ein Stempel von vor einer Sekunde liegt unter der Grenze von fuenf.
    """
    stand = {
        "jetzt": T0,
        "konto": _konto(),
        "preise": [{"symbol": "EURUSD", "ts": T0 - timedelta(seconds=1)}],
    }
    aus = OB._abschnitt_konto(stand)
    assert ">\n          ok</span>" in aus
    assert "1.0 s alt" in aus


def test_ohne_jeden_kursstempel_ist_die_frische_nicht_bewertbar() -> None:
    """Fail-closed: keine Auskunft ist keine gute Auskunft.

    Ohne Kursstempel gibt es kein Lebenszeichen vom Broker. Die Kachel meldet
    ``session_not_connected`` -- und nicht etwa das Alter des Kontoschnappschusses,
    denn den setzt ``account()`` selbst auf die eigene Uhr.
    """
    aus = OB._abschnitt_konto({"jetzt": T0, "konto": _konto(), "preise": []})
    assert "session_not_connected" in aus


def test_ein_live_konto_wird_rot_gezeigt() -> None:
    """Die eine Zahl, die der Betreiber im Zweifel zuerst sucht.

    Mutationsprobe: die Bedingung ``konto.is_demo`` verneint -- dann stuende ueber
    einem Demokonto ``LIVE-KONTO`` in rot und ueber einem Livekonto ``Demokonto`` in
    gruen. Das ist die Anzeige, an der man sich in genau die falsche Sicherheit
    wiegt.
    """
    live = OB._abschnitt_konto({"jetzt": T0, "konto": _konto(demo=False), "preise": []})
    assert 'class="wert krit">LIVE-KONTO' in live
    demo = OB._abschnitt_konto({"jetzt": T0, "konto": _konto(), "preise": []})
    assert 'class="wert gut">Demokonto' in demo


# --- Offene Positionen -----------------------------------------------------
def test_das_alter_einer_position_wird_in_stunden_gezeigt() -> None:
    """Von Hand: geoeffnet 2 h 30 min vor der Renderzeit -> ``2.50 h``.

    Das Alter entscheidet ueber die Hoechsthaltedauer im Betriebslauf. Eine Anzeige,
    die hier danebenliegt, verdeckt genau den Fall, in dem eine Position zu lange
    steht -- und der Befund aus ``_lage_lesen`` (real 0,77 h, gerechnet -2,23 h) war
    genau dieser.
    """
    pos = Position(
        venue_position_id="1",
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=Decimal("0.01"),
        entry_price=Decimal("4415.18"),
        stop_loss=Decimal("4400.00"),
        take_profit=None,
        opened_at=T0 - timedelta(hours=2, minutes=30),
        unrealised_pnl=Decimal("-2.68"),
        swap_accrued=Decimal("-0.11"),
    )
    aus = OB._abschnitt_positionen({"jetzt": T0, "positionen": (pos,)})
    assert "2.50 h" in aus
    assert "-2.68" in aus
    assert 'class="zahl krit"' in aus, "Ein Buchverlust gehoert nicht in gruen"


def test_ohne_position_sagt_die_seite_dass_das_konto_flach_ist() -> None:
    """„Keine Zeilen" und „flach" sind fuer den Leser dasselbe -- fuer die Maschine
    nicht. Der Satz macht die leere Tabelle zur Aussage."""
    assert "flach" in OB._abschnitt_positionen({"jetzt": T0, "positionen": ()})


# --- Welcher Lauf gezeigt wird --------------------------------------------
def test_der_laufende_betrieb_schlaegt_den_zuletzt_begonnenen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein kurzer Testlauf nach dem Start des Dauerbetriebs waere sonst der neueste.

    Von Hand: Lauf A beginnt um 12:00 und laeuft noch (kein ``ende``), Lauf B beginnt
    um 12:01 und ist beendet. Nach Startzeit sortiert ist B der letzte -- gezeigt wird
    trotzdem A, weil er laeuft.

    Mutationsprobe: ``return laeufe[-1]`` ohne die Vorauswahl -- dieser Fall faellt,
    und die Seite zeigte einen Lauf mit einem einzigen Takt statt des Betriebs, der
    gerade handelt.
    """
    a = tmp_path / "journal-a.jsonl"
    a.write_text(
        json.dumps({"ts": T0.isoformat(), "art": "takt", "lauf": "A", "equity": "1"})
        + "\n",
        encoding="utf-8",
    )
    b = tmp_path / "journal-b.jsonl"
    b.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": (T0 + timedelta(minutes=1)).isoformat(),
                        "art": "takt",
                        "lauf": "B",
                        "equity": "1",
                    }
                ),
                json.dumps(
                    {
                        "ts": (T0 + timedelta(minutes=2)).isoformat(),
                        "art": "ende",
                        "lauf": "B",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(OB, "JOURNALE", tmp_path)
    lauf = OB._neuester_lauf()
    assert lauf is not None
    assert lauf.pfad.name == "journal-a.jsonl"


def test_ohne_journale_gibt_es_keinen_lauf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OB, "JOURNALE", tmp_path)
    assert OB._neuester_lauf() is None


# --- Der gemessene Spread --------------------------------------------------
class LeseVenue:
    """Ein Handelsplatz, der nur die drei lesenden Auskuenfte kennt."""

    def __init__(self, *, bid: str, ask: str) -> None:
        self.bid, self.ask = Decimal(bid), Decimal(ask)

    def get_account(self) -> AccountState:
        return _konto()

    def get_positions(self) -> tuple[Position, ...]:
        return ()

    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, ts=T0, bid=self.bid, ask=self.ask)


def test_der_gemessene_spread_kommt_in_basispunkten_der_mitte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Von Hand: Bid 99,99 / Ask 100,01. Mitte 100,00, Spanne 0,02.

    ``0,02 / 100,00 * 10 000 = 2,00 bp``. Das ist die Zahl, die neben dem Modellwert
    steht und ueber die Bewertung entscheidet -- sie muss auf der MITTE stehen und
    nicht etwa auf dem Bid, sonst laege sie systematisch zu hoch.
    """
    monkeypatch.setattr(OB, "JOURNALE", tmp_path)
    stand = OB._lage(LeseVenue(bid="99.99", ask="100.01"))
    assert stand["fehler"] is None
    gemessene = {p["gemessen"] for p in stand["preise"] if "gemessen" in p}
    assert gemessene == {Decimal("2.00")}


def test_ein_defektes_journal_wird_gemeldet_und_nicht_verschluckt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine unlesbare Zeile ist ein Defekt, kein leeres Journal.

    Ohne diesen Fang meldete die Seite „Kein Journal gefunden" -- der Betreiber
    saehe eine harmlose Leermeldung ueber einem kaputten Protokoll.
    """
    (tmp_path / "journal-x.jsonl").write_text("{kein json\n", encoding="utf-8")
    monkeypatch.setattr(OB, "JOURNALE", tmp_path)
    stand = OB._lage(LeseVenue(bid="99.99", ask="100.01"))
    assert stand["lauf"] is None
    assert "journal-x.jsonl" in stand["journalfehler"]
    assert stand["journalfehler"] in OB.seite(stand)


# --- Der Stopp-Knopf: die einzige Handlung der Seite -----------------------
class FakeGriff(OB.Griff):
    """Ein Griff ohne Netz. ``BaseHTTPRequestHandler.__init__`` bedient sonst sofort
    einen Socket -- hier wird nur der Rumpf gebraucht.
    """

    # Absichtlich ohne ``super().__init__`` -- der Rumpf reicht.
    def __init__(self, pfad: str, koerper: bytes, token: str) -> None:
        self.path = pfad
        self.headers = {"Content-Length": str(len(koerper))}  # type: ignore[assignment]
        self.rfile = io.BytesIO(koerper)  # type: ignore[assignment]
        self.wfile = io.BytesIO()  # type: ignore[assignment]
        self.token = token
        self.fehler: list[tuple[int, str | None]] = []
        self.antworten: list[int] = []
        self.kopfzeilen: list[tuple[str, str]] = []

    def send_error(
        self, code: int, message: str | None = None, explain: str | None = None
    ) -> None:
        self.fehler.append((code, message))

    def send_response(self, code: int, message: str | None = None) -> None:
        self.antworten.append(code)

    def send_header(self, name: str, wert: str) -> None:
        self.kopfzeilen.append((name, wert))

    def end_headers(self) -> None:
        return None


@pytest.fixture
def stoppdatei(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ziel = tmp_path / "STOP"
    monkeypatch.setattr(OB, "STOPPDATEI", ziel)
    return ziel


def test_ein_falsches_token_legt_keine_stoppdatei_an(stoppdatei: Path) -> None:
    """DER Sicherheitsfall dieser Seite.

    Die Seite haengt auf ``127.0.0.1``, und localhost ist fuer jede andere Seite im
    selben Browser erreichbar. Ohne Tokenpruefung koennte ein verstecktes Formular auf
    einer fremden Seite den laufenden Betrieb beenden -- und der stellt dabei alle
    Positionen glatt.

    Mutationsprobe: die Tokenpruefung entfernt -- dann entsteht die Datei, und dieser
    Fall faellt.
    """
    griff = FakeGriff("/stopp", b"token=falsch", "geheim")
    griff.do_POST()
    assert griff.fehler and griff.fehler[0][0] == 403
    assert not stoppdatei.exists()
    assert griff.antworten == []


def test_ein_fehlendes_token_wird_genauso_abgewiesen(stoppdatei: Path) -> None:
    """Ein leeres Feld darf nicht besser dastehen als ein falsches.

    Mutationsprobe: der Rueckfall ``(felder.get("token") or [""])[0]`` zu
    ``felder.get("token")`` gemacht -- dann verglichen sich ``None`` und der Token,
    was zufaellig auch abweist; auf ein leeres Token als Vorgabe umgestellt faellt
    dieser Fall dagegen sofort.
    """
    griff = FakeGriff("/stopp", b"", "geheim")
    griff.do_POST()
    assert griff.fehler and griff.fehler[0][0] == 403
    assert not stoppdatei.exists()


def test_mit_dem_richtigen_token_entsteht_die_stoppdatei(stoppdatei: Path) -> None:
    """Die Gegenprobe -- ein Knopf, der nie wirkt, ist kein Not-Halt.

    Der Betriebslauf sieht die Datei im naechsten Takt, stellt glatt und beendet sich.
    Danach schickt die Seite den Browser mit 303 zurueck auf ``/``, damit ein
    Neuladen den Knopf nicht ein zweites Mal drueckt.
    """
    griff = FakeGriff("/stopp", b"token=geheim", "geheim")
    griff.do_POST()
    assert griff.fehler == []
    assert griff.antworten == [303]
    assert ("Location", "/") in griff.kopfzeilen
    assert stoppdatei.is_file()
    assert "Oberflaeche" in stoppdatei.read_text(encoding="utf-8")


def test_ein_post_auf_einen_anderen_weg_wird_abgewiesen(stoppdatei: Path) -> None:
    """Es gibt genau einen schreibenden Weg. Jeder andere ist ein Fehler, kein
    stillschweigendes Nichts."""
    griff = FakeGriff("/irgendwas", b"token=geheim", "geheim")
    griff.do_POST()
    assert griff.fehler and griff.fehler[0][0] == 404
    assert not stoppdatei.exists()


# --- Die beiden Wege der Seite --------------------------------------------
class _StummerSammler:
    def hole(self) -> tuple[dict[str, Any] | None, datetime | None, float]:
        return None, None, 0.0


def test_die_huelle_kommt_nur_auf_dem_wurzelweg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Trennung ist der ganze Sinn des Nachladens.

    Kaeme unter ``/inhalt`` die volle Huelle, schoebe das Skript bei jedem Takt ein
    zweites ``<html>`` in die Seite -- samt eigenem Skript, das wieder nachlaedt.
    """
    monkeypatch.setattr(OB.Griff, "sammler", _StummerSammler(), raising=False)
    wurzel = FakeGriff("/", b"", "t")
    wurzel.do_GET()
    assert wurzel.antworten == [200]
    assert b"<html" in wurzel.wfile.getvalue()

    teil = FakeGriff("/inhalt", b"", "t")
    teil.do_GET()
    assert b"<html" not in teil.wfile.getvalue()
    assert b"Noch kein Schnappschuss" in teil.wfile.getvalue()


def test_ein_unbekannter_weg_wird_nicht_bedient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(OB.Griff, "sammler", _StummerSammler(), raising=False)
    griff = FakeGriff("/etc/passwd", b"", "t")
    griff.do_GET()
    assert griff.fehler and griff.fehler[0][0] == 404
    assert griff.wfile.getvalue() == b""


def test_ein_alter_schnappschuss_wird_als_alt_ausgezeichnet() -> None:
    """Von Hand: 45 s gegen die Schwelle von 30 s -- rot. 10 s -- unauffaellig.

    Der bestehende Fall prueft nur, dass irgendwo ``krit`` steht; das tut es auf
    dieser Seite ohnehin (der Hinweis zur fehlenden Zulassung traegt es). Geprueft
    wird deshalb die Klasse AN DIESER Zahl.
    """
    stand: dict[str, Any] = {
        "jetzt": T0,
        "fehler": None,
        "lauf": None,
        "alle_laeufe": [],
        "dauer_ms": 12.0,
    }
    stand["gebaut"] = T0 - timedelta(seconds=45)
    assert '<span class="krit">45 s alt</span>' in OB.seite(stand, jetzt=T0)
    stand["gebaut"] = T0 - timedelta(seconds=10)
    assert '<span class="klein">10 s alt</span>' in OB.seite(stand, jetzt=T0)
