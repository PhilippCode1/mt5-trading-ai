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

JOURNALE = ROOT / "betrieb"


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
        kann_schreiben=False, schliesst_am_ende=True,
        offene_symbole=["EURUSD", "GBPUSD", "XAUUSD"],
    )
    assert grund is not None
    # Die Meldung muss sagen, WAS offen steht -- sonst weiss der Mensch nicht, was er
    # von Hand schliessen soll.
    assert "EURUSD" in grund and "XAUUSD" in grund
    # Und sie muss alle drei Auswege nennen; ein Riegel ohne Ausweg wird umgangen.
    assert "--scharf" in grund
    assert "--am-ende-offen-lassen" in grund
    assert "von Hand" in grund


def test_gruen_ohne_offene_position_startet_der_lauf() -> None:
    """Der haeufigste Fall. Ohne ihn stuende der Riegel jedem Lauf im Weg."""
    assert ausstiegszusage_pruefen(
        kann_schreiben=False, schliesst_am_ende=True, offene_symbole=[]
    ) is None


def test_gruen_mit_schreibrecht_startet_der_lauf() -> None:
    """``--scharf``: der Lauf kann halten, was er zusagt."""
    assert ausstiegszusage_pruefen(
        kann_schreiben=True, schliesst_am_ende=True, offene_symbole=["EURUSD"]
    ) is None


def test_gruen_wer_kein_glattstellen_zusagt_darf_zusehen() -> None:
    """``--am-ende-offen-lassen``: der Lauf verspricht den Ausstieg gar nicht erst.

    Das ist der Beobachtungslauf, den es geben muss -- die Verantwortung fuer die
    offenen Positionen bleibt dann ausdruecklich beim Menschen, und er hat es
    hingeschrieben.
    """
    assert ausstiegszusage_pruefen(
        kann_schreiben=False, schliesst_am_ende=False, offene_symbole=["EURUSD"]
    ) is None


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


def test_rot_ein_lauf_mit_offener_position_zaehlt_nicht_als_sauber() -> None:
    wert = ausstiegsdeckung(
        [json.loads(_ende([])), json.loads(_ende(["EURUSD", "GBPUSD"]))]
    )
    assert (wert.gelungen, wert.gesamt) == (1, 2)
    assert wert.anteil == pytest.approx(0.5)


def test_gruen_lauter_saubere_laeufe_ergeben_volle_deckung() -> None:
    wert = ausstiegsdeckung([json.loads(_ende([])) for _ in range(5)])
    assert wert.anteil == pytest.approx(1.0)
    assert wert.unbeurteilbar == 0


def test_ein_fehlendes_feld_zaehlt_NICHT_als_sauber(tmp_path: Path) -> None:
    """V3 an der Stelle, an der es am leichtesten zu uebersehen waere.

    Aufzeichnungen von vor der Einfuehrung des Feldes sagen ueber den Ausstieg
    **nichts**. Sie als sauber zu zaehlen ersetzte einen fehlenden Messwert durch einen
    Standardwert -- und zwar durch den schmeichelnden.
    """
    wert = ausstiegsdeckung([
        json.loads(_ende([])),
        json.loads(_ende(None, feld=False)),
        json.loads(_ende(None, feld=False)),
    ])
    assert (wert.gelungen, wert.gesamt) == (1, 1), "Fehlende Felder im Nenner!"
    assert wert.unbeurteilbar == 2
    assert wert.anteil == pytest.approx(1.0)


def test_rot_die_neue_regel_schlaegt_auf_den_echten_journalen_an() -> None:
    """Der Beleg, dass die Metrik den gemessenen Fall wirklich faengt.

    Ohne diesen Fall koennte die Metrik an den echten Daten voellig stumm bleiben und
    trotzdem alle Einzeltests bestehen.
    """
    zeilen: list[str] = []
    for datei in sorted(JOURNALE.glob("*.jsonl")):
        zeilen.extend(datei.read_text(encoding="utf-8").splitlines())
    if not zeilen:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    werte = erhebe(zeilen)
    wert = werte["ausstiegsdeckung"]
    assert wert.gesamt >= 2
    assert wert.anteil is not None and wert.anteil < 1.0, (
        "Die Metrik sieht die zwei Laeufe vom 2026-08-17 nicht mehr."
    )
    namen = [a.regel.name for a in pruefe_alarme(werte)]
    assert "position_offen_geblieben" in namen


# =====================================================================
# Die drei Bindungen der neuen Regel (wie fuer jede andere auch)
# =====================================================================


def test_die_neue_regel_ist_vollstaendig_gebunden() -> None:
    regel = next(r for r in ALARMREGELN if r.name == "position_offen_geblieben")
    assert regel.metrik in METRIKEN
    runbook = (ROOT / "RUNBOOK.md").read_text(encoding="utf-8")
    assert f"\n## {regel.handlungsanweisung}\n" in runbook
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
