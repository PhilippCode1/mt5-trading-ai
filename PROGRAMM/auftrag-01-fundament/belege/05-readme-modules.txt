# T5 Schritt 4: README neu, MODULES.md mit Aufrufern, Kennzahlenblock erzeugt (2026-09-03)
$ python -m pytest -q -p no:cacheprovider
1511 passed in 257.63s (0:04:17)
[exit=0]
$ python tools/gen_docs.py --check
ok — MODULES.md ist aktuell (599 Zeilen).
$ grep -c 'Aufrufer:' MODULES.md
39
$ grep -B1 -A1 'Aufrufer: Paket 0 · Werkzeuge 0' MODULES.md   (Module ohne Aufrufpfad ausserhalb der Tests)
(keines)
$ git ls-files '*.md' | grep -v '^archiv/' | grep -v '^PROGRAMM/'
CLAUDE.md
MODULES.md
README.md
