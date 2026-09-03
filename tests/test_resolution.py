"""Aufloesung: die Rechnung, die entscheidet, ob eine Studie ueberhaupt sehen kann.

Der teuerste Fehler dieses Moduls waere kein Absturz, sondern ein zu **guenstiges**
Ergebnis: eine Studie, die als aufloesbar gilt und es nicht ist, misst Rauschen und
berichtet es als Befund. Die Tests unten pruefen darum besonders die Richtungen, in die
ein Fehler schmeicheln wuerde -- ueberlappende Fenster, zu grosse Ereigniszahl, zu
kleine Streuung.

Genau so ein Fehler stand hier: gerechnet wurde gegen die volle Ereigniszahl, gemessen
wird der DSR aber auf dem Out-of-Sample-Drittel. Die Faelle unter „Gegen die
Deflationsstichprobe" sind dazu die Eichfaelle -- sie waeren gegen die alte Fassung
allesamt fehlgeschlagen.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.backtest.ereignisstudie import (
    OOS_ANTEIL,
    Kerze,
    StudienError,
    bestaetige,
    studie,
)
from mt5_trading_ai.backtest.resolution import (
    DEFAULT_COST_FACTOR,
    DEFAULT_DSR_THRESHOLD,
    MIN_DEFLATIONSBEOBACHTUNGEN,
    MIN_EREIGNISSE,
    DeflationUnreachableError,
    ResolutionError,
    assess,
    deflation_observations,
    dispersion_bps,
    min_events_for_resolution,
    required_sharpe,
    window_returns_bps,
)

REPO = Path(__file__).resolve().parents[1]
ECHTE_DATEI = REPO / "config" / "aufloesung.json"

#: Die Zeile, an der der Fehler aufgefallen ist: K3 (Monatsende-Fixing) auf GBPJPY im
#: 1h-Fenster. Zahlen aus ``config/aufloesung.json`` und
#: ``ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt``.
K3_EREIGNISSE = 193
K3_GEMESSEN = 192
K3_STREUUNG = 14.1517
K3_KOSTEN = 1.8351
K3_VERSUCHE = 12

#: Ueberschrift des Vorbehalts in ``ABSCHLUSS-3a/01-AUFLOESUNG.md``. Solange
#: ``config/aufloesung.json`` nicht gegen ``OOS_ANTEIL`` gerechnet ist, muss dieser Text
#: dort stehen.
VORBEHALT_MARKE = "Vorbehalt zur gesamten Tabelle"


def _anteil_stimmt(roh: dict[str, Any]) -> bool:
    """Fuehrt die Messdatei den Anteil, auf dem die Deflation TATSAECHLICH laeuft?

    Geprueft wird der WERT, nicht die Anwesenheit des Schluessels. Die vorige Fassung
    fragte ``"oos_share" not in roh`` -- damit liess sich die Zusicherung auf den
    Vorbehalt durch EINEN nachgetragenen Schluessel abschalten, ohne dass eine einzige
    Zahl neu gemessen worden waere. Genau diese Bauart -- ein Melder, der die
    Anwesenheit eines Feldes fuer seinen Inhalt nimmt -- ist die Fehlerklasse, gegen
    die dieses ganze Vorhaben laeuft.

    ``True`` faellt ausdruecklich durch: in Python ist ``bool`` ein ``int``, und
    ``"oos_share": true`` waere sonst klaglos 1,0.
    """
    wert = roh.get("oos_share")
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        return False
    return abs(float(wert) - OOS_ANTEIL) <= 1e-9


def test_der_vorbehalt_haengt_am_wert_nicht_am_schluessel() -> None:
    """Eichfall zum Melder dieses Tests selbst.

    Gegen die vorige Fassung (``"oos_share" in roh``) sind die mittleren drei Zeilen
    rot: dort galt jede Datei als geprueft, der jemand den Schluessel nachgetragen hat.
    """
    assert not _anteil_stimmt({})
    assert not _anteil_stimmt({"oos_share": 1.0})
    assert not _anteil_stimmt({"oos_share": "1/3"})
    assert not _anteil_stimmt({"oos_share": True})
    assert _anteil_stimmt({"oos_share": OOS_ANTEIL})


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
    assert (
        deflated_sharpe_ratio(observed_sharpe=s, observations=500, trials=8)
        >= DEFAULT_DSR_THRESHOLD
    )
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
# ``oos_share=1.0`` heisst hier ausdruecklich: in diesen Faellen IST die Ereigniszahl
# die Stichprobe der Deflation. Die Faelle pruefen die reinen Zusammenhaenge des
# Verhaeltnisses; der Anteil selbst hat weiter unten seinen eigenen Abschnitt.
def test_aufloesbar_wenn_nachweisbarer_effekt_unter_der_schwelle_liegt() -> None:
    urteil = assess(
        events=6000, trials=12, dispersion=23.0, cost_bps=1.10, oos_share=1.0
    )
    assert urteil.resolvable is True
    assert urteil.ratio < 1.0
    assert urteil.needed_bps == pytest.approx(DEFAULT_COST_FACTOR * 1.10)


def test_blind_wenn_die_streuung_zu_gross_ist() -> None:
    urteil = assess(
        events=60, trials=12, dispersion=200.0, cost_bps=0.85, oos_share=1.0
    )
    assert urteil.resolvable is False
    assert urteil.ratio > 1.0


def test_mehr_ereignisse_machen_es_nie_schlechter() -> None:
    schlecht = assess(
        events=100, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    )
    besser = assess(
        events=10_000, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    )
    assert besser.ratio < schlecht.ratio


def test_groessere_streuung_macht_es_nie_besser() -> None:
    eng = assess(events=1000, trials=8, dispersion=10.0, cost_bps=1.0, oos_share=1.0)
    weit = assess(events=1000, trials=8, dispersion=100.0, cost_bps=1.0, oos_share=1.0)
    assert weit.ratio > eng.ratio


def test_hoehere_kosten_verlangen_einen_groesseren_effekt_und_helfen_der_aufloesung() -> (
    None
):
    """Hoehere Kosten heben die wirtschaftliche Schwelle — das erleichtert den Nachweis.

    Das klingt verkehrt herum und ist es nicht: die Studie muss nur zeigen, dass der
    Effekt die Kosten uebersteigt. Bei hohen Kosten ist die zu belegende Groesse
    groesser und damit leichter von Null zu trennen. Der Preis dafuer steht woanders --
    ein solcher Effekt muss erst einmal existieren.
    """
    billig = assess(events=1000, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0)
    teuer = assess(events=1000, trials=8, dispersion=50.0, cost_bps=10.0, oos_share=1.0)
    assert teuer.ratio < billig.ratio


@pytest.mark.parametrize(
    "feld,wert",
    [
        ("dispersion", 0.0),
        ("dispersion", -1.0),
        ("cost_bps", 0.0),
        ("cost_factor", 0.0),
        ("oos_share", 0.0),
        ("oos_share", -0.5),
        ("oos_share", 1.5),
    ],
)
def test_nicht_positive_eingaben_sind_fehler(feld: str, wert: float) -> None:
    basis = dict(events=100, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0)
    basis[feld] = wert  # type: ignore[assignment]
    with pytest.raises(ResolutionError):
        assess(**basis)  # type: ignore[arg-type]


# --- Wie viele Ereignisse braeuchte es? -----------------------------------
def test_mindestereigniszahl_liegt_an_der_kippstelle() -> None:
    n = min_events_for_resolution(
        trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    )
    assert n is not None
    assert assess(
        events=n, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    ).resolvable
    assert not assess(
        events=n - 1, trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    ).resolvable


def test_mindestereigniszahl_ist_none_wenn_es_nie_reicht() -> None:
    """Eine Streuung, die auch bei einer Million Ereignissen nicht reicht."""
    assert (
        min_events_for_resolution(
            trials=8,
            dispersion=100_000.0,
            cost_bps=0.01,
            oos_share=1.0,
            ceiling=10_000,
        )
        is None
    )


def test_mindestereigniszahl_wirft_nicht_an_ihrem_eigenen_rand() -> None:
    """Eichfall. Vorher kam hier ein ``ResolutionError`` statt einer Zahl.

    Bei einer kleinen Streuung liegt die Kippstelle unmittelbar an der unteren
    Suchgrenze. Die suchte frueher ab „zwei Beobachtungen" -- also unterhalb dessen,
    worueber ``assess`` ueberhaupt urteilt --, und die Binaersuche landete auf einer
    Stichprobe, fuer die selbst eine Sharpe von 5,0 die Deflationsschwelle nicht
    erreicht. Der zugesicherte Rueckgabetyp ``int | None`` war damit nicht eingeloest:
    die Funktion warf. Der Aufruf in ``tools/aufloesung.py`` lag ausserhalb des
    ``try``, ein Messlauf waere dort abgebrochen -- nach der gedruckten Tabelle und vor
    dem Schreiben der Messdatei.
    """
    n = min_events_for_resolution(
        trials=12, dispersion=0.5, cost_bps=1.0, oos_share=OOS_ANTEIL
    )
    assert n == 58, "die kleinste Ereigniszahl, aus der 20 Beobachtungen werden"
    assert assess(
        events=n, trials=12, dispersion=0.5, cost_bps=1.0, oos_share=OOS_ANTEIL
    ).resolvable


def test_mindestereigniszahl_bleibt_eine_zahl_wenn_die_schwelle_unerreichbar_ist() -> (
    None
):
    """Auch am oberen Ende der Versuchszahl bleibt die Antwort eine Zahl.

    Bei sehr vielen Versuchen ist die Schwelle fuer kleine Stichproben mit KEINER
    Sharpe erreichbar; ``required_sharpe`` wirft dort. Das ist kein Rechenfehler,
    sondern ein „nicht aufloesbar" in seiner schaerfsten Form, und die Suche liest es
    genau so -- an einem eigenen Fehlertyp, nicht an einem breiten ``except``.
    """
    with pytest.raises(DeflationUnreachableError):
        required_sharpe(MIN_DEFLATIONSBEOBACHTUNGEN, 1_000_000)
    n = min_events_for_resolution(
        trials=1_000_000, dispersion=0.5, cost_bps=1.0, oos_share=OOS_ANTEIL
    )
    assert n is not None and n > 58


def test_mindestereigniszahl_ist_none_wenn_die_obergrenze_zu_klein_ist() -> None:
    """Reicht ``ceiling`` nicht fuer eine bestaetigungsfaehige Stichprobe: ``None``.

    Nicht ein Fehler und nicht eine geschmeichelte Zahl -- ``None`` heisst hier genau
    das, was der Docstring zusagt: „so viele Ereignisse gibt es in diesem Rahmen nicht".
    """
    assert (
        min_events_for_resolution(
            trials=8, dispersion=1.0, cost_bps=1.0, oos_share=OOS_ANTEIL, ceiling=40
        )
        is None
    )
    assert (
        min_events_for_resolution(
            trials=8, dispersion=1.0, cost_bps=1.0, oos_share=1.0, ceiling=10
        )
        is None
    )


def test_mindestereigniszahl_zaehlt_ereignisse_nicht_beobachtungen() -> None:
    """Wer nur ein Drittel deflationiert, braucht rund dreimal so viele Ereignisse.

    Die Zahl soll direkt beantwortbar sein („so viele Monatsenden brauchen wir"). Gaebe
    sie Deflationsbeobachtungen zurueck, unterschaetzte jeder Leser den Bedarf um genau
    den Kehrwert des Anteils -- und zwar in der schmeichelnden Richtung.
    """
    voll = min_events_for_resolution(
        trials=8, dispersion=50.0, cost_bps=1.0, oos_share=1.0
    )
    drittel = min_events_for_resolution(
        trials=8, dispersion=50.0, cost_bps=1.0, oos_share=OOS_ANTEIL
    )
    assert voll is not None and drittel is not None
    assert drittel > voll
    assert 2.5 < drittel / voll < 3.5
    assert deflation_observations(drittel, oos_share=OOS_ANTEIL) >= voll


# --- Gegen die Deflationsstichprobe ---------------------------------------
def _gerade_kerzen(anzahl: int) -> list[Kerze]:
    """Stundenkerzen mit abwechselndem Vorzeichen -- erfunden, aber messbar.

    Abwechselnd, weil ``messe_ereignis`` ein Ereignis ohne Richtung in der Vorstunde
    verwirft: eine Reihe aus lauter Nullrenditen ergaebe keine einzige Beobachtung.
    """
    start = datetime(2020, 1, 6, tzinfo=UTC)
    kerzen: list[Kerze] = []
    kurs = 100.0
    for i in range(anzahl):
        zu = kurs * (1.0 + (0.001 if i % 2 == 0 else -0.0008))
        kerzen.append(Kerze(ts=start + timedelta(hours=i), open=kurs, close=zu))
        kurs = zu
    return kerzen


def _leeres_register(tmp_path: Path) -> Path:
    """Ein eigenes, leeres Versuchsregister fuer diesen Testlauf.

    Ohne Angabe griffe ``bestaetige`` auf ``<repo>/TRIALS.jsonl`` zu -- und die Datei
    ist per ``.gitignore`` NICHT versioniert. Ein Fall, der sie braucht, ist auf dem
    Rechner des Erbauers gruen und auf jedem frischen Klon rot. Ein leeres Register ist
    fuer ``deflation_trials`` kein Fehler, sondern „dies ist der erste Versuch"; die
    Versuchszahl geht in ``dsr_n`` ohnehin nicht ein.
    """
    register = tmp_path / "TRIALS.jsonl"
    register.write_text("", encoding="utf-8")
    return register


@pytest.mark.parametrize(
    "kerzenzahl,trennt_abschneiden_von_runden", [(320, False), (324, True)]
)
def test_deflationsstichprobe_deckt_sich_mit_der_ereignisstudie(
    kerzenzahl: int, trennt_abschneiden_von_runden: bool, tmp_path: Path
) -> None:
    """Die Umrechnung wird nicht nachgebaut, sondern gegen die Studie gehalten.

    ``bestaetige`` meldet in ``Bestaetigung.dsr_n``, wie viele Beobachtungen der DSR
    tatsaechlich gesehen hat. Genau diese Zahl muss ``deflation_observations`` liefern.
    Waere hier nur die Formel aus der Studie abgeschrieben, pruefte der Fall die
    Abschrift und nicht die Uebereinstimmung -- und ein Abriss zwischen beiden Modulen
    bliebe unsichtbar.

    ZWEI LAEUFE, WEIL EINER NICHTS UNTERSCHEIDET
    --------------------------------------------
    Mit 320 Kerzen sind 78 Ereignisse messbar, und 78 x 2/3 ist glatt 52: abschneiden,
    runden und aufrunden liefern dasselbe. Der Fall haette also gruen bestanden, wenn
    ``deflation_observations`` auf ``round`` gewechselt waere -- ausgerechnet die
    Rundungsart, die sein Docstring als tragend bezeichnet. Mit 324 Kerzen sind es 79,
    und dort trennen sich die beiden um einen ganzen Wert (27 gegen 26). Der Parameter
    ``trennt_abschneiden_von_runden`` haelt fest, welcher Lauf das leisten kann.
    """
    kerzen = _gerade_kerzen(kerzenzahl)
    ereignisse = [k.ts for k in kerzen[4:-4:4]]
    ergebnis, werte = studie(
        kandidat="erfunden",
        instrument="ERFUNDEN",
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
    )
    bestaetigung = bestaetige(
        werte,
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
        saat=7,
        register_pfad=_leeres_register(tmp_path),
    )
    assert bestaetigung.dsr_n == deflation_observations(
        ergebnis.n_gemessen, oos_share=OOS_ANTEIL
    )
    assert bestaetigung.dsr_n < ergebnis.n_gemessen

    gerundet = ergebnis.n_gemessen - round(ergebnis.n_gemessen * (1.0 - OOS_ANTEIL))
    assert (gerundet != bestaetigung.dsr_n) is trennt_abschneiden_von_runden, (
        f"{ergebnis.n_gemessen} gemessene Ereignisse: abschneiden gibt "
        f"{bestaetigung.dsr_n}, runden {gerundet} -- dieser Lauf sollte die beiden "
        f"{'unterscheiden' if trennt_abschneiden_von_runden else 'nicht unterscheiden'}"
    )


def test_die_untergrenzen_sind_die_der_bestaetigung(tmp_path: Path) -> None:
    """Woher ``MIN_EREIGNISSE`` und ``MIN_DEFLATIONSBEOBACHTUNGEN`` kommen -- gemessen.

    Beide Zahlen stehen in ``ereignisstudie.py`` als nackte Literale in
    ``studie``/``bestaetige`` und lassen sich von aussen nicht importieren. Statt sie
    hier zu behaupten, fragt dieser Fall die echten Funktionen: was sie ablehnen, muss
    ``assess`` ablehnen, und wo sie laufen, muss ``assess`` urteilen. Laufen die
    Grenzen auseinander, wird es hier rot -- nicht erst in einer Studie, die als
    „aufloesbar" gilt und deren Bestaetigung dann wirft.
    """
    register = _leeres_register(tmp_path)

    # (a) Unter MIN_EREIGNISSE messbaren Werten faengt die Studie gar nicht erst an.
    kurz = _gerade_kerzen(108)
    with pytest.raises(StudienError, match="messbare Ereignisse"):
        studie(
            kandidat="erfunden",
            instrument="ERFUNDEN",
            kerzen=kurz,
            ereignisse=[k.ts for k in kurz[4:-4:4]],
            fenster_stunden=1.0,
            k_bps=1.0,
        )
    with pytest.raises(ResolutionError, match="bestaetige"):
        assess(events=25, trials=12, dispersion=50.0, cost_bps=1.0, oos_share=1.0)
    assert 25 < MIN_EREIGNISSE

    # (b) Genau an der Grenze des Out-of-Sample-Teils: 57 Ereignisse ergeben 19
    #     Beobachtungen und werden abgewiesen, 58 ergeben 20 und laufen durch.
    for kerzenzahl, erwartet_laeuft in ((234, False), (238, True)):
        kerzen = _gerade_kerzen(kerzenzahl)
        ereignisse = [k.ts for k in kerzen[4:-4:4]]
        ergebnis, werte = studie(
            kandidat="erfunden",
            instrument="ERFUNDEN",
            kerzen=kerzen,
            ereignisse=ereignisse,
            fenster_stunden=1.0,
            k_bps=1.0,
        )
        beobachtungen = deflation_observations(
            ergebnis.n_gemessen, oos_share=OOS_ANTEIL
        )
        assert (beobachtungen >= MIN_DEFLATIONSBEOBACHTUNGEN) is erwartet_laeuft
        if erwartet_laeuft:
            bestaetigung = bestaetige(
                werte,
                kerzen=kerzen,
                ereignisse=ereignisse,
                fenster_stunden=1.0,
                k_bps=1.0,
                saat=7,
                register_pfad=register,
            )
            assert bestaetigung.dsr_n == MIN_DEFLATIONSBEOBACHTUNGEN
            assert (
                assess(
                    events=ergebnis.n_gemessen,
                    trials=12,
                    dispersion=50.0,
                    cost_bps=1.0,
                    oos_share=OOS_ANTEIL,
                ).deflation_events
                == MIN_DEFLATIONSBEOBACHTUNGEN
            )
        else:
            with pytest.raises(StudienError, match="Out-of-Sample-Drittel zu klein"):
                bestaetige(
                    werte,
                    kerzen=kerzen,
                    ereignisse=ereignisse,
                    fenster_stunden=1.0,
                    k_bps=1.0,
                    saat=7,
                    register_pfad=register,
                )
            with pytest.raises(ResolutionError, match="verlangt"):
                assess(
                    events=ergebnis.n_gemessen,
                    trials=12,
                    dispersion=50.0,
                    cost_bps=1.0,
                    oos_share=OOS_ANTEIL,
                )


def test_aufloesbar_ohne_bestaetigungsfaehige_stichprobe_gibt_es_nicht() -> None:
    """Eichfall. Gegen die vorige Fassung stand hier ein gruenes „aufloesbar".

    ``assess`` hatte eine eigene Untergrenze von ZWEI Beobachtungen -- drei
    Groessenordnungen unter der, die ``bestaetige`` tatsaechlich verlangt. Damit galt
    diese Kombination mit einem Verhaeltnis von 0,975 als aufloesbar, obwohl die
    Bestaetigung fuer dieselben Zahlen „Out-of-Sample-Drittel zu klein: 18" wirft. Die
    Abweichung zeigte in die schmeichelnde Richtung: sie liess Studien zu, die niemand
    haette bestaetigen koennen.
    """
    with pytest.raises(ResolutionError, match="verlangt 20"):
        assess(events=52, trials=12, dispersion=3.0, cost_bps=1.0, oos_share=OOS_ANTEIL)

    # Zwei Ereignisse mehr aendern daran nichts -- es fehlt die Stichprobe, nicht ein
    # Zehntel im Verhaeltnis.
    with pytest.raises(ResolutionError, match="verlangt 20"):
        assess(events=57, trials=12, dispersion=3.0, cost_bps=1.0, oos_share=OOS_ANTEIL)
    assert (
        assess(
            events=58, trials=12, dispersion=3.0, cost_bps=1.0, oos_share=OOS_ANTEIL
        ).deflation_events
        == MIN_DEFLATIONSBEOBACHTUNGEN
    )


def test_k3_gbpjpy_war_gegen_die_deflationsstichprobe_nie_aufloesbar() -> None:
    """Der Eichfall. Gegen die alte Fassung waere er fehlgeschlagen.

    K3 (Monatsende-Fixing, GBPJPY) galt mit einem Verhaeltnis von 0,62 als aufloesbar
    und bekam deshalb das 1h-Fenster zugewiesen. Gerechnet war das gegen N = 193, den
    ganzen Ereignisvorrat. Der DSR lief dann auf 64 Ereignissen -- fuer die war dasselbe
    Modul schon damals bei 1,12, also blind. Die Studie wurde auf einer Frage gefahren,
    die sie nicht beantworten konnte, und hat einen der zwoelf Versuche gekostet.

    Die drei Zahlen unten halten das fest: was dastand, was richtig gewesen waere, und
    was fuer die tatsaechlich gemessenen 192 Ereignisse gilt.
    """
    voll = assess(
        events=K3_EREIGNISSE,
        trials=K3_VERSUCHE,
        dispersion=K3_STREUUNG,
        cost_bps=K3_KOSTEN,
        oos_share=1.0,
    )
    assert voll.ratio == pytest.approx(0.6229, abs=1e-3)
    assert voll.resolvable, "die alte, zu guenstige Lesart -- hier nur als Beleg"

    geplant = assess(
        events=K3_EREIGNISSE,
        trials=K3_VERSUCHE,
        dispersion=K3_STREUUNG,
        cost_bps=K3_KOSTEN,
        oos_share=OOS_ANTEIL,
    )
    assert geplant.deflation_events == 65
    assert geplant.ratio == pytest.approx(1.1121, abs=1e-3)
    assert not geplant.resolvable

    gemessen = assess(
        events=K3_GEMESSEN,
        trials=K3_VERSUCHE,
        dispersion=K3_STREUUNG,
        cost_bps=K3_KOSTEN,
        oos_share=OOS_ANTEIL,
    )
    assert gemessen.deflation_events == 64, (
        "die Zahl aus 07-AUSGABEN/ereignisstudie.txt"
    )
    assert gemessen.ratio == pytest.approx(1.1217, abs=1e-3)
    assert not gemessen.resolvable


def test_ein_kleinerer_oos_anteil_macht_es_nie_besser() -> None:
    """Je weniger die Deflation sieht, desto hoeher die Huerde. Nie umgekehrt."""
    vorher = None
    for anteil in (1.0, 0.75, 0.5, OOS_ANTEIL, 0.2):
        urteil = assess(
            events=3000, trials=12, dispersion=50.0, cost_bps=1.0, oos_share=anteil
        )
        if vorher is not None:
            assert urteil.ratio > vorher
        vorher = urteil.ratio


def test_der_oos_anteil_hat_keinen_vorgabewert() -> None:
    """Ein Vorgabewert waere der stille Rueckfall auf genau diesen Fehler.

    Solange ``assess`` ohne Angabe des Anteils rechnet, sieht jeder Aufruf richtig aus
    und ist es nicht. Der Aufrufer muss sich aeussern.
    """
    with pytest.raises(TypeError, match="oos_share"):
        assess(events=193, trials=12, dispersion=14.15, cost_bps=1.84)  # type: ignore[call-arg]


def test_zu_kleine_deflationsstichprobe_ist_ein_fehler_kein_ergebnis() -> None:
    """Fail-closed: aus drei Ereignissen wird bei einem Drittel keine Stichprobe."""
    with pytest.raises(ResolutionError, match="Deflation"):
        assess(events=3, trials=12, dispersion=50.0, cost_bps=1.0, oos_share=OOS_ANTEIL)


def test_deflationsstichprobe_schneidet_ab_statt_zu_runden() -> None:
    """``int`` statt ``round`` -- und zwar wie in der Studie, nicht wie es huebsch ist.

    Bei kleinen Stichproben macht das einen ganzen Wert Unterschied, und der Wert zaehlt:
    er geht in die Wurzel der noetigen Sharpe ein.
    """
    assert deflation_observations(192, oos_share=OOS_ANTEIL) == 64
    assert deflation_observations(193, oos_share=OOS_ANTEIL) == 65
    assert deflation_observations(472, oos_share=OOS_ANTEIL) == 158
    assert deflation_observations(100, oos_share=1.0) == 100


@pytest.mark.parametrize("wert", [0.0, -0.1, 1.0001, 2.0])
def test_unmoeglicher_oos_anteil_ist_ein_fehler(wert: float) -> None:
    with pytest.raises(ResolutionError, match="oos_share"):
        deflation_observations(100, oos_share=wert)


# --- Gegen die echte Messdatei --------------------------------------------
def test_die_echte_aufloesungsdatei_ist_in_sich_stimmig() -> None:
    """Positivtest gegen die gemessene Datei: jede Zeile muss nachrechenbar sein.

    Rechnet die Datei nicht gegen ``OOS_ANTEIL``, stammt sie aus der Zeit vor der
    Korrektur; sie wird dann so nachgerechnet, wie sie entstanden ist. Damit sie nicht
    stillschweigend weiterlebt, darf sie in diesem Zustand nur zusammen mit dem
    Vorbehalt in ``ABSCHLUSS-3a/01-AUFLOESUNG.md`` existieren. Wer den Vorbehalt
    streicht, ohne neu zu messen, faellt hier auf.

    Massgeblich ist der WERT von ``oos_share``, nicht sein Vorhandensein -- siehe
    ``_anteil_stimmt``. Ein nachgetragener Schluessel ist keine Messung, und er darf
    diese Zusicherung nicht abschalten.
    """
    import json

    if not ECHTE_DATEI.is_file():
        pytest.skip("config/aufloesung.json nicht vorhanden")
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    eintraege = roh["entries"]
    assert eintraege, "Datei ohne Eintraege"

    stimmig = _anteil_stimmt(roh)
    anteil = float(roh["oos_share"]) if stimmig else 1.0
    for e in eintraege:
        nach = assess(
            events=e["events"],
            trials=roh["trials_assumed"],
            dispersion=e["dispersion_bps"],
            cost_bps=e["cost_bps"],
            oos_share=anteil,
        )
        assert nach.ratio == pytest.approx(e["ratio"], abs=1e-3), (
            f"{e['instrument']}/{e['window']}/{e['frequency']}: "
            f"Datei sagt {e['ratio']}, nachgerechnet {nach.ratio}"
        )
        assert nach.resolvable == e["resolvable"]

    if not stimmig:
        bericht = (REPO / "ABSCHLUSS-3a" / "01-AUFLOESUNG.md").read_text(
            encoding="utf-8"
        )
        assert VORBEHALT_MARKE in bericht, (
            "config/aufloesung.json ist nicht gegen die Deflationsstichprobe "
            "gerechnet, aber 01-AUFLOESUNG.md fuehrt den Vorbehalt "
            f'„{VORBEHALT_MARKE}" nicht mehr'
        )


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
