# Bewusst zurückgestellt

*Funde, die dieses Paket **nicht** aufgenommen hat. Die Schleifen-Sperre aus §0 des Auftrags
gilt: ein neuer Fund kommt nur dann in dieses Paket, wenn er sich am fertigen Ergebnis zeigt
oder dieses Paket gefährdet. Alles andere steht hier, je mit einem Satz Begründung.*

---

## S2-1 — BTCUSD ist auf dem erreichbaren Handelsplatz nicht messbar

Der MetaQuotes-Demo-Handelsplatz führt keinen Krypto-CFD (12.525 Symbole, davon 0 in einem
Kryptosegment), sodass ein Sechstel des Prüfuniversums ohne Volatilität bleibt.
**Zurückgestellt, weil** die Abhilfe ein zweites Demokonto bei einem der vier recherchierten
Broker wäre — eine Kontoeröffnung, die nicht zum Auftrag dieses Pakets gehört und die der
Auftraggeber selbst vornehmen muss.

## S2-2 — Der Name des Vorgänger-Repositorys fehlt

Der Tag `archive/pre-extraction` liegt nicht in diesem Repo und nicht an seinem Remote; das
Repository, das ihn trägt, ist nirgends benannt, und damit ist die Isolationsbehauptung aus
`README.md` von außen nicht nachprüfbar und der Alt-Baum nicht auf Geheimnisse prüfbar.
**Zurückgestellt, weil** nur der Auftraggeber weiß, wie dieses Repository heißt; die
Behauptung selbst ist in diesem Paket bereits auf „nicht nachprüfbar" korrigiert.

## S2-3 — Slippage ist an keinem Instrument gemessen

Der einzige ungemessene Posten in den Round-Turn-Kosten ist zugleich bei den günstigen
Instrumenten der größte Einzelposten (bei XAUUSD 59 % von K), und kein Broker veröffentlicht
Slippage-Statistiken. **Zurückgestellt, weil** eine Messung eigene Fills im Demobetrieb
voraussetzt, die es noch nicht gibt — deshalb steht sie als bezifferte Abbruchbedingung 3
in `ABBRUCH.md` statt als Annahme im Verborgenen.

## S2-4 — Der Swap fließt in kein Tor zurück

Er ist getrennt ausgewiesen, wie der Auftrag es verlangt, wird danach aber von keiner Sperre
wieder aufgegriffen — obwohl er bei 4 Round-Turns je Tag EURUSD allein von grün auf gelb
kippt. **Zurückgestellt, weil** die Verrechnung eine Annahme über die tatsächliche
Haltedauer verlangt, die erst der Strategiecode liefert; die Zahl steht so lange in Tabelle 4
und in der Robustheitsrechnung sichtbar daneben.

## S2-5 — Die Kommission je Ticket ist nur bei einem Broker modelliert

Admirals' Mindestkommission von 1 USD je Transaktion bindet unterhalb von rund 50 Aktien und
kippt die NVDA-Zeile unterhalb von rund 12 Aktien auf gelb; die anderen Broker
veröffentlichen ihre Mindestgebühren teils gar nicht. **Zurückgestellt, weil** die
Modellierung eine Bezugs-Positionsgröße braucht, die erst mit dem Eigenkapital und der
Strategie feststeht — die gewählte Bezugsgröße (100 Aktien) steht in
`config/broker_costs.json` unter `reference_position`.

## S2-6 — Der ATR fließt nicht in den Stop-Floor am Orderpfad

`risk/sizing.py::executable_stop_floor` bekommt weiter `volatility_bps = 0`, obwohl seit
diesem Paket ein gemessener ATR je Instrument vorliegt; der Floor nimmt das Maximum, die
übrigen Komponenten binden also weiter. **Zurückgestellt, weil** der Anschluss eine
Entscheidung über die Zeitskala verlangt (H1-ATR am Orderpfad oder je Bar neu berechnet) und
weil die Verdrahtungsaufgabe A3 ausdrücklich nur die fünf Sollsperren umfasst.

## S2-7 — US500 ist gemessen, aber nicht in der Kostenmatrix

Der Auftrag verlangt „einen Hauptindex (DAX40 **oder** US500)"; gewählt wurde DE40, weil
IC Markets EU nur dafür Handelszeiten veröffentlicht — US500 wurde trotzdem mitgemessen
(ATR-Median 21,24 bp) und steht ungenutzt in der Messdatei. **Zurückgestellt, weil** eine
zweite Indexzeile den Auftrag erweitert hätte, ohne das Urteil zu ändern.

## S2-8 — Die Drossel läuft mit einem einzigen Kandidaten

`gates/evaluation.py::select_one` wird im Orderpfad mit genau einem Kandidaten aufgerufen;
die Rangfolge- und Korrelationslogik ist dort funktionslos, und die Sperre wirkt nur als
Frequenzbremse. **Zurückgestellt, weil** eine echte Bewertungsschleife mit mehreren
Kandidaten Strategiecode voraussetzt — sie steht bereits als S12 in `SPAETER.md`.

## S2-9 — `Preregistration.as_dict()` wird nirgends geschrieben

Die vorregistrierten Schwellen sind nur durch `frozen=True` und Code-Defaults gesichert, aber
nicht durch einen geschriebenen, datierten Datensatz — eine Änderung der Schwelle wäre damit
ein gewöhnlicher Commit statt eines sichtbaren Bruchs der Vorregistrierung.
**Zurückgestellt, weil** die Aufgabe zur Vorregistrierung in diesem Paket auf die
Widerlegungsmessung aus A5 beschränkt war; die Schwellen selbst sind in `ABBRUCH.md` §2
zusätzlich schriftlich festgehalten.

---

## Nicht zurückgestellt, sondern erledigt

Zur Klarstellung, weil diese Punkte in `SPAETER.md` oder in früheren Berichten als offen
geführt wurden und es jetzt nicht mehr sind:

- **S1 (Risikoschicht am Orderpfad)** — erledigt, siehe [`02-VERDRAHTUNG.md`](02-VERDRAHTUNG.md).
- **S2 (Frische-Latch)** — erledigt, `mt5_trading_ai/execution/freshness.py`.
- **S3 (Zeilenzahl-Drift in `MASTERBERICHT.md` §3)** — erledigt, siehe
  [`03-DOKU-WAHRHEIT.md`](03-DOKU-WAHRHEIT.md) N1.
- **Kill-Switch aus `FEHLT.md` §7** — erledigt, siehe [`02-VERDRAHTUNG.md`](02-VERDRAHTUNG.md) A3.5.
- **Zwei getrennte `RiskManager`-Zustände** — erledigt, Runner und Venue teilen einen.
