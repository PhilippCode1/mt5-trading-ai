# Ereigniskalender (A2)

Je Kandidat die Ereigniszeitpunkte, **in echtem UTC**. Ablage `config/ereigniskalender.json`,
Regeln als Code in `mt5_trading_ai/backtest/kalender.py`, Belege
`tests/test_kalender.py` (26 Fälle).

---

## 1. Die Zeitzonenfalle, geschlossen

Der Auftrag benennt sie ausdrücklich: die Kandidaten hängen an Ortszeiten, die Kerzen
kommen in Serverzeit, und `RealMt5Terminal._utc` deutet den Zeitstempel ungeprüft als UTC.
Gemessen wurde (siehe [`02-DATENLAGE.md`](02-DATENLAGE.md)): die Serverzeit ist
**EET/EEST** — `Europe/Helsinki`, UTC+2 im Winter, UTC+3 im Sommer, Umschaltung nach
**EU**-Regel.

Es ist damit **keine Zahl**, sondern eine Zeitzone. Wer einen festen Versatz einträgt,
liegt sieben Monate im Jahr um eine Stunde daneben — bei einem Ein-Stunden-Fenster heißt
das: vollständig neben dem Ereignis.

`server_zu_utc()` ist die einzige Stelle, an der gedreht wird. Die Drehung darf je
Zeitstempel **genau einmal** angewandt werden; ein bereits gedrehter Zeitstempel ist von
einem ungedrehten nicht zu unterscheiden.

---

## 2. Die fünf Kandidaten

Alle Zeitpunkte sind **abgeleitet**, keiner ist abgelesen. Der Auftrag lässt das
ausdrücklich zu: „Wo der Zeitpunkt ableitbar ist, ist die Ableitungsregel als Code die
Quelle, nicht eine Liste." Eine Liste veraltet, eine Regel nicht.

| # | Ereignis | Instrumente | Zeit | Zone | Regel | Fenster |
|---|---|---|---|---|---|---|
| K1 | London-Fixing | EURUSD, GBPJPY | 16:00 | `Europe/London` | werktäglich | 1 h |
| K2 | Tokioter TTM | GBPJPY | 09:55 | `Asia/Tokyo` | werktäglich | 1 h |
| K3 | Monatsende-Fixing | GBPJPY | 16:00 | `Europe/London` | letzter Werktag | 1 h |
| K4 | Rollover | EURUSD, GBPJPY | 00:00 | `Europe/Helsinki` | werktäglich | 1 h |
| K5 | NASDAQ-Schluss | NVDA | 16:00 | `America/New_York` | werktäglich | 1 h |

**Vier verschiedene Zeitzonen, und sie laufen auseinander.** Am 15.07.2024 liegen die
Ereignisse bei 15:00 (K1), 00:55 (K2), 21:00 (K4) und 20:00 (K5) UTC — vier Zonen mit
drei verschiedenen Sommerzeitregeln, davon eine ohne (Tokio). Kein einzelner Versatz
bedient auch nur zwei davon.

Die Fensterlänge von 1 h ist überall dieselbe. Das ist kein Entwurf, sondern das Ergebnis
der Auflösungsmessung aus [`01-AUFLOESUNG.md`](01-AUFLOESUNG.md): im 1h-Fenster löst jedes
Instrument auf, im 4h-Fenster nicht mehr alle.

---

## 3. Was der Kalender nicht enthält — und warum

**Keine Feiertage.** Der Kalender liefert die planmäßigen Zeitpunkte; ob an einem
Zeitpunkt gehandelt wurde, entscheidet die Kursreihe. Ein Ereignis ohne Kerze fällt in der
Studie heraus. Das ist genauer als ein gepflegter Feiertagskalender — und es kann nicht
veralten, was bei einer Feiertagsliste über 16 Jahre und fünf Handelsplätze der
wahrscheinlichste Fehler wäre.

**Kein angebrochener Monat bei K3.** Endet der Zeitraum mitten im Monat, ist unklar, ob
sein letzter Werktag schon vorbei ist. Ein halber Monat hat kein Monatsende; der Eintrag
entfällt, statt einen Zufallstag zum Ereignis zu erklären.

---

## 4. Der Loader hält Datei und Code zusammen

`load_ereigniskalender()` lädt nicht, wenn die Datei etwas anderes sagt als der Code —
weder bei abweichender Uhrzeit noch bei abweichender Zone, Regel oder Instrumentenliste.
Der Grund ist der teuerste stille Fehler, den dieses Paket haben könnte: eine Studie, die
gegen andere Zeitpunkte läuft als die dokumentierten, liefert eine Zahl, die niemand
nachvollziehen kann.

Ebenso fail-closed: eine **andere** Serverzeitzone lädt nicht. Ein anderer Broker braucht
eine eigene Messung, keinen geänderten Eintrag — die Zone ist gemessen, nicht gesetzt, und
`server_tz_beleg` darf nicht leer sein.

Beleg: `tests/test_kalender.py::test_datei_die_vom_code_abweicht_laedt_nicht`,
`::test_andere_serverzone_laedt_nicht`, `::test_leerer_zeitzonenbeleg_laedt_nicht`.

---

## 5. Nachtrag zum Kandidatenfeld

[`01-AUFLOESUNG.md`](01-AUFLOESUNG.md) hielt fest, dass K3 vom 4h- ins 1h-Fenster wechselt
und alle fünf Kandidaten bleiben. Das gilt beim Aufstellen des Kalenders unverändert.

Erst die Studie hat gezeigt, dass **K5 so nicht messbar ist** — siehe
[`04-EREIGNISSTUDIE.md`](04-EREIGNISSTUDIE.md) Abschnitt 3. Das ist ein Mangel dieses
Kalenders, nicht der Studie: er trägt für K5 einen Zeitpunkt ein, zu dem es die geforderte
Folgestunde nicht gibt.
