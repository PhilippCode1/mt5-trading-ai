"""Aufloesung: die Rechnung, die entscheidet, ob eine Studie ueberhaupt sehen kann.

Der teuerste Fehler dieses Moduls waere kein Absturz, sondern ein zu **guenstiges**
Ergebnis: eine Studie, die als aufloesbar gilt und es nicht ist, misst Rauschen und
berichtet es als Befund. Die Tests unten pruefen darum besonders die Richtungen, in die
ein Fehler schmeicheln wuerde -- ueberlappende Fenster, zu grosse Ereigniszahl, zu
kleine Streuung.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.resolution import (
    DEFAULT_COST_FACTOR,
    DEFAULT_DSR_THRESHOLD,
    ResolutionError,
    assess,
    dispersion_bps,
    min_events_for_resolution,
    required_sharpe,
    window_returns_bps,
)

REPO = Path(__file__).resolve().parents[1]
ECHTE_DATEI = REPO / "config" / "aufloesung.json"


# --- required_sharpe ------------------------------------------------------
def test_noetige_sharpe_faellt_mit_der_ereigniszahl() -> None:
    """Mehr Ereignisse, kleinere Huerde. Das ist der ganze Grund fuer haeufige Kandidaten."""
    wenige = required_sharpe(60, 8)
    viele = required_sharpe(6000, 8)
    assert viele < wenige
    assert viele < wenige / 5  # Groessenordnung, nicht nur Vorzeichen


def test_noetige_sharpe_steigt_mit_der_versuchszahl() -> None:
    """Wer viel sucht, muss mehr finden — das ist die Deflation."""
    assert required_sharpe(1000, 1) < required_sharpe(1000, 12)


def test_noetige_sharpe_erreicht_die_schwelle_genau() -> None:
    """Der zurueckgegebene Wert liegt auf der Schwelle, nicht darueber oder darunter."""
    from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio

    s = required_sharpe(500, 8)
    assert deflated_sharpe_ratio(
        observed_sharpe=s, observations=500, trials=8
    ) >= DEFAULT_DSR_THRESHOLD
    knapp_darunter = deflated_sharpe_ratio(
        observed_sharpe=s * 0.99, observations=500, trials=8
    )
    assert knapp_darunter < DEFAULT_DSR_THRESHOLD


def test_zu_wenige_beobachtungen_sind_ein_fehler() -> None:
    with pytest.raises(ResolutionError, match="observations"):
        required_sharpe(1, 8)


def test_nicht_positive_versuchszahl_ist_ein_fehler() -> None:
    with pytest.raises(ResolutionError, match="trials"):
        required_sharpe(100, 0)


def test_schwelle_ausserhalb_null_bis_eins_ist_ein_fehler() -> None:
    with pytest.raises(ResolutionError, match="threshold"):
        required_sharpe(100, 8, threshold=1.5)


# --- Fensterrenditen ------------------------------------------------------
def test_fenster_ueberlappen_nicht() -> None:
    """Ueberlappende Fenster wuerden dieselbe Bewegung mehrfach zaehlen.

    Die Streuung saehe dann kleiner aus, als sie ist, und die Aufloesung besser --
    ein Fehler in genau der Richtung, die schmeichelt.
    """
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]
    renditen = window_returns_bps(closes, 3)
    # Fenster 0->3 und 3->6, nicht 0->3, 1->4, 2->5 ...
    assert len(renditen) == 2
    assert renditen[0] == pytest.approx((103.0 - 100.0) / 100.0 * 10_000)
    assert renditen[1] == pytest.approx((106.0 - 103.0) / 103.0 * 10_000)


def test_fensterlaenge_eins_ergibt_balkenrenditen() -> None:
    renditen = window_returns_bps([100.0, 110.0, 121.0], 1)
    assert len(renditen) == 2
    assert renditen[0] == pytest.approx(1000.0)


def test_nicht_positiver_kurs_ist_ein_fehler_kein_ueberspringen() -> None:
    with pytest.raises(ResolutionError):
        window_returns_bps([100.0, 0.0, 50.0], 1)


def test_fensterlaenge_null_ist_ein_fehler() -> None:
    with pytest.raises(ResolutionError):
        window_returns_bps([1.0, 2.0], 0)


def test_zu_kurze_reihe_ergibt_keine_fenster() -> None:
    assert window_returns_bps([100.0, 101.0], 5) == []


# --- Streuung -------------------------------------------------------------
def test_streuung_ist_die_standardabweichung() -> None:
    import statistics

    werte = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert dispersion_bps(werte) == pytest.approx(statistics.stdev(werte))


def test_streuung_braucht_mindestens_zwei_fenster() -> None:
    with pytest.raises(ResolutionError):
        dispersion_bps([1.0])


# --- Das Urteil -----------------------------------------------------------
def test_aufloesbar_wenn_nachweisbarer_effekt_unter_der_schwelle_liegt() -> None:
    urteil = assess(events=6000, trials=12, dispersion=23.0, cost_bps=1.10)
    assert urteil.resolvable is True
    assert urteil.ratio < 1.0
    assert urteil.needed_bps == pytest.approx(DEFAULT_COST_FACTOR * 1.10)


def test_blind_wenn_die_streuung_zu_gross_ist() -> None:
    urteil = assess(events=60, trials=12, dispersion=200.0, cost_bps=0.85)
    assert urteil.resolvable is False
    assert urteil.ratio > 1.0


def test_mehr_ereignisse_machen_es_nie_schlechter() -> None:
    schlecht = assess(events=100, trials=8, dispersion=50.0, cost_bps=1.0)
    besser = assess(events=10_000, trials=8, dispersion=50.0, cost_bps=1.0)
    assert besser.ratio < schlecht.ratio


def test_groessere_streuung_macht_es_nie_besser() -> None:
    eng = assess(events=1000, trials=8, dispersion=10.0, cost_bps=1.0)
    weit = assess(events=1000, trials=8, dispersion=100.0, cost_bps=1.0)
    assert weit.ratio > eng.ratio


def test_hoehere_kosten_verlangen_einen_groesseren_effekt_und_helfen_der_aufloesung() -> None:
    """Hoehere Kosten heben die wirtschaftliche Schwelle — das erleichtert den Nachweis.

    Das klingt verkehrt herum und ist es nicht: die Studie muss nur zeigen, dass der
    Effekt die Kosten uebersteigt. Bei hohen Kosten ist die zu belegende Groesse
    groesser und damit leichter von Null zu trennen. Der Preis dafuer steht woanders --
    ein solcher Effekt muss erst einmal existieren.
    """
    billig = assess(events=1000, trials=8, dispersion=50.0, cost_bps=1.0)
    teuer = assess(events=1000, trials=8, dispersion=50.0, cost_bps=10.0)
    assert teuer.ratio < billig.ratio


@pytest.mark.parametrize(
    "feld,wert",
    [("dispersion", 0.0), ("dispersion", -1.0), ("cost_bps", 0.0), ("cost_factor", 0.0)],
)
def test_nicht_positive_eingaben_sind_fehler(feld: str, wert: float) -> None:
    basis = dict(events=100, trials=8, dispersion=50.0, cost_bps=1.0)
    basis[feld] = wert  # type: ignore[assignment]
    with pytest.raises(ResolutionError):
        assess(**basis)  # type: ignore[arg-type]


# --- Wie viele Ereignisse braeuchte es? -----------------------------------
def test_mindestereigniszahl_liegt_an_der_kippstelle() -> None:
    n = min_events_for_resolution(trials=8, dispersion=50.0, cost_bps=1.0)
    assert n is not None
    assert assess(events=n, trials=8, dispersion=50.0, cost_bps=1.0).resolvable
    assert not assess(events=n - 1, trials=8, dispersion=50.0, cost_bps=1.0).resolvable


def test_mindestereigniszahl_ist_none_wenn_es_nie_reicht() -> None:
    """Eine Streuung, die auch bei einer Million Ereignissen nicht reicht."""
    assert min_events_for_resolution(
        trials=8, dispersion=100_000.0, cost_bps=0.01, ceiling=10_000
    ) is None


# --- Gegen die echte Messdatei --------------------------------------------
def test_die_echte_aufloesungsdatei_ist_in_sich_stimmig() -> None:
    """Positivtest gegen die gemessene Datei: jede Zeile muss nachrechenbar sein."""
    import json

    if not ECHTE_DATEI.is_file():
        pytest.skip("config/aufloesung.json nicht vorhanden")
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    eintraege = roh["entries"]
    assert eintraege, "Datei ohne Eintraege"
    for e in eintraege:
        nach = assess(
            events=e["events"],
            trials=roh["trials_assumed"],
            dispersion=e["dispersion_bps"],
            cost_bps=e["cost_bps"],
        )
        assert nach.ratio == pytest.approx(e["ratio"], abs=1e-3), (
            f"{e['instrument']}/{e['window']}/{e['frequency']}: "
            f"Datei sagt {e['ratio']}, nachgerechnet {nach.ratio}"
        )
        assert nach.resolvable == e["resolvable"]


def test_monatliche_kandidaten_loesen_nur_im_stundenfenster_auf() -> None:
    """Der Befund, der K3 sein Fenster gab — festgehalten.

    Die erste Fassung dieses Tests verlangte, dass **keine** monatliche Kombination
    aufloest. Das galt, solange die Messung auf zwei Jahren H1-Historie stand. Mit der
    tatsaechlich verfuegbaren Tiefe (elf Jahre) loest die monatliche Frage im
    1h-Fenster auf und im 4h-Fenster nicht — und genau das entschied, in welchem
    Fenster K3 (Monatsende-Fixing) laeuft. Kehrt sich das um, muss es auffallen.
    """
    import json

    if not ECHTE_DATEI.is_file():
        pytest.skip("config/aufloesung.json nicht vorhanden")
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    monatlich = [e for e in roh["entries"] if e["frequency"] == "monatlich"]
    assert monatlich, "keine monatlichen Kombinationen in der Datei"

    aufloesbar = [e for e in monatlich if e["resolvable"]]
    assert aufloesbar, "keine monatliche Kombination loest mehr auf — K3 faellt damit"
    assert all(e["window"] == "1h" for e in aufloesbar), (
        "eine monatliche Kombination loest ausserhalb des 1h-Fensters auf; "
        f"gefunden: {sorted({(e['instrument'], e['window']) for e in aufloesbar})}"
    )

    vier_stunden = [
        e for e in monatlich if e["window"] == "4h" and e["instrument"] == "GBPJPY"
    ]
    assert vier_stunden and not vier_stunden[0]["resolvable"], (
        "GBPJPY/4h/monatlich gilt wieder als aufloesbar — dann ist die "
        "Fensterwahl fuer K3 neu zu begruenden"
    )


def test_eurusd_reihe_beginnt_nicht_vor_dem_euro() -> None:
    """Vor 1999 gab es den Euro nicht — was das Terminal davor liefert, ist Rueckrechnung.

    Das Terminal gibt EURUSD-Tageskerzen ab 1981 heraus, nahtlos an die echte Reihe
    angesetzt. Es sind 4.480 Kerzen, sie wuerden N um 71 % aufblaehen, und sie stammen
    aus einem anderen Streuungsregime (67,1 gegen 58,1 bp). Faellt der Schnitt in
    ``tools/aufloesung.py::FRUEHESTE_KERZE`` weg, waechst die Ereigniszahl still an —
    also in der schmeichelnden Richtung, und ohne dass es jemandem auffiele.
    """
    import json

    manifeste = sorted((REPO / "config" / "reihen").glob("EURUSD_*.manifest.json"))
    if not manifeste:
        pytest.skip("keine EURUSD-Manifeste vorhanden")
    for pfad in manifeste:
        man = json.loads(pfad.read_text(encoding="utf-8"))
        assert man["first"] >= "1999-01-01", (
            f"{pfad.name} beginnt am {man['first']} — vor der Einfuehrung des Euro"
        )


def test_wurzel_t_naeherung_ist_kein_ersatz_fuer_die_messung() -> None:
    """Die Naeherung aus dem Auftrag gegen die Messung — sie weicht erheblich ab.

    Der Auftrag naeherte die Fensterstreuung als ATR(H1) mal Wurzel der Fensterlaenge.
    Gemessen ist sie bei GBPJPY im 4h-Fenster rund 31 bp statt der genaeherten 23 bp --
    ein Drittel mehr, und genug, um die monatliche Kombination von 'aufloesbar' auf
    'blind' zu kippen. Der Test haelt fest, dass die Naeherung nicht ausreicht.
    """
    import json

    if not ECHTE_DATEI.is_file():
        pytest.skip("config/aufloesung.json nicht vorhanden")
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    gemessen = {
        (e["instrument"], e["window"]): e["dispersion_bps"] for e in roh["entries"]
    }
    atr_h1 = {"EURUSD": 10.04, "GBPJPY": 11.72, "XAUUSD": 41.80}
    for instrument, atr in atr_h1.items():
        schluessel = (instrument, "4h")
        if schluessel not in gemessen:
            continue
        genaehert = atr * math.sqrt(4)
        assert genaehert != pytest.approx(gemessen[schluessel], rel=0.05), (
            f"{instrument}: Naeherung {genaehert:.1f} und Messung "
            f"{gemessen[schluessel]:.1f} liegen naeher beieinander als erwartet — "
            "der Befund, der A1.3 begruendet, waere damit hinfaellig"
        )
