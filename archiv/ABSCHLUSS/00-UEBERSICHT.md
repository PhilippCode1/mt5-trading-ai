# Übersicht — Paket 2 „Kostentor, Verdrahtung, Wahrheit"

*Stand 2026-08-17. Je Aufgabe eine Zeile: Ampel, Zahl, Bezugsgröße. Jede Aussage trägt
entweder „bestätigt durch Ausführung" mit beiliegender Ausgabe oder „gelesen, nicht
ausgeführt".*

---

> **Nachtrag 2026-08-19 — der Halal-Strang ist aus dem Stand entfernt.** Dieser Ordner
> ist eingefroren und wird deshalb *nicht* umgeschrieben: er bleibt der Beleg dessen, was
> zum genannten Stichtag vorlag. Die darin erwähnte Vorfrage, die zugehörigen Module
> (`costs/halal.py`, `venue/halal.py`), das Live-Tor `_enforce_halal` und die Datei
> `HALAL-VORFRAGE.md` gibt es seit dem 2026-08-19 nicht mehr — auf Anweisung des
> Auftraggebers. Was genau entfernt wurde und was der Wegfall am Orderpfad ändert, steht
> in [`../AUFTRAG/geloescht.md`](../AUFTRAG/geloescht.md). Verweise unten, die auf
> Halal-Dateien zeigen, laufen entsprechend ins Leere.

---

## Die eine Zahl vorweg

**M1 = GRÜN, aber ohne Reserve — und M2 ist gerissen.**

Die erforderliche Trefferquote p\* liegt bei 4 von 6 Prüfinstrumenten unter der Schwelle von
56 % (gefordert: mindestens 3). Getragen wird das Urteil von **Gold (51,0 %), DAX (51,6 %)
und NVIDIA (52,3 %)**. Das Haupt-Währungspaar EURUSD liegt bei 55,5 % — 0,5 Prozentpunkte
vor der Schwelle — und fällt unter drei von fünf gleich vertretbaren Lesarten derselben
Daten heraus. Für EURUSD und GBPJPY liegt zudem die Kostenuntergrenze der **eigenen**
Risikoschicht über dem gemessenen Median-ATR: ein Stop von 1,0 × ATR auf H1 ist dort nach
der Politik dieses Systems nicht handelbar.

**Und die zweite Zahl, die genauso zählt:** die Jahreskostenlast bei der geplanten
Auslegung (4 Round-Turns je Handelstag, 250 Tage, Hebel 5) reißt bei **13 von 18**
Kostenzeilen die 50-%-Grenze aus M2 — bei EURUSD und GBPJPY und NVDA an **jedem** Broker.
Nach M2 ist damit nicht der Maßstab zu ändern, sondern die **Betriebsauslegung**. Die
Gegenrechnung: M2 hält erst bei **4 Round-Turns je Tag mit Hebel 1** oder bei **2
Round-Turns je Tag mit Hebel 2** — jeweils je Instrument beim günstigsten Broker gerechnet.

*Bestätigt durch Ausführung:* [`07-AUSGABEN/kostentor.txt`](07-AUSGABEN/kostentor.txt).

---

## Aufgabe für Aufgabe

| Aufgabe | Ampel | Zahl mit Bezugsgröße | Beleg |
|---|---|---|---|
| **A1 Kostentor** | **GRÜN** | p\* ≤ 56 % bei **4 von 6** Instrumenten; **18 von 24** Kostenzeilen rechenbar (6 Instrumente × 4 Broker) | [01-KOSTENTOR.md](01-KOSTENTOR.md), [`kostentor.txt`](07-AUSGABEN/kostentor.txt) |
| **A1.1 Kosten erhoben** | **GRÜN** | **4 von 3** geforderten EU-Brokern; **22 von 24** Zeilen mit Quelle + Abrufdatum, 2 begründet ohne | [`config/broker_costs.json`](../config/broker_costs.json) |
| **A1.2 Volatilität gemessen** | **GELB** | **6 von 7** Symbolen gemessen (ATR(14), H1, 12 Monate); **BTCUSD nicht gemessen** — kein Krypto-CFD auf dem erreichbaren Terminal | [`atr_messung.txt`](07-AUSGABEN/atr_messung.txt) |
| **A2 Abbruchkriterium** | **GRÜN** | **6 Bedingungen**, jede beziffert; davon **1 bereits ausgelöst** (Bedingung 6) | [06-ABBRUCHKRITERIUM.md](06-ABBRUCHKRITERIUM.md) |
| **A3 Verdrahtung** | **GRÜN** | **5 von 5** Sperren an **3 von 3** eröffnenden Eintrittspunkten; vorher 4 von 5 nur am Live-Konto, 0 von 5 am Demokonto | [02-VERDRAHTUNG.md](02-VERDRAHTUNG.md), [`eichfaelle.txt`](07-AUSGABEN/eichfaelle.txt) |
| **A3.3 Eichfälle** | **GRÜN** | **6 rote** und **2 grüne** Eichfälle; jede der 5 Sperren mindestens einmal rot gefahren | [`eichfaelle.txt`](07-AUSGABEN/eichfaelle.txt) |
| **A3.4 Dauertor** | **GRÜN** | `tests/test_orderpfad_verdrahtung.py`, **28 Fälle**; scheitert laut, wenn es keinen Eintrittspunkt findet | [`eichfaelle.txt`](07-AUSGABEN/eichfaelle.txt) |
| **A3.5 Kill-Switch** | **GRÜN** | Widerspruch aufgelöst: er existiert, verteilt auf **drei** Quelldateien; beide Aussagen korrigiert | [02-VERDRAHTUNG.md](02-VERDRAHTUNG.md) |
| **A4 Doku-Wahrheit** | **GRÜN** | **0** widersprüchliche Zahlen zwischen README, MASTERBERICHT, FEHLT, MODULES — geprüft vom Werkzeug | [`check_doc_numbers.txt`](07-AUSGABEN/check_doc_numbers.txt) |
| **A4.1 Zahlenwächter** | **GRÜN** | Regel 5 neu; **18 von 18** falschen Zeilenzahlen entfernt, Zahl jetzt erzeugt statt gepflegt | [03-DOKU-WAHRHEIT.md](03-DOKU-WAHRHEIT.md) |
| **A4.4 Geheimnisprüfung** | **GRÜN** | **0** echte Funde bei **130** verfolgten Dateien und **342** Blobs aus **50** Commits | [`geheimnispruefung.txt`](07-AUSGABEN/geheimnispruefung.txt) |
| **A5 Alpha-Hypothese** | **ROT** | **1 von 4** Fragen beantwortet; auf Quelle, Gegenpartei und Fortbestand keine haltbare Antwort | [04-ALPHA.md](04-ALPHA.md) |
| **A6 Halal-Vorfrage** | **GRÜN** | **3 getrennte** Fragen formuliert, Alternativkonstruktion daneben; nicht beantwortet (das ist Auftrag) | entfernt am 2026-08-19 |
| **Prüfstand §5** | **GRÜN** | **10 von 10** Läufen mit Exit 0; **581 von 581** Tests grün | [07-AUSGABEN/](07-AUSGABEN/pytest.txt) |

---

## Maßstäbe aus §2 — gemessen dagegen

| Maßstab | Gefordert | Gemessen | Urteil |
|---|---|---|---|
| **M1 Kostentor** | p\* ≤ 56 % bei ≥ 3 von 6 Instrumenten bei ≥ 1 Broker | 4 von 6; strenge Lesart: IC Markets allein trägt 3 | **GRÜN** |
| **M2 Jahreskostenlast** | ≤ 50 % des Eigenkapitals bei 4 RT/Tag, 250 Tagen, Hebel 5 (Krypto 2) | **13 von 18** Kostenzeilen reißen die Grenze; EURUSD 55–64 %, GBPJPY 92–180 %, NVDA 209–1154 % | **ROT — Betriebsauslegung ändern** |
| **M3 Verdrahtung** | 5 von 5 | **5 von 5**, dynamisch gezählt an einer echten Order | **GRÜN** |
| **M4 Doku-Wahrheit** | 0 widersprüchliche Zahlen | **0**, geprüft von `tools/check_doc_numbers.py` | **GRÜN** |

---

## Was dieses Paket nicht liefern konnte

| Lücke | Zahl mit Bezugsgröße | Warum |
|---|---|---|
| Volatilität BTCUSD | **1 von 6** Prüfinstrumenten ohne ATR | Der erreichbare MT5-Handelsplatz (MetaQuotes-Demo, 12.525 Symbole) führt **keinen** Krypto-CFD — nur Forex, Metalle, Indizes und Nasdaq-Titel. Ein geschätzter ATR wäre laut Auftrag wertlos; es steht „nicht gemessen" da |
| Kostenzeilen Aktien-CFD | **2 von 4** Brokern ohne Spread für NVDA | Tickmill EU und Pepperstone EU veröffentlichen für Aktien-CFDs keine Spreadtabelle. Null wäre falsch — die Zeilen fallen begründet aus der Rechnung |
| Swap in Basispunkten | **6 von 18** rechenbaren Zeilen | Nur Admirals und IC Markets (Krypto/Aktien) weisen den Satz als Anteil am Nominal aus. Wer ihn in „Punkten je Lot" veröffentlicht, veröffentlicht den dafür nötigen Pip-Wert nicht — ein geratener Pip-Wert wäre die stille Annahme, die dieses Paket ausschließt |
| Slippage gemessen | **0 von 7** Instrumenten | Kein Broker veröffentlicht Slippage-Statistiken. Der Wert ist eine bezifferte Annahme (0,5–2,0 bp) und der einzige ungemessene Posten in K. Nachzumessen im Demobetrieb — Abbruchbedingung 3 |

---

## Eigene Entscheidungen dieses Laufs

Alle als eigene gekennzeichnet, mit Begründung — im Einzelnen in den jeweiligen Dateien:

1. **Der Demo-Ausstieg der Risikoschicht wurde entfernt** (A3). Sie lief zuvor nur am
   Live-Konto und damit an keinem erreichbaren. → [02-VERDRAHTUNG.md](02-VERDRAHTUNG.md)
2. **Kostentor und Halal-Screen bleiben demo-frei.** Sie schützen vor realem Geld und
   realer Zinsbelastung; auf einem Demokonto gibt es beides nicht. → [02](02-VERDRAHTUNG.md)
3. **Die Reihenfolge der Sperren 2–5 folgt dem bestehenden `RiskManager`**, nicht der
   Auflistung in A3.2. Der Frische-Latch steht dagegen bindend zuerst. → [02](02-VERDRAHTUNG.md)
4. **Die Frist des Frische-Latches ist 5 Sekunden.** → [02](02-VERDRAHTUNG.md)
5. **Sollzahl der Eintrittspunkte ist 3, nicht 5.** `emergency_flatten` und
   `RealMt5Terminal.order_send` sind bewertet und begründet ausgenommen. → [02](02-VERDRAHTUNG.md)
6. **Die PROGRESS.md-Ausnahme bleibt, verschärft.** → [03-DOKU-WAHRHEIT.md](03-DOKU-WAHRHEIT.md)
7. **Die Doku-Obergrenze wurde von 12 auf 24 angehoben**, nicht abgeschafft. → [03](03-DOKU-WAHRHEIT.md)
8. **ATR wird um Session-Lücken bereinigt.** Ein unbereinigter ATR wäre größer und ließe das
   Kostentor besser aussehen. → [01-KOSTENTOR.md](01-KOSTENTOR.md)
9. **Für IC Markets/NVIDIA gilt der veröffentlichte Prozentsatz (20 bp), nicht die
   Mindestgebühr (2,1 bp).** Das kippt diese Zeile von grün auf rot. → [01](01-KOSTENTOR.md)

---

## Eigene Fehler

Vier, davon einer mit Wirkung auf ein Ergebnis:
[09-EIGENE-FEHLER.md](09-EIGENE-FEHLER.md).

## Bewusst zurückgestellt

Neun Funde, je mit einem Satz Begründung: [08-SPAETER.md](08-SPAETER.md).
