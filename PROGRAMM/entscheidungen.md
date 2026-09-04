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
erweitert), `CLAUDE.md`, `PROGRAMM/`. Alles Übrige nach `archiv/` per
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

## E-014 — Alarmregeln tragen ihre Handlungsanweisung selbst; `RUNBOOK.md` wird archiviert (2026-09-03)

**Entscheidung.** `betrieb/dienstguete.py`: jede `Alarmregel` bekommt `handlung` (zwei bis vier
Sätze, imperativ, aus den vier RUNBOOK-Abschnitten destilliert) und verweist nicht mehr auf einen
Abschnittstitel in `RUNBOOK.md`; die Alarmzeile druckt die Handlung. `RUNBOOK.md` geht ins Archiv.
Die Tests, die RUNBOOK-Abschnitte je Regel verlangen (`test_stufe10_betrieb.py`,
`test_ausstiegsdeckung.py`, `test_laufabschluss.py`), prüfen stattdessen die Handlung im Code.

**Messung.** `dienstguete.py:104,124,450-476` koppelt lebenden Code an den exakten Abschnittstitel
einer Datei, die nach A8 archiviert wird; ein archiviertes Dokument darf keine Abhängigkeit lebenden
Codes sein (sonst wäre das Archiv nicht eingefroren). Vier Regeln, vier Abschnitte (195–332 Wörter);
das Runbook für den Dauerbetrieb entsteht in Auftrag 8 (F4) neu.

**Verworfen.** RUNBOOK.md als lebendes Dokument behalten: verletzt A8 („ein Standdokument") und
enthält Handgriffe, die auf nicht existierende Werkzeuge zeigen (Bewertung §2). Tests auf den
Archivpfad umbiegen: bindet Code an Archiv.

## E-015 — Pfadverweise auf archivierte Dokumente werden nachgezogen; Kopien-Tor gilt nur lebenden Dokumenten (2026-09-03)

**Entscheidung.** Beim Verschieben (`belege/05-archivieren.py`) werden Verweise in Code, Tests,
Konfiguration und CI auf `archiv/…` umgeschrieben (gezählt, Ausgabe im Beleg);
Tests, die eingefrorene Belegdateien lesen (`ABSCHLUSS-3a/07-AUSGABEN/*`, `01-AUFLOESUNG.md`), lesen
sie im Archiv weiter — sie bewachen, dass das Werkzeug zu seinem Beleg passt. `tools/kopien_abgleichen.py`
überspringt `archiv/`: dort sichert das Manifest; die Kopie `ABSCHLUSS/04-ALPHA.md` bleibt als
historisches Dokument, ohne dass ihr Kopf gegen ein bewegtes Original geprüft wird.

**Messung.** 45 Dateien nennen Archivkandidaten (Zählung 2026-09-03); die meisten Nennungen sind
Fundstellenangaben in Docstrings. Ein Verweis, der ins Leere zeigt, ist Doku-Drift (Befund F5).

**Verworfen.** Tests löschen, die Archivdateien lesen: verliert die Bindung Werkzeug ↔ Beleg. Verweise
stehen lassen: Drift.

## E-016 — Archivwurzel ist `archiv/`, nicht `archiv/altstand-306bbaa/` (2026-09-03)

**Entscheidung.** Der Altstand liegt direkt unter `archiv/` (Herkunft in `archiv/HERKUNFT.txt`,
Manifest `archiv/MANIFEST.sha256`). Die Nennung `archiv/altstand-306bbaa/` in E-008, E-014, E-015,
im Plan und in `zustand.md` ist damit durch `archiv/` zu lesen; die älteren Einträge wurden an dieser
einen Stelle berichtigt, nicht umgeschrieben.

**Messung.** Nach dem Nachziehen der 147 Verweise meldete `ruff` 45 überlange Zeilen (E501), fast alle
in Docstrings, die eine Fundstelle nennen; der um 24 Zeichen längere Pfad war die Ursache. Mit `archiv/`
blieben 22, davon 15 als Prosa umgebrochen und 2 gekürzt.

**Verworfen.** Die Zeilen mit `# noqa` freistellen: das wäre eine Ausnahmeliste im Kleinen.

**Nachtrag zu E-015 (2026-09-03).** Zwei Stellen werden nicht nachgezogen: der Wortlaut der
Kostentor-Ausgabe (`tools/kostentor.py`, ein Satz) und die Herkunftsangaben in `config/broker_costs.json`
und `config/instrument_catalog.json`, weil `tests/test_kostentor_ausgabe.py` die Werkzeugausgabe
zeilengenau gegen den eingefrorenen Beleg `archiv/ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt` hält
(Messung: Zeile 110 und 414 wichen ab). Ein Beleg, der bei einer Pfadumbenennung rot wird, bewacht
den Wortlaut, und der Wortlaut nennt das Dokument mit seinem damaligen Namen.

## E-017 — Geldbeträge tragen ihre Währung; ein fehlender Kurs ist eine Sperre, keine 1 (2026-09-03)

**Kriterium.** Der Befund D3 (Bewertung 3.3) ist keine Stelle, sondern eine Klasse: sechs Stellen multiplizierten
`contract_size * price` und teilten einen Betrag in Kontowährung durch einen Abstand in Notierungswährung. Eine
Behebung, die nur diese sechs Stellen umrechnet, lässt die siebte zu. Darum muss der Typ die Klasse sperren.

**Wahl.** Neues Modul `mt5_trading_ai/risk/waehrung.py`: `Betrag(wert, waehrung)` rechnet nur in gleicher Währung,
`umgerechnet(nach, kurs)` verlangt einen gegebenen Kurs, `kurs=None` bei ungleicher Währung ist `WaehrungsFehler`.
Die Kursquelle ist das Terminal (`kurs_aus_ticks`: Mittelkurs von VONNACH, sonst Kehrwert von NACHVON, sonst
`None`); `Mt5Venue.kurs(von, nach)` stellt sie dem Orderpfad bereit. `size_position` bekommt Kontowährung,
Notierungswährung und Kurs als Pflichtparameter — kein Kurs, keine Größe (`fx_unverifiable`, Regel 7).
Die Marge entsteht in der Margenwährung des Instruments (`Instrument.margin_currency` aus `currency_margin`
des Terminals; Basiswährung → Volumen × Kontraktgröße, Notierungswährung → zusätzlich × Preis) und wird in
die Kontowährung umgerechnet oder gesperrt.

**Verworfen.** (a) Kurs per Vorgabe 1, wenn keiner vorliegt — genau der Fehler, den D3 beschreibt. (b) Eine
Umrechnungstabelle in `config/` — Kurse sind Messwerte des Terminals, keine Konfiguration. (c) Umrechnung
nur in `sizing.py` — der Margendeckel im Runner und der Preflight rechnen dieselbe Klasse.

**Eigener Fehler dabei.** Die Marge für 0,01 Lot USDJPY erwartete ich mit 33,33 USD (Kontohebel 30); die
Hebelklammer der Klasse ist 5, richtig sind 200 USD. Der Eichfall pinnt jetzt Hebel und Rechnung, nicht
nur die Zahl. Die Bewertung nannte ebenfalls 33 USD.

## E-018 — Zählbasis der Obergrenze: Wurzel + eigene PROGRAMM/-Dateien; Vorregistrierungen sind gesichert, nicht lebend (2026-09-04; ersetzt den Zählsatz von E-012)

**Anlass.** Gegenlese T5 (Einwände B4, B5): E-012 sagte, `check_docs_claims.py` zähle die eigenen
`PROGRAMM/`-Dateien nicht gegen die Obergrenze; der T5-Code (`counted()` = alle lebenden) zählt sie
seit 102f68d. Der Code ist richtig, der Registereintrag war es nicht mehr. Dazu die Rechnung des
Prüfers: 3 Wurzel + 8 feste PROGRAMM-Dateien + 2 je Auftrag × 9 = 29 von 32 — und jede
Vorregistrierung wäre eine weitere lebende Datei, die der Hook weder archivieren noch löschen lässt.

**Kriterium.** Die Mengenregel (A14) unterscheidet lebend (wird bearbeitet, wird gezählt und
geprüft) von gesichert (wird nie mehr geändert, Manifest statt Scan). Vorregistrierungen sind per
Wächter nach dem Schreiben unveränderlich — sie gehören nach diesem Kriterium zur zweiten Klasse,
nicht zur ersten. Die Obergrenze 32 bleibt (Katalog eingefroren).

**Entscheidung.** Zählbasis = Wurzel (genau README.md, MODULES.md, CLAUDE.md) + eigene Dateien unter
`PROGRAMM/` ohne `eingang/`, `masterprompts/` und `vorregistrierung/`. `PROGRAMM/vorregistrierung/`
wird per Manifest (`PROGRAMM/vorregistrierung/MANIFEST.sha256`, `tools/archiv_manifest.py`) gesichert;
das Manifest wird nur beim Anlegen einer neuen Vorregistrierung erneuert (`--schreiben --erneuern`),
und der Wächter lässt bestehende Einträge unverändert. Nachträge zu Aufträgen stehen in
`entscheidungen.md`, `fehler.md`, `geloescht.md` (anhängend), nicht in neuen Dateien. Damit sind
12 von 32 belegt (Stand 2026-09-04) und 2 je weiterem Auftrag; die Vorregistrierungen zählen nicht.

**Verworfen.** (a) Obergrenze anheben — verboten (Regel 6). (b) Vorregistrierungen in eine
einzige anhängende Datei — der Wächter schützt Dateien, nicht Absätze; ein Nachtrag wäre nicht von
einer Änderung zu unterscheiden. (c) E-012 umschreiben — Register bleiben stehen; dieser Eintrag
ersetzt den Zählsatz von E-012 ausdrücklich.

**Messung.** `python tools/check_docs_claims.py` vor dieser Änderung: 13/32; danach: 12/32
(`PROGRAMM/vorregistrierung/00-HINWEIS.md` ist gesichert statt lebend); `python
tools/archiv_manifest.py --pruefen` nennt vier Ordner. Tests: `tests/test_doku_menge.py`.

## E-019 — Ein Katalogsymbol, das der Broker nicht führt, wird im Katalog als „nicht angeboten“ geführt, mit Messung; Adapter und Smoke lassen es benannt durch (2026-09-04)

**Anlass (gemessen, T9 Lauf 1, `belege/09-smoke-lauf1.txt`).** Der lesende Smoke-Test am Demo-Terminal
(Server MetaQuotes-Demo) löst sechs von sieben Katalogsymbolen auf; `BTCUSD` (Klasse crypto) nicht.
Lesend geprüft: 12.455 Symbole in den Gruppen Forex, Indexes, Metals, Nasdaq; kein Krypto-CFD; `BTC`
ist dort ein Nasdaq-ETF (Grayscale Bitcoin Mini Trust). `Mt5Venue.list_instruments` wirft laut Vertrag
bei einem nicht auflösbaren Katalogsymbol (`UnknownInstrumentError`), der Smoke endet mit Exit 1 — A9
ist an diesem Broker so nicht erreichbar.

**Kriterium.** Der Katalog ist die belegte Quelle des Universums; ein Symbol still wegzulassen ist
verboten (Vertragstext in `venue/mt5.py`). Die Datenlage muss aber die Wahrheit tragen: welche
Katalogsymbole dieser Broker führt, ist eine Messung, kein Wunsch. Die Schwelle (jedes Katalogsymbol
muss auflösbar sein) bleibt für alle Symbole, die als angeboten gelten.

**Entscheidung.** Der Katalogeintrag bekommt das Feld `angebot`: `{"angeboten": false, "broker":
"MetaQuotes-Demo", "gemessen_am": "2026-09-04", "beleg": "PROGRAMM/auftrag-01-fundament/belege/09-smoke-lauf1.txt"}`
— nur für `BTCUSD`. `venue/catalog.py` liest das Feld (`CatalogEntry.angeboten`, Vorgabe `true`);
`Mt5Venue.list_instruments` und der Smoke führen ein als nicht angeboten gemessenes Symbol als benannten
Schritt „laut Katalog bei diesem Broker nicht angeboten (gemessen <Datum>)“ statt als Fehler; ein
Symbol OHNE dieses Feld, das das Terminal nicht auflöst, bleibt ein Fehler (Vertrag unverändert).
Ein Symbol mit `angeboten: false`, das das Terminal DOCH auflöst, ist ebenfalls ein Fehler (die Messung
ist dann veraltet). Kosten-, Hebel- und ATR-Daten von `BTCUSD` bleiben im Katalog (Auftrag 3 entscheidet
über das Universum).

**Verworfen.** (a) `BTCUSD` löschen — greift in das Universum ein (Auftrag 3) und in eingefrorene
Belege (Kostentor-Ausgabe). (b) Den Smoke das Symbol still überspringen lassen — genau das verbietet der
Vertrag. (c) Anderen Broker/Server wählen — Haltepunkt (Broker/Klasse), nicht meine Entscheidung.

**Umsetzung.** Nach dem Einspielen der T6-Familien (berührt `venue/mt5.py`), mit Eichfall rot/grün
(`tests/eichfall_katalog_angebot.py`) und Smoke-Lauf 2 (`belege/09-smoke.txt`). Bis dahin ist A9 rot.
