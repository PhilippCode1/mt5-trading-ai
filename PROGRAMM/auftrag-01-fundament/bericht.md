# Bericht Auftrag 1 — Fundament

**Stand: in Arbeit (T3 läuft).** Jede Zahl nennt ihre Bezugsgröße und ihre Belegdatei unter `belege/`. „ausgeführt" heißt: Ausgabe liegt bei; „gelesen" heißt: aus dem Quelltext, nicht gemessen. Referenzstand für alle roten Eichfälle: 306bbaa im Worktree `../nachstellung-306bbaa` (ohne `betrieb/`, ohne `daten/`, also wie ein frischer Klon; Windows, Python 3.11.7).

## 1 · Nachstellung der Befunde der Bewertung (T3)

Die Bewertung vom 2026-09-02 ist ein Prüfauftrag. Jeder Befund wurde mit eigenem Skript gegen 306bbaa nachgestellt; drei Skripte sind aus den Nachproben der Bewertung abgeleitet (Kopfzeile nennt die Quelle), die übrigen sind neu. Alle Ausgaben: `belege/03-nachstellung/`.

| Befund | nachgestellt | Ausgabe (Beleg) | Abweichung von der Bewertung |
|---|---|---|---|
| **D1** Erkundungswürfel im Trockenlauf latcht Schwebeakte und Global-Halt; `clear_halt()` löst nicht | ja, ausgeführt | `03-befunde-v1-v9.txt` V1: `halt_reason: sendeversuch_unklar:open-EURUSD-…`, Eintrag in der Schwebeakte, nächste Eröffnung auch nach `clear_halt()` mit `schwebender_auftrag` abgewiesen | keine |
| **D2** Reduce-only ohne Positionsticket geht als Marktorder raus | ja, ausgeführt | V2: `'position' im Request? False`, `sl = 0.0`, `accepted = True`; V2b: SLTP-Request ohne `symbol`, nur-SL-Aufruf ohne `tp` | keine |
| **D3** Positionsgröße/Marge ohne Währungsumrechnung | ja, ausgeführt | V3: EURGBP auf USD-Konto, Verlust am Stop 63,15 USD statt 50 USD (+26 %); USDJPY `volume = None (below_volume_min)`; V3c: `required_margin = 30000.00` statt 33 USD | keine |
| **D4** `reconcile()` überschreibt fremden Halt-Grund | ja, ausgeführt | V4: `tagesverlust` → `reconcile_drift:notional_drift_exceeds_limit` | keine |
| **D5** Scheitert das Vermerken (OSError), bleibt `_halted False` | ja, ausgeführt | V7: `venue.is_halted(): False`, Sendeversuch nur im Prozessspeicher | keine |
| **D6** Defekte Schwebeakte verwirft unlesbare Einträge dauerhaft | ja, ausgeführt | V6: `open-C` nach `vermerken()` weg, `sperrgrund = None` | keine |
| **D7** Geisterpositionen nach Neustart sperren Eröffnung | ja, ausgeführt | V5: `open_position_count nach Neustart: 3`, `reason: risk_concurrent_position_cap` | keine |
| **D8** Risikozustand und Schwebeakte per Vorgabe flüchtig; Umgebungsvariablen undokumentiert | ja, ausgeführt | `03-befunde-weitere.txt`: `RiskManager().zustand_dauerhaft = False`, `_schwebeakte_waehlen().dauerhaft = False`, `live_betrieb.py:832 RiskManager()`; 7 `os.environ`-Lesestellen im Paket; `.env.example`: „liest keine Umgebungsvariablen"; 0 Markdown-Dateien nennen eine der drei Variablen | keine |
| **D13/D20** Serverzone fest `Europe/Helsinki`; keine Gap-Sperre vor dem Wochenende | ja, ausgeführt/gelesen | `kalender.py:50-51`; 2026: **28 Tage**, an denen EU- und US-Sommerzeitregel auseinanderliegen (`zoneinfo`); `freshness.py`: `MAX_SNAPSHOT_AGE = 5 s` → ein Stundenversatz sperrt jeden Eintritt; `gap_events` Vorgabe `()`, `live_betrieb.py` nennt Gap/Wochenende/Freitag in 0 Zeilen | Bewertung: „2–4 Wochen im Jahr" — gemessen 4 Wochen für 2026 |
| **Z** Zulassung ist ein Kommandozeilenargument | ja, ausgeführt | `live_betrieb.py:814` (`--scharf`, Freitext), `:827` (`allow_write=bool(args.scharf)`), `:924` (`CriteriaVerdict(passed=bool(args.scharf))`); `bool('Maschinenprobe') = True` | keine |
| **E** ESMA-Deckel binden nie | ja, ausgeführt | V3b: effektiv 5 (`requested`) für fx_major (Deckel 30), fx_minor/gold/index_major (20), index_minor/commodity (10); equity 5, crypto 2 | keine |
| **G** Sechs-Bedingungen-Tor ohne Trennschärfe | ja, ausgeführt (89 s) | `03-befund-g-trennschaerfe.txt`: 3.000 Wiederholungen je Zeile, T=2.000, N=60: wahre Sharpe 0 → Bedingung 1 zu 17,0 % bestanden; Sharpe 1,0 → beide 0,1 %; **Sharpe 2,0 → 1,5 %**; 3,0 → 12,1 %; 4,0 → 41,7 %; Bedingung 2 verlangt annualisiert 4,22 | identisch (gleicher Seed 20260902) |
| **K** Backtest füllt zum Close des Signalbars, zählt Nächte nach UTC, kennt weder Stop noch Margin-Call | ja, ausgeführt | `03-befund-k-engine.txt`: (A) Fill 1,1000 = Close des Signalbars, am Open wäre der Bruttoertrag 0 statt 500 USD; (B) Kosten 18,00 USD je Roundturn = Handrechnung; (D) drei Randfälle, davon **alle drei** gegen den 21/22-UTC-Rollover falsch gezählt; (F) `net_return = −84,3 %`, `max_drawdown = 99,0 %`, Lauf läuft weiter | Bewertung: „von vier Randfällen zwei falsch" — das Skript fährt drei Fälle, alle drei weichen ab |
| **T (a)** 12 Tests überspringen sich selbst | ja, ausgeführt (149 s) | `03-grundmessung-pytest-worktree.txt`: im Worktree ohne `betrieb/` **1612 passed, 12 skipped**, Liste identisch (test_ausstiegsdeckung 1, test_buchtreue 2, test_journal_leser 1, test_laufabschluss 8); mit `betrieb/` (dieser Rechner, HEAD): 1629 passed, **0 skipped** (`02-pre-push-erster-lauf.txt`). Quelltext: 20 `pytest.skip(`-Stellen, 13 mit Journalbezug | Bewertung: 1611 passed + 1 failed auf Linux; hier 1612 passed, weil der Windows-Pfad-Test auf Windows grün ist |
| **T (b)** ein Test nur unter Windows grün | ja, CI + Mechanik | CI-Läufe 306bbaa und 4d02db3 (`00-ci-nach-t0.txt`): `test_localappdata_wird_nur_unter_windows_gefragt` rot auf ubuntu; Mechanik: `PurePosixPath('C:\Users\…').is_absolute() = False` (`risiko_zustand.py:407`) | keine |
| **T (c)** CI auf Linux 2 von 8 Toren rot (pytest, mypy) | CI-Historie + lokal, ausgeführt | 8 von 8 GitHub-Läufen seit 2026-08-19 `failure`; auf GitHub fällt `Tests` als erstes Tor, die übrigen werden übersprungen. mypy-Fall nachgestellt mit Python-3.13-Interpreter ohne `MetaTrader5` und **frischem Cache**: `Found 2 errors in 1 file` (`live_betrieb.py`, `import-not-found` nicht von `type: ignore[import-untyped]` gedeckt) — `03-mypy-linuxfall.txt`. Erster Versuch im Worktree meldete „Success", weil der 3.11-Cache wiederverwendet wurde (Messfehler, erkannt und korrigiert). `ruff format --check` bei 306bbaa: 112 von 171 Dateien würden umformatiert (`03-grundmessung-statisch-worktree.txt`) | keine; die CI selbst zeigt nur das erste rote Tor, die Bewertung fuhr die acht einzeln |
| **T (d)** Mutationstor vergiftet den Bytecode | ausstehend | `03-grundmessung-mutation-worktree.txt` (folgt) | |
| **T (e)** Flake `test_der_takt_schreibt_den_kontozustand` | ja, ausgeführt | `03-flake-worktree.txt`: **3 von 100** Läufen rot (Läufe 72, 80, 98); lokal am HEAD zusätzlich 1 Fehlschlag in einem Lauf (`00-pytest-lokal-nach-t0.txt`: `'HaltVenue' object has no attribute 'get_instrument'`) | Bewertung 4 von 100 und 1 von 30 — gleiche Größenordnung |
| **Werkzeuge** `--help`, Verhalten ohne Terminal | ja, ausgeführt | `03-grundmessung-statisch-worktree.txt`: `--help` bei **27 von 29** Werkzeugen Exit 0; rot: `edge_test.py` (`ValueError: unsupported format character 'v'`) und `betrieb_auswerten.py` (kein argparse, liest `sys.argv[1]`). Mit unsichtbarem `MetaTrader5` (Shim, wie Linux): `mt5_smoke.py` benannt („nicht installiert", Exit 1), `live_betrieb.py` und `live_konsole.py` **Traceback** aus `venue/mt5.py:2156`, Exit 1. **Neuer Befund (Windows):** ist das Paket installiert und läuft kein Terminal, **startet `MetaTrader5.initialize()` das Terminal selbst** (vorher kein `terminal64`-Prozess, danach PID 31256) und verbindet sich mit dem gespeicherten Konto — `atr_messung.py` schrieb daraufhin `config/atr_measurements.json` im Worktree, `live_betrieb.py` fuhr 4 Takte im Trockenlauf (kein Schreibrecht, keine Order) | Bewertung: 26 von 29 mit Exit 0 (andere Zählung); Autostart des Terminals war auf Linux nicht beobachtbar |
| **Geheimnis-Scan** Exit immer 0 | ja, ausgeführt (241 s) | `03-grundmessung-statisch-worktree.txt`: 129 Funde (40 detect-secrets Baum, 76 roh / 39 bereinigt im Verlauf über 1.284 Blobs aus 127 Commits, 13 Muster im Baum), **Exit 0**; Laufzeit 241 s | Bewertung: 77 Funde (detect-secrets dort für den Baum nicht installiert); Klasse bestätigt: kein Tor |
| **Terminal, lesend** (Vorgriff auf A9) | ja, ausgeführt | `03-terminal-lesend.txt`: `mt5_smoke.py` ohne Schreibrecht: Demokonto bestätigt, Equity 49.975,75 EUR, **rot** wegen Katalogsymbol `BTCUSD`, das das Terminal nicht kennt; `account_info`: `trade_mode=0` (Demo), MetaQuotes-Demo, Hebel 1, Build 6116; 12.455 Symbole; `US500` mit `trade_mode=0` (Handel gesperrt — die 753 Ablehnungen der Bewertung); `currency_margin` je Symbol vorhanden (EURUSD → EUR, USDJPY → USD); Serverzeitversatz des EURUSD-Ticks **+10.796 s** (Serverzone UTC+3) | — |
| **Zweigdeckung / Mutationstor** | ausstehend | (folgt) | |
| **Doku** Widersprüche, zwölf Standdokumente | ja, ausgeführt (Stichprobe) | `03-befunde-weitere.txt`: `FEHLT.md` nennt Backtest/Strategie in 4 Zeilen, `backtest/engine.py` und `strategies.py` existieren; `README.md` verweist auf `venue/mt5.py:447` — die Zeile ist leer, der Aufruf steht in 968; 57 Markdown-Dateien, 116.062 Wörter (`split()`); 10 Dateien mit „Stand" in den ersten 12 Zeilen | Bewertung: 113.408 Wörter, „zwölf Stand-Dokumente" — andere Zählweise, gleiche Größenordnung |
| **V8/V9** magic 60 Bit; Füllart-Bitmaske 4 als RETURN gedeutet | ja, ausgeführt | V8: `magic = 1041574110080518917, bits = 60`; V9: `filling_mode=4 -> 2` | keine |

**Was ich der Bewertung nicht bestätige:** nichts Inhaltliches. Zwei Zahlen weichen in der Zählweise ab (Wörter, Standdokumente), eine in der Fallzahl (K, Nächte: 3 statt 4 Randfälle im Skript).

## 2 · Bestandszählung und Wahl je Modul (T4)

(folgt — `belege/04-bestand.txt`)

## 3 · Behebungen mit Eichfällen (T6)

(folgt)

## 4 · Ehrliche CI (T7), Persistenz-Eichfall (T8), Smoke-Test (T9)

(folgt)

## 5 · Katalog und Wächter (T2)

- Katalog eingefroren 2026-09-03, SHA-256 `25b6ff9aaf93c3a4b7298d811c5d5534163ae0830b9a16f2a42b40138716b76a` (`PROGRAMM/abnahmekatalog.sha256`, in `zustand.md` genannt; `tools/katalog_hash.py --pruefen` grün: `02-pre-commit-erster-lauf.txt`).
- Wächter-Hook (`PROGRAMM/hooks/waechter.py`): Selbsttest 11 von 11 Fällen wie erwartet; stdin-Aufruf mit `Write` auf den Katalog → Exit 2 (`02-hook-waechter-selbsttest.txt`). **Live-Abweisung durch Claude Code in dieser Sitzung nicht belegt**: Hooks werden beim Sitzungsstart geladen, `.claude/settings.json` entstand in der Sitzung — der Schreibversuch über das Bash-Werkzeug ging durch und wurde zurückgenommen (`02-eichfall-live-arbeitsrepo.txt`). Wiederholung zu Beginn der nächsten Sitzung.
- Pre-Commit-Hook: im Wegwerf-Klon 3 Abweisungen (Katalog, Live-Schalter, Vorregistrierung), 1 Annahme (README), Hash-Tor rot nach Änderung / grün danach (`02-eichfall-pre-commit.txt`); live im Arbeitsrepo: Commit mit geändertem Katalog abgewiesen (`02-eichfall-live-arbeitsrepo.txt`). Acht Tore in 2,2–2,6 s je Commit.
- Pre-Push-Hook: volle Suite, 1629 passed in 130 s, 0 Bytecode geschrieben (`02-pre-push-erster-lauf.txt`).

## 6 · Gegenlese (T10)

(folgt)

## 7 · Eigene Fehler

Siehe `PROGRAMM/fehler.md`: F-001 und F-003 (Doku-Tore vor `git add` gefahren, zweimal), F-002 (Commit trotz roter Tore, Rückgabewerte verschluckt). Alle drei Klassen sind seit T2 im Pre-Commit-Hook abgefangen.
