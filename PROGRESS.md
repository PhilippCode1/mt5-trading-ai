# PROGRESS — mastertrade

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

**Was geschehen ist:** Ein neues Paket `mastertrade/` wurde unter `C:\Users\Acer\mastertrade`
angelegt — ausserhalb des Altbaums und ausserhalb von OneDrive. Es enthaelt die
Verzeichnisstruktur aus Teil 2, `pyproject.toml` (Ruff/Mypy/Pytest), `README.md`,
`.env.example`, `.gitignore` und einen Rauchtest. Ein frisches `git init` mit einem ersten
Commit haelt es von der alten Historie getrennt.

**Abnahme (Befehle und Ausgaben):**
```
$ python -c "import mastertrade, inspect; print(inspect.getfile(mastertrade))"
C:\Users\Acer\mastertrade\mastertrade\__init__.py        # zeigt in den NEUEN Baum
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mastertrade
Success: no issues found in 7 source files
$ python -m pytest -q
1 passed in 0.09s
```

**Entscheidungen, die ich selbst getroffen habe:** Ort `C:\Users\Acer\mastertrade` statt
eines Geschwisterordners im OneDrive-Baum, um Sync-Last und Platzrisiko auf der knappen
Platte zu vermeiden; die Isolation (`import mastertrade` zeigt in den neuen Baum) ist
nachgewiesen. Die Ruff-Konfiguration ist bewusst identisch zum Altbestand (line-length 88,
Regelauswahl `E,F,I,UP,B`, Test-Ausnahmen `E402,E501`), damit „gruen im Alt" und „gruen im
Neu" dasselbe bedeuten.

**Eigene Fehler in diesem Paket:** keine in U1 selbst.

**Zeilenstand:** leeres Paket, nur Geruest.

---

## ERLEDIGT U2 — Risiko- und Sperrschicht umgezogen

**Was geschehen ist:** Die elf Module aus Teil 4.1 und ihre zehn Testdateien wurden in den
neuen Baum kopiert, die Importe von `shared_py.*` auf die neuen Paketpfade umgeschrieben
(`from shared_py import trials_ledger` → `from mastertrade.gates import trials as
trials_ledger`). Nach dem Umzug ist keine `shared_py`-Referenz mehr im Paket. Die beiden
Sperren wurden anschliessend absichtlich beschaedigt und liefen rot, bevor der Schaden
zurueckgenommen wurde.

**Abnahme (Befehle und Ausgaben):**
```
$ grep -rn 'shared_py' mastertrade tests
(keine)
$ python -m pytest -q
155 passed in 0.85s                 # 154 Kern-Faelle + 1 Rauchtest
$ python -m ruff check .
All checks passed!
$ python -m mypy --strict mastertrade
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
--strict` gilt fuer das Paket `mastertrade` (Teil 8, Punkt 2), Tests bestehen `ruff`.

**Eigene Fehler in diesem Paket:** Die mechanische Import-Umschreibung veraenderte die
Import-Sortierung und erzeugte 7 `ruff`-Fehler (I001) in Testdateien. Von `ruff` gefangen,
mit `--fix` (nur Sortierung) behoben; `pytest` war davor und danach unveraendert bei 155.

**Auffaelligkeiten, gemeldet, nicht angefasst:** `venues/protocol.py` ist ohne eigenen Test
umgezogen (es gab keinen). Gehoert in `VERLUST.md` (U5).

**Zeilenstand (gemessen):**
```
$ find mastertrade -name '*.py' | xargs wc -l | tail -1
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
`_band_for_purge_and_embargo`), nach `mastertrade/backtest/splits.py` uebernommen — die
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
$ python -m mypy --strict mastertrade
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

**Zeilenstand:** `mastertrade/backtest/splits.py` = 190 Zeilen; Paket-Summe waechst
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
$ python -m mypy --strict mastertrade tools
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
ueber `tools/` gefahren (ueber das Teil-8-Minimum `mypy --strict mastertrade` hinaus), um
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
generiert (159 Zeilen, nicht handgepflegt). Paket-Quellcode `mastertrade/` unveraendert 2.680.

---

## OFFEN — als Naechstes

- **U5** — `VERLUST.md` (Faehigkeiten und Sperren des Altbestands einordnen). Vor U6 vorlegen.
- **U6** — Altbaum archivieren, `.pth`-Leckagen pruefen (`import signal_engine` muss scheitern),
  `README.md`/`FEHLT.md` finalisieren.
