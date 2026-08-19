#!/usr/bin/env python3
"""Trainingslauf: aus beobachteten Trades einen Herausforderer machen -- oder keinen.

WAS DIESES WERKZEUG IST
-----------------------
Der Einstiegspunkt, den die Abnahme der Stufe 6 verlangt: *„ein Trainingslauf erzeugt
einen Herausforderer im Wartezustand, nicht einen Champion."*

Es liest ein Betriebsjournal (oder die eingecheckte Aufzeichnung), leitet daraus einen
Parametersatz-Vorschlag ab und legt ihn als **Artefakt** ab -- wenn er die Schranken
nimmt. Nimmt er sie nicht, entsteht kein Artefakt, und das Werkzeug sagt warum.

WAS ES AUSDRUECKLICH NICHT TUT
------------------------------
* Es **befoerdert nichts.** Es gibt in ``gates/herausforderer.py`` keine Funktion, die
  einen Zustand aendert, und hier keinen Schalter dafuer. Ein Herausforderer wird nicht
  dadurch Champion, dass jemand ihn befoerdert, sondern indem er den gesaeuberten
  Vorwaertstest besteht -- und der laeuft in ``tools/edge_test.py``, gegen die
  vorregistrierten Schwellen, mit Eintrag ins Versuchsregister.
* Es **optimiert nicht.** Der Vorschlag ist eine Ableitung aus dem, was gemessen wurde,
  kein Suchlauf ueber einen Parameterraum. Ein Suchlauf waere nach dem Ergebnistor ein
  neuer Versuch je Punkt und muesste vorregistriert werden.
* Es **schreibt nicht ins Versuchsregister.** Ein Herausforderer im Wartezustand hat
  nichts gemessen; erst sein Vorwaertstest ist ein Versuch. Wer hier zaehlte, zaehlte
  Absichten statt Messungen -- und verschaerfte die Deflation aller spaeteren Laeufe
  fuer nichts.

Aufruf::

    python tools/modelllauf.py --journal aufzeichnungen/demo-2026-08-17.jsonl \\
        --ablage betrieb/herausforderer --code-commit <sha>
    python tools/modelllauf.py --ablage betrieb/herausforderer --lesen
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.llm_compare import (  # noqa: E402
    LlmGateInputs,
    evaluate_llm_gate,
)
from mt5_trading_ai.gates.erkundung import erkundungsanteil  # noqa: E402
from mt5_trading_ai.gates.herausforderer import (  # noqa: E402
    HerausfordererAblage,
    HerausfordererFehler,
    Herkunft,
    baue_herausforderer,
    mindestbeobachtungen,
)
from mt5_trading_ai.gates.learning_phase import (  # noqa: E402
    LearningPhaseError,
    Proposal,
    TradeRow,
    find_weaknesses,
    rank_strategies,
    validate_proposal,
)

#: Der Nachweis, auf den ein Herausforderer wartet. Kein freier Text: er benennt das
#: Verfahren, unter dem allein er Champion werden kann.
FREIGABETEILUNG = (
    "purged-walk-forward k=5, purge+embargo aus backtest/splits.py, "
    "Sechs-Bedingungen-Tor aus backtest/edge.py"
)


def spannen_aus_journal(pfad: Path) -> list[tuple[str, datetime, datetime]]:
    """Haltespannen ``(Symbol, von, bis)`` aus den ``geschlossen``-Saetzen.

    Nur geschlossene Positionen: eine offene hat kein Ergebnis und keine Spanne. Genau
    dieselbe Regel wie ``learning_phase.rank_strategies`` -- „kein Training auf Trades,
    die nie stattfanden".
    """
    spannen: list[tuple[str, datetime, datetime]] = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            satz = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if satz.get("art") not in ("geschlossen", "vom_broker_geschlossen"):
            continue
        symbol, seit, ts = satz.get("symbol"), satz.get("seit"), satz.get("ts")
        if not (
            isinstance(symbol, str)
            and isinstance(seit, str)
            and isinstance(ts, str)
        ):
            continue
        try:
            von = datetime.fromisoformat(seit)
            bis = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if bis >= von:
            spannen.append((symbol, von, bis))
    return spannen


def _lesen(ablage: HerausfordererAblage) -> int:
    befund = ablage.lade()
    print(f"Ablage: {ablage.ordner}")
    print(f"  gelesen   : {len(befund.herausforderer)}")
    for h in befund.herausforderer:
        print(
            f"    {h.strategy_id} ({h.base_version}) zustand={h.zustand} "
            f"beobachtungen={h.beobachtungen} effektiv={h.effektive_beobachtungen:.1f}"
        )
        print(f"      wartet auf: {h.freigabeteilung}")
    print(f"  verworfen : {len(befund.verworfen)}")
    for grund in befund.verworfen:
        print(f"    {grund}")
    return 0


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Trainingslauf des Modellpfads")
    ap.add_argument("--journal", type=Path, default=None)
    ap.add_argument("--ablage", type=Path, required=True)
    ap.add_argument("--lesen", action="store_true", help="nur die Ablage anzeigen")
    ap.add_argument("--strategy-id", default="smc-v1")
    ap.add_argument("--base-version", default="1.0.0")
    ap.add_argument("--data-checksum", default="")
    ap.add_argument("--code-commit", default="")
    args = ap.parse_args()

    ablage = HerausfordererAblage(args.ablage)
    if args.lesen:
        return _lesen(ablage)

    if args.journal is None:
        print("FEHLGESCHLAGEN — --journal fehlt.", file=sys.stderr)
        return 1
    if not args.journal.is_file():
        print(f"FEHLGESCHLAGEN — {args.journal} fehlt.", file=sys.stderr)
        return 1

    spannen = spannen_aus_journal(args.journal)
    # Der Parametersatz ist eine Ableitung, kein Suchlauf: die mittlere gemessene
    # Haltedauer als Hoechsthaltedauer vorschlagen. Ein Parameter -- mehr traegt die
    # Beobachtungsmenge dieses Journals ohnehin nicht.
    if spannen:
        stunden = sum(
            (bis - von).total_seconds() for _s, von, bis in spannen
        ) / len(spannen) / 3600.0
    else:
        stunden = 0.0
    parameter = {"max_haltedauer_stunden": round(stunden, 2)}

    print("=" * 74)
    print("TRAININGSLAUF — er erzeugt einen Herausforderer, nie einen Champion")
    print("=" * 74)
    # Stufe 9: das LLM-Tor sitzt jetzt DA, wo ein Modell ueberhaupt in den Pfad
    # koennte -- am Trainingslauf. Bis dahin lag ``evaluate_llm_gate`` ohne Aufrufer
    # im Paket: die einzige Zulassungsstelle fuer ein Modell, die nie befragt wurde.
    #
    # Die Eingaben sind hier bewusst die des LLM-FREIEN Standes: kein Modell, keine
    # Modellversion, kein Stichtag. Das Tor lehnt deshalb ab, und genau das ist die
    # richtige Auskunft -- ``kein LLM zugelassen`` ist eine Aussage, ``das Tor wurde
    # nie gefragt`` ist keine.
    llm = evaluate_llm_gate(
        LlmGateInputs(
            baseline_passed=False,
            baseline_score=0.0,
            llm_passed=False,
            llm_score=0.0,
            model_version="",
            model_training_cutoff=date(1970, 1, 1),
            backtest_start=date(1970, 1, 1),
        )
    )
    print(f"LLM im Entscheidungspfad: {'ZUGELASSEN' if llm.allowed else 'nein'}"
          f" ({'; '.join(llm.reasons) if llm.reasons else 'kein Grund'})")
    if llm.allowed:
        # Kann mit diesen Eingaben nicht vorkommen; wenn doch, ist das Tor kaputt.
        print("FEHLGESCHLAGEN — das LLM-Tor laesst ohne jeden Beleg zu.",
              file=sys.stderr)
        return 1

    # Stufe 7, Abnahme: „ein Trainingslauf weist den Anteil erkundender Beobachtungen
    # aus." Ohne diese Zahl weiss niemand, ob ein Vorschlag aus dem Regelbetrieb kommt
    # oder ueberwiegend aus Faellen, die das System selbst abgelehnt haette.
    from tools.auswertung import tabelle_aus_journal

    zeilen = tabelle_aus_journal(args.journal)
    anteil = erkundungsanteil(zeilen)

    print(f"Journal           : {args.journal}")
    print(f"Geschlossene Trades: {len(spannen)}")
    print(f"Erkundende Beobachtungen: {anteil * 100:.2f} % "
          f"(von {sum(1 for z in zeilen if z.ergebnis_bp is not None)} mit Ergebnis)")
    # Vor dem Vorschlag die Rangliste dessen, was tatsaechlich gefahren wurde.
    # ``gates/learning_phase.py`` traegt die vier Grenzen der Lernphase (kein
    # automatisches Freischalten, kein selbstmodifizierender Code, kein Vorschlag ohne
    # Registereintrag, kein Training auf Trades, die nie stattfanden) -- und es hatte
    # bis Stufe 8 **keinen Aufrufer im Ausfuehrungspfad**. Ein Modul mit gruenen
    # Eigentests belegt nicht, dass es je laeuft; genau das misst diese Stufe.
    trades = [
        TradeRow(
            strategy_id=args.strategy_id,
            version=args.base_version,
            instrument=symbol,
            asset_class="fx_major",
            opened_at=von,
            closed_at=bis,
            # Ohne Ergebnisspalte im Journal traegt die Zeile keinen Ertrag. Die
            # Rangliste zaehlt sie dann als 0,0 R -- und weil ``rank_strategies``
            # ausschliesslich geschlossene Zeilen rechnet, steht die Zahl fuer die
            # Handelsfrequenz, nicht fuer einen Ertrag. Das steht so in der Ausgabe.
            net_pnl_r=0.0,
            execution_mode="paper",
        )
        for symbol, von, bis in spannen
    ]
    rangliste = rank_strategies(trades)
    print(f"Rangliste (Lernphase): {len(rangliste)} Eintrag/Eintraege, "
          f"{sum(r.trades for r in rangliste)} geschlossene Zeilen gezaehlt")
    # Wo die Schwaechen liegen, gehoert in denselben Lauf: ein Trainingslauf, der
    # ranglistet und die Schwaechen verschweigt, laesst den unbequemen Teil weg.
    schwaechen = find_weaknesses(trades)
    if schwaechen:
        print(f"Schwaechen (Lernphase): {len(schwaechen)}")
        for s in schwaechen[:3]:
            print(f"  {s.dimension}={s.key}: {s.trades} Trades, "
                  f"mittleres Ergebnis {s.mean_r:+.3f} R")
    else:
        print("Schwaechen (Lernphase): keine benennbare")
    # Grenze 2 der Lernphase: ein Vorschlag ist ein PARAMETERSATZ, niemals Quelltext.
    # ``validate_proposal`` lehnt alles ab, was nach Code aussieht -- und lag bis
    # Stufe 9 nur hinter dem toten ``propose_parameter_sets``.
    try:
        validate_proposal(
            Proposal(
                strategy_id=args.strategy_id,
                base_version=args.base_version,
                parameters=parameter,
                rationale="Trainingslauf",
            )
        )
    except LearningPhaseError as exc:
        print(f"FEHLGESCHLAGEN — Parametersatz abgelehnt: {exc}", file=sys.stderr)
        return 1
    print(f"Parametersatz     : {parameter}")
    noetig = mindestbeobachtungen(len(parameter))
    print(f"Noetig dafuer     : {noetig} effektive Beobachtungen")
    print()

    try:
        herausforderer = baue_herausforderer(
            strategy_id=args.strategy_id,
            base_version=args.base_version,
            parameters=parameter,
            rationale=f"mittlere gemessene Haltedauer aus {args.journal.name}",
            herkunft=Herkunft(args.data_checksum, args.code_commit),
            spannen=spannen,
            freigabeteilung=FREIGABETEILUNG,
            jetzt=datetime.now(UTC),
        )
    except HerausfordererFehler as exc:
        # Kein Artefakt. Das ist ein gueltiger Ausgang und kein Fehlschlag des Laufs:
        # die Schranke hat getan, wofuer sie da ist.
        print(f"KEIN HERAUSFORDERER — {exc}")
        print()
        print("Das ist der auftragsgemaesse Ausgang, wenn die Beobachtungsmenge den")
        print("Parametersatz nicht traegt. Es entsteht nichts, was spaeter aussaehe,")
        print("als haette es einmal gegolten.")
        return 2

    ziel = ablage.schreibe(herausforderer)
    print(f"HERAUSFORDERER angelegt: {ziel}")
    print(f"  zustand              : {herausforderer.zustand}")
    print(f"  beobachtungen        : {herausforderer.beobachtungen}")
    print(f"  effektiv (Ueberlappung abgezogen): "
          f"{herausforderer.effektive_beobachtungen:.1f}")
    print(f"  wartet auf           : {herausforderer.freigabeteilung}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
