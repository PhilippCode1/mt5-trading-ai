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

## OFFEN — als Naechstes

- **U3** — `splits.py` umziehen, Purge/Embargo-Default ≠ 0 korrigieren, Leckage-Gegentest,
  negativ fahren.
- **U4** — Doku-Tore (`gen_docs`, `check_docs_claims` auf alle Markdown-Dateien) + README-Zahlentest.
- **U5** — `VERLUST.md` (Faehigkeiten und Sperren des Altbestands einordnen). Vor U6 vorlegen.
- **U6** — Altbaum archivieren, `.pth`-Leckagen pruefen (`import signal_engine` muss scheitern),
  `README.md`/`FEHLT.md` finalisieren.
