# Übersicht Paket 3a

**Die Vorfrage, auf das Auflösbare zugeschnitten.** Dieses Paket liest nur — kein
Broker-Konto, kein Handelsbetrieb, kein Schreibpfad. `allow_write=False` und
`require_demo=True` blieben unangetastet.

---

## Das Ergebnis in einer Zeile

**M5 = GELB. Keine Strategiearbeit. Paket 3b wird nicht geschrieben.** Fünf strukturelle
Zwangslagen wurden benannt und in sieben Studien über bis zu 16 Jahre Stundenhistorie
gemessen. Sie existieren. Sie tragen ihre Kosten nicht — es fehlt der Faktor 4 bis 39.

---

## Je Aufgabe eine Zeile

| Aufgabe | Ampel | Zahl | Bezugsgröße |
|---|---|---|---|
| **A1.1** Historientiefe | ✅ | D1 bis 33,3 J, H4 bis 33,3 J, H1 bis 17,1 J | 15 Reihen, 5 Instrumente × 3 Zeitrahmen |
| **A1.2** Herkunft | ✅ | 15 Manifeste mit SHA-256 | `data_checksum` je Versuch gedeckt |
| **A1.2** Gegenprobe D1 | ⚠️ | 3,57 / 6,84 bp | Schwelle 2 bp — **gerissen**, Ursache Zeitzone |
| **A1.2** Gegenprobe H1 | ✅ | 0,28 / 0,55 bp bei −3 h | Schwelle 2 bp — bestanden nach Drehung |
| **A1.3** Fensterstreuung | ✅ | 13 von 30 Kombinationen auflösbar | gemessen, nicht ATR-skaliert |
| **A2** Ereigniskalender | ✅ | 5 Kandidaten, 4 Zeitzonen, alle abgeleitet | fail-closed, Datei gegen Code geprüft |
| **A3** Ereignisstudien | ❌ | 7 Studien, **7 negative Nettoeffekte** | 0 von 21 Prüfungen aus M6.1/M6.2 bestanden |
| **A4** Urteil | ⚠️ | M5 gelb | Bedingung 6 bleibt ausgelöst |
| **Prüfstand** | ✅ | 8 von 8 Befehlen Exit 0 | Tests, ruff und mypy sauber (Zahlen im KENNZAHLEN-Block der README) |

---

## Die drei Zahlen, auf die es ankommt

**1,36 bp** — der größte Bruttoeffekt im ganzen Feld (K3, Monatsende-Fixing auf GBPJPY),
gegen eine Kostenschwelle von 5,51 bp. Ein Viertel dessen, was nötig wäre.

**0,686** — der höchste Deflated Sharpe über alle sieben Studien, gerechnet auf dem
Out-of-Sample-Drittel gegen T = 12 Versuche. Die Schwelle ist 0,95.

**14 % bis 100 %** — der Anteil von 1.000 zufällig verschobenen Ereignismengen, die
denselben Median erreichen wie die echten Ereignisse. Der gemessene Effekt ist **nicht an
die Zwangslage gebunden**; er ist die allgemeine Eigenschaft der Stundenrendite, nach einer
Bewegung leicht zurückzukehren.

---

## Der wichtigste Einzelbefund

**Die Zeitstempel des Terminals sind nicht UTC.** Sie tragen die Broker-Serverzeit
(EET/EEST, UTC+2 im Winter, UTC+3 im Sommer, Umschaltung nach EU-Regel) und werden vom
Adapter als UTC ausgegeben. Richtig gelesen stimmt der Feed mit einer unabhängigen
institutionellen Quelle auf **0,09 bp** je Stundenrendite überein — in jedem einzelnen
Monat des Jahres.

Naiv gelesen liegt jedes Ein-Stunden-Fenster zwei bis drei Stunden neben seinem Ereignis.
Der Befund gilt für **jede** spätere Arbeit an diesem Terminal, unabhängig vom Urteil dieses
Pakets.

---

## Was gebaut wurde

| Baustein | Zweck |
|---|---|
| `mt5_trading_ai/backtest/resolution.py` | Sondert blinde Studien **vor** der Messung aus |
| `mt5_trading_ai/backtest/kalender.py` | Ereigniszeitpunkte in echtem UTC; die einzige Stelle, an der gedreht wird |
| `mt5_trading_ai/backtest/ereignisstudie.py` | Brutto **und** Netto, mit Bestätigungstests |
| `tools/aufloesung.py` | Historientiefe, Herkunft, Fensterstreuung |
| `tools/ereignisstudie.py` | Die Studien, mit `--selbsttest` ohne Versuchsverbrauch |
| `config/reihen/` | 15 Reihen-Manifeste mit Prüfsummen |
| `config/aufloesung.json`, `config/ereigniskalender.json` | Messdatei und Kalender, beide fail-closed |

`tools/fetch_data.py` kann jetzt auch H1 abrufen (Dukascopy legt Stundenkerzen monatsweise
ab) und hält die Rohdateien zwischen — ohne Zwischenspeicher ist das Werkzeug wegen der
Sperren des Anbieters praktisch nicht ausführbar.

---

## Sechs eigene Fehler

Alle beim Nachrechnen der jeweils vorigen Fassung gefunden, fünf davon in der Richtung, die
schmeichelt. Vollständig in [`09-EIGENE-FEHLER.md`](09-EIGENE-FEHLER.md). Der teuerste
kostete einen Versuch von zwölf: K5 wurde gemessen, obwohl er mit der **messbaren**
Ereigniszahl blind war.

---

## Die Dateien

| Datei | Inhalt |
|---|---|
| [`01-AUFLOESUNG.md`](01-AUFLOESUNG.md) | Auflösungstabelle genähert gegen gemessen, Kandidatenfeld |
| [`02-DATENLAGE.md`](02-DATENLAGE.md) | Historientiefe, Prüfsummen, Gegenprobe, Serverzeit |
| [`03-KALENDER.md`](03-KALENDER.md) | Kandidaten, Ereigniszeitpunkte, Zeitzonenfalle |
| [`04-EREIGNISSTUDIE.md`](04-EREIGNISSTUDIE.md) | Je Studie Effekt, Netto, M6.1/M6.2 |
| [`05-URTEIL.md`](05-URTEIL.md) | Ampeln, sechs Abbruchbedingungen, Empfehlung, Unterschrift |
| [`08-SPAETER.md`](08-SPAETER.md) | Bewusst Zurückgestelltes, je eines mit Grund |
| [`09-EIGENE-FEHLER.md`](09-EIGENE-FEHLER.md) | Was schiefging, ohne Beschönigung |
| [`07-AUSGABEN/`](07-AUSGABEN/) | Rohe Terminalausgaben, eine Datei je Befehl |

**Werden die vier Demokonten noch gebraucht? Nein** — ausdrücklich nicht. Begründung in
[`05-URTEIL.md`](05-URTEIL.md) §6.
