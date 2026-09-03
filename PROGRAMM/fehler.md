# Eigene Fehler (Programm NEUAUFBAU)

Regel 10 des Rahmens: eigene Fehler zuerst und klar. Anhaengend; je Eintrag Datum,
was geschah, was es kostete, was sich aendert. Nummerierung F-001 aufwaerts, unabhaengig
vom Register des Altstands (`archiv/`).

## F-001 — Doku-Tore vor dem `git add` gefahren, CI durch den eigenen Setup-Commit rot (2026-09-03)

**Was geschah.** Beim Einrichten (Commit 2f5d9db) habe ich `check_docs_claims.py` und
`check_doc_numbers.py` lokal laufen lassen, **bevor** `PROGRAMM/` im Index war. Beide
Werkzeuge zaehlen `git ls-files`; die Zaehlung war deshalb unvollstaendig und meldete
„ok". Auf GitHub fiel danach `tests/test_auftrag_doku_tore.py::test_das_echte_repo_besteht_die_zaehlung`
(43 verfolgte Markdown-Dateien gegen Obergrenze 32), und die Tore selbst haetten 14
Befunde in fremden Dateien gemeldet (5 gesperrte Phrasen in Bewertung und Masterprompt 09,
8 Zahlen ohne Bezug). Beleg: GitHub-Lauf 33784013095, `tests` 2 failed / 1610 passed.

**Was es kostete.** Zwei zusaetzliche CI-Laeufe rot; ein Teilschritt (T0) im Plan.

**Was sich aendert.** Tore werden nach `git add` gefahren, nie davor. Behoben in aa28bfa
(fremde Eingaenge sind kein Pruefgegenstand; Obergrenze unveraendert).

## F-002 — Commit mit roten Toren, weil die Shell-Verkettung Rueckgabewerte verschluckte (2026-09-03)

**Was geschah.** Commit aa28bfa wurde ausgefuehrt, obwohl `check_doc_numbers.py` rot war
(Kennzahlen nach der Formatierung veraltet) und `pytest` drei Fehlschlaege meldete. Ursache:
`a && b` in einem Skript mit `set -e` bricht bei rotem `b` nicht ab, und `pytest | tail`
liefert den Rueckgabewert von `tail`. Ich habe die Ausgabe gelesen, aber die Ausfuehrung
nicht davon abhaengig gemacht.

**Was es kostete.** Ein Commit im Verlauf, dessen Tore rot waren; Nachzug in 0b959da.

**Was sich aendert.** Jedes Tor laeuft einzeln, sein Rueckgabewert wird gesammelt, und
der Commit haengt an der Summe (`FEHLER == 0`). Genau diese Regel wird in Teilschritt 2
zum Pre-Commit-Hook -- damit sie nicht von meiner Disziplin abhaengt.

## F-003 — Derselbe Fehler wie F-001 ein zweites Mal: Behauptungs-Tor vor dem `git add` gefahren (2026-09-03)

**Was geschah.** Beim T1-Commit (4d02db3) lief `check_docs_claims.py` gruen, weil
`PROGRAMM/entscheidungen.md` noch nicht im Index war. Der Eintrag E-012 zitierte zwei
gesperrte Phrasen woertlich; nach dem `git add` war das Tor rot. Die CI hat es nicht
gezeigt, weil der Schritt hinter den (noch roten) Tests uebersprungen wird.

**Was es kostete.** Ein Commit mit rotem Tor im Verlauf; Korrektur in T2.

**Was sich aendert.** Nicht mehr „Disziplin": der Pre-Commit-Hook (T2) faehrt die Tore
ueber den **Index**, also nach dem Stagen -- genau die Stelle, an der ich zweimal
vorbeigelaufen bin. Bis dahin: Tore nur nach `git add -A` fahren.
