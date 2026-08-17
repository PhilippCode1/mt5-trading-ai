# Bewusst zurückgestellt

Was in diesem Paket aufgefallen ist und **nicht** gemacht wurde, jedes mit dem Grund. Ein
Fund ohne Begründung, warum er liegen bleibt, ist ein vergessener Fund.

---

## 1. `RealMt5Terminal._utc()` gibt Serverzeit als UTC aus

**Der Fund.** Die Funktion hängt das Etikett `UTC` an einen Zeitstempel, dessen Wanduhr die
Broker-Serverzeit trägt (EET/EEST, UTC+2 bzw. UTC+3). Weder ihr Name noch `Mt5Rate.ts` noch
ein Kommentar erwähnt das. Details in [`02-DATENLAGE.md`](02-DATENLAGE.md) §4.

**Warum zurückgestellt.** Die Korrektur gehört in den Adapter, aber sie braucht die
Serverzeitzone als Eingabe — und die kennt das Terminal nicht von selbst; sie ist hier
gemessen worden. Sie im Adapter fest zu verdrahten hieße, eine gemessene Eigenschaft
**eines bestimmten Brokers** in eine Schicht zu schreiben, die für jeden Broker gilt.
Paket 3a liest nur; der Umbau eines Moduls, das auch den Schreibpfad trägt, ist nicht sein
Auftrag.

**Was stattdessen geschah.** `mt5_trading_ai/backtest/kalender.py::server_zu_utc()` ist die
einzige Stelle, an der gedreht wird; die Zone steht gemessen und mit Beleg in
`config/ereigniskalender.json` und lädt fail-closed.

**Was es bräuchte.** Eine Serverzeitzone als Konfigurationswert des Handelsplatzes, je
Broker gemessen, plus eine Umstellung aller Verbraucher. Vorher: **nicht** anfassen — ein
halb gedrehter Baum ist schlimmer als ein durchgehend ungedrehter, weil `server_zu_utc()`
einem Zeitstempel nicht ansieht, ob er schon gedreht wurde.

### ERLEDIGT am 2026-08-17 (Abschluss)

`RealMt5Terminal` nimmt jetzt `server_tz`; ist es gesetzt, dreht das Terminal **alle**
seine Zeitstempel selbst in echtes UTC. Ohne den Wert bleibt es beim alten Verhalten —
bewusst kein stiller Standardwert, weil eine geratene Zone für jeden anderen Broker falsch
wäre und ein falscher Versatz schlimmer ist als ein bekannter fehlender.
Beleg: `tests/test_serverzeit_drehung.py` (6 Fälle).

Umgestellt sind die Werkzeuge, die **Entscheidungen** an Uhrzeiten hängen:
`tools/live_betrieb.py` und `tools/live_konsole.py`. Beide reichen `server_tz` herein und
drehen an der Aufrufstelle **nicht** mehr — die zweite Drehung wäre ein zweiter Versatz.

**Bewusst nicht umgestellt: `tools/aufloesung.py`.** Es hat die Belege von Paket 3a
erzeugt, und die müssen reproduzierbar bleiben. Eine Drehung verschöbe jeden Zeitstempel
und damit jede Prüfsumme in `config/reihen/`, ohne an einer einzigen Messung etwas zu
ändern — Streuung und Ereigniszahlen hängen an der Reihenfolge der Kerzen, nicht an ihrer
Beschriftung. Die Manifeste führen dafür jetzt das Feld `zeitbasis`, damit jeder spätere
Leser weiß, was er vor sich hat.

Der Anlass war nicht theoretisch: die Höchsthaltedauer im Betrieb rechnete mit Serverzeit
und meldete für eine 0,77 h alte Position ein Alter von **−2,23 h**. Die Vier-Stunden-Grenze
hätte erst nach sieben realen Stunden gefeuert.

---

## 2. Die Terminal-Obergrenze von 100.000 Balken

**Der Fund.** EURUSD, GBPJPY und XAUUSD liefern auf H1 alle exakt 99.998 Kerzen bei drei
verschiedenen Anfangsdaten; DE40 und NVDA liegen darunter und sind vollständig. Das ist die
Einstellung „Max bars in chart" des Terminals, nicht eine Grenze des Brokers.

**Warum zurückgestellt.** Es ist eine Einstellung im MT5-Terminal des Betreibers, keine
Sache des Codes. Und sie ändert am Urteil nichts: alle sieben Studien lösen auch mit 16
Jahren auf, und sie scheitern nicht an der Ereigniszahl, sondern an der Effektgröße.

**Was es bräuchte.** Ein Handgriff im Terminal plus Nachladen der Historie. Lohnt sich erst,
wenn es eine Frage gibt, die daran hängt.

---

## 3. Die Auflösungsrechnung gegen die messbare Ereigniszahl

**Der Fund.** M6.0 rechnete gegen die Zahl der **Kalendereinträge** statt gegen die Zahl der
Ereignisse, für die es Kurse im Fenster gibt. Bei K5 ist das der Faktor 12 und der Grund,
warum ein Versuch für eine blinde Messung draufging
([`09-EIGENE-FEHLER.md`](09-EIGENE-FEHLER.md) §6).

**Warum zurückgestellt.** Die Korrektur ist klein — die Ereignisse einmal durch
`messe_ereignis` schicken und die Treffer zählen, bevor `assess()` läuft —, aber sie
erfordert, dass die Auflösungsrechnung die Kursreihe **und** den Kalender kennt. Heute kennt
sie nur die Reihe. Das ist ein Umbau der Schnittstelle zwischen A1 und A3, und ihn jetzt zu
machen hieße, ihn ohne laufende Studie zu prüfen.

**Was es bräuchte.** Ein Folgepaket, das A1 und A3 zusammenzieht: erst Kalender, dann
messbare Ereignisse zählen, dann Auflösung, dann messen. In dieser Reihenfolge kann ein
Kandidat wie K5 gar nicht erst durchrutschen.

---

## 4. Die Umkehr-Hypothese ist nicht die einzige mögliche

**Der Fund.** Gemessen wurde **Preisdruck und Umkehr** mit einem Vorzeichen aus der
Vorstunde. Denkbar wären andere Fassungen derselben Zwangslage: Fortsetzung statt Umkehr,
ein Fenster **vor** dem Ereignis statt danach, oder eine Bedingung auf die Größe der
Vorbewegung statt nur ihr Vorzeichen.

**Warum zurückgestellt — und zwar hart.** Jede davon ist eine **zweite Hypothese und ein
zweiter Versuch** (M7). Sie nach einem negativen Ergebnis nachzuschieben, ist genau die
Suche, gegen die die Deflation gebaut ist. Fünf Versuche sind übrig; sie bleiben ungenutzt,
solange keine neue Zwangslage mit eigener Begründungstiefe vorliegt — nicht als Vorrat für
weitere Anläufe auf dieselben fünf.

**Was es bräuchte.** Eine Begründung, warum gerade diese andere Fassung wirtschaftlich zu
erwarten wäre, geschrieben **bevor** jemand die Zahlen kennt. Nach diesem Paket kennt sie
jeder — die Gelegenheit dazu ist vorbei.

---

## 5. XAUUSD und DE40 als Kandidaten

**Der Fund.** Beide lösen im 1h-Fenster auf (0,43 und 0,61), und §5 des Auftrags hält die
Reserveversuche ausdrücklich für diesen Fall bereit.

**Warum zurückgestellt.** Ein Kandidat braucht dieselbe Begründungstiefe wie K1 bis K5: eine
benannte Gruppe, die zu einem benannten Zeitpunkt handeln **muss**. Für XAUUSD wäre das die
LBMA-Auktion, für DE40 die Xetra-Schlussauktion; beides ist plausibel und beides war nicht
ausgearbeitet. Kandidaten aufzunehmen, weil ihre Auflösungszahl passt, und die
wirtschaftliche Begründung nachzureichen, kehrt die Reihenfolge um, auf der das Feld beruht.

**Endgültig, nicht vertagt.** Die Feldregel lässt Ergänzungen nur zu, **bevor** die erste
Studie läuft. Sie ist gelaufen. Ein späteres Paket bringt seine eigene Versuchszahl mit.

Anmerkung zu DE40: die Xetra-Schlussauktion hätte dasselbe Problem wie K5 — nach dem
Schluss gibt es keine handelbare Stunde am selben Tag. Wer diesen Kandidaten aufnimmt,
prüft das zuerst.

---

## 6. Das Qualitätstor kennt keine Intraday-Session bei Aktien

**Der Fund.** `FxSession` löst die Devisenwoche sauber. Für NVDA gibt es nichts
Vergleichbares — die 09:30–16:00-Sitzung, die Sommerzeitlücke zwischen amerikanischer und
europäischer Umstellung, die Halbtage vor Feiertagen. Beim Ablegen einer NVDA-Stundenreihe
über das Qualitätstor würde dasselbe passieren wie zunächst bei EURUSD/H1.

**Warum zurückgestellt.** Dieses Paket legt keine NVDA-Reihe über das Tor ab; es liest sie
aus dem Terminal und hasht sie selbst. Der Bedarf entsteht erst, wenn eine Aktienreihe aus
zweiter Quelle geprüft abgelegt werden soll.

**Was es bräuchte.** Eine `UsEquitySession` nach dem Muster von `FxSession`, am
NY-Handelskalender verankert, samt Halbtagsliste.

---

## 7. Die drei Nachgänge aus Paket 2

Der Auftrag hält fest, dass aus Paket 2 **nichts** in den Rahmen von 3a fällt: alle drei
offenen Punkte brauchen einen Handelsbetrieb oder eine Kostenerhebung. Sie stehen hier,
damit sie nicht verloren gehen — angefangen wurde keiner.

**S2-1 — BTCUSD.** Braucht eine Kostenerhebung bei den vier Brokern. Krypto bleibt
außerdem hart bei Hebel 2:1; die Zeile im Kostentor fehlt bislang ganz.

**S2-3 — Slippage messen.** Der Kern der Sache: die Slippage steht in
`config/broker_costs.json` als **bezifferte Annahme** (0,5 bp für EURUSD, 1,0 bp für
GBPJPY), nicht als Messung. Sie zu messen verlangt Demobetrieb an vier Konten über zwei
Wochen — das war der Inhalt von Paket 3b.

Nach dem Urteil dieses Pakets ist die Messung **nicht mehr dringlich**, und das ist eine
Aussage mit Zahl: selbst bei Slippage null bliebe K für GBPJPY bei 0,84 bp gegen die
nötigen 0,45 bp. Die Messung könnte das Urteil nicht drehen. Sie bleibt richtig für den
Tag, an dem es eine Frage gibt, die daran hängt — Slippage ist eine Eigenschaft des
Brokers und lässt sich zwischen Brokern nicht übertragen.

**S2-7 — US500.** Fällt aus einem harten Grund aus: **keiner der vier Broker führt in
`config/broker_costs.json` eine US500-Kostenzeile.** Ohne K ist US500 in keiner
M6-Rechnung verwendbar — auch nicht als Zusammenlegungspartner für DE40, dessen
Historientiefe von 14 Jahren die kürzeste im Feld ist. Zuerst die Kostenzeile, dann alles
Weitere.
