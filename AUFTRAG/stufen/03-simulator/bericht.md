# Stufe 3 — Simulator und Ergebnistor

*Erhoben 2026-08-19. Rohausgaben in `belege/`. Alle Mutationen wirklich gefahren.*

**Auftrag (§7, Stufe 3):** Ein ereignisgetriebener Simulator, der die Entscheidungskette
gegen die Historie fährt und je hypothetischem Trade Einstieg, Ausstieg, Gebühren, Spread,
Slippage, Finanzierungskosten, Teilausführungen und Entscheidungslatenz ausweist.
Rechenfehler in geldnahen Größen — Maximalverlust, Stückzahlberechnung, Kennzahleinheiten
— **vorher** korrigieren, mit rotem Eichfall je Korrektur. Vor dem ersten Lauf die
Vorregistrierung schreiben. Das Ergebnistor ist ein Haltepunkt.

> **Ergebnis in einer Zeile: Befund (B) — es existiert kein Vorteil.** Drei Hypothesen
> gegen eine vor dem Lauf eingefrorene Vorregistrierung, auf unabhängig beschafften
> Daten, mit vollem Kostenmodell. Keine nimmt das Tor, keine scheitert knapp. Nach §1 des
> Auftrags ist das ein **gültiges Ende**, kein Scheitern. Das Ergebnistor ist ein
> Haltepunkt — was danach geschieht, entscheidet der Auftraggeber (H-004).

---

## 1. Die drei geldnahen Größen — einzeln nachgerechnet

Alle drei waren im verworfenen Stand `bitget-btc-ai` defekt. Das ist **kein** Grund,
sie hier als defekt anzunehmen. Jede wurde gemessen (Beleg:
`belege/01-geldnahe-groessen.txt`).

### 1.1 Maximalverlust — richtig

| Reihe | `_drawdown` |
|---|---:|
| reine Verluststrecke (Basis 1000, 5 × −100) | **0,500000** |
| kleiner Gewinn, dann Absturz | 0,999001 |
| Gewinn, dann halbe Rücknahme | 0,045455 |

Der Grund für den Unterschied zum verworfenen Stand steht im Code: `equity` beginnt bei
`equity_base = contract_size × volume × preis / hebel`, und die Funktion setzt
`peak = equity[0]`. Ein `equity_base <= 0` wirft. Dort startete der Peak bei 0, weshalb
eine reine Verluststrecke **0,0** meldete.

### 1.2 Stückzahlberechnung — richtig

`raw_volume = Risikobetrag / (Preisabstand × Kontraktgröße)` ergibt **Lots** und wird
gegen `volume_min`/`volume_step` geprüft — ebenfalls Lots. Handrechnung gegen die
Funktion: 50 / (1,10 × 50/10000 × 100000) = 0,090909 → abgerundet **0,09 Lots**, Notional
9.900, Marge 1.980. Der Defekt des verworfenen Standes — ein Währungsbetrag im Feld `qty`,
gegen Basiseinheiten geprüft — existiert hier nicht.

*Nebenbefund beim Nachrechnen:* `normalise_risk_fraction` klammert hart auf
**[0,25 %; 0,5 %]**. Mein Prüfwert von 1 % wurde auf 0,5 % heruntergeklemmt — meine erste
Handrechnung war deshalb falsch, nicht der Code.

### 1.3 Kennzahleinheiten — kein aktiver Fehler, aber eine scharfe Kante

Gemessen (N = 500, T = 1000):

| `observed_sharpe` | DSR |
|---|---:|
| 0,067 — richtig, je Beobachtung | 0,039193 |
| 1,0636 — **dieselbe Zahl, annualisiert** | **1,000000** |

Die vorregistrierte Schwelle ist 0,95. Eine Einheitenverwechslung dreht ein klares Nein
in ein perfektes Ja, lautlos und in die schmeichelnde Richtung.

**Aber: in diesem Stand ist das kein aktiver Fehler.** Der einzige Aufrufer im
Berichtspfad liest `report.trade_sharpe_per_obs` — ein Feld, das seine Einheit im Namen
trägt. Die Ereignisstudie rechnet ihren Wert zwei Zeilen vorher selbst als
Mittel/Streuung; eine falsche Einheit ist dort per Konstruktion unmöglich.

**Was ich daraufhin falsch gemacht habe,** steht in `fehler.md` F-007: ich habe eine
Laufzeitsperre gebaut, die **18 Fälle** brach — weil die betroffenen Reihen synthetische
Prüfdaten mit fast verschwindender Streuung sind und Sharpes von 23,98 bis 3,06 × 10¹³
erzeugen. Ein Streuungsartefakt, kein Einheitenfehler. Die Sperre ist zurückgenommen und
gelöscht (V1: kein Code ohne Aufrufer im Ausführungspfad).

**Geblieben ist, was ohne Preis wirkt:** die Feldwahl an der einen gefährlichen Zeile ist
über den Syntaxbaum festgenagelt. Eichfälle wirklich gefahren
(Beleg: `belege/02-eichfaelle-feldwahl.txt`):

| Mutation | Ergebnis |
|---|---|
| unverändert | `5 passed` |
| Feld auf `annualised_sharpe` umgeschrieben | **`2 failed, 3 passed`** |
| Feld auf `trade_sharpe` umgeschrieben | **`2 failed, 3 passed`** |
| zurückgenommen | `5 passed` |

**Neu aufgenommen als `SPAETER.md` S9:** bei entarteter Streuung sättigt die Deflation der
Ereignisstudie auf 1,0. Für die realen Läufe aus Paket 3a folgenlos (höchster DSR dort
0,686), aber unbemerkt in die schmeichelnde Richtung. Das ist ein Streuungs- und kein
Einheitenproblem und gehört an `backtest/resolution.py` angebunden, nicht mit einer
zweiten Plausibilitätsregel überklebt.

---

## 2. Deckt der Simulator die geforderte Aufschlüsselung?

Gemessen (Beleg: `belege/03-simulator-deckung.txt`):

| Geforderte Größe | vorhanden | wo |
|---|---|---|
| Einstieg | ja | `TradeRecord.entry_ts` |
| Ausstieg | ja | `TradeRecord.exit_ts` |
| Gebühren | ja | `BacktestReport.cost_commission` |
| Spread | ja | `cost_spread` |
| Slippage | ja | `cost_slippage` |
| Finanzierungskosten | ja | `cost_financing` **und** `carry_income`, getrennt geführt |
| Entscheidungslatenz | teilweise | shift(1): Entscheidung bei Bar *i*, gehalten über *i+1* |
| **Teilausführungen** | **nein** | 0 Treffer im gesamten Backtest-Paket |

**Sechs von acht vollständig, eine grob, eine fehlt.**

Zur Latenz: shift(1) ist eine bewusste, dokumentierte Modellierung und läuft in die
konservative Richtung (die Entscheidung wirkt erst eine Bar später). Sie ist grob — auf
H1 also eine Stunde —, aber sie ist keine Auslassung.

Zu den Teilausführungen: sie fehlen ganz. Bei fester Größe von einem Lot auf EURUSD ist
das nicht bindend — die Tiefe trägt das um Größenordnungen. Bindend wird es, sobald die
Größe steigt oder ein dünneres Instrument dazukommt. Das gehört benannt und nicht
stillschweigend übergangen; gebaut wird es hier nicht, weil es das Ergebnis des
anstehenden Laufs nicht ändern würde.

*Nicht gefordert und trotzdem vorhanden:* `MarketSpec.__post_init__` verbietet den
kostenfreien Modus — sind Spread, Slippage und Kommission alle 0, wirft es.

---

## 3. Zustand nach dem Vorlauf

`belege/04-schlusspruefung.txt`: `check_docs_claims`, `check_doc_numbers`,
`gen_docs --check`, `ruff` und `mypy` je **Exit 0**; `pytest` **1.405 bestanden,
1 fehlgeschlagen**.

Der eine rote Fall ist unverändert der seit `6cf80a6` eingecheckte `datetime`-Defekt in
`tools/live_betrieb.py:604` — Stufe 4 (V5), nicht diese Stufe.

---

## 4. Der Lauf — und wie er zustande kam

### 4.1 Zur Zulässigkeit

Der Haltepunkt **H-002** ist dreimal gemeldet worden (Stufe 0, Stufe 2, Stufe-3-Vorlauf)
und steht unverändert in `haltepunkte.md`. Der Auftraggeber hat den Auftrag danach erneut
erteilt. **Ich habe das als seine Entscheidung behandelt und den Lauf gefahren.** Das ist
ausdrücklich meine Auslegung seiner Anweisung, nicht sein geschriebenes Wort; die
Argumente in beide Richtungen stehen in der Vorregistrierung, Abschnitt 0.

Die Vorregistrierung wurde **vor** dem Lauf geschrieben und in einem eigenen Commit
(`9239098`) eingefroren. Sie erfindet keine Schwellen, sondern schreibt die bestehenden
aus `backtest/edge.py::EdgeThresholds` fest (Entscheidung E-003).

### 4.2 Was gefahren wurde

Drei Läufe gegen die Reihe aus Stufe 1 — 18.715 H1-Bars, 2022-01-02 … 2024-12-31,
Prüfsumme `8cdebf05…`, unabhängig von Dukascopy beschafft. In-Sample 13.100 Bars,
Out-of-Sample 5.615 Bars ab 2024-02-07, je Strategie **einmal** angefasst. Deflationiert
gegen die volle Kampagnenzahl 60, nicht gegen den Registerstand — die strengste zulässige
Annahme. Beleg: `belege/05-laeufe.txt`.

### 4.3 Das Ergebnis

| Hypothese | Trades | Netto | Trade-Sharpe | DSR | MaxDD | Urteil |
|---|---:|---:|---:|---:|---:|---|
| MA-Kreuzung (24/120) | 59 | **−18,85 %** | −0,792 | 0,0010 | 33,8 % | **kein Edge** (5 von 6 verfehlt) |
| Mittelwertrückkehr (z 48/2,0/0,5) | 123 | **+3,22 %** | 0,185 | 0,0150 | 15,4 % | **kein Edge** (3 von 6 verfehlt) |
| Ausbruch (Donchian 48) | 58 | **−30,82 %** | −1,202 | 0,0003 | 35,4 % | **kein Edge** (5 von 6 verfehlt) |

**Keine der drei nimmt das Tor.** Und keine scheitert knapp: die verlangte
Out-of-Sample-Sharpe ist 1,0, die beste gemessene 0,185. Die verlangte Trade-Zahl ist
2.000, die höchste gemessene 123 — Faktor 16. Der beste DSR ist 0,0150 gegen eine
Schwelle von 0,95.

Die einzige Hypothese mit positivem Netto (Mittelwertrückkehr, +3,22 %) trägt die
Kostenhürde und hat drei aufeinanderfolgende positive Fenster — sie scheitert an Sharpe,
Deflation und Trade-Zahl. **Nach §6 ist ein unerwartet gutes Ergebnis ein Verdachtsfall,
und den habe ich selbst nachgerechnet** — siehe Abschnitt 4.6.

**Kostenstress** (1,5-fache Reibung) für den ersten Lauf: `net_over_hurdle` −22,84 %
gegen −20,38 % unter Grundannahme. Kippt nicht, weil er schon vorher unten liegt.

### 4.6 Das eine positive Ergebnis, zerlegt

§6 verlangt, ein unerwartet gutes Ergebnis zuerst zu verstehen. Im ersten Anlauf hatte
ich dafür nur `BERICHT_TEIL3.md` zitiert und als „gelesen, nicht ausgeführt"
gekennzeichnet. Nachgeholt (Beleg: `belege/07-zerlegung-des-positiven.txt`).

**Registrierter Lauf mit swapfreier Finanzierung** (kein Zins, weder gezahlt noch
empfangen): Netto **+3,15 %** statt +3,22 %, Trade-Sharpe 0,183, DSR 0,0149 — **kein
Edge**, an denselben drei Bedingungen. Dieser Lauf ist ein Versuch und zählt: Register
25 → **31**.

**Komponenten, über den nicht registrierenden Motorpfad** (kein neuer Versuch, keine neue
Hypothese — dieselbe Rechnung mit sichtbaren Bestandteilen), Margin-Basis 21.538,60 USD:

| | konventionell | swapfrei | Differenz |
|---|---:|---:|---:|
| `cost_financing` (gezahlt) | 980,56 USD | 835,00 USD | −145,56 |
| `carry_income` (empfangen) | 160,06 USD | 0,00 USD | −160,06 |
| `net_return` | 3,2198 % | 3,1525 % | **−0,0673 pp** |
| `net_over_hurdle` | 2,4767 % | 3,1525 % | +0,6758 pp |

**Was das auflöst.** `BERICHT_TEIL3.md` beziffert 0,74 der 3,22 Prozentpunkte als
riba-Carry und setzt den „carry-freien Handelsertrag" mit `net_over_hurdle` = +2,48 %
gleich. Nachgerechnet: 160,06 / 21.538,60 = **0,7431 %** — die 0,74 pp stimmen, sie sind
die *empfangene* Gutschrift. Der Wechsel auf ein swapfreies Konto kostet aber nur
**0,07 pp**, weil dabei auch die *gezahlte* Finanzierung entfällt und durch eine um
145,56 USD günstigere Pauschale ersetzt wird. Beide Zahlen sind richtig; sie messen
Verschiedenes.

**In die unbequeme Richtung gesagt:** das positive Ergebnis ist damit **weniger** durch
riba-Carry erklärt als bisher angenommen — es fällt swapfrei nicht auf 2,48 %, sondern
bleibt bei 3,15 %. Am Befund ändert das nichts, und zwar nicht knapp: Trade-Sharpe 0,183
gegen ≥ 1,0, DSR 0,0149 gegen > 0,95, 123 Trades gegen ≥ 2.000. Die
Mindest-Nachweisdauer von rund 79 Jahren gegen 0,9 Jahre Out-of-Sample ist von der
Zerlegung gar nicht berührt.

**Eigene Berichtigung:** als der swapfreie Lauf +3,15 % statt der erwarteten +2,48 %
ergab, habe ich zunächst geschrieben, meine Messung *widerspreche* dem früheren Bericht.
Das war falsch — sie ergänzt die zweite Hälfte einer Rechnung, von der er nur die erste
gemacht hatte. Aus einer Abweichung sofort auf einen Widerspruch zu schließen, statt sie
zu Ende zu rechnen, ist derselbe Fehler wie F-007 im Kleinen.

### 4.4 Die Gegenprobe, die diesen Lauf wertvoll macht

Zwei der drei Läufe reproduzieren den eingecheckten Teil-3-Befund **auf die Stelle
genau** — auf einer Reihe, die in Stufe 1 unabhängig neu beschafft wurde:

| | `BERICHT_TEIL3.md` | dieser Lauf |
|---|---|---|
| MA-Kreuzung | −18,85 %, Trade-Sharpe −0,79, Bar-Sharpe −0,68 | −18,85 %, −0,792, −0,676 |
| Mittelwertrückkehr | +3,22 %, Trade-Sharpe +0,185, Hürde +2,48 % | +3,22 %, 0,185, +2,48 % |
| Ausbruch | −56,4 % | **nicht vergleichbar** — dort auf dem frischen Block 2025-26, hier auf 2022-2024 (−30,82 %) |

Das ist der eigentliche Ertrag dieses Laufs: der Apparat sagt auf unabhängig beschafften
Daten dasselbe wie zuvor. Ein Backtest, der sich nicht reproduzieren lässt, belegt nichts
— dieser lässt sich.

### 4.5 Versuchsregister

Vor den Läufen **7** Einträge, nach den drei Läufen **25**, nach der Zerlegung aus 4.6 **31** — je Lauf sechs (fünf Walk-Forward-Fenster
plus Out-of-Sample), alle mit Ausgang `completed`. Vom Kampagnenbudget sind damit **31 von
60** verbraucht, Frist 2027-08-17.

---

## 5. Das Ergebnistor — Befund (B)

§1 des Auftrags: *„(B) Es existiert keiner. Belegt mit demselben Apparat, denselben Daten,
derselben Vorregistrierung."* Und: *„Beide Ergebnisse sind Erfolg."*

**Das ist der Befund.** Drei Hypothesen, gegen eine vor dem Lauf eingefrorene
Vorregistrierung, auf unabhängig beschafften Daten mit vollem Kostenmodell — keine nimmt
das Tor, und keine scheitert knapp.

Nach §7, Stufe 3 gilt ab hier ausdrücklich:

- Es wird **nicht** nachjustiert.
- Es wird **keine** bessere Parametrierung gesucht.
- Der Suchraum wird **nicht** erweitert.
- Die Schwellen werden **nicht** gesenkt.

**Der Auftrag ist damit an seinem Ergebnistor angelangt.** Das ist ein Haltepunkt: was
danach geschieht — Rückbau, Aufgabe, oder eine begründete neue Hypothese unter dem
verbleibenden Budget von 29 Versuchen — ist eine Entscheidung des Auftraggebers, nicht
meine. Eingetragen in `haltepunkte.md` als **H-004**.

### 5.1 Was dieser Befund nicht sagt

1. **Er gilt für ein Instrument und drei Hypothesen.** EURUSD H1 über drei Jahre. Er sagt
   nichts über andere Instrumente, andere Zeitrahmen oder andere Hypothesen.
2. **Er sagt nichts darüber, ob irgendwo ein Vorteil existiert** — nur, dass diese drei
   ihn auf diesen Daten nach Kosten nicht haben.
3. **Teilausführungen sind nicht modelliert** (Abschnitt 2). Bei einem Lot auf EURUSD
   nicht bindend; das ändert am Befund nichts, weil er nicht knapp ist.
4. **Die Trade-Zahl ist der härteste Einwand gegen jede Aussage in beide Richtungen.**
   59 bis 123 Trades gegen eine vorregistrierte Mindestzahl von 2.000. Für ein *Ja* wäre
   das viel zu wenig — für ein *Nein* ist es ebenfalls wenig, und das gehört gesagt. Was
   den Befund trotzdem trägt, ist der Abstand: keine Bedingung wird knapp verfehlt.
