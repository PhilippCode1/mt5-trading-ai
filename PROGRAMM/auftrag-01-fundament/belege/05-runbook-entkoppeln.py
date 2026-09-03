"""T5, Schritt 3 (E-014): Alarmregeln tragen ihre Handlung selbst; kein Verweis auf RUNBOOK.md.

Eigenes Skript (2026-09-03). Patcht mt5_trading_ai/betrieb/dienstguete.py (Feld
``handlungsanweisung`` ist jetzt der imperative Text, nicht ein Abschnittstitel; die
Alarmzeile druckt ihn), tools/dienstguete.py (Meldung) und die drei Tests, die
RUNBOOK-Abschnitte verlangten. Jede Ersetzung ist mit Anker abgesichert; scheitert ein
Anker, wird nichts geschrieben.

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-runbook-entkoppeln.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)

HANDLUNGEN = {
    "Buchtreue unter Ziel": (
        "Zuerst pruefen, ob der Halt ueberhaupt gesperrt hat: ein Reconcile-Halt, der im "
        "selben Takt halt_erklaert mit weiter_gesperrt=false traegt, hat nichts blockiert "
        "(der Broker hat zwischen zwei Takten geschlossen). Nur Takte ohne solche "
        "Aufloesung zaehlen. Dann mit tools/dienstguete.py nach Codestand "
        "aufschluesseln und die Ursache im lebenden Code suchen, nicht in alten Laeufen."
    ),
    "Ausstieg misslingt": (
        "Im Journal die Saetze schliessen_fehlgeschlagen lesen; das Feld fehler traegt "
        "den Wortlaut des Handelsplatzes. Offene Positionen im Terminal gegen das Buch "
        "halten. Bei 'Trade disabled' oder 'AutoTrading disabled by client' den "
        "Schreibpfad im Terminal freigeben und bis dahin von Hand schliessen, nicht "
        "warten. Bei 'Unsupported filling mode' die Fuellart je Symbol pruefen."
    ),
    "Position offen geblieben": (
        "Sofort im Terminal nachsehen, welche Positionen offen sind (das Journal sagt, "
        "was der Lauf wusste; der Broker sagt, was ist), und entscheiden: von Hand "
        "schliessen oder bewusst stehen lassen. Erst danach die Ursache: der ende-Satz "
        "fuehrt die Symbole unter offen_geblieben, die schliessen_fehlgeschlagen-Saetze "
        "davor den Grund."
    ),
    "Läufe brechen ab": (
        "Kein Sicherheitsalarm: die Kennzahl sagt nicht, ob Geld am Markt blieb "
        "(Nachtrag Laufabschluss des Altstands). Pruefen, ob der Rechner in den Standby "
        "ging (Windows-Ereignisprotokoll, Kernel-Power 42) oder der Prozess hart beendet "
        "wurde. Fuer offene Positionen gilt der Alarm 'Position offen geblieben'."
    ),
}


def patch(rel: str, pairs: list[tuple[str, str]]) -> None:
    p = REPO / rel
    s = p.read_text(encoding="utf-8")
    for alt, neu in pairs:
        assert s.count(alt) == 1, f"{rel}: Anker nicht eindeutig: {alt[:70]!r}"
        s = s.replace(alt, neu)
    p.write_text(s, encoding="utf-8", newline="")
    print(f"  gepatcht: {rel} ({len(pairs)} Stellen)")


def main() -> int:
    d = REPO / "mt5_trading_ai/betrieb/dienstguete.py"
    s = d.read_text(encoding="utf-8")
    paare: list[tuple[str, str]] = []
    for titel, text in HANDLUNGEN.items():
        alt = f'        "{titel}",{NL}'
        assert s.count(alt) == 1, f"Regeltitel {titel!r}: {s.count(alt)} Treffer"
        neu = "        (" + NL
        worte = text.split(" ")
        zeile = ""
        teile: list[str] = []
        for w in worte:
            if len(zeile) + len(w) + 1 > 76:
                teile.append(zeile)
                zeile = w
            else:
                zeile = (zeile + " " + w).strip()
        teile.append(zeile)
        for i, t in enumerate(teile):
            neu += f'            "{t}{" " if i < len(teile) - 1 else ""}"' + NL
        neu += "        )," + NL
        paare.append((alt, neu))
    paare += [
        (
            "    #: Ueberschrift des zugehoerigen Abschnitts in ``archiv/RUNBOOK.md``. Exakt, nicht"
            + NL
            + "    #: sinngemaess." + NL,
            "    #: Die Handlung selbst -- imperativ, zwei bis vier Saetze (E-014). Frueher der"
            + NL
            + "    #: Titel eines RUNBOOK-Abschnitts; das Runbook liegt im Archiv." + NL,
        ),
        (
            '            f"-> archiv/RUNBOOK.md: {self.regel.handlungsanweisung}"',
            '            f"-> Handlung: {self.regel.handlungsanweisung}"',
        ),
        (
            "#: Die Alarmregeln. Jede nennt ihre Metrik und den EXAKTEN Abschnittstitel in"
            + NL
            + "#: ``archiv/RUNBOOK.md``; beides wird geprueft." + NL,
            "#: Die Alarmregeln. Jede nennt ihre Metrik und ihre Handlung (E-014); beides wird"
            + NL
            + "#: geprueft (tests/test_stufe10_betrieb.py)." + NL,
        ),
    ]
    # Kommentarblock vor der vierten Regel (Umlaut-Anker) entfernen
    m = re.search(
        r"        # Der EXAKTE Abschnittstitel aus ``archiv/RUNBOOK.md``.*?beim ersten Lauf gefunden\.\n",
        s,
        flags=re.S,
    )
    assert m, "Kommentarblock vor 'Laeufe brechen ab' nicht gefunden"
    paare.append((m.group(0), ""))
    m = re.search(r"2\. \*\*Eine Handlungsanweisung\*\*, die es wirklich gibt -- ein Abschnitt in\n``archiv/RUNBOOK\.md``\.", s)
    assert m, "Docstring-Punkt 2 nicht gefunden"
    paare.append((m.group(0), "2. **Eine Handlungsanweisung**, die es wirklich gibt -- die Regel traegt sie" + NL + "selbst (E-014)."))
    patch("mt5_trading_ai/betrieb/dienstguete.py", paare)

    patch(
        "tools/dienstguete.py",
        [
            (
                '"FEHLGESCHLAGEN — Alarm steht. Handlungsanweisung in archiv/RUNBOOK.md.",',
                '"FEHLGESCHLAGEN — Alarm steht. Die Handlung steht in der Alarmzeile.",',
            )
        ],
    )

    # tests/test_stufe10_betrieb.py
    t = REPO / "tests/test_stufe10_betrieb.py"
    s = t.read_text(encoding="utf-8")
    m = re.search(
        r"def _runbook_abschnitte\(\) -> set\[str\]:.*?(?=\n\n\ndef test_jede_alarmregel_hat_eine_existierende_metrik)",
        s,
        flags=re.S,
    )
    assert m
    s = s.replace(m.group(0), "")
    m = re.search(
        r"def test_jede_alarmregel_hat_eine_existierende_handlungsanweisung\(\) -> None:.*?(?=\n\n\ndef test_jedes_dienstgueteziel_hat_eine_existierende_metrik)",
        s,
        flags=re.S,
    )
    assert m
    s = s.replace(
        m.group(0),
        'def test_jede_alarmregel_traegt_ihre_handlung_selbst() -> None:' + NL
        + '    """E-014: die Handlung steht in der Regel -- zwei bis vier Saetze, imperativ,' + NL
        + '    kein Verweis auf ein Dokument, das im Archiv liegt."""' + NL
        + '    for r in ALARMREGELN:' + NL
        + '        saetze = [x for x in re.split(r"(?<=[.!?])\\s+", r.handlungsanweisung) if x]' + NL
        + '        assert 2 <= len(saetze) <= 6, (r.name, len(saetze))' + NL
        + '        assert "RUNBOOK" not in r.handlungsanweisung, r.name' + NL
        + '        assert len(r.handlungsanweisung.split()) >= 20, r.name' + NL
        + NL + NL
        + 'def test_die_andere_richtung_keine_zwei_regeln_mit_derselben_handlung() -> None:' + NL
        + '    """Eine Handlung, die fuer zwei Alarme gilt, unterscheidet sie nicht."""' + NL
        + '    handlungen = [r.handlungsanweisung for r in ALARMREGELN]' + NL
        + '    assert len(set(handlungen)) == len(handlungen)',
    )
    alt = '    assert "archiv/RUNBOOK.md: Ausstieg misslingt" in zeile'
    assert s.count(alt) == 1
    s = s.replace(alt, '    assert "Handlung:" in zeile\n    assert "schliessen_fehlgeschlagen" in zeile')
    alt = 'RUNBOOK = ROOT / "archiv/RUNBOOK.md"\n'
    assert s.count(alt) == 1
    s = s.replace(alt, "")
    alt = 'def test_das_runbook_nennt_die_wiederanlaufprobe_und_sie_existiert() -> None:\n    assert WIEDERANLAUFPROBE.is_file()\n    assert "tools/wiederanlaufprobe.py" in RUNBOOK.read_text(encoding="utf-8")'
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        'def test_die_wiederanlaufprobe_existiert_und_nennt_ihren_zweck() -> None:\n    assert WIEDERANLAUFPROBE.is_file()\n    assert "Wiederanlauf" in WIEDERANLAUFPROBE.read_text(encoding="utf-8")',
    )
    s = s.replace('"""Gruener Eichfall: das Werkzeug, das ``archiv/RUNBOOK.md`` nennt, existiert und faellt', '"""Gruener Eichfall: die Wiederanlaufprobe existiert und faellt')
    t.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: tests/test_stufe10_betrieb.py")

    # tests/test_ausstiegsdeckung.py
    patch(
        "tests/test_ausstiegsdeckung.py",
        [
            (
                '    runbook = (ROOT / "archiv/RUNBOOK.md").read_text(encoding="utf-8")\n    assert f"\\n## {regel.handlungsanweisung}\\n" in runbook\n',
                '    assert "Terminal" in regel.handlungsanweisung  # die Handlung selbst (E-014)\n',
            )
        ],
    )

    # tests/test_laufabschluss.py
    t = REPO / "tests/test_laufabschluss.py"
    s = t.read_text(encoding="utf-8")
    m = re.search(
        r"def test_das_runbook_behauptet_die_widerlegte_ungenauigkeit_nicht_mehr\(\) -> None:.*?(?=\n\n\ndef |\Z)",
        s,
        flags=re.S,
    )
    assert m
    s = s.replace(
        m.group(0),
        'def test_die_handlung_behauptet_die_widerlegte_ungenauigkeit_nicht_mehr() -> None:' + NL
        + '    """Eine Handlungsanweisung, die auf eine unmoegliche Lage zeigt, ist schlimmer als' + NL
        + '    keine -- sie verbraucht die Aufmerksamkeit, die der echte Fall braucht (E-014:' + NL
        + '    die Handlung steht in der Regel selbst)."""' + NL
        + '    regel = next(r for r in ALARMREGELN if r.name == "laeufe_brechen_ab")' + NL
        + '    text = regel.handlungsanweisung' + NL
        + '    assert "bekannte Ungenauigkeit der Metrik" not in text' + NL
        + '    assert "Kein Sicherheitsalarm" in text',
    )
    if "from mt5_trading_ai.betrieb.dienstguete import" in s and "ALARMREGELN" not in s.split("def test_")[0]:
        s = s.replace("from mt5_trading_ai.betrieb.dienstguete import (", "from mt5_trading_ai.betrieb.dienstguete import (\n    ALARMREGELN,", 1)
    t.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: tests/test_laufabschluss.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
