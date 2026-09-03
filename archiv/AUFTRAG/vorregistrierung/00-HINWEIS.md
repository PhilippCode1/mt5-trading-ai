# Hinweis zu diesem Ordner

Er ist absichtlich leer.

Die Vorregistrierung fuer Stufe 3 wird hier abgelegt, **sobald Stufe 3 beginnt** — und sie
setzt auf der bestehenden Regel auf, statt sie zu ersetzen. Siehe `../entscheidungen.md`,
Eintrag E-003.

Massgeblich bis dahin:

- **Kampagnen-Vorregistrierung:** `ABBRUCH.md` §2 — 60 vorregistrierte Versuche,
  **7 verbraucht**, befristet bis 2027-08-17.
- **Versuchsregister:** `TRIALS.jsonl` im Wurzelverzeichnis, 7 Eintraege. Es wird **nicht**
  nach `AUFTRAG/versuchsregister.jsonl` dupliziert (E-002); der Schreiber dafuer ist
  `mt5_trading_ai/backtest/engine.py::run_registered_backtest`.

Vor dem ersten Lauf der Stufe 3 gehoert hierher: Mindestzahl Trades, Mindest-Erwartungswert
nach Kosten, Signifikanzmass, Kostenannahme einschliesslich der 1,5-fachen, und der Stand
des Versuchszaehlers zum Zeitpunkt des Schreibens. Danach wird die Datei nicht mehr
geaendert.
