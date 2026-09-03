"""Stufe 7 — Kaltstart öffnen. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Woertlich::

    Der Kreis „ohne Modell keine Entscheidung, ohne Entscheidung keine Daten, ohne
    Daten kein Modell" wird aufgebrochen: protokollierter Erkundungspfad im
    Papierkonto mit mitgeschriebenen Ablehnungsgruenden, Gewichtung nach
    Auswahlwahrscheinlichkeit im Training, Herkunftsspalte in den Auswertungen.
    Schwellen, die exakt auf dem Maximum der Ersatzheuristik liegen, davon entkoppeln.

    Abnahme: die Auswertungstabelle enthaelt gekennzeichnete Zeilen aus abgelehnten
    Signalen; ein Trainingslauf weist den Anteil erkundender Beobachtungen aus.

DER KREIS, IN EINER ZAHL
------------------------
Gemessen an den echten Journalen: von **4.343** Eroeffnungsversuchen wurden **32**
eroeffnet -- **0,74 %**. Ueber die uebrigen 99,26 % gibt es keine Beobachtung. Ein Tor,
das zu streng ist, sieht dabei genauso aus wie eines, das richtig liegt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.gates.erkundung import (
    ERKUNDBARE_GRUENDE,
    Auswertungszeile,
    Herkunft,
    entscheide_erkundung,
    erkundung_erlaubt,
    erkundungsanteil,
    gewichteter_mittelwert,
)
from mt5_trading_ai.risk.stop_budget import (
    ASSUMED_ROUND_TURN_COST_BPS,
    KOSTENPRAEMISSE_BPS,
    kostenpraemisse_bps,
)

ROOT = Path(__file__).resolve().parents[1]
AUFZEICHNUNG = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"


def _zeile(**kw):
    basis = dict(
        ts="2026-08-17T12:00:00+00:00",
        instrument="EURUSD",
        signal="LONG",
        herkunft=Herkunft.GEFAHREN,
        ergebnis_bp=1.0,
    )
    basis.update(kw)
    return Auswertungszeile(**basis)  # type: ignore[arg-type]


# =====================================================================
# A1 — Erkundungspfad: nur Papier, nur Auswahlgruende, nie eine Sperre
# =====================================================================
@pytest.mark.parametrize("grund", sorted(ERKUNDBARE_GRUENDE))
def test_auswahlgruende_sind_auf_dem_papierkonto_erkundbar(grund: str) -> None:
    """Ueber ALLE Eintraege der Positivliste, nicht am Vertreter."""
    assert erkundung_erlaubt(ist_papierkonto=True, ablehnungsgrund=grund) == ""


@pytest.mark.parametrize(
    "grund",
    [
        "global_halt",
        "missing_stop_loss",
        "schwebender_auftrag",
        "account_unevaluable",
        "cost_gate",
        "insufficient_margin",
        "volume_below_min",
        "risk_drawdown_halt",
    ],
)
def test_keine_sicherheitssperre_wird_je_erkundet(grund: str) -> None:
    """DER rote Eichfall der Stufe.

    Erkundung darf Wissen kaufen, aber nie mit einer Sperre bezahlen. Waere die Liste
    ein Filter statt einer Positivliste, ginge jeder neue Ablehnungsgrund automatisch
    durch -- und der naechste eingebaute Riegel waere ab dem Tag seiner Entstehung
    erkundbar.
    """
    assert erkundung_erlaubt(ist_papierkonto=True, ablehnungsgrund=grund) != ""
    entscheidung = entscheide_erkundung(
        ist_papierkonto=True, ablehnungsgrund=grund, schluessel="egal"
    )
    assert entscheidung.erkunden is False
    assert entscheidung.wahrscheinlichkeit == 0.0


def test_auf_einem_echtgeldkonto_wird_nie_erkundet() -> None:
    """Erkundung mit echtem Geld waere keine Erkundung, sondern eine Umgehung."""
    for grund in sorted(ERKUNDBARE_GRUENDE):
        assert erkundung_erlaubt(ist_papierkonto=False, ablehnungsgrund=grund) == (
            "kein_papierkonto"
        )


def test_dieselbe_gelegenheit_ergibt_dieselbe_entscheidung() -> None:
    """Ohne Reproduzierbarkeit belegt eine Auswertung nichts."""
    a = entscheide_erkundung(
        ist_papierkonto=True, ablehnungsgrund="strategy_not_admitted", schluessel="x"
    )
    b = entscheide_erkundung(
        ist_papierkonto=True, ablehnungsgrund="strategy_not_admitted", schluessel="x"
    )
    assert a == b


def test_die_rate_trifft_ueber_viele_gelegenheiten() -> None:
    """Der gruene Gegenfall: es wird ueberhaupt erkundet, und ungefaehr so oft wie gesagt.

    Ohne ihn bestuende der rote Fall oben auch an einer Funktion, die grundsaetzlich
    nie erkundet -- und die waere im Betrieb wirkungslos.
    """
    treffer = sum(
        1
        for i in range(4000)
        if entscheide_erkundung(
            ist_papierkonto=True,
            ablehnungsgrund="strategy_not_admitted",
            schluessel=f"gelegenheit-{i}",
        ).erkunden
    )
    anteil = treffer / 4000
    assert 0.03 < anteil < 0.07, f"Rate {anteil:.3f} weit weg von 0,05"


def test_eine_unsinnige_rate_wirft() -> None:
    for rate in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="Erkundungsrate"):
            entscheide_erkundung(
                ist_papierkonto=True,
                ablehnungsgrund="strategy_not_admitted",
                schluessel="x",
                rate=rate,
            )


# =====================================================================
# A2 — Gewichtung nach Auswahlwahrscheinlichkeit
# =====================================================================
def test_eine_erkundete_zeile_wiegt_invers_zu_ihrer_wahrscheinlichkeit() -> None:
    zeile = _zeile(herkunft=Herkunft.ERKUNDET, wahrscheinlichkeit=0.05)
    assert zeile.gewicht == pytest.approx(20.0)


def test_eine_regulaere_zeile_wiegt_eins() -> None:
    """Der gruene Gegenfall: die Gewichtung greift nur, wo sie hingehoert."""
    assert _zeile().gewicht == 1.0
    assert _zeile(herkunft=Herkunft.ABGELEHNT, ergebnis_bp=None).gewicht == 1.0


def test_eine_erkundete_zeile_ohne_wahrscheinlichkeit_laesst_sich_nicht_gewichten() -> (
    None
):
    """V3: ein fehlender Messwert sperrt, er wird nicht durch 1 ersetzt."""
    with pytest.raises(ValueError, match="Auswahlwahrscheinlichkeit"):
        _ = _zeile(herkunft=Herkunft.ERKUNDET, wahrscheinlichkeit=0.0).gewicht


def test_die_gewichtung_verschiebt_den_mittelwert_in_die_richtige_richtung() -> None:
    """Die Rechnung an einem Fall, der von Hand nachzuvollziehen ist.

    Eine regulaere Zeile mit +1 und eine erkundete mit -1 bei ``p = 0,05``: die
    erkundete steht fuer zwanzig Gelegenheiten. Ungewichtet waere das Mittel 0,
    gewichtet (1·1 + 20·(-1)) / 21 = -0,905.
    """
    zeilen = [
        _zeile(ergebnis_bp=1.0),
        _zeile(herkunft=Herkunft.ERKUNDET, wahrscheinlichkeit=0.05, ergebnis_bp=-1.0),
    ]
    assert gewichteter_mittelwert(zeilen) == pytest.approx((1.0 - 20.0) / 21.0)


def test_ohne_zeile_mit_ergebnis_gibt_es_keinen_mittelwert() -> None:
    """Kein Ersatzwert: ein Mittel aus nichts ist keine Null (V3)."""
    assert (
        gewichteter_mittelwert([_zeile(herkunft=Herkunft.ABGELEHNT, ergebnis_bp=None)])
        is None
    )


def test_der_erkundungsanteil_zaehlt_gegen_die_zeilen_mit_ergebnis() -> None:
    """Die Bezugsgroesse ist bewusst nicht die Gesamtzahl.

    Sonst liesse sich der Anteil beliebig klein rechnen, indem man mehr Absagen
    protokolliert -- ohne dass sich am Erkundeten etwas aendert.
    """
    zeilen = [
        _zeile(ergebnis_bp=1.0),
        _zeile(herkunft=Herkunft.ERKUNDET, wahrscheinlichkeit=0.05, ergebnis_bp=1.0),
        *[_zeile(herkunft=Herkunft.ABGELEHNT, ergebnis_bp=None) for _ in range(98)],
    ]
    assert erkundungsanteil(zeilen) == pytest.approx(0.5)


# =====================================================================
# A4 — Schwelle von der Ersatzheuristik entkoppeln
# =====================================================================
@pytest.mark.parametrize("klasse", sorted(ASSUMED_ROUND_TURN_COST_BPS))
def test_der_plausibilitaetsboden_liegt_echt_unter_der_annahme(klasse: str) -> None:
    """DER rote Eichfall zur Entkopplung -- ueber ALLE Klassen.

    Vor dieser Stufe waren beide Zahlen dieselbe: ``RiskManager._kostenbasis`` nahm die
    Annahmetabelle als Schwelle, gegen die eine gemessene Zahl antreten musste, UND als
    Rueckfall, wenn keine kam. Eine echte Messung von 0,30 bp wurde gegen die Annahme
    0,65 bp verworfen -- und danach galt 0,65 bp. Die Schwelle mass ihre eigene Ausgabe
    (Sperre V2).

    Setzt jemand beide Tabellen wieder gleich, ist dieser Fall sofort rot.
    """
    # Der Zugriff auf die Annahme geht direkt an die Tabelle: der Leser
    # ``assumed_cost_bps`` ist in Stufe 9 entfernt worden, weil ``stop_budget`` die
    # Tabelle ohnehin direkt liest -- zwei Lesearten derselben Zahl, von denen eine
    # keinen Aufrufer mehr hatte.
    boden = kostenpraemisse_bps(klasse)
    annahme = ASSUMED_ROUND_TURN_COST_BPS[klasse]
    assert boden is not None
    assert boden < annahme, (
        f"{klasse}: Boden {boden} >= Annahme {annahme} -- die Schwelle sitzt wieder "
        "auf der Ersatzheuristik."
    )


def test_beide_tabellen_kennen_dieselben_klassen() -> None:
    """Eine Klasse ohne Boden fiele stillschweigend auf 'kein Vergleich' zurueck."""
    assert set(KOSTENPRAEMISSE_BPS) == set(ASSUMED_ROUND_TURN_COST_BPS)


def test_der_boden_weist_unsinn_weiterhin_ab() -> None:
    """Der gruene Gegenfall zur Entkopplung: sie macht die Sperre nicht wirkungslos."""
    for klasse in sorted(KOSTENPRAEMISSE_BPS):
        boden = kostenpraemisse_bps(klasse)
        assert boden is not None
        assert boden > Decimal("0"), f"{klasse}: ein Boden von 0 waere kein Boden."


# =====================================================================
# Abnahme — die Auswertungstabelle traegt gekennzeichnete Absagen
# =====================================================================
def test_die_auswertung_enthaelt_gekennzeichnete_zeilen_aus_abgelehnten_signalen() -> (
    None
):
    """Der Abnahmefall, gegen die eingecheckte Aufzeichnung."""
    from tools.auswertung import tabelle_aus_journal

    zeilen = tabelle_aus_journal(AUFZEICHNUNG)
    abgelehnt = [z for z in zeilen if z.herkunft is Herkunft.ABGELEHNT]
    assert abgelehnt, "Keine einzige abgelehnte Zeile in der Auswertung."
    assert all(z.ergebnis_bp is None for z in abgelehnt), (
        "Eine abgelehnte Zeile darf kein Ergebnis tragen -- es gibt keines."
    )
    assert all(z.ablehnungsgrund for z in abgelehnt), (
        "Jede Absage traegt ihren Grund; ohne ihn ist die Zeile nutzlos."
    )
    gefahren = [z for z in zeilen if z.herkunft is Herkunft.GEFAHREN]
    assert gefahren, "Der gruene Gegenpart fehlt: keine gefahrene Zeile."
    assert any(z.ergebnis_bp is not None for z in gefahren)


def test_die_eingecheckte_aufzeichnung_traegt_die_abgelehnten_signale() -> None:
    """Sie tat es nicht -- in Stufe 5 habe ich sie als Messrauschen weggelassen.

    Die Korrektur steht in ``tools/aufzeichnung_redigieren.py`` an ``BEHALTEN``. Ohne
    diesen Fall faellt sie beim naechsten Aufraeumen wieder heraus.
    """
    kopf = json.loads(AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()[0])
    assert kopf["saetze_behalten"].get("eroeffnungsversuch", 0) > 0
    assert "eroeffnungsversuch" not in kopf["saetze_weggelassen"]


def test_die_aufzeichnung_weist_auch_weggelassene_FELDER_aus() -> None:
    """Ein weggelassenes Feld ist so verschwiegen wie ein weggelassener Satz."""
    kopf = json.loads(AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()[0])
    assert kopf["felder_weggelassen"] == ["schritte"]


def test_die_auswertung_laeuft_gegen_die_eingecheckte_aufzeichnung() -> None:
    """Bestaetigt durch Ausfuehrung, nicht durch Zusicherung."""
    lauf = subprocess.run(
        [sys.executable, "tools/auswertung.py", "--journal", str(AUFZEICHNUNG)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    assert "abgelehnt" in lauf.stdout
    assert "Ablehnungsgruende" in lauf.stdout
