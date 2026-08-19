# Entscheidungen

*Je Eintrag: Entscheidung, Begründung, verworfene Alternative. Was hier steht, hat der
ausführende Agent entschieden — es ist nicht vorgegeben worden.*

---

## E-001 — `mt5_trading_ai` ist der lebende Stand

**Datum:** 2026-08-19 · **Stufe:** 0 · **Entschieden von:** ausführender Agent

**Entscheidung.** `C:\Users\Acer\mt5_trading_ai` ist der Stand, auf dem dieser Auftrag
weiterarbeitet. `AUFTRAG/` liegt in dessen Wurzelverzeichnis.

**Begründung, in der Reihenfolge der Beweiskraft:**

1. **Er ist der einzige Stand mit einem Simulator, der Kosten erzwingt.**
   `backtest/engine.py` ruft `order_roundturn_cost` (Zeile 292) und trägt im Kopf die
   Zusage „Es gibt keinen kostenlosen Modus, auch nicht zum Debuggen." Sechs Stellen
   werfen `LookAheadError`. Die beiden anderen Stände haben gemessen **keinen**
   Simulator: `strategy-validation` 0 Definitionen und 0 Ergebnisartefakte,
   `bitget-btc-ai` 0 Kostenbegriffe in `runner_replay.py`.
2. **Simulator und Ausführungsstrecke liegen zusammen.** Damit entfällt der Haltefall
   aus §2.4 des Auftrags. Es gibt nichts zusammenzuführen und nichts zu wählen, das
   das andere verlöre.
3. **Er ist der jüngste Stand.** Letzter Commit 2026-08-18, ein Tag alt; die beiden
   anderen 8 bzw. 13 Tage. Alle 79 Commits liegen in den letzten 30 Tagen.
4. **Er ist der einzige Stand mit einem geführten Versuchsregister.** `TRIALS.jsonl`
   hält 7 Einträge mit `code_commit`, `data_checksum`, `net_expectancy` und
   `period_start`/`period_end`. Ohne Register ist die Signifikanzrechnung aus §7 Stufe 3
   nicht führbar.
5. **Sein Handelsplatz ist erreichbar.** MT5 in 76 Dateien, Bitget in 0. Der verworfene
   Stand `bitget-btc-ai` hängt an einem Handelsplatz, der im Wirtschaftsraum des
   Auftraggebers nicht betrieben wird — nach §9.2 eine harte Grenze, die kein Code
   aufhebt.

**Verworfene Alternative 1: `bitget-btc-ai` weiterführen.** 101.323 Zeilen
Produktionscode, 15 Dienste, ein Dashboard von rund 100.000 Zeilen — der mit Abstand
größte Bestand. Verworfen, weil der Umfang gegen das Ziel nichts ausrichtet: kein
Simulator, kein Kostenmodell im Validierungspfad, und ein Handelsplatz, an dem aus dem
EWR nicht gehandelt werden kann. Versunkene Kosten zählen nach §3 des Auftrags nicht.

**Verworfene Alternative 2: `strategy-validation` weiterführen.** Der methodisch
sauberste Ansatz der drei — eine eingefrorene Vorregistrierung mit neun vorab bezifferten
Kriterien, geschrieben bevor Daten geladen waren. Verworfen, weil sie einen Score prüft
(`signal-engine/config.py:91-100`, Gewichte 0,22/0,20/0,22/0,10/0,18/0,08) und eine
Anlageklasse (Krypto über Binance), die der gewählte Stand beide nicht handelt. Ihre
Maschine wurde nie gebaut. Was an ihr überführbar ist, ist die Haltung, und die ist im
gewählten Stand bereits vorhanden.

**Was diese Entscheidung nicht behauptet.** Sie sagt nichts darüber, ob der gewählte
Stand einen Vorteil hat. Das ist die Frage aus §1, und sie wird in Stufe 3 beantwortet.

---

## E-002 — Kein zweites Versuchsregister

**Datum:** 2026-08-19 · **Stufe:** 0 · **Entschieden von:** ausführender Agent

**Entscheidung.** `AUFTRAG/versuchsregister.jsonl` wird **nicht** angelegt. Maßgeblich
bleibt `TRIALS.jsonl` im Wurzelverzeichnis, das bereits 7 Einträge trägt und an das
`backtest/engine.py::run_registered_backtest` bei jedem Lauf anhängt.

**Begründung.** §10 des Auftrags nennt `AUFTRAG/versuchsregister.jsonl` als Ablageort.
Ein zweites Register neben einem bestehenden wäre exakt der Fehler, den Sperre V6
verbietet: zwei Zählungen derselben Sache, von denen die schwächere übrig bleibt. Der
Versuchszähler geht nach §7 Stufe 3 in die Signifikanzrechnung ein; er darf nicht in zwei
Dateien stehen. Die strengere Fassung ist die bestehende — sie ist an den Simulator
verdrahtet, die neue wäre es nicht.

**Verworfene Alternative.** `TRIALS.jsonl` nach `AUFTRAG/versuchsregister.jsonl`
verschieben und den Simulator umhängen. Verworfen für Stufe 0: das ist eine Änderung am
Ausführungspfad und gehört nicht in eine Bestandsaufnahme. Falls der Auftraggeber die
Ablage nach §10 buchstäblich will, ist der Umzug in Stufe 3 zu machen, zusammen mit dem
Schreiber — nicht getrennt von ihm.

---

## E-003 — Vorregistrierung wird erweitert, nicht ersetzt

**Datum:** 2026-08-19 · **Stufe:** 0 · **Entschieden von:** ausführender Agent

**Entscheidung.** `AUFTRAG/vorregistrierung/` ist angelegt, aber leer. Die Vorregistrierung
für Stufe 3 wird auf `ABBRUCH.md` §2 aufsetzen (60 vorregistrierte Versuche, 7 verbraucht,
befristet bis 2027-08-17) und diese Zahlen fortschreiben, nicht neu beginnen.

**Begründung.** Ein neuer Versuchszähler bei null wäre eine Verbesserung der Kennzahl ohne
Änderung der Wirklichkeit — nach §0 des Auftrags der Beweis, dass die Handlung zu
unterlassen ist. Die sieben verbrauchten Versuche sind gelaufen und stehen im Register;
sie gehen in die Deflation ein.

**Verworfene Alternative.** Eine frische Vorregistrierung ohne Bezug auf die bestehende.
Verworfen aus dem genannten Grund.
