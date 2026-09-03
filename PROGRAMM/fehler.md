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

## F-004 — Commit 102f68d trotz eines roten Tests (2026-09-03)

**Was geschah.** Vor dem Commit lief ein Teil der Suite mit „1 failed, 181 passed"; der Commit
hing nur an den neun Toren des Pre-Commit-Hooks, nicht am Testergebnis. Der rote Test
(`tests/test_kostentor_ausgabe.py`, Zeile 414 der eingefrorenen Ausgabe) blieb im Commit.

**Was es kostete.** Ein weiterer Commit im Verlauf mit rotem Test; der Pre-Push-Hook haette den
Push abgewiesen, der Verlauf ist aber nicht sauber.

**Was sich aendert.** Der Commit-Befehl im Arbeitsskript haengt ab jetzt am Rueckgabewert des
Testlaufs (`[ $rc -eq 0 ] || exit 1` VOR `git commit`), so wie die Tore es tun. F-002 hatte dieselbe
Klasse fuer die Tore geschlossen, nicht fuer die Tests.

## F-005 — Ein Mutant des Mutationstors blieb im Arbeitsbaum, und mein `ruff --fix` hat ihn zementiert (2026-09-03)

**Was geschah.** Der Pre-Push-Hook fuhr die volle Suite samt Mutationstor. Beim Zurueckschreiben von
`mt5_trading_ai/execution/risk_manager.py` scheiterte `write_bytes` an einem Zugriffsfehler; der
Mutant der Sonde `kostenpraemisse` (`assumed_cost_bps`) blieb in der Datei, die Suite meldete 2 rote
Faelle, der Push wurde abgewiesen -- das Tor hat gehalten. Ich habe die Meldung nicht gelesen,
sondern weitergearbeitet: `ruff check --fix` entfernte den nun unbenutzten Import, die naechste
Suite zeigte 126 rote Faelle.

**Was es kostete.** Ein Suitelauf (5 min), eine Diagnose; kein Commit war betroffen.

**Was sich aendert.** (1) `git diff HEAD --stat` auf die Sondendateien nach jedem Mutationslauf, vor
jedem `ruff --fix`. (2) Das Mutationstor stellt jetzt mit zehn Wiederholungen zurueck und nennt den
Mutanten laut, wenn es scheitert. (3) Endgueltig: T6 faehrt Mutanten in einer temporaeren Kopie
(E-006) -- ein Werkzeug, das den Arbeitsbaum anfasst, ist das eigentliche Loch.
