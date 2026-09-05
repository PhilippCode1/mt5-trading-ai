# Verschärfungen des Abnahmekatalogs (additiv)

Der eingefrorene Katalog (`PROGRAMM/abnahmekatalog.md`) wird nie bearbeitet. Wer einen Punkt verschärft, trägt ihn hier ein: Datum, Auftrag, Punkt, alte Zahl, neue Zahl, Begründung mit Messung. Lockern ist ausgeschlossen. Ein Eintrag hier gilt ab seinem Commit.

| Datum | Auftrag | Punkt | vorher | nachher | Begründung |
|---|---|---|---|---|---|
| 2026-09-04 | Auftrag 1 | A15, A17 (Geltungsbereich) | Geldpfad = 11 Dateien | Geldpfad = 14 Dateien (`risk/waehrung.py`, `execution/handelspause.py`, `execution/reconcile.py` dazu) | E-020: Kriterium „berührt eine Order oder das Konto“ auf alle Dateien angewandt, die in Auftrag 1 dazukamen; Deckung je Datei ≥ 90 % und Sonden gemessen (`06-mutationstor-voll.txt`, `06-zweigdeckung.txt`). Schwelle unverändert, Menge größer. |
| 2026-09-05 | Auftrag 1 | A15, A17 (Geltungsbereich) | Geldpfad = 14 Dateien | Geldpfad = 16 Dateien (`execution/leverage_preflight.py`, `execution/runner.py` dazu) | Gegenlese T10, E15: nach dem Kriterium E-020 (ein Fehler kann eine Order, ihre Größe, ihren Stop oder ihre Sperre verändern) gehören der Hebel-/Margenanschluss und der Runner, der die Order baut und sendet, zum Geldpfad. Deckung vor der Aufnahme 75,0 % und 56,5 % (Gegenlese, CI-Lauf 33977291625); Tests bringen beide über 90 % (`06-zweigdeckung-e15.txt`). Schwelle unverändert, Menge größer. |
