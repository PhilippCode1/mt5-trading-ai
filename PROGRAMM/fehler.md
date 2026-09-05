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

## F-006 — Neue Quelldatei waehrend eines laufenden Pushs angelegt; der Pre-Push-Lauf wies den Push ab (2026-09-03)

**Was geschah.** Waehrend der Pre-Push-Hook die Suite fuhr, legte ich `mt5_trading_ai/risk/waehrung.py`
(noch ohne Aufrufer) im Arbeitsbaum an. Die Suite laeuft auf dem Arbeitsbaum, nicht auf dem Commit;
die Erreichbarkeitstore (`tests/test_stufe8_testwirkung.py`) meldeten das Modul als verwaist, der
Push wurde abgewiesen. Inhaltlich richtig (Regel 5), zeitlich mein Fehler.

**Was es kostete.** Ein Suitelauf (5 min), ein zweiter Push.

**Was sich aendert.** Waehrend eines Pushs keine Datei im Arbeitsbaum anlegen oder aendern -- auch
keine neue; Entwuerfe entstehen im Scratchpad oder unter PROGRAMM/, nie unter mt5_trading_ai/, tools/
oder tests/.

**Wiederholung am 2026-09-04 (dieselbe Klasse, anderer Anlass).** Waehrend eines Suitelaufs im Hintergrund
habe ich `tools/zweigdeckung.py` und `PROGRAMM/entscheidungen.md` geaendert und zweimal committet. Der Lauf
meldete `2 failed, 1731 passed, 1 error` und einen Verstoss gegen Waechter A10 (`.pytest_cache/v/cache/lastfailed`
im Arbeitsbaum) -- kein Befund am Code, sondern ein Messfehler an mir. Der saubere Lauf ohne Nebenarbeit:
`1733 passed, 5 deselected in 594,95 s`, 0 uebersprungen. Die Regel gilt also nicht nur fuer Pushs, sondern
fuer jede laufende Messung: **waehrend eine Suite, ein Tor oder ein Push laeuft, wird am Arbeitsbaum nichts
geaendert und nichts committet.** Ein Messwert aus einem veraenderten Baum ist kein Messwert.

## F-007 — Der Claude-Code-Wächter (PreToolUse) war in dieser Sitzung nicht aktiv; ich hatte ihn als aktiv angenommen (2026-09-04)

**Was geschah.** Der Live-Eichfall aus T2 (`echo x >> PROGRAMM/abnahmekatalog.md` über das
Bash-Werkzeug) ging durch: Datei angehängt, Exit 0 (Beleg `belege/02-hook-live-naechste-sitzung.txt`).
Der Katalog-Hash-Test (`tools/katalog_hash.py --pruefen`) sah die Änderung; sie wurde zurückgenommen.

**Ursache (gemessen).** Claude Code lädt Projekt-Hooks aus dem Verzeichnis, in dem die Sitzung
startet. Diese Sitzung startete im OneDrive-Altbestand und wechselte per `cd` in das Programm-Repo;
die dortige `.claude/settings.json` wurde nie geladen. Der Selbsttest des Skripts (11/11) belegt die
Logik des Wächters, nicht seine Verdrahtung — genau der Unterschied, den Regel 1 meint.

**Was es kostete.** Nichts am Bestand (Git-Hook und Hash-Tor hielten); aber `zustand.md` führte A7
seit T2 als „zu drei Vierteln belegt“ mit einem offenen Punkt, der jetzt rot ist statt offen.

**Was sich ändert.** A7 wird im Bericht als „Git-Hooks belegt; Claude-Hook nur bei Sitzungsstart im
Repo“ geführt. Sitzungen für das Programm starten in `C:/Users/<konto>/mt5_trading_ai` (im
Gedächtnis vermerkt); der Live-Eichfall wird zu Beginn der nächsten Sitzung wiederholt. Bis dahin ist
der Pre-Commit-Hook die haltende Sperre.

## F-008 — Drei Fehlschlaege im Pre-Push-Lauf waren kein Codefehler, sondern eine volle Platte (2026-09-04)

**Was geschah.** Der Push wurde abgewiesen: `tests/test_provenance.py` (2 Faelle) und der
Mutationstor-Selbsttest fielen mit `error: unable to write file .git/objects/...: Permission denied`,
`failed to insert into database`, `fatal: adding files failed`. Dieselbe Meldung hatte kurz zuvor ein
`git add` im Hauptrepo geliefert. Die Fehlermeldung nennt ein Recht, gemeint ist der Platz.

**Messung.** `Get-PSDrive C`: 2,9 GB frei von 475 GB (99,4 % belegt). Alle drei Faelle legen temporaere
Git-Repositories an und schreiben Objekte hinein; unterhalb weniger GB scheitert das sporadisch.
Nach dem Aufraeumen **eigener** Reste — elf beendete Git-Worktrees unter `.claude/worktrees` (ihre Arbeit
ist eingespielt und als Patch gesichert), Klone und mypy-Caches im Scratchpad, Temp-Ordner abgebrochener
Subagenten — waren 3,7 GB frei, und dieselben Dateien liefen: `59 passed in 117,87 s`.

**Was sich aendert.** (1) Vor einer langen Messung (Suite, Mutationstor, Zweigdeckung, Push) den freien
Platz pruefen; unter 5 GB zuerst aufraeumen. (2) Nach jeder Runde Subagenten die Worktrees entfernen,
sobald ihre Patches eingespielt sind — sie kosten je rund 25 MB. (3) Eine Fehlermeldung ueber Rechte an
`.git/objects` ist zuerst ein Platzverdacht, kein Rechteverdacht.

**Zweiter Anlauf, zweite Ursache.** Mit 3,8 GB frei fiel der Push erneut an derselben Stelle:
`tests/eichfall_mutationstor.py` -- `git add` in der Wegwerf-Kopie, exit 128, `failed to insert into
database`. Diesmal war es nicht der Platz: dieselbe Kopie ohne Last gelingt in 1,8 s (613 Dateien, 15 MB,
`git add ok`). `tools/zweigdeckung.py::_wegwerf_git` kannte den Fall bereits und versuchte es dreimal mit
je einer Sekunde -- unter der Last des Pre-Push-Laufs (Suite, Mutantenlaeufe, Virenscanner) zu wenig.
Jetzt sechs Versuche mit wachsender Wartezeit (0,5 bis 16 s, in Summe unter 32 s); der Fehler bleibt hart,
nur die Zahl der Versuche steigt. Danach: `tests/eichfall_mutationstor.py` 3 gruen in 232 s.

**Dritter Anlauf, dritte Ursache -- und die ist keine Umgebung.** Der Push fiel erneut, diesmal an
`tests/test_stufe8_testwirkung.py::test_die_messung_faellt_ohne_absturz_wenn_die_suite_rot_ist`:
`assert () == ('tests/test_rot_eichfall_zweigdeckung.py::test_rot',)`. Die Messung sah `exit=1`, konnte
aber keinen roten Fall benennen -- `tools/zweigdeckung.py::fehlschlaege` liest die Zeilen `FAILED ...`
aus der pytest-Ausgabe, und die druckt pytest nur nach seiner Vorgabe fuer `-r`. Der Fall laeuft einzeln
gruen (dreimal nachgestellt) und fiel nur im vollen Lauf: eine Abhaengigkeit von etwas, das nicht
zugesichert ist, ist ein Fehler im Werkzeug, kein Flatterfall. `SUITE_ARGUMENTE` erzwingt die Zeilen
jetzt mit `-rfE`; danach dreimal gruen (16,9 / 20,4 / 28,2 s).

**Was ich daraus mitnehme.** Drei Pushs, drei verschiedene Ursachen unter einer Fehlermeldung. Zweimal
war es die Umgebung (Platz, Virenscanner), einmal das Werkzeug. Die Reihenfolge war richtig: erst
nachstellen, dann die Ursache benennen, nie die Zusicherung lockern. Falsch war, den Pre-Push-Lauf als
Messgeraet zu benutzen -- 16 Minuten je Anlauf. Kuenftig: die Suite ohne slow lokal fahren, dann die
slow-Faelle einzeln, erst dann pushen.

**Nicht meine Sache, aber zu sagen:** die Platte ist zu 99,4 % belegt; die restlichen 470 GB sind fremde
Daten. Wer hier weiterarbeitet, braucht Platz — das steht in `PROGRAMM/haltepunkte.md` als Hinweis, nicht
als Handlung von mir.

## F-009 -- Die Pre-Commit-Tore massen den Arbeitsbaum, der Commit traegt den Index (2026-09-05)

**Was geschah.** Die Gegenlese T10 (Einwand E7, S1) hat den Hook mit seinem eigenen Mittel
ausgehebelt: eine rote Fassung stagen, die saubere im Arbeitsbaum liegen lassen (`git add x`,
danach die Datei zuruecksetzen) -- und alle neun Tore melden gruen. Der Commit enthielt danach
eine Datei, die `ruff check` mit neun Fehlern quittiert. Gemessen im Wegwerf-Klon, Commit f830319.

**Warum ich es uebersehen habe.** Der Docstring des Hooks sagte, die Doku-Tore laesen
`git ls-files` und damit den Index. Das gilt fuer die *Dateiliste*, nicht fuer den *Inhalt*:
`git ls-files` nennt Pfade, die Werkzeuge oeffnen danach die Platte. Ich habe einen Satz ueber
die Menge fuer einen Satz ueber den Inhalt gehalten -- genau die Verwechslung, gegen die
'messen statt annehmen' steht. Der Hook war seit T2 im Einsatz und hat in dieser Zeit jeden
Commit auf dem falschen Gegenstand geprueft.

**Was sich aendert.** `PROGRAMM/hooks/pre_commit.py` checkt den Index vor dem Lauf in ein
temporaeres Verzeichnis aus (`git checkout-index -a`), legt dort ein Wegwerf-Git an (die
Doku-Tore brauchen `git ls-files`) und faehrt die Tore mit `cwd` auf dieser Kopie. Scheitert
das Auschecken, wird der Commit abgewiesen -- ein Tor, das heimlich etwas anderes misst als
angekuendigt, ist schlimmer als keines. Gegenprobe: derselbe Angriff bringt jetzt drei Tore zu
Fall (Katalog-Hash, ruff check, ruff format), der Commit wird abgewiesen. Test:
`tests/test_waechter_verdrahtung.py::test_die_tore_laufen_auf_dem_index_nicht_auf_dem_arbeitsbaum`.

## F-010 -- Vier Waechter hatten Loecher, die genau ihre eigene Zusicherung betrafen (2026-09-05)

Die Gegenlese T10 fand sie; jeder ist nachgestellt und geschlossen:

- **A2 (E8, S1).** `@pytest.mark.xfail(run=False)` meldete `1 xfailed` und Exit 0 -- ein
  Dekorator genuegte, um einen Test stillzulegen. Der Waechter prueft auf `[NOTRUN]`, kam aber
  zu spaet: pytests eigener `makereport` ist mit `tryfirst=True` registriert und liegt aussen.
  Jetzt faellt der Fall beim **Sammeln** auf, wo kein fremder Wrapper dazwischenliegt;
  `pytest.xfail()` mitten im Test wird zusaetzlich zum Fehlschlag. Ein `xfail`, das wirklich
  laeuft, bleibt erlaubt (Gegenprobe mitgetestet).
- **A10 (E9, S2).** Drei blinde Flecken: ein Ordner mit selbstgebauter `.git`-Marke ab Tiefe 2,
  eine beliebige Datei unter `__pycache__/`, und jeder Name mit dem Praefix `.coverage`. Jetzt
  gelten als fremde Baeume nur die, die `git worktree list` nennt; unter `__pycache__` zaehlt
  alles ausser Bytecode; das Praefix ist `.coverage.` statt `.coverage`.
- **A7 (E10, S2).** Der PreToolUse-Waechter entschied nach Werkzeugnamen und kannte nur vier
  Schreibwerkzeuge und `Bash`. Ein `Set-Content` ueber das PowerShell-Werkzeug -- auf Windows
  der gewoehnliche Schreibweg -- lief mit Exit 0 durch. Jetzt entscheidet er ueber **Felder**:
  jede Zeichenkette der Eingabe wird geprueft, der Matcher steht auf `.*`.
- **A7 (E11, S2).** Kein Test fuhr die Waechter; `git config --unset core.hooksPath` schaltete
  alle neun Tore ab, ohne dass etwas rot wurde. Neu: `tests/test_waechter_verdrahtung.py`
  (13 Faelle) laeuft in Suite, Pre-Push und CI; der Hook meldet jede Aenderung an einer
  Waechterdatei als eigene Zeile (`GEMELDET`).
- **A5 (E12, S2).** Die Basislinie des Geheimnis-Scans war nach Blob geschluesselt, nicht nach
  Ort: derselbe Inhalt liess sich aus `PROGRAMM/eingang/` an einen lebenden Pfad kopieren, und
  der Scan meldete 0 neue Funde. Der Schluessel traegt jetzt den Ort, und der Ort eines Objekts
  ist die **strengste** Gruppe aller seiner heutigen Pfade. Gegenprobe: derselbe Blob unter
  `config/zugang_neu.txt` ergibt 37 neue Funde, Exit 1.

## F-011 -- Die A11-Messung mass zweimal den Messaufbau statt der Suite (2026-09-05)

- **Erster Anlauf:** 100 Laeufe aus einem Schnappschuss der verfolgten Dateien -- ohne `.git`.
  Neun Tests fragen `git ls-files`/`status`/`worktree list` und fielen in JEDEM Lauf (36 von 36
  mit denselben neun roten Faellen). Das war kein Flattern. Behoben: der Schnappschuss bekommt
  ein Wegwerf-Git.
- **Zweiter Anlauf:** sechs Laeufe gleichzeitig, waehrend nebenher eine Deckungsmessung und
  eine Gegenprobe liefen. Jeder Lauf brauchte 21 statt 4 Minuten und meldete ~280 rote Faelle --
  Unterprozess-Tests mit Zeitschranke (Eichfaelle, Werkzeuge) liefen in ihre Timeouts. Gemessen
  wurde die Last der Maschine, nicht die Suite. Abgebrochen, Laufordner entfernt (die Platte
  stand bei 99 %).
- **Dritter Fall, gleiche Klasse (Aequivalenz-Nachweis E21):** Die Kopie fuer den Nachweis
  entstand, waehrend `tests/test_a18_laufzeitdaten.py` halbfertig im Baum lag (zwei Faelle
  dort rot: `TRIALS.jsonl` noch in der Wurzel, Modul ohne `sys.modules`-Eintrag). Beide
  Sonden meldeten `2 failed` -- ich hatte das zuerst als „getoetet, Eintrag falsch“ gelesen.
  Die Diagnose auf einer sauberen Kopie: 176 Risikofaelle gruen mit der Sonde. Ein
  Ueberlebensnachweis ohne Basislauf derselben Kopie ist keiner; der Nachweis wurde mit
  Basislauf wiederholt (`06-mutationsgrenzen.txt`).
- **Regel daraus:** Eine Flattermessung faehrt allein und mit so viel Gleichzeitigkeit, dass
  die Laufzeit je Lauf nahe der Einzellaufzeit bleibt; die Laufzeit steht je Lauf im Beleg,
  damit ein Pruefer die Last sieht. Rote Faelle einer Wiederholungsmessung sind erst dann
  „Flattern“, wenn derselbe Fall in derselben Umgebung mal rot, mal gruen ist.

## F-012 -- Zwei Fehlgriffe beim Umbau des Zusicherungstors (E13), beide von Toren gefangen (2026-09-05)

- **Backslash-Unfall:** Ein Heredoc-Patch schrieb `"\n".join(...)` mit echtem Zeilenumbruch in
  `tools/check_docs_claims.py` -- die Zeichenkette `\n` war auf dem Weg durch die Shell zum
  Zeilenumbruch geworden. ruff meldete zwoelf Syntaxfehler, das Tor selbst lief nicht mehr.
  Behoben ueber `chr(92)`/`chr(10)`; Patches mit Escapes gehen seither als Datei, nicht als
  Heredoc.
- **Absatz statt Zeile:** Der erste Umbau pruefte ganze Absaetze. Damit entlastete EIN gueltiger
  Beleg irgendwo im Absatz jede Zusicherung darin -- der rote B3-Eichfall (Beleg ins Leere,
  `tests/test_doku_menge.py`) fiel gruen. Zurueck auf Zeilen, plus ein Fenster aus Zeile und
  Folgezeile (mit Bindestrich-Verschmelzung), gemeldet an der ersten Zeile. Nebenbefund: das
  Muster `vollst[aä]ndig` fing die ASCII-Schreibung `vollstaendig` nie -- verschaerft.
