# PROGRESS — mt5_trading_ai

Angehaengt, nie ueberschrieben. Je Paket ein Eintrag. Jede Zahl gemessen
(`measured`, 2026-08-11), oder als Schaetzung gekennzeichnet. Keine
Reifegradbehauptung, keine Note.

---

## ERLEDIGT U0 — Sicherung und Bestandsaufnahme

**Was geschehen ist:** Der Altbestand wurde unter dem Tag `archive/pre-extraction`
(→ `5c39ebb`) gesichert und auf dem Remote nachgewiesen. Die zwoelf Kandidaten aus Teil 4
wurden gemessen; der entscheidende Befund ist, dass alle elf Kernmodule import-sauber sind
(nur stdlib, plus ein interner Verweis `learning_phase → trials_ledger`, der selbst
mitkommt). Vollstaendige Messung im Altbestand unter `HERKUNFT.md`.

**Abnahme:** `git ls-remote --tags` zeigt `archive/pre-extraction`; `ruff` 11/11 pass;
`mypy --strict` 11/11 pass; `pytest --collect-only` = 154 Faelle. Details in `HERKUNFT.md`.

**Entscheidungen, die ich selbst getroffen habe:** U0 wurde ausschliesslich messend
gefahren, ohne Schreiblast, weil `C:` zu dem Zeitpunkt 0 Byte frei hatte. Die Negativfahrt
von U2 wurde vorab aus dem echten Code berechnet, damit sie beim Ausfuehren eine Vorhersage
bestaetigt statt eine offene Frage zu sein.

**Auffaelligkeiten, gemeldet, nicht angefasst:** `venues/protocol.py` hat keine Testdatei;
`splits.py` (U3) liegt am erwarteten Pfad.

---

## ERLEDIGT U1 — Leeres Paket und Werkzeugkette

**Was geschehen ist:** Ein neues Paket `mt5_trading_ai/` wurde unter `C:\Users\Acer\mt5_trading_ai`
angelegt — ausserhalb des Altbaums und ausserhalb von OneDrive. Es enthaelt die
Verzeichnisstruktur aus Teil 2, `pyproject.toml` (Ruff/Mypy/Pytest), `README.md`,
`.env.example`, `.gitignore` und einen Rauchtest. Ein frisches `git init` mit einem ersten
Commit haelt es von der alten Historie getrennt.

**Abnahme (Befehle und Ausgaben):**
```
$ python -c "import mt5_trading_ai, inspect; print(inspect.getfile(mt5_trading_ai))"
C:\Users\Acer\mt5_trading_ai\mt5_trading_ai\__init__.py        # zeigt in den NEUEN Baum
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai
Success: no issues found in 7 source files
$ python -m pytest -q
1 passed in 0.09s
```

**Entscheidungen, die ich selbst getroffen habe:** Ort `C:\Users\Acer\mt5_trading_ai` statt
eines Geschwisterordners im OneDrive-Baum, um Sync-Last und Platzrisiko auf der knappen
Platte zu vermeiden; die Isolation (`import mt5_trading_ai` zeigt in den neuen Baum) ist
nachgewiesen. Die Ruff-Konfiguration ist bewusst identisch zum Altbestand (line-length 88,
Regelauswahl `E,F,I,UP,B`, Test-Ausnahmen `E402,E501`), damit „gruen im Alt" und „gruen im
Neu" dasselbe bedeuten.

**Eigene Fehler in diesem Paket:** keine in U1 selbst.

**Zeilenstand:** leeres Paket, nur Geruest.

---

## ERLEDIGT U2 — Risiko- und Sperrschicht umgezogen

**Was geschehen ist:** Die elf Module aus Teil 4.1 und ihre zehn Testdateien wurden in den
neuen Baum kopiert, die Importe von `shared_py.*` auf die neuen Paketpfade umgeschrieben
(`from shared_py import trials_ledger` → `from mt5_trading_ai.gates import trials as
trials_ledger`). Nach dem Umzug ist keine `shared_py`-Referenz mehr im Paket. Die beiden
Sperren wurden anschliessend absichtlich beschaedigt und liefen rot, bevor der Schaden
zurueckgenommen wurde.

**Abnahme (Befehle und Ausgaben):**
```
$ grep -rn 'shared_py' mt5_trading_ai tests
(keine)
$ python -m pytest -q
155 passed in 0.85s                 # 154 Kern-Faelle + 1 Rauchtest
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai
Success: no issues found in 18 source files
```

**Negativ gefahren — Hebelklammer** (`min(want, SYSTEM_MAX_LEVERAGE, cap)` → `min(want, cap)`):
```
# mit Schaden — rot wird GENAU {fx_major, fx_minor, gold, index_major} (Deckel > 10):
FAILED ...test_class_cap_is_enforced[fx_major-30-10-10]
FAILED ...test_class_cap_is_enforced[fx_minor-20-10-10]
FAILED ...test_class_cap_is_enforced[gold-20-10-10]
FAILED ...test_class_cap_is_enforced[index_major-20-10-10]
FAILED ...test_no_class_can_exceed_system_cap[fx_major-30-10-10]
FAILED ...test_no_class_can_exceed_system_cap[fx_minor-20-10-10]
FAILED ...test_no_class_can_exceed_system_cap[gold-20-10-10]
FAILED ...test_no_class_can_exceed_system_cap[index_major-20-10-10]
8 failed, 15 passed
# equity (5) und crypto (2) bleiben gruen — dort bindet ohnehin der Klassendeckel.
# Schaden zurueckgenommen:
23 passed in 0.56s
```

**Negativ gefahren — Live-Freigabe** (`if missing:` → `if len(missing) > 1:`):
```
# mit Schaden — 9 rot, 5 gruen; test_default_configuration_blocks bleibt GRUEN (0 Treffer):
FAILED ...test_every_proper_subset_of_switches_still_blocks
FAILED ...test_all_switches_without_release_id_still_blocks
FAILED ...test_missing_attribute_counts_as_not_met
FAILED ...test_truthy_is_not_true[1_0]
FAILED ...test_truthy_is_not_true[true]
FAILED ...test_truthy_is_not_true[yes]
FAILED ...test_truthy_is_not_true[1_1]
FAILED ...test_truthy_is_not_true[truthy4]
FAILED ...test_truthy_is_not_true[truthy5]
9 failed, 5 passed
# Beleg: der bequeme Fall (alle Schalter aus) haette den Defekt durchgelassen; erst
# test_every_proper_subset_of_switches_still_blocks macht ihn sichtbar.
# Schaden zurueckgenommen:
14 passed in 0.10s
```

**Entscheidungen, die ich selbst getroffen habe:** Die Tests behalten ihre Originalnamen in
einem flachen `tests/`-Verzeichnis (kein Umbenennen auf die neuen Modulnamen) — minimale
Aenderung, erhaelt die Rueckverfolgbarkeit zum Archiv. Kopie aller elf Module in einem
mechanischen Schritt mit anschliessender Pruefung je Testdatei, weil die Module stdlib-rein
und voneinander unabhaengig sind; ein Fehlschlag isoliert damit auf seine Datei. `mypy
--strict` gilt fuer das Paket `mt5_trading_ai` (Teil 8, Punkt 2), Tests bestehen `ruff`.

**Eigene Fehler in diesem Paket:** Die mechanische Import-Umschreibung veraenderte die
Import-Sortierung und erzeugte 7 `ruff`-Fehler (I001) in Testdateien. Von `ruff` gefangen,
mit `--fix` (nur Sortierung) behoben; `pytest` war davor und danach unveraendert bei 155.

**Auffaelligkeiten, gemeldet, nicht angefasst:** `venues/protocol.py` ist ohne eigenen Test
umgezogen (es gab keinen). Gehoert in `VERLUST.md` (U5).

**Zeilenstand (gemessen):**
```
$ find mt5_trading_ai -name '*.py' | xargs wc -l | tail -1
2490 total
$ find tests -name '*.py' | xargs wc -l | tail -1
1440 total
```
Summe `.py` im Paket: 3.930. Zielgroesse < 6.000; splits.py (U3) und Werkzeuge (U4) kommen
noch hinzu, bleiben aber deutlich darunter.

---

## ERLEDIGT U3 — Validierungsschicht (Zeitreihen-Splits) umgezogen

**Was geschehen ist:** Aus `learning_engine/backtest/splits.py` sind nur die drei
Funktionen `purged_walk_forward_indices`, `purged_kfold_embargo_indices`,
`walk_forward_indices` samt der Helfer, die sie brauchen (`Range`, `_overlaps`,
`_band_for_purge_and_embargo`), nach `mt5_trading_ai/backtest/splits.py` uebernommen — die
fuenf uebrigen Funktionen blieben zurueck. Der Test zog mit (ohne seinen sys.path-Shim).
Der Fix, der den letzten Fold bis zum Datenende fuehrt, ist enthalten.

**Default-Korrektur (Auftrag Teil 3 VI), berichtet:** `purge_ms` und `embargo_ms` trugen
im Altbestand den Default `0`. **Alt:** `purge_ms: int = 0, embargo_ms: int = 0` (bzw.
`purge_ms: int = 0` in der K-Fold-Variante). **Neu:** pflichtige keyword-only-Parameter
ohne Default. Ein stiller Null-Default sieht im Protokoll aus wie eine Sperre und ist offen.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
175 passed              # 155 (U2) + 20 (Splits)
$ python -m pytest tests/test_splits.py -q
20 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai
Success: no issues found in 19 source files
```

**Negativ gefahren — Fold-Fix zurueckgenommen** (`hi = n if i==k-1 else …` → `hi = …`):
```
# 15 rot / 5 gruen — rot: die drei 'reaches_the_last_sample'-Gruppen (je 5 Faelle),
# gruen: die 5 Leckage-Gegenproben. Deckt sich mit dem Auftrag ("15 rote von 20").
15 failed, 5 passed
# no_leakage-FAILED: 0   (die Gegenprobe bleibt gruen, weil der Fehler ein Auslassen war,
#                         kein Ueberschneiden)
# Schaden zurueckgenommen:
20 passed
```

**Entscheidungen, die ich selbst getroffen habe:** Statt eines willkuerlichen
Nicht-Null-Defaults (jeder ms-Wert waere ohne Kenntnis der Datenrate falsch) sind
`purge_ms`/`embargo_ms` pflichtig — die staerkste Fail-Closed-Form, und die bewusste Wahl
`0` (Abdeckungstest) bleibt sichtbar. Nur die drei genannten Funktionen plus die von ihnen
benoetigten Helfer kamen mit; die fuenf uebrigen (`purged_kfold_embargo`,
`walk_forward_splits`, `range_bounds_for_indices`, `range_time_overlap`,
`build_purge_embargo_guard_band`) gehoeren in `VERLUST.md`.

**Eigene Fehler in diesem Paket:** Meine Restore-`sed` (`hi = min(` →
`hi = n if i==k-1 else min(`) traf als Teilzeichenkette auch `embargo_hi = min(` und
veraenderte diese Zeile ungewollt — funktional wirkungslos (fuer den letzten Fold ist das
Embargo-Fenster ohnehin leer), aber eine stille Mutation. Mit einem `diff` gegen das
Original gefunden und punktgenau zurueckgesetzt; die Algorithmuszeilen sind nun
zeichengleich zum Altbestand.

**Auffaelligkeiten, gemeldet, nicht angefasst:** Die Testdatei enthielt bereits alle vom
Auftrag verlangten Faelle (`n=100/k=7`, `n=97/k=5`, `n=10/k=3`, dazu `50/3`, `101/4`) und
eine fertige Leckage-Gegenprobe — gemessen, nicht neu geschrieben.

**Zeilenstand:** `mt5_trading_ai/backtest/splits.py` = 190 Zeilen; Paket-Summe waechst
entsprechend, bleibt deutlich unter 6.000.

---

## ERLEDIGT U4 — Doku-Tore umgezogen und erweitert

**Was geschehen ist:** `check_docs_claims.py` uebernommen — es prueft bereits **jede** vom
Git verfolgte Markdown-Datei (`git ls-files *.md`), keine Auswahl; damit ist die vom
Auftrag verlangte Ausweitung schon erfuellt. `gen_docs.py` wurde auf das neue Paket
umgestellt: der alte erzeugte Service-/Konfigurationsdoku aus einem Manifest und den
Settings-Klassen (beides im Kern nicht vorhanden), der neue erzeugt `MODULES.md` aus dem
Paket-AST, mit `--check`-Gate. Dazu ein neuer, blockierender README-Zahlentest.

**Abnahme (Befehle und Ausgaben):**
```
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (159 Zeilen).
$ python tools/check_docs_claims.py
ok - 3/12 Markdown-Dateien, keine Zusicherung ohne Beleg
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 21 source files
$ python -m pytest -q
178 passed
```

**Negativ gefahren — README-Zahlentest** (falsche Zahl eingetragen):
```
# module_count 12 -> 13:
FAILED tests/test_readme_numbers.py::test_readme_module_count_matches_code
1 failed, 2 passed
# zurueckgenommen:
3 passed
```

**Entscheidungen, die ich selbst getroffen habe:** `gen_docs` wurde adaptiert statt
woertlich umgezogen — seine alten Quellen (Service-Manifest, Settings-AST, `.env*.example`)
existieren im Kern nicht, ein Verbatim-Port waere sofort gescheitert; der Zweck (Doku aus
Code + Gate) bleibt, der Umfang ist das neue Paket. `mypy --strict` habe ich zusaetzlich
ueber `tools/` gefahren (ueber das Teil-8-Minimum `mypy --strict mt5_trading_ai` hinaus), um
Teil 3 VIII fuer selbstgeschriebenen Code einzuloesen; die Tests bleiben unter `ruff` +
`pytest`.

**Eigene Fehler in diesem Paket:** Der uebernommene `check_docs_claims.py` trug 6
E501-Zeilen und eine `mypy --strict`-Verletzung (eine Schleifenvariable war erst `Path`,
dann `str`) — im Altbestand nie gefangen, weil dessen CI 0 Produktionsdateien lintete.
Genau der Befund, den Teil 3 VIII beschreibt. Beim Umzug behoben: Zeilen umbrochen,
Schleifenvariable umbenannt; Logik und Meldungen unveraendert.

**Auffaelligkeiten, gemeldet, nicht angefasst:** `MAX_MARKDOWN_FILES = 12`; aktuell 3
verfolgte Markdown-Dateien, viel Luft.

**Zeilenstand:** `tools/gen_docs.py` und `tools/check_docs_claims.py` neu; `MODULES.md`
generiert (159 Zeilen, nicht handgepflegt). Paket-Quellcode `mt5_trading_ai/` unveraendert 2.680.

---

## ERLEDIGT U5 — Verlustnachweis (VERLUST.md), vorgelegt

**Was geschehen ist:** Der Altbestand (15 Dienste unter `services/`, dazu `shared_py/` und
`config/`) wurde per Subagent vollstaendig aus dem Code enumeriert. `VERLUST.md` ordnet jede
Faehigkeit und **jede Sperre** einzeln ein (mitgekommen / neu zu schreiben / bewusst
entfallen), mit `pfad:zeile`-Ankern und Begruendung bei „entfallen". Die zwei Pflicht-Befunde
sind uebernommen.

**Abnahme (Befehle und Ausgaben):**
```
$ python tools/check_docs_claims.py
ok - 4/12 Markdown-Dateien, keine Zusicherung ohne Beleg
```
`VERLUST.md` vollstaendig; jede Sperre eingeordnet; keine Zeile ohne Einordnung.

**Ueberraschender Befund, zuerst verstanden (Regel 12):** Die Auftragsangabe „Hebelklammer
war nicht angeschlossen" stimmt nur fuer den **Live-Broker-Order-Pfad**. Gemessen ist der
7/75-Deckel in `signal-engine`, `paper-broker` und `shared_py` sehr wohl verdrahtet
(`risk_governor.py:558` u. a.). Zwei Konsequenzen im Bericht festgehalten: der Live-Pfad war
ungeklammert (aber durch Befund 1 ohnehin blockiert), und der Kern **senkt die Obergrenze
von 75 auf 10** (ESMA-Deckel), die alten 7/75-Defaults bleiben bewusst zurueck.

**Entscheidungen, die ich selbst getroffen habe:** Enumeration per Subagent statt manuell,
weil der Altbaum gross und die Platte langsam ist; das Ergebnis ist mit `pfad:zeile`-Ankern
nachpruefbar. Der grosse Fail-Closed-Apparat des Live-Pfads (Kill-Switch, Global-Halt-Latch,
Runtime-Safety-Oracle, Exchange-Readiness mit `WRITE_ORDER_ALLOWED_DEFAULT=False`, VPIN-Halt,
Positions-Drift-Halt …) ist als **neu zu schreiben** eingeordnet — nichts davon kann der Kern
heute tragen, aber jedes muss stehen, bevor ein Ausfuehrungspfad entsteht.

**Auffaelligkeiten, gemeldet, nicht angefasst:** Kein Dienst hat ein eigenes README; die
Faehigkeiten sind aus `app.py`-Importen und Modulbaeumen abgeleitet.

---

## ERLEDIGT U6 — Endzustand hergestellt

**Was geschehen ist:** Philipp entschied „voll archivieren, auftragstreu" — nichts kommt
aus `VERLUST.md` nachtraeglich mit; alle offenen Faehigkeiten/Sperren bleiben in `FEHLT.md`
fuer den naechsten Auftrag. Die 16 `.pth`-Eintraege, die in den Altbaum zeigten, sind
entfernt (die `strategy-validation`-`.pth` eines anderen Projekts blieb unangetastet).
`FEHLT.md` ist geschrieben. Die **funktionale** Isolation ist hergestellt (16 `.pth` weg,
`import signal_engine` scheitert). Die **Umbenennung** des Altbaums in `_archiv` schlug im
Session-Kontext fehl — `mv` meldete `Device or resource busy`, weil der Ordner das
Arbeitsverzeichnis der Session ist und zusaetzlich von OneDrive gehalten wird. Sie ist der
einzige offene, umgebungsbedingt **manuell** nachzuholende Handgriff (aus einem Terminal
ausserhalb des Ordners). Der Altbaum ist **nicht geloescht** und per Tag
`archive/pre-extraction` auf dem Remote gesichert.

**Abnahme (Befehle und Ausgaben):**
```
$ (16 .pth mit Bezug bitget-btc-ai entfernt)
$ python -c "import signal_engine"
ModuleNotFoundError: No module named 'signal_engine'      # die stille Probe: scheitert
$ python -c "import mt5_trading_ai, inspect; print(inspect.getfile(mt5_trading_ai))"
C:\Users\Acer\mt5_trading_ai\mt5_trading_ai\__init__.py          # zeigt weiter in den neuen Baum
$ python -m pytest -q
178 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 21 source files
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell
$ python tools/check_docs_claims.py
ok - 5/12 Markdown-Dateien, keine Zusicherung ohne Beleg
```

**Entscheidungen, die ich selbst getroffen habe:** Reihenfolge — `.pth` zuerst, Umbenennung
zuletzt, weil der Altbaum das Session-Verzeichnis ist und seine Umbenennung den Pfad
entzieht. `README.md` wurde nicht neu geschrieben: es beschreibt bereits, was das Paket ist,
kann und nicht kann, und seine Kennzahlen sind gemessen und per Test gegen den Code
gesperrt.

**Zeilenstand (gemessen):** `.py` gesamt **4.462** (Quellcode `mt5_trading_ai/` 2.680, Tests
1.567, Werkzeuge `tools/` 215). Zielgroesse < 6.000 eingehalten.

---

## Endzustand

Sechs Pakete, sechs Commits. Der Kern ist gruen, seine Sperren werden nachweislich rot,
wenn man sie beschaedigt, seine Splits reichen bis zum Datenende und tragen kein
Null-Purge, seine Doku kann nicht mehr behaupten, was der Code nicht tut. `VERLUST.md`
sagt, was zurueckblieb; `FEHLT.md`, was der naechste Auftrag fuellt. Der Altbestand ist per
Tag `archive/pre-extraction` gesichert, und `import signal_engine` scheitert; die
Umbenennung des Ordners in `_archiv` ist umgebungsbedingt manuell nachzuholen.

---

## ERLEDIGT — Umbenennung in MT5 Trading AI

**Was geschehen ist:** Das gesamte Paket ist von `mastertrade` in **`mt5_trading_ai`**
umbenannt — Wurzelordner (`C:\Users\Acer\mt5_trading_ai`), Python-Paket (`mt5_trading_ai/`),
Distributionsname (`mt5-trading-ai`) und **jede Referenz in jeder Datei**. Alle 43 Dateien
wurden angefasst und geprueft; keine blieb unberuehrt. **Entscheidung „bleibt/geht":** alle
43 bleiben — jede hatte in U0–U6 einzeln ihren Nachweis; etwas zu entfernen braeche den Kern.

**Abnahme (Befehle und Ausgaben):**
```
$ git ls-files | grep -v __pycache__ | xargs grep -li mastertrade
(leer)
$ python -c "import mt5_trading_ai, inspect; print(inspect.getfile(mt5_trading_ai))"
C:\Users\Acer\mt5_trading_ai\mt5_trading_ai\__init__.py
$ python -m pytest -q
178 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 21 source files
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (159 Zeilen)
$ python tools/check_docs_claims.py
ok - 5/12 Markdown-Dateien, keine Zusicherung ohne Beleg
```

**Entscheidung, die ich selbst getroffen habe:** Ordner und Importpaket beide
`mt5_trading_ai` (Unterstrich, konsistent und importierbar); der Distributionsname bleibt
`mt5-trading-ai` (Bindestrich, PyPI-Konvention). Der alte Baum `bitget-btc-ai` ist davon
unberuehrt und weiterhin per Tag gesichert.

---

## ERLEDIGT — MT5-Venue-Anbindung mit Vertragstest

**Was geschehen ist:** Der erste Punkt aus `FEHLT.md` (Anbindung) ist gebaut.
`mt5_trading_ai/venue/mt5.py` implementiert das `TradingVenue`-Protokoll (`Mt5Venue`),
gespeist aus der schmalen, injizierbaren Naht `Mt5Terminal`. Die reale MetaTrader5-Bindung
(`RealMt5Terminal`) liegt als duenne, optionale Schicht daneben; `MetaTrader5` wird nur lazy
geladen, der Modulimport bleibt stdlib-rein. Der Vertragstest (`tests/test_mt5_venue.py`, 18
Faelle) prueft Protokoll-Konformitaet, MT5→Protokoll-Abbildung und das Sicherheitstor — damit
hat `venue/protocol.py` erstmals einen Test.

**Sicherheit — das Live-Freigabe-Tor ist verdrahtet, nicht umgangen:** Eine **eroeffnende**
Order an ein **Live**-Konto passiert nur mit vollstaendiger Freigabe (`execution/release.py`);
Demo und Reduce-Only passieren ohne. Der Schreibpfad von `RealMt5Terminal` ist zusaetzlich
`allow_write=False` (fail-closed) — auch das echte Terminal sendet keine Order, bevor es
bewusst nach einem Demo-Smoke-Test freigegeben wird.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
196 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 22 source files
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (174 Zeilen)
```

**Negativ gefahren — Live-Freigabe-Tor** (`if account.is_demo:` → `if True:`):
```
# mit Schaden: die Live-Order wird faelschlich akzeptiert
FAILED tests/test_mt5_venue.py::test_live_opening_order_blocked_without_release
1 failed
# Schaden zurueckgenommen:
18 passed
```

**Entscheidungen, die ich selbst getroffen habe:** Die MT5→Protokoll-Abbildung liegt im
Adapter (getestet gegen ein Fake-Terminal), nicht in der Terminal-Bindung — so ist der
riskante Teil geprueft. `RealMt5Terminal` ist nicht unit-getestet (kann es ohne Terminal
nicht sein) und deshalb schreibgesperrt. Der Instrumentenkatalog (Klasse/Kosten/Zeiten) wird
injiziert; ohne Eintrag ist ein Symbol unbekannt (fail-closed).

**Auffaelligkeiten, gemeldet, nicht angefasst:** Die Hebelklammer steckt noch nicht im
Order-Pfad (das Protokoll traegt kein Hebelfeld); das bleibt der naechste Anschluss.
`RealMt5Terminal` braucht einen Demo-Smoke-Test, bevor `allow_write=True` sinnvoll ist.

**Zeilenstand (gemessen):** `venue/mt5.py` neu; Paket-Quellcode `mt5_trading_ai/` = 3.381
Zeilen.

---

## ERLEDIGT — Hebelklammer-Anschluss an den Order-Pfad

**Was geschehen ist:** Die (bereits getestete) Hebelklammer `risk/leverage.py` ist an den
Order-Pfad gebunden. `execution/leverage_preflight.py` verbindet die Klammer mit Instrument,
Konto und Auftrag: Klasse handelbar? (unbekannt/Krypto → no_trade), Hebel geklammert
(`min(want, 10, Deckel)`), Marge frei? `Mt5Venue.submit_order` ruft den Preflight bei
**jeder** eroeffnenden Order — fehlt ein Strategiewunsch, klammert die Klammer auf ihren
Default (Betriebsminimum), nie den gefaehrlichsten Wert. Damit ist der in `VERLUST.md` §3 /
`FEHLT.md` markierte Anschluss gebaut — **mit** dem Tor, nicht daran vorbei.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
202 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 23 source files
```

**Negativ gefahren — Hebel-Anschluss** (`self._enforce_leverage(...)` → `pass`):
```
FAILED tests/test_mt5_venue.py::test_venue_opening_blocks_untradeable_crypto
FAILED tests/test_mt5_venue.py::test_venue_opening_blocks_on_insufficient_margin
2 failed
# Schaden zurueckgenommen:
24 passed
```

**Entscheidungen, die ich selbst getroffen habe:** Der Preflight nimmt die freie Marge ueber
den Kontozustand (`AccountState`, Protokolltyp), nicht das MT5-Rohkonto — der Adapter reicht
`get_account()` hinein. Krypto (Deckel 2 < Betriebsminimum 5) ist im Order-Pfad damit
**nicht handelbar** — fail-closed, wie schon in `VERLUST.md` vermerkt.

**Auffaelligkeiten, gemeldet, nicht angefasst:** Der effektive geklammerte Hebel muss am
realen Terminal noch je Symbol gesetzt werden (MT5-Symbol-Leverage/Margin); bisher prueft
der Preflight, dass die noetige Marge zum geklammerten Hebel frei ist. Das gehoert an die
reale Terminal-Bindung.

**Zeilenstand (gemessen):** `execution/leverage_preflight.py` neu; Paket-Quellcode
`mt5_trading_ai/` = 3.496 Zeilen, 14 Module, 148 Testfunktionen.

---

## ERLEDIGT — Instrumentenkatalog (versioniert, fail-closed)

**Was geschehen ist:** `mt5_trading_ai/venue/catalog.py` laedt den Instrumentenkatalog aus
einer versionierten Datei (`config/instrument_catalog.json`, mit Quelle/Gueltigkeits-/
Pruefdatum): je Symbol die Anlageklasse (steuert den Hebeldeckel), das Kostenmodell und die
Handelszeiten — genau das, was MT5 nicht liefert. `CatalogEntry` wohnt jetzt hier (aus
`venue/mt5.py` hierher verschoben; `mt5.py` importiert es und reicht es weiter). Fail-closed:
jeder Defekt ist ein Fehler, kein Default; ein Symbol ohne Eintrag ist unbekannt.

**Anschluss an die Hebelpolitik:** Ein Test prueft, dass **jede** Anlageklasse im Katalog der
Hebelklammer bekannt ist (sonst faende sie keinen Deckel). Krypto steht im Katalog, ist aber
nicht handelbar (Deckel 2 < Betriebsminimum 5) — der Katalog kennt es, die Klammer nicht.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
215 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 24 source files
$ python tools/check_docs_claims.py
ok - 5/12 Markdown-Dateien, keine Zusicherung ohne Beleg
```

**Fail-closed geprueft (9 Faelle):** fehlende Datei, kaputtes JSON, fehlendes Pflichtfeld,
leere Instrumentenliste, unbekannte Anlageklasse, fehlende Kosten, Kosten ohne Waehrung,
leere und kaputte Handelszeiten — jeder wirft `InstrumentCatalogError`.

**Entscheidungen, die ich selbst getroffen habe:** Kosten und Handelszeiten in der Datei
sind **indikative** Platzhalter, in den Quellen der Datei ausdruecklich so ausgewiesen und je
Broker zu verifizieren; die handelsrelevante Zuordnung (Anlageklasse → Hebeldeckel) folgt der
ESMA-Klasseneinteilung aus `config/asset_class_leverage.json`. `CatalogEntry` verschoben,
damit die Katalog-Definition beim Katalog liegt, nicht beim Adapter.

**Zeilenstand (gemessen):** `venue/catalog.py` + `config/instrument_catalog.json` neu;
Paket-Quellcode `mt5_trading_ai/` = 3.640 Zeilen, 15 Module, 161 Testfunktionen.

---

## ERLEDIGT — Order-Lebenszyklus und Reconcile (Konto gegen Buch)

**Was geschehen ist:** `mt5_trading_ai/execution/reconcile.py` bringt ein lokales
Nettopositions-**Buch** (`PositionBook`) und den Reconcile-Vergleich Buch gegen Meldung.
`Mt5Venue` fuehrt das Buch aus jedem angenommenen Fill; `venue.reconcile()` vergleicht es mit
den gemeldeten Positionen und **rastet bei Notional-Drift ueber der Grenze in einen
Global-Halt**. Danach lehnt `submit_order` jede Eroeffnung ab (`reason="global_halt"`),
Reduce-Only bleibt frei. Der Latch klaert nicht selbst; `clear_halt()` ist die manuelle
Freigabe. Damit ist die in `VERLUST.md` §2b gelistete Positions-Drift-/Global-Halt-Sperre
gebaut, und Befund 1 (frischer Risikocheck vor Eroeffnung) ist beantwortet: der Reconcile
ist genau dieser frische Check, den das System selbst rechnet.

**Fail-closed in zwei Richtungen:** Notional-Drift ueber der Grenze haelt an; eine **nicht
bewertbare** Drift (kein Preis fuers Symbol) haelt ebenfalls an.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
226 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 25 source files
```

**Negativ gefahren — Halt-Tor** (`if self._halted:` → `if False:`):
```
FAILED tests/test_mt5_venue.py::test_reconcile_drift_halts_and_blocks_opening
1 failed
# Schaden zurueckgenommen:
35 passed
```

**Entscheidungen, die ich selbst getroffen habe:** Reconcile ist eine **Methode**
(`venue.reconcile()`), kein Automatismus je Order — der Betreiber/Scheduler ruft sie, das
Ergebnis rastet den Latch. So bleibt der Order-Pfad billig, und der Halt ist ein bewusster,
manuell zu loesender Zustand (wie der Drawdown-Halt in `loss_limits`). Standardgrenze
`max_notional_drift=0` (strengstmoeglich, fail-closed); der Betreiber kann lockern.

**Auffaelligkeiten, gemeldet, nicht angefasst:** Das Buch startet leer; nach einem Neustart
muss es aus der Boerse **adoptiert** werden, sonst meldet der erste Reconcile jede bestehende
Position als Drift (sichere Richtung, aber ein bewusster Adoptionsschritt gehoert in die
reale Terminal-Bindung).

**Zeilenstand (gemessen):** `execution/reconcile.py` neu; Paket-Quellcode `mt5_trading_ai/` =
3.804 Zeilen, 16 Module, 172 Testfunktionen.

---

## ERLEDIGT — Buch-Adoption beim Neustart

**Was geschehen ist:** `PositionBook.adopt(net_by_symbol)` ersetzt das Buch durch die
gegebenen Nettopositionen; `Mt5Venue.adopt_book()` uebernimmt die gemeldeten Positionen als
Buch. Bewusst **explizit** (kein Automatismus in `connect()` — das wuerde unerwartete
Positionen still uebernehmen); der Global-Halt-Latch bleibt unberuehrt (`clear_halt()` ist
getrennt). Damit ist der Neustart-Ablauf vollstaendig: Halt bei Drift → adoptieren →
deckungsgleich → freigeben.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
230 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 25 source files
```

**Adversariale Review (Workflow `review-book-adoption`, 4 Dimensionen, jede Fund-Behauptung
gegengeprueft):** 2 bestaetigte Befunde (beide „Test-Abdeckung"), beide eingearbeitet — die
ersten Adoptions-Tests bewiesen das **Ersetzen** nicht (sie starteten mit leerem oder
ueberlappendem Buch; eine `= {...}` → `.update({...})`-Merge-Regression waere gruen
durchgelaufen und haette ein Phantom im Buch gelassen, das der naechste Reconcile
faelschlich als Drift haelt).

**Negativ gefahren — Merge statt Ersetzen** (`self._net = {` → `self._net.update({`):
```
FAILED tests/test_reconcile.py::test_book_adopt_replaces_and_drops_zeros
FAILED tests/test_mt5_venue.py::test_adopt_book_empty_clears_prior_book
2 failed
# Schaden zurueckgenommen:
39 passed
```

**Entscheidungen, die ich selbst getroffen habe:** Adoption **ersetzt** (kein Zusammen-
fuehren), damit offline geschlossene Positionen das Buch tatsaechlich leeren. Der Unit-Test
pinnt jetzt ein nur-altes Symbol (muss wegfallen), und ein Venue-Test deckt die Gegenrichtung
(Buch gefuellt, Boerse leer → Buch leer); beide fangen die Merge-Regression.

**Zeilenstand (gemessen):** keine neue Datei; Paket-Quellcode `mt5_trading_ai/` = 3.822
Zeilen, 16 Module, 176 Testfunktionen.

---

## ERLEDIGT — Demo-Smoke-Test (Runner + Sicherheitslogik)

**Was geschehen ist:** `mt5_trading_ai/venue/smoke.py` (`run_smoke` + `SmokeReport`) faehrt
eine feste Folge gegen einen `Mt5Venue`: verbinden, Konto lesen und **auf Demo bestehen
(harter Abbruch)**, Marktdaten, Buch adoptieren, reconcilen, optional die Schreib-Probe
(winzige Order, sofort per Reduce-Only geschlossen). `tools/mt5_smoke.py` ist die CLI fuer die
MT5-Maschine (bindet `RealMt5Terminal`, haengt sich ans laufende Terminal, keine Zugangsdaten
auf der Kommandozeile). `RealMt5Terminal.initialize` meldet fehlendes `MetaTrader5` jetzt
sauber statt mit Traceback.

**Sicherheit — dreifach gegen Schreibzugriff auf Live:** Demo-Abbruch in `run_smoke`,
`RealMt5Terminal.allow_write=False`, und das Live-Freigabe-Tor. Standardlauf nur lesend.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
235 passed
$ python tools/mt5_smoke.py          # hier, ohne MetaTrader5:
!! connect: MetaTrader5 nicht installiert (pip install MetaTrader5)
SMOKE FEHLGESCHLAGEN
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 27 source files
```

**Negativ gefahren — Demo-Abbruch** (`if not account.is_demo:` → `if False:`):
`test_smoke_demo_guard_hard_stops_on_live` rot; die Schreib-Probe bleibt dennoch blockiert
(Live-Freigabe haelt) — defense-in-depth.
**Negativ gefahren — Tick-Rundung** (Stop ungerundet): `test_probe_stop_snaps_to_tick_grid`
rot, zurueckgenommen gruen.

**Adversariale Review (Workflow `review-demo-smoke`, 4 Dimensionen, 7 erhoben, 5 in der
Gegenpruefung verworfen, 2 bestaetigt) — beide eingearbeitet:**
1. Der Probe-Stop war nicht aufs Tick-Raster gerundet (`bid - bid*0.01` → Sub-Tick, MT5 lehnt
   mit INVALID_STOPS ab); jetzt in `_probe_stop`, tick-gerundet und getestet.
2. `RealMt5Terminal.order_send` behandelte `reduce_only` nicht (auf Hedging-Konten oeffnete
   der Close eine neue Gegenposition); jetzt wird die Gegenposition per Ticket geschlossen.

**Entscheidungen, die ich selbst getroffen habe:** Der eigentliche Terminal-Lauf ist der
Schritt des Betreibers (hier kein MT5); die Orchestrierung ist gegen ein Fake gepruft. Die
zwei Review-Befunde liegen im realen Schreibpfad, den genau dieser Smoke verifiziert — Fix 1
ist rasterrundungs-getestet, Fix 2 bleibt am Demo-Smoke gegen ein echtes Terminal zu
bestaetigen.

**Zeilenstand (gemessen):** `venue/smoke.py` + `tools/mt5_smoke.py` neu; Paket-Quellcode
`mt5_trading_ai/` = 3.998 Zeilen, 17 Module, 181 Testfunktionen.
