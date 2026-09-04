"""Der Ausstieg: dass am Ende wirklich niemand mehr draussen steht.

WORAUS DAS ENTSTANDEN IST
-------------------------
Stufe 10 hat die Ausstiegsverlaesslichkeit mit **78,8 % (26 von 33 Schliessversuchen)**
gemessen -- das schlechteste Ergebnis des ganzen Standes. Die Aufschluesselung der
sieben Fehlschlaege ergab **zwei voellig verschiedene Klassen**, und nur eine davon war
noch offen:

* **2 Faelle** (2026-08-17, 14:57 und 14:58 UTC): ``Handelsplatz hat abgelehnt: Done``
  bzw. ``Done (retcode=0)``. Das war die Annahme-Erkennung: dieser Broker meldet Erfolg
  mit ``retcode=0`` und ``comment='Done'``. Ein ausgefuehrter Schluss galt als
  Ablehnung. **Bereits behoben** in Commit ``82c81c3`` (2026-08-17, 15:03 UTC -- also
  fuenf Minuten nach dem zweiten Fall) und gepinnt in
  ``tests/test_schreibpfad_wirkung.py::test_der_gemessene_retcode_null_bleibt_ein_fill``.
* **5 Faelle** (17:34 und 18:28 UTC, zwei Laeufe):
  ``Real-Terminal: Schreibpfad gesperrt (allow_write=False)``. **Diese Klasse war
  offen**, und sie ist die schwerere.

DIE OFFENE KLASSE, GENAU BESCHRIEBEN
------------------------------------
Beide Laeufe liefen ohne ``--scharf``, also ohne Schreibrecht. Beide haben beim Start
ueber ``adopt_book()`` fremde Positionen uebernommen (Journal ``173413``: 23.002,90
belegte Marge), einen Takt lang beaufsichtigt -- und **erst beim Herunterfahren**
gemerkt, dass sie den zugesagten Ausstieg nicht fahren koennen. Der ``ende``-Satz
fuehrt, was liegen blieb::

    "offen_geblieben": ["EURUSD", "GBPUSD", "XAUUSD"]
    "offen_geblieben": ["EURUSD", "GBPUSD"]

**Und keine Kennzahl sah das.** ``laufabschluss`` fragt nur nach einem ``ende``-Satz --
beide Laeufe haben einen. Sie zaehlten als saubere Laeufe, waehrend Geld ohne
beaufsichtigenden Prozess am Markt stand.

WAS HIER GEPRUEFT WIRD
----------------------
1. Der **Riegel** (``tools/live_betrieb.py::ausstiegszusage_pruefen``): ein Lauf, der ein
   Glattstellen zusagt, das er nicht halten kann, startet nicht mehr.
2. Die **Metrik** (``betrieb/dienstguete.py::ausstiegsdeckung``), die den Fall ueberhaupt
   sichtbar macht -- samt der Frage, was mit nicht beurteilbaren Laeufen geschieht.

Jeweils rot und gruen (V4).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from mt5_trading_ai.betrieb.dienstguete import (
    ALARMREGELN,
    METRIKEN,
    ZIELE,
    ausstiegsdeckung,
    erhebe,
    pruefe_alarme,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from live_betrieb import ausstiegszusage_pruefen  # noqa: E402

#: Der Gegenstand des Dauertors auf den „echten Journalen" (Auftrag 1, T6, Befund T):
#: die eingecheckte Aufzeichnung mit ``takt``-Saetzen, nicht das gitignorierte
#: ``betrieb/``. Gemessen (Beleg ``06-aufzeichnung-metriken-vergleich.txt``):
#: Ausstiegsdeckung 8 von 11 Laeufen mit Position, 10 unbeurteilbar -- an den 21
#: Journalen wie an der Aufzeichnung.
AUFZEICHNUNG = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"


# =====================================================================
# Der Riegel — ein Lauf sagt keinen Ausstieg zu, den er nicht halten kann
# =====================================================================


def test_rot_der_gemessene_fall_wird_jetzt_abgewiesen() -> None:
    """Genau die Lage der beiden Laeufe vom 2026-08-17.

    Kein Schreibrecht, Glattstellen zugesagt, Positionen offen. Vorher: Start, ein
    Takt, dann funf gescheiterte Schliessversuche und drei offene Positionen. Jetzt:
    kein Start.
    """
    grund = ausstiegszusage_pruefen(
        kann_schreiben=False,
        schliesst_am_ende=True,
        offene_symbole=["EURUSD", "GBPUSD", "XAUUSD"],
    )
    assert grund is not None
    # Die Meldung muss sagen, WAS offen steht -- sonst weiss der Mensch nicht, was er
    # von Hand schliessen soll.
    assert "EURUSD" in grund and "XAUUSD" in grund
    # Und sie muss alle drei Auswege nennen; ein Riegel ohne Ausweg wird umgangen.
    assert "--demo-schreiben" in grund
    assert "--am-ende-offen-lassen" in grund
    assert "von Hand" in grund


def test_gruen_ohne_offene_position_startet_der_lauf() -> None:
    """Der haeufigste Fall. Ohne ihn stuende der Riegel jedem Lauf im Weg."""
    assert (
        ausstiegszusage_pruefen(
            kann_schreiben=False, schliesst_am_ende=True, offene_symbole=[]
        )
        is None
    )


def test_gruen_mit_schreibrecht_startet_der_lauf() -> None:
    """``--scharf``: der Lauf kann halten, was er zusagt."""
    assert (
        ausstiegszusage_pruefen(
            kann_schreiben=True, schliesst_am_ende=True, offene_symbole=["EURUSD"]
        )
        is None
    )


def test_gruen_wer_kein_glattstellen_zusagt_darf_zusehen() -> None:
    """``--am-ende-offen-lassen``: der Lauf verspricht den Ausstieg gar nicht erst.

    Das ist der Beobachtungslauf, den es geben muss -- die Verantwortung fuer die
    offenen Positionen bleibt dann ausdruecklich beim Menschen, und er hat es
    hingeschrieben.
    """
    assert (
        ausstiegszusage_pruefen(
            kann_schreiben=False, schliesst_am_ende=False, offene_symbole=["EURUSD"]
        )
        is None
    )


def test_der_riegel_haengt_wirklich_im_werkzeug() -> None:
    """V1: eine Sperre ohne Aufrufer im Ausfuehrungspfad ist keine.

    Geprueft wird der Quelltext von ``main()``: der Aufruf steht dort, und er steht
    **vor** ``adopt_book()`` -- uebernommen wird nur, was der Lauf wieder loswerden kann.
    """
    quelle = (ROOT / "tools" / "live_betrieb.py").read_text(encoding="utf-8")
    ruf = quelle.index("hindernis = ausstiegszusage_pruefen(")
    uebernahme = quelle.index("venue.adopt_book()", ruf)
    assert ruf < uebernahme
    # Und der Abbruch endet den Lauf wirklich, statt nur zu warnen.
    zwischen = quelle[ruf:uebernahme]
    assert "return 2" in zwischen


# =====================================================================
# Die Metrik — sie macht den Fall ueberhaupt sichtbar
# =====================================================================


def _ende(offen: list[str] | None, *, feld: bool = True) -> str:
    satz: dict[str, object] = {"art": "ende"}
    if feld:
        satz["offen_geblieben"] = offen
    return json.dumps(satz)


def _lauf(*saetze: str, hielt: bool = True) -> list[str]:
    """Ein vollstaendiger Lauf: start, optional ein Beleg fuer eine gehaltene Position.

    ``hielt`` traegt seit dem Nachtrag vom 2026-08-20 den Nenner: nur Laeufe, die
    nachweislich eine Position hielten, werden gezaehlt. Ohne diesen Riegel hoben
    zwanzig Trockenlaeufe von je zwanzig Sekunden jede Quote ueber jede Schwelle.
    """
    kopf = [json.dumps({"art": "start"})]
    if hielt:
        kopf.append(
            json.dumps(
                {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "EURUSD"}
            )
        )
    return kopf + list(saetze)


def test_rot_ein_lauf_mit_offener_position_zaehlt_nicht_als_sauber() -> None:
    zeilen = _lauf(_ende([])) + _lauf(_ende(["EURUSD", "GBPUSD"]))
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert (wert.gelungen, wert.gesamt) == (1, 2)
    assert wert.anteil == pytest.approx(0.5)


def test_gruen_lauter_saubere_laeufe_ergeben_volle_deckung() -> None:
    zeilen = [z for _ in range(5) for z in _lauf(_ende([]))]
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert wert.anteil == pytest.approx(1.0)
    assert wert.unbeurteilbar == 0


def test_ein_fehlendes_feld_zaehlt_NICHT_als_sauber() -> None:
    """V3 an der Stelle, an der es am leichtesten zu uebersehen waere.

    Aufzeichnungen von vor der Einfuehrung des Feldes sagen ueber den Ausstieg
    **nichts**. Sie als sauber zu zaehlen ersetzte einen fehlenden Messwert durch einen
    Standardwert -- und zwar durch den schmeichelnden.
    """
    zeilen = (
        _lauf(_ende([]))
        + _lauf(json.dumps({"art": "takt"}), hielt=False)
        + _lauf(json.dumps({"art": "takt"}), hielt=False)
    )
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert (wert.gelungen, wert.gesamt) == (1, 1), "Fehlende Felder im Nenner!"
    assert wert.unbeurteilbar == 2
    assert wert.anteil == pytest.approx(1.0)


def test_ROT_zwanzig_trockenlaeufe_heben_die_quote_NICHT() -> None:
    """Der Riegel gegen die naheliegendste Beschoenigung.

    Ein Lauf, der nachweislich nie eine Position hielt (jeder Takt traegt ein leeres
    Positionsfeld), kann nichts zuruecklassen. Er ist weder Erfolg noch Fehlschlag und
    gehoert nicht in den Nenner. Ohne diesen Riegel hoeben zwanzig Trockenlaeufe von je
    zwanzig Sekunden -- zusammen sieben Minuten Arbeit -- jede Quote ueber jede
    Schwelle, ohne dass sich am Betrieb das Geringste bessert.
    """
    echt = _lauf(_ende(["EURUSD"]))  # ein echter Fehlschlag
    trocken = [
        z
        for _ in range(20)
        for z in _lauf(
            json.dumps({"art": "takt", "positionen": []}), _ende([]), hielt=False
        )
    ]
    vorher = ausstiegsdeckung([json.loads(z) for z in echt])
    nachher = ausstiegsdeckung([json.loads(z) for z in echt + trocken])
    assert (vorher.gelungen, vorher.gesamt) == (0, 1)
    assert (nachher.gelungen, nachher.gesamt) == (0, 1), (
        "Trockenlaeufe sind in den Nenner gerutscht -- die Quote ist schoenbar."
    )
    assert nachher.unbeurteilbar == 0  # sie sind NICHT unbeurteilbar, sondern
    # schlicht nicht anwendbar


def test_ein_hart_gestorbener_lauf_mit_offener_position_wird_GESEHEN() -> None:
    """Der Fall, der die erste Fassung dieser Metrik nicht sah.

    ``journal-20260817T150513``: drei Eroeffnungen, keine Schliessung, dann der Tod --
    ohne ``ende``-Satz. Die erste Fassung zaehlte nur ``ende``-Saetze und war fuer
    diesen Vorgang blind, obwohl ihre Alarmregel „Position offen geblieben" heisst.
    """
    zeilen = [
        json.dumps({"art": "start"}),
        json.dumps(
            {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "EURUSD"}
        ),
        json.dumps(
            {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "GBPUSD"}
        ),
        json.dumps(
            {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "XAUUSD"}
        ),
        json.dumps({"art": "takt", "nr": 6}),
    ]  # kein ende -- der Prozess ist tot
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert (wert.gelungen, wert.gesamt) == (0, 1)
    assert wert.unbeurteilbar == 0


def test_gruen_ein_hart_gestorbener_lauf_mit_leerem_buch_ist_sauber() -> None:
    """Die Gegenprobe: ohne sie hiesse „hart gestorben" pauschal „gefaehrlich".

    ``journal-20260817T182951`` starb nach 18,7 Stunden -- mit 13 Eroeffnungen, 13
    Schliessungen und einem letzten Takt, der ein leeres Buch ausweist.
    """
    zeilen = [
        json.dumps({"art": "start"}),
        json.dumps(
            {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "EURUSD"}
        ),
        json.dumps({"art": "geschlossen", "symbol": "EURUSD"}),
        json.dumps({"art": "takt", "nr": 1122, "positionen": []}),
    ]
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert (wert.gelungen, wert.gesamt) == (1, 1)


def test_die_aussage_des_laufs_schlaegt_die_bilanz() -> None:
    """Rangfolge: ``offen_geblieben`` steht ueber dem letzten Takt und ueber der Bilanz.

    Der Lauf hat drei eroeffnet und keine geschlossen -- die Bilanz sagte 3. Sein
    ``ende``-Satz sagt aber, dass nichts liegen blieb (die Schliessungen kamen im
    finally-Block, nach dem letzten Takt). Die Aussage des Laufs gewinnt.
    """
    zeilen = [
        json.dumps({"art": "start"}),
        json.dumps(
            {"art": "eroeffnungsversuch", "eroeffnet": True, "symbol": "EURUSD"}
        ),
        json.dumps({"art": "takt", "nr": 1, "positionen": [{"symbol": "EURUSD"}]}),
        _ende([]),
    ]
    wert = ausstiegsdeckung([json.loads(z) for z in zeilen])
    assert (wert.gelungen, wert.gesamt) == (1, 1)


def test_rot_die_neue_regel_schlaegt_auf_den_echten_journalen_an() -> None:
    """Der Beleg, dass die Metrik den gemessenen Fall wirklich faengt.

    Ohne diesen Fall koennte die Metrik an den echten Daten voellig stumm bleiben und
    trotzdem alle Einzeltests bestehen.
    """
    assert AUFZEICHNUNG.is_file(), (
        f"{AUFZEICHNUNG.relative_to(ROOT).as_posix()} fehlt -- kein Gegenstand fuer "
        "das Dauertor (Katalog A2). Erzeugen mit: python tools/aufzeichnung_redigieren.py"
    )
    zeilen = [
        z for z in AUFZEICHNUNG.read_text(encoding="utf-8").splitlines() if z.strip()
    ]
    assert zeilen and json.loads(zeilen[0]).get("art") == "_kopf"
    werte = erhebe(zeilen[1:])
    wert = werte["ausstiegsdeckung"]
    # 3 gerissene Laeufe: 150513 (hart gestorben, drei offen), 173413 und 182800
    # (ende-Satz mit offen_geblieben). 10 der 21 Laeufe sind unbeurteilbar (alte
    # Journale ohne Positionsfeld und ohne offen_geblieben).
    assert (wert.gelungen, wert.gesamt, wert.unbeurteilbar) == (8, 11, 10)
    assert wert.anteil is not None and wert.anteil < 1.0, (
        "Die Metrik sieht die Laeufe vom 2026-08-17 nicht mehr."
    )
    namen = [a.regel.name for a in pruefe_alarme(werte)]
    assert "position_offen_geblieben" in namen


# =====================================================================
# Die drei Bindungen der neuen Regel (wie fuer jede andere auch)
# =====================================================================


def test_die_neue_regel_ist_vollstaendig_gebunden() -> None:
    regel = next(r for r in ALARMREGELN if r.name == "position_offen_geblieben")
    assert regel.metrik in METRIKEN
    assert "Terminal" in regel.handlungsanweisung  # die Handlung selbst (E-014)
    ziel = next(z for z in ZIELE if z.metrik == regel.metrik)
    assert regel.schwelle == ziel.ziel


def test_dieses_eine_ziel_hat_bewusst_kein_fehlerbudget() -> None:
    """Und ``verbraucht`` faellt darueber nicht um.

    Ein Fehlerbudget von 0 laesst sich nicht als Anteil verbrauchen -- die Rechnung
    teilte durch null. ``verbraucht`` gibt darum ``None`` zurueck, und die Anzeige
    schreibt „--" statt einer erfundenen Zahl.
    """
    ziel = next(z for z in ZIELE if z.metrik == "ausstiegsdeckung")
    assert ziel.ziel == 1.00
    assert ziel.fehlerbudget == pytest.approx(0.0)
    wert = ausstiegsdeckung([json.loads(_ende(["EURUSD"]))])
    assert ziel.verbraucht(wert) is None
