# mt5-trading-ai

Kern eines KI-gestützten Handelssystems für MetaTrader 5, im Umbau nach dem Programm NEUAUFBAU (neun Aufträge, Ablage unter `PROGRAMM/`). Stand, Fortschritt und offene Haltepunkte stehen an genau einer Stelle: `PROGRAMM/zustand.md`. Der Rahmen, der in jeder Sitzung gilt, steht in `CLAUDE.md`. Was das Paket im Einzelnen enthält, erzeugt `tools/gen_docs.py` aus dem Code nach `MODULES.md`; dieses README beschreibt nur, wo etwas liegt und wie es startet.

Kein Dienst, kein Server, keine Datenbank, keine Oberfläche. Kein echter Handel: der Live-Pfad ist in allen Aufträgen des Programms technisch geschlossen (`config/live_freigabe.json`, alle Schalter aus, hook-geschützt).

## Was hier liegt

- `mt5_trading_ai/` — das Paket: Handelsplatz-Adapter mit Fake- und Echt-Terminal (`venue/`), Orderpfad mit Risikoschicht, Risikozustand und Schwebeakte (`execution/`, `risk/`), Kostenmodell (`costs/`), Datenlader und Datenqualität (`data/`), Kriterien, Register, Erkundung (`gates/`), Backtest-Maschine und Sechs-Bedingungen-Tor (`backtest/`, Logik unverändert bis Auftrag 3; in T5 nur Verweise nachgezogen und `llm_compare.py` gelöscht), Journal-Leser und Dienstgüte (`betrieb/`).
- `tools/` — Kommandozeilenwerkzeuge; jedes antwortet auf `--help`.
- `tests/` — die Testsuite (`python -m pytest -q`).
- `config/` — Instrumentenkatalog, Kostentabelle, Hebeldeckel je Anlageklasse, Manifeste der Datenreihen, Live-Schalter.
- `aufzeichnungen/` — die redigierte Aufzeichnung eines echten Demolaufs (2026-08-17).
- `PROGRAMM/` — das Programm NEUAUFBAU: Masterprompts und Bewertung (Eingang, unveränderlich), eingefrorener Abnahmekatalog, Zustand, Entscheidungen, Haltepunkte, eigene Fehler, Gelöschtes, Plan und Belege je Auftrag, die Hooks.
- `archiv/` — der Altstand vor dem Programm (Stufenberichte, Abschlussordner, Recherchen, Runbook), unverändert und per Manifest gesichert (`archiv/HERKUNFT.txt`).

## Start

Python 3.11 und `pip install -r requirements-dev.txt`. Der Import des Pakets braucht kein Fremdpaket; wer das MT5-Terminal anspricht, braucht `pip install MetaTrader5`, ein installiertes Terminal und ein angemeldetes Demokonto (Windows). Hinweis: `MetaTrader5.initialize()` startet ein nicht laufendes Terminal selbst und verbindet sich mit dem gespeicherten Konto.

```
python -m pytest -q                       # die Suite
python tools/mt5_smoke.py                 # lesender Smoke-Test am Terminal (sendet ohne --allow-write nichts)
python tools/live_betrieb.py --help       # Demo-Betrieb; ohne --scharf ein Trockenlauf
python tools/gen_docs.py                  # MODULES.md und den Kennzahlenblock unten neu erzeugen
```

## Tore

Jeder Commit fährt über `.githooks/pre-commit` neun Tore (Katalog-Hash, ruff check, ruff format, mypy strict, MODULES.md, Doku-Behauptungen, Doku-Zahlen, Kopien, Manifeste); jeder Push die volle Suite (`.githooks/pre-push`); die CI (`.github/workflows/ci.yml`) läuft auf einem frischen Linux-Klon. Lokal aktivieren: `git config core.hooksPath .githooks`. Weitere Tore mit eigenem Aufruf: `tools/zweigdeckung.py` (Zweigdeckung je Geldpfad-Datei), `tools/mutationstor.py` (Mutationssonden), `tools/geheimnis_scan.py`, `tools/katalog_hash.py --pruefen`, `tools/archiv_manifest.py --pruefen`.

Der Claude-Code-Hook `PROGRAMM/hooks/waechter.py` (`.claude/settings.json`) weist Schreibzugriffe auf den eingefrorenen Abnahmekatalog, die Live-Schalter und vorhandene Vorregistrierungen ab.

## Kennzahlen

Erzeugt von `tools/gen_docs.py`, geprüft von `tools/check_doc_numbers.py` und `tests/test_readme_numbers.py`; andere Dokumente verweisen hierher.

<!-- KENNZAHLEN-ANFANG (erzeugt von tools/gen_docs.py, geprueft von tests/test_readme_numbers.py) -->
- module_count: 42
- test_function_count: 1585
- source_lines: 18645
<!-- KENNZAHLEN-ENDE -->

## Zustand außerhalb des Arbeitsbaums

Risikozustand, Schwebeakte, Positionsbuch, Stoppdatei und Journale liegen im Zustandsordner des Benutzers (Windows: `%LOCALAPPDATA%\mt5_trading_ai
isiko`), nie im Repository. `tools/live_betrieb.py --zustandsordner <pfad>` waehlt ihn; ohne Angabe gilt `standard_zustandsordner()`. Ein fluechtiger Zustand ist ein ausdruecklicher Testtyp, den das Betriebswerkzeug abweist. Ansehen und Eingreifen: `tools/zustand.py --zeigen | --halt-freigeben | --schwebeakte-aufloesen`. Die drei Umgebungsvariablen des Altstands sind entfallen (Befund D8, `PROGRAMM/entscheidungen.md`).
