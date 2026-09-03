# Gelöscht und archiviert (Programm NEUAUFBAU)

Regel 5 des Rahmens: kein Code ohne nachgewiesenen Aufrufpfad. Sperre aus Masterprompt 01
§7: kein Löschen von Aufzeichnungen, Registern oder Berichten ohne Archivkopie mit
Prüfsumme; nie stilles Löschen. Je Eintrag: was, warum, Messung, wohin (Archivpfad und
Prüfsumme) oder „gelöscht, im Git-Verlauf bei Commit …".

## 2026-09-03 — Zwei verwaiste Claude-Code-Worktrees entfernt

- `.claude/worktrees/blissful-morse-94a3c6` (detached bei 53f75aa) und
  `.claude/worktrees/recursing-haibt-491e4d` (detached bei 43a97ad).
- **Messung.** `git status --short` in beiden: 0 Einträge — keine ungesicherte Arbeit;
  beide Commits liegen im Verlauf von `master`.
- **Wohin.** Nirgends: Arbeitskopien ohne eigenen Inhalt (`git worktree remove`,
  `git worktree prune`). Nicht Teil des Repositories, daher kein Archiv.

## 2026-09-03 — Fuenf Loeschkandidaten (E-009) samt Tests, Stand vor Loeschung 06bb392
- `mt5_trading_ai/backtest/llm_compare.py` (74 Zeilen): Huelle fuer ein kuenftiges LLM; einziger Aufrufer tools/modelllauf.py fuetterte sie mit Attrappen (Bewertung F3). Im Verlauf bei 06bb392.
- `mt5_trading_ai/gates/herausforderer.py` (375 Zeilen): JSON-Artefakt im Zustand 'wartend' ohne Weg in den Entscheidungspfad; kein Modell, das es befoerdert (Bewertung F3). Im Verlauf bei 06bb392.
- `mt5_trading_ai/gates/learning_phase.py` (230 Zeilen): Modellpfad, der jeden Trade auf net_pnl_r = 0 setzt; nur von tools/modelllauf.py erreicht (Bewertung F3). Im Verlauf bei 06bb392.
- `tools/modelllauf.py` (303 Zeilen): 'Trainingslauf' ohne Modell (Bewertung F3); Auftrag 1 schliesst Modelle aus. Im Verlauf bei 06bb392.
- `tools/oberflaeche.py` (1075 Zeilen): Web-Oberflaeche; Auftrag 1 schliesst Oberflaechen aus; Sammler-Thread starb ohne Terminal still (Bewertung F1). Im Verlauf bei 06bb392.
- `tests/test_llm_compare.py` (100 Zeilen): Tests des geloeschten Moduls (6 Faelle). Im Verlauf bei 06bb392.
- `tests/test_learning_phase.py` (132 Zeilen): Tests des geloeschten Moduls (9 Faelle). Im Verlauf bei 06bb392.
- `tests/test_stufe6_modellpfad.py` (409 Zeilen): Tests von modelllauf/herausforderer/learning_phase (26 Faelle). Im Verlauf bei 06bb392.
- `tests/test_oberflaeche_kacheln.py` (908 Zeilen): Tests der Oberflaeche (37 Faelle). Im Verlauf bei 06bb392.
- `tests/test_oberflaeche_seite.py` (291 Zeilen): Tests der Oberflaeche (27 Faelle). Im Verlauf bei 06bb392.
- `tests/test_stufe7_kaltstart.py::test_der_trainingslauf_weist_den_anteil_erkundender_beobachtungen_aus`: fuhr das geloeschte Werkzeug als Unterprozess.
- `tools/mutationstor.py`: die drei Sonden auf `gates/herausforderer.py` (Katalog 16 -> 13).
- `tools/zweigdeckung.py`: `gates/herausforderer.py` aus der Geldpfad-Liste (12 -> 11 Dateien).
- 9 Nennungen der Oberflaeche/des LLM-Tests in Docstrings als geloescht gekennzeichnet (nicht entfernt: sie erklaeren Entscheidungen im Code).
