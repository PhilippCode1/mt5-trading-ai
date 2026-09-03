# Rückbau-Bestandsaufnahme

*Erhoben 2026-08-19, nach dem Ergebnistor. Diese Datei entscheidet nichts — sie legt dem
Auftraggeber Zahlen vor, damit H-004 nicht aus dem Bauch entschieden werden muss.*

---

## Warum es diese Datei gibt

§1 des Auftrags sagt für den Ausgang (B) zwei Dinge, und beide sind Anweisungen, keine
Empfehlungen:

> „(B) beendet den Auftrag ebenso gültig wie (A) — und zwar, **bevor weiterer Aufwand in
> Absicherung, Ausführung, Oberfläche oder Betrieb fließt**. Ein System, dessen Vorteil
> widerlegt ist, wird nicht abgesichert. **Es wird zurückgebaut oder aufgegeben.**"

Die Stufen 4 bis 10 sind wörtlich Absicherung, Ausführung, Oberfläche und Betrieb. **Es
gibt für diesen Ausgang keine nächste Stufe** — sie zu fahren wäre nicht Fortschritt,
sondern ein Verstoß gegen §1.

Was der Auftrag stattdessen vorsieht, ist „zurückgebaut **oder** aufgegeben". Welches von
beidem, entscheidet der Auftraggeber (H-004). Diese Datei misst, was an jeder Option
hängt.

---

## Der Bestand, klassifiziert

Gemessen über alle `.py` ohne `__pycache__`; Bezugsgrößen getrennt nach Paket und
Werkzeugen, weil das Vermischen die Prozentzahlen unlesbar macht.

### Paket `mt5_trading_ai/` — 47 Dateien, 15.248 Zeilen

*Neu gemessen am 2026-08-19 nach dem Halal-Rückbau. Die Anteile verschieben sich dadurch
nicht nennenswert: der entfernte Strang lag mit einem Modul in Gruppe A und einem in
Gruppe B.*

| Gruppe | Dateien | Zeilen | Anteil |
|---|---:|---:|---:|
| **A — Messapparat** (`backtest`, `data`, `costs`, `gates`) | 22 | **5.500** | 36 % |
| **B — Handelsstrecke** (`venue`, `execution`, `betrieb`) | 19 | **8.760** | **57 %** |
| **C — Risikoschicht** (`risk`) | 5 | 975 | 6 % |
| nicht klassifiziert (`__init__.py`) | 1 | 13 | — |

### Werkzeuge `tools/` — 21 Dateien, 7.507 Zeilen

| Gruppe | Dateien | Zeilen |
|---|---:|---:|
| **A — Messapparat** (`edge_test`, `fetch_data`, `aufloesung`, `ereignisstudie`, `atr_messung`, `kostentor`) | 6 | 3.318 |
| **B — Handelsstrecke** (`live_betrieb`, `live_konsole`, `oberflaeche`, `paper_run`, `mt5_smoke`, `betrieb_auswerten`, `betrieb_reihe`, `journal_sichern`) | 8 | 3.114 |
| Doku- und Prüfwerkzeuge (`check_*`, `gen_docs`, `geheimnis_scan`, …) | 7 | 1.075 |

### Die eine Zahl, auf die es ankommt

**57 % des Pakets ist Handelsstrecke.** Sie existiert ausschließlich, um zu handeln — und
für das Handeln gibt es nach dem Ergebnistor keinen belegten Grund. Rechnet man die
Werkzeuge dazu, sind es **11.874 von 22.755 Zeilen**.

---

## Was die drei Optionen aus H-004 konkret bedeuten

### Option 1 — Beenden (empfohlen)

Nichts wird gelöscht, nichts wird weitergebaut. Der Stand bleibt als das liegen, was er
ist: ein Apparat, der eine Frage ehrlich beantwortet hat.

- **Fällt weg:** die Stufen 4 bis 10, also der gesamte weitere Auftrag.
- **Bleibt:** alles, unverändert und lesbar.
- **Kosten:** keine.
- **Was man verliert:** nichts, außer der Möglichkeit, es sich später anders zu überlegen
  — und die bleibt ohnehin, weil nichts gelöscht wird.

### Option 2 — Zurückbauen

Gruppe B entfernen, damit das Repository nicht länger eine Handelsfähigkeit vorhält, für
die es keinen Grund gibt.

- **Fällt weg:** 19 Paketdateien mit 8.760 Zeilen plus 8 Werkzeuge mit 3.114 Zeilen.
- **Bleibt:** der Messapparat (A) und die Risikoschicht (C) — zusammen 6.475 Zeilen im
  Paket. Das ist genau der Teil, der den Befund getragen hat.
- **Nebenwirkung, gemessen:** von den 1.392 Testfällen hängen große Teile an Gruppe B
  (`test_mt5_venue`, `test_bar_geschlossen`, `test_live_betrieb_sperren`,
  `test_oberflaeche_kacheln`, `test_handelszeiten` …). Ein Rückbau ist keine Löschaktion,
  sondern ein Umbau mit eigener Abnahme.
- **Was man gewinnt:** ein Repository, dessen Umfang seiner belegten Aussage entspricht.
- **Was man verliert:** die MT5-Anbindung samt Not-Aus, Reconcile und Buchführung — 
  handwerklich der sorgfältigste Teil des Standes. Sie wieder aufzubauen wäre teuer.

### Option 3 — Eine neu begründete Hypothese

Zulässig unter den verbleibenden **29 von 60** Versuchen, befristet bis **2027-08-17**.

- **Bedingung:** eine eigene Begründungstiefe — eine benennbare Zwangslage, nicht andere
  Parameter derselben drei Hypothesen. Nachjustieren ist nach §7 ausdrücklich verboten.
- **Preis:** jeder verbrauchte Versuch macht die Deflation für alle späteren strenger. Bei
  31 verbrauchten Versuchen liegt die nötige Sharpe je Beobachtung bereits messbar höher
  als bei 7.
- **Was dagegen spricht, in Zahlen:** die höchste erreichte Trade-Zahl war 123 gegen eine
  vorregistrierte Mindestzahl von 2.000. Auf H1 über drei Jahre ist diese Schwelle mit
  Hypothesen dieser Art nicht erreichbar — nicht wegen der Hypothese, sondern wegen der
  Handelsfrequenz. Wer Option 3 zieht, muss das zuerst lösen.

---

## Was in jedem Fall stehen bleiben sollte

Unabhängig von der Wahl — das ist keine Empfehlung zur Sache, sondern zur Aufbewahrung:

1. **Der Messapparat (Gruppe A).** Er hat die Frage beantwortet, und er hat sich dabei
   selbst reproduziert: zwei der drei Läufe geben auf unabhängig neu beschafften Daten
   dieselben Zahlen wie der frühere Bericht. Das ist der belastbarste Teil des Vorhabens.
2. **Das Versuchsregister.** 31 Einträge, Abzug in
   `stufen/03-simulator/belege/06-trials-abzug.jsonl`. Ohne es ist jede spätere Deflation
   wertlos, weil die Zahl der bisherigen Versuche fehlt.
3. **Die Vorregistrierung und die Abschlussordner.** Sie belegen, was *vorher* gedacht
   wurde. Genau das macht den Befund prüfbar.

---

## Ein offener Punkt, der von H-004 unabhängig ist

Hier standen am 2026-08-19 zwei. Einer ist seither erledigt; er bleibt durchgestrichen
stehen, weil er dem Auftraggeber als Entscheidungsgrundlage vorgelegen hat und ein still
verschwundener Punkt nicht nachprüfbar wäre.

- ~~`tools/live_betrieb.py:604` — roher `datetime` im Journal.~~ **Am 2026-08-19
  berichtigt und erledigt.** Es war kein Produktionsdefekt: der Produktionspfad wandelte
  Zeitstempel immer korrekt, rot war der Fall nur unter dem Testaufbau. Meine Fehldiagnose
  steht als F-008 in [`fehler.md`](fehler.md); die Ursache (ein Modulname, der zugleich Uhr
  und Typ war) ist behoben und mit rotem und grünem Eichfall festgehalten. **Damit hängt an
  H-004 ein Punkt weniger.**
- **`SPAETER.md` S9** — bei entarteter Streuung sättigt die Deflation der Ereignisstudie
  auf 1,0. Für die gefahrenen Läufe folgenlos, aber unbemerkt in die schmeichelnde
  Richtung.
