# Entscheidungen (Programm NEUAUFBAU)

Regel aus dem Rahmen: zwei Wege benennen, den Unterschied messen oder begründet schätzen,
wählen, festhalten — Entscheidung, Messung (oder Schätzung, gekennzeichnet), verworfene
Alternative. Anhängend, nie überschreiben; eine Entscheidung wird durch eine neue Nummer
ersetzt, nicht durch Bearbeiten. Nummerierung E-001 aufwärts, unabhängig vom Register des
Altstands (`archiv/`).

## E-001 — Das Programm läuft im bestehenden Repository `PhilippCode1/mt5-trading-ai`, Zweig `master` (2026-09-03)

**Entscheidung.** Auftrag 1 und alle folgenden arbeiten in `C:\Users\Acer\mt5_trading_ai`
(origin PhilippCode1/mt5-trading-ai, master, Bewertungsstand 306bbaa). Kein neues
Repository, keine importierte Historie.

**Messung.** Die Sitzung startete in `C:\Users\Acer\OneDrive\Documents\Cursor1\mt5-trading-ai`;
das ist der Altbestand `bitget-btc-ai` (Zweig `main`, Remote PhisoLive/bitget-btc-ai,
122 Commits, kein gemeinsamer Vorfahr mit 306bbaa — `git merge-base` leer). Jeder Befund
D1–D8 der Bewertung verweist auf Dateien, die nur unter `mt5_trading_ai/` existieren.
Masterprompt 01 Abschnitt 0 und die Programm-Übersicht §2 nennen dieses Repository als
Arbeitsverzeichnis. Die Historie (114 Commits) und die CI-Historie (8 Läufe, alle rot)
sind die Referenz für rote Eichfälle.

**Verworfen.** (a) Neues Repository mit importierter Historie: Umzug ohne messbaren
Nutzen, zusätzliche Fehlerquelle. (b) Der OneDrive-Ordner: falscher Code, Cloud-Sync,
Git-Eigentümerkonflikt („dubious ownership"), offener Haltepunkt H-003 (Zugangsdaten
im Klartext).

## E-002 — Git-Identität lokal auf `phisolive <philippcrljic3@gmail.com>` gesetzt (2026-09-03)

**Entscheidung.** `git config --local user.name phisolive`, `user.email philippcrljic3@gmail.com`.

**Messung.** Global stand „Dein GitHub Benutzername <Deine E-Mail-Adresse>" (alle 114
Commits des Altstands, Befund der Bewertung §6.3). Philipps anderes Repository
(OneDrive) führt lokal die genannte Identität — die einzige, die er selbst gesetzt hat.

**Verworfen.** Globale Konfiguration ändern (Eingriff außerhalb des Repos); eine frei
erfundene Identität. Philipp kann die Identität jederzeit ändern; die Commits ab 2f5d9db
tragen sie.

## E-003 — Python 3.11 bleibt in Auftrag 1 (2026-09-03)

**Entscheidung.** Keine Versionsänderung in Auftrag 1.

**Messung.** CI pinnt 3.11; lokal 3.11.7 mit `MetaTrader5` 5.0.6090 installiert; der
Demolauf vom 2026-08-17 lief so. Für 3.13 ist die Verfügbarkeit des `MetaTrader5`-Wheels
auf diesem Rechner nicht gemessen.

**Verworfen.** Wechsel auf ≥ 3.12 jetzt: ungemessener Nutzen, sicherer Aufwand (CI,
Wheel, Stubs). Wird in Auftrag 8 gemessen.

## E-004 — Die 89 Testdateien bleiben und werden erweitert; Eichfälle in neuen Dateien (2026-09-03)

**Entscheidung.** Keine Ersetzung der Suite. Je Befund ein roter und ein grüner Eichfall
in `tests/eichfall_*.py`. Neue `tests/conftest.py` mit zwei Wächtern: ein Skip ist ein
Fehlschlag; ein Zugriff auf den echten Zustandsordner ist ein Fehlschlag. Tests, die heute
„flüchtig per Vorgabe" zusichern, werden zu roten Eichfällen von D8 umgedreht.

**Messung.** 1.611 grüne Fälle auf dem Klon (Bewertung), 1.622 lokal; 29.416 Zeilen
Tests. Ein Ersatz müsste jede dieser Sperren neu beweisen, bevor er etwas gewinnt.

**Verworfen.** Neue Suite gegen engeren Vertrag (zulässig laut Masterprompt §3):
Umbau ohne Messung, die ihn trägt.

## E-005 — Behebungen als Fehlerklasse; Zustand als Datei, nicht SQLite (2026-09-03)

**Entscheidung.** D2: ein Schließauftrag trägt das Positionsticket im Typ; Reduce-only
ohne Ticket ist nicht darstellbar. D3: Geldbeträge tragen ihre Währung als Typ,
Umrechnungskurs aus dem Terminal-Tick des Konvertierungspaars, fehlend → Sperre.
D8: Risikozustand, Schwebeakte und ein neu persistiertes Positionsbuch sind nur mit
Zustandsordner konstruierbar; flüchtig nur als ausdrücklicher Testtyp, den das
Betriebswerkzeug abweist; Umgebungsvariablen entfallen zugunsten `--zustandsordner`.
Speicherform: JSON-Dateien, atomar per Umbenennen.

**Messung/Schätzung.** Die Bewertung stellte D2 und D3 mit Attrappen nach (V2, V3);
19 Stellen setzen `reduce_only=True`, 94 Teststellen bauen `RiskManager()` ohne Zustand
(gezählt). Der `kill`-Eichfall (A6) ist mit Dateien direkt prüfbar (Bytevergleich); der
Zustand bleibt für Menschen lesbar. Geschätzt: SQLite spart nichts, was A6 verlangt, und
fügt einen Treiber und ein Sperrverhalten hinzu.

**Verworfen.** Prüfung an der Fundstelle („Flicken"): behebt den Fall, nicht die
Klasse — ein zweiter Aufrufer ohne Ticket wäre wieder möglich. SQLite: siehe oben.
Buch weiterhin nicht persistieren (wie `wiederanlaufprobe.py` zusichert): dann ist nach
einem Neustart nicht unterscheidbar, ob eine Broker-Position die eigene ist (D7).

## E-006 — Mutationstor: temporäre Kopie, zwei Tore, keine Schwelle gesenkt (2026-09-03)

**Entscheidung.** Mutanten werden in einer temporären Kopie des Repos gefahren, nie im
Arbeitsbaum. Handverlesener Katalog bleibt bei Tötungsrate 1,0. Dazu erzeugte
Operator-Mutanten über alle 12 Geldpfad-Dateien, ≥ 3 je Datei, gesamt ≥ 50, Mindestrate
0,90. Der `slow`-Test fährt einen Selbsttest mit 2 Sonden; das volle Tor ist ein CI-Schritt.

**Messung.** 16 Sonden (`--liste`, gezählt); 5 der 12 Geldpfad-Dateien ohne Sonde;
Vergiftung des Bytecodes nachgewiesen (Bewertung 03b, 2 von 42 pyc-Dateien). Die
Schwelle 1,0 ist per Test gepinnt (`test_stufe8_testwirkung.py`); 0,90 für den Katalog
wäre eine Absenkung.

**Verworfen.** Fremdes Werkzeug (mutmut, cosmic-ray): neue Abhängigkeit, eigene
Schreibmechanik auf Platte, kein Gewinn gegenüber einer Kopie in `tempfile`.

## E-007 — Wächter als Hooks: PreToolUse, Git pre-commit/pre-push, CI-Hash (2026-09-03)

**Entscheidung.** (a) `.claude/settings.json` mit `PreToolUse`-Hook (`PROGRAMM/hooks/waechter.py`),
der Write, Edit und Bash-Befehle abweist, die `PROGRAMM/abnahmekatalog.md` oder
`config/live_freigabe.json` nennen. (b) `.githooks/` mit `core.hooksPath`: pre-commit
lehnt Änderungen an beiden Dateien ab und fährt die schnellen Tore; pre-push die volle
Suite. (c) CI prüft den Katalog-Hash. Verschärfungen additiv in
`PROGRAMM/abnahmekatalog-verschaerfungen.md`.

**Messung/Schätzung.** Kein aktiver Hook im Repo (nur `.sample`), keine
`.claude/settings.json` (gezählt). Laufzeit der vollen Suite lokal 110 s — zu lang für
jeden Commit (Schätzung: > 30 s wird umgangen); die schnellen Tore werden gemessen.

**Verworfen.** Nur ein Vorsatz („nicht anfassen") — genau das, was der Rahmen §0.5
ausschließt. Nur Git-Hooks: sie fangen den Schreibzugriff erst beim Commit, nicht die
Bearbeitung.

## E-008 — Ein Standdokument, ein erzeugtes Architekturdokument, Archiv mit Prüfsumme (2026-09-03)

**Entscheidung.** Lebend: `README.md`, `MODULES.md` (generiert, um Aufrufer je Modul
erweitert), `CLAUDE.md`, `PROGRAMM/`. Alles Übrige nach `archiv/altstand-306bbaa/` per
`git mv` mit `MANIFEST.sha256`. Doku-Tore als Mengenregel: Wurzel = genau die drei
Dateien; eigene Markdown-Dateien ≤ 32, phrasen- und zahlengeprüft; `archiv/`,
`PROGRAMM/eingang/`, `PROGRAMM/masterprompts/` per Prüfsumme auf Unverändertheit geprüft.

**Messung.** 57 Markdown-Dateien, 117.302 Wörter (gezählt); zwölf „Stand"-Dokumente
(Bewertung §6.2); Tests lesen fünf Dateien unter `ABSCHLUSS-3a/` und `RUNBOOK.md`
(gezählt) — die Pfade ziehen mit.

**Verworfen.** Löschen statt archivieren: verboten ohne Archivkopie (Masterprompt §7).
Stehen lassen: zwölf Stände, die sich widersprechen (Befund F5).

## E-009 — Kein Modell, keine Oberfläche: fünf Löschkandidaten, Entscheidung nach Bestandszählung (2026-09-03)

**Entscheidung.** `tools/oberflaeche.py` (+ `docs/overview.html`), `tools/modelllauf.py`,
`backtest/llm_compare.py`, `gates/herausforderer.py`, `gates/learning_phase.py` werden
in T4 nach dem festgeschriebenen Kriterium beurteilt; erwartet: Löschung mit Eintrag.
Backtest-Engine, Sechs-Bedingungen-Tor, Strategien und der Betriebsplatzhalter bleiben
unverändert bis Auftrag 3.

**Messung.** 106 Testfunktionen (7,5 % von 1.409) hängen an den fünf Kandidaten
(gezählt); `gates/herausforderer.py` trägt 3 der 16 Mutationssonden und steht in der
Geldpfad-Liste, obwohl es ein Modellartefakt ohne Modell ist (Bewertung §4).

**Verworfen.** Behalten, weil Tests existieren: Regel 5 (kein Code ohne Wirkung).

## E-010 — Zulassung und Schreibrecht sind zwei Dinge (2026-09-03)

**Entscheidung.** `--scharf "<Text>"` entfällt. `--demo-schreiben` setzt `allow_write`
(`require_demo` bleibt `True`). `--zulassung <datei>` verweist auf einen eingecheckten
Registereintrag; ohne ihn ist nichts zugelassen. `config/live_freigabe.json` trägt die
vier Schalter und die Kennung aus `execution/release.py`, alle aus, hook-geschützt.

**Messung.** `--scharf` setzt heute `allow_write` **und** `CriteriaVerdict(passed=True)`
(`tools/live_betrieb.py:827,924`, gelesen); 15 von 21 Demoläufen liefen so
(`zulassung_uebergangen`, Bewertung §3.5). Das `settings`-Objekt der Live-Freigabe wird
nirgends übergeben (gezählt: 0 Konstruktionsstellen).

**Verworfen.** `--scharf` als Boolean behalten: bleibt ein Freitext-Ersatz für ein Tor.

## E-011 — Formatierung einmal, zuerst, als eigener Commit (2026-09-03)

**Entscheidung.** `ruff format` über den Bestand (Commit 9f13f44), bevor irgendetwas
parallel bearbeitet wird; `ruff format --check` wird CI-Tor (A1 verlangt Formatierung).

**Messung.** 112 von 171 Dateien wurden umformatiert; ein Mutationsanker traf danach
nicht mehr und wurde nachgezogen (16/16); Quellzeilen 16.835 → 16.979.

**Verworfen.** Formatierung am Ende: jeder parallele Zweig hätte Konflikte in jeder Datei.

## E-012 — Das Zahlen-Tor nimmt `PROGRAMM/` aus; das Behauptungs-Tor nicht (2026-09-03)

**Entscheidung.** `tools/check_doc_numbers.py` prüft `PROGRAMM/` nicht;
`tools/check_docs_claims.py` prüft die eigenen Dateien darin uneingeschränkt und zählt
sie nicht gegen die Obergrenze (wie `AUFTRAG/`). `PROGRAMM/eingang/` und
`PROGRAMM/masterprompts/` sind fremde Eingänge: weder gezählt noch geprüft; ihre
Unverändertheit sichert ein Manifest.

**Messung.** Der Rahmen schreibt `Zuletzt: <Datum, Commit>` in `zustand.md` und
Messwerte je Modul im Bericht vor; das Zahlen-Tor verbietet beides in Live-Dokumenten
(Regeln 2 und 5, gelesen). Ohne die Ausnahme wären 14 Befunde in fremden Dateien und
jeder Bericht rot (Bewertung und Masterprompt 09 zitieren gesperrte
Reifegrad-Zusicherungen des Altstands als Befund — der Commit-Titel 651c752 und die
Abschlussformel der Abnahme-Pakete).

**Verworfen.** Obergrenze anheben oder Phrasen streichen: eine Absenkung (Regel 3).

## E-013 — Belegskripte unter `PROGRAMM/auftrag-*/belege/` werden nicht gelintet (2026-09-03)

**Entscheidung.** `ruff` (check und format) nimmt `PROGRAMM/auftrag-*/belege/` aus; `PROGRAMM/hooks/`
bleibt gelintet und mit `mypy --strict` typgeprüft.

**Messung.** Die Nachstellungsskripte sind Messprotokolle, drei davon aus den Nachproben der
Bewertung abgeleitet (Kopfzeile nennt die Quelle); die Vorlage trägt 170 Lint-Befunde
(`ruff check PROGRAMM/eingang`, 2026-09-03). Sie umzuschreiben änderte die Messung, nicht den Code.

**Verworfen.** Lint erzwingen: Aufwand ohne Wirkung auf das Produkt; Belege dürfen fremd aussehen,
solange ihre Herkunft und ihre Ausgabe daneben liegen.
