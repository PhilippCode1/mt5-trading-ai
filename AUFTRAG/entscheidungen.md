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

---

## E-004 — Die beiden Doku-Tore gelten nicht für `AUFTRAG/`

**Datum:** 2026-08-19 · **Stufe:** 1 · **Entschieden von:** ausführender Agent

**Entscheidung.** `tools/check_docs_claims.py` zählt `AUFTRAG/` nicht mehr gegen die
Obergrenze von 32 Markdown-Dateien (prüft den Ordner aber weiterhin auf Behauptungen).
`tools/check_doc_numbers.py` führt `AUFTRAG/` in `HISTORICAL`, wie `PROGRESS.md` und
`docs/audit/`.

**Anlass — und der war mein eigener Fehler.** Der Stufe-0-Commit hat `AUFTRAG/` in die
Versionsverwaltung gebracht. Beide Tore zählen getrackte Dateien; sie wurden dadurch rot.
Vor dem Commit meldete `check_docs_claims` noch „ok - 32/32", weil der Ordner untracked
war. Ich habe das Gate-Set vor dem Stufe-0-Push nicht vollständig gefahren — siehe
`fehler.md`, F-004.

**Warum nicht die Grenze anheben.** Das Werkzeug dokumentiert im eigenen Kommentar, dass
die Grenze schon zweimal angehoben wurde, „jeweils für einen vorgeschriebenen
Abschlussordner", und dass sie „Doku-Wildwuchs bremsen, nicht einen Auftrag verhindern"
soll. Eine dritte Anhebung wäre naheliegend gewesen — und falsch: `AUFTRAG/` wächst
**bauartbedingt** mit jeder Stufe (ein Bericht je Stufe, bis zu elf). Die Grenze bei jeder
Stufe nachzuziehen ist genau die Ratsche, vor der derselbe Kommentar warnt. Sie steht
deshalb unverändert bei 32 für die Projektdoku, und der Auftragsordner fällt gar nicht
erst in ihren Geltungsbereich.

**Was ausdrücklich scharf bleibt.** Die Behauptungsprüfung läuft weiter über `AUFTRAG/`.
Gefahren als roter Eichfall: „10/10 und produktionsreif" in `zustand.md` → Exit 1 mit zwei
Treffern; nach Rücknahme → Exit 0 (Beleg: `stufen/01-historie/belege/05-doku-tore.txt`).
Das ist die Hälfte, auf die es ankommt — der Dauerauftrag verbietet Notenbehauptungen in
§0, und ein Bericht darin soll daran genauso scheitern wie jede andere Datei.

**Der ehrliche Rest.** `AUFTRAG/zustand.md` ist **kein** historisches Dokument, sondern
der laufende Stand — und es trägt eine harte Commit-Kennung, weil §10 des Vertrags genau
das Format `Zuletzt: <Datum, Commit>` vorschreibt. Hier widersprechen sich Vertrag und
Tor, und ich habe dem Vertrag den Vorrang gegeben. Wer das anders sieht, ändert eine
Zeile in `HISTORICAL` und muss dann §10 anders auslegen.

**Verworfene Alternative.** `MAX_MARKDOWN_FILES` von 32 auf 41 anheben. Verworfen: das
wäre eine Schwelle, die gesenkt wird, damit etwas durchgeht (V6) — und sie wäre bei
Stufe 2 wieder fällig.

---

## E-005 — Kein zweites Abrufwerkzeug für die Historie

**Datum:** 2026-08-19 · **Stufe:** 1 · **Entschieden von:** ausführender Agent

**Entscheidung.** Das geduldige Vorwärmen des `.bi5`-Zwischenspeichers geschieht mit einem
Wegwerf-Skript im Ablagebereich außerhalb des Repositoriums. Es kommt **nicht** nach
`tools/`.

**Begründung.** `tools/fetch_data.py` ist das Abrufwerkzeug des Standes und macht bereits
alles, worauf es ankommt: Dekodierung, Wochentagsfilter, Qualitätstor, Manifest,
Prüfsumme, Gegenprobe. Was hier fehlte, war allein Geduld gegenüber einer gedrosselten
Gegenstelle. Ein zweites Werkzeug im Repo hätte zwei Abrufpfade erzeugt, von denen der
schwächere übrig bleibt (V6), und neuen Code ohne Aufrufer im Ausführungspfad (V1). Das
Skript legt nur Rohdateien an den Ort, an dem `--cache` sie ohnehin sucht.

**Verworfene Alternative.** Den Backoff in `tools/fetch_data.py` selbst erhöhen. Nicht
verworfen, sondern **vertagt**: sinnvoll, sobald belegt ist, dass die Drosselung kein
Einzelfall dieser Umgebung ist. Eine Änderung am geprüften Werkzeug wegen einer einmal
beobachteten Netzlage wäre verfrüht.

---

## E-006 — Der Halal-Strang wird ersatzlos entfernt, nicht stillgelegt

**Datum:** 2026-08-19 · **Stufe:** nach dem Ergebnistor · **Entschieden von:**
**Auftraggeber** (Anweisung: „Entferne halal-vorfrage komplett aus dem gesamten Projekt
mit Code"). Die Ausführung und ihre Reichweite hat der ausführende Agent festgelegt.

**Entscheidung.** Beide Module (`costs/halal.py`, `venue/halal.py`), das Live-Tor
`Mt5Venue._enforce_halal`, der Runner-Schritt, die drei Konfigurationsfelder
(`account_swap_free`, `interest_bearing_margin`, `scholar_review_id`), der Schalter
`edge_test.py --halal`, das Feld `MarketSpec.financing_policy`, die zugehörigen Testfälle
und die Datei `HALAL-VORFRAGE.md` samt ihrer Kopie sind gelöscht — nicht auskommentiert,
nicht hinter einen Schalter gelegt, nicht als toter Zweig behalten. Bezifferung in
`geloescht.md`.

**Begründung.** Ein stillgelegtes Tor ist die schlechtere Lage als ein entferntes: Es steht
weiter in der Doku, es wird weiter mitgetestet, und es erweckt den Eindruck einer Sperre,
die nicht mehr sperrt. V1 verlangt für Code ohne Aufrufer im Ausführungspfad ohnehin die
Löschung. Der Auftraggeber hat die Entfernung angewiesen; die halbe Ausführung hätte den
Stand unehrlicher gemacht als beide Vollvarianten.

**Was dadurch am Orderpfad wegfällt — ausdrücklich benannt.** `_enforce_halal` war ein
fail-closed-Tor auf **jeder eröffnenden Live-Order**. Es hat zwei Dinge erzwungen: eine
mechanische Kontokonfiguration und das Vorliegen einer hinterlegten menschlichen Freigabe.
Beides ist weg. Der Live-Pfad ist damit um eine Sperre ärmer.

**Was bleibt — gemessen, nicht behauptet** (`tests/test_orderpfad_verdrahtung.py` zählt es
an einer echten Order nach): Idempotenz, Global-Halt-Latch, Stop-Pflicht, Frische-Latch,
vierteilige Live-Freigabe, Hebel-Preflight, Kostentor, Verlustgrenzen, Drossel,
Stop-Budget, Positionsgröße — und darunter `allow_write=False` sowie die Demo-Pflicht am
Terminal. Der Wegfall betrifft keine dieser Sperren; die Zahl der zählenden Sollsperren
aus Paket 2 A3.2 bleibt fünf.

**Verworfene Alternative.** Das Tor behalten und nur die Vorfrage-Dokumente entfernen.
Verworfen: Ein Tor, dessen Begründungsdokument fehlt, ist nicht prüfbar — man kann weder
sagen, wogegen es schützt, noch wann es fallen dürfte. Das ist genau die Sorte Sperre, die
später aus Unkenntnis entfernt wird.

---

## E-007 — Eingefrorene Belege werden ergänzt, nicht umgeschrieben

**Datum:** 2026-08-19 · **Stufe:** nach dem Ergebnistor · **Entschieden von:** ausführender
Agent

**Entscheidung.** Die Anweisung „komplett aus dem gesamten Projekt" ist auf alle Dokumente
angewandt worden, die den **heutigen** Stand beschreiben — und **nicht** auf die vier
Bestände, die sich selbst als datierten Beleg ausweisen: `ABSCHLUSS/`, `ABSCHLUSS-3a/`,
`docs/audit/` und `PROGRESS.md`. Diese vier haben stattdessen einen datierten Nachtrag
bzw. einen angehängten Eintrag bekommen, und tote Verweise auf gelöschte Dateien sind
entschärft.

**Begründung.** `ABSCHLUSS/06` trägt im Kopf wörtlich „EINGEFROREN AUF DEM STAND VON
PAKET 2 … wird bewusst NICHT mehr nachgezogen"; `PROGRESS.md` trägt „Angehaengt, nie
ueberschrieben"; `check_doc_numbers.py` nimmt `PROGRESS.md` und `docs/audit/`
ausdrücklich als historische Belege von der Prüfung aus. Ein Bericht vom 2026-08-17 so
umzuschreiben, dass er 2026-08-19 nie etwas anderes gesagt hätte, ist keine Bereinigung,
sondern eine Fälschung — und der ganze Auftrag steht darauf, dass diese Ordner belegen,
was **vorher** gedacht wurde.

**Was das konkret heißt.** In den vier Beständen stehen weiterhin Sätze über einen Strang,
den es nicht mehr gibt. Jeder von ihnen ist über den Nachtrag am Kopf des jeweiligen
Ordners bzw. den Schlusseintrag als überholt gekennzeichnet. Wer die vier Bestände
ebenfalls bereinigt haben will, muss das anweisen — es ist eine Entscheidung über die
Beweislage, nicht über den Code.

---

## E-008 — Die Erfüllbarkeitsmessung verbraucht keinen Versuch

**Datum:** 2026-08-19 · **Stufe:** Nachtrag zu 3 · **Entschieden von:** ausführender Agent

**Entscheidung.** Der Lauf von `tools/torerfuellbarkeit.py` schreibt **keinen** Eintrag in
`TRIALS.jsonl`. Der Registerstand bleibt bei 31 von 60.

**Begründung.** Der Auftrag verlangt in Stufe 3: „Jeder Lauf — auch ein abgebrochener —
schreibt vor der Ergebnisausgabe einen Eintrag." Ein „Lauf" ist dort der Lauf des
Simulators gegen eine Hypothese; der Registerstand geht in die Deflation ein und misst,
**wie viel gesucht wurde**. Diese Messung sucht nichts: sie fährt keinen Backtest, prüft
keine Hypothese, erzeugt kein Edge-Urteil und berührt keine Strategieparameter. Sie
rechnet aus, was die vorregistrierten Schwellen miteinander verlangen.

Einen Eintrag zu schreiben wäre nicht die vorsichtigere, sondern die falsche Wahl: er
würde die Deflation künftiger echter Versuche verschärfen und dabei eine Suche zählen,
die nicht stattgefunden hat. Ein Register, das etwas anderes zählt als das, wofür es
gebaut ist, ist danach für nichts mehr brauchbar.

**Was die Entscheidung angreifbar macht.** Die Messung liest die Reihe, deren OoS-Block
„genau einmal angefasst" werden darf. Deshalb wird auf dem **In-Sample**-Block gerechnet;
der OoS-Block erscheint nur in einer Stationaritäts-Gegenprobe, die in keine Zahl eingeht,
die etwas entscheidet. Wer das anders sieht, findet den Sachverhalt hier.

**Verworfene Alternative.** Ein zweites, getrenntes Register für Messungen ohne
Hypothese. Verworfen aus demselben Grund wie E-002: zwei Register für benachbarte Fragen
laufen auseinander, und danach weiß niemand mehr, welches die Deflation speist.
