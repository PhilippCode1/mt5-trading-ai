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

---

## ERLEDIGT — Private WS-Sync (Konsument + Fail-closed)

**Was geschehen ist:** `mt5_trading_ai/execution/private_sync.py` (`PrivateSync`) konsumiert
den privaten Kontostrom (`PrivateEvent`: Fill/Heartbeat mit fortlaufender `seq`) und fuehrt
das Nettobuch. **Fail-closed bei Desync** in zwei Formen: **Sequenzluecke** (fehlende Nummer)
und **Stille** (`is_stale`/`healthy` gegen `max_silence`); malformte Fills ebenso. In
`Mt5Venue`: ist ein Strom angeschlossen, **fuehrt er das Buch** (geteiltes `PositionBook`),
und `submit_order` bucht nicht mehr optimistisch — der autoritative Fill tut es (kein
Doppel-Buchen). `apply_private_event` rastet bei Desync den Global-Halt; `check_sync` rastet
bei Stille; `clear_halt` resynchronisiert. Eroeffnungen sind waehrend des Halts gesperrt,
Reduce-Only frei.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
244 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 28 source files
```

**Negativ gefahren — Sequenzluecken-Check** (`event.seq != last_seq + 1` → `False`):
`test_sync_sequence_gap_is_desync` und `test_synced_venue_gap_halts_and_blocks_opening` rot,
zurueckgenommen 9 gruen.

**Entscheidungen, die ich selbst getroffen habe:** Der Strom ist autoritativ, wenn
angeschlossen — deshalb bucht der Submit dann nicht optimistisch (sonst Doppelzaehlung). Die
konkrete **Quelle** (Krypto-WS bzw. MT5-Deal-Abfrage) ist die boersenspezifische Bindung und
gehoert an den realen Lauf, wie `RealMt5Terminal`. Eine adversariale Review wurde gestartet;
sie war bei der Finalisierung (auf Wunsch „fertigstellen und pushen") noch nicht fertig — der
Code ist unabhaengig gruen und negativ gefahren; etwaige bestaetigte Befunde arbeite ich als
Nachtrag ein.

**Zeilenstand (gemessen):** `execution/private_sync.py` neu; Paket-Quellcode `mt5_trading_ai/`
= 4.112 Zeilen, 18 Module, 190 Testfunktionen.

---

## ERLEDIGT — Paket 0 (Teil 3): Bereinigung und Wahrheitsprüfung

**Was geschehen ist:** Die sechs Aufträge aus Paket 0 des Edge-Masterprompts.
- **A0.1** Sichtbarkeit/Historie: Repo ist öffentlich (Beleg `gh repo view … visibility`
  = PUBLIC). Historien-Scan über alle Refs: keine Zugangsdaten/Server/Kennungen committet
  (einzige „password"-Treffer sind der `password:`-Parameter und CLI-Argumente, kein Wert).
- **A0.2** Order-Pfad-Wahrheit: `submit_order` Zeile für Zeile gelesen. Ergebnis-Tabelle:
  `risk/limits.py`, `risk/sizing.py`, `risk/stop_budget.py`, `gates/evaluation.py` werden
  **nicht** im Order-Pfad aufgerufen (0 Treffer, kein Import). Getestete, aber verwaiste
  Inseln — dieselbe Fehlerklasse wie die alte Hebelklammer. Als **S1** in `SPAETER.md`.
- **A0.3** Befund 1: kein Frische-Mechanismus am Halt-Latch (`reconcile` ist betreiber-
  gerufen, kein Zeitstempel/Maximalalter). Befund bleibt **offen**; die frühere
  „beantwortet"-Behauptung ist hiermit als Nachtrag korrigiert. Als **S2** in `SPAETER.md`.
- **A0.4** Doku-Drift + Ursache: sieben Drift-Punkte behoben (Commit-Zahl, Test-Fallzahlen,
  `protocol.py`-Test, `docs/` im Baum, U5-Kästchen, Review-Zählung, Fix-2-Status). Ursache
  behoben durch neues Tor `tools/check_doc_numbers.py`: Live-Kennzahlen leben nur im
  README-Block, andere Live-Docs verweisen; „N Fälle je Testdatei" wird gegen die Ist-Zahl
  geprüft; harte Commit-Zahlen sind verboten; `PROGRESS.md` und `docs/audit/` sind als
  historische Belege ausgenommen (Rule 22).
- **A0.5** CI: das neue Tor als sechster Schritt in `.github/workflows/ci.yml`.
- **A0.6** E2 umgesetzt: Betriebsminimum Hebel gestrichen. `SYSTEM_MIN_LEVERAGE` und die
  zwei „unter-Minimum → no_trade"-Zweige entfernt; ESMA-Deckel je Klasse bleibt hart.
  Krypto handelt jetzt bei 2:1, niedrige Wunschhebel werden geklammert statt abgelehnt.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
247 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 29 source files
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (215 Zeilen).
$ python tools/check_docs_claims.py
ok - 8/12 Markdown-Dateien, keine Zusicherung ohne Beleg
$ python tools/check_doc_numbers.py
ok - Code: 18 Module, 193 Testfunktionen, 4129 Quellzeilen; Doku widerspruchsfrei.
```

**Negativ gefahren (das neue Zahlen-Tor, zwei Facetten):**
- README-Block: `source_lines` 4129 → 4128 → Tor **rot** („4128 im Block, Code sagt 4129")
  → zurückgenommen.
- Testfall-je-Datei: `FEHLT.md` `test_mt5_venue.py` 31 → 30 → Tor **rot** („30 behauptet,
  tatsächlich 31") → zurückgenommen → grün.

**Entscheidungen, die ich selbst getroffen habe:**
- Das Zahlen-Tor unterscheidet **Live**- von **historischen** Docs. `PROGRESS.md`
  (anhängendes Logbuch) und `docs/audit/` (datierter Snapshot) gegen den heutigen Code zu
  prüfen wäre Geschichtsfälschung (Rule 22) — sie sind ausgenommen. Live-Kennzahlen leben an
  **einer** Stelle (README-Block, Rule 9), MASTERBERICHT verweist nur noch.
- A0.6 „streichen" heißt: `DEFAULT_LEVERAGE` bleibt als konservativer Default bei fehlendem
  Wunsch; nur der **Boden** (Ablehnung unter Minimum) entfällt. Der Deckel bleibt unberührt.
- Die vier verwaisten Risikomodule (A0.2) habe ich **nicht** verdrahtet: Paket 0 baut keine
  Infrastruktur, und Venue-Schicht vs. Risiko-Manager-Schicht ist eine offene Designfrage
  (S1). „Mitgekommen und getestet" bleibt getrennt von „verdrahtet" benannt.

**Eigene Fehler:**
- Das Fallzahl-Muster `F[aä]lle` traf „Faelle" (ae-Schreibung, wie in `FEHLT.md`) nicht →
  auf `F(?:ä|ae)lle` erweitert.
- Die Windows-Konsole (cp1252) stürzte an einem `·` im Zitat ab → `stdout.reconfigure(utf-8)`.
- Der Zeilen-basierte Fallzahl-Check paarte in einem umgebrochenen Satz die falsche Datei mit
  der falschen Zahl (`test_mt5_smoke.py` mit 13 statt 5) → MASTERBERICHT §3.4 auf **eine**
  Datei+Zahl je Zeile umgestellt, damit die Paarung eindeutig ist.

**Auffälligkeiten, gemeldet, nicht angefasst:** S1–S4 in `SPAETER.md` — die vier verwaisten
Risikomodule (S1), der fehlende Frische-Latch (S2), die Modul-Zeilenzahl-Doppelung in
MASTERBERICHT §3 (S3, Rule 9), die Halal-Frage für Krypto-CFDs nach E2 (S4).

**Entscheidungstore an Philipp:** **E1** beantwortet — öffentlich lassen, gut lesbar für
LLM-Weiterarbeit. **E2** beantwortet — Betriebsminimum gestrichen (in A0.6 umgesetzt).

**Zeilenstand (gemessen):** `tools/check_doc_numbers.py` und `SPAETER.md` neu; `leverage.py`
um die zwei Minimum-Zweige gekürzt. Paket-Quellcode `mt5_trading_ai/` = 4.129 Zeilen,
18 Module, 193 Testfunktionen; 247 Testfälle grün.

---

## ERLEDIGT — Paket 1 (Teil 3): Das Kostenmodell

**Was geschehen ist:** Erst **Recherche R1** (`RECHERCHE_KOSTEN.md`): neun parallele
Web-Rechercheure + Plausibilitäts-Skeptiker zu Spread/Kommission/Swap/Slippage/A-B-Book/
Halal bei vier EU-MT5-Brokern (IC Markets, Pepperstone, Admirals, Tickmill), jede Zahl
measured/estimate/literature mit Quelle. **Tor E3 → IC Markets (EU)** (A-Book/ECN,
günstigster belegter Kanal, swapfrei auch für EU). Dann `mt5_trading_ai/costs/model.py`:
`order_roundturn_cost` (Spread aus echtem Bid/Ask · Kommission aus der Katalog-`FeeSchedule` ·
Slippage in Pips · Finanzierung je Nacht inkl. Dreifach-Tag), `load_cost_fees` (fehlende
Kosten → Fehler, nie Null), `hurdle_rate`. Der Katalog wurde von indikativen Platzhaltern auf
die IC-Markets-Werte gehoben (FX/Gold Kommission 7 USD RT, Indizes 0; Swaps aus R1).

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
273 passed
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 31 source files
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (225 Zeilen).
$ python tools/check_docs_claims.py
ok - 9/12 Markdown-Dateien, keine Zusicherung ohne Beleg
$ python tools/check_doc_numbers.py
ok - Code: 19 Module, 219 Testfunktionen, 4386 Quellzeilen; Doku widerspruchsfrei.
```

**Negativ gefahren:** Kommission im Modell auf `Decimal("0")` gezwungen →
`test_roundturn_cost_components` rot (`0 == 7` schlägt fehl) → zurückgenommen → grün. Das
Kostenmodell ist damit nachweislich verdrahtet (nicht hohl).

**hurdle_rate gegen Handrechnung:** 1 bp, 5 Trades/Tag, 250 Tage → Hebel 5 = 0,625 (62,5 %),
Hebel 10 = 1,25 (125 %). Beide Zahlen im Test (`test_hurdle_rate_matches_hand_calculation`)
und deckungsgleich mit der Vorgabe.

**Adversariale Review (§9, vor der Abnahme — nicht abgekürzt):** 15 Agenten, drei
Blickwinkel (Buchhalter/Angreifer/Betreiber) + Gegenkontrolle jedes Befunds. Erhoben 12,
**bestätigt 10, verworfen 2**. Der Buchhalter bestätigte EURUSD-Kernpfad + `hurdle_rate` als
korrekt. Zwei HIGH und mehrere MEDIUM waren **reale** Defekte in meinem Code — alle behoben:

**Eigene Fehler (von der Review gefunden, alle eingearbeitet):**
- **HIGH:** `quote_to_account_rate` hatte Default 1 — nicht-USD-notierte Instrumente (EURGBP
  in GBP) wären still ~25 % zu niedrig bewertet worden. Der eigene Docstring nannte genau
  diese stille 1 „eine versteckte Annahme". → `quote_currency` ist jetzt Pflicht; bei
  Währungsdifferenz ohne Kurs `CostModelError`.
- **HIGH:** Nicht-endliche Decimals (Infinity/NaN) umgingen die Guards (Infinity → still
  `total=Infinity`; NaN → `InvalidOperation` statt `CostModelError`). → `is_finite()`-Prüfung
  an jedem Preis/Größen/Kurs/Swap-Eingang.
- **MEDIUM:** Slippage-Default (1 Tick = 0,2 Pip RT) war als „konservativ" deklariert, lag
  aber unter dem ruhigen Mittel der eigenen Recherche → auf **Pips** umgestellt
  (`slippage_pips_per_side`, Default 0,5 Pip/Seite = oberer Rand des ruhigen Bandes), das
  behebt zugleich den Ticks-vs-Pips-10×-Footgun.
- **MEDIUM:** Kommission 0 schlüpfte für FX/Gold durch → `load_cost_fees` lehnt FX/Gold ohne
  Kommission jetzt fail-closed ab.
- **MEDIUM:** Aktien-CFD (ad valorem) passt nicht in die Fixbetrag-`FeeSchedule` → im
  Kostenpfad hart abgelehnt (S5 in `SPAETER.md`), statt still falsch zu rechnen.
- **MEDIUM/LOW:** EURGBP-Swaps waren GBP-„Punkte", als USD gelabelt → auf USD umgerechnet
  (approx, notiert); `FeeSchedule`-Docstring-Einheiten präzisiert.

**Entscheidungen, die ich selbst getroffen habe:** Das Kostenmodell liest die Gebühren aus
der bestehenden Katalog-`FeeSchedule` statt einer eigenen Datei (Regel 9, keine Dublette);
`contract_size`/`pip_size` kommen aus dem `Instrument`. `hurdle_rate` als reine Funktion, in
jedem Backtest-Bericht auszuweisen.

**Auffälligkeiten, gemeldet, nicht angefasst:** S5 (Aktien-CFD-Kostenmodell) in `SPAETER.md`;
die Stress-Spreads/Slippage sind nirgends broker-veröffentlicht (nur estimate) und am eigenen
Konto nachzumessen (Paket 2). Der Halal-Konflikt (S4) bleibt Philipps Entscheidung + Fatwa.

**Zeilenstand (gemessen):** `costs/model.py`, `tests/test_cost_model.py`,
`RECHERCHE_KOSTEN.md` neu; Katalog auf IC-Markets-Werte. Paket-Quellcode `mt5_trading_ai/`
= 4.386 Zeilen, 19 Module, 219 Testfunktionen; 273 Testfälle grün.

---

## ERLEDIGT — Paket 2 (Teil 3): Das Datenfundament

**Was geschehen ist:** **Recherche R2** (`RECHERCHE_DATEN.md`): sieben Rechercheure zu
Datenquellen (gratis/günstig/premium), Broker-vs-Referenz-Methode, Bias, Zeitzonen/DST.
**Tor E4 → Dukascopy** (kostenlos, institutionell, keyless). `mt5_trading_ai/data/loader.py`
(rein, getestet): Dukascopy-Candle-Dekodierung, Yahoo-Parsing, Session-Normalisierung,
Kettung ans Qualitätstor (fail-closed), reproduzierbare CSV-Ablage + Prüfsummen.
`tools/fetch_data.py` macht den Netzabruf (Retry/Backoff) + die Gegenprobe.

**Das Abbruchkriterium (4.4) greift NICHT** — eine saubere Quelle ist beschaffbar.

**Abnahme (Befehle und Ausgaben):**
```
$ python -m pytest -q
290 passed
$ python -m ruff check .            -> All checks passed!
$ python -m mypy --strict mt5_trading_ai tools
Success: no issues found in 33 source files
$ python tools/gen_docs.py --check  -> ok, MODULES.md aktuell (242 Zeilen)
$ python tools/check_docs_claims.py -> ok - 10/12
$ python tools/check_doc_numbers.py -> ok - 20 Module, 236 Testfunktionen, 4691 Zeilen

$ python tools/fetch_data.py --instrument EURUSD --from-year 2022 --to-year 2024 --out DIR
Dukascopy EURUSD 2022-2024: 365 + 365 + 366 = 1096 Kalendertag-Bars
-> Mo-Fr gefiltert: 782 Bars (2022-01-03 .. 2024-12-31)
Qualitaetstor: BESTANDEN | globale Luecke 0.000 % | 0 Ausreisser | 0 OHLC-ungueltig
Bars-Pruefsumme:     78683f92b090b99c9204ebbb0e700efd0abeebd87cf03b63e2089f7ae2cc8602
Manifest-Pruefsumme: 0b3b8b5c2a433298e7d62aaacf58fac5f7caff3ff90671456ae08bf20c238a1c
Gegenprobe (Dukascopy vs Yahoo, 766/782 nach Filter): Median 28,2 | Mittel 37,0 | max 209,5 bps
```

**Negativ gefahren:** (a) 20 Bars aus der echten Reihe entfernt → Tor **rot**
(`gap_ratio_above_limit`) → zurück → grün. (b) Unit: ein Block von 4 fehlenden Tagen bei nur
0,8 % Gesamtlücke → **rot** durch den neuen Block-Ausfall-Check.

**Adversariale Review (§9, vor der Abnahme):** 15 Agenten (Angreifer/Betreiber/Datenprüfer)
+ Gegenkontrolle. Erhoben 12, **bestätigt 11, verworfen 1** — mehrere reale HIGH-Defekte,
alle behoben.

**Eigene Fehler (von der Review gefunden, alle eingearbeitet):**
- **HIGH:** Preis-Divisor fix auf 100000 + signed struct → jedes Nicht-EURUSD-Paar (JPY)
  still 100x falsch skaliert / hohe Kurse laufen über, alles skaleninvariant durchs Tor →
  Instrument→Divisor-Tabelle (fail-closed bei unbekannt), **unsigned** struct.
- **HIGH:** Lückentor misst **global statt pro Monat** (Docstring-Zusage falsch) →
  zusammenhängende Block-Ausfälle bleiben unter 1 % → **Block-Ausfall-Check** (max.
  zusammenhängende Lücke) im Lader; Qualitätstor-Docstring ehrlich gemacht.
- **HIGH:** Fenster aus min/max der Daten → abgeschnittene Randjahre unsichtbar → **Jahres-
  Abdeckungsprüfung** (< 300 Kalendertag-Bars/Jahr → Fehler).
- **HIGH:** „0 % Lücke" ist teils Vendor-Padding-Artefakt (Dukascopy füllt jeden
  Kalendertag) → in `RECHERCHE_DATEN.md` ehrlich eingeordnet, nicht als Vollständigkeitsbeleg.
- **MEDIUM:** Prüfsumme band nur die Zahlen → **Manifest-Prüfsumme** (Instrument, Divisor,
  Quelle, Session, Urteil) — eine fehl-dekodierte Reihe fällt jetzt auf.
- **MEDIUM:** Gegenprobe verglich ungefiltertes Yahoo → Yahoo vorher auf OHLC-Gültigkeit
  gefiltert (16 verworfen), **Median** (28,2) zusätzlich zum ausreißer-anfälligen Mittel.
- **§5-Korrektur:** die 37 bps nicht mehr zirkulär dem Cutoff zugeschrieben (§5 an §3
  angeglichen, kein Split ohne Messung behauptet).

**Entscheidungen, die ich selbst getroffen habe:** Dukascopy-Tageskerzen (nicht Ticks) für
den ersten Tagesbar-Test — Tick-Aggregation über 2 Jahre wären ~12k Dateien, Overkill. Yahoo
nur als **Gegenprobe** (zu schmutzig fürs Fundament: DST-Zeitstempel, ~2,4 % OHLC-ungültig).
Marktdaten bleiben **lokal** (nicht im Repo — Lizenz nur privat/Backtest); nur Code, Prüfsumme
und Bericht sind öffentlich.

**Auffälligkeiten, gemeldet, nicht angefasst:** S6 in `SPAETER.md` — Qualitätstor-/Session-
Härtung (NY-17:00-Anker, Handelstagskalender, absolute Preis-Bänder, Ausreißer als Fail),
Intraday-Vorarbeit. Der Halal-Konflikt (S4) bleibt offen.

**Zeilenstand (gemessen):** `data/loader.py`, `tools/fetch_data.py`,
`tests/test_data_loader.py`, `RECHERCHE_DATEN.md` neu. Paket-Quellcode `mt5_trading_ai/`
= 4.691 Zeilen, 20 Module, 236 Testfunktionen; 290 Testfälle grün.

---

## ERLEDIGT — Paket 3 (Teil 3): Die Backtest-Maschine

**Was geschehen ist:** `mt5_trading_ai/backtest/engine.py` führt die drei fertigen Teile
zusammen (Splits + Dukascopy-Daten + Kostenmodell). `MarketView` mit harter Zukunfts-Grenze
(Leckage-Schutz), Entscheidung bei Bar `i` / Ausführung `i+1` (shift(1)), jede Order durchs
Kostenmodell, `run_backtest`/`run_walk_forward`/`run_registered_backtest`, Deflated-Sharpe-
Anbindung an `gates/criteria.py`, voller Bericht (Trades, Brutto/Netto, Kosten getrennt,
Sharpe annualisiert, MaxDD, Trefferquote, Hürde, Netto über Hürde, Seed/Prüfsumme/Commit).

**Abnahme (§5.2, Befehle und Ausgaben):**
```
$ python -m pytest -q            -> 304 passed
$ python -m ruff check .         -> All checks passed!
$ python -m mypy --strict …      -> no issues in 34 source files
$ (Zufalls-Referenzlauf, echte EURUSD-Bars, 20 Seeds)
  Netto-Mittel -45.7 % (negativ, wie es sein muss); seed 0: 350 Trades, Netto -95.6 %,
  Sharpe -1.01, Huerde 41 %, Kosten getrennt (Fin gezahlt 3041 vs Carry 551 USD)
```
- ✅ **Leckage-Test grün und negativ gefahren:** Zukunfts-Grenze aufgeweicht → Leck-Test rot
  → zurück → grün.
- ✅ **Zufalls-Referenzlauf negativ** um die Kostenhürde (Mittel −45,7 %) — die schärfste
  Gegenprobe. Einzel-Seed-Varianz hoch (±100 %+) durch Hebel 5 auf Trend, ehrlich benannt.
- ✅ **Zwei identische Läufe → bitgleicher Bericht** (`as_dict` deckungsgleich).
- ✅ **Jeder Lauf zählt** (auch abgebrochene) — Versuchszähler **negativ gefahren** (Append
  lahmgelegt → „10 Läufe = 10"-Test rot → zurück).
- ✅ **Walk-Forward** über `splits.py` mit **pflichtigem** Purge/Embargo.

**Adversariale Review (§9, 15 Agenten, 4 Blickwinkel): erhoben 11, bestätigt 10, verworfen 1**
— mehrere reale HIGH-Defekte, alle behoben.

**Eigene Fehler (von der Review gefunden, alle eingearbeitet):**
- **HIGH:** Look-ahead trotz `MarketView` — `view._bars` war Live-Referenz auf die volle,
  mutable Liste → Strategie konnte die Zukunft **lesen oder überschreiben** (Fake-Profit) →
  `MarketView` hält jetzt nur die unveränderliche Vergangenheits-Kopie.
- **HIGH:** Triple-Swap Off-by-one (Ankunfts- statt Startbar gezählt) → `range(start, end+1)`;
  kontrollierter Di→Mi-/Mi→Do-Test ergänzt.
- **HIGH:** Kostenfreier Modus über ungeprüfte `MarketSpec` möglich → `__post_init__` lehnt
  Spread=Slippage=Kommission=0 ab.
- **HIGH:** Positiver Carry als „negative Kosten" verrechnet (net > gross, Hürde negativ) →
  Carry als eigener Ertrag (`carry_income`), Hürde aus Reibung (≥0), `net_over_hurdle` = gross
  − hürde.
- **HIGH:** `equity_base==0` (Preis/Hebel 0) → unkontrollierter `ZeroDivisionError` →
  fail-closed `ValueError`.
- **HIGH:** Deflated-Sharpe/Trial-Count-Anbindung fehlte (toter Gate) →
  `deflated_sharpe_for_report` bindet Bericht + echte Versuchszahl an `criteria.py`.
- **MEDIUM:** „Jeder Lauf zählt" nur für LookAhead/Value → breites `except` (alle Fehler);
  Walk-Forward-Purge ohne Trainingsschritt ehrlich als Grenze benannt (**S7**).

**Entscheidungen, die ich selbst getroffen habe:** Kosten-Spread aus einer dokumentierten
`spread_pips`-Annahme (Bars haben kein Bid/Ask); per-Bar-Equity-Kurve für Sharpe/Drawdown;
Walk-Forward mit `strategy_factory` (frischer Zufallsgenerator je Fenster).

**Auffälligkeiten, gemeldet, nicht angefasst:** **S7** in `SPAETER.md` — Trainings-/Fit-
Schritt je Fenster (damit Purge/Embargo greifen) + volle `evaluate_criteria`-Auswertung, beides
Paket-4-Vorarbeit. Halal (S4) bleibt offen.

**Zeilenstand (gemessen):** `backtest/engine.py`, `tests/test_backtest_engine.py` neu.
Paket-Quellcode `mt5_trading_ai/` = 5.181 Zeilen, 21 Module, 250 Testfunktionen; 304
Testfälle grün.

## ERLEDIGT — Paket 4 (Teil 3): Der Edge-Test — die eine Frage, beantwortet

**Die Frage:** Existiert auf EURUSD ein Edge nach realistischen Kosten? **Die Antwort ist
Nein — und ein sauberes Nein ist der auftragsgemäße Ausgang, kein Scheitern.** 74–89 % der
Retail-Konten verlieren (ESMA), unter 1 % sind nach Kosten dauerhaft profitabel. Das negative
Ergebnis ist das statistisch erwartete; es hier **belegt** zu haben ist der Wert des Pakets.

**Was gebaut wurde:**
- `backtest/edge.py` — das **Sechs-Bedingungen-Tor** (§7.2), vorab gesetzt und unveränderlich:
  OoS-Sharpe ≥ 1,0 · Deflated Sharpe > 0,95 · ≥ 2.000 Trades · ≥ 3 positive WF-Fenster am
  Stück · `net_over_hurdle > 0` · Leckage grün + Zufalls-Referenz negativ. **Alle sechs**
  müssen erfüllt sein; ein einziges Nein genügt zum Gesamt-Nein.
- `backtest/strategies.py` — MA-Kreuzung (24/120 H1 = 1 Tag vs. 1 Woche), **nicht optimiert**,
  bewusst die einfachste ernsthafte Signallogik.
- `tools/edge_test.py` — der Runner; Walk-Forward **nur auf In-Sample**, OoS-Block genau einmal
  angefasst, jeder Lauf ins Versuchsregister.
- `BERICHT_TEIL3.md` — der Abschlussbericht (§13) mit Abnahme-Matrix und offenen Schwächen.

**Das gemessene Ergebnis (H1 2022–2024, 18.715 Bars, Hebel 5, Kosten aus dem Katalog):**
- OoS (letzte 30 %, ab 2024-02-07): **59 Trades, Netto −18,85 %, Trade-Sharpe −0,79,
  Bar-Sharpe −0,68, MaxDD 33,8 %, `net_over_hurdle` −20,4 %**.
- Deflated Sharpe (6 Versuche registriert): **0,026**. WF In-Sample je Fenster:
  [+0,03 · +0,34 · −0,38 · −0,07 · −0,25] → 2 positiv am Stück.
- Zufalls-Referenz (5 Seeds, **gefahren**): Mittel −218 % → negativ. Leckage-Schutz fängt eine
  Zukunfts-Strategie (`LookAheadError`) → grün.
- **Fünf von sechs nicht erfüllt → KEIN EDGE.** Negativ getrieben: die einzige erfüllte
  Bedingung (Leckage/Zufall) habe ich absichtlich gebrochen (Leckage-Strategie ohne Schutz →
  Fake-Profit; Zufall mit Kosten=0 → positiv) und den Rot-Nachweis rückgängig gemacht.

**Eigene Fehler (von der §9-Review vor der Abnahme gefunden, alle eingearbeitet):**
- **HIGH:** OoS überlappte den Walk-Forward — „genau einmal angefasst" war unwahr →
  Walk-Forward läuft jetzt **nur auf `bars[:split]`**, der OoS-Block bleibt bis zum Abschluss
  unberührt.
- **HIGH:** Deflated-Sharpe-Tor wirkungslos, weil nur 1 Versuch registriert war (erwartetes
  Maximum ≈ 0) → jede WF-Fenster-Auswertung geht unter der Basis-`strategy_id` ins Register;
  die Deflation kennt jetzt die wahre Versuchszahl (DSR fiel dadurch 0,26 → **0,026**).
- **HIGH:** Bedingungen 6 (Leckage/Zufall) waren fest auf `True` verdrahtet statt gefahren →
  echter Zufalls-Referenzlauf (5 Seeds, Netto < 0) + echter Leckage-Lauf (`LookAheadError`
  gefangen) ersetzen die Behauptung.
- **MEDIUM:** Bar-Sharpe ist bei seltenem Handel autokorreliert (überschätzt) →
  **Trade-Level-Sharpe** ergänzt (eine Beobachtung je Trade), Bedingung 1 prüft ihn.
- **MEDIUM:** Hürde als „p.a." fehlbeschriftet, obwohl Ganzzeitraum-Reibung → `n_bars`
  umbenannt, Kommentar korrigiert.
- **MEDIUM:** `net_above_hurdle` zählte die Kosten doppelt → Bedingung 5 nutzt
  `net_over_hurdle > 0` (gross − hürde), keine Doppelzählung.
- **LOW (ehrlich benannt, Schwelle NICHT gesenkt):** 2.000-Trades-Schwelle ist für eine
  MA-Kreuzung auf H1 in diesem Zeitraum unerreichbar (59 Trades) — die Schwelle ist
  masterprompt-gesetzt und bleibt; das Instrument/die Frequenz wären zu ändern, nicht das Tor.
- **LOW:** DSR-Versuchszahl kann bei identischen Wiederholungen inflationieren (kein Dedup) —
  als Grenze notiert.

**Entscheidungen, die ich selbst getroffen habe:** MA(24,120) per Konvention statt Optimierung
(Optimierung würde das Tor verwässern); OoS-Anteil 30 %; Trade-Level-Sharpe als ehrlichere
Kennzahl neben der Bar-Sharpe ausgewiesen, nicht ersetzt.

**Auffälligkeiten, gemeldet, nicht angefasst:** Halal (**S4**) bleibt offen — CFDs sind
mehrheitlich haram; ein Halal-Pfad wäre eigener Auftrag. **S1/S2** (Risiko-Module unverdrahtet,
kein Freshness-Latch), **S7** (Fit-Schritt je WF-Fenster) unverändert offen.

**Zeilenstand (gemessen):** `backtest/edge.py`, `backtest/strategies.py`,
`tools/edge_test.py`, `tests/test_edge.py`, `BERICHT_TEIL3.md` neu; `backtest/engine.py`
erweitert (date-basierte Nächte, Trade-Sharpe, Register-Anbindung). Paket-Quellcode
`mt5_trading_ai/` = 5.368 Zeilen, 23 Module, 259 Testfunktionen; 312 Testfälle grün.

## ERLEDIGT — Paket 4b (Teil 3): Zweiter Edge-Versuch — Mittelwertrückkehr (E5 = weiterbauen)

**E5-Entscheid nach dem ersten Nein:** Philipp wählte **weiterbauen mit einer anderen
Hypothese** — den regelkonformen Weg (§7.3 erlaubt keinen Ausbau ohne bestandenen Test, aber E5
lässt einen neuen, ehrlich registrierten Versuch zu). Ausdrücklich **nicht** Paket 5: das bleibt
am bestandenen Edge-Test verriegelt. Bevor ich baute, habe ich den Konflikt „Paket 5 vs.
§7.3/§8" offengelegt und E5 erneut vorgelegt — Antwort: neuer ehrlicher Versuch zuerst.

**Was gebaut wurde:**
- `backtest/strategies.py` → `mean_reversion_zscore(lookback, entry_z, exit_z)`: zustandsbehaftete
  z-Score-Mittelwertrückkehr (Ein bei |z|≥2, Aus bei |z|≤0,5), **nicht** optimiert. Die
  Hysterese hält die Rückkehr über viele Bars — bewusst verschieden von der Trendfolge.
- `backtest/engine.py` → `deflated_sharpe_for_report(count_scope=...)`: additiv; "total" zählt
  das **gesamte** Register (ehrliche Multiple-Testing-Zahl bei mehreren Strategien gegen
  denselben OoS-Block), "strategy" bleibt Paket-4-Default.
- `tools/edge_test.py`: `--strategy {ma_crossover, mean_reversion}`, geteiltes Kampagnen-Register,
  Deflation mit `count_scope="total"`.
- `tests/test_edge.py`: fünf Tests der Mittelwertrückkehr (FLAT vor Historie, LONG/SHORT bei
  Ausschlag, Halten-dann-Aussteigen, Parametervalidierung).

**Gemessen (EURUSD H1, OoS letzte 30 %, Hebel 5, Katalog-Kosten, Register-Kampagne N = 12):**
123 Trades, Netto **+3,22 %**, Trade-Sharpe **+0,185**, Bar-Sharpe +0,167, MaxDD 15,4 %,
`net_over_hurdle` **+2,48 %**, Deflated Sharpe **0,066** (N = 12). WF In-Sample:
[−0,22, +0,07, +0,35, +0,07, −0,03]. **Drei von sechs Bedingungen erfüllt → aber KEIN EDGE**
(Sharpe 0,185 ≪ 1,0; Deflation 0,066 ≪ 0,95; 123 ≪ 2.000 Trades).

**§1.13 (unerwartet gut = Bug-Verdacht) — Multi-Agenten-§9-Review (22 Agenten) + eigene
Gegenproben:**
- **Kein Bug:** Reproduzierbar bitgleich; kein Look-ahead (`MarketView` blockt Zukunftsbar,
  OoS nutzt frische `factory()`-Instanz); Kosten alle angewandt (14,8 % Reibung, $26/Trade),
  Trade 1 von Hand bestätigt (gross 226 − cost 16,49 = net 209,51).
- **Das Positive ist teils Artefakt, nicht Edge:** (a) **Selektionsbias** — +3,22 % ist der
  Bessere aus zwei Hypothesen auf demselben OoS-Block (offengelegt; Deflation N = 12 trägt es);
  (b) **0,74 pp sind riba-Carry** (Short-EUR-Overnight-Swap), kein Alpha — carry-frei bleiben
  +2,48 %; (c) **statistisch null:** MinTRL ≈ 79–97 Jahre bei 0,9 Jahren OoS; (d) Bedingung 4
  (3 positive Fenster) liegt im Zufallsbereich (P ≈ 25 %).
- **Review-Einwand gegengeprüft und verworfen:** Der Prüf-Agent vermutete, die Zahl hänge an der
  optimistischen Füllung zur Signal-Kerze (an einer synthetischen Reihe halbierte sich das
  Brutto). **An den echten Daten hält das nicht** — Füllung eine Kerze später: Brutto
  +17,31 % → +17,94 % (praktisch gleich), erste Kerze nach Einstieg trägt −4 %. Grund: die
  Hysterese, nicht der Snap-back. Begründet verworfen statt blind übernommen (§9.2).

**Entscheidungen, die ich selbst getroffen habe:** z-Score-Mittelwertrückkehr als zweite,
literaturgestützte Hypothese (Intraday-FX kehrt zurück); Parameter 48/2,0/0,5 per Konvention;
Deflation kampagnenweit (N = 12) statt per Strategie (N = 6), weil zwei Hypothesen gegen
denselben OoS-Block selektiert wurden; Füllzeitpunkt-Sensitivität selbst gemessen statt den
Review-Befund zu übernehmen.

**Eigene Fehler (§9-Review, benannt):** OoS-Block zweimal angefasst (Selektionsbias, offengelegt
statt kaschiert); `deflated_sharpe_for_report` deflationiert die Bar- statt der Trade-Sharpe
(hier folgenlos, beide 0,066 — als **S8** notiert).

**Auffälligkeiten, gemeldet, nicht angefasst:** Halal (**S4**) — der +0,74-pp-Carry ist riba und
auf einem swapfreien Konto nicht vorhanden; das unterstreicht S4. **S8** neu. S1/S2/S7 offen.

**Zeilenstand (gemessen):** `strategies.py`/`engine.py`/`edge_test.py`/`test_edge.py` erweitert.
Ergebnis der Kampagne: **KEIN EDGE** auf EURUSD nach zwei ehrlichen Versuchen. E5 erneut an
Philipp (§10 des Berichts).

## ERLEDIGT — Paket 4c (Teil 3): Dritter Edge-Versuch — Volatilitäts-Ausbruch, FRISCHES OoS

**E5-Entscheid nach dem zweiten Nein:** wieder **weiterbauen** — aber diesmal mit einem
**frisch abgetrennten** OoS-Block, weil der bisherige (letzte 30 % von 2022–2024) durch zwei
Strategien belastet ist (Selektionsbias). Dazu echte EURUSD-H1-Daten **2025-01 bis 2026-07**
neu von Dukascopy geladen (9.850 Handels-Stundenbars, Prüfsumme `08a6e4c9…`) — unberührtes
Out-of-Sample, das keine der ersten zwei Strategien je gesehen hat.

**Was gebaut wurde:**
- `strategies.py` → `volatility_breakout(lookback)`: Donchian-Kanal-Ausbruch (LONG bei neuem
  Hoch, SHORT bei neuem Tief, sonst halten), zustandsbehaftet, **nicht** optimiert. Dritte,
  von Trend-MA und Reversion verschiedene Hypothese.
- `edge_test.py` → `--strategy breakout` + `--oos-csv` (frischer Held-out-Block aus eigener
  Datei; In-Sample = ganzes `--csv`, OoS = neue Periode, einmal angefasst).
- `tests/test_edge.py` → fünf Breakout-Tests (FLAT vor Historie, LONG/SHORT bei Ausbruch,
  Halten zwischen Ausbrüchen, Parametervalidierung).

**Gemessen (Walk-Forward In-Sample 2022–2024, Abschlusstest frisches OoS 2025–26, N=18):**
101 Trades, Netto **−56,42 %**, Trade-Sharpe **−1,005**, Bar-Sharpe −0,882, MaxDD 65,1 %,
`net_over_hurdle` −59,1 %, Deflated Sharpe **0,0015**. Walk-Forward-Fenster **alle fünf negativ**
→ 0 positiv am Stück. **Fünf von sechs nicht erfüllt → KEIN EDGE** (der klarste der drei).

**§9 proportional (Verlust = kein Fake-Edge-Risiko; Motor in 4b von 22 Agenten geprüft):**
- **Verlust ist echt, kein Artefakt:** Brutto schon −35,9 % (vor Kosten), Netto −56,4 %.
- **Reproduzierbar bitgleich;** Trade von Hand: net −1.064,48 = gross −1.030,00 − Kosten 34,48.
- **Frische Daten strukturell sauber:** 0 Duplikate, 0 nicht-monotone, 0 ungültige OHLC. Das
  Qualitätstor meldet formal `passed=False` nur wegen `expected_bar_count_unknown` (fehlender
  Session-/Feiertagskalender, **S6**) — kein Integritätsdefekt, ehrlich benannt.
- **Kohärenter Quer-Check:** Breakout (Trendfortsetzung) verliert hart, Mittelwertrückkehr
  (Fade) war knapp positiv — beide zeigen dieselbe Richtung (EURUSD H1 kehrt zurück, bricht
  nicht aus). Die drei Versuche ergeben ein widerspruchsfreies Bild.

**Entscheidungen, die ich selbst getroffen habe:** Donchian-Ausbruch als dritte, distinkte
Hypothese; frisches OoS aus echten 2025–26-Daten statt den belasteten Block wiederzuverwenden
(heilt den Selektionsbias); proportionale §9 statt vollem Agentenschwarm, weil ein Verlust
keinen Edge vortäuschen kann und der Motor bereits erschöpfend geprüft war.

**Eigene Fehler / Grenzen:** das Qualitätstor kann den frischen Block ohne Session-Kalender
nicht formal zertifizieren (**S6**) — benannt, nicht übergangen. Mit N=18 sinkt auch der
Mittelwertrückkehr-DSR von 0,066 (N=12) auf 0,045 — jede weitere Hypothese verschärft die
Schwelle rückwirkend; im Bericht offengelegt.

**Auffälligkeiten, gemeldet, nicht angefasst:** Halal (**S4**), Session-Härtung (**S6**),
Deflation auf Trade-Sharpe (**S8**) offen. S1/S2/S7 unverändert.

**Ergebnis der Kampagne: KEIN EDGE auf EURUSD nach DREI ehrlichen Versuchen** (Trend −18,85 %,
Ausbruch −56,4 %, Reversion +2,48 % aber statistisch null). E5 erneut an Philipp (§10).

## ABGESCHLOSSEN — TEIL 3 (Edge-Nachweis): Tor E5 = beenden

Nach **drei** ehrlichen, vorab registrierten Versuchen (Trendfolge −18,85 %, Mittelwertrückkehr
+3,22 % aber statistisch null, Volatilitäts-Ausbruch −56,4 % auf frischem OoS 2025–26) hat
Philipp am Entscheidungstor **E5** entschieden: **Auftrag beenden.** Die eine Frage —
„Existiert auf EURUSD ein Edge nach realistischen Kosten?" — ist mit einem sauber belegten,
dreifach gegengeprüften **Nein** beantwortet. Das ist der auftragsgemäße Ausgang, kein
Scheitern.

Weitere Hypothesen zu testen wäre Data-Mining (die Deflation bestraft es bereits: N=18,
Reversion-DSR auf 0,045 gefallen). Paket 5 (Ausbau/LLM/Demo) entfällt — es läuft nur bei
bestandenem Edge-Test. Der geprüfte Sicherheits-, Kosten-, Daten- und Backtest-Apparat bleibt
für einen künftigen echten Edge bereit. Kohärenter Kern-Befund: **EURUSD H1 kehrt eher zum
Mittel zurück, als dass es trendet oder ausbricht — aber der Effekt schlägt die Kosten nicht.**
Größter offener Block bleibt **S4 (Halal):** der riba-Carry hat konkret gezeigt, dass gehebelte
CFDs mit Overnight-Swaps ohne swapfreien Pfad fraglich sind.

## ERLEDIGT — Paket 5 (Teil 3): Auf ausdrückliche Anweisung gebaut, unter Vorbehalt

**Ausgangslage ehrlich:** Der Edge-Test ist nach drei Versuchen **nicht** bestanden (§2 des
Berichts). Bei E5 hatte Philipp „beenden" gewählt; danach hat er sich **ausdrücklich
umentschieden** und Paket 5 angewiesen („Doch Paket 5"). Das ist ein bewusstes **Übersteuern**
des harten Tors §7.3/§8 (Paket 5 nur bei bestandenem Edge-Test) — hier klar als seine Anweisung
gekennzeichnet, nicht als meine Ableitung. **Harte Sicherheitsregeln unberührt:** kein Echtgeld,
`allow_write` auf dem Live-Pfad geschlossen, ESMA-Hebel (konservativ 5:1), kein LLM im
Entscheidungspfad ohne Beleg, Halal benannt.

**Was gebaut wurde (die §8-Infrastruktur):**
- `backtest/llm_compare.py` (§8.2–8.4): fail-closed **LLM-Entscheidungspfad-Tor**. Lässt ein LLM
  nur zu, wenn die LLM-Variante die Nicht-LLM-Variante gegen dieselben sechs Bedingungen
  **schlägt**, nur auf Daten **nach** dem Trainingsstichtag (Leckage), mit Modellversion (Drift).
  Ruft **kein** LLM, trifft keine Entscheidung — nur das Tor davor (Kernregel 17). 5 Tests.
- `venue/demo_run.py` (§8.5): fail-closed **Demo-Betrieb-Tor**. Registriert nur eine Strategie
  mit **bestandenem** Edge-Test; Live-Frage erst nach ≥ 6 Monaten Demo und weiter bestandenen
  Bedingungen. 6 Tests.
- `tools/multi_instrument_edge.py` (§8.1): **Multi-Instrument-Harness**. Prüft die beste
  Strategie (Mittelwertrückkehr) einzeln je Instrument gegen dasselbe Tor, Hebel 5:1. Register
  geteilt, Deflation kampagnenweit. **Gefahren auf EURUSD + GBPUSD (GBPUSD neu geladen, 18.187
  Bars, Prüfsumme `c7d55735`, Vendor-Lücke Dez 2022): 0 von 2 mit Edge** (EURUSD +3,22 %,
  GBPUSD +7,18 % — beide knapp positiv, aber Sharpe/Deflation/Trade-Zahl verfehlt) → kein Ausbau.

**Negativ gefahren / nachgewiesen, dass die Tore greifen:** gegen das echte Mittelwertrückkehr-
Urteil (bester der drei, `passed=False`) **verweigert das Demo-Tor die Registrierung**
(fail-closed, „Strategie hat den Edge-Test nicht bestanden"); das LLM-Tor lässt ohne bestandene
LLM-Variante nichts durch. Die Infrastruktur lässt also — ihrer eigenen Integrität folgend —
**kein aktuelles Vorhaben durch**, weil kein Edge existiert.

**Entscheidungen, die ich selbst getroffen habe:** die §8-Infrastruktur als fail-closed Tore
gebaut, die ihre Vorbedingung (bestandener Edge-Test) selbst erzwingen — so ist Paket 5 gebaut,
ohne das „kein Edge"-Urteil zu untergraben; GBPUSD als zweites Instrument neu geladen; Hebel
durchgängig konservativ 5:1 (unter jeder ESMA-Klassengrenze).

**Auffälligkeiten:** Paket 5 ist gebaut, aber **leer** — es wartet auf eine Strategie, die das
Sechs-Bedingungen-Tor zuerst besteht. Halal (S4), S6, S8 unverändert offen.

## ERLEDIGT — Halal-Pfad (S4): das mechanisch Erzwingbare, die fiqh-Grenze benannt

**Auf Nutzeranweisung** den größten offenen Block (S4) gebaut. Der konkrete Konflikt war im
zweiten Edge-Versuch sichtbar geworden: +0,74 pp des Netto waren reiner Overnight-Swap-Carry —
Zins (riba). Der Swap ist an beiden Enden Zins: gezahlt (negativer Swap) und, bei positivem
Swap, als Gutschrift **erhalten**.

**Was gebaut wurde:**
- `costs/halal.py` → `HalalFinancingPolicy` + `halal_financing`: swapfreie Finanzierung **ohne
  Zins** (weder gezahlt noch erhalten), stattdessen pauschale Verwaltungsgebühr je Nacht
  (Dienstleistung, nicht zinsbasiert), kein Dreifach-Tag. **Invariante per Test: Finanzierung
  nie negativ → nie Gutschrift → nie riba-Ertrag.**
- `costs/model.py` → `order_roundturn_cost(financing_policy=...)`: additiv; gesetzt = swapfrei,
  sonst konventioneller Swap (Altpfad unverändert, alle bestehenden Tests grün).
- `backtest/engine.py` → `MarketSpec.financing_policy` durchgereicht; `edge_test.py --halal`.
- `venue/halal.py` → `screen_halal` / `HalalVerdict`: prüft fail-closed nur das **mechanisch**
  Prüfbare (swapfreies Konto, zinsfreie Margin, Instrument nicht verboten), zertifiziert nie
  „halal"; `requires_scholar_review` ist **immer** wahr (die fiqh-Grundfrage entscheidet der
  Code nicht — Kernregel 16). 12 Tests, negativ gefahren.

**Gemessen (Mittelwertrückkehr EURUSD OoS, konventionell vs. swapfrei):** Carry-Gutschrift
(riba) **160,06 → 0,00 USD** — die riba ist eliminiert. Netto 3,22 % → 3,15 % (kaum Änderung,
weil die Gebühr-Schätzung 5 USD/Lot/Nacht zufällig nahe an der konventionellen Netto-Finanzierung
820,50 liegt); die exakte Zahl hängt an der Schätzung, das qualitative Ergebnis nicht:
**auch auf dem Halal-Pfad KEIN EDGE** (dieselben drei Bedingungen verfehlt).

**§9 proportional (Cost-Model-nah, aber contained):** riba nachweislich weg (Gutschrift 0,
Invariante getestet); **kein Fake-Edge** — Netto sinkt (3,22 → 3,15), Urteil unverändert;
fail-closed (negative Gebühr/Karenz/Nächte abgelehnt); Altpfad intakt (343 Tests grün).

**Entscheidungen, die ich selbst getroffen habe:** die swapfreie Politik als fixe
Dienstleistungsgebühr modelliert (kein Zins); den Screen so gebaut, dass er **nie** „halal"
zertifiziert, sondern die fiqh-Grundfrage bei jedem Aufruf zur Gelehrten-Prüfung markiert;
Gebühr 5 USD/Lot/Nacht als dokumentierte Schätzung (Broker-Bestätigung nötig).

**Ehrliche Grenze / offen:** erledigt ist die **mechanische** Riba-Vermeidung. **Offen bleibt
die fiqh-Grundentscheidung** (sind gehebelte CFDs für Philipp überhaupt zulässig — gharar) —
keine Codefrage, braucht Gelehrten + Philipp. S6, S8 unverändert offen.

## ERLEDIGT — Abnahme-Paket 1 (Datenfundament fail-closed schliessen + Kalender-Härtung)

Erstes Paket des `ABNAHME_PLAN.md`. Kernbefund der Bewertung war: das Qualitätstor lief **nicht**
am Backtest-Rand (Treiber luden per `from_csv` direkt in den Lauf), die berichtete `data_checksum`
war nicht an die echten Bars gebunden, und der Session-Filter (`WeekdaySession`) war für Intraday
falsch (verwarf Sonntagsbars, zählte Feiertage als erwartet).

**Was gebaut wurde:**
- **S6-Kalender** (`data/loader.py`): `FxSession` bildet die FX-Woche **an New York 17:00
  verankert** ab (DST-korrekt: So-Öffnung 22:00 UTC im Winter = 21:00 UTC im Sommer = 17:00 NY);
  `DEFAULT_FX_HOLIDAYS` (Neujahr/Weihnachten) senken die **erwartete** Bar-Zahl in
  `expected_bar_count`/`_max_consecutive_gap`, ohne dünne echte Feiertagsbars als Fehler zu
  flaggen. Wirkung gemessen: EURUSD-H1 gap_ratio **0,70 % → 0,000 %** (Phantom-DST-Lücken weg),
  besteht das Tor; GBPUSD (echte Dez-2022-Monatslücke) wird zu Recht abgewiesen.
- **Verifizierter Loader** `load_verified_csv` (der erzwungene Tor-Punkt): zwei Sicherungen —
  (1) **Herkunft** gegen ein Manifest ODER eine Erwartungs-Pruefsumme (≥ 16 Hex); fehlen beide
  → **fail-closed** (`require_provenance`); (2) das strukturelle Qualitätstor. Read-Fehler in
  `DataLoadError` gekapselt.
- **Engine-Provenienz** (`backtest/engine.py`): `run_backtest` leitet `bars_checksum` aus den
  **tatsächlich gefahrenen** Bars ab und speichert es (statt dem Aufrufer-Wert);
  `DataProvenanceError` bei Erwartungs-Mismatch; `run_walk_forward` prüft das ganze Fenster einmal
  und gibt `""` an die Fold-Sub-Slices.
- **Treiber verdrahtet**: `edge_test`/`multi_instrument_edge` nutzen `load_verified_csv(FxSession)`;
  Manifeste für die H1-Datensätze zur Fetch-Zeit erzeugt → Provenienz trägt ohne CLI-Zwang. Der
  Edge-Test liefert unverändert +3,22 % (Tor transparent für gute Daten).

**§9-Review (25 Agenten, vier Blickwinkel) fand vor der Abnahme drei bestätigte Blocker — alle
behoben:**
- **HOCH:** Provenienz war per Default **fail-OPEN** (ohne Manifest und ohne `expected_checksum`
  lief ein OHLC-gültiger Inhalts-Edit klaglos durch) → `require_provenance` (fail-closed, wenn
  keine Herkunft belegbar) + Manifeste ausgeliefert.
- **HOCH:** Docstrings **überversprachen** unbedingtes fail-closed → ehrlich umformuliert (Herkunft
  nur via Manifest/Checksum; das Qualitätstor sieht keine inhaltliche Fälschung in gültigen
  OHLC-Grenzen).
- **MITTEL/Blocker:** `startswith`-Präfix ohne Mindestlänge (`expected="c"` kollidiert) → **≥ 16
  Hex** erzwungen (Loader + Engine), kürzere Erwartungen fail-closed.
- **Nicht-Blocker behoben:** DST-Phantom-Lücken (NY-Anker, s.o.); Read-Fehler gekapselt.

**Negativ gefahren / nachgewiesen:** neue Tests belegen — eine CSV ohne Herkunft fällt fail-closed
(`test_load_verified_csv_requires_provenance`); ein OHLC-gültiger Inhalts-Edit fällt gegen die
gepinnte Pruefsumme (`..._catches_content_edit_against_pinned_checksum`); zu kurze Pruefsumme wird
abgewiesen; `report.data_checksum == bars_checksum(bars)`; ein falscher `--data-checksum` bricht den
Edge-Test fail-closed ab.

**Entscheidungen, die ich selbst getroffen habe:** die FX-Woche an NY 17:00 statt an feste
UTC-Stunden zu ankern (der Review-Vorschlag; DST-korrekt statt Phantom-Lücken); Herkunft via
**Manifest ODER Checksum** (fail-closed ohne beides) statt --data-checksum zur Pflicht zu machen;
Feiertage als Erwartungs-Reduktion statt als Session-Ausschluss (dünne echte Feiertagsbars sind
kein Fehler).

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich):** Der Gate steckt in `load_verified_csv`
am **Treiber**-Rand, nicht in der Engine-API — `run_backtest` nimmt weiter beliebige Bars; ein
künftiger Treiber, der `from_csv`→`run_backtest` ruft, umginge das Tor (MITTEL; der ABNAHME_PLAN
bot Treiber-Gating als zulässige Option an). Nachhaltiger Fix (VerifiedBars-Typ als einziger
Engine-Eingang) gehört in die Integration (Paket 7). Restliche S6-Punkte (Preis-Plausibilität,
Ausreißer als harte Fail-Gründe, Overflow) bleiben offen (in `SPAETER.md`).

**Nachtrag (letzter §9-Nebenbefund geschlossen):** die `gap_ratio` zählt jetzt nur Bars auf
**erwarteten** Slots (in Session, nicht Feiertag) statt `len(seen)` — eine Feiertags-/Ausser-
Session-Bar kann eine echte Lücke nicht mehr maskieren (konservativ). Wirkung: EURUSD-H1 ehrlich
**0,016 %** (vorher 0 % maskiert), weiter deutlich unter 1 %. Test
`test_holiday_bar_does_not_mask_a_real_gap`. Damit sind alle bestätigten §9-Befunde geschlossen
außer dem bewusst nach Paket 7 verschobenen Engine-API-Gate.

**Zeilenstand (gemessen):** 5.930 Zeilen, 27 Module, 312 Testfunktionen, 366 Testfälle grün. SPAETER
**S6 (Kalender-Teil)** als erledigt markiert.

---

## ERLEDIGT — Abnahme-Paket 2 (Backtest-Integrität scharf stellen: Leckage, Kriterien, Deflation)

Zweites Paket des `ABNAHME_PLAN.md`. Kernbefund der Bewertung war: der Walk-Forward hatte
**keinen Fit-Schritt** (Purge/Embargo waren dekorativ, weil dieselbe Fixstrategie über alle
Fenster lief), die Deflated Sharpe wurde gegen die **Bar**-Sharpe gerechnet (nicht die Kennzahl,
die das Tor prüft), und die vollere 10-Kriterien-Auswertung (`evaluate_criteria`, inkl.
`cost_stress`) war nicht an einen echten Lauf gebunden.

**Was gebaut wurde:**
- **S7 — echter Fit-Schritt** (`run_walk_forward`): nimmt jetzt einen `strategy_fitter:
  Callable[[Sequence[BarRow]], Strategy]`, der die **Trainings-Bars** (expandierendes Fenster,
  `exclude_prior_test=False`) bekommt und die darauf bestimmte Strategie auf `test_idx` testet.
  Damit greift der **Purge** faktisch — gemessen als Schrumpfung des Trainingsfensters.
- **S8 — Deflation auf Trade-Level** (`deflated_sharpe_for_report`): deflationiert
  `report.trade_sharpe_per_obs` (Beobachtungen = Trade-Anzahl) statt der Bar-Sharpe — dieselbe
  Kennzahl, die Bedingung 1 des Tores prüft. Unter 2 Trades keine Deflation (0). Neues Feld
  `trade_sharpe_per_obs` in `BacktestReport`.
- **Volle Kriterien verdrahtet** (`criteria_evidence`, `stressed_spec`): die
  `evaluate_criteria`-Auswertung ist über `criteria_evidence(...)` an den OoS-Lauf gebunden;
  `stressed_spec(spec, mult)` skaliert die Transaktionskosten für das `cost_stress`-Kriterium.
  Beide Treiber (`edge_test`, `multi_instrument_edge`) drucken den Zusatz-Report.
- **Edge-Urteil stabil:** KEIN EDGE, cost_stress bei 1,5× Kosten −2,66 % net_over_hurdle
  (unverändert zur Bewertung; die Verdrahtung bricht nichts).

**§9-Review (vier Blickwinkel: Angreifer/Statistiker/Betreiber/Buchhalter) fand vor der Abnahme
einen bestätigten Blocker — behoben:**
- **MITTEL/Blocker — Embargo-Fassade:** Docstring und der gemeinsame Abnahme-Test behaupteten
  „Purge UND Embargo wirksam". Reproduziert: im strikten Walk-Forward ist das **Embargo ein
  No-op** (die rechte Bandkante hinter dem Testblock trifft keinen Trainings-Bar, weil Training
  nur Vergangenheit ist). Kein Look-Ahead-Leck, aber genau das falsche Grün, das dieses Paket
  eliminieren soll. **Fix:** Docstring/Kommentar ehrlich („Leckfreiheit aus
  Vergangenheits-Konstruktion + Purge, NICHT aus dem Embargo"); der Test aufgeteilt statt
  maskiert — `test_purge_shrinks_the_training_window` (Purge schrumpft) +
  `test_embargo_alone_does_not_change_the_training_window` (Embargo unverändert, als No-op
  belegt).
- **Nicht-Blocker präzisiert (nicht als Fix ausgegeben):** (i) S8 „Bar-Sharpe überzeichnet die
  Deflation" ist datenabhängig, nicht monoton (im Teil-3-Lauf lag Trade-Level-DSR sogar leicht
  über Bar-Level) → Kommentar/SPAETER sagen jetzt „Gewinn ist Konsistenz, nicht garantierte
  Strenge"; (ii) `stressed_spec` stresst keine Finanzierung/Swap → Docstring begründet das (Swap
  ist Zinssatz/Carry, kein Ausführungs-Friction), neuer SPAETER-Eintrag **S9** für ein eigenes
  Finanzierungs-Stressszenario, sobald eine carry-abhängige Strategie in den Test soll.

**Negativ gefahren / nachgewiesen:** `test_purge_shrinks_the_training_window` (Purge schrumpft
das Fenster messbar), `test_embargo_alone_does_not_change_the_training_window` (Embargo lässt es
exakt gleich — der No-op ist belegt, nicht behauptet), `test_walk_forward_fit_uses_training_window`
(der Fitter sieht nur Vergangenheit), Cost-Stress-Tests (`test_stressed_spec_raises_costs`,
`test_cost_stress_criterion_is_evaluable_from_a_run`), Deflation reproduziert (DSR 0,1303 bei 123
Trades / 6 Versuchen).

**Entscheidungen, die ich selbst getroffen habe:** `exclude_prior_test=False` (expandierendes
Trainingsfenster — im Walk-Forward IST jeder frühere Bar ein „prior test"; der Default hätte
alle Trainings-Bars entfernt); das Embargo ehrlich als No-op ausweisen statt einen grünen
Sammeltest stehen zu lassen; den Swap bewusst NICHT mitstressen (kein sinnvoller Uniform-Stress
für einen Zinssatz).

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich):** das Embargo bleibt strukturell
folgenlos, solange der Walk-Forward strikt (nur Vergangenheit) fittet — es gatet erst in
`purged_kfold_embargo_indices` (K-Fold mit Zukunfts-Bars im Training); das ist korrekt so und in
SPAETER **S7** dokumentiert. Der cost_stress skaliert nur Transaktionskosten (SPAETER **S9**).

**Zeilenstand (gemessen, 2026-08-13):** 6.009 Zeilen, 27 Module, 319 Testfunktionen, 373 Testfälle
grün; `ruff` und `mypy --strict` sauber. SPAETER **S7** und **S8** als erledigt markiert, **S9**
neu eröffnet.

---

## ERLEDIGT — Abnahme-Paket 3 (Pre-Trade-Kostentor am Order-Pfad + hurdle_rate bereinigen)

Drittes Paket des `ABNAHME_PLAN.md`. Kernbefund der Bewertung war: kein Live-Trade wurde je
gegen die im Backtest vorausgesetzten Kosten gegengeprüft (das Kostenmodell lief nur im
Backtest, nie am Order-Pfad), und es standen zwei parallele Hürdenformeln im Repo —
`hurdle_rate()` (p. a., ohne Produktions-Aufrufer, mit falscher Docstring-Zusage) neben der
inline im Backtest-Bericht genutzten Gesamtperioden-Formel.

**Was gebaut wurde:**
- **Pre-Trade-Kostentor** (`execution/cost_gate.py`, neu): reine `evaluate_cost_gate(...)`
  rechnet die realen Roundturn-**Transaktionskosten** (Spread + Kommission + Slippage) einer
  eröffnenden Order aus dem echten Bid/Ask + der versionierten `FeeSchedule` und vergleicht sie
  als Anteil des Notionals gegen die im Backtest vorausgesetzte Obergrenze `CostGate`. Spiegelt
  das `leverage_preflight`-Muster (reine Funktion + Venue-Wiring).
- **Verdrahtet in `submit_order`** (`venue/mt5.py`): `_enforce_cost_gate` läuft für eröffnende
  Orders nach der Hebelklammer, vor dem Terminal-Send. **Demo-frei** (kein Echtgeld, wie die
  Live-Freigabe); auf **Live ohne konfiguriertes Tor → fail-closed** (`cost_gate_unconfigured`);
  Kosten nicht bestimmbar (Währungsdifferenz ohne Kurs, verschränkte Notierung) → fail-closed
  (`cost_unverifiable`); Kosten über Schwelle → `cost_gate`.
- **`hurdle_rate()` entfernt** (`costs/model.py`): toter Code, null Produktions-Aufrufer, und der
  Docstring behauptete fälschlich „steht in jedem Backtest-Bericht" (der Bericht nutzt die
  Inline-Gesamtperioden-Formel). Die inline-Formel in `run_backtest` ist jetzt als **einzige**
  Hürdenquelle gekennzeichnet. Doppelte Formel und widersprüchlicher Docstring beseitigt.
- **S5 bestätigt** (bewusste Nicht-Verdrahtung): `config/instrument_catalog.json` enthält kein
  EQUITY; `load_cost_fees` weist EQUITY fail-closed ab (getestet `test_equity_is_rejected`); das
  ad-valorem-Kostenmodell wird erst bei Einzelaktien nötig (SPAETER S5, nicht in diesem Plan).

**§9-Review (vier Blickwinkel, 15 Agenten) fand vor der Abnahme einen bestätigten HOCH-Blocker
— behoben, dann per Fix-Re-Check gegengeprüft:**
- **HOCH / fail-OPEN — Währungs-Einheitenfehler im Kostentor:** `evaluate_cost_gate` teilte
  `friction` (in **Kontowährung**, aus `order_roundturn_cost`) durch `notional` (aus dem rohen
  Preis, in **Notierungswährung**). Bei kreuznotiertem Instrument (z. B. USDJPY auf USD-Konto,
  rate≈1/150) war `fraction = wahr × rate` → das Tor unterschätzte die Kosten um ~150× und ließ
  eine zu teure Order **fälschlich zu** (fail-open) — genau die Schein-Gate-Klasse, die dieses
  Paket eliminieren soll. Verschärfend: ein einzelner `quote_to_account_rate`-Skalar am Konto-
  Venue kann nicht zugleich für USD- und JPY-notierte Paare stimmen, und `order_roundturn_cost`
  wandte einen übergebenen Kurs sogar bei Währungsgleichheit an (verfälschte damit auch USD-Paare).
  Mein eigener Test prüfte nur `approved is True`, nie die **Größe** — so blieb der Bug grün.
  **Fix:** `quote_to_account_rate` aus `CostGate` entfernt; das Tor prüft nur **gleich notierte**
  Instrumente (rate=1, `friction`/`notional` in einer Währung → korrekt), kreuznotierte werden
  **fail-closed** abgewiesen (`cost_unverifiable`, statt mit einem Skalar falsch zu rechnen);
  `order_roundturn_cost` erzwingt bei Währungsgleichheit hart rate=1; der neue
  `test_fraction_matches_hand_calculation` **pinnt die Kostenquote als Zahl** (2,70/11.000). Die
  Kreuzwährungs-Abdeckung (instrumentspezifischer Live-FX-Kurs) ist als **SPAETER S10** vermerkt.
- **Rest-fail-open, vom Fix-Re-Check gefunden — ebenfalls behoben:** Ein zweiter, unabhängiger
  Adversarial-Durchlauf auf den Fix fand einen verbliebenen Pfad: `instrument.quote_currency or
  fees.currency` setzte bei **unbekannter** Notierungswährung (`None`, live real, wenn der Broker
  `currency_profit` leer meldet) still die Kontowährung ein → ein tatsächlich kreuznotiertes
  Instrument wäre als gleich notiert (rate=1) durchgelaufen. Genau die „stille Annahme", gegen die
  das Kostenmodell gebaut ist. **Fix:** `quote_currency is None` → `cost_unverifiable` fail-closed,
  kein Default; Test `test_unknown_quote_currency_is_fail_closed`. Ein abschließender dritter,
  unabhängiger Re-Check (zwei Blickwinkel) verifizierte algebraisch, dass `friction` und `notional`
  jetzt garantiert dieselbe Währung tragen und alle numerischen Sonden (inkl. NaN-Schwelle)
  fail-closed landen — **kein** verbliebenes fail-open/Währungs-Loch (`problem_count: 0`).

**Negativ gefahren / nachgewiesen:** `test_live_opening_rejected_when_cost_exceeds_threshold`
(reale ~24,5 bp gegen 10-bp-Schwelle → `cost_gate`, kein Send), `..._unconfigured` (Live ohne Tor
→ fail-closed), `test_demo_opening_skips_cost_gate` (Demo ohne Tor → angenommen),
`..._allowed_when_cost_within_threshold` (50-bp-Schwelle deckt die realen Kosten → Send). Die
reine `evaluate_cost_gate` deckt die **Größe** der Kostenquote (2,70/11.000 exakt), Kreuzwährung
fail-closed, unbekannte Notierungswährung fail-closed, verschränkte Notierung und negative
Schwelle ab (`tests/test_cost_gate.py`, 7 Fälle); `test_same_currency_ignores_supplied_rate`
sichert das harte rate=1 in `order_roundturn_cost`.

**Entscheidungen, die ich selbst getroffen habe:** das Tor als **Live-Pflicht/Demo-frei** zu
bauen (spiegelt die Live-Freigabe; Demo hat kein Echtgeld-Risiko) statt opt-in (ein opt-in-Tor
wäre still abschaltbar — genau die Schein-Gate-Klasse); nur die **Transaktionskosten** zu prüfen
(Spread/Kommission/Slippage), nicht die haltedauerabhängige Finanzierung, die beim Eröffnen
unbekannt ist; `hurdle_rate` zu **löschen** statt zu verdrahten (die Einheiten p. a. vs.
Gesamtperiode unterscheiden sich — Verdrahtung hätte die Tor-Semantik `net_over_hurdle` verändert,
keine Bereinigung).

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich):** (1) Das Kostentor deckt **nur gleich
notierte** Instrumente ab (EURUSD/GBPUSD/XAUUSD/BTCUSD auf USD-Konto — der gesamte Edge-Test-
Fokus). Kreuznotierte Paare (USDJPY, EURGBP) werden bewusst fail-closed abgewiesen, bis ein
instrumentspezifischer Live-FX-Kurs nachgerüstet ist (SPAETER **S10**). Das ist die sichere
Richtung (nicht handeln statt falsch bepreisen), keine stille Lücke. (2) Zwei vorbestehende
Vertrauensgrenzen, vom Re-Check genannt, **kein** Paket-3-Defekt: `reduce_only`-Orders umgehen
alle Eröffnungs-Tore (Kostentor, Hebel, Live-Freigabe) — bewusster Carve-out für Risikoabbau, aber
ein `reduce_only`-Missbrauch auf einer *eröffnenden* Order läge außerhalb der Tore (SPAETER **S11**);
und das Tor vertraut den Broker-Metadaten (`currency_profit`, Kommission), die es nicht gegen
`load_cost_fees` gegenprüft (Daten-, keine Torlogik-Frage, in **S11** vermerkt).

**Zeilenstand (gemessen, 2026-08-13):** 6.167 Zeilen, 28 Module, 329 Testfunktionen, 383
Testfälle grün; `ruff` und `mypy --strict` sauber. SPAETER **S5** bestätigt, **S10** und **S11**
neu eröffnet.

---

## ERLEDIGT — Abnahme-Paket 4 (Risikoschicht in den Order-Pfad verdrahten — S1)

Viertes Paket des `ABNAHME_PLAN.md` und der große Block. Kernbefund der Bewertung war die
gefährlichste offene Fehlerklasse des Systems: **vier getestete, aber verwaiste Risikomodule**
(`risk/limits.py`, `risk/sizing.py`, `risk/stop_budget.py`, `gates/evaluation.py`) hatten keinen
Aufrufer — dieselbe Klasse wie die alte Hebelklammer (getestet, am Live-Pfad nie aufgerufen).

**Was gebaut wurde:**
- **`RiskManager`** (`execution/risk_manager.py`, neu): führt die vier Module zu **einem** Aufrufer
  am Order-Pfad zusammen und fährt sie in der vorgeschriebenen, nicht verhandelbaren Reihenfolge:
  (1) **`evaluate_limits`** (Kill-Switch: Tagesverlust → Ablehnung, Drawdown → `_halted`-Latch,
  Positionsdeckel, Gap-Sperre); (2) **`select_one`** (Drossel: Cooldown, Mindesthaltedauer,
  Tageskappen, Positionsdeckel); (3) **`stop_budget`** + **`executable_stop_floor`** (Floor >
  Budget → `no_trade`); (4) **`size_position`** (angefordertes Volumen > Budget-Volumen →
  Ablehnung). Der Manager trägt den Zustand, den die Venue nicht hat: Equity-Verlauf (Tagesstart,
  rollierender Fenster-Hoechststand), Handelsfrequenz und offene Positionen mit Eröffnungszeit.
- **Verdrahtet in `submit_order`** (`venue/mt5.py`): `_enforce_risk` läuft für eröffnende Orders
  nach Hebel-Preflight und Kostentor. **Demo-frei / Live-Pflicht** (wie das Kostentor: fehlt der
  Manager auf Live → fail-closed `risk_unconfigured`). Ein Drawdown-Halt setzt `_halted`.
  `_enforce_leverage` gibt jetzt den effektiven Hebel zurück (die Budget-Obergrenze hängt am
  Hebel). Akzeptierte Eröffnungen werden dem Manager gemeldet (`record_open_fill`).
- **Docstrings angeglichen**: die vier Module tragen jetzt einen „Aufrufer (Paket 4)"-Vermerk;
  SPAETER **S1** als erledigt markiert, die bewussten Vereinfachungen in **S12** vermerkt.

**§9-Review (vier Blickwinkel, 11 Agenten) fand sechs bestätigte Befunde — alle behoben, dann per
Fix-Re-Check gegengeprüft:**
- **HOCH / fail-OPEN #1 — klebrige Drawdown-Freigabe:** `_manual_release_id` wurde nie gelöscht →
  eine einzige manuelle Freigabe entwaffnete den Drawdown-Kill-Switch **dauerhaft** für alle
  späteren Episoden (der Kill-Switch, den `limits.py` ausdrücklich als „löst sich nicht von selbst"
  beschreibt, löste sich nach der ersten Freigabe selbst). **Fix:** die Freigabe gilt nur für die
  **aktuelle** Halt-Episode — vor `evaluate_limits` wird sie verworfen, sobald der Drawdown sich
  unter die Grenze erholt (re-arm) **oder** sich über das freigegebene Niveau vertieft (neuer
  Halt); `_release_ceiling` hält das Niveau. Zwei Regressionstests.
- **MITTEL / Schein-Gate #2 — `stop_budget.lower_bps` nie erzwungen:** nur die Obergrenze wurde
  geprüft; `budget.allows()`/die Kosten-Untergrenze war am Order-Pfad toter Code → ein zu enger
  Stop (unter dem Kosten-Floor, rechnerisch unhandelbar) passierte. Genau die zu eliminierende
  Klasse. **Fix:** `effective_stop < budget.lower_bps` → `stop_budget_below_cost_floor` (die
  Obergrenze bleibt präzise bei `size_position`). Test fx_minor 25 bps < Floor 40.
- **#4 (fail-closed) — Frequenz-Tageszähler resetten nur beim Fill:** nach einer ausgeschöpften
  Tageskappe hätte die erste Order des Folgetags stale weitergeblockt. **Fix:** Tages-Rollover in
  einen Helper gezogen und auch auf dem Lesepfad (`authorize_opening`) gerufen.
- **#5 (fail-closed) — `record_close` ohne Order-Pfad-Aufrufer:** der Positionsdeckel hätte
  Lifetime-Eröffnungen statt offener Positionen gezählt. **Fix:** in `submit_order` ruft ein
  glattstellender reduce_only-Fill (`book.net==0`) jetzt `record_close`.
- **#6 (fail-closed, niedrig) — Deckel zählte Fills statt Netto-Symbole:** **Fix:**
  `record_open_fill` dedupt je Symbol (spiegelt `record_close`).
- **Fix-Re-Check-Nachzug zu #5:** Ein Adversarial-Durchlauf auf die Fixe fand, dass die erste
  Fassung von #5 nur im **Nicht-Strom**-Modus trug — mit `PrivateSync` läuft das lokale Buch dem
  asynchronen Ereignisstrom nach, sodass `book.net==0` zum falschen Zeitpunkt prüfte. **Fix:** das
  Glattstellen wird jetzt aus `pre_net + Fill` bestimmt (Buch **vor** der Mutation erfasst),
  stromunabhängig korrekt — mit einem Strom-Modus-Test belegt, der mit der alten Fassung rot wäre.
  Die verbleibende seltene Strom-Latenz-Kante (Open + sofortiger Close innerhalb der Ereignis-
  Latenz) ist fail-**closed** und in SPAETER **S12** vermerkt. #1/#2/#4/#6 wurden vom Re-Check als
  korrekt bestätigt.

**Negativ gefahren / nachgewiesen (Order-Pfad, `tests/test_mt5_venue.py`):** (a) 0,10 Lot (~1 %
Risiko) gegen 0,25 % Budget → `volume_exceeds_risk_budget`, kein Send; (b) `safety=100` drückt das
Budget unter den Tiefe-Floor → `risk_sizing_stop_floor_exceeds_budget`; (c) Fenster-Hoechststand
12k / Equity 10k → Drawdown 16,7 % → `_halted` gesetzt, die nächste Eröffnung fällt am Global-Halt;
(d) zweiter Trade sofort → `throttle_*`, nur der erste ging raus. Plus 18 reine `RiskManager`-
Einheitstests (`tests/test_risk_manager.py`): Budget, Stop-Floor, untradeable-Budget, Drawdown-Halt
+ manuelle Freigabe, Tagesverlust ohne Latch, Cooldown, Positionsdeckel, `record_close` gibt Platz
frei, Gap-Sperre, Tagesgrenzen-Reset, strengere Limits — und die fünf §9-Regressionen
(Freigabe-Re-Arm, Freigabe-Vertiefung, Stop unter Kosten-Floor, Tageskappen-Reset, Symbol-Dedup).

**Entscheidungen, die ich selbst getroffen habe:** die Risikoschicht in die **Venue-Schicht** zu
legen (letzte Verteidigungslinie je Order, per Plan), realisiert als injizierte `RiskManager`-
Komponente (wie das Kostentor) statt als Manager-Schicht über dem Venue — der Venue ist der
erzwingende Punkt, der Manager trägt den Zustand; das Tor **Demo-frei / Live-Pflicht** zu bauen
(ein Live-Sicherheitstor, konsistent mit Live-Freigabe und Kostentor); ein über dem Budget
liegendes Volumen zu **verwerfen** statt still zu verkleinern (ein verkleinerter Trade ist ein
anderer als der bewertete).

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich, SPAETER S12):** die Volatilität steht am
Order-Pfad nicht je Bar bereit → im Stop-Floor mit 0 angesetzt (Broker-Abstand, Tiefe, Spread
binden weiter); der Ranglisten-/Ein-Gewinner-Teil der Drossel wird per Order mit einem
Einzelkandidaten gefahren und wird erst mit einer echten Bewertungsschleife wirksam; der
Positions-Lebenszyklus (`record_open_fill`/`record_close`) ist gegenüber dem Netto-Buch
vereinfacht (kein Teil-Fill-Tracking); der Manager-Zustand ist In-Memory (kein Neustart-Persist).

**Zeilenstand (gemessen, 2026-08-13):** 6.641 Zeilen, 29 Module, 355 Testfunktionen, 409 Testfälle
grün; `ruff`, `mypy --strict`, `gen_docs --check`, `check_doc_numbers` sauber. SPAETER **S1**
erledigt, **S12** neu.

---

## ERLEDIGT — Abnahme-Paket 5 (Compliance-Tore an den Live-/Demo-Pfad: Halal, Demo, LLM)

Fünftes Paket des `ABNAHME_PLAN.md`. Kernbefund: drei getestete, aber **verwaiste** Compliance-
Module (`venue/halal.py`, `venue/demo_run.py`, `backtest/llm_compare.py`) hatten keinen Aufrufer —
sie waren Funktionen, keine wirksamen Tore. Die fiqh-Bewertung selbst bleibt bewusst beim Gelehrten
(Kernregel 16); der Code erzwingt nur das mechanisch Prüfbare und die menschliche Sign-off.

**Was gebaut wurde:**
- **Halal-Screen in `submit_order`** (`venue/mt5.py` `_enforce_halal`): jede eröffnende Live-Order
  (Demo-frei) wird gegen Instrument/Kontokonfiguration gescreent. Zweiteilig, beide fail-closed:
  (1) **mechanische** Konformität (`screen_halal`: swapfreies Konto, zinsfreie Margin, Instrument
  nicht verboten — aus `settings`, Defaults konservativ = nicht konform); (2) weil
  `requires_scholar_review` per Kernregel 16 **immer** wahr ist, kann eine Live-Order nur eröffnen,
  wenn ein Mensch die Gelehrten-Entscheidung als `halal_scholar_review_id` hinterlegt hat — sonst
  `halal_scholar_review_missing`. Der Code entscheidet die fiqh-Grundfrage nie.
- **Demo-Reife-Tor an die Live-Freigabe gebunden** (`venue/mt5.py`
  `_require_live_release_for_opening`): eine Live-Eröffnung verlangt zusätzlich ein injiziertes
  `DemoReadiness` mit `ready_for_live_question` (≥ 180 Tage Demo-Betrieb + weiter bestandener Edge);
  fehlt es oder ist es nicht reif → `demo_not_ready`. Die Naht §8.5→§7: `venue/smoke.py`
  `run_smoke(demo=DemoRunInputs)` füttert `register_for_demo` (fail-closed ohne Edge) und
  `evaluate_demo_progress` mit echten Edge-Verdicts; das Ergebnis speist das Tor.
- **LLM-Tor verankert** (`backtest/llm_compare.py` unverändert fail-closed): der Entscheidungspfad
  ist heute **LLM-frei** (regelbasierte Strategien) — per Regressionstest
  `test_decision_path_is_llm_free` verankert, der die entscheidungstragenden Module auf
  LLM-Bibliotheks-Importe scannt. `evaluate_llm_gate` bleibt die einzige Zulassungsstelle: käme je
  ein Modell in den Pfad, muss es zuvor den belegten Vergleich (schlägt Baseline, keine Leckage,
  Versionsstempel) bestehen.
- **Docstrings angeglichen**: die drei Module tragen jetzt „Aufrufer (Paket 5)"-Vermerke.

**§9-Review (vier Blickwinkel, 13 Agenten) fand einen bestätigten HOCH-Blocker — behoben, dann per
Fix-Re-Check gegengeprüft:**
- **HOCH / fail-OPEN — `reduce_only` umging ALLE Tore + Global-Halt:** das caller-gesetzte
  `reduce_only`-Flag wurde blind vertraut → eine als `reduce_only` markierte **eröffnende** Order
  (ohne Gegenposition) umging sämtliche Compliance-/Risiko-Tore **und** den Not-Aus (per LIMIT sogar
  ohne Stop). Genau die Schein-Gate-Klasse, die dieses Paket eliminieren soll (in Paket 4 als
  S11-„Vertrauensgrenze" vermerkt — der Review zeigte, dass es real fail-open ist). **Fix:**
  `submit_order` überspringt die Eröffnungs-Tore nur noch, wenn die Order eine **tatsächlich offene
  Gegenposition abbaut** (neuer Helper `_reduces_position`: Gegenseiten-Exposure aus lokalem
  Netto-Buch **und** autoritativen Börsen-Positionen — hedging-fähig, deckt Drift vor der Adoption).
  Ein `reduce_only`-Flag ohne (oder gleichgerichtet zu einer) Position fällt in den Eröffnungs-Zweig
  und wird regulär geprüft/abgelehnt (`test_live_reduce_only_without_position_is_gated_as_opening`).
  Legitimer Risikoabbau (echtes Schließen) passiert weiter ohne Freigabe, auch im Halt. SPAETER
  **S11** als erledigt markiert.
- **Drei Fix-Re-Check-Nachzüge auf denselben Vektor (loop-until-dry, jede Runde ein subtilerer
  Buch-Vektor):** (i) volumen-blind → ein Over-Fill flippte netto → **Volumen-Klammer**
  (`volume <= opposite`); (ii) `opposite = max(Buch, Börse)` → ein **stale-hohes Buch** überzeichnete
  die Börse → **börsen-autoritativ, Buch nur bei `not desync`**; (iii) **Stille/Latenz setzt `desync`
  nicht** (ein routinemäßiger SL/TP-Close, dessen Fill-Event nur in-flight ist) → das stale-Buch
  schlüpfte weiter durch. **Endfassung:** der Buch-Zweig ist **ganz entfernt** — maßgeblich ist
  **ausschließlich** die autoritative Börsen-Gegenposition (`get_positions()`, ein frischer
  Broker-Query). Das lokale Buch trägt die Reduce-Autorisierung nie (es kann in beide Richtungen
  veralten). Das schneidet die gesamte „stale-Buch"-Klasse an der Wurzel. Über-Fill/Flip/flat →
  gated; Teilschluss/Hedging/exaktes Glattstellen (`volume == opposite`)/Abbau im Halt bleiben
  reine Reduktion. Tests: `test_reduce_only_over_fill_is_gated_as_opening`,
  `test_live_reduce_only_without_position_is_gated_as_opening`, Drift/Desync/Sync via
  Terminal-Position. Ein abschließender vierter Re-Check bestätigte die Endfassung **frei von
  fail-open und regressionsfrei** (`problem_count: 0`).
- **2 Non-Blocker (LLM-Anker) — gehärtet:** mein `test_decision_path_is_llm_free` scannte nur 8
  Dateien (nicht transitiv) und hatte eine unvollständige Denylist. **Gehärtet:** scannt jetzt das
  **ganze Paket** (`rglob *.py`, transitiv-vollständig für statische Importe), erweiterte
  `_LLM_LIBS`; der Anspruch ist ehrlich auf statische Importe begrenzt (dynamischer `importlib`-Import
  bewusst außerhalb dieses Regressions-Ankers).

**Negativ gefahren / nachgewiesen (Order-Pfad, `tests/test_mt5_venue.py`):** nicht-halal (Krypto)
→ `halal_not_conformant`; nicht-swapfreies Konto → `halal_not_conformant`; fehlende
Gelehrten-Freigabe (auch bei konformem EURUSD) → `halal_scholar_review_missing`; Demo < 180 Tage /
Edge verfehlt → `demo_not_ready`; kein Reife-Ergebnis → `demo_not_ready`; realer
`register_for_demo → evaluate_demo_progress`-Fluss (≥ 180 Tage + Edge) → Live-Eröffnung besteht;
Demo überspringt alle Compliance-Tore. Plus `tests/test_mt5_smoke.py` (Demo-Registrierung reif /
fail-closed ohne Edge), `tests/test_llm_compare.py` (Tor-Bedingungen + LLM-frei-Anker),
`tests/test_demo_run.py`.

**Entscheidungen, die ich selbst getroffen habe:** den Halal-Screen als **Live-Pflicht/Demo-frei**
zu bauen (ein Live-Compliance-Tor; Demo hat kein Echtgeld); die Gelehrten-Freigabe als hinterlegte
`halal_scholar_review_id` zu erzwingen (systemische Kernregel-16-Durchsetzung — ohne menschliche
fiqh-Entscheidung keine Live-Order, ohne dass der Code fiqh entscheidet); das LLM-Tor als
**dokumentierten Frei-Vermerk + Regressionstest** zu verankern (statt eines synthetischen
Durchsetzungspunkts ohne LLM-Infrastruktur), weil der Pfad heute LLM-frei ist.

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich):** Der Halal-Screen liest swapfrei/zinsfrei
aus `settings` (Betreiber-Selbstauskunft), nicht als Broker-bestätigte Kontoeigenschaft — der
`Mt5Account` trägt das Feld nicht. Das ist eine bewusste Grenze: der Code erzwingt, dass die Flags
gesetzt UND die Gelehrten-Freigabe hinterlegt sind, kann die Broker-Realität aber nicht prüfen (wie
schon bei den Live-Freigabe-Schaltern). Der LLM-Anker deckt statische Importe im ganzen Paket ab,
nicht dynamische `importlib`-Importe (bewusst außerhalb des Regressions-Ankers). Und: das
Reduce-Gate summiert das Gegen-Brutto, während `order_send` nur das erste Gegen-Ticket adressiert —
auf Hedging-Konten ein broker-definiertes Überlauf-Verhalten (kein fail-open, senkt immer das Netto;
vorbestehend, SPAETER **S11**); für Netting-Konten (ESMA-Retail-Norm) irrelevant.

**Zeilenstand (gemessen, 2026-08-14):** 6.805 Zeilen, 29 Module, 367 Testfunktionen, 421 Testfälle
grün; `ruff`, `mypy --strict`, `gen_docs --check`, `check_doc_numbers` sauber.

## ERLEDIGT — Abnahme-Paket 6 (Werkzeug-Härtung: erzwungene Provenienz, E2E-Smoke, Verhaltens-Tests)

**Ziel (aus dem Plan):** Die Forschungs-Werkzeuge sind regressionsfest auf ihrem real
gefahrenen Pfad, ein Mini-Fixture beweist die ganze Kette in der CI, und **kein
registrierter Versuch geht mit leerer Herkunft ins Ledger**. Die Deflated Sharpe hängt an
der ehrlichen Versuchszahl — ein beweisfreier Eintrag macht sie unehrlich. Genau das wird
hier fail-closed geschlossen.

**Was gebaut wurde:**

- **Provenienz erzwungen (Kern).** Neues Modul `backtest/provenance.py`: `code_commit_from_git()`
  leitet den Codestand aus `git rev-parse HEAD` ab — fail-closed (`ProvenanceError`), wenn git
  fehlt, kein Repo vorliegt, HEAD unbestimmt ist **oder der Arbeitsbaum schmutzig ist** (siehe
  §9-Blocker unten). Der `Trial` (in `gates/trials.py`) trägt jetzt zwei **Pflicht**-Felder
  `data_checksum` + `code_commit`; `__post_init__` wirft `TrialsLedgerError`, sobald eines
  leer/blank ist — ein Versuch ohne ableitbare Herkunft kommt nicht mehr ins Register. `new_trial()`
  reicht beide durch. `run_registered_backtest` und `run_walk_forward` schreiben die **abgeleitete,
  echte** Fenster-/Bericht-Prüfsumme (`report.data_checksum`, nicht den Erwartungswert-Parameter)
  plus den git-Commit — auch im Fehlerfall (`bars_checksum` der Bars). Die Werkzeuge
  (`edge_test.py`, `multi_instrument_edge.py`) leiten den Commit aus git ab (`args.code_commit or
  code_commit_from_git()`) und reichen ihn überall durch; `learning_phase.propose_parameter_sets`
  verlangt die Herkunft jetzt ebenfalls (man kann eine Optimierung nicht einmal *vorschlagen*, ohne
  die verifizierten Daten und den Code zu benennen).

- **Rückwärtskompatibel gelesen, ohne die Schreib-Pflicht zu weichen.** `iter_trials()` setzt für
  Alt-Zeilen (vor Paket 6) `data_checksum`/`code_commit` beim **Lesen** auf `"legacy"`. Die
  non-empty-Pflicht gilt unverändert beim **Schreiben** (`__post_init__`), sodass kein neuer Eintrag
  ohne Herkunft entsteht.

- **E2E-Smoke auf committeter Mini-Fixture.** `tests/fixtures/smoke_eurusd_d1.csv` (+ Manifest) ist
  eine **synthetische** D1-Reihe (kein Marktdatum, `source: synthetic-smoke-fixture`), 220
  Weekday-Bars, die das Datenqualitätstor besteht. `test_e2e_smoke.py` fährt die ganze Kette als
  **einen** zusammenlaufenden Lauf: `load_verified_csv → run_walk_forward →
  run_registered_backtest → deflated_sharpe_for_report → evaluate_edge`. Geprüft wird die
  **Konvergenz** und dass die Herkunft durch die ganze Kette ins Register fällt — nicht, dass ein
  Edge existiert (auf Rauschen ist das ehrliche Urteil „kein Edge"). Die Prüfsumme ist angeheftet:
  driftet die Fixture, fällt der Smoke laut auf.

- **Register-Disziplin als Verhaltens-Test.** `tests/fixtures/smoke_eurusd_h1.csv` (+ Manifest,
  synthetisch, FxSession-tauglich) trägt `test_edge_test_cli.py`: `edge_test.main()` läuft real,
  danach steht im Register **nur** die Strategie-ID (5 WF-Fenster + 1 OoS = 6 Einträge), die
  Kontroll-Läufe (`rnd`/`leak`/`stress`) stehen **nicht** drin. Ein versehentliches `ledger_path` am
  Kontrolllauf ließe dessen ID auftauchen → der Test wird rot.

- **`multi_instrument_edge` + `demo_run` mit echtem Verdict.** `test_multi_instrument_edge.py` prüft
  `_run_one`/`main` auf der Fixture (echtes `EdgeVerdict`, 6 Register-Einträge, dieselbe Disziplin).
  `test_demo_run_e2e.py` erzeugt ein **real abgeleitetes** Urteil aus `run_backtest → evaluate_edge`
  und füttert es in `register_for_demo`/`evaluate_demo_progress` — ein ehrlich durchgefallenes Urteil
  (synthetisches Rauschen) wird fail-closed abgelehnt, mit den echten offenen Bedingungen als
  Begründung.

**§9-Review (adversarial, 4 Linsen als Hintergrund-Workflow, vor dem Commit) — loop-until-dry über
drei Runden auf denselben Vektor:** Der erste Lauf brachte 6 bestätigte Befunde, verdichtet auf
**einen Blocker** (aus vier Linsen derselbe Defekt) plus zwei Non-Blocker. Der Blocker wurde gefixt,
und **zwei Fix-Re-Checks** (je ein eigener adversarialer Workflow) legten nach — jede Runde ein
subtilerer Umgehungsweg derselben Wache, bis sie hermetisch war.

- **HOCH / fail-OPEN — `code_commit_from_git()` belegte nicht den tatsächlich gefahrenen Code
  (vier Runden, jede fand einen subtileren Umgehungsweg derselben Wache):**
  - *Runde 1 (Blocker):* Die Funktion nahm allein `git rev-parse HEAD`. Lief ein Backtest gegen
    **uncommitteten** Code, trug der Ledger-Eintrag den sauberen HEAD-Hash — non-empty, also am
    `__post_init__`-Tor vorbei, aber eine **Lüge über den gefahrenen Code**. Ein Prüfer, der den
    Commit auscheckt, kann eine Manipulation (z. B. gesenkte Tor-Schwelle) weder reproduzieren noch
    entdecken. *Fix 1:* `git status --porcelain`; nicht leer → `ProvenanceError`.
  - *Runde 2 (Fix-Re-Check fand zwei Umgehungen, beide blockierend):* (A) `status.showUntrackedFiles=no`
    (eine gutartige Performance-Config) versteckt neue untracked `.py` vor `--porcelain`; (B)
    `git update-index --assume-unchanged`/`--skip-worktree` macht `status` blind für eine
    **modifizierte** versionierte Datei. Beide liefern weiter einen sauberen Hash für schmutzigen Code
    — und falsifizierten meine eigene Fix-1-Zusicherung samt Test. *Fix 2:* Helfer
    `_working_tree_is_dirty` mit **zwei** config-unabhängigen Prüfungen —
    `git --no-optional-locks status --porcelain --untracked-files=all` (das feste `--untracked-files=all`
    überschreibt `showUntrackedFiles=no` → schließt A) **und** `git ls-files -v`, wo jede Zeile mit
    Kleinbuchstaben-Tag (`assume-unchanged`→`h`) oder `S` (`skip-worktree`) als schmutzig gilt → schließt
    B. Tags empirisch verifiziert.
  - *Runde 3 (Fix-Re-Check fand die Skopierung):* `git ls-files -v` ist **verzeichnis-skopiert**. Der
    Default-Pfad läuft mit `cwd = .../mt5_trading_ai/backtest/` (Modul-Unterverzeichnis); von dort
    listete der Suppress-Bit-Scan **nur** `backtest/` — ein `assume-unchanged`/`skip-worktree`-Bit auf
    `costs/`, `gates/`, `risk/`, `venue/` … blieb unsichtbar, also Vektor B für fast den ganzen Baum
    wieder offen (end-to-end reproduziert). *Fix 3 (Endfassung):* `code_commit_from_git` löst zuerst das
    Repo-**Toplevel** auf (`git rev-parse --show-toplevel`, fail-closed ohne Repo) und fährt **alle**
    git-Aufrufe von dort — der `ls-files`-Scan ist damit repo-weit statt teilbaum-lokal.
  - `.gitignore` wird durchgehend beachtet, also zählen lokale Daten/`TRIALS.jsonl` **nicht** als
    Schmutz.

**Negativ gefahren (jede Wache bewiesen):**
- **Leere Herkunft** → `test_empty_provenance_is_rejected`: `data_checksum=""` und
  `code_commit="   "` werfen `TrialsLedgerError` bei Konstruktion.
- **Schmutziger Arbeitsbaum, alle Umgehungswege** (`tests/test_provenance.py`, hermetisches tmp-git-Repo,
  vorher **null** Abdeckung): sauber → 40-Hex-Hash; tracked-modifiziert → Fehler; untracked Quelldatei →
  Fehler; **untracked trotz `showUntrackedFiles=no`** → Fehler (R2-Vektor A);
  **`assume-unchanged`/`skip-worktree` modifiziert** → Fehler (R2-Vektor B); **Suppress-Bit auf Datei
  außerhalb des cwd-Teilbaums, Aufruf vom Unterverzeichnis** → Fehler (R3-Skopierung); gitignored →
  **kein** Schmutz; kein Repo → Fehler.
- **Register-Disziplin (edge_test):** temporär einen Kontroll-Lauf (`rnd`) fälschlich registriert →
  `test_only_real_runs_reach_the_ledger` **rot** (7 statt 6 Einträge, fremde ID `rnd`). Zurückgebaut
  → grün.
- **Demo-Naht:** temporär die fail-closed-Prüfung in `register_for_demo` aufgebrochen →
  `test_real_no_edge_verdict_is_refused_by_demo_gate` **rot** („DID NOT RAISE"). Zurückgebaut → grün.

**Entscheidungen, die ich selbst getroffen habe:** D1/Weekday für die E2E-Smoke-Fixture (das
Qualitätstor ist dort am einfachsten ehrlich zu bestehen; H1/FxSession separat für den
`edge_test`-Pfad, der auf H1 fest verdrahtet ist); die Fixtures **synthetisch** und mit Manifest
committen (kein Marktdatum ins öffentliche Repo — die Marktdaten-Regel bleibt); die Herkunfts-Pflicht
auch auf `learning_phase.propose_parameter_sets` ausdehnen (ein Vorschlag ist ein Versuch und zählt
in die Deflation — also benennt auch er Daten + Code); die Werkzeuge leiten den Commit ab, das
Gate-Modul koppelt sich **nicht** an git (Aufrufer liefert, fail-closed am Rand); den Dirty-Tree-Fix
als **fail-closed-Wurf** (statt `<hash>-dirty`-Markierung), weil ein nicht reproduzierbarer Lauf gar
nicht erst registriert werden soll — Code erzwingt Ehrlichkeit statt Betreiber-Disziplin.

**Auffälligkeiten, gemeldet, nicht angefasst (ehrlich — vom §9-Review, kein Blocker für dieses
Paket):**
- **NIEDRIG — Lese-/Audit-Härtungslücke im Ledger:** `iter_trials()` ersetzt fehlende Herkunft
  still durch `"legacy"`, und `check_integrity()` prüft die Herkunft nie. Eine hand-angehängte Zeile
  ohne Herkunft ist so von einem echten Alt-Eintrag nicht unterscheidbar und wird mitgezählt.
  Konservativ (Overcount senkt die DSR, kann sie nicht schönrechnen), die **Schreib**-Pflicht ist
  intakt — daher Follow-up, kein Blocker. Richtung: nach der Migration `"legacy"`-Coercion abschaffen
  bzw. `check_integrity` fehlende Herkunft flaggen lassen.
- **HOCH, aber vorbestehend/außerhalb der Paket-6-Diff — `count_scope='total'` ist ordnungsabhängig:**
  `deflated_sharpe_for_report` liest `total_trials` **zum Aufrufzeitpunkt**. In einer Mehr-Instrument-
  /Mehr-Strategie-Kampagne wird der zuerst getestete Lauf nur gegen seine ~6 Versuche deflationiert,
  der letzte gegen die volle Zahl — „Wunsch-Instrument zuerst" = schwächste Deflation, an der
  Tor-Schwelle (Bedingung 2, `deflated_sharpe > 0.95`) messbar order-gameable. Der Code ist im
  Paket-6-Diff **unverändert** (Kontextzeilen), also vorbestehend und keine Herkunfts-Änderung —
  fällt nicht unter das Blockier-Kriterium dieses Commits. Als eigenes Ticket vermerkt: Endbewertung
  gegen den finalen Registerstand oder die vorregistrierte Kampagnengröße
  (`Preregistration.total_instruments/total_folds`), nicht gegen den laufenden Stand.

**Zeilenstand (gemessen, 2026-08-14):** 6.958 Zeilen, 30 Module, 384 Testfunktionen, 438 Testfälle
grün; `ruff`, `mypy --strict`, `gen_docs --check`, `check_doc_numbers` sauber.
