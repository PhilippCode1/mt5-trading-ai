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
