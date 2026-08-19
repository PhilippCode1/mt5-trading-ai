"""Stufe 6 — Modellpfad schliessbar machen. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Woertlich::

    Befoerderung standardmaessig aus. Artefakt erreicht den auswertenden Dienst und
    ueberlebt Neustarts. Freigabeteilung auf den gesaeuberten Vorwaertstest.
    Trainingsmindestmenge in ein Verhaeltnis zur Merkmalszahl setzen.
    Trainingsendpunkte authentifizieren. Ueberlappende Zielwerte gewichten.

    Abnahme: ein Trainingslauf erzeugt einen Herausforderer im Wartezustand, nicht
    einen Champion; ein falscher Schemahash fuehrt zum Verwerfen; das Artefakt ist
    nach Neustart noch da.

WAS DIE MESSUNG GEFUNDEN HAT
----------------------------
Der Modellpfad dieses Standes ist ``gates/learning_phase.py`` -- aus Trades entstehen
Parametersaetze. Gemessen (``AUFTRAG/stufen/06-modellpfad/belege/``):

* Befoerderung war bereits aus. **Erfuellt.**
* Eine Rangliste entstand aus **einem einzigen Trade**; acht Parameter liessen sich
  ohne jeden Bezug zur Beobachtungszahl vorschlagen.
* Fuenf vollstaendig ueberlappende Trades zaehlten als **fuenf** unabhaengige
  Beobachtungen. Sie sind eine.
* Eine Pruefsumme durfte ``"egal"`` lauten.
* Schemahash, Artefakt und Lesefunktion gab es nicht.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mt5_trading_ai.gates import herausforderer as hf_modul
from mt5_trading_ai.gates.herausforderer import (
    MINDESTBEOBACHTUNGEN_ABSOLUT,
    WARTEND,
    Herausforderer,
    HerausfordererAblage,
    HerausfordererFehler,
    Herkunft,
    baue_herausforderer,
    effektive_beobachtungen,
    mindestbeobachtungen,
    schema_hash,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 6, 12, tzinfo=UTC)
ECHTE_SUMME = "a" * 64


def _spannen(n: int, *, stunden: float = 5.0, versatz: float = 6.0, symbol: str = "EURUSD"):
    """``n`` Spannen; ``versatz=0`` macht sie deckungsgleich."""
    return [
        (
            symbol,
            NOW + timedelta(hours=versatz * i),
            NOW + timedelta(hours=versatz * i + stunden),
        )
        for i in range(n)
    ]


def _baue(**kw):
    basis = dict(
        strategy_id="smc-v1",
        base_version="1.0.0",
        parameters={"n": 5},
        rationale="Eichfall",
        herkunft=Herkunft(ECHTE_SUMME, "abc1234"),
        spannen=_spannen(60),
        freigabeteilung="purged-walk-forward k=5",
        jetzt=NOW,
    )
    basis.update(kw)
    return baue_herausforderer(**basis)  # type: ignore[arg-type]


# =====================================================================
# A1 — Befoerderung standardmaessig aus
# =====================================================================
def test_ein_herausforderer_entsteht_im_wartezustand() -> None:
    """Der Zustand ist keine Voreinstellung, die man beim Bau uebergehen kann."""
    assert _baue().zustand == WARTEND


def test_das_modul_kennt_keine_funktion_die_einen_zustand_aendert() -> None:
    """Am Syntaxbaum: keine Zuweisung an ``zustand`` ausserhalb der Klasse.

    „Befoerderung standardmaessig aus" waere schwach, wenn daneben eine Funktion
    ``befoerdere()`` staende, die man nur aufrufen muss. Der Fall haelt fest, dass es
    sie nicht gibt -- und wird rot, sobald jemand sie schreibt.
    """
    quelle = Path(inspect.getsourcefile(hf_modul) or "")
    baum = ast.parse(quelle.read_text(encoding="utf-8"))
    verstoesse = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef | ast.AsyncFunctionDef):
            for inner in ast.walk(knoten):
                ziele = []
                if isinstance(inner, ast.Assign):
                    ziele = inner.targets
                elif isinstance(inner, ast.AugAssign | ast.AnnAssign):
                    ziele = [inner.target]
                for ziel in ziele:
                    if isinstance(ziel, ast.Attribute) and ziel.attr == "zustand":
                        verstoesse.append(f"{knoten.name}:{inner.lineno}")
    assert verstoesse == [], (
        f"Zustandsaenderung in: {verstoesse}. Die Befoerderung ist kein Programmschritt."
    )


def test_ein_artefakt_das_sich_selbst_zum_champion_erklaert_wird_nicht_gelesen(
    tmp_path: Path,
) -> None:
    """Der rote Gegenfall: die Befoerderung ist auch kein Feld in einer Datei."""
    ablage = HerausfordererAblage(tmp_path)
    pfad = ablage.schreibe(_baue())
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["zustand"] = "champion"
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    befund = ablage.lade()
    assert befund.herausforderer == ()
    assert any("champion" in g for g in befund.verworfen)


# =====================================================================
# A4 — Trainingsmindestmenge im Verhaeltnis zur Merkmalszahl
# =====================================================================
def test_die_mindestmenge_waechst_mit_der_merkmalszahl() -> None:
    assert mindestbeobachtungen(1) == MINDESTBEOBACHTUNGEN_ABSOLUT
    assert mindestbeobachtungen(8) > mindestbeobachtungen(4) > mindestbeobachtungen(2)


def test_acht_parameter_aus_drei_trades_werden_abgelehnt() -> None:
    """Genau die Lage, die die Messung vor dieser Stufe gefunden hat."""
    with pytest.raises(HerausfordererFehler, match="effektive Beobachtungen"):
        _baue(parameters={f"p{i}": i for i in range(8)}, spannen=_spannen(3))


def test_genug_beobachtungen_lassen_denselben_satz_durch() -> None:
    """Der gruene Gegenfall. Ohne ihn bestuende der rote auch an einer Schranke, die
    ausnahmslos alles abweist."""
    parameter = {f"p{i}": i for i in range(8)}
    h = _baue(parameters=parameter, spannen=_spannen(mindestbeobachtungen(8) + 5))
    assert h.zustand == WARTEND
    assert h.effektive_beobachtungen >= mindestbeobachtungen(8)


def test_ein_parametersatz_ohne_parameter_ist_keiner() -> None:
    with pytest.raises(HerausfordererFehler):
        _baue(parameters={})


# =====================================================================
# A6 — Ueberlappende Zielwerte gewichten
# =====================================================================
def test_deckungsgleiche_trades_zaehlen_als_eine_beobachtung() -> None:
    """Fuenfmal dieselbe Marktbewegung ist eine Beobachtung, nicht fuenf."""
    assert effektive_beobachtungen(_spannen(5, versatz=0)) == pytest.approx(1.0)


def test_disjunkte_trades_zaehlen_einzeln() -> None:
    """Der gruene Gegenfall: die Gewichtung frisst nicht, was nicht ueberlappt."""
    assert effektive_beobachtungen(_spannen(5, stunden=5, versatz=6)) == pytest.approx(5.0)


def test_zwei_instrumente_laufen_getrennt() -> None:
    """Verschiedene Maerkte ueberlappen nicht, auch wenn sie zur selben Zeit laufen."""
    spannen = _spannen(5, versatz=0) + _spannen(5, versatz=0, symbol="GBPUSD")
    assert effektive_beobachtungen(spannen) == pytest.approx(2.0)


def test_die_ueberlappung_haelt_die_schranke_scharf() -> None:
    """Der Fall, der beide Regeln zusammen prueft -- und der Grund fuer beide.

    60 deckungsgleiche Trades sehen nach reichlich Belegen aus. Effektiv ist es eine
    Beobachtung, und der Vorschlag faellt. Ohne die Gewichtung waere er durchgegangen.
    """
    with pytest.raises(HerausfordererFehler, match="Ueberlappung"):
        _baue(spannen=_spannen(60, versatz=0))


def test_eine_spanne_die_vor_ihrem_beginn_endet_ist_ein_fehler() -> None:
    with pytest.raises(HerausfordererFehler, match="endet vor"):
        effektive_beobachtungen([("EURUSD", NOW, NOW - timedelta(hours=1))])


# =====================================================================
# A5 — Trainingsendpunkte authentifizieren
# =====================================================================
@pytest.mark.parametrize(
    "summe", ["", "egal", "a" * 63, "a" * 65, "z" * 64]
)
def test_eine_pruefsumme_die_jeder_text_sein_darf_authentifiziert_nichts(
    summe: str,
) -> None:
    """``"egal"`` ging vor dieser Stufe durch -- gemessen, nicht vermutet."""
    with pytest.raises(HerausfordererFehler, match="SHA-256"):
        _baue(herkunft=Herkunft(summe, "abc1234"))


def test_eine_echte_pruefsumme_geht_durch() -> None:
    assert _baue(herkunft=Herkunft(ECHTE_SUMME, "abc1234")).zustand == WARTEND


def test_ohne_codestand_kein_herausforderer() -> None:
    with pytest.raises(HerausfordererFehler, match="code_commit"):
        _baue(herkunft=Herkunft(ECHTE_SUMME, "   "))


# =====================================================================
# A3 — Freigabeteilung auf den gesaeuberten Vorwaertstest
# =====================================================================
def test_ohne_benannte_freigabeteilung_kein_herausforderer() -> None:
    """Ein Kandidat, der nicht sagt, worauf er wartet, wartet auf nichts."""
    with pytest.raises(HerausfordererFehler, match="Freigabeteilung"):
        _baue(freigabeteilung="  ")


def test_der_trainingslauf_benennt_den_gesaeuberten_vorwaertstest() -> None:
    """Und zwar den echten: purge, embargo und das Sechs-Bedingungen-Tor."""
    from tools.modelllauf import FREIGABETEILUNG

    for wort in ("purged-walk-forward", "purge", "embargo", "edge.py"):
        assert wort in FREIGABETEILUNG


# =====================================================================
# Abnahme B2 — falscher Schemahash fuehrt zum Verwerfen
# =====================================================================
def test_falscher_schemahash_fuehrt_zum_verwerfen(tmp_path: Path) -> None:
    """Ein Artefakt aus einer anderen Feldwelt wird verworfen, nicht gedeutet."""
    ablage = HerausfordererAblage(tmp_path)
    pfad = ablage.schreibe(_baue())
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["schema_hash"] = "0000000000000000"
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    befund = ablage.lade()
    assert befund.herausforderer == ()
    assert len(befund.verworfen) == 1
    assert "Schemahash" in befund.verworfen[0]


def test_der_richtige_schemahash_wird_gelesen(tmp_path: Path) -> None:
    """Der gruene Gegenfall. Sonst bestuende der rote auch an einer Ablage, die
    grundsaetzlich alles verwirft."""
    ablage = HerausfordererAblage(tmp_path)
    ablage.schreibe(_baue())
    befund = ablage.lade()
    assert len(befund.herausforderer) == 1
    assert befund.verworfen == ()


def test_der_schemahash_haengt_an_den_feldern_nicht_an_einer_konstante() -> None:
    """Er muss sich aendern, wenn sich der Feldsatz aendert -- sonst schuetzt er nichts.

    Geprueft wird gegen eine unabhaengig gerechnete Groesse: derselbe Hash ueber
    Feldnamen und -typen, hier von Hand gebildet. Eine Pruefung, die die Formel des
    Prueflings wiederholt, prueft nichts -- darum wird die Empfindlichkeit gemessen,
    indem ein Feldname veraendert in die Rechnung geht.
    """
    import hashlib
    from dataclasses import fields as feld_liste

    echt = ";".join(f"{f.name}:{f.type}" for f in feld_liste(Herausforderer))
    assert schema_hash() == hashlib.sha256(echt.encode()).hexdigest()[:16]

    verfaelscht = echt.replace("beobachtungen", "trades", 1)
    anderer = hashlib.sha256(verfaelscht.encode()).hexdigest()[:16]
    assert anderer != schema_hash(), "Ein geaenderter Feldname aendert den Hash nicht."


def test_eine_unlesbare_datei_wird_verworfen_und_genannt(tmp_path: Path) -> None:
    (tmp_path / "kaputt.json").write_text("{kein json", encoding="utf-8")
    befund = HerausfordererAblage(tmp_path).lade()
    assert befund.herausforderer == ()
    assert "unlesbar" in befund.verworfen[0]


def test_ein_defektes_artefakt_nimmt_die_anderen_nicht_mit(tmp_path: Path) -> None:
    """Je Datei einer -- damit ein Formatfehler nicht alle Kandidaten mitnimmt."""
    ablage = HerausfordererAblage(tmp_path)
    ablage.schreibe(_baue(strategy_id="gut"))
    (tmp_path / "kaputt.json").write_text("{kein json", encoding="utf-8")
    befund = ablage.lade()
    assert [h.strategy_id for h in befund.herausforderer] == ["gut"]
    assert len(befund.verworfen) == 1


# =====================================================================
# Abnahme B3 — das Artefakt ist nach Neustart noch da
# =====================================================================
def test_das_artefakt_ueberlebt_den_neustart(tmp_path: Path) -> None:
    """„Neustart" heisst hier: eine zweite, frisch gebaute Ablage auf demselben Ordner.

    Sie teilt mit der ersten nichts ausser dem Pfad -- genau wie ein neuer Prozess.
    """
    HerausfordererAblage(tmp_path).schreibe(_baue(strategy_id="ueberlebt"))

    zweite = HerausfordererAblage(tmp_path)
    gelesen = zweite.lade().herausforderer
    assert [h.strategy_id for h in gelesen] == ["ueberlebt"]
    assert gelesen[0].zustand == WARTEND
    assert gelesen[0].herkunft.data_checksum == ECHTE_SUMME
    assert gelesen[0].effektive_beobachtungen > 0


def test_eine_leere_ablage_meldet_leer_statt_zu_werfen(tmp_path: Path) -> None:
    """Der gruene Gegenfall: „noch kein Kandidat" ist kein Fehler."""
    befund = HerausfordererAblage(tmp_path / "gibtsnicht").lade()
    assert befund.herausforderer == ()
    assert befund.verworfen == ()


# =====================================================================
# Abnahme B1 — ein Trainingslauf erzeugt einen Herausforderer, keinen Champion
# =====================================================================
def test_der_trainingslauf_legt_einen_wartenden_kandidaten_an(tmp_path: Path) -> None:
    """Der ganze Weg: Werkzeug aufrufen, Artefakt lesen, Zustand pruefen."""
    journal = tmp_path / "journal.jsonl"
    zeilen = []
    for i in range(60):
        auf = NOW + timedelta(hours=6 * i)
        zeilen.append(
            json.dumps(
                {
                    "art": "geschlossen",
                    "symbol": "EURUSD",
                    "seit": auf.isoformat(),
                    "ts": (auf + timedelta(hours=5)).isoformat(),
                }
            )
        )
    journal.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    ablage = tmp_path / "ablage"

    lauf = subprocess.run(
        [
            sys.executable, "tools/modelllauf.py",
            "--journal", str(journal),
            "--ablage", str(ablage),
            "--data-checksum", ECHTE_SUMME,
            "--code-commit", "abc1234",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    assert "HERAUSFORDERER angelegt" in lauf.stdout
    # Nicht auf das Wort "champion" pruefen -- es steht im Banner des Werkzeugs
    # ("nie einen Champion"). Geprueft wird der ausgegebene ZUSTAND.
    assert f"zustand              : {WARTEND}" in lauf.stdout

    gelesen = HerausfordererAblage(ablage).lade().herausforderer
    assert len(gelesen) == 1
    assert gelesen[0].zustand == WARTEND
    assert gelesen[0].freigabeteilung


def test_der_trainingslauf_legt_bei_zu_wenig_beobachtungen_nichts_an(
    tmp_path: Path,
) -> None:
    """Der rote Gegenfall -- und der Ausgang auf den echten Daten dieses Standes.

    Die eingecheckte Aufzeichnung traegt 16 geschlossene Trades gegen 50 noetige. Es
    entsteht nichts, was spaeter aussaehe, als haette es einmal gegolten.
    """
    ablage = tmp_path / "ablage"
    lauf = subprocess.run(
        [
            sys.executable, "tools/modelllauf.py",
            "--journal", "aufzeichnungen/demo-2026-08-17.jsonl",
            "--ablage", str(ablage),
            "--data-checksum", ECHTE_SUMME,
            "--code-commit", "abc1234",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert lauf.returncode == 2, lauf.stdout
    assert "KEIN HERAUSFORDERER" in lauf.stdout
    assert HerausfordererAblage(ablage).lade().herausforderer == ()
