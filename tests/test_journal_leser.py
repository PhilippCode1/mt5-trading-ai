"""Der Journal-Leser: die erste Zeile Auswertungscode in diesem Repo mit Test.

WARUM DIESE TESTS
-----------------
Bis heute parste **kein einziger Test** ein Betriebsjournal, waehrend die CI
``mypy --strict`` ueber ``tools/`` faehrt. Beide Leser -- ``betrieb_auswerten.py`` und
``oberflaeche.py`` (geloescht, E-009) -- zaehlten Ereignisse aus rohen Woerterbuechern, ungeprueft. Eine
Auswertung ohne Test ist eine Zahl, die man nicht zitieren kann.

Geprueft wird vor allem, was in der schmeichelnden Richtung schiefgehen koennte:

* Eine kaputte Zeile darf **nicht** stillschweigend uebersprungen werden. Eine
  Auswertung, der Zeilen fehlen, sieht vollstaendig aus und ist es nicht.
* Ein Trade ohne beide Preise darf **nicht** als Ergebnis null durchgehen, sondern
  muss als unvollstaendig gelten.
* Die Richtung muss stimmen: ein Verkauf gewinnt bei fallendem Kurs.
* Die Luecken ZWISCHEN Laeufen muessen sichtbar bleiben.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.betrieb.journal import (
    KOPF_ART,
    QUELLE_ALTJOURNAL,
    QUELLE_BEOBACHTET,
    JournalError,
    Trade,
    bilanz,
    durchgehende_equity,
    geldbilanz,
    lies_alle,
    lies_journal,
    trenne_laeufe,
)

T0 = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]
AUFZEICHNUNG = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"


def _zeile(art: str, minute: int = 0, **felder: Any) -> str:
    d = {
        "ts": (T0 + timedelta(minutes=minute)).isoformat(timespec="seconds"),
        "art": art,
        "lauf": "lauf-a",
        "version": "abc1234",
    }
    d.update(felder)
    return json.dumps(d, ensure_ascii=False)


def _schreib(pfad: Path, *zeilen: str) -> Path:
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad


# --- Lesen ----------------------------------------------------------------
def test_leere_zeilen_stoeren_nicht(tmp_path: Path) -> None:
    p = _schreib(tmp_path / "journal-x.jsonl", _zeile("start"), "", _zeile("takt", 1))
    assert len(lies_journal(p).saetze) == 2


def test_kaputte_zeile_ist_ein_fehler_und_kein_ueberspringen(tmp_path: Path) -> None:
    """Der wichtigste Test der Datei.

    Wer defekte Zeilen ueberspringt, liefert eine Auswertung, die vollstaendig
    aussieht und Zeilen verloren hat -- ohne dass es jemand sieht.
    """
    p = _schreib(
        tmp_path / "journal-x.jsonl", _zeile("start"), "{kaputt", _zeile("takt", 1)
    )
    with pytest.raises(JournalError, match="kein JSON"):
        lies_journal(p)


def test_zeile_ohne_art_ist_ein_fehler(tmp_path: Path) -> None:
    p = _schreib(tmp_path / "journal-x.jsonl", json.dumps({"ts": T0.isoformat()}))
    with pytest.raises(JournalError, match="ts oder art"):
        lies_journal(p)


def test_unlesbarer_zeitstempel_ist_ein_fehler(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl", json.dumps({"ts": "gestern", "art": "takt"})
    )
    with pytest.raises(JournalError, match="ts nicht lesbar"):
        lies_journal(p)


def test_fehlende_datei_ist_ein_fehler(tmp_path: Path) -> None:
    with pytest.raises(JournalError, match="gibt es nicht"):
        lies_journal(tmp_path / "gibtsnicht.jsonl")


def test_lauf_und_version_werden_gelesen(tmp_path: Path) -> None:
    p = _schreib(tmp_path / "journal-x.jsonl", _zeile("start"))
    lauf = lies_journal(p)
    assert lauf.lauf_id == "lauf-a"
    assert lauf.version == "abc1234"


def test_ein_lauf_ohne_endeintrag_gilt_als_nicht_beendet(tmp_path: Path) -> None:
    """Zwei von sechzehn echten Journalen haben keinen Endeintrag."""
    p = _schreib(tmp_path / "journal-x.jsonl", _zeile("start"), _zeile("takt", 1))
    assert lies_journal(p).beendet is False


# --- Equity ---------------------------------------------------------------
def test_equity_reihe_kommt_aus_den_takten(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile("start"),
        _zeile("takt", 1, equity="50000.0"),
        _zeile("takt", 2, equity="50010.5"),
    )
    reihe = lies_journal(p).equity_reihe()
    assert [w for _, w in reihe] == [Decimal("50000.0"), Decimal("50010.5")]


def test_takt_ohne_equity_faellt_aus_der_reihe(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl", _zeile("takt", 1), _zeile("takt", 2, equity="1")
    )
    assert len(lies_journal(p).equity_reihe()) == 1


# --- Trades ---------------------------------------------------------------
def _lauf_mit_trade(tmp_path: Path, **zu: Any) -> Path:
    return _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile("start"),
        _zeile(
            "eroeffnet",
            1,
            symbol="EURUSD",
            signal="LONG",
            volumen="0.11",
            position_id="P1",
            einstiegspreis="1.10000",
            seit=(T0 + timedelta(minutes=1)).isoformat(timespec="seconds"),
        ),
        _zeile(
            "geschlossen",
            5,
            symbol="EURUSD",
            position_id="P1",
            volumen="0.11",
            war_kauf=True,
            grund="signalwechsel",
            **zu,
        ),
    )


def test_eroeffnung_und_schliessung_finden_ueber_die_positions_id_zusammen(
    tmp_path: Path,
) -> None:
    t = lies_journal(_lauf_mit_trade(tmp_path, ausstiegspreis="1.10110")).trades()
    assert len(t) == 1
    assert t[0].position_id == "P1"
    assert t[0].offen is False
    assert t[0].vollstaendig is True


def test_ergebnis_eines_kaufs_in_basispunkten(tmp_path: Path) -> None:
    t = lies_journal(_lauf_mit_trade(tmp_path, ausstiegspreis="1.10110")).trades()[0]
    assert t.ergebnis_bps == pytest.approx(Decimal("10"), abs=Decimal("0.01"))


def test_ein_verkauf_gewinnt_bei_fallendem_kurs(tmp_path: Path) -> None:
    """Die Richtung ist der Fehler, den man einer einzelnen Zahl nicht ansieht."""
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "eroeffnet",
            1,
            symbol="EURUSD",
            signal="SHORT",
            volumen="0.1",
            position_id="P9",
            einstiegspreis="1.10000",
        ),
        _zeile(
            "geschlossen",
            5,
            symbol="EURUSD",
            position_id="P9",
            ausstiegspreis="1.09890",
            grund="haltedauer",
        ),
    )
    t = lies_journal(p).trades()[0]
    assert t.ist_kauf is False
    assert t.ergebnis_bps is not None and t.ergebnis_bps > 0


def test_ohne_ausstiegspreis_gilt_der_trade_als_unvollstaendig(tmp_path: Path) -> None:
    """Kein Preis heisst nicht Ergebnis null -- das waere eine erfundene Zahl."""
    t = lies_journal(_lauf_mit_trade(tmp_path)).trades()[0]
    assert t.vollstaendig is False
    assert t.ergebnis_bps is None


def test_eine_noch_offene_position_bleibt_offen(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "eroeffnet",
            1,
            symbol="XAUUSD",
            signal="LONG",
            volumen="0.01",
            position_id="P2",
            einstiegspreis="4400.0",
        ),
    )
    t = lies_journal(p).trades()[0]
    assert t.offen is True
    assert t.zu_ts is None


def test_broker_schliessung_wird_als_solche_erkannt(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "eroeffnet",
            1,
            symbol="EURUSD",
            signal="LONG",
            volumen="0.1",
            position_id="P3",
            einstiegspreis="1.1",
        ),
        _zeile(
            "vom_broker_geschlossen",
            9,
            symbol="EURUSD",
            position_id="P3",
            volumen="0.1",
            war_kauf=True,
        ),
    )
    t = lies_journal(p).trades()[0]
    assert t.vom_broker is True
    assert t.vollstaendig is False, "Der Stop-Preis ist nicht bekannt"


def test_schliessung_ohne_bekannte_eroeffnung_geht_nicht_verloren(
    tmp_path: Path,
) -> None:
    """``adopt_book`` uebernimmt beim Start offene Positionen, ohne sie zu melden."""
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "geschlossen",
            3,
            symbol="GBPUSD",
            volumen="0.07",
            war_kauf=True,
            grund="lauf_beendet",
            ausstiegspreis="1.35",
        ),
    )
    t = lies_journal(p).trades()
    assert len(t) == 1
    assert t[0].grund == "lauf_beendet"


def test_die_dauer_wird_aus_den_zeitstempeln_gerechnet(tmp_path: Path) -> None:
    t = lies_journal(_lauf_mit_trade(tmp_path, ausstiegspreis="1.1")).trades()[0]
    assert t.dauer_stunden == pytest.approx(4 / 60, abs=1e-6)


# --- Kurse ----------------------------------------------------------------
def test_kursreihe_je_instrument(tmp_path: Path) -> None:
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile("kurs", 1, symbol="EURUSD", bid="1.1000", ask="1.1002"),
        _zeile("kurs", 1, symbol="XAUUSD", bid="4400", ask="4401"),
        _zeile("kurs", 2, symbol="EURUSD", bid="1.1010", ask="1.1012"),
    )
    lauf = lies_journal(p)
    assert lauf.symbole_mit_kursen() == ["EURUSD", "XAUUSD"]
    reihe = lauf.kurs_reihe("EURUSD")
    assert len(reihe) == 2
    assert reihe[0][1] == Decimal("1.1001")


# --- Ueber mehrere Laeufe -------------------------------------------------
def test_mehrere_laeufe_werden_nach_startzeit_sortiert(tmp_path: Path) -> None:
    _schreib(
        tmp_path / "journal-b.jsonl",
        json.dumps(
            {
                "ts": (T0 + timedelta(hours=2)).isoformat(),
                "art": "takt",
                "lauf": "b",
                "equity": "2",
            }
        ),
    )
    _schreib(
        tmp_path / "journal-a.jsonl",
        json.dumps({"ts": T0.isoformat(), "art": "takt", "lauf": "a", "equity": "1"}),
    )
    assert [lauf.lauf_id for lauf in lies_alle(tmp_path)] == ["a", "b"]


def test_die_luecke_zwischen_zwei_laeufen_wird_markiert(tmp_path: Path) -> None:
    """Zwischen zwei Laeufen laeuft die Schleife nicht.

    Was dort geschah -- Stop, Swap, Handeingriff -- steht in keinem Journal. Eine
    Kurve, die das verschweigt, behauptet eine Lueckenlosigkeit, die sie nicht hat.
    """
    _schreib(
        tmp_path / "journal-a.jsonl",
        json.dumps({"ts": T0.isoformat(), "art": "takt", "lauf": "a", "equity": "100"}),
    )
    _schreib(
        tmp_path / "journal-b.jsonl",
        json.dumps(
            {
                "ts": (T0 + timedelta(hours=1)).isoformat(),
                "art": "takt",
                "lauf": "b",
                "equity": "101",
            }
        ),
    )
    punkte = list(durchgehende_equity(lies_alle(tmp_path)))
    assert [luecke for _, _, luecke in punkte] == [False, True]


def test_leeres_verzeichnis_gibt_eine_leere_liste(tmp_path: Path) -> None:
    assert lies_alle(tmp_path) == []


# --- Die Aufzeichnung: Kopfzeile und mehrere Laeufe in einer Datei -----------
def _kopf() -> str:
    return json.dumps({"art": KOPF_ART, "fassung": 2, "behalten_gesamt": 2})


def test_die_kopfzeile_ist_ein_kopf_und_kein_satz(tmp_path: Path) -> None:
    """Gruener Eichfall: die Aufzeichnung beginnt mit ``art: _kopf`` ohne ``ts``.

    Vor Auftrag 1 warf der Leser hier ``ts oder art fehlt`` -- ``betrieb_auswerten.py``
    konnte die eingecheckte Aufzeichnung nicht lesen (Bewertung, Befund T).
    """
    p = _schreib(tmp_path / "aufz.jsonl", _kopf(), _zeile("start"), _zeile("takt", 1))
    lauf = lies_journal(p)
    assert lauf.kopf is not None and lauf.kopf["fassung"] == 2
    assert [s.art for s in lauf.saetze] == ["start", "takt"]


def test_ein_kopf_mitten_in_den_saetzen_ist_ein_fehler(tmp_path: Path) -> None:
    """Roter Eichfall: zwei aneinandergehaengte Aufzeichnungen haben zwei Koepfe, und
    dann stimmt keine der beiden Zaehlungen mehr."""
    p = _schreib(tmp_path / "aufz.jsonl", _zeile("start"), _kopf(), _zeile("takt", 1))
    with pytest.raises(JournalError, match="nicht am Anfang"):
        lies_journal(p)


def test_lies_alle_trennt_eine_aufzeichnungsdatei_nach_laufkennung(
    tmp_path: Path,
) -> None:
    """Eine Datei, drei Laeufe -- ueber ``lauf`` an jedem Satz, nach Startzeit sortiert.

    Die Saetze stehen absichtlich nicht in Startreihenfolge: LAUF-02 beginnt frueher
    als LAUF-01. Der Leser sortiert nach dem ersten Zeitstempel je Lauf.
    """
    p = _schreib(
        tmp_path / "aufz.jsonl",
        _kopf(),
        _zeile("start", 10, lauf="LAUF-01"),
        _zeile("takt", 11, lauf="LAUF-01", equity="1"),
        _zeile("ende", 12, lauf="LAUF-01"),
        _zeile("start", 0, lauf="LAUF-02"),
        _zeile("takt", 1, lauf="LAUF-02", equity="2"),
        _zeile("start", 20, lauf="LAUF-03"),
    )
    laeufe = lies_alle(p)
    assert [lauf.lauf_id for lauf in laeufe] == ["LAUF-02", "LAUF-01", "LAUF-03"]
    assert [len(lauf.saetze) for lauf in laeufe] == [2, 3, 1]
    assert all(lauf.kopf is not None for lauf in laeufe)
    assert all(lauf.pfad == p for lauf in laeufe)
    assert [lauf.beendet for lauf in laeufe] == [False, True, False]
    # Und die Luecke zwischen den Laeufen bleibt sichtbar.
    punkte = list(durchgehende_equity(laeufe))
    assert [luecke for _, _, luecke in punkte] == [False, True]


def test_saetze_ohne_laufkennung_werden_an_start_getrennt(tmp_path: Path) -> None:
    """Ein Journal ohne ``lauf``-Feld (17 der 21 alten Journale) traegt in einer
    Datei mehrere Laeufe nur ueber seine ``start``-Saetze. Der Leser vergibt dann eine
    Kennung je Teil -- sonst verschmoelzen zwei Laeufe in ``durchgehende_equity`` zu
    einem, und keine Luecke wuerde je gemeldet."""
    p = _schreib(
        tmp_path / "zusammen.jsonl",
        json.dumps({"ts": T0.isoformat(), "art": "start"}),
        json.dumps({"ts": (T0 + timedelta(minutes=1)).isoformat(), "art": "ende"}),
        json.dumps({"ts": (T0 + timedelta(hours=1)).isoformat(), "art": "start"}),
    )
    laeufe = trenne_laeufe(lies_journal(p))
    assert [lauf.lauf_id for lauf in laeufe] == [
        "zusammen.jsonl#1",
        "zusammen.jsonl#2",
    ]
    assert [len(lauf.saetze) for lauf in laeufe] == [2, 1]


def test_ein_verzeichnis_bleibt_ein_journal_je_lauf(tmp_path: Path) -> None:
    """Der alte Weg aendert sich nicht: Verzeichnis -> ein Lauf je journal-*.jsonl,
    auch wenn die Saetze dieselbe Kennung tragen."""
    _schreib(tmp_path / "journal-a.jsonl", _zeile("start"))
    _schreib(tmp_path / "journal-b.jsonl", _zeile("start", 5))
    _schreib(tmp_path / "notiz.jsonl", _zeile("start", 9))  # kein journal-*
    laeufe = lies_alle(tmp_path)
    assert [lauf.pfad.name for lauf in laeufe] == ["journal-a.jsonl", "journal-b.jsonl"]


# --- Geld: Herkunft ist Pflicht -------------------------------------------
def test_ein_geldbetrag_ohne_herkunft_ist_ein_fehler(tmp_path: Path) -> None:
    """Der Eichfall gegen die schmeichelnde Richtung.

    Gegen die alte Fassung: ``_geldergebnis`` setzte ``"unbenannt"`` ein, wenn
    ``ergebnis_geld_quelle`` fehlte. Der Betrag ging damit als vollwertiges
    Geldergebnis durch, bestimmte ueber ``gewinn`` den Trefferanteil mit -- und weil
    das Herkunftsfeld ausserdem keinen Leser hatte, sah es niemand. Eine Schaetzung,
    die sich als Messung ausgibt, ist genau die Sorte Zahl, gegen die dieses Repo
    gebaut ist.

    Alte Journale laufen hier nicht hinein: sie tragen ``ergebnis_geld`` gar nicht.
    """
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "vom_broker_geschlossen",
            9,
            symbol="EURUSD",
            volumen="0.1",
            war_kauf=True,
            position_id="P4",
            einstiegspreis="1.1",
            ergebnis_geld="-3.10",
            ergebnis_geld_waehrung="EUR",
        ),
    )
    with pytest.raises(JournalError, match="ohne ergebnis_geld_quelle"):
        lies_journal(p)


def test_die_herkunft_darf_nicht_leer_sein(tmp_path: Path) -> None:
    """Ein leerer String ist keine Angabe -- sonst waere die Sperre in einem Zug
    umgangen."""
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "vom_broker_geschlossen",
            9,
            symbol="EURUSD",
            volumen="0.1",
            war_kauf=True,
            ergebnis_geld="-3.10",
            ergebnis_geld_quelle="  ",
        ),
    )
    with pytest.raises(JournalError, match="ohne ergebnis_geld_quelle"):
        lies_journal(p)


def test_ein_alter_satz_ohne_geldfeld_bleibt_lesbar(tmp_path: Path) -> None:
    """Die Gegenprobe: die Sperre darf nicht die Altjournale erschlagen.

    Kernregel 22 -- alte Saetze werden nicht umgeschrieben. Sie tragen kein
    ``ergebnis_geld``, sondern ``zuletzt_unrealisiert``, und die Deutung faellt
    sichtbar beim Lesen.
    """
    p = _schreib(
        tmp_path / "journal-x.jsonl",
        _zeile(
            "vom_broker_geschlossen",
            9,
            symbol="EURUSD",
            volumen="0.1",
            war_kauf=True,
            zuletzt_unrealisiert="-3.10",
        ),
    )
    t = lies_journal(p).trades()[0]
    assert t.ergebnis_geld == Decimal("-3.10")
    assert t.ergebnis_geld_quelle == QUELLE_ALTJOURNAL


def test_geldbilanz_wirft_bei_einem_trade_ohne_herkunft() -> None:
    """Dieselbe Regel dort, wo aufsummiert wird -- nicht nur am Dateileser."""
    t = Trade(
        symbol="EURUSD",
        ist_kauf=True,
        volumen=Decimal("0.1"),
        auf_ts=T0,
        einstieg=Decimal("1.1"),
        zu_ts=T0,
        ergebnis_geld=Decimal("-1"),
    )
    with pytest.raises(JournalError, match="ohne ergebnis_geld_quelle"):
        geldbilanz([t])


# --- Die eine Einteilung ---------------------------------------------------
def _trade(
    *,
    geld: str | None = None,
    ausstieg: str | None = None,
    quelle: str = QUELLE_BEOBACHTET,
    waehrung: str | None = "EUR",
    vom_broker: bool = False,
) -> Trade:
    return Trade(
        symbol="EURUSD",
        ist_kauf=True,
        volumen=Decimal("0.1"),
        auf_ts=T0,
        einstieg=Decimal("1.10000"),
        zu_ts=T0 + timedelta(minutes=5),
        ausstieg=None if ausstieg is None else Decimal(ausstieg),
        vom_broker=vom_broker,
        ergebnis_geld=None if geld is None else Decimal(geld),
        ergebnis_geld_waehrung=None if geld is None else waehrung,
        ergebnis_geld_quelle=None if geld is None else quelle,
    )


def test_bilanz_sortiert_in_vier_toepfe() -> None:
    """Die Einteilung, die vorher zweimal im Haus stand.

    Ein Trade mit Preis zaehlt beim Preis, einer mit nur Geld im Geldtopf, ein stummer
    in keinem von beiden -- und ein offener gar nicht mit.
    """
    offen = Trade(
        symbol="EURUSD",
        ist_kauf=True,
        volumen=Decimal("0.1"),
        auf_ts=T0,
        einstieg=Decimal("1.1"),
    )
    b = bilanz(
        [
            _trade(ausstieg="1.10110", geld="+4.82"),
            _trade(geld="-2.68", vom_broker=True),
            _trade(),
            offen,
        ]
    )
    assert len(b.geschlossen) == 3
    assert len(b.preis) == 1
    assert len(b.beurteilt) == 2
    assert len(b.nur_geld) == 1
    assert len(b.stumm) == 1


def test_geldbilanz_nimmt_auch_die_selbst_geschlossenen_trades() -> None:
    """Der Kern: der Geldtopf ist NICHT der Topf "nur Geld".

    ``urteilsquelle`` gibt dem Preis den Vorrang. Wer die Geldsumme daran aufhaengt,
    hat wieder ausschliesslich Stop-Outs -- also nur Verlierer -- in der Statistik,
    und das Geldfeld am eigenen Schluss waere wirkungslos.
    """
    b = geldbilanz(
        [
            _trade(ausstieg="1.10110", geld="+4.82"),
            _trade(geld="-2.68", vom_broker=True),
        ]
    )
    assert len(b.trades) == 2
    assert b.vom_broker == 1
    assert b.summe == Decimal("2.14")
    assert b.waehrung == "EUR"
    assert b.hindernis is None


def test_geldbilanz_haelt_geschriebene_und_gedeutete_betraege_auseinander() -> None:
    """Der Leser fuer ``ergebnis_geld_quelle``. Ohne ihn ist die Marke Ballast."""
    b = geldbilanz(
        [_trade(geld="-2.68"), _trade(geld="-2.43", quelle=QUELLE_ALTJOURNAL)]
    )
    assert b.je_herkunft == {QUELLE_BEOBACHTET: 1, QUELLE_ALTJOURNAL: 1}


def test_geldbilanz_summiert_keine_zwei_waehrungen() -> None:
    """Ueber mehrere Laeufe ist das erreichbar: verschiedene Konten, verschiedene
    Waehrungen. Eine Summe darueber sieht aus wie Geld und ist keines."""
    b = geldbilanz([_trade(geld="+1.00"), _trade(geld="+2.00", waehrung="USD")])
    assert b.summe is None
    assert b.hindernis is not None and "verschiedene Waehrungen" in b.hindernis


def test_geldbilanz_ohne_waehrungsangabe_summiert_nicht() -> None:
    b = geldbilanz([_trade(geld="+1.00", waehrung=None)])
    assert b.summe is None
    assert b.hindernis is not None and "ohne Waehrungsangabe" in b.hindernis


def test_geldbilanz_ohne_geldergebnisse_ist_leer() -> None:
    b = geldbilanz([_trade(ausstieg="1.10110")])
    assert b.trades == []
    assert b.summe is None and b.hindernis is None


# --- Gegen die echten Laeufe: die eingecheckte Aufzeichnung ---------------
def test_alle_echten_laeufe_sind_lesbar() -> None:
    """Positivprobe: was der Betrieb wirklich geschrieben hat, muss durchgehen.

    Gelesen wird die Aufzeichnung (Auftrag 1, T6, Befund T), nicht ``betrieb/``: das
    ist gitignoriert, und dieser Fall uebersprang sich auf jedem Klon. Fehlt die
    Aufzeichnung, ist der Fall rot (Katalog A2). Die Zahlen sind an den 21 Journalen
    und an der Aufzeichnung gemessen und gleich (Beleg
    ``06-aufzeichnung-metriken-vergleich.txt``): 21 Laeufe, 32 Trades (alle
    geschlossen), 1.360 Equity-Punkte, 19 beendet, 15 scharf.
    """
    assert AUFZEICHNUNG.is_file(), (
        f"{AUFZEICHNUNG.relative_to(ROOT).as_posix()} fehlt -- kein Gegenstand fuer "
        "die Positivprobe (Katalog A2). Erzeugen mit: python tools/aufzeichnung_redigieren.py"
    )
    laeufe = lies_alle(AUFZEICHNUNG)
    assert [lauf.lauf_id for lauf in laeufe] == [f"LAUF-{n:02d}" for n in range(1, 22)]
    for lauf in laeufe:
        assert lauf.saetze, f"{lauf.lauf_id} ist leer"
        assert lauf.kopf is not None and lauf.kopf["laeufe"][lauf.lauf_id]
        for t in lauf.trades():
            assert isinstance(t, Trade)
    trades = [t for lauf in laeufe for t in lauf.trades()]
    assert len(trades) == 32
    assert sum(1 for t in trades if not t.offen) == 32
    assert sum(len(lauf.equity_reihe()) for lauf in laeufe) == 1360
    assert sum(1 for lauf in laeufe if lauf.beendet) == 19
    assert sum(1 for lauf in laeufe if lauf.scharf) == 15
